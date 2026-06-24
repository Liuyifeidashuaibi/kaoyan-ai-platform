from __future__ import annotations

from pathlib import Path

import typer

from translator.core.engine import TranslatorEngine
from translator.core.exceptions import TranslatorError
from translator.core.types import (
    ExportFormat,
    SubtitleFormat,
    SubtitleOutputMode,
    TranslationDomain,
    TranslationMode,
)
from translator.exporters import normalize_format
from translator.models.registry import create_provider
from translator.processors import extract_document
from translator.utils.config import Settings, load_config

app = typer.Typer(
    name="translator",
    help="Local AI Translator Engine powered by Ollama and faster-whisper.",
    no_args_is_help=True,
)


def _parse_mode(value: str) -> TranslationMode:
    try:
        return TranslationMode(value.lower())
    except ValueError as exc:
        raise typer.BadParameter("Mode must be 'full' or 'bilingual'") from exc


def _parse_domain(value: str | None) -> TranslationDomain | None:
    if value is None:
        return None
    try:
        return TranslationDomain(value.lower())
    except ValueError as exc:
        raise typer.BadParameter(
            "Domain must be 'textbook', 'paper', or 'technical'"
        ) from exc


def _build_engine(
    config_path: Path | None, *, require_ollama: bool = True
) -> TranslatorEngine:
    config = load_config(config_path)
    config = Settings().apply_to(config)
    provider = create_provider(config.model)
    if require_ollama and not provider.is_available():
        typer.secho(
            f"Ollama is not reachable at {config.model.base_url}. "
            f"Ensure Ollama is running and model '{config.model.name}' is pulled.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    return TranslatorEngine(provider, config)


@app.command("translate")
def translate(
    input: Path | None = typer.Option(
        None, "--input", "-i", help="Input file (text, image, PDF, DOCX)."
    ),
    text: str | None = typer.Option(
        None, "--text", "-t", help="Inline English text to translate."
    ),
    mode: str = typer.Option(
        "full", "--mode", "-m", help="Translation mode: full or bilingual."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output file path (.txt or .md)."
    ),
    fmt: str | None = typer.Option(
        None, "--format", "-f", help="Export format: txt or md/markdown."
    ),
    domain: str | None = typer.Option(
        None, "--domain", "-d", help="Content domain: textbook, paper, technical."
    ),
    config_path: Path | None = typer.Option(
        None, "--config", help="Path to YAML config file."
    ),
) -> None:
    """Translate text, image, PDF, or DOCX."""
    if input is None and text is None:
        raise typer.BadParameter("Provide --input or --text.")
    if input is not None and text is not None:
        raise typer.BadParameter("Use only one of --input or --text.")

    engine = _build_engine(config_path)
    translation_mode = _parse_mode(mode)
    translation_domain = _parse_domain(domain)

    export_format = (
        normalize_format(fmt)
        if fmt
        else normalize_format(engine.config.export.default_format)
    )
    if output is not None and fmt is None:
        export_format = normalize_format(output.suffix.lstrip(".") or "txt")

    try:
        if text is not None:
            result = engine.text_translate(
                text, mode=translation_mode, domain=translation_domain
            )
            from translator.exporters import export_result

            content = export_result(result, export_format)
            if output is not None:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(content, encoding="utf-8")
                typer.secho(f"Saved to {output}", fg=typer.colors.GREEN)
            else:
                typer.echo(content)
        else:
            document = extract_document(input)  # type: ignore[arg-type]
            result, content = engine.translate_and_export(
                document,
                mode=translation_mode,
                export_format=export_format,
                output_path=output,
                domain=translation_domain,
            )
            if output is None:
                typer.echo(content)
            else:
                typer.secho(f"Saved to {output}", fg=typer.colors.GREEN)

        if translation_mode == TranslationMode.BILINGUAL and getattr(result, "pairs", None):
            typer.secho(
                f"Translated {len(result.pairs)} sentence pair(s).",
                fg=typer.colors.CYAN,
            )
        if hasattr(result, "ocr_text") and result.ocr_text:
            typer.secho("OCR text extracted from image.", fg=typer.colors.CYAN)
    except TranslatorError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


@app.command("video")
def video_translate(
    input: Path = typer.Option(..., "--input", "-i", help="Video file (MP4/MKV/MOV)."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Subtitle output path (.srt/.vtt/.txt)."
    ),
    subtitle_mode: str = typer.Option(
        "bilingual",
        "--subtitle-mode",
        help="original, translated, or bilingual.",
    ),
    fmt: str = typer.Option("srt", "--format", "-f", help="srt, vtt, or txt."),
    domain: str | None = typer.Option(
        None, "--domain", "-d", help="Content domain: textbook, paper, technical."
    ),
    config_path: Path | None = typer.Option(
        None, "--config", help="Path to YAML config file."
    ),
) -> None:
    """Transcribe video with Whisper medium and translate subtitles."""
    needs_translation = subtitle_mode.lower() != "original"
    engine = _build_engine(config_path, require_ollama=needs_translation)
    translation_domain = _parse_domain(domain)

    subtitle_format = SubtitleFormat(fmt.lower())
    output_mode = SubtitleOutputMode(subtitle_mode.lower())

    if output is None:
        output = input.with_suffix(f".{subtitle_format.value}")

    try:
        typer.secho("Preparing Whisper medium (auto-install if needed)...", fg=typer.colors.CYAN)
        if engine.config.video.vocal_separation:
            typer.secho(
                "Separating vocals with demucs (auto-install if needed)...",
                fg=typer.colors.CYAN,
            )
        result = engine.translate_video(
            input,
            domain=translation_domain,
            output_mode=output_mode,
        )
        content = engine.export_video_subtitles(
            result,
            fmt=subtitle_format,
            output_path=output,
            output_mode=output_mode,
        )
        typer.secho(f"Saved subtitles to {output}", fg=typer.colors.GREEN)
        typer.secho(f"Generated {len(result.cues)} subtitle cue(s).", fg=typer.colors.CYAN)
        if result.detected_language:
            typer.secho(
                f"Detected language: {result.detected_language}",
                fg=typer.colors.CYAN,
            )
        if output is None:
            typer.echo(content)
    except TranslatorError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


@app.command("check")
def check(
    config_path: Path | None = typer.Option(None, "--config", help="Config file path."),
) -> None:
    """Check Ollama connectivity and configured model."""
    config = load_config(config_path)
    config = Settings().apply_to(config)
    provider = create_provider(config.model)
    if provider.is_available():
        typer.secho(
            f"Ollama OK — {config.model.base_url} (model: {config.model.name})",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            f"Cannot reach Ollama at {config.model.base_url}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    typer.secho(
        f"Whisper model dir: {config.whisper_model_dir}",
        fg=typer.colors.CYAN,
    )


if __name__ == "__main__":
    app()

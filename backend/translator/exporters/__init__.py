from __future__ import annotations

from pathlib import Path

from translator.core.types import ExportFormat, TranslationResult


class BaseExporter:
    def export(self, result: TranslationResult) -> str:
        raise NotImplementedError


class TxtExporter(BaseExporter):
    def export(self, result: TranslationResult) -> str:
        if result.is_bilingual and result.pairs:
            blocks = []
            for pair in result.pairs:
                blocks.append(f"{pair.source}\n{pair.target}")
            return "\n\n".join(blocks) + "\n"
        return (result.full_text or "") + "\n"


class MarkdownExporter(BaseExporter):
    def export(self, result: TranslationResult) -> str:
        title = "# 翻译结果\n\n"
        if result.source_name:
            title = f"# 翻译结果 — {result.source_name}\n\n"

        if result.is_bilingual and result.pairs:
            parts = [title]
            for pair in result.pairs:
                parts.append(f"> {pair.source}\n\n{pair.target}\n")
            return "\n".join(parts)

        body = result.full_text or ""
        return f"{title}{body}\n"


_EXPORTERS: dict[ExportFormat, BaseExporter] = {
    ExportFormat.TXT: TxtExporter(),
    ExportFormat.MARKDOWN: MarkdownExporter(),
}


def normalize_format(value: str) -> ExportFormat:
    lowered = value.lower().strip()
    if lowered in {"md", "markdown"}:
        return ExportFormat.MARKDOWN
    if lowered == "txt":
        return ExportFormat.TXT
    raise ValueError(f"Unsupported export format: {value}")


def export_result(result: TranslationResult, export_format: ExportFormat) -> str:
    exporter = _EXPORTERS.get(export_format)
    if exporter is None:
        raise ValueError(f"No exporter for format: {export_format}")
    return exporter.export(result)


def write_export(
    result: TranslationResult, export_format: ExportFormat, output_path: Path
) -> str:
    content = export_result(result, export_format)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return content

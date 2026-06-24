"""FastAPI application exposing TranslatorAPI as HTTP endpoints."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from translator.server.env import load_server_env

load_server_env()

from translator.models.ollama.model_check import validate_model_config

from translator.api import TranslatorAPI
from translator.core.exceptions import (
    DependencyMissingError,
    FileProcessingError,
    GPUUnavailableError,
    ModelDownloadError,
    ModelNotFoundError,
    TranslationFailedError,
    TranslatorError,
    UnsupportedFormatError,
)
from translator.core.types import (
    ExportFormat,
    ImageTranslationResult,
    SentencePair,
    SubtitleCue,
    SubtitleFormat,
    SubtitleOutputMode,
    TranslationDomain,
    TranslationMode,
    TranslationResult,
    VideoTranslationResult,
)
from translator.exporters import normalize_format
from translator.server.auth import verify_api_key
from translator.server.responses import error_response, success_response
from translator.server.schemas import ExportSubtitlesRequest, ExportTextRequest, TextTranslateRequest
from translator.server.serializers import serialize_translation_result, serialize_video_result
from translator.server.task_queue import run_exclusive

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    try:
        api = get_api()
        validate_model_config(api.engine.config.model)
    except Exception:
        pass

    async def _warmup() -> None:
        try:
            await asyncio.to_thread(get_api().warmup_models)
        except Exception:
            pass

    warmup_task = asyncio.create_task(_warmup())
    yield
    warmup_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await warmup_task


@lru_cache
def get_api() -> TranslatorAPI:
    config_path = os.environ.get("TRANSLATOR_CONFIG_PATH")
    return TranslatorAPI.create(config_path) if config_path else TranslatorAPI.create()


app = FastAPI(
    title="Translator API",
    description="Internal HTTP service for the local AI translation engine",
    version="0.2.0",
    lifespan=_lifespan,
)


def _parse_mode(value: str) -> TranslationMode:
    try:
        return TranslationMode(value.lower())
    except ValueError as exc:
        raise ValueError("mode must be 'full' or 'bilingual'") from exc


def _parse_domain(value: str | None) -> TranslationDomain | None:
    if value is None:
        return None
    try:
        return TranslationDomain(value.lower())
    except ValueError as exc:
        raise ValueError("domain must be 'textbook', 'paper', or 'technical'") from exc


def _parse_subtitle_mode(value: str) -> SubtitleOutputMode:
    try:
        return SubtitleOutputMode(value.lower())
    except ValueError as exc:
        raise ValueError(
            "subtitle_mode must be 'original', 'translated', or 'bilingual'"
        ) from exc


def _parse_export_format(value: str | None) -> ExportFormat | None:
    if value is None:
        return None
    return normalize_format(value)


def _parse_subtitle_format(value: str) -> SubtitleFormat:
    lowered = value.lower().strip()
    try:
        return SubtitleFormat(lowered)
    except ValueError as exc:
        raise ValueError("format must be 'srt', 'vtt', or 'txt'") from exc


def _maybe_export_text(
    api: TranslatorAPI,
    result: TranslationResult | ImageTranslationResult,
    export_format: ExportFormat | None,
) -> str | None:
    if export_format is None:
        return None
    return api.export_text(result, fmt=export_format)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "success" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(str(exc.detail), error_code="HTTP_ERROR"),
    )


@app.exception_handler(ValueError)
async def value_error_handler(_request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content=error_response(str(exc), error_code="INVALID_PARAMETER"),
    )


@app.exception_handler(UnsupportedFormatError)
async def unsupported_format_handler(_request, exc: UnsupportedFormatError):
    return JSONResponse(
        status_code=400,
        content=error_response(str(exc), error_code="UNSUPPORTED_FORMAT"),
    )


@app.exception_handler(FileProcessingError)
async def file_processing_handler(_request, exc: FileProcessingError):
    return JSONResponse(
        status_code=422,
        content=error_response(str(exc), error_code="FILE_PROCESSING_ERROR"),
    )


@app.exception_handler(ModelNotFoundError)
async def model_not_found_handler(_request, exc: ModelNotFoundError):
    return JSONResponse(
        status_code=503,
        content=error_response(str(exc), error_code="MODEL_NOT_FOUND"),
    )


@app.exception_handler(ModelDownloadError)
async def model_download_handler(_request, exc: ModelDownloadError):
    return JSONResponse(
        status_code=503,
        content=error_response(str(exc), error_code="MODEL_DOWNLOAD_ERROR"),
    )


@app.exception_handler(DependencyMissingError)
async def dependency_missing_handler(_request, exc: DependencyMissingError):
    return JSONResponse(
        status_code=503,
        content=error_response(str(exc), error_code="DEPENDENCY_MISSING"),
    )


@app.exception_handler(GPUUnavailableError)
async def gpu_unavailable_handler(_request, exc: GPUUnavailableError):
    return JSONResponse(
        status_code=503,
        content=error_response(str(exc), error_code="GPU_UNAVAILABLE"),
    )


@app.exception_handler(TranslationFailedError)
async def translation_failed_handler(_request, exc: TranslationFailedError):
    return JSONResponse(
        status_code=502,
        content=error_response(str(exc), error_code="TRANSLATION_FAILED"),
    )


@app.exception_handler(TranslatorError)
async def translator_error_handler(_request, exc: TranslatorError):
    return JSONResponse(
        status_code=500,
        content=error_response(str(exc), error_code="TRANSLATOR_ERROR"),
    )


@app.exception_handler(Exception)
async def generic_error_handler(_request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=error_response(str(exc), error_code="INTERNAL_ERROR"),
    )


@app.get("/health")
async def health_check():
    """Service health check (no auth required for monitoring)."""
    api = get_api()
    try:
        info = await asyncio.to_thread(api.health_check)
        return success_response(info, message="ok")
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content=error_response(str(exc), error_code="SERVICE_UNAVAILABLE"),
        )


def _run_translate(func, /, *args, **kwargs):
    return run_exclusive(func, *args, **kwargs)


@app.get("/config", dependencies=[Depends(verify_api_key)])
async def get_config():
    """Read-only view of model and whisper settings."""
    config = get_api().engine.config
    return success_response(
        {
            "model": {
                "name": config.model.name,
                "main_model": config.model.main_model,
                "draft_model": config.model.draft_model,
                "base_url": config.model.base_url,
            },
            "whisper": {
                "model_size": config.whisper.model_size,
                "compute_type": config.whisper.compute_type,
                "device": config.whisper.device,
            },
            "translation": {
                "target_language": config.translation.target_language,
                "single_pass_word_limit": config.translation.single_pass_word_limit,
                "max_chunk_words": config.translation.max_chunk_words,
                "image_max_dimension": config.translation.image_max_dimension,
            },
        }
    )


@app.post("/translate/text", dependencies=[Depends(verify_api_key)])
async def translate_text(body: TextTranslateRequest):
    mode = _parse_mode(body.mode)
    domain = _parse_domain(body.domain)
    export_format = _parse_export_format(body.export_format)
    api = get_api()
    result = await asyncio.to_thread(
        _run_translate, api.translate_text, body.text, mode, domain
    )
    data = serialize_translation_result(result)
    exported = _maybe_export_text(api, result, export_format)
    if exported is not None:
        data["exported_content"] = exported
        data["export_format"] = export_format.value if export_format else None
    return success_response(data, message="Translation completed")


@app.post("/translate/image", dependencies=[Depends(verify_api_key)])
async def translate_image(
    file: UploadFile = File(...),
    mode: str = Form(default="full"),
    domain: str | None = Form(default=None),
    export_format: str | None = Form(default=None),
):
    translation_mode = _parse_mode(mode)
    translation_domain = _parse_domain(domain)
    fmt = _parse_export_format(export_format)
    suffix = Path(file.filename or "upload.png").suffix or ".png"
    api = get_api()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        result = await asyncio.to_thread(
            _run_translate,
            api.translate_image,
            tmp_path,
            translation_mode,
            translation_domain,
        )
        data = serialize_translation_result(result)
        exported = _maybe_export_text(api, result, fmt)
        if exported is not None:
            data["exported_content"] = exported
            data["export_format"] = fmt.value if fmt else None
        return success_response(data, message="Image translation completed")
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/translate/document", dependencies=[Depends(verify_api_key)])
async def translate_document(
    file: UploadFile = File(...),
    mode: str = Form(default="full"),
    domain: str | None = Form(default=None),
    export_format: str | None = Form(default=None),
):
    translation_mode = _parse_mode(mode)
    translation_domain = _parse_domain(domain)
    fmt = _parse_export_format(export_format)
    suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    api = get_api()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        result = await asyncio.to_thread(
            _run_translate,
            api.translate_document,
            tmp_path,
            translation_mode,
            translation_domain,
        )
        data = serialize_translation_result(result)
        exported = _maybe_export_text(api, result, fmt)
        if exported is not None:
            data["exported_content"] = exported
            data["export_format"] = fmt.value if fmt else None
        return success_response(data, message="Document translation completed")
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/translate/video", dependencies=[Depends(verify_api_key)])
async def translate_video(
    file: UploadFile = File(...),
    subtitle_mode: str = Form(default="bilingual"),
    domain: str | None = Form(default=None),
    export_format: str | None = Form(default=None),
):
    translation_domain = _parse_domain(domain)
    output_mode = _parse_subtitle_mode(subtitle_mode)
    subtitle_fmt = _parse_subtitle_format(export_format) if export_format else None
    suffix = Path(file.filename or "upload.mp4").suffix or ".mp4"
    api = get_api()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        result = await asyncio.to_thread(
            _run_translate,
            api.translate_video,
            tmp_path,
            translation_domain,
            output_mode,
        )
        data = serialize_video_result(result)
        if subtitle_fmt is not None:
            exported = await asyncio.to_thread(
                api.export_subtitles, result, subtitle_fmt, None, output_mode
            )
            data["exported_content"] = exported
            data["export_format"] = subtitle_fmt.value
        return success_response(data, message="Video subtitle translation completed")
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/export/text", dependencies=[Depends(verify_api_key)])
async def export_text(body: ExportTextRequest):
    mode = _parse_mode(body.mode)
    export_format = _parse_export_format(body.export_format) or ExportFormat.MARKDOWN
    pairs = [SentencePair(source=p["source"], target=p["target"]) for p in body.pairs]
    if body.ocr_text is not None:
        result: TranslationResult | ImageTranslationResult = ImageTranslationResult(
            mode=mode,
            full_text=body.full_text,
            pairs=pairs,
            source_name=body.source_name,
            ocr_text=body.ocr_text,
        )
    else:
        result = TranslationResult(
            mode=mode,
            full_text=body.full_text,
            pairs=pairs,
            source_name=body.source_name,
        )
    api = get_api()
    content = await asyncio.to_thread(api.export_text, result, export_format)
    return success_response(
        {"content": content, "format": export_format.value},
        message="Export completed",
    )


@app.post("/export/subtitles", dependencies=[Depends(verify_api_key)])
async def export_subtitles(body: ExportSubtitlesRequest):
    subtitle_fmt = _parse_subtitle_format(body.export_format)
    output_mode = (
        _parse_subtitle_mode(body.subtitle_mode)
        if body.subtitle_mode
        else _parse_subtitle_mode(body.mode)
    )
    cues = [
        SubtitleCue(
            index=int(c["index"]),
            start=float(c["start"]),
            end=float(c["end"]),
            text=str(c["text"]),
            translation=c.get("translation"),
        )
        for c in body.cues
    ]
    result = VideoTranslationResult(
        source_name=body.source_name,
        detected_language=body.detected_language,
        mode=output_mode,
        cues=cues,
    )
    api = get_api()
    content = await asyncio.to_thread(
        api.export_subtitles, result, subtitle_fmt, None, output_mode
    )
    return success_response(
        {"content": content, "format": subtitle_fmt.value},
        message="Subtitle export completed",
    )

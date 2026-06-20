"""Translator business routes — auth, validation, proxy to independent service."""

from __future__ import annotations

import logging
import mimetypes

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.settings import EmailExportRequest
from app.schemas.translator import (
    SaveToNotebookRequest,
    TextTranslateRequest,
    TranslateFromNotebookRequest,
)
from app.services.email_service import EmailDeliveryError, send_email_with_attachment
from app.services.export_attachment_service import build_attachment
from app.services.user_settings_service import UserSettingsService
from app.services.translator_service import (
    TranslatorService,
    TranslatorServiceError,
)
from app.infrastructure.cache.translator_cache import get_cached_translator_facade
from app.infrastructure.cache.membership_quota import get_membership_quota_cache
from app.services.wrong_question_service import WrongQuestionService
from app.utils.auth import require_user_id
from app.utils.response import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/translator", tags=["Translator"])


def _get_translator_service() -> TranslatorService:
    """返回带 Redis 缓存的 Translator Facade（接口与 TranslatorService 一致）。"""
    return get_cached_translator_facade()


def _get_wq_service(db: Session = Depends(get_db)) -> WrongQuestionService:
    return WrongQuestionService(db)


def _guess_content_type(filename: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


@router.get("/health")
async def translator_health(
    service: TranslatorService = Depends(_get_translator_service),
):
    """Check upstream Translator service availability."""
    if not service.is_configured:
        return success_response(
            {"available": False, "configured": False},
            message="Translator 服务未配置",
        )
    try:
        data = await service.health_check()
        return success_response(
            {"available": True, "configured": True, **data},
            message="Translator 服务正常",
        )
    except TranslatorServiceError as exc:
        logger.warning("Translator health check failed: %s", exc)
        return success_response(
            {"available": False, "configured": True},
            message=str(exc),
        )


@router.get("/config")
async def translator_config(
    _user_id: str = Depends(require_user_id),
    service: TranslatorService = Depends(_get_translator_service),
):
    try:
        data = await service.get_config()
        return success_response(data)
    except TranslatorServiceError as exc:
        return error_response(str(exc))


@router.post("/text")
async def translate_text(
    body: TextTranslateRequest,
    user_id: str = Depends(require_user_id),
    service: TranslatorService = Depends(_get_translator_service),
):
    allowed, quota = get_membership_quota_cache().check_and_consume(user_id, "translate")
    if not allowed:
        return error_response(
            f"今日翻译额度已用完（{quota.get('translate_used')}/{quota.get('translate_limit')}）",
            data=quota,
        )
    try:
        data = await service.translate_text(
            body.text,
            mode=body.mode,
            domain=body.domain,
            export_format=body.export_format,
        )
        return success_response(data, message="翻译完成")
    except TranslatorServiceError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("文本翻译失败")
        return error_response(f"翻译失败：{exc}")


@router.post("/image")
async def translate_image(
    file: UploadFile = File(...),
    mode: str = Form(default="full"),
    domain: str | None = Form(default=None),
    export_format: str | None = Form(default=None),
    _user_id: str = Depends(require_user_id),
    service: TranslatorService = Depends(_get_translator_service),
):
    content = await file.read()
    filename = file.filename or "upload.png"
    content_type = file.content_type or _guess_content_type(filename)
    try:
        data = await service.translate_image(
            content,
            filename,
            mode=mode,
            domain=domain,
            export_format=export_format,
            content_type=content_type,
        )
        return success_response(data, message="图片翻译完成")
    except TranslatorServiceError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("图片翻译失败")
        return error_response(f"图片翻译失败：{exc}")


@router.post("/document")
async def translate_document(
    file: UploadFile = File(...),
    mode: str = Form(default="full"),
    domain: str | None = Form(default=None),
    export_format: str | None = Form(default=None),
    _user_id: str = Depends(require_user_id),
    service: TranslatorService = Depends(_get_translator_service),
):
    content = await file.read()
    filename = file.filename or "upload.pdf"
    try:
        data = await service.translate_document(
            content,
            filename,
            mode=mode,
            domain=domain,
            export_format=export_format,
        )
        return success_response(data, message="文档翻译完成")
    except TranslatorServiceError as exc:
        return error_response(str(exc))


@router.post("/video")
async def translate_video(
    file: UploadFile = File(...),
    subtitle_mode: str = Form(default="bilingual"),
    domain: str | None = Form(default=None),
    export_format: str | None = Form(default=None),
    _user_id: str = Depends(require_user_id),
    service: TranslatorService = Depends(_get_translator_service),
):
    content = await file.read()
    filename = file.filename or "upload.mp4"
    try:
        data = await service.translate_video(
            content,
            filename,
            subtitle_mode=subtitle_mode,
            domain=domain,
            export_format=export_format,
        )
        return success_response(data, message="视频字幕翻译完成")
    except TranslatorServiceError as exc:
        return error_response(str(exc))


@router.post("/from-notebook")
async def translate_from_notebook(
    body: TranslateFromNotebookRequest,
    user_id: str = Depends(require_user_id),
    wq_service: WrongQuestionService = Depends(_get_wq_service),
    service: TranslatorService = Depends(_get_translator_service),
):
    """Translate content from a notebook material (notes text or attached file)."""
    question = wq_service.get_question(body.question_id, user_id=user_id)
    if not question:
        return error_response("笔记本资料不存在")

    file_type = question.file_type or "other"
    file_path = question.file_path or question.image_path

    try:
        if file_type == "document" and file_path:
            file_bytes, filename = service.read_local_file(file_path)
            data = await service.translate_document(
                file_bytes,
                filename,
                mode=body.mode,
                domain=body.domain,
                export_format=body.export_format,
            )
        elif file_type == "image" and file_path:
            file_bytes, filename = service.read_local_file(file_path)
            data = await service.translate_image(
                file_bytes,
                filename,
                mode=body.mode,
                domain=body.domain,
                export_format=body.export_format,
            )
        elif file_type == "video" and file_path:
            file_bytes, filename = service.read_local_file(file_path)
            video_subtitle_mode = body.subtitle_mode or (
                body.mode
                if body.mode in {"original", "translated", "bilingual"}
                else "bilingual"
            )
            data = await service.translate_video(
                file_bytes,
                filename,
                subtitle_mode=video_subtitle_mode,
                domain=body.domain,
                export_format=body.export_format,
            )
        elif question.notes and question.notes.strip():
            data = await service.translate_text(
                question.notes.strip(),
                mode=body.mode,
                domain=body.domain,
                export_format=body.export_format,
            )
        else:
            return error_response("该资料没有可翻译的文本或支持的文件")

        data["notebook"] = {
            "question_id": question.id,
            "title": question.title,
            "file_type": file_type,
        }
        return success_response(data, message="笔记本资料翻译完成")
    except TranslatorServiceError as exc:
        return error_response(str(exc))


@router.post("/email-export")
async def email_export_translation(
    body: EmailExportRequest,
    user_id: str = Depends(require_user_id),
):
    """Email translation export (txt / docx / pdf) to the user's bound address."""
    try:
        settings_data = UserSettingsService().get_settings(user_id)
    except RuntimeError as exc:
        return error_response(str(exc))

    to_email = (settings_data.get("translation_download_email") or "").strip()
    if not to_email:
        return error_response(
            "Set a translation download email in Settings before exporting."
        )

    try:
        attachment_bytes, filename, mime_type = build_attachment(
            body.content,
            body.export_format,
            body.title,
        )
        send_email_with_attachment(
            to_email=to_email,
            subject=f"Your translation export — {body.title.strip() or 'Translation'}",
            body_text=(
                "Your translation export is attached.\n\n"
                f"Format: {body.export_format.upper()}\n"
                f"Sent to: {to_email}\n"
            ),
            attachment_name=filename,
            attachment_bytes=attachment_bytes,
            attachment_mime=mime_type,
        )
        return success_response(
            {"email": to_email, "format": body.export_format, "filename": filename},
            message=f"Export sent to {to_email}",
        )
    except EmailDeliveryError as exc:
        return error_response(str(exc))
    except RuntimeError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Email export failed")
        return error_response(f"Export failed: {exc}")


@router.post("/save-to-notebook")
async def save_translation_to_notebook(
    body: SaveToNotebookRequest,
    user_id: str = Depends(require_user_id),
    wq_service: WrongQuestionService = Depends(_get_wq_service),
):
    """Save translation result back to notebook notes."""
    question = wq_service.get_question(body.question_id, user_id=user_id)
    if not question:
        return error_response("笔记本资料不存在")

    notes = question.notes or ""
    if body.append and notes.strip():
        new_notes = f"{notes.rstrip()}\n\n---\n\n## 翻译结果\n\n{body.content}"
    else:
        new_notes = body.content

    updated = wq_service.update_question(
        body.question_id,
        user_id,
        notes=new_notes,
    )
    if not updated:
        return error_response("保存失败")
    return success_response(
        {
            "question_id": updated.id,
            "notes": updated.notes,
        },
        message="翻译结果已保存到笔记本",
    )

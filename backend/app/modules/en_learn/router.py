"""英文学习增强路由 — 纠错 + 双语翻译。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.infrastructure.cache.membership_quota import get_membership_quota_cache
from app.modules.en_learn.facade_service import EnLearnFacade, get_en_learn_facade
from app.modules.en_learn.schemas import EnLearnTextRequest
from app.services.translator_service import TranslatorServiceError
from app.utils.auth import require_user_id
from app.utils.response import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/en-learn", tags=["EnLearn"])


@router.post("/translate/text")
async def en_learn_translate_text(
    body: EnLearnTextRequest,
    user_id: str = Depends(require_user_id),
    facade: EnLearnFacade = Depends(get_en_learn_facade),
):
    allowed, quota = get_membership_quota_cache().check_and_consume(user_id, "translate")
    if not allowed:
        return error_response(
            f"今日翻译额度已用完（{quota.get('translate_used')}/{quota.get('translate_limit')}）",
            data=quota,
        )
    try:
        result = await facade.translate_text(body.text, mode=body.mode)
        return success_response(result.model_dump(), message="纠错翻译完成")
    except TranslatorServiceError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("en-learn translate failed")
        return error_response(f"翻译失败：{exc}")


@router.post("/translate/image")
async def en_learn_translate_image(
    file: UploadFile = File(...),
    mode: str = Form(default="bilingual"),
    user_id: str = Depends(require_user_id),
    facade: EnLearnFacade = Depends(get_en_learn_facade),
):
    """图片 OCR 后走纠错 + 翻译（OCR 仍由 Translator 上游处理）。"""
    allowed, quota = get_membership_quota_cache().check_and_consume(user_id, "translate")
    if not allowed:
        return error_response(
            f"今日翻译额度已用完（{quota.get('translate_used')}/{quota.get('translate_limit')}）",
            data=quota,
        )
    content = await file.read()
    try:
        payload = await facade.translate_image_enhanced(
            content,
            file.filename or "upload.png",
            mode=mode,
            content_type=file.content_type,
        )
        return success_response(payload, message="图片纠错翻译完成")
    except TranslatorServiceError as exc:
        return error_response(str(exc))

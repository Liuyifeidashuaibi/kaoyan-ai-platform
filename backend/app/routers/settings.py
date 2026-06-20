"""User module settings API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.schemas.settings import UserSettingsResponse, UserSettingsUpdate
from app.services.user_settings_service import UserSettingsService
from app.utils.auth import require_user_id
from app.utils.response import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["Settings"])


def _svc() -> UserSettingsService:
    return UserSettingsService()


@router.get("")
async def get_settings(user_id: str = Depends(require_user_id)):
    try:
        data = _svc().get_settings(user_id)
        return success_response(UserSettingsResponse(**data).model_dump())
    except RuntimeError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to load settings")
        return error_response(f"Failed to load settings: {exc}")


@router.patch("")
async def update_settings(
    body: UserSettingsUpdate,
    user_id: str = Depends(require_user_id),
):
    try:
        data = _svc().update_settings(
            user_id,
            translation_download_email=body.translation_download_email,
        )
        return success_response(
            UserSettingsResponse(**data).model_dump(),
            message="Settings saved",
        )
    except ValueError as exc:
        return error_response(str(exc))
    except RuntimeError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to update settings")
        return error_response(f"Failed to save settings: {exc}")

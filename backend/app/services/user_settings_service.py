"""Per-user module settings stored in Supabase public.users."""

from __future__ import annotations

import re
from typing import Any

from app.config import get_settings
from supabase import Client, create_client


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserSettingsService:
    def __init__(self) -> None:
        settings = get_settings()
        url = settings.effective_supabase_url
        key = settings.effective_supabase_service_key
        if not url or not key:
            raise RuntimeError("Supabase is not configured")
        self._sb: Client = create_client(url, key)

    @staticmethod
    def _normalize_email(value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if not _EMAIL_RE.match(trimmed):
            raise ValueError("Invalid email address")
        return trimmed.lower()

    def get_settings(self, user_id: str) -> dict[str, Any]:
        resp = (
            self._sb.table("users")
            .select("translation_download_email")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        row = (resp.data or [None])[0]
        email = None
        if row and row.get("translation_download_email"):
            email = str(row["translation_download_email"]).strip() or None
        settings = get_settings()
        configured = bool(
            settings.smtp_host.strip()
            and settings.smtp_from.strip()
        )
        return {
            "translation_download_email": email,
            "email_delivery_configured": configured,
        }

    def update_settings(
        self,
        user_id: str,
        *,
        translation_download_email: str | None = None,
    ) -> dict[str, Any]:
        normalized = self._normalize_email(translation_download_email)
        resp = (
            self._sb.table("users")
            .update({"translation_download_email": normalized})
            .eq("id", user_id)
            .select("translation_download_email")
            .execute()
        )
        row = (resp.data or [None])[0]
        if not row:
            raise RuntimeError("Failed to update settings")
        settings = get_settings()
        return {
            "translation_download_email": row.get("translation_download_email"),
            "email_delivery_configured": bool(
                settings.smtp_host.strip() and settings.smtp_from.strip()
            ),
        }

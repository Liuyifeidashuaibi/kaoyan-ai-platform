"""User settings schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UserSettingsResponse(BaseModel):
    translation_download_email: str | None = None
    email_delivery_configured: bool = False


class UserSettingsUpdate(BaseModel):
    translation_download_email: str | None = Field(
        default=None,
        description="Email for translator export attachments",
    )


class EmailExportRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500_000)
    export_format: str = Field(default="docx", pattern="^(txt|docx|pdf)$")
    title: str = Field(default="Translation", max_length=120)

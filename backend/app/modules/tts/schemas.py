"""TTS 请求/响应 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TtsSynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="仅朗读修正后的标准英文")
    accent: str = Field(default="us", pattern="^(us|uk)$")
    speed: float = Field(default=1.0, ge=0.5, le=1.3)
    voice: str = Field(default="female", pattern="^(male|female)$")


class TtsSentence(BaseModel):
    index: int
    text: str
    start_char: int
    end_char: int

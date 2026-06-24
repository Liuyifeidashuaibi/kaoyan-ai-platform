#!/usr/bin/env python3
"""
Qwen3-TTS GPU 推理服务，监听 :8200。

- Docker Compose 模式：作为 tts-host 容器运行，backend 通过 http://tts-host:8200 调用。
- 本机开发模式：直接在宿主机运行，backend 通过 http://127.0.0.1:8200 调用。

启动（开发模式）: .\\scripts\\start-tts-host.ps1
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from scripts.qwen3_tts_lib import is_qwen_available, synthesize_wav

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tts-host")

app = FastAPI(title="Kaoyan TTS Host", version="1.0")


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    accent: str = "us"
    speed: float = 1.0
    voice: str = "female"


@app.get("/health")
def health():
    ready = is_qwen_available()
    return {"ok": True, "qwen_ready": ready}


@app.post("/synthesize")
def synthesize(req: SynthesizeRequest):
    if not is_qwen_available():
        raise HTTPException(
            status_code=503,
            detail="Qwen3-TTS not installed. Run .\\scripts\\setup-tts.ps1",
        )
    try:
        wav = synthesize_wav(
            req.text,
            accent=req.accent,  # type: ignore[arg-type]
            speed=req.speed,
            voice=req.voice,  # type: ignore[arg-type]
        )
    except Exception as exc:
        logger.exception("synthesize failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(content=wav, media_type="audio/wav")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8200, log_level="info")

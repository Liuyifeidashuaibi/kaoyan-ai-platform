"""
TTS 路由 — 流式 WAV，不持久化 mp3；仅朗读修正英文。
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.modules.tts.engines import TTSService, get_tts_service
from app.modules.tts.schemas import TtsSynthesizeRequest
from app.modules.tts.sentence_split import split_tts_sentences
from app.utils.auth import require_user_id
from app.utils.response import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tts", tags=["TTS"])


@router.post("/sentences")
async def tts_sentences(
    body: TtsSynthesizeRequest,
    _user_id: str = Depends(require_user_id),
):
    """返回分句列表，供前端播放时高亮。"""
    items = split_tts_sentences(body.text)
    return success_response([s.model_dump() for s in items])


@router.post("/stream")
async def tts_stream(
    body: TtsSynthesizeRequest,
    _user_id: str = Depends(require_user_id),
    service: TTSService = Depends(get_tts_service),
):
    """
    流式返回音频：按句合成 WAV chunk，HTTP chunked transfer，不写磁盘。
    首块为 JSON meta（engine/sentences），后续为 audio/wav 片段。
    """

    sentences = split_tts_sentences(body.text)
    if not sentences:
        return error_response("文本为空")

    async def generate() -> AsyncIterator[bytes]:
        meta = {
            "type": "meta",
            "sentences": [s.model_dump() for s in sentences],
        }
        yield (json.dumps(meta, ensure_ascii=False) + "\n").encode("utf-8")
        engine_used = "piper"
        for sent in sentences:
            try:
                wav, engine_used = service.synthesize_wav(
                    sent.text,
                    accent=body.accent,
                    speed=body.speed,
                    voice=body.voice,
                )
            except Exception as exc:
                logger.exception("TTS sentence failed")
                err = {"type": "error", "index": sent.index, "message": str(exc)}
                yield (json.dumps(err, ensure_ascii=False) + "\n").encode("utf-8")
                continue
            header = {
                "type": "audio",
                "index": sent.index,
                "engine": engine_used,
                "bytes": len(wav),
            }
            yield (json.dumps(header, ensure_ascii=False) + "\n").encode("utf-8")
            yield wav

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.post("/synthesize")
async def tts_synthesize(
    body: TtsSynthesizeRequest,
    _user_id: str = Depends(require_user_id),
    service: TTSService = Depends(get_tts_service),
):
    """整段合成 WAV（非流式 fallback）。"""
    try:
        wav, engine = service.synthesize_wav(
            body.text.strip(),
            accent=body.accent,
            speed=body.speed,
            voice=body.voice,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(
        content=wav,
        media_type="audio/wav",
        headers={"X-TTS-Engine": engine},
    )

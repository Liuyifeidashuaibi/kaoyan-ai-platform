"""
多模态输入处理 — ASR / 视觉 OCR / TTS（按需串行调用，不滥用模型）。
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import tempfile
from pathlib import Path

import dashscope
from openai import AsyncOpenAI

from app.config import get_settings
from app.utils.audio_utils import (
    detect_asr_format,
    extract_recognition_text,
    is_silent_wav,
)
from app.utils.image_url import ImageProcessingError, ResolvedImage

logger = logging.getLogger(__name__)

OCR_PROMPT = (
    "请完整提取图片中的全部文字（含所有题号如第一题、第二题、1.、2.、(1)、(2)），"
    "按从上到下、从左到右顺序输出。保留公式、选项、图表旁文字，不要省略、不要总结、不要解释。"
)

# 试卷专用 OCR Prompt：明确忽略手写内容
EXAM_OCR_PROMPT = (
    "你是一个试卷还原助手。请只提取试卷上的原始印刷内容，完全忽略所有手写内容。\n\n"
    "规则：\n"
    "1. 只输出印刷体文字（题目、选项、分值、Directions、说明文字等）\n"
    "2. 完全忽略以下手写内容：手写答案、解题过程、红笔批注、改错标记、圈画、下划线、手写笔记\n"
    "3. 保留所有题号（第一题、第二题、1.、2.、(1)、(2)）\n"
    "4. 保留数学公式（LaTeX 格式）\n"
    "5. 按从上到下、从左到右顺序输出\n"
    "6. 不要省略、不要总结、不要解释、不要添加内容\n"
    "7. 如果某个区域只有手写内容没有印刷内容，则跳过该区域"
)


class MediaService:
    def __init__(self) -> None:
        self.settings = get_settings()
        dashscope.api_key = self.settings.dashscope_api_key
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.dashscope_api_key,
                base_url=self.settings.dashscope_base_url,
                timeout=self.settings.model_timeout_seconds,
            )
        return self._client

    def _compress_image_bytes(self, data: bytes) -> tuple[bytes, str]:
        """压缩图片供 OCR，返回 (bytes, mime)。"""
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(data))
            max_w = self.settings.vision_max_width
            if img.width > max_w:
                ratio = max_w / img.width
                img = img.resize(
                    (max_w, int(img.height * ratio)),
                    Image.Resampling.LANCZOS,
                )
            has_alpha = img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            )
            buf = io.BytesIO()
            if has_alpha:
                img.save(buf, format="PNG", optimize=True)
                return buf.getvalue(), "image/png"
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(buf, format="JPEG", quality=92, optimize=True)
            return buf.getvalue(), "image/jpeg"
        except Exception:
            return data, "image/jpeg"

    def _image_to_data_url(self, image: ResolvedImage, raw_bytes: bytes | None = None) -> str:
        if raw_bytes:
            compressed, mime = self._compress_image_bytes(raw_bytes)
            b64 = base64.b64encode(compressed).decode()
            return f"data:{mime};base64,{b64}"
        return image.api_url

    def _transcribe_sync(self, tmp_path: str, audio_format: str, sample_rate: int) -> str:
        from http import HTTPStatus

        from dashscope.audio.asr import Recognition

        model = self.settings.asr_model
        recognition = Recognition(
            model=model,
            format=audio_format,
            sample_rate=sample_rate,
            callback=None,
            language_hints=["zh", "en"],
        )
        result = recognition.call(tmp_path)
        if result.status_code != HTTPStatus.OK:
            msg = getattr(result, "message", None) or str(result)
            raise RuntimeError(f"ASR 失败 ({result.status_code}): {msg}")

        text = extract_recognition_text(result)
        if not text:
            logger.warning(
                "ASR 无文本 output=%s",
                getattr(result, "output", None),
            )
            raise ImageProcessingError("语音识别结果为空，请靠近麦克风重试")
        return text

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        """
        语音识别 → 文本。
        推荐前端上传 16kHz 单声道 WAV（见 src/lib/audio/wav-recorder.ts）。
        """
        if not audio_bytes:
            raise ImageProcessingError("语音文件为空")
        if len(audio_bytes) > self.settings.max_audio_upload_bytes:
            raise ImageProcessingError(
                f"语音文件过大（上限 {self.settings.max_audio_upload_bytes // 1024 // 1024}MB）"
            )

        audio_format, sample_rate = detect_asr_format(audio_bytes, filename)

        if audio_format == "webm":
            raise ImageProcessingError(
                "当前浏览器上传了 webm 格式，服务端无法识别。"
                "请刷新页面后重试（需使用最新版录音组件）。"
            )

        if audio_format == "wav" and is_silent_wav(audio_bytes):
            raise ImageProcessingError("未检测到有效人声，请靠近麦克风后重试")

        suffix = ".wav" if audio_format == "wav" else Path(filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            text = await asyncio.to_thread(
                self._transcribe_sync,
                tmp_path,
                audio_format,
                sample_rate,
            )
            max_chars = self.settings.max_audio_seconds * 12
            return text[:max_chars]
        except ImageProcessingError:
            raise
        except Exception as exc:
            logger.error("ASR 异常 format=%s rate=%s: %s", audio_format, sample_rate, exc)
            raise RuntimeError(str(exc)) from exc
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def extract_image_text(
        self,
        image: ResolvedImage,
        raw_bytes: bytes | None = None,
        *,
        prompt: str | None = None,
    ) -> str:
        """
        从图片中提取文字。

        :param image: 解析后的图片引用
        :param raw_bytes: 原始图片字节
        :param prompt: 自定义 OCR prompt（默认使用通用 OCR prompt）
        """
        url = self._image_to_data_url(image, raw_bytes)
        ocr_prompt = prompt or OCR_PROMPT
        resp = await self.client.chat.completions.create(
            model=self.settings.vl_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": url}},
                        {"type": "text", "text": ocr_prompt},
                    ],
                }
            ],
            max_tokens=2500,
            temperature=0.01,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            raise RuntimeError("图片未识别到文字")
        return text

    async def synthesize_speech(self, text: str) -> bytes | None:
        if not text.strip():
            return None
        speech_text = text[: self.settings.tts_max_chars]
        try:
            from dashscope.audio.tts import SpeechSynthesizer

            result = SpeechSynthesizer.call(
                model=self.settings.tts_model,
                text=speech_text,
                sample_rate=16000,
                format="wav",
            )
            if result.get_audio_data() is None:
                return None
            return result.get_audio_data()
        except Exception as exc:
            logger.error("TTS 失败: %s", exc)
            return None


_media: MediaService | None = None


def get_media_service() -> MediaService:
    global _media
    if _media is None:
        _media = MediaService()
    return _media

"""本地 Qwen3-TTS + Piper 兜底语音模块。"""

from app.modules.tts.engines import TTSService, get_tts_service

__all__ = ["TTSService", "get_tts_service"]

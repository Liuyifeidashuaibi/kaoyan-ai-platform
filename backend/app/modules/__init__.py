"""
新增业务模块包 — 与 chat / translator / schools 等核心 Service 解耦。

子模块：
- word_dict: ECDICT 离线词库 + AI 生词缓存
- tts: 本地 Qwen3-TTS + Piper 兜底
- en_learn: 英文纠错 + 增强翻译 Facade（复用 TranslatorService，不改其内部）
"""

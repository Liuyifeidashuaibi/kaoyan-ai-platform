from __future__ import annotations



from pathlib import Path



import yaml

from pydantic import BaseModel, Field, field_validator

from pydantic_settings import BaseSettings, SettingsConfigDict



_DEPRECATED_MODELS = frozenset(

    {

        "qwen2.5vl:7b",

        "qwen2.5:7b",

        "qwen2.5-vl:7b",

    }

)





class ModelOllamaOptions(BaseModel):

    temperature: float = 0.1

    num_ctx: int = 4096

    num_predict: int = 1500

    num_batch: int = 256

    num_gpu_layers: int = 99

    draft_num_predict: int = 8
    ocr_num_predict: int = 450
    ocr_num_ctx: int | None = None
    text_draft_num_predict: int = 600
    text_draft_num_ctx: int = 2048
    draft_num_gpu_layers: int | None = None
    use_mmap: bool = True
    keep_alive: str = "10m"
    ocr_keep_alive: str | None = None





class ModelConfig(BaseModel):

    provider: str = "ollama"

    name: str = "translator-speculative"

    main_model: str = "qwen2.5-vl:7b-q4_K_M"

    draft_model: str = "qwen2:0.5b-q4_K_M"

    base_url: str = "http://localhost:11434"

    draft_base_url: str | None = None

    timeout: int = 300

    options: ModelOllamaOptions = Field(default_factory=ModelOllamaOptions)



    @field_validator("name", "main_model", "draft_model")

    @classmethod

    def reject_deprecated_models(cls, value: str) -> str:

        if value in _DEPRECATED_MODELS:

            raise ValueError(

                f"Model '{value}' is deprecated. Use Q4 quantized models only."

            )

        return value





class WhisperConfig(BaseModel):

    model_size: str = "medium"

    device: str = "cuda"

    compute_type: str = "int8"

    model_dir: str = "models/whisper"

    language: str | None = None

    beam_size: int = 5

    best_of: int = 1

    temperature: float = 0.0

    initial_prompt: str | None = None

    vad_filter: bool = True

    vad_min_silence_ms: int = 250

    word_timestamps: bool = True

    no_speech_threshold: float = 0.5

    compression_ratio_threshold: float = 2.4

    log_prob_threshold: float = -1.0

    condition_on_previous_text: bool = False

    hallucination_silence_threshold: float | None = 2.0





class PathsConfig(BaseModel):

    data_dir: str = "data"

    cache_dir: str = "cache"





class TranslationConfig(BaseModel):

    target_language: str = "zh-CN"

    default_domain: str = "technical"

    single_pass_word_limit: int = 1000

    max_chunk_words: int = 800

    image_max_dimension: int = 960
    image_ocr_max_dimension: int = 720
    image_jpeg_quality: int = 85
    image_single_pass_full: bool = True
    use_draft_for_bilingual: bool = True
    bilingual_sentence_batch_size: int = 12
    bilingual_single_pass_sentence_limit: int = 24





class SubtitleConfig(BaseModel):

    max_chars_per_line: int = 42

    max_lines: int = 2

    max_cue_duration: float = 4.5

    max_cue_chars: int = 72

    word_max_gap: float = 0.35

    word_max_duration: float = 4.0





class ExportConfig(BaseModel):

    default_format: str = "markdown"





class VideoConfig(BaseModel):

    audio_format: str = "wav"

    audio_sample_rate: int = 16000

    enhance_audio: bool = True

    vocal_isolation: bool = False

    highpass_hz: int = 80

    lowpass_hz: int = 0

    use_loudnorm: bool = False

    use_dynaudnorm: bool = True

    noise_reduction: bool = False

    vocal_separation: bool = True

    demucs_model: str = "htdemucs_ft"

    demucs_device: str = "cuda"

    demucs_shifts: int = 1





class AppConfig(BaseModel):

    model: ModelConfig = Field(default_factory=ModelConfig)

    whisper: WhisperConfig = Field(default_factory=WhisperConfig)

    paths: PathsConfig = Field(default_factory=PathsConfig)

    translation: TranslationConfig = Field(default_factory=TranslationConfig)

    subtitle: SubtitleConfig = Field(default_factory=SubtitleConfig)

    export: ExportConfig = Field(default_factory=ExportConfig)

    video: VideoConfig = Field(default_factory=VideoConfig)



    def resolve_path(self, relative: str) -> Path:

        root = _project_root()

        return (root / relative).resolve()



    @property

    def whisper_model_dir(self) -> Path:

        return self.resolve_path(self.whisper.model_dir)



    @property

    def data_dir(self) -> Path:

        return self.resolve_path(self.paths.data_dir)



    @property

    def cache_dir(self) -> Path:

        return self.resolve_path(self.paths.cache_dir)





def _project_root() -> Path:

    return Path(__file__).resolve().parents[3]





def _default_config_path() -> Path:

    return _project_root() / "config" / "default.yaml"





def load_config(path: Path | None = None) -> AppConfig:

    config_path = path or _default_config_path()

    if not config_path.exists():

        return AppConfig()

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    return AppConfig.model_validate(raw)





class Settings(BaseSettings):

    model_config = SettingsConfigDict(env_prefix="TRANSLATOR_", extra="ignore")



    ollama_base_url: str | None = None

    ollama_draft_base_url: str | None = None

    ollama_model: str | None = None

    whisper_model_dir: str | None = None

    whisper_device: str | None = None



    def apply_to(self, config: AppConfig) -> AppConfig:

        if self.ollama_base_url:

            config.model.base_url = self.ollama_base_url

        if self.ollama_draft_base_url:

            config.model.draft_base_url = self.ollama_draft_base_url

        if self.ollama_model:

            if self.ollama_model in _DEPRECATED_MODELS:

                raise ValueError(

                    f"TRANSLATOR_OLLAMA_MODEL={self.ollama_model} is deprecated. "

                    "Use translator-speculative or qwen2.5-vl:7b-q4_K_M."

                )

            config.model.name = self.ollama_model

        if self.whisper_model_dir:

            config.whisper.model_dir = self.whisper_model_dir

        if self.whisper_device:

            config.whisper.device = self.whisper_device

        return config



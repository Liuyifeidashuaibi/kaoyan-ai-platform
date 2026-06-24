from __future__ import annotations

from translator.models.base import ModelProvider
from translator.models.ollama.provider import create_ollama_provider
from translator.utils.config import ModelConfig

_PROVIDERS = {
    "ollama": create_ollama_provider,
}


def create_provider(config: ModelConfig) -> ModelProvider:
    factory = _PROVIDERS.get(config.provider)
    if factory is None:
        supported = ", ".join(sorted(_PROVIDERS))
        raise ValueError(
            f"Unknown model provider: {config.provider}. Supported: {supported}"
        )
    return factory(config)

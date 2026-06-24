"""Verify required quantized Ollama models exist locally (no auto-download)."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

from translator.utils.config import ModelConfig

_DEPRECATED = frozenset(
    {
        "qwen2.5vl:7b",
        "qwen2.5:7b",
        "qwen2.5-vl:7b",
    }
)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_MODELFILE = _PROJECT_ROOT / "config" / "Ollama.Modelfile"


def _installed_names(base_url: str) -> set[str]:
    try:
        with httpx.Client(base_url=base_url.rstrip("/"), timeout=10) as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError:
        return set()
    names: set[str] = set()
    for item in data.get("models") or []:
        name = item.get("name")
        if isinstance(name, str) and name:
            names.add(name)
            if ":" in name:
                names.add(name.split(":", 1)[0])
    return names


def _has_model(installed: set[str], model: str) -> bool:
    if model in installed:
        return True
    prefix = f"{model}:"
    return any(name == model or name.startswith(prefix) for name in installed)


def validate_model_config(config: ModelConfig) -> list[str]:
    """Return human-readable issues; print pull/create commands for missing models."""
    issues: list[str] = []
    if config.name in _DEPRECATED or config.main_model in _DEPRECATED:
        issues.append("已废弃 FP16 模型，请改用 Q4 量化模型")

    base = config.base_url.rstrip("/")
    installed = _installed_names(base)

    missing: list[str] = []
    for model in (config.main_model, config.draft_model):
        if model and not _has_model(installed, model):
            missing.append(model)

    if config.name and not _has_model(installed, config.name):
        if config.name not in missing:
            missing.append(config.name)

    if missing or issues:
        print("\n=== Translator 模型检查 ===", file=sys.stderr)
        for item in issues:
            print(f"  [错误] {item}", file=sys.stderr)
        for model in sorted({m for m in missing if m in (config.main_model, config.draft_model)}):
            print(f"  ollama pull {model}", file=sys.stderr)
        if config.name and not _has_model(installed, config.name):
            print(
                f"  ollama create {config.name} -f {_MODELFILE}",
                file=sys.stderr,
            )
            print(
                "  (若主模型已存在: ollama cp qwen2.5vl:7b qwen2.5-vl:7b-q4_K_M)",
                file=sys.stderr,
            )
        print(file=sys.stderr)

    return issues

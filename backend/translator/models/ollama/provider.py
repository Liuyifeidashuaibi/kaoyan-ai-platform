from __future__ import annotations

import base64
from pathlib import Path

import httpx

from translator.models.base import ModelProvider
from translator.models.ollama.client import close_ollama_client, get_ollama_client
from translator.utils.config import ModelConfig


class OllamaProvider:
    """Main VL bundle for vision/full text; draft model for fast bilingual text."""

    def __init__(self, config: ModelConfig) -> None:
        self._config = config
        self._client = get_ollama_client(config.base_url, config.timeout)

    def is_available(self) -> bool:
        try:
            response = self._client.get("/api/tags")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def _model(self) -> str:
        return self._config.name

    def _ollama_options(self, *, ocr: bool = False, draft: bool = False) -> dict:
        opts = self._config.options
        if ocr:
            num_predict = opts.ocr_num_predict
            num_ctx = opts.num_ctx
            num_gpu = opts.num_gpu_layers
        elif draft:
            num_predict = opts.text_draft_num_predict
            num_ctx = opts.text_draft_num_ctx
            num_gpu = opts.num_gpu_layers
        else:
            num_predict = opts.num_predict
            num_ctx = opts.num_ctx
            num_gpu = opts.num_gpu_layers
        return {
            "temperature": opts.temperature,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "num_batch": opts.num_batch,
            "num_gpu": num_gpu,
            "use_mmap": opts.use_mmap,
            "draft_num_predict": opts.draft_num_predict,
        }

    def _payload(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        ocr: bool = False,
        draft: bool = False,
    ) -> dict:
        return {
            "model": model or self._model(),
            "stream": False,
            "keep_alive": self._config.options.keep_alive,
            "options": self._ollama_options(ocr=ocr, draft=draft),
            "messages": messages,
        }

    def translate_text(self, text: str, system_prompt: str, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": f"{user_prompt.strip()}\n\n{text}".strip()},
        ]
        return self._chat(self._payload(messages))

    def translate_text_draft(
        self, text: str, system_prompt: str, user_prompt: str
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": f"{user_prompt.strip()}\n\n{text}".strip()},
        ]
        return self._chat(
            self._payload(
                messages,
                model=self._config.draft_model,
                draft=True,
            )
        )

    def translate_with_image(
        self,
        image_path: Path,
        system_prompt: str,
        user_prompt: str,
        *,
        ocr: bool = False,
    ) -> str:
        image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        prompt = f"{system_prompt}\n{user_prompt}".strip()
        return self._chat(
            self._payload(
                [{"role": "user", "content": prompt, "images": [image_data]}],
                ocr=ocr,
            )
        )

    def _chat(self, payload: dict) -> str:
        response = self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content", "")
        if not content:
            raise RuntimeError("Empty response from Ollama")
        return content.strip()

    def close(self) -> None:
        pass

    def warmup(self) -> None:
        for model, draft in ((self._model(), False), (self._config.draft_model, True)):
            if not model:
                continue
            payload = self._payload(
                [{"role": "user", "content": "."}],
                model=model,
                draft=draft,
            )
            payload["options"] = {**payload["options"], "num_predict": 1}
            try:
                self._client.post("/api/chat", json=payload, timeout=120)
            except httpx.HTTPError:
                pass

    def __enter__(self) -> "OllamaProvider":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def create_ollama_provider(config: ModelConfig) -> ModelProvider:
    return OllamaProvider(config)


def shutdown_ollama_client() -> None:
    close_ollama_client()

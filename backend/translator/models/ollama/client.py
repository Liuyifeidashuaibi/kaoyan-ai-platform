"""Shared httpx clients for Ollama — connection reuse per base URL."""

from __future__ import annotations

import threading

import httpx

_clients: dict[tuple[str, int], httpx.Client] = {}
_lock = threading.Lock()


def get_ollama_client(base_url: str, timeout: int) -> httpx.Client:
    key = (base_url.rstrip("/"), timeout)
    with _lock:
        client = _clients.get(key)
        if client is None:
            client = httpx.Client(
                base_url=key[0],
                timeout=timeout,
                limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            )
            _clients[key] = client
        return client


def close_ollama_client() -> None:
    with _lock:
        for client in _clients.values():
            client.close()
        _clients.clear()

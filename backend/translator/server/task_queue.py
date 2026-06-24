"""Serialize translation work — one inference task at a time."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_lock = threading.Lock()


def run_exclusive(func: Callable[..., T], /, *args, **kwargs) -> T:
    with _lock:
        return func(*args, **kwargs)

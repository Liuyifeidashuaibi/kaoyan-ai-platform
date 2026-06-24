"""CLI entry point for the Translator HTTP server."""

from __future__ import annotations

import os

from translator.server.env import load_server_env


def main() -> None:
    load_server_env()
    import logging
    import uvicorn

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    host = os.environ.get("TRANSLATOR_HOST", "127.0.0.1")
    port = int(os.environ.get("TRANSLATOR_PORT", "8100"))
    uvicorn.run(
        "translator.server.app:app",
        host=host,
        port=port,
        log_level="warning",
        reload=os.environ.get("TRANSLATOR_RELOAD", "").lower() in {"1", "true", "yes"},
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Qwen3-TTS 0.6B 本地合成脚本（GPU 优先）。

.env:
  QWEN3_TTS_ENABLED=true
  QWEN3_TTS_SCRIPT=scripts/qwen3_tts_synthesize.py
  QWEN3_TTS_MODEL=data/tts/qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.qwen3_tts_lib import is_qwen_available, synthesize_wav  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--accent", default="us")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--voice", default="female")
    parser.add_argument("--model", default="")
    args = parser.parse_args()

    model = args.model or None
    if not is_qwen_available(model):
        print(
            "Qwen3-TTS not ready. Run: .\\scripts\\setup-tts.ps1",
            file=sys.stderr,
        )
        sys.exit(1)

    wav = synthesize_wav(
        args.text,
        accent=args.accent,  # type: ignore[arg-type]
        speed=args.speed,
        voice=args.voice,  # type: ignore[arg-type]
        model_path=model,
    )
    sys.stdout.buffer.write(wav)


if __name__ == "__main__":
    main()

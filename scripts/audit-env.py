#!/usr/bin/env python3
"""Audit and merge env files without printing secret values."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        out[key.strip()] = val.strip()
    return out


def is_placeholder(val: str) -> bool:
    if not val:
        return True
    low = val.lower()
    return low.startswith("your_") or low in {"xxx", ""}


def audit() -> None:
    files = [
        ROOT / ".env",
        ROOT / ".env.local",
        ROOT / "crawler" / ".env",
        ROOT / ".env.vercel",
    ]
    for path in files:
        print(f"--- {path.relative_to(ROOT)} ({path.stat().st_size if path.exists() else 0} bytes) ---")
        if not path.exists():
            print("  (missing)")
            continue
        data = parse_env(path)
        for key in sorted(data):
            val = data[key]
            status = "EMPTY" if is_placeholder(val) else f"set ({len(val)} chars)"
            print(f"  {key}: {status}")


def merge_env(target: Path, template: Path, sources: list[Path]) -> None:
    """Fill missing/empty keys in target from sources; create from template if missing."""
    template_text = template.read_text(encoding="utf-8") if template.exists() else ""
    existing = parse_env(target) if target.exists() else {}
    merged = dict(existing)

    for src in sources:
        for key, val in parse_env(src).items():
            if key not in merged or is_placeholder(merged.get(key, "")):
                if not is_placeholder(val):
                    merged[key] = val

    if target.exists():
        lines = target.read_text(encoding="utf-8").splitlines()
        out_lines: list[str] = []
        seen: set[str] = set()
        key_re = re.compile(r"^([A-Z0-9_]+)=")
        for line in lines:
            m = key_re.match(line.strip())
            if m:
                key = m.group(1)
                seen.add(key)
                if key in merged and not is_placeholder(merged[key]):
                    out_lines.append(f"{key}={merged[key]}")
                else:
                    out_lines.append(line)
            else:
                out_lines.append(line)
        append = [
            f"{k}={v}"
            for k, v in sorted(merged.items())
            if k not in seen and not is_placeholder(v)
        ]
        if append:
            if out_lines and out_lines[-1].strip():
                out_lines.append("")
            out_lines.append("# --- auto-merged missing keys ---")
            out_lines.extend(append)
        target.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    else:
        # create from template, substitute merged values
        text = template_text
        for key, val in merged.items():
            if not is_placeholder(val):
                text = re.sub(
                    rf"^{re.escape(key)}=.*$",
                    f"{key}={val}",
                    text,
                    flags=re.MULTILINE,
                )
        target.write_text(text, encoding="utf-8")

    print(f"Updated {target.relative_to(ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "merge":
        crawler = ROOT / "crawler" / ".env"
        merge_env(
            ROOT / ".env",
            ROOT / ".env.example",
            [crawler, ROOT / ".env.local"],
        )
        merge_env(
            ROOT / ".env.local",
            ROOT / ".env.local.example",
            [crawler, ROOT / ".env"],
        )
    else:
        audit()

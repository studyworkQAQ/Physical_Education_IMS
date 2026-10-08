# -*- coding: utf-8 -*-
"""F1-2 的全仓扫描：把 `6–20` / `6-20` / `Borg` / `rpe` 的命中逐条打出来（带上下文）。

只用 python（PowerShell 的 Select-String 对 UTF-8 破折号不稳），只读、不写盘。
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
PATTERNS = [
    ("6–20 (en dash)", re.compile(r"6\u201320")),
    ("6-20 (hyphen)", re.compile(r"6-20")),
    ("Borg", re.compile(r"Borg|borg")),
    ("rpe", re.compile(r"rpe|RPE")),
]
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules",
             ".mypy_cache", ".ruff_cache", "htmlcov", ".coverage"}


def walk(root):
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in {".py", ".md", ".yaml", ".yml", ".txt", ".json",
                                    ".cfg", ".ini", ".toml", ".sql"}:
            continue
        yield p


def main():
    hits = {name: [] for name, _ in PATTERNS}
    for p in walk(ROOT):
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.split("\n"), 1):
            for name, rx in PATTERNS:
                if rx.search(line):
                    hits[name].append((p.relative_to(ROOT).as_posix(), lineno,
                                       line.strip()[:220]))
    for name, _ in PATTERNS:
        rows = hits[name]
        print("=" * 100)
        print(f"### 模式 {name}: {len(rows)} 命中")
        print("=" * 100)
        for rel, lineno, snippet in rows:
            print(f"{rel}:{lineno}: {snippet}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

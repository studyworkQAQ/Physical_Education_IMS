# -*- coding: utf-8 -*-
"""F1-2 的**收敛扫描**：只扫 `backend/` 与 `Document/`（取证件 `.superpowers/` 刻意排除，
因为那一堆文件里出现 `6–20` / `Borg` 是**取证本身**，不是待改的目标）。

每条命中打印文件:行 + 该行前 200 字，并自动判定它是不是「显式否定句」（含「不是」/「原先」/
「撤回」/「错了」之一）。
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
SCOPES = (ROOT / "backend", ROOT / "Document")
TOKENS = (("6\u201320", re.compile("6\u201320")),
          ("6-20", re.compile("6-20")),
          ("Borg", re.compile("Borg")))
NEGATION = ("不是", "原先", "撤回", "错了", "改前")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".coverage"}


def main() -> int:
    totals = {}
    for label, rx in TOKENS:
        rows = []
        for scope in SCOPES:
            for p in sorted(scope.rglob("*")):
                if not p.is_file() or any(d in SKIP_DIRS for d in p.parts):
                    continue
                if p.suffix.lower() not in {".py", ".md", ".yaml", ".yml", ".txt", ".toml"}:
                    continue
                try:
                    text = p.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                for no, line in enumerate(text.split("\n"), 1):
                    if rx.search(line):
                        neg = any(k in line for k in NEGATION)
                        rows.append((p.relative_to(ROOT).as_posix(), no, neg, line.strip()))
        totals[label] = rows
        print("=" * 100)
        print(f"### {label!r}：backend/ + Document/ 合计 {len(rows)} 命中"
              f"（其中显式否定句 {sum(1 for r in rows if r[2])} 条）")
        print("=" * 100)
        for rel, no, neg, line in rows:
            print(f"  [{'否定句' if neg else '⚠️ 非否定'}] {rel}:{no}")
            print(f"        {line[:200]}")
        print()
    print("汇总：", {k: (len(v), sum(1 for r in v if r[2])) for k, v in totals.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())

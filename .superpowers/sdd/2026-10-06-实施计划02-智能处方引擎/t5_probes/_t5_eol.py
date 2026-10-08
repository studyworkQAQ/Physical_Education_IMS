"""量计划正文的行尾一致性，并定位 P5-A10 / P5-A13 两格。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]
for rel in ("Document/2026-10-06-实施计划02-智能处方引擎.md",
            ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md",
            ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-5-report.md"):
    p = ROOT / rel
    b = p.read_bytes()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n")
    cr = b.count(b"\r")
    BOM = b"\xef\xbb\xbf"
    kind = "纯CRLF" if (lf == crlf and cr == crlf) else ("纯LF" if crlf == 0 else "⚠️ 混杂")
    print(f"{rel}")
    print(f"   bytes={len(b)}  CRLF={crlf}  裸LF={lf - crlf}  裸CR={cr - crlf}  "
          f"bom={b[:3] == BOM}  -> {kind}")

plan = ROOT / "Document/2026-10-06-实施计划02-智能处方引擎.md"
t = plan.read_text(encoding="utf-8")
L = t.split("\n")
print(f"\n按 \\n 切：{len(L)} 行")
for i, l in enumerate(L):
    if "P5-A10" in l or "P5-A13" in l:
        print(f"\n--- 行 {i+1}（{len(l)} 字符）---")
        print(l[:1400])

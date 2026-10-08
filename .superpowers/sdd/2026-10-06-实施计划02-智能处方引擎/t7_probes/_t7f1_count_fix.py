"""F1-3 连带（硬规矩 #66）：「三处预检更正」这个计数在两处都要抬一格。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]

# --- 计划正文（CRLF）---
P1 = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
s1 = P1.read_text(encoding="utf-8")
O1 = "- **`prescription` 表**按 spec §4.4 **+ 三处预检更正**："
N1 = ("- **`prescription` 表**按 spec §4.4 **+ 三处预检更正 + fix round 1 的一处追加"
      "（F1-1：`label_at_generation`，控制者错误 #148）**：")
assert s1.count(O1) == 1, s1.count(O1)
P1.write_text(s1.replace(O1, N1), encoding="utf-8", newline="\r\n")

# --- app/db/models/prescription.py（CRLF）---
P2 = ROOT / "backend" / "app" / "db" / "models" / "prescription.py"
s2 = P2.read_text(encoding="utf-8")
O2 = '    """一名学生在某一天生成的一张运动处方。spec §4.4 ``:240`` + **三处预检更正**。\n'
N2 = ('    """一名学生在某一天生成的一张运动处方。spec §4.4 ``:240`` + **三处预检更正**\n'
      '    + **fix round 1 的一处追加**（F1-1：``label_at_generation``，控制者错误 #148）。\n')
assert s2.count(O2) == 1, s2.count(O2)
P2.write_text(s2.replace(O2, N2), encoding="utf-8", newline="\r\n")

for p in (P1, P2):
    b = p.read_bytes()
    print(f"OK {p.name:26s} {len(b):7d} B  CRLF={b.count(bytes([13,10]))} LF={b.count(bytes([10]))}")

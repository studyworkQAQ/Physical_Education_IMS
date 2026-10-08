"""修掉 _t9_close.py 插进计划正文的那 1 个裸 LF（该文件其余 1104 处都是 CRLF）。"""
from pathlib import Path

P = Path(__file__).resolve().parents[3] / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
b = P.read_bytes()
crlf0, lf0 = b.count(b"\r\n"), b.count(b"\n")
print(f"[before] {len(b)} B  CRLF={crlf0}  LF={lf0}  裸LF={lf0 - crlf0}")
assert lf0 - crlf0 == 1, f"预期恰好 1 个裸 LF，实为 {lf0 - crlf0}"

# 逐个定位裸 LF（前面不是 \r 的 \n）
idx = [i for i, ch in enumerate(b) if ch == 0x0A and (i == 0 or b[i - 1] != 0x0D)]
print(f"  裸 LF 的字节偏移 = {idx}")
for i in idx:
    print(f"  上下文 = ...{b[max(0, i-70):i]!r} <LF> {b[i+1:i+70]!r}...")

fixed = bytearray()
prev = None
for ch in b:
    if ch == 0x0A and prev != 0x0D:
        fixed.append(0x0D)
    fixed.append(ch)
    prev = ch
out = bytes(fixed)
P.write_bytes(out)

c = P.read_bytes()
crlf1, lf1 = c.count(b"\r\n"), c.count(b"\n")
print(f"[after]  {len(c)} B  CRLF={crlf1}  LF={lf1}  裸LF={lf1 - crlf1}  "
      f"裸CR={c.count(bytes([13])) - crlf1}")
assert crlf1 == lf1 and c.count(bytes([13])) == crlf1, "仍不是纯 CRLF"
assert len(out) == len(b) + 1, "字节数应恰好 +1"
assert out.replace(b"\r\n", b"\n") == b.replace(b"\r\n", b"\n"), "折成 LF 后内容必须逐字相同"
print("  ✅ 纯 CRLF，且折成 LF 后与改前逐字相同（只多了一个 \\r）")
t = c.decode("utf-8")
print(f"  行数（按 CRLF 切）= {t.count(chr(13) + chr(10))}")

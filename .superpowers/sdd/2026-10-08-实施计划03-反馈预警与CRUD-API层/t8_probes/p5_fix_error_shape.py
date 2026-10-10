"""T8 探针 5：把 tests/api/test_dashboard.py 里 19 处 ``resp.json()["code"|"message"]``
机械地改成 ``resp.json()["error"]["code"|"message"]``。

背景：``app/api/errors.py`` 的统一响应形状是 ``{"error": {"code", "message", "detail"}}``
（``error_response`` 是全仓唯一写那个字面量的地方），而本文件的第一版按**顶层**键读，
故 19 处 ``KeyError``。

⚠️ 只改这两个精确子串，改完立刻复核「还剩几处顶层读法」与「新写法有几处」，
并复核文件的行尾与 BOM（硬规矩 #89：数行尾用 read_bytes()）。
"""
import pathlib

TARGET = pathlib.Path(__file__).resolve().parents[4] / "backend" / "tests" / "api" / "test_dashboard.py"
before_bytes = TARGET.read_bytes()
text = before_bytes.decode("utf-8")

PAIRS = [
    ('.json()["code"]', '.json()["error"]["code"]'),
    ('.json()["message"]', '.json()["error"]["message"]'),
]
counts = {}
for old, new in PAIRS:
    counts[old] = text.count(old)
    text = text.replace(old, new)

TARGET.write_text(text, encoding="utf-8", newline="\n")
after = TARGET.read_bytes()

print("替换前：", {k: v for k, v in counts.items()}, "合计", sum(counts.values()))
print("替换后残留的顶层读法：",
      sum(after.decode('utf-8').count(o) for o, _n in PAIRS))
print("替换后的新写法：",
      sum(after.decode('utf-8').count(n) for _o, n in PAIRS))
print("BOM:", after[:3] == bytes([239, 187, 191]),
      "| CRLF:", after.count(bytes([13, 10])),
      "| LF:", after.count(bytes([10])),
      "| 字节:", len(before_bytes), "->", len(after))

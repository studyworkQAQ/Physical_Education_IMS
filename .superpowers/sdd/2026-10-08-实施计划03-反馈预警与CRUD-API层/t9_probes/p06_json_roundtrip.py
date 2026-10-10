"""Task 9 探针 06：确认 golden_cases.json 能否被 json.dumps(indent=2) 逐字往返。

若能，改它就是「load → 改 dict → dump」，不会顺手动到既有 13 例的一个字节；
若不能，就必须走**文本拼接**（把 GC14 的两段对象插进两条 list 的末尾）。
判据用 read_bytes()（硬规矩 #89 扩写：数行尾用字节）。
"""
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
GOLDEN = ROOT / "backend" / "tests" / "fixtures" / "golden_cases.json"

raw = GOLDEN.read_bytes()
print("bytes:", len(raw), "CRLF:", raw.count(b"\r\n"), "LF:", raw.count(b"\n"))
print("sha256[:16] (as-is):", hashlib.sha256(raw).hexdigest()[:16].upper())
norm = raw.replace(b"\r\n", b"\n")
print("sha256[:16] (CRLF→LF):", hashlib.sha256(norm).hexdigest()[:16].upper())
text = norm.decode("utf-8")

data = json.loads(text)
for kwargs in (
    {"indent": 2, "ensure_ascii": False},
    {"indent": 2, "ensure_ascii": True},
    {"indent": 4, "ensure_ascii": False},
):
    dumped = json.dumps(data, **kwargs)
    print(kwargs, "-> equal:", dumped == text, "| equal+newline:", dumped + "\n" == text,
          "| len", len(dumped.encode("utf-8")))
# 找出第一处不同的位置，看差异是什么形状
dumped = json.dumps(data, indent=2, ensure_ascii=False)
for i, (a, b) in enumerate(zip(text, dumped + "\n")):
    if a != b:
        print("first diff at", i)
        print("  original:", repr(text[max(0, i - 80):i + 80]))
        print("  dumped  :", repr((dumped + "\n")[max(0, i - 80):i + 80]))
        break
else:
    print("no diff in the common prefix; len(text)=", len(text), "len(dumped)+1=", len(dumped) + 1)
print("ends with newline:", text.endswith("\n"), "| trailing bytes:", repr(text[-30:]))
print("sys.argv unused:", sys.argv[0:])

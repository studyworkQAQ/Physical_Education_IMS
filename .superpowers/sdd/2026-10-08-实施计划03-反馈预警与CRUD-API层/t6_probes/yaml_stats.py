"""核算 ``backend/data/alert_rules.yaml`` 的字节数 / 行数 / CRLF 计数 / sha256[:16]。

⚠️ 数行尾与字节数一律用 ``read_bytes()``（硬规矩 #89 的扩写），不用 ``read_text()``
——后者会做通用换行转换，数出来的 CRLF 恒为 0。
⚠️ 若发现 CRLF，就地按字节改写成 LF（``.gitattributes`` 钉了 ``backend/data/*.yaml
text eol=lf``，写成 CRLF 会让指纹与 ``git ls-files --eol`` 双双对不上）。
"""
import hashlib
import pathlib

PATH = pathlib.Path(
    r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend\data\alert_rules.yaml"
)

raw = PATH.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
crlf = raw.count(b"\r\n")
lf = raw.count(b"\n")
print(f"[as-written] bytes={len(raw)} BOM={bom} CRLF={crlf} LF={lf} bare_LF={lf - crlf}")

if bom or crlf:
    fixed = raw
    if bom:
        fixed = fixed[3:]
    fixed = fixed.replace(b"\r\n", b"\n")
    PATH.write_bytes(fixed)
    raw = fixed
    print("[fixed] 已按字节改写成 LF / 去 BOM")

crlf = raw.count(b"\r\n")
lf = raw.count(b"\n")
bom2 = raw.startswith(bytes([0xEF, 0xBB, 0xBF]))
digest = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
lines = raw.decode("utf-8").split("\n")
print(f"[final ] bytes={len(raw)} BOM={bom2} CRLF={crlf} LF={lf}")
print(f"[final ] split-newline 段数={len(lines)} 末段为空={lines[-1] == ''}")
print(f"[final ] sha256[:16]={digest}")
print(f"[final ] 首行={lines[0][:60]!r}")
print(f"[final ] 末行(非空)={lines[-2][:60]!r}")

# version 那一行必须是逐字 version: "1.0"
version_lines = [ln for ln in lines if ln.startswith("version:")]
print(f"[final ] version 行={version_lines}")

# 5 个规则 ID 各在 2 空格缩进处出现一次
import re
for name in ("RED_MINITEST_DROP", "RED_RPE_SUSTAINED", "YELLOW_CHECKIN_GAP",
             "YELLOW_CLASS_RPE_HIGH", "GREEN_MASTERY"):
    hits = re.findall(rf"^\s{{2}}{re.escape(name)}:\s*$", raw.decode("utf-8"),
                      flags=re.MULTILINE)
    print(f"[final ] {name}: 键位命中 {len(hits)} 次")

# 解析一遍，确认加载器读到的形状
import sys
sys.path.insert(0, str(PATH.parents[1]))
import yaml
doc = yaml.safe_load(raw.decode("utf-8"))
print(f"[final ] 顶层键={list(doc)}  version={doc['version']!r} "
      f"({type(doc['version']).__name__})")
print(f"[final ] 规则键={list(doc['rules'])}")
for name, block in doc["rules"].items():
    print(f"         {name}: level={block['level']} scope={block['scope']} "
          f"params={block['params']}")

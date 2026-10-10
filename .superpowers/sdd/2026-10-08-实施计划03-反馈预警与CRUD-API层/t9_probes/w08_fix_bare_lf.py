"""Task 9 落地脚本 08：修 w07 引入的**裸 LF**。

成因（如实记录，这是一次真实的工具错误）：w07 的 ``_edit`` 对每个锚点准备两个候选
（LF 版与 CRLF 版），取「恰好命中一次」的那一个。而**单行锚点**的两个候选是同一个字节串，
于是 LF 版先命中、被选中的 ``replacement`` 也是 LF 版——当那一条的**新文本是多行**时，
就往一个本来全 CRLF 的文件里插进了裸 LF。

⚠️ 判据用 ``read_bytes()``（硬规矩 #89 扩写：数行尾用字节）。两个文件改前的裸 LF 都是
**0**（w07 自己打印的「改前 CRLF=… bare=0」），故「任何裸 LF 都是本次引入的」成立，
一律折回 CRLF 是安全的、且是唯一正确的修法。
⚠️ ``app/api/routers/feedback.py`` 与 ``app/pipeline/alert_stage.py`` **不在本清单里**：
它们本来就是 w/lf（``git ls-files --eol`` 实测），插进去的 LF 与文件一致。
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
TARGETS = ("app/db/models/feedback.py", "app/refdata_prescription.py")
CRLF = b"\r\n"
LF = b"\n"

for rel in TARGETS:
    path = BACKEND / rel
    raw = path.read_bytes()
    crlf0 = raw.count(CRLF)
    bare0 = raw.count(LF) - crlf0
    fixed = raw.replace(CRLF, LF).replace(LF, CRLF)
    path.write_bytes(fixed)
    after = path.read_bytes()
    crlf1 = after.count(CRLF)
    bare1 = after.count(LF) - crlf1
    print(f"{rel}: {len(raw)} B -> {len(after)} B | CRLF {crlf0} -> {crlf1} | "
          f"bare LF {bare0} -> {bare1}")
    assert bare1 == 0, f"{rel} 仍有裸 LF"
    assert crlf1 == crlf0 + bare0, f"{rel} 的行数变了（{crlf0}+{bare0} != {crlf1}）"
print("两个文件的裸 LF 已折回 CRLF，行数不变")
sys.exit(0)

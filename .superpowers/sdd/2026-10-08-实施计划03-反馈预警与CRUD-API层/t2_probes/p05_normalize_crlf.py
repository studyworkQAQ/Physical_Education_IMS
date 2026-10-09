"""把所有被本 Task 改过的文件统一成纯 CRLF（磁盘原状），并印出行尾账（硬规矩 #89 的扩写）。

`backend/app/` 与 `backend/tests/` 下的 .py 全部是纯 CRLF（探针 p02 实测 14 个文件
bareLF = 0），而 IDE 的编辑工具按 \\n 写回，一次编辑就会把改动过的那几行变成 bareLF。
`core.autocrlf = true`，故 git 的 blob 两侧其实一致；但工作树的混合行尾会让
`read_bytes()` 口径的账对不上，也会让下一个用 `newline=""` 读它的人拿到两种行尾。
本脚本把 bareLF 一律补成 CRLF，然后复核 CRLF + bareLF == 总换行数。
"""
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[4] / "backend"
TARGETS = [pathlib.Path(a) for a in sys.argv[1:]]

for rel in TARGETS:
    path = BACKEND / rel if not rel.is_absolute() else rel
    raw = path.read_bytes()
    crlf_before = raw.count(b"\r\n")
    bare_before = raw.count(b"\n") - crlf_before
    fixed = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    path.write_bytes(fixed)
    raw2 = path.read_bytes()
    crlf_after = raw2.count(b"\r\n")
    bare_after = raw2.count(b"\n") - crlf_after
    print(f"{str(rel):48s} before CRLF={crlf_before:5d} bareLF={bare_before:5d}"
          f" | after CRLF={crlf_after:5d} bareLF={bare_after:3d}"
          f" | bytes {len(raw)} -> {len(raw2)}")
    assert bare_after == 0

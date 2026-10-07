# -*- coding: utf-8 -*-
"""P16 — 硬规矩 #56 自查后的两处收紧（给两句补上行内主语）。"""
import hashlib
import pathlib

P = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend\tests\architecture\test_domain_purity.py")
SHA0 = hashlib.sha256(P.read_bytes()).hexdigest()

EDITS = [
    ("补主语 1：level==2 那一档点名 _is_allowed",
     "    * ``level == 2`` 的**跨子包**导入也必须放行（矩阵第 9 行，fix round 5 新加，Plan02\n",
     "    * ``level == 2`` 的**跨子包**导入也必须仍被 :func:`_is_allowed` 放行（矩阵第 9 行，\n"
     "      fix round 5 新加，Plan02\n",
     "的**跨子包**导入也必须放行（矩阵第 9 行"),
    ("补主语 2：「全红」点名本文件三条守卫",
     "    「全红」既可能是守卫坏了、也可能是配方少了一项，两者不可区分（硬规矩 #53）。逐条写进\n",
     "    「全红」既可能是本文件那三条守卫坏了、也可能是配方少了一项，两者不可区分\n"
     "    （硬规矩 #53）。逐条写进\n",
     "「全红」既可能是守卫坏了"),
]

raw = P.read_bytes().decode("utf-8")
assert raw.count("\r\n") == raw.count("\n")
t = raw.replace("\r\n", "\n")
for name, old, new, absent in EDITS:
    assert t.count(old) == 1, (name, t.count(old))
    t = t.replace(old, new, 1)
    assert t.count(new) >= 1 and t.count(absent) == 0, name
    print("  OK", name)
P.write_bytes(t.replace("\n", "\r\n").encode("utf-8"))
back = P.read_bytes()
print("sha256[:16] %s -> %s ; CRLF %d -> %d"
      % (SHA0[:16], hashlib.sha256(back).hexdigest()[:16],
         raw.count("\r\n"), back.count(b"\r\n")))
assert back.count(b"\r\n") == back.count(b"\n")
tt = back.decode("utf-8").replace("\r\n", "\n")
for name, old, new, absent in EDITS:
    print("  闸门 %-34s 新串=%d 旧标记=%d" % (name, tt.count(new), tt.count(absent)))
import py_compile
py_compile.compile(str(P), doraise=True, cfile=str(P) + "c.tmp")
pathlib.Path(str(P) + "c.tmp").unlink()
print("compile OK")

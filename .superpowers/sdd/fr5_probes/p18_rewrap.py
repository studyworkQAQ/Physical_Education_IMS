# -*- coding: utf-8 -*-
"""P18 — 四处散文重排（纯 docstring，不改一个字节代码）。"""
import hashlib
import pathlib
import py_compile

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
PUR = ROOT / "backend/tests/architecture/test_domain_purity.py"
LAY = ROOT / "backend/tests/architecture/test_layering.py"
DAI = ROOT / "backend/app/pipeline/daily.py"

JOBS = [
    (PUR, [
        ("重排 1：level==2 那一 bullet",
         "    * ``level == 2`` 的**跨子包**导入也必须仍被 :func:`_is_allowed` 放行（矩阵第 9 行，\n"
         "      fix round 5 新加，Plan02\n"
         "      Ruling 67）：Task 2 起 ``app/domain/prescription/match.py`` 里的\n"
         "      ``from ..indicators import X`` 就是这一档。⚠️ 它是 ``level == 2`` 而**不是**\n",
         "    * ``level == 2`` 的**跨子包**导入也必须仍被 :func:`_is_allowed` 放行（矩阵第 9 行，\n"
         "      fix round 5 新加，Plan02 Ruling 67）：Task 2 起\n"
         "      ``app/domain/prescription/match.py`` 里的 ``from ..indicators import X`` 就是这一档。\n"
         "      ⚠️ 它是 ``level == 2`` 而**不是**\n",
         "fix round 5 新加，Plan02\n"),
        ("重排 2：干净对照那一段",
         "    「全红」既可能是本文件那三条守卫坏了、也可能是配方少了一项，两者不可区分\n"
         "    （硬规矩 #53）。逐条写进\n"
         "    探针文件后分别调用三条守卫（fix round 1 首跑；fix round 5 用补正后的配方复跑，\n"
         "    14 行 × 3 列 = 42 格逐格相符、0 处不符）::\n",
         "    「全红」既可能是本文件那三条守卫坏了、也可能是配方少了一项，两者不可区分（硬规矩\n"
         "    #53）。逐条写进探针文件后分别调用三条守卫（fix round 1 首跑；fix round 5 用补正后的\n"
         "    配方复跑，14 行 × 3 列 = 42 格逐格相符、0 处不符）::\n",
         "（硬规矩 #53）。逐条写进\n"),
    ]),
    (LAY, [
        ("重排 3：断言里印出来的折算值",
         "    **保持绿**——两份 ``_absolute`` 互相独立，这正是硬规矩 #51 要两份回归测试的原因。\n"
         "    断言里印出来的折算值\n"
         "    也是实跑的：越界档报 ``_absolute('seed', 5, ('app', 'db', 'models'), 'generate') =\n",
         "    **保持绿**——两份 ``_absolute`` 互相独立，这正是硬规矩 #51 要两份回归测试的原因。\n"
         "    断言里印出来的折算值也是实跑的：越界档报\n"
         "    ``_absolute('seed', 5, ('app', 'db', 'models'), 'generate') =\n",
         "    断言里印出来的折算值\n"),
    ]),
    (DAI, [
        ("重排 4：差 +0.37 s 那一段",
         "    21.04，故这两个「均值」都不是 ``round()`` 出来的；组内极差 0.29 s）→ 差\n"
         "    **+0.37 s = +1.8%**，与两组\n"
         "    各自的抖动同量级，**n=2 不足以判定显著**。``elapsed < 60`` 的余量是\n",
         "    21.04，故这两个「均值」都不是 ``round()`` 出来的；组内极差 0.29 s）→ 差\n"
         "    **+0.37 s = +1.8%**，与两组各自的抖动同量级，**n=2 不足以判定显著**。\n"
         "    ``elapsed < 60`` 的余量是\n",
         "，与两组\n"),
    ]),
]

for path, edits in JOBS:
    sha0 = hashlib.sha256(path.read_bytes()).hexdigest()
    raw = path.read_bytes().decode("utf-8")
    assert raw.count("\r\n") == raw.count("\n"), path
    t = raw.replace("\r\n", "\n")
    print("### %s" % path.name)
    for name, old, new, absent in edits:
        assert t.count(old) == 1, (name, t.count(old))
        t = t.replace(old, new, 1)
        assert t.count(new) >= 1 and t.count(absent) == 0, name
        print("   OK  %s" % name)
    path.write_bytes(t.replace("\n", "\r\n").encode("utf-8"))
    back = path.read_bytes()
    print("   sha256[:16] %s -> %s ; CRLF %d -> %d"
          % (sha0[:16], hashlib.sha256(back).hexdigest()[:16],
             raw.count("\r\n"), back.count(b"\r\n")))
    assert back.count(b"\r\n") == back.count(b"\n")
    tt = back.decode("utf-8").replace("\r\n", "\n")
    for name, old, new, absent in edits:
        print("   闸门 %-28s 新串=%d 旧标记=%d" % (name, tt.count(new), tt.count(absent)))
    py_compile.compile(str(path), doraise=True, cfile=str(path) + "c.tmp")
    pathlib.Path(str(path) + "c.tmp").unlink()
    print("   compile OK")

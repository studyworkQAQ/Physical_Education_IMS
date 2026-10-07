# -*- coding: utf-8 -*-
"""pe_fr4_commit.py — 写 commit message（UTF-8 无 BOM、LF）到 TEMP，git add 两个守卫文件后
commit -F，然后打印 git log / git status 自证。不 push。

用法: python pe_fr4_commit.py <仓库根>
"""
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
MSG = os.path.join(os.environ["TEMP"], "pe_fr4_commitmsg.txt")
FILES = ["backend/tests/architecture/test_domain_purity.py",
         "backend/tests/architecture/test_layering.py"]

BODY = """test: Plan02 Task1 fix round 4，给两份 _package_of 补回归断言（Ruling 54）+ 更正「三条守卫」计数（Ruling 55）

Ruling 54 _package_of 是两条架构守卫共同的假绿入口，而此前仓库里没有任何断言看着它：它的实现
是纯路径运算 py.relative_to(BACKEND).with_suffix("").parts[:-1]，上一轮新增的
test_absolute_folding_matches_resolve_name 里 package 入参是手写的四元组，故谁把 parts[:-1]
写成 parts（让它返回**模块路径**而不是包），app/db/models/x.py 里的 from ...seed import … 就会
折成 app.db.seed、不再以 app.seed 开头，守卫当场假绿而全部 481 条测试仍然通过。本轮把断言塞进
已有的那条测试里、**不新增测试函数**（passed 数仍是 481），两个文件各一段（硬规矩 #51：两份
_package_of 就要两份断言），覆盖 4 个形状：app/db/models/organisation.py 与
app/db/models/__init__.py（包深 3；两者必须给出**同一个**包 ("app","db","models")——这一格正是
parts[:-1] 这个写法的全部理由，test_layering.py 的 docstring 解释过它、但此前没有断言）、
app/domain/indicators.py（包深 2）、app/domain/prescription/match.py（Task 2 才会出现的形状；
_package_of 不碰文件系统，故可以先断言）。同时按硬规矩 #50 的红档要求**显式断言不等于错的形状**
（("app","db","models","organisation") 一类），让读者知道这条断言在挡什么；再补一段「后果也要能
跑」：把 _package_of 的输出直接喂给 _absolute，仍须与 importlib.util.resolve_name 逐字相同
（判据锚在 Python 自己的语义上，不是锚在一张期望值表上）。断言消息里写明后果，并按硬规矩 #52
逐个实跑过：app/domain/x.py + from ..seed 折成 app.domain.seed（_is_allowed -> True，假绿）、
app/db/models/x.py + from ...seed 折成 app.db.seed（_is_forbidden -> False，假绿）。

两个 docstring 的「本测试守不住什么（硬规矩 #39）」第一条已**不再成立**（原文写的是
「_package_of 不在守卫范围内……本测试照样全绿」），改成新的能力边界：_package_of 由本测试末尾
那一段看着，但**只在枚举到的那 4 个形状上**，没枚举进去的包深（包深 4 及更深）不被覆盖，而 11 格
矩阵的 package 入参仍是手写的，故矩阵与末尾那一段互不覆盖、谁也不替代谁。

Ruling 55 test_domain_purity.py 模块 docstring 开头那句「三条守卫，Plan 02 Task 1 全部改写过
一次」会让数 test_* 个数的人对不上（本文件有 4 个）。改成「本文件有 4 个 test_*：三条架构守卫
+ 一条辅助函数的单元测试（test_absolute_folding_matches_resolve_name，测 _absolute /
_package_of，不是第四条守卫）」，原句的其余部分逐字保留。test_layering.py 按派单要求一并 grep
过：通篇是单数「本守卫」、没有任何关于守卫条数的计数陈述，故无同类问题、未改。

超出派单的三处最小更正（主动披露，全部在这两个文件内）：① purity 侧 _absolute docstring 里
Ruling 37 那段「_package_of 的规格说明」写「谁按假举例对齐代码，app/domain/x.py 里的
from ..seed import generate 就会折成 app.domain.seed.generate」——折算串错了，实跑是
app.domain.seed（generate 住在 node.names 里、不进折算串，Ruling 36）；「假绿」这个结论不变，
与 Ruling 42 同型（结论对、机制错）。本轮正要给 _package_of 加断言，留着它会让同一个文件里
「断言消息说 app.domain.seed、docstring 说 app.domain.seed.generate」自相矛盾（Ruling 32 的
就近修正先例）。layering 侧同一句话写的是 app.db.seed，实跑相符，未动。② 两处
「本轮的改动面被钉死在『新增这一条测试函数』之内」的注释：那条函数是 fix round 3 新增的、本轮
只是往里加一段，故改成引 Ruling 46/57 的口径。注释不进 AST，逐顶层单元的自证看不见它，故在
自证脚本里单列一节把注释全量清点出来。③ 去掉一个没有占位符的 f 前缀。

变异验收 8 相位全 PASS，两份分别做，每次变异都在**剥 docstring 后的 ast.dump** 上确认「真的改了
代码」，并额外跑一组「只改 docstring」的对照证明该口径不恒真。① parts[:-1] -> parts 只变异
test_layering.py：layering 红（10 条 offender，含 4 格值错 + 4 格「是模块路径」+ 2 格与
resolve_name 不一致）、purity 保持绿。② 同一变异只变异 test_domain_purity.py：反向。
③ M0 对照：不变异时 2 passed。④ M1 对照：等价改写成 parts = …; return tuple(list(parts)
[: len(parts) - 1])，AST 变了但两条仍 2 passed（尺子不恒红）。⑤ 额外：变异下只跑旧的 4 条守卫
= 4 passed, 2 deselected、rc 0，即「守卫假绿」是真的。⑥ 额外：把基线 be0f1af 的两份文件
（git show 取到内存、LF 换成 CRLF 后 sha256[:16] 与本轮开工前的工作树逐字相符）加上同一变异
落盘后跑全量 = 481 passed / rc 0，即断言消息里那句「在本段断言加上之前，这么改一次全量测试都
照样通过」有实测依据。每次变异后按字节还原并核 sha256，全程未用 git checkout / git restore。

硬规矩 #32 本轮形态：逐顶层单元比基线 be0f1af（HEAD 73313f7 只多一个 Document/ 的文档 commit，
两个守卫文件自 be0f1af 起未变，故代码基线取 be0f1af），带四组对照。结果：两个文件有差异的顶层
单元都**只有** test_absolute_folding_matches_resolve_name 一个；_package_of / _absolute /
_imported_modules / _is_allowed / _is_forbidden / 既有 4 个 test_* / <module-level> 全部「未动」
（模块 docstring 与 _absolute docstring 的改动被剥掉了，故另立一节把 docstring 全量清点、
再另立一节把注释全量清点）；既有 5 条守卫 assert（purity 1+1+1、layering 2）逐字未动；
git diff --name-only HEAD 只含这两个守卫文件，backend/app/** 命中 0 个（--numstat：purity
+70/-8、layering +61/-6）。两份 _package_of 与两份 _absolute 剥 docstring 后仍逐字相同、
且与基线逐字相同（硬规矩 #51）。import importlib.util 维持在函数体内（Ruling 57）。

收工闸门 python -m pytest -q = 481 passed（passed 数与基线逐字相同）；-W error = 481 passed /
0 error；--cov=app/domain --cov-branch --cov-report=term-missing = 399 stmts / Miss 0 /
114 branch / BrPart 0 / 100%，同一次跑 480 passed, 1 skipped（那 1 条 skip 是
test_backfill.py:182 的 trace-hook 自觉跳过，既有行为）。禁区：backend/pe.db 不存在、
backend/data/seed/ 0 文件、national_standard_2014.csv 21412 B / sha256[:16] =
D2C8E539E2FA0029 / CRLF = 0、backend/data/ 与 Document/ 未动、两个守卫文件行尾纯 CRLF
（purity 634、layering 396，裸 LF 0）、无临时目录残留（取证脚本 7 个收在 gitignore 的
.superpowers/sdd/…/fr4_probes/）。不 push。
"""

pathlib.Path(MSG).write_bytes(BODY.replace("\r\n", "\n").encode("utf-8"))
b = pathlib.Path(MSG).read_bytes()
assert not b.startswith(b"\xef\xbb\xbf") and b.count(b"\r") == 0
print("commit message: %d 字节 / %d 行 / 首行 %d 字符"
      % (len(b), b.count(b"\n") + 1, len(BODY.splitlines()[0])))

for rel in FILES:
    r = subprocess.run(["git", "add", "--", rel], cwd=str(REPO), capture_output=True)
    assert r.returncode == 0, r.stderr.decode()
r = subprocess.run(["git", "-c", "core.quotepath=false", "status", "--short"], cwd=str(REPO),
                   capture_output=True)
print("git status --short（add 之后）:")
for l in r.stdout.decode("utf-8").splitlines():
    print("   ", l)

r = subprocess.run(["git", "commit", "-F", MSG], cwd=str(REPO), capture_output=True)
print(r.stdout.decode("utf-8", "replace"))
print(r.stderr.decode("utf-8", "replace"))
assert r.returncode == 0, r.returncode
os.unlink(MSG)

r = subprocess.run(["git", "log", "--oneline", "-3"], cwd=str(REPO), capture_output=True)
print(r.stdout.decode("utf-8", "replace"))
r = subprocess.run(["git", "-c", "core.quotepath=false", "status", "--short"], cwd=str(REPO),
                   capture_output=True)
print("收工 git status --short = %r" % r.stdout.decode("utf-8"))
r = subprocess.run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], cwd=str(REPO), capture_output=True)
print("本 commit 触及的文件 =", r.stdout.decode("utf-8").split())
r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(REPO), capture_output=True)
print("分支 =", r.stdout.decode().strip())
r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO), capture_output=True)
print("HEAD =", r.stdout.decode().strip())

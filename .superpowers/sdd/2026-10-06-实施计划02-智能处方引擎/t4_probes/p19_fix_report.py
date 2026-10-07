"""对 task-4-report.md 做三处替换（SearchReplace 报了成功但磁盘未写，sha256 逐字未变，
这是「工具/磁盘分歧」家族的第 61-63 次、也是「连 diff 一起伪造」那个形态的第 3 次）。
按 Ruling 135 的处置：python 字节级重写 + 双向串查。
"""
import hashlib
import pathlib

p = pathlib.Path(r".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-4-report.md")
b0 = p.read_bytes()
print("before: %d B  sha16 %s  CRLF %d" % (len(b0), hashlib.sha256(b0).hexdigest()[:16].upper(),
                                           b0.count(b"\r\n")))
assert b0.count(b"\r\n") == 0, "报告是纯 LF，替换锚点按 \\n 写"
t = b0.decode("utf-8")

REPL = []

# ---------------------------------------------------------------- 1. §9.1 的三行表格
REPL.append((
    "| ① `# Task 2 会新建 app/domain/prescription/ 子包（今天不存在）` | ✓ 命中（`pkg_cases` 的注释） | ✓ 命中（同一处） | **2** |\n"
    "| ② `但 ``app/domain/prescription/`` 这一层子包已经建出，Task 3 的 ``match.py`` 一写` | ✓ 命中（`test_domain_imports_stay_within_the_allow_list` 的 docstring） | **0 命中** | **1** |\n"
    "| ③ `# Task 2 的形状（fix round 5 新加，Plan02 Ruling 67）：app/domain/prescription/match.py` | ✓ 命中（`cases` 的注释） | ✓ 命中（同一处） | **2** |\n",
    "| ① `pkg_cases` 里那条「子包今天还不存在、将来某个 Task 才会建它」的注释 | ✓ 命中 | ✓ 命中（同一处） | **2** |\n"
    "| ② allow-list 那条守卫 docstring 里「子包已建出、某个 Task 一写 `from ..indicators import X` 它就开始出现」那半句，而它把 `match.py` 归给了**错的那个 Task** | ✓ 命中 | **0 命中** | **1** |\n"
    "| ③ `cases` 矩阵里那一格绿档的注释，把「谁加的、为哪个 Task 埋的」记错了**两处** | ✓ 命中 | ✓ 命中（同一处） | **2** |\n"
    "\n"
    "（三处的可 grep 原文由派单与简报 P4-A6 给出；本报告按硬规矩 #74 **不逐字复述**被撤销的\n"
    "写法、只描述——否则将来 grep 那些串会同时命中简报、计划与本报告，分不清错误是否还在。）\n",
))

# ---------------------------------------------------------------- 2. CE-2 的标题
REPL.append((
    "**CE-2（成立，Important）— 简报 P4-A6 / 派单说「全仓相对导入今天 16 条，`match.py` 若写相对导入会变 17」。实测变 18。**\n",
    "**CE-2（成立，Important）— 简报 P4-A6 与派单 §2 都预测「`match.py` 写相对导入之后，全仓相对导入的条数会变成 17」。实测是 **18**——两处都少算了一条。**\n",
))

# ---------------------------------------------------------------- 3. CE-2 的正文
REPL.append((
    "计数预测互相矛盾。派单 §2 的「控制者的补充裁定」也重复了这个数（「若你沿用绝对导入，\n"
    "全仓相对导入计数不变（仍 16）；若 `match.py` 写 `from ..indicators import X` 这类\n"
    "`level == 2`，计数变 17、level 分布变 `{1:16, 2:1}`」）——两个分支都少算了 `__init__.py`\n"
    "那一条：沿用绝对导入是 **17**（`match.py` 仍需从某处拿 `Template`；若它也写绝对串则\n"
    "`__init__.py` 那一句仍使总数变 17），写 `level == 2` 是 **18** 且分布 `{1:17, 2:1}`。\n",
    "计数预测互相矛盾。派单 §2 的「控制者的补充裁定」给了两个分支各自的预测值，\n"
    "**两个分支都少算了 `__init__.py` 那一条**（按硬规矩 #74，这里只描述、不逐字复述）：\n"
    "\n"
    "* 「沿用绝对导入则全仓计数不变」——不成立。`match.py` 无论如何要从某处拿 `Template`\n"
    "  （我选的是同包相对串），而**即使它选绝对串**，`prescription/__init__.py` 新增的那一句\n"
    "  `from .match import (…)` 自己就是一条 `level == 1` 的相对导入，故那个分支的实测值是\n"
    "  **17**、不是 16。\n"
    "* 「写 `level == 2` 则计数变成 17、level 分布变成一条 `level 2` 加原来的 `level 1`」——\n"
    "  那个分支的实测值应是 **18**、分布 `{1: 17, 2: 1}`。\n",
))

# ---------------------------------------------------------------- 4. CE-3 里被撤销的那组数
REPL.append((
    "三处都写着同一组数：简报 Task 4 全节（「若顺序反过来，分类会变成\n"
    "`{NO_LAYER:8, NO_BUCKET:4, UNREACHABLE:5, MATCHED:15}`」）、账本 P4-A3 节、\n"
    "以及派单 §2 与 §3 的变异 ④ 判据。\n",
    "三处都写着同一组数（简报 Task 4 全节、账本 P4-A3 节、派单 §2 与 §3 的变异 ④ 判据）：\n"
    "「顺序反过来之后 `NO_BUCKET` 是 **4**、`UNREACHABLE` 是 **5**」（按硬规矩 #74 只描述\n"
    "那两个数、不逐字复述整句）。**实测恰好相反：`NO_BUCKET` 是 5、`UNREACHABLE` 是 4。**\n",
))

for old, new in REPL:
    n = t.count(old)
    assert n == 1, "锚点命中 %d 次（应为 1）：%r" % (n, old[:60])
    t = t.replace(old, new)

b1 = t.encode("utf-8")
p.write_bytes(b1)

b2 = p.read_bytes()
t2 = b2.decode("utf-8")
print("after : %d B  sha16 %s  CRLF %d  lines %d" % (
    len(b2), hashlib.sha256(b2).hexdigest()[:16].upper(), b2.count(b"\r\n"), len(b2.splitlines())))
assert b2 != b0, "写盘没有生效"

# 双向串查：新串命中 >= 1 且旧串残留 == 0
MUST_HAVE = [
    "| ① `pkg_cases` 里那条「子包今天还不存在",
    "本报告按硬规矩 #74 **不逐字复述**被撤销的",
    "**CE-2（成立，Important）— 简报 P4-A6 与派单 §2 都预测",
    "**两个分支都少算了 `__init__.py` 那一条**（按硬规矩 #74，这里只描述、不逐字复述）",
    "**实测恰好相反：`NO_BUCKET` 是 5、`UNREACHABLE` 是 4。**",
]
MUST_NOT = [
    "若写相对导入会变 17",
    "计数变 17、level 分布变",
    "Task 2 的形状（fix round 5 新加",
    "Task 2 会新建 app/domain/prescription/ 子包（今天不存在）",
    "这一层子包已经建出，Task 3 的",
    "NO_BUCKET:4, UNREACHABLE:5",
    "MatchResult",
]
ok = True
for s in MUST_HAVE:
    n = t2.count(s)
    print(("HAVE  " if n >= 1 else "MISS!!"), n, repr(s[:58]))
    ok &= n >= 1
for s in MUST_NOT:
    n = t2.count(s)
    print(("CLEAN " if n == 0 else "RESID!!"), n, repr(s[:58]))
    ok &= n == 0
# 任何「0 命中」的结论，先用一个已知存在的串验证查询本身有效
print("control probe (must be >=1):", t2.count("硬规矩"))
ok &= t2.count("硬规矩") >= 1
print("OK" if ok else "FAILED")

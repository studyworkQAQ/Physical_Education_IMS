# -*- coding: utf-8 -*-
"""pe_fr3_report.py — 把 fix round 3 的报告**追加**到 task-1-report.md（读回全文再追加再落盘）。

用法: python pe_fr3_report.py <仓库根>
"""
import hashlib
import pathlib
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
REPORT = REPO / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md"

SECTION = r"""

## fix round 3

**派单**：Ruling 42（一处印在源码里的机制错话，一行改动）+ Ruling 46（给上一轮修掉的两个 bug
加回归测试，**已授权改变测试计数**）。禁区：只许动 `test_domain_purity.py` 与 `test_layering.py`
两个文件，生产代码一个字节都不许动，不得改现有 5 条 `assert` 的语义。
**基线** `1fa9941`（479 passed / 0 failed，`app/domain/` 分支覆盖 100%）。开工时我亲验
`git status --short` = **0 行**、`git rev-parse --short HEAD` = `1fa9941`、分支
`feature/plan-02-prescription-engine`（硬规矩 #48）。
**产出** 一个 commit **`be0f1af`**（不 push、不动 `main`），**479 → 481 passed**：本轮新增
2 条测试函数（两个守卫文件各一条，硬规矩 #51），无其他计数变化。

⚠️ **这个 commit 是 `--amend` 过一次的第二版**。第一版 `e647459` 里我在新测试的 docstring 写了
「（变异实测，见任务报告 fix round 3）」——**指针指向不入库的文件**（`.gitignore:10` 的
`.superpowers/`，`git ls-files .superpowers` 计数 0），正是账本 Ruling 27 / 评审 M2 要消灭的
形态，而我在 fr2 里刚读过那条裁定。自查后改成「写全复现命令 + 贴实跑的断言原文」，
`git commit --amend --no-edit` 进同一个 commit（保持派单要求的「一个 commit」）。见 fr3.8-④。

行号一律 **shell 口径**（python 读字节数行，不用 Read 工具——本轮它在这个报告文件上又一次报
「文件只有 1031 行」，实测 **2152** 行；Grep 与 python 口径一致）。改前引用绑定 `1fa9941`、
改后引用绑定 `be0f1af`。

| 文件 | 改前 | 改后 | 字节 |
|---|---|---|---|
| `tests/architecture/test_domain_purity.py` | 458 | **572** | 29846 → 37435 |
| `tests/architecture/test_layering.py` | 228 | **341** | 14461 → 22144 |

`git diff 1fa9941..HEAD --numstat` = **2 文件 / +228 / −1**（purity `115 1`、layering `113 0`）。
`git diff --name-only 1fa9941` 只含这两个守卫文件，`backend/app/**` 命中 **0** 个。

### fr3.0 闸门（全部亲跑，命令逐字给出）

| 闸门 | 命令 | 结果 |
|---|---|---|
| 全量测试 | `cd backend; python -m pytest -q` | **481 passed in 53.55s**，0 failed（基线 479 + 本轮 2 条） |
| 全量 `-W error` | `cd backend; python -m pytest -q -W error` | **481 passed in 53.06s**，0 error |
| domain 分支覆盖 | `cd backend; python -m pytest -q --cov=app/domain --cov-branch --cov-report=term-missing` | `TOTAL **399** stmts / Miss **0** / **114** branch / BrPart **0** / **100%**`；同一次跑 **480 passed, 1 skipped in 112.37s**（那 1 条 skip 是 `test_backfill.py` 在 `--cov` 下的既有自我跳过，与派单预测逐字相同） |
| 架构守卫单跑 | `cd backend; python -m pytest tests/architecture -q -W error` | **6 passed in 0.07s**（基线 4 → +2），0 error |
| 硬规矩 #32（本轮形态：逐顶层单元 + 三组对照） | `python fr3_probes/pe_fr3_astdiff.py .` | **PASS**，见 fr3.4 |
| 硬规矩 #51（两份 `_absolute` 仍逐字相同） | `python fr2_probes/pe_fr2_rule51.py .` | **PASS**，见 fr3.5 |
| 变异验收（12 相位） | `python fr3_probes/pe_fr3_mutation.py .` | **失败项 0 / 12**，见 fr3.3 |
| 判据复核（对拍矩阵 13 格） | `python fr3_probes/pe_fr3_matrix.py .` | **MISMATCH 0 / 13**，见 fr3.2 |
| Ruling 42 的机制实跑 | `python fr3_probes/pe_fr3_r42.py .` | 见 fr3.1 |
| Ruling 46 那句「479 条全绿」 | `python fr3_probes/pe_fr3_blind.py .` | **在基线上复现：479 passed、退出码 0**，见 fr3.6 |
| 变异后的断言原文 | `python fr3_probes/pe_fr3_msgs.py .` | 见 fr3.3 |

禁区与行尾（python 直接读字节，不走 PowerShell 管道）：

```
backend/pe.db exists: False
backend/data/seed/ 条目数: 0
csv bytes=21412 sha256[:16]=D2C8E539E2FA0029 CRLF=0
backend/tests/architecture/test_domain_purity.py   bytes=37435 CRLF=572 裸LF=0 BOM=False 乱码=False
backend/tests/architecture/test_layering.py        bytes=22144 CRLF=341 裸LF=0 BOM=False 乱码=False
```

收工时 `git status --short` → **0 行**，`git log --oneline -2` = `be0f1af` 一个 commit 在
`1fa9941` 之上。本轮**没有造合成树**（新测试直接调 `_absolute`，不需要临时目录），
`$env:TEMP` 下我的 `pe_fr3_msg_*` commit-message 临时文件已 `os.unlink`；上一轮留下的
20 个 `pe_fr2_*` 文件不是我造的，未动。取证脚本 11 个收在
`.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/fr3_probes/`（gitignore、不入库、可一键重跑）。

### fr3.1 Ruling 42 — `_is_allowed('app.domain')` 命中的是「相等」那一支 ✅

**改法**：`test_domain_purity.py` 基线 `:167` 那一行换成 5 行（改后 `:167-171`）。
`ast.get_docstring(_absolute)` 的 unified diff（`pe_fr3_astdiff.py` ② 段实跑）：

```
--- 基线
+++ 工作树
@@ -41,3 +41,7 @@
 ``app/domain/x.py`` 里的 ``from ....domain import tables``（``level == 4``、包深 2）
-会折成 ``app.domain``、**命中白名单前缀 ``app.domain.`` 变成真绿**，而 ``resolve_name``
+会折成 ``app.domain``，而 ``_is_allowed`` 的第一支正是 ``module == ALLOWED_PACKAGE``——
+**命中的是「相等」这一支，不是 ``startswith(ALLOWED_PACKAGE + ".")`` 那一支**（本机
+Python 3.11.1 实跑：``"app.domain" == ALLOWED_PACKAGE`` -> ``True``、
+``"app.domain".startswith(ALLOWED_PACKAGE + ".")`` -> ``False``；Plan02 Ruling 42），
+于是变成真绿；而 ``resolve_name``
 对同一输入抛 ``ImportError``（Plan02 Ruling 35）。
```

**结论（真绿）没改，只改机制**，与派单要求一致。写进 docstring 的两个值是我自己跑的
（`pe_fr3_r42.py`，硬规矩 #52；不是抄派单也不是抄 fr2.8 ①）：

```
ALLOWED_PACKAGE = 'app.domain'
_is_allowed('app.domain'              ) = True  | == ALLOWED_PACKAGE: True  | startswith('app.domain.'): False | in ALLOWED_MODULES: False
_is_allowed('app.domain.seed'         ) = True  | == ALLOWED_PACKAGE: False | startswith('app.domain.'): True  | in ALLOWED_MODULES: False
_is_allowed('app.domain.seed.generate') = True  | == ALLOWED_PACKAGE: False | startswith('app.domain.'): True  | in ALLOWED_MODULES: False
_is_allowed('app.db.seed'             ) = False | == ALLOWED_PACKAGE: False | startswith('app.domain.'): False | in ALLOWED_MODULES: False
_is_allowed('enum'                    ) = True  | == ALLOWED_PACKAGE: False | startswith('app.domain.'): False | in ALLOWED_MODULES: True
```

**没误伤另外两处**：派单点名 `:139` 与 `:246` 说的是 `app.domain.seed.generate`
（`startswith('app.domain.')` 实测 **True**，正确），要求不动。改完全仓 grep「白名单前缀」
只剩 **2 处**，正是它们（`:246` 因本轮插入而后移到 `:351`）：

```
backend/tests/architecture/test_domain_purity.py:139:    就会折成 ``app.domain.seed.generate``、命中白名单前缀 ``app.domain.`` → **守卫当场假绿**
backend/tests/architecture/test_domain_purity.py:351:        这个深度解析到的是 ``app.domain.seed.generate``、命中白名单前缀 ``app.domain.`` →
```

`layering` 侧 `_absolute` 的 docstring **逐字未动**（`pe_fr3_astdiff.py` ② 段实测
`docstring 相同 = True`）——它基线里就没有这句错话。

### fr3.2 Ruling 46 — 两份 `_absolute` 的两份回归测试 ✅

两个文件各新增一条 `test_absolute_folding_matches_resolve_name()`（**同名**，故意的：
`_absolute` 是两份重复代码，两条回归测试同名才 grep 得出来，硬规矩 #51）。
purity 侧插在 `_is_allowed` 与 `test_domain_imports_stay_within_the_allow_list` 之间（改后
`:193-291`），layering 侧插在 `_is_forbidden` 与 `test_production_layers_never_import_app_seed`
之间（改后 `:183-284`）。

**判据锚在 `resolve_name` 上、一个折算结果都不写死**（派单要求）：

```python
rel = "." * level + (module or name)
pkg = ".".join(package)
try:
    want = importlib.util.resolve_name(rel, pkg)
except ImportError:
    want = None
got = _absolute(module, level, package, name)
```

外加一列**期望颜色**（`RED`/`GREEN`）——那是判据（各文件自己的白名单/前缀语义），不是折算
结果，故不违反「不要抄表」。所有不一致一次性收进 `offenders` 再 `assert offenders == []`，
与本文件既有的 `assert offenders == []` 惯例一致（第一个红不会盖住后面的）。

**矩阵 11 格**（以 `(module, level, package, name)` 四元组为参数，Ruling 45）。写进仓库前我先
用 `pe_fr3_matrix.py` 把派单点名的 9 个形状 + 2 个自选边界档一起对拍过一遍，**13 格 MISMATCH 0**、
两份 `_absolute` 互相一致（下面是实跑输出，不是抄派单的期望值）：

| 形状 `(module, level, package, name)` | `resolve_name` | 两份 `_absolute` | purity 判定 | layering 判定 |
|---|---|---|---|---|
| `("app.seed.generate", 0, ("app","domain"), "")` | `'app.seed.generate'` | 同 | RED | RED |
| `("tables", 1, ("app","domain"), "")` | `'app.domain.tables'` | 同 | **GREEN** | GREEN |
| `("", 1, ("app","domain"), "tables")` | `'app.domain.tables'` | 同 | **GREEN** | GREEN |
| `("_shared", 1, ("app","db","models"), "")` | `'app.db.models._shared'` | 同 | RED | **GREEN** |
| `("", 1, ("app","db","models"), "_shared")` | `'app.db.models._shared'` | 同 | RED | **GREEN** |
| `("seed.generate", 2, ("app","pipeline"), "")` | `'app.seed.generate'` | 同 | RED | RED |
| `("", 2, ("app","pipeline"), "seed")` | `'app.seed'` | 同 | RED | RED |
| `("", 2, ("app","db"), "seed")` | `'app.seed'` | 同 | RED | RED |
| `("", 2, ("app","db","models"), "seed")` | `'app.db.seed'` | 同 | RED | **GREEN** |
| `("", 2, ("app","domain"), "seed")` | `'app.seed'` | 同 | RED | RED |
| `("seed", 5, ("app","db","models"), "generate")` | `ImportError` | `None` | RED | RED |
| `("domain", 4, ("app","domain"), "tables")` | `ImportError` | `None` | RED | RED |
| `("seed", 3, ("app","domain"), "generate")` | `ImportError` | `None` | RED | RED |

（第 2/3 行只有 purity 侧进了仓库矩阵、第 4/5 行只有 layering 侧进了仓库矩阵——各取自己包树里
真实会出现的那一档当绿档；越界档第 3 行 `("seed", 3, ("app","domain"), …)` 是
`level - 1 == len(package)`，由既有的 `if not anchor: return None` 兜住、**不是**由 Ruling 35
新加的那一行兜住，两侧都进了仓库矩阵，理由见 fr3.8-②。表里另外 2 格
`("", 1, ("app",), "seed")` → `'app.seed'` 与 `("seed", 3, ("app","db","models"), "generate")`
→ `'app.seed'` 是我为验证等价性多跑的，**没进仓库**。）

**⚠️ 两份的期望颜色列刻意不相同**：`("", 2, ("app","db","models"), "seed")` 折成 `app.db.seed`，
在 layering 的 `app.seed` 前缀下是 **GREEN**（Ruling 41 的「折算串错了不等于判定错了」），
在 purity 的白名单下是 **RED**（`_is_allowed('app.db.seed') = False`，上面实跑）。两个
docstring 里都写明了这一点，免得下一个人以为其中一份抄错。

**判据的可靠性论证**（为什么锚在 `resolve_name` 上就够）：Python 3.11.1
`Lib/importlib/util.py` 的 `resolve_name` 是

```python
def resolve_name(name, package):
    if not name.startswith('.'):
        return name                     # ← level == 0 走这一支，故派单给的公式对 level 0 也成立
    elif not package:
        raise ImportError(...)
    level = 0
    for character in name:
        if character != '.': break
        level += 1
    return _resolve_name(name[level:], package, level)
```

而 `_resolve_name` 抛 `ImportError` 的条件是 `len(package.rsplit('.', level - 1)) < level`；
`len(package.rsplit('.', level - 1)) == min(level, 包深)`，故该条件等价于 `包深 < level`，
即 `level - 1 >= 包深`。`_absolute` 用**两行**覆盖同一个集合：`level - 1 > len(package)`
（Ruling 35 新加）与 `level - 1 == len(package)`（既有的 `not anchor`）。**两者合起来与
`resolve_name` 精确等价**，13 格对拍 0 DIFF 是这个论证的实测面。

### fr3.3 变异验收（12 相位，两份分别做，硬规矩 #50 / #51 / #53）

`pe_fr3_mutation.py`，全部相位都先在 **AST 上确认变异真的改了代码**（`ast.dump` 前后不等），
每次变异后按**字节**还原并核 sha256，全程未用 `git checkout` / `git restore`。

| 相位 | 变异 | purity | layering |
|---|---|---|---|
| M0 | 不变异（**对照 GREEN**，#53） | GREEN ✅ | GREEN ✅ |
| M1 | `package[: len(package) - (level - 1)]` → `package[: len(package) - level + 1]`（**AST 变了、语义等价**，#53 的「尺子不是恒红」对照） | GREEN ✅ | GREEN ✅ |
| M2 = 派单 ① | 删掉 `if level - 1 > len(package): return None`（含注释共 3 行），只变异 purity | **RED** ✅ | GREEN ✅（未被变异） |
| M2 | 同上，只变异 layering | GREEN ✅（未被变异） | **RED** ✅ |
| M2 | 同上，两份都变异 | **RED** ✅ | **RED** ✅ |
| M3 = 派单 ② | `tail = module or name` → `tail = module`，只变异 purity | **RED** ✅ | GREEN ✅ |
| M3 | 同上，只变异 layering | GREEN ✅ | **RED** ✅ |
| M3 | 同上，两份都变异 | **RED** ✅ | **RED** ✅ |
| M4 = 额外 | `_imported_modules` 的逐个 `names` 展开改回「一个节点只 yield 第一条」，只变异 purity | **RED** ✅ | GREEN ✅ |
| M4 | 同上，只变异 layering | GREEN ✅ | **RED** ✅ |
| M4 | 同上，两份都变异 | **RED** ✅ | **RED** ✅ |
| M4-附 | 同 M4，但只跑**旧的 4 条**守卫（`-k not test_absolute_folding_…`） | `4 passed, 2 deselected`、退出码 0 → **旧守卫对这一档无感** | |

**失败项 0 / 12**。「只变异一份时另一份保持绿」这一列是硬规矩 #51 的正面证据：两条回归测试
各自看着自己那一份 `_absolute`，谁也替代不了谁。

**红的是哪条断言**（`pe_fr3_msgs.py` 实跑的 pytest 输出，硬规矩 #53 要求区分「真红」与
「harness 坏了导致的假红」——下面每一行都是断言消息本体，不是收集错误）：

```
M2 purity   E  _absolute('seed', 5, ('app', 'db', 'models'), 'generate') = 'app.db.seed'，而 resolve_name('.....seed', 'app.db.models') = None
            E  _absolute('domain', 4, ('app', 'domain'), 'tables') = 'app.domain'，而 resolve_name('....domain', 'app.domain') = None
            E  _absolute('domain', 4, ('app', 'domain'), 'tables') = 'app.domain' 判成 GREEN、期望 RED
M2 layering E  _absolute('seed', 5, ('app', 'db', 'models'), 'generate') = 'app.db.seed' 判成 GREEN、期望 RED   （+ 同上 3 行）
M3 purity   E  _absolute('', 1, ('app', 'domain'), 'tables') = 'app.domain'，而 resolve_name('.tables', 'app.domain') = 'app.domain.tables'
            E  _absolute('', 2, ('app', 'pipeline'), 'seed') = 'app'，而 resolve_name('..seed', 'app.pipeline') = 'app.seed'
            E  _absolute('', 2, ('app', 'db'), 'seed') = 'app'，而 resolve_name('..seed', 'app.db') = 'app.seed'
            E  _absolute('', 2, ('app', 'db', 'models'), 'seed') = 'app.db'，而 resolve_name('..seed', 'app.db.models') = 'app.db.seed'
            E  _absolute('', 2, ('app', 'domain'), 'seed') = 'app'，而 resolve_name('..seed', 'app.domain') = 'app.seed'      （共 5 格）
M3 layering E  _absolute('', 1, ('app', 'db', 'models'), '_shared') = 'app.db.models'，而 resolve_name('._shared', 'app.db.models') = 'app.db.models._shared'
            E  …（含 3 格「判成 GREEN、期望 RED」，共 8 行）
M4 两侧     E  AssertionError: 一名一条的展开失效: ['app.seed'] != ['app.seed', 'app.pipeline']
```

**三重还原取证**（脚本末尾实跑）：

```
purity    sha256[:16]=dffa51f460826436 与原始一致=True 37435 字节 CRLF=572 裸LF=0
layering  sha256[:16]=a5afd212bd485ef4 与原始一致=True 22144 字节 CRLF=341 裸LF=0
git status --short: （变异过程中 2 行 M；相位结束后逐次核 sha256 一致）
```

### fr3.4 硬规矩 #32 闸门（本轮形态：逐顶层单元 + 三组对照）

本轮**两个守卫文件都真改了代码**（新增函数），故「剥 docstring 后 `ast.dump` 比基线 SAME」
这条判据**按字面不可满足、也不该满足**。自证改成派单要求的形态：`pe_fr3_astdiff.py`
逐顶层单元比（基线用 `git show 1fa9941:<path>` 取到内存，不落盘、不 checkout），并带三组对照。

```
=== ⓪ 改动面 ===
   backend/tests/architecture/test_domain_purity.py
   backend/tests/architecture/test_layering.py
   合计 2 个文件；生产代码（backend/app/**）命中 = 0

=== ① 逐顶层单元（剥 docstring 后）===
test_domain_purity.py：_domain_files / _assert_not_empty / _imported_modules / _package_of /
   _absolute / _is_allowed / test_domain_imports_stay_within_the_allow_list / _dotted /
   _hit_forbidden_call / test_domain_has_no_clock_or_file_access /
   test_domain_has_no_filesystem_access / <module-level>  → **全部「未动」**
   NEW test_absolute_folding_matches_resolve_name
   → 有差异的顶层单元 = ['test_absolute_folding_matches_resolve_name']
test_layering.py：_py_files / _package_of / _absolute / _imported_modules / _is_forbidden /
   test_production_layers_never_import_app_seed / <module-level>  → **全部「未动」**
   NEW test_absolute_folding_matches_resolve_name
   → 有差异的顶层单元 = ['test_absolute_folding_matches_resolve_name']

=== ③ 既有 5 条 assert 逐字对比 ===
   test_domain_imports_stay_within_the_allow_list    assert 1→1 逐字相同=True
   test_domain_has_no_clock_or_file_access           assert 1→1 逐字相同=True
   test_domain_has_no_filesystem_access              assert 1→1 逐字相同=True
   test_production_layers_never_import_app_seed      assert 2→2 逐字相同=True
   既有 assert 合计 5 条，全部逐字未动

=== 对照组（硬规矩 #53）===
   test_domain_purity.py  ① 注入语义变异后报 DIFF 的单元=['_absolute']  ② 自比报 DIFF=[]
                          ③ 只改 docstring：不剥时报 DIFF=True、剥掉后报 DIFF=[]
   test_layering.py       ① 同上  ② 同上  ③ 同上
```

即：**改动面恰好是「新增的两条测试函数」+「purity 侧 `_absolute` docstring 的那一处」**
（② 段的 docstring diff 见 fr3.1），`<module-level>` 逐字未动——这就是我把
`import importlib.util` 写在**函数体内**的原因（fr3.8-③）。
对照 ③ 用的是 `_absolute` docstring 首句「折算成**绝对模块串**」→「**绝对的模块串**」：
不剥 docstring 时尺子报 DIFF、剥掉后报 SAME，证明它真的在剥。

### fr3.5 硬规矩 #51 闸门（两份 `_absolute` 仍逐字相同）

复跑上一轮的 `fr2_probes/pe_fr2_rule51.py`（本轮没改它）：

```
=== ① 全仓定义份数 ===  合计 4 处定义（_package_of 2 份 + _absolute 2 份）
=== ② 剥 docstring 后的函数体 AST ===
    _package_of    份数=2  签名=['py']                              函数体 AST 逐字相同=True
    _absolute      份数=2  签名=['module', 'level', 'package', 'name']  函数体 AST 逐字相同=True
=== ③ 7 项关键点在两份里都在 ===  两份全 OK
=== ④ 两条旧的假举例串 ===  命中 无（已删）
硬规矩 #51 闸门: PASS
```

派单要求「本轮不许打破 `identical(excl docstring) = True`」——**未打破**。
本轮两条新测试函数**也各有一份**（同名、同结构，只有绿档取样与颜色判据按各自守卫的语义
不同），故 #51 的适用面从「两份实现」扩到了「两份实现 + 两份回归测试」。

### fr3.6 Ruling 46 那句「479 条全绿」我自己在基线上复核了

新测试的 docstring 里印了「谁删掉 `if level - 1 > len(package): return None`，479 条全绿」
（引自 Ruling 46）。按硬规矩 #52，印进在库文件的数字我得自己能指到一条命令，故亲跑
（`pe_fr3_blind.py`）：把 `git show 1fa9941:<path>` 取到的**基线**两份守卫都删掉那一行、
写进工作树，跑全量：

```
=== 把基线 1fa9941 的两份 _absolute 删掉越界守卫，跑全量测试 ===
  purity    已写入基线-变异版 29664 字节（基线 blob 29388 字节）
  layering  已写入基线-变异版 14279 字节（基线 blob 14233 字节）
  退出码=0
  479 passed in 54.05s
  => Ruling 46 那句「479 条全绿」在基线上复现 = True
```

**成立**：那个口子是真的，本轮新增的两条测试正是为了堵住它（fr3.3 的 M2 三个相位）。

⚠️ 顺带一个坑，记下以免下一个人误判（**这是我自己踩的**）：`git show HEAD:<path>` 给出的是
**blob 里的 LF 版本**（`core.autocrlf=true`，实测 `git config core.autocrlf` = `true`），
而工作树是 CRLF 版本。我第一版脚本直接拿 blob 字节与工作树比，断言当场炸：
purity blob `36103 B` vs 工作树 `36666 B`，差 `563` **恰等于 CRLF 行数**。修法是把 blob 的
`\n` → `\r\n` 再比，并在脚本里 assert「差值 == CRLF 行数」。**这与硬规矩 #46 是同一族**
（`git checkout` / `git show` 会按 `autocrlf` 给不同字节），只是这次它出现在**读**的一侧、
不是写的一侧。

还原后取证：

```
purity    sha256[:16]=892119ff89ba63ff 与 HEAD 一致=True 36666 字节 CRLF=563 裸LF=0   （amend 前的第一版）
layering  sha256[:16]=60ba5d6e3f8115bd 与 HEAD 一致=True 21355 字节 CRLF=332 裸LF=0
git status --short: 0 行 []
HEAD = e647459 …
```

（这次探针跑在 amend 之前，故 sha 是第一版的；amend 后的最终 sha 见 fr3.3 末尾与 fr3.0。）

### fr3.7 我发现的派单错误（2 条成立 + 1 条歧义不计入 + 1 条我自己的预期错了）

按派单 §4.7 逐条给实测证据。**没有一条导致判据不可满足**，两件事我全部按派单做了。

**① 「`task-1-brief.md` — Global Constraints **9 条**」→ 实测 **10 条**。（成立，计一条）**

python 数 `## Global Constraints` 与 `## Review Focus` 之间的 `- ` 顶层 bullet：
`task-1-brief.md` = **10**，`Document/2026-10-06-实施计划02-智能处方引擎.md` 同一节也 = **10**
（10 条依次是：domain 无 I/O、domain 分支覆盖 100%、单一所有者、断言两侧不得同源、
散文必须带口径、行号取 shell 口径、PowerShell、落盘唯一权威是 shell、禁区、`app/seed/` 冻结）。
影响：无，我 10 条全读了。
**附带发现（不在派单里、也不在我可改的范围里）**：计划文档 `:13` 自己写「其中对本计划最要命的
**六条**见 Global Constraints」，与该节实有的 10 条不符。那是基线 `e26347f` 就有的、
在禁区 `Document/` 里，本轮**未动**，只记下转给控制者。

**② 「矩阵至少覆盖这 **7 类**」→ 派单自己枚举的是 **5 个 bullet / 9 个具体形状**。（成立，计一条）**

派单那 5 个 bullet 展开是：`level == 0`（1 个形状）+ `level == 1`（1）+
`from ..seed import generate` @ `app/pipeline`（1）+ `module` 为空（**4**）+ 越界（**2**）
= **9 个形状、5 组**。`7` 与 5、9 都不符；最接近的读法是「前四个 bullet 的形状数
1+1+1+4 = 7」，即**漏数了第五个 bullet 的 2 个越界形状**——而那 2 个恰恰是 Ruling 35 的主角、
也是变异 ① 唯一的抓手。账本 Ruling 46（`progress.md:502`）列的也是同样 5 组 / 9 个形状。
影响：因为是「**至少**覆盖」，判据仍可满足。我覆盖了全部 9 个 + 2 个自选档 = **11 格**
（fr3.2 的表是 13 格，其中 2 格只用于验证等价性、没进仓库）。

**③（歧义，按 Ruling 45 的口径不计入控制者错误）**
「`("", 2, ("app","db","models"), "seed")` → `app.db.seed`（**判定仍绿**，折算串才是重点）」
——「仍绿」只在 **layering** 侧成立。同一折算串在 **purity** 侧实测
`_is_allowed('app.db.seed') = False` → **RED**（fr3.1 的实跑表第 4 行）。派单那句话的语境是
Ruling 41（讲的是 layering 守卫），**不是事实错误**，只是没标主语；而它落到「两份文件各加
一条」的要求上时，两份的期望颜色列**必须不同**。我在两个 docstring 里都写明了理由，
以免下一个人以为其中一份抄错。

**④（我自己的预期错了，派单是对的——记下以免下一个人重复怀疑）**
开工前我判断「派单给的公式 `resolve_name("." * level + (module or name), …)` 对 `level == 0`
会抛异常（名字不以 `.` 开头），故那条判据对 `level == 0` 档按字面不可满足」，准备报成一条
派单错误。实测**不成立**：Python 3.11.1 `Lib/importlib/util.py` 的 `resolve_name` 第一行就是
`if not name.startswith('.'): return name`，故
`resolve_name("app.seed.generate", "app.domain")` = `'app.seed.generate'`，与 `_absolute` 逐字
相同（fr3.2 表第 1 行）。**派单的公式对 `level == 0` 同样成立、不需要特例。**
按「把不成立的指控也一并认下来是同一种失职」的口径，这条**不计入控制者错误**，
计入我自己的判断失误。

其余我逐条核过、**成立**的派单陈述（列出来表示核过，不是凑数）：分支名与基线 HEAD ✓、
`core.autocrlf=true` ✓、`progress.md` 448+ 行（实测 529）✓、#48 在 `:172` / #49 `:265` /
#50 `:290` / #51 `:409` / #52 `:411` / #53 `:509` ✓、`test_domain_purity.py:167` 原文逐字命中 ✓、
`_is_allowed` 的实现串逐字命中 ✓、「全仓只有 `:167` 一处错」✓、`fr2_probes/` 11 个脚本 ✓、
基线 479 passed ✓、基线 domain `399/0/114/0/100%` ✓、`--cov` 下 `1 skipped` 且本轮应变
`480 passed, 1 skipped` ✓、既有 5 条 assert（purity 3 + layering 2）✓、上一轮
`identical(excl docstring) = True` ✓。

### fr3.8 超出派单的改动（主动披露，4 处，全部在两个守卫文件内）

**① 额外钉住 Ruling 36 的「另一半」：`_imported_modules` 的逐个 `names` 展开。**
派单的变异验收只点名 `_absolute` 的两个变异，但 Ruling 46 的原话是「本轮修掉的**两个 bug**」，
而 bug 2（忽略 `node.names`）的修法有**三部分**（fr2.2）：`_absolute` 加 `name` 入参、
`tail = module or name`、`_imported_modules` 在 `module` 为空档**逐个 `names` yield**。
只测 `_absolute` 会把第三部分继续留在没人看的状态。故两个新测试的末尾各加一段：
`ast.parse("from .. import seed, pipeline")` → 必须折算出两条。变异 M4 实测（fr3.3）：
把逐个 yield 改回「只 yield 第一条」，**两条新测试都红**，而同一次跑里**旧的 4 条守卫
`4 passed` 无感**——这是 Ruling 46 那个口子的第三个实例，本轮一并堵上。
不造目录树、不重定向全局，只用 `ast.parse` 一个字符串，成本 6 行。

**② 矩阵比派单点名的多 2 格。** 一格是 `level == 1` 的 `name` 形式
（`("", 1, <包>, "tables"/"_shared")`）——派单只要求「`level == 1` 的包内合法导入」一格，
但 `module` 形式与 `name` 形式在 `_absolute` 里走的是**不同的分支**（`tail = module or name`
的两侧），只放一格就测不到 `or name` 这一侧在 `level == 1` 下的行为（变异 M3 的红里
就有这一格：`_absolute('', 1, ('app','domain'), 'tables') = 'app.domain'`）。
另一格是 `("seed", 3, ("app","domain"), "generate")`，即 `level - 1 == len(package)`：
它由**既有的** `if not anchor: return None` 兜住、不是由 Ruling 35 新加的那一行兜住。
放它的目的是把两行守卫的管辖范围分开——删掉新行时这一格**不变**（仍 `None`），
故它证明 `not anchor` 那一行还在干活、没有被新行的存在掩盖掉。

**③ `import importlib.util` 写在函数体内、不写在模块顶部。**
派单 §3 要求自证「除新增的两条测试函数与 `:167` 那一处 docstring 外，其余部分与基线逐字
相同」；模块级 import 会改动 `<module-level>` 这个顶层单元，故就地 import。两处各写了一行
注释交代理由。**代价**：不如顶部 import 惯例。若控制者认为该按惯例放顶部，那 §3 的自证
口径要跟着放宽成「`<module-level>` 只多一条 import」。

**④ docstring 里不留「见任务报告」这类指向不入库文件的指针**（amend 的那一处，见开头 ⚠️）。
改成写全复现命令 `python -m pytest tests/architecture -q` + 贴实跑的断言原文，
符合账本 Ruling 27 的处置口径（「写全命令 + 引账本 Ruling 编号，或标『历史实测，不被守卫』」）。
账本 Ruling 编号（`Plan02 Ruling 35/36/41/45/46/51`）仍然引——那是这两个文件既有的惯例。

### fr3.9 关切清单（3 条）

**C-fr3-1【中】`_package_of` 仍然没有回归测试，而它是两条守卫共同的假绿入口** — 自己重新推导

两个新测试的 `package` 入参是**手写的**，故 `_package_of` 不在守卫范围内。这一点我已按
硬规矩 #39 写进两个 docstring 的「本测试守不住什么」段。风险不是假想的：Ruling 37 说得很
清楚——谁按那个假举例去「对齐」代码、让 `_package_of` 返回模块名而不是包名，
`app/db/models/x.py` 里的 `from ...seed import …` 就会折成 `app.db.seed`、不再以 `app.seed`
开头，**两条架构守卫一起假绿**，而今天只有 docstring 里两行 `resolve_name` 实跑举例在交代。
本轮派单只授权给 `_absolute` 的两个 bug 加测试，我没扩到 `_package_of`（那会再动 passed 数）。
**最小修法（成本极低，不需要文件存在）**：`_package_of` 是纯路径算术，
`_package_of(BACKEND / "app" / "domain" / "x.py") == ("app", "domain")` 与
`_package_of(BACKEND / "app" / "db" / "models" / "__init__.py") == ("app", "db", "models")`
两行就够，且可以**塞进现有那条新测试里、不增加 passed 数**。**留给控制者裁。**

**C-fr3-2【低】`test_domain_purity.py` 的模块 docstring 说「三条守卫」，而文件里现在有 4 个
`test_*` 函数** — 自己发现，未改

那句话本身不假（新增的那条是**辅助函数的单元测试**，不是第四条守卫），但按「数 `test_*`
函数」的方式点人头的人会以为漏改了一处。改它要动**模块 docstring**，超出本轮「除新增函数与
`:167` 外逐字相同」的钉死范围，故未动。**建议**：若 Plan 02 后续还要往这两个文件里加
单元测试，就把模块 docstring 的那句改成「三条守卫 + N 条辅助函数单元测试」。

**C-fr3-3【低 → 建议 Plan 02 Task 2 之后评估】11 格矩阵是手写的，形状不会自动跟进** — 自己重新推导

判据锚在 `resolve_name` 上，所以矩阵**不会过期成假绿**（加一行就是加一格覆盖）；
但**没人会被提醒去加**——Task 2 建了 `app/domain/prescription/` 子包之后，包深 3 的
`from ..indicators import X` 是新增的真实形状，而矩阵里包深 3 的绿档只有 layering 侧那一格。
真要机械化，做法是「扫真仓所有 `ImportFrom` 节点、逐个与 `resolve_name` 对拍」：那是一条
**更强**的守卫（自动覆盖以后出现的每一个形状），而且它会顺带把 `_package_of` 拉进判据
（于是 C-fr3-1 一并解决）。**本轮不做**的理由：它会改变「不扫真仓」这条边界、且需要
预授权改 passed 数；Task 2 落地后形状才稳定，那时做收益更高。

### fr3.10 本轮**没做**的事

- 没动任何生产代码：`git diff --name-only 1fa9941` 只含两个守卫文件，`backend/app/**` 命中 0。
- 没动 `backend/tests/` 下的其他文件、没动 `backend/data/`、没动 `Document/`
  （包括 fr3.7-① 附带发现的「六条 vs 10 条」不一致，它在禁区里）。
- 没改既有 5 条 `assert` 的语义（fr3.4 ③ 段逐字比过：1+1+1+2 = 5 条，全部 `逐字相同=True`）。
- 没动 `:139` 与 `:351`（原 `:246`）那两处「命中白名单前缀 `app.domain.`」——它们说的是
  `app.domain.seed.generate`，`startswith` 实测为 True，是正确的。
- 没动 `layering` 侧 `_absolute` 的 docstring（它基线里没有 Ruling 42 那句错话，实测逐字未动）。
- 没把 `_package_of` / `_absolute` 抽成公共模块（Ruling 33 仍有效；fr2.10 的 C-fr2-1 也仍有效
  ——本轮又付了一次「改两遍 + 核两份是否仍相同」的代价，还多付一次「两条回归测试也要各写一份」）。
- 没给 `FORBIDDEN_IO` 补 `__import__(`（Ruling 47 已判延后 Minor）。
- 没造合成树、没重定向任何守卫模块的全局（本轮的新测试直接调 `_absolute`，不需要）；
  没跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`（禁区）。
- 没 `git push`；`git checkout` / `git restore` / `git switch` **一次都没用**
  （基线内容全部用 `git show` 取到内存，还原全部用 python `write_bytes`）。
- 没动 `fr2_probes/` 里的 11 个脚本（只**读**着复跑了 `pe_fr2_rule51.py`）。
"""


def main():
    raw = REPORT.read_bytes()
    text = raw.decode("utf-8")
    before_lines = text.split("\n")
    before_h2 = [l for l in before_lines if l.startswith("## ")]
    print("改前：%d 字节，%d 行（LF 口径），%d 个 ## 标题" % (len(raw), len(before_lines), len(before_h2)))
    assert text.count("## fix round 3") == 0, "## fix round 3 已存在，不许重复追加"
    assert raw.count(b"\r\n") == 0, "报告文件本该是裸 LF"
    assert text.endswith("\n"), repr(text[-20:])

    new = text + SECTION.replace("\r\n", "\n")
    if not new.endswith("\n"):
        new += "\n"
    data = new.encode("utf-8")
    REPORT.write_bytes(data)

    back = REPORT.read_bytes()
    assert back == data, "落盘后读回不一致"
    t2 = back.decode("utf-8")
    after_lines = t2.split("\n")
    after_h2 = [l for l in after_lines if l.startswith("## ")]
    print("改后：%d 字节，%d 行，%d 个 ## 标题" % (len(back), len(after_lines), len(after_h2)))
    print("CRLF=%d 裸LF=%d BOM=%s 乱码=%s"
          % (back.count(b"\r\n"), back.count(b"\n") - back.count(b"\r\n"),
             back[:3] == b"\xef\xbb\xbf", "\ufffd" in t2))
    assert back.count(b"\r\n") == 0, "写坏了行尾"
    # 既有内容一字未动（前缀必须逐字相同）
    assert t2.startswith(text), "既有内容被改动了"
    assert t2[:len(text)] == text
    # 新增的 ## 标题恰为 1 个
    assert len(after_h2) == len(before_h2) + 1, (len(before_h2), len(after_h2))
    print("既有 %d 个 ## 标题全部保留、位置未变 = %s"
          % (len(before_h2), after_h2[:len(before_h2)] == before_h2))
    assert after_h2[:len(before_h2)] == before_h2
    print("新增的 ## 标题 = %r" % after_h2[-1])
    print("## fix round 3 出现次数 = %d" % t2.count("## fix round 3"))
    assert t2.count("## fix round 3") == 1
    for k in ("### fr3.0", "### fr3.1", "### fr3.2", "### fr3.3", "### fr3.4",
              "### fr3.5", "### fr3.6", "### fr3.7", "### fr3.8", "### fr3.9", "### fr3.10"):
        assert t2.count(k) == 1, (k, t2.count(k))
    print("fr3.0–fr3.10 各出现 1 次 OK")
    print("sha256[:16] 改前=%s 改后=%s"
          % (hashlib.sha256(raw).hexdigest()[:16], hashlib.sha256(back).hexdigest()[:16]))
    print("追加完成")


main()

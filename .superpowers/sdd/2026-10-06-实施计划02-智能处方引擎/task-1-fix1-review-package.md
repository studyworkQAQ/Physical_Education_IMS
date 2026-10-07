# Re-review package — Plan 02 Task 1 fix round 1

FIX_BASE ad1d190 -> HEAD 6a2938f

## git log --oneline
6a2938f docs: Plan02 Task1 fix round 1，修 4 条 Important 散文错误 + 两条架构守卫的相对导入放行

## git diff --stat
 backend/app/config.py                            |  11 +-
 backend/app/pipeline/daily.py                    |  31 ++++-
 backend/tests/architecture/test_domain_purity.py | 153 +++++++++++++++++++----
 backend/tests/architecture/test_layering.py      |  85 +++++++++++--
 backend/tests/db/test_models.py                  |  96 +++++++++++++-
 backend/tests/pipeline/test_daily.py             |  13 +-
 backend/tests/test_config.py                     |  30 +++++
 7 files changed, 371 insertions(+), 48 deletions(-)

## git diff -U10
diff --git a/backend/app/config.py b/backend/app/config.py
index 90d4b79..281c76b 100644
--- a/backend/app/config.py
+++ b/backend/app/config.py
@@ -26,18 +26,27 @@
 import pathlib
 
 __all__ = ["BACKEND_DIR", "DEFAULT_CSV_DIR", "DEFAULT_DB_URL"]
 
 #: ``backend/`` 的绝对路径。本文件在 ``backend/app/config.py``，故 ``parent.parent``。
 #: 它此前住在 ``app/seed/generate.py``（那里写作 ``pathlib.Path(__file__).resolve().parents[2]``，
 #: 与本式等价：``generate.py`` 在 ``backend/app/seed/`` 下，深一层）。
 BACKEND_DIR: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent
 
 #: ``python -m app.seed.generate`` 写三类 CSV 的缺省目录，也是
-#: :class:`~app.adapters.mock_lepao.MockLePaoAdapter` 的缺省 ``seed_dir``。
+#: :func:`app.adapters.factory.build_adapter` 在 ``kind="mock"`` 且没给 ``csv_dir`` 时
+#: 传给 :class:`~app.adapters.mock_lepao.MockLePaoAdapter` 的那个 ``seed_dir``
+#: （``app/adapters/factory.py:50``：
+#: ``return MockLePaoAdapter(DEFAULT_CSV_DIR if csv_dir is None else csv_dir)``）。
+#:
+#: ⚠️ **这个缺省值是工厂给的、不是构造函数给的**：``app/adapters/mock_lepao.py:428`` 是
+#: ``def __init__(self, seed_dir: pathlib.Path) -> None``——必填位置参数、**没有缺省值**，
+#: 故 ``MockLePaoAdapter()`` 会 ``TypeError``（响亮，不静默）。要拿缺省目录请调
+#: ``build_adapter()``，不要照本行字面去写构造调用。
+#:
 #: 该目录**不入库**（``.gitignore``），且在本仓里恒为空——生成器不许被随手跑。
 DEFAULT_CSV_DIR: pathlib.Path = BACKEND_DIR / "data" / "seed"
 
 #: 演示用磁盘库的 URL。``as_posix()`` 是承重的：Windows 上 ``str(Path)`` 给出反斜杠，
 #: 而 SQLite 的 URL 语法里反斜杠不是路径分隔符，``sqlite:///C:\\…\\pe.db`` 会被当成
 #: 一个名字里带反斜杠的相对文件。
 DEFAULT_DB_URL: str = f"sqlite:///{(BACKEND_DIR / 'pe.db').as_posix()}"
diff --git a/backend/app/pipeline/daily.py b/backend/app/pipeline/daily.py
index cc4fff6..8bf80c7 100644
--- a/backend/app/pipeline/daily.py
+++ b/backend/app/pipeline/daily.py
@@ -191,29 +191,52 @@ def _fitness_batch(
 
     终审 B 诚实标注过：它**构造了反例但没能演示 anchor 真的翻转**（重跑更早那天时
     ``_load_sources`` 又把 ``test_date`` PATCH 回去了），所以那条是 Major 不是 Critical。
     **修它的理由不是「它今天会错」，而是「Task 1 给 ``fitness_test_result`` 加了
     ``tested_on`` 之后，``test_date`` 的唯一职责变成 :func:`assessment_anchor` 的排序键」**
     （挑「``<= as_of`` 的最新一个 ``week1`` 批次」），而一个随执行顺序漂移的排序键是不可
     接受的：漂移一旦发生，被选中的评估锚点就换批次，全员的 ``years`` / 趋势 / 分层跟着换。
 
     ``min`` 折叠而不是「插入时写、更新时不动」：后者仍然**依赖执行顺序**（先跑的那天赢），
     而 ``min`` 是一个可交换、可结合的折叠——任意顺序、任意次重放，收敛到同一个值
-    （= 该批次见过的最早 ``tested_on``）。取「最早」也符合语义：一个批次的 ``test_date``
-    应当是「这次体测**开始**的那天」，而 ``assessment_anchor`` 用它当「这个批次是否已经
-    可用」的判据，用开始日是保守侧（宁可晚一点认它可用，也不要提前）。
+    （= 该批次见过的最早 ``tested_on``）。**这才是选 ``min`` 的全部理由**，与「保守」无关。
+
+    ⚠️ 取「最早」在**可用性**方向上是**提前**、不是延后——本段此前把方向写反了。
+    ``assessment_anchor`` 的判据是 ``FitnessTestBatch.test_date <= as_of``
+    （``app/pipeline/percentile_stage.py:133``：``models.FitnessTestBatch.test_date <= as_of,``），
+    ``test_date`` 越**小**，满足它的 ``as_of`` 就越**多**。实测（本轮亲跑：内存库，同一个
+    ``week1`` 批次、5 条成绩横跨 ``2025-09-01..09-05``，只改 ``test_date`` 这一个值，
+    逐日调用 :func:`app.pipeline.percentile_stage.assessment_anchor` 看它拿到批次没有；
+    n=1，判据是确定性的布尔查询，故不需要重复采样）::
+
+        test_date=2025-09-01  09-01=Y 09-02=Y 09-03=Y 09-04=Y 09-05=Y  -> 首次被选中 as_of=2025-09-01
+        test_date=2025-09-05  09-01=n 09-02=n 09-03=n 09-04=n 09-05=Y  -> 首次被选中 as_of=2025-09-05
+
+    这是**有意的**：批次里已经测完的那部分人当天就该有分层，而当天还没测到的人由
+    ``FitnessTestResult.tested_on <= as_of``（``percentile_stage.py:176``）逐行截断成
+    ``insufficient_data``，故「批次提前可用 + 只看见已测的那部分人」是自洽的，
+    读不到未来数据。语义上也对得上：一个批次的 ``test_date`` 就是「这次体测**开始**的那天」。
 
     代价是每条体测记录多一次按 ``(semester_id, timepoint)`` 的 SELECT（``repo.upsert``
     内部本来就有一次，故这一张表变成两次）。批次一共只有「两学年 × 三时点」至多 6 个，
     整学期回放（500 人 × 112 业务日）里体测记录约 3000 条，故多出约 3000 次索引查找；
     ``tests/pipeline/test_backfill.py::test_backfill_500_students_under_60_seconds``
-    的 ``elapsed < 60`` 是这条代价的守卫（实测数字见任务报告）。**不做进程内缓存**：
+    的 ``elapsed < 60`` 是这条代价的守卫。整学期回放的墙钟口径（**历史实测，不被守卫**；
+    Plan 02 Task 1，本机，用 ``git worktree`` 把基线 ``e26347f`` 检出到 ``$env:TEMP`` 后
+    两棵树背靠背各跑 n=2，同一个脚本、同一份 500 人 / ``seed=20250828`` / 112 业务日数据）：
+    基线 **20.48 / 20.85 s**（均值 20.66、组内极差 0.38 s），本 Task 之后
+    **20.89 / 21.18 s**（均值 21.03、组内极差 0.29 s）→ 差 **+0.37 s = +1.8%**，与两组
+    各自的抖动同量级，**n=2 不足以判定显著**。``elapsed < 60`` 的余量是
+    ``60 / 21.18 = 2.83×``（硬规矩 #42 的线是 2×）。⚠️ 上面四个墙钟数**没有测试看着**：
+    那条断言只在超过 60 s 时才红，墙钟退化到 25 s 它照样绿；且复现脚本不在库内，
+    要复量就得按上面的口径重跑一遍。
+    **不做进程内缓存**：
     缓存 ``test_date`` 等于在 ``repo.upsert`` 之外再开一个所有者，而省下的那点查询
     换不来「同一批次两个地方各存一份日期」的风险。
     """
     existing = session.scalar(
         select(models.FitnessTestBatch).where(
             models.FitnessTestBatch.semester_id == semester.id,
             models.FitnessTestBatch.timepoint == timepoint,
         )
     )
     batch = repo.upsert(
diff --git a/backend/tests/architecture/test_domain_purity.py b/backend/tests/architecture/test_domain_purity.py
index fdf9f29..a4c953f 100644
--- a/backend/tests/architecture/test_domain_purity.py
+++ b/backend/tests/architecture/test_domain_purity.py
@@ -4,25 +4,30 @@ spec §3.3 规定 ``app/domain/`` 禁止任何 I/O：不得 import 数据库 / H
 时钟、文件与无种子随机数接口。时间与随机数一律由调用方注入，参考表一律由
 :mod:`app.refdata` 加载后**作为参数传入**（Plan01 Ruling 15）。这是分层引擎与处方引擎
 可单测、可复现的前提，也是 spec §12「domain 分支覆盖 100%」能成立的前提。
 
 三条守卫，Plan 02 Task 1 全部改写过一次，改动理由各写在对应测试的 docstring 里：
 
 1. import 守卫从 **deny-list 改成 allow-list**（终审 A 的 M7）；
 2. 时钟与 ``open`` 从**子串匹配改成 AST 节点匹配**（解析 ``ast.Call`` 的 ``func``）；
 3. 三条都加 ``len(scanned) >= 5`` 的空转守卫——此前只有 ``DOMAIN.is_dir()``，而
    一个**存在但被搬空**的目录同样会让 ``rglob`` 返回空、offenders 恒为 ``[]``、测试假绿。
+
+第 1 条在 fix round 1 又补了一刀：相对导入不再无条件放行，先用 :func:`_absolute` 折算成
+绝对模块串再走白名单（``level >= 2`` 的相对导入会跨包，见该函数的 docstring）。
 """
 import ast
 import pathlib
 
 DOMAIN = pathlib.Path(__file__).resolve().parents[2] / "app" / "domain"
+#: ``backend/``。相对导入要折算成绝对串，就得知道源文件在包树里的位置，见 :func:`_package_of`。
+BACKEND = DOMAIN.parent.parent
 
 #: domain 允许 import 的**完整模块串**白名单（Plan02 Ruling 3）。
 #:
 #: ⚠️ 按**完整串**比对，不按顶层名：计划原文写「允许 ``collections.abc``」，而
 #: ``from collections.abc import X`` 的 AST 顶层名是 ``collections``
 #: （``node.module.split(".")[0]``）——按顶层名比对的话 ``collections.abc`` 这一项
 #: **永不匹配**，同时 ``from collections import OrderedDict`` 与
 #: ``from collections.abc import Iterable`` 变得无法区分，白名单退化成过宽的许可。
 #: 故 ``collections`` 与 ``collections.abc`` **两个都列**：前者覆盖 ``import collections``，
 #: 后者覆盖 ``from collections.abc import …`` 的完整串。
@@ -87,49 +92,118 @@ def _assert_not_empty(scanned: list[pathlib.Path]) -> None:
 def _imported_modules(tree: ast.AST):
     """yield ``(lineno, 完整模块串, 相对层级)``；``ast.walk`` 覆盖函数内导入。"""
     for node in ast.walk(tree):
         if isinstance(node, ast.Import):
             for alias in node.names:
                 yield node.lineno, alias.name, 0
         elif isinstance(node, ast.ImportFrom):
             yield node.lineno, (node.module or ""), node.level
 
 
-def _is_allowed(module: str, level: int) -> bool:
-    if level:
-        # 相对导入只可能落在 app.domain 包内（本守卫扫的就是这个包），恒合法
-        return True
+def _package_of(py: pathlib.Path) -> tuple[str, ...]:
+    """``py`` 所在的**包**，以 ``backend/`` 为根的段。
+
+    ``app/domain/x.py`` → ``("app", "domain")``，``app/domain/sub/x.py`` →
+    ``("app", "domain", "sub")``。``__init__.py`` 与同目录的普通模块给出**同一个**包：
+    去掉扩展名后最后一段在两种情况下都是「模块名」（``__init__`` / ``x``），故一律取
+    ``parts[:-1]``——这正是 Python 自己的 ``__package__``。
+    """
+    return py.relative_to(BACKEND).with_suffix("").parts[:-1]
+
+
+def _absolute(module: str, level: int, package: tuple[str, ...]) -> str | None:
+    """把 ``ast.ImportFrom`` 折算成**绝对模块串**；上溯到顶层包 ``app`` 之外返回 ``None``。
+
+    ``level == 0`` 本来就是绝对串。``level == 1`` 落在 ``package`` 自己这一层，
+    ``level == 2`` 上溯一层，依此类推——与 :func:`importlib.util.resolve_name` 同口径
+    （``resolve_name("..seed.generate", "app.domain.ind")`` == ``"app.seed.generate"``）。
+
+    **相对导入必须先折算再走白名单，不能一律放行**。这段判定此前住在 :func:`_is_allowed`
+    里、形如 ``if level: return True``，注释是「相对导入只可能落在 ``app.domain`` 包内」——
+    那句只对 ``level == 1`` 成立。合成树实测（``app/domain/probe.py`` 里逐条写入下列
+    写法后直接调用本测试函数）：``from .. import pipeline`` 解析到 ``app.pipeline``、
+    ``from ..seed import generate`` 解析到 ``app.seed.generate``，**改前两条全绿**。
+    这与 :data:`ALLOWED_MODULES` 的立意相反：allow-list 的意义是「没被显式允许的一律
+    不行」，而 ``if level: return True`` 恰好是「有一类写法一律允许」。
+
+    返回 ``None`` 的那一档（``app/domain/x.py`` 里写 ``from ...seed import …``）同样
+    判 offender、**不是「不管」**：Python 运行时会抛
+    ``ValueError: attempted relative import beyond top-level package``，但那是运行期的事，
+    静态守卫不拦的话「写一句永远跑不到的 import」也能让本测试全绿。
+    """
+    if level == 0:
+        return module
+    anchor = package[: len(package) - (level - 1)]
+    if not anchor:
+        return None
+    return ".".join(anchor + ((module,) if module else ()))
+
+
+def _is_allowed(module: str) -> bool:
+    """一个**绝对**模块串是否在白名单内（相对导入先经 :func:`_absolute` 折算）。"""
     if module == ALLOWED_PACKAGE or module.startswith(ALLOWED_PACKAGE + "."):
         return True
     return module in ALLOWED_MODULES
 
 
 def test_domain_imports_stay_within_the_allow_list():
     """domain 的 import 一律落在白名单内（allow-list，不是 deny-list）。
 
-    **为什么从 deny-list 改成 allow-list**：deny-list 只能挡住**已经被想到**的库。终审 A
-    实测旧 deny-list 能被 **14 种写法**绕过（如 ``from os import listdir``——旧守卫比的是
-    顶层名 ``os`` 在不在 ``FORBIDDEN`` 里，而它确实拦得住这一种；但 ``import importlib``
-    再 ``importlib.import_module("sqlalchemy")`` 这类间接写法它一个也拦不住）。allow-list
-    把举证责任反过来：**没被显式允许的一律不行**，于是不需要有人先想到 ``os`` 才会被挡。
+    **为什么从 deny-list 改成 allow-list**：deny-list 只能挡住**已经被想到**的库。基线
+    ``e26347f`` 上那个集合是**六项**，里面**没有 ``os``**（``git show
+    e26347f:backend/tests/architecture/test_domain_purity.py`` 第 13 行）::
+
+        FORBIDDEN = {"sqlalchemy", "fastapi", "requests", "httpx",
+                     "pydantic_settings", "random"}
+
+    它比的是 AST 取出的**顶层名**（同文件 ``:38`` ``mods = [a.name.split(".")[0] …]``、
+    ``:40`` ``mods = [node.module.split(".")[0]]``、``:41`` ``… if m in FORBIDDEN``）。
+    把基线守卫落盘、``DOMAIN`` 重定向到一棵合成树后亲跑，**下面三种写法在基线上三条守卫
+    全绿**：
+
+    * ``from os import listdir`` —— 第一条取出顶层名 ``os``，不在 ``FORBIDDEN``；第三条
+      子串守卫也撞不上：源码里写的是 ``os import``，**没有**子串 ``import os``，
+      也没有 ``os.listdir``。
+    * ``import numpy.random`` —— 顶层名 ``numpy`` 不在 ``FORBIDDEN``（Global Constraints
+      点名要挡的无种子随机数由此进来）。
+    * ``import app.refdata`` —— 顶层名 ``app`` 不在 ``FORBIDDEN``。
+
+    控制组（证明基线守卫**不是恒绿**，同一次跑）：``import sqlalchemy`` → 第一条 **红**；
+    ``import os`` → 第三条 **红**（源码里有子串 ``import os``）；``os.listdir('x')`` →
+    第三条 **红**。故基线守卫是有牙的，只是牙口不含 ``from os import …`` 这一种写法。
+
+    allow-list 把举证责任反过来：**没被显式允许的一律不行**，于是不需要有人先想到 ``os``
+    才会被挡。终审 A 说的「14 种写法可绕过」是它自己的枚举，本轮没有逐条复跑；上面三条
+    是**亲跑基线**的结果，两者方向一致。
 
     ⚠️ **这一条是回归守卫、不是修复**（Plan02 Ruling 4）。落地当天 domain 六个文件的
     全部 import 就已经在白名单内，所以它**一上来就是绿的**——计划原文 Step 2 写的
     「allow-list 守卫报 ``numpy`` 之外的漏网」是猜的，AST 亲扫没有漏网。它的价值不在于
     今天红不红，而在于**新增的拦截力**：
 
     * ``import app.refdata`` 从此会被抓。终审 A 曾说「domain 经两跳依赖 ``app.refdata``」，
       **AST 实测不成立**——那是 ``percentile.py`` 模块 docstring 里的自陈（说的是「参考表
       由 refdata 加载后注入」这件事），不是 import。旧 deny-list 里没有 ``app.refdata``，
       所以真的加上这一句 import 时它不会响；白名单会。
     * ``from os import listdir`` / ``import json`` / ``import pathlib`` 一律被抓，
       不必再靠第三条守卫的子串去撞。
+    * **相对导入一律先折算成绝对串**再走白名单（:func:`_absolute`）。今天全仓的相对导入
+      只有 ``app/db/models/`` 包内的 ``level == 1``（命令::
+
+          cd backend; python -c "import ast,pathlib; [print(p, n.lineno, n.level, n.module) for p in sorted(pathlib.Path('app').rglob('*.py')) for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.level]"
+
+      实测 12 条、全部 ``level == 1``），故 domain 侧**没有 offender**；但 Plan 02 Task 2
+      起会建 ``app/domain/prescription/`` 这一层子包，届时 ``level == 2`` 的相对导入
+      开始正常出现，「一律放行」的写法会跟着变成真漏洞。折算之后
+      ``app/domain/sub/x.py`` 里的 ``from ..tables import X`` 仍然合法（解析到
+      ``app.domain.tables``），而 ``from ..seed import generate`` 解析到 ``app.seed.generate``
+      → offender。
 
     **落地当天的 import 全貌**（AST 亲扫，这就是白名单取值的实测依据；命令::
 
         python -c "import ast,pathlib; [print(p.name, sorted({a.name for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.Import) for a in n.names} | {n.module for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.module})) for p in sorted(pathlib.Path('app/domain').rglob('*.py'))]"
 
     在 ``backend/`` 下跑，基线 ``e26347f``）::
 
         __init__.py      []
         derive.py        ['app.domain.indicators', 'app.domain.percentile', 'dataclasses', 'enum']
         indicators.py    ['app.domain.tables', 'enum']
@@ -140,38 +214,48 @@ def test_domain_imports_stay_within_the_allow_list():
         tables.py        ['collections.abc', 'dataclasses']
 
     六个文件、去重后**五个**不同的顶层来源（``dataclasses`` / ``enum`` /
     ``collections.abc`` / ``numpy`` / ``app.domain.*``），全部在白名单内。
     ``typing`` 在名单里但今天没人用：它是 ``Mapped[str | None]`` 这类标注的天然候选，
     列进来是为了让「加一个类型标注」不必先改架构测试。
     """
     scanned = _domain_files()
     offenders: list[str] = []
     for py in scanned:
+        package = _package_of(py)
         tree = ast.parse(py.read_text(encoding="utf-8"))
         for lineno, module, level in _imported_modules(tree):
-            if not _is_allowed(module, level):
-                offenders.append(f"{py.name}:{lineno}: {module or '<空模块名>'}")
+            absolute = _absolute(module, level, package)
+            if absolute is not None and _is_allowed(absolute):
+                continue
+            written = module or "<空模块名>"
+            if level:
+                target = "<上溯到顶层包 app 之外>" if absolute is None else absolute
+                written = f"{'.' * level}{module} → {target}"
+            offenders.append(f"{py.name}:{lineno}: {written}")
 
     _assert_not_empty(scanned)
     assert offenders == [], (
         "app/domain 是叶子层，import 必须落在白名单内"
         f"（{sorted(ALLOWED_MODULES)} + {ALLOWED_PACKAGE}.*）：\n" + "\n".join(offenders)
     )
 
 
 def _dotted(node: ast.AST) -> str | None:
     """把一个表达式还原成点号串（``dt.datetime.now`` → ``"dt.datetime.now"``）。
 
-    还原不出来的形态（``f()()``、``table[0]()``、``getattr(x, "now")()``）返回 ``None``。
-    那不是漏洞：这类写法要先拿到 ``datetime`` / ``time`` / ``builtins`` 这个对象，而
-    拿到它的唯一途径是 import，import 已经被 allow-list 挡在门外。
+    还原不出来的形态（``f()()``、``table[0]()``、``getattr(x, "now")()``）返回 ``None``，
+    本守卫因此**放过**它们。对 ``datetime`` / ``time`` / ``builtins`` 那不是漏洞：拿到这些
+    对象的唯一途径是 import，而 import 已经被 allow-list 挡在门外。**但 ``open`` 是内置名、
+    不需要 import**，故这一档对 ``open`` 是真漏——与
+    :func:`test_domain_has_no_clock_or_file_access` docstring 里那条「别名间接不被守卫」
+    是同一个缺口，两处一起看才是本守卫的完整能力边界。
     """
     parts: list[str] = []
     while isinstance(node, ast.Attribute):
         parts.append(node.attr)
         node = node.value
     if not isinstance(node, ast.Name):
         return None
     parts.append(node.id)
     return ".".join(reversed(parts))
 
@@ -186,30 +270,51 @@ def _hit_forbidden_call(dotted: str) -> str | None:
     """
     for name in sorted(FORBIDDEN_CALLS):
         if dotted == name or dotted.endswith("." + name):
             return name
     return None
 
 
 def test_domain_has_no_clock_or_file_access():
     """domain 不得调用时钟，也不得自己打开文件句柄。
 
-    **为什么从子串改成 AST 节点匹配**（终审 A 的 M7）：子串匹配同时有两种失效。
-
-    * **漏报**：``import datetime as dt`` 之后写 ``dt.datetime.now()``，子串
-      ``"datetime.now"`` 恰好在里面，这一种能撞上；但 ``now = datetime.now`` 再
-      ``now()`` 就撞不上了，而 AST 侧只要 ``now`` 的赋值来源是一次 ``ast.Call``
-      就能顺着 ``_dotted`` 追到。
-    * **误报**：docstring 或注释里出现一句「不要用 ``datetime.now()``」就会把守卫
-      弄红。Plan 01 因此**不敢在 domain 的散文里写这些词**，那是让守卫反过来审查
-      文档——本仓的 docstring 恰恰要求把口径写全（硬规矩 #19）。AST 只看代码节点，
-      散文里怎么提都不响。
+    **为什么从子串改成 AST 节点匹配**（终审 A 的 M7）。**收益是「不再误报」，不是「多抓
+    漏报」**——本节此前把方向写反了（它说 AST 侧「顺着 ``_dotted`` 追赋值」，而
+    :func:`_dotted` 只还原调用表达式自身、代码里没有任何赋值追踪）。下面是合成树上的实测
+    口径：把 ``DOMAIN`` 指到 ``$env:TEMP`` 下一棵只有 ``app/domain/`` 的合成树，逐条写进
+    一个探针文件后分别调用三条守卫（本轮亲跑）::
+
+        probe.py 的内容                                   G1 allow-list  G2 AST 时钟/open  G3 子串 IO
+        _f = open; _f('x')                                GREEN          GREEN             GREEN
+        def reopen(): …  然后 reopen()                     GREEN          GREEN             GREEN
+        def open_ended(): …  然后 open_ended()             GREEN          GREEN             GREEN
+        只有 docstring:「不要用 datetime.now()，也不要 open(」 GREEN          GREEN             GREEN
+        open('x')                                         GREEN          RED               GREEN
+        import builtins; builtins.open('x')               RED            RED               GREEN
+        import datetime as dt; dt.datetime.now()           RED            RED               GREEN
+
+    * **误报没了**（真收益）：第 4 行。旧守卫是逐项 ``if c in src``（基线 ``e26347f`` 的
+      ``test_domain_purity.py:50``），Plan 01 因此**不敢在 domain 的散文里写这些词**——
+      那是让守卫反过来审查文档，而本仓的 docstring 恰恰要求把口径写全（硬规矩 #19）。
+      AST 只看 ``ast.Call`` 节点，散文里怎么提都不响。
+    * **``.`` 边界替代 ``\\b`` 正则**：第 2、3 行不被误抓，而第 6 行 ``builtins.open()``
+      仍然被抓（:func:`_hit_forbidden_call`）。
+    * **点号形态天然覆盖**：第 7 行由 :func:`_dotted` 还原成 ``"dt.datetime.now"``、命中
+      ``datetime.now`` 那一项。但旧子串守卫这一种**也能撞上**（源码里就有子串
+      ``datetime.now``），故**不是新增拦截力**。
+
+    ⚠️ **本条守不住什么**（硬规矩 #39）：第 1 行 ``_f = open`` 再 ``_f('x')`` **三条守卫
+    全绿**。``open`` 是内置名、不需要 import，故 G1 的白名单帮不上；:data:`FORBIDDEN_IO`
+    里没有裸 ``open``，故 G3 的子串也帮不上；G2 拿到的 ``node.func`` 是
+    ``ast.Name(id="_f")`` → 点号串 ``"_f"`` → 不命中 :data:`FORBIDDEN_CALLS`。
+    ``now = datetime.now`` 再 ``now()`` 同理（那种写法 G1 会先因 ``import datetime`` 变红，
+    但**红的原因不是这次调用**）。堵这一类需要数据流/别名分析，本仓不做。
 
     ``open`` 从旧的 ``\\bopen\\s*\\(`` 正则并进 :data:`FORBIDDEN_CALLS`：它本来也是
     一次 ``ast.Call``，两套机制守同一件事只会让人分不清哪条是真相。
 
     ⚠️ **本条今天与 allow-list 高度重叠**：``datetime`` / ``time`` 都不在白名单里，
     所以 domain 根本 import 不到它们；``open`` 是内置名，不需要 import，故它是本条
     **唯一独立生效**的封禁项。保留整条的理由是纵深：白名单是「不许拿到工具」，本条是
     「不许做这个动作」——将来有人为了别的原因把 ``datetime`` 加进白名单（一个完全可能
     的合法请求，比如要一个 ``date`` 类型标注），本条仍然挡着 ``datetime.now()``。
     """
diff --git a/backend/tests/architecture/test_layering.py b/backend/tests/architecture/test_layering.py
index ad1d6f1..b11d252 100644
--- a/backend/tests/architecture/test_layering.py
+++ b/backend/tests/architecture/test_layering.py
@@ -60,34 +60,78 @@ FORBIDDEN_PREFIX = "app.seed"
 
 
 def _py_files(relative_dir: str) -> list[pathlib.Path]:
     """一个生产层目录下的全部 ``.py``，按路径升序（报告顺序因此稳定可复现）。"""
     root = APP / relative_dir
     # Path.rglob() 对不存在的目录静默返回空，缺了这行守卫会空转全绿
     assert root.is_dir(), f"目录缺失，架构测试将空转: {root}"
     return sorted(root.rglob("*.py"))
 
 
-def _imported_modules(tree: ast.AST):
+def _package_of(py: pathlib.Path) -> tuple[str, ...]:
+    """``py`` 所在的**包**，以 ``backend/`` 为根的段。
+
+    ``app/pipeline/x.py`` → ``("app", "pipeline")``；``app/db/models/x.py`` 与
+    ``app/db/models/__init__.py`` **都**是 ``("app", "db", "models")``——去掉扩展名后最后
+    一段在两种情况下都是「模块名」（``x`` / ``__init__``），故一律取 ``parts[:-1]``，
+    这正是 Python 自己的 ``__package__``。
+    """
+    return py.relative_to(BACKEND).with_suffix("").parts[:-1]
+
+
+def _absolute(module: str, level: int, package: tuple[str, ...]) -> str | None:
+    """把 ``ast.ImportFrom`` 折算成**绝对模块串**；上溯到顶层包 ``app`` 之外返回 ``None``。
+
+    与 :func:`importlib.util.resolve_name` 同口径（``resolve_name("...seed.generate",
+    "app.db.models.organisation")`` == ``"app.seed.generate"``）。``None`` 的那一档
+    （如 ``app/pipeline/x.py`` 里写 ``from ...seed import …``）由调用方直接判 offender：
+    Python 运行时会抛 ``ValueError: attempted relative import beyond top-level package``，
+    但静态守卫不拦的话「写一句永远跑不到的 import」也能让本测试全绿。
+    """
+    if level == 0:
+        return module
+    anchor = package[: len(package) - (level - 1)]
+    if not anchor:
+        return None
+    return ".".join(anchor + ((module,) if module else ()))
+
+
+def _imported_modules(tree: ast.AST, package: tuple[str, ...]):
     """yield ``(lineno, 完整模块串)``；``ast.walk`` 因此覆盖函数内导入。
 
-    相对导入（``node.level > 0``）一律跳过：它只可能落在**同一个包内**，而
-    ``app.pipeline`` / ``app.db`` / ``app.domain`` 三个包里都没有 ``app.seed``。
+    相对导入（``node.level > 0``）**不再一律跳过**，而是先经 :func:`_absolute` 折算成绝对
+    串。此前这里写的是 ``if node.level: continue``，理由写的是「它只可能落在**同一个包
+    内**」——那句只对 ``level == 1`` 成立。``level >= 2`` 会**跨包**，而本守卫要抓的
+    ``app.seed`` 恰恰在包外：
+
+    * ``app/pipeline/x.py`` 里的 ``from ..seed import generate``（``level == 2``）解析到
+      ``app.seed.generate``；
+    * ``app/db/models/x.py`` 里的 ``from ...seed import generate``（``level == 3``）同样
+      解析到 ``app.seed.generate``。**这一档是 Plan 02 Task 1 的拆包新造出来的**：拆包前
+      ``app/db/models.py`` 的 ``level == 2`` 才到 ``app``，拆包后要 ``level == 3``——
+      模块深度多了一层，于是「三级相对导入」从不可达变成可达。
+
+    合成树实测（把 ``BACKEND`` / ``APP`` 指到 ``$env:TEMP`` 下一棵形状与 ``backend/app``
+    相同的树，逐条写进探针文件后直接调用本测试函数）：上述两种写法**改前全绿**、改后全红。
+
+    而 ``app/db/models/`` 包内**真实存在**的那批相对导入，折算后是 ``app.db.models._shared``
+    / ``app.db.models.organisation`` 一类，不以 ``app.seed`` 开头，**仍然绿**。它们的全貌用
+    这条命令数（本轮亲跑：12 条、全部 ``level == 1``、全部落在 ``app.db.models`` 包内）::
+
+        cd backend; python -c "import ast,pathlib; [print(p, n.lineno, n.level, n.module) for p in sorted(pathlib.Path('app').rglob('*.py')) for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.level]"
     """
     for node in ast.walk(tree):
         if isinstance(node, ast.Import):
             for alias in node.names:
                 yield node.lineno, alias.name
         elif isinstance(node, ast.ImportFrom):
-            if node.level or not node.module:
-                continue
-            yield node.lineno, node.module
+            yield node.lineno, _absolute(node.module or "", node.level, package)
 
 
 def _is_forbidden(module: str) -> bool:
     """按**完整模块串**判前缀，且只在 ``.`` 边界上匹配。
 
     边界是必需的：裸 ``startswith("app.seed")`` 会把 ``app.seedling`` 这类
     （今天不存在、但将来可能有的）合法模块误判成 offender。
     """
     return module == FORBIDDEN_PREFIX or module.startswith(FORBIDDEN_PREFIX + ".")
 
@@ -97,25 +141,42 @@ def test_production_layers_never_import_app_seed():
 
     offender 一次性报全（``assert offenders == []``）：逐处 assert 的话第一个红会盖住
     后面的，而迁移这四处是一次性的活，一次看全才不必跑四遍。
     """
     scanned: list[pathlib.Path] = []
     offenders: list[str] = []
     for relative_dir in SCANNED_DIRS:
         for py in _py_files(relative_dir):
             scanned.append(py)
             tree = ast.parse(py.read_text(encoding="utf-8"))
-            for lineno, module in _imported_modules(tree):
-                if _is_forbidden(module):
-                    where = py.relative_to(BACKEND).as_posix()
+            where = py.relative_to(BACKEND).as_posix()
+            for lineno, module in _imported_modules(tree, _package_of(py)):
+                if module is None:
+                    offenders.append(f"{where}:{lineno}: 相对导入上溯到顶层包 app 之外")
+                elif _is_forbidden(module):
                     offenders.append(f"{where}:{lineno}: {module}")
 
     # 空转守卫：目录被搬空 / 拼错时 offenders 恒为 []，测试会假绿。
-    # 基线 e26347f 上实测 pipeline 7 + db 4 + domain 6 = 17 个 .py
-    # （命令：python -c "…rglob('*.py')…"，见任务报告）。下界取 8 而不是 17：
-    # 拆包 / 合并模块会正常地改变文件数，17 会让一次合法重构也变红。
+    # 文件数实测（在**仓库根**跑，一条命令数完三个目录；本轮亲跑）::
+    #
+    #     python -c "import pathlib,collections; c=collections.Counter(p.parts[2] for p in pathlib.Path('backend/app').rglob('*.py') if p.parts[2] in ('pipeline','db','domain')); print(sorted(c.items()), sum(c.values()))"
+    #
+    #   基线 e26347f          → [('db', 4), ('domain', 6), ('pipeline', 7)] 17
+    #   Task 1 拆包后 ad1d190 → [('db', 11), ('domain', 6), ('pipeline', 7)] 24
+    #
+    # 交叉核对（同样在仓库根跑，逐文件名可比）::
+    #
+    #     git ls-tree -r --name-only <commit> -- backend/app/pipeline backend/app/db backend/app/domain
+    #
+    # 下界取 8 而不是实测的 17 / 24：拆包与合并模块都会正常地改变文件数，写死实测值会让
+    # 一次合法重构变红。**代价（硬规矩 #39）**：8 只挡得住「三个目录被一起搬空」——单个
+    # 目录被搬空时仍剩 13…17 个 .py，本断言拦不住。那一档的兜底是：``domain`` 由
+    # ``tests/architecture/test_domain_purity.py`` 自己那条 ``>= 5`` 空转守卫看着；
+    # ``pipeline`` / ``db`` 被搬空时 ``tests/pipeline/`` 与 ``tests/db/`` 会在**收集期**
+    # 就 ImportError（它们直接 ``from app.pipeline import …`` / ``from app.db import …``）。
+    # 目录被**整个删掉**则由 :func:`_py_files` 里的 ``root.is_dir()`` 当场拦下。
     assert len(scanned) >= 8, f"只扫到 {len(scanned)} 个 .py，目录可能被搬空: {SCANNED_DIRS}"
 
     assert offenders == [], (
         f"生产层依赖了仿真数据生成器 app.seed（spec §3.3 依赖方向单向不可逆）：\n"
         + "\n".join(offenders)
     )
diff --git a/backend/tests/db/test_models.py b/backend/tests/db/test_models.py
index 8f9be97..23cdf29 100644
--- a/backend/tests/db/test_models.py
+++ b/backend/tests/db/test_models.py
@@ -580,36 +580,126 @@ _SINGLE_PERSON_QUERIES = (
 
 def test_single_person_queries_are_index_served(session):
     """两条单人查询必须走 ``(student_id, computed_on)`` 索引，不得全表扫、不得另建临时 B-tree。
 
     **这条测试取代了计划 Step 4 第 1 项要的显式 ``Index``**，理由是本仓实测那条索引是
     **冗余**的：Plan01 Ruling 212 已经给这两张表加了
     ``UniqueConstraint("student_id", "computed_on")``，而 SQLite 会为 UNIQUE 约束自动建出
     一条同列序的索引（``sqlite_autoindex_<table>_1``），查询规划器已经在用它。
 
     实测（本机、CPython 3.11 + SQLAlchemy 2.1 + SQLite；500 人 × 112 业务日 = **56000 行**
-    ``stratification_result``；每条查询 300 次、随机学号、``random.Random(20250828)``；
-    落磁盘库后按 ``.db`` 文件字节量体积）：
+    ``stratification_result``；每条查询 n=300、学号由 ``random.Random(20250828)`` 抽、先跑
+    同规模一遍预热；落**磁盘**库、``eng.dispose()`` 之后按 ``.db`` 文件字节量体积）：
 
     ==============================  ==================  ==================  =====================
     场景                             单次墙钟中位 (ms)    ``.db`` 字节        EXPLAIN QUERY PLAN
     ==============================  ==================  ==================  =====================
     A 仅 UniqueConstraint 的自动索引        0.2708           5 423 104        ``USING COVERING INDEX sqlite_autoindex_stratification_result_1 (student_id=?)``
     B A + 显式 ``Index(student_id, computed_on)``  0.2941      6 791 168        ``USING COVERING INDEX ix_stratification_result_student_computed (student_id=?)``
     ==============================  ==================  ==================  =====================
 
-    B/A = **1.086**（即加了索引**没有变快**，中位数还慢了 8.6%，n=300，两个场景各自
+    B/A = **1.086**（即加了索引**没有变快**，中位数还慢了 8.6%，两个场景各自
     min…max = 0.1385…0.9031 与 0.1698…1.0212 ms，区间完全重叠），而文件体积
     **+1 368 064 B = +25.23%**（十进制百分比；计划原文写的代价是「+2.7% 文件体积」，
     与本次实测差一个量级）。计划原文的收益数字「57.9 ms → 0.2 ms（258×）」因此只能来自
     一个**没有**那条 UNIQUE 约束的 schema——即 Plan01 Ruling 212 落地之前的状态。
 
+    ⚠️ **上面四个数不被守卫**（硬规矩 #39）：本测试守的是**查询计划**与**两条唯一约束的
+    列序**，全仓**没有任何测试量墙钟或 ``.db`` 字节**——它们变了不会红。故上表属历史实测，
+    而产生它的脚本此前不在库内（从仓库无法复现）；本轮把它整段抄在下面，在**仓库根**跑
+    ``python <存成 .py 的本段>`` 即可复现。
+
+    本轮（Plan 02 Task 1 fix round 1）**复跑**了它：``.db`` 字节与两条查询计划**逐字复现**
+    （5 423 104 / 6 791 168 / +1 368 064 B / +25.23%），但**墙钟中位不复现**——同一个脚本
+    连跑四次，B/A 依次是 **1.086 / 0.944 / 1.019 / 0.989**（每次 n=300）。所以可复现的结论
+    只有「加了具名索引**没有可测的加速**」，而**「慢 8.6%」这个方向不可复现**，是机器/负载
+    噪声；上表的 0.2708 / 0.2941 ms 仅作为**当时那一组**样本留档，不要当稳定量引用。
+
+    复现脚本（完整内容，本轮亲跑验证过；``#`` 注释处原本是脚本自己的 docstring，为了不与
+    本 docstring 的三引号打架而改成注释）::
+
+        import datetime as dt, pathlib, random, statistics, sys, tempfile, time
+        sys.path.insert(0, "backend")
+        from sqlalchemy import Index, create_engine, text
+        from app.db import models as M
+        from app.db.session import Session, init_db
+
+        N, DAYS, BASE = 500, 112, dt.date(2025, 9, 1)
+        Q = ("select id from stratification_result where student_id = :sid "
+             "order by computed_on desc limit 1")
+
+
+        def build(tmp, tag, extra_index):
+            # 场景 A/B 只差 extra_index：A 只有 UniqueConstraint 的 autoindex，
+            # B 再加计划 Step 4 第 1 项要的那条具名 Index
+            dbfile = tmp / f"{tag}.db"
+            eng = create_engine(f"sqlite:///{dbfile.as_posix()}")
+            init_db(eng)
+            if extra_index:
+                Index("ix_stratification_result_student_computed",
+                      M.StratificationResult.student_id,
+                      M.StratificationResult.computed_on).create(eng)
+            with Session(eng) as s:
+                sem = M.Semester(name="2025-2026-1", start_date=BASE,
+                                 end_date=BASE + dt.timedelta(days=DAYS + 1),
+                                 weeks=16, is_current=True)
+                s.add(sem); s.flush()
+                run = M.DailySyncRun(semester_id=sem.id, business_date=BASE, status="success")
+                s.add(run); s.flush()
+                s.add_all([M.Student(student_no=f"2025{i:06d}", name="x", sex="male",
+                                     birth=dt.date(2006, 1, 1), grade=1) for i in range(N)])
+                s.flush()
+                s.add_all([M.StratificationResult(
+                    student_id=sid, computed_on=BASE + dt.timedelta(days=d), batch_id=run.id,
+                    label="green", hit_rules="R1,R2,Y1", input_snapshot={},
+                    percentile_source="school", valid_from=BASE + dt.timedelta(days=d))
+                    for sid in range(1, N + 1) for d in range(DAYS)])
+                s.commit()
+            return eng, dbfile
+
+
+        def bench(eng, n=300):
+            # n 次同一条查询，学号由固定种子抽；先跑同规模一遍预热
+            rng = random.Random(20250828)
+            sids = [rng.randrange(1, N + 1) for _ in range(n)]
+            out = []
+            with eng.connect() as c:
+                for sid in sids:
+                    c.execute(text(Q), {"sid": sid}).all()
+                for sid in sids:
+                    t0 = time.perf_counter()
+                    c.execute(text(Q), {"sid": sid}).all()
+                    out.append((time.perf_counter() - t0) * 1000.0)
+                plan = [r[3] for r in
+                        c.execute(text("explain query plan " + Q.replace(":sid", "1")))]
+            return out, plan
+
+
+        tmp = pathlib.Path(tempfile.mkdtemp(prefix="pe_idx_"))
+        res = {}
+        for tag, extra in (("A", False), ("B", True)):
+            eng, dbfile = build(tmp, tag, extra)
+            with eng.connect() as c:
+                assert c.execute(
+                    text("select count(*) from stratification_result")).scalar() == N * DAYS
+            samples, plan = bench(eng)
+            eng.dispose()                       # 先释放句柄，再量 .db 字节
+            lo, hi = min(samples), max(samples)
+            res[tag] = (statistics.median(samples), lo, hi, dbfile.stat().st_size)
+            print(f"{tag}  median={res[tag][0]:.4f} ms  min={lo:.4f}  max={hi:.4f}"
+                  f"  .db={res[tag][3]} B")
+            for p in plan:
+                print(f"   plan: {p}")
+        a, b = res["A"], res["B"]
+        print(f"行数 {N}*{DAYS} = {N * DAYS}   B/A = {b[0] / a[0]:.3f}"
+              f"   .db +{b[3] - a[3]} B = +{(b[3] - a[3]) / a[3] * 100:.2f}%")
+
     所以本测试守的是**结果**（走索引、不全表扫、不排序）而不是**机制**（某条具名索引存在）。
     这样它同时挡住两种回归：有人删掉 UNIQUE 约束而没补索引，以及有人加了一条列序不对的
     索引（如 ``(computed_on, student_id)``——前导列不是 ``student_id`` 时这条查询用不上它）。
     """
     # 用会话自己那条连接：``session.get_bind()`` 给的是 ``Engine``，SQLAlchemy 2.x 上它
     # 没有 ``.execute``；而另开一条连接会离开本会话的事务（夹具是 ``sqlite:///:memory:``，
     # 是否还是同一个库取决于连接池策略，不该由本测试来赌）。
     conn = session.connection()
     for table, query in _SINGLE_PERSON_QUERIES:
         detail = [row[3] for row in conn.execute(text("explain query plan " + query))]
diff --git a/backend/tests/pipeline/test_daily.py b/backend/tests/pipeline/test_daily.py
index ff25ef5..9951ec1 100644
--- a/backend/tests/pipeline/test_daily.py
+++ b/backend/tests/pipeline/test_daily.py
@@ -632,24 +632,29 @@ def _spread_week1_tested_on(seed_dir: pathlib.Path, days: tuple[str, ...]) -> in
 def test_fitness_batch_folds_test_date_to_the_earliest(session):
     """``_fitness_batch`` 对乱序的日期做 ``min`` 折叠，且四次调用只产生**一行**批次。
 
     直接喂乱序日期而不走 ``run_daily``：缺省数据造不出多日批次（见
     :func:`_spread_week1_tested_on` 的 docstring），而折叠本身是这个修复的全部内容。
 
     四次调用的期望值逐个**写死**（硬规矩 #35，不从被测函数读回来）。改回「每条记录都
     PATCH ``test_date``」之后第三次会得到 ``2025-09-05`` 而不是 ``2025-09-01``，当场红。
 
     ``min`` 折叠而不是「插入时写、更新时不动」：后者仍然依赖执行顺序（先跑的那天赢），
-    而 ``min`` 可交换、可结合，任意顺序任意次重放都收敛到同一个值。取「最早」也符合语义
-    ——``assessment_anchor`` 用这一列当「该批次是否已可用」的判据，用**开始日**是保守侧
-    （宁可晚一点认它可用），而批次内更晚的那些记录由
-    ``fitness_test_result.tested_on <= as_of`` 逐行截断兜住。
+    而 ``min`` 可交换、可结合，任意顺序任意次重放都收敛到同一个值——**这才是选它的理由**，
+    与「保守」无关。取「最早」在**可用性**方向上是**提前**、不是延后：``assessment_anchor``
+    的判据是 ``test_date <= as_of``（``app/pipeline/percentile_stage.py:133``），``test_date``
+    越小满足它的 ``as_of`` 越多。实测（内存库，同一批 5 条成绩横跨 ``2025-09-01..09-05``、
+    只改 ``test_date`` 一个值，逐日调用 ``assessment_anchor``）：``test_date=09-01`` 从
+    ``as_of=09-01`` 起就被选中，``test_date=09-05`` 要等到 ``as_of=09-05``——两行逐日输出
+    见 :func:`app.pipeline.daily._fitness_batch` 的 docstring。这是有意的：批次内更晚的那些
+    记录由 ``fitness_test_result.tested_on <= as_of``（``percentile_stage.py:176``）逐行
+    截断兜住，故读不到未来数据。
     """
     semester = session.scalar(select(M.Semester).where(M.Semester.name == SEMESTER_NAME))
     assert semester is not None, "夹具应已由 seed_database 建好本学年"
     assert session.scalar(select(func.count()).select_from(M.FitnessTestBatch)) == 0
 
     calls = (
         (dt.date(2025, 9, 8), dt.date(2025, 9, 8)),   # 首条：插入，用它自己的值
         (dt.date(2025, 9, 1), dt.date(2025, 9, 1)),   # 更早 → 折叠下去
         (dt.date(2025, 9, 5), dt.date(2025, 9, 1)),   # 更晚 → 不动（改回 PATCH 就是 09-05）
         (dt.date(2025, 9, 1), dt.date(2025, 9, 1)),   # 重复 → 幂等
diff --git a/backend/tests/test_config.py b/backend/tests/test_config.py
new file mode 100644
index 0000000..7c8b9af
--- /dev/null
+++ b/backend/tests/test_config.py
@@ -0,0 +1,30 @@
+"""``app.config`` 三个缺省值的**非同源**断言（硬规矩 #35）。
+
+``tests/adapters/test_factory.py:32`` 那条 ``assert adapter.seed_dir == DEFAULT_CSV_DIR``
+两侧**同源于 ``app.config``**：它证明的是「工厂把常量的值原样交给了适配器」，而**不能**
+证明那个值本身对——把 ``DEFAULT_CSV_DIR`` 改成 ``BACKEND_DIR / "wrong"`` 它照样绿。
+``DEFAULT_DB_URL`` 在 ``tests/`` 下此前**没有任何断言**（``git grep -n "DEFAULT_DB_URL"
+-- backend/tests`` 在基线 ``ad1d190`` 上给 2 条命中，两条都是
+``tests/architecture/test_layering.py:22-23`` docstring 里引的基线 offender 原文）。
+本文件补上缺的那一半：期望值**字面写死在这里**。
+
+**为什么只钉后缀与文件名就够了**：``BACKEND_DIR`` 自己错了**会**变红——
+``app/refdata.py:23`` 是 ``DATA_DIR = BACKEND_DIR / "data"``，而
+``tests/test_refdata.py:82-83`` 断言 ``refdata.DATA_DIR.name == "data"`` 且
+``(refdata.DATA_DIR / "national_standard_2014.csv").is_file()``、``:187`` 再按
+``DATA_DIR / STANDARD_FILENAME`` 取那份评分表量指纹 ``D2C8E539E2FA0029``：``BACKEND_DIR``
+一错，这两条当场找不到文件。故这里真正裸奔的只剩 ``"data"/"seed"`` 这个后缀与 ``pe.db``
+这个文件名。
+
+**本文件不守什么**（硬规矩 #39）：``backend/data/seed/`` **是否存在、是否为空**不由这里管
+（它不入库、本仓恒为空，那是各 Task 收工清单里的禁区检查，不是配置值的性质）；
+``backend/pe.db`` **不得存在**那条也不在这里断言——它是运行期状态，且把它写进测试会让
+「跑过 CLI 的机器上测试变红」这种与配置无关的失败混进来。
+"""
+from app.config import BACKEND_DIR, DEFAULT_CSV_DIR, DEFAULT_DB_URL
+
+
+def test_default_csv_dir_and_db_url_are_pinned_by_literal_suffixes():
+    """``DEFAULT_CSV_DIR`` 的后缀与 ``DEFAULT_DB_URL`` 的尾部用**字面量**钉住。"""
+    assert DEFAULT_CSV_DIR.relative_to(BACKEND_DIR).as_posix() == "data/seed"
+    assert DEFAULT_DB_URL.endswith("/backend/pe.db")

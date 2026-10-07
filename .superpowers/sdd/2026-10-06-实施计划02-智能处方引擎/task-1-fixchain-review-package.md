# Task 1 收尾评审包 — fix 链 `ad1d190..6784d57`

> 生成方式：控制者用 python `subprocess` 跑 git，输出原样拼接（不经 PowerShell 管道，避免其自行加 CRLF）。**只含 fix 链**：Task 1 的主体（`1df5e8a`）已在 `task-1-review-package.md` 里评审过。


## git log --oneline

```
6784d57 test: Plan02 Task1 fix round 4，给两份 _package_of 补回归断言（Ruling 54）+ 更正「三条守卫」计数（Ruling 55）
73313f7 docs: Ruling 53 更正计划 02 正文 Global Constraints 的计数（六条 -> 十条，实数 10 条 bullet）
be0f1af test: Plan02 Task1 fix round 3，给两条架构守卫的 _absolute 补两份回归测试 + 更正 Ruling 42 的机制错话
1fa9941 fix: Plan02 Task1 fix round 2，修两条架构守卫 _absolute 的假绿（负数切片 + 忽略 names）+ 4 处散文错误
6a2938f docs: Plan02 Task1 fix round 1，修 4 条 Important 散文错误 + 两条架构守卫的相对导入放行
```


## git diff --stat

```
 ...244\204\346\226\271\345\274\225\346\223\216.md" |   2 +-
 backend/app/config.py                              |  11 +-
 backend/app/pipeline/daily.py                      |  32 +-
 backend/tests/architecture/test_domain_purity.py   | 432 +++++++++++++++++++--
 backend/tests/architecture/test_layering.py        | 299 +++++++++++++-
 backend/tests/db/test_models.py                    |  99 ++++-
 backend/tests/pipeline/test_daily.py               |  13 +-
 backend/tests/test_config.py                       |  30 ++
 8 files changed, 863 insertions(+), 55 deletions(-)
```


## git diff --name-status

```
M	"Document/2026-10-06-\345\256\236\346\226\275\350\256\241\345\210\22202-\346\231\272\350\203\275\345\244\204\346\226\271\345\274\225\346\223\216.md"
M	backend/app/config.py
M	backend/app/pipeline/daily.py
M	backend/tests/architecture/test_domain_purity.py
M	backend/tests/architecture/test_layering.py
M	backend/tests/db/test_models.py
M	backend/tests/pipeline/test_daily.py
A	backend/tests/test_config.py
```


## 生产代码命中（必须为空）

```
backend/app/config.py
backend/app/pipeline/daily.py
```


## git diff -U10

```diff
diff --git "a/Document/2026-10-06-\345\256\236\346\226\275\350\256\241\345\210\22202-\346\231\272\350\203\275\345\244\204\346\226\271\345\274\225\346\223\216.md" "b/Document/2026-10-06-\345\256\236\346\226\275\350\256\241\345\210\22202-\346\231\272\350\203\275\345\244\204\346\226\271\345\274\225\346\223\216.md"
index 4b8bf25..e6def17 100644
--- "a/Document/2026-10-06-\345\256\236\346\226\275\350\256\241\345\210\22202-\346\231\272\350\203\275\345\244\204\346\226\271\345\274\225\346\223\216.md"
+++ "b/Document/2026-10-06-\345\256\236\346\226\275\350\256\241\345\210\22202-\346\231\272\350\203\275\345\244\204\346\226\271\345\274\225\346\223\216.md"
@@ -3,21 +3,21 @@
 > **For agentic workers:** REQUIRED SUB-SKILL: 用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务实施本计划。步骤用 checkbox（`- [ ]`）语法便于跟踪。
 
 **Goal:** 把 Plan 01 产出的红黄绿分层结果，按「层 × 主导短板 × 体成分」装配成可复现、可审校、可被教师覆盖的 4 周运动处方，并接进每日批处理管道。
 
 **Architecture:** `app/domain/prescription/` 是无 I/O 的纯函数叶子层（匹配、强度换算、装配、安全后置、覆盖、触发判定），模板与动作等价映射是 `backend/data/` 下带版本号的静态 YAML（体育专家可独立审校），`app/pipeline/prescription_stage.py` 负责落库与幂等。处方**不每天重发**——只有 spec §5.2 的五个触发条件之一成立时才生成，而分层重算仍然每天跑。
 
 **Tech Stack:** Python 3.11.1、SQLAlchemy 2.1、SQLite（`PRAGMA foreign_keys=ON`）、PyYAML、pytest + pytest-cov。不引入新依赖。
 
 **Spec:** `Document/2026-09-28-体育闭环原型-设计spec.md` —— 本计划实现 **§4.4（处方数据模型）、§5.2（五个触发条件）、§7.1–7.5（智能处方层全部）、§8.4（骨架 + 周微调两层拆分）、§11.2（B 类算法降级）、§1.3（单人处方 p95 < 3 秒）、§12（`domain/` 100% 分支覆盖 + 黄金用例延伸到训练包）**。
 
-**上游状态（Plan 01 已交付，commit `1355541`）：** `453 passed / 0 failed`、`app/domain/` 分支覆盖 **100%**（392 stmts / 112 branch）、14 张表、13 例黄金用例、500 人 ×112 业务日整学期回放 28.4–34.0 s。**执行账本**：`.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md`（234 条裁定、47 条硬规矩，**gitignore 不入库**）。本计划的每个 Task 都受那 47 条硬规矩约束，其中对本计划最要命的六条见 Global Constraints。
+**上游状态（Plan 01 已交付，commit `1355541`）：** `453 passed / 0 failed`、`app/domain/` 分支覆盖 **100%**（392 stmts / 112 branch）、14 张表、13 例黄金用例、500 人 ×112 业务日整学期回放 28.4–34.0 s。**执行账本**：`.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md`（234 条裁定、47 条硬规矩，**gitignore 不入库**）。本计划的每个 Task 都受那 47 条硬规矩约束，其中对本计划最要命的十条见 Global Constraints。
 
 ---
 
 ## Global Constraints
 
 - **`app/domain/` 无任何 I/O**：不得 import `sqlalchemy` / `fastapi` / `requests` / `httpx` / `pydantic_settings` / `random`；不得出现 `datetime.now` / `date.today` / `time.time` / `open(`；不得出现 `read_csv` / `read_text` / `Path(` / `__file__` / `json.load` / `os.listdir` / `import os`。**时间与随机数一律由调用方注入**，参考表一律由 `app/refdata.py` 加载后**作为参数传入**。守卫是 `tests/architecture/test_domain_purity.py`（Task 1 会把它从 deny-list 改成 allow-list）。
 - **`app/domain/` 分支覆盖 100%**（spec §12）。验收命令**必须带 `--cov-branch`**：`cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing` → `Miss 0 / BrPart 0`。
 - **单一所有者**：任何常量/词表/权重只允许有一个住址。Plan 01 为此立过 6 条裁定（Ruling 35/36/63/152/156/190）。本计划新增的 `ITEM_BUCKET` 消费、模板维度词表、`impact_level` 词表、`exercise_ref` 词表都必须指向唯一所有者，且**各有一条漂移测试**。
 - **断言两侧不得同源**（硬规矩 #35）：期望值一律**字面写在测试里**，不从被测常量读回来跟自己比。Plan 01 因此吃过三次亏（Ruling 166/186/216-M3）。
 - **散文必须带口径**（硬规矩 #19/#20/#25/#29/#36/#39/#43）：注释与 docstring 里出现的每个数字都要能指到产生它的那条命令；每个因果机制都要附 `文件:行 + 引文`；尺寸/时长/速率必须带单位与进制、带 n 与区间；**不得印未经多样本验证的概率模型**；凡写下测量条件，必须同时写「哪条测试会在它失效时变红」，写不出来就标「历史实测，不被守卫」。
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
index cc4fff6..cb5c559 100644
--- a/backend/app/pipeline/daily.py
+++ b/backend/app/pipeline/daily.py
@@ -191,29 +191,53 @@ def _fitness_batch(
 
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
+    基线 **20.48 / 20.85 s**（均值 20.66、组内极差 20.85 − 20.48 = 0.37 s；两个样本
+    各自只记到百分位，故极差也只能给到这个精度），本 Task 之后
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
index fdf9f29..29e3ca0 100644
--- a/backend/tests/architecture/test_domain_purity.py
+++ b/backend/tests/architecture/test_domain_purity.py
@@ -1,28 +1,36 @@
 """domain 层纯净性架构约束的可执行检查（spec §3.3、Plan 02 Global Constraints）。
 
 spec §3.3 规定 ``app/domain/`` 禁止任何 I/O：不得 import 数据库 / HTTP 框架，不得调用
 时钟、文件与无种子随机数接口。时间与随机数一律由调用方注入，参考表一律由
 :mod:`app.refdata` 加载后**作为参数传入**（Plan01 Ruling 15）。这是分层引擎与处方引擎
 可单测、可复现的前提，也是 spec §12「domain 分支覆盖 100%」能成立的前提。
 
-三条守卫，Plan 02 Task 1 全部改写过一次，改动理由各写在对应测试的 docstring 里：
+本文件有 **4 个 ``test_*``**：**三条架构守卫** + 一条**辅助函数的单元测试**
+（``test_absolute_folding_matches_resolve_name``，测的是 ``_absolute`` / ``_package_of``
+这两个辅助函数，**不是第四条守卫**；Plan02 Ruling 46/54）。三条守卫 Plan 02 Task 1 全部
+改写过一次，改动理由各写在对应测试的 docstring 里：
 
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
@@ -78,58 +86,349 @@ def _assert_not_empty(scanned: list[pathlib.Path]) -> None:
     ``derive`` / ``indicators`` / ``percentile`` / ``stratify`` / ``tables``；命令见
     :func:`test_domain_imports_stay_within_the_allow_list` 的 docstring）。取 5 是给
     「两个模块合并」这类合法重构留一格余量，同时仍能挡住「整层被搬空」。
     """
     assert len(scanned) >= 5, (
         f"只扫到 {len(scanned)} 个 .py，app/domain 可能被搬空，三条守卫会一起假绿"
     )
 
 
 def _imported_modules(tree: ast.AST):
-    """yield ``(lineno, 完整模块串, 相对层级)``；``ast.walk`` 覆盖函数内导入。"""
+    """yield ``(lineno, 完整模块串, 相对层级, 被导入名)``；``ast.walk`` 覆盖函数内导入。
+
+    第 4 项只在 ``level > 0`` **且** ``module`` 为空时非空——那一档被导入的模块名住在
+    ``node.names`` 里（``from .. import seed``）。**一个节点可以带多个名字**，而
+    ``from .. import seed, pipeline`` 导入的是**两个**模块，故这一档逐个 ``names`` yield
+    两条、由 :func:`_absolute` 各自折算；只 yield 一条就会把 ``app.seed`` 折成 ``app``
+    （Plan02 Ruling 36）。真仓里就有这一形状：``app/db/models/__init__.py:74`` 的
+    ``from . import feedback, prescription``。
+    """
     for node in ast.walk(tree):
         if isinstance(node, ast.Import):
             for alias in node.names:
-                yield node.lineno, alias.name, 0
+                yield node.lineno, alias.name, 0, ""
         elif isinstance(node, ast.ImportFrom):
-            yield node.lineno, (node.module or ""), node.level
+            if node.level and not node.module:
+                for alias in node.names:
+                    yield node.lineno, "", node.level, alias.name
+            else:
+                yield node.lineno, (node.module or ""), node.level, ""
 
 
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
+def _absolute(module: str, level: int, package: tuple[str, ...], name: str = "") -> str | None:
+    """把 ``ast.ImportFrom`` 折算成**绝对模块串**；上溯到顶层包 ``app`` 之外返回 ``None``。
+
+    ``level == 0`` 本来就是绝对串。``level == 1`` 落在 ``package`` 自己这一层，
+    ``level == 2`` 上溯一层，依此类推——与 :func:`importlib.util.resolve_name` 同口径。
+    ⚠️ 它的第二个参数是 ``__package__``、即**包名**，不是模块名。两行都是本机 Python
+    3.11.1 的实跑值（Plan02 Ruling 37）::
+
+        resolve_name("..seed.generate", "app.domain")     -> "app.seed.generate"      # 包名，对
+        resolve_name("..seed.generate", "app.domain.ind") -> "app.domain.seed.generate"  # 模块名，错
+
+    第二行是 fix round 1 的 docstring 原来举的例子。这一段是 :func:`_package_of` 的**规格
+    说明**，所以一个假举例不是笔误：谁按它去「对齐」代码（让 ``_package_of`` 返回
+    ``("app", "domain", "ind")``），``app/domain/x.py`` 里的 ``from ..seed import generate``
+    就会折成 ``app.domain.seed``（**不是** ``app.domain.seed.generate``：``generate`` 住在
+    ``node.names`` 里、不进折算串，Plan02 Ruling 36；本机 Python 3.11.1 实跑
+    ``_absolute("seed", 2, ("app", "domain", "ind"))`` -> ``'app.domain.seed'``、
+    ``_is_allowed('app.domain.seed')`` -> ``True``）、命中白名单前缀 ``app.domain.`` →
+    **守卫当场假绿**
+    （硬规矩 #52：形如 ``f(x) == y`` 的举例必须是真跑过的输出）。
+
+    ``name`` 是 ``node.names`` 里的**一个**被导入名，只在 ``module`` 为空时用得上：
+    ``from .. import seed`` 的 AST 是 ``ImportFrom(module=None, level=2,
+    names=[alias("seed")])``，被导入的模块名住在 ``names`` 里。只看 ``module`` 会把它折成
+    ``app``、丢掉 ``.seed``，而 ``resolve_name("..seed", "app.pipeline")`` -> ``"app.seed"``
+    → 不在白名单 → 本该 offender。**一个节点可以带多个名字**（``from .. import seed,
+    pipeline`` 导入的是两个模块），故由 :func:`_imported_modules` 逐个展开成多次调用，
+    本函数一次只折一个（Plan02 Ruling 36）。
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
+    判 offender、**不是「不管」**：Python 3.11.1 运行时会抛
+    ``ImportError: attempted relative import beyond top-level package``（合成树里真跑一遍
+    ``import app.domain.x`` 的实测；:func:`importlib.util.resolve_name` 对同一输入抛同一个
+    异常），但那是运行期的事，静态守卫不拦的话「写一句永远跑不到的 import」也能让本测试
+    全绿。**而这一档必须真的返回 ``None``**：``level - 1 > len(package)`` 时切片末端是
+    **负数**，Python 会从尾部切出一个非空 anchor（``("app", "domain")[: 2 - 3]`` ==
+    ``("app",)``），于是越界的 import 被折成一个**更浅的错误绝对串**——
+    ``app/domain/x.py`` 里的 ``from ....domain import tables``（``level == 4``、包深 2）
+    会折成 ``app.domain``，而 ``_is_allowed`` 的第一支正是 ``module == ALLOWED_PACKAGE``——
+    **命中的是「相等」这一支，不是 ``startswith(ALLOWED_PACKAGE + ".")`` 那一支**（本机
+    Python 3.11.1 实跑：``"app.domain" == ALLOWED_PACKAGE`` -> ``True``、
+    ``"app.domain".startswith(ALLOWED_PACKAGE + ".")`` -> ``False``；Plan02 Ruling 42），
+    于是变成真绿；而 ``resolve_name``
+    对同一输入抛 ``ImportError``（Plan02 Ruling 35）。
+    """
+    if level == 0:
+        return module
+    if level - 1 > len(package):
+        # 越界档：不设这一行，负数切片会从尾部切出非空 anchor、把越界折成更浅的错误绝对串
+        return None
+    anchor = package[: len(package) - (level - 1)]
+    if not anchor:
+        return None
+    tail = module or name
+    return ".".join(anchor + ((tail,) if tail else ()))
+
+
+def _is_allowed(module: str) -> bool:
+    """一个**绝对**模块串是否在白名单内（相对导入先经 :func:`_absolute` 折算）。"""
     if module == ALLOWED_PACKAGE or module.startswith(ALLOWED_PACKAGE + "."):
         return True
     return module in ALLOWED_MODULES
 
 
+def test_absolute_folding_matches_resolve_name():
+    """:func:`_absolute` 的折算必须与 :func:`importlib.util.resolve_name` 逐格相同。
+
+    **判据为什么锚在 ``resolve_name`` 上、而不是锚在一张期望值表上**：表是某个人某一次跑
+    出来的结果，抄进测试就成了「期望值从被测对象的同一口径读回来」（硬规矩 #35 的形状）；
+    ``resolve_name`` 是 Python 自己对相对导入的定义。故本测试**一个折算结果都不写死**：每格
+    现场调一次 ``resolve_name``，它对同一输入抛 ``ImportError`` 的那一档期望值就是 ``None``
+    （越界档，Plan02 Ruling 35）。
+
+    **守的是 fix round 2 修掉、而此前仓库里没有任何断言看着的两个 bug**（Plan02 Ruling 46：
+    谁删掉 ``if level - 1 > len(package): return None``，479 条全绿）：
+
+    * **越界档**：删掉那一行，负数切片会从尾部切出非空 anchor，
+      ``("domain", 4, ("app", "domain"), "tables")`` 折成 ``app.domain`` 而不是 ``None``
+      → 本测试红。
+    * **``module`` 为空时接 ``node.names`` 里的那个名字**：把 ``tail = module or name`` 改回
+      ``tail = module``，``("", 2, ("app", "pipeline"), "seed")`` 折成 ``app`` 而不是
+      ``app.seed`` → 本测试红。
+    * **一个节点带 N 个名字要展开成 N 条**（``from .. import seed, pipeline`` 导入的是两个
+      模块，Plan02 Ruling 36）→ 末尾那一段红。
+
+    三条的复现命令是同一条（在 ``backend/`` 下）：把对应改动打回本文件的 ``_absolute`` /
+    ``_imported_modules``，再跑 ``python -m pytest tests/architecture -q``。本轮实测三种变异
+    各让**本文件这一条**红、而 :mod:`tests.architecture.test_layering` 那一条**保持绿**——
+    两份 ``_absolute`` 互相独立，这正是硬规矩 #51 要两份回归测试的原因。断言里印出来的折算值
+    也是实跑的：越界档报 ``_absolute('domain', 4, ('app', 'domain'), 'tables') =
+    'app.domain'``（而 ``resolve_name('....domain', 'app.domain')`` 抛 ``ImportError``）、
+    ``tail = module`` 报 ``_absolute('', 2, ('app', 'pipeline'), 'seed') = 'app'``（正确答案
+    ``'app.seed'``）、展开档报 ``['app.seed'] != ['app.seed', 'app.pipeline']``。
+
+    **绿档同时在场**（硬规矩 #50：只放红档会得到一条过紧的守卫）：``level == 1`` 的包内导入
+    折成 ``app.domain.tables``，必须仍被 :func:`_is_allowed` 放行——Task 2 起
+    ``app/domain/prescription/`` 子包里的 ``from ..indicators import X`` 正是这一档。
+    ⚠️ 矩阵第 7 行 ``("", 2, ("app", "db", "models"), "seed")`` 折成 ``app.db.seed``，在
+    **本文件**的白名单下是 RED、在 :mod:`tests.architecture.test_layering` 的 ``app.seed``
+    前缀下却是 GREEN：**折算串错了不等于判定错了**（Plan02 Ruling 41），故两份回归测试的
+    期望颜色列**不相同**，这不是抄错。
+
+    **本测试守不住什么**（硬规矩 #39）：
+
+    * :func:`_package_of` 由本测试**末尾那一段**看着（Plan02 Ruling 54），但**只在枚举到
+      的那 4 个形状上**：``app/db/models/organisation.py`` 与 ``app/db/models/__init__.py``
+      （包深 3；两者必须给出**同一个**包——这一格正是 ``parts[:-1]`` 这个写法的全部理由）、
+      ``app/domain/indicators.py``（包深 2）、``app/domain/prescription/match.py``（包深 3，
+      Task 2 才会出现的形状；``_package_of`` 是纯路径运算、不碰文件系统，故可以先断言）。
+      **没枚举进去的包深（包深 4 及更深）不被覆盖**；上面那 11 格矩阵的 ``package`` 入参
+      仍是**手写的**，故矩阵与末尾那一段互不覆盖、谁也不替代谁。
+    * 它不扫真仓文件，故「白名单取值本身对不对」仍只由
+      :func:`test_domain_imports_stay_within_the_allow_list` 看着，两条判据互不覆盖。
+    * 矩阵是有限的 11 格：更深的包、更大的 ``level`` 没列进去就不被覆盖。判据既然是
+      ``resolve_name``，往 ``cases`` 里加一行就是加一格覆盖，不必动断言。
+    """
+    # 就地 import：模块级 import 会改动本文件的 <module-level>，故这条测试自 fix round 3
+    # 起就把 import 留在函数体内、改动面也一直钉死在「这一条测试函数 + docstring」
+    # 之内（Plan02 Ruling 46/57）。
+    import importlib.util
+
+    #: ``(module, level, package, name, 期望颜色)``。以 **AST 形状**为参数，不用「``from …``
+    #: 的字面写法」当唯一标识——同一句写法在不同包深下折算到不同的地方（Plan02
+    #: Ruling 41/45）。期望颜色是**判据**（本文件的白名单语义），不是折算结果。
+    cases = [
+        # level == 0：本来就是绝对串，原样返回
+        ("app.seed.generate", 0, ("app", "domain"), "", "RED"),
+        # level == 1：包内合法导入（绿档，硬规矩 #50 的 ②）
+        ("tables", 1, ("app", "domain"), "", "GREEN"),
+        ("", 1, ("app", "domain"), "tables", "GREEN"),
+        # level == 2：跨包指向 app.seed，真 offender
+        ("seed.generate", 2, ("app", "pipeline"), "", "RED"),
+        # module 为空：被导入的模块名住在 node.names 里（Ruling 36）
+        ("", 2, ("app", "pipeline"), "seed", "RED"),
+        ("", 2, ("app", "db"), "seed", "RED"),
+        ("", 2, ("app", "db", "models"), "seed", "RED"),
+        ("", 2, ("app", "domain"), "seed", "RED"),
+        # 越界档：resolve_name 抛 ImportError，_absolute 必须返回 None（Ruling 35）
+        ("seed", 5, ("app", "db", "models"), "generate", "RED"),
+        ("domain", 4, ("app", "domain"), "tables", "RED"),
+        # level - 1 == len(package)：由 `not anchor` 那一行兜住，同样必须 None
+        ("seed", 3, ("app", "domain"), "generate", "RED"),
+    ]
+    offenders: list[str] = []
+    for module, level, package, name, color in cases:
+        rel = "." * level + (module or name)
+        pkg = ".".join(package)
+        try:
+            want = importlib.util.resolve_name(rel, pkg)
+        except ImportError:
+            want = None
+        got = _absolute(module, level, package, name)
+        if got != want:
+            offenders.append(
+                f"_absolute({module!r}, {level}, {package!r}, {name!r}) = {got!r}，"
+                f"而 resolve_name({rel!r}, {pkg!r}) = {want!r}"
+            )
+        verdict = "RED" if got is None or not _is_allowed(got) else "GREEN"
+        if verdict != color:
+            offenders.append(
+                f"_absolute({module!r}, {level}, {package!r}, {name!r}) = {got!r} "
+                f"判成 {verdict}、期望 {color}"
+            )
+    assert offenders == [], (
+        "_absolute 与 importlib.util.resolve_name 不一致、或某一档颜色不对"
+        "（Plan02 Ruling 35/36/41）：\n" + "\n".join(offenders)
+    )
+
+    # Ruling 36 的另一半：一个 ImportFrom 节点带两个名字，必须展开成两条、各自折算。
+    tree = ast.parse("from .. import seed, pipeline\n")
+    package = ("app", "pipeline")
+    got = [_absolute(module, level, package, name)
+           for _lineno, module, level, name in _imported_modules(tree)]
+    want = [importlib.util.resolve_name(f"..{alias}", ".".join(package))
+            for alias in ("seed", "pipeline")]
+    assert got == want, f"一名一条的展开失效: {got} != {want}"
+
+    # ---------------------------------------------------------------- Ruling 54
+    # 上面 11 格的 package 入参是**手写的**，故 _package_of 被改坏时它们照样全绿；而它是
+    # 两条守卫共同的假绿入口（Plan02 Ruling 37/54）。_package_of 是纯路径运算、不碰文件
+    # 系统，故最后一格可以写 Task 2 才会出现的形状。
+    pkg_cases = [
+        # (backend/ 下的相对路径, 正确的**包**, parts[:-1] 写成 parts 时会得到的**模块路径**)
+        ("app/db/models/organisation.py", ("app", "db", "models"),
+         ("app", "db", "models", "organisation")),
+        # __init__.py 与同目录的普通模块给出**同一个**包：这一格是 parts[:-1] 的全部理由
+        ("app/db/models/__init__.py", ("app", "db", "models"),
+         ("app", "db", "models", "__init__")),
+        ("app/domain/indicators.py", ("app", "domain"), ("app", "domain", "indicators")),
+        # Task 2 会新建 app/domain/prescription/ 子包（今天不存在）
+        ("app/domain/prescription/match.py", ("app", "domain", "prescription"),
+         ("app", "domain", "prescription", "match")),
+    ]
+    pkg_offenders: list[str] = []
+    for rel, want_pkg, module_path in pkg_cases:
+        got_pkg = _package_of(BACKEND / rel)
+        if got_pkg != want_pkg:
+            pkg_offenders.append(
+                f"_package_of(BACKEND / {rel!r}) = {got_pkg!r}，应为**包** {want_pkg!r}"
+            )
+        if got_pkg == module_path:
+            pkg_offenders.append(
+                f"_package_of(BACKEND / {rel!r}) = {got_pkg!r} 是**模块路径**、不是包"
+                "（parts[:-1] 被写成了 parts）"
+            )
+    # 后果也要能跑、不能只写在断言消息里：把 _package_of 的输出直接喂给 _absolute，
+    # 结果仍须与 resolve_name 逐字相同（判据同上，锚在 Python 自己的语义上）。
+    for rel, level, module, want_pkg in (
+            ("app/domain/indicators.py", 2, "seed", ("app", "domain")),
+            ("app/db/models/organisation.py", 3, "seed", ("app", "db", "models"))):
+        rel_import = "." * level + module
+        pkg_str = ".".join(want_pkg)
+        got = _absolute(module, level, _package_of(BACKEND / rel))
+        want = importlib.util.resolve_name(rel_import, pkg_str)
+        if got != want:
+            pkg_offenders.append(
+                f"{rel} 里的 from {rel_import} import …：用 _package_of 的结果折算得到 "
+                f"{got!r}，而 resolve_name({rel_import!r}, {pkg_str!r}) = {want!r}"
+            )
+    assert pkg_offenders == [], (
+        "_package_of 返回的不是**包**（Plan02 Ruling 37/54）：parts[:-1] 写成 parts 会让"
+        "它返回**模块路径**，于是 app/domain/x.py 里的 from ..seed import … 折成 "
+        "app.domain.seed、命中白名单前缀 app.domain. → 本文件的守卫假绿（test_layering.py "
+        "那一份同理：app/db/models/x.py 里的 from ...seed import … 折成 app.db.seed、不再"
+        "以 app.seed 开头），而在本段断言加上之前，这么改一次全量测试都照样通过：\n"
+        + "\n".join(pkg_offenders)
+    )
+
+
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
+      开始正常出现，「一律放行」的写法会跟着变成真漏洞。折算之后（⚠️ **同一句写法在不同
+      文件深度解析到不同的地方**，故下面每条都带主语；合成树里逐条写入探针文件后直接
+      调用本测试函数，颜色是实跑的，Plan02 Ruling 39-3）：
+
+      * **扁平的** ``app/domain/x.py``（包深 2）：``from ..seed import generate`` 解析到
+        ``app.seed.generate`` → **offender**；``from ...seed import generate`` 已经越界，
+        :func:`_absolute` 返回 ``None`` → **同样 offender**。
+      * ``app/domain/sub/x.py``（包深 3）：``from ..tables import X`` 解析到
+        ``app.domain.tables`` → **合法**；而**同一句** ``from ..seed import generate`` 在
+        这个深度解析到的是 ``app.domain.seed.generate``、命中白名单前缀 ``app.domain.`` →
+        **不是 offender**（这一档要到 ``app.seed`` 得写 ``from ...seed import generate``，
+        即 ``level == 3``，它才是 offender）。
 
     **落地当天的 import 全貌**（AST 亲扫，这就是白名单取值的实测依据；命令::
 
         python -c "import ast,pathlib; [print(p.name, sorted({a.name for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.Import) for a in n.names} | {n.module for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.module})) for p in sorted(pathlib.Path('app/domain').rglob('*.py'))]"
 
     在 ``backend/`` 下跑，基线 ``e26347f``）::
 
         __init__.py      []
         derive.py        ['app.domain.indicators', 'app.domain.percentile', 'dataclasses', 'enum']
         indicators.py    ['app.domain.tables', 'enum']
@@ -140,38 +439,64 @@ def test_domain_imports_stay_within_the_allow_list():
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
-        for lineno, module, level in _imported_modules(tree):
-            if not _is_allowed(module, level):
-                offenders.append(f"{py.name}:{lineno}: {module or '<空模块名>'}")
+        for lineno, module, level, name in _imported_modules(tree):
+            absolute = _absolute(module, level, package, name)
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
+    还原不出点号串的形态一律返回 ``None``，本守卫因此**放过**它们。四种形态的
+    ``node.func`` 是什么，本机 Python 3.11.1 实跑（``ast.parse(s).body[0].value.func``）::
+
+        f()()                                   ast.Call
+        table[0]()                              ast.Subscript
+        getattr(x, "now")()                     ast.Call
+        __import__("datetime").datetime.now()   ast.Attribute(value=ast.Attribute(value=ast.Call))
+
+    本函数只沿 ``ast.Attribute`` 下溯、走到 ``ast.Name`` 才收工，故上面四种都还原不出来。
+    ``eval("…")`` 是**另一种**放过法：它的 ``node.func`` 是 ``ast.Name(id="eval")``、点号串
+    还原得出 ``"eval"``，只是 ``eval`` 不在 :data:`FORBIDDEN_CALLS` 里。
+
+    ⚠️ 这一段此前写着「对 ``datetime`` / ``time`` / ``builtins`` 那不是漏洞：拿到这些对象的
+    **唯一途径是 import**，而 import 已经被 allow-list 挡在门外」——**那句是假的**，
+    是个全称断言而它有反例：``__import__`` 自己就是**内置名**、不需要 import，而 G1 只匹配
+    ``ast.Import`` / ``ast.ImportFrom`` 两种节点，于是 ``__import__("datetime").datetime.now()``
+    **三条守卫全绿**（本机 Python 3.11.1 实跑；行与颜色见
+    :func:`test_domain_has_no_clock_or_file_access` docstring 里那张 G1/G2/G3 表的第 8–14 行）。
+    ``open`` 同理，也是内置名。**正确口径是：凡 :func:`_dotted` 还原不出点号串的调用形态，
+    一律不被本守卫覆盖**，与那个对象是怎么拿到的无关。与
+    :func:`test_domain_has_no_clock_or_file_access` docstring 里那条「别名间接不被守卫」
+    是同一个缺口，两处一起看才是本守卫的完整能力边界（硬规矩 #39）。
     """
     parts: list[str] = []
     while isinstance(node, ast.Attribute):
         parts.append(node.attr)
         node = node.value
     if not isinstance(node, ast.Name):
         return None
     parts.append(node.id)
     return ".".join(reversed(parts))
 
@@ -186,30 +511,79 @@ def _hit_forbidden_call(dotted: str) -> str | None:
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
+        __import__("datetime").datetime.now()             GREEN          GREEN             GREEN
+        __import__("os").listdir(".")                     GREEN          GREEN             GREEN
+        __import__("builtins").open("x")                  GREEN          GREEN             GREEN
+        getattr(__import__("datetime"), "datetime").now()  GREEN          GREEN             GREEN
+        eval("__import__('datetime').datetime.now()")     GREEN          GREEN             GREEN
+        def _f(x): return getattr(x, "now")()             GREEN          GREEN             GREEN
+        def _f(table): return table[0]()                  GREEN          GREEN             GREEN
+
+    第 1–7 行是 fix round 1 那次跑的结果，第 8–14 行是 **fix round 2 新增**（Plan02
+    Ruling 38）；本轮把 14 行**全部重跑了一遍**，前 7 行的颜色逐字复现。
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
+
+    ⚠️ **「拿到工具必经 import」也不成立**（上表第 8–14 行，Plan02 Ruling 38）：
+    ``__import__`` / ``eval`` / ``getattr`` 三个**内置名**都能在不写一条 ``ast.Import`` 的
+    前提下拿到 ``datetime`` / ``os`` / ``builtins``，于是 G1 一声不响；G2 对
+    ``__import__(…).datetime.now()`` / ``getattr(x, "now")()`` / ``table[0]()`` 还原不出
+    点号串（见 :func:`_dotted`），对 ``eval(…)`` 还原得出 ``"eval"``、只是它不在
+    :data:`FORBIDDEN_CALLS` 里；G3 的子串表里既没有 ``__import__`` 也没有 ``eval``——
+    三条守卫**全绿**。
+
+    ``__import__("os").listdir(".")`` 这一行尤其值得记住：``os.listdir`` 与 ``import os``
+    **两个子串都在** :data:`FORBIDDEN_IO` 里，而写成这个形状后源码里**一个都不出现**
+    （本机实跑：该探针命中的 ``FORBIDDEN_IO`` 子串数 = 0；对照组 ``import os`` 换行
+    ``os.listdir(".")`` 命中 2 个），于是第三条子串守卫也一声不响——「不许读盘」这条立意
+    被完整绕过。这七行不是待修的漏洞清单，而是本条守卫的**能力边界**：它守的是「直白地
+    写出 ``datetime.now()`` / ``open()`` / ``os.listdir()``」，不守任何需要还原、求值或
+    别名追踪才能看清的形态。要堵这一族就得把 ``__import__`` / ``eval`` / ``getattr`` 这些
+    内置名本身列进封禁，代价是 domain 里连一个正常的 ``getattr(obj, "name", default)``
+    都写不了——本仓不做，但必须写清楚（硬规矩 #39）。
 
     ``open`` 从旧的 ``\\bopen\\s*\\(`` 正则并进 :data:`FORBIDDEN_CALLS`：它本来也是
     一次 ``ast.Call``，两套机制守同一件事只会让人分不清哪条是真相。
 
     ⚠️ **本条今天与 allow-list 高度重叠**：``datetime`` / ``time`` 都不在白名单里，
     所以 domain 根本 import 不到它们；``open`` 是内置名，不需要 import，故它是本条
     **唯一独立生效**的封禁项。保留整条的理由是纵深：白名单是「不许拿到工具」，本条是
     「不许做这个动作」——将来有人为了别的原因把 ``datetime`` 加进白名单（一个完全可能
     的合法请求，比如要一个 ``date`` 类型标注），本条仍然挡着 ``datetime.now()``。
     """
diff --git a/backend/tests/architecture/test_layering.py b/backend/tests/architecture/test_layering.py
index ad1d6f1..ad46a25 100644
--- a/backend/tests/architecture/test_layering.py
+++ b/backend/tests/architecture/test_layering.py
@@ -60,62 +60,337 @@ FORBIDDEN_PREFIX = "app.seed"
 
 
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
+def _absolute(module: str, level: int, package: tuple[str, ...], name: str = "") -> str | None:
+    """把 ``ast.ImportFrom`` 折算成**绝对模块串**；上溯到顶层包 ``app`` 之外返回 ``None``。
+
+    与 :func:`importlib.util.resolve_name` 同口径。⚠️ 它的第二个参数是 ``__package__``、
+    即**包名**，不是模块名。两行都是本机 Python 3.11.1 的实跑值（Plan02 Ruling 37）::
+
+        resolve_name("...seed.generate", "app.db.models")              -> "app.seed.generate"     # 包名，对
+        resolve_name("...seed.generate", "app.db.models.organisation") -> "app.db.seed.generate"  # 模块名，错
+
+    第二行是 fix round 1 的 docstring 原来举的例子。这一段是 :func:`_package_of` 的**规格
+    说明**，所以一个假举例不是笔误：谁按它去「对齐」代码（让 ``_package_of`` 把模块名那段
+    也返回），``app/db/models/x.py`` 里的 ``from ...seed import …`` 就会折成 ``app.db.seed``、
+    **不再以 ``app.seed`` 开头** → 本守卫当场假绿（硬规矩 #52）。
+
+    ``name`` 是 ``node.names`` 里的**一个**被导入名，只在 ``module`` 为空时用得上：
+    ``from .. import seed`` 的 AST 是 ``ImportFrom(module=None, level=2,
+    names=[alias("seed")])``，被导入的模块名住在 ``names`` 里。只看 ``module`` 会把它折成
+    ``app``、丢掉 ``.seed``，而 ``resolve_name("..seed", "app.pipeline")`` -> ``"app.seed"``
+    → :func:`_is_forbidden` 命中 → **本该 offender、却是绿的**。多个名字由
+    :func:`_imported_modules` 逐个展开，本函数一次只折一个（Plan02 Ruling 36）。
+    ⚠️ **折算串错了不等于判定错了**：``app/db/models/x.py``（包深 3）的 ``from .. import
+    seed`` 上溯一层到 ``app.db``，正确答案是 ``app.db.seed``，它**本来就不以 ``app.seed``
+    开头**，故这一例的判定一直是绿、修完仍是绿，变的只是折算出来的那个串（此前是
+    ``app.db``）。同一句写在 ``app/pipeline/x.py`` 或 ``app/db/x.py``（包深 2）里才指向
+    ``app.seed``、才必须变红（Plan02 Ruling 41）。
+
+    ``None`` 的那一档（如 ``app/pipeline/x.py`` 里写 ``from ...seed import …``）由调用方
+    直接判 offender：Python 3.11.1 运行时会抛
+    ``ImportError: attempted relative import beyond top-level package``（合成树里真跑一遍
+    ``import app.domain.x`` 的实测；:func:`importlib.util.resolve_name` 抛同一个异常），
+    但静态守卫不拦的话「写一句永远跑不到的 import」也能让本测试全绿。**而这一档必须真的
+    返回 ``None``**：``level - 1 > len(package)`` 时切片末端是**负数**，Python 会从尾部切出
+    一个非空 anchor（``("app", "db", "models")[: 3 - 4]`` == ``("app", "db")``），于是
+    ``app/db/models/x.py`` 里的 ``from .....seed import generate``（``level == 5``、包深 3）
+    被折成 ``app.db.seed``、**不以 ``app.seed`` 开头 → 假绿**，而 ``resolve_name`` 对同一
+    输入抛 ``ImportError``（Plan02 Ruling 35）。
+    """
+    if level == 0:
+        return module
+    if level - 1 > len(package):
+        # 越界档：不设这一行，负数切片会从尾部切出非空 anchor、把越界折成更浅的错误绝对串
+        return None
+    anchor = package[: len(package) - (level - 1)]
+    if not anchor:
+        return None
+    tail = module or name
+    return ".".join(anchor + ((tail,) if tail else ()))
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
+
+    那 12 条里有 **1 条**是 ``module`` 为空的形状：``app/db/models/__init__.py:74`` 的
+    ``from . import feedback, prescription``（上面那条命令打出来的第 7 行是
+    ``app/db/models/__init__.py 74 1 None``）。它是**一个节点、两个名字、两个模块**，故
+    下面按 ``names`` 逐个 yield、折算成 ``app.db.models.feedback`` 与
+    ``app.db.models.prescription`` 两条；此前只 yield 一条 ``app.db.models``（Plan02
+    Ruling 36）。两条都不以 ``app.seed`` 开头，**判定不变、仍然绿**。
     """
     for node in ast.walk(tree):
         if isinstance(node, ast.Import):
             for alias in node.names:
                 yield node.lineno, alias.name
         elif isinstance(node, ast.ImportFrom):
-            if node.level or not node.module:
-                continue
-            yield node.lineno, node.module
+            if node.level and not node.module:
+                # `from .. import seed, pipeline` 是一个节点导入两个模块，必须逐个折算
+                for alias in node.names:
+                    yield node.lineno, _absolute("", node.level, package, alias.name)
+            else:
+                yield node.lineno, _absolute(node.module or "", node.level, package)
 
 
 def _is_forbidden(module: str) -> bool:
     """按**完整模块串**判前缀，且只在 ``.`` 边界上匹配。
 
     边界是必需的：裸 ``startswith("app.seed")`` 会把 ``app.seedling`` 这类
     （今天不存在、但将来可能有的）合法模块误判成 offender。
     """
     return module == FORBIDDEN_PREFIX or module.startswith(FORBIDDEN_PREFIX + ".")
 
 
+def test_absolute_folding_matches_resolve_name():
+    """:func:`_absolute` 的折算必须与 :func:`importlib.util.resolve_name` 逐格相同。
+
+    **这一条与 :mod:`tests.architecture.test_domain_purity` 里的同名测试是「两份重复守卫的
+    两份回归测试」**（硬规矩 #51）：``_absolute`` 在两个文件里各有一份、逐字相同，故回归
+    测试也必须各有一份——只留一份的话，另一份 ``_absolute`` 被改坏时**没有任何测试会红**。
+    下面「复现命令」那一段给了实测：只变异本文件的 ``_absolute``，purity 那条**保持绿**。
+
+    **判据锚在 ``resolve_name`` 上、不锚在期望值表上**：表是某个人某一次跑出来的结果，抄进
+    测试就成了「期望值从被测对象的同一口径读回来」（硬规矩 #35 的形状）；``resolve_name``
+    是 Python 自己对相对导入的定义。故本测试**一个折算结果都不写死**：每格现场调一次
+    ``resolve_name``，它对同一输入抛 ``ImportError`` 的那一档期望值就是 ``None``（越界档，
+    Plan02 Ruling 35）。
+
+    **守的是 fix round 2 修掉、而此前仓库里没有任何断言看着的两个 bug**（Plan02 Ruling 46：
+    谁删掉 ``if level - 1 > len(package): return None``，479 条全绿）：
+
+    * **越界档**：删掉那一行，负数切片会从尾部切出非空 anchor，
+      ``("seed", 5, ("app", "db", "models"), "generate")`` 折成 ``app.db.seed`` 而不是
+      ``None`` → 本测试红。
+    * **``module`` 为空时接 ``node.names`` 里的那个名字**：把 ``tail = module or name`` 改回
+      ``tail = module``，``("", 2, ("app", "pipeline"), "seed")`` 折成 ``app`` 而不是
+      ``app.seed`` → 本测试红。
+    * **一个节点带 N 个名字要展开成 N 条**（``from .. import seed, pipeline`` 导入的是两个
+      模块，Plan02 Ruling 36）→ 末尾那一段红。
+
+    三条的复现命令是同一条（在 ``backend/`` 下）：把对应改动打回本文件的 ``_absolute`` /
+    ``_imported_modules``，再跑 ``python -m pytest tests/architecture -q``。本轮实测三种变异
+    各让**本文件这一条**红、而 :mod:`tests.architecture.test_domain_purity` 那一条**保持绿**——
+    两份 ``_absolute`` 互相独立，这正是硬规矩 #51 要两份回归测试的原因。断言里印出来的折算值
+    也是实跑的：越界档报 ``_absolute('seed', 5, ('app', 'db', 'models'), 'generate') =
+    'app.db.seed'``（而 ``resolve_name('.....seed', 'app.db.models')`` 抛 ``ImportError``）、
+    ``tail = module`` 报 ``_absolute('', 2, ('app', 'pipeline'), 'seed') = 'app'``（正确答案
+    ``'app.seed'``）、展开档报 ``['app.seed'] != ['app.seed', 'app.pipeline']``。
+
+    **绿档同时在场**（硬规矩 #50：只放红档会得到一条过紧的守卫）：``app/db/models/`` 包内
+    真实存在的那 12 条 ``level == 1`` 相对导入折成 ``app.db.models._shared`` 一类，必须仍被
+    :func:`_is_forbidden` 放过。⚠️ 矩阵第 7 行 ``("", 2, ("app", "db", "models"), "seed")``
+    折成 ``app.db.seed``——**在 ``app.seed`` 前缀下是 GREEN**（它上溯一层只到 ``app.db``），
+    而在 purity 的白名单下是 RED：**折算串错了不等于判定错了**（Plan02 Ruling 41），故两份
+    回归测试的期望颜色列**不相同**，这不是抄错。
+
+    **本测试守不住什么**（硬规矩 #39）：
+
+    * :func:`_package_of` 由本测试**末尾那一段**看着（Plan02 Ruling 54），但**只在枚举到
+      的那 4 个形状上**：``app/db/models/organisation.py`` 与 ``app/db/models/__init__.py``
+      （包深 3；两者必须给出**同一个**包——这一格正是 ``parts[:-1]`` 这个写法的全部理由）、
+      ``app/domain/indicators.py``（包深 2）、``app/domain/prescription/match.py``（包深 3，
+      Task 2 才会出现的形状；``_package_of`` 是纯路径运算、不碰文件系统，故可以先断言）。
+      **没枚举进去的包深（包深 4 及更深）不被覆盖**；上面那 11 格矩阵的 ``package`` 入参
+      仍是**手写的**，故矩阵与末尾那一段互不覆盖、谁也不替代谁。
+    * 它不扫真仓文件，故「``FORBIDDEN_PREFIX`` 取值本身对不对」仍只由
+      :func:`test_production_layers_never_import_app_seed` 看着，两条判据互不覆盖。
+    * 矩阵是有限的 11 格：更深的包、更大的 ``level`` 没列进去就不被覆盖。判据既然是
+      ``resolve_name``，往 ``cases`` 里加一行就是加一格覆盖，不必动断言。
+    """
+    # 就地 import：模块级 import 会改动本文件的 <module-level>，故这条测试自 fix round 3
+    # 起就把 import 留在函数体内、改动面也一直钉死在「这一条测试函数 + docstring」
+    # 之内（Plan02 Ruling 46/57）。
+    import importlib.util
+
+    #: ``(module, level, package, name, 期望颜色)``。以 **AST 形状**为参数，不用「``from …``
+    #: 的字面写法」当唯一标识——同一句写法在不同包深下折算到不同的地方（Plan02
+    #: Ruling 41/45）。期望颜色是**判据**（本文件的 ``app.seed`` 前缀语义），不是折算结果。
+    cases = [
+        # level == 0：本来就是绝对串，原样返回
+        ("app.seed.generate", 0, ("app", "domain"), "", "RED"),
+        # level == 1：包内合法导入（绿档，硬规矩 #50 的 ②）；真仓 app/db/models/ 就是这一档
+        ("_shared", 1, ("app", "db", "models"), "", "GREEN"),
+        ("", 1, ("app", "db", "models"), "_shared", "GREEN"),
+        # level == 2：跨包指向 app.seed，真 offender
+        ("seed.generate", 2, ("app", "pipeline"), "", "RED"),
+        # module 为空：被导入的模块名住在 node.names 里（Ruling 36）
+        ("", 2, ("app", "pipeline"), "seed", "RED"),
+        ("", 2, ("app", "db"), "seed", "RED"),
+        ("", 2, ("app", "db", "models"), "seed", "GREEN"),
+        ("", 2, ("app", "domain"), "seed", "RED"),
+        # 越界档：resolve_name 抛 ImportError，_absolute 必须返回 None（Ruling 35）
+        ("seed", 5, ("app", "db", "models"), "generate", "RED"),
+        ("domain", 4, ("app", "domain"), "tables", "RED"),
+        # level - 1 == len(package)：由 `not anchor` 那一行兜住，同样必须 None
+        ("seed", 3, ("app", "domain"), "generate", "RED"),
+    ]
+    offenders: list[str] = []
+    for module, level, package, name, color in cases:
+        rel = "." * level + (module or name)
+        pkg = ".".join(package)
+        try:
+            want = importlib.util.resolve_name(rel, pkg)
+        except ImportError:
+            want = None
+        got = _absolute(module, level, package, name)
+        if got != want:
+            offenders.append(
+                f"_absolute({module!r}, {level}, {package!r}, {name!r}) = {got!r}，"
+                f"而 resolve_name({rel!r}, {pkg!r}) = {want!r}"
+            )
+        verdict = "RED" if got is None or _is_forbidden(got) else "GREEN"
+        if verdict != color:
+            offenders.append(
+                f"_absolute({module!r}, {level}, {package!r}, {name!r}) = {got!r} "
+                f"判成 {verdict}、期望 {color}"
+            )
+    assert offenders == [], (
+        "_absolute 与 importlib.util.resolve_name 不一致、或某一档颜色不对"
+        "（Plan02 Ruling 35/36/41）：\n" + "\n".join(offenders)
+    )
+
+    # Ruling 36 的另一半：一个 ImportFrom 节点带两个名字，必须展开成两条、各自折算。
+    tree = ast.parse("from .. import seed, pipeline\n")
+    package = ("app", "pipeline")
+    got = [module for _lineno, module in _imported_modules(tree, package)]
+    want = [importlib.util.resolve_name(f"..{alias}", ".".join(package))
+            for alias in ("seed", "pipeline")]
+    assert got == want, f"一名一条的展开失效: {got} != {want}"
+
+    # ---------------------------------------------------------------- Ruling 54
+    # 上面 11 格的 package 入参是**手写的**，故 _package_of 被改坏时它们照样全绿；而它是
+    # 两条守卫共同的假绿入口（Plan02 Ruling 37/54）。_package_of 是纯路径运算、不碰文件
+    # 系统，故最后一格可以写 Task 2 才会出现的形状。
+    pkg_cases = [
+        # (backend/ 下的相对路径, 正确的**包**, parts[:-1] 写成 parts 时会得到的**模块路径**)
+        ("app/db/models/organisation.py", ("app", "db", "models"),
+         ("app", "db", "models", "organisation")),
+        # __init__.py 与同目录的普通模块给出**同一个**包：这一格是 parts[:-1] 的全部理由
+        ("app/db/models/__init__.py", ("app", "db", "models"),
+         ("app", "db", "models", "__init__")),
+        ("app/domain/indicators.py", ("app", "domain"), ("app", "domain", "indicators")),
+        # Task 2 会新建 app/domain/prescription/ 子包（今天不存在）
+        ("app/domain/prescription/match.py", ("app", "domain", "prescription"),
+         ("app", "domain", "prescription", "match")),
+    ]
+    pkg_offenders: list[str] = []
+    for rel, want_pkg, module_path in pkg_cases:
+        got_pkg = _package_of(BACKEND / rel)
+        if got_pkg != want_pkg:
+            pkg_offenders.append(
+                f"_package_of(BACKEND / {rel!r}) = {got_pkg!r}，应为**包** {want_pkg!r}"
+            )
+        if got_pkg == module_path:
+            pkg_offenders.append(
+                f"_package_of(BACKEND / {rel!r}) = {got_pkg!r} 是**模块路径**、不是包"
+                "（parts[:-1] 被写成了 parts）"
+            )
+    # 后果也要能跑、不能只写在断言消息里：把 _package_of 的输出直接喂给 _absolute，
+    # 结果仍须与 resolve_name 逐字相同（判据同上，锚在 Python 自己的语义上）。
+    for rel, level, module, want_pkg in (
+            ("app/domain/indicators.py", 2, "seed", ("app", "domain")),
+            ("app/db/models/organisation.py", 3, "seed", ("app", "db", "models"))):
+        rel_import = "." * level + module
+        pkg_str = ".".join(want_pkg)
+        got = _absolute(module, level, _package_of(BACKEND / rel))
+        want = importlib.util.resolve_name(rel_import, pkg_str)
+        if got != want:
+            pkg_offenders.append(
+                f"{rel} 里的 from {rel_import} import …：用 _package_of 的结果折算得到 "
+                f"{got!r}，而 resolve_name({rel_import!r}, {pkg_str!r}) = {want!r}"
+            )
+    assert pkg_offenders == [], (
+        "_package_of 返回的不是**包**（Plan02 Ruling 37/54）：parts[:-1] 写成 parts 会让"
+        "它返回**模块路径**，于是 app/db/models/x.py 里的 from ...seed import … 折成 "
+        "app.db.seed、不再以 app.seed 开头 → 本守卫假绿（test_domain_purity.py 那一份同理："
+        "app/domain/x.py 里的 from ..seed import … 折成 app.domain.seed、命中白名单前缀 "
+        "app.domain.），而在本段断言加上之前，这么改一次全量测试都照样通过：\n"
+        + "\n".join(pkg_offenders)
+    )
+
+
 def test_production_layers_never_import_app_seed():
     """``app/pipeline`` / ``app/db`` / ``app/domain`` 不得 import ``app.seed``。
 
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
+    # 目录被搬空时仍剩 **13…18** 个 .py（24 − 11(db) = 13、24 − 7(pipeline) = 17、
+    # 24 − 6(domain) = 18，由上面那条 Counter 命令本轮亲跑得出），本断言拦不住。
+    # 那一档的兜底是：``domain`` 由
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
index 8f9be97..f1bf29d 100644
--- a/backend/tests/db/test_models.py
+++ b/backend/tests/db/test_models.py
@@ -580,36 +580,127 @@ _SINGLE_PERSON_QUERIES = (
 
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
-    场景                             单次墙钟中位 (ms)    ``.db`` 字节        EXPLAIN QUERY PLAN
+    场景                        单次墙钟中位 (ms，单次采样、方向不可复现)   ``.db`` 字节   EXPLAIN QUERY PLAN
     ==============================  ==================  ==================  =====================
     A 仅 UniqueConstraint 的自动索引        0.2708           5 423 104        ``USING COVERING INDEX sqlite_autoindex_stratification_result_1 (student_id=?)``
     B A + 显式 ``Index(student_id, computed_on)``  0.2941      6 791 168        ``USING COVERING INDEX ix_stratification_result_student_computed (student_id=?)``
     ==============================  ==================  ==================  =====================
 
-    B/A = **1.086**（即加了索引**没有变快**，中位数还慢了 8.6%，n=300，两个场景各自
+    B/A = **1.086**（即加了索引**没有变快**，中位数还慢了 8.6%——⚠️ **这个方向不可复现**，
+    是机器/负载噪声，四次连跑的值见下方「复跑」那一段；两个场景各自
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
```

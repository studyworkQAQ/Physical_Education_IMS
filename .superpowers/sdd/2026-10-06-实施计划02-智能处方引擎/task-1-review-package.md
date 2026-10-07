# Review package — Plan 02 Task 1

BASE e26347f -> HEAD 1df5e8a

## git log --oneline
1df5e8a refactor: Plan02 Task1 架构债清偿，切断 app/seed 依赖、models 拆包、两列 schema 补齐

## git diff --stat
 backend/app/adapters/factory.py                  | 109 ++++
 backend/app/config.py                            |  43 ++
 backend/app/db/models.py                         | 676 -----------------------
 backend/app/db/models/__init__.py                |  91 +++
 backend/app/db/models/_shared.py                 |  65 +++
 backend/app/db/models/assessment.py              | 187 +++++++
 backend/app/db/models/derived.py                 | 243 ++++++++
 backend/app/db/models/feedback.py                |   8 +
 backend/app/db/models/ops.py                     | 169 ++++++
 backend/app/db/models/organisation.py            | 121 ++++
 backend/app/db/models/prescription.py            |  16 +
 backend/app/db/session.py                        |  31 +-
 backend/app/domain/indicators.py                 | 111 ++++
 backend/app/pipeline/backfill.py                 |  12 +-
 backend/app/pipeline/clean.py                    |  15 +-
 backend/app/pipeline/daily.py                    |  95 +++-
 backend/app/pipeline/percentile_stage.py         |  35 +-
 backend/app/pipeline/run_stratify.py             |  40 +-
 backend/app/refdata.py                           |  15 +-
 backend/app/seed/fitness.py                      |  15 +-
 backend/app/seed/generate.py                     |  13 +-
 backend/tests/adapters/test_factory.py           |  88 +++
 backend/tests/architecture/test_domain_purity.py | 281 ++++++++--
 backend/tests/architecture/test_layering.py      | 121 ++++
 backend/tests/db/test_models.py                  | 251 ++++++++-
 backend/tests/db/test_repo.py                    |   6 +
 backend/tests/domain/test_derive.py              |   4 +-
 backend/tests/domain/test_indicators.py          | 111 +++-
 backend/tests/pipeline/test_clean.py             |  61 ++
 backend/tests/pipeline/test_daily.py             | 169 +++++-
 backend/tests/pipeline/test_percentile_stage.py  | 100 ++++
 backend/tests/seed/test_fitness.py               |   2 +-
 32 files changed, 2503 insertions(+), 801 deletions(-)

## git diff -U10
diff --git a/backend/app/adapters/factory.py b/backend/app/adapters/factory.py
new file mode 100644
index 0000000..2f3fb8f
--- /dev/null
+++ b/backend/app/adapters/factory.py
@@ -0,0 +1,109 @@
+"""适配器工厂：把「用哪个数据源实现」这个决定收拢到一处。
+
+**为什么要建它**（Plan 02 Task 1，终审 B）：基线 ``e26347f`` 上
+``MockLePaoAdapter(DEFAULT_CSV_DIR)`` 被**硬编码在两处生产代码**里——
+``app/pipeline/backfill.py:268`` 与 ``app/pipeline/daily.py:712``（命令::
+
+    git grep -n "MockLePaoAdapter(DEFAULT_CSV_DIR)" -- backend/app/pipeline
+
+）。这与 :mod:`app.adapters.http_lepao` 模块 docstring 里那句承诺直接冲突：
+
+    「乐跑只读接口的字段一旦确定，改动只落在本文件，``app/pipeline`` 与 ``app/domain``
+    完全不动——它们只认 ``DataSourceAdapter`` 这个契约。」
+
+有两处硬编码时，换成 HTTP 实现要改**两个** CLI，而漏改一个不会报错——那条管道会安静地
+继续读本地 CSV，跑出来的数字看起来完全正常。本模块是那句承诺的兑现处：**换实现只改
+这一个文件的 ``_BUILDERS``，或者只改调用方传进来的 ``kind`` 字符串**。
+
+依赖方向（spec §3.3 是 ``pipeline → adapters``）：本模块在 ``adapters`` 里，故它可以
+import 两个具体实现；``app/pipeline`` 的两个 CLI 只在 ``main()`` 函数体内 import 本模块，
+于是 ``import app.pipeline.daily`` 的顶层依赖图里**仍然不出现任何具体适配器**——这个性质
+是 ``daily.py`` 当初写函数内导入的理由，工厂没有把它破坏掉。
+
+:mod:`app.config` 是叶子（只 import ``pathlib``），故 ``adapters → config`` 这条边不可能
+造出环。
+"""
+import pathlib
+from collections.abc import Callable
+
+from app.adapters.base import DataSourceAdapter
+from app.adapters.http_lepao import HttpLePaoAdapter
+from app.adapters.mock_lepao import MockLePaoAdapter
+from app.config import DEFAULT_CSV_DIR
+
+__all__ = ["KINDS", "build_adapter"]
+
+#: 合法的 ``kind`` 取值。元组而不是字典的键集合：``KINDS`` 会被写进报错文本，
+#: 元组让「有哪几种实现」这件事的顺序是声明序、稳定可复现。
+KINDS: tuple[str, ...] = ("mock", "http")
+
+
+def _build_mock(
+    csv_dir: pathlib.Path | None, base_url: str | None, token: str | None
+) -> DataSourceAdapter:
+    """:class:`~app.adapters.mock_lepao.MockLePaoAdapter` 读本地 CSV 夹具。
+
+    ``csv_dir`` 缺省取 :data:`app.config.DEFAULT_CSV_DIR`（``backend/data/seed/``，
+    本仓里恒为空且不入库）。构造函数**不做任何 I/O**，故目录不存在时也不报错——
+    四个 ``fetch_*`` 会 yield 空，那是 Mock 的既有契约，本工厂不改它。
+    """
+    return MockLePaoAdapter(DEFAULT_CSV_DIR if csv_dir is None else csv_dir)
+
+
+def _build_http(
+    csv_dir: pathlib.Path | None, base_url: str | None, token: str | None
+) -> DataSourceAdapter:
+    """:class:`~app.adapters.http_lepao.HttpLePaoAdapter`（骨架，四个方法一律
+    ``NotImplementedError``）。
+
+    ``base_url`` 与 ``token`` **都必填**：``HttpLePaoAdapter.__init__`` 收的是两个无缺省
+    的位置参数，缺一个就是 ``TypeError``。在这里显式拒绝而不是让 ``None`` 流进构造函数，
+    是因为骨架的 ``__init__`` **不发任何请求**（契约测试要在收集期就实例化它），于是
+    ``build_adapter("http")`` 会「成功」返回一个把 ``base_url=None`` 存下来的对象，
+    直到有人真去调 ``fetch_*`` 才炸——离真因隔了一整个调用栈。
+    """
+    if base_url is None or token is None:
+        raise ValueError(
+            f'kind="http" 需要同时给出 base_url 与 token（收到 base_url={base_url!r}, '
+            f"token={'<已给出>' if token is not None else None}）；"
+            f"{HttpLePaoAdapter.__name__} 的构造函数不发请求，缺参会被静默存下来、"
+            f"到第一次 fetch_* 才炸"
+        )
+    return HttpLePaoAdapter(base_url, token)
+
+
+_BUILDERS: dict[str, Callable[..., DataSourceAdapter]] = {
+    "mock": _build_mock,
+    "http": _build_http,
+}
+
+
+def build_adapter(
+    kind: str = "mock",
+    *,
+    csv_dir: pathlib.Path | None = None,
+    base_url: str | None = None,
+    token: str | None = None,
+) -> DataSourceAdapter:
+    """按 ``kind`` 造一个 :class:`~app.adapters.base.DataSourceAdapter`。
+
+    只读与 ``kind`` 对应的那几个参数，其余一律忽略（``kind="mock"`` 时 ``base_url`` /
+    ``token`` 不看，``kind="http"`` 时 ``csv_dir`` 不看）。刻意**不**为「传了用不上的
+    参数」报错：那会让调用方在两个实现之间切换时必须同时改参数表，而工厂的意义正是让
+    切换只动 ``kind`` 一个词。
+
+    ``kind`` 不在 :data:`KINDS` 里时抛 ``ValueError`` 并**列出全部合法取值**——一个拼错的
+    ``kind``（``"Mock"``、``"mock_lepao"``）若退化成「用缺省的 mock」，HTTP 那条路径会
+    永远走不到，而控制台上一切正常。
+
+    ``token`` 不出现在任何报错文本里（只印「已给出 / None」）：它是凭据，
+    :mod:`app.adapters.http_lepao` 的模块 docstring 明确要求它不得进日志、异常消息或
+    ``repr``。
+    """
+    try:
+        builder = _BUILDERS[kind]
+    except KeyError:
+        raise ValueError(
+            f"未知的适配器 kind={kind!r}；合法取值是 {list(KINDS)}"
+        ) from None
+    return builder(csv_dir, base_url, token)
diff --git a/backend/app/config.py b/backend/app/config.py
new file mode 100644
index 0000000..90d4b79
--- /dev/null
+++ b/backend/app/config.py
@@ -0,0 +1,43 @@
+"""进程级路径与 URL 缺省值的**唯一所有者**。
+
+本模块是全仓依赖图的一个**叶子**：它只 import :mod:`pathlib`，不 import ``app`` 里的
+任何东西，因此任何一层（``adapters`` / ``db`` / ``pipeline`` / ``seed`` / ``refdata``）
+都可以安全地 import 它而不可能造出环。spec §3.3 的依赖方向图里没有它的位置，因为它
+不是一个层——它是「这个项目在磁盘上长什么样」这一件事的住址。
+
+**为什么要建这个模块**（Plan 02 Task 1，终审 C 组）：这三个值原先住在
+``app/seed/generate.py``，于是生产层为了拿一个**路径常量**必须 import 仿真数据生成器。
+基线 ``e26347f`` 上 ``git grep -n "from app.seed" -- backend/app/pipeline`` 报出的
+4 处 offender 里有 3 处（``daily.py:689``、``backfill.py:234`` 各一处、
+``run_stratify.py:49`` 一处）就是为了 ``DEFAULT_CSV_DIR`` / ``DEFAULT_DB_URL``。
+把常量搬到这里之后，``app/pipeline`` 与 ``app/seed`` 之间不再有边，
+:mod:`tests.architecture.test_layering` 的依赖方向守卫因此转绿。
+
+**``DEFAULT_DB_URL`` 是绝对路径，不是 ``sqlite:///pe.db``**：后者是 CWD 相对路径，
+从仓库根跑与从 ``backend/`` 跑会指向**两个不同的文件**，而两个文件都不会报错——
+只是其中一个永远是空的（Plan01 Ruling 190 要消除的正是这个形状）。
+``app/db/session.py`` 的 :func:`~app.db.session.engine` 也因此**不再带缺省 URL**：
+一个函数签名里的 ``"sqlite:///pe.db"`` 字面量是本常量的第二个所有者，而它是相对路径
+的那一个。
+
+⚠️ ``DEFAULT_DB_URL`` 指向的 ``backend/pe.db`` **不入库**（``.gitignore``），且本仓
+不做迁移——schema 改动等于重建库，见 :mod:`app.db.models` 的模块 docstring。
+"""
+import pathlib
+
+__all__ = ["BACKEND_DIR", "DEFAULT_CSV_DIR", "DEFAULT_DB_URL"]
+
+#: ``backend/`` 的绝对路径。本文件在 ``backend/app/config.py``，故 ``parent.parent``。
+#: 它此前住在 ``app/seed/generate.py``（那里写作 ``pathlib.Path(__file__).resolve().parents[2]``，
+#: 与本式等价：``generate.py`` 在 ``backend/app/seed/`` 下，深一层）。
+BACKEND_DIR: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent
+
+#: ``python -m app.seed.generate`` 写三类 CSV 的缺省目录，也是
+#: :class:`~app.adapters.mock_lepao.MockLePaoAdapter` 的缺省 ``seed_dir``。
+#: 该目录**不入库**（``.gitignore``），且在本仓里恒为空——生成器不许被随手跑。
+DEFAULT_CSV_DIR: pathlib.Path = BACKEND_DIR / "data" / "seed"
+
+#: 演示用磁盘库的 URL。``as_posix()`` 是承重的：Windows 上 ``str(Path)`` 给出反斜杠，
+#: 而 SQLite 的 URL 语法里反斜杠不是路径分隔符，``sqlite:///C:\\…\\pe.db`` 会被当成
+#: 一个名字里带反斜杠的相对文件。
+DEFAULT_DB_URL: str = f"sqlite:///{(BACKEND_DIR / 'pe.db').as_posix()}"
diff --git a/backend/app/db/models.py b/backend/app/db/models.py
deleted file mode 100644
index ea2c6f7..0000000
--- a/backend/app/db/models.py
+++ /dev/null
@@ -1,676 +0,0 @@
-"""14 张表的 ORM 模型（字段清单严格按 spec §4.1–§4.3、§4.6）。
-
-三条贯穿全表的约定，改动前请先读完：
-
-1. **缺测就是 ``NULL``，绝不是 0**（Ruling 21）。所有原始测量值与国标单项得分一律
-   声明为可空。0 是数值列最常见的缺测占位，而 50 米跑与耐力跑各占 20% 权重：把缺测
-   当 0 分入库，等于给体能最差的学生送上 40% 权重的满分，还同时抹掉两个能力桶的短板
-   ——而且它抬分不压分，不会被「成绩异常低」的直觉发现。「有效项数」由
-   ``derived_metrics.valid_count`` 显式承载，不靠 0 值反推。
-
-2. **枚举取值域两处设防**。每个枚举式列都同时给出类常量集合（供 Python 侧校验与测试
-   断言）与 SQL 层 ``CheckConstraint``（让数据库自己拒绝脏值）。类常量是唯一真相，
-   约束文本由 :func:`_in_domain` 从类常量生成，两者不可能各说各话。
-
-3. **JSON 形态的列一律用 :class:`JsonText`**（八个列，无一例外）。SQLite 没有原生
-   JSON，该类型以 ``TEXT`` 为底层、由它自己负责 dumps/loads，调用方拿到手的直接是
-   原样的 ``dict`` / ``list`` / 标量，与 domain 层的值对象（如
-   ``DerivedResult.annual_change: dict[str, float]``）同构，不必各自再约定一套序列化
-   格式——那正是口径漂移的温床。为什么不用 SQLAlchemy 自带的 ``JSON`` 类型，见
-   :class:`JsonText` 的 docstring（SQLite 的 NUMERIC 亲和性会改写标量）。
-
-本模块不声明任何 ``relationship``：管道按 ``batch_id`` 批量读写，显式 ``select`` 比
-懒加载更可预测，也不会在 Session 关闭后触发意外的延迟查询。
-"""
-import datetime as dt
-import json
-from collections.abc import Iterable
-from typing import Any
-
-from sqlalchemy import (
-    Boolean,
-    CheckConstraint,
-    Date,
-    DateTime,
-    Float,
-    ForeignKey,
-    Integer,
-    String,
-    Text,
-    UniqueConstraint,
-)
-from sqlalchemy.orm import Mapped, mapped_column
-from sqlalchemy.types import TypeDecorator
-
-from app.db.session import Base
-
-__all__ = [
-    "Semester",
-    "Teacher",
-    "Student",
-    "CourseSection",
-    "Enrollment",
-    "FitnessTestBatch",
-    "FitnessTestResult",
-    "BodyComposition",
-    "InterestSurvey",
-    "PercentileSnapshot",
-    "DerivedMetrics",
-    "StratificationResult",
-    "DailySyncRun",
-    "CleaningLog",
-]
-
-
-def _in_domain(column: str, allowed: Iterable[str], name: str) -> CheckConstraint:
-    """由类常量集合生成 SQL 层的取值域约束。
-
-    约束文本从集合生成而不是手写第二遍：手写两遍迟早会漂移，而漂移是静默的——
-    Python 侧放行的值数据库拒收，或反过来数据库放进了 Python 侧读不懂的值。
-    取值按字典序排序，使 DDL 文本稳定可复现（同 seed 同 DDL）。
-    """
-    quoted = ", ".join("'" + v.replace("'", "''") + "'" for v in sorted(allowed))
-    return CheckConstraint(f"{column} IN ({quoted})", name=name)
-
-
-class JsonText(TypeDecorator):
-    """把 Python 的 ``dict`` / ``list`` / 标量以 JSON 文本存进 ``TEXT`` 列。
-
-    **为什么不直接用 SQLAlchemy 自带的 ``JSON`` 类型**：它在 SQLite 上渲染成
-    ``JSON``，而 SQLite 的亲和性规则里 ``JSON`` 落到 **NUMERIC** 亲和性——凡「看起来
-    像数字」的值会被就地转成原生数值存进去，不再是 JSON 文本。实测（Python 3.11.1 /
-    SQLAlchemy 2.1.1 / SQLite；探针 = 建一张只有一个 ``JSON`` 列的表、写四个标量后读
-    ``select id, typeof(v), v``）：``0.0`` 与 ``65.0`` **都**落 ``typeof='integer'``、
-    读回来是 Python ``int`` ``0`` / ``65``（浮点被降成整型），``65.5`` 与 ``65.0000001``
-    才落 ``typeof='real'``——NUMERIC 亲和性把**能无损表示成整数**的实数降成整型、其余留
-    ``real``。本段此前印的是「``65.0`` 存成 ``real`` 而非文本」，那与它自己下一句的结论
-    相反：真存成 ``real 65.0`` 的话读回仍是 ``65.0``，「原值 65.0 kg」就不会被记成
-    「原值 65」——正是**降成整型**才造成失真。这条探针**不在测试网里、不被守卫**
-    （本仓没有任何测试用 SQLAlchemy 自带的 ``JSON`` 类型），属历史实测，fix round 3 复跑。
-    对 ``cleaning_log`` 这种存标量的审计列，这是实打实的失真，而审计记录的全部价值就在于
-    原值不被改写。
-
-    以 ``TEXT`` 为底层类型即绕开亲和性转换，同时保留透明 dumps/loads：调用方拿到手的
-    仍是原样的 Python 对象，全库八个 JSON 形态的列共用这一种落法，不必区分「这一列
-    要不要自己 ``json.dumps``」——那种不对称正是会被忘掉、且忘掉后静默出错的地方。
-    ``ensure_ascii=False`` 让中文原样落库，用 sqlite3 命令行直接看审计记录时可读。
-    ``None`` 存 SQL ``NULL`` 而不是 ``'null'`` 文本，读回也是 ``None``。
-
-    ``cache_ok = True`` 是必需的：缺了它 SQLAlchemy 会对每条用到该列的语句发
-    ``SAWarning``（该类型无法生成缓存键），在 ``-W error`` 下直接变成失败。
-    """
-
-    impl = Text
-    cache_ok = True
-
-    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
-        return None if value is None else json.dumps(value, ensure_ascii=False)
-
-    def process_result_value(self, value: Any, dialect: Any) -> Any:
-        return None if value is None else json.loads(value)
-
-
-# ---------------------------------------------------------------------------
-# spec §4.1 组织与身份
-# ---------------------------------------------------------------------------
-
-
-class Semester(Base):
-    """学期：整条管道的日历骨架，业务日期的合法区间由它的起止日界定。"""
-
-    __tablename__ = "semester"
-
-    id: Mapped[int] = mapped_column(primary_key=True)
-    # 学期名同时是 CLI（--semester 2025-2026-1）与幂等键的查找键，故唯一
-    name: Mapped[str] = mapped_column(String(32), unique=True)
-    start_date: Mapped[dt.date] = mapped_column(Date)
-    # **排他**上界（Ruling 174）：学期区间是 ``[start_date, end_date)``，与 range/slice 的
-    # 惯例一致，也与 ``app.seed.config.semester_end_date`` 的算式（开学日 + 教学周数）自洽——
-    # 16 周 × 7 = 112 天对应的闭区间是 ``2025-09-01..2025-12-21``，而本列存的是
-    # ``2025-12-22``。故 ``app.pipeline.backfill`` 的 CLI 把它当闭区间上界用之前必须减一天
-    # （换算放在 CLI 层，不改 ``semester_end_date``：Task 6 冻结代码，它的算式本身是对的）。
-    # 注意 ``daily._semester_of`` / ``percentile_stage.current_semester_of`` 的区间查询仍是
-    # **闭**的（``end_date >= day``）：那两处要的是「包含某个测量日」，而最晚的测量日是
-    # ``week16`` = ``end_date - 7 天``，多含的那一天里没有任何数据。
-    end_date: Mapped[dt.date] = mapped_column(Date)
-    weeks: Mapped[int] = mapped_column(Integer)  # 教学周数，spec 固定 16
-    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
-
-
-class Teacher(Base):
-    """体育教师。工号是与教务系统对接的自然键。"""
-
-    __tablename__ = "teacher"
-
-    id: Mapped[int] = mapped_column(primary_key=True)
-    staff_no: Mapped[str] = mapped_column(String(32), unique=True)  # 工号
-    name: Mapped[str] = mapped_column(String(64))
-
-
-class Student(Base):
-    """学生。``sex`` / ``birth`` / ``grade`` 共同决定该查哪一张国标评分表。"""
-
-    __tablename__ = "student"
-
-    # 取值域与 app/domain/indicators.py 的 Sex 枚举一致（male / female）。这里不
-    # import 它：Task 3 的接口约定是「Consumes: 无」，db 层不为一个二元集合引入
-    # 跨层依赖。代价是两处需人工同步，已登记在任务报告的关切里。
-    SEXES: set[str] = {"male", "female"}
-
-    id: Mapped[int] = mapped_column(primary_key=True)
-    student_no: Mapped[str] = mapped_column(String(32), unique=True)  # 学号
-    name: Mapped[str] = mapped_column(String(64))
-    sex: Mapped[str] = mapped_column(String(8))
-    birth: Mapped[dt.date] = mapped_column(Date)  # 出生年月；龄组由它折算
-    department: Mapped[str | None] = mapped_column(String(64))  # 院系
-    grade: Mapped[int] = mapped_column(Integer)  # 年级 1–4
-
-    __table_args__ = (_in_domain("sex", SEXES, "ck_student_sex"),)
-
-
-class CourseSection(Base):
-    """教学班。阶段一的行政班与阶段二的分层班并存，靠 ``grouping_mode`` 区分。"""
-
-    __tablename__ = "course_section"
-
-    # administrative = 阶段一在行政班内分层；stratified = 阶段二跨班重编出来的
-    # 提升班 / 强化班 / 拓展班。同一批学生两套编班同时存在，演示时可切换。
-    GROUPING_MODES: set[str] = {"administrative", "stratified"}
-
-    id: Mapped[int] = mapped_column(primary_key=True)
-    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
-    teacher_id: Mapped[int] = mapped_column(ForeignKey("teacher.id"))
-    name: Mapped[str] = mapped_column(String(64))  # 课程名 / 分层班名
-    schedule_text: Mapped[str | None] = mapped_column(String(64))  # 上课时间
-    grouping_mode: Mapped[str] = mapped_column(String(16))
-
-    __table_args__ = (
-        _in_domain("grouping_mode", GROUPING_MODES, "ck_course_section_grouping_mode"),
-    )
-
-
-class Enrollment(Base):
-    """选课关系，对应厦大「三自主」选课：学期 × 学生 × 教学班。"""
-
-    __tablename__ = "enrollment"
-
-    id: Mapped[int] = mapped_column(primary_key=True)
-    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
-    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
-    course_section_id: Mapped[int] = mapped_column(ForeignKey("course_section.id"))
-
-    __table_args__ = (
-        UniqueConstraint(
-            "semester_id",
-            "student_id",
-            "course_section_id",
-            name="uq_enrollment_semester_student_section",
-        ),
-    )
-
-
-# ---------------------------------------------------------------------------
-# spec §4.2 学期节点数据（低频，来自乐跑）
-# ---------------------------------------------------------------------------
-
-
-class FitnessTestBatch(Base):
-    """一次体测批次。``timepoint`` 是学期内的三个采集节点。"""
-
-    __tablename__ = "fitness_test_batch"
-
-    TIMEPOINTS: set[str] = {"week1", "week8", "week16"}
-
-    id: Mapped[int] = mapped_column(primary_key=True)
-    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
-    timepoint: Mapped[str] = mapped_column(String(8))
-    test_date: Mapped[dt.date] = mapped_column(Date)
-    # 下面两项来自源系统、可能整列缺失，故可空（见模块 docstring 的可空性原则）
-    source: Mapped[str | None] = mapped_column(String(32))  # 来源系统
-    academic_year: Mapped[str | None] = mapped_column(String(16))  # 学年
-
-    __table_args__ = (
-        _in_domain("timepoint", TIMEPOINTS, "ck_fitness_test_batch_timepoint"),
-    )
-
-
-class FitnessTestResult(Base):
-    """一名学生在某批次里的 8 项原始测量、7 项国标计分项得分、总分与等级。
-
-    8 → 7 → 6 的口径见 spec §4.2：身高与体重合成 BMI 一项计分，故 8 项原始测量对应
-    7 个计分项；短板判定又排除 BMI（避免与体成分 ``C`` 重复计数），故只有 6 项进
-    ``derived_metrics`` 的 ``W``。得分列名一律是 ``score_`` + ``ScoredItem`` 的值，
-    管道可用 ``getattr(row, f"score_{item.value}")`` 逐项取用，不必再维护一张映射表。
-
-    指向体测批次的外键**刻意不叫** ``batch_id`` 而叫 ``test_batch_id``（Ruling 31）：
-    本项目里 ``batch_id`` 一词专指「指向 ``daily_sync_run`` 的外键」，也就是
-    :func:`app.db.repo.delete_by_batch` 可据以删除的归属键，只有三张派生表才允许拥有
-    它。若本表也叫 ``batch_id``，误调 ``delete_by_batch(session, FitnessTestResult,
-    sync_run_id)`` 时——``fitness_test_batch.id`` 只有 1/2/3（week1/week8/week16），
-    而 ``daily_sync_run.id`` 按业务日递增（一学期 1…112）——凡 ``sync_run_id ∈ {1, 2,
-    3}`` 都会匹配上并**静默删掉真实源体测数据**：两列都是 int，外键拦不住（每个值各自
-    合法），``AttributeError`` 也拦不住（属性存在）。删源数据比删派生行严重得多——派生
-    行重算就回来了，源体测数据删了就是删了。改名后这一脚踩下去是响亮的
-    ``AttributeError``，与 ``CleaningLog`` 用 ``sync_run_id`` 的既有设计同一口径。
-    """
-
-    __tablename__ = "fitness_test_result"
-
-    id: Mapped[int] = mapped_column(primary_key=True)
-    # 体测批次（week1/week8/week16 的测试事件），不是 daily_sync_run，故不叫 batch_id
-    test_batch_id: Mapped[int] = mapped_column(ForeignKey("fitness_test_batch.id"))
-    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
-
-    # —— 8 项原始测量（乐跑口径）——
-    height_cm: Mapped[float | None] = mapped_column(Float)  # 身高
-    weight_kg: Mapped[float | None] = mapped_column(Float)  # 体重
-    vital_capacity_ml: Mapped[float | None] = mapped_column(Float)  # 肺活量
-    sprint_50m_s: Mapped[float | None] = mapped_column(Float)  # 50 米跑
-    sit_and_reach_cm: Mapped[float | None] = mapped_column(Float)  # 坐位体前屈
-    standing_jump_cm: Mapped[float | None] = mapped_column(Float)  # 立定跳远
-    # 引体向上（男）/ 一分钟仰卧起坐（女）；0 次是合法真实值，只有 NULL 才是缺测
-    strength_count: Mapped[float | None] = mapped_column(Float)
-    distance_run_s: Mapped[float | None] = mapped_column(Float)  # 1000 米（男）/ 800 米（女）
-
-    # —— 7 项国标计分项得分（0–100，就低取档，Ruling 18）——
-    score_bmi: Mapped[int | None] = mapped_column(Integer)
-    score_vital_capacity: Mapped[int | None] = mapped_column(Integer)
-    score_sprint_50m: Mapped[int | None] = mapped_column(Integer)
-    score_sit_and_reach: Mapped[int | None] = mapped_column(Integer)
-    score_standing_jump: Mapped[int | None] = mapped_column(Integer)
-    score_pull_up_or_sit_up: Mapped[int | None] = mapped_column(Integer)
-    score_distance_run: Mapped[int | None] = mapped_column(Integer)
-
-    total_score: Mapped[int | None] = mapped_column(Integer)  # 国标总分（100 分制）
-    national_grade: Mapped[str | None] = mapped_column(String(16))  # 国标等级
-
-    # 一名学生在同一次体测事件里只可能有一条成绩（Ruling 24）。注意本表的
-    # test_batch_id 指向 fitness_test_batch（week1/week8/week16 的测试事件），与
-    # daily_sync_run 无关，故幂等重放不能靠 delete_by_batch 按批清理，只能靠这条业务
-    # 键兜底：**没有它**的话，Task 10 重跑同一业务日期时若对源表走裸 insert 而不是
-    # repo.upsert，同一名学生同一批次的成绩会静默翻倍（该约束加上之前实测 1 → 2 行、
-    # 无任何异常），百分位快照、短板计数与趋势随之全部失真。**加上之后它是响亮的**：
-    # fix round 3 复跑（裸 SQL 对同一 (student_id, test_batch_id) 插第二行）得
-    # ``sqlite3.IntegrityError: UNIQUE constraint failed: fitness_test_result.test_batch_id,
-    # fitness_test_result.student_id``、行数保持 1。故那句「1 → 2 行」是**改前**实测、
-    # 现由本约束守卫（守卫断言在 ``tests/db/test_models.py``：约束名与列序被逐字钉住）。
-    # 约束显式命名，是为了让报错与将来的迁移脚本能指名道姓地引用它。
-    __table_args__ = (
-        UniqueConstraint(
-            "test_batch_id", "student_id", name="uq_fitness_result_test_batch_student"
-        ),
-    )
-
-
-class BodyComposition(Base):
-    """体成分测量。骨骼肌指数入库但不参与异常判定（spec §14 待确认 #16）。"""
-
-    __tablename__ = "body_composition"
-
-    id: Mapped[int] = mapped_column(primary_key=True)
-    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
-    measured_on: Mapped[dt.date] = mapped_column(Date)
-    muscle_mass_kg: Mapped[float | None] = mapped_column(Float)  # 肌肉量
-    body_fat_pct: Mapped[float | None] = mapped_column(Float)  # 体脂率 %
-    smi: Mapped[float | None] = mapped_column(Float)  # 骨骼肌指数
-    weight_kg: Mapped[float | None] = mapped_column(Float)  # 体重
-    device: Mapped[str | None] = mapped_column(String(32))  # 测量设备
-
-    # 同一学生同一天只留一条体成分（Ruling 24）。本表没有 batch_id，重放翻倍同样只能
-    # 靠这条业务键挡住；一旦重复，C（体成分异常）的判定与异常率都会被同一份读数抬高，
-    # 而它不会报错——「异常率莫名偏高」比「异常率莫名偏低」更难被当成数据问题追查。
-    __table_args__ = (
-        UniqueConstraint(
-            "student_id", "measured_on", name="uq_body_composition_student_measured_on"
-        ),
-    )
-
-
-class InterestSurvey(Base):
-    """体育学习兴趣量表问卷（占位 5 维度 × 5 点李克特，spec §10.9）。"""
-
-    __tablename__ = "interest_survey"
-
-    id: Mapped[int] = mapped_column(primary_key=True)
-    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
-    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
-    filled_on: Mapped[dt.date] = mapped_column(Date)
-    total_score: Mapped[float] = mapped_column(Float)
-    dimensions: Mapped[dict] = mapped_column(JsonText)  # 各维度分，如 {"运动乐趣": 4.0}
-    raw_answers: Mapped[dict] = mapped_column(JsonText)  # 原始答题
-
-    # 同一学生同一学期同一天只留一份问卷（Ruling 24）。三列缺一不可：问卷可按学期
-    # 重复发放，只有「学期 + 填写日」一起才定位得到唯一的那一份。重复的问卷会同时
-    # 抬高样本量与同一个人的权重，兴趣维度均值随之漂移且不报错。
-    __table_args__ = (
-        UniqueConstraint(
-            "student_id",
-            "semester_id",
-            "filled_on",
-            name="uq_interest_survey_student_semester_filled_on",
-        ),
-    )
-
-
-# ---------------------------------------------------------------------------
-# spec §4.3 派生与分层（可追溯核心）
-# ---------------------------------------------------------------------------
-
-
-class PercentileSnapshot(Base):
-    """校内百分位快照。**物化而非实时计算**（spec §4.0）。
-
-    实时算会随人群变动漂移，而研究项目必须能复现任意一天的分层结果。列与 Task 7 的
-    ``PercentileRow`` 值对象一一对应，故 ``compute_snapshot`` 的输出可直接落库，
-    样本量不足 30 时降级来的国标常模行（``source = "national"``）亦然。
-
-    ``batch_id`` + 五列业务唯一键是它的幂等防线（Ruling 29）。此前本表是**唯一一张
-    会被物化、却在库层没有任何幂等机制**的表：既无 ``batch_id``（``delete_by_batch``
-    删不到它），也无唯一约束（重放翻倍不报错），只能靠 Task 10 的跨日复用逻辑加一条
-    行数断言兜着——那是纪律，不是机制；纪律会被下一次重构悄悄改掉，约束不会。
-
-    唯一键的五个列正是 Task 7 的分组键 ``(sex, age_group, item)`` 再加「哪个学期、
-    哪一天」：``compute_snapshot`` 对每个分组最多产出一行（7 个计分项在样本 < 30 时
-    整组降级为 ``source = "national"``，不是并存两行；``muscle_mass_kg`` **没有国标
-    常模可降级**，样本 < 30 时整组不产出行），故 ``source`` 不必进键，同一组同一天
-    也只可能有一行。
-    """
-
-    __tablename__ = "percentile_snapshot"
-
-    SOURCES: set[str] = {"school", "national"}
-
-    # 取值域与 ``app/domain/percentile.py`` 的 ``SnapshotMetric`` 一致：7 个国标计分项
-    # 加上 ``muscle_mass_kg``（肌肉量）。肌肉量**不是计分项**，故它不在 ``ScoredItem``
-    # 里；而 spec §6.3② 的 ``C`` 要用「同龄同性别肌肉量 P20」这条判定线，所以快照表
-    # 必须存得下它。此前本列是该表**唯一没有取值域约束**的业务列，也正是「库里存得下、
-    # 算不出来」这个缺陷形态的机制来源（Ruling 102/121）。与 ``Student.SEXES`` 同一条
-    # 处置：db 层不为一个取值集合引入跨层依赖，代价是两处需人工同步，由
-    # ``tests/db/test_models.py`` 的漂移测试钉住。
-    ITEMS: set[str] = {
-        "bmi",
-        "vital_capacity",
-        "sprint_50m",
-        "sit_and_reach",
-        "standing_jump",
-        "pull_up_or_sit_up",
-        "distance_run",
-        "muscle_mass_kg",
-    }
-
-    id: Mapped[int] = mapped_column(primary_key=True)
-    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
-    computed_on: Mapped[dt.date] = mapped_column(Date)
-    batch_id: Mapped[int] = mapped_column(
-        ForeignKey("daily_sync_run.id"), index=True
-    )
-    item: Mapped[str] = mapped_column(String(32))  # 指标，取 SnapshotMetric 的值
-    sex: Mapped[str] = mapped_column(String(8))
-    age_group: Mapped[str] = mapped_column(String(16))  # 国标年级组
-    p10: Mapped[float] = mapped_column(Float)
-    p20: Mapped[float] = mapped_column(Float)
-    p25: Mapped[float] = mapped_column(Float)  # 短板判定线：低于它即显性短板
-    p50: Mapped[float] = mapped_column(Float)
-    p75: Mapped[float] = mapped_column(Float)
-    sample_size: Mapped[int] = mapped_column(Integer)
-    source: Mapped[str] = mapped_column(String(8))
-
-    __table_args__ = (
-        _in_domain("source", SOURCES, "ck_percentile_snapshot_source"),
-        _in_domain("sex", Student.SEXES, "ck_percentile_snapshot_sex"),
-        _in_domain("item", ITEMS, "ck_percentile_snapshot_item"),
-        UniqueConstraint(
-            "semester_id",
-            "computed_on",
-            "item",
-            "sex",
-            "age_group",
-            name="uq_percentile_snapshot_group_day",
-        ),
-    )
-
-
-class DerivedMetrics(Base):
-    """派生指标：分层判定的直接输入，也是「逐人可追溯」链条的中间一环。
-
-    ``batch_id`` 指向 ``daily_sync_run``：幂等重放靠它按批删除本表与
-    ``stratification_result`` 的旧行（见 :func:`app.db.repo.delete_by_batch`）。
-    没有这一列，重跑同一天就只能靠「学生 + 日期」去猜哪些行属于哪一次运行。
-
-    **``uq_derived_metrics_student_day``（Ruling 212）**：``(student_id, computed_on)``
-    唯一。派生表的**自然键**是 ``(student_id, computed_on)``，而重放的**幂等键**是
-    ``(semester_id, business_date)`` —— **两个键不同维度**，``_replay_cleanup`` 只按
-    ``batch_id`` 删，跨学期删不到对方。于是「同一业务日期在两个 ``semester_id`` 下各跑一次」
-    会留下两套「当前」结果，而所有自然读法（``ORDER BY computed_on DESC LIMIT 1``）
-    都会**稳定取到陈旧那一套**（``computed_on`` 相同、无二级排序 → SQLite 按 rowid 升序扫
-    → 预跑那批 id 更小）。终审实测（60 人，第二次跑的 ``standing_jump_cm`` 减 60）：
-    ``stratification_result`` 120 行 / 60 学生 / **60 人各有两行同 ``computed_on``**、
-    ``COUNT(DISTINCT input_snapshot) = 2``。教师大屏 ``WHERE computed_on=? GROUP BY label``
-    会把 60 人的班报成 120 人。
-
-    终审已亲验：干净回放下 ``(student_id, computed_on)`` 在 **56000 行**上已经唯一
-    （``distinct = 56000``），故正常路径不会误伤，只有跨学期重跑才会响亮失败。
-    另一道闸是 CLI 的「``--date`` 必须落在 ``--semester`` 区间内」守卫
-    （:func:`app.pipeline.daily.require_dates_in_semester`）。
-
-    ⚠️ **``init_db`` 用 ``Base.metadata.create_all``，它对已存在的表不会补约束/索引**：
-    本约束只对**新建**的库生效。已有的 ``pe.db`` 必须重建（或手工
-    ``CREATE UNIQUE INDEX``），否则跨学期重跑仍然静默双写。
-    """
-
-    __tablename__ = "derived_metrics"
-
-    id: Mapped[int] = mapped_column(primary_key=True)
-    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
-    computed_on: Mapped[dt.date] = mapped_column(Date)
-    batch_id: Mapped[int] = mapped_column(
-        ForeignKey("daily_sync_run.id"), index=True
-    )
-
-    annual_change: Mapped[dict] = mapped_column(JsonText)  # 各指标年均变化率
-    # 列宽 **20** 而不是 16（Ruling 144）：``Trend.INSUFFICIENT.value`` =
-    # ``"insufficient_data"`` 是 **17** 字符，16 装不下。SQLite 不强制 ``VARCHAR`` 长度，
-    # 故它静默存下——而 500 人首批实测就有 209 行（41.8%）写这个 17 字符的值；换任何严格
-    # 长度的后端（MySQL / PostgreSQL）会截断成 ``"insufficient_dat"``，读回来
-    # ``Trend(...)`` 当场 ``ValueError``，**炸在读侧不在写侧**，离真因隔一整个批处理周期。
-    # 取 20 与 ``stratification_result.label`` 对齐：两列存的是同一族 17 字符的值。
-    # 守卫见 ``tests/db/test_models.py`` 的列宽遍历测试（硬规矩 #18）。
-    trend: Mapped[str] = mapped_column(String(20))  # 趋势标签（Task 8 的 Trend 值）
-    weaknesses: Mapped[list] = mapped_column(JsonText)  # 短板列表，元素为 ScoredItem 的值
-    weakness_count: Mapped[int] = mapped_column(Integer, default=0)  # W，分母恒为 6
-    valid_count: Mapped[int] = mapped_column(Integer, default=0)  # < 4 则本日不分层
-    body_comp_abnormal: Mapped[bool] = mapped_column(Boolean, default=False)  # C
-    body_comp_reasons: Mapped[list] = mapped_column(JsonText)  # C 的原因；正常时为 []
-
-    __table_args__ = (
-        UniqueConstraint(
-            "student_id", "computed_on", name="uq_derived_metrics_student_day"
-        ),
-    )
-
-
-class StratificationResult(Base):
-    """红黄绿分层结果（含 ``insufficient_data``），逐人逐日一条。
-
-    ``hit_rules`` 的语义必须读清楚：它是**本次求值评估过的规则 ID 序列**，逗号分隔
-    （如 ``"R1,R2,Y1"``），**最后一项才是命中的那条**——**Z0 闸门 + 7 条分层规则**
-    自上而下求值、命中即停，所以最多只可能命中一条。保留已评估但未命中的前缀不是
-    冗余：它正是回答「这个学生为什么不是红色层」的证据（spec §4.3 要求的可追溯性），
-    也是 ``explain()`` 生成中文文案的依据。
-
-    **前缀的构成（Ruling 132）**：``Z0`` 命中时本列**恰为 ``"Z0"``**、只有这一项
-    （闸门未评估任何分层规则）；``Z0`` 未命中时本列是**已评估的 7 条分层规则序列**、
-    最后一项即命中者、**不含 ``Z0``**（``"R1,R2,Y1"`` 而不是 ``"Z0,R1,R2,Y1"``）。
-    故最长取值是 ``"R1,R2,Y1,Y2,Y3,Y4,G1"`` = **20 字符**（7 个两字符 ID + 6 个逗号；
-    实测 500 人整批的最大长度就是 20——fix round 3 复跑：把 ``stratify_dataset`` 的 500 人
-    产出按 ``,``.join 后量，``max = 20``、长度集合 ``{2, 5, 8, 11, 14, 17, 20}``，七档
-    「已评估前缀」逐档都在，最长的那条正是 ``R1,R2,Y1,Y2,Y3,Y4,G1``。**这个 20 不被
-    守卫**：``hit_rules`` 列没有取值域 CHECK，故 ``tests/db/test_models.py`` 的列宽遍历
-    测试扫不到它；128 的余量靠的是 20 ≪ 128 这个量级差，不是断言），``String(128)`` 充裕。
-
-    **``insufficient_data`` 时 ``hit_rules`` 恰为 ``"Z0"``，任何路径都至少有一项**
-    （Ruling 125，**不是空串**）：``explain()`` 按 ``hit_rules[-1]`` 取文案，空串会让
-    学生端点开「为什么我没有分层结果」时当场 ``IndexError``——而 ``Z0`` 恰恰是最需要
-    向学生解释的那条路径。Task 9 已用变异实证过这一崩溃。
-
-    ``input_snapshot`` 存判定当时的全部输入（W、C、valid_count、趋势、主导素质桶、
-    各项得分与所用百分位等），使任一条结果都能离线复算，不必回到当天的原始数据。
-
-    **``uq_stratification_result_student_day``（Ruling 212）**：``(student_id, computed_on)``
-    唯一。理由、机制与实测证据见 :class:`DerivedMetrics` 的 docstring（两张派生表同一条
-    缺陷、同一道约束）：本表的自然键与重放的幂等键 ``(semester_id, business_date)``
-    **不同维度**，跨学期重跑同一业务日期会留下两套「当前」分层，而
-    ``ORDER BY computed_on DESC LIMIT 1`` 稳定取到陈旧那一套。
-
-    ⚠️ **``init_db`` 用 ``create_all``，对已存在的表不会补约束/索引**：本约束只对**新建**
-    的库生效，已有的 ``pe.db`` 必须重建或手工 ``CREATE UNIQUE INDEX``。
-    """
-
-    __tablename__ = "stratification_result"
-
-    LABELS: set[str] = {"red", "yellow", "green", "insufficient_data"}
-    # ``"none"`` = 本条结果**没有用过任何判定线**（``valid_count = 0``，Z0 闸门直接拦下）。
-    # 它不是第三种数据来源，而是「无来源」：若拿 ``"school"`` 去填，教师大屏会说「这个
-    # 人的判定线来自校内百分位」，而他根本没有判定线——那是一条凭空造出的可追溯性。
-    # ``String(8)`` 够宽（最长的 ``"national"`` 恰 8 字符）。
-    PERCENTILE_SOURCES: set[str] = {"school", "national", "none"}
-
-    id: Mapped[int] = mapped_column(primary_key=True)
-    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
-    computed_on: Mapped[dt.date] = mapped_column(Date)
-    batch_id: Mapped[int] = mapped_column(
-        ForeignKey("daily_sync_run.id"), index=True
-    )
-    label: Mapped[str] = mapped_column(String(20))
-    hit_rules: Mapped[str] = mapped_column(
-        String(128),
-        comment="逗号分隔的规则 ID 序列；最后一项为命中者，前缀是已评估但未命中的规则",
-    )
-    input_snapshot: Mapped[dict] = mapped_column(JsonText)
-    # 本条结果**实际用过**的那些判定线行的来源汇总（Ruling 137）：一项都没用过 →
-    # ``"none"``；用过 1–3 项（Z0 命中但确实用过判定线）与用过 6 项同一条规则——
-    # 6 项混用 school / national 时**任一项降级即 ``"national"``**（保守侧：告诉教师
-    # 「这个人的判定线里有人是兜底来的」比反过来安全）。生产者见
-    # ``app.domain.percentile.summarize_source``。
-    percentile_source: Mapped[str] = mapped_column(String(8))
-    valid_from: Mapped[dt.date] = mapped_column(Date)  # 生效起
-    valid_to: Mapped[dt.date | None] = mapped_column(Date)  # 生效止；仍生效时为 NULL
-
-    __table_args__ = (
-        _in_domain("label", LABELS, "ck_stratification_result_label"),
-        _in_domain(
-            "percentile_source",
-            PERCENTILE_SOURCES,
-            "ck_stratification_result_percentile_source",
-        ),
-        UniqueConstraint(
-            "student_id", "computed_on", name="uq_stratification_result_student_day"
-        ),
-    )
-
-
-# ---------------------------------------------------------------------------
-# spec §4.6 预警与运维（本计划只落运维两张表，alert / notification 属计划 03）
-# ---------------------------------------------------------------------------
-
-
-class DailySyncRun(Base):
-    """一次每日批处理的运行记录，同时是全管道幂等键的载体。
-
-    ``(semester_id, business_date)`` 唯一：同一天重跑必须落到同一行。管道据此先按
-    ``batch_id`` 删掉派生行再重写，重放才是幂等的；否则同一学生同一天会累积出多条
-    分层结果，红黄绿分布随之失真。
-
-    计数列一律 ``default=0`` 而非可空：运行记录常在跑完之前就已入库（拿 ``id`` 当
-    ``batch_id`` 用），此时计数是「还没数」而不是「未知」，0 比 NULL 更诚实，也让
-    下游求和时不必处处防 None。
-    """
-
-    __tablename__ = "daily_sync_run"
-
-    STATUSES: set[str] = {"success", "partial", "failed"}
-
-    id: Mapped[int] = mapped_column(primary_key=True)
-    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
-    business_date: Mapped[dt.date] = mapped_column(Date)  # 与 semester_id 组成唯一约束
-    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
-    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
-
-    # 各源抽取条数
-    extracted_fitness: Mapped[int] = mapped_column(Integer, default=0)
-    extracted_body_comp: Mapped[int] = mapped_column(Integer, default=0)
-    extracted_survey: Mapped[int] = mapped_column(Integer, default=0)
-    # 清洗计数
-    dropped_count: Mapped[int] = mapped_column(Integer, default=0)  # 剔除数
-    corrected_count: Mapped[int] = mapped_column(Integer, default=0)  # 修正数
-    # 分层分布计数。spec §4.6 只写「红黄绿」，这里补 insufficient_count：
-    # 标签域是四个值，少一列就会让「本日没分层的人」在运维记录里凭空消失。
-    red_count: Mapped[int] = mapped_column(Integer, default=0)
-    yellow_count: Mapped[int] = mapped_column(Integer, default=0)
-    green_count: Mapped[int] = mapped_column(Integer, default=0)
-    insufficient_count: Mapped[int] = mapped_column(Integer, default=0)
-    # 下面两列由计划 02（处方）与计划 03（预警）写入；spec §4.6 已把它们列在本表，
-    # 故此处只留计数列，不提前建 prescription / alert 表。
-    prescription_count: Mapped[int] = mapped_column(Integer, default=0)  # 处方生成数
-    alert_count: Mapped[int] = mapped_column(Integer, default=0)  # 预警触发数
-
-    # status 同样有默认值（Ruling 30），理由与计数列一致：本列 NOT NULL，而运行记录
-    # 常在跑完之前就已入库（要先拿到 id 当 batch_id 用），此时它还没有真实结局。
-    # 默认取 "failed" 而不是 "success"，是保守方向：进程崩在中途时，这一行留下的
-    # 就是 "failed"——崩溃被记成失败只是难看，被记成成功则是谎报一次并没有发生的
-    # 完整运行，而下游看 status 决定是否要重跑，谎报成功会让这一天永远不再重跑。
-    status: Mapped[str] = mapped_column(String(8), default="failed")
-    error_summary: Mapped[str | None] = mapped_column(Text)  # 错误摘要
-
-    __table_args__ = (
-        UniqueConstraint(
-            "semester_id",
-            "business_date",
-            name="uq_daily_sync_run_semester_business_date",
-        ),
-        _in_domain("status", STATUSES, "ck_daily_sync_run_status"),
-    )
-
-
-class CleaningLog(Base):
-    """每一条被剔除或被修正的数据的交代（spec §4.6）。
-
-    不是过度设计：一个要发论文、要结题、要向省内高校推广的研究项目，必须能回答
-    「这条数据为什么没了」。``kind`` 与 Task 5 的 ``CleaningEntry.kind`` 同域。
-
-    原值与处理后值用 :class:`JsonText` 而不是裸 ``Text``：清洗条目的值是 ``object``
-    （数值、字符串或 ``None``），JSON 编码能原样保住类型与 ``None`` 的语义。若直接
-    ``str(value)`` 落成文本，``str(None)`` 会把「缺失」写成字符串 ``"None"``——那是
-    审计记录里最难被发现的一类谎报。这两列也是 :class:`JsonText` 存在的直接理由：
-    SQLAlchemy 自带的 ``JSON`` 类型在 SQLite 上会把 ``0.0`` 这类标量按 NUMERIC 亲和性
-    改写成原生数值（实测读回 ``int 0``），审计记录里的「原值」因此不再等于原值。
-
-    学号用双列承载（Ruling 25）：``student_no`` 非空、逐字节照抄收到的原始学号，
-    ``student_id`` 可空、只在学号能解析到 ``student`` 表时才填。**学号解析不出来的
-    那条记录，本身就是最该留痕的数据质量问题**：若把 ``student_id`` 做成非空外键，
-    孤儿学号的审计记录会被约束直接挡在库外，最该被看见的那一类问题反而被静默吞掉，
-    而 spec §4.6「必须能交代每一条被剔除或修正的数据」恰恰在这一类上失守。Task 5 的
-    ``CleaningEntry.student_no`` 是 ``str``，双列也让清洗结果不必先解析成功才落库。
-    """
-
-    __tablename__ = "cleaning_log"
-
-    KINDS: set[str] = {
-        "missing_dropped",
-        "outlier_corrected",
-        "unit_normalized",
-        "duplicate_removed",
-    }
-
-    id: Mapped[int] = mapped_column(primary_key=True)
-    sync_run_id: Mapped[int] = mapped_column(ForeignKey("daily_sync_run.id"))
-    student_no: Mapped[str] = mapped_column(String(32))  # 原始学号，不做 strip / 补零
-    student_id: Mapped[int | None] = mapped_column(ForeignKey("student.id"))  # 解析得到才填
-    field: Mapped[str] = mapped_column(String(32))  # 出问题的字段名
-    # 值域是标量或 None；标注取最常见形态，实际由 JsonText 承载，不做运行期检查
-    original_value: Mapped[float | str | None] = mapped_column(JsonText)
-    processed_value: Mapped[float | str | None] = mapped_column(JsonText)
-    kind: Mapped[str] = mapped_column(String(24))
-    reason: Mapped[str] = mapped_column(Text)
-
-    __table_args__ = (_in_domain("kind", KINDS, "ck_cleaning_log_kind"),)
diff --git a/backend/app/db/models/__init__.py b/backend/app/db/models/__init__.py
new file mode 100644
index 0000000..75d1919
--- /dev/null
+++ b/backend/app/db/models/__init__.py
@@ -0,0 +1,91 @@
+"""14 张表的 ORM 模型（字段清单严格按 spec §4.1–§4.3、§4.6）。
+
+三条贯穿全表的约定，改动前请先读完：
+
+1. **缺测就是 ``NULL``，绝不是 0**（Ruling 21）。所有原始测量值与国标单项得分一律
+   声明为可空。0 是数值列最常见的缺测占位，而 50 米跑与耐力跑各占 20% 权重：把缺测
+   当 0 分入库，等于给体能最差的学生送上 40% 权重的满分，还同时抹掉两个能力桶的短板
+   ——而且它抬分不压分，不会被「成绩异常低」的直觉发现。「有效项数」由
+   ``derived_metrics.valid_count`` 显式承载，不靠 0 值反推。
+
+2. **枚举取值域两处设防**。每个枚举式列都同时给出类常量集合（供 Python 侧校验与测试
+   断言）与 SQL 层 ``CheckConstraint``（让数据库自己拒绝脏值）。类常量是唯一真相，
+   约束文本由 :func:`_in_domain` 从类常量生成，两者不可能各说各话。
+
+3. **JSON 形态的列一律用 :class:`JsonText`**（八个列，无一例外）。SQLite 没有原生
+   JSON，该类型以 ``TEXT`` 为底层、由它自己负责 dumps/loads，调用方拿到手的直接是
+   原样的 ``dict`` / ``list`` / 标量，与 domain 层的值对象（如
+   ``DerivedResult.annual_change: dict[str, float]``）同构，不必各自再约定一套序列化
+   格式——那正是口径漂移的温床。为什么不用 SQLAlchemy 自带的 ``JSON`` 类型，见
+   :class:`JsonText` 的 docstring（SQLite 的 NUMERIC 亲和性会改写标量）。
+
+本包的六个表模块都不声明任何 ``relationship``：管道按 ``batch_id`` 批量读写，显式 ``select`` 比
+懒加载更可预测，也不会在 Session 关闭后触发意外的延迟查询。
+
+**本包是 2026-10 的一次拆包（Plan 02 Task 1）**，此前 14 张表同住一个 676 行的
+``models.py``。小节划分严格按 spec §4：
+
+=========================  ==========================================
+模块                        spec 小节与内容
+=========================  ==========================================
+:mod:`.organisation`        §4.1 组织与身份（5 张）
+:mod:`.assessment`          §4.2 学期节点数据（4 张）
+:mod:`.derived`             §4.3 派生与分层（3 张）
+:mod:`.prescription`        §4.4 处方（**今天为空**，Plan 02 Task 2/3/9 填）
+:mod:`.feedback`            §4.5 反馈（**今天为空**，Plan 03 填）
+:mod:`.ops`                 §4.6 预警与运维（2 张）
+:mod:`._shared`             跨小节共享的 ``JsonText`` 与 ``_in_domain``
+=========================  ==========================================
+
+**``from app.db import models`` 的导入面逐字未变**：``models.Student``、``models.Base``、
+``models.JsonText``、``models._in_domain`` 全部照旧可用。这一点由
+``tests/db/test_models.py::test_models_public_namespace_is_unchanged_by_the_split``
+钉住——它把拆包**之前**实测的 33 个公有名（``sorted(n for n in dir(models) if not
+n.startswith("_"))``，Plan02 Ruling 1 的可执行判据）字面写进测试，拆包后逐字比对。
+唯一的新增名是六个子模块本身（``models.organisation`` 等），那是包的结构性属性、
+不是导入面，测试里显式排除并断言排除集与基线不相交。
+
+⚠️ **子模块刻意不定义 ``__all__``**：本文件用 ``from .x import *`` 重导出，于是包的公有
+名恰好等于「各子模块自己需要的那些 import 的并集」——这正是拆包前单模块的语义。哪个子
+模块一旦定义了 ``__all__``，``import *`` 就会被它截断、并集缩小，上面那条测试当场变红。
+所以**不要给子模块加 ``__all__``**；要收窄导入面，先改那条测试的判据并说明理由。
+
+⚠️ **本仓不做迁移，schema 改动 = 重建库**：``init_db`` 走 ``Base.metadata.create_all``，
+它对**已存在**的表既不补列、也不补索引/约束（详见 :func:`app.db.session.init_db` 的
+docstring）。没有 Alembic，也不打算有。``backend/pe.db`` 不入库（``.gitignore``），故这
+对版本控制没有影响；但本地已经生成过库的人，改完 schema 必须删掉 ``pe.db`` 重跑
+``python -m app.seed.generate``，否则新列在旧库上根本不存在。
+"""
+
+# _in_domain 带前导下划线，`import *` 不会带它过来；显式重导出以保持
+# `app.db.models._in_domain` 这个既有写法可用（tests/db/test_models.py 的注释引用它）。
+from ._shared import _in_domain  # noqa: F401
+
+# 六个子模块刻意不定义 __all__，故 `import *` 带过来的是它们各自命名空间里的全部公有名，
+# 其并集 == 拆包前单模块 models.py 的公有名集合（见上方 docstring 与那条基线测试）。
+from ._shared import *  # noqa: F401,F403
+from .organisation import *  # noqa: F401,F403
+from .assessment import *  # noqa: F401,F403
+from .derived import *  # noqa: F401,F403
+from .ops import *  # noqa: F401,F403
+
+# 两个今天为空的小节也要被导入：它们的模块 docstring 是「这里为什么没有表」的唯一交代，
+# 而 `app.db.models.prescription` 这个属性名要让 Plan 02 Task 2/3 直接可用。
+from . import feedback, prescription  # noqa: F401
+
+__all__ = [
+    "Semester",
+    "Teacher",
+    "Student",
+    "CourseSection",
+    "Enrollment",
+    "FitnessTestBatch",
+    "FitnessTestResult",
+    "BodyComposition",
+    "InterestSurvey",
+    "PercentileSnapshot",
+    "DerivedMetrics",
+    "StratificationResult",
+    "DailySyncRun",
+    "CleaningLog",
+]
diff --git a/backend/app/db/models/_shared.py b/backend/app/db/models/_shared.py
new file mode 100644
index 0000000..1172848
--- /dev/null
+++ b/backend/app/db/models/_shared.py
@@ -0,0 +1,65 @@
+"""``app.db.models`` 包内共享的两件基础设施：JSON 列类型与取值域约束生成器。
+
+拆包（Plan 02 Task 1）之前它们与 14 张表同住一个 ``models.py``。放这里而不是塞进六个
+表模块里的某一个，是因为**四个**表模块都要用它们（``organisation`` / ``assessment`` /
+``derived`` / ``ops``）：塞进任何一个都会让另外三个为了拿一个工具而 import 一个与它
+毫无关系的小节（例如 ``derived`` 为了 ``JsonText`` 去 import ``organisation``）。
+
+模块名带前导下划线，故它不出现在包 ``__init__`` 那份「公有导入面」基线里
+（Plan02 Ruling 1 的判据是 ``sorted(n for n in dir(models) if not n.startswith("_"))``）。
+"""
+
+import json
+from collections.abc import Iterable
+from typing import Any
+
+from sqlalchemy import CheckConstraint, Text
+from sqlalchemy.types import TypeDecorator
+
+
+def _in_domain(column: str, allowed: Iterable[str], name: str) -> CheckConstraint:
+    """由类常量集合生成 SQL 层的取值域约束。
+
+    约束文本从集合生成而不是手写第二遍：手写两遍迟早会漂移，而漂移是静默的——
+    Python 侧放行的值数据库拒收，或反过来数据库放进了 Python 侧读不懂的值。
+    取值按字典序排序，使 DDL 文本稳定可复现（同 seed 同 DDL）。
+    """
+    quoted = ", ".join("'" + v.replace("'", "''") + "'" for v in sorted(allowed))
+    return CheckConstraint(f"{column} IN ({quoted})", name=name)
+
+
+class JsonText(TypeDecorator):
+    """把 Python 的 ``dict`` / ``list`` / 标量以 JSON 文本存进 ``TEXT`` 列。
+
+    **为什么不直接用 SQLAlchemy 自带的 ``JSON`` 类型**：它在 SQLite 上渲染成
+    ``JSON``，而 SQLite 的亲和性规则里 ``JSON`` 落到 **NUMERIC** 亲和性——凡「看起来
+    像数字」的值会被就地转成原生数值存进去，不再是 JSON 文本。实测（Python 3.11.1 /
+    SQLAlchemy 2.1.1 / SQLite；探针 = 建一张只有一个 ``JSON`` 列的表、写四个标量后读
+    ``select id, typeof(v), v``）：``0.0`` 与 ``65.0`` **都**落 ``typeof='integer'``、
+    读回来是 Python ``int`` ``0`` / ``65``（浮点被降成整型），``65.5`` 与 ``65.0000001``
+    才落 ``typeof='real'``——NUMERIC 亲和性把**能无损表示成整数**的实数降成整型、其余留
+    ``real``。本段此前印的是「``65.0`` 存成 ``real`` 而非文本」，那与它自己下一句的结论
+    相反：真存成 ``real 65.0`` 的话读回仍是 ``65.0``，「原值 65.0 kg」就不会被记成
+    「原值 65」——正是**降成整型**才造成失真。这条探针**不在测试网里、不被守卫**
+    （本仓没有任何测试用 SQLAlchemy 自带的 ``JSON`` 类型），属历史实测，fix round 3 复跑。
+    对 ``cleaning_log`` 这种存标量的审计列，这是实打实的失真，而审计记录的全部价值就在于
+    原值不被改写。
+
+    以 ``TEXT`` 为底层类型即绕开亲和性转换，同时保留透明 dumps/loads：调用方拿到手的
+    仍是原样的 Python 对象，全库八个 JSON 形态的列共用这一种落法，不必区分「这一列
+    要不要自己 ``json.dumps``」——那种不对称正是会被忘掉、且忘掉后静默出错的地方。
+    ``ensure_ascii=False`` 让中文原样落库，用 sqlite3 命令行直接看审计记录时可读。
+    ``None`` 存 SQL ``NULL`` 而不是 ``'null'`` 文本，读回也是 ``None``。
+
+    ``cache_ok = True`` 是必需的：缺了它 SQLAlchemy 会对每条用到该列的语句发
+    ``SAWarning``（该类型无法生成缓存键），在 ``-W error`` 下直接变成失败。
+    """
+
+    impl = Text
+    cache_ok = True
+
+    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
+        return None if value is None else json.dumps(value, ensure_ascii=False)
+
+    def process_result_value(self, value: Any, dialect: Any) -> Any:
+        return None if value is None else json.loads(value)
diff --git a/backend/app/db/models/assessment.py b/backend/app/db/models/assessment.py
new file mode 100644
index 0000000..946bc95
--- /dev/null
+++ b/backend/app/db/models/assessment.py
@@ -0,0 +1,187 @@
+"""spec §4.2 学期节点数据（低频，来自乐跑）：体测批次、体测成绩、体成分、兴趣问卷。
+
+Plan 02 Task 1 从单文件 ``app/db/models.py`` 拆包而来，内容逐字搬运。
+三条贯穿全表的约定写在包的 docstring 里：:mod:`app.db.models`。
+"""
+
+import datetime as dt
+
+from sqlalchemy import (
+    Date,
+    Float,
+    ForeignKey,
+    Integer,
+    String,
+    UniqueConstraint,
+)
+from sqlalchemy.orm import Mapped, mapped_column
+
+from app.db.session import Base
+
+from ._shared import JsonText, _in_domain
+
+
+# ---------------------------------------------------------------------------
+# spec §4.2 学期节点数据（低频，来自乐跑）
+# ---------------------------------------------------------------------------
+
+
+class FitnessTestBatch(Base):
+    """一次体测批次。``timepoint`` 是学期内的三个采集节点。"""
+
+    __tablename__ = "fitness_test_batch"
+
+    TIMEPOINTS: set[str] = {"week1", "week8", "week16"}
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
+    timepoint: Mapped[str] = mapped_column(String(8))
+    test_date: Mapped[dt.date] = mapped_column(Date)
+    # 下面两项来自源系统、可能整列缺失，故可空（见模块 docstring 的可空性原则）
+    source: Mapped[str | None] = mapped_column(String(32))  # 来源系统
+    academic_year: Mapped[str | None] = mapped_column(String(16))  # 学年
+
+    __table_args__ = (
+        _in_domain("timepoint", TIMEPOINTS, "ck_fitness_test_batch_timepoint"),
+    )
+
+
+class FitnessTestResult(Base):
+    """一名学生在某批次里的 8 项原始测量、7 项国标计分项得分、总分与等级。
+
+    8 → 7 → 6 的口径见 spec §4.2：身高与体重合成 BMI 一项计分，故 8 项原始测量对应
+    7 个计分项；短板判定又排除 BMI（避免与体成分 ``C`` 重复计数），故只有 6 项进
+    ``derived_metrics`` 的 ``W``。得分列名一律是 ``score_`` + ``ScoredItem`` 的值，
+    管道可用 ``getattr(row, f"score_{item.value}")`` 逐项取用，不必再维护一张映射表。
+
+    指向体测批次的外键**刻意不叫** ``batch_id`` 而叫 ``test_batch_id``（Ruling 31）：
+    本项目里 ``batch_id`` 一词专指「指向 ``daily_sync_run`` 的外键」，也就是
+    :func:`app.db.repo.delete_by_batch` 可据以删除的归属键，只有三张派生表才允许拥有
+    它。若本表也叫 ``batch_id``，误调 ``delete_by_batch(session, FitnessTestResult,
+    sync_run_id)`` 时——``fitness_test_batch.id`` 只有 1/2/3（week1/week8/week16），
+    而 ``daily_sync_run.id`` 按业务日递增（一学期 1…112）——凡 ``sync_run_id ∈ {1, 2,
+    3}`` 都会匹配上并**静默删掉真实源体测数据**：两列都是 int，外键拦不住（每个值各自
+    合法），``AttributeError`` 也拦不住（属性存在）。删源数据比删派生行严重得多——派生
+    行重算就回来了，源体测数据删了就是删了。改名后这一脚踩下去是响亮的
+    ``AttributeError``，与 ``CleaningLog`` 用 ``sync_run_id`` 的既有设计同一口径。
+    """
+
+    __tablename__ = "fitness_test_result"
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    # 体测批次（week1/week8/week16 的测试事件），不是 daily_sync_run，故不叫 batch_id
+    test_batch_id: Mapped[int] = mapped_column(ForeignKey("fitness_test_batch.id"))
+    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
+    # **这一列是「本条成绩是哪一天测的」的唯一所有者**（Plan 02 Task 1，终审 B 的 M1）。
+    # 源记录本来就带它（``RawFitnessRecord.tested_on``，同时是适配器的增量水位线字段），
+    # 但 Plan 01 只把它写进了 ``fitness_test_batch.test_date`` —— 那是**一个批次一个值**，
+    # 而一个 week1 批次的记录横跨好几个采集日。后果是 ``cohort_from_db`` 无法按日期截断：
+    # 重跑一个**更早**的业务日期时，``_results_of`` 会把整个批次的记录全读回来，包括
+    # 那些测量日**晚于** as_of 的行——用未来的数据算过去的分层。终审实测 60 人里
+    # **12 人 label 不同**。加上本列后 ``percentile_stage._results_of`` 多一句
+    # ``.where(FitnessTestResult.tested_on <= as_of)``，守卫是
+    # ``tests/pipeline/test_percentile_stage.py::test_cohort_truncates_results_by_tested_on``。
+    #
+    # ``fitness_test_batch.test_date`` **不删**：加了本列之后它的唯一职责变成
+    # ``assessment_anchor`` 的**排序键**（挑「<= as_of 的最新一个 week1 批次」），
+    # 而一个随执行顺序漂移的排序键是不可接受的——故 Step 5 同时把 ``daily._fitness_batch``
+    # 的 upsert 改成 ``min(现有值, 本条值)`` 折叠，使它不再随抽取窗口漂移。
+    #
+    # NOT NULL 且无缺省：每条源记录都带 ``tested_on``（Ruling 41 让适配器**无条件**校验并
+    # 归一化它，空单元格在抽取阶段就抛 ``ValueError``），故生产路径上不存在「不知道哪天测的」
+    # 的成绩行。做成可空的代价是 ``tested_on <= as_of`` 对 NULL 恒为假、那一行被静默丢掉，
+    # 而「静默少一个人」正是本列要消灭的缺陷形态。
+    #
+    # ⚠️ **破坏性 schema 改动**：已有的 ``pe.db`` 里那 3000 行（500 人 × 6 个采集日）没有
+    # 这一列，而 ``create_all`` 不给已存在的表补列，故**必须重建库**（见包 docstring）。
+    tested_on: Mapped[dt.date] = mapped_column(Date)
+
+    # —— 8 项原始测量（乐跑口径）——
+    height_cm: Mapped[float | None] = mapped_column(Float)  # 身高
+    weight_kg: Mapped[float | None] = mapped_column(Float)  # 体重
+    vital_capacity_ml: Mapped[float | None] = mapped_column(Float)  # 肺活量
+    sprint_50m_s: Mapped[float | None] = mapped_column(Float)  # 50 米跑
+    sit_and_reach_cm: Mapped[float | None] = mapped_column(Float)  # 坐位体前屈
+    standing_jump_cm: Mapped[float | None] = mapped_column(Float)  # 立定跳远
+    # 引体向上（男）/ 一分钟仰卧起坐（女）；0 次是合法真实值，只有 NULL 才是缺测
+    strength_count: Mapped[float | None] = mapped_column(Float)
+    distance_run_s: Mapped[float | None] = mapped_column(Float)  # 1000 米（男）/ 800 米（女）
+
+    # —— 7 项国标计分项得分（0–100，就低取档，Ruling 18）——
+    score_bmi: Mapped[int | None] = mapped_column(Integer)
+    score_vital_capacity: Mapped[int | None] = mapped_column(Integer)
+    score_sprint_50m: Mapped[int | None] = mapped_column(Integer)
+    score_sit_and_reach: Mapped[int | None] = mapped_column(Integer)
+    score_standing_jump: Mapped[int | None] = mapped_column(Integer)
+    score_pull_up_or_sit_up: Mapped[int | None] = mapped_column(Integer)
+    score_distance_run: Mapped[int | None] = mapped_column(Integer)
+
+    total_score: Mapped[int | None] = mapped_column(Integer)  # 国标总分（100 分制）
+    national_grade: Mapped[str | None] = mapped_column(String(16))  # 国标等级
+
+    # 一名学生在同一次体测事件里只可能有一条成绩（Ruling 24）。注意本表的
+    # test_batch_id 指向 fitness_test_batch（week1/week8/week16 的测试事件），与
+    # daily_sync_run 无关，故幂等重放不能靠 delete_by_batch 按批清理，只能靠这条业务
+    # 键兜底：**没有它**的话，Task 10 重跑同一业务日期时若对源表走裸 insert 而不是
+    # repo.upsert，同一名学生同一批次的成绩会静默翻倍（该约束加上之前实测 1 → 2 行、
+    # 无任何异常），百分位快照、短板计数与趋势随之全部失真。**加上之后它是响亮的**：
+    # fix round 3 复跑（裸 SQL 对同一 (student_id, test_batch_id) 插第二行）得
+    # ``sqlite3.IntegrityError: UNIQUE constraint failed: fitness_test_result.test_batch_id,
+    # fitness_test_result.student_id``、行数保持 1。故那句「1 → 2 行」是**改前**实测、
+    # 现由本约束守卫（守卫断言在 ``tests/db/test_models.py``：约束名与列序被逐字钉住）。
+    # 约束显式命名，是为了让报错与将来的迁移脚本能指名道姓地引用它。
+    __table_args__ = (
+        UniqueConstraint(
+            "test_batch_id", "student_id", name="uq_fitness_result_test_batch_student"
+        ),
+    )
+
+
+class BodyComposition(Base):
+    """体成分测量。骨骼肌指数入库但不参与异常判定（spec §14 待确认 #16）。"""
+
+    __tablename__ = "body_composition"
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
+    measured_on: Mapped[dt.date] = mapped_column(Date)
+    muscle_mass_kg: Mapped[float | None] = mapped_column(Float)  # 肌肉量
+    body_fat_pct: Mapped[float | None] = mapped_column(Float)  # 体脂率 %
+    smi: Mapped[float | None] = mapped_column(Float)  # 骨骼肌指数
+    weight_kg: Mapped[float | None] = mapped_column(Float)  # 体重
+    device: Mapped[str | None] = mapped_column(String(32))  # 测量设备
+
+    # 同一学生同一天只留一条体成分（Ruling 24）。本表没有 batch_id，重放翻倍同样只能
+    # 靠这条业务键挡住；一旦重复，C（体成分异常）的判定与异常率都会被同一份读数抬高，
+    # 而它不会报错——「异常率莫名偏高」比「异常率莫名偏低」更难被当成数据问题追查。
+    __table_args__ = (
+        UniqueConstraint(
+            "student_id", "measured_on", name="uq_body_composition_student_measured_on"
+        ),
+    )
+
+
+class InterestSurvey(Base):
+    """体育学习兴趣量表问卷（占位 5 维度 × 5 点李克特，spec §10.9）。"""
+
+    __tablename__ = "interest_survey"
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
+    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
+    filled_on: Mapped[dt.date] = mapped_column(Date)
+    total_score: Mapped[float] = mapped_column(Float)
+    dimensions: Mapped[dict] = mapped_column(JsonText)  # 各维度分，如 {"运动乐趣": 4.0}
+    raw_answers: Mapped[dict] = mapped_column(JsonText)  # 原始答题
+
+    # 同一学生同一学期同一天只留一份问卷（Ruling 24）。三列缺一不可：问卷可按学期
+    # 重复发放，只有「学期 + 填写日」一起才定位得到唯一的那一份。重复的问卷会同时
+    # 抬高样本量与同一个人的权重，兴趣维度均值随之漂移且不报错。
+    __table_args__ = (
+        UniqueConstraint(
+            "student_id",
+            "semester_id",
+            "filled_on",
+            name="uq_interest_survey_student_semester_filled_on",
+        ),
+    )
diff --git a/backend/app/db/models/derived.py b/backend/app/db/models/derived.py
new file mode 100644
index 0000000..c402d44
--- /dev/null
+++ b/backend/app/db/models/derived.py
@@ -0,0 +1,243 @@
+"""spec §4.3 派生与分层（可追溯核心）：百分位快照、派生指标、分层结果。
+
+Plan 02 Task 1 从单文件 ``app/db/models.py`` 拆包而来，内容逐字搬运。
+三条贯穿全表的约定写在包的 docstring 里：:mod:`app.db.models`。
+
+``percentile_snapshot.sex`` 的取值域复用 :attr:`.organisation.Student.SEXES`（唯一所有者），
+故本模块 import ``Student``；这是包内唯一的跨小节依赖。
+"""
+
+import datetime as dt
+
+from sqlalchemy import (
+    Boolean,
+    Date,
+    Float,
+    ForeignKey,
+    Integer,
+    String,
+    UniqueConstraint,
+)
+from sqlalchemy.orm import Mapped, mapped_column
+
+from app.db.session import Base
+
+from ._shared import JsonText, _in_domain
+from .organisation import Student
+
+
+# ---------------------------------------------------------------------------
+# spec §4.3 派生与分层（可追溯核心）
+# ---------------------------------------------------------------------------
+
+
+class PercentileSnapshot(Base):
+    """校内百分位快照。**物化而非实时计算**（spec §4.0）。
+
+    实时算会随人群变动漂移，而研究项目必须能复现任意一天的分层结果。列与 Task 7 的
+    ``PercentileRow`` 值对象一一对应，故 ``compute_snapshot`` 的输出可直接落库，
+    样本量不足 30 时降级来的国标常模行（``source = "national"``）亦然。
+
+    ``batch_id`` + 五列业务唯一键是它的幂等防线（Ruling 29）。此前本表是**唯一一张
+    会被物化、却在库层没有任何幂等机制**的表：既无 ``batch_id``（``delete_by_batch``
+    删不到它），也无唯一约束（重放翻倍不报错），只能靠 Task 10 的跨日复用逻辑加一条
+    行数断言兜着——那是纪律，不是机制；纪律会被下一次重构悄悄改掉，约束不会。
+
+    唯一键的五个列正是 Task 7 的分组键 ``(sex, age_group, item)`` 再加「哪个学期、
+    哪一天」：``compute_snapshot`` 对每个分组最多产出一行（7 个计分项在样本 < 30 时
+    整组降级为 ``source = "national"``，不是并存两行；``muscle_mass_kg`` **没有国标
+    常模可降级**，样本 < 30 时整组不产出行），故 ``source`` 不必进键，同一组同一天
+    也只可能有一行。
+    """
+
+    __tablename__ = "percentile_snapshot"
+
+    SOURCES: set[str] = {"school", "national"}
+
+    # 取值域与 ``app/domain/percentile.py`` 的 ``SnapshotMetric`` 一致：7 个国标计分项
+    # 加上 ``muscle_mass_kg``（肌肉量）。肌肉量**不是计分项**，故它不在 ``ScoredItem``
+    # 里；而 spec §6.3② 的 ``C`` 要用「同龄同性别肌肉量 P20」这条判定线，所以快照表
+    # 必须存得下它。此前本列是该表**唯一没有取值域约束**的业务列，也正是「库里存得下、
+    # 算不出来」这个缺陷形态的机制来源（Ruling 102/121）。与 ``Student.SEXES`` 同一条
+    # 处置：db 层不为一个取值集合引入跨层依赖，代价是两处需人工同步，由
+    # ``tests/db/test_models.py`` 的漂移测试钉住。
+    ITEMS: set[str] = {
+        "bmi",
+        "vital_capacity",
+        "sprint_50m",
+        "sit_and_reach",
+        "standing_jump",
+        "pull_up_or_sit_up",
+        "distance_run",
+        "muscle_mass_kg",
+    }
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
+    computed_on: Mapped[dt.date] = mapped_column(Date)
+    batch_id: Mapped[int] = mapped_column(
+        ForeignKey("daily_sync_run.id"), index=True
+    )
+    item: Mapped[str] = mapped_column(String(32))  # 指标，取 SnapshotMetric 的值
+    sex: Mapped[str] = mapped_column(String(8))
+    age_group: Mapped[str] = mapped_column(String(16))  # 国标年级组
+    p10: Mapped[float] = mapped_column(Float)
+    p20: Mapped[float] = mapped_column(Float)
+    p25: Mapped[float] = mapped_column(Float)  # 短板判定线：低于它即显性短板
+    p50: Mapped[float] = mapped_column(Float)
+    p75: Mapped[float] = mapped_column(Float)
+    sample_size: Mapped[int] = mapped_column(Integer)
+    source: Mapped[str] = mapped_column(String(8))
+
+    __table_args__ = (
+        _in_domain("source", SOURCES, "ck_percentile_snapshot_source"),
+        _in_domain("sex", Student.SEXES, "ck_percentile_snapshot_sex"),
+        _in_domain("item", ITEMS, "ck_percentile_snapshot_item"),
+        UniqueConstraint(
+            "semester_id",
+            "computed_on",
+            "item",
+            "sex",
+            "age_group",
+            name="uq_percentile_snapshot_group_day",
+        ),
+    )
+
+
+class DerivedMetrics(Base):
+    """派生指标：分层判定的直接输入，也是「逐人可追溯」链条的中间一环。
+
+    ``batch_id`` 指向 ``daily_sync_run``：幂等重放靠它按批删除本表与
+    ``stratification_result`` 的旧行（见 :func:`app.db.repo.delete_by_batch`）。
+    没有这一列，重跑同一天就只能靠「学生 + 日期」去猜哪些行属于哪一次运行。
+
+    **``uq_derived_metrics_student_day``（Ruling 212）**：``(student_id, computed_on)``
+    唯一。派生表的**自然键**是 ``(student_id, computed_on)``，而重放的**幂等键**是
+    ``(semester_id, business_date)`` —— **两个键不同维度**，``_replay_cleanup`` 只按
+    ``batch_id`` 删，跨学期删不到对方。于是「同一业务日期在两个 ``semester_id`` 下各跑一次」
+    会留下两套「当前」结果，而所有自然读法（``ORDER BY computed_on DESC LIMIT 1``）
+    都会**稳定取到陈旧那一套**（``computed_on`` 相同、无二级排序 → SQLite 按 rowid 升序扫
+    → 预跑那批 id 更小）。终审实测（60 人，第二次跑的 ``standing_jump_cm`` 减 60）：
+    ``stratification_result`` 120 行 / 60 学生 / **60 人各有两行同 ``computed_on``**、
+    ``COUNT(DISTINCT input_snapshot) = 2``。教师大屏 ``WHERE computed_on=? GROUP BY label``
+    会把 60 人的班报成 120 人。
+
+    终审已亲验：干净回放下 ``(student_id, computed_on)`` 在 **56000 行**上已经唯一
+    （``distinct = 56000``），故正常路径不会误伤，只有跨学期重跑才会响亮失败。
+    另一道闸是 CLI 的「``--date`` 必须落在 ``--semester`` 区间内」守卫
+    （:func:`app.pipeline.daily.require_dates_in_semester`）。
+
+    ⚠️ **``init_db`` 用 ``Base.metadata.create_all``，它对已存在的表不会补约束/索引**：
+    本约束只对**新建**的库生效。已有的 ``pe.db`` 必须重建（或手工
+    ``CREATE UNIQUE INDEX``），否则跨学期重跑仍然静默双写。
+    """
+
+    __tablename__ = "derived_metrics"
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
+    computed_on: Mapped[dt.date] = mapped_column(Date)
+    batch_id: Mapped[int] = mapped_column(
+        ForeignKey("daily_sync_run.id"), index=True
+    )
+
+    annual_change: Mapped[dict] = mapped_column(JsonText)  # 各指标年均变化率
+    # 列宽 **20** 而不是 16（Ruling 144）：``Trend.INSUFFICIENT.value`` =
+    # ``"insufficient_data"`` 是 **17** 字符，16 装不下。SQLite 不强制 ``VARCHAR`` 长度，
+    # 故它静默存下——而 500 人首批实测就有 209 行（41.8%）写这个 17 字符的值；换任何严格
+    # 长度的后端（MySQL / PostgreSQL）会截断成 ``"insufficient_dat"``，读回来
+    # ``Trend(...)`` 当场 ``ValueError``，**炸在读侧不在写侧**，离真因隔一整个批处理周期。
+    # 取 20 与 ``stratification_result.label`` 对齐：两列存的是同一族 17 字符的值。
+    # 守卫见 ``tests/db/test_models.py`` 的列宽遍历测试（硬规矩 #18）。
+    trend: Mapped[str] = mapped_column(String(20))  # 趋势标签（Task 8 的 Trend 值）
+    weaknesses: Mapped[list] = mapped_column(JsonText)  # 短板列表，元素为 ScoredItem 的值
+    weakness_count: Mapped[int] = mapped_column(Integer, default=0)  # W，分母恒为 6
+    valid_count: Mapped[int] = mapped_column(Integer, default=0)  # < 4 则本日不分层
+    body_comp_abnormal: Mapped[bool] = mapped_column(Boolean, default=False)  # C
+    body_comp_reasons: Mapped[list] = mapped_column(JsonText)  # C 的原因；正常时为 []
+
+    __table_args__ = (
+        UniqueConstraint(
+            "student_id", "computed_on", name="uq_derived_metrics_student_day"
+        ),
+    )
+
+
+class StratificationResult(Base):
+    """红黄绿分层结果（含 ``insufficient_data``），逐人逐日一条。
+
+    ``hit_rules`` 的语义必须读清楚：它是**本次求值评估过的规则 ID 序列**，逗号分隔
+    （如 ``"R1,R2,Y1"``），**最后一项才是命中的那条**——**Z0 闸门 + 7 条分层规则**
+    自上而下求值、命中即停，所以最多只可能命中一条。保留已评估但未命中的前缀不是
+    冗余：它正是回答「这个学生为什么不是红色层」的证据（spec §4.3 要求的可追溯性），
+    也是 ``explain()`` 生成中文文案的依据。
+
+    **前缀的构成（Ruling 132）**：``Z0`` 命中时本列**恰为 ``"Z0"``**、只有这一项
+    （闸门未评估任何分层规则）；``Z0`` 未命中时本列是**已评估的 7 条分层规则序列**、
+    最后一项即命中者、**不含 ``Z0``**（``"R1,R2,Y1"`` 而不是 ``"Z0,R1,R2,Y1"``）。
+    故最长取值是 ``"R1,R2,Y1,Y2,Y3,Y4,G1"`` = **20 字符**（7 个两字符 ID + 6 个逗号；
+    实测 500 人整批的最大长度就是 20——fix round 3 复跑：把 ``stratify_dataset`` 的 500 人
+    产出按 ``,``.join 后量，``max = 20``、长度集合 ``{2, 5, 8, 11, 14, 17, 20}``，七档
+    「已评估前缀」逐档都在，最长的那条正是 ``R1,R2,Y1,Y2,Y3,Y4,G1``。**这个 20 不被
+    守卫**：``hit_rules`` 列没有取值域 CHECK，故 ``tests/db/test_models.py`` 的列宽遍历
+    测试扫不到它；128 的余量靠的是 20 ≪ 128 这个量级差，不是断言），``String(128)`` 充裕。
+
+    **``insufficient_data`` 时 ``hit_rules`` 恰为 ``"Z0"``，任何路径都至少有一项**
+    （Ruling 125，**不是空串**）：``explain()`` 按 ``hit_rules[-1]`` 取文案，空串会让
+    学生端点开「为什么我没有分层结果」时当场 ``IndexError``——而 ``Z0`` 恰恰是最需要
+    向学生解释的那条路径。Task 9 已用变异实证过这一崩溃。
+
+    ``input_snapshot`` 存判定当时的全部输入（W、C、valid_count、趋势、主导素质桶、
+    各项得分与所用百分位等），使任一条结果都能离线复算，不必回到当天的原始数据。
+
+    **``uq_stratification_result_student_day``（Ruling 212）**：``(student_id, computed_on)``
+    唯一。理由、机制与实测证据见 :class:`DerivedMetrics` 的 docstring（两张派生表同一条
+    缺陷、同一道约束）：本表的自然键与重放的幂等键 ``(semester_id, business_date)``
+    **不同维度**，跨学期重跑同一业务日期会留下两套「当前」分层，而
+    ``ORDER BY computed_on DESC LIMIT 1`` 稳定取到陈旧那一套。
+
+    ⚠️ **``init_db`` 用 ``create_all``，对已存在的表不会补约束/索引**：本约束只对**新建**
+    的库生效，已有的 ``pe.db`` 必须重建或手工 ``CREATE UNIQUE INDEX``。
+    """
+
+    __tablename__ = "stratification_result"
+
+    LABELS: set[str] = {"red", "yellow", "green", "insufficient_data"}
+    # ``"none"`` = 本条结果**没有用过任何判定线**（``valid_count = 0``，Z0 闸门直接拦下）。
+    # 它不是第三种数据来源，而是「无来源」：若拿 ``"school"`` 去填，教师大屏会说「这个
+    # 人的判定线来自校内百分位」，而他根本没有判定线——那是一条凭空造出的可追溯性。
+    # ``String(8)`` 够宽（最长的 ``"national"`` 恰 8 字符）。
+    PERCENTILE_SOURCES: set[str] = {"school", "national", "none"}
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
+    computed_on: Mapped[dt.date] = mapped_column(Date)
+    batch_id: Mapped[int] = mapped_column(
+        ForeignKey("daily_sync_run.id"), index=True
+    )
+    label: Mapped[str] = mapped_column(String(20))
+    hit_rules: Mapped[str] = mapped_column(
+        String(128),
+        comment="逗号分隔的规则 ID 序列；最后一项为命中者，前缀是已评估但未命中的规则",
+    )
+    input_snapshot: Mapped[dict] = mapped_column(JsonText)
+    # 本条结果**实际用过**的那些判定线行的来源汇总（Ruling 137）：一项都没用过 →
+    # ``"none"``；用过 1–3 项（Z0 命中但确实用过判定线）与用过 6 项同一条规则——
+    # 6 项混用 school / national 时**任一项降级即 ``"national"``**（保守侧：告诉教师
+    # 「这个人的判定线里有人是兜底来的」比反过来安全）。生产者见
+    # ``app.domain.percentile.summarize_source``。
+    percentile_source: Mapped[str] = mapped_column(String(8))
+    valid_from: Mapped[dt.date] = mapped_column(Date)  # 生效起
+    valid_to: Mapped[dt.date | None] = mapped_column(Date)  # 生效止；仍生效时为 NULL
+
+    __table_args__ = (
+        _in_domain("label", LABELS, "ck_stratification_result_label"),
+        _in_domain(
+            "percentile_source",
+            PERCENTILE_SOURCES,
+            "ck_stratification_result_percentile_source",
+        ),
+        UniqueConstraint(
+            "student_id", "computed_on", name="uq_stratification_result_student_day"
+        ),
+    )
diff --git a/backend/app/db/models/feedback.py b/backend/app/db/models/feedback.py
new file mode 100644
index 0000000..1984334
--- /dev/null
+++ b/backend/app/db/models/feedback.py
@@ -0,0 +1,8 @@
+"""spec §4.5 反馈数据模型（**本模块今天刻意是空的**）。
+
+打卡记录、RPE、二次小测、班级周报（``weekly_class_report``，spec §4.7）全部属
+**Plan 03**，由它填充。Plan 02 Task 1 建这个模块只是为了让包的六个小节与 spec §4 的
+六个小节一一对应，读代码的人不必猜「反馈那部分去哪了」。
+
+留空而不是放占位类的理由见 :mod:`app.db.models.prescription` 的 docstring。
+"""
diff --git a/backend/app/db/models/ops.py b/backend/app/db/models/ops.py
new file mode 100644
index 0000000..2a0f903
--- /dev/null
+++ b/backend/app/db/models/ops.py
@@ -0,0 +1,169 @@
+"""spec §4.6 预警与运维：每日批处理运行记录、清洗审计。
+
+Plan 01 只落这两张表；``alert`` / ``notification`` 属计划 03。
+Plan 02 Task 1 从单文件 ``app/db/models.py`` 拆包而来，内容逐字搬运。
+三条贯穿全表的约定写在包的 docstring 里：:mod:`app.db.models`。
+"""
+
+import datetime as dt
+
+from sqlalchemy import (
+    Date,
+    DateTime,
+    ForeignKey,
+    Integer,
+    String,
+    Text,
+    UniqueConstraint,
+)
+from sqlalchemy.orm import Mapped, mapped_column
+
+from app.db.session import Base
+
+from ._shared import JsonText, _in_domain
+
+
+# ---------------------------------------------------------------------------
+# spec §4.6 预警与运维（本计划只落运维两张表，alert / notification 属计划 03）
+# ---------------------------------------------------------------------------
+
+
+class DailySyncRun(Base):
+    """一次每日批处理的运行记录，同时是全管道幂等键的载体。
+
+    ``(semester_id, business_date)`` 唯一：同一天重跑必须落到同一行。管道据此先按
+    ``batch_id`` 删掉派生行再重写，重放才是幂等的；否则同一学生同一天会累积出多条
+    分层结果，红黄绿分布随之失真。
+
+    计数列一律 ``default=0`` 而非可空：运行记录常在跑完之前就已入库（拿 ``id`` 当
+    ``batch_id`` 用），此时计数是「还没数」而不是「未知」，0 比 NULL 更诚实，也让
+    下游求和时不必处处防 None。
+    """
+
+    __tablename__ = "daily_sync_run"
+
+    STATUSES: set[str] = {"success", "partial", "failed"}
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
+    business_date: Mapped[dt.date] = mapped_column(Date)  # 与 semester_id 组成唯一约束
+    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
+    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
+
+    # 各源抽取条数
+    extracted_fitness: Mapped[int] = mapped_column(Integer, default=0)
+    extracted_body_comp: Mapped[int] = mapped_column(Integer, default=0)
+    extracted_survey: Mapped[int] = mapped_column(Integer, default=0)
+    # 清洗计数
+    dropped_count: Mapped[int] = mapped_column(Integer, default=0)  # 剔除数
+    corrected_count: Mapped[int] = mapped_column(Integer, default=0)  # 修正数
+    # 分层分布计数。spec §4.6 只写「红黄绿」，这里补 insufficient_count：
+    # 标签域是四个值，少一列就会让「本日没分层的人」在运维记录里凭空消失。
+    red_count: Mapped[int] = mapped_column(Integer, default=0)
+    yellow_count: Mapped[int] = mapped_column(Integer, default=0)
+    green_count: Mapped[int] = mapped_column(Integer, default=0)
+    insufficient_count: Mapped[int] = mapped_column(Integer, default=0)
+    # 缺肌肉量 P20 判定线的 (性别 × 年级组) 组数（Plan 02 Task 1，终审 C 组第 24 项）。
+    # 生产者是 ``app.pipeline.run_stratify.muscle_line_gaps``，由
+    # ``daily._stratify_and_persist`` 返回、``run_daily`` 写进本列。
+    #
+    # **它取代了此前写进 ``error_summary`` 的那段自由文本**（「注意（非错误）：N 个组没有
+    # 肌肉量 P20 判定线……」）。那段文本有两个毛病：① 列名与内容不符——它明写「非错误」
+    # 却住在 ``error_summary`` 里，于是一个只看列名的人会以为今天出了错；② 它是**文本**，
+    # 教师大屏要按组数排序或求和就得先把中文句子解析回一个整数。改成计数列之后两个毛病
+    # 一起消失，而 ``daily_sync_run`` 的其余计数列（``dropped_count`` / ``red_count`` …）
+    # 本来就是这个形状。
+    #
+    # **直接切、不与 ``error_summary`` 双写**（Plan02 Ruling 13；计划 Step 4 第 4 项留了
+    # 「保留一个 Task 周期两处同时写」的选项）。切之前自己复验过零消费者::
+    #
+    #     git grep -n "error_summary" -- backend/
+    #     git grep -n "注意（非错误）" -- backend/
+    #
+    # 基线 ``e26347f`` 上，「注意（非错误）」这段文本的写入点只有 ``daily.py:652-659``
+    # 一处，**读取点为零**：``daily.py:728-730`` 的 CLI 读的是 ``run.error_summary``
+    # 这个列（不区分内容），两条测试（``test_backfill.py:336`` 断言 ``"boom on 2025-09-04"``、
+    # ``test_daily.py:435`` 断言 ``"唯一约束"``）读的都是**真错误**那段，没有任何一处
+    # 断言过缺线提示。双写等于造出第二个所有者，而单一所有者是本计划 Global Constraints
+    # 的第一条。
+    #
+    # **「为什么会有缺线组」这段解释没有丢**，只是不再逐日复制一份进库里：机制写在
+    # ``app.domain.percentile.compute_snapshot`` 的 docstring（Ruling 121 第 4 步：该组
+    # InBody 样本 < ``MIN_SAMPLE = 30`` 时整组不产出快照行，而肌肉量**没有国标常模可降级**，
+    # 故这些组的 ``C`` 只由体脂率决定），逐人的痕迹仍在
+    # ``stratification_result.input_snapshot["snapshot_muscle_p20"] = null`` 里。
+    muscle_line_gaps: Mapped[int] = mapped_column(Integer, default=0)
+    # 下面两列由计划 02（处方）与计划 03（预警）写入；spec §4.6 已把它们列在本表，
+    # 故此处只留计数列，不提前建 prescription / alert 表。
+    # ⚠️ **Plan 01 就已经建好了这两列**（``models.py:614-615``），Plan 02 计划原文写的
+    # 「spec §4.6 明确列了……Plan 01 没建」与基线不符，故 Task 1 没有新增它们，只把
+    # ``alert_count`` 的现状写清楚：**本计划只建列不写值**，写入方是 Plan 03 的 Alert 阶段
+    # （spec §5 第 8 阶段）；在那之前它恒为 0，读它的人不得把 0 当成「今天没有预警」。
+    prescription_count: Mapped[int] = mapped_column(Integer, default=0)  # 处方生成数
+    alert_count: Mapped[int] = mapped_column(Integer, default=0)  # 预警触发数
+
+    # status 同样有默认值（Ruling 30），理由与计数列一致：本列 NOT NULL，而运行记录
+    # 常在跑完之前就已入库（要先拿到 id 当 batch_id 用），此时它还没有真实结局。
+    # 默认取 "failed" 而不是 "success"，是保守方向：进程崩在中途时，这一行留下的
+    # 就是 "failed"——崩溃被记成失败只是难看，被记成成功则是谎报一次并没有发生的
+    # 完整运行，而下游看 status 决定是否要重跑，谎报成功会让这一天永远不再重跑。
+    status: Mapped[str] = mapped_column(String(8), default="failed")
+    # **自 Plan 02 起本列只承载真错误**（``status == "failed"`` 那次运行的
+    # ``f"{type(exc).__name__}: {exc}"``）。此前它还兼着写「注意（非错误）：N 个组没有
+    # 肌肉量 P20 判定线……」这段自由文本——列名与内容不符，且它是个要被人再解析回整数的
+    # 数字。缺线组数改由上面的 :attr:`DailySyncRun.muscle_line_gaps` 计数列承载，
+    # 理由、零消费者的复验命令与「为什么不双写」都写在那一列的注释里（Plan02 Ruling 13）。
+    error_summary: Mapped[str | None] = mapped_column(Text)  # 错误摘要
+
+    __table_args__ = (
+        UniqueConstraint(
+            "semester_id",
+            "business_date",
+            name="uq_daily_sync_run_semester_business_date",
+        ),
+        _in_domain("status", STATUSES, "ck_daily_sync_run_status"),
+    )
+
+
+class CleaningLog(Base):
+    """每一条被剔除或被修正的数据的交代（spec §4.6）。
+
+    不是过度设计：一个要发论文、要结题、要向省内高校推广的研究项目，必须能回答
+    「这条数据为什么没了」。``kind`` 与 Task 5 的 ``CleaningEntry.kind`` 同域。
+
+    原值与处理后值用 :class:`JsonText` 而不是裸 ``Text``：清洗条目的值是 ``object``
+    （数值、字符串或 ``None``），JSON 编码能原样保住类型与 ``None`` 的语义。若直接
+    ``str(value)`` 落成文本，``str(None)`` 会把「缺失」写成字符串 ``"None"``——那是
+    审计记录里最难被发现的一类谎报。这两列也是 :class:`JsonText` 存在的直接理由：
+    SQLAlchemy 自带的 ``JSON`` 类型在 SQLite 上会把 ``0.0`` 这类标量按 NUMERIC 亲和性
+    改写成原生数值（实测读回 ``int 0``），审计记录里的「原值」因此不再等于原值。
+
+    学号用双列承载（Ruling 25）：``student_no`` 非空、逐字节照抄收到的原始学号，
+    ``student_id`` 可空、只在学号能解析到 ``student`` 表时才填。**学号解析不出来的
+    那条记录，本身就是最该留痕的数据质量问题**：若把 ``student_id`` 做成非空外键，
+    孤儿学号的审计记录会被约束直接挡在库外，最该被看见的那一类问题反而被静默吞掉，
+    而 spec §4.6「必须能交代每一条被剔除或修正的数据」恰恰在这一类上失守。Task 5 的
+    ``CleaningEntry.student_no`` 是 ``str``，双列也让清洗结果不必先解析成功才落库。
+    """
+
+    __tablename__ = "cleaning_log"
+
+    KINDS: set[str] = {
+        "missing_dropped",
+        "outlier_corrected",
+        "unit_normalized",
+        "duplicate_removed",
+    }
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    sync_run_id: Mapped[int] = mapped_column(ForeignKey("daily_sync_run.id"))
+    student_no: Mapped[str] = mapped_column(String(32))  # 原始学号，不做 strip / 补零
+    student_id: Mapped[int | None] = mapped_column(ForeignKey("student.id"))  # 解析得到才填
+    field: Mapped[str] = mapped_column(String(32))  # 出问题的字段名
+    # 值域是标量或 None；标注取最常见形态，实际由 JsonText 承载，不做运行期检查
+    original_value: Mapped[float | str | None] = mapped_column(JsonText)
+    processed_value: Mapped[float | str | None] = mapped_column(JsonText)
+    kind: Mapped[str] = mapped_column(String(24))
+    reason: Mapped[str] = mapped_column(Text)
+
+    __table_args__ = (_in_domain("kind", KINDS, "ck_cleaning_log_kind"),)
diff --git a/backend/app/db/models/organisation.py b/backend/app/db/models/organisation.py
new file mode 100644
index 0000000..3552277
--- /dev/null
+++ b/backend/app/db/models/organisation.py
@@ -0,0 +1,121 @@
+"""spec §4.1 组织与身份：学期、教师、学生、教学班、选课关系。
+
+Plan 02 Task 1 从单文件 ``app/db/models.py`` 拆包而来，内容逐字搬运。
+三条贯穿全表的约定（缺测就是 NULL、枚举取值域两处设防、JSON 列一律用 JsonText）
+写在包的 docstring 里：:mod:`app.db.models`。
+"""
+
+import datetime as dt
+
+from sqlalchemy import (
+    Boolean,
+    Date,
+    ForeignKey,
+    Integer,
+    String,
+    UniqueConstraint,
+)
+from sqlalchemy.orm import Mapped, mapped_column
+
+from app.db.session import Base
+
+from ._shared import _in_domain
+
+
+# ---------------------------------------------------------------------------
+# spec §4.1 组织与身份
+# ---------------------------------------------------------------------------
+
+
+class Semester(Base):
+    """学期：整条管道的日历骨架，业务日期的合法区间由它的起止日界定。"""
+
+    __tablename__ = "semester"
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    # 学期名同时是 CLI（--semester 2025-2026-1）与幂等键的查找键，故唯一
+    name: Mapped[str] = mapped_column(String(32), unique=True)
+    start_date: Mapped[dt.date] = mapped_column(Date)
+    # **排他**上界（Ruling 174）：学期区间是 ``[start_date, end_date)``，与 range/slice 的
+    # 惯例一致，也与 ``app.seed.config.semester_end_date`` 的算式（开学日 + 教学周数）自洽——
+    # 16 周 × 7 = 112 天对应的闭区间是 ``2025-09-01..2025-12-21``，而本列存的是
+    # ``2025-12-22``。故 ``app.pipeline.backfill`` 的 CLI 把它当闭区间上界用之前必须减一天
+    # （换算放在 CLI 层，不改 ``semester_end_date``：Task 6 冻结代码，它的算式本身是对的）。
+    # 注意 ``daily._semester_of`` / ``percentile_stage.current_semester_of`` 的区间查询仍是
+    # **闭**的（``end_date >= day``）：那两处要的是「包含某个测量日」，而最晚的测量日是
+    # ``week16`` = ``end_date - 7 天``，多含的那一天里没有任何数据。
+    end_date: Mapped[dt.date] = mapped_column(Date)
+    weeks: Mapped[int] = mapped_column(Integer)  # 教学周数，spec 固定 16
+    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
+
+
+class Teacher(Base):
+    """体育教师。工号是与教务系统对接的自然键。"""
+
+    __tablename__ = "teacher"
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    staff_no: Mapped[str] = mapped_column(String(32), unique=True)  # 工号
+    name: Mapped[str] = mapped_column(String(64))
+
+
+class Student(Base):
+    """学生。``sex`` / ``birth`` / ``grade`` 共同决定该查哪一张国标评分表。"""
+
+    __tablename__ = "student"
+
+    # 取值域与 app/domain/indicators.py 的 Sex 枚举一致（male / female）。这里不
+    # import 它：Task 3 的接口约定是「Consumes: 无」，db 层不为一个二元集合引入
+    # 跨层依赖。代价是两处需人工同步，已登记在任务报告的关切里。
+    SEXES: set[str] = {"male", "female"}
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    student_no: Mapped[str] = mapped_column(String(32), unique=True)  # 学号
+    name: Mapped[str] = mapped_column(String(64))
+    sex: Mapped[str] = mapped_column(String(8))
+    birth: Mapped[dt.date] = mapped_column(Date)  # 出生年月；龄组由它折算
+    department: Mapped[str | None] = mapped_column(String(64))  # 院系
+    grade: Mapped[int] = mapped_column(Integer)  # 年级 1–4
+
+    __table_args__ = (_in_domain("sex", SEXES, "ck_student_sex"),)
+
+
+class CourseSection(Base):
+    """教学班。阶段一的行政班与阶段二的分层班并存，靠 ``grouping_mode`` 区分。"""
+
+    __tablename__ = "course_section"
+
+    # administrative = 阶段一在行政班内分层；stratified = 阶段二跨班重编出来的
+    # 提升班 / 强化班 / 拓展班。同一批学生两套编班同时存在，演示时可切换。
+    GROUPING_MODES: set[str] = {"administrative", "stratified"}
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
+    teacher_id: Mapped[int] = mapped_column(ForeignKey("teacher.id"))
+    name: Mapped[str] = mapped_column(String(64))  # 课程名 / 分层班名
+    schedule_text: Mapped[str | None] = mapped_column(String(64))  # 上课时间
+    grouping_mode: Mapped[str] = mapped_column(String(16))
+
+    __table_args__ = (
+        _in_domain("grouping_mode", GROUPING_MODES, "ck_course_section_grouping_mode"),
+    )
+
+
+class Enrollment(Base):
+    """选课关系，对应厦大「三自主」选课：学期 × 学生 × 教学班。"""
+
+    __tablename__ = "enrollment"
+
+    id: Mapped[int] = mapped_column(primary_key=True)
+    semester_id: Mapped[int] = mapped_column(ForeignKey("semester.id"))
+    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
+    course_section_id: Mapped[int] = mapped_column(ForeignKey("course_section.id"))
+
+    __table_args__ = (
+        UniqueConstraint(
+            "semester_id",
+            "student_id",
+            "course_section_id",
+            name="uq_enrollment_semester_student_section",
+        ),
+    )
diff --git a/backend/app/db/models/prescription.py b/backend/app/db/models/prescription.py
new file mode 100644
index 0000000..7cb15fe
--- /dev/null
+++ b/backend/app/db/models/prescription.py
@@ -0,0 +1,16 @@
+"""spec §4.4 处方数据模型（**本模块今天刻意是空的**）。
+
+Plan 02 Task 1 建了这个模块但**没有往里放任何表**，因为处方的四张表分属后续任务：
+
+* ``prescription`` / ``prescription_template`` / ``training_package`` 由 **Task 2/3** 建
+  （模板与动作库先落地，处方表要引用它们）；
+* ``prescription_override``（教师覆盖）与 ``prescription`` 的触发/幂等列由 **Task 9** 建。
+
+留空而不是先建一个空类占位（Plan02 Ruling 5）：一个没有列的 ORM 类会被
+``Base.metadata.create_all`` 建成一张**零列以外的空表**，而
+``tests/db/test_models.py::test_all_fourteen_tables_created`` 用 ``==`` 钉住了表集合
+（Plan01 Ruling 28：用 ``==`` 而不是 ``>=``，正是为了抓「有人提前把计划 02 的表建进来」）。
+先建空类等于自己弄红那道守卫，而它红得毫无信息量。
+
+⚠️ 建表时请同时更新那道守卫的 ``expected`` 集合与它的「14 张」措辞。
+"""
diff --git a/backend/app/db/session.py b/backend/app/db/session.py
index c709c54..441fa1b 100644
--- a/backend/app/db/session.py
+++ b/backend/app/db/session.py
@@ -43,24 +43,51 @@ def _sqlite_foreign_keys_on(dbapi_connection, _record):
 
 
 class Base(DeclarativeBase):
     """全部 14 张表的声明基类。
 
     ``Base.metadata`` 是建表的唯一真相：表在 :mod:`app.db.models` 里声明一次，
     :func:`init_db` 据此 ``create_all``，不存在第二份需要手工同步的 DDL。
     """
 
 
-def engine(url: str = "sqlite:///pe.db") -> Engine:
-    """按 URL 造一个引擎。缺省落在 ``backend/pe.db``，即演示用的那个库。"""
+def engine(url: str) -> Engine:
+    """按 URL 造一个引擎。
+
+    ``url`` **没有缺省值**（Plan 02 Task 1，终审 C 组）。此前签名是
+    ``def engine(url: str = "sqlite:///pe.db")``，那个字面量是
+    :data:`app.config.DEFAULT_DB_URL` 的**第二个所有者**，而且是**相对路径**的那一个：
+    ``sqlite:///pe.db`` 由 CWD 决定落在哪个文件，从仓库根跑与从 ``backend/`` 跑会得到两个
+    不同的库，而两个都不报错——只是其中一个永远是空的（Plan01 Ruling 190 要消除的正是
+    这个形状）。缺省值删掉之后，「用哪个库」这个问题只能由调用方回答，而三个 CLI
+    （``app.seed.generate`` / ``app.pipeline.daily`` / ``app.pipeline.backfill``）都已经
+    显式传 :data:`app.config.DEFAULT_DB_URL`。
+
+    **删缺省值当天它是死代码**：基线 ``e26347f`` 上 ``git grep -n "engine(" -- backend/app``
+    报出的生产调用点只有 3 处（``app/pipeline/backfill.py`` / ``app/pipeline/daily.py`` /
+    ``app/seed/generate.py``），全部显式传 URL，没有任何一处依赖缺省值。删它的理由不是
+    「今天会错」，而是「它是一个活陷阱」：下一个写 ``engine()`` 的人会静默拿到一个取决于
+    CWD 的库。
+
+    ``url`` 缺失时是 ``TypeError``（响亮），不是回退到某个默认库（静默）。
+    """
     return create_engine(url)
 
 
 def init_db(eng: Engine) -> None:
     """在给定引擎上建出全部表；已存在的表原样跳过，故可重复调用。
 
     ``models`` 在函数体内才导入：它反过来要导入本模块的 :class:`Base`，
     放在模块顶层会构成导入环。
+
+    ⚠️ **``create_all`` 对已存在的表既不补列、也不补索引/约束**（SQLite 的
+    ``CREATE TABLE IF NOT EXISTS`` 语义，SQLAlchemy 不做 diff）。本仓**不做迁移**
+    （没有 Alembic，也不打算有），故 **schema 改动 = 重建库**：已有的 ``backend/pe.db``
+    必须删掉重新跑 ``python -m app.seed.generate``，否则新增的列/索引/约束在旧库上
+    **完全不存在**，而读写旧库的代码会以「列不存在」或「查询变慢」的形式在离真因很远的
+    地方炸开。``backend/pe.db`` 不入库（``.gitignore``），故这一条对版本控制没有影响，
+    只影响本地已经生成过库的人。两个 CLI 都**没有** ``--recreate`` 开关：删文件比重建
+    索引更诚实，而一个「帮你把库删了」的开关本身就是危险动作。
     """
     from app.db import models  # noqa: F401  仅为把 14 张表注册进 Base.metadata
 
     Base.metadata.create_all(eng)
diff --git a/backend/app/domain/indicators.py b/backend/app/domain/indicators.py
index 346a4f4..1794354 100644
--- a/backend/app/domain/indicators.py
+++ b/backend/app/domain/indicators.py
@@ -77,39 +77,150 @@ ITEM_WEIGHTS: dict[ScoredItem, int] = {
 ITEM_DISPLAY_NAMES: dict[ScoredItem, dict[Sex, str]] = {
     ScoredItem.BMI: {Sex.MALE: "BMI", Sex.FEMALE: "BMI"},
     ScoredItem.VITAL_CAPACITY: {Sex.MALE: "肺活量", Sex.FEMALE: "肺活量"},
     ScoredItem.SPRINT_50M: {Sex.MALE: "50 米跑", Sex.FEMALE: "50 米跑"},
     ScoredItem.SIT_AND_REACH: {Sex.MALE: "坐位体前屈", Sex.FEMALE: "坐位体前屈"},
     ScoredItem.STANDING_JUMP: {Sex.MALE: "立定跳远", Sex.FEMALE: "立定跳远"},
     ScoredItem.PULL_UP_OR_SIT_UP: {Sex.MALE: "引体向上", Sex.FEMALE: "1 分钟仰卧起坐"},
     ScoredItem.DISTANCE_RUN: {Sex.MALE: "1000 米跑", Sex.FEMALE: "800 米跑"},
 }
 
+# 计分项 → 原始测量列名。这张映射**无法从名字推导**（``pull_up_or_sit_up`` 对应的是
+# ``strength_count``），只能显式写出；写错的后果是按契约列序取值时 KeyError，当场炸开，
+# 不会静默产出一个缺列的文件。
+#
+# **只有 6 个短板判定项、没有 BMI**：BMI 是「8 项原始测量 → 7 个国标计分项」里由身高与
+# 体重**合成**的那一项（spec §4.2），它没有自己的原始测量列，故不在本映射里；合成算式是
+# 下面的 :func:`bmi_of`。
+#
+# **住址为什么在 domain 而不在 ``app/seed/fitness.py``**（Plan 02 Task 1，终审 C 组）：
+# 它原先住在生成器里，于是生产层为了拿这一张词表必须 ``from app.seed.fitness import …``
+# ——基线 ``e26347f`` 上 ``app/pipeline/run_stratify.py:48`` 就是这么写的，而 spec §3.3
+# 的依赖方向是单向的、``app/seed`` 是开发期工具。domain 是叶子（谁都能依赖它），且它已经
+# 拥有 ``ScoredItem`` 与 ``WEAKNESS_ITEMS``，键的类型与取值域都在这儿。
+# **不放在 ``app/adapters/base.py``**（终审 B 的备选方案）：那会让 ``base.py`` 新增一句
+# ``from app.domain.indicators import ScoredItem``，打破它现有「import 面只有 ``re`` /
+# ``abc`` / ``collections.abc`` / ``dataclasses``」的性质——为一个词表给契约层引入跨层
+# 依赖，代价比收益大。
+COLUMN_BY_ITEM: dict[ScoredItem, str] = {
+    ScoredItem.VITAL_CAPACITY: "vital_capacity_ml",
+    ScoredItem.SPRINT_50M: "sprint_50m_s",
+    ScoredItem.SIT_AND_REACH: "sit_and_reach_cm",
+    ScoredItem.STANDING_JUMP: "standing_jump_cm",
+    ScoredItem.PULL_UP_OR_SIT_UP: "strength_count",
+    ScoredItem.DISTANCE_RUN: "distance_run_s",
+}
+
+# 记录级清洗条目（整条重复被去除）不对应任何单个字段名，用星号通配占位。
+# ``cleaning_log.field`` 是 String(32) 且无 CHECK 约束，星号能原样落库，并在审计界面里
+# 一眼可辨「不是某一列的问题」。
+#
+# **住址在 domain 的理由与 :data:`CLEANING_FIELDS` 是同一个**：它是那一列取值域的成员，
+# 而取值域只能有一个所有者（Plan01 Ruling 156）。它原先住在 ``app/pipeline/clean.py``，
+# 本模块定义 ``CLEANING_FIELDS`` 时若不去引用它、而是自己再写一个字面量 ``"*"``，
+# 就等于把同一个魔法值分成两个所有者——改一处漏一处，而漏掉的那一处**不会报错**，
+# 只会让审计记录里同时出现两种「整条记录」的写法。``clean.py`` 现在从本模块重导出它，
+# 故 ``from app.pipeline.clean import WHOLE_RECORD`` 与
+# ``app.seed.generate`` 的那句导入都照旧可用，一个字都没改。
+WHOLE_RECORD = "*"
+
+# ``cleaning_log.field`` 的取值域，即那一列的**唯一所有者**（Plan01 Ruling 156 的落点，
+# Plan 02 Task 1 兑现）。消费者是 ``tests/db/test_models.py`` 的列宽遍历测试：该列是
+# ``String(32)`` 且没有 CHECK 约束，故此前**没有任何东西**保证 32 装得下最长的字段名——
+# 换任何严格长度的后端（MySQL / PostgreSQL）会静默截断，与 Ruling 144 的
+# ``derived_metrics.trend String(16)`` 是同一个缺陷形态。
+#
+# **13 个值的构成**（全量口径来自生产侧的**全部**写入点，命令::
+#
+#     git grep -n "field=" -- backend/app/pipeline/clean.py backend/app/pipeline/daily.py
+#
+# 基线 ``e26347f``，共 9 处写入点）：
+#
+# * 6 个 = :data:`COLUMN_BY_ITEM` 的值（``clean_fitness`` 逐字段处置时写 ``field=name``）；
+# * 2 个 = ``height_cm`` / ``weight_kg``——**它们不在 ``COLUMN_BY_ITEM`` 里**（那一列只覆盖
+#   6 个短板判定项），但同样是 ``RawFitnessRecord`` 的测量列、同样逐字段过清洗，且
+#   ``height_cm`` 还有 ``normalize_height`` 那条 ``unit_normalized`` 专属写入点
+#   （``clean.py`` 的 ``field="height_cm"``）。**计划原文的公式漏了这两个**；
+# * 3 个 = ``muscle_mass_kg`` / ``body_fat_pct`` / ``smi``，即 ``RawBodyCompRecord`` 的三个
+#   测量列（``clean_body_comp`` 逐字段处置）。**计划原文的公式同样漏了这三个**；
+# * 1 个 = ``student_no``（``clean._unattributable_entry`` 与 ``daily._log_unattributable``
+#   两处都写它：学号为空或解析不到人时，缺的正是这一列）；
+# * 1 个 = :data:`WHOLE_RECORD`（两处 ``duplicate_removed``）。
+#
+# 计划原文写的是「``COLUMN_BY_ITEM`` 的值 ∪ ``{"student_no"}`` ∪ ``WHOLE_RECORD``」= 8 个，
+# 少了上面那 5 个测量列——照它写的话列宽守卫会有 5 个字段名裸奔，而 ``vital_capacity_ml``
+# （17 字符）恰好**在**那 8 个里，所以守卫看上去是有效的。漂移测试
+# ``tests/pipeline/test_clean.py::test_cleaning_fields_cover_every_produced_field``
+# 把本集合与生产侧**推导出来的**那一份对齐（两侧不同源，硬规矩 #35）。
+CLEANING_FIELDS: frozenset[str] = frozenset(COLUMN_BY_ITEM.values()) | {
+    "height_cm",
+    "weight_kg",
+    "muscle_mass_kg",
+    "body_fat_pct",
+    "smi",
+    "student_no",
+    WHOLE_RECORD,
+}
+
 # 国标 2014「说明」第 4 条：小学、初中、高中按每个年级为一组，
 # 「大学一、二年级为一组，三、四年级为一组」。大学这里官方是按年级组划分、
 # 没有年龄段，所以 AGE_GROUPS 直接用官方的两个年级组名，不另造年龄带。
 AGE_GROUPS: tuple[str, ...] = ("大一、大二", "大三、大四")
 
 # 典型在校年龄：大一 18、大二 19、大三 20、大四 21，故以 19/20 岁为两组分界
 _LOWER_GRADE_MAX_AGE = 19
 
 
 def age_group_of(age: int) -> str:
     """把年龄折算成国标 2014 的大学年级组。
 
     国标按年级而非年龄分组，这里按典型入学年龄折算：不超过 19 岁归
     ``大一、大二``，20 岁及以上归 ``大三、大四``；超出常见在校年龄（18–22 岁）
     的输入会自然落到端点组，不会产出评分表里不存在的键。
     """
     return AGE_GROUPS[0] if age <= _LOWER_GRADE_MAX_AGE else AGE_GROUPS[1]
 
 
+def bmi_of(height_cm: float | None, weight_kg: float | None) -> float | None:
+    """身高体重 → BMI（kg/m²），保留 1 位小数。
+
+    **它是身高与体重的纯函数**，没有任何 I/O、时钟或数据库依赖，故住在 domain。
+    原先它住在 ``app/pipeline/run_stratify.py``（Plan 02 Task 1 迁走）——一个纯函数住在
+    管道层，意味着 domain 里的任何判定都拿不到它，而 spec §7.4 的安全后置规则要用
+    「BMI > 30」这个**原始值**（不是国标得分），Plan 02 的 ``StudentProfile.bmi`` 因此
+    必须由 domain 自己算得出来。``run_stratify`` 现在从本模块重导出它，
+    ``run_stratify.bmi_of`` 与 ``run_stratify.__all__`` 里的 ``"bmi_of"`` 都照旧可用。
+
+    ``round(..., 1)`` 是承重的：国标 BMI 档位是**区间映射**（两头 80、中间 100），而
+    生成器 ``app.seed.fitness._anthropometrics`` 也算到 1 位小数，两侧差 0.05 就可能在
+    档位边界上翻档——进而翻 ``score_bmi``、翻那 15% 权重的总分贡献。
+    ⚠️ **生成器并没有调用本函数**：``app/seed/`` 自 Plan 01 结案后重新冻结，Plan 02
+    Task 1 对它的改动只允许是「import 与被删常量」（Plan02 Ruling 2/15），把
+    ``_anthropometrics`` 里的算式换成一次 ``bmi_of(...)`` 调用属于**逻辑行**改动，故没做。
+    「两侧逐字一致」因此仍由**独立复算**钉住，而不是由共用一个函数保证：
+    ``tests/domain/test_derive.py`` 的 oracle 自己写了一遍
+    ``round(weight / (height / 100.0) ** 2, 1)``（刻意不复用本函数，硬规矩 #35 两侧不同源）。
+
+    任一为 ``None``（缺测）时返回 ``None``——**绝不当 0**（Plan01 Ruling 21）：
+    BMI = 0 kg/m² 会被 :func:`score_item` 的低侧夹取拿到 **80** 分（实测四个
+    (性别 × 年级组) 组全部 80，因为 BMI 档位的最低哨兵 ``raw_value`` 就是 ``0``，
+    而它对应的官方档是 80。命令：在 ``backend/`` 下跑 ``python`` 交互环境，
+    ``from app.domain.indicators import *`` + ``from app.refdata import standard``，
+    对 ``Sex`` × ``AGE_GROUPS`` 四组逐个求 ``score_item(standard(), ScoredItem.BMI,
+    0.0, sex, group)``，四次都返回 80），一个缺测于是变成「BMI 低到不存在、
+    却仍拿 80 分与 15% 权重」。
+    """
+    if height_cm is None or weight_kg is None:
+        return None
+    return round(weight_kg / (height_cm / 100.0) ** 2, 1)
+
+
 def _segments_of(
     table: StandardTable, item: ScoredItem, sex: Sex, age_group: str
 ) -> tuple[tuple[float, int], ...] | None:
     return table.segments.get((item.value, sex.value, age_group))
 
 
 def _lower_is_better(segments: tuple[tuple[float, int], ...]) -> bool:
     """该项是否「越小越好」——沿 raw_value 升序看得分是否全程单调不增。
 
     方向从表推断，不按项硬编码。对沿 raw 单调的表（除 BMI 外全部 **24** 组——7 项 ×
diff --git a/backend/app/pipeline/backfill.py b/backend/app/pipeline/backfill.py
index 8cae308..e196926 100644
--- a/backend/app/pipeline/backfill.py
+++ b/backend/app/pipeline/backfill.py
@@ -210,35 +210,37 @@ def run_backfill(
 
 
 def main(argv: list[str] | None = None) -> int:
     """CLI 入口：``python -m app.pipeline.backfill --semester 2025-2026-1``。
 
     ``--start`` / ``--end`` 缺省从 ``Semester`` 记录取起止日，而 **``--end`` 必须减一天**
     （Ruling 174：``end_date`` 排他，``semester_end_date`` = 开学日 + 教学周数）。不减就是
     113 天，而第 113 天（``2025-12-22``）在本数据集里没有任何新采集记录，它只会多写 500 行
     派生结果、多一条运行记录，看起来完全正常。
 
-    ``--db`` 缺省取 :data:`app.seed.generate.DEFAULT_DB_URL`，与 ``python -m app.seed.generate``
+    ``--db`` 缺省取 :data:`app.config.DEFAULT_DB_URL`，与 ``python -m app.seed.generate``
     写的是**同一个所有者**：这是计划字面（``sqlite:///pe.db``）的一处有意偏离，理由是先跑
     生成器、再跑回填是 Step 6 的既定顺序，而相对路径的 ``sqlite:///pe.db`` 取决于 CWD——
     两个所有者会在有人从仓库根而不是 ``backend/`` 运行时静默指向两个不同的文件。
+    （Plan 02 Task 1 之前这个常量住在 ``app.seed.generate``，本函数为此必须 import 生成器；
+    现在它住在 :mod:`app.config` 这个叶子里，``pipeline → seed`` 那条边因此消失。）
 
     退出码：**有任一天 ``status == "failed"``（批没跑完）→ 1**，否则 0。per-day 的
     ``"partial"`` 是「跑完了但有记录因学号解析不到而整条跳过」（已在 ``cleaning_log`` 逐条
     留痕），它体现在控制台的整体汇总里、不改退出码——否则一个建档缺失的学号会让每天的
     定时任务都报失败，而重跑修不好它。
     """
-    # 函数内导入：Mock 适配器与 seed 的缺省路径只属于 CLI 这条启动路径，
+    # 函数内导入：适配器工厂与缺省 DB URL 只属于 CLI 这条启动路径，
     # 放进模块顶层会让 ``import app.pipeline.backfill`` 也依赖它们。
-    from app.adapters.mock_lepao import MockLePaoAdapter
+    from app.adapters.factory import build_adapter
+    from app.config import DEFAULT_DB_URL
     from app.db.session import engine
-    from app.seed.generate import DEFAULT_CSV_DIR, DEFAULT_DB_URL
 
     parser = argparse.ArgumentParser(
         prog="python -m app.pipeline.backfill",
         description="按业务日期逐日回放整个学期（Extract → Clean → Percentile → Derive → Stratify）",
     )
     parser.add_argument(
         "--semester", required=True,
         help="学期名（semester.name，如 2025-2026-1）；它是幂等键的一半，故按名字查",
     )
     parser.add_argument("--start", default=None, help="起始业务日期 ISO（缺省 = 学期 start_date）")
@@ -258,21 +260,21 @@ def main(argv: list[str] | None = None) -> int:
             args.end if args.end is not None
             else (semester.end_date - dt.timedelta(days=1)).isoformat()
         )
         # Ruling 212 ③：两个端点都必须落在 --semester 的 [start_date, end_date) 内。
         # 缺省值天然满足（start_date 本身、end_date − 1 天），故本闸只挡显式传参的误操作：
         # 跨学期回填会让同一业务日期在两个 semester_id 下各留一套「当前」派生结果，
         # 而 _replay_cleanup 按 batch_id 删不到对方（见 require_dates_in_semester）。
         require_dates_in_semester(semester, "--start", start)
         require_dates_in_semester(semester, "--end", end)
         days = business_dates(start, end)
-        adapter = MockLePaoAdapter(DEFAULT_CSV_DIR)
+        adapter = build_adapter()
         started = time.perf_counter()
         runs = run_backfill(session, semester.id, start, end, adapter)
         elapsed = time.perf_counter() - started
 
         # ⚠️ 以下一切字段读取都必须在这个 with 块内完成（run_daily 的 commit 已 expire 它们）
         statuses = Counter(run.status for run in runs)
         failed = statuses.get("failed", 0)
         overall = (
             "success" if set(statuses) == {"success"}
             else "failed" if set(statuses) == {"failed"}
diff --git a/backend/app/pipeline/clean.py b/backend/app/pipeline/clean.py
index 7edda3c..c3c40fc 100644
--- a/backend/app/pipeline/clean.py
+++ b/backend/app/pipeline/clean.py
@@ -31,20 +31,27 @@
 """
 import pathlib
 from collections.abc import Callable, Iterable
 from dataclasses import dataclass, fields, replace
 from typing import TypeVar
 
 import yaml
 
 from app.adapters.base import RawBodyCompRecord, RawFitnessRecord
 from app.db.models import CleaningLog
+# WHOLE_RECORD 的**唯一所有者**是 app.domain.indicators（它同时拥有 cleaning_log.field
+# 的整个取值域 CLEANING_FIELDS，Plan01 Ruling 156 的落点）。本模块重导出它，故
+# ``from app.pipeline.clean import WHOLE_RECORD`` 与 app/seed/generate.py 的那句导入
+# 都照旧可用——Plan02 Ruling 2 要求本 Task 对 app/seed/ 的改动只限 import 与被删常量，
+# 重导出正是让它一个字都不必改的做法。依赖方向 pipeline → domain 合法（spec §3.3，
+# domain 是叶子）；indicators 只 import enum 与 app.domain.tables，故不可能与本模块成环。
+from app.domain.indicators import WHOLE_RECORD
 
 # 两类原始记录在「剔除无法归属 → 去重」这一段里完全同构（都有 student_no 与一个日期/批次
 # 列），用受约束的 TypeVar 让 :func:`_dedup` 的返回类型跟着入参走，而不是退化成 Any。
 _RecordT = TypeVar("_RecordT", RawFitnessRecord, RawBodyCompRecord)
 
 # ``kind`` 的四个取值逐字来自 ORM 的 ``CleaningLog.KINDS``（Task 3 已建 CHECK 约束
 # ck_cleaning_log_kind）。在此只写一次、由 :class:`CleaningEntry` 构造时校验，而不是在
 # 每个记录点重抄字符串：两处漂移只会在 Task 10 落库时被约束拒绝，错误现场离真正的原因
 # 隔了五个任务，而审计条目已经在内存里攒了一整批。
 KIND_MISSING = "missing_dropped"
@@ -52,25 +59,25 @@ KIND_OUTLIER = "outlier_corrected"
 KIND_UNIT = "unit_normalized"
 KIND_DUPLICATE = "duplicate_removed"
 
 # dropped / corrected 的口径（计划只声明了这两个计数字段、没给定义，由控制方裁定）：
 # dropped 只数 missing_dropped；corrected 数 outlier_corrected 与 unit_normalized 之和；
 # duplicate_removed **两个计数都不进**——被去掉的是一整条重复行，活下来的那一行本身
 # 完好无损，既没丢值也没改值。Task 10 要把这两个数写进 daily_sync_run 的
 # dropped_count / corrected_count，口径含糊就等于报表口径含糊。
 _CORRECTED_KINDS = frozenset({KIND_OUTLIER, KIND_UNIT})
 
-# 记录级条目（重复行去除）不对应任何单个字段名，用星号通配占位。CleaningLog.field 是
-# String(32) 且无 CHECK 约束，星号能原样落库，并在审计界面里一眼可辨「不是某一列的问题」。
-# 导出为模块常量（Ruling 50）：字面量只在本行出现一次，调用点一律引用常量，避免同一个
+# 记录级条目（重复行去除）不对应任何单个字段名，用星号通配占位；常量本身住在
+# app.domain.indicators（见文件头那句重导出的理由）。CleaningLog.field 是 String(32)
+# 且无 CHECK 约束，星号能原样落库，并在审计界面里一眼可辨「不是某一列的问题」。
+# 导出为模块常量（Ruling 50）：字面量只在一处出现，调用点一律引用常量，避免同一个
 # 魔法值散落在几处、改一处漏一处。
-WHOLE_RECORD = "*"
 
 # 学号 / 批次 / 日期列不是测量值，不进 ranges 表。测量字段清单从两个数据类的字段声明序
 # 推导，不手抄第二份真相（与 base.py 的 FITNESS_COLUMNS 同一手法）：将来给记录加一列，
 # load_ranges 会立刻因为「ranges 文件漏了一个字段」而响亮报错，而不是让新列裸奔。
 _IDENTITY_FIELDS = frozenset({"student_no", "batch_key", "tested_on", "measured_on"})
 
 FITNESS_MEASURE_FIELDS: tuple[str, ...] = tuple(
     f.name for f in fields(RawFitnessRecord) if f.name not in _IDENTITY_FIELDS
 )
 BODY_COMP_MEASURE_FIELDS: tuple[str, ...] = tuple(
diff --git a/backend/app/pipeline/daily.py b/backend/app/pipeline/daily.py
index 8046279..cc4fff6 100644
--- a/backend/app/pipeline/daily.py
+++ b/backend/app/pipeline/daily.py
@@ -34,21 +34,20 @@ import argparse
 import datetime as dt
 
 from sqlalchemy import delete, select
 from sqlalchemy.exc import IntegrityError
 from sqlalchemy.orm import Session
 
 from app.adapters.base import DataSourceAdapter, parse_batch_key
 from app.db import models, repo
 from app.domain.derive import national_total
 from app.domain.indicators import ScoredItem, Sex, age_group_of
-from app.domain.percentile import MIN_SAMPLE
 # **``stratify`` 必须绑在本模块的命名空间里**：``test_failure_rolls_back_whole_batch``
 # monkeypatch 的是 ``app.pipeline.daily.stratify``。若本模块只调
 # ``run_stratify.stratify_dataset``，那次 monkeypatch 会打到 ``run_stratify`` 自己的
 # 绑定上、对这里毫无作用，整批照常成功，而断言 ``pytest.raises(RuntimeError)`` 当场失败。
 # 这不是两套算法路径：调的是同一个 domain 纯函数，只是调用点在本模块。
 from app.domain.stratify import stratify
 from app.pipeline import run_stratify
 from app.pipeline.clean import clean_body_comp, clean_fitness
 from app.pipeline.extract import extract, parse_business_date
 from app.pipeline.percentile_stage import (
@@ -177,29 +176,63 @@ def _fitness_batch(
     """查找或创建体测批次，并**立刻 flush** 取回 ``id``。
 
     ``fitness_test_result.test_batch_id`` 是 NOT NULL 外键，而 ``repo.upsert`` 的插入分支
     在 flush 前 ``id`` 为 ``None``。批次一共只有「两学年 × 三时点」至多 6 个，逐个 flush
     的代价可以忽略。
 
     幂等键是 ``(semester_id, timepoint)``：本表没有唯一约束，故靠 ``repo.upsert`` 的
     查找分支兜住——重跑同一业务日期时查到同一行、更新它，不会插出第二个 week1 批次。
     插出第二个的后果是 ``fitness_test_result`` 按 ``(test_batch_id, student_id)`` 去重时
     认不出「这是同一次体测」，同一学生同一时点于是留下两行，百分位样本翻倍且不报错。
+
+    **``test_date`` 折叠成 ``min(库里现有值, 本条值)``**（Plan 02 Task 1，终审 B 的 M3）。
+    此前本函数把 ``test_date`` 放进了**每一条**记录的 upsert 值，而 ``repo.upsert`` 的更新
+    分支是 PATCH 语义 → 这一列被写成「本次抽取窗口里**最后一条**记录的 ``tested_on``」，
+    于是同一份 CSV、同一个最终业务日期，只改执行顺序就能得到 09-01 / 09-05 / 09-08 三个值。
+
+    终审 B 诚实标注过：它**构造了反例但没能演示 anchor 真的翻转**（重跑更早那天时
+    ``_load_sources`` 又把 ``test_date`` PATCH 回去了），所以那条是 Major 不是 Critical。
+    **修它的理由不是「它今天会错」，而是「Task 1 给 ``fitness_test_result`` 加了
+    ``tested_on`` 之后，``test_date`` 的唯一职责变成 :func:`assessment_anchor` 的排序键」**
+    （挑「``<= as_of`` 的最新一个 ``week1`` 批次」），而一个随执行顺序漂移的排序键是不可
+    接受的：漂移一旦发生，被选中的评估锚点就换批次，全员的 ``years`` / 趋势 / 分层跟着换。
+
+    ``min`` 折叠而不是「插入时写、更新时不动」：后者仍然**依赖执行顺序**（先跑的那天赢），
+    而 ``min`` 是一个可交换、可结合的折叠——任意顺序、任意次重放，收敛到同一个值
+    （= 该批次见过的最早 ``tested_on``）。取「最早」也符合语义：一个批次的 ``test_date``
+    应当是「这次体测**开始**的那天」，而 ``assessment_anchor`` 用它当「这个批次是否已经
+    可用」的判据，用开始日是保守侧（宁可晚一点认它可用，也不要提前）。
+
+    代价是每条体测记录多一次按 ``(semester_id, timepoint)`` 的 SELECT（``repo.upsert``
+    内部本来就有一次，故这一张表变成两次）。批次一共只有「两学年 × 三时点」至多 6 个，
+    整学期回放（500 人 × 112 业务日）里体测记录约 3000 条，故多出约 3000 次索引查找；
+    ``tests/pipeline/test_backfill.py::test_backfill_500_students_under_60_seconds``
+    的 ``elapsed < 60`` 是这条代价的守卫（实测数字见任务报告）。**不做进程内缓存**：
+    缓存 ``test_date`` 等于在 ``repo.upsert`` 之外再开一个所有者，而省下的那点查询
+    换不来「同一批次两个地方各存一份日期」的风险。
     """
+    existing = session.scalar(
+        select(models.FitnessTestBatch).where(
+            models.FitnessTestBatch.semester_id == semester.id,
+            models.FitnessTestBatch.timepoint == timepoint,
+        )
+    )
     batch = repo.upsert(
         session,
         models.FitnessTestBatch,
         ("semester_id", "timepoint"),
         {
             "semester_id": semester.id,
             "timepoint": timepoint,
-            "test_date": test_date,
+            "test_date": (
+                test_date if existing is None else min(existing.test_date, test_date)
+            ),
             "source": SOURCE_SYSTEM,
             "academic_year": academic_year,
         },
     )
     session.flush()
     return batch
 
 
 def _log_cleaning_entries(
     session: Session, batch_id: int, entries, student_id_by_no: dict[str, int]
@@ -347,20 +380,23 @@ def _load_sources(
         years_back = current.start_date.year - semester.start_date.year
         age_group = age_group_of(
             age_at(student.birth, current.start_date) - years_back
         )
         scores = run_stratify.score_raw(
             run_stratify.record_dict(record), Sex(student.sex), age_group, table
         )
         values = {
             "test_batch_id": batch.id,
             "student_id": student.id,
+            # 每条成绩自己的测量日（Plan 02 Task 1 新列）：批次的 test_date 是一个批次
+            # 一个值，而百分位阶段要按业务日期截断，只有逐行的 tested_on 做得到。
+            "tested_on": tested_on,
             "height_cm": record.height_cm,
             "weight_kg": record.weight_kg,
             "vital_capacity_ml": record.vital_capacity_ml,
             "sprint_50m_s": record.sprint_50m_s,
             "sit_and_reach_cm": record.sit_and_reach_cm,
             "standing_jump_cm": record.standing_jump_cm,
             "strength_count": record.strength_count,
             "distance_run_s": record.distance_run_s,
             "total_score": national_total(scores),
             "national_grade": None,
@@ -598,20 +634,21 @@ def run_daily(
             # 写入，本批开始时一律归零（重放必须重算它们，见前向约束）。
             "extracted_fitness": 0,
             "extracted_body_comp": 0,
             "extracted_survey": 0,
             "dropped_count": 0,
             "corrected_count": 0,
             "red_count": 0,
             "yellow_count": 0,
             "green_count": 0,
             "insufficient_count": 0,
+            "muscle_line_gaps": 0,
             "prescription_count": 0,
             "alert_count": 0,
             "status": "failed",
             "error_summary": None,
         },
     )
     # **必须 flush 取回 id**：插入分支在 flush 前 id 为 None，而三张派生表的 batch_id
     # 都是 NOT NULL 外键（repo.upsert 的 docstring 把这条契约写在了那里）。
     session.flush()
     batch_id = run.id
@@ -639,61 +676,66 @@ def run_daily(
             session.flush()
             labels, muscle_gaps = _stratify_and_persist(session, batch_id, as_of)
 
             run.dropped_count = dropped
             run.corrected_count = corrected
             run.red_count = labels.count("red")
             run.yellow_count = labels.count("yellow")
             run.green_count = labels.count("green")
             run.insufficient_count = labels.count("insufficient_data")
             run.status = "partial" if unattributable else "success"
-            # 缺线组数的留痕（Ruling 121 第 4 步）。**不新增第三个 reasons token**
-            # （Ruling 97① 冻结了 vocabulary），而 DailySyncRun 上唯一的自由文本列是
-            # error_summary，故写在这里并明写「非错误」。已登记为关切：列名与内容不符。
-            run.error_summary = (
-                None if not muscle_gaps else (
-                    f"注意（非错误）：{muscle_gaps} 个 (性别 × 年级组) 组没有肌肉量 P20 "
-                    f"判定线——该组 InBody 样本 < {MIN_SAMPLE}，而肌肉量没有国标常模可降级，"
-                    f"故整组不产出快照行（Ruling 121 第 4 步）。这些组的 C 只由体脂率决定，"
-                    f"逐人的 snapshot_muscle_p20=null 已留在 input_snapshot 里"
-                )
-            )
+            # 缺线组数的留痕（Ruling 121 第 4 步）。**它现在有自己的计数列**
+            # ``daily_sync_run.muscle_line_gaps``（Plan 02 Task 1，Plan02 Ruling 13），
+            # 不再写进 ``error_summary`` 的自由文本：那段文本明写「注意（非错误）」却住在
+            # 错误摘要列里（列名与内容不符，Plan 01 自己就登记过这个关切），而教师大屏
+            # 要按组数排序或求和就得先把一句中文解析回一个整数。
+            # **直接切、不双写**：切之前自己复验过零消费者（命令与输出见
+            # :attr:`app.db.models.DailySyncRun.muscle_line_gaps` 的列注释）——写入点只有
+            # 下面这一处，读取点为零；``main()`` 的 CLI 读的是 ``error_summary`` 这个列、
+            # 不区分内容，两条测试读的都是**真错误**那段。双写等于造出第二个所有者，
+            # 而单一所有者是本计划 Global Constraints 的第一条。
+            # 「**不新增第三个 reasons token**」（Ruling 97① 冻结了 vocabulary）这条约束
+            # 仍然成立：``muscle_line_gaps`` 是一个计数列，不是 ``reasons`` 词表的新成员。
+            run.muscle_line_gaps = muscle_gaps
             run.finished_at = dt.datetime.now()
             session.flush()
     except Exception as exc:
         _record_failure(session, semester_id, as_of, exc)
         raise
     session.commit()
     return run
 
 
 def main(argv: list[str] | None = None) -> int:
     """CLI 入口：``python -m app.pipeline.daily --semester 2025-2026-1 --date 2025-09-15``。
 
     ``--date`` **没有缺省**：给「今天」会让同一条命令在不同日子跑不同的批，而可复现是本
     项目的硬要求（``app/seed/config.py`` 的模块 docstring 为同一件事拒绝过 ``date.today()``）。
 
-    ``--db`` 缺省取 :data:`app.seed.generate.DEFAULT_DB_URL`，与 ``python -m app.seed.generate``
+    ``--db`` 缺省取 :data:`app.config.DEFAULT_DB_URL`，与 ``python -m app.seed.generate``
     和 ``python -m app.pipeline.backfill`` 是**同一个所有者**（计划字面写的是相对路径
     ``sqlite:///pe.db``，那取决于 CWD；两个所有者会在有人从仓库根运行时静默指向两个文件）。
 
-    适配器缺省是 :class:`~app.adapters.mock_lepao.MockLePaoAdapter` 读 ``data/seed/`` 下的
-    CSV——Plan 01 只有这一个实现；Plan 02 接 HTTP 乐跑时改的就是这一处（函数内导入，故本
-    生产模块的顶层依赖图里不出现 Mock）。
+    适配器经 :func:`app.adapters.factory.build_adapter` 造，缺省 ``kind="mock"`` 读
+    ``data/seed/`` 下的 CSV——今天只有这一个实现能跑；将来接 HTTP 乐跑时改的是工厂
+    （或调用方传进来的 ``kind``），**本文件不动**（函数内导入，故本生产模块的顶层依赖图里
+    既不出现 Mock 也不出现工厂）。此前这里是硬编码的 ``MockLePaoAdapter(DEFAULT_CSV_DIR)``，
+    与 ``backfill.py`` 的 ``main()`` 各一处，换实现要改两处生产代码，与
+    ``http_lepao.py`` 承诺的「改动只落在本文件」不符。
 
     ``run_daily`` 失败时**不捕获**：它已经把 ``status = "failed"`` 的运行记录提交进库，真因
     由 traceback 原样抛出、退出码 1。在这里包一层 try/except 只会把唯一的线索换成一行摘要。
     故正常返回时 ``status`` 只可能是 ``"success"`` 或 ``"partial"``，退出码恒 0。
     """
-    from app.adapters.mock_lepao import MockLePaoAdapter
+    from app.adapters.factory import build_adapter
+    from app.config import DEFAULT_DB_URL
     from app.db.session import engine
-    from app.seed.generate import DEFAULT_CSV_DIR, DEFAULT_DB_URL
 
     parser = argparse.ArgumentParser(
         prog="python -m app.pipeline.daily",
         description="跑单个业务日期的整批（Extract → Clean → Percentile → Derive → Stratify）",
     )
     parser.add_argument(
         "--semester", required=True,
         help="学期名（semester.name，如 2025-2026-1）；它是幂等键的一半，故按名字查",
     )
     parser.add_argument(
@@ -702,34 +744,43 @@ def main(argv: list[str] | None = None) -> int:
              "跑不同的批，与可复现的硬要求冲突",
     )
     parser.add_argument("--db", default=DEFAULT_DB_URL, help=f"数据库 URL（缺省 {DEFAULT_DB_URL}）")
     args = parser.parse_args(argv)
 
     eng = engine(args.db)
     with Session(eng) as session:
         semester = semester_by_name(session, args.semester)
         # Ruling 212 ③：跑之前先挡掉跨学期组合（见 require_dates_in_semester 的 docstring）
         require_dates_in_semester(semester, "--date", args.date)
-        run = run_daily(session, semester.id, args.date, MockLePaoAdapter(DEFAULT_CSV_DIR))
+        run = run_daily(session, semester.id, args.date, build_adapter())
         # ⚠️ 一切字段读取都必须在这个 with 块内完成：run_daily 末尾的 commit 已把它们
         #    expire，会话一关就是 DetachedInstanceError（Task 10 关切 10）。
         total = run.red_count + run.yellow_count + run.green_count + run.insufficient_count
         print(
             f"业务日期 {run.business_date.isoformat()}（学期 {semester.name}，"
             f"batch_id={run.id}）status={run.status}"
         )
         print(
             f"抽取 体测 {run.extracted_fitness} / 体成分 {run.extracted_body_comp} / "
             f"问卷 {run.extracted_survey}；剔除 {run.dropped_count}、修正 {run.corrected_count}"
         )
         print(
             f"分层分布（{total} 人）：红 {run.red_count}、黄 {run.yellow_count}、"
             f"绿 {run.green_count}、数据不足 {run.insufficient_count}"
         )
+        if run.muscle_line_gaps:
+            # 缺线组数此前是塞在 error_summary 里的一句「注意（非错误）：…」自由文本
+            # （Plan 02 Task 1 改走计数列）。控制台这一行是它换来的**操作员可见信号**：
+            # 计数列能进报表，但跑 CLI 的人当场就该看见「今天有几个组没有肌肉量判定线」。
+            print(
+                f"缺肌肉量 P20 判定线的 (性别 × 年级组) 组数：{run.muscle_line_gaps}"
+                f"（这些组的 C 只由体脂率决定，机制见 daily_sync_run.muscle_line_gaps 的列注释）"
+            )
         if run.error_summary:
-            # 缺肌肉量 P20 判定线时这里写的是「注意（非错误）」，见 run_daily
-            print(f"备注：{run.error_summary}")
+            # 自 Plan 02 起这一列**只承载真错误**（缺线组数改由 muscle_line_gaps 计数列
+            # 承载并在上面单独打印），故这里的「备注」措辞改成「错误摘要」，与列名对齐。
+            print(f"错误摘要：{run.error_summary}")
     return 0
 
 
 if __name__ == "__main__":
     raise SystemExit(main())
diff --git a/backend/app/pipeline/percentile_stage.py b/backend/app/pipeline/percentile_stage.py
index 0411ed2..ef87190 100644
--- a/backend/app/pipeline/percentile_stage.py
+++ b/backend/app/pipeline/percentile_stage.py
@@ -137,29 +137,50 @@ def assessment_anchor(session: Session, as_of: dt.date) -> Anchor:
     curr = rows[0] if rows else None
     prev = rows[1] if len(rows) > 1 else None
     return Anchor(
         curr_batch_id=None if curr is None else curr[0],
         prev_batch_id=None if prev is None else prev[0],
         curr_date=None if curr is None else curr[1],
         prev_date=None if prev is None else prev[1],
     )
 
 
-def _results_of(session: Session, batch_id: int | None) -> dict[int, models.FitnessTestResult]:
-    """某批次的体测成绩，按 ``student_id`` 索引。``batch_id`` 为 ``None`` 时返回空表。"""
+def _results_of(
+    session: Session, batch_id: int | None, as_of: dt.date
+) -> dict[int, models.FitnessTestResult]:
+    """某批次里 **``tested_on <= as_of``** 的体测成绩，按 ``student_id`` 索引。
+
+    ``batch_id`` 为 ``None`` 时返回空表。
+
+    **``tested_on <= as_of`` 这个截断是承重的**（Plan 02 Task 1，终审 B 的 M1）：
+    ``fitness_test_batch.test_date`` 是**一个批次一个值**，而一个 ``week1`` 批次的记录横跨
+    好几个采集日。只按 ``test_batch_id`` 过滤的话，重跑一个**更早**的业务日期会把整个批次
+    读回来——包括那些测量日**晚于** ``as_of`` 的行，即用未来的数据算过去的分层。终审实测
+    60 人里 **12 人 label 不同**。
+
+    ``fitness_test_result.tested_on`` 那一列与本截断是同一个 Task 加的（见
+    :class:`app.db.models.FitnessTestResult` 的列注释）；守卫是
+    ``tests/pipeline/test_percentile_stage.py::test_cohort_truncates_results_by_tested_on``
+    ——把它的 ``.where`` 删掉那条测试必须变红。
+
+    ``as_of`` 对 ``prev_batch_id``（上学年 ``week16``）同样施加：那一批的记录全部远早于
+    ``as_of``，故截断在这条路径上是恒真的 no-op，但**统一施加**比「只对 curr 截断」安全——
+    后者是一个等着被忘掉的例外，而忘了的后果正是上面那个缺陷。
+    """
     if batch_id is None:
         return {}
     return {
         row.student_id: row
         for row in session.scalars(
             select(models.FitnessTestResult).where(
-                models.FitnessTestResult.test_batch_id == batch_id
+                models.FitnessTestResult.test_batch_id == batch_id,
+                models.FitnessTestResult.tested_on <= as_of,
             )
         )
     }
 
 
 def _latest_body_comp(session: Session, as_of: dt.date) -> dict[int, models.BodyComposition]:
     """每人 ``<= as_of`` 的**最新一条**体成分（Ruling 121：样本单位是学生，不是测量行）。
 
     按 ``measured_on`` 升序遍历、后写覆盖，故留下的是最新的一条。``(student_id,
     measured_on)`` 上有唯一约束（Ruling 24），同一天不可能有两条。
@@ -198,25 +219,29 @@ def cohort_from_db(session: Session, as_of: dt.date) -> tuple[list[PersonInputs]
 
     ``snapshot_muscle_p20`` 一律回填 ``None``（**未解析**）：肌肉量 P20 来自快照，而快照
     正是 :func:`run_percentile` 要产出的东西，此刻还不存在。调用方在物化/读回快照之后用
     :func:`app.pipeline.run_stratify.resolve_muscle_lines` 回填——两条路径共用同一个回填
     函数，故不可能一处查表、另一处凭空给值。
 
     ``years`` 恒为 ``YEAR_STEP = 1.0``（Ruling 140 的 week1-vs-week1 口径；无历史时也是
     1.0 而不是 0，Ruling 123）。``curr_total`` / ``prev_total`` 取**落库的** ``total_score``
     列，于是 ``derive`` 的 Ruling 118-M1 值校验真的在核对「落库总分」与「落库七项得分」
     是否自洽——它不是空转的。
+
+    **体测成绩按 ``tested_on <= as_of`` 截断**（Plan 02 Task 1）：批次的 ``test_date`` 是
+    一个批次一个值、而批次内记录横跨好几个采集日，不截断就会在重跑更早的业务日期时读到
+    **未来**的测量。机制与实测数字见 :func:`_results_of` 的 docstring。
     """
     anchor = assessment_anchor(session, as_of)
     current = current_semester_of(session, as_of)
-    curr_rows = _results_of(session, anchor.curr_batch_id)
-    prev_rows = _results_of(session, anchor.prev_batch_id)
+    curr_rows = _results_of(session, anchor.curr_batch_id, as_of)
+    prev_rows = _results_of(session, anchor.prev_batch_id, as_of)
     bodies = _latest_body_comp(session, as_of)
     # 批次所属学期 → 该学期开学年，用来算「这条记录是几个学年之前」（Ruling 56）
     year_of_batch: dict[int, int] = {}
     for batch_id in (anchor.curr_batch_id, anchor.prev_batch_id):
         if batch_id is None:
             continue
         year_of_batch[batch_id] = session.scalar(
             select(models.Semester.start_date)
             .join(
                 models.FitnessTestBatch,
diff --git a/backend/app/pipeline/run_stratify.py b/backend/app/pipeline/run_stratify.py
index acdea87..9d875de 100644
--- a/backend/app/pipeline/run_stratify.py
+++ b/backend/app/pipeline/run_stratify.py
@@ -28,32 +28,40 @@
 import datetime as dt
 import pathlib
 from dataclasses import dataclass, fields, replace
 
 from app.adapters.base import (
     BODY_COMP_COLUMNS, FITNESS_COLUMNS, RawBodyCompRecord, RawFitnessRecord,
     parse_batch_key,
 )
 from app.domain.derive import DerivedResult, derive, national_total
 from app.domain.indicators import (
-    WEAKNESS_ITEMS, ScoredItem, Sex, age_group_of, score_item,
+    COLUMN_BY_ITEM, WEAKNESS_ITEMS, ScoredItem, Sex, age_group_of, bmi_of,
+    score_item,
 )
 from app.domain.percentile import (
     MUSCLE_MASS, PercentileRow, compute_snapshot, lines_used, lookup_p20,
     summarize_source,
 )
 from app.domain.stratify import Layer, StratResult, explain, stratify
 from app.domain.tables import StandardTable
 from app.pipeline.clean import clean_body_comp, clean_fitness, load_ranges
-from app.refdata import DATA_DIR, standard
-from app.seed.fitness import COLUMN_BY_ITEM
-from app.seed.generate import RANGES_FILENAME
+from app.refdata import DATA_DIR, RANGES_FILENAME, standard
+
+# ⚠️ ``bmi_of`` 与 ``COLUMN_BY_ITEM`` 在本模块是**重导出**，唯一所有者是
+# :mod:`app.domain.indicators`（Plan 02 Task 1 迁走：前者是身高体重的纯函数，住在管道层
+# 意味着 domain 里的安全后置规则拿不到它；后者是一张词表，住在 ``app/seed`` 意味着生产层
+# 为了拿它必须 import 仿真数据生成器，违反 spec §3.3 的单向依赖）。
+# 重导出是为了**保持既有导入面**：``bmi_of`` 在下面 ``__all__`` 里、
+# ``run_stratify.bmi_of`` 与 ``run_stratify.COLUMN_BY_ITEM`` 都照旧可用。
+# 新代码请直接从 domain 导入；``tests/architecture/test_layering.py`` 的依赖方向守卫
+# 会在有人把这两句改回 ``from app.seed...`` 时变红。
 
 __all__ = [
     "Evaluated",
     "PersonInputs",
     "StratifyReport",
     # 跨模块消费的常量，唯一消费者是 ``app/pipeline/percentile_stage.py`` 的那条显式导入：
     # ``WEEK1_TIMEPOINT`` 是 week1 评估锚点的唯一所有者（Ruling 152 合流）、``YEAR_STEP`` 是
     # ``years`` 口径的唯一所有者（Ruling 140）。``from x import name`` 不看 ``__all__``，故
     # 漏掉它们不影响功能，但会让下一个人以为它们私有、可放心改名——而改值会同时改动 DB 与
     # 内存两条路径的口径。实测（**Task 10 的** fix round 3 做的变异：``WEEK1_TIMEPOINT`` →
@@ -95,23 +103,26 @@ __all__ = [
 # 保证」），端到端交叉验证就没了。week8 / week16 是学期内的过程测量，归 spec §8.2 与 Plan 03。
 WEEK1_TIMEPOINT = "week1"
 YEAR_STEP = 1.0
 
 _ranges_cache = None
 
 
 def ranges():
     """:func:`app.pipeline.clean.load_ranges` 的进程内单例（与 ``app.seed.generate._ranges`` 同法）。
 
-    区间表只有 ``data/indicator_ranges.yaml`` 一个真相，文件名从 ``app.seed.generate``
+    区间表只有 ``data/indicator_ranges.yaml`` 一个真相，文件名从 :mod:`app.refdata`
     导入而不是在这里重抄一遍——两处字面量漂移的后果是清洗层静默用不上越界保护，
     而 ``load_ranges`` 的键集合校验只在**它读到的那个文件**上生效。
+    （Plan 02 Task 1 之前它住在 ``app.seed.generate``，于是本模块为了拿一个文件名字符串
+    就得 import 仿真数据生成器；:mod:`app.refdata` 是 ``DATA_DIR`` 与
+    ``STANDARD_FILENAME`` 的既有所有者，搬过去之后「哪个文件在哪个目录」在同一个模块里。）
 
     **导出而不私有**：``daily.py`` 的 Clean 阶段要用同一份区间表，两处各读一次盘、
     或其中一处自己拼一个路径，都会让「清洗口径只有一个所有者」这句话不成立。
     """
     global _ranges_cache
     if _ranges_cache is None:
         _ranges_cache = load_ranges(pathlib.Path(DATA_DIR) / RANGES_FILENAME)
     return _ranges_cache
 
 
@@ -168,48 +179,37 @@ class StratifyReport:
     ``valid_count`` / ``dominant_bucket`` / ``trend`` / ``percentile_source`` / ``explain``
     （计划 Task 10 的 Interfaces 块逐字）。``distribution`` 的键是四个标签、值是**占比
     float**（不是计数），四个键**恒在**（无人的档为 ``0.0``）——少一个键会让
     ``dist["green"]`` 在「本日没有绿层」这种完全合法的情况下 ``KeyError``。
     """
 
     results: list[dict]
     distribution: dict[str, float]
 
 
-def bmi_of(height_cm: float | None, weight_kg: float | None) -> float | None:
-    """身高体重 → BMI，口径与生成器（``app.seed.fitness._anthropometrics``）逐字一致。
-
-    ``round(..., 1)`` 是承重的：国标 BMI 档位是区间映射，生成器也算到 1 位小数，
-    两侧差 0.05 就可能在档位边界上翻档（进而翻 ``score_bmi``、翻 15% 权重的总分贡献）。
-    任一为 ``None``（缺测）时返回 ``None``——**绝不当 0**（Ruling 21）。
-    """
-    if height_cm is None or weight_kg is None:
-        return None
-    return round(weight_kg / (height_cm / 100.0) ** 2, 1)
-
-
 def score_raw(
     raw: dict, sex: Sex, age_group: str, table: StandardTable
 ) -> dict[ScoredItem, int | None]:
     """8 项原始测量 → 7 项国标得分（含由身高体重合成的 BMI）。
 
     **前置条件：``raw`` 里的值必须已经是清洗过的**（Ruling 21）。``score_item`` 对越界
     只做夹取，而低侧夹取对「越小越好」的项意味着**低值得高分**（实测 50 米跑与耐力跑的
     0.0 秒都返回 100 分）——一个零填充的缺测会给体能最差的学生送上 20% 权重的满分，
     还同时抹掉两个桶的短板，全程不报错。故 :func:`_from_dataset` 先过 Task 5 的清洗层。
 
     返回的 dict **恒含 7 个键**（缺测的值为 ``None``）：``derive`` 的
     ``_require_seven_keys``（Ruling 101）要求键齐全，缺键会 ``KeyError``。
 
-    项 → 原始值列名的映射从 ``app.seed.fitness.COLUMN_BY_ITEM`` 导入，**不在这里重抄**：
-    它无法从名字推导（``pull_up_or_sit_up`` 对应的是 ``strength_count``），抄错的后果是
-    某一项恒为 ``None``、该桶短板静默消失。
+    项 → 原始值列名的映射从 :data:`app.domain.indicators.COLUMN_BY_ITEM` 导入，
+    **不在这里重抄**：它无法从名字推导（``pull_up_or_sit_up`` 对应的是
+    ``strength_count``），抄错的后果是某一项恒为 ``None``、该桶短板静默消失。
+    BMI 那一项走 :func:`app.domain.indicators.bmi_of` 合成，同样不在这里重写算式。
     """
     scores = {
         ScoredItem.BMI: score_item(
             table, ScoredItem.BMI,
             bmi_of(raw.get("height_cm"), raw.get("weight_kg")), sex, age_group,
         )
     }
     for item in WEAKNESS_ITEMS:
         scores[item] = score_item(table, item, raw.get(COLUMN_BY_ITEM[item]), sex, age_group)
     return scores
diff --git a/backend/app/refdata.py b/backend/app/refdata.py
index 4af91e4..95d3f57 100644
--- a/backend/app/refdata.py
+++ b/backend/app/refdata.py
@@ -1,25 +1,38 @@
 """参考数据加载：全项目唯一允许读 ``backend/data/*.csv`` 的模块。
 
 依赖方向是 refdata → domain：这里把 CSV 解析成 app/domain/tables.py 的
 StandardTable，再交给 domain 的纯函数使用；进程内缓存也放在这里而不是 domain。
 domain 因此保持为无 I/O 的叶子（Ruling 15），不会隐式依赖磁盘上某个 CSV 是否存在。
+
+本模块同时是 ``backend/data/`` 下**文件名与目录**的唯一所有者：``BACKEND_DIR`` 取自
+:mod:`app.config`（叶子，只 import ``pathlib``，故 refdata → config 不可能造出环），
+``DATA_DIR`` / ``STANDARD_FILENAME`` / ``RANGES_FILENAME`` 都住在这里。
+``RANGES_FILENAME`` 原先住在 ``app/seed/generate.py``，于是生产层为了拿一个**文件名字符串**
+必须 import 仿真数据生成器（基线 ``e26347f`` 的 ``app/pipeline/run_stratify.py:49``）；
+搬到这里之后 ``pipeline → seed`` 那条边消失，且它与 ``DATA_DIR`` 住在同一个模块里，
+「哪个文件在哪个目录」这件事不必再跨两个模块拼。
 """
 import csv
 import pathlib
 import types
 
+from app.config import BACKEND_DIR
 from app.domain.indicators import AGE_GROUPS, ScoredItem, Sex, segment_thresholds
 from app.domain.tables import StandardTable
 
-DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
+DATA_DIR = BACKEND_DIR / "data"
 STANDARD_FILENAME = "national_standard_2014.csv"
+#: 各测量字段的合理区间表（清洗层的越界保护与 ``non_positive_is_missing`` 标记都读它）。
+#: 只有文件名住在这里，**加载器是** :func:`app.pipeline.clean.load_ranges`——本模块只负责
+#: 国标评分表的解析，不把两种格式各异的参考表混在一个加载器里。
+RANGES_FILENAME = "indicator_ranges.yaml"
 
 # 国标 2014 的**单项标准分词表**（0–100 段；加分表 2-3~2-6 不在本仓，见
 # ``data/README_national_standard.md`` 的「未纳入本表的内容」）。官方档位是
 # 100/95/90/85/80，然后 78→60 每隔 2 分一档，再 50/40/30/20/10，共 **20** 个取值。
 #
 # **它必须是字面量、不得从 CSV 数出来**（硬规矩 #35：断言两侧不得同源）：
 # ``tests/domain/test_indicators.py`` 现有的 ``official = {listed for _, listed in segments}``
 # 与 ``_official_scores(...)`` 两处都是从被校验的同一份 CSV 里取词表，故「表里混进一个
 # 国标不存在的分（如 65）」在那些测试下**恒等成立**。本常量是这条校验唯一的独立一侧。
 OFFICIAL_SCORES: frozenset[int] = frozenset({
diff --git a/backend/app/seed/fitness.py b/backend/app/seed/fitness.py
index 098c907..31e0d8d 100644
--- a/backend/app/seed/fitness.py
+++ b/backend/app/seed/fitness.py
@@ -32,20 +32,21 @@
 ``app.seed`` 里真正碰磁盘的是 :func:`app.seed.generate.write_csv`（写三个 CSV）与
 :func:`app.seed.generate._ranges`（经 ``load_ranges`` 读 ``indicator_ranges.yaml``）。
 """
 import math
 from dataclasses import dataclass
 
 import numpy as np
 
 from app.adapters import base
 from app.domain.indicators import (
+    COLUMN_BY_ITEM,
     ITEM_BUCKET,
     ITEM_WEIGHTS,
     WEAKNESS_ITEMS,
     ScoredItem,
     Sex,
     age_group_of,
     raw_from_score,
     score_item,
     segment_thresholds,
 )
@@ -138,31 +139,23 @@ def _items_by_latent() -> dict[str, tuple[ScoredItem, ...]]:
     grouped: dict[str, list[ScoredItem]] = {}
     for item, bucket in ITEM_BUCKET.items():
         if bucket is None:  # BMI 不归桶，也不进短板判定
             continue
         grouped.setdefault(LATENT_BY_BUCKET[bucket], []).append(item)
     return {name: tuple(items) for name, items in grouped.items()}
 
 
 ITEMS_BY_LATENT: dict[str, tuple[ScoredItem, ...]] = _items_by_latent()
 
-# 计分项 → 体测 CSV 的原始值列名。这张映射**无法从名字推导**（``pull_up_or_sit_up``
-# 对应的是 ``strength_count``），只能显式写出；写错的后果是 write_csv 按契约列序取值时
-# KeyError，当场炸开，不会静默产出一个缺列的文件。
-COLUMN_BY_ITEM: dict[ScoredItem, str] = {
-    ScoredItem.VITAL_CAPACITY: "vital_capacity_ml",
-    ScoredItem.SPRINT_50M: "sprint_50m_s",
-    ScoredItem.SIT_AND_REACH: "sit_and_reach_cm",
-    ScoredItem.STANDING_JUMP: "standing_jump_cm",
-    ScoredItem.PULL_UP_OR_SIT_UP: "strength_count",
-    ScoredItem.DISTANCE_RUN: "distance_run_s",
-}
+# 计分项 → 体测 CSV 的原始值列名：``COLUMN_BY_ITEM`` 的唯一所有者已迁到
+# ``app.domain.indicators``（Plan 02 Task 1），本模块从那里 import 后重导出，
+# 故 ``write_csv`` 那句 ``record[COLUMN_BY_ITEM[item]]`` 与既有导入面都不变。
 
 # 每个计分项的**测量分辨率**（小数位数）。这是仪器口径与上报口径的知识，不是可调旋钮，
 # 所以是模块级常量而不是 ``SeedConfig`` 字段：把它开成配置就等于允许「配出一份评分表
 # 根本没有的测量精度」，而 spec §12 要求系统能与学校官方报表逐格对账。
 #
 # 改动它会**整体平移随机流**（抖动区间的整数单位变了，抽数次数随之变），因而改变同一
 # seed 的全部输出——这是配置变更的预期后果，不是缺陷，但必须重做可复现性取证。
 MEASURE_DECIMALS: dict[ScoredItem, int] = {
     ScoredItem.VITAL_CAPACITY: 0,      # 肺活量计读到 1 ml
     ScoredItem.SPRINT_50M: 1,          # 计时读到 0.1 s
diff --git a/backend/app/seed/generate.py b/backend/app/seed/generate.py
index 819eec3..7e2ea9c 100644
--- a/backend/app/seed/generate.py
+++ b/backend/app/seed/generate.py
@@ -25,46 +25,49 @@ import argparse
 import csv
 import datetime as dt
 import json
 import math
 import pathlib
 
 import numpy as np
 from sqlalchemy.orm import Session
 
 from app.adapters import base
+from app.config import DEFAULT_CSV_DIR, DEFAULT_DB_URL
 from app.db import models, repo
 from app.db.session import engine, init_db
 from app.pipeline.clean import (
     BODY_COMP_MEASURE_FIELDS,
     FITNESS_MEASURE_FIELDS,
     WHOLE_RECORD,
     FieldRange,
     load_ranges,
 )
-from app.refdata import DATA_DIR
+from app.refdata import DATA_DIR, RANGES_FILENAME
 from app.seed.body_comp import make_body_comp
 from app.seed.config import (
     SEMESTERS,
     SeedConfig,
     current_semester,
     semester_end_date,
 )
 from app.seed.fitness import latent_profiles, make_fitness_tests
 from app.seed.population import make_population
 from app.seed.sections import make_sections, make_teachers
 from app.seed.survey import make_survey
 
-BACKEND_DIR = pathlib.Path(__file__).resolve().parents[2]
-DEFAULT_CSV_DIR = BACKEND_DIR / "data" / "seed"
-DEFAULT_DB_URL = f"sqlite:///{(BACKEND_DIR / 'pe.db').as_posix()}"
-RANGES_FILENAME = "indicator_ranges.yaml"
+# ``DEFAULT_CSV_DIR`` / ``DEFAULT_DB_URL`` 的唯一所有者已迁到 :mod:`app.config`，
+# ``RANGES_FILENAME`` 已迁到 :mod:`app.refdata`（Plan 02 Task 1，终审 C 组）：这三个值
+# 原先住在本模块，于是 ``app/pipeline`` 为了拿一个**路径常量**必须 import 仿真数据生成器，
+# 而 spec §3.3 的依赖方向是单向的。本模块现在从新所有者 import 后照旧使用，
+# 故 ``--out-csv`` 的帮助文本、``engine(DEFAULT_DB_URL)`` 与 ``_ranges()`` 都不变。
+# ``BACKEND_DIR`` 只有那三行在用，故不再 import（本模块别处不需要它）。
 
 # 注入痕迹挂在记录上的私有键。build_dataset 会把它**摘下来**汇总成顶层的 dirty_marks，
 # 故最终数据集里的记录不含此键——这一点是承重的：duplicate 注入要求两行逐字相同
 # （Ruling 52），若其中一行多带一个痕迹键，两行就不再相同，清洗层「保留输入顺序中靠后
 # 的一条」也就会留下一条与它的前身不一致的记录。
 DIRTY_MARKS_KEY = "_dirty_marks"
 
 # 三类源各自的「记录身份列」。同时用它来**从记录的形状推断源**，于是 inject_dirty
 # 不必多收一个 source 参数、简报里的三参数签名可以逐字保留。
 # 用元组而不是字典：匹配顺序是契约的一部分，元组让这一点在类型上就是显然的。
diff --git a/backend/tests/adapters/test_factory.py b/backend/tests/adapters/test_factory.py
new file mode 100644
index 0000000..bcac85b
--- /dev/null
+++ b/backend/tests/adapters/test_factory.py
@@ -0,0 +1,88 @@
+"""适配器工厂 ``build_adapter``：kind 分派、参数校验、凭据不外泄。
+
+工厂存在的理由（终审 B）：``MockLePaoAdapter(DEFAULT_CSV_DIR)`` 此前被硬编码在
+``app/pipeline/backfill.py`` 与 ``app/pipeline/daily.py`` 两处 ``main()`` 里，换实现要改
+两处生产代码，与 ``http_lepao.py`` 承诺的「改动只落在本文件」不符；而漏改一处**不报错**，
+那条管道会安静地继续读本地 CSV。
+"""
+import pytest
+
+from app.adapters.base import DataSourceAdapter
+from app.adapters.factory import KINDS, build_adapter
+from app.adapters.http_lepao import HttpLePaoAdapter
+from app.adapters.mock_lepao import MockLePaoAdapter
+from app.config import DEFAULT_CSV_DIR
+
+
+def test_kinds_are_exactly_mock_and_http():
+    """``KINDS`` 字面钉住：加一种实现是一次**有意识**的改动，不是顺手多一个分支。"""
+    assert KINDS == ("mock", "http")
+
+
+def test_default_kind_is_the_mock_adapter_reading_the_default_csv_dir():
+    """``build_adapter()`` == 两个 CLI 此前硬编码的那一句。
+
+    ``seed_dir`` 缺省落在 :data:`app.config.DEFAULT_CSV_DIR`（``backend/data/seed/``）。
+    构造函数**不做任何 I/O**（Mock 的既有契约：目录不存在也照样构造，四个 ``fetch_*``
+    yield 空），故本条不读盘、也不要求那个目录存在——它在本仓里恒为空且不入库。
+    """
+    adapter = build_adapter()
+    assert isinstance(adapter, MockLePaoAdapter)
+    assert isinstance(adapter, DataSourceAdapter), "工厂的返回类型契约"
+    assert adapter.seed_dir == DEFAULT_CSV_DIR
+
+
+def test_csv_dir_override_reaches_the_mock_adapter(tmp_path):
+    adapter = build_adapter("mock", csv_dir=tmp_path)
+    assert isinstance(adapter, MockLePaoAdapter)
+    assert adapter.seed_dir == tmp_path
+
+
+def test_http_kind_builds_the_skeleton_and_needs_both_credentials():
+    """``kind="http"`` 造出骨架；缺 ``base_url`` 或 ``token`` 一律**响亮**拒绝。
+
+    ``HttpLePaoAdapter.__init__`` 不发任何请求（契约测试要在收集期就实例化它），所以
+    ``base_url=None`` 会被**静默存下来**、直到第一次 ``fetch_*`` 才炸——离真因隔一整个
+    调用栈。工厂在这里就拦住。
+    """
+    adapter = build_adapter("http", base_url="https://lepao.example/api", token="tk")
+    assert isinstance(adapter, HttpLePaoAdapter)
+    assert adapter.base_url == "https://lepao.example/api"
+
+    with pytest.raises(ValueError) as excinfo:
+        build_adapter("http")
+    message = str(excinfo.value)
+    assert "base_url" in message and "token" in message
+
+    with pytest.raises(ValueError):
+        build_adapter("http", base_url="https://lepao.example/api")   # 缺 token
+    with pytest.raises(ValueError):
+        build_adapter("http", token="tk")                            # 缺 base_url
+
+
+def test_the_token_never_appears_in_an_error_message():
+    """``token`` 是凭据，不得进异常文本（``http_lepao.py`` 的模块 docstring 明确要求）。
+
+    报错里只印「``<已给出>``」这个占位。这条断言用的是一个**不会与任何真实值撞上**的
+    哨兵字符串，故它既证明「没泄露」，也证明「报错确实提到了 token 这一项」。
+    """
+    sentinel = "SENTINEL-TOKEN-DO-NOT-LEAK"
+    with pytest.raises(ValueError) as excinfo:
+        build_adapter("http", token=sentinel)          # 缺 base_url
+    message = str(excinfo.value)
+    assert sentinel not in message
+    assert "<已给出>" in message
+
+
+def test_unknown_kind_names_the_legal_values():
+    """拼错的 ``kind`` 不得退化成「用缺省的 mock」。
+
+    退化的后果是 HTTP 那条路径永远走不到，而控制台上一切正常——正是工厂要消灭的那类
+    静默失效。报错里列出全部合法取值，改的人才知道该写什么。
+    """
+    with pytest.raises(ValueError) as excinfo:
+        build_adapter("Mock")            # 大小写不对
+    message = str(excinfo.value)
+    assert "'Mock'" in message
+    for kind in KINDS:
+        assert kind in message
diff --git a/backend/tests/architecture/test_domain_purity.py b/backend/tests/architecture/test_domain_purity.py
index 4eab1d9..fdf9f29 100644
--- a/backend/tests/architecture/test_domain_purity.py
+++ b/backend/tests/architecture/test_domain_purity.py
@@ -1,61 +1,260 @@
-"""domain 层纯净性架构约束的可执行检查。
+"""domain 层纯净性架构约束的可执行检查（spec §3.3、Plan 02 Global Constraints）。
 
-spec Global Constraints 规定 app/domain/ 禁止任何 I/O：不得 import 数据库/HTTP 框架，
-不得调用时钟、文件与无种子随机数接口。时间与随机数一律由调用方注入，
-这是分层引擎与处方引擎可单测、可复现的前提。
+spec §3.3 规定 ``app/domain/`` 禁止任何 I/O：不得 import 数据库 / HTTP 框架，不得调用
+时钟、文件与无种子随机数接口。时间与随机数一律由调用方注入，参考表一律由
+:mod:`app.refdata` 加载后**作为参数传入**（Plan01 Ruling 15）。这是分层引擎与处方引擎
+可单测、可复现的前提，也是 spec §12「domain 分支覆盖 100%」能成立的前提。
+
+三条守卫，Plan 02 Task 1 全部改写过一次，改动理由各写在对应测试的 docstring 里：
+
+1. import 守卫从 **deny-list 改成 allow-list**（终审 A 的 M7）；
+2. 时钟与 ``open`` 从**子串匹配改成 AST 节点匹配**（解析 ``ast.Call`` 的 ``func``）；
+3. 三条都加 ``len(scanned) >= 5`` 的空转守卫——此前只有 ``DOMAIN.is_dir()``，而
+   一个**存在但被搬空**的目录同样会让 ``rglob`` 返回空、offenders 恒为 ``[]``、测试假绿。
 """
 import ast
 import pathlib
-import re
-
-DOMAIN = pathlib.Path(__file__).parents[2] / "app" / "domain"
-# 与 spec Global Constraints 逐条对应：禁 I/O 库、禁无种子随机数
-FORBIDDEN = {"sqlalchemy", "fastapi", "requests", "httpx", "pydantic_settings", "random"}
-# 时间必须由调用方注入；子串检查足以覆盖这五种写法
-FORBIDDEN_CALLS = {"datetime.now", "datetime.today", "datetime.utcnow", "date.today", "time.time"}
-# open 用词边界正则而非裸子串，避免 open_ended / reopen / 注释里的 "open" 误报
-FORBIDDEN_PATTERNS = (re.compile(r"\bopen\s*\("),)
-# 文件访问模式：domain 不得读盘，参考表一律由 app/refdata.py 加载后注入（Ruling 15）。
-# pandas 不在封禁之列——它是纯计算库，spec 的意图是「无文件系统/数据库/网络/时钟」，
-# 不是「不许用某个计算库」；封禁它会迫使 Task 11 的向量化优化落到更差的设计上。
-# os / __file__ / json.load / pickle.load 也在列：少了它们，domain 里写一句
-# 「import 该标准库再列目录」就能同时绕过下面三个守卫而全绿。
+
+DOMAIN = pathlib.Path(__file__).resolve().parents[2] / "app" / "domain"
+
+#: domain 允许 import 的**完整模块串**白名单（Plan02 Ruling 3）。
+#:
+#: ⚠️ 按**完整串**比对，不按顶层名：计划原文写「允许 ``collections.abc``」，而
+#: ``from collections.abc import X`` 的 AST 顶层名是 ``collections``
+#: （``node.module.split(".")[0]``）——按顶层名比对的话 ``collections.abc`` 这一项
+#: **永不匹配**，同时 ``from collections import OrderedDict`` 与
+#: ``from collections.abc import Iterable`` 变得无法区分，白名单退化成过宽的许可。
+#: 故 ``collections`` 与 ``collections.abc`` **两个都列**：前者覆盖 ``import collections``，
+#: 后者覆盖 ``from collections.abc import …`` 的完整串。
+#:
+#: ``numpy`` 只列裸名、不列 ``numpy.*``：**这是有意的**。``numpy.linalg`` 一类纯计算
+#: 子模块今天用不上，而 ``numpy.random`` 恰恰是 Global Constraints 点名要挡的无种子
+#: 随机数来源；只列裸名就让「要加一个 numpy 子模块」必须是一次显式的白名单修改。
+ALLOWED_MODULES = frozenset({
+    "dataclasses",
+    "enum",
+    "collections",
+    "collections.abc",
+    "numpy",
+    "typing",
+})
+
+#: 唯一允许的**包**前缀：domain 内部互相依赖（``app.domain.tables`` 等）
+ALLOWED_PACKAGE = "app.domain"
+
+#: 时钟与文件句柄。按 ``ast.Call`` 的 ``func`` 点号串匹配，见
+#: :func:`test_domain_has_no_clock_or_file_access` 的 docstring。
+FORBIDDEN_CALLS = frozenset({
+    "datetime.now",
+    "datetime.today",
+    "datetime.utcnow",
+    "date.today",
+    "time.time",
+    "open",
+})
+
+#: 文件访问模式的子串黑名单（第三条守卫仍是子串匹配，理由见其 docstring）。
+#: pandas 不在封禁之列——它是纯计算库，spec 的意图是「无文件系统/数据库/网络/时钟」，
+#: 不是「不许用某个计算库」；封禁它会迫使向量化优化落到更差的设计上。
+#: ``os`` / ``__file__`` / ``json.load`` / ``pickle.load`` 在列：少了它们，domain 里写一句
+#: 「import 该标准库再列目录」就能同时绕过时钟与 ``open`` 两道守卫而全绿。
 FORBIDDEN_IO = ("read_csv", "read_excel", "read_json", "read_parquet",
                 "csv.reader", "csv.DictReader", ".read_text", ".read_bytes", "Path(",
                 "import os", "os.listdir", "os.walk", "__file__",
                 "json.load", "pickle.load")
 
 
-def test_domain_has_no_forbidden_imports():
-    # 守卫：Path.rglob() 对不存在的目录静默返回空，缺了这行测试会空转全绿
+def _domain_files() -> list[pathlib.Path]:
+    """``app/domain/`` 下的全部 ``.py``，按路径升序（offender 报告顺序因此稳定）。"""
+    # Path.rglob() 对不存在的目录静默返回空，缺了这行测试会空转全绿
     assert DOMAIN.is_dir(), f"领域层目录缺失，架构测试将空转: {DOMAIN}"
-    offenders = []
-    for py in DOMAIN.rglob("*.py"):
+    return sorted(DOMAIN.rglob("*.py"))
+
+
+def _assert_not_empty(scanned: list[pathlib.Path]) -> None:
+    """空转守卫的第二半：目录**存在但被搬空**时 ``is_dir()`` 拦不住。
+
+    下界 5 而不是 6：基线 ``e26347f`` 上实测 domain 有 **6** 个 ``.py``（``__init__`` /
+    ``derive`` / ``indicators`` / ``percentile`` / ``stratify`` / ``tables``；命令见
+    :func:`test_domain_imports_stay_within_the_allow_list` 的 docstring）。取 5 是给
+    「两个模块合并」这类合法重构留一格余量，同时仍能挡住「整层被搬空」。
+    """
+    assert len(scanned) >= 5, (
+        f"只扫到 {len(scanned)} 个 .py，app/domain 可能被搬空，三条守卫会一起假绿"
+    )
+
+
+def _imported_modules(tree: ast.AST):
+    """yield ``(lineno, 完整模块串, 相对层级)``；``ast.walk`` 覆盖函数内导入。"""
+    for node in ast.walk(tree):
+        if isinstance(node, ast.Import):
+            for alias in node.names:
+                yield node.lineno, alias.name, 0
+        elif isinstance(node, ast.ImportFrom):
+            yield node.lineno, (node.module or ""), node.level
+
+
+def _is_allowed(module: str, level: int) -> bool:
+    if level:
+        # 相对导入只可能落在 app.domain 包内（本守卫扫的就是这个包），恒合法
+        return True
+    if module == ALLOWED_PACKAGE or module.startswith(ALLOWED_PACKAGE + "."):
+        return True
+    return module in ALLOWED_MODULES
+
+
+def test_domain_imports_stay_within_the_allow_list():
+    """domain 的 import 一律落在白名单内（allow-list，不是 deny-list）。
+
+    **为什么从 deny-list 改成 allow-list**：deny-list 只能挡住**已经被想到**的库。终审 A
+    实测旧 deny-list 能被 **14 种写法**绕过（如 ``from os import listdir``——旧守卫比的是
+    顶层名 ``os`` 在不在 ``FORBIDDEN`` 里，而它确实拦得住这一种；但 ``import importlib``
+    再 ``importlib.import_module("sqlalchemy")`` 这类间接写法它一个也拦不住）。allow-list
+    把举证责任反过来：**没被显式允许的一律不行**，于是不需要有人先想到 ``os`` 才会被挡。
+
+    ⚠️ **这一条是回归守卫、不是修复**（Plan02 Ruling 4）。落地当天 domain 六个文件的
+    全部 import 就已经在白名单内，所以它**一上来就是绿的**——计划原文 Step 2 写的
+    「allow-list 守卫报 ``numpy`` 之外的漏网」是猜的，AST 亲扫没有漏网。它的价值不在于
+    今天红不红，而在于**新增的拦截力**：
+
+    * ``import app.refdata`` 从此会被抓。终审 A 曾说「domain 经两跳依赖 ``app.refdata``」，
+      **AST 实测不成立**——那是 ``percentile.py`` 模块 docstring 里的自陈（说的是「参考表
+      由 refdata 加载后注入」这件事），不是 import。旧 deny-list 里没有 ``app.refdata``，
+      所以真的加上这一句 import 时它不会响；白名单会。
+    * ``from os import listdir`` / ``import json`` / ``import pathlib`` 一律被抓，
+      不必再靠第三条守卫的子串去撞。
+
+    **落地当天的 import 全貌**（AST 亲扫，这就是白名单取值的实测依据；命令::
+
+        python -c "import ast,pathlib; [print(p.name, sorted({a.name for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.Import) for a in n.names} | {n.module for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.module})) for p in sorted(pathlib.Path('app/domain').rglob('*.py'))]"
+
+    在 ``backend/`` 下跑，基线 ``e26347f``）::
+
+        __init__.py      []
+        derive.py        ['app.domain.indicators', 'app.domain.percentile', 'dataclasses', 'enum']
+        indicators.py    ['app.domain.tables', 'enum']
+        percentile.py    ['app.domain.indicators', 'app.domain.tables',
+                          'collections.abc', 'dataclasses', 'enum', 'numpy']
+        stratify.py      ['app.domain.derive', 'app.domain.indicators',
+                          'collections.abc', 'dataclasses', 'enum']
+        tables.py        ['collections.abc', 'dataclasses']
+
+    六个文件、去重后**五个**不同的顶层来源（``dataclasses`` / ``enum`` /
+    ``collections.abc`` / ``numpy`` / ``app.domain.*``），全部在白名单内。
+    ``typing`` 在名单里但今天没人用：它是 ``Mapped[str | None]`` 这类标注的天然候选，
+    列进来是为了让「加一个类型标注」不必先改架构测试。
+    """
+    scanned = _domain_files()
+    offenders: list[str] = []
+    for py in scanned:
         tree = ast.parse(py.read_text(encoding="utf-8"))
-        for node in ast.walk(tree):
-            mods = []
-            if isinstance(node, ast.Import):
-                mods = [a.name.split(".")[0] for a in node.names]
-            elif isinstance(node, ast.ImportFrom) and node.module:
-                mods = [node.module.split(".")[0]]
-            offenders += [f"{py.name}:{m}" for m in mods if m in FORBIDDEN]
-    assert offenders == []
+        for lineno, module, level in _imported_modules(tree):
+            if not _is_allowed(module, level):
+                offenders.append(f"{py.name}:{lineno}: {module or '<空模块名>'}")
+
+    _assert_not_empty(scanned)
+    assert offenders == [], (
+        "app/domain 是叶子层，import 必须落在白名单内"
+        f"（{sorted(ALLOWED_MODULES)} + {ALLOWED_PACKAGE}.*）：\n" + "\n".join(offenders)
+    )
+
+
+def _dotted(node: ast.AST) -> str | None:
+    """把一个表达式还原成点号串（``dt.datetime.now`` → ``"dt.datetime.now"``）。
+
+    还原不出来的形态（``f()()``、``table[0]()``、``getattr(x, "now")()``）返回 ``None``。
+    那不是漏洞：这类写法要先拿到 ``datetime`` / ``time`` / ``builtins`` 这个对象，而
+    拿到它的唯一途径是 import，import 已经被 allow-list 挡在门外。
+    """
+    parts: list[str] = []
+    while isinstance(node, ast.Attribute):
+        parts.append(node.attr)
+        node = node.value
+    if not isinstance(node, ast.Name):
+        return None
+    parts.append(node.id)
+    return ".".join(reversed(parts))
+
+
+def _hit_forbidden_call(dotted: str) -> str | None:
+    """点号串是否命中 :data:`FORBIDDEN_CALLS`，命中则返回被封禁的那个名字。
+
+    匹配口径是「**等于**，或以 ``.`` + 名字**结尾**」，不是裸 ``endswith``：
+    后者会让一个名叫 ``reopen`` 的函数撞上 ``open``。带 ``.`` 边界之后
+    ``builtins.open`` / ``open`` 命中，而 ``reopen`` / ``open_ended`` 不命中——
+    这正是旧守卫用 ``\\bopen\\s*\\(`` 正则想做到的事，现在由 AST 天然做到。
+    """
+    for name in sorted(FORBIDDEN_CALLS):
+        if dotted == name or dotted.endswith("." + name):
+            return name
+    return None
 
 
 def test_domain_has_no_clock_or_file_access():
-    assert DOMAIN.is_dir(), f"领域层目录缺失，架构测试将空转: {DOMAIN}"
-    offenders = []
-    for py in DOMAIN.rglob("*.py"):
-        src = py.read_text(encoding="utf-8")
-        offenders += [f"{py.name}:{c}" for c in FORBIDDEN_CALLS if c in src]
-        offenders += [f"{py.name}:{p.pattern}" for p in FORBIDDEN_PATTERNS if p.search(src)]
-    assert offenders == []
+    """domain 不得调用时钟，也不得自己打开文件句柄。
+
+    **为什么从子串改成 AST 节点匹配**（终审 A 的 M7）：子串匹配同时有两种失效。
+
+    * **漏报**：``import datetime as dt`` 之后写 ``dt.datetime.now()``，子串
+      ``"datetime.now"`` 恰好在里面，这一种能撞上；但 ``now = datetime.now`` 再
+      ``now()`` 就撞不上了，而 AST 侧只要 ``now`` 的赋值来源是一次 ``ast.Call``
+      就能顺着 ``_dotted`` 追到。
+    * **误报**：docstring 或注释里出现一句「不要用 ``datetime.now()``」就会把守卫
+      弄红。Plan 01 因此**不敢在 domain 的散文里写这些词**，那是让守卫反过来审查
+      文档——本仓的 docstring 恰恰要求把口径写全（硬规矩 #19）。AST 只看代码节点，
+      散文里怎么提都不响。
+
+    ``open`` 从旧的 ``\\bopen\\s*\\(`` 正则并进 :data:`FORBIDDEN_CALLS`：它本来也是
+    一次 ``ast.Call``，两套机制守同一件事只会让人分不清哪条是真相。
+
+    ⚠️ **本条今天与 allow-list 高度重叠**：``datetime`` / ``time`` 都不在白名单里，
+    所以 domain 根本 import 不到它们；``open`` 是内置名，不需要 import，故它是本条
+    **唯一独立生效**的封禁项。保留整条的理由是纵深：白名单是「不许拿到工具」，本条是
+    「不许做这个动作」——将来有人为了别的原因把 ``datetime`` 加进白名单（一个完全可能
+    的合法请求，比如要一个 ``date`` 类型标注），本条仍然挡着 ``datetime.now()``。
+    """
+    scanned = _domain_files()
+    offenders: list[str] = []
+    for py in scanned:
+        tree = ast.parse(py.read_text(encoding="utf-8"))
+        for node in ast.walk(tree):
+            if not isinstance(node, ast.Call):
+                continue
+            dotted = _dotted(node.func)
+            if dotted is None:
+                continue
+            hit = _hit_forbidden_call(dotted)
+            if hit is not None:
+                offenders.append(f"{py.name}:{node.lineno}: {dotted}() 命中 {hit}")
+
+    _assert_not_empty(scanned)
+    assert offenders == [], (
+        "时间与文件句柄一律由调用方注入，domain 不得自取：\n" + "\n".join(offenders)
+    )
 
 
 def test_domain_has_no_filesystem_access():
-    assert DOMAIN.is_dir(), f"领域层目录缺失，架构测试将空转: {DOMAIN}"
-    offenders = []
-    for py in DOMAIN.rglob("*.py"):
+    """domain 不得出现任何读盘/取路径的写法（子串黑名单，第三条守卫）。
+
+    **这一条刻意仍然是子串匹配**：它要抓的东西里有一半**不是调用**——``__file__`` 是
+    一个模块级名字、``import os`` 是一条语句、``.read_text`` 可能挂在一个被注入进来的
+    对象上。用 AST 逐个建模这些形态的成本远高于收益，而子串匹配在这里**只会误报不会
+    漏报**（误报的代价是散文里不能写这些词，可接受）。
+
+    与 allow-list 的分工：``import os`` / ``json.load`` / ``pickle.load`` /
+    ``csv.DictReader`` 现在**两条都抓**（白名单先抓 import，本条再抓用法）。冗余是有意
+    的——白名单抓的是「拿到工具」，本条抓的是「用工具」，两者独立失效时另一条还在。
+    ``__file__`` 与 ``.read_text`` 则是本条**独有**的拦截面：前者不需要任何 import，
+    后者可以作用在一个由调用方传进来的对象上。
+    """
+    scanned = _domain_files()
+    offenders: list[str] = []
+    for py in scanned:
         src = py.read_text(encoding="utf-8")
         offenders += [f"{py.name}:{tok}" for tok in FORBIDDEN_IO if tok in src]
-    assert offenders == []
+
+    _assert_not_empty(scanned)
+    assert offenders == [], (
+        "domain 不得读盘（参考表由 app/refdata 加载后作为参数注入，Plan01 Ruling 15）：\n"
+        + "\n".join(offenders)
+    )
diff --git a/backend/tests/architecture/test_layering.py b/backend/tests/architecture/test_layering.py
new file mode 100644
index 0000000..ad1d6f1
--- /dev/null
+++ b/backend/tests/architecture/test_layering.py
@@ -0,0 +1,121 @@
+"""层间依赖方向的架构守卫（spec §3.3）。
+
+spec §3.3 把依赖方向钉成**单向、不可逆**::
+
+    api → services → domain
+                  ↘ pipeline → adapters
+    db ← services / pipeline
+
+    domain 不依赖任何模块（叶子）
+
+``app/seed/`` 不在这张图里：它是**仿真数据生成器**，属于「造出被试数据」的开发期工具，
+位置在 ``pipeline`` 之外、之上。生产层（``pipeline`` / ``db``）反向 import 它，就意味着
+「跑一次真实的每日批处理」需要「仿真数据生成器」在导入期就是可用的——而生成器带着
+``numpy`` 的随机流、500 人的分布定标、以及 ``data/seed/`` 那套 CSV 契约。这不是风格问题：
+它让生产路径的依赖图里出现一个本该只属于开发期的节点，将来把生成器换成真实数据源时，
+生产代码要跟着改。
+
+**本守卫落地时抓到的 4 处 offender**（基线 ``e26347f``，命令与输出::
+
+    cd backend
+    git grep -n "from app.seed" -- app/pipeline app/db app/domain
+    # app/pipeline/backfill.py:234:    from app.seed.generate import DEFAULT_CSV_DIR, DEFAULT_DB_URL
+    # app/pipeline/daily.py:689:       from app.seed.generate import DEFAULT_CSV_DIR, DEFAULT_DB_URL
+    # app/pipeline/run_stratify.py:48: from app.seed.fitness import COLUMN_BY_ITEM
+    # app/pipeline/run_stratify.py:49: from app.seed.generate import RANGES_FILENAME
+
+四处都是「生产层为了拿一个**常量**而依赖生成器」：两个路径/URL 常量与两个词表常量。
+Plan 02 Task 1 给它们各自建了唯一所有者（``app.config`` / ``app.refdata`` /
+``app.domain.indicators``）之后本守卫转绿，此后它是**回归守卫**——挡住下一次
+「顺手从 seed 里 import 一个现成的常量」。
+
+**为什么用 AST 而不是 ``grep``**：``ast.walk`` 天然覆盖**函数内导入**。上面 4 处里有
+2 处（``daily.py:689``、``backfill.py:234``）就写在 ``main()`` 的函数体内，按行扫源码
+的文本匹配虽然也能撞上，但一旦有人把它改成 ``importlib.import_module("app.seed.generate")``
+或加一层间接，文本匹配就静默失效，AST 也仍然抓得到前一种（``ast.Call`` 不在本守卫范围
+内，见下方「本守卫不覆盖什么」）。
+
+**本守卫不覆盖什么**（写清楚，免得下一个人以为它管得比实际宽）：
+
+* ``app/domain/`` 的 import 由 :mod:`tests.architecture.test_domain_purity` 的
+  allow-list 守卫管——那条是**白名单**，比本条的黑名单紧得多，domain 里出现
+  ``app.seed`` 会先被它抓。本文件仍把 ``app/domain`` 一起扫，是为了让「依赖方向」
+  这件事在**一个地方**能被一次看完（``SCANNED_DIRS`` 加一项即可）。
+* ``importlib`` 动态导入、字符串拼接出来的模块名。
+* ``app/adapters/``：spec §3.3 里它是 ``pipeline`` 的被依赖方，今天没有任何理由
+  import ``app.seed``；等真出现理由了再把目录加进 ``SCANNED_DIRS``。
+"""
+import ast
+import pathlib
+
+BACKEND = pathlib.Path(__file__).resolve().parents[2]
+APP = BACKEND / "app"
+
+#: 被扫的生产层目录。``app/domain`` 一并扫：它由 allow-list 守卫更紧地管着，
+#: 列在这里只是让「谁能依赖 app.seed」这个问题有一个统一的取景框。
+SCANNED_DIRS = ("pipeline", "db", "domain")
+
+#: 生产层不得依赖的模块前缀
+FORBIDDEN_PREFIX = "app.seed"
+
+
+def _py_files(relative_dir: str) -> list[pathlib.Path]:
+    """一个生产层目录下的全部 ``.py``，按路径升序（报告顺序因此稳定可复现）。"""
+    root = APP / relative_dir
+    # Path.rglob() 对不存在的目录静默返回空，缺了这行守卫会空转全绿
+    assert root.is_dir(), f"目录缺失，架构测试将空转: {root}"
+    return sorted(root.rglob("*.py"))
+
+
+def _imported_modules(tree: ast.AST):
+    """yield ``(lineno, 完整模块串)``；``ast.walk`` 因此覆盖函数内导入。
+
+    相对导入（``node.level > 0``）一律跳过：它只可能落在**同一个包内**，而
+    ``app.pipeline`` / ``app.db`` / ``app.domain`` 三个包里都没有 ``app.seed``。
+    """
+    for node in ast.walk(tree):
+        if isinstance(node, ast.Import):
+            for alias in node.names:
+                yield node.lineno, alias.name
+        elif isinstance(node, ast.ImportFrom):
+            if node.level or not node.module:
+                continue
+            yield node.lineno, node.module
+
+
+def _is_forbidden(module: str) -> bool:
+    """按**完整模块串**判前缀，且只在 ``.`` 边界上匹配。
+
+    边界是必需的：裸 ``startswith("app.seed")`` 会把 ``app.seedling`` 这类
+    （今天不存在、但将来可能有的）合法模块误判成 offender。
+    """
+    return module == FORBIDDEN_PREFIX or module.startswith(FORBIDDEN_PREFIX + ".")
+
+
+def test_production_layers_never_import_app_seed():
+    """``app/pipeline`` / ``app/db`` / ``app/domain`` 不得 import ``app.seed``。
+
+    offender 一次性报全（``assert offenders == []``）：逐处 assert 的话第一个红会盖住
+    后面的，而迁移这四处是一次性的活，一次看全才不必跑四遍。
+    """
+    scanned: list[pathlib.Path] = []
+    offenders: list[str] = []
+    for relative_dir in SCANNED_DIRS:
+        for py in _py_files(relative_dir):
+            scanned.append(py)
+            tree = ast.parse(py.read_text(encoding="utf-8"))
+            for lineno, module in _imported_modules(tree):
+                if _is_forbidden(module):
+                    where = py.relative_to(BACKEND).as_posix()
+                    offenders.append(f"{where}:{lineno}: {module}")
+
+    # 空转守卫：目录被搬空 / 拼错时 offenders 恒为 []，测试会假绿。
+    # 基线 e26347f 上实测 pipeline 7 + db 4 + domain 6 = 17 个 .py
+    # （命令：python -c "…rglob('*.py')…"，见任务报告）。下界取 8 而不是 17：
+    # 拆包 / 合并模块会正常地改变文件数，17 会让一次合法重构也变红。
+    assert len(scanned) >= 8, f"只扫到 {len(scanned)} 个 .py，目录可能被搬空: {SCANNED_DIRS}"
+
+    assert offenders == [], (
+        f"生产层依赖了仿真数据生成器 app.seed（spec §3.3 依赖方向单向不可逆）：\n"
+        + "\n".join(offenders)
+    )
diff --git a/backend/tests/db/test_models.py b/backend/tests/db/test_models.py
index 7ebf7d8..8f9be97 100644
--- a/backend/tests/db/test_models.py
+++ b/backend/tests/db/test_models.py
@@ -1,20 +1,21 @@
 # backend/tests/db/test_models.py
 import datetime as dt
 import re
+import types
 import pytest
-from sqlalchemy import JSON as BuiltinJson, create_engine, inspect, text
+from sqlalchemy import JSON as BuiltinJson, create_engine, inspect, select, text
 from sqlalchemy.exc import IntegrityError
 from app.db.session import Base, init_db, Session
 from app.db import models as M
 from app.domain.derive import Trend
-from app.domain.indicators import AGE_GROUPS, Sex
+from app.domain.indicators import AGE_GROUPS, CLEANING_FIELDS, Sex
 from app.domain.percentile import (
     PercentileRow, SnapshotMetric, summarize_source,
 )
 from app.domain.stratify import RULE_ORDER, RuleId
 
 @pytest.fixture
 def session():
     eng = create_engine("sqlite:///:memory:")
     init_db(eng)
     with Session(eng) as s:
@@ -341,47 +342,289 @@ def test_string_column_widths_fit_their_value_domains():
     = ``"insufficient_data"`` 是 17 字符，500 人首批实测有 **209 行（41.8%）**往这一列写它。
     换 MySQL / PostgreSQL 会截断成 ``"insufficient_dat"``，读回来 ``Trend(...)`` 当场
     ``ValueError``——**炸在读侧不在写侧**，离真因隔一整个批处理周期。
 
     取值域的两个来源，都不是手抄的第二份清单：
 
     1. **有 CHECK 约束的列**——从 :func:`_in_domain` 生成的约束文本反解（今天恰好 10 列：
        ``student.sex``、``course_section.grouping_mode``、``fitness_test_batch.timepoint``、
        ``percentile_snapshot`` 的 ``source`` / ``sex`` / ``item``、``stratification_result``
        的 ``label`` / ``percentile_source``、``daily_sync_run.status``、``cleaning_log.kind``）。
-    2. **没有 CHECK 约束、但取值域有唯一所有者的三列**——见下方注释里各自的出处。
+    2. **没有 CHECK 约束、但取值域有唯一所有者的四列**——见下方注释里各自的出处。
     """
     domains = _in_domain_columns()
     # 空转守卫：正则写错会静默匹配到 0 列而全绿（那时 offenders 恒为空）。
     assert len(domains) >= 10, f"反解出的受约束列数不对，正则可能失配：{sorted(domains)}"
 
-    # 无 CHECK 约束的三列，取值域各自指向生产里的唯一所有者：
+    # 无 CHECK 约束的四列，取值域各自指向生产里的唯一所有者：
     # · ``derived_metrics.trend``       ← :class:`app.domain.derive.Trend` 的成员值
     #   （写入处 ``pipeline/daily.py`` 的 ``trend=derived.trend.value``），最长 17。
     # · ``stratification_result.hit_rules`` ← ``",".join(RuleId.value)``。Z0 路径恰为
     #   ``"Z0"``、非 Z0 路径是 7 条分层规则的已评估前缀，**两者互斥**（Ruling 132），
     #   故生产最大值是非 Z0 的完整前缀 ``"R1,R2,Y1,Y2,Y3,Y4,G1"`` = **20**，不是把 Z0
     #   也串起来的 23（Ruling 148）。
     # · ``percentile_snapshot.age_group`` ← :data:`app.domain.indicators.AGE_GROUPS`
     #   （全仓唯一口径），最长 5。
+    # · ``cleaning_log.field`` ← :data:`app.domain.indicators.CLEANING_FIELDS`
+    #   （**Plan 02 Task 1 新增**，Plan01 Ruling 156 的落点：这一列此前**没有任何所有者**，
+    #   13 个字段名散落在 ``clean.py`` 的 9 个写入点上）。最长 17 = ``"vital_capacity_ml"``。
+    #   它与清洗层实际产出的一致性由
+    #   ``tests/pipeline/test_clean.py::test_cleaning_fields_cover_every_produced_field``
+    #   钉住（那一侧从两个记录数据类的 ``fields()`` 推导，两侧不同源）。
     domains[("derived_metrics", "trend")] = {t.value for t in Trend}
     domains[("stratification_result", "hit_rules")] = {
         ",".join(rule.value for rule in RULE_ORDER if rule is not RuleId.Z0),
         RuleId.Z0.value,
     }
     domains[("percentile_snapshot", "age_group")] = set(AGE_GROUPS)
+    domains[("cleaning_log", "field")] = set(CLEANING_FIELDS)
 
     offenders: list[str] = []
     for (table_name, column_name), values in sorted(domains.items()):
         column = Base.metadata.tables[table_name].c[column_name]
         width = getattr(column.type, "length", None)
         if width is None:
             continue  # Text 一类无长度限制，不存在截断风险
         longest = max(values, key=len)
         if width < len(longest):
             offenders.append(
                 f"{table_name}.{column_name} 声明 String({width})，"
                 f"取值域里最长的却是 {longest!r}（{len(longest)} 字符）"
             )
     # 一次性报全：一列一个 assert 的话，第一个红会盖住后面的。
     assert offenders == [], "列宽容不下取值域（严格长度的后端会静默截断）：\n" + "\n".join(offenders)
 
+
+# ---------------------------------------------------------------------------
+# Plan 02 Task 1：models.py 拆包的导入面基线（Plan02 Ruling 1）
+# ---------------------------------------------------------------------------
+
+# 拆包**之前**在基线 ``e26347f`` 上实测的 ``app.db.models`` 公有导入面，逐字抄进来。
+# 取法（在 ``backend/`` 下跑，一次性取证，之后不再重跑——重跑就是拿拆包后的结果当基线）::
+#
+#     python -c "from app.db import models; import json; print(json.dumps(sorted(n for n in dir(models) if not n.startswith('_')), ensure_ascii=False))"
+#
+# **不从拆包后的 ``models`` 读回来跟自己比**（硬规矩 #35）：那样两侧同源，漏导出一个类
+# 两边一起少一个、恒等成立。这 33 个名字里既有 14 张表的类，也有 ``Base`` / ``JsonText``
+# 这两个真正被跨模块引用的基础设施，还有一批**偶然公有**的名字（``dt`` / ``json`` /
+# ``Boolean`` / ``mapped_column`` …）——它们本来就是单文件 ``models.py`` 的模块级 import，
+# 因此出现在 ``dir()`` 里。保留它们是判据「逐字相同」的应有代价：宁可多保住几个没人用的
+# 名字，也不要让判据松到抓不住「漏导出一个类」。
+_MODELS_PUBLIC_BASELINE = [
+    "Any", "Base", "BodyComposition", "Boolean", "CheckConstraint", "CleaningLog",
+    "CourseSection", "DailySyncRun", "Date", "DateTime", "DerivedMetrics", "Enrollment",
+    "FitnessTestBatch", "FitnessTestResult", "Float", "ForeignKey", "Integer",
+    "InterestSurvey", "Iterable", "JsonText", "Mapped", "PercentileSnapshot", "Semester",
+    "StratificationResult", "String", "Student", "Teacher", "Text", "TypeDecorator",
+    "UniqueConstraint", "dt", "json", "mapped_column",
+]
+
+# 拆包**新增**的六个子模块名。它们是包的结构性属性（``from .x import *`` 必然在父包上
+# 留下 ``x`` 这个属性），不是导入面，故从比对里排除。
+_MODELS_SUBMODULES = frozenset({
+    "organisation", "assessment", "derived", "prescription", "feedback", "ops",
+})
+
+# 拆包前的 ``__all__``（14 张表的声明序，spec §4.1→§4.6）
+_MODELS_ALL_BASELINE = [
+    "Semester", "Teacher", "Student", "CourseSection", "Enrollment",
+    "FitnessTestBatch", "FitnessTestResult", "BodyComposition", "InterestSurvey",
+    "PercentileSnapshot", "DerivedMetrics", "StratificationResult",
+    "DailySyncRun", "CleaningLog",
+]
+
+
+def test_models_public_namespace_is_unchanged_by_the_split():
+    """``app.db.models`` 拆成包之后，公有导入面**逐字未变**（Plan02 Ruling 1）。
+
+    这是「``from app.db import models`` 与 ``models.X`` 的既有写法不变」这句散文的
+    **唯一可执行判据**：散文不可执行，而「漏导出一个类」的失效形态是运行时才
+    ``AttributeError``——恰好是这条要求要防的事。
+
+    排除六个子模块名之前先断言两件事，好让排除本身不可能吞掉一次真回归：
+
+    1. 排除集与基线**不相交**（若哪天有人把一个表模块命名为 ``derived`` 之外又与基线
+       重名，这条会先红）；
+    2. 排除集里的每个名字**确实是一个模块**（若 ``organisation`` 哪天变成了一个类，
+       这条会红，而它就不该再被排除）。
+    """
+    assert len(_MODELS_PUBLIC_BASELINE) == 33, "基线是 33 个名字，抄漏了就当场红"
+    assert not (_MODELS_SUBMODULES & set(_MODELS_PUBLIC_BASELINE)), (
+        "排除集与基线相交，排除会吞掉真名字："
+        f"{sorted(_MODELS_SUBMODULES & set(_MODELS_PUBLIC_BASELINE))}"
+    )
+    for name in sorted(_MODELS_SUBMODULES):
+        assert isinstance(getattr(M, name, None), types.ModuleType), (
+            f"{name} 不再是子模块，就不该继续被排除在导入面比对之外"
+        )
+
+    observed = {n for n in dir(M) if not n.startswith("_")}
+    assert observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE), (
+        f"少了 {sorted(set(_MODELS_PUBLIC_BASELINE) - observed)}，"
+        f"多了 {sorted(observed - _MODELS_SUBMODULES - set(_MODELS_PUBLIC_BASELINE))}"
+    )
+    assert list(M.__all__) == _MODELS_ALL_BASELINE
+
+    # 私有名里有一个是**承重的**：约束文本生成器。它带前导下划线故不在上面的比对里，
+    # 但 tests/db/test_models.py 自己的注释与将来的迁移脚本都按
+    # ``app.db.models._in_domain`` 引用它，故单独钉一条。
+    assert callable(M._in_domain)
+    # 14 张表一个不少地注册进了同一个 metadata（拆包最容易漏的就是这个）
+    assert len(Base.metadata.tables) == 14
+    for name in _MODELS_ALL_BASELINE:
+        assert getattr(M, name).__tablename__ in Base.metadata.tables
+
+
+# ---------------------------------------------------------------------------
+# Plan 02 Task 1 Step 4：fitness_test_result.tested_on 与 daily_sync_run 的计数列
+# ---------------------------------------------------------------------------
+
+def _semester_and_student(session):
+    sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
+                     end_date=dt.date(2026, 1, 20), weeks=16, is_current=True)
+    session.add(sem)
+    session.flush()
+    stu = M.Student(student_no="2025001001", name="张三", sex="male",
+                    birth=dt.date(2006, 3, 4), grade=1)
+    session.add(stu)
+    session.flush()
+    batch = M.FitnessTestBatch(semester_id=sem.id, timepoint="week1",
+                               test_date=dt.date(2025, 9, 1))
+    session.add(batch)
+    session.flush()
+    return sem, stu, batch
+
+
+def test_fitness_test_result_tested_on_is_required(session):
+    """``fitness_test_result.tested_on`` NOT NULL 且无缺省：漏传必须**当场炸**。
+
+    这一列是「本条成绩是哪一天测的」的唯一所有者，而百分位阶段靠它按业务日期截断
+    （``percentile_stage._results_of`` 的 ``tested_on <= as_of``）。做成可空的代价是
+    静默的：``NULL <= as_of`` 在 SQL 里恒为 **NULL**（不是 TRUE 也不是 FALSE），
+    ``WHERE`` 因此把那一行**悄悄丢掉**，于是「这个学生今天没有成绩」与「这个学生的成绩
+    没写日期」在库里长得一模一样，而前者会让他走 Z0 → ``insufficient_data``。
+    """
+    _sem, stu, batch = _semester_and_student(session)
+    column = M.FitnessTestResult.__table__.c.tested_on
+    assert column.nullable is False, "本列不许为空，故必须显式给值"
+    assert column.default is None, "也不得有缺省值：缺省会让「忘了写」看起来像「写了」"
+
+    session.add(M.FitnessTestResult(test_batch_id=batch.id, student_id=stu.id,
+                                    height_cm=172.5))
+    with pytest.raises(IntegrityError) as excinfo:
+        session.flush()
+    assert "fitness_test_result.tested_on" in str(excinfo.value)
+    # 失败的 flush 让会话进入「必须回滚」状态；回滚把上面那三行夹具也一起撤掉
+    # （它们从未 commit），故正向那一段重新建一次。
+    session.rollback()
+    _sem, stu, batch = _semester_and_student(session)
+
+    # 给了值就照常落库、读回同一个日期
+    day = dt.date(2025, 9, 4)
+    session.add(M.FitnessTestResult(test_batch_id=batch.id, student_id=stu.id,
+                                    tested_on=day, height_cm=172.5))
+    session.flush()
+    session.expire_all()
+    assert session.scalar(select(M.FitnessTestResult)).tested_on == day
+
+
+def test_daily_sync_run_carries_the_plan02_count_columns(session):
+    """``muscle_line_gaps`` / ``prescription_count`` / ``alert_count`` 三列都在、都默认 0。
+
+    ⚠️ **``prescription_count`` 与 ``alert_count`` 是 Plan 01 就建好的**：基线 ``e26347f``
+    的 ``app/db/models.py:614-615`` 已经有这两列（``git grep -n "prescription_count" --
+    backend/app`` 可复验）。Plan 02 计划原文写的「spec §4.6 明确列了『处方生成数、
+    预警触发数』两列，**Plan 01 没建**」与基线不符，故 Task 1 没有新增它们，本测试只是
+    把「三列都在、都默认 0」钉住，免得后面的人以为要再建一次。
+
+    ``muscle_line_gaps`` 是本 Task **真正新增**的那一列，它取代了此前写进
+    ``error_summary`` 的「注意（非错误）：N 个组没有肌肉量 P20 判定线……」自由文本
+    （Plan02 Ruling 13：直接切、不双写）。默认 0 与其余计数列同一条理由——运行记录常在
+    跑完之前就入库（要先拿到 ``id`` 当 ``batch_id`` 用），此时它是「还没数」而不是「未知」。
+    """
+    columns = M.DailySyncRun.__table__.columns
+    for name in ("muscle_line_gaps", "prescription_count", "alert_count"):
+        assert name in columns, f"daily_sync_run 缺列 {name}"
+        assert columns[name].nullable is False, f"{name} 不许为空"
+        assert columns[name].default.arg == 0, f"{name} 的默认值必须是 0"
+
+    sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
+                     end_date=dt.date(2026, 1, 20), weeks=16, is_current=True)
+    session.add(sem)
+    session.flush()
+    run = M.DailySyncRun(semester_id=sem.id, business_date=dt.date(2025, 9, 15))
+    session.add(run)
+    session.flush()
+    run_id = run.id
+    session.expire_all()
+    got = session.get(M.DailySyncRun, run_id)
+    assert (got.muscle_line_gaps, got.prescription_count, got.alert_count) == (0, 0, 0)
+    # error_summary 不再承载缺线提示：一个成功的运行它就是 NULL
+    assert got.error_summary is None
+
+
+# ---------------------------------------------------------------------------
+# Plan 02 Task 1 Step 4 第 1 项：单人「当前分层」查询必须走索引
+# ---------------------------------------------------------------------------
+
+#: 两条生产读法：教师大屏点一个人看「他现在什么层」，以及看他的派生指标。
+_SINGLE_PERSON_QUERIES = (
+    ("stratification_result",
+     "select id from stratification_result "
+     "where student_id = 1 order by computed_on desc limit 1"),
+    ("derived_metrics",
+     "select id from derived_metrics "
+     "where student_id = 1 and computed_on <= '2025-09-15' "
+     "order by computed_on desc limit 1"),
+)
+
+
+def test_single_person_queries_are_index_served(session):
+    """两条单人查询必须走 ``(student_id, computed_on)`` 索引，不得全表扫、不得另建临时 B-tree。
+
+    **这条测试取代了计划 Step 4 第 1 项要的显式 ``Index``**，理由是本仓实测那条索引是
+    **冗余**的：Plan01 Ruling 212 已经给这两张表加了
+    ``UniqueConstraint("student_id", "computed_on")``，而 SQLite 会为 UNIQUE 约束自动建出
+    一条同列序的索引（``sqlite_autoindex_<table>_1``），查询规划器已经在用它。
+
+    实测（本机、CPython 3.11 + SQLAlchemy 2.1 + SQLite；500 人 × 112 业务日 = **56000 行**
+    ``stratification_result``；每条查询 300 次、随机学号、``random.Random(20250828)``；
+    落磁盘库后按 ``.db`` 文件字节量体积）：
+
+    ==============================  ==================  ==================  =====================
+    场景                             单次墙钟中位 (ms)    ``.db`` 字节        EXPLAIN QUERY PLAN
+    ==============================  ==================  ==================  =====================
+    A 仅 UniqueConstraint 的自动索引        0.2708           5 423 104        ``USING COVERING INDEX sqlite_autoindex_stratification_result_1 (student_id=?)``
+    B A + 显式 ``Index(student_id, computed_on)``  0.2941      6 791 168        ``USING COVERING INDEX ix_stratification_result_student_computed (student_id=?)``
+    ==============================  ==================  ==================  =====================
+
+    B/A = **1.086**（即加了索引**没有变快**，中位数还慢了 8.6%，n=300，两个场景各自
+    min…max = 0.1385…0.9031 与 0.1698…1.0212 ms，区间完全重叠），而文件体积
+    **+1 368 064 B = +25.23%**（十进制百分比；计划原文写的代价是「+2.7% 文件体积」，
+    与本次实测差一个量级）。计划原文的收益数字「57.9 ms → 0.2 ms（258×）」因此只能来自
+    一个**没有**那条 UNIQUE 约束的 schema——即 Plan01 Ruling 212 落地之前的状态。
+
+    所以本测试守的是**结果**（走索引、不全表扫、不排序）而不是**机制**（某条具名索引存在）。
+    这样它同时挡住两种回归：有人删掉 UNIQUE 约束而没补索引，以及有人加了一条列序不对的
+    索引（如 ``(computed_on, student_id)``——前导列不是 ``student_id`` 时这条查询用不上它）。
+    """
+    # 用会话自己那条连接：``session.get_bind()`` 给的是 ``Engine``，SQLAlchemy 2.x 上它
+    # 没有 ``.execute``；而另开一条连接会离开本会话的事务（夹具是 ``sqlite:///:memory:``，
+    # 是否还是同一个库取决于连接池策略，不该由本测试来赌）。
+    conn = session.connection()
+    for table, query in _SINGLE_PERSON_QUERIES:
+        detail = [row[3] for row in conn.execute(text("explain query plan " + query))]
+        assert len(detail) == 1, f"{table} 的查询计划不止一步：{detail}"
+        plan = detail[0]
+        assert "SCAN" not in plan, f"{table} 走了全表扫：{plan}"
+        assert "USING" in plan and "INDEX" in plan, f"{table} 没用索引：{plan}"
+        # 前导列必须是 student_id：列序反过来的索引对这条查询毫无用处
+        assert "student_id=?" in plan, f"{table} 的索引前导列不是 student_id：{plan}"
+        # 排序由索引本身供给；出现这一句就说明规划器另建了临时 B-tree
+        assert "TEMP B-TREE" not in plan, f"{table} 为 ORDER BY 另建了临时 B-tree：{plan}"
+
+    # 守卫自己也得有牙：那条自动索引确实在库里，且列序是 (student_id, computed_on)
+    for table in ("stratification_result", "derived_metrics"):
+        uniques = {u["name"]: u["column_names"]
+                   for u in inspect(conn).get_unique_constraints(table)}
+        assert uniques[f"uq_{table}_student_day"] == ["student_id", "computed_on"], uniques
+
diff --git a/backend/tests/db/test_repo.py b/backend/tests/db/test_repo.py
index 6de2288..952c634 100644
--- a/backend/tests/db/test_repo.py
+++ b/backend/tests/db/test_repo.py
@@ -199,20 +199,22 @@ def test_upsert_updates_existing_row_without_duplicating(session):
     assert (row.name, row.grade) == ("张三丰", 2), "非键字段应被更新"
     assert second is first, "走的是更新分支，返回同一个实例而非新对象"
 
 
 def test_upsert_handles_composite_key(session, seeded):
     """复合自然键 ``(test_batch_id, student_id)``——Ruling 24 给体测结果定的那把键。"""
     key = ["test_batch_id", "student_id"]
     values = {
         "test_batch_id": seeded["fitness_batch_id"],
         "student_id": seeded["student_ids"][0],
+        # tested_on 是 NOT NULL（Plan 02 Task 1 新列），故它属于「必须传的完整列集合」
+        "tested_on": dt.date(2025, 9, 10),
         "height_cm": 172.5,
         "weight_kg": 65.0,
     }
     repo.upsert(session, M.FitnessTestResult, key, dict(values))
     session.flush()
     repo.upsert(session, M.FitnessTestResult, key, {**values, "height_cm": 173.0})
     session.flush()
     session.expire_all()
 
     assert _count(session, M.FitnessTestResult) == 1, "两列全同即为同一行，不得翻倍"
@@ -339,20 +341,22 @@ def test_delete_by_batch_rejects_fitness_test_result(session, seeded):
     删源数据比删派生行严重：派生行重算就回来了，源体测数据删了就是删了。
     """
     assert seeded["fitness_batch_id"] == seeded["sync_run_id"], (
         "两个 id 数值相同是本测试的前提，否则它测不到裁定点名的那种混淆"
     )
 
     session.add(
         M.FitnessTestResult(
             test_batch_id=seeded["fitness_batch_id"],
             student_id=seeded["student_ids"][0],
+            # tested_on 是 NOT NULL（Plan 02 Task 1 新列，见 FitnessTestResult 的列注释）
+            tested_on=dt.date(2025, 9, 10),
             height_cm=172.5,
         )
     )
     session.flush()
     assert _count(session, M.FitnessTestResult) == 1
 
     with pytest.raises(AttributeError) as excinfo:
         repo.delete_by_batch(session, M.FitnessTestResult, seeded["sync_run_id"])
     message = str(excinfo.value)
     assert "FitnessTestResult" in message, "报错要点名是哪个模型"
@@ -362,20 +366,22 @@ def test_delete_by_batch_rejects_fitness_test_result(session, seeded):
 
 # ---------------------------------------------------------------------------
 # 三张源数据表的业务唯一约束（Ruling 24）
 # ---------------------------------------------------------------------------
 
 def _fitness_result(ids: dict, **over) -> M.FitnessTestResult:
     """week1 批次里第一名学生的一条体测记录；``over`` 用来覆盖非键字段。"""
     base = {
         "test_batch_id": ids["fitness_batch_id"],
         "student_id": ids["student_ids"][0],
+        # 与 _fitness_batch 的 test_date 同一天（Plan 02 Task 1 起本列 NOT NULL）
+        "tested_on": dt.date(2025, 9, 10),
         "height_cm": 172.5,
         "weight_kg": 65.0,
     }
     return M.FitnessTestResult(**{**base, **over})
 
 
 def _body_composition(ids: dict, **over) -> M.BodyComposition:
     base = {
         "student_id": ids["student_ids"][0],
         "measured_on": dt.date(2025, 9, 12),
diff --git a/backend/tests/domain/test_derive.py b/backend/tests/domain/test_derive.py
index ce6e878..359a8b4 100644
--- a/backend/tests/domain/test_derive.py
+++ b/backend/tests/domain/test_derive.py
@@ -6,25 +6,25 @@
 """
 import inspect
 
 import pytest
 
 from app.domain.derive import (
     Trend, classify_trend, derive, find_weaknesses, flag_body_comp, national_total,
 )
 from app.domain.percentile import PercentileRow
 from app.domain.indicators import (
-    AGE_GROUPS, WEAKNESS_ITEMS, ScoredItem, Sex, age_group_of, score_item,
+    AGE_GROUPS, COLUMN_BY_ITEM, WEAKNESS_ITEMS, ScoredItem, Sex, age_group_of,
+    score_item,
 )
 from app.refdata import standard
 from app.seed.config import SEMESTERS, SeedConfig
-from app.seed.fitness import COLUMN_BY_ITEM
 from app.seed.generate import build_dataset
 
 # 计划 Step 1 用 ``ScoredItem as I`` 导入，但同一段代码里的 ``total()`` 助手写的是
 # ``ScoredItem.BMI``——两个名字都要能用，故导入真名再起别名（见报告关切）。
 I = ScoredItem
 
 LOWER_GRADE = AGE_GROUPS[0]        # "大一、大二"
 UPPER_GRADE = AGE_GROUPS[1]        # "大三、大四"
 
 
diff --git a/backend/tests/domain/test_indicators.py b/backend/tests/domain/test_indicators.py
index 26c613c..9f37d0e 100644
--- a/backend/tests/domain/test_indicators.py
+++ b/backend/tests/domain/test_indicators.py
@@ -1,16 +1,17 @@
 """国标 2014 指标定义与评分正查/反查的行为约束。"""
 import pytest
 
 from app.domain.indicators import (
     Sex, ScoredItem, WEAKNESS_ITEMS, ITEM_BUCKET, ITEM_WEIGHTS, AGE_GROUPS,
-    age_group_of, score_item, raw_from_score, segment_thresholds,
+    CLEANING_FIELDS, COLUMN_BY_ITEM, WHOLE_RECORD,
+    age_group_of, bmi_of, score_item, raw_from_score, segment_thresholds,
 )
 from app.refdata import standard
 
 T = standard()          # 表由 refdata 加载后注入，domain 自身不读盘（Ruling 15）
 G = age_group_of(19)
 
 # 全部测试一律从评分表自身推导档位与档位分，不硬编码 CSV 数值——
 # 将来一次合法的数据更正不应该弄红测试。唯一例外见
 # test_bmi_unrounded_value_scores_correctly 里的说明。
 EPS = 1e-6
@@ -278,10 +279,118 @@ def test_raw_from_score_and_thresholds_raise_keyerror_for_absent_key():
     with pytest.raises(KeyError):
         raw_from_score(T, ScoredItem.VITAL_CAPACITY, 80, Sex.MALE, "不存在的年级组")
     with pytest.raises(KeyError):
         segment_thresholds(T, ScoredItem.VITAL_CAPACITY, Sex.MALE, "不存在的年级组")
 
 def test_domain_functions_are_pure_and_take_table_explicitly():
     # Ruling 15：同一个表对象传入两次结果必须一致，且 domain 不依赖任何全局加载状态
     a = score_item(T, ScoredItem.STANDING_JUMP, 230.0, Sex.MALE, G)
     b = score_item(T, ScoredItem.STANDING_JUMP, 230.0, Sex.MALE, G)
     assert a == b and a is not None
+
+
+# ---------------------------------------------------------------------------
+# Plan 02 Task 1 迁进 domain 的四样东西：bmi_of / COLUMN_BY_ITEM /
+# WHOLE_RECORD / CLEANING_FIELDS
+# ---------------------------------------------------------------------------
+
+def test_bmi_of_rounds_to_one_decimal():
+    """``bmi_of`` 的两个字面期望值（不从被测函数读回来跟自己比，硬规矩 #35）。
+
+    ``65.0 / 1.725² = 21.84399…`` → ``round(…, 1) = 21.8``。
+    ``80.0 / 1.60² = 31.25``（二进制下精确可表示）→ ``round(31.25, 1) = 31.2``，
+    **不是 31.3**：CPython 的 ``round`` 是银行家舍入（round-half-to-even）。
+    第二个值因此不只是「算对了」，它还钉住了「本函数用的是 ``round`` 而不是
+    ``math.floor(x*10+0.5)/10`` 这类半进位实现」——两者在 ``.25`` 这个输入上分道。
+
+    ``round(…, 1)`` 是承重的：国标 BMI 档位是区间映射，生成器也算到 1 位小数，
+    两侧差 0.05 就可能在档位边界上翻档（进而翻 ``score_bmi``、翻 15% 权重的总分贡献）。
+    """
+    assert bmi_of(172.5, 65.0) == 21.8
+    assert bmi_of(160.0, 80.0) == 31.2
+
+
+@pytest.mark.parametrize("height,weight", [
+    (None, 65.0),      # 身高缺测
+    (172.5, None),     # 体重缺测
+    (None, None),      # 两项都缺测
+])
+def test_bmi_of_returns_none_for_missing_input(height, weight):
+    """任一为 ``None`` → ``None``，**绝不当 0**（Plan01 Ruling 21）。
+
+    三个参数化用例覆盖 ``if height_cm is None or weight_kg is None`` 的两个操作数：
+    第一个走 ``or`` 左侧短路、第二个走右侧、第三个两侧都真。少任何一个，
+    ``--cov-branch`` 下这一行的分支就只被覆盖一半（BrPart）。
+    """
+    assert bmi_of(height, weight) is None
+
+
+def test_bmi_zero_would_score_eighty_not_none():
+    """上一条坚持返回 ``None`` 的代价核算：``score_item(BMI, 0.0)`` = **80**。
+
+    这是「缺测当 0」在 BMI 上的具体后果，四个 (性别 × 年级组) 组全部实测 80——
+    BMI 档位的最低哨兵 ``raw_value`` 就是 ``0``（CSV 用它封住「低于某个 BMI」那个
+    开口区间），而它对应的官方档是 80。于是一个从未被测过的身高/体重会变成
+    「BMI 低到不存在、却仍拿 80 分与 15% 权重」，全程不报错。
+    期望值 80 写死在这里，不从评分表读回来（硬规矩 #35）。
+    """
+    for sex in Sex:
+        for group in AGE_GROUPS:
+            assert score_item(T, ScoredItem.BMI, 0.0, sex, group) == 80
+
+
+def test_column_by_item_is_exactly_the_six_weakness_items():
+    """``COLUMN_BY_ITEM`` 的键恰为 6 个短板判定项，值为**字面写死**的原始列名。
+
+    这张映射无法从名字推导（``pull_up_or_sit_up`` 对应的是 ``strength_count``），
+    抄错的后果是某一项恒为 ``None``、该桶短板静默消失，而 ``score_raw`` 全程不报错。
+    **BMI 不在里面**：它是「8 项原始测量 → 7 个国标计分项」里由身高与体重合成的那一项，
+    没有自己的原始列（合成算式是 :func:`bmi_of`）。
+
+    值与 ``RawFitnessRecord`` 的字段名对齐由
+    ``tests/pipeline/test_clean.py::test_cleaning_fields_cover_every_produced_field``
+    那一侧核对（两侧不同源：这里写字面量，那里从数据类 ``fields()`` 推导）。
+    """
+    assert set(COLUMN_BY_ITEM) == set(WEAKNESS_ITEMS)
+    assert len(COLUMN_BY_ITEM) == 6
+    assert ScoredItem.BMI not in COLUMN_BY_ITEM
+    assert COLUMN_BY_ITEM == {
+        ScoredItem.VITAL_CAPACITY: "vital_capacity_ml",
+        ScoredItem.SPRINT_50M: "sprint_50m_s",
+        ScoredItem.SIT_AND_REACH: "sit_and_reach_cm",
+        ScoredItem.STANDING_JUMP: "standing_jump_cm",
+        ScoredItem.PULL_UP_OR_SIT_UP: "strength_count",
+        ScoredItem.DISTANCE_RUN: "distance_run_s",
+    }
+
+
+def test_cleaning_fields_is_the_vocabulary_of_cleaning_log_field():
+    """``cleaning_log.field`` 的取值域，13 个值**字面写死**（Plan01 Ruling 156 的落点）。
+
+    ⚠️ **计划原文的公式只有 8 个**：它写的是「``COLUMN_BY_ITEM`` 的值 ∪
+    ``{"student_no"}`` ∪ ``WHOLE_RECORD``」，漏了 5 个测量列——``height_cm`` 与
+    ``weight_kg``（它们**不在** ``COLUMN_BY_ITEM`` 里，因为那一列只覆盖 6 个短板判定项，
+    而这两项合成 BMI），以及体成分的 ``muscle_mass_kg`` / ``body_fat_pct`` / ``smi``。
+    照那个公式写的话列宽守卫会有 5 个字段名裸奔，而最长的 ``vital_capacity_ml``
+    （17 字符）恰好**在**那 8 个里，所以守卫看上去仍然有效——这正是「用样本推断清单」
+    的典型失效形态（硬规矩 #27）。
+
+    全量口径来自生产侧的**全部**写入点：``git grep -n "field=" --
+    backend/app/pipeline/clean.py backend/app/pipeline/daily.py`` 在基线 ``e26347f``
+    上报 9 处，逐处归类见 :data:`app.domain.indicators.CLEANING_FIELDS` 的注释。
+    """
+    assert WHOLE_RECORD == "*"
+    assert CLEANING_FIELDS == frozenset({
+        # 6 个短板判定项的原始列
+        "vital_capacity_ml", "sprint_50m_s", "sit_and_reach_cm",
+        "standing_jump_cm", "strength_count", "distance_run_s",
+        # 合成 BMI 的那两项，同样逐字段过清洗（height_cm 还有专属的 unit_normalized）
+        "height_cm", "weight_kg",
+        # 体成分的三个测量列
+        "muscle_mass_kg", "body_fat_pct", "smi",
+        # 记录级：学号无法归属（整条剔除）与整条重复（去重）
+        "student_no", "*",
+    })
+    assert len(CLEANING_FIELDS) == 13
+    # 最长值 17 字符必须装得进 cleaning_log.field 的 String(32)；那一侧的核对在
+    # tests/db/test_models.py 的列宽遍历测试里用 ORM 元数据做（两侧不同源）。
+    assert max(len(f) for f in CLEANING_FIELDS) == 17 == len("vital_capacity_ml")
diff --git a/backend/tests/pipeline/test_clean.py b/backend/tests/pipeline/test_clean.py
index 7ee77a0..ef4777c 100644
--- a/backend/tests/pipeline/test_clean.py
+++ b/backend/tests/pipeline/test_clean.py
@@ -12,21 +12,24 @@
 ``test_dropped_and_corrected_counters_exclude_duplicate_removed`` 的被丢弃行由干净改为弄脏，
 好让「去重先于清洗」这个顺序真的能被钉住（M4）。
 """
 import pathlib
 from dataclasses import replace
 
 import pytest
 import yaml
 
 from app.adapters.base import RawFitnessRecord, RawBodyCompRecord
+from app.domain.indicators import CLEANING_FIELDS
 from app.pipeline.clean import (
+    BODY_COMP_MEASURE_FIELDS,
+    FITNESS_MEASURE_FIELDS,
     WHOLE_RECORD,
     clean_body_comp,
     clean_fitness,
     load_ranges,
     normalize_height,
 )
 
 RANGES_PATH = pathlib.Path(__file__).parents[2] / "data" / "indicator_ranges.yaml"
 RANGES = load_ranges(RANGES_PATH)
 
@@ -350,10 +353,68 @@ def test_load_ranges_rejects_malformed_field_configuration(tmp_path, field, over
     # M3：_parse_range 的每一道守卫都要有测试——「未测的守卫等于没有守卫」。其中 min: true
     # 这一条正是整套类型守卫存在的理由：bool 是 int 的子类，不排除布尔就会把 true 当成 1
     # 静默通过，区间下界于是变成 1，而任何地方都不会报错。
     path = _mutated_ranges(tmp_path, field, override)
     with pytest.raises(ValueError) as excinfo:
         load_ranges(path)
     message = str(excinfo.value)
     assert expected in message
     assert field in message           # 报错必须指名是哪个字段
     assert str(path) in message       # 以及是哪个文件
+
+
+# ---------------------------------------------------------------------------
+# Plan 02 Task 1：``cleaning_log.field`` 的取值域唯一所有者（Plan01 Ruling 156）
+# ---------------------------------------------------------------------------
+
+
+def test_cleaning_fields_cover_every_produced_field():
+    """``app.domain.indicators.CLEANING_FIELDS`` == 清洗层**实际会写进 ``field`` 的**全部值。
+
+    **两侧不同源**（硬规矩 #35）：
+
+    * 左侧是 domain 里那份**字面写死**的 ``frozenset``（13 个字符串，另有一条
+      ``tests/domain/test_indicators.py::test_cleaning_fields_is_the_vocabulary_of_cleaning_log_field``
+      逐字钉住它）；
+    * 右侧是从 ``RawFitnessRecord`` / ``RawBodyCompRecord`` 的**字段声明序**推导出来的
+      （``dataclasses.fields()``，与 ``load_ranges`` 的键集合校验同一手法），加上两个
+      **记录级**取值 ``student_no``（学号无法归属时整条剔除）与 ``WHOLE_RECORD``
+      （整条重复被去除）。
+
+    所以「往记录数据类里加一个测量列而忘了更新 ``CLEANING_FIELDS``」会让本测试当场红——
+    而那正是列宽守卫会漏掉新字段名的唯一途径。
+
+    **为什么这一条重要**：``cleaning_log.field`` 是 ``String(32)`` 且**没有 CHECK 约束**，
+    故此前没有任何东西保证 32 装得下最长的字段名。SQLite 不强制 ``VARCHAR`` 长度，换
+    MySQL / PostgreSQL 会静默截断——与 Plan01 Ruling 144 的
+    ``derived_metrics.trend String(16)`` 是同一个缺陷形态（那一列漏了 7 个任务，
+    500 人首批实测 209 行 = 41.8% 写的是 17 字符的 ``"insufficient_data"``）。
+    列宽那一侧的核对在 ``tests/db/test_models.py`` 的列宽遍历测试里做。
+    """
+    assert len(FITNESS_MEASURE_FIELDS) == 8, FITNESS_MEASURE_FIELDS
+    assert len(BODY_COMP_MEASURE_FIELDS) == 3, BODY_COMP_MEASURE_FIELDS
+
+    produced = (
+        set(FITNESS_MEASURE_FIELDS)
+        | set(BODY_COMP_MEASURE_FIELDS)
+        | {"student_no", WHOLE_RECORD}
+    )
+    assert CLEANING_FIELDS == produced, (
+        f"缺 {sorted(produced - CLEANING_FIELDS)}，"
+        f"多 {sorted(CLEANING_FIELDS - produced)}"
+    )
+    assert len(CLEANING_FIELDS) == 13
+
+    # 两个记录级取值在生产路径上**确实会被写出来**（不是纸面推导）：
+    # ① 学号全空白 → 整条剔除，field = "student_no"（Ruling 47）
+    blank = clean_fitness([rec(student_no="   ")], RANGES)
+    assert {e.field for e in blank.entries} == {"student_no"}
+    assert blank.fitness == [] and blank.dropped == 1
+    # ② 同学号同批次两行 → 去重，field = WHOLE_RECORD（Ruling 48/50）
+    dup = clean_fitness([rec(tested_on="2025-09-04"), rec(tested_on="2025-09-06")], RANGES)
+    assert {e.field for e in dup.entries if e.kind == "duplicate_removed"} == {WHOLE_RECORD}
+    # ③ 逐字段处置走的是测量列名本身
+    missing = clean_fitness([rec(vital_capacity_ml=None)], RANGES)
+    assert "vital_capacity_ml" in {e.field for e in missing.entries}
+    # ④ 量纲归一是 height_cm 专属的 unit_normalized 写入点
+    _, unit_entry = normalize_height(1.75)
+    assert unit_entry.field == "height_cm" and unit_entry.kind == "unit_normalized"
diff --git a/backend/tests/pipeline/test_daily.py b/backend/tests/pipeline/test_daily.py
index 86e6fd3..ff25ef5 100644
--- a/backend/tests/pipeline/test_daily.py
+++ b/backend/tests/pipeline/test_daily.py
@@ -23,22 +23,23 @@
 数据一律来自 ``tmp_path`` 里的独立 sqlite 文件与临时 CSV 目录：不碰 ``backend/pe.db``，
 也不往 ``backend/data/seed/`` 写任何东西（Ruling 68）。
 学期一律按**名字**取（:func:`semester_id`，Ruling 173）：``scalar(select(M.Semester))`` 会
 取到先插入的上学年 ``2024-2025-1``，那既不是 CLI 会跑的路径、也不是幂等键该用的那一半。
 """
 import csv, datetime as dt, hashlib, json, pathlib, pytest
 from collections import Counter
 from sqlalchemy import create_engine, func, select
 from app.db.session import init_db, Session
 from app.db import models as M
-from app.adapters.base import FITNESS_FILENAME
+from app.adapters.base import FITNESS_COLUMNS, FITNESS_FILENAME
 from app.adapters.mock_lepao import MockLePaoAdapter
+from app.pipeline import daily
 from app.pipeline.daily import require_dates_in_semester, run_daily, semester_by_name
 from app.pipeline.extract import previous_watermark
 from app.pipeline.run_stratify import stratify_dataset
 from app.seed.generate import seed_database, build_dataset, write_csv
 from app.seed.config import SEMESTERS, SeedConfig, semester_end_date
 
 CFG = SeedConfig(students=60, weeks=16, seed=20250828)
 
 # 趋势真值对账专用（Ruling 140 / 75②）：**零注入**。缺省注入下 4% 的缺测会让
 # national_total 变成 None → 趋势 INSUFFICIENT（合法状态，但对不了账），0.5% 的越界会把
@@ -575,10 +576,176 @@ def test_rerunning_the_same_business_date_reproduces_every_table(session, seed_d
     second, rows_second = canonical_dump(session)
 
     assert rows_first == rows_second, (rows_first, rows_second)
     assert sum(rows_first.values()) > 0                  # 反空转：真的 dump 到了行
     assert first == second, "同一业务日期重跑后全表 canonical sha256 不同"
 
     # 被排除的那两列**确实**变了（否则「排除它们」这个口径就没被证明是必要的，
     # 本条也就退化成一条普通的行数断言）
     assert session.scalar(select(M.DailySyncRun.started_at)) != started_first
     assert session.scalar(select(func.count()).select_from(M.DailySyncRun)) == 1
+
+
+# ---------------------------------------------------------------------------
+# Plan 02 Task 1 Step 5：fitness_test_batch.test_date 不得随抽取窗口漂移
+# ---------------------------------------------------------------------------
+
+#: 缺省种子数据里本学年 week1 那批的采集日**只有一个**，故先把它摊成多日，
+#: 「test_date 随抽取窗口漂移」才可达。5 天 × 60 人 = 每天 12 人。
+_SPREAD_DAYS = ("2025-09-01", "2025-09-02", "2025-09-03", "2025-09-04", "2025-09-05")
+
+
+def _spread_week1_tested_on(seed_dir: pathlib.Path, days: tuple[str, ...]) -> int:
+    """把 ``fitness.csv`` 里本学年 ``week1`` 那批记录的 ``tested_on`` 按行序轮转到 ``days`` 上。
+
+    **为什么必须自己造多日批次**：缺省种子数据里一个批次只有一个采集日（实测 60 人 /
+    ``seed=20250828``，命令是 ``build_dataset(CFG)`` 之后按 ``parse_batch_key`` 分组数
+    ``tested_on`` 的 distinct 值）::
+
+        ('2024-2025', 'week1')   n=60  distinct=['2024-09-02']
+        ('2024-2025', 'week8')   n=61  distinct=['2024-10-21']
+        ('2024-2025', 'week16')  n=61  distinct=['2024-12-16']
+        ('2025-2026', 'week1')   n=60  distinct=['2025-09-01']
+        ('2025-2026', 'week8')   n=61  distinct=['2025-10-20']
+        ('2025-2026', 'week16')  n=62  distinct=['2025-12-15']
+
+    每组恰好一个值，于是「同一份 CSV、只改执行顺序就得到不同的 ``test_date``」在缺省数据上
+    **不可达**——这正是终审 B「构造了反例但没能演示 anchor 真的翻转」的原因，也是它把这条
+    定为 Major 而不是 Critical 的原因。真实的乐跑接口不会这么整齐：一次 week1 体测跨好几个
+    采集日是常态（院系轮流进场）。
+    """
+    path = seed_dir / FITNESS_FILENAME
+    with path.open(newline="", encoding="utf-8-sig") as fh:
+        rows = list(csv.DictReader(fh))
+    touched = 0
+    for row in rows:
+        if row["batch_key"] == "2025-2026|week1":
+            row["tested_on"] = days[touched % len(days)]
+            touched += 1
+    assert touched == 60, f"本学年 week1 的记录数不是 60，夹具口径变了：{touched}"
+    with path.open("w", newline="", encoding="utf-8") as fh:
+        writer = csv.DictWriter(fh, fieldnames=FITNESS_COLUMNS, lineterminator="\n")
+        writer.writeheader()
+        writer.writerows(rows)
+    return touched
+
+
+def test_fitness_batch_folds_test_date_to_the_earliest(session):
+    """``_fitness_batch`` 对乱序的日期做 ``min`` 折叠，且四次调用只产生**一行**批次。
+
+    直接喂乱序日期而不走 ``run_daily``：缺省数据造不出多日批次（见
+    :func:`_spread_week1_tested_on` 的 docstring），而折叠本身是这个修复的全部内容。
+
+    四次调用的期望值逐个**写死**（硬规矩 #35，不从被测函数读回来）。改回「每条记录都
+    PATCH ``test_date``」之后第三次会得到 ``2025-09-05`` 而不是 ``2025-09-01``，当场红。
+
+    ``min`` 折叠而不是「插入时写、更新时不动」：后者仍然依赖执行顺序（先跑的那天赢），
+    而 ``min`` 可交换、可结合，任意顺序任意次重放都收敛到同一个值。取「最早」也符合语义
+    ——``assessment_anchor`` 用这一列当「该批次是否已可用」的判据，用**开始日**是保守侧
+    （宁可晚一点认它可用），而批次内更晚的那些记录由
+    ``fitness_test_result.tested_on <= as_of`` 逐行截断兜住。
+    """
+    semester = session.scalar(select(M.Semester).where(M.Semester.name == SEMESTER_NAME))
+    assert semester is not None, "夹具应已由 seed_database 建好本学年"
+    assert session.scalar(select(func.count()).select_from(M.FitnessTestBatch)) == 0
+
+    calls = (
+        (dt.date(2025, 9, 8), dt.date(2025, 9, 8)),   # 首条：插入，用它自己的值
+        (dt.date(2025, 9, 1), dt.date(2025, 9, 1)),   # 更早 → 折叠下去
+        (dt.date(2025, 9, 5), dt.date(2025, 9, 1)),   # 更晚 → 不动（改回 PATCH 就是 09-05）
+        (dt.date(2025, 9, 1), dt.date(2025, 9, 1)),   # 重复 → 幂等
+    )
+    for given, want in calls:
+        batch = daily._fitness_batch(session, semester, "week1", given, "2025-2026")
+        session.flush()
+        session.expire_all()          # 强制从库里读回，不测内存里的残留值
+        assert batch.test_date == want, f"喂 {given.isoformat()} 后应为 {want.isoformat()}"
+
+    assert session.scalar(select(func.count()).select_from(M.FitnessTestBatch)) == 1, (
+        "幂等键 (semester_id, timepoint) 失效了：同一个 week1 批次被插出了第二行"
+    )
+
+
+@pytest.mark.parametrize("days_to_run", [
+    ("2025-09-15",),                    # 一次跑完整个窗口
+    ("2025-09-03", "2025-09-15"),       # 先跑到窗口中间，再跑完
+])
+def test_batch_test_date_is_the_earliest_tested_on_whatever_the_window(
+    session, seed_dir, days_to_run
+):
+    """生产形状下的同一条不变量：``test_date`` == 该批次全部成绩里**最早**的 ``tested_on``。
+
+    两个参数化用例是「一次跑完」与「分两次跑」；两边都必须得到 ``2025-09-01``。
+    期望值 ``2025-09-01`` 是 :data:`_SPREAD_DAYS` 里的最小值、**字面写死**，不从
+    ``FitnessTestResult`` 读回来跟自己比（那样两侧同源，硬规矩 #35）；右侧那个
+    ``func.min(...)`` 是**独立**用 SQL 从另一张表算出来的同一量，用来交叉核对。
+
+    改回「每条记录都 PATCH ``test_date``」之后两个用例都会得到 ``2025-09-05``
+    （CSV 行序轮转 5 天，第 60 行落在 ``_SPREAD_DAYS[59 % 5]`` = 最后一天），当场红。
+    """
+    _spread_week1_tested_on(seed_dir, _SPREAD_DAYS)
+    sem = semester_id(session)
+    for day in days_to_run:
+        assert run_daily(session, sem, day, MockLePaoAdapter(seed_dir)).status == "success"
+
+    batch = session.scalar(
+        select(M.FitnessTestBatch).where(
+            M.FitnessTestBatch.semester_id == sem,
+            M.FitnessTestBatch.timepoint == "week1",
+        )
+    )
+    assert batch is not None
+    assert batch.test_date == dt.date(2025, 9, 1), (
+        f"跑了 {days_to_run} 之后 test_date 漂到了 {batch.test_date.isoformat()}"
+    )
+    earliest = session.scalar(
+        select(func.min(M.FitnessTestResult.tested_on))
+        .where(M.FitnessTestResult.test_batch_id == batch.id)
+    )
+    assert earliest == dt.date(2025, 9, 1)
+    # 反空转：这个批次真的有跨多日的记录，否则「min == test_date」会退化成平凡真
+    distinct = session.execute(
+        select(M.FitnessTestResult.tested_on)
+        .where(M.FitnessTestResult.test_batch_id == batch.id)
+        .distinct()
+    ).scalars().all()
+    assert sorted(distinct) == [dt.date.fromisoformat(d) for d in _SPREAD_DAYS], distinct
+
+
+# ---------------------------------------------------------------------------
+# Plan 02 Task 1 Step 4 第 4 项：缺线组数走计数列，不再塞进 error_summary
+# ---------------------------------------------------------------------------
+
+def test_muscle_line_gaps_lands_in_its_own_count_column(session, seed_dir):
+    """``muscle_line_gaps`` 承载缺线组数，``error_summary`` 在成功运行下保持 ``NULL``。
+
+    ``4`` 是实测值（60 人 / ``seed=20250828`` / 业务日期 ``2025-09-15``，缺省注入）：
+    60 人摊到 4 个 (性别 × 年级组) 组，每组约 15 人 < ``MIN_SAMPLE = 30``，而肌肉量
+    **没有国标常模可降级**（Ruling 121 第 4 步），故四组全部不产出 P20 判定线。
+    字面写死在这里，不从被测列读回来（硬规矩 #35）。
+
+    ``error_summary is None`` 钉住 Plan02 Ruling 13 的「**直接切、不双写**」：谁把那段
+    「注意（非错误）：…」自由文本加回去，这一句当场红。切之前自己复验过零消费者
+    （``git grep -n "error_summary" -- backend/``：写入点只有 ``daily._record_failure``
+    与 ``run_daily`` 的 upsert 归零，读取点只有 ``main()`` 的 CLI 打印与两条断言真错误的
+    测试；``git grep -n "注意（非错误）" -- backend/`` 只有写入处一条）。
+    """
+    sem = semester_id(session)
+    run = run_daily(session, sem, D, MockLePaoAdapter(seed_dir))
+    assert run.status == "success"
+    assert run.muscle_line_gaps == 4
+    assert run.error_summary is None
+
+    # 反空转：判定线**确实**缺了，不是「本来就有 4 条线」被误数成 4 个缺口
+    assert session.scalar(
+        select(func.count()).select_from(M.PercentileSnapshot)
+        .where(M.PercentileSnapshot.item == "muscle_mass_kg")
+    ) == 0
+    # 六项计分项的判定线则照常物化（60 人 < 30 × 2 时也降级为国标常模，但**有**行）
+    assert session.scalar(
+        select(func.count()).select_from(M.PercentileSnapshot)
+    ) > 0
+
+    # 落到了库里，不只是内存对象上
+    session.expire_all()
+    got = session.get(M.DailySyncRun, run.id)
+    assert got.muscle_line_gaps == 4 and got.error_summary is None
diff --git a/backend/tests/pipeline/test_percentile_stage.py b/backend/tests/pipeline/test_percentile_stage.py
new file mode 100644
index 0000000..aa6e9ca
--- /dev/null
+++ b/backend/tests/pipeline/test_percentile_stage.py
@@ -0,0 +1,100 @@
+"""``cohort_from_db`` 按业务日期截断体测成绩（Plan 02 Task 1 Step 4 第 2 项）。
+
+本文件是 ``fitness_test_result.tested_on`` 那一列与 ``percentile_stage._results_of`` 的
+``tested_on <= as_of`` **唯一的守卫**。两条测试构成一对：同一条夹具、两个不同的 ``as_of``、
+两个不同的结果——这才是「截断由 ``as_of`` 驱动」的证据（硬规矩 #23：给观测归因时必须
+构造一个同样满足归因、但结果不同的场景）。
+
+夹具**手工建**、不经 ``app.seed``：缺省种子数据里一个批次只有一个采集日（实测见
+``tests/pipeline/test_daily.py::_spread_week1_tested_on`` 的 docstring），造不出
+「同一批次里既有 ``as_of`` 之前、又有 ``as_of`` 之后的记录」这个形状。
+"""
+import datetime as dt
+
+import pytest
+from sqlalchemy import create_engine
+
+from app.db import models as M
+from app.db.session import Session, init_db
+from app.pipeline.percentile_stage import cohort_from_db
+
+AS_OF = dt.date(2025, 9, 5)
+#: 三条成绩的测量日：一条在 ``AS_OF`` 之前、一条恰等于它（闭区间，须被包含）、
+#: 一条在**之后**（未来数据，须被截断掉）。
+TESTED_ON = (dt.date(2025, 9, 1), dt.date(2025, 9, 5), dt.date(2025, 9, 8))
+#: 逐条对应的「本批有没有成绩」期望值，字面写死（硬规矩 #35）
+VISIBLE_AT_AS_OF = (True, True, False)
+
+
+@pytest.fixture
+def session():
+    """一个学期、一个 ``week1`` 批次、三名学生各一条成绩，``tested_on`` 逐日递增。
+
+    ``fitness_test_batch.test_date`` 取三条里最早的那天（``min`` 折叠的不动点，见
+    ``daily._fitness_batch``），故 ``assessment_anchor`` 在 ``AS_OF`` 上一定选得到它——
+    截断发生在**成绩行**这一层，不在批次这一层。
+    """
+    eng = create_engine("sqlite:///:memory:")
+    init_db(eng)
+    with Session(eng) as s:
+        sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
+                         end_date=dt.date(2026, 1, 20), weeks=16, is_current=True)
+        s.add(sem)
+        s.flush()
+        batch = M.FitnessTestBatch(semester_id=sem.id, timepoint="week1",
+                                   test_date=min(TESTED_ON))
+        s.add(batch)
+        s.flush()
+        for i, day in enumerate(TESTED_ON, start=1):
+            stu = M.Student(student_no=f"202500100{i}", name=f"学生{i}", sex="male",
+                            birth=dt.date(2006, 3, 4), grade=1)
+            s.add(stu)
+            s.flush()
+            s.add(M.FitnessTestResult(
+                test_batch_id=batch.id, student_id=stu.id, tested_on=day,
+                height_cm=172.5, weight_kg=65.0, total_score=70,
+            ))
+        s.commit()
+        yield s
+
+
+def test_cohort_truncates_results_by_tested_on(session):
+    """``as_of = 2025-09-05`` 只看得见 ``tested_on <= 09-05`` 的两条成绩。
+
+    第三人那条 ``tested_on = 2025-09-08`` 的记录**在库里**、也属于被选中的那个批次，
+    但它测量于 ``as_of`` **之后**——用它就是在拿未来的数据算过去的分层。改前
+    ``_results_of`` 只按 ``test_batch_id`` 过滤，那一行会被读回来；终审实测 60 人里
+    **12 人 label 不同**。
+
+    被截断的那个人不是「消失」，而是退化成「本批没有成绩」这个**合法状态**：
+    ``curr_scores`` 七项全 ``None``（``empty_scores()``）→ ``valid_count = 0`` → Z0 闸门
+    → ``insufficient_data``（Ruling 106）。他仍然在 ``derived_metrics`` 与
+    ``stratification_result`` 里各留一行，故 spec §4.6「运维记录能数出本日没分层的人」
+    不失守。
+    """
+    persons, anchor = cohort_from_db(session, AS_OF)
+    assert anchor.curr_batch_id is not None, "批次 test_date <= as_of，锚点必须选得到它"
+    assert len(persons) == 3, "遍历的是 student 表的每一个人，不是「本批抽到记录的人」"
+
+    # persons 按 Student.id 升序，与 TESTED_ON 的插入序一一对应
+    assert tuple(p.curr_total is not None for p in persons) == VISIBLE_AT_AS_OF
+
+    hidden = persons[2]
+    assert len(hidden.curr_scores) == 7, "键必须齐全，derive 的 _require_seven_keys 会查"
+    assert all(value is None for value in hidden.curr_scores.values())
+    assert hidden.curr_total is None
+
+    # 边界是**闭**的：恰等于 as_of 的那条属于「当天已经测过」，必须看得见
+    assert persons[1].curr_total == 70
+
+
+def test_the_same_cohort_sees_every_result_once_as_of_moves_past(session):
+    """同一条夹具、``as_of = 2025-09-30`` → 三条全部可见。
+
+    这一条是上一条的**反证场景**：若两条都通过，就说明「第三人不可见」确实是 ``as_of``
+    截断造成的，而不是那条记录本身有什么问题（比如学号解析不到、外键没对上）。
+    """
+    persons, anchor = cohort_from_db(session, dt.date(2025, 9, 30))
+    assert anchor.curr_batch_id is not None
+    assert tuple(p.curr_total is not None for p in persons) == (True, True, True)
+    assert [p.curr_total for p in persons] == [70, 70, 70]
diff --git a/backend/tests/seed/test_fitness.py b/backend/tests/seed/test_fitness.py
index e56cf16..71f68c0 100644
--- a/backend/tests/seed/test_fitness.py
+++ b/backend/tests/seed/test_fitness.py
@@ -13,33 +13,33 @@ Ruling 54（档内抖动 + 表下溢出，含修正 Ruling 57/58）。
 """
 import re
 from collections import Counter
 from dataclasses import fields
 
 import numpy as np
 import pytest
 
 from app.domain.indicators import (
     AGE_GROUPS,
+    COLUMN_BY_ITEM,
     WEAKNESS_ITEMS,
     ScoredItem,
     Sex,
     age_group_of,
     raw_from_score,
     score_item,
     segment_thresholds,
 )
 from app.refdata import standard
 from app.seed import fitness
 from app.seed.config import SEMESTERS, SeedConfig, current_semester
 from app.seed.fitness import (
-    COLUMN_BY_ITEM,
     MEASURE_DECIMALS,
     jitter_raw,
     latent_profiles,
     make_fitness_tests,
     sub_floor_marks,
 )
 from app.seed.generate import build_dataset
 from app.seed.population import make_population
 from app.seed.sections import make_sections
 

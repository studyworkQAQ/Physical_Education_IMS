"""``app.demo_data`` 的守卫：幂等、不碰时钟、以及「它不是 ``seed_database`` 的一段」。

四条测试各守一件事，缺一条就有一档失效是静默的：

* :func:`test_build_demo_feedback_is_idempotent` —— 跑两次行数逐字不变，且**四个计数
  都不是 0**（否则「不变」只是「两次都没写」）；
* :func:`test_demo_feedback_gives_the_alert_engine_something_to_fire_on` —— 造出来的数据
  里真的有 Task 7 那五条规则够得着的样本（连续 ≥ 3 次 RPE ≥ 9、迟交、休息日、未完成、
  ≥ 3 个小测周次）。少了它，「演示库有 480 行小测」与「演示库能让预警跑起来」是两件事，
  而本模块存在的理由只有后者；
* :func:`test_demo_data_never_touches_the_clock` —— 源码级守卫 + 一条**自证**
  （假模块里放三种违规写法，断言守卫报警）；
* :func:`test_seed_database_still_writes_no_feedback_rows` —— 分区决定的守卫：
  ``seed_database`` 之后 Plan 03 那 7 张表**全 0 行**。

⚠️ **本文件的夹具一律用内存库**，且**从不**让 ``PE_DB_URL`` 落到缺省：
``app.config.DEFAULT_DB_URL`` 逐字指向 ``backend/pe.db``，那是禁区。
"""
import ast
import datetime as dt
import pathlib

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app import demo_data
from app.db import models
from app.db.models.feedback import (
    Alert,
    ClassSession,
    MiniTest,
    Notification,
    RpeRecord,
    TrainingLog,
    WeeklyClassReport,
)
from app.db.session import init_db
from app.demo_data import DemoReport, build_demo_feedback
from app.seed.config import SeedConfig
from app.seed.generate import seed_database

# ⚠️ 三份「被禁写法」的词表**不在本文件抄第二份**：它们的唯一所有者是
# ``tests/seed/test_generate.py``（Plan 01 为 ``app/seed`` 立的那套源码级守卫）。
# 从那里 import 会让 pytest 之外多出一个 ``tests.seed.test_generate`` 模块实例
# （pytest 自己按 rootdir 把它导入成顶层的 ``test_generate``），代价是那份模块级
# 常量被求值两遍——全是 ``frozenset`` / ``SeedConfig`` 一类的无副作用字面量，可接受；
# 抄第二份的代价则是「两边一起放宽也全绿」，那正是硬规矩 #35 要防的形状。
# ⚠️ **不复用它的 ``_offenders_in``**：那一份把「``default_rng`` 只允许出现在
# ``generate.py``」写死了（``app/seed`` 全项目只有一个带种子的随机数入口），
# 而 ``app/demo_data.py`` 不在 ``app/seed`` 下、**必须**有自己的带种子根生成器
# （它的签名 ``build_demo_feedback(session, *, cfg, as_of)`` 里没有 rng 参数）。
# 故本文件只借词表，判据自己写、并自带一条自证。
from tests.seed.test_generate import CLOCK_METHODS, RNG_GLOBAL_FUNCS, RNG_SOURCES

#: 与 ``tests/seed/test_generate.py`` 的 ``SMALL`` 同规模（120 人是能同时满足
#: 「每班 30–38 人」的最小可编班规模）：够小以致整套测试仍在秒级，
#: 而 4 个行政班 × 4 周课次已经能把幂等与「预警够得着」两件事都跑出来。
CFG = SeedConfig(students=120, weeks=16, seed=20250828)

#: 2025-09-01 开学的第 10 周（星期三）。⚠️ 刻意挑在周中而不是学期头几天：
#: ``as_of`` 太靠近 ``start_date`` 时，往前推的课次/打卡/小测周会全部落在开学日之前
#: 而被跳过，四个计数于是全是 0，幂等那条断言会**恒真**。
AS_OF = dt.date(2025, 11, 5)

#: Plan 03 Task 2 的 7 张表。⚠️ 这份清单在本文件里是**断言的期望侧**，
#: 故逐字写死；被测侧从 ``Base.metadata`` 现取（两侧不同源，硬规矩 #35）。
PLAN03_TABLES = (
    "class_session", "rpe_record", "training_log", "mini_test",
    "alert", "notification", "weekly_class_report",
)

DEMO_FILE = pathlib.Path(demo_data.__file__)


@pytest.fixture()
def engine():
    """建好 25 张表的内存引擎。``sqlite://`` 在 SQLAlchemy 上走 SingletonThreadPool，
    故 ``init_db`` 用的连接与下面 ``Session`` 拿到的是同一条（同一个库）。"""
    eng = create_engine("sqlite://")
    init_db(eng)
    return eng


@pytest.fixture()
def seeded(engine):
    """已经 ``seed_database`` 过（组织结构齐了）的引擎——``build_demo_feedback`` 的前提。"""
    with Session(engine) as session:
        seed_database(session, CFG)
        session.commit()
    return engine


# ---------------------------------------------------------------------------
# 幂等
# ---------------------------------------------------------------------------


def test_build_demo_feedback_is_idempotent(seeded):
    """跑两次，四张表的行数与批次号**逐字不变**。

    ``DemoReport`` 的四个计数是**从库里数出来的**（``select(func.count())``），
    不是「本函数打算写几行」的自报——这一点是承重的：自报的计数会让本条断言恒真
    （第二次调用时它写 0 行，若报的是「写了 0 行」，那与第一次的报数根本不可比；
    若报的是「打算写 N 行」，两次都报 N，同样恒真）。数库里的行才把「没有翻倍」
    变成可判的命题。

    ⚠️ 幂等的机制是 :func:`app.db.repo.upsert` 按四张表各自的唯一约束写，
    而不是「先删后插」：``rpe_record`` 与 ``mini_test`` 是**用户实时写入**的表
    （刻意不带 ``batch_id``），演示生成器没有资格删掉它们。
    ⚠️ 而 ``upsert`` 是「先 select 再 update/insert」，故 ``class_session`` 那条
    ``UniqueConstraint`` 是它唯一的 DB 层兜底（顶回 #1）：少了它，两个写入方
    会各插一行，第三次调用的 select 撞上 ``MultipleResultsFound``。
    """
    with Session(seeded) as session:
        first = build_demo_feedback(session, cfg=CFG, as_of=AS_OF)
        session.commit()

    # 反空转：四个计数一个都不是 0，否则「两次相同」只是「两次都没写」
    assert isinstance(first, DemoReport)
    assert first.class_sessions == 16, first     # 4 个行政班 × DEMO_SESSION_WEEKS(4)
    assert first.rpe_records == 480, first       # 120 人 × 4 节课（每人只在自己那个班）
    assert first.training_logs == 1680, first    # 120 人 × DEMO_CHECKIN_DAYS(14)
    assert first.mini_tests == 480, first        # 120 人 × 4 个偶数周（4/6/8/10）
    assert first.batch_id >= 1

    with Session(seeded) as session:
        second = build_demo_feedback(session, cfg=CFG, as_of=AS_OF)
        session.commit()
    assert second == first, f"第二次调用改变了行数：{first} → {second}"

    # 第三次也一样，且库里数出来的行数与报告一致（报告不是自己算给自己看的）
    with Session(seeded) as session:
        third = build_demo_feedback(session, cfg=CFG, as_of=AS_OF)
        session.commit()
        assert third == first
        for model, expected in (
            (ClassSession, first.class_sessions),
            (RpeRecord, first.rpe_records),
            (TrainingLog, first.training_logs),
            (MiniTest, first.mini_tests),
        ):
            assert session.scalar(select(func.count()).select_from(model)) == expected


# ---------------------------------------------------------------------------
# 造出来的数据要让 Task 7 的规则够得着
# ---------------------------------------------------------------------------


def test_demo_feedback_gives_the_alert_engine_something_to_fire_on(seeded):
    """演示数据的**用途**是喂 Task 7 的五条规则，故它必须真的喂得进去。

    本模块的 docstring 逐字声明了「刻意不造 ``alert`` / ``notification`` /
    ``weekly_class_report``」——那三张表是引擎的**产物**，伪造它们会让
    「预警 → 减量 20% → 学生端看到更新后的训练单」这条闭环的验收变成假象。
    于是「演示库有没有东西可显示」这件事，全押在四张输入表**造得对不对**上，
    而「行数 > 0」证明不了这一点：480 行全是 RPE = 5 的小测，
    ``RED_RPE_SUSTAINED`` 与 ``RED_MINITEST_DROP`` 一样都触发不了。

    五条断言各对应 spec §8.2 的一条规则要用的原料（``GREEN_MASTERY`` 要的
    「本周完成度 100%」由 ``completed=True`` 的行提供，已在第 4 条里）。
    ⚠️ 阈值一律写**字面量**（9 / 3 / 2），不读 ``demo_data.HIGH_RPE_FLOOR``
    一类的常量：那一侧是被测模块，读它就是把断言的两端接到同一个源上（硬规矩 #35）。
    字面量的出处是 spec §8.2（``RED_RPE_SUSTAINED`` = RPE 连续 ≥ 9、
    补齐口径 #1 = 连续 3 次、补齐口径 #2 = 3 个数据点、补齐口径 #3 = 连续 2 个训练日）。
    """
    with Session(seeded) as session:
        build_demo_feedback(session, cfg=CFG, as_of=AS_OF)
        session.commit()

    with Session(seeded) as session:
        # ① RED_RPE_SUSTAINED：至少一个学生有 ≥ 3 次 RPE ≥ 9
        per_student = session.execute(
            select(RpeRecord.student_id, func.count())
            .where(RpeRecord.rpe >= 9)
            .group_by(RpeRecord.student_id)
        ).all()
        assert per_student, "演示库里一个 RPE ≥ 9 的样本都没有：红色规则永远触发不了"
        assert max(count for _sid, count in per_student) >= 3, per_student[:5]

        # ② RED_MINITEST_DROP：≥ 3 个不同的小测周次（判「连续两次下降」要 3 个点）
        weeks = sorted(set(session.scalars(select(MiniTest.week)).all()))
        assert len(weeks) >= 3, weeks
        assert all(week % 2 == 0 for week in weeks), f"小测只在偶数周：{weeks}"

        # ③ YELLOW_CHECKIN_GAP：既有「未完成」也有「休息日」，两者都必须出现
        #    （休息日不计入中断，故这两档在库里必须可区分）
        assert session.scalar(
            select(func.count()).select_from(TrainingLog)
            .where(TrainingLog.completed.is_(False))
        ) > 0
        assert session.scalar(
            select(func.count()).select_from(TrainingLog)
            .where(TrainingLog.is_rest_day.is_(True))
        ) > 0

        # ④ GREEN_MASTERY / spec §8.1 的「22:00 后提交」：完成与迟交两档都要有，
        #    且**存在 completed=True 且 late=True 的那一档**（练了但交得晚，
        #    不计入当日完成）——把两列合成一个三态枚举就造不出这一档
        assert session.scalar(
            select(func.count()).select_from(TrainingLog)
            .where(TrainingLog.completed.is_(True))
        ) > 0
        assert session.scalar(
            select(func.count()).select_from(TrainingLog)
            .where(TrainingLog.late.is_(True), TrainingLog.completed.is_(True))
        ) > 0

        # ⑤ 造出来的 RPE 全部落在值域里：不是靠 CHECK 拦下来的（拦下来会当场
        #    IntegrityError、整批回滚），而是本来就合法
        rpes = session.scalars(select(RpeRecord.rpe)).all()
        assert rpes and all(0 <= value <= 10 for value in rpes)
        # ⑥ 演示数据自己标得出来源：``training_log.source`` 一律是 "demo"
        sources = set(session.scalars(select(TrainingLog.source)).all())
        assert sources == {"demo"}, sources


# ---------------------------------------------------------------------------
# 不碰时钟（源码级守卫 + 自证）
# ---------------------------------------------------------------------------


def _demo_offenders(source: str, filename: str) -> list[str]:
    """一段源码里全部「读时钟 / 第二个随机源」的违规点。

    抽成函数是为了让它**可被自证测试打**：把违规源码写进 ``tmp_path`` 下的假模块，
    再断言本函数对它返回违规——否则「守卫存在」与「守卫有效」是两件没人分得清的事
    （``tests/seed/test_generate.py`` 为同一件事配了 40 多条自证用例）。

    判据与那一份**同源不同形**：词表（:data:`CLOCK_METHODS` / :data:`RNG_SOURCES` /
    :data:`RNG_GLOBAL_FUNCS`）从那里 import，形状按本模块的实际改一处——
    ``default_rng`` 在 ``app/demo_data.py`` 里是**合法**的，但必须**带种子**。
    """
    tree = ast.parse(source)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root == "random":
                    offenders.append(f"{filename}:{alias.name}")
                if root == "time":
                    offenders.append(f"{filename}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[0] in ("random", "time"):
                offenders.append(f"{filename}:from {module}")
            elif module == "numpy.random":
                offenders += [
                    f"{filename}:from {module} import {alias.name}"
                    for alias in node.names
                    if alias.name in RNG_GLOBAL_FUNCS
                ]
        elif isinstance(node, ast.Call):
            text = ast.unparse(node.func)
            head = text.rsplit(".", 1)[-1]
            if head in CLOCK_METHODS:
                offenders.append(f"{filename}:{node.lineno}:clock:{text}")
            if head == "default_rng" and not node.args:
                offenders.append(f"{filename}:{node.lineno}:unseeded:{text}")
            if head in RNG_SOURCES:
                offenders.append(f"{filename}:{node.lineno}:rng-source:{text}")
            parts = text.split(".")
            if (
                head in RNG_GLOBAL_FUNCS
                and len(parts) >= 3
                and parts[-2] == "random"
                and parts[-3] in ("np", "numpy")
            ):
                offenders.append(f"{filename}:{node.lineno}:global-rng:{text}")
    return offenders


def test_demo_data_never_touches_the_clock(tmp_path):
    """``app/demo_data.py`` 一次都不读时钟、也不自建无种子的随机源。

    时钟那一半是 Global Constraint #1（时间与随机数一律由调用方注入）：
    本模块的时间来源只有 ``as_of`` 与 ``semester.start_date``，全部日期都由它们减出来。
    失效形态是**静默**的——读了 ``date.today()`` 之后，同一个 ``cfg.seed`` 在不同日期
    产出不同的行，「跑两次行数不变」仍然成立（同一天内跑两次），
    而「同种子字节级一致」已经不成立了。故用源码级检查，不用运行时断言。

    随机数那一半：本模块**有**自己的根生成器（``np.random.default_rng(cfg.seed)``），
    那是合法的——``app/seed`` 那条「全项目只有一个 ``default_rng``」的纪律管的是
    ``app/seed`` 目录，而本模块不在里面。要守的是「**必须带种子**」：
    无种子的 ``default_rng()`` 由 OS 熵播种，同种子同输出当场失效。
    """
    assert DEMO_FILE.is_file(), f"守卫将空转全绿：{DEMO_FILE}"
    source = DEMO_FILE.read_text(encoding="utf-8")
    assert _demo_offenders(source, DEMO_FILE.name) == []

    # 反空转：as_of 真的被用上了（否则「不读时钟」只是因为它压根不需要日期）
    assert "as_of" in source
    assert "build_demo_feedback" in source

    # ---- 自证：三种被禁写法各一条，守卫必须报警 -------------------------
    fake = tmp_path / "fake_demo.py"

    fake.write_text(
        "import datetime as dt\n"
        "def when():\n"
        "    return dt.date.today()\n",
        encoding="utf-8",
    )
    offenders = _demo_offenders(fake.read_text(encoding="utf-8"), fake.name)
    assert any("clock:dt.date.today" in item for item in offenders), offenders

    fake.write_text(
        "import datetime as dt\n"
        "def when():\n"
        "    return dt.datetime.now()\n",
        encoding="utf-8",
    )
    offenders = _demo_offenders(fake.read_text(encoding="utf-8"), fake.name)
    assert any("clock:dt.datetime.now" in item for item in offenders), offenders

    fake.write_text(
        "import numpy as np\n"
        "rng = np.random.default_rng()\n",
        encoding="utf-8",
    )
    offenders = _demo_offenders(fake.read_text(encoding="utf-8"), fake.name)
    assert any("unseeded" in item for item in offenders), offenders

    fake.write_text(
        "import time\n"
        "import numpy as np\n"
        "np.random.seed(0)\n"
        "x = np.random.normal(0.0, 1.0, 3)\n"
        "t = time.time()\n",
        encoding="utf-8",
    )
    offenders = _demo_offenders(fake.read_text(encoding="utf-8"), fake.name)
    assert any(item.endswith(":import time") or item.endswith(":time") for item in offenders)
    assert any("rng-source" in item for item in offenders), offenders
    assert any("global-rng:np.random.normal" in item for item in offenders), offenders
    assert any("clock:time.time" in item for item in offenders), offenders

    # ---- 负对照：本模块真正的写法必须放行 -------------------------------
    fake.write_text(
        "import datetime as dt\n"
        "import numpy as np\n"
        "\n"
        "def build(cfg, as_of):\n"
        "    rng = np.random.default_rng(cfg.seed)\n"
        "    day = as_of - dt.timedelta(days=1)\n"
        "    return dt.datetime(day.year, day.month, day.day, 10, 30), "
        "float(rng.uniform(1.0, 2.0))\n",
        encoding="utf-8",
    )
    assert _demo_offenders(fake.read_text(encoding="utf-8"), fake.name) == [], (
        "守卫把「带种子的 default_rng + dt.timedelta + dt.datetime 构造器 + rng.uniform」"
        "这些合法写法判成了违规——一个把全部合法代码判成违规的守卫，"
        "与一个什么都不判的守卫同样无用"
    )


# ---------------------------------------------------------------------------
# 分区决定：演示数据不得由 seed_database 产出
# ---------------------------------------------------------------------------


def test_seed_database_still_writes_no_feedback_rows():
    """``seed_database`` 之后，Plan 03 那 7 张表**全 0 行**。

    这条守的是本 Task 的分区决定，而不是 ``demo_data`` 的行为：7 张新表全归
    ``tests/seed/test_generate.py`` 的 ``DATA_TABLES``（11 → 18），而那个文件有一条
    ``for table in DATA_TABLES + REFERENCE_TABLES: assert count == 0``。
    于是「演示数据由 ``seed_database`` 灌」这条路在分区那一刻就被堵死了——
    本条把那件事**点名**说出来，免得下一个人只看到「0 行」而看不到「为什么必须是 0 行」，
    进而以为把 ``build_demo_feedback`` 接进 ``seed_database`` 只是一个方便的改法。

    ⚠️ 这与 Plan 02 的 P2-A1 / P3-A1 是同一条纪律（``sync_exercises`` /
    ``sync_templates`` 不许接进 ``seed_database``），另一条理由是 Global Constraint #10：
    ``app/seed/`` 自 Plan 01 结案后重新冻结。

    ⚠️ 本条**自带反空转**：同一个库上组织结构必须已经写进去了（120 个学生），
    否则「7 张表 0 行」只是「什么都没建」的另一种说法。
    """
    eng = create_engine("sqlite://")
    init_db(eng)
    with Session(eng) as session:
        seed_database(session, CFG)
        session.commit()

    with Session(eng) as session:
        offenders = []
        for table in PLAN03_TABLES:
            count = session.scalar(
                select(func.count()).select_from(models.Base.metadata.tables[table])
            )
            if count != 0:
                offenders.append(f"{table}={count}")
        assert offenders == [], (
            f"seed_database 写了反馈/预警表：{offenders}。演示数据的入口是 "
            "app.demo_data.build_demo_feedback，不是 seed_database（分区决定的理由见 "
            "tests/seed/test_generate.py 的 DATA_TABLES 注释）"
        )
        # 反空转：组织结构真的建起来了
        assert session.scalar(select(func.count()).select_from(models.Student)) == CFG.students
        assert session.scalar(select(func.count()).select_from(models.CourseSection)) == 4 + 3

    # 同一份库上再跑演示生成器，那 7 张里的**4 张**才会有行；另外 3 张
    # （alert / notification / weekly_class_report）永远是引擎的产物，本模块一行都不写
    with Session(eng) as session:
        build_demo_feedback(session, cfg=CFG, as_of=AS_OF)
        session.commit()
    with Session(eng) as session:
        for table in ("class_session", "rpe_record", "training_log", "mini_test"):
            assert session.scalar(
                select(func.count()).select_from(models.Base.metadata.tables[table])
            ) > 0, table
        for model in (Alert, Notification, WeeklyClassReport):
            assert session.scalar(select(func.count()).select_from(model)) == 0, (
                f"{model.__tablename__} 是 Task 7/8/9 引擎的产物，演示数据不得伪造它"
            )

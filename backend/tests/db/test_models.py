# backend/tests/db/test_models.py
import datetime as dt
import re
import types
import pytest
from sqlalchemy import JSON as BuiltinJson, create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from app.db.session import Base, init_db, Session
from app.db import models as M
# Ruling 97：Plan 02 的新表**不进** ``models`` 的公有导入面，故按子模块引用
# ⚠️ Plan 03 Task 2 的 7 张新表同理，而且它们**全部**住在 ``feedback.py``——包括
# spec §4.6 的 ``alert`` / ``notification`` 与 §4.7 的 ``weekly_class_report``。
# 不放进 ``ops.py`` 的理由（``__init__.py`` 对 ``ops`` 是星号导入、对 ``feedback`` 不是）
# 逐字写在 ``app/db/models/feedback.py`` 的模块 docstring 里，别按 spec 的章节标题搬回去。
from app.db.models.feedback import (
    Alert,
    ClassSession,
    MiniTest,
    Notification,
    RpeRecord,
    TrainingLog,
    WeeklyClassReport,
)
from app.db.models.prescription import (
    Prescription,
    PrescriptionTemplate,
    WeeklyAdjustment,
)
from app.db.repo import delete_by_batch
from app.domain.derive import Trend
from app.domain.indicators import AGE_GROUPS, CLEANING_FIELDS, Sex
from app.domain.percentile import (
    PercentileRow, SnapshotMetric, summarize_source,
)
from app.domain.stratify import RULE_ORDER, RuleId

@pytest.fixture
def session():
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    with Session(eng) as s:
        yield s

def test_all_twenty_five_tables_created(session):
    expected = {"semester","teacher","student","course_section","enrollment",
        "fitness_test_batch","fitness_test_result","body_composition",
        "interest_survey","percentile_snapshot","derived_metrics",
        "stratification_result","daily_sync_run","cleaning_log","exercise",
        "prescription_template","prescription","weekly_adjustment",
        # Plan 03 Task 2 的 7 张：反馈三源（spec §4.5）4 张 + 预警/通知（§4.6）2 张
        # + 班级周报（§4.7）1 张。⚠️ **后三张也住在 ``models/feedback.py``**，不在
        # ``ops.py``——``__init__.py`` 对 ``ops`` 是星号导入、对 ``feedback`` 不是，
        # 放进去会让三个类名自动进入包的公有命名空间、当场撞红下面那条基线守卫
        # （P3-A1，理由逐字写在 ``feedback.py`` 的模块 docstring 里）。
        "class_session","rpe_record","training_log","mini_test",
        "alert","notification","weekly_class_report"}
    # Ruling 28：用 == 而不是 >=。「本批只建这些」是真实的范围边界，>= 抓不到
    # 有人提前把后续计划的表建进来——那种提前建表会逼出一次本该不存在的迁移，
    # 而超集断言对它完全无感。
    # ⚠️ **表数逐 Task 递增**：Plan 01 结案是 14 张，Plan 02 Task 2 加 ``exercise`` → 15；
    # Task 3 加 ``prescription_template`` → 16；Task 6 加 ``prescription`` +
    # ``weekly_adjustment`` → 18；**Plan 03 Task 2 一次加 7 张 → 25（本条现值）**。
    # 再加表时同一套同步动作要重跑一遍：① 函数名里的英文数词；② 本文件里那三处
    # ``==`` 断言——**按可 grep 的原文找，不要按裸行号找**：``git grep -n "== 25" --
    # backend/tests/db/test_models.py`` 现命中 **7** 处 = **3** 处真断言（两处 ``assert
    # len(tables) == 25, "守卫的覆盖面必须先被确认是这 25 张表"`` 与一处 ``assert
    # len(Base.metadata.tables) == 25``）+ **4** 处本段的散文（这条 grep 命令自己、
    # 紧随其后逐字引出的那两条断言原文，以及下面第 ④ 格提到 ``tests/test_main.py``
    # 那两处的地方）。⚠️ **散文计数比 Plan 02 时多了一处**，就是第 ④ 格新加的那半句
    # ——这正是硬规矩 #66 要的形状：加一处引用就要把计数一起改。
    # **改完表数请重跑这条 grep、按命中数逐个
    # 更新，并连带更新 ``app/db/models/prescription.py`` 里同一处计数**（硬规矩 #66）。
    # ⚠️ 此前这里印的是**三个裸行号**，它们是 ``fb5bddb`` 上 ``== 14`` 的位置，Task 2 改成
    # ``== 15`` 时那三处就已推移（Task 2 fix round 3 更正；与 fr2 的 CE-7 同一个失效形态；
    # 那三个过期行号**不再复述**）。⚠️ **Task 3 又踩了一次同一个坑**：控制者派单的自查清单里
    # 印的是 ``966eae0`` 上的 ``:169`` / ``:236`` / ``:494``，而在代码基线 ``c29bc69`` 上实测
    # 已是 ``:176`` / ``:243`` / ``:501``（取证：``t3_probes/p01_verify_baseline.py``）——
    # 即「复用历史输出里的行号等同手写」，硬规矩 #61 的扩写。故本段**一个行号都不写**。
    # ③ ``app/db/models/prescription.py`` 模块 docstring 里那张「表 → 归属 Task」的表；
    # ④ ``tests/seed/test_generate.py`` 的分区清单（Plan 03 Task 2 起是
    # ``DATA_TABLES`` **18** 张 + ``REFERENCE_TABLES`` 2 张 + ``ORGANISATION_TABLES`` 5 张；
    # ``REFERENCE_TABLES`` 是**两处**：定义与 ``assert REFERENCE_TABLES == (…)``，
    # Plan02 账本 P3-A6 第 4 项）与 ``tests/test_main.py`` 的 ``tables == 25``（两处）；
    # ⑤ **本文件里另外两处按表数/列数写死的断言**（Task 6 实测发现，派单的 Step 0 清单
    # 漏了这两格）：``test_no_column_uses_builtin_sqlalchemy_json`` 的
    # ``assert len(json_text_columns) == 21``（Plan 03 Task 2 的 7 张新表带来 7 个
    # ``JsonText`` 列）与 :data:`_BATCH_OWNED_TABLES`（7 张新表里有 4 张带 ``batch_id``，而
    # ``test_only_batch_owned_tables_expose_batch_id`` 按**集合相等**判「谁有 batch_id」）；
    # ⑥ **两处散文里的外键总数与 ``_in_domain`` 列数**（Plan 03 Task 2 实测发现，派单的
    # 预检清单也没列）：``test_sqlite_foreign_keys_are_enforced`` docstring 里的
    # 「**41** 个外键」与 ``test_string_column_widths_fit_their_value_domains`` docstring
    # 里的「今天 **23** 列」。两者都用运行时口径复算过（``t2_probes/p02_baseline.py``）。
    assert set(inspect(session.get_bind()).get_table_names()) == expected

def test_daily_sync_run_business_date_is_unique(session):
    sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025,9,1),
                     end_date=dt.date(2026,1,20), weeks=16, is_current=True)
    session.add(sem); session.flush()
    d = dt.date(2025, 9, 15)
    session.add(M.DailySyncRun(semester_id=sem.id, business_date=d, status="success"))
    session.flush()
    session.add(M.DailySyncRun(semester_id=sem.id, business_date=d, status="success"))
    with pytest.raises(IntegrityError):
        session.flush()

def test_stratification_label_domain(session):
    assert M.StratificationResult.LABELS == {
        "red", "yellow", "green", "insufficient_data"}

def test_grouping_mode_domain(session):
    assert M.CourseSection.GROUPING_MODES == {"administrative", "stratified"}

def test_timepoint_domain(session):
    assert M.FitnessTestBatch.TIMEPOINTS == {"week1", "week8", "week16"}


# ---------------------------------------------------------------------------
# Ruling 27：SQLite 的外键强制
# ---------------------------------------------------------------------------

def test_sqlite_foreign_keys_are_enforced(session):
    """SQLite 每条连接默认 ``foreign_keys=OFF``，钩子必须真的把它打开。

    会话按测试一贯的方式产生（``create_engine`` + ``init_db``），因此这条断言验的
    正是注册在 ``Engine`` **类**上的那个钩子——挂在 ``engine()`` 返回值上的话，这条
    路径一个也覆盖不到，PRAGMA 会照旧读回 0，而 schema 里 41 个外键全是装饰。
    （41 = Plan 01 的 20 + Plan 02 Task 6 的 4（``prescription`` 的 ``student_id`` /
    ``batch_id`` 与 ``weekly_adjustment`` 的 ``prescription_id`` / ``batch_id``）
    + Plan 03 Task 2 的 17（``class_session`` 2、``rpe_record`` 2、``training_log`` 2、
    ``mini_test`` 2、``alert`` 4、``notification`` 2、``weekly_class_report`` 3）。
    取法：``sum(len(c.foreign_keys) for t in Base.metadata.tables.values()
    for c in t.columns)``，Task 6 与 Plan 03 Task 2 各亲跑一次
    （``t2_probes/p02_baseline.py``）。）
    """
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_orphan_batch_id_is_rejected(session):
    """``derived_metrics.batch_id`` 是 Task 10 幂等重放的唯一依据，必须真有兜底。

    外键不强制时，``delete_by_batch`` 漏删留下的孤儿派生行永远不会报错，只会静默
    抬高红黄绿分布。这条测试就是那个兜底的回归：批号在 ``daily_sync_run`` 里查无
    此行时，插入必须被数据库自己拒收。
    """
    stu = M.Student(student_no="2025001001", name="张三", sex="male",
                    birth=dt.date(2006, 3, 4), grade=1)
    session.add(stu); session.flush()
    session.add(M.DerivedMetrics(student_id=stu.id, computed_on=dt.date(2025, 9, 15),
                                 batch_id=999_999, annual_change={}, trend="stable",
                                 weaknesses=[], weakness_count=0, valid_count=6,
                                 body_comp_abnormal=False, body_comp_reasons=[]))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "FOREIGN KEY constraint failed" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Ruling 30：DailySyncRun.status 的默认值
# ---------------------------------------------------------------------------

def test_daily_sync_run_status_defaults_to_failed(session):
    """运行记录常在跑完之前就入库，此时 status 必须落到保守的那一侧。

    默认取 ``"failed"``：进程崩在中途，这一行留下的就是 failed——崩溃被记成失败
    只是难看，被记成成功则是谎报一次并没有发生的完整运行，而下游看 status 决定要
    不要重跑，谎报成功会让这一天永远不再重跑。
    """
    column = M.DailySyncRun.__table__.columns["status"]
    assert column.nullable is False, "本列不许为空，故必须有默认值"
    assert column.default.arg == "failed"

    sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
                     end_date=dt.date(2026, 1, 20), weeks=16, is_current=True)
    session.add(sem); session.flush()
    # 只给必需的三样： semester_id / business_date，status 一律不传
    run = M.DailySyncRun(semester_id=sem.id, business_date=dt.date(2025, 9, 15))
    session.add(run); session.flush()
    run_id = run.id
    session.expire_all()

    assert session.get(M.DailySyncRun, run_id).status == "failed", "落库后须读回 failed"
    # 显式给出时仍以显式值为准，默认值不得覆盖真实结局
    other = M.DailySyncRun(semester_id=sem.id, business_date=dt.date(2025, 9, 16),
                           status="success")
    session.add(other); session.flush(); other_id = other.id
    session.expire_all()
    assert session.get(M.DailySyncRun, other_id).status == "success"


# ---------------------------------------------------------------------------
# Student.SEXES ↔ domain.indicators.Sex 的一致性
# ---------------------------------------------------------------------------

def test_student_sexes_match_domain_sex_enum(session):
    """两处字面量此前只是「碰巧相同」，没有任何东西钉住它。

    db 层没有 import ``Sex``（Task 3 的接口约定是「Consumes: 无」，且纯度约束管的是
    ``app/domain/`` 自己的导入，不管谁 import 它），代价就是漂移只能靠这条测试抓：
    一旦 ``Sex`` 多出一个值而 ``Student.SEXES`` 没跟上，db 会拒收 domain 的合法值。
    """
    assert {s.value for s in Sex} == M.Student.SEXES

    # percentile_snapshot.sex 复用同一常量，故顺带钉住 DDL 里的取值域也一致
    checks = {c.name: str(c.sqltext) for c in M.PercentileSnapshot.__table__.constraints
              if type(c).__name__ == "CheckConstraint"}
    assert checks["ck_percentile_snapshot_sex"] == "sex IN ('female', 'male')"


# ---------------------------------------------------------------------------
# JsonText 约定的结构守卫
# ---------------------------------------------------------------------------

def _is_builtin_json(type_) -> bool:
    """判断一个列类型是不是 SQLAlchemy 自带的 ``JSON``（含 ``TypeDecorator`` 的底层）。"""
    if isinstance(type_, BuiltinJson):
        return True
    impl = getattr(type_, "impl", None)  # TypeDecorator 的真实落库类型
    return isinstance(impl, type) and issubclass(impl, BuiltinJson)


def test_no_column_uses_builtin_sqlalchemy_json():
    """``JsonText`` 已是全库约定，任何一列退回自带 ``JSON`` 都要当场炸。

    自带 ``JSON`` 在 SQLite 上是 NUMERIC 亲和性：``original_value = 0.0`` 会存成
    ``integer 0``、读回 ``int 0``，审计记录里的「原值 65.0 kg」变成「原值 65」。
    行为侧已有 ``test_json_text_keeps_float_and_none`` 覆盖，这条是结构侧的守卫——
    它不看某一列的行为，而是遍历 25 张表的每一列，让「新加的模型忘了这条约定」也
    逃不掉。
    """
    tables = Base.metadata.tables
    assert len(tables) == 25, "守卫的覆盖面必须先被确认是这 25 张表"

    offenders = [
        f"{table.name}.{column.name}"
        for table in tables.values()
        for column in table.columns
        if _is_builtin_json(column.type)
    ]
    assert offenders == [], f"这些列用了自带 JSON，必须换成 JsonText：{offenders}"

    # 守卫自己也得有牙：21 个 JSON 形态的列确实被遍历到了，不是空跑。
    # Plan 02 Task 2 把 8 改成 9：新增的是 ``exercise.targets``（动作瞄准的素质桶名列表）。
    # ⚠️ Task 3 的 ``prescription_template`` **没有** JsonText 列（10 列全是 String / Date /
    # Boolean / int），故那个 9 当时**不变**（P2-A6 的教训：加表时要顺手核一遍这个数）。
    # **Task 6 一次加 5 个 → 9 + 5 = 14**（派单的 Step 0 九格清单漏了这一格，实测发现）：
    # ``prescription`` 的 ``training_package`` / ``assembly_snapshot`` /
    # ``safety_substitutions`` / ``teacher_overrides`` / ``trigger_reasons``；
    # ``weekly_adjustment`` 一个都没有（``reason`` 是自由文本，照 ``cleaning_log.reason``
    # 的既有口径用 ``Text``）。
    # **Plan 03 Task 2 一次加 7 个 → 14 + 7 = 21**（运行时口径复算，不照抄计划正文）：
    # ``mini_test.item_combo``、``alert.trigger_snapshot``，以及 ``weekly_class_report``
    # 的 5 个（``layer_distribution`` / ``rpe_summary`` / ``checkin_rate_by_layer`` /
    # ``progress_board`` / ``alert_summary``）。另外 4 张新表一个都没有——
    # ``class_session`` / ``rpe_record`` / ``training_log`` / ``notification`` 全是标量列。
    # ⚠️ 这个数字与 ``app/db/models/_shared.py`` 的
    # ``JsonText`` docstring、``app/db/models/__init__.py`` 的约定 3 是**三处同一事实**，
    # 改一处要改三处（硬规矩 #66）。
    json_text_columns = sorted(
        f"{table.name}.{column.name}"
        for table in tables.values()
        for column in table.columns
        if type(column.type).__name__ == "JsonText"
    )
    assert len(json_text_columns) == 21, json_text_columns
    assert "cleaning_log.original_value" in json_text_columns
    assert "exercise.targets" in json_text_columns
    assert "prescription.trigger_reasons" in json_text_columns
    # Plan 03 Task 2 的 7 个：点名两个「一张表只有一列」的，与 ``weekly_class_report``
    # 那一族（5 列全部是 JSON，故按表数出 5 个）
    assert "mini_test.item_combo" in json_text_columns
    assert "alert.trigger_snapshot" in json_text_columns
    assert sum(1 for c in json_text_columns if c.startswith("weekly_class_report.")) == 5
    assert "rpe_record.rpe" not in json_text_columns, "标量列不许用 JsonText"


# ---------------------------------------------------------------------------
# Ruling 31：``batch_id`` 一词专指 daily_sync_run 的外键
# ---------------------------------------------------------------------------

# 全库唯一允许拥有 ``batch_id`` 列的表——即 ``delete_by_batch`` 的合法目标。
# Plan 01 结案时是**三张派生表**；Plan 02 Task 6 加 ``prescription`` 与 ``weekly_adjustment``
# → **五张**（P6-A8：``weekly_adjustment`` 也要有 ``batch_id``，因为 Task 7 的
# ``_replay_cleanup`` 要按 ``batch_id`` 删它，而 ``repo.delete_by_batch`` 要求模型有这一列）；
# **Plan 03 Task 2 加 4 张 → 九张**：``class_session`` / ``training_log`` / ``alert`` /
# ``weekly_class_report``——它们是批处理产物，重放那天要能按批删干净。
# ⚠️ **同批的另外三张刻意不带**：``rpe_record`` / ``mini_test`` / ``notification`` 是
# **用户实时写入**的（学生在课堂上交的快评、教师批量录入的小测、已经推给某人的消息），
# 按 ``batch_id`` 整批删会把「学生刚交的作业」连同重放一起抹掉。给全部 7 张加 ``batch_id``
# 是本清单最容易被「顺手补齐」破坏的一条，故理由逐字写在 ``models/feedback.py`` 的
# 模块 docstring 里，并由 :func:`test_the_three_user_written_tables_have_no_batch_id` 钉住。
# ⚠️ **Task 9 把它从 ``_DERIVED_TABLES`` 改名为 ``_BATCH_OWNED_TABLES``**（待清扫第 2 条
# 结案）：``prescription`` / ``weekly_adjustment`` 不是「派生指标」，它们是**管道产物**
# ——与派生表同一类的是「由每日批处理按 ``batch_id`` 写、也按 ``batch_id`` 删」这个性质，
# 而 ``batch_id`` 一词专指的正是它（Ruling 31）。原名从 Task 6 扩到五张那一刻起就名不副实，
# 当时留的话是「等 Task 7 把 ``_replay_cleanup`` 接上时一并处理」，Task 7 接完了却没改。
# 新名取「**归每日批处理所有**」而不是「批处理产物」，因为判据是 ``batch_id`` 那一列
# （= ``delete_by_batch`` 的合法目标），而不是「谁算出来的」。
# ⚠️ 上一段此前印的是「把它从 ``_BATCH_OWNED_TABLES`` 改名为 ``_BATCH_OWNED_TABLES``」
# ——原名被某一次全局替换一起吃掉了，Plan 03 Task 2 按 ``app/pipeline/daily.py``
# ``_replay_cleanup`` docstring 里那句仍正确的记录改回来。
# ⚠️ **连带改名的散文引用共三处**（``models/prescription.py`` 那条 ``git grep`` 指令与
# ``WeeklyAdjustment.batch_id`` 的列注释、``models/__init__.py`` 的模块 docstring）；
# ``app/db/repo.py`` 与 ``app/db/models/assessment.py`` 里写的是「Plan 01 的三张派生表」
# 这个**说法**、不是这个常量名，它对 Plan 01 仍为真，故不动。
# ⚠️ **本常量只有这一份定义**（Plan 03 Task 2 实测，取证 ``t2_probes/p03_batch_owned.py``）：
# ``git grep -n "_BATCH_OWNED_TABLES" -- backend/app`` 的**八处**命中
# （``models/prescription.py`` 三处、``models/feedback.py`` 两处、``pipeline/daily.py`` 两处、
# ``models/__init__.py`` 一处）**全部是散文引用**，没有一处是赋值。
# 故派单预检 P3-A3 说的「它是生产代码里的常量、测试那一份是镜像」与基线不符——
# **不存在需要同步的第二份**；要改的只有下面这九个字面量，以及那八处散文里
# 「五张」的说法（本 Task 之后是九张）。
_BATCH_OWNED_TABLES = {
    "derived_metrics", "stratification_result", "percentile_snapshot",
    "prescription", "weekly_adjustment",
    "class_session", "training_log", "alert", "weekly_class_report",
}


def test_fitness_test_result_has_no_batch_id_attribute():
    """``FitnessTestResult`` 不得再有 ``batch_id`` 属性，那条外键叫 ``test_batch_id``。

    这是 Ruling 31 的回归守卫，也是它唯一的存在理由：没有这条断言，改名会被后人当成
    一次「不够简洁」的重命名而顺手改回去。改回去的代价是静默删源数据——
    ``fitness_test_batch.id`` 只有 1/2/3（week1/week8/week16），``daily_sync_run.id``
    按业务日递增（一学期 1…112），故误调
    ``delete_by_batch(session, FitnessTestResult, sync_run_id)`` 时，凡
    ``sync_run_id ∈ {1, 2, 3}`` 都会**匹配上并删掉真实的源体测成绩**（实测 3 → 2 行、
    返回 1、无任何异常）。两列都是 int：外键拦不住（每个值各自合法，Ruling 27 的钩子
    在这里帮不上忙），``AttributeError`` 也拦不住（属性存在）。删**源**数据比删派生行
    严重得多——派生行重算就回来了，源体测数据删了就是删了。

    改名后本表没有 ``batch_id`` 属性，那一脚踩下去是响亮的 ``AttributeError``，与
    ``CleaningLog`` 用 ``sync_run_id`` 而非 ``batch_id`` 的既有设计同一口径。
    """
    assert not hasattr(M.FitnessTestResult, "batch_id")
    assert hasattr(M.FitnessTestResult, "test_batch_id")

    # 改名只换名字、不换语义：这条外键仍指向体测批次，不是 daily_sync_run
    column = M.FitnessTestResult.__table__.c.test_batch_id
    assert [fk.target_fullname for fk in column.foreign_keys] == ["fitness_test_batch.id"]


def test_only_batch_owned_tables_expose_batch_id():
    """命名规则必须机器可查，不能只是「大家记得」的约定。

    遍历 ``Base.metadata``，有 ``batch_id`` 列的表**恰好**是 :data:`_BATCH_OWNED_TABLES` 那九张
    （Plan 01 的三张派生表 + Plan 02 Task 6 的 ``prescription`` / ``weekly_adjustment``
    + Plan 03 Task 2 的 ``class_session`` / ``training_log`` / ``alert`` /
    ``weekly_class_report``）。
    ``batch_id`` 在本项目里专指「指向 ``daily_sync_run`` 的外键」，也就是 ``delete_by_batch``
    可据以删除的归属键；任何别的父表都得用可区分的名字（``fitness_test_result.test_batch_id``
    指体测批次、``cleaning_log.sync_run_id`` 指同步运行）。

    只断言列名还不够——名字对了语义错了才是 Ruling 31 要防的失效，故同时断言这九列
    真的指向 ``daily_sync_run``。
    """
    tables = Base.metadata.tables
    assert len(tables) == 25, "守卫的覆盖面必须先被确认是这 25 张表"

    observed = {
        name for name, table in tables.items() if "batch_id" in set(table.c.keys())
    }
    assert observed == _BATCH_OWNED_TABLES, (
        f"batch_id 专指 daily_sync_run 的外键，实到 {sorted(observed)}"
    )

    for name in sorted(_BATCH_OWNED_TABLES):
        column = tables[name].c.batch_id
        assert [fk.target_fullname for fk in column.foreign_keys] == [
            "daily_sync_run.id"
        ], f"{name}.batch_id 必须指向 daily_sync_run"


def test_the_three_user_written_tables_have_no_batch_id():
    """Plan 03 Task 2 那 7 张表里，**只有 4 张**该有 ``batch_id``；另外三张必须没有。

    上面那条守卫按**集合相等**判，已经能抓住「多一张」；本条把**理由**与另外三张的
    名字一起钉住，因为它们是同一个决定的两半，而失效方向是「顺手补齐」：
    给全部 7 张加 ``batch_id`` 看起来更整齐，代价却是重放那天
    :func:`app.pipeline.daily._replay_cleanup`（**Plan 03 Task 7 已把 ``Alert`` 接进那份清单**，Task 8 又接了 ``WeeklyClassReport``，故今天是七张）
    按批删掉**学生刚在课堂上交的快评**、**教师刚批量录入的小测**与**已经推给某人的站内消息**。
    派生行重算就回来了，这三类是用户手工产生的、删了就是删了——与
    :func:`test_fitness_test_result_has_no_batch_id_attribute` 守的「删源数据比删派生行
    严重得多」是同一条判断。

    ⚠️ 三张表的 ``batch_id`` **缺席**由本条与上面那条**双向**钉住：本条点名三张表没有，
    上面那条保证没有第八张。少了本条，把 ``rpe_record`` 加进 :data:`_BATCH_OWNED_TABLES`
    就能让上面那条继续全绿。
    """
    tables = Base.metadata.tables
    for name in ("rpe_record", "mini_test", "notification"):
        assert name in tables, f"{name} 这张表本身必须在（本条只判它没有 batch_id）"
        assert "batch_id" not in set(tables[name].c.keys()), (
            f"{name} 是用户实时写入的表，不得有 batch_id："
            "重放按批删会抹掉学生刚交的作业（理由见 models/feedback.py 的模块 docstring）"
        )
    # 反面：同批的 4 张批处理产物**必须**有，否则「按批删」对它们够不着
    for name in ("class_session", "training_log", "alert", "weekly_class_report"):
        assert "batch_id" in set(tables[name].c.keys()), f"{name} 是批处理产物，必须有 batch_id"


# ---------------------------------------------------------------------------
# Ruling 121 / 137（Task 10 Step 0.2、0.3）：两个新取值域与 domain 的一致性
# ---------------------------------------------------------------------------

def _snapshot_row(source: str) -> PercentileRow:
    """一行只为了拿 ``source`` 的快照行（``summarize_source`` 只读这一列）。"""
    return PercentileRow(
        item=SnapshotMetric.SPRINT_50M, sex=Sex.MALE, age_group=AGE_GROUPS[0],
        p10=1.0, p20=2.0, p25=3.0, p50=4.0, p75=5.0, sample_size=30, source=source,
    )


def test_percentile_snapshot_item_domain_matches_snapshot_metric(session):
    """``percentile_snapshot.item`` 的取值域与 domain 的 ``SnapshotMetric`` 逐字一致。

    与 ``Student.SEXES`` 同一条处置：db 层不 import domain，代价是两处需人工同步，
    漂移只能靠这条测试抓。**两个方向都致命**：少了 ``muscle_mass_kg``，Task 10 物化
    肌肉量行时会被自己刚加的 CHECK 拒收（响亮，但整批回滚）；多一个 domain 不认的值，
    库里就存得下一行 ``lookup_p20`` 永远匹配不上的判定线（静默）。
    """
    assert {m.value for m in SnapshotMetric} == M.PercentileSnapshot.ITEMS

    checks = {c.name: str(c.sqltext) for c in M.PercentileSnapshot.__table__.constraints
              if type(c).__name__ == "CheckConstraint"}
    assert "ck_percentile_snapshot_item" in checks
    sqltext = checks["ck_percentile_snapshot_item"]
    assert sqltext.startswith("item IN (")
    # 肌肉量是 Ruling 121 才进来的那一个：它是 spec §6.3② 那条 P20 判定线的样本
    assert "'muscle_mass_kg'" in sqltext
    for value in M.PercentileSnapshot.ITEMS:
        assert f"'{value}'" in sqltext


def test_percentile_source_domain_covers_the_producer_codomain(session):
    """``percentile_source`` 的取值域必须容得下生产者 :func:`summarize_source` 的**全部**输出。

    ``"none"`` 是 Ruling 137 补的第三值（``valid_count = 0``，即「没有用过任何判定线」）。
    少了它，Z0 那条路径在 Task 10 落库时会被 CHECK 约束拒收——而那正是最需要留痕的一类人；
    而拿 ``"school"`` 去填更糟：它会声称「这个人的判定线来自校内百分位」，可他根本没有
    判定线，那是一条凭空造出的可追溯性。
    """
    assert M.StratificationResult.PERCENTILE_SOURCES == {"school", "national", "none"}

    produced = {
        summarize_source([]),                                        # 一行都没用过
        summarize_source([_snapshot_row("school")]),
        summarize_source([_snapshot_row("national")]),
        # 混用：任一项降级即 national（保守侧）
        summarize_source([_snapshot_row("school"), _snapshot_row("national")]),
    }
    assert produced == {"none", "school", "national"}, "生产者的值域恰好是这三个"
    assert produced <= M.StratificationResult.PERCENTILE_SOURCES

    checks = {c.name: str(c.sqltext)
              for c in M.StratificationResult.__table__.constraints
              if type(c).__name__ == "CheckConstraint"}
    assert checks["ck_stratification_result_percentile_source"] == (
        "percentile_source IN ('national', 'none', 'school')"
    )
    # String(8) 刚好容得下最长的 "national"，不得有人往里塞更长的 token
    assert max(len(value) for value in produced) <= \
        M.StratificationResult.__table__.c.percentile_source.type.length


# ---------------------------------------------------------------------------
# Ruling 144 / 硬规矩 #18：列宽必须容得下取值域里最长的那个值
# ---------------------------------------------------------------------------

# :func:`app.db.models._in_domain` 生成的约束文本形如 ``column IN ('a', 'b')``（取值按
# 字典序排序、单引号转义为两个单引号）。从文本反解出「列 → 允许值集合」，表就是
# **自描述**的：Plan 02/03 新加的表与列自动被覆盖，不必回来手抄第二张清单——手抄的清单
# 就是第二个所有者，迟早与 DDL 漂移（Ruling 35/36 的单一所有者原则）。
_IN_DOMAIN_SQL = re.compile(r"^\s*(\w+) IN \((.*)\)\s*$")
_QUOTED_VALUE = re.compile(r"'((?:[^']|'')*)'")


def _in_domain_columns() -> dict[tuple[str, str], set[str]]:
    """遍历 ``Base.metadata``，反解每条 ``_in_domain`` CHECK 约束的列名与允许值集合。"""
    parsed: dict[tuple[str, str], set[str]] = {}
    for table in Base.metadata.tables.values():
        for constraint in table.constraints:
            if type(constraint).__name__ != "CheckConstraint":
                continue
            match = _IN_DOMAIN_SQL.match(str(constraint.sqltext))
            if match is None:
                # 不是取值域约束。⚠️ Plan 03 Task 2 之前本库**一条都没有**（这一行因此
                # 是死代码）；现在有两处，都是本 Task 加的：
                # ① ``rpe_record.ck_rpe_record_rpe``（``rpe BETWEEN 0 AND 10``）——
                #    整数区间不是词表，:func:`app.db.models._shared._in_domain` 不适用
                #    （P3-A5），故是全库第一处**手写**的 CHECK；
                # ② ``alert.ck_alert_subject_is_exactly_one``
                #    （``(student_id IS NULL) <> (course_section_id IS NULL)``）——
                #    它约束的是**两列之间的关系**、不是某一列的取值域，
                #    是本库第一处这一类的 CHECK（顶回 #2 的 ``subject_key`` 设计的前提守卫）。
                # 两者各由一条测试单独钉住：
                # :func:`test_rpe_check_is_generated_from_the_class_constants` 与
                # :func:`test_alert_subject_is_exactly_one_of_student_or_section`。
                continue
            values = {
                v.replace("''", "'") for v in _QUOTED_VALUE.findall(match.group(2))
            }
            parsed[(table.name, match.group(1))] = values
    return parsed


def test_string_column_widths_fit_their_value_domains():
    """凡 ``String(n)`` 列存枚举值或固定词表，``n`` 必须 ≥ 该域内最长值的长度。

    SQLite **不强制** ``VARCHAR`` 长度，故这类溢出在测试里永远不报错——Ruling 144 的
    ``derived_metrics.trend String(16)`` 就是这样漏了 7 个任务：``Trend.INSUFFICIENT.value``
    = ``"insufficient_data"`` 是 17 字符，500 人首批实测有 **209 行（41.8%）**往这一列写它。
    换 MySQL / PostgreSQL 会截断成 ``"insufficient_dat"``，读回来 ``Trend(...)`` 当场
    ``ValueError``——**炸在读侧不在写侧**，离真因隔一整个批处理周期。

    取值域的两个来源，都不是手抄的第二份清单：

    1. **有 CHECK 约束的列**——从 :func:`_in_domain` 生成的约束文本反解（今天 **24** 列：
       ``student.sex``、``course_section.grouping_mode``、``fitness_test_batch.timepoint``、
       ``percentile_snapshot`` 的 ``source`` / ``sex`` / ``item``、``stratification_result``
       的 ``label`` / ``percentile_source``、``daily_sync_run.status``、``cleaning_log.kind``、
       Plan 02 Task 2 新增的 ``exercise.impact_level``、Task 3 新增的
       ``prescription_template`` 的 ``layer`` / ``weakness`` / ``body_comp`` /
       ``review_status``、Task 6 新增的 ``prescription.status`` 与
       ``weekly_adjustment.source``、Task 7 fix round 1（F1-1）新增的
       ``prescription.label_at_generation``、**Plan 03 Task 2 新增的 5 列**：
       ``training_log.feeling``、``alert.level``、``alert.status``、
       ``notification.recipient_kind``、``notification.channel``，以及
       **Plan 03 Task 5 新增的 ``training_log.source``**（P5-A3：那一列此前刻意没有
       CHECK，因为它的取值域当时没有唯一所有者；Task 5 落地采集端点时按
       ``TrainingLog.source`` 列注释里写下的那句「Task 5 落地时必须回来定这个值域并补
       CHECK」兑现，于是本清单从 23 涨到 **24**）。
    2. **没有 CHECK 约束、但取值域有唯一所有者的列**——见下方注释里各自的出处。

    ⚠️ **这道遍历测试只看得见第 1 类**（Plan02 账本 P2-A5 / P3-A5）：``Exercise`` 的 5 个
    ``String(n)`` 列里只有 ``impact_level`` 带 ``_in_domain`` CHECK，``ref`` / ``name`` /
    ``video_url`` / ``equipment`` 的取值域不是封闭集合、没有 CHECK，故**完全不被本测试
    覆盖**——它们的列宽断言住在
    ``tests/test_refdata_prescription.py::test_exercise_string_column_widths_fit_the_yaml_values``
    （实际侧从 ``exercises.yaml`` 现读）。**Task 3 同型**：``PrescriptionTemplate`` 的 7 个
    ``String(n)`` 列里有 4 个带 CHECK（自动被本测试覆盖），而 ``template_ref`` / ``version``
    / ``reviewer`` 没有 → 它们的列宽断言住在
    ``tests/domain/test_prescription_templates.py::test_template_string_column_widths_fit_the_yaml_values``
    （实际侧从 18 份模板 YAML 现读）。
    ⚠️ **Plan 03 Task 2 的 7 张新表里原有 6 个 ``String(n)`` 列没有 CHECK，Task 5 之后
    是 5 个**（``training_log.source`` 按 P5-A3 补了 ``ck_training_log_source``，
    于是它落进上面第 1 类、被本遍历**自动**覆盖）：
    ``alert.rule_id`` / ``alert.window_key`` / ``alert.subject_key`` /
    ``class_session.rpe_token`` / ``mini_test.entered_by``
    → 由 :func:`test_the_unconstrained_string_columns_of_the_plan03_tables_are_wide_enough`
    按**字面量**逐个钉住（那 5 个列的取值域今天都还没有唯一所有者，理由逐字写在
    ``models/feedback.py`` 各列的注释里）。⚠️ 那条测试**仍保留** ``training_log.source``
    的一格（钉「列宽恰好 16」）：本遍历只判**够宽**（``width >= len(longest)``）、
    不判「不许改窄」，而 SQLite 不强制 ``VARCHAR`` 长度，故那一格是防改窄的唯一守卫。
    """
    domains = _in_domain_columns()
    # 空转守卫：正则写错会静默匹配到 0 列而全绿（那时 offenders 恒为空）。
    # ⚠️ 这是**下界**、刻意不逐 Task 抬高：它的职责只是「正则没有失配到 0 列」，
    # 抬到 == 11 会让 Plan 02 剩下的三个 Task 每次都来改这一行，而它抓不到任何新失效。
    assert len(domains) >= 10, f"反解出的受约束列数不对，正则可能失配：{sorted(domains)}"

    # 无 CHECK 约束的四列，取值域各自指向生产里的唯一所有者：
    # · ``derived_metrics.trend``       ← :class:`app.domain.derive.Trend` 的成员值
    #   （写入处 ``pipeline/daily.py`` 的 ``trend=derived.trend.value``），最长 17。
    # · ``stratification_result.hit_rules`` ← ``",".join(RuleId.value)``。Z0 路径恰为
    #   ``"Z0"``、非 Z0 路径是 7 条分层规则的已评估前缀，**两者互斥**（Ruling 132），
    #   故生产最大值是非 Z0 的完整前缀 ``"R1,R2,Y1,Y2,Y3,Y4,G1"`` = **20**，不是把 Z0
    #   也串起来的 23（Ruling 148）。
    # · ``percentile_snapshot.age_group`` ← :data:`app.domain.indicators.AGE_GROUPS`
    #   （全仓唯一口径），最长 5。
    # · ``cleaning_log.field`` ← :data:`app.domain.indicators.CLEANING_FIELDS`
    #   （**Plan 02 Task 1 新增**，Plan01 Ruling 156 的落点：这一列此前**没有任何所有者**，
    #   13 个字段名散落在 ``clean.py`` 的 9 个写入点上）。最长 17 = ``"vital_capacity_ml"``。
    #   它与清洗层实际产出的一致性由
    #   ``tests/pipeline/test_clean.py::test_cleaning_fields_cover_every_produced_field``
    #   钉住（那一侧从两个记录数据类的 ``fields()`` 推导，两侧不同源）。
    domains[("derived_metrics", "trend")] = {t.value for t in Trend}
    domains[("stratification_result", "hit_rules")] = {
        ",".join(rule.value for rule in RULE_ORDER if rule is not RuleId.Z0),
        RuleId.Z0.value,
    }
    domains[("percentile_snapshot", "age_group")] = set(AGE_GROUPS)
    domains[("cleaning_log", "field")] = set(CLEANING_FIELDS)

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


# ---------------------------------------------------------------------------
# Plan 02 Task 1：models.py 拆包的导入面基线（Plan02 Ruling 1）
# ---------------------------------------------------------------------------

# 拆包**之前**在基线 ``e26347f`` 上实测的 ``app.db.models`` 公有导入面，逐字抄进来。
# 取法（在 ``backend/`` 下跑，一次性取证，之后不再重跑——重跑就是拿拆包后的结果当基线）::
#
#     python -c "from app.db import models; import json; print(json.dumps(sorted(n for n in dir(models) if not n.startswith('_')), ensure_ascii=False))"
#
# **不从拆包后的 ``models`` 读回来跟自己比**（硬规矩 #35）：那样两侧同源，漏导出一个类
# 两边一起少一个、恒等成立。这 33 个名字里既有 14 张表的类，也有 ``Base`` / ``JsonText``
# 这两个真正被跨模块引用的基础设施，还有一批**偶然公有**的名字（``dt`` / ``json`` /
# ``Boolean`` / ``mapped_column`` …）——它们本来就是单文件 ``models.py`` 的模块级 import，
# 因此出现在 ``dir()`` 里。保留它们是判据「逐字相同」的应有代价：宁可多保住几个没人用的
# 名字，也不要让判据松到抓不住「漏导出一个类」。
_MODELS_PUBLIC_BASELINE = [
    "Any", "Base", "BodyComposition", "Boolean", "CheckConstraint", "CleaningLog",
    "CourseSection", "DailySyncRun", "Date", "DateTime", "DerivedMetrics", "Enrollment",
    "FitnessTestBatch", "FitnessTestResult", "Float", "ForeignKey", "Integer",
    "InterestSurvey", "Iterable", "JsonText", "Mapped", "PercentileSnapshot", "Semester",
    "StratificationResult", "String", "Student", "Teacher", "Text", "TypeDecorator",
    "UniqueConstraint", "dt", "json", "mapped_column",
]

# 拆包**新增**的六个子模块名。它们是包的结构性属性（``from .x import *`` 必然在父包上
# 留下 ``x`` 这个属性），不是导入面，故从比对里排除。
_MODELS_SUBMODULES = frozenset({
    "organisation", "assessment", "derived", "prescription", "feedback", "ops",
})

# 拆包前的 ``__all__``（14 张表的声明序，spec §4.1→§4.6）
_MODELS_ALL_BASELINE = [
    "Semester", "Teacher", "Student", "CourseSection", "Enrollment",
    "FitnessTestBatch", "FitnessTestResult", "BodyComposition", "InterestSurvey",
    "PercentileSnapshot", "DerivedMetrics", "StratificationResult",
    "DailySyncRun", "CleaningLog",
]


def test_models_public_namespace_is_unchanged_by_the_split():
    """``app.db.models`` 拆成包之后，公有导入面**逐字未变**（Plan02 Ruling 1）。

    这是「``from app.db import models`` 与 ``models.X`` 的既有写法不变」这句散文的
    **唯一可执行判据**：散文不可执行，而「漏导出一个类」的失效形态是运行时才
    ``AttributeError``——恰好是这条要求要防的事。

    排除六个子模块名之前先断言两件事，好让排除本身不可能吞掉一次真回归：

    1. 排除集与基线**不相交**（若哪天有人把一个表模块命名为 ``derived`` 之外又与基线
       重名，这条会先红）；
    2. 排除集里的每个名字**确实是一个模块**（若 ``organisation`` 哪天变成了一个类，
       这条会红，而它就不该再被排除）。
    """
    assert len(_MODELS_PUBLIC_BASELINE) == 33, "基线是 33 个名字，抄漏了就当场红"
    assert not (_MODELS_SUBMODULES & set(_MODELS_PUBLIC_BASELINE)), (
        "排除集与基线相交，排除会吞掉真名字："
        f"{sorted(_MODELS_SUBMODULES & set(_MODELS_PUBLIC_BASELINE))}"
    )
    for name in sorted(_MODELS_SUBMODULES):
        assert isinstance(getattr(M, name, None), types.ModuleType), (
            f"{name} 不再是子模块，就不该继续被排除在导入面比对之外"
        )

    observed = {n for n in dir(M) if not n.startswith("_")}
    assert observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE), (
        f"少了 {sorted(set(_MODELS_PUBLIC_BASELINE) - observed)}，"
        f"多了 {sorted(observed - _MODELS_SUBMODULES - set(_MODELS_PUBLIC_BASELINE))}"
    )
    assert list(M.__all__) == _MODELS_ALL_BASELINE

    # 私有名里有一个是**承重的**：约束文本生成器。它带前导下划线故不在上面的比对里，
    # 但 tests/db/test_models.py 自己的注释与将来的迁移脚本都按
    # ``app.db.models._in_domain`` 引用它，故单独钉一条。
    assert callable(M._in_domain)
    # 25 张表一个不少地注册进了同一个 metadata（拆包最容易漏的就是这个）。下面点名的
    # 是**拆包前就有的 14 张**（``_MODELS_ALL_BASELINE``）；Plan 02 新增的
    # ``exercise`` / ``prescription_template`` / ``prescription`` / ``weekly_adjustment``
    # 与 Plan 03 Task 2 新增的 7 张**都不在**那份基线里（Ruling 97：新增的表**刻意不进**
    # ``models`` 的公有导入面），
    # 它们由 ``test_all_twenty_five_tables_created`` 的 ``expected`` 集合点名，并由
    # ``test_plan02_and_plan03_tables_stay_out_of_the_models_public_namespace``
    # 钉住「不进导入面」。
    assert len(Base.metadata.tables) == 25
    for name in _MODELS_ALL_BASELINE:
        assert getattr(M, name).__tablename__ in Base.metadata.tables


#: Ruling 97 要钉住的 **11 个表类**，按「住在哪个子模块」分组。
#:
#: ⚠️ **Plan 03 Task 2 的 7 个全在 ``feedback``**——包括 spec §4.6 的 ``Alert`` /
#: ``Notification`` 与 §4.7 的 ``WeeklyClassReport``。**不要按 spec 的章节标题把它们搬去
#: ``ops.py``**：``models/__init__.py`` 对 ``ops`` 是 ``from .ops import *``（星号导入），
#: 对 ``feedback`` 与 ``prescription`` 是 ``from . import feedback, prescription``（非星号）。
#: 搬过去这三个类名会**自动**进入 ``app.db.models`` 的公有命名空间，下面那条
#: ``…is_unchanged_by_the_split`` 当场红，而唯一的「修法」是把 ``_MODELS_PUBLIC_BASELINE``
#: 从 33 抬到 36——那正是 Ruling 97 逐字禁止的（P3-A1）。
_PLAN02_AND_03_TABLE_CLASSES = (
    ("prescription", ("Exercise", "PrescriptionTemplate", "Prescription", "WeeklyAdjustment")),
    ("feedback", ("ClassSession", "RpeRecord", "TrainingLog", "MiniTest",
                  "Alert", "Notification", "WeeklyClassReport")),
)


def test_plan02_and_plan03_tables_stay_out_of_the_models_public_namespace():
    """Ruling 97 对 **Plan 02 的 4 张表与 Plan 03 的 7 张表**同样成立。

    ⚠️ 函数名里的 ``plan02`` 在 Plan 03 Task 2 扩成 ``plan02_and_plan03``：本条守的是
    「**每一批新表**都按子模块引用」，名字只写一个计划会让下一个计划的实现者以为
    Plan 03 的表由别处守（或另起第三条同型守卫），而三处引用它的散文
    （``models/__init__.py``、``pipeline/daily.py``、``pipeline/prescription_stage.py``）
    也会跟着指向一个不存在的事实。

    :data:`_MODELS_PUBLIC_BASELINE` 钉的是**拆包之前**（基线 ``e26347f``）实测的 33 个公有名，
    往那份基线里加新名字等于把「拆包没改导入面」偷换成「拆包后的现状」，
    两侧就同源了（硬规矩 #35）。Plan 02 Task 2 对 ``Exercise``、Task 3 对 ``PrescriptionTemplate``
    各守住过一次（后者由
    ``tests/test_refdata_prescription.py::test_prescription_template_is_not_in_the_models_public_namespace``
    钉），Task 6 把 ``Prescription`` / ``WeeklyAdjustment`` 收进本条，Plan 03 Task 2 再把
    7 张反馈/预警表收进来——**同一条纪律，一份清单**。

    **为什么单独一条而不是往上面那条基线里加名字**：那条的判据是「集合**相等**于拆包前的
    33 个名字」，加名字会让它的函数名（``…is_unchanged_by_the_split``）当场变成谎话，
    而 Ruling 97 那条守卫的 docstring 逐字把「基线被更新成含新名字」列为它要防的失效形态。
    故本条与那条**分工**：那条守「拆包没改导入面」，本条守「Plan 02/03 的表按子模块引用
    （``from app.db.models.feedback import Alert``）」。

    ⚠️ **它守不住什么**（硬规矩 #39）：它不守「这 11 张表**存在**」——那是
    :func:`test_all_twenty_five_tables_created` 的 ``expected`` 集合与
    ``test_only_batch_owned_tables_expose_batch_id`` 的遍历在守；本条只守导入面。
    末尾那两句 ``<= set(Base.metadata.tables)`` 是**反空转**：它保证本条不是
    「因为类根本不存在所以不在公有面上」的假绿。
    """
    checked = 0
    for module_name, class_names in _PLAN02_AND_03_TABLE_CLASSES:
        submodule = getattr(M, module_name)
        for name in class_names:
            assert name not in M.__all__, f"{name} 不该出现在 models.__all__（Ruling 97）"
            assert not hasattr(M, name), (
                f"{name} 出现在了 app.db.models 的公有导入面上（Ruling 97 要求按子模块引用："
                f"from app.db.models.{module_name} import {name}）"
            )
            # 表本身**必须**注册进 metadata：`from . import feedback, prescription` 那一句
            # 是承重的（漏掉它这些类就不会被 import、也就不进 Base.metadata）
            assert hasattr(submodule, name), f"models/{module_name}.py 里没有 {name} 这个类"
            checked += 1
    assert checked == 11, f"本条要钉住 11 个表类，实到 {checked}"
    assert len(_MODELS_PUBLIC_BASELINE) == 33, (
        "基线是 33 个名字（拆包前实测），Plan 02/03 的 11 张表刻意不进这份清单"
    )
    assert len(_MODELS_SUBMODULES) == 6, "子模块仍是六个：本 Task 不新增、也不改名"
    assert {
        "exercise", "prescription_template", "prescription", "weekly_adjustment",
        "class_session", "rpe_record", "training_log", "mini_test",
        "alert", "notification", "weekly_class_report",
    } <= set(Base.metadata.tables)


# ---------------------------------------------------------------------------
# Plan 02 Task 1 Step 4：fitness_test_result.tested_on 与 daily_sync_run 的计数列
# ---------------------------------------------------------------------------

def _semester_and_student(session):
    sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
                     end_date=dt.date(2026, 1, 20), weeks=16, is_current=True)
    session.add(sem)
    session.flush()
    stu = M.Student(student_no="2025001001", name="张三", sex="male",
                    birth=dt.date(2006, 3, 4), grade=1)
    session.add(stu)
    session.flush()
    batch = M.FitnessTestBatch(semester_id=sem.id, timepoint="week1",
                               test_date=dt.date(2025, 9, 1))
    session.add(batch)
    session.flush()
    return sem, stu, batch


def test_fitness_test_result_tested_on_is_required(session):
    """``fitness_test_result.tested_on`` NOT NULL 且无缺省：漏传必须**当场炸**。

    这一列是「本条成绩是哪一天测的」的唯一所有者，而百分位阶段靠它按业务日期截断
    （``percentile_stage._results_of`` 的 ``tested_on <= as_of``）。做成可空的代价是
    静默的：``NULL <= as_of`` 在 SQL 里恒为 **NULL**（不是 TRUE 也不是 FALSE），
    ``WHERE`` 因此把那一行**悄悄丢掉**，于是「这个学生今天没有成绩」与「这个学生的成绩
    没写日期」在库里长得一模一样，而前者会让他走 Z0 → ``insufficient_data``。
    """
    _sem, stu, batch = _semester_and_student(session)
    column = M.FitnessTestResult.__table__.c.tested_on
    assert column.nullable is False, "本列不许为空，故必须显式给值"
    assert column.default is None, "也不得有缺省值：缺省会让「忘了写」看起来像「写了」"

    session.add(M.FitnessTestResult(test_batch_id=batch.id, student_id=stu.id,
                                    height_cm=172.5))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "fitness_test_result.tested_on" in str(excinfo.value)
    # 失败的 flush 让会话进入「必须回滚」状态；回滚把上面那三行夹具也一起撤掉
    # （它们从未 commit），故正向那一段重新建一次。
    session.rollback()
    _sem, stu, batch = _semester_and_student(session)

    # 给了值就照常落库、读回同一个日期
    day = dt.date(2025, 9, 4)
    session.add(M.FitnessTestResult(test_batch_id=batch.id, student_id=stu.id,
                                    tested_on=day, height_cm=172.5))
    session.flush()
    session.expire_all()
    assert session.scalar(select(M.FitnessTestResult)).tested_on == day


def test_daily_sync_run_carries_the_plan02_count_columns(session):
    """``muscle_line_gaps`` / ``prescription_count`` / ``alert_count`` 三列都在、都默认 0。

    ⚠️ **``prescription_count`` 与 ``alert_count`` 是 Plan 01 就建好的**：基线 ``e26347f``
    的 ``app/db/models.py:614-615`` 已经有这两列（``git grep -n "prescription_count" --
    backend/app`` 可复验）。Plan 02 计划原文写的「spec §4.6 明确列了『处方生成数、
    预警触发数』两列，**Plan 01 没建**」与基线不符，故 Task 1 没有新增它们，本测试只是
    把「三列都在、都默认 0」钉住，免得后面的人以为要再建一次。

    ``muscle_line_gaps`` 是本 Task **真正新增**的那一列，它取代了此前写进
    ``error_summary`` 的「注意（非错误）：N 个组没有肌肉量 P20 判定线……」自由文本
    （Plan02 Ruling 13：直接切、不双写）。默认 0 与其余计数列同一条理由——运行记录常在
    跑完之前就入库（要先拿到 ``id`` 当 ``batch_id`` 用），此时它是「还没数」而不是「未知」。
    """
    columns = M.DailySyncRun.__table__.columns
    for name in ("muscle_line_gaps", "prescription_count", "alert_count"):
        assert name in columns, f"daily_sync_run 缺列 {name}"
        assert columns[name].nullable is False, f"{name} 不许为空"
        assert columns[name].default.arg == 0, f"{name} 的默认值必须是 0"

    sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
                     end_date=dt.date(2026, 1, 20), weeks=16, is_current=True)
    session.add(sem)
    session.flush()
    run = M.DailySyncRun(semester_id=sem.id, business_date=dt.date(2025, 9, 15))
    session.add(run)
    session.flush()
    run_id = run.id
    session.expire_all()
    got = session.get(M.DailySyncRun, run_id)
    assert (got.muscle_line_gaps, got.prescription_count, got.alert_count) == (0, 0, 0)
    # error_summary 不再承载缺线提示：一个成功的运行它就是 NULL
    assert got.error_summary is None


# ---------------------------------------------------------------------------
# Plan 02 Task 1 Step 4 第 1 项：单人「当前分层」查询必须走索引
# ---------------------------------------------------------------------------

#: 两条生产读法：教师大屏点一个人看「他现在什么层」，以及看他的派生指标。
_SINGLE_PERSON_QUERIES = (
    ("stratification_result",
     "select id from stratification_result "
     "where student_id = 1 order by computed_on desc limit 1"),
    ("derived_metrics",
     "select id from derived_metrics "
     "where student_id = 1 and computed_on <= '2025-09-15' "
     "order by computed_on desc limit 1"),
)


def test_single_person_queries_are_index_served(session):
    """两条单人查询必须走 ``(student_id, computed_on)`` 索引，不得全表扫、不得另建临时 B-tree。

    **这条测试取代了计划 Step 4 第 1 项要的显式 ``Index``**，理由是本仓实测那条索引是
    **冗余**的：Plan01 Ruling 212 已经给这两张表加了
    ``UniqueConstraint("student_id", "computed_on")``，而 SQLite 会为 UNIQUE 约束自动建出
    一条同列序的索引（``sqlite_autoindex_<table>_1``），查询规划器已经在用它。

    实测（本机、CPython 3.11 + SQLAlchemy 2.1 + SQLite；500 人 × 112 业务日 = **56000 行**
    ``stratification_result``；每条查询 n=300、学号由 ``random.Random(20250828)`` 抽、先跑
    同规模一遍预热；落**磁盘**库、``eng.dispose()`` 之后按 ``.db`` 文件字节量体积）：

    ==============================  ==================  ==================  =====================
    场景                        单次墙钟中位 (ms，单次采样、方向不可复现)   ``.db`` 字节   EXPLAIN QUERY PLAN
    ==============================  ==================  ==================  =====================
    A 仅 UniqueConstraint 的自动索引        0.2708           5 423 104        ``USING COVERING INDEX sqlite_autoindex_stratification_result_1 (student_id=?)``
    B A + 显式 ``Index(student_id, computed_on)``  0.2941      6 791 168        ``USING COVERING INDEX ix_stratification_result_student_computed (student_id=?)``
    ==============================  ==================  ==================  =====================

    B/A = **1.086**（即加了索引**没有变快**，中位数还慢了 8.6%——⚠️ **这个方向不可复现**，
    是机器/负载噪声，四次连跑的值见下方「复跑」那一段；两个场景各自
    min…max = 0.1385…0.9031 与 0.1698…1.0212 ms，区间完全重叠），而文件体积
    **+1 368 064 B = +25.23%**（十进制百分比；计划原文写的代价是「+2.7% 文件体积」，
    与本次实测差一个量级）。计划原文的收益数字「57.9 ms → 0.2 ms（258×）」因此只能来自
    一个**没有**那条 UNIQUE 约束的 schema——即 Plan01 Ruling 212 落地之前的状态。

    ⚠️ **上面四个数不被守卫**（硬规矩 #39）：本测试守的是**查询计划**与**两条唯一约束的
    列序**，全仓**没有任何测试量墙钟或 ``.db`` 字节**——它们变了不会红。故上表属历史实测，
    而产生它的脚本此前不在库内（从仓库无法复现）；fix round 1 把它整段抄在下面，在**仓库根**跑
    ``python <存成 .py 的本段>`` 即可复现。

    本轮（Plan 02 Task 1 fix round 1）**复跑**了它：``.db`` 字节**逐字复现**（5 423 104 /
    6 791 168 / +1 368 064 B / +25.23%）；两条查询计划是**尾部逐字复现**——上表最后一列只印
    了 ``USING COVERING INDEX …`` 那一段，而 ``EXPLAIN QUERY PLAN`` 的 detail **全串**其实
    以 ``SEARCH stratification_result `` 开头（fix round 5 亲跑，两个场景的 detail 全串::

        A  SEARCH stratification_result USING COVERING INDEX sqlite_autoindex_stratification_result_1 (student_id=?)
        B  SEARCH stratification_result USING COVERING INDEX ix_stratification_result_student_computed (student_id=?)

    「逐字」是个强断言，不能用在截断过的引文上）。但**墙钟中位不复现**——同一个脚本
    连跑四次，B/A 依次是 **1.086 / 0.944 / 1.019 / 0.989**（每次 n=300）。所以可复现的结论
    只有「加了具名索引**没有可测的加速**」，而**「慢 8.6%」这个方向不可复现**，是机器/负载
    噪声；上表的 0.2708 / 0.2941 ms 仅作为**当时那一组**样本留档，不要当稳定量引用。

    复现脚本（完整内容，fix round 1 亲跑验证过；``#`` 注释处原本是脚本自己的 docstring，为了不与
    本 docstring 的三引号打架而改成注释）::

        import datetime as dt, pathlib, random, statistics, sys, tempfile, time
        sys.path.insert(0, "backend")
        from sqlalchemy import Index, create_engine, text
        from app.db import models as M
        from app.db.session import Session, init_db

        N, DAYS, BASE = 500, 112, dt.date(2025, 9, 1)
        Q = ("select id from stratification_result where student_id = :sid "
             "order by computed_on desc limit 1")


        def build(tmp, tag, extra_index):
            # 场景 A/B 只差 extra_index：A 只有 UniqueConstraint 的 autoindex，
            # B 再加计划 Step 4 第 1 项要的那条具名 Index
            dbfile = tmp / f"{tag}.db"
            eng = create_engine(f"sqlite:///{dbfile.as_posix()}")
            init_db(eng)
            if extra_index:
                Index("ix_stratification_result_student_computed",
                      M.StratificationResult.student_id,
                      M.StratificationResult.computed_on).create(eng)
            with Session(eng) as s:
                sem = M.Semester(name="2025-2026-1", start_date=BASE,
                                 end_date=BASE + dt.timedelta(days=DAYS + 1),
                                 weeks=16, is_current=True)
                s.add(sem); s.flush()
                run = M.DailySyncRun(semester_id=sem.id, business_date=BASE, status="success")
                s.add(run); s.flush()
                s.add_all([M.Student(student_no=f"2025{i:06d}", name="x", sex="male",
                                     birth=dt.date(2006, 1, 1), grade=1) for i in range(N)])
                s.flush()
                s.add_all([M.StratificationResult(
                    student_id=sid, computed_on=BASE + dt.timedelta(days=d), batch_id=run.id,
                    label="green", hit_rules="R1,R2,Y1", input_snapshot={},
                    percentile_source="school", valid_from=BASE + dt.timedelta(days=d))
                    for sid in range(1, N + 1) for d in range(DAYS)])
                s.commit()
            return eng, dbfile


        def bench(eng, n=300):
            # n 次同一条查询，学号由固定种子抽；先跑同规模一遍预热
            rng = random.Random(20250828)
            sids = [rng.randrange(1, N + 1) for _ in range(n)]
            out = []
            with eng.connect() as c:
                for sid in sids:
                    c.execute(text(Q), {"sid": sid}).all()
                for sid in sids:
                    t0 = time.perf_counter()
                    c.execute(text(Q), {"sid": sid}).all()
                    out.append((time.perf_counter() - t0) * 1000.0)
                plan = [r[3] for r in
                        c.execute(text("explain query plan " + Q.replace(":sid", "1")))]
            return out, plan


        tmp = pathlib.Path(tempfile.mkdtemp(prefix="pe_idx_"))
        res = {}
        for tag, extra in (("A", False), ("B", True)):
            eng, dbfile = build(tmp, tag, extra)
            with eng.connect() as c:
                assert c.execute(
                    text("select count(*) from stratification_result")).scalar() == N * DAYS
            samples, plan = bench(eng)
            eng.dispose()                       # 先释放句柄，再量 .db 字节
            lo, hi = min(samples), max(samples)
            res[tag] = (statistics.median(samples), lo, hi, dbfile.stat().st_size)
            print(f"{tag}  median={res[tag][0]:.4f} ms  min={lo:.4f}  max={hi:.4f}"
                  f"  .db={res[tag][3]} B")
            for p in plan:
                print(f"   plan: {p}")
        a, b = res["A"], res["B"]
        print(f"行数 {N}*{DAYS} = {N * DAYS}   B/A = {b[0] / a[0]:.3f}"
              f"   .db +{b[3] - a[3]} B = +{(b[3] - a[3]) / a[3] * 100:.2f}%")

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
        assert len(detail) == 1, f"{table} 的查询计划不止一步：{detail}"
        plan = detail[0]
        assert "SCAN" not in plan, f"{table} 走了全表扫：{plan}"
        assert "USING" in plan and "INDEX" in plan, f"{table} 没用索引：{plan}"
        # 前导列必须是 student_id：列序反过来的索引对这条查询毫无用处
        assert "student_id=?" in plan, f"{table} 的索引前导列不是 student_id：{plan}"
        # 排序由索引本身供给；出现这一句就说明规划器另建了临时 B-tree
        assert "TEMP B-TREE" not in plan, f"{table} 为 ORDER BY 另建了临时 B-tree：{plan}"

    # 守卫自己也得有牙：那条自动索引确实在库里，且列序是 (student_id, computed_on)
    for table in ("stratification_result", "derived_metrics"):
        uniques = {u["name"]: u["column_names"]
                   for u in inspect(conn).get_unique_constraints(table)}
        assert uniques[f"uq_{table}_student_day"] == ["student_id", "computed_on"], uniques


# ---------------------------------------------------------------------------
# Plan 02 Task 6：prescription / weekly_adjustment 两张表
# ---------------------------------------------------------------------------

def _prescription_context(session):
    """一行处方所需的最小上下文：学生 + 一次批处理运行（两个外键的父行）。"""
    sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
                     end_date=dt.date(2026, 1, 20), weeks=16, is_current=True)
    session.add(sem)
    session.flush()
    stu = M.Student(student_no="2025001001", name="张三", sex="male",
                    birth=dt.date(2006, 3, 4), grade=1)
    session.add(stu)
    session.flush()
    run = M.DailySyncRun(semester_id=sem.id, business_date=dt.date(2026, 3, 2),
                         status="success")
    session.add(run)
    session.flush()
    return stu, run


def _prescription_fields(stu, run, **overrides):
    """一行**合法**处方所需的字段：NOT NULL 的列一律显式给值（``status`` 刻意没有缺省）。

    ⚠️ ``assembly_snapshot`` 这里只放一个占位键：本文件守的是 **schema**，快照的
    「恰好 12 键 / ``apply_safety`` 至多追加 3 键」那两条契约住在
    ``tests/domain/test_prescription_{assembler,safety}.py``，在这里复制一份就是第二个所有者。
    ``valid_to`` 的字面量 ``2026-03-29`` = ``2026-03-02 + 4 周 − 1 天``（闭区间的第 28 天），
    算式的出处见 ``Prescription`` 的 docstring。
    """
    fields = dict(
        student_id=stu.id, generated_on=dt.date(2026, 3, 2), batch_id=run.id,
        template_ref="RED-END-ABN-01", microcycle_weeks=4,
        label_at_generation="red",
        training_package={"weeks": []}, assembly_snapshot={"as_of": "2026-03-02"},
        safety_substitutions=[], teacher_overrides=[], status="active",
        valid_from=dt.date(2026, 3, 2), valid_to=dt.date(2026, 3, 29),
        trigger_reasons=["first_stratification"],
    )
    fields.update(overrides)
    return fields


def test_prescription_template_ref_is_the_same_name_as_the_template_table_column():
    """P6-A7：``prescription`` 那一列叫 ``template_ref``，与 ``prescription_template`` 同名。

    domain 侧叫 ``template_id``（spec §7.2 ``:454`` YAML 骨架的字面键名），DB 侧统一叫
    ``template_ref``；两者是**同一串字符**，只在 ORM 边界上换名字。这条守卫钉住
    「DB 侧只有一个名字」：``prescription`` 上**不得**再长出一个 ``template_id`` 列——
    那正是 P6-A7 担心的失效（Task 7 的实现者会以为它们是两个东西）。
    """
    assert "template_ref" in Prescription.__table__.c
    assert "template_ref" in PrescriptionTemplate.__table__.c
    assert "template_id" not in Prescription.__table__.c, (
        "DB 侧统一叫 template_ref（P6-A7）；template_id 是 domain 侧的名字"
    )


def test_prescription_template_ref_column_is_as_wide_as_the_template_table_one():
    """硬规矩 #18 的补位：``template_ref`` **没有** CHECK，故不被那道列宽遍历测试覆盖。

    两列各自对**字面量 32** 断言（不是互相比，硬规矩 #35：互相比的话两列一起变窄也全绿），
    并对**字面量 14** 断言「今天最长的那个真实值塞得下」——14 是 spec §7.2 ``:454`` 的
    ``<层3>-<桶3>-<体成分3>-<序号2>`` 格式的长度，``RED-END-ABN-01`` 就是它。
    ⚠️ 与 Task 2 的 P2-A5、Task 3 的 P3-A5 同型：没有封闭取值域的列要自己找地方钉列宽。
    """
    assert Prescription.__table__.c.template_ref.type.length == 32
    assert PrescriptionTemplate.__table__.c.template_ref.type.length == 32
    longest_today = "RED-END-ABN-01"
    assert len(longest_today) == 14
    assert len(longest_today) <= Prescription.__table__.c.template_ref.type.length


def test_prescription_status_is_required_and_its_check_rejects_unknown_values(session):
    """``status`` NOT NULL、**无缺省值**、CHECK 的值域是 :attr:`Prescription.STATUSES`。

    与 ``daily_sync_run.status`` 的 ``default="failed"`` 相反（理由见 ``Prescription`` 的
    docstring）：那一列在 INSERT 时还不知道结局，本列在 INSERT 那一刻就已经知道了。
    给一个 ``default="active"`` 会让「忘了写 status」静默变成「这张处方是好的」，而 spec
    §7.4 恰恰要求「安全规则命中却找不到等价动作」时落成 ``needs_review``、**不得静默跳过**
    （Review Focus 第 5 条）。

    期望的 CHECK 文本**字面写死**（硬规矩 #35）：它是 ``_in_domain`` 按字典序生成的，
    从 ``STATUSES`` 现拼一份来比就是同源。
    """
    column = Prescription.__table__.c.status
    assert column.nullable is False, "本列不许为空，故漏传必须报错而不是静默落 NULL"
    assert column.default is None, "也不得有缺省值：缺省会让「忘了写」看起来像「写了」"
    assert Prescription.STATUSES == {"active", "replaced", "archived", "needs_review"}

    checks = {c.name: str(c.sqltext) for c in Prescription.__table__.constraints
              if type(c).__name__ == "CheckConstraint"}
    assert checks["ck_prescription_status"] == (
        "status IN ('active', 'archived', 'needs_review', 'replaced')"
    )

    stu, run = _prescription_context(session)
    fields = _prescription_fields(stu, run)
    del fields["status"]
    session.add(Prescription(**fields))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "prescription.status" in str(excinfo.value)
    session.rollback()

    stu, run = _prescription_context(session)
    session.add(Prescription(**_prescription_fields(stu, run, status="draft")))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "ck_prescription_status" in str(excinfo.value)


def test_prescription_label_at_generation_shares_its_domain_with_the_label_column(session):
    """**F1-1（Task 7 fix round 1）**：``label_at_generation`` 与 ``stratification_result.label``
    同口径——同宽（**20**）、同一个 CHECK 值域，且那个值域**只有一个所有者**。

    本列是触发 2（``current_label != last_prescription.label_at_generation``）的唯一输入，
    快照在处方行上才能离线复算（spec §4.3；理由逐字写在 ``Prescription`` 那一列的注释里）。
    两处各持一份词表就是漂移的温床，故 ``_in_domain`` 的值域直接引
    :attr:`M.StratificationResult.LABELS`——本条把这件事钉住：**两列的 CHECK 文本除了
    列名以外逐字相同**，且两侧都不是从被测模块现拼的（硬规矩 #35：期望值字面写死）。

    列宽对**字面量 20** 断言而不是互相比（互相比的话两列一起变窄也全绿），并对
    **字面量 17** 断言「最长的那个真实值塞得下」——17 = ``len("insufficient_data")``
    （Ruling 144 的同一个值；SQLite 不强制长度，故溢出只在换严格后端时才炸、且炸在读侧）。
    """
    column = Prescription.__table__.c.label_at_generation
    assert column.nullable is False, "触发 2 的判据不许为空：NULL 会让它静默不成立"
    assert column.default is None, "也不得有缺省值：它必须是生成当时那个标签的显式快照"
    assert column.type.length == 20
    assert M.StratificationResult.__table__.c.label.type.length == 20
    longest = "insufficient_data"
    assert len(longest) == 17
    assert len(longest) <= column.type.length

    checks = {c.name: str(c.sqltext) for c in Prescription.__table__.constraints
              if type(c).__name__ == "CheckConstraint"}
    label_checks = {c.name: str(c.sqltext)
                    for c in M.StratificationResult.__table__.constraints
                    if type(c).__name__ == "CheckConstraint"}
    assert checks["ck_prescription_label_at_generation"] == (
        "label_at_generation IN ('green', 'insufficient_data', 'red', 'yellow')"
    )
    # 单一所有者：两列的值域部分逐字相同（同一个类常量生成的）
    assert checks["ck_prescription_label_at_generation"].split(" IN ", 1)[1] == \
        label_checks["ck_stratification_result_label"].split(" IN ", 1)[1]

    stu, run = _prescription_context(session)
    fields = _prescription_fields(stu, run)
    del fields["label_at_generation"]
    session.add(Prescription(**fields))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "prescription.label_at_generation" in str(excinfo.value)
    session.rollback()

    stu, run = _prescription_context(session)
    session.add(Prescription(**_prescription_fields(stu, run, label_at_generation="blue")))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "ck_prescription_label_at_generation" in str(excinfo.value)


def test_weekly_adjustment_source_check_rejects_unknown_values(session):
    """``weekly_adjustment.source`` 的 CHECK 只放行 ``auto`` / ``teacher``（P6-A9）。

    ⚠️ ``auto`` 今天**没有任何生产写入方**（spec §8.4 的「预警触发减量 20%」留给 Plan 03）。
    它现在就在值域里，是因为届时往一个已结案的 CHECK 里加值等于重建库（本仓不做迁移）。
    本条同时钉住这件事：值域是**两个**值，不是「今天用得上的那一个」。
    """
    assert WeeklyAdjustment.SOURCES == {"auto", "teacher"}
    checks = {c.name: str(c.sqltext) for c in WeeklyAdjustment.__table__.constraints
              if type(c).__name__ == "CheckConstraint"}
    assert checks["ck_weekly_adjustment_source"] == "source IN ('auto', 'teacher')"
    # 硬规矩 #18：最长者 "teacher" 是 7 字符，String(8) 余量 1
    assert WeeklyAdjustment.__table__.c.source.type.length == 8

    stu, run = _prescription_context(session)
    rx = Prescription(**_prescription_fields(stu, run))
    session.add(rx)
    session.flush()
    session.add(WeeklyAdjustment(prescription_id=rx.id, batch_id=run.id, week=1,
                                 factor=0.8, reason="本周月考，减量",
                                 source="principal", created_at=dt.datetime(2026, 3, 2, 8, 0)))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "ck_weekly_adjustment_source" in str(excinfo.value)


def test_prescription_microcycle_weeks_is_snapshotted_on_the_row_not_on_the_template():
    """P6-A3：``microcycle_weeks`` 住在 ``prescription`` 上，**不在** ``prescription_template`` 上。

    两半都要钉：① 处方行上有这一列且 NOT NULL（触发 3 的判据与 ``valid_to`` 的算式都要它，
    缺了就没法离线复算一张旧处方的有效期）；② 模板索引表上**没有**它——那是**刻意的**，
    教师端要展示模板周期是 Plan 03 的 CRUD 层的活，今天加会让 Task 6 回头改 Task 3
    已结案的表 + ``sync_templates`` + 基线（硬规矩 #11）。少了 ②，下一个人会以为
    「模板表本来就有、处方行上这一列是冗余」而把它删掉。
    """
    column = Prescription.__table__.c.microcycle_weeks
    assert column.nullable is False, "触发 3 与 valid_to 都要它，缺了就没法离线复算"
    assert column.default is None, "它是生成当时从模板快照下来的，没有合理的缺省值"
    assert "microcycle_weeks" not in PrescriptionTemplate.__table__.c, (
        "P6-A3 刻意不给 prescription_template 加列；那是 Plan 03 CRUD 层的活"
    )
    assert len(PrescriptionTemplate.__table__.c) == 10, "Task 3 结案时是 10 列，本 Task 不动它"


def test_prescription_previous_had_overrides_is_a_column_not_a_snapshot_key(session):
    """P6-A2：``previous_had_overrides`` 是**独立的一列**，不是 ``assembly_snapshot`` 的第 16 个键。

    Task 5 刚钉死两条键集守卫（``assemble`` 产出恰好 12 键、``apply_safety`` 至多追加 3 键），
    往快照里加键会让**两条一起变红**；更要紧的是范畴错误——那一列的契约是「离线复算
    **本张**处方」，而这件事是**关于上一张处方**的事实。

    ``default=False`` 且 NOT NULL：首次生成没有「上一张」，此时它是 ``False``。
    「没有上一张」与「上一张没有覆盖」对**本张处方**的处置完全相同（都无覆盖可继承），
    故合并成一档、不另设三态（三态会让读侧处处防 ``None``，而 ``None`` 在这里没有独立含义）。
    """
    column = Prescription.__table__.c.previous_had_overrides
    assert column.nullable is False
    assert column.default.arg is False

    stu, run = _prescription_context(session)
    # previous_had_overrides **不传**，靠列上的缺省落 False
    rx = Prescription(**_prescription_fields(stu, run))
    session.add(rx)
    session.flush()
    rx_id = rx.id
    session.expire_all()
    assert session.get(Prescription, rx_id).previous_had_overrides is False


def test_same_day_second_prescription_for_one_student_is_rejected(session):
    """Review Focus 第 2 条：同一天被两次触发只生成一张处方，而这是**机制**不是纪律。

    ``(student_id, generated_on)`` 唯一 → 管道重跑、或「教师手动请求撞上自动触发」时，
    第二次的 INSERT 被数据库自己拒收，不必靠 Task 7 的实现者记得先查一遍。
    ⚠️ 约束名沿用 ``derived_metrics`` / ``stratification_result`` 那一对的
    ``uq_<table>_student_day`` 口径（Ruling 212），故 SQLite 为它自动建出的索引也叫
    ``sqlite_autoindex_prescription_1``——「这名学生当前生效的处方」那条读法
    （``WHERE student_id = ? ORDER BY generated_on DESC LIMIT 1``）因此不必另建具名索引
    （理由与 :func:`test_single_person_queries_are_index_served` 那一条相同：Plan01
    Ruling 212 的 UNIQUE 已经供出同列序的索引，再建一条只涨体积不涨速度）。
    ⚠️ **本条不查那条读法的查询计划**：``_SINGLE_PERSON_QUERIES`` 是 Plan 01 那两条的
    字面清单，处方读模型要到 Task 8 才落地，届时再往那份清单里加一行。
    """
    stu, run = _prescription_context(session)
    session.add(Prescription(**_prescription_fields(stu, run)))
    session.flush()
    session.add(Prescription(**_prescription_fields(stu, run, status="needs_review")))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    # ⚠️ SQLite 的 UNIQUE 报错**不带约束名**（它印的是列名），与 CHECK 报错不同——
    # CHECK 那一档印的是 ``ck_*`` 的名字（见上面那两条测试）。故约束名另从 DDL 反查。
    assert "UNIQUE constraint failed: prescription.student_id, prescription.generated_on" in str(
        excinfo.value
    )
    session.rollback()
    uniques = {u["name"]: u["column_names"]
               for u in inspect(session.connection()).get_unique_constraints("prescription")}
    assert uniques["uq_prescription_student_day"] == ["student_id", "generated_on"], uniques

    # 换个日期就是**另一张**处方（换处方时把上一张置 replaced 是 Task 7 的活）
    stu, run = _prescription_context(session)
    session.add(Prescription(**_prescription_fields(stu, run)))
    session.flush()
    session.add(Prescription(**_prescription_fields(
        stu, run, generated_on=dt.date(2026, 3, 30), valid_from=dt.date(2026, 3, 30),
        valid_to=dt.date(2026, 4, 26), trigger_reasons=["microcycle_expired"])))
    session.flush()
    assert session.scalar(select(func.count()).select_from(Prescription)) == 2


def test_delete_by_batch_reaches_both_new_tables(session):
    """P6-A8 的前提必须当场验：``delete_by_batch`` 对两张新表都能用。

    计划 Task 7 逐字写着「``_replay_cleanup`` 的清单要加上 ``prescription`` 与
    ``weekly_adjustment``（**按 ``batch_id`` 删**）」，而 ``repo.delete_by_batch`` 是
    ``delete(model).where(model.batch_id == …)`` ——模型没有这一列就当场 ``AttributeError``。
    本条把「有这一列」升级成「按它删真的能删掉」，免得 Task 7 才发现
    ``weekly_adjustment`` 少了列而要回头改一张已结案的表（硬规矩 #11）。

    删除顺序是承重的：``weekly_adjustment.prescription_id`` 指向 ``prescription``，
    且 SQLite 的 ``PRAGMA foreign_keys=ON``（Ruling 27）真的在强制它，故必须**先删子表**。
    """
    stu, run = _prescription_context(session)
    rx = Prescription(**_prescription_fields(stu, run))
    session.add(rx)
    session.flush()
    session.add(WeeklyAdjustment(prescription_id=rx.id, batch_id=run.id, week=1,
                                 factor=0.8, reason="本周月考，减量", source="teacher",
                                 created_at=dt.datetime(2026, 3, 2, 8, 0)))
    session.flush()
    session.commit()

    assert delete_by_batch(session, WeeklyAdjustment, run.id) == 1
    assert delete_by_batch(session, Prescription, run.id) == 1
    session.commit()
    assert session.scalar(select(func.count()).select_from(WeeklyAdjustment)) == 0
    assert session.scalar(select(func.count()).select_from(Prescription)) == 0


def test_prescription_valid_from_is_required_and_valid_to_is_not():
    """``valid_from`` NOT NULL、``valid_to`` nullable——与 Plan 01 的处置相反，两者都对。

    ``stratification_result.valid_to`` **恒 NULL**（每日快照没有自然有效期，且关账会让重放
    跨批改写）；``prescription.valid_to`` **要真的填**（处方天然有一个微周期的有效期，而
    「当前生效的处方」是 Plan 02 的核心查询）。差别来自「有没有自然有效期」，不是其中一个
    写错了——那段「为什么两者不同」逐字写在 ``Prescription`` 的 docstring 里。
    本条钉住 schema 侧的那一半：列**允许** NULL（``needs_review`` 的处方还没有确定的
    有效期），但 ``valid_from`` 不允许（一张处方必须能说清从哪天起按它练）。
    """
    assert Prescription.__table__.c.valid_from.nullable is False
    assert Prescription.__table__.c.valid_to.nullable is True
    assert Prescription.__table__.c.generated_on.nullable is False
    assert WeeklyAdjustment.__table__.c.created_at.nullable is False
    assert WeeklyAdjustment.__table__.c.created_at.default is None, (
        "时钟一律由调用方注入（Global Constraint #1），不得用 Python 侧或 DB 侧缺省"
    )


# ---------------------------------------------------------------------------
# Plan 03 Task 2：反馈三源 4 张 + 预警/通知 2 张 + 班级周报 1 张
# ---------------------------------------------------------------------------

def _feedback_context(session):
    """7 张新表所需的最小上下文：学期 + 教师 + 学生 + 教学班 + 一次批处理运行。

    与 :func:`_prescription_context` 分开两份而不是合并：那一份只造 ``prescription``
    的两个父行（学生 + 批次），本份还要教师与教学班（``class_session`` /
    ``weekly_class_report`` 的父行）。合并会让 Plan 02 那几条已结案的测试多建两行。

    ⚠️ **``session.rollback()`` 之后必须重新调一次本函数**：夹具从不 commit，
    一次 rollback 会把上面五行父行一起撤掉，而复用旧的 ``stu.id`` / ``run.id``
    会撞 ``FOREIGN KEY constraint failed``——炸点离真因（回滚）很远。下面每一条测试
    都按「回滚 → 重建上下文 → 重建字段字典」的形状写，字段字典因此一律是**函数**
    而不是模块级常量（照 :func:`_prescription_fields` 的既有口径）。
    """
    sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
                     end_date=dt.date(2026, 1, 20), weeks=16, is_current=True)
    session.add(sem)
    session.flush()
    teacher = M.Teacher(staff_no="T2025001", name="李老师")
    session.add(teacher)
    session.flush()
    stu = M.Student(student_no="2025001001", name="张三", sex="male",
                    birth=dt.date(2006, 3, 4), grade=1)
    session.add(stu)
    session.flush()
    section = M.CourseSection(semester_id=sem.id, teacher_id=teacher.id,
                              name="体育(一)班", grouping_mode="administrative")
    session.add(section)
    session.flush()
    run = M.DailySyncRun(semester_id=sem.id, business_date=dt.date(2025, 11, 3),
                         status="success")
    session.add(run)
    session.flush()
    return sem, teacher, stu, section, run


def _class_session_fields(section, run, **overrides):
    """一节**合法**课次的字段（``period`` 缺省第 3 节，日期与 ``run.business_date`` 同一天）。"""
    fields = dict(course_section_id=section.id, session_date=dt.date(2025, 11, 3),
                  period=3, rpe_opened=True, rpe_token="A3F9K2QX", batch_id=run.id)
    fields.update(overrides)
    return fields


def _rpe_fields(cs, stu, **overrides):
    """一条**合法**课堂快评的字段。"""
    fields = dict(class_session_id=cs.id, student_id=stu.id, rpe=7,
                  submitted_at=dt.datetime(2025, 11, 3, 10, 35), elapsed_seconds=7.5)
    fields.update(overrides)
    return fields


def _training_log_fields(stu, run, **overrides):
    """一条**合法**打卡记录的字段。

    ⚠️ ``submitted_at`` 是 Plan 03 Task 5 加的那一列（NOT NULL、无缺省，
    理由见 :class:`app.db.models.feedback.TrainingLog` 的类 docstring），
    故本助手必须给值。这里取 ``log_date`` 那天的 **20:00**：与 ``late=False`` 自洽
    （20:00 < 22:00）、且日期与 ``log_date`` 一致（即「当天打的卡」，不是补卡）。
    """
    fields = dict(student_id=stu.id, log_date=dt.date(2025, 11, 3), completed=True,
                  submitted_at=dt.datetime(2025, 11, 3, 20, 0),
                  duration_min=42.5, feeling="moderate", is_rest_day=False, late=False,
                  source="demo", batch_id=run.id)
    fields.update(overrides)
    return fields


def _mini_test_fields(stu, sem, **overrides):
    """一条**合法**二次小测的字段（第 6 周 = 偶数周，spec §8.1「每两周」）。"""
    fields = dict(student_id=stu.id, semester_id=sem.id, week=6,
                  item_combo=["squat_30s", "shuttle_20m"], squat_30s_count=28,
                  shuttle_20m_s=34.2, normalized_score=71.5,
                  tested_on=dt.date(2025, 10, 13), entered_by="T2025001")
    fields.update(overrides)
    return fields


def _alert_fields(stu, sem, run, **overrides):
    """一条**合法**的**学生级**预警字段（``course_section_id`` 为 NULL）。

    ⚠️ ``subject_key`` 的算式**不在这里定义**：它的唯一所有者是 Task 6 的
    :mod:`app.domain.alerts`（本 Task 只建列与约束）。测试里按**字面量形状**现拼
    （``f"student:{stu.id}"``）而不是 import 一个常量——两侧同源的话，
    前缀写错也全绿（硬规矩 #35）。
    """
    fields = dict(student_id=stu.id, course_section_id=None, semester_id=sem.id,
                  subject_key=f"student:{stu.id}", level="red",
                  rule_id="RED_RPE_SUSTAINED",
                  trigger_snapshot={"streak": 3, "rpe": [9, 9, 10]},
                  triggered_at=dt.datetime(2025, 11, 3, 10, 30), status="pending",
                  batch_id=run.id, window_key="42")
    fields.update(overrides)
    return fields


def _class_alert_fields(section, sem, run, **overrides):
    """一条**合法**的**班级级**预警字段（``student_id`` 为 NULL，主语是教学班）。"""
    fields = dict(student_id=None, course_section_id=section.id, semester_id=sem.id,
                  subject_key=f"section:{section.id}", level="yellow",
                  rule_id="YELLOW_CLASS_RPE_HIGH",
                  trigger_snapshot={"mean_rpe": 7.8, "submitted": 31},
                  triggered_at=dt.datetime(2025, 11, 3, 10, 40), status="pending",
                  batch_id=run.id, window_key=f"{sem.id}:10")
    fields.update(overrides)
    return fields


def _weekly_report_fields(section, sem, run, **overrides):
    """一份**合法**班级周报的字段（5 个 JSON 列 + 1 个自由文本列）。"""
    fields = dict(course_section_id=section.id, semester_id=sem.id, week=10,
                  layer_distribution={"red": 4, "yellow": 18, "green": 12, "flow": {}},
                  rpe_summary={"mean": 6.4, "previous_mean": 6.1},
                  checkin_rate_by_layer={"red": 0.62, "yellow": 0.78, "green": 0.91},
                  progress_board={"up": [], "down": []},
                  alert_summary={"red": 1, "yellow": 3, "green": 2},
                  suggestion="红层完成率偏低，建议下周把红层训练日由 4 天调为 3 天。",
                  generated_at=dt.datetime(2025, 11, 9, 20, 0), batch_id=run.id)
    fields.update(overrides)
    return fields


def _notification_fields(stu, **overrides):
    """一条**合法**站内通知的字段（``alert_id`` / ``prescription_id`` 都可空）。"""
    fields = dict(recipient_kind="student", recipient_id=stu.id, channel="in_app",
                  title="打卡提醒", body="今日训练尚未打卡", alert_id=None,
                  prescription_id=None, is_read=False,
                  created_at=dt.datetime(2025, 11, 3, 19, 0))
    fields.update(overrides)
    return fields


#: 7 张新表的**列数**与**具名约束**（``UniqueConstraint`` + ``CheckConstraint``；
#: 主键与外键不列——外键总数由 :func:`test_sqlite_foreign_keys_are_enforced` 的
#: docstring 按运行时口径记，主键由 ``primary_key=True`` 那一列自己钉）。
#: ⚠️ 两个数都用运行时口径核过（``len(list(Model.__table__.columns))`` /
#: ``sorted(c.name for c in Model.__table__.constraints if c.name)``），不是数源码行数
#: （硬规矩 #89）。``alert`` 是 **14** 列：计划正文的 13 列 + 顶回 #2 加的 ``subject_key``。
#: ⚠️ ``training_log`` 自 **Plan 03 Task 5** 起是 **11** 列 / **3** 条具名约束
#: （Task 2 结案时是 10 / 2）：加了 ``submitted_at`` 那一列与 ``ck_training_log_source``
#: 那一条。两者的理由各写在 :class:`app.db.models.feedback.TrainingLog` 的类 docstring
#: 与 ``SOURCES`` 的注释里（前者是「没有它就实现不了 spec §8.1 自己要求的两件事」，
#: 后者是 P5-A3 兑现那一列注释里写下的「Task 5 落地时必须回来定这个值域并补 CHECK」）。
#: ⚠️ ``class_session`` 仍是 **7** 列：Task 5 只改了它两列的**可空性**与 ``rpe_token``
#: 的宽度来源（``String(16)`` → ``String(RPE_TOKEN_LEN)``），列数与约束都不变。
_PLAN03_TABLE_SHAPE = {
    "class_session": (7, ["uq_class_session_section_date_period"]),
    "rpe_record": (6, ["ck_rpe_record_rpe", "uq_rpe_record_session_student"]),
    "training_log": (11, ["ck_training_log_feeling", "ck_training_log_source",
                          "uq_training_log_student_day"]),
    "mini_test": (10, ["uq_mini_test_student_semester_week"]),
    "alert": (14, ["ck_alert_level", "ck_alert_status", "ck_alert_subject_is_exactly_one",
                   "uq_alert_rule_subject_semester_window"]),
    "notification": (10, ["ck_notification_channel", "ck_notification_recipient_kind"]),
    "weekly_class_report": (12, ["uq_weekly_class_report_section_semester_week"]),
}

_PLAN03_MODELS = (ClassSession, RpeRecord, TrainingLog, MiniTest,
                  Alert, Notification, WeeklyClassReport)


def test_the_seven_plan03_tables_have_the_documented_shape():
    """7 张新表的列数与具名约束**逐个点名**（本 Task 的「约束清单」断言）。

    列数与约束名一起断言，是因为它们各自抓一类不同的漏：少一列往往意味着 spec §4.5–§4.7
    的某个字段被漏掉（例如 ``rpe_record.elapsed_seconds``——spec §8.1 逐字「指导文件要求
    10 秒内完成」，没有它这句话就没有落点）；少一条约束则意味着一个本该由 DB 保证的
    不变量退化成「大家记得」（Review Focus 第 3 条的重复触发正是这一类）。

    ⚠️ **本条守不住什么**（硬规矩 #39）：它不判**列名**与**类型**对不对（列数相同、
    名字错了它全绿），也不判约束的**列序**。列名与类型逐列写在
    ``app/db/models/feedback.py`` 的 spec 对照表里，而列序由下面那几条行为测试
    （唯一约束真的拒收、CHECK 真的拒收）间接钉住。
    """
    models_by_table = {m.__tablename__: m for m in _PLAN03_MODELS}
    assert sorted(models_by_table) == sorted(_PLAN03_TABLE_SHAPE)
    offenders = []
    for table, (columns, constraints) in sorted(_PLAN03_TABLE_SHAPE.items()):
        model = models_by_table[table]
        got_columns = len(list(model.__table__.columns))
        if got_columns != columns:
            offenders.append(
                f"{table}: 列数 {got_columns}，期望 {columns}"
                f"（实到 {sorted(model.__table__.c.keys())}）"
            )
        got_constraints = sorted(
            c.name for c in model.__table__.constraints
            if c.name and type(c).__name__ in ("UniqueConstraint", "CheckConstraint")
        )
        if got_constraints != sorted(constraints):
            offenders.append(
                f"{table}: 具名约束 {got_constraints}，期望 {sorted(constraints)}"
            )
    assert offenders == [], "7 张新表的形状与文档不符：\n" + "\n".join(offenders)


def test_class_session_rejects_a_second_session_for_the_same_section_date_and_period(session):
    """同一个班、同一天、同一节次只能有一节课——由 **DB** 保证，不是靠写入方记得先查。

    ⚠️ **本条是顶回 #1 的落点**：计划正文给 ``rpe_record`` / ``training_log`` /
    ``mini_test`` / ``alert`` / ``weekly_class_report`` 都点了 ``UniqueConstraint``，
    **唯独漏了 ``class_session``**。而它正是 7 张里最需要的一条：

    1. :func:`app.demo_data.build_demo_feedback` 与 Task 5 的采集端点都按
       ``repo.upsert(session, ClassSession, ("course_section_id", "session_date", "period"), …)``
       写它，而 ``upsert`` 是**先 select 再 update/insert**：没有 DB 层的 UNIQUE 兜底时，
       两个写入方会各自 select 到「没有」、各自 insert 一行，而 ``upsert`` 下一次再
       select 就撞上 ``MultipleResultsFound``——**炸在离真因很远的读侧**；
    2. ``class_session`` 是 ``rpe_record`` 的父行。课次翻倍之后，「这节课的快评提交率」
       的分母（选课人数）对不上分子（挂在其中一个 ``class_session_id`` 上的提交数），
       而 spec §8.1 要求教师端「实时显示已提交/未提交名单」；
    3. ``class_session`` 带 ``batch_id``，而它**不得**进 ``_replay_cleanup``
       （``rpe_record`` 是用户实时写入的、重放不该删）——见 ``models/feedback.py`` 的
       模块 docstring。既然它的幂等手段只能是 upsert，那条 UNIQUE 就是它唯一的兜底。

    换个 ``period`` 就是另一节课（同一天第 3 节与第 5 节），本条同时把这一档钉住，
    免得约束被写成 ``(course_section_id, session_date)`` 而少一列。
    """
    _sem, _teacher, _stu, section, run = _feedback_context(session)
    session.add(ClassSession(**_class_session_fields(section, run)))
    session.flush()
    session.add(ClassSession(**_class_session_fields(section, run, rpe_opened=False,
                                                     rpe_token=None)))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    # ⚠️ SQLite 的 UNIQUE 报错**不带约束名**（它印的是列名），故约束名另从 DDL 反查
    assert ("UNIQUE constraint failed: class_session.course_section_id, "
            "class_session.session_date, class_session.period") in str(excinfo.value)
    session.rollback()

    _sem, _teacher, _stu, section, run = _feedback_context(session)
    uniques = {u["name"]: u["column_names"]
               for u in inspect(session.connection()).get_unique_constraints("class_session")}
    assert uniques["uq_class_session_section_date_period"] == [
        "course_section_id", "session_date", "period"
    ], uniques

    # 换节次是另一节课，换日期也是
    session.add(ClassSession(**_class_session_fields(section, run)))
    session.flush()
    session.add(ClassSession(**_class_session_fields(section, run, period=5)))
    session.flush()
    session.add(ClassSession(**_class_session_fields(
        section, run, session_date=dt.date(2025, 11, 10))))
    session.flush()
    assert session.scalar(select(func.count()).select_from(ClassSession)) == 3


def test_rpe_check_is_generated_from_the_class_constants(session):
    """``rpe BETWEEN 0 AND 10`` 的 **0 与 10 只有一个所有者**：:attr:`RpeRecord` 的类常量。

    P3-A5 实测坐实：:func:`app.db.models._shared._in_domain` 的签名是
    ``(column: str, allowed: Iterable[str], name: str)``——它**只吃字符串词表**，
    而 RPE 是整数区间，``ops.py`` 里也没有整数区间的先例，故这是**全库第一处手写的
    CHECK**。手写就是「同一事实写两遍」的形状，于是约束文本按 f-string 从类常量生成，
    与 ``_in_domain`` 的理由逐字同一条（「手写两遍迟早会漂移，而漂移是静默的」）。

    **为什么值域本身要钉成类常量而不是直接写进 DDL**：spec §8.2 的两条阈值都建立在
    这个值域上——``RED_RPE_SUSTAINED`` 是「连续 ≥ **9**」、``YELLOW_CLASS_RPE_HIGH`` 是
    「均值 > **7**」。若哪天有人把上界改成 100（百分制），那两条阈值会**静默失效**
    （再也触发不了），而全部测试仍然全绿。有了 ``RPE_MIN`` / ``RPE_MAX``，
    Task 6 的 ``alert_rules.yaml`` 校验就能拿它们当上界来验阈值。

    期望的 CHECK 文本**字面写死**（硬规矩 #35）：从类常量现拼一份来比就是同源。
    下面四段插入用的 rpe 值也一律是**字面量** 0 / 10 / -1 / 11，不读类常量。
    """
    assert RpeRecord.RPE_MIN == 0
    assert RpeRecord.RPE_MAX == 10
    checks = {c.name: str(c.sqltext) for c in RpeRecord.__table__.constraints
              if type(c).__name__ == "CheckConstraint"}
    assert checks["ck_rpe_record_rpe"] == "rpe BETWEEN 0 AND 10"
    # 类常量与 DDL 文本里的两个数**逐字对得上**（这一侧才允许读类常量：它验的正是
    # 「约束文本由类常量生成」这个动作，而不是「值域是什么」）
    assert str(RpeRecord.RPE_MIN) in checks["ck_rpe_record_rpe"]
    assert str(RpeRecord.RPE_MAX) in checks["ck_rpe_record_rpe"]

    # 两个端点都**放行**（闭区间：0 与 10 都是合法的主观疲劳值）；越界一律拒收，
    # 且报的是那条 CHECK 的名字
    for rpe, allowed in ((0, True), (10, True), (-1, False), (11, False)):
        session.rollback()
        _sem, _teacher, stu, section, run = _feedback_context(session)
        cs = ClassSession(**_class_session_fields(section, run))
        session.add(cs)
        session.flush()
        session.add(RpeRecord(**_rpe_fields(cs, stu, rpe=rpe)))
        if allowed:
            session.flush()
            assert session.scalar(select(func.count()).select_from(RpeRecord)) == 1, rpe
        else:
            with pytest.raises(IntegrityError) as excinfo:
                session.flush()
            assert "ck_rpe_record_rpe" in str(excinfo.value), (rpe, str(excinfo.value))


def test_rpe_record_is_unique_per_session_and_student(session):
    """一节课上同一个学生只能有一条快评（spec §8.1：滑块打分 → 提交，一次）。

    没有它，学生连点两次「提交」就会让「课堂 RPE 均值」（``YELLOW_CLASS_RPE_HIGH``
    的输入）被同一个人算两遍，而教师端「已提交/未提交名单」也会显示 101%。
    """
    _sem, _teacher, stu, section, run = _feedback_context(session)
    cs = ClassSession(**_class_session_fields(section, run))
    session.add(cs)
    session.flush()
    session.add(RpeRecord(**_rpe_fields(cs, stu)))
    session.flush()
    session.add(RpeRecord(**_rpe_fields(cs, stu, rpe=9, elapsed_seconds=11.25,
                                        submitted_at=dt.datetime(2025, 11, 3, 10, 36))))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert ("UNIQUE constraint failed: rpe_record.class_session_id, "
            "rpe_record.student_id") in str(excinfo.value)
    session.rollback()

    _sem, _teacher, stu, section, run = _feedback_context(session)
    uniques = {u["name"]: u["column_names"]
               for u in inspect(session.connection()).get_unique_constraints("rpe_record")}
    assert uniques["uq_rpe_record_session_student"] == ["class_session_id", "student_id"], uniques
    # elapsed_seconds 可空且无缺省：spec §8.1 的「10 秒内完成」要有落点，而「没量到」
    # 与「量到 0 秒」不是一回事（包约定 1：缺测就是 NULL）
    assert RpeRecord.__table__.c.elapsed_seconds.nullable is True
    assert RpeRecord.__table__.c.elapsed_seconds.default is None


def test_training_log_feeling_domain_and_one_row_per_student_per_day(session):
    """``feeling`` 的三值词表（spec §8.1「轻松/适中/吃力」）+ ``(student_id, log_date)`` 唯一。

    唯一约束是「完成率是 RCT 关键过程指标，必须严格」（spec §8.1 逐字）的**机制**那一半：
    一天两行会让分母（应打卡天数）与分子（完成天数）各说各话，而
    ``YELLOW_CHECKIN_GAP``（打卡中断 2 天）读的正是这张表。
    """
    assert TrainingLog.FEELINGS == {"easy", "moderate", "hard"}
    checks = {c.name: str(c.sqltext) for c in TrainingLog.__table__.constraints
              if type(c).__name__ == "CheckConstraint"}
    assert checks["ck_training_log_feeling"] == "feeling IN ('easy', 'hard', 'moderate')"

    # 同一天第二行 → 拒收
    _sem, _teacher, stu, _section, run = _feedback_context(session)
    session.add(TrainingLog(**_training_log_fields(stu, run)))
    session.flush()
    session.add(TrainingLog(**_training_log_fields(stu, run, feeling="hard")))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert ("UNIQUE constraint failed: training_log.student_id, "
            "training_log.log_date") in str(excinfo.value)
    session.rollback()

    # 词表外的值 → 拒收（中文的「轻松」也不行：值域是三个英文 token）
    _sem, _teacher, stu, _section, run = _feedback_context(session)
    session.add(TrainingLog(**_training_log_fields(stu, run, feeling="轻松")))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "ck_training_log_feeling" in str(excinfo.value)
    session.rollback()

    # ``feeling`` 可空：没打卡就没有感受（包约定 1，缺测是 NULL 不是 0/""）
    _sem, _teacher, stu, _section, run = _feedback_context(session)
    session.add(TrainingLog(**_training_log_fields(
        stu, run, feeling=None, completed=False, duration_min=None)))
    session.flush()
    assert session.scalar(select(func.count()).select_from(TrainingLog)) == 1
    # 换一天就是另一行
    session.add(TrainingLog(**_training_log_fields(stu, run, log_date=dt.date(2025, 11, 4))))
    session.flush()
    assert session.scalar(select(func.count()).select_from(TrainingLog)) == 2


def test_mini_test_is_unique_per_student_semester_week(session):
    """二次小测每两周一次，故 ``(student_id, semester_id, week)`` 唯一（spec §8.1）。

    ``RED_MINITEST_DROP`` 的判据是「连续两次下降 ≥ 5%」，需要 **3 个数据点**
    （spec §8.2 的补齐口径 #2）。同一周多出一行，那三个点就会错位成
    「同一周自己跟自己比」，而它是**静默**的：得分都在、都合法，只是趋势算错了。
    """
    _sem, _teacher, stu, _section, _run = _feedback_context(session)
    session.add(MiniTest(**_mini_test_fields(stu, _sem)))
    session.flush()
    session.add(MiniTest(**_mini_test_fields(stu, _sem, squat_30s_count=30)))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert ("UNIQUE constraint failed: mini_test.student_id, mini_test.semester_id, "
            "mini_test.week") in str(excinfo.value)
    session.rollback()

    _sem, _teacher, stu, _section, _run = _feedback_context(session)
    uniques = {u["name"]: u["column_names"]
               for u in inspect(session.connection()).get_unique_constraints("mini_test")}
    assert uniques["uq_mini_test_student_semester_week"] == [
        "student_id", "semester_id", "week"
    ], uniques

    # item_combo 走 JsonText：读回来是**原样的 list**，不是字符串（包约定 3）
    session.add(MiniTest(**_mini_test_fields(stu, _sem)))
    session.flush()
    session.expire_all()
    got = session.scalar(select(MiniTest))
    assert got.item_combo == ["squat_30s", "shuttle_20m"]
    assert isinstance(got.item_combo, list)
    # 三个测量列都可空且无缺省（包约定 1：缺测就是 NULL）
    for name in ("squat_30s_count", "shuttle_20m_s", "normalized_score"):
        assert MiniTest.__table__.c[name].nullable is True, name
        assert MiniTest.__table__.c[name].default is None, name


def test_alert_dedup_binds_for_both_student_and_class_scope(session):
    """Review Focus 第 3 条的 **DB 那一半**：同一次触发只有一条 ``alert``，两种作用域都要。

    计划正文的去重键是 ``(rule_id, student_id, course_section_id, semester_id, window_key)``，
    并裁定「两列都改成 ``nullable=False`` + 用 ``0`` 作哨兵」，理由是 SQLite 的 UNIQUE 对
    NULL 是「NULL ≠ NULL」，两列可空会让约束对班级级预警**静默失效**。
    **那个诊断是对的，但开的方子撞在另一堵墙上**：这两列在计划的 Interfaces 里都是外键，
    而 SQLite 跑在 ``PRAGMA foreign_keys=ON`` 下（Ruling 27 的钩子挂在 ``Engine`` **类**上），
    于是「父表里没有 id = 0 的那一行」会让**每一条**哨兵行当场
    ``IntegrityError: FOREIGN KEY constraint failed``——见
    :func:`test_alert_subject_sentinel_zero_would_violate_the_fk`（探针
    ``t2_probes/p01_sentinel_fk.py`` 亲跑过最小复现）。

    **顶回 #2 的替代方案**：两个外键列**保持可空**（完整性不丢），另加一个 NOT NULL 的
    ``subject_key``（学生级 ``student:<id>``、班级级 ``section:<id>``），去重键改成
    ``(rule_id, subject_key, semester_id, window_key)``——四列全 NOT NULL，
    于是 UNIQUE 对两种作用域**都真的生效**。这与 ``CleaningLog`` 的
    ``student_no``（非空、逐字照抄）+ ``student_id``（可空外键）双列承载（Ruling 25）
    是同一个形状：**真的外键留可空，另配一个 NOT NULL 的伴随列去承担约束**。
    代价是多一列、且它与那两个外键**冗余**（可由它们推出）；换来的是完整性与去重同时成立。

    ``window_key`` 让「下一轮再触发」是一条新行而不是撞约束：
    ``RED_RPE_SUSTAINED`` 用第 3 次快评的 ``class_session_id``、``YELLOW_CLASS_RPE_HIGH``
    用 ``semester_id:week``（五种算式归 Task 6 的 :mod:`app.domain.alerts`）。
    """
    # ① 学生级：同 rule + 同 subject + 同 window 插第二次必须被拒收
    _sem, _teacher, stu, section, run = _feedback_context(session)
    session.add(Alert(**_alert_fields(stu, _sem, run)))
    session.flush()
    session.add(Alert(**_alert_fields(stu, _sem, run,
                                      triggered_at=dt.datetime(2025, 11, 3, 11, 0))))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert ("UNIQUE constraint failed: alert.rule_id, alert.subject_key, "
            "alert.semester_id, alert.window_key") in str(excinfo.value)
    session.rollback()

    _sem, _teacher, stu, section, run = _feedback_context(session)
    uniques = {u["name"]: u["column_names"]
               for u in inspect(session.connection()).get_unique_constraints("alert")}
    assert uniques["uq_alert_rule_subject_semester_window"] == [
        "rule_id", "subject_key", "semester_id", "window_key"
    ], uniques

    # ② 换一个 window_key 就是**下一轮**触发，必须放行（否则「连续第 4、5 次」记不下痕迹）
    session.add(Alert(**_alert_fields(stu, _sem, run, window_key="42")))
    session.flush()
    session.add(Alert(**_alert_fields(stu, _sem, run, window_key="43")))
    session.flush()
    assert session.scalar(select(func.count()).select_from(Alert)) == 2
    session.rollback()

    # ③ 班级级预警（``student_id`` 为 NULL）同样被去重约束抓住——这正是哨兵方案要解决、
    #    而 ``subject_key`` 方案真的解决了的那一档
    _sem, _teacher, stu, section, run = _feedback_context(session)
    session.add(Alert(**_class_alert_fields(section, _sem, run)))
    session.flush()
    session.add(Alert(**_class_alert_fields(section, _sem, run,
                                            triggered_at=dt.datetime(2025, 11, 3, 12, 0))))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "UNIQUE constraint failed: alert.rule_id" in str(excinfo.value)
    session.rollback()

    # ④ **只有 ``subject_key`` 不同**的两条必须能共存：rule_id / semester_id / window_key
    #    三列逐字相同，一条学生级、一条班级级。这一段才是「去重键对两种作用域都成立」的
    #    正面证据——若去重键里用的是那两个可空外键，第 ③ 段那两行会**都插进去**。
    _sem, _teacher, stu, section, run = _feedback_context(session)
    shared = dict(rule_id="YELLOW_CLASS_RPE_HIGH", semester_id=_sem.id,
                  window_key=f"{_sem.id}:10")
    session.add(Alert(**_alert_fields(stu, _sem, run, level="yellow", **shared)))
    session.flush()
    session.add(Alert(**_class_alert_fields(section, _sem, run, **shared)))
    session.flush()
    assert session.scalar(select(func.count()).select_from(Alert)) == 2
    # 而第三条（与班级级那条完全同键）仍然被拒收
    session.add(Alert(**_class_alert_fields(section, _sem, run, **shared)))
    with pytest.raises(IntegrityError):
        session.flush()


def test_alert_subject_is_exactly_one_of_student_or_section(session):
    """``ck_alert_subject_is_exactly_one``：两个作用域列**恰好一个**非空。

    这条 CHECK 是 ``subject_key`` 那套设计的前提守卫：``subject_key`` 由两个可空外键推出，
    而「两个都填」与「两个都不填」都让它无从定义——前者是一条既属于某个学生又属于某个班的
    预警（去重键于是有两个主语），后者是一条**谁都不属于**的预警（大屏上永远查不到它）。
    两种都是静默的：行照样插得进去，只是 Task 6 的规则求值会读到一个没有主语的对象。

    ⚠️ 它**守不住**「``subject_key`` 与非空的那一列一致」（硬规矩 #39）：
    ``student_id = 7`` 而 ``subject_key = "section:3"`` 在库层面放行。那半边由 Task 6/7
    的写入方负责——``subject_key`` 的算式只有 :mod:`app.domain.alerts` 一个所有者，
    本 Task 刻意不在 SQL 里再拼一次前缀（那会是第二个所有者）。
    """
    # 两个都填 → 拒收
    _sem, _teacher, stu, section, run = _feedback_context(session)
    session.add(Alert(**_alert_fields(stu, _sem, run, course_section_id=section.id)))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "ck_alert_subject_is_exactly_one" in str(excinfo.value)
    session.rollback()

    # 两个都不填 → 拒收
    _sem, _teacher, stu, section, run = _feedback_context(session)
    session.add(Alert(**_alert_fields(stu, _sem, run, student_id=None,
                                      subject_key="student:")))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "ck_alert_subject_is_exactly_one" in str(excinfo.value)
    session.rollback()

    # 两个作用域列都**可空**（哨兵方案在这里不可行，见下一条测试），
    # 而去重键的那四列一个都不可空——否则 UNIQUE 对 NULL 就是「NULL ≠ NULL」
    assert Alert.__table__.c.student_id.nullable is True
    assert Alert.__table__.c.course_section_id.nullable is True
    for name in ("rule_id", "subject_key", "semester_id", "window_key"):
        assert Alert.__table__.c[name].nullable is False, f"alert.{name} 不许为空"


def test_alert_subject_sentinel_zero_would_violate_the_fk(session):
    """**反证**：计划正文那个「``nullable=False`` + 用 ``0`` 作哨兵」的方案在本库跑不起来。

    留着这一条是为了让「为什么不用哨兵 0」有一个**可执行**的答案，而不是一段只有
    读过 Plan 03 账本才看得懂的散文。失效形态很具体：``alert.student_id`` 与
    ``alert.course_section_id`` 都是外键，而 ``app/db/session.py`` 的
    ``_sqlite_foreign_keys_on`` 钩子挂在 ``Engine`` **类**上（Ruling 27），
    故 ``PRAGMA foreign_keys`` 对测试的内存库同样是 1；父表里没有 ``id = 0`` 的行
    （SQLite 的 rowid 从 1 起），子表写 0 就是当场
    ``IntegrityError: FOREIGN KEY constraint failed``。

    ⚠️ 于是「让去重约束对班级级预警生效」与「保住外键完整性」在哨兵方案下**不可兼得**，
    而 Review Focus 第 4 条（删除连带）恰恰要求外键是**真的**在强制。
    最小复现见探针 ``t2_probes/p01_sentinel_fk.py``（一张父表 + 一张 NOT NULL 外键子表，
    写 0 → 拒收）。

    ⚠️ **哨兵方案在本表上还撞第二堵墙**：它要求两列都 NOT NULL（一列填真 id、另一列填 0），
    于是 ``ck_alert_subject_is_exactly_one``（两列**恰好一个**非空）也会拒收每一条。
    为把「外键那一撞」单独取出来，本条让另一列保持 ``NULL``——这样 XOR 那条 CHECK
    是满足的，报错只可能来自外键。
    """
    _sem, _teacher, stu, section, run = _feedback_context(session)
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1
    assert min(stu.id, section.id) >= 1, "SQLite 的 rowid 从 1 起，故 0 不可能是合法父键"

    # 哨兵 0 当 student_id（另一列保持 NULL，好让 XOR 那条 CHECK 不参与）
    session.add(Alert(**_alert_fields(stu, _sem, run, student_id=0)))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "FOREIGN KEY constraint failed" in str(excinfo.value), str(excinfo.value)
    session.rollback()

    # 哨兵 0 当 course_section_id（同上）
    _sem, _teacher, stu, section, run = _feedback_context(session)
    session.add(Alert(**_class_alert_fields(section, _sem, run, course_section_id=0)))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "FOREIGN KEY constraint failed" in str(excinfo.value), str(excinfo.value)
    session.rollback()

    # 第二堵墙：哨兵方案要求的「两列都非空」被 XOR 那条 CHECK 拒收，
    # 且报的是 CHECK 的名字而不是外键——两道约束各挡一半，谁都绕不过去
    _sem, _teacher, stu, section, run = _feedback_context(session)
    session.add(Alert(**_class_alert_fields(section, _sem, run, student_id=0)))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "ck_alert_subject_is_exactly_one" in str(excinfo.value), str(excinfo.value)


def test_alert_level_and_status_domains(session):
    """``level`` ∈ {red, yellow, green}、``status`` ∈ {pending, handled, ignored}（spec §4.6）。

    两个值域都按包约定 2「类常量 + ``_in_domain``」两处设防，期望文本字面写死。
    ``status`` 的三值是 Review Focus 第 3 条「同一学生 + 同一规则 + 同一**未处理**状态
    只有一条活跃 alert」那个口径的落点：``handled`` / ``ignored`` 让教师处置过的预警
    留在库里当痕迹，而不是被删掉——删掉之后「这一条为什么没有再触发」就无从回答。
    """
    assert Alert.LEVELS == {"red", "yellow", "green"}
    assert Alert.STATUSES == {"pending", "handled", "ignored"}
    checks = {c.name: str(c.sqltext) for c in Alert.__table__.constraints
              if type(c).__name__ == "CheckConstraint"}
    assert checks["ck_alert_level"] == "level IN ('green', 'red', 'yellow')"
    assert checks["ck_alert_status"] == "status IN ('handled', 'ignored', 'pending')"

    _sem, _teacher, stu, section, run = _feedback_context(session)
    session.add(Alert(**_alert_fields(stu, _sem, run, level="🔴")))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "ck_alert_level" in str(excinfo.value)
    session.rollback()

    _sem, _teacher, stu, section, run = _feedback_context(session)
    session.add(Alert(**_alert_fields(stu, _sem, run, status="done")))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "ck_alert_status" in str(excinfo.value)
    session.rollback()

    # 处置列在处置之前本来就没有值（可空、无缺省）
    _sem, _teacher, stu, section, run = _feedback_context(session)
    for name in ("handled_action", "handled_at"):
        assert Alert.__table__.c[name].nullable is True, name
        assert Alert.__table__.c[name].default is None, name
    session.add(Alert(**_alert_fields(stu, _sem, run)))
    session.flush()
    session.expire_all()
    got = session.scalar(select(Alert))
    assert got.status == "pending" and got.handled_at is None and got.handled_action is None
    assert got.trigger_snapshot == {"streak": 3, "rpe": [9, 9, 10]}, "快照走 JsonText"


def test_notification_alert_id_and_prescription_id_are_set_null_on_delete(session):
    """两个可空外键都带 ``ondelete="SET NULL"``：删父行时通知**留在库里**、只是断开关联。

    ``alert_id`` 的那一半是计划正文的显式决定：**Plan 03 Task 7 已把 ``Alert`` 加进
    :func:`app.pipeline.daily._replay_cleanup`**，而 ``notification`` **不带** ``batch_id``、
    不进那份清单——重放删掉 alert 时，若这一列是普通外键，
    ``DELETE FROM alert`` 会当场 ``FOREIGN KEY constraint failed``（``PRAGMA foreign_keys=ON``），
    整批回滚；若改成 ``CASCADE``，则会连带删掉**已经推给某人的站内消息**
    （消息中心的红点凭空消失，而学生不知道自己收到过什么）。

    ⚠️ **``prescription_id`` 的那一半是顶回 #3**：计划只点了 ``alert_id``，
    而 ``prescription`` **今天就已经在** ``_replay_cleanup`` 的清单里
    （Plan 02 Task 7，P7-A4），故「重放那天删掉处方」不是 Task 8 才会发生的事、
    **是现在每天都在发生的事**。少了 ``SET NULL``，第一条指向处方的通知一落库，
    下一次重放同一天就会当场炸在 ``delete_by_batch(session, Prescription, …)`` 上——
    而 Plan 02 的既有测试全绿，因为它们一条 ``notification`` 都不写。

    ``SET NULL`` 是三个选项里唯一同时满足「重放不炸」与「消息不丢」的那个。
    代价：断开关联的通知再也点不回原处方（前端应把 ``prescription_id IS NULL``
    渲染成不可点的纯文本），已登记为关切。
    """
    from sqlalchemy.dialects import sqlite
    from sqlalchemy.schema import CreateTable

    # ① DDL 侧：两个 ``ON DELETE SET NULL`` 真的被渲染进建表语句（不读模型自己的
    #    ``fk.ondelete`` 声明——那一侧与被测的列声明同源，硬规矩 #35）
    ddl = str(CreateTable(Notification.__table__).compile(dialect=sqlite.dialect()))
    assert ddl.count("ON DELETE SET NULL") == 2, ddl

    # ② 行为侧：删 alert，通知留下、alert_id 变 NULL
    _sem, _teacher, stu, section, run = _feedback_context(session)
    alert = Alert(**_alert_fields(stu, _sem, run))
    session.add(alert)
    session.flush()
    note = Notification(**_notification_fields(
        stu, title="连续三次课堂快评 RPE ≥ 9", body="建议本周减量 20%",
        alert_id=alert.id, created_at=dt.datetime(2025, 11, 3, 10, 31)))
    session.add(note)
    session.flush()
    session.commit()
    note_id = note.id

    session.delete(alert)
    session.flush()
    session.commit()
    session.expire_all()

    assert session.scalar(select(func.count()).select_from(Alert)) == 0
    got = session.get(Notification, note_id)
    assert got is not None, "删预警不得连带删掉已经推出去的通知"
    assert got.alert_id is None
    assert got.title == "连续三次课堂快评 RPE ≥ 9"

    # ③ 行为侧：删 prescription，通知同样留下（顶回 #3 的那一半）。
    #    这一段照 ``_replay_cleanup`` 的真实写法走 ``repo.delete_by_batch``，
    #    而不是 ORM 的 ``session.delete``——那才是重放那天真的会执行的语句。
    #    ⚠️ **不重新调 :func:`_feedback_context`**：上面那一段已经 ``commit()`` 过，
    #    学期行真的在库里了，再建一个同名学期会撞 ``uq_semester_name``。
    #    故复用同一个 ``stu`` / ``run``（``_prescription_fields`` 只需要这两样）。
    rx = Prescription(**_prescription_fields(stu, run))
    session.add(rx)
    session.flush()
    note2 = Notification(**_notification_fields(
        stu, title="本周训练单已更新", body="第 2 周减量 20%", prescription_id=rx.id,
        created_at=dt.datetime(2026, 3, 2, 8, 5)))
    session.add(note2)
    session.flush()
    session.commit()
    note2_id = note2.id

    assert delete_by_batch(session, Prescription, run.id) == 1
    session.commit()
    session.expire_all()
    got2 = session.get(Notification, note2_id)
    assert got2 is not None and got2.prescription_id is None


def test_notification_domains_and_the_read_flag_default(session):
    """``recipient_kind`` / ``channel`` 两个词表 + ``is_read`` 缺省 ``False``。

    ``channel`` 的三值照 spec §8.3 的 ``NotificationChannel`` 三实现（``InAppChannel`` /
    微信订阅消息 / 短信）。**本计划只做 ``in_app``**，另两个值今天没有写入方——
    与 ``WeeklyAdjustment.SOURCES`` 的 ``"auto"`` 同一条理由：届时往一个已结案的 CHECK
    里加值等于重建库（本仓不做迁移）。

    ``recipient_id`` **不是外键**：它是多态的（``recipient_kind = "student"`` 时指
    ``student.id``、``"teacher"`` 时指 ``teacher.id``），而 SQLite 没有跨两张父表的
    外键写法。代价是「删学生不会带走他的通知」，已登记为关切（Task 3 的删除策略要
    显式声明这一档）。

    ``is_read`` NOT NULL + ``default=False``：红点与消息中心都读它，而「没写」与「未读」
    对前端是同一件事，故给缺省而不是留 NULL（与 ``DailySyncRun`` 计数列 ``default=0``
    同一条理由：0/False 比 NULL 更诚实）。
    """
    assert Notification.RECIPIENT_KINDS == {"student", "teacher"}
    assert Notification.CHANNELS == {"in_app", "wechat_subscribe", "sms"}
    checks = {c.name: str(c.sqltext) for c in Notification.__table__.constraints
              if type(c).__name__ == "CheckConstraint"}
    assert checks["ck_notification_recipient_kind"] == "recipient_kind IN ('student', 'teacher')"
    assert checks["ck_notification_channel"] == (
        "channel IN ('in_app', 'sms', 'wechat_subscribe')"
    )

    column = Notification.__table__.c.is_read
    assert column.nullable is False
    assert column.default.arg is False

    # recipient_id 刻意不是外键（多态接收者）；另两个可空外键各指一张表
    assert len(Notification.__table__.c.recipient_id.foreign_keys) == 0
    assert [fk.target_fullname for fk in Notification.__table__.c.alert_id.foreign_keys] == [
        "alert.id"
    ]
    assert [fk.target_fullname
            for fk in Notification.__table__.c.prescription_id.foreign_keys] == [
        "prescription.id"
    ]
    # notification 刻意**不带** batch_id（用户实时写入），见
    # :func:`test_the_three_user_written_tables_have_no_batch_id`
    assert "batch_id" not in set(Notification.__table__.c.keys())

    _sem, _teacher, stu, _section, _run = _feedback_context(session)
    session.add(Notification(**_notification_fields(stu)))
    session.flush()
    session.expire_all()
    got = session.scalar(select(Notification))
    assert got.is_read is False, "缺省必须落 False，不是 NULL"
    assert got.alert_id is None and got.prescription_id is None

    # 词表外的值一律拒收
    session.rollback()
    _sem, _teacher, stu, _section, _run = _feedback_context(session)
    session.add(Notification(**_notification_fields(stu, channel="email")))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "ck_notification_channel" in str(excinfo.value)
    session.rollback()

    _sem, _teacher, stu, _section, _run = _feedback_context(session)
    session.add(Notification(**_notification_fields(stu, recipient_kind="parent")))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "ck_notification_recipient_kind" in str(excinfo.value)


def test_weekly_class_report_is_unique_per_section_semester_week(session):
    """``(course_section_id, semester_id, week)`` 唯一：一个班一周只有一份周报（spec §8.5）。

    周报的 5 个 JSON 列都是**当周的聚合快照**，同一周两份会让「环比流动」
    （``layer_distribution``）与「人均 RPE 与上周对比」（``rpe_summary``）有两个互相矛盾的
    基准，而教师大屏读的是「最新那一份」——于是哪一份生效取决于 ``id`` 的先后，
    那是一个没人会去查的静默不一致。
    """
    _sem, _teacher, _stu, section, run = _feedback_context(session)
    session.add(WeeklyClassReport(**_weekly_report_fields(section, _sem, run)))
    session.flush()
    session.add(WeeklyClassReport(**_weekly_report_fields(
        section, _sem, run, generated_at=dt.datetime(2025, 11, 9, 21, 0))))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert ("UNIQUE constraint failed: weekly_class_report.course_section_id, "
            "weekly_class_report.semester_id, weekly_class_report.week") in str(excinfo.value)
    session.rollback()

    _sem, _teacher, _stu, section, run = _feedback_context(session)
    uniques = {
        u["name"]: u["column_names"]
        for u in inspect(session.connection()).get_unique_constraints("weekly_class_report")
    }
    assert uniques["uq_weekly_class_report_section_semester_week"] == [
        "course_section_id", "semester_id", "week"
    ], uniques

    # 5 个 JSON 列读回来都是原样的 dict（包约定 3；``suggestion`` 是自由文本、不是 JSON）
    session.add(WeeklyClassReport(**_weekly_report_fields(section, _sem, run)))
    session.flush()
    session.expire_all()
    got = session.scalar(select(WeeklyClassReport))
    assert got.layer_distribution == {"red": 4, "yellow": 18, "green": 12, "flow": {}}
    assert got.rpe_summary == {"mean": 6.4, "previous_mean": 6.1}
    assert got.checkin_rate_by_layer == {"red": 0.62, "yellow": 0.78, "green": 0.91}
    assert got.progress_board == {"up": [], "down": []}
    assert got.alert_summary == {"red": 1, "yellow": 3, "green": 2}
    assert isinstance(got.suggestion, str) and got.suggestion.startswith("红层完成率偏低")
    # 换一周就是另一份
    session.add(WeeklyClassReport(**_weekly_report_fields(section, _sem, run, week=11)))
    session.flush()
    assert session.scalar(select(func.count()).select_from(WeeklyClassReport)) == 2


def test_weekly_adjustment_rejects_a_duplicate_week_reason_source(session):
    """**S2 / P3-A4**：同一处方 + 同一周 + 同一原因 + 同一来源，第二次 INSERT 被 DB 拒收。

    这是 Review Focus 第 3 条（重复触发不得把训练量连乘成 ``0.8³ = 0.512``）的
    **DB 层那一半**；应用层那一半是 Task 7 的 ``window_key``。两半各挡一条路径：
    ``alert`` 的唯一约束挡「同一次触发生成两条预警」，本条挡「同一条预警写两次减量」。
    少了本条，``app/pipeline/alert_stage.py``（Task 7）只要在某一天跑了两遍，
    「本周训练单」= ``骨架第 N 周 × 该周全部 factor`` 的**累乘**就会把那一周再打一次八折，
    而全程不报错——``app/pipeline/daily.py`` 的 ``_replay_cleanup`` docstring
    逐字描述过这个失效形态（当时 ``weekly_adjustment`` 「没有任何唯一约束」）。

    ⚠️ **本 Task 只保证约束在、不建 upsert 路径**（P3-A4）：Plan 02 的
    ``weekly_factors_of`` 是只读的，写入方是 Task 7。届时 ``repo.upsert`` 的
    ``key_fields`` 应当就是这四个列。

    ⚠️ **换 ``reason`` 就是另一条**，这是**刻意**的：同一周上叠多条微调是本表的设计语义
    （教师先减 20%、再因天气减 10%，``0.8 × 0.9 = 0.72``），故约束不能只按
    ``(prescription_id, week)``——那样第二次合法的微调就插不进去了。
    """
    def _adjustment_fields(rx, run, **overrides):
        fields = dict(prescription_id=rx.id, batch_id=run.id, week=2, factor=0.8,
                      reason="RED_RPE_SUSTAINED：连续三次 RPE ≥ 9，减量 20%",
                      source="auto", created_at=dt.datetime(2026, 3, 9, 8, 0))
        fields.update(overrides)
        return fields

    stu, run = _prescription_context(session)
    rx = Prescription(**_prescription_fields(stu, run))
    session.add(rx)
    session.flush()
    session.add(WeeklyAdjustment(**_adjustment_fields(rx, run)))
    session.flush()
    session.add(WeeklyAdjustment(**_adjustment_fields(
        rx, run, created_at=dt.datetime(2026, 3, 9, 9, 0))))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert ("UNIQUE constraint failed: weekly_adjustment.prescription_id, "
            "weekly_adjustment.week, weekly_adjustment.reason, "
            "weekly_adjustment.source") in str(excinfo.value)
    session.rollback()

    stu, run = _prescription_context(session)
    uniques = {
        u["name"]: u["column_names"]
        for u in inspect(session.connection()).get_unique_constraints("weekly_adjustment")
    }
    assert uniques["uq_weekly_adjustment_prescription_week_reason_source"] == [
        "prescription_id", "week", "reason", "source"
    ], uniques

    # 换 reason（连带换 source 与 factor）/ 换 week 都是**另一条**（累乘语义）
    rx = Prescription(**_prescription_fields(stu, run))
    session.add(rx)
    session.flush()
    session.add(WeeklyAdjustment(**_adjustment_fields(rx, run)))
    session.flush()
    session.add(WeeklyAdjustment(**_adjustment_fields(
        rx, run, reason="本周月考，减量", source="teacher", factor=0.9)))
    session.flush()
    session.add(WeeklyAdjustment(**_adjustment_fields(rx, run, week=3)))
    session.flush()
    assert session.scalar(select(func.count()).select_from(WeeklyAdjustment)) == 3


def test_the_unconstrained_string_columns_of_the_plan03_tables_are_wide_enough():
    """Plan 03 那几张表里**列宽必须对字面量钉住**的 6 个 ``String(n)`` 列（硬规矩 #18 的补位）。

    :func:`test_string_column_widths_fit_their_value_domains` 从 ``_in_domain`` 生成的
    约束文本反解取值域，故它**只看得见带 CHECK 的列**（Plan02 账本 P2-A5 / P3-A5），
    而且它只判**够宽**（``width >= len(longest)``）、不判「不许改窄」。
    本条补上两格：① Plan 03 那 5 个没有封闭词表的列（Task 5 之后是 5 个：
    ``training_log.source`` 按 P5-A3 补了 CHECK、移到上面那条遍历里去了）；
    ② ``training_log.source`` 的**列宽本身**仍留在这里钉（防改窄）。
    两侧都写**字面量**（不是互相比，互相比的话两列一起变窄也全绿），
    照 ``test_prescription_template_ref_column_is_as_wide_as_the_template_table_one``
    的既有形状。

    ⚠️ SQLite **不强制** ``VARCHAR`` 长度，故溢出在本仓的测试里永远不报错；换
    MySQL / PostgreSQL 会静默截断，而炸点在读侧、离真因隔一整个批处理周期
    （Ruling 144 的 ``derived_metrics.trend`` 就是这样漏了 7 个任务）。
    ⚠️ ``class_session.rpe_token`` 那一格尤其如此：它一旦在严格长度的后端被截断，
    症状是**课堂快评的口令校验永远失败**（学生交的 token 与库里被截短的对不上），
    而那看起来像「学生输错了口令」。
    """
    # ① alert.rule_id ← spec §8.2 那 5 个规则 ID（唯一所有者是 data/alert_rules.yaml，
    #    Task 6 落地；本条只钉「最长的那个塞得下」）
    longest_rule_id = "YELLOW_CLASS_RPE_HIGH"
    assert len(longest_rule_id) == 21
    assert Alert.__table__.c.rule_id.type.length == 32
    assert len(longest_rule_id) <= Alert.__table__.c.rule_id.type.length

    # ② alert.window_key ← Task 6 那五种算式里最长的一种（``semester_id:week``）
    longest_window_key = "2147483647:16"
    assert len(longest_window_key) == 13
    assert Alert.__table__.c.window_key.type.length == 32
    assert len(longest_window_key) <= Alert.__table__.c.window_key.type.length

    # ③ alert.subject_key ← ``section:<id>`` 比 ``student:<id>`` 短一个字符，故取前者
    longest_subject_key = "section:2147483647"
    assert len(longest_subject_key) == 18
    assert Alert.__table__.c.subject_key.type.length == 24
    assert len(longest_subject_key) <= Alert.__table__.c.subject_key.type.length

    # ④ class_session.rpe_token ← 课堂快评口令，**两个写入方、两种长度**。
    #    ⚠️ 本处此前印的是「演示与 Task 5 都用 8 位大写字母数字」（字面量 "A3F9K2QX"）：
    #    演示侧（``app/demo_data.py``）确实仍是 8 位大写十六进制，而 **Task 5 的采集端点
    #    生成的是 ``secrets.token_urlsafe(RPE_TOKEN_LEN * 3 // 4)[:RPE_TOKEN_LEN]``**
    #    ——base64url 字母表（大小写混排 + ``-`` / ``_``）、长度**恰好等于列宽 16**。
    #    故「最长真实值」是 16 而不是 8，「余量 8」已经不成立（余量 0），按实际口径改写。
    #    ⚠️ 两侧不同源（硬规矩 #35）：这个串是**手写**的、不读 ``RPE_TOKEN_LEN``，
    #    于是「有人把列改窄」会让下面第 3 行断言红（而不是两个值一起变、恒成立）。
    longest_rpe_token = "aB3-_xY9kL2mNpQr"
    assert len(longest_rpe_token) == 16
    assert ClassSession.__table__.c.rpe_token.type.length == 16
    assert len(longest_rpe_token) <= ClassSession.__table__.c.rpe_token.type.length

    # ⑤ mini_test.entered_by ← 录入教师的工号，与 teacher.staff_no **同宽**
    #    （两列各自对字面量 32 断言，不互相比）
    assert MiniTest.__table__.c.entered_by.type.length == 32
    assert M.Teacher.__table__.c.staff_no.type.length == 32
    longest_staff_no = "T2025001"
    assert len(longest_staff_no) == 8
    assert len(longest_staff_no) <= MiniTest.__table__.c.entered_by.type.length

    # ⑥ training_log.source ← ⚠️ 本处此前印的是「今天**没有唯一所有者**（写入方是 Task 5
    #    的采集端点），故只钉得住演示生成器写的那一个字面量 "demo"」。Task 5 按 P5-A3
    #    定了值域（:attr:`TrainingLog.SOURCES` 三个值 + ``ck_training_log_source``），
    #    故「够宽」那一半已由上面那条遍历**自动**覆盖（最长者 "checkin" = 7 ≤ 16）。
    #    **本格保留的唯一职责是钉「列宽恰好 16」**（遍历不判改窄），并把
    #    「今天最长的真实值」从 "demo" 更正成 "checkin"——否则字面量还在按旧词表说话。
    longest_source_today = "checkin"
    assert len(longest_source_today) == 7
    assert TrainingLog.__table__.c.source.type.length == 16
    assert len(longest_source_today) <= TrainingLog.__table__.c.source.type.length


def test_the_plan03_tables_inject_the_clock_and_never_default_it():
    """7 张新表的时间列一律 NOT NULL、且**一个 ``default`` / ``server_default`` 都没有**。

    Global Constraint #1：时钟一律由调用方注入。本包的表不声明
    ``default=dt.datetime.now`` 一类的 Python 侧缺省，也不用 ``server_default``——
    后者会把「这一行是什么时候写的」的所有权交给 DB 进程的时钟，而回放与重放要求它与
    ``daily_sync_run.business_date`` 对得上（``WeeklyAdjustment.created_at`` 的既有口径）。

    ⚠️ 布尔列的 ``default=False`` **不在此列**：那不是时钟，是「没写就是没发起/没读过」
    的诚实缺省（与 ``DailySyncRun`` 计数列 ``default=0`` 同一条理由）。本条把它们显式
    列在末尾单独钉，否则下一个人会连 ``default=False`` 一起删掉。
    """
    time_columns = {
        "class_session": ("session_date",),
        "rpe_record": ("submitted_at",),
        "training_log": ("log_date", "submitted_at"),
        "mini_test": ("tested_on",),
        "alert": ("triggered_at",),
        "notification": ("created_at",),
        "weekly_class_report": ("generated_at",),
    }
    models_by_table = {m.__tablename__: m for m in _PLAN03_MODELS}
    offenders = []
    for table, names in sorted(time_columns.items()):
        for name in names:
            column = models_by_table[table].__table__.c[name]
            if column.default is not None:
                offenders.append(f"{table}.{name} 有 Python 侧缺省 {column.default.arg!r}")
            if column.server_default is not None:
                offenders.append(f"{table}.{name} 有 server_default")
            if column.nullable:
                offenders.append(f"{table}.{name} 可空：漏传会静默落 NULL")
    # 唯一一个可空的时间列是 alert.handled_at——「处置之前本来就没有值」，不是「忘了写」
    assert Alert.__table__.c.handled_at.nullable is True
    assert Alert.__table__.c.handled_at.default is None
    assert offenders == [], "时钟必须由调用方注入：\n" + "\n".join(offenders)

    # 布尔缺省：四个 ``default=False`` 的列
    for model, name in ((ClassSession, "rpe_opened"), (TrainingLog, "is_rest_day"),
                        (TrainingLog, "late"), (Notification, "is_read")):
        column = model.__table__.c[name]
        assert column.nullable is False, f"{model.__tablename__}.{name} 不许为空"
        assert column.default.arg is False, f"{model.__tablename__}.{name} 缺省必须是 False"

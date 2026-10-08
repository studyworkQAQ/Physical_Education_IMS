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

def test_all_eighteen_tables_created(session):
    expected = {"semester","teacher","student","course_section","enrollment",
        "fitness_test_batch","fitness_test_result","body_composition",
        "interest_survey","percentile_snapshot","derived_metrics",
        "stratification_result","daily_sync_run","cleaning_log","exercise",
        "prescription_template","prescription","weekly_adjustment"}
    # Ruling 28：用 == 而不是 >=。「本批只建这些」是真实的范围边界，>= 抓不到
    # 有人提前把后续计划的表建进来——那种提前建表会逼出一次本该不存在的迁移，
    # 而超集断言对它完全无感。
    # ⚠️ **Plan 02 逐 Task 递增**：Plan 01 结案是 14 张，Task 2 加 ``exercise`` → 15；
    # Task 3 加 ``prescription_template`` → 16；**Task 6 加 ``prescription`` +
    # ``weekly_adjustment`` → 18（本条现值，计划 ``:700`` 那份「18 张」清单到此全数落地）**。
    # Plan 03 再加表时同一套同步动作要重跑一遍：① 函数名里的英文数词；② 本文件里那三处
    # ``==`` 断言——**按可 grep 的原文找，不要按裸行号找**：``git grep -n "== 18" --
    # backend/tests/db/test_models.py`` 现命中 **6** 处 = **3** 处真断言（两处 ``assert
    # len(tables) == 18, "守卫的覆盖面必须先被确认是这 18 张表"`` 与一处 ``assert
    # len(Base.metadata.tables) == 18``）+ **3** 处本段的散文（这条 grep 命令自己，
    # 以及紧随其后逐字引出的那两条断言原文）。**改完表数请重跑这条 grep、按命中数逐个
    # 更新，并连带更新 ``app/db/models/prescription.py`` 里同一处计数**（硬规矩 #66）。
    # ⚠️ 此前这里印的是**三个裸行号**，它们是 ``fb5bddb`` 上 ``== 14`` 的位置，Task 2 改成
    # ``== 15`` 时那三处就已推移（Task 2 fix round 3 更正；与 fr2 的 CE-7 同一个失效形态；
    # 那三个过期行号**不再复述**）。⚠️ **Task 3 又踩了一次同一个坑**：控制者派单的自查清单里
    # 印的是 ``966eae0`` 上的 ``:169`` / ``:236`` / ``:494``，而在代码基线 ``c29bc69`` 上实测
    # 已是 ``:176`` / ``:243`` / ``:501``（取证：``t3_probes/p01_verify_baseline.py``）——
    # 即「复用历史输出里的行号等同手写」，硬规矩 #61 的扩写。故本段**一个行号都不写**。
    # ③ ``app/db/models/prescription.py`` 模块 docstring 里那张「表 → 归属 Task」的表；
    # ④ ``tests/seed/test_generate.py`` 的 ``REFERENCE_TABLES``（**两处**：定义与
    # ``assert REFERENCE_TABLES == (…)``，Plan02 账本 P3-A6 第 4 项）；
    # ⑤ **本文件里另外两处按表数/列数写死的断言**（Task 6 实测发现，派单的 Step 0 清单
    # 漏了这两格）：``test_no_column_uses_builtin_sqlalchemy_json`` 的
    # ``assert len(json_text_columns) == 14``（``prescription`` 一张表就带来 5 个
    # ``JsonText`` 列）与 :data:`_DERIVED_TABLES`（两张新表都带 ``batch_id``，而
    # ``test_only_derived_tables_expose_batch_id`` 按**集合相等**判「谁有 batch_id」）。
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
    路径一个也覆盖不到，PRAGMA 会照旧读回 0，而 schema 里 24 个外键全是装饰。
    （24 = Plan 01 的 20 + Plan 02 Task 6 的 4：``prescription`` 的 ``student_id`` /
    ``batch_id`` 与 ``weekly_adjustment`` 的 ``prescription_id`` / ``batch_id``。
    取法：``sum(len(c.foreign_keys) for t in Base.metadata.tables.values()
    for c in t.columns)``，Task 6 亲跑。）
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
    它不看某一列的行为，而是遍历 18 张表的每一列，让「新加的模型忘了这条约定」也
    逃不掉。
    """
    tables = Base.metadata.tables
    assert len(tables) == 18, "守卫的覆盖面必须先被确认是这 18 张表"

    offenders = [
        f"{table.name}.{column.name}"
        for table in tables.values()
        for column in table.columns
        if _is_builtin_json(column.type)
    ]
    assert offenders == [], f"这些列用了自带 JSON，必须换成 JsonText：{offenders}"

    # 守卫自己也得有牙：14 个 JSON 形态的列确实被遍历到了，不是空跑。
    # Plan 02 Task 2 把 8 改成 9：新增的是 ``exercise.targets``（动作瞄准的素质桶名列表）。
    # ⚠️ Task 3 的 ``prescription_template`` **没有** JsonText 列（10 列全是 String / Date /
    # Boolean / int），故那个 9 当时**不变**（P2-A6 的教训：加表时要顺手核一遍这个数）。
    # **Task 6 一次加 5 个 → 9 + 5 = 14**（派单的 Step 0 九格清单漏了这一格，实测发现）：
    # ``prescription`` 的 ``training_package`` / ``assembly_snapshot`` /
    # ``safety_substitutions`` / ``teacher_overrides`` / ``trigger_reasons``；
    # ``weekly_adjustment`` 一个都没有（``reason`` 是自由文本，照 ``cleaning_log.reason``
    # 的既有口径用 ``Text``）。⚠️ 这个数字与 ``app/db/models/_shared.py`` 的
    # ``JsonText`` docstring、``app/db/models/__init__.py`` 的约定 3 是**三处同一事实**，
    # 改一处要改三处（硬规矩 #66）。
    json_text_columns = sorted(
        f"{table.name}.{column.name}"
        for table in tables.values()
        for column in table.columns
        if type(column.type).__name__ == "JsonText"
    )
    assert len(json_text_columns) == 14, json_text_columns
    assert "cleaning_log.original_value" in json_text_columns
    assert "exercise.targets" in json_text_columns
    assert "prescription.trigger_reasons" in json_text_columns


# ---------------------------------------------------------------------------
# Ruling 31：``batch_id`` 一词专指 daily_sync_run 的外键
# ---------------------------------------------------------------------------

# 全库唯一允许拥有 ``batch_id`` 列的表——即 ``delete_by_batch`` 的合法目标。
# Plan 01 结案时是**三张派生表**；Plan 02 Task 6 加 ``prescription`` 与 ``weekly_adjustment``
# → **五张**（P6-A8：``weekly_adjustment`` 也要有 ``batch_id``，因为 Task 7 的
# ``_replay_cleanup`` 要按 ``batch_id`` 删它，而 ``repo.delete_by_batch`` 要求模型有这一列）。
# ⚠️ 常量名仍叫 ``_DERIVED_TABLES`` 是 Plan 01 的遗留措辞：``prescription`` /
# ``weekly_adjustment`` 不是「派生指标」，它们是**管道产物**——与派生表同一类的是
# 「由每日批处理按 ``batch_id`` 写、也按 ``batch_id`` 删」这个性质，而 ``batch_id`` 一词
# 专指的正是它（Ruling 31）。改名要连带改 ``app/db/repo.py`` 与
# ``app/db/models/assessment.py`` 里引用这个说法的散文，故留到 Task 7 把
# ``_replay_cleanup`` 接上时一并处理。
_DERIVED_TABLES = {
    "derived_metrics", "stratification_result", "percentile_snapshot",
    "prescription", "weekly_adjustment",
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


def test_only_derived_tables_expose_batch_id():
    """命名规则必须机器可查，不能只是「大家记得」的约定。

    遍历 ``Base.metadata``，有 ``batch_id`` 列的表**恰好**是 :data:`_DERIVED_TABLES` 那五张
    （Plan 01 的三张派生表 + Plan 02 Task 6 的 ``prescription`` / ``weekly_adjustment``）。
    ``batch_id`` 在本项目里专指「指向 ``daily_sync_run`` 的外键」，也就是 ``delete_by_batch``
    可据以删除的归属键；任何别的父表都得用可区分的名字（``fitness_test_result.test_batch_id``
    指体测批次、``cleaning_log.sync_run_id`` 指同步运行）。

    只断言列名还不够——名字对了语义错了才是 Ruling 31 要防的失效，故同时断言这五列
    真的指向 ``daily_sync_run``。
    """
    tables = Base.metadata.tables
    assert len(tables) == 18, "守卫的覆盖面必须先被确认是这 18 张表"

    observed = {
        name for name, table in tables.items() if "batch_id" in set(table.c.keys())
    }
    assert observed == _DERIVED_TABLES, (
        f"batch_id 专指 daily_sync_run 的外键，实到 {sorted(observed)}"
    )

    for name in sorted(_DERIVED_TABLES):
        column = tables[name].c.batch_id
        assert [fk.target_fullname for fk in column.foreign_keys] == [
            "daily_sync_run.id"
        ], f"{name}.batch_id 必须指向 daily_sync_run"


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
                continue  # 不是取值域约束（本库今天没有这类 CHECK）
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

    1. **有 CHECK 约束的列**——从 :func:`_in_domain` 生成的约束文本反解（今天 **18** 列：
       ``student.sex``、``course_section.grouping_mode``、``fitness_test_batch.timepoint``、
       ``percentile_snapshot`` 的 ``source`` / ``sex`` / ``item``、``stratification_result``
       的 ``label`` / ``percentile_source``、``daily_sync_run.status``、``cleaning_log.kind``、
       Plan 02 Task 2 新增的 ``exercise.impact_level``、Task 3 新增的
       ``prescription_template`` 的 ``layer`` / ``weakness`` / ``body_comp`` /
       ``review_status``、**Task 6 新增的 ``prescription.status`` 与
       ``weekly_adjustment.source``**、以及 **Task 7 fix round 1（F1-1）新增的
       ``prescription.label_at_generation``**）。
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
    （实际侧从 18 份模板 YAML 现读）。Plan 03 再加表时同理：没有 CHECK 的列要自己去
    对应的测试文件里写。
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
    # 18 张表一个不少地注册进了同一个 metadata（拆包最容易漏的就是这个）。下面点名的
    # 是**拆包前就有的 14 张**（``_MODELS_ALL_BASELINE``）；Plan 02 新增的
    # ``exercise`` / ``prescription_template`` / ``prescription`` / ``weekly_adjustment``
    # **不在**那份基线里（Ruling 97：Plan 02 的新表**刻意不进** ``models`` 的公有导入面），
    # 它们由 ``test_all_eighteen_tables_created`` 的 ``expected`` 集合点名，并由
    # ``test_plan02_tables_stay_out_of_the_models_public_namespace`` 钉住「不进导入面」。
    assert len(Base.metadata.tables) == 18
    for name in _MODELS_ALL_BASELINE:
        assert getattr(M, name).__tablename__ in Base.metadata.tables


def test_plan02_tables_stay_out_of_the_models_public_namespace():
    """Ruling 97 对 **Task 6 的两张表**同样成立（与 ``Exercise`` / ``PrescriptionTemplate`` 同口径）。

    :data:`_MODELS_PUBLIC_BASELINE` 钉的是**拆包之前**（基线 ``e26347f``）实测的 33 个公有名，
    往那份基线里加 Plan 02 的新名字等于把「拆包没改导入面」偷换成「拆包后的现状」，
    两侧就同源了（硬规矩 #35）。Task 2 对 ``Exercise``、Task 3 对 ``PrescriptionTemplate``
    各守住过一次（后者由
    ``tests/test_refdata_prescription.py::test_prescription_template_is_not_in_the_models_public_namespace``
    钉），本条把同一道纪律钉到 Task 6 的 ``Prescription`` / ``WeeklyAdjustment`` 上。

    **为什么单独一条而不是往上面那条基线里加名字**：那条的判据是「集合**相等**于拆包前的
    33 个名字」，加名字会让它的函数名（``…is_unchanged_by_the_split``）当场变成谎话，
    而 Ruling 97 那条守卫的 docstring 逐字把「基线被更新成含新名字」列为它要防的失效形态。
    故本条与那条**分工**：那条守「拆包没改导入面」，本条守「Plan 02 的表按子模块引用
    （``from app.db.models.prescription import Prescription``）」。

    ⚠️ **它守不住什么**（硬规矩 #39）：它不守「这两张表**存在**」——那是
    :func:`test_all_eighteen_tables_created` 的 ``expected`` 集合与
    ``test_only_derived_tables_expose_batch_id`` 的遍历在守；本条只守导入面。
    """
    for name in ("Prescription", "WeeklyAdjustment"):
        assert name not in M.__all__, f"{name} 不该出现在 models.__all__（Ruling 97）"
        assert not hasattr(M, name), (
            f"{name} 出现在了 app.db.models 的公有导入面上（Ruling 97 要求按子模块引用："
            f"from app.db.models.prescription import {name}）"
        )
        # 表本身**必须**注册进 metadata：`from . import feedback, prescription` 那一句是承重的
        assert hasattr(M.prescription, name), f"models/prescription.py 里没有 {name} 这个类"
    assert len(_MODELS_PUBLIC_BASELINE) == 33, (
        "基线是 33 个名字（拆包前实测），Task 6 的两张表刻意不进这份清单"
    )
    assert {"prescription", "weekly_adjustment"} <= set(Base.metadata.tables)


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


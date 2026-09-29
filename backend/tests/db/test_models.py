# backend/tests/db/test_models.py
import datetime as dt
import pytest
from sqlalchemy import JSON as BuiltinJson, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from app.db.session import Base, init_db, Session
from app.db import models as M
from app.domain.indicators import Sex

@pytest.fixture
def session():
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    with Session(eng) as s:
        yield s

def test_all_fourteen_tables_created(session):
    expected = {"semester","teacher","student","course_section","enrollment",
        "fitness_test_batch","fitness_test_result","body_composition",
        "interest_survey","percentile_snapshot","derived_metrics",
        "stratification_result","daily_sync_run","cleaning_log"}
    # Ruling 28：用 == 而不是 >=。「第一批只建这 14 张」是真实的范围边界，>= 抓不到
    # 有人提前把计划 02（处方 / 运动记录）或计划 03（预警 / 通知）的表建进来——那种
    # 提前建表会逼出一次本该不存在的迁移，而超集断言对它完全无感。
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
    路径一个也覆盖不到，PRAGMA 会照旧读回 0，而 schema 里 20 个外键全是装饰。
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
    它不看某一列的行为，而是遍历 14 张表的每一列，让「新加的模型忘了这条约定」也
    逃不掉。
    """
    tables = Base.metadata.tables
    assert len(tables) == 14, "守卫的覆盖面必须先被确认是这 14 张表"

    offenders = [
        f"{table.name}.{column.name}"
        for table in tables.values()
        for column in table.columns
        if _is_builtin_json(column.type)
    ]
    assert offenders == [], f"这些列用了自带 JSON，必须换成 JsonText：{offenders}"

    # 守卫自己也得有牙：八个 JSON 形态的列确实被遍历到了，不是空跑
    json_text_columns = sorted(
        f"{table.name}.{column.name}"
        for table in tables.values()
        for column in table.columns
        if type(column.type).__name__ == "JsonText"
    )
    assert len(json_text_columns) == 8, json_text_columns
    assert "cleaning_log.original_value" in json_text_columns


# ---------------------------------------------------------------------------
# Ruling 31：``batch_id`` 一词专指 daily_sync_run 的外键
# ---------------------------------------------------------------------------

# 全库唯一允许拥有 ``batch_id`` 列的三张派生表——即 ``delete_by_batch`` 的合法目标。
_DERIVED_TABLES = {"derived_metrics", "stratification_result", "percentile_snapshot"}


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

    遍历 ``Base.metadata``，有 ``batch_id`` 列的表**恰好**是三张派生表。``batch_id``
    在本项目里专指「指向 ``daily_sync_run`` 的外键」，也就是 ``delete_by_batch`` 可据以
    删除的归属键；任何别的父表都得用可区分的名字（``fitness_test_result.test_batch_id``
    指体测批次、``cleaning_log.sync_run_id`` 指同步运行）。

    只断言列名还不够——名字对了语义错了才是 Ruling 31 要防的失效，故同时断言这三列
    真的指向 ``daily_sync_run``。
    """
    tables = Base.metadata.tables
    assert len(tables) == 14, "守卫的覆盖面必须先被确认是这 14 张表"

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

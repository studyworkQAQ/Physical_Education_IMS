"""``app.db.repo`` 与库层约束的回归测试（Ruling 24/25/26/29 + Minor 2/3/7）。

这个文件存在的理由要先说清楚：``repo.upsert`` 是 Task 10 幂等重放的**唯一执行
机制**，而它此前只被临时探针验证过、探针随后被删除——删掉的探针就是删掉的证据。
一旦 upsert 退化成「查不到就插重复行」，同业务日期重跑会静默翻倍源数据，百分位
快照、短板计数与趋势全部失真且无任何异常，Task 10 的幂等测试（只数派生三表）也
抓不到。故本文件把那些探针逐条固化成可回归的断言。

覆盖分组：

* ``upsert`` / ``delete_by_batch`` 的插入、更新、复合键、错键、跨批不误删、空批
  返回 0（Ruling 26）；
* ``delete_by_batch`` 进来先 flush（Minor 3）、以及对没有 ``batch_id`` 列的模型
  抛 ``AttributeError`` 而不是静默返回 0（Minor 7）；
* Ruling 24 给 ``fitness_test_result`` / ``body_composition`` / ``interest_survey``
  补的三条业务唯一约束，逐表验证「重复行被数据库自己拒收」；
* Ruling 25 的 ``cleaning_log`` 学号双列（孤儿学号可留痕），以及 ``JsonText`` 的
  标量类型保真（它已是全库约定，此前零覆盖）；
* Ruling 29 给 ``percentile_snapshot`` 补的 ``batch_id`` 外键与五列业务唯一键；
* 九条 ``ck_*`` 取值域约束逐条验证（Minor 2）——此前它们在提交内容里零覆盖，
  删掉任一 ``_in_domain(...)`` 全套测试照样全绿。
"""
import datetime as dt

import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.exc import IntegrityError

from app.db import models as M
from app.db import repo
from app.db.session import Session, init_db


@pytest.fixture
def session():
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    with Session(eng) as s:
        yield s


@pytest.fixture
def quiet_session():
    """关掉 autoflush 的会话。

    ``delete_by_batch`` 少一次 flush 就会漏删——但**只在 autoflush 关掉时**才看得出来：
    默认会话里 ``Session.execute`` 会先自动 flush，缺那行代码也照样删得掉。要测
    ``delete_by_batch`` 自己的契约而不是 SQLAlchemy 的实现细节，就得用这个夹具。
    """
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    with Session(eng, autoflush=False) as s:
        yield s


def _seed(session) -> dict:
    """写入最小但父子关系完整的组织数据与一个体测批次、一次批处理运行。

    外键强制已由 ``session.py`` 的 connect 钩子打开（Ruling 27），故父行必须先落库
    再插子行——顺序颠倒会直接 ``FOREIGN KEY constraint failed``。
    """
    semester = M.Semester(
        name="2025-2026-1",
        start_date=dt.date(2025, 9, 1),
        end_date=dt.date(2026, 1, 20),
        weeks=16,
        is_current=True,
    )
    teacher = M.Teacher(staff_no="T2025001", name="李老师")
    session.add_all([semester, teacher])
    session.flush()

    section = M.CourseSection(
        semester_id=semester.id,
        teacher_id=teacher.id,
        name="体育(一)01班",
        grouping_mode="administrative",
    )
    students = [
        M.Student(
            student_no="2025001001",
            name="张三",
            sex="male",
            birth=dt.date(2006, 3, 4),
            grade=1,
        ),
        M.Student(
            student_no="2025001002",
            name="李四",
            sex="female",
            birth=dt.date(2006, 7, 8),
            grade=1,
        ),
    ]
    fitness_batch = M.FitnessTestBatch(
        semester_id=semester.id, timepoint="week1", test_date=dt.date(2025, 9, 10)
    )
    sync_run = M.DailySyncRun(
        semester_id=semester.id, business_date=dt.date(2025, 9, 15), status="success"
    )
    session.add_all([section, *students, fitness_batch, sync_run])
    session.flush()
    return {
        "semester_id": semester.id,
        "teacher_id": teacher.id,
        "course_section_id": section.id,
        "student_ids": [s.id for s in students],
        "student_nos": [s.student_no for s in students],
        "fitness_batch_id": fitness_batch.id,
        "sync_run_id": sync_run.id,
    }


@pytest.fixture
def seeded(session):
    return _seed(session)


@pytest.fixture
def quiet_seeded(quiet_session):
    return _seed(quiet_session)


def _derived_values(seeded: dict, batch_id: int, computed_on: dt.date) -> dict:
    """一条字段齐备的派生指标行，写成 ``upsert`` 能直接吃的字典。"""
    return {
        "student_id": seeded["student_ids"][0],
        "computed_on": computed_on,
        "batch_id": batch_id,
        "annual_change": {"sprint_50m": -0.02},
        "trend": "stable",
        "weaknesses": [],
        "weakness_count": 0,
        "valid_count": 6,
        "body_comp_abnormal": False,
        "body_comp_reasons": [],
    }


def _derived(seeded: dict, batch_id: int, computed_on: dt.date) -> M.DerivedMetrics:
    """造一条字段齐备的派生指标行，供 ``delete_by_batch`` 的测试用。"""
    return M.DerivedMetrics(**_derived_values(seeded, batch_id, computed_on))


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


# ---------------------------------------------------------------------------
# repo.upsert（Ruling 26）
# ---------------------------------------------------------------------------


def test_upsert_inserts_when_no_row_matches(session):
    row = repo.upsert(
        session,
        M.Student,
        ["student_no"],
        {
            "student_no": "2025001001",
            "name": "张三",
            "sex": "male",
            "birth": dt.date(2006, 3, 4),
            "grade": 1,
        },
    )
    session.flush()
    assert _count(session, M.Student) == 1
    assert row.id is not None


def test_upsert_updates_existing_row_without_duplicating(session):
    """幂等的核心：同键第二次写入必须「改」而不是「再插一条」。"""
    values = {
        "student_no": "2025001001",
        "name": "张三",
        "sex": "male",
        "birth": dt.date(2006, 3, 4),
        "grade": 1,
    }
    first = repo.upsert(session, M.Student, ["student_no"], dict(values))
    session.flush()
    first_id = first.id

    second = repo.upsert(
        session,
        M.Student,
        ["student_no"],
        {**values, "name": "张三丰", "grade": 2},
    )
    session.flush()
    session.expire_all()

    assert _count(session, M.Student) == 1, "同键重放不得新增行"
    row = session.scalar(select(M.Student))
    assert row.id == first_id, "改的必须是原来那一行（主键不变）"
    assert (row.name, row.grade) == ("张三丰", 2), "非键字段应被更新"
    assert second is first, "走的是更新分支，返回同一个实例而非新对象"


def test_upsert_handles_composite_key(session, seeded):
    """复合自然键 ``(batch_id, student_id)``——Ruling 24 给体测结果定的那把键。"""
    key = ["batch_id", "student_id"]
    values = {
        "batch_id": seeded["fitness_batch_id"],
        "student_id": seeded["student_ids"][0],
        "height_cm": 172.5,
        "weight_kg": 65.0,
    }
    repo.upsert(session, M.FitnessTestResult, key, dict(values))
    session.flush()
    repo.upsert(session, M.FitnessTestResult, key, {**values, "height_cm": 173.0})
    session.flush()
    session.expire_all()

    assert _count(session, M.FitnessTestResult) == 1, "两列全同即为同一行，不得翻倍"
    row = session.scalar(select(M.FitnessTestResult))
    assert row.height_cm == 173.0, "非键字段应被更新"
    assert row.weight_kg == 65.0, "未出现在本次 values 之外的键字段保持不变"

    # 复合键的另一半变了就是另一条记录，必须新增（否则 week1 与 week8 会互相覆盖）
    repo.upsert(
        session,
        M.FitnessTestResult,
        key,
        {**values, "student_id": seeded["student_ids"][1]},
    )
    session.flush()
    assert _count(session, M.FitnessTestResult) == 2


def test_upsert_raises_when_key_field_is_not_a_column(session):
    """键名写错必须当场炸出来，不能退化成「查不到」而插一条重复行。"""
    with pytest.raises(AttributeError) as excinfo:
        repo.upsert(
            session, M.Student, ["student_noo"], {"student_noo": "2025001001"}
        )
    message = str(excinfo.value)
    assert "student_noo" in message, "报错要点名写错的那个字段"
    assert "Student" in message, "报错要点名是哪个模型"
    assert _count(session, M.Student) == 0, "炸在查询之前，不得落下半行"


# ---------------------------------------------------------------------------
# repo.delete_by_batch（Ruling 26）
# ---------------------------------------------------------------------------


def test_delete_by_batch_deletes_only_the_matching_batch(session, seeded):
    other_run = M.DailySyncRun(
        semester_id=seeded["semester_id"],
        business_date=dt.date(2025, 9, 16),
        status="success",
    )
    session.add(other_run)
    session.flush()
    session.add(_derived(seeded, seeded["sync_run_id"], dt.date(2025, 9, 15)))
    session.add(_derived(seeded, other_run.id, dt.date(2025, 9, 16)))
    session.flush()
    assert _count(session, M.DerivedMetrics) == 2

    deleted = repo.delete_by_batch(session, M.DerivedMetrics, seeded["sync_run_id"])
    session.flush()

    assert deleted == 1, "返回值必须是真实删除条数，Task 10 要靠它对账"
    survivors = session.scalars(select(M.DerivedMetrics)).all()
    assert [r.batch_id for r in survivors] == [other_run.id], "另一批的行必须完好"


def test_delete_by_batch_on_absent_batch_returns_zero(session, seeded):
    session.add(_derived(seeded, seeded["sync_run_id"], dt.date(2025, 9, 15)))
    session.flush()

    assert repo.delete_by_batch(session, M.DerivedMetrics, 999_999) == 0
    assert _count(session, M.DerivedMetrics) == 1, "不存在的批次不得误删任何行"
    # 整表为空时同样返回 0 而不抛（首次运行与重放走同一条代码路径）
    assert repo.delete_by_batch(session, M.StratificationResult, seeded["sync_run_id"]) == 0


def test_delete_by_batch_flushes_pending_rows_first(quiet_session, quiet_seeded):
    """先 upsert 出**尚未落库**的新行、再清批：新行不得躲过那条 DELETE。

    批量 DELETE 只作用于已经在库里的行。顺序颠倒（「算完就写、写完再清旧的」）时，
    若不先 flush，新行会躲过删除、随后在 commit 时被写回——调用方以为清干净了，
    实际留下「旧行没了、新行还在」。实测（去掉 ``delete_by_batch`` 里那行 flush）：
    ``rowcount=1``、提交后残留 1 行；带上 flush 则是 ``rowcount=2``、残留 0 行。

    必须跑在 ``autoflush=False`` 的会话上，这条测试才有牙：默认会话里
    ``Session.execute`` 会先自动 flush，缺那行代码也照样删得掉，那样测到的是
    SQLAlchemy 的实现细节，而不是 ``delete_by_batch`` 自己的契约。
    """
    session, ids = quiet_session, quiet_seeded
    session.add(_derived(ids, ids["sync_run_id"], dt.date(2025, 9, 15)))
    session.commit()  # 上一轮留下的旧行，已在库里

    # 本轮：upsert 出一条待落库的新行，紧接着清批（顺序故意颠倒，不手动 flush）
    repo.upsert(
        session,
        M.DerivedMetrics,
        ["student_id", "computed_on", "batch_id"],
        _derived_values(ids, ids["sync_run_id"], dt.date(2025, 9, 16)),
    )
    assert _count(session, M.DerivedMetrics) == 1, "新行此刻还没落库，库里只有旧行"

    deleted = repo.delete_by_batch(session, M.DerivedMetrics, ids["sync_run_id"])
    session.commit()

    assert deleted == 2, "待落库的新行必须先被 flush 出来，才算在「本批」里"
    assert _count(session, M.DerivedMetrics) == 0, "提交后本批不得残留任何行"


def test_delete_by_batch_on_model_without_batch_id_raises(session, seeded):
    """``cleaning_log`` 那一列叫 ``sync_run_id``：记错表名必须当场炸。

    三张带 ``batch_id`` 的表里就它不叫 ``batch_id``，正是 Task 10 最可能踩的那一脚。
    静默返回 0 的后果是「调用方以为清掉了审计记录」而实际一行没删，比抛错难查得多。
    """
    with pytest.raises(AttributeError) as excinfo:
        repo.delete_by_batch(session, M.CleaningLog, seeded["sync_run_id"])
    message = str(excinfo.value)
    assert "CleaningLog" in message, "报错要点名是哪个模型"
    assert "batch_id" in message, "报错要点名缺的是哪一列"
    assert _count(session, M.CleaningLog) == 0, "不得留下任何副作用"


# ---------------------------------------------------------------------------
# 三张源数据表的业务唯一约束（Ruling 24）
# ---------------------------------------------------------------------------

def _fitness_result(ids: dict, **over) -> M.FitnessTestResult:
    """week1 批次里第一名学生的一条体测记录；``over`` 用来覆盖非键字段。"""
    base = {
        "batch_id": ids["fitness_batch_id"],
        "student_id": ids["student_ids"][0],
        "height_cm": 172.5,
        "weight_kg": 65.0,
    }
    return M.FitnessTestResult(**{**base, **over})


def _body_composition(ids: dict, **over) -> M.BodyComposition:
    base = {
        "student_id": ids["student_ids"][0],
        "measured_on": dt.date(2025, 9, 12),
        "body_fat_pct": 18.5,
        "weight_kg": 65.0,
    }
    return M.BodyComposition(**{**base, **over})


def _interest_survey(ids: dict, **over) -> M.InterestSurvey:
    base = {
        "student_id": ids["student_ids"][0],
        "semester_id": ids["semester_id"],
        "filled_on": dt.date(2025, 9, 15),
        "total_score": 3.6,
        "dimensions": {"运动乐趣": 4.0},
        "raw_answers": {"q1": 4},
    }
    return M.InterestSurvey(**{**base, **over})


# 每张表给出：约束名、业务键列、一条合法行的构造器、以及构造重复行时改动的
# **非键**字段。改非键字段是刻意的：只有当「同键但读数不同」也被拒收时，才证明
# 拦住重放翻倍的是业务键，而不是碰巧整行相同。
_SOURCE_TABLES = {
    "fitness_test_result": {
        "constraint": "uq_fitness_result_batch_student",
        "key_columns": ("batch_id", "student_id"),
        "dup_overrides": {"height_cm": 999.0},
        "build": _fitness_result,
    },
    "body_composition": {
        "constraint": "uq_body_composition_student_measured_on",
        "key_columns": ("student_id", "measured_on"),
        "dup_overrides": {"body_fat_pct": 99.0},
        "build": _body_composition,
    },
    "interest_survey": {
        "constraint": "uq_interest_survey_student_semester_filled_on",
        "key_columns": ("student_id", "semester_id", "filled_on"),
        "dup_overrides": {"total_score": 1.0},
        "build": _interest_survey,
    },
}


@pytest.mark.parametrize("table_name", sorted(_SOURCE_TABLES))
def test_source_table_unique_constraint_rejects_duplicate(session, seeded, table_name):
    """同业务键的第二行必须被数据库自己拒收，而不是静默翻倍。"""
    spec = _SOURCE_TABLES[table_name]

    # 约束名与键列组合先取证：一旦下面的 flush 抛了 IntegrityError，会话就进入待回滚
    # 状态，此后再查任何东西都会得到 PendingRollbackError 而盖掉真正要看的报错。
    # 反射一律复用会话自己那条连接（内存库上另开一条只会自找麻烦）。
    connection = session.connection()
    ddl = connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE name = ?", (table_name,)
    ).scalar()
    assert spec["constraint"] in ddl, "约束必须显式命名，DDL 里要能指名道姓地引用"
    reflected = inspect(connection).get_unique_constraints(table_name)
    columns_by_name = {c["name"]: tuple(c["column_names"]) for c in reflected}
    assert columns_by_name.get(spec["constraint"]) == spec["key_columns"]

    session.add(spec["build"](seeded))
    session.flush()

    session.add(spec["build"](seeded, **spec["dup_overrides"]))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()

    message = str(excinfo.value)
    assert "UNIQUE constraint failed" in message
    for column in spec["key_columns"]:
        assert f"{table_name}.{column}" in message, "报错要点名是哪几列撞了"


# ---------------------------------------------------------------------------
# cleaning_log 的学号双列（Ruling 25）与 JsonText 的类型保真
# ---------------------------------------------------------------------------

# 前导零 + 尾随空格：CSV 里原样收到什么就原样留痕，不 strip、不补零、不数字化
_ORPHAN_NO = "02025001001 "


def test_cleaning_log_keeps_orphan_student_no(session, seeded):
    """学号解析不出来的那条记录，本身就是最该留痕的数据质量问题（Ruling 25）。"""
    columns = {c.name: c for c in M.CleaningLog.__table__.columns}
    assert columns["student_no"].nullable is False, "原始学号永远照抄，不许为空"
    assert columns["student_id"].nullable is True, "解析不出来时外键必须能留空"

    session.add(
        M.CleaningLog(
            sync_run_id=seeded["sync_run_id"],
            student_no=_ORPHAN_NO,
            student_id=None,
            field="height_cm",
            original_value=None,
            processed_value=None,
            kind="missing_dropped",
            reason="学号在学生表中不存在且身高缺测；孤儿学号本身即为数据质量问题",
        )
    )
    session.add(
        M.CleaningLog(
            sync_run_id=seeded["sync_run_id"],
            student_no=seeded["student_nos"][0],
            student_id=seeded["student_ids"][0],
            field="weight_kg",
            original_value=650.0,
            processed_value=65.0,
            kind="unit_normalized",
            reason="体重单位由 g 归一到 kg",
        )
    )
    session.flush()
    session.expire_all()

    orphan, resolved = session.scalars(
        select(M.CleaningLog).order_by(M.CleaningLog.id)
    ).all()
    assert orphan.student_id is None, "孤儿记录必须能落库，不因外键被丢弃"
    assert orphan.student_no == _ORPHAN_NO, "学号须逐字节原样往返（前导零与空格都保住）"
    assert type(orphan.student_no) is str
    assert (resolved.student_no, resolved.student_id) == (
        seeded["student_nos"][0],
        seeded["student_ids"][0],
    ), "能解析时外键照填，两种情形并存"


def test_json_text_keeps_float_and_none(session, seeded):
    """``JsonText`` 已是全库八列的共同约定，这里补上它此前完全没有的覆盖。

    若换回 SQLAlchemy 自带的 ``JSON``，``original_value = 0.0`` 会因 SQLite 的
    NUMERIC 亲和性存成整数、读回 ``int 0``——审计记录里的「原值」不再等于原值。
    """
    session.add(
        M.CleaningLog(
            sync_run_id=seeded["sync_run_id"],
            student_no=seeded["student_nos"][0],
            student_id=seeded["student_ids"][0],
            field="standing_jump_cm",
            original_value=0.0,
            processed_value=None,
            kind="missing_dropped",
            reason="原值 0.0 与缺测都不得被改写成整数 0",
        )
    )
    session.flush()
    session.expire_all()

    row = session.scalar(select(M.CleaningLog))
    assert type(row.original_value) is float, "浮点不得被降成整型"
    assert row.original_value == 0.0
    assert row.processed_value is None, "None 存 SQL NULL，读回仍是 None 而非 'None'"

    column_types = {
        c["name"]: str(c["type"]).upper()
        for c in inspect(session.connection()).get_columns("cleaning_log")
    }
    assert column_types["original_value"] == "TEXT", "底层必须是 TEXT，不是 JSON 亲和性"
    assert column_types["processed_value"] == "TEXT"


# ---------------------------------------------------------------------------
# percentile_snapshot 的幂等防线（Ruling 29）
# ---------------------------------------------------------------------------

def _percentile_snapshot(ids: dict, **over) -> M.PercentileSnapshot:
    """一组（指标 × 性别 × 龄组 × 日）的百分位行；``over`` 用来覆盖字段。"""
    base = {
        "semester_id": ids["semester_id"],
        "computed_on": dt.date(2025, 9, 15),
        "batch_id": ids["sync_run_id"],
        "item": "sprint_50m",
        "sex": "male",
        "age_group": "18-19",
        "p10": 6.8,
        "p20": 7.0,
        "p25": 7.1,
        "p50": 7.6,
        "p75": 8.2,
        "sample_size": 42,
        "source": "school",
    }
    return M.PercentileSnapshot(**{**base, **over})


# 五列业务键 = Task 7 的分组键 (sex, age_group, item) 再加「哪个学期、哪一天」
_SNAPSHOT_KEY = ("semester_id", "computed_on", "item", "sex", "age_group")


def test_percentile_snapshot_group_day_is_unique(session, seeded):
    """同组同日的第二行必须被数据库自己拒收（Ruling 29）。

    此前本表是唯一一张「会被物化、却在库层没有任何幂等防线」的表：既无 ``batch_id``
    （``delete_by_batch`` 够不着它），也无唯一约束（重放翻倍不报错），只能靠 Task 10
    的跨日复用逻辑加一条行数断言兜着——那是纪律，不是机制。
    """
    constraint = "uq_percentile_snapshot_group_day"

    # 取证放在会抛错的 flush 之前：IntegrityError 之后会话进入待回滚状态，再查任何
    # 东西都会得到 PendingRollbackError，盖掉真正要看的报错。
    connection = session.connection()
    ddl = connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE name = ?", ("percentile_snapshot",)
    ).scalar()
    assert constraint in ddl, "约束必须显式命名，DDL 里要能指名道姓地引用"
    reflected = inspect(connection).get_unique_constraints("percentile_snapshot")
    columns_by_name = {c["name"]: tuple(c["column_names"]) for c in reflected}
    assert columns_by_name.get(constraint) == _SNAPSHOT_KEY

    # batch_id 必须真指向 daily_sync_run 且带索引，delete_by_batch 才够得着这张表
    inspector = inspect(connection)
    referred = {
        tuple(f["constrained_columns"]): f["referred_table"]
        for f in inspector.get_foreign_keys("percentile_snapshot")
    }
    assert referred[("batch_id",)] == "daily_sync_run"
    assert M.PercentileSnapshot.__table__.c.batch_id.index is True
    assert "ix_percentile_snapshot_batch_id" in {
        i["name"] for i in inspector.get_indexes("percentile_snapshot")
    }

    session.add(_percentile_snapshot(seeded))
    session.flush()

    # 改的全是**非键**读数：只有「同键但数值不同」也被拒收，才证明拦住翻倍的是业务键
    session.add(
        _percentile_snapshot(
            seeded, p25=9.9, p50=10.5, sample_size=84, source="national"
        )
    )
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()

    message = str(excinfo.value)
    assert "UNIQUE constraint failed" in message
    for column in _SNAPSHOT_KEY:
        assert f"percentile_snapshot.{column}" in message, "报错要点名是哪几列撞了"


def test_percentile_snapshot_orphan_batch_id_is_rejected(session, seeded):
    """新加的 ``batch_id`` 得真受外键管，否则它只是一个长得像外键的整数列。"""
    session.add(_percentile_snapshot(seeded, batch_id=999_999, computed_on=dt.date(2025, 9, 16)))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "FOREIGN KEY constraint failed" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 九条 ck_* 取值域约束（Minor 2）
# ---------------------------------------------------------------------------

def _course_section(ids: dict, **over) -> M.CourseSection:
    base = {
        "semester_id": ids["semester_id"],
        "teacher_id": ids["teacher_id"],
        "name": "体育(一)01班",
        "grouping_mode": "administrative",
    }
    return M.CourseSection(**{**base, **over})


def _fitness_batch(ids: dict, **over) -> M.FitnessTestBatch:
    base = {
        "semester_id": ids["semester_id"],
        "timepoint": "week1",
        "test_date": dt.date(2025, 9, 10),
    }
    return M.FitnessTestBatch(**{**base, **over})


def _stratification(ids: dict, **over) -> M.StratificationResult:
    base = {
        "student_id": ids["student_ids"][0],
        "computed_on": dt.date(2025, 9, 15),
        "batch_id": ids["sync_run_id"],
        "label": "green",
        "hit_rules": "R1,R2,Y1",
        "input_snapshot": {"W": 1, "C": False, "valid_count": 6},
        "percentile_source": "school",
        "valid_from": dt.date(2025, 9, 15),
    }
    return M.StratificationResult(**{**base, **over})


def _sync_run(ids: dict, **over) -> M.DailySyncRun:
    # 不传 status：让 Ruling 30 的默认值生效，合法行照样插得进去
    base = {"semester_id": ids["semester_id"], "business_date": dt.date(2025, 9, 17)}
    return M.DailySyncRun(**{**base, **over})


def _cleaning_log(ids: dict, **over) -> M.CleaningLog:
    base = {
        "sync_run_id": ids["sync_run_id"],
        "student_no": ids["student_nos"][0],
        "student_id": ids["student_ids"][0],
        "field": "height_cm",
        "original_value": 1.75,
        "processed_value": 175.0,
        "kind": "unit_normalized",
        "reason": "身高单位由 m 归一到 cm",
    }
    return M.CleaningLog(**{**base, **over})


def _student(ids: dict, **over) -> M.Student:
    base = {
        "student_no": "2025001999",
        "name": "王五",
        "sex": "male",
        "birth": dt.date(2006, 5, 6),
        "grade": 1,
    }
    return M.Student(**{**base, **over})


# 每项给出：约束名、类常量（取值域的唯一真相）、合法行的构造器、以及把目标列改脏的
# 覆盖值。其中三项额外改动了一个自然键列——**不是为了省事，而是必须**：那三张表带
# 唯一约束，若脏行与刚插入的合法行同键，SQLite 会先报 UNIQUE，测到的就不是取值域了。
_CHECK_CONSTRAINTS = {
    "course_section.grouping_mode": {
        "constraint": "ck_course_section_grouping_mode",
        "allowed": M.CourseSection.GROUPING_MODES,
        "build": _course_section,
        "dirty_over": {"grouping_mode": "mixed"},
    },
    "fitness_test_batch.timepoint": {
        "constraint": "ck_fitness_test_batch_timepoint",
        "allowed": M.FitnessTestBatch.TIMEPOINTS,
        "build": _fitness_batch,
        "dirty_over": {"timepoint": "week3"},
    },
    "stratification_result.label": {
        "constraint": "ck_stratification_result_label",
        "allowed": M.StratificationResult.LABELS,
        "build": _stratification,
        "dirty_over": {"label": "crimson"},
    },
    "stratification_result.percentile_source": {
        "constraint": "ck_stratification_result_percentile_source",
        "allowed": M.StratificationResult.PERCENTILE_SOURCES,
        "build": _stratification,
        "dirty_over": {"percentile_source": "city"},
    },
    "percentile_snapshot.source": {
        "constraint": "ck_percentile_snapshot_source",
        "allowed": M.PercentileSnapshot.SOURCES,
        "build": _percentile_snapshot,
        "dirty_over": {"source": "city", "item": "vital_capacity"},
    },
    "percentile_snapshot.sex": {
        "constraint": "ck_percentile_snapshot_sex",
        "allowed": M.Student.SEXES,
        "build": _percentile_snapshot,
        "dirty_over": {"sex": "unknown"},
    },
    "daily_sync_run.status": {
        "constraint": "ck_daily_sync_run_status",
        "allowed": M.DailySyncRun.STATUSES,
        "build": _sync_run,
        "dirty_over": {"status": "ok", "business_date": dt.date(2025, 9, 18)},
    },
    "cleaning_log.kind": {
        "constraint": "ck_cleaning_log_kind",
        "allowed": M.CleaningLog.KINDS,
        "build": _cleaning_log,
        "dirty_over": {"kind": "whatever"},
    },
    "student.sex": {
        "constraint": "ck_student_sex",
        "allowed": M.Student.SEXES,
        "build": _student,
        "dirty_over": {"sex": "unknown", "student_no": "2025001998"},
    },
}


@pytest.mark.parametrize("target", sorted(_CHECK_CONSTRAINTS))
def test_check_constraint_rejects_dirty_value(session, seeded, target):
    """九条 ``ck_*`` 逐条验证：脏值被数据库自己拒收，且约束名出现在报错与 DDL 里。

    此前这九条约束在提交内容里**零覆盖**——从任一 ``__table_args__`` 里删掉一个
    ``_in_domain(...)``，全套测试照样全绿。第一轮拿出的「脏值被拒」证据来自随后被
    删除的临时探针，删掉的探针就是删掉的证据。
    """
    table_name, column = target.split(".")
    spec = _CHECK_CONSTRAINTS[target]
    dirty = spec["dirty_over"][column]
    assert dirty not in spec["allowed"], "脏值必须确实不在取值域里，否则这条测试没有牙"

    # 取证放在会抛错的 flush 之前（理由同上：IntegrityError 之后会话待回滚）
    connection = session.connection()
    ddl = connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE name = ?", (table_name,)
    ).scalar()
    assert spec["constraint"] in ddl, "约束名必须出现在 DDL 里；被删掉要能当场发现"
    assert column in ddl

    reflected = {
        c["name"]: c["sqltext"]
        for c in inspect(connection).get_check_constraints(table_name)
    }
    assert spec["constraint"] in reflected, "反射也要拿得到名字"
    sqltext = reflected[spec["constraint"]]
    assert sqltext.startswith(f"{column} IN ("), f"约束必须落在 {column} 上：{sqltext}"
    for value in spec["allowed"]:
        assert f"'{value}'" in sqltext, f"取值域由类常量生成，{value} 必须在约束文本里"

    # 合法值先过得去，否则「脏值被拒」证明不了什么——也可能是整张表都插不进去
    session.add(spec["build"](seeded))
    session.flush()

    session.add(spec["build"](seeded, **spec["dirty_over"]))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()

    message = str(excinfo.value)
    assert "CHECK constraint failed" in message, "必须是取值域拦的，不是别的约束顺手拦的"
    # 与 UNIQUE 不同：SQLite 的 CHECK 报错**带约束名**，可直接指名道姓
    assert spec["constraint"] in message


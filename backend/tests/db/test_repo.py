"""``app.db.repo`` 与三张源数据表业务唯一约束的回归测试（Ruling 24/25/26）。

这个文件存在的理由要先说清楚：``repo.upsert`` 是 Task 10 幂等重放的**唯一执行
机制**，而它此前只被临时探针验证过、探针随后被删除——删掉的探针就是删掉的证据。
一旦 upsert 退化成「查不到就插重复行」，同业务日期重跑会静默翻倍源数据，百分位
快照、短板计数与趋势全部失真且无任何异常，Task 10 的幂等测试（只数派生三表）也
抓不到。故本文件把那些探针逐条固化成可回归的断言。

三组覆盖：

* ``upsert`` / ``delete_by_batch`` 的插入、更新、复合键、错键、跨批不误删、空批
  返回 0（Ruling 26）；
* Ruling 24 给 ``fitness_test_result`` / ``body_composition`` / ``interest_survey``
  补的三条业务唯一约束，逐表验证「重复行被数据库自己拒收」；
* Ruling 25 的 ``cleaning_log`` 学号双列（孤儿学号可留痕），以及 ``JsonText`` 的
  标量类型保真（它已是全库约定，此前零覆盖）。
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
def seeded(session):
    """写入最小但父子关系完整的组织数据与一个体测批次、一次批处理运行。

    SQLite 默认不开外键强制，但测试仍照真实关系建父行：约束测的是业务键，不是
    「反正外键不查就随便填个 id」——那会让测试在换到 PostgreSQL 时集体失效。
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
        "course_section_id": section.id,
        "student_ids": [s.id for s in students],
        "student_nos": [s.student_no for s in students],
        "fitness_batch_id": fitness_batch.id,
        "sync_run_id": sync_run.id,
    }


def _derived(seeded: dict, batch_id: int, computed_on: dt.date) -> M.DerivedMetrics:
    """造一条字段齐备的派生指标行，供 ``delete_by_batch`` 的测试用。"""
    return M.DerivedMetrics(
        student_id=seeded["student_ids"][0],
        computed_on=computed_on,
        batch_id=batch_id,
        annual_change={"sprint_50m": -0.02},
        trend="stable",
        weaknesses=[],
        weakness_count=0,
        valid_count=6,
        body_comp_abnormal=False,
        body_comp_reasons=[],
    )


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

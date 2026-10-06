"""``cohort_from_db`` 按业务日期截断体测成绩（Plan 02 Task 1 Step 4 第 2 项）。

本文件是 ``fitness_test_result.tested_on`` 那一列与 ``percentile_stage._results_of`` 的
``tested_on <= as_of`` **唯一的守卫**。两条测试构成一对：同一条夹具、两个不同的 ``as_of``、
两个不同的结果——这才是「截断由 ``as_of`` 驱动」的证据（硬规矩 #23：给观测归因时必须
构造一个同样满足归因、但结果不同的场景）。

夹具**手工建**、不经 ``app.seed``：缺省种子数据里一个批次只有一个采集日（实测见
``tests/pipeline/test_daily.py::_spread_week1_tested_on`` 的 docstring），造不出
「同一批次里既有 ``as_of`` 之前、又有 ``as_of`` 之后的记录」这个形状。
"""
import datetime as dt

import pytest
from sqlalchemy import create_engine

from app.db import models as M
from app.db.session import Session, init_db
from app.pipeline.percentile_stage import cohort_from_db

AS_OF = dt.date(2025, 9, 5)
#: 三条成绩的测量日：一条在 ``AS_OF`` 之前、一条恰等于它（闭区间，须被包含）、
#: 一条在**之后**（未来数据，须被截断掉）。
TESTED_ON = (dt.date(2025, 9, 1), dt.date(2025, 9, 5), dt.date(2025, 9, 8))
#: 逐条对应的「本批有没有成绩」期望值，字面写死（硬规矩 #35）
VISIBLE_AT_AS_OF = (True, True, False)


@pytest.fixture
def session():
    """一个学期、一个 ``week1`` 批次、三名学生各一条成绩，``tested_on`` 逐日递增。

    ``fitness_test_batch.test_date`` 取三条里最早的那天（``min`` 折叠的不动点，见
    ``daily._fitness_batch``），故 ``assessment_anchor`` 在 ``AS_OF`` 上一定选得到它——
    截断发生在**成绩行**这一层，不在批次这一层。
    """
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    with Session(eng) as s:
        sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
                         end_date=dt.date(2026, 1, 20), weeks=16, is_current=True)
        s.add(sem)
        s.flush()
        batch = M.FitnessTestBatch(semester_id=sem.id, timepoint="week1",
                                   test_date=min(TESTED_ON))
        s.add(batch)
        s.flush()
        for i, day in enumerate(TESTED_ON, start=1):
            stu = M.Student(student_no=f"202500100{i}", name=f"学生{i}", sex="male",
                            birth=dt.date(2006, 3, 4), grade=1)
            s.add(stu)
            s.flush()
            s.add(M.FitnessTestResult(
                test_batch_id=batch.id, student_id=stu.id, tested_on=day,
                height_cm=172.5, weight_kg=65.0, total_score=70,
            ))
        s.commit()
        yield s


def test_cohort_truncates_results_by_tested_on(session):
    """``as_of = 2025-09-05`` 只看得见 ``tested_on <= 09-05`` 的两条成绩。

    第三人那条 ``tested_on = 2025-09-08`` 的记录**在库里**、也属于被选中的那个批次，
    但它测量于 ``as_of`` **之后**——用它就是在拿未来的数据算过去的分层。改前
    ``_results_of`` 只按 ``test_batch_id`` 过滤，那一行会被读回来；终审实测 60 人里
    **12 人 label 不同**。

    被截断的那个人不是「消失」，而是退化成「本批没有成绩」这个**合法状态**：
    ``curr_scores`` 七项全 ``None``（``empty_scores()``）→ ``valid_count = 0`` → Z0 闸门
    → ``insufficient_data``（Ruling 106）。他仍然在 ``derived_metrics`` 与
    ``stratification_result`` 里各留一行，故 spec §4.6「运维记录能数出本日没分层的人」
    不失守。
    """
    persons, anchor = cohort_from_db(session, AS_OF)
    assert anchor.curr_batch_id is not None, "批次 test_date <= as_of，锚点必须选得到它"
    assert len(persons) == 3, "遍历的是 student 表的每一个人，不是「本批抽到记录的人」"

    # persons 按 Student.id 升序，与 TESTED_ON 的插入序一一对应
    assert tuple(p.curr_total is not None for p in persons) == VISIBLE_AT_AS_OF

    hidden = persons[2]
    assert len(hidden.curr_scores) == 7, "键必须齐全，derive 的 _require_seven_keys 会查"
    assert all(value is None for value in hidden.curr_scores.values())
    assert hidden.curr_total is None

    # 边界是**闭**的：恰等于 as_of 的那条属于「当天已经测过」，必须看得见
    assert persons[1].curr_total == 70


def test_the_same_cohort_sees_every_result_once_as_of_moves_past(session):
    """同一条夹具、``as_of = 2025-09-30`` → 三条全部可见。

    这一条是上一条的**反证场景**：若两条都通过，就说明「第三人不可见」确实是 ``as_of``
    截断造成的，而不是那条记录本身有什么问题（比如学号解析不到、外键没对上）。
    """
    persons, anchor = cohort_from_db(session, dt.date(2025, 9, 30))
    assert anchor.curr_batch_id is not None
    assert tuple(p.curr_total is not None for p in persons) == (True, True, True)
    assert [p.curr_total for p in persons] == [70, 70, 70]

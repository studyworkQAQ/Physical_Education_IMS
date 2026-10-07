### Task 3: 数据模型与 Repository

**Files:**
- Create: `backend/app/db/session.py`、`backend/app/db/models.py`、`backend/app/db/repo.py`
- Test: `backend/tests/db/test_models.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `engine(url: str = "sqlite:///pe.db") -> Engine`、`Session` 工厂、`init_db(engine) -> None`
  - ORM 模型：`Semester`、`Teacher`、`Student`、`CourseSection`、`Enrollment`、`FitnessTestBatch`、`FitnessTestResult`、`BodyComposition`、`InterestSurvey`、`PercentileSnapshot`、`DerivedMetrics`、`StratificationResult`、`DailySyncRun`、`CleaningLog`
  - `Student.sex: str`、`Student.birth: date`、`Student.grade: int`
  - `CourseSection.grouping_mode: str` ∈ `{"administrative", "stratified"}`
  - `FitnessTestBatch.timepoint: str` ∈ `{"week1", "week8", "week16"}`
  - `StratificationResult.label: str` ∈ `{"red", "yellow", "green", "insufficient_data"}`、`.hit_rules: str`（逗号分隔规则 ID）、`.percentile_source: str` ∈ `{"school", "national"}`
  - `DailySyncRun` 上 `UniqueConstraint("semester_id", "business_date")`
  - `repo.py`：`upsert(session, model, key_fields, values) -> instance`、`delete_by_batch(session, model, batch_id) -> int`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/db/test_models.py
import datetime as dt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from app.db.session import init_db, Session
from app.db import models as M

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
    from sqlalchemy import inspect
    assert set(inspect(session.get_bind()).get_table_names()) >= expected

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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/db -v`
Expected: FAIL — `ModuleNotFoundError: app.db.session`

- [ ] **Step 3: 实现 `session.py` / `models.py` / `repo.py`**

字段清单严格按 spec §4.1–§4.3、§4.6。三个枚举以类常量集合（`LABELS` / `GROUPING_MODES` / `TIMEPOINTS`）声明，并用 SQLAlchemy `CheckConstraint` 在库层兜住。`DerivedMetrics` 与 `StratificationResult` 均带 `batch_id` 外键指向 `DailySyncRun`，供幂等重放时按批删除。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && pytest tests/db -v`
Expected: PASS，5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/ backend/tests/db/
git commit -m "feat: 建立 14 张表的数据模型与 Repository，业务日期唯一约束保障幂等"
```

---


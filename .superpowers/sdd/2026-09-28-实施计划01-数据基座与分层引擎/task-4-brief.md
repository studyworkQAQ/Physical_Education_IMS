### Task 4: DataSourceAdapter 契约与两个实现

**Files:**
- Create: `backend/app/adapters/base.py`、`backend/app/adapters/mock_lepao.py`、`backend/app/adapters/http_lepao.py`
- Create: `backend/tests/fixtures/lepao_sample/fitness.csv`、`body_comp.csv`、`survey.csv`（各 3 行迷你夹具）
- Test: `backend/tests/adapters/test_contract.py`

**Interfaces:**
- Consumes: Task 2 `Sex`
- Produces:
  - `@dataclass(frozen=True) RawFitnessRecord`: `student_no: str`、`batch_key: str`、`height_cm: float | None`、`weight_kg: float | None`、`vital_capacity_ml: float | None`、`sprint_50m_s: float | None`、`sit_and_reach_cm: float | None`、`standing_jump_cm: float | None`、`strength_count: float | None`、`distance_run_s: float | None`
  - `@dataclass(frozen=True) RawBodyCompRecord`: `student_no: str`、`measured_on: str`、`muscle_mass_kg: float | None`、`body_fat_pct: float | None`、`smi: float | None`
  - `@dataclass(frozen=True) RawSurveyRecord`: `student_no: str`、`filled_on: str`、`total: float`、`dimensions: dict[str, float]`、`raw_answers: dict`
  - `class DataSourceAdapter(ABC)`：
    - `fetch_students(since: str | None) -> Iterator[dict]`
    - `fetch_fitness(since: str | None) -> Iterator[RawFitnessRecord]`
    - `fetch_body_comp(since: str | None) -> Iterator[RawBodyCompRecord]`
    - `fetch_survey(since: str | None) -> Iterator[RawSurveyRecord]`
  - `class MockLePaoAdapter(DataSourceAdapter)`：`__init__(self, seed_dir: pathlib.Path)`
  - `class HttpLePaoAdapter(DataSourceAdapter)`：`__init__(self, base_url: str, token: str)`，四个方法体均 `raise NotImplementedError`，但**类必须存在且通过 `isinstance` 契约检查**
  - **CSV 契约（本 Task 是唯一权威定义处，Task 6 的 `write_csv` 必须遵守）**：
    - 文件名固定：`students.csv`、`fitness.csv`、`body_comp.csv`、`survey.csv`（**四个**，Ruling 33 补入 `students.csv`）
    - 列序 = 对应数据类的字段声明顺序，首行为表头，UTF-8 编码
    - `RawSurveyRecord.dimensions` 与 `raw_answers` 各序列化为一个 JSON 字符串列
    - 空值写为空字符串（非 `None`、非 `nan`），读取时还原为 `None`。**这条是承重的**：Ruling 21 已查明 `0` 会经 `score_item` 低侧夹取拿到满分，所以适配器绝不能把空单元格读成 `0` 或 `nan`
  - **`since` 增量语义（Ruling 33）**：`since: str | None` 是 ISO 日期串，**排他**过滤（`> since`）；`None` 表示全量。各方法按记录自身的日期字段过滤：`fetch_fitness` 用 `tested_on`、`fetch_body_comp` 用 `measured_on`、`fetch_survey` 用 `filled_on`；`fetch_students` 不支持增量，`since` 非 `None` 时同样返回全量并在 docstring 说明
  - **`RawFitnessRecord` 增加 `tested_on: str` 字段（Ruling 33）**：Task 10 需要它来查找或创建 `fitness_test_batch` 行，也需要它作为增量水位线。位置放在 `batch_key` 之后
  - **`batch_key` 格式（Ruling 33）**：`"<academic_year>|<timepoint>"`，如 `"2025-2026|week1"`、`"2024-2025|week16"`。`academic_year` 形如 `"2025-2026"`，`timepoint` ∈ {`week1`,`week8`,`week16`}。由 `base.py` 的 `parse_batch_key(key: str) -> tuple[str, str]` 统一解析——**格式只能有一个所有者**，Task 10 不得自己 `split("|")`；格式非法时抛 `ValueError`
  - **`fetch_students` 在第一批只属于契约，不被任何管道阶段消费**（Ruling 33）：`MockLePaoAdapter` 从 `students.csv` 读取（文件缺失则 yield 空），`HttpLePaoAdapter` 留骨架。这是 spec §3.4「骨架先行」的有意安排，**不是待删的死代码**——组织结构在原型阶段由 Task 6 的 `seed_database` 建立，Task 10 的 `test_organization_data_never_flows_through_adapter` 正是钉住「管道不得经适配器插入学生」

- [ ] **Step 1: 写失败测试 — 两个实现跑同一组契约**

```python
# backend/tests/adapters/test_contract.py
import pathlib, pytest
from app.adapters.base import DataSourceAdapter, RawFitnessRecord
from app.adapters.mock_lepao import MockLePaoAdapter
from app.adapters.http_lepao import HttpLePaoAdapter

FIXTURE = pathlib.Path(__file__).parents[1] / "fixtures" / "lepao_sample"

def implementations():
    return [MockLePaoAdapter(FIXTURE), HttpLePaoAdapter("https://api.lepao.example", "t")]

@pytest.mark.parametrize("adapter", implementations(), ids=["mock", "http"])
def test_satisfies_adapter_contract(adapter):
    assert isinstance(adapter, DataSourceAdapter)
    for m in ("fetch_students", "fetch_fitness", "fetch_body_comp", "fetch_survey"):
        assert callable(getattr(adapter, m))

def test_mock_yields_raw_fitness_records():
    recs = list(MockLePaoAdapter(FIXTURE).fetch_fitness(None))
    assert len(recs) == 3 and all(isinstance(r, RawFitnessRecord) for r in recs)

def test_mock_parses_empty_cell_as_none():
    # CSV 契约：空字符串 → None，绝不可解析为 0 或 nan
    recs = list(MockLePaoAdapter(FIXTURE).fetch_fitness(None))
    assert any(r.vital_capacity_ml is None for r in recs)

def test_mock_returns_iterator_not_list():
    import types
    assert isinstance(MockLePaoAdapter(FIXTURE).fetch_fitness(None), types.GeneratorType)

def test_missing_dir_yields_empty_not_raises(tmp_path):
    assert list(MockLePaoAdapter(tmp_path / "nope").fetch_fitness(None)) == []

def test_http_adapter_declares_not_implemented():
    with pytest.raises(NotImplementedError):
        next(HttpLePaoAdapter("https://x", "t").fetch_fitness(None))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/adapters -v`
Expected: FAIL — `ModuleNotFoundError: app.adapters.base`

- [ ] **Step 3: 建迷你夹具 + 实现三个模块**

`tests/fixtures/lepao_sample/` 下三个 CSV 各写 3 行数据，按上面的 CSV 契约（列序 = 数据类字段序）；`fitness.csv` 中须有**一行 `vital_capacity_ml` 为空字符串**，供 `test_mock_parses_empty_cell_as_none` 使用。夹具进版本控制——它是契约的可执行定义。

`MockLePaoAdapter` 从 `seed_dir` 惰性读取并 `yield` 数据类实例；目录不存在时 `yield` 空而非抛错。`http_lepao.py` 只写类与方法签名、docstring 说明乐跑只读接口每日增量同步的契约形状，方法体 `raise NotImplementedError`——spec §3.4 要求现在就建骨架，使未来接口字段确定后改动限于该文件。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && pytest tests/adapters -v`
Expected: PASS，7 passed（`test_satisfies_adapter_contract` 参数化产生 2 个用例）

- [ ] **Step 5: Commit**

```bash
git add backend/app/adapters/ backend/tests/adapters/ backend/tests/fixtures/lepao_sample/
git commit -m "feat: 定义 DataSourceAdapter 契约与 CSV 列序，落地 Mock 实现与乐跑 HTTP 骨架"
```

---


### Task 5: 清洗管道与 cleaning_log

**Files:**
- Create: `backend/data/indicator_ranges.yaml`
- Create: `backend/app/pipeline/clean.py`
- Test: `backend/tests/pipeline/test_clean.py`

**Interfaces:**
- Consumes: Task 4 `RawFitnessRecord`、`RawBodyCompRecord`
- Produces:
  - `@dataclass CleaningEntry`: `student_no: str`、`field: str`、`original_value: object`、`processed_value: object`、`kind: str` ∈ `{"missing_dropped","outlier_corrected","unit_normalized","duplicate_removed"}`、`reason: str`
    - **字段名与 ORM `CleaningLog` 逐字对齐（Ruling 46）**：原计划写 `original`/`processed`，而 Task 3 的 `CleaningLog` 列名是 `original_value`/`processed_value`。同一概念跨两层不同名，会让 Task 10 多一层易错的手工映射；统一为 `original_value`/`processed_value`，Task 10 可直接 `CleaningLog(**entry_dict)` 式落库
    - `kind` 的四个取值必须与 `CleaningLog.KINDS`（Task 3 已建 CHECK 约束）逐字相同，否则落库时被约束拒绝
  - `@dataclass CleanResult`: `fitness: list[RawFitnessRecord]`、`body_comp: list[RawBodyCompRecord]`、`entries: list[CleaningEntry]`、`dropped: int`、`corrected: int`
  - `@dataclass(frozen=True) FieldRange`: `min: float`、`max: float`、`non_positive_is_missing: bool`、`zero_allowed: bool`（`strength_count` 为 `True`：0 次是合法真实值，只有 `< 0` 才算缺失；其余 `non_positive_is_missing=True` 的字段为 `False`）
  - `load_ranges(path: pathlib.Path) -> dict[str, FieldRange]` —— **Ruling 45 更正**：原计划此处声明返回 `dict[str, tuple[float, float]]`，与 Step 3 要求的「每字段两个属性」自相矛盾；改为返回 `FieldRange` 字典。YAML 结构相应为每字段一个映射（`{min: …, max: …, non_positive_is_missing: …}`）而非一个二元列表
  - `clean_fitness(records: Iterable[RawFitnessRecord], ranges: dict[str, FieldRange]) -> CleanResult`
  - `clean_body_comp(records: Iterable[RawBodyCompRecord], ranges: dict[str, FieldRange]) -> CleanResult`
  - `normalize_height(cm: float | None) -> tuple[float | None, CleaningEntry | None]` —— **单参数**，与 Step 1 的测试代码一致。米制启发式（`0 < cm < 3` → ×100）是身高专有的，不需要 `ranges`；`cm <= 0 → None` 的通用规则由 `clean_fitness` 在归一化**之后**按 `FieldRange.non_positive_is_missing` 统一施加，不在本函数内重复
  - **日期列不在清洗范围内**：Ruling 41 已让适配器无条件校验并归一化 `tested_on`/`measured_on`/`filled_on`，`clean.py` 收到的日期一定是合法的零填充 `YYYY-MM-DD`，不得再对其做缺失/异常/量纲处理

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/pipeline/test_clean.py
from app.adapters.base import RawFitnessRecord, RawBodyCompRecord
from app.pipeline.clean import clean_fitness, clean_body_comp, normalize_height, load_ranges
import pathlib

RANGES = load_ranges(pathlib.Path(__file__).parents[2] / "data" / "indicator_ranges.yaml")

def rec(**kw):
    # 字段序与 Ruling 33 后的 RawFitnessRecord 一致：tested_on 是必填的第 3 个位置参数，
    # batch_key 必须是 "<academic_year>|<timepoint>" 格式（parse_batch_key 独占解析）
    base = dict(student_no="S1", batch_key="2025-2026|week1", tested_on="2025-09-04",
        height_cm=175.0, weight_kg=65.0,
        vital_capacity_ml=4200.0, sprint_50m_s=7.2, sit_and_reach_cm=12.0,
        standing_jump_cm=230.0, strength_count=10.0, distance_run_s=240.0)
    return RawFitnessRecord(**{**base, **kw})

def test_unit_error_height_in_meters_normalized():
    # Review Focus #3
    v, entry = normalize_height(1.75)
    assert v == 175.0
    assert entry.kind == "unit_normalized"

def test_outlier_corrected_and_logged():
    r = clean_fitness([rec(sprint_50m_s=3.2)], RANGES)
    assert r.corrected == 1
    assert r.entries[0].kind == "outlier_corrected"
    assert r.entries[0].field == "sprint_50m_s"

def test_body_fat_out_of_range_logged():
    r = clean_body_comp([RawBodyCompRecord("S1", "2025-09-01", 55.0, 62.0, 8.0)], RANGES)
    assert any(e.field == "body_fat_pct" and e.kind == "outlier_corrected" for e in r.entries)

def test_duplicate_record_removed_keeping_newer():
    r = clean_fitness([rec(), rec()], RANGES)
    assert len(r.fitness) == 1
    assert any(e.kind == "duplicate_removed" for e in r.entries)

def test_missing_field_produces_missing_dropped_entry_not_zero():
    # Review Focus #2：缺失字段绝不可被填 0
    r = clean_fitness([rec(vital_capacity_ml=None)], RANGES)
    assert r.fitness[0].vital_capacity_ml is None
    assert any(e.kind == "missing_dropped" and e.field == "vital_capacity_ml" for e in r.entries)

def test_zero_filled_time_field_becomes_missing_not_outlier_corrected():
    # Ruling 21：0 是最常见的缺测占位。若按「修正为区间下界」处理，
    # sprint_50m_s=0.0 会变成 5.0 秒，再经 score_item 低侧夹取得到 100 分——
    # 一个缺测项反而给体能最差的学生送上 20% 权重的满分。必须转 None。
    r = clean_fitness([rec(sprint_50m_s=0.0, distance_run_s=0.0)], RANGES)
    assert r.fitness[0].sprint_50m_s is None
    assert r.fitness[0].distance_run_s is None
    assert all(e.kind == "missing_dropped" for e in r.entries
               if e.field in ("sprint_50m_s", "distance_run_s"))

def test_zero_strength_count_is_a_real_value_not_missing():
    # 引体向上做不起一个 = 0 次，合法真实值，绝不可当缺测
    r = clean_fitness([rec(strength_count=0.0)], RANGES)
    assert r.fitness[0].strength_count == 0.0
    assert not any(e.field == "strength_count" for e in r.entries)

def test_negative_strength_count_is_missing():
    r = clean_fitness([rec(strength_count=-1.0)], RANGES)
    assert r.fitness[0].strength_count is None

def test_negative_sit_and_reach_is_a_real_value():
    # 国标坐位体前屈本就有 −1.3 等负值档
    r = clean_fitness([rec(sit_and_reach_cm=-1.3)], RANGES)
    assert r.fitness[0].sit_and_reach_cm == -1.3
    assert r.entries == []

def test_clean_record_passes_through_untouched():
    r = clean_fitness([rec()], RANGES)
    assert r.entries == [] and r.dropped == 0 and r.corrected == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/pipeline/test_clean.py -v`
Expected: FAIL — `ModuleNotFoundError: app.pipeline.clean`

- [ ] **Step 3: 落地 `data/indicator_ranges.yaml`**

每个字段一条记录，含**两个**属性：合理区间 `[min, max]` 与 `non_positive_is_missing` 布尔标记（Ruling 21）。

| 字段 | 区间 | `non_positive_is_missing` |
|---|---|---|
| `height_cm` | [140, 220] | `true` |
| `weight_kg` | [35, 150] | `true` |
| `vital_capacity_ml` | [800, 9000] | `true` |
| `sprint_50m_s` | [5.0, 15.0] | `true` |
| `sit_and_reach_cm` | [-15, 40] | **`false`**（国标本就有 −1.3 等负值档） |
| `standing_jump_cm` | [120, 400] | `true` |
| `strength_count` | [0, 60] | **`false`**（引体向上做不起一个 = 0 次，是合法真实值；仅 `< 0` 视为缺失） |
| `distance_run_s` | [150, 900] | `true` |
| `muscle_mass_kg` | [20, 90] | `true` |
| `body_fat_pct` | [3, 60] | `true` |
| `smi` | [4, 15] | `true` |

**为什么必须按字段区分、且必须在清洗层处理**：`score_item` 按 Ruling 17 对低侧越界做夹取，而夹取对「越小越好」的项意味着**低值得高分**。实测 `score_item(T, SPRINT_50M, 0.0, ...)` 与 `score_item(T, DISTANCE_RUN, 0.0, ...)` 都返回 **100 分**。`0` 是数值列最常见的缺测占位（NOT NULL 默认值、解析失败回退、导入空值填 0），而 50 米与耐力跑各占国标 20% 权重——一个体能最差的学生会因此拿到 40% 权重的满分，且 `speed_flexibility` 与 `endurance` 两个桶的短板同时消失。**这比高侧越界更危险，因为它抬分而非压分，不会被「成绩异常低」的直觉发现。**

不能在 `score_item` 里一刀切拒绝 `<= 0`：`strength_count = 0` 与 `sit_and_reach_cm < 0` 都是合法真实值。所以处置必须落在清洗层、按字段配置。

- [ ] **Step 4: 实现 `clean.py`**

超出区间的值**修正为最近的区间边界**并记 `outlier_corrected`（不丢弃整条记录，保留该生其余有效项）。

**但 `non_positive_is_missing: true` 的字段上，`value <= 0` 不走「修正为下界」，而是转 `None` 并记 `missing_dropped`**——这是 Ruling 21 的核心：把零填充占位识别为缺测，而不是当成一个极端好成绩。`strength_count` 仅在 `< 0` 时转 `None`（`0` 保留）。

`normalize_height`：`0 < cm < 3` 判定为米制，×100 并记 `unit_normalized`；`cm <= 0` 按上条转 `None`。去重键为 `(student_no, batch_key)`，保留后者。缺失字段保持 `None` 并记 `missing_dropped`——**绝不填 0**，因为 0 分会污染短板判定。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && pytest tests/pipeline/test_clean.py -v`
Expected: PASS，10 passed

- [ ] **Step 6: Commit**

```bash
git add backend/data/indicator_ranges.yaml backend/app/pipeline/clean.py backend/tests/pipeline/
git commit -m "feat: 实现清洗管道，缺失值不填零、异常值修正、量纲启发式识别并全程留痕"
```

---


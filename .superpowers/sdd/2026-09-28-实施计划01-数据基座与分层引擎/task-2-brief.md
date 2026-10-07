### Task 2: 国标 2014 评分表与指标定义

**Files:**
- Create: `backend/data/national_standard_2014.csv`
- Create: `backend/app/domain/tables.py`（表数据结构，纯 dataclass）
- Create: `backend/app/domain/indicators.py`（枚举、桶映射、正查/反查纯函数）
- Create: `backend/app/refdata.py`（**domain 之外**，唯一允许读 `backend/data/*.csv` 的模块）
- Modify: `backend/tests/architecture/test_domain_purity.py`（补文件访问模式检查，Ruling 15）
- Test: `backend/tests/domain/test_indicators.py`、`backend/tests/test_refdata.py`

**Interfaces:**
- Consumes: Task 1 的架构测试与包结构
- Produces:
  - `class Sex(str, Enum)`: `MALE = "male"`, `FEMALE = "female"`
  - `class ScoredItem(str, Enum)`: `BMI`, `VITAL_CAPACITY`, `SPRINT_50M`, `SIT_AND_REACH`, `STANDING_JUMP`, `PULL_UP_OR_SIT_UP`, `DISTANCE_RUN`（**7 项**）
  - `WEAKNESS_ITEMS: tuple[ScoredItem, ...]` — **6 项，不含 `BMI`**
  - `ITEM_BUCKET: dict[ScoredItem, str | None]` — `DISTANCE_RUN`/`VITAL_CAPACITY` → `"endurance"`；`PULL_UP_OR_SIT_UP`/`STANDING_JUMP` → `"strength"`；`SPRINT_50M`/`SIT_AND_REACH` → `"speed_flexibility"`；`BMI` → `None`
  - `AGE_GROUPS: tuple[str, ...]` — 按国标 2014 分组
  - `age_group_of(age: int) -> str`
  - `@dataclass(frozen=True) StandardTable`（在 `app/domain/tables.py`），结构固定为：
    ```python
    segments: dict[tuple[str, str, str], tuple[tuple[float, int], ...]]
    # 键 = (item.value, sex.value, age_group)
    # 值 = 按原始值升序排列的 (raw_value, score) 档位序列
    ```
  - `score_item(table: StandardTable, item: ScoredItem, value: float | None, sex: Sex, age_group: str) -> int | None` — 正查；`value` 为 `None`、键不存在或超出表范围返回 `None`
  - `raw_from_score(table: StandardTable, item: ScoredItem, score: int, sex: Sex, age_group: str) -> float` — 反查，供仿真数据生成；分段函数**线性插值**
  - `segment_thresholds(table: StandardTable, item: ScoredItem, sex: Sex, age_group: str) -> list[float]` — 该组全部档位原始值阈值，升序
  - `app/refdata.py`：`DATA_DIR: pathlib.Path`、`load_standard(path: pathlib.Path | None = None) -> StandardTable`（`path` 缺省为 `DATA_DIR / "national_standard_2014.csv"`；文件不存在抛 `FileNotFoundError`）、`standard() -> StandardTable`（进程内单例缓存，**缓存放在 refdata 而非 domain**）、`segment_count(table: StandardTable, item: ScoredItem, sex: Sex, age_group: str) -> int`（表完整性校验用）

> **Ruling 15 要点**：`score_item` / `raw_from_score` / `segment_thresholds` 的**首参一律是表对象**。domain 内不得出现任何默认加载、模块级缓存或文件读取——否则 domain 会隐式依赖磁盘上某个 CSV 是否存在，spec §1.3「逐人可追溯」与 §12「黄金用例」就都站不住。加载与缓存全部由 `app/refdata.py` 承担，依赖方向 `refdata → domain`，domain 仍是叶子。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/domain/test_indicators.py
from app.domain.indicators import (
    Sex, ScoredItem, WEAKNESS_ITEMS, ITEM_BUCKET,
    age_group_of, score_item, raw_from_score, segment_thresholds,
)
from app.refdata import standard

T = standard()          # 表由 refdata 加载后注入，domain 自身不读盘（Ruling 15）
G = age_group_of(19)

def test_weakness_items_exclude_bmi():
    assert len(WEAKNESS_ITEMS) == 6
    assert ScoredItem.BMI not in WEAKNESS_ITEMS

def test_scored_items_count_is_seven():
    assert len(list(ScoredItem)) == 7

def test_buckets_cover_all_weakness_items():
    assert {ITEM_BUCKET[i] for i in WEAKNESS_ITEMS} == {
        "endurance", "strength", "speed_flexibility"}
    assert ITEM_BUCKET[ScoredItem.BMI] is None

def test_direction_is_normalized_to_higher_is_better():
    # 50 米跑越快得分越高
    assert score_item(T, ScoredItem.SPRINT_50M, 6.5, Sex.MALE, G) > \
           score_item(T, ScoredItem.SPRINT_50M, 9.0, Sex.MALE, G)

def test_score_at_segment_boundary():
    # Review Focus #1：恰好等于档位阈值时不得因浮点误差掉档。
    # 阈值从评分表本身取，避免硬编码魔数与 CSV 内容脱钩。
    thr = segment_thresholds(T, ScoredItem.SPRINT_50M, Sex.MALE, G)[3]
    at_thr     = score_item(T, ScoredItem.SPRINT_50M, thr, Sex.MALE, G)
    just_worse = score_item(T, ScoredItem.SPRINT_50M, thr + 1e-9, Sex.MALE, G)
    assert at_thr == just_worse
    assert at_thr is not None

def test_sex_specific_items_differ():
    m = score_item(T, ScoredItem.PULL_UP_OR_SIT_UP, 10, Sex.MALE, G)
    f = score_item(T, ScoredItem.PULL_UP_OR_SIT_UP, 10, Sex.FEMALE, G)
    assert m != f  # 男引体向上 10 次与女仰卧起坐 10 次得分不同

def test_missing_value_returns_none():
    assert score_item(T, ScoredItem.VITAL_CAPACITY, None, Sex.MALE, G) is None

def test_out_of_range_value_returns_none():
    assert score_item(T, ScoredItem.SPRINT_50M, 999.0, Sex.MALE, G) is None

def test_raw_from_score_roundtrips():
    for item in WEAKNESS_ITEMS:
        raw = raw_from_score(T, item, 80, Sex.MALE, G)
        assert abs(score_item(T, item, raw, Sex.MALE, G) - 80) <= 1

def test_domain_functions_are_pure_and_take_table_explicitly():
    # Ruling 15：同一个表对象传入两次结果必须一致，且 domain 不依赖任何全局加载状态
    a = score_item(T, ScoredItem.STANDING_JUMP, 230.0, Sex.MALE, G)
    b = score_item(T, ScoredItem.STANDING_JUMP, 230.0, Sex.MALE, G)
    assert a == b and a is not None
```

```python
# backend/tests/test_refdata.py
import dataclasses, pytest
from app import refdata
from app.domain.tables import StandardTable
from app.domain.indicators import AGE_GROUPS, Sex, ScoredItem

def test_data_dir_points_at_backend_data():
    assert refdata.DATA_DIR.name == "data"
    assert (refdata.DATA_DIR / "national_standard_2014.csv").is_file()

def test_load_standard_returns_frozen_table():
    t = refdata.load_standard()
    assert isinstance(t, StandardTable)
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.segments = {}

def test_standard_is_cached_singleton():
    assert refdata.standard() is refdata.standard()

def test_table_covers_every_item_sex_agegroup():
    # 每一项 × 性别 × 龄组都必须有档位，否则 score_item 会静默返回 None，
    # 进而让短板判定漏项——这是会污染整个分层结果的静默失效
    t = refdata.load_standard()
    missing = [(i, s, ag) for i in ScoredItem for s in Sex for ag in AGE_GROUPS
               if refdata.segment_count(t, i, s, ag) < 2]
    assert missing == []

def test_missing_csv_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        refdata.load_standard(tmp_path / "nope.csv")
```

- [ ] **Step 2: 扩展架构测试 — domain 禁止文件访问模式（Ruling 15）**

在 `backend/tests/architecture/test_domain_purity.py` 增加第三个检查与对应测试：

```python
# 文件访问模式：domain 不得读盘，参考表一律由 app/refdata.py 加载后注入
FORBIDDEN_IO = ("read_csv", "read_excel", "read_json", "read_parquet",
                "csv.reader", "csv.DictReader", ".read_text", ".read_bytes", "Path(")

def test_domain_has_no_filesystem_access():
    assert DOMAIN.is_dir(), f"领域层目录缺失，架构测试将空转: {DOMAIN}"
    offenders = []
    for py in DOMAIN.rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        offenders += [f"{py.name}:{tok}" for tok in FORBIDDEN_IO if tok in src]
    assert offenders == []
```

**注意**：`pandas` **不**加入 `FORBIDDEN`。它是纯计算库，封禁它会迫使 Task 11 的向量化优化落到更差的设计上；spec 的意图是「无文件系统/数据库/网络/时钟」，不是「不许用某个计算库」。

先运行确认新测试**通过**（此时 domain 仍为空）——它的价值在 Step 5 之后才体现：一旦有人把 CSV 加载写进 domain，这里立刻红灯。

Run: `cd backend; pytest tests/architecture -v`
Expected: PASS，3 passed

- [ ] **Step 3: 落地 `backend/data/national_standard_2014.csv`**

列：`item, sex, age_group, score, raw_value`。每行表示「该性别龄组下，某计分项得 `score` 分对应原始值 `raw_value`」。数据取自《国家学生体质健康标准（2014 年修订）》评分表。`PULL_UP_OR_SIT_UP` 与 `DISTANCE_RUN` 按性别对应不同测试项目，`item` 值相同但 `sex` 区分。

**完整性要求**：7 个计分项 × 2 性别 × 全部龄组的每个组合都必须有 ≥2 个档位。缺任一组会让 `score_item` 静默返回 `None`，进而使短板判定漏项——这是会污染整个分层结果且**不报错**的失效，由 `test_table_covers_every_item_sex_agegroup` 看守。

- [ ] **Step 4: 实现 `tables.py` / `indicators.py` / `refdata.py`**

`app/domain/tables.py`：只放 `StandardTable` frozen dataclass，按 Interfaces 块给定的 `segments` 结构，无任何逻辑与 I/O。

`app/domain/indicators.py`：枚举、`WEAKNESS_ITEMS`、`ITEM_BUCKET`、`AGE_GROUPS`、`age_group_of`，以及三个**首参为 `table`** 的纯函数。`score_item` 在 `table.segments[(item.value, sex.value, age_group)]` 的档位序列内按 `raw_value` 定位区间后线性插值；方向由表本身保证（CSV 中「越大越好」的项按 `raw_value` 升序对应 `score` 升序，「越小越好」的项按 `raw_value` 升序对应 `score` 降序），实现无需硬编码方向。键不存在、`value` 为 `None` 或超出档位范围一律返回 `None`，**不得抛异常也不得返回 0**（0 分会被当成真实短板，污染 `W`）。`raw_from_score` 为同一表的反向插值。`segment_thresholds` 返回该组全部档位原始值阈值（升序），供边界测试取真实档位而非魔数。

`app/refdata.py`（**在 domain 之外**）：`DATA_DIR` 指向 `backend/data`；`load_standard(path=None)` 读 CSV 构造 `StandardTable`，文件不存在抛 `FileNotFoundError`；`standard()` 做进程内单例缓存——**缓存放这里，不放 domain**；`segment_count()` 供表完整性校验。

**domain 模块的注释与 docstring 里不要写出 `datetime.now`、`date.today`、`time.time` 这些 token**：`FORBIDDEN_CALLS` 是源码文本级子串匹配，写一句「本模块不得调用 datetime.now()」的合规说明反而会自伤红灯（Task 1 复审已登记此延后 Minor）。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend; pytest tests/domain/test_indicators.py tests/test_refdata.py tests/architecture -v`
Expected: PASS，18 passed（indicators 10 + refdata 5 + architecture 3）

再验证守卫真的会咬人：临时在 `backend/app/domain/indicators.py` 里加一行 `import pandas as pd` 与 `pd.read_csv("x.csv")`，运行架构测试确认 `test_domain_has_no_filesystem_access` **FAIL**，然后删除该行恢复绿色。把两次输出记进报告。

- [ ] **Step 6: Commit**

```bash
git add backend/data/national_standard_2014.csv backend/app/domain/tables.py backend/app/domain/indicators.py backend/app/refdata.py backend/tests/
git commit -m "feat: 国标2014评分表与指标定义，参考表加载移出domain以保持领域层无I/O"
```

---


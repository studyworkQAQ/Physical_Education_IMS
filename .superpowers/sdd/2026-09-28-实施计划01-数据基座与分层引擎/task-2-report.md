# Task 2 报告：国标 2014 评分表与指标定义

**状态**：DONE_WITH_CONCERNS
**Commit**：`0f2d60d` — `feat: 国标2014评分表与指标定义，参考表加载移出domain以保持领域层无I/O`
**分支 / 起点**：`feature/plan-01-data-foundation`，基于 `f71cc46`
**测试**：18/18 passed，输出洁净（`pytest -q` 与 `pytest -q -W error` 均无 warning），文件访问守卫已变异验证

---

## 1. 实现内容

### `backend/app/domain/tables.py`（新增，21 行）
只有 `@dataclass(frozen=True) class StandardTable`，字段严格按 brief：

```python
segments: dict[tuple[str, str, str], tuple[tuple[float, int], ...]]
# 键 = (item.value, sex.value, age_group)；值 = 按 raw_value 升序的 (raw_value, score) 档位序列
```
无任何逻辑、无 I/O。

### `backend/app/domain/indicators.py`（新增，157 行）
- `Sex(str, Enum)`：`MALE="male"` / `FEMALE="female"`
- `ScoredItem(str, Enum)`：7 项，value 为 snake_case（`bmi` / `vital_capacity` / `sprint_50m` / `sit_and_reach` / `standing_jump` / `pull_up_or_sit_up` / `distance_run`），与 CSV `item` 列一致
- `WEAKNESS_ITEMS`：6 项，不含 `BMI`
- `ITEM_BUCKET`：`BMI → None`；`VITAL_CAPACITY`/`DISTANCE_RUN → "endurance"`；`PULL_UP_OR_SIT_UP`/`STANDING_JUMP → "strength"`；`SPRINT_50M`/`SIT_AND_REACH → "speed_flexibility"`
- `AGE_GROUPS = ("大一、大二", "大三、大四")`、`age_group_of(age)`
- 三个**首参为 `table`** 的纯函数：`score_item` / `raw_from_score` / `segment_thresholds`

### `backend/app/refdata.py`（新增，50 行，domain 之外）
`DATA_DIR`、`STANDARD_FILENAME`、`load_standard(path=None)`、`standard()`（进程内单例缓存 `_standard_cache` 放在这里）、`segment_count()`。
`load_standard` 按 `(item, sex, age_group)` 聚行后 `tuple(sorted(...))`，所以 **CSV 行序不影响结果**；用 `encoding="utf-8-sig"` + `newline=""`，已实测 CRLF 版 CSV 与 LF 版解析结果完全相同（`core.autocrlf=true`，checkout 后必然变 CRLF）。

### `backend/tests/architecture/test_domain_purity.py`（修改，+14 行）
新增 `FORBIDDEN_IO` 与 `test_domain_has_no_filesystem_access`。`pandas` 未加入 `FORBIDDEN`，理由写在注释里。

### 测试文件
`backend/tests/domain/test_indicators.py`（10 个）、`backend/tests/test_refdata.py`（5 个）——**逐字采用 brief 中的测试代码**，未增删任何断言。未建 `conftest.py`、未建 `tests/__init__.py`。

---

## 2. 数据溯源（最重要的一节）

### 2.1 来源文件

《国家学生体质健康标准（2014 年修订）》，教育部 **教体艺〔2014〕5 号**。
原文入口：<http://www.moe.gov.cn/s78/A17/twys_left/moe_938/moe_792/s3273/201407/t20140708_171692.html>

逐格核对用了 4 份相互独立的高校转载全文：

| # | 机构 | URL |
| --- | --- | --- |
| A | 广东工业大学体育学院（教体艺〔2014〕5 号节选） | https://tyb.gdut.edu.cn/info/1114/1811.htm |
| B | 山东大学体育学院（威海）（大学版） | https://tyb.wh.sdu.edu.cn/info/1005/2291.htm |
| C | 长春理工大学体育教研部 | https://tyjyb.ccut.edu.cn/info/1211/1761.htm |
| D | 中国民航大学体育工作部（全学段版） | https://www.cauc.edu.cn/tyb/info/1124/1220.htm |

溯源说明已落在 `backend/data/README_national_standard.md`，其中明确写了「上线前请项目组用官方正式文本逐表复核」。

### 2.2 分组问题的裁决：**官方是年级组，不是年龄段**

国标「说明」第 4 条原文：

> 本标准将适用对象划分为以下组别：小学、初中、高中按每个年级为一组，其中小学为 6 组、初中为 3 组、高中为 3 组。**大学一、二年级为一组，三、四年级为一组。**

4 份来源一致。所以大学只有 **2 个组**，`AGE_GROUPS` 直接用官方年级组名 `"大一、大二"` / `"大三、大四"`，**没有另造任何年龄带**（brief 要求「不要凭空发明标准里不存在的年龄带」）。

`age_group_of(age)` 的年龄→年级组折算是**工程约定，不是国标条文**，按典型在校年龄（大一 18、大二 19、大三 20、大四 21）取 19/20 岁为分界：`age <= 19 → 大一、大二`，`age >= 20 → 大三、大四`；超出 18–22 的输入自然落到端点组，不会产出表里没有的键。已写进 docstring 与 README。

### 2.3 单位口径

| `item` | 官方表号 | `raw_value` 单位 |
| --- | --- | --- |
| `bmi` | 表1-1 / 表1-2 | 千克/米² |
| `vital_capacity` | 表1-3 / 表1-4 | 毫升 |
| `sprint_50m` | 表1-5 / 表1-6 | 秒 |
| `sit_and_reach` | 表1-7 / 表1-8 | 厘米 |
| `standing_jump` | 表1-9 / 表1-10 | 厘米 |
| `pull_up_or_sit_up` | 表1-11（男引体向上）/ 表1-12（女一分钟仰卧起坐） | 次 |
| `distance_run` | 表1-13（男 1000 m）/ 表1-14（女 800 m） | **秒（总秒数）** |

耐力跑官方写 `3'17"`，CSV 统一存总秒数 `197`（否则线性插值无意义）。README 里附了全部 80 个 `分'秒"` 原值表，可逐格复核。转换在一次性生成脚本里机械完成（`mm:ss → mm*60+ss`），不是手算。

### 2.4 完整性：28 / 28 组合全部有源，0 缺失、0 编造

7 项 × 2 性别 × 2 年级组 = **28 个组合，全部有官方数据**，`len(T.segments) == 28` 已实测。CSV 共 **502 行数据**：

| item | 每性别每组档位数 | 小计 |
| --- | --- | --- |
| `bmi` | 8（含 2 个表示层哨兵，见 2.5） | 32 |
| `vital_capacity` / `sprint_50m` / `sit_and_reach` / `standing_jump` / `distance_run` | 20 | 400 |
| `pull_up_or_sit_up` | 男 15（官方及格段稀疏）/ 女 20 | 70 |

`test_table_covers_every_item_sex_agegroup`（要求每组合 ≥2 档）**全绿，无任何组合需要填充**。没有为凑档位编造过任何一个数值。

### 2.5 两处必须让 controller 知道的表示层妥协（**Concern 主因**）

**(a) BMI 在国标里是非单调的区间映射，与 `StandardTable` 结构不同构。**

官方（表1-1/1-2，且**只有「大学」一列、不分年级组**）：

| 性别 | 正常 100 | 低体重 80 | 超重 80 | 肥胖 60 |
| --- | --- | --- | --- | --- |
| 男 | 17.9~23.9 | ≤17.8 | 24.0~27.9 | ≥28.0 |
| 女 | 17.2~23.9 | ≤17.1 | 24.0~27.9 | ≥28.0 |

`StandardTable` 的档位序列只能表达「沿 `raw_value` 单调」的映射，而 BMI 是 80→100→80→60。
落法：把 **6 个官方闭区间端点原样落成档位**，再用 **`0` / `999` 两个哨兵**把 `≤17.8` 和 `≥28.0` 两个开口区间封口。哨兵**不是国标数值**，纯粹是为了把开区间表示成有限档位序列——README 已用加粗写明。

实测（男，大一、大二）：`16→80`、`17.8→80`、`20→100`、`23.9→100`、`24→80`、`27.9→80`、`28→60`、`35→60`；（女）`17.1→80`、`17.2→100`、`30→60`。**每个官方闭区间上取值精确。**

残留偏差只在 `17.8~17.9`、`23.9~24.0`、`27.9~28.0` 三个 0.1 宽的舍入缝里（缝内插值成 90 / 90 / 70）。国标 BMI 本身按 1 位小数报告，缝宽即舍入误差宽。
另：BMI 官方不分组，两个年级组的行完全相同（如实复制，非编造）。
**注意**：BMI 不在 `WEAKNESS_ITEMS` 内、`ITEM_BUCKET[BMI] is None`，不参与短板判定与桶化，但它占总分权重 15%，上述偏差会进总分。若不可接受，需要 controller 裁决（给 `StandardTable` 增加区间型档位表达能力，或把 BMI 评分单列一条规则）。

**(b) 男生引体向上档位稀疏，是国标原样，不是缺数据。**

整数次数填不满每 2 分一档，官方及格段只有 76/72/68/64/60 五档有实测次数，78/74/70/66/62 五档留空。CSV 只落有官方数值的 15 档。所以男生没有「74 分」这个可取分数。女生仰卧起坐是完整 20 档。

### 2.6 待复核清单（唯一一处来源分歧）

- **男 / 大一、大二 / 引体向上 14 次**：来源 A（广东工业）、C（长春理工）均记 **76 分**；来源 B（山大威海）的表格渲染把它落在 78 分、并把大三、大四的 15 次落在 76 分——这破坏了「大三、大四 = 大一大二 + 1 次同分」的一致规律。本 CSV 采用 **76 分**（两份一致 + 规律自洽）。**请用官方原件确认这一格。**
- 其余 27 个组合在 3–4 份来源间**完全一致，无分歧**。

### 2.7 未纳入本表的内容（有意为之，非遗漏）

- **加分表（表2-3 ~ 表2-6）**：国标学年总分满分 120，其中 20 分附加分来自男引体向上／男 1000 米、女仰卧起坐／女 800 米「超过 100 分」的部分。本 CSV 只覆盖 0–100 的单项标准分。若后续要还原 120 分制总分，需要另加一张加分表。
- 小学／初中／高中各年级组：本项目只做高校，未录入。

---

## 3. TDD 证据

### RED

```
cd backend; pytest tests/architecture -v
→ 3 passed（Step 2 要求：此时 domain 仍为空，新守卫先绿，价值在 Step 5 之后体现）

cd backend; pytest tests/domain/test_indicators.py tests/test_refdata.py -q
→ ERROR tests/domain/test_indicators.py
    tests\domain\test_indicators.py:2: in <module>
        from app.domain.indicators import (
    E   ModuleNotFoundError: No module named 'app.domain.indicators'
  ERROR tests/test_refdata.py
    tests\test_refdata.py:3: in <module>
        from app import refdata
    E   ImportError: cannot import name 'refdata' from 'app'
  2 errors in 0.17s
```

**为什么这是预期的失败**：Step 1 的测试先于实现落地，`app/domain/indicators.py` 与 `app/refdata.py` 尚不存在，两个测试模块在 import 阶段就报错，一个断言都没执行到。失败原因正是「被测对象不存在」，而不是「断言写错」。

### GREEN

```
cd backend; pytest tests/domain/test_indicators.py tests/test_refdata.py tests/architecture -v

tests/domain/test_indicators.py::test_weakness_items_exclude_bmi PASSED  [  5%]
tests/domain/test_indicators.py::test_scored_items_count_is_seven PASSED [ 11%]
tests/domain/test_indicators.py::test_buckets_cover_all_weakness_items PASSED [ 16%]
tests/domain/test_indicators.py::test_direction_is_normalized_to_higher_is_better PASSED [ 22%]
tests/domain/test_indicators.py::test_score_at_segment_boundary PASSED   [ 27%]
tests/domain/test_indicators.py::test_sex_specific_items_differ PASSED   [ 33%]
tests/domain/test_indicators.py::test_missing_value_returns_none PASSED  [ 38%]
tests/domain/test_indicators.py::test_out_of_range_value_returns_none PASSED [ 44%]
tests/domain/test_indicators.py::test_raw_from_score_roundtrips PASSED   [ 50%]
tests/domain/test_indicators.py::test_domain_functions_are_pure_and_take_table_explicitly PASSED [ 55%]
tests/test_refdata.py::test_data_dir_points_at_backend_data PASSED       [ 61%]
tests/test_refdata.py::test_load_standard_returns_frozen_table PASSED    [ 66%]
tests/test_refdata.py::test_standard_is_cached_singleton PASSED          [ 72%]
tests/test_refdata.py::test_table_covers_every_item_sex_agegroup PASSED  [ 77%]
tests/test_refdata.py::test_missing_csv_raises_file_not_found PASSED     [ 83%]
tests/architecture/test_domain_purity.py::test_domain_has_no_forbidden_imports PASSED [ 88%]
tests/architecture/test_domain_purity.py::test_domain_has_no_clock_or_file_access PASSED [ 94%]
tests/architecture/test_domain_purity.py::test_domain_has_no_filesystem_access PASSED [100%]

18 passed in 0.06s
```

全量套件（提交前）：

```
cd backend; pytest -q           → 18 passed in 0.05s
cd backend; pytest -q -W error  → 18 passed in 0.04s   # 以 warning 为 error 仍全绿 ⇒ 输出确实洁净
```

### 额外做的国标对拍（非提交内容，一次性命令行核对）

用官方表里的原始档位值反查得分，逐项对上：

```
groups ('大一、大二', '大三、大四')   age_group_of(19)=大一、大二  age_group_of(21)=大三、大四
50m 7.1 → 80 ✓        50m 9.1 → 60 ✓       50m 6.5 → 100（优于表内最好档，按满分封顶）✓
50m 10.1 → 10 ✓       50m 10.2 → None（差于最差档）✓
1000m 272s(4'32") → 60 ✓   1000m 197s(3'17") → 100 ✓
肺活量 4300 → 80 ✓   5200 → 100（封顶）✓   2000 → None ✓
立定跳远 230 → 71（228→70 与 232→72 之间插值）✓   坐位体前屈 17.7 → 80 ✓
引体向上(男) 14 → 76 ✓   仰卧起坐(女) 44 → 78 ✓
BMI 男 16→80 17.8→80 20→100 23.9→100 24→80 27.9→80 28→60 35→60  全部与官方区间一致 ✓
BMI 女 17.1→80 17.2→100 30→60 ✓
大三、大四 50m 6.6 → 100 ✓
raw_from_score(80)：引体向上→15.0 ✓  耐力跑→222.0(=3'42") ✓
len(T.segments) == 28 ✓
```

---

## 4. Step 5 变异检查证据（新文件访问守卫真的会咬人）

**注入变异**：在 `backend/app/domain/indicators.py` 顶部临时加 `import pandas as pd`，并在 import 段后加 `pd.read_csv("x.csv")`。

```
cd backend; pytest tests/architecture -v

E         Left contains one more item: 'indicators.py:read_csv'
E         Full diff:
E         - []
E         + [
E         +     'indicators.py:read_csv',
E         + ]
tests\architecture\test_domain_purity.py:57: AssertionError
FAILED tests/architecture/test_domain_purity.py::test_domain_has_no_filesystem_access
  - AssertionError: assert ['indicators.py:read_csv'] == []
========================= 1 failed, 2 passed in 0.10s =========================
```

**结论**：`test_domain_has_no_filesystem_access` **FAIL**，offender 精确指到 `indicators.py:read_csv`；同时另两个既有守卫仍 `2 passed`——说明咬人的正是本次新增的检查，且 `pandas` 本身没有被误封（import 未触发 `test_domain_has_no_forbidden_imports`），符合 brief「pandas 不加入 FORBIDDEN」的要求。

**恢复**：删除那两行，架构测试回到 `3 passed`，全量 `18 passed`。已 `git show` 复核 diff，mutation 无残留。

---

## 5. 变更文件（8 个，+955 行，0 删除）

```
backend/app/domain/indicators.py                 | 157 +   （新增）
backend/app/domain/tables.py                     |  21 +   （新增）
backend/app/refdata.py                           |  50 +   （新增）
backend/data/README_national_standard.md         | 123 +   （新增，溯源说明）
backend/data/national_standard_2014.csv          | 503 +   （新增，1 表头 + 502 数据行）
backend/tests/architecture/test_domain_purity.py |  14 +   （修改，新增 FORBIDDEN_IO + 第 3 个检查）
backend/tests/domain/test_indicators.py          |  57 +   （新增，10 个测试）
backend/tests/test_refdata.py                    |  30 +   （新增，5 个测试）
```

brief 的 Create/Modify 清单全部覆盖；`README_national_standard.md` 是任务说明额外要求的溯源文件。工作树提交后干净。

---

## 6. 自检结论

- **`None` 契约**：`score_item` 对「键不存在 / `value is None` / 读数差到超出评分表覆盖范围」三种情形一律返回 `None`，**任何路径都不返回 `0`、不抛异常**。已逐行走查：`return None` 出现在 `value is None`、`not segments`、两端越界且该端不是最优端、以及循环兜底；唯一的非 None 返回是 `round(...)` 与端点满分封顶。`0` 分只能来自表内真实档位（官方最低档是 10 分），不会被误当短板污染 `W`。
- **越界语义（需要 controller 知晓的一处实现裁决）**：brief 的两条测试联合起来只能有一种自洽解释——`test_direction_is_normalized_to_higher_is_better` 要求 50 m 跑 6.5 s（**优于**表内最好档 6.7 s）返回一个大于 61 的整数，而 `test_out_of_range_value_returns_none` 要求 999.0 s（**差于**表内最差档 10.1 s）返回 `None`。因此实现为**非对称**：优于最好档 → 按该项满分封顶（国标单项分本来就封顶 100，破表好成绩不该被当缺测）；差于最差档 → `None`。方向不硬编码，靠「该端点得分是否等于表内最高分」判定，对「越大越好」「越小越好」两类项都成立，BMI 的非单调序列也安全（两个哨兵端都不是最高分端，且生理可达值全在表内）。副作用：一个跑 1000 m 用 7 分钟的学生（差于 10 分档 6'12"）会得到 `None` 而非 10 分，即被当缺测。这是 brief 测试强制的行为，如实记录。
- **边界不掉档**：`test_score_at_segment_boundary` 取 `segment_thresholds(...)[3]`（= 7.0 s，真实档位而非魔数），`7.0` 与 `7.0+1e-9` 都得 85 分——靠 `round()` 而非 `int()` 截断实现，浮点表示误差不会导致掉档。
- **纯净性**：对 `app/domain/` 全量 grep `datetime.now|datetime.today|datetime.utcnow|date.today|time.time|read_csv|read_excel|read_json|read_parquet|csv.reader|csv.DictReader|.read_text|.read_bytes|Path\(|\bopen\s*\(|import (sqlalchemy|fastapi|requests|httpx|pydantic_settings|random)` → **No matches found**。注释与 docstring 里也没有写出任何被禁 token（避开了 Task 1 复审登记的延后 Minor）。domain 只 import `dataclasses` 与 `enum`，外加 domain 内部的 `app.domain.tables`。
- **Ruling 15 依赖方向**：`refdata → domain` 单向；domain 内无默认加载、无模块级缓存、无文件读取；三个函数首参一律是表对象。`standard()` 的缓存 `_standard_cache` 在 `app/refdata.py`。
- **纪律**：没装 linter、没加 CI、没建 venv、没建 `conftest.py`、没建 `tests/__init__.py`；除任务要求的溯源 README 外没写任何文档。一次性 CSV 生成脚本写在 `$env:TEMP` 下、运行后已删除，未进入仓库。
- **CSV 编码/换行**：文件为无 BOM UTF-8、LF。因 `core.autocrlf=true`，checkout 后会变 CRLF；已实测 CRLF 版与 LF 版 `load_standard` 结果 `segments` 完全相等（`csv` 模块配 `newline=""` 原生处理 `\r\n`），不会静默串值。
- **测试代码逐字采用 brief**，一个断言都没改。`test_sex_specific_items_differ` 实际是「男 10 次 → 60 分」vs「女 10 次 → None」（女生仰卧起坐最低档是 16 次，10 次差于表内范围），`60 != None` 成立、断言通过——语义上仍然表达了「同一 item 值在两性下不是同一张表」，但值得 controller 知道它是以 None 而非以另一个整数通过的。

---

## 7. Concerns（按严重度排序）

1. **【需裁决】BMI 与 `StandardTable` 结构不同构。** 国标 BMI 是区间型非单调映射，现用「6 个官方端点 + 0/999 两个哨兵」表示，官方闭区间上取值精确，仅在 3 个 0.1 宽的舍入缝内插值（90/90/70）。BMI 占总分 15%，若这个偏差不可接受，需要给表结构增加区间型档位能力或把 BMI 单列规则。不影响短板判定与桶化（BMI 已排除在 `WEAKNESS_ITEMS` 之外、桶为 `None`）。
2. **【需人工复核】男 / 大一、大二 / 引体向上 14 次** 这一格在 4 份来源中有 1 份（山大威海）渲染成 78 分，其余 2 份为 76 分且满足「大三、大四 = +1 次同分」的一致规律。已采用 76 分。这是**全表 28 个组合中唯一存在来源分歧的一格**，请用教体艺〔2014〕5 号原件确认。其余全部多源一致。
3. **【已知行为，源于 brief 的测试】差于表内最差档 → `None`（当缺测）**，不是 10 分。极端差的真实成绩（如 1000 m 跑 7 分钟）会被判为缺测而非最低分。若下游希望这种读数落到 10 分，需要 controller 改测试口径。
4. **【范围外，供后续任务注意】附加分表未纳入。** 国标学年总分满分 120，含 20 分附加分（男引体向上／男 1000 米、女仰卧起坐／女 800 米）。本表只有 0–100 的单项标准分，`score_item` 返回值上限是 100。Task 9 若要还原国标 120 分制总分，需另建加分表。
5. **【小】`raw_from_score` 对表里没有的 (项, 性别, 年级组) 组合抛 `KeyError`**（签名是 `-> float`，非 Optional）。理由：那是调用方传错组合的程序缺陷，与「学生某项缺测」不是一回事，不该静默吞掉。已写进 docstring。若 Task 6 希望它也返回 `None`，需要改签名。
6. **【小】`age_group_of` 的 19/20 岁分界是工程折算而非国标条文**（国标按年级分组）。同班同年级但年龄跨界的两个学生会被分到不同评分组。若后续能拿到真实年级字段，应优先用年级而非年龄。
---

# 修复轮（Fix Round 1）— Critical：`score_item` 越界返回 `None`

**起点**：`feature/plan-01-data-foundation` @ `0c6ac79`，工作树干净（`git status --short` 空）。
`0c6ac79` 只改了计划文档（Ruling 17 落到 `Document/…md`），**代码未改**，故缺陷仍在，本轮不存在重复提交风险。
**状态**：DONE_WITH_CONCERNS（唯一 concern 是测试条数与计划文本的 19 相差 1，见 §F.6）

## F.1 变更内容

只动了 2 个文件、共 +40/−13 行：

| 文件 | 变更 |
| --- | --- |
| `backend/app/domain/indicators.py` | `score_item` 越界改为夹到端点档位分；删除 `best = max(...)`；docstring 按更正后的契约重写（原「0 分会被当成真实短板计入 W，那是静默失效」的反向论证已删除）；循环后的兜底 `return None` 改为 `return high_score` |
| `backend/tests/domain/test_indicators.py` | 删 `test_out_of_range_value_returns_none`；加 `test_value_worse_than_worst_segment_clamps_to_floor_not_none`、`test_value_better_than_best_segment_clamps_to_ceiling`、`test_unknown_item_sex_agegroup_key_returns_none` |

核心 diff：

```python
-    best = max(score for _, score in segments)
     low_raw, low_score = segments[0]
     high_raw, high_score = segments[-1]
     if value < low_raw:
-        return low_score if low_score == best else None
+        return low_score
     if value > high_raw:
-        return high_score if high_score == best else None
+        return high_score
```

`segments` 按原始值升序，故同一句夹取对「越小越好」（50 米、耐力跑）与「越大越好」（肺活量、跳远、引体）两类项都自动落到正确端点，无需方向判断。
循环后的 `return None` 是修复前唯一剩下的第三个 `None` 出口：夹取已保证 `low_raw <= value <= high_raw`，循环必然命中，但**档位序列只有 1 个元素**的退化表会掉到那里并把表内真值判成缺测，故改为 `return high_score`（取该唯一档位的分）。现在 `None` 的出口恰好两处：`value is None`、`not segments`（键不存在）。

**未触碰**：CSV 数据、`tables.py`、`refdata.py`、架构测试、`pyproject.toml`、`.gitignore`、`README_national_standard.md`、`raw_from_score` 的 `KeyError` 行为；未加附加分表。
`README_national_standard.md` 已 grep 核对，**并未记载旧的「越界 → None」语义**（只写了 BMI 哨兵与 `ITEM_BUCKET[BMI] is None`），故无需改文档；docstring 即唯一需要同步的文本，已改。
`app/domain/` 全量 grep `datetime\.now|datetime\.today|datetime\.utcnow|date\.today|time\.time|read_csv|csv\.DictReader|\.read_text|Path\(` → **No matches found**（新增 docstring 未引入任何被禁 token），3 个架构守卫仍全绿。

## F.2 六点边界验证（探针实测，非推理）

一次性探针脚本写在 `$env:TEMP\probe_task2.py`（未进仓库），同一脚本在修复前后各跑一次。
组合：`DISTANCE_RUN` / `Sex.MALE` / `G = age_group_of(19) = "大一、大二"`。

### 点 1 — 取真实档位端点

```
distance_run/male/大一、大二  first(raw,score)= (197.0, 100)   last(raw,score)= (372.0, 10)
sprint_50m/male/大一、大二    first(raw,score)= (6.7, 100)     last(raw,score)= (10.1, 10)
bmi/male/大一、大二           first(raw,score)= (0.0, 80)      last(raw,score)= (999.0, 60)
pull_up male | female         (5.0,10)…(19.0,100) | (16.0,10)…(56.0,100)
worst = segment_thresholds(T, DISTANCE_RUN, MALE, G)[-1] = 372.0
```

### 点 2 — 修复前（pre-fix）实际观测输出

```
worst raw = 372.0 score at worst = 10
worst+120 = 492.0 score = None      ← 缺陷
6'30"=390s  score = None            ← 缺陷（题面举的真实场景）
mid 300s    score = 46
sprint_50m 999.0 → None
pull_up female 10 → None
```

### 点 3 — 修复后（post-fix）实际观测输出

```
worst raw = 372.0 score at worst = 10
worst+120 = 492.0 score = 10        ← 夹到表内最低档
6'30"=390s  score = 10              ← 夹到表内最低档
mid 300s    score = 46              ← 表内插值不变
sprint_50m 999.0 → 10               ← 差侧越界同样夹到底档（不再是 None）
pull_up female 10 → 10              ← 原为 None；male 10 → 60 不变，m != f 仍成立
```

### 点 4 — 夹取落到的是**真**国标底档（CSV 原行核对）

`backend/data/national_standard_2014.csv` 男 / 大一、大二 耐力跑（官方表1-13，男 1000 m）首尾档：

```
354: distance_run,male,大一、大二,100,197     ← 3'17" = 100 分（表内最好档）
373: distance_run,male,大一、大二,10,372      ← 6'12" = 10 分（表内最差档，官方最低档就是 10 分）
```

修复后 `492.0 s`（8'12"）与 `390.0 s`（6'30"）都返回 **10**，与 CSV 第 373 行的 `score=10` 逐字一致 —— 夹到的是真实国标底档，不是巧合值。
同理 50 米（官方表1-5）：

```
114: sprint_50m,male,大一、大二,100,6.7       ← 最好档 100 分
133: sprint_50m,male,大一、大二,10,10.1       ← 最差档 10 分
```

### 点 5 — 优侧（破表好成绩）行为未变

```
best raw = 6.7  score at best = 100
best-2.0 = 4.7  score = 100   （修复前也是 100，修复后仍是 100）
```

即 `test_value_better_than_best_segment_clamps_to_ceiling` 在修复前后都通过；本轮改的是差侧，优侧封顶行为零变化。

### 点 6 — BMI 哨兵端点使夹取成为 no-op（逐值对比）

BMI 用 `0` / `999` 两个哨兵封口（CSV 第 2、9 行），生理可达值恒在表内，故夹取分支永不触发：

| BMI | 修复前 | 修复后 |
| --- | --- | --- |
| **15.0**（极端偏瘦） | 80 | **80** |
| 17.8 | 80 | 80 |
| 20.0 | 100 | 100 |
| 23.9 | 100 | 100 |
| 24.0 | 80 | 80 |
| 27.9 | 80 | 80 |
| 28.0 | 60 | 60 |
| 35.0 | 60 | 60 |
| **38.0**（极端肥胖） | 60 | **60** |

九个取值全部逐字相同 ⇒ BMI 不受本次改动影响，官方闭区间上的精确性未被破坏。

### `None` 的两个合法来源（修复后仍成立）

```
score_item(T, VITAL_CAPACITY, None, MALE, G)                     → None   （真缺测）
score_item(T, VITAL_CAPACITY, 4000.0, MALE, "不存在的年级组")     → None   （键不存在）
```

## F.3 RED 证据（证明缺陷真实存在，新测试确实咬得住）

把 `backend/app/domain/indicators.py` 单独 stash 回旧实现，保留新测试后运行：

```
cd c:\Users\whwenhao\Desktop\Physical_Education_ims; git stash push -- backend/app/domain/indicators.py
cd backend; C:\Python\python.exe -m pytest tests/domain/test_indicators.py -q

.......F....                                                             [100%]
________ test_value_worse_than_worst_segment_clamps_to_floor_not_none _________
>       assert beyond == at_worst
E       assert None == 10
tests\domain\test_indicators.py:53: AssertionError
1 failed, 11 passed in 0.12s
```

`assert None == 10` 正是缺陷本体的可执行证据。随后 `git stash pop` 恢复修复（`git status --short` 确认两个文件都回到 modified，diff 复核与 §F.1 一致，无残留）。

## F.4 GREEN 证据

覆盖测试：

```
cd backend; C:\Python\python.exe -m pytest tests/domain/test_indicators.py tests/test_refdata.py tests/architecture -v

tests/domain/test_indicators.py::test_weakness_items_exclude_bmi PASSED  [  5%]
tests/domain/test_indicators.py::test_scored_items_count_is_seven PASSED [ 10%]
tests/domain/test_indicators.py::test_buckets_cover_all_weakness_items PASSED [ 15%]
tests/domain/test_indicators.py::test_direction_is_normalized_to_higher_is_better PASSED [ 20%]
tests/domain/test_indicators.py::test_score_at_segment_boundary PASSED   [ 25%]
tests/domain/test_indicators.py::test_sex_specific_items_differ PASSED   [ 30%]
tests/domain/test_indicators.py::test_missing_value_returns_none PASSED  [ 35%]
tests/domain/test_indicators.py::test_value_worse_than_worst_segment_clamps_to_floor_not_none PASSED [ 40%]
tests/domain/test_indicators.py::test_value_better_than_best_segment_clamps_to_ceiling PASSED [ 45%]
tests/domain/test_indicators.py::test_unknown_item_sex_agegroup_key_returns_none PASSED [ 50%]
tests/domain/test_indicators.py::test_raw_from_score_roundtrips PASSED   [ 55%]
tests/domain/test_indicators.py::test_domain_functions_are_pure_and_take_table_explicitly PASSED [ 60%]
tests/test_refdata.py::test_data_dir_points_at_backend_data PASSED       [ 65%]
tests/test_refdata.py::test_load_standard_returns_frozen_table PASSED    [ 70%]
tests/test_refdata.py::test_standard_is_cached_singleton PASSED          [ 75%]
tests/test_refdata.py::test_table_covers_every_item_sex_agegroup PASSED  [ 80%]
tests/test_refdata.py::test_missing_csv_raises_file_not_found PASSED     [ 85%]
tests/architecture/test_domain_purity.py::test_domain_has_no_forbidden_imports PASSED [ 90%]
tests/architecture/test_domain_purity.py::test_domain_has_no_clock_or_file_access PASSED [ 95%]
tests/architecture/test_domain_purity.py::test_domain_has_no_filesystem_access PASSED [100%]

20 passed in 0.05s
```

全量套件（两次，第二次把 warning 当 error）：

```
cd backend; C:\Python\python.exe -m pytest -q            → 20 passed in 0.04s
cd backend; C:\Python\python.exe -m pytest -q -W error   → 20 passed in 0.04s   # 输出洁净
```

## F.5 对下游 / 既有测试的连带影响（已逐一核过）

- `test_sex_specific_items_differ` 修复前是靠「女 10 次 → `None`」通过的（旧报告 §6 已登记此隐忧）；修复后变成「男 60 vs 女 10」，**两个整数不相等**，断言以更健康的方式成立，隐忧消除。
- `test_raw_from_score_roundtrips`、`test_score_at_segment_boundary`、`test_direction_is_normalized_to_higher_is_better` 均在表内取值，行为不变，全绿。
- 旧报告 Concern #3（「差于表内最差档 → None，极端差的真实成绩被判缺测」）**已由本轮消除**，不再需要 controller 裁决。
- Concern #1（BMI 与表结构不同构）、#2（引体向上 14 次那一格待原件复核）、#4（附加分表未纳入）、#5（`raw_from_score` 抛 `KeyError`）、#6（19/20 岁分界是工程折算）**本轮未触碰，依旧有效**。

## F.6 Concern（本轮唯一一条）

**测试条数 20 而非计划文本写的 19。** 计划 Step 5 的 `19 passed（indicators 11 + refdata 5 + architecture 3）` 是在「indicators 10 − 1 删 + 2 新增 = 11」的前提下算的，没有计入本轮 dispatch 另外要求的「若没有测试覆盖『未知 (item, sex, group) 键返回 None』则补一条」。旧测试文件确实没有这条覆盖，故按 dispatch 指令补了 `test_unknown_item_sex_agegroup_key_returns_none`，indicators 变 12、总数变 **20 passed**。这是 brief 契约（`None` 的两个合法来源之一）此前无测试看守的真实缺口，宁可多一条也不留空；若 controller 坚持 19 这个数字，删掉该条即可，其余 19 条与计划逐字一致。

> **【修复轮 2 补注】** 本节（§F.1–§F.6）此前只存在于编辑器未落盘的缓冲区中，磁盘上的报告文件只有 §1–§7；修复轮 2 已将其原样补回磁盘。其中 §F.5 提到的 `test_score_at_segment_boundary` 已在修复轮 2 按 Ruling 18 删除并拆分为两条（见 §R2.9），§F.6 的 20 条也已在修复轮 2 增至 30 条。

---

# 修复轮 2（Fix Round 2）— Ruling 18/19/20/21 与 Minor 7/8/9/10/11

**起点**：`feature/plan-01-data-foundation` @ `329b1f5`，`git status --short` 为空（干净树）。
**重复提交检查**：`git log --oneline -4` 显示 `329b1f5 / 2cb40ff / 0c6ac79 / 0f2d60d`，本轮 8 条发现的改动**在起点全部不存在**（探针实测：`score_item` 仍在插值、`raw_from_score(BMI,80)` 仍返回 `0.0`、`refdata` 仍无枚举校验、`type(t.segments)` 仍是 `dict`、`segment_thresholds` 仍返回 `[]`、`FORBIDDEN_IO` 仍是 9 个 token）。**无一条已预先存在，故无跳过项，也不存在重复提交风险。**
**权威依据**：`Document/2026-09-28-实施计划01-数据基座与分层引擎.md` Task 2 Step 4（Ruling 18 就低取档、Ruling 17 越界夹取）与 Task 5 Step 3–4（Ruling 21 归清洗层）。brief 已过期，一律以计划为准。
**CSV 数据零改动**：`git hash-object backend/data/national_standard_2014.csv` = `7a65f5bb25a9b7c48d251589c6f57f42b7d3fc46`，与 `HEAD:` 同一 blob，逐字节相同。

**状态**：DONE_WITH_CONCERNS（3 条 concern，见 §R2.10；均为口径确认类，无未完成工作）

## R2.0 变更总览

```
backend/app/domain/indicators.py                 | 114 ++++++++-----   （Finding 1/2/4/7）
backend/app/domain/tables.py                     |   8 +-              （Finding 5 的类型标注）
backend/app/refdata.py                           |  47 +++++-          （Finding 3/5）
backend/data/README_national_standard.md         |  72 ++++++---       （Finding 8）
backend/tests/architecture/test_domain_purity.py |   6 +-              （Finding 6）
backend/tests/domain/test_indicators.py          | 104 ++++++++++--    （测试更新）
backend/tests/test_refdata.py                    |  71 ++++++++--      （测试更新）
7 files changed, 350 insertions(+), 72 deletions(-)
```

**未触碰**：`national_standard_2014.csv`（含任何数值）、`pyproject.toml`、`.gitignore`、Task 2 以外的任何文件；未实现 Task 5 的清洗规则（本轮只落 docstring 前置条件）。

---

## R2.1 Finding 1（Important，Ruling 18）— 线性插值 → 就低取档阶梯查表

### 改动

`score_item` 的插值循环整段删除，替换为阶梯查表；`round()` 调用消失，`best` 早在修复轮 1 已删、本轮无残留：

```python
    # 上面两次夹取已保证 low_raw <= value <= high_raw，故下面两个生成式必然非空
    if _lower_is_better(segments):
        return next(score for raw, score in segments if raw >= value)
    return next(score for raw, score in reversed(segments) if raw <= value)
```

方向由新增的私有函数从表推断，不按项硬编码：

```python
def _lower_is_better(segments: tuple[tuple[float, int], ...]) -> bool:
    scores = [score for _, score in segments]
    return all(nxt <= cur for cur, nxt in zip(scores, scores[1:]))
```

越界夹取（Ruling 17）的两个分支 `if value < low_raw: return low_score` / `if value > high_raw: return high_score` **一字未动**；`None` 的两个出口（`value is None`、`not segments`）也一字未动。

> ⚠️ **方向推断与计划字面表述的一处刻意偏离，见 §R2.10 Concern 1**（只影响 BMI，26 个单调组两种写法完全等价）。

### 修复前 / 修复后实测（同一探针脚本 `$env:TEMP\probe_task2_r2.py`，改前改后各跑一次）

**立定跳远 男／大一、大二（越大越好）**

| 原始值 | 修复前（插值） | 修复后（就低取档） | CSV 依据 |
| --- | --- | --- | --- |
| 208.0 | 60 | **60** | 第 288 行 `standing_jump,male,大一、大二,60,208` |
| 209.0 | 60 | **60** | 落在 208 档 |
| **210.0** | **61** ← 国标无此分 | **60** ✅ | 最大 `raw ≤ 210` 是 208（第 288 行，60 分） |
| 211.0 | 62 ← 国标无此分 | **60** | 同上 |
| 212.0 | 62 | **62** | 第 287 行 `standing_jump,male,大一、大二,62,212` |

**耐力跑 男／大一、大二（越小越好）**

| 原始值 | 修复前（插值） | 修复后（就低取档） | CSV 依据 |
| --- | --- | --- | --- |
| 272.0 | 60 | **60** | 第 368 行 `distance_run,male,大一、大二,60,272` |
| 275.0 | 58 ← 国标无此分 | **50** | 最小 `raw ≥ 275` 是 292（第 369 行，50 分） |
| **280.0** | **56** ← 偏 6 分／20% 权重 | **50** ✅ | 最小 `raw ≥ 280` 是 292（第 369 行 `distance_run,male,大一、大二,50,292`） |
| 290.0 | 51 ← 国标无此分 | **50** | 同上 |
| 292.0 | 50 | **50** | 第 369 行 |

两个题面点位的 after 值与 CSV 行逐字一致：**210 cm → 60 分 = 第 288 行的 `score`**；**280 s → 50 分 = 第 369 行的 `score`**。
floor／ceiling 端点行也已核对：立定跳远 男／大一、大二 首末档为第 274 行 `100,273` 与第 293 行 `10,183`；耐力跑同组为第 354 行 `100,197` 与第 373 行 `10,372`。

### 连带修掉的两个缺陷（已显式验证）

**BMI 0.1 舍入缝**（CSV 第 2–9 行为男／大一、大二的 8 个档位）：

| BMI | 修复前 | 修复后 | 就低取档依据 |
| --- | --- | --- | --- |
| 15.0 | 80 | **80** | 最大 `raw ≤ 15.0` = 0（第 2 行哨兵，80 分） |
| 17.8 | 80 | **80** | 第 3 行 `bmi,male,大一、大二,80,17.8` |
| **17.85** | **90** ← 国标无此分 | **80** ✅ | 最大 `raw ≤ 17.85` = 17.8（第 3 行，低体重 80 分） |
| 23.9 | 100 | **100** | 第 5 行 `bmi,male,大一、大二,100,23.9` |
| **23.94** | **92** ← 国标无此分 | **100** ✅ | 最大 `raw ≤ 23.94` = 23.9（第 5 行）——该生按国标确为「正常」 |
| 24.0 | 80 | **80** | 第 6 行 `bmi,male,大一、大二,80,24` |
| **27.95** | **70** ← 国标无此分 | **80** | 最大 `raw ≤ 27.95` = 27.9（第 7 行，超重 80 分） |
| 28.0 | 60 | **60** | 第 8 行 `bmi,male,大一、大二,60,28` |
| 38.0 | 60 | **60** | 最大 `raw ≤ 38.0` = 28（第 8 行） |

**`round()` 银行家舍入**：探针确认 `round(58.5) == 58`、`round(59.5) == 60`（Python 的偶数舍入）。修复后 `indicators.py` 里已无任何 `round(` 调用（`grep` 只命中 docstring 中那句说明文字），该偏差路径整体消失。

### 「非官方分」的总量证据

对全部 7 项 × 2 性别在 `[首档 raw, 末档 raw]` 上各扫 201 点，统计返回值不属于该组 CSV 分数集的次数：

```
修复前：非官方分数出现次数合计 = 1666
        例：vital_capacity/male raw=2313.7 → 11（官方分集为 {10,20,30,…,100}）
修复后：非官方分数出现次数合计 = 0
```

这条扫描已固化为测试 `test_score_item_only_returns_official_discrete_scores`（含 2 个越界点），即「本可以抓住插值缺陷的那条测试」。

---

## R2.2 Finding 2（Important，Ruling 19）— `raw_from_score` 不再泄漏 BMI 哨兵

### 修复前实测（缺陷本体）

```
raw_from_score(bmi, 80) = 0.0   回代 score_item -> 80      ← 0.0 是 CSV 第 2 行的哨兵
raw_from_score(bmi, 100) = 17.9 回代 score_item -> 100
raw_from_score(bmi, 60) = 28.0  回代 score_item -> 60
```

`0.0` 来自 CSV 第 2 行 `bmi,male,大一、大二,80,0`；80 分是 BMI 最常见的目标分（第 3 行低体重与第 6 行超重都是 80）。回代得 80 ⇒ 往返测试恒绿，缺陷被完美掩盖。

### 修复后实测

```
raw_from_score(bmi, 80)  raised ValueError: bmi 的档位得分沿原始值非单调（区间型映射），
  同一得分对应多段互不相邻的原始值区间，无法按目标分反查唯一原始值；
  请直接生成身高与体重、算出该指标后用 score_item 正查得分
raw_from_score(bmi, 100) raised ValueError: （同上）
raw_from_score(bmi, 60)  raised ValueError: （同上）
```

男女两个性别都由 `test_raw_from_score_rejects_non_monotonic_item` 看守。

### 单调项改为「就低映射官方档 → 返回带中点」

| 调用 | 修复前 | 修复后 | 说明 |
| --- | --- | --- | --- |
| `raw_from_score(standing_jump, 80)` | 248.0（回代 80） | **252.0**（回代 80） | 80 档区间 `[248, 256)` 的中点；CSV 第 278 行 `80,248`、第 277 行 `85,256` |
| `raw_from_score(standing_jump, 73)` | 234.0（回代 **73**） | 234.0（回代 **72**） | 73 非官方档，就低落到 72 档（CSV 第 282 行 `72,232`、第 281 行 `74,236`），区间 `[232,236)` 中点 234 |
| `raw_from_score(pull_up_or_sit_up, 73)` | 13.25（回代 **73**） | 13.5（回代 **72**） | 男引体向上稀疏档：72@13（第 440 行）、76@14（第 439 行），带 `[13,14)` 中点 13.5 |
| `raw_from_score(distance_run, 80)` | 222.0（回代 80） | **218.0**（回代 80） | 越小越好，80 档区间 `(214, 222]` 中点；CSV 第 358 行 `80,222`、第 357 行 `85,214` |
| `raw_from_score(sprint_50m, 80)` | 7.1（回代 80） | **7.05**（回代 80） | 80 档区间 `(7.0, 7.1]` 中点；CSV 第 118 行 `80,7.1`、第 117 行 `85,7` |
| `raw_from_score(vital_capacity, 97)` | 4968.0（回代 **97**） | 4980.0（回代 **95**） | 97 非官方档，就低落到 95 档 |

`KeyError` 保留：`raw_from_score(T, VITAL_CAPACITY, 80, MALE, "不存在的年级组")` 修复前后都抛 `KeyError: ('vital_capacity', 'male', '不存在的年级组')`。

`test_raw_from_score_roundtrips` 已从「`abs(... - 80) <= 1`」收紧为：对 6 个短板项 × 2 性别 × **该组每一个官方档**，`score_item(raw_from_score(档)) == 档` 精确相等（共 230 个断言，全绿）。

---

## R2.3 Finding 3（Important，Ruling 20）— 加载期校验 CSV 字符串

### 改动

`load_standard` 对每行的三个分组列逐一校验，失败即抛 `ValueError` 并带上 **CSV 行号 + offending 值 + 合法值集**；行号取 `csv.DictReader.line_num`（比 `enumerate` 准，能处理跨行引号字段）：

```python
        for row in reader:
            line_no = reader.line_num
            try:
                item = ScoredItem(row["item"])
            except ValueError:
                raise ValueError(
                    f"国标评分表 {csv_path} 第 {line_no} 行 item 值非法: {row['item']!r}；"
                    f"合法值: {[i.value for i in ScoredItem]}"
                ) from None
            ...  # sex 同构；age_group 走 `not in AGE_GROUPS`
```

### 修复前 / 修复后（RED 证据即修复前行为）

在 `tmp_path` 造 4 行小 CSV（表头 + 2 行合法 + 第 4 行非法），三种非法列各参数化一例：

| 注入 | 修复前 | 修复后 |
| --- | --- | --- |
| `item = vital_capacty` | **静默加载成功**（`DID NOT RAISE ValueError`）——该行的档被摘到孤儿键，正确组少一档 | `ValueError: … 第 4 行 item 值非法: 'vital_capacty'；合法值: ['bmi', …]` |
| `sex = Male` | 同上静默通过 | `ValueError: … 第 4 行 sex 值非法: 'Male'；合法值: ['male', 'female']` |
| `age_group = 大一-大二` | 同上静默通过 | `ValueError: … 第 4 行 age_group 值非法: '大一-大二'；合法值: ['大一、大二', '大三、大四']` |

### 覆盖测试从「`>= 2` 档」升级为精确集合断言

`test_table_covers_every_item_sex_agegroup` 现在断言两件事：

1. `set(t.segments) == {(i.value, s.value, ag) for i in ScoredItem for s in Sex for ag in AGE_GROUPS}`
   ——**恰好相等**，0 孤儿键、0 缺失组合（7 × 2 × 2 = 28 个键）。
2. 每组的档位数 == 该组在 CSV 里的行数。行数由测试内 `_csv_group_counts()` **独立再数一遍**（不复用 `load_standard` 的解析路径），并交叉校验总数：
   `assert total == sum(per_group.values()) == sum(len(v) for v in t.segments.values())`（502 == 502 == 502）。
   任何一组不等会以 `{key: (表内档数, CSV 行数)}` 的形式打印出来。

真实 CSV 下该测试通过 ⇒ 当前 28 组无孤儿、无缺失、档数与行数逐组吻合。

---

## R2.4 Finding 4（Important，Ruling 21）— 只写进 docstring，**未改 `score_item` 行为**

按计划 Task 5 Step 3–4，处置归清洗层的逐字段 `non_positive_is_missing`，本任务只让前置条件在调用点可见。

**行为刻意保持不变**（探针实测，修复前后完全一致）：

```
sprint_50m     0.0 -> 100      distance_run   0.0 -> 100     ← 低侧夹取把 0 抬成满分（20%+20% 权重）
standing_jump  0.0 -> 10       vital_capacity 0.0 -> 10       ← 越大越好的项则是压到底档
```

`score_item` docstring 新增段落（节选）：

> **前置条件：``value`` 必须已经是清洗过的值**（Ruling 21）。本函数对越界只做夹取，不判断读数是否物理可能，因此调用方必须先把物理上不可能的读数转成 ``None`` 再传入：高侧如 50 米跑 999 秒（夹到底档 10 分，压分），低侧如 50 米跑 0.0 秒——``0`` 是数值列最常见的缺测占位，而低侧夹取对「越小越好」的项意味着**低值得高分**，实测 50 米跑与耐力跑的 0.0 秒都返回 **100 分**……这比高侧更危险，因为它抬分而非压分。处置不能放在这里一刀切拒绝 ``<= 0``（引体向上 0 次、坐位体前屈 −1.3 cm 都是合法真实值），必须由 Task 5 的清洗层按 ``indicator_ranges.yaml`` 的逐字段 ``non_positive_is_missing`` 标记完成。

高侧例子（999 秒）与低侧例子（0.0 秒）并列给出。`README_national_standard.md` 的「查表口径」一节也同步记了这条前置条件。

---

## R2.5 Finding 5（Minor 9）— 表真正只读

`load_standard` 的返回值改为 `StandardTable(segments=types.MappingProxyType({...}))`；`tables.py` 的字段标注相应从 `dict[...]` 放宽为 `collections.abc.Mapping[...]`（**这是本轮对 `tables.py` 的唯一改动**，符合范围约束「除 MappingProxyType  typing 所需外不动 tables.py」）。底层 dict 是 `load_standard` 的局部变量、不外泄，故只读视图有效。

| | 修复前 | 修复后 |
| --- | --- | --- |
| `type(t.segments)` | `dict` | **`mappingproxy`** |
| `t.segments[k] = ((0.0, 0),)` | **写入成功**，进程级单例被就地污染 | `TypeError: 'mappingproxy' object does not support item assignment` |
| `del t.segments[k]` | 成功 | `TypeError` |
| `t.segments = {}` | `FrozenInstanceError` | `FrozenInstanceError`（不变） |

新测试 `test_segments_mapping_is_read_only` 同时看守赋值与删除两条路径（`pytest.raises(TypeError)`）。

---

## R2.6 Finding 6（Minor 10）— 架构守卫 I/O token 扩表 + 双向变异检查

`FORBIDDEN_IO` 从 9 个 token 增至 15 个，新增：`"import os"`、`"os.listdir"`、`"os.walk"`、`"__file__"`、`"json.load"`、`"pickle.load"`。

**先确认新增 token 不误伤现状**：对 `backend/app/domain/*.py` 全量 grep
`datetime\.now|datetime\.today|datetime\.utcnow|date\.today|time\.time|__file__|import os|os\.listdir|os\.walk|json\.load|pickle\.load|read_csv|csv\.reader|Path\(`
→ **No matches found**。`domain/__init__.py` 为空文件，`tables.py` 只 import `collections.abc` 与 `dataclasses`，`indicators.py` 只 import `enum` 与 `app.domain.tables`。**没有任何 domain 模块引用 `__file__`**，新 token 安全。

**变异检查（双向，都实测）**：在 `app/domain/indicators.py` 顶部植入

```python
import os
_MUTATION_PROBE = os.listdir(".")
```

- **旧 token 表**（把 `test_domain_purity.py` 单独 `git stash push` 回 HEAD 版，保留植入）：
  ```
  cd backend; C:\Python\python.exe -m pytest tests/architecture -q
  ...                                                                      [100%]
  3 passed in 0.02s
  ```
  ⇒ **三个守卫全绿**，正是 Finding 描述的漏洞：`import os; os.listdir(...)` 能大摇大摆走进 domain。
- **新 token 表**（`git stash pop` 恢复，植入仍在）：
  ```
  cd backend; C:\Python\python.exe -m pytest tests/architecture -q
  >       assert offenders == []
  E       AssertionError: assert ['indicators....y:os.listdir'] == []
  E         Left contains 2 more items, first extra item: 'indicators.py:import os'
  E         + [ 'indicators.py:import os', 'indicators.py:os.listdir', ]
  FAILED tests/architecture/test_domain_purity.py::test_domain_has_no_filesystem_access
  1 failed, 2 passed in 0.09s
  ```
  ⇒ **守卫咬人**，且两个新 token 都被点到名。注意 `test_domain_has_no_forbidden_imports` 仍是 passed——`FORBIDDEN` 集合里没有 `os`，抓住它的正是新扩的 `FORBIDDEN_IO`，这与 Finding 的判断一致。
- **清除植入**：删掉那两行后 `pytest tests/architecture -q` → `3 passed`；再跑一次完整探针，输出与植入前的 `probe_after.txt` **逐行 IDENTICAL**（`Compare-Object` 无差异），确认变异零残留。两次 `git stash` 均已 `pop`，`git stash list` 为空。

---

## R2.7 Finding 7（Minor 11）— 「键不存在」契约对齐

`segment_thresholds` 从 `_segments_of(...) or ()` + 返回 `[]` 改为直接下标取值，让 `KeyError` 自然抛出：

```python
    segments = table.segments[(item.value, sex.value, age_group)]
    return [float(raw) for raw, _ in segments]
```

| 函数 | 修复前 | 修复后 |
| --- | --- | --- |
| `score_item` | `None` | `None`（不变——它的 `None` 是「缺测」语义的一部分） |
| `raw_from_score` | `KeyError` | `KeyError`（不变） |
| `segment_thresholds` | **`[]`** → 调用方 `[0]`/`[-1]` 退化成看不出所以然的 `IndexError` | **`KeyError: ('vital_capacity', 'male', '不存在的年级组')`** |

新测试 `test_raw_from_score_and_thresholds_raise_keyerror_for_absent_key` 一次看守两个函数。
调用方影响：仓内唯一调用者是 `refdata.segment_count` 与测试，均以合法键调用，无需连带修改。

---

## R2.8 Finding 8（Minor 7、8）— README 四处事实更正

`backend/data/README_national_standard.md`：

1. **来源份数**：「三份…三者相互独立」→「**四份**…**四者**相互独立」（下面本就列了 4 条）。另新增一条列出复核阶段的 2 份新来源（北京化工大学、海南大学）。
2. **表号归属**：原第 49 行「表号取自长春理工／山大威海转载件的编号」→「表号取自**长春理工**转载件的编号。山大威海与广东工业把引体向上／耐力跑编为 **1-13** 与 **1-15／1-16**」——山大威海并非 1-11/1-12 的使用者，原句是事实错误。
3. **争议格结案**：「待复核」一节改写为「**复核结论（原「待复核」一节，已结案）**」，记明男／大一、大二／引体向上 14 次 = **76 分** 由三份独立来源（北京化工大学 表1-6、广东工业 表1-13、海南大学）一致印证，山大威海的 78 分是其自身表格渲染错误，**不再等官方原件**；并记录全部 28 个组合逐格复核 0 处分歧、CSV 一个数值都没动。顶部的 ⚠️ 提示相应改为 ℹ️（已无待复核疑点）。
4. **Ruling 18 入档**：新增「## 查表口径：就低取档，不做插值（Ruling 18）」一节，写明越大越好／越小越好的取档规则、越界夹取、以及「系统单项分与学校官方体测报表**逐格可对账**」这一后果，并把 210 cm → 61（官方 60）、280 s → 56（官方 50）两个实测反例留在文档里。

**顺带修掉本轮改动直接使其失真的 3 处旧文本**（不改就是留下自相矛盾的文档）：

- 原第 53 行「这样**线性插值**才有意义」→「这样档位阈值才能直接按数值排序与比较（查表口径是就低取档）」。
- 原第 98–99 行「落在缝内会被**线性插值成 90 / 90 / 70**」→ 改为实测值 17.85 → **90**、23.94 → **92**、27.95 → **70**，并写明就低取档后依次落到 `17.8→80`、`23.9→100`、`27.9→80`，**该偏差已由 Ruling 18 关闭**。（旧文本的中间那个 90 也不准：23.94 插值出来是 92，90 只在缝中点 23.95 才出现。）
- 原第 100–102 行「**若不可接受需要 controller 裁决**」→ 旧报告 Concern #1 就此**结案**；同时补记 Ruling 19（`raw_from_score` 对 BMI 抛 `ValueError` 的理由与哨兵泄漏后果）与 Ruling 21 前置条件。

---

## R2.9 测试改动与 TDD 证据

### 语义变了、必须改的既有断言

- **删除** `test_score_at_segment_boundary`（断言 `at_thr == just_worse`）。那是为**插值**做的抗浮点漂移检查；就低取档下刚越过阈值 legitimately 掉一档，该断言现在是错的。实测旧断言点位：`sprint_50m thr[3] = 7.0`，`at = 85`、`+1e-9 = 85`（修复前）→ `at = 85`、`+1e-6 = 80`（修复后，CSV 第 118 行 `80,7.1`）。按 dispatch 拆成两条替代：
  - `test_score_at_exact_threshold_returns_that_thresholds_score`：对 50 米跑与立定跳远，遍历**该组每一个档位**，断言 `score_item(raw) == 表里列出的 score`（阈值与期望分都从 `T.segments` 取，不硬编码）。
  - `test_score_just_past_threshold_drops_one_band`：越小越好项 `thr + EPS` 掉到下一档、越大越好项 `thr - EPS` 同样掉一档；两侧都先断言相邻阈值间距 > EPS 且分数确实更低，避免 EPS 跨过两档造成假绿。
- **收紧** `test_raw_from_score_roundtrips`：从 `abs(... - 80) <= 1` 的单点容差，改为 6 项 × 2 性别 × 每组全部官方档的**精确相等**。
- **保留并复验** `test_value_worse_than_worst_segment_clamps_to_floor_not_none` 与 `test_value_better_than_best_segment_clamps_to_ceiling`（Ruling 17 不变）。两条都以 `segment_thresholds` 自推导端点，故无需改文本；已实测其期望值在阶梯查表下仍成立：
  ```
  distance_run worst=372.0 at=10 +120=10      （CSV 第 373 行 10,372 → floor 档未变）
  sprint_50m   best=6.7   at=100 -2=100       （CSV 第 114 行 100,6.7 → ceiling 档未变）
  ```
- `test_domain_functions_are_pure_and_take_table_explicitly` 用的 230.0 cm 在修复前得 71（插值）、修复后得 70（第 283 行 `70,228`）；该测试只断言 `a == b and a is not None`，两种语义下都成立，未改。
- `test_sex_specific_items_differ` 修复前后都是「男 60 vs 女 10」，未改。

### 新增测试（6 条）

| 测试 | 看守的发现 |
| --- | --- |
| `test_score_item_only_returns_official_discrete_scores` | Finding 1（本可抓住插值缺陷的那条） |
| `test_bmi_unrounded_value_scores_correctly` | Finding 1 的 BMI 缝（15.0→80、17.85→80、23.94→100、24.0→80、28.0→60、38.0→60，男） |
| `test_raw_from_score_maps_unofficial_target_down_to_official_band` | Finding 2 的就低映射 |
| `test_raw_from_score_rejects_non_monotonic_item` | Finding 2 的 `ValueError` |
| `test_raw_from_score_and_thresholds_raise_keyerror_for_absent_key` | Finding 7 |
| `test_segments_mapping_is_read_only` | Finding 5 |

外加 `test_malformed_csv_raises_with_line_number` 参数化 3 例（Finding 3）与强化后的 `test_table_covers_every_item_sex_agegroup`（Finding 3）。

**「不得硬编码 CSV 数值」的落实**：所有新测试的阈值与档位分一律从 `T.segments` / `segment_thresholds` 推导；文件头写明该纪律。唯一例外是 `test_bmi_unrounded_value_scores_correctly`，其注释明确标注「**本文件唯一允许硬编码 CSV 数值的测试**」并说明理由——它钉的正是国标公布的 BMI 区间端点（`≤17.8 / 17.9~23.9 / 24.0~27.9 / ≥28.0`），这些端点本身就是被测口径，无法从 `segment_thresholds` 推导。`test_raw_from_score_maps_unofficial_target_down_to_official_band` 里的 `72 / 70` 不是 CSV 原始值而是**由 `max(s for s in official if s <= requested)` 现场推导后再钉住**的结果，同一断言里两件事都验。

### RED（把实现 stash 回 HEAD、只留新测试）

```
cd c:\Users\whwenhao\Desktop\Physical_Education_ims
git stash push -- backend/app/domain/indicators.py backend/app/domain/tables.py backend/app/refdata.py
cd backend; C:\Python\python.exe -m pytest tests/domain tests/test_refdata.py -q

FAILED tests/domain/test_indicators.py::test_score_just_past_threshold_drops_one_band
       - AssertionError: assert 85 == 80
FAILED tests/domain/test_indicators.py::test_score_item_only_returns_official_discrete_scores
       - AssertionError: vital_capacity/male/大一、大二 raw=2313.7 得到非官方分 11
FAILED tests/domain/test_indicators.py::test_bmi_unrounded_value_scores_correctly
       - AssertionError: assert 90 == 80          （17.85 被插值成 90）
FAILED tests/domain/test_indicators.py::test_raw_from_score_maps_unofficial_target_down_to_official_band
       - AssertionError: assert 73 == 72
FAILED tests/domain/test_indicators.py::test_raw_from_score_rejects_non_monotonic_item
       - Failed: DID NOT RAISE ValueError
FAILED tests/domain/test_indicators.py::test_raw_from_score_and_thresholds_raise_keyerror_for_absent_key
       - Failed: DID NOT RAISE KeyError
FAILED tests/test_refdata.py::test_segments_mapping_is_read_only
       - Failed: DID NOT RAISE TypeError
FAILED tests/test_refdata.py::test_malformed_csv_raises_with_line_number[item-vital_capacty]
       - Failed: DID NOT RAISE ValueError
FAILED tests/test_refdata.py::test_malformed_csv_raises_with_line_number[sex-Male]
       - Failed: DID NOT RAISE ValueError
FAILED tests/test_refdata.py::test_malformed_csv_raises_with_line_number[age_group-大一-大二]
       - Failed: DID NOT RAISE ValueError
10 failed, 17 passed in 0.20s
```

8 条发现里有 6 条（1、2、3、5、7 与 Finding 1 的 BMI 缝）在 RED 里各自被至少一条断言咬住，`assert 90 == 80`、`assert 73 == 72`、`得到非官方分 11` 都是缺陷本体的可执行证据。
`test_table_covers_every_item_sex_agegroup` 与 `test_score_at_exact_threshold_returns_that_thresholds_score` 在 RED 里通过是**预期的**：真实 CSV 本来就干净（28 组无孤儿），而「恰好在档位上」在插值实现下也成立——前者防的是未来的录入错误，后者防的是未来的口径回退。
随后 `git stash pop` 恢复，`git status --short` 与 `git diff --stat` 复核，无残留。

### GREEN

```
cd c:\Users\whwenhao\Desktop\Physical_Education_ims\backend
C:\Python\python.exe -m pytest tests/domain tests/test_refdata.py tests/architecture -v

tests/domain/test_indicators.py::test_weakness_items_exclude_bmi PASSED                                    [  3%]
tests/domain/test_indicators.py::test_scored_items_count_is_seven PASSED                                   [  6%]
tests/domain/test_indicators.py::test_buckets_cover_all_weakness_items PASSED                              [ 10%]
tests/domain/test_indicators.py::test_direction_is_normalized_to_higher_is_better PASSED                   [ 13%]
tests/domain/test_indicators.py::test_score_at_exact_threshold_returns_that_thresholds_score PASSED        [ 16%]
tests/domain/test_indicators.py::test_score_just_past_threshold_drops_one_band PASSED                      [ 20%]
tests/domain/test_indicators.py::test_score_item_only_returns_official_discrete_scores PASSED              [ 23%]
tests/domain/test_indicators.py::test_bmi_unrounded_value_scores_correctly PASSED                          [ 26%]
tests/domain/test_indicators.py::test_sex_specific_items_differ PASSED                                     [ 30%]
tests/domain/test_indicators.py::test_missing_value_returns_none PASSED                                    [ 33%]
tests/domain/test_indicators.py::test_value_worse_than_worst_segment_clamps_to_floor_not_none PASSED       [ 36%]
tests/domain/test_indicators.py::test_value_better_than_best_segment_clamps_to_ceiling PASSED              [ 40%]
tests/domain/test_indicators.py::test_unknown_item_sex_agegroup_key_returns_none PASSED                    [ 43%]
tests/domain/test_indicators.py::test_raw_from_score_roundtrips PASSED                                     [ 46%]
tests/domain/test_indicators.py::test_raw_from_score_maps_unofficial_target_down_to_official_band PASSED   [ 50%]
tests/domain/test_indicators.py::test_raw_from_score_rejects_non_monotonic_item PASSED                     [ 53%]
tests/domain/test_indicators.py::test_raw_from_score_and_thresholds_raise_keyerror_for_absent_key PASSED   [ 56%]
tests/domain/test_indicators.py::test_domain_functions_are_pure_and_take_table_explicitly PASSED           [ 60%]
tests/test_refdata.py::test_data_dir_points_at_backend_data PASSED                                         [ 63%]
tests/test_refdata.py::test_load_standard_returns_frozen_table PASSED                                      [ 66%]
tests/test_refdata.py::test_segments_mapping_is_read_only PASSED                                           [ 70%]
tests/test_refdata.py::test_standard_is_cached_singleton PASSED                                            [ 73%]
tests/test_refdata.py::test_table_covers_every_item_sex_agegroup PASSED                                    [ 76%]
tests/test_refdata.py::test_malformed_csv_raises_with_line_number[item-vital_capacty] PASSED               [ 80%]
tests/test_refdata.py::test_malformed_csv_raises_with_line_number[sex-Male] PASSED                         [ 83%]
tests/test_refdata.py::test_malformed_csv_raises_with_line_number[age_group-大一-大二] PASSED               [ 86%]
tests/test_refdata.py::test_missing_csv_raises_file_not_found PASSED                                       [ 90%]
tests/architecture/test_domain_purity.py::test_domain_has_no_forbidden_imports PASSED                      [ 93%]
tests/architecture/test_domain_purity.py::test_domain_has_no_clock_or_file_access PASSED                   [ 96%]
tests/architecture/test_domain_purity.py::test_domain_has_no_filesystem_access PASSED                      [100%]

============================= 30 passed in 0.09s ==============================
```

全量套件（含把 warning 当 error）：

```
cd backend; C:\Python\python.exe -m pytest -q
..............................                                           [100%]
30 passed in 0.08s

cd backend; C:\Python\python.exe -m pytest -q -W error
..............................                                           [100%]
30 passed in 0.07s
```

**测试条数：20 → 30**（indicators 12 → 18、refdata 5 → 9、architecture 3 → 3）。计划 Step 5 写的「20 passed」是修复轮 1 的数字，本轮按 dispatch 要求净增 10 条，属预期偏差。
IDE 诊断（`GetDiagnostics`，全仓）：`[]`，无 error／warning。

---

## R2.10 Concerns（3 条，均为口径确认，无未完成工作）

### 1【需 controller 确认】BMI 的方向推断与计划字面表述不一致——**这是 dispatch 预告的「方向推断对某项可能歧义」的那一项**

计划 Task 2 Step 4 写的是「从表推断方向（`scores[0] < scores[-1]` 为『越大越好』）」。BMI 男组的档位序列沿 raw 升序是
`(0,80) (17.8,80) (17.9,100) (23.9,100) (24.0,80) (27.9,80) (28.0,60) (999,60)`（CSV 第 2–9 行），
故 `scores[0] = 80`、`scores[-1] = 60`，`80 < 60` 为假 ⇒ 按计划字面 BMI 会走**越小越好**分支（取最小的 `raw_i >= value`）。但该分支给出：

| BMI | 计划字面规则（越小越好） | dispatch 要求的断言 | 国标正解 |
| --- | --- | --- | --- |
| 17.85 | 17.9 → **100** | **80** | 80（低体重 ≤17.8） |
| 23.94 | 24.0 → **80** | **100** | 100（正常 17.9~23.9） |

即计划字面规则与 dispatch 明确要求的新测试 `test_bmi_unrounded_value_scores_correctly`（`23.94 → 100`）、以及 Finding 1 正文里那句「Under step lookup, "largest raw ≤ 23.94" is 23.9 → **100**, which is correct」**直接冲突**。dispatch 同时要求「不得为了通过而弱化测试」，故按 dispatch 的显式期望值实现。

采用的推断式是「**沿 raw 升序得分全程单调不增 → 越小越好；否则 → 越大越好**」（`_lower_is_better`）：

- 对 26 个单调组（除 BMI 外的 6 项 × 2 性别 × 2 年级组，其中 50 米跑与耐力跑单调不增、其余单调不减），它与计划的 `scores[0] < scores[-1]` **完全等价**，逐组实测无差异。
- 只对 BMI 的 2 个组不同，且给出的正是 dispatch 要求的口径。语义上也站得住：BMI 的 CSV 落法是「**从该端点起（含）到下一端点前**取该端点的分」，那本来就是「最大的 `raw_i <= value`」。
- 结果：BMI 在全部生理可达值上都返回官方档分（15.0→80、17.85→80、23.94→100、24.0→80、27.95→80、28.0→60、38.0→60），三个 0.1 舍入缝的偏差彻底关闭，旧报告 Concern #1 结案。

若 controller 认为必须严格照计划字面（BMI 走越小越好），则 `test_bmi_unrounded_value_scores_correctly` 的 17.85 与 23.94 两个期望值需要改成 100 与 80，且要接受「BMI 23.94 的正常学生被判成超重 80 分」。**已按 dispatch 实现，未自行发明第三种行为。**

### 2【口径确认】dispatch 里「73 → 70 档」应为「73 → 72 档」

dispatch 要求「add a case for a non-official target (e.g. 73) asserting it maps 就低 to the 70 档」。实测：全部 7 项 × 2 性别的官方分集都含 **72**（如立定跳远男组 CSV 第 282 行 `72,232`；男引体向上第 440 行 `72,13`），故「不超过 73 的最大官方档」是 **72**，不是 70。已按 Finding 2 正文给出的算法（largest official 档 ≤ requested）实现，并把测试写成两例：`73 → 72`、`71 → 70`（71 才真正落到 70 档），后者覆盖了 dispatch 想验的「落到 70 档」这件事。测试内已就地注明这一出入，未弱化任何断言。

### 3【给 Task 6 的前置提醒】反查返回的是**区间中点**，整数次数项会是 `.5`

`raw_from_score(pull_up_or_sit_up, 72, MALE, G)` 现在返回 **13.5**（带 `[13, 14)` 的中点），回代得 72 分。Task 6 若把次数四舍五入或向上取整成 14，就会跨到 76 档（CSV 第 439 行），目标分失真。同理 `raw_from_score(vital_capacity, 97, ...)` 现在返回 95 档的值而非 97 分对应的插值——**任何「请求分 == 回代分」的下游假设都不再成立**，Task 6 必须按「请求分会就低落到官方档」来写。这两点都已写进 `raw_from_score` 的 docstring（含「必须向下取整到带内整数」的明确指示）与 README。

---

## R2.11 过程记录（一处工具异常，已绕过并验证）

对 `backend/data/README_national_standard.md` 的前几次编辑，编辑工具报成功且回显了 diff，但**内容只进了 IDE 缓冲区、没有落盘**：`git status` 不报该文件修改，`git hash-object` 显示工作树 blob 与 `HEAD` 完全相同（`d42e6f69…`），文件 `LastWriteTime` 也未变。已改用「写临时文件 + `Copy-Item -Force` 覆盖」落盘，随后 `git status --short` 报 `M backend/data/README_national_standard.md`、`Select-String` 逐条命中新内容，确认生效；临时文件已 `Remove-Item`。
**这也是本报告对全部改动都以「磁盘真值」复核的原因**：CSV 用 `git hash-object` 比对 HEAD blob（未变），6 个 `.py`／测试文件用 `Select-String` 直接扫磁盘内容并跑 pytest（pytest 读的也是磁盘），domain 禁用 token 用 `Select-String` 扫磁盘（No matches），变异植入用 `Compare-Object` 确认清除后探针输出与植入前逐行相同。`.superpowers/` 报告文件本身同样以「临时文件 + .NET `AppendAllText`（无 BOM UTF-8）」方式追加。

---

# 修复轮 3（Fix Round 3）— Ruling 22：`raw_from_score` 返回方向感知的档位端点

**起点**：`feature/plan-01-data-foundation` @ `8454ade`，`git status --short` 为空（干净树）。
**状态**：DONE
**结论**：反查从「档位区间**中点**」改为「**方向感知的档位端点** = 仍然拿到该分的最差原始值」，
往返不变量在全表每一个官方档上**精确**成立，次数项因此天然是整数，Task 6 不再需要任何取整。
只动了 2 个文件（`indicators.py` 的 `raw_from_score` + 其测试），CSV 一个字节都没碰。

## R3.1 Finding（为什么要改）

旧实现返回「映射到目标档的原始值区间的中点」，有三个后果，逐条实测确认：

1. **次数项造出不可能的读数**。`raw_from_score(pull_up_or_sit_up, 72, MALE, 大一、大二)` 返回
   **13.5**（带 `[13, 14)` 的中点）。Task 6 消费本函数，仿真数据里会出现「做了 13.5 个引体向上」的学生。
2. **取整方向无法安全选择**。13.5 向上取整成 14 就跨进 76 档（CSV 第 439 行），只有向下才对；
   而「该往哪边取整」是**方向相关**的知识（越大越好向下、越小越好向上），把它泄漏到每个调用点，
   等于要求每个调用方自己重推一遍评分表的方向。
3. **往返不变量名义成立、实质无约束力**。中点确实也能回代得到同一档分，所以旧
   `test_raw_from_score_roundtrips` 全绿——它区分不出「端点」与「带内任意一点」，
   也就守不住「返回值是最差合格值」这个真正有用的性质。

## R3.2 变更内容

| 文件 | 变更 |
| --- | --- |
| `backend/app/domain/indicators.py` | `raw_from_score` 尾部：删除 `better` / `near,far` / `(near+far)/2` 的中点算法，改为 `return float(max(band) if _lower_is_better(segments) else min(band))`；docstring 重写为端点语义 + 精确往返保证，删除全部中点表述与「必须向下取整」的指示 |
| `backend/tests/domain/test_indicators.py` | `test_raw_from_score_roundtrips` → `test_raw_from_score_roundtrips_exactly_across_whole_table`（全表扫描）；新增 `test_raw_from_score_returns_integral_value_for_count_items`、`test_raw_from_score_returns_worst_qualifying_value_not_midpoint`；新增两个模块内推导辅助 `_monotonic_groups()` / `_official_scores()`；import 补 `AGE_GROUPS` |

`git diff --stat`：`2 files changed, 107 insertions(+), 24 deletions(-)`。

核心 diff：

```python
     band = [raw for raw, s in segments if s == target]
-    better = [raw for raw, s in segments if s > target]
-    if non_increasing and not non_decreasing:
-        near, far = max(band), (max(better) if better else None)
-    else:
-        near, far = min(band), (min(better) if better else None)
-    if far is None:
-        return float(near)
-    return float((near + far) / 2)
+    # 方向沿用 score_item 那套推断（_lower_is_better）：越小越好取带上界、
+    # 越大越好取带下界，两者都是「仍拿到 target 分的最差原始值」。
+    return float(max(band) if _lower_is_better(segments) else min(band))
```

**方向推断复用了 `score_item` 用的 `_lower_is_better`**（沿 raw 升序看得分是否全程单调**不增**），
没有重新引入 `scores[0] < scores[-1]` 那种朴素判据——BMI 首末档是 80/60，朴素判据会把它误判成
「越小越好」，这正是上一轮更正过的坑。旧实现里等价的局部判据是 `non_increasing and not non_decreasing`，
与 `_lower_is_better(segments)` 只在「全表同分」这种退化序列上有别（真实 28 组无一如此），
换成复用后单一口径、少一份可漂移的副本。

**保持不变（已逐条实测）**：

- 就低映射：非官方请求分落到「不超过它的最大官方档」。`73 → 72 档`、`71 → 70 档`（见 R3.3 表末两行）。
- 非单调项抛 `ValueError`：BMI 男女两组都抛（`test_raw_from_score_rejects_non_monotonic_item`）。
- 键不存在抛 `KeyError`：`raw_from_score(T, VITAL_CAPACITY, 80, MALE, "不存在的年级组")`
  → `KeyError: ('vital_capacity', 'male', '不存在的年级组')`。
- `score_item`、`segment_thresholds`、`tables.py`、`refdata.py`、架构测试、`pyproject.toml`、`.gitignore`：
  **零改动**。`git status --short` 只列出上述 2 个文件。
- CSV 未动：`git hash-object backend/data/national_standard_2014.csv` =
  `7a65f5bb25a9b7c48d251589c6f57f42b7d3fc46`，与 `git rev-parse HEAD:…` **逐字相同**。

## R3.3 修复前 / 修复后实测（同一探针脚本 `$env:TEMP\probe_task2_r3.py`，改前改后各跑一次）

### dispatch 点名的三组

| 用例 | 方向 | 就低落到 | CSV 原行 | 修复前（中点） | 回代 | 修复后（端点） | 回代 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `standing_jump,male,大一、大二` @ 80 | 越大越好 | 80 档 | 第 278 行 `standing_jump,male,大一、大二,80,248`；第 277 行 `85,256` | **252.0** | 80 | **248.0** | **80** |
| `sprint_50m,male,大一、大二` @ 95 | 越小越好 | 95 档 | 第 115 行 `sprint_50m,male,大一、大二,95,6.8`；第 114 行 `100,6.7` | **6.75** | 95 | **6.8** | **95** |
| `pull_up_or_sit_up,male,大一、大二` @ 72 | 越大越好 | 72 档 | 第 440 行 `pull_up_or_sit_up,male,大一、大二,72,13`；第 439 行 `76,14` | **13.5** | 72 | **13.0** | **72** |

三组的修复后返回值 **逐字等于 CSV 里那一档的 `raw_value`**（248 / 6.8 / 13），
不是算出来的近似值：越大越好取带下界 = 该档在 CSV 里的阈值行本身；
越小越好取带上界 = 该档在 CSV 里的阈值行本身（其区间是 `(上一档, 本档]`，本档阈值即最差合格值）。
`13.0.is_integer() == True` ⇒ 次数项不再出现 `.5`。

### 就低映射与异常路径（修复前后语义一致，只有返回值从中点变成端点）

```
standing_jump,male,大一、大二
  请求 73 → 修复前 raw=234.0 回代 72      修复后 raw=232.0 回代 72   （CSV 第 282 行 72,232）
  请求 71 → 修复前 raw=230.0 回代 70      修复后 raw=228.0 回代 70   （CSV 第 283 行 70,228）
  BMI 80  → 修复前后都 ValueError ✓
  缺键    → 修复前后都 KeyError ✓ ('vital_capacity','male','不存在的年级组')
```

## R3.4 全表扫描计数（探针实测，非推算）

```
非单调（跳过）组 = 4: bmi/male/大一、大二, bmi/male/大三、大四, bmi/female/大一、大二, bmi/female/大三、大四
单调组数 = 24   组内官方档总数 = 470（去重后仍 470 ⇒ 每个单调组的每个官方档只对应一个 raw）

                        修复前                     修复后
往返断言（470）         失败 0                     失败 0
『最差合格值』端点断言   446 条中失败 422           446 条中失败 0
  （另 24 个「表内最差档」无更差侧，两侧都跳过：越界会被 score_item 夹回同一档，无从比较）
次数项整数性断言         66 条中失败 30             66 条中失败 0
```

修复前端点断言失败的 4 个样例（缺陷本体）：

```
FAIL vital_capacity/male/大一、大二 s=20 raw=2540.0 probe=2539.999999 got=20
FAIL vital_capacity/male/大一、大二 s=30 raw=2700.0 probe=2699.999999 got=30
FAIL standing_jump/male/大一、大二 s=80 raw=252.0 probe=251.999999 got=80
FAIL pull_up_or_sit_up/male/大一、大二 s=72 raw=13.5 probe=13.499999 got=72
```

修复前非整数次数项的 4 个样例：`pull_up_or_sit_up/male/大一、大二 s=72 raw=13.5`、
`s=76 raw=14.5`、`female/大一、大二 s=80 raw=47.5`、`s=85 raw=50.5`。

**注意「往返断言修复前也是 0 失败」**——这正是 dispatch 指出的：中点能通过往返测试。
区分端点与中点的只有第 3 类断言（往差侧挪 EPS 必须掉档），故它必须存在，
否则本次修复在测试层面毫无看守。

## R3.5 TDD 证据

### RED（先写测试，未改实现）

```
cd backend; C:\Python\python.exe -m pytest tests/domain/test_indicators.py -q

FAILED tests/domain/test_indicators.py::test_raw_from_score_returns_integral_value_for_count_items
  - AssertionError: pull_up_or_sit_up/male/大一、大二 目标 10 分反查得非整数次数 5.5
    assert 5.5 == 5   +  where 5 = int(5.5)
FAILED tests/domain/test_indicators.py::test_raw_from_score_returns_worst_qualifying_value_not_midpoint
  - AssertionError: vital_capacity/male/大一、大二 目标 10 分反查得 raw=2380.0，
    但只差 EPS 的 2379.999999 仍得 10 分——返回的不是最差合格值
    assert (10 is not None and 10 < 10)
2 failed, 18 passed in 0.14s
```

两条都因**被测语义缺失**而失败，不是笔误：一条钉住「次数项必须是整数」，
一条钉住「返回值必须是最差合格值」。全表扫描那条在修复前就绿（中点也满足精确往返），
如实记录——它的价值是防回归，不是抓本缺陷。

### GREEN

```
cd backend; C:\Python\python.exe -m pytest tests/domain/test_indicators.py -q
→ 20 passed in 0.07s

cd backend; C:\Python\python.exe -m pytest tests/domain tests/test_refdata.py tests/architecture -v
→ 32 passed in 0.09s（indicators 20 + refdata 9 + architecture 3；逐条 PASSED 已核对）

cd backend; C:\Python\python.exe -m pytest -q
→ 32 passed in 0.08s
cd backend; C:\Python\python.exe -m pytest -q -W error
→ 32 passed in 0.08s        # 以 warning 为 error 仍全绿 ⇒ 输出洁净
```

（`pytest` 未在 PATH，一律用 `C:\Python\python.exe -m pytest`，与 dispatch 的 `cd backend; pytest …` 等价；
`pyproject.toml` 的 `pythonpath = ["."]`、`testpaths = ["tests"]` 未改。）

### 三条新/改测试的断言量（实测点数，非估算）

| 测试 | 覆盖面 | 断言数 |
| --- | --- | --- |
| `test_raw_from_score_roundtrips_exactly_across_whole_table` | 24 个单调组（6 短板项 × 2 性别 × 2 年级组）× 每组全部官方档 | **470** 条往返断言 + 2 条反空转守卫（覆盖集合等于 `WEAKNESS_ITEMS × Sex × AGE_GROUPS`；`checked == 由表现场推导的档对总数 >= 2 × 组数`） |
| `test_raw_from_score_returns_integral_value_for_count_items` | `PULL_UP_OR_SIT_UP` × 2 性别 × 2 年级组 × 全部官方档（男 15+15、女 20+20 = 70 档） | **140**（70 档 × `raw == int(raw)` 与 `raw >= 0` 各一条） |
| `test_raw_from_score_returns_worst_qualifying_value_not_midpoint` | 同 24 组 × 全部官方档，跳过 24 个「表内最差档」 | **892**（446 条 `gap > EPS` 前置 + 446 条 `score_item(raw ± EPS) < score`）+ 1 条 `checked > 0` 反空转 |

EPS = `1e-6`（模块内既有常量），远小于全表最小差侧档距（0.1）；每条断言前都先断言
`gap > EPS`，避免 EPS 一次跨过两档造成假绿。

### 既有测试：一条断言都没弱化

- `test_raw_from_score_roundtrips` 被 `…_exactly_across_whole_table` **取代而非削弱**：
  旧的是「6 短板项 × 2 性别 × **1 个**年级组 × 全部档行、精确相等」，
  新的是「6 短板项 × 2 性别 × **2 个**年级组 × 全部**去重**官方档、精确相等 + 反空转守卫」。
  实测每个单调组的档行数 == 去重官方档数（470 == 470），故旧断言集合是新断言集合的**真子集**。
- `test_raw_from_score_maps_unofficial_target_down_to_official_band`（73→72、71→70）**原文未改**，仍全绿。
- `test_raw_from_score_rejects_non_monotonic_item`（BMI → `ValueError`）、
  `test_raw_from_score_and_thresholds_raise_keyerror_for_absent_key`（`KeyError`）**原文未改**，仍全绿。
- 其余 15 条（`score_item` 相关、refdata、architecture）**一行未动**，全绿。
- **没有发现任何既有测试与端点语义冲突**，因此没有需要上报的「测试与新语义矛盾」情形。

## R3.6 文档与纯净性核对

- `backend/app/domain/indicators.py` 的 docstring 已改为端点语义，并写明精确往返保证
  `score_item(table, item, raw_from_score(table, item, s, sex, ag), sex, ag) == s`；
  中点表述与「调用方必须向下取整」的指示已**全部删除**（`Select-String -Pattern '中点'` 对该文件 → No matches）。
- `backend/data/README_national_standard.md`：**无需更正，未改动**。已逐字核对该文件全部 161 行中
  与反查相关的唯一一处（第 129–133 行「`raw_from_score` 对 BMI 直接抛 `ValueError`（Ruling 19）」），
  讲的是 BMI 哨兵泄漏，与中点无关，修复后依旧准确；全文 `Select-String -Pattern '中点|13\.5|请求分'`
  → **No matches**，即 README 从未记载中点语义，也从未写过「请求分 == 回代分 不再成立」这条 caveat
  （那条只写在上一轮的 docstring 与报告 §R2.10-3 里，docstring 已改，报告属历史记录不改写）。
- `app/domain/` 禁用 token 扫描（磁盘真值，`Select-String -SimpleMatch`）：
  `datetime.now`、`datetime.today`、`datetime.utcnow`、`date.today`、`time.time`、`__file__`、
  `import os`、`os.listdir`、`os.walk`、`json.load`、`pickle.load`、`read_csv`、`csv.reader`、`Path(`
  → **No forbidden token in app/domain**；3 条架构守卫全绿。
- **落盘复核**：`indicators.py` 改后 `git hash-object` = `2632a2033653ed03e53be3cd10222490a20b8548`
  （≠ HEAD blob），并用 `Get-Content` 直接从磁盘回读第 150–172 行确认新 docstring 与新 `return`
  语句都在盘上；对 `中点|向下取整|near + far|13\.5` 的磁盘扫描 → **0 命中**。
  测试文件用 `Select-String` 从磁盘命中 6 处新符号（`AGE_GROUPS,` / `_monotonic_groups` ×3 /
  三个新测试函数名）。本节自身按 §R2.11 的做法用「临时文件 + .NET `AppendAllText`（无 BOM UTF-8）」追加，
  追加后回读校验 §1–§7、§F.1–§F.6、§R2.0–§R2.11 全部仍在盘上。

## R3.7 给 Task 6 的影响（原 §R2.10-3 的前置提醒已作废）

- **不再需要任何取整**：`raw_from_score` 对次数项直接给整数（`13.0`），对其他项给国标档位的真实阈值
  （`248.0` cm、`6.8` s），可以直接落库当实测值。
- **「请求分会就低落到官方档」这条仍然成立且必须遵守**：目标分 73 造出来的学生回代得 **72**。
  Task 6 若要按连续目标分分层，得自己记住这个落差，别指望回代等于请求分。
- **返回值是档位边界，不是带内随机点**：仿真学生恰好压在阈值上。若 Task 6 想给原始值加抖动，
  必须**只往好的方向加**（越大越好向上、越小越好向下），往差侧加任意小的抖动都会掉一档。
  这是端点语义的固有代价，换来的是精确往返与整数次数；如需带内随机点，应在 Task 6 内
  用 `[raw_from_score(s), raw_from_score(下一档))` 自行采样，而不是让本函数返回中点。

## R3.8 Concerns

无阻塞项。一条留档提醒：**计划文档 `Document/2026-09-28-实施计划01-数据基座与分层引擎.md`
Task 2 Step 4 第 344 行仍写着「`raw_from_score` 为同一表的反向插值」**，既与 Ruling 18（不插值）
也与本轮 Ruling 22（端点）不符；同文件第 173 行的 Interfaces 块同样写着「分段函数**线性插值**」。
本轮 dispatch 的范围明确限定在代码与测试，未授权改计划文档，故**未动**——请 controller 在
下一次文档轮把这两处一并更正为「方向感知的档位端点，精确往返」，否则 Task 6 的实现者
读计划会拿到与代码相反的口径。

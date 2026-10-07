# Task 4 报告：DataSourceAdapter 契约与两个实现

- 分支：`feature/plan-01-data-foundation`
- 提交：`3de6c22` `feat: 定义 DataSourceAdapter 契约与 CSV 列序，落地 Mock 实现与乐跑 HTTP 骨架`（父提交 `0c32ef1`）
- 测试：`tests/adapters` **43 passed**；全量 **112 passed**（此前 69 条全部保留、未改动），`-W error` 下同样 112 passed、零警告
- 状态：**DONE_WITH_CONCERNS**（实现与测试全绿；关切全部是跨 Task 的契约衔接项，见末节，其中 C1/C2/C3/C6 需要裁定）

---

## 1. 实现了什么

### `backend/app/adapters/base.py`（契约层，零 I/O 知识）

- 三个 `@dataclass(frozen=True)`：`RawFitnessRecord`（**11 字段**，`tested_on` 按 Ruling 33 插在 `batch_key` 之后）、`RawBodyCompRecord`（5 字段）、`RawSurveyRecord`（5 字段）。字段声明序即 CSV 列序，是唯一真相来源。
- `class DataSourceAdapter(ABC)`：四个 `@abstractmethod`（`fetch_students` / `fetch_fitness` / `fetch_body_comp` / `fetch_survey`），一律声明返回 `Iterator[...]`；docstring 写明惰性是契约的一部分、`since` 排他语义、`fetch_students` 不支持增量。
- `parse_batch_key(key) -> tuple[str, str]`：**`batch_key` 格式的唯一所有者**，配套 `BATCH_KEY_SEPARATOR = "|"`、`TIMEPOINTS = frozenset({"week1","week8","week16"})`、学年正则 `\d{4}-\d{4}`。三类畸形（分隔符数量不对、学年形状不对、时点不在域内）各抛带原值的 `ValueError`。
- base.py 不含任何文件名、`csv`、`pathlib.open`、网络或 db 引用（`import` 只有 `re` / `abc` / `collections.abc` / `dataclasses`）。

### `backend/app/adapters/mock_lepao.py`（读取侧实现，契约的具体清单在此）

- 文件名常量 4 个 + 列序常量：`FITNESS_COLUMNS` / `BODY_COMP_COLUMNS` / `SURVEY_COLUMNS` 由 `dataclasses.fields()` 从 base.py 的数据类**推导**（不手抄第二份）；`STUDENT_COLUMNS` 因无对应数据类而显式声明。
- `MockLePaoAdapter(seed_dir)`：构造时**不做任何 I/O**（契约测试在收集期就要实例化它）；四个 `fetch_*` 都返回生成器（已用探针实测四者 `isinstance(..., types.GeneratorType)` 均为 True）。
- 表头逐列（含顺序）校验，不符抛 `ValueError` 并列出期望/实际；文件缺失（含整个目录缺失）一律 yield 空。
- 单元格解析：可缺测数值列空 → `None`、非空 → 有限 `float`、`nan`/`inf` → `ValueError`；`str` 声明列原样透传（空 → `""`）；`students.csv` 的 dict 值空 → `None`；`sex` 按 Task 2 的 `Sex` 枚举校验并产出 `.value`；`dimensions`/`raw_answers` 走 JSON 对象解析，`dimensions` 的值统一转 `float`。
- 所有报错都带**文件名 + 行号（`DictReader.line_num`）+ 列名**，实测消息见 §3。

### `backend/app/adapters/http_lepao.py`（骨架，spec §3.4）

- `HttpLePaoAdapter(base_url, token)`，四个方法体一律 `raise NotImplementedError`，但类存在且通过 `isinstance` 契约检查与 Mock 跑同一组参数化用例。**（此句表述过头，已在 §7 的 M9 更正：与 HTTP 骨架共享的只有 `isinstance`+可调用与 `NotImplementedError` 两组断言，其余全是 Mock 专属的行为测试。）**
- 模块 docstring 写明未来实现必须满足的契约形状（增量排他、惰性分页、字段映射只在本文件、空值 → `None`、`fetch_students` 全量）。
- 刻意**不含** HTTP 客户端、重试、鉴权、超时；docstring 注明 `token` 不得进日志或异常消息。

### 夹具 `backend/tests/fixtures/lepao_sample/`（进版本控制，契约的可执行定义）

四个 CSV，各 3 行数据 + 1 行表头，UTF-8 无 BOM、LF 行尾。数据本身自洽：`fitness.csv` 覆盖两个学年（`2024-2025|week16`、`2025-2026|week1`、`2025-2026|week8`）、**一行 `vital_capacity_ml` 为空**、**一行 `strength_count` 为合法的 0**（用来钉住「0 是真实成绩，不等于缺测」）；`body_comp.csv` 一行 `smi` 为空；`survey.csv` 的 5 维度分恰为其 2 道题的均值（`dimensions` 与 `raw_answers` 内部一致）。

---

## 2. CSV 契约（Task 6 的 `write_csv` 必须逐列对齐；权威定义处）

**通用规则**

1. 文件名固定四个：`students.csv`、`fitness.csv`、`body_comp.csv`、`survey.csv`，写入同一个 `out_dir`。
2. 首行为表头，UTF-8 编码（读取侧用 `utf-8-sig`，带 BOM 也能读）。行尾 LF/CRLF 皆可（已实测 CRLF 副本解析结果与 LF 完全一致，末列不带残留 `\r`）。
3. 列序 = 对应数据类的字段声明顺序，**逐列含顺序都会被校验**；不符即在抽取处抛 `ValueError`（消息列出期望与实际）。用 `csv.DictWriter(fieldnames=<下表>)` 或按同序构造 DataFrame 即可满足。
4. **缺测写空字符串**（`,,`），不是 `None`、不是 `nan`、不是 `0`。数值列读到 `nan`/`inf` 字面量会抛 `ValueError`——pandas `to_csv` 的缺省 `na_rep=''` 正好合规，但手写 `str(float('nan'))` 会炸。
5. `since` 是 ISO 日期串 `YYYY-MM-DD`，**排他**过滤（严格 `> since`，日期恰等于 `since` 的记录不返回）；`None` 表示全量。各源按自身日期列过滤：`fitness.tested_on`、`body_comp.measured_on`、`survey.filled_on`；`students` 不过滤（`since` 非 None 时也返回全量）。水位线格式非法在**调用时**就抛 `ValueError`（`date.fromisoformat` 会把 `20250910` 归一为 `2025-09-10`）。**（§7 I2 补充：记录侧日期列同样必须是零填充 `YYYY-MM-DD`、不带时间部分；增量模式下解析失败即在抽取那一行抛 `ValueError`。）**
6. `batch_key` 形如 `"<academic_year>|<timepoint>"`（`"2025-2026|week1"`、`"2024-2025|week16"`）；解析只走 `app.adapters.base.parse_batch_key`，Task 10 不得自己 `split("|")`。

**列序（逐列，照抄即可）**

| 文件 | 列数 | 列序 |
|---|---|---|
| `students.csv` | 6 | `student_no,name,sex,birth,department,grade` |
| `fitness.csv` | 11 | `student_no,batch_key,tested_on,height_cm,weight_kg,vital_capacity_ml,sprint_50m_s,sit_and_reach_cm,standing_jump_cm,strength_count,distance_run_s` |
| `body_comp.csv` | 5 | `student_no,measured_on,muscle_mass_kg,body_fat_pct,smi` |
| `survey.csv` | 5 | `student_no,filled_on,total,dimensions,raw_answers` |

程序化取列序：`from app.adapters.mock_lepao import FITNESS_COLUMNS, BODY_COMP_COLUMNS, SURVEY_COLUMNS, STUDENT_COLUMNS`（前三者由 `dataclasses.fields()` 从 base.py 推导，改字段只改 base.py 一处）。**（已按 Ruling 36 更正：八个常量现在住在 `app.adapters.base`，生产方应 `from app.adapters.base import ...`，见 §7。）**

**逐列的取值与空值语义**

- 8 个体测数值列 + 3 个体成分数值列：`float | None`，空 → `None`。**绝不可写 0 代替缺测**（Ruling 21：`0` 经 `score_item` 低侧夹取得 100 分）。合法的 `0` 必须写 `0`（`strength_count` 的 0 次是真实成绩，读取侧原样保留为 `0.0`）。
- 数据类里声明为 `str` 的列（`student_no`/`batch_key`/`tested_on`/`measured_on`/`filled_on`）：空单元格透传为 `""` 而非 `None`（契约没给它们 `None` 的位置），数据质量由 Task 5 清洗与 `cleaning_log` 留痕。
- `students.csv`：值是 dict，空单元格 → `None`；`sex` 必须是 `male`/`female`（Task 2 `Sex` 的 value），写 `男`/`M` 会在抽取那一行抛 `ValueError`；`birth` 为 ISO 日期串，`grade` 为数字串（都按原始字符串产出，不做类型转换——`fetch_students` 在第一批无消费者）。
- `survey.csv` 的 `total`、`dimensions`、`raw_answers` **三列必填**：`total` 空 → `ValueError`（不用 `0.0` 兜底，0 是有意义的最低分）；两个 JSON 列必须是合法 JSON **对象**，缺失请写 `{}` 而不是空字符串（`dict` 字段没有 `None` 的位置，悄悄读成 `{}` 会让「没有维度」与「没填问卷」在下游变成同一件事）。`dimensions` 的值会被统一转成 `float`（JSON 里的 `4` 会变 `4.0`）。
- JSON 列的 CSV 转义：字段整体用 `"` 包裹、内部 `"` 翻倍（夹具 `survey.csv` 就是可照抄的样例）。

---

## 3. TDD 证据

### RED

命令（PowerShell，`;` 分隔）：

```
cd backend; python -m pytest tests/adapters -v
```

输出（关键片段）：

```
collecting ... collected 0 items / 1 error
=================================== ERRORS =================================
______________ ERROR collecting tests/adapters/test_contract.py _______________
tests\adapters\test_contract.py:9: in <module>
    from app.adapters.base import DataSourceAdapter, RawFitnessRecord
E   ModuleNotFoundError: No module named 'app.adapters.base'
=========================== short test summary info ===========================
ERROR tests/adapters/test_contract.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.17s ===============================
```

为什么是预期失败：此时 `backend/app/adapters/` 只有一个空的 `__init__.py`，测试第 9 行 import 的 `app.adapters.base` 尚不存在，故与 brief Step 2 的 `Expected: FAIL — ModuleNotFoundError: app.adapters.base` 完全一致。测试先写、实现在后，收集期就失败也证明这 43 条用例不是「跑不到所以绿」。

### GREEN

命令：

```
cd backend; python -m pytest tests/adapters -v          # 聚焦
cd backend; python -m pytest -q                          # 全量
cd backend; python -m pytest -q -W error                 # 全量 + 警告即错误
```

输出（关键片段）：

```
tests/adapters/test_contract.py::test_satisfies_adapter_contract[mock] PASSED
tests/adapters/test_contract.py::test_satisfies_adapter_contract[http] PASSED
tests/adapters/test_contract.py::test_mock_parses_empty_cell_as_none PASSED
tests/adapters/test_contract.py::test_mock_returns_iterator_not_list PASSED
tests/adapters/test_contract.py::test_missing_dir_yields_empty_not_raises PASSED
tests/adapters/test_contract.py::test_http_adapter_declares_not_implemented PASSED
tests/adapters/test_contract.py::test_since_is_exclusive_on_fitness_tested_on PASSED
tests/adapters/test_contract.py::test_parse_batch_key_rejects_malformed[2025-2026week1] PASSED
tests/adapters/test_contract.py::test_parse_batch_key_rejects_malformed[2025-2026|week9] PASSED
...（中略，43 条全 PASSED）
============================= 42 passed in 0.08s ==============================   ← 首次 GREEN（补 Sex 用例前）
43 passed in 0.10s                                                                  ← 补 Sex 域校验用例后
112 passed in 0.57s   （-W error，全量；69 条既有 + 43 条新增）
```

偏离说明：brief Step 4 写「Expected: PASS，7 passed」。brief 的 6 个测试函数**逐字保留未改**（含其 `import pathlib, pytest` 等原始导入行），另按派发指令补了 `since` 排他边界、`parse_batch_key` 畸形输入、`is None` 身份断言等契约用例，故实际为 43 条。

### 运行时探针（不属于仓库文件，用完即删）

- 四个 `fetch_*` 均返回 `types.GeneratorType`；`since` 校验为**调用时**立即触发。
- 三条 `fitness` 记录解析结果：`vital_capacity_ml=None`（空格）、`strength_count=0.0`（真实 0）、`parse_batch_key` 对三条 `batch_key` 均返回 `('2024-2025','week16')` / `('2025-2026','week1')` / `('2025-2026','week8')`；问卷 5 个中文维度键无乱码。
- 六类错误消息逐条实测，均带文件名/行号/列名，例如：
  - `students.csv 第 2 行 sex 值非法: '男'；合法值: ['male', 'female']`
  - `fitness.csv 表头与 CSV 契约不符：期望 ['student_no', 'batch_key', ...]，实际 ['batch_key', 'student_no', ...]；列序 = 数据类字段声明顺序，write_csv 必须逐列对齐`
  - `fitness.csv 第 2 行 vital_capacity_ml 是非有限值 'nan'；CSV 契约要求缺测写空字符串，不可写 nan/inf`
  - `survey.csv 第 2 行 total 为空，但该字段不可缺测`
  - `survey.csv 第 2 行 dimensions 为空；JSON 列缺失请写 {} 而不是空字符串`
  - `batch_key 的时点部分非法: 'week9'（来自 '2025-2026|week9'）；合法值: ['week1', 'week16', 'week8']`
- CRLF 副本回归：把四个夹具转成 CRLF 后重新读取，条数、`None`、`0.0`、5 维度、`sex` 值全部与 LF 一致。

---

## 4. 变更文件（8 个新增，864 行；无既有文件被修改）

| 文件 | 行数 | 说明 |
|---|---|---|
| `backend/app/adapters/base.py` | 165 | 契约：3 数据类 + ABC + `parse_batch_key` + `TIMEPOINTS`/`BATCH_KEY_SEPARATOR` |
| `backend/app/adapters/mock_lepao.py` | 353 | CSV 读取实现 + 文件名/列序常量 + 单元格解析器 |
| `backend/app/adapters/http_lepao.py` | 59 | 乐跑 HTTP 骨架（四方法 `NotImplementedError`） |
| `backend/tests/adapters/test_contract.py` | 271 | 43 条契约用例（brief 原文 6 函数 + 扩展） |
| `backend/tests/fixtures/lepao_sample/students.csv` | 4 | 6 列 × 3 行 |
| `backend/tests/fixtures/lepao_sample/fitness.csv` | 4 | 11 列 × 3 行（含空格与真实 0） |
| `backend/tests/fixtures/lepao_sample/body_comp.csv` | 4 | 5 列 × 3 行（含空格） |
| `backend/tests/fixtures/lepao_sample/survey.csv` | 4 | 5 列 × 3 行（JSON 列） |

- 未创建 `conftest.py`、`tests/__init__.py`、配置文件或 linter 配置；未新增任何依赖（只用标准库 `csv`/`json`/`math`/`re`/`datetime`/`dataclasses`/`abc`/`pathlib`）。
- 未改动 `backend/tests/architecture/test_domain_purity.py`、`backend/data/national_standard_2014.csv`、Task 2/3 的任何文件。
- 写盘校验：8 个文件逐个 `git hash-object <file>` 与 `git rev-parse HEAD:<file>` 比对，全部 MATCH；`git status --short -- backend` 为空。四个夹具与三个模块均确认 UTF-8 无 BOM。
- 仓库里另有一处**先前就存在、非本 Task 产生**的未提交改动：`Document/2026-09-28-体育闭环原型-设计spec.md`（Ruling 31 的 spec 同步）。我没有 add 它，也没改它。

---

## 5. 自查

- 四个夹具 CSV 均已提交，列序与数据类字段序逐列一致（由 `test_fixture_header_equals_dataclass_field_order` 与 `test_fixture_students_header_matches_contract` 双向钉住：一边读夹具表头、一边读 `dataclasses.fields()`）。
- `test_mock_parses_empty_cell_as_none` 用的是 brief 原文的 `is None`（身份断言，非 falsy）；另补 `test_missing_measure_keeps_row_and_stays_none`（缺测行不被丢）、`test_real_zero_stays_zero_and_is_not_confused_with_missing`（`== 0.0` 且 `is not None`）、`test_no_numeric_cell_becomes_nan_or_inf`（`math.isfinite`）、`test_nan_literal_cell_is_rejected`。
- `since` 排他边界：三个源各一条（`2025-06-18` → 排除同日、返回后两条；`2025-10-22` → 只剩 `2025-12-17`；`2025-10-21` → 只剩 `2025-12-16`），外加「水位线晚于所有行 → 空」与「非 ISO → `ValueError`」。
- `parse_batch_key`：3 条正常路径 + 6 条畸形（缺分隔符、时点越域、多分隔符、学年非四位-四位、时点为空、空串）；`grep` 确认 `backend/app` 下只有 base.py 一处 `split(`，没有第二个解析点。
- 两个实现跑同一条参数化契约（`test_satisfies_adapter_contract[mock|http]`），HTTP 骨架另有一条覆盖四个方法的 `NotImplementedError` 用例。
- 无多余产物：无 HTTP 客户端、无重试、无配置、无 `conftest.py`、无 `tests/__init__.py`、无 linter。
- 既有 69 条测试全绿且文件未被触碰；`-W error` 下 112 passed，输出无 warning、无 skip、无 xfail。
- 一处自我纠错：`_sex_cell` 的 docstring 初稿写了「`hash(Sex.MALE) != hash("male")`」，实测（Python 3.11.1）为 **False**（两者 hash 相等、集合比较为真）。已把该句改成实测成立的理由：`str(Sex.MALE)` 与 `f"{Sex.MALE}"` 都得到 `"Sex.MALE"`，枚举成员混进原始 dict 会被日志/入库路径写成错值。同时把 `test_wrong_column_order_raises` 的 `match` 从 `"fitness.csv"` 收紧为 `"表头"`——原写法在表头错误与数值解析错误下都能匹配，可能因错误原因不对而假绿。

---

## 6. 关切（每一条都同时写在代码注释/docstring 里，此处汇总供裁定）

**需要裁定的跨 Task 冲突**

- **C1（高）Task 5 的 brief 已与 Ruling 33 冲突。** 计划第 597–599 行的 `rec()` 辅助函数用 `batch_key="2025-w1"`（不符合 `<academic_year>|<timepoint>`），且**没有 `tested_on`**——而 `tested_on` 现在是 `RawFitnessRecord` 的必填字段（无默认值），照抄那段测试代码会直接 `TypeError`。派发 Task 5 前需修 brief：`batch_key="2025-2026|week1"` + 补 `tested_on="2025-09-04"`。我没有改计划文件。
- **C2（中）Task 6 的 `write_csv` 正文只写三类 CSV。** 计划第 874 行「把 `fitness`/`body_comp`/`survey` 三类写成…」，而 Ruling 33 的文件名清单是**四个**（含 `students.csv`）。我的实现对缺文件一律 yield 空（`test_missing_file_yields_empty_for_every_source` 钉住），所以 Task 10 的 `test_write_csv_roundtrips_through_adapter` 不会因此失败；但 `fetch_students` 在第一批会永远拿不到数据。需明确 Task 6 是否从 `population` 写 `students.csv`。
- **C3（中）`students.csv` 的列没有数据类作权威来源。** 我按 ORM `Student` 的业务列钉成 `student_no,name,sex,birth,department,grade`（不含自增 `id`），而计划里 `population` 的 dict 键是 `student_id`/`sex`/`age`/… 形态不同。若 Task 6 直接把 `population` 写成 `students.csv`，会被表头校验拒绝（响亮失败，消息列出期望与实际）——需要一次显式投影（`age` → `birth` 还需换算），请裁定投影由谁做。
- **C6（中）问卷三列必填 vs Task 6 的脏数据注入。** `total`/`dimensions`/`raw_answers` 的空格子会抛 `ValueError`，而计划里**没有 `clean_survey` 阶段**兜底。若 `inject_dirty` 把「缺失 3–5%」注入到问卷行（或写出 `nan`），Task 10 的管道会在抽取阶段崩。请裁定：问卷不参与脏数据注入，还是放宽适配器（把空 `dimensions` 读成 `{}`）。我选了响亮失败，因为静默读成 `{}`/`0.0` 会造出「对体育毫无兴趣」的假学生。

**契约边界（已写进代码，供知悉）**

- **C4** 表头**逐列含顺序**严格校验。这是有意的：`DictReader` 按名取值会让列序漂移静默通过。Task 6 若用 pandas 且列序不同，会在抽取处 `ValueError`。
- **C5** 数值列读到 `nan`/`inf` 字面量 → `ValueError`。pandas `to_csv` 缺省 `na_rep=''` 合规；任何显式 `na_rep='nan'` 或手写 `str(float('nan'))` 都会炸。
- **C7** `str` 声明列的空单元格透传为 `""` 而不是 `None`（数据类没给 `None` 的位置）。缺学号/缺日期属数据质量问题，交 Task 5 与 `cleaning_log`，适配器不代为决定丢弃。
- **C8** 增量过滤下，**空日期字段（`""`）会被排除**（字典序排在任何日期之前）。Task 6 一定会写日期，第一批不会触发；写在 `_is_after` 的 docstring 里，未为不会发生的情形加分支。
- **C9** `since` 在调用时（而非首次取值时）校验并规范化，非法格式抛 `ValueError`；`fetch_students` 也校验格式但**不据此过滤**（Ruling 33）。
- **C10** `TIMEPOINTS` 在 base.py 与 `app/db/models.py` 的 `FitnessTestBatch.TIMEPOINTS` 各写一份：adapters 不反向 import db（依赖方向 `db ← services / pipeline`）。两处一旦漂移会在入库时被 `ck_fitness_test_batch_timepoint` 拦下，不会静默。若希望单一所有者，可裁定由 domain 或某个常量模块持有。
- **C11** `MockLePaoAdapter._build` 的「`str` 字段透传 / 其余按可缺测数值解析」分派依赖 base.py **没有** `from __future__ import annotations`（注解是被求值的对象，故 `field.type is str` 成立）。若将来加上那行 import，文本列会走数值解析并**立刻抛 `ValueError`**（响亮，不静默）。
- **C12** 只有 `parse_batch_key`（读侧），**没有 `make_batch_key`（写侧）**——brief 的 Produces 里没有它，我没擅自加。后果：Task 6 仍需自己拼 `f"{academic_year}|{timepoint}"`，格式若有第二个所有者，漂移会在 Task 10 调 `parse_batch_key` 时响亮报错（不会静默）。若要让写侧也只有一个所有者，建议裁定补一个 `make_batch_key`。
- **C13** 测试条数偏离 brief Step 4 的「7 passed」→ 实际 43 条，原因见 §3；brief 原文 6 个测试函数逐字未改。
- **C14** `HttpLePaoAdapter` 只保存 `base_url`/`token`，无 HTTP 客户端/重试/鉴权/超时（brief 与 spec §3.4 的要求）；docstring 注明 `token` 不得写进日志或异常消息，未来实现时需遵守。
- **C15** 仓库启用了 `core.autocrlf`：夹具与源码以 **LF 入库**（提交 blob 是 LF），检出到 Windows 工作区可能变成 CRLF。已实测 CRLF 副本解析结果与 LF 完全一致，故不构成风险，仅记录。

---

## 7. 修复轮次 1（review findings 12 项：2 Important + 2 Ruling + 8 Minor）

- 起点：分支 `feature/plan-01-data-foundation`，HEAD `7f28221`，Task 4 实现提交 `3de6c22`；修复前 **112 passed**
- 结果：**143 passed**（净增 31），`-W error` 下同样 **143 passed**、零警告；`tests/adapters` 43 → **74**
- 变更文件 5 个：`base.py`（165→227 行）、`mock_lepao.py`（353→473 行）、`http_lepao.py`（59→72 行）、`test_contract.py`（271→548 行）、`tests/fixtures/lepao_sample/fitness.csv`（1 格）；`git diff --stat` = 556 insertions / 84 deletions
- 12 项**全部落地**，无一项「已完成可跳过」（已逐项核对 HEAD 上的代码，没有前一次派发留下的痕迹）
- **未触碰**：`app/domain/`、`app/db/`、`app/refdata.py`、`backend/data/national_standard_2014.csv` 及其 README、architecture 测试、`pyproject.toml`、`.gitignore`；`http_lepao.py` 仍是骨架（四方法 `NotImplementedError`，未加任何 HTTP 行为）；未加 `clean_survey`；未放宽问卷空白单元格（Ruling 34）

### 7.0 命令与输出（原文）

```
cd backend; C:\Python\python.exe -m pytest -q
........................................................................ [ 50%]
....................................................................... [100%]
143 passed in 1.59s

cd backend; C:\Python\python.exe -m pytest -q -W error
143 passed in 0.66s

cd backend; C:\Python\python.exe -m pytest tests/adapters -q
74 passed in 0.15s
```

修复前同一命令的基线：`112 passed in 0.61s`（本轮开工时实测复现）。

证据探针是临时文件 `backend/_probe_task4.py`（不属于仓库，用完即删；`Test-Path _probe_task4.py` → `False`）。

### 7.1 I1 — `nan` 经 JSON 列进入 `dimensions`（Important）

**改了什么**

- `mock_lepao._dimension_scores`：`float(value)` 之后加 `math.isfinite(score)` 检查，非有限值抛 `ValueError`，消息带**文件名 + `DictReader.line_num` + 列名 + 出错的维度键**，与模块其余错误同形。
- `mock_lepao._json_object` docstring 明写：本函数只校验「是合法 JSON 对象」，`raw_answers` 声明为无类型 `dict`、**有意不做**数值检查（见关切 N3）；`_survey` 里 `raw_answers=` 那一行也加了行内注释。
- `base.py` 模块 docstring 第 2 条补上 JSON 列的 `allow_nan=False` 要求（Ruling 39 的生产方一侧）；`mock_lepao` 模块 docstring 的 nan 要点扩到 `dimensions`；`http_lepao` 的契约形状清单同步补一条。

**证据（探针实测，Python 3.11.1）**

```
json.loads('{"a": NaN}')            -> {'a': nan}
json.dumps({'a': nan})  (缺省)       -> {"a": NaN}
float(json.loads(...)['a']) isfinite -> False
写盘的 dimensions 单元格             -> {"\u8fd0\u52a8\u4e50\u8da3": NaN}
修复后 fetch_survey(None) -> ValueError: survey.csv 第 2 行 dimensions 的维度值是非有限值: '运动乐趣'=nan；JSON 列必须用 allow_nan=False 序列化，缺测不得写成 NaN/Infinity
```

即：写盘（`json.dumps` 缺省）→ 读回（`json.loads` 缺省）→ `float()` 三步全都不报错，第四步被新检查拦下。

**覆盖测试**

- `test_nan_literal_inside_dimensions_json_is_rejected[nan|inf|-inf]`（新增，参数化 3 条）：用 `json.dumps({"运动乐趣": float("nan")})` 写 `survey.csv` 到 `tmp_path`，先 `assert "NaN" in dumped or "Infinity" in dumped` 钉住攻击面成立，再断言 `ValueError`，`match=r"survey\.csv 第 2 行 dimensions 的维度值是非有限值"`。形状照抄 `test_nan_literal_cell_is_rejected`。
- `test_no_numeric_cell_becomes_nan_or_inf`（扩充）：迭代源从 `fetch_fitness`/`fetch_body_comp` 扩到**加上 `fetch_survey`**；除数据类字段里的 `float` 外，再逐个检查 `dimensions` 的每个值既 `isinstance(score, float)` 又 `math.isfinite(score)`。`raw_answers` 有意不在断言范围内（行内注释写明）。

### 7.2 I2 — `since` 过滤拿规范化水位线比未规范化记录日期（Important）

**改了什么**

- `_validated_since` 返回类型由 `str | None` 改为 **`dt.date | None`**（不再需要「归一成字符串好让字典序成立」这个前提）。
- `_is_after(value, watermark, *, source, line_no, column)`：记录日期用 `dt.date.fromisoformat` 解析后**比 `date` 对象**；解析失败抛 `ValueError`，消息带文件名、行号、列名。空日期（`""`）不解析、排在任何日期之前（保持 C8 行为）；`watermark is None`（全量）时也不解析（见关切 N2）。
- 三个调用点（`_fitness`/`_body_comp`/`_survey`）传入 `source`/`line_no`/`column`。
- **删掉了那段无效的推诿**：原 docstring 说「格式合法性归 Task 5 的清洗层管」——过滤发生在 Task 5 **之前**，被 `_is_after` 丢掉的行根本到不了清洗层。新 docstring 改成实测的三种形状 + Ruling 38 的理由。
- `base.py` 模块 docstring 第 3 条**明写契约**：记录侧日期列必须是零填充 `YYYY-MM-DD`、不带时间部分，并声明「读取侧实现按此强制校验，文档本身不算兜底」。

**证据（探针实测；「修复前」= 复刻旧实现的字符串比较，「修复后」= 真跑一遍 `fetch_fitness`）**

```
记录 '2025-9-5' vs 水位线 '2025-10-01'      （记录其实更早，不该被抽到）
  修复前（字典序）: _is_after=True
  修复后（date）  : ValueError: fitness.csv 第 2 行 tested_on 不是合法的 ISO 日期: '2025-9-5'；CSV 契约要求零填充的 YYYY-MM-DD 且不带时间部分（带 T 后缀会让恰等于水位线的记录被永久重复抽取）

记录 '2025-09-04T10:00' vs 水位线 '2025-09-04'   （同一天，排他语义要求不抽）
  修复前（字典序）: _is_after=True          ← 排他语义被击穿，永久重复抽取
  修复后（date）  : ValueError: fitness.csv 第 2 行 tested_on 不是合法的 ISO 日期: '2025-09-04T10:00'；…

记录 '2025-09-04' vs 水位线 '2025-09-04'    （同一天，排他语义要求不抽）
  修复前（字典序）: _is_after=False
  修复后（date）  : 抽出 []                 ← 排他语义保住

记录 '20250904' vs 水位线 '2025-09-04'      （紧凑写法，同一天；指令未列，探针实测发现）
  修复前（字典序）: _is_after=True          ← 同样击穿排他语义
  修复后（date）  : 抽出 []
```

**与派发指令的一处偏离（需裁定，关切 N1）**：指令要求测「非零填充日期 `2025-9-5` 对零填充水位线**排序正确**」，但实测 `date.fromisoformat('2025-9-5')` 在 Python 3.11.1 **抛 `ValueError`**（它接受 `20250904`，不接受 `2025-9-5`）。按指令指定的实现（`fromisoformat` + 解析失败即抛），非零填充日期的结果是**响亮失败**而不是「按日历排对」。

**覆盖测试**

- `test_record_dated_exactly_since_is_excluded`（新增）：`tmp_path` 单行夹具，`since` 恰等于记录日期 → `[]`；早一天 → 1 条。
- `test_time_suffixed_record_date_raises_instead_of_breaking_exclusion`（新增）：先 `assert "2025-09-04T10:00" > "2025-09-04"` 钉住「字符串比较确实是错的」，再断言 `ValueError`（`match` 含文件名/行号/列名）。
- `test_non_padded_or_non_iso_record_date_raises_when_filtering[2025-9-5|04/09/2025|2025-09-04 10:00]`（新增，参数化 3 条）。
- `test_compact_iso_record_date_is_accepted_when_filtering`（新增）：`20250904` 合法且按日历正确排除/包含。
- `test_record_date_format_is_only_enforced_when_filtering`（新增）：钉住 N2 那条有意的不对称。
- 既有 `test_since_is_exclusive_on_*` 三条、`test_since_after_every_row_yields_empty`、`test_non_iso_since_raises_value_error` 全部保持绿（未改一字）。

### 7.3 Ruling 35 — `base.make_batch_key`

**改了什么**：`base.py` 新增 `make_batch_key(academic_year, timepoint) -> str`，复用既有 `BATCH_KEY_SEPARATOR` 与 `TIMEPOINTS`；学年不是「四位-四位」（含混进分隔符的情况）或时点越域 → `ValueError` 并带原值。模块 docstring 第 4 条改为「只由 `parse_batch_key` 解析、只由 `make_batch_key` 构造——读写两侧都只有一个所有者」。

**证据**

```
make_batch_key('2025-2026', 'week1')  = '2025-2026|week1'   parse -> ('2025-2026', 'week1')
make_batch_key('2025-2026', 'week16') = '2025-2026|week16'  parse -> ('2025-2026', 'week16')
make_batch_key('2025-2026', 'week8')  = '2025-2026|week8'   parse -> ('2025-2026', 'week8')
make_batch_key('2025-2026', 'week9') -> ValueError: timepoint 非法: 'week9'；合法值: ['week1', 'week16', 'week8']
make_batch_key('25-26', 'week1')     -> ValueError: academic_year 非法: '25-26'；应形如 "2025-2026"，即「四位-四位」，且不含分隔符 '|'
```

**覆盖测试**：`test_make_batch_key_is_the_exact_inverse_of_parse_batch_key[week1|week8|week16]`（新增，遍历全部合法时点，断言 `parse(make(...)) == (...)` 且 `make(*parse(k)) == k`）、`test_make_batch_key_rejects_malformed`（新增，5 条畸形，含「学年里混进分隔符」）、`test_fixture_batch_keys_survive_a_parse_make_roundtrip`（新增，夹具三个 `batch_key` 全部往返恒等）。

### 7.4 Ruling 36 — 8 个 CSV 契约常量迁到 `base.py`

**改了什么**：`STUDENTS_FILENAME` / `FITNESS_FILENAME` / `BODY_COMP_FILENAME` / `SURVEY_FILENAME` / `FITNESS_COLUMNS` / `BODY_COMP_COLUMNS` / `SURVEY_COLUMNS` / `STUDENT_COLUMNS` 全部搬到 `base.py`（放在三个数据类之后）。三个数据类支撑的列序仍由 `fields(...)` 推导（`from dataclasses import dataclass, fields`），**没有手抄第二份**；`STUDENT_COLUMNS` 照原样搬（含「与 ORM `Student` 业务列一一对应、不含自增 id」的注释）。`mock_lepao.py` 改成从 `base` import 这八个；两个模块的 docstring 都改了「清单唯一出处」的表述。

**覆盖测试**：`test_contract_constants_live_in_base_module`（新增）——逐个断言八个常量 `hasattr(base, name)`，且 `getattr(mock_lepao, name) is getattr(base, name)`（**同一对象**，钉住没有第二份真相）；再断言三个列序等于 `dataclasses.fields()` 推导值、`STUDENT_COLUMNS` 等于六列。既有 `test_fixture_students_header_matches_contract`（钉 `STUDENT_COLUMNS`）与 `test_fixture_header_equals_dataclass_field_order` 保持绿；`test_contract.py` 顶部的 `from app.adapters.mock_lepao import STUDENT_COLUMNS` 已改为从 `base` 导入。

### 7.5 八个 Minor

| # | 改了什么 | 证据 | 覆盖测试 |
|---|---|---|---|
| M1 | 夹具 `fitness.csv` 第 2 行 `sit_and_reach_cm` 由 `6.2` 改为 **`-1.3`**（Ruling 21 的负坐位体前屈） | `git diff` = `1 file changed, 1 insertion(+), 1 deletion(-)`；shell 复核该行现为 `…,9.18,-1.3,168,0,268.0` | `test_real_zero_stays_zero_and_is_not_confused_with_missing` 补 `== -1.3` 与 `is not None` 两条断言 |
| M2 | 「不是合法数值」分支现在有测试，且 `match` 同时要求文件名+行号+列名 | `ValueError: fitness.csv 第 2 行 vital_capacity_ml 不是合法数值: '四千'` | `test_error_message_names_file_line_and_column`（新增） |
| M3 | 生成器断言参数化到四个方法（原先只测 `fetch_fitness`，把 `_students` 改成列表推导不会红） | 四条全过 | `test_every_fetch_method_returns_a_generator[4 方法]`（新增）；brief 原文的 `test_mock_returns_iterator_not_list` 一字未改 |
| M4 | `_check_header` 报**第一处**不一致的列号（1 起与 0 起都给）与两边列名；缺列时给 `（缺列）` 而不是 IndexError | `…第 1 列（下标 0）期望 'student_no'，实际 'batch_key'；…` 与 `…第 11 列（下标 10）期望 'distance_run_s'，实际 '（缺列）'；…`（完整列表仍附在后面） | `test_header_mismatch_names_the_first_differing_position`（新增，含错位与缺列两支）；既有 `test_wrong_column_order_raises`（`match="表头"`）保持绿 |
| M5 | 新增 `_check_row_shape`，在 `_read` 里与表头检查配对：短行（`restval=None` 补齐）与长行（塞进 `row[None]`）都抛 `ValueError` | 短行：`fitness.csv 第 2 行字段数与表头不符：期望 11 列，实际 3 列（缺 8 列 ['height_cm', …]）`；长行：`…期望 11 列，实际 12 列（多出 1 个字段 ['多出来的一格']）` | `test_ragged_row_is_rejected[extra_fields=0|1]`（新增，参数化 2 条） |
| M6 | `_build` 的分派由 `field.type is str` 改为**显式点名**的 `TEXT_COLUMNS: frozenset[str]` | 见下方专段 | `test_text_column_set_matches_dataclass_declarations`、`test_all_digit_student_no_stays_text`（均新增） |
| M8 | `HttpLePaoAdapter.token` → **`self._token`**；另加显式 `__repr__` 只回显 `base_url` | `repr()` 里没有 token；`hasattr(adapter, "token")` 为 False | `test_http_adapter_does_not_expose_token`（新增） |
| M9 | `http_lepao.py:4-5`、`test_contract.py` 模块 docstring、以及本报告 §1/§2 的过头表述全部改写：与 HTTP 骨架**共享**的只有 `test_satisfies_adapter_contract` 与 `test_http_skeleton_raises_for_every_method`，其余全是 Mock 专属行为测试；并明写「真实实现落地时必须补齐行为契约测试」 | 三处文本均已 shell 复核（`Select-String` 命中 `test_satisfies_adapter_contract` 于 http_lepao.py:5） | 文档改动，无测试；本报告 §1/§2 各加了一条指向本节的更正标记 |

**M6 证据（探针实测）**

```
float('2024010101')                  -> 2024010101.0 （成功，不抛）
加了 __future__ 后 field.type        -> 'str'
  field.type is str                  -> False （旧分派据此走 _float_cell）
  _float_cell('2024010101')          -> 2024010101.0 （静默变成浮点学号）
'student_no' in TEXT_COLUMNS         -> True
新分派下 record.student_no           -> '2024010101' str
```

第一行证明「走偏不会报错」这个前提成立（旧 docstring 声称会「立刻抛 `ValueError`」是**错的**，C11 的这条判断已在代码注释里改正）；中间三行用 `exec` 编译一段带 `from __future__ import annotations` 的数据类，证明 `field.type` 会变成字符串 `'str'`，旧分派据此把学号送进 `_float_cell` 并得到 `2024010101.0`；最后一行证明新的显式集合把 `student_no` 路由到文本解析器，产出仍是 `str`。

### 7.6 写盘校验（本项目已被坑六次，本轮**又踩了一次**）

- **`fitness.csv` 的两次 SearchReplace 都报成功、字节却没落盘**：编辑工具回显了正确的 diff，但 shell `Get-Content` 仍是 `6.2`，`git diff --stat` 对该文件为空，`Length` 仍是 371（`-1.3` 应为 372），文件非只读。改用 PowerShell `[IO.File]::WriteAllText(..., UTF8Encoding($false))` 重写后 shell 复核：`bytes=372 CR=0 BOM=False`、`git diff --stat` 显示 `1 file changed, 1 insertion(+), 1 deletion(-)`。**只靠编辑器内复读会漏掉这次失败**——是 `pytest` 的 `assert 6.2 == -1.3` 把它暴露出来的。
- 其余 4 个文件逐个 shell 复核：`Select-String` 命中全部关键标记（`def make_batch_key` / `STUDENT_COLUMNS` / `TEXT_COLUMNS` / `_check_row_shape` / `record_date > watermark` / `math.isfinite(score)` / `field.name in TEXT_COLUMNS` / `self._token` / `def __repr__`），`self.token` 已无命中；`git ls-files --eol` 全部 `i/lf w/lf`；`BOM=False`。
- 本报告改完后从 shell 复读：§1–§6 全部存活，§7 只出现一次（见下方复核输出）。
- 探针 `backend/_probe_task4.py` 用完即删，`git status --short` 只剩那 5 个 M。

### 7.7 关切（本轮新增；代码注释/docstring 里写的每一条都在此）

- **N1（需裁定）I2 的修法与派发指令的一处偏离。** 指令要求测「`2025-9-5` 对零填充水位线**排序正确**」，但实测 `date.fromisoformat('2025-9-5')` 在 Python 3.11.1 抛 `ValueError`（它接受 `20250904`，不接受非零填充）。按指令指定的实现，非零填充日期是**响亮失败**而不是「排对」。我认为应接受：契约已明写必须零填充，响亮失败比静默多抽更容易定位写错的生产方；但这比 reviewer 的「over-inclusion 不算 silent corruption」定级更严——**它把一次良性重抽变成了中断整条管道**。若希望保留宽容（例如额外用 `strptime` 兜一层非零填充），请裁定。
- **N2（需裁定）日期格式只在增量模式下强制。** `watermark is None`（全量）时 `_is_after` 提前返回 True、不解析记录日期，故 `2025-9-5` 在全量拉取里原样透传给 Task 5。这是有意的不对称：全量模式不需要比较，此时把格式问题升级成中断管道，等于抢走清洗层该记一条 `cleaning_log` 的活（与 C7「缺学号/缺日期归清洗层」一致）。已写进 `_is_after` docstring，并由 `test_record_date_format_is_only_enforced_when_filtering` 钉住。若希望全量也强制，请裁定。
- **N3（需裁定）`raw_answers` 有意不做有限性检查。** 它声明为无类型 `dict`，值可以是 int、字符串甚至嵌套结构，套浮点契约会误杀合法数据。后果：写侧若在 `raw_answers` 里塞一个 `NaN`，抽取阶段不拦，只靠 Task 6 的 `allow_nan=False`（Ruling 39）与 Task 5 兜底。已写进 `_json_object` docstring 与 `_survey` 行内注释。若希望也拦（例如只对 `float` 类型的值查 `isfinite`），请裁定。
- **N4** M5 的行长度检查把短行与长行**一律**升级为 `ValueError`。方向安全（原先补出来的是 `None`/`""`，不会变成 `0` 或 `nan`，且 `DictReader` 按名取值不会错位），但更严格：若真实乐跑接口的 CSV 导出带尾随逗号（长行），管道会在抽取阶段中断。第一批的生产方是 Task 6，可控。
- **N5** `TEXT_COLUMNS` 是一份**显式点名的第二份真相**（与数据类声明并存）——这正是 M6 要求的取舍：用「一份需要测试看守的清单」换掉「一个依赖注解求值时机的隐式反射」。看守者是 `test_text_column_set_matches_dataclass_declarations`，它用 `typing.get_type_hints`（对延迟注解同样成立），所以 base.py 哪天加了 `from __future__ import annotations` 也不会假绿。集合含 `filled_on`：它不经 `_build`（`RawSurveyRecord` 单独构造），但同样走 `_text_cell`。
- **N6** 探针发现的**第四种**日期形状（指令未列）：`20250904` 这类紧凑写法在修复前同样**击穿排他语义**——水位线被 `_validated_since` 归一成 `2025-09-04`，而 `'20250904' > '2025-09-04'` 为 True，那条记录会被永久重复抽取。也就是说旧实现连它自己想支持的「合法但非规范写法归一」都没做对。修复后按 `date` 比较正确排除，已补 `test_compact_iso_record_date_is_accepted_when_filtering`。
- **N7** M8 之后 `HttpLePaoAdapter` 的 token 只能通过 `self._token` 访问；未来实现若要在子类或方法里用，请沿用私有名，且不得写进日志、异常消息或 `repr`（docstring 已写）。
- **N8** 夹具 `fitness.csv` 第 2 行现在同时承载三种边界：空 `vital_capacity_ml`、`strength_count=0`、`sit_and_reach_cm=-1.3`。后续 Task 5/7/9 若拿这条夹具当黄金用例输入，需知道坐位体前屈已是负数（`-1.3` 在国标 2014 表里是合法低值，不是异常值）。
- **N9** C15 的 `core.autocrlf` 情况本轮仍在：写 `fitness.csv` 时 git 提示 `LF will be replaced by CRLF the next time Git touches it`，入库仍是 LF（`git ls-files --eol` = `i/lf w/lf`），不构成风险。
- **N10** 本报告 §4 的行数表已过期（那是 `3de6c22` 的快照）；本轮后的行数为 base.py 227、mock_lepao.py 473、http_lepao.py 72、test_contract.py 548。§1/§2 的两处过头表述已就地加更正标记指向本节，原文保留以便追溯。

---

## 8. 修复轮次 2（Ruling 41 + 42：关闭轮次 1 的关切 N2 与 N3）

- 起点：分支 `feature/plan-01-data-foundation`，HEAD `11453eb`，Task 4 提交 `3de6c22` `52e16b8`；修复前 **143 passed**（开工时实测复现：`143 passed in 0.63s`）
- 结果：**176 passed**（净增 33），`-W error` 下同样 **176 passed**、零警告、零 skip；`tests/adapters` 74 → **107**
- 变更文件 4 个：`mock_lepao.py`（473→552 行）、`base.py`（227→238 行）、`http_lepao.py`（72→78 行）、`test_contract.py`（548→753 行）；`git diff --stat` = **388 insertions / 87 deletions**
- 两项**都不是已完成状态**：开工时逐个核对 HEAD 上的代码——`_is_after` 仍写着 `if watermark is None: return True` 的提前返回，`_json_object` docstring 仍写着「有意不做数值检查」，`_survey` 里 `raw_answers=` 那行仍是「不在浮点契约内」的注释。无一项可跳过（前两次派发重复执行的教训已核）
- **未触碰**：`app/domain/`、`app/db/`、`app/refdata.py`、`backend/data/`、architecture 测试、`pyproject.toml`、`.gitignore`、`base.py` 三个数据类的字段声明（base.py 的 diff 逐行核对，只有模块 docstring 的第 2、3 条）；`http_lepao.py` 仍是骨架（四方法 `NotImplementedError`，未加任何 HTTP 行为）；未加 `clean_survey`；未加任何宽容日期解析（Ruling 40）；未改计划文件

### 8.0 命令与输出（原文）

```
cd backend; C:\Python\python.exe -m pytest -q
........................................................................ [ 40%]
........................................................................ [ 81%]
................................                                         [100%]
176 passed in 0.80s

cd backend; C:\Python\python.exe -m pytest -q -W error
176 passed in 0.80s

cd backend; C:\Python\python.exe -m pytest tests/adapters -q
107 passed in 0.29s
```

33 条净增的构成：轮次 1 的 `test_record_date_format_is_only_enforced_when_filtering` 退役（−1）；Item 1 新增 28 条（12 + 6 + 9 + 1）；Item 2 新增 6 条（1 + 1 + 3 + 1）。28 + 6 − 1 = 33，与 143 → 176 对得上；`tests/adapters` 74 → 107 同样是 +33（本轮没动别的目录）。

证据探针是临时文件 `backend/_probe_r2.py`（不属于仓库，用完即删；`Test-Path _probe_r2.py` → `False`）。

### 8.1 Item 1（Ruling 41）— 记录侧日期无条件校验并归一化

**改了什么**

- 新增 `_record_date(raw, *, source, line_no, column) -> dt.date`：**唯一**的记录侧日期解析点，无条件执行；解析失败抛带文件名 + `DictReader.line_num` + 列名的 `ValueError`。docstring 写了裁定的三条实质理由（校验不得是调用模式的副作用；`body_composition.measured_on` 在 ORM 里是 `date` 列，透传原始串会在 Task 10 写库时炸成远因错误；归一化让 Ruling 38 由适配器**强制**而非只声明），并明写按 Ruling 40 不加宽容层、宽容属于 `http_lepao.py` 自己的边界。
- `_is_after` **签名与职责双双收窄**：由 `(value: str | None, watermark, *, source, line_no, column)` 改成 `(record_date: dt.date, watermark: dt.date | None)`，只做比较，不再解析、不再报错。两侧都是 `date` 对象，故既没有字符串字典序，也不需要二次解析。
- 三个调用点（`_fitness` / `_body_comp` / `_survey`）改成「先 `_record_date` → 再 `_is_after` → 再把 `.isoformat()` 写进记录」。**过滤用的与写进记录的是同一个 `date` 对象**，两者不可能再分叉（这是轮次 1 的 I2 只做到一半的部分）。
- `_build` 与 `TEXT_COLUMNS` 未动：日期列仍走 `_text_cell`，只是它现在收到的是已归一化的 ISO 串，`strip()` 成为 no-op。
- `base.py` 模块 docstring 第 3 条改为「无条件强制校验并归一化」并补 Ruling 40 的边界归属；`http_lepao.py` 契约形状清单第 1 条同步；`mock_lepao.py` 模块 docstring 的日期要点重写。

**证据（探针实测，Python 3.11.1；「修复前」= HEAD `11453eb` 上跑同一探针，「修复后」= 改动后重跑）**

```
修复前（不对称，关切 N2）
  '2025-09-04T10:00'  全量 since=None       -> 抽出 ['2025-09-04T10:00']  ← 原样透传，未校验
  '2025-09-04T10:00'  增量 since=2025-09-04 -> ValueError: fitness.csv 第 2 行 tested_on 不是合法的 ISO 日期: …
  '2025-9-5'          全量 since=None       -> 抽出 ['2025-9-5']          ← 原样透传，未校验
  '2025-9-5'          增量 since=2025-09-04 -> ValueError: …
  ''                  全量 since=None       -> 抽出 ['']                  ← 原样透传，未校验
  ''                  增量 since=2025-09-04 -> 抽出 []                    ← 静默排除
  '20250904'          全量 since=None       -> 抽出 ['20250904']          ← 未归一化

修复后（三个源 × 两种模式，同一个畸形日期一律报错）
  [tested_on  ] 全量 -> ValueError: fitness.csv 第 2 行 tested_on 不是合法的 ISO 日期:
                      '2025-09-04T10:00'；CSV 契约要求零填充的 YYYY-MM-DD 且不带时间部分
                      （带 T 后缀会让恰等于水位线的记录被永久重复抽取）
  [tested_on  ] 增量 -> ValueError: （与上一行逐字相同）
  [measured_on] 全量 -> ValueError: body_comp.csv 第 2 行 measured_on 不是合法的 ISO 日期: '2025-09-04T10:00'；…
  [measured_on] 增量 -> ValueError: （同上）
  [filled_on  ] 全量 -> ValueError: survey.csv 第 2 行 filled_on 不是合法的 ISO 日期: '2025-09-04T10:00'；…
  [filled_on  ] 增量 -> ValueError: （同上）
  '2025-9-5' 与 '' 在三个源 × 两种模式下同样 6 + 6 条全部 ValueError（无宽容层，Ruling 40）

归一化往返（20250904 进 → "2025-09-04" 出）
  [tested_on  ] 全量 -> '2025-09-04'  增量(=水位线 2025-09-04) -> []  增量(2025-09-03) -> '2025-09-04'
  [measured_on] 全量 -> '2025-09-04'  增量(=水位线)            -> []  增量(早一天)     -> '2025-09-04'
  [filled_on  ] 全量 -> '2025-09-04'  增量(=水位线)            -> []  增量(早一天)     -> '2025-09-04'
```

第三段同时钉住两件事：紧凑写法归一为零填充，且恰等于水位线的那条**仍被排除**——增量语义没被这次改动破坏。

`date.fromisoformat` 的接受面（实测，是「不加宽容层」这条选择的事实基础）：`'2025-09-04'`→OK、`'20250904'`→OK（归一为 `2025-09-04`）、`'2025-9-5'` / `'2025-09-04T10:00'` / `'2025-09-04 10:00'` / `''` → 均 `ValueError`。

**退役的轮次 1 测试（派发指令要求点名）**

`test_record_date_format_is_only_enforced_when_filtering` **整条删除**。它断言 `_write_fitness_row(tested_on="2025-9-5")` 之后 `fetch_fitness(None)` 返回 `["2025-9-5"]`——正是 Ruling 41 撤掉的那处不对称，留着就是一条钉住已废除行为的测试（而且它现在会红）。取代它的是下面四条；原位置留了一行分节注释说明退役原因，`Select-String` 确认该测试名在文件里只剩这一处历史指称、不是活测试。

**覆盖测试（28 条）**

- `test_malformed_record_date_raises_in_full_mode_too`（12 = 3 源 × 4 畸形：`2025-09-04T10:00` / `2025-9-5` / `04/09/2025` / `""`）：`since=None` 下全部 `ValueError`，`match` 用 `re.escape(filename)` 同时要求文件名、行号、列名。
- `test_malformed_record_date_raises_in_incremental_mode_as_before`（6 = 3 源 × 2 畸形）：钉住增量模式那一半**没有**变。
- `test_record_date_is_normalised_in_full_mode`（9 = 3 源 × 3 组 `raw→expected`）：`20250904`→`2025-09-04`（归一化）、`2025-09-04`→自身（幂等）、`2025-12-07`→自身；另断言产出类型仍是 `str`（数据类字段声明未动）。
- `test_incremental_filtering_is_unchanged_by_unconditional_normalisation`（1）：恰等于水位线→排除、早一天→返回、晚于记录→排除。
- 三个日期列全覆盖由 `DATE_CASES` / `DATE_IDS`（`fitness.tested_on` / `body_comp.measured_on` / `survey.filled_on`）参数化保证，新增辅助 `_write_date_row` 按源填合法的其他列。
- `test_compact_iso_record_date_is_accepted_when_filtering`（轮次 1 的，扩充）：由 `len(...) == 1` 改成断言产出的 `tested_on == "2025-09-04"`，顺带钉住增量模式下也归一化。
- 轮次 1 的 `test_since_is_exclusive_on_*` 三条、`test_record_dated_exactly_since_is_excluded`、`test_time_suffixed_record_date_raises_instead_of_breaking_exclusion`、`test_non_padded_or_non_iso_record_date_raises_when_filtering`、`test_since_after_every_row_yields_empty`、`test_non_iso_since_raises_value_error` **全部未改一字**且保持绿。

### 8.2 Item 2（Ruling 42）— 有限性不变式扩到 `raw_answers`

**改了什么**

- 新增 `_assert_finite_floats(value, path, *, source, line_no, column)`：递归遍历 dict 与 list，**只对 `float` 实例**查 `math.isfinite`，非有限即抛带文件名/行号/列名/**键路径**的 `ValueError`。
- 新增 `_key_path(prefix, key)`：`str` 键渲染成 `['键']`，列表下标渲染成 `[0]`，于是路径形如 `raw_answers['第3题']['子项']`、`raw_answers['scores'][1]`。
- 挂进 `_json_object`（`dimensions` 与 `raw_answers` **共用**的那个函数），解析成功后立即遍历——两列走同一条代码路径，不留例外。
- `_json_object` docstring 删掉轮次 1 那段「有意不做数值检查」的推诿，改成裁定理由 + 「只查 float 实例」为何不会误杀合法数据 + `allow_nan=False` 是纵深防御的**第二道而非替代**（它只保证写出去的字节合法，管不了手写夹具、真实乐跑接口、将来的回填脚本写进来的东西）。
- `_dimension_scores` **一字未放松**（`dict[str, float]` 的更严契约保留），docstring 补了它与递归遍历的分工。
- `base.py` 第 2 条、`http_lepao.py` 契约清单第 4 条、`mock_lepao.py` 模块 docstring 的 nan 要点、`_survey` 里 `raw_answers=` 那行的行内注释，四处同步。

**证据（探针实测）**

```
写盘字节     -> {"第3题": {"子项": NaN}}      （json.dumps 缺省 allow_nan=True，写得出来）
json.loads   -> {'第3题': {'子项': nan}}      （缺省又读得回来，两头都不报错）
修复前 fetch_survey(None) -> raw_answers={'第3题': {'子项': nan}, 'list': [1, inf]}  ← 一路透传（关切 N3）
修复后 fetch_survey(None) -> ValueError: survey.csv 第 2 行 raw_answers 含非有限浮点值:
                            raw_answers['第3题']['子项']=nan；JSON 列必须用 allow_nan=False
                            序列化，缺测不得写成 NaN/Infinity

列表下标进键路径   {"scores": [1, Infinity]}        -> … raw_answers['scores'][1]=inf；…
四层深            {"a": {"b": {"c": [-Infinity]}}}  -> … raw_answers['a']['b']['c'][0]=-inf；…

合法 raw_answers 原样透传（int / str / None / bool / 嵌套容器 / 有限 float）
  深比较相等         -> True
  重新序列化字节相等 -> True    （json.dumps(读回的结构) == 写进去的那串）
  scores 仍是 int    -> ['int', 'int', 'int']  （没被升成 float）
  已答 is True       -> True                   （布尔没被当成数）
  跳过 is None       -> True

bool 的类型前提（实测）
  isinstance(True, int)   -> True    （bool 是 int 子类）
  isinstance(True, float) -> False   （但不是 float 子类，故「只查 float」天然安全）

dimensions 的两层分工
  真 float nan -> ValueError: survey.csv 第 2 行 dimensions 含非有限浮点值: dimensions['运动乐趣']=nan；…   ← 递归遍历先拦
  字符串 'nan' -> ValueError: survey.csv 第 2 行 dimensions 的维度值是非有限值: '运动乐趣'='nan'；…        ← 只有 _dimension_scores 能拦
```

最后两行是「扩大覆盖面而不是放松」的实证：递归遍历放过 `str`，而 `_dimension_scores` 的 `float(value)` 把字符串 `"nan"` 变成真 nan 再拦下——那一层**不是死代码**。

**覆盖测试（6 条新增 + 2 条改动）**

- `test_nan_nested_two_levels_deep_in_raw_answers_is_rejected`（1）：两层深的 nan；先 `assert "NaN" in dumped` 钉住「写得出来」，再 `assert x != x` 钉住「读回来的确实是 nan」，最后 `match` 要求完整键路径 `raw_answers\['第3题'\]\['子项'\]=nan`。
- `test_non_finite_float_at_any_depth_of_raw_answers_is_rejected`（3）：列表下标、四层深、顶层，各自断言键路径。
- `test_legitimate_raw_answers_passes_through_unchanged`（1）：深比较相等 + **逐字节相等** + int 没升成 float + 布尔/`None` 身份断言；开头 `assert isinstance(True, int) and not isinstance(True, float)` 钉住判据前提。
- `test_string_encoded_nan_in_dimensions_is_still_caught`（1）：钉住 `_dimension_scores` 那层没被取代。
- `test_nan_literal_inside_dimensions_json_is_rejected`（轮次 1 的，**改 `match`**）：3 条参数化本身一字未动，`match` 由 `dimensions 的维度值是非有限值` 改为统一的键路径形状，并把期望字面量一起参数化。原因见关切 R2-N2。
- `test_no_numeric_cell_becomes_nan_or_inf`（轮次 1 的，扩充）：删掉「`raw_answers` 有意不在断言范围内」那条行内注释，改为对 `dimensions` 与 `raw_answers` 两列做递归断言；遍历器 `_walk_floats` 在测试里**另写一份**而不 import 被测函数（用被测代码验被测代码，漏掉的那一支会两边一起漏，测试就绿得毫无意义）。`dimensions` 原有的逐值 `isinstance(score, float)` 断言保留。

### 8.3 写盘校验（本项目已被坑七次）

四个文件逐个 shell 复核，**不用编辑器内复读**：

```
git status --short       -> 只有那 4 个 M，无其他改动、无遗留探针
git diff --stat          -> base.py 15± / http_lepao.py 14± / mock_lepao.py 211± / test_contract.py 235±
                            4 files changed, 388 insertions(+), 87 deletions(-)
git ls-files --eol       -> 四个文件全部 i/lf w/lf
BOM（IO.File.ReadAllBytes）-> base.py False/13152、mock_lepao.py False/28571、
                            http_lepao.py False/5048、test_contract.py False/40902
Select-String 关键标记    -> mock_lepao.py: def _record_date(93)、def _is_after(132，新签名)、
                            def _key_path(228)、def _assert_finite_floats(235)、
                            _assert_finite_floats(parsed, …)(319)、tested_on.isoformat()(488)、
                            measured_on.isoformat()(500)、filled_on.isoformat()(512)
                            base.py: Ruling 42(23)、Ruling 41(32)、Ruling 40(36)
                            http_lepao.py: Ruling 41/40(19-20)、Ruling 42(27)
退役测试名残留            -> 只命中 test_contract.py:530，是分节注释里的历史指称
探针                     -> Test-Path backend/_probe_r2.py = False
```

`base.py` 的 diff 已逐行打印核对：只有模块 docstring 第 2、3 条，**三个数据类的字段声明一行未动**（派发指令的禁区）。

### 8.4 关切（本轮新增；代码注释/docstring 里写的每一条都在此）

- **R2-N1（需裁定）空日期现在在两种模式下都抛 `ValueError`。** 这是 Ruling 41 的必然推论而不是我另加的决定：`date.fromisoformat("")` 抛错，而「解析失败即抛」正是无条件校验的含义。但它**同时撤掉了轮次 1 的两条既有行为**——(a) C8「增量模式下空日期排在任何日期之前被静默排除」；(b) C7 那条推论「缺日期属数据质量问题，交 Task 5 与 `cleaning_log`」。我认为该撤：三个日期列声明为 `str`，契约里没有 `None` 的位置，把空格读成 `""` 会让「缺日期」伪装成一条合法记录一路走到入库；而静默排除更糟（那行数据消失了，谁都不会知道）。**风险面已核查**：spec §10.7「缺失 3–5%」举的例子是「体测某项未测、体成分未测」，指**测量项**而非日期；Ruling 34 又把 `missing`/`outlier`/`unit_error` 限制在 `fitness` 与 `body_comp`，`survey` 只允许 `duplicate`。故 Task 6 的脏数据注入不会写出空日期。**若控制器认为空日期该留给清洗层**，就得给这三列一个 `None` 的位置（即改 `base.py` 的字段声明——本轮禁区），请裁定。已写进 `_record_date` docstring 与 `test_malformed_record_date_raises_in_full_mode_too` docstring。
- **R2-N2 `dimensions` 的非有限值报错消息形状变了。** 递归遍历挂在 `_json_object` 里、先于 `_dimension_scores` 执行，所以真 `float` nan 的消息现在是 `dimensions 含非有限浮点值: dimensions['运动乐趣']=nan`（统一带键路径），不再是轮次 1 的 `dimensions 的维度值是非有限值: '运动乐趣'=nan`。轮次 1 的 `test_nan_literal_inside_dimensions_json_is_rejected` 因此**改了 `match`**（这是本轮第二处被改动的轮次 1 测试；参数化与断言的异常类型未动）。我选了统一形状而不是给 `dimensions` 开一个例外分支：两列同一条消息模板，下游日志与 grep 只需认一种。**若控制器要求保留轮次 1 的原消息**，需要让 `_dimension_scores` 先于遍历执行（即在 `_survey` 里换调用顺序、并给 `_json_object` 加一个「跳过遍历」的开关），请裁定。已写进该测试的 docstring 与 `_dimension_scores` docstring。
- **R2-N3 `_assert_finite_floats` 是递归的，没有显式深度上限。** 事实上不可能由它先触发 `RecursionError`：实测（Python 3.11.1，`sys.getrecursionlimit() == 1000`）`json.loads` 对 2000 层嵌套**自己**就抛 `RecursionError`，而它的扫描器每层消耗约 2 个栈帧，故能被成功解析的嵌套深度上限约 500 层；本函数每层只消耗 1 帧，永远比解析器浅——深度上限由 `json.loads` 隐式给定。若哪天换成流式/非递归 JSON 解析器，这条前提要重新核对。已写进本节，未写进代码注释（那条注释会是给不会发生的情形加的）。
- **R2-N4 日期列仍走 `_build` 的 `TEXT_COLUMNS` 分支。** `_record_date` 产出的 `.isoformat()` 串被塞回行 dict（`{**row, ...}`，不改动 `DictReader` 的产物），再由 `_text_cell` 取走，此时 `strip()` 是 no-op。`TEXT_COLUMNS` 与数据类字段声明都没动，`test_text_column_set_matches_dataclass_declarations` 保持绿。代价：「日期列要解析」这件事在 `_fitness`/`_body_comp`/`_survey` 三处各调用一次 `_record_date`，而 `_build` 对它一无所知——将来若再加第四个带日期的源，容易漏调（漏调的症状是产出未归一化的原始串，且增量模式下仍会被 `_is_after` 的类型不符暴露）。已用 `DATE_CASES` 三源参数化测试兜住现有的三处。
- **R2-N5 解析与过滤的先后顺序**：现在是「先解析日期 → 再判断是否在水位线之后 → 再解析其余单元格」。因此一行即使会被增量过滤掉，它的**日期**也已被校验（Ruling 41 要求的），但它的数值列**不会**被解析（`_build` 在过滤之后）。轮次 1 也是这个顺序，未变。含义：增量模式下，水位线之前那一行若有 `nan` 数值，仍然不会报错。
- **R2-N6 轮次 1 的关切 N1 / N4–N10 本轮未处理**，状态不变。N1（`2025-9-5` 是响亮失败而非「按日历排对」）可视为已由 Ruling 40 关闭——裁定明写「不加宽容解析层」。N2、N3 由本轮关闭。C1/C2/C3/C6 四项跨 Task 裁定请求**仍然待决**，本轮没有触碰计划文件。
- **R2-N7 本报告 §4 与 §7.7 的 N10 行数表都已过期**（分别是 `3de6c22` 与轮次 1 的快照）。本轮后：`base.py` 238 行、`mock_lepao.py` 552 行、`http_lepao.py` 78 行、`test_contract.py` 753 行。原文保留以便追溯。


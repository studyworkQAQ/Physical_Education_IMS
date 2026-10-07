# Plan 02 Task 1 实施报告 — 架构债清偿

- **分支**：`feature/plan-02-prescription-engine`
- **基线 commit**：`e26347f`
- **本 Task commit**：**`1df5e8a`**（一个 commit，未 push，未合并分支）
- **状态**：**DONE_WITH_CONCERNS**（14 条关切，其中 3 条最高优先级 = 计划文本里的事实错误 2 处 +
  开工前工作树就不干净 1 处）。控制者指示「处理评审关切」后：**C1 已闭环**（无损保全 + 还原到 HEAD，
  `git status --short` 现在为空，且 `git apply --check` 验过可一键回放）、**C11 已闭环**
  （用 `git worktree` 在基线上亲测，证明那 +2–3 s 不是本 Task 造成的）；
  **C2 / C3 / C5 是计划文本的错误，代码侧已按正确口径落地，但计划正文与简报需要控制者更正**；
  其余 9 条是我的判断交代或低优先级观察。逐条处置见 §8。
- **本报告内所有行号绑定 commit `1df5e8a`，一律取 shell 口径**（`git grep -n` / python `enumerate`）。
  ⚠️ `git grep` **只搜已跟踪文件**，本 Task 新增的文件（`app/config.py`、`app/adapters/factory.py`、
  `app/db/models/*`、三个新测试文件）在 commit 之前搜不到——报告里那些行号是用 python 直接读文件取的。

---

## 0. 三个闸门数字

| 闸门 | 命令（在 `backend/` 下） | 结果 |
|---|---|---|
| 全量测试 | `python -m pytest -q` | **478 passed / 0 failed**（54.79 s，n=1） |
| 期望通过数 | `python -m pytest --collect-only -q` 末行 | **478 tests collected**（自己数的，没照抄简报；基线 453 + 新增 25） |
| 警告即错误 | `python -m pytest -q -W error` | **478 passed**，0 error（54.46 s，n=1） |
| domain 分支覆盖 | `python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing` | **Miss 0 / BrPart 0 / 100%**（TOTAL 399 stmts / 114 branch；477 passed + 1 skipped） |

覆盖率逐文件（`--cov-branch`）：

```
app\domain\__init__.py         0      0      0      0   100%
app\domain\derive.py         146      0     54      0   100%
app\domain\indicators.py      62      0     14      0   100%
app\domain\percentile.py      94      0     26      0   100%
app\domain\stratify.py        92      0     20      0   100%
app\domain\tables.py           5      0      0      0   100%
----------------------------------------------------------------------
TOTAL                        399      0    114      0   100%
```

基线是 392 stmts / 112 branch → 现在 399 / 114：**+7 stmts**（`COLUMN_BY_ITEM` 1 +
`WHOLE_RECORD` 1 + `CLEANING_FIELDS` 1 + `bmi_of` 的 def/if/return None/return round 4）、
**+2 branch arc**（`bmi_of` 那一个 `if` 的两条弧）。
迁进 domain 的两样东西**都带进了覆盖**（不是靠 import 顺带过）：`bmi_of` 由
`tests/domain/test_indicators.py` 的 3 条测试直接调用（含参数化的 3 个缺测组合，覆盖
`or` 的两个操作数），常量由 2 条字面比对测试断言。故简报里那句「若带不进覆盖说明迁移方式
错了」的关切**不成立**。

那 1 条 skipped 是既有的 `test_backfill_500_students_under_60_seconds`：它检测到 trace 钩子
（`--cov`）就自己跳过，理由与实测区间写在它自己的 docstring 里（Plan01 硬规矩 #42）。
不带 `--cov` 时它照常断言并通过。

## 0.1 禁区复核（commit `1df5e8a` 之后）

```
git diff e26347f..HEAD --stat -- backend/data/     → 空（本 Task 没动 backend/data/）
backend/pe.db                                       → 不存在
backend/data/seed/                                  → 0 个文件
backend/data/national_standard_2014.csv             → 21412 B，sha256[:16] = D2C8E539E2FA0029 ✓
git status --short                                  → **空**（开工前那条 Document/ 修改已按 C1 处置：
                                                       先无损保全、再还原到 HEAD，`git apply --check` 验过可回放）
git diff --exit-code HEAD -- backend/               → exit 0（工作树与提交逐字节一致）
git worktree list                                   → 只剩主树（C11 的基线 worktree 已 remove + prune）
```

以上检查在**三个时点**各跑过一遍：commit 前、commit 后、以及 C11 的
`git worktree add/remove` 之后。三次结果一致。

测量口径：字节与哈希用 python `pathlib.Path.read_bytes()` + `hashlib.sha256`，
**不经 PowerShell 管道**（它会自己加 CRLF）。命令见
`C:\Users\whwenhao\AppData\Local\Temp\pe_blob_eol.py`（临时文件，不入库）。

`.coverage` 与 `.pytest_cache/` 由 pytest 生成，均在 `.gitignore` 里
（`git check-ignore -v backend/.coverage` → `.gitignore:7:.coverage`）。

---

## 1. 改动清单（`git diff e26347f..HEAD --stat -- backend/`，32 文件 / +2503 / −801）

### 1.1 新建（13 个文件）

| 文件 | 行 | 内容 |
|---|---|---|
| `backend/app/config.py` | 43 | `BACKEND_DIR:33` / `DEFAULT_CSV_DIR:38` / `DEFAULT_DB_URL:43`，叶子（只 import `pathlib`） |
| `backend/app/adapters/factory.py` | 109 | `KINDS:38` / `build_adapter:81`，`_build_mock` / `_build_http` 两个分派 |
| `backend/app/db/models/__init__.py` | 91 | 包 docstring（含拆包表 + 「本仓不做迁移，schema 改动 = 重建库」）、`_in_domain` 显式重导出`:62`、五个 `import *` `:66-70`、`from . import feedback, prescription` `:74`、`__all__:76` |
| `backend/app/db/models/_shared.py` | 65 | `_in_domain:20` + `JsonText:31`（**Files 块没列，见关切 C8**） |
| `backend/app/db/models/organisation.py` | 121 | spec §4.1：`Semester` / `Teacher` / `Student` / `CourseSection` / `Enrollment` |
| `backend/app/db/models/assessment.py` | 187 | spec §4.2：4 张表 + **新列 `tested_on:97`** |
| `backend/app/db/models/derived.py` | 243 | spec §4.3：`PercentileSnapshot` / `DerivedMetrics` / `StratificationResult` |
| `backend/app/db/models/prescription.py` | 16 | **只有模块 docstring**（Ruling 5：写明由 Task 2/3/9 填） |
| `backend/app/db/models/feedback.py` | 8 | **只有模块 docstring**（Ruling 5：写明由 Plan 03 填） |
| `backend/app/db/models/ops.py` | 169 | spec §4.6：`DailySyncRun`（**新列 `muscle_line_gaps:95`**）/ `CleaningLog` |
| `backend/tests/architecture/test_layering.py` | 121 | 依赖方向守卫（Step 1） |
| `backend/tests/adapters/test_factory.py` | 88 | `build_adapter` 6 条 |
| `backend/tests/pipeline/test_percentile_stage.py` | 100 | `tested_on` 截断 2 条（一对反证场景） |

### 1.2 删除

`backend/app/db/models.py`（676 行，内容逐字搬进包的六个表模块 + `_shared`）。

### 1.3 修改（生产代码）

| 文件:行（`1df5e8a` 口径） | 改动 |
|---|---|
| `app/domain/indicators.py:104` | **迁入** `COLUMN_BY_ITEM`（6 项，从 `app/seed/fitness.py`） |
| `app/domain/indicators.py:124` | **迁入** `WHOLE_RECORD = "*"`（从 `app/pipeline/clean.py`，见关切 C7） |
| `app/domain/indicators.py:154` | **新增** `CLEANING_FIELDS`（13 个值，`cleaning_log.field` 的唯一所有者） |
| `app/domain/indicators.py:183` | **迁入** `bmi_of`（从 `app/pipeline/run_stratify.py:178`） |
| `app/refdata.py:19,23,28` | `from app.config import BACKEND_DIR`；`DATA_DIR = BACKEND_DIR / "data"`；**迁入** `RANGES_FILENAME` |
| `app/pipeline/clean.py:47` | `from app.domain.indicators import WHOLE_RECORD`（重导出），删掉原 `WHOLE_RECORD = "*"` 定义行 |
| `app/pipeline/run_stratify.py:37-48` | 删掉 `from app.seed.fitness/generate` 两行；`COLUMN_BY_ITEM`、`bmi_of` 改从 domain 导入，`RANGES_FILENAME` 改从 refdata 导入；删掉本地 `def bmi_of`（原 `:178-187`），`__all__` 里的 `"bmi_of"`（现 `:82`）不变 |
| `app/pipeline/percentile_stage.py:147,176,236-237` | `_results_of(session, batch_id, as_of)` + `.where(tested_on <= as_of)`，两个调用点同步 |
| `app/pipeline/daily.py:213,226` | `_fitness_batch`：先查现有行，`test_date = min(现有值, 本条值)`（Step 5） |
| `app/pipeline/daily.py:392` | `_load_sources` 的 upsert 值里加 `"tested_on": tested_on` |
| `app/pipeline/daily.py:644` | 运行记录 upsert 的完整列集合里加 `"muscle_line_gaps": 0` |
| `app/pipeline/daily.py:686-698` | **直接切**：删掉 `run.error_summary = "注意（非错误）：…"`，改成 `run.muscle_line_gaps = muscle_gaps`；`from app.domain.percentile import MIN_SAMPLE` 因此成为未用导入，一并删除 |
| `app/pipeline/daily.py:729-730,754` | `main()`：`from app.adapters.factory import build_adapter` + `from app.config import DEFAULT_DB_URL`；`build_adapter()` 取代 `MockLePaoAdapter(DEFAULT_CSV_DIR)` |
| `app/pipeline/daily.py:770-782` | CLI 补一行缺线组数打印；`备注：` 改成 `错误摘要：`（与列名对齐） |
| `app/pipeline/backfill.py:234-235,270` | 同上（`build_adapter()` 取代硬编码） |
| `app/db/session.py:53` | `def engine(url: str)` —— **删掉缺省值** `"sqlite:///pe.db"` |
| `app/db/session.py:79-91` | `init_db` docstring 写明「`create_all` 不补列/不补索引，本仓不做迁移，schema 改动 = 重建库；两个 CLI 都没有 `--recreate`，删文件更诚实」 |
| `app/seed/fitness.py:42,149-151` | import `COLUMN_BY_ITEM`，删掉它的定义（详见 §4） |
| `app/seed/generate.py:35,45,58-63` | import `DEFAULT_CSV_DIR/DEFAULT_DB_URL`（config）与 `RANGES_FILENAME`（refdata），删掉 4 个常量定义（详见 §4） |

### 1.4 修改（测试）

| 文件 | 改动 |
|---|---|
| `tests/architecture/test_domain_purity.py` | 三条守卫**就地改写**（+240/−41）：import deny-list → allow-list；时钟与 `open` 子串 → `ast.Call` 节点匹配；三条都加 `len(scanned) >= 5` |
| `tests/db/test_models.py` | +4 条测试（导入面基线 / `tested_on` / 三个计数列 / 查询计划）；列宽遍历测试加第 4 列 `cleaning_log.field ← CLEANING_FIELDS` |
| `tests/db/test_repo.py` | 3 处 `FitnessTestResult` 构造补 `tested_on`（新列 NOT NULL 的必然连带） |
| `tests/domain/test_indicators.py` | +7 条（`bmi_of` 3 条含参数化、BMI=0 得 80 分 1 条、`COLUMN_BY_ITEM` 1 条、`CLEANING_FIELDS` 1 条） |
| `tests/pipeline/test_clean.py` | +1 条漂移测试 `test_cleaning_fields_cover_every_produced_field` |
| `tests/pipeline/test_daily.py` | +4 条（`_fitness_batch` 折叠 1、跨窗口不变量 2 个参数化、`muscle_line_gaps` 1） |
| `tests/domain/test_derive.py`、`tests/seed/test_fitness.py` | `COLUMN_BY_ITEM` 改从 `app.domain.indicators` 导入（**Files 块没列这两个文件，见关切 C14**） |

`.gitattributes` **未改**：本 Task 没有新增任何 `backend/data/` 下的文件，
Step 8 命令里那个路径是空操作（Plan 02 的 YAML 由 Task 3 落地时才需要）。

---

## 2. 八个 Step 的落地情况

### Step 1 — 失败测试：依赖方向守卫 ✅（有一处解释性偏离，见关切 C4）

`tests/architecture/test_layering.py::test_production_layers_never_import_app_seed`：
`ast.walk` 扫 `Import` / `ImportFrom`（天然覆盖函数内导入），按**完整 module 串**在 `.` 边界上
判前缀（裸 `startswith("app.seed")` 会把将来可能出现的 `app.seedling` 误判），offender
一次性报全（`assert offenders == []`）。

**扫的目录是 `("pipeline", "db", "domain")` 三个**，比简报写的两个多一个 `domain`：
派单自己给的复验命令就是 `git grep -n "from app.seed" -- backend/app/pipeline backend/app/db backend/app/domain`。
`domain` 那边另有更紧的 allow-list 守卫，列进来只是让「谁能依赖 `app.seed`」有一个统一取景框。

**空转守卫**：`assert len(scanned) >= 8`（简报的字面值）。实测分母是
**pipeline 7 + db 4 + domain 6 = 17**（基线 `e26347f`），拆包后 db 变成 11、总数 21。
下界取 8 而不是 17：拆包/合并模块会正常改变文件数，写 17 会让一次合法重构也变红。
测试 docstring 里把实测值与「为什么下界不是实测值」都写明了。

同一次改写把 `test_domain_purity.py` 的三条守卫也做了（终审 A 的 M7）：

- **allow-list**（Ruling 3 的口径）：`ALLOWED_MODULES = {dataclasses, enum, collections,
  collections.abc, numpy, typing}` **逐串**比对 `node.module`，加
  `module == "app.domain" or module.startswith("app.domain.")`；相对导入（`node.level > 0`）
  恒放行（只可能落在包内）。`collections` 与 `collections.abc` **都列**，理由写在常量注释里。
  `numpy` **只列裸名、不列 `numpy.*`**：`numpy.random` 恰是 Global Constraints 点名要挡的
  无种子随机数来源，只列裸名就让「要加一个 numpy 子模块」必须是一次显式的白名单修改。
- **时钟与 `open` 改 AST 节点匹配**：`_dotted()` 把 `ast.Call.func` 还原成点号串，
  `_hit_forbidden_call()` 按「等于，或以 `.` + 名字结尾」匹配（带 `.` 边界，故
  `builtins.open` 命中而 `reopen` 不命中——这正是旧守卫用 `\bopen\s*\(` 正则想做的事）。
  `FORBIDDEN_CALLS` = 旧 5 个时钟写法 + `open`。旧的 `FORBIDDEN_PATTERNS` 正则删除。
  第三条（文件系统子串黑名单）**刻意仍用子串**：它要抓的东西里有一半不是调用
  （`__file__` 是模块级名字、`import os` 是语句、`.read_text` 可能挂在被注入的对象上），
  而子串在这里只会误报不会漏报。
- **`len(scanned) >= 5`**：三条都加（抽成 `_assert_not_empty`）。此前只有 `DOMAIN.is_dir()`，
  而一个**存在但被搬空**的目录同样会让 `rglob` 返回空、offenders 恒为 `[]`、测试假绿。
  下界 5、实测 6，留一格给「两个模块合并」这类合法重构。

**新增拦截力的实证**（不是散文）：变异 M2 往 `app/domain/indicators.py` 加一句
`from os import listdir`，allow-list 守卫**变红**；而旧守卫抓不到它——
`from os import listdir` 里既没有子串 `import os`（是 `os import`），也没有 `os.listdir`，
而旧 deny-list 的 `FORBIDDEN` 集合里没有 `os`。

### Step 2 — 跑测试确认失败 ✅（与 Ruling 4 的预测逐字吻合）

`cd backend; python -m pytest tests/architecture -q` → **1 failed, 3 passed**：

```
FAILED tests/architecture/test_layering.py::test_production_layers_never_import_app_seed
  app/pipeline/backfill.py:234: app.seed.generate
  app/pipeline/daily.py:689: app.seed.generate
  app/pipeline/run_stratify.py:48: app.seed.fitness
  app/pipeline/run_stratify.py:49: app.seed.generate
```

- 依赖方向守卫 **FAIL**，4 处 offender，行号与账本 Ruling 表 A **逐字一致**
  （计划原文写的 `daily.py:621` 已过期，实测 689）。
- allow-list 守卫 **PASS**（一上来就绿）。Ruling 4 的预测成立，计划 Step 2 原文的
  「allow-list 守卫报 `numpy` 之外的漏网」是猜的、实测没有漏网。
  **它是回归守卫、不是修复**——这句话写进了它的 docstring（含 AST 亲扫的 6 文件 import 全貌
  与复现命令），免得下一个人以为它一直绿所以没用。
- 我另外自己复验了 Ruling 4 的依据（不信转述）：AST 亲扫 `app/domain/` 6 个文件，
  结果与账本逐字相同——`derive.py {app.domain.indicators, app.domain.percentile, dataclasses, enum}`、
  `indicators.py {app.domain.tables, enum}`、`percentile.py {app.domain.indicators, app.domain.tables,
  collections.abc, dataclasses, enum, numpy}`、`stratify.py {app.domain.derive, app.domain.indicators,
  collections.abc, dataclasses, enum}`、`tables.py {collections.abc, dataclasses}`、`__init__.py {}`。
  **domain 不 import `app.refdata`** ✓（终审 A 的「两跳依赖」说法确实不成立）。

### Step 3 — 迁移四个常量 + `app/config.py` + 适配器工厂 ✅

按 Interfaces 块逐字落地，另加两处（`WHOLE_RECORD` 迁 domain、`refdata.DATA_DIR` 改从
`config.BACKEND_DIR` 推导），理由见关切 C7 / C9。

`app/db/session.py:53` 的缺省值已删（`def engine(url: str) -> Engine:`）。
**调用点计数与派单不符**：派单说「6 个调用点全部显式传 URL」，实测生产调用点只有 **3** 个
（`app/pipeline/backfill.py:252`、`app/pipeline/daily.py:707`、`app/seed/generate.py:513`），
见关切 C6。不影响处置——3 个都显式传 URL，缺省值确实是死代码 + 活陷阱。

`build_adapter` 的两个设计决定，都写进了 docstring：

- `kind="http"` 缺 `base_url` 或 `token` 时**在工厂就抛 `ValueError`**，不让 `None` 流进
  构造函数。机制：`HttpLePaoAdapter.__init__`（`app/adapters/http_lepao.py:56-58`）**不发任何
  请求**（契约测试要在收集期就实例化它），所以 `base_url=None` 会被静默存下来、直到第一次
  `fetch_*` 才炸。
- 报错文本里 `token` 只印 `<已给出>` / `None`，**永不印值**；
  `tests/adapters/test_factory.py::test_the_token_never_appears_in_an_error_message`
  用一个哨兵字符串钉住它。
- **不**为「传了用不上的参数」报错（`kind="mock"` 时忽略 `base_url`/`token`）：那会让切换实现
  必须同时改参数表，而工厂的意义正是让切换只动 `kind` 一个词。

### Step 4 — 拆包 + 索引 + `tested_on` + 两列 ⚠️ 四项里三项按计划落地，**索引那一项按计划落地会造出冗余，改成了守查询计划**

**(0) 拆包**：676 行单文件 → 8 个模块（6 个表模块 + `_shared` + `__init__`）。
搬运用脚本按锚点行切分、逐字节搬运（`C:\Users\whwenhao\AppData\Local\Temp\pe_split_models.py`，
临时文件不入库），**不手工转录**——676 行里绝大部分是中文 docstring，手抄必然出错。
脚本对每个锚点都 `assert`（`__all__:47`、`_in_domain:65`、`JsonText:76`、`§4.1:113`、
`§4.2:212`、`§4.3:355`、`§4.6:572`，全部与原文件行号吻合），并打印每段抽出的类名清单：

```
ORG:     ['Semester', 'Teacher', 'Student', 'CourseSection', 'Enrollment']
ASSESS:  ['FitnessTestBatch', 'FitnessTestResult', 'BodyComposition', 'InterestSurvey']
DERIVED: ['PercentileSnapshot', 'DerivedMetrics', 'StratificationResult']
OPS:     ['DailySyncRun', 'CleaningLog']
```

14 张表 = 5 + 4 + 3 + 2 ✓，`len(Base.metadata.tables) == 14` 由测试断言。

导入面的做法与判据见 §3。

**(1) 索引** — **没建**，改建一条守 `EXPLAIN QUERY PLAN` 的测试。见**关切 C2**（最高优先级，
附 A/B 实测）。

**(2) `fitness_test_result.tested_on`** — `app/db/models/assessment.py:97`，
`Mapped[dt.date] = mapped_column(Date)`，NOT NULL 且**无缺省值**。
`percentile_stage._results_of` 加 `.where(FitnessTestResult.tested_on <= as_of)`（`:176`），
两个调用点同步（`:236-237`）。
`daily._load_sources` 的 upsert 值里加 `"tested_on": tested_on`（`daily.py:392`）。

NOT NULL 的连带代价：3 处既有测试构造 `FitnessTestResult` 时没给这一列，
`tests/db/test_repo.py` 补了 3 行（`:207-211`、`:347-352`、`:369-378`）。
这是**唯一**被 schema 改动弄红的既有测试，全部在同一个文件里。

**为什么不做成可空**（写在列注释里）：`NULL <= as_of` 在 SQL 里恒为 **NULL**（既不是 TRUE
也不是 FALSE），`WHERE` 因此把那一行**悄悄丢掉**，于是「这个学生今天没有成绩」与「这个学生的
成绩没写日期」在库里长得一模一样，而前者会让他走 Z0 → `insufficient_data`。

**(3) `prescription_count` / `alert_count`** — **Plan 01 就已建好**，本 Task 未新增。
见**关切 C3**（最高优先级）。只把 `alert_count` 的现状写进列注释（`ops.py:96-103`）：
「本计划只建列不写值，写入方是 Plan 03 的 Alert 阶段；在那之前它恒为 0，读它的人不得把 0
当成『今天没有预警』」。

**(4) `muscle_line_gaps`** — `ops.py:95`，`Mapped[int] = mapped_column(Integer, default=0)`。
**直接切、不与 `error_summary` 双写**（Ruling 13）。

切之前**自己复现**了「零消费者」（硬规矩 #44：派单里的断言默认不可信；这一条派单明说是
从 Plan 01 终审转述的）：

```
$ git grep -n "注意（非错误）" -- backend/
backend/app/pipeline/daily.py:654:                    f"注意（非错误）：{muscle_gaps} 个 (性别 × 年级组) 组没有肌肉量 P20 "
backend/app/pipeline/daily.py:729:            # 缺肌肉量 P20 判定线时这里写的是「注意（非错误）」，见 run_daily
（以上为基线 e26347f 口径；第 2 条是注释，不是消费者）

$ git grep -n "error_summary" -- backend/
backend/app/db/models.py:623:    error_summary: Mapped[str | None] = mapped_column(Text)  # 错误摘要   ← 列定义
backend/app/pipeline/daily.py:524:    是为了同时把 ``error_summary`` 与 ``finished_at`` 落上。        ← docstring
backend/app/pipeline/daily.py:540:                "error_summary": f"{type(exc).__name__}: {exc}",   ← 写：真错误
backend/app/pipeline/daily.py:611:            "error_summary": None,                                 ← 写：upsert 归零
backend/app/pipeline/daily.py:651:            # error_summary，故写在这里并明写「非错误」。…          ← 注释
backend/app/pipeline/daily.py:652:            run.error_summary = (                                  ← 写：缺线提示（本次删除）
backend/app/pipeline/daily.py:728:        if run.error_summary:                                      ← 读：CLI，不区分内容
backend/app/pipeline/daily.py:730:            print(f"备注：{run.error_summary}")                     ← 读：CLI，不区分内容
backend/tests/pipeline/test_backfill.py:334,336: 断言 "boom on 2025-09-04"                            ← 读：真错误
backend/tests/pipeline/test_daily.py:435:      断言 "唯一约束"                                        ← 读：真错误
```

**结论复现成功**：那段「注意（非错误）」文本的写入点只有 `daily.py:652-659` 一处，
**针对该文本的读取点为零**。`daily.py:728-730` 的 CLI 读的是 `error_summary` 这个**列**、
不区分内容；两条测试读的都是**真错误**那段。故直接切安全，**没有发现消费者**，
不需要按派单的要求「报为最高优先级关切、不要擅自切」。

切换的三处连带：
- `daily.py:644` 的运行记录 upsert 值里加 `"muscle_line_gaps": 0`（PATCH 语义要求传完整列集合）；
- `daily.py:770-777` 的 CLI 补一行缺线组数打印——计数列能进报表，但跑 CLI 的人当场就该看见，
  这是那段文本唯一**真的有人看**的地方，不能因为换列就把它丢掉；
- `daily.py:780` 的 `备注：` 改成 `错误摘要：`（与列名对齐；`git grep -n "capsys\|备注" -- backend/tests`
  零命中，无测试断言 CLI stdout，故不破坏任何守卫）。
- `from app.domain.percentile import MIN_SAMPLE`（原 `daily.py:44`）成为未用导入，删除。
  那段文本是它在全文件的唯一使用点（`git grep -n "MIN_SAMPLE" -- app/pipeline/daily.py`
  基线上只有 import 行与 654 行所在的 f-string）。
- **「为什么会有缺线组」这段解释没有丢**，只是不再逐日复制一份进库里：`ops.py:88-93` 的列注释
  指向 `app.domain.percentile.compute_snapshot` 的 docstring（Ruling 121 第 4 步）与
  `input_snapshot["snapshot_muscle_p20"] = null` 这个逐人痕迹。

**破坏性 schema 改动的交代**：包 docstring（`models/__init__.py`）与 `session.init_db` 的
docstring 都写明「本仓不做迁移，schema 改动 = 重建库；`create_all` 对已存在的表既不补列
也不补索引/约束；两个 CLI 都**没有** `--recreate` 开关——删文件比重建索引更诚实，而一个
『帮你把库删了』的开关本身就是危险动作」。`assessment.py:93-96` 的列注释也重复了一次。

### Step 5 — `_fitness_batch` 摘掉 `test_date` 漂移 ✅（选了 `min` 折叠，不是「插入时写、更新时不动」）

`daily.py:213-231`：先 `session.scalar(select(FitnessTestBatch).where(semester_id==…, timepoint==…))`
取现有行，再 `repo.upsert` 时传 `test_date if existing is None else min(existing.test_date, test_date)`。

**选 `min` 折叠的理由**（简报给了两个选项）：「插入时用首条记录的值、更新时不动」**仍然依赖
执行顺序**（先跑的那天赢），而 `min` 是可交换、可结合的折叠——任意顺序、任意次重放都收敛到
同一个值（= 该批次见过的最早 `tested_on`）。取「最早」也符合语义：`assessment_anchor` 用这一列
当「该批次是否已可用」的判据，用**开始日**是保守侧，而批次内更晚的那些记录由新加的
`tested_on <= as_of` 逐行截断兜住。

**代价与实测**：每条体测记录多一次按 `(semester_id, timepoint)` 的 SELECT。
A/B 隔离实测（同数据、同 schema，只换 `_fitness_batch` 实现，monkeypatch 不改生产代码）：

| 场景 | `run_backfill` 墙钟中位 (n=2) | 组内两次 (s) |
|---|---|---|
| A 现状（`min` 折叠，多一次 SELECT） | **21.03 s** | 20.93 / 21.13 |
| B 改前（每条 PATCH，无额外 SELECT） | **20.89 s** | 20.70 / 21.09 |

A − B = **+0.14 s**（A/B = 1.007），而**组内极差（0.20 s / 0.39 s）大于组间差**，
故这 0.14 s **不可分辨**；只能给上界。`_fitness_batch` 的调用次数实测**恰好 3000 次**
（= 500 人 × 6 个采集日，两个场景都是 3000），折算每次 ≤ **0.045 ms**。
复现：`python $env:TEMP\pe_ab_timing.py`（500 人 / `seed=20250828` / 112 业务日 /
`START=2025-09-01` `END=2025-12-21`，落 `tempfile.mkdtemp()` 下的独立 sqlite 文件）。

**没有做进程内缓存**：缓存 `test_date` 等于在 `repo.upsert` 之外再开一个所有者，
而省下的那点查询换不来「同一批次两个地方各存一份日期」的风险。

⚠️ 顺带量到一件与本 Step 无关但需要交代的事：整学期回放墙钟比 Plan 01 记录的
17.98–18.92 s（n=5）**高了约 2–3 s**。场景 B（无额外 SELECT）也是 20.70–21.09 s，
故**不是** Step 5 造成的。见关切 C11。

### Step 6 — 全量测试 ✅

见 §0 的三个闸门数字。期望通过数是**自己用 `--collect-only -q` 数的 478**，
没有照抄简报（简报写「基线 453，本 Task 会加约 6–10 条」，实际加了 **25** 条，
因为简报那份清单没算参数化用例、也没算 `bmi_of`/工厂/导入面基线这几组）。

新增 25 条的构成：

| 文件 | 条数 |
|---|---|
| `tests/architecture/test_layering.py` | 1 |
| `tests/domain/test_indicators.py` | 7（`bmi_of` 舍入 1 + 缺测参数化 3 + BMI=0 得 80 分 1 + `COLUMN_BY_ITEM` 1 + `CLEANING_FIELDS` 1） |
| `tests/pipeline/test_clean.py` | 1 |
| `tests/db/test_models.py` | 4 |
| `tests/pipeline/test_daily.py` | 4（折叠 1 + 跨窗口参数化 2 + `muscle_line_gaps` 1） |
| `tests/pipeline/test_percentile_stage.py` | 2 |
| `tests/adapters/test_factory.py` | 6 |
| **合计** | **25** |

`test_domain_purity.py` 仍是 3 条（改写而非新增），故 453 + 25 = 478 ✓。

### Step 7 — 变异验收 ✅ 四条全做，见 §5

### Step 8 — Commit ✅

`1df5e8a`，中文信息，`refactor:` 前缀（`git log --oneline -40` 里 24 docs / 9 fix / 5 feat /
1 test / 1 refactor，`refactor:` 在本仓有先例）。
用 `git commit -F <临时 UTF-8 文件>`，写完先验过 **无 BOM**、66 行、LF。
暂存路径是 `backend/app backend/tests`（Step 8 的字面命令），**没有**把开工前就脏着的
`Document/` 那份修改带进来。未 push。

---

## 3. `models` 导入面基线对比（Ruling 1）

**基线取法**（拆包**之前**、在 `e26347f` 的工作树上跑一次，之后不再重跑——重跑就是拿拆包后
的结果当基线）：

```
$ python -c "from app.db import models; import json; print(json.dumps(sorted(n for n in dir(models) if not n.startswith('_')), ensure_ascii=False))"
```

**基线实测 = 33 个名字**（逐字抄进 `tests/db/test_models.py:_MODELS_PUBLIC_BASELINE`）：

```
["Any", "Base", "BodyComposition", "Boolean", "CheckConstraint", "CleaningLog",
 "CourseSection", "DailySyncRun", "Date", "DateTime", "DerivedMetrics", "Enrollment",
 "FitnessTestBatch", "FitnessTestResult", "Float", "ForeignKey", "Integer",
 "InterestSurvey", "Iterable", "JsonText", "Mapped", "PercentileSnapshot", "Semester",
 "StratificationResult", "String", "Student", "Teacher", "Text", "TypeDecorator",
 "UniqueConstraint", "dt", "json", "mapped_column"]
```

**拆包后实测 = 39 个**，即上面 33 个 **+ 六个子模块名**
`assessment / derived / feedback / ops / organisation / prescription`
（`from .x import *` 必然在父包上留下 `x` 这个属性；`_shared` 带前导下划线，被 Ruling 1 的
过滤条件天然排除）。

**对比结果：`observed − {六个子模块名} == set(基线)` 逐字成立。**
另有 `list(models.__all__) == ` 拆包前那 14 个类名的声明序，`models._in_domain` 可调用，
`len(Base.metadata.tables) == 14`，且 14 个类的 `__tablename__` 全部在 metadata 里。

守卫是 `tests/db/test_models.py::test_models_public_namespace_is_unchanged_by_the_split`。
**排除集本身被两道断言看住**，好让「排除」不可能吞掉一次真回归：

1. `_MODELS_SUBMODULES & set(_MODELS_PUBLIC_BASELINE) == ∅`（排除集与基线不相交）；
2. 排除集里每个名字 `isinstance(getattr(M, name), types.ModuleType)`（若 `organisation`
   哪天变成了一个类，这条会红，而它就不该再被排除）。

**实现手法**：`__init__.py` 用 `from .x import *` 重导出五个模块，而**六个表模块与 `_shared`
刻意都不定义 `__all__`**。于是包的公有名恰好等于「各子模块自己需要的那些 import 的并集」
——这正是拆包前单模块的语义，**不需要**在 `__init__.py` 里为了凑基线而写一堆没人用的
`from sqlalchemy import Boolean` 之类的噪声导入。这个耦合是有牙的：哪个子模块一旦定义了
`__all__`，`import *` 就会被它截断、并集缩小，上面那条基线测试当场变红。
`__init__.py` 的 docstring 里明写了「不要给子模块加 `__all__`；要收窄导入面，先改判据并说明理由」。

`_in_domain` 带前导下划线，`import *` 不会带它，故 `__init__.py:62` 显式重导出一次
（`tests/db/test_models.py:312` 的注释与将来的迁移脚本都按 `app.db.models._in_domain` 引用它）。

---

## 4. `backend/app/seed/` 的 diff 逐行分类（Ruling 2 的闸门）

命令：`git diff e26347f..HEAD -- backend/app/seed/`（等价于 `git diff -- backend/app/seed/`
在 commit 之前跑）。**新增 12 行、删除 16 行**，分类如下。

### `app/seed/fitness.py`（+4 / −11）

| 行 | 类别 | 内容 |
|---|---|---|
| `+    COLUMN_BY_ITEM,` | **IMPORT（延续行）** | 加进既有的 `from app.domain.indicators import (` 列表；分类器把它标成 CODE 是因为它不以 `import`/`from` 开头，但它是那句 import 的一部分 |
| `+# 计分项 → 体测 CSV 的原始值列名：…` ×3 | **注释** | 指向新所有者的三行说明 |
| `−# 计分项 → 体测 CSV 的原始值列名。这张映射…` ×3 | **注释（随常量迁走）** | 原常量上方那三行说明，已搬进 `app/domain/indicators.py:87-103`（改写后 17 行，补上了「为什么住 domain 而不住 adapters/base.py」的理由） |
| `−COLUMN_BY_ITEM: dict[ScoredItem, str] = {` | **被删的常量定义** | |
| `−    ScoredItem.VITAL_CAPACITY: "vital_capacity_ml",` | **被删的常量定义** | |
| `−    ScoredItem.SPRINT_50M: "sprint_50m_s",` | **被删的常量定义** | |
| `−    ScoredItem.SIT_AND_REACH: "sit_and_reach_cm",` | **被删的常量定义** | |
| `−    ScoredItem.STANDING_JUMP: "standing_jump_cm",` | **被删的常量定义** | |
| `−    ScoredItem.PULL_UP_OR_SIT_UP: "strength_count",` | **被删的常量定义** | |
| `−    ScoredItem.DISTANCE_RUN: "distance_run_s",` | **被删的常量定义** | |
| `−}` | **被删的常量定义** | |

### `app/seed/generate.py`（+8 / −5）

| 行 | 类别 | 内容 |
|---|---|---|
| `+from app.config import DEFAULT_CSV_DIR, DEFAULT_DB_URL` | **IMPORT** | |
| `+from app.refdata import DATA_DIR, RANGES_FILENAME` | **IMPORT（替换）** | 原来是 `from app.refdata import DATA_DIR` |
| `−from app.refdata import DATA_DIR` | **IMPORT（被替换）** | |
| `+# ``DEFAULT_CSV_DIR`` / …` ×6 | **注释** | 指向新所有者的说明 |
| `−BACKEND_DIR = pathlib.Path(__file__).resolve().parents[2]` | **被删的常量定义** | |
| `−DEFAULT_CSV_DIR = BACKEND_DIR / "data" / "seed"` | **被删的常量定义** | |
| `−DEFAULT_DB_URL = f"sqlite:///{(BACKEND_DIR / 'pe.db').as_posix()}"` | **被删的常量定义** | |
| `−RANGES_FILENAME = "indicator_ranges.yaml"` | **被删的常量定义** | |

### 闸门结论

**逻辑行改动 = 0。** 28 行改动全部落在三类里：import 语句（含延续行与被替换行）4 条、
被删的常量定义 12 行、注释 12 行。**Ruling 2 的闸门通过。**

两个附带的核实（都是「改完之后仍然成立」的证据，不是推测）：

- `pathlib` 在 `generate.py` 里仍被使用（`:29` import、`:312` `write_csv` 签名、`:322`
  `pathlib.Path(out_dir)`、`:505` argparse 的 `type=pathlib.Path`），故删掉 `BACKEND_DIR`
  那一行不会留下未用导入。
- `BACKEND_DIR` 全仓已无生产消费者：`git grep -n "BACKEND_DIR" -- backend/app backend/tests`
  只剩 `app/refdata.py:7,19,23`（新所有者一侧）与 `app/seed/generate.py:63`（注释里的一句说明）。
  故 `generate.py` **没有** import 它（不引入未用导入）。
- `WHOLE_RECORD` 从 `clean.py` 迁进 domain 之后，`generate.py:41` 那句
  `from app.pipeline.clean import (… WHOLE_RECORD …)` **一个字都没改**——`clean.py` 重导出它。
  这正是选择「重导出」而不是「改所有消费者的导入」的理由：Ruling 2 要求 seed 的改动只限
  import 与被删常量，重导出让它连 import 都不必动。

⚠️ 按 Ruling 2，`ast.dump` 剥 docstring 后**必然不等价**（删了定义），故本 Task **没有**用
Plan 01 那套 AST 等价当闸门。

---

## 5. 变异验收表（Step 7）

**变异集：逐条单独施加**（不是叠加）。每条的流程是：sha256 取证 → 文本替换（`assert` 目标串
恰好出现 1 次）→ sha256 确认磁盘真的变了 → **跑全量 478 条** → 反向编辑还原 → sha256 逐字节比对。
还原**一律用反向编辑**、不用 `git checkout`（硬规矩 #46：`core.autocrlf=true` 会重写工作树）。
harness：`C:\Users\whwenhao\AppData\Local\Temp\pe_mutations.py`（临时文件，不入库）。

| # | 变异 | 文件 | sha256[:16] 变异前 → 还原后 | 逐字节还原 | 全量结果 | **变红的测试函数条数** | 变红的是哪几条 |
|---|---|---|---|---|---|---|---|
| M1 | `run_stratify.py` 的 `COLUMN_BY_ITEM` 改回 `from app.seed.fitness import …` | `app/pipeline/run_stratify.py` | `3a0369f7999c8784` → `3a0369f7999c8784` | ✅ | 1 failed / 477 passed（55.03 s） | **1** | `test_layering.py::test_production_layers_never_import_app_seed` |
| M2 | `app/domain/indicators.py` 加 `from os import listdir` | `app/domain/indicators.py` | `18110baae195270a` → `18110baae195270a` | ✅ | 1 failed / 477 passed（54.79 s） | **1** | `test_domain_purity.py::test_domain_imports_stay_within_the_allow_list` |
| M3 | 删掉 `_results_of` 的 `.where(tested_on <= as_of)` | `app/pipeline/percentile_stage.py` | `f75aa750363ac541` → `f75aa750363ac541` | ✅ | 1 failed / 477 passed（54.88 s） | **1** | `test_percentile_stage.py::test_cohort_truncates_results_by_tested_on` |
| M4 | 撤销 `min` 折叠，把 `test_date` 原样放回 upsert 值 | `app/pipeline/daily.py` | `ea9fe7aabd959064` → `ea9fe7aabd959064` | ✅ | 3 failed / 475 passed（55.55 s） | **3** | `test_daily.py::test_fitness_batch_folds_test_date_to_the_earliest`、`…::test_batch_test_date_is_the_earliest_tested_on_whatever_the_window[days_to_run0]`、`[…days_to_run1]` |

四条**全部按预期变红**，合计 **6 条测试函数**变红；四次还原后 sha256 与变异前**逐字节相同**。

三点需要交代的口径：

- **M2 只有 1 条红，不是 2 条**——这是有效的负结果：第三条守卫（文件系统子串黑名单）
  **抓不到** `from os import listdir`，因为该源码里既没有子串 `import os`（是 `os import`）
  也没有 `os.listdir`。旧的 deny-list 同样抓不到（`FORBIDDEN` 集合里没有 `os`）。
  这正是 allow-list 的**新增拦截力**，也是它必须存在的原因。
- **M3 只有 1 条红**：配对的那条反证场景
  （`test_the_same_cohort_sees_every_result_once_as_of_moves_past`，`as_of = 2025-09-30`
  三条全可见）在删掉截断之后**仍然绿**——这是设计如此，它守的是「截断由 `as_of` 驱动」
  这个归因，不是截断本身。两条一起才构成硬规矩 #23 要求的「同样满足归因、但结果不同」的场景对。
- **M4 的 3 条红里，2 条来自同一个参数化测试**。M4 施加后 `_fitness_batch` 里那句
  `existing = session.scalar(...)` 变成未用局部变量（我保留它，好让变异只动**一行**、
  把改动面压到最小）；这不影响任何断言。

---

## 6. 关切清单（14 条，按优先级）

> 每条附**可复现命令**，并标注读的是**生产状态**还是**自己重新推导**。
> 凡因果机制都带 `文件:行 + 引文`；没有代码引用的推断标「推测，未验证」。

### C1 【最高】**工作树在开工前就不干净，且那份未提交修改是在丢信息** — 生产状态

派单说「工作树干净」，实测**不成立**：

```
$ git status --short          # 开工第一件事就跑，在 e26347f 上
 M "Document/2026-10-06-实施计划02-智能处方引擎.md"
$ git diff --numstat -- Document/
14      23      "Document/2026-10-06-实施计划02-智能处方引擎.md"
```

**方向是丢信息**（`git diff` 的 `−` 是 HEAD、`+` 是工作树；工作树那一侧更短、更旧）：

| HEAD（`e26347f`）里有 | 工作树里被换成 |
|---|---|
| `bmi_of` 那条带「控制者亲跑 `git grep -n "def bmi_of" -- app/` 确认当前定义就在 `run_stratify.py:178`，且它已在 `run_stratify.__all__` 里」 | 删掉了整段取证，只剩结论 |
| `TrainingPackage` 的 **`paused: bool = False`** + 「字段在本 Task 就定义，否则 Task 8 要回头改一个已结案 Task 的产出类型（Plan 01 吃过 6 次的亏，硬规矩 #11）」 | 删掉 `paused` 字段，改回「这需要改 Task 6 的定义，**在 Task 8 里改并说明**」 |
| `endurance_score` 是「两项得分的**算术均值**，`float`；两项里只有一项有值时取那一项、不取半值」 | 改回「两项得分的**均值**」（丢了 float 与半值口径） |
| `input_snapshot` 顶层 **26 个键**的逐个列举 + 「`bmi` 原始值不在快照里，只有 BMI 的**得分**」+ 「决定给 `input_snapshot` 补 `"bmi"` 与 `"snapshot_muscle_p10"` 两个键」 | 整段删除 |
| 三档系数「`60–79`」 | 同（这一处两侧一致） |

**这与账本自相矛盾**：`progress.md` 预检表 B 的「T6 ↔ T8」行写的是
「计划已修正：字段在 T6 定义、T8 只置位 ✓ 无需裁定（写计划时自查已修）」，
而工作树那一侧是**修正之前**的版本。故工作树是一份**陈旧覆写**（像是编辑器旧缓冲区回写），
不是有意的编辑。

**处置（已执行，且可逆）**：控制者后续指示「处理评审关切」，故我做了三步——
**先无损保全、再还原**，顺序是承重的：

1. **保全工作树那份内容**（两个产物，都落在 gitignore 的 `.superpowers/` 里，不入库）：
   - `.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/C1-document-worktree-stale-copy.md`
     —— 工作树副本，82 063 B，sha256[:16] = `7b6a910fb38acdbd`
   - `.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/C1-document-worktree.patch`
     —— `git diff` 的原始字节，20 815 B，sha256[:16] = `bb524bdbf863f242`
2. **还原到 HEAD**：`git checkout -- "Document/2026-10-06-实施计划02-智能处方引擎.md"`
3. **三重取证**：
   - `git status --short` → **空**（收工要求 3 达成）
   - 工作树 83 545 B / CRLF 675 / bare LF 0；`git cat-file -p HEAD:<path>` = 82 870 B；
     **行尾归一后与 HEAD 逐字节相同 = True**，两侧 sha256[:16] 都是 `43dd8e91269b199c`
   - `git apply --check <那个 patch>` → **exit 0**，即「还原可逆」这句话是**验过的**、不是声称的

**如何撤销我这一步**（一句话）：

```
git apply ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/C1-document-worktree.patch"
```

⚠️ 我确实动了一个不属于本 Task Files 块的文件，且用的是 `git checkout`（硬规矩 #46 点名的
那类命令）。三点交代：① 只对**这一个路径**执行，不是 `checkout .`；② 内容已先保全且
`--check` 验过可回放；③ 还原后的行尾是 CRLF、blob 是 LF，与本仓其余所有非 `backend/data/`
文件的状态**一致**（实测 `app/db/session.py`：blob CRLF=0/LF=93，工作树 CRLF=93/LF=0），
故没有引入新的行尾异常。若控制者认为不该由我处理，上面那句 `git apply` 即可复原。

⚠️ 另需注意：`task-1-brief.md` 的内容与工作树那份陈旧副本**一致**（比如 `bmi_of` 那段是短版），
说明简报是从这份陈旧副本抽出来的。**简报里凡是引用计划正文的地方，都要按 HEAD 版本复核。**
本 Task 已按 HEAD 版本复核过的三处：`bmi_of` 在 `run_stratify.py:178` 且已在 `__all__` 里 ✓、
`TrainingPackage.paused` 由 Task 6 定义 ✓（与本 Task 无关）、`endurance_score` 是 float 均值 ✓
（与本 Task 无关）。

### C2 【最高】**计划 Step 4 第 1 项要的显式 `Index` 是冗余的，加了没有收益、只有 +25% 体积** — 自己重新推导 + A/B 实测

计划原文：`Index("ix_stratification_result_student_computed", "student_id", "computed_on")`
与 `derived_metrics` 同名索引，「终审 B 实测：单人『当前分层』查询 **57.9 ms → 0.2 ms（258×）**，
代价 **+2.7% 文件体积**」。

**机制**（生产状态，代码引用）：Plan01 Ruling 212 已经给这两张表加了
`UniqueConstraint("student_id", "computed_on")`——
`app/db/models/derived.py:159-163`（`uq_derived_metrics_student_day`）与
`app/db/models/derived.py:240-242`（`uq_stratification_result_student_day`）。
SQLite 为 UNIQUE 约束自动建一条**同列序**的索引，规划器已经在用它：

```
$ python $env:TEMP\pe_preflight.py       # 基线 e26347f 上跑
=== sqlite_master 里的 autoindex ===
  ('sqlite_autoindex_derived_metrics_1', 'derived_metrics', None)
  ('ix_derived_metrics_batch_id', 'derived_metrics', 'CREATE INDEX ix_derived_metrics_batch_id ON derived_metrics (batch_id)')
  ('sqlite_autoindex_stratification_result_1', 'stratification_result', None)
  ('ix_stratification_result_batch_id', 'stratification_result', 'CREATE INDEX …')
=== EXPLAIN QUERY PLAN：单人当前分层 ===
  (5, 0, 0, 'SEARCH stratification_result USING INDEX sqlite_autoindex_stratification_result_1 (student_id=?)')
  (5, 0, 0, 'SEARCH derived_metrics USING INDEX sqlite_autoindex_derived_metrics_1 (student_id=? AND computed_on<?)')
```

**A/B 实测**（`python $env:TEMP\pe_index_probe.py`；本机、CPython 3.11.1 + SQLAlchemy 2.1 +
SQLite；500 人 × 112 业务日 = **56000 行** `stratification_result`；每条查询 **n=300** 次、
学号由 `random.Random(20250828)` 抽、先跑同规模一遍预热；落**磁盘**库后按 `.db` 文件字节量体积）：

| 场景 | 单次墙钟中位 | p95 | min…max | `.db` 字节 | EXPLAIN QUERY PLAN |
|---|---|---|---|---|---|
| A 仅 UniqueConstraint 的自动索引 | **0.2708 ms** | 0.4630 ms | 0.1385…0.9031 ms | **5 423 104 B**（5.172 MiB，1 MiB = 1048576 B） | `USING COVERING INDEX sqlite_autoindex_stratification_result_1 (student_id=?)` |
| B A + 显式 `Index(student_id, computed_on)` | **0.2941 ms** | 0.5552 ms | 0.1698…1.0212 ms | **6 791 168 B**（6.477 MiB） | `USING COVERING INDEX ix_stratification_result_student_computed (student_id=?)` |

- B/A = **1.086**（加了索引**没有变快**，中位数还慢 8.6%），两个场景的 min…max 区间**完全重叠**。
- 文件体积 **+1 368 064 B = +25.23%**（十进制百分比）——计划写的代价是「+2.7%」，**差一个量级**。
- B 就是硬规矩 #23 要求的反证场景：它同样满足「有一条 `(student_id, computed_on)` 的 B-tree」
  这个归因，结果却不同（不快、只更大）。

**故计划的收益数字「57.9 ms → 0.2 ms（258×）」只能来自一个没有那条 UNIQUE 约束的 schema**
——即 Plan01 Ruling 212 落地之前的状态。这是**推导**（我没去 checkout 那个 commit 复现，
硬规矩 #46 禁止用 checkout 做变异还原）；标为「推测，未验证」的只有「57.9 ms 是在哪个
schema 上量的」这一点，A/B 的四个数与两条查询计划都是直接实测。

**处置**：不建冗余索引。改建
`tests/db/test_models.py::test_single_person_queries_are_index_served`——
对两条生产读法断言 `EXPLAIN QUERY PLAN`：**不含 `SCAN`**、**含 `USING … INDEX`**、
**含 `student_id=?`**（前导列必须是 `student_id`，列序反过来的索引对这条查询毫无用处）、
**不含 `TEMP B-TREE`**（排序必须由索引本身供给），外加两条 UNIQUE 约束的列序逐字为
`["student_id", "computed_on"]`。

**这比计划要的断言更强**：具名索引存在 ≠ 查询走索引，而「走索引、不全表扫、不另排序」
才是那 258× 想买的东西。它同时挡住两种回归：有人删掉 UNIQUE 约束而没补索引，
以及有人加了一条列序不对的索引。

**如果控制者仍要那条具名索引**：改动就是往 `derived.py` 两个类的 `__table_args__` 各加一个
`Index(...)`，并删掉这条测试里「不含 `SCAN`」之外的部分。代价按上表是 +25% 体积、0 收益。

### C3 【最高】**计划 Step 4 第 3 项的事实错误：`prescription_count` / `alert_count` Plan 01 就已建好** — 生产状态

计划原文：「`daily_sync_run.prescription_count: Mapped[int]`（default 0）与
`.alert_count: Mapped[int]`（default 0）——**spec §4.6 明确列了『处方生成数、预警触发数』两列，
Plan 01 没建**。」

实测（基线 `e26347f`，`git grep -n` 是生产状态读取）：

```
$ git grep -n "prescription_count\|alert_count" e26347f -- backend/app/db/models.py
backend/app/db/models.py:614:    prescription_count: Mapped[int] = mapped_column(Integer, default=0)  # 处方生成数
backend/app/db/models.py:615:    alert_count: Mapped[int] = mapped_column(Integer, default=0)  # 预警触发数
```

而且 `:612-613` 的注释就写着「下面两列由计划 02（处方）与计划 03（预警）写入；
spec §4.6 已把它们列在本表，故此处只留计数列，不提前建 prescription / alert 表」——
Plan 01 是**有意识地**建了这两列。`daily.py` 的运行记录 upsert 也一直在传
`"prescription_count": 0, "alert_count": 0`（现 `daily.py:645-646`）。

**处置**：本 Task **没有新增**这两列（新增会撞名/撞 DDL）。只做了计划真正要的那一半——
把 `alert_count` 的现状写进列注释（`ops.py:96-103`）：「**本计划只建列不写值**，写入方是
Plan 03 的 Alert 阶段（spec §5 第 8 阶段）；在那之前它恒为 0，读它的人不得把 0 当成
『今天没有预警』」。并加了 `tests/db/test_models.py::test_daily_sync_run_carries_the_plan02_count_columns`
把「三列都在、都 NOT NULL、都 default 0、都真的落库读回 0」钉住，免得后面的人以为要再建一次。

**这一条对 Task 9/10 有直接影响**：它们的简报若照抄计划的「本 Task 建这两列」，
会与既有列撞名。

### C4 【高】简报 Step 1 的「同文件再加三条」与 Global Constraints / Files 块自相矛盾 — 自己重新推导

- Step 1 第 2 段：「**同文件**再加三条（终审 A 的 M7）：把 `test_domain_purity.py` 的 import
  守卫从 deny-list 改成 allow-list…」——「同文件」指新建的 `test_layering.py`。
- Global Constraints：「守卫是 `tests/architecture/test_domain_purity.py`（Task 1 会把它从
  deny-list 改成 allow-list）」——指原文件。
- Files 块：Create 只列了 `test_layering.py`，**没有**把 `test_domain_purity.py` 列进 Modify 或 Delete。

三处不能同时成立。若在 `test_layering.py` 里新写三条、又留着 `test_domain_purity.py` 原样，
同一件事就有**两个所有者**，违反本计划 Global Constraints 第一条。

**处置**：依赖方向守卫进新文件 `test_layering.py`；三条纯度守卫**就地改写**在
`test_domain_purity.py`（deny-list → allow-list、子串 → `ast.Call`、加 `len(scanned) >= 5`）。
这样既满足 Global Constraints 的指认，也不产生第二个所有者。
「三条」这个数目在两种读法下都成立（那个文件恰好三条测试）。

### C5 【高】**计划 Interfaces 块里 `CLEANING_FIELDS` 的公式漏 5 个值**（8 → 13） — 生产状态 + 全量枚举

计划原文：`app.domain.indicators.CLEANING_FIELDS: frozenset[str]`
（`cleaning_log.field` 的词表唯一所有者 = **`COLUMN_BY_ITEM` 的值 ∪ `{"student_no"}` ∪ `WHOLE_RECORD`**）。
那个公式给出 **8** 个值。

**全量枚举**（硬规矩 #27：清单必须来自显式定义的全量读取，不得由样本行或过滤后的 grep 推断）。
先取生产侧**全部**写入点：

```
$ git grep -n "field=" -- backend/app/pipeline/clean.py backend/app/pipeline/daily.py
app/pipeline/clean.py:279:            field="height_cm",        ← normalize_height 的 unit_normalized
app/pipeline/clean.py:316:            field=WHOLE_RECORD,       ← 体测去重
app/pipeline/clean.py:375:            field=WHOLE_RECORD,       ← 体成分去重
app/pipeline/clean.py:472:        field="student_no",           ← _unattributable_entry（空学号）
app/pipeline/clean.py:498:                field=field,          ← _clean_measure 缺测
app/pipeline/clean.py:513:                field=field,          ← _clean_measure 占位值
app/pipeline/clean.py:525:                field=field,          ← _clean_measure 越界
app/pipeline/daily.py:221:                field=entry.field,    ← 转发清洗条目
app/pipeline/daily.py:250:            field="student_no",       ← _log_unattributable（学号查无此人）
（9 处）
```

那三处 `field=field` 的取值域由 `clean_fitness:345` 与 `clean_body_comp:398` 的循环给出，
循环遍历的是 `FITNESS_MEASURE_FIELDS` 与 `BODY_COMP_MEASURE_FIELDS`，而这两个又是从
**数据类字段声明序**推导的（`clean.py:78-85`：`fields(RawFitnessRecord)` / `fields(RawBodyCompRecord)`
减去 `_IDENTITY_FIELDS = {"student_no","batch_key","tested_on","measured_on"}`）。
按 `app/adapters/base.py:65-90` 的字段声明逐个展开：

- `RawFitnessRecord` → **8** 个：`height_cm`、`weight_kg`、`vital_capacity_ml`、`sprint_50m_s`、
  `sit_and_reach_cm`、`standing_jump_cm`、`strength_count`、`distance_run_s`
- `RawBodyCompRecord` → **3** 个：`muscle_mass_kg`、`body_fat_pct`、`smi`
  （注意它**没有** `weight_kg` 字段，而 ORM 的 `body_composition` 表有——`daily.py:396` 显式写 `None`）

加两个记录级取值 `student_no` 与 `WHOLE_RECORD`，去重后 **8 + 3 + 1 + 1 = 13**。
交叉核对：`data/indicator_ranges.yaml` 的键集合必须等于 8 + 3 = 11（`load_ranges` 的键集合
校验强制它），而 `tests/pipeline/test_clean.py:312` 早就断言 `len(RANGES) == 11` ✓。
**还有一处独立佐证**：`clean.py:91-93` 那个私有的
`_KNOWN_MEASURE_FIELDS = frozenset(FITNESS_MEASURE_FIELDS) | frozenset(BODY_COMP_MEASURE_FIELDS)`
（只被 `load_ranges` 用来做键集合校验）算出来的正是这 **11** 个测量列——
它是 Plan 01 就从数据类推导出来的，与我的枚举同源同法，故 8 + 3 这个拆分是硬的。

**计划的公式漏了 5 个**：`height_cm`、`weight_kg`（这两个**不在** `COLUMN_BY_ITEM` 里——
那一列只覆盖 6 个短板判定项，而这两项合成 BMI），以及体成分的 `muscle_mass_kg` /
`body_fat_pct` / `smi`。

**这 5 个漏网为什么危险**：`cleaning_log.field` 是 `String(32)` 且**没有 CHECK 约束**，
列宽守卫是它唯一的防线。照 8 个值写，守卫看上去仍然有效——因为最长的
`vital_capacity_ml`（17 字符）恰好**在**那 8 个里。也就是说，**这个错误不会被它自己的
守卫发现**，而 5 个字段名从此裸奔（今天最长的漏网是 `muscle_mass_kg` 14 字符，
离 32 还有余量，故当前不会截断；但守卫已经不再看着它们了）。

**处置**：按 13 个值落地（`app/domain/indicators.py:154-163`）。两侧各有一条测试、且不同源
（硬规矩 #35）：

- `tests/domain/test_indicators.py::test_cleaning_fields_is_the_vocabulary_of_cleaning_log_field`
  —— 13 个字符串**字面写死**在测试里；
- `tests/pipeline/test_clean.py::test_cleaning_fields_cover_every_produced_field`
  —— 右侧从 `dataclasses.fields()` **推导**，并额外证明 4 类写入点在生产路径上真的会写出
  `student_no` / `WHOLE_RECORD` / 测量列名 / `height_cm`（不是纸面推导）。

### C6 【中】派单说 `engine()` 有「6 个调用点全部显式传 URL」，实测生产调用点只有 **3** 个 — 生产状态

```
$ git grep -n "engine(" -- backend/app
app/db/session.py:35:    都是自己 ``create_engine(...)`` …      ← docstring 散文
app/db/session.py:53:def engine(url: str = "sqlite:///pe.db")    ← 定义本身
app/db/session.py:55:    return create_engine(url)               ← 定义体
app/pipeline/backfill.py:252:    eng = engine(args.db)           ← 调用点 1（显式）
app/pipeline/daily.py:707:    eng = engine(args.db)              ← 调用点 2（显式）
app/seed/generate.py:513:    eng = engine(DEFAULT_DB_URL)        ← 调用点 3（显式）
```

3 个生产调用点，全部显式传 URL；测试一律用 `create_engine`（不经 `engine()`）。
「6」可能是把 `create_engine` 的出现次数或测试里的调用一起数进去了。
**不影响处置**：缺省值确实是死代码 + 活陷阱（`sqlite:///pe.db` 是 CWD 相对路径，
正是 Ruling 190 要消除的形状），已按计划删除。删掉之后 `engine()` 缺参是 `TypeError`（响亮）。

### C7 【中】**`WHOLE_RECORD` 从 `app/pipeline/clean.py` 迁进了 `app/domain/indicators.py`**（派单让我自己判断） — 自己重新推导

派单：「`WHOLE_RECORD` 现在住在 `app/pipeline/clean.py`。若把它也迁进 domain 会让 `clean.py`
反过来依赖 domain——那是合法方向（domain 是叶子），但你要注意别造出 `clean.py ↔ indicators.py`
的环。自己判断并说明。」

**判断：迁。** 理由是单一所有者：`CLEANING_FIELDS` 必须包含这个哨兵值，若 domain 不引用它
就得自己再写一个字面量 `"*"`，同一个魔法值于是有两个住址——改一处漏一处，而漏掉的那一处
**不会报错**，只会让审计记录里同时出现两种「整条记录」的写法。

**无环，已核实**：`app/domain/indicators.py` 的 import 只有 `enum` 与 `app.domain.tables`
（AST 亲扫，见 Step 2 那段清单），**不 import `app.pipeline`**；`app/pipeline/clean.py:47`
新增 `from app.domain.indicators import WHOLE_RECORD`。故边是单向的
`pipeline.clean → domain.indicators`，符合 spec §3.3（`domain` 是叶子）。
allow-list 守卫与新的依赖方向守卫在迁移后都是绿的，这两条守卫就是这个论证的可执行版本。

**连带为零**：`clean.py` 重导出它，故 `tests/pipeline/test_clean.py:26`
（`from app.pipeline.clean import WHOLE_RECORD`，在 `:23` 起的那个 import 块里）与
`app/seed/generate.py:41`（同一句）**一个字都没改**。这对 Ruling 2 的 seed 闸门是必要的——
否则 `generate.py` 的 import 也要动，而它已经是 4 条 import 改动了。
`tests/pipeline/test_clean.py:262` 的 `assert WHOLE_RECORD == "*"` 照旧通过。

**语义上的取舍**（诚实交代）：`WHOLE_RECORD` 是一个**审计哨兵**，把它放进
「国标 2014 指标定义」这个模块确实有点跑题。但 `CLEANING_FIELDS`（`cleaning_log.field`
的整个取值域）按计划的 Interfaces 块就要住在这里，而 `WHOLE_RECORD` 是那个取值域的成员，
两者应当同住。`indicators.py:112-123` 的注释把这条理由写全了。

### C8 【中】新增了 `app/db/models/_shared.py`，Files 块没列它 — 自己重新推导

Files 块写的是 `models/{__init__,organisation,assessment,derived,prescription,feedback,ops}.py`
——恰好 7 个，与 spec §4 的六个小节 + `__init__` 一一对应。但 `JsonText` 与 `_in_domain`
是**跨小节**的基础设施：`JsonText` 被 assessment（`InterestSurvey` 2 列）、derived（4 列）、
ops（`CleaningLog` 2 列）用；`_in_domain` 被 organisation、assessment、derived、ops **四个**
模块用。塞进 7 个里的任何一个，都会让另外几个为了拿一个工具去 import 一个与它毫无关系的
小节（例如 `derived` 为了 `JsonText` 去 import `organisation`）。

另一个选项是在 `__init__.py` 里定义它们、并让子模块 `from app.db.models import JsonText`——
那要求 `__init__.py` 把定义写在子模块导入**之前**，靠「部分初始化的模块已经有这个属性」
成立，一次无害的重排就会变成 `ImportError`。太脆。

**处置**：加第 8 个模块 `_shared.py`（65 行）。前导下划线 ⇒ 它不出现在 Ruling 1 的
公有名基线里（过滤条件是 `not n.startswith("_")`），故**不影响导入面判据**。
`__init__.py:62` 显式重导出 `_in_domain`，保持 `app.db.models._in_domain` 这个既有写法可用
（`tests/db/test_models.py:312` 的注释引用它）。

### C9 【中】`app/refdata.py` 的 `DATA_DIR` 改成从 `app.config.BACKEND_DIR` 推导 — 自己重新推导

Files 块把 `app/refdata.py` 列进 Modify，但 Interfaces 块只要求它新增 `RANGES_FILENAME`。
我多做了一行：`DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"` →
`DATA_DIR = BACKEND_DIR / "data"`（`app/refdata.py:19,23`）。

**理由**：不做的话，「`backend/` 在磁盘上哪里」就有**两个所有者**——新建的
`app.config.BACKEND_DIR` 与 `refdata` 里那句 `Path(__file__).parent.parent`，
违反本计划 Global Constraints 第一条。

**值逐字不变**：`refdata.py` 在 `backend/app/`，`.parent.parent` = `backend`；
`config.py` 也在 `backend/app/`，`.parent.parent` = `backend`。两条式子等价。
证据是**指纹测试照旧绿**：`tests/test_refdata.py` 钉住
`national_standard_2014.csv` 的 sha256[:16] = `D2C8E539E2FA0029`，而它是按
`DATA_DIR / STANDARD_FILENAME` 读的（`app/refdata.py:145`）。478 条全绿 + 禁区复核里
那个哈希仍是 `D2C8E539E2FA0029`，就是这一行没改坏的证据。

依赖方向：`refdata → config`，而 `config` 只 import `pathlib`（叶子），故不可能成环。
spec §3.3 的图里没有 `config` 的位置——它不是一个层，是「这个项目在磁盘上长什么样」
这件事的住址；`config.py` 的模块 docstring 把这一点写明了。

### C10 【中】**缺省种子数据下「`test_date` 漂移」不可达**，故守卫必须自己造多日批次 — 自己重新推导 + 实测

这解释了终审 B 那句诚实标注（「构造了反例但没能演示 anchor 真的翻转」）的**机制**。

实测（60 人 / `seed=20250828`，`build_dataset(CFG)` 后按 `parse_batch_key` 分组数
`tested_on` 的 distinct 值；命令见 `C:\Users\whwenhao\AppData\Local\Temp\pe_probe_daily.py`）：

```
('2024-2025', 'week1')   n=60  distinct=['2024-09-02']
('2024-2025', 'week8')   n=61  distinct=['2024-10-21']
('2024-2025', 'week16')  n=61  distinct=['2024-12-16']
('2025-2026', 'week1')   n=60  distinct=['2025-09-01']
('2025-2026', 'week8')   n=61  distinct=['2025-10-20']
('2025-2026', 'week16')  n=62  distinct=['2025-12-15']
```

**每组恰好一个 distinct 值**。一个批次只有一个采集日 ⇒ 抽取窗口怎么切，
「窗口里最后一条的 `tested_on`」都等于「窗口里最早一条的 `tested_on`」⇒ PATCH 与 `min`
折叠给出同一个值 ⇒ 漂移**不可达**。500 人的配置同样是每组一日（A/B 脚本里两个场景跑完
112 天后 `(timepoint, test_date)` 集合逐字相同）。

**处置**：守卫分两层，都不依赖缺省数据的这个巧合——

1. `tests/pipeline/test_daily.py::test_fitness_batch_folds_test_date_to_the_earliest`
   直接对私有函数喂乱序日期 `(09-08, 09-01, 09-05, 09-01)`，四次期望值逐个写死
   `(09-08, 09-01, 09-01, 09-01)`。M4 施加后第三次得到 `09-05`，红。
2. `…::test_batch_test_date_is_the_earliest_tested_on_whatever_the_window`（2 个参数化用例）
   先用 `_spread_week1_tested_on` 把 `fitness.csv` 里本学年 week1 那 60 条的 `tested_on`
   按行序轮转到 5 天上（造出真实乐跑接口那种「一次 week1 体测跨好几个采集日」的形状），
   再分别按「一次跑完」与「分两次跑」回放，两边都必须得到 `2025-09-01`；
   并附一条反空转断言（该批次的 `tested_on` distinct 集合恰好是那 5 天），
   免得「min == test_date」退化成平凡真。

真实的乐跑接口不会这么整齐，所以这个缺陷在生产上是可达的——修它的理由与简报 Step 5 的
⚠️ 一致：加了 `tested_on` 之后 `test_date` 的唯一职责就是 `assessment_anchor` 的排序键。

### C11 【中 → 已闭环】**整学期回放墙钟比 Plan 01 记录的区间高约 2–3 s：已用基线 worktree 证明不是本 Task 造成的** — 自己实测

| 量 | 数值 | 口径 |
|---|---|---|
| Plan 01 fix round 3 记录 | **17.98–18.92 s**（n=5） | `tests/pipeline/test_backfill.py:84` 的 docstring：「量的是**回放本身**」 |
| 本 Task 实测（现状 A） | **20.93 / 21.13 s**，中位 21.03 s（n=2） | 同口径：`run_backfill` 那一句的 `time.perf_counter()` 差 |
| 本 Task 实测（B：撤掉 Step 5 的额外 SELECT） | **20.70 / 21.09 s**，中位 20.89 s（n=2） | 同上，monkeypatch `_fitness_batch`，不改生产代码 |
| pytest `--durations` 的 `replay` 夹具 setup | **22.00 s**（n=1） | ⚠️ **不同口径**：它含 `create_engine` + `init_db` + `seed_database`，不只是回放 |

500 人 / `seed=20250828` / 112 业务日 / `START=2025-09-01` `END=2025-12-21`，
落 `tempfile.mkdtemp()` 下的独立 sqlite 文件，`.db` 终态 91 590 656 B，`len(runs) == 112`。
复现：`python $env:TEMP\pe_ab_timing.py`。

**已隔离的部分**：Step 5 那次额外 SELECT 的代价 = A − B = **+0.14 s**（A/B = 1.007），
而**组内极差 0.20 s（A）/ 0.39 s（B）大于组间差**，故这 0.14 s 在本机**不可分辨**，
只能给上界：`_fitness_batch` 调用恰好 **3000 次**（500 人 × 6 采集日，两个场景都是 3000），
折算每次 ≤ **0.045 ms**。

**残差已用 `git worktree` 在基线上亲测，不再是推测**（控制者指示「处理评审关切」后补做）。
`git worktree add --detach $env:TEMP\pe_base e26347f` 开一个**独立目录**检出基线，
**不动主工作树**（这正是硬规矩 #46 要求避开 `git checkout` 的理由——worktree 是它的合法替身），
两棵树用**同一个脚本**（`$env:TEMP\pe_replay_one.py`）、同一份数据、同一台机器、
背靠背各跑 n=2：

| 树 | commit | `run_backfill` 墙钟 (n=2) | 均值 | 组内极差 | `.db` 终态 |
|---|---|---|---|---|---|
| BASE | `e26347f`（Plan 01 状态） | **20.48 / 20.85 s** | 20.66 s | 0.38 s | 91 553 792 B |
| HEAD | `1df5e8a`（本 Task 之后） | **20.89 / 21.18 s** | 21.03 s | 0.29 s | 91 590 656 B |

- HEAD − BASE = **+0.37 s（+1.8%）**，而**两组各自的组内极差（0.38 / 0.29 s）都大于组间差**
  ⇒ 本 Task 的全部改动（`tested_on` 新列 3000 行 + `_results_of` 多一个 `WHERE` × 112 天 × 2
  + Step 5 的 3000 次额外 SELECT）在 500 人整学期回放上**不可分辨**。
- `.db` 终态 **+36 864 B = +0.040%**（十进制百分比）——这就是新列的存储代价。
- **BASE 在本机也是 20.5–20.9 s**，而 Plan 01 记录的是 17.98–18.92 s（n=5）。
  故那 +2–3 s 的差**不是本 Task 造成的，是本机与 Plan 01 那台机器/那一轮的差异**。
  两棵树 `len(runs) == 112`、`fitness_test_result` 都是 **3000 行**，工作量逐字相同，
  所以这不是「BASE 少干了活」。
- worktree 用完即 `git worktree remove --force` + `prune`；`git worktree list` 只剩主树，
  `git status --short` 空，禁区四项复核照旧全过（`pe.db` 不存在 / `data/seed/` 0 文件 /
  评分表 sha256[:16] = `D2C8E539E2FA0029` / `git diff e26347f..HEAD -- backend/data/` 空）。

**是否要紧**：`assert elapsed < 60` 的余量是 60 / 21.18 = **2.83×**，仍在硬规矩 #42
要求的 2× 之上，故那条断言**不是** flaky。带 `--cov` 时它自己 skip（既有设计）。
`tests/pipeline/test_backfill.py:75-84` 提到的「整个文件 < 30 s 软预算」：本 Task 实测
`python -m pytest tests/pipeline/test_backfill.py -q --durations=6` = **30.52 s**（7 条，n=1），
**略超**那个 30 s 软预算（它不是断言，没有任何测试量本文件墙钟）；而 BASE 在同一台机器上
也要 20.5 s 回放，故这 30.52 s 里超出预算的部分**不是本 Task 引入的**。
若控制者认为 30 s 是要守的，最省的办法是把 `replay` 夹具的人数从 500 降到 300——
但那会动 Plan 01 的一条口径，**我没做**。

### C12 【低】`tests/pipeline/test_backfill.py` 里同一个量有两个互不相容的实测区间 — 生产状态（Plan 01 遗留，本 Task 未动该文件）

- `:84`（夹具 docstring）：「真正被断言的只有 `test_backfill_500_students_under_60_seconds`
  里的 `elapsed < 60`，量的是**回放本身**（fix round 3 n=5：**17.98–18.92 s**，余量 3.2×）」
- `:186`（skip 消息）：「不带 --cov 时实测 **28.4–34.0 s**（余量 1.8–2.1×），照常断言」

两个数各自与自己的余量自洽（60/18.92 = 3.17 ≈ 3.2×；60/34.0 = 1.76、60/28.4 = 2.11 ≈ 1.8–2.1×），
但指的是**同一个** `elapsed`。看起来 `:186` 是较早一轮的数、`:84` 是 fix round 3 的数，
后者更新了而前者没跟上。派单里引用的「28.4–34.0 s」取自 `:186` 那一处。
本 Task 的实测（HEAD 20.89–21.18 s、BASE 20.48–20.85 s，见 C11）离**两个**区间都不近，
故我按 `:84` 的口径对比（同为「回放本身」）。

**处置：未改。** 三点理由：① 那是 Plan 01 的产出、不在本 Task 的 Files 块里；
② 正确的修法取决于「哪台机器算权威口径」，那是控制者的账本决定，不是我能替他做的
——本机的 20.5–21.2 s 与 Plan 01 记录的 17.98–18.92 s 差 +13…+18%，而 C11 的 worktree A/B
证明这个差**不是代码造成的**，所以「该把哪个数写进散文」是个口径问题；
③ 我若自己填一个数进去，就等于给同一个量造出**第三个**区间，正是这条关切要消灭的东西。

**给控制者的现成替换文本**（若决定统一口径，把 `:186` 那半句换成）：

```
不带 --cov 时实测见本夹具 docstring 的 fix round 3 那一行（17.98–18.92 s，n=5，余量 3.2×）；
Plan 02 Task 1 在同一台机器上复测 BASE(e26347f) 20.48–20.85 s / HEAD(1df5e8a) 20.89–21.18 s
（各 n=2，脚本见该 Task 报告 C11），余量 2.83×，照常断言
```

### C13 【低】CLI 输出有一处操作员可见的措辞变更 — 自己重新推导

`python -m app.pipeline.daily` 的输出：

- `备注：{error_summary}` → **`错误摘要：{error_summary}`**（`daily.py:778-781`）。
  理由：自 Plan 02 起这一列只承载真错误，「备注」这个措辞是当初为了软化「非错误内容住在
  error_summary 里」而选的，现在名实相符了。
- 新增一行（仅在 `muscle_line_gaps > 0` 时）：
  `缺肌肉量 P20 判定线的 (性别 × 年级组) 组数：N（这些组的 C 只由体脂率决定，机制见 daily_sync_run.muscle_line_gaps 的列注释）`
  （`daily.py:770-777`）。理由：那段文本被换掉之后，跑 CLI 的人当场就看不见这个信号了；
  计数列能进报表，但报表不是终端。

**无测试断言 CLI stdout**：`git grep -n "capsys\|备注\|注意（非错误）" -- backend/tests` 零命中
（`备注` 与 `注意（非错误）` 在 `backend/` 下也只出现在我改掉的那两处）。
故这不破坏任何守卫，但**它是行为变更**，Plan 03 若打算解析终端输出需要知道。
`python -m app.pipeline.backfill` 的输出未改。

### C14 【低】动了两个 Files 块没列的测试文件的 import — 自己重新推导

`tests/domain/test_derive.py:20` 与 `tests/seed/test_fitness.py:35`（以上为基线 `e26347f` 口径）
原先都 `from app.seed.fitness import COLUMN_BY_ITEM`，改成从 `app.domain.indicators` 导入
（现分别在 `test_derive.py:15-18` 与 `test_fitness.py:21-31` 的那个 import 块里）。

**理由**：① 单一所有者——常量搬家之后，消费者应当指向新住址；
② 一个 **domain** 测试从 `app.seed` 导入常量，正是本 Task 在生产层要消灭的那个形状
（新的依赖方向守卫只扫 `app/`，扫不到 `tests/`，故这条只能靠人守）；
③ 改动面是 2 行 import，零逻辑改动，两侧测试全部照旧通过。

**不是必须**：`app/seed/fitness.py:42` 重导出了 `COLUMN_BY_ITEM`，旧写法也能用。
若评审认为不该动 Files 块之外的文件，还原这 2 行即可，不影响任何断言。

### 附：一处过程性观察（不是关切，但下一个人会撞上）

**`git grep` 只搜已跟踪文件。** 本 Task 有 13 个新文件，在 `git add` 之前
`git grep -n "^BACKEND_DIR" -- app/config.py` 之类会**静默返回空**，看起来像「没有这个定义」。
我因此一度以为 `app/config.py` 没写进磁盘。新文件一律用 python 直接读，或先 `git add -N`。

**`core.autocrlf=true` 下，新写成 LF 的文件若事后改成 CRLF，`git status` 会报它 modified**
（实测：把 5 个 LF 新文件转成 CRLF 后 `git status --short` 列出 5 条 ` M`，
而 `git diff --exit-code` 仍返回 0）。机制未查证。处置：把那 5 个文件还原成 LF
（= 提交进去的 blob 字节），`git status` 随即干净。
**后果**：本仓工作树里 pre-existing 的 `.py` 是 CRLF，而这 5 个新文件是 LF；
**blob 一律是 LF**（实测：`git cat-file -p HEAD:<path>` 对 8 个文件逐个数字节，
CRLF 计数全为 0），故提交内容与仓库其余部分一致，只是工作树字节不一致。
下次 `git checkout` / `git merge` 会把它们重写成 CRLF（硬规矩 #46），届时按字节哈希的
断言需要复核——本 Task 没有任何断言依赖这 5 个文件的字节。

---

## 7. 未做 / 有意不做的事

| 项 | 原因 |
|---|---|
| 计划 Step 4 第 1 项的两条具名 `Index` | 实测冗余（关切 C2）；改成守 `EXPLAIN QUERY PLAN` 的测试 |
| 计划 Step 4 第 3 项的 `prescription_count` / `alert_count` | Plan 01 已建（关切 C3）；只补了列注释与一条钉住它们的测试 |
| `.gitattributes` 改动 | 本 Task 没新增任何 `backend/data/` 下的文件；Task 3 落 YAML 时才需要 |
| `--recreate` CLI 开关 | `session.init_db` 的 docstring 里说明了为什么不做（删文件更诚实，一个「帮你把库删了」的开关本身就是危险动作） |
| 把 `app/seed/fitness._anthropometrics` 里的 BMI 算式换成一次 `bmi_of(...)` 调用 | Ruling 2/15：seed 的改动只允许是 import 与被删常量，那是**逻辑行**。故「生成器与生产路径口径一致」仍由 `tests/domain/test_derive.py:265` 的**独立复算**钉住（它刻意自己写了一遍算式，不复用 `bmi_of`，两侧不同源）。这条交代写进了 `indicators.py:194-201` 的 `bmi_of` docstring |
| `Document/` 那份开工前就存在的未提交修改 | ~~不是我的改动~~ → **控制者指示后已处置**：无损保全 + 还原到 HEAD（关切 C1） |
| `tests/pipeline/test_backfill.py` 的两个互斥区间 | Plan 01 遗留，不在本 Task 的 Files 块里；「该写哪个数」是控制者的口径决定，我给了现成替换文本（关切 C12） |
| 把 `replay` 夹具从 500 人降到 300 人以回到 30 s 软预算 | 那会动 Plan 01 的一条口径；且 C11 的 worktree A/B 证明超预算的部分不是本 Task 引入的 |

---

## 8. 评审关切的处置汇总

| # | 优先级 | 一句话 | 处置 | 需要控制者做什么 |
|---|---|---|---|---|
| C1 | 最高 | 开工前工作树就脏，且那份修改在丢信息 | **已闭环**：副本 + patch 保全进 `.superpowers/`，`git checkout --` 还原到 HEAD，三重取证（status 空 / 行尾归一后与 HEAD 逐字节相同 / `git apply --check` exit 0） | 确认还原是对的；若要那份陈旧内容，`git apply` 那个 patch 即可 |
| C2 | 最高 | 计划要的显式 `Index` 冗余（A/B：无加速、+25.23% 体积） | **已按实测处置**：不建索引，改建守 `EXPLAIN QUERY PLAN` 的测试（更强：同时挡住删约束与列序错两种回归） | **更正计划 Step 4 第 1 项**；若仍要具名索引，见 C2 末尾的两行改法 |
| C3 | 最高 | 计划说「Plan 01 没建 `prescription_count`/`alert_count`」，实测已建 | **已按基线处置**：未新增，只补列注释 + 一条钉住三列的测试 | **更正计划 Step 4 第 3 项**；并检查 Task 9/10 的简报有没有照抄这句 |
| C4 | 高 | 简报 Step 1「同文件再加三条」与 Global Constraints / Files 块矛盾 | **已裁定**：依赖守卫进新文件，三条纯度守卫就地改写（不造第二个所有者） | 认可这个读法，或要求把三条搬进 `test_layering.py`（那要删 `test_domain_purity.py`，并同步改 Global Constraints 的指认） |
| C5 | 高 | 计划的 `CLEANING_FIELDS` 公式漏 5 个值（8 → 13） | **已按全量枚举处置**：13 个值 + 两侧不同源的双测试 | **更正计划 Interfaces 块那一行** |
| C6 | 中 | 派单说 `engine()` 有 6 个调用点，实测 3 个 | 不影响处置，缺省值已删 | 无 |
| C7 | 中 | `WHOLE_RECORD` 迁进 domain（派单让我自己判断） | **已迁**，`clean.py` 重导出 ⇒ seed 一个字没改；无环（AST 已验） | 认可，或要求改回「domain 里写字面量 `*` + 漂移测试」（那是两个所有者） |
| C8 | 中 | 新增了 Files 块没列的 `models/_shared.py` | **已加**，理由是 4 个表模块共用；前导下划线 ⇒ 不影响 Ruling 1 判据 | 认可，或指定另一个家（`__init__.py` 里定义那个方案我评估过，太脆） |
| C9 | 中 | `refdata.DATA_DIR` 改从 `config.BACKEND_DIR` 推导 | **已改**，值逐字不变（指纹测试 + sha256 双证） | 认可，或要求还原那一行（代价是 `backend/` 路径有两个所有者） |
| C10 | 中 | 缺省种子数据下 `test_date` 漂移不可达 | **已用两层守卫覆盖**：私有函数喂乱序日期 + 自己造多日批次的生产形状测试 | 无（这条解释了终审 B 那句诚实标注的机制） |
| C11 | 中 | 回放墙钟比 Plan 01 记录高 2–3 s | **已闭环**：`git worktree` 在 `e26347f` 上亲测 BASE 20.48/20.85 s vs HEAD 20.89/21.18 s，差 +0.37 s 小于两组各自的组内极差 ⇒ 不是本 Task 造成的 | 无（若 30 s 软预算要守，见 C11 末尾） |
| C12 | 低 | `test_backfill.py` 里同一个量有两个互斥区间 | **未改**（Plan 01 产出 + 口径决定权在控制者），给了现成替换文本 | 决定是否统一口径 |
| C13 | 低 | CLI 输出措辞变更 + 新增一行 | 已做，无测试断言 stdout | 告知 Plan 03（若它要解析终端输出） |
| C14 | 低 | 动了两个 Files 块没列的测试文件的 import | 已改（单一所有者 + domain 测试不该 import seed） | 认可，或要求还原那 2 行（不影响任何断言） |

**闭环 2 条（C1 / C11）、按实测偏离计划 3 条（C2 / C3 / C5，都需要控制者更正计划文本）、
我的判断待认可 5 条（C4 / C7 / C8 / C9 / C14）、无需动作 4 条（C6 / C10 / C12 / C13）。**

**本 Task 之后仓库的状态**：`git status --short` 空；HEAD = `1df5e8a`（一个 commit，未 push，
未合并）；`backend/` 工作树与 HEAD 逐字节一致（`git diff --exit-code HEAD -- backend/` exit 0）；
478 passed / 0 failed、`-W error` 0 error、`app/domain` 分支覆盖 Miss 0 / BrPart 0 / 100%。

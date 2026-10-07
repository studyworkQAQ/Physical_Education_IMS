# Plan 02 Task 1 实施报告 — 架构债清偿

> ## ⚠️ 数据丢失事故（20261007-174217，控制者记录）
>
> 本文件在 Plan 02 Task 2 fix round 2 进行期间（约 16:44:35）被**外部进程截断**：
> 从 295 011 B / 3906 LF 掉到 77 837 B / 1031 LF，`## 9` 与 `## fix round 1`–`## fix round 5`
> **六个节全部消失**。同一秒 `task-2-report.md` 也被截断（117 694 B / 972 LF → 62 640 B / 617 LF，
> 丢了 `## fix round 1` 节）。
>
> **根因（高度怀疑，未证实）**：两个文件被截断后的行数**精确等于 `Read` 工具此前报过的行数**
> （1031 / 617，账本 Ruling 64 记的也是 1031）。即 IDE 的文件视图层把它那份
> 「只含前 N 行」的缓存**写回了磁盘**。此外被截断版本与备份在**第 580 行的措辞也不同**
> （当前写「与工作树那份陈旧副本**一致**」、备份写「与工作树那一侧一致」），
> 说明写回的是**陈旧**缓存而不只是短缓存。
>
> **已还原**：从 `$env:TEMP\pe_fr5_report_backup.md`（Task 1 fix round 5 的实现者在**追加前**
> 做的字节备份，243 343 B / 3298 LF）还原，**recover 了 `## 9` 与 `## fix round 1`–`## fix round 4`**。
>
> **仍然丢失、无法恢复**：`## fix round 5` 那一节（约 51 668 B）。全 `$env:TEMP` 扫描
> （91 个候选文件）没有任何副本。**其结论与全部关键取证已由控制者逐条转录进账本**
> `.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md` 的
> `#### Task 1 fix round 5 — 控制者亲验` 一节（Ruling 79–88，含 6 相位变异表与实现者报的
> 5 条控制者错误），故**技术结论无损**，丢的是实现者自己的详细过程记录。
>
> **取证物**：被截断的版本原样另存为 `task-1-report.TRUNCATED-20261007-174217.md`（未删）。
>
> **教训已升级为硬规矩 #68/#69**（见账本）。


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

⚠️ 另需注意：`task-1-brief.md` 的内容与工作树那一侧**一致**（比如 `bmi_of` 那段是短版），
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
---

## 9. 过程取证：编辑工具在本报告文件上**静默未落盘** 26 次

这一节是给自己和下一个实现者留的，不是 Task 成果。

**现象**：对 `task-1-report.md` 连续做了 **26 次**行内编辑（修正过期行号、补 C1/C11 的处置、
新增 §8）。每一次工具都返回 `success` 并附上**看起来正确的 diff**；`git status` 看不出异常
（该文件在 `.superpowers/` 下，被 gitignore）。事后用 python 读回，**26 处一处都没落盘**：
文件仍是首次整文件写入时的那份（67 973 B / 932 行），旧的 C1 处置文本
（「我**没有碰它**」）原样在里面。

**怎么发现的**：写完 §8 之后我没有直接信，而是跑了一个「列全部 `## ` 标题」的探针，
输出里**没有 §8**——标题清单是文件的显式全量读取（硬规矩 #27），比「工具说成功了」可信。
随后用一个 26 条 marker 的校验脚本逐条查，`落盘 0/26`。

**处置**：改用 python 做替换（23 个操作，每个都 `assert` 目标串出现次数恰为 1，
任一不匹配就 `sys.exit(1)` **不写盘**），写回后再跑同一个 26-marker 校验脚本 → `落盘 26/26`，
并额外查了 13 条**旧**文本确认全部消失（`我**没有碰它**` / `未隔离的部分` /
`derived.py:180-182` / `test_models.py:311` / `2.84×` …，13 条全为 `False`）。
文件从 67 973 B / 932 行 → **77 828 B / 1031 行**。

**这不是孤例**：Plan 01 记录了 18 次同类失效，派单也明写「就在写本计划时，控制者连续 4 次
SearchReplace 报成功而磁盘未写」。**26 次是本仓目前单文件最高的连续失败计数。**

**对代码的影响：无。** 本 Task 对 `backend/` 的每一次编辑都用**独立的第三条路径**验过，
不依赖编辑工具的返回值：

| 验证手段 | 覆盖了什么 |
|---|---|
| `git diff --numstat` / `--stat` | 每次编辑后确认改动行数符合预期、且没有整文件被重写 |
| python 读回 + 打印行号 | 关键定义（`COLUMN_BY_ITEM:104`、`WHOLE_RECORD:124`、`CLEANING_FIELDS:154`、`bmi_of:183`、`tested_on:97`、`muscle_line_gaps:95`、`engine(url: str):53`…）逐个确认 |
| `pytest` 全量 478 条 | 行为侧：拆包后导入面基线测试通过 ⇒ `models/__init__.py` 的重导出确实写对了 |
| `--cov=app.domain --cov-branch` 100% | `bmi_of` 真的迁进了 domain 且真的被调用（否则会有 Miss） |
| 4 条变异的 sha256 前后比对 | 反向编辑还原**逐字节**成功（4/4 `restored_byte_identical = true`） |
| 60 处 `文件:行` 引用的独立校验脚本 | 报告里引用的每一处代码位置都真的含我说的那个东西（第二轮 60 处，3 处不符已修正） |
| `git diff --exit-code HEAD -- backend/` | 收工时工作树与提交逐字节一致（exit 0） |

**给下一个实现者的规矩**：对 `.superpowers/` 下的**报告与账本**（gitignore ⇒ `git diff` 帮不上忙）
做行内编辑时，**写完必须用 python 读回并查一个只有新内容里才有的 marker**；
不要信工具返回的 diff。整文件重写（Write）在本 Task 里是可靠的——首次写 932 行一次成功。

---

## fix round 1

**派单**：评审 I1–I4 + Minor M1/M2/M3/M7，共 8 项，全部是散文与守卫口径，零生产语义改动、
零断言期望值改动。
**基线** `ad1d190`（478 passed / 0 failed，`app/domain/` 分支覆盖 100%）。
**产出** 一个 commit **`6a2938f`**（不 push、不动 `main`），**479 passed / 0 failed**
= 478 + M7 那**一条**新测试函数（派单已预授权这一条）。

行号一律 **shell 口径**（`git grep -n` / python 数行），**绑定 commit `6a2938f`**。

### fr1.0 三个闸门 + 禁区（全部亲跑）

| 闸门 | 命令 | 结果 |
|---|---|---|
| 全量测试 | `cd backend; python -m pytest -q -W error -p no:cacheprovider` | **479 passed in 54.42 s**，0 failed，**-W error 0 error** |
| domain 分支覆盖 | `cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing` | `TOTAL 399 stmts / Miss 0 / 114 branch / BrPart 0 / **100%**`；同一次跑 `478 passed, 1 skipped in 114.25 s`（那条 skip 是 `test_backfill_500_students_under_60_seconds` 在 `--cov` 下的既有自我跳过，非本轮引入） |
| 硬规矩 #32（剥 docstring 比 `ast.dump`） | `python $env:TEMP\pe_fr1_rule32.py` | **PASS**，见 fr1.6 |

禁区（python 直接读字节，不走 PowerShell 管道）：

```
pe.db exists: False
data/seed files: 0
csv bytes: 21412 sha256[:16]: D2C8E539E2FA0029 CRLF: 0
```

`git status --short` → **0 行**；`git diff ad1d190..HEAD --stat -- backend/app/seed/ backend/data/ .gitattributes`
→ **空**（本轮没碰这两处，也没碰 `.gitattributes`）。

本轮 diff（`git diff ad1d190..HEAD --stat`，**7 文件 / +371 / −48**）：

```
 backend/app/config.py                            |  11 +-
 backend/app/pipeline/daily.py                    |  31 ++++-
 backend/tests/architecture/test_domain_purity.py | 153 +++++++++++++++++++----
 backend/tests/architecture/test_layering.py      |  85 +++++++++++++--
 backend/tests/db/test_models.py                  |  96 +++++++++++++-
 backend/tests/pipeline/test_daily.py             |  13 +-
 backend/tests/test_config.py                     |  30 +++++
```

### fr1.1 I1（Ruling 23）— 两条守卫对 `level >= 2` 的相对导入无条件放行 ✅

**改法**（两个文件同法，各自一份 `_package_of` + `_absolute`）：

- `tests/architecture/test_domain_purity.py:102` `_package_of(py)`：源文件 → 所在包
  （`py.relative_to(BACKEND).with_suffix("").parts[:-1]`；`__init__.py` 与同目录普通模块
  给出同一个包，正是 Python 的 `__package__`）；`:113` `_absolute(module, level, package)`
  把 `ast.ImportFrom` 折算成绝对模块串，**上溯到顶层包 `app` 之外返回 `None`**；
  `:141` `_is_allowed(module)` 收窄成只接受**绝对串**（原来那个 `if level: return True`
  整段删掉）；`:224-232` 调用处 `absolute is None` 也判 offender。
- `tests/architecture/test_layering.py:70` / `:81` 同样两个 helper；`:100-127`
  `_imported_modules(tree, package)` 不再 `if node.level: continue`，改成
  `yield node.lineno, _absolute(...)`；`:150-156` 调用处把 `module is None` 单独报成
  「相对导入上溯到顶层包 app 之外」。

**为什么不照裁定字面写「`level == 2` → `app`、`level >= 3` → offender」**：那两条只对
**扁平的** `app/domain/` 成立。裁定自己给的公式一旦遇到 Task 2 要建的
`app/domain/prescription/`，`from ..indicators import X`（`level == 2`）会被折算成
`app.indicators` → **假 offender**，把后续 Task 卡死；而 `app/db/models/x.py` 的
`level == 3` 与 `app/domain/x.py` 的 `level == 3` 语义**不同**（前者到 `app`、后者超出
`app`），不能用同一个常数档。故改成**按源文件真实包深度**折算——对今天扁平的 domain
与裁定的三档给出**逐字相同**的判定（见下面 11 例），同时不会在 Task 2 造出假红。
合成树里专门放了一例 `app/domain/sub/probe.py: from ..tables import X`（期望 **GREEN**）
钉住这一点。

**验收：合成树端到端，改前 vs 改后**（`python $env:TEMP\pe_fr1_relimport.py <backend>`；
树建在 `tempfile.mkdtemp(prefix="pe_fr1_rel_")` 下、形状与 `backend/app` 相同，每种写法
写进一个探针槽、**每个用例前把全部探针重置成良性**以免串味；用 `importlib` 直接加载守卫
模块并把 `DOMAIN` / `BACKEND` / `APP` 指到合成树，然后调用测试函数本体）：

改**前**（守卫取自 `ad1d190` 的工作树，即评审量的那份）：

```
!! [purity  ] app/domain/probe.py       from ..seed import generate                want=RED   got=GREEN
!! [purity  ] app/domain/probe.py       from .. import pipeline                    want=RED   got=GREEN
!! [purity  ] app/domain/probe.py       from ...seed import generate               want=RED   got=GREEN
OK [purity  ] app/domain/sub/probe.py   from ..tables import X                     want=GREEN got=GREEN
OK [layering] app/db/models/probe.py    from ._shared import JsonText              want=GREEN got=GREEN
!! [layering] app/db/models/probe.py    from ...seed import generate               want=RED   got=GREEN
!! [layering] app/db/models/probe.py    from ...seed.generate import DEFAULT_CSV_DIR want=RED got=GREEN
!! [layering] app/pipeline/probe.py     from ..seed import generate                want=RED   got=GREEN
OK [layering] app/pipeline/probe.py     def f(): from app.seed.fitness import …    want=RED   got=RED   app/pipeline/probe.py:2: app.seed.fitness
OK [purity  ] app/domain/probe.py       import numpy / from .tables import X       want=GREEN got=GREEN
OK [layering] app/db/models/probe.py    PASS = 1                                   want=GREEN got=GREEN

符合期望 5/11
```

改**后**（守卫取自 `6a2938f`）：

```
OK [purity  ] app/domain/probe.py       from ..seed import generate       want=RED   got=RED   probe.py:1: ..seed → app.seed
OK [purity  ] app/domain/probe.py       from .. import pipeline           want=RED   got=RED   probe.py:1: .. → app
OK [purity  ] app/domain/probe.py       from ...seed import generate      want=RED   got=RED   probe.py:1: ...seed → <上溯到顶层包 app 之外>
OK [purity  ] app/domain/sub/probe.py   from ..tables import X            want=GREEN got=GREEN
OK [layering] app/db/models/probe.py    from ._shared import JsonText     want=GREEN got=GREEN
OK [layering] app/db/models/probe.py    from ...seed import generate      want=RED   got=RED   app/db/models/probe.py:1: app.seed
OK [layering] app/db/models/probe.py    from ...seed.generate import …    want=RED   got=RED   app/db/models/probe.py:1: app.seed.generate
OK [layering] app/pipeline/probe.py     from ..seed import generate       want=RED   got=RED   app/pipeline/probe.py:1: app.seed
OK [layering] app/pipeline/probe.py     def f(): from app.seed.fitness …  want=RED   got=RED   app/pipeline/probe.py:2: app.seed.fitness
OK [purity  ] app/domain/probe.py       import numpy / from .tables …     want=GREEN got=GREEN
OK [layering] app/db/models/probe.py    PASS = 1                          want=GREEN got=GREEN

符合期望 11/11
```

派单点名的四种情况逐条对号：① domain 的 `from ..seed import generate` → **改前 GREEN、
改后 RED**；② domain 的 `from .. import pipeline` → **改前 GREEN、改后 RED**；
③ db 三级深度 `from ...seed import generate` → **改前 GREEN、改后 RED**；
④ `app/db/models/` 包内的 level-1 相对导入 `from ._shared import JsonText` →
**改前改后都 GREEN**（不误伤）。三条控制组（函数体内绝对导入变红、良性内容变绿、
子包内 level-2 合法导入变绿）证明「不是守卫整体空转、也不是恒红」。

**真实仓库里没有 offender**（与评审一致）：全仓相对导入 12 条、全部 `level == 1`、
全部落在 `app.db.models` 包内，折算后是 `app.db.models._shared` / `app.db.models.organisation`
一类，不以 `app.seed` 开头。命令（已写进两个守卫的 docstring，不再指向不入库的文件）：

```
cd backend; python -c "import ast,pathlib; [print(p, n.lineno, n.level, n.module) for p in sorted(pathlib.Path('app').rglob('*.py')) for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.level]"
```

`cd backend; python -m pytest tests/architecture -q -W error` → **4 passed in 0.08 s**。

### fr1.2 I2（Ruling 24）— 守卫能力虚报 ✅

`test_domain_purity.py:280-311` 整段改成实测口径。评审的两点纠正我都独立复验为真：
`_dotted`（`:238-256`）只把**调用表达式自身**还原成点号串，代码里没有任何赋值追踪；
`now = datetime.now` 的赋值来源是 `ast.Attribute` 不是 `ast.Call`。

自己的合成树实测（`python $env:TEMP\pe_fr1_clock.py <backend>`，每条写法单独写进
`app/domain/probe.py` 后分别调用三条守卫）：

```
_f = open; _f('x')                              G1 allow-list=GREEN  G2 AST 时钟/open=GREEN  G3 子串 IO=GREEN
import datetime as _dt; _now = _dt.datetime.now; _now()
                                                G1=RED(probe.py:1: datetime)  G2=GREEN  G3=GREEN
open('x')                                       G1=GREEN  G2=RED(probe.py:1: open() 命中 open)  G3=GREEN
import builtins; builtins.open('x')             G1=RED(builtins)  G2=RED(probe.py:2: builtins.open() 命中 open)  G3=GREEN
def reopen(): … ; reopen()                      G1=GREEN  G2=GREEN  G3=GREEN
def open_ended(): … ; open_ended()              G1=GREEN  G2=GREEN  G3=GREEN
只有 docstring:「不要用 datetime.now()，也不要 open(」
                                                G1=GREEN  G2=GREEN  G3=GREEN
import datetime as dt; dt.datetime.now()        G1=RED(datetime)  G2=RED(dt.datetime.now() 命中 datetime.now)  G3=GREEN
```

与评审的结论逐条吻合：`_f = open; _f('x')` **三条全绿**；散文里的 `datetime.now()` /
`open(` **不再误报**；`reopen()` / `open_ended()` **不被误抓**；`builtins.open()` **被抓**。

落进 docstring 的新口径（`:280-311`）：真收益是「散文不再误报」+「`.` 边界替代 `\b`
正则」+「`builtins.open` 这类点号形态天然覆盖」，并明写「`dt.datetime.now()` 旧子串守卫
**也能撞上**，故不是新增拦截力」；末尾按硬规矩 #39 补 ⚠️ 段：**别名间接不被守卫**，
并给出三条守卫各自为什么帮不上的机制（`open` 是内置名不需 import 故 G1 帮不上、
`FORBIDDEN_IO` 里没有裸 `open` 故 G3 帮不上、G2 拿到的是 `ast.Name(id="_f")` → 点号串
`"_f"` → 不命中 `FORBIDDEN_CALLS`）。

### fr1.3 I3（Ruling 25）— 旧 deny-list 的历史陈述写反了 ✅

**我没有采信转述，把基线守卫亲跑了一遍**（`python $env:TEMP\pe_fr1_i3.py`：
`git show e26347f:backend/tests/architecture/test_domain_purity.py` 用 subprocess 取字节
落盘、`importlib` 加载、`DOMAIN` 指到合成树）：

```
基线守卫 3226 B
基线 FORBIDDEN = ['fastapi', 'httpx', 'pydantic_settings', 'random', 'requests', 'sqlalchemy']
'os' in FORBIDDEN = False

from os import listdir   G1 deny-list=GREEN  G2 时钟/open=GREEN  G3 子串 IO=GREEN
import numpy.random      G1 deny-list=GREEN  G2 时钟/open=GREEN  G3 子串 IO=GREEN
import app.refdata       G1 deny-list=GREEN  G2 时钟/open=GREEN  G3 子串 IO=GREEN
import sqlalchemy        G1 deny-list=RED    G2=GREEN            G3=GREEN      ← 控制组
import os                G1=GREEN            G2=GREEN            G3 子串 IO=RED ← 控制组
os.listdir('x')          G1=GREEN            G2=GREEN            G3 子串 IO=RED ← 控制组
```

评审的裁定完全成立：基线 `FORBIDDEN` 六项、**没有 `os``**；三种写法三条守卫全绿。
我另外加了三条**控制组**证明基线守卫不是恒绿——这一组正好把机制说清楚：`import os`
被 G3 抓住是因为源码里有子串 `import os`，而 `from os import listdir` 里是 `os import`，
**没有那个子串**，也没有 `os.listdir`。

三处口径的矛盾也复核了：本报告 §5 与 commit `1df5e8a` 的信息都是对的（都写「旧 deny-list
抓不到」），**只有落进代码的那句 docstring 是反的**——正如派单说的，上一轮我知道正确答案
却没写进代码。改后的文本在 `test_domain_purity.py:151-176`，含基线 `FORBIDDEN` 的原文引用、
基线的三个行号（`:13` 的集合、`:38`/`:40`/`:41` 的顶层名比对，均按 `git show` 的字节数行
复核过），以及上面那三条控制组。

### fr1.4 I4（Ruling 26）— `min` 折叠的因果方向写反了 ✅

**先自己构造并跑了评审那个反例**（`python $env:TEMP\i4_anchor.py`：内存库，同一个 `week1`
批次、5 条成绩横跨 `2025-09-01..09-05`，只改 `fitness_test_batch.test_date` 一个值，
逐日调用真的 `app.pipeline.percentile_stage.assessment_anchor`）：

```
WEEK1_TIMEPOINT = 'week1'
判据源码: percentile_stage.py:133  FitnessTestBatch.test_date <= as_of
test_date=2025-09-01  09-01=Y 09-02=Y 09-03=Y 09-04=Y 09-05=Y   -> 首次被选中 as_of=2025-09-01
test_date=2025-09-05  09-01=n 09-02=n 09-03=n 09-04=n 09-05=Y   -> 首次被选中 as_of=2025-09-05
```

**`min` = 提前，不是延后**，评审正确。两处散文都改了，且都附了代码行 + 引文（硬规矩 #29）：

- `app/pipeline/daily.py:199-217`：先给**真理由**（`:201`「这才是选 `min` 的全部理由，
  与『保守』无关」），再给 ⚠️ 段（`:203-212`）——判据引文
  `percentile_stage.py:133`、上面两行逐日输出、以及「提前可用为什么是自洽的」
  （`FitnessTestResult.tested_on <= as_of`，`percentile_stage.py:176`，逐行截断成
  `insufficient_data`，读不到未来数据）。
- `tests/pipeline/test_daily.py:641-650`：同一句话的第二处，同口径改写，并把完整两行输出
  指回 `_fitness_batch` 的 docstring（避免同一组数字有两个住址）。

### fr1.5 M1 / M2 / M3 / M7（Ruling 27）✅

**M1** `app/config.py:35-46`：不再说 `DEFAULT_CSV_DIR` 是 `MockLePaoAdapter` 的「缺省
`seed_dir`」。改成指向 `app.adapters.factory.build_adapter`（`kind="mock"` 且没给 `csv_dir`
时），并引两行原文钉住机制：`factory.py:50`
`return MockLePaoAdapter(DEFAULT_CSV_DIR if csv_dir is None else csv_dir)` 与
`mock_lepao.py:428` `def __init__(self, seed_dir: pathlib.Path) -> None`（**必填位置参数、
没有缺省值**）。两个行号都用 `git grep -n` 复核过。

**M2** 两处指向不入库文件的指针都清掉了（`.gitignore:10` 是 `.superpowers/`，
`git ls-files .superpowers | Measure-Object -Line` → **0**，本轮复核）：

- `tests/architecture/test_layering.py:158-176`：命令**写全**（不带省略号），一条
  `collections.Counter` 的 `python -c` 数完三个目录，另附 `git ls-tree` 交叉核对命令；
  两个实测值就地写死（基线 `e26347f` → `[('db', 4), ('domain', 6), ('pipeline', 7)] 17`；
  `ad1d190` → `[('db', 11), ('domain', 6), ('pipeline', 7)] 24`）。**这两组数我都亲跑了**：
  `git ls-tree -r --name-only` 逐文件数得 7/4/6=17 与 7/11/6=24，
  `Counter` 命令在 HEAD 上输出 `[('db', 11), ('domain', 6), ('pipeline', 7)] 24`，
  与评审复核的数一致。顺带按硬规矩 #39 写清「下界 8」守不住什么：它只挡得住「三个目录
  被一起搬空」，**单个**目录被搬空时仍剩 13…17 个 `.py`、本断言拦不住；那一档的兜底是
  domain 由 `test_domain_purity.py` 自己的 `>= 5` 看着、`pipeline`/`db` 被搬空时
  `tests/pipeline/`、`tests/db/` 在**收集期**就 ImportError，目录被**整个删掉**则由
  `_py_files` 的 `root.is_dir()` 当场拦下。
- `app/pipeline/daily.py:223-232`：「实测数字见任务报告」换成**就地写全口径**并标
  「历史实测，不被守卫」——基线 20.48 / 20.85 s（均值 20.66、组内极差 0.38 s）vs
  HEAD 20.89 / 21.18 s（均值 21.03、组内极差 0.29 s），差 +0.37 s = +1.8%，n=2，
  `git worktree` 法，余量 `60 / 21.18 = 2.83×`，并明写「那条断言只在超过 60 s 时才红，
  墙钟退化到 25 s 它照样绿；复现脚本不在库内」。
  ⚠️ 我**没有**沿用账本 Ruling 21 与本报告 §C11 那句「+0.37 s 小于两组各自的组内极差」
  ——见关切 **C-fr1-2**。
  （`app/db/models/organisation.py:69` 那处同类指针按派单指示**没动**。）

**M3** `tests/db/test_models.py:606-694`：补「⚠️ 上面四个数不被守卫」标签（`:606-610`，
明写本测试守的是**查询计划**与**两条唯一约束的列序**，全仓没有任何测试量墙钟或 `.db`
字节），并把**复现脚本的完整内容**抄进 docstring（`:617-694`，约 78 行，照
`app/db/models/_shared.py:43-44` 的形状；脚本自己的 `"""` 改成 `#` 注释以免与外层
docstring 的三引号打架）。

**抄进去之前我把它跑了两遍**（`$env:TEMP\pe_fr1_index_probe.py` 是原脚本、
`pe_fr1_index_probe2.py` 是压进 docstring 的那一份），得到一个新发现：

```
第一次（原脚本）  A median=0.1369 ms  .db=5423104 B   B median=0.1293 ms  .db=6791168 B   B/A = 0.944
第二次（docstring 版）A median=0.1291 ms  .db=5423104 B   B median=0.1277 ms  .db=6791168 B   B/A = 0.989
                  两次 plan 逐字复现：A=USING COVERING INDEX sqlite_autoindex_stratification_result_1 (student_id=?)
                                     B=USING COVERING INDEX ix_stratification_result_student_computed (student_id=?)
                  两次 行数断言 500*112 = 56000 通过、.db +1368064 B = +25.23% 逐字复现
```

即：**`.db` 字节、+1 368 064 B、+25.23%、56000 行、两条查询计划全部逐字复现**（确定性量），
而**墙钟中位不复现**——同一脚本连跑四次的 `B/A` 是 **1.086（上一轮）/ 0.944 / 1.019 / 0.989**
（每次 n=300）。故可复现的结论只有「加了具名索引**没有可测的加速**」，
而**「中位数慢 8.6%」这个方向不可复现**、是机器/负载噪声。这一点已写进 docstring
（`:611-616`），并作为关切 **C-fr1-1** 报上来（账本 Ruling 16 的措辞需要跟着收一下）。

**M7** 新建 `backend/tests/test_config.py`（**1 个测试函数、2 条断言**，`:27-30`）：

```python
assert DEFAULT_CSV_DIR.relative_to(BACKEND_DIR).as_posix() == "data/seed"
assert DEFAULT_DB_URL.endswith("/backend/pe.db")
```

两侧**不同源**（右侧字面写死在测试里，硬规矩 #35）。docstring 里写清了为什么只钉后缀与
文件名就够（`BACKEND_DIR` 错了会变红：`app/refdata.py:23` `DATA_DIR = BACKEND_DIR / "data"`，
被 `tests/test_refdata.py:82-83` 的 `.name == "data"` + `.is_file()` 与 `:187` 的指纹
`D2C8E539E2FA0029` 钉住），以及**本文件不守什么**（`data/seed/` 是否存在/为空、
`pe.db` 是否存在都不在这里断言，那是运行期状态与禁区检查，不是配置值的性质）。

**变异实测两条都有牙**（`python $env:TEMP\pe_fr1_m7_mutation.py`；改完用**反向编辑**还原，
不 `git checkout`，硬规矩 #46）：

```
config.py 原字节 sha256[:16] = 1be4001feb32c84d  (3615 B)
变异[DEFAULT_CSV_DIR 后缀 seed -> seeds]  -> exit=1 RED(有牙) | 1 failed in 0.10s
变异[DEFAULT_DB_URL 文件名 pe.db -> pe2.db] -> exit=1 RED(有牙) | 1 failed in 0.10s
还原后 sha256[:16] = 1be4001feb32c84d  逐字节相同=True
未变异基线 -> exit=0 | 1 passed in 0.01s
```

### fr1.6 硬规矩 #32 闸门（带两组对照）

`python $env:TEMP\pe_fr1_rule32.py`——把两侧的**所有 docstring**（模块/类/函数首条字符串
表达式）就地换成 `ast.Pass()`，再比 `ast.dump(include_attributes=False)`；注释本来就不进
AST。基线内容用 `git show ad1d190:<path>` 取（**不落盘、不 checkout**，避开硬规矩 #46）；
两侧一律 CRLF→LF 归一化后再解析（基线 blob 是 LF、工作树在 `autocrlf=true` 下是 CRLF，
不归一化会让**多行字符串字面量**假不等）。

```
=== ① 生产状态：backend/app/ 下 40 个 .py，工作树 vs ad1d190 ===
  基线里不存在（本轮新增）: 无
  不剥 docstring 就不相等（1 个）:
    - backend/app/pipeline/daily.py
  剥掉 docstring 后仍不相等（0 个）: 无 ← 闸门通过

=== ② 对照组：往基线注入 3 个真语义变异，判定必须抓到 ===
  抓到(False)  backend/app/pipeline/daily.py: 把 test_date 的 min 折叠改成 max
  抓到(False)  backend/app/config.py: 改 DEFAULT_CSV_DIR 的后缀
  抓到(False)  backend/app/pipeline/percentile_stage.py: 把 tested_on 截断的 <= 改成 <

=== ③ 对照组：同一份基线跟自己比，判定必须为 True（证明它不是恒 False）===
  self-equal(backend/app/pipeline/daily.py) = True

闸门结论: PASS
```

对照组 ① 的意义：`backend/app/` 只有 **`daily.py` 一个文件**在「不剥 docstring」时不等
（本轮改的是它 `_fitness_batch` 的函数 docstring），而 `config.py` 改的是 `#:` **注释**、
根本不进 AST —— 这正好说明这把尺子在量什么。对照组 ② 的三条变异分别打在
「本轮唯一被讨论过要不要改的语义」（`min` 折叠）、「M7 新断言守的值」（`data/seed`）与
「Step 4 的承重截断」（`tested_on <= as_of`）上，判定全部抓到。

**预期的例外**：`tests/architecture/` 两个文件本轮**要改守卫逻辑**，其 AST 必然不等价。
用同一把尺子量 `backend/tests/`（`python $env:TEMP\pe_fr1_rule32_tests.py`）：

```
AST 变了  backend/tests/architecture/test_domain_purity.py     ← I1/I2/I3，预期
AST 变了  backend/tests/architecture/test_layering.py          ← I1/M2，预期
只改散文  backend/tests/db/test_models.py                      ← M3
只改散文  backend/tests/pipeline/test_daily.py                 ← I4
NEW       backend/tests/test_config.py                         ← M7
```

**`backend/tests/` 里除那两个架构守卫外，没有任何文件的 AST 变了**——即 M3 与 I4 确实
只动了散文，**零断言期望值改动**（`test_daily.py` 那四条写死的期望日期、`test_models.py`
那几条查询计划断言逐字未动）。

### fr1.7 超出派单 8 项的两处最小必要更正（主动披露）

两处都在 `test_domain_purity.py`，都是为了让 I2 的「写明守不住什么」在文件内部**不自相
矛盾**，不改任何判定：

1. `:238-247` `_dotted` 的 docstring 原写「还原不出来的形态…**那不是漏洞**：这类写法要
   先拿到 `datetime` / `time` / `builtins` 这个对象，而拿到它的**唯一途径是 import**」。
   对 `open` **不成立**（内置名，不需 import），与 I2 新补的 ⚠️ 段是**同一个缺口**。
   改成「对 `datetime`/`time`/`builtins` 不是漏洞；**但 `open` 是内置名、不需要 import，
   故这一档对 `open` 是真漏**」，并交叉引用下面那条 ⚠️。
2. `:15-16` 模块 docstring 末尾加一句，说明第 1 条守卫在 fix round 1 又补了「相对导入
   先折算成绝对串」——否则模块级那份「三条守卫改了什么」的清单会与 `_absolute` 的存在
   对不上。

另有一处**格式性**修正：`:229-232` 的 offender 文本，绝对导入仍是原来的
`file:lineno: module`，只有相对导入才附加 `.. → app.seed` 这段折算结果（我第一版写成
所有导入都带 `x → x`，冗余，已收回）。

### fr1.8 关切清单（6 条）

**C-fr1-1【最高】账本 Ruling 16 与本报告 §C2 都把「中位数慢 8.6%」当成结论之一，而它不可复现** — 自己实测

- **读的是生产状态还是重新推导**：**自己重新实测**（本轮跑了 2 次，加上上一轮那次共 4 次）。
- **命令**：`cd <仓库根>; python $env:TEMP\pe_fr1_index_probe2.py`（脚本全文已抄进
  `tests/db/test_models.py:617-694`，从仓库可复现）。
- **观测**：同一脚本四次 `B/A` = **1.086 / 0.944 / 1.019 / 0.989**（每次 n=300，
  单次墙钟中位；本机 CPython 3.11.1 + SQLAlchemy 2.1 + SQLite）。极差 0.142，
  **跨过 1.0**，故「B 比 A 慢」的**方向不可复现**。相比之下 `.db` 字节
  （5 423 104 / 6 791 168）、`+1 368 064 B`、`+25.23%`、`56000` 行、两条 EXPLAIN QUERY PLAN
  **四次逐字相同**（确定性量）。
- **为什么最高**：账本 `progress.md:137` 写「加具名索引后中位墙钟 **0.2708 → 0.2941 ms
  （无加速，两组区间完全重叠）**、`.db` **+25.23%**」。「无加速」成立且被本轮加强；
  但**下一个 Task 的人若把 0.2708/0.2941 当稳定量引用**（例如写进 spec 或 Plan 03 的
  性能预算），会引一个噪声值。**建议账本 Ruling 16 补一句「墙钟中位不可复现，四次
  B/A = 1.086/0.944/1.019/0.989，可复现的只有『无可测加速』与体积 +25.23%」**。
  在库一侧我已经把这句写进 `tests/db/test_models.py:611-616`。

**C-fr1-2【高】账本 Ruling 21 与本报告 §C11 的「+0.37 s 小于两组各自的组内极差」对 HEAD 那组不成立** — 自己重新推导

- **读的是生产状态还是重新推导**：**重新推导**（对已入账的两组数做算术）。
- **证据**：§C11 表格给的是 BASE 20.48 / 20.85 s（极差 **0.37 s**，表里写 0.38，
  应是未舍入值）、HEAD 20.89 / 21.18 s（极差 **0.29 s**）；组间差 HEAD−BASE 均值 =
  21.035 − 20.665 = **+0.370 s**。故「+0.37 **小于** 两组各自的组内极差」对 BASE（0.38）
  勉强成立、对 HEAD（**0.29**）**不成立**——0.370 > 0.29。§C11 原文写的是「两组各自的
  组内极差（0.38 / 0.29 s）**都**大于组间差」，那一句是错的；账本 Ruling 21 照抄了它。
- **处置**：`daily.py:223-232` 里我**没有**沿用这句，改成「差 +0.37 s = +1.8%，与两组
  各自的抖动**同量级**，**n=2 不足以判定显著**」——这是 n=2 能支持的最强表述。
  「不可分辨」这个**结论**仍然成立（n=2、无方差估计、硬规矩 #42 也只要 2× 余量而这里
  是 2.83×），错的只是用来支撑它的那句不等式。**建议账本 Ruling 21 更正措辞**。

**C-fr1-3【中】派单说 `DEFAULT_DB_URL` 在 `tests/` 下「零命中」，实测是 2 条命中、0 条断言** — 生产状态

- **命令**：`git grep -n "DEFAULT_DB_URL" ad1d190 -- backend/tests`
- **输出**：2 条，都在 `tests/architecture/test_layering.py:22-23`，是 docstring 里引的
  **基线 offender 原文**（`from app.seed.generate import DEFAULT_CSV_DIR, DEFAULT_DB_URL`），
  **不是断言**。评审的实质判断（「`app/config.py` 的三个值没有非同源测试」）成立，
  只是「零命中」这个措辞不准。`test_config.py:6-9` 的 docstring 里按实测口径写的。
- 同类：派单说 M7 那两条断言「放哪个测试文件你定」。我选了**新建** `tests/test_config.py`
  而不是塞进 `tests/adapters/test_factory.py`——`DEFAULT_DB_URL` 与适配器毫无关系，
  塞进去会让「单一所有者」的口径变浑；且 `tests/` 顶层已有 `test_refdata.py` 这个同类
  形状（app 级模块一个文件）。

**C-fr1-4【中】派单给的 8 处行号在 `ad1d190` 上**仍然准**，但 `Read` 工具在这些区段仍系统性少 1** — 生产状态

- `ad1d190` 相对 `1df5e8a` 只改了 `Document/`（`git diff 1df5e8a..ad1d190 --stat` 只列
  计划文档），故评审在 `1df5e8a` 上量的 `backend/` 行号原样有效：本轮开工前逐个复核，
  `test_domain_purity.py:97-100`（`if level: return True`）、`:110-113`、`:196-201`、
  `test_layering.py:73-74`/`:81-82`/`:114`、`daily.py:201-203`/`:209`、
  `test_daily.py:642-644`、`config.py:35-36`、`test_models.py:589-604`、
  `mock_lepao.py:428`、`factory.py:50`、`percentile_stage.py:133`、`.gitignore:10`
  **全部命中**。
- 但 `Read` 工具给的行号在这些区段**少 1**（例：「保守侧」那句 `Read` 显示 202、
  `git grep -n` 给 **203**；`daily.py:209` 的「见任务报告」`Read` 显示 208）。
  硬规矩 #30/#37 又一次生效，本报告与所有落库行号一律取 shell 口径、绑定 `6a2938f`。

**C-fr1-5【中】编辑工具本轮把 3 个文件整体重写成裸 LF，与仓库其余 CRLF 不一致** — 生产状态

- **观测**：改完 7 个文件后按字节数 EOL，`backend/app/config.py`、
  `tests/architecture/test_layering.py`、`tests/test_config.py` 三个是
  **CRLF=0 / bareLF=52、182、30**，其余四个仍是纯 CRLF。`git diff` 也对此告警
  （`warning: in the working copy of 'backend/app/config.py', LF will be replaced by CRLF
  the next time Git touches it`）。
- **处置**：用 python 按字节 `b.replace(b"\n", b"\r\n")` 归一化回 CRLF（先 `assert`
  原文件 `CRLF == 0`，避免二次转换），归一化前后 **`git diff ad1d190 --numstat` 逐字相同**
  ——证明 blob 没变（`core.autocrlf=true`、这三个 `.py` 无 `.gitattributes` 覆盖，
  `git check-attr text eol` 三项全 `unspecified`），只是工作树与仓库其余部分对齐了。
  归一化后重跑 `-W error` 全量 → **479 passed**、重跑 #32 闸门 → **PASS**。
- **本轮没有出现上一轮那种「编辑工具报成功而磁盘未写」**（上一轮 26 次）。但按纪律每次
  编辑后都用 `git diff --numstat` + `git grep -n` 读回确认，7 个文件的改动**全部落盘**；
  本报告用 python 写、写完逐处 `assert` 出现次数恰为 1 再读回。

**C-fr1-6【低】`_package_of` / `_absolute` 在两个架构测试文件里各有一份（约 12 行重复）** — 自己重新推导

- 没抽公共模块，理由：① 抽出来要**新建文件**，而派单只授权「M7 可新建一个测试文件」；
  ② 两条守卫的判定语义不同（allow-list 白名单 vs `app.seed` 前缀黑名单），共用的只有
  「相对导入 → 绝对串」这 12 行；③ 两份各自带**自己那一条**守卫的实测口径 docstring，
  合并后那段散文会同时讲两件事。
- **若 Plan 02 后续再加第三条架构守卫**（例如 Task 9 要守「`app/api` 不得直接 import
  `app/db`」），第三份重复就不划算了，届时应抽到 `tests/architecture/_ast.py`。
  这里留个记号，不作为本轮的改动。

### fr1.9 本轮**没做**的事

- 没动 `app/db/models/organisation.py:69` 那处「已登记在任务报告的关切里」——派单明写
  本轮不改（Plan 01 原文搬运、已转延后 Minor）。
- 没给两个 CLI 的 `ArgumentParser` 加「schema 改了要重建库」提示（评审 M5，已转延后 Minor）。
- 没改 `min` 折叠本身、没改 `tested_on <= as_of`、没改任何断言期望值、没改
  `backend/app/seed/` 与 `backend/data/`（`git diff ad1d190..HEAD --stat` 对这两处为空）。
- 没提高 `test_layering.py` 的空转下界（8 → 17/24）。那会让一次合法重构变红，且派单
  与评审都认可 8；我只按 #39 把它的**能力边界**写清楚（见 fr1.5 的 M2 段）。
- 没把 `_package_of` / `_absolute` 抽成公共模块（见 C-fr1-6）。
- 没跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`
  （禁区）；fr1.4 的反例走内存库 + 直接调 `assessment_anchor`，fr1.5 的 M3 复跑走
  `tempfile.mkdtemp()` 下的独立 sqlite 文件，两者都不碰 `backend/pe.db` 与 `backend/data/seed/`。
---

## fix round 2

**派单**：Ruling 35 / 36 / 37 / 38 + Minor 1–4，共 8 项。四个文件：两个架构守卫的**辅助函数**
`_absolute` / `_imported_modules`（+ 它们自己的 docstring）、`test_models.py` 只改 docstring、
`daily.py` 只改 `:226` 那一个散文数字。
**基线** `6a2938f`（479 passed / 0 failed，`app/domain/` 分支覆盖 100%）。
**产出** 一个 commit **`1fa9941`**（不 push、不动 `main`），**479 passed / 0 failed —— 一字不变**：
本轮没有新增测试文件、也没有新增测试函数（合成树探针是**取证脚本**，不进 `tests/`，理由见 fr2.11）。

行号一律 **shell 口径**（python 读字节数行，不用 Read 工具——本轮又一次确认它在这个报告文件上
少行：Grep 看到 1512 行、Read 工具报「文件只有 1031 行」）。改前引用绑定 `6a2938f`、
改后引用绑定 `1fa9941`。四个文件的行数变化：

| 文件 | 改前 | 改后 | 字节 |
|---|---|---|---|
| `tests/architecture/test_domain_purity.py` | 365 | **458** | 22125 → 29846 |
| `tests/architecture/test_layering.py` | 182 | **228** | 10768 → 14461 |
| `tests/db/test_models.py` | 720 | **721** | 41330 → 41478 |
| `app/pipeline/daily.py` | 809 | **810** | 47659 → 47761 |

`git diff 6a2938f..HEAD --stat` = **4 文件 / +174 / −33**。

### fr2.0 闸门（全部亲跑，命令逐字给出）

| 闸门 | 命令 | 结果 |
|---|---|---|
| 全量测试 | `cd backend; python -m pytest -q` | **479 passed in 53.96s**，0 failed（与基线一字不变） |
| domain 分支覆盖 | `cd backend; python -m pytest -q --cov=app/domain --cov-branch --cov-report=term-missing` | `TOTAL **399** stmts / Miss **0** / **114** branch / BrPart **0** / **100%**`；同一次跑 `478 passed, 1 skipped in 112.60s`（那条 skip 是 `test_backfill_500_students_under_60_seconds` 在 `--cov` 下的既有自我跳过，非本轮引入） |
| 架构守卫单跑 | `cd backend; python -m pytest tests/architecture -q -W error` | **4 passed in 0.07s**，0 error |
| 硬规矩 #32（剥 docstring 比 `ast.dump`，三组对照） | `python fr2_probes/pe_fr2_rule32.py <仓库根>` | **PASS**，见 fr2.7 |
| 硬规矩 #51（两份重复守卫都改了） | `python fr2_probes/pe_fr2_rule51.py <仓库根>` | **PASS**，见 fr2.6 |
| 断言未变（逐顶层单元 AST 对比） | `python fr2_probes/pe_fr2_astdiff.py <仓库根>` | **PASS**，见 fr2.7 |
| 合成树端到端 + 对拍矩阵 + G1/G2/G3 表 | `python fr2_probes/pe_fr2_probe.py <仓库根> baseline` / `… work` | 改前 **10/15**、改后 **15/15**；对拍 DIFF **7/15 → 0/15**，见 fr2.1 / fr2.2 |

禁区与行尾（`python fr2_probes/pe_fr2_zones.py <仓库根>`，直接读字节、不走 PowerShell 管道）：

```
backend/pe.db exists: False
backend/data/seed/ 下的条目数: 0
csv bytes=21412 sha256[:16]=D2C8E539E2FA0029 CRLF=0
app/pipeline/daily.py                      bytes=47761  CRLF=810  裸LF=0  BOM=False  乱码=False
tests/db/test_models.py                    bytes=41478  CRLF=721  裸LF=0  BOM=False  乱码=False
tests/architecture/test_domain_purity.py   bytes=29846  CRLF=458  裸LF=0  BOM=False  乱码=False
tests/architecture/test_layering.py        bytes=14461  CRLF=228  裸LF=0  BOM=False  乱码=False
```

`git diff 6a2938f..HEAD --stat -- backend/app/seed/ backend/data/ .gitattributes Document/
backend/app/db/models/ backend/app/domain/` → **空**（本轮连碰都没碰这些路径，
`config.py` / `adapters/` / `refdata.py` 同样零改动）。收工时 `git status --short` → **0 行**，
`git log --oneline -2` = `1fa9941` 一个 commit 在 `6a2938f` 之上。

合成树探针跑在 `tempfile.mkdtemp(prefix="pe_fr2_")` 下、`finally` 里 `shutil.rmtree`，
不落仓库、不碰 `backend/pe.db` 与 `backend/data/seed/`——上面的禁区复核就是跑完之后取的。

### fr2.1 Ruling 35 — `_absolute()` 的负数切片造成假绿 ✅

**改法**（两个文件各一份，**两份都改**，见 fr2.6）：在切片之前加一行

```python
    if level - 1 > len(package):
        # 越界档：不设这一行，负数切片会从尾部切出非空 anchor、把越界折成更浅的错误绝对串
        return None
```

原来的 `anchor = package[: len(package) - (level - 1)]` 与 `if not anchor: return None` 都保留
（`level - 1 == len(package)` 那一档由 `not anchor` 兜住，`>` 那一档由新行兜住）。

**验收判据（派单点名的两例，改前 GREEN → 改后必须 RED）——合成树端到端实跑**
（`pe_fr2_probe.py <仓库根> baseline` / `… work`；树建在 `$env:TEMP` 下、形状与 `backend/app`
相同，21 个 `.py`，满足 purity 的 `>= 5` 与 layering 的 `>= 8` 两个空转下界；每个用例前把
5 个探针槽全部重置成 `PASS = 1` 以免串味；守卫模块用 `importlib` 从源码加载、
`DOMAIN` / `BACKEND` / `APP` 重定向到合成树，然后调用测试函数本体）：

改**前**（守卫取自 `git show 6a2938f:…`，不落盘、不 checkout）：

```
!! [layering] app/db/models/probe.py   from .....seed import generate   want=RED   got=GREEN
!! [purity  ] app/domain/probe.py      from ....domain import tables    want=RED   got=GREEN
```

改**后**（守卫取自工作树）：

```
OK [layering] app/db/models/probe.py   from .....seed import generate   want=RED   got=RED
     offender: 生产层依赖了仿真数据生成器 app.seed（spec §3.3 依赖方向单向不可逆）：
               app/db/models/probe.py:1: 相对导入上溯到顶层包 app 之外
OK [purity  ] app/domain/probe.py      from ....domain import tables    want=RED   got=RED
     offender: app/domain 是叶子层，import 必须落在白名单内（[…] + app.domain.*）：
               probe.py:1: ....domain → <上溯到顶层包 app 之外>
```

**折算值的直接调用取证**（`pe_fr2_last.py`，基线 `_absolute` 三个入参、改后四个，按签名兼容调用）：

```
from .....seed import generate     改前='app.db.seed'          改后=None
from .....seed.generate import X   改前='app.db.seed.generate' 改后=None
from ....domain import tables      改前='app.domain'           改后=None
```

`resolve_name` 对这两个输入都抛异常（本机 Python 3.11.1 实跑）：

```
resolve_name('....domain'      , 'app.domain'   ) = ImportError: attempted relative import beyond top-level package
resolve_name('.....seed.generate','app.db.models') = ImportError: attempted relative import beyond top-level package
```

⚠️ 第一行的折算串**依赖 `module` 的形状**：`from .....seed import generate` 的 `module` 是
`"seed"`（`generate` 在 `names` 里），故折成 `app.db.seed`，与派单一致；若写成
`from .....seed.generate import X`（`module="seed.generate"`）则折成 `app.db.seed.generate`。
两者都不以 `app.seed` 开头 → 改前都假绿，改后都返回 `None` → 都判 offender，判据不受影响。
我第一版对拍矩阵里把这一行的标签写成了 `from .....seed import generate` 而实际传的是
`module="seed.generate"`，已重跑并把两种形状分开列（见上）。

**对拍矩阵**（15 格，`_absolute` vs `importlib.util.resolve_name`，两个文件各调一次并 assert
两份返回值相同）：改前 **DIFF 7 / 15**，其中 Ruling 35 那两格是

```
DIFF from .....seed.generate import X  @ app.db.models  _absolute='app.db.seed.generate'  resolve_name=ImportError
DIFF from ....domain.tables import X   @ app.domain     _absolute='app.domain.tables'     resolve_name=ImportError
```

改后 **DIFF 0 / 15**（全表见 fr2.2）。

### fr2.2 Ruling 36 — `_absolute()` 忽略 `node.names` ✅

**改法**（两个文件各一份）：

1. `_absolute` 增第 4 个入参 `name: str = ""`，末尾由 `".".join(anchor + ((module,) if module else ()))`
   改成 `tail = module or name` → `".".join(anchor + ((tail,) if tail else ()))`；
2. `_imported_modules` 在 `node.level and not node.module` 这一档**逐个 `node.names` yield**
   （派单点出的关键：一个 `ImportFrom` 节点原来只 yield 一条，而 `from .. import seed, pipeline`
   导入的是两个模块）；
3. purity 侧的 `_imported_modules` 由 3 元组改成 4 元组（第 4 项 = 被导入名），
   调用点 `test_domain_imports_stay_within_the_allow_list` 跟着解包 4 个值并把 `name` 传下去
   ——**这是那个测试函数里唯一的 AST 改动，它的那条 `assert offenders == []` 逐字未动**（fr2.7）。

**验收判据（按 Ruling 41 校正后的四行表，逐行实跑）**：

| 形状 | `resolve_name` 正确答案（我实跑） | 改前折算 | 改前判定 | 改后折算 | 改后判定 |
|---|---|---|---|---|---|
| `from .. import seed` @ `app/pipeline` | `resolve_name("..seed","app.pipeline")` = `'app.seed'` | `'app'` | GREEN（**假绿**） | `'app.seed'` | **RED** ✅ |
| `from .. import seed` @ `app/db` | `resolve_name("..seed","app.db")` = `'app.seed'` | `'app'` | GREEN（**假绿**） | `'app.seed'` | **RED** ✅ |
| `from .. import seed` @ `app/db/models` | `resolve_name("..seed","app.db.models")` = `'app.db.seed'` | `'app.db'` | GREEN（**判定本来就对**，只是折算串错） | `'app.db.seed'` | **仍 GREEN** ✅ |
| `from .. import seed, pipeline` @ `app/pipeline` | `'app.seed'` / `'app.pipeline'` 两个 | 一条：`'app'` | GREEN（**假绿**） | **两条**：`'app.seed'`, `'app.pipeline'` | `app.seed` 那条 **RED** ✅ |

第三行按派单的明确要求**用直接调用 `_absolute` 断言返回值**、不靠守卫颜色：

```
改前：_absolute('', 2, ('app','db','models'), 'seed') = 'app.db'     == 'app.db.seed'? False
改后：_absolute('', 2, ('app','db','models'), 'seed') = 'app.db.seed' == 'app.db.seed'? True
```

第四行的 yield 条数（合成树里对同一份源码 `from .. import seed, pipeline` 直接调
`_imported_modules`）：

```
改前：layering 侧 yield 1 条: [(1, 'app')]
      purity   侧 yield 1 条(原始) → 折算 [(1, 'app')]
改后：layering 侧 yield 2 条: [(1, 'app.seed'), (1, 'app.pipeline')]
      purity   侧 yield 2 条(原始) → 折算 [(1, 'app.seed'), (1, 'app.pipeline')]
      resolve_name 正确答案: 'app.seed' / 'app.pipeline'
```

端到端（改后）：

```
OK [layering] app/pipeline/probe.py    from .. import seed              want=RED   got=RED
     offender: …app/pipeline/probe.py:1: app.seed
OK [layering] app/db/probe.py          from .. import seed              want=RED   got=RED
     offender: …app/db/probe.py:1: app.seed
OK [layering] app/db/models/probe.py   from .. import seed              want=GREEN got=GREEN
OK [layering] app/pipeline/probe.py    from .. import seed, pipeline    want=RED   got=RED
     offender: …app/pipeline/probe.py:1: app.seed
OK [purity  ] app/domain/probe.py      from .. import seed              want=RED   got=RED
     offender: …probe.py:1: .. → app.seed      ← 改前这一行是「.. → app」，折算串也跟着修对了
```

**改后的完整对拍矩阵（DIFF 0 / 15）**：

```
OK from .. import seed              @ app.pipeline    _absolute='app.seed'                resolve_name='app.seed'
OK from .. import seed              @ app.db          _absolute='app.seed'                resolve_name='app.seed'
OK from .. import seed              @ app.db.models   _absolute='app.db.seed'             resolve_name='app.db.seed'
OK from .. import pipeline          @ app.domain      _absolute='app.pipeline'            resolve_name='app.pipeline'
OK from . import tables             @ app.domain      _absolute='app.domain.tables'       resolve_name='app.domain.tables'
OK from ._shared import X           @ app.db.models   _absolute='app.db.models._shared'   resolve_name='app.db.models._shared'
OK from ..seed import X             @ app.domain      _absolute='app.seed'                resolve_name='app.seed'
OK from ..seed.generate import X    @ app.domain      _absolute='app.seed.generate'       resolve_name='app.seed.generate'
OK from ...seed.generate import X   @ app.db.models   _absolute='app.seed.generate'       resolve_name='app.seed.generate'
OK from .....seed.generate import X @ app.db.models   _absolute=None                      resolve_name=ImportError
OK from ....domain.tables import X  @ app.domain      _absolute=None                      resolve_name=ImportError
OK from ...seed import X            @ app.domain      _absolute=None                      resolve_name=ImportError
OK from ..seed import X             @ app.domain.sub  _absolute='app.domain.seed'         resolve_name='app.domain.seed'
OK from ...seed import X            @ app.domain.sub  _absolute='app.seed'                resolve_name='app.seed'
OK from .clean import X             @ app.pipeline    _absolute='app.pipeline.clean'      resolve_name='app.pipeline.clean'
---- 对拍 DIFF 格数 = 0 / 15
```

改前同一张表是 **DIFF 7 / 15**：上表第 1–5 行（Ruling 36 那一族，其中第 5 行
`from . import tables` @ `app/domain` 是我这轮**新查到的一格**，派单与账本都没列：改前折成
`'app.domain'`、正确答案是 `'app.domain.tables'`，两侧都合法故判定不变）+ 第 10、11 行
（Ruling 35 那一族）。

**回归：真仓那 12 条 `level == 1` 相对导入改后仍全绿**（数它们的命令就写在
`test_layering.py:152` 的 docstring 里，本轮亲跑）：

```
真仓 ImportFrom(level>0) 节点数 = 12（其中 module 为空的 = 1）
   module 为空的那条: ('…/backend/app/db/models/__init__.py', 74, 1, None, ['feedback', 'prescription'])
改前：真仓相对导入折算出 12 条，offender = 0
改后：真仓相对导入折算出 13 条，offender = 0
     app/db/models/__init__.py :62  -> 'app.db.models._shared'
     app/db/models/__init__.py :66  -> 'app.db.models._shared'
     app/db/models/__init__.py :67  -> 'app.db.models.organisation'
     app/db/models/__init__.py :68  -> 'app.db.models.assessment'
     app/db/models/__init__.py :69  -> 'app.db.models.derived'
     app/db/models/__init__.py :70  -> 'app.db.models.ops'
     app/db/models/__init__.py :74  -> 'app.db.models.feedback'        ← 改前这一条只 yield 一行
     app/db/models/__init__.py :74  -> 'app.db.models.prescription'    ←  'app.db.models'
     app/db/models/assessment.py :21 -> 'app.db.models._shared'
     app/db/models/derived.py   :25 -> 'app.db.models._shared'
     app/db/models/derived.py   :26 -> 'app.db.models.organisation'
     app/db/models/ops.py       :23 -> 'app.db.models._shared'
     app/db/models/organisation.py :22 -> 'app.db.models._shared'
守卫实际扫描面（SCANNED_DIRS = pipeline / db / domain）共 yield 127 条，offender = 0
```

即：**12 条节点、13 条折算**（`:74` 那条一个节点两个名字，现在展开成两条），全部不以
`app.seed` 开头、全部仍绿。这一条真仓实例已写进 `test_layering.py:154-159` 的 docstring。

⚠️ 一个探针脚本自身的坑（不是仓库问题，记下以免下一个人误判）：我第一版把 `backend/app`
**全部**目录都扫了一遍，数出 12 个「offender」——它们全在 `app/seed/` 内部
（`app/seed/generate.py` import `app.seed.config` 一类，12 条），而守卫的 `SCANNED_DIRS`
只有 `pipeline` / `db` / `domain`，本来就不扫 `app/seed/`。限定到守卫的真实扫描面后
offender = 0（上面那行）。

### fr2.3 Ruling 37 — 两处 `resolve_name` 举例是假的 ✅

**改法**：`test_domain_purity.py:118`（改后 `:129-140`）的 `"app.domain.ind"` → `"app.domain"`；
`test_layering.py:84-85`（改后 `:84-93`）的 `"app.db.models.organisation"` → `"app.db.models"`。
两处都**不只换一个字符串**，而是把「对的那行 + 错的那行」并排印出来、标明第二参数是
`__package__`（包名），并写清「按假举例去对齐 `_package_of` 会让守卫假绿」的因果。

**我亲跑的输出**（`pe_fr2_probe.py` §A 与 `pe_fr2_claims.py` §③，本机 Python 3.11.1；
按硬规矩 #52，写进 docstring 的每一行都是这里跑出来的，不是照抄派单）：

```
resolve_name('..seed.generate'   , 'app.domain.ind'            ) = 'app.domain.seed.generate'   # 改前 purity:118 写的 → MISMATCH
resolve_name('...seed.generate'  , 'app.db.models.organisation') = 'app.db.seed.generate'       # 改前 layering:84-85 写的 → MISMATCH
resolve_name('..seed.generate'   , 'app.domain'                ) = 'app.seed.generate'          # 改成包名之后 → MATCH
resolve_name('...seed.generate'  , 'app.db.models'             ) = 'app.seed.generate'          # 改成包名之后 → MATCH
resolve_name('..seed'            , 'app.db.models'             ) = 'app.db.seed'                # Ruling 41 第三行的正确答案
resolve_name('..seed'            , 'app.pipeline'              ) = 'app.seed'
resolve_name('....domain.tables' , 'app.domain'                ) = ImportError: attempted relative import beyond top-level package
resolve_name('.....seed.generate', 'app.db.models'             ) = ImportError: attempted relative import beyond top-level package
```

与派单给的四行**逐字相同**（我独立跑的，不是抄的）。

### fr2.4 Ruling 38 — 「拿到这些对象的唯一途径是 import」是假的 ✅

**改法两条都做了**：

1. `test_domain_purity.py` 的 `_dotted` docstring（改前 `:246-251`、改后 `:295-309`）：删掉
   「唯一途径是 import」这个全称断言，改成实测口径——「凡 `_dotted` 还原不出点号串的调用形态，
   一律不被本守卫覆盖，与那个对象是怎么拿到的无关」，并把反例的机制写全（`__import__` 是内置名、
   G1 只匹配 `ast.Import` / `ast.ImportFrom`）。
2. 落点是**已有的那张 G1/G2/G3 三列表**（改前 `:286-293`、改后 `:344-358`），**加了 7 个新行**
   （派单要求 5 行，我把复审列出的另两行也补上，凑成完整的一族），颜色全部本机亲跑；
   并在表下加一句「第 1–7 行是 fix round 1 那次跑的结果，第 8–14 行是 fix round 2 新增；
   本轮把 14 行全部重跑了一遍，前 7 行的颜色逐字复现」。

**实跑的表**（`pe_fr2_probe.py` §C2；改前/改后跑出来**逐字相同**，因为本轮没动 G2/G3 的逻辑）：

```
probe.py 的内容                                         G1     G2     G3      说明
_f = open ⏎ _f('x')                                    GREEN  GREEN  GREEN   既有表第 1 行
def reopen(): ⏎     return 1 ⏎ reopen()                GREEN  GREEN  GREEN   既有表第 2 行
def open_ended(): ⏎     return 1 ⏎ open_ended()        GREEN  GREEN  GREEN   既有表第 3 行
"""不要用 datetime.now()，也不要 open("""               GREEN  GREEN  GREEN   既有表第 4 行
open('x')                                              GREEN  RED    GREEN   既有表第 5 行
import builtins ⏎ builtins.open('x')                   RED    RED    GREEN   既有表第 6 行
import datetime as dt ⏎ dt.datetime.now()              RED    RED    GREEN   既有表第 7 行
__import__("datetime").datetime.now()                  GREEN  GREEN  GREEN   ← 新增 8
__import__("os").listdir(".")                          GREEN  GREEN  GREEN   ← 新增 9
__import__("builtins").open("x")                       GREEN  GREEN  GREEN   ← 新增 10
getattr(__import__("datetime"), "datetime").now()      GREEN  GREEN  GREEN   ← 新增 11
eval("__import__('datetime').datetime.now()")          GREEN  GREEN  GREEN   ← 新增 12
def _f(x): ⏎     return getattr(x, "now")()            GREEN  GREEN  GREEN   ← 新增 13
def _f(table): ⏎     return table[0]()                 GREEN  GREEN  GREEN   ← 新增 14
```

**harness 自检**：前 7 行的颜色与 `6a2938f` 上那张表**逐字相同**（`GREEN×4` /
`GREEN RED GREEN` / `RED RED GREEN` ×2），说明我这个合成树 harness 量的就是上一轮那把尺子。

新写进表的 ⚠️ 段（改后 `:380-397`）除了这一族，还补了一条实证的量化对比：

```
探针 '__import__("os").listdir(".")'   命中的 FORBIDDEN_IO 子串 = []            ← 0 个
探针 'import os\nos.listdir(".")'      命中的 FORBIDDEN_IO 子串 = ['import os', 'os.listdir']  ← 2 个
```

即 `os.listdir` 与 `import os` **两个子串都在** `FORBIDDEN_IO` 里，写成 `__import__("os").listdir(".")`
之后源码里一个都不出现——第三条子串守卫也一声不响，「不许读盘」这条立意被完整绕过。

### fr2.5 Minor 1–4 ✅

**Minor 1（`test_layering.py:172` → 改后 `:215-218`）「仍剩 13…17」→「13…18」**，并把三个减式
就地写出来。我亲跑的计数（派单给的那条 Counter 命令，在仓库根跑）：

```
per-dir: [('db', 11), ('domain', 6), ('pipeline', 7)] total: 24
  搬空 db       -> 仍剩 13
  搬空 domain   -> 仍剩 18
  搬空 pipeline -> 仍剩 17
```

与派单逐字相同，正确区间 **13…18**。

**Minor 2（`test_models.py:600` + `:594`）**：`:600` 就地补「——⚠️ **这个方向不可复现**，是机器/
负载噪声，四次连跑的值见下方「复跑」那一段」；`:594` 表头标签 `单次墙钟中位 (ms)` →
`单次墙钟中位 (ms，单次采样、方向不可复现)`。**一个数都没删**（0.2708 / 0.2941 / 1.086 /
min…max 两对区间 / 5 423 104 / 6 791 168 / +1 368 064 B / +25.23% 全部原样保留）。
⚠️ 派单说「`:594-596` 表头那两个点值」、账本 Ruling 39-2 说「`:595-596`」，实测**两个点值在
`:596` 与 `:597`**、标签在 `:594`（见 fr2.8）。我没重排表格，只改了标签那一行。

**Minor 3（`test_domain_purity.py:196-199` → 改后 `:237-248`）**：把主语与结论对齐到同一个
文件深度，改成两条带主语的 bullet：

* **扁平的** `app/domain/x.py`（包深 2）：`from ..seed import generate` → `app.seed.generate`
  → **offender**；`from ...seed import generate` 已越界 → `None` → **同样 offender**。
* `app/domain/sub/x.py`（包深 3）：`from ..tables import X` → `app.domain.tables` → **合法**；
  **同一句** `from ..seed import generate` 在这个深度折成 `app.domain.seed.generate`、命中白名单
  → **不是 offender**；那一档要到 `app.seed` 得写 `from ...seed import generate`（`level == 3`）。

四条颜色都是合成树实跑的（`pe_fr2_probe.py` §C）：

```
OK [purity] app/domain/probe.py      from ..seed import generate      want=RED   got=RED
OK [purity] app/domain/sub/probe.py  from ..seed import generate      want=GREEN got=GREEN
OK [purity] app/domain/sub/probe.py  from ...seed import generate     want=RED   got=RED
OK [purity] app/domain/sub/probe.py  from ..tables import X           want=GREEN got=GREEN
```

改完把 Ruling 28 那整段论证（改后 `:230-248`）重读了一遍：论证仍然通，而且比原来更有力——
它现在同时给出了「子包 level 2 合法」（Ruling 28 的立意）与「同一句在更深一层就不指向
`app.seed`」这个边界，正是 Ruling 28 当初要说明的「不能用常数档」。

**Minor 4（`daily.py:226`，本轮唯一一处生产文件改动）**：`组内极差 0.38 s` →
`组内极差 20.85 − 20.48 = 0.37 s；两个样本各自只记到百分位，故极差也只能给到这个精度`。
选了派单给的第二条路（直接写 0.37）+ 把减式印出来，这样这个数**从同一行就能算出来**
（硬规矩 #19）。我核过同行的其它数：均值 `(20.48+20.85)/2 = 20.665` → 20.66 ✓；
`:227-228` 的 `21.18 − 20.89 = 0.29` ✓、均值 `21.035` → 21.03 ✓、差 `21.03 − 20.66 = 0.37` ✓、
`0.37 / 20.66 = 1.79%` → +1.8% ✓、`60 / 21.18 = 2.833` → 2.83× ✓，**那半句一个字没动**。
`:226` 新出现的 0.37 与 `:228` 原有的「差 +0.37 s」是**两个不同的量**（前者是基线组内极差、
后者是两组均值之差），数值巧合相同，标签不同、不会混。

### fr2.6 硬规矩 #51 — 两份重复守卫，改了几份

`git grep -n -E "def (_absolute|_package_of)" -- backend` 的**全部**命中：

```
backend/tests/architecture/test_domain_purity.py:114:def _package_of(py: pathlib.Path) -> tuple[str, ...]:
backend/tests/architecture/test_domain_purity.py:125:def _absolute(module: str, level: int, package: tuple[str, ...], name: str = "") -> str | None:
backend/tests/architecture/test_layering.py:70:def _package_of(py: pathlib.Path) -> tuple[str, ...]:
backend/tests/architecture/test_layering.py:81:def _absolute(module: str, level: int, package: tuple[str, ...], name: str = "") -> str | None:
合计 4 处定义
```

**`_absolute` 全仓 2 份，两份都改了**（`_package_of` 也是 2 份，本轮**没改**它，但一并核了）。
不止是「都改了」，还核了**两份改完仍然逐字相同**（`pe_fr2_rule51.py`，剥掉 docstring 后比
函数体 AST）：

```
_package_of    份数=2  签名=['py']                             函数体 AST 逐字相同=True
_absolute      份数=2  签名=['module','level','package','name'] 函数体 AST 逐字相同=True
```

以及 7 项关键点在两份里都在（负数切片守卫 / `name` 入参 / `tail = module or name` /
逐个 `names` / 假举例已删 / 旧的 `ValueError` 说法已删 / 原切片行保留），两份全 OK；
两条旧的假举例串在两个文件里都已彻底消失（脚本里 assert 过命中数为 0）。

### fr2.7 硬规矩 #32 闸门（三组对照）+ 改动面钉死

`pe_fr2_rule32.py`：把两侧**所有 docstring**（模块/类/函数首条字符串表达式）就地换成
`ast.Pass()`，再比 `ast.dump(include_attributes=False)`；注释本来就不进 AST。基线用
`git show 6a2938f:<path>` 取（**不落盘、不 checkout**，避开硬规矩 #46）；两侧一律 CRLF→LF
归一化后再解析。

```
=== ① 本轮 4 个文件：工作树 vs 基线 6a2938f ===
  OK backend/app/pipeline/daily.py                        不剥docstring相等=False 剥掉后相等=True （本轮期望 True）
  OK backend/tests/db/test_models.py                      不剥docstring相等=False 剥掉后相等=True （本轮期望 True）
  OK backend/tests/architecture/test_domain_purity.py     不剥docstring相等=False 剥掉后相等=False（本轮期望 False）
  OK backend/tests/architecture/test_layering.py          不剥docstring相等=False 剥掉后相等=False（本轮期望 False）

=== ② 对照组 A：往基线注入 3 个真语义变异，尺子必须判『不相等』（抓到）===
  抓到 backend/app/pipeline/daily.py                     把 test_date 的 min 折叠改成 max（:251）
  抓到 backend/tests/db/test_models.py                   把查询计划断言的 not in 改成 in（:709）
  抓到 backend/tests/architecture/test_domain_purity.py  把空转守卫的下界 5 改成 4（:87）

=== ③ 对照组 B：往基线只注入 docstring 改动，尺子必须判『相等』（证明它真的剥了 docstring）===
  判相等 backend/app/pipeline/daily.py       只改 docstring（散文里的一个数字）→ 剥掉后相等=True
  判相等 backend/tests/db/test_models.py     只改 docstring（表头标签）→ 剥掉后相等=True

=== ④ 对照组 C：基线跟自己比，尺子必须判『相等』（证明它不是恒 False）===
  self-equal(4 个文件) = True / True / True / True

闸门结论: PASS
```

比派单要求的「3 个真语义变异 + 自比」多了一组（③ docstring-only 变异判相等）：只有 ② 与 ④
还不能排除「尺子对这两个文件恰好恒 True」，③ 直接证明它剥得掉 docstring。
② 的三条变异分别打在「本轮唯一被允许改语义的地方之外的承重逻辑」（`min` 折叠）、
「M3 那条查询计划断言」与「purity 的空转下界」上。

**改动面钉死**（`pe_fr2_astdiff.py`，逐顶层单元比剥 docstring 后的 AST）：

```
=== backend/tests/architecture/test_domain_purity.py ===
   未动      _domain_files          未动  _assert_not_empty
   AST 变了  _imported_modules      ← Ruling 36（yield 4 元组 + 逐个 names）
   未动      _package_of
   AST 变了  _absolute              ← Ruling 35 + 36
   未动      _is_allowed
   AST 变了  test_domain_imports_stay_within_the_allow_list  ← 只是调用点解包 4 个值
   未动      _dotted                未动  _hit_forbidden_call
   未动      test_domain_has_no_clock_or_file_access
   未动      test_domain_has_no_filesystem_access
   未动      <module-level>         ← ALLOWED_MODULES / ALLOWED_PACKAGE / FORBIDDEN_CALLS / FORBIDDEN_IO 全未动
=== backend/tests/architecture/test_layering.py ===
   未动      _py_files   未动 _package_of
   AST 变了  _absolute            ← Ruling 35 + 36
   AST 变了  _imported_modules    ← Ruling 36
   未动      _is_forbidden
   未动      test_production_layers_never_import_app_seed
   未动      <module-level>       ← SCANNED_DIRS / FORBIDDEN_PREFIX 全未动

=== 4 个 test_* 函数体里的 assert 语句逐字对比（剥 docstring 后）===
   test_domain_imports_stay_within_the_allow_list    assert 条数 1→1  逐字相同=True
   test_domain_has_no_clock_or_file_access           assert 条数 1→1  逐字相同=True
   test_domain_has_no_filesystem_access              assert 条数 1→1  逐字相同=True
   test_production_layers_never_import_app_seed      assert 条数 2→2  逐字相同=True
断言未变闸门: PASS
```

即：**5 条 assert 逐字未动**，`test_domain_imports_stay_within_the_allow_list` 里唯一的 AST 改动
是 `for lineno, module, level, name in …` 这个解包与把 `name` 传给 `_absolute`——派单在
Ruling 36 里明写了「purity 侧的对应调用点同样要改」，这是它的必然波及面，不是断言行为改动。
测试通过/失败状态的变化**全部**落在派单各条验收判据上（fr2.1 两例转红、fr2.2 三例转红 +
一例保持绿），**没有计划外的红**（全量 479 passed 就是这条的总账）。

### fr2.8 我发现的派单错误（4 条）

按派单 §4.7 的要求逐条给出实测证据。**没有一条导致判据不可满足**，8 项我全部按派单做了；
第 1、2 条是事实/机制层面的偏差，第 3、4 条是位置与措辞。

**① Ruling 35 第二例的机制描述差一支：改前折成的 `app.domain` 命中的是白名单的「相等」那一支，
不是「前缀 `app.domain.`」那一支。**

派单原话：「改前折成 `app.domain`、**命中白名单前缀 `app.domain.` → 真绿**」（账本 Ruling 35
同一处措辞：「还落在白名单前缀 `app.domain.` 内」）。`_is_allowed` 有两支
（`test_domain_purity.py`，改前 `:143-145`）：`module == ALLOWED_PACKAGE` **或**
`module.startswith(ALLOWED_PACKAGE + ".")`。本机实跑：

```
_is_allowed('app.domain')          = True
== ALLOWED_PACKAGE（相等那一支）    = True
startswith(ALLOWED_PACKAGE + '.')  = False      ← 前缀那一支并不命中
_is_allowed('app.domain.seed')     = True       （这一支才是前缀）
```

**结论「真绿」完全正确**，改后也确实转红（fr2.1）；只是机制是「相等」而不是「前缀」。
之所以值得记：这两支的**覆盖面不同**——「前缀」那一支是 `app.domain.<任何子模块>`，
「相等」那一支只有 `app.domain` 自己。谁要按「前缀」这个描述去推理「折成 `app.domain`
说明它把某个子模块当成了目标」，就会推错。我在改后的 docstring 里写的是「命中白名单前缀
``app.domain.`` 变成真绿」——**照抄了派单的措辞，现在看这一句同样不够准**，但它是散文里的
因果描述、且结论正确，我没有再为它多改一次盘（见 fr2.10 的关切 C-fr2-2）。

**② Minor 2 的行号：两个点值在 `:596` 与 `:597`，不在派单写的「`:594-596`」里。**

`6a2938f` 上实测（shell 口径）：`:593`/`:595`/`:598` 是三条 `====` 框线，`:594` 是表头
（`场景 | 单次墙钟中位 (ms) | .db 字节 | EXPLAIN QUERY PLAN`），`:596` 是 A 行（含 `0.2708`），
`:597` 是 B 行（含 `0.2941`）。账本 Ruling 39-2 写的是「`:595-596` 表头那两个点值」——
`:595` 是框线、不是表头。**标签在 `:594`、点值在 `:596`/`:597`**。我按标签在 `:594` 改
（派单要的正是改标签），两个点值一个没删。

**③ 派单 §1 说硬规矩 #48–#52「散在」progress.md 的最后三节里；实测 #48/#49/#50 都在最后三节之外。**

`progress.md` 共 448 行，最后三节从 `:333`（`#### Task 1 fix round 1 — 范围内复审`）起。
实测位置：**#48 在 `:172`**、**#49 在 `:265`**、**#50 在 `:290`**、#51 在 `:409`、#52 在 `:411`。
即只有 #51/#52 在最后三节内。不影响执行（我把 `:165-180`、`:262-292`、`:330-448` 都读了），
但「重点读最后三节」这个指引若被下一个人照字面执行，会漏掉 #48（派单前必须验工作树干净）、
#49（预检要核「计划 vs 既有代码」）与 #50（守卫必须同时构造红/绿两个输入）——
**#50 恰好是本轮 fr2.1/fr2.2 验收表的形状依据**。

**④ Ruling 35 第一例「改前折成 `app.db.seed`」只对 `module="seed"` 成立，派单没标这个前提。**

`from .....seed import generate` 的 AST 是 `module="seed"`、`names=["generate"]`，折成
`app.db.seed` ✓（与派单一致）；而 `from .....seed.generate import X`（`module="seed.generate"`）
折成 `app.db.seed.generate`。两者都不以 `app.seed` 开头 → 改前都假绿、改后都 `None` → 判据
不受影响，**派单那条判据是可满足的、我按字面跑通了**。记下来的原因是我自己先踩了这个坑：
第一版对拍矩阵里那一行的标签写着 `from .....seed import generate` 而传的是
`module="seed.generate"`，标签与输入不一致；已把两种形状分开重跑（fr2.1）。
这与 Ruling 41（控制者错误 #67）是**同一个错误类型**——「归纳/转述时把具体输入的形状丢掉」，
只是这次它没有变成一条不可满足的判据。

### fr2.9 超出派单 8 项的改动（主动披露，共 4 处，全部是散文）

1. **两个守卫的 docstring 都写「Python 运行时会抛 `ValueError: attempted relative import
   beyond top-level package`」——本机 Python 3.11.1 实跑抛的是 `ImportError`**（消息文本相同）。
   取证：在 `$env:TEMP` 下造一个真包（`app/__init__.py` + `app/domain/__init__.py` +
   `app/domain/x.py` 内容为 `from ...seed import generate`），`import app.domain.x` 的 stderr 末行：

   ```
   ImportError: attempted relative import beyond top-level package
   returncode = 1        python -V: Python 3.11.1
   ```

   `resolve_name` 对同一输入也抛 `ImportError`（fr2.1）。两处都改成 `ImportError` 并写明是
   「合成树里真跑一遍 `import app.domain.x` 的实测」。**这是硬规矩 #52 的直接适用**：一个
   长得像可执行断言的异常名，没人跑过就写进了两个文件。它在派单点名的段落里（Ruling 35 的
   修法就在那三行旁边），不改就等于本轮只修了一半的假断言。
2. **`_dotted` docstring 里我第一版写的 AST 形状自己有一处不准，落盘后核出来改掉了**：
   `__import__("datetime").datetime.now()` 的 `node.func` 是
   `ast.Attribute(value=ast.Attribute(value=ast.Call))`（我第一版写成
   `ast.Attribute(value=ast.Call)`，那其实是 `__import__("os").listdir(".")` 的形状）；
   而 `eval("…")` 是**另一种**放过法——它的 `node.func` 是 `ast.Name(id="eval")`、点号串
   **还原得出** `"eval"`，只是 `eval` 不在 `FORBIDDEN_CALLS` 里，并非「还原不出来」。实跑：

   ```
   f()()                                   node.func = ast.Call
   table[0]()                              node.func = ast.Subscript
   getattr(x, "now")()                     node.func = ast.Call
   __import__("datetime").datetime.now()   node.func = ast.Attribute(value=ast.Attribute(value=ast.Call))
   __import__("os").listdir(".")           node.func = ast.Attribute(value=ast.Call)
   eval("...")                             node.func = ast.Name
   ```

   改后的 `:295-305` 印的就是这张实跑表。**披露的理由**：这正是本轮要消灭的错误形态
   （Ruling 37 / 硬规矩 #52），我自己第一版就犯了一次，靠「写完再跑一遍」抓住。
3. **`test_layering.py:154-159` 新增一段**：指出真仓那 12 条里有 **1 条**正是 `module` 为空的
   形状（`app/db/models/__init__.py:74` 的 `from . import feedback, prescription`），改后
   yield 两条。派单只要求「回归 12 条仍全绿」，但这条真仓实例是 Ruling 36 在**本仓唯一**的
   落点，不写下来下一个人会以为那一档是纯假想的。
4. **G1/G2/G3 表加了 7 行而不是派单点名的 5 行**：多出的两行是
   `__import__("builtins").open("x")` 与 `getattr(__import__("datetime"), "datetime").now()`，
   都来自复审在账本 Ruling 38 里贴的实跑清单。它与派单点名的 5 行是**同一族**，拆开放
   （5 行进表、2 行进散文）反而会让读者以为它们机制不同。

### fr2.10 关切清单（4 条）

**C-fr2-1【中】`_absolute` / `_package_of` 的两份重复这轮又付了一次代价，而且这次是「改两遍 +
核一遍是否还相同」** — 生产状态 + 自己重新推导

Ruling 33 判「本计划内不抽」，Ruling 40 已把「维护成本极低」这个判断更正为偏乐观。本轮的
实际成本比账本记的还要高一格：不光要**改两遍**（硬规矩 #51），还要**额外写一个脚本核两份
改完是否仍逐字相同**（`pe_fr2_rule51.py` 的 ②），因为「两份都改了」与「两份改得一样」是两件事，
后者才是重复代码的真正风险（一份多加一个分支、另一份没加，守卫就开始给出不一致的答案，而
两个测试都是绿的）。**建议**：Plan 02 若真加第三条架构守卫（fr1.8 的 C-fr1-6 提过 Task 9 的
「`app/api` 不得直接 import `app/db`」），抽公共模块的收益就不只是省 12 行，而是省掉这个
「一致性核对」环节。本轮不动（Ruling 33 仍然有效）。

**C-fr2-2【低】我在 `_absolute` 的 docstring 里照抄了派单「命中白名单前缀 `app.domain.`」这个
不够准的措辞** — 自己发现，已实测、未改盘

见 fr2.8 ①。改后的 `test_domain_purity.py:166-168` 写的是「会折成 `app.domain`、**命中白名单
前缀 `app.domain.` 变成真绿**」，实测它命中的是**相等**那一支。**结论对、机制描述差一支**。
我没再改一次盘的理由：① 本轮的收工要求是「一个 commit」，为一个不影响任何判定的措辞再开
一次写盘会拉长取证链；② 它已经在 fr2.8 ① 里被显式记录，下一个人读账本能看到。
**如果控制者认为该改，一行就够**（把「命中白名单前缀 `app.domain.`」改成「命中白名单里
`ALLOWED_PACKAGE` 那一项（相等那一支，不是前缀那一支）」），我可以在 fix round 3 里带上。

**C-fr2-3【低】`FORBIDDEN_IO` 里 `os.listdir` / `import os` 这两个子串对 `__import__("os")` 形状
完全失效，而它们是 Plan 01 专门为此加进去的** — 生产状态 + 自己实测

`test_domain_purity.py:64-65`（改前）的注释写着：「`os` / `__file__` / `json.load` /
`pickle.load` 在列：少了它们，domain 里写一句「import 该标准库再列目录」就能同时绕过时钟与
`open` 两道守卫而全绿」。这句话本身没错，但 fr2.4 的实跑显示：把同一件事写成
`__import__("os").listdir(".")`，命中的子串数是 **0**。也就是说这条注释描述的防线，只对
**直白的 `import os` 形状**有效。**本轮按派单只把它写进了「不被守卫」清单**（G1/G2/G3 表的
第 9 行 + `:380-397` 的 ⚠️ 段），没有改 `FORBIDDEN_IO` 本身——加 `__import__` / `eval` /
`getattr` 进子串表的代价（domain 里不能写正常的 `getattr`）我在 ⚠️ 段里写清了，那是个设计
决定，不该在 fix round 里顺手做。**留给控制者裁**：要不要给 `FORBIDDEN_IO` 补一个
`__import__(` 子串（代价小得多：只挡这一个内置名，不挡 `getattr`）。

**C-fr2-4【低】合成树探针没有进 `tests/`，故 fr2.1/fr2.2 那些「改前 GREEN、改后 RED」的判据
在仓库里没有测试看着** — 自己重新推导

本轮 15 例合成树验收全部由 `pe_fr2_probe.py` 跑出来，它是**取证脚本**、不是测试：
① 派单明写「不得新增测试文件」；② 它要造临时目录树、重定向守卫模块的 `DOMAIN`/`BACKEND`/`APP`
全局，作为常驻测试会引入 21 个临时文件的 I/O 与跨平台路径风险；③ 479 这个数一字不变是
本轮的验收要求之一。**代价（硬规矩 #39）**：`_absolute` 的负数切片那一档、以及 `module` 为空
那一档，**在仓库里没有回归测试**——将来谁把 `if level - 1 > len(package)` 删掉，479 条全绿。
脚本已收进 `.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/fr2_probes/`（gitignore、
不入库，但落在磁盘上、可一键重跑），一条命令复现：

```
python <sdd>/fr2_probes/pe_fr2_probe.py <仓库根> baseline   # 期望 10/15
python <sdd>/fr2_probes/pe_fr2_probe.py <仓库根> work       # 期望 15/15
```

**若控制者希望这两档进仓库**，最小的做法是在 `test_layering.py` 里加**一个**参数化测试函数
直接调 `_absolute`（不造目录树、不重定向全局），大约 6 个 case、passed 数 +1 或 +6。
本轮没做，因为派单的禁区写着「不得新增测试文件、不得改测试断言的行为」，而新增测试函数
会让 479 变化——需要派单预授权（fix round 1 的 M7 就是这样预授权的）。

### fr2.11 本轮**没做**的事

- 没动任何禁区路径（fr2.0 的 `git diff … --stat -- <禁区>` 为空）。`daily.py` 只动了 `:226`
  那一处散文数字，**代码一行没改**（fr2.7 的 ① 用 `ast.dump` 证明了这一点）。
- 没改 `test_models.py` 的任何断言、任何实测数字（只加了两个就地标签）。
- 没重排 `test_models.py:593-598` 那张表的 `====` 框线（改了标签后第二列变宽、框线对不齐，
  但那张表本来 B 行就已经溢出框线；纯排版 churn，与账本 Ruling 39-5 的处置一致）。
- 没动 `test_domain_purity.py:155-156`（改后 `:196-197`）那个把基线单行 `FORBIDDEN` 排成两行的
  `::` 字面块——账本 Ruling 39-5 已判「不修，转延后 Minor」，本轮维持。
- 没把 `_package_of` / `_absolute` 抽成公共模块（Ruling 33 仍有效，见 C-fr2-1）。
- 没给 `FORBIDDEN_IO` 补 `__import__(` 子串（见 C-fr2-3，留给控制者裁）。
- 没提高 `test_layering.py` 的空转下界（8 → 13/17/18 中的任何一个）：Minor 1 只是把上界
  **写对**，把下界提上去会让一次合法重构变红，派单与评审都认可 8。
- 没跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`（禁区）；
  本轮所有实测都不落库：合成树在 `tempfile.mkdtemp()` 下、跑完 `rmtree`；
  「越界相对导入抛什么」那个探针同样在 `mkdtemp()` 下造独立包，`import` 的是那个临时包、
  不是 `app.domain`。
- 没 `git push`；`git checkout` / `git restore` 一次都没用（基线内容全部用 `git show` 取到内存）。


## fix round 3

**派单**：Ruling 42（一处印在源码里的机制错话，一行改动）+ Ruling 46（给上一轮修掉的两个 bug
加回归测试，**已授权改变测试计数**）。禁区：只许动 `test_domain_purity.py` 与 `test_layering.py`
两个文件，生产代码一个字节都不许动，不得改现有 5 条 `assert` 的语义。
**基线** `1fa9941`（479 passed / 0 failed，`app/domain/` 分支覆盖 100%）。开工时我亲验
`git status --short` = **0 行**、`git rev-parse --short HEAD` = `1fa9941`、分支
`feature/plan-02-prescription-engine`（硬规矩 #48）。
**产出** 一个 commit **`be0f1af`**（不 push、不动 `main`），**479 → 481 passed**：本轮新增
2 条测试函数（两个守卫文件各一条，硬规矩 #51），无其他计数变化。

⚠️ **这个 commit 是 `--amend` 过一次的第二版**。第一版 `e647459` 里我在新测试的 docstring 写了
「（变异实测，见任务报告 fix round 3）」——**指针指向不入库的文件**（`.gitignore:10` 的
`.superpowers/`，`git ls-files .superpowers` 计数 0），正是账本 Ruling 27 / 评审 M2 要消灭的
形态，而我在 fr2 里刚读过那条裁定。自查后改成「写全复现命令 + 贴实跑的断言原文」，
`git commit --amend --no-edit` 进同一个 commit（保持派单要求的「一个 commit」）。见 fr3.8-④。

行号一律 **shell 口径**（python 读字节数行，不用 Read 工具——本轮它在这个报告文件上又一次报
「文件只有 1031 行」，实测 **2152** 行；Grep 与 python 口径一致）。改前引用绑定 `1fa9941`、
改后引用绑定 `be0f1af`。

| 文件 | 改前 | 改后 | 字节 |
|---|---|---|---|
| `tests/architecture/test_domain_purity.py` | 458 | **572** | 29846 → 37435 |
| `tests/architecture/test_layering.py` | 228 | **341** | 14461 → 22144 |

`git diff 1fa9941..HEAD --numstat` = **2 文件 / +228 / −1**（purity `115 1`、layering `113 0`）。
`git diff --name-only 1fa9941` 只含这两个守卫文件，`backend/app/**` 命中 **0** 个。

### fr3.0 闸门（全部亲跑，命令逐字给出）

| 闸门 | 命令 | 结果 |
|---|---|---|
| 全量测试 | `cd backend; python -m pytest -q` | **481 passed in 53.55s**，0 failed（基线 479 + 本轮 2 条） |
| 全量 `-W error` | `cd backend; python -m pytest -q -W error` | **481 passed in 53.06s**，0 error |
| domain 分支覆盖 | `cd backend; python -m pytest -q --cov=app/domain --cov-branch --cov-report=term-missing` | `TOTAL **399** stmts / Miss **0** / **114** branch / BrPart **0** / **100%**`；同一次跑 **480 passed, 1 skipped in 112.37s**（那 1 条 skip 是 `test_backfill.py` 在 `--cov` 下的既有自我跳过，与派单预测逐字相同） |
| 架构守卫单跑 | `cd backend; python -m pytest tests/architecture -q -W error` | **6 passed in 0.07s**（基线 4 → +2），0 error |
| 硬规矩 #32（本轮形态：逐顶层单元 + 三组对照） | `python fr3_probes/pe_fr3_astdiff.py .` | **PASS**，见 fr3.4 |
| 硬规矩 #51（两份 `_absolute` 仍逐字相同） | `python fr2_probes/pe_fr2_rule51.py .` | **PASS**，见 fr3.5 |
| 变异验收（12 相位） | `python fr3_probes/pe_fr3_mutation.py .` | **失败项 0 / 12**，见 fr3.3 |
| 判据复核（对拍矩阵 13 格） | `python fr3_probes/pe_fr3_matrix.py .` | **MISMATCH 0 / 13**，见 fr3.2 |
| Ruling 42 的机制实跑 | `python fr3_probes/pe_fr3_r42.py .` | 见 fr3.1 |
| Ruling 46 那句「479 条全绿」 | `python fr3_probes/pe_fr3_blind.py .` | **在基线上复现：479 passed、退出码 0**，见 fr3.6 |
| 变异后的断言原文 | `python fr3_probes/pe_fr3_msgs.py .` | 见 fr3.3 |

禁区与行尾（python 直接读字节，不走 PowerShell 管道）：

```
backend/pe.db exists: False
backend/data/seed/ 条目数: 0
csv bytes=21412 sha256[:16]=D2C8E539E2FA0029 CRLF=0
backend/tests/architecture/test_domain_purity.py   bytes=37435 CRLF=572 裸LF=0 BOM=False 乱码=False
backend/tests/architecture/test_layering.py        bytes=22144 CRLF=341 裸LF=0 BOM=False 乱码=False
```

收工时 `git status --short` → **0 行**，`git log --oneline -2` = `be0f1af` 一个 commit 在
`1fa9941` 之上。本轮**没有造合成树**（新测试直接调 `_absolute`，不需要临时目录），
`$env:TEMP` 下我的 `pe_fr3_msg_*` commit-message 临时文件已 `os.unlink`；上一轮留下的
20 个 `pe_fr2_*` 文件不是我造的，未动。取证脚本 11 个收在
`.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/fr3_probes/`（gitignore、不入库、可一键重跑）。

### fr3.1 Ruling 42 — `_is_allowed('app.domain')` 命中的是「相等」那一支 ✅

**改法**：`test_domain_purity.py` 基线 `:167` 那一行换成 5 行（改后 `:167-171`）。
`ast.get_docstring(_absolute)` 的 unified diff（`pe_fr3_astdiff.py` ② 段实跑）：

```
--- 基线
+++ 工作树
@@ -41,3 +41,7 @@
 ``app/domain/x.py`` 里的 ``from ....domain import tables``（``level == 4``、包深 2）
-会折成 ``app.domain``、**命中白名单前缀 ``app.domain.`` 变成真绿**，而 ``resolve_name``
+会折成 ``app.domain``，而 ``_is_allowed`` 的第一支正是 ``module == ALLOWED_PACKAGE``——
+**命中的是「相等」这一支，不是 ``startswith(ALLOWED_PACKAGE + ".")`` 那一支**（本机
+Python 3.11.1 实跑：``"app.domain" == ALLOWED_PACKAGE`` -> ``True``、
+``"app.domain".startswith(ALLOWED_PACKAGE + ".")`` -> ``False``；Plan02 Ruling 42），
+于是变成真绿；而 ``resolve_name``
 对同一输入抛 ``ImportError``（Plan02 Ruling 35）。
```

**结论（真绿）没改，只改机制**，与派单要求一致。写进 docstring 的两个值是我自己跑的
（`pe_fr3_r42.py`，硬规矩 #52；不是抄派单也不是抄 fr2.8 ①）：

```
ALLOWED_PACKAGE = 'app.domain'
_is_allowed('app.domain'              ) = True  | == ALLOWED_PACKAGE: True  | startswith('app.domain.'): False | in ALLOWED_MODULES: False
_is_allowed('app.domain.seed'         ) = True  | == ALLOWED_PACKAGE: False | startswith('app.domain.'): True  | in ALLOWED_MODULES: False
_is_allowed('app.domain.seed.generate') = True  | == ALLOWED_PACKAGE: False | startswith('app.domain.'): True  | in ALLOWED_MODULES: False
_is_allowed('app.db.seed'             ) = False | == ALLOWED_PACKAGE: False | startswith('app.domain.'): False | in ALLOWED_MODULES: False
_is_allowed('enum'                    ) = True  | == ALLOWED_PACKAGE: False | startswith('app.domain.'): False | in ALLOWED_MODULES: True
```

**没误伤另外两处**：派单点名 `:139` 与 `:246` 说的是 `app.domain.seed.generate`
（`startswith('app.domain.')` 实测 **True**，正确），要求不动。改完全仓 grep「白名单前缀」
只剩 **2 处**，正是它们（`:246` 因本轮插入而后移到 `:351`）：

```
backend/tests/architecture/test_domain_purity.py:139:    就会折成 ``app.domain.seed.generate``、命中白名单前缀 ``app.domain.`` → **守卫当场假绿**
backend/tests/architecture/test_domain_purity.py:351:        这个深度解析到的是 ``app.domain.seed.generate``、命中白名单前缀 ``app.domain.`` →
```

`layering` 侧 `_absolute` 的 docstring **逐字未动**（`pe_fr3_astdiff.py` ② 段实测
`docstring 相同 = True`）——它基线里就没有这句错话。

### fr3.2 Ruling 46 — 两份 `_absolute` 的两份回归测试 ✅

两个文件各新增一条 `test_absolute_folding_matches_resolve_name()`（**同名**，故意的：
`_absolute` 是两份重复代码，两条回归测试同名才 grep 得出来，硬规矩 #51）。
purity 侧插在 `_is_allowed` 与 `test_domain_imports_stay_within_the_allow_list` 之间（改后
`:193-291`），layering 侧插在 `_is_forbidden` 与 `test_production_layers_never_import_app_seed`
之间（改后 `:183-284`）。

**判据锚在 `resolve_name` 上、一个折算结果都不写死**（派单要求）：

```python
rel = "." * level + (module or name)
pkg = ".".join(package)
try:
    want = importlib.util.resolve_name(rel, pkg)
except ImportError:
    want = None
got = _absolute(module, level, package, name)
```

外加一列**期望颜色**（`RED`/`GREEN`）——那是判据（各文件自己的白名单/前缀语义），不是折算
结果，故不违反「不要抄表」。所有不一致一次性收进 `offenders` 再 `assert offenders == []`，
与本文件既有的 `assert offenders == []` 惯例一致（第一个红不会盖住后面的）。

**矩阵 11 格**（以 `(module, level, package, name)` 四元组为参数，Ruling 45）。写进仓库前我先
用 `pe_fr3_matrix.py` 把派单点名的 9 个形状 + 2 个自选边界档一起对拍过一遍，**13 格 MISMATCH 0**、
两份 `_absolute` 互相一致（下面是实跑输出，不是抄派单的期望值）：

| 形状 `(module, level, package, name)` | `resolve_name` | 两份 `_absolute` | purity 判定 | layering 判定 |
|---|---|---|---|---|
| `("app.seed.generate", 0, ("app","domain"), "")` | `'app.seed.generate'` | 同 | RED | RED |
| `("tables", 1, ("app","domain"), "")` | `'app.domain.tables'` | 同 | **GREEN** | GREEN |
| `("", 1, ("app","domain"), "tables")` | `'app.domain.tables'` | 同 | **GREEN** | GREEN |
| `("_shared", 1, ("app","db","models"), "")` | `'app.db.models._shared'` | 同 | RED | **GREEN** |
| `("", 1, ("app","db","models"), "_shared")` | `'app.db.models._shared'` | 同 | RED | **GREEN** |
| `("seed.generate", 2, ("app","pipeline"), "")` | `'app.seed.generate'` | 同 | RED | RED |
| `("", 2, ("app","pipeline"), "seed")` | `'app.seed'` | 同 | RED | RED |
| `("", 2, ("app","db"), "seed")` | `'app.seed'` | 同 | RED | RED |
| `("", 2, ("app","db","models"), "seed")` | `'app.db.seed'` | 同 | RED | **GREEN** |
| `("", 2, ("app","domain"), "seed")` | `'app.seed'` | 同 | RED | RED |
| `("seed", 5, ("app","db","models"), "generate")` | `ImportError` | `None` | RED | RED |
| `("domain", 4, ("app","domain"), "tables")` | `ImportError` | `None` | RED | RED |
| `("seed", 3, ("app","domain"), "generate")` | `ImportError` | `None` | RED | RED |

（第 2/3 行只有 purity 侧进了仓库矩阵、第 4/5 行只有 layering 侧进了仓库矩阵——各取自己包树里
真实会出现的那一档当绿档；越界档第 3 行 `("seed", 3, ("app","domain"), …)` 是
`level - 1 == len(package)`，由既有的 `if not anchor: return None` 兜住、**不是**由 Ruling 35
新加的那一行兜住，两侧都进了仓库矩阵，理由见 fr3.8-②。表里另外 2 格
`("", 1, ("app",), "seed")` → `'app.seed'` 与 `("seed", 3, ("app","db","models"), "generate")`
→ `'app.seed'` 是我为验证等价性多跑的，**没进仓库**。）

**⚠️ 两份的期望颜色列刻意不相同**：`("", 2, ("app","db","models"), "seed")` 折成 `app.db.seed`，
在 layering 的 `app.seed` 前缀下是 **GREEN**（Ruling 41 的「折算串错了不等于判定错了」），
在 purity 的白名单下是 **RED**（`_is_allowed('app.db.seed') = False`，上面实跑）。两个
docstring 里都写明了这一点，免得下一个人以为其中一份抄错。

**判据的可靠性论证**（为什么锚在 `resolve_name` 上就够）：Python 3.11.1
`Lib/importlib/util.py` 的 `resolve_name` 是

```python
def resolve_name(name, package):
    if not name.startswith('.'):
        return name                     # ← level == 0 走这一支，故派单给的公式对 level 0 也成立
    elif not package:
        raise ImportError(...)
    level = 0
    for character in name:
        if character != '.': break
        level += 1
    return _resolve_name(name[level:], package, level)
```

而 `_resolve_name` 抛 `ImportError` 的条件是 `len(package.rsplit('.', level - 1)) < level`；
`len(package.rsplit('.', level - 1)) == min(level, 包深)`，故该条件等价于 `包深 < level`，
即 `level - 1 >= 包深`。`_absolute` 用**两行**覆盖同一个集合：`level - 1 > len(package)`
（Ruling 35 新加）与 `level - 1 == len(package)`（既有的 `not anchor`）。**两者合起来与
`resolve_name` 精确等价**，13 格对拍 0 DIFF 是这个论证的实测面。

### fr3.3 变异验收（12 相位，两份分别做，硬规矩 #50 / #51 / #53）

`pe_fr3_mutation.py`，全部相位都先在 **AST 上确认变异真的改了代码**（`ast.dump` 前后不等），
每次变异后按**字节**还原并核 sha256，全程未用 `git checkout` / `git restore`。

| 相位 | 变异 | purity | layering |
|---|---|---|---|
| M0 | 不变异（**对照 GREEN**，#53） | GREEN ✅ | GREEN ✅ |
| M1 | `package[: len(package) - (level - 1)]` → `package[: len(package) - level + 1]`（**AST 变了、语义等价**，#53 的「尺子不是恒红」对照） | GREEN ✅ | GREEN ✅ |
| M2 = 派单 ① | 删掉 `if level - 1 > len(package): return None`（含注释共 3 行），只变异 purity | **RED** ✅ | GREEN ✅（未被变异） |
| M2 | 同上，只变异 layering | GREEN ✅（未被变异） | **RED** ✅ |
| M2 | 同上，两份都变异 | **RED** ✅ | **RED** ✅ |
| M3 = 派单 ② | `tail = module or name` → `tail = module`，只变异 purity | **RED** ✅ | GREEN ✅ |
| M3 | 同上，只变异 layering | GREEN ✅ | **RED** ✅ |
| M3 | 同上，两份都变异 | **RED** ✅ | **RED** ✅ |
| M4 = 额外 | `_imported_modules` 的逐个 `names` 展开改回「一个节点只 yield 第一条」，只变异 purity | **RED** ✅ | GREEN ✅ |
| M4 | 同上，只变异 layering | GREEN ✅ | **RED** ✅ |
| M4 | 同上，两份都变异 | **RED** ✅ | **RED** ✅ |
| M4-附 | 同 M4，但只跑**旧的 4 条**守卫（`-k not test_absolute_folding_…`） | `4 passed, 2 deselected`、退出码 0 → **旧守卫对这一档无感** | |

**失败项 0 / 12**。「只变异一份时另一份保持绿」这一列是硬规矩 #51 的正面证据：两条回归测试
各自看着自己那一份 `_absolute`，谁也替代不了谁。

**红的是哪条断言**（`pe_fr3_msgs.py` 实跑的 pytest 输出，硬规矩 #53 要求区分「真红」与
「harness 坏了导致的假红」——下面每一行都是断言消息本体，不是收集错误）：

```
M2 purity   E  _absolute('seed', 5, ('app', 'db', 'models'), 'generate') = 'app.db.seed'，而 resolve_name('.....seed', 'app.db.models') = None
            E  _absolute('domain', 4, ('app', 'domain'), 'tables') = 'app.domain'，而 resolve_name('....domain', 'app.domain') = None
            E  _absolute('domain', 4, ('app', 'domain'), 'tables') = 'app.domain' 判成 GREEN、期望 RED
M2 layering E  _absolute('seed', 5, ('app', 'db', 'models'), 'generate') = 'app.db.seed' 判成 GREEN、期望 RED   （+ 同上 3 行）
M3 purity   E  _absolute('', 1, ('app', 'domain'), 'tables') = 'app.domain'，而 resolve_name('.tables', 'app.domain') = 'app.domain.tables'
            E  _absolute('', 2, ('app', 'pipeline'), 'seed') = 'app'，而 resolve_name('..seed', 'app.pipeline') = 'app.seed'
            E  _absolute('', 2, ('app', 'db'), 'seed') = 'app'，而 resolve_name('..seed', 'app.db') = 'app.seed'
            E  _absolute('', 2, ('app', 'db', 'models'), 'seed') = 'app.db'，而 resolve_name('..seed', 'app.db.models') = 'app.db.seed'
            E  _absolute('', 2, ('app', 'domain'), 'seed') = 'app'，而 resolve_name('..seed', 'app.domain') = 'app.seed'      （共 5 格）
M3 layering E  _absolute('', 1, ('app', 'db', 'models'), '_shared') = 'app.db.models'，而 resolve_name('._shared', 'app.db.models') = 'app.db.models._shared'
            E  …（含 3 格「判成 GREEN、期望 RED」，共 8 行）
M4 两侧     E  AssertionError: 一名一条的展开失效: ['app.seed'] != ['app.seed', 'app.pipeline']
```

**三重还原取证**（脚本末尾实跑）：

```
purity    sha256[:16]=dffa51f460826436 与原始一致=True 37435 字节 CRLF=572 裸LF=0
layering  sha256[:16]=a5afd212bd485ef4 与原始一致=True 22144 字节 CRLF=341 裸LF=0
git status --short: （变异过程中 2 行 M；相位结束后逐次核 sha256 一致）
```

### fr3.4 硬规矩 #32 闸门（本轮形态：逐顶层单元 + 三组对照）

本轮**两个守卫文件都真改了代码**（新增函数），故「剥 docstring 后 `ast.dump` 比基线 SAME」
这条判据**按字面不可满足、也不该满足**。自证改成派单要求的形态：`pe_fr3_astdiff.py`
逐顶层单元比（基线用 `git show 1fa9941:<path>` 取到内存，不落盘、不 checkout），并带三组对照。

```
=== ⓪ 改动面 ===
   backend/tests/architecture/test_domain_purity.py
   backend/tests/architecture/test_layering.py
   合计 2 个文件；生产代码（backend/app/**）命中 = 0

=== ① 逐顶层单元（剥 docstring 后）===
test_domain_purity.py：_domain_files / _assert_not_empty / _imported_modules / _package_of /
   _absolute / _is_allowed / test_domain_imports_stay_within_the_allow_list / _dotted /
   _hit_forbidden_call / test_domain_has_no_clock_or_file_access /
   test_domain_has_no_filesystem_access / <module-level>  → **全部「未动」**
   NEW test_absolute_folding_matches_resolve_name
   → 有差异的顶层单元 = ['test_absolute_folding_matches_resolve_name']
test_layering.py：_py_files / _package_of / _absolute / _imported_modules / _is_forbidden /
   test_production_layers_never_import_app_seed / <module-level>  → **全部「未动」**
   NEW test_absolute_folding_matches_resolve_name
   → 有差异的顶层单元 = ['test_absolute_folding_matches_resolve_name']

=== ③ 既有 5 条 assert 逐字对比 ===
   test_domain_imports_stay_within_the_allow_list    assert 1→1 逐字相同=True
   test_domain_has_no_clock_or_file_access           assert 1→1 逐字相同=True
   test_domain_has_no_filesystem_access              assert 1→1 逐字相同=True
   test_production_layers_never_import_app_seed      assert 2→2 逐字相同=True
   既有 assert 合计 5 条，全部逐字未动

=== 对照组（硬规矩 #53）===
   test_domain_purity.py  ① 注入语义变异后报 DIFF 的单元=['_absolute']  ② 自比报 DIFF=[]
                          ③ 只改 docstring：不剥时报 DIFF=True、剥掉后报 DIFF=[]
   test_layering.py       ① 同上  ② 同上  ③ 同上
```

即：**改动面恰好是「新增的两条测试函数」+「purity 侧 `_absolute` docstring 的那一处」**
（② 段的 docstring diff 见 fr3.1），`<module-level>` 逐字未动——这就是我把
`import importlib.util` 写在**函数体内**的原因（fr3.8-③）。
对照 ③ 用的是 `_absolute` docstring 首句「折算成**绝对模块串**」→「**绝对的模块串**」：
不剥 docstring 时尺子报 DIFF、剥掉后报 SAME，证明它真的在剥。

### fr3.5 硬规矩 #51 闸门（两份 `_absolute` 仍逐字相同）

复跑上一轮的 `fr2_probes/pe_fr2_rule51.py`（本轮没改它）：

```
=== ① 全仓定义份数 ===  合计 4 处定义（_package_of 2 份 + _absolute 2 份）
=== ② 剥 docstring 后的函数体 AST ===
    _package_of    份数=2  签名=['py']                              函数体 AST 逐字相同=True
    _absolute      份数=2  签名=['module', 'level', 'package', 'name']  函数体 AST 逐字相同=True
=== ③ 7 项关键点在两份里都在 ===  两份全 OK
=== ④ 两条旧的假举例串 ===  命中 无（已删）
硬规矩 #51 闸门: PASS
```

派单要求「本轮不许打破 `identical(excl docstring) = True`」——**未打破**。
本轮两条新测试函数**也各有一份**（同名、同结构，只有绿档取样与颜色判据按各自守卫的语义
不同），故 #51 的适用面从「两份实现」扩到了「两份实现 + 两份回归测试」。

### fr3.6 Ruling 46 那句「479 条全绿」我自己在基线上复核了

新测试的 docstring 里印了「谁删掉 `if level - 1 > len(package): return None`，479 条全绿」
（引自 Ruling 46）。按硬规矩 #52，印进在库文件的数字我得自己能指到一条命令，故亲跑
（`pe_fr3_blind.py`）：把 `git show 1fa9941:<path>` 取到的**基线**两份守卫都删掉那一行、
写进工作树，跑全量：

```
=== 把基线 1fa9941 的两份 _absolute 删掉越界守卫，跑全量测试 ===
  purity    已写入基线-变异版 29664 字节（基线 blob 29388 字节）
  layering  已写入基线-变异版 14279 字节（基线 blob 14233 字节）
  退出码=0
  479 passed in 54.05s
  => Ruling 46 那句「479 条全绿」在基线上复现 = True
```

**成立**：那个口子是真的，本轮新增的两条测试正是为了堵住它（fr3.3 的 M2 三个相位）。

⚠️ 顺带一个坑，记下以免下一个人误判（**这是我自己踩的**）：`git show HEAD:<path>` 给出的是
**blob 里的 LF 版本**（`core.autocrlf=true`，实测 `git config core.autocrlf` = `true`），
而工作树是 CRLF 版本。我第一版脚本直接拿 blob 字节与工作树比，断言当场炸：
purity blob `36103 B` vs 工作树 `36666 B`，差 `563` **恰等于 CRLF 行数**。修法是把 blob 的
`\n` → `\r\n` 再比，并在脚本里 assert「差值 == CRLF 行数」。**这与硬规矩 #46 是同一族**
（`git checkout` / `git show` 会按 `autocrlf` 给不同字节），只是这次它出现在**读**的一侧、
不是写的一侧。

还原后取证：

```
purity    sha256[:16]=892119ff89ba63ff 与 HEAD 一致=True 36666 字节 CRLF=563 裸LF=0   （amend 前的第一版）
layering  sha256[:16]=60ba5d6e3f8115bd 与 HEAD 一致=True 21355 字节 CRLF=332 裸LF=0
git status --short: 0 行 []
HEAD = e647459 …
```

（这次探针跑在 amend 之前，故 sha 是第一版的；amend 后的最终 sha 见 fr3.3 末尾与 fr3.0。）

### fr3.7 我发现的派单错误（2 条成立 + 1 条歧义不计入 + 1 条我自己的预期错了）

按派单 §4.7 逐条给实测证据。**没有一条导致判据不可满足**，两件事我全部按派单做了。

**① 「`task-1-brief.md` — Global Constraints **9 条**」→ 实测 **10 条**。（成立，计一条）**

python 数 `## Global Constraints` 与 `## Review Focus` 之间的 `- ` 顶层 bullet：
`task-1-brief.md` = **10**，`Document/2026-10-06-实施计划02-智能处方引擎.md` 同一节也 = **10**
（10 条依次是：domain 无 I/O、domain 分支覆盖 100%、单一所有者、断言两侧不得同源、
散文必须带口径、行号取 shell 口径、PowerShell、落盘唯一权威是 shell、禁区、`app/seed/` 冻结）。
影响：无，我 10 条全读了。
**附带发现（不在派单里、也不在我可改的范围里）**：计划文档 `:13` 自己写「其中对本计划最要命的
**六条**见 Global Constraints」，与该节实有的 10 条不符。那是基线 `e26347f` 就有的、
在禁区 `Document/` 里，本轮**未动**，只记下转给控制者。

**② 「矩阵至少覆盖这 **7 类**」→ 派单自己枚举的是 **5 个 bullet / 9 个具体形状**。（成立，计一条）**

派单那 5 个 bullet 展开是：`level == 0`（1 个形状）+ `level == 1`（1）+
`from ..seed import generate` @ `app/pipeline`（1）+ `module` 为空（**4**）+ 越界（**2**）
= **9 个形状、5 组**。`7` 与 5、9 都不符；最接近的读法是「前四个 bullet 的形状数
1+1+1+4 = 7」，即**漏数了第五个 bullet 的 2 个越界形状**——而那 2 个恰恰是 Ruling 35 的主角、
也是变异 ① 唯一的抓手。账本 Ruling 46（`progress.md:502`）列的也是同样 5 组 / 9 个形状。
影响：因为是「**至少**覆盖」，判据仍可满足。我覆盖了全部 9 个 + 2 个自选档 = **11 格**
（fr3.2 的表是 13 格，其中 2 格只用于验证等价性、没进仓库）。

**③（歧义，按 Ruling 45 的口径不计入控制者错误）**
「`("", 2, ("app","db","models"), "seed")` → `app.db.seed`（**判定仍绿**，折算串才是重点）」
——「仍绿」只在 **layering** 侧成立。同一折算串在 **purity** 侧实测
`_is_allowed('app.db.seed') = False` → **RED**（fr3.1 的实跑表第 4 行）。派单那句话的语境是
Ruling 41（讲的是 layering 守卫），**不是事实错误**，只是没标主语；而它落到「两份文件各加
一条」的要求上时，两份的期望颜色列**必须不同**。我在两个 docstring 里都写明了理由，
以免下一个人以为其中一份抄错。

**④（我自己的预期错了，派单是对的——记下以免下一个人重复怀疑）**
开工前我判断「派单给的公式 `resolve_name("." * level + (module or name), …)` 对 `level == 0`
会抛异常（名字不以 `.` 开头），故那条判据对 `level == 0` 档按字面不可满足」，准备报成一条
派单错误。实测**不成立**：Python 3.11.1 `Lib/importlib/util.py` 的 `resolve_name` 第一行就是
`if not name.startswith('.'): return name`，故
`resolve_name("app.seed.generate", "app.domain")` = `'app.seed.generate'`，与 `_absolute` 逐字
相同（fr3.2 表第 1 行）。**派单的公式对 `level == 0` 同样成立、不需要特例。**
按「把不成立的指控也一并认下来是同一种失职」的口径，这条**不计入控制者错误**，
计入我自己的判断失误。

其余我逐条核过、**成立**的派单陈述（列出来表示核过，不是凑数）：分支名与基线 HEAD ✓、
`core.autocrlf=true` ✓、`progress.md` 448+ 行（实测 529）✓、#48 在 `:172` / #49 `:265` /
#50 `:290` / #51 `:409` / #52 `:411` / #53 `:509` ✓、`test_domain_purity.py:167` 原文逐字命中 ✓、
`_is_allowed` 的实现串逐字命中 ✓、「全仓只有 `:167` 一处错」✓、`fr2_probes/` 11 个脚本 ✓、
基线 479 passed ✓、基线 domain `399/0/114/0/100%` ✓、`--cov` 下 `1 skipped` 且本轮应变
`480 passed, 1 skipped` ✓、既有 5 条 assert（purity 3 + layering 2）✓、上一轮
`identical(excl docstring) = True` ✓。

### fr3.8 超出派单的改动（主动披露，4 处，全部在两个守卫文件内）

**① 额外钉住 Ruling 36 的「另一半」：`_imported_modules` 的逐个 `names` 展开。**
派单的变异验收只点名 `_absolute` 的两个变异，但 Ruling 46 的原话是「本轮修掉的**两个 bug**」，
而 bug 2（忽略 `node.names`）的修法有**三部分**（fr2.2）：`_absolute` 加 `name` 入参、
`tail = module or name`、`_imported_modules` 在 `module` 为空档**逐个 `names` yield**。
只测 `_absolute` 会把第三部分继续留在没人看的状态。故两个新测试的末尾各加一段：
`ast.parse("from .. import seed, pipeline")` → 必须折算出两条。变异 M4 实测（fr3.3）：
把逐个 yield 改回「只 yield 第一条」，**两条新测试都红**，而同一次跑里**旧的 4 条守卫
`4 passed` 无感**——这是 Ruling 46 那个口子的第三个实例，本轮一并堵上。
不造目录树、不重定向全局，只用 `ast.parse` 一个字符串，成本 6 行。

**② 矩阵比派单点名的多 2 格。** 一格是 `level == 1` 的 `name` 形式
（`("", 1, <包>, "tables"/"_shared")`）——派单只要求「`level == 1` 的包内合法导入」一格，
但 `module` 形式与 `name` 形式在 `_absolute` 里走的是**不同的分支**（`tail = module or name`
的两侧），只放一格就测不到 `or name` 这一侧在 `level == 1` 下的行为（变异 M3 的红里
就有这一格：`_absolute('', 1, ('app','domain'), 'tables') = 'app.domain'`）。
另一格是 `("seed", 3, ("app","domain"), "generate")`，即 `level - 1 == len(package)`：
它由**既有的** `if not anchor: return None` 兜住、不是由 Ruling 35 新加的那一行兜住。
放它的目的是把两行守卫的管辖范围分开——删掉新行时这一格**不变**（仍 `None`），
故它证明 `not anchor` 那一行还在干活、没有被新行的存在掩盖掉。

**③ `import importlib.util` 写在函数体内、不写在模块顶部。**
派单 §3 要求自证「除新增的两条测试函数与 `:167` 那一处 docstring 外，其余部分与基线逐字
相同」；模块级 import 会改动 `<module-level>` 这个顶层单元，故就地 import。两处各写了一行
注释交代理由。**代价**：不如顶部 import 惯例。若控制者认为该按惯例放顶部，那 §3 的自证
口径要跟着放宽成「`<module-level>` 只多一条 import」。

**④ docstring 里不留「见任务报告」这类指向不入库文件的指针**（amend 的那一处，见开头 ⚠️）。
改成写全复现命令 `python -m pytest tests/architecture -q` + 贴实跑的断言原文，
符合账本 Ruling 27 的处置口径（「写全命令 + 引账本 Ruling 编号，或标『历史实测，不被守卫』」）。
账本 Ruling 编号（`Plan02 Ruling 35/36/41/45/46/51`）仍然引——那是这两个文件既有的惯例。

### fr3.9 关切清单（3 条）

**C-fr3-1【中】`_package_of` 仍然没有回归测试，而它是两条守卫共同的假绿入口** — 自己重新推导

两个新测试的 `package` 入参是**手写的**，故 `_package_of` 不在守卫范围内。这一点我已按
硬规矩 #39 写进两个 docstring 的「本测试守不住什么」段。风险不是假想的：Ruling 37 说得很
清楚——谁按那个假举例去「对齐」代码、让 `_package_of` 返回模块名而不是包名，
`app/db/models/x.py` 里的 `from ...seed import …` 就会折成 `app.db.seed`、不再以 `app.seed`
开头，**两条架构守卫一起假绿**，而今天只有 docstring 里两行 `resolve_name` 实跑举例在交代。
本轮派单只授权给 `_absolute` 的两个 bug 加测试，我没扩到 `_package_of`（那会再动 passed 数）。
**最小修法（成本极低，不需要文件存在）**：`_package_of` 是纯路径算术，
`_package_of(BACKEND / "app" / "domain" / "x.py") == ("app", "domain")` 与
`_package_of(BACKEND / "app" / "db" / "models" / "__init__.py") == ("app", "db", "models")`
两行就够，且可以**塞进现有那条新测试里、不增加 passed 数**。**留给控制者裁。**

**C-fr3-2【低】`test_domain_purity.py` 的模块 docstring 说「三条守卫」，而文件里现在有 4 个
`test_*` 函数** — 自己发现，未改

那句话本身不假（新增的那条是**辅助函数的单元测试**，不是第四条守卫），但按「数 `test_*`
函数」的方式点人头的人会以为漏改了一处。改它要动**模块 docstring**，超出本轮「除新增函数与
`:167` 外逐字相同」的钉死范围，故未动。**建议**：若 Plan 02 后续还要往这两个文件里加
单元测试，就把模块 docstring 的那句改成「三条守卫 + N 条辅助函数单元测试」。

**C-fr3-3【低 → 建议 Plan 02 Task 2 之后评估】11 格矩阵是手写的，形状不会自动跟进** — 自己重新推导

判据锚在 `resolve_name` 上，所以矩阵**不会过期成假绿**（加一行就是加一格覆盖）；
但**没人会被提醒去加**——Task 2 建了 `app/domain/prescription/` 子包之后，包深 3 的
`from ..indicators import X` 是新增的真实形状，而矩阵里包深 3 的绿档只有 layering 侧那一格。
真要机械化，做法是「扫真仓所有 `ImportFrom` 节点、逐个与 `resolve_name` 对拍」：那是一条
**更强**的守卫（自动覆盖以后出现的每一个形状），而且它会顺带把 `_package_of` 拉进判据
（于是 C-fr3-1 一并解决）。**本轮不做**的理由：它会改变「不扫真仓」这条边界、且需要
预授权改 passed 数；Task 2 落地后形状才稳定，那时做收益更高。

### fr3.10 本轮**没做**的事

- 没动任何生产代码：`git diff --name-only 1fa9941` 只含两个守卫文件，`backend/app/**` 命中 0。
- 没动 `backend/tests/` 下的其他文件、没动 `backend/data/`、没动 `Document/`
  （包括 fr3.7-① 附带发现的「六条 vs 10 条」不一致，它在禁区里）。
- 没改既有 5 条 `assert` 的语义（fr3.4 ③ 段逐字比过：1+1+1+2 = 5 条，全部 `逐字相同=True`）。
- 没动 `:139` 与 `:351`（原 `:246`）那两处「命中白名单前缀 `app.domain.`」——它们说的是
  `app.domain.seed.generate`，`startswith` 实测为 True，是正确的。
- 没动 `layering` 侧 `_absolute` 的 docstring（它基线里没有 Ruling 42 那句错话，实测逐字未动）。
- 没把 `_package_of` / `_absolute` 抽成公共模块（Ruling 33 仍有效；fr2.10 的 C-fr2-1 也仍有效
  ——本轮又付了一次「改两遍 + 核两份是否仍相同」的代价，还多付一次「两条回归测试也要各写一份」）。
- 没给 `FORBIDDEN_IO` 补 `__import__(`（Ruling 47 已判延后 Minor）。
- 没造合成树、没重定向任何守卫模块的全局（本轮的新测试直接调 `_absolute`，不需要）；
  没跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`（禁区）。
- 没 `git push`；`git checkout` / `git restore` / `git switch` **一次都没用**
  （基线内容全部用 `git show` 取到内存，还原全部用 python `write_bytes`）。
- 没动 `fr2_probes/` 里的 11 个脚本（只**读**着复跑了 `pe_fr2_rule51.py`）。

## fix round 4

**派单**：Ruling 54（给两份 `_package_of` 补回归断言，**塞进已有的那条测试里、passed 数不变**）
+ Ruling 55（`test_domain_purity.py` 模块 docstring 说「三条守卫」而文件里有 4 个 `test_*`）。
禁区：只许动 `test_domain_purity.py` 与 `test_layering.py`，生产代码一个字节都不许动，
不得改现有 5 条守卫 `assert` 的语义，**不新增测试函数**，`import importlib.util` 维持在
函数体内（Ruling 57）。
**基线**：HEAD = `73313f7`（亲验 `git diff --name-only be0f1af 73313f7` 只含
`Document/2026-10-06-实施计划02-智能处方引擎.md` 一个文件，故**代码基线取 `be0f1af`**，
两个守卫文件自 `be0f1af` 起逐字未变），481 passed / `app/domain` 分支覆盖 100%。
开工时亲验：`git status --short` = **0 行**、`git rev-parse --short HEAD` = `73313f7`、
分支 `feature/plan-02-prescription-engine`、`git config core.autocrlf` = `true`、
`python -V` = `Python 3.11.1`、仓库根与 `backend/` 下**都没有 venv 目录**（硬规矩 #48）。
两个守卫文件开工时的 sha256[:16] = `dffa51f460826436` / `a5afd212bd485ef4`，与 fr3 报告
收工值**逐字相符**，即工作树确实就是 `be0f1af` 的状态。
**产出**：一个 commit **`6784d57`**（不 push、不动 `main`），**481 passed 不变**
（本轮新增测试函数 **0** 条，与派单要求逐字相符）。

行号一律 **shell 口径**（python 读字节数行；本轮实测 `Read` 工具在 `test_layering.py` 上
偏移 **−2**、在 `progress.md` 的 `:300` 处偏移 **0** 而在 `:446`/`:450`/`:588` 处偏移 **−1**、
在 `test_domain_purity.py` 上偏移 **0**，见 fr4.7-④）。改前引用绑定 `be0f1af`、
改后引用绑定 `6784d57`。

| 文件 | 改前行数 | 改后行数 | 字节 | CRLF | 裸LF | sha256[:16]（改后） |
|---|---|---|---|---|---|---|
| `tests/architecture/test_domain_purity.py` | 573 | **635** | 37435 → 41613 | 572 → 634 | 0 | `440f7167610df187` |
| `tests/architecture/test_layering.py` | 342 | **397** | 22144 → 25789 | 341 → 396 | 0 | `50d776680defc25e` |

`git diff --numstat be0f1af HEAD -- backend/` = purity `70 8`、layering `61 6`；commit 汇总
`2 files changed, 131 insertions(+), 14 deletions(-)`（70+61=131、8+6=14，自洽）。
`git diff --name-only 73313f7`（= 本轮工作树改动面）只含这两个守卫文件，
`git diff --name-only be0f1af HEAD -- backend/app/` 命中 **0** 个。

落盘方式：**全程 python 按字节写**（`fr4_probes/pe_fr4_edit.py` / `pe_fr4_edit2.py` /
`pe_fr4_edit3.py`），不用编辑工具改这两个守卫文件。每处替换都按**行号区间 + 指纹**双确认、
自底向上改，落盘后重新读字节逐处 `assert` 新串命中恰 1 次 / 旧串命中 0 次 / 行尾纯 CRLF。
`git checkout` / `git restore` / `git switch` **一次都没用**（基线内容全部用 `git show`
取到内存，并按账本记的坑把 blob 的 LF 换成 CRLF 后才落盘，见 fr4.3 的 M6）。

⚠️ **本轮亲身撞上「编辑工具报成功而磁盘未写」9 次**（工具/磁盘分歧家族的第 48–56 次），
全部发生在**本报告草稿**上、没有一次发生在两个守卫文件上（那两个文件我只用 python 写）：

* 对 `fr4_probes/SECTION_fix_round_4.md` 连做 **8 次**替换（`SearchReplace`），工具每次都回
  「success」并**打印了看起来正确的 diff**，而 `pe_fr4_section_check.py` 逐串实测
  **8 / 8 未落盘**（新串命中 0、旧串命中 1）。
* 改用**整文件重写**（`Write`）再试一次：工具回「has been updated successfully」并**把新内容
  用 `cat -n` 全篇回显**（633 行、逐行带行号），而磁盘上仍是旧内容
  （`pe_fr4_report.py` ① 段的落盘闸门抓到：11 个新串里 10 个命中 0、6 个旧串全部残留，
  文件 sha256[:12] 仍是 `a72f50f3c91d`）。**这是本轮最危险的一次**：回执里那份逐行回显
  与真落盘没有任何区别，只有 shell 读回能揭穿它。
* 最终处置：**换一个从未写过的文件名**（`SECTION_fr4_final.md`）重写，落盘后用
  `pe_fr4_report.py` ① 段逐串核过（11 个新串全命中、6 个旧串 0 残留）才允许追加。
* 同一批工具调用对 `fr4_probes/*.py` 的 **9 次**替换全部落盘成功（每次都用 python 读回 +
  实际跑通验证过）。故失败与文件类型无关、与「该文件此前已被本会话写过」有关。

派单 §0 那条警告是对的，而且它没说的部分是：**失败时会连 diff、甚至整篇 `cat -n` 回显一起
伪造出来**，只看工具回执根本发现不了。故本轮把「每次编辑后 shell 读回」从守卫文件扩到了
**所有**文件，包括报告本身。

### fr4.0 闸门（全部亲跑，命令逐字给出）

| 闸门 | 命令 | 结果 |
|---|---|---|
| 全量测试 | `cd backend; python -m pytest -q` | **481 passed in 101.12s**，rc 0（与基线逐字相同，**passed 数未变**） |
| 全量 `-W error` | `cd backend; python -m pytest -q -W error` | **481 passed in 105.68s**，rc 0，0 error |
| domain 分支覆盖 | `cd backend; python -m pytest -q --cov=app/domain --cov-branch --cov-report=term-missing` | `TOTAL **399** stmts / Miss **0** / **114** branch / BrPart **0** / **100%**`；同一次跑 **480 passed, 1 skipped in 196.34s** |
| 那 1 条 skip 是谁 | 读 `backend/tests/pipeline/test_backfill.py` | `:181` 是 `if sys.gettrace() is not None:`、**`:182` 是 `pytest.skip(`** → 与派单点名的 `test_backfill.py:182` trace-hook 自觉跳过逐字相符，既有行为 |
| 架构守卫单跑 | `cd backend; python -m pytest tests/architecture -q -W error` | **6 passed in 0.17s**（基线 6 → 6，**没有新增测试函数**），0 error |
| 硬规矩 #32（逐顶层单元 + 四组对照） | `python fr4_probes/pe_fr4_astdiff.py .` | **PASS**（rc 0），见 fr4.4 |
| 硬规矩 #51（两份 `_package_of` / `_absolute`） | 同上 ⑤ 段 | **PASS**，见 fr4.5 |
| 变异验收（8 相位） | `python fr4_probes/pe_fr4_mutation.py .` | **失败项 0 / 8**（rc 0），见 fr4.3 |
| 硬规矩 #52（写进 docstring / 断言消息的每个值） | `python fr4_probes/pe_fr4_r52.py .` | **PASS**（rc 0），见 fr4.6 |
| Ruling 42 那句「`:139` 是正确的」复核 | `python fr4_probes/pe_fr4_ruling42b.py .` | **不成立**（rc 0），见 fr4.7-⑥ 与 fr4.8-① |
| 开工预检（4 个形状 + 两个 docstring 的举例 + 计数陈述） | `python fr4_probes/pe_fr4_precheck.py .` | 见 fr4.1 / fr4.2 |
| 「后果」两格的折算实跑 | `python fr4_probes/pe_fr4_compose.py .` | 见 fr4.1 |
| 报告里引的计数与行区间 | `python fr4_probes/pe_fr4_counts.py .` | 见 fr4.2 / fr4.5 |
| 报告草稿的落盘复核 | `python fr4_probes/pe_fr4_section_check.py .` | **8 / 8 未落盘**，见上面那条 ⚠️ |
| 追加报告 + 复核 | `python fr4_probes/pe_fr4_report.py .`；`python fr4_probes/pe_fr4_verify_report.py .` | 前者 rc **1**（追加正确、它自己那条子串计数断言写错）、后者 **PASS** rc 0，见 fr4.11 |

禁区与行尾（python 直接读字节，不走 PowerShell 管道）：

```
backend/pe.db exists: False
backend/data/seed/ exists: True  entries: 0
data/national_standard_2014.csv bytes=21412 sha256[:16]=D2C8E539E2FA0029 CRLF=0
backend/tests/architecture/test_domain_purity.py   bytes=41613 CRLF=634 裸LF=0 BOM=False 乱码=False
backend/tests/architecture/test_layering.py        bytes=25789 CRLF=396 裸LF=0 BOM=False 乱码=False
```

收工时 `git status --short` → **0 行**；`git log --oneline -2` = `6784d57` 一个 commit 在
`73313f7` 之上；`git diff --name-only HEAD~1 HEAD` = 那两个守卫文件；分支仍是
`feature/plan-02-prescription-engine`（未 push）。仓库根无临时目录：`.pytest_cache/` 与
`backend/.pytest_cache/` 的 mtime 是 **2026-09-28 18:01 / 17:58**，早于本轮，非我造；
`backend/.coverage` 是本轮 `--cov` 那次跑更新的（`.gitignore:7` 忽略）。
`$env:TEMP` 下我的 `fr4_astdiff.txt` / `fr4_mut.txt` / `fr4_r52.txt` / `fr4_diff_layering.txt`
4 个文件已 `os.unlink`（前 3 个先复制进 `fr4_probes/OUT_*.txt`），commit-message 临时文件
`pe_fr4_commitmsg.txt` 已在 `pe_fr4_commit.py` 里删除。取证产物收在
`.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/fr4_probes/`（`.gitignore:10`、不入库、
可一键重跑）：**16 个 `pe_fr4_*.py` + 3 份 `OUT_*.txt` + 2 份报告草稿 = 21 个条目**（那份被工具写坏的
`SECTION_fix_round_4.md` 留着当证据，不删）。本轮**没有造合成树**（`_package_of` 是纯路径
运算，不需要临时目录）。

### fr4.1 Ruling 54 — 两份 `_package_of` 的回归断言 ✅

**开工先把派单点名的 4 个形状实跑一遍**（`pe_fr4_precheck.py` ①），确认两份 `_package_of`
给出**同一个**值、且与派单逐字相符：

| `BACKEND /` 之下的相对路径 | 磁盘上存在 | `_package_of` 实跑值（两份一致） |
|---|---|---|
| `app/db/models/organisation.py` | ✅ | `('app', 'db', 'models')` |
| `app/db/models/__init__.py` | ✅ | `('app', 'db', 'models')` ← **与同目录普通模块同包，这一格是 `parts[:-1]` 的全部理由** |
| `app/domain/indicators.py` | ✅ | `('app', 'domain')` |
| `app/domain/prescription/match.py` | ❌（Task 2 才会出现） | `('app', 'domain', 'prescription')` |

**改法**：在两个文件的 `test_absolute_folding_matches_resolve_name` **末尾各加一段**
（purity 改后 `:313-362`、layering 改后 `:299-348`，**各 50 行**），**不新增测试函数**。
三件事：

1. **值断言**（派单要求 2）：`pkg_cases` 四行 `(相对路径, 正确的包, 错形状)`，逐格调
   `_package_of(BACKEND / rel)`，`!= 正确的包` 就进 `pkg_offenders`。
2. **错形状断言**（派单要求 3，硬规矩 #50 的红档）：同一格里 `== ("app","db","models",
   "organisation")` 一类**模块路径**也进 `pkg_offenders`。变异下这两条会**同时**触发
   （4 格值错 + 4 格「是模块路径」），fr4.3 的断言原文里 8 行都在。
3. **后果断言**（超出派单，见 fr4.8-②）：把 `_package_of` 的输出**直接喂给** `_absolute`，
   与 `importlib.util.resolve_name` 对拍 2 格 —— 这样「假绿」这件事是**跑出来的**、
   不只是写在断言消息里（硬规矩 #52 的精神：能跑的别只写成散文）。

`pkg_offenders == []` 的断言消息按派单要求 4 写明后果，**两个文件各写自己的那一份**
（派单给的那句「折成 `app.db.seed`、不再以 `app.seed` 开头」只在 layering 成立，见
fr4.7-③）：purity 侧写「`app/domain/x.py` 里的 `from ..seed import …` 折成
`app.domain.seed`、命中白名单前缀 `app.domain.` → 本文件的守卫假绿（`test_layering.py`
那一份同理：… `app.db.seed` …）」，layering 侧反过来。两段消息里的 4 个折算串**全部实跑过**
（`pe_fr4_r52.py`，见 fr4.6）。消息末尾**不写死 481**（那个数会随后续 Task 漂），
只写「而在本段断言加上之前，这么改一次全量测试都照样通过」，其依据是 fr4.3 的 M6。

「后果」两格的实跑值（`pe_fr4_compose.py`，正常 / 变异两列）：

| 源文件 + 写法 | `_package_of` 正常 | 折算（正常） | `_package_of` 变异后 | 折算（变异后） | purity 判定 | layering 判定 |
|---|---|---|---|---|---|---|
| `app/domain/indicators.py` + `from ..seed` | `('app','domain')` | `app.seed` | `('app','domain','indicators')` | `app.domain.seed` | RED → **GREEN（假绿）** | RED → **GREEN（假绿）** |
| `app/db/models/organisation.py` + `from ...seed` | `('app','db','models')` | `app.seed` | `('app','db','models','organisation')` | `app.db.seed` | RED → RED | RED → **GREEN（假绿）** |

`resolve_name('..seed', 'app.domain')` = `resolve_name('...seed', 'app.db.models')` =
`'app.seed'`，与正常列逐字相同 —— 即判据锚在 Python 自己的语义上，不是锚在我写的元组上。

**docstring 跟着改**（派单要求 5）：两个文件「本测试守不住什么（硬规矩 #39）」段的**第一条**
原文都是「``package`` 入参是**手写的**，故 `_package_of` 不在守卫范围内：谁把它改成返回
『模块名』而不是『包名』，本测试**照样全绿**」——**这一条现在不再成立**，已改成新的能力边界
（两个文件逐字同文，硬规矩 #51）：

```
* :func:`_package_of` 由本测试**末尾那一段**看着（Plan02 Ruling 54），但**只在枚举到
  的那 4 个形状上**：``app/db/models/organisation.py`` 与 ``app/db/models/__init__.py``
  （包深 3；两者必须给出**同一个**包——这一格正是 ``parts[:-1]`` 这个写法的全部理由）、
  ``app/domain/indicators.py``（包深 2）、``app/domain/prescription/match.py``（包深 3，
  Task 2 才会出现的形状；``_package_of`` 是纯路径运算、不碰文件系统，故可以先断言）。
  **没枚举进去的包深（包深 4 及更深）不被覆盖**；上面那 11 格矩阵的 ``package`` 入参
  仍是**手写的**，故矩阵与末尾那一段互不覆盖、谁也不替代谁。
```

第二、三条边界（不扫真仓 / 矩阵有限）逐字未动。

### fr4.2 Ruling 55 — 「三条守卫」的计数 ✅

**先 grep 确认那句的确切位置和措辞**（`pe_fr4_precheck.py` ④，不照抄派单的转述）：
`test_domain_purity.py` 模块 docstring 的**第 8 行**（= 文件第 8 行，shell 口径，基线
`be0f1af`）原文逐字是

```
三条守卫，Plan 02 Task 1 全部改写过一次，改动理由各写在对应测试的 docstring 里：
```

而该文件的 `test_*` 实测 **4 个**：`test_absolute_folding_matches_resolve_name` /
`test_domain_imports_stay_within_the_allow_list` / `test_domain_has_no_clock_or_file_access` /
`test_domain_has_no_filesystem_access`。改成（改后 `:8-11`，原句的其余部分逐字保留）：

```
本文件有 **4 个 ``test_*``**：**三条架构守卫** + 一条**辅助函数的单元测试**
（``test_absolute_folding_matches_resolve_name``，测的是 ``_absolute`` / ``_package_of``
这两个辅助函数，**不是第四条守卫**；Plan02 Ruling 46/54）。三条守卫 Plan 02 Task 1 全部
改写过一次，改动理由各写在对应测试的 docstring 里：
```

**同文件里另有 17 处「三条 / 第三条 / 两道」的表述，逐条核对过、全部未动**
（`pe_fr4_counts.py` ①，shell 口径行号绑定 `6784d57`；全文件正则 `三条|第三条|两道` 共命中
**19** 处，减去本轮新写的 `:8`/`:10` 两处即 17）：`:15`「三条都加 `len(scanned) >= 5` 的空转
守卫」、`:64`「第三条守卫仍是子串匹配」、`:68`「同时绕过时钟与 `open` 两道守卫」、
`:91`（断言消息）「三条守卫会一起假绿」、`:221`「三条的复现命令是同一条」（**指 fix round 3
那三种变异**，不是守卫）、`:377`/`:380`/`:388`/`:389`/`:392`/`:405`（基线守卫的合成树实测段）、
`:487`/`:525`/`:556`/`:569`（G1/G2/G3 探针实测表）、`:574`「第三条子串守卫」、
`:611`「子串黑名单，第三条守卫」。它们说的都是**那三条架构守卫**（或那三种变异），与
`test_*` 的个数无关，改了反而会把真话说错。

**`test_layering.py` 按派单要求一并 grep：无同类计数陈述，故未改。** 证据：该文件
`test_*` 实测 **2 个**，模块 docstring（`:1-47`）通篇用**单数**「本守卫」（`:18`「**本守卫
落地时抓到的 4 处 offender**」、`:29`「之后本守卫转绿」、`:35-36`「不在本守卫范围内」、
`:38`「**本守卫不覆盖什么**」），`4 处 offender` 数的是 offender 而不是守卫条数；
正则 `[一二三四五六七八九十]+\s*条|三条|两道` 在该文件模块 docstring 内**没有**任何关于
守卫条数的命中。读者数出 2 个 `test_*` 也不会与「本守卫」这个单数主语冲突，故派单那句
「如果有同类问题一并修」的条件**不成立**，我没改（改了就是无中生有的 churn）。

### fr4.3 变异验收（8 相位，两份分别做，硬规矩 #50 / #51 / #53）

`pe_fr4_mutation.py`（rc 0）。**派单 ⑤ 的要求逐字落地**：每次变异都在**剥 docstring 后的
`ast.dump`** 上确认「真的改了代码」，并**另加一组「只改 docstring」的对照**证明这个口径
不恒真（控制者上一轮踩过的 #72 形态）。每次变异后按**字节**还原并核 sha256。

先跑变异算子的 AST 自证（两个文件 × 3 个算子）：

```
purity    parts[:-1] -> parts    文本变了=True 剥docstring后AST变了=True（应为 True）OK
purity    等价改写               文本变了=True 剥docstring后AST变了=True（应为 True）OK
purity    只改 docstring         文本变了=True 剥docstring后AST变了=False（应为 False）OK
layering  parts[:-1] -> parts    文本变了=True 剥docstring后AST变了=True（应为 True）OK
layering  等价改写               文本变了=True 剥docstring后AST变了=True（应为 True）OK
layering  只改 docstring         文本变了=True 剥docstring后AST变了=False（应为 False）OK
```

| 相位 | 变异 | purity | layering | pytest |
|---|---|---|---|---|
| **M0** | 不变异（**对照 GREEN**，#53） | GREEN ✅ | GREEN ✅ | `2 passed`，rc 0 |
| **M1** | `parts = py.relative_to(BACKEND).with_suffix("").parts` + `return tuple(list(parts)[: len(parts) - 1])`（**语义等价、AST 变了**，#53 的「尺子不恒红」对照） | GREEN ✅ | GREEN ✅ | `2 passed`，rc 0 |
| **①（M2）** | `parts[:-1]` → `parts`，**只变异 layering** | **GREEN** ✅（未被变异） | **RED** ✅ | `1 failed, 1 passed`，rc 1 |
| **②（M3）** | `parts[:-1]` → `parts`，**只变异 purity** | **RED** ✅ | **GREEN** ✅（未被变异） | `1 failed, 1 passed`，rc 1 |
| **M4** 额外 | 同一变异，**两份都变异** | **RED** ✅ | **RED** ✅ | `2 failed`，rc 1 |
| **M5** 额外 | 两份都变异，但只跑**旧的 4 条守卫**（`-k not test_absolute_folding_…`） | — | — | `4 passed, 2 deselected`，**rc 0** |
| **M6** 额外 | **基线 `be0f1af`** 的两份文件 + 同一变异，跑**全量** | — | — | **`481 passed in 105.24s`，rc 0** |

**失败项 0 / 8**。「只变异一份时另一份保持绿」（①②）是硬规矩 #51 的正面证据。**M5/M6 是
Ruling 54 那个口子在改前真的存在的实测**：变异下 4 条架构守卫**无感**（M5，rc 0），而在
**基线**上做同一变异、全量 **481 passed / rc 0**（M6）—— 即「守卫假绿、而全部 481 条测试
仍然通过」不是推理，是跑出来的。

**M6 的基线取法**（按账本记的坑做归一化）：`git show be0f1af:<path>` 取到内存，
LF → CRLF 后落盘。亲验：purity blob(LF) **36863 B** → CRLF **37435 B**（差 **572** =
CRLF 行数 572）、sha256[:16] `dffa51f460826436`；layering blob(LF) **21803 B** →
CRLF **22144 B**（差 **341** = CRLF 行数 341）、sha256[:16] `a5afd212bd485ef4`。
两个 sha 与本轮**开工前**亲测的工作树值逐字相符（脚本里把这两个值**写死成期望值**再
`assert`，不是拿 `git show` 跟自己比，避免循环自证）。

**红的是哪条断言**（`check()` 从 pytest 输出里抓的断言消息本体，不是收集错误；M2 与 M3
的 10 行 offender 逐字相同，只是红的那一份不同）：

```
E  AssertionError: _package_of 返回的不是**包**（Plan02 Ruling 37/54）：parts[:-1] 写成 parts 会让它返回**模块路径**，…
E    _package_of(BACKEND / 'app/db/models/organisation.py') = ('app', 'db', 'models', 'organisation')，应为**包** ('app', 'db', 'models')
E    _package_of(BACKEND / 'app/db/models/organisation.py') = ('app', 'db', 'models', 'organisation') 是**模块路径**、不是包（parts[:-1] 被写成了 parts）
E    _package_of(BACKEND / 'app/db/models/__init__.py') = ('app', 'db', 'models', '__init__')，应为**包** ('app', 'db', 'models')
E    _package_of(BACKEND / 'app/db/models/__init__.py') = ('app', 'db', 'models', '__init__') 是**模块路径**、不是包（parts[:-1] 被写成了 parts）
E    _package_of(BACKEND / 'app/domain/indicators.py') = ('app', 'domain', 'indicators')，应为**包** ('app', 'domain')
E    _package_of(BACKEND / 'app/domain/indicators.py') = ('app', 'domain', 'indicators') 是**模块路径**、不是包（parts[:-1] 被写成了 parts）
E    _package_of(BACKEND / 'app/domain/prescription/match.py') = ('app', 'domain', 'prescription', 'match')，应为**包** ('app', 'domain', 'prescription')
E    _package_of(BACKEND / 'app/domain/prescription/match.py') = ('app', 'domain', 'prescription', 'match') 是**模块路径**、不是包（parts[:-1] 被写成了 parts）
E    app/domain/indicators.py 里的 from ..seed import …：用 _package_of 的结果折算得到 'app.domain.seed'，而 resolve_name('..seed', 'app.domain') = 'app.seed'
E    app/db/models/organisation.py 里的 from ...seed import …：用 _package_of 的结果折算得到 'app.db.seed'，而 resolve_name('...seed', 'app.db.models') = 'app.seed'
```

**三重还原取证**（脚本末尾实跑）：

```
purity    sha256[:16]=440f7167610df187 与原始一致=True 41613 字节 CRLF=634 裸LF=0
layering  sha256[:16]=50d776680defc25e 与原始一致=True 25789 字节 CRLF=396 裸LF=0
git status --short:  M backend/tests/architecture/test_domain_purity.py
                     M backend/tests/architecture/test_layering.py
（= 本轮自己的两处改动；相位之间的还原一律核 sha256 一致，未用 git checkout / git restore）
```

### fr4.4 硬规矩 #32 闸门（本轮形态：逐顶层单元 + docstring 全量清点 + 注释全量清点 + 四组对照）

`pe_fr4_astdiff.py`（rc 0）。本轮**没有新增顶层单元**，故自证的形状与 fr3 不同：预期
「有差异的顶层单元」= `test_absolute_folding_matches_resolve_name`（两个文件各一）。

```
=== ⓪ 改动面 ===
   git diff --name-only HEAD(73313f7):
      backend/tests/architecture/test_domain_purity.py
      backend/tests/architecture/test_layering.py
   合计 2 个文件；生产代码（backend/app/**）命中 = 0
   git diff --numstat HEAD:  70 8 purity / 61 6 layering
   git diff --name-only be0f1af -- backend/      = 那两个守卫文件
   git diff --name-only be0f1af -- backend/app/  = []（禁区，必须空）

=== ① 剥 docstring 后逐顶层单元比（基线 be0f1af）===
test_domain_purity.py：_domain_files / _assert_not_empty / _imported_modules / _package_of /
   _absolute / _is_allowed / test_domain_imports_stay_within_the_allow_list / _dotted /
   _hit_forbidden_call / test_domain_has_no_clock_or_file_access /
   test_domain_has_no_filesystem_access / <module-level>  → **全部「未动」**
   AST 变了  test_absolute_folding_matches_resolve_name
   → 有差异的顶层单元 = ['test_absolute_folding_matches_resolve_name']
test_layering.py：_py_files / _package_of / _absolute / _imported_modules / _is_forbidden /
   test_production_layers_never_import_app_seed / <module-level>  → **全部「未动」**
   AST 变了  test_absolute_folding_matches_resolve_name
   → 有差异的顶层单元 = ['test_absolute_folding_matches_resolve_name']
```

**⚠️ 派单 §3 预期的 `<module-level>` 实测「未动」**：尺子对 `ast.Module` 也剥 docstring，
故模块 docstring 的改动**不会**让 `<module-level>` 报 DIFF（派单用「若模块 docstring 算在
里面」限定过，这里给出实测答案：**不算**）。为免这个盲区藏东西，脚本另立两节把 AST 看不见
的两类东西全量清点：

```
=== ② docstring 全量清点 ===
test_domain_purity.py  变了 3 处：<module>（Ruling 55 的计数）、_absolute（fr4.8-① 的折算串更正）、
                       test_absolute_folding_matches_resolve_name（「守不住什么」第一条）
                       其余 9 个单元（含 _package_of）逐字未动
test_layering.py       变了 1 处：test_absolute_folding_matches_resolve_name
                       其余 6 个单元（含 <module>、_package_of、_absolute）逐字未动
（四处 diff 全文见 fr4_probes/OUT_astdiff.txt 的 ② 段，都是 unified diff 逐行贴的）

=== ③ 注释全量清点（AST 对注释同样是盲的）===
test_domain_purity.py  注释条数 36 -> 46：改了 1 处（2 行 -> 3 行，fr4.8-③ 的「就地 import」注释）
                       + 新增 9 条（全在 Ruling 54 那一段里）
test_layering.py       注释条数 39 -> 49：同上
```

```
=== ④ 既有 5 条守卫 assert 逐字对比 ===
   test_domain_imports_stay_within_the_allow_list    assert 1→1 逐字相同=True
   test_domain_has_no_clock_or_file_access           assert 1→1 逐字相同=True
   test_domain_has_no_filesystem_access              assert 1→1 逐字相同=True
   test_production_layers_never_import_app_seed      assert 2→2 逐字相同=True
   既有守卫 assert 合计 5 条，全部逐字未动
   新测试里的 assert 条数（工作树）：purity 3、layering 3（基线各 2；多的那一条就是 Ruling 54
   的 `assert pkg_offenders == []`。派单只禁改**既有 5 条守卫 assert** 的语义，未禁在已有的
   那条测试里加断言，且 passed 数不变）

=== ⑥ 对照组（硬规矩 #53，两个文件各跑一遍，全部相符）===
   ① 注入 _package_of 语义变异（parts[:-1] -> parts）→ 报 DIFF 的单元 = ['_package_of']（尺子能报 DIFF）
   ② 基线自比                                        → 报 DIFF 的单元 = []（尺子能报 SAME）
   ③ 只改 _package_of 的 docstring：AST 报 DIFF=True、剥掉后 = []（尺子真的在剥 docstring）
   ④ 只改一行**注释**：AST 报 DIFF=False、逐单元 = []（**尺子对注释是盲的** → 故有 ③ 段）
```

### fr4.5 硬规矩 #51 闸门（两份 `_package_of` / `_absolute` 仍逐字相同）

`pe_fr4_astdiff.py` ⑤ 段：

```
_package_of    两份 identical(excl docstring) = True
               test_domain_purity.py  与基线逐字相同 = True
               test_layering.py       与基线逐字相同 = True
_absolute      两份 identical(excl docstring) = True
               test_domain_purity.py  与基线逐字相同 = True
               test_layering.py       与基线逐字相同 = True
```

**份数清点（硬规矩 #51 要求列出）**：`_package_of` **2 份**、`_absolute` **2 份**，
本轮**都没改代码**（只改了 purity 侧 `_absolute` 的 docstring，layering 侧逐字未动）。
新增的那一段断言也**各写了一份**：`pe_fr4_counts.py` ④ 段把两段逐行比过，
**各 50 行、只有 4 行不同**，而那 4 行正是断言消息里「本文件 / 那一份」的主语与折算串
（purity 侧主写 `app.domain.seed` + 命中白名单前缀、layering 侧主写 `app.db.seed` +
不再以 `app.seed` 开头，各自把对方的形状作为「那一份同理」附在后面）。4 个形状、
2 格后果对拍、`pkg_offenders` 的累积逻辑全部同文。故 #51 的适用面现在是「两份实现 +
两份回归测试 + 两份 `_package_of` 断言段」= **6 处**，每处都写了两次。

### fr4.6 硬规矩 #52 闸门（本轮写进 docstring / 断言消息的每个值都真跑过）

`pe_fr4_r52.py`（rc 0）：

```
=== purity _absolute docstring 里本轮新写的那两个值 ===
  _absolute("seed", 2, ("app", "domain", "ind")) -> 'app.domain.seed'   docstring 写的 'app.domain.seed'  相符=True
  _is_allowed('app.domain.seed')                 -> True                docstring 写的 True               相符=True

=== 两个断言消息里写的折算串（各文件写自己那一份）===
  purity    app/domain/x.py      from ..seed  import …  pkg=('app','domain','x')          folded=app.domain.seed  GREEN  相符=True
  layering  app/db/models/x.py   from ...seed import …  pkg=('app','db','models','x')     folded=app.db.seed      GREEN  相符=True
  （两条都是 GREEN，正是断言消息声称的「假绿」）

=== layering _absolute docstring 原有的那句（本轮未改，复核仍成立）===
  _absolute('seed', 3, ('app','db','models','x')) -> 'app.db.seed'  _is_forbidden=False  相符=True
```

另把 `pe_fr4_precheck.py` ② 段的结果记在这里：**两个 `_package_of` docstring 里原有的 5 个
举例全部是真跑过的输出**（`app/domain/x.py` → `('app','domain')`、`app/domain/sub/x.py` →
`('app','domain','sub')`、`app/pipeline/x.py` → `('app','pipeline')`、`app/db/models/x.py` →
`('app','db','models')`、`app/db/models/__init__.py` → `('app','db','models')`，两份
`_package_of` 各跑一遍、10/10 相符），故 Ruling 54 要求断言的那 4 格与 docstring 的举例
**互不矛盾**。

### fr4.7 我发现的派单错误（5 条成立 + 1 条账本错误 + 2 条不计入）

按派单 §4.7 逐条给实测证据。**没有一条导致判据不可满足**，两件事我全部按派单做了。
按 Ruling 45/51 的口径：不成立的我不认（⑦⑧），成立的我不替派单辩（①–⑥）。

**① 「读最后一节 `#### Task 1 fix round 3 — 控制者亲验`（**Ruling 48–57**）」→ 账本里
根本没有 Ruling 48；那一节含 Ruling 49–57（9 条）。（成立，计一条）**

python 正则扫 `progress.md` 全文（617 行），`Ruling (\d+)` 在 40..57 区间**出现过**的编号是
`[40,41,42,43,44,45,46,47,49,50,51,52,53,54,55,56,57]`，**48 缺失**；`**Ruling 47` 在 `:505`、
`**Ruling 49` 在 `:558`，编号直接跳过 48。整个 sdd 目录里 `Ruling 48\b` 只命中 **1** 处，在
`task-1-review-package.md:4017`，那是 **Plan 01** 的 Ruling 48（一段 `test_clean.py` 的 diff
里写着 `# ② 同学号同批次两行 → 去重，field = WHOLE_RECORD（Ruling 48/50）`），与 Plan 02 无关。
影响：无（我按 49–57 读了那一节；派单同一句里的「#48 在 `:172`」指的是**硬规矩** #48，
两套编号撞在同一个数字上，这也是它容易被写错的原因）。**这是硬规矩 #54 的又一次适用**
（编号/计数错），形态与 Ruling 49/50/53 同族：把一个清单当成连续的，而它有缺口。

**② 「上一轮新增的 `test_absolute_folding_matches_resolve_name` 里，`package` 入参是
**手写的四元组**」→ 实测矩阵里没有任何四元组。（成立，计一条）**

AST 抽出两个文件的 `cases` 字面量：

```
test_domain_purity.py  cases 行数 = 11  每行元素数 = [5]  package 元组的长度分布 = {2: 9, 3: 2}
test_layering.py       cases 行数 = 11  每行元素数 = [5]  package 元组的长度分布 = {2: 7, 3: 4}
```

**两种读法下「四元组」都不成立**：`package` 自己是 **2 元或 3 元**（没有 4 元），而
**case 行是 5 元**（`(module, level, package, name, 期望颜色)`）。账本 Ruling 45 立的口径是
「以 `(module, level, package, name)` 四元组为参数」，fr3 落地时另加了颜色列 → 5 元。
影响：无（`package` 是手写的这一点完全成立，正是 Ruling 54 的立意）。
**这与 ① 同为硬规矩 #54 的适用面**（计数）。

**③ 派单给两个文件描述了**同一个**后果，而它只在 layering 成立、在 purity 实测是 RED。
（成立，计一条 —— Ruling 51 的同型复发）**

派单 §2 Ruling 54 的背景段与要求 4 都写：「让 `_package_of` 返回模块路径，`app/db/models/x.py`
里的 `from ...seed import …` 就会折成 `app.db.seed`、不再以 `app.seed` 开头 → **守卫假绿**」，
并要求把它写进**两个文件**的断言消息。实测（`pe_fr4_compose.py`、`pe_fr4_precheck.py` ③）：

| 那一格 | layering 的 `_is_forbidden('app.db.seed')` | purity 的 `_is_allowed('app.db.seed')` |
|---|---|---|
| `app/db/models/x.py` + `from ...seed` + `_package_of` 变异 | `False` → **GREEN（假绿）✅** | `False` → **RED**（而且 purity 只扫 `app/domain`，这一格根本在它管辖之外） |

**这与 Ruling 51 是同一个形态**（「派单给两个文件指定了同一张矩阵，却写了一个只在一个文件里
成立的判定」），而控制者在 Ruling 51 里已经明说这不是笔误、是复发。处置同 fr3：**两份断言
消息各写自己那一份的后果**，并把对方的形状作为「那一份同理」附在后面（purity 侧写
`app.domain.seed` + 命中白名单前缀；layering 侧写 `app.db.seed` + 不再以 `app.seed` 开头），
两个串都实跑过（fr4.6）。

**④ 「`Read` 工具的行号在本仓部分区段系统性少 1」→ 实测偏移是 **0 / −1 / −2**，
而且 `Read` **对自己都不自洽**。（成立，「少 1」这个量级错；结论仍成立且更该遵守）**

同一个文件、同一次会话里两次 `Read` 调用，对**同一行内容**给出了不同的行号
（`progress.md` 全程未被我改动过）：

| 文件 | 区段锚点（内容） | python 行号 | `Read` 显示的行号 | 偏移 |
|---|---|---|---|---|
| `progress.md` | `**补硬规矩 #48：派单前必须…` | 172 | 172（`Read offset=160`） | **0** |
| `progress.md` | `Ruling 21 记的是 BASE 20.48/20.85 s…` | 300 | 300（`Read offset=300`） | **0** |
| `progress.md` | `亲验清单（全部本机实跑）：` | **450** | **449**（`Read offset=310`）／**450**（`Read offset=450`） | **−1 / 0 ← 自相矛盾** |
| `progress.md` | `#### Task 1 fix round 2 — 控制者亲验…` | **446** | **445**（同一次 `Read offset=310`） | **−1** |
| `progress.md` | `**→ 补硬规矩 #54：更正计划正文时…` | **588** | **587**（`Read offset=488`） | **−1** |
| `test_domain_purity.py` | `def _package_of` | 117 | 117 | **0** |
| `test_layering.py` | `def _package_of` | 70 | 68 | **−2** |
| `test_layering.py` | `def _is_forbidden` | 174 | 172 | **−2** |

另：`Read` 对 `task-1-report.md` 直接报「文件只有 **1031** 行」并拒绝 `offset >= 1031`，
而该文件实测 **189916 字节 / 2616 个 LF / 0 个 CRLF**（fr3 也撞到同一个 1031，当时实测
2152 行）——即 `Read` 连**总行数**都报错了，本轮读前任报告全程只能用 python。
影响：无（我全程用 shell 口径，派单也已经这么要求了）。**但结论比派单说的更强**：偏移
**不是常数**（同一文件里 0 与 −1 并存、跨文件还有 −2），`Read` 甚至对同一行给出过两个
不同的号，故任何「把 `Read` 行号 +1」的换算都不安全，唯一安全的做法就是派单已经给出的
那条——一律 shell 口径。⚠️ 这句话同时是 `task-1-brief.md` Global Constraints 第 6 条与
`Document/2026-10-06-实施计划02-智能处方引擎.md:24` 的**原文**（「`Read` 工具的行号在本仓
部分区段**系统性少 1**，已四次误导」），不只是本轮派单的转写，故要改得改两处，
而两处都在我的禁区里。

**⑤ 派单让我在账本里 grep 硬规矩 **#30**，而 `progress.md` 里 `硬规矩 #30` 命中 **0** 处。
（成立，计一条 —— 与 ① 同族）**

派单 §1.1 原文：「请 grep `硬规矩 #` 把 **#30** / #32 / #35 / #39 / #42 / #50 / #51 / #52 /
#53 / #54 全部读一遍（它们散在全文各处…）」。实测各号在 `progress.md` 里的命中行：

| 号 | 命中行 | 号 | 命中行 |
|---|---|---|---|
| **#30** | **（无）** | #42 | 62, 183, 185, 296, 300, 400, 455 |
| #32 | 467 | #50 | 290, 497, 538 |
| #35 | 261 | #51 | 409, 466, 539, 554 |
| #39 | 55, 235, 296, 387, 507, 540, 594 | #52 | 411, 578 |
| #48 | 172（定义行） | #53 | 509, 521 |
| #49 | 265（定义行） | #54 | 588（定义行） |

`硬规矩 #30` 只出现在 `task-1-brief.md`（Global Constraints 第 6 条）、
`Document/…计划02…:24`、`task-1-report.md` 与那份陈旧副本里，**账本里一次都没有**
（`硬规矩 #37` 在账本里命中 1 处）。#30/#32/#35/#39/#42 都是 **Plan 01** 立的规矩，
账本里只有引用、没有「补硬规矩 #N」的定义行（#48–#54 才各有 1 行定义）。
影响：无（我按 brief 与 `Document/` 里的原文读了 #30，并按账本里的引用逐处读了其余各号）。
**「它们散在全文各处」对 #30 不成立**，而且 #30 恰好是本轮最该遵守的那条（行号口径）——
与 Ruling 44（把 #50 指到阅读范围之外）同型。

**⑥ 账本 Ruling 42 那句「`:139` 与 `:246` 说的是 `app.domain.seed.generate`（`startswith`
为 True，**正确**），只有 `:167` 是错的」→ 对 `:139` 不成立。（成立；这是**账本**里的错，
不是本轮派单里的错，但它是本轮我改动的直接依据，故一并报）**

`pe_fr4_ruling42b.py` 实跑：`_absolute("seed", 2, ("app","domain","ind"))` =
**`'app.domain.seed'`**，与 `resolve_name('..seed', 'app.domain.ind')` 逐字相同；
要折出 `'app.domain.seed.generate'` 必须把写法换成 `from ..seed.generate import X`
（`module` 带点），而老 `:139` 写的是 `from ..seed import generate`。**关键是动词**：
老 `:139` 用的是「就会**折成**」= `_absolute` 的返回值 → 串错；老 `:246`（今 `:422`）用的是
「**解析到**的是」= 这句 import 语义上取到的对象，`resolve_name('..seed.generate',
'app.domain.sub')` 实跑就是 `'app.domain.seed.generate'` → **对**，本轮未动。
Ruling 42 只核了「那个串是否命中 `app.domain.` 前缀」（True），**没核「`_absolute` 对
`from ..seed import generate` 是否真产出那个串」**（不产出：`generate` 住在 `node.names` 里、
不进折算串，这正是 Ruling 36）；fr3 的实现者照抄了这句判断、还在报告 fr3.1 里写「要求不动」。
处置：见 fr4.8-①（就近更正 `:139`，`:422` 那一处保留）。

**⑦ 派单 §3 预期「`<module-level>`（若模块 docstring 算在里面）」→ 实测不算。（不计入：
派单已用「若」限定，只是把实测答案报回来）**

见 fr4.4：尺子对 `ast.Module` 也剥 docstring，故模块 docstring 的改动不会让 `<module-level>`
报 DIFF；实测有差异的顶层单元 = `['test_absolute_folding_matches_resolve_name']`
（两个文件各一）。为免这个盲区藏东西，已另立 docstring 与注释两节全量清点，并用对照 ④
把「尺子对注释是盲的」显式跑出来。

**⑧ 派单 §2 要求 4 那个 M1 例子是**片段**、不是可直接替换的一行。（不计入：派单用「例如」
限定、意图清楚）**

派单写「例如 `parts[:-1]` → `tuple(list(parts)[: len(parts) - 1])`」，而实现是单行
`return py.relative_to(BACKEND).with_suffix("").parts[:-1]`，里面**没有** `parts` 这个名字，
照字面替换会 `NameError`。我的 M1 实现是先绑一个局部名再返回
（`parts = py.relative_to(BACKEND).with_suffix("").parts` +
`return tuple(list(parts)[: len(parts) - 1])`），AST 变了、语义等价、两条仍绿。

**其余我逐条核过、成立**的派单陈述（列出来表示核过，不是凑数）：分支名与 HEAD `73313f7` ✓、
`73313f7` 只比 `be0f1af` 多一个 `Document/` 的文档 commit 且两个守卫文件自 `be0f1af` 起未变 ✓
（`git diff --name-only be0f1af 73313f7` 只含那个文档）、`core.autocrlf=true` ✓、
Python 3.11.1 / 无 venv ✓、硬规矩 #48 在 `progress.md:172` / #49 `:265` / #50 `:290` ✓
（另 #51 `:409`、#52 `:411`、#53 `:509`、#54 `:588`；#32 `:467`、#35 `:261`、
#39 七处、#42 七处；**#30 零处**，见 ⑤）、`task-1-brief.md` Global Constraints
**10 条**顶层 bullet（0 条缩进子项）✓、`fr3_probes/` **11 个**脚本 ✓、
`_package_of` 的实现串 `return py.relative_to(BACKEND).with_suffix("").parts[:-1]` 在两个
文件里各命中恰 1 次、逐字相同 ✓、`_package_of` 不碰文件系统（不存在的路径照样算）✓、
4 个点名形状与期望值 ✓（fr4.1 的表）、`test_layering.py:70-77` 的 docstring 已解释
`parts[:-1]` 而此前没有断言 ✓（shell 口径 `:70` 是 `def`、`:71-77` 是 docstring、`:78` 是
`return`）、模块 docstring「三条守卫」而文件里有 4 个 `test_*` ✓、
`test_layering.py` 有 2 个 `test_*` ✓、基线 481 passed ✓、基线 domain `399/0/114/0/100%` ✓、
`--cov` 下 `480 passed, 1 skipped` 且 skip 在 `test_backfill.py:182` ✓、
既有 5 条守卫 assert（purity 1+1+1、layering 2）✓、上一轮两份 `_absolute`
`identical(excl docstring) = True` ✓、`git show` 的 blob 是 LF 版且差值 = CRLF 行数 ✓
（本轮实测 purity 差 572、layering 差 341；派单引的 36103/36666/563 是 fr3 过程中的一个
中间态，机制描述正确）、Ruling 54 背景段那句「守卫假绿、而全部 481 条测试仍然通过」✓
（fr4.3 的 M6 在基线上实测 481 passed / rc 0）、`Read` 工具不可信 ✓（但我撞上的是**写**
侧的 9 次静默失败，见开头那条 ⚠️）。

### fr4.8 超出派单的改动（主动披露，3 处 + 1 处纯风格，全部在这两个守卫文件内）

**① 更正 purity 侧 `_absolute` docstring 里的一处折算串错话（改后 `:141-146`）。**
即 fr4.7-⑥ 那条。原文「`app/domain/x.py` 里的 `from ..seed import generate` 就会折成
`app.domain.seed.generate`、命中白名单前缀 `app.domain.` → 守卫当场假绿」，实跑折成
`app.domain.seed`。改成：

```
就会折成 ``app.domain.seed``（**不是** ``app.domain.seed.generate``：``generate`` 住在
``node.names`` 里、不进折算串，Plan02 Ruling 36；本机 Python 3.11.1 实跑
``_absolute("seed", 2, ("app", "domain", "ind"))`` -> ``'app.domain.seed'``、
``_is_allowed('app.domain.seed')`` -> ``True``）、命中白名单前缀 ``app.domain.`` →
**守卫当场假绿**
```

**结论（假绿）没改，只改串**，与 Ruling 42 的处置口径一致。**为什么本轮就近改而不是留给
控制者**：① 本轮正要给 `_package_of` 加断言，而新断言消息里写的就是 `app.domain.seed`——
不改就会让**同一个文件**里「断言消息说 `app.domain.seed`、docstring 说
`app.domain.seed.generate`」自相矛盾（Ruling 32 的就近修正先例：「两处都是为了让…在同一个
文件内不自相矛盾」）；② 这段 docstring 正是 Ruling 37 说的「`_package_of` 的规格说明」，
本轮的主题就是给它加守卫，留一个假的规格说明在里面与本轮的立意直接冲突。
**layering 侧同一句话写的是 `app.db.seed`、实跑相符，逐字未动**（fr4.4 ② 段实测）；
**今 `:422`（老 `:246`）那一处「解析到的是 `app.domain.seed.generate`」也未动**——它的动词
是「解析到」而不是「折成」，实测相符（fr4.7-⑥）。改完全仓 grep「白名单前缀」在 purity 里
命中 **3** 处：`:145`（本轮更正后的那句）、`:358`（本轮新写的断言消息）、`:422`（未动，正确）。

**② 新断言里多写了一段「后果对拍」（两个文件各 14 行，purity `:341-354`、
layering `:327-340`）。**
派单要求 1–5 只要求断言 `_package_of` 的**值**（等于对的 + 不等于错的）。我另加一段把
`_package_of` 的输出**直接喂给** `_absolute`、与 `resolve_name` 对拍 2 格
（`app/domain/indicators.py` + `from ..seed`、`app/db/models/organisation.py` + `from ...seed`）。
理由：派单要求 4 让「后果」只出现在**断言消息**里，而消息是散文；这一段让后果**可跑**，
且判据锚在 `resolve_name` 上（与本测试已有的 11 格同一个锚，不是新造一张表），
与 Ruling 46「判据不要抄表」的立意一致。成本 14 行 × 2 份，不新增测试函数、不新增文件。

**③ 两处「就地 import」注释的精度修正（每个文件 2 行 → 3 行）。**
原文「模块级 import 会改动本文件的 `<module-level>`，而**本轮**的改动面被钉死在
『**新增**这一条测试函数』之内（Plan02 Ruling 46）」——那条函数是 fix round 3 新增的、
本轮只是往里加一段，故「本轮」「新增」都不再成立。改成「…故这条测试自 fix round 3 起就把
import 留在函数体内、改动面也一直钉死在『这一条测试函数 + docstring』之内（Plan02 Ruling
46/57）」。`import importlib.util` 本身**维持在函数体内未动**（Ruling 57）。
**⚠️ 注释不进 AST**，逐顶层单元的自证对它完全盲（fr4.4 对照 ④ 实测），故这类改动必须靠
fr4.4 ③ 段的注释全量清点来交代，不能只贴 AST 自证。

**④ 一处纯风格**：去掉一个没有占位符的 `f` 前缀（`f"（parts[:-1] 被写成了 parts）"` →
`"（…）"`，两个文件各一处）。它在同一条隐式拼接里，AST 合并成一个 `JoinedStr`，故
`git diff --numstat` 的增删行数不变（仍是 purity `70 8`、layering `61 6`）。
本项目没有配 linter（`backend/pyproject.toml` 里只有 pytest 与 setuptools 配置），
故这不是修 lint，只是不留一个无意义的 `f`。

### fr4.9 关切清单（3 条）

**C-fr4-1【低 → 建议记进 Task 2 预检清单】`_package_of` 的断言仍是手写枚举的 4 格，
Task 2 建了子包之后没人会被提醒去加行。** — 自己重新推导

判据是字面元组（不是 `resolve_name` 那种外部锚），故它**不会过期成假绿**（多加一格就是多一格
覆盖，少一格只是少覆盖），但**也没人会收到提醒**。Task 2 会新建 `app/domain/prescription/`，
届时 `app/domain/prescription/match.py` 从「今天不存在的形状」变成真仓里真实存在的文件，
而矩阵里包深 3 的真实绿档也会多起来。Ruling 56 已经把「扫真仓所有 `ImportFrom` 逐个对拍
`resolve_name`」转给 Task 2，那条方案会**顺带**把 `_package_of` 全覆盖（因为它必须先调
`_package_of` 才能得到 `package`）；建议在 Task 2 的预检清单里明确写一句
「若不做全仓扫描，则至少把 `_package_of` 的断言换成扫真仓每个 `.py`、与
`py.relative_to(BACKEND).parent.parts` 对拍」——那是**非同源**判据（一边是
`with_suffix("").parts[:-1]`、一边是 `.parent.parts`，两种写法对 `__init__.py` 给出同一个
结果，正是这一格要守的东西），且自动跟进以后出现的每一个深度。

**C-fr4-2【低 → 账本自身】Ruling 编号在 48 处有缺口，引用时容易错一位。** — 自己发现

见 fr4.7-①。这不是本轮派单独有的问题：只要编号有洞，任何「Ruling N–M」的区间写法都可能
把不存在的号包进去。建议在 `progress.md` 里补一行（例如在 Ruling 47 之后）
「**Ruling 48 号未用**（编号跳过，无内容）」，成本一行，能挡住下一次同类错误。
`progress.md` 是控制者的账本（且在 gitignore 的 `.superpowers/` 里），对我是禁区，
故本轮**未动**，只记下转给控制者。同一族的问题还有 fr4.7-⑤（硬规矩 #30 在账本里 0 命中，
而派单让人去账本里 grep 它）。

**C-fr4-3【低 → 流程】两份重复代码的维护成本本轮又付了一次，且第一次付在「断言段」上。** — 自己重新推导

Ruling 33 裁「本计划内不抽公共模块」，fr1 的延后 Minor 也记了「维护成本极低的判断偏乐观」。
本轮的具体代价：同一段 50 行断言在两个文件里各写一份，其中**只有 4 行不同**（fr4.5 实测），
外加改完后要再跑一次「两份是否仍逐字相同」的闸门。Ruling 33 的三个理由（语义故意不同 /
只有两个文件 / 抽出来会多一个没人守的助手模块）本轮**依然成立**，我不申请推翻；
只是把「重复的账」再记一笔：Plan 03 若加第三个架构守卫，`_package_of` + `_absolute` +
回归测试 + `_package_of` 断言段 = **4 段 × 3 份 = 12 处**要同步，那时抽公共模块的收益会
明显盖过成本。

### fr4.10 本轮**没做**的事

- 没动任何生产代码：`git diff --name-only be0f1af HEAD -- backend/app/` 命中 **0**；
  `git diff --name-only 73313f7` 只含两个守卫文件。
- 没动 `backend/tests/` 下的其他文件、没动 `backend/data/`、没动 `Document/`
  （`73313f7` 那个文档 commit 是控制者的，本轮未再动它一个字节；fr4.7-④ 指出的
  `Document/…:24` 那句「系统性少 1」也在禁区里，未动）。
- **没新增测试函数**：`tests/architecture` 仍 **6 passed**、全量仍 **481 passed**
  （与基线逐字相同）。
- 没改既有 5 条守卫 `assert` 的语义（fr4.4 ④ 段逐字比过：1+1+1+2 = 5 条，全部
  `逐字相同=True`）。
- 没改 `_package_of` / `_absolute` 的**代码**（fr4.4 ⑤ 段：两份都与基线逐字相同）；
  只改了 purity 侧 `_absolute` 的 docstring 一处（fr4.8-①）。
- 没改 `test_layering.py` 的模块 docstring（grep 无同类计数陈述，见 fr4.2）。
- 没动 purity `:422`（老 `:246`）那处「解析到的是 `app.domain.seed.generate`」——它的动词是
  「解析到」、实测相符（fr4.7-⑥）。
- 没把 `import importlib.util` 挪到模块级（Ruling 57 维持）。
- 没把 `_package_of` / `_absolute` 抽成公共模块（Ruling 33 仍有效，见 C-fr4-3）。
- 没给 `FORBIDDEN_IO` 补 `__import__(`（Ruling 47 已判延后 Minor）。
- 没做 Ruling 56 转给 Task 2 的「扫真仓所有 `ImportFrom` 逐个对拍」（本轮不做）。
- 没造合成树、没重定向任何守卫模块的全局（`_package_of` 是纯路径运算，不需要）；
  没跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`（禁区）。
- 没 `git push`；`git checkout` / `git restore` / `git switch` **一次都没用**。
- 没动 `fr3_probes/` 里的 11 个脚本（本轮只**参照**它的变异/还原写法，另写了 `fr4_probes/`
  的 13 个）。
- 没改 `progress.md`（账本）与 `task-1-brief.md`：C-fr4-2 与 fr4.7-④⑤ 指出的三处都在
  我不可动的文件里，只报不改。
- 没删那份被工具写坏的 `fr4_probes/SECTION_fix_round_4.md`：它是「工具报成功而磁盘未写」
  的物证（sha256[:12] `a72f50f3c91d`、44302 B、仍是第一版内容），留着比删掉有用。

### fr4.11 报告的追加方式与自检（含一次我自己的断言写错）

追加由 `pe_fr4_report.py` 做：先读全文、记下 sha256 与全部 `##`/`###`/`####` 标题清单，
再 `旧文（去尾换行）+ 空行 + 本节` 落盘。**落盘前**有一道草稿落盘闸门（就是它抓到了那次
`Write` 静默失败）：13 个新串必须全命中、6 个旧串必须 0 残留，否则 `assert` 失败、不追加
——本次实跑 **13/13 命中、6/6 零残留**。**落盘后**的自检里，前缀那两条通过、
第三条断言**我自己写错了**：它按**子串**数 `## fix round 4`，而本节正文里正好引用了这个串，
故子串命中 **2**、脚本 **rc 1**。追加本身是对的（脚本已经打印
`bytes 189916 -> 241269`、`LF 2616 -> 3277`、`标题数 77 -> 90（新增 13）`，
且 `heads_after[:77] == heads_before` 与 `back.startswith(old.rstrip())` 两条都在 rc 1 之前
就通过了）。改用 `pe_fr4_verify_report.py` 以**整行**口径复核，**rc 0**：

```
整行 `## fix round 4` 命中 1 次 [2618]；`## fix round 3` 1 次 [2154]；`## fix round 1` [1076]、`## fix round 2` [1527]
### fr4.0…### fr4.11 各整行命中 1 次：2677 / 2720 / 2780 / 2819 / 2885 / 2951 / 2973 / 2998 / 3153 / 3203 / 3238 / 3268
四节先后顺序（字节偏移）fr1(53230) < fr2(75013) < fr3(105324) < fr4(127643)
fr3.10 的末行（「没动 `fr2_probes/` 里的 11 个脚本…」）仍在、且在 `## fix round 4` 之前 = True → **没有覆盖事故**
最终 3278 行 / 241269 字节 / LF 3277 / CRLF 0 / BOM False / 乱码(U+FFFD) False
git status --short = ''；git ls-files .superpowers 计数 = 0（报告在 gitignore 内，不入库）
```

⚠️ 这一条要记下来：**「断言 rc 1」不等于「操作失败」**。看到 rc 1 之后我第一件事是核磁盘上
的实际状态（前缀关系 + 标题清单 + 字节数），确认追加正确、只是断言口径错，才去改断言；
如果照着 rc 1 直接重跑一次 `pe_fr4_report.py`，就会把本节**追加两遍**（它的
`assert old.count("## fix round 4") == 0` 会先拦下来，但那只是运气——正确的做法是先核状态）。
这与硬规矩 #53 是同一族：**尺子坏了要和被测对象坏了指认得一样清楚**。

（⚠️ 上面那个引用块是**修本节这三处自述之前**那次跑的输出，故它写的 `3278 行 / 241269 字节`
已经过时——`pe_fr4_edit4.py` 之后复跑 `pe_fr4_verify_report.py` 仍是 **PASS**，最终
**3294 行 / 242876 字节 / LF 3293 / CRLF 0**，`git status --short` = `''`、HEAD = `6784d57`。
把一个已被自己改过时的数留在报告里，正是账本 Ruling 29 / 评审 Minor 2 要消灭的形态，故就地标注。）

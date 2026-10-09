# Task 6 简报 — 预警规则：`alert_rules.yaml` + `app/domain/alerts.py`

> 本简报由控制者从 `Document/2026-10-08-实施计划03-反馈预警与CRUD-API层.md` 按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + Global Constraints + Review Focus + File Structure + **Task 6 全节（含预检更正 P6-A1..A5）**。

## 0. 派单说明（控制者写，不在计划正文里）

**⚠️ 本 Task 是本计划唯一要求变异测试的**（账本 Ruling 1 的裁定：预警阈值是本系统里唯一会直接改变「给哪个学生推减量 20%」的量，而这类错误在端到端测试里看不出来——少触发一条预警，500 人的分布测试只动几个百分点）。

**代码基线**：见 `git log --oneline -1`（分支 `feature/plan-03-feedback-alert-crud-api`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **956 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**（带 `--cov` 时 `955 passed, 1 skipped`）。⚠️ **本 Task 新增 `app/domain/alerts.py`，四格会变**（stmts 与 branch 都会涨）——**但 `Miss` 与 `BrPart` 必须仍是 0、覆盖率必须仍是 100%**（spec §12 的硬要求）。报告里给出新的四个数。
**表数 25**（本 Task 不建表）；`_MODELS_PUBLIC_BASELINE` **33（不动）**；扫描面 **51 → 52**（domain 16 → 17）；**56 个端点在线**（本 Task 不加端点）。
**环境**：Python 3.11.1（无 venv）、SQLAlchemy **2.1.3**、FastAPI 0.141.1、Pydantic 2.13.5、**PyYAML 6.0.3**。
⚠️ **开工第一件事（硬规矩 #73）**：跑那条 import 冒烟并记进报告。**若撞上 `ImportError: DLL load failed`，立刻停手报回控制者。**
⚠️ **控制者有一个 uvicorn 进程跑在 `127.0.0.1:8000`（用 `pe_demo.db`）**。你要手工起服务的话**换一个端口**。

## 0.1 ⚠️ 本 Task 的 1 条 Critical

**P6-A1：计划给的 `StudentSignals` 带不出 `window_key`。** 它的字段清单是 `rpe_streak: int` / `mini_test_scores: tuple[float, ...]` / `checkin_gap_days: int` / `completion_rate: float | None` / `mini_test_improved: bool` —— **一个 id 都没有**。而 `StudentHit.window_key` 的算式逐字要「`f"rpe{第 3 次快评的 class_session_id}"`」与「`f"mt{mini_test_scores 最后一项的 id}"`」。**`ClassSignals` 同样缺**：它只有 `mean_rpe` / `student_count`，而 `YELLOW_CLASS_RPE_HIGH` 与 `GREEN_MASTERY` 的 `window_key` 是 `f"{semester_id}:{week}"`。

**裁定**：`StudentSignals` 加 **`rpe_session_ids: tuple[int, ...]`**（与 `rpe_streak` 平行，取**触发那一次**的 `class_session_id`）与 **`mini_test_ids: tuple[int, ...]`**（与 `mini_test_scores` **同序**）；`ClassSignals` 加 **`semester_id: int`** 与 **`week: int`**。

**⚠️ 为什么把 id 放进 domain、而不是让 Task 7 在 I/O 层拼 `window_key`**：`window_key` 是**去重键**，它承重的是 Review Focus 第 3 条（「同一次触发只有一条 alert、只推一次减量 20%」，否则 `0.8³ = 0.512`）—— **放在 domain 里它是纯函数、能被单元测试穷举；放在 `alert_stage` 里它只能靠集成测试撞**。这与 Plan 02 的 Ruling 96（「值类型住 domain、加载器住 domain 外」）是同一条纪律。

## 0.2 其余 4 条（简报的预检总表里有完整实测依据）

- **P6-A2**：**YAML 报错的那套助手要抽成公共模块 `app/refdata_yaml.py`，不是「照抄」。** 实测它是 `refdata_prescription.py` 的 **16 个私有函数**，其中**通用的 6 个**是 `_line_index(text) -> dict[tuple,int]`、`_fail(path, lines, key_path, message) -> ValueError`、`_exact_keys(path, lines, where, raw, required, label) -> None`、`_as_float(...)`、`_as_int(...)`、`_as_optional_text(...)`。**「照抄」在字面上等于复制、复制就是第二个所有者。** → **把那 6 个搬进 `app/refdata_yaml.py`（改名去掉前导下划线，因为它们跨模块了），两处都从它 import。** ⚠️ **搬的是私有助手、不改 `refdata_prescription.py` 的公开面** → `_PRESCRIPTION_PUBLIC_BASELINE`（**24 个二元组**）**不动**；**指纹测试钉的是 YAML 文件、不是 `.py`** → 也不动。⚠️ `app/refdata_yaml.py` 在 `app/` 根下，**不在 `SCANNED_DIRS` 任何一项里**（与 `app/main.py` / `app/config.py` / `app/refdata.py` 同档），故架构守卫不扫它、**扫描面也不因它而涨**。
- **P6-A3（确认，无需改）**：两份守卫的下界**全是 `>=`**（`len(scanned) >= 5` / `>= 18`、`len(real_py) >= 40`、`relative_seen >= 16`、`len(api_py) >= 3`、`len(reverse_py) >= 15`、`len(cases) >= 22`）→ **加一个 domain 模块不会让任何一条红，本 Task 不需要动任何下界断言**（S6 的裁定兑现了）。
- **P6-A4（确认，无需改）**：**`ALLOWED_MODULES` 实测 = `{collections, collections.abc, dataclasses, enum, numpy, typing}`** —— `alerts.py` 要的全在里面。⚠️ 但 **`datetime` 不在白名单** → `alerts.py` **不得 import 它**。**若日期字段的类型注解绕不过去（写 `dt.date` 就要 import），请顶回来**；控制者倾向的处置是**把日期字段换成调用方已算好的 `str`**（`window_key` 里要的本来就是 ISO 串）。
- **P6-A5**：**`refdata_prescription.py` 没有 `__all__`** —— 它的公开面是靠 `test_refdata_prescription.py` 的 `_PRESCRIPTION_PUBLIC_BASELINE`（**24 个 `(名字, 所有者模块)` 二元组** + `assert len(...) == 24`）从**外部**钉住的。→ **`refdata_alerts.py` 照它的形状办（不写 `__all__`）**，改在 `tests/test_refdata_alerts.py` 里建 **`_ALERTS_PUBLIC_BASELINE`** + `assert len(...) == <自己数>`（**数用运行时口径**，硬规矩 #89）。⚠️ 而 **`app/domain/alerts.py` 要写 `__all__`**（它是 domain 模块，与 `app/domain/prescription/*.py` 同档，那些都写）。

**⚠️ 另一条单一所有者的处置**：`Alert` 表今天已有类常量 `LEVELS`（`red`/`yellow`/`green`）与 `STATUSES`，被 `_in_domain` 用着生成 CHECK 约束。**裁定：`app/domain/alerts.py` 的 `AlertLevel` 是那三个字符串的所有者，`Alert.LEVELS` 是它的 DB 镜像 —— 但本 Task 不改 `Alert.LEVELS`**（改它会连带 CHECK 约束名与 `test_models.py`），**改为加一条测试断言两者逐字相等**。

## 0.3 你要交付什么

**Create**：`backend/data/alert_rules.yaml`、`backend/app/domain/alerts.py`、`backend/app/refdata_alerts.py`、**`backend/app/refdata_yaml.py`（P6-A2 抽出来的 6 个通用助手）**、`backend/tests/domain/test_alerts.py`、`backend/tests/test_refdata_alerts.py`
**Modify**：`backend/app/refdata_prescription.py`（**改成从 `refdata_yaml` import 那 6 个，删掉本地副本**）

**⚠️ `alert_rules.yaml` 的内容在简报的 Task 6 节里逐字给了**（`version: "1.0"` + 5 条规则的 `level` / `scope` / `params`），**阈值一律照 spec §8.2 的表与那张「四项均待确认」的口径表**。⚠️ **`version` 必须加引号**（YAML 的 `1.0` 不加引号会被 PyYAML 解析成 `float`，而 `1.10` 会变成 `1.1` —— Plan 02 Task 3 踩过，18 份模板因此一律加引号），**并在加载器里校验它是 `str`**。
**⚠️ `.gitattributes` 的 `backend/data/*.yaml text eol=lf` 已覆盖它**（它直接在 `backend/data/` 下），**但写完仍要用 `read_bytes()` 复核 CRLF 计数为 0**（硬规矩 #89 的扩写）。
**⚠️ 变异测试（本 Task 的硬要求）**：5 条规则的比较符各做一次（`>=` ↔ `>`、`<` ↔ `<=`），**断言对应的边界测试变红**。⚠️ **按硬规矩 #83 的 `.pyc` 纪律做**（改完删 `__pycache__`、跑完三重还原取证：`git diff` 为空 + sha256 复原 + 复跑全绿）。⚠️ **每条变异要先论证它在结构上可达**（硬规矩 #92）——Task 5 的实现者已经示范了正确做法：它的 M1（`>` → `>=`）**只让 `22:00:00` 那一条红**，并在报告里写明「变异只让中间那条红」，这就是「尺子真的在量闭区间」的自证。

## 0.4 执行强度（账本 Ruling 1 + Ruling 5）

**目标 0–1 轮 fix round。**
- **保留**：TDD 先红后绿；**`app/domain/` 分支覆盖 100%**（四格的 stmts/branch 会涨，但 **`Miss` 与 `BrPart` 必须仍是 0**）；单一所有者；断言两侧不同源；架构守卫全绿；**既有 956 条测试一条都不许退步**。
- **⚠️ 本 Task 要求变异**（Ruling 1 的唯一例外，理由见 0.3）。
- **取消**：纯散文精度 → 记进「待清扫」清单。**但 Critical 级一律当场修。**
- ⚠️ **Ruling 5**：Plan 03 的独立评审席折进了控制者亲验，故**你的顶回是唯一的独立视角**。Plan 02 顶回 **25/25**，Plan 03 已顶回 **25/25**（累计 **50/50**）。共同点：**控制者对着「文档的形状」推理，实现者对着「守卫实际能抓到什么」推理。你在代码现场，你的判断优先。**
- ⚠️ **若你顶回 0 处，请在报告里显式写「0 处顶回」并说明你逐条核过哪些决定。**

## 0.5 纪律

- **禁区**：`backend/pe.db`（**不得存在**）、`backend/data/seed/`（0 文件）、`backend/data/**` **除了新增 `alert_rules.yaml` 之外一个字节都不许动**（三个既有指纹 `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` 必须逐字不变）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**。
- **PowerShell**：`;` 分隔；不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑写临时 `.py`。**所有写文件走 python。**
- **`git add` 按文件名逐个加**。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。**不要 push。**
- **⚠️ 探针脚本放在 `.superpowers/sdd/…/t6_probes/`，不要放 `backend/` 下** —— 架构守卫会 AST 解析工作树里的**全部** `.py`（含未入库的），Task 5 的实现者把探针留在 `backend/t5_probes/` 就撞过一次（硬规矩 #108）。**写完先 `python -m py_compile` 一遍。**
- **数列/字段/成员一律用运行时口径**，**绝不用正则数源码**（硬规矩 #89）；**数行尾/字节数用 `read_bytes()`**（#89 扩写）；**数「一个名字有几份定义」用 AST**（#89 再扩写）；**一个探针里若有两种口径，以运行时那一种为准、另一种标注为不可用**（#103）；**用谓词挑对象时先对一个已知反例验证谓词**（#107）。
- **断言「A 等于/不等于 B」时，若任一侧经过序列化/编码/格式化，必须先证明那个变换是单射**（硬规矩 #99）。
- **报告与探针脚本一律用 python 写**，不要用编辑器工具反复改 `.superpowers/` 下的文件。

## 0.6 commit 与报告

**建议 3 个 commit**：① `refdata_yaml.py` 抽取 + `refdata_prescription.py` 改成 import（**先做，让 956 条仍全绿**）；② `alerts.py` + `alert_rules.yaml` + `refdata_alerts.py` + 它们的测试；③ 变异取证 + 收尾。

报告写进 `c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd\2026-10-08-实施计划03-反馈预警与CRUD-API层\task-6-report.md`（**python 写**）。至少 8 节：① 环境与基线复现；② **P6-A2 的抽取**（`refdata_yaml.py` 的 6 个函数签名、`refdata_prescription.py` 改了几处、`_PRESCRIPTION_PUBLIC_BASELINE` 是否仍 24）；③ `alerts.py` 的 `__all__` 与全部值类型的字段（运行时口径）；④ **`alert_rules.yaml` 的字节数 / 行数 / CRLF 计数 / sha256[:16] 指纹**；⑤ **5 条规则的判据逐条落地位置与它的边界测试名**；⑥ **变异取证的完整表**（5 条规则 × 每条的变异内容 × 哪条测试变红 × 三重还原的证据）；⑦ 待清扫 / 关切 / **没按派单做的地方（0 处也要写）** / **顶回控制者的地方（0 处也要显式写并说明核过哪些决定）**；⑧ 最终验收（passed 数 956 → ?、**覆盖率四个新数（`Miss` 与 `BrPart` 必须仍是 0）**、表数 25、扫描面 51 → 52、三个既有指纹、`git diff <base> HEAD -- backend/data` **只应多出 `alert_rules.yaml` 一行**、`pe.db` 不存在）+ commit sha。

## 0.7 交回控制者

最终回复里给出（**简洁，不要贴大段代码**）：commit sha 与说明 / passed 数 / **覆盖率四个新数** / 扫描面 51 → ? / `refdata_yaml.py` 的 6 个函数名与 `_PRESCRIPTION_PUBLIC_BASELINE` 是否仍 24 / `alerts.py` 的 `__all__` 有几个名字 / `alert_rules.yaml` 的字节数与指纹 / **`_ALERTS_PUBLIC_BASELINE` 的长度** / **变异取证的 5 行摘要**（每条：变异了什么 → 哪条测试红了）/ 三个既有指纹 / 顶回控制者的地方 / 没按派单做的地方 / 待清扫条数 / 报告字节数与行数。

---


# 实施计划 03：智慧反馈层 + 预警 + 全系统 CRUD API

> **For agentic workers:** REQUIRED SUB-SKILL: 用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务实施本计划。步骤用 checkbox（`- [ ]`）语法便于跟踪。

**Goal:** 把 Plan 01/02 的批处理系统变成一个**能用浏览器点起来的原型系统**——加一层 FastAPI HTTP 接口覆盖全部实体的增删改查，补齐 spec §8 的智慧反馈层（三源采集 + 三级预警 + 班级周报），并让「预警 → 减量 20% → 学生端看到更新后的训练单」这条闭环真的跑通。

**Architecture:** 模块化单体不变。新增两层：`app/api/`（FastAPI 路由 + Pydantic schema，**可以读 DB、可以碰时钟**）与 `app/domain/alerts.py`（预警规则的纯函数叶子层，与 `app/domain/` 其余模块同纪律：无 I/O、100% 分支覆盖）。**CRUD 用一个泛型工厂生成**（`app/api/crud.py` 的 `build_crud_router`），而不是给 23 个资源各写一遍路由——原型阶段「一致的行为」比「每个资源有自己的特例」更值钱。反馈三源与预警落地是**手写的特例路由**（它们有业务语义，不是 CRUD）。

**Tech Stack:** Python 3.11.1、**FastAPI 0.141.1 / Starlette 1.7.0 / Pydantic 2.13.5 / uvicorn 0.54.0 / httpx 0.28.1（全部已装，`backend/pyproject.toml` 早已声明，本计划不引入任何新依赖）**、SQLAlchemy 2.1.3、SQLite、PyYAML、pytest + pytest-cov。

**Spec:** `Document/2026-09-28-体育闭环原型-设计spec.md`（128 328 B / 1 093 行）—— 本计划实现 **§4.5（反馈三源 4 张表）、§4.6（`alert` / `notification`）、§4.7（`weekly_class_report`）、§8.1（三源采集）、§8.2（5 条预警规则）、§8.3（消息通知，只做 `InAppChannel`）、§8.4（`weekly_adjustment` 的 `auto` 来源）、§8.5（班级周报）、§9 的后端侧（大屏与两端页面要的数据接口）**。

**上游状态（Plan 01 + Plan 02 已交付并合入 `main`，commit `a5f16b1`）：** `807 passed`、`app/domain/` **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**、**18 张表**、`app.domain.prescription.__all__` **51**、架构守卫扫描面 **35**（pipeline 8 + db 11 + domain 16）。**执行账本**：`.superpowers/sdd/2026-09-28-实施计划01-…/progress.md`（Rulings 1–234、硬规矩 #1–#47）与 `.superpowers/sdd/2026-10-06-实施计划02-…/progress.md`（Rulings 1–158、硬规矩 #48–#94、控制者错误 158 条）。

**⚠️ 用户裁定（2026-10-08，两次）：「项目只要能运行起来的原型系统就好」「后端其实只要不出太大的 bug 就行，算法层面要求不是很高，主要是要做一个系统，类似管理型的原型系统，需要能够进行增删改查，然后加上之前的大数据算法即可」。** 本计划的每一个取舍都以这句话为最高准则：**能跑通 > 参数保真；一致的 CRUD > 每资源特例；站内消息 > 真实推送；Mock 适配器 > 真实乐跑接口。**

---

## Global Constraints

- **不引入新依赖**。`fastapi` / `uvicorn[standard]` / `httpx` 已在 `backend/pyproject.toml` 的 `dependencies` 与 `dev` 里，且实测已装（fastapi 0.141.1 / uvicorn 0.54.0 / httpx 0.28.1 / pydantic 2.13.5 / starlette 1.7.0）。**开工第一件事是复跑那条 import 冒烟并把版本记进报告**（硬规矩 #73）。
- **`app/domain/` 无任何 I/O**：不得 import `sqlalchemy` / `fastapi` / `requests` / `httpx` / `pydantic_settings` / `random` / `math` / `types` / `json` / `os` / `sys` / `pathlib` / `datetime`；不得出现 `datetime.now` / `date.today` / `time.time` / `open(` / `Path(` / `__file__`。实测 `ALLOWED_MODULES = {dataclasses, enum, collections, collections.abc, numpy, typing}`。**时间与随机数一律由调用方注入，参考表一律作为参数传入。** 守卫是 `tests/architecture/test_domain_purity.py` 与 `test_layering.py`。
- **`app/domain/` 分支覆盖 100%**（spec §12）。验收命令必须带 `--cov-branch`：`cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing` → `Miss 0 / BrPart 0`。本计划新增的 `app/domain/alerts.py` 纳入这个口径。
- **`app/api/` 是新的层，架构守卫今天不认识它**。实测 `test_layering.py` 扫的是 `("pipeline", 7)` / `("db", 11)` / `("domain", 16)` 三个目录、下界断言是 `>=5` / `>=8` / `>=16` 之类。**Task 1 要给守卫加 `api` 这一层并定它的依赖方向**（`api` 可以 import `db` / `domain` / `pipeline` / `refdata*`，**反向一律禁止**）。⚠️ 加一层会让扫描面从 35 涨上去，**涨了要在报告里说明**。
- **Ruling 97（`models` 的公有导入面）**：`_MODELS_PUBLIC_BASELINE` 恒为 **33**，Plan 02 的四个表类（`Exercise` / `PrescriptionTemplate` / `Prescription` / `WeeklyAdjustment`）**刻意不在** `app.db.models` 的 `__all__` 里，本计划新增的 7 个表类**同样不进**。**一律走子模块路径**：`from app.db.models.feedback import ClassSession`。守卫是 `test_models_public_namespace_is_unchanged_by_the_split` 与 `test_plan02_tables_stay_out_of_the_models_public_namespace`（Task 2 要把后者扩到 7 张新表）。
- **分区穷尽守卫**：`tests/seed/test_generate.py` 的 `assert partitioned == actual`（`ORGANISATION_TABLES` 5 + `DATA_TABLES` 11 + `REFERENCE_TABLES` 2 = 18）。**7 张新表必须归进 `DATA_TABLES`**（11 → 18），否则这条红。⚠️ 同一文件的 `for table in DATA_TABLES + REFERENCE_TABLES: assert count == 0` 要求 **seed 阶段这些表 0 行** —— 而本计划 Task 2 要给反馈表灌演示数据，**灌数据的函数不得叫 `seed_database`、不得进它的那一圈**（见 Task 2 的决定）。
- **单一所有者**：任何常量/词表/阈值只允许有一个住址。预警阈值的唯一所有者是 `backend/data/alert_rules.yaml`（spec §4.4 逐字：「`alert_rules`（预警阈值）为 `data/` 下的**静态 YAML + 版本号**，不入库……改阈值应走版本控制与评审，不应在运行时改数据库」）。**RPE 的值域 0–10 的唯一所有者是 spec §8.2**，Plan 02 已把它写进 `assembler.py` 的 docstring 与 `INTENSITY_TYPES` 的 `rpe` 档；**不要在本计划里写第三份**。
- **断言两侧不得同源**（硬规矩 #35）：期望值一律字面写在测试里。
- **`backend/data/` 的行尾纪律**：`.gitattributes` 钉了 `backend/data/*.yaml text eol=lf` 与 `backend/data/**/*.yaml text eol=lf`。新增的 `alert_rules.yaml` 落进同一条规则，**写完立刻用 `read_bytes()` 复核 CRLF 计数为 0**（硬规矩 #89 的扩写：数行尾用 `read_bytes()`，不用 `read_text()`）。**改被指纹钉住的文件要同步常量**（Plan 02 Task 9 做过一次：`EXERCISES_FINGERPRINT` `3DE598AF38631209` → `5394B37F01DAC9AC`）。
- **禁区**：`backend/pe.db`（不得存在——⚠️ **但本计划要跑 uvicorn，它会建库文件**，见 Task 1 的决定）、`backend/data/seed/`（0 文件）、三个指纹 `D2C8E539E2FA0029`（CSV）/ `5394B37F01DAC9AC`（`exercises.yaml`）/ `822CB86A5E998301`（`exercise_equivalence.yaml`）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**（会写前两个禁区）；要数据集就在 python 里 `build_dataset(cfg)`。
- **PowerShell**：分隔用 `;`，不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑一律写临时 `.py`。**所有写文件走 python**（`Add-Content` 会静默写坏中文）。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。
- **数键/字段/成员/表格行一律用运行时口径**（`len(dict)` / `len(dataclasses.fields(...))` / `len(list(...columns))` / 数换行 + 校验首尾两行），**绝不用正则数源码**（硬规矩 #89/#93）。控制者在 Plan 02 为此栽了 4 次（#139 跨行元组 / #147 大写键 / #153 `read_text()` 换行 / #155 加粗编号）。
- **落盘唯一权威是 shell**；**`git checkout` / `git switch` / `git merge` 会按 `core.autocrlf` 重写工作树**（硬规矩 #46），事后必须复核所有「按字节哈希」的断言。要还原一个改坏的文件，用 python 从 TEMP 备份写回原字节，**不用 `git checkout`**。

## Review Focus

spec 是愿景文档：它说系统必须做什么，没说它会遇到什么。下面五类是一个真实使用者最可能撞上、而 spec **没有覆盖**的，每类都在拥有该代码的 Task 里补了测试：

1. **越权访问**：学生 A 用 `X-Student-Id: B` 的请求头去读/写学生 B 的打卡、RPE、训练单、处方。原型没有真实鉴权，但**必须有一道「身份与作用域」的闸门**，否则前端一上线就是任意读写全库。归属 Task 1（依赖注入 + 作用域校验）与 Task 5（三源采集的写入方）。
2. **打卡的时间边界**：spec §8.1 逐字「打卡窗口 = 当日 00:00–22:00。22:00 后提交仍入库但标记 `late = true`，**不计入当日完成**」。22:00:00 整点算哪边？跨时区/夏令时？服务器时钟与学生本地时钟不一致？**必须响亮地定一个口径并测边界**，因为「完成率是 RCT 关键过程指标，必须严格」（spec 原文）。归属 Task 5。
3. **预警的重复触发**：同一条 `RED_RPE_SUSTAINED` 在连续第 3、4、5 次快评都满足条件 → 会不会生成 3 条 `alert`、推 3 次「减量 20%」、把训练量连乘成 `0.8³ = 0.512`？**必须有去重口径**（同一学生 + 同一规则 + 同一「未处理」状态只有一条活跃 alert）。归属 Task 7。
4. **CRUD 的删除连带**：删一个 `semester` 会带走它下面的 `student` / `fitness_test_result` / `prescription` 吗？删一个 `prescription` 会带走它的 `weekly_adjustment` 吗？SQLite 跑在 `PRAGMA foreign_keys=ON` 下，**FK 违例是当场炸而不是静默留下孤儿行**（Plan 02 Task 7 的 P7-A4 就是这个坑：`_replay_cleanup` 必须先删子表）。泛型 CRUD 工厂必须对每个资源显式声明删除策略。归属 Task 3。
5. **`alert_rules.yaml` 被改坏**（少一个键、阈值写成字符串、规则 ID 拼错、版本号缺失）→ 必须在**加载时**响亮失败并指出是哪个键，而不是在某个学生触发预警时才炸。与 Plan 02 Review Focus 第 1 条（模板 YAML 被专家改坏）同构，照它的口径办。归属 Task 6。

---

## File Structure

**新建（生产）**

| 路径 | 职责 |
|---|---|
| `backend/app/main.py` | FastAPI 应用工厂 `create_app()` + `app = create_app()`；挂 CORS、异常处理器、全部路由；`uvicorn app.main:app` 的入口 |
| `backend/app/api/__init__.py` | 空 |
| `backend/app/api/deps.py` | `get_db()` 依赖（`Session` 生成器）、`current_student()` / `current_teacher()`（从请求头取身份）、`Page`（分页参数）、`require_scope()`（作用域闸门，Review Focus 第 1 条） |
| `backend/app/api/crud.py` | **`build_crud_router(...)` 泛型工厂**：一次生成 list/create/read/update/delete 五个端点 |
| `backend/app/api/errors.py` | 统一的错误响应形状 + `domain ValueError → 422`、`IntegrityError → 409`、`NoResultFound → 404` 的映射 |
| `backend/app/api/schemas/__init__.py` | 重导出 |
| `backend/app/api/schemas/organisation.py` | `semester` / `teacher` / `student` / `course_section` / `enrollment` 的 Pydantic 模型（`Read` / `Create` / `Update` 三件套） |
| `backend/app/api/schemas/assessment.py` | `fitness_test_batch` / `fitness_test_result` / `body_composition` / `interest_survey` |
| `backend/app/api/schemas/derived.py` | `percentile_snapshot` / `derived_metrics` / `stratification_result`（**只读**） |
| `backend/app/api/schemas/prescription.py` | `exercise` / `prescription_template` / `prescription` / `weekly_adjustment` + 教师覆盖的写入模型 |
| `backend/app/api/schemas/feedback.py` | `class_session` / `rpe_record` / `training_log` / `mini_test` |
| `backend/app/api/schemas/alerts.py` | `alert` / `notification` / `weekly_class_report` |
| `backend/app/api/routers/__init__.py` | `APIRouter` 汇总，`create_app()` 只 include 这一个 |
| `backend/app/api/routers/catalog.py` | 23 个资源的 CRUD 路由（全部由 `build_crud_router` 生成，一个列表驱动） |
| `backend/app/api/routers/feedback.py` | §8.1 三源采集的特例端点 |
| `backend/app/api/routers/prescription.py` | 教师覆盖、本周训练单、手动重生成 |
| `backend/app/api/routers/alerts.py` | 预警处理（→ 减量 20%）、通知已读 |
| `backend/app/api/routers/dashboard.py` | 教师大屏（§9.1）与学生端首页（§9.2）要的聚合读接口 |
| `backend/app/api/routers/pipeline.py` | `POST /api/pipeline/run-daily`（手动触发批处理，原型演示用） |
| `backend/app/domain/alerts.py` | **5 条预警规则的纯函数**（无 I/O，100% 分支覆盖） |
| `backend/app/refdata_alerts.py` | 加载 + 校验 `data/alert_rules.yaml`，持有 `alert_rules()` 单例（与 `refdata_prescription.py` 同口径：`load_*` 只加载不缓存，单例是另一个函数） |
| `backend/app/pipeline/alert_stage.py` | 预警求值 + 落库 + 幂等；`weekly_adjustment` 的 `auto` 来源 |
| `backend/app/pipeline/report_stage.py` | §8.5 班级周报生成 |
| `backend/app/notify.py` | `NotificationChannel` 接口 + `InAppChannel`（写 `notification` 表）+ 两个未来通道的骨架 |
| `backend/app/demo_data.py` | **反馈三源与预警的演示数据生成器**（⚠️ 不是 `seed_database`，见 Task 2） |
| `backend/data/alert_rules.yaml` | 5 条规则的阈值 + `version` |

**修改**：`backend/app/db/models/feedback.py`（475 B 空壳 → 4 张表）、`backend/app/db/models/ops.py`（+3 张表）、`backend/app/db/models/__init__.py`（子模块导入，**不改 `__all__`**）、`backend/tests/db/test_models.py`（表数 18 → 25 的**全部**命中点）、`backend/tests/seed/test_generate.py`（`DATA_TABLES` 11 → 18）、`backend/tests/architecture/test_layering.py`（加 `api` 层）、`backend/tests/fixtures/golden_cases.json`（**GC14**）、`backend/tests/integration/test_golden_cases.py`、`Document/…设计spec.md`（§14 补项）

**新建（测试）**：`backend/tests/api/`（`conftest.py` + `test_crud.py` + `test_feedback.py` + `test_alerts_api.py` + `test_dashboard.py` + `test_scope.py`）、`backend/tests/domain/test_alerts.py`、`backend/tests/test_refdata_alerts.py`、`backend/tests/pipeline/test_alert_stage.py`、`backend/tests/pipeline/test_report_stage.py`、`backend/tests/test_notify.py`、`backend/tests/test_demo_data.py`、`backend/tests/test_main.py`

**⚠️ 本计划刻意不做**（用户裁定「能运行起来的原型系统就好」）：
- **`HttpLePaoAdapter` 的真实实现**。骨架已在（`app/adapters/http_lepao.py`，78 行，四个方法一律 `raise NotImplementedError`，docstring 逐字写明了未来实现必须满足的契约形状与「不得沿用『两个实现跑同一组契约测试』这种说法」）。**原型用 `MockLePaoAdapter` 就能跑通全链路**，而真实实现要补约 40 条行为契约测试且**接口字段今天未定**——写了也是猜测，而猜测出来的重试策略会在真实接口确定后变成需要拆掉的负担（那段 docstring 自己就是这么说的）。**留给真实对接那一期。**
- **真实消息推送**（微信订阅消息 / 短信）。spec §8.3 原文：「原型不做真实推送（需微信订阅消息资质 / 短信通道）」。**只做 `InAppChannel`**，另两个通道建骨架 + 契约测试。
- **真实鉴权**。用请求头传身份（`X-Student-Id` / `X-Teacher-Staff-No`），并在 `deps.py` 的 docstring 里明写「原型口径，上线前必须换成真实会话」。
- **性能压测**（用户 2026-10-08 裁定，Plan 02 已删）。

---

---

## Task 6: 预警规则 —— `alert_rules.yaml` + `app/domain/alerts.py`

### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `4e7cc08`，取证脚本 `t6_probes/_preflight.py`，**写完先 `py_compile` 过一遍**——硬规矩 #108）

**测试基线**：`956 passed`；`app/domain/` **996/0/288/0/100%**；**25 张表**；扫描面 **51**（pipeline 8 + db 11 + domain **16** + api 16）；**56 个端点在线**。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P6-A1** | **Critical** | **`StudentSignals` 带不出 `window_key`。** 计划的字段清单是 `rpe_streak: int` / `mini_test_scores: tuple[float, ...]` / `checkin_gap_days: int` / `completion_rate: float \| None` / `mini_test_improved: bool` —— **一个 id 都没有**。而 `StudentHit.window_key` 的算式逐字要「`f"rpe{第 3 次快评的 class_session_id}"`」与「`f"mt{mini_test_scores 最后一项的 id}"`」。**`ClassSignals` 同样缺**：它只有 `mean_rpe` / `student_count`，而 `YELLOW_CLASS_RPE_HIGH` 与 `GREEN_MASTERY` 的 `window_key` 是 `f"{semester_id}:{week}"`。 | **`StudentSignals` 加两个与既有字段平行的 id 元组**：`rpe_session_ids: tuple[int, ...]`（与 `rpe_streak` 平行，取**触发那一次**的 id）与 `mini_test_ids: tuple[int, ...]`（与 `mini_test_scores` 平行，同序）。**`ClassSignals` 加 `semester_id: int` 与 `week: int`。** ⚠️ **为什么把 id 放进 domain 而不是让 Task 7 在 I/O 层拼 `window_key`**：`window_key` 是**去重键**，而它承重的是 Review Focus 第 3 条（「同一次触发只有一条 alert、只推一次减量 20%」）——**放在 domain 里它是纯函数、能被单元测试穷举；放在 `alert_stage` 里它只能靠集成测试撞**。Plan 02 的同一条纪律是「值类型住 domain、加载器住 domain 外」 |
| **P6-A2** | **Important** | **YAML 报错的那套助手是 `refdata_prescription.py` 的私有函数**，实测共 16 个，其中**通用的有 6 个**：`_line_index(text) -> dict[tuple, int]`、`_fail(path, lines, key_path, message) -> ValueError`、`_exact_keys(path, lines, where, raw, required, label) -> None`、`_as_float(...)`、`_as_int(...)`、`_as_optional_text(...)`。计划 Task 6 的决定写「**直接照抄那套形状**，不要另发明一套」—— **「照抄」在字面上等于复制，而复制就是第二个所有者。** | **抽公共模块 `app/refdata_yaml.py`**，把那 6 个通用助手搬进去（**改名去掉前导下划线**，因为它们跨模块了），`refdata_prescription.py` 与 `refdata_alerts.py` 都从它 import。⚠️ **这与 Plan 02 遗留的那条 Minor 是同一条纪律**（「两份守卫的重复代码在 Plan 03 加第三个守卫时必须抽公共模块」）。⚠️ **搬的是私有助手，不改 `refdata_prescription.py` 的公开面** → `_PRESCRIPTION_PUBLIC_BASELINE`（**24 个二元组**）**不动**；**指纹测试钉的是 YAML 文件、不是 `.py`** → 也不动。⚠️ `app/refdata_yaml.py` 在 `app/` 根下，**不在 `SCANNED_DIRS` 任何一项里**（与 `app/main.py` / `app/config.py` / `app/refdata.py` 同档），故架构守卫不扫它 |
| **P6-A3** | 确认（无需改） | **两份守卫的下界全是 `>=`**：`test_domain_purity.py` 的 `len(scanned) >= 5`、`len(real_py) >= 40`、`relative_seen >= 16`；`test_layering.py` 的 `len(scanned) >= 18`（= pipeline 5 + db 5 + domain 5 + api 3）、`len(api_py) >= 3`、`len(reverse_py) >= 15`、`len(cases) >= 22`。**加一个 domain 模块（16 → 17，扫描面 51 → 52）不会让任何一条红。** | **S6 的裁定兑现了：本 Task 不需要动任何下界断言。** 报告里只需写明扫描面 51 → 52 |
| **P6-A4** | 确认（无需改） | **`ALLOWED_MODULES` 实测 = `{collections, collections.abc, dataclasses, enum, numpy, typing}`** —— `alerts.py` 要的 `dataclasses` / `enum` / `collections.abc` / `typing` **全在里面**。 | **不需要改 purity 守卫。** ⚠️ 但 `alerts.py` **不得 import `datetime`**（不在白名单）→ `window_key` 里要用的日期串**必须由调用方传进来**（Task 7 传 ISO 串），**不能在 domain 里 `date.isoformat()`**……⚠️ **更正：`isoformat()` 是实例方法，不需要 import `datetime`**，故只要 `StudentSignals` / `ClassSignals` 里的日期字段**由调用方注入**（`datetime.date` 对象本身也不需要 import 就能当参数类型——但**注解里写 `dt.date` 就需要 import**）。**决定：注解一律用字符串形式或干脆不注解那两个字段的具体类型，避免 import `datetime`**；实现者若发现绕不过去，**顶回来** |
| **P6-A5** | Minor | **`refdata_prescription.py` 没有 `__all__`**（实测 `getattr(RP, '__all__', '（无）')` → 无），它的公开面是靠 `test_refdata_prescription.py` 的 `_PRESCRIPTION_PUBLIC_BASELINE`（**24 个 `(名字, 所有者模块)` 二元组** + `assert len(...) == 24`）从**外部**钉住的。 | `refdata_alerts.py` **照它的形状办：不写 `__all__`**，改在 `tests/test_refdata_alerts.py` 里建一份 **`_ALERTS_PUBLIC_BASELINE`**（`app.domain.alerts` 的公开名 + `refdata_alerts` 的公开名，逐个带所有者模块），并 `assert len(...) == <自己数>`。**⚠️ 数用运行时口径**（硬规矩 #89） |


**Files:** Create `backend/data/alert_rules.yaml`、`backend/app/domain/alerts.py`、`backend/app/refdata_alerts.py`、`backend/tests/domain/test_alerts.py`、`backend/tests/test_refdata_alerts.py`；Modify `backend/tests/architecture/*`（domain 多一个模块 → 扫描面 +1）**⚠️ S6 的裁定：下界断言由 Task 1 一次性抬到位（含 `api` 那一层），本 Task 只加一个 domain 模块、不再动下界**（domain 16 → 17 仍满足 Task 1 抬过的下界）。故本 Task 的「扫描面涨了要说明」只是**报告里写一句**，不是改断言。

**Interfaces:**
- Produces（`app/domain/alerts.py`，**无 I/O、100% 分支覆盖**）：
  - `AlertLevel(str, Enum)`：`RED = "red"` / `YELLOW = "yellow"` / `GREEN = "green"`
  - `RuleId(str, Enum)`：`RED_MINITEST_DROP` / `RED_RPE_SUSTAINED` / `YELLOW_CHECKIN_GAP` / `YELLOW_CLASS_RPE_HIGH` / `GREEN_MASTERY`（**声明序 = spec §8.2 表格的行序**）
  - `AlertScope(str, Enum)`：`STUDENT = "student"` / `CLASS = "class"`（spec §8.2 的「作用域」列）
  - `AlertRule`（frozen）：`rule_id` / `level` / `scope` / `params: Mapping[str, float | int]`（阈值，来自 YAML）
  - `AlertRules`（frozen）：`version: str` / `rules: Mapping[RuleId, AlertRule]`；方法 `params_of(rule_id) -> Mapping[...]`
  - `StudentSignals`（frozen）：**一个学生在某一周的全部输入**（`rpe_streak: int`（当前连续 ≥ 阈值的次数）/ `mini_test_scores: tuple[float, ...]`（按周次升序，最近 3 个）/ `checkin_gap_days: int`（连续未打卡的**应打卡训练日**数）/ `completion_rate: float | None` / `mini_test_improved: bool`）**⚠️ P6-A1 更正：还要加两个与既有字段平行的 id 元组 —— `rpe_session_ids: tuple[int, ...]`（与 `rpe_streak` 平行，`window_key` 要取**触发那一次**的 `class_session_id`）与 `mini_test_ids: tuple[int, ...]`（与 `mini_test_scores` **同序**，`window_key` 要取最后一项的 `mini_test.id`）。原清单里一个 id 都没有，而 `StudentHit.window_key` 的算式逐字要它们** —— 照原清单写，`window_key` 在 domain 里根本拼不出来**
  - `ClassSignals`（frozen）：`mean_rpe: float | None` / `student_count: int`**⚠️ P6-A1 更正：还要加 `semester_id: int` 与 `week: int`** —— `YELLOW_CLASS_RPE_HIGH` 与 `GREEN_MASTERY` 的 `window_key` 是 `f"{semester_id}:{week}"`，原清单里两个都没有
  **⚠️ 为什么把 id 放进 domain 而不是让 Task 7 在 I/O 层拼 `window_key`**：`window_key` 是**去重键**，它承重的是 Review Focus 第 3 条（「同一次触发只有一条 alert、只推一次减量 20%」）—— **放在 domain 里它是纯函数、能被单元测试穷举；放在 `alert_stage` 里它只能靠集成测试撞**。Plan 02 的同一条纪律是「值类型住 domain、加载器住 domain 外」（Ruling 96）
  - `evaluate_student(sig: StudentSignals, rules: AlertRules) -> tuple[StudentHit, ...]`、`evaluate_class(sig: ClassSignals, rules: AlertRules) -> tuple[ClassHit, ...]`
  - `StudentHit` / `ClassHit`（frozen）：`rule_id` / `level` / `window_key: str`（**Task 2 那个去重列的值，由 domain 算出来**）/ `snapshot: dict`（**触发数据快照**，落进 `alert.trigger_snapshot`）

**`data/alert_rules.yaml` 的内容（阈值逐字照 spec §8.2 的表 + 那张「四项均待确认」的口径表）：**

```yaml
version: "1.0"
rules:
  RED_MINITEST_DROP:
    level: red
    scope: student
    params: {drop_pct: 0.05, consecutive: 2, points_needed: 3}
  RED_RPE_SUSTAINED:
    level: red
    scope: student
    params: {rpe_min: 9, streak: 3}
  YELLOW_CHECKIN_GAP:
    level: yellow
    scope: student
    params: {gap_days: 2}
  YELLOW_CLASS_RPE_HIGH:
    level: yellow
    scope: class
    params: {mean_rpe_max: 7.0}
  GREEN_MASTERY:
    level: green
    scope: student
    params: {completion_rate_min: 1.0, improve_pct: 0.03}
```

**spec §8.2 五条的精确口径（每条都要有测试）：**

| 规则 | 判据（spec 原文 + §8.2 那张口径表） | 决定 |
|---|---|---|
| `RED_MINITEST_DROP` | 「连续两次二次小测下降 ≥ 5%」；口径表 #2：「需 **3 个数据点**：`score(t) < score(t-1) × 0.95` **且** `score(t-1) < score(t-2) × 0.95`。首次可能触发于第 6 周」 | **严格 `<`**（与 Plan 01 的 P25、Plan 02 的 `BODY_FAT_LIMIT` / `bmi > 30` / `muscle < P10` 同口径）。**数据点不足 3 个 → 不触发 + 在 `snapshot` 里留痕 `"insufficient_points": n`**（「没测」不得讲成「测了且没问题」，Plan 01 Ruling 134 / Plan 02 P5-A3 的同一条纪律）。`window_key = f"mt{mini_test_scores 最后一项的 id}"` |
| `RED_RPE_SUSTAINED` | 「RPE 连续 ≥ 9 分」；口径表 #1：「**连续 3 次课堂快评**」 | `rpe_streak >= 3`，其中 streak 的定义是「**最近连续若干次** `rpe >= 9`」。**`>=` 不是 `>`**（spec 逐字「≥ 9」）。`window_key = f"rpe{第 3 次快评的 class_session_id}"` |
| `YELLOW_CHECKIN_GAP` | 「打卡中断 2 天」；口径表 #3：「连续 **2 个应打卡训练日**未打卡（**休息日不计入中断**）」 | `checkin_gap_days >= 2`，而 `checkin_gap_days` 由 **Task 7 的 `alert_stage` 按处方训练日算好传进来**（domain 不知道什么是训练日）。**这是 spec §8.1 折中方案的直接后果**，要在 docstring 里写明。`window_key = f"gap{中断结束日的 ISO 串}"` |
| `YELLOW_CLASS_RPE_HIGH` | 「课堂 RPE 均值 > 7 分」，作用域**班级** | **严格 `>`**（spec 逐字「> 7」）。`mean_rpe is None`（本周一次快评都没有）→ **不触发 + 留痕**（同上纪律）。`window_key = f"{semester_id}:{week}"` |
| `GREEN_MASTERY` | 「本周完成度 100% **AND** 二次小测提升」；口径表 #4：「任一指标改善 ≥ **3%**。与下降阈值 5% 刻意不对称——正向激励应更宽松」 | `completion_rate == 1.0`（**不是 `>=`**，spec 逐字「100%」）且 `mini_test_improved`。`completion_rate is None` → **不触发**。⚠️ **`improve_pct: 0.03` 这个阈值在 domain 里不被 `GREEN_MASTERY` 直接消费**——「任一指标改善 ≥ 3%」的判定发生在 Task 7 算 `mini_test_improved` 的时候。**故 `params` 里保留它是为了可配置，但要在 docstring 里写明它由谁消费**（否则它会看起来像一个没人读的死配置，而下一个人会以为改了它就改了行为） |

**决定：**
- **加载器与 domain 的分层照 Plan 02 的既有做法**（Ruling 96）：**值类型住 domain（`alerts.py`）、加载器住 domain 外（`refdata_alerts.py`）、加载器 import 值类型**。`load_alert_rules(path=None) -> AlertRules` + `alert_rules()` 单例（**`load_*` 只加载不缓存，单例是另一个函数**，P2-A9）。
- **⚠️ P6-A2 更正：YAML 报错的那套助手要抽成公共模块 `app/refdata_yaml.py`，不是「照抄」。** 实测它是 `refdata_prescription.py` 的 **16 个私有函数**，其中**通用的有 6 个**：`_line_index(text) -> dict[tuple, int]`、`_fail(path, lines, key_path, message) -> ValueError`、`_exact_keys(path, lines, where, raw, required, label) -> None`、`_as_float(...)`、`_as_int(...)`、`_as_optional_text(...)`。**原文说「直接照抄那套形状」，而「照抄」在字面上等于复制、复制就是第二个所有者。** **把那 6 个搬进 `app/refdata_yaml.py`（改名去掉前导下划线，因为它们跨模块了），两处都从它 import。** ⚠️ **这与 Plan 02 遗留的那条 Minor 是同一条纪律**（「两份守卫的重复代码在 Plan 03 加第三个守卫时必须抽公共模块」）。⚠️ **搬的是私有助手、不改 `refdata_prescription.py` 的公开面** → `_PRESCRIPTION_PUBLIC_BASELINE`（**24 个二元组**）**不动**；**指纹测试钉的是 YAML 文件、不是 `.py`** → 也不动。⚠️ `app/refdata_yaml.py` 在 `app/` 根下，**不在 `SCANNED_DIRS` 任何一项里**（与 `app/main.py` / `app/config.py` / `app/refdata.py` 同档），故架构守卫不扫它、扫描面也不因它而涨。
- **YAML 被改坏要在加载时响亮失败**（Review Focus 第 5 条），照 `refdata_prescription.py` 的口径：**违例消息里带文件名 + 行号 + 键路径**（它有一套 `_line_index` / `_fail` / `_exact_keys` 的现成机制，**直接照抄那套形状**，不要另发明一套）。至少拦：缺 `version`、`rules` 不是 dict、规则 ID 不在 `RuleId` 里、`level` / `scope` 值非法、`params` 缺键、阈值不是数、**多出一个没人认识的规则 ID**（那是专家加新规则忘了改代码，静默忽略会让新规则永远不生效）。
- **`version` 必须是 `str`**（YAML 的 `1.0` 不加引号会被 PyYAML 解析成 `float`，而 `1.10` 会变成 `1.1` —— Plan 02 Task 3 踩过，18 份模板因此一律加引号）。**`alert_rules.yaml` 的 `version` 也加引号**，并在加载器里校验它是 `str`。
- **指纹测试**：`alert_rules.yaml` 加一条 sha256[:16] 指纹（照 `exercises.yaml` / `exercise_equivalence.yaml` 的口径，算法逐字是 `hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16].upper()`），**防止有人在跑测试的间隙改阈值**。⚠️ **`.gitattributes` 的 `backend/data/*.yaml text eol=lf` 已覆盖它**（它直接在 `backend/data/` 下，不在子目录），**但写完仍要用 `read_bytes()` 复核 CRLF 计数为 0**（硬规矩 #89 的扩写）。
- **⚠️ P6-A5：公开面基线守卫照 `test_refdata_prescription.py` 的形状办** —— 实测 `refdata_prescription.py` **没有 `__all__`**，它的公开面是靠 `_PRESCRIPTION_PUBLIC_BASELINE`（**24 个 `(名字, 所有者模块)` 二元组** + `assert len(...) == 24`）从**外部**钉住的。故 `refdata_alerts.py` **也不写 `__all__`**，改在 `tests/test_refdata_alerts.py` 里建一份 **`_ALERTS_PUBLIC_BASELINE`**（`app.domain.alerts` 与 `app.refdata_alerts` 的公开名，逐个带所有者模块）+ `assert len(...) == <自己数>`。**⚠️ 数用运行时口径**（硬规矩 #89）。⚠️ **`app.domain.alerts` 要写 `__all__`**（它是 domain 模块，与 `app/domain/prescription/*.py` 同档，那些都写）。
- **⚠️ 变异测试（本 Task 是全计划唯一要求做变异的地方）**：5 条规则的比较符各做一次（`>=` ↔ `>`、`<` ↔ `<=`），断言对应的边界测试变红。**理由：预警阈值是本系统里唯一会直接改变「给哪个学生推减量 20%」的东西，而这类错误在端到端测试里完全看不出来**（少触发一条预警，500 人的分布测试只会动几个百分点）。按硬规矩 #83 的 `.pyc` 纪律做。

- [ ] **Step 1–6: 写失败测试 → 跑失败 → 写 YAML + 加载器 + domain → 跑通 → 变异验收 → Commit**

---

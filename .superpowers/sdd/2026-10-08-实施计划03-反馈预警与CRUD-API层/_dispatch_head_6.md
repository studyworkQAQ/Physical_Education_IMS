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


"""Task 9 落地脚本 06：spec 勘误 + §14 补项 #38 / #39 / #40。

⚠️ 字节级替换（read_bytes → replace → write_bytes）：这份 spec 工作树是 CRLF
（实测 1092 CRLF / 0 bare LF），按文本读写会统一行尾、制造一个巨大的无意义 diff。
⚠️ 每一处锚点断言**恰好命中一次**：抄错当场响，不静默漏改。
⚠️ 格式照本仓既有的勘误体例：``> ### ⚠️ 勘误（Plan NN Task M 补）：…`` 的 blockquote，
内含 **原文 / 更正 / 理由 / → §14 编号** 四格（§4.4 与 §4.6 那两条 Plan 02 勘误是模板）。
"""
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
SPEC = ROOT / "Document" / "2026-09-28-体育闭环原型-设计spec.md"

#: ⚠️ Python 3.11 的 f-string 表达式里**不能有反斜杠**，故两个行尾字节串提成常量。
CRLF = b"\r\n"
LF = b"\n"

EDITS: list[tuple[str, str, str]] = []


def after(anchor: str, insertion: str, label: str) -> None:
    """在 ``anchor`` 之后插入 ``insertion``（锚点原样保留）。"""
    EDITS.append((label, anchor, anchor + insertion))


# ---------------------------------------------------------------------------
# §3.4 —— HttpLePaoAdapter 本计划仍未实现
# ---------------------------------------------------------------------------
A = ("**`http_lepao.py` 现在就建骨架**，即使没有一行真实请求。它定义「乐跑只读接口每日增量同步」"
     "的契约形状，配一组契约测试，且与 `MockLePaoAdapter` 跑同一套契约。接口字段一旦确定，"
     "改动只落在这一个文件，`pipeline` 与 `domain` 完全不动。这是指导文件 3.1.1"
     "「功能扩展与深度集成」的落点。")
I = """

> ### ⚠️ 勘误（Plan 03 Task 9 补）：`HttpLePaoAdapter` **到 Plan 03 结案仍未实现**，而「与 `MockLePaoAdapter` 跑同一套契约」这句话**刻意不成立**
>
> **原文**（`:184`）逐字是「配一组契约测试，且与 `MockLePaoAdapter` 跑同一套契约」。
> **更正**：`backend/app/adapters/http_lepao.py` 今天仍是 **78 行的骨架**，四个 `fetch_*` 方法一律 `raise NotImplementedError`；契约测试（`backend/tests/adapters/test_contract.py`）**只跑 `MockLePaoAdapter`**。§12 那一格早已按实际登记（`:956` 的勘误：「两实现全通过」字面未达成，而对一个骨架**不存在更强的可表达断言**），本条只是把它在 §3.4 这一侧也交代一次，免得读者只读架构章节就以为 HTTP 实现存在。
> **理由**：Plan 03 的 File Structure 逐字把「`HttpLePaoAdapter` 的真实实现」列进「**本计划刻意不做**」，两条依据：① 真实实现要补约 **40 条**行为契约测试，而**乐跑只读接口的字段今天未定**——写了也是猜测；② 猜测出来的重试策略会在真实接口确定后变成需要拆掉的负担。⚠️ 而骨架的 docstring 里逐字写明了「未来实现必须满足的契约形状」，并且明写「**不得沿用『两个实现跑同一组契约测试』这种说法**」——那句正是本条更正的原文。原型用 `MockLePaoAdapter` 就能跑通全链路（`backend/scripts/demo.ps1` 走的就是它）。
> **→ §14 无新编号**：这是「spec 的字面与实现不一致」，不是需要项目负责人裁决的空洞；真实对接那一期要回来改的是 §12 `:956` 与本条。"""
after(A, I, "§3.4 HttpLePaoAdapter")

# ---------------------------------------------------------------------------
# §4.5 —— 反馈三源：实现比 spec 的字段清单多了哪些列
# ---------------------------------------------------------------------------
A = ("| `mini_test` | student_id、semester_id、周次、测试项组合、30 秒深蹲次数、20m 折返秒数、"
     "标准化得分、测试日期、录入教师 |")
I = """

> ### ⚠️ 勘误（Plan 03 Task 9 补）：四张反馈表各比本节的字段清单**多了几列**，逐张交代「多了什么、为什么多」
>
> **原文**（`:286`–`:289`）是四行字段清单。实现（`backend/app/db/models/feedback.py`）逐张多出来的东西如下，**每一条都是「不加就会静默出错」的那一类**，不是顺手加的：
>
> | 表 | 多出来的 | 为什么多 |
> |---|---|---|
> | `class_session` | `batch_id`（**可空**外键 → `daily_sync_run`）、`UniqueConstraint("course_section_id", "session_date", "period")` | 本表有**两个**写入来源：管道整批写的那种带 `batch_id`，教师实时建的那种没有批次可指，而 `NOT NULL` 只容得一个。⚠️ 可空还有一个**承重的**副作用：`app.db.repo.delete_by_batch` 是 `WHERE batch_id = :b`，而 SQL 里 `NULL = 任何值` 都不成立，故教师实时建的课次**天然躲过重放**——那正是我们要的（重放不该删掉教师手工排的课）。唯一约束是 `repo.upsert` 的 DB 层兜底（本表**刻意不进** `_replay_cleanup` 的清单：`rpe_record.class_session_id` 是 NOT NULL 外键，按批删课次要么当场 `FOREIGN KEY constraint failed`、要么把那一列改成 `CASCADE` 而连带删掉学生刚交的快评）。 |
> | `rpe_record` | `id`（代理主键）、`submitted_at`、`UniqueConstraint("class_session_id", "student_id")` | 原文把「提交时间」列了，但没说要一个代理主键。⚠️ 那条唯一约束是**承重的**：少了它，学生连点两次「提交」会让 `YELLOW_CLASS_RPE_HIGH` 的「课堂 RPE 均值」被同一个人算两遍，而教师端的「已提交名单」会显示 101%。 |
> | `training_log` | `submitted_at`（原文只有「日期」与「`late` 标记」）、`batch_id`（可空）、`UniqueConstraint("student_id", "log_date")` | ⚠️ **`submitted_at` 是「补卡不计入完成率」这条口径的前提**：判据是 `submitted_at.date() == log_date`，而 `late` 表达不了它——一个 21:00 交的**补卡**（补的是三天前）`late = False` 却仍然不该计入那一天的完成率。→ 见 #39。⚠️ 一天一行是本表的口径，故**不做**「补卡覆盖旧行」：改成 upsert 会让「学生先打了『没练』、后来又改成『练了』」这件事在库里不留痕迹，而 `YELLOW_CHECKIN_GAP` 与事后审计都要能回答「他当时交的是什么」。 |
> | `mini_test` | `id`、`normalized_score` **可空**、`UniqueConstraint("student_id", "semester_id", "week")` | ⚠️ 原文把「标准化得分」当成一个普通字段，而它**在录入时算不出来**：「班内百分位反查」要读整个教学班的行，而教师是**一次提交一批**的——录到第 3 行时第 4..40 行还没进来，那一刻算出来的百分位**必然是错的**。故那一列可空、录入时一律留 `NULL`，算式住在 `app.domain.report.mini_test_scores`（见 §8.1 的勘误）。唯一约束是 `RED_MINITEST_DROP` 的前提：它要 3 个数据点判「连续两次下降 ≥ 5%」，同一周多一行会让那三个点错位成「同一周自己跟自己比」。 |
>
> **→ §14 无新编号**：以上都是「spec 的字段清单少了几列」，不是需要项目负责人裁决的空洞（与 §4.4 / §4.6 那两条 Plan 02 勘误同一处置）。⚠️ 而「打卡的三个模糊点」**占** #39（它们是口径裁决，不是字段清单）。"""
after(A, I, "§4.5 反馈三源多出来的列")

# ---------------------------------------------------------------------------
# §4.6 —— alert / notification 多出来的列
# ---------------------------------------------------------------------------
A = ("> **→ §14 无新编号**：这是「spec 的字段清单少了一列」，不是需要项目负责人裁决的空洞。\n"
     "\n"
     "### 4.7 班级周报")
I = """
> ### ⚠️ 勘误（Plan 03 Task 9 补）：`alert` 多了 **3** 列、`notification` 多了 **1** 个外键处置，逐条交代
>
> **原文**（`:295`–`:296`）：`alert` 的清单是「id、student_id（班级级预警为 course_section_id）、级别、规则 ID、触发数据快照 JSON、触发时间、状态、教师处理动作、处理时间」，`notification` 的清单里有「关联 alert/prescription」。实现多出来的：
>
> | 多出来的 | 为什么多 |
> |---|---|
> | **`alert.window_key`**（NOT NULL，`String(32)`） | **本节没有它，而它是 §8.2「重复触发」那个失效的唯一解**。同一条 `RED_RPE_SUSTAINED` 在连续第 3、4、5 次快评都满足条件时，若没有「窗口」这个维度，就会生成 3 条 `alert`、推 3 次「减量 20%」、把训练量连乘成 `0.8³ = 0.512`——而全链路没有一处报错。故它与 `rule_id` / `subject_key` / `semester_id` 组成 `UniqueConstraint`，让 **DB 当去重的裁判**。⚠️ 取值算式**逐规则不同**且住在 `app/domain/alerts.py`（纯函数、可穷举）：`RED_RPE_SUSTAINED` 取 `rpe{凑满 streak 那一次的 class_session_id}`（**不是最后一次**——锚在最后一次的话 streak 再长键也会天天变），`RED_MINITEST_DROP` 取 `mt{最后一次小测的 id}`（小测不是每堂课都有，一次新小测是一次**新的观测窗口**），`YELLOW_CHECKIN_GAP` 取 `gap{中断结束日}`，两条周级规则取 `{semester_id}:{week}`。→ **#38** |
> | **`alert.subject_key`**（NOT NULL，`String(24)`） | SQLite 的 `UNIQUE` 对 NULL 是「NULL ≠ NULL」，而 `student_id` 与 `course_section_id` 是**两个可空外键**（原文自己写着「班级级预警为 course_section_id」），进不了去重键——否则那条 `UniqueConstraint` 对班级级预警**静默失效**。故加一个 NOT NULL 的归一化主语位（`student:<id>` / `section:<id>`）。⚠️ 前缀是 `section` 而不是 `course_section`：列宽 24，最长形状 `course_section:2147483647` 是 **25** 字符、**超宽 1**，而 `section:2147483647` 是 18 字符、余量 6。 |
> | **`alert.batch_id`**（NOT NULL 外键 → `daily_sync_run`） | 预警是**管道产物**，故它进 `app.pipeline.daily._replay_cleanup` 的清单（重放那一天先按 `batch_id` 删掉本批的行再整批重算）。⚠️ 它能进清单的前提是下面那一格的 `ON DELETE SET NULL`。 |
> | **`notification.alert_id` 带 `ON DELETE SET NULL`** | `notification` **刻意不带** `batch_id`、不在重放清单里（消息是已经推给某个人的东西，重放那天按批删掉它，学生端消息中心的红点会凭空消失），而它的 `alert_id` 指着 `alert`。普通外键会让重放删 `alert` 时当场 `FOREIGN KEY constraint failed`、整批回滚；`CASCADE` 则会连带删掉已经推出去的消息。**`SET NULL` 是唯一同时满足「重放不炸」与「消息不丢」的那一档。** |
> | **`notification.recipient_id` 刻意不是外键** | 收件人是**多态**的（`recipient_kind` + `recipient_id` 两列合起来才是原文那一格「接收者」：学生级预警发给学生、班级级发给教师），而一个外键只能指一张表。⚠️ 代价：删一个学生不会带走他的通知，`course_section` 的删除连带也看不到这一层关系。 |
>
> **→ §14 新编号 #38**（`window_key` 是「spec 没有、而实现必须有」的一列，它的**取值算式**是一个需要项目负责人过目的口径：哪一次触发算「同一次」直接决定教师看到几条工单、学生被减几次量）。"""
EDITS.append(("§4.6 alert/notification 多出来的列", A, A.replace(
    "> **→ §14 无新编号**：这是「spec 的字段清单少了一列」，不是需要项目负责人裁决的空洞。\n",
    "> **→ §14 无新编号**：这是「spec 的字段清单少了一列」，不是需要项目负责人裁决的空洞。\n"
    + I.rstrip("\n").replace("### 4.7 班级周报", "") .rstrip("\n") + "\n",
)))

# ---------------------------------------------------------------------------
# §4.7 —— weekly_class_report 多出来的列
# ---------------------------------------------------------------------------
A = ("| `weekly_class_report` | id、course_section_id、semester_id、周次、分层分布及环比流动、"
     "人均 RPE 与上周对比、按层分组打卡完成率、进步榜/退步名单 JSON、预警汇总、算法建议、生成时间 |")
I = """

> ### ⚠️ 勘误（Plan 03 Task 9 补）：`weekly_class_report` 多了 `batch_id` 与一条 `UniqueConstraint`，且「算法建议」是一句**中文自由文本**
>
> **原文**（`:315`）的清单里没有 `batch_id`，也没有唯一约束。实现多出来的两格：
>
> * **`batch_id`**（NOT NULL 外键 → `daily_sync_run`）：周报是**管道产物**（§5 的第 9 阶段 `Weekly`），故它进 `_replay_cleanup` 的清单（Plan 03 Task 8 把它从六张扩到七张）。⚠️ **漏掉它的失效形态不是翻倍**（下面那条唯一约束挡着），而是更隐蔽的一格：那一行会静默沿用**上一轮**的 `batch_id`，于是下一次重放按新的 `batch_id` 删时**删不到它**——它从此永远停在旧批次上，而 `daily_sync_run` 的计数看起来全都正常。
> * **`UniqueConstraint("course_section_id", "semester_id", "week")`**：一个班一周只有一份周报，故同日重跑命中 `repo.upsert` 的**更新**分支。⚠️ 于是「生成了几份」这个计数是「**写了**多少行」而不是「**插了**多少行」，两者在重放时不相等，而重放要的是前者。
>
> ⚠️ **另外两格口径**（都不是字段清单的问题，故写在这里）：
>
> 1. 「算法建议」那一列是 `Text`（**一句中文**），不是 JSON，也**没有任何写入方去改处方**——它是给教师看的建议，与 §8.4 那个会自动生效的「减量 20%」刻意不对称。→ **#40**
> 2. **§9.1 的第 ④ 块「异常名单」不落库**：`app.pipeline.report_stage.aggregates_of` 产出**七个**聚合量，落库的只有**六个**（本表的 5 个 JSON 列 + 1 个 Text 列），`abnormal_roster` 只由 `GET /api/dashboard/class/{id}` 现算现给。理由：它是 §9.1 的一个**实时筛选器**、不是本节那 6 项里的一项，而本表没有它的位置。
>
> **→ §14 新编号 #40**（「算法建议」的查表规则与两个阈值是本设计自己定的，spec 只给了形状没给口径）。"""
after(A, I, "§4.7 weekly_class_report")

# ---------------------------------------------------------------------------
# §8.1 —— 打卡的三个模糊点（→ #39）
# ---------------------------------------------------------------------------
A = ("打卡窗口 = 当日 00:00–22:00。22:00 后提交仍入库但标记 `late = true`，"
     "**不计入当日完成**——完成率是 RCT 关键过程指标，必须严格。")
I = """

> ### ⚠️ 勘误（Plan 03 Task 9 补）：这一句有**三个模糊点**，实现一律「响亮地定一个口径并测边界」
>
> **原文**（`:636`）逐字是「打卡窗口 = 当日 00:00–22:00。22:00 后提交仍入库但标记 `late = true`，**不计入当日完成**」。它答不了三个问题，而三个都会在真实数据上出现：
>
> | # | 模糊点 | 实现的口径 | 为什么这么定 |
> |---|---|---|---|
> | ① | **22:00:00 整点算哪边** | 窗口是**闭区间** `[00:00, 22:00]`，判定式是 `submitted_at.time() > CHECKIN_DEADLINE`（**不是 `>=`**）：`21:59:59` 不迟、`22:00:00` **不迟**、`22:00:01` 迟。⚠️ 下界 `00:00` **不需要判**（`datetime.time` 的最小值就是它，任何时刻都 `>=`）。 | 原文写的是「22:00 **后**」，而 `22:00:00` 整点不是「后」。⚠️ 三条守卫只差一秒，故把 `>` 改成 `>=` 只有中间那条会红——那正是「边界测试」要的形状。 |
> | ② | **补卡算不算** | **照收、但不计入完成率**：写入侧 `POST /api/training-logs` 对 `log_date != submitted_at.date()` 的请求照样 201；读侧的分子多一个条件 `submitted_at.date() == log_date`。 | 补卡是学生主动补交的作业，拒收它等于把数据丢掉；而完成率要严，故排除落在**读侧**——两个决定各在自己那一层做。⚠️ 这一条**需要** `training_log.submitted_at` 那一列，而原文的字段清单里没有它（`late` 表达不了：一个 21:00 交的补卡 `late = False` 却仍然不该计入那一天）。见 §4.5 的勘误。 |
> | ③ | **服务器时钟与学生本地时钟不一致 / 跨时区** | **一律用服务端时区**：`submitted_at` 由服务端填（请求模型上**没有**这一格，结构上不可伪造），时区的唯一所有者是 `app.config.TIMEZONE = "Asia/Shanghai"`（一个 IANA 名字，不是 `"+08:00"` 这类固定偏移），判定式是 `datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None)`。 | 学生端的时钟可以被改，而它是 RCT 的过程指标。⚠️ `replace(tzinfo=None)` **是承重的**：本仓的 `DateTime` 列存 naive（SQLite 没有时区类型），aware 与 naive 相比会当场 `TypeError`。⚠️ **原型口径：不处理跨时区学生**——一个在别的时区的学生会被按本时区的 22:00 判迟；要支持就得给 `training_log` 加一列存学生的时区，那是后续批次的活。 |
>
> **→ §14 新编号 #39**（三条都是口径裁决，且第 ③ 条的「不处理跨时区」是一个**已知偏差**，须由项目负责人确认是否可接受）。"""
after(A, I, "§8.1 打卡三个模糊点")

# ---------------------------------------------------------------------------
# §8.1 —— 标准化得分的算式住址与「进步榜在生成时算」
# ---------------------------------------------------------------------------
A = """```text
深蹲得分   = 深蹲次数（越大越好，直接用）
折返得分   = 该教学班内折返秒数的百分位反查（秒数越少 → 得分越高）
小测综合分 = 两项标准化得分等权平均
```"""
I = """

> ### ⚠️ 勘误（Plan 03 Task 9 补）：这三行的**算式住址**与**什么时候算**，spec 都没说
>
> **原文**（`:648`–`:652`）只给了算式。实现把它落成两条口径，两条都是本节读不出来的：
>
> 1. **算式只有一个住址**：`app.domain.report.shuttle_percentile`（班内百分位反查）+ `app.domain.report.mini_test_scores`（三格：`squat_score` / `shuttle_score` / `composite`）+ `app.domain.report.SCORE_PRECISION = 2`。⚠️ 它有**两个消费者**：`GET /api/mini-tests/normalized`（教师录完成绩当场看）与 `app.pipeline.report_stage._composite_of`（周日生成班级周报时算进步榜）。两处**共用同一份**，故「教师当场看到的分」与「周报上的进步榜」不可能漂开；守卫是一条 AST 断言（数定义份数 == 2，即那两个函数各一份、都在 `app/domain/report.py`）。⚠️ 它原先住在 `app/api/routers/feedback.py` 的私有 `_shuttle_percentile` 里，Plan 03 Task 9 搬进 domain——因为 `pipeline` 反向 import `api` 被架构守卫禁止，而在 pipeline 里再写一份就是第二个所有者。
> 2. **进步榜的分在生成周报时算、不由前端读时算**：`weekly_class_report.progress_board` 里存的是**已经算好的** `change_pct`。理由是**周报是快照，而快照里的量应该在生成时就算好**——让前端去调 `GET /api/mini-tests/normalized` 现算，等于把「哪一周的进步榜」这个口径交给了客户端，同一份周报在不同时刻读出来会给出**不同**的榜。
>
> ⚠️ **百分位反查的两条细节**（本节没写、实现里是承重的）：① 公式是标准的 percentile rank、**并列取中点**（`(比自己慢的人数 + 0.5 × 并列人数) / 样本数 × 100`），故三个人跑出一样的秒数时他们拿到**同一个** 50.0 而不是三个不同的分；② **`shuttle_20m_s IS NULL` 的行不进样本**——一个「没测」的人若被当成「最慢的那个」，会把全班的百分位一起往下拽（所有人都变好）。
> ⚠️ **`mini_test.normalized_score` 那一列刻意不回写**：让一个 `GET` 有副作用本仓不接受，而让批处理去 UPDATE 一张**教师手工录入**的表会把「教师录的是什么」与「系统算出来的是什么」混在同一列上（`mini_test` 是 RCT 的过程数据）。故那一列今天的唯一写入方是 `app.demo_data.build_demo_feedback`（**演示口径的近似值**），而它的读者只剩 `app.pipeline.alert_stage._mini_test_improved`（`GREEN_MASTERY` 的三个指标之一）。⚠️ **代价**：`GREEN_MASTERY` 读的是列里的近似值、进步榜读的是算出来的值，**两者可以不同**——已移交 Plan 04（要统一就得让 `alert_stage` 也现算，而它按学生分组、拿不到「班」这个维度，先要裁决「一个学生在两个班时按哪个班算」）。
> ⚠️ **量纲是混的**（次数 vs 百分位），故 `composite` 不是一个可以跨班比较的绝对量；它今天的两个消费者都只用它做**同一个班内**的相对比较，把它当成「体能总分」显示给学生看是错的（Plan 04 的前端要注意）。
> **→ §14 无新编号**：算式本身是本节给的，实现只补了「住址」与「什么时候算」两条工程口径。⚠️ 而「单人班的百分位给 50.0 看起来像真排过名」那一格**移交 Plan 04**（应在 `scored_count == 1` 时显示「无排名」，`scored_count` 已经在响应里给出去了）。"""
after(A, I, "§8.1 标准化得分的住址")

# ---------------------------------------------------------------------------
# §8.2 —— YELLOW_CHECKIN_GAP 的人群口径 + 阈值个数是 9 不是 8
# ---------------------------------------------------------------------------
A = ("| 4 | 「二次小测提升」（绿色激励） | 任一指标改善 ≥ **3%**。与下降阈值 5% 刻意不对称"
     "——正向激励应更宽松，让学生更容易拿到 |")
I = """

> ### ⚠️ 勘误（Plan 03 Task 9 补）：`YELLOW_CHECKIN_GAP` **只对「本周有训练单」的学生可判**；而 `alert_rules.yaml` 的阈值是 **9** 个、不是 8 个
>
> **① 人群口径（本节读不出来，而它决定「谁永远不会被这条规则看到」）**
>
> 上表第 3 行「打卡中断 2 天」的判据是「连续 2 个**应打卡训练日**未打卡」，而**「什么是应打卡训练日」由该生的处方训练单算出来**（本节与 §8.1 的折中方案都这么说）。于是它有两层收窄，两层都是刻意的：
>
> * **求值人群** = 「本学期在三源里留过痕的学生」（`rpe_record` ∪ `mini_test` ∪ `training_log` 三个来源的 `student_id` 并集，其中 `training_log` 那一份**只按学期起点收窄、不按回看窗口收窄**）。⚠️ 后一半是承重的：用同一个 3 周回看窗口的话会漏掉最该被提醒的那一类人——一个连续失联 4 周的学生在那 3 周里**一行 `training_log` 都没有**，于是他不在人群里、于是本规则对他**永远不触发**，而它存在的理由逐字就是「打卡中断」。
> * **可判性**：一个在人群里、但**本周没有生效处方**（或处方已到期、或那一周 `paused`、或处方训练日与本周一天都不相交）的学生，「应打卡训练日」这个基线**无从算起** → 中断天数记为 `None`（**判不了**）而不是 `0`。⚠️ 于是「一个本学期从没在任何一源留过痕的学生」**不会被求值**，而「留过痕但本周没有训练单的学生」**被求值、但这一条判不了**——两档都在 `daily_sync_run` 之外留了痕（前者不在人群里、后者进 `AlertReport.skipped` 的计数）。
>
> ⚠️ **代价**：一个刚转进来、还没被任何一源采集到的学生，即使他真的一天都没练，也不会收到补练提醒。**这是「宁可不报，也不要报一个没有依据的数」那一侧的错**（`0` 天中断会被学生读成「系统说我今天该练而我没练」，而他本周根本没有训练单）。
>
> **② 阈值个数是 9 个、不是 8 个**
>
> `backend/data/alert_rules.yaml` 的 5 条规则逐条的参数个数是 **3 / 2 / 1 / 1 / 2 = 9**：
> `RED_MINITEST_DROP` = `consecutive` + `drop_pct` + `points_needed`；`RED_RPE_SUSTAINED` = `rpe_min` + `streak`；`YELLOW_CHECKIN_GAP` = `gap_days`；`YELLOW_CLASS_RPE_HIGH` = `mean_rpe_max`；`GREEN_MASTERY` = `completion_rate_min` + `improve_pct`。
> ⚠️ **Plan 03 的计划正文与派单一路写「8 个阈值」，那个数对不上任何一条口径**（既不是规则数 5、也不是参数数 9）；代码与测试一律按 **9** 走（加载器 `app.refdata_alerts._PARAM_TYPES` 逐规则钉住键集，多一个键与少一个键都在**加载时**响亮失败）。
>
> ⚠️ **另有两个阈值在 domain 里不被读**（`app/domain/alerts.py` 的模块 docstring 逐字记了）：`rpe_min`（那个 9）与 `improve_pct`（那个 3%）——`rpe_streak` 与 `mini_test_improved` 是 `app.pipeline.alert_stage` **算好再传进来**的（它才读得到 `rpe_record` / `mini_test` 两张表），故 domain 无从校验这两个阈值被用对了。两者仍原样进 `alert.trigger_snapshot`，于是「这条预警当时按哪一版阈值判的」可以离线复核。
> **→ §14 无新编号**：①是本节判据的**人群前提**（实现期才浮出来的口径，已逐字写进 `app.pipeline.alert_stage` 的模块 docstring），②是计划正文的一个错数。"""
after(A, I, "§8.2 人群口径 + 9 个阈值")

# ---------------------------------------------------------------------------
# §8.4 —— auto 来源已落地；reason 不带版本号
# ---------------------------------------------------------------------------
A = ("「周周微调」与「4 周微周期」由此同时成立：微调改的是**本周训练量**，不是重开周期。"
     "预警触发的「减量 20%」落成一条 `weekly_adjustment(系数 0.8, 原因 RED_RPE_SUSTAINED)`，"
     "可追溯、可回滚。")
I = """

> ### ⚠️ 勘误（Plan 03 Task 9 补）：`source = "auto"` **已由 Plan 03 Task 7 落地**；而「当时按哪一版阈值判的」**不写进 `reason`**
>
> **原文**（`:701`）只给了 `weekly_adjustment(系数 0.8, 原因 RED_RPE_SUSTAINED)` 这一个例子。实现的两条口径：
>
> 1. **`source = "auto"` 的写入方是 `app.pipeline.alert_stage._write_auto_adjustment`**：一条 `red` 预警落库的**同一批**里就自动写一条 `factor = 0.8` / `reason = <规则 ID>` / `source = "auto"` 的调整，**不等教师点击**。⚠️ 而**推送**要等教师点击（`POST /api/alerts/{id}/handle` 的 `reduce_20pct` 那一档）——两者刻意不是一件事：减量是系统对「这个学生练得太苦」的**保护性动作**，而推送是**告诉学生**这件事，后者要教师先看过一眼（教师可能知道一个系统不知道的理由：学生受伤了、这周月考，那时正确的处置是 `ignore`）。⚠️ 于是 `weekly_adjustment` 表**不再是 0 行**（§14 #34 的正文里那句「今天 `weekly_adjustment` 表 0 行……`source = "auto"` 是 Plan 03 的预警落地」已到期兑现）。
> 2. **`reason` 那一列刻意不带 `alert_rules.yaml` 的版本号**。它是 `UniqueConstraint("prescription_id", "week", "reason", "source")` 的一列，把版本号拼进去等于「**升一次版本号 = 同一周可以再减一次量**」→ `0.8 × 0.8 = 0.64`，而教师只以为自己减了一次。⚠️ **版本号改落 `alert.trigger_snapshot["alert_rules_version"]`**：那一格是一个 `JsonText` 列、不进去重键，于是「这条预警当时按哪一版阈值判的」照样可离线复核，而减量仍然一周只发生一次。
>
> ⚠️ **去重的两道闸门**（本节没写，而它们是「减量不被连乘」的全部保证）：① 上面那条 `UniqueConstraint` 让 **DB 当裁判**（`_write_auto_adjustment` 用裸 INSERT + 自己的 SAVEPOINT，撞上就返回「没写」）；② `POST /api/alerts/{id}/handle` 对一条 `status != "pending"` 的预警回 **409 `alert_not_pending`**，故教师点两次「减量 20%」第二次是 409、不是 `0.64`。⚠️ 而 ① 命中时**消息照发**：教师点了「减量 20%」，学生就该被告知「本周的量减了 20%」——哪怕那一条调整是管道几天前就写好的。
> **→ §14 无新编号**：#34 已经裁决了「同一周多条调整怎么合成」（相乘），本条只是交代 `auto` 那一半已经落地、以及版本号为什么不进 `reason`。"""
after(A, I, "§8.4 auto 来源与版本号")

# ---------------------------------------------------------------------------
# §8.5 —— 算法建议（→ #40）
# ---------------------------------------------------------------------------
A = ("- **算法建议**：基于 `YELLOW_CLASS_RPE_HIGH` 等班级级信号，"
     "给出「本周建议整体降量/加量 X%」")
I = """

> ### ⚠️ 勘误（Plan 03 Task 9 补）：「算法建议」的 `X%` 与查表规则 spec 没给，实现定成**一条三档查表**
>
> **原文**（`:712`）逐字是「基于 `YELLOW_CLASS_RPE_HIGH` **等**班级级信号，给出『本周建议整体降量/加量 X%』」——`X` 是一个占位符，而「等」字没有点名第二条信号。实现（`app.domain.report.suggestion`）落成**自上而下、命中即停**的三档：
>
> | 条件 | 返回 |
> |---|---|
> | `class_rpe_high` 为真（本周这个班有一条 `rule_id = YELLOW_CLASS_RPE_HIGH` 的 `alert` 行） | 「本周建议整体降量 **10%**」 |
> | 本周人均 RPE 可测 **且** `< 5.0`（**严格**小于） | 「本周建议整体加量 **10%**」 |
> | 其余（含「本周一次快评都没有」→ 人均 RPE 为 `None`） | 「维持当前强度」 |
>
> ⚠️ **优先级是承重的**：`class_rpe_high` 排第一，故一个班同时「课堂 RPE 均值超线」与「整周人均很低」时给出**降量**——两档方向相反，顺序反了结论就反了。⚠️ 那一档在**今天的两个阈值下不可达**（`YELLOW_CLASS_RPE_HIGH` 要均值 `> 7.0`，加量要均值 `< 5.0`），仍把顺序钉住的理由是**它们是两个独立的所有者**：专家把 `mean_rpe_max` 调到 4.5 之后那一档立刻可达，而那时「先判低 RPE」会给出加量建议——对一个刚刚因为「课太累」被开了工单的班。
> ⚠️ **`class_rpe_high` 是布尔、由调用方从「本周有没有那一条 `alert` 行」得出，不在这里重算一遍阈值**：那份阈值的所有者是 `data/alert_rules.yaml`，在 domain 里再比一次 `mean_rpe > 7` 就是第二个住址，而专家改一次 YAML 之后两处会给出两个结论。
> ⚠️ **`10%` 与 §8.4 的「减量 20%」刻意不对称**：20% 是对**单个学生**的处置且**系统自动执行**（写一条 `weekly_adjustment(source="auto")`，学生端当周的训练单立刻变），10% 是**班级级建议**、给教师看的、**不自动执行**（它落进本表那一列，是一句中文，没有写入方去改任何处方）。一个会自动生效的动作可以激进一点（它保护的是「这个学生练得太苦」），一个只是建议的动作应当温和一点（教师可能知道一个系统不知道的理由）。
> ⚠️ **`mean_rpe` 为 `None` 时不得折成 `0.0`**：那会让「本周没测」变成「一点都不累 → 建议加量 10%」，一句**建立在缺失数据上的建议**，而教师无从看出它没有依据。
> **→ §14 新编号 #40**（三档查表、两个阈值、以及它与 §8.4 的不对称，全部是本设计的默认规定，须由体育专家确认）。"""
after(A, I, "§8.5 算法建议")

# ---------------------------------------------------------------------------
# §9.1 —— 大屏两个阈值的住址（⚠️ 顶回简报：不在 alert_rules.yaml 的 screen: 段）
# ---------------------------------------------------------------------------
A = ("> **规定：两套并存，职责不同。** 预警是需要教师处理的**正式工单**（阈值严、有处理流程与状态机）；"
     "大屏异常名单是课堂即时扫视用的**宽松筛选器**（阈值松、只展示不派单）。"
     "本条须在评审材料中主动说明，避免被追问。")
I = """

> ### ⚠️ 勘误（Plan 03 Task 9 补）：那两个阈值（连续 **3** 天 / RPE > **8**）的**住址**是 `app/domain/report.py`，**不是** `alert_rules.yaml`
>
> **原文**（`:738`–`:740`）把两个阈值写在散文里，Plan 03 的计划正文据此要求「改成落在 `alert_rules.yaml` 的 `screen:` 段，并引 §14 #11 的『两套并存』裁定」。⚠️ **实现者顶回了这一条**：`alert_rules.yaml` 里**没有** `screen:` 段，两个阈值住在 `app/domain/report.py` 的两个具名常量 `SCREEN_GAP_DAYS = 3` 与 `SCREEN_RPE_MAX = 8`，并由 `tests/domain/test_report.py::test_the_screen_thresholds_are_not_the_alert_thresholds` 钉住「它们与预警那两个**不相等**」（改成相等 → 当场红）。
>
> **理由**（Plan 03 Task 8 的裁定 P8-A6，两条）：
>
> 1. **`alert_rules.yaml` 的所有者是「5 条判据的阈值」**，而大屏那两个数**不是判据**——它们不产生工单、不产生任何写入，只是 §9.1 那个**滚动名单**的筛选器。加载器 `app.refdata_alerts._PARAM_TYPES` 逐规则钉住键集（多一个键、少一个键都在**加载时**响亮失败），给它加一个不属于任何规则的 `screen:` 段要么破坏那道校验、要么给它开一个例外；
> 2. **加它要按 Plan 02 的 P9-A3 六步程序走**（重算 sha256 指纹 `ALERT_RULES_FINGERPRINT`、复核 CRLF、同步常量，而**另四个指纹必须逐字不变**），换来的只是「两个数换一个文件住」。
>
> ⚠️ **代价（硬规矩 #39）**：于是「大屏的两个阈值」与「预警的五个规则的九个阈值」住在**两个不同的地方**，一个专家想「把两边一起调松」时要改两个文件、走两套评审（一个是代码 review、一个是 YAML 的版本控制）。⚠️ 而 #11 那条「两套并存」的裁定**恰恰要求它们不同**，故这个代价与裁定同向、不是漂移。
> ⚠️ **两个阈值今天没有任何 spec 出处之外的依据**（它们就是本节那张 ASCII 图里的两个字面量），故它们是**待体育专家确认**的工程约定，与 Plan 02 处理 `Intensity.rpe` 的方式一致 → 归 #11 一并裁决，**不新开编号**。
> ⚠️ 另两格实现口径（本节读不出来）：① 判的是本周课堂快评的**峰值** RPE（`max`）而不是均值，且**只要一次**超过 8 就上名单——与预警那一条「**连续** ≥ 9」的判据**形状**也不同；② `abnormal_roster` **不落库**（见 §4.7 的勘误），它只由 `GET /api/dashboard/class/{id}` 现算现给。
> **→ §14 无新编号**（归 #11）。"""
after(A, I, "§9.1 大屏两个阈值的住址")

# ---------------------------------------------------------------------------
# §14 —— #38 / #39 / #40 三行 + 三段编号说明
# ---------------------------------------------------------------------------
ROW38 = ("| **38** | **`alert.window_key`：spec §4.6 的字段清单里没有这一列，而它是「同一次触发只开一条工单」的唯一载体** | "
         "**加一列 `window_key`（`String(32)`，NOT NULL），与 `rule_id` / `subject_key` / `semester_id` 组成四列 `UniqueConstraint`，让 DB 当去重的裁判。** "
         "§4.6 的清单里没有「窗口」这个维度，而没有它，同一条 `RED_RPE_SUSTAINED` 在连续第 3、4、5 次快评都满足条件时会生成 **3** 条 `alert`、推 **3** 次「减量 20%」、把训练量连乘成 `0.8³ = 0.512`——而全链路没有一处报错（Plan 03 Review Focus 第 3 条点名的正是这个形状）。"
         "⚠️ **取值算式逐规则不同**，且住在 `app/domain/alerts.py`（纯函数、可穷举）：`RED_RPE_SUSTAINED` = `rpe{凑满 streak 那一次的 class_session_id}`（**不是最后一次**：锚在最后一次的话 streak 再长键也会天天变）；`RED_MINITEST_DROP` = `mt{最后一次小测的 id}`（小测不是每堂课都有，一次新小测是一次**新的观测窗口**，锚在最后一次才对）；`YELLOW_CHECKIN_GAP` = `gap{中断结束日的 ISO 串}`；两条周级规则 = `{semester_id}:{week}`。"
         "**须由项目负责人确认的是「哪一次触发算同一次」这个口径本身**：它直接决定教师看到几条工单、学生被减几次量。 | "
         "**§4.6、§8.2** | "
         "`alert` 表的一列 + 一条 `UniqueConstraint`（`uq_alert_rule_subject_semester_window`）；`app.domain.alerts` 的四条 `window_key` 算式与 `subject_key` 的两个前缀常量；`app.pipeline.alert_stage._persist`（**先 SELECT 后 INSERT、不走 `repo.upsert`**：upsert 的更新分支会把一条已经 `handled` / `ignored` 的预警**静默改回** `pending`、并把 `triggered_at` 与 `trigger_snapshot` 一起换掉，教师处置过的痕迹就此消失）；`tests/db/test_models.py` 钉住列宽与最长形状（`section:2147483647` = 18 字符、余量 6，而 `course_section:2147483647` 是 25 字符、**超宽 1**，故前缀必须是 `section`） |")

ROW39 = ("| **39** | **§8.1 打卡窗口的三个模糊点：22:00 整点算哪边 / 补卡算不算 / 用谁的时钟** | "
         "**① 窗口是闭区间 `[00:00, 22:00]`**，判定式 `submitted_at.time() > 22:00`（**严格大于**，故 `22:00:00` 整点**不算迟**、`22:00:01` 算）；下界不需要判（`datetime.time` 的最小值就是 `00:00`）。"
         "**② 补卡照收、但不计入完成率**：写入侧对 `log_date != submitted_at.date()` 的请求照样 201，读侧的分子多一个条件 `submitted_at.date() == log_date`——补卡是学生主动补交的作业，拒收它等于把数据丢掉，而完成率是 RCT 关键过程指标、要严，故排除落在**读侧**（两个决定各在自己那一层做）。"
         "**③ 一律用服务端时区**：`submitted_at` 由服务端填（请求模型上**没有**这一格，结构上不可伪造），时区的唯一所有者是 `app.config.TIMEZONE = \"Asia/Shanghai\"`（一个 IANA 名字，不是 `\"+08:00\"` 这类固定偏移——固定偏移不处理夏令时），判定式 `datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None)`。"
         "⚠️ **③ 的代价是一个已知偏差**：原型**不处理跨时区学生**，一个在别的时区的学生会被按本时区的 22:00 判迟；要支持就得给 `training_log` 加一列存学生的时区。**须由项目负责人确认这三条口径**（尤其 ③ 的偏差是否可接受）。 | "
         "**§8.1** | "
         "`app.api.routers.feedback.CHECKIN_DEADLINE`（那个 `dt.time(22, 0)`）与它的**严格大于**判定式；`training_log.submitted_at` 那一列（⚠️ spec §4.5 的字段清单里没有它，而 ② **需要**它——`late` 表达不了「补卡」：一个 21:00 交的补卡 `late = False` 却仍然不该计入那一天）；完成率的**分子四个条件**有**两个所有者**（`app.api.routers.feedback.completion_rate` 与 `app.pipeline.alert_stage._counted_checkin_days`），由 `tests/pipeline/test_alert_stage.py` 的一条测试钉成逐字相等；三条只差一秒的边界测试（`21:59:59` / `22:00:00` / `22:00:01`），把 `>` 改成 `>=` 只有中间那条会红 |")

ROW40 = ("| **40** | **§8.5「算法建议」的 `X%` 与查表规则：spec 只给了形状、没给口径** | "
         "**一条自上而下、命中即停的三档查表，步长 10%**：① 本周这个班有一条 `YELLOW_CLASS_RPE_HIGH` 的 `alert` 行 → 「本周建议整体降量 10%」；② 本周人均 RPE 可测**且** `< 5.0`（严格小于）→ 「本周建议整体加量 10%」；③ 其余（含「本周一次快评都没有」→ 人均 RPE 为 `None`）→ 「维持当前强度」。"
         "⚠️ **优先级承重**：两档方向相反，顺序反了结论就反了；而那一档在**今天的两个阈值下不可达**（要 `> 7.0` 又要 `< 5.0`），仍钉住顺序的理由是**它们是两个独立的所有者**——专家把 `mean_rpe_max` 调到 4.5 之后那一档立刻可达。"
         "⚠️ **`10%` 与 §8.4 的「减量 20%」刻意不对称**：20% 对**单个学生**、**系统自动执行**（写 `weekly_adjustment(source=\"auto\")`，学生端当周的训练单立刻变）；10% 是**班级级建议**、给教师看的、**不自动执行**（落进 `weekly_class_report.suggestion` 那一列，是一句中文，没有写入方去改任何处方）。一个会自动生效的动作可以激进一点，一个只是建议的动作应当温和一点（教师可能知道一个系统不知道的理由）。"
         "⚠️ `mean_rpe` 为 `None` 时**不得折成 `0.0`**：那会让「本周没测」变成「一点都不累 → 建议加量 10%」。**须由体育专家确认这条查表规则与两个阈值（10% / 5.0）。** | "
         "**§8.5** | "
         "`app/domain/report.py` 的 `SUGGESTION_STEP_PCT = 10` / `CLASS_RPE_LOW_MAX = 5.0` / 三句文案常量（⚠️ 文案由 `SUGGESTION_STEP_PCT` **生成**、不手写第二遍：改一个数而忘了改文案，教师看到的建议就与系统据以判的数不符，而那一列是 `Text`、没有 CHECK 也没有词表，没有任何东西会拦）；`weekly_class_report.suggestion` 那一列；`tests/domain/test_report.py` 的 `test_the_suggestion_step_is_ten_percent_and_the_auto_reduction_is_twenty`（把 10 与 20 改成同一个数 → 当场红）与 `test_the_class_signal_beats_the_low_rpe_signal`（优先级）。⚠️ **`class_rpe_high` 是布尔、由调用方从 `alert` 表得出，不在 domain 里重算阈值**：那份阈值的所有者是 `data/alert_rules.yaml` |")

A = "\n\n**⚠️ 编号说明（Plan 02 Task 9 结案）**：本表现在是**编号 1–37 连续、共 37 行、无空洞**。"
I = ("\n" + ROW38 + "\n" + ROW39 + "\n" + ROW40 +
     "\n\n**⚠️ 编号说明（Plan 03 Task 9 更新）**：本表现在是**编号 1–40 连续、共 40 行、无空洞**"
     "（Plan 02 Task 9 结案时是 1–37；Plan 03 Task 9 追加 #38 / #39 / #40 三行，"
     "三行都照 18–37 的加粗格式写）。")
EDITS.append(("§14 追加三行 + 编号说明", A, I))

A = ("三批写入的归属：**#28** 由 Plan 02 **Task 2** 写入")
I = ("四批写入的归属：**#38 / #39 / #40** 由 **Plan 03 Task 9** 写入"
     "（#38 = `alert.window_key` 的去重口径；#39 = §8.1 打卡窗口的三个模糊点；"
     "#40 = §8.5「算法建议」的查表规则与两个阈值）。\n\n"
     "三批写入的归属：**#28** 由 Plan 02 **Task 2** 写入")
EDITS.append(("§14 写入归属", A, I))

A = "**⚠️ 编号 18–37 一律加粗写**（`| **18** | …`），与 1–17 的不加粗格式不同。"
I = ("**⚠️ 编号 18–40 一律加粗写**（`| **18** | …`），与 1–17 的不加粗格式不同。")
EDITS.append(("§14 加粗范围", A, I))

A = ("这是**刻意**的：从 18 起那一批全部是**实现期撞见的空洞**"
     "（写代码 / 写 YAML 的人发现 spec 没给口径，当场登记），加粗让它们在一张 37 行的表里一眼可辨；"
     "本 Task 追加的 7 项同属这一类，故照 18–31 的格式写，不照 1–17。")
I = ("这是**刻意**的：从 18 起那一批全部是**实现期撞见的空洞**"
     "（写代码 / 写 YAML 的人发现 spec 没给口径，当场登记），加粗让它们在一张 40 行的表里一眼可辨；"
     "Plan 02 Task 9 追加的 7 项与 Plan 03 Task 9 追加的 3 项同属这一类，"
     "故照 18–31 的格式写，不照 1–17。")
EDITS.append(("§14 加粗范围的理由", A, I))


def main() -> int:
    raw = SPEC.read_bytes()
    before_sha = hashlib.sha256(raw).hexdigest()[:16].upper()
    crlf0 = raw.count(CRLF)
    bare0 = raw.count(LF) - crlf0
    print(f"改前: {len(raw)} B sha256[:16]={before_sha} CRLF={crlf0} bare LF={bare0} "
          f"lines={bare0 + crlf0 + 1}")
    assert bare0 == 0, "本文件工作树应当全是 CRLF，实测有裸 LF"

    text = raw.replace(CRLF, LF).decode("utf-8")
    for label, old, new in EDITS:
        hits = text.count(old)
        assert hits == 1, f"{label}: 锚点命中 {hits} 次（应为 1）：{old[:70]!r}"
        text = text.replace(old, new)
        print(f"  ✓ {label}")

    out = text.replace("\n", "\r\n").encode("utf-8")
    SPEC.write_bytes(out)
    after = SPEC.read_bytes()
    crlf1 = after.count(CRLF)
    bare1 = after.count(LF) - crlf1
    print(f"改后: {len(after)} B sha256[:16]={hashlib.sha256(after).hexdigest()[:16].upper()} "
          f"CRLF={crlf1} bare LF={bare1} lines={bare1 + crlf1 + 1}")
    assert bare1 == 0
    # 复核：#38/#39/#40 三行都在、且编号 1..40 各出现一次（数**行首**的表格编号，
    # 不用正则抽编号——#155 的成因正是那个正则只匹配到未加粗的 1–17）
    lines = after.replace(CRLF, LF).decode("utf-8").split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith("## 14. 待确认事项清单"))
    end = next(i for i, line in enumerate(lines) if line.startswith("## 15. 后续批次规划"))
    rows = [line for line in lines[start:end] if line.startswith("| ") and not line.startswith("|---")
            and not line.startswith("| # |")]
    print(f"§14 表格行数（数换行 + 校验首尾两行）= {len(rows)}")
    print(f"  首行: {rows[0][:60]}…")
    print(f"  末行: {rows[-1][:60]}…")
    assert len(rows) == 40, f"§14 应当是 40 行，实测 {len(rows)}"
    assert rows[-1].startswith("| **40** |"), rows[-1][:40]
    assert rows[0].startswith("| 1 |"), rows[0][:40]
    return 0


if __name__ == "__main__":
    sys.exit(main())

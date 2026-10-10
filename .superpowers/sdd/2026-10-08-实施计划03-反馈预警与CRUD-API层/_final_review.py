"""Plan 03 全分支终审的记账 + 确认 main 已推送。"""
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LEDGER = HERE / "progress.md"


def git(*a):
    r = subprocess.run(["git", *a], cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return (r.stdout or r.stderr).strip()


print("### git 状态")
print(f"  当前分支 = {git('rev-parse', '--abbrev-ref', 'HEAD')}")
print(f"  HEAD = {git('log', '--oneline', '-1')}")
print(f"  main 与 origin/main 的差 = {git('rev-list', '--count', 'origin/main..main')} 个 commit（应 0）")
print(f"  特性分支与 origin 的差 = "
      f"{git('rev-list', '--count', 'origin/feature/plan-03-feedback-alert-crud-api..feature/plan-03-feedback-alert-crud-api')} 个")
print(f"  git status -> {git('status', '--short') or '（干净）'}")
print(f"  a5f16b1..HEAD 的 commit 数 = {git('rev-list', '--count', 'a5f16b1..HEAD')}")

b = LEDGER.read_bytes()
t = b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"\n[ledger before] bytes={len(b)} lines={t.count(nl)}")

BODY = """

---

## 🏁 Plan 03 全分支终审（Ruling 5 保留的那一席独立评审者）+ 合入 main

**合并**：`git checkout main` → `git merge --ff-only feature/plan-03-feedback-alert-crud-api` → **fast-forward `a5f16b1..a544c96`（54 个 commit）**，与 Plan 01/02 同口径、不造 merge commit。两个分支都已推送。

**终审的基线复现：账本里每一个可复核的数字它都独立复现了，一个不差** —— `1244 passed`（154.71 s）、`app/domain` **1268/0/376/0/100%**、`/api/` **63 路径 / 91 操作**、读写矩阵 **23 / 可写 9 / 只读 14 / restrict 12 / forbid 10 / cascade 1**、`natural_key is None` **恰好 3 个**（`course-sections` / `fitness-test-batches` / `notifications`）、显式 `pk_alias` **恰好 1 行**（`fitness-test-batches`）、`JsonText` 自动探测 **19 列 / 8 张表**、路径参数名 **distinct 23、无 `pk_value`**、`securitySchemes` **恰好 2 格**、18 个操作带 `security`、**五个指纹不变**、`pe.db` 不存在、`data/seed` 0 文件。

**⚠️ 它没有停在读覆盖率表，而是做了 9 个定点变异（改真源码、二进制读写保住 CRLF、`finally` 还原、跑完 `git status` 干净）：9/9 killed、0 survived**，其中两条正是 Review Focus #3 承重的 `window_key` 锚点（`_rpe_sustained` 的 `[needed-1]` → `[-1]`、`_minitest_drop` 的 `mt[-1]` → `mt[0]`）。**并用 AST 逐字段核对 `StudentSignals` 的 11 个与 `ClassSignals` 的 5 个字段全部在 `app/domain/alerts.py` 里被 Load —— 无死配置。** 它的结论是「**100% 分支覆盖名副其实**」。

### Ruling 21 — 终审查出 1 Critical / 4 Important / 3 Minor，其中 **C1 是控制者与 9 个实现者全都漏掉的**

**⚠️ C1（Critical）：一个学生同一处方周命中两条不同的红色规则时，减量被连乘成 `0.64`，而 spec §8.4 逐字是「减量 20%」，教师端推送的文案还说「减了 20%」。**

**它给了两次独立复现，都不是推测**：
- **复现 A（合成最小例，走真 `evaluate_alerts`）**：一个学生同时满足 `RED_MINITEST_DROP` 与 `RED_RPE_SUSTAINED` → `raised=4 by_level={'red':2,'yellow':2} adjustments_written=2`，`weekly_adjustment` 落下**两行**（`week=3 factor=0.8 reason=RED_MINITEST_DROP source=auto` 与 `week=3 factor=0.8 reason=RED_RPE_SUSTAINED source=auto`），`weekly_factors_of` 返回两条，**`weekly_training_sheet(pkg, 3, factors).factor == 0.6400000000000001`**。
- **复现 B（项目自带的演示数据集，`demo_bootstrap` 60 人 / `seed=20250828` / `as_of=2025-10-12`）**：10 个受影响（处方，周）里**有 1 个**带两条 auto 调整（`prescription_id=11 week=1`），**该周训练单的 factor 就是 `0.6400000000000001`**。**即：跑一次 `demo.ps1` 就会产出这个状态。**

**为什么全链路无一处报错**：两个四列唯一约束（`uq_alert_rule_subject_semester_window` 与 `uq_weekly_adjustment_prescription_week_reason_source`）挡住的是「**同一条规则**重复触发」，而 `reason` 在键里 → **两条不同规则各写一行是约束允许的**。`alert_stage.py:31-49` 明写的「三道闸门，各挡一段」没有一道覆盖它。**而 `0.64` 这个数在 6 处 docstring 里被逐字点名为「Review Focus #3 要挡的失效形态」**（`alerts.py:268`、`api/routers/alerts.py:233`、`alert_stage.py:678`）—— **今天它从第三个门进来了。**

**⚠️ 连带一句关于学生的假话**：`api/routers/alerts.py:327-331` 的文案是 `f"把本周的训练量减了 {int(round((1.0 - AUTO_REDUCTION_FACTOR) * 100))}%"` → **恒为「减了 20%」，而实际是 36%**。

**⚠️ 零守卫**：`test_alert_stage.py` 的 36 条测试**没有一条让两条红色规则同时命中**；`test_end_to_end.py:443` 断言「`0.8` 而不是 `0.64`」，但它的场景也只有一条红色。

**它如实给了减轻情节**：`weekly_training_sheet` 的 `reasons`/`sources` 保留两个理由、`alert` 表也有两行，**可追溯性没丢**；`weekly.py:359-363` 逐字写了「同一周有多条调整时相乘、不取最后一条」是工程决定；`uq_..._reason_source` 把 `reason` 放进键里也确实**允许**不同理由并存。**故这不是「代码违反了自己的设计」，而是「没有人对『两条红色规则同周』这个必然会出现的组合做过决定，而现有散文一律把 0.64 当成失效来讲」。**

**→ 控制者错误 #39（本计划最重的一条）**：**Review Focus 第 3 条从头到尾被理解成「同一条规则不得重复触发」，而它要防的数是 `0.64`——`0.64` 只需要「两条规则各触发一次」就能出现。** 控制者在 Task 2 加唯一约束、在 Task 6 要求 `window_key`、在 Task 7 要求 SAVEPOINT，**三道闸门全都在防「重复」，没有一道在防「叠加」**。而 9 个实现者里没有一个顶回这一条 —— 因为**每一道闸门单看都是对的**，缺的是「这两道闸门合起来够不够」的那个视角，而那个视角只有跨 Task 的终审有。
**⚠️ 这正是 Ruling 5 那一句「独立评审者是唯一能抓到『控制者自己规定的东西是错的』的席位」的兑现**：Plan 03 把 9 个逐 Task 评审席折进了控制者亲验，**而唯一保留的这一席抓到了 9 个 Task 全都漏掉的那一条**。
**→ 补硬规矩 #116：一条纪律若是以「某个具体的错误数值不得出现」的形式写下的（如「不得连乘成 0.64」），那么守卫必须直接钉住那个数值的**全部产生路径**，而不只是钉住「其中一条路径被挡住」。判据是：把所有能产生那个数的机制列出来，逐个问「哪一道闸门挡它」；列不全就是没想完。** 依据：#39。

**C1 的裁定**：评审者给了两个处置（A：把 auto 减量收成「一处方一周至多一条」，`reason` 记第一条命中的规则、其余只落 `alert` 行；B：承认「每条红色规则各减 20%」是产品口径，则必须改掉那句文案、在「三道闸门」那一节写明第四种形状是许可的、并加一条守卫钉住 `0.64` 免得下一个人当 bug 修掉）。
**⚠️ 控制者裁定：选 A，但它是一个产品口径问题，必须先问用户再动手** —— 因为它决定的是「一个学生同时触发两条红色预警时，本周训练量减多少」，**这是体育教学口径、不是工程口径**，而 spec §8.4 只写了「减量 20%」没说叠加怎么办。**无论选哪个，`api/routers/alerts.py:327` 那句「减了 20%」今天与库里的数不符，这一半是无条件要改的。**

### 其余 7 条（终审的发现，控制者逐条裁定归属）

**I1（Important，归 Plan 04 开工前必修）**：`weekly_class_report.alert_summary` 在**任何重放日**恒为 9 个 0、`suggestion` 也永远给不出「降量」档。机制：`daily.py:892` 的 `now = dt.datetime.now()` **不可注入** → `alert.triggered_at` 是真实今天；而 `report_stage.py:727-745` 用 `Alert.triggered_at` 夹报表周（历史区间）→ **恒不相交**。**⚠️ 而 `demo_bootstrap.py:229` 的注释写的是「生产上 `as_of == 今天`，故这一档不可达」—— 这句对 `app.pipeline.backfill` 不成立**（`backfill` 是已交付的 CLI，语义逐字就是「把一学期的每个业务日都跑一遍」，每一个业务日都是历史日）。**后果**：spec §8.5 的两项产出在**回放路径上永远为空**，而回放是唯一能得到历史周报的路径；**Plan 04 会用 `demo.ps1` 灌出来的库开发教师大屏，那两个块永远拿不到非零数据，前端很可能被写成「这块没数据就隐藏」**。**处置：让 `run_daily` 的 `now` 可注入（与 `as_of` 同源），一次签名变更；并把那句注释的理由改对**（账本原先把它登记为「演示口径」，**理由写错了**）。

**I2（Important，归 Plan 04 开工前必修）**：演示库上 `checkin_rate_by_layer` **三个层全是 `rate: 0.0`**，且 `measured == students`（**读起来像「测过了、就是 0%」**），连带 `GREEN_MASTERY` 永不触发、`notification` 表 **0 行**、5 条规则里只有 2 条红色在演示库上出现过。机制是**三个各自合理的决定撞在一起**（且与 `--as-of` 无关、是确定性的）：① `DEMO_AS_OF` **必须**是周日（否则 `is_report_day` 为假、一行周报都没有）；② `run_daily` 让 `generated_on = as_of`，于是微周期第 1 周的第 1 个训练日**就是那个周日**，报表窗口里 `<= as_of` 的训练日**只有它一天**；③ `demo_data.py:357` 是 `is_rest_day = log_date.weekday() >= 5`，**周日一律是休息日** → `_counted_checkin_days` 的四个条件把它全部剔掉 → 分子恒 0。**⚠️ 这违反本项目自己那条最响的纪律（「不知道」不得讲成「0」）**：库里明明有 628 条 `completed=True` 的打卡，而大屏显示三层全 0%。**且 `demo_bootstrap.py:238-246` 的 `offenders` 只检查「行数 > 0」，11 条预警就让它通过了、一条警告都不打** —— 演示的人会以为大屏坏了。**处置：`demo_data` 的休息日规则改成「按处方的训练日反推」而不是「按周末」，或让处方生成日早于 `as_of`（先跑一次 `run_daily` 生成处方、再灌打卡、再跑第二次）；并给 `offenders` 加两格（三层全 0 与 `notification == 0` 都应当场报警）。**

**I3（Important，可进 Plan 04 backlog，但那句警告要搬家）**：路由顺序纪律**只有一条点状行为守卫**（`test_feedback.py:1260`），而**写结构守卫的自然办法在 FastAPI 0.141.1 上是假绿** —— 它实测：真 app 上 `len(app.routes) == 6`（带 `.methods` 的只有 5 个），**发出一次真请求之后仍然是 6**；它用「遍历 `app.routes`、找同段数且前段是占位符的 pair」写的通用遮蔽扫描，**在今天正确的顺序下报 0 对、在一个把顺序排反的最小 app 上也报 0 对**。**而顺序确实承重**：同一个最小 app，特例先 include → `GET /api/mini-tests/normalized` = **200**；catalog 先 → **422** `{"type":"int_parsing","loc":["path","mini_test_id"],…}`，**逐字就是 `__init__.py:72-74` 预言的那个「把下一个人支去修前端」的错误消息**。**处置：把「⚠️ 不要用 `app.routes` 写路由顺序守卫，0.141.1 上只数得出 5–6 条、会假绿」这句从两个测试的 docstring 搬进 `app/api/routers/__init__.py` 的纪律住址**（下一个人要写守卫时会先读 `__init__.py`）；结构守卫改用 `_IncludedRouter.original_router.routes`（它实测这条路能拿到真路由），或退一步写清单式守卫（枚举今天 3 个末段为字面量的特例路径，逐个实发一次请求断言不是 422）。

**I4（Important，归 Plan 04 开工前必修，一句话的改动）**：`api/schemas/feedback.py:136` 的 docstring 逐字写着「教师『发起课堂快评』就是 `PATCH {"rpe_opened": true, "rpe_token": "…"}`」，**而 `open-rpe` 才是 Task 5 建出来的正主**（唯一走 `_new_rpe_token()`、强制 CSPRNG 与 `RPE_TOKEN_LEN` 长度不变量的那个）。它实测匿名 `POST /api/class-sessions` → **201 且 `rpe_token` 是它自己挑的串**，随后 `GET` 原样带回。**⚠️ 它正指着 Plan 04 教师端要实现的第一个按钮，而指向的那扇门会绕过 CSPRNG 与长度不变量**（SQLite 不强制 `VARCHAR` 长度，故走 PATCH 写一个超长口令**永远不报错** —— 正是 `_new_rpe_token` docstring 自己点名的失效形态）。**且同一个 docstring 末尾还写着「Task 5 的采集端点是它的正主」，前后两句互相矛盾。** 处置：①改掉那句过期 docstring（**零风险，现在就做**）；②把 `ClassSessionUpdate`/`ClassSessionCreate` 的 `rpe_token` 去掉，或加 `field_validator` 强制 `len(v) == ClassSession.RPE_TOKEN_LEN`。

**M1（Minor，但对 Plan 04 最有用的一条）**：**「2xx 带 schema 82/90」这个数已过期** —— 实测 **83/91**（8 个不带的是 8 个 `204 DELETE`，本来就不该有 body）。**而真正该告诉 Plan 04 的数是：那 83 个里有 24 个的 schema 是 `{"type":"object","additionalProperties":true}`**（23 个泛型 list 端点 + `/api/health`），**即 `openapi-typescript` / `orval` 生成出来是 `Record<string, unknown>`**。这是 `crud.py:544-555` 逐字交代过的取舍（挂 `response_model` 会让 `defer` 掉的大 JSON 列触发 N+1、性能收益归零），**评审者认可这个取舍**，但指出**代价应当写在 Plan 04 的入口**：前端拿不到 list 项的机器可读字段清单，只能照 docstring 那句「list 的键集合 = `schemas.read` 减去 `list_exclude`」手推 23 份。**它给的建议：Plan 04 要么手写这 23 个 `Omit<XRead, …JsonText 列>` 类型，要么给工厂加一个窄化的 `*ListRead`（「那才是既保性能又保契约的解」）。**

**M2（Minor）**：`demo_bootstrap` 的两道禁区守卫**比它们看起来窄** —— `--csv-dir backend/data/seed/sub` **不拦**（且 `:141` 的 `mkdir(parents=True)` 会把它建出来）、`--db-url …/PE.DB` **不拦**（`endswith` 区分大小写而 Windows 文件系统不区分）、`…/pe.db?x=1` **不拦**；`demo.ps1:133` 的 `Get-ChildItem $ForbiddenCsv -File` **没有 `-Recurse`**。**为什么只是 Minor**：`demo.ps1` 是唯一调用方，它的 `$DbUrl` 从 `app.main.DEMO_DB_URL` 单点读出、`$CsvDir` 恒在 `$env:TEMP`，**故今天结构上碰不到，两道守卫是保险带**。处置：`db_url` 用 `make_url(...).database` 解析后 `Path(...).resolve()` 做**大小写无关**比较、`csv_dir` 用 `is_relative_to(...)`、`demo.ps1` 加 `-Recurse`。

**M3（Minor）**：`AlertReport` 六格里只有 `raised` 落库（`daily.py:973` 的 `run.alert_count = alerts.raised`），**`errors` 在库里没有任何痕迹** —— 而加载阶段的同类部分失败会置 `run.status = "partial"` 并为**每一条**被跳过的记录写一行 `cleaning_log`（理由逐字是「silently 丢掉一条记录与『这条记录从来没到过』在库里长得一模一样，而 spec §4.6 要求必须能交代每一条被剔除或修正的数据」）。**故「预警为什么少了一个人」这个问题今天只能靠翻会滚掉的日志回答。** ⚠️ 它 AST/字面核对过那六格全部被 `alert_stage.py:1106-1114` 的 `logger.info` 读到，**所以不是死配置**（`AlertReport` 的 docstring 那句「它进报表、进日志」是真的）。处置：`errors > 0` 时把 `run.status` 降成 `"partial"`，或把计数写进 `error_summary`（**一行改动**）。

### Ruling 22 — 终审对 Ruling 20（匿名写入）的独立判断：**裁定站得住，但我的第 ③ 条理由不成立**

它实测了缺口有多大：**35 个 mutating 操作里 9 个带 `security`、26 个不带**（9 POST + 9 PATCH + 8 DELETE），另有 47 个 GET 不带。零请求头连续 `POST /api/semesters → /api/teachers → /api/course-sections → /api/class-sessions` **全部 201**，最后一行的 `rpe_token` 是**它自己挑的串**，随后 `GET` 原样返回、`DELETE` 也 204。**故「闸门可绕过」是事实。**

**但它判定裁定仍然成立**，两条理由（第 ③ 条被它推翻）：
1. 用户两次裁定「原型系统、无真实鉴权」，而 `X-Student-Id` / `X-Teacher-Staff-No` 本身在 `deps.py:3-7` 就逐字声明了「**挡事故、不挡攻击**」。**既然身份头可以随便伪造，泛型写入侧要求它就不增加任何安全性 —— 它只增加一致性。**
2. **它原本想建议「至少挂一个只声明不判定的 `Security(TEACHER_STAFF_NO_SCHEME)` 让契约统一」，但读完 `test_prescription_api.py:1401-1402` 之后撤回了这个建议** —— 那条测试的第 ③ 拍逐字写着「23 个 CRUD 资源的端点一个都不带 `security`：它们不要求身份，**而 OpenAPI 上多出来的要求会让前端以为每个 CRUD 都要登录**」。**在不加强制的前提下声明 security 是一份反方向的假契约**（Swagger 会强制填一个服务端忽略的头）。**「今天的状态是诚实的，而且是被守卫钉住的诚实，不是遗漏。这一点我认为实现者做对了。」**
3. **⚠️ 我的第 ③ 条理由（「前端本来就要带教师头」）不成立** —— **服务端根本不读它，所以前端不需要带；契约上今天说的是相反的话。** 它要求把这条理由从账本里划掉，**免得 Plan 04 以为「带着头就安全了」**。**控制者采纳并划掉。**

**⚠️ 它同时指出「不能等的那一件事」（不是代码缺陷，是一条派单义务）**：**Plan 04 的第一条任务必须把「9 个可写资源里，教师 UI 能建/改/删哪几个」定下来，并同时决定要不要加强制。** 理由是这 26 个匿名 mutating 操作是**一份前端会编码进去的契约**（生成的 TS 客户端不带任何身份参数），而改它要同时动三处：`build_crud_router`、`test_prescription_api.py:1488-1495` 那条全仓级断言、以及每个资源在 `catalog.RESOURCES` 里的 `scope` 钩子（**今天 23 行全为 `None`**，`crud.py:109-116` 已说明它只挂在 detail 三端点、**表达不了 list 的过滤与 create 的「行还不存在」**）。**「先写前端再改这份契约，就要重写前端的每一个写请求。」**

### 终审的总体结论（逐字）

> **这个分支已经合并（fast-forward 进 `main`），而它配得上这次合并。** 账本里每一个可复核的数字我都独立复现了，一个不差；`app/domain` 的 100% 分支覆盖经 9 个定点变异验证是真覆盖；泛型 CRUD 工厂的配置矩阵、`JsonText` 自动探测、`_child_tables` 的 `SET NULL` 排除、`pk_alias` 的笨推导 + 一个显式覆盖，全部与散文逐字相符；两个禁区在真机跑完一整条演示链路之后仍然干净。文档密度与「硬规矩 #39：写下能力就写明守不住什么」的执行程度，是我见过的原型代码里最高的一档 —— 我上面 8 条发现里有 5 条（I1 的一半、I3 的一半、M1、M2、M3）是**代码自己已经如实声明过代价**的，我只是把声明里的数或理由纠正到与运行时一致。
> **未发现任何 Critical 级的「守卫假绿」或「数据不可追溯」问题。**

**它给的「必须在 Plan 04 开工前处理」清单（按不能等的程度排序）**：**C1**（它今天就在官方演示库里，Plan 04 的学生端「本周训练单」与教师端处置流程会直接照这个数写 UI 与文案，而那句「减了 20%」是一句关于学生的假话 —— **先决定 A 还是 B，再让前端照着写**）→ **I2**（Plan 04 的**全部**教师大屏与学生消息中心都要照这个库开发；不修，前端会把「有数据但显示 0」当成「本来就没数据」，并且无从自测勋章/补练提醒两条流程）→ **I1**（同一批前端页面里的另两块在任何回放日结构性为空，而代码注释把原因误诊成「演示口径、生产不可达」；**修法是一次 `run_daily` 的签名变更，越晚做越贵**）→ **I4**（一句话的改动，但它正指着 Plan 04 教师端要实现的第一个按钮）。**I3 与 M1–M3 可以进 Plan 04 的 backlog。**

### Plan 03 的最终账面

**9 个 Task、54 个 commit、`807 → 1244 passed`（+437）、`app/domain/` 覆盖率从 `996/0/288/0/100%` 到 `1268/0/376/0/100%`、HTTP 端点从 0 到 63 个路径 / 91 个操作、表从 18 到 25、黄金用例从 13 到 14、五个指纹逐字不变、两个禁区全程干净。**
**顶回累计 73 次、73 次都对**；**控制者错误累计 39 条**；**硬规矩从 #94 增到 #116**；**Ruling 1–22**。
**⚠️ 而终审（唯一保留的独立评审席）抓到了 9 个 Task 全都漏掉的那一条 Critical** —— 这是 Ruling 5 那个裁定的代价与回报的完整形状：**折进控制者亲验的 9 个席位没有漏掉任何一条实现层的缺陷，但漏掉了那条需要跨 Task 视角的。**

**下一步**：① 问用户 C1 选 A 还是 B（**这是体育教学口径、不是工程口径**）；② 修 C1 的那句文案 + I1 + I2 + I4（Plan 04 开工前必修的四条）；③ 写 Plan 04（Vue3 前端），**第一条任务就是 Ruling 22 那个「不能等」的决定**。
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
SENT = "Plan 03 全分支终审（Ruling 5 保留的那一席独立评审者）"
assert SENT not in t, f"{SENT!r} 已存在"
LEDGER.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)}")
for k in ("Ruling 21", "Ruling 22", "硬规矩 #116", "控制者错误 #39", "0.6400000000000001", "9/9 killed"):
    print(f"  {k}: {c.count(k)}")

print("\n[git] 提交")
subprocess.run(["git", "add", ".superpowers/sdd/2026-10-08-实施计划03-反馈预警与CRUD-API层/"],
               cwd=str(ROOT), check=True)
r = subprocess.run(["git", "commit", "-m",
                    "docs(sdd): Plan03 全分支终审 —— 基线全部复现、9/9 变异 killed；查出 1 Critical（两条红色规则同周把减量连乘成 0.64）"
                    "+ 4 Important + 3 Minor；Ruling 21/22 + 硬规矩 #116 + 控制者错误 #39"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
out = (r.stdout or r.stderr).strip().splitlines()
print("  " + (out[1] if len(out) > 1 else out[0] if out else "(无输出)"))
print(f"  HEAD = {git('log', '--oneline', '-1')}")
print(f"  git status -> {git('status', '--short') or '（干净）'}")

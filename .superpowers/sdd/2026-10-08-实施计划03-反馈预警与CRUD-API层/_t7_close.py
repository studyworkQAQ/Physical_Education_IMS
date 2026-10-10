"""Plan 03 Task 7 结案：账本追加 Ruling 17（顶回 5 处全采纳）+ 控制者错误 #30-#32 + 硬规矩 #112，然后 commit。"""
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LEDGER = HERE / "progress.md"
b = LEDGER.read_bytes()
t = b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"[ledger before] bytes={len(b)} lines={t.count(nl)}")

BODY = """

---

## ✅ Task 7: complete (commits 6d0c8d2..5fe289c, 0 fix round)

**交付（5 个 commit，派单建议 3–4 个）**：`7228868`（`app/notify.py`：`NotificationChannel` Protocol + `InAppChannel` + 两个未来通道骨架，**值域与模型类常量对账、import 期响亮失败** + 14 条测试）、`6dc46a7`（**前置重构**：`_training_days_of` 从 `app/api/routers/feedback.py` 搬到 `app/pipeline/prescription_stage.py::training_days_of` —— 守卫禁止 `pipeline` import `app.api`；**零行为变更**）、`480a36e`（`app/pipeline/alert_stage.py`：组装 Signals → 调 domain → 落 alert → 发消息 → 写 `weekly_adjustment` 的 `auto` 来源 + 33 条测试 + **3 条变异自证**）、`196a00e`（Alert 阶段接进 `daily.py`：阶段序列 6→7、`run.alert_count`、`_replay_cleanup` 5→6 张 + `POST /api/alerts/{alert_id}/handle` + 24 条测试）、`5fe289c`（报告 + 7 个探针 + 清掉自查出的 2 个死 import）。
**多出的那个 commit 是 `training_days_of` 的搬家**（改的是 Task 5 的文件、零行为变更，**混进 ② 会让评审看不清哪一半是重构**）—— 控制者追认这个切分。

**验收（控制者本机亲跑复核，探针 `_t7_verify.py` 已入库）**：
- 全量 **1026 → 1097 passed**（+71 = notify 14 + alert_stage 36 + alerts_api 21），**零回归**
- `app/domain/` 四格 **1147 / Miss 0 / 336 / BrPart 0 / 100% 逐字未变** ✓（带 `--cov` 时 `1096 passed, 1 skipped`）
- **扫描面 52 → 54**（pipeline 8→9、db 11、domain 17、api 16→17）；**`/api/` 路径模板 56 → 57、操作数 84 → 85**（新增 `POST /api/alerts/{alert_id}/handle`，控制者从 `openapi()` 实读）；表数 **25**；`_MODELS_PUBLIC_BASELINE` **33**
- **`_replay_cleanup` 的清单控制者用 AST 口径亲验**（不用文本计数，#103/#107）：`['models.DerivedMetrics', 'models.StratificationResult', 'models.PercentileSnapshot', 'WeeklyAdjustment', 'Prescription', 'Alert']` = **6 张** ✅；**`ClassSession` 确实不在里面** ✅；**`WeeklyAdjustment`(#3) 在 `Prescription`(#4) 之前**（子表先删，Plan 02 的 P7-A4）✅
- **`AlertReport` 6 字段**（简报的 4 个 + `skipped`（P7-A3 第 1 条要求的）+ `errors`）；`AUTO_REDUCTION_FACTOR = 0.8`；`AUTO_SOURCE = 'auto'`
- **三个新模块的公开面**：`alert_stage` **9** 个、`notify` **8** 个、`api/routers/alerts` **5** 个；`refdata_alerts` 实测 **3** 个（`ALERT_RULES_FILENAME` / `alert_rules` / `load_alert_rules`）
- **`training_days_of` 只有一份定义**（控制者用 AST 数定义份数 = **1**，#89 再扩写）✅
- **禁区**：**四个指纹逐字不变**（三个既有 + Task 6 新增的 `alert_rules.yaml` = `E48E3AC82BB45BB7`，CRLF 均 0）；`git diff 6d0c8d2 HEAD -- backend/data` **为空**；`pe.db` 不存在；`data/seed/` 0 文件；架构守卫全绿

### Ruling 17 — 实现者顶回 5 处，**全部采纳**（Plan 03 的第 34–38 次；累计 **63 次，63 次都对**）

**顶回 3（Critical，采纳 → 控制者错误 #30）：RPE 的排序键应是「课次时间」`(session_date, period)`，不是派单写的 `submitted_at`。⚠️ 按派单的方子反而会引入它要防的那个失效。**
失效序列（实现者给的，控制者复核成立）：`submit_rpe` **刻意不做过期**（它 docstring 的「刻意不做」第 2 条），故**一节早先的课完全可以在一节晚近的课之后才被提交**。那时按 `submitted_at` 排会把 `S0` 插进 `[S1,S2,S3]` 的**前面** → `window_key` 的锚点从 `S3` 移到 `S2` → **键变** → 同一次「连续 ≥ 9」**第二次落库** → 减量系数连乘回来（正是 Review Focus 第 3 条要防的 `0.8³ = 0.512`）。
落地：`.order_by(ClassSession.session_date, ClassSession.period, RpeRecord.submitted_at, RpeRecord.id)` —— **`submitted_at` 与 `id` 只作同节课内的 tie-breaker**。**变异 M2 取证：只有该抓它的那一条红（1 failed / 32 passed）。**
**⚠️ 这一条的性质**：控制者从 Task 6 的关切里逐字抄了「`rpe_session_ids` 必须按时间升序」，**并自作主张指定了「按 `submitted_at` 排序」** —— 而「时间」在这个语境里有两个候选（课次时间 vs 提交时刻），**控制者选了错的那个，且它不是「不够好」而是「会引入失效」**。
**→ 补硬规矩 #112：传导一条纪律时，只传「要满足什么性质」（如「按时间升序」），不要替实现者指定「用哪一列」——除非控制者已经核实那一列在该语境里就是那个性质的唯一载体。** 依据：#30。**⚠️ 这与硬规矩 #98 是一对**：#98 说「要求 X 时必须给出怎么做到 X 的机制」，#112 说「给出机制时不要给错的那一个；给不出正确的就只给性质」。**两条合起来是：机制要么给对，要么不给。**

**顶回 4（Important，采纳）：`reason` 不带 YAML 版本号**（与 `app/domain/alerts.py` 模块 docstring 那一句相反）。理由是一条具体的失效：**`reason` 是那条四列唯一约束的一列**，把版本号拼进去（`"RED_RPE_SUSTAINED@v1.0"`）会让「专家升一次 YAML 版本号」**等价于「同一周可以再减一次量」** → `0.8 × 0.8 = 0.64`，**而 Review Focus 第 3 条要防的连乘从版本号那一侧回来了**。约束自己的注释也逐字警告过「`reason` 是自由文本，改一个标点就绕过了本约束」。
落地：**版本号改落 `alert.trigger_snapshot["alert_rules_version"]`** —— 预警行与调整行是**同一次触发**的两半（同一条规则、同一周、同一个学生），故「当时按哪一版阈值判的」仍可离线复核，**可追溯性无损**。
**⚠️ 连带**：`app/domain/alerts.py` 的模块 docstring 那一句现在是错的 → **归 Task 9 的勘误**。

**顶回 1（Important，采纳 → 控制者错误 #31）：`_replay_cleanup` 的元组在 HEAD 上已经是 5 项、不是 3 项。** 派单的 P7-A2 把 **Plan 02 Task 7 早做完的扩表**当成本 Task 的活，并引了 `daily.py:755` 那条注释作证据 —— **而那条注释自己就是过期的**（它说「Task 7 把 `_replay_cleanup` 扩到五张之后就过期了」，而那次扩表在 Plan 02 就发生了）。**⚠️ 这是硬规矩 #111 的第 2 次违反**（「派单里每一个既有常量的当前值都要在当前 HEAD 上实测」）—— 控制者实测了它**存在**，但没实测它**当前的长度**，而是照注释里的数字推理。

**顶回 2（Important，采纳 → 控制者错误 #32）：扫描面 52 → 54，不是派单预测的 53。** 派单漏算了 `app/api/routers/alerts.py` —— **而那是派单自己在第 4 节逐字要求本 Task 创建的**（S1 的裁定），且 `api` 在 `SCANNED_DIRS` 里。**⚠️ 同一份派单的两节互相矛盾，控制者没有在写完后回读一遍。**

**顶回 5（Minor，采纳）：`checkin_gap_end` 锚在「凑满 `gap_days` 那一天」，不是 domain docstring 字面的「中断的**结束日**」。** 按字面读法**键会天天变**，一个 5 天的中断会落 **4 条 alert** —— **Review Focus 第 3 条从打卡侧回来了**（与顶回 4 是同一条纪律在另一条规则上的应用）。

### 3 处偏离派单字面：全部追认

① `evaluate_alerts` 多了 3 个 keyword-only 形参（`exercises` / `now` / `channel`）—— **简报那个签名跑不起来**（`triggered_at` 与 `created_at` 都是 NOT NULL 无缺省，`training_days_of` 要动作库）；② `AlertReport` 是 6 字段不是 4（`skipped` 是派单 P7-A3 第 1 条**要求**的；`errors` 是异常分层的可观测量）；③ skip 留痕的日志落在 `alert_stage` 而**不是** `run_daily`（照 `generate_prescriptions` 的既有先例：阶段自己印自己的计数；`main()` 的 CLI 另补了一行「预警：本日新触发 N 条」）。

### ⚠️ 实现者报的三件事，控制者逐条裁定

**① 撞红的既有守卫只有 1 条，且不是派单预测的那一条。** 派单预测 `tests/api/test_crud.py` 的路由数断言会红；**实际红的是 `tests/api/test_prescription_api.py::test_the_identity_headers_are_registered_as_openapi_security_schemes` 的第 ③ 拍**（「除特例清单外 `/api/` 下不带 security」）。**那条守卫的 docstring 逐字写着「Task 7/8/9 每加一个带身份的特例端点都要回来加一行——这是有意的」**，故按其设计登记（11 → 12 项）。`test_crud.py` 一条都没红。**⚠️ 这又是一次「控制者预测的红点不是真的红点」**（与 Plan 02 的 #138 同族：控制者凭记忆点名一个位置，而真的在另一处）。

**② 求值人群这个决定是性能实测驱动的，代价如实记录。** 人群 = **本学期在三源里留过痕的学生**。理由：`GREEN_MASTERY` 与 `YELLOW_CHECKIN_GAP` 都要 `training_days_of`（= 装配训练包），**全员求值会让 `test_backfill`（500 人 × 112 天）多跑约 56 000 次装配**，而那条 `elapsed < 90` 在 Task 5 结案时全量跑实测已到 **47.33 / 47.96 s（余量仅 1.88×，低于硬规矩 #42 的 2× 线）**。**本 Task 实测 `elapsed = 31.63 s`**（单跑，取证照账本 Ruling 12，跑完按字节还原并复核），Alert 阶段约 **+2 s**。
**控制者裁定：采纳这个人群口径**，并**如实记录代价**：**一个本学期从没在任何一源留过痕的学生不会被求值** —— 而这类学生恰恰可能是最该被关注的（长期缺席）。**但 `YELLOW_CHECKIN_GAP` 的语义是「连续 N 个应打卡训练日未打卡」，一个从没留痕的学生没有「应打卡训练日」的基线可算**（分母来自他本周的训练单），故**这不是本 Task 的取舍失误，而是这条规则的定义边界**。**→ 记进 Task 9 的 spec 勘误：`YELLOW_CHECKIN_GAP` 只对「本周有训练单」的学生可判。**

**③ 实现者自己发现了一格派单没点出来的东西（控制者认为这是本轮最有价值的一处）**：打卡那一源用了**两个不同的窗口** —— 喂**信号**的按三周回看，喂**人群**的只按 `semester.start_date`。**用同一个窗口会漏掉最该被提醒的人**：连续失联四周的学生在三周窗口里**一行都没有** → 不在人群里 → `YELLOW_CHECKIN_GAP` 对他**永远不触发**，而那正是这条规则存在的理由。
**⚠️ 这一条的形状值得记**：它不是「派单错了」也不是「守卫不够」，而是**「两个看起来该用同一个参数的地方，其实需要不同的参数」** —— 与 Plan 02 的控制者错误 #5（「枚举分桶的 6 个结果」被当成「分层判定的 3 个结果」）同族，但方向相反：**那次是把两个东西当成一个，这次是发现了两个东西不能当成一个。**
**→ 补硬规矩 #113：一个查询窗口/阈值/人群口径被两处使用时，先问「这两处要回答的是同一个问题吗」；若不是，它们需要两个参数，而共用一个会静默地让其中一处失效。** 依据：本条；Plan 02 的 #5。

### 待清扫：**4 条**（全无 Critical）

`repo.py::delete_by_batch` 的两处过期计数（「清的是九张里的五张」、「Alert 由 Task 8 接进」——**Alert 本 Task 已接进**）｜`models/feedback.py` 模块 docstring 与 `Alert.batch_id`/`Notification.alert_id` 列注释里的「Task 8」｜`prescription_stage.py` 的「`auto` 也留给 Plan 03」与「生产写入方今天仍为零」（**本 Task 已落地**）｜`api/routers/feedback.py` 的 **4 个死 import**（用 `git show 6d0c8d2` 复核过，**基线上就有**，不是本 Task 造成的）。
**⚠️ 前三条都是「散文说某个活留给后面的 Task，而那个活已经做完了」** —— 与硬规矩 #97 同族（一个改动会让别处的事实过期）。**归 Task 9 的勘误一并清。**

### ⚠️ 按硬规矩 #86 回扫 Task 8/9 与 Plan 04

1. **Task 8**：`_replay_cleanup` 现在是 **6 张**，本 Task 加的是 `Alert`；**Task 8 要加 `WeeklyClassReport`（→ 7 张）**，且**子表先删的纪律仍适用**（`WeeklyClassReport` 没有子表指向它，故排在哪都行，但**要有一条测试钉住清单的长度与成员**，否则下一个人加表时会静默改变重放语义）。**⚠️ `notification` 不进清单**（它不带 `batch_id`），它的 `alert_id` 带 `ondelete="SET NULL"`，故删 `alert` 不会让通知行炸 FK。
2. **Task 8**：`api/routers/alerts.py` **已由本 Task 创建**（S1 的裁定兑现），Task 8 只 **Modify** 它（若要加端点）。**⚠️ 特例路由必须在 `catalog` 之前 include**（Task 5 顶回 5 立的规矩）。
3. **Task 8**：`training_days_of` 现在住在 **`app/pipeline/prescription_stage.py`**（不再是 `app/api/routers/feedback.py` 的私有函数）→ Task 8 的班级周报若要算训练日，**从这里 import，不要另写一份**（AST 守卫 `test_training_days_of_has_exactly_one_definition` 会抓）。
4. **Task 9 的勘误清单新增 4 条**：① `app/domain/alerts.py` 模块 docstring 里「`version` …… Task 7 把它写进 `weekly_adjustment` 的 `auto` 来源留痕」那一句**是错的**（顶回 4）；② `YELLOW_CHECKIN_GAP` **只对「本周有训练单」的学生可判**（裁定 ②）；③ 上面那 3 条「散文说留给后面的 Task 而活已做完」；④ **`subject_key` 的宽度口径**：Task 6 的报告写「`course_section:2147483647` 是 27 字符、超宽 3」，控制者实测是 **25 字符、超宽 1**（结论一致：前缀必须是 `section`）。
5. **Plan 04**：`POST /api/alerts/{alert_id}/handle` 的三个动作值是 **`ACTION_REDUCE` / `ACTION_IGNORE` / `ACTION_NOTE`**（在 `app/api/routers/alerts.py`），前端要从 `/openapi.json` 读、不要抄字符串。

**下一步**：抽 `task-8-brief.md` → 派实现者（班级周报 + 大屏/首页聚合 + 教师端训练单变体）。
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
SENT = "Task 7: complete (commits 6d0c8d2..5fe289c"
assert SENT not in t, f"{SENT!r} 已存在"
LEDGER.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)}")
for k in ("Ruling 17", "硬规矩 #112", "硬规矩 #113", "控制者错误 #30", "控制者错误 #32", "1097 passed", "63 次"):
    print(f"  {k}: {c.count(k)}")

print("\n[git] 提交")
subprocess.run(["git", "add", ".superpowers/sdd/2026-10-08-实施计划03-反馈预警与CRUD-API层/"],
               cwd=str(ROOT), check=True)
r = subprocess.run(["git", "commit", "-m",
                    "docs(sdd): Plan03 Task 7 结案 —— 1097 passed，57 个端点，auto 来源已落地，"
                    "Ruling 17 + 硬规矩 #112/#113 + 控制者错误 #30-#32（顶回 5 处全采纳，累计 63/63）"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
out = (r.stdout or r.stderr).strip().splitlines()
print("  " + (out[1] if len(out) > 1 else out[0] if out else "(无输出)"))
r = subprocess.run(["git", "log", "--oneline", "-1"], cwd=str(ROOT), capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print(f"  HEAD = {(r.stdout or '').strip()}")
r = subprocess.run(["git", "status", "--short"], cwd=str(ROOT), capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print(f"  git status -> {(r.stdout or '').strip() or '（干净）'}")

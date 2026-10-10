"""Plan 03 Task 6 结案：账本追加 Ruling 16（顶回 8 处全采纳）+ 控制者错误 #26-#29 + 硬规矩 #111，然后 commit。"""
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

## ✅ Task 6: complete (commits a8d61b4..caf80c5, 0 fix round)

**交付**：`834fa34`（抽 `app/refdata_yaml.py`：6 个通用助手 + **必填 keyword-only `doc_kind`**，`refdata_prescription.py` 改成 5 个薄适配器 + 1 个别名，闸 A 5 条守卫；**956 → 961**）、`f08e9ce`（`data/alert_rules.yaml` + `app/domain/alerts.py` + `app/refdata_alerts.py` + 65 条测试；**961 → 1026**）、`caf80c5`（变异取证 5 条 × 三重还原 + 报告 + 行尾归一）。

**验收（控制者本机亲跑复核，探针 `t6_probes/_verify.py` 已入库）**：
- 全量 **956 → 1026 passed**（+70 = domain 35 + 加载器 35）；带 `--cov` **1025 passed, 1 skipped**
- **`app/domain/` 四格 996/0/288/0 → `1147 stmts / Miss 0 / 336 branch / BrPart 0 / 100%`** —— **stmts 与 branch 都涨了，而 `Miss` 与 `BrPart` 仍是 0、覆盖率仍是 100%**（spec §12 的硬要求兑现）。`app/domain/alerts.py` 自己 **151 / 0 / 48 / 0 / 100%**
- **扫描面 51 → 52**（pipeline 8 + db 11 + domain **17** + api 16）—— **只涨 domain 一格，与 P6-A3 的预测逐字相符**；`refdata_yaml.py` / `refdata_alerts.py` 都**不在** `SCANNED_DIRS`，故扫描面不因它们而涨 ✓
- 表数 **25**（未建表）；`_MODELS_PUBLIC_BASELINE` **33**（`models.__all__` 仍 14）；openapi paths 仍 **56**（operations 84）
- **P6-A1 + 顶回 3/4/5 全部落地亲验**：`StudentSignals` **11 字段** = `student_id / semester_id / week / rpe_streak / rpe_session_ids / mini_test_scores / mini_test_ids / checkin_gap_days / checkin_gap_end / completion_rate / mini_test_improved`（**顶回 4 的 `checkin_gap_end` 与顶回 5 的 `semester_id`/`week` 都在**）；`ClassSignals` **5 字段** = `course_section_id / semester_id / week / mean_rpe / student_count`；**`StudentHit` 与 `ClassHit` 都是 5 字段 = `rule_id / level / subject_key / window_key / snapshot`**（顶回 3 的 `subject_key` 在两个 Hit 上）
- `alerts.py` 的 `__all__` = **16** 个名字；`_ALERTS_PUBLIC_BASELINE` **`assert len(...) == 19`**（`app.domain.alerts` 16 + `app.refdata_alerts` 3）；`refdata_alerts.py` 照 P6-A5 **不写 `__all__`** ✓
- **P6-A2 落地亲验**：`app/refdata_yaml.py` 的 6 个函数 = `line_index` / `fail` / `exact_keys` / `as_int` / `as_float` / `as_optional_text`，**其中 5 个都有必填 keyword-only `doc_kind`**（`line_index` 没有，因为它只吃 `text`、报错时不涉及文档种类——**正确**）；`refdata_prescription.py` 只改了 3 处（docstring + 一行 import + 141 行的 6 个定义换成 49 行适配器块，diff **+49 / −126**），**57 处调用点一个字没动**（AST 实测），报错文本逐字不变
- **顶回 6 落地亲验**：`alerts.py:545` 是 `sig.completion_rate >= float(rule.params["completion_rate_min"])`，而 `:523` 的注释逐字写着「YAML 的参数名逐字是 `completion_rate_min`——一个叫 `_min` 的阈值被 `==` 消费自相矛盾」
- **`alert_rules.yaml` 亲验**：**6 037 B / CRLF 0 / sha256[:16] = `E48E3AC82BB45BB7`**；`version` 那一行原始文本逐字是 `version: "1.0"`（**带引号**，P6-A5 的要求兑现）
- **禁区**：三个既有指纹逐字不变；**`git diff a8d61b4 HEAD --name-status -- backend/data` 只有一行 `A backend/data/alert_rules.yaml`**（控制者用 `--name-status` 逐行比对，不是看它是否为空）；`pe.db` 不存在；`data/seed/` 0 文件
- **变异取证 5/5**（本 Task 的硬要求）：M1–M5 分别让 **3 / 9 / 6 / 2 / 5** 条测试红，**每条都靶命中且邻居保持绿**（M1 只让「坐在恰好 5%」那一格红，5.1% 与「更早的下降不算」两条仍绿；M4 最干净，只红 2 条，`mean_rpe=None` 与 `10.0` 仍绿）。**三重还原全部通过**：sha256 复原 `BF36B469F0FC19C9`（5/5）、`git diff` 该文件输出长度 **0**、复跑 `70 passed`；改完删了 `backend/app` + `backend/tests` 全部 `__pycache__`（硬规矩 #83），还原用 python 从 TEMP `write_bytes`（**不用 `git checkout`**）。收尾全量复跑 **1026 passed**

### Ruling 16 — 实现者顶回 8 处（3 条 Critical），**全部采纳**（Plan 03 的第 26–33 次；累计 **58 次，58 次都对**）

**顶回 1（Critical，采纳 → 控制者错误 #26）**：**P6-A2 漏了 `_fail` 的硬编码前缀。** 实测 `refdata_prescription.py` 的 `_fail` 末行逐字是 `f"处方模板 {path} {where}：{message}"` —— **原样共用会让 `alert_rules.yaml` 的报错说「处方模板 …/alert_rules.yaml 第 3 行」**，而 Review Focus 第 5 条要的正是「指出是哪个文件」，**那句话当场变成谎话**。实现者的处置：给 5 个助手各加一个**必填 keyword-only `doc_kind`（无缺省值）**。
**⚠️ 控制者的 P6-A2 说「把那 6 个搬进去、两处都从它 import」，却没有读那 6 个函数的函数体** —— 只读了签名。**这与 Plan 02 的控制者错误 #137 同型**（「派单说 `percentile.py` 里有一处先例是『触私有名』，而恰恰相反，那个文件明写『不 import 私有名』」）：**都是「引用一个既有实现的做法，却没读它的实现」。**

**顶回 2（采纳 → 控制者错误 #27）**：**`_PRESCRIPTION_PUBLIC_BASELINE` 实测是 51，不是派单说的 24。** 控制者亲验坐实：`assert len(...) == 51` 且 `app.domain.prescription.__all__` 实测 **51** 个。**而且它钉的是 `app.domain.prescription.__all__`（`_OWNED_MODULES` 九个模块 + `Layer`），与 `refdata_prescription.py` 的公开面无关** —— 后者 8 个公有函数今天没有任何基线钉它。**结论（「不动」）采纳，理由换掉。**
**⚠️ 这是「复用历史数字」的第 6 次**（Plan 02 的 #126 / #144 / #156、Plan 03 的 #7 / #8，本次 #27）—— **24 是 Plan 02 Task 4 结案时的值，之后 Plan 02 的 Task 5/6/7/8 各加过名字，而控制者在 Plan 03 Task 6 的派单里把它当成现值抄了进去。**
**→ 补硬规矩 #111：派单里出现的每一个「既有常量/基线的当前值」，必须在**当前 HEAD** 上实测一次；凡是能从更早的账本、报告或自己的记忆里读出来的数，一律视为过期。** 依据：#27；与 #89（运行时口径）配套 —— #89 管「怎么数」，#111 管「什么时候必须重数」。

**顶回 3（Critical，采纳）**：**`subject_key` 缺失。** 实测 `app/db/models/feedback.py`、`app/api/schemas/alerts.py`、`tests/db/test_models.py` **三处已落地代码**逐字把它的算式钉为「唯一所有者是 `app.domain.alerts`」，而它是 `uq_alert_rule_subject_semester_window` 的一列（控制者亲验：4 列 = `rule_id / subject_key / semester_id / window_key`）；**而计划的 Interfaces 只给了 `window_key`**。⚠️ **附带发现**：`subject_key` 是 `String(24)`，故前缀必须是 `section` 而不是 `course_section`（控制者亲验：`section:2147483647` = **18** 字符 ≤ 24 ✅；`course_section:2147483647` = **25** 字符 → **超宽 1**）。
**⚠️ 实现者报告里写的是「27 字符、超宽 3」，控制者实测是 25 / 超宽 1** —— **结论一致（前缀必须是 `section`），但它的两个数都错了 2**。这是纯散文精度问题（代码是对的），**归 Task 9 的勘误清扫，不返工**（Ruling 1 的口径）。**→ 控制者错误 #28 的反面：这是实现者的第 1 次散文数字错**（Plan 02 的实现者 3 次错误全部自纠，本次是第 4 次，且**没有被它自己抓到**）。

**顶回 4（Critical，采纳）**：**`checkin_gap_end` 缺失** —— `YELLOW_CHECKIN_GAP` 的 `window_key` 逐字要「中断结束日的 ISO 串」，而 `StudentSignals` 一个日期字段都没有；**P6-A4 只给了处置倾向（「控制者倾向把日期字段换成调用方已算好的 `str`」）却没把字段加进清单**。

**顶回 5（Critical，采纳）**：**`StudentSignals.semester_id` / `week` 缺失** —— `GREEN_MASTERY` 是 **student** 作用域（**计划自己给的 YAML 逐字 `scope: student`**）而它的 `window_key` 是 `semester_id:week`；**P6-A1 只给 `ClassSignals` 补了这两个**。

**⚠️ 顶回 3/4/5 是同一条纪律（硬规矩 #110）的三次应用**：把 P6-A1 自己的判据（「定义输出结构时逐字段回问这个值从哪个入参来」）在**两个去重键**上逐字段跑一遍，缺的 4 个字段就自己浮出来了。**控制者立了 #110、并在 P6-A1 里用了一次，但没有把它系统地跑完** → **这与控制者错误 #24 的形状相同（刚立完规矩就违反）**，是 Plan 03 的第 3 次（前两次：#107 立完十分钟就犯、#24）。
**→ 硬规矩 #110 扩写：立完一条新规矩的当轮，必须把它**系统地**跑一遍当前 Task 的全部相关对象（不是一个例子），并把「跑了几个、各查出什么」写进账本。只在一个例子上用过，等于没立。**

**顶回 6（采纳，且它是本轮最有价值的一处）**：**`GREEN_MASTERY` 用 `>=` 而不是计划正文的 `==`。** 三条理由全部成立：① **参数名逐字是 `completion_rate_min`，一个叫 `_min` 的阈值被 `==` 消费自相矛盾**；② `completion_rate ∈ [0,1]`，故 `>= 1.0` 与 `== 1.0` **对任何合法输入逐格等价**，spec 的「100%」没被放宽；③ **写成 `==` 会让本 Task 唯一要求的变异对第 5 条规则没有靶子**（`==`→`>=` 在 `[0,1]` 上不可分辨）。**M5 实跑红 5 条就是这条顶回的证据。**
**⚠️ 这一条的形状值得记**：控制者写的判据**语义上没错**（`==1.0` 与 `>=1.0` 在定义域内等价），**但它会让守卫失去牙齿** —— 而「守卫有没有牙」正是硬规矩 #92 管的事。**故 #92 的完整形态是：不仅「要求一条测试变红前先论证破坏在结构上可达」，还包括「写判据时优先选那个能被变异区分的形状」。**

**顶回 7（采纳）**：**「留痕」没有出口。** 计划要 `insufficient_points` 进 `snapshot`，但**不触发就没有 Hit、也就没有 snapshot**；而 `points_needed` 是 YAML 参数，故「够不够点」必须在 domain（否则 Task 7 要再读一次那个阈值 = **第二个所有者**）。实现者的处置：**每个求值器返回 `(命中, 留痕)` 一对**，新增 `student_skip_traces` / `class_skip_traces` 取后半 —— **「什么时候判不了」在代码里只有一处**。

**顶回 8（采纳）**：**P6-A2 的「两处都从它 import」落地成「各留 5 个一句转发的薄适配器 + 1 个别名」**，而不是改 57 处调用点。理由成立：**57 处逐点加关键字参数 = 57 次改坏一条被测试逐字钉住的报错文本的机会**。**逻辑仍只有一份**，单一所有者由 **AST 机器守**（定义点唯一 + 函数体恰好一句且在调谁 + `is` 身份比对）。

### 7 处偏离派单字面：全部追认

① `refdata_prescription.py` 的改法（= 顶回 8 的落地形状，**删的是实现层不是绑定层**）；② `alert_rules.yaml` 在逐字数据之外加了 33 行注释（**数据部分逐字不变**，由 `_SPEC_PARAMS`/`_SPEC_LEVELS`/`_SPEC_SCOPES` 三个字面量对账）；③ `tests/test_refdata_alerts.py` 的闸 A 6 条不在派单的 Create 语义里（**它是 P6-A2 的唯一机器守卫，没有别的自然住址**）；④ 加载器多做了 **4 类计划没要求的校验**（YAML `scope` 与 `declared_scope()` 对账、比率/计数取值范围、`points_needed == consecutive + 1`、计数必须是 `int` 而非 `float` —— **四类的共同点是失效静默**）；⑤ 变异跑两个测试文件（70 条）而非全量，收尾另跑两次全量确认；⑥ 5 个新 `.py` 的工作树行尾 LF→CRLF（**`git hash-object` 双向取证 blob 逐字不变、`git diff --cached` 为空**；`alert_rules.yaml` 刻意不在名单里）；⑦ `AlertLevel` ↔ `Alert.LEVELS` 那条断言住在 `tests/domain/test_alerts.py`（派单没指定住处）。

### 待清扫：**5 条**（纯散文精度，无 Critical）

① `refdata_prescription.py` 的 `equivalence()` docstring 说「本模块公有函数是 **5** 个」，AST 实测 **8** 个（**Plan 02 Task 3 留下的**）；② `tests/domain/test_prescription_templates.py` 说行号索引的实现在 `app.refdata_prescription._line_index`，**那个实现今天住在 `app/refdata_yaml.py`**；③ `refdata_prescription.py` 模块 docstring「两段的报错口径刻意不同」那段没指向 `app/refdata_yaml`；④ `refdata_alerts.py` 的 `_as_optional_text` 适配器今天没有调用者（docstring 已写明保留理由）；⑤ **阈值个数口径：派单与计划都说「8 个」，运行时实测 9 个**（逐条 3/2/1/1/2），**代码与测试一律用 9** → **控制者错误 #29**（又一次自己数错，与 #7/#8/#27 同族）。

### ⚠️ 控制者错误 #29 与本轮自查出的第 4 次路径深度错

**#29**：派单与计划都说预警阈值是「8 个」，实测 **9** 个（`RED_MINITEST_DROP` 3 个 / `RED_RPE_SUSTAINED` 2 / `YELLOW_CHECKIN_GAP` 1 / `YELLOW_CLASS_RPE_HIGH` 1 / `GREEN_MASTERY` 2）。**根因与 #7 相同：数的时候把「规则数 × 平均参数数」估了一下，没有逐条数。**

**⚠️ 第 4 次路径深度错**：本轮的亲验探针 `_verify.py` 又写了 `ROOT = HERE.parents[2]`（应为 `parents[3]`，因为它在 `t6_probes/` 下、比 `_t6_preflight_patch.py` 深一层），**当场让 `assert BACKEND.is_dir()` 红**（报出 `…\\.superpowers\\backend`）。前三次：`t3_probes/_verify.py`、`t4_probes/_preflight.py`、以及本轮的 `t5_probes`（那次是 `parents[4]` 写对但 `_t5_close.py` 的 `parents[2]` 也需复核）。
**⚠️ 每次都靠那条 `assert` 当场抓住、没有一次产生错误结论** —— 这正是硬规矩 #82（「探针的每一个前提都要有一条会红的断言」）的正面回报。**故不立新规矩，只记一笔：`assert BACKEND.is_dir()` 这一行是本项目里性价比最高的一行代码。**

### ⚠️ 按硬规矩 #86 回扫 Task 7/8/9 与 Plan 04（实现者给的 6 条关切，控制者逐条裁定）

1. **Task 7**：**`*_skip_traces` 必须有消费者**（顶回 7 的产出）。裁定：**Task 7 把 `student_skip_traces` / `class_skip_traces` 的计数写进 `daily_sync_run` 的日志或 `alert` 的 `trigger_snapshot` 之外的一个运维字段**；若无处可放，**至少要有一条测试断言它们被读过**（否则就是死配置，与 Plan 02 的 `Intensity.rpe` 同型）。
2. **Task 7**：**`rpe_session_ids` 必须按时间升序**（domain 只校长度、校不了顺序）→ **Task 7 组装 `StudentSignals` 时要按 `submitted_at` 排序，并加一条测试钉住**（乱序会让 `window_key` 取到错误的 `class_session_id`，从而让去重键失效 → 同一学生重复触发 → `0.8³`）。
3. **Task 7**：**`rpe_min` 与 `improve_pct` 由 Task 7 消费，不读就是死配置**（`rpe_min` 是「连续 ≥ 9」的那个 9，Task 7 要自己数连续；`improve_pct` 是「提高 ≥ 10%」，Task 7 要自己算 `mini_test_improved`）。
4. **Task 7**：**`completion_rate` 必须夹在 `[0,1]`**（`GREEN_MASTERY` 的 `>=` 与顶回 6 的等价性论证都建立在这个前提上；**越界会让 `>=1.0` 与 `==1.0` 不再等价**）。
5. **Task 7**：**`checkin_gap_days` 的「应打卡训练日」语义有一半住在调用方**（domain 只收一个整数）→ Task 7 要复用 Task 5 的 `_training_days_of()`，**不要另写一份**。
6. **Task 8/9**：**`AlertRules.params_of` 今天没有生产调用者**（留给 Task 7）；**Task 9 的勘误要收 5 条待清扫 + 顶回 3 的两个数（27/超宽3 → 25/超宽1）+ #29 的阈值个数（8 → 9）**。

**下一步**：抽 `task-7-brief.md` → 派实现者（预警落地 + `InAppChannel` + `weekly_adjustment` 的 `auto` 来源）。
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
SENT = "Task 6: complete (commits a8d61b4..caf80c5"
assert SENT not in t, f"{SENT!r} 已存在"
LEDGER.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)}")
for k in ("Ruling 16", "硬规矩 #111", "控制者错误 #26", "控制者错误 #29", "1026 passed", "58 次", "E48E3AC82BB45BB7"):
    print(f"  {k}: {c.count(k)}")

print("\n[git] 提交")
subprocess.run(["git", "add", ".superpowers/sdd/2026-10-08-实施计划03-反馈预警与CRUD-API层/"],
               cwd=str(ROOT), check=True)
r = subprocess.run(["git", "commit", "-m",
                    "docs(sdd): Plan03 Task 6 结案 —— 1026 passed，domain 1147/0/336/0/100%，变异取证 5/5，"
                    "Ruling 16 + 硬规矩 #111 + 控制者错误 #26-#29（顶回 8 处含 3 Critical 全采纳，累计 58/58）"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
out = (r.stdout or r.stderr).strip().splitlines()
print("  " + (out[1] if len(out) > 1 else out[0] if out else "(无输出)"))
r = subprocess.run(["git", "log", "--oneline", "-1"], cwd=str(ROOT), capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print(f"  HEAD = {(r.stdout or '').strip()}")
r = subprocess.run(["git", "status", "--short"], cwd=str(ROOT), capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print(f"  git status -> {(r.stdout or '').strip() or '（干净）'}")

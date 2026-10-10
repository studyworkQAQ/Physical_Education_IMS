"""Plan 03 Task 8 亲验 + 结案（Ruling 18）+ commit。⚠️ #109：不符项先用第二个工具复核。"""
import ast
import dataclasses
import hashlib
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BACKEND = ROOT / "backend"
LEDGER = HERE / "progress.md"
assert BACKEND.is_dir(), f"BACKEND 算错了：{ROOT}"
sys.path.insert(0, str(BACKEND))
ok = True


def chk(label, got, want):
    global ok
    good = got == want
    ok &= good
    print(f"  {'✅' if good else '⚠️'} {label}: 实测 {got!r}  期望 {want!r}")


print("### 1. 扫描面 / 端点 / 表数 / 公有面")
from app.db import models as M  # noqa: E402
chk("表数", len(M.Base.metadata.tables), 25)
per = {s: len(list((BACKEND / "app" / s).rglob("*.py"))) for s in ("pipeline", "db", "domain", "api")}
print(f"  分目录 = {per}")
chk("扫描面", sum(per.values()), 58)
obs = {n for n in dir(M) if not n.startswith("_")}
subs = {"_shared", "organisation", "assessment", "derived", "ops", "feedback", "prescription"}
chk("models 公有面", len(obs - subs), 33)
from app.main import create_app  # noqa: E402
spec = create_app(db_url="sqlite://").openapi()
api = [p for p in spec["paths"] if p.startswith("/api/")]
ops = sum(1 for p in api for m in spec["paths"][p] if m in ("get", "post", "patch", "delete"))
chk("/api/ 路径模板数", len(api), 62)
chk("操作数", ops, 90)
for want in ("/api/dashboard/class/{course_section_id}",
             "/api/dashboard/weekly-class-report/{course_section_id}",
             "/api/students/{student_id}/home",
             "/api/teacher/students/{student_id}/weekly-sheet",
             "/api/notifications/{notification_id}/read"):
    hit = want in spec["paths"]
    ok &= hit
    print(f"  {'✅' if hit else '⚠️'} {want}")
n_sec = sum(1 for p in api for m, op in spec["paths"][p].items()
            if isinstance(op, dict) and op.get("security"))
chk("挂 security 的操作数", n_sec, 17)
n_schema = sum(1 for p in api for m, op in spec["paths"][p].items() if isinstance(op, dict)
               for code, r in op.get("responses", {}).items() if code.startswith("2")
               and r.get("content", {}).get("application/json", {}).get("schema"))
n_2xx = sum(1 for p in api for m, op in spec["paths"][p].items() if isinstance(op, dict)
            for code in op.get("responses", {}) if code.startswith("2"))
print(f"  2xx 响应带 schema = {n_schema} / {n_2xx}（前端 codegen 的可用性）")

print("\n### 2. app/domain/report.py 的 __all__ 与 RpeWeek")
import app.domain.report as RP  # noqa: E402
chk("__all__ 长度", len(RP.__all__), 26)
funcs = [n for n in RP.__all__ if callable(getattr(RP, n)) and not dataclasses.is_dataclass(getattr(RP, n))
         and not isinstance(getattr(RP, n), type)]
consts = [n for n in RP.__all__ if n.isupper()]
print(f"  函数 {len(funcs)} 个 / 常量 {len(consts)} 个 / 值类型 {[n for n in RP.__all__ if n not in funcs and n not in consts]}")
print(f"  RpeWeek 字段 = {[f.name for f in dataclasses.fields(RP.RpeWeek)]}")

print("\n### 3. _replay_cleanup 的清单（AST 口径）")
dp = (BACKEND / "app" / "pipeline" / "daily.py").read_text(encoding="utf-8")
tree = ast.parse(dp)
found = None
for n in ast.walk(tree):
    if isinstance(n, ast.FunctionDef) and n.name == "_replay_cleanup":
        for s in ast.walk(n):
            if isinstance(s, (ast.Tuple, ast.List)) and len(s.elts) >= 3:
                names = [ast.unparse(e) for e in s.elts]
                if all(("models" in x) or x[0].isupper() for x in names):
                    found = names
print(f"  清单 = {found}")
chk("清单长度", len(found or []), 7)
chk("含 WeeklyClassReport", any("WeeklyClassReport" in x for x in (found or [])), True)
chk("不含 ClassSession", any("ClassSession" in x for x in (found or [])), False)
iw = next((i for i, x in enumerate(found or []) if "WeeklyAdjustment" in x), -1)
ip = next((i for i, x in enumerate(found or []) if x.endswith("Prescription")), -1)
good = 0 <= iw < ip
ok &= good
print(f"  {'✅' if good else '⚠️'} WeeklyAdjustment(#{iw}) 在 Prescription(#{ip}) 之前")

print("\n### 4. 周日判据 + training_days_of 单一所有者")
rs = (BACKEND / "app" / "pipeline" / "report_stage.py").read_text(encoding="utf-8")
for pat in ("is_report_day", "weekday()", "REPORT_WEEKDAY"):
    print(f"  report_stage.py 里 {pat!r} 命中 {rs.count(pat)}")
hits = []
for p in sorted(BACKEND.rglob("*.py")):
    if "__pycache__" in p.parts or "_probes" in p.parts:
        continue
    try:
        tr = ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for n in ast.walk(tr):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.endswith("training_days_of"):
            hits.append(f"{p.relative_to(BACKEND).as_posix()}:{n.lineno}")
print(f"  training_days_of 定义点 = {hits}")
chk("定义份数", len(hits), 1)

print("\n### 5. 四个指纹 + data 未改 + pe.db")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "5394B37F01DAC9AC"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301"),
                  ("data/alert_rules.yaml", "E48E3AC82BB45BB7")):
    b = (BACKEND / rel).read_bytes()
    chk(rel, hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper(), want)
    print(f"      {len(b)} B  CRLF={b.count(bytes([13,10]))}")
r = subprocess.run(["git", "diff", "--stat", "6127fc7", "HEAD", "--", "backend/data"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  git diff -- backend/data -> {(r.stdout or '').strip() or '（空）✅'}")
chk("pe.db 存在?", (BACKEND / "pe.db").exists(), False)
chk("test_backfill.py 是否已按字节还原（实现者说它临时改过阈值取证）",
    subprocess.run(["git", "diff", "--stat", "HEAD", "--", "backend/tests/pipeline/test_backfill.py"],
                   cwd=str(ROOT), capture_output=True, text=True,
                   encoding="utf-8", errors="replace").stdout.strip(), "")

print(f"\n===== 亲验结论：{'全部通过 ✅' if ok else '⚠️ 有不符项（按 #109 先复核再采信）'} =====")
if not ok:
    sys.exit(1)

# ================= 账本 =================
b = LEDGER.read_bytes()
t = b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"\n[ledger before] bytes={len(b)} lines={t.count(nl)}")

BODY = """

---

## ✅ Task 8: complete (commits 6127fc7..d100ff5, 0 fix round)

**交付**：`6b5decc`（`app/domain/report.py` —— 周报与大屏**共享**的九个聚合量，纯函数、100% 分支覆盖、**24 条变异全 killed**）、`e593532`（Report 阶段接进 `daily.py`：周日判据 + **与 Alert 阶段共享同一个 `now`** + `_replay_cleanup` 6→7 张）、`415db83`（大屏/首页聚合读接口 + **P8-A5 的教师端训练单变体** + 通知已读，security 清单 12→17）、`d100ff5`（报告 + 派单 + 7 个探针）。

**验收（控制者本机亲跑复核，探针 `_t8_verify.py` 已入库）**：
- 全量 **1097 → 1225 passed**（+128 = `test_report.py` 55 + `test_report_stage.py` 35 + `test_daily.py` 2 + `test_dashboard.py` 36），**既有 1097 条一条都没退步**；带 `--cov` **1224 passed, 1 skipped**
- **`app/domain/` 四格 1147/0/336/0 → `1259 stmts / Miss 0 / 376 branch / BrPart 0 / 100%`** —— **`Miss` 与 `BrPart` 仍是 0**，stmts +112 / branch +40 **恰为 `report.py` 一个文件的量**（P8-A2 的裁定兑现了：聚合逻辑进了 domain，故它被 100% 分支覆盖）
- **扫描面 54 → 58**（pipeline 9→10、db 11、domain 17→18、api 17→19）；**`/api/` 路径模板 57 → 62、操作数 85 → 90**（控制者从 `openapi()` 实读）；**挂 `security` 的操作数 12 → 17**；表数 **25**；`_MODELS_PUBLIC_BASELINE` **33**
- **五个新端点逐个亲验在线**：`GET /api/dashboard/class/{course_section_id}`、`GET /api/dashboard/weekly-class-report/{course_section_id}`、`GET /api/students/{student_id}/home`、`GET /api/teacher/students/{student_id}/weekly-sheet`、`POST /api/notifications/{notification_id}/read`
- **`app/domain/report.py` 的 `__all__` = 26 个名字**（10 个函数 + 1 个值类型 `RpeWeek`（字段 `days` / `values`）+ 15 个常量）
- **`_replay_cleanup` 的清单控制者用 AST 口径亲验 = 7 张**：`models.DerivedMetrics / models.StratificationResult / models.PercentileSnapshot / WeeklyAdjustment / Prescription / Alert / WeeklyClassReport`；**`ClassSession` 确实不在里面**；**`WeeklyAdjustment` 仍在 `Prescription` 之前**（子表先删）
- **`training_days_of` 定义份数 = 1**（AST 口径，P8-A3 兑现）
- **周日判据的三格边界测试**（日期一律字面写死、且都真的跑一遍 `run_daily`）：`test_a_saturday_does_not_generate_a_report`（2025-09-13 → 0 行）、`test_a_sunday_generates_a_report`（2025-09-14 → 1 行、`week == 2`）、`test_a_monday_does_not_generate_a_report`（2025-09-15 → 0 行）；另有 `test_the_report_weekday_constant_is_six_and_six_is_sunday`（**反证 `isoweekday()==6` 是周六**）、`test_is_report_day_over_one_whole_real_week`（七天逐个过）、`test_a_sunday_before_the_semester_starts_generates_nothing`（2025-08-31：`is_report_day` 为真而 `semester_week_of` 为 `None`，**两个判据不互相掩盖**）
- **禁区**：四个指纹逐字不变（CRLF 全 0）；`git diff 6127fc7 HEAD -- backend/data` **为空**；`pe.db` 不存在；`data/seed/` 0 文件；**`test_backfill.py` 已按字节还原**（实现者为取证 `elapsed` 临时改过阈值，控制者亲验 `git diff` 为空）
- **性能哨兵**：`elapsed` 实测 **43.96 / 48.37 s**（n=2，同口径基线 47.33 / 47.96），余量 **1.86×** vs 基线 1.88× —— **差异在 n=2 的组内极差（4.41 s）之内，没有可辨退化**

### Ruling 18 — 实现者顶回 4 处，**全部采纳**（Plan 03 的第 39–42 次；累计 **67 次，67 次都对**）

**顶回 3（Critical，采纳 → 控制者错误 #33）：P8-A5 那条授权链必须带学期，派单没说。** 派单写的是「`enrollment` 表 + `course_section.teacher_id` 是那条链」，**而没有要求两行的 `semester_id` 都等于 `as_of` 所属的那个学期**。**不带的后果**：判据退化成「他**曾经**教过这个学生」—— **上学期教过某人的教师，这学期仍读得到他本学期的训练单**。实现者落地的链是 `teacher.staff_no → teacher.id → course_section.teacher_id → enrollment.course_section_id → enrollment.student_id`，**且两行的 `semester_id` 都必须等于 `as_of` 所属的那个学期**。
**⚠️ 最值得记的是它自己说的这句：「这一格是被自己的测试抓到的，不是先想到的。」** 即**它先按派单写了、测试红了、才发现派单少了一格** —— 这正是 TDD 的回报，也是 Ruling 5（独立评审席折进控制者亲验）唯一还站得住的理由：**控制者亲验抓不到「控制者自己规定的东西是错的」，而实现者的测试能。**
**→ 补硬规矩 #114：派单里写「用 X 表 + Y 列做校验」时，必须同时写明**时间/学期的限定**——授权与归属类的判据几乎总是「在某一段时间内成立」，而「曾经成立」与「现在成立」是两个不同的判据。** 依据：#33。**⚠️ 这一族与 #112（「传导纪律时只传性质、不指定用哪一列」）是一对**：#112 管「不要给错的机制」，#114 管「不要给不完整的机制」。

**顶回 1（采纳 → 控制者错误 #34）**：`generate_weekly_reports` 的签名**跑不起来** —— 派单写 `(*, as_of)`，而 `generated_at` 是 `DateTime NOT NULL` 且无缺省、`training_days_of` 要 `exercises` → 补 `now` / `exercises`。**⚠️ 与 Task 7 顶回 `evaluate_alerts` 的签名是同型同理由**（`triggered_at` 与 `created_at` 都是 NOT NULL 无缺省）。**这是控制者连续两个 Task 犯同一个错**：写端点/阶段函数的签名时，**没有核那些 NOT NULL 无缺省的列由谁填**。
**→ 硬规矩 #98 再扩写：派单给出一个函数签名时，必须逐个核对它要写的表的 NOT NULL 无缺省列，每一列都要在签名里有一个来源（形参、或函数体里能从形参算出来）。**

**顶回 2（采纳）**：`ReportSummary` 加第三格 `errors`，并**给派单没定义的 `skipped` 定了口径**（= **名册为空的班**；并明确它**不是**「判不了」的垃圾桶）。**⚠️ 这与 Task 7 的 `AlertReport.skipped`（= `*_skip_traces` 的计数）是两个不同的 `skipped`** —— 同名不同义，**控制者裁定：两个都保留，但各自的 docstring 必须写明自己的口径**（否则下一个人会以为它们是同一个量）。

**顶回 4（采纳，且它报的成本比派单说的更高）**：P8-A6 的结论对（不加 `screen:` 段），但**成本比派单说的更高** —— `refdata_alerts.load_alert_rules` 的校验顺序是「**顶层键集** → version → rules 键集 → 逐条规则」，而**顶层键集是「恰好相等」的判据**，故加 `screen:` 段会**当场让加载器响亮失败**、必须再动一个 Task 6 已结案的守卫。**处置照派单办**（不加、四个指纹不变、阈值做 domain 常量并注明「待体育专家确认」）。**⚠️ 这一条说明控制者的 P8-A6 只算了「指纹要同步」这一项成本，漏了「加载器的键集校验是恰好相等」这一项** —— 与 #26（P6-A2 没读 `_fail` 的函数体）同族：**引用一个既有实现的做法，却没读它的实现。**

### 5 处偏离派单字面：全部追认

① **新增 `app/api/schemas/dashboard.py`（16 个响应模型）**，在派单的 Create 清单之外，**理由是 P4-A5「要确保后端和前端能够对接的上」** —— 控制者认为这是本轮最好的一处偏离：**没有响应模型，`/openapi.json` 里那 5 个新端点的 2xx 就是空的，前端 codegen 拿不到任何形状**（控制者亲验：2xx 响应带 schema 的比例见上面第 1 节）；② 多改 `deps.py` / `routers/prescription.py` / `schemas/__init__.py` 三个文件；③ `_replay_cleanup` 的 AST 断言放在 `test_report_stage.py` 而不是 `test_daily.py`（与 Task 7 把 `Alert` 那一条放在 `test_alert_stage.py` 同构）；④ **`test_daily.py` 的 `PIPELINE_TABLES` 刻意不加 `weekly_class_report`**（那条测试跑在周一，**加了是空转守卫**——硬规矩 #92 的正面执行）；⑤ **删掉 `generate_weekly_reports` 里一段自己第一版写的、实测不可达的学期存在性校验**。

### ⚠️ 变异取证 24/24 killed，其中两条的来历值得记

`report.py` 做了 **24 条变异、全部 killed**。其中 **M13 与 M23 两条是「先写测试 → 变异存活 → 补反例 → killed」的产物**，各对应硬规矩 #107（谓词先对已知反例验证）与**字符串驻留**。
**⚠️ 控制者裁定：这个形状（变异存活 → 补反例）比「一次就 killed」更有价值**，因为它证明的是「测试**曾经**抓不到、现在抓得到了」—— 而一次就 killed 只证明「这条变异在这个测试面前是可达的」。**→ 记进 Task 9 的勘误：把「变异存活过再补反例」当作一种正当的、要写进报告的取证形状，不是「测试写错了」的证据。**

### 待清扫：**6 条**（另有 4 条关切）

① `_stratification_payload` 是 `input_snapshot_of` 的**逆运算**，而正向那一份住在 `run_stratify.py`（**两个所有者，一正一逆**）；② **两档 404 的形状在 OpenAPI 里看不见**；③ **`daily_sync_run` 没有 `report_count` 列**（周报份数只有日志，而 `prescription_count` 与 `alert_count` 都有列 —— 三个阶段的可观测量不一致）；④ **教师侧「通知已读」今天没有端点**；⑤ **`mini_test.normalized_score` 仍只有 `demo_data` 一个写入方**（**进步榜在生产路径上会全员 `unmeasured`**）；⑥ 三个写入端点仍只过 `require_teacher`（没有任教关系校验）。
**⚠️ 第 ⑤ 条要传导给 Plan 04**：进步榜（`progress_board`）在真实数据下会全是 `unmeasured`，因为 `POST /api/mini-tests/batch` 今天**不算** `normalized_score`（Task 5 的 `GET /api/mini-tests/normalized` 是**读时算**、不写回列）。**故 Plan 04 的进步榜要调 `GET /api/mini-tests/normalized`，不要读 `weekly_class_report.progress_board`** —— 或者 **Task 9 要让 `report_stage` 在生成周报时把标准化得分算出来填进 `progress_board`**（控制者倾向后者，因为周报是快照、而快照里的量应该在生成时就算好）。

### ⚠️ 按硬规矩 #86 回扫 Task 9 与 Plan 04

1. **Task 9**：`_replay_cleanup` 现在是 **7 张**，钉住它的守卫是 `test_the_replay_cleanup_list_is_pinned_to_seven_tables`（**函数名里有「seven」**，Task 9 若再加表要连函数名一起改）。
2. **Task 9**：**`progress_board` 的填充口径要定**（见待清扫第 ⑤ 条）。
3. **Task 9 的勘误清单再新增 3 条**：① `require_teacher` / `require_scope` 里「原型没有教师↔班级↔学生授权模型」那两句**已被 Task 8 改写**（它连带收窄了班级那一侧），核实新文本是否如实；② **两个不同的 `skipped`** 各自 docstring 是否写明口径（顶回 2）；③ **`daily_sync_run` 三个阶段的可观测量不一致**（`prescription_count` / `alert_count` 有列，周报份数只有日志）。
4. **Plan 04**：① **`app/api/schemas/dashboard.py` 有 16 个响应模型**，前端 codegen 直接可用；② 教师端读学生训练单的路径是 **`/api/teacher/students/{student_id}/weekly-sheet`**（与学生侧 `/api/students/{student_id}/weekly-sheet` **响应体逐字相同**，因为 `weekly_sheet` 的函数体被抽成 `_weekly_sheet_response` 两处共用）；③ **进步榜走 `GET /api/mini-tests/normalized`**（见待清扫第 ⑤ 条）；④ `POST /api/alerts/{alert_id}/handle` 的三个动作值是 `ACTION_REDUCE` / `ACTION_IGNORE` / `ACTION_NOTE`。

**下一步**：抽 `task-9-brief.md` → 派实现者（GC14 + 端到端冒烟 + `demo.ps1` + spec 勘误）。**⚠️ 这是 Plan 03 的最后一个 Task，也是「能运行起来」的唯一可执行判据所在。**
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
SENT = "Task 8: complete (commits 6127fc7..d100ff5"
assert SENT not in t, f"{SENT!r} 已存在"
LEDGER.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)}")
for k in ("Ruling 18", "硬规矩 #114", "控制者错误 #33", "控制者错误 #34", "1225 passed", "67 次"):
    print(f"  {k}: {c.count(k)}")

print("\n[git] 提交")
subprocess.run(["git", "add", ".superpowers/sdd/2026-10-08-实施计划03-反馈预警与CRUD-API层/"],
               cwd=str(ROOT), check=True)
r = subprocess.run(["git", "commit", "-m",
                    "docs(sdd): Plan03 Task 8 结案 —— 1225 passed，domain 1259/0/376/0/100%，62 个端点，"
                    "Ruling 18 + 硬规矩 #114 + 控制者错误 #33/#34（顶回 4 处全采纳，累计 67/67）"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
out = (r.stdout or r.stderr).strip().splitlines()
print("  " + (out[1] if len(out) > 1 else out[0] if out else "(无输出)"))
r = subprocess.run(["git", "log", "--oneline", "-1"], cwd=str(ROOT), capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print(f"  HEAD = {(r.stdout or '').strip()}")
r = subprocess.run(["git", "status", "--short"], cwd=str(ROOT), capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print(f"  git status -> {(r.stdout or '').strip() or '（干净）'}")

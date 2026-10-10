"""Plan 03 Task 9 亲验 + 结案（Ruling 19/20 + 硬规矩 #115）+ commit。⚠️ #109：不符项先复核。"""
import hashlib
import json
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


print("### 1. 计数")
from app.db import models as M  # noqa: E402
chk("表数", len(M.Base.metadata.tables), 25)
per = {s: len(list((BACKEND / "app" / s).rglob("*.py"))) for s in ("pipeline", "db", "domain", "api")}
print(f"  分目录 = {per}")
chk("扫描面", sum(per.values()), 60)
from app.main import create_app  # noqa: E402
spec = create_app(db_url="sqlite://").openapi()
api = [p for p in spec["paths"] if p.startswith("/api/")]
ops = sum(1 for p in api for m in spec["paths"][p] if m in ("get", "post", "patch", "delete"))
chk("/api/ 路径模板数", len(api), 63)
chk("操作数", ops, 91)
n_sec = sum(1 for p in api for m, op in spec["paths"][p].items()
            if isinstance(op, dict) and op.get("security"))
chk("挂 security 的操作数", n_sec, 18)
chk("run-daily 端点在线", "/api/pipeline/run-daily" in spec["paths"], True)
gcb = (BACKEND / "tests" / "fixtures" / "golden_cases.json").read_bytes()
gc = json.loads(gcb.decode("utf-8"))
# ⚠️ 结构无关地找「用例列表」：顶层是 dict、键名不叫 cases，故取「第一个 list-of-dict 的值」。
#    （控制者第 5 次用错探针工具：先假定了一个键名。硬规矩 #107 的正面执行是「先看清结构」。）
if isinstance(gc, dict):
    print(f"  golden_cases.json 顶层键 = {list(gc)}")
    cases = next((v for v in gc.values() if isinstance(v, list) and v and isinstance(v[0], dict)), [])
else:
    cases = gc
chk("黄金用例数", len(cases), 14)
ids = [c.get("id") or c.get("case_id") or c.get("name") for c in cases]
print(f"  用例 id = {ids}")

print("\n### 2. GC14 覆盖的那一档")
c14 = [c for c in cases if (c.get("id") or c.get("case_id") or "").upper().endswith("14")]
if c14:
    c14 = c14[0]
    prof = c14.get("profile", c14)
    print(f"  bmi = {prof.get('bmi')}")
    exp = c14.get("expected", {})
    print(f"  safety_triggers = {exp.get('safety_triggers')}")
    print(f"  safety_skipped  = {exp.get('safety_skipped')}")
    print(f"  template_id     = {exp.get('template_id')}")
    chk("GC14 命中 bmi_over_30", "bmi_over_30" in (exp.get("safety_triggers") or []), True)

print("\n### 3. 五个指纹 + data 未改 + pe.db")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "5394B37F01DAC9AC"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301"),
                  ("data/alert_rules.yaml", "E48E3AC82BB45BB7")):
    b = (BACKEND / rel).read_bytes()
    chk(rel, hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper(), want)
fx = (BACKEND / "tests" / "fixtures" / "golden_cases.json").read_bytes()
print(f"  golden_cases.json {len(fx)} B  CRLF={fx.count(bytes([13,10]))} bareLF={fx.count(bytes([10])) - fx.count(bytes([13,10]))}")
chk("golden_cases.json as-is 指纹", hashlib.sha256(fx).hexdigest()[:16].upper(), "39FC9C29D9106C47")
chk("golden_cases.json CRLF→LF 指纹",
    hashlib.sha256(fx.replace(b"\r\n", b"\n")).hexdigest()[:16].upper(), "9FB1C619F896D418")
r = subprocess.run(["git", "diff", "--stat", "cf9ad7a", "HEAD", "--", "backend/data"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  git diff -- backend/data -> {(r.stdout or '').strip() or '（空）✅'}")
chk("pe.db 存在?", (BACKEND / "pe.db").exists(), False)
chk("data/seed 文件数", len(list((BACKEND / "data" / "seed").rglob("*")))
    if (BACKEND / "data" / "seed").exists() else -1, 0)

print("\n### 4. demo.ps1 存在且第一步删旧库 + 显式设 PE_DB_URL")
dp = BACKEND / "scripts" / "demo.ps1"
chk("demo.ps1 存在", dp.exists(), True)
if dp.exists():
    b = dp.read_bytes()
    print(f"  {len(b)} B / {b.decode('utf-8', errors='replace').count(chr(10))} 行  "
          f"BOM={b[:3] == bytes([0xEF, 0xBB, 0xBF])}  CRLF={b.count(bytes([13,10]))}")
    s = b.decode("utf-8-sig", errors="replace")
    for pat in ("pe_demo.db", "Remove-Item", "PE_DB_URL", "pe.db", "seed.generate", "pipeline.backfill"):
        print(f"    {pat!r} 命中 {s.count(pat)}")
    chk("不含禁区命令 seed.generate", "seed.generate" in s, False)
    chk("不含禁区命令 pipeline.backfill", "pipeline.backfill" in s, False)
chk("demo_bootstrap.py 存在", (BACKEND / "scripts" / "demo_bootstrap.py").exists(), True)

print("\n### 5. 标准化得分的单一所有者（AST 数定义份数）")
import ast  # noqa: E402
hits = []
for p in sorted(BACKEND.rglob("*.py")):
    if "__pycache__" in p.parts or "_probes" in p.parts or "scripts" in p.parts:
        continue
    try:
        tr = ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for n in ast.walk(tr):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in (
                "shuttle_percentile", "mini_test_scores"):
            hits.append((n.name, p.relative_to(BACKEND).as_posix(), n.lineno))
print(f"  定义点 = {hits}")
chk("两个函数各只有一份定义", len(hits), 2)
chk("都在 app/domain/report.py", all("domain/report.py" in h[1] for h in hits), True)

print("\n### 6. ⚠️ 关切 ④ 复核：POST /api/class-sessions 今天是否真的匿名可写")
from fastapi.testclient import TestClient  # noqa: E402
cl = TestClient(create_app(db_url="sqlite://"))
op = spec["paths"].get("/api/class-sessions", {}).get("post", {})
print(f"  openapi 里 POST /api/class-sessions 的 security = {op.get('security', '（无 = 匿名）')}")
print(f"  挂 security 的 POST 端点清单：")
for p in api:
    for m, o in spec["paths"][p].items():
        if m == "post" and isinstance(o, dict) and o.get("security"):
            print(f"     POST {p}")

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

## ✅ Task 9: complete (commits cf9ad7a..4a8b792, 0 fix round) —— **Plan 03 的 9 个 Task 全部完成**

**交付（6 个 commit）**：`db3eec0`（GC14：让 spec §7.4「BMI > 30」那一档在黄金用例里**第一次真的命中**）、`491c4e7`（`POST /api/pipeline/run-daily` + **端到端冒烟八步走完整条闭环**）、`de95ef6`（周报的进步榜在**生成时**算标准化得分；算式提到 domain 一个住址）、`ec6a65f`（**`demo.ps1` + `demo_bootstrap.py`：一条命令把系统跑起来**）、`9c0b1e9`（spec 勘误 §14 补 #38/#39/#40 + 10 处章节勘误 + 19 条待清扫）、`4a8b792`（结案文档：报告 + 派单原文 + 28 个探针，31 files / 5076 insertions，**不含生产代码**）。

**验收（控制者本机亲跑复核，探针 `_t9_verify.py` 已入库）**：
- 全量 **1225 → 1244 passed**（+19；带 `--cov` 时 `1243 passed, 1 skipped`）
- **`app/domain/` 四格 1259/0/376/0 → `1268 stmts / Miss 0 / 376 branch / BrPart 0 / 100%`** —— **`Miss` 与 `BrPart` 仍是 0**（`app/domain/report.py` 112 → 121 stmts）
- **扫描面 58 → 60**（pipeline 10 + db 11 + domain 18 + **api 21**）；**`/api/` 路径模板 62 → 63、操作数 90 → 91、挂 `security` 的 17 → 18**（控制者从 `openapi()` 实读）；表数 **25**；`_MODELS_PUBLIC_BASELINE` **33**
- **黄金用例 13 → 14**（控制者亲验用例数 = 14）；**GC14 覆盖 `bmi_over_30` 那一档**，且是 14 例里**唯一同时命中两个触发**的（`safety_triggers=["bmi_over_30","body_fat_abnormal"]`、`safety_skipped=["muscle_p10_missing"]`），`bmi=31.0` → `RED-SPD-ABN-05`、32 次等价替换、`needs_review=false`
- ⚠️ **`muscle_low_p10` 那一档仍不可达、刻意留下**：`smi` 为 `null` 时 `safety.py` 走的是 **skipped 分支**而不是触发分支，要命中它得先有一个「肌肉量低于 P10 但 `smi` 有值」的输入，**而那与 GC14 要钉的 BMI 档冲突**；理由已写进夹具 `_meta`
- **`golden_cases.json` 的新指纹控制者亲验**：43 571 B / 892 行 → **51 619 B / 959 行**；as-is sha256[:16] `A08B6AE9A463BBA3` → **`39FC9C29D9106C47`**、CRLF→LF `E0E2DABA0FE97344` → **`9FB1C619F896D418`**；**CRLF 959 / bare LF 0**（纯 CRLF，与本仓夹具的既有行尾一致）
- **硬编码「13」的连带**：3 条相等断言（`== 13` → `== 14`）+ 7 个文件里 **28 处**散文 + 夹具 `_meta` **24 处**精确串替换。**既有 13 例零影响**（实现者逐例对拍 `bmi`/`match_status`/`template_id` 全 SAME；百分位快照仍 24 行，只有 (male, 大一、大二) 那 6 行的 `sample_size` 8→9，**五档判定线与 source 逐格不变**）
- **端到端冒烟走真实 HTTP**：客户端是 `fastapi.testclient.TestClient`（内部是 **httpx 的 `ASGITransport`**，基址恒为 `http://testserver`），**八步全部走 HTTP 往返**，含两格对照（换学生头 → **403 forbidden**；拿错口令 → **403 `invalid_rpe_token`** 且库里仍 3 条）。关键格：① `alert_count==0`（④ 那格 `==2` 的对照）④ 重放的 `daily_sync_run_id` 与 ① **逐字相同** ⑤ RED 恰好 1 条 + `window_key == f"rpe{第三节课 id}"`（**期望侧用 ③ 的响应现拼，两侧不同源**）⑥ **`adjustment is None`**（管道已自动减过，**教师点击没有第二次减量**）⑦ **`factor==0.8` 而不是 `0.64`** + block 量 == 骨架 × 0.8（两个不同投影）⑧ 学生恰好 1 条 + `is_read is False`。**变异 3/3 killed，各打一个层间接缝**
- **`demo.ps1` 真机取证（port 8010，避开控制者的 8000）**：`backend/scripts/demo.ps1`（171 行 / 9 750 B，**UTF-8 带 BOM + CRLF** —— ⚠️ PowerShell 5.1 读无 BOM 的 `.ps1` 会按 GBK 静默乱码）+ `demo_bootstrap.py`。**真 uvicorn + 真磁盘 SQLite**：`GET /api/health` → **`{"status":"ok","tables":25,"students":60}`**；处置前 `factor=0.8`；换学生头 → **403** `{"error":{"code":"forbidden","message":"学生 2 无权访问学生 1 的数据","detail":null}}`；handle → `adjustment=None` + notification `title='本周训练量已减 20%'`、处置后 `factor` 仍 **0.8**；`POST /api/notifications/1/read` → `is_read=true`；**`progress_board` 非空**（top: student 10 `+235.88%`）；重放 `run-daily` → `status=success run_id=1 prescription_count=60 alert_count=11`；**`pe.db` 不存在、`data/seed/` 0 文件**。演示库：8 节课 / 240 条快评 / 180 条小测 / **11 条预警**（`RED_RPE_SUSTAINED` 6 + `RED_MINITEST_DROP` 5）。⚠️ **`DEMO_AS_OF` 必须从 `2025-09-14` 挪到 `2025-10-12`**（学期第 6 周的周日）才有预警可看，两个下界的推导写进了注释
- **`progress_board` 的裁定已落地**：`report_stage.class_snapshot` 在**生成周报时**用 `mini_test_scores` 现算，**不再读 `mini_test.normalized_score` 列**。算式（`shuttle_percentile` / `mini_test_scores`）从 `app/api/routers/feedback.py` **提到 `app/domain/report.py` 一个住址**，两层都从那里 import，`feedback.py` 里那一份私有实现已删。**控制者用 AST 亲验：两个函数各只有一份定义、都在 `app/domain/report.py`** ✅（⚠️ 派单说的「定义份数 == 1」是「**一个住址**」，而那一个住址里有**两个**函数定义，故守卫断言的是 **2**；M7 变异往 `report_stage.py` 塞第二份 → 守卫报 `3 != 2` → KILLED）
- **禁区**：**五个指纹逐字不变**（四个 YAML/CSV + 18 套处方模板 18-18 逐字一致）；**`git diff cf9ad7a HEAD -- backend/data` 为空**；`pe.db` 不存在；`data/seed/` 0 文件

### Ruling 19 — 实现者顶回 6 处，**全部采纳**（Plan 03 的第 43–48 次；累计 **73 次，73 次都对**）

**顶回 1（采纳 → 控制者错误 #35）**：**`golden_cases.json` 不在 `backend/data/` 下** —— 全仓只命中 **`backend/tests/fixtures/golden_cases.json`**。**后果：派单第 9 节那一格验收的正确答案是「`backend/data` 一个字节都没动」，而不是「只多出 `golden_cases.json`」。** 控制者亲验坐实：`git diff cf9ad7a HEAD -- backend/data` **为空**。**⚠️ 这是硬规矩 #97 的第 4 次违反**（派单里提到的每一个文件路径都要先核实它真的在那个位置）。

**顶回 2（采纳）**：**这份文件没有指纹常量，P9-A3 六步程序的第 4/5 步不存在** —— 五组指纹一个都不在它上面。实现者按**剩下四步**办 + 补做等价物（**改前改后各两个 sha256** + 变异 3/3）。**⚠️ 控制者在派单里把 Plan 02 的 P9-A3 六步程序原样搬过来，没有先核这份文件有没有指纹常量**（与 #26 同族：引用一个既有程序，却没核它的前提）。

**顶回 3（采纳）**：**`GET /api/alerts?rule_id=…` 这个筛选不存在** —— 泛型 list 只有 `limit`/`offset`，**FastAPI 静默忽略未知查询参数**。实现者采「`?limit=200` + 客户端过滤 + **断言恰好 1 条且 `total==2`**」，**这是更强的断言**（它同时钉住了「筛选不存在」这个事实，故若将来加了筛选，这条测试会提醒改写）。**⚠️ 「FastAPI 静默忽略未知查询参数」这一格值得记**：它意味着**一个拼错的查询参数不会报错、只会静默返回全量** —— 前端最容易踩。

**顶回 4（采纳）**：**spec §9.1 的勘误按实际写、不按计划正文写** —— `alert_rules.yaml` 里**没有** `screen:` 段（P8-A6 的裁定：不加），两个阈值住在 `app/domain/report.py`。**照计划写会让 spec 说一件没发生的事。**

**顶回 5（采纳 → 控制者错误 #36）**：**`test_layering.py` 那两条注释的当前值不是 90/36，而是 130/38** —— 实现者用 **AST 与 `rglob` 两个独立口径各数一遍、结果一致**。⚠️ **差额成因它没有完全定死**（最可能是控制者数的是入库文件或只数 `app/**`，而那条测试数 `backend/**/*.py` **含 47 个测试文件**），故**它在注释里附了命令让下一个人自己复算**。**控制者裁定：这个处置是对的** —— 把一个没定死成因的数写进注释、并附上复算命令，比写一个看起来确定的数更诚实。

**顶回 6（采纳）**：**`demo.ps1` 不用 `run_backfill`** —— **简报与派单冲突，采派单**。代价（演示库「周环比流动」恒为 `has_previous=False`）**已写进 `demo_bootstrap.py` 的模块 docstring**。

### 1 处偏离派单字面：追认，但它自己报出来的方式值得记

**TDD 的 RED 步骤在「端到端冒烟」这一条上是「变异代替」而不是「先写测试看它红」。** GC14 那一条照做了（先改 `== 13` → `== 14`、**亲眼看到 `assert 13 == 14` 红**）。而 `run-daily` 端点在本 Task 之前**根本不存在**，测试先写的话红的是「路由不存在」，**那一格红的信息量与 M1 变异（删掉 `include_router` → ① 得 404）完全重复**，故用 M1 当 RED 证据。⚠️ **它同时写明「两者证明同一件事，但顺序确实与派单不同」** —— 控制者追认，并认为**这个自报的形状（明知是偏离、说明为什么、并承认顺序不同）正是 Ruling 5 想要的**。

### Ruling 20 — 关切 ④ 是本轮最要紧的一条：泛型 CRUD 的写入侧今天完全匿名

**事实（实现者亲验，控制者用 `openapi()` 复核）**：**`POST /api/class-sessions` 不带任何身份头就返回 201** —— 即**任何人都能建一个课次并拿到 `rpe_token`**，而 `rpe_token` 正是学生提交快评的唯一闸门。**故那个闸门今天是可以绕过的**：建课次 → 拿口令 → 代填快评。
**成因**：Task 3 的泛型工厂给 8 个可写资源生成的 `POST`/`PATCH`/`DELETE` **一个都没挂 `security`**（控制者亲验：挂 `security` 的 18 个操作**全部是特例端点**，泛型 CRUD 的 73 个操作一个都没有）。**而派单的勘误 #19 第 2 条只点了「三个写入端点仍只过 `require_teacher`」，漏了泛型工厂这一整圈。**
**→ 控制者错误 #37**：控制者在 Task 3 的读写矩阵里逐个声明了 `writable` 与 `on_delete`，**却没有声明「可写的资源要不要身份」** —— 因为 Task 3 时还没有身份模型（`require_teacher` 是 Task 4 建的、`require_teaches_section` 是 Task 8 建的）。**而 Task 4/8 建了身份闸门之后，控制者没有回头把它应用到泛型工厂上**（硬规矩 #86 的「回扫」漏了一格）。
**裁定**：**这是 Plan 04 的第一件事，不阻塞 Plan 03 结案。** 三条理由：① **原型阶段没有真实鉴权**（Global Constraints 逐字写着「真实鉴权：用身份头 + 作用域闸门代替」），故「匿名可写」与「用身份头代替鉴权」是同一个取舍的两面；② **修它要动 `crud.py` 的工厂签名**（给 8 个可写资源挂 `require_teacher`），而那会连带 Task 3 的 23 行 `RESOURCES` 与它的遍历型守卫 —— **在 Plan 03 的最后一个 Task 里改第一个 Task 的核心工厂，风险高于收益**；③ **Plan 04 的前端本来就要给每个写请求带 `X-Teacher-Staff-No`**（`securitySchemes` 已注册），故前端不会因为后端不校验而写错。
**⚠️ 但必须显式记进 Plan 04 的第一条约束**：**给 `build_crud_router` 加一个 `require_teacher: bool` 参数，8 个可写资源全部置 `True`**（`semesters` / `teachers` / `students` / `course-sections` / `enrollments` / `body-compositions` / `interest-surveys` / `class-sessions`），并**加一条遍历型守卫断言「可写 ⇒ 挂 security」**（否则下一个人加第 24 个资源时会静默漏掉）。
**→ 补硬规矩 #115：一个横切关注点（身份、租户、审计）在系统里第一次出现时，必须回头扫一遍**所有已经建好的**同类入口，而不只是新入口。** 依据：#37。**⚠️ 这是硬规矩 #86（「回扫后续 Task」）的镜像**：#86 管「向前传导给还没做的 Task」，#115 管「向后回扫已经做完的 Task」。**Plan 03 的 #86 执行了 9 次（每个 Task 结案都回扫），而 #115 一次都没执行 —— 因为控制者从没立过它。**

### 待清扫 5 条 + 关切 7 条（Task 9 报的，控制者逐条裁定归属）

**⚠️ 待清扫第 ⑤ 条接近 Critical，控制者裁定归 Plan 04 的第一批**：**spec §13「运行方式」仍是 Plan 01 的四条命令，照它跑会破禁区**（那四条里有 `python -m app.seed.generate`，它写 `backend/data/seed/` 与 `pe.db`）。**它改的是运行手册不是勘误，故实现者显式报出留待清扫** —— 控制者认为这个判断对，且**它必须在 Plan 04 开工前改掉**（否则前端开发者照 spec §13 跑一次就破两个禁区）。
其余：① `catalog.py` 的 23 行对照表与 `RESOURCES` 书写序无守卫；② `schemas/dashboard.py` 的「16 个模型」来源只在测试的字面清单里；③ 本仓阶段序与 spec §5 编号两套混用、没有一处并排；④ `test_crud.py` 的 `running_total == 19` 没说清 19 怎么来。
**关切 7 条**：① **`GREEN_MASTERY` 读的 `normalized_score` 与进步榜算的不是同一个数**（前者读列、后者现算 → **控制者裁定：归 Plan 04，让 `GREEN_MASTERY` 也走现算的那一个住址**，否则「进步榜说他进步了」与「绿灯说他掌握了」会互相矛盾）；② **重放历史业务日时 `alert_summary` 恒为 9 个 0**（`run_daily` 的 `now` 是真实时钟、`as_of` 是历史日期，两者不同源；**生产不可达**，故只记录）；③ `run-daily` 在 `status=="failed"` 时仍回 200（**归 Plan 04：前端要靠状态码决定要不要弹错误**）；④ 见 Ruling 20；⑤ 教师端预警队列没有筛选；⑥ **`prescription_stage` 的 warning 日志措辞过宽**（演示库打 18 条「需要人工复核」，而 `status=="needs_review"` 是 **0** 张 —— **日志在说一件没发生的事**，归 Plan 04）；⑦ `_stratification_payload` 与 `input_snapshot_of` 一正一逆两个所有者。

### ⚠️ 实现者提请立一条硬规矩，控制者采纳

**它本 Task 第 5 次踩 `SyntaxError: f-string expression part cannot include a backslash`（Python 3.11）。** 建议：**f-string 里不许出现任何字节字面量，一律先提成模块级常量。**
**控制者裁定：采纳，但归并到硬规矩 #87 而不是新立一条** —— #87 今天写的是「PowerShell 下 `python -c` 里嵌双引号会被吃、f-string 里不能有反斜杠 → 复杂逻辑写临时 `.py`」，**它已经把这条包含进去了，只是写在「PowerShell」那一节里、看起来像 shell 的问题而不是 Python 的问题**。
**→ 硬规矩 #87 扩写：f-string 的表达式部分不得含反斜杠（Python 3.11 及以前是 `SyntaxError`，3.12 才放开），也不得含字节字面量 `b"..."`；需要它们时先提成模块级常量。⚠️ 这一条与 shell 无关，是纯 Python 的约束，故不要只在「PowerShell 注意事项」里找它。** 依据：实现者本 Task 第 5 次踩、Plan 02 与 Plan 03 各有多次。

### Plan 03 结案口径

**9 个 Task 全部完成，0 轮 fix round 的有 6 个（Task 3/5/6/7/8/9），1 轮的有 1 个（Task 1），Task 2 与 Task 4 也是 0 轮 —— 即 9 个 Task 里 8 个是 0 轮、1 个是 1 轮。** 这个成绩与 Ruling 1（降低执行强度）并不矛盾：**降低的是「变异测试的覆盖面」与「纯散文精度」，而 Critical 级一条都没放**，且**每个 Task 的预检都查出了 1–8 条问题**（其中 Task 2/3/5/6/7 各有一条 Critical）。
**⚠️ 更准确的归因**：**0 轮 fix round 不是因为计划对，而是因为实现者顶回来了 73 次** —— 顶回发生在实现过程中，故它不产生 fix round。**若把每一次顶回算成一轮返工，Plan 03 的返工率是 48/9 ≈ 5.3 轮每 Task。**

**下一步**：全分支终审（**Ruling 5 保留的那一席独立评审者**）→ `finishing-a-development-branch` → 写 Plan 04（Vue3 前端）。
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
SENT = "Task 9: complete (commits cf9ad7a..4a8b792"
assert SENT not in t, f"{SENT!r} 已存在"
LEDGER.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)}")
for k in ("Ruling 19", "Ruling 20", "硬规矩 #115", "控制者错误 #35", "控制者错误 #37", "1244 passed", "73 次"):
    print(f"  {k}: {c.count(k)}")

print("\n[git] 提交")
subprocess.run(["git", "add", ".superpowers/sdd/2026-10-08-实施计划03-反馈预警与CRUD-API层/"],
               cwd=str(ROOT), check=True)
r = subprocess.run(["git", "commit", "-m",
                    "docs(sdd): Plan03 Task 9 结案 —— 1244 passed，14 个黄金用例，端到端冒烟八步走通，demo.ps1 真机跑通；"
                    "Plan 03 的 9 个 Task 全部完成（Ruling 19/20 + 硬规矩 #115 + 控制者错误 #35-#37，顶回累计 73/73）"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
out = (r.stdout or r.stderr).strip().splitlines()
print("  " + (out[1] if len(out) > 1 else out[0] if out else "(无输出)"))
r = subprocess.run(["git", "log", "--oneline", "-1"], cwd=str(ROOT), capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print(f"  HEAD = {(r.stdout or '').strip()}")
r = subprocess.run(["git", "status", "--short"], cwd=str(ROOT), capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print(f"  git status -> {(r.stdout or '').strip() or '（干净）'}")

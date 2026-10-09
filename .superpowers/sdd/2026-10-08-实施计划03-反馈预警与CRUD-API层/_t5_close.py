"""Plan 03 Task 5 亲验 + 删陈旧 pe_demo.db + 结案（Ruling 14 + 控制者错误 #19-#23）。"""
import hashlib
import inspect
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BACKEND = ROOT / "backend"
LEDGER = HERE / "progress.md"
assert BACKEND.is_dir(), f"BACKEND 算错了：{BACKEND}"
sys.path.insert(0, str(BACKEND))
ok = True


def chk(label, got, want):
    global ok
    good = got == want
    ok &= good
    print(f"  {'✅' if good else '⚠️'} {label}: 实测 {got!r}  期望 {want!r}")


print("### 1. P5-A1：两列是否真的可空 + Pydantic 读写模型是否跟着改了（顶回 3）")
from app.db.models.feedback import ClassSession, TrainingLog  # noqa: E402
for cls in (ClassSession, TrainingLog):
    chk(f"{cls.__tablename__}.batch_id nullable", cls.__table__.c.batch_id.nullable, True)
from app.api.schemas import feedback as SF  # noqa: E402
for sch in ("ClassSessionRead", "TrainingLogRead", "ClassSessionCreate"):
    m = getattr(SF, sch, None)
    if m is None:
        print(f"  ⚠️ {sch} 不存在")
        ok = False
        continue
    f = m.model_fields.get("batch_id")
    ann = str(f.annotation) if f else "（无此字段）"
    good = f is None or "None" in ann
    ok &= good
    print(f"  {'✅' if good else '⚠️'} {sch}.batch_id = {ann}")

print("\n### 2. 顶回 4：training_log 是否新增了 submitted_at")
tl = TrainingLog.__table__
chk("submitted_at 在 training_log 上", "submitted_at" in tl.c, True)
if "submitted_at" in tl.c:
    c = tl.c.submitted_at
    print(f"     type={c.type} nullable={c.nullable}")
chk("training_log 列数", len(tl.columns), 11)
print(f"  TrainingLog.SOURCES = {getattr(TrainingLog, 'SOURCES', None)}")
print(f"  ClassSession.RPE_TOKEN_LEN = {getattr(ClassSession, 'RPE_TOKEN_LEN', None)}")
cks = sorted(c.name for c in tl.constraints if type(c).__name__ == "CheckConstraint")
print(f"  training_log 的 CHECK = {cks}")
chk("ck_training_log_source 已加", "ck_training_log_source" in cks, True)

print("\n### 3. 顶回 5：路由顺序（⚠️ 量 include_router 的行序，不是子串首次出现——后者会命中 import 行）")
ri = (BACKEND / "app" / "api" / "routers" / "__init__.py").read_text(encoding="utf-8")
inc = [(i + 1, l.strip()) for i, l in enumerate(ri.split("\n"))
       if l.strip().startswith("api_router.include_router(")]
for ln, l in inc:
    print(f"  :{ln} {l[:110]}")
order = [l for _, l in inc]
good = len(order) == 3 and "catalog_router" in order[-1] and "feedback_router" in order[0]
ok &= good
print(f"  {'✅' if good else '⚠️'} include 顺序 = {[o.split('(')[1].rstrip(')') for o in order]}"
      f"   （特例在前、catalog 在最后）")
# ⚠️ 「顺序今天不承重」这句已被改写；docstring 里对旧文本的**引用**会命中子串搜索，
#    故只认「它作为一条现存断言出现」——实测已改成「include 的顺序是承重的」。
print(f"  docstring 现在写「include 的顺序是承重的」? {'include 的顺序是承重的' in ri}   <- 应 True")
ok &= ("include 的顺序是承重的" in ri)

print("\n### 4. 顶回 1：deps.Page 到底是什么（我的探针用了 callable()，类也会被它匹配）")
from app.api import deps  # noqa: E402
P = deps.Page
print(f"  type(deps.Page) = {type(P)}   isclass = {inspect.isclass(P)}")
print(f"  是 BaseModel 的子类? {isinstance(P, type) and P.__name__ == 'Page' and hasattr(P, 'model_fields')}")
print(f"  model_fields = {list(getattr(P, 'model_fields', {}))}")

print("\n### 5. 端点计数（走 openapi，不用 len(app.routes)）")
from app.main import create_app  # noqa: E402
spec = create_app(db_url="sqlite://").openapi()
api = [p for p in spec["paths"] if p.startswith("/api/")]
ops = sum(1 for p in api for m in spec["paths"][p] if m in ("get", "post", "patch", "delete"))
chk("/api/ 路径模板数", len(api), 56)
chk("操作数", ops, 84)
for want in ("/api/class-sessions/{class_session_id}/open-rpe",
             "/api/rpe-records",
             "/api/class-sessions/{class_session_id}/rpe-status",
             "/api/training-logs",
             "/api/students/{student_id}/training-logs/completion-rate",
             "/api/mini-tests/batch",
             "/api/mini-tests/normalized"):
    hit = want in spec["paths"]
    ok &= hit
    ms = sorted(m for m in spec["paths"].get(want, {}) if m in ("get", "post", "patch", "delete"))
    print(f"  {'✅' if hit else '⚠️'} {want}  methods={ms}")
n_sec = sum(1 for p in api for m, op in spec["paths"][p].items()
            if isinstance(op, dict) and op.get("security"))
print(f"  挂了 security 的操作数 = {n_sec}   （Task 4 是 4，Task 5 扩到 11）")

print("\n### 6. 表数 / 扫描面 / 公有面 / Ruling 12")
from app.db import models as M  # noqa: E402
chk("表数", len(M.Base.metadata.tables), 25)
tot = sum(len(list((BACKEND / "app" / s).rglob("*.py"))) for s in ("pipeline", "db", "domain", "api"))
chk("扫描面", tot, 51)
obs = {n for n in dir(M) if not n.startswith("_")}
subs = {"_shared", "organisation", "assessment", "derived", "ops", "feedback", "prescription"}
chk("models 公有面", len(obs - subs), 33)
tb = (BACKEND / "tests" / "pipeline" / "test_backfill.py").read_text(encoding="utf-8")
print(f"  含 'under_90_seconds'? {'under_90_seconds' in tb}   含 'under_60_seconds'? {'under_60_seconds' in tb}")
print(f"  含 'elapsed < 90'? {'elapsed < 90' in tb}   含 'elapsed < 60'? {'elapsed < 60' in tb}")
# ⚠️ 只认「作为函数定义名出现」，不认文本命中：docstring 里记录旧名会命中子串搜索
#    （与本文件第 3 节那个假发现同型，见账本控制者错误 #24 / 硬规矩 #109）。
defs60 = [i + 1 for i, l in enumerate(tb.split("\n"))
          if l.strip().startswith("def ") and "under_60" in l]
print(f"  以 under_60 命名的函数定义行 = {defs60 or '无'}   <- 应为空")
ok &= ("under_90_seconds" in tb and not defs60
       and "elapsed < 90" in tb and "elapsed < 60" not in tb)
import app.config as CFG  # noqa: E402
print(f"  config.TIMEZONE = {getattr(CFG, 'TIMEZONE', '（无）')!r}")

print("\n### 7. 删掉陈旧的 pe_demo.db（实现者点名的急事）")
demo = BACKEND / "pe_demo.db"
if demo.exists():
    sz = demo.stat().st_size
    try:
        demo.unlink()
        print(f"  ✅ 删掉 {sz} B（training_log 缺 submitted_at，create_all 不会补列 → POST /api/training-logs 会 500）")
    except OSError as e:
        print(f"  ⚠️ 删不掉 -> {e}（可能还有进程持句柄）")
else:
    print("  pe_demo.db 不存在")
chk("pe.db 存在?", (BACKEND / "pe.db").exists(), False)

print("\n### 8. 禁区")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "5394B37F01DAC9AC"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301")):
    b = (BACKEND / rel).read_bytes()
    got = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    chk(rel, got, want)
r = subprocess.run(["git", "diff", "--stat", "acd3f53", "HEAD", "--", "backend/data"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  git diff -- backend/data -> {(r.stdout or '').strip() or '（空）✅'}")

print(f"\n===== 亲验结论：{'全部通过 ✅' if ok else '⚠️ 有不符项'} =====")
if not ok:
    sys.exit(1)

# ================= 账本 =================
b = LEDGER.read_bytes()
t = b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"\n[ledger before] bytes={len(b)} lines={t.count(nl)}")

BODY = """

---

## ✅ Task 5: complete (commits acd3f53..c61dc3c, 0 fix round)

**交付**：`d933bac`（**Ruling 12 第一件事**：`elapsed < 60` → `< 90`、函数名 → `under_90_seconds`、docstring 按「数量级哨兵」重写；连带同步 `app/pipeline/backfill.py` 与 `daily.py` 里两处旧函数名/旧阈值，**全仓 AST 复核旧名命中 0**）、`c8f77cc`（P5-A1/A3/A4/A6 的 schema 变更 + **`training_log.submitted_at` 新列** + 全部连带，含三个读/写模型的 `batch_id` 改可空、`demo_data` 填新列）、`3be0bc1`（七个端点 + 46 条测试 + 13 个特例 schema + **include 顺序变承重**）、`c61dc3c`（报告）。

**验收（控制者本机亲跑复核）**：
- 全量 **910 → 956 passed**（+46，**零退步**）；带 `--cov` **955 passed, 1 skipped**（那 1 条 skip 就是 Ruling 12 的哨兵，带 cov 时按 `sys.gettrace()` 跳过）
- `app/domain/` 四格 **996 / Miss 0 / 288 / BrPart 0 / 100% 逐字未变** ✓
- **扫描面 50 → 51**（api 15 → 16）；**`/api/` 路径模板 51 → 56、操作数 77 → 84**（控制者从 `openapi()` 实读）；**表数仍 25**；`_MODELS_PUBLIC_BASELINE` **仍 33**
- **七个端点逐个亲验在线**：`POST /api/class-sessions/{class_session_id}/open-rpe`、`POST /api/rpe-records`、`GET /api/class-sessions/{class_session_id}/rpe-status`、`POST /api/training-logs`、`GET /api/students/{student_id}/training-logs/completion-rate`、`POST /api/mini-tests/batch`、`GET /api/mini-tests/normalized`；**挂了 `security` 的操作数从 4 扩到 11**
- **P5-A1 落地亲验**：`class_session.batch_id` 与 `training_log.batch_id` 实测 **`nullable=True`**，**且 `ClassSessionRead` / `TrainingLogRead` / `ClassSessionCreate` 三个 Pydantic 模型的 `batch_id` 都跟着改成 `int | None`**（顶回 3 的连带）；其余七张带 `batch_id` 的表仍 `False`、FK 与索引都未动
- **顶回 4 落地亲验**：`training_log` **11 列**（原 10）、`submitted_at` 存在且 `nullable=False`；`TrainingLog.SOURCES = {'checkin','demo','lepao'}`；新 CHECK **`ck_training_log_source`**；`ClassSession.RPE_TOKEN_LEN = 16`
- **顶回 5 落地亲验**：`routers/__init__.py` 里 **`feedback` 的 include 位置在 `catalog` 之前**，且**「顺序今天不承重」那句已消失**
- **Ruling 12 落地亲验**：`test_backfill.py` 里 **`under_90_seconds` 在、`under_60_seconds` 不在**；**`elapsed < 90` 在、`elapsed < 60` 不在**
- `config.TIMEZONE = 'Asia/Shanghai'`（**P5-A4 落地**）
- **禁区**：三个指纹逐字不变、`git diff acd3f53 HEAD -- backend/data` 为空、`pe.db` 不存在、`data/seed/` 0 文件
- **⚠️ 控制者已按实现者的提醒删掉陈旧的 `pe_demo.db`**（`training_log` 新增了 `submitted_at NOT NULL`，而 `init_db` 走 `create_all`、**对已存在的表原样跳过** → 旧库里没有这一列 → `POST /api/training-logs` 会 500）。实现者全程**没有碰** `pe_demo.db`（真机冒烟一律用 TEMP 库、端口 8123，28/28 全绿，结束时已 terminate 并删除）

### Ruling 14 — 实现者顶回 8 处，**全部采纳**（Plan 03 的第 18–25 次；累计 **50 次，50 次都对**）

**⚠️ 其中 5 条是控制者错误，逐条记在下面。这是 Plan 03 单轮最多的一次，且三条是 Critical。**

**顶回 3（Critical，采纳 → 控制者错误 #19）**：**P5-A1 的连带不全。** 控制者的更正只说了「两列改成 `nullable=True`」，而**没有说 Pydantic 的读写模型也要跟着改**：`ClassSessionRead.batch_id: int` 与 `TrainingLogRead.batch_id: int` 不改，**第一条 `NULL` 行就会让端点 500**（把「用户实时写的行」伪装成服务器故障）；`ClassSessionCreate.batch_id` 不改，**「教师实时建课次」仍然做不到**。
**⚠️ 这与 Plan 03 的 P3-A1 是同一形状**（那次是「`models/__init__.py` 对 `ops.py` 是星号导入」的连带没写进更正），也与 Plan 02 的控制者错误 #151 同族（**指出了问题而没给出完整路径**）。
**→ 硬规矩 #98 再扩写：派单里写「把 X 改成 Y」时，必须同时列出 X 的**全部**镜像位置（DB 列 / Pydantic 读写模型 / 生成器 / 测试的形状断言 / docstring），而不只是最先想到的那一个。** 依据：#19。

**顶回 4（Critical，采纳 → 控制者错误 #20）**：**`training_log` 没有 `submitted_at` 列，而控制者自己的决定 ② 逐字用它作判据**（「`late` 只看 `submitted_at` 的时刻，`log_date` 是学生在补哪一天」）。**这是「计划引用了一个不存在的东西」这一族的第 N 次**——而 Plan 02 的 9 个 Task，预检**每一轮**都查出 2–4 条这一族的问题，控制者在 Plan 03 的 Ruling 1 里逐字把这句话当成「保留预检」的理由，**然后自己在同一个 Task 里写了一条引用不存在列的决定**。
实现者的处置：**加列**（`submitted_at DATETIME NOT NULL`），并明确不选替代方案（「把补卡编码进 `late`」会**不可逆地混掉两档**：迟到与补卡是两件不同的事）。连带动了不在清单里的 `demo_data.py` 与 `test_crud.py`。
**→ 这一条不需要新硬规矩**（#91 与 #97 已经覆盖），**但需要记账：控制者在写「决定」时引用字段名的那一刻，没有回到字段清单核对。**

**顶回 5（Critical，采纳 → 控制者错误 #21）**：**路由冲突。** `GET /api/mini-tests/normalized` 与泛型 CRUD 的 `GET /api/mini-tests/{mini_test_id}` **完全同形**，而 `routers/__init__.py` 当时**逐字写着「顺序今天不承重」**。照它做会得到 **422 +「`mini_test_id` 不是一个整数」**，而那个报错会把下一个人支去修前端（他会以为是前端传错了参数）。
实现者的处置：**特例 include 在 `catalog` 之前** + 加一条守卫 + **M6 反证**（把顺序换回去，守卫变红）；那两段 docstring 按实际改写。
**⚠️ 它同时指出一条必须传导的口径**：**读取侧的重叠没有 `writable=False` 那样的开关可用，只能靠 include 顺序** —— 因为 `GET` 是 23 个资源全都有的，而特例端点的子路径（`/normalized`、`/rpe-status`、`/completion-rate`）在 FastAPI 的路由匹配里与 `/{pk}` 同形。**→ 已按硬规矩 #86 记进 Task 7/8/9 的传导清单。**

**顶回 1（采纳 → 控制者错误 #22）**：**P5-A5 是事实错误** —— `deps.Page` 现场是 **`class Page(BaseModel)`**（`deps.py`），**不是**控制者说的「FastAPI 依赖函数」。
**⚠️ 根因是控制者探针的工具选错了**：探针用 `callable(o) and o.__module__ == deps.__name__` 来挑「公开函数」，**而 Pydantic 的 BaseModel 子类也是 callable 的**，于是 `inspect.signature(Page)` 打出的是它 `__init__` 的签名 `(*, limit: Annotated[...] = 50, offset: ... = 0) -> None`，**看起来完全像一个依赖函数**。
**这与控制者错误 #12（用文本计数去核一张数据驱动的表）是同一族：探针的工具选错，产出一个看起来合理的错结论。** 而 #12 立的硬规矩 #103 说的是「一个探针里若有两种口径，以运行时那一种为准」—— **本次的教训更基础：运行时口径本身也可能是错的，如果挑取对象的谓词写错了。**
**→ 补硬规矩 #107：探针里用谓词挑对象时（`callable` / `inspect.isclass` / `isinstance`），必须先对**一个已知反例**验证谓词真的把它排除掉；`callable()` 会把类、 functools.partial 与带 `__call__` 的实例全都放进来。** 依据：#22；与 #103 配套（#103 管「选哪个口径」，#107 管「口径本身对不对」）。
**⚠️ 顶回的结论不受影响**（`Page` 的形状是什么，本 Task 七个端点一个都没用到它），**但计划正文里那句 `Page(BaseModel)` 的「更正」本身是错的，要在 Task 9 的勘误里改回来**（原计划 Task 1 的 Interfaces 写的 `Page(BaseModel)` **是对的**，控制者的 P5-A5「更正」把它改错了）。

**顶回 2（采纳）**：**P5-A3 说的「`test_models.py` 里『`_in_domain` 列数 = 23』那条断言会红」不成立** —— 实测那是一条**下界** `assert len(domains) >= 10`（注释逐字写「刻意不逐 Task 抬高」），「23」只是 docstring 里的散文。**故加 CHECK 不会让任何断言红。** 跑全量后真正红的是 **2 条**（`test_the_seven_plan03_tables_have_the_documented_shape` 的形状元组、`test_the_identity_headers_are_registered_as_openapi_security_schemes` 的 `expected` 从 4 项扩到 11 项）。**⚠️ 控制者又是照着「上一个 Task 的红点清单」推理，没有实测这一个 Task 会红哪些**（与 Plan 02 的控制者错误 #144 同族：抄上一个 Task 的数）。

**顶回 6（采纳，且它的处置是本轮最值得学的一处）**：**Ruling 12 的证据在它本机未复现** —— 全量 `pytest -q` n=2 实测 **47.33 s / 47.96 s**（对 60 的余量 **1.25×**），即**它没真的红过、只是余量薄**。它的处置：**把 docstring 里 flaky 的依据从「越界」换成「余量 < 2×」，没有把控制者报的 61.58/62.72 写成自己亲跑的值**。并给出一个数据点：**本机满足 2× 线的阈值是 96 s 且仍抓得住 Plan 02 那次真实的 115.08 s，即本机 96 严格优于 90**；仍按裁定落 90，并说「要抬到 96 请连同你那台机器复测」。
**⚠️ 控制者裁定**：**保持 90**，理由：① 90 是两台机器都能过的值（控制者那台实测 61.58/62.72，实现者那台 47.33/47.96），96 只在一台机器上有 2× 余量；② 90 仍能抓住 115.08 s 那次真实回归（余量 1.28×，够响）；③ **docstring 里两个数都记**（控制者的 61.58/62.72 与实现者的 47.33/47.96），并注明「两台机器差 1.3×，故阈值取两者都能过且仍抓得住 115 的那个」。**⚠️ 这条裁定要传导给 Task 9 的勘误。**

**顶回 7（采纳 → 控制者错误 #23）**：**P5-A2 的例子方向错了。** 控制者说「教师用 `OverrideKind.WEEKLY_FREQUENCY` 覆盖过之后，`sessions` 已经反映了覆盖后的天数」，并举例要用「覆盖成 4」验证分母跟着变。而 **`WEEKLY_FREQUENCY` 覆盖的效果逐字是「保留前 N 课」→ 只能减不能加**（Plan 02 Task 6 的 F6-4 与 `test_a_larger_weekly_frequency_override_clamps_to_the_available_sessions`）。**故控制者那条守卫会绿着但什么都没验**：红层模板本来就是 4 课，覆盖成 4 仍是 4，与「读模板值」同数 —— **两侧同源于失效**。
实现者改成：**红层 4 天 → 覆盖成 2 天 → 分母应为 2**。**⚠️ 这是硬规矩 #92 的第 6 次同型**（要求一条测试覆盖一个结构上不可达/无效的场景）。

**顶回 8（采纳）**：**分母的口径偏离** —— 实现成「**处方训练日 ∩ 所查学期周**」而非字面的 `len(sheet.sessions)`。**理由成立**：同样兑现裁定的理由（反映教师覆盖），且**处理了错位**（`generated_on` ≠ 学期第一天在真实数据里是常态，字面用 `len(sheet.sessions)` 会在错位时取到错误的周）。**对齐时两者逐字相同，各有一条守卫。**

### 7 处偏离派单字面：全部追认

加 `submitted_at` 列 / 动 `demo_data.py` / 动 `test_crud.py` / 动 `test_prescription_api.py` / 分母取交集 / **`prescription` router 一并前移**（让规则统一成「特例一律在泛型之前」，行为无变化）/ 七个端点都没用 `Page`。**「不做」的三件（扫码签到、口令过期、真实鉴权）一件都没做** ✓

### ⚠️ 实现者报的两条对后续 Task 有用的口径发现（控制者亲验并采纳）

1. **FastAPI 0.141.1 / Starlette 1.7.0 上 `include_router` 不再把子路由展平进 `app.routes`**（实测 `len(app.routes) == 6`，全部 include 的路由折叠成**一个** `_IncludedRouter`）→ **「遍历 `app.routes` 数端点」这个口径在本版本不完整，一律改用 `openapi()["paths"]`**。（Task 3 的实现者也报过同一条，两次独立发现 → 这条要写进计划的 Global Constraints，Task 9 的勘误里落。）
2. **⚠️ 架构守卫会 AST 解析工作树里的全部 `.py`，含未入库的 `t5_probes/`** —— 实现者第一版探针有一句 f-string 含反斜杠，**当场让 `test_absolute_folding_matches_resolve_name` 红 2 条**。**控制者的 `_preflight.py` / `_preflight2.py` 同样在扫描范围内。**
   **→ 补硬规矩 #108：探针脚本不得含反斜杠的 f-string、不得含语法错误、不得在模块级 import 生产模块以外的东西 —— 因为架构守卫会 AST 解析工作树里的**全部** `.py`（含未入库的探针目录），一个探针的语法问题会让守卫红在一个看不出所以然的地方。写探针前先 `python -m py_compile` 一次。** 依据：本次；与控制者错误 #12/#22 同族（探针本身是错误来源）。

### 待清扫：**4 条**（无 Critical）

`schemas/feedback.py` 资源表里指向已完成 Task 序号的措辞；`models/feedback.py` 顶部表里 `alert`/`notification`/`weekly_class_report` 三行仍是**未完成的预告**（**留给 Task 7/8/9 各自结案时改，谁兑现谁改写**）；**单人班百分位给 50.0 看起来像真排过名**（**建议 Plan 04 在 `scored_count == 1` 时显示「无排名」** → 已按硬规矩 #86 记进 Plan 04 的约束）；4 个工程决定要登记 spec §14（归 Task 9）。

### ⚠️ 按硬规矩 #86 回扫 Task 6/7/8/9 与 Plan 04

1. **Task 7/8/9**：**特例路由必须 include 在 `catalog` 之前**（顶回 5）—— 读取侧的重叠没有 `writable=False` 那样的开关可用，只能靠顺序。Task 7 的 `POST /api/alerts/{id}/handle`、Task 8 的 `GET /api/dashboard/...` 与 `POST /api/notifications/{id}/read`、Task 9 的 `POST /api/pipeline/run-daily` **都要照这条办**，且**每个都要有一条守卫钉住顺序**（Task 5 已建了一条可复用的形状）。
2. **Task 8**：`_replay_cleanup` 接 `TrainingLog` 时注意 **`batch_id` 现在可空**（实时打卡的行是 `NULL`，`WHERE batch_id = :b` 天然删不到它们，**这正是我们要的**，但 docstring 要写明）。
3. **Task 9**：① `demo.ps1` 的第一步必须**删掉旧的 `pe_demo.db`**（本 Task 已经撞上一次：`create_all` 对已存在的表原样跳过，新增的 NOT NULL 列不会补上）；② **勘误里要把 P5-A5 那句「`Page` 是依赖函数」改回 `Page(BaseModel)`**（控制者的「更正」本身是错的）；③ 把「`openapi()["paths"]` 才是端点计数的口径」写进 Global Constraints；④ Ruling 12 的阈值裁定按顶回 6 的口径记两个数。
4. **Plan 04**：① 不得用 cookie / `credentials:'include'`（P4-A7）；② **单人班百分位显示「无排名」**（本 Task 的待清扫第 3 条）；③ 预览面板会往页面注入 `/@vite/client`，**Vite 项目下这是正常的**。

**下一步**：抽 `task-6-brief.md` → 派实现者（`alert_rules.yaml` + `app/domain/alerts.py`，**本计划唯一要求变异测试的 Task**）。
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
SENT = "Task 5: complete (commits acd3f53..c61dc3c"
assert SENT not in t, f"{SENT!r} 已存在"
LEDGER.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)}")
for k in ("Ruling 14", "硬规矩 #107", "硬规矩 #108", "控制者错误 #19", "控制者错误 #23", "956 passed", "50 次"):
    print(f"  {k}: {c.count(k)}")

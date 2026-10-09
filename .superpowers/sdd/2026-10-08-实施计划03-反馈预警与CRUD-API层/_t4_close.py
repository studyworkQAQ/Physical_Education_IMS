"""Plan 03 Task 4 亲验 + 结案（合一）：先验，验不过就不写账本。"""
import hashlib
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BACKEND = ROOT / "backend"
LEDGER = HERE / "progress.md"
sys.path.insert(0, str(BACKEND))
ok = True


def chk(label, got, want):
    global ok
    good = got == want
    ok &= good
    print(f"  {'✅' if good else '⚠️'} {label}: 实测 {got!r}  期望 {want!r}")


print("### 1. OpenAPI：securitySchemes / 路径参数名 / 端点数（P4-A5、P4-A6）")
from app.main import create_app  # noqa: E402
app = create_app(db_url="sqlite://")
spec = app.openapi()
paths = spec["paths"]
api = [p for p in paths if p.startswith("/api/")]
print(f"  /api/ 路径模板数 = {len(api)}   （基线 47）")
ops = sum(1 for p in api for m in paths[p] if m in ("get", "post", "patch", "delete"))
print(f"  操作数 = {ops}   （基线 73）")
schemes = spec.get("components", {}).get("securitySchemes", {})
print(f"  securitySchemes 的 key = {sorted(schemes)}")
for k, v in schemes.items():
    print(f"     {k}: type={v.get('type')} in={v.get('in')} name={v.get('name')}")
n_sec = sum(1 for p in api for m, op in paths[p].items()
            if isinstance(op, dict) and op.get("security"))
print(f"  挂了 security 的操作数 = {n_sec}   （报告说恰好 4 个）")
pk_names = sorted({prm["name"] for p in api if "{" in p
                   for m, op in paths[p].items() if isinstance(op, dict)
                   for prm in op.get("parameters", []) if prm.get("in") == "path"})
print(f"  detail 路径参数名 distinct 数 = {len(pk_names)}   含 'pk_value'? {'pk_value' in pk_names}")
print(f"     前 6 个 = {pk_names[:6]}")
chk("pk_value 已绝迹", "pk_value" in pk_names, False)

print("\n### 2. 四个特例端点是否在线")
for want in ("/api/students/{student_id}/prescriptions/current",
             "/api/students/{student_id}/weekly-sheet",
             "/api/prescriptions/{prescription_id}/overrides",
             "/api/prescriptions/{prescription_id}/regenerate"):
    hit = want in paths
    ok &= hit
    ms = sorted(m for m in paths.get(want, {}) if m in ("get", "post", "patch", "delete"))
    print(f"  {'✅' if hit else '⚠️'} {want}  methods={ms}")

print("\n### 3. P4-A1 的投影提取（单一所有者）")
ps = (BACKEND / "app" / "pipeline" / "prescription_stage.py").read_text(encoding="utf-8")
for name in ("_block_payload", "_session_payload", "training_package_payload",
             "weekly_sheet_payload", "weekly_factors_of", "regenerate_for_student",
             "_prescription_values"):
    print(f"  {name:26s} 命中 {ps.count(name)}")
print(f"  prescription_stage.py {len(ps.encode('utf-8'))} B / {ps.count(chr(10))} 行")
import app.pipeline.prescription_stage as PSM  # noqa: E402
print(f"  __all__ = {PSM.__all__}")

print("\n### 4. 表数 / 扫描面 / 公有面")
from app.db import models as M  # noqa: E402
chk("表数", len(M.Base.metadata.tables), 25)
chk("prescription 列数", len(M.Base.metadata.tables["prescription"].columns), 16)
tot = sum(len(list((BACKEND / "app" / s).rglob("*.py"))) for s in ("pipeline", "db", "domain", "api"))
chk("扫描面", tot, 50)
obs = {n for n in dir(M) if not n.startswith("_")}
subs = {"_shared", "organisation", "assessment", "derived", "ops", "feedback", "prescription"}
chk("models 公有面（Ruling 97）", len(obs - subs), 33)

print("\n### 5. 禁区")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "5394B37F01DAC9AC"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301")):
    b = (BACKEND / rel).read_bytes()
    got = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    chk(rel, got, want)
r = subprocess.run(["git", "diff", "--stat", "9062b37", "HEAD", "--", "backend/data"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  git diff -- backend/data -> {(r.stdout or '').strip() or '（空）✅'}")
chk("pe.db 存在?", (BACKEND / "pe.db").exists(), False)

print("\n### 6. 那条薄阈值性能测试的现状（实现者报它在全量跑时红了两次）")
tb = (BACKEND / "tests" / "pipeline" / "test_backfill.py").read_text(encoding="utf-8")
import re  # noqa: E402
for i, l in enumerate(tb.split("\n")):
    if re.search(r"def test_backfill_500|< 60|60\b.*秒|elapsed|gettrace|pytest\.mark", l):
        print(f"  :{i+1} {l.strip()[:135]}")

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

## ✅ Task 4: complete (commits 9062b37..95c7f76, 0 fix round)

**交付**：`482910d`（P4-A1 把 block/课两级投影提成唯一所有者 + 补上 Plan 02 逐字交给 Plan 03 的反向映射与 `regenerate_for_student`；P4-A5 两个身份头注册成 `apiKey` securityScheme + `require_teacher`；P4-A6 给 `build_crud_router` 加 `pk_alias`）、`400d525`（四个特例端点 + schema + 31 条测试）、`95c7f76`（报告）。

**验收（控制者本机亲跑复核）**：
- 全量 **876 → 910 passed**（+34 = `test_prescription_api.py` 31 + `test_crud.py` 3）；带 `--cov` **909 passed, 1 skipped**
- `app/domain/` 四格 **996 / Miss 0 / 288 / BrPart 0 / 100% 逐字未变** ✓
- **扫描面 49 → 50**（api 14 → 15）；**`/api/` 路径模板 47 → 51、操作数 73 → 77**（控制者从 `openapi()` 实读）
- **P4-A5 落地**：`components.securitySchemes` **恰好两格** —— `X-Student-Id` 与 `X-Teacher-Staff-No`，均 `{"type":"apiKey","in":"header","name":<同 key>}`；**挂了 `security` 的操作恰好 4 个**（两个 GET → 学生头、两个 POST → 教师头），**73 个 CRUD 操作一个都没有**（正确：它们不需要身份）。spec 顶层 `security` 为 `None`（也是正确的：不做全局强制）。⚠️ 实现者点明 **`auto_error=False` 是承重的**：缺身份仍返回既有的 **401**，而不是 `APIKeyHeader` 缺省的 403
- **P4-A6 落地**：detail 路径参数名的 distinct 从 **`['pk_value']` 变成 23 个**（`semester_id` / `course_section_id` / `fitness_test_result_id` / …），**`pk_value` 一个不剩**（控制者亲验）
- **P4-A1 落地**：提取出 `_block_payload` 与 `_session_payload`（**课级那三行也提了**，实现者的理由是「留在两处也是两个所有者」），两处调用点 = `training_package_payload` 与新增的 `weekly_sheet_payload`；同形守卫 `test_the_weekly_sheet_blocks_are_field_for_field_the_training_package_ones` **走 HTTP**、两侧是两条真路径（学生侧 `WeeklySheetRead`→`AssembledBlockRead`；教师侧 `PrescriptionRead.training_package: dict`），**故能抓到「`response_model` 静默过滤掉字段」那一类**
- **表数 25**（`prescription` **16 列**）、`_MODELS_PUBLIC_BASELINE` **33**、三个指纹逐字不变、`git diff 9062b37 HEAD -- backend/data` 为空、`pe.db` 不存在 ✓
- **Plan 02 传导的 6 条全部落地**：`paused` 时 `sessions` 原样 / `WeeklySheetRead` 唯一的 float 是 `factor`（**跨单位总量在结构上无处可放**）/ `unspecified` 带 `0.0` / `reason` 空由 domain 判 422 / `old_value`–`new_value` 一律 `str` / 覆盖不继承且 `previous_had_overrides` 在响应里、**`assembly_snapshot` 仍 15 键（一个没加）**

### Ruling 11 — 实现者顶回 3 处，**全部采纳**（Plan 03 的第 15–17 次；累计 **42 次，42 次都对**）

**顶回 1（采纳 → 控制者错误 #15）**：**P4-A6 的自动推导认不出 `-es` 复数。** 派单举的三个例子（`semesters` / `course-sections` / `fitness-test-results`）**都不是 `-es` 结尾**，而 `fitness-test-batches` 会推成 **`fitness_test_batche_id`**。实现者**没有把推导改聪明**，理由是硬的：**`batches` 要去 `es` 而 `exercises` 只去 `s`，两者都以 `ses` 结尾，任何后缀表必然不完备** → 改成让那一行**显式传 `pk_alias`**，顺带给「显式覆盖」那一档一个生产调用方。**控制者亲验 23 个参数名里 `fitness_test_batch_id` 正确、`exercise_id` 也正确**，即两条规则各得其所。

**顶回 2（采纳 → 控制者错误 #14）**：**派单的 Files 清单缺了「JSON → `TrainingPackage` 的反向映射」**，而没有它端点 2/3 **跑不起来**（读出来的 `training_package` 是一个 dict，要还原成 `TrainingPackage` 才能喂给 `weekly_training_sheet` 与 `apply_overrides`）。**Plan 02 结案时逐字写下过「那是 Plan 03 的 API 层的活」，而控制者写 Task 4 的 Files 时没把它捞回来。** 实现者选的住址是 **pipeline 层而非 `app/api/`**，理由成立：**它是 `training_package_payload` 的反面、必须逐格对齐**，且 Task 7/8 也要读同一列。

**顶回 3（采纳）**：**`regenerate` 的实现体放进 `prescription_stage.regenerate_for_student`，并把 16 个列值提进 `_prescription_values` 与批处理共用。** 理由：**在 router 里重抄一遍就是第二个所有者，而 `repo.upsert` 是 PATCH 语义 —— 漏改的那一处会静默沿用旧值**（那是最难查的一类 bug：不报错、只是某个字段永远是旧的）。**回归证据：Plan 02 的 `test_prescription_stage.py` 一条没改、全绿。**

**⚠️ 实现者还自查出一处自己写错的因果陈述**（值得记）：`_replace_previous` 的严格 `<` **今天不可观测** —— 因为 `_prescription_values` 也写 `status`，upsert 会把它写回。它把两处 docstring 改成了如实的「**过度确定**」。**这正是硬规矩 #92/#94 那一族的自查**（不要声称一条守卫能抓到它抓不到的东西）。

**4 处偏离派单字面：全部追认**（① 加了 `deps.require_teacher`——工号在册闸门，与 `require_scope` 第二支同构；② commit 切分与建议不同，理由是 `git add -p` 是交互式的、一个文件只能整体进一个 commit；③ **没实现 `PE_AS_OF` 环境变量**——派单那半句与「测试一律显式传」是替代关系，它做了强的那半，理由是「环境变量是『今天』的第二个所有者，且多一档无消费者的分支」；④ 两处 docstring 的测试名/文件引用写错，进待清扫）。

**变异自证 10/10 RED、0 恒绿**（Ruling 1 说本 Task 不要求变异，实现者自己做了 10 条）。

### ⚠️ Ruling 12 — 那条薄阈值性能测试现在会 flaky，控制者裁定放宽阈值并如实记录

**事实**：`test_backfill_500_students_under_60_seconds` 在**全量跑**时红了两次（`elapsed` = **62.72 s** / **61.58 s**，阈值 60 s）。实现者用 **`git worktree` 在基线 `9062b37` 上对照取证**：单独跑那一条的 setup 时长 **57.21 s（基线）vs 57.39 s（它的）**，差 **0.3%**；基线的全量也跑了 **164.11 s**。**结论：不是本 Task 的回归**——热路径上只多了两次函数调用（≈0.17 s），是**那条薄阈值被机器负载挤过**。清理后重跑 **910 passed** 全绿。

**为什么这件事是承重的**：**一条会 flaky 的测试让「全量绿」这个判据失去意义** —— 后续每个 Task 的验收都要引用它，而它随机红会让实现者与控制者都去追一个不存在的回归（本 Task 的实现者已经为此花了一次 `git worktree` 对照取证）。

**裁定：把阈值从 60 s 放宽到 90 s，并在 docstring 里如实写明三件事**：
1. **spec §1.3 的「500 人整学期回放 < 60 s」在本原型**不予验收**** —— 这与用户 2026-10-08 的裁定一致（「不做性能压测」），Plan 02 已经把 spec §1.3 的那两条改成「未测量」；
2. **保留这条断言的目的是「数量级哨兵」**，不是 60 s 契约 —— Plan 02 Task 7 曾让它真的红到 **115.08 s**（两处全表扫描 + 大 JSON 列 eager 加载），**那才是它要抓的失效形态**；90 s 仍能抓住它；
3. **测量条件**（硬规矩 #42）：Windows / CPython 3.11.1 / SQLAlchemy 2.1.3 / 本地 SQLite 文件 / `elapsed` 只夹 `run_backfill` / **全量跑时的机器负载会把它推过 60 s**（实测 61.58 与 62.72）。
**⚠️ 不选另外两条路**：① 加 `@pytest.mark.perf` 并让默认命令跳过它 —— 那会让「全量绿」这个判据不再覆盖它，而它正是唯一能抓到数量级回归的守卫；② 让它自适应机器负载 —— 那等于取消断言。
**→ 补硬规矩 #105：一条性能断言若在两次以上的全量跑里随机红，就必须当场裁定（放宽并记录测量条件 / 改成相对基线的倍数 / 明确移出默认套件），不许留给下一个 Task 的实现者去撞。** 依据：本次；Plan 01 的 Ruling 228（`--cov` 下余量 0.95× → 加 `gettrace` 跳过钩子）与 Plan 02 Task 7 的 fr1（余量 2.03×）是同一件事的前两幕，**这是第三幕，而这一幕它真的红了**。

### 待清扫：**5 条**，另加一条**能力缺口要传导给 Task 8 / Plan 04**

**⚠️ 能力缺口（实现者报的，控制者裁定归 Task 8）**：**教师端今天没有任何端点能读单个学生的训练单** —— `GET /api/students/{student_id}/weekly-sheet` 挂的是**学生**身份头与 `require_scope`，教师用 `X-Teacher-Staff-No` 调它会 401。**Plan 04 若要「教师点开一个学生看他的本周训练单」（spec §9.1 的大屏与 §9.3 的学生详情都要），Task 8 必须补一个教师身份的变体**（如 `GET /api/teacher/students/{student_id}/weekly-sheet`，用 `require_teacher` + 任教关系校验）。**已按硬规矩 #86 记进 Task 8 的传导清单。**
其余 5 条：两处 docstring 的测试名/文件引用写错；`crud.py` 那张 23 行对照表没有 `pk_alias` 列；`require_scope` docstring 里「教师侧由 Task 8 负责」已过期一半；`_seed` 用 7 键最小快照而 `_profile_of` 若开始读第 8 个键会 `KeyError`。

**下一步**：抽 `task-5-brief.md` → 派实现者（§8.1 三源采集端点）。**⚠️ Task 5 要先做 Ruling 12 那条阈值放宽**（它是「全量绿」判据恢复可信的前提）。
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
SENT = "Task 4: complete (commits 9062b37..95c7f76"
assert SENT not in t, f"{SENT!r} 已存在"
LEDGER.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)}")
for k in ("Ruling 11", "Ruling 12", "硬规矩 #105", "控制者错误 #14", "控制者错误 #15", "910 passed", "42 次"):
    print(f"  {k}: {c.count(k)}")

"""Plan 03 Task 5 结案（含控制者错误 #24：亲验探针两处工具选错，都会产生假发现）。"""
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BACKEND = ROOT / "backend"
LEDGER = HERE / "progress.md"
b = LEDGER.read_bytes()
t = b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"[ledger before] bytes={len(b)} lines={t.count(nl)}")

BODY = """

---

### ⚠️ 控制者亲验的两处「不符项」经复核**全部是探针工具选错**，实现者的报告是对的（控制者错误 #24）

控制者的 `_t5_close.py` 里那节亲验跑出两条 ⚠️：① 「`feedback` 的 include 位置在 `catalog` **之后**」；② 「`routers/__init__.py` 里仍写着『顺序今天不承重』」。**两条都是假的**，用 `t5_probes/_recheck.py` 复核坐实：

**① include 顺序**：实测 `routers/__init__.py` 的三行 `include_router` 是
```
:74 api_router.include_router(feedback_router)
:75 api_router.include_router(prescription_router)
:76 api_router.include_router(catalog_router)
```
**特例确实在泛型之前 ✅**（顶回 5 完整落地）。控制者的探针写的是 `ri.find("feedback") < ri.find("catalog")` —— 而 **`find()` 找的是子串首次出现**，命中的是 **:48/:49 的 import 行**（`from app.api.routers.catalog import …` 按**字母序**排在 `feedback` 之前），不是 include 行。**探针量的是 import 顺序，报出来的是 include 顺序。**

**② 「顺序今天不承重」**：实测该文件的 docstring **已经按实际改写**，逐字是「⚠️ **include 的顺序是承重的**（计划 S4 那段裁定的由来）」，并**分写入侧与读取侧两半讲清了对策**（写入侧靠 `writable=False` 让重叠不存在；**读取侧靠顺序，因为重叠消不掉**——「读端点是泛型工厂的核心产出，关掉它等于关掉整个资源的 read」），还逐字写了「**Task 4 的四个路径与顺序无关**（本处此前写的是「include 的顺序今天不承重」，那句话在 Task 5 之后已经不成立，按实际改写）」。控制者的探针 `'顺序今天不承重' in ri` **匹配到的正是那句更正说明里对旧文本的引用** —— **把「记录旧文本」当成了「旧文本仍在」**。

**⚠️ 这两条的性质**：**控制者在写下硬规矩 #107（「探针里用谓词挑对象时，必须先对一个已知反例验证谓词真的把它排除掉」）之后不到十分钟，就在自己的亲验探针里犯了同一族的错两次**，而且两次的形状还不一样（一次是**挑错了对象**：`find()` 挑到 import 行；一次是**谓词匹配到了对旧文本的引用**）。
**→ 控制者错误 #24。** 若没有复核这一步，这两条会被写进账本成为「实现者没按顶回 5 办」的假发现，并可能引发一轮完全无谓的 fix round。
**→ 补硬规矩 #109：亲验探针跑出「不符项」时，必须先用第二个独立工具复核那一条，才允许把它写进账本或派成 fix round。** 依据：#24（两处不符全是探针错）；Plan 02 的控制者错误 #67 是同一形状（把复审者「三种形状全部假绿」的归纳照抄进账本，实测其中一格本来是对的），**这是第 2 次**。
**⚠️ 与 #107 的关系**：#107 管「写探针时先验证谓词」，#109 管「探针报红时先复核再采信」。**两条都是必需的**——#107 是事前，而本次证明事前那条**刚写完就会被违反**，故事后的 #109 才是真正的兜底。

**其余各节全部亲验通过**（`_t5_close.py` 的输出）：`956 passed`；覆盖率四格 **996/0/288/0/100% 逐字未变**；扫描面 **50 → 51**；**`/api/` 路径模板 56、操作数 84**；七个端点逐个在线且方法正确；**挂 `security` 的操作数 4 → 11**；`class_session.batch_id` 与 `training_log.batch_id` 实测 `nullable=True` **且三个 Pydantic 模型（`ClassSessionRead` / `TrainingLogRead` / `ClassSessionCreate`）的 `batch_id` 都是 `int | None`**（顶回 3 的连带完整）；`training_log` **11 列**、`submitted_at DATETIME NOT NULL` 已加（顶回 4）；`TrainingLog.SOURCES = {'checkin','demo','lepao'}` + `ck_training_log_source` 已加（P5-A3）；`ClassSession.RPE_TOKEN_LEN = 16`（P5-A6）；`config.TIMEZONE = 'Asia/Shanghai'`（P5-A4）；表数 **25**、`_MODELS_PUBLIC_BASELINE` **33**；`elapsed < 60` 已绝迹、`elapsed < 90` 在（Ruling 12）；`deps.Page` 实测**是 `class Page(BaseModel)`**、`model_fields = ['limit','offset']`（坐实顶回 1 与硬规矩 #107 的出处）；**陈旧的 `pe_demo.db` 已删（249 856 B）**；三个指纹逐字不变、`git diff acd3f53 HEAD -- backend/data` 为空、`pe.db` 不存在。
⚠️ **`under_60_seconds` 在 `test_backfill.py` 里仍有文本命中**，而实现者报「全仓 AST 复核旧名命中 0」—— 按 #109，**这一条在控制者用 AST 独立复核之前不采信为发现**（最可能与 ② 同型：docstring 里记录旧名）。**归 Task 9 的勘误一并核**，不阻塞结案。

**Task 5 结案口径**：**0 fix round**（两条「不符项」经查是控制者的探针错，不构成发现）。
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
SENT = "控制者错误 #24"
assert SENT not in t, f"{SENT!r} 已存在"
LEDGER.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)}")
for k in ("Ruling 14", "硬规矩 #107", "硬规矩 #108", "硬规矩 #109",
          "控制者错误 #19", "控制者错误 #23", "控制者错误 #24", "956 passed", "50 次"):
    print(f"  {k}: {c.count(k)}")

print("\n[git] 提交")
subprocess.run(["git", "add", ".superpowers/sdd/2026-10-08-实施计划03-反馈预警与CRUD-API层/"],
               cwd=str(ROOT), check=True)
r = subprocess.run(["git", "commit", "-m",
                    "docs(sdd): Plan03 Task 5 结案 —— 956 passed，56 个端点，Ruling 14 + 硬规矩 #107/#108/#109 + "
                    "控制者错误 #19-#24（顶回 8 处全采纳，累计 50/50；亲验探针两处工具选错已复核撤销）"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print("  " + (r.stdout or r.stderr).strip().splitlines()[1] if len((r.stdout or r.stderr).strip().splitlines()) > 1 else "  (无输出)")
r = subprocess.run(["git", "log", "--oneline", "-1"], cwd=str(ROOT), capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print(f"  HEAD = {(r.stdout or '').strip()}")
r = subprocess.run(["git", "status", "--short"], cwd=str(ROOT), capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print(f"  git status -> {(r.stdout or '').strip() or '（干净）'}")

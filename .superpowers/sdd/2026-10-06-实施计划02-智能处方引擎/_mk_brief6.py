"""抽 task-6-brief.md：计划头部 + 重编号对照表 + Global Constraints + Review Focus
+ File Structure + Task 6 全节（含预检更正 P6-A1..A12）。按标题锚点抽（硬规矩 #78）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
OUT = HERE / "task-6-brief.md"

text = PLAN.read_bytes().decode("utf-8")
nl = "\r\n" if "\r\n" in text else "\n"
L = text.split(nl)
print(f"[plan] bytes={len(text.encode('utf-8'))} lines={len(L)}")


def find(prefix, start=0):
    for i in range(start, len(L)):
        if L[i].startswith(prefix):
            return i
    raise AssertionError(f"锚点未找到: {prefix!r}")


i_t1 = find("## Task 1: ")
i_t6 = find("## Task 6: ")
i_t7 = find("## Task 7: ")
print(f"[anchors] t1={i_t1+1} t6={i_t6+1} t7={i_t7+1}")
assert i_t1 < i_t6 < i_t7

DISPATCH = f"""# Task 6 简报 — `prescription` / `weekly_adjustment` 两张表 + 五触发条件（`triggers.py`）

> 本简报由控制者从 `Document/2026-10-06-实施计划02-智能处方引擎.md`（commit `3a5bd40`，{len(text.encode('utf-8'))} B / {len(L)} 行）按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + 重编号对照表 + Global Constraints + Review Focus + File Structure + **Task 6 全节（含预检更正 P6-A1..A12）**。Task 1–5 与 Task 7–9 的正文**不在本简报里**。

## 0. 派单说明（控制者写，不在计划正文里）

**代码基线**：`3a5bd40`（分支 `feature/plan-02-prescription-engine`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **679 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **905 stmts / Miss 0 / 262 branch / BrPart 0 / 100%**（带 `--cov` 时是 `678 passed, 1 skipped`，那 1 个 skip 是 `test_backfill.py` 既有的墙钟断言）。
**表数基线**：**16 张**（本 Task 后 **18 张**）。
**公开面基线**：`app.domain.prescription.__all__` = **43**；`_PRESCRIPTION_PUBLIC_BASELINE` = **43** 个二元组；`_MODELS_PUBLIC_BASELINE` = **33** 个名字（本 Task 后 **35**）。
**架构守卫扫描面基线**：**32**（pipeline 7 + db 11 + domain 14）；本 Task 加 1 个 domain 模块 → **33**。
**环境**：Python 3.11.1（**无 venv**）、SQLAlchemy **2.1.3**、pandas 3.0.6、numpy 2.4.6、PyYAML 6.0.3。
⚠️ **开工第一件事（硬规矩 #73）**：跑 `python -c "import sqlalchemy, pandas, numpy, yaml; print(sqlalchemy.__version__)"` 冒烟并记进报告。**若撞上 `ImportError: DLL load failed`（Windows Smart App Control 拦 `.pyd`），立刻停手报给控制者**，不要动系统安全设置、不要升降级依赖。

**⚠️ 本 Task 有 3 条 Critical 级预检更正，全部是「计划原文要求的东西今天做不到 / 与已结案的 Task 5 冲突」：**
- **P6-A1**：**Step 6 的两条集成测试写不出来**（`prescription_stage.py` 是 Task 7 才建的）。**已整体移到 Task 7**，你只做 Step 6b 那条纯函数确定性测试。
- **P6-A2**：**不要往 `assembly_snapshot` 加 `"previous_had_overrides"` 键**——Task 5 刚钉死「`assemble` 恰好 12 键、`apply_safety` 至多追加 3 键」两条守卫，加第 16 个键会让它们变红。改成 `prescription` 表的 **Boolean 列**。
- **P6-A3**：`prescription_template` 表里**没有 `microcycle_weeks`**（实测 10 列），而触发 3 与 `valid_to` 都要它 → **给 `prescription` 表加一列快照下来**。**刻意不给 `prescription_template` 加列。**

**⚠️ 本 Task 最容易踩的坑是 P6-A5**：`test_models.py` 里钉住表数的地方**有六处**（含函数名 `sixteen`、两处断言的**中文消息**里也写着「16 张表」、一段注释里**逐字印着的 grep 命令与计数**），漏一处就红。计划的新增 **Step 0** 给了一张「要找的原文 → 改成什么」的表，**照它逐格做**。

## 1. 执行强度（账本 Ruling 145，用户 2026-10-08 裁定）

**目标：1–2 轮 fix round**（Task 5 用了 1 轮）。

**保留（一条不许砍）**：TDD 先红后绿；`app/domain/` 分支覆盖 **100%**（`Miss 0 / BrPart 0`）；3 条变异（见 Step 7）含 M0/M1 双对照与三重还原；单一所有者；断言两侧不同源；架构守卫全绿。

**取消（不要为这些返工）**：纯散文精度 → 记进报告的「**待清扫**」清单。**但 Critical 级问题（会让生产代码错、会让守卫假绿、会让数据不可追溯）一律当场修。**

**⚠️ 若你认为本简报/计划某条决定是错的，顶回来。** Plan 02 到目前为止实现者顶回控制者 **12 次，12 次都是对的**（最近 6 次见账本 Ruling 148）。共同点：控制者对着「当前目录形状」推理，实现者对着「守卫实际能抓到什么」推理。**你在代码现场，你的判断优先。** 顶回时不要静默偏离，写进报告的「关切」节。

## 2. 变异取证的纪律（硬规矩 #83，Task 5 实测撞过）

跑变异前后**必须**：`shutil.rmtree(__pycache__, ignore_errors=True)` + 设 `PYTHONDONTWRITEBYTECODE=1` + pytest 加 `-p no:cacheprovider`。
**原因**：CPython 的 `.pyc` 失效判据是 `(mtime 截断到秒, size)`。Task 5 的实现者做过一次**等长改动**（47 字符 → 47 字符）且四步在同一秒内完成 → 加载了陈旧字节码、产出**假红**（sha256 已还原成功而 pytest 仍报变异行为）。**假绿更危险**：它会让你以为一条守卫还在工作。
每条变异要写明：**改了哪一行 → 哪条测试的哪个断言分支变红（贴那一句 `assert`）→ 三重还原后的 sha256 与变异前逐字相同**。

## 3. 报告要求

写进 `task-6-report.md`。⚠️ **这个文件在 `.superpowers/` 下，必须用 python 写**（`write_bytes` 一次性写，或 `open(..., "a", encoding="utf-8", newline="")` 追加），**不要用 Write/SearchReplace 工具反复改它** —— IDE 曾把陈旧且截断的缓存写回磁盘、永久丢了约 107 KB。

报告至少 7 节：
1. **环境与基线复现**（SQLAlchemy 版本、开工前 `pytest -q` 的结果）
2. **Step 0 的九格逐格落地**（P6-A5 那张表：每格给「找到的原文 → 改成什么 → 在哪个文件」）
3. **两张表的最终列清单**（逐列给名字与类型，含 P6-A2/A3/A8 新增的三列）+ `_in_domain` 的两个 CHECK 的名字
4. **`triggers.py` 的公开面与五条触发的实现口径**（含 P6-A6 的 `Layer.INSUFFICIENT.value`）
5. **变异取证**（3 条 + M0 + M1，按第 2 节的纪律）
6. **待清扫清单** + **关切**（你认为计划错了的地方、你**没按派单做**的地方，0 处也要写「0 处」）
7. **最终验收**：passed 数（679 → ?）、覆盖率四格、`__all__`（43 → ?）、`_MODELS_PUBLIC_BASELINE`（33 → ?）、表数（16 → 18）、扫描面（32 → 33）、三个禁区指纹、`git diff -- backend/data` 为空

## 4. 交回控制者

最终回复里给出（**简洁，不要贴大段代码**）：commit sha 与说明 / passed 数 / 覆盖率四格 / 表数 / `__all__` 与 `_MODELS_PUBLIC_BASELINE` 的新值 / 扫描面 / 3 条变异的结论 / Step 0 九格是否全部落地 / 顶回控制者的地方 / 没按派单做的地方 / 待清扫条数 / 报告的字节数与行数。

---

"""

parts = [
    DISPATCH,
    nl.join(L[0:i_t1]).rstrip(),
    "",
    "---",
    "",
    nl.join(L[i_t6:i_t7]).rstrip(),
    "",
]
body = nl.join(parts)
if nl != "\n":
    body = body.replace("\r\n", "\n").replace("\n", nl)
OUT.write_bytes(body.encode("utf-8"))
chk = OUT.read_bytes().decode("utf-8")
print(f"[out] {OUT.name}  bytes={len(chk.encode('utf-8'))} lines={chk.count(nl)}")
for probe in ("P6-A1", "P6-A3", "P6-A12", "## Task 6:", "Step 0", "## Global Constraints",
              "DATA_TABLES", "_MODELS_PUBLIC_BASELINE", "previous_had_overrides"):
    print(f"  含 {probe!r}: {chk.count(probe)}")
for bad in ("## Task 5:", "## Task 7:", "## Task 1:"):
    print(f"  不含 {bad!r}: {chk.count(bad) == 0}")

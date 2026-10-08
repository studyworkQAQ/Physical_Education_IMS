"""抽 task-5-brief.md：计划头部 + 重编号对照表 + Global Constraints + Review Focus
+ File Structure + Task 5 全节（含预检更正）。按标题锚点抽，不用裸行号（硬规矩 #78）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
OUT = HERE / "task-5-brief.md"

text = PLAN.read_bytes().decode("utf-8")
nl = "\r\n" if "\r\n" in text else "\n"
L = text.split(nl)
print(f"[plan] bytes={len(text.encode('utf-8'))} lines={len(L)}")


def find(prefix, start=0):
    for i in range(start, len(L)):
        if L[i].startswith(prefix):
            return i
    raise AssertionError(f"锚点未找到: {prefix!r}")


i_head = 0
i_renum = find("## ⚠️ Task 重编号对照表")
i_gc = find("## Global Constraints")
i_rf = find("## Review Focus")
i_fs = find("## File Structure")
i_t1 = find("## Task 1: ")
i_t5 = find("## Task 5: ")
i_t6 = find("## Task 6: ")
print(f"[anchors] renum={i_renum+1} gc={i_gc+1} rf={i_rf+1} fs={i_fs+1} "
      f"t1={i_t1+1} t5={i_t5+1} t6={i_t6+1}")
assert i_head < i_renum < i_gc < i_rf < i_fs < i_t1 < i_t5 < i_t6

DISPATCH = f"""# Task 5 简报 — 处方装配（简化版）：`intensity.py` + `assembler.py` + `safety.py` + `override.py`

> 本简报由控制者从 `Document/2026-10-06-实施计划02-智能处方引擎.md`（commit `c8e26b8`，{len(text.encode('utf-8'))} B / {len(L)} 行）按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + 重编号对照表 + Global Constraints + Review Focus + File Structure + **Task 5 全节（含预检更正 P5-A1..A13）**。Task 1–4 与 Task 6–9 的正文**不在本简报里**（它们已结案或还没轮到）。

## 0. 派单说明（控制者写，不在计划正文里）

**代码基线**：`c8e26b8`（分支 `feature/plan-02-prescription-engine`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **592 passed**（控制者本机实跑，61.84 s）。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **541 stmts / Miss 0 / 132 branch / BrPart 0 / 100%**。
**表数基线**：**16 张**。
**公开面基线**：`app.domain.prescription.__all__` = **24** 个名字；`assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 24`。
**架构守卫扫描面基线**：**28**（pipeline 7 + db 11 + domain 10）。
**环境**：Python 3.11.1（**无 venv**）、SQLAlchemy **2.1.3**、pandas 3.0.6、numpy 2.4.6、PyYAML 6.0.3。
⚠️ **开工第一件事（硬规矩 #73）**：跑 `python -c "import sqlalchemy, pandas, numpy, yaml; print(sqlalchemy.__version__)"` 冒烟，把版本记进报告的「环境与基线复现」节。**Windows Smart App Control 曾在会话中途拦掉 SQLAlchemy 的一个 `.pyd`（文件一个字节都没变），全量测试跑不起来**（账本 Ruling 121/122）。若撞上，**立刻停手报给控制者**，不要自己动系统安全设置。

**⚠️ 本 Task 是四个原 Task（5/6/7/8）的合并，工作量比前面任何一个 Task 都大。** 建议按 5.1 → 5.2 → 5.3 → 5.4 → 5.5 的顺序**分五次 commit**（每节一次），不要攒成一个大 commit。

**⚠️ 本节有 4 条 Critical 级预检更正（P5-A1 ~ P5-A4），全部是「计划原文引用了一个不存在的东西」：**
- **P5-A1**：`Block.structure` 里**没有**「周训练总量」这个字段。实测只有两种键集（时长类 78 个 `{{sets, work_min, rest_min}}`、次数类 52 个 `{{rounds, reps}}`）。基准量口径见 5.2 的「⚠️ P5-A1 的基准量口径」段。
- **P5-A2**：同一 `exercise_ref` 在一周内**跨 session 重复，18/18 全部如此**。`weekly_volume = base × sessions_per_week`，不是 `base`。
- **P5-A3**：`when: muscle_low` 的 12 个 addon **必须被消费**（原计划判「无法自动化」是错的）。addon 的量口径 = `weekly_volume 0.0` + `volume_unit "unspecified"` + 一条 warning。
- **P5-A4**：**不许 `import math`**（`ALLOWED_MODULES` 不放行）。用 `int(x)` 与 `-(-x // 1)`，并给 `hr_zone` 加 `hrmax_bpm <= 0` 的拒绝。

**⚠️ Ruling 133（本 Task 的头号约束）**：18 套模板的 130 个 block 里 **82 个是 `intensity: {{type: none}}`**，按层是 **绿 `{{none}}` / 黄 `{{none}}` / 红 `{{hrmax_pct, none, onerm_pct}}`**。**「模板没给强度」是常态不是例外**；心率相关的测试**必须用红层模板或手工构造的 `hrmax_pct` block**，用黄层写会全绿但什么也没测（假绿）。

## 1. 执行强度（账本 Ruling 145，用户 2026-10-08 裁定）

**目标：1–2 轮 fix round**（不是前面几个 Task 的 3–6 轮）。

**保留（一条不许砍）**：TDD 先红后绿；`app/domain/` 分支覆盖 **100%**（`Miss 0 / BrPart 0`）；4 条安全关键变异（见 5.5 的 Step 4）含 M0/M1 双对照与三重还原；单一所有者；断言两侧不同源（期望值**字面写在测试里**）；domain 纯净性守卫全绿。

**取消（不要为这些返工）**：纯散文精度。**注释/docstring 里某个数字与实测不符，不要单独返工一轮**——记进报告的「**待清扫**」清单，控制者在 Task 9 一次性清扫。**但 Critical 级问题（会让生产代码错、会让守卫假绿、会让数据不可追溯）一律当场修，不进清单。**

**⚠️ 若你认为本节某条决定是错的，顶回来。** Plan 02 到目前为止实现者顶回控制者的裁定 **4 次，4 次都是对的**（Ruling 67 / dict-vs-Mapping / CE-4 / CE-7）。共同点是：控制者对着「当前目录形状」推理，实现者对着「守卫实际能抓到什么」推理。**你在代码现场，你的判断优先。**

## 2. 报告要求

写进 `task-5-report.md`（**⚠️ 不要用编辑器打开 `.superpowers/` 下的大文件**——IDE 曾把陈旧且截断的缓存写回磁盘，永久丢了约 107 KB。一律用 python 追加写）：
1. **环境与基线复现**：SQLAlchemy 版本、开工前的 `pytest -q` 结果。
2. **逐节交付**（5.1 / 5.2 / 5.3 / 5.4 / 5.5）：每节的 commit sha、新增测试数、全量 passed 数、domain 覆盖率四格。
3. **变异取证**：4 条变异逐条给「改了哪一行 → 哪条测试的哪个断言分支变红 → 三重还原后的 sha256」，外加 M0（不变异全绿）与 M1（语义等价改写仍全绿）。
4. **待清扫清单**：散文与实测的偏差（Ruling 145）。
5. **关切**：你认为计划错了的地方、以及你**没按派单做**的地方（**必须显式列出并说明理由**，不要静默偏离）。
6. **公开面变化**：`__all__` 从 24 变成几，`_PRESCRIPTION_PUBLIC_BASELINE` 的新值与那句 `assert len(...) == N` 是否同步改了。
7. **扫描面变化**：28 → 32（domain 10 → 14），并说明架构守卫是否需要改。

---

"""

parts = [
    DISPATCH,
    nl.join(L[i_head:i_t1]).rstrip(),   # 头部 + 对照表 + GC + RF + File Structure
    "",
    "---",
    "",
    nl.join(L[i_t5:i_t6]).rstrip(),     # Task 5 全节
    "",
]
body = nl.join(parts)
if nl != "\n":
    body = body.replace("\r\n", "\n").replace("\n", nl)
OUT.write_bytes(body.encode("utf-8"))
chk = OUT.read_bytes().decode("utf-8")
print(f"[out] {OUT.name}  bytes={len(chk.encode('utf-8'))} lines={chk.count(nl)}")
for probe in ("P5-A1", "P5-A4", "P5-A13", "Ruling 133", "## Task 5:", "### 5.5 收尾",
              "## Global Constraints", "ALLOWED_MODULES", "resistance_priority"):
    print(f"  含 {probe!r}: {chk.count(probe)}")
for bad in ("## Task 4:", "## Task 6:", "## Task 1:"):
    print(f"  不含 {bad!r}: {chk.count(bad) == 0}")

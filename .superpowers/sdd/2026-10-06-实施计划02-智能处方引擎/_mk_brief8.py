"""抽 task-8-brief.md：计划头部 + 对照表 + GC + RF + File Structure + Task 8 全节。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
OUT = HERE / "task-8-brief.md"

text = PLAN.read_bytes().decode("utf-8")
nl = "\r\n" if "\r\n" in text else "\n"
L = text.split(nl)


def find(prefix, start=0):
    for i in range(start, len(L)):
        if L[i].startswith(prefix):
            return i
    raise AssertionError(f"锚点未找到: {prefix!r}")


i_t1, i_t8, i_t9 = find("## Task 1: "), find("## Task 8: "), find("## Task 9: ")
print(f"[plan] bytes={len(text.encode('utf-8'))} lines={len(L)}  t1={i_t1+1} t8={i_t8+1} t9={i_t9+1}")
assert i_t1 < i_t8 < i_t9

DISPATCH = f"""# Task 8 简报 — 「本周训练单」读模型（`weekly.py`，spec §8.4）

> 本简报由控制者从 `Document/2026-10-06-实施计划02-智能处方引擎.md`（commit 见 `git log --oneline -1`，{len(text.encode('utf-8'))} B / {len(L)} 行）按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + 重编号对照表 + Global Constraints + Review Focus + File Structure + **Task 8 全节（含预检更正 P8-A1..A8）**。

## 0. 派单说明（控制者写，不在计划正文里）

**代码基线**：`197147f`（分支 `feature/plan-02-prescription-engine`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **750 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **951 stmts / Miss 0 / 274 branch / BrPart 0 / 100%**（带 `--cov` 时 `749 passed, 1 skipped`）。
**表数 18**（`prescription` **16 列**、`weekly_adjustment` **8 列**）；`app.domain.prescription.__all__` = **47**；`_MODELS_PUBLIC_BASELINE` = **33（刻意不动，Ruling 97）**；扫描面 **34**（pipeline 8 + db 11 + domain 15）→ 本 Task 后 **35**（domain 16）。
**环境**：Python 3.11.1（**无 venv**）、SQLAlchemy **2.1.3**、pandas 3.0.6、numpy 2.4.6、PyYAML 6.0.3。
⚠️ **开工第一件事（硬规矩 #73）**：跑 `python -c "import sqlalchemy, pandas, numpy, yaml; print(sqlalchemy.__version__)"` 并记进报告。**若撞上 `ImportError: DLL load failed`，立刻停手报回控制者。**

**本 Task 是 Plan 02 里最小的一个**：新建 1 个 domain 模块（`weekly.py`）+ 1 个 pipeline 函数（`weekly_factors_of`）。**控制者预期 0–1 轮 fix round。**

## 0.1 你要交付什么

**新建**：
- `backend/app/domain/prescription/weekly.py` —— `current_week` / `weekly_training_sheet` / `WeeklySheet` / `WeeklyFactor`
- `backend/tests/domain/test_prescription_weekly.py`

**修改**：
- `backend/app/pipeline/prescription_stage.py` —— 加 `weekly_factors_of(session, prescription_id) -> list[WeeklyFactor]`
- `backend/tests/pipeline/test_prescription_stage.py` —— 加它的测试（**直接插 `WeeklyAdjustment` 行**喂它）+ `WeeklyAdjustment.SOURCES` 的漂移测试
- `backend/app/domain/prescription/__init__.py` —— 重导出新公开名
- `backend/tests/test_refdata_prescription.py` —— `_PRESCRIPTION_PUBLIC_BASELINE` **47 → 新值**，并同步那里的 `assert len(...)` 与 `_OWNED_MODULES`（⚠️ Task 5/6 的实现者发现同文件里**有两句 `assert len`**、且 `_OWNED_MODULES` 也要跟着加 `weekly`，**三处都要改**）

## 0.2 ⚠️ 2 条 Critical（逐条照办）

- **P8-A1**：`AssembledBlock` 今天是 **10 个字段**（实测：`exercise_ref / exercise_name / video_url / impact_level / intensity_text / hr_zone / structure / weekly_volume / volume_unit / sessions_per_week`）。计划原文只说「缩放只作用于 `weekly_volume`，不改 `hr_zone`」，**对另外 8 个字段一字未提**。口径收紧成：**只改 `weekly_volume`（`round(x * factor, 1)`），其余 9 个字段逐字不变**。⚠️ **`sessions_per_week` 被缩会让「一周做几次」随减量变化**（语义错误）。测试用 `dataclasses.replace` 做对照、断言「除 `weekly_volume` 外全等」。⚠️ **`WeeklySheet` 刻意不提供跨单位的周总量汇总字段**（`volume_unit` 值域实测 `{{min, reps, unspecified}}`，相加就是 Task 5 F1-1 那个「混合量纲 float」错误）—— **这条要写进 docstring，否则 Plan 03 的前端会自己把 `min` 和 `reps` 加起来。**
- **P8-A2**：`volume_unit` 的第三档 **`"unspecified"`** 是 Task 5 的 P5-A3 为 **addon block** 加的，那一档 `weekly_volume` 恒为 **`0.0`**；而 `apply_safety` 追加的 addon **已经在 `TrainingPackage.weeks` 里** → `weekly_training_sheet` **一定会吃到它**，而计划对这一档只字未提。**照原样带出、不特殊处理**（`0.0 × factor = 0.0`），但**必须有一条吃真仓的测试**：红层模板 + 体脂异常触发 → 装配出一个含 addon 的包 → 断言那个 addon block 的 `weekly_volume == 0.0` 且 `volume_unit == "unspecified"`。

## 0.3 其余 6 条（简报的预检总表里有完整实测依据）

- **P8-A3**：`WeeklySheet` **加一个 `paused: bool` 字段**（从 `pkg.paused` 直接抄），`paused=True` 时 `sessions` **原样保留**。**不要抛 `ValueError`**（读模型的职责是投影、不是校验）。「暂停」与「本周量为 0」是两件不同的事，`paused` 字段就是为了不让前端把两者静默合并。
- **P8-A4**：`weekly_factors_of` **今天不存在**（`prescription_stage.py` 里 0 命中），`weekly_adjustment` 表**今天 0 行**。**照 Task 2 的 `sync_exercises` / `sync_templates` 先例**：测试**直接插 `WeeklyAdjustment` 行**喂它，docstring 按硬规矩 #39 写明「今天没有生产调用方，Plan 03 的 API 层才会调」。⚠️ **排序必须显式**：`created_at` 是 `DateTime NOT NULL 无缺省` → **`ORDER BY created_at, id`**（`id` 作 tie-breaker，因为同一秒批量插入时 `created_at` 相等），并**有一条测试钉住这个 tie-breaker**（构造两行 `created_at` 相同、`id` 不同的调整）。
- **P8-A5**：`WeeklyFactor.source` 的值域有**两个住址**（DB 的 `ck_weekly_adjustment_source` ∈ `{{auto, teacher}}`，与 domain 的裸 `str`）。**domain 侧不另立词表**，但**要有一条漂移测试**字面钉住 `WeeklyAdjustment.SOURCES == {{"auto", "teacher"}}` —— **放 pipeline 层的测试里**（domain 不能 import ORM）。
- **P8-A6**：`factor` 的 `(0, 2]` 与 DB 列没有 CHECK 是**两层守卫、不是重复**。DB 那一层**刻意不加**（`(0, 2]` 是**读模型的语义**、不是数据的形状，Plan 03 可能要放宽上界）。**把这个理由写进 `weekly.py` 的 docstring。**
- **P8-A7**：Task 6 的 `triggers.py` 实测用 `(as_of - generated_on).days >= microcycle_weeks * _DAYS_PER_WEEK`（**不是 `timedelta`**，domain 不能 import `datetime`）。`current_week` 用**同一口径**：`week = (as_of - generated_on).days // 7 + 1`。⚠️ **`.days // 7` 对负数向下取整**（`-1 // 7 == -1`）→ **必须先判 `.days < 0` 再算**，配一条 `as_of == generated_on - 1 day → None` 的测试（**不是 0、不是 1**）。⚠️ **另配一条跨模块一致性测试**：「`current_week` 返回 `None`」与「`evaluate_triggers` 的 `MICROCYCLE_EXPIRED` 成立」在到期日那一格**同真** —— **这是两个模块口径不漂的唯一守卫。**
- **P8-A8**：「缩放不动 `hr_zone`」那条测试**必须用红层模板**（如 `RED-END-ABN-01`）。实测 `hr_zone` **只有红层的 `hrmax_pct` block 非 `None`**（Ruling 133：130 个 block 里 82 个是 `type: none`），**用黄层绿层写是恒真式（假绿）**。

## 0.4 控制者实测的三套真仓装配数据（供你对拍，**期望值仍要自己算**，硬规矩 #44）

`as_of = 2026-10-08`、男 20 岁、`endurance_score = 70`（→ 档 `mid` → `1.0`）、性别男（`1.0`）：

| 模板 | `weeks` | `sessions/周` | `volume_unit` | 第 1 周各 block 的 `weekly_volume` | `delta` |
|---|---|---|---|---|---|
| `RED-END-ABN-01` | 4 | `[4,4,4,4]` | `{{min, reps}}` | 8 个 block = `[48.0 min, 120.0 reps] × 4` | `[1.0, 1.05, 1.1, 0.85]` |
| `YEL-END-NOR-08` | 4 | `[3,3,3,3]` | `{{min}}` | 6 个 block 全是 `36.0 min` | 同上 |
| `GRN-END-NOR-14` | 4 | `[2,2,2,2]` | `{{min}}` | 4 个 block 全是 `24.0 min` | 同上 |

三套的 `paused` 都是 `False`。`weekly_training_sheet(pkg, 1, [])` 应当返回 `factor == 1.0` 且 `sessions` 与骨架逐字段相同。

## 1. 执行强度（账本 Ruling 145）

**目标 0–1 轮 fix round**（Task 6 用了 0 轮、Task 5 与 Task 7 各 1 轮）。
**保留**：TDD；`app/domain/` 分支覆盖 **100%**；变异（**2 条即可**：① 把「缩放也作用于 `hr_zone`」→ 那条测试红；② 把 `factor` 的 `(0, 2]` 上界删掉 → 越界拒绝测试红）含 M0/M1 双对照与三重还原；单一所有者；断言两侧不同源；架构守卫全绿；**Plan 01 与 Task 5/6/7 的全部既有测试仍全绿**。
**取消**：纯散文精度 → 记进「待清扫」清单。**但 Critical 级一律当场修。**

## 2. 变异取证纪律（硬规矩 #83）

跑变异前后**必须**：`shutil.rmtree(__pycache__, ignore_errors=True)` + `PYTHONDONTWRITEBYTECODE=1` + pytest 加 `-p no:cacheprovider`。**原因**：CPython 的 `.pyc` 失效判据是 `(mtime 截断到秒, size)`，Task 5 的实现者做过一次等长改动（47 字符 → 47 字符）且四步在同一秒内完成 → 加载了陈旧字节码、产出**假红**。**假绿更危险。**

## 3. 硬约束

1. **`app/domain/` 无任何 I/O**：不得 import `sqlalchemy` / `fastapi` / `requests` / `httpx` / `pydantic_settings` / `random` / `math` / `types` / `json` / `os` / `sys` / `pathlib` / **`datetime`**；不得出现 `datetime.now` / `date.today` / `time.time` / `open(` / `Path(` / `__file__`。实测 `ALLOWED_MODULES = {{dataclasses, enum, collections, collections.abc, numpy, typing}}`。⚠️ **`weekly.py` 要用日期减法** —— 照 `triggers.py` 的做法（`.days`），**不要 import `datetime`**；类型标注照 `intensity.py` / `override.py` 的既有做法（实测 `app/domain/` 下 `from __future__` 与 `TYPE_CHECKING` 各 **0** 命中，用的是**前向引用字符串标注**如 `birth: "dt.date"`）。
2. **`app/domain/` 分支覆盖 100%**（`Miss 0 / BrPart 0`）。
3. **单一所有者**：`source` 的值域所有者是 `WeeklyAdjustment.SOURCES`（DB 侧），domain 只消费 + 漂移测试。
4. **断言两侧不得同源**：期望值字面写在测试里（硬规矩 #35）。
5. **TDD**：先写失败测试、跑红、再实现。
6. **禁区**：`backend/pe.db`（不得存在）、`backend/data/seed/`（0 文件）、`backend/data/**` 与 `golden_cases.json` **一个字节都不许动**（三个指纹 `D2C8E539E2FA0029` / `3DE598AF38631209` / `822CB86A5E998301`）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**。
7. **PowerShell**：`;` 分隔；不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑写临时 `.py`。**所有写文件走 python。**
8. **`git add` 按文件名逐个加**。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。**不要 push。**
9. **数键/字段/成员一律用运行时口径**（`len(dict)` / `len(dataclasses.fields(...))` / `len(list(...columns))`），**绝不用正则数源码**（硬规矩 #89）。**数行尾/字节数用 `read_bytes()`，不用 `read_text()`**（通用换行会把 `\\r\\n` 翻成 `\\n`，硬规矩 #89 的扩写）。

## 4. ⚠️ 若你认为简报/计划某条决定是错的，**顶回来**

Plan 02 到目前为止实现者顶回控制者 **21 次，21 次都是对的**。最近 5 次（账本 Ruling 152）包括：「计划要求换处方时关账 `valid_to` —— 那会让 `valid_to` 不再是该行自身数据的纯函数、违反 spec §4.3」、「**派单声称控制者已经改了计划正文的 4 处，实测 0/4 在树上**」、「派单预设了一条根本不存在的守卫」。
共同点：**控制者对着「当前目录形状」推理，实现者对着「守卫实际能抓到什么」推理。你在代码现场，你的判断优先。**
顶回时：① 不要静默偏离；② 在报告的「关切」节写明「哪条决定、为什么错、你的替代方案、代价」；③ 若能同时给两个版本，先实现你认为对的那个。

## 5. 报告

写进 `task-8-report.md`。⚠️ **必须用 python 写**（`write_bytes` 一次性，或 `open(..., "a", encoding="utf-8", newline="")` 追加），**不要用 Write/SearchReplace 工具反复改它**。

至少 7 节：① 环境与基线复现；② `weekly.py` 的公开面与四个对象的字段（运行时口径）；③ `weekly_factors_of` 的排序口径与 tie-breaker 测试；④ 变异取证（2 条 + M0 + M1）；⑤ 待清扫清单 / 关切 / 没按派单做的地方（0 处也要写「0 处」）；⑥ 最终验收（passed 数 750 → ?、覆盖率四格、`__all__` 47 → ?、`_PRESCRIPTION_PUBLIC_BASELINE`、扫描面 34 → 35、表数 18、三个指纹、`git diff 197147f HEAD -- backend/data` 为空、`golden_cases.json` 未改）；⑦ commit sha。

## 6. 交回控制者

最终回复里给出（**简洁**）：commit sha 与说明 / passed 数 / 覆盖率四格 / `__all__` 与 `_PRESCRIPTION_PUBLIC_BASELINE` 的新值 / 扫描面 / `WeeklySheet` 与 `WeeklyFactor` 的最终字段清单（运行时口径）/ 2 条变异的结论 / P8-A1..A8 八条逐条的落地位置 / 顶回控制者的地方 / 没按派单做的地方 / 待清扫条数 / 报告的字节数与行数。

---

"""

parts = [DISPATCH, nl.join(L[0:i_t1]).rstrip(), "", "---", "", nl.join(L[i_t8:i_t9]).rstrip(), ""]
body = nl.join(parts)
if nl != "\n":
    body = body.replace("\r\n", "\n").replace("\n", nl)
OUT.write_bytes(body.encode("utf-8"))
chk = OUT.read_bytes().decode("utf-8")
print(f"[out] {OUT.name}  bytes={len(chk.encode('utf-8'))} lines={chk.count(nl)}")
for probe in ("P8-A1", "P8-A8", "## Task 8:", "## Global Constraints", "unspecified",
              "paused", "weekly_factors_of", "RED-END-ABN-01"):
    print(f"  含 {probe!r}: {chk.count(probe)}")
for bad in ("## Task 7:", "## Task 9:", "## Task 1:"):
    print(f"  不含 {bad!r}: {chk.count(bad) == 0}")

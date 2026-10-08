"""Task 6 结案：① 硬规矩 #86 的回扫（Task 7/8/9 的前提被 Task 6 改变了什么）
② 撤回 Step 0 第 6 格（控制者错误 #143）③ 账本追加 Ruling 150 + 硬规矩 #87。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
LEDGER = HERE / "progress.md"
edits = []


def patch(path, pairs):
    raw = path.read_bytes()
    t = raw.decode("utf-8")
    nl = "\r\n" if "\r\n" in t else "\n"
    before = (len(raw), t.count(nl))
    for old, new, count, label in pairs:
        if nl != "\n":
            old = old.replace("\r\n", "\n").replace("\n", nl)
            new = new.replace("\r\n", "\n").replace("\n", nl)
        n = t.count(old)
        assert n == count, f"[{label}] 期望 {count}，实为 {n}\n  old={old[:90]!r}"
        t = t.replace(old, new)
        edits.append((label, n))
    path.write_bytes(t.encode("utf-8"))
    c = path.read_bytes().decode("utf-8")
    print(f"[{path.name}] {before[0]} B / {before[1]} 行 -> "
          f"{len(c.encode('utf-8'))} B / {c.count(nl)} 行  "
          f"CRLF={c.count(chr(13)+chr(10))} LF={c.count(chr(10))}")


# ================= 计划正文 =================
patch(PLAN, [
    # --- ① 撤回 Step 0 第 6 格（控制者错误 #143）---
    ("| 同上 | `assert len(_MODELS_PUBLIC_BASELINE) == 33` + 那个清单本身 | **35**，清单加 `\"Prescription\"` 与 `\"WeeklyAdjustment\"`（**按字母序插进去**，清单今天是排序的） |",
     "| 同上 | ~~`assert len(_MODELS_PUBLIC_BASELINE) == 33` + 那个清单本身 → 35~~ | **⛔ 撤回（控制者错误 #143，实现者顶回成立）。这一格不许做。** 实测 `models/__init__.py` 里有 Task 2/3 留下的逐字纪律（账本 **Ruling 97**）：Plan 02 新加的表类**刻意不进** `__all__`、也没有 `from .prescription import *`；`_MODELS_PUBLIC_BASELINE` 钉的是**拆包之前**（基线 `e26347f`）实测的 33 个公有名，**往那份基线里加新名字等于把「拆包没改导入面」偷换成「拆包后的现状」，断言两侧就同源了（硬规矩 #35）**，而 `…is_unchanged_by_the_split` 这个函数名会当场变成谎话。实测 `Exercise` / `PrescriptionTemplate` **也都不在** `__all__` 里，故抬基线还会与 Task 2/3 的既有先例分裂成两套规矩。**正确做法：基线保持 33、不重导出，改为新增一条守卫 `test_plan02_tables_stay_out_of_the_models_public_namespace` 把 Ruling 97 钉到这两张表上；Task 7 的写入方走 `from app.db.models.prescription import Prescription, WeeklyAdjustment`。** |",
     1, "撤回 Step 0 第 6 格"),

    # --- ② Step 0 补两格（控制者错误 #144：清单自称穷尽却漏了两处相等断言）---
    ("| 同上 | `assert REFERENCE_TABLES == (\"exercise\", \"prescription_template\")` | **不动**（字面钉住，两张新表不进参考数据分区） |",
     "| 同上 | `assert REFERENCE_TABLES == (\"exercise\", \"prescription_template\")` | **不动**（字面钉住，两张新表不进参考数据分区） |\n"
     "| `tests/db/test_models.py` | `assert len(json_text_columns) == 14`（原为 `== 9`） | **P6-A5 补格 1（控制者错误 #144：原清单自称「六处」却漏了它）**：`prescription` 一张表就带 **5 个 `JsonText` 列**，9 → **14**。这是相等断言，不改必红 |\n"
     "| `tests/db/test_models.py` | `_DERIVED_TABLES`（原为三张） | **P6-A5 补格 2**：三张 → **五张**（加 `prescription` 与 `weekly_adjustment`）。同为相等断言 |\n\n"
     "⚠️ **控制者错误 #144 的教训**：原清单把「表数这一个事实的所有副本」找全了，却漏了「**别的事实被同一改动证伪**」的那两格。→ **补硬规矩 #88：列「一个改动要同步几处」的清单时，除了搜那个数本身，还要跑一次全量测试、把红掉的相等断言逐个收进清单——测试比 grep 更全。**",
     1, "Step 0 补两格"),

    # --- ③ Task 7 的 import 路径（Ruling 97 的连带）---
    ("**Interfaces:**\n- Consumes: Task 4–6 全部；Plan 01 的 `StratificationResult` / `DerivedMetrics` / `Student` / `repo.upsert`",
     "**Interfaces:**\n- Consumes: Task 4–6 全部；Plan 01 的 `StratificationResult` / `DerivedMetrics` / `Student` / `repo.upsert`\n"
     "- ⚠️ **import 路径（Ruling 97 / Task 6 的顶回 1）**：两张新表**刻意不进** `app.db.models` 的公有导入面，故本 Task 必须写 "
     "`from app.db.models.prescription import Prescription, WeeklyAdjustment`，**不是** `models.Prescription`。"
     "写错会让 `test_plan02_tables_stay_out_of_the_models_public_namespace` 与 `test_models_public_namespace_is_unchanged_by_the_split` 两条守卫同时失去意义。",
     1, "Task 7 的 import 路径"),

    # --- ④ Task 7 要填 Task 6 新增的三列 ---
    ("- **`daily_sync_run.prescription_count`**（**Plan 01 就已建好的列**，Ruling 17）= `PrescriptionReport.generated`。",
     "- **`daily_sync_run.prescription_count`**（**Plan 01 就已建好的列**，实测 `daily_sync_run` 共 19 列，`prescription_count` 与 `alert_count` 都在）= `PrescriptionReport.generated`。\n"
     "- **⚠️ Task 6 新增的三列必须由本 Task 填**（硬规矩 #86 的回扫结果）：\n"
     "  - `prescription.microcycle_weeks`（**P6-A3**）← `Template.microcycle_weeks`。`valid_to` 的算式与 Task 6 触发 3 的判据都读它，**漏填会让 `valid_to` 无从复算**。\n"
     "  - `prescription.previous_had_overrides`（**P6-A2**）← 生成时查上一张处方的 `teacher_overrides` 是否非空。**这是「界面提示『该生上次存在人工覆盖』」的唯一载体**，不是 `assembly_snapshot` 里的键。\n"
     "  - `weekly_adjustment.batch_id`（**P6-A8**）← 本批的 `batch_id`。**教师手工加的调整行没有批次**，决定：取**该行所属处方当前的 `batch_id`**（若处方尚未落库则取本次运行的批次），并在表注释里写明这个口径。\n"
     "- **⚠️ `skipped_reasons` 必须有 `\"insufficient_data\"` 这个键**（Task 6 实现者报的最高优先级关切）：`evaluate_triggers` 是纯函数、**没有任何渠道**把「为什么返回空 tuple」传出来，而 Z0 闸门拦下的学生（Plan 01 实测缺省注入下 500 人有 **2** 人）会让教师端的「重新生成」按钮**无声失败**。故 `PrescriptionReport.skipped_reasons` 的键除了 `MatchStatus.value` 与 `\"no_trigger\"`，**必须再有 `\"insufficient_data\"`**，并有一条测试钉住这 2 人落进这一格。",
     1, "Task 7 填三列 + skipped_reasons"),

    # --- ⑤ Task 8 的 import 路径 ---
    ("  - `app.pipeline.prescription_stage.weekly_factors_of(session, prescription_id: int) -> list[WeeklyFactor]`（ORM 行 → 纯值对象的转换，放 pipeline 层）",
     "  - `app.pipeline.prescription_stage.weekly_factors_of(session, prescription_id: int) -> list[WeeklyFactor]`（ORM 行 → 纯值对象的转换，放 pipeline 层）\n"
     "  - ⚠️ **ORM 行的 import 路径同 Task 7**：`from app.db.models.prescription import WeeklyAdjustment`（Ruling 97：它**不在** `app.db.models` 的公有导入面上）",
     1, "Task 8 的 import 路径"),

    # --- ⑥ Task 9 的 §14 补项：spec §5.2 的真实空洞（Task 6 实现者发现）---
    ("- §1.3 加勘误：「单人处方生成 p95 < 3 秒」与「500 人整学期回放 < 60 s」**本原型均未验收**",
     "- **§14 补 #37（Task 6 实现者发现的 spec §5.2 真实空洞）**：五个触发条件**都只看分层标签**（`current_label` vs `label_at_generation`），"
     "而模板匹配还吃 `dominant_bucket`（`W`）与体成分状态（`C`）——**这两个每天都重算**。故「标签不变、但 `W` 或 `C` 变了 → 该换模板」这一类学生，"
     "**五条触发一条都不成立**，今天全靠触发 4 的工程口径（「任何新采集即刷新」）兜住。**若将来把触发 4 收窄成「只在 week16」，就会真的漏人。**"
     "→ 登记 §14 并**与触发 4 的口径（#33）绑在一起交代**，不要分成两项。\n"
     "- §1.3 加勘误：「单人处方生成 p95 < 3 秒」与「500 人整学期回放 < 60 s」**本原型均未验收**",
     1, "Task 9 的 §14 #37"),
])

# ================= 账本 =================
lb = LEDGER.read_bytes()
lt = lb.decode("utf-8")
lnl = "\r\n" if "\r\n" in lt else "\n"
print(f"[ledger before] bytes={len(lb)} lines={lt.count(lnl)}")

BODY = """

---

## ✅ Task 6 结案（`prescription` / `weekly_adjustment` 两张表 + 五触发条件 `triggers.py`）

**fix round 用了 0 轮**（Plan 02 第三次零 fix round：Task 3、Task 4、Task 6）。**Critical 零遗留。**

### 交付与验收（全部控制者本机亲跑复核，探针 `t6_probes/_t6_verify.py` 已入库）

| 项 | Task 5 结案基线 | Task 6 结案 |
|---|---|---|
| commit | `55874a6` | **`6bf47f6`（Step 0 + 两张表）→ `3eff251`（`triggers.py` + 27 条测试）→ `0f559e9`（公开面 + 变异取证）** |
| 全量 `pytest -q` | 679 passed | **716 passed**（+37） |
| 带 `--cov` | 678 passed, 1 skipped | **715 passed, 1 skipped** |
| `app/domain/` 覆盖率 | 905 / Miss 0 / 262 / BrPart 0 / 100% | **948 stmts / Miss 0 / 274 branch / BrPart 0 / 100%**；`triggers.py` 自己 **42/0/12/0/100%** |
| 表数 | 16 | **18**（`prescription` 15 列 + `weekly_adjustment` 8 列） |
| `__all__` | 43 | **47**（+4：`LastPrescription` / `TriggerInput` / `TriggerReason` / `evaluate_triggers`；**少了 = 空**） |
| `_PRESCRIPTION_PUBLIC_BASELINE` | 43 | **47**（两处 `assert len` 都改了）；`_OWNED_MODULES` 7 → **8** |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33（刻意不动，见 Ruling 150 的顶回 1）** |
| 扫描面 | 32（domain 14） | **33**（domain **15**） |
| 三个禁区指纹 | `D2C8E539E2FA0029` / `3DE598AF38631209` / `822CB86A5E998301` | **逐字不变**；`git diff 3a5bd40 HEAD -- backend/data` **为空**；`pe.db` 不存在、`data/seed/` 0 文件 |

**控制者亲验的承重结论**：
- `prescription` **15 列**：`id` / `student_id` FK / `generated_on` Date / `batch_id` FK+index / **`template_ref` String(32)**（P6-A7）/ **`microcycle_weeks` Integer**（P6-A3）/ 五个 `JsonText`（`training_package` / `assembly_snapshot` / `safety_substitutions` / `teacher_overrides` / `trigger_reasons`）/ **`previous_had_overrides` Boolean NOT NULL default False**（P6-A2）/ `status` String(16) NOT NULL **无缺省** / `valid_from` Date / `valid_to` Date NULL；表级 `uq_prescription_student_day(student_id, generated_on)` + `ck_prescription_status`。
- `weekly_adjustment` **8 列**：`id` / `prescription_id` FK / **`batch_id` FK+index**（P6-A8）/ `week` / `factor` Float / `reason` Text / `source` String(8) + `ck_weekly_adjustment_source` / `created_at` DateTime NOT NULL 无缺省。
- **两个 CHECK 都走 `_shared._in_domain` + 类常量**（`STATUSES` / `SOURCES`），P6-A9 ✓
- **`prescription_template` 仍是 10 列**（P6-A3 的「刻意不加列」被遵守，且实现者加了 `len(...columns) == 10` 的守卫钉住它）
- **`triggers.py` 的 import 面只有 `app.domain.stratify` / `dataclasses` / `enum`** —— **没有 `datetime`、没有 `timedelta`**（P6-A6 的绝对导入 ✓、domain 纯净性 ✓）
- 分区守卫：`ORGANISATION_TABLES` **5**、`DATA_TABLES` **11**（含两张新表）、`REFERENCE_TABLES` **2 未动**（P6-A4 ✓）
- `test_models.py`：`== 16` **0 命中**、`sixteen` **0 命中**、`== 18` **6 命中**、`eighteen` **3 命中**（P6-A5 的九格 + 补的两格全部落地）

### Ruling 150 — 实现者第 13–16 次顶回控制者，**4 处全部采纳**；5 处偏离全部追认

**顶回 1（Critical，采纳 → 控制者错误 #143）**：派单 Step 0 的**第 6 格**要求把 `_MODELS_PUBLIC_BASELINE` 从 33 抬到 35 并重导出两个新类。**照做会破坏一条有意的架构守卫。** 控制者亲验坐实：`models/__init__.py` 里有 Task 2/3 留下的逐字纪律（账本 **Ruling 97**）——Plan 02 新加的表类**刻意不进** `__all__`、也没有 `from .prescription import *`；那条基线钉的是**拆包之前**（基线 `e26347f`）实测的 33 个公有名，**往基线里加新名字等于把「拆包没改导入面」偷换成「拆包后的现状」，断言两侧就同源了（硬规矩 #35）**，而 `test_models_public_namespace_is_unchanged_by_the_split` 这个函数名会当场变成谎话。实测 `Exercise` / `PrescriptionTemplate` **也都不在** `__all__` 里，且 Task 3 已经有一条 `test_prescription_template_is_not_in_the_models_public_namespace` 守卫——**抬基线还会与既有先例分裂成两套规矩，而现有守卫只查前两个名字、不会红，不一致会静默留下**。实现者的处置正确：基线不动，新增 `test_plan02_tables_stay_out_of_the_models_public_namespace` 把 Ruling 97 钉到两张新表上，并把整段顶回逐字写进 `models/__init__.py` 的注释（含 Task 7 该怎么 import）。
**⚠️ 这与 Ruling 103 同型第 2 次**：控制者让实现者改一个 import/基线，照做会**静默**破坏一条守卫。
**→ 补硬规矩 #87：派单里凡是「把某个基线数字抬上去」的指令，必须先读那条基线断言的 docstring——有些基线的意义恰恰是「不许抬」。**

**顶回 2（采纳 → 控制者错误 #144）**：Step 0 的清单**自称穷尽（「六处」/九格）却漏了两格**：`assert len(json_text_columns) == 9`（`prescription` 一张表就带 5 个 `JsonText` 列 → **14**）与 `_DERIVED_TABLES`（三张 → **五张**）。两者都是相等断言，不改必红。**根因**：漏的两格不是「表数这一个事实的副本」，而是「**别的事实被同一改动证伪**」——控制者只 grep 了那个数本身。
**→ 补硬规矩 #88：列「一个改动要同步几处」的清单时，除了搜那个数本身，还要跑一次全量测试、把红掉的相等断言逐个收进清单——测试比 grep 更全。**

**顶回 3（采纳 → 控制者错误 #145）**：变异 ③ 的字面要求**不可表达**。派单写「触发 2 改成比较『上一次运行的标签』而不是 `label_at_generation`」，但 `TriggerInput` 的 10 个字段里**没有「上一次运行的标签」这个字段**——而**那个缺席正是设计本身**（计划 Task 6 的触发 2 决定段逐字写着「比较的是**生成当时**的标签，不是上一次运行的标签——否则『黄→红→黄』会在第三天又触发一次」）。实现者取了最近的可表达变异（改成比较 `current_template_id != last.template_id`）并**另补一条守卫**。**⚠️ 这与 P6-A1 是同一根因的第 3 次**：派单要求一个在 Task 6 里不存在的东西。

**顶回 4（采纳 → 控制者错误 #146）**：触发 3 需要 `timedelta`，而 `datetime` **不在** domain 的 allow-list 里。派单只回答了「类型标注怎么办」的一半（`dt.date` 的标注），**没回答运行时算术怎么办**。实现者的处置：不构造 `timedelta`，改写成 `(as_of - generated_on).days >= microcycle_weeks * _DAYS_PER_WEEK`（`_DAYS_PER_WEEK = 7`），并给出等价性论证（对 `date` 操作数 `a - b` 恰好是 `timedelta(days=n)`、`seconds=0`，故 `>=` 与 `.days >=` 逐格等价），**还写明了失效边界**：若有人喂 `datetime` 进来，`.days` 对负差值向下取整（`timedelta(days=-1, seconds=1).days == -1`），故契约必须是 `date`；并配了一条 **duck typing 守卫**（只实现 `__sub__` / `__gt__` 的替身必须照样能用）堵死「偷偷 import timedelta」这条退路。实现者**明确不建议**把 `datetime` 加进 allow-list（`assembler.py` 已表过态，且那会让时钟守卫退化成只挡一种写法，而它的 docstring 亲跑取证过 **7 种**绕过）。**控制者采纳，且认为这比派单的原方案更好。**

**5 处偏离派单字面的处置**：
| # | 偏离 | 裁定 |
|---|---|---|
| ① | Step 0 第 6 格未做 | **追认**（见顶回 1，那格本来就不该做） |
| ② | 变异 ③ 换成可表达的等价形态并另补守卫 | **追认**（见顶回 3） |
| ③ | 触发 3 用 `.days >= weeks*7` 代替 `>= timedelta(...)` | **追认**（见顶回 4） |
| ④ | 多改了 3 个派单 `Files` 段没列的文件（`_shared.py` / `repo.py` / `assessment.py`，**全是散文**，且都被本次改动**证伪**） | **追认**（按硬规矩 #66 当场修）。⚠️ `daily.py` / `backfill.py` 的「三张派生表」**刻意没改**——它们今天仍为真（Task 7 才会变成五张） |
| ⑤ | 在 `tests/db/test_models.py` **新增 10 条测试**（派单只说改六处） | **追认**。其中 **3 条是 P6-A2 / P6-A3 / P6-A8 唯一的可执行判据**（`previous_had_overrides` 列存在且 NOT NULL、`microcycle_weeks` 列存在、`weekly_adjustment.batch_id` 列存在且是 FK）——没有它们，那三条 Critical 更正只有散文、没有守卫 |

### 实现者报的两条关切（控制者裁定）

**关切 1（最高优先级，简报点名要报的）—— `insufficient_data` 早退会让教师端无声失败**：实现者**同意**这个决定（Z0 闸门拦下的学生不该生成处方），但指出**代价派单只写了半句**：`evaluate_triggers` 是纯函数、**没有任何渠道**把「为什么返回空 tuple」传出去，而 Plan 01 实测缺省注入下 500 人有 **2** 人落这一档 → 教师点「重新生成」会得到一个**没有任何解释的空结果**。
**裁定：采纳，已按硬规矩 #86 当场写进 Task 7 的计划正文**——`PrescriptionReport.skipped_reasons` 的键除了 `MatchStatus.value` 与 `"no_trigger"`，**必须再有 `"insufficient_data"`**，并有一条测试钉住那 2 人落进这一格。

**关切 2 —— spec §5.2 的真实空洞**：五个触发条件**都只看分层标签**，而模板匹配还吃 `dominant_bucket`（`W`）与体成分状态（`C`），**这两个每天都重算**。故「标签不变、但 `W` 或 `C` 变了 → 该换模板」这一类学生**五条触发一条都不成立**，今天全靠触发 4 的工程口径（「任何新采集即刷新」）兜住；**若将来把触发 4 收窄成「只在 week16」就会真的漏人**。
**裁定：采纳，已写进 Task 9 的 §14 补项（新 #37），并要求与触发 4 的口径（#33）绑在一起交代、不分成两项。**

### 硬规矩 #86 的回扫结果（本 Task 结案时扫 Task 7/8/9）

按 Ruling 149 立的硬规矩 #86，结案时扫了后续三个 Task 的正文，**查出 5 处被 Task 6 改变的前提，已当场更正**：
1. **Task 7 的 import 路径**：两张新表**不在** `app.db.models` 的公有导入面上 → 必须 `from app.db.models.prescription import Prescription, WeeklyAdjustment`（Ruling 97 的连带；写错会让两条守卫同时失去意义）
2. **Task 7 要填 Task 6 新增的三列**：`prescription.microcycle_weeks`（← `Template.microcycle_weeks`；漏填会让 `valid_to` 无从复算）、`prescription.previous_had_overrides`（← 上一张处方的 `teacher_overrides` 是否非空；**这是「界面提示该生上次存在人工覆盖」的唯一载体**）、`weekly_adjustment.batch_id`（教师手工加的调整行没有批次，决定取该行所属处方当前的 `batch_id`）
3. **Task 7 的 `skipped_reasons` 要有 `"insufficient_data"` 键**（关切 1）
4. **Task 8 的 `weekly_factors_of` 同样要走子模块 import 路径**
5. **Task 9 的 §14 补 #37**（关切 2）
⚠️ 同时把 Task 7 那句「`daily_sync_run.prescription_count` 是 Plan 01 就已建好的列」补上实测口径（该表共 **19 列**，`prescription_count` 与 `alert_count` 都在）。

**计划正文**：6 处替换全部命中 1 次（硬规矩 #79）。
**待清扫（推 Task 9）**：实现者报的 **8 条**（`_DERIVED_TABLES` 常量名、`daily.py`/`backfill.py` 的散文、`test_repo.py` 的「九条 `ck_*`」、RST 表列宽、`valid_from` 无区分测试、`factor` 无范围 CHECK、spec §14 两项待登记、`get_type_hints` 抛 `NameError`）。**其中 `factor` 无范围 CHECK 值得 Task 8 留意**——Task 8 的 `WeeklyFactor.__post_init__` 会校验 `(0, 2]`，而 DB 列没有对应的 CHECK，两者是**两层守卫**，不是重复（domain 的值对象与 DB 的列各有各的失守方式），但**要在 Task 8 的正文里写明这一点**，否则下一个人会以为其中一个是冗余的。

### Task 7 的入口状态

- 代码基线 **`0f559e9`** + 本轮结案 commit
- **716 passed**、domain **948 / Miss 0 / 274 / BrPart 0 / 100%**、**18 张表**、`__all__` **47**、`_MODELS_PUBLIC_BASELINE` **33（不动）**、扫描面 **33**
- SQLAlchemy **2.1.3**、Python 3.11.1（无 venv）
- ⚠️ **Task 7 是本计划改动面最大的一个 Task**：新建 `prescription_stage.py`、改 `daily.py`、改 Plan 01 已结案的 `run_stratify.input_snapshot_of`（补 `"bmi"` 与 `"snapshot_muscle_p10"` 两个键）、改 `_replay_cleanup` 的清单、并接收 Task 6 移过来的两条集成测试。**且它会改变 Plan 01 那条「全表 canonical sha256」测试的实测值**（计划正文已写明两处要同步：账本与 spec §1.3 的勘误段）。预检时要把这些都逐个实测一遍。
"""

if lnl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", lnl)
assert "Ruling 150" not in lt, "Ruling 150 已存在"
LEDGER.write_bytes((lt.rstrip("\r\n") + BODY).encode("utf-8"))
c = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c.encode('utf-8'))} lines={c.count(lnl)} "
      f"CRLF={c.count(chr(13)+chr(10))} LF={c.count(chr(10))}")
for k in ("Ruling 150", "硬规矩 #87", "硬规矩 #88", "控制者错误 #143", "控制者错误 #144",
          "控制者错误 #145", "控制者错误 #146"):
    print(f"  {k}: {c.count(k)}")

print(f"\n[edits] {len(edits)} 处：")
for lab, n in edits:
    print(f"  {n}x  {lab}")

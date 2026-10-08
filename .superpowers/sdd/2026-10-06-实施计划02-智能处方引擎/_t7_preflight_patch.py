"""Task 7 预检更正（P7-A1..A10）+ 账本 Ruling 151 + 硬规矩 #89。逐条 assert 命中次数。"""
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
    b0 = (len(raw), t.count(nl))
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
    print(f"[{path.name}] {b0[0]} B / {b0[1]} 行 -> {len(c.encode('utf-8'))} B / {c.count(nl)} 行  "
          f"CRLF={c.count(chr(13)+chr(10))} LF={c.count(chr(10))}")
    return c


PRE = """
### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `537683f`，取证脚本 `t7_probes/_t7_probe{1,2,3}.py`）

**测试基线**：`716 passed`；`app/domain/` **948 stmts / Miss 0 / 274 branch / BrPart 0 / 100%**；**18 张表**；`__all__` **47**；扫描面 **33**。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P7-A1** | **Critical** | **`PersonInputs` 上没有身高体重**，故 `input_snapshot_of` 今天**算不出 `bmi` 原始值**。实测 `PersonInputs` 的 **12 个字段** = `student_id / sex / age_group / prev_age_group / curr_scores / prev_scores / curr_total / prev_total / years / body_fat_pct / muscle_mass_kg / snapshot_muscle_p20`。`bmi_of(height_cm, weight_kg)` 住在 `app/domain/indicators.py`，而 `input_snapshot_of(evaluated, result, snapshot)` 的三个参数里**没有任何一个带身高体重**。原始值只在 `fitness_test_result` 表的 `height_cm` / `weight_kg` 两列里。 | **给 `PersonInputs` 加两个字段 `height_cm: float | None` 与 `weight_kg: float | None`**，`input_snapshot_of` 里加 `"bmi": bmi_of(person.height_cm, person.weight_kg)`。**实测构造点只有 3 处**：`percentile_stage.py`（预跑占位路径）、`run_stratify.py` 的黄金用例路径、`run_stratify.py` 的从库构造路径（**这一处能拿到 `fitness_test_result` 的行，身高体重是现成的**）。**否掉另两条路**：给 `input_snapshot_of` 加参数（签名多一个只在快照里用的形参，而 `PersonInputs` 本来就是它的输入载体）；让 `profile_of` 自己查库重算（计划自己已否：第二个所有者） |
| **P7-A2** | **Critical** | **黄金用例路径用硬下标**：`run_stratify.py` 的那一处写的是 `snapshot_muscle_p20=case["snapshot_muscle_p20"]`。若照同样写法加 `height_cm=case["height_cm"]`，**现有 13 例 fixture 会当场 `KeyError`** —— 而 `golden_cases.json` 是 **Task 9** 才改的文件。 | 新增的两个字段**一律用 `case.get("height_cm")` / `case.get("weight_kg")`**（缺省 `None`；`bmi_of(None, None)` 按签名返回 `None`，实测其签名就是 `float | None`）。于是 Task 7 之后黄金用例路径的快照里 `"bmi"` 是 `None`，**直到 Task 9 给 13 例补上身高体重**。⚠️ **已按硬规矩 #86 当场把这条写进 Task 9 的正文**（否则 Task 9 的实现者只会加 `expected` 字段、不会加**输入**字段，而缺了输入，安全触发那三档在黄金用例里根本走不到） |
| **P7-A3** | **Critical** | **`percentile.py` 没有 `lookup_p10`**。实测它的公开函数只有 `lookup_p25` / `lookup_p20` / `lines_used` / `compute_snapshot` / `national_norm` / `norm_is_derivable` / `summarize_source` / `summarize_source`。**但 `PercentileRow` 有 `p10` 字段**（实测 10 个字段：`item / sex / age_group / p10 / p20 / p25 / p50 / p75 / sample_size / source`），DB 的 `percentile_snapshot` 表也有 `p10` 列——**数据在，只是没有取法**。 | **给 `app/domain/percentile.py` 新增 `lookup_p10(snapshot, sex, age_group) -> float | None`**，**逐字照 `lookup_p20` 的口径**（同一个 `_lookup_row`、同一套「样本 < MIN_SAMPLE 就返回 `None`」语义、同一段 docstring 结构）。然后：`PersonInputs` 加 `snapshot_muscle_p10` 字段、`resolve_muscle_lines` 用 `dataclasses.replace` **同时**回填 P20 与 P10、`input_snapshot_of` 加 `"snapshot_muscle_p10"` 键。⚠️ **两条红线**：① **P10 绝不得进入分层判定**（`flag_body_comp` / `evaluate` 一律不读它）——它只服务 spec §7.4 的处方安全触发；读进去就会改 Plan 01 已结案的标签，而 Plan 01 的 13 例黄金用例会当场红。② **domain 覆盖率的分母会变**（`percentile.py` 今天 94/26，加一个函数后 stmts 与 branch 都涨），新函数必须 100% 覆盖，含「组不存在 → `None`」与「样本不足 → `None`」两档 |
| **P7-A4** | **Critical** | `_replay_cleanup` 的清单实测是 `(models.DerivedMetrics, models.StratificationResult, models.PercentileSnapshot)`，走 `repo.delete_by_batch`。**两个坑**：① 两张新表**不在** `models` 的公有导入面上（Ruling 97 / Task 6 的顶回 1），写 `models.Prescription` 会 `AttributeError`；② `weekly_adjustment` 有 **FK 到 `prescription`**，而 SQLite 跑在 `PRAGMA foreign_keys=ON` 下——**先删 `prescription` 会当场 FK 违例**。 | 清单写成 `(models.DerivedMetrics, models.StratificationResult, models.PercentileSnapshot, WeeklyAdjustment, Prescription)`——**`WeeklyAdjustment` 必须排在 `Prescription` 前面**，并在代码注释里写明「顺序承重：子表先删」。import 走 `from app.db.models.prescription import Prescription, WeeklyAdjustment`。**要有一条测试钉住这个顺序**（构造一批带调整行的处方，跑 `_replay_cleanup`，断言两张表都空且没抛 FK 错） |
| P7-A5 | Important | `PIPELINE_TABLES` 实测 **9 张**（`fitness_test_batch / fitness_test_result / body_composition / interest_survey / percentile_snapshot / derived_metrics / stratification_result / daily_sync_run / cleaning_log`），`canonical_dump` 的 docstring 逐字写着「**9 张表**的全部行」。 | **扩到 11 张**（加 `prescription` 与 `weekly_adjustment`），docstring 的「9 张」同步改。理由：那条断言是「幂等性的**强**断言」（Ruling 218），而处方是本计划新加的最大一块派生数据；不覆盖等于「重放翻倍」这个失效形态只被一条较弱的行数断言守着。⚠️ **连带**：扩表之后那个 canonical sha256 的值**真的会变** → 见 P7-A6 |
| P7-A6 | Important | 计划原文说「加键之后，**Plan 01 那条『全表 canonical sha256』测试的实测值会变**」——**这句会被读成「测试会红」，而它不会**。实测那条断言是 `assert first == second`（**两次运行相等**），不是与一个字面哈希相等；字面哈希 `fe0a44e052c7946b…` 在 `backend/` 下 **0 命中**，只出现在账本、spec §1.3 的勘误段与计划正文里。 | 改成两句：① **测试不会红**（它比的是两次运行，不是字面哈希）；② **但散文里的值会过期**——账本与 spec §1.3 印着的 `fe0a44e052c7946b425515fbaaa78f09e32320917a927cd10c8947aea3abfd8f` 与「行数合计 882」**在 P7-A5 扩表 + P7-A1/A3 加键之后都必须重测**，两处都要更新并注明是哪个 commit 改的（硬规矩 #26；Ruling 229 记过一次「一个修复改变了另一个修复的取证基线」） |
| P7-A7 | Minor | `assert first == second` 实测有**两处**（一处在 canonical sha256 那条测试里，另一处在一个更早的幂等测试里），计划只提了一处。 | 加键与扩表之后**两处都要重跑**，报告里分别给结论 |
| P7-A8 | Minor | 计划写「`tests/pipeline/test_daily.py:717-751` 已钉住」`muscle_line_gaps` 恒为 4 / `error_summary` 恒为 NULL。实测那两条断言在**别的位置**（`assert run.muscle_line_gaps == 4` 与 `assert run.error_summary is None`，且**各有两处**）。**结论是对的，裸行号是过期的。** | 按硬规矩 #78 改成可 grep 的原文片段（`git grep -n "muscle_line_gaps == 4" -- backend/`），不写裸行号 |
| P7-A9 | Minor | `bmi_of` 的 docstring **已经预写了 Plan 02 的用途**：逐字有「spec §7.4 的安全后置规则要用『BMI > 30』这个**原始值**（不是国标得分），Plan 02 的 `StudentProfile.bmi` 因此必须由 domain 自己算得出来」，并写明它原先住在 `run_stratify.py`、Task 1 迁走、`run_stratify.bmi_of` 仍重导出可用。 | 无需更正（计划的说法对）。**Task 1 已经为这一步铺好路**，`profile_of` 不必自己算 BMI，只从快照读 |
| P7-A10 | — | **控制者错误 #147**：预检探针用 `[a-z_0-9]+` 这个正则去数 `input_snapshot_of` 返回字典的键，**漏了 `W` 与 `C` 两个大写键**，数出 **24** 而实为 **26**。计划的「26 个键」与它列的 26 个名字**逐格正确**（我按函数体逐行数过一遍坐实）。 | **计划是对的，探针是错的。** → **这是硬规矩 #80 连续第 3 次被违反**（#80 立于 Ruling 147、#82 立于 P5-A10、本次是 #147），三次全是同一形状：**用一个自己没验证的查询去数一个已经写在计划里的量，然后把「我的查询没显示」讲成「计划写错了」**。→ **补硬规矩 #89：数键/数字段/数成员时，一律用 `len(dict)` / `len(dataclass.fields)` / `len(list(Enum))` 这类运行时口径，绝不用正则去数源码——正则的字符类会静默漏掉它没想到的形状（大写键、跨行元组、注释里的同名词）。** |

**扫描面**：本 Task 新建 `app/pipeline/prescription_stage.py` → pipeline 7 → **8**，扫描面 33 → **34**。⚠️ 但 `percentile.py` 加 `lookup_p10` **不新增文件**，故 domain 仍是 15。

"""

c = patch(PLAN, [
    ("## Task 7: 处方生成阶段接入管道（`prescription_stage.py`）\n\n**Files:**",
     "## Task 7: 处方生成阶段接入管道（`prescription_stage.py`）\n" + PRE + "\n**Files:**",
     1, "P7 插入预检更正总表"),

    # Files 行补齐（P7-A1/A3/A5）
    ("**Files:** Create `backend/app/pipeline/prescription_stage.py`、`backend/tests/pipeline/test_prescription_stage.py`；"
     "Modify `backend/app/pipeline/daily.py`、`backend/tests/pipeline/test_daily.py`",
     "**Files:** Create `backend/app/pipeline/prescription_stage.py`、`backend/tests/pipeline/test_prescription_stage.py`；"
     "Modify `backend/app/pipeline/daily.py`（阶段序列 + `_replay_cleanup` 的清单）、"
     "**`backend/app/pipeline/run_stratify.py`（`PersonInputs` 加 3 个字段、`input_snapshot_of` 加 2 个键、"
     "`resolve_muscle_lines` 同时回填 P10；P7-A1/A3）**、"
     "**`backend/app/pipeline/percentile_stage.py`（`PersonInputs` 的构造点之一；P7-A1）**、"
     "**`backend/app/domain/percentile.py`（新增 `lookup_p10`；P7-A3）**、"
     "`backend/tests/pipeline/test_daily.py`（**`PIPELINE_TABLES` 9 → 11** + docstring 的「9 张表」；P7-A5）",
     1, "P7-A1/A3/A5 Files 行"),

    # bmi 那一段（P7-A1/A6/A7）
    ("    **决定：给 `input_snapshot` 补两个键 `\"bmi\"`（原始值）与 `\"snapshot_muscle_p10\"`**，"
     "而不是让 `profile_of` 回去查 `fitness_test_result` 重算。",
     "    **决定：给 `input_snapshot` 补两个键 `\"bmi\"`（原始值）与 `\"snapshot_muscle_p10\"`**，"
     "而不是让 `profile_of` 回去查 `fitness_test_result` 重算。"
     "**⚠️ P7-A1：但这两个键今天在 `input_snapshot_of` 里都算不出来**——`PersonInputs` 的 12 个字段里"
     "**没有身高体重**，而 `percentile.py` **没有 `lookup_p10`**。故本 Task 的真实改动面是："
     "① `PersonInputs` 加 `height_cm` / `weight_kg` / `snapshot_muscle_p10` 三个字段（**3 个构造点**）；"
     "② `percentile.py` 新增 `lookup_p10`（逐字照 `lookup_p20` 的口径）；"
     "③ `resolve_muscle_lines` 同时回填 P20 与 P10；④ `input_snapshot_of` 加那两个键。"
     "**⚠️ P7-A3 的红线：P10 绝不得进入分层判定**（`flag_body_comp` / `evaluate` 一律不读它），"
     "读进去就会改 Plan 01 已结案的标签、13 例黄金用例当场红。",
     1, "P7-A1/A3 决定段"),

    ("    ⚠️ 加键之后，**Plan 01 那条「全表 canonical sha256」测试的实测值会变**——"
     "账本与 spec §1.3 的勘误段里都印着 `fe0a44e052c7946b425515fbaaa78f09e32320917a927cd10c8947aea3abfd8f` "
     "与「行数合计 882」。**两处都要按新实测更新并注明是哪个 commit 改的**"
     "（硬规矩 #26 基数陈述要核对；Ruling 229 记过一次「一个修复改变了另一个修复的取证基线」）。",
     "    ⚠️ **P7-A6 更正原文的表述**：原文写「那条测试的实测值会变」，**这会被读成「测试会红」，而它不会**——"
     "实测那条断言是 `assert first == second`（**两次运行相等**），不是与一个字面哈希相等；字面哈希 "
     "`fe0a44e052c7946b…` 在 `backend/` 下 **0 命中**，只出现在账本、spec §1.3 的勘误段与计划正文里。"
     "**正确的说法是两句**：① 测试不会红；② **但散文里的值会过期**——账本与 spec §1.3 印着的那个哈希与"
     "「行数合计 882」，在 **P7-A5 把 `PIPELINE_TABLES` 从 9 扩到 11** + 本条加两个键之后**都必须重测**，"
     "两处都要更新并注明是哪个 commit 改的（硬规矩 #26；Ruling 229 记过一次「一个修复改变了另一个修复的取证基线」）。"
     "⚠️ **P7-A7：`assert first == second` 实测有两处**（一处在 canonical sha256 那条测试里、"
     "另一处在一个更早的幂等测试里），加键与扩表之后**两处都要重跑**并在报告里分别给结论。",
     1, "P7-A6/A7 sha256 段"),

    # _replay_cleanup（P7-A4）
    ("`_replay_cleanup` 的清单要**加上 `prescription` 与 `weekly_adjustment`**"
     "（按 `batch_id` 删；**⚠️ P6-A8：`weekly_adjustment` 的 `batch_id` 列已由 Task 6 加好**，"
     "故 `repo.delete_by_batch` 对它直接可用，**不需要**新写级联删逻辑）",
     "`_replay_cleanup` 的清单要**加上 `prescription` 与 `weekly_adjustment`**"
     "（按 `batch_id` 删；**⚠️ P6-A8：`weekly_adjustment` 的 `batch_id` 列已由 Task 6 加好**，"
     "故 `repo.delete_by_batch` 对它直接可用，**不需要**新写级联删逻辑）。"
     "**⚠️⚠️ P7-A4 的两个坑**：① 两张新表**不在** `models` 的公有导入面上（Ruling 97 / Task 6 的顶回 1），"
     "写 `models.Prescription` 会 `AttributeError`，必须 `from app.db.models.prescription import Prescription, WeeklyAdjustment`；"
     "② `weekly_adjustment` 有 **FK 到 `prescription`**，而 SQLite 跑在 `PRAGMA foreign_keys=ON` 下——"
     "**先删 `prescription` 会当场 FK 违例**。故清单的顺序是 "
     "`(DerivedMetrics, StratificationResult, PercentileSnapshot, **WeeklyAdjustment**, **Prescription**)`，"
     "**子表先删**，并在代码注释里写明「顺序承重」。要有一条测试钉住它"
     "（构造一批带调整行的处方 → 跑 `_replay_cleanup` → 断言两张表都空且没抛 FK 错）",
     1, "P7-A4 _replay_cleanup"),

    # muscle_line_gaps 的裸行号（P7-A8）
    ("（`tests/pipeline/test_daily.py:717-751` 已钉住）。**别去断言一个恒为 NULL 的列。**",
     "（**P7-A8：按可 grep 的原文找、不要按裸行号找**——`git grep -n \"muscle_line_gaps == 4\" -- backend/` "
     "与 `git grep -n \"error_summary is None\" -- backend/`，两条**各有两处**；原文写的 `:717-751` 已过期，"
     "但结论「60 人下恒为 4 / 恒为 NULL」是对的）。**别去断言一个恒为 NULL 的列。**",
     1, "P7-A8 裸行号"),

    # Task 9 的连带（P7-A2）
    ("⚠️ **GC09 的脆性会传导**",
     "⚠️ **P7-A2 的连带（Task 7 预检时按硬规矩 #86 当场补进来）**：本 Task 除了给每例追加 `expected` 字段，"
     "**还必须给 13 例追加两个输入字段 `height_cm` 与 `weight_kg`**。理由：Task 7 的 `run_stratify` 黄金用例路径"
     "对这两个字段用的是 `case.get(...)`（缺省 `None`，因为 Task 7 不许改本 fixture），故 Task 7 之后 13 例的快照里 "
     "`\"bmi\"` 全是 `None` → **spec §7.4 的三档安全触发在黄金用例里一档都走不到**，"
     "而本 Task 要断言的 `needs_review` 与 `safety_substitutions` 因此恒为假绿。"
     "**补值的方法**：从生成器 `app.seed.fitness._anthropometrics` 的口径反推（它也算到 1 位小数），"
     "或直接给每例一组能让 BMI 落在想要的档位上的身高体重，**并在 `_meta` 里写明每例的 BMI 与它命中的触发**。"
     "⚠️ 补完之后 `bmi_of(height_cm, weight_kg)` 的结果要与该例既有的 `score_bmi` **档位一致**"
     "（否则同一例的输入自相矛盾），这条一致性要有测试。\n\n"
     "⚠️ **GC09 的脆性会传导**",
     1, "P7-A2 Task 9 的连带"),
])

# ================= 账本 =================
lb = LEDGER.read_bytes()
lt = lb.decode("utf-8")
lnl = "\r\n" if "\r\n" in lt else "\n"
print(f"[ledger before] bytes={len(lb)} lines={lt.count(lnl)}")

BODY = """

---

### Task 7: 处方生成阶段接入管道 — 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`537683f`（Task 6 结案，工作树干净）。**测试基线**：`716 passed`；domain **948/0/274/0/100%**；**18 张表**；`__all__` **47**；扫描面 **33**。
**取证脚本**：`t7_probes/_t7_probe{1,2,3}.py`（三份入库）。

#### Ruling 151 — 预检查出 4 Critical / 2 Important / 3 Minor / 1 控制者错误，计划正文更正 7 处

**这是 Plan 02 到目前为止预检命中密度最高的一个 Task**（4 条 Critical，与 Task 5 并列），而根因与前几次不同：**Task 7 是全计划唯一一个要改 Plan 01 已结案代码的 Task**（`input_snapshot_of` / `PersonInputs` / `resolve_muscle_lines` / `percentile.py`），而计划正文是在 Plan 01 结案当天写的、**没有回头核过那些函数的实际签名**。

| # | 级别 | 实测事实 | 处置 |
|---|---|---|---|
| **P7-A1** | **Critical** | **`PersonInputs` 上没有身高体重**，故 `input_snapshot_of` 今天**算不出 `bmi` 原始值**。实测 12 个字段 = `student_id / sex / age_group / prev_age_group / curr_scores / prev_scores / curr_total / prev_total / years / body_fat_pct / muscle_mass_kg / snapshot_muscle_p20`；`input_snapshot_of(evaluated, result, snapshot)` 的三个参数**没有一个带身高体重**；原始值只在 `fitness_test_result.height_cm` / `.weight_kg` 两列里。 | **给 `PersonInputs` 加 `height_cm` / `weight_kg` 两个字段**，`input_snapshot_of` 里加 `"bmi": bmi_of(...)`。**实测构造点只有 3 处**（`percentile_stage.py` 的预跑占位路径、`run_stratify.py` 的黄金用例路径、`run_stratify.py` 的从库构造路径——**最后这一处能拿到 `fitness_test_result` 的行，身高体重是现成的**）。否掉另两条路：给 `input_snapshot_of` 加形参（`PersonInputs` 本来就是它的输入载体）；让 `profile_of` 查库重算（计划自己已否：第二个所有者） |
| **P7-A2** | **Critical** | **黄金用例路径用硬下标** `case["snapshot_muscle_p20"]`。照同样写法加 `case["height_cm"]` 会让**现有 13 例 fixture 当场 `KeyError`**，而 `golden_cases.json` 是 **Task 9** 才改的文件。 | 新增字段一律用 **`case.get(...)`**（缺省 `None`；`bmi_of` 的签名实测就是 `float | None`，返回 `None`）。**并已按硬规矩 #86 当场把连带写进 Task 9 的正文**：Task 9 必须给 13 例**补两个输入字段** `height_cm` / `weight_kg`，否则快照里 `"bmi"` 全是 `None` → **spec §7.4 的三档安全触发在黄金用例里一档都走不到**，而 Task 9 要断言的 `needs_review` / `safety_substitutions` 会**恒为假绿**。补值要与该例既有的 `score_bmi` **档位一致**，且这条一致性要有测试 |
| **P7-A3** | **Critical** | **`percentile.py` 没有 `lookup_p10`**（公开函数只有 `lookup_p25` / `lookup_p20` / `lines_used` / `compute_snapshot` / `national_norm` / `norm_is_derivable` / `summarize_source`）。**但 `PercentileRow` 有 `p10` 字段**（实测 10 个字段），DB 的 `percentile_snapshot` 也有 `p10` 列——**数据在，只是没有取法**。 | **新增 `lookup_p10(snapshot, sex, age_group) -> float | None`**，逐字照 `lookup_p20` 的口径（同一个 `_lookup_row`、同一套「样本 < MIN_SAMPLE 返回 `None`」语义）。连带：`PersonInputs` 加 `snapshot_muscle_p10`、`resolve_muscle_lines` 用 `replace` 同时回填 P20 与 P10、`input_snapshot_of` 加 `"snapshot_muscle_p10"` 键。**⚠️ 两条红线**：① **P10 绝不得进入分层判定**（`flag_body_comp` / `evaluate` 一律不读它），读进去就会改 Plan 01 已结案的标签、13 例黄金用例当场红；② **domain 覆盖率的分母会变**（`percentile.py` 今天 94/26），新函数必须 100% 覆盖，含「组不存在 → `None`」与「样本不足 → `None`」两档 |
| **P7-A4** | **Critical** | `_replay_cleanup` 的清单实测是 `(models.DerivedMetrics, models.StratificationResult, models.PercentileSnapshot)`。**两个坑**：① 两张新表**不在** `models` 的公有导入面上（Ruling 97），写 `models.Prescription` 会 `AttributeError`；② `weekly_adjustment` 有 **FK 到 `prescription`**，SQLite 跑在 `PRAGMA foreign_keys=ON` 下，**先删 `prescription` 会当场 FK 违例**。 | 清单顺序 = `(DerivedMetrics, StratificationResult, PercentileSnapshot, **WeeklyAdjustment**, **Prescription**)`，**子表先删**，代码注释写明「顺序承重」，import 走子模块路径。**要有一条测试钉住顺序**（构造带调整行的处方 → 跑 `_replay_cleanup` → 两张表都空且没抛 FK 错） |
| P7-A5 | Important | `PIPELINE_TABLES` 实测 **9 张**，`canonical_dump` 的 docstring 逐字写着「**9 张表**的全部行」。 | **扩到 11 张**（加两张新表）+ docstring 同步。理由：那条是「幂等性的**强**断言」（Ruling 218），而处方是本计划新加的最大一块派生数据；不覆盖等于「重放翻倍」只被一条较弱的行数断言守着 |
| P7-A6 | Important | 计划原文「那条测试的实测值会变」**会被读成「测试会红」，而它不会**：实测断言是 `assert first == second`（两次运行相等），字面哈希 `fe0a44e052c7946b…` 在 `backend/` 下 **0 命中**（只在账本、spec §1.3、计划正文里）。 | 改成两句：① **测试不会红**；② **但散文里的值会过期**——那个哈希与「行数合计 882」在 P7-A5 扩表 + 加两个键之后**都必须重测**，账本与 spec §1.3 两处都要更新并注明是哪个 commit 改的 |
| P7-A7 | Minor | `assert first == second` 实测有**两处**（canonical sha256 那条 + 一个更早的幂等测试），计划只提了一处。 | 两处都要重跑，报告里分别给结论 |
| P7-A8 | Minor | 计划写「`test_daily.py:717-751` 已钉住」`muscle_line_gaps` 恒为 4 / `error_summary` 恒为 NULL。实测那两条断言在别的位置、且**各有两处**。**结论对，裸行号过期。** | 按硬规矩 #78 改成可 grep 的原文（`git grep -n "muscle_line_gaps == 4"` / `"error_summary is None"`） |
| P7-A9 | Minor | `bmi_of` 的 docstring **已经预写了 Plan 02 的用途**（逐字有「spec §7.4 的安全后置规则要用『BMI > 30』这个**原始值**……Plan 02 的 `StudentProfile.bmi` 因此必须由 domain 自己算得出来」，并写明它原先住在 `run_stratify.py`、Task 1 迁走、仍重导出可用）。 | 无需更正。**Task 1 已为这一步铺好路**，`profile_of` 不必自己算 BMI、只从快照读 |
| P7-A10 | — | **控制者错误 #147**：预检探针用 `[a-z_0-9]+` 这个正则去数 `input_snapshot_of` 返回字典的键，**漏了 `W` 与 `C` 两个大写键**，数出 **24** 而实为 **26**。**计划的「26 个键」与它列的 26 个名字逐格正确**（控制者按函数体逐行数过一遍坐实）。 | **计划是对的，探针是错的。** → **补硬规矩 #89**（见下） |

**扫描面**：本 Task 新建 `app/pipeline/prescription_stage.py` → pipeline 7 → **8**，扫描面 **33 → 34**。⚠️ `percentile.py` 加 `lookup_p10` **不新增文件**，故 domain 仍是 **15**。

**→ 补硬规矩 #89：数键 / 数字段 / 数成员时，一律用运行时口径（`len(dict)` / `len(dataclasses.fields(...))` / `len(list(Enum))`），绝不用正则去数源码——正则的字符类会静默漏掉它没想到的形状（大写键、跨行元组、注释里的同名词）。**
**依据：这是硬规矩 #80 连续第 3 次被违反**（#80 立于 Ruling 147 的 P5-A13、#82 立于 P5-A10、本次是 P7-A10 的 #147），三次全是同一形状：**用一个自己没验证的查询去数一个已经写在计划里的量，然后把「我的查询没显示」讲成「计划写错了」**。#80 只说了「先读那条断言」、#82 只说了「0 命中要先自证查询有效」，**两条都没禁掉「用正则数源码」这个动作本身**，故这次直接禁掉它。

**计划正文更正**：`_t7_preflight_patch.py`，**7 处替换全部命中 1 次**（硬规矩 #79）。

**下一步**：抽 `task-7-brief.md` → 派实现者。**⚠️ 本 Task 是全计划改动面最大的一个**：新建 1 个 pipeline 模块、改 4 个已结案文件（`daily.py` / `run_stratify.py` / `percentile_stage.py` / `domain/percentile.py`）、接收 Task 6 移来的 2 条集成测试、并让 Plan 01 的两处幂等断言与那份 canonical sha256 散文全部重测。**按 Ruling 145 目标仍是 1–2 轮，但控制者预期本 Task 的评审要比前两个更细。**
"""

if lnl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", lnl)
assert "Ruling 151" not in lt, "Ruling 151 已存在"
LEDGER.write_bytes((lt.rstrip("\r\n") + BODY).encode("utf-8"))
c2 = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c2.encode('utf-8'))} lines={c2.count(lnl)} "
      f"CRLF={c2.count(chr(13)+chr(10))} LF={c2.count(chr(10))}")
for k in ("Ruling 151", "硬规矩 #89", "控制者错误 #147", "P7-A1", "P7-A10", "lookup_p10"):
    print(f"  {k}: {c2.count(k)}")
print(f"\n[edits] {len(edits)} 处：")
for lab, n in edits:
    print(f"  {n}x  {lab}")

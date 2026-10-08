"""抽 task-7-brief.md：计划头部 + 对照表 + GC + RF + File Structure + Task 7 全节。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
OUT = HERE / "task-7-brief.md"

text = PLAN.read_bytes().decode("utf-8")
nl = "\r\n" if "\r\n" in text else "\n"
L = text.split(nl)


def find(prefix, start=0):
    for i in range(start, len(L)):
        if L[i].startswith(prefix):
            return i
    raise AssertionError(f"锚点未找到: {prefix!r}")


i_t1, i_t7, i_t8 = find("## Task 1: "), find("## Task 7: "), find("## Task 8: ")
print(f"[plan] bytes={len(text.encode('utf-8'))} lines={len(L)}  anchors t1={i_t1+1} t7={i_t7+1} t8={i_t8+1}")
assert i_t1 < i_t7 < i_t8

DISPATCH = f"""# Task 7 简报 — 处方生成阶段接入管道（`prescription_stage.py`）

> 本简报由控制者从 `Document/2026-10-06-实施计划02-智能处方引擎.md`（commit `d498bac`，{len(text.encode('utf-8'))} B / {len(L)} 行）按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + 重编号对照表 + Global Constraints + Review Focus + File Structure + **Task 7 全节（含预检更正 P7-A1..A10）**。Task 1–6 与 Task 8–9 的正文**不在本简报里**。

## 0. 派单说明（控制者写，不在计划正文里）

**代码基线**：`d498bac`（分支 `feature/plan-02-prescription-engine`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **716 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **948 stmts / Miss 0 / 274 branch / BrPart 0 / 100%**（带 `--cov` 时 `715 passed, 1 skipped`）。
**表数基线**：**18 张**（本 Task 不建表）。
**公开面基线**：`app.domain.prescription.__all__` = **47**；`_PRESCRIPTION_PUBLIC_BASELINE` = **47**；`_MODELS_PUBLIC_BASELINE` = **33（刻意不动，Ruling 97）**。
**架构守卫扫描面基线**：**33**（pipeline 7 + db 11 + domain 15）；本 Task 新建 1 个 pipeline 模块 → **34**。
**环境**：Python 3.11.1（**无 venv**）、SQLAlchemy **2.1.3**、pandas 3.0.6、numpy 2.4.6、PyYAML 6.0.3。
⚠️ **开工第一件事（硬规矩 #73）**：跑 `python -c "import sqlalchemy, pandas, numpy, yaml; print(sqlalchemy.__version__)"` 并记进报告。**若撞上 `ImportError: DLL load failed`（Smart App Control 拦 `.pyd`），立刻停手报回控制者**，不要动系统安全设置、不要升降级依赖。

## 0.1 ⚠️ 本 Task 是全计划改动面最大的一个，也是唯一一个要改 Plan 01 已结案代码的

**新建**：`app/pipeline/prescription_stage.py` + `tests/pipeline/test_prescription_stage.py`
**改 4 个已结案文件**：
- `app/pipeline/daily.py` —— 阶段序列插 `Prescribe`、`_replay_cleanup` 的清单加两张表
- `app/pipeline/run_stratify.py` —— **`PersonInputs` 加 3 个字段**、`input_snapshot_of` 加 2 个键、`resolve_muscle_lines` 同时回填 P10
- `app/pipeline/percentile_stage.py` —— `PersonInputs` 的构造点之一（预跑占位路径）
- **`app/domain/percentile.py`** —— **新增 `lookup_p10`**（⚠️ 这是 domain，会动覆盖率分母）
**改测试**：`tests/pipeline/test_daily.py`（`PIPELINE_TABLES` 9 → 11 + docstring 的「9 张表」）
**接收 Task 6 移来的 2 条集成测试**（Step 0）

**建议分 4 次 commit**：① `lookup_p10` + `PersonInputs` 三字段 + `input_snapshot_of` 两键 + `resolve_muscle_lines`（**这一组必须一次做完，否则中间态跑不起来**）；② `prescription_stage.py` + 它的测试；③ `daily.py` 接入 + `_replay_cleanup` + Step 0 的两条集成测试；④ 收尾（`PIPELINE_TABLES` 扩表、公开面、变异取证、全量）。

## 0.2 ⚠️ 4 条 Critical（逐条照办，不要按计划原文的字面做）

- **P7-A1**：`PersonInputs` **没有身高体重** → `input_snapshot_of` 今天算不出 `bmi`。**加 `height_cm` / `weight_kg` 两个字段**（实测构造点只有 3 处：`percentile_stage.py` 的预跑占位、`run_stratify.py` 的黄金用例路径、`run_stratify.py` 的从库构造路径 —— **最后这一处能拿到 `fitness_test_result` 的行，身高体重是现成的**）。**否掉的两条路**：给 `input_snapshot_of` 加形参；让 `profile_of` 查库重算（第二个所有者）。
- **P7-A2**：黄金用例路径今天写的是 `case["snapshot_muscle_p20"]`（**硬下标**）。新增的两个字段**一律用 `case.get("height_cm")` / `case.get("weight_kg")`**（缺省 `None`；`bmi_of` 的签名实测是 `float | None → float | None`）。**不许改 `golden_cases.json`**（那是 Task 9 的文件）；Task 9 的正文已被控制者按硬规矩 #86 补上连带要求。
- **P7-A3**：`percentile.py` **没有 `lookup_p10`**（但 `PercentileRow` 有 `p10` 字段、DB 也有 `p10` 列）。**新增它，逐字照 `lookup_p20` 的口径**（同一个 `_lookup_row`、同一套「样本 < MIN_SAMPLE 返回 `None`」语义、同一段 docstring 结构）。**⚠️ 两条红线**：① **P10 绝不得进入分层判定** —— `flag_body_comp` / `evaluate` / `derive` 一律**不读**它；读进去就会改 Plan 01 已结案的标签、13 例黄金用例当场红。② **domain 覆盖率分母会变**（`percentile.py` 今天 94 stmts / 26 branch），新函数必须 100% 覆盖，含「组不存在 → `None`」与「样本不足 → `None`」两档。
- **P7-A4**：`_replay_cleanup` 的**两个坑**：① 两张新表**不在** `models` 的公有导入面上（Ruling 97），写 `models.Prescription` 会 `AttributeError` → 必须 `from app.db.models.prescription import Prescription, WeeklyAdjustment`；② `weekly_adjustment` 有 **FK 到 `prescription`**，SQLite 跑在 `PRAGMA foreign_keys=ON` 下，**先删 `prescription` 会当场 FK 违例** → 清单顺序必须是 **`(DerivedMetrics, StratificationResult, PercentileSnapshot, WeeklyAdjustment, Prescription)`，子表先删**，代码注释写明「顺序承重」，并**有一条测试钉住它**。

## 0.3 其余 6 条（简报的预检总表里有完整实测依据）

- **P7-A5**：`PIPELINE_TABLES` **9 → 11**（加两张新表）+ `canonical_dump` docstring 里的「9 张表」同步改。
- **P7-A6**：**Plan 01 那条 canonical sha256 测试不会红**（它断言的是 `first == second`，不是与字面哈希相等；字面哈希 `fe0a44e052c7946b…` 在 `backend/` 下 0 命中）。**但扩表 + 加键之后，账本与 spec §1.3 印着的那个哈希与「行数合计 882」必须重测**，把新值写进报告（控制者会负责回填账本与 spec）。
- **P7-A7**：`assert first == second` 实测有**两处**，两处都要重跑并在报告里分别给结论。
- **P7-A8**：`muscle_line_gaps == 4` / `error_summary is None` 按**可 grep 的原文**找（`git grep -n "muscle_line_gaps == 4" -- backend/`），**不要用计划里的裸行号**（已过期）。
- **P7-A9**：`bmi_of` 的 docstring **已预写 Plan 02 的用途**，Task 1 已铺好路 —— `profile_of` **不必自己算 BMI**，只从快照读。
- **P7-A10**：控制者错误 #147（探针用正则数键漏了 `W`/`C` 两个大写键）→ 硬规矩 #89：**数键/字段/成员一律用运行时口径**（`len(dict)` / `len(dataclasses.fields(...))` / `len(list(Enum))`），**绝不用正则数源码**。你也要遵守这条。

## 0.4 Task 6 结案时按硬规矩 #86 传导过来的四件事（计划正文已写，这里点名）

1. **`prescription.microcycle_weeks`** ← `Template.microcycle_weeks`。**漏填会让 `valid_to` 无从复算**（Task 6 的触发 3 与 `valid_to` 的算式都读它）。
2. **`prescription.previous_had_overrides`** ← 生成时查上一张处方的 `teacher_overrides` 是否非空。**这是「界面提示『该生上次存在人工覆盖』」的唯一载体**，不是 `assembly_snapshot` 里的键（往快照加键会让 Task 5 钉死的 12 键 / +3 键两条守卫变红）。
3. **`weekly_adjustment.batch_id`** ← 本批的 `batch_id`；**教师手工加的调整行没有批次**，取该行所属处方当前的 `batch_id`（若处方尚未落库则取本次运行的批次），并在表注释里写明这个口径。
4. **`skipped_reasons` 必须有 `"insufficient_data"` 这个键**（Task 6 实现者报的最高优先级关切）：`evaluate_triggers` 是纯函数、没有渠道把「为什么返回空」传出来，而 Z0 闸门拦下的学生（Plan 01 实测缺省注入下 500 人有 **2** 人）会让教师端的「重新生成」按钮**无声失败**。要有一条测试钉住这 2 人落进这一格。

## 1. 执行强度（账本 Ruling 145）

**目标 1–2 轮 fix round**（Task 5 用了 1 轮、Task 6 用了 0 轮）。**但控制者预期本 Task 的评审要比前两个更细**，因为它改 Plan 01 已结案的代码。

**保留（一条不许砍）**：TDD；`app/domain/` 分支覆盖 **100%**；4 条变异（Step 2–6 那段）含 M0/M1 双对照与三重还原；单一所有者；断言两侧不同源；架构守卫全绿；**Plan 01 的全部既有测试必须仍然全绿**（这是本 Task 的硬门槛 —— 你改的是已结案代码）。

**取消**：纯散文精度 → 记进报告的「待清扫」清单。**但 Critical 级一律当场修。**

## 2. 变异取证纪律（硬规矩 #83 + #89）

跑变异前后**必须**：`shutil.rmtree(__pycache__, ignore_errors=True)` + `PYTHONDONTWRITEBYTECODE=1` + pytest 加 `-p no:cacheprovider`。
**原因**：CPython 的 `.pyc` 失效判据是 `(mtime 截断到秒, size)`。Task 5 的实现者做过一次**等长改动**（47 字符 → 47 字符）且四步在同一秒内完成 → 加载了陈旧字节码、产出**假红**（sha256 已还原成功而 pytest 仍报变异行为）。**假绿更危险。**
每条变异写明：**改了哪一行 → 哪条测试的哪个断言分支变红（贴那一句 `assert`）→ 三重还原后的 sha256 与变异前逐字相同**。
⚠️ **控制者亲验过 Task 5 的变异 ②**（等长 `True` → `None`，M0 2 passed → 变异后 `1 failed`（`assert None is True`）→ sha256 `BC471A4B5161D10C` → `53C57434FD5AAEEE` → `BC471A4B5161D10C`）。**本 Task 控制者也会亲验至少一条。**

## 3. 硬约束

1. **`app/domain/` 无任何 I/O**：不得 import `sqlalchemy` / `fastapi` / `requests` / `httpx` / `pydantic_settings` / `random` / `math` / `types` / `json` / `os` / `sys` / `pathlib` / **`datetime`**；不得出现 `datetime.now` / `date.today` / `time.time` / `open(` / `Path(` / `__file__`。实测 `ALLOWED_MODULES = {{dataclasses, enum, collections, collections.abc, numpy, typing}}`。⚠️ **`lookup_p10` 住在 domain**，故它也不能碰 I/O —— 照 `lookup_p20` 抄就不会错。
2. **`app/domain/` 分支覆盖 100%**（`Miss 0 / BrPart 0`）。
3. **单一所有者**：`Layer` 的所有者是 `stratify.py`；`bmi_of` 的所有者是 `indicators.py`（`run_stratify` 只是重导出）；`lookup_p20`/`lookup_p10` 的所有者是 `percentile.py`。
4. **断言两侧不得同源**：期望值字面写在测试里（硬规矩 #35）。
5. **TDD**：先写失败测试、跑红、再实现。
6. **禁区**：`backend/pe.db`（不得存在）、`backend/data/seed/`（0 文件）、`backend/data/**` **一个字节都不许动**（三个指纹 `D2C8E539E2FA0029` / `3DE598AF38631209` / `822CB86A5E998301`）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**（会写前两个禁区）；要数据集就在 python 里 `build_dataset(cfg)`，要落 CSV 就 `write_csv(ds, <临时目录>)`。⚠️ **`golden_cases.json` 也不许改**（P7-A2）。
7. **PowerShell**：`;` 分隔，不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑写临时 `.py`。**所有写文件走 python。**
8. **`git add` 按文件名逐个加**，不要 `git add -A`。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。**不要 push。**

## 4. ⚠️ 若你认为本简报/计划某条决定是错的，**顶回来**

Plan 02 到目前为止实现者顶回控制者 **16 次，16 次都是对的**（最近 4 次见账本 Ruling 150，包括「派单要求把 `_MODELS_PUBLIC_BASELINE` 从 33 抬到 35 —— 照做会破坏 Ruling 97 那条有意的架构守卫、让断言两侧同源、让函数名变成谎话」）。共同点：**控制者对着「当前目录形状」推理，实现者对着「守卫实际能抓到什么」推理。你在代码现场，你的判断优先。**
顶回时：① 不要静默偏离；② 在报告的「关切」节写明「哪条决定、为什么错、你的替代方案、代价」；③ 若能同时给两个版本，先实现你认为对的那个。

## 5. 报告

写进 `task-7-report.md`。⚠️ **必须用 python 写**（`write_bytes` 一次性，或 `open(..., "a", encoding="utf-8", newline="")` 追加），**不要用 Write/SearchReplace 工具反复改它**（IDE 曾把陈旧且截断的缓存写回磁盘、永久丢了约 107 KB）。

至少 8 节：
1. 环境与基线复现
2. **Plan 01 既有测试的回归结论**（本 Task 的硬门槛：改了 4 个已结案文件，Plan 01 的测试必须仍全绿；逐条给 `test_daily.py` 两处 `assert first == second` 的结论）
3. `PersonInputs` 的 3 个新字段 + 3 个构造点各自怎么填的（逐点说明）
4. `lookup_p10` 的实现与它与 `lookup_p20` 的**逐字对照**（哪些地方相同、哪些地方必须不同）+ 「P10 不进分层判定」的守卫测试
5. `prescription_stage.py` 的公开面 + Task 6 传导过来的 4 件事逐条落地位置
6. **canonical sha256 的新实测值**（扩表 + 加键之后）与「行数合计」的新值 —— 控制者要拿它回填账本与 spec §1.3
7. 变异取证（4 条 + M0 + M1，按第 2 节的纪律）
8. 待清扫清单 / 关切 / 没按派单做的地方（0 处也要写「0 处」）/ 最终验收（passed 数、覆盖率四格、`__all__`、扫描面、三个指纹、`git diff d498bac HEAD -- backend/data` 为空）

## 6. 交回控制者

最终回复里给出（**简洁，不要贴大段代码**）：commit sha 与说明 / passed 数（716 → ?）/ 覆盖率四格 / 扫描面（33 → 34）/ `PIPELINE_TABLES` 是否 11 / canonical sha256 的新值与行数合计 / Plan 01 既有测试是否全绿 / 4 条变异的结论 / Task 6 传导的 4 件事是否全部落地 / 顶回控制者的地方 / 没按派单做的地方 / 待清扫条数 / 报告字节数与行数。

---

"""

parts = [DISPATCH, nl.join(L[0:i_t1]).rstrip(), "", "---", "", nl.join(L[i_t7:i_t8]).rstrip(), ""]
body = nl.join(parts)
if nl != "\n":
    body = body.replace("\r\n", "\n").replace("\n", nl)
OUT.write_bytes(body.encode("utf-8"))
chk = OUT.read_bytes().decode("utf-8")
print(f"[out] {OUT.name}  bytes={len(chk.encode('utf-8'))} lines={chk.count(nl)}")
for probe in ("P7-A1", "P7-A4", "P7-A10", "## Task 7:", "Step 0", "## Global Constraints",
              "lookup_p10", "PersonInputs", "WeeklyAdjustment, Prescription", "previous_had_overrides"):
    print(f"  含 {probe!r}: {chk.count(probe)}")
for bad in ("## Task 6:", "## Task 8:", "## Task 1:"):
    print(f"  不含 {bad!r}: {chk.count(bad) == 0}")

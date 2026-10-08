"""commit ① 的消息文件（UTF-8 无 BOM）+ git add 逐个文件名 + git commit -F。"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
D = pathlib.Path(__file__).resolve().parent
MSG = D / "_t7f1_msg1.txt"

MSG.write_text("""fix: Plan02 Task7 fix round 1 F1-1 —— prescription 加 label_at_generation 列（控制者错误 #148）

触发 2 的判据逐字是 `current_label != last_prescription.label_at_generation`，而
`LastPrescription` 的五个字段里**只有它没有住址**：`prescription` 的 15 列里没有它，
`assembly_snapshot` 那 12 + 3 个键里也没有它（Task 5 用两条键集守卫钉死了那份契约，
P6-A2 已经为 `previous_had_overrides` 否掉过「往快照加键」这个方案）。于是
`prescription_stage` 只能按 `(student_id, computed_on == generated_on)` 去 `outerjoin`
回读**同一天**的 `stratification_result.label`。三个具体失效形态：

* `_replay_cleanup` 按 `batch_id` 删 `stratification_result` 的行 —— **重放之后那一天的
  分层行可能已经不在了**，join 返回 `NULL` → 触发 2 **静默不成立**（该换处方的时候不换）；
* join 的条件是一个**跨表的隐式契约**，没有任何守卫钉住它；
* 它让「处方的触发判定」依赖另一张表的行还在不在，而 spec §4.3 要的是「任一条结果都能
  离线复算」。

裁定：**加列**。理由与 P6-A3 给 `microcycle_weeks` 快照**完全同构** —— 处方要能离线复算
触发判定，就把判定输入快照在处方行上。#148 的形状是：Task 6 预检时逐个核了
`microcycle_weeks` 有没有住址，却没把 `LastPrescription` 的字段**逐个**对到列上，
只查了触发 3 需要的那一个。

改动：

* `Prescription` 加 `label_at_generation: Mapped[str] = mapped_column(String(20),
  nullable=False)`。**列宽与 CHECK 都与 `stratification_result.label` 同口径**（硬规矩
  #18）：实测那一列就是 `String(20)` + `_in_domain("label", LABELS,
  "ck_stratification_result_label")`，最长者 `insufficient_data` 是 **17** 字符；
  CHECK 的值域**直接引 `StratificationResult.LABELS`**、不在 `Prescription` 上另立第二份
  词表（单一所有者，故 `Prescription` 上**没有** `LABELS` 常量），约束名
  `ck_prescription_label_at_generation` 照本表既有风格。值域**含** `insufficient_data`
  而生产上写不进那一档（Z0 闸门在 upsert 之前就 `continue`），**刻意不收窄成三个** ——
  收窄就要另立词表。
* `generate_prescriptions` 的 upsert 值字典填它，来源就是**当天刚写好的**
  `stratification_result.label`（在本循环手上的 `result` 里，不需要额外查询）。
* `_previous_prescriptions` 去掉那个 `outerjoin`、返回 `dict[int, Prescription]`，
  `load_only` 多留一列（6 → **7** 个小列）；`_last_prescription_of` 改读本列，于是它成了
  一个**纯映射**、不再碰库，那个「标签查不到」的 `ValueError` 分支**结构上不可达**、已删。

TDD 取证（硬规矩 #65）：新增
`tests/pipeline/test_prescription_stage.py::test_trigger_2_survives_the_deletion_of_that_days_stratification_row`
—— 生成一张处方 → **删掉那一天的 `stratification_result` 行** → 换一个标签跑第二天 →
断言触发 2 **仍然成立**（`trigger_reasons == ["layer_changed"]`）。**改之前当场红**：

    ValueError: 学生 1 在 2025-09-15 没有分层结果，而他当天有一张处方（id=1）：
    触发 2 要比的是「生成当时的标签」…

**改之后绿**。它**取代**了首轮的
`test_a_prescription_whose_stratification_row_is_gone_fails_loudly`：同一个数据形状，
断言的是**相反**的结论（原先那条钉的 `ValueError` 分支在加了本列之后不可达）。
另新增
`tests/db/test_models.py::test_prescription_label_at_generation_shares_its_domain_with_the_label_column`
钉住同宽 / 同值域 / NOT NULL 无缺省 / 两条 CHECK 的值域部分逐字相同。
**变异取证**（硬规矩 #83：前后 `rmtree __pycache__` + `PYTHONDONTWRITEBYTECODE=1` +
`-p no:cacheprovider`）：把新列的 `String(20)` 改成 `String(16)` → 那条新守卫与 Plan 01
的列宽**遍历**测试同时红（`2 failed, 58 passed`），还原后 `60 passed`。即新列
**自动被那道遍历测试覆盖**（它带 CHECK，故反解得出值域），不必另找地方钉列宽。

连带（硬规矩 #66）：

* `prescription` **15 → 16** 列（运行时口径 `len(list(Prescription.__table__.columns))`）；
  `_in_domain_columns` 的 docstring「今天 **17** 列」→ **18** 列并补上新列名；
  `_prescription_fields` 补 `label_at_generation="red"`。
* `PIPELINE_TABLES` 仍是 **11** 张，但加一列改变了那个 canonical sha256。本夹具
  （`CFG`：60 人 / `seed=20250828` / 缺省注入，`D = 2025-09-15`）本轮亲跑
  （`canonical_dump` 逐字复用，n=1，两遍 `run_daily`，`first == second` 成立）：

      表集合          sha256                                                            行数合计
      9 张（Plan 01）  1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952   882
      11 张（Task 7）  2b2649add55205e668c40e287f91592c0bcfcd68599d725030a68fc2400456df   942

  **9 张那一行逐字未变**（本轮只动 `prescription` 一张表，而它不在那 9 张里）；
  11 张 `05c5b2aa…` → `2b2649ad…`（**列变而行数不变**，仍是 882 + 60 张处方 + 0 条周微调）。
  `test_daily.py` 的取证表已按此更新，供控制者回填账本与 spec §1.3。
* `prescription_stage.py` 的模块 docstring 里有两处**失效引用**（`_current_prescriptions`
  与 `_labels_at`，这两个函数今天都不存在）改成 `_previous_prescriptions`。
* `test_backfill.py` 那条 `elapsed < 60` 的 docstring 按硬规矩 #42 补写实测与测量条件
  （F1-2）：fix round 1 复测 **n=3、不带 `--cov`** = **28.86 / 29.05 / 29.59 s** →
  最小余量 `60 / 29.59 = ` **2.03×**；带 `--cov=app.domain --cov-branch`（n=1）
  `elapsed = ` **57.25 s** → 余量 **1.05×**，被既有的 `sys.gettrace()` 钩子如实 skip
  （**钩子今天仍在、仍生效**，skip 出自 `tests/pipeline/test_backfill.py:182`）。
  **没有放宽那条断言**（放宽等于取消守卫）。

全量：**750 passed**（不带 `--cov`）/ **749 passed, 1 skipped**（带 `--cov`，
skip 的就是上面那条）；`app/domain` 覆盖率 **951 stmts / Miss 0 / 274 branch / BrPart 0
/ 100%**（本轮不新增 domain 代码，分母逐字未变）。三个禁区指纹逐字不变、
`golden_cases.json` 未改（27 346 B / sha16 `8C787701EA70EF90`）、`pe.db` 不存在、
`backend/data/` 零改动。
""", encoding="utf-8", newline="")
print(f"消息文件 {MSG.name} = {len(MSG.read_bytes())} B")

FILES = [
    "backend/app/db/models/prescription.py",
    "backend/app/pipeline/prescription_stage.py",
    "backend/tests/db/test_models.py",
    "backend/tests/pipeline/test_prescription_stage.py",
    "backend/tests/pipeline/test_daily.py",
    "backend/tests/pipeline/test_backfill.py",
]


def git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        sys.exit(1)
    return r.stdout.strip()


for f in FILES:
    git("add", "--", f)
    print("  added", f)
print(git("diff", "--cached", "--stat"))
git("commit", "-F", str(MSG))
print(git("log", "--oneline", "-1"))
print(git("status", "--porcelain", "--", "backend"))

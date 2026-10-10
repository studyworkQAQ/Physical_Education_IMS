"""Task 7 变异自证：三条守卫各打一次变异，验它们**真的会红**（不是恒绿）。

做法（硬规矩：不用 git checkout 还原文件，用 python 从内存里的原字节写回）：
1. 读原字节；2. 打变异；3. 跑目标测试；4. 写回原字节；5. 复核字节逐字相同。

三条变异：
  M1  ``_persist`` 的「先 SELECT 后 INSERT」换成 ``repo.upsert``
      → 目标 ``test_running_the_same_day_twice_does_not_duplicate_anything``
        （第二遍会走更新分支，把一条已经 handled 的预警静默改回 pending）
  M2  ``_rpe_rows`` 的 ORDER BY 把课次时间换成 submitted_at
      → 目标 ``test_a_late_submission_does_not_move_the_window_key_anchor``
  M3  ``_write_auto_adjustment`` 绕过 WeeklyFactor 值对象、直接写 AUTO_REDUCTION_FACTOR
      → 目标 ``test_the_auto_factor_passes_through_weekly_factor_validation``
        （Plan 02 留给 Plan 03 的第 4 条的守卫；把系数变异成 0.0 之后它必须红）
"""
import pathlib
import subprocess
import sys

BACKEND = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend")
TARGET = BACKEND / "app" / "pipeline" / "alert_stage.py"

ORIGINAL = TARGET.read_bytes()

M1_OLD = """        existing = session.scalar(
            select(Alert).where(
                Alert.rule_id == hit.rule_id.value,
                Alert.subject_key == hit.subject_key,
                Alert.semester_id == semester_id,
                Alert.window_key == hit.window_key,
            )
        )
        if existing is not None:
            deduped += 1"""
M1_NEW = """        existing = None
        if True:
            deduped += 0"""

M2_OLD = """        .order_by(
            RpeRecord.student_id,
            ClassSession.session_date,
            ClassSession.period,
            RpeRecord.submitted_at,
            RpeRecord.id,
        )"""
M2_NEW = """        .order_by(
            RpeRecord.student_id,
            RpeRecord.submitted_at,
            RpeRecord.id,
        )"""

M3_OLD = """    factor = WeeklyFactor(
        week=week,
        factor=AUTO_REDUCTION_FACTOR,
        reason=rule_id.value,
        source=AUTO_SOURCE,
    )"""
M3_NEW = """    class _NoValidation:
        week = week
        factor = AUTO_REDUCTION_FACTOR
        reason = rule_id.value
        source = AUTO_SOURCE

    factor = _NoValidation()"""

MUTATIONS = [
    ("M1 先SELECT后INSERT → 恒不 dedup（等价于换 upsert 的更新分支）", M1_OLD, M1_NEW,
     "test_running_the_same_day_twice_does_not_duplicate_anything"),
    ("M2 ORDER BY 课次时间 → submitted_at", M2_OLD, M2_NEW,
     "test_a_late_submission_does_not_move_the_window_key_anchor"),
    ("M3 绕过 WeeklyFactor 值对象", M3_OLD, M3_NEW,
     "test_the_auto_factor_passes_through_weekly_factor_validation"),
]


def run(test_name: str) -> tuple[int, str]:
    target = "tests/pipeline/test_alert_stage.py"
    if test_name:
        target = f"{target}::{test_name}"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", target,
         "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    tail = [line for line in proc.stdout.splitlines() if line.strip()][-1:]
    return proc.returncode, (tail[0] if tail else "")


try:
    for label, old, new, test_name in MUTATIONS:
        text = ORIGINAL.decode("utf-8")
        assert text.count(old) == 1, f"{label}: 变异锚点命中 {text.count(old)} 次（应为 1）"
        TARGET.write_bytes(text.replace(old, new).encode("utf-8"))
        code, tail = run(test_name)
        verdict = "RED（守卫有效）" if code != 0 else "GREEN ⚠️（守卫恒绿！）"
        print(f"{label}\n    目标 {test_name}\n    退出码 {code} → {verdict}\n    {tail}")
        # 顺带跑整个文件：确认变异没有把文件搞崩（收集期错误同样会让退出码非 0，
        # 那种「红」不能算守卫有效）
        code_all, tail_all = run("")
        print(f"    整个文件：退出码 {code_all} → {tail_all}")
finally:
    TARGET.write_bytes(ORIGINAL)

print()
print("还原后字节逐字相同:", TARGET.read_bytes() == ORIGINAL)
code, tail = run("test_the_same_trigger_raises_one_alert_not_three")
print(f"还原后复跑一条：退出码 {code} → {tail}")

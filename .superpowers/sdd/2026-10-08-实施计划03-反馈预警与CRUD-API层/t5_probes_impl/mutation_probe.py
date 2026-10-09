"""变异自证（Plan 03 Task 5）：把 10 处口径逐个改坏，验证「新守卫有牙」。

纪律：
* 备份原**字节**到 TEMP，还原时 write_bytes 写回（硬规矩 #46：绝不用 git checkout，
  core.autocrlf 会重写工作树）；
* try/finally 保证任何一次失败都把文件还原；
* 每个变异只跑它**该**红的那一条测试（快，2 s 一条），RED 才算有牙；
* 变异是**字符串精确替换**，替换前先断言原文本恰好出现 1 次（否则说明锚点漂了，
  那一次变异无效、必须响亮报出来而不是静默跳过）。
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

BACKEND = pathlib.Path(__file__).resolve().parents[1]
TEMP = pathlib.Path(tempfile.gettempdir()) / "t5_mutation_backup"
TEMP.mkdir(exist_ok=True)

ROUTERS = BACKEND / "app" / "api" / "routers" / "feedback.py"
INIT = BACKEND / "app" / "api" / "routers" / "__init__.py"
MODELS = BACKEND / "app" / "db" / "models" / "feedback.py"
SCHEMAS = BACKEND / "app" / "api" / "schemas" / "feedback.py"

FEEDBACK_TESTS = "tests/api/test_feedback.py"

#: (说明, 目标文件, 原文本, 变异后文本, 该红的测试 nodeid 片段)
MUTATIONS = [
    ("M1 late 的闭区间改成半开（> → >=）：22:00:00 整点会被判迟",
     ROUTERS, "late=submitted_at.time() > CHECKIN_DEADLINE",
     "late=submitted_at.time() >= CHECKIN_DEADLINE",
     "test_the_checkin_deadline_is_a_closed_interval_at_22_00"),

    ("M2 完成率分子不再排除 late",
     ROUTERS, "            and not row.late\n", "",
     "test_late_rest_day_and_backfilled_rows_do_not_count"),

    ("M3 完成率分子不再排除补卡（submitted_at 与 log_date 不一致）",
     ROUTERS, "            and row.submitted_at.date() == row.log_date\n", "",
     "test_late_rest_day_and_backfilled_rows_do_not_count"),

    ("M4 分母改成无条件的 len(sheet.sessions)（不取与学期周的交集）",
     ROUTERS,
     "        if day in training_days:\n            expected.append(day)",
     "        if True:\n"
     "            expected.extend(d for d in training_days if d not in expected)",
     "test_training_days_outside_the_queried_week_do_not_count"),

    ("M5 折返百分位的方向反了（数比自己**快**的人）",
     ROUTERS, "slower = sum(1 for value in sample if value > seconds)",
     "slower = sum(1 for value in sample if value < seconds)",
     "test_squat_score_is_the_count_and_shuttle_score_is_the_within_section_percentile"),

    ("M6 include 顺序反过来（泛型在特例之前）",
     INIT, "api_router.include_router(feedback_router)\napi_router.include_router(prescription_router)\napi_router.include_router(catalog_router)",
     "api_router.include_router(catalog_router)\napi_router.include_router(feedback_router)\napi_router.include_router(prescription_router)",
     "test_the_normalized_route_is_not_swallowed_by_the_generic_read_route"),

    ("M7 open-rpe 每次都换口令（幂等被破坏）",
     ROUTERS, "    already_open = row.rpe_opened and row.rpe_token is not None",
     "    already_open = False",
     "test_open_rpe_twice_keeps_the_first_token"),

    ("M8 综合分把缺失的一项当 0",
     ROUTERS,
     '                "composite": (\n                    None if squat is None or raw_shuttle is None\n                    else round((squat + raw_shuttle) / 2, SCORE_PRECISION)\n                ),',
     '                "composite": round(((squat or 0.0) + (raw_shuttle or 0.0)) / 2,\n                                    SCORE_PRECISION),',
     "test_a_null_shuttle_time_stays_out_of_the_percentile_and_gets_a_null_score"),

    ("M9 SOURCES 词表里去掉 demo（DDL 文本守卫应当红）",
     MODELS, 'SOURCES: set[str] = {"checkin", "lepao", "demo"}',
     'SOURCES: set[str] = {"checkin", "lepao"}',
     "test_the_source_check_rejects_a_value_outside_the_pinned_domain"),

    ("M9b 同上，但看**后果**：演示生成器写 source=\"demo\" 会当场 CHECK 失败",
     MODELS, 'SOURCES: set[str] = {"checkin", "lepao", "demo"}',
     'SOURCES: set[str] = {"checkin", "lepao"}',
     "demo_feedback"),

    ("M10 没人交时 mean_rpe 返回 0 而不是 None（把「不知道」讲成「0」）",
     ROUTERS,
     '            sum(record.rpe for record in records) / len(records) if records else None',
     '            sum(record.rpe for record in records) / len(records) if records else 0.0',
     "test_rpe_status_lists_who_has_not_submitted"),
]

#: M9b 要看的是**后果**（演示生成器写 ``source="demo"`` 会不会当场撞 CHECK），
#: 故它的目标文件不是 test_feedback.py 而是 test_demo_data.py
OVERRIDDEN_TARGETS = {
    "M9b": ("tests/test_demo_data.py", "demo_feedback"),
}


def run(target_file: str, keyword: str) -> tuple[bool, str]:
    """跑 ``pytest -k <keyword> <target_file>``，返回 (是否 RED, 摘要行)。"""
    cmd = [sys.executable, "-m", "pytest", target_file, "-q", "-k", keyword,
           "--tb=no", "-p", "no:cacheprovider"]
    proc = subprocess.run(cmd, cwd=str(BACKEND), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    tail = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    summary = tail[-1] if tail else "(no output)"
    # ⚠️ 区分「测试红了」与「文件语法坏了」：后者是**假 RED**（collection error 也
    #    返回非 0），而一个语法错误说明变异锚点选错了位置，必须报出来而不是记功。
    if proc.returncode == 0:
        return False, summary
    if "failed" in summary:
        return True, summary
    return None, summary     # None = ERROR / 无法判定


def main() -> int:
    touched = sorted({m[1] for m in MUTATIONS})
    backups = {}
    for path in touched:
        dest = TEMP / path.name
        shutil.copyfile(path, dest)
        backups[path] = (dest, path.read_bytes())
    results = []
    try:
        for label, path, old, new, keyword in MUTATIONS:
            text = path.read_text(encoding="utf-8")
            count = text.count(old)
            if count != 1:
                results.append((label, "INVALID", f"锚点出现 {count} 次（应恰好 1 次）"))
                continue
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
            target, kw = OVERRIDDEN_TARGETS.get(
                label.split()[0], (FEEDBACK_TESTS, keyword))
            red, summary = run(target, kw)
            verdict = {True: "RED", False: "GREEN(!!)", None: "ERROR(!!)"}[red]
            results.append((label, verdict, summary))
            path.write_bytes(backups[path][1])   # 立刻还原，避免污染下一个变异
    finally:
        for path, (_dest, raw) in backups.items():
            path.write_bytes(raw)
        # 复核还原是否逐字节成功
        for path, (_dest, raw) in backups.items():
            assert path.read_bytes() == raw, f"还原失败：{path}"

    print()
    print("=" * 78)
    red_count = sum(1 for _, verdict, _ in results if verdict == "RED")
    for label, verdict, summary in results:
        print(f"{verdict:11s} {label}")
        print(f"            └─ {summary}")
    print("=" * 78)
    print(f"RED {red_count} / {len(results)}"
          f"（GREEN(!!) = 守卫没牙，INVALID = 锚点漂了）")
    print("还原复核：全部逐字节相同 ✅")
    return 0 if red_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

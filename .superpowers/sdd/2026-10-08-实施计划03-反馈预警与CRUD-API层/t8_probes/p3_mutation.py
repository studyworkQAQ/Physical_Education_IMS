"""T8 探针 3：``app/domain/report.py`` 的变异自证（Ruling 1 不要求，但 Task 2/3/4/5/7
的实现者都自己加了一轮，控制者五次都采纳）。

做法：把 ``app/domain/report.py`` 备份到 TEMP，逐条改一个字符/一个数，
跑 ``tests/domain/test_report.py``，断言**至少一条红**，然后从 TEMP 写回原字节
（⚠️ 不用 git checkout，硬规矩 #46：它会按 core.autocrlf 重写工作树）。

口径：每一条变异都记「哪几条测试红了」，红了才算这条守卫有牙。
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

BACKEND = pathlib.Path(__file__).resolve().parents[4] / "backend"
TARGET = BACKEND / "app" / "domain" / "report.py"
TEST = "tests/domain/test_report.py"
BACKUP = pathlib.Path(tempfile.mkdtemp(prefix="t8_mut_")) / "report.py.orig"

ORIGINAL = TARGET.read_bytes()
shutil.copyfile(TARGET, BACKUP)
print("备份 =", BACKUP, BACKUP.stat().st_size, "字节；原文件", len(ORIGINAL), "字节")

MUTATIONS = [
    ("M1 建议的低 RPE 边界从严格改成闭合（< → <=）",
     "    if mean_rpe is not None and mean_rpe < CLASS_RPE_LOW_MAX:",
     "    if mean_rpe is not None and mean_rpe <= CLASS_RPE_LOW_MAX:"),
    ("M2 大屏的中断阈值改成预警那一个（3 → 2）",
     "SCREEN_GAP_DAYS: int = 3", "SCREEN_GAP_DAYS: int = 2"),
    ("M3 大屏的 RPE 阈值改成预警那一个（8 → 9）",
     "SCREEN_RPE_MAX: int = 8", "SCREEN_RPE_MAX: int = 9"),
    ("M4 建议步长改成与自动减量同一个数（10 → 20）",
     "SUGGESTION_STEP_PCT: int = 10", "SUGGESTION_STEP_PCT: int = 20"),
    ("M5 周级均值改成「日均值再平均」（加权口径被换掉）",
     "flat = [rpe for submissions in week.values.values() for rpe in submissions]",
     "flat = [sum(s) / len(s) for s in week.values.values() if s]"),
    ("M6 entered 与 left 对调（流动方向反了）",
     '            entered[now].append(student_id)\n            left[before].append(student_id)',
     '            left[now].append(student_id)\n            entered[before].append(student_id)'),
    ("M7 空日画成 0 而不是 None",
     "            None\n            if not submissions\n            else {",
     "            {\"day\": day, \"mean\": 0.0, \"submissions\": 0}\n            if not submissions\n            else {"),
    ("M8 一层无人可测时 rate 给 0.0 而不是 None",
     "                None\n                if not values\n                else round(sum(values) / len(values), RATE_PRECISION)",
     "                round(sum(values) / len(values), RATE_PRECISION)\n                if values\n                else 0.0"),
    ("M9 相对变化的分母去掉 abs（负分把方向翻过来）",
     "(newer - older) / abs(older) * 100.0", "(newer - older) / older * 100.0"),
    ("M10 old == 0 不再被当成「判不了」（除零 → ZeroDivisionError）",
     "if older is None or newer is None or not older:", "if older is None or newer is None:"),
    ("M11 进步榜不截断（Top10 变成全员）",
     '"top": improved[:PROGRESS_BOARD_TOP_N],', '"top": improved,'),
    ("M12 建议的优先级反过来（先判低 RPE）",
     "    if class_rpe_high:\n        return SUGGESTION_REDUCE\n    if mean_rpe is not None and mean_rpe < CLASS_RPE_LOW_MAX:\n        return SUGGESTION_INCREASE",
     "    if mean_rpe is not None and mean_rpe < CLASS_RPE_LOW_MAX:\n        return SUGGESTION_INCREASE\n    if class_rpe_high:\n        return SUGGESTION_REDUCE"),
    ("M13 名单不排序（幂等断言会红）",
     "for student_id in sorted(set(labels_now) | set(labels_prev)):",
     "for student_id in set(labels_now) | set(labels_prev):"),
    ("M14 分层分布改成稀疏（0 计数的层不出现）",
     "counts = dict.fromkeys(LAYERS, 0)", "counts = {}"),
    ("M15 预警汇总的级别改成稀疏",
     "summary = {level: dict.fromkeys(statuses, 0) for level in LEVELS}",
     "summary = {}"),
    ("M16 delta 在不可测时给 0.0（「持平」的谎）",
     "    if current is None or previous is None:\n        return None",
     "    if current is None or previous is None:\n        return 0.0"),
    ("M17 peak_rpe 缺失时补 0 而不是 None",
     'peak = max(rpes.get(student_id) or (), default=None)',
     'peak = max(rpes.get(student_id) or (), default=0)'),
    ("M18 完成率精度改成 2（与 api 层那一处不再相等）",
     "RATE_PRECISION: int = 4", "RATE_PRECISION: int = 2"),
    ("M19 大屏异常名单不排序",
     "for student_id in sorted(set(gap_days) | set(rpes)):",
     "for student_id in set(gap_days) | set(rpes):"),
    ("M20 进步榜的并列不按学生 id 打 tie-breaker",
     'key=lambda entry: (-entry["change_pct"], entry["student_id"]),',
     'key=lambda entry: -entry["change_pct"],'),
    ("M21 进步榜的退步名单也截断到 Top10",
     '"regressed": regressed,', '"regressed": regressed[:PROGRESS_BOARD_TOP_N],'),
    ("M22 上周不存在时把 flow 当成「上周一个人都没有」",
     "    if labels_prev is None:\n        return {",
     "    if False:\n        return {"),
    ("M23 换层判定从 != 改成 is not（同一层也算流动）",
     "        elif now != before:", "        elif now is not before:"),
    ("M24 完成率 round 的位数用 RPE_PRECISION（2）",
     "else round(sum(values) / len(values), RATE_PRECISION)",
     "else round(sum(values) / len(values), RPE_PRECISION)"),
]

results = []
for label, old, new in MUTATIONS:
    text = TARGET.read_text(encoding="utf-8")
    occurrences = text.count(old)
    if occurrences != 1:
        results.append((label, "SKIP", f"锚点命中 {occurrences} 次（要恰好 1 次），本条没跑"))
        continue
    TARGET.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TEST, "-q", "--no-header", "-x", "--tb=no"],
        cwd=BACKEND, capture_output=True, text=True,
    )
    tail = [ln for ln in proc.stdout.splitlines() if " passed" in ln or " failed" in ln
            or " error" in ln]
    names = sorted({ln.split(" ")[0] for ln in proc.stdout.splitlines()
                    if ln.startswith("FAILED ")})
    if proc.returncode == 0:
        results.append((label, "**SURVIVED**", tail[-1] if tail else "(无输出)"))
    else:
        results.append((label, "killed", f"{tail[-1] if tail else '?'} | {names[:3]}"))
    TARGET.write_bytes(ORIGINAL)

print("\n" + "=" * 100)
for label, verdict, detail in results:
    print(f"{verdict:14s} {label}\n{'':14s}   {detail}")
killed = sum(1 for _l, v, _d in results if v == "killed")
survived = [r[0] for r in results if r[1] == "**SURVIVED**"]
skipped = [r[0] for r in results if r[1] == "SKIP"]
print("=" * 100)
print(f"合计 {len(results)} 条：killed {killed}、SURVIVED {len(survived)}、SKIP {len(skipped)}")
if survived:
    print("存活的：", survived)
if skipped:
    print("跳过的：", skipped)

# 还原复核（按字节）
assert TARGET.read_bytes() == ORIGINAL, "还原失败！"
print("还原复核：字节逐字相等 ✓（", len(ORIGINAL), "字节）")
print("backend/pe.db 存在?", (BACKEND / "pe.db").exists())

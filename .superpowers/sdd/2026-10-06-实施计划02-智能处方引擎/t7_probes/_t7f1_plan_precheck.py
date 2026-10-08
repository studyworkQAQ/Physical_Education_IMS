"""F1-3 前置取证：控制者说本轮已改的 4 处，逐处在树上核一遍（改前）。"""
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[4]
REL = "Document/2026-10-06-实施计划02-智能处方引擎.md"
src = (ROOT / REL).read_text(encoding="utf-8")

STALE = {
    "更正① Task7 Step1 的『valid_to 关账』": "`valid_to` 关账",
    "更正① Task6 决定的『并关账 valid_to』": "并关账 `valid_to`",
    "更正② 变异②的『重放翻倍测试红』": "重放翻倍测试红",
    "更正③ 表定义里有没有 label_at_generation": "label_at_generation",
    "更正④ skipped_reasons 的 assembly_error": "assembly_error",
    "补① Task8 的 WeeklyAdjustment import 路径":
        "from app.db.models.prescription import WeeklyAdjustment",
    "补① Task8 的 weekly_factors_of": "weekly_factors_of",
}
print("=== 改前：计划正文实测命中次数 ===")
for k, v in STALE.items():
    print(f"  {k:44s} {src.count(v)}")

out = subprocess.run(["git", "status", "--porcelain", "--", REL], cwd=ROOT,
                     capture_output=True, text=True, encoding="utf-8")
print(f"\ngit status --porcelain -- {REL}\n  -> {out.stdout!r}  (空 = 相对 HEAD 未改动)")
head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                      capture_output=True, text=True, encoding="utf-8").stdout.strip()
print(f"  HEAD = {head}")
print(f"  文件 {len((ROOT / REL).read_bytes())} B / {src.count(chr(10))} 行")

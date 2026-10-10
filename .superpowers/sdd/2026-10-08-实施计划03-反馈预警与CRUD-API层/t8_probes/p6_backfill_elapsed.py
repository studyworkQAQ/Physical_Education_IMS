"""T8 探针 6：按账本既有口径实测 ``test_backfill_500_students_under_90_seconds`` 的 ``elapsed``。

取证手段逐字照 Plan 03 Task 5 的那一条（test_backfill.py:162-165）：
「把阈值临时改成必然红的 ``1``、从 pytest 的 assert 输出里读回真值，跑完改回
——不留 print、不留插件」。

⚠️ 测量条件也逐字照那一条：Windows / CPython 3.11.1 / SQLAlchemy 2.1.3 /
本地 SQLite 文件（不是 :memory:）；``elapsed`` 只夹 ``run_backfill`` 那一段；
**不带** ``--cov``、无任何 trace 钩子；**全量** ``python -m pytest -q``。

⚠️ 还原用 python 从内存里存的原字节写回，**不用 git checkout**
（硬规矩 #46：git checkout 会按 core.autocrlf 重写工作树）。
"""
import pathlib
import re
import subprocess
import sys
import time

BACKEND = pathlib.Path(__file__).resolve().parents[4] / "backend"
TARGET = BACKEND / "tests" / "pipeline" / "test_backfill.py"

ORIGINAL = TARGET.read_bytes()
CRLF = bytes([13, 10])
print("test_backfill.py 的行尾：CRLF =", ORIGINAL.count(CRLF),
      " LF =", ORIGINAL.count(bytes([10])))
# ⚠️ 按**字节**匹配，两种行尾各试一次（硬规矩 #89 的扩写：数行尾用 read_bytes()）
ANCHORS = [
    b"    assert elapsed < 90, elapsed\r\n",
    b"    assert elapsed < 90, elapsed\n",
]
ANCHOR = next((a for a in ANCHORS if ORIGINAL.count(a) == 1), None)
assert ANCHOR is not None, f"锚点不唯一或不存在：{[ORIGINAL.count(a) for a in ANCHORS]}"
PATCHED = b"    assert elapsed < 1, elapsed" + ANCHOR[len(b"    assert elapsed < 90, elapsed"):]
TARGET.write_bytes(ORIGINAL.replace(ANCHOR, PATCHED))
print("已把阈值临时改成 1（必然红），跑完写回原字节；锚点 =", repr(ANCHOR))

VALUES = []
try:
    for run in (1, 2):
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--no-header", "--tb=line"],
            cwd=BACKEND, capture_output=True, text=True,
        )
        wall = time.perf_counter() - t0
        text = proc.stdout + proc.stderr
        # assert 输出形如： "assert 50.42 < 1" 或末尾那行 "E   assert 50.42 < 1"
        got = re.findall(r"assert ([0-9]+\.[0-9]+) < 1", text)
        summary = [ln for ln in text.splitlines()
                   if re.search(r"\d+ (passed|failed)", ln)]
        print(f"\n--- 第 {run} 轮（全量墙钟 {wall:.2f}s）---")
        print("  摘要:", summary[-1] if summary else "(无)")
        print("  elapsed 读数:", got)
        if got:
            VALUES.append(float(got[0]))
finally:
    TARGET.write_bytes(ORIGINAL)
    assert TARGET.read_bytes() == ORIGINAL, "还原失败！"
    print("\n还原复核：test_backfill.py 字节逐字相等 ✓（", len(ORIGINAL), "字节）")
    print("  阈值那一行:", [ln for ln in TARGET.read_text(encoding='utf-8').splitlines()
                          if "assert elapsed" in ln])

if VALUES:
    lo, hi = min(VALUES), max(VALUES)
    mean = sum(VALUES) / len(VALUES)
    print("\n" + "=" * 72)
    print(f"n={len(VALUES)}  elapsed = {VALUES}  区间 {lo:.2f}–{hi:.2f}s  均值 {mean:.2f}s")
    print(f"  基线（Plan 03 Task 5，同口径）：47.33 / 47.96 s，均值 47.65 s")
    print(f"  差：{mean - 47.645:+.2f}s = {(mean / 47.645 - 1) * 100:+.1f}%")
    print(f"  对阈值 90 的余量：{90 / hi:.2f}×（按最坏值 {hi:.2f}s 算）")
    print(f"  ⚠️ 硬规矩 #42 的线是 2×；Plan 03 Task 5 结案时的余量是 1.88×")
print("=" * 72)
print("backend/pe.db 存在?", (BACKEND / "pe.db").exists())

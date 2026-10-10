"""取证：整学期回放（500 人 ×112 业务日）在接入 Alert 阶段之后的实际耗时。

手段照账本 Ruling 12 那一条（「把阈值临时改成必然红的 1、从 pytest 的 assert 输出里
读回真值，跑完改回——不留 print、不留插件」）。跑完按字节还原并复核。
"""
import pathlib
import subprocess
import sys

BACKEND = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend")
TARGET = BACKEND / "tests" / "pipeline" / "test_backfill.py"
ORIGINAL = TARGET.read_bytes()
OLD = "assert elapsed < 90"
NEW = "assert elapsed < 1"

text = ORIGINAL.decode("utf-8")
assert text.count(OLD) == 1, f"锚点命中 {text.count(OLD)} 次（应为 1）"

try:
    TARGET.write_bytes(text.replace(OLD, NEW).encode("utf-8"))
    proc = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/pipeline/test_backfill.py::test_backfill_500_students_under_90_seconds",
         "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    lines = [line for line in proc.stdout.splitlines()
             if "elapsed" in line or "assert" in line.lower() or "passed" in line
             or "failed" in line]
    print("退出码 =", proc.returncode)
    for line in lines[:20]:
        print("   ", line.strip())
finally:
    TARGET.write_bytes(ORIGINAL)

print()
print("还原后字节逐字相同:", TARGET.read_bytes() == ORIGINAL)

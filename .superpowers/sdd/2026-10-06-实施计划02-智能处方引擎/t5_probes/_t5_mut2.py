"""控制者独立复跑变异 ②（删掉 safety.py 的 needs_review = True）。

按硬规矩 #83：跑测试前 rmtree 所有 __pycache__，并设 PYTHONDONTWRITEBYTECODE=1。
六步：M0 全绿 -> 变异 -> 必须红 -> 还原 -> sha256 逐字相同 -> 重跑全绿。
"""
import hashlib
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
TARGET = BACKEND / "app" / "domain" / "prescription" / "safety.py"
KEXPR = "needs_review"

ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16].upper()


def clean_pyc():
    n = 0
    for d in BACKEND.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)
        n += 1
    return n


def run(tag):
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-k", KEXPR, "--no-header", "-p", "no:cacheprovider"],
        cwd=str(BACKEND), env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = [l for l in r.stdout.strip().split("\n") if l.strip()][-1:]
    print(f"  [{tag}] exit={r.returncode}  {tail[0] if tail else '(无输出)'}")
    return r


orig = TARGET.read_text(encoding="utf-8")
h0 = sha(TARGET)
print(f"[0] safety.py sha16={h0}  bytes={len(orig.encode('utf-8'))}")
print(f"    清掉 __pycache__ 目录 {clean_pyc()} 个；PYTHONDONTWRITEBYTECODE=1")

print("[1] M0 —— 不变异，必须先全绿")
r0 = run("M0")
assert r0.returncode == 0, "M0 就不绿，尺子本身有问题，停止"

OLD = "                        needs_review = True"
NEW = "                        needs_review = None"
assert orig.count(OLD) == 1, f"锚点命中 {orig.count(OLD)} 次，不是 1"
print(f"[2] 锚点长度 = {len(OLD)}，替换串长度 = {len(NEW)}  "
      f"-> 等长? {len(OLD) == len(NEW)}（**刻意等长**，正好复现硬规矩 #83 的陷阱条件："
      f"等长改动 + 同一秒 → CPython 的 (mtime 截断到秒, size) 失效判据不触发）")

TARGET.write_text(orig.replace(OLD, NEW), encoding="utf-8", newline="")
h1 = sha(TARGET)
print(f"[3] 变异后 sha16={h1}  变了? {h1 != h0}")
clean_pyc()
print("[4] 变异后跑 —— 必须红")
r1 = run("MUT")
red = r1.returncode != 0
failed = [l.strip() for l in r1.stdout.split("\n") if l.startswith("FAILED") or "assert" in l]
print(f"    红? {red}")
for l in failed[:6]:
    print(f"      {l[:160]}")

TARGET.write_text(orig, encoding="utf-8", newline="")
h2 = sha(TARGET)
print(f"[5] 还原后 sha16={h2}  与原始逐字相同? {h2 == h0}")
assert h2 == h0, "还原失败，工作树被污染"
clean_pyc()
print("[6] 还原后重跑 —— 必须全绿")
r2 = run("RESTORED")
assert r2.returncode == 0, "还原后仍红，说明有残留"

print()
print(f"结论：变异② {'真的会变红（尺子有效）' if red else '⚠️ 不变红（尺子恒绿，守卫是假的）'}")
print(f"      sha256 三重还原 {h0} -> {h1} -> {h2}，首尾一致 = {h0 == h2}")

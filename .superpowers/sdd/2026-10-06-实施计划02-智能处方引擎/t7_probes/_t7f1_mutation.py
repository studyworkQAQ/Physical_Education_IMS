"""变异取证（硬规矩 #83）：把新列的 String(20) 改成 String(16) —— 17 字符的
``insufficient_data`` 塞不下。预期红：① 新加的专责守卫；② Plan 01 那道列宽**遍历**测试
（它反解 CHECK 得到值域，故新列自动被它覆盖）。跑完立刻还原。
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
P = BACKEND / "app" / "db" / "models" / "prescription.py"

OLD = "    label_at_generation: Mapped[str] = mapped_column(String(20), nullable=False)"
NEW = "    label_at_generation: Mapped[str] = mapped_column(String(16), nullable=False)"

src = P.read_text(encoding="utf-8")
assert src.count(OLD) == 1, src.count(OLD)


def clean_pyc():
    for d in BACKEND.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)


def run(*a):
    return subprocess.run([sys.executable, "-m", "pytest", "-q", *a,
                           "-p", "no:cacheprovider"],
                          cwd=BACKEND, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


try:
    clean_pyc()
    P.write_text(src.replace(OLD, NEW), encoding="utf-8", newline="\r\n")
    r = run("tests/db/test_models.py", "tests/pipeline/test_prescription_stage.py")
    tail = [ln for ln in r.stdout.splitlines() if ln.startswith("FAILED") or " failed" in ln or " passed" in ln]
    print("=== 变异：String(20) -> String(16) ===")
    for ln in tail:
        print("  " + ln)
finally:
    P.write_text(src, encoding="utf-8", newline="\r\n")
    clean_pyc()
    back = P.read_text(encoding="utf-8")
    assert back.count(OLD) == 1 and back.count(NEW) == 0
    r2 = run("tests/db/test_models.py", "tests/pipeline/test_prescription_stage.py")
    print("=== 还原后 ===")
    print("  " + r2.stdout.splitlines()[-1])
    print(f"  文件 {len(P.read_bytes())} B")

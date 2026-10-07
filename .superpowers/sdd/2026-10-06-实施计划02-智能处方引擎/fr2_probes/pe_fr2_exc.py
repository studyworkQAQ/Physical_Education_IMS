"""越界相对导入在**运行时**抛什么？两个守卫的 docstring 现在都写 ValueError，先亲跑核实。"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(tempfile.mkdtemp(prefix="pe_fr2_exc_"))
try:
    for rel in ("app", "app/domain"):
        (root / rel).mkdir(parents=True)
        (root / rel / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "domain" / "x.py").write_text(
        "from ...seed import generate\n", encoding="utf-8")
    runner = root / "run.py"
    runner.write_text("import app.domain.x\n", encoding="utf-8")
    out = subprocess.run([sys.executable, str(runner)], cwd=str(root),
                         capture_output=True, env={**__import__("os").environ,
                                                   "PYTHONIOENCODING": "utf-8"})
    err = out.stderr.decode("utf-8", "replace")
    print("returncode =", out.returncode)
    print("stderr 末两行:")
    for line in [ln for ln in err.splitlines() if ln.strip()][-2:]:
        print("   ", line)
    print()
    print("python -V:", subprocess.run([sys.executable, "-V"], capture_output=True).stdout.decode().strip())
finally:
    import shutil
    shutil.rmtree(root, ignore_errors=True)

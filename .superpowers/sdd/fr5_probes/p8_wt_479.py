"""P8 — Minor 2：在 $env:TEMP 的 git worktree 上亲验「be0f1af^ 上删掉越界守卫 -> 479 条全绿」。

两次全量跑：
  (a) worktree 原样            -> 预期 479 passed
  (b) 两份的 `if level - 1 > len(package): return None` 都删掉 -> 预期仍 479 passed、rc 0
跑完 `git worktree remove --force`。全程不碰主工作树。
"""
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
WT = pathlib.Path(os.environ["TEMP"]) / "pe_fr5_wt_479"

GUARD = "    if level - 1 > len(package):\n"
FILES = ["tests/architecture/test_domain_purity.py", "tests/architecture/test_layering.py"]


def run(args, cwd):
    return subprocess.run(args, cwd=str(cwd), capture_output=True)


print("be0f1af^ =", run(["git", "rev-parse", "--short", "be0f1af^"], ROOT).stdout.decode().strip())

if WT.exists():
    run(["git", "worktree", "remove", "--force", str(WT)], ROOT)
    shutil.rmtree(WT, ignore_errors=True)
run(["git", "worktree", "prune"], ROOT)

r = run(["git", "worktree", "add", "--detach", str(WT), "be0f1af^"], ROOT)
print("worktree add rc =", r.returncode, r.stderr.decode("utf-8", "replace")[:300])
print("worktree HEAD =", run(["git", "rev-parse", "--short", "HEAD"], WT).stdout.decode().strip())

backend = WT / "backend"


def pytest_run(tag):
    p = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=str(backend),
                       capture_output=True)
    out = p.stdout.decode("utf-8", "replace").strip().splitlines()
    print("  [%s] rc=%d  末行=%s" % (tag, p.returncode, out[-1] if out else "<no output>"))
    fails = [l for l in out if l.startswith("FAILED") or l.startswith("ERROR")]
    for l in fails[:6]:
        print("      %s" % l[:160])
    return p.returncode, (out[-1] if out else "")


print("\n=== (a) worktree 原样 ===")
pytest_run("a 原样")

print("\n=== (b) 两份都删掉越界守卫 ===")
for rel in FILES:
    p = backend / rel
    t = p.read_text(encoding="utf-8")
    n = t.count(GUARD)
    assert n == 1, (rel, n)
    # 连同它下面那两行（注释 + return None）一起删，与评审者的做法一致
    lines = t.splitlines(keepends=True)
    i = next(k for k, l in enumerate(lines) if l == GUARD)
    removed = lines[i:i + 3]
    print("  %s 删掉 3 行: %r" % (rel, [x.strip()[:60] for x in removed]))
    del lines[i:i + 3]
    p.write_text("".join(lines), encoding="utf-8", newline="")
rc, last = pytest_run("b 删守卫")
print("\n判读：rc == 0 且末行是 '479 passed' -> 「be0f1af^ 上 479 条全绿」为真：",
      rc == 0 and "479 passed" in last)

print("\n=== 清理 worktree ===")
r = run(["git", "worktree", "remove", "--force", str(WT)], ROOT)
print("worktree remove rc =", r.returncode, r.stderr.decode("utf-8", "replace")[:300])
run(["git", "worktree", "prune"], ROOT)
print("WT 还存在?", WT.exists())
print("git worktree list:")
print(run(["git", "worktree", "list"], ROOT).stdout.decode("utf-8", "replace"))
print("主工作树 git status --short =", repr(run(["git", "status", "--short"], ROOT).stdout.decode("utf-8", "replace")))
print("主工作树 HEAD =", run(["git", "rev-parse", "--short", "HEAD"], ROOT).stdout.decode().strip())

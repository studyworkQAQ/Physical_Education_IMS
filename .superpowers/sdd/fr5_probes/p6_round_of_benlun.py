"""P6 — 12 处「本轮」各属于哪一轮 fix round：逐个 commit 的 -U0 diff 里找新增行。"""
import subprocess, pathlib

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
COMMITS = [("6a2938f", "fix round 1"), ("1fa9941", "fix round 2"),
           ("be0f1af", "fix round 3"), ("6784d57", "fix round 4")]
FILES = ["backend/app/pipeline/daily.py",
         "backend/tests/architecture/test_domain_purity.py",
         "backend/tests/architecture/test_layering.py",
         "backend/tests/db/test_models.py"]

# 当前 HEAD 上这 12 处的行内容（用 P5 之前那次 grep 的口径重新定位，不硬编码行号）
targets = {}
for f in FILES:
    txt = (ROOT / f).read_text(encoding="utf-8")
    for i, line in enumerate(txt.splitlines(), 1):
        if "本轮" in line:
            targets.setdefault(f, []).append((i, line.strip()))

for f, lst in targets.items():
    print("### %s  (%d 处)" % (f, len(lst)))
    for ln, content in lst:
        print("  :%d | %s" % (ln, content[:110]))
    print()

print("=== 逐个 commit 的 -U0 diff 里含「本轮」的新增行 ===")
owner = {}
for sha, label in COMMITS:
    d = subprocess.run(["git", "diff", "-U0", sha + "^", sha, "--"] + FILES,
                       cwd=ROOT, capture_output=True)
    text = d.stdout.decode("utf-8", "replace")
    cur = None
    print("--- %s (%s) ---" % (sha, label))
    for line in text.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            if "本轮" in line:
                key = line[1:].strip()
                print("   [%s] %s" % (cur, key[:120]))
                owner[key] = (sha, label)
print()
print("=== 归属（后写的 commit 覆盖前一个）===")
for f, lst in targets.items():
    for ln, content in lst:
        key = content
        hit = owner.get(key)
        if hit is None:
            # 允许「这一行在后续轮次被改写」的情况：按最长公共子串粗匹配
            cand = [k for k in owner if k[:40] == content[:40]]
            hit = owner[cand[0]] if cand else None
        print("  %-52s :%-4d -> %s" % (pathlib.Path(f).name, ln,
                                        ("%s %s" % hit) if hit else "**未在任何一轮的新增行里**"))

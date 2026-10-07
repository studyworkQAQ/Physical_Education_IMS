import subprocess, pathlib, sys

repo = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
d = subprocess.run(["git", "diff", "-U0", "ad1d190", "6784d57", "--", "backend"],
                   cwd=repo, capture_output=True)
text = d.stdout.decode("utf-8", "replace")
cur = None
newln = 0
hits = []
for line in text.splitlines():
    if line.startswith("+++ b/"):
        cur = line[6:]
    elif line.startswith("@@"):
        # parse new start line
        part = line.split("+")[1].split(" ")[0]
        if "," in part:
            start = int(part.split(",")[0])
        else:
            start = int(part)
        newln = start
    elif line.startswith("+") and not line.startswith("+++"):
        if "本轮" in line:
            hits.append((cur, newln, line[1:]))
        newln += 1
    elif line.startswith("-") or line.startswith("---"):
        pass
    else:
        newln += 1

print("added-line 本轮 hits:", len(hits))
for f, n, l in hits:
    print("%-60s %5d| %s" % (f, n, l.strip()[:150]))

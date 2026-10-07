import ast, collections, hashlib, pathlib, subprocess, sys

ROOT = pathlib.Path(".").resolve()
out = []


def sh(*args, cwd=ROOT):
    r = subprocess.run(list(args), capture_output=True, text=True, cwd=cwd, encoding="utf-8")
    return r.stdout.strip()


# --- 1. 相对导入与扫描面（Task 4 落地后的当前值）---
BACKEND = ROOT / "backend"
rows = []
for p in sorted((BACKEND / "app").rglob("*.py")):
    tree = ast.parse(p.read_bytes().decode("utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.level:
            rows.append((p.relative_to(BACKEND).as_posix(), n.level))
out.append("全仓相对导入 = %d 条，level 分布 = %s" % (
    len(rows), dict(collections.Counter(r[1] for r in rows))))
out.append("  按目录 = %s" % dict(collections.Counter(pathlib.Path(r[0]).parent.as_posix() for r in rows)))
tot = 0
for d in ("pipeline", "db", "domain"):
    n = len(list((BACKEND / "app" / d).rglob("*.py")))
    tot += n
    out.append("  app/%s = %d .py" % (d, n))
out.append("SCANNED_DIRS 合计 = %d" % tot)

# --- 2. 指纹与禁区 ---
for rel, want_b, want_sha in [
    ("backend/data/national_standard_2014.csv", 21412, "D2C8E539E2FA0029"),
    ("backend/data/exercises.yaml", 22739, "3DE598AF38631209"),
    ("backend/data/exercise_equivalence.yaml", 8245, "822CB86A5E998301"),
]:
    b = (ROOT / rel).read_bytes()
    sha = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    out.append("%-46s %6d B  %s  CRLF %d  %s" % (
        rel, len(b), sha, b.count(b"\r\n"),
        "OK" if (len(b), sha, b.count(b"\r\n")) == (want_b, want_sha, 0) else "MISMATCH!!"))
out.append("pe.db 存在? %s   data/seed 文件数 = %d" % (
    (BACKEND / "pe.db").exists(),
    len(list((BACKEND / "data" / "seed").glob("*"))) if (BACKEND / "data" / "seed").exists() else -1))

# --- 3. 新建/修改文件的字节口径 ---
for rel in ["backend/app/domain/prescription/match.py",
            "backend/app/domain/prescription/__init__.py",
            "backend/tests/domain/test_prescription_match.py",
            "backend/tests/domain/test_prescription_exercises.py",
            "backend/tests/test_refdata_prescription.py",
            "backend/tests/architecture/test_domain_purity.py",
            "backend/tests/architecture/test_layering.py"]:
    b = (ROOT / rel).read_bytes()
    out.append("%-58s %7d B  lines %5d  CRLF %5d  bareLF %4d  sha16(raw)=%s  sha16(归一化)=%s" % (
        rel, len(b), len(b.splitlines()), b.count(b"\r\n"),
        b.count(b"\n") - b.count(b"\r\n"),
        hashlib.sha256(b).hexdigest()[:16].upper(),
        hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()))

# --- 4. git ls-files --eol 口径 ---
out.append("--- git ls-files --eol（新建三个 + 修改四个）---")
out.append(sh("git", "ls-files", "--eol", "--",
              "backend/app/domain/prescription/match.py",
              "backend/app/domain/prescription/__init__.py",
              "backend/tests/domain/test_prescription_match.py",
              "backend/tests/domain/test_prescription_exercises.py",
              "backend/tests/test_refdata_prescription.py",
              "backend/tests/architecture/test_domain_purity.py",
              "backend/tests/architecture/test_layering.py"))
out.append("--- check-attr（.gitattributes 覆盖面，硬规矩 #61）---")
out.append(sh("git", "check-attr", "text", "eol", "--",
              "backend/app/domain/prescription/match.py",
              "backend/tests/domain/test_prescription_match.py"))

# --- 5. 计划正文的裸行号核对 ---
plan = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
pl = plan.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
out.append("--- 计划正文 %s（%d B / %d 行）---" % (plan.name, plan.stat().st_size, len(pl)))
for n in (255, 374, 378, 380, 381, 385, 386, 387, 388, 389, 392, 394, 451):
    if 1 <= n <= len(pl):
        out.append("  plan:%-4d| %s" % (n, pl[n - 1][:150]))

# --- 6. 简报里的裸行号 ---
brief = ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-4-brief.md"
bt = brief.read_bytes().decode("utf-8").replace("\r\n", "\n")
import re
qual = re.findall(r"`[A-Za-z_./]+\.py:\d+`", bt)
unqual = re.findall(r"`:\d+(?:-\d+)?`", bt)
out.append("--- 简报里的裸行号 ---")
out.append("  带文件名的 `X.py:NNN` = %d 处: %s" % (len(qual), qual))
out.append("  不带文件名的 `:NNN`   = %d 处: %s" % (len(unqual), unqual))

print("\n".join(out))

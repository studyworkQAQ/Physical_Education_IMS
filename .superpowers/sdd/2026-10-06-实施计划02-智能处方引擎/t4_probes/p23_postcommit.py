import hashlib, pathlib, subprocess

ROOT = pathlib.Path(".").resolve()


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True, cwd=ROOT,
                          encoding="utf-8").stdout.strip()


print("HEAD          =", sh("git", "rev-parse", "--short", "HEAD"))
print("status --short = %r  (行数 %d)" % (sh("git", "status", "--short"),
                                        len([x for x in sh("git", "status", "--short").splitlines() if x.strip()])))
print("log -3:")
print(sh("git", "log", "--oneline", "-3"))
print("\n--- git ls-files --eol（本轮 7 个文件）---")
print(sh("git", "ls-files", "--eol", "--",
         "backend/app/domain/prescription/match.py",
         "backend/app/domain/prescription/__init__.py",
         "backend/tests/domain/test_prescription_match.py",
         "backend/tests/domain/test_prescription_exercises.py",
         "backend/tests/test_refdata_prescription.py",
         "backend/tests/architecture/test_domain_purity.py",
         "backend/tests/architecture/test_layering.py",
         ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-4-report.md"))

print("\n--- blob 字节 vs 工作树字节（归一化后必须相同；.superpowers/** 是 -text 故裸字节也相同）---")
for rel in ["backend/app/domain/prescription/match.py",
            "backend/tests/domain/test_prescription_match.py",
            "backend/tests/domain/test_prescription_exercises.py",
            "backend/app/domain/prescription/__init__.py",
            "backend/tests/test_refdata_prescription.py",
            "backend/tests/architecture/test_domain_purity.py",
            "backend/tests/architecture/test_layering.py",
            ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-4-report.md"]:
    r = subprocess.run(["git", "show", "HEAD:" + rel], capture_output=True, cwd=ROOT)
    blob = r.stdout
    work = (ROOT / rel).read_bytes()
    nb, nw = blob.replace(b"\r\n", b"\n"), work.replace(b"\r\n", b"\n")
    print("  %-70s blob %7d B  work %7d B | 裸字节%s | 归一化%s | blob CRLF %d" % (
        rel.split("/")[-1], len(blob), len(work),
        "同" if blob == work else "异",
        "同 ✓" if nb == nw else "异 ✗",
        blob.count(b"\r\n")))

print("\n--- 禁区四项 ---")
for rel, want_b, want_sha in [
    ("backend/data/national_standard_2014.csv", 21412, "D2C8E539E2FA0029"),
    ("backend/data/exercises.yaml", 22739, "3DE598AF38631209"),
    ("backend/data/exercise_equivalence.yaml", 8245, "822CB86A5E998301"),
]:
    b = (ROOT / rel).read_bytes()
    sha = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    print("  %-46s %6d B %s CRLF %d %s" % (
        rel.split("/")[-1], len(b), sha, b.count(b"\r\n"),
        "OK" if (len(b), sha, b.count(b"\r\n")) == (want_b, want_sha, 0) else "MISMATCH!!"))
print("  pe.db 存在? %s | data/seed 文件数 %d | backend/data 有改动? %s" % (
    (ROOT / "backend/pe.db").exists(),
    len(list((ROOT / "backend/data/seed").glob("*"))),
    sh("git", "diff", "--name-only", "ab075d3", "HEAD", "--", "backend/data") or "无 ✓"))
print("  本轮 commit 动过 backend/data 吗:",
      sh("git", "diff", "--name-only", "3473dc6", "HEAD", "--", "backend/data") or "没有 ✓")
print("  本轮 commit 动过 .gitattributes / app/seed 吗:",
      sh("git", "diff", "--name-only", "3473dc6", "HEAD", "--",
         ".gitattributes", "backend/app/seed") or "没有 ✓")

print("\n--- 表数 ---")
r = subprocess.run(["python", "-c",
                    "from app.db.models import Base; print(len(Base.metadata.tables))"],
                   capture_output=True, text=True, cwd=ROOT / "backend", encoding="utf-8")
print("  Base.metadata.tables =", r.stdout.strip(), r.stderr.strip()[:200])

print("\n--- 临时目录残留 ---")
tmp = [p.name for p in (ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎").iterdir()
       if p.name.startswith("_") or "tmp" in p.name.lower()]
print("  SDD 目录下的 _xxx / tmp 残留:", tmp or "无 ✓")
print("  t4_probes 内容:", sorted(p.name for p in
      (ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/t4_probes").iterdir()))

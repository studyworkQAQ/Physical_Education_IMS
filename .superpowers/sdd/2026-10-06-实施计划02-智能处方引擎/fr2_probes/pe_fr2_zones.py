# -*- coding: utf-8 -*-
"""pe_fr2_zones.py — 行尾完整性 + 禁区复核（python 直接读字节，不走 PowerShell 管道）。"""
import hashlib
import pathlib
import subprocess
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
BK = REPO / "backend"

print("=== 行尾完整性（本轮改过的 4 个文件） ===")
for rel in ("app/pipeline/daily.py", "tests/db/test_models.py",
            "tests/architecture/test_domain_purity.py", "tests/architecture/test_layering.py"):
    b = (BK / rel).read_bytes()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n")
    print("   %-48s bytes=%-6d CRLF=%-4d 裸LF=%-3d BOM=%s  非ASCII乱码=%s"
          % (rel, len(b), crlf, lf - crlf, b[:3] == b"\xef\xbb\xbf",
             b"\xef\xbf\xbd" in b))
    assert lf == crlf, "出现裸 LF"
    assert b"\xef\xbf\xbd" not in b, "出现替换字符（乱码）"

print()
print("=== 禁区 ===")
print("   backend/pe.db exists:", (BK / "pe.db").exists())
seed = BK / "data" / "seed"
files = sorted(seed.rglob("*")) if seed.is_dir() else []
print("   backend/data/seed/ 下的条目数:", len([f for f in files if f.is_file()]))
csv = BK / "data" / "national_standard_2014.csv"
raw = csv.read_bytes()
print("   csv bytes=%d sha256[:16]=%s CRLF=%d" % (len(raw),
      hashlib.sha256(raw).hexdigest()[:16].upper(), raw.count(b"\r\n")))

print()
print("=== git 状态 ===")
for args in (["git", "status", "--short"], ["git", "diff", "--stat"],
             ["git", "diff", "--stat", "6a2938f", "--", "backend/app/seed/", "backend/data/",
              ".gitattributes", "Document/", "backend/app/db/models/", "backend/app/domain/",
              "backend/app/config.py", "backend/app/adapters/", "backend/app/refdata.py"]):
    out = subprocess.run(args, cwd=str(REPO), capture_output=True)
    txt = out.stdout.decode("utf-8", "replace").strip()
    print("   $ %s" % " ".join(args))
    print("     %s" % (txt.replace("\n", "\n     ") if txt else "<空>"))

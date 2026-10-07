# -*- coding: utf-8 -*-
"""Probe P21: 补一个我此前只是推断、没有实测的数：HEAD 上两份都删掉越界守卫，全量末行是什么。"""
import pathlib, shutil, subprocess, sys, tempfile, hashlib
ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
G = ["tests/architecture/test_domain_purity.py", "tests/architecture/test_layering.py"]
before = {f: hashlib.sha256((ROOT / "backend" / f).read_bytes()).hexdigest() for f in G}
TMP = pathlib.Path(tempfile.mkdtemp(prefix="pe_head_mut_"))
COPY = TMP / "backend"
shutil.copytree(ROOT / "backend", COPY, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.db"))
OLD = ("\n    if level - 1 > len(package):\n"
       "        # 越界档：不设这一行，负数切片会从尾部切出非空 anchor、把越界折成更浅的错误绝对串\n"
       "        return None\n")
for f in G:
    p = COPY / f
    s = p.read_text(encoding="utf-8")
    assert s.count(OLD) == 1, (f, s.count(OLD))
    p.write_text(s.replace(OLD, "\n"), encoding="utf-8")
r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider"],
                   capture_output=True, text=True, encoding="utf-8", cwd=str(COPY))
print("exit =", r.returncode)
print("末行 =", (r.stdout.strip().splitlines() or ["<none>"])[-1])
print("FAILED 行:")
for l in r.stdout.splitlines():
    if l.startswith("FAILED"):
        print("   ", l)
after = {f: hashlib.sha256((ROOT / "backend" / f).read_bytes()).hexdigest() for f in G}
print("\n主工作树 sha256 未变:", all(before[f] == after[f] for f in G),
      {f.split("/")[-1]: after[f][:16] for f in G})
shutil.rmtree(TMP, ignore_errors=True)
print("临时副本已删除:", TMP.exists())

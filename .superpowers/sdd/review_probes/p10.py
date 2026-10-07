# -*- coding: utf-8 -*-
"""Probe P10: 复核两条印在源码里的「改前口子是真的」历史陈述。
 (a) purity:209-210 / layering:197-198 —— 在基线 1fa9941 上删掉越界守卫，479 条全绿
 (b) purity:360 / layering:346        —— 在基线 be0f1af 上把两份 _package_of 改成 parts，全量照样通过
一律用 `git archive` 导出到 $env:TEMP，**不碰主工作树**。"""
import hashlib, pathlib, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
G1 = "backend/tests/architecture/test_domain_purity.py"
G2 = "backend/tests/architecture/test_layering.py"


def export(rev, dest):
    dest.mkdir(parents=True, exist_ok=True)
    blob = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", rev, "backend"],
                          capture_output=True).stdout
    assert blob, "git archive 失败"
    (dest / "a.tar").write_bytes(blob)
    subprocess.run(["tar", "-xf", "a.tar"], cwd=str(dest), check=True, capture_output=True)
    (dest / "a.tar").unlink()
    return dest / "backend"


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def mutate(bk, rel, old, new, tag):
    p = bk / rel
    s = p.read_text(encoding="utf-8")
    n = s.count(old)
    assert n == 1, "%s: %s 里目标串出现 %d 次" % (tag, rel, n)
    p.write_text(s.replace(old, new), encoding="utf-8")


def full_suite(bk):
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider"],
                       capture_output=True, text=True, encoding="utf-8", cwd=str(bk))
    return r.returncode, (r.stdout.strip().splitlines() or ["<no output>"])[-1]


GUARD_OLD = ("\n    if level - 1 > len(package):\n"
             "        # 越界档：不设这一行，负数切片会从尾部切出非空 anchor、把越界折成更浅的错误绝对串\n"
             "        return None\n")
PKG_OLD = '\n    return py.relative_to(BACKEND).with_suffix("").parts[:-1]\n'
PKG_NEW = '\n    return py.relative_to(BACKEND).with_suffix("").parts\n'

TMP = pathlib.Path(tempfile.mkdtemp(prefix="pe_hist_p10_"))
before_real = {f: sha(ROOT / f) for f in (G1, G2)}

print("=== (a) 基线 1fa9941：删掉越界守卫（两份都删），跑全量 ===")
bk = export("1fa9941", TMP / "a")
for f in (G1.replace("backend/", ""), G2.replace("backend/", "")):
    pass
mutate(bk, "tests/architecture/test_domain_purity.py", GUARD_OLD, "\n", "a")
mutate(bk, "tests/architecture/test_layering.py", GUARD_OLD, "\n", "a")
rc, tail = full_suite(bk)
print("  变异后 exit=%d  末行=%s   （源码陈述：479 条全绿）" % (rc, tail))
rc0, tail0 = full_suite(export("1fa9941", TMP / "a0"))
print("  不变异的基线   exit=%d  末行=%s" % (rc0, tail0))

print("\n=== (b) 基线 be0f1af：两份 _package_of 改成 parts，跑全量 ===")
bk = export("be0f1af", TMP / "b")
mutate(bk, "tests/architecture/test_domain_purity.py", PKG_OLD, PKG_NEW, "b")
mutate(bk, "tests/architecture/test_layering.py", PKG_OLD, PKG_NEW, "b")
rc, tail = full_suite(bk)
print("  变异后 exit=%d  末行=%s   （源码陈述：全量测试照样通过 / 481 passed）" % (rc, tail))

print("\n=== 主工作树 sha256 前后（证明一字未动）===")
for f in (G1, G2):
    a = sha(ROOT / f)
    print("  %-46s %s  %s" % (f, a[:16], "UNCHANGED" if a == before_real[f] else "!! CHANGED !!"))

shutil.rmtree(TMP, ignore_errors=True)
print("\n临时导出已删除:", TMP.exists())

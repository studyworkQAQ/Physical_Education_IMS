# -*- coding: utf-8 -*-
"""pe_fr3_blind.py — 复核 Ruling 46 那句「谁删掉 if level - 1 > len(package): return None，
479 条全绿」：把**基线 1fa9941** 的两个守卫文件删掉那一行后跑全量测试。

用完按 HEAD 的 blob 字节还原并核 sha256，全程不用 git checkout / git restore。
用法: python pe_fr3_blind.py <仓库根>
"""
import hashlib
import pathlib
import subprocess
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
BACKEND = REPO / "backend"
FILES = {
    "purity": BACKEND / "tests/architecture/test_domain_purity.py",
    "layering": BACKEND / "tests/architecture/test_layering.py",
}
REL = {t: "backend/tests/architecture/%s" % n for t, n in
       (("purity", "test_domain_purity.py"), ("layering", "test_layering.py"))}


def show(rev, rel):
    r = subprocess.run(["git", "show", "%s:%s" % (rev, rel)], cwd=str(REPO), capture_output=True)
    assert r.returncode == 0, rel
    return r.stdout


HEADB = {t: show("HEAD", REL[t]) for t in FILES}
BASEB = {t: show("1fa9941", REL[t]) for t in FILES}
# ⚠️ core.autocrlf=true：git show 给出的是 blob 里的 LF 版本，工作树是 CRLF 版本。
# 故「工作树应有的字节」= blob 的 \n -> \r\n。差值必须恰等于行数（本轮实测确认）。
HEADW = {t: HEADB[t].replace(b"\n", b"\r\n") for t in FILES}
BASEW = {t: BASEB[t].replace(b"\n", b"\r\n") for t in FILES}
print("=== 字节（blob 是 LF、工作树是 CRLF；差值应恰为行数） ===")
for t in FILES:
    print("  %-9s HEAD blob=%d B / 工作树=%d B / 差=%d，CRLF 行数=%d"
          % (t, len(HEADB[t]), len(HEADW[t]), len(HEADW[t]) - len(HEADB[t]),
             HEADW[t].count(b"\r\n")))
    print("           HEAD sha256[:16]=%s  基线 1fa9941 blob=%d B sha256[:16]=%s"
          % (hashlib.sha256(HEADB[t]).hexdigest()[:16], len(BASEB[t]),
             hashlib.sha256(BASEB[t]).hexdigest()[:16]))
    assert len(HEADW[t]) - len(HEADB[t]) == HEADW[t].count(b"\r\n")
    assert FILES[t].read_bytes() == HEADW[t], (t, "工作树与 HEAD 的 CRLF 版不一致")


def drop_guard(text):
    lines = text.replace("\r\n", "\n").split("\n")
    out, hit, i = [], 0, 0
    while i < len(lines):
        if lines[i] == "    if level - 1 > len(package):":
            assert lines[i + 2] == "        return None"
            hit += 1
            i += 3
            continue
        out.append(lines[i])
        i += 1
    assert hit == 1, hit
    return "\r\n".join(out)


try:
    print()
    print("=== 把基线 1fa9941 的两份 _absolute 删掉越界守卫，跑全量测试 ===")
    for t in FILES:
        mutated = drop_guard(BASEB[t].decode("utf-8")).encode("utf-8")
        assert mutated != BASEB[t]
        FILES[t].write_bytes(mutated)
        print("  %-9s 已写入基线-变异版 %d 字节（基线 %d 字节）" % (t, len(mutated), len(BASEB[t])))
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                       cwd=str(BACKEND), capture_output=True)
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    lines = [l for l in out.splitlines() if l.strip()]
    print("  退出码=%d" % r.returncode)
    for l in lines[-3:]:
        print("   ", l)
    print("  => Ruling 46 那句「479 条全绿」在基线上复现 = %s"
          % ("479 passed" in out and r.returncode == 0))
finally:
    print()
    print("=== 还原成 HEAD 的工作树字节（blob 的 LF -> CRLF） ===")
    for t in FILES:
        FILES[t].write_bytes(HEADW[t])
        got = FILES[t].read_bytes()
        print("  %-9s sha256[:16]=%s 与 HEAD 一致=%s %d 字节 CRLF=%d 裸LF=%d"
              % (t, hashlib.sha256(got).hexdigest()[:16], got == HEADW[t], len(got),
                 got.count(b"\r\n"), got.count(b"\n") - got.count(b"\r\n")))
        assert got == HEADW[t]
    r = subprocess.run(["git", "status", "--short"], cwd=str(REPO), capture_output=True)
    o = r.stdout.decode("utf-8").splitlines()
    print("  git status --short: %d 行 %s" % (len(o), o))
    r = subprocess.run(["git", "log", "--oneline", "-1"], cwd=str(REPO), capture_output=True)
    print("  HEAD = %s" % r.stdout.decode("utf-8").strip())

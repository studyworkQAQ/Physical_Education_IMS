# -*- coding: utf-8 -*-
"""pe_fr3_msgs.py — 取变异后的**断言原文**（docstring 里写的折算值必须来自这里），
并复核 layering docstring 里「真仓 12 条 level==1 相对导入」那句话。

用法: python pe_fr3_msgs.py <仓库根>
"""
import ast
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
NID = {
    "purity": "tests/architecture/test_domain_purity.py::test_absolute_folding_matches_resolve_name",
    "layering": "tests/architecture/test_layering.py::test_absolute_folding_matches_resolve_name",
}
ORIG = {t: p.read_bytes() for t, p in FILES.items()}
SHA = {t: hashlib.sha256(b).hexdigest() for t, b in ORIG.items()}


def restore():
    for t, p in FILES.items():
        p.write_bytes(ORIG[t])
        assert hashlib.sha256(p.read_bytes()).hexdigest() == SHA[t], t


def m2_drop_guard(lines):
    out, hit, i = [], 0, 0
    while i < len(lines):
        if lines[i] == "    if level - 1 > len(package):":
            hit += 1
            i += 3
            continue
        out.append(lines[i])
        i += 1
    assert hit == 1, hit
    return out


def m3_tail(lines):
    out, hit = [], 0
    for l in lines:
        if l == "    tail = module or name":
            out.append("    tail = module")
            hit += 1
        else:
            out.append(l)
    assert hit == 1, hit
    return out


def m4_names(lines):
    out, hit, i = [], 0, 0
    while i < len(lines):
        if lines[i] == "            if node.level and not node.module:":
            j = i + 1
            if lines[j].strip().startswith("#"):
                j += 1
            assert lines[j] == "                for alias in node.names:", lines[j]
            body = lines[j + 1]
            out.append(lines[i])
            if 'yield node.lineno, "", node.level, alias.name' in body:
                out.append('                yield node.lineno, "", node.level, node.names[0].name')
            else:
                out.append('                yield node.lineno, _absolute("", node.level, package,'
                           ' node.names[0].name)')
            hit += 1
            i = j + 2
            continue
        out.append(lines[i])
        i += 1
    assert hit == 1, hit
    return out


for name, mut in (("M2 派单① 删掉越界守卫", m2_drop_guard),
                  ("M3 派单② tail = module", m3_tail),
                  ("M4 额外   names 展开改回一条", m4_names)):
    print()
    print("############ %s ############" % name)
    for t, p in FILES.items():
        restore()
        text = p.read_bytes().decode("utf-8")
        before = ast.dump(ast.parse(text.replace("\r\n", "\n")))
        new = "\r\n".join(mut(text.split("\r\n")))
        p.write_bytes(new.encode("utf-8"))
        after = ast.dump(ast.parse(new.replace("\r\n", "\n")))
        print("  --- %s（AST 变了=%s）---" % (t, before != after))
        assert before != after
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", NID[t]],
                           cwd=str(BACKEND), capture_output=True)
        out = (r.stdout + r.stderr).decode("utf-8", "replace")
        for l in out.splitlines():
            if l.strip().startswith("E ") or "assert" in l and l.strip().startswith("E"):
                print("   ", l.rstrip())
        print("    退出码=%d  汇总=%s"
              % (r.returncode, [l for l in out.splitlines() if l.strip()][-1]))
    restore()

print()
print("=== 复核 layering docstring 的那句「真仓 12 条 level==1 相对导入」 ===")
rows = []
for p in sorted((BACKEND / "app").rglob("*.py")):
    tree = ast.parse(p.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.level:
            rows.append((p.relative_to(BACKEND).as_posix(), n.lineno, n.level, n.module,
                         [a.name for a in n.names]))
print("  真仓 ImportFrom(level>0) 节点数 = %d" % len(rows))
print("  其中 level != 1 的 = %d" % sum(1 for r in rows if r[2] != 1))
print("  其中不在 app/db/models/ 下的 = %d"
      % sum(1 for r in rows if not r[0].startswith("app/db/models/")))
print("  module 为空的 = %d -> %s"
      % (sum(1 for r in rows if r[3] is None), [r for r in rows if r[3] is None]))
print("  前 3 条: %s" % rows[:3])

print()
print("=== 三重还原 ===")
restore()
for t, p in FILES.items():
    b = p.read_bytes()
    print("  %-9s sha256[:16]=%s 一致=%s %d 字节 CRLF=%d 裸LF=%d"
          % (t, hashlib.sha256(b).hexdigest()[:16],
             hashlib.sha256(b).hexdigest() == SHA[t], len(b),
             b.count(b"\r\n"), b.count(b"\n") - b.count(b"\r\n")))
r = subprocess.run(["git", "status", "--short"], cwd=str(REPO), capture_output=True)
print("  git status --short: %s" % (r.stdout.decode("utf-8").splitlines() or "0 行"))

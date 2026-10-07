# -*- coding: utf-8 -*-
"""pe_fr4_mutation.py — Ruling 54 的变异验收（硬规矩 #50 / #51 / #53）。

用法: python pe_fr4_mutation.py <仓库根>

相位：
  M0  对照 GREEN   ：不变异，两条测试必须绿（否则 harness 本身坏了，#53）
  M1  对照「AST 变了、语义没变」：parts[:-1] -> tuple(list(parts)[: len(parts) - 1])
                     两条必须**仍绿** —— 证明尺子不是恒 RED（#53 的 #72 形态）
  M2  派单 ①       ：parts[:-1] -> parts，**只变异 layering**
  M3  派单 ②       ：同一变异，**只变异 purity**
  M4  额外         ：同一变异，两份都变异
  M5  额外         ：变异下只跑**旧的 4 条守卫**，必须全绿 —— 这正是 Ruling 54 说的
                     「守卫假绿、而测试仍然通过」，也是本轮为什么要加那一段断言
  M6  额外         ：把**基线 be0f1af** 的两份文件（含变异）落盘后跑**全量**，
                     必须 481 passed / rc 0 —— 这是断言消息里那句「在本段断言加上之前，
                     这么改一次全量测试都照样通过」的实测依据

每次变异都在**剥 docstring 后的 ast.dump** 上确认「真的改了代码」（派单 ⑤、硬规矩 #53）；
每个相位结束后按**字节**还原并核 sha256；全程不用 git checkout / git restore。
⚠️ 账本记的坑：`git show <commit>:<path>` 给的是 blob 的 **LF** 版，落盘前必须换成 CRLF。
"""
import ast
import hashlib
import pathlib
import subprocess
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
BACKEND = REPO / "backend"
COMMIT = "be0f1af"
FILES = {
    "purity": BACKEND / "tests/architecture/test_domain_purity.py",
    "layering": BACKEND / "tests/architecture/test_layering.py",
}
REL = {t: "backend/tests/architecture/%s" % ("test_domain_purity.py" if t == "purity"
                                             else "test_layering.py") for t in FILES}
#: pytest 的 cwd 是 backend/，故 node id 用**相对 backend/** 的路径（REL 是给 git show 用的）
NID = {t: "%s::test_absolute_folding_matches_resolve_name" % REL[t].split("backend/", 1)[1]
       for t in FILES}
TAG = "test_absolute_folding_matches_resolve_name"
MSG = "_package_of 返回的不是**包**"

ORIG = {t: p.read_bytes() for t, p in FILES.items()}
SHA = {t: hashlib.sha256(b).hexdigest() for t, b in ORIG.items()}
#: 本轮开工前（= 基线 be0f1af 的工作树 CRLF 版）的 sha256[:16]。取自 fr3 报告与本轮开工前
#: 的亲跑测量，用于证明 M6 从 `git show` 取回并归一化的确实是基线，而不是循环自证。
PRE_FR4_SHA = {"purity": "dffa51f460826436", "layering": "a5afd212bd485ef4"}
results = []


def sha(tag):
    return hashlib.sha256(FILES[tag].read_bytes()).hexdigest()


def intact():
    return all(sha(t) == SHA[t] for t in FILES)


def read(tag):
    return FILES[tag].read_bytes().decode("utf-8")


def strip_docs(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            b = node.body
            if (b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant)
                    and isinstance(b[0].value.value, str)):
                node.body = [ast.Pass()] + b[1:]
    return tree


def dump_nodoc(text):
    """剥 docstring 后的 ast.dump —— 派单 ⑤ 要求的口径。"""
    return ast.dump(strip_docs(ast.parse(text.replace("\r\n", "\n"))), include_attributes=False)


def restore(tag):
    FILES[tag].write_bytes(ORIG[tag])
    assert sha(tag) == SHA[tag], (tag, "还原失败")


def apply_mutation(tag, mutate):
    before = read(tag)
    after_text = "\r\n".join(mutate(before.replace("\r\n", "\n").split("\n")))
    FILES[tag].write_bytes(after_text.encode("utf-8"))
    after = read(tag)
    return dump_nodoc(before) != dump_nodoc(after), before != after


def run(targets):
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + list(targets)
    r = subprocess.run(cmd, cwd=str(BACKEND), capture_output=True)
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    lines = [l for l in out.splitlines() if l.strip()]
    return r.returncode, (lines[-1] if lines else ""), out


def check(phase, mutated, want, msg=None):
    rc, tail, out = run([NID[t] for t in ("purity", "layering")])
    print("  pytest 退出码=%d  汇总行=%s" % (rc, tail))
    allok = True
    for tag in ("purity", "layering"):
        got = "RED" if ("FAILED %s" % NID[tag]) in out else "GREEN"
        ok = got == want[tag]
        note = ""
        if want[tag] == "RED":
            if msg and msg not in out:
                ok = False
                note = "（断言文本 %r 未出现 → 不是我们要的那条红）" % msg
            else:
                for l in out.splitlines():
                    if l.lstrip().startswith("E") and "_package_of" in l:
                        print("      断言原文: %s" % l.strip()[:200])
        else:
            if "passed" not in tail:
                ok = False
                note = "（汇总行里没有 passed → 可能是收集错误，不是真绿）"
        allok = allok and ok
        print("    %-9s 期望 %-5s 实测 %-5s %s%s%s"
              % (tag, want[tag], got, "OK" if ok else "!! FAIL", note,
                 "" if tag in mutated else "   ← 未被变异"))
    print("  => %s: %s" % (phase, "PASS" if allok else "FAIL"))
    return allok


# ------------------------------------------------------------------ 变异算子
OLD_RETURN = '    return py.relative_to(BACKEND).with_suffix("").parts[:-1]'


def m_parts(lines):
    """派单 ①/②：parts[:-1] -> parts（返回**模块路径**而不是包）。"""
    out, hit = [], 0
    for l in lines:
        if l == OLD_RETURN:
            out.append('    return py.relative_to(BACKEND).with_suffix("").parts')
            hit += 1
        else:
            out.append(l)
    assert hit == 1, hit
    return out


def m_equiv(lines):
    """语义等价改写：AST 必须变、行为必须不变。"""
    out, hit = [], 0
    for l in lines:
        if l == OLD_RETURN:
            out.append('    parts = py.relative_to(BACKEND).with_suffix("").parts')
            out.append("    return tuple(list(parts)[: len(parts) - 1])")
            hit += 1
        else:
            out.append(l)
    assert hit == 1, hit
    return out


def m_docstring_only(lines):
    """对照：只改 docstring 一个字 —— 剥 docstring 后的 ast.dump 必须**相等**
    （证明 M1/M2 报的「AST 变了」不是尺子恒真）。"""
    out, hit = [], 0
    for l in lines:
        if l == "    \"\"\"``py`` 所在的**包**，以 ``backend/`` 为根的段。":
            out.append("    \"\"\"``py`` 所在的**包**（以 ``backend/`` 为根的段）。")
            hit += 1
        else:
            out.append(l)
    assert hit == 1, hit
    return out


print("=== 原始字节 sha256[:16] ===")
for t in FILES:
    print("  %-9s %s  %d 字节" % (t, SHA[t][:16], len(ORIG[t])))

print()
print("=== 变异算子的 AST 自证（派单 ⑤：剥 docstring 后的 ast.dump 必须前后不等）===")
for t in FILES:
    before = read(t)
    for name, op, want_changed in (("parts[:-1] -> parts", m_parts, True),
                                   ("等价改写", m_equiv, True),
                                   ("只改 docstring", m_docstring_only, False)):
        after = "\r\n".join(op(before.replace("\r\n", "\n").split("\n")))
        changed = dump_nodoc(before) != dump_nodoc(after)
        print("  %-9s %-22s 文本变了=%s 剥docstring后AST变了=%s（应为 %s）%s"
              % (t, name, after != before, changed, want_changed,
                 "OK" if changed == want_changed else "!! FAIL"))
        assert changed == want_changed, (t, name)
results.append(("变异算子 AST 自证", True))

print()
print("=== M0 对照 GREEN（不变异）：尺子必须能报绿 ===")
results.append(("M0 不变异（两条都应绿）", check("M0", set(), {"purity": "GREEN", "layering": "GREEN"})))
assert intact()

print()
print("=== M1 对照「AST 变了、语义没变」：两条必须仍绿（硬规矩 #53）===")
for t in FILES:
    a, tx = apply_mutation(t, m_equiv)
    print("  变异 %-9s 剥docstring后AST变了=%s 文本变了=%s" % (t, a, tx))
    assert a and tx, (t, "变异没真改代码")
results.append(("M1 等价改写（应仍绿）", check("M1", set(FILES), {"purity": "GREEN", "layering": "GREEN"})))
for t in FILES:
    restore(t)
print("  还原后 sha256 一致 = %s" % intact())
assert intact()

for phase, scope in (("M2 派单① parts[:-1]->parts [layering]", ("layering",)),
                     ("M3 派单② parts[:-1]->parts [purity]", ("purity",)),
                     ("M4 额外   parts[:-1]->parts [两份]", ("purity", "layering"))):
    print()
    print("=== %s ===" % phase)
    for t in FILES:
        restore(t)
    for t in scope:
        a, tx = apply_mutation(t, m_parts)
        assert a and tx, (t, phase, "变异没真改代码")
        print("  变异 %-9s 剥docstring后AST变了=%s 文本变了=%s" % (t, a, tx))
    want = {t: ("RED" if t in scope else "GREEN") for t in FILES}
    results.append((phase, check(phase, set(scope), want, MSG)))
    for t in FILES:
        restore(t)
    assert intact(), phase

print()
print("=== M5 额外：变异下**旧的 4 条守卫**仍全绿（这就是 Ruling 54 说的「守卫假绿」）===")
for t in FILES:
    a, tx = apply_mutation(t, m_parts)
    assert a and tx
rc, tail, out = run(["tests/architecture", "-k", "not %s" % TAG])
print("  pytest tests/architecture（排除那条回归测试）退出码=%d  汇总行=%s" % (rc, tail))
print("  => 4 条架构守卫对 _package_of 被改坏**无感** = %s" % (rc == 0))
results.append(("M5 旧守卫无感（应 rc==0）", rc == 0 and "4 passed" in tail))
for t in FILES:
    restore(t)
assert intact()

print()
print("=== M6 额外：基线 %s + 变异 -> 全量测试仍全绿（断言消息里那句话的依据）===" % COMMIT)
base_bytes = {}
for t in FILES:
    r = subprocess.run(["git", "show", "%s:%s" % (COMMIT, REL[t])], cwd=str(REPO), capture_output=True)
    assert r.returncode == 0, REL[t]
    blob = r.stdout.decode("utf-8")
    # ⚠️ blob 是 LF 版；工作树是 CRLF 版，落盘前必须换成 CRLF
    crlf = blob.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    base_bytes[t] = crlf
    ast.parse(crlf.decode("utf-8").replace("\r\n", "\n"))
    print("  %-9s blob(LF)=%d B  换成 CRLF 后=%d B  sha256[:16]=%s"
          % (t, len(r.stdout), len(crlf), hashlib.sha256(crlf).hexdigest()[:16]))
    print("           本轮开工前的工作树 sha256[:16]=%s  相符=%s（证明取到的确实是基线）"
          % (PRE_FR4_SHA[t], hashlib.sha256(crlf).hexdigest()[:16] == PRE_FR4_SHA[t]))
    assert hashlib.sha256(crlf).hexdigest()[:16] == PRE_FR4_SHA[t], (t, "基线 sha256 不符")
    assert b"pkg_offenders" not in crlf, t
    assert crlf.count(b"\r\n") == crlf.count(b"\n"), t
for t in FILES:
    FILES[t].write_bytes("\r\n".join(m_parts(base_bytes[t].decode("utf-8")
                                            .replace("\r\n", "\n").split("\n"))).encode("utf-8"))
rc, tail, out = run([])
print("  pytest -q（全量）退出码=%d  汇总行=%s" % (rc, tail))
results.append(("M6 基线+变异 全量应 481 passed/rc0", rc == 0 and "481 passed" in tail))
for t in FILES:
    restore(t)
assert intact()

print()
print("=== 三重还原取证 ===")
for t in FILES:
    b = FILES[t].read_bytes()
    print("  %-9s sha256[:16]=%s 与原始一致=%s %d 字节 CRLF=%d 裸LF=%d"
          % (t, hashlib.sha256(b).hexdigest()[:16], sha(t) == SHA[t], len(b),
             b.count(b"\r\n"), b.count(b"\n") - b.count(b"\r\n")))
    assert sha(t) == SHA[t]
r = subprocess.run(["git", "-c", "core.quotepath=false", "status", "--short"], cwd=str(REPO), capture_output=True)
print("  git status --short:")
for l in r.stdout.decode("utf-8").splitlines():
    print("    " + l)

print()
print("=== 汇总 ===")
for n, ok in results:
    print("  %-46s %s" % (n, "PASS" if ok else "!! FAIL"))
bad = [n for n, ok in results if not ok]
print("失败项 = %d / %d" % (len(bad), len(results)))
sys.exit(1 if bad else 0)

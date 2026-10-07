# -*- coding: utf-8 -*-
"""pe_fr3_mutation.py — Ruling 46 的变异验收（硬规矩 #50 / #51 / #53）。

用法: python pe_fr3_mutation.py <仓库根>

相位：
  M0  对照 GREEN      ：不变异，两条新测试必须绿（否则 harness 本身坏了，硬规矩 #53）
  M1  对照「AST 变了但语义没变」：把 anchor 的切片算式等价改写，两条新测试必须仍绿
                        —— 证明尺子不是恒 RED（#53 的 #71 形态）
  M2  派单 ①           ：删掉 `if level - 1 > len(package): return None`
  M3  派单 ②           ：`tail = module or name` -> `tail = module`
  M4  额外（超出派单）  ：`_imported_modules` 的逐个 names 展开改回「一个节点只 yield 一条」
                        —— 证明新测试末尾那一段是活的，且旧的 4 条守卫对此**无感**

M2 / M3 / M4 各跑三个变体：只变异 purity、只变异 layering、两份都变异（硬规矩 #51 的证据）。
每次变异都在 AST 上确认「真的改了代码」；每个相位结束后按字节还原并核 sha256。
全程不用 git checkout / git restore。
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
MSG_FOLD = "_absolute 与 importlib.util.resolve_name 不一致"
MSG_NAMES = "一名一条的展开失效"
TAG = "test_absolute_folding_matches_resolve_name"

ORIG = {t: p.read_bytes() for t, p in FILES.items()}
SHA = {t: hashlib.sha256(b).hexdigest() for t, b in ORIG.items()}


def sha(tag):
    return hashlib.sha256(FILES[tag].read_bytes()).hexdigest()


def intact():
    return all(sha(t) == SHA[t] for t in FILES)


def read(tag):
    return FILES[tag].read_bytes().decode("utf-8")


def dump(text):
    return ast.dump(ast.parse(text.replace("\r\n", "\n")))


def restore(tag):
    FILES[tag].write_bytes(ORIG[tag])
    assert sha(tag) == SHA[tag], (tag, "还原失败")


def apply_mutation(tag, mutate):
    before = read(tag)
    FILES[tag].write_bytes("\r\n".join(mutate(before.split("\r\n"))).encode("utf-8"))
    after = read(tag)
    return dump(before) != dump(after), before != after


def run(nodeids):
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + list(nodeids)
    r = subprocess.run(cmd, cwd=str(BACKEND), capture_output=True)
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    lines = [l for l in out.splitlines() if l.strip()]
    return r.returncode, (lines[-1] if lines else ""), out


def check(phase, mutated, want, msg=None):
    """want: {tag: 'RED'/'GREEN'}；msg: 期望 RED 时必须出现的断言文本。"""
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
def m1_equiv(lines):
    """语义等价的算式改写：AST 必须变、行为必须不变。"""
    out, hit = [], 0
    for l in lines:
        if l == "    anchor = package[: len(package) - (level - 1)]":
            out.append("    anchor = package[: len(package) - level + 1]")
            hit += 1
        else:
            out.append(l)
    assert hit == 1, hit
    return out


def m2_drop_guard(lines):
    """派单 ①：删掉 `if level - 1 > len(package): return None`（含它下面那行注释）。"""
    out, hit, i = [], 0, 0
    while i < len(lines):
        if lines[i] == "    if level - 1 > len(package):":
            assert lines[i + 1].strip().startswith("#"), lines[i + 1]
            assert lines[i + 2] == "        return None", lines[i + 2]
            hit += 1
            i += 3
            continue
        out.append(lines[i])
        i += 1
    assert hit == 1, hit
    return out


def m3_tail(lines):
    """派单 ②：`tail = module or name` -> `tail = module`。"""
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
    """额外：`_imported_modules` 的逐个 names 展开改回「一个节点只 yield 第一条」。"""
    out, hit, i = [], 0, 0
    while i < len(lines):
        if lines[i] == "            if node.level and not node.module:":
            j = i + 1
            if lines[j].strip().startswith("#"):
                j += 1
            assert lines[j] == "                for alias in node.names:", lines[j]
            body = lines[j + 1]
            assert body.strip().startswith("yield node.lineno,"), body
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


MUTATIONS = [
    ("M2 派单①  删掉越界守卫", m2_drop_guard, MSG_FOLD),
    ("M3 派单②  tail = module", m3_tail, MSG_FOLD),
    ("M4 额外   names 展开改回一条", m4_names, MSG_NAMES),
]

results = []
print("=== 原始字节 sha256[:16] ===")
for t in FILES:
    print("  %-9s %s  %d 字节" % (t, SHA[t][:16], len(ORIG[t])))

print()
print("=== M0 对照 GREEN（不变异）：尺子必须能报绿 ===")
results.append(("M0 不变异", check("M0", set(), {"purity": "GREEN", "layering": "GREEN"})))
assert intact()

print()
print("=== M1 对照「AST 变了、语义没变」：两条新测试必须仍绿（硬规矩 #53）===")
for t in FILES:
    a, tx = apply_mutation(t, m1_equiv)
    print("  %-9s AST 变了=%s 文本变了=%s" % (t, a, tx))
    assert a and tx, (t, "变异没真改代码")
results.append(("M1 等价改写（应仍绿）", check("M1", set(FILES), {"purity": "GREEN", "layering": "GREEN"})))
for t in FILES:
    restore(t)
print("  还原后 sha256 一致 = %s" % intact())

for name, mut, msg in MUTATIONS:
    print()
    print("=== %s ===" % name)
    for scope in (("purity",), ("layering",), ("purity", "layering")):
        for t in FILES:
            restore(t)
        for t in scope:
            a, tx = apply_mutation(t, mut)
            assert a and tx, (t, name, "变异没真改代码")
            print("  变异 %-9s AST 变了=%s 文本变了=%s" % (t, a, tx))
        want = {t: ("RED" if t in scope else "GREEN") for t in FILES}
        results.append(("%s [%s]" % (name, "+".join(scope)),
                        check("%s [%s]" % (name, "+".join(scope)), set(scope), want, msg)))
        for t in FILES:
            restore(t)
        assert intact(), name

print()
print("=== M4 附带证据：names 展开被改回一条时，旧的 4 条守卫**无感**（仍绿）===")
for t in FILES:
    a, tx = apply_mutation(t, m4_names)
    assert a and tx
rc, tail, out = run(["tests/architecture", "-k", "not %s" % TAG])
print("  pytest tests/architecture（排除新测试）退出码=%d  汇总行=%s" % (rc, tail))
print("  => 旧守卫对这一档无感 = %s（这正是 Ruling 46 说的『仓库里没有断言看着』）" % (rc == 0))
results.append(("M4 旧守卫无感（应 rc==0）", rc == 0))
for t in FILES:
    restore(t)

print()
print("=== 三重还原取证 ===")
for t in FILES:
    b = FILES[t].read_bytes()
    print("  %-9s sha256[:16]=%s 与原始一致=%s %d 字节 CRLF=%d 裸LF=%d"
          % (t, SHA[t][:16], sha(t) == SHA[t], len(b),
             b.count(b"\r\n"), b.count(b"\n") - b.count(b"\r\n")))
    assert sha(t) == SHA[t]
r = subprocess.run(["git", "status", "--short"], cwd=str(REPO), capture_output=True)
print("  git status --short:")
for l in r.stdout.decode("utf-8").splitlines():
    print("    " + l)

print()
print("=== 汇总 ===")
for n, ok in results:
    print("  %-44s %s" % (n, "PASS" if ok else "!! FAIL"))
bad = [n for n, ok in results if not ok]
print("失败项 = %d / %d" % (len(bad), len(results)))
sys.exit(1 if bad else 0)

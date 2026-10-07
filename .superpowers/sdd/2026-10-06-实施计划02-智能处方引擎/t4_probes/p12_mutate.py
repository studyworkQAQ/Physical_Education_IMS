"""Task 4 变异验收 harness（硬规矩 #50/#53/#62/#65，全部**串行**跑）。

相位：M0（不变异，已知 GREEN 的对照）→ MUT-①/②/③/④ → M1（语义等价改写，仍须全绿）。
每个变异：① 字节级写入；② 在**剥掉 docstring 的 ast.dump** 上确认真的改了代码；
③ 跑全量 pytest（记退出码与 failed 清单）；④ 跑 32 格 tally（记分类分布）；
⑤ 按字节还原并核 sha256。
"""
import ast
import collections
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
MATCH = ROOT / "backend" / "app" / "domain" / "prescription" / "match.py"
BACKEND = ROOT / "backend"
ORIG = MATCH.read_bytes()
ORIG_SHA = hashlib.sha256(ORIG).hexdigest()
assert ORIG.count(b"\r\n") == 0, "match.py 应是纯 LF，变异锚点按 \\n 写"
NL = "\n"


def stripped_dump(raw: bytes) -> str:
    """剥掉每一层 docstring 之后的 ast.dump（散文改动不算「真的改了代码」）。"""
    tree = ast.parse(raw.decode("utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree)


BASE_DUMP = stripped_dump(ORIG)

REACHABLE_BLOCK = NL.join([
    "        # ④ UNREACHABLE：读**字段**，不调 is_reachable（理由见模块 docstring 第二节）。",
    "        if not template.reachable:",
    "            return MatchOutcome(",
    "                None,",
    "                MatchStatus.UNREACHABLE,",
    '                f"模板 {template.template_id} 是预留位（reachable: false），"',
    '                f"当前不参与匹配",',
    "            )",
    "",
])

REVIEW_BLOCK = NL.join([
    "        # ⑤ NOT_APPROVED：spec §7.2「review.status != approved 的模板拒绝用于生成」，",
    "        #    措辞照 §11.2 那一行的「模板待审校」（教师端原文）。",
    "        if template.review_status is not ReviewStatus.APPROVED:",
    "            return MatchOutcome(",
    "                None,",
    "                MatchStatus.NOT_APPROVED,",
    '                f"模板待审校（{template.template_id} 的 review.status = "',
    '                f"{template.review_status.value}），拒绝生成处方",',
    "            )",
    "",
])

LAYER_BLOCK = NL.join([
    "    # ① NO_LAYER：Z0 闸门拦下的学生没有分层标签，谈不上匹配（Review Focus 第 3 条）。",
    "    if inp.layer is Layer.INSUFFICIENT:",
    "        return MatchOutcome(None, MatchStatus.NO_LAYER, _NO_LAYER_REASON)",
    "",
])

NO_BUCKET_ANCHOR = "    if inp.dominant_bucket is None:"

SWAP_INSERT = NL.join([
    "    if inp.layer is Layer.GREEN and inp.body_comp_abnormal:",
    '        return MatchOutcome(None, MatchStatus.UNREACHABLE, "MUT-4 顺序对调")',
    "",
    NO_BUCKET_ANCHOR,
])

PHASES = [
    ("M0", None, None, "不变异的已知 GREEN 对照（硬规矩 #53）"),
    ("MUT-1", REACHABLE_BLOCK, "", "删掉 reachable 检查（变异 ①）"),
    ("MUT-2", REVIEW_BLOCK, "", "删掉 review_status 检查（变异 ②）"),
    ("MUT-3", LAYER_BLOCK, "", "删掉 Layer.INSUFFICIENT 分支（变异 ③）"),
    ("MUT-4", NO_BUCKET_ANCHOR, SWAP_INSERT,
     "把 UNREACHABLE 的判据提到 NO_BUCKET 之前（变异 ④，P4-A3 的承重处）"),
    ("M1", "for template_id in sorted(templates):",
     "for template_id in sorted(templates.keys()):",
     "语义等价改写（AST 真变、运行时值不变），仍须全绿"),
]


def tally(raw: bytes) -> str:
    """在**当前落盘的** match.py 上跑 32 格（子进程调 p13_tally_probe.py）。"""
    MATCH.write_bytes(raw)
    probe = pathlib.Path(__file__).resolve().parent / "p13_tally_probe.py"
    r = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True,
                       cwd=ROOT, encoding="utf-8")
    return (r.stdout + r.stderr).strip()


results = []
for name, old, new, note in PHASES:
    print("=" * 78)
    print("相位 %s —— %s" % (name, note))
    if old is None:
        raw = ORIG
    else:
        text = ORIG.decode("utf-8")
        assert text.count(old) == 1, "%s: 锚点命中 %d 次（应为 1）" % (name, text.count(old))
        raw = text.replace(old, new).encode("utf-8")
    MATCH.write_bytes(raw)
    dump = stripped_dump(MATCH.read_bytes())
    changed = dump != BASE_DUMP
    print("  剥 docstring 的 ast.dump 与基线不同？ %s" % changed)
    if name in ("MUT-1", "MUT-2", "MUT-3", "MUT-4"):
        assert changed, "%s 没有真的改到代码（只改了散文？）" % name
    if name == "M1":
        assert changed, "M1 的 AST 没变，说明改写不是真改写（硬规矩 #53）"
    if name == "M0":
        assert not changed, "M0 应当与基线逐字相同"
    print("  sha256[:16] = %s  bytes = %d" % (
        hashlib.sha256(MATCH.read_bytes()).hexdigest()[:16].upper(), len(MATCH.read_bytes())))
    print("  --- 32 格 tally ---")
    t = tally(MATCH.read_bytes())
    for ln in t.splitlines():
        print("   ", ln)
    print("  --- pytest 全量（串行）---")
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"],
                       capture_output=True, text=True, cwd=BACKEND, encoding="utf-8")
    tail = [ln for ln in r.stdout.splitlines() if ln.strip()][-1:]
    failed = sorted({ln.split(" ")[1] for ln in r.stdout.splitlines() if ln.startswith("FAILED ")})
    print("    exit=%d  %s" % (r.returncode, tail[0] if tail else "<no output>"))
    for f in failed:
        print("    FAILED", f)
    results.append((name, changed, r.returncode, tail[0] if tail else "", failed, t))
    MATCH.write_bytes(ORIG)
    back = hashlib.sha256(MATCH.read_bytes()).hexdigest()
    assert back == ORIG_SHA, "%s 之后还原失败：%s != %s" % (name, back, ORIG_SHA)
    print("  已按字节还原，sha256 = %s（与开工时逐字相同）" % back[:16].upper())

MATCH.write_bytes(ORIG)
assert hashlib.sha256(MATCH.read_bytes()).hexdigest() == ORIG_SHA
print("=" * 78)
print("汇总（sha256 已还原 = %s）" % ORIG_SHA[:16].upper())
for name, changed, rc, last, failed, t in results:
    tally_line = [ln for ln in t.splitlines() if ln.startswith("TALLY")]
    mism = [ln for ln in t.splitlines() if ln.startswith("MISMATCH")]
    print("  %-6s ast_changed=%-5s exit=%d  %s  %s  %s" % (
        name, changed, rc, tally_line[0] if tally_line else "", mism[0] if mism else "", last))
    for f in failed:
        print("         FAILED %s" % f)

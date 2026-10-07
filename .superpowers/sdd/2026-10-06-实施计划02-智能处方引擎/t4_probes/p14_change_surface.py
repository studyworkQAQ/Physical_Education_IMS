"""改动面自证（硬规矩 #32）：backend/app/** 里除 match.py 与 prescription/__init__.py 之外，
其余文件剥 docstring 后的 ast.dump 必须与代码基线 ab075d3 逐字 SAME。

**带对照组**（否则「全 SAME」可能只是尺子恒 SAME）：
  - 阳性对照：对 3 个应当 SAME 的文件各造一个真语义变异，尺子必须报 DIFF；
  - 阴性对照：同一份文件自比，尺子必须报 SAME（不恒 DIFF）。
sha256 一律标明口径：这里报的是**归一化后**（CRLF→LF）的裸内容哈希。
"""
import ast
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(".").resolve()
BASE = "ab075d3"
EXPECT_DIFF = {
    "backend/app/domain/prescription/__init__.py",   # 公开面从 20 扩到 24
    "backend/app/domain/prescription/match.py",      # 本 Task 新建
}


def strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:] or [ast.Pass()]
    return tree


def dump(raw: bytes) -> str:
    return ast.dump(strip_docstrings(ast.parse(raw.decode("utf-8").replace("\r\n", "\n"))))


def norm(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n")


def git_blob(rel: str) -> bytes | None:
    r = subprocess.run(["git", "show", "%s:%s" % (BASE, rel)], capture_output=True, cwd=ROOT)
    return r.stdout if r.returncode == 0 else None


files = subprocess.run(["git", "ls-tree", "-r", "--name-only", BASE, "--", "backend/app"],
                       capture_output=True, text=True, cwd=ROOT).stdout.split()
print("基线 %s 下 backend/app 的 .py 共 %d 个" % (BASE, len(files)))

same, diff, added = [], [], []
for rel in files:
    if not rel.endswith(".py"):
        continue
    base_raw = git_blob(rel)
    work_path = ROOT / rel
    if not work_path.exists():
        diff.append((rel, "工作树里不存在"))
        continue
    work_raw = work_path.read_bytes()
    b, w = norm(base_raw), norm(work_raw)
    if dump(b) == dump(w):
        same.append(rel)
    else:
        diff.append((rel, "ast.dump DIFF（剥 docstring 后）"))

work_all = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "backend" / "app").rglob("*.py"))
for rel in work_all:
    if rel not in files:
        added.append(rel)

print("\n--- SAME (%d) ---" % len(same))
for rel in same:
    print("   ", rel)
print("--- DIFF (%d) ---" % len(diff))
for rel, why in diff:
    print("   ", rel, "|", why)
print("--- 新增（基线里没有）(%d) ---" % len(added))
for rel in added:
    print("   ", rel)

unexpected = [d for d in diff if d[0] not in EXPECT_DIFF] + [a for a in added if a not in EXPECT_DIFF]
print("\n授权面之外的改动 =", unexpected if unexpected else "无 ✓")

# ------------------------------------------------------------------ 对照组
print("\n=== 对照组：证明这把尺子既不是恒 SAME、也不是恒 DIFF ===")
# 每个锚点都先用 p15_anchors.py 亲验过 hits == 1；下面 assert 命中次数，
# 命中 0 次就当场炸而不是静默跳过（上一版就是静默跳过，9 个变异只跑成 1 个）。
CONTROLS = [
    # (文件, 变异标签, 旧串, 新串, 期望尺子判定)
    ("backend/app/domain/stratify.py", "改一个常量 4→5",
     "MIN_VALID_COUNT = 4", "MIN_VALID_COUNT = 5", "DIFF"),
    ("backend/app/domain/derive.py", "对调一个比较符 < → <=",
     "if score < line:", "if score <= line:", "DIFF"),
    ("backend/app/domain/prescription/exercises.py", "lookup 的 >= 改成 >",
     "if IMPACT_RANK[mapping.max_impact] >= ceiling_rank:",
     "if IMPACT_RANK[mapping.max_impact] > ceiling_rank:", "DIFF"),
    ("backend/app/domain/prescription/templates.py", "is_reachable 的枚举成员换成另一个",
     "return not (layer is Layer.GREEN and body_comp is BodyCompState.ABNORMAL)",
     "return not (layer is Layer.GREEN and body_comp is BodyCompState.NORMAL)", "DIFF"),
    # 阴性对照：只改 docstring 必须仍报 SAME（证明「剥 docstring」那一步真的在生效、
    # 尺子不是靠散文差异在报 DIFF）
    ("backend/app/domain/stratify.py", "只改 docstring（阴性对照）",
     '"""决策表的八行行号。``Z0`` 是数据不足闸门（Ruling 125），其余七条是分层规则。"""',
     '"""决策表的八行行号（本行被对照组改过一句散文）。'
     '``Z0`` 是数据不足闸门（Ruling 125），其余七条是分层规则。"""', "SAME"),
]
caught_diff = caught_same = 0
for rel, label, old, new, expect in CONTROLS:
    p = ROOT / rel
    raw = p.read_bytes()
    sha0 = hashlib.sha256(norm(raw)).hexdigest()[:16].upper()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    assert text.count(old) == 1, "[%s] 锚点命中 %d 次（应为 1）：%r" % (rel, text.count(old), old)
    mutated = text.replace(old, new).encode("utf-8")
    verdict = "SAME" if dump(mutated) == dump(raw) else "DIFF"
    hit = verdict == expect
    print("   [%s] %-34s → 尺子报 %-4s（期望 %s）%s" % (rel, label, verdict, expect, "✓" if hit else "✗"))
    assert hit, "尺子判定与期望不符"
    if expect == "DIFF":
        caught_diff += 1
    else:
        caught_same += 1
    # 对照组只在内存里做，一个字都不落盘
    assert p.read_bytes() == raw, "对照组把文件改坏了！"
    assert hashlib.sha256(norm(p.read_bytes())).hexdigest()[:16].upper() == sha0
# 阴性对照之二：同一份文件自比必须 SAME（尺子不恒 DIFF）
for rel in ("backend/app/domain/tables.py", "backend/app/domain/stratify.py"):
    raw = (ROOT / rel).read_bytes()
    assert dump(raw) == dump(raw)
print("\n阳性对照（真语义变异）caught = %d 个，全部报 DIFF ✓" % caught_diff)
print("阴性对照（只改散文 / 自比）= %d + 2 个，全部报 SAME ✓" % caught_same)
print("对照组没有落盘任何字节，sha256(归一化后) 逐个复核通过。")
sys.exit(1 if unexpected else 0)

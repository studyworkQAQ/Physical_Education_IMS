"""落盘闸门（硬规矩 #48 升级口径）：对本轮**所有**被编辑过的文件做一次总核。

背景：本轮实测到 3 次「SearchReplace 报成功并回显 diff、而磁盘逐字未写」
（task-4-report.md，sha256 前后同为 A673C075FC056050）。故这里对 7 个文件逐个做
① 双向串查（新串命中 >=1 且旧串残留 == 0）② 缩进敏感处另加 repr 抽查
③ 任何「0 命中」的结论先用一个已知存在的串验证查询本身有效。
"""
import ast
import hashlib
import pathlib

FILES = {
    "backend/app/domain/prescription/match.py": dict(
        have=["class MatchStatus(str, Enum):", "def match_template(inp: MatchInput, templates: Mapping[str, Template]) -> MatchOutcome:",
              '_NO_LAYER_REASON = f"有效项不足 {MIN_VALID_COUNT} 项，本日不分层"',
              "for template_id in sorted(templates):",
              "from .templates import BodyCompState, ReviewStatus, Template\n",
              "from app.domain.stratify import MIN_VALID_COUNT, Layer",
              "from app.domain.indicators import WEAKNESS_ITEMS"],
        not_have=["__all__", "is_reachable(", "from .templates import BodyCompState, ReviewStatus, Template, WeaknessBucket"],
        probe="MatchStatus.NO_LAYER",
    ),
    "backend/app/domain/prescription/__init__.py": dict(
        have=["from .match import (", '"MatchStatus",', '"match_template",',
              "共 **24** 个", "``assert len(...) == 24``",
              "``BodyCompState`` 取自 ``.templates`` 而不是 ``.match``",
              "Task 4 那 4 个名字"],
        not_have=["共 **20** 个。Task 4 建", "``assert len(...) == 20``",
                  "``BodyCompState`` / ``WeaknessBucket`` 取自"],
        probe="from app.domain.stratify import Layer",
    ),
    "backend/tests/domain/test_prescription_match.py": dict(
        have=["_MATRIX_32 = [", "_EXPECTED_TALLY = {",
              "def test_thirty_two_cell_matrix_is_classified_cell_by_cell():",
              "def test_the_load_bearing_cell_green_none_abnormal_is_no_bucket_not_unreachable():",
              "def test_no_layer_reason_is_verbatim_the_stratify_z0_reason():",
              "from app.domain.stratify import _REASON, RuleId  # 触私有名：本条要比较的正是它"],
        not_have=[],
        probe="MatchStatus.MATCHED",
    ),
    "backend/tests/domain/test_prescription_exercises.py": dict(
        have=["def test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable():",
              'assert synthetic.lookup("a", ImpactLevel.LOW) is None',
              "Ruling 107-1"],
        not_have=[],
        probe="rp.load_equivalence()",
    ),
    "backend/tests/test_refdata_prescription.py": dict(
        have=['assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 24, "基线是 24 个名字，抄漏了就当场红"',
              "assert len(set(names)) == 24",
              '("MatchStatus", "app.domain.prescription.match")',
              '("match_template", "app.domain.prescription.match")',
              '"app.domain.prescription.match",\n)',
              "**本条加入之前**（Task 2 fix round 2 落地，账本 Ruling 107-2）",
              "**Task 4 只搬走了 ``lookup()`` 的分支测试**",
              "只对本包拥有的三个模块成立",
              "不守这 24 个名字各自的**取值**"],
        not_have=["def test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable():",
                  "== 20", "MatchResult", "今天看着它的本来只有两条",
                  "只对本包拥有的两个模块成立", "不守这 20 个名字",
                  "    EquivalenceMapping,\n", "    EquivalenceTable,\n"],
        probe="_PRESCRIPTION_PUBLIC_BASELINE = [",
    ),
    "backend/tests/architecture/test_domain_purity.py": dict(
        have=["**Task 1 fix round 5 为 Task 4 的形状埋的一格**",
              "real_py = sorted(BACKEND.rglob(\"*.py\"))",
              "want_pkg = py.relative_to(BACKEND).parent.parts",
              "assert relative_seen >= 16",
              '"app.domain.prescription.match",',
              "**Task 4 落地后的当前值是 18 条**",
              "level 分布仍是 ``{1: 18}``",
              "本 Task（Task 4，建 ``match.py``）落地时同一条命令数出 **10** 个",
              "它是那 12 格矩阵的补充、不是替代"],
        not_have=["pkg_cases = [", "Task 2 会新建 app/domain/prescription/ 子包（今天不存在）",
                  "Task 2 的形状（fix round 5 新加", "Task 3 的 ``match.py`` 一写",
                  "17 条", "{1: 17}", "Task 2 才会出现的形状"],
        probe="def test_absolute_folding_matches_resolve_name():",
    ),
    "backend/tests/architecture/test_layering.py": dict(
        have=["**Task 1 fix round 5 为 Task 4 的形状埋的一格**",
              "real_py = sorted(BACKEND.rglob(\"*.py\"))",
              "want_pkg = py.relative_to(BACKEND).parent.parts",
              "assert relative_seen >= 16",
              '"app.domain.prescription.match",',
              "**Task 4 落地后的当前值是 18 条**",
              "**Task 4 落地后全仓是 18 条**",
              "Plan02 Task 4 建 match.py 后 → [('db', 11), ('domain', 10), ('pipeline', 7)] 28",
              "仍剩 **17…21** 个 .py",
              "它是那 12 格矩阵的补充、不是替代",
              "本段刻意**不复用** :func:`_imported_modules`"],
        not_have=["pkg_cases = [", "Task 2 会新建 app/domain/prescription/ 子包（今天不存在）",
                  "Task 2 的形状（fix round 5 新加", "17 条", "{1: 17}",
                  "Task 2 才会出现的形状", "它不扫真仓文件"],
        probe="def test_absolute_folding_matches_resolve_name():",
    ),
    ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-4-report.md": dict(
        have=["## 11. 我发现的控制者错误", "CE-7", "### 13.1 commit 之后补录",
              "本报告按硬规矩 #74 **不逐字复述**被撤销的"],
        not_have=["若写相对导入会变 17", "NO_BUCKET:4, UNREACHABLE:5", "MatchResult"],
        probe="硬规矩",
    ),
}

allok = True
for rel, spec in FILES.items():
    p = pathlib.Path(rel)
    b = p.read_bytes()
    t = b.decode("utf-8").replace("\r\n", "\n")
    print("=" * 90)
    print("%s\n  %d B / %d 行 / CRLF %d / sha16(raw) %s / sha16(归一化) %s" % (
        rel, len(b), len(b.splitlines()), b.count(b"\r\n"),
        hashlib.sha256(b).hexdigest()[:16].upper(),
        hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()))
    ctrl = t.count(spec["probe"])
    print("  control probe %-52r -> %d %s" % (spec["probe"][:50], ctrl,
                                             "✓" if ctrl >= 1 else "✗ 查询本身无效！"))
    allok &= ctrl >= 1
    for s in spec["have"]:
        n = t.count(s)
        flag = "HAVE  " if n >= 1 else "MISS!!"
        print("  %s %d  %r" % (flag, n, s[:74]))
        allok &= n >= 1
    for s in spec["not_have"]:
        n = t.count(s)
        flag = "CLEAN " if n == 0 else "RESID!!"
        print("  %s %d  %r" % (flag, n, s[:74]))
        allok &= n == 0
    if rel.endswith(".py"):
        try:
            ast.parse(t)
            print("  ast.parse OK")
        except SyntaxError as e:
            print("  ast.parse FAILED:", e)
            allok = False

print("=" * 90)
print("ALL OK" if allok else "*** FAILED ***")

"""Task 9 落地脚本 02：GC14 之后「13」的连带清扫（**只改当前事实的散文，不改历史陈述**）。

纪律：
* **字节级替换**（read_bytes → replace → write_bytes）：这些文件的工作树行尾是**混合**的
  （`git ls-files --eol` 实测 run_stratify.py / percentile.py / stratify.py /
  test_golden_cases.py / test_stratify.py / test_percentile.py /
  test_prescription_stage.py 是 w/crlf，而 feedback.py / report.py / report_stage.py 是 w/lf），
  按文本读写会把行尾统一掉、制造一个巨大的无意义 diff（硬规矩 #89 扩写：数行尾用 read_bytes）。
* **每一处断言恰好命中一次**：抄错当场响，不静默漏改。
* **历史陈述刻意不动**（绑时点的话改了就变假）：
  - test_golden_cases.py 的「Plan 02 Task 9 那轮逐条复核」改成显式绑时点，而不是把 13 抹成 14；
  - run_stratify.py:595「代价是 13 例的 "bmi" 全 None」是 Task 7 时点的陈述，不动；
  - test_prescription_stage.py:302/304 那两句「13 例夹具的顶层没有它们 / 三档安全触发在 13 例里
    一档都走不到」同为 Task 7 时点，不动。
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"

#: ⚠️ Python 3.11 的 f-string 表达式里**不能有反斜杠**，故两个行尾字节串提成常量。
CRLF_BYTES = b"\r\n"
LF_BYTES = b"\n"

EDITS: dict[str, list[tuple[str, str]]] = {
    "tests/integration/test_golden_cases.py": [
        ('"""13 个手工构造的典型学生，断言原始值→得分→百分位→短板→标签全链路。',
         '"""14 个手工构造的典型学生，断言原始值→得分→百分位→短板→标签全链路。'),
        ('现在 13 例的**全文**钉在夹具里，一次改动把那批 0 红转红。',
         '现在 14 例的**全文**钉在夹具里，一次改动把那批 0 红转红。'),
        ('本轮逐条复核的结论：13 例全部为真。',
         '**Plan 02 Task 9 那一轮**逐条复核的结论：当时的 13 例全部为真'
         '（⚠️ 绑时点：Plan 03 Task 9 加的第 14 例 GC14 由那一轮另行复核，记录在\n'
         '    ``.superpowers/sdd/2026-10-08-实施计划03-反馈预警与CRUD-API层/task-9-report.md``\n'
         '    第 ② 节，本句不替它背书）。'),
        ('⚠️ **13 例覆盖不到 ``_trend_text`` 的「无从比较」那一支**',
         '⚠️ **14 例覆盖不到 ``_trend_text`` 的「无从比较」那一支**'),
        ('``annual_change == {}`` 渲染成 ``+0.0 分``）：12 个非 Z0 用例的 ``curr`` 与 ``prev``',
         '``annual_change == {}`` 渲染成 ``+0.0 分``）：13 个非 Z0 用例的 ``curr`` 与 ``prev``'),
        ('#: 整份夹具（模块级读一次：下面那条参数化测试的 ``ids`` 在**收集期**就要拿到 13 个学号，',
         '#: 整份夹具（模块级读一次：下面那条参数化测试的 ``ids`` 在**收集期**就要拿到 14 个学号，'),
        ('#: 13 个学号，按 ``input`` 的书写序。',
         '#: 14 个学号，按 ``input`` 的书写序。'),
        ('**list 不是 dict**，故 12 个训练包键逐例按顺序加时**加错一格不会报错**——只会让 13 例',
         '**list 不是 dict**，故 12 个训练包键逐例按顺序加时**加错一格不会报错**——只会让 14 例'),
        ('    """13 例黄金用例 → 逐例的「模板 → 训练包」实测值（12 个键，与夹具 ``expected`` 同形）。',
         '    """14 例黄金用例 → 逐例的「模板 → 训练包」实测值（12 个键，与夹具 ``expected`` 同形）。'),
        ('    ``module`` 作用域：13 例共用一次 ``_from_golden_cases``（它要读国标评分表并算一次\n'
         '    ``compute_snapshot``），逐例重建会让同一份快照算 13 遍。',
         '    ``module`` 作用域：14 例共用一次 ``_from_golden_cases``（它要读国标评分表并算一次\n'
         '    ``compute_snapshot``），逐例重建会让同一份快照算 14 遍。'),
        ('    2. **spec §7.4 的 ``bmi_over_30`` 与 ``muscle_low_p10`` 两档**——P9-A1 之后 13 例的\n'
         '       ``bmi`` 各有其值（改前恒 ``None``），故 ``bmi_over_30`` 从「结构上不可求值」变成\n'
         '       「**可求值但不命中**」：13 例的 ``bmi`` 全落在 ``[18.9, 25.7]``，没有一例 > 30；\n'
         '       ``muscle_low_p10`` 仍结构上不可达（``muscle_p10`` 恒 ``None``）。于是\n'
         '       ``needs_review`` 与 ``safety_substitution_count`` 在 13 例里**恒为 ``False`` / ``0``**，\n'
         '       这两档的**行为守卫**在 ``tests/domain/test_prescription_safety.py``；',
         '    2. **spec §7.4 的 ``muscle_low_p10`` 那一档**——⚠️ ``bmi_over_30`` 自 Plan 03 Task 9\n'
         '       的 **GC14** 起**已经可达**（``bmi = 31.0``、``safety_substitution_count = 32``、\n'
         '       ``week1_block0_exercise_ref`` 是替身 ``stationary_cycling``），故本条此前那句\n'
         '       「两档都不可达 / ``needs_review`` 与 ``safety_substitution_count`` 恒为\n'
         '       ``False`` / ``0``」**已过期**，按实际改写：``muscle_low_p10`` 仍结构上不可达\n'
         '       （黄金用例路径刻意不调 ``resolve_muscle_lines``，``muscle_p10`` 恒 ``None``），\n'
         '       而 ``needs_review = True`` 那一档在 14 例里也仍不可达（等价表 v1.0 给全部 5 个\n'
         '       high 动作都备了 low 替身）。两者的**行为守卫**都在\n'
         '       ``tests/domain/test_prescription_safety.py``，「这一档是刻意留下的空白、\n'
         '       不是遗漏」的完整理由写在夹具 ``_meta.caveats_training_package`` ②；'),
        ('    13 例里 **12 例有处方**（``match_status == "matched"``）、**1 例断言「无处方」**',
         '    14 例里 **13 例有处方**（``match_status == "matched"``）、**1 例断言「无处方」**'),
    ],
    "app/pipeline/run_stratify.py": [
        ('``snapshot_muscle_p20`` 用夹具**手工给定**的值而不是查快照：13 人',
         '``snapshot_muscle_p20`` 用夹具**手工给定**的值而不是查快照：14 人'),
        ('"national"``），故这 13 例守卫的是**国标常模判定线**那一路；校内百分位那一路由',
         '"national"``），故这 14 例守卫的是**国标常模判定线**那一路；校内百分位那一路由'),
        ('# ``snapshot_muscle_p10`` **仍**缺省 ``None``：13 人 < ``MIN_SAMPLE = 30``，',
         '# ``snapshot_muscle_p10`` **仍**缺省 ``None``：14 人 < ``MIN_SAMPLE = 30``，'),
        ('# （P20 用夹具手工给定的值）。故 ``muscle_low_p10`` 那一档在 13 例里',
         '# （P20 用夹具手工给定的值）。故 ``muscle_low_p10`` 那一档在 14 例里'),
        ('# test_golden_cases_reach_the_training_package（13 例逐例钉 ``bmi``）。',
         '# test_golden_cases_reach_the_training_package（14 例逐例钉 ``bmi``）。'),
    ],
    "app/domain/percentile.py": [
        ('``for item in ScoredItem`` **含 BMI**，黄金用例那 13 人 < ``MIN_SAMPLE`` 故整组降级，',
         '``for item in ScoredItem`` **含 BMI**，黄金用例那 14 人 < ``MIN_SAMPLE`` 故整组降级，'),
        ('会**收窄** ``C`` 的触发面、改掉 Plan 01 已结案的分层标签，13 例黄金用例当场红。',
         '会**收窄** ``C`` 的触发面、改掉 Plan 01 已结案的分层标签，14 例黄金用例当场红。'),
    ],
    "tests/domain/test_percentile.py": [
        ('含 BMI，黄金用例 13 人 < ``MIN_SAMPLE`` 故整组降级，改前那 28 行快照里 BMI 占 4 行。',
         '含 BMI，黄金用例 14 人 < ``MIN_SAMPLE`` 故整组降级，改前那 28 行快照里 BMI 占 4 行。'),
    ],
    "tests/domain/test_stratify.py": [
        ('⚠️ ``explain()`` 的**全文**另由 ``tests/integration/test_golden_cases.py`` 的 13 个黄金用例',
         '⚠️ ``explain()`` 的**全文**另由 ``tests/integration/test_golden_cases.py`` 的 14 个黄金用例'),
        ('    **这一支 13 个黄金用例覆盖不到**（Ruling 216-M1 补 A6 时实测到的缺口）：夹具里 12 个',
         '    **这一支 14 个黄金用例覆盖不到**（Ruling 216-M1 补 A6 时实测到的缺口）：夹具里 13 个'),
    ],
    "tests/pipeline/test_prescription_stage.py": [
        ('故它的价值主要是「不回归」——13 例黄金用例与 500 人分布测试全绿只证明标签没变，',
         '故它的价值主要是「不回归」——14 例黄金用例与 500 人分布测试全绿只证明标签没变，'),
        ('让 13 例黄金用例一起红。',
         '让 14 例黄金用例一起红。'),
        ('``snapshot_muscle_p10`` **仍然**是 ``None``：13 人 < ``MIN_SAMPLE = 30``，肌肉量组按',
         '``snapshot_muscle_p10`` **仍然**是 ``None``：14 人 < ``MIN_SAMPLE = 30``，肌肉量组按'),
        ('``muscle_low_p10`` 那一档在 13 例里**结构上不可达**、``safety_skipped`` 恒含',
         '``muscle_low_p10`` 那一档在 14 例里**结构上不可达**、``safety_skipped`` 恒含'),
        ('路径接上 ``resolve_muscle_lines``：那会让 13 例的 P20 也一起被 ``None`` 覆盖掉',
         '路径接上 ``resolve_muscle_lines``：那会让 14 例的 P20 也一起被 ``None`` 覆盖掉'),
        ('    # P10 仍是 None：13 人 < MIN_SAMPLE，且本路径不调 resolve_muscle_lines',
         '    # P10 仍是 None：14 人 < MIN_SAMPLE，且本路径不调 resolve_muscle_lines'),
    ],
}


def _edit(rel: str, pairs: list[tuple[str, str]]) -> None:
    path = BACKEND / rel
    raw = path.read_bytes()
    crlf = raw.count(b"\r\n")
    bare = raw.count(b"\n") - crlf
    for old, new in pairs:
        # 锚点用**工作树自己的行尾**编码：文件是 CRLF 就把锚点里的 \n 换成 \r\n
        needle = old.replace("\n", "\r\n").encode("utf-8") if crlf and not bare else old.encode("utf-8")
        replacement = new.replace("\n", "\r\n").encode("utf-8") if crlf and not bare else new.encode("utf-8")
        hits = raw.count(needle)
        if hits != 1 and crlf and not bare:
            # 退回 LF 锚点再试一次（混合行尾的文件）
            needle, replacement = old.encode("utf-8"), new.encode("utf-8")
            hits = raw.count(needle)
        assert hits == 1, f"{rel}: 锚点命中 {hits} 次（应为 1）：{old[:60]!r}"
        raw = raw.replace(needle, replacement)
    path.write_bytes(raw)
    after = path.read_bytes()
    crlf_after = after.count(CRLF_BYTES)
    bare_after = after.count(LF_BYTES) - crlf_after
    print(f"  {rel}: {len(after)} B, CRLF={crlf_after}, bare LF={bare_after}"
          f"（改前 CRLF={crlf}, bare={bare}）")


print("== 改前 ==")
for rel in EDITS:
    b = (BACKEND / rel).read_bytes()
    n_crlf = b.count(CRLF_BYTES)
    n_bare = b.count(LF_BYTES) - n_crlf
    print(f"  {rel}: {len(b)} B, CRLF={n_crlf}, bare LF={n_bare}")
print("== 应用 ==")
for rel, pairs in EDITS.items():
    _edit(rel, pairs)
print("done; 编辑处数 =", sum(len(v) for v in EDITS.values()))
sys.exit(0)

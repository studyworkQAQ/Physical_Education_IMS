"""Task 9 落地脚本 04：给 tests/domain/test_report.py 追加「支 I：二次小测标准化得分」。

⚠️ 用**追加**而不是编辑器改写：本文件 800+ 行，而新增的一支是一个自包含的块
（放在文件末尾与既有八支的书写序一致：支 A…H 按 spec 的章节序，支 I 是 Plan 03 Task 9
从 api 层搬进来的那一块）。⚠️ 字节级追加，工作树行尾逐字保持（先实测再决定用哪种换行）。
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
TARGET = ROOT / "backend" / "tests" / "domain" / "test_report.py"

BLOCK = '''

# ===========================================================================
# 支 I：二次小测的**标准化得分**（spec §8.1；Plan 03 Task 9 从 api 层搬进 domain）
# ===========================================================================
#
# ⚠️ 本支的两个函数原先住在 ``app/api/routers/feedback.py``（``_shuttle_percentile``
# 与那三格内联的算式）。搬家的触发条件是**第二个消费者出现了**：
# :func:`app.pipeline.report_stage.class_snapshot` 生成班级周报时要算同一个数填进
# 进步榜，而 ``pipeline`` 反向 import ``api`` 被架构守卫禁止。
# 故本支既是「算式对不对」的守卫，也是「算式只有一份」的守卫（末尾那条 AST 断言）。


def test_the_shuttle_percentile_counts_slower_people_and_splits_ties():
    """**班内百分位反查**：``PR = (比自己慢的人数 + 0.5 × 并列人数) / 样本数 × 100``。

    ⚠️ 折返跑是**秒数越少越好**，故「反查」= 数比自己**慢**的人。三格期望值都是手算的
    （样本 ``[10.0, 11.0, 12.0]``，``n = 3``）：

    * 最快（10.0）：慢的 2 人 + 并列 1 人 → ``(2 + 0.5) / 3 × 100 = 83.333…``
    * 中间（11.0）：慢的 1 人 + 并列 1 人 → ``(1 + 0.5) / 3 × 100 = 50.0``
    * 最慢（12.0）：慢的 0 人 + 并列 1 人 → ``(0 + 0.5) / 3 × 100 = 16.666…``

    ⚠️ **返回未 round 的裸值**（:data:`SCORE_PRECISION` 的注释逐字写了那个
    ``56.665`` 浮点坑）：round 由 :func:`mini_test_scores` 一处做完，
    故本条用 ``pytest.approx`` 比到小数点后 10 位，**不**比 round 过的值。
    """
    sample = [10.0, 11.0, 12.0]
    assert shuttle_percentile(10.0, sample) == pytest.approx(250.0 / 3.0, abs=1e-10)
    assert shuttle_percentile(11.0, sample) == pytest.approx(50.0, abs=1e-10)
    assert shuttle_percentile(12.0, sample) == pytest.approx(50.0 / 3.0, abs=1e-10)


def test_tied_runtimes_get_the_same_percentile_not_three_different_ones():
    """**并列取中点**：三个人跑出一样的秒数 → 三个人**同一个** 50.0。

    ⚠️ 这一格是本函数与「严格小于」口径的分水岭：严格口径会按书写序给他们三个
    **不同**的分（0 / 33.33 / 66.67），而「并列」该有的样子是同一个数。
    把 ``0.5 *`` 改成 ``0`` 或把 ``>`` 改成 ``>=``，本条当场红。
    """
    assert shuttle_percentile(11.0, [11.0, 11.0, 11.0]) == pytest.approx(50.0, abs=1e-10)


def test_a_single_person_sample_is_fifty_not_zero_and_not_a_hundred():
    """``n = 1`` → **50.0**（自己的并列数 = 1，``0.5 / 1 × 100``）。

    ⚠️ 这是标准公式的自洽结果，**不是**「排过名」：全班只有一个人测了折返时他既不是
    最好也不是最差。⚠️ 而它在真实数据下**看起来像**真排过名，故 Plan 04 应当在
    ``scored_count == 1`` 时显示「无排名」——那是展示层的口径
    （``scored_count`` 已经由 ``GET /api/mini-tests/normalized`` 给出去了），
    本函数**刻意不改**（已登记为移交项）。
    """
    assert shuttle_percentile(30.0, [30.0]) == pytest.approx(50.0, abs=1e-10)


def test_an_empty_sample_raises_instead_of_reporting_the_worst_score():
    """空样本 → ``ZeroDivisionError``（**刻意不兜底**）。

    ⚠️ 兜一个 ``return 0.0`` 会把「算错了」静默变成「这个学生最差」，
    而 0.0 是一个**合法的**百分位值，下游没有任何东西会拦。
    两个调用方都只在 ``shuttle_20m_s is not None`` 时调它，那时样本必非空
    （至少含调用者自己），故这一档在生产路径上不可达——本条钉的是
    「不可达的那一档是响的」。
    """
    with pytest.raises(ZeroDivisionError):
        shuttle_percentile(30.0, [])


def test_mini_test_scores_follows_spec_8_1_verbatim():
    """spec §8.1 的三格：**深蹲得分 = 次数**、**折返得分 = 班内百分位反查**、
    **综合分 = 两项等权平均**。

    ⚠️ 样本 ``[10.0, 10.0, 12.0, 13.0, 14.0, 15.0]``、本人 ``10.0``：
    慢的 4 人 + 并列 2 人 → ``(4 + 0.5 × 2) / 6 × 100 = 83.3333…`` →
    round 2 位 = **83.33**；深蹲 30 次 → **30.0**；
    综合分 = ``(30 + 83.3333…) / 2 = 56.6666…`` → round 2 位 = **56.67**。

    ⚠️⚠️ **56.67 而不是 56.66 是本条的全部价值**（:data:`SCORE_PRECISION` 的注释
    逐字写了这个坑）：若先把百分位 round 成 83.33 再平均，得到的是
    ``(30 + 83.33) / 2 = 56.665``，而 ``round(56.665, 2)`` 在 CPython 上给 **56.66**
    （56.665 的二进制表示略小于十进制的 56.665）。故本条同时钉住
    「中间步骤不 round」这条口径——把 :func:`mini_test_scores` 改成
    ``round((squat + round(raw, 2)) / 2, 2)``，本条当场红。
    """
    sample = [10.0, 10.0, 12.0, 13.0, 14.0, 15.0]
    assert mini_test_scores(30, 10.0, sample) == {
        "squat_score": 30.0,
        "shuttle_score": 83.33,
        "composite": 56.67,
    }
    # 反面对照：先 round 百分位再平均会得到 56.66（本行把那个坑写成一个可执行的事实）
    assert round((30 + round(250.0 / 3.0, 2)) / 2, 2) == 56.66


def test_the_composite_rounds_the_unrounded_percentile_not_the_displayed_one():
    """:data:`SCORE_PRECISION` 的注释里点名的那一条守卫（**与上一条互为正反面**）。

    上一条钉的是「三格的字面值」，本条钉的是「``shuttle_score`` 显示 83.33、
    而 ``composite`` 用的是 83.3333…」这件事本身：两格**必须**来自同一个裸值，
    一个 round 过、一个没 round 过，否则同一份响应里的两个数互相矛盾
    （教师拿 83.33 与 30 一平均得 56.665，而系统写的是 56.67，他会认为系统算错了）。
    """
    sample = [10.0, 10.0, 12.0, 13.0, 14.0, 15.0]
    got = mini_test_scores(30, 10.0, sample)
    assert got["shuttle_score"] == 83.33
    assert got["composite"] == 56.67
    assert got["composite"] != round((30 + got["shuttle_score"]) / 2, SCORE_PRECISION)


def test_a_missing_squat_leaves_the_composite_unknown_not_halved():
    """深蹲缺测 → ``squat_score`` 与 ``composite`` 都是 ``None``，
    而 ``shuttle_score`` **照常给**。

    ⚠️ 把 ``None`` 当 0 会让这个学生的综合分变成「另一项的一半」
    （``(0 + 83.33) / 2 = 41.67``），那是一句关于他的假话；而它会直接掉进
    :func:`progress_board` 的**退步名单**（相对上一次的分是负的），
    教师于是去找一个其实没退步的学生谈话。
    """
    sample = [10.0, 10.0, 12.0, 13.0, 14.0, 15.0]
    assert mini_test_scores(None, 10.0, sample) == {
        "squat_score": None,
        "shuttle_score": 83.33,
        "composite": None,
    }


def test_a_missing_shuttle_leaves_the_composite_unknown_and_skips_the_sample():
    """折返缺测 → ``shuttle_score`` 与 ``composite`` 都是 ``None``，
    而 ``squat_score`` **照常给**；⚠️ 且**样本可以是空的**（本函数不去查百分位）。

    ⚠️ 这一格同时钉住「``shuttle_20m_s is None`` 时不调
    :func:`shuttle_percentile`」：若调了，空样本会当场 ``ZeroDivisionError``
    （见上面那条）。而生产路径上这一档**是可达的**——教师只录了深蹲、
    折返那一格空着，:func:`app.pipeline.report_stage._composite_of` 就会以空样本调进来。
    """
    assert mini_test_scores(30, None, []) == {
        "squat_score": 30.0,
        "shuttle_score": None,
        "composite": None,
    }


def test_both_measurements_missing_is_all_none():
    """两项都缺测 → 三格全 ``None``（``or`` 的第二支：``squat`` 为 ``None`` 时
    短路，``raw`` 那一支也要单独走到，故本条与上两条**互不覆盖**）。"""
    assert mini_test_scores(None, None, []) == {
        "squat_score": None,
        "shuttle_score": None,
        "composite": None,
    }


def test_the_squat_score_is_a_float_even_though_the_column_is_an_integer():
    """``squat_score`` 一律 ``float``：那一列是 ``Integer``，而 ``composite`` 是两项的
    平均（可能是 ``x.5``），两格类型不一致会让前端拿到 ``70`` 与 ``70.0`` 两种形状。"""
    got = mini_test_scores(70, 30.0, [30.0])
    assert isinstance(got["squat_score"], float)
    assert got["squat_score"] == 70.0
    # 全班并列 → 百分位 50.0 → 综合分 (70 + 50) / 2 = 60.0
    assert got == {"squat_score": 70.0, "shuttle_score": 50.0, "composite": 60.0}


def test_the_mini_test_normalization_has_exactly_one_definition():
    """**AST 口径**（硬规矩 #89 再扩写：数「一个名字有几份定义」用 AST）：
    「班内百分位反查」与「综合分」在全仓只有**一份定义**。

    照 ``tests/pipeline/test_alert_stage.py`` 的
    ``test_training_days_of_has_exactly_one_definition`` 的形状办（同为「一个私有函数
    因为第二个消费者出现而搬家」，而搬家之后**旧的那一份必须真的消失**）。

    ⚠️ **失效形态很具体**：留一个平行的副本就是第二个所有者，两份「班内百分位」
    漂了之后，教师录完成绩当场看到的分与周日周报上的进步榜就不是同一个口径了，
    而**两边各自的测试都还是绿的**（一边测端点、一边测周报）。

    ⚠️ **本条守不住什么**（硬规矩 #39）：它数的是**函数名**，故谁把算式
    **内联**进 ``report_stage`` 或某个 router（不再是一个有名字的函数）本条不红。
    那一档由 ``app/domain/`` 的 **100% 分支覆盖**兜一半
    （内联进 pipeline/api 的那一份不在覆盖率口径里，于是它没有测试），
    以及 :func:`test_the_api_layer_and_the_report_stage_give_the_same_composite` 兜另一半。
    """
    names = ("shuttle_percentile", "_shuttle_percentile", "mini_test_scores",
             "_mini_test_scores")
    definitions = []
    for py in sorted((BACKEND / "app").rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                node.name in names
            ):
                definitions.append(
                    (py.relative_to(BACKEND).as_posix(), node.name, node.lineno)
                )
    assert len(definitions) == 2, (
        f"「班内百分位反查 + 综合分」应当只有 2 份定义"
        f"（shuttle_percentile 与 mini_test_scores，都在 app/domain/report.py），"
        f"实到 {len(definitions)}: {definitions}"
    )
    assert [(where, name) for where, name, _line in definitions] == [
        ("app/domain/report.py", "shuttle_percentile"),
        ("app/domain/report.py", "mini_test_scores"),
    ], f"住址不对（应当都在 app/domain/report.py）: {definitions}"


def test_the_api_layer_and_the_report_stage_give_the_same_composite():
    """**两个消费者给出同一个综合分**（本支存在的理由本身）。

    一侧是 ``GET /api/mini-tests/normalized`` 的响应，另一侧是
    :func:`app.pipeline.report_stage._composite_of`。⚠️ 两侧**都**调
    :func:`mini_test_scores`，故本条看似恒真——它挡的是「某一侧在调用前后又自己做了一次
    round / 又自己挑了一次样本」：那正是上面那条 AST 断言守不住的内联档。
    """
    from app.pipeline.report_stage import _composite_of

    sample = [10.0, 10.0, 12.0, 13.0, 14.0, 15.0]
    via_domain = mini_test_scores(30, 10.0, sample)["composite"]

    class _Row:
        squat_30s_count = 30
        shuttle_20m_s = 10.0

    class _Other:
        def __init__(self, shuttle):
            self.squat_30s_count = 0
            self.shuttle_20m_s = shuttle

    week_rows = [_Row()] + [_Other(value) for value in (10.0, 12.0, 13.0, 14.0, 15.0)]
    assert _composite_of(_Row(), week_rows) == via_domain == 56.67
'''

raw = TARGET.read_bytes()
crlf = raw.count(b"\r\n")
bare = raw.count(b"\n") - crlf
print(f"改前: {len(raw)} B, CRLF={crlf}, bare LF={bare}")
newline = "\r\n" if (crlf and not bare) else "\n"
block = BLOCK.replace("\n", newline).encode("utf-8")
assert b"test_the_mini_test_normalization_has_exactly_one_definition" not in raw, "已经追加过了"
TARGET.write_bytes(raw.rstrip(b"\r\n") + newline.encode("utf-8") * 1 + block)
after = TARGET.read_bytes()
crlf2 = after.count(b"\r\n")
bare2 = after.count(b"\n") - crlf2
print(f"改后: {len(after)} B, CRLF={crlf2}, bare LF={bare2}")
sys.exit(0)

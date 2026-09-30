import collections, json, pathlib
import pytest
from app.seed.config import SeedConfig
from app.seed.generate import build_dataset
from app.pipeline.run_stratify import stratify_dataset   # Task 10 提供
# ``_REASON`` 取自生产而不是在测试里重抄一份文案：这条断言要守的是「fixture 与生产一致」，
# 抄一份字面量进来会变成两边一起改错也不红。测试触私有名是本项目既有惯例
# （``tests/architecture/test_domain_purity.py`` 直接对 ``app/domain`` 做 AST 内省）。
from app.domain.stratify import _REASON, RuleId

GOLDEN = pathlib.Path(__file__).parents[1] / "fixtures" / "golden_cases.json"

def test_golden_cases_match_expected_labels():
    """13 个手工构造的典型学生，断言原始值→得分→百分位→短板→标签全链路。"""
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
    report = stratify_dataset(cases["input"])
    assert len(report.results) == len(cases["expected"])
    for exp, got in zip(cases["expected"], report.results):
        assert got["label"] == exp["label"], exp["note"]
        assert got["W"] == exp["W"], exp["note"]
        assert got["C"] == exp["C"], exp["note"]
        assert got["valid_count"] == exp["valid_count"], exp["note"]
        assert got["dominant_bucket"] == exp["dominant_bucket"], exp["note"]
        assert got["hit_rules"] == exp["hit_rules"], exp["note"]
        # ``reason`` 是生产文案的逐字副本、不是自由散文，故可以直接断言，从此不必靠人记得
        # 同步：Ruling 134/138 把 Y3/G1 改成「体成分未判为异常」后，fixture 里 4 条
        # （GC06/GC07 = Y3、GC09/GC11 = G1）漂移了整整一轮才被发现（Ruling 145）——一份与
        # 生产不一致的期望值 fixture 是哑弹。``_REASON`` 只由 ``RuleId`` 决定（Ruling 129），
        # 而 ``hit_rules`` 是 ``RULE_ORDER`` 的**已评估前缀**、最后一项即胜出规则
        # （Z0 路径恰为 ``["Z0"]``，Ruling 125/132）。
        assert exp["reason"] == _REASON[RuleId(got["hit_rules"][-1])], exp["note"]

@pytest.fixture(scope="module")
def dataset_500():
    """500 人 ×16 周的数据集与它的分层报告，``(ds, report)``。

    ``build_dataset`` + ``stratify_dataset`` 一次约 **0.40–0.42 s**（fix round 3 实测 n=3：
    build 0.337–0.350 s、stratify 0.059–0.079 s）。本处此前印的是单次跑的点值
    「0.334 + 0.069」，按 Ruling 201 一律改成区间 + 样本数——跑次间有 ±5% 量级的波动，
    而**没有任何测试守卫这个耗时**，点值写死了就等着过期。本文件有两条测试要读同一份产出
    （spec §10.2 的分布容差、Ruling 146 的趋势一致率），故用 module 作用域共享，
    **不建两遍**。
    """
    ds = build_dataset(SeedConfig(students=500, weeks=16, seed=20250828))
    return ds, stratify_dataset(ds)

def test_target_layer_distribution_within_tolerance(dataset_500):
    """spec §10.2：500 人分层分布须落在 20/45/35 的 ±5% 容差内。

    ⚠️ **本测试跑的是「缺省注入」那一组，不是「零注入」那一组。** 本 docstring 此前把两组
    的数字混在一起，于是印出了一个对本测试为假的余量（Ruling 199）。fixture
    ``dataset_500`` 用 ``SeedConfig(students=500, weeks=16, seed=20250828)``，``dirty``
    取缺省值（4% 逐项缺测 / 0.5% 越界 / 0.3% 量纲错 / 1% 重复行），**不是**零注入。

    两组的实测分布（fix round 3 在 commit ``b6ebaa3`` 上各复跑一次，走的就是本测试这条
    ``stratify_dataset(build_dataset(cfg))`` 生产路径，不是自建探针；容差的实现口径是
    **5 个百分点**而不是相对 5%——见下面 ``abs(dist[...] - ...) <= 0.05``，故三层可行带是
    red [15, 25] / yellow [40, 50] / green [30, 40]）::

        口径               red     yellow  green   insufficient      green 对下界 30% 的余量
        ------------------ ------- ------- ------- ----------------- -----------------------
        缺省注入（本测试）  19.0%   46.6%   34.0%   0.4%（2 人）      **+4.0 pp**
        零注入             22.0%   47.6%   30.4%   0%（0 人）        **+0.4 pp**

    两组都逐层落在 ±5 pp 内，故断言全绿——**这正是错散文能一路存活的原因**。

    **本条断言守的是「缺省注入下三层都在 ±5 pp 内」**（上表第一行）。第二行那组
    （22.0 / 47.6 / 30.4）**不被任何测试守卫**，按硬规矩 #39 降级为**历史实测**
    （Ruling 128/149 的探针；条件 = 500 人 / ``seed=20250828`` / 零注入 / 本学年 week1 /
    学生级 P20 / ``national_total``、``find_weaknesses``、``flag_body_comp``、
    ``classify_trend`` 全走生产代码，只有 spec §6.2 的八行表与 P20 是探针自建）。

    ⚠️ **「零注入」三个字本身不足以确定分布，人数同样是承重条件。**
    ``tests/pipeline/test_daily.py`` 的 ``CLEAN_CFG`` 也是零注入，但它是 **60 人**、而且
    只钉趋势配额不钉分层分布——fix round 3 实测 60 人零注入的分层是
    **red 13.3% / yellow 50.0% / green 36.7%**，其中 red 对目标 20% 偏 −6.7 pp、
    **已在 ±5 pp 之外**，与 500 人零注入的 22.0/47.6/30.4 完全不是一组数。引用任何一组
    分布都必须同时写出「注入配置 + 人数 + seed + 锚点」。

    **Ruling 128 的历史结论仍然成立，但要挂上它的条件**：缺省 ``latent_mean=0.0`` /
    ``latent_sd=1.0`` 就已达标、二分法逼近（计划原文的预设）用不上——那是在**零注入**下
    测的；fix round 3 复跑确认缺省注入下同样达标（上表第一行），故这条结论对两组都成立。
    同一段里「无肌肉量 P20 线：red 20.2% / yellow 44.2% / green 35.6%」是 Ruling 102
    未解决时的历史状态，Task 10 落地 Ruling 121 之后恒有 P20 线、已不可复现，
    一并记为历史实测、**不被守卫**。

    **若 green 掉到 30% 以下，先怀疑肌肉量 P20 的口径，不要直接放宽容差。** 这条建议出自
    **零注入**那一组（余量只有 0.4 pp，翻几个人就出界），故挂在那一组上；缺省注入这一组
    有 4.0 pp 余量，真掉出去说明的是别的事。口径本身（学生级 vs 测量行级）的实测量级见
    :func:`app.domain.percentile.compute_snapshot` 的 docstring：零注入下男性「大一、大二」
    的学生级 P20 = **33.20**、按测量行入样 = **33.10**，四个 (性别, 年级组) 的差值跨度是
    −0.06 到 +0.40 kg、翻动 **7 个人**的 ``C``。本处此前印的「实测 33.2 vs 33.40」是
    Ruling 128 探针的数：33.2 与今天的生产学生级值吻合，**33.40 在生产路径上复现不出来**
    （fix round 3 四个组的学生级值是 23.70 / 23.60 / 33.20 / 33.56），故按本轮实测改写。
    """
    dist = dataset_500[1].distribution
    assert abs(dist["red"]    - 0.20) <= 0.05
    assert abs(dist["yellow"] - 0.45) <= 0.05
    assert abs(dist["green"]  - 0.35) <= 0.05
    assert dist["red"] > 0 and dist["yellow"] > 0 and dist["green"] > 0

def test_trend_agrees_with_the_generator_oracle_on_the_decidable_subset(dataset_500):
    """Ruling 146/149：真不变量是「**可判子集**上的高一致率」，不是「分布逐类相等」。

    ``_from_dataset`` 的 docstring 此前印着一个**不带测量条件**的等式——「500 人跑完后的
    趋势分布必须等于生成器的配额 ``{持续下滑:100, 波动大:75, 稳定:200, 稳步提升:125}``」。
    它**不是无条件为假**（Ruling 149 更正了 Ruling 146 那句「可证明为假」）：``dirty`` 四项
    全 0 的**零注入**下它精确成立——同一 seed 实测趋势分布 ``{持续下滑:100, 波动大:75,
    稳定:200, 稳步提升:125}``、``insufficient_data`` **0 人**、分层分布 ``{red 0.22,
    yellow 0.476, green 0.304, insufficient_data 0.0}``。Task 10 的落库取证与
    ``tests/pipeline/test_daily.py`` 的
    ``test_trend_matches_the_generator_oracle_on_week1_anchors`` 量的都是这一组条件
    （``CLEAN_CFG``）；**本测试的 fixture 走的是缺省注入**（``build_dataset(cfg)``：4% 逐项
    缺测、0.5% 越界、0.3% 量纲错、1% 重复行），等式在这组条件下不成立，成因是构造性的、
    不是实现走偏：``classify_trend`` 在 ``prev_total`` / ``curr_total`` 任一为 ``None`` 时归
    ``INSUFFICIENT``（Ruling 99），而 ``national_total`` 对 7 个计分项**得分**全有或全无，
    这 7 个得分又由 **8 个原始单元格**算出（身高与体重共同决定 BMI 得分），任一单元格缺测
    即让整条记录的总分变 ``None``。**只印实测、不印概率模型**（硬规矩 #25：此处原有一个
    把「7 个计分项得分」当成「7 个独立同率缺测单元格」的概率推算，Ruling 159 实测推翻了
    它的全部前提——单元格是 8 个不是 7 个；注入后 week1 行 1011 条里 252 条（24.9%）含
    ≥1 个缺测单元格，8 个单元格合计缺测 283/8088 = 3.5%、逐列 2.6%–4.5% 不均匀——故整段
    删除、不换新模型）。本 fixture 的口径是
    ``seed=20250828``、缺省注入、500 人、内存路径：实测 291/500 = 58.2% 可判、209/500 =
    41.8% 不可判；**可判比例随 seed 变动**，四个 seed 实测 227–291 人（45.4%–58.2%），故
    下面钉的精确计数只对 ``seed=20250828`` 成立——它是 ``SeedConfig`` 的缺省值，也是本
    fixture 显式传入的值。源码里印着一个不带条件的等式，损害与
    Ruling 81 同类而且是**双向**的：拿缺省注入跑的人会把它当回归基线、跑出不等就去「修」
    那个本来正确的管道；拿零注入跑的人会得出「docstring 没错」的相反结论，于是那个条件
    永远补不上。

    故本测试钉三段实测真值（seed 固定故完全确定；本项目风格是钉精确值而不是弱断言，
    Ruling 143）：① 生成器配额成立——**比较只有在配额成立时才有意义**；② 管道侧趋势
    分布；③ 逐人对账的可判数与一致数（280/291 = 96.2%）。那 11 处分歧全部可由「某个
    单项缺测被清成 ``None`` → 该项 delta 退出计数、加权和下降」解释，是**正确行为**。

    「不可判必然因为 ``curr_total`` / ``prev_total`` 为 ``None``」这条**单元级**不变量已由
    ``tests/domain/test_derive.py`` 的
    ``test_derive_rejects_prev_total_with_a_missing_prev_value`` 覆盖，此处不重复：
    ``result_dict`` 的 10 个键是契约（见 ``StratifyReport`` 的 docstring），里面没有
    totals，集成层要验它就得伸进 ``_from_dataset`` 这个私有函数。
    """
    ds, report = dataset_500

    # 生成器侧的真值：``trend_label`` 挂在该生的**每一条**体测记录上（``app/seed/fitness.py``
    # 的记录循环），故按 ``student_id`` 归并即「每人一个标签」。**必须归并**：缺省注入 1%
    # 重复行，``timepoint == "week1"`` 的行实测 1011 条（两学年 ×500 + 11 条重复副本）、
    # 其中本学年 505 条，都不是 500——直接数行会得到近两倍的配额。
    oracle = {row["student_id"]: row["trend_label"] for row in ds["fitness"]}
    assert len(oracle) == 500
    assert dict(collections.Counter(oracle.values())) == {
        "持续下滑": 100, "波动大": 75, "稳定": 200, "稳步提升": 125,
    }, "生成器配额不成立，下面的一致率比较就没有意义"

    # 管道侧的趋势分布：209 人（41.8%）因整条记录不完整而不可判。
    assert dict(collections.Counter(r["trend"] for r in report.results)) == {
        "insufficient_data": 209, "稳定": 120, "稳步提升": 71,
        "持续下滑": 60, "波动大": 40,
    }

    # 逐人对账：可判 291 人，其中 280 人与生成器的 trend_label 一致。
    decidable = [r for r in report.results if r["trend"] != "insufficient_data"]
    assert len(decidable) == 291
    assert sum(1 for r in decidable if r["trend"] == oracle[r["student_id"]]) == 280

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

    ``build_dataset`` + ``stratify_dataset`` 一次实测约 0.40 s（0.334 + 0.069），而本文件
    有两条测试要读同一份产出（spec §10.2 的分布容差、Ruling 146 的趋势一致率），故用
    module 作用域共享，**不建两遍**。
    """
    ds = build_dataset(SeedConfig(students=500, weeks=16, seed=20250828))
    return ds, stratify_dataset(ds)

def test_target_layer_distribution_within_tolerance(dataset_500):
    """spec §10.2：500 人分层分布须落在 20/45/35 的 ±5% 容差内。

    **控制者已跑通全链路实测（Ruling 128），缺省 `latent_mean=0.0` / `latent_sd=1.0`
    就已达标，本 Task 不需要调参**——二分法逼近是计划原文的预设，实测证明用不上：
      · 无肌肉量 P20 线（今天的现实，Ruling 102 未解决）：red 20.2% / yellow 44.2% / green 35.6%
      · 有肌肉量 P20 线（Task 10 落地 Ruling 121 之后）：red 22.0% / yellow 47.6% / green 30.4%
    两者都在 ±5% 内。测量条件（必须逐条写明，硬规矩 #8）：零注入配置、本学年 week1、
    学生级 P20、`national_total` 与 `find_weaknesses`/`flag_body_comp`/`classify_trend`
    全部走生产代码，只有 spec §6.2 的八行表与 P20 是探针自建；Z0 闸门在第一行；
    `insufficient` 实测 0 人（零注入下无人 `valid_count < 4`）。

    ⚠️ **green 的余量在 Task 10 之后只剩 0.4 个百分点**（30.4% vs 下界 30%）。
    本测试用 `stratify_dataset`（Task 10 提供），故它跑的是**有线**的那一组；
    若 Task 10 落地后 green 掉到 30% 以下，**先怀疑肌肉量 P20 的口径**
    （学生级 vs 测量行级，实测 33.2 vs 33.40 就会翻几个人），不要直接放宽容差。
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
    ``INSUFFICIENT``（Ruling 99），而 ``national_total`` 对 7 个计分项**全有或全无**；故单条
    记录完整的概率约 ``0.96^7 = 75.1%``、两条同时完整约 ``56.4%``——实测 291/500 = 58.2%
    可判、209/500 = 41.8% 不可判，与推算吻合。源码里印着一个不带条件的等式，损害与
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

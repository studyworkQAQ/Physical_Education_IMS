import collections, datetime as dt, json, pathlib
import pytest
from app.db import models
from app.domain.prescription.assembler import assemble
from app.domain.prescription.match import MatchInput, match_template
from app.domain.prescription.safety import SafetyInput, apply_safety
from app.domain.stratify import Layer, stratify
from app.seed.config import SeedConfig
from app.seed.generate import build_dataset
# ⚠️ ``run_stratify._from_golden_cases`` 与 ``prescription_stage._profile_of`` 都是**私有名**：
# 本文件要复用的正是「映射只有一个所有者」这件事本身（Global Constraint #3）——
# ``endurance_score`` 的均值口径与 ``bmi`` 的读取口径都在 ``_profile_of`` 里，在测试里重抄
# 一遍就是第二个住址，两侧一起改错也不红。测试触私有名是本项目既有惯例
# （见本文件顶部那段 ``_REASON`` 的说明，与 ``tests/architecture/test_domain_purity.py``）。
from app.pipeline import run_stratify
from app.pipeline.prescription_stage import _profile_of
# ``stratify_dataset`` 的生产者落地于 **Plan 01 的 Task 10**（⚠️ Plan 02 重编号后已无
# Task 10：原 Task 10 = 新 Task 7，故写全「Plan 01 的」以消歧，P9-A5）
from app.pipeline.run_stratify import input_snapshot_of, stratify_dataset
from app.refdata_prescription import equivalence, exercises, templates
# ``_REASON`` 取自生产而不是在测试里重抄一份文案：这条断言要守的是「fixture 与生产一致」，
# 抄一份字面量进来会变成两边一起改错也不红。测试触私有名是本项目既有惯例
# （``tests/architecture/test_domain_purity.py`` 直接对 ``app/domain`` 做 AST 内省）。
from app.domain.stratify import _REASON, RuleId

GOLDEN = pathlib.Path(__file__).parents[1] / "fixtures" / "golden_cases.json"

def test_golden_cases_match_expected_labels():
    """13 个手工构造的典型学生，断言原始值→得分→百分位→短板→标签全链路。

    ``explain`` 那一段（Ruling 216-M1）是本轮加的：改前全仓对 :func:`app.domain.stratify.explain`
    输出的断言**只有 3 条子串**（``tests/domain/test_stratify.py`` 的 ``"体脂率" / "22.4" /
    "20%" / "28%" / "女" / "数据不足"``），而 ``stratify.py`` 的分支覆盖之所以是 100%，
    是因为 ``run_stratify.result_dict`` 对 13 + 500 人各调一次 ``explain()``——**被执行、
    不被断言**。按目录拆覆盖率即露馅：``tests/domain`` 单独只给 ``stratify.py`` **84%**，
    ``tests/integration`` 单独给 **98%**。终审实测 13 个文案变异里 **8 个 0 红**，含
    「低于 P25」→「高于 P25」（语义完全反转）、体成分 over/under 措辞互换、项目名恒取
    男性那一列。现在 13 例的**全文**钉在夹具里，一次改动把那批 0 红转红。

    期望值的取法是「跑一次生产、把输出粘进夹具」，然后**逐条人读**确认每句文案为真
    （同 ``reason`` 的处置：Ruling 145 那次漂移正是 fixture 与生产不一致而无人核对）。
    本轮逐条复核的结论：13 例全部为真。两处**已登记的关切**（不擅自改生产文案）：
    ① GC13 的「男生阈值 20%」在同一句里出现两次（``肌肉量低于同龄同性别 P20（体脂率 16%
    未超过男生 20% 阈值，男生阈值 20%）``）——冗余，终审 A 已报过；② ``你的 肺活量、1000 米跑
    在校内…`` 的项目名两侧各有一个空格，是 ``_weakness_text`` 的 f-string 字面留下的。

    ⚠️ **13 例覆盖不到 ``_trend_text`` 的「无从比较」那一支**（Ruling 99 禁止把
    ``annual_change == {}`` 渲染成 ``+0.0 分``）：12 个非 Z0 用例的 ``curr`` 与 ``prev``
    都完整，故 ``annual_change`` 恒有 7 个键、恒走 ``国标总分年均变化 {total:+.1f} 分``
    那一支；唯一 ``annual_change == {}`` 的 GC10 走的是 Z0 单独成句的分支、根本不渲染趋势。
    那一支由 ``tests/domain/test_stratify.py`` 的
    ``test_explain_renders_missing_history_as_not_comparable`` 单独钉住。
    """
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
    # ``explain`` 用 **offender 列表**而不是循环内 assert：循环式断言会在第一例就截断，
    # 13 条文案里改坏 3 条时只看得见第 1 条（Ruling 157）。全文比较、附 note 定位。
    offenders = [
        f"{exp['student_id']}（{exp['note'][:40]}…）\n      期望: {exp['explain']}\n"
        f"      实际: {got['explain']}"
        for exp, got in zip(cases["expected"], report.results)
        if got["explain"] != exp["explain"]
    ]
    assert offenders == [], "explain 全文与夹具不符：\n  " + "\n  ".join(offenders)

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
    分布；③ 逐人对账的可判数与一致数（280/291 = 96.2%）。

    **那 11 处分歧的真因是 ``outlier`` 注入，11/11**（Ruling 210）。本 docstring 此前印着
    一句**编造的机制**——「某个单项缺测被清成 ``None`` → 该项 delta 退出计数、加权和下降」，
    它已被反例推翻，而且在代码里**结构性不可能**：``national_total`` 对七项得分全有或全无
    （``derive.py:199`` 的 ``if any(value is None ...)``），故可判 ⟺ 七项得分齐全 ⟺ 6 个
    delta 全部参与计数（``derive.py:265`` 是无条件列表推导，没有「退出计数」的分支）。
    实测佐证：可判的 291 人里，本学年 week1 行含 ≥1 个 ``None`` 单元格的人数是 **0**。
    真因的逐人取证表（11 人全列）与三个反例见
    :func:`app.pipeline.run_stratify._from_dataset` 的 docstring；**成因**由本文件下面的
    ``test_trend_discrepancies_vanish_without_outlier_injection`` 钉住。

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


def test_trend_discrepancies_vanish_without_outlier_injection():
    """Ruling 210 的**成因**守卫：把 ``outlier`` 关掉，11 处分歧归零。

    上面那条测试钉住了 ``11`` 这个**数字**，却钉不住它的**成因**——一个把
    ``inject_dirty`` 的 ``outlier`` 分支改坏（或把清洗层的上限夹取改坏）的回归，会让分歧数
    变化，而那时红的是「280」这个计数，看不出真因是哪一类注入。本条就是终审报告里的
    **反例 B1**：同样 4% 逐项缺测，只把 ``outlier`` / ``unit_error`` / ``duplicate``
    关掉，断言分歧为 **0**。它同时否证了 Ruling 210 清掉的那句编造机制
    （「缺测 → delta 退出计数」）：缺测率一字未动、分歧却归零。

    实测条件（本轮亲跑，500 人 / ``seed=20250828``，只改 ``cfg.dirty``）::

        配置                                        decidable  discrepant
        ------------------------------------------- ---------  ----------
        缺省注入（4% 缺测 + 0.5% 越界 + 0.3% + 1%）     291          11
        本条（4% 缺测，其余三类 = 0）                   286           0
        只有 outlier 0.5%、缺测 = 0（反例 B2）          500          17
        缺测拉到 20%、其余 = 0（反例 B5）                17           0

    **可判人数从 291 变成 286 是预期的**：``inject_dirty`` 对每个测量单元格恰好消耗一次
    ``rng.random()``、随机数消耗量不随 ``cfg.dirty`` 变化（``generate.py`` 的
    ``inject_dirty`` docstring），故换一组注入比例**不会**平移后面所有数据的取值，但
    ``outlier`` 单元格改成 ``missing`` 之后确实多几条记录变得不完整。本条只断言
    **分歧为 0**，不断言可判人数——后者不是这条要守的东西（硬规矩 #41：分母取守卫它那条
    测试自己的定义）。

    运行时间约 0.4 s（一次 ``build_dataset`` + 一次 ``stratify_dataset``，与
    ``dataset_500`` fixture 同量级），故**不复用**那个 fixture——它用的是缺省注入，
    而本条要的正是另一组注入配置。
    """
    cfg = SeedConfig(
        students=500, weeks=16, seed=20250828,
        dirty={"missing": 0.04, "outlier": 0.0, "unit_error": 0.0, "duplicate": 0.0},
    )
    ds = build_dataset(cfg)
    # 前置断言：这组配置下确实**一条 outlier 都没注入**（否则本条测的就不是 B1）。
    # 两侧不同源（硬规矩 #35）：左侧数 ``build_dataset`` 产出的痕迹，右侧是字面量 0。
    assert sum(1 for m in ds["dirty_marks"] if m["kind"] == "outlier") == 0
    assert sum(1 for m in ds["dirty_marks"] if m["kind"] == "missing") > 0

    report = stratify_dataset(ds)
    oracle = {row["student_id"]: row["trend_label"] for row in ds["fitness"]}
    decidable = [r for r in report.results if r["trend"] != "insufficient_data"]
    # offender 一次性报全（Ruling 157：循环里逐条 assert 会在第一例就停、证据被截断）
    offenders = [
        (r["student_id"], oracle[r["student_id"]], r["trend"])
        for r in decidable if r["trend"] != oracle[r["student_id"]]
    ]
    assert offenders == [], f"零 outlier 注入下仍有人趋势分歧: {offenders}"


# ---------------------------------------------------------------------------
# Plan 02 Task 9：把 spec §12 的黄金用例链路从「标签」延伸到「模板 → 训练包」
# ---------------------------------------------------------------------------

#: 整份夹具（模块级读一次：下面那条参数化测试的 ``ids`` 在**收集期**就要拿到 13 个学号，
#: 而 ``golden_packages`` fixture 与它又要读同一份内容）。⚠️ 既有的
#: ``test_golden_cases_match_expected_labels`` **刻意不改**（P9-A4），它自己读自己的。
_CASES = json.loads(GOLDEN.read_text(encoding="utf-8"))

#: 13 个学号，按 ``input`` 的书写序。参数化用它当 id，于是失败信息里带的是 ``GC07``
#: 而不是一个裸下标（硬规矩 #56：主语要写清）。
_CASE_IDS = [case["student_id"] for case in _CASES["input"]]

#: ``expected`` 里 Plan 02 Task 9 追加的 **12** 个键 = ``bmi`` + 11 个训练包键。
#: **逐字写死**（硬规矩 #35）：夹具里少一个键，下面那条 offender 断言就把它报出来，
#: 而不是等到 ``exp[key]`` 抛一个离真因隔了一层的 ``KeyError``。
_PINNED_PACKAGE_KEYS = (
    "bmi",
    "match_status",
    "template_id",
    "label_at_generation",
    "week1_block0_exercise_ref",
    "week1_block0_hr_zone",
    "week1_block0_weekly_volume",
    "week1_block0_volume_unit",
    "needs_review",
    "safety_substitution_count",
    "safety_triggers",
    "safety_skipped",
)

#: 训练包那一环的业务日。⚠️ 夹具只给 ``age``、不给 ``birth``，故 ``birth`` 由它与 ``age``
#: 反推：``dt.date(_AS_OF.year - age, _AS_OF.month, _AS_OF.day)``。
#: :func:`app.domain.prescription.intensity.age_from` 的判据是
#: ``(as_of.month, as_of.day) < (birth.month, birth.day)``，**相等时不减岁**，故它精确给回
#: ``age``，装配器第 1 步的一致性闸门 ``age == age_from(birth, as_of)`` 因此过得了。
#: 取 ``2025-09-15`` 与本仓其余取证同一个业务日（``tests/pipeline/test_daily.py`` 的
#: 那个锚点日），于是 ``hr_zone`` 的字面值可以与别处的记录直接对读。
_AS_OF = dt.date(2025, 9, 15)


def test_golden_case_input_and_expected_align_one_to_one_by_student_id():
    """**P9-A4**：``input`` 与 ``expected`` 是两条**等长 list**、按 ``student_id`` 逐格对齐。

    ⚠️ 本条是「往 ``expected`` 里加新键」这件事的**前提**，不是装饰：``expected`` 是
    **list 不是 dict**，故 12 个训练包键逐例按顺序加时**加错一格不会报错**——只会让 13 例
    的期望值集体张冠李戴，而 ``zip`` 那一边一声不响（每一条断言都仍然「通过」，只是通过得
    毫无意义）。

    既有的 ``test_golden_cases_match_expected_labels`` **不覆盖本条**：它断言的是
    ``len(report.results) == len(cases["expected"])``，比的是**生产输出**与 ``expected``，
    从头到尾没有比过 ``input`` 与 ``expected`` 的学号序。
    """
    assert len(_CASES["input"]) == 13
    assert len(_CASES["expected"]) == 13
    assert [c["student_id"] for c in _CASES["input"]] == [
        c["student_id"] for c in _CASES["expected"]
    ]
    # 13 个学号互不相同：否则「按顺序一一对应」这句话本身就没有意义
    # （``_meta.input_schema.student_id`` 逐字写着它）
    assert len(set(_CASE_IDS)) == 13
    # 12 个新键逐例齐全（offender 一次性报全，Ruling 157）
    offenders = [
        (exp["student_id"], sorted(set(_PINNED_PACKAGE_KEYS) - set(exp)))
        for exp in _CASES["expected"]
        if set(_PINNED_PACKAGE_KEYS) - set(exp)
    ]
    assert offenders == [], f"这些例缺训练包键: {offenders}"


@pytest.fixture(scope="module")
def golden_packages():
    """13 例黄金用例 → 逐例的「模板 → 训练包」实测值（12 个键，与夹具 ``expected`` 同形）。

    链路与 :func:`app.pipeline.prescription_stage.generate_prescriptions` 的**算法部分**
    逐字同构（``match_template`` → ``assemble`` → ``apply_safety``）。差别只有两处，都是
    「黄金用例没有库」的必然结果，⚠️ 两处的代价都写明（硬规矩 #39）：

    * **``StudentProfile`` 从一个瞬态 ``models.Student`` 造**：夹具只给 ``age``、不给
      ``birth``，故 ``birth`` 由 ``age`` 与 :data:`_AS_OF` 反推（见那个常量的注释）。
      ``Student`` 实例**不入 session、不落库**——``_profile_of`` 只读它的
      ``id`` / ``sex`` / ``birth`` 三列，故一个瞬态实例与一行真数据在它眼里没有区别。
      **复用 ``_profile_of`` 而不在测试里重抄映射**：``endurance_score`` 的两项均值口径
      （spec §14 #36 的邻居，唯一所有者是 ``prescription_stage._endurance_score``）与
      ``bmi`` 的读取口径都只有一个住址（Global Constraint #3）。
    * **不求值 spec §5.2 的五触发**：夹具是**单日**的，既没有 ``last_prescription``
      也没有采集日，五个判据一个都无从成立。故本条钉的是「**模板 → 训练包**」那两格，
      **不钉**触发；触发由 ``tests/domain/test_prescription_triggers.py`` 与
      ``tests/pipeline/test_prescription_stage.py`` 守（含触发 2 那条「删掉当天分层行仍成立」）。
      ⚠️ 于是 ``expected[i]["label_at_generation"]`` 钉的是「那一列填的是**当天分层结果的
      那一个标签**」，**不是**触发 2 本身。

    ``module`` 作用域：13 例共用一次 ``_from_golden_cases``（它要读国标评分表并算一次
    ``compute_snapshot``），逐例重建会让同一份快照算 13 遍。
    """
    persons, snapshot = run_stratify._from_golden_cases(_CASES["input"])
    evaluated = run_stratify.evaluate(persons, snapshot)
    rows = []
    for index, (case, one) in enumerate(zip(_CASES["input"], evaluated)):
        result = stratify(one.derived)
        snap = input_snapshot_of(one, result, snapshot)
        outcome = match_template(
            MatchInput(
                layer=Layer(snap["label"]),
                dominant_bucket=snap["dominant_bucket"],
                body_comp_abnormal=snap["C"],
            ),
            templates(),
        )
        row = {"student_id": case["student_id"], "bmi": snap["bmi"],
               "match_status": outcome.status.value}
        row.update({key: None for key in _PINNED_PACKAGE_KEYS[2:]})
        if outcome.template is None:
            # Z0 闸门（``no_layer``）：**不得生成处方**，且这一档必须留痕
            # （Review Focus 第 3 条）。留痕的载体是 ``match_status`` 本身——
            # 六种 status 没有一种静默返回 ``None``。
            rows.append(row)
            continue
        template = outcome.template
        age = int(case["age"])
        birth = dt.date(_AS_OF.year - age, _AS_OF.month, _AS_OF.day)
        student = models.Student(id=index + 1, sex=case["sex"], birth=birth)
        profile = _profile_of(student, snap, _AS_OF)
        package = assemble(profile, template, _AS_OF, exercises=exercises())
        safety = apply_safety(
            package,
            SafetyInput(
                bmi=profile.bmi,
                muscle_mass_kg=profile.muscle_mass_kg,
                muscle_p10=profile.muscle_p10,
                body_fat_abnormal=snap["C"],
            ),
            equivalence(),
            template=template,
            exercises=exercises(),
        )
        block = safety.package.weeks[0].sessions[0].blocks[0]
        after = safety.package.assembly_snapshot
        row.update({
            "template_id": template.template_id,
            # 生产上 ``prescription.label_at_generation`` 那一列写的就是**当天分层结果的
            # 标签**（``prescription_stage`` 的 ``"label_at_generation": label``），
            # 而 ``label`` 来自 ``result.label`` == ``snap["label"]``。
            "label_at_generation": snap["label"],
            "week1_block0_exercise_ref": block.exercise_ref,
            # ⚠️ 显式转 ``list``：JSON 没有 tuple，夹具里存的是 ``[116, 137]``。口径与
            # ``training_package_payload`` 对 ``hr_zone`` 的处置逐字相同（不转的话
            # 「写进去的那个对象」与「读回来的那个对象」不相等）。
            "week1_block0_hr_zone": None if block.hr_zone is None else list(block.hr_zone),
            "week1_block0_weekly_volume": block.weekly_volume,
            "week1_block0_volume_unit": block.volume_unit,
            "needs_review": safety.needs_review,
            "safety_substitution_count": len(safety.substitutions),
            "safety_triggers": list(after["safety_triggers"]),
            "safety_skipped": list(after["safety_skipped"]),
        })
        rows.append(row)
    return rows


@pytest.mark.parametrize("index,student_id", list(enumerate(_CASE_IDS)))
def test_golden_cases_reach_the_training_package(golden_packages, index, student_id):
    """spec §12：黄金用例的链路延伸到「**模板 → 训练包**」（Plan 02 Task 9）。

    Plan 01 做到了「原始值 → 国标得分 → 百分位 → 短板 → 标签」，本条接上最后两格，
    于是 §12 那一行「断言完整链路：原始值 → … → 标签 → **模板 → 训练包**」逐字达成。

    ⚠️ **与既有的 ``test_golden_cases_match_expected_labels`` 并列、不合并**（P9-A4 /
    硬规矩 #56）：那一条守的是「标签」那一环，把训练包的断言塞进去会让它红的时候
    **分不清是哪一环断了**。

    期望值的取法（跑一次生产、粘进夹具、**逐条人读确认**）与测量条件写在夹具的
    ``_meta.training_package_provenance``，逐条人读的记录在 ``task-9-report.md`` 第 ② 节。
    **不要 blindly 改这里或夹具的任何一侧**——Plan 01 的 ``reason`` 字段就是这么漂移的
    （Ruling 145）。

    ⚠️ **本条钉不住什么**（硬规矩 #39，三条都在夹具 ``_meta.caveats_training_package`` 里
    有对应的一段）：

    1. **五触发**——单日夹具，见 ``golden_packages`` 的 docstring；
    2. **spec §7.4 的 ``bmi_over_30`` 与 ``muscle_low_p10`` 两档**——P9-A1 之后 13 例的
       ``bmi`` 各有其值（改前恒 ``None``），故 ``bmi_over_30`` 从「结构上不可求值」变成
       「**可求值但不命中**」：13 例的 ``bmi`` 全落在 ``[18.9, 25.7]``，没有一例 > 30；
       ``muscle_low_p10`` 仍结构上不可达（``muscle_p10`` 恒 ``None``）。于是
       ``needs_review`` 与 ``safety_substitution_count`` 在 13 例里**恒为 ``False`` / ``0``**，
       这两档的**行为守卫**在 ``tests/domain/test_prescription_safety.py``；
    3. **装配失败与换处方两档**——前者要一套坏模板、后者要两天，都在
       ``tests/pipeline/test_prescription_stage.py``。

    13 例里 **12 例有处方**（``match_status == "matched"``）、**1 例断言「无处方」**
    （GC10：``valid_count = 3 < 4`` → Z0 → ``no_layer``，其余 10 个键全为 ``null``）。
    """
    exp = _CASES["expected"][index]
    got = golden_packages[index]
    note = exp["note"]
    # 对齐前置：参数化的 index 与夹具的两条 list 都指同一个学生（P9-A4 的那条守卫
    # 钉的是夹具自身，本行钉的是「本条测试拿对了格子」）
    assert exp["student_id"] == student_id
    assert got["student_id"] == student_id
    # offender 一次性报全（Ruling 157：循环里逐条 assert 会在第一格就停、证据被截断）
    offenders = [
        f"{key}: 期望 {exp[key]!r} / 实际 {got[key]!r}"
        for key in _PINNED_PACKAGE_KEYS
        if got[key] != exp[key]
    ]
    assert offenders == [], (
        f"{student_id} 的「模板 → 训练包」期望值不符（{note[:60]}…）：\n  "
        + "\n  ".join(offenders)
    )

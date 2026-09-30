import json, pathlib
from app.seed.config import SeedConfig
from app.seed.generate import build_dataset
from app.pipeline.run_stratify import stratify_dataset   # Task 10 提供

GOLDEN = pathlib.Path(__file__).parents[1] / "fixtures" / "golden_cases.json"

def test_golden_cases_match_expected_labels():
    """12 个手工构造的典型学生，断言原始值→得分→百分位→短板→标签全链路。"""
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

def test_target_layer_distribution_within_tolerance():
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
    ds = build_dataset(SeedConfig(students=500, weeks=16, seed=20250828))
    dist = stratify_dataset(ds).distribution
    assert abs(dist["red"]    - 0.20) <= 0.05
    assert abs(dist["yellow"] - 0.45) <= 0.05
    assert abs(dist["green"]  - 0.35) <= 0.05
    assert dist["red"] > 0 and dist["yellow"] > 0 and dist["green"] > 0

"""Task 9 落地脚本 01：把 GC14 写进 backend/tests/fixtures/golden_cases.json。

**为什么用脚本而不是编辑器**：这份文件 43 571 B / 892 行、工作树全是 CRLF 而 index 是 LF
（`git ls-files --eol` 实测 `i/lf w/crlf attr/`），而它**没有**指纹常量钉住
（探针 06 实测：全仓 5 个指纹是国标 CSV / exercises.yaml / exercise_equivalence.yaml /
alert_rules.yaml / 18 套模板，一个都不在它上面）。故它的纪律只剩两条：
① 改完 CRLF 计数仍等于行数（不混行尾）；② 既有 13 例的**输入**一个字节都不动
（那是 Plan 01 已逐条人读确认的值）。

探针 06 已实测 `json.dumps(json.loads(text), indent=2, ensure_ascii=False) + "\\n"`
与 LF 归一化后的原文**逐字相等**，故「load → 改 dict → dump」不会顺手动到别处。
每一处 `_meta` 改写都是**精确串替换 + 断言命中一次**：找不到就当场 KeyError/AssertionError，
不会静默漏改。
"""
import datetime as dt
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
GOLDEN = BACKEND / "tests" / "fixtures" / "golden_cases.json"

before = GOLDEN.read_bytes()
text = before.replace(b"\r\n", b"\n").decode("utf-8")
data = json.loads(text)

# ---------------------------------------------------------------------------
# ① GC14 的 input（探针 04：目标得分经生产 raw_from_score 反查，score_item 精确往返）
# ---------------------------------------------------------------------------
GC14_CURR = {
    "height_cm": 175.0,
    "weight_kg": 95.0,
    "vital_capacity_ml": 3700.0,
    "sprint_50m_s": 9.5,
    "sit_and_reach_cm": 3.7,
    "standing_jump_cm": 228.0,
    "strength_count": 10.0,
    "distance_run_s": 292.0,
}
GC14_INPUT = {
    "student_id": "GC14",
    "sex": "male",
    "age": 19,
    "years": 1.0,
    "snapshot_muscle_p20": 33.2,
    "body_comp": {"body_fat_pct": 28.0, "muscle_mass_kg": 45.0, "smi": None},
    "curr": GC14_CURR,
    "prev": dict(GC14_CURR),
}

GC14_NOTE = (
    "**GC14（Plan 03 Task 9 补）**：spec §7.4 三档安全触发里「BMI > 30」那一档，在此前 13 例里"
    "**可求值但不命中**（bmi 全落在 [18.9, 25.7]），故 needs_review 与 safety_substitution_count "
    "在黄金用例里恒为 false / 0。本例身高 175.0 / 体重 95.0 → bmi = round(95 / 1.75², 1) = "
    "**31.0 > 30**，触发 1 第一次真的命中；体脂率 28.0% > 男生 20% 阈值 → C=True"
    "（reasons=(\"body_fat_high\",)，肌肉量 45.0 kg **高于**本组 P20 33.2 故第二支不成立）；"
    "50 米跑 40 分 < P25 50、坐位体前屈 60 分 < P25 62 → W=2 且两项同在 speed_flexibility 桶"
    "（13 例里**没有一例**的主导桶是它）→ 命中 R1 → 红、模板 **RED-SPD-ABN-05**。"
    "⚠️ 于是本例是 14 例里**唯一同时命中两个安全触发**的（safety_triggers = "
    "[\"bmi_over_30\", \"body_fat_abnormal\"]，按 _TRIGGER_MAP 的迭代序），也是**唯一 "
    "safety_substitution_count 非 0** 的（32 = 该模板 48 个 block 里 32 个 high，"
    "sprint_50m_intervals → stationary_cycling、shuttle_run → brisk_walking，等价表 v1.0）；"
    "week1_block0_exercise_ref 因此是**替身**而不是原 ref，而替身**继承原动作的剂量**"
    "（hr_zone [116, 137]、volume_unit min、weekly_volume 48.0 × 0.8 = 38.4）。"
    "needs_review 仍是 false：v1.0 给全部 5 个 high 动作都备了 low 替身，一格都查不到空。"
    "⚠️ 它落在决策表**已覆盖的** R1 行上（与 GC01 同一行）：本例的用途是把安全后置那一环"
    "打通，不是补一行决策表。"
)

GC14_EXPECTED = {
    "student_id": "GC14",
    "note": GC14_NOTE,
    "label": "red",
    "W": 2,
    "C": True,
    "valid_count": 6,
    "dominant_bucket": "speed_flexibility",
    "trend": "稳定",
    "hit_rules": ["R1"],
    "reason": "短板 ≥2 项且体成分异常",
    "explain": (
        "红色层 ← 短板 ≥2 项且体成分异常（规则 R1）。依据：你的 50 米跑、坐位体前屈 "
        "在校内同龄男生中低于 P25（6 个有效项里 2 项短板）；体脂率 28% 超过男生 20% 阈值；"
        "历史趋势「稳定」，国标总分年均变化 +0.0 分。"
    ),
    "bmi": 31.0,
    "match_status": "matched",
    "template_id": "RED-SPD-ABN-05",
    "label_at_generation": "red",
    "week1_block0_exercise_ref": "stationary_cycling",
    "week1_block0_hr_zone": [116, 137],
    "week1_block0_weekly_volume": 38.4,
    "week1_block0_volume_unit": "min",
    "needs_review": False,
    "safety_substitution_count": 32,
    "safety_triggers": ["bmi_over_30", "body_fat_abnormal"],
    "safety_skipped": ["muscle_p10_missing"],
}

# 键序必须与既有 13 例逐字相同（expected 是 list、按键序书写，人读对账靠它）
assert list(GC14_EXPECTED) == list(data["expected"][0]), (
    list(GC14_EXPECTED), list(data["expected"][0])
)
assert list(GC14_INPUT) == list(data["input"][0])
assert len(data["input"]) == 13 and len(data["expected"]) == 13
data["input"].append(GC14_INPUT)
data["expected"].append(GC14_EXPECTED)

# ---------------------------------------------------------------------------
# ② _meta 的精确串替换（每一处都断言「恰好命中一次」）
# ---------------------------------------------------------------------------
REPLACEMENTS: list[tuple[str, str, str]] = [
    # (容器路径说明, 旧串, 新串)
    (
        "_meta.purpose",
        "spec §12 的黄金用例：13 个手工构造的典型学生，覆盖 spec §6.2 决策表的全部八行"
        "（Z0/R1/R2/Y1/Y2/Y3/Y4/G1）、两处阈值边界（男体脂率 20.0%、女体脂率 28.1%）、"
        "P25 的严格小于比较符，以及 C 的**肌肉量那一支**（GC13，**Plan 01 的** Task 10 "
        "Step 0.7 补）。",
        "spec §12 的黄金用例：14 个手工构造的典型学生，覆盖 spec §6.2 决策表的全部八行"
        "（Z0/R1/R2/Y1/Y2/Y3/Y4/G1）、两处阈值边界（男体脂率 20.0%、女体脂率 28.1%）、"
        "P25 的严格小于比较符、C 的**肌肉量那一支**（GC13，**Plan 01 的** Task 10 Step 0.7 补），"
        "以及 **spec §7.4 三档安全触发里「BMI > 30」那一档**（GC14，Plan 03 Task 9 补）。"
        "⚠️ GC14 落在决策表**已覆盖的** R1 行上（与 GC01 同一行）：加它是为了让「安全后置」"
        "那一环在黄金用例里可达，不是为了补一行决策表。",
    ),
    (
        "_meta.expected_from",
        "compute_snapshot（这 13 人自己的 curr 得分）",
        "compute_snapshot（这 14 人自己的 curr 得分）",
    ),
    (
        "_meta.expected_schema.bmi",
        "它是 spec §7.4 触发 1「BMI > 30」的**唯一输入**。13 例逐例手算复核过"
        "（见 training_package_provenance）。",
        "它是 spec §7.4 触发 1「BMI > 30」的**唯一输入**。14 例逐例手算复核过"
        "（见 training_package_provenance）。⚠️ **GC14 是唯一一例 > 30 的**"
        "（175.0 cm / 95.0 kg → 95 / 3.0625 = 31.0204… → 31.0），其余 13 例落在 [18.9, 25.7]。",
    ),
    (
        "_meta.expected_schema.match_status",
        "其余 12 例是 matched。⚠️ 六种 status 里 13 例只覆盖两种",
        "其余 13 例是 matched。⚠️ 六种 status 里 14 例只覆盖两种",
    ),
    (
        "_meta.expected_schema.week1_block0_exercise_ref",
        "取的是**安全后置之后**的那一份（故它是替身 ref 而不是原 ref；13 例里没有一例发生替换，"
        "见 safety_substitution_count）。⚠️ 命中 body_fat_abnormal 的 5 例会在**每一课的末尾**"
        "多一个 addon block，但 blocks[0] 不受影响（addon 只 extend、不插到前面）。",
        "取的是**安全后置之后**的那一份（故它是替身 ref 而不是原 ref）。⚠️ **GC14 是 14 例里"
        "唯一真的发生替换的一例**：它的 blocks[0] 原 ref 是 sprint_50m_intervals（high），"
        "被等价表 v1.0 换成 stationary_cycling（low）；其余 13 例的 blocks[0] 就是模板给的"
        "原 ref。⚠️ 替身**继承原动作的剂量**（hr_zone / intensity_text / structure / "
        "volume_unit / sessions_per_week 全原样，只换冲击等级），故 GC14 的 "
        "week1_block0_hr_zone 与 week1_block0_volume_unit 与替换前逐字相同，"
        "只有 weekly_volume 被 safety_volume_factor 0.8 乘过。⚠️ 命中 body_fat_abnormal 的 "
        "**6** 例（GC01 / GC04 / GC05 / GC12 / GC13 / GC14）会在**每一课的末尾**多一个 addon "
        "block，但 blocks[0] 不受影响（addon 只 extend、不插到前面）。",
    ),
    (
        "_meta.expected_schema.week1_block0_hr_zone",
        "13 例里只有 GC01 / GC02（红层，模板给 60–70% HRmax）非 null：HRmax = 208 − 0.7 × age"
        "（GC01 age 19 → 194.7、GC02 age 21 → 193.3），低界向下取整、高界向上取整"
        "（保守方向：区间略宽比略窄安全）。⚠️ 其余 10 例是 null 而**不是遗漏**",
        "14 例里只有 GC01 / GC02 / **GC14**（红层，模板给 60–70% HRmax）非 null："
        "HRmax = 208 − 0.7 × age（GC01 age 19 → 194.7 → [116, 137]、GC02 age 21 → 193.3 → "
        "[115, 136]、GC14 age 19 → 194.7 → [floor(116.82), ceil(136.29)] = [116, 137]），"
        "低界向下取整、高界向上取整（保守方向：区间略宽比略窄安全）。"
        "⚠️ 其余 11 例是 null 而**不是遗漏**",
    ),
    (
        "_meta.expected_schema.needs_review",
        "（P5-A3）。13 例全为 false：触发 1 要 BMI > 30，而 13 例最大只有 25.7，"
        "故等价表根本没被查过（见 caveats_training_package ②）。",
        "（P5-A3）。14 例全为 false，而**理由分两档**：GC01–GC13 的 bmi 全落在 [18.9, 25.7]，"
        "触发 1 不命中、等价表根本没被查过；**GC14 的 bmi = 31.0 让触发 1 真的命中、"
        "等价表真的被查了 32 次**，而 v1.0 给全部 5 个 high 动作都备了 low 替身"
        "（10 条映射 = 5 动作 × 2 触发），一格都查不到空 → 仍不置位。⚠️ 于是 "
        "**needs_review = true 那一档在 14 例里仍不可达**，它由 "
        "tests/domain/test_prescription_safety.py 守（见 caveats_training_package ②）。",
    ),
    (
        "_meta.expected_schema.safety_substitution_count",
        "len(SafetyOutcome.substitutions)。13 例全为 0，理由同 needs_review。"
        "⚠️ 它是**逐 block 实例**的计数（同一个 ref 在 4 周 × 4 课里出现 16 次就有 16 条），"
        "而 warnings 按 ref 去重——两者不是一个量级。",
        "len(SafetyOutcome.substitutions)。GC01–GC13 全为 0（触发 1 不命中），**GC14 = 32**："
        "RED-SPD-ABN-05 装配出 48 个 block，其中 32 个是 high"
        "（sprint_50m_intervals / shuttle_run 两个 ref），逐个被换掉。"
        "⚠️ 它是**逐 block 实例**的计数（同一个 ref 在 4 周 × 4 课里出现 16 次就有 16 条），"
        "而 warnings 按 ref 去重——两者不是一个量级：GC14 的 32 条替换只对应 **1** 条 "
        "warning，而那条 warning 说的是 addon 的训练量未指定、与替换无关。",
    ),
    (
        "_meta.expected_schema.safety_triggers",
        "按 safety.py 的 _TRIGGER_MAP 迭代序。13 例里**只有 body_fat_abnormal 命中过**"
        "（GC01 / GC04 / GC05 / GC12 / GC13，与本夹具已人读确认的 C = True 逐例吻合）。",
        "按 safety.py 的 _TRIGGER_MAP 迭代序。14 例里 **body_fat_abnormal 命中 6 例**"
        "（GC01 / GC04 / GC05 / GC12 / GC13 / **GC14**，与本夹具已人读确认的 C = True "
        "逐例吻合），**bmi_over_30 只命中 GC14**，故 GC14 是**唯一一例同时命中两个触发**的"
        "（列表是 [\"bmi_over_30\", \"body_fat_abnormal\"]，迭代序把 bmi_over_30 排在前面）。"
        "⚠️ **muscle_low_p10 在 14 例里一次都没命中**——结构上不可达，见 safety_skipped。",
    ),
    (
        "_meta.expected_schema.safety_skipped",
        "**13 例恒为 [\"muscle_p10_missing\"]**",
        "**14 例恒为 [\"muscle_p10_missing\"]**",
    ),
    (
        "_meta.expected_schema.safety_skipped（第二处）",
        "muscle_p10_missing 则**结构上无法消除**：13 人 < MIN_SAMPLE = 30，",
        "muscle_p10_missing 则**结构上无法消除**：14 人 < MIN_SAMPLE = 30，",
    ),
    (
        "_meta.training_package_provenance（守卫那一处）",
        "test_golden_cases_reach_the_training_package（13 例参数化）",
        "test_golden_cases_reach_the_training_package（14 例参数化）",
    ),
    (
        "_meta.training_package_provenance（末尾追加 GC14 的人读记录）",
        "2 个 hr_zone 都按 208 − 0.7 × age 与「低界向下、高界向上」手算过。",
        "2 个 hr_zone 都按 208 − 0.7 × age 与「低界向下、高界向上」手算过。"
        " ⚠️ **GC14 是 Plan 03 Task 9 加的第 14 例**，它的四格数字由 Plan 03 Task 9 手算复核"
        "（记录在 .superpowers/sdd/2026-10-08-实施计划03-反馈预警与CRUD-API层/"
        "task-9-report.md 第 ② 节）：weekly_volume 38.4 = block base（work_min 3 × sets 4 = 12，"
        "rest_min 2 不计入量，§14 #36）× sessions_per_week 4 × 个体修正 1.0（band=mid）"
        "× week_deltas[0] 1.0 = 48.0，再 × safety_volume_factor 0.8；hr_zone [116, 137] = "
        "[floor(194.7 × 0.60), ceil(194.7 × 0.70)] = [floor(116.82), ceil(136.29)]，"
        "而 194.7 = 208 − 0.7 × 19；template_id RED-SPD-ABN-05 按 (红层, speed_flexibility, "
        "C=True) 三元与 §7.2 勘误 ⑥ 的命名规则对过；safety_substitution_count 32 = 该模板"
        "装配出的 48 个 block 里 32 个 high（探针实测）。",
    ),
    (
        "_meta.caveats_training_package ②（整段改写）",
        "② **spec §7.4 三档触发在 13 例里的可达性**（本 Task 实测，P9-A1 之后）："
        "body_fat_abnormal **命中 5 例**（GC01 / GC04 / GC05 / GC12 / GC13；它在 P9-A1 之前"
        "也已可达，因为它读的是 C 而不是 bmi）；bmi_over_30 从「结构上不可求值」变成"
        "「**可求值但不命中**」——13 例的 bmi 全落在 [18.9, 25.7]，**没有一例 > 30**，"
        "故 needs_review 与 safety_substitutions 在 13 例里**仍恒为 false / 0**；"
        "muscle_low_p10 **仍结构上不可达**（P10 恒 None，见 expected_schema 的 safety_skipped）。"
        "要让前两档在黄金用例里真的命中，就得改某例 curr 的身高体重——那是改 Plan 01 已逐条"
        "人读确认的**输入**，本 Task 未做（未获授权），已作为关切报给控制者。"
        "这两档的**行为守卫**在 tests/domain/test_prescription_safety.py。",
        "② **spec §7.4 三档触发在 14 例里的可达性**（Plan 03 Task 9 实测，GC14 之后）："
        "body_fat_abnormal **命中 6 例**（GC01 / GC04 / GC05 / GC12 / GC13 / GC14；"
        "它读的是 C 而不是 bmi，故在 P9-A1 之前也已可达）；**bmi_over_30 命中 1 例（GC14）**"
        "——它把 Plan 02 Task 9 留下的那一格空白补上了（那时 13 例的 bmi 全落在 [18.9, 25.7]、"
        "触发 1「可求值但不命中」，故 needs_review 与 safety_substitutions 恒为 false / 0）。"
        "⚠️ 本 Task 的做法是**只新增一例、不动既有 13 例的输入**——那是 Plan 01 已逐条人读"
        "确认的值，改它就是让 13 份人读记录作废。"
        "⚠️⚠️ **muscle_low_p10 那一档仍结构上不可达，这是刻意留下的空白、不是遗漏**"
        "（硬规矩 #39）：黄金用例路径（run_stratify._from_golden_cases）**刻意不调** "
        "resolve_muscle_lines，而 14 人 < MIN_SAMPLE = 30 → 肌肉量组不产出行 → P10 恒 None "
        "→ 判据 muscle_mass_kg < muscle_p10 永不成立、safety_skipped 恒含 "
        "\"muscle_p10_missing\"。**要让它可达就得把黄金用例的样本量抬到 30 人以上，而那会"
        "改变 _meta.percentile_note 里「24 行」与全部 14 例 P25 判定线的整个前提**"
        "（校内百分位会取代国标常模兜底，14 例的 label / W / C / dominant_bucket 都要重算"
        "并重新逐条人读确认），故 Plan 02 Task 9 与 Plan 03 Task 9 两轮都**决定不做**。"
        "它的**行为守卫**在 tests/domain/test_prescription_safety.py（那里直接构造 "
        "SafetyInput、不经黄金用例路径），而「黄金用例路径的 P10 恒 None」这件事本身由 "
        "tests/pipeline/test_prescription_stage.py 的 "
        "test_golden_case_path_reads_height_and_weight_from_curr_and_leaves_p10_none 钉住。"
        "⚠️ 同理 **needs_review = true 那一档在 14 例里仍不可达**：等价表 v1.0 给全部 5 个 "
        "high 动作都备了 low 替身（10 条映射），故「命中却查不到替身」在生产参考数据下"
        "永不发生，它同样由 tests/domain/test_prescription_safety.py 守。",
    ),
    (
        "_meta.caveats_training_package ③",
        "③ **13 例覆盖不到「装配失败」与「换处方」两档**",
        "③ **14 例覆盖不到「装配失败」与「换处方」两档**",
    ),
    (
        "_meta.input_schema.student_id",
        "只会让 13 例的期望值集体张冠李戴",
        "只会让 14 例的期望值集体张冠李戴",
    ),
    (
        "_meta.input_schema.snapshot_muscle_p20（第一处）",
        "**黄金用例仍走手工给定**：13 人 < MIN_SAMPLE=30，",
        "**黄金用例仍走手工给定**：14 人 < MIN_SAMPLE=30，",
    ),
    (
        "_meta.input_schema.snapshot_muscle_p20（第二处）",
        "GC01–GC12 的肌肉量都**高于**本组 P20，故它们的 C 只由体脂率决定，"
        "传它还是传 None 期望值都成立；GC13 是唯一依赖它的一例。",
        "GC01–GC12 与 **GC14** 的肌肉量都**高于**本组 P20（GC14 是 45.0 kg vs 33.2），"
        "故它们的 C 只由体脂率决定，传它还是传 None 期望值都成立；"
        "GC13 是唯一依赖它的一例。",
    ),
    (
        "_meta.bmi（末尾那一处）",
        "13 例的 bmi 于是各有其值、逐例钉在 expected[i][\"bmi\"]。",
        "14 例的 bmi 于是各有其值、逐例钉在 expected[i][\"bmi\"]"
        "（Plan 03 Task 9 加 GC14 之后，14 例里**恰好一例 > 30**）。",
    ),
    (
        "_meta.percentile_note（第一处 a：人数）",
        "13 人 < MIN_SAMPLE=30，故 compute_snapshot 对",
        "14 人 < MIN_SAMPLE=30，故 compute_snapshot 对",
    ),
    (
        "_meta.percentile_note（第一处 b：24 行 + GC14 的影响）",
        "共 **24 行**（本轮亲跑：6 项 × 2 性别 × 2 年级组，source 全为 national）。",
        "共 **24 行**（Plan 03 Task 9 复跑：6 项 × 2 性别 × 2 年级组，source 全为 national）。"
        "⚠️ **加 GC14 之后行数仍是 24**：它落在 (male, 大一、大二) 这个**已存在**的组里，"
        "只把那 6 行的 sample_size 从 **8 抬到 9**，而 p10/p20/p25/p50/p75 五档判定线与 "
        "source **逐格不变**（national_norm 的判定线来自国标表、与样本无关；探针实测"
        "两侧 24 行只差 sample_size 一格）。",
    ),
    (
        "_meta.percentile_note（第二处）",
        "对 13 例的 label / W / C / valid_count / hit_rules **零影响**",
        "对 14 例的 label / W / C / valid_count / hit_rules **零影响**",
    ),
    (
        "_meta.percentile_note（第三处）",
        "但意味着这 13 例守卫的是**国标常模判定线**那一路",
        "但意味着这 14 例守卫的是**国标常模判定线**那一路",
    ),
]


def _apply(container, old: str, new: str, where: str) -> None:
    """在 ``container`` 的**所有字符串值**里把 ``old`` 精确替换成 ``new``，断言恰好一次。"""
    hits = []
    for key, value in container.items():
        if isinstance(value, str) and old in value:
            hits.append(key)
    assert len(hits) == 1, f"{where}: 命中 {len(hits)} 处（{hits}），应当恰好 1 处"
    key = hits[0]
    assert container[key].count(old) == 1, f"{where}: 同一个值里命中多次"
    container[key] = container[key].replace(old, new)


meta = data["_meta"]
for where, old, new in REPLACEMENTS:
    if where.startswith("_meta.expected_schema"):
        _apply(meta["expected_schema"], old, new, where)
    elif where.startswith("_meta.input_schema"):
        _apply(meta["input_schema"], old, new, where)
    else:
        _apply(meta, old, new, where)

# ---------------------------------------------------------------------------
# ③ 落盘：CRLF（与工作树既有 892 行逐一致），并复核行尾与既有 13 例的输入未动
# ---------------------------------------------------------------------------
dumped = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
GOLDEN.write_bytes(dumped.replace("\n", "\r\n").encode("utf-8"))

after = GOLDEN.read_bytes()
print("bytes:", len(before), "->", len(after))
print("CRLF:", after.count(b"\r\n"), "| bare LF:", after.count(b"\n") - after.count(b"\r\n"))
print("sha256[:16] (as-is):", hashlib.sha256(after).hexdigest()[:16].upper())
norm = after.replace(b"\r\n", b"\n")
print("sha256[:16] (CRLF->LF):", hashlib.sha256(norm).hexdigest()[:16].upper())
print("lines:", norm.count(b"\n"))

reloaded = json.loads(norm.decode("utf-8"))
print("input:", len(reloaded["input"]), "expected:", len(reloaded["expected"]))
# 既有 13 例的 input 与 expected **逐格未动**（两侧不同源：左边读回磁盘、右边是内存里的原件）
original = json.loads(text)
assert reloaded["input"][:13] == original["input"], "既有 13 例的 input 被动过了！"
assert reloaded["expected"][:13] == original["expected"], "既有 13 例的 expected 被动过了！"
assert reloaded["input"][13] == GC14_INPUT
assert reloaded["expected"][13] == GC14_EXPECTED
# _meta 的键集不变（只改值、不加键）
assert set(reloaded["_meta"]) == set(original["_meta"])
assert set(reloaded["_meta"]["expected_schema"]) == set(original["_meta"]["expected_schema"])
assert set(reloaded["_meta"]["input_schema"]) == set(original["_meta"]["input_schema"])
assert reloaded["_meta"]["muscle_p20_by_group"] == original["_meta"]["muscle_p20_by_group"]
print("既有 13 例的 input / expected 逐格未动：OK")
print("GC14 已写入：OK")
print("_meta 键集不变、muscle_p20_by_group 不变：OK")
print("done at", dt.datetime.now().isoformat(timespec="seconds"))

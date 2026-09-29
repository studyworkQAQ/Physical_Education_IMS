"""InBody 体成分记录生成（肌肉量 / 体脂率 / 骨骼肌指数）。

三个量的生成口径不一样，这一点必须先说清楚：

* **体脂率**由潜变量牵引——体能好的人体脂低，这是``latent_fitness`` 与体成分之间唯一
  真实的耦合，也是分层规则里 ``C``（体成分异常）能与体能短板互相印证的原因。若体脂
  独立随机，「红色层的人同时体脂超标」就变成纯粹的巧合，处方引擎的复合判据在演示数据
  上永远触发不出有意义的组合。
* **骨骼肌指数 SMI** 同样随潜变量正向变动，幅度小得多（它是形态量，训练半年变化有限）。
* **肌肉量**不独立抽：由 ``SMI × 身高² × 折算系数`` 算出。三个量因此内部自洽——
  独立抽三次会得到「SMI 很高但肌肉量很低」这种仪器不可能同时报出的组合。

**所有取值都夹在 ``data/indicator_ranges.yaml`` 的合理区间内部**（而且留了余量）：
生成出来的干净数据不该被清洗层当成异常值夹取，否则 ``inject_dirty`` 注入的
``outlier`` 与「本来就越界」混在同一批 ``outlier_corrected`` 条目里，Task 5 的交叉验证
就分不清哪一条是谁造成的。
"""
import numpy as np

from app.seed.config import SEMESTERS, TIMEPOINT_SEQUENCE, SeedConfig, timepoint_date

# 体脂率：性别基准 + 潜变量牵引 + 个体稳定差异 + 单次测量噪声。
# 缺省配置下男性均值 17%、女性 27%，配上 −3.0 / −3.5 的潜变量斜率后，
# 「男 > 20%、女 > 28%」的异常率实测约 0.36，落在简报要求的 0.20–0.50 区间中段。
BODY_FAT_BASE: dict[str, float] = {"male": 17.0, "female": 27.0}
BODY_FAT_LATENT_SLOPE: dict[str, float] = {"male": -3.0, "female": -3.5}
BODY_FAT_RESIDUAL_SD: dict[str, float] = {"male": 4.5, "female": 5.5}
BODY_FAT_PERSON_SD = 2.0        # 个体稳定差异（同一人跨批次共享）
BODY_FAT_MEASURE_SD = 1.2       # 单次测量噪声
BODY_FAT_RANGE: tuple[float, float] = (5.0, 55.0)   # ⊂ yaml 的 [3, 60]

# 学年与时点上的漂移：一年前体脂略高，一学期上下来略降。量级都远小于个体差异，
# 否则「异常率」会随时点大幅摆动，而简报的断言是对全部记录求一个总比例。
PREVIOUS_YEAR_BODY_FAT_SHIFT = 0.8
TIMEPOINT_BODY_FAT_DRIFT: dict[str, float] = {"week1": 0.0, "week8": -0.3, "week16": -0.6}

# 骨骼肌指数：男性约 8.4、女性约 6.8（InBody 对大学生的常见读数量级）
SMI_BASE: dict[str, float] = {"male": 8.4, "female": 6.8}
SMI_RESIDUAL_SD: dict[str, float] = {"male": 0.9, "female": 0.8}
SMI_LATENT_SLOPE = 0.3
SMI_PERSON_SD = 0.25
SMI_MEASURE_SD = 0.15
SMI_RANGE: tuple[float, float] = (5.0, 12.5)       # ⊂ yaml 的 [4, 15]

# SMI 的分子是四肢骨骼肌量（ASMM），而 ``muscle_mass_kg`` 记的是全身骨骼肌量，
# 故需要一个折算系数。取 1.5 是量级上的近似（真实比值随性别与训练水平在 1.5–1.8 之间），
# 选它的判据是「算出来的分布落在 InBody 对中国大学生的常见读数区间」：
# 男 8.4 × 1.72² × 1.5 ≈ 37 kg、女 6.8 × 1.60² × 1.5 ≈ 26 kg。
MUSCLE_MASS_PER_SMI = 1.5
# 下界会在「最矮的学生 × 最低的 SMI」上真的夹住（152 cm × SMI 5.0 × 1.5 ≈ 17.3 kg，
# 而 yaml 的合理下界是 20）。这类记录占比不足 1%，夹到 22 后仍在生理上说得过去，
# 且换来的是「生成的干净数据一条都不会被清洗层当异常值夹取」这条整体保证。
MUSCLE_MASS_RANGE: tuple[float, float] = (22.0, 85.0)   # ⊂ yaml 的 [20, 90]


def make_body_comp(
    population: list[dict],
    latents: dict[int, dict[str, float]],
    cfg: SeedConfig,
    rng: np.random.Generator,
) -> list[dict]:
    """生成两学年 × 三时点 × 全体学生的体成分记录。

    键为 ``student_id`` / ``student_no`` / ``measured_on`` / ``muscle_mass_kg`` /
    ``body_fat_pct`` / ``smi``；后四列中 ``measured_on`` 与三个测量列即
    :data:`app.adapters.base.BODY_COMP_COLUMNS` 的契约列，``student_id`` 是合成序号、
    不写盘（体成分 CSV 里没有这一列，它只在数据集内部用来关联 ``population``）。

    ``measured_on`` 取该学期该采集节点的日期，与同批次的 ``tested_on`` 相同——InBody
    与体测在同一天完成，这也是 ``body_composition`` 上
    ``uq_body_composition_student_measured_on`` 唯一约束能被满足的原因：一名学生
    两学年共 6 个互不相同的测量日。

    个体稳定差异（``*_PERSON_SD``）按 ``population`` 列表序**先**整批抽完，再进「学期 →
    时点 → 学生」三层循环抽单次噪声。两阶段分开是为了让同一个人跨批次的读数围绕同一条
    水平线波动；反过来在循环里现抽「个体差异」，就等于每次测量都换一个人。
    """
    total = len(population)
    sex_of = [person["sex"] for person in population]
    height_of = np.array([person["height_cm"] for person in population])
    latent_of = np.array([latents[p["student_id"]]["fitness"] for p in population])

    fat_base = np.array([BODY_FAT_BASE[sex] for sex in sex_of])
    fat_slope = np.array([BODY_FAT_LATENT_SLOPE[sex] for sex in sex_of])
    fat_sd = np.array([BODY_FAT_RESIDUAL_SD[sex] for sex in sex_of])
    smi_base = np.array([SMI_BASE[sex] for sex in sex_of])
    smi_sd = np.array([SMI_RESIDUAL_SD[sex] for sex in sex_of])

    fat_person = rng.normal(0.0, BODY_FAT_PERSON_SD, total)
    smi_person = rng.normal(0.0, SMI_PERSON_SD, total)

    records: list[dict] = []
    for plan in SEMESTERS:
        year_shift = 0.0 if plan.is_current else PREVIOUS_YEAR_BODY_FAT_SHIFT
        for timepoint in TIMEPOINT_SEQUENCE:
            measured_on = timepoint_date(plan, timepoint).isoformat()
            drift = TIMEPOINT_BODY_FAT_DRIFT[timepoint]
            for index, person in enumerate(population):
                body_fat = float(
                    np.clip(
                        fat_base[index]
                        + fat_slope[index] * latent_of[index]
                        + fat_person[index]
                        + rng.normal(0.0, float(fat_sd[index]))
                        + year_shift
                        + drift,
                        *BODY_FAT_RANGE,
                    )
                )
                smi = float(
                    np.clip(
                        smi_base[index]
                        + SMI_LATENT_SLOPE * latent_of[index]
                        + smi_person[index]
                        + rng.normal(0.0, float(smi_sd[index])),
                        *SMI_RANGE,
                    )
                )
                muscle_mass = float(
                    np.clip(
                        smi * (height_of[index] / 100.0) ** 2 * MUSCLE_MASS_PER_SMI,
                        *MUSCLE_MASS_RANGE,
                    )
                )
                records.append(
                    {
                        "student_id": person["student_id"],
                        "student_no": person["student_no"],
                        "measured_on": measured_on,
                        "muscle_mass_kg": round(muscle_mass, 1),
                        "body_fat_pct": round(body_fat, 1),
                        "smi": round(smi, 1),
                    }
                )
    return records

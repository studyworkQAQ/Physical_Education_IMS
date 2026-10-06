"""InBody 体成分记录生成（肌肉量 / 体脂率 / 骨骼肌指数）。

三个量的生成口径不一样，这一点必须先说清楚：

* **体脂率**由潜变量牵引——体能好的人体脂低，这是``latent_fitness`` 与体成分之间唯一
  真实的耦合，也是分层规则里 ``C``（体成分异常）能与体能短板互相印证的原因。若体脂
  独立随机，「红色层的人同时体脂超标」就变成纯粹的巧合，处方引擎的复合判据在演示数据
  上永远触发不出有意义的组合。
* **骨骼肌指数 SMI** 同样随潜变量正向变动，幅度小得多（它是形态量，训练半年变化有限）。
* **肌肉量**不独立抽：由 ``SMI × 身高² × 折算系数`` 算出。三个量因此内部自洽——
  独立抽三次会得到「SMI 很高但肌肉量很低」这种仪器不可能同时报出的组合。

  ⚠️ **这条自洽性有一个例外：被 ``MUSCLE_MASS_RANGE`` 下界夹住的那批记录**（Ruling 222）。
  夹取只改 ``muscle_mass_kg``、**不回算 ``smi``**，故那批记录落盘后
  ``肌肉量 ≠ SMI × 身高² × 1.5``。本轮亲跑（500 人 / ``seed=20250828``；容差取**逐记录的
  舍入传播量** ``0.05 × 身高² × 1.5 + 0.05``——落盘的 ``smi`` 只有 1 位小数，它的 ±0.05
  会传播成 ±0.05×身高²×1.5 kg ≈ ±0.22 kg（身高 1.72 m），用固定小容差会把舍入噪声
  误报成违例：实测固定容差 0.05 / 0.10 / 0.15 kg 会分别报出 76.5% / 53.4% / 31.4% 的
  「违例」，全是假阳性）::

      口径                违例 / 分母        其中落在下界 22.0   学生级       违例者身高
      ------------------  -----------------  -----------------  -----------  --------------
      clean（注入前）      138 / 3000 = 4.60%  **138 / 138**      87/500=17.4% [152.0, 169.4] cm
      缺省注入             161 / 2786 = 5.78%  130 / 161          109/500=21.8% [152.0, 179.0] cm
                          （分母 = 非 None 行；全行分母 3033 → 5.31%）

  clean 那一列的 **138/138** 就是结论：违例**全部**由下界夹取造成，一个不多一个不少。
  缺省注入多出的 31 条由 ``outlier`` 注入改掉 ``muscle_mass_kg``（抬到 yaml 上限的 1.5 倍）
  造成，与本段无关。

  **方向恰好与本段原话说的相反**：不是「SMI 很高但肌肉量很低」，而是 **SMI 很低、
  肌肉量被抬到 22.0**。Plan 02/03 若同时消费 ``smi`` 与 ``muscle_mass_kg`` 两列，会在这
  ~5% 的记录上得到自相矛盾的结论**且不报错**——代价的完整版见下面 ``MUSCLE_MASS_RANGE``
  的注释。**守卫**：``tests/seed/test_generate.py`` 的
  ``test_unclamped_body_comp_records_satisfy_the_muscle_mass_identity``
  （它同时钉住 ``MUSCLE_MASS_PER_SMI = 1.5`` 这个此前**零测试引用**的常量，
  以及 clean 下 138 条夹取这个数）。

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
# 而 yaml 的合理下界是 20）。夹到 22 后仍在生理上说得过去，且换来的是「生成的干净数据
# 一条都不会被清洗层当异常值夹取」这条整体保证。
#
# ⚠️ **本处此前印的「这类记录占比不足 1%」是错的：实测 5.0–5.4%（记录级）/ 18.6%（学生级）**
# （Ruling 222）。测量方法：给本模块的 ``np.clip`` 套一层探针、读**生产代码自己的中间状态**
# （不是重新推导一遍公式——硬规矩 #6）。条件：500 人 / ``seed=20250828`` / 探针按
# ``(a_min, a_max) == MUSCLE_MASS_RANGE`` 认出肌肉量那一次 clip 调用。五种口径，
# **没有一个接近 1%**::
#
#     口径                                                 分数           百分比
#     ---------------------------------------------------  -------------  -------
#     生成时被下界夹住的记录（clean 与缺省注入**同值**）       156 / 3000     5.20%
#     同上，分母换成缺省注入后的 ds 行数                       156 / 3033     5.14%
#     同上，分母换成缺省注入后的非 None 行                     156 / 2786     5.60%
#     落盘 muscle_mass_kg 恰为 22.0（clean / 缺省注入）        158 / 3000     5.27%
#                                                            152 / 3033     5.01%
#     **学生级**：至少有一条落在 22.0（clean / 缺省注入）       93 / 500      18.6%
#                                                             89 / 500      17.8%
#
# 被夹**前**的值区间是 **[17.328, 21.992] kg**，故最多被抬 **4.67 kg**（= 22.0 − 17.328）。
# 上界 85.0 夹取 **0 条**。「clean 与缺省注入同值 156」是因为 ``inject_dirty`` 不回算生成值、
# 只改落盘的那一份（``generate.py`` 的 ``inject_dirty`` 返回新列表、输入行不被改动）。
# 落盘 22.0 的行数（158）比被夹数（156）多 **2**：真值落在 [21.95, 22.0) 的记录经
# ``round(..., 1)`` 也写成 22.0，那 2 条**没有被夹**、只是舍入到下界。
#
# **这不是纯文档瑕疵**：上面那句「不足 1%」正是给「把下界从 yaml 的 20 抬到 22」这个决定
# 做的成本论证。真实代价是 **5.2% 的记录被抬了最多 4.67 kg、18.6% 的学生至少有一条**，
# 外加模块 docstring 里记的那一条——**这三列的自洽性在夹住处失效**（``smi`` 与
# ``muscle_mass_kg`` 在 4.60% 的记录上互相矛盾，正是本模块 docstring 说「仪器不可能同时
# 报出」的那类组合）。与账本评为「20 条里最危险」的 ``derive.py`` 那条（4% vs 25%）同类：
# 一个数量级的偏差被写成「不足 1%」，读者会据此认为这个决定几乎没有代价。
# **守卫**：夹取条数 138（clean、非 None 行分母 3000）由
# ``tests/seed/test_generate.py`` 的
# ``test_unclamped_body_comp_records_satisfy_the_muscle_mass_identity`` 钉住；
# 上表其余四种口径**不被守卫**（硬规矩 #39：它们是这一处成本论证的取证，不是回归网）。
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

"""占位版体育学习兴趣量表（spec §10.9）：5 维度 × 5 点李克特。

**这是占位量表，不是已验证的测量工具。** 五个维度（运动乐趣、运动能力自信、健康认知、
同伴互动、教师评价）与 5 点计分只保证「形状对、取值域对、与体能有弱正相关」，
不保证任何心理测量学性质（信度、效度、因子结构一律未验证）。spec §14 待确认 #15 的
真实量表到位后，本模块的维度清单、题量与计分方式都要替换，故此处**不做任何超出占位
需要的抽象**（不建题库、不建反向计分、不建缺失答题模型）。

**为什么问卷总分要与 ``latent_fitness`` 弱相关（约 0.3）而不是完全无关**
体育学习兴趣与体能水平在真实人群里确有中等偏弱的正相关：体能好的学生更可能从运动中
获得乐趣与自信。完全独立会让「兴趣高但体能差」与「兴趣低但体能差」等概率出现，
处方引擎就无法演示「兴趣画像影响处方选择」这条路径；而强相关（>0.6）又等于宣称兴趣
只是体能的别名，那是伪造。0.3 是刻意选定的弱耦合。

**为什么问卷不接受 ``missing`` / ``outlier`` / ``unit_error`` 注入（Ruling 34）**
适配器契约声明的是 ``total: float`` 与 ``dimensions: dict[str, float]``，**没有 ``None``
的位置**：空白单元格会让 ``MockLePaoAdapter`` 抛 ``ValueError`` 并在抽取阶段中断整条
管道；兜底成 ``0.0`` / ``{}`` 则会凭空造出「对体育毫无兴趣」的学生（Ruling 21 禁止的
静默捏造）。所以问卷只接受 ``duplicate``，由
``uq_interest_survey_student_semester_filled_on`` + ``repo.upsert`` 兜住。
"""
import math

import numpy as np

from app.seed.config import SEMESTERS, SeedConfig, timepoint_date

DIMENSIONS: tuple[str, ...] = (
    "运动乐趣",
    "运动能力自信",
    "健康认知",
    "同伴互动",
    "教师评价",
)
QUESTIONS_PER_DIMENSION = 2
QUESTION_COUNT = len(DIMENSIONS) * QUESTIONS_PER_DIMENSION
LIKERT_MIN = 1
LIKERT_MAX = 5

# 总分与 latent_fitness 的目标相关系数（约 0.3）。做法是先把潜变量投影成一个
# 相关系数恰为 LIKERT_LATENT_WEIGHT 的标准正态量 z，再由 z 生成答题倾向：
#   z = w·latent + sqrt(1 − w²)·N(0,1)  ⟹  corr(z, latent) = w
# 这样「弱相关」是构造出来的而不是碰运气调出来的；李克特取整与 1–5 夹取会再削掉一点，
# 实测落在 0.30 附近。
LIKERT_LATENT_WEIGHT = 0.32
SURVEY_MEAN = 3.2           # 5 点量表的中性偏正倾向
# z 每变动 1 个标准差，答题倾向变动 0.65 分。这个值是按实测反推的：李克特取整、
# 1–5 夹取与「每人两学年共用一个倾向、只叠小幅漂移」三处各削掉一点相关，
# 0.65 让 corr(total, latent_fitness) 落在 0.30 附近（实测 0.295–0.313，随随机数
# 消耗顺序略有出入）。调到 0.9 以上相关系数就不再上升（0.31 附近饱和），
# 只会把维度分挤到 1 与 5 两个端点上——那是量表的天花板/地板效应，不是更强的耦合。
SURVEY_SLOPE = 0.65
ITEM_NOISE_SD = 0.55        # 单题相对该生倾向的离散度
SEMESTER_NOISE_SD = 0.25    # 同一人两次发放之间的倾向漂移
# 上学年整体略低一点：兴趣随课程推进小幅上升，量级远小于个体差异
PREVIOUS_YEAR_SURVEY_SHIFT = -0.1


def _likert(value: float) -> int:
    """连续倾向 → 1–5 的整数答题。

    用 ``floor(x + 0.5)`` 而不是内建 ``round``：后者是银行家舍入（``round(2.5) == 2``、
    ``round(3.5) == 4``），在李克特这种小整数域上会造成可察觉的偶数偏好——2 分与 4 分
    被系统性地多选中，而 1/3/5 少选中，直方图上会出现锯齿。四舍五入到最近的整数、
    平局一律进位，就不存在这种偏好。
    """
    clipped = min(max(value, float(LIKERT_MIN)), float(LIKERT_MAX))
    return int(min(max(math.floor(clipped + 0.5), LIKERT_MIN), LIKERT_MAX))


def make_survey(
    population: list[dict],
    latents: dict[int, dict[str, float]],
    cfg: SeedConfig,
    rng: np.random.Generator,
) -> list[dict]:
    """生成两学年各一份的兴趣问卷（每人 2 份）。

    键为 ``student_id`` / ``student_no`` / ``filled_on`` / ``total`` / ``dimensions`` /
    ``raw_answers``，其中后四列即 :data:`app.adapters.base.SURVEY_COLUMNS` 的契约列。

    ``dimensions`` 的五个维度分**由 ``raw_answers`` 的十道单题算出来**（每维度两题取
    均值），而不是独立抽两次：两者独立会让「维度分 4 分、底下两题一个 2 一个 5」这种
    自相矛盾的记录出现，而 ``raw_answers`` 是原样入库的，矛盾会一路留到分析阶段。
    ``total`` 是五个维度分之和，与 ``tests/fixtures/lepao_sample/survey.csv`` 的口径一致。

    填写日取该学期 ``week1`` 的采集日：问卷与首次体测同期发放。
    """
    total_people = len(population)
    latent_of = np.array([latents[p["student_id"]]["fitness"] for p in population])
    residual_sd = math.sqrt(1.0 - LIKERT_LATENT_WEIGHT**2)
    # 每名学生的答题倾向投影量 z 只抽一次，两学年共用：兴趣是相对稳定的特质，
    # 两次发放之间只有小幅漂移（SEMESTER_NOISE_SD），不该是完全无关的两次抽样。
    tendency = LIKERT_LATENT_WEIGHT * latent_of + rng.normal(
        0.0, residual_sd, total_people
    )

    records: list[dict] = []
    for plan in SEMESTERS:
        filled_on = timepoint_date(plan, "week1").isoformat()
        year_shift = 0.0 if plan.is_current else PREVIOUS_YEAR_SURVEY_SHIFT
        for index, person in enumerate(population):
            mean = min(
                max(
                    SURVEY_MEAN
                    + SURVEY_SLOPE * float(tendency[index])
                    + year_shift
                    + float(rng.normal(0.0, SEMESTER_NOISE_SD)),
                    float(LIKERT_MIN),
                ),
                float(LIKERT_MAX),
            )
            answers = {
                f"q{number:02d}": _likert(mean + float(rng.normal(0.0, ITEM_NOISE_SD)))
                for number in range(1, QUESTION_COUNT + 1)
            }
            dimensions = {
                dimension: sum(
                    answers[f"q{slot:02d}"]
                    for slot in range(
                        position * QUESTIONS_PER_DIMENSION + 1,
                        (position + 1) * QUESTIONS_PER_DIMENSION + 1,
                    )
                )
                / QUESTIONS_PER_DIMENSION
                for position, dimension in enumerate(DIMENSIONS)
            }
            records.append(
                {
                    "student_id": person["student_id"],
                    "student_no": person["student_no"],
                    "filled_on": filled_on,
                    "total": float(sum(dimensions.values())),
                    "dimensions": {name: float(score) for name, score in dimensions.items()},
                    "raw_answers": answers,
                }
            )
    return records

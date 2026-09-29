"""人口学与人体测量基准的生成（spec §10.1）。

**唯一职责**：产出 ``students`` 名学生的身份与体格基准。不生成任何学期内数据
（体测、体成分、问卷都在各自的模块里），也不碰数据库。随机数一律来自调用方传入的
``rng``——本模块内**不得**出现第二个生成器，否则「同种子字节级一致」当场失效
（由 ``tests/seed/test_generate.py`` 的源码级守卫钉住）。

**年龄 → 年级的分界必须与国标一致**
:func:`app.domain.indicators.age_group_of` 以 19/20 岁为「大一、大二」与「大三、大四」
的分界。:data:`GRADE_BY_AGE` 用的是同一条线：18/19 岁 → 1/2 年级，20 岁及以上 → 3/4
年级。若这里另立一条线（比如按 20/21 分），生成的 ``grade`` 与评分时查表用的
``age_group`` 就会指向两个不同的年级组，而两者都合法、谁都不会报错——查出来的分数
静默地来自另一张表。所以年龄**先**生成、年级由年龄折算，而不是反过来「先定年级再
配年龄」：后者一旦给某个一年级学生配了 20 岁，矛盾就无声地留下了。

**身高与体重是「基准值」**
它们代表该生本学年 week1 的读数；每条体测记录在此基础上再叠一次测量噪声
（见 :mod:`app.seed.fitness`）。体重由 BMI 分布反推（``weight = BMI × 身高²``），
因为简报 Step 3 明确要求 BMI「由身高体重分布独立生成后正查评分表」——独立于潜变量，
且**绝不**用 ``raw_from_score`` 反查 BMI（它的档位序列非单调，反查会抛 ``ValueError``）。
"""
import datetime as dt

import numpy as np

from app.seed.config import BIRTH_REFERENCE_DATE, SeedConfig, allocate_quota

# 在校年龄与典型年级：18 大一、19 大二、20 大三、21/22 大四（含留级与延毕）
AGES: tuple[int, ...] = (18, 19, 20, 21, 22)
AGE_PROBABILITIES: tuple[float, ...] = (0.28, 0.27, 0.25, 0.17, 0.03)
GRADE_BY_AGE: dict[int, int] = {18: 1, 19: 2, 20: 3, 21: 4, 22: 4}

# 身高与 BMI 的性别分组基准（中国大学生常见量级）。取值区间刻意收在
# data/indicator_ranges.yaml 的合理区间**内部**：生成出来的干净数据不该被清洗层
# 当成异常值夹取，否则注入的 outlier 与「本来就越界」混在一起，Task 5 的交叉验证
# 就分不清哪一条是谁造成的。
HEIGHT_MEAN: dict[str, float] = {"male": 172.5, "female": 160.5}
HEIGHT_SD: dict[str, float] = {"male": 6.2, "female": 5.6}
BMI_MEAN: dict[str, float] = {"male": 21.8, "female": 20.6}
BMI_SD: dict[str, float] = {"male": 2.9, "female": 2.8}
# 夹取区间：身高 [152, 198] ⊂ [140, 220]，体重 [40, 140] ⊂ [35, 150]。
# 下界不是随手取的——最矮的身高乘上最低的 BMI 必须仍高于体重下限，
# 152 cm × BMI 16.5 = 38.1 kg，再叠上 ±0.9 kg 的测量噪声也不会掉到 35 以下。
HEIGHT_RANGE: tuple[float, float] = (152.0, 198.0)
WEIGHT_RANGE: tuple[float, float] = (40.0, 140.0)
BMI_RANGE: tuple[float, float] = (16.5, 34.0)

DEPARTMENTS: tuple[str, ...] = (
    "计算机学院",
    "经济学院",
    "外国语学院",
    "化学化工学院",
    "医学院",
    "法学院",
    "建筑与土木工程学院",
    "海洋与地球学院",
    "人文学院",
    "数学科学学院",
    "管理学院",
    "物理科学与技术学院",
)

SURNAMES: tuple[str, ...] = (
    "王", "李", "张", "刘", "陈", "杨", "黄", "赵", "吴", "周",
    "徐", "孙", "马", "朱", "胡", "郭", "林", "何", "高", "罗",
    "郑", "梁", "谢", "宋", "唐", "许", "韩", "冯", "邓", "曹",
    "曾", "彭",
)
GIVEN_NAMES_MALE: tuple[str, ...] = (
    "浩然", "子轩", "宇航", "俊杰", "思远", "泽宇", "嘉豪", "明轩", "博文", "昊天",
    "睿哲", "家豪", "志强", "建国", "文轩", "皓宇", "锦程", "亦凡", "书豪", "冠宇",
    "一帆", "子豪", "泽楷", "晨阳", "越", "磊", "帆", "楠", "骁", "翊",
)
GIVEN_NAMES_FEMALE: tuple[str, ...] = (
    "欣怡", "梓萱", "雨桐", "诗涵", "语嫣", "思彤", "芷若", "佳怡", "梦琪", "晓彤",
    "静怡", "雅雯", "慧敏", "书瑶", "可欣", "婉清", "若曦", "嘉懿", "沐辰", "沁园",
    "一帆", "子涵", "玥", "宁", "颖", "琳", "妍", "璇", "嫣", "翊",
)


def birth_date(age: int, span: float) -> dt.date:
    """把年龄折算成出生日期，参考日是 :data:`app.seed.config.BIRTH_REFERENCE_DATE`。

    在参考日恰好满 ``age`` 周岁的出生日，落在开区间 ``(参考日 − (age+1) 年,
    参考日 − age 年]`` 内；``span ∈ [0, 1)`` 在这个区间里等距取一天，于是同一年龄
    的人生日均匀散开，而不是全部挤在参考日的整年倍上（那会让 ``birth`` 列只有 5 个
    不同取值，一眼假）。

    参考日取当前学期的开学日（9 月 1 日），永远不会是 2 月 29 日，故
    ``date.replace(year=…)`` 不存在闰日溢出问题。
    """
    latest = BIRTH_REFERENCE_DATE.replace(year=BIRTH_REFERENCE_DATE.year - age)
    earliest = BIRTH_REFERENCE_DATE.replace(year=BIRTH_REFERENCE_DATE.year - age - 1)
    days = (latest - earliest).days
    return earliest + dt.timedelta(days=1 + int(span * days))


def make_population(cfg: SeedConfig, rng: np.random.Generator) -> list[dict]:
    """生成 ``cfg.students`` 名学生的人口学与体格基准。

    返回的每个 dict 含 ``student_id``（1 起的合成序号，供 ``enrollments`` 与三类学期
    数据引用）、``student_no``（学号，CSV 与数据库用的自然键）、``name`` / ``sex`` /
    ``age`` / ``birth`` / ``department`` / ``grade``，以及 ``height_cm`` / ``weight_kg``
    两个体格基准。

    **性别用精确配额 + 洗牌**，不用 ``rng.random() < male_ratio`` 逐个抽样：后者在
    500 人上的男女比带 ±2.2 个标准差（约 ±25 人）的波动，简报那条 ``< 0.05`` 的容差
    断言就会变成一个「换了种子可能翻车」的定时炸弹。配额 + 洗牌给出的是**恰好**
    ``round(500 × 0.55) = 275`` 名男生，比例精确到 0.55，且顺序仍然是随机的。

    随机数的消耗顺序（性别洗牌 → 年龄 → 院系 → 姓 → 名 → 生日位置 → 身高 → BMI）
    是这个函数契约的一部分：改动顺序会改变同一种子下的全部输出，因此任何调整都必须
    同时更新基准数据，而不是悄悄换一个「看起来一样」的数据集。
    """
    total = cfg.students
    sex_quota = allocate_quota(
        {"male": cfg.male_ratio, "female": 1.0 - cfg.male_ratio}, total
    )
    sexes = np.array(
        ["male"] * sex_quota["male"] + ["female"] * sex_quota["female"], dtype=object
    )
    rng.shuffle(sexes)
    ages = rng.choice(AGES, size=total, p=AGE_PROBABILITIES)
    department_index = rng.integers(0, len(DEPARTMENTS), total)
    surname_index = rng.integers(0, len(SURNAMES), total)
    male_given_index = rng.integers(0, len(GIVEN_NAMES_MALE), total)
    female_given_index = rng.integers(0, len(GIVEN_NAMES_FEMALE), total)
    birth_spans = rng.random(total)

    male_mask = sexes == "male"
    heights = np.where(
        male_mask,
        rng.normal(HEIGHT_MEAN["male"], HEIGHT_SD["male"], total),
        rng.normal(HEIGHT_MEAN["female"], HEIGHT_SD["female"], total),
    ).clip(*HEIGHT_RANGE)
    bmis = np.where(
        male_mask,
        rng.normal(BMI_MEAN["male"], BMI_SD["male"], total),
        rng.normal(BMI_MEAN["female"], BMI_SD["female"], total),
    ).clip(*BMI_RANGE)
    weights = (bmis * (heights / 100.0) ** 2).clip(*WEIGHT_RANGE)

    # 入学年 = 参考日所在年 − (年级 − 1)。sorted(set(...)) 而不是直接 set：
    # 集合的迭代顺序由哈希决定，本字典虽然只被查找、不被遍历，但「不依赖集合顺序」
    # 这件事应当写在代码里，而不是留给下一个改这段代码的人去重新论证一遍。
    enroll_year_of_grade = {
        grade: BIRTH_REFERENCE_DATE.year - (grade - 1)
        for grade in sorted(set(GRADE_BY_AGE.values()))
    }
    # 学号 = 入学年 + 院系码(2 位) + 该(入学年, 院系)内的序号(4 位)，共 10 位。
    # 序号按 (入学年, 院系) 分桶递增，故学号在整个人群里天然唯一，不必事后再查一遍重。
    sequence: dict[tuple[int, int], int] = {}
    people: list[dict] = []
    for index in range(total):
        sex = str(sexes[index])
        age = int(ages[index])
        grade = GRADE_BY_AGE[age]
        department_slot = int(department_index[index])
        enroll_year = enroll_year_of_grade[grade]
        bucket = (enroll_year, department_slot)
        sequence[bucket] = sequence.get(bucket, 0) + 1
        given = (
            GIVEN_NAMES_MALE[int(male_given_index[index])]
            if sex == "male"
            else GIVEN_NAMES_FEMALE[int(female_given_index[index])]
        )
        people.append(
            {
                "student_id": index + 1,
                "student_no": f"{enroll_year}{department_slot + 1:02d}{sequence[bucket]:04d}",
                "name": SURNAMES[int(surname_index[index])] + given,
                "sex": sex,
                "age": age,
                "birth": birth_date(age, float(birth_spans[index])).isoformat(),
                "department": DEPARTMENTS[department_slot],
                "grade": grade,
                "height_cm": round(float(heights[index]), 1),
                "weight_kg": round(float(weights[index]), 1),
            }
        )
    return people

"""两套编班（spec §10.3）：阶段一行政班 + 阶段二分层班。

同一批学生**全员**同时属于两套编班：阶段一在行政班内分层教学，阶段二跨班重编成
提升班 / 强化班 / 拓展班。演示时可切换，两套关系因此必须并存于同一学期，而不是
「先有行政班、后来被分层班替换掉」。

**行政班数是从 ``students`` 与 ``section_size`` 反推出来的，不是写死的 12。**
简报正文写「12 个行政班容纳全部 500 人，每班 30–38 人」，这三个数互斥：
``12 × 38 = 456 < 500``，装不下全员；而装得下 500 人的班数区间是
``ceil(500/38) = 14`` 到 ``floor(500/30) = 16``。既然「全员编入」与「每班 30–38 人」
是两条要被测试钉住的性质，而 12 只出现在正文与一条断言里，就改班数、不改那两条性质。
缺省配置下算出 14 个班，规模 35/36 人。

**``teachers × sections_per_teacher`` 是班数的下限，不是班数本身。**
``course_section.teacher_id`` 非空，所以每个行政班都得有一名教师；简报那句「3 × 2 = 6
个由任课教师带」在本原型里落成「6 是行政班数的下限」——只有当这个下限比
``ceil(students / 上限)`` 更大时才起作用，否则教师会轮流带多个班。
"""
import math

import numpy as np

from app.seed.config import SeedConfig

# 阶段二的三个分层班名（spec §10.3）。顺序即体能从低到高：
# 提升班收 latent_fitness 最低的三分之一，拓展班收最高的三分之一。
STRATIFIED_NAMES: tuple[str, ...] = ("提升班", "强化班", "拓展班")
STRATIFIED_SCHEDULE = "分层走班（阶段二）"

TEACHER_NAMES: tuple[str, ...] = (
    "陈国华", "林慧敏", "赵志刚", "孙雅琴", "周文斌",
    "吴海燕", "郑立群", "黄思远",
)

# 上课时间的固定组合：周次 × 节次。由班序号推算而不是抽随机数——排课表本身没有
# 研究含义，用随机数只会白白消耗随机序列、把后面所有数据的取值推走。
_WEEKDAYS: tuple[str, ...] = ("周一", "周二", "周三", "周四", "周五")
_PERIOD_PAIRS: tuple[str, ...] = ("1-2", "3-4", "5-6", "7-8", "9-10")


def make_teachers(cfg: SeedConfig) -> list[dict]:
    """教师名册。是 ``cfg`` 的纯函数（不消耗随机数），故 :func:`make_sections` 与
    :func:`app.seed.generate.seed_database` 各自调用它时一定得到同一份工号——
    ``course_sections`` 里存的是 ``teacher_staff_no``，入库时按工号回查 id。
    """
    return [
        {"staff_no": f"T{index + 1:04d}", "name": TEACHER_NAMES[index % len(TEACHER_NAMES)]}
        for index in range(cfg.teachers)
    ]


def administrative_section_count(students: int, cfg: SeedConfig) -> int:
    """容纳 ``students`` 人所需的行政班数。

    取「装得下所有人的最少班数」``ceil(n / 上限)``；只有当把人数摊到
    ``teachers × sections_per_teacher`` 个班上仍不低于下限时，才把班数抬到这个下限。
    反过来的方向（为了凑够教师带班数而让每班人数掉到下限以下）是**不做**的：
    小规模人群（如测试里的 40 人）本来就凑不出 30–38 人的班，硬抬班数只会得到
    20 人的班外加更多的空班。
    """
    low, high = cfg.section_size
    count = max(1, math.ceil(students / high))
    teacher_floor = max(1, cfg.teachers * cfg.sections_per_teacher)
    if students // teacher_floor >= low:
        count = max(count, teacher_floor)
    return count


def make_sections(
    population: list[dict],
    cfg: SeedConfig,
    rng: np.random.Generator,
    latents: dict[int, dict[str, float]],
) -> dict[str, list[dict]]:
    """生成两套编班，返回 ``{"course_sections": […], "enrollments": […]}``。

    ``course_sections`` 的每项含 ``section_id``（合成键，供 ``enrollments`` 引用）、
    ``name``、``grouping_mode``、``teacher_staff_no``、``schedule_text``；
    ``enrollments`` 的每项含 ``student_id`` 与 ``section_id``。两套编班各贡献
    ``len(population)`` 条选课关系，故总数是人数的两倍。

    **第四个参数 ``latents`` 是必需的**，简报的接口清单只写了三个参数，但 Step 5 要求
    阶段二「按 ``latent_fitness`` 三分位近似分配」——不给它一个「按学号顺序三等分」的
    缺省值，是因为那种退化分配不报错，只会静默产出与体能毫无关系的分层班，而这三个班
    正是阶段二演示的全部内容。

    行政班的成员用 ``rng.permutation`` 打散后连续切片，所以每个班的性别、年龄、院系
    构成都接近总体，班与班之间的体能差异只来自抽样、不来自「前面的人恰好都弱」。
    """
    teachers = make_teachers(cfg)
    course_sections: list[dict] = []
    enrollments: list[dict] = []

    order = rng.permutation(len(population))
    admin_count = administrative_section_count(len(population), cfg)
    base_size, extra = divmod(len(population), admin_count)
    cursor = 0
    for index in range(admin_count):
        size = base_size + (1 if index < extra else 0)
        section_id = f"adm-{index + 1:02d}"
        course_sections.append(
            {
                "section_id": section_id,
                "name": f"行政班{index + 1:02d}",
                "grouping_mode": "administrative",
                "teacher_staff_no": teachers[index % len(teachers)]["staff_no"],
                "schedule_text": f"{_WEEKDAYS[index % len(_WEEKDAYS)]} "
                f"{_PERIOD_PAIRS[(index // len(_WEEKDAYS)) % len(_PERIOD_PAIRS)]} 节",
            }
        )
        for slot in range(size):
            person = population[int(order[cursor + slot])]
            enrollments.append(
                {"student_id": person["student_id"], "section_id": section_id}
            )
        cursor += size

    # 阶段二：按 latent_fitness 升序三等分。排序键带上 student_id 作稳定的次序决胜，
    # 于是即便两个人的潜变量恰好相等，分班结果也只取决于配置而不取决于排序算法的实现。
    ranked = sorted(
        population,
        key=lambda p: (latents[p["student_id"]]["fitness"], p["student_id"]),
    )
    first = len(ranked) // 3
    second = 2 * len(ranked) // 3
    terciles = (ranked[:first], ranked[first:second], ranked[second:])
    for index, (name, group) in enumerate(zip(STRATIFIED_NAMES, terciles)):
        section_id = f"str-{index + 1}"
        course_sections.append(
            {
                "section_id": section_id,
                "name": name,
                "grouping_mode": "stratified",
                "teacher_staff_no": teachers[index % len(teachers)]["staff_no"],
                "schedule_text": STRATIFIED_SCHEDULE,
            }
        )
        enrollments.extend(
            {"student_id": person["student_id"], "section_id": section_id} for person in group
        )

    return {"course_sections": course_sections, "enrollments": enrollments}

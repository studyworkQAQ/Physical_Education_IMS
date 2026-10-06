"""国标 2014 的指标定义、能力桶映射，以及评分表的正查/反查纯函数。

本模块是纯计算叶子：不碰磁盘、不碰数据库、不碰网络，也不自己取当前时刻——
时间与随机数一律由调用方注入，评分表一律由调用方（app/refdata.py 加载）作为
首参传入（Ruling 15）。只有这样，spec §1.3「逐人可追溯」与 §12「黄金用例」
才站得住：同一张表、同一个输入，永远得到同一个输出。
"""
from enum import Enum

from app.domain.tables import StandardTable


class Sex(str, Enum):
    """国标按性别分列评分表；引体向上（男）与一分钟仰卧起坐（女）也靠它区分。"""

    MALE = "male"
    FEMALE = "female"


class ScoredItem(str, Enum):
    """大学组的 7 个计分项，对应国标「单项指标与权重」表的全部行。"""

    BMI = "bmi"
    VITAL_CAPACITY = "vital_capacity"
    SPRINT_50M = "sprint_50m"
    SIT_AND_REACH = "sit_and_reach"
    STANDING_JUMP = "standing_jump"
    PULL_UP_OR_SIT_UP = "pull_up_or_sit_up"
    DISTANCE_RUN = "distance_run"


# 短板判定只看这 6 项。BMI 被排除：它是身体形态指标而不是可训练的能力短板，
# 且其官方评分是「区间 → 得分」的映射，与能力项不同构，混进桶化短板逻辑会失真。
WEAKNESS_ITEMS: tuple[ScoredItem, ...] = (
    ScoredItem.VITAL_CAPACITY,
    ScoredItem.SPRINT_50M,
    ScoredItem.SIT_AND_REACH,
    ScoredItem.STANDING_JUMP,
    ScoredItem.PULL_UP_OR_SIT_UP,
    ScoredItem.DISTANCE_RUN,
)

# 能力桶：处方引擎按桶聚合短板后给运动处方，BMI 不归桶
ITEM_BUCKET: dict[ScoredItem, str | None] = {
    ScoredItem.BMI: None,
    ScoredItem.VITAL_CAPACITY: "endurance",
    ScoredItem.DISTANCE_RUN: "endurance",
    ScoredItem.PULL_UP_OR_SIT_UP: "strength",
    ScoredItem.STANDING_JUMP: "strength",
    ScoredItem.SPRINT_50M: "speed_flexibility",
    ScoredItem.SIT_AND_REACH: "speed_flexibility",
}

# 国标 2014「单项指标与权重」表（spec §4.2 逐行对应）。**全仓唯一的权重所有者**：
# 国标总分 = ``Σ w_i × score_i // 100``（0–100），Task 8 的 ``national_total``、Task 10 的
# 总分入库、Task 6 生成器的趋势定标一律读这一份，不得手抄第二张权重表（Ruling 63）。
# 和恰为 100，故 ``// 100`` 之后总分仍在 0–100 内、且七项全满分时正好 100。
ITEM_WEIGHTS: dict[ScoredItem, int] = {
    ScoredItem.BMI: 15,
    ScoredItem.VITAL_CAPACITY: 15,
    ScoredItem.SPRINT_50M: 20,
    ScoredItem.SIT_AND_REACH: 10,
    ScoredItem.STANDING_JUMP: 10,
    ScoredItem.PULL_UP_OR_SIT_UP: 10,
    ScoredItem.DISTANCE_RUN: 20,
}

# 计分项 → 中文项目名，取自 spec §4.2 计分项表的「计分项」列（Ruling 127）。
# **两项随性别变**：``PULL_UP_OR_SIT_UP`` 男「引体向上」/ 女「1 分钟仰卧起坐」，
# ``DISTANCE_RUN`` 男「1000 米跑」/ 女「800 米跑」；其余五项两性别同名——靠
# ``item.value`` 拼不出来，只能显式列出。
#
# 它是纯数据、无行为，住在 ``ScoredItem`` 的同一个模块里（Task 6 加 ``ITEM_WEIGHTS``
# 是同一先例）；**不放在 Task 9 的 ``stratify.py``**：Task 11 的前端与 API 同样要显示
# 项目名，放在 ``explain()`` 旁边会变成第二份口径。消费者是 ``stratify.explain()``
# （spec §9.2 的示例文案里「1000 米跑」「引体向上」都是中文名）。
ITEM_DISPLAY_NAMES: dict[ScoredItem, dict[Sex, str]] = {
    ScoredItem.BMI: {Sex.MALE: "BMI", Sex.FEMALE: "BMI"},
    ScoredItem.VITAL_CAPACITY: {Sex.MALE: "肺活量", Sex.FEMALE: "肺活量"},
    ScoredItem.SPRINT_50M: {Sex.MALE: "50 米跑", Sex.FEMALE: "50 米跑"},
    ScoredItem.SIT_AND_REACH: {Sex.MALE: "坐位体前屈", Sex.FEMALE: "坐位体前屈"},
    ScoredItem.STANDING_JUMP: {Sex.MALE: "立定跳远", Sex.FEMALE: "立定跳远"},
    ScoredItem.PULL_UP_OR_SIT_UP: {Sex.MALE: "引体向上", Sex.FEMALE: "1 分钟仰卧起坐"},
    ScoredItem.DISTANCE_RUN: {Sex.MALE: "1000 米跑", Sex.FEMALE: "800 米跑"},
}

# 计分项 → 原始测量列名。这张映射**无法从名字推导**（``pull_up_or_sit_up`` 对应的是
# ``strength_count``），只能显式写出；写错的后果是按契约列序取值时 KeyError，当场炸开，
# 不会静默产出一个缺列的文件。
#
# **只有 6 个短板判定项、没有 BMI**：BMI 是「8 项原始测量 → 7 个国标计分项」里由身高与
# 体重**合成**的那一项（spec §4.2），它没有自己的原始测量列，故不在本映射里；合成算式是
# 下面的 :func:`bmi_of`。
#
# **住址为什么在 domain 而不在 ``app/seed/fitness.py``**（Plan 02 Task 1，终审 C 组）：
# 它原先住在生成器里，于是生产层为了拿这一张词表必须 ``from app.seed.fitness import …``
# ——基线 ``e26347f`` 上 ``app/pipeline/run_stratify.py:48`` 就是这么写的，而 spec §3.3
# 的依赖方向是单向的、``app/seed`` 是开发期工具。domain 是叶子（谁都能依赖它），且它已经
# 拥有 ``ScoredItem`` 与 ``WEAKNESS_ITEMS``，键的类型与取值域都在这儿。
# **不放在 ``app/adapters/base.py``**（终审 B 的备选方案）：那会让 ``base.py`` 新增一句
# ``from app.domain.indicators import ScoredItem``，打破它现有「import 面只有 ``re`` /
# ``abc`` / ``collections.abc`` / ``dataclasses``」的性质——为一个词表给契约层引入跨层
# 依赖，代价比收益大。
COLUMN_BY_ITEM: dict[ScoredItem, str] = {
    ScoredItem.VITAL_CAPACITY: "vital_capacity_ml",
    ScoredItem.SPRINT_50M: "sprint_50m_s",
    ScoredItem.SIT_AND_REACH: "sit_and_reach_cm",
    ScoredItem.STANDING_JUMP: "standing_jump_cm",
    ScoredItem.PULL_UP_OR_SIT_UP: "strength_count",
    ScoredItem.DISTANCE_RUN: "distance_run_s",
}

# 记录级清洗条目（整条重复被去除）不对应任何单个字段名，用星号通配占位。
# ``cleaning_log.field`` 是 String(32) 且无 CHECK 约束，星号能原样落库，并在审计界面里
# 一眼可辨「不是某一列的问题」。
#
# **住址在 domain 的理由与 :data:`CLEANING_FIELDS` 是同一个**：它是那一列取值域的成员，
# 而取值域只能有一个所有者（Plan01 Ruling 156）。它原先住在 ``app/pipeline/clean.py``，
# 本模块定义 ``CLEANING_FIELDS`` 时若不去引用它、而是自己再写一个字面量 ``"*"``，
# 就等于把同一个魔法值分成两个所有者——改一处漏一处，而漏掉的那一处**不会报错**，
# 只会让审计记录里同时出现两种「整条记录」的写法。``clean.py`` 现在从本模块重导出它，
# 故 ``from app.pipeline.clean import WHOLE_RECORD`` 与
# ``app.seed.generate`` 的那句导入都照旧可用，一个字都没改。
WHOLE_RECORD = "*"

# ``cleaning_log.field`` 的取值域，即那一列的**唯一所有者**（Plan01 Ruling 156 的落点，
# Plan 02 Task 1 兑现）。消费者是 ``tests/db/test_models.py`` 的列宽遍历测试：该列是
# ``String(32)`` 且没有 CHECK 约束，故此前**没有任何东西**保证 32 装得下最长的字段名——
# 换任何严格长度的后端（MySQL / PostgreSQL）会静默截断，与 Ruling 144 的
# ``derived_metrics.trend String(16)`` 是同一个缺陷形态。
#
# **13 个值的构成**（全量口径来自生产侧的**全部**写入点，命令::
#
#     git grep -n "field=" -- backend/app/pipeline/clean.py backend/app/pipeline/daily.py
#
# 基线 ``e26347f``，共 9 处写入点）：
#
# * 6 个 = :data:`COLUMN_BY_ITEM` 的值（``clean_fitness`` 逐字段处置时写 ``field=name``）；
# * 2 个 = ``height_cm`` / ``weight_kg``——**它们不在 ``COLUMN_BY_ITEM`` 里**（那一列只覆盖
#   6 个短板判定项），但同样是 ``RawFitnessRecord`` 的测量列、同样逐字段过清洗，且
#   ``height_cm`` 还有 ``normalize_height`` 那条 ``unit_normalized`` 专属写入点
#   （``clean.py`` 的 ``field="height_cm"``）。**计划原文的公式漏了这两个**；
# * 3 个 = ``muscle_mass_kg`` / ``body_fat_pct`` / ``smi``，即 ``RawBodyCompRecord`` 的三个
#   测量列（``clean_body_comp`` 逐字段处置）。**计划原文的公式同样漏了这三个**；
# * 1 个 = ``student_no``（``clean._unattributable_entry`` 与 ``daily._log_unattributable``
#   两处都写它：学号为空或解析不到人时，缺的正是这一列）；
# * 1 个 = :data:`WHOLE_RECORD`（两处 ``duplicate_removed``）。
#
# 计划原文写的是「``COLUMN_BY_ITEM`` 的值 ∪ ``{"student_no"}`` ∪ ``WHOLE_RECORD``」= 8 个，
# 少了上面那 5 个测量列——照它写的话列宽守卫会有 5 个字段名裸奔，而 ``vital_capacity_ml``
# （17 字符）恰好**在**那 8 个里，所以守卫看上去是有效的。漂移测试
# ``tests/pipeline/test_clean.py::test_cleaning_fields_cover_every_produced_field``
# 把本集合与生产侧**推导出来的**那一份对齐（两侧不同源，硬规矩 #35）。
CLEANING_FIELDS: frozenset[str] = frozenset(COLUMN_BY_ITEM.values()) | {
    "height_cm",
    "weight_kg",
    "muscle_mass_kg",
    "body_fat_pct",
    "smi",
    "student_no",
    WHOLE_RECORD,
}

# 国标 2014「说明」第 4 条：小学、初中、高中按每个年级为一组，
# 「大学一、二年级为一组，三、四年级为一组」。大学这里官方是按年级组划分、
# 没有年龄段，所以 AGE_GROUPS 直接用官方的两个年级组名，不另造年龄带。
AGE_GROUPS: tuple[str, ...] = ("大一、大二", "大三、大四")

# 典型在校年龄：大一 18、大二 19、大三 20、大四 21，故以 19/20 岁为两组分界
_LOWER_GRADE_MAX_AGE = 19


def age_group_of(age: int) -> str:
    """把年龄折算成国标 2014 的大学年级组。

    国标按年级而非年龄分组，这里按典型入学年龄折算：不超过 19 岁归
    ``大一、大二``，20 岁及以上归 ``大三、大四``；超出常见在校年龄（18–22 岁）
    的输入会自然落到端点组，不会产出评分表里不存在的键。
    """
    return AGE_GROUPS[0] if age <= _LOWER_GRADE_MAX_AGE else AGE_GROUPS[1]


def bmi_of(height_cm: float | None, weight_kg: float | None) -> float | None:
    """身高体重 → BMI（kg/m²），保留 1 位小数。

    **它是身高与体重的纯函数**，没有任何 I/O、时钟或数据库依赖，故住在 domain。
    原先它住在 ``app/pipeline/run_stratify.py``（Plan 02 Task 1 迁走）——一个纯函数住在
    管道层，意味着 domain 里的任何判定都拿不到它，而 spec §7.4 的安全后置规则要用
    「BMI > 30」这个**原始值**（不是国标得分），Plan 02 的 ``StudentProfile.bmi`` 因此
    必须由 domain 自己算得出来。``run_stratify`` 现在从本模块重导出它，
    ``run_stratify.bmi_of`` 与 ``run_stratify.__all__`` 里的 ``"bmi_of"`` 都照旧可用。

    ``round(..., 1)`` 是承重的：国标 BMI 档位是**区间映射**（两头 80、中间 100），而
    生成器 ``app.seed.fitness._anthropometrics`` 也算到 1 位小数，两侧差 0.05 就可能在
    档位边界上翻档——进而翻 ``score_bmi``、翻那 15% 权重的总分贡献。
    ⚠️ **生成器并没有调用本函数**：``app/seed/`` 自 Plan 01 结案后重新冻结，Plan 02
    Task 1 对它的改动只允许是「import 与被删常量」（Plan02 Ruling 2/15），把
    ``_anthropometrics`` 里的算式换成一次 ``bmi_of(...)`` 调用属于**逻辑行**改动，故没做。
    「两侧逐字一致」因此仍由**独立复算**钉住，而不是由共用一个函数保证：
    ``tests/domain/test_derive.py`` 的 oracle 自己写了一遍
    ``round(weight / (height / 100.0) ** 2, 1)``（刻意不复用本函数，硬规矩 #35 两侧不同源）。

    任一为 ``None``（缺测）时返回 ``None``——**绝不当 0**（Plan01 Ruling 21）：
    BMI = 0 kg/m² 会被 :func:`score_item` 的低侧夹取拿到 **80** 分（实测四个
    (性别 × 年级组) 组全部 80，因为 BMI 档位的最低哨兵 ``raw_value`` 就是 ``0``，
    而它对应的官方档是 80。命令：在 ``backend/`` 下跑 ``python`` 交互环境，
    ``from app.domain.indicators import *`` + ``from app.refdata import standard``，
    对 ``Sex`` × ``AGE_GROUPS`` 四组逐个求 ``score_item(standard(), ScoredItem.BMI,
    0.0, sex, group)``，四次都返回 80），一个缺测于是变成「BMI 低到不存在、
    却仍拿 80 分与 15% 权重」。
    """
    if height_cm is None or weight_kg is None:
        return None
    return round(weight_kg / (height_cm / 100.0) ** 2, 1)


def _segments_of(
    table: StandardTable, item: ScoredItem, sex: Sex, age_group: str
) -> tuple[tuple[float, int], ...] | None:
    return table.segments.get((item.value, sex.value, age_group))


def _lower_is_better(segments: tuple[tuple[float, int], ...]) -> bool:
    """该项是否「越小越好」——沿 raw_value 升序看得分是否全程单调不增。

    方向从表推断，不按项硬编码。对沿 raw 单调的表（除 BMI 外全部 **24** 组——7 项 ×
    2 性别 × 2 年级组 = 28 组、28 组在 CSV 里全都有、BMI 占其中 4 组，故单调的是 24 组；
    fix round 3 逐组复算，本处此前印的「26 组」多了 2，硬规矩 #26。**不被守卫**：没有测试
    数这个组数，被守的是方向推断本身——``tests/domain/test_indicators.py`` 逐项断言
    就低取档的方向与越界夹取），
    这与「首档得分 < 末档得分则为越大越好」完全等价；BMI 是非单调的区间映射
    （两头 80、中间 100），不满足单调不增，故落入「越大越好」分支——那正是它的
    CSV 落法所要求的口径：每个官方闭区间端点起（含）到下一端点前取该端点的分。
    """
    scores = [score for _, score in segments]
    return all(nxt <= cur for cur, nxt in zip(scores, scores[1:]))


def score_item(
    table: StandardTable,
    item: ScoredItem,
    value: float | None,
    sex: Sex,
    age_group: str,
) -> int | None:
    """正查：原始成绩 → 国标单项得分。

    **就低取档的阶梯查表，不做插值**（Ruling 18）。国标评分表是离散阈值表，官方
    口径是「落在哪一档就拿哪一档的分」：越大越好取**最大的 ``raw_i <= value``**，
    越小越好取**最小的 ``raw_i >= value``**。插值会产出 56/61/92 这类国标里根本不
    存在的分数（实测**男生 ×「大一、大二」**组、线性插值：立定跳远 210 cm 给 61 分、
    :func:`score_item` 给 60 分；1000 米 280 秒给 56 分、:func:`score_item` 给 50 分。
    **这两个数随年级组变**：同一算式在「大三、大四」组给 60 / 55，故引用它们必须带上
    组名与性别。守卫在 ``tests/domain/test_indicators.py`` 的
    ``test_score_item_only_returns_official_discrete_scores``——它把 ``G = age_group_of(19)``
    即「大一、大二」这一组的全部 7 项 × 2 性别 × 203 个扫描点逐个断言 ``in official``，
    一旦改回插值当场红；**插值那两个数本身不被守卫**，它是旧实现的取证），
    使系统单项分与学校官方体测报表无法逐格对账，
    而 spec §12 黄金用例与 §1.3 可追溯性正是要拿真实报表校验的。阶梯查表无插值
    即无舍入，``round()`` 的银行家舍入偏差也随之消失。

    **越界一律夹到所落那一端的档位分，绝不返回 ``None``**（Ruling 17）。
    ``segments`` 按原始值升序，所以「优于表内最好档」与「差于表内最差档」都由同一句
    夹取自动落到正确端点：哪一端是高分由表自身的单调性决定。国标本来就是这么给分的：
    低于最低档的成绩拿最低档的分，而不算「没有成绩」。

    ``None`` 只保留给两种**真缺测**情形：``value`` 缺失，或表里没有这个
    (项, 性别, 年级组) 组合。任何路径都不抛异常、也不返回 0。

    把差到表外的真实成绩判成 ``None`` 是会静默反转研究结论的缺陷：``None`` 在下游
    一律等于「没测」，既拉低 ``valid_count``（有效项不足 4 个直接不分层），又让该项
    不计入短板数 ``W``——体能最差的学生因此被系统性地筛出红色干预层，全程不报错。

    **前置条件：``value`` 必须已经是清洗过的值**（Ruling 21）。本函数对越界只做夹取，
    不判断读数是否物理可能，因此调用方必须先把物理上不可能的读数转成 ``None`` 再传入：
    高侧如 50 米跑 999 秒（夹到底档 10 分，压分），低侧如 50 米跑 0.0 秒——
    ``0`` 是数值列最常见的缺测占位，而低侧夹取对「越小越好」的项意味着**低值得高分**，
    实测 50 米跑与耐力跑的 0.0 秒都返回 **100 分**：一个缺测项会给体能最差的学生送上
    20% 权重的满分，还同时抹掉两个桶的短板。这比高侧更危险，因为它抬分而非压分。
    处置不能放在这里一刀切拒绝 ``<= 0``（引体向上 0 次、坐位体前屈 −1.3 cm 都是合法
    真实值），必须由 Task 5 的清洗层按 ``indicator_ranges.yaml`` 的逐字段
    ``non_positive_is_missing`` 标记完成。
    """
    if value is None:
        return None
    segments = _segments_of(table, item, sex, age_group)
    if not segments:
        return None
    low_raw, low_score = segments[0]
    high_raw, high_score = segments[-1]
    if value < low_raw:
        return low_score
    if value > high_raw:
        return high_score
    # 上面两次夹取已保证 low_raw <= value <= high_raw，故下面两个生成式必然非空
    if _lower_is_better(segments):
        return next(score for raw, score in segments if raw >= value)
    return next(score for raw, score in reversed(segments) if raw <= value)


def raw_from_score(
    table: StandardTable, item: ScoredItem, score: int, sex: Sex, age_group: str
) -> float:
    """反查：目标单项得分 → 原始成绩，供仿真数据生成按目标分数造出可信的实测值。

    用的是与 :func:`score_item` 同一张表、同一套档位，口径同样是**就低取档**：
    请求分不一定是官方档（Task 6 会算出 73 这类连续目标分），此时先把它落到
    **不超过请求分的最大官方档**（73 → 72、71 → 70）。请求分高于表内最高档时落到
    最高档、低于最低档时落到最低档，即夹到端点档。

    返回值是**方向感知的档位端点，也就是「仍然拿到该分的最差成绩」**（Ruling 22）：
    越大越好取该档原始值区间的**下界**，越小越好取**上界**。两端与 :func:`score_item`
    的就低口径是同一件事——差一点点就掉档，再好也只是同一档。由此得到**精确往返**：

        ``score_item(table, item, raw_from_score(table, item, s, sex, ag), sex, ag) == s``

    对每一个官方档 ``s`` 恒成立（全表 24 个单调组 × 每组全部官方档已逐一验证）。
    往返精确意味着 Task 6 拿到什么就存什么，不必再猜该往哪边取整。

    端点语义还带来一个额外好处：**次数项天然是整数**。引体向上／仰卧起坐在国标里的
    档边界本身就是整数次，故反查结果一定是 ``13.0`` 这类可测量的读数；调用方不必再
    自己取整——取整方向是方向相关的知识（越大越好只能向下、越小越好只能向上），
    不该泄漏到每个调用点。

    **非单调的项直接抛 ``ValueError``**：只有 BMI 是这样（两头 80、中间 100）。
    它的档位序列里同一个分对应两段互不相邻的原始值区间，「反查唯一原始值」这个问题
    本身不成立；照旧返回会泄漏 CSV 用来封口开区间的哨兵值——**改前**实测
    ``raw_from_score(table, BMI, 80, ...)`` 返回 ``0.0``，而 80 分恰是 BMI 最常见的
    目标分（低体重与超重都是 80），下游会因此造出 BMI = 0 kg/m² 的学生，且因为
    ``score_item(table, BMI, 0.0, ...) == 80`` 往返测试全绿，缺陷被完美掩盖。
    改成抛 ``ValueError`` 之后那个 ``0.0`` 已经**不可复现**（fix round 3 复跑确认现在
    一律 ``ValueError``），故它是历史实测、**不再可验证**；被守卫的是新行为——
    ``tests/domain/test_indicators.py`` 断言 BMI 反查抛 ``ValueError``。
    正确做法是直接生成身高与体重、算出 BMI 后用 :func:`score_item` 正查得分。

    表里没有这个 (项, 性别, 年级组) 组合时抛 ``KeyError``：那是调用方传错了组合，
    属于程序缺陷，与「学生某项缺测」不是一回事，不该被静默吞掉。
    """
    segments = table.segments[(item.value, sex.value, age_group)]
    scores = [segment[1] for segment in segments]
    non_decreasing = all(b >= a for a, b in zip(scores, scores[1:]))
    non_increasing = all(b <= a for a, b in zip(scores, scores[1:]))
    if not (non_decreasing or non_increasing):
        raise ValueError(
            f"{item.value} 的档位得分沿原始值非单调（区间型映射），同一得分对应多段"
            f"互不相邻的原始值区间，无法按目标分反查唯一原始值；请直接生成身高与体重、"
            f"算出该指标后用 score_item 正查得分"
        )
    # 就低：不超过请求分的最大官方档；请求分低于最低档时夹到最低档
    official = sorted(set(scores))
    target = max((s for s in official if s <= score), default=official[0])
    band = [raw for raw, s in segments if s == target]
    # 方向沿用 score_item 那套推断（_lower_is_better）：越小越好取带上界、
    # 越大越好取带下界，两者都是「仍拿到 target 分的最差原始值」。
    return float(max(band) if _lower_is_better(segments) else min(band))


def segment_thresholds(
    table: StandardTable, item: ScoredItem, sex: Sex, age_group: str
) -> list[float]:
    """该 (项, 性别, 年级组) 下全部档位的原始值阈值，升序。

    边界测试用它从评分表本身取真实档位，而不是硬编码魔数与 CSV 脱钩。

    表里没有这个组合时抛 ``KeyError``，与 :func:`raw_from_score` 保持一致：
    返回空列表会让调用方的 ``[0]`` / ``[-1]`` 退化成 ``IndexError``，
    把「传错了组合」这个明确原因藏进一个看不出所以然的下标错误里。
    """
    segments = table.segments[(item.value, sex.value, age_group)]
    return [float(raw) for raw, _ in segments]


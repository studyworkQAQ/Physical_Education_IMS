"""spec §7.5 的五种教师覆盖（Plan 02 Task 5 的 5.4）。

**覆盖不修改模板**（spec §7.5 原文）：:func:`apply_overrides` 只作用于
:class:`~app.domain.prescription.assembler.TrainingPackage`，且是**纯函数**——不改传入的包、
不改注入的动作库、不读盘、不读时钟（``applied_at`` 由调用方注入）。
守卫是 ``test_apply_overrides_does_not_mutate_the_template_or_the_package``。

**下次自动生成回到算法基线、不继承覆盖**（spec §7.5 原文）**不是本模块的职责**：那是 Task 6
的触发逻辑——生成时**不读**上一张处方的 override 记录。本模块甚至**看不见**历史记录
（它只收一个 ``records`` 序列），故这件事在结构上就不可能由本模块负责。集成测试归 Task 6。

--------------------------------------------------------------------------

**⚠️ 签名比简报多一个 keyword-only 形参 ``exercises``**（与 5.3 的
:func:`app.domain.prescription.safety.apply_safety` 同一条顶回）：``SUBSTITUTE_EXERCISE`` 要
换掉一个动作，而 :class:`~app.domain.prescription.assembler.AssembledBlock` 的
``exercise_name`` / ``video_url`` / ``impact_level`` 三个字段**只能从动作库取**
（P5-A8：读**源**，不读模板里的冗余副本）。简报给的 ``apply_overrides(pkg, records)``
拿不到它们，于是要么留着**旧动作**的名字与视频 URL（学生端点进去看到的是间歇跑的视频、
而处方上写着快走——一个看起来正常的谎），要么把三个字段留空。两者都不可接受。

--------------------------------------------------------------------------

**五种 ``kind`` 的取值约定**（``old_value`` / ``new_value`` 一律是 ``str``）

=========================  ==================  ==========================  ==========================
``kind``                    ``target``           ``new_value``                效果
=========================  ==================  ==========================  ==========================
``WEEKLY_FREQUENCY``       ``None``             周课次的整数字符串 ``"3"``    保留前 N 课 + 按 N/原课次重量
``SUBSTITUTE_EXERCISE``    原 ``exercise_ref``   新 ``exercise_ref``          换 ref + 名字 + URL + 冲击等级
``INTENSITY_STEP``         ref 或 ``None``       百分比点数增量 ``"-5"``      整体平移目标心率区间
``VOLUME_SCALE``           ref 或 ``None``       乘数字符串 ``"0.8"``         ``weekly_volume`` 乘它
``PAUSE``                  ``None``             任意（约定 ``"true"``）      ``paused = True``，``weeks`` 原样
=========================  ==================  ==========================  ==========================

**为什么 ``old_value`` / ``new_value`` 是 ``str`` 而不是各自类型的联合**：它们要落进
``prescription.teacher_overrides`` 这个 **JSON 列**，异构类型会让 JSON 结构不稳定
（同一列里一会儿是数字、一会儿是字符串、一会儿是布尔，读回来的人必须先判类型）。
统一成 ``str`` 之后，那一列的形状恒定，而**解析失败一律是响的**：``int("abc")`` 与
``float("abc")`` 都抛 ``ValueError``（Python 自己的消息就点出了那个坏字面量），
故本模块**不写 try/except** 去包装它们。

**``INTENSITY_STEP`` 的语义是「目标心率区间的百分比点数增量」**，位移量
``delta = int(step × hrmax / 100)``，``hrmax`` 从 ``assembly_snapshot["hrmax"]`` 读
——**不重新算**：快照里那个数才是这张处方当初用的值（可能是实测值而不是 Tanaka），
重算一次就是同一条规则的第二个住址（Global Constraint #3）。区间是**整体平移**
（宽度不变），故不需要重新做保守取整。

⚠️ **``hr_zone is None`` 的 block 原样不动**：``AssembledBlock`` **不保存**
:class:`~app.domain.prescription.templates.Intensity`，只保存渲染好的 ``intensity_text`` 与
``hr_zone``，故「70% 1RM」这个数在装配之后只剩文案里的字面量——改它就是改一句中文。
真仓 130 个 block 里 **106** 个是这一档（``none`` 82 + ``onerm_pct`` 24），于是
``INTENSITY_STEP`` 对它们**无事发生**，而 ``apply_overrides`` 只返回一个
``TrainingPackage``、**没有 warning 通道**能把这件事说出来。已作为关切报出。

--------------------------------------------------------------------------

**多条覆盖同一目标 → 由列表顺序决定，后者胜**（简报 5.4 的决定原文）。
**不用 ``applied_at``**：同一秒批量操作时它相等，而调用方持有真实顺序。
:attr:`OverrideRecord.applied_at` 因此是**纯载荷**（落库与审计用），本模块一个字都不读它。

⚠️ 各 ``kind`` 的「后者胜」含义不同，因为它们是**顺序应用**而不是「最后一条覆盖前面所有」：

* ``WEEKLY_FREQUENCY`` / ``SUBSTITUTE_EXERCISE`` / ``PAUSE`` 是**设状态**的，故最后一条
  决定终态（``4 → 3 → 2`` 得到 2 课）。
* ``VOLUME_SCALE`` / ``INTENSITY_STEP`` 是**增量**的，故它们**复合**（``"0.8"`` 再 ``"0.9"``
  得到 ``0.72`` 倍，不是 ``0.9`` 倍）。这不是 bug：教师先降 20% 再降 10% 的意图就是复合，
  而「后者胜」要的是**顺序由列表决定**这件事本身。
* ``WEEKLY_FREQUENCY`` 的量重算是**相对当前课次**的（``× N / len(当前 sessions)``），
  故 ``4 → 3 → 2`` 与 ``4 → 2`` 得到同一个 ``weekly_volume``（``24.0``）——复合不漂移。

--------------------------------------------------------------------------

⚠️ **本模块不 import ``datetime``**（与 :mod:`app.domain.prescription.intensity` 同一条纪律，
理由与代价逐字见那个模块 docstring 的第 5 段）：``applied_at`` 的标注是**前向引用字符串**
``"dt.datetime"``，运行时本模块**一个属性都不读它**（顺序由列表决定），故连 duck typing
都不需要。

⚠️ **本模块守不住什么**（硬规矩 #39）：

* **不守 ``teacher_staff_no`` 非空**：简报只要求 ``reason`` 非空，故一个空工号的覆盖记录
  能构造出来、没有任何一条测试会红。
* **不守 ``kind`` 是 ``OverrideKind`` 的成员**：``OverrideRecord`` 构造期只校验 ``reason``，
  一个 ``kind="teleport"`` 的记录**能构造出来**；:func:`apply_overrides` 用 ``is`` 逐个比对
  枚举成员，故它落到 ``else`` 那一支 ``ValueError``（**不静默忽略**——教师以为改过了、
  而处方一个字没变，那正是「静默跳过」在覆盖侧的形状）。守卫是
  ``test_an_unknown_override_kind_is_rejected``。
* **不守覆盖写进快照**：``assembly_snapshot`` 的键集是 ``assemble`` 的 **12** 个 +
  ``apply_safety`` 的 **3** 个（P5-A7 字面钉死），本模块**一个都不加**。覆盖记录由 Task 6
  落进 ``prescription.teacher_overrides`` 那一列——两份数据各有一个住址
  （Global Constraint #3）。代价：单看 ``assembly_snapshot`` **看不出**这张包被教师改过，
  只有 ``paused`` 与 ``intensity_text`` 里那句留痕是包内可见的痕迹。
"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum

from .assembler import TrainingPackage
from .exercises import ExerciseSpec


class OverrideKind(str, Enum):
    """spec §7.5 的五种教师覆盖。**声明序照 spec 的书写序**，一个都不能少。

    **继承 ``str``** 的理由与 :class:`~app.domain.prescription.templates.ReviewStatus` /
    :class:`~app.domain.prescription.match.MatchStatus` 相同：``prescription.teacher_overrides``
    那个 JSON 列里存的就是 ``kind.value``，继承 ``str`` 之后 ``OverrideKind.PAUSE == "pause"``
    直接成立，不必在 ORM 边界上处处写 ``.value``。

    ⚠️ **但 :func:`apply_overrides` 用 ``is`` 而不是 ``==`` 分派**：``OverrideKind.PAUSE ==
    "pause"`` 为真而 ``OverrideKind.PAUSE is "pause"`` 为假，故一个裸字符串 ``"pause"``
    **不会**被当成 ``PAUSE`` 处理，而是落到 ``ValueError`` 那一支。这是有意的：
    分派只认真枚举成员，于是一个从 JSON 读回来、忘了过 ``OverrideKind(...)`` 的记录
    会**当场响**，而不是被静默当成某一种覆盖执行。
    """

    WEEKLY_FREQUENCY = "weekly_frequency"
    SUBSTITUTE_EXERCISE = "substitute_exercise"
    INTENSITY_STEP = "intensity_step"
    VOLUME_SCALE = "volume_scale"
    PAUSE = "pause"


@dataclass(frozen=True)
class OverrideRecord:
    """一条教师覆盖记录。字段名与顺序照简报 Interfaces / Produces 逐字。

    ``target`` 是**周次或 ``exercise_ref``**（简报原文）。⚠️ 本模块的落地口径是
    **只按 ``exercise_ref`` 用它**：``WEEKLY_FREQUENCY`` 与 ``PAUSE`` 作用于整包（``None``），
    ``SUBSTITUTE_EXERCISE`` 必须给一个 ref（要打错就响），``INTENSITY_STEP`` 与
    ``VOLUME_SCALE`` 给 ref 或 ``None``（``None`` = 全部 block）。「周次」那一档今天
    **没有 kind 用它**——spec §7.5 的五种覆盖里没有「只改第 3 周」这一种，而按周微调是
    ``week_deltas`` 的活（Task 8 的读模型）。

    ``old_value`` **只作留痕**：本模块一个字都不读它（终态由 ``new_value`` 与当前包决定）。
    它的价值在教师端与审计：一条 ``old_value="4" / new_value="3"`` 的记录能回答
    「教师把周频次从几天改成了几天」，而只有 ``new_value`` 的记录答不出前半句。
    ⚠️ 于是**它与包的实际状态可能不符**（教师填错了 ``old_value``，或同一目标被覆盖了两次），
    而本模块**不校验**它——校验就等于要求调用方在生成记录之前先算一遍，那是两个住址。

    ``applied_at`` 由调用方注入（domain 不碰时钟），且**本模块不读它**（顺序由列表决定，
    见模块 docstring 第五节）。标注是前向引用字符串，因为 ``datetime`` 不在 domain 的
    allow-list 里。
    """

    kind: OverrideKind
    target: str | None
    old_value: str
    new_value: str
    reason: str
    teacher_staff_no: str
    applied_at: "dt.datetime"

    def __post_init__(self) -> None:
        """``reason`` 不得为空（全空格也算空）。

        理由：spec §7.5 末段说这些记录是**研究数据**（「学期末回答教师在哪些环节最不信任
        算法」），一条没有理由的覆盖对研究毫无价值。这与 Plan 01 给 ``WeaknessResult`` 加
        ``count == len(items)`` 不变量是同一个手法：**把「这条数据有没有意义」变成构造期的
        不变量**，而不是留给下游去猜。

        ⚠️ ``teacher_staff_no`` **刻意不在这里校验**（硬规矩 #39）：简报只点了 ``reason``，
        故一个空工号的记录能构造出来、没有任何一条测试会红。
        """
        if not self.reason.strip():
            raise ValueError(
                "OverrideRecord.reason 不得为空（全空格也算空）：spec §7.5 末段把这些记录"
                "当成研究数据（「学期末回答教师在哪些环节最不信任算法」），一条没有理由的"
                "覆盖对研究毫无价值，而事后补理由等于事后编理由"
            )


def _rebuild(pkg: TrainingPackage, transform, target: str | None) -> TrainingPackage:
    """把 ``transform`` 作用到 ``target`` 命中的**每一个** block（四周 × 每课），产出新包。

    ``target is None`` 表示**全部** block。命中 **0** 个 block 时抛 ``ValueError``：
    一个打错的 ``target``（``"interval_runn"``）会让覆盖**静默无事发生**，而教师以为自己
    已经改过了——那正是「静默跳过」在覆盖侧的形状（Review Focus 第 5 条的同一条纪律）。

    ⚠️ 它作用于**所有周的所有课**：``AssembledBlock`` 在 4 周 × 4 课里是 16 个**独立实例**
    （frozen dataclass，值相同但对象不同），只改第 1 周会让「教师改了一个动作」变成
    「教师只改了第一周的那个动作」，而 spec §7.5 的五种覆盖里没有任何一种带周次。
    """
    matched = 0
    weeks = []
    for week in pkg.weeks:
        sessions = []
        for session in week.sessions:
            blocks = []
            for block in session.blocks:
                if target is not None and block.exercise_ref != target:
                    blocks.append(block)
                else:
                    matched += 1
                    blocks.append(transform(block))
            sessions.append(replace(session, blocks=tuple(blocks)))
        weeks.append(replace(week, sessions=tuple(sessions)))
    if matched == 0:
        raise ValueError(
            f"{target!r} 在这张训练包里一个 block 都没命中（4 周 × 每课的 block 全查过），"
            f"覆盖没有生效。**不静默返回原包**：教师会以为自己已经改过了。"
            f"请核对 exercise_ref 是否拼错，或该动作是否本来就不在这套模板里"
        )
    return replace(pkg, weeks=tuple(weeks))


def _weekly_frequency(pkg: TrainingPackage, record: OverrideRecord) -> TrainingPackage:
    """``WEEKLY_FREQUENCY``：每周保留前 N 课，并按 ``N / 原课次`` 重算量。

    ⚠️ **重算是承重的**：``weekly_volume`` 是**周量**（``base × sessions_per_week × 系数 ×
    delta``），砍掉一课而不改它，那个数就在**撒谎**——教师端会显示「48 分钟/周」而学生实际
    只做 3 课共 36 分钟。故 ``sessions_per_week`` 与 ``weekly_volume`` 一起改，
    于是 ``4 → 3 → 2`` 与 ``4 → 2`` 得到同一个量（复合不漂移，见模块 docstring 第五节）。

    ``N > 该周的课数`` 与 ``N < 1`` 都拒绝、**不夹取**：模板只有 4 课，算法**造不出**第 5 课
    （那等于代码替专家写模板）；``0`` 课与 ``PAUSE`` 是两件事（``PAUSE`` 保留 ``weeks``、
    可撤销，``0`` 课是一份空训练包）。
    """
    wanted = int(record.new_value)
    weeks = []
    for week in pkg.weeks:
        available = len(week.sessions)
        if wanted < 1 or wanted > available:
            raise ValueError(
                f"WEEKLY_FREQUENCY 的 new_value 是 {wanted}，而这张训练包每周有 "
                f"{available} 课：合法区间是 [1, {available}]。**不夹取**——"
                f"{available + 1} 课要算法自己造一课（等于代码替专家写模板），"
                f"0 课是一份空训练包，而「暂停」请用 OverrideKind.PAUSE"
                f"（它保留 weeks、可撤销）"
            )
        factor = wanted / available
        sessions = tuple(
            replace(
                session,
                blocks=tuple(
                    replace(
                        block,
                        weekly_volume=round(block.weekly_volume * factor, 1),
                        sessions_per_week=wanted,
                    )
                    for block in session.blocks
                ),
            )
            for session in week.sessions[:wanted]
        )
        weeks.append(replace(week, sessions=sessions))
    return replace(pkg, weeks=tuple(weeks))


def _substitute(
    pkg: TrainingPackage, record: OverrideRecord,
    exercises: Mapping[str, ExerciseSpec],
) -> TrainingPackage:
    """``SUBSTITUTE_EXERCISE``：四个字段一起换，替身的值取自**动作库**。

    ⚠️ 只换 ``exercise_ref`` 而留着旧动作的名字与视频 URL 是一个**看起来正常的谎**
    （学生端点进去看到的是间歇跑的视频、而处方上写着快走），故 ``exercise_ref`` /
    ``exercise_name`` / ``video_url`` / ``impact_level`` 四个一起换。
    **剂量原样继承**（强度文案 / 心率区间 / ``structure`` / ``weekly_volume`` / 单位 /
    周课次）——与 5.3 的等价替换同一语义：换掉的是动作，不是训练刺激。

    ⚠️ 与 5.3 不同，这里**不查等价表**：教师覆盖的优先级高于安全规则（spec §7.4 与 §7.5
    都写了「优先级」，而 §7.5 的教师是最后一手），故教师可以把一个 high 冲击动作换成
    另一个 high 冲击动作，本模块不拦。**拦它的地方是教师端 UI 与审校流程**，不是 domain。
    """
    spec = exercises.get(record.new_value)
    if spec is None:
        raise ValueError(
            f"SUBSTITUTE_EXERCISE 的 new_value {record.new_value!r} 不在动作库里"
            f"（{len(exercises)} 个键里没有它）。**不静默忽略**：学生端会拿到一个查不到的"
            f"动作（没有名字、没有视频 URL），而处方看起来是改过了"
        )
    return _rebuild(
        pkg,
        lambda block: replace(
            block,
            exercise_ref=spec.ref,
            exercise_name=spec.name,
            video_url=spec.video_url,
            impact_level=spec.impact_level,
        ),
        record.target,
    )


def _intensity_step(pkg: TrainingPackage, record: OverrideRecord) -> TrainingPackage:
    """``INTENSITY_STEP``：把目标心率区间**整体平移** ``step`` 个 HRmax 百分点。

    ``delta = int(step × hrmax / 100)``，``hrmax`` 读 ``assembly_snapshot["hrmax"]``
    （**不重新算**，理由见模块 docstring 第四节）。``int()`` 是**向零截断**：
    ``step = -5``、``hrmax = 194.0`` → ``int(-9.7) = -9``；``step = +5`` → ``int(9.7) = 9``。
    平移量是**整数 bpm**，故区间宽度不变、也不需要重新做保守取整。

    平移之后低界 ``<= 0`` → 拒绝、**不夹取**：一个 0 bpm 的目标心率区间是荒谬值，而它
    **看起来完全正常**（两个整数、低界小于高界）。口径照
    :func:`app.domain.prescription.intensity.hr_zone` 对 ``hrmax_bpm <= 0`` 的拒绝
    （Review Focus 第 4 条：静默产出荒谬值比崩溃危险）。

    ``hr_zone is None`` 的 block **原样不动**（``onerm_pct`` / ``rpe`` / ``none`` 三档，
    真仓 106/130），理由与本模块守不住什么，见模块 docstring 第四节。
    ``intensity_text`` 后面追加一句留痕：模板的原文案（教师的意图冲突时它是证据）与
    覆盖后的 bpm 都在。
    """
    step = int(record.new_value)
    max_hr = pkg.assembly_snapshot["hrmax"]
    delta = int(step * max_hr / 100.0)

    def transform(block):
        if block.hr_zone is None:
            return block
        low = block.hr_zone[0] + delta
        high = block.hr_zone[1] + delta
        if low <= 0:
            raise ValueError(
                f"INTENSITY_STEP {step:+d} 个百分点（HRmax {max_hr} bpm → 平移 {delta} bpm）"
                f"会把目标心率区间的低界推到 {low} bpm。**不夹取**：一个 <= 0 的目标心率"
                f"是荒谬值，而它看起来完全正常（两个整数、低界小于高界）。"
                f"要暂停这张处方请用 OverrideKind.PAUSE"
            )
        return replace(
            block,
            hr_zone=(low, high),
            intensity_text=(
                f"{block.intensity_text}｜教师覆盖：强度 {step:+d} 个百分点，"
                f"目标心率 {low}–{high} bpm"
            ),
        )

    return _rebuild(pkg, transform, record.target)


def _volume_scale(pkg: TrainingPackage, record: OverrideRecord) -> TrainingPackage:
    """``VOLUME_SCALE``：``weekly_volume`` 乘一个正数（``< 1`` 降量、``> 1`` 加量）。

    ⚠️ **加量是合法的**（``> 1`` 不拒绝）：``exercise_equivalence.yaml`` 的
    ``volume_reduction`` 那两个系数被加载器限制在 ``(0.0, 1.0)`` 内（``> 1`` 是「安全触发
    反而加量」），而**教师覆盖不是安全触发**——一个恢复得快的学生可以被教师加量。
    故本模块只拒绝 ``<= 0``（``0`` 是把训练量清零、处方名存实亡；负数没有物理意义）。

    ``volume_unit`` / ``sessions_per_week`` / ``structure`` 都不动：「整体降量/加量」
    降的是**量**，不是频次、也不是组数结构（改频次是 ``WEEKLY_FREQUENCY`` 的活）。
    """
    factor = float(record.new_value)
    if not factor > 0.0:
        raise ValueError(
            f"VOLUME_SCALE 的 new_value 是 {factor}，应 > 0：0 是把训练量清零"
            f"（处方名存实亡），负数没有物理意义。要停用这张处方请用 OverrideKind.PAUSE"
            f"（它保留 weeks、可撤销）。**加量（> 1）是合法的**：教师覆盖不是安全触发，"
            f"与 exercise_equivalence.yaml 的 volume_reduction 限制在 (0.0, 1.0) 不同口径"
        )
    return _rebuild(
        pkg,
        lambda block: replace(
            block, weekly_volume=round(block.weekly_volume * factor, 1)
        ),
        record.target,
    )


def apply_overrides(
    pkg: TrainingPackage,
    records: Sequence[OverrideRecord],
    *,
    exercises: Mapping[str, ExerciseSpec],
) -> TrainingPackage:
    """按**列表顺序**逐条应用覆盖，产出一个新包（入参那个一个字不改）。

    ⚠️ ``exercises`` 是 keyword-only 的**新增**形参（理由见模块 docstring 第二节）。
    只有 ``SUBSTITUTE_EXERCISE`` 用它，但把它做成可选（``None`` 缺省）会让
    「传了 ``SUBSTITUTE_EXERCISE`` 却忘了传 ``exercises``」变成一个只在**那一条记录**上
    才炸的 ``TypeError``——离真因隔了一层，故一律必填。

    **空列表也产出新包**（``replace(pkg)``）：``out is not pkg`` 是「纯函数不返回入参」
    这条纪律的一部分，否则调用方拿到同一个对象、以为它是覆盖后的产物，而下游任何一次
    就地改写都会污染两边。

    分派用 ``is`` 逐个比对枚举成员（不是 ``==``），故一个裸字符串 ``kind`` 落到 ``else``
    那一支 ``ValueError``——见 :class:`OverrideKind` 的 docstring。
    """
    current = replace(pkg)
    for record in records:
        kind = record.kind
        if kind is OverrideKind.WEEKLY_FREQUENCY:
            current = _weekly_frequency(current, record)
        elif kind is OverrideKind.SUBSTITUTE_EXERCISE:
            current = _substitute(current, record, exercises)
        elif kind is OverrideKind.INTENSITY_STEP:
            current = _intensity_step(current, record)
        elif kind is OverrideKind.VOLUME_SCALE:
            current = _volume_scale(current, record)
        elif kind is OverrideKind.PAUSE:
            # 「暂停」是可撤销的，故**原样保留 weeks**、只置一个标志位：删掉 weeks 就不可逆了
            current = replace(current, paused=True)
        else:
            raise ValueError(
                f"OverrideRecord.kind {kind!r} 不是 OverrideKind 的五个成员之一"
                f"（{[member.value for member in OverrideKind]}）。**不静默忽略**："
                f"教师以为自己改过了、而处方一个字没变，那正是「静默跳过」在覆盖侧的形状。"
                f"若这一条是从 JSON 列读回来的，请先过 OverrideKind(...) 再传进来"
            )
    return current


def summarize_overrides(records: Sequence[OverrideRecord]) -> dict[str, int]:
    """按 ``kind`` 计数，供 spec §7.5 末段「学期末回答教师在哪些环节最不信任算法」。

    键是 ``kind.value``（``str``）而**不是**枚举成员本身：这个 dict 要落进 JSON。
    **按字典序排**，于是落库字节只由内容决定（canonical dump 才可复现，口径照
    :func:`app.refdata_prescription.sync_exercises` 里 ``sorted(spec.targets)`` 那句注释）。

    **只出现过的档才有键**（不补 0）：于是「一档都没被覆盖过」与「覆盖过但计数为 0」在
    数据上分得开——后者不可能发生，前者是一个真实且有意义的观测
    （``summarize_overrides([]) == {}``，即这个学期教师一次都没动过算法的结论）。
    """
    counts: dict[str, int] = {}
    for record in records:
        key = record.kind.value
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))

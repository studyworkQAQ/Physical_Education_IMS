"""spec §5.2 的五个触发条件求值（Plan 02 Task 6）。

处方**不每天重发**——分层重算每天跑，而一张 4 周训练包只在 spec §5.2 的五条判据之一
成立时才重新生成。本模块就是那五条判据的唯一住址：一个纯函数，输入是「今天是什么日子、
他今天什么层、库里那张处方是什么样」，输出是**全部命中**的触发原因。

**它是纯函数、不做 I/O**（Global Constraint #1）：日期与「教师点没点」全部由调用方注入，
本模块不读盘、不读时钟、不掷随机数，也不 import ``sqlalchemy`` / ``yaml`` / ``pathlib``。
于是「同一份输入 → 同一个结果」成立，且
:mod:`tests.architecture.test_domain_purity` 的三条守卫能机器可查地钉住这件事。

--------------------------------------------------------------------------

**返回全部命中者，不是第一个**（简报 Interfaces / Produces 逐字要求）。落库时全部写进
``prescription.trigger_reasons`` 那个 ``JsonText`` 列，因为教师端要能回答「为什么今天换了
处方」——只留第一条会让「教师手动请求 + 微周期到期」看起来只是「教师手动请求」，而后者
恰恰是需要人去复核安全替换的那一个（spec §7.4 / Review Focus 第 5 条）。

**tuple 的顺序 == :class:`TriggerReason` 的声明序 == spec §5.2 的编号序**（1..5）。
⚠️ 判据表说触发 5「**优先级最高**」，那说的是**是否触发**上的无条件（教师点了就要生成，
即使其余四条都不成立），**不是**它在返回 tuple 里的位置。把它挪到 tuple 的第一位会改掉
教师端那句文案的语序，而「按 spec 编号读」正是这一列能被人和机器同时读懂的原因。
守卫是 ``tests/domain/test_prescription_triggers.py`` 的
:func:`~tests.domain.test_prescription_triggers.test_multiple_triggers_all_reported_in_spec_order`
（钉顺序）与
:func:`~tests.domain.test_prescription_triggers.test_the_returned_order_is_the_declaration_order_not_the_evaluation_order`
（它的反面对照：证明那条 ``==`` 红的原因是顺序而不是集合）。

--------------------------------------------------------------------------

**第 0 条判据：``insufficient_data`` 一律早退**（Review Focus 第 3 条，spec §6.3① / §11.1
的 Z0 闸门）。``valid_count < 4`` 时 Plan 01 不产出分层标签，此时谈「该不该换处方」没有
意义——**数据不足时产出任何结果都是把「不知道」讲成「知道」**。故本函数第一句就是它，
且**无条件**：``teacher_requested=True`` 也不例外。

⚠️ **这一档的代价必须交代清楚**（简报 Step 1 点名「若你不同意这个决定，报为最高优先级
关切」）：它让教师端的「重新生成」按钮对这类学生**无声失败**。Plan 01 实测缺省注入下
500 人有 2 人落这一档（``tests/domain/test_prescription_triggers.py`` 的
:func:`~tests.domain.test_prescription_triggers.test_insufficient_data_label_never_triggers`
把 48 格穷举钉住）。**本模块只负责返回空 tuple，留痕是调用方的职责**（硬规矩 #39）：
Task 7 落库时必须把「今天对这个学生求值过、结果是空、原因是数据不足」记进
``daily_sync_run`` 的计数或一条 ``warning`` 日志，否则教师点了没反应又查不出原因。

**``Layer`` 从 :mod:`app.domain.stratify` 绝对导入**（P6-A6，与
:mod:`app.domain.prescription.match` 同口径：跨包指向所有者用绝对串，同包兄弟才用
``level == 1`` 的相对串）。⚠️ **本模块不出现第二份 ``"insufficient_data"`` 字面串**
（Global Constraint #3 单一所有者）：判据写 ``Layer.INSUFFICIENT.value``。
漂移守卫是
:func:`~tests.domain.test_prescription_triggers.test_insufficient_label_value_is_pinned_verbatim`
（把那个值字面钉在所有者上）与
:func:`~tests.domain.test_prescription_triggers.test_the_insufficient_early_return_reads_the_enum_not_a_second_literal`
（钉住行为侧的因果）。

--------------------------------------------------------------------------

⚠️ **本模块不 import ``datetime``**（与 :mod:`app.domain.prescription.intensity` /
``assembler`` / ``override`` / ``templates`` 同一条纪律）：
:data:`tests.architecture.test_domain_purity.ALLOWED_MODULES` 实测 =
``{dataclasses, enum, collections, collections.abc, numpy, typing}``，**``datetime`` 不在其中**。

既有做法有两半，本模块两半都沿用：

1. **类型标注写成前向引用字符串** ``"dt.date"``（实测：``intensity.py`` 的
   ``def age_from(birth: "dt.date", as_of: "dt.date") -> int``、``assembler.py`` 的
   ``birth: "dt.date"``、``override.py`` 的 ``applied_at: "dt.datetime"``）。
   ⚠️ **不是** ``from __future__ import annotations`` + ``TYPE_CHECKING``——那四个模块
   一个都没有 ``from __future__`` 那一行，也没有 ``TYPE_CHECKING`` 块；它们靠的是
   「标注本身就是一个字符串字面量」，运行时不求值。**代价**：
   ``typing.get_type_hints(evaluate_triggers)`` 会抛 ``NameError``（``dt`` 在本模块的
   命名空间里不存在），理由与处置逐字写在 :mod:`app.domain.prescription.intensity`
   的模块 docstring 里。
2. **运行时只读注入对象的属性**（duck typing），不新建任何日期/时间对象。

⚠️ **第 2 半在本模块比那四个更难，因为触发 3 要算「过了多少天」**，而计划判据表写的
算式是 ``as_of - last.generated_on >= timedelta(weeks=microcycle_weeks)`` ——
``timedelta`` 同样 import 不到。**处置是不构造它**：``date - date`` 的结果**自己就是**
一个带 ``.days`` 的对象，故判据写成::

    (inp.as_of - last.generated_on).days >= last.microcycle_weeks * _DAYS_PER_WEEK

即「只**读**减法结果的属性」，与 ``assembler.py`` 读 ``as_of.isoformat()``、
``intensity.py`` 读 ``birth.year`` 是同一条纪律，没有发明新东西。

**两者逐格等价**（对 ``datetime.date`` 操作数）：``date - date`` 恒为整数天的
``timedelta``，而 ``timedelta(weeks=W) == timedelta(days=7*W)``，故
``a - b >= timedelta(weeks=W)`` ⟺ ``(a - b).days >= 7*W``。
⚠️ **本模块守不住什么**（硬规矩 #39）：这个等价只在操作数是 ``date`` 时成立。谁传
``datetime.datetime`` 进来，``a - b`` 会带 ``seconds``，而 ``.days`` 对**负**差值向下取整
（``timedelta(days=-1, seconds=1).days == -1``）——本模块的判据按契约是 ``date``，
故不为此加防御；守卫是
:func:`~tests.domain.test_prescription_triggers.test_evaluate_triggers_only_needs_subtraction_and_greater_than_on_dates`
（它把「只需要 ``__sub__`` 与 ``__gt__``」这个最小契约钉住，于是「偷偷 import
``timedelta``」这条退路被堵死：一个只实现这两个方法的替身必须照样能用）。

--------------------------------------------------------------------------

**``current_template_id`` 被携带、但不被读**。它在 :class:`TriggerInput` 里的用处是让
调用方（Task 7）把「为什么生成」与「生成了什么」绑在同一次求值上：落库时
``prescription.template_ref`` 写的就是它，而两件事必须读同一个值，否则对不上账。
⚠️ 它**不是**第六条判据——spec §5.2 只有五条，「该换模板了」不在其中。守卫是
:func:`~tests.domain.test_prescription_triggers.test_current_template_id_is_not_a_trigger_criterion`。

⚠️ 于是 spec §5.2 有一个**真实的空洞**：同一层里主导短板或体成分翻了（``W`` / ``C`` 每天
重算），标签不变而该练的模板变了，五条一条都不成立。今天它由**触发 4** 兜住——体成分变化
必然伴随一次新采集，``latest_assessment_date`` 因此前进。那个兜底依赖的正是触发 4 的工程
口径（「任何新采集都算刷新，不限 week16」）；若将来把触发 4 收窄成「只在 week16 触发」，
这个空洞就会真的漏人。已记进 Task 6 报告的关切节，登记 spec §14 归 Task 9。

--------------------------------------------------------------------------

**``LastPrescription.status`` 也不进任何判据**：按契约它就是「当前那一张」，挑出正确的一行
是调用方的职责。让它进判据会有两个坏结果：① ``needs_review`` 抑制触发 3 的话，一张
有安全问题的处方就会**永远**挂着不换（而它照样该到期，教师端在复核安全替换的同时也该看到
「该换一张了」，两件事互不掩盖）；② ``archived`` 被当作「没有上一张」的话，学期归档后
重新开学就变成一次**静默的首次生成**，而正确的形状是它同时命中触发 3 或触发 4。
守卫是
:func:`~tests.domain.test_prescription_triggers.test_first_stratification_does_not_fire_when_there_is_a_last_prescription`
与
:func:`~tests.domain.test_prescription_triggers.test_microcycle_expiry_still_fires_for_a_replaced_or_needs_review_prescription`。
"""
from dataclasses import dataclass
from enum import Enum

from app.domain.stratify import Layer

#: 一周的天数。**私有**：它是历法事实、不是一个可以被调的口径，做成公有名会让人以为
#: 「改它就能改判据」，而真正该改的是 ``microcycle_weeks``（每张处方各自带）。
#: ⚠️ 前导下划线也让它不出现在
#: ``tests/test_refdata_prescription.py::_public_top_level_definitions`` 数出的公开面里
#: ——本模块的公开面**恰好四个名字**（下面那三个定义 + :func:`evaluate_triggers`），
#: 多一个公有顶层定义，那条穷尽守卫（支 5）当场红。
_DAYS_PER_WEEK = 7


class TriggerReason(str, Enum):
    """spec §5.2 的五条触发原因。**顺序即 spec 的编号**（1..5），声明序是承重的。

    **继承 ``str``** 的理由与 :class:`~app.domain.prescription.match.MatchStatus` /
    :class:`app.domain.stratify.Layer` 相同：``prescription.trigger_reasons`` 是一个
    ``JsonText`` 列，继承 ``str`` 之后 ``[r.value for r in reasons]`` 与直接落
    ``reasons`` 都能被 ``json.dumps`` 接受，不必在 ORM 边界上处处翻译
    （``Enum`` 本身不是 JSON 可序列化的，``json.dumps`` 对它当场 ``TypeError``）。

    ⚠️ **不要重排本枚举**：:func:`evaluate_triggers` 返回的 tuple 按声明序排列，而
    「声明序 == spec §5.2 的编号序」正是那一列能被人和机器同时读懂的原因。守卫是
    ``tests/domain/test_prescription_triggers.py`` 的
    :func:`~tests.domain.test_prescription_triggers.test_trigger_reason_has_exactly_the_five_spec_triggers_in_spec_order`
    （成员名与 ``.value`` 都字面钉住）。
    """

    #: ① 学生首次产生分层结果。
    FIRST_STRATIFICATION = "first_stratification"
    #: ② 分层标签发生变化（比的是**生成当时**的标签，见 :func:`evaluate_triggers`）。
    LAYER_CHANGED = "layer_changed"
    #: ③ 当前处方的微周期到期（``>=``，第 ``microcycle_weeks × 7`` 天当天就换）。
    MICROCYCLE_EXPIRED = "microcycle_expired"
    #: ④ 学期末体测/体成分数据刷新。⚠️ 「学期末」的口径 spec 没给，取的是
    #: 「任何新采集都算刷新」，见 :func:`evaluate_triggers` 的那一段。
    SEMESTER_DATA_REFRESHED = "semester_data_refreshed"
    #: ⑤ 教师手动请求。**无条件**成立，但**排在最后**（编号序），见模块 docstring 第 2 节。
    TEACHER_REQUESTED = "teacher_requested"


@dataclass(frozen=True)
class LastPrescription:
    """库里「当前那一张」处方的五个事实。字段名与顺序照简报 Interfaces / Produces 逐字。

    ``generated_on`` 是触发 3 与触发 4 的共同基准；``label_at_generation`` 是触发 2 的
    **唯一**比较对象（⚠️ 不是「上一次运行的标签」，两者的分岔见
    :func:`evaluate_triggers` 触发 2 那一段）；``microcycle_weeks`` 是触发 3 的周期长度，
    **不硬编码 4**（P6-A3 为此给 ``prescription`` 表加了同名列，生成当时从
    :attr:`app.domain.prescription.templates.Template.microcycle_weeks` 快照下来）。

    ⚠️ **``template_id`` 是 domain 侧的名字，DB 列叫 ``template_ref``**（P6-A7）：
    两者是**同一串字符**（``RED-END-ABN-01`` 一类），只在 ORM 边界上换名字，
    Task 7 落库时写 ``template_ref=last.template_id`` 即可。对照关系逐字写在
    ``app/db/models/prescription.py`` 的 :class:`~app.db.models.prescription.Prescription`
    docstring 里，守卫是
    ``tests/db/test_models.py::test_prescription_template_ref_is_the_same_name_as_the_template_table_column``。
    **本字段不参与任何判据**（见模块 docstring 倒数第二节）。

    ⚠️ **``status`` 也不参与任何判据**，理由见模块 docstring 最后一节。它在这里是给
    调用方留的（Task 7 换处方时要把上一张置 ``replaced``，那一步需要知道它原本是什么）。

    ``generated_on`` 的标注是前向引用字符串，因为 ``datetime`` 不在 domain 的 allow-list
    里（代价与既有做法见模块 docstring 第 4 节）。
    """

    generated_on: "dt.date"
    template_id: str
    label_at_generation: str
    microcycle_weeks: int
    status: str


@dataclass(frozen=True)
class TriggerInput:
    """一次求值所需的全部输入。字段名与顺序照简报 Interfaces / Produces 逐字。

    **一个字段都不多、也一个都不少**：本函数是纯函数，故它需要的每一件事都必须由调用方
    显式带进来（Global Constraint #1 的「时间与随机数一律由调用方注入」）。

    * ``as_of`` —— 今天是哪一天。**不是** ``date.today()``，是管道传进来的业务日期
      （:func:`app.pipeline.daily.run_daily` 的 ``business_date``）。
    * ``current_label`` —— 今天这次分层重算的标签，取值域是 :class:`Layer` 的四个
      ``.value``（**含** ``insufficient_data``：Z0 闸门拦下的学生带着它来求值，
      本模块必须认得它并早退）。⚠️ 标注是 ``str`` 而不是 ``Layer``：它的来源是
      ``stratification_result.label`` 那一列，而
      :class:`app.domain.prescription.match.MatchInput` 的 ``layer`` 之所以是 ``Layer``
      是因为它要按枚举身份比对模板维度；本模块只比字符串相等，收窄成枚举会要求 Task 7
      多做一次 ``Layer(...)`` 转换，而转换失败（``ValueError``）与「标签是
      ``insufficient_data``」是两件不同的事。
    * ``current_template_id`` —— 今天匹配到的模板 id（``None`` = 没匹配到）。
      **不参与判据**，见模块 docstring 倒数第二节。
    * ``last_prescription`` —— 库里当前那一张，``None`` = 从来没有过。
    * ``latest_assessment_date`` —— 最近一次体测/体成分采集的日期，``None`` = 本学期
      一次都没采到（或采集记录缺日期）。触发 4 对 ``None`` **短路**：把它当「很久以前」
      去比会 ``TypeError``，当「今天」去比会天天触发。
    * ``teacher_requested`` —— 教师点了「重新生成」。
    """

    as_of: "dt.date"
    current_label: str
    current_template_id: "str | None"
    last_prescription: "LastPrescription | None"
    latest_assessment_date: "dt.date | None"
    teacher_requested: bool


def evaluate_triggers(inp: TriggerInput) -> "tuple[TriggerReason, ...]":
    """求 spec §5.2 的五条判据，返回**全部**命中者（按声明序 == spec 编号序）。

    五条判据的精确口径（简报 Task 6 的判据表逐字）：

    ===  ==========================  ==========================================================
    #    触发                        判据
    ===  ==========================  ==========================================================
    1    首次产生分层结果            ``last_prescription is None``（且已过第 0 条早退）
    2    分层标签发生变化            ``current_label != last_prescription.label_at_generation``
    3    微周期到期                  ``(as_of - generated_on).days >= microcycle_weeks × 7``
    4    体测/体成分数据刷新         ``latest_assessment_date is not None`` 且它 **严格晚于**
                                     ``last_prescription.generated_on``
    5    教师手动请求                ``teacher_requested``
    ===  ==========================  ==========================================================

    **第 0 条（不是五条之一，但排在最前）**：``current_label == Layer.INSUFFICIENT.value``
    → **返回空 tuple**，无论其余条件是否成立、包括 ``teacher_requested=True``。
    理由与代价见模块 docstring 第 3 节（Review Focus 第 3 条的落点）。

    **触发 2 比的是 ``label_at_generation``，不是「上一次运行的标签」**——两者只在
    「判据成立但生成被拒」时才分岔，而那是一档真实存在的路径（:mod:`app.domain.prescription.match`
    的六种 status 里有五种是「今天不生成」）。构造：黄(D1，生成 P1) → 红(D2，触发 2 成立
    但模板待审校 → **没有 P2**) → 黄(D3)。此时库里那张仍是 P1，``label_at_generation``
    仍是 ``"yellow"``，故 D3 **不触发**；若比的是「D2 那次运行的标签」（``"red"``），
    D3 就会 ``"yellow" != "red"`` → 又触发一次，而库里那张的 ``label_at_generation``
    永远停在 ``"yellow"``，于是它**天天**触发、天天被拒，教师端天天收到一条
    「今天换了处方」而处方从来没换过。守卫是
    :func:`~tests.domain.test_prescription_triggers.test_layer_change_compares_against_the_label_at_generation`。

    **触发 3 是 ``>=`` 不是 ``>``**：第 ``microcycle_weeks × 7`` 天当天就该换。周数从
    **上一张处方**取（``last_prescription.microcycle_weeks``），**不硬编码 4**——模板可以
    是别的周期，而 P6-A3 为此把它快照在 ``prescription`` 行上。⚠️ 判据写成
    ``.days >= weeks × 7`` 而不是计划原文的 ``>= timedelta(weeks=…)``，因为
    ``timedelta`` import 不到；两者对 ``date`` 操作数逐格等价，理由见模块 docstring 第 4 节。

    **触发 4 的「学期末」口径 spec 没给**，取的是「``latest_assessment_date``
    **严格晚于** ``generated_on`` 即触发」（**任何**新采集都算刷新，不限 week16）。
    理由：week8 的二次采集同样改变了判定输入，而「只在 week16 触发」会让 10 月的数据变化
    拖到 12 月才反映到处方上。**这是工程决定，须登记 spec §14**（归 Task 9）。
    ⚠️ ``==`` 那一格**刻意不触发**：生成当天用的就是那批采集，再触发一次等于「生成完
    立刻又该生成」，而 ``prescription`` 表的 ``UniqueConstraint("student_id",
    "generated_on")`` 会把同一天第二次的 INSERT 直接拒收——于是「触发成立但落不了库」
    会变成 Task 7 每天都要处理的一档异常。
    ⚠️ **``last_prescription is None`` 时触发 4 不求值**：判据本身要读
    ``generated_on``，无从判起；而那一档已被触发 1 完整表达，再报一次会让
    ``trigger_reasons`` 里出现两条指向同一件事的原因。

    **触发 5 无条件成立**（教师点了就要生成，即使其余四条都不成立），但**排在 tuple 的
    最后**——「优先级最高」说的是是否触发上的无条件，不是位置，见模块 docstring 第 2 节。

    纯函数：不读盘、不读时钟、不掷随机数、不改 ``inp``（它是 frozen dataclass，
    连嵌套的 ``last_prescription`` 也是）。返回的 tuple 可能是空的（``()``）而
    **不是 ``None``**：空 tuple 与第 0 条早退的返回值同型，故调用方只需一条读法
    （``if evaluate_triggers(inp):``），不会分出 ``is not None`` 与「非空」两种语义。
    """
    # ⓪ Z0 早退（Review Focus 第 3 条）。**必须是第一句**：谁把它挪到触发 5 之后，
    #    「教师点了就无条件生成」这个误读就会让数据不足的学生拿到一张处方，而
    #    tests/domain/test_prescription_triggers.py 的 48 格穷举会当场红。
    #    ⚠️ 用 Layer.INSUFFICIENT.value，不在本模块写第二份字面串（P6-A6 / Global Constraint #3）。
    if inp.current_label == Layer.INSUFFICIENT.value:
        return ()

    hits: list[TriggerReason] = []
    last = inp.last_prescription

    if last is None:
        # ① 首次产生分层结果。⚠️ 触发 2/3/4 都要读 last 的字段，故它们住进 else 那一支：
        #    这不是省事，而是「没有上一张时那三条无从判起」的口径本身（见 docstring 触发 4）。
        hits.append(TriggerReason.FIRST_STRATIFICATION)
    else:
        # ② 分层标签发生变化：比**生成当时**的标签，不是「上一次运行的标签」。
        if inp.current_label != last.label_at_generation:
            hits.append(TriggerReason.LAYER_CHANGED)
        # ③ 微周期到期。`>=`：第 microcycle_weeks × 7 天当天就换。
        #    ⚠️ 只读减法结果的 .days，不构造 timedelta（domain import 不到 datetime）。
        elapsed_days = (inp.as_of - last.generated_on).days
        if elapsed_days >= last.microcycle_weeks * _DAYS_PER_WEEK:
            hits.append(TriggerReason.MICROCYCLE_EXPIRED)
        # ④ 体测/体成分数据刷新。**严格晚于**，且 None 短路。
        if (
            inp.latest_assessment_date is not None
            and inp.latest_assessment_date > last.generated_on
        ):
            hits.append(TriggerReason.SEMESTER_DATA_REFRESHED)

    # ⑤ 教师手动请求：无条件，但按 spec 编号序排在最后。
    if inp.teacher_requested:
        hits.append(TriggerReason.TEACHER_REQUESTED)

    return tuple(hits)

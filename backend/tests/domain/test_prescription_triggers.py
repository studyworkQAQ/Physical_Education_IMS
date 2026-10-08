# backend/tests/domain/test_prescription_triggers.py
"""五触发条件求值器 :func:`app.domain.prescription.triggers.evaluate_triggers` 的守卫（Task 6）。

spec §5.2 列了五条「什么时候该重新生成处方」的判据。处方**不每天重发**（分层重算才每天跑），
故这五条是整个处方引擎的**闸门**：判据松一档，学生每天拿到一张新处方、教师覆盖天天被冲掉；
判据紧一档，学生练着一张已经过期的处方而没人知道。

**本文件的三条主线**：

1. **``insufficient_data`` 早退是全局的、无条件的**（Review Focus 第 3 条）：Z0 闸门
   （spec §6.3①，``valid_count < 4``）拦下的学生**不得生成处方**，即使教师手动点了
   「重新生成」。:func:`test_insufficient_data_label_never_triggers` 把 32 种「其余条件
   全部成立」的组合穷举一遍，**每一格都必须是空 tuple**。这一条与 Plan 01 的 Z0 闸门
   同构：数据不足时产出任何结果都是把「不知道」讲成「知道」。
2. **触发 2 比的是 ``label_at_generation``，不是「上一次运行的标签」**：两者只在
   「触发成立但生成被拒」时才分岔，:func:`test_layer_change_compares_against_the_label_at_generation`
   用「黄→红→黄」三天把那一档构造出来（红那一天的生成被拒 → 库里那张处方的
   ``label_at_generation`` 仍是 ``"yellow"`` → 第三天回到黄时**不该**再触发一次）。
3. **触发 3 的 ``microcycle_weeks`` 从上一张处方取、边界是 ``>=``**：
   :func:`test_microcycle_expiry_is_inclusive_on_day_28`（第 28 天当天就该换）与
   :func:`test_microcycle_weeks_comes_from_the_previous_template_not_a_hardcoded_four`
   （构造一个 2 周的上一张处方，断言第 14 天触发）各钉一半。

**期望侧一律字面写死**（硬规矩 #35 / Global Constraint #4）：五个 ``TriggerReason`` 的
成员名与 ``.value``、``Layer.INSUFFICIENT.value``、日期与天数都写在测试里，
**不从**被测模块反推。唯一「两侧同源」的例外是
:func:`test_insufficient_label_value_is_pinned_verbatim`，而它**刻意**同源——它是
P6-A6 要求的**漂移测试**：``triggers.py`` 用 ``Layer.INSUFFICIENT.value`` 而不是第二份
字面串（Global Constraint #3 单一所有者），故由本条把那个值字面钉在
:mod:`app.domain.stratify` 上；谁改了 ``Layer``，本条与 ``triggers.py`` 的行为一起变。

⚠️ **本文件守不住什么**（硬规矩 #39）：

* **不守「同一天被两次触发只生成一张处方」**：那是**落库幂等**，住在
  ``prescription`` 表的 ``UniqueConstraint("student_id", "generated_on")`` 上，守卫是
  ``tests/db/test_models.py::test_same_day_second_prescription_for_one_student_is_rejected``。
  :func:`evaluate_triggers` 是纯函数，同一输入**必须**给同一答案（无随机、无时钟），
  这件事由 :func:`test_evaluate_triggers_is_deterministic` 钉；「只生成一张」不是它的职责。
* **不守「数据不足这件事被留痕」**：本函数返回空 tuple 就是它对 Review Focus 第 3 条的
  全部贡献；「调用方要把这件事记下来」是 Task 7 的落库职责，本文件管不到，也刻意不假装管到。
* **不守触发 4 的「学期末」口径**：spec 没给，简报 Task 6 的判据表把它定成
  「``latest_assessment_date > generated_on`` 即触发（**任何**新采集都算刷新，不限 week16）」，
  并明写「**这是工程决定，须登记 spec §14**」。本文件钉的是那个**已定的口径**，
  不是 spec 的原文；登记项归 Task 9。
"""
import dataclasses
import datetime as dt
import json

import pytest

from app.domain.prescription.triggers import (
    LastPrescription,
    TriggerInput,
    TriggerReason,
    evaluate_triggers,
)
from app.domain.stratify import Layer

# ---------------------------------------------------------------------------
# 期望侧的字面量（一律不从被测对象反推，硬规矩 #35）
# ---------------------------------------------------------------------------

#: spec §5.2 的五条，**顺序即 spec 的编号**（1..5）。返回 tuple 的顺序必须与它一致。
_FIVE_IN_SPEC_ORDER = (
    "first_stratification",
    "layer_changed",
    "microcycle_expired",
    "semester_data_refreshed",
    "teacher_requested",
)

#: 上一张处方的生成日。下面所有天数都从它起算（字面写死，不用 ``timedelta`` 现算，
#: 免得期望侧与被测侧共用同一个算式）。
_GENERATED_ON = dt.date(2026, 3, 2)
#: ``microcycle_weeks = 4`` → 28 天。**第 28 天**（``>=`` 的开火日）与**第 27 天**。
_DAY_28 = dt.date(2026, 3, 30)
_DAY_27 = dt.date(2026, 3, 29)
#: ``microcycle_weeks = 2`` → 14 天。第 14 天与第 13 天。
_DAY_14 = dt.date(2026, 3, 16)
_DAY_13 = dt.date(2026, 3, 15)


def _last(label="yellow", weeks=4, template_id="YEL-END-NOR-01",
          generated_on=_GENERATED_ON, status="active"):
    """一张上一张处方。**默认与「黄层、4 周、今天之前 28 天以内」相容**，故默认不触发。"""
    return LastPrescription(
        generated_on=generated_on, template_id=template_id, label_at_generation=label,
        microcycle_weeks=weeks, status=status,
    )


def _inp(as_of=_DAY_27, label="yellow", template_id="YEL-END-NOR-01", last=None,
         assessment=None, teacher=False):
    """一次求值的输入。``last`` 默认 ``None``，故每条测试都必须显式说清有没有上一张。"""
    return TriggerInput(
        as_of=as_of, current_label=label, current_template_id=template_id,
        last_prescription=last, latest_assessment_date=assessment,
        teacher_requested=teacher,
    )


# ---------------------------------------------------------------------------
# 契约：五个成员、字段名与顺序、frozen、str 混入
# ---------------------------------------------------------------------------

def test_trigger_reason_has_exactly_the_five_spec_triggers_in_spec_order():
    """``TriggerReason`` 恰好五个成员，**声明序 == spec §5.2 的编号序**。

    顺序是承重的：:func:`evaluate_triggers` 返回的 tuple 按声明序排列，教师端据此
    把「为什么今天换了处方」渲染成一句话，而 ``prescription.trigger_reasons`` 落库的
    也是这个顺序。重排枚举会静默改掉那个渲染顺序，故这里连 ``.value`` 一起字面钉住。
    """
    assert [m.name for m in TriggerReason] == [
        "FIRST_STRATIFICATION", "LAYER_CHANGED", "MICROCYCLE_EXPIRED",
        "SEMESTER_DATA_REFRESHED", "TEACHER_REQUESTED",
    ]
    assert [m.value for m in TriggerReason] == list(_FIVE_IN_SPEC_ORDER)
    assert len(TriggerReason) == 5


def test_trigger_reason_inherits_str_so_it_lands_in_json_without_dot_value():
    """继承 ``str``：``trigger_reasons`` 那个 ``JsonText`` 列要能直接 ``json.dumps``。

    与 :class:`app.domain.prescription.match.MatchStatus` /
    :class:`app.domain.stratify.Layer` 同一条处置。少了 ``str`` 混入，Task 7 落库时
    会写出 ``["<TriggerReason.TEACHER_REQUESTED: 'teacher_requested'>"]`` 一类的东西
    （``Enum`` 本身不是 JSON 可序列化的，``json.dumps`` 当场 ``TypeError``）。
    """
    assert isinstance(TriggerReason.TEACHER_REQUESTED, str)
    assert TriggerReason.TEACHER_REQUESTED == "teacher_requested"
    assert json.dumps([r.value for r in TriggerReason]) == json.dumps(list(_FIVE_IN_SPEC_ORDER))


def test_the_two_value_objects_are_frozen_and_carry_the_pinned_fields():
    """``TriggerInput`` / ``LastPrescription`` 的字段名与顺序逐字照简报 Produces，且 frozen。

    frozen 不是风格问题：:func:`evaluate_triggers` 是纯函数，而它能被「求值过程中就地
    改写输入」破坏的唯一途径就是字段可变。两个值对象都不可变，「同一输入 → 同一输出」
    才有机制保证，而不只是纪律。
    """
    assert tuple(f.name for f in dataclasses.fields(TriggerInput)) == (
        "as_of", "current_label", "current_template_id", "last_prescription",
        "latest_assessment_date", "teacher_requested",
    )
    assert tuple(f.name for f in dataclasses.fields(LastPrescription)) == (
        "generated_on", "template_id", "label_at_generation", "microcycle_weeks", "status",
    )
    inp = _inp()
    last = _last()
    with pytest.raises(dataclasses.FrozenInstanceError):
        inp.current_label = "red"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        last.label_at_generation = "red"  # type: ignore[misc]


def test_insufficient_label_value_is_pinned_verbatim():
    """**漂移测试**（P6-A6）：``Layer.INSUFFICIENT.value`` 字面就是 ``"insufficient_data"``。

    ``triggers.py`` 刻意**不**硬编码这一串，而是用 ``Layer.INSUFFICIENT.value``
    （Global Constraint #3：``Layer`` 的唯一所有者是 :mod:`app.domain.stratify`）。
    代价是「那个值到底是什么」在本包里没有字面记录，故由本条把它钉住：谁改了
    ``Layer.INSUFFICIENT`` 的值，本条红，而 ``triggers.py`` 的行为**跟着一起变**
    （这正是单一所有者想要的：改一处、两侧同步，而不是两处各说各话）。
    """
    assert Layer.INSUFFICIENT.value == "insufficient_data"
    assert [m.value for m in Layer] == ["red", "yellow", "green", "insufficient_data"]


# ---------------------------------------------------------------------------
# 决定第 1 条：``insufficient_data`` → 空 tuple，无条件、无例外
# ---------------------------------------------------------------------------

def test_insufficient_data_label_never_triggers():
    """Review Focus 第 3 条：**即使 ``teacher_requested=True``** 也不生成处方。

    穷举「其余四条全部成立」的 **48** 种组合（有没有上一张 × 上一张的标签 × 到期没到期
    × 有没有新采集 × 教师点没点 = 2 × 3 × 2 × 2 × 2），**每一格都必须是空 tuple**。
    这一条要放在 :func:`evaluate_triggers` 的最前面，而本测试就是它的守卫：
    谁把早退挪到触发 5 之后（「教师点了就无条件生成」是一个很自然的误读），本条当场红。

    ⚠️ **这是本 Task 最高优先级的一个工程决定**，简报 Task 6 Step 1 明写「若你不同意
    这个决定，报为最高优先级关切」：它会让教师端的「重新生成」按钮对 ``valid_count < 4``
    的学生**无声失败**。Plan 01 实测缺省注入下 500 人有 2 人落这一档，故它不是理论档。
    决定仍是「不生成」，理由与 Z0 同构；但 Task 7 **必须**给这一档留痕
    （``daily_sync_run`` 的计数或一条 ``warning`` 日志），否则教师点了没反应又查不出原因。
    """
    cases = []
    for has_last in (False, True):
        for label in ("red", "yellow", "green"):
            for expired in (False, True):
                for assessment in (None, dt.date(2026, 3, 20)):
                    for teacher in (False, True):
                        last = None
                        if has_last:
                            last = _last(
                                label=label if not expired else "green",
                                generated_on=_GENERATED_ON,
                            )
                        cases.append(_inp(
                            as_of=_DAY_28 if expired else _DAY_27,
                            label="insufficient_data",
                            last=last, assessment=assessment, teacher=teacher,
                        ))
    # 空转守卫：这一档必须是 2 × 3 × 2 × 2 × 2 = 48 格，且「其余四条全成立」那一格在里面
    assert len(cases) == 48
    assert any(
        c.last_prescription is not None and c.teacher_requested
        and c.latest_assessment_date is not None and c.as_of == _DAY_28
        for c in cases
    ), "穷举里必须真的包含「其余四条全部成立」那一格，否则本条是空转"

    for case in cases:
        assert evaluate_triggers(case) == (), (
            f"insufficient_data 的学生不该生成处方（Review Focus 第 3 条）：{case}"
        )


def test_no_last_prescription_and_insufficient_label_returns_empty():
    """首次分层 + ``insufficient_data`` → 空 tuple（触发 1 的判据里那半个条件）。

    触发 1 是「``last_prescription is None`` **且** ``current_label !=
    Layer.INSUFFICIENT.value``」：Z0 闸门拦下的学生**没有产生分层结果**，故「首次」
    对他不成立。少了后半个条件，Plan 01 实测那 2/500 人会在第一天就拿到一张处方，
    而匹配器对他们只能报 ``NO_LAYER``（:mod:`app.domain.prescription.match` 的 ①）。
    """
    assert evaluate_triggers(_inp(label="insufficient_data", last=None)) == ()
    # 对照：同一格把标签换成合法层，触发 1 立刻成立
    assert evaluate_triggers(_inp(label="green", last=None)) == (
        TriggerReason.FIRST_STRATIFICATION,
    )


# ---------------------------------------------------------------------------
# 触发 1：首次产生分层结果
# ---------------------------------------------------------------------------

def test_first_stratification_triggers_only_once():
    """触发 1 只在「没有上一张处方」时成立；有了就永不重复。

    三个合法层各钉一格（``red`` / ``yellow`` / ``green``），且断言返回的是**恰好一个**
    元素——它不该顺带把触发 2/3/4 也带上（``last is None`` 时那三条无从判起）。
    """
    for label in ("red", "yellow", "green"):
        assert evaluate_triggers(_inp(label=label, last=None)) == (
            TriggerReason.FIRST_STRATIFICATION,
        ), label


def test_first_stratification_does_not_fire_when_there_is_a_last_prescription():
    """有上一张处方时触发 1 不成立——即使那张处方已经 ``replaced`` / ``archived``。

    ``status`` 刻意**不进任何一条判据**：``last_prescription`` 按契约就是「当前那一张」，
    调用方（Task 7）负责挑出正确的一行传进来。本条把这件事钉成期望行为：一个
    ``status="archived"`` 的上一张处方**照样**抑制触发 1，免得下一个人以为这里该加一句
    ``if last.status == "archived": 当作没有上一张``——那会让「学期归档后重新开学」
    变成一次静默的首次生成，而正确的形状是它同时也会命中触发 3 或触发 4。
    """
    for status in ("active", "replaced", "archived", "needs_review"):
        assert evaluate_triggers(
            _inp(last=_last(status=status))
        ) == (), status


# ---------------------------------------------------------------------------
# 触发 2：分层标签发生变化
# ---------------------------------------------------------------------------

def test_layer_change_fires_when_the_label_differs_from_the_one_at_generation():
    """触发 2 成立：当前标签 ≠ 生成当时的标签。三对合法层各钉一格。"""
    for generated, current in (("yellow", "red"), ("red", "green"), ("green", "yellow")):
        assert evaluate_triggers(
            _inp(label=current, last=_last(label=generated))
        ) == (TriggerReason.LAYER_CHANGED,), (generated, current)


def test_layer_change_does_not_fire_when_the_label_is_unchanged():
    """触发 2 不成立：三个合法层各自「没变」都不触发（``!=`` 的假分支）。"""
    for label in ("red", "yellow", "green"):
        assert evaluate_triggers(_inp(label=label, last=_last(label=label))) == (), label


def test_layer_change_compares_against_the_label_at_generation():
    """**主线 2**：比的是 ``label_at_generation``，不是「上一次运行的标签」。

    「黄→红→黄」三天，红那一天的生成**被拒**（例如匹配器报 ``NOT_APPROVED``，
    见 Review Focus 第 5 条与 :mod:`app.domain.prescription.match`）——于是库里那张
    处方的 ``label_at_generation`` 仍是 ``"yellow"``：

    * **D1**（``03-02``，黄）：没有上一张 → 触发 1，生成 P1（``label_at_generation="yellow"``）；
    * **D2**（``03-03``，红）：``"red" != "yellow"`` → 触发 2 成立，但**生成被拒**，没有 P2；
    * **D3**（``03-04``，黄）：``last_prescription`` 仍是 P1，``"yellow" == "yellow"``
      → **不触发**。

    若改成比「上一次运行的标签」（D2 那次运行的结果是 ``"red"``），D3 就会
    ``"yellow" != "red"`` → **又触发一次**，而库里那张处方的 ``label_at_generation``
    依然是 ``"yellow"``：于是它会**天天**触发、天天被拒，教师端天天收到一条
    「今天换了处方」而处方从来没换过。那正是简报判据表点名的失效。

    ⚠️ D3 那一格刻意让 ``current_template_id`` 与 ``last.template_id`` **不同**
    （同一层里主导短板从耐力翻到力量，而 ``W`` 是每天重算的，故这是真实可能的一档）：
    它钉住触发 2 **只看标签、不看模板**。谁把判据换成 ``current_template_id !=
    last.template_id``（一个很自然的误读：「该换模板了就该换处方」），D3 那一条断言
    当场红——而模板变化本身**不是** spec §5.2 的五条之一。
    """
    # D1：黄，没有上一张
    assert evaluate_triggers(_inp(as_of=_GENERATED_ON, label="yellow", last=None)) == (
        TriggerReason.FIRST_STRATIFICATION,
    )
    p1 = _last(label="yellow", generated_on=_GENERATED_ON, template_id="YEL-END-NOR-01")

    # D2：红，上一张是 P1（黄）→ 触发 2 成立
    assert evaluate_triggers(
        _inp(as_of=dt.date(2026, 3, 3), label="red",
             template_id="RED-END-NOR-01", last=p1)
    ) == (TriggerReason.LAYER_CHANGED,)

    # D3：回到黄，而库里那张**仍是 P1**（红那天的生成被拒）→ 不触发
    assert evaluate_triggers(
        _inp(as_of=dt.date(2026, 3, 4), label="yellow",
             template_id="YEL-STR-NOR-01", last=p1)
    ) == ()


def test_current_template_id_is_not_a_trigger_criterion():
    """``current_template_id`` **不是**判据：它被携带、但不被读。

    它在 :class:`TriggerInput` 里的用处是给调用方（Task 7）当输入记录的一部分——
    落库时 ``prescription.template_ref`` 要写它，而 ``evaluate_triggers`` 与那次落库
    必须读同一个值（否则「为什么生成」与「生成了什么」会对不上账）。
    本条把「它不参与判定」钉成期望行为：只改 ``current_template_id``、其余不动，
    结果必须逐字不变。

    ⚠️ **spec §5.2 因此有一个真实的空洞**（记进报告的关切节）：同一层里主导短板或体成分
    翻了（``W`` / ``C`` 每天重算，故这会发生在**没有新采集**的情况下——例如身高体重录入了
    补测），标签不变而该练的模板变了，五条触发**一条都不成立**。今天它由触发 4 兜住
    （体成分变化必然伴随一次新采集 → ``latest_assessment_date`` 前进），而那个兜底
    依赖的是触发 4 的工程口径（「任何新采集都算刷新」）；若将来把触发 4 收窄成
    「只在 week16 触发」，这个空洞就会真的漏人。
    """
    base = evaluate_triggers(_inp(last=_last(template_id="YEL-END-NOR-01")))
    for other in ("YEL-STR-NOR-01", "YEL-END-ABN-01", None):
        assert evaluate_triggers(
            _inp(template_id=other, last=_last(template_id="YEL-END-NOR-01"))
        ) == base, other
    assert base == ()


# ---------------------------------------------------------------------------
# 触发 3：微周期到期（``>=``，且周数从上一张处方取）
# ---------------------------------------------------------------------------

def test_microcycle_expiry_is_inclusive_on_day_28():
    """**``>=`` 不是 ``>``**：第 28 天当天就该换。

    ``microcycle_weeks = 4`` → 28 天。``_GENERATED_ON = 2026-03-02``，故
    ``_DAY_28 = 2026-03-30``（差 28 天，开火）与 ``_DAY_27 = 2026-03-29``（差 27 天，不开火）。
    两个日期都**字面写死**、不用 ``timedelta`` 现算，免得期望侧与被测侧共用同一个算式
    （硬规矩 #35）。差一天不是小事：``>`` 会让每张处方都多活一天，而
    ``prescription.valid_to`` 的闭区间算式（``generated_on + 4 周 − 1 天`` = ``03-29``）
    正是按「第 28 天到期、次日换新」设计的——判据写成 ``>`` 就会在 ``03-30`` 出现
    「旧处方已过期、新处方还没生成」的空档（守卫在
    ``tests/db/test_models.py::test_prescription_valid_from_is_required_and_valid_to_is_not``
    的算式说明里）。
    """
    assert (_DAY_28 - _GENERATED_ON).days == 28, "字面日期必须真的差 28 天"
    assert (_DAY_27 - _GENERATED_ON).days == 27
    assert evaluate_triggers(_inp(as_of=_DAY_28, last=_last(weeks=4))) == (
        TriggerReason.MICROCYCLE_EXPIRED,
    )
    assert evaluate_triggers(_inp(as_of=_DAY_27, last=_last(weeks=4))) == ()
    # 过了到期日也一样成立（判据是 >=，不是 ==）
    assert evaluate_triggers(
        _inp(as_of=dt.date(2026, 4, 15), last=_last(weeks=4))
    ) == (TriggerReason.MICROCYCLE_EXPIRED,)


def test_microcycle_weeks_comes_from_the_previous_template_not_a_hardcoded_four():
    """周数从**上一张处方**取：2 周的模板在第 14 天就到期，不是第 28 天。

    P6-A3 为此给 ``prescription`` 表加了 ``microcycle_weeks`` 这一列（``prescription_template``
    表里没有它，实测 10 列），理由正是「不硬编码 4」。本条与
    :func:`test_microcycle_expiry_is_inclusive_on_day_28` 一起把两个方向都钉住：
    ``weeks=2`` 时第 14 天开火、第 13 天不开；``weeks=6`` 时第 28 天**不**开火
    （硬编码 4 的实现会在这一格给出相反的答案）。
    """
    assert (_DAY_14 - _GENERATED_ON).days == 14
    assert (_DAY_13 - _GENERATED_ON).days == 13
    assert evaluate_triggers(_inp(as_of=_DAY_14, last=_last(weeks=2))) == (
        TriggerReason.MICROCYCLE_EXPIRED,
    )
    assert evaluate_triggers(_inp(as_of=_DAY_13, last=_last(weeks=2))) == ()
    # 反向对照：6 周的处方在第 28 天还没到期（硬编码 4 的实现在这一格会误报）
    assert evaluate_triggers(_inp(as_of=_DAY_28, last=_last(weeks=6))) == ()
    assert evaluate_triggers(
        _inp(as_of=dt.date(2026, 4, 13), last=_last(weeks=6))
    ) == (TriggerReason.MICROCYCLE_EXPIRED,)


def test_microcycle_expiry_still_fires_for_a_replaced_or_needs_review_prescription():
    """``status`` 不进判据：一张 ``needs_review`` 的处方到期了照样到期。

    这一格是**安全侧**的：spec §7.4 要求「安全规则命中却找不到等价动作」时把处方置
    ``needs_review`` 并交人工复核（Review Focus 第 5 条）。若 ``needs_review`` 抑制了
    触发 3，那张有问题的处方就会**永远**挂着不换；而它照样到期，教师端在复核的同时
    也会看到「该换一张了」，两件事互不掩盖。
    """
    for status in ("needs_review", "replaced", "archived", "active"):
        assert evaluate_triggers(
            _inp(as_of=_DAY_28, last=_last(weeks=4, status=status))
        ) == (TriggerReason.MICROCYCLE_EXPIRED,), status


# ---------------------------------------------------------------------------
# 触发 4：学期末体测/体成分数据刷新（工程口径，须登记 spec §14）
# ---------------------------------------------------------------------------

def test_assessment_refresh_triggers():
    """新采集晚于生成日 → 触发 4。**不限 week16**（简报 Task 6 判据表的工程决定）。

    理由照抄判据表：week8 的二次采集同样改变了判定输入，而「只在 week16 触发」会让
    10 月的数据变化拖到 12 月才反映到处方上。⚠️ spec §5.2 那一格写的是「学期末体测/
    体成分数据刷新」，**没给「学期末」的口径**，故这是一次工程决定、须登记 spec §14
    （归 Task 9）。本条钉的是已定的口径，不是 spec 的原文。
    """
    assert evaluate_triggers(
        _inp(as_of=_DAY_27, last=_last(), assessment=dt.date(2026, 3, 20))
    ) == (TriggerReason.SEMESTER_DATA_REFRESHED,)
    # 采集日就在生成日的次日也算刷新（严格晚于即可，不看间隔多久）
    assert evaluate_triggers(
        _inp(as_of=_DAY_27, last=_last(), assessment=dt.date(2026, 3, 3))
    ) == (TriggerReason.SEMESTER_DATA_REFRESHED,)


def test_assessment_on_or_before_the_generation_day_does_not_trigger():
    """触发 4 是**严格晚于**：采集日 == 生成日不触发（那张处方就是用这批数据生成的）。

    ``==`` 那一格是这一条的承重处：生成当天用的就是那批采集，再触发一次等于
    「生成完立刻又该生成」，而 ``prescription`` 表的
    ``UniqueConstraint("student_id", "generated_on")`` 会把第二次的 INSERT 直接拒收
    ——于是同一天里「触发成立但落不了库」会变成 Task 7 每天都要处理的一档异常。
    """
    assert evaluate_triggers(
        _inp(last=_last(), assessment=_GENERATED_ON)
    ) == (), "采集日 == 生成日：那张处方就是用这批数据生成的"
    assert evaluate_triggers(
        _inp(last=_last(), assessment=dt.date(2026, 2, 1))
    ) == (), "采集日早于生成日：不是刷新"


def test_missing_assessment_date_does_not_trigger():
    """``latest_assessment_date is None`` → 触发 4 不成立（``and`` 的短路那一支）。

    ``None`` 是真实的一档：这名学生本学期一次体测都没采到（或采集记录缺日期）。
    把它当「很久以前」去比会 ``TypeError``，当「今天」去比会天天触发，故只能短路。
    """
    assert evaluate_triggers(_inp(last=_last(), assessment=None)) == ()


def test_assessment_refresh_is_not_evaluated_without_a_last_prescription():
    """没有上一张处方时触发 4 不成立——那一档由触发 1 覆盖。

    判据本身要读 ``last_prescription.generated_on``，``last is None`` 时无从判起；
    而「首次分层 + 恰好有一批新采集」这件事已经被触发 1 完整表达了，再报一次触发 4
    会让 ``trigger_reasons`` 里出现两条指向同一件事的原因，教师端渲染成
    「首次分层 + 数据刷新」两句废话。
    """
    assert evaluate_triggers(
        _inp(label="green", last=None, assessment=dt.date(2026, 3, 20))
    ) == (TriggerReason.FIRST_STRATIFICATION,)


# ---------------------------------------------------------------------------
# 触发 5：教师手动请求
# ---------------------------------------------------------------------------

def test_teacher_request_triggers_alone():
    """教师点了就要生成：其余四条**全不成立**时它单独触发。

    这一格是「优先级最高」的字面含义——它说的是**是否触发**上的无条件，
    **不是**返回 tuple 里的位置（位置恒为 spec 编号序，见
    :func:`test_multiple_triggers_all_reported_in_spec_order`）。
    """
    assert evaluate_triggers(
        _inp(as_of=_DAY_27, label="yellow", last=_last(), assessment=None, teacher=True)
    ) == (TriggerReason.TEACHER_REQUESTED,)
    # 首次分层 + 教师点了：两条都报，触发 5 排在后面（编号序）
    assert evaluate_triggers(_inp(label="green", last=None, teacher=True)) == (
        TriggerReason.FIRST_STRATIFICATION, TriggerReason.TEACHER_REQUESTED,
    )


def test_teacher_request_does_not_fire_when_not_requested():
    """``teacher_requested=False`` 时触发 5 不成立（``if`` 的假分支）。"""
    assert evaluate_triggers(_inp(last=_last(), teacher=False)) == ()
    assert TriggerReason.TEACHER_REQUESTED not in evaluate_triggers(
        _inp(label="red", last=_last(label="yellow"), teacher=False)
    )


# ---------------------------------------------------------------------------
# 组合与顺序
# ---------------------------------------------------------------------------

def test_multiple_triggers_all_reported_in_spec_order():
    """返回**全部**命中的，且顺序 == ``TriggerReason`` 的声明序 == spec §5.2 的编号序。

    不是「返回第一个」：落库时全部写进 ``prescription.trigger_reasons``，教师端要能
    看到「为什么今天换了处方」的**完整**理由（只留第一条会让「教师手动请求 + 微周期
    到期」看起来只是「教师手动请求」，而后者恰恰是那个需要人去复核安全替换的原因）。

    两格各钉一半：① 触发 2/3/4/5 同时成立 → 四个按编号序；② 五条全成立
    （没有上一张 + 教师点了）→ 触发 1 与触发 5 两个（2/3/4 在 ``last is None``
    时无从判起，见 :func:`test_assessment_refresh_is_not_evaluated_without_a_last_prescription`）。
    """
    assert evaluate_triggers(_inp(
        as_of=_DAY_28, label="red", last=_last(label="yellow", weeks=4),
        assessment=dt.date(2026, 3, 20), teacher=True,
    )) == (
        TriggerReason.LAYER_CHANGED,
        TriggerReason.MICROCYCLE_EXPIRED,
        TriggerReason.SEMESTER_DATA_REFRESHED,
        TriggerReason.TEACHER_REQUESTED,
    )
    assert evaluate_triggers(_inp(
        as_of=_DAY_28, label="green", last=None,
        assessment=dt.date(2026, 3, 20), teacher=True,
    )) == (TriggerReason.FIRST_STRATIFICATION, TriggerReason.TEACHER_REQUESTED)


def test_the_returned_order_is_the_declaration_order_not_the_evaluation_order():
    """顺序由**枚举声明序**决定，不由求值顺序决定。

    这一条是上一条的**反面对照**（硬规矩 #50）：把触发 5 的判定挪到函数最前面
    （一个很自然的改写，因为判据表说它「优先级最高」），返回的 tuple 会变成
    ``(TEACHER_REQUESTED, LAYER_CHANGED)``——**集合相同、顺序不同**。上一条断言的是
    tuple 相等，故它会红；本条把「红的原因是顺序而不是集合」显式说清，
    免得下一个人以为那条断言过紧而放宽成 ``set(...) == set(...)``。
    """
    got = evaluate_triggers(_inp(
        as_of=_DAY_28, label="red", last=_last(label="yellow"), teacher=True,
    ))
    assert got == (
        TriggerReason.LAYER_CHANGED, TriggerReason.MICROCYCLE_EXPIRED,
        TriggerReason.TEACHER_REQUESTED,
    )
    assert set(got) == {
        TriggerReason.LAYER_CHANGED, TriggerReason.MICROCYCLE_EXPIRED,
        TriggerReason.TEACHER_REQUESTED,
    }, "集合相等但顺序不对时，上面那条 == 才是真的在钉顺序"
    assert got != (
        TriggerReason.TEACHER_REQUESTED, TriggerReason.LAYER_CHANGED,
        TriggerReason.MICROCYCLE_EXPIRED,
    )


def test_no_trigger_returns_an_empty_tuple_not_none():
    """五条全不成立 → **空 tuple**，不是 ``None``。

    ``None`` 会让调用方写出 ``if reasons:`` 与 ``if reasons is not None:`` 两种读法，
    而前者对空 tuple 与 ``None`` 给出同一个答案、后者不同——一处静默的分歧。
    空 tuple 还与「``insufficient_data`` 早退」的返回值同型，故调用方只需一条读法。
    """
    got = evaluate_triggers(_inp(last=_last()))
    assert got == ()
    assert got is not None
    assert isinstance(got, tuple)
    assert not got


# ---------------------------------------------------------------------------
# Global Constraint #1：无时钟、无随机、纯函数
# ---------------------------------------------------------------------------

def test_evaluate_triggers_is_deterministic():
    """**Step 6b（本 Task 唯一保留的确定性测试，P6-A1）**：同输入两次，结果逐字相同。

    这是 Global Constraint「时间与随机数一律由调用方注入」的落点：日期全部由
    :class:`TriggerInput` 带进来，本函数**不读时钟**、**不掷随机数**、**不改输入**。
    三件事各钉一半：

    * 同一个输入对象连调两次 → 结果 ``==`` 且 ``repr`` 逐字相同（``repr`` 一起比是因为
      ``==`` 对 tuple 只比元素，而元素是 ``str`` 混入的枚举、``repr`` 才暴露「换了个对象」）；
    * 两个**内容相同但不同一**的输入对象 → 结果相同（证明它没有按对象身份缓存）；
    * 调用之后输入对象**逐字段未变**（frozen dataclass 已经保证，但 ``last_prescription``
      是嵌套的，故连它一起复核）。

    ⚠️ **本条守不住「不读时钟」这件事本身**（硬规矩 #39）：一个读了
    ``date.today()`` 的实现在同一天里连调两次也会给出相同答案。真正守那一档的是
    :mod:`tests.architecture.test_domain_purity` 的三条守卫（``datetime`` 不在
    :data:`~tests.architecture.test_domain_purity.ALLOWED_MODULES` 里，故 domain 根本
    import 不到它），以及下面那条 duck typing 测试（它证明本函数**只需要** ``__sub__``
    与 ``__gt__``，连 ``datetime`` 这个模块都不必存在）。
    """
    once = _inp(as_of=_DAY_28, label="red", last=_last(label="yellow"),
                assessment=dt.date(2026, 3, 20), teacher=True)
    first = evaluate_triggers(once)
    second = evaluate_triggers(once)
    assert first == second
    assert repr(first) == repr(second)

    again = _inp(as_of=_DAY_28, label="red", last=_last(label="yellow"),
                 assessment=dt.date(2026, 3, 20), teacher=True)
    assert again == once and again is not once
    assert evaluate_triggers(again) == first

    # 输入未被改写（连嵌套的 last_prescription 一起复核）
    assert once.as_of == _DAY_28 and once.current_label == "red"
    assert once.last_prescription == _last(label="yellow")
    assert once.latest_assessment_date == dt.date(2026, 3, 20)
    assert once.teacher_requested is True


def test_evaluate_triggers_only_needs_subtraction_and_greater_than_on_dates():
    """domain **不 import** ``datetime``，故日期是 duck typing 的。

    :mod:`app.domain.prescription.intensity` / ``assembler`` / ``override`` 的既有做法是
    **标注写成前向引用字符串** ``"dt.date"``、运行时只读注入对象的属性；本模块沿用同一条，
    但它比那三个多一件事：**日期要参与算术**（触发 3 的天数差、触发 4 的先后比较），
    而 ``timedelta`` 同样 import 不到（``datetime`` 不在
    :data:`tests.architecture.test_domain_purity.ALLOWED_MODULES` 里）。

    处置是**不构造 ``timedelta``**：``date - date`` 的结果自己就是一个带 ``.days`` 的对象，
    故触发 3 写成 ``(as_of - generated_on).days >= microcycle_weeks * 7``，只**读**减法结果
    的属性、不新建任何日期对象。这与那三个模块「只读注入对象的属性」是同一条纪律。

    本条把那个最小契约钉住：一个**不是** ``datetime.date``、只实现 ``__sub__``（返回带
    ``.days`` 的对象）与 ``__gt__`` 的替身同样能用。少了它，「不 import datetime」只是
    一句散文，下一个人可以顺手补一句 ``from datetime import timedelta`` 而全绿
    （架构守卫会红，但那条红的原因与这里要守的契约隔了一层）。
    """

    class _FakeSpan:
        def __init__(self, days: int) -> None:
            self.days = days

    class _FakeDate:
        """只带 ``__sub__`` 与 ``__gt__`` 的最小日期替身（序数天）。"""

        def __init__(self, ordinal: int) -> None:
            self._ordinal = ordinal

        def __sub__(self, other: "_FakeDate") -> _FakeSpan:
            return _FakeSpan(self._ordinal - other._ordinal)

        def __gt__(self, other: "_FakeDate") -> bool:
            return self._ordinal > other._ordinal

    generated, day_27, day_28 = _FakeDate(0), _FakeDate(27), _FakeDate(28)
    assert evaluate_triggers(TriggerInput(
        as_of=day_28, current_label="yellow", current_template_id="YEL-END-NOR-01",
        last_prescription=LastPrescription(
            generated_on=generated, template_id="YEL-END-NOR-01",
            label_at_generation="yellow", microcycle_weeks=4, status="active",
        ),
        latest_assessment_date=None, teacher_requested=False,
    )) == (TriggerReason.MICROCYCLE_EXPIRED,)
    assert evaluate_triggers(TriggerInput(
        as_of=day_27, current_label="yellow", current_template_id="YEL-END-NOR-01",
        last_prescription=LastPrescription(
            generated_on=generated, template_id="YEL-END-NOR-01",
            label_at_generation="yellow", microcycle_weeks=4, status="active",
        ),
        latest_assessment_date=None, teacher_requested=False,
    )) == ()
    # 触发 4 只需要 __gt__
    assert evaluate_triggers(TriggerInput(
        as_of=day_27, current_label="yellow", current_template_id="YEL-END-NOR-01",
        last_prescription=LastPrescription(
            generated_on=generated, template_id="YEL-END-NOR-01",
            label_at_generation="yellow", microcycle_weeks=4, status="active",
        ),
        latest_assessment_date=_FakeDate(5), teacher_requested=False,
    )) == (TriggerReason.SEMESTER_DATA_REFRESHED,)


def test_the_insufficient_early_return_reads_the_enum_not_a_second_literal():
    """P6-A6 的行为侧：早退认的是 ``Layer.INSUFFICIENT.value``，不是第二份字面串。

    与 :func:`test_insufficient_label_value_is_pinned_verbatim` 是一对：那一条钉住
    **值**（漂移测试），本条钉住**行为**（那个值真的会让求值短路）。两条都在，
    「单一所有者」才不是一句散文：谁把 ``Layer.INSUFFICIENT`` 的值改成
    ``"insufficient"``，那一条红、本条仍绿（因为它从枚举取值、不写字面串）；
    谁在 ``triggers.py`` 里写第二份 ``"insufficient_data"``，架构守卫与本条都不响，
    但那一条会在 ``Layer`` 改值时暴露出两份不同步。

    ⚠️ **本条守不住什么**（硬规矩 #39）：它抓不到「``triggers.py`` 里硬编码了字面串」
    这件事本身——今天两份恰好相同，故行为无法区分。真正的守卫是
    :mod:`tests.architecture.test_domain_purity`（它只查 import 与 I/O，不查字面串）
    **加**代码评审；本条的价值是把「改 ``Layer`` 会改到本函数的行为」这条因果钉住。
    """
    label = Layer.INSUFFICIENT.value
    assert evaluate_triggers(_inp(label=label, last=None, teacher=True)) == ()
    assert label == "insufficient_data", "上面那一格用的必须是本条字面钉住的那个值"

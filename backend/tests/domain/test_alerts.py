# backend/tests/domain/test_alerts.py
"""spec §8.2 五条预警规则的纯函数核心 :mod:`app.domain.alerts` 的守卫（Plan 03 Task 6）。

预警是「学生练得太苦 → 系统推减量 20%」这条闭环的**闸门**（spec §8.4 的 ``auto`` 来源）。
判据松一档，教师天天收到没人看的红牌、而学生的训练量被连乘下去；判据紧一档，一个连续
三次 RPE 9 分的学生系统一声不响。⚠️ **而这类错误在端到端测试里看不出来**：少触发一条
预警，500 人的分布测试只动几个百分点。故本文件是**全计划唯一要求做变异测试**的地方
（账本 Ruling 1 的裁定），5 条规则的比较符各有一条**边界测试**当靶子（下面用
``[变异靶 Mn]`` 标出）。

**本文件的六条主线**：

1. **``window_key`` 是去重键，它的取值算式必须让「同一次触发只有一条 alert」**
   （Review Focus 第 3 条）。最要紧的一档是 ``RED_RPE_SUSTAINED``：连续第 3、4、5 次快评
   都满足条件时，若 ``window_key`` 取的是**最后一次**快评的 ``class_session_id``，
   三次触发就会得到三个不同的键、插进三行 ``alert``、推三次「减量 20%」，训练量被连乘成
   ``0.8³ = 0.512``。故算式取的是**凑满 streak 那一次**的 id
   （``rpe_session_ids[streak - 1]``），于是 streak 再长键也不变。
   :func:`test_rpe_window_key_is_anchored_at_the_session_that_completed_the_streak` 与
   :func:`test_a_longer_rpe_streak_reuses_the_same_window_key_so_the_dedup_key_holds`
   各钉一半（后者是 Review Focus 第 3 条的正面复现）。
2. **``subject_key`` 的两个前缀住在这里**：``alert`` 表的去重约束是
   ``UniqueConstraint("rule_id", "subject_key", "semester_id", "window_key")``，四列全
   NOT NULL；而 ``app/db/models/feedback.py`` / ``app/api/schemas/alerts.py`` /
   ``tests/db/test_models.py`` **三处**都已写明「那个前缀算式的唯一所有者是
   :mod:`app.domain.alerts`」。⚠️ 计划的 Interfaces 只给了 ``window_key``、没给
   ``subject_key``（实现者顶回后补上），少了它 Task 7 就得在 ``alert_stage`` 里自己拼
   前缀——那正是三处 docstring 点名不许的第二个所有者。
3. **阈值一律从 ``rules`` 读，不写第二份字面量**（Global Constraint #3）：
   :func:`test_the_thresholds_come_from_the_rules_not_from_literals_in_this_module`
   换一套参数（``streak: 4`` / ``mean_rpe_max: 8.0`` / ``gap_days: 3``）再跑一遍，
   行为必须跟着变。少了它，「把 9 硬编码进 domain」这件事全绿。
4. **「没测」不得讲成「测了且没问题」**（Plan 01 Ruling 134 / Plan 02 P5-A3 的同一条纪律）：
   数据点不足时**不触发**，但必须在 :func:`app.domain.alerts.student_skip_traces` /
   :func:`app.domain.alerts.class_skip_traces` 的留痕里说清是「判不了」而不是「没问题」。
   ⚠️ 留痕不能只写在散文里：``points_needed`` 是 ``alert_rules.yaml`` 的一个参数，
   判「够不够点」因此必须在 domain（否则 Task 7 得再读一次那个阈值 = 第二个所有者）。
5. **两个平行元组的契约由 domain 自己校验**：``rpe_session_ids`` 与 ``rpe_streak`` 平行、
   ``mini_test_ids`` 与 ``mini_test_scores`` 同序（P6-A1 的裁定）。``window_key`` 要按下标
   取它们，长度不对时 ``IndexError`` 会出现在 domain 深处、离真因隔三层，故改成响亮的
   ``ValueError``。
6. **``AlertLevel`` 是那三个字符串的所有者，``Alert.LEVELS`` 是它的 DB 镜像**：
   本 Task **不改** ``Alert.LEVELS``（改它会连带 CHECK 约束名与 ``tests/db/test_models.py``），
   改为用一条断言把两者钉成逐字相等
   （:func:`test_alert_level_is_the_owner_and_the_db_check_domain_is_its_mirror`）。

**期望侧一律字面写死**（硬规矩 #35 / Global Constraint #4）：五个 ``RuleId`` 的成员名与
``.value``、三级、两个作用域、8 个阈值、每一种 ``window_key`` / ``subject_key`` 的成品串
都写在本文件里，**不从**被测模块或 ``alert_rules.yaml`` 反推。
:func:`test_the_thresholds_come_from_the_rules_not_from_literals_in_this_module` 用的那套
参数刻意**与真 YAML 不同**，于是它同时是「参数真的被读了」的正面对照。

⚠️ **本文件守不住什么**（硬规矩 #39）：

* **不守「同一次触发在库里只有一行」**：那是 DB 的
  ``uq_alert_rule_subject_semester_window``，守卫在
  ``tests/db/test_models.py::test_alert_dedup_key_…``。本文件钉的是**喂给那个约束的两个键
  的算法**——键算对了，去重才成立；键算错了，约束照样全绿而行照样插得进去。
* **不守 ``alert_rules.yaml`` 的内容**：那是 ``tests/test_refdata_alerts.py`` 的活
  （指纹 + 逐参数字面对账）。本文件的 ``_RULES`` 是**测试自己构造的**，与磁盘上那份
  无关，故「有人把 YAML 里的 9 改成 8」在这里一声不响。
* **不守 ``improve_pct`` 与 ``rpe_min`` 被谁消费**：这两个阈值在 domain 里**不被读**
  （判定发生在 Task 7 算 ``mini_test_improved`` 与 ``rpe_streak`` 的时候）。本文件只钉
  「它们原样出现在 snapshot 里」，钉不住「Task 7 真的用了它们」。
"""
import dataclasses

import pytest

from app.db.models.feedback import Alert
from app.domain.alerts import (
    SUBJECT_PREFIX_SECTION,
    SUBJECT_PREFIX_STUDENT,
    AlertLevel,
    AlertRule,
    AlertRules,
    AlertScope,
    ClassHit,
    ClassSignals,
    RuleId,
    StudentHit,
    StudentSignals,
    class_skip_traces,
    declared_scope,
    evaluate_class,
    evaluate_student,
    student_skip_traces,
)

# ---------------------------------------------------------------------------
# 期望侧的字面量（一律不从被测对象或 alert_rules.yaml 反推，硬规矩 #35）
# ---------------------------------------------------------------------------

#: spec §8.2 表格的**行序**。``RuleId`` 的声明序必须与它逐字相同——落库时
#: ``alert.rule_id`` 与教师端列表的排序都按它读。
_FIVE_IN_SPEC_ORDER = (
    "RED_MINITEST_DROP",
    "RED_RPE_SUSTAINED",
    "YELLOW_CHECKIN_GAP",
    "YELLOW_CLASS_RPE_HIGH",
    "GREEN_MASTERY",
)

#: spec §8.2 的「级别」列（红/黄/绿）与「作用域」列。
_LEVELS_IN_DECLARATION_ORDER = ("RED", "YELLOW", "GREEN")
_LEVEL_VALUES = ("red", "yellow", "green")
_SCOPES_IN_DECLARATION_ORDER = ("STUDENT", "CLASS")
_SCOPE_VALUES = ("student", "class")

#: spec §8.2 的判据表 + 那张「四项均待确认」的口径表，逐条抄成阈值。
#: ⚠️ 这一份是**测试侧的字面量**，与 ``backend/data/alert_rules.yaml``（唯一所有者）
#: 刻意不同源：``tests/test_refdata_alerts.py`` 里另有一份同样字面的对账，
#: 两侧都写死，于是「改坏哪一侧都有人红」（口径同
#: ``refdata_prescription._GUIDANCE_WEEKLY_FREQUENCY`` 与它测试侧那一份的关系）。
_SPEC_PARAMS = {
    "RED_MINITEST_DROP": {"drop_pct": 0.05, "consecutive": 2, "points_needed": 3},
    "RED_RPE_SUSTAINED": {"rpe_min": 9.0, "streak": 3},
    "YELLOW_CHECKIN_GAP": {"gap_days": 2},
    "YELLOW_CLASS_RPE_HIGH": {"mean_rpe_max": 7.0},
    "GREEN_MASTERY": {"completion_rate_min": 1.0, "improve_pct": 0.03},
}
_SPEC_LEVELS = {
    "RED_MINITEST_DROP": "red",
    "RED_RPE_SUSTAINED": "red",
    "YELLOW_CHECKIN_GAP": "yellow",
    "YELLOW_CLASS_RPE_HIGH": "yellow",
    "GREEN_MASTERY": "green",
}
_SPEC_SCOPES = {
    "RED_MINITEST_DROP": "student",
    "RED_RPE_SUSTAINED": "student",
    "YELLOW_CHECKIN_GAP": "student",
    "YELLOW_CLASS_RPE_HIGH": "class",
    "GREEN_MASTERY": "student",
}

#: ``alert`` 表两个去重键列的宽度（``tests/db/test_models.py`` 那一份是从 ORM 现读的，
#: 这一份是字面量，两侧不同源）。
_WINDOW_KEY_COLUMN_WIDTH = 32
_SUBJECT_KEY_COLUMN_WIDTH = 24


def _rules(version: str = "1.0", **param_overrides) -> AlertRules:
    """按 :data:`_SPEC_PARAMS` 造一套规则；``param_overrides`` 逐 ``RuleId`` 名覆盖参数。

    ⚠️ 造的是**测试自己的**那一份，不读磁盘上的 YAML（理由见模块 docstring）。
    """
    store = {}
    for name in _FIVE_IN_SPEC_ORDER:
        rule_id = RuleId(name)
        params = dict(_SPEC_PARAMS[name])
        params.update(param_overrides.get(name, {}))
        store[rule_id] = AlertRule(
            rule_id=rule_id,
            level=AlertLevel(_SPEC_LEVELS[name]),
            scope=AlertScope(_SPEC_SCOPES[name]),
            params=params,
        )
    return AlertRules(version=version, rules=store)


_RULES = _rules()


def _student(**overrides) -> StudentSignals:
    """一个**什么规则都不触发**的学生信号（缺省值刻意全在阈值的安全侧）。"""
    fields = dict(
        student_id=7,
        semester_id=1,
        week=10,
        rpe_streak=0,
        rpe_session_ids=(),
        mini_test_scores=(),
        mini_test_ids=(),
        checkin_gap_days=0,
        checkin_gap_end="2026-10-08",
        completion_rate=None,
        mini_test_improved=False,
    )
    fields.update(overrides)
    return StudentSignals(**fields)


def _klass(**overrides) -> ClassSignals:
    """一个**什么规则都不触发**的班级信号。"""
    fields = dict(
        course_section_id=3,
        semester_id=1,
        week=10,
        mean_rpe=None,
        student_count=0,
    )
    fields.update(overrides)
    return ClassSignals(**fields)


def _only(hits) -> object:
    """断言恰好命中一条并返回它（多于一条时把全部印出来，便于定位）。"""
    assert len(hits) == 1, f"应恰好命中 1 条，实为 {len(hits)} 条：{hits}"
    return hits[0]


# ---------------------------------------------------------------------------
# 闸 1：三个枚举 + 作用域声明（spec §8.2 的三列）
# ---------------------------------------------------------------------------


def test_rule_id_has_exactly_the_five_spec_rules_in_spec_table_order():
    """``RuleId`` 恰好是 spec §8.2 表格的那 5 行，且**声明序 == 表格行序**。

    声明序是承重的：:func:`evaluate_student` / :func:`evaluate_class` 按它排返回 tuple，
    而教师端与 ``alert`` 表的读接口按同一个序渲染。⚠️ 成员名与 ``.value`` **逐字相同**
    （``rule_id`` 列存的就是那个大写串，``String(32)``，最长者
    ``YELLOW_CLASS_RPE_HIGH`` 21 字符）。
    """
    members = list(RuleId)
    assert [member.name for member in members] == list(_FIVE_IN_SPEC_ORDER)
    assert [member.value for member in members] == list(_FIVE_IN_SPEC_ORDER)
    assert len(members) == 5


def test_alert_level_and_alert_scope_have_exactly_the_spec_values_in_order():
    """``AlertLevel`` 三档、``AlertScope`` 两档，声明序与 ``.value`` 都字面钉住。

    两个枚举都继承 ``str``：``alert.level`` 与 ``alert.rule_id`` 是普通字符串列，而
    ``trigger_snapshot`` 是 ``JsonText`` 列——继承 ``str`` 之后 ``json.dumps`` 直接接受它们，
    不必在 ORM 边界上处处翻译（口径同
    :class:`app.domain.prescription.triggers.TriggerReason` 的 docstring）。
    """
    assert [m.name for m in AlertLevel] == list(_LEVELS_IN_DECLARATION_ORDER)
    assert [m.value for m in AlertLevel] == list(_LEVEL_VALUES)
    assert [m.name for m in AlertScope] == list(_SCOPES_IN_DECLARATION_ORDER)
    assert [m.value for m in AlertScope] == list(_SCOPE_VALUES)
    assert isinstance(AlertLevel.RED, str) and isinstance(AlertScope.CLASS, str)


def test_alert_level_is_the_owner_and_the_db_check_domain_is_its_mirror():
    """``AlertLevel`` 是那三个字符串的**所有者**，``Alert.LEVELS`` 是它的 DB 镜像。

    本 Task **刻意不改** ``Alert.LEVELS``：它是 ``_in_domain("level", LEVELS,
    "ck_alert_level")`` 生成 CHECK 约束的输入，改它会连带约束名与
    ``tests/db/test_models.py`` 的几条断言。故改用一条断言把两者钉成逐字相等——
    谁在 domain 里加第四档而忘了同步 DB（或反过来），本条当场红。

    ⚠️ **两侧不同源**（硬规矩 #35）：期望侧是 :data:`_LEVEL_VALUES` 那个字面量，
    实际侧一边是枚举、一边是 ORM 的类常量，三者互不推导。
    """
    assert {level.value for level in AlertLevel} == set(_LEVEL_VALUES)
    assert Alert.LEVELS == set(_LEVEL_VALUES)
    assert Alert.LEVELS == {level.value for level in AlertLevel}, (
        "Alert.LEVELS（DB 的 CHECK 取值域）与 AlertLevel（唯一所有者）漂了："
        f"{sorted(Alert.LEVELS)} vs {sorted(level.value for level in AlertLevel)}。"
        "漂了的后果是静默的：domain 产出一个 level，DB 的 ck_alert_level 当场拒收，"
        "而报错点在 Task 7 的落库那一层、离真因隔两层"
    )


def test_declared_scope_partitions_the_five_rules_as_the_spec_table_says():
    """:func:`declared_scope` 把 5 条规则分成 4 学生 + 1 班级，与 spec §8.2 的「作用域」列一致。

    ⚠️ **它是加载器对账的一侧**：``alert_rules.yaml`` 每条规则也写了一个 ``scope``，
    两者必须一致（``tests/test_refdata_alerts.py`` 的
    ``test_loader_rejects_a_rule_whose_yaml_scope_disagrees_with_the_code``）。
    **代码这一侧是行为**（哪一套 evaluator 处理它：班级级规则拿不到 ``StudentSignals``），
    YAML 那一侧是 spec §8.2 的原文列；两份必须对账，否则专家把 ``scope`` 一翻就变成
    一件**什么也不发生**的事（``scope`` 退化成装饰）。

    ⚠️ 本条同时是「有人加了第 6 个 ``RuleId`` 却忘了接进 dispatch」的守卫：那一档
    ``_EXPECTED`` 里没有它，下面的字典比对会因为多出一个键而红。
    """
    expected = dict(_SPEC_SCOPES)
    assert {rid.value: declared_scope(rid).value for rid in RuleId} == expected


# ---------------------------------------------------------------------------
# 闸 2：``subject_key`` 与 ``window_key`` —— alert 表去重键的两半（Review Focus 第 3 条）
# ---------------------------------------------------------------------------


def test_the_two_subject_key_prefixes_are_pinned_verbatim():
    """两个前缀的字面值。``tests/db/test_models.py::_alert_fields`` 里是现拼的字面量形状
    （``f"student:{stu.id}"``），两侧刻意不同源（那边 docstring 逐字写了这个理由）。"""
    assert SUBJECT_PREFIX_STUDENT == "student"
    assert SUBJECT_PREFIX_SECTION == "section"


def test_student_hits_carry_a_student_subject_key_and_class_hits_a_section_one():
    """学生级命中 → ``student:<id>``；班级级命中 → ``section:<id>``。

    ``subject_key`` 存在的理由是 SQLite 的 UNIQUE 对 NULL 是「NULL ≠ NULL」：
    ``student_id`` 与 ``course_section_id`` 两个可空外键进不了去重键，否则约束对班级级
    预警**静默失效**（``app/db/models/feedback.py`` 模块 docstring 的那一段）。
    """
    student_hit = _only(evaluate_student(
        _student(student_id=42, rpe_streak=3, rpe_session_ids=(11, 12, 13)), _RULES))
    assert student_hit.subject_key == "student:42"
    class_hit = _only(evaluate_class(
        _klass(course_section_id=9, mean_rpe=7.5, student_count=31), _RULES))
    assert class_hit.subject_key == "section:9"


def test_rpe_window_key_is_anchored_at_the_session_that_completed_the_streak():
    """``RED_RPE_SUSTAINED`` 的 ``window_key`` 取**凑满 streak 那一次**的 ``class_session_id``。

    spec 口径表 #1 逐字：「连续 **3 次**课堂快评」，故 ``window_key = f"rpe{第 3 次的 id}"``。
    ⚠️ **不是最后一次的 id**，理由见下一条（那是 Review Focus 第 3 条要防的连乘）。
    """
    hit = _only(evaluate_student(
        _student(rpe_streak=3, rpe_session_ids=(101, 102, 103)), _RULES))
    assert hit.window_key == "rpe103"
    # streak 更长时仍锚在**第 3 个**（下标 streak-1），不是最后一个
    longer = _only(evaluate_student(
        _student(rpe_streak=5, rpe_session_ids=(101, 102, 103, 104, 105)), _RULES))
    assert longer.window_key == "rpe103"


def test_a_longer_rpe_streak_reuses_the_same_window_key_so_the_dedup_key_holds():
    """**Review Focus 第 3 条的正面复现**：streak 3 → 4 → 5 三次求值给出**同一个** ``window_key``。

    于是 ``uq_alert_rule_subject_semester_window`` 把第 2、3 次 INSERT 拒收，
    ``alert`` 只有一行、「减量 20%」只推一次。
    ⚠️ **反面**：若算式取 ``rpe_session_ids[-1]``，三次会得到 ``rpe103`` / ``rpe104`` /
    ``rpe105`` 三个不同的键 → 三行 alert → 三次减量 → 训练量 ``0.8³ = 0.512``，
    而全链路没有一处报错（分布测试只动几个百分点）。
    """
    keys = []
    for streak in (3, 4, 5):
        session_ids = tuple(range(101, 101 + streak))
        hit = _only(evaluate_student(
            _student(rpe_streak=streak, rpe_session_ids=session_ids), _RULES))
        keys.append(hit.window_key)
    assert keys == ["rpe103", "rpe103", "rpe103"], keys
    assert len(set(keys)) == 1, f"去重键随 streak 漂了：{keys}"


def test_minitest_drop_window_key_uses_the_last_mini_test_id():
    """``RED_MINITEST_DROP`` 的 ``window_key`` = ``f"mt{mini_test_ids 最后一项}"``。

    ⚠️ 与 RPE 那条**刻意不同**：小测不是每堂课都有，一次新的小测是一次**新的观测窗口**
    （spec §8.2 口径表 #2「首次可能触发于第 6 周」），故它随最后一次小测前进；
    而快评是每堂课都有的，锚在最后一次会让去重键天天变。
    """
    hit = _only(evaluate_student(
        _student(mini_test_scores=(88.0, 80.0, 70.0), mini_test_ids=(11, 12, 13)),
        _RULES))
    assert hit.window_key == "mt13"


def test_checkin_gap_window_key_uses_the_iso_date_injected_by_the_caller():
    """``YELLOW_CHECKIN_GAP`` 的 ``window_key`` = ``f"gap{中断结束日的 ISO 串}"``。

    ⚠️ **那个 ISO 串由调用方注入**（``StudentSignals.checkin_gap_end``）：
    ``datetime`` 不在 domain 的 allow-list 里
    （``tests/architecture/test_domain_purity.ALLOWED_MODULES`` 实测 =
    ``{collections, collections.abc, dataclasses, enum, numpy, typing}``），
    故 domain 既不 import 它、也不调 ``date.isoformat()``。P6-A4 的裁定就是这个形状。
    """
    hit = _only(evaluate_student(
        _student(checkin_gap_days=2, checkin_gap_end="2026-10-08"), _RULES))
    assert hit.window_key == "gap2026-10-08"


def test_class_and_mastery_window_keys_are_semester_colon_week():
    """``YELLOW_CLASS_RPE_HIGH`` 与 ``GREEN_MASTERY`` 的 ``window_key`` = ``f"{semester_id}:{week}"``。

    这两条的窗口就是**一周**（一个班一周一条、一个学生一周一条「掌握」绿牌），
    故键只由 ``semester_id`` 与 ``week`` 决定。
    ⚠️ **``GREEN_MASTERY`` 是 student 作用域**（``alert_rules.yaml`` 逐字
    ``scope: student``，spec §8.2 的作用域列同），而它的键要 ``semester_id`` / ``week``
    ——计划的 P6-A1 只给 ``ClassSignals`` 补了这两个字段，``StudentSignals`` 上没有，
    于是这条的 ``window_key`` 在 domain 里根本拼不出来（实现者顶回后补上）。
    """
    class_hit = _only(evaluate_class(
        _klass(semester_id=2, week=11, mean_rpe=8.0, student_count=31), _RULES))
    assert class_hit.window_key == "2:11"
    green = _only(evaluate_student(
        _student(semester_id=2, week=11, completion_rate=1.0, mini_test_improved=True),
        _RULES))
    assert green.window_key == "2:11"


def test_both_dedup_keys_fit_their_db_columns():
    """两个键都塞得进 ``alert`` 的列宽（``window_key String(32)`` / ``subject_key String(24)``）。

    取**最长的现实形状**：id 用到 ``2147483647``（10 位，``tests/db/test_models.py``
    钉 ``subject_key`` 余量时用的同一个数）。超宽不会报错——SQLite 不强制 ``VARCHAR``
    长度——而是**静默**让去重键变成一个谁也读不懂的长串，故这里钉一下。
    """
    hit = _only(evaluate_student(
        _student(student_id=2147483647, rpe_streak=3,
                 rpe_session_ids=(1, 2, 2147483647)), _RULES))
    assert len(hit.subject_key) <= _SUBJECT_KEY_COLUMN_WIDTH, hit.subject_key
    assert len(hit.window_key) <= _WINDOW_KEY_COLUMN_WIDTH, hit.window_key
    gap = _only(evaluate_student(
        _student(checkin_gap_days=2, checkin_gap_end="2026-10-08"), _RULES))
    assert len(gap.window_key) <= _WINDOW_KEY_COLUMN_WIDTH
    klass = _only(evaluate_class(
        _klass(course_section_id=2147483647, semester_id=2147483647, week=16,
               mean_rpe=8.0, student_count=1), _RULES))
    assert len(klass.subject_key) <= _SUBJECT_KEY_COLUMN_WIDTH, klass.subject_key
    assert len(klass.window_key) <= _WINDOW_KEY_COLUMN_WIDTH, klass.window_key


# ---------------------------------------------------------------------------
# 闸 3：五条判据的边界（``[变异靶 Mn]`` = 变异测试的靶子）
# ---------------------------------------------------------------------------


def test_minitest_drop_fires_on_two_consecutive_five_percent_drops():
    """spec §8.2 口径表 #2：``score(t) < score(t-1) × 0.95`` **且**
    ``score(t-1) < score(t-2) × 0.95``（需 3 个数据点）。"""
    hit = _only(evaluate_student(
        _student(mini_test_scores=(88.0, 80.0, 70.0), mini_test_ids=(11, 12, 13)),
        _RULES))
    assert hit.rule_id is RuleId.RED_MINITEST_DROP
    assert hit.level is AlertLevel.RED
    assert hit.snapshot["mini_test_scores"] == [88.0, 80.0, 70.0]


def test_minitest_drop_is_strict_at_exactly_five_percent():  # [变异靶 M1]
    """**恰好**下降 5% 不算下降（严格 ``<``）。

    ``80.0 × 0.95 == 76.0``，故 ``(80.0, 76.0)`` 这一对**不触发**。口径与 Plan 01 的 P25、
    Plan 02 的 ``BODY_FAT_LIMIT`` / ``bmi > 30`` / ``muscle < P10`` 一致。
    ⚠️ **变异 M1** 把 ``alerts.py`` 里那句 ``newer >= older * factor`` 改成 ``>``
    （= 把 spec 的 ``<`` 改成 ``<=``），本条应当红、而上一条与下面那条保持绿。
    """
    assert evaluate_student(
        _student(mini_test_scores=(88.0, 80.0, 76.0), mini_test_ids=(11, 12, 13)),
        _RULES) == ()
    # 反面对照：差一点点（75.9 < 76.0）就触发，证明上一条红的原因是「恰好 5%」而不是别的
    assert len(evaluate_student(
        _student(mini_test_scores=(88.0, 80.0, 75.9), mini_test_ids=(11, 12, 13)),
        _RULES)) == 1


def test_minitest_drop_only_reads_the_last_consecutive_plus_one_scores():
    """只看**最后** ``consecutive + 1`` 个数据点：更早的下降不算，更近的回升能把它取消。"""
    # 更早那两次下降（88→80→70）不算数，最后两个点 (70, 69) 没有下降 → 不触发
    assert evaluate_student(
        _student(mini_test_scores=(88.0, 80.0, 70.0, 69.0),
                 mini_test_ids=(11, 12, 13, 14)),
        _RULES) == ()
    # 四个点里最后三个 (88, 80, 70) 连续下降 → 触发，且 window_key 锚在最后一个 id
    hit = _only(evaluate_student(
        _student(mini_test_scores=(60.0, 88.0, 80.0, 70.0),
                 mini_test_ids=(10, 11, 12, 13)),
        _RULES))
    assert hit.window_key == "mt13"


def test_minitest_drop_leaves_a_trace_instead_of_firing_when_points_are_short():
    """数据点不足 ``points_needed`` → **不触发 + 留痕**（「没测」不得讲成「测了且没问题」）。

    ⚠️ 缺省信号里 ``completion_rate`` 也是 ``None``，故 ``GREEN_MASTERY`` 同时留一条痕
    ——两条痕互不掩盖，这正是留痕的意义（「判不了」要逐条说清是哪一条判不了）。
    """
    sig = _student(mini_test_scores=(88.0, 70.0), mini_test_ids=(11, 12),
                   completion_rate=1.0)
    assert evaluate_student(sig, _RULES) == ()
    traces = student_skip_traces(sig, _RULES)
    assert traces == {
        RuleId.RED_MINITEST_DROP: {"insufficient_points": 2, "points_needed": 3},
    }
    # 0 个点同样留痕（一个从没测过的学生 ≠ 一个测了没下降的学生）
    assert student_skip_traces(_student(), _RULES) == {
        RuleId.RED_MINITEST_DROP: {"insufficient_points": 0, "points_needed": 3},
        RuleId.GREEN_MASTERY: {"missing": "completion_rate",
                               "completion_rate_min": 1.0},
    }
    # 点数够了就没有留痕
    assert student_skip_traces(
        _student(mini_test_scores=(88.0, 80.0, 70.0), mini_test_ids=(11, 12, 13),
                 completion_rate=1.0),
        _RULES) == {}


def test_rpe_sustained_fires_at_exactly_the_streak_threshold():  # [变异靶 M2]
    """``rpe_streak >= 3`` 就触发——**第 3 次当天**触发，``>=`` 不是 ``>``。

    ⚠️ **变异 M2** 把 ``alerts.py`` 里的 ``>=`` 改成 ``>``，本条应当红
    （``rpe_streak == 3`` 那一格），而 ``rpe_streak == 4`` 那一格保持绿。
    """
    hit = _only(evaluate_student(
        _student(rpe_streak=3, rpe_session_ids=(101, 102, 103)), _RULES))
    assert hit.rule_id is RuleId.RED_RPE_SUSTAINED
    assert hit.level is AlertLevel.RED
    assert hit.snapshot == {"rpe_streak": 3, "rpe_min": 9.0, "streak": 3}
    # 4 次也触发（上面那条窗口的稳定性由 window_key 那两条钉）
    assert len(evaluate_student(
        _student(rpe_streak=4, rpe_session_ids=(101, 102, 103, 104)), _RULES)) == 1


def test_rpe_sustained_does_not_fire_below_the_streak_threshold():
    """``rpe_streak == 2`` 不触发（差一次）。"""
    assert evaluate_student(
        _student(rpe_streak=2, rpe_session_ids=(101, 102)), _RULES) == ()
    assert evaluate_student(_student(), _RULES) == ()


def test_checkin_gap_fires_at_exactly_the_gap_threshold():  # [变异靶 M3]
    """``checkin_gap_days >= 2`` 就触发——**第 2 天**触发，``>=`` 不是 ``>``。

    spec §8.2 口径表 #3：「连续 **2 个应打卡训练日**未打卡（**休息日不计入中断**）」。
    ⚠️ **变异 M3** 把 ``>=`` 改成 ``>``，本条应当红。
    """
    hit = _only(evaluate_student(
        _student(checkin_gap_days=2, checkin_gap_end="2026-10-08"), _RULES))
    assert hit.rule_id is RuleId.YELLOW_CHECKIN_GAP
    assert hit.level is AlertLevel.YELLOW
    assert hit.snapshot == {"checkin_gap_days": 2, "gap_days": 2}


def test_checkin_gap_does_not_fire_after_a_single_missed_training_day():
    """中断 1 个应打卡训练日不触发（差一天）。"""
    assert evaluate_student(
        _student(checkin_gap_days=1, checkin_gap_end="2026-10-08"), _RULES) == ()


def test_class_rpe_high_is_strict_at_exactly_seven():  # [变异靶 M4]
    """课堂 RPE 均值 **> 7** 才触发——恰好 7.0 **不**触发（spec 逐字「> 7」）。

    ⚠️ **变异 M4** 把 ``alerts.py`` 里的 ``>`` 改成 ``>=``，本条应当红
    （``mean_rpe == 7.0`` 那一格），而 ``7.1`` 那一格保持绿。
    """
    assert evaluate_class(_klass(mean_rpe=7.0, student_count=31), _RULES) == ()
    hit = _only(evaluate_class(_klass(mean_rpe=7.1, student_count=31), _RULES))
    assert hit.rule_id is RuleId.YELLOW_CLASS_RPE_HIGH
    assert hit.level is AlertLevel.YELLOW
    assert hit.snapshot == {"mean_rpe": 7.1, "student_count": 31, "mean_rpe_max": 7.0}


def test_class_rpe_high_leaves_a_trace_when_no_one_submitted_rpe_this_week():
    """``mean_rpe is None``（本周一次快评都没有）→ **不触发 + 留痕**。"""
    sig = _klass(mean_rpe=None, student_count=31)
    assert evaluate_class(sig, _RULES) == ()
    assert class_skip_traces(sig, _RULES) == {
        RuleId.YELLOW_CLASS_RPE_HIGH: {
            "insufficient_points": 0, "mean_rpe_max": 7.0, "student_count": 31,
        },
    }
    assert class_skip_traces(_klass(mean_rpe=6.0, student_count=31), _RULES) == {}


def test_mastery_fires_at_exactly_full_completion():  # [变异靶 M5]
    """完成度 **100%** 且小测有提升 → 绿牌。

    ⚠️ **判据写 ``>=`` 而不是计划正文的 ``==``**（实现者顶回，理由三条，逐字写在
    :func:`app.domain.alerts.evaluate_student` 的 docstring 里）：① YAML 的参数名逐字是
    ``completion_rate_min``——一个叫 ``_min`` 的阈值被 ``==`` 消费是自相矛盾的；
    ② ``completion_rate`` 是「打卡数 ÷ 应打卡数」，值域 ``[0, 1]``，故 ``>= 1.0`` 与
    ``== 1.0`` 对**任何合法输入**逐格等价，spec 的「100%」没有被放宽；
    ③ 写成 ``==`` 会让本 Task 唯一要求的变异测试**没有靶子**——``==`` → ``>=``
    在值域 ``[0, 1]`` 上不可分辨，任何测试都不会红。
    ⚠️ **变异 M5** 把 ``>=`` 改成 ``>``，本条应当红（``completion_rate == 1.0`` 那一格）。
    """
    hit = _only(evaluate_student(
        _student(completion_rate=1.0, mini_test_improved=True), _RULES))
    assert hit.rule_id is RuleId.GREEN_MASTERY
    assert hit.level is AlertLevel.GREEN
    assert hit.snapshot == {"completion_rate": 1.0, "mini_test_improved": True,
                            "completion_rate_min": 1.0, "improve_pct": 0.03}


def test_mastery_needs_both_halves_of_the_conjunction():
    """**AND** 的两半各缺一半都不触发（完成度 99% / 小测没提升）。"""
    assert evaluate_student(
        _student(completion_rate=0.99, mini_test_improved=True), _RULES) == ()
    assert evaluate_student(
        _student(completion_rate=1.0, mini_test_improved=False), _RULES) == ()


def test_mastery_leaves_a_trace_when_the_completion_rate_is_missing():
    """``completion_rate is None`` → **不触发 + 留痕**（同一条纪律）。

    ⚠️ 计划的判据表对这一档只写了「不触发」、没写留痕，而它对 ``RED_MINITEST_DROP`` 与
    ``YELLOW_CLASS_RPE_HIGH`` 都写了。三档是同一件事（**判不了**，不是**没问题**），
    故一律留痕——一个本周没有应打卡训练日的学生与一个天天打卡的学生，在教师端不该
    看起来一样。
    """
    sig = _student(completion_rate=None, mini_test_improved=True)
    assert evaluate_student(sig, _RULES) == ()
    assert student_skip_traces(sig, _RULES)[RuleId.GREEN_MASTERY] == {
        "missing": "completion_rate", "completion_rate_min": 1.0,
    }


# ---------------------------------------------------------------------------
# 闸 4：阈值真的来自 ``rules``（Global Constraint #3 的正面验证）
# ---------------------------------------------------------------------------


def test_the_thresholds_come_from_the_rules_not_from_literals_in_this_module():
    """换一套阈值，行为必须跟着变——证明 domain 里没有第二份字面量。

    ⚠️ 这一套参数**刻意与真 YAML 不同**（``streak`` 3→4、``gap_days`` 2→3、
    ``mean_rpe_max`` 7.0→8.0、``drop_pct`` 0.05→0.10、``completion_rate_min`` 1.0→0.9），
    于是「把 9 / 3 / 2 / 7.0 / 0.95 / 1.0 硬编码进 ``alerts.py``」这件事**每一条都红**。
    """
    loose = _rules(
        RED_MINITEST_DROP={"drop_pct": 0.10},
        RED_RPE_SUSTAINED={"streak": 4},
        YELLOW_CHECKIN_GAP={"gap_days": 3},
        YELLOW_CLASS_RPE_HIGH={"mean_rpe_max": 8.0},
        GREEN_MASTERY={"completion_rate_min": 0.9},
    )
    # streak 3 在真阈值下触发，在 streak=4 下不触发
    three = _student(rpe_streak=3, rpe_session_ids=(101, 102, 103))
    assert len(evaluate_student(three, _RULES)) == 1
    assert evaluate_student(three, loose) == ()
    four = _student(rpe_streak=4, rpe_session_ids=(101, 102, 103, 104))
    hit = _only(evaluate_student(four, loose))
    assert hit.window_key == "rpe104", "window_key 要跟着新的 streak 阈值走"
    # 中断 2 天在真阈值下触发，在 gap_days=3 下不触发
    two_days = _student(checkin_gap_days=2, checkin_gap_end="2026-10-08")
    assert len(evaluate_student(two_days, _RULES)) == 1
    assert evaluate_student(two_days, loose) == ()
    # 恰好下降 5% 在真阈值下不触发，在 drop_pct=0.10 下更不触发；下降 8% 只在宽松版触发
    five_pct = _student(mini_test_scores=(100.0, 95.0, 90.25), mini_test_ids=(1, 2, 3))
    assert evaluate_student(five_pct, _RULES) == ()
    assert evaluate_student(five_pct, loose) == ()
    eight_pct = _student(mini_test_scores=(100.0, 92.0, 84.0), mini_test_ids=(1, 2, 3))
    assert len(evaluate_student(eight_pct, _RULES)) == 1
    assert evaluate_student(eight_pct, loose) == ()
    # 班级均值 7.5 在真阈值下触发，在 mean_rpe_max=8.0 下不触发
    assert len(evaluate_class(_klass(mean_rpe=7.5, student_count=31), _RULES)) == 1
    assert evaluate_class(_klass(mean_rpe=7.5, student_count=31), loose) == ()
    # 完成度 0.95 在真阈值（1.0）下不触发，在 0.9 下触发
    partial = _student(completion_rate=0.95, mini_test_improved=True)
    assert evaluate_student(partial, _RULES) == ()
    assert len(evaluate_student(partial, loose)) == 1


def test_params_of_returns_the_rules_own_params():
    """:meth:`AlertRules.params_of` 返回那一条规则自己的阈值映射（``rules`` 的只读视图）。"""
    assert _RULES.params_of(RuleId.RED_RPE_SUSTAINED) == {"rpe_min": 9.0, "streak": 3}
    assert _RULES.params_of(RuleId.YELLOW_CHECKIN_GAP) == {"gap_days": 2}
    assert _RULES.version == "1.0"


# ---------------------------------------------------------------------------
# 闸 5：两个平行元组的契约（P6-A1）与纯函数性质
# ---------------------------------------------------------------------------


def test_rpe_session_ids_must_be_parallel_to_rpe_streak():
    """``len(rpe_session_ids) != rpe_streak`` → 响亮的 ``ValueError``，不是深处的 ``IndexError``。

    ``window_key`` 要按 ``[streak - 1]`` 取那个 id，长度不对时朴素实现会抛
    ``IndexError``——它点不出是哪个字段不对、也说不出这是调用方的契约违例。
    """
    with pytest.raises(ValueError, match="rpe_session_ids"):
        evaluate_student(_student(rpe_streak=3, rpe_session_ids=(101, 102)), _RULES)
    with pytest.raises(ValueError, match="rpe_session_ids"):
        evaluate_student(_student(rpe_streak=1, rpe_session_ids=(101, 102)), _RULES)


def test_mini_test_ids_must_be_the_same_length_as_the_scores():
    """``mini_test_ids`` 与 ``mini_test_scores`` 必须**同序等长**（P6-A1 的裁定）。"""
    with pytest.raises(ValueError, match="mini_test_ids"):
        evaluate_student(
            _student(mini_test_scores=(88.0, 80.0, 70.0), mini_test_ids=(11, 12)),
            _RULES)


def test_a_clean_student_and_a_clean_class_produce_nothing():
    """缺省信号（一切都在阈值的安全侧）→ 两个求值器都返回**空 tuple**（不是 ``None``）。

    空 tuple 让调用方只需一条读法（``if evaluate_student(sig, rules):``），
    不必分出 ``is not None`` 与「非空」两种语义（口径同
    :func:`app.domain.prescription.triggers.evaluate_triggers`）。
    """
    assert evaluate_student(_student(), _RULES) == ()
    assert evaluate_class(_klass(), _RULES) == ()


def test_a_student_can_hit_several_rules_at_once_in_declaration_order():
    """一个学生同时命中 3 条 → 返回 3 条，且**按 ``RuleId`` 的声明序**（== spec §8.2 行序）。

    ⚠️ 顺序是承重的：Task 7 按它落库，教师端按它渲染；一个随 dict 迭代序漂的顺序会让
    「同一个学生今天为什么收到这三条」在两次运行里读出两个答案。
    """
    sig = _student(
        semester_id=1, week=10,
        rpe_streak=3, rpe_session_ids=(101, 102, 103),
        mini_test_scores=(88.0, 80.0, 70.0), mini_test_ids=(11, 12, 13),
        checkin_gap_days=2, checkin_gap_end="2026-10-08",
        completion_rate=1.0, mini_test_improved=True,
    )
    hits = evaluate_student(sig, _RULES)
    assert [hit.rule_id.value for hit in hits] == [
        "RED_MINITEST_DROP", "RED_RPE_SUSTAINED", "YELLOW_CHECKIN_GAP", "GREEN_MASTERY",
    ]
    assert [hit.level.value for hit in hits] == ["red", "red", "yellow", "green"]
    assert all(isinstance(hit, StudentHit) for hit in hits)


def test_evaluate_class_only_runs_class_scoped_rules():
    """``evaluate_class`` 只跑班级级规则：一个均值爆表的班不会顺带产出学生级的命中。"""
    hits = evaluate_class(
        _klass(mean_rpe=9.5, student_count=31, semester_id=1, week=10), _RULES)
    assert [hit.rule_id.value for hit in hits] == ["YELLOW_CLASS_RPE_HIGH"]
    assert all(isinstance(hit, ClassHit) for hit in hits)


def test_the_two_evaluators_never_mix_scopes():
    """学生级求值器**不会**产出班级级规则，反之亦然（两个 ``Hit`` 类型也不混）。

    ⚠️ 这一条是 :func:`test_declared_scope_partitions_the_five_rules_as_the_spec_table_says`
    的行为侧对读：那一条钉的是**声明**，本条钉的是**行为**。
    """
    everything_student = _student(
        rpe_streak=9, rpe_session_ids=tuple(range(1, 10)),
        mini_test_scores=(99.0, 80.0, 60.0), mini_test_ids=(1, 2, 3),
        checkin_gap_days=9, checkin_gap_end="2026-10-08",
        completion_rate=1.0, mini_test_improved=True,
    )
    student_ids = {hit.rule_id for hit in evaluate_student(everything_student, _RULES)}
    assert RuleId.YELLOW_CLASS_RPE_HIGH not in student_ids
    assert student_ids == {
        RuleId.RED_MINITEST_DROP, RuleId.RED_RPE_SUSTAINED,
        RuleId.YELLOW_CHECKIN_GAP, RuleId.GREEN_MASTERY,
    }
    class_ids = {
        hit.rule_id
        for hit in evaluate_class(_klass(mean_rpe=10.0, student_count=1), _RULES)
    }
    assert class_ids == {RuleId.YELLOW_CLASS_RPE_HIGH}


def test_evaluate_is_deterministic_and_does_not_mutate_its_input():
    """纯函数：同一输入两次求值给出相等的结果，且**不改**入参（frozen dataclass）。

    ⚠️ ``snapshot`` 是一个 ``dict``（``JsonText`` 列要的就是它），故它**不是** frozen 的；
    本条钉的是「两次求值给出两个**相等但不共享**的 dict」——共享的话 Task 7 往一条
    alert 的 snapshot 里补一个键会连带改掉另一条。
    """
    sig = _student(rpe_streak=3, rpe_session_ids=(101, 102, 103))
    first = evaluate_student(sig, _RULES)
    second = evaluate_student(sig, _RULES)
    assert first == second
    assert first[0].snapshot == second[0].snapshot
    assert first[0].snapshot is not second[0].snapshot
    with pytest.raises(dataclasses.FrozenInstanceError):
        sig.rpe_streak = 99  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        _klass().mean_rpe = 9.9  # type: ignore[misc]


def test_the_signal_dataclasses_have_exactly_the_fields_the_rules_need():
    """两个信号类型的字段清单（运行时口径，硬规矩 #89：``dataclasses.fields``，不数源码）。

    ⚠️ **每一个字段都要有消费者**（硬规矩 #110：定义一个纯函数的输出结构时，逐字段回问
    「这个值从哪个入参来」——反过来问就是「这个入参被谁读」）：

    ==========================  ==========================================================
    字段                        谁读它
    ==========================  ==========================================================
    ``student_id``              ``subject_key``
    ``semester_id`` / ``week``  ``GREEN_MASTERY`` 的 ``window_key``
    ``rpe_streak``              ``RED_RPE_SUSTAINED`` 的判据
    ``rpe_session_ids``         ``RED_RPE_SUSTAINED`` 的 ``window_key``
    ``mini_test_scores``        ``RED_MINITEST_DROP`` 的判据
    ``mini_test_ids``           ``RED_MINITEST_DROP`` 的 ``window_key``
    ``checkin_gap_days``        ``YELLOW_CHECKIN_GAP`` 的判据
    ``checkin_gap_end``         ``YELLOW_CHECKIN_GAP`` 的 ``window_key``
    ``completion_rate``         ``GREEN_MASTERY`` 的判据
    ``mini_test_improved``      ``GREEN_MASTERY`` 的判据
    ``course_section_id``       ``subject_key``（班级级）
    ``mean_rpe``                ``YELLOW_CLASS_RPE_HIGH`` 的判据
    ``student_count``           ``YELLOW_CLASS_RPE_HIGH`` 的 snapshot（不是判据）
    ==========================  ==========================================================
    """
    assert [f.name for f in dataclasses.fields(StudentSignals)] == [
        "student_id", "semester_id", "week",
        "rpe_streak", "rpe_session_ids",
        "mini_test_scores", "mini_test_ids",
        "checkin_gap_days", "checkin_gap_end",
        "completion_rate", "mini_test_improved",
    ]
    assert [f.name for f in dataclasses.fields(ClassSignals)] == [
        "course_section_id", "semester_id", "week", "mean_rpe", "student_count",
    ]
    assert [f.name for f in dataclasses.fields(StudentHit)] == [
        "rule_id", "level", "subject_key", "window_key", "snapshot",
    ]
    assert [f.name for f in dataclasses.fields(ClassHit)] == [
        "rule_id", "level", "subject_key", "window_key", "snapshot",
    ]
    assert [f.name for f in dataclasses.fields(AlertRule)] == [
        "rule_id", "level", "scope", "params",
    ]
    assert [f.name for f in dataclasses.fields(AlertRules)] == ["version", "rules"]
    assert len(dataclasses.fields(StudentSignals)) == 11
    assert len(dataclasses.fields(ClassSignals)) == 5

"""预警阈值 ``backend/data/alert_rules.yaml`` 的加载与校验（Plan 03 Task 6）。

**分层照 Plan 02 的既有做法**（账本 Ruling 96：**值类型住 domain、加载器住 domain 外、
加载器 import 值类型**）：``AlertLevel`` / ``RuleId`` / ``AlertScope`` / ``AlertRule`` /
``AlertRules`` 五个值类型住 :mod:`app.domain.alerts`，本模块只负责**读盘 + 校验 +
组装**，一个判据都不写在这里。理由与 :mod:`app.refdata_prescription` 逐字相同：
``tests/architecture/test_domain_purity.py`` 的 allow-list 只放行 6 个标准库模块串与
``app.domain`` 前缀，**不放行 domain → 非 domain 的 import**，故值对象若住在这里，
Task 7 的 ``app/pipeline/alert_stage.py`` 就拿不到它们做标注。

**本文件不入库**（spec §4.4 :243 逐字：「``alert_rules``（预警阈值）为 ``data/`` 下的
**静态 YAML + 版本号**，不入库……改阈值应走版本控制与评审，不应在运行时改数据库」）。
故本模块**没有** ``sync_*`` 投影入口（那是 :mod:`app.refdata_prescription` 为
``exercise`` / ``prescription_template`` 两张表准备的），也**不 import** ``app.db``。

--------------------------------------------------------------------------

**报错口径：文件名 + 行号 + 键路径**（Review Focus 第 5 条）。``alert_rules.yaml`` 是全
系统**唯一**直接决定「给哪个学生推减量 20%」的一份数据，而它由体育专家手工维护；一个
改坏的阈值必须在**加载期**炸，而不是在某个学生触发预警时才炸——后者离真因隔三层，
且在端到端测试里只让 500 人的分布动几个百分点（账本 Ruling 1 因此把本 Task 定为全计划
唯一要求变异测试的地方）。

那套机制（:func:`app.refdata_yaml.line_index` / :func:`~app.refdata_yaml.fail` /
:func:`~app.refdata_yaml.exact_keys` / ``as_int`` / ``as_float``）**与
:mod:`app.refdata_prescription` 共用一个所有者**（P6-A2：计划原文写「直接照抄那套形状」，
而「照抄」在字面上等于复制、复制就是第二个所有者）。本模块只留 5 个**薄适配器**
（:func:`_fail` / :func:`_exact_keys` / :func:`_as_int` / :func:`_as_float` /
:func:`_as_optional_text`，各一句「转发 + 绑 :data:`_DOC_KIND`）与一个别名
:data:`_line_index`。守卫是 ``tests/test_refdata_alerts.py`` 的闸 A（AST 钉「6 个名字各只有
一处定义」与「适配器只转发」，另加身份比对）。

⚠️ :func:`_as_optional_text` 今天**没有调用者**：``alert_rules.yaml`` 里没有可空文本字段
（``level`` / ``scope`` 走枚举，**9** 个阈值全是数——逐条 3 / 2 / 1 / 1 / 2；⚠️ 本处此前印的是「8 个」，Plan 03 的计划正文与派单一路跟着写 8，而 ``data/alert_rules.yaml`` 实测是 **9** 个，Plan 03 Task 9 用运行时口径更正）。保留它是为了与另一个消费者的适配器
清单**逐字同形**——那 5 个名字是 :mod:`app.refdata_yaml` 的公开面，两个消费者各绑一次
``doc_kind``，于是「共用模块加了第 7 个助手」时两边要改的是同一张清单。
⚠️ 它同时是 ``tests/test_refdata_alerts.py`` 支 A2 的一个反面对照：那一支要求**每个**
适配器都只转发，一个没有调用者的适配器同样被钉住，故「先复制一份进来备用」这条路是堵死的。

⚠️ **它守不住什么**（硬规矩 #39）：

* **不校验阈值的「对不对」，只校验「可不可能」**：``mean_rpe_max: 3.0`` 会被照收
  （它是个合法的数、在合法的类型里），而它会让每个班每周都吃一张黄牌。
  「这个数合不合理」是体育专家的评审职责，不是加载器的（spec §4.4 那句「走版本控制与
  评审」说的就是这件事）。加载器只拦**语义上不可能**的三档：比率不在 ``(0, 1)``、
  计数 ``< 1``、``points_needed != consecutive + 1``（逐条理由见 :func:`_check_bounds`
  与 :func:`_check_cross`）。
* **不校验 RPE 的值域 0–10**：Global Constraints 逐字写「**RPE 的值域 0–10 的唯一所有者
  是 spec §8.2**，Plan 02 已把它写进 ``assembler.py`` 的 docstring 与 ``INTENSITY_TYPES``
  的 ``rpe`` 档；**不要在本计划里写第三份**」。故 ``rpe_min`` 与 ``mean_rpe_max`` 只做
  「是个数」的校验，不做「在 0–10 内」的校验。
* **不校验 ``version`` 与 ``RuleId`` 的关系**：加了第 6 条规则而 ``version`` 仍是
  ``"1.0"`` 会被照收。版本号是给**人**读的（Task 7 把它写进 ``weekly_adjustment`` 的
  留痕，于是一张已减量的训练单能回答「当时按哪一版阈值判的」），自动升号会让
  「改阈值要评审」这件事看起来像一次自动手续。
"""
import pathlib
import types

import yaml

from app import refdata_yaml
from app.domain.alerts import (
    AlertLevel,
    AlertRule,
    AlertRules,
    AlertScope,
    RuleId,
    declared_scope,
)
from app.refdata import DATA_DIR

#: 预警阈值 YAML 的**文件名**（``DATA_DIR / ALERT_RULES_FILENAME``）。
#: ⚠️ 本常量是这个文件名的**唯一所有者**：``tests/test_refdata_alerts.py`` 的
#: ``test_the_filename_constant_is_the_only_owner_of_the_yaml_name`` 用 AST 扫
#: ``backend/app/`` 下全部 ``.py`` 的 ``ast.Constant``，要求**逐字等于**那个串的常量
#: 只出现在本模块里。⚠️ 判据是**相等**而不是「包含」，故 docstring 里提一提
#: （例如本模块 docstring 的首行）不构成第二个住址——散文里的一个词不是常量。
ALERT_RULES_FILENAME = "alert_rules.yaml"

#: 绑进 :func:`app.refdata_yaml.fail` 的**文档种类**（报错前缀）。
#: ⚠️ 另一个消费者绑的是 ``"处方模板"``；两个措辞由
#: ``tests/test_refdata_alerts.py`` 的 ``test_doc_kind_is_bound_per_consumer_and_has_no_default``
#: 各钉一份。
_DOC_KIND = "预警规则"

#: 顶层必需的键，恰好这两个（多一个少一个都在加载时响亮失败）。
_TOP_KEYS = ("version", "rules")

#: 每条规则必需的键，恰好这三个（spec §8.2 的「级别」/「作用域」两列 + 阈值）。
_RULE_KEYS = ("level", "scope", "params")

#: 每条规则的 ``params`` 键集与**类型**。``int`` = 计数，``float`` = 测量值/比率。
#: ⚠️ 这张表是「哪条规则有哪几个阈值」的**唯一所有者**（YAML 是**值**的所有者，
#: 本表是**键集与类型**的所有者）——与 ``refdata_prescription._TEMPLATE_KEYS`` 对
#: 18 套模板的关系同构。
#: ⚠️ ``streak`` / ``consecutive`` / ``points_needed`` / ``gap_days`` 必须是 ``int``：
#: ``streak`` 会被 :func:`app.domain.alerts.evaluate_student` 当成**下标**用
#: （``window_key`` 取 ``rpe_session_ids[streak - 1]``），一个 ``3.0`` 会在那一步抛
#: ``TypeError: list indices must be integers``——报错点在 domain 深处、离「YAML 里
#: 写错了一个数」隔三层，故在加载期就拦。
_PARAM_TYPES: dict[RuleId, tuple[tuple[str, type], ...]] = {
    RuleId.RED_MINITEST_DROP: (
        ("drop_pct", float), ("consecutive", int), ("points_needed", int),
    ),
    RuleId.RED_RPE_SUSTAINED: (("rpe_min", float), ("streak", int)),
    RuleId.YELLOW_CHECKIN_GAP: (("gap_days", int),),
    RuleId.YELLOW_CLASS_RPE_HIGH: (("mean_rpe_max", float),),
    RuleId.GREEN_MASTERY: (("completion_rate_min", float), ("improve_pct", float)),
}

#: 比率类参数（**开区间** ``(0.0, 1.0)``）：一个「下降百分比」或「改善百分比」写成
#: ``5.0``（把「5%」当成 5）是最常见的坏形状，而它**静默**——见 :func:`_check_bounds`。
_RATIO_PARAMS = frozenset({"drop_pct", "improve_pct"})

#: 计数类参数（``>= 1``）。``0`` 会让判据恒真，见 :func:`_check_bounds`。
_COUNT_PARAMS = frozenset({"consecutive", "points_needed", "streak", "gap_days"})

_line_index = refdata_yaml.line_index

_alerts_cache: AlertRules | None = None


def _fail(path, lines, key_path, message) -> ValueError:
    """**薄适配器**：转发给 :func:`app.refdata_yaml.fail` 并绑上本模块的 :data:`_DOC_KIND`。

    ⚠️ 本函数除本 docstring 外只许有那一句（守卫见模块 docstring）。``key_path`` /
    ``lines`` / ``message`` 的语义逐字见 :func:`app.refdata_yaml.fail`。
    """
    return refdata_yaml.fail(path, lines, key_path, message, doc_kind=_DOC_KIND)


def _exact_keys(path, lines, where, raw, required, label) -> None:
    """薄适配器；理由与「只许一句」的守卫逐字见 :func:`_fail` 的 docstring。"""
    refdata_yaml.exact_keys(path, lines, where, raw, required, label,
                            doc_kind=_DOC_KIND)


def _as_int(path, lines, where, raw, label) -> int:
    """薄适配器；理由与「只许一句」的守卫逐字见 :func:`_fail` 的 docstring。"""
    return refdata_yaml.as_int(path, lines, where, raw, label, doc_kind=_DOC_KIND)


def _as_float(path, lines, where, raw, label) -> float:
    """薄适配器；理由与「只许一句」的守卫逐字见 :func:`_fail` 的 docstring。"""
    return refdata_yaml.as_float(path, lines, where, raw, label, doc_kind=_DOC_KIND)


def _as_optional_text(path, lines, where, raw, label) -> str | None:
    """薄适配器；理由与「只许一句」的守卫逐字见 :func:`_fail` 的 docstring。

    ⚠️ **今天没有调用者**，保留的理由逐字见模块 docstring 那一段。
    """
    return refdata_yaml.as_optional_text(path, lines, where, raw, label,
                                         doc_kind=_DOC_KIND)


def _check_bounds(path, lines, where, name: str, value: float | int) -> None:
    """校验一个阈值的**取值范围**（「语义上不可能」的三档），违例带文件名 + 行号响亮失败。

    三档各是一种**静默失效**，故必须在加载期拦（Review Focus 第 5 条）：

    * **比率不在 ``(0.0, 1.0)``**（:data:`_RATIO_PARAMS`）——``drop_pct: 5.0``
      （把「5%」写成 5.0）会让判据里的 ``1 - 5.0 = -4.0``，于是
      ``newer >= older × -4.0`` 对任何正分数都成立 → **``RED_MINITEST_DROP`` 永不触发**；
      ``improve_pct: 0.0`` 则让「改善 ≥ 0%」恒真 → **每个完成度达标的学生每周都拿一张
      绿牌**，绿牌从此不代表任何事。
    * **``completion_rate_min`` 不在 ``(0.0, 1.0]``**——上界**含** 1.0，因为 spec §8.2
      逐字要「100%」；``1.5`` 会让 ``>= 1.5`` 恒假 → **``GREEN_MASTERY`` 永不触发**。
    * **计数 ``< 1``**（:data:`_COUNT_PARAMS`）——``streak: 0`` 让 ``rpe_streak >= 0``
      恒真 → **每个学生每周一张红牌**，而 ``window_key`` 会去取
      ``rpe_session_ids[0 - 1]``，一个恰好不报错、却指着**最早**那一次快评的下标
      （于是去重键锚在一个随 streak 变的位置上，Review Focus 第 3 条的连乘又回来了）。

    ⚠️ **它不校验 ``rpe_min`` / ``mean_rpe_max`` 的范围**（硬规矩 #39，理由逐字见模块
    docstring 最后一条）：RPE 的值域 0–10 的唯一所有者是 spec §8.2，Plan 02 已把它写进
    ``assembler.py`` 的 docstring 与 ``INTENSITY_TYPES`` 的 ``rpe`` 档，
    Global Constraints 逐字要求「**不要在本计划里写第三份**」。
    """
    if name in _RATIO_PARAMS and not 0.0 < value < 1.0:
        raise _fail(
            path, lines, where,
            f"params.{name} = {value!r} 不在开区间 (0.0, 1.0) 内：它是一个**比率**"
            f"（0.05 = 5%）。写成 5.0 会让判据里的 1 - {name} 变成负数，"
            f"于是那条规则对任何正分数都「不下降」/「不改善」——**永不触发**，"
            f"而 YAML 看起来完全正常；写成 0.0 则让判据恒真——每次求值都触发"
        )
    if name == "completion_rate_min" and not 0.0 < value <= 1.0:
        raise _fail(
            path, lines, where,
            f"params.completion_rate_min = {value!r} 不在 (0.0, 1.0] 内：完成率是"
            f"「打卡数 ÷ 应打卡训练日数」，值域就是 [0, 1]。上界**含** 1.0"
            f"（spec §8.2 逐字「本周完成度 100%」）；> 1.0 会让判据恒假 → "
            f"GREEN_MASTERY 永不触发，<= 0.0 会让它恒真 → 每周人手一张绿牌"
        )
    if name in _COUNT_PARAMS and value < 1:
        raise _fail(
            path, lines, where,
            f"params.{name} = {value!r} 应 >= 1：它是一个**计数**（几次快评 / 几个数据点 / "
            f"几个训练日）。0 会让判据恒真（每个学生每周都触发那一条），"
            f"而 streak: 0 还会让 window_key 去取 rpe_session_ids[-1]——"
            f"一个恰好不报错、却指着最早那一次快评的下标，于是「同一次触发只有一条 alert」失效"
        )


def _check_cross(path, lines, where, rule_id: RuleId, values: dict) -> None:
    """校验**跨参数**的不变量。今天只有一条（``RED_MINITEST_DROP``），理由见下。

    ``points_needed`` 必须 == ``consecutive + 1``：spec §8.2 口径表 #2 逐字
    「需 **3 个数据点**：``score(t) < score(t-1) × 0.95`` **且**
    ``score(t-1) < score(t-2) × 0.95``」——**两次**下降要**三个**点。

    ⚠️ 它的失效是**静默**的：``consecutive: 2`` 配 ``points_needed: 5`` 时，
    :func:`app.domain.alerts.evaluate_student` 会拿到 5 个点却只查**最后 2 对**下降
    （判据本身没错），于是「需 3 个数据点」悄悄变成了「需 5 个点才够格被检查」——
    首次触发的周次跟着漂（口径表说的「第 6 周」会变成第 8 周），而 YAML 看起来完全合理。

    ⚠️ **这条不变量只在加载器校验一次**：domain 侧**不再校**（校两遍就是两个所有者，
    而两份迟早不一致）。故直接构造一个 ``AlertRules`` 的调用方（例如 domain 的单元测试）
    要自己保证它成立。
    """
    if rule_id is not RuleId.RED_MINITEST_DROP:
        return
    consecutive = values["consecutive"]
    needed = values["points_needed"]
    if needed != consecutive + 1:
        raise _fail(
            path, lines, where + ("params", "points_needed"),
            f"params.points_needed 是 {needed}，而 params.consecutive 是 {consecutive}"
            f"——前者必须 == 后者 + 1 = {consecutive + 1}（spec §8.2 口径表 #2 逐字："
            f"「需 3 个数据点：score(t) < score(t-1) × 0.95 且 score(t-1) < "
            f"score(t-2) × 0.95」，即 {consecutive} 次下降要 {consecutive + 1} 个点）。"
            f"不等的话判据本身不会错，但「需几个数据点」会悄悄变成另一个数，"
            f"于是首次触发的周次跟着漂，而 YAML 看起来完全合理"
        )


def _params(path, lines, where, rule_id: RuleId, raw: object) -> dict:
    """校验并返回一条规则的 ``params``（键集恰好是 :data:`_PARAM_TYPES` 给的那几个）。"""
    spec = _PARAM_TYPES[rule_id]
    names = tuple(name for name, _kind in spec)
    label = f"规则 {rule_id.value} 的 params"
    _exact_keys(path, lines, where + ("params",), raw, names, label)
    values: dict = {}
    for name, kind in spec:
        cell = where + ("params", name)
        if kind is int:
            values[name] = _as_int(path, lines, cell, raw[name], f"params.{name}")
        else:
            values[name] = _as_float(path, lines, cell, raw[name], f"params.{name}")
        _check_bounds(path, lines, cell, name, values[name])
    _check_cross(path, lines, where, rule_id, values)
    return values


def _rule(path, lines, name: str, raw: object) -> AlertRule:
    """校验并构造一条 :class:`~app.domain.alerts.AlertRule`。

    校验顺序是「**先键集、后取值、跨模块对账最后**」：键集错会让后面的取值拿不到值，
    而 ``scope`` 与 :func:`~app.domain.alerts.declared_scope` 的对账要拿一个合法的
    :class:`~app.domain.alerts.RuleId` 才做得成，故放最后。

    ⚠️ 这里的 ``RuleId(name)`` 之所以不会抛 ``ValueError``：调用方
    （:func:`load_alert_rules`）已经先把 ``rules:`` 的键集与 ``RuleId`` 对过账
    （多一个、少一个都响亮失败），故走到这里的 ``name`` 一定是合法成员。
    """
    where = ("rules", name)
    _exact_keys(path, lines, where, raw, _RULE_KEYS, f"规则 {name}")

    level_raw = raw["level"]
    try:
        level = AlertLevel(level_raw)
    except (ValueError, TypeError):
        raise _fail(
            path, lines, where + ("level",),
            f"level 值非法: {level_raw!r}；合法值: "
            f"{[member.value for member in AlertLevel]}（spec §4.6 / §8.2 的「级别」列）。"
            f"⚠️ 一个词表外的级别不会被任何人当成 red——它会在 Task 7 落库时被 "
            f"alert 表的 ck_alert_level 拒收，报错点离真因隔两层"
        ) from None

    scope_raw = raw["scope"]
    try:
        scope = AlertScope(scope_raw)
    except (ValueError, TypeError):
        raise _fail(
            path, lines, where + ("scope",),
            f"scope 值非法: {scope_raw!r}；合法值: "
            f"{[member.value for member in AlertScope]}（spec §8.2 的「作用域」列）。"
            f"它决定「哪一套求值器处理这条规则」：班级级规则拿不到学生信号，反之亦然"
        ) from None

    rule_id = RuleId(name)
    expected = declared_scope(rule_id)
    if scope is not expected:
        raise _fail(
            path, lines, where + ("scope",),
            f"scope 写的是 {scope.value!r}，而 app.domain.alerts.declared_scope({name}) "
            f"是 {expected.value!r}——两者矛盾。**代码那一份是所有者**：班级级规则拿不到 "
            f"StudentSignals（它没有 mean_rpe），学生级规则拿不到 ClassSignals，故「哪一套"
            f"求值器处理这条规则」只能由 app/domain/alerts.py 的两个 dispatch 表决定。"
            f"只翻 YAML 里这一行是**一件什么也不会发生的事**（而改的人会以为发生了）；"
            f"真要改作用域，改 app/domain/alerts.py 里那条规则的求值器与它的信号类型"
        )

    return AlertRule(
        rule_id=rule_id,
        level=level,
        scope=scope,
        params=types.MappingProxyType(_params(path, lines, where, rule_id, raw["params"])),
    )


def load_alert_rules(path: pathlib.Path | None = None) -> AlertRules:
    """读取预警阈值 YAML 并构造 :class:`~app.domain.alerts.AlertRules`。

    ``path`` 缺省为 ``DATA_DIR / ALERT_RULES_FILENAME``；文件不存在抛 ``FileNotFoundError``。
    校验顺序是 **顶层键集 → ``version`` → ``rules`` 的键集 → 逐条规则**：前三个是**表级**
    属性（缺了整份配置就没法用），第四个是**条目级**的，逐条报错时要点名是哪一条，故放最后。

    ⚠️ **``rules:`` 的键集必须与 ``RuleId`` 恰好相等**，两个方向都拦：

    * **多出一个没人认识的规则 ID** → 那是专家照 spec 加了新规则、忘了改代码。
      **静默忽略会让那条新规则永远不生效**，而 YAML 看起来完全正常、评审也过了
      （Review Focus 第 5 条点名的最阴的一档）。
    * **少一条** → 那一条规则从此不再被求值。⚠️ 它的失效形态与上面那个不同：
      :func:`app.domain.alerts.evaluate_student` 是按 ``RuleId`` 遍历、再用
      ``rules.rules[rule_id]`` 取配置的，故少一条是一次 ``KeyError``——响亮，但报错点
      在**第一个学生**身上、离「YAML 少了一行」隔两层。在加载期拦下来才有意义。

    ⚠️ **PyYAML 对重复的键是后者覆盖前者、不报错**（实测
    ``yaml.safe_load("a: 1\\na: 2") == {"a": 2}``），故「专家复制一段忘了改 ID」会让一条
    规则**静默变质**。本函数看不出来（它拿到的已经是覆盖后的 dict），守卫在
    ``tests/test_refdata_alerts.py::test_each_rule_id_appears_exactly_once_in_the_raw_text``
    ——那条用**原始文本**数一遍、与解析结果对账，两侧不同源。

    返回的 ``rules`` 与每条规则的 ``params`` 都是 :class:`types.MappingProxyType`：
    ``AlertRules.frozen=True`` 只挡住换掉整个字段，挡不住 ``rules[RuleId.X] = …`` 的
    就地改写，而 :func:`alert_rules` 是进程内共享单例（Task 7 的 ``alert_stage``
    逐学生逐班跑），一次误写会让之后所有求值静默变质。底层 dict 是本函数的局部变量、
    不外泄，故这两个只读视图是有效的（口径逐字同 :func:`app.refdata_prescription.load_exercises`）。

    ⚠️ **domain 侧做不出只读视图**：``types`` 不在
    ``tests/architecture/test_domain_purity.ALLOWED_MODULES`` 里，故
    :class:`app.domain.alerts.StudentHit` 的 ``snapshot`` 只能是普通 ``dict``
    （它每次求值新建、不外泄，故不构成同一类风险）。
    """
    yaml_path = DATA_DIR / ALERT_RULES_FILENAME if path is None else pathlib.Path(path)
    if not yaml_path.is_file():
        raise FileNotFoundError(f"预警规则缺失: {yaml_path}")
    text = yaml_path.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        # PyYAML 的 mark 里有行列、但**没有文件名**（喂给它的是字符串而不是文件对象），
        # 且 YAMLError 不是 ValueError 的子类。包一层让调用方只需认一种异常类型。
        raise ValueError(f"预警规则 {yaml_path} 不是合法的 YAML：{exc}") from exc
    lines = _line_index(text)

    if raw is None:
        raise _fail(
            yaml_path, lines, (),
            "文件为空：一条规则都没有，于是 500 人一个预警都不触发、而管道全绿"
            "（Review Focus 第 5 条要防的正是这个静默形状）"
        )
    _exact_keys(yaml_path, lines, (), raw, _TOP_KEYS, "预警规则顶层")

    version = raw["version"]
    if not isinstance(version, str) or not version.strip():
        raise _fail(
            yaml_path, lines, ("version",),
            f"version 应为非空字符串，实为 {type(version).__name__} 的 {version!r}。"
            f"⚠️ YAML 里**不加引号**的 ``1.0`` 会被 PyYAML 解析成 float，而 ``1.10`` 会"
            f"变成 ``1.1``——版本号静默变形，故本文件的 version 一律加引号"
            f"（口径同 18 份处方模板与 ``exercise_equivalence.yaml``）。"
            f"它是 spec §4.4 要求的「静态 YAML + **版本号**」的那一半：Task 7 把它写进 "
            f"weekly_adjustment 的 auto 来源留痕，于是一张已减量的训练单能回答"
            f"「当时是按哪一版阈值判的」"
        )

    rules_raw = raw["rules"]
    if not isinstance(rules_raw, dict):
        raise _fail(
            yaml_path, lines, ("rules",),
            f"rules 应为「规则 ID → 规则块」的映射（spec §8.2 的 5 行），"
            f"实为 {type(rules_raw).__name__}"
        )
    known = [rule_id.value for rule_id in RuleId]
    unknown = sorted(key for key in rules_raw if key not in known)
    if unknown:
        raise _fail(
            yaml_path, lines, ("rules", unknown[0]),
            f"rules 里有代码不认识的规则 ID {unknown}；合法的 ID 恰好是 {known}"
            f"（app.domain.alerts.RuleId）。⚠️ **静默忽略会让那条新规则永远不生效**："
            f"加一条新规则要同时改 app/domain/alerts.py（RuleId 加一个成员 + 一个求值器 + "
            f"接进对应的 dispatch 表）与本文件，只改一边都不算加成功"
        )
    absent = [name for name in known if name not in rules_raw]
    if absent:
        raise _fail(
            yaml_path, lines, ("rules",),
            f"rules 缺规则 {absent}；必需的规则恰好是 {known}（spec §8.2 的 5 行）。"
            f"少一条的话 app.domain.alerts 的求值器会在第一个学生身上抛 KeyError"
            f"（它按 RuleId 遍历、再按 ID 取配置），报错点离「YAML 少了一段」隔两层"
        )

    store = {
        rule_id: _rule(yaml_path, lines, rule_id.value, rules_raw[rule_id.value])
        for rule_id in RuleId
    }
    return AlertRules(version=version, rules=types.MappingProxyType(store))


def alert_rules() -> AlertRules:
    """进程内单例：预警阈值是只读参考数据，一个进程加载一次即可。

    与 :func:`app.refdata.standard` / :func:`app.refdata_prescription.templates` 同口径
    （Plan02 账本 P2-A9：``load_*`` 只负责加载、**不缓存**，单例是另一个函数）。

    **单例同时是性能前提**：Task 7 的 ``alert_stage`` 是逐学生逐班跑的，少了单例就会
    每人重解析一次 YAML——而每次还要跑一遍 ``yaml.compose`` 建行号索引
    （见 :func:`app.refdata_yaml.line_index`），即每份解析两遍。
    """
    global _alerts_cache
    if _alerts_cache is None:
        _alerts_cache = load_alert_rules()
    return _alerts_cache

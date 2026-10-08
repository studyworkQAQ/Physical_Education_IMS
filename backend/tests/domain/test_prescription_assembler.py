# backend/tests/domain/test_prescription_assembler.py
"""处方装配器 :func:`app.domain.prescription.assembler.assemble` 的守卫（Plan 02 Task 5 的 5.2）。

**期望值一律字面写死、且由实现者独立重算**（硬规矩 #35 / #44）。重算过程（本机 Python
3.11.1 亲跑 ``repr``，``RED-END-ABN-01`` 第 1 课、``weekly_frequency = 4``、
``week_deltas = (1.0, 1.05, 1.1, 0.85)``、男 20 岁、``endurance_score = 50`` → 档 ``< 60``
给 ``0.8``、性别男给 ``1.0``、系数 **0.8**）::

    interval_run       structure {sets:4, work_min:3, rest_min:2}
                       base = work_min × sets = 3 × 4 = 12 min/课
                       weekly = base × sessions_per_week = 12 × 4 = 48.0 min/周
                       第 1 周 48.0 × 0.8 × 1.00 = 38.400000000000006 → round(…,1) = 38.4
                       第 2 周 48.0 × 0.8 × 1.05 = 40.32000000000001  → 40.3
                       第 3 周 48.0 × 0.8 × 1.10 = 42.24000000000001  → 42.2
                       第 4 周 48.0 × 0.8 × 0.85 = 32.64              → 32.6
    compound_circuit   structure {rounds:3, reps:10}
                       base = rounds × reps = 3 × 10 = 30 reps/课 → weekly 120.0 reps/周
                       第 1 周 96.0 / 第 2 周 100.8 / 第 3 周 105.6 / 第 4 周 81.6

**与派单那张算例表逐格相符**（38.4 / 32.6 / 96.0 / 81.6 四个数两边一致），故不存在
「先怀疑自己还是先怀疑表」的分歧。⚠️ 但**未 round 的中间值不是那些数**：
``48.0 × 0.8 × 1.0`` 亲跑是 ``38.400000000000006``（Plan02 账本 P5-A6 记的同一类浮点尾数），
故断言一律打在 ``round(…, 1)`` **之后**的字面值上，系数本身才用 ``pytest.approx``。

``hrmax(20) = 208 − 0.7 × 20 = 194.0``；``hr_zone(194.0, 60, 70) = (116, 136)``
（``116.4`` 向下、``135.8`` 向上），与派单一致。

--------------------------------------------------------------------------

**本文件同时是 Ruling 133（简报 5.2 的头号约束）的唯一守卫**：真仓 18 套模板的 **130** 个
block 里 **82** 个是 ``intensity: {type: none}``（亲扫：绿 24 / 黄 42 / 红 16，``hrmax_pct``
24 与 ``onerm_pct`` 24 全在红层）。故：

* :func:`test_real_yellow_and_green_templates_assemble_with_no_hr_zone_and_explicit_text`
  **直接吃真仓 YAML**（不是手工构造的 ``Template``），是「简化版装配器真能跑通 18 套模板」
  的唯一守卫；
* **心率相关的断言一律打在红层**（``RED-END-ABN-01`` / ``RED-SPD-ABN-05``）上——用黄层写
  会全绿、但什么也没测（假绿）。

⚠️ **吃真仓 YAML 的测试用 :func:`app.refdata_prescription.exercises` /
:func:`~app.refdata_prescription.templates` 两个进程内单例**（简报 P5-A12），不用 ``load_*``
（后者每次重解析 18 份 YAML、还各跑一遍 ``yaml.compose`` 建行号索引）。
⚠️ **单例是进程内共享的，本文件一个字都不改它**：要一个坏形状的模板一律用
:func:`dataclasses.replace` 造副本（``Template`` / ``Session`` / ``Block`` 都是 frozen
dataclass，``replace`` 产出新对象、原单例不动）。

⚠️ **本文件守不住什么**（硬规矩 #39）：

* **不守三档系数的取值对不对**。``< 60 → 0.8``、``[60, 80) → 1.0``、``>= 80 → 1.2``、
  男 ``1.0`` / 女 ``0.9`` 这套阈值**指导文件没给**，是工程约定（spec §14 第 **32** 项，
  归 Task 9 登记）。本文件钉的是「实现的就是这张表」，不是「这张表运动生理学上对」。
* **不守 ``structure`` 里各键的**值类型**：加载器 :func:`app.refdata_prescription._structure`
  只查「是个非空映射、键全是字符串」，**不查值是不是数字**；本模块按简报 P5-A1
  「不重复校验键的类型（单一所有者）」也不查。故一份 ``structure: {sets: "4", work_min: 3,
  rest_min: 2}`` 的 YAML 能加载成功，然后在装配时给出 ``float(3 * "4") = 444.0`` 这个
  **静默错值**（``sets`` 与 ``work_min`` 都是字符串时反而 ``TypeError``、是响的）。
  已作为关切报出，修法是在加载器那一侧补值类型校验（本 Task 无权改 ``app/`` 的其它文件）。

--------------------------------------------------------------------------

**⚠️ ``weekly_volume_base`` 在 fix round 1（F1-1）从混合量纲的裸 ``float`` 改成按单位分列的
只读 ``Mapping[str, float]``**（控制者采纳实现者上一轮的异议）。改前它是
``48.0 min + 120.0 reps = 168.0``——**一个把分钟和次数加在一起的数没有意义**，而它要落进
``prescription.assembly_snapshot`` 这个 JSON 列、并在 Plan 03/04 被前端读出来展示，与
P5-A1 自己立的「两种单位不可通约」互相打脸。改后的口径与四条守卫：

* **口径**：键 = 实际出现过的 ``volume_unit``；值 = 该单位下的周量之和（``round(…, 1)``）。
  ``RED-END-ABN-01`` 亲算：``min`` = 4 课 × 12 = **48.0**、``reps`` = 4 课 × 30 = **120.0**，
  即 ``{"min": 48.0, "reps": 120.0}``（两者相加正是改前那个 ``168.0``）。
* **键集不写死**（:func:`test_weekly_volume_base_keys_are_a_subset_of_volume_units`）：
  18 套模板亲扫的键集分布是 ``{("min",): 10, ("reps",): 6, ("min", "reps"): 2}``——
  **16/18 套只有一个单位**，只有两套 ``RED-END-*`` 两个都有。``"unspecified"`` 一档
  **0 次出现**：``assemble`` 跑在 ``apply_safety`` 之前，那时还没有 addon block。
* **只读**（:func:`test_weekly_volume_base_is_read_only`）：``types`` 不在 domain 的
  allow-list 里（fix round 1 亲跑坐实：往 ``assembler.py`` 插一句 ``import types`` →
  ``test_domain_imports_stay_within_the_allow_list`` 报 ``assembler.py:148: types``），
  故拿不到 ``types.MappingProxyType``；而 ``MappingProxyType`` 又**不是** JSON 可序列化的
  （亲跑 ``TypeError: Object of type mappingproxy is not JSON serializable``）。落地的是一个
  **屏蔽了全部 8 个 mutator 的 ``dict`` 子类**——它同时满足「只读」与「``json.dumps`` 认它」
  （亲跑 ``isinstance(m, dict) is True`` → C 编码器走 ``PyDict_Next`` 快路径）。
* **JSON 化**（:func:`test_assembly_snapshot_is_json_serialisable`）：全局纪律是
  ``allow_nan=False``，故这一条是承重的，不是装饰。
"""
import copy
import dataclasses
import datetime as dt
import json
import pickle

import pytest

from app import refdata_prescription as rp
from app.domain.indicators import Sex
from app.domain.prescription.assembler import (
    VOLUME_FACTOR_BANDS,
    VOLUME_UNITS,
    AssembledBlock,
    AssembledSession,
    AssembledWeek,
    StudentProfile,
    TrainingPackage,
    assemble,
)
from app.domain.prescription.templates import Intensity

# ---------------------------------------------------------------------------
# 期望侧的字面量（一律不从被测对象反推，硬规矩 #35）
# ---------------------------------------------------------------------------

#: 装配基准日。**domain 不碰时钟**，故它由测试注入（Global Constraint #1）。
_AS_OF = dt.date(2026, 10, 6)
#: 出生日 → 在 :data:`_AS_OF` 那天周岁 **20**（生日 3-15 早已过）。
_BIRTH = dt.date(2006, 3, 15)

#: ``assembly_snapshot`` 的键集，**恰好 12 个**（简报 P5-A7：这 12 个是 ``assemble`` 的完整
#: 契约，一个都不许多；``apply_safety`` 的 3 个追加键由
#: ``tests/domain/test_prescription_safety.py`` 钉）。字面写死、按 ``assemble`` 产出时的
#: 书写序排列，**不是字母序**——故 ``sorted(...) == ...`` 这类改法会红。
_SNAPSHOT_KEYS = (
    "formula", "hrmax", "age", "as_of", "endurance_score", "volume_factor",
    "volume_factor_band", "sex_factor", "template_id", "template_version",
    "week_deltas", "weekly_volume_base",
)

#: ``RED-END-ABN-01`` 第 1 课两个 block 的 ref（照 ``backend/data/prescription/`` 的
#: YAML 字面抄，不从 :func:`rp.templates` 读回来）。
_RED_END_REFS = ("interval_run", "compound_circuit")

#: ``RED-END-ABN-01`` 的 ``weekly_volume_base``（F1-1 之后是**按单位分列**的只读映射）。
#: 独立重算：4 课 × ``interval_run`` 的 ``work_min 3 × sets 4 = 12`` min → ``min`` 档 **48.0**；
#: 4 课 × ``compound_circuit`` 的 ``rounds 3 × reps 10 = 30`` reps → ``reps`` 档 **120.0**。
#: ⚠️ 键序是**书写序**（``min`` 先、``reps`` 后），因为它按 block 的首次出现序累加，而
#: ``RED-END-ABN-01`` 每一课都是 ``interval_run`` 在前。
_RED_END_VOLUME_BASE = {"min": 48.0, "reps": 120.0}

#: 18 套模板的 ``weekly_volume_base`` **键集分布**（亲扫，字面写死）。它证明「键集不是
#: 硬写死的」这件事真的被测到了：16/18 套只有一个单位，只有两套 ``RED-END-*`` 两个都有。
_VOLUME_BASE_KEYSET_DISTRIBUTION = {("min",): 10, ("reps",): 6, ("min", "reps"): 2}

#: 三档系数（男）。字面值 = 档位系数 × 性别系数 ``1.0`` 再 ``round(…, 2)``。
_BANDS_MALE = ((50.0, 0.8, "low"), (70.0, 1.0, "mid"), (90.0, 1.2, "high"))
#: 档位边界：**半开、无缝无叠**（简报 5.2 的「三档系数」段，Ruling 9 更正原文的「60–79」）。
_BAND_EDGES = ((59.9, 0.8, "low"), (60.0, 1.0, "mid"),
               (79.9, 1.0, "mid"), (80.0, 1.2, "high"))


def _profile(**overrides) -> StudentProfile:
    """一个默认的学生画像：男、20 岁、``endurance_score = 50``（档 ``low`` → 系数 0.8）。"""
    fields = {
        "student_id": 1,
        "sex": Sex.MALE,
        "birth": _BIRTH,
        "age": 20,
        "endurance_score": 50.0,
        "bmi": None,
        "body_fat_pct": None,
        "muscle_mass_kg": None,
        "muscle_p10": None,
        "measured_hrmax": None,
    }
    fields.update(overrides)
    return StudentProfile(**fields)


def _unit_factor_profile(**overrides) -> StudentProfile:
    """系数恰为 **1.0** 的画像（男 + ``endurance_score = 70`` → 档 ``mid``）。

    用它把「个体系数」这一层剥掉，于是 ``weekly_volume`` 的字面值就只剩
    ``base × sessions_per_week × week_deltas[n]`` 三个因子，算例可以心算对拍。
    """
    overrides.setdefault("endurance_score", 70.0)
    return _profile(**overrides)


def _blocks(pkg: TrainingPackage, week: int = 1) -> tuple[AssembledBlock, ...]:
    """第 ``week`` 周（1 基）第 1 课的全部 block。"""
    return pkg.weeks[week - 1].sessions[0].blocks


def _by_ref(pkg: TrainingPackage, week: int = 1) -> dict[str, AssembledBlock]:
    return {block.exercise_ref: block for block in _blocks(pkg, week)}


# ---------------------------------------------------------------------------
# 词表（单一所有者在本模块，期望值字面写死在测试里）
# ---------------------------------------------------------------------------


def test_volume_unit_vocabulary_is_pinned_verbatim():
    """``volume_unit`` 的取值域恰好三档（简报 P5-A1 新增的字段）。

    **第三档 ``"unspecified"`` 是为 5.3 的追加 addon 加的**：``Addon`` 只有
    ``when`` / ``module`` 两个字段，没有 ``structure``，故它的量**无从算起**；编造一个数
    就是把「不知道」讲成「知道」（Plan01 Ruling 134 的同一条纪律）。
    """
    assert VOLUME_UNITS == frozenset({"min", "reps", "unspecified"})


def test_volume_factor_band_vocabulary_is_pinned_verbatim():
    """``volume_factor_band`` 的取值域恰好四档，含 ``"unknown"``。

    ``"unknown"`` 承载「``endurance_score is None``」这件事，**不另加第 13 个快照键**
    （简报 P5-A7：那 12 个键是离线复算的契约，多一个键就废了）。
    """
    assert VOLUME_FACTOR_BANDS == frozenset({"low", "mid", "high", "unknown"})


# ---------------------------------------------------------------------------
# 第 1 步：HRmax
# ---------------------------------------------------------------------------


def test_hrmax_uses_tanaka_when_no_measured_value():
    """``measured_hrmax is None`` → Tanaka。``hrmax(20) = 194.0``（精确 float）。"""
    pkg = assemble(_profile(), rp.templates()["RED-END-ABN-01"], _AS_OF,
                   exercises=rp.exercises())
    assert pkg.assembly_snapshot["formula"] == "tanaka"
    assert pkg.assembly_snapshot["hrmax"] == 194.0


def test_hrmax_prefers_the_measured_value():
    """``measured_hrmax`` 非空 → 用它，且**心率区间跟着变**（不是只改快照里的一个数）。

    ``186.0 × 60 / 100.0 = 111.6`` → ``111``；``186.0 × 70 / 100.0 = 130.2`` → 向上 ``131``。
    与 Tanaka 的 ``(116, 136)`` 不同，故「用了实测值」这件事可辨识。
    ⚠️ ``formula`` 仍恒为 ``"tanaka"``：它记的是**本构建实现的是哪个公式**（简化版砍掉了
    ``HrmaxFormula`` 枚举），而「实际用的是哪个值」由 ``hrmax`` 那一格承担。
    """
    pkg = assemble(_profile(measured_hrmax=186.0), rp.templates()["RED-END-ABN-01"],
                   _AS_OF, exercises=rp.exercises())
    assert pkg.assembly_snapshot["hrmax"] == 186.0
    assert pkg.assembly_snapshot["formula"] == "tanaka"
    assert _by_ref(pkg)["interval_run"].hr_zone == (111, 131)


def test_hrmax_inconsistent_age_is_rejected():
    """第 1 步的一致性闸门：``age != age_from(birth, as_of)`` → ``ValueError``。

    **它是一个廉价闸门，挡的是「调用方用了错误的 ``as_of``」**：``age`` 与 ``birth`` 都由
    调用方给，装配器不自己算日期（避免两个所有者），但**必须对账**——否则一个
    ``as_of`` 传成去年的调用方会静默装配出一个按 19 岁算 HRmax 的训练包。
    ``21`` 是刻意挑的：它与 ``age_from(_BIRTH, _AS_OF) == 20`` 差 1，且 ``hrmax(21)``
    自己完全合法（``193.3``），故红的原因只能是这道闸门。
    """
    with pytest.raises(ValueError) as excinfo:
        assemble(_profile(age=21), rp.templates()["RED-END-ABN-01"], _AS_OF,
                 exercises=rp.exercises())
    assert "21" in str(excinfo.value) and "20" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 第 2 步：目标心率区间（⚠️ 只能用红层，Ruling 133）
# ---------------------------------------------------------------------------


def test_hr_zone_only_for_hrmax_pct_blocks():
    """只有 ``hrmax_pct`` 的 block 有心率区间；``onerm_pct`` 的是 ``None`` 且文案含「1RM」。

    **不要给非心率类动作硬塞一个心率区间**（简报 5.2 六步口径的第 2 步）：一个
    ``70% 1RM`` 的复合循环被标上「116–136 bpm」会让学生以为要盯着心率做，而那恰恰是
    力量动作不该有的指令。
    """
    pkg = assemble(_profile(), rp.templates()["RED-END-ABN-01"], _AS_OF,
                   exercises=rp.exercises())
    blocks = _by_ref(pkg)
    assert blocks["interval_run"].hr_zone == (116, 136)
    assert "60" in blocks["interval_run"].intensity_text
    assert "70" in blocks["interval_run"].intensity_text
    assert blocks["compound_circuit"].hr_zone is None
    assert "1RM" in blocks["compound_circuit"].intensity_text
    assert "70" in blocks["compound_circuit"].intensity_text


def test_rpe_intensity_renders_text_without_an_hr_zone():
    """``rpe`` 那一档：渲染文案、``hr_zone is None``（简报 P5-A5）。

    ⚠️ **真仓 18 套模板里 ``rpe`` 出现 0 次**（亲扫：``none`` 82 / ``hrmax_pct`` 24 /
    ``onerm_pct`` 24，共 130），故这一档**只能手工构造**——不构造它，domain 的分支覆盖
    就到不了 100%（Global Constraint #2，简化版不豁免）。

    ``Intensity.value`` 的语义**随 ``type`` 变**：``onerm_pct`` 是 1RM 的百分比、``rpe`` 是
    **0–10** 的自觉受累程度（⚠️ **不是** Borg 经典的 6–20 —— spec 全篇的 RPE 都是 0–10
    标度：``rpe_record`` 表字段逐字是「RPE 0–10」、§8.2 的小标题逐字是「课堂端 RPE
    （0–10 主观疲劳）」、``RED_RPE_SUSTAINED`` 是「RPE 连续 ≥ 9 分」、
    ``YELLOW_CLASS_RPE_HIGH`` 是「课堂 RPE 均值 > 7 分」、大屏异常名单是「RPE > 8」）。
    故这里用 ``value=7.0``（0–10 标度上的合法值）；改前用的是 ``13``，那在 0–10 上非法。
    """
    template = rp.templates()["RED-END-ABN-01"]
    session = template.sessions[0]
    rpe_block = dataclasses.replace(
        session.blocks[0], intensity=Intensity(type="rpe", value=7.0)
    )
    template = dataclasses.replace(template, sessions=(
        dataclasses.replace(session, blocks=(rpe_block,)),
        *template.sessions[1:],
    ))
    pkg = assemble(_profile(), template, _AS_OF, exercises=rp.exercises())
    block = _blocks(pkg)[0]
    assert block.hr_zone is None
    assert block.intensity_text == "RPE 7"


def test_rpe_value_outside_zero_to_ten_is_rejected():
    """**F1-2 的边界守卫**：``rpe`` 的值域是 **0–10**（两端**闭**），越界 ``ValueError``。

    四个值 ``-0.1`` / ``0.0`` / ``10.0`` / ``10.1``：两端合法、两侧越界。
    ⚠️ 这四个期望值不需要「自己算」：``0`` 与 ``10`` 就是 spec 自己给的两个端点
    （``rpe_record`` 表字段逐字「RPE 0–10」、§8.2 小标题逐字「课堂端 RPE（0–10 主观疲劳）」），
    故硬规矩 #44 在这一条上没有可算的东西。

    **为什么加这道校验**（派单允许「加或不加，但要写明理由」）：

    * 它与 :func:`app.domain.prescription.intensity.hr_zone` 里那道
      ``0 <= low <= high <= 100`` **对称**——``hrmax_pct`` 的值域在 domain 这一层就有守卫，
      ``rpe`` 没有就是一个不对称的洞，而不是「单一所有者」。
    * 加载器 :func:`app.refdata_prescription._intensity` 只校验**字段形状**
      （``rpe`` 要有 ``value``、不许有 ``low``/``high``），**不校验值域**。故没有本条的话，
      一份 ``intensity: {type: rpe, value: 13}`` 的 YAML 能加载成功、渲染成学生端的
      「RPE 13」——在 0–10 标度上那是一个**看起来完全正常的谎**。
    * **可证明不会让任何真仓模板炸**：``rpe`` 在 18 套模板里出现 **0** 次（P5-A5 亲扫），
      故这道拒绝今天在生产路径上不可达，只有本条测试走它。
    """
    template = rp.templates()["RED-END-ABN-01"]
    session = template.sessions[0]
    for value in (0.0, 10.0):
        legal = dataclasses.replace(
            session.blocks[0], intensity=Intensity(type="rpe", value=value)
        )
        pkg = assemble(
            _profile(),
            dataclasses.replace(template, sessions=(
                dataclasses.replace(session, blocks=(legal,)),)),
            _AS_OF, exercises=rp.exercises())
        assert _blocks(pkg)[0].intensity_text == f"RPE {value:g}"
    for value in (-0.1, 10.1):
        illegal = dataclasses.replace(
            session.blocks[0], intensity=Intensity(type="rpe", value=value)
        )
        with pytest.raises(ValueError) as excinfo:
            assemble(_profile(),
                     dataclasses.replace(template, sessions=(
                         dataclasses.replace(session, blocks=(illegal,)),)),
                     _AS_OF, exercises=rp.exercises())
        # 消息里要带**实际收到的值**与那条值域（口径照 hrmax 的年龄拒绝）
        message = str(excinfo.value)
        assert f"{value}" in message, message
        assert "0–10" in message, message


def test_an_unknown_intensity_type_is_rejected():
    """词表外的 ``intensity.type`` → ``ValueError``，**不静默渲染成空文案**。

    ``INTENSITY_TYPES`` 的所有者是 :mod:`app.domain.prescription.templates`，加载器
    :func:`app.refdata_prescription._intensity` 已经拦过一道；本条是**第二道**（口径照简报
    对 ``exercise_ref`` 的处置：「Task 3 的加载校验是第一道，这是第二道；**两道都要有**」），
    因为装配器可能被喂进一个手工构造的 ``Template``。
    """
    template = rp.templates()["RED-END-ABN-01"]
    session = template.sessions[0]
    bogus = dataclasses.replace(
        session.blocks[0], intensity=Intensity(type="watt_bike", value=200.0)
    )
    template = dataclasses.replace(
        template, sessions=(dataclasses.replace(session, blocks=(bogus,)),)
    )
    with pytest.raises(ValueError) as excinfo:
        assemble(_profile(), template, _AS_OF, exercises=rp.exercises())
    assert "watt_bike" in str(excinfo.value)


def test_real_yellow_and_green_templates_assemble_with_no_hr_zone_and_explicit_text():
    """⚠️⚠️ **Ruling 133 的那条守卫**：直接吃真仓 YAML 的黄层 + 绿层各一套。

    断言三件事：① ``assemble`` 成功；② **所有** block 的 ``hr_zone is None``；
    ③ **所有** ``intensity_text`` 非空。

    第 ③ 件是承重的：``intensity: {type: none}`` 在真仓是**常态不是例外**（82/130），
    故文案必须有一档**显式**渲染它——回落到 ``hrmax_pct`` 的默认值会给学生一个模板从没
    要求过的心率区间，留空字符串则让学生端看到一格空白（分不清「不需要强度区间」与
    「忘了填」，与 ``exercises.yaml`` 的 ``equipment: none`` 同一条理由）。

    **为什么挑这两套**（亲扫 ``backend/data/prescription/``）：
    ``YEL-END-ABN-07``（黄层、``weekly_frequency = 3``、``steady_run`` + ``step_training``、
    两个 block 的 intensity 全是 ``none``）与 ``GRN-END-NOR-14``（绿层、``weekly_frequency = 2``、
    ``orienteering`` + ``interest_ball_games``、同样全是 ``none``）。
    ⚠️ 绿层挑的是 ``-NOR-14`` 而不是 ``-ABN-13``：后者 ``reachable: false``
    （spec §7.1 的预留位），装配器**不查** ``reachable``（那是
    :func:`app.domain.prescription.match_template` 的职责），故两套都能装配；挑可达的那套
    是为了让本条同时是「生产路径真能走通」的证据。
    """
    for template_id in ("YEL-END-ABN-07", "GRN-END-NOR-14"):
        template = rp.templates()[template_id]
        pkg = assemble(_unit_factor_profile(), template, _AS_OF,
                       exercises=rp.exercises())
        assert pkg.template_id == template_id
        all_blocks = [b for w in pkg.weeks for s in w.sessions for b in s.blocks]
        # 黄层 3 课 × 2 block × 4 周 = 24；绿层 2 课 × 2 block × 4 周 = 16
        expected_count = template.weekly_frequency * 2 * template.microcycle_weeks
        assert len(all_blocks) == expected_count, template_id
        for block in all_blocks:
            assert block.hr_zone is None, (template_id, block.exercise_ref)
            assert block.intensity_text.strip(), (template_id, block.exercise_ref)
            assert block.intensity_text == (
                "模板未指定强度（spec §7.2 只给了红层数值，见 spec §14）"
            ), (template_id, block.exercise_ref)


# ---------------------------------------------------------------------------
# 第 3 步：周训练总量（P5-A1 的基准量口径 + 三档系数）
# ---------------------------------------------------------------------------


def test_volume_factor_three_bands():
    """三档各一条 + 四个边界点（系数与档名都字面写死）。

    档位是**半开区间**：``< 60`` / ``[60, 80)`` / ``>= 80``，无缝无叠。
    ``59.9`` 与 ``79.9`` 这两格是 Ruling 9 更正原文「60–79」的理由：``endurance_score`` 是
    两项国标得分的 **float 均值**，``79.5`` 会落在 ``(79, 80)`` 的缝里。
    女性 ``0.9`` 与档位系数相乘后 ``round(…, 2)``：``0.8 × 0.9`` 亲跑是
    ``0.7200000000000001``（P5-A6），故期望值写 round 之后的 ``0.72``。
    """
    template = rp.templates()["RED-END-ABN-01"]
    for score, factor, band in _BANDS_MALE + _BAND_EDGES:
        snapshot = assemble(_profile(endurance_score=score), template, _AS_OF,
                            exercises=rp.exercises()).assembly_snapshot
        assert snapshot["volume_factor"] == pytest.approx(factor), score
        assert snapshot["volume_factor_band"] == band, score
    female = assemble(_profile(sex=Sex.FEMALE, endurance_score=50.0), template, _AS_OF,
                      exercises=rp.exercises()).assembly_snapshot
    assert female["sex_factor"] == pytest.approx(0.9)
    assert female["volume_factor"] == pytest.approx(0.72)
    assert female["volume_factor_band"] == "low"
    assert assemble(_profile(sex=Sex.MALE), template, _AS_OF,
                    exercises=rp.exercises()).assembly_snapshot["sex_factor"] == pytest.approx(1.0)


def test_volume_factor_falls_back_when_endurance_score_missing():
    """``endurance_score is None`` → 系数 ``1.0``、档名 ``"unknown"``、**仍是 12 个键**。

    ⚠️ **不加第 13 个键**（简报 P5-A7）：原文另要求的 ``volume_factor_fallback`` 会让键集
    从 12 变 13，而那 12 个是离线复算的契约。信息已经在 ``volume_factor_band`` 里了。
    """
    pkg = assemble(_profile(endurance_score=None), rp.templates()["RED-END-ABN-01"],
                   _AS_OF, exercises=rp.exercises())
    assert pkg.assembly_snapshot["volume_factor"] == pytest.approx(1.0)
    assert pkg.assembly_snapshot["volume_factor_band"] == "unknown"
    assert tuple(pkg.assembly_snapshot) == _SNAPSHOT_KEYS


def test_volume_base_uses_the_right_formula_per_structure_shape():
    """**P5-A1**：两种 ``structure`` 形状各有各的基准量公式，且 ``volume_unit`` 跟着变。

    实测 130 个 block 只有两种键集、无第三种、无交集（亲扫：**78** 个
    ``{sets, work_min, rest_min}``、**52** 个 ``{rounds, reps}``，78 + 52 = 130 ✓），
    且取值全部相同（时长类一律 ``{4, 3, 2}``、次数类一律 ``{3, 10}``）。

    用系数 **1.0** 的画像 + 第 1 周（``week_deltas[0] == 1.0``），于是
    ``weekly_volume`` 的字面值就等于 ``base × sessions_per_week``：
    ``interval_run`` → ``12 × 4 = `` **48.0** ``min``；
    ``compound_circuit`` → ``30 × 4 = `` **120.0** ``reps``。
    **两种单位不可通约**，故 ``volume_unit`` 是必需字段而不是可选修饰：一个裸 ``float``
    无法回答「48.0 是分钟还是次数」。
    """
    pkg = assemble(_unit_factor_profile(), rp.templates()["RED-END-ABN-01"], _AS_OF,
                   exercises=rp.exercises())
    blocks = _by_ref(pkg)
    assert blocks["interval_run"].weekly_volume == 48.0
    assert blocks["interval_run"].volume_unit == "min"
    assert blocks["compound_circuit"].weekly_volume == 120.0
    assert blocks["compound_circuit"].volume_unit == "reps"
    assert blocks["interval_run"].structure == {"sets": 4, "work_min": 3, "rest_min": 2}
    assert blocks["compound_circuit"].structure == {"rounds": 3, "reps": 10}


def test_rest_min_is_not_counted_as_volume():
    """**P5-A1**：``rest_min`` 从 2 改成 20，``weekly_volume`` 必须**一个字都不变**。

    **理由**（简报要求写进 docstring）：``rest_min`` 是**恢复**、不是负荷。把它算进训练量，
    「减量 20%」就会**同时缩短恢复时间**——而对红层学生缩短恢复恰恰是危险的那一半
    （减量本该降的是负荷，恢复时间要保住甚至加长）。
    """
    template = rp.templates()["RED-END-ABN-01"]
    baseline = assemble(_unit_factor_profile(), template, _AS_OF, exercises=rp.exercises())

    def _with_rest(rest_min: int) -> TrainingPackage:
        sessions = []
        for session in template.sessions:
            blocks = tuple(
                dataclasses.replace(
                    block,
                    structure={"sets": 4, "work_min": 3, "rest_min": rest_min},
                )
                if block.exercise_ref == "interval_run" else block
                for block in session.blocks
            )
            sessions.append(dataclasses.replace(session, blocks=blocks))
        return assemble(_unit_factor_profile(),
                        dataclasses.replace(template, sessions=tuple(sessions)),
                        _AS_OF, exercises=rp.exercises())

    long_rest = _with_rest(20)
    assert _by_ref(long_rest)["interval_run"].weekly_volume == 48.0
    # 四周逐周对账：rest_min 从 2 变 20，量一个字不变（48.0 × week_deltas）
    assert [_by_ref(long_rest, n)["interval_run"].weekly_volume for n in (1, 2, 3, 4)] == [
        48.0, 50.4, 52.8, 40.8]
    for week_index in range(4):
        before = _by_ref(baseline, week_index + 1)["interval_run"]
        after = _by_ref(long_rest, week_index + 1)["interval_run"]
        assert before.weekly_volume == after.weekly_volume
        assert after.structure["rest_min"] == 20
    # 快照里的 weekly_volume_base 同样不含 rest_min：min 档仍是 4 课 × 12 = 48.0，
    # reps 档仍是 4 课 × 30 = 120.0（F1-1 之后按单位分列，故逐档都要对账）
    assert long_rest.assembly_snapshot["weekly_volume_base"] == _RED_END_VOLUME_BASE
    assert baseline.assembly_snapshot["weekly_volume_base"] == _RED_END_VOLUME_BASE


def test_unknown_structure_shape_is_rejected_not_zeroed():
    """**P5-A1**：既不是那两种形状 → ``ValueError``，**不得静默取 0**。

    量变 0 会让训练包**看起来完全正常**（结构齐全、文案齐全、快照齐全），而每个 block
    都是空的——那正是「静默失效」最坏的形态。
    ⚠️ 加载器 :func:`app.refdata_prescription._structure` **刻意不约束键集**（它自己的
    docstring 逐字写着「spec 只给了两个字面例子…故本 Task 不编一个」），故本条是
    这个形状**唯一**的守卫。
    """
    template = rp.templates()["RED-END-ABN-01"]
    session = template.sessions[0]
    bogus = dataclasses.replace(session.blocks[0], structure={"foo": 1})
    template = dataclasses.replace(
        template, sessions=(dataclasses.replace(session, blocks=(bogus,)),)
    )
    with pytest.raises(ValueError) as excinfo:
        assemble(_profile(), template, _AS_OF, exercises=rp.exercises())
    assert "foo" in str(excinfo.value)
    # 空映射同样拒绝（加载器也拦它，这里是第二道）
    session = rp.templates()["RED-END-ABN-01"].sessions[0]
    empty = dataclasses.replace(session.blocks[0], structure={})
    template = dataclasses.replace(
        rp.templates()["RED-END-ABN-01"],
        sessions=(dataclasses.replace(session, blocks=(empty,)),),
    )
    with pytest.raises(ValueError):
        assemble(_profile(), template, _AS_OF, exercises=rp.exercises())


def test_weekly_volume_is_base_times_sessions_per_week():
    """**P5-A2**：``weekly_volume = base × sessions_per_week``，不是 ``base``。

    同一 ``exercise_ref`` 在一周内**跨 session 重复，18/18 套模板全部如此**（亲扫）。
    若 ``weekly_volume`` 只是「单次课的量」，它就**名不符实**（叫 weekly 却是 per-session），
    而 spec §4.3 的可追溯性会断在这一环。
    ``sessions_per_week`` 由装配器**实测统计**（数该 ref 在 ``template.sessions`` 里出现
    几次），**不假设它等于 ``weekly_frequency``**，并作为字段留痕。
    """
    pkg = assemble(_unit_factor_profile(), rp.templates()["RED-END-ABN-01"], _AS_OF,
                   exercises=rp.exercises())
    blocks = _by_ref(pkg)
    assert blocks["interval_run"].sessions_per_week == 4
    assert blocks["interval_run"].weekly_volume == 48.0     # 12 min/课 × 4 课
    assert blocks["compound_circuit"].sessions_per_week == 4
    assert blocks["compound_circuit"].weekly_volume == 120.0  # 30 reps/课 × 4 课


def test_every_block_appears_in_every_session_of_the_real_templates():
    """**P5-A2 的守卫**：真仓 18 套，每个 block 的 ``sessions_per_week == weekly_frequency``。

    ⚠️ **这条今天全绿**，它的价值是「专家改坏了会立刻变红提示」（例如让某个动作只出现在
    2 课里）。而装配器**仍按实测统计**——那是数据的性质、不是结构的保证，不因为有一条
    测试盯着就改成假设。

    块数加权的分布字面写死（亲扫：按 ``exercise_ref`` 去重是 ``{2: 12, 3: 14, 4: 16}``
    共 42 个 ref；乘以各自的 ``sessions_per_week`` 得块数加权 ``{2: 24, 3: 42, 4: 64}``
    共 **130** 个 block，与简报 P5-A2 的分布逐格相符）。
    """
    store, lib = rp.templates(), rp.exercises()
    assert len(store) == 18
    weighted: dict[int, int] = {}
    for template_id in sorted(store):
        template = store[template_id]
        pkg = assemble(_unit_factor_profile(), template, _AS_OF, exercises=lib)
        first_week_blocks = [b for s in pkg.weeks[0].sessions for b in s.blocks]
        for block in first_week_blocks:
            assert block.sessions_per_week == template.weekly_frequency, (
                template_id, block.exercise_ref
            )
            weighted[block.sessions_per_week] = weighted.get(block.sessions_per_week, 0) + 1
    assert weighted == {2: 24, 3: 42, 4: 64}
    assert sum(weighted.values()) == 130


# ---------------------------------------------------------------------------
# 第 4 步：4 周递进
# ---------------------------------------------------------------------------


def test_four_week_progression_applies_week_deltas_in_order():
    """``week_deltas`` **按序**套到第 1..4 周，且第 4 周**小于**第 1 周（末项 0.85）。

    期望值 ``38.4 / 40.3 / 42.2 / 32.6`` 与 ``96.0 / 100.8 / 105.6 / 81.6`` 是本文件开头
    那段独立重算的结果，与派单的算例表逐格相符。
    ⚠️ 「顺序对」与「计数对」是两件事：把 ``week_deltas`` 反过来用，四周的**集合**不变、
    而**序列**变，故这里断言的是序列。
    """
    pkg = assemble(_profile(), rp.templates()["RED-END-ABN-01"], _AS_OF,
                   exercises=rp.exercises())
    assert [week.week for week in pkg.weeks] == [1, 2, 3, 4]
    assert [week.delta for week in pkg.weeks] == [1.0, 1.05, 1.1, 0.85]
    assert [_by_ref(pkg, n)["interval_run"].weekly_volume for n in (1, 2, 3, 4)] == [
        38.4, 40.3, 42.2, 32.6]
    assert [_by_ref(pkg, n)["compound_circuit"].weekly_volume for n in (1, 2, 3, 4)] == [
        96.0, 100.8, 105.6, 81.6]
    assert pkg.weeks[3].sessions[0].blocks[0].weekly_volume < \
        pkg.weeks[0].sessions[0].blocks[0].weekly_volume
    # 每一周的课数与每课的 block 数都相同（递进只改量、不改结构）
    for week in pkg.weeks:
        assert len(week.sessions) == 4
        for session in week.sessions:
            assert [b.exercise_ref for b in session.blocks] == list(_RED_END_REFS)


def test_week_deltas_length_mismatch_is_rejected_not_silently_truncated():
    """``len(week_deltas) != microcycle_weeks`` → ``ValueError``，**不静默截断**。

    加载器 :func:`app.refdata_prescription._week_deltas` 已经拦过一道（它的 docstring 逐字
    写着这个失效形态：「3 项配 4 周时『容错』写法会让第 4 周悄悄回到第 3 周的量，恰好在
    最该减量的那一周加量」）。装配器仍要抛，因为它可能被喂进一个手工构造的 ``Template``
    ——两道都要有（口径同 ``exercise_ref``）。
    """
    template = dataclasses.replace(
        rp.templates()["RED-END-ABN-01"], week_deltas=(1.0, 1.05, 1.1)
    )
    with pytest.raises(ValueError) as excinfo:
        assemble(_profile(), template, _AS_OF, exercises=rp.exercises())
    assert "3" in str(excinfo.value) and "4" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 第 5 步：动作视频 URL
# ---------------------------------------------------------------------------


def test_every_block_carries_a_video_url_from_the_exercise_library():
    """URL 与中文名都取自**注入的动作库**，装配器自己不读 DB、不读盘。

    ``video_url`` 是 spec §7.3 ``:499`` 那一步（学生端二维码）的落点；加载器已经校验过它
    非空，故这里只钉「取的是动作库那一份、且逐 block 都有」。
    """
    lib = rp.exercises()
    pkg = assemble(_unit_factor_profile(), rp.templates()["RED-END-ABN-01"], _AS_OF,
                   exercises=lib)
    for week in pkg.weeks:
        for session in week.sessions:
            for block in session.blocks:
                spec = lib[block.exercise_ref]
                assert block.video_url == spec.video_url
                assert block.video_url.strip()
                assert block.exercise_name == spec.name
                assert block.exercise_name.strip()


def test_unknown_exercise_ref_is_rejected_at_assembly_time():
    """``exercise_ref`` 不在注入的映射里 → ``ValueError``（**第二道**，不是 ``KeyError``）。

    加载器 :func:`app.refdata_prescription._block` 是第一道；两道都要有，因为装配器可能被
    喂进一个手工构造的 ``Template``，也可能被喂进一份**与模板不同版本**的动作库
    （例如专家删了一个动作却忘了改 18 套模板）——后一种情况加载器看不见。
    """
    template = rp.templates()["RED-END-ABN-01"]
    session = template.sessions[0]
    dangling = dataclasses.replace(session.blocks[0], exercise_ref="no_such_exercise")
    template = dataclasses.replace(
        template, sessions=(dataclasses.replace(session, blocks=(dangling,)),)
    )
    with pytest.raises(ValueError) as excinfo:
        assemble(_profile(), template, _AS_OF, exercises=rp.exercises())
    assert "no_such_exercise" in str(excinfo.value)


def test_impact_level_comes_from_the_exercise_library_not_the_template():
    """**P5-A8**：``impact_level`` 从 :class:`ExerciseSpec`（动作库）取，不从 ``Block`` 取。

    **理由**：``exercises.yaml`` 是 ``impact_level`` 的**源**（它是 ``exercise`` 表的 seed
    源），模板里那一份是**冗余副本**（Plan02 账本 P2-B2）。安全规则（5.3）必须读源，否则
    「专家改了动作库、忘了改 18 套模板」会让安全替换**静默失效**——一个被改成 ``low`` 的
    高冲击动作永远不会被换成低冲击替身，而全链路没有一处报错。

    ⚠️ 加载器今天**会**拒绝两份不一致的模板，故这一档在生产路径上不可达；本条钉的是
    **装配器读的是哪一份**，用 :func:`dataclasses.replace` 造一个矛盾的副本（不动 YAML，
    故 18 个指纹一个都不动）。
    """
    from app.domain.prescription.exercises import ImpactLevel

    template = rp.templates()["RED-END-ABN-01"]
    session = template.sessions[0]
    lied = tuple(
        dataclasses.replace(block, impact_level=ImpactLevel.LOW) for block in session.blocks
    )
    template = dataclasses.replace(template, sessions=(
        dataclasses.replace(session, blocks=lied), *template.sessions[1:]))
    pkg = assemble(_unit_factor_profile(), template, _AS_OF, exercises=rp.exercises())
    assembled = _by_ref(pkg)
    # interval_run 在动作库里是 high；模板谎称 low，装配结果必须仍是 high
    assert assembled["interval_run"].impact_level is ImpactLevel.HIGH
    assert assembled["compound_circuit"].impact_level is ImpactLevel.MEDIUM


# ---------------------------------------------------------------------------
# 第 6 步：快照
# ---------------------------------------------------------------------------


def test_assembly_snapshot_keys_are_exactly_the_pinned_set():
    """键**恰好** 12 个、且**顺序**也钉死（多一个少一个都红）。

    **这一列是 spec §4.3 可追溯性在处方侧的落点**：有了它，任一条处方都能离线复算
    （公式、HRmax、年龄、业务日、耐力得分、系数与档名、性别系数、模板 id 与版本、
    四周系数、未修正的周量基数）。
    ⚠️ 断言的是 ``tuple(snapshot)`` 而不是 ``set(snapshot)``：``dict`` 保序，故顺序也可钉；
    钉顺序的额外收益是「谁往中间插一个键」与「谁往末尾追加一个键」报的是同一条红。
    """
    pkg = assemble(_profile(), rp.templates()["RED-END-ABN-01"], _AS_OF,
                   exercises=rp.exercises())
    assert tuple(pkg.assembly_snapshot) == _SNAPSHOT_KEYS
    assert len(pkg.assembly_snapshot) == 12
    assert sorted(_SNAPSHOT_KEYS) != list(_SNAPSHOT_KEYS), "基线不是字母序，故上一条真在钉顺序"


def test_assembly_snapshot_values_are_the_independently_recomputed_literals():
    """12 个键的**值**逐个字面写死（``RED-END-ABN-01``、男 20 岁、``endurance_score = 50``）。

    ``as_of`` 落进快照时取 ``isoformat()``：``datetime.date`` **不是 JSON 可序列化的**，而
    这个快照要落进 ``prescription.assembly_snapshot`` 那个 JSON 列（Task 6）。
    ``weekly_volume_base`` = **未乘个体系数、未乘 ``week_deltas``** 的周量，
    **按 ``volume_unit`` 分列**（F1-1）：``min`` 档 ``4 课 × 12 = `` **48.0**、
    ``reps`` 档 ``4 课 × 30 = `` **120.0**。
    ⚠️ 改前它是把两者加起来的 ``168.0``——**一个把分钟和次数加在一起的数**，而它要落进
    JSON 列并被前端展示（那与 P5-A1 自己立的「两种单位不可通约」互相打脸）。
    ⚠️ 整条 ``==`` 断言同时钉住「它是只读映射也能与普通 ``dict`` 字面量相等」：
    ``dict.__eq__`` 不看子类型，故 ``_ReadOnlyVolumeBase({...}) == {...}`` 为真（亲跑）。
    """
    pkg = assemble(_profile(), rp.templates()["RED-END-ABN-01"], _AS_OF,
                   exercises=rp.exercises())
    assert pkg.assembly_snapshot == {
        "formula": "tanaka",
        "hrmax": 194.0,
        "age": 20,
        "as_of": "2026-10-06",
        "endurance_score": 50.0,
        "volume_factor": 0.8,
        "volume_factor_band": "low",
        "sex_factor": 1.0,
        "template_id": "RED-END-ABN-01",
        "template_version": "1.0",
        "week_deltas": [1.0, 1.05, 1.1, 0.85],
        "weekly_volume_base": {"min": 48.0, "reps": 120.0},
    }


def test_weekly_volume_base_is_split_by_volume_unit():
    """**F1-1 的①**：``weekly_volume_base`` 是**按单位分列**的映射，逐个字面值写死。

    三套模板各代表一种键集形状（亲扫 18 套得到的分布是
    ``{("min",): 10, ("reps",): 6, ("min", "reps"): 2}``）：

    ==================  ======  ==========================================  ==========================
    模板                 层      逐课 block 的 base                            ``weekly_volume_base``
    ==================  ======  ==========================================  ==========================
    ``RED-END-ABN-01``   红      ``interval_run`` 12 min + ``compound_circuit`` 30 reps，4 课
    ``GRN-END-NOR-14``   绿      ``orienteering`` 12 min + ``interest_ball_games`` 12 min，2 课
    ``YEL-STR-ABN-09``   黄      ``bodyweight_resistance`` 30 reps + ``band_resistance`` 30 reps，3 课
    ==================  ======  ==========================================  ==========================

    独立重算：红 ``min`` = 4 × 12 = **48.0**、``reps`` = 4 × 30 = **120.0**；
    绿 ``min`` = 2 × (12 + 12) = **48.0**（只有一个单位）；
    黄 ``reps`` = 3 × (30 + 30) = **180.0**（只有一个单位）。
    ⚠️ 绿层那套的 ``min`` 档恰好也是 48.0，与红层的 ``min`` 档同值而**来源完全不同**
    （2 课 × 2 个 12 min 对 4 课 × 1 个 12 min）——这正是「按单位分列」比「一个总数」
    信息量大的地方，也是它为什么不能被加成一个数。
    """
    lib = rp.exercises()
    store = rp.templates()
    expected = {
        "RED-END-ABN-01": {"min": 48.0, "reps": 120.0},
        "GRN-END-NOR-14": {"min": 48.0},
        "YEL-STR-ABN-09": {"reps": 180.0},
    }
    for template_id, want in expected.items():
        snapshot = assemble(_profile(), store[template_id], _AS_OF,
                            exercises=lib).assembly_snapshot
        got = snapshot["weekly_volume_base"]
        assert got == want, template_id
        # 键序也钉住：按 block 的首次出现序累加，不是字母序
        assert tuple(got) == tuple(want), template_id


def test_weekly_volume_base_keys_are_a_subset_of_volume_units():
    """**F1-1 的②**：键集 ⊆ :data:`VOLUME_UNITS`，且**不含 ``"unspecified"``**（真仓 18 套）。

    ``"unspecified"`` 是 5.3 追加的 addon block 那一档，而 ``assemble`` 跑在
    :func:`app.domain.prescription.safety.apply_safety` **之前**，故它在这里**不可能**出现。
    ⚠️ 这一条同时钉住「键集**不是**硬写死的」：18 套里有 **10** 套只给 ``min``、**6** 套只给
    ``reps``、**2** 套两个都给（分布字面写死在
    :data:`_VOLUME_BASE_KEYSET_DISTRIBUTION`，由一份**不 import 被测模块**的 YAML 探针
    独立算出）。谁把键集写成固定的 ``{"min", "reps"}``，那 16 套立刻红。
    """
    lib, store = rp.exercises(), rp.templates()
    assert len(store) == 18
    distribution: dict[tuple[str, ...], int] = {}
    for template_id in sorted(store):
        snapshot = assemble(_profile(), store[template_id], _AS_OF,
                            exercises=lib).assembly_snapshot
        base = snapshot["weekly_volume_base"]
        assert set(base) <= set(VOLUME_UNITS), template_id
        assert "unspecified" not in base, template_id
        assert base, f"{template_id} 的 weekly_volume_base 是空的"
        assert all(isinstance(value, float) for value in base.values()), template_id
        keyset = tuple(base)
        distribution[keyset] = distribution.get(keyset, 0) + 1
    assert distribution == _VOLUME_BASE_KEYSET_DISTRIBUTION
    assert sum(distribution.values()) == 18


def test_weekly_volume_base_is_read_only():
    """**F1-1 的③**：它是**只读**的——8 个 mutator 一律 ``TypeError``。

    派单点名的那一条是 ``snap["weekly_volume_base"]["min"] = 0``；本条把 ``dict`` 的
    **全部 8 个**改写入口都走一遍。⚠️ 只挡 ``__setitem__`` 是**不够**的：亲跑坐实
    ``d |= {...}`` 走的是 ``dict.__ior__`` 的 C 实现、**绕过**被覆盖的 ``update``，
    于是「看起来只读、其实一改就穿」。8 个入口是
    ``__setitem__`` / ``__delitem__`` / ``pop`` / ``popitem`` / ``clear`` / ``update`` /
    ``setdefault`` / ``__ior__``。

    ⚠️ **为什么不是 ``types.MappingProxyType``**（亲跑取证，两条都写进报告）：

    * ``types`` **不在** :data:`tests.architecture.test_domain_purity.ALLOWED_MODULES` 里
      ——往 ``assembler.py`` 临时插一句 ``import types``，
      ``test_domain_imports_stay_within_the_allow_list`` 立刻报 ``assembler.py:148: types``。
    * ``MappingProxyType`` **不是 JSON 可序列化的**——亲跑
      ``json.dumps({"weekly_volume_base": types.MappingProxyType({...}})`` 抛
      ``TypeError: Object of type mappingproxy is not JSON serializable``，
      而这个快照要落进 ``prescription.assembly_snapshot`` 那个 JSON 列（Task 6）。

    故落地的是一个**屏蔽了 mutator 的 ``dict`` 子类**：``isinstance(m, dict) is True``
    → ``json`` 的 C 编码器走 ``PyDict_Next`` 快路径、认它；同时 8 个入口全 ``TypeError``。
    **两条约束（只读 + JSON 化）在这里是互斥的，只有 ``dict`` 子类同时满足**——
    这是本轮唯一能同时守住两边的构造，取舍写进 :mod:`app.domain.prescription.assembler`
    的模块 docstring。
    """
    base = assemble(_profile(), rp.templates()["RED-END-ABN-01"], _AS_OF,
                    exercises=rp.exercises()).assembly_snapshot["weekly_volume_base"]
    # 派单点名的那一条
    with pytest.raises(TypeError):
        base["min"] = 0
    mutators = (
        ("__setitem__", lambda: base.__setitem__("min", 0.0)),
        ("__delitem__", lambda: base.__delitem__("min")),
        ("pop", lambda: base.pop("min")),
        ("popitem", lambda: base.popitem()),
        ("clear", lambda: base.clear()),
        ("update", lambda: base.update({"min": 0.0})),
        ("setdefault", lambda: base.setdefault("min", 0.0)),
        ("__ior__", lambda: base.__ior__({"reps": 0.0})),
    )
    for name, mutate in mutators:
        with pytest.raises(TypeError):
            mutate()
    # 8 次尝试之后一个字都没变
    assert base == _RED_END_VOLUME_BASE
    assert tuple(base) == ("min", "reps")


def test_weekly_volume_base_survives_copy_and_pickle():
    """只读映射在 ``copy`` / ``deepcopy`` / ``pickle`` 之后**仍是同一类型、同一内容**。

    ⚠️ 这一条不是装饰：**屏蔽 ``__setitem__`` 会顺手打断 ``copy``**。亲跑坐实，一个只挡了
    7 个 mutator、没有 ``__reduce__`` 的 ``dict`` 子类，``copy.copy(m)`` 会抛
    ``TypeError``——因为 ``copy._reconstruct`` 正是靠 ``y[key] = value`` 逐项重建的。
    ``TrainingPackage`` 是 frozen dataclass，Task 6/8 完全可能对整包做一次 ``deepcopy``；
    那时一个会炸的只读映射就是一个埋好的地雷。落地办法是给它一个 ``__reduce__``
    （``(_ReadOnlyVolumeBase, (dict(self),))``），三条路径一次修好。
    """
    base = assemble(_profile(), rp.templates()["RED-END-ABN-01"], _AS_OF,
                    exercises=rp.exercises()).assembly_snapshot["weekly_volume_base"]
    for label, cloned in (("copy", copy.copy(base)),
                          ("deepcopy", copy.deepcopy(base)),
                          ("pickle", pickle.loads(pickle.dumps(base)))):
        assert type(cloned) is type(base), label
        assert cloned == _RED_END_VOLUME_BASE, label
        assert cloned is not base, label
        with pytest.raises(TypeError):
            cloned["min"] = 0.0


def test_assembly_snapshot_is_json_serialisable():
    """**F1-1 的④（本轮最容易漏的一条）**：整个 ``assembly_snapshot`` 真能 JSON 化。

    判据是全局纪律那一条：``json.dumps(snap, allow_nan=False)``。
    ⚠️ ``allow_nan=False`` 是承重的：它会把 ``NaN`` / ``Infinity`` 变成 ``ValueError``，
    而 ``endurance_score`` 与 ``volume_factor`` 都是 float——一个 ``0/0`` 就能让整个快照
    在 Task 6 落库时炸掉，且炸点离真因很远。
    ⚠️ 本条同时是「``weekly_volume_base`` 用 ``dict`` 子类而不用 ``MappingProxyType``」
    这个取舍的**唯一守卫**：换成 ``MappingProxyType`` 或
    ``collections.abc.Mapping`` 的自定义子类，这一条立刻红
    （亲跑：``Object of type mappingproxy is not JSON serializable``）。
    **round-trip 之后 ``weekly_volume_base`` 变回普通 ``dict``**——只读性只在进程内成立，
    落库再读回来就是可变的了，这一条如实写进 :mod:`app.domain.prescription.assembler`
    的 docstring（硬规矩 #39）。
    """
    pkg = assemble(_profile(), rp.templates()["RED-END-ABN-01"], _AS_OF,
                   exercises=rp.exercises())
    text = json.dumps(pkg.assembly_snapshot, allow_nan=False, ensure_ascii=False)
    # 逐字面：序列化文本里那一格必须是分列后的两个数，不是加起来的 168.0
    assert '"weekly_volume_base": {"min": 48.0, "reps": 120.0}' in text
    assert "168.0" not in text
    # round-trip 之后 12 个键一个不落、名与序都不变
    restored = json.loads(text)
    assert tuple(restored) == _SNAPSHOT_KEYS
    assert len(restored) == 12
    assert restored["weekly_volume_base"] == _RED_END_VOLUME_BASE
    # round-trip 之后它是**普通 dict**（只读性只在进程内成立，见 docstring）
    assert type(restored["weekly_volume_base"]) is dict
    restored["weekly_volume_base"]["min"] = 0.0
    assert pkg.assembly_snapshot["weekly_volume_base"] == _RED_END_VOLUME_BASE
    # endurance_score is None 那一档也要能序列化（null，不是 NaN）
    unknown = assemble(_profile(endurance_score=None), rp.templates()["RED-END-ABN-01"],
                       _AS_OF, exercises=rp.exercises())
    assert '"endurance_score": null' in json.dumps(
        unknown.assembly_snapshot, allow_nan=False)


def test_assembly_snapshot_is_reproducible():
    """同一 ``profile`` + 同一 ``template`` + 同一 ``as_of`` 装配两次 → **逐字段相同**。

    ``as_of`` 是 ``date`` 不是 ``datetime``，故快照里不含执行时刻；这是「离线复算」能成立的
    前提（spec §1.3）。整包相等也一起断言：``TrainingPackage`` 是 frozen dataclass，
    逐字段相等即 ``==``。
    """
    template, lib = rp.templates()["RED-END-ABN-01"], rp.exercises()
    first = assemble(_profile(), template, _AS_OF, exercises=lib)
    second = assemble(_profile(), template, _AS_OF, exercises=lib)
    assert first.assembly_snapshot == second.assembly_snapshot
    assert first == second


# ---------------------------------------------------------------------------
# 产出类型
# ---------------------------------------------------------------------------


def test_assemble_produces_an_unpaused_package_of_the_pinned_types():
    """``paused`` 一律 ``False``（置位是 5.4 的 ``OverrideKind.PAUSE`` 的活）。

    **字段在 5.2 就定义**是刻意的（简报 5.2 的 Produces 段）：否则 5.4 要回头改一个已定稿的
    产出类型，而那是 Plan 01 吃过 6 次的亏——改了 Interfaces 却没改照抄它的 Step。
    """
    pkg = assemble(_unit_factor_profile(), rp.templates()["GRN-END-NOR-14"], _AS_OF,
                   exercises=rp.exercises())
    assert isinstance(pkg, TrainingPackage)
    assert pkg.paused is False
    assert pkg.template_id == "GRN-END-NOR-14"
    assert pkg.template_version == "1.0"
    assert len(pkg.weeks) == 4
    assert all(isinstance(week, AssembledWeek) for week in pkg.weeks)
    assert all(isinstance(session, AssembledSession)
               for week in pkg.weeks for session in week.sessions)
    assert all(isinstance(block, AssembledBlock)
               for week in pkg.weeks for session in week.sessions
               for block in session.blocks)
    # 绿层 weekly_frequency = 2 → 每周 2 课，每课 2 个 block
    assert [len(week.sessions) for week in pkg.weeks] == [2, 2, 2, 2]
    assert [[b.exercise_ref for b in s.blocks] for s in pkg.weeks[0].sessions] == [
        ["orienteering", "interest_ball_games"],
        ["orienteering", "interest_ball_games"],
    ]
    # 绿层：base 12 min × 2 课 = 24.0；系数 1.0、第 1 周 delta 1.0
    assert _blocks(pkg)[0].weekly_volume == 24.0
    assert _blocks(pkg)[0].sessions_per_week == 2
    assert _blocks(pkg)[0].volume_unit == "min"


def test_assemble_does_not_mutate_the_injected_template_or_library():
    """纯函数：注入的 ``Template`` 与动作库一个字都不改。

    生产路径上两者都是 :class:`types.MappingProxyType` / frozen dataclass（就地改写会当场
    ``TypeError``），但「改不动」不等于「不该试」（简报 5.5 Step 5 的原话）：本条用**副本
    比对**证明装配器没有偷偷换掉 ``Block.structure`` 之类的东西。
    """
    template, lib = rp.templates()["RED-END-ABN-01"], rp.exercises()
    before_template = dataclasses.replace(template)
    before_refs = {ref: dataclasses.replace(spec) for ref, spec in lib.items()}
    assemble(_profile(), template, _AS_OF, exercises=lib)
    assert template == before_template
    assert len(lib) == len(before_refs)
    for ref, spec in before_refs.items():
        assert lib[ref] == spec
    # Block.structure 是只读视图：装配器若试图就地改写会 TypeError，故这里只钉「值没变」
    assert dict(template.sessions[0].blocks[0].structure) == {
        "sets": 4, "work_min": 3, "rest_min": 2}

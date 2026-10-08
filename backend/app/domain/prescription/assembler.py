"""spec §7.3 的六步装配：模板 × 学生 → 一个可复现、可离线复算的 4 周训练包
（Plan 02 Task 5 的 5.2）。

**它是纯函数、不做 I/O**（Global Constraint #1）：动作库 ``exercises`` 与业务日 ``as_of``
都由调用方注入（生产路径上是 :func:`app.refdata_prescription.exercises` 那个进程内单例与
``app/pipeline/daily.py`` 的业务日）。本模块不读盘、不读 DB、不读时钟，故「同一份输入 →
同一个结果」（spec §1.3），:func:`assemble` 也因此可以被 :mod:`tests.domain` 直接穷举。

--------------------------------------------------------------------------

**六步口径**（简报 5.2 那张表；每一步的守卫都在
``tests/domain/test_prescription_assembler.py`` 里点名）：

1. **HRmax**：``profile.measured_hrmax`` 非空则用它，否则
   :func:`app.domain.prescription.intensity.hrmax` 的 Tanaka。``profile.age`` 由**调用方**
   从 ``birth`` 与 ``as_of`` 算好传入（不让装配器自己碰日期，避免两个所有者），但装配器
   **必须对账** ``age == age_from(birth, as_of)``——一个 ``as_of`` 传成去年的调用方会静默
   装配出一个按错误年龄算 HRmax 的训练包，而这道闸门只值一次减法。
2. **目标心率区间**：只对 ``intensity.type == "hrmax_pct"`` 的 block 算。``onerm_pct`` /
   ``rpe`` / ``none`` 的 ``hr_zone`` 一律 ``None``——**不给非心率类动作硬塞一个心率区间**：
   一个 ``70% 1RM`` 的复合循环被标上「116–136 bpm」会让学生以为要盯着心率做，而那恰恰是
   力量动作不该有的指令。
3. **周训练总量** = 每课基准量 × 周内课次 × 个体修正系数（下面两节各有一段）。
4. **4 周递进**：第 N 周再乘 ``week_deltas[N-1]``。
5. **动作视频 URL 与中文名**：从注入的动作库取（spec §7.3 ``:499`` 的学生端二维码）。
6. **快照**：全部输入输出写进 :attr:`TrainingPackage.assembly_snapshot`。

--------------------------------------------------------------------------

**⚠️ 基准量口径（P5-A1：``Block.structure`` 里没有「量」这个字段，必须自己定；
登记 spec §14 新 #36）**

实测 130 个 block 的 ``structure`` **只有两种键集、无第三种、无交集**（亲扫：**78** 个
``{sets, work_min, rest_min}``、**52** 个 ``{rounds, reps}``，78 + 52 = 130 ✓），且**取值
全部相同**（时长类一律 ``{4, 3, 2}``、次数类一律 ``{3, 10}``）：

===============  =====  ============================  ==================  ==============
形状              个数   键集                          ``base`` 口径        ``volume_unit``
===============  =====  ============================  ==================  ==============
时长类            **78**  ``{sets, work_min, rest_min}``  ``work_min × sets``  ``"min"``
次数类            **52**  ``{rounds, reps}``              ``rounds × reps``    ``"reps"``
===============  =====  ============================  ==================  ==============

* **``rest_min`` 不计入量**：它是**恢复**、不是负荷。把休息算进训练量会让「减量 20%」
  **同时缩短恢复时间**，而对红层学生缩短恢复恰恰是危险的那一半（减量本该降的是负荷，
  恢复时间要保住甚至加长）。守卫是
  ``test_rest_min_is_not_counted_as_volume``（把 ``rest_min`` 从 2 改成 20，量一个字不变）。
* **两种单位不可通约** → :attr:`AssembledBlock.volume_unit` 是**必需字段**、不是可选修饰。
  一个裸 ``float`` 无法回答「48.0 是分钟还是次数」，那会让 spec §4.3 的可追溯性断在这一环。
  第三档 ``"unspecified"`` 是给 5.3 的追加 addon 留的（``Addon`` 没有 ``structure``）。
* **既不是这两种形状 → ``ValueError``，不得静默取 0**：量变 0 会让训练包**看起来完全正常**
  （结构齐全、文案齐全、快照齐全）而每个 block 都是空的。⚠️ 加载器
  :func:`app.refdata_prescription._structure` **刻意不约束键集**（它自己的 docstring 逐字
  写着「spec 只给了两个字面例子…故本 Task 不编一个」），故 :func:`_base_volume` 是这个
  形状**唯一**的守卫。
* **不重复校验键的值类型**（单一所有者，简报 P5-A1）。⚠️ **代价必须写明**（硬规矩 #39）：
  加载器只查「``structure`` 是个非空映射、键全是字符串」，**不查值是不是数字**，故一份
  ``structure: {sets: "4", work_min: 3, rest_min: 2}`` 的 YAML 能加载成功、然后在
  :func:`_base_volume` 里得到 ``float(3 * "4") = 444.0`` 这个**静默错值**（两个值都是字符串
  时反而 ``TypeError``、是响的）。修法是在加载器那一侧补值类型校验；本 Task 不改
  ``app/refdata_prescription.py``（不在派单的文件清单里），故如实记录为关切。

**⚠️ ``sessions_per_week`` 由装配器实测统计**（P5-A2：数该 ``exercise_ref`` 在
``template.sessions`` 里出现几次），**不假设它等于 ``weekly_frequency``**。实测它今天恰好
恒等（130 个 block 的分布 ``{2: 24, 3: 42, 4: 64}`` = 绿全 2 / 黄全 3 / 红全 4），但那是
**数据的性质、不是结构的保证**——专家完全可以让某个动作只出现在 2 课里。守卫
``test_every_block_appears_in_every_session_of_the_real_templates`` 今天全绿，它的价值是
「专家改坏了会立刻变红提示」，而装配器**仍按实测统计**（正确行为，不因为有测试盯着就改成
假设）。字段 :attr:`AssembledBlock.sessions_per_week` 把统计结果留痕，于是
``weekly_volume`` 这个数**自己就能解释自己**（``base × sessions_per_week × 系数 × delta``）。

--------------------------------------------------------------------------

**⚠️ 三档个体修正系数（spec 最欠定的一步，口径自己定；登记 spec §14 #32）**

* ``endurance_score`` = ``vital_capacity`` 与 ``distance_run`` 两项国标得分的**算术均值**
  （``float``，因为 :data:`app.domain.indicators.ITEM_BUCKET` 把这两项归 endurance 桶）。
  两项里只有一项有值时**取那一项、不取半值**；两项都无值时为 ``None``。
  ⚠️ **那个均值不是本模块算的**：``StudentProfile.endurance_score`` 由调用方
  （Task 6/7 的管道）算好传入，本模块只消费——否则「均值」这条口径就有两个住址
  （Global Constraint #3）。
* 档位：**``< 60`` → ``0.8``、``[60, 80)`` → ``1.0``、``>= 80`` → ``1.2``**（**半开、无缝
  无叠**——Ruling 9 更正原文的「60–79」：``endurance_score`` 是 float 均值，``79.5`` 会落在
  ``(79, 80)`` 的缝里，而 500 人里可能只有个位数、分布断言完全测不出来）。
* 性别修正：男 ``1.0`` / 女 ``0.9``。**最终系数 = 档位系数 × 性别系数，``round(…, 2)``**
  （⚠️ ``round`` 是承重的：``0.8 * 0.9`` 亲跑是 ``0.7200000000000001`` 而**不是** ``0.72``，
  Plan02 账本 P5-A6）。
* ``endurance_score is None`` → 系数 **``1.0``**（连性别修正也不做：``1.0`` 是「不知道就
  不动」的中性值，而 ``0.9`` 是一个**基于档位表**的修正，档位未知时它没有依据），档名置
  ``"unknown"``。**⚠️ 不另加第 13 个快照键**（P5-A7：那 12 个键是离线复算的契约，多一个
  键就废了）——信息已经在 :data:`VOLUME_FACTOR_BANDS` 的 ``"unknown"`` 里。
* ⚠️ **这套阈值指导文件没给**：它是**工程约定，不是运动生理学结论，须由体育专家确认**
  （spec §14 #32，归 Task 9 登记）。守卫钉的是「实现的就是这张表」，不是「这张表对」。

--------------------------------------------------------------------------

**⚠️⚠️ Ruling 133（本 Task 的头号约束）**：18 套模板的 130 个 block 里 **82** 个是
``intensity: {type: none}``，按层是 **绿 ``{none}`` / 黄 ``{none}`` / 红 ``{hrmax_pct, none,
onerm_pct}``**——spec §7.2 ``:487`` **只给了红层的强度数值**（60–70% HRmax、70% 1RM），
黄层绿层只有动作名。故：

* **「模板没给强度」是常态、不是例外**。:data:`_NO_INTENSITY_TEXT` 是**显式的一档**，
  既不回落到 ``hrmax_pct`` 的默认值（那会给学生一个模板从没要求过的心率区间），
  也不留空字符串（学生端会看到一格空白，分不清「不需要强度区间」与「忘了填」——与
  ``exercises.yaml`` 的 ``equipment: none`` 同一条理由）。
* 这 82 个 block 的 ``hr_zone`` 一律 ``None``。
* ``rpe`` 在真仓出现 **0** 次（P5-A5），但它是 :data:`app.domain.prescription.templates.INTENSITY_TYPES`
  的第四档，**不可达也必须被覆盖**（Global Constraint #2：domain 分支 100%，简化版不豁免）；
  守卫用手工构造的 ``Intensity(type="rpe", value=7.0)``（**0–10 标度上的合法值**，
  值域与出处见 :func:`_render` 的 docstring）。

--------------------------------------------------------------------------

⚠️ **本模块不 import ``datetime``**（与 :mod:`app.domain.prescription.intensity` 同一条
纪律）：:data:`tests.architecture.test_domain_purity.ALLOWED_MODULES` 实测 =
``{dataclasses, enum, collections, collections.abc, numpy, typing}``，**``datetime`` 不在其中**。
故 :attr:`StudentProfile.birth` 与 :func:`assemble` 的 ``as_of`` 标注写成**前向引用字符串**
``"dt.date"``，运行时只读它们的 ``year`` / ``month`` / ``day`` / ``isoformat``。
**代价**：``typing.get_type_hints(assemble)`` 会抛 ``NameError``（理由与处置见
:mod:`app.domain.prescription.intensity` 模块 docstring 的第 5 段）。

⚠️ **``assembly_snapshot`` 里的 ``as_of`` 是 ``isoformat()`` 之后的字符串**，不是 ``date``
对象：``datetime.date`` **不是 JSON 可序列化的**，而这个快照要落进
``prescription.assembly_snapshot`` 那个 JSON 列（Task 6）。同一理由，``week_deltas`` 落进
快照时是 ``list`` 而不是 ``tuple``。

⚠️ **``weekly_volume_base`` 按 ``volume_unit`` 分列**（fix round 1 / F1-1；控制者采纳实现者
上一轮的异议）。它是 ``Mapping[str, float]`` 而**不是** ``float``：

* **口径**：键 = **实际出现过的** ``volume_unit``；值 = 该单位下的周量之和，``round(…, 1)``。
  ``RED-END-ABN-01`` 亲算得 ``{"min": 48.0, "reps": 120.0}``（``min`` = 4 课 × ``3 × 4``、
  ``reps`` = 4 课 × ``3 × 10``）。
* **改前它是 ``168.0`` = ``48.0 min + 120.0 reps``**——**一个把分钟和次数加在一起的数没有
  意义**，而它要落进 ``prescription.assembly_snapshot`` 这个 JSON 列、并在 Plan 03/04 被前端
  读出来展示。那与本模块自己立的「两种单位不可通约」（P5-A1）互相打脸，故改。
* **键集不写死**：18 套模板亲扫的键集分布是 ``{("min",): 10, ("reps",): 6, ("min", "reps"): 2}``
  ——**16/18 套只有一个单位**。``"unspecified"`` 那一档**不出现**：``assemble`` 跑在
  :func:`app.domain.prescription.safety.apply_safety` **之前**，那时还没有 addon block
  （守卫 ``test_weekly_volume_base_keys_are_a_subset_of_volume_units``）。
* **实现按 ``(session, block)`` 逐次累加 ``base``**，而口径写的是「该单位下所有 block 的
  ``base × sessions_per_week`` 之和」。两者**逐格相等**（真仓 18/18 亲跑对拍相同），因为
  ``sum(base over 每一次出现) == base × 该 ref 的出现次数 == base × sessions_per_week``。
  选逐次累加是因为它对「同一 ``exercise_ref`` 在不同课里 ``structure`` 不同」这一档更稳健
  ——那档下 ``base × sessions_per_week`` 得先挑一个 ``base``，而挑哪一个没有答案
  （加载器不约束「同 ref 同 structure」）。今天真仓没有这一档。

⚠️ **只读性与 JSON 化在这里是互斥的两条约束，落地构造是它们唯一的交集**（硬规矩 #39，
两条取舍都是亲跑取证）：

* **拿不到 ``types.MappingProxyType``**：``types`` **不在**
  :data:`tests.architecture.test_domain_purity.ALLOWED_MODULES` 里。亲跑：往本文件插一句
  ``import types``，``test_domain_imports_stay_within_the_allow_list`` 立刻报
  ``assembler.py:148: types``（对照：不插时 4 passed、退出码 0）。往 allow-list 加模块是
  **扩大 domain 可用面**的架构决策，不是一个 Task 能顺手做的（与 ``datetime`` / ``math``
  同一条纪律）。
* **``MappingProxyType`` 也不是 JSON 可序列化的**：亲跑 ``json.dumps({"k":
  types.MappingProxyType({"min": 48.0})})`` 抛 ``TypeError: Object of type mappingproxy is
  not JSON serializable``，且 ``isinstance(proxy, dict) is False``。
  ``collections.abc.Mapping`` 的自定义子类同理不在 ``json`` 的默认类型表里。
* 故 :class:`_ReadOnlyVolumeBase` 是一个**屏蔽了全部 8 个 mutator 的 ``dict`` 子类**：
  ``isinstance(m, dict) is True`` → ``json`` 的 C 编码器认它（亲跑
  ``json.dumps(m, allow_nan=False)`` 给 ``{"min": 48.0, "reps": 120.0}``），同时
  ``m["min"] = 0`` / ``del`` / ``pop`` / ``popitem`` / ``clear`` / ``update`` / ``setdefault``
  / ``|=`` 八个入口一律 ``TypeError``。⚠️ **``|=`` 必须单独挡**：亲跑坐实它走
  ``dict.__ior__`` 的 C 实现、**绕过**被覆盖的 ``update``，只挡 7 个的话它就是那个
  「看起来只读、其实一改就穿」的口子。
* ⚠️ **只挡 mutator 会顺手打断 ``copy``**：亲跑，没有 ``__reduce__`` 时 ``copy.copy(m)``
  抛 ``TypeError``——``copy._reconstruct`` 正是靠 ``y[key] = value`` 逐项重建的。
  故给它一个 ``__reduce__``，``copy`` / ``deepcopy`` / ``pickle`` 三条路径一次修好
  （守卫 ``test_weekly_volume_base_survives_copy_and_pickle``）。
* ⚠️ **只读性只在进程内成立**：落进 JSON 列再读回来就是普通 ``dict``、可变的了
  （守卫 ``test_assembly_snapshot_is_json_serialisable`` 的 round-trip 那一段钉住了这件事，
  并证明改写读回来的那一份**不会**回写到进程内的快照）。跨进程没有免费的不可变，
  这一格如实记录。

⚠️ **本模块守不住什么**（硬规矩 #39）：

* **不守 ``Template`` 自身的形状**（``weekly_frequency`` 与 ``len(sessions)`` 不符、
  ``day`` 跳号、``reachable`` 与维度矛盾、``review_status`` 是 ``pending``）：全部住在加载器
  :func:`app.refdata_prescription.load_templates` 与匹配器
  :func:`app.domain.prescription.match_template`。**装配器不查 ``reachable`` 也不查
  ``review_status``**——那是匹配器的两道拒绝，在这里重查一遍就是同一条规则的第二个住址。
* **不守 ``intensity`` 的字段完整性**：一个手工构造的 ``Intensity(type="hrmax_pct")``
  （``low`` / ``high`` 都是 ``None``）会在 :func:`_render` 里 ``TypeError``，不是
  ``ValueError``。加载器 :func:`app.refdata_prescription._intensity` 已经两个方向都校验过
  （「该有的有、不该有的没有」），故不重复。
* **唯一的例外是 ``week_deltas`` 的长度**：加载器已拦，装配器**仍**抛 ``ValueError``
  （它可能被喂进一个手工构造的 ``Template``），口径照简报对 ``exercise_ref`` 的处置——
  「Task 3 的加载校验是第一道，这是第二道；**两道都要有**」。
"""
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.indicators import Sex

from .exercises import ExerciseSpec, ImpactLevel
from .intensity import age_from, hr_zone, hrmax
from .templates import INTENSITY_TYPES, Intensity, Session, Template

#: ``volume_unit`` 的取值域（P5-A1 新增的字段）。**它是这个词表的唯一所有者**：
#: ``"min"`` / ``"reps"`` 来自 :func:`_base_volume` 的两种 ``structure`` 形状，
#: ``"unspecified"`` 来自 5.3 追加的 addon block（``Addon`` 没有 ``structure``，量无从算起）。
VOLUME_UNITS: frozenset[str] = frozenset({"min", "reps", "unspecified"})

#: ``volume_factor_band`` 的取值域（P5-A7：``"unknown"`` 承载「``endurance_score is None``」，
#: **不另加第 13 个快照键**）。
VOLUME_FACTOR_BANDS: frozenset[str] = frozenset({"low", "mid", "high", "unknown"})

#: 两种 ``structure`` 键集（P5-A1 的实测口径；口径与理由见模块 docstring 的第二节）。
_DURATION_KEYS = frozenset({"sets", "work_min", "rest_min"})
_REPS_KEYS = frozenset({"rounds", "reps"})

#: 三档系数。**私有**：这套阈值指导文件没给、是工程约定（spec §14 #32），把它做成公开面
#: 会让「专家调阈值」看起来像一次破坏公开契约的改动。守卫用**字面写死**的期望系数
#: （``tests/domain/test_prescription_assembler.py`` 的 :data:`_BANDS_MALE` /
#: :data:`_BAND_EDGES`），不从这三个常量读回来跟自己比（硬规矩 #35）。
_ENDURANCE_LOW_CUTOFF = 60.0
_ENDURANCE_MID_CUTOFF = 80.0
_BAND_FACTOR = {"low": 0.8, "mid": 1.0, "high": 1.2}

#: 性别系数：男 ``1.0`` / 女 ``0.9``。``Sex`` 的所有者是
#: :mod:`app.domain.indicators`（P5-A11：**绝对导入**，与 ``match.py`` 引 ``Layer`` 同口径）。
_SEX_FACTOR = {Sex.MALE: 1.0, Sex.FEMALE: 0.9}

#: ``intensity: {type: none}`` 的**显式**文案（Ruling 133）。措辞是简报 5.2 的决定原文。
_NO_INTENSITY_TEXT = "模板未指定强度（spec §7.2 只给了红层数值，见 spec §14）"

#: 快照 ``"formula"`` 那一格的恒定取值。简化版砍掉了 ``HrmaxFormula`` 枚举与 FOX 公式
#: （简报 Task 5 合并说明的 ①/⑤），故本构建实现的公式**只有** Tanaka。
#: ⚠️ 它记的是「本构建实现哪个公式」，**不是**「这次用的是不是公式值」——后者由快照的
#: ``"hrmax"`` 那一格承担（``measured_hrmax`` 非空时它就是实测值）。
_HRMAX_FORMULA = "tanaka"

#: ``rpe`` 的值域 **0–10**（两端**闭**）。⚠️ **不是 Borg 经典的 6–20**：spec 全篇的 RPE
#: 都是 0–10 标度，四处逐字可 grep（按硬规矩 #78 引原文、不写裸行号）——
#: ① ``rpe_record`` 表的字段列逐字是「class_session_id、student_id、**RPE 0–10**、提交时间、
#: **提交耗时秒**」；② §8.2 的小标题逐字是「**课堂端 RPE（0–10 主观疲劳）**」；
#: ③ 预警规则 ``RED_RPE_SUSTAINED`` 的触发条件逐字是「**RPE 连续 ≥ 9 分**」（§14 第 6 项
#: 补明「连续」= **连续 3 次课堂快评**）、``YELLOW_CLASS_RPE_HIGH`` 是「**课堂 RPE 均值 > 7 分**」；
#: ④ 大屏异常名单逐字是「连续 3 天未打卡 | **RPE > 8**」。
#: 四处在 6–20 标度上都读不通（「连续 ≥ 9」在 6–20 上只是中高档，而在 0–10 上已贴近力竭），
#: 故值域是 0–10。**私有**：这套标度的所有者是 spec §8.2，把它做成公开面会让「改标度」
#: 看起来像一次破坏公开契约的改动。
#: ⚠️ spec §14 记着一条**待确认**：「指导文件内部矛盾：大屏阈值 RPE > 8 与预警规则
#: RPE 连续 ≥ 9 不一致」。**那是两个*告警阈值*之间的矛盾，不是*标度*的矛盾**——标度在
#: spec 里四处一致，故钉住 0–10 不是在替那条待确认事项做决定。
_RPE_MIN = 0.0
_RPE_MAX = 10.0


class _ReadOnlyVolumeBase(dict):
    """``assembly_snapshot["weekly_volume_base"]`` 那一格的**只读** ``Mapping[str, float]``。

    **为什么是 ``dict`` 子类而不是 ``types.MappingProxyType``**：两条约束在这里互斥，
    而 ``dict`` 子类是它们唯一的交集——完整的亲跑取证与备选方案的失败原因见模块
    docstring 里「**只读性与 JSON 化在这里是互斥的两条约束**」那一段（按可 grep 的原文找）。
    摘要：``types`` 不在 domain 的 allow-list 里（插一句就红），
    而 ``MappingProxyType`` 又不是 ``json`` 默认可序列化的类型，这一格偏偏要落进
    ``prescription.assembly_snapshot`` 那个 JSON 列。

    ⚠️ **8 个 mutator 一个都不能少**：``__setitem__`` / ``__delitem__`` / ``pop`` /
    ``popitem`` / ``clear`` / ``update`` / ``setdefault`` / ``__ior__``。
    **``__ior__`` 必须单独挡**（亲跑）：``m |= {...}`` 走的是 ``dict.__ior__`` 的 C 实现、
    **绕过**被覆盖的 ``update``，只挡前 7 个的话它就是那个「看起来只读、其实一改就穿」的口子。

    ⚠️ **``__reduce__`` 不是装饰**（亲跑）：屏蔽 ``__setitem__`` 会顺手打断 ``copy``——
    ``copy._reconstruct`` 正是靠 ``y[key] = value`` 逐项重建的，故没有它时 ``copy.copy(m)``
    抛 ``TypeError``。:class:`TrainingPackage` 是 frozen dataclass，Task 6/8 完全可能对整包
    做一次 ``deepcopy``。一个 ``__reduce__`` 同时修好 ``copy`` / ``deepcopy`` / ``pickle``
    三条路径。⚠️ 值是 ``float``（不可变），故「浅拷贝即深拷贝」在这一格成立。

    **私有**（前导下划线）：它不出现在 :mod:`app.domain.prescription` 的公开面里，故
    ``__all__`` 与 ``tests/test_refdata_prescription.py`` 的 ``_PRESCRIPTION_PUBLIC_BASELINE``
    都不动（那一份的支 5 要求七个模块的**公有**顶层定义与基线互为充要）。消费者看到的
    就是一个「改不动的 ``dict``」，不需要知道它的类名。
    """

    def _blocked(self, *args, **kwargs):
        raise TypeError(
            "assembly_snapshot['weekly_volume_base'] 是**只读**的（fix round 1 / F1-1）："
            "它按 volume_unit 分列，是离线复算的账，就地改写会让同一张处方在两个消费者"
            "手里给出不同的量。要改请产出一个新的映射"
        )

    __setitem__ = _blocked
    __delitem__ = _blocked
    pop = _blocked
    popitem = _blocked
    clear = _blocked
    update = _blocked
    setdefault = _blocked
    __ior__ = _blocked

    def __reduce__(self):
        return (_ReadOnlyVolumeBase, (dict(self),))


@dataclass(frozen=True)
class StudentProfile:
    """装配一个学生所需的全部输入。**由调用方（Task 6/7 的管道）算好再传进来**。

    ``age`` 与 ``birth`` **同时**存在是有意的冗余：``age`` 让装配器不必自己碰日期
    （``datetime`` 不在 domain 的 allow-list 里），而 :func:`assemble` 会**对账**
    ``age == age_from(birth, as_of)``，于是一个传错 ``as_of`` 的调用方当场就炸。

    ``endurance_score`` 的口径（两项国标得分的算术均值、只有一项时取那一项、两项都无值时
    ``None``）见模块 docstring 的第三节；⚠️ **那个均值不在本模块算**，否则口径就有两个住址。

    ``bmi`` / ``body_fat_pct`` / ``muscle_mass_kg`` / ``muscle_p10`` **本模块一个都不用**：
    它们是 5.3 :func:`app.domain.prescription.safety.apply_safety` 的输入
    （:class:`app.domain.prescription.safety.SafetyInput` 的四个字段与之同名同义）。
    放在这里是为了让「一个学生的处方输入」只有一个值对象，而不是让管道同时抱着两个。

    ``measured_hrmax`` 今天**永远是 ``None``**（Plan 01/02 没有任何心率数据），理由与
    :func:`app.domain.prescription.intensity.hrmax` 的 ``measured`` 形参完全相同。
    """

    student_id: int
    sex: Sex
    birth: "dt.date"
    age: int
    endurance_score: float | None
    bmi: float | None
    body_fat_pct: float | None
    muscle_mass_kg: float | None
    muscle_p10: float | None
    measured_hrmax: float | None


@dataclass(frozen=True)
class AssembledBlock:
    """一个装配好的训练块。字段名与顺序照简报 Interfaces / Produces 逐字。

    ``impact_level`` **取自动作库**（:attr:`ExerciseSpec.impact_level`）而**不是**
    ``Block.impact_level``（P5-A8）：``exercises.yaml`` 是 ``impact_level`` 的**源**
    （它是 ``exercise`` 表的 seed 源），模板里那一份是**冗余副本**（Plan02 账本 P2-B2）。
    5.3 的安全规则按它挑「要换掉的高冲击动作」，故它必须读源——读副本的话，「专家改了
    动作库、忘了改 18 套模板」会让安全替换**静默失效**。守卫是
    ``test_impact_level_comes_from_the_exercise_library_not_the_template``。

    ``weekly_volume`` 是**周量**、不是单课量：同一个 ``exercise_ref`` 在一周内跨 session
    重复（18/18 套模板全部如此），故 ``weekly_volume = base × sessions_per_week ×
    volume_factor × week_deltas[week-1]``，最后 ``round(…, 1)``（P5-A6：不 round 的话
    ``48.0 × 0.8 × 1.0`` 是 ``38.400000000000006``）。
    ⚠️ **同一个 block 在同一周的每一课里带着同一个 ``weekly_volume``**：它是周量，
    按课再除一次才是单课量（Task 8 的「本周训练单」读模型要自己决定怎么摊）。

    ``structure`` 原样透传 ``Block.structure``（:class:`types.MappingProxyType`，只读）；
    5.3 追加的 addon block 那一份是 ``{}``（⚠️ 一个普通 ``dict``：``types`` **不在** domain
    的 allow-list 里，故拿不到 ``MappingProxyType``。它是**每实例新建**的空字典，
    改它只影响那一个 addon block）。
    """

    exercise_ref: str
    exercise_name: str
    video_url: str
    impact_level: ImpactLevel
    intensity_text: str
    hr_zone: tuple[int, int] | None
    structure: Mapping[str, object]
    weekly_volume: float
    volume_unit: str
    sessions_per_week: int


@dataclass(frozen=True)
class AssembledSession:
    """一周里的一个训练日。``day`` / ``focus`` 原样透传 :class:`Session`。"""

    day: int
    focus: str
    blocks: tuple[AssembledBlock, ...]


@dataclass(frozen=True)
class AssembledWeek:
    """微周期的第 ``week`` 周（**1 基**，与 ``week_deltas[week-1]`` 对得上）。

    ``delta`` 原样留着：教师端要能回答「第 4 周为什么量少了」，答案是「模板的
    ``week_deltas`` 末项是 0.85（超量恢复）」，而不是「算法决定减量」。
    """

    week: int
    delta: float
    sessions: tuple[AssembledSession, ...]


@dataclass(frozen=True)
class TrainingPackage:
    """一个完整的 4 周训练包（spec §4.4 的 ``prescription.training_package`` 那一列的内容）。

    ``assembly_snapshot`` **恰好 12 个键**（P5-A7；键名与顺序由
    ``test_assembly_snapshot_keys_are_exactly_the_pinned_set`` 字面钉死，多一个少一个都红）。
    **这一列是 spec §4.3 可追溯性在处方侧的落点**——有了它，任一条处方都能离线复算。
    ⚠️ 5.3 的 :func:`app.domain.prescription.safety.apply_safety` 会在它上面**追加至多 3 个**
    键（``safety_triggers`` / ``safety_skipped`` / ``safety_volume_factor``），
    **这 12 个一个都不许改**。

    ``paused`` **在本节就定义**（虽然置位是 5.4 的 ``OverrideKind.PAUSE`` 的活）：否则 5.4
    要回头改一个已定稿的产出类型，而那是 Plan 01 吃过 6 次的亏——改了 Interfaces 却没改
    照抄它的 Step（硬规矩 #11）。装配器一律产出 ``paused=False``。

    ⚠️ ``assembly_snapshot`` 是 ``dict``（可变）而不是 ``MappingProxyType``：它要直接落进
    一个 JSON 列，而 ``types`` 不在 domain 的 allow-list 里（与
    :attr:`AssembledBlock.structure` 的注释同一条理由）。5.3 追加键时用的是
    ``{**pkg.assembly_snapshot, ...}`` **产出新字典**，故「不可变」这件事由纪律而不是类型
    保证，守卫是 ``test_apply_safety_does_not_mutate_its_input``。

    ⚠️ **外层可变、``"weekly_volume_base"`` 那一格只读**（F1-1）：12 个键里 11 个是标量或
    ``list``，只有那一格是 :class:`_ReadOnlyVolumeBase`（屏蔽了 8 个 mutator 的 ``dict``
    子类，``Mapping[str, float]`` 口径）。它**必须**是 ``dict`` 的子类才既能只读又能被
    ``json.dumps`` 认下——两条约束的取舍与亲跑取证见模块 docstring 里
    「**只读性与 JSON 化在这里是互斥的两条约束**」那一段（按可 grep 的原文找）。
    整个快照的 JSON 化由 ``test_assembly_snapshot_is_json_serialisable``（12 键）与
    ``test_the_safety_snapshot_is_json_serialisable``（5.3 之后的 15 键，Task 6 真正落库的
    那一份）两条守卫看着。
    """

    template_id: str
    template_version: str
    weeks: tuple[AssembledWeek, ...]
    assembly_snapshot: dict
    paused: bool = False


def _base_volume(structure: Mapping[str, object]) -> tuple[float, str]:
    """``structure`` → ``(每课基准量, volume_unit)``（P5-A1 的口径，见模块 docstring）。

    两种键集之外的形状一律 ``ValueError``（**不得静默取 0**）。判据是 ``frozenset(keys)``
    **相等**，不是「包含这几个键」：``{sets, work_min, rest_min, rounds}`` 这种混形状必须
    响，因为「按哪一套公式算」在它面前没有答案。
    """
    keys = frozenset(structure)
    if keys == _DURATION_KEYS:
        # rest_min 刻意不参与：它是恢复、不是负荷（理由见模块 docstring）
        return float(structure["work_min"] * structure["sets"]), "min"
    if keys == _REPS_KEYS:
        return float(structure["rounds"] * structure["reps"]), "reps"
    raise ValueError(
        f"block.structure 的键集是 {sorted(keys)}，而基准量只认两种形状："
        f"{sorted(_DURATION_KEYS)}（base = work_min × sets，单位 min）与 "
        f"{sorted(_REPS_KEYS)}（base = rounds × reps，单位 reps）。"
        f"**不静默取 0**：量变 0 会让训练包看起来完全正常（结构齐全、文案齐全、快照齐全）"
        f"而每个 block 都是空的"
    )


def _render(intensity: Intensity, max_hr: float) -> tuple[str, tuple[int, int] | None]:
    """``Intensity`` → ``(intensity_text, hr_zone)``。四档**各有显式的一支**，词表外抛。

    ⚠️ 只有 ``hrmax_pct`` 那一支返回非 ``None`` 的 ``hr_zone``（六步口径的第 2 步）。
    ``none`` 那一支的文案是 :data:`_NO_INTENSITY_TEXT`——Ruling 133：**「模板没给强度」是
    常态不是例外**（真仓 82/130），故它必须有一档显式渲染，既不回落到 ``hrmax_pct`` 的
    默认值、也不留空字符串。

    ``rpe`` 在真仓出现 **0** 次（P5-A5），但它必须被覆盖（domain 分支 100%）。
    ⚠️ ``Intensity.value`` 的语义**随 ``type`` 变**：``onerm_pct`` 是 1RM 的百分比、
    ``rpe`` 是 **0–10** 标度的自觉受累程度（**不是** Borg 经典的 6–20；出处逐字引在
    :data:`_RPE_MIN` 的注释里：``rpe_record`` 表字段「RPE 0–10」、§8.2 小标题「课堂端 RPE
    （0–10 主观疲劳）」、``RED_RPE_SUSTAINED``「RPE 连续 ≥ 9 分」、
    ``YELLOW_CLASS_RPE_HIGH``「课堂 RPE 均值 > 7 分」、大屏「RPE > 8」）。
    它与 :mod:`app.domain.prescription.templates` 的
    :data:`~app.domain.prescription.templates.INTENSITY_TYPES` 注释（「``rpe`` 的出处是
    spec §8.2 的课堂快评 RPE 0–10」）同口径——**这是跨计划契约**：Plan 03 的预警侧要把
    「9 分」读成 0–10 标度上贴近力竭的那一档，读成 6–20 的中高档就整个错位。

    ⚠️ **``rpe`` 那一支校验值域，其余三档不校验**（fix round 1 / F1-2 的决定，理由三条）：

    * **与 :func:`~app.domain.prescription.intensity.hr_zone` 对称**：``hrmax_pct`` 的值域
      （``0 <= low <= high <= 100``）在 domain 这一层**本来就有**守卫，``rpe`` 没有就是一个
      不对称的洞，不是「单一所有者」。
    * **加载器不校值域**：:func:`app.refdata_prescription._intensity` 只校**字段形状**
      （``rpe`` 要有 ``value``、不许有 ``low``/``high``）。故没有本条的话，一份
      ``intensity: {type: rpe, value: 13}`` 的 YAML 能加载成功、渲染成学生端的「RPE 13」
      ——在 0–10 标度上那是一个**看起来完全正常的谎**。
    * **可证明不会让任何真仓模板炸**：``rpe`` 在 18 套模板里出现 **0** 次，故这道拒绝今天
      在生产路径上不可达（守卫 ``test_rpe_value_outside_zero_to_ten_is_rejected`` 的
      ``-0.1`` / ``0.0`` / ``10.0`` / ``10.1`` 四个值是它唯一的消费者）。

    ``onerm_pct`` 与 ``none`` 两档**仍不校验值域**：前者的百分比合法性是加载器与
    ``EquivalenceTable`` 的账（且 spec §7.2 只给了 ``70`` 一个例子，值域无出处），后者没有
    标量。
    """
    kind = intensity.type
    if kind == "hrmax_pct":
        zone = hr_zone(max_hr, intensity.low, intensity.high)
        return (
            f"{intensity.low:g}–{intensity.high:g}% HRmax"
            f"（{zone[0]}–{zone[1]} bpm）",
            zone,
        )
    if kind == "onerm_pct":
        return f"{intensity.value:g}% 1RM", None
    if kind == "rpe":
        if intensity.value < _RPE_MIN or intensity.value > _RPE_MAX:
            raise ValueError(
                f"intensity.value 是 {intensity.value}，而 rpe 的值域是闭区间 "
                f"[{_RPE_MIN:g}, {_RPE_MAX:g}]（0–10 主观疲劳标度，**不是** Borg 的 6–20）："
                f"spec 四处逐字写着这个标度——rpe_record 表字段「RPE 0–10」、§8.2 小标题"
                f"「课堂端 RPE（0–10 主观疲劳）」、RED_RPE_SUSTAINED「RPE 连续 ≥ 9 分」、"
                f"YELLOW_CLASS_RPE_HIGH「课堂 RPE 均值 > 7 分」。"
                f"**不夹取、不静默渲染**：一份 rpe: 13 的模板会渲染成学生端的「RPE 13」，"
                f"在 0–10 标度上那是一个看起来完全正常的谎，而 Plan 03 的预警阈值"
                f"（连续 ≥ 9）会跟着整个错位"
            )
        return f"RPE {intensity.value:g}", None
    if kind == "none":
        return _NO_INTENSITY_TEXT, None
    raise ValueError(
        f"intensity.type {kind!r} 不在词表内，无法渲染强度文案。合法值是 "
        f"{sorted(INTENSITY_TYPES)}"
        f"（词表的所有者是 app.domain.prescription.templates.INTENSITY_TYPES，"
        f"加载器已经拦过一道；这里是第二道，因为装配器可能被喂进一个手工构造的 Template）。"
        f"**不静默渲染成空文案**：学生端会看到一格空白，分不清「不需要强度区间」与「忘了填」"
    )


def _volume_factor(
    endurance_score: float | None, sex: Sex
) -> tuple[float, str, float]:
    """→ ``(最终系数, 档名, 性别系数)``。三档 + ``unknown`` 的口径见模块 docstring 第三节。

    ⚠️ **``endurance_score is None`` 时连性别修正也不做**，返回字面的 ``1.0``：
    ``1.0`` 是「不知道就不动」的中性值，而 ``0.9`` 是一个**基于档位表**的修正，
    档位未知时它没有依据。档名 ``"unknown"`` 就是这件事的留痕（P5-A7：不加第 13 个键）。

    ``round(…, 2)`` 是承重的：``0.8 * 0.9`` 亲跑是 ``0.7200000000000001``（P5-A6），
    不 round 的话 ``weekly_volume`` 的字面值就不稳定、快照也就不可复算。
    """
    sex_factor = _SEX_FACTOR[sex]
    if endurance_score is None:
        return 1.0, "unknown", sex_factor
    if endurance_score < _ENDURANCE_LOW_CUTOFF:
        band = "low"
    elif endurance_score < _ENDURANCE_MID_CUTOFF:
        band = "mid"
    else:
        band = "high"
    return round(_BAND_FACTOR[band] * sex_factor, 2), band, sex_factor


def assemble(
    profile: StudentProfile,
    template: Template,
    as_of: "dt.date",
    *,
    exercises: Mapping[str, ExerciseSpec],
) -> TrainingPackage:
    """spec §7.3 的六步装配。**纯函数**：不读盘、不读 DB、不读时钟、不改任何入参。

    三道 ``ValueError``（顺序即代码顺序）：

    1. ``profile.age != age_from(profile.birth, as_of)`` —— 第 1 步的一致性闸门，挡的是
       「调用方用了错误的 ``as_of``」。消息里**同时**带给出的年龄与算出的年龄。
    2. ``len(template.week_deltas) != template.microcycle_weeks`` —— 加载器已拦，这里是
       第二道（**不静默截断**：3 项配 4 周时「容错」写法会让第 4 周悄悄回到第 3 周的量，
       恰好在最该减量的那一周加量）。
    3. 逐 block 的四道：``exercise_ref`` 不在注入的动作库里、``structure`` 键集不是那两种、
       ``intensity.type`` 不在词表内、``intensity.type == "rpe"`` 而 ``value`` 落在
       ``[0, 10]`` 之外（分别见 :func:`_base_volume` 与 :func:`_render`）。

    ``exercises`` 是**keyword-only**：它有 18 套模板共享的一份内容，位置参数容易被喂成
    ``templates()``（两个映射的键形状完全不同，一个是 ``exercise_ref``、一个是
    ``template_id``），而 keyword-only 让调用点上必须写出 ``exercises=`` 这个名字。
    """
    # ① 一致性闸门（六步的第 1 步之前，因为它决定后面所有算式用的年龄对不对）
    expected_age = age_from(profile.birth, as_of)
    if profile.age != expected_age:
        raise ValueError(
            f"StudentProfile.age 是 {profile.age}，而 age_from(birth={profile.birth}, "
            f"as_of={as_of}) 是 {expected_age}：两者必须相等。age 由调用方算好传入"
            f"（domain 不碰日期），装配器只对账；不一致说明调用方的 as_of 或 birth 传错了，"
            f"而 HRmax = 208 − 0.7 × age 会跟着错，进而整个目标心率区间都错"
        )

    # ④ 的前置：week_deltas 的长度（不静默截断）
    if len(template.week_deltas) != template.microcycle_weeks:
        raise ValueError(
            f"模板 {template.template_id} 的 week_deltas 有 "
            f"{len(template.week_deltas)} 项，而 microcycle_weeks 是 "
            f"{template.microcycle_weeks}：两者必须相等。**不静默截断也不静默补齐**——"
            f"3 项配 4 周时，「容错」写法会让第 4 周悄悄回到第 3 周的量，恰好在最该减量"
            f"（超量恢复）的那一周加量。加载器 app.refdata_prescription._week_deltas "
            f"是第一道，这里是第二道（装配器可能被喂进一个手工构造的 Template）"
        )

    # ① HRmax：实测优先，否则 Tanaka
    max_hr = hrmax(profile.age, profile.measured_hrmax)
    # ③ 个体修正系数
    volume_factor, volume_factor_band, sex_factor = _volume_factor(
        profile.endurance_score, profile.sex
    )

    # ③ 的 sessions_per_week：**实测统计**，不假设它等于 weekly_frequency（P5-A2）
    per_ref: Counter[str] = Counter()
    for session in template.sessions:
        for block in session.blocks:
            per_ref[block.exercise_ref] += 1

    # ②③⑤ 逐 block 备料（先全部备完再进周循环：一个坏 block 应该在第 1 周就炸，
    #    而不是在装配到第 3 周时才炸——报错点越靠前，离真因越近）
    prepared: list[tuple[Session, list[tuple]]] = []
    # ⑥ 的备料：按 volume_unit 分列累加**每课基准量**（F1-1）。逐 (session, block) 累加与
    #    「base × sessions_per_week 之和」逐格相等，理由见模块 docstring 的那一节。
    #    键序 = 单位的首次出现序（不是字母序），故快照的字面值稳定可复算。
    volume_base: dict[str, float] = {}
    for session in template.sessions:
        entries = []
        for block in session.blocks:
            spec = exercises.get(block.exercise_ref)
            if spec is None:
                raise ValueError(
                    f"exercise_ref {block.exercise_ref!r} 不在注入的动作库里"
                    f"（{len(exercises)} 个键里没有它），装配第 5 步取不到视频 URL 与中文名。"
                    f"加载器 app.refdata_prescription._block 是第一道，这里是第二道："
                    f"装配器可能被喂进一个手工构造的 Template，也可能被喂进一份**与模板"
                    f"不同版本**的动作库（专家删了一个动作却忘了改 18 套模板），"
                    f"后一种情况加载器看不见"
                )
            base, volume_unit = _base_volume(block.structure)
            intensity_text, zone = _render(block.intensity, max_hr)
            entries.append((block, spec, base, volume_unit, intensity_text, zone))
            volume_base[volume_unit] = volume_base.get(volume_unit, 0.0) + base
        prepared.append((session, entries))

    # ④ 4 周递进：weekly_volume = base × sessions_per_week × 系数 × week_deltas[N-1]
    weeks: list[AssembledWeek] = []
    for week_number, delta in enumerate(template.week_deltas, 1):
        assembled_sessions = []
        for session, entries in prepared:
            assembled_blocks = []
            for block, spec, base, volume_unit, intensity_text, zone in entries:
                sessions_per_week = per_ref[block.exercise_ref]
                assembled_blocks.append(
                    AssembledBlock(
                        exercise_ref=spec.ref,
                        exercise_name=spec.name,
                        video_url=spec.video_url,
                        # ⑤ + P5-A8：impact_level 取动作库那一份，不取模板的副本
                        impact_level=spec.impact_level,
                        intensity_text=intensity_text,
                        hr_zone=zone,
                        structure=block.structure,
                        weekly_volume=round(
                            base * sessions_per_week * volume_factor * delta, 1
                        ),
                        volume_unit=volume_unit,
                        sessions_per_week=sessions_per_week,
                    )
                )
            assembled_sessions.append(
                AssembledSession(
                    day=session.day, focus=session.focus,
                    blocks=tuple(assembled_blocks),
                )
            )
        weeks.append(
            AssembledWeek(
                week=week_number, delta=delta, sessions=tuple(assembled_sessions)
            )
        )

    # ⑥ 快照：**恰好 12 个键**（P5-A7），键名与顺序由测试字面钉死
    snapshot = {
        "formula": _HRMAX_FORMULA,
        "hrmax": max_hr,
        "age": profile.age,
        "as_of": as_of.isoformat(),
        "endurance_score": profile.endurance_score,
        "volume_factor": volume_factor,
        "volume_factor_band": volume_factor_band,
        "sex_factor": sex_factor,
        "template_id": template.template_id,
        "template_version": template.version,
        "week_deltas": list(template.week_deltas),
        # F1-1：按 volume_unit 分列的**只读**映射（不是把 min 与 reps 加成一个数）。
        #      键数仍是 12——这一格的**类型**变了，键集契约一个字没动。
        "weekly_volume_base": _ReadOnlyVolumeBase(
            {unit: round(total, 1) for unit, total in volume_base.items()}
        ),
    }
    return TrainingPackage(
        template_id=template.template_id,
        template_version=template.version,
        weeks=tuple(weeks),
        assembly_snapshot=snapshot,
        paused=False,
    )

"""spec §7.4 的三触发安全后置处理 + 低冲击等价替换（Plan 02 Task 5 的 5.3）。

**它是纯函数**：不改传入的 :class:`~app.domain.prescription.assembler.TrainingPackage`
（frozen dataclass，一律用 :func:`dataclasses.replace` 产出新的），不读盘、不读时钟、
不读 DB。守卫是 ``test_apply_safety_does_not_mutate_its_input``。

--------------------------------------------------------------------------

**⚠️⚠️ 签名比简报多了两个 keyword-only 形参（实现者顶回控制者的一处矛盾）**

简报 5.3 的 Produces 写的是 ``apply_safety(pkg, inp, eq) -> SafetyOutcome``，而**同一节**的
P5-A3 要求「追加**模板自己的** ``when == "body_fat_over"`` 的 addon」、addon 的
``exercise_name`` / ``video_url`` / ``impact_level``「从 ``exercises[addon.module]`` 取」、
``sessions_per_week`` = ``template.weekly_frequency``。而
:class:`~app.domain.prescription.assembler.TrainingPackage` 里这三样**一个都没有**（它只带
``template_id`` / ``template_version`` 两个字符串）；等价替换同样需要动作库——替身的名字、
URL 与冲击等级只能从 :class:`~app.domain.prescription.exercises.ExerciseSpec` 取
（P5-A8：读**源**，不读模板里的冗余副本）。

故落地签名是 ``apply_safety(pkg, inp, eq, *, template, exercises)``：三个位置参数与简报逐字
一致，新增的两个是 **keyword-only**（口径照
:func:`~app.domain.prescription.assembler.assemble` 的 ``*, exercises``）。
**代价**：调用点（Task 6 的 ``prescription_stage``）要多写两个实参，而它本来就持有这两样东西
（它先调 :func:`match_template` 拿到 ``Template``、再调 :func:`assemble` 时已经传过
``exercises=``）。**收益**：P5-A3 这条 Critical 级更正可实现，且 ``impact_level`` 仍然只有
一个源。备选方案是把 ``addons`` 与 ``weekly_frequency`` 塞进 ``TrainingPackage``——那会让
「装配产物」与「装配输入」混在一个值对象里，且 Task 8 的读模型会看到两份 ``weekly_frequency``。

--------------------------------------------------------------------------

**三个触发（spec §7.4 ``:508-510``），比较符一律严格 ``<`` / ``>``**

====================  ==================================================  =====================
触发                   条件                                                动作
====================  ==================================================  =====================
``bmi_over_30``        ``bmi is not None and bmi > 30``                    下调 + 换低冲击替身
``muscle_low_p10``     ``muscle_mass_kg < muscle_p10``（两者都非 ``None``）  下调 + 换替身 + **追加 addon**
``body_fat_abnormal``  ``body_fat_abnormal`` 为真                          **只追加 addon**
====================  ==================================================  =====================

**与 Plan 01 同口径**：P25 的比较符钉死为严格小于（``score < p25``，spec §14 #21，可 grep
原文 ``**P25 的比较符钉死为严格小于**``）；体脂率阈值同样是严格大于——
``app/domain/derive.py`` 里可 grep 到 ``BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}``
（**一行 dict 定义**，P5-A10 实测）与它的唯一消费点 ``body_fat_pct > limit``，同文件那句注释
逐字写着「男 > 20%、女 > 28%，**严格大于**」。故 ``bmi == 30.0`` 不触发、
``muscle_mass == muscle_p10`` 不触发，两格各有测试。

⚠️ **这里的阈值是 P10、不是 Plan 01 体成分 ``C`` 判定用的 P20**：spec §7.4 用「肌肉量 < P10」、
§4.2 的 ``C`` 用「肌肉量 < P20」，**两个阈值不同、分属两个机制，不得混用**
（``backend/data/exercise_equivalence.yaml`` 的注释里也逐字写了这一条）。故
:class:`SafetyInput` 的字段名叫 ``muscle_p10`` 而不是 ``muscle_percentile``。

--------------------------------------------------------------------------

**⚠️ P5-A9：两套不同名的触发词表，本模块只消费、不定义**（Global Constraint #3）

实测 ``ADDON_TRIGGERS = {body_fat_over, muscle_low}``（所有者
:mod:`app.domain.prescription.templates`，也是 YAML 里 ``addons.when`` 的取值域）、
``EQUIVALENCE_TRIGGERS = {bmi_over_30, muscle_low_p10}``（所有者
:mod:`app.domain.prescription.exercises`，也是 ``volume_reduction`` 的键），而
:class:`SafetyInput` 给的是**第三套**（``bmi`` / ``muscle_mass_kg`` / ``muscle_p10`` /
``body_fat_abnormal``）。:data:`_TRIGGER_MAP` 就是这张跨表翻译，**字面写死**。
两条漂移测试（``test_trigger_word_lists_have_not_drifted``）各自字面钉住两个上游词表：
上游一改名，``KeyError`` 是响的，但「查不到 addon 于是只留一条 warning」是**静默的**，
那两条断言就是这道提醒。

--------------------------------------------------------------------------

**「没测不得讲成测了没问题」**（Plan01 Ruling 134 的同一条纪律）：``bmi is None`` /
``muscle_mass_kg is None`` / ``muscle_p10 is None`` 都**不触发**，且在
``assembly_snapshot`` 的 ``safety_skipped`` 里逐条留痕（``"bmi_missing"`` /
``"muscle_mass_missing"`` / ``"muscle_p10_missing"``）。**安全规则静默跳过比不跳过危险**：
一张已生成的处方必须能回答「安全规则是真没命中，还是根本没数据可判」。

**⚠️ P5-A7：追加的键字面固定为至多 3 个**——``safety_triggers`` / ``safety_skipped`` /
``safety_volume_factor``。:func:`~app.domain.prescription.assembler.assemble` 那 **12** 个键
**一个都不许改**（它们是离线复算的契约）。

--------------------------------------------------------------------------

**「找不到等价动作 → 不静默跳过」**（Review Focus 第 5 条，spec §7.4 ``:514`` 末段原文）：
``needs_review = True``、``warnings`` 里写明「哪个动作、哪个触发、映射表版本」、
**该 block 原样保留**（不删除、不替换）。**「原样保留」是决定**：删掉动作会让训练量
**静默缩水**（教师看到的是一份「看起来正常」的训练包，只是少了一块），而保留 +
``needs_review`` 让教师看见。

⚠️ **同一个 ``exercise_ref`` 只留一条 warning**：它在一套模板里出现
``microcycle_weeks × weekly_frequency`` 次（``RED-END-ABN-01`` 是 16 次），16 条同样的
warning 会把教师端的复核队列刷成噪音，而队列一旦被淹没，真正需要人看的那一档就没人看了。
:attr:`Substitution` 反而是**逐 block 实例**的（它带 ``week`` 与 ``day``）：那是**审计**数据
（哪一课被换了），不是**待办**数据。

**``needs_review`` 只由这一条置位**（P5-A3 的更正）：肌肉量偏低那一档既然已经自动追加了
``resistance_priority`` 模块，就不存在「宁可不自动」的问题了。原计划把它也判成
``needs_review = True``，那会让**每一个**肌肉量偏低的红/黄层学生都进人工复核队列。

--------------------------------------------------------------------------

⚠️ **本模块守不住什么**（硬规矩 #39）：

* **不守 ``volume_reduction`` 那两个系数对不对**：``0.8`` / ``0.9`` 在 spec 里**没有出处**
  （``:508`` 只写「按映射表下调」、没给数；spec 里唯一的「系数 0.8」在 ``:604``，那是
  Plan 03 的**预警减量**，是另一个机制）。它们是**工程约定、须专家确认**（spec §14 #28），
  所有者是 ``backend/data/exercise_equivalence.yaml``，字面钉住它的测试在
  ``tests/test_refdata_prescription.py``。本模块只是把它们**乘上去**。
* **不守 ``lookup`` 的 ``when``**：:meth:`~app.domain.prescription.exercises.EquivalenceTable.lookup`
  按 ``from_ref`` 与 ``max_impact`` 过滤，**不看 ``when``**。真表里两个触发的替身逐条相同
  （``exercise_equivalence.yaml`` 的注释逐字写着「替身与触发 1 相同：spec 原文就是『同上』」），
  故今天无影响；将来若专家给两个触发配了**不同**的替身，``lookup`` 会返回书写顺序里的第一条
  ——那是 ``EquivalenceTable`` 的契约问题，不在本模块。
* **不守 addon ``module`` 在不在动作库里**：简报明写「Task 3 的加载器已校验过它存在，
  故这里**不重复校验**——单一所有者」。于是那一档 surfaces 成 ``KeyError`` 而**不是**
  ``ValueError``（响亮，但异常类型与装配器那三道不一致）。
* **不修「``hiit`` 有等价映射、``energy_expenditure_plus_5min_hiit`` 没有」这个已知不对称**
  （Task 3 记录，本 Task 只复述）：BMI > 30 的黄层学生会「主项被换掉、追加模块原样保留」。
  那是**数据面的事实**，不是代码缺陷。
"""
from collections.abc import Mapping
from dataclasses import dataclass, replace

from .assembler import AssembledBlock, TrainingPackage
from .exercises import EquivalenceTable, ExerciseSpec, ImpactLevel
from .templates import Template

#: spec §7.4 ``:508`` 的 BMI 阈值。**严格大于**才触发（口径见模块 docstring 第二节）。
_BMI_LIMIT = 30.0

#: **P5-A9 的跨表翻译**：键 = 本模块的触发名，值 = (``volume_reduction`` 的键 or ``None``,
#: ``addons.when`` 的键 or ``None``)。字面照简报 5.3 的代码骨架写死。
#:
#: * ``bmi_over_30`` 的 addon 键是 ``None``：实测模板里**没有** ``when: bmi_over_30`` 的
#:   addon（``addons.when`` 的取值域是 ``ADDON_TRIGGERS`` = ``{body_fat_over, muscle_low}``）。
#: * ``body_fat_abnormal`` 的下调键是 ``None``：spec §7.4 ``:510`` 只说「追加能量消耗模块」、
#:   **没说下调**，而 ``volume_reduction`` 的键集恰好是 ``EQUIVALENCE_TRIGGERS`` 那两个
#:   （加载器 :func:`app.refdata_prescription.load_equivalence` 强制
#:   ``set(volume_reduction) == EQUIVALENCE_TRIGGERS``），根本没有这一格。
#:
#: ⚠️ **迭代序是承重的**：它决定 ``safety_triggers`` 的排列、下调系数的相乘顺序（浮点乘法
#: 可交换、故不改变乘积）、以及多个 addon 被追加到 ``blocks`` 末尾的先后。
_TRIGGER_MAP: dict[str, tuple[str | None, str | None]] = {
    "bmi_over_30": ("bmi_over_30", None),
    "muscle_low_p10": ("muscle_low_p10", "muscle_low"),
    "body_fat_abnormal": (None, "body_fat_over"),
}

#: 追加的 addon block 的强度文案。与
#: :data:`app.domain.prescription.assembler._NO_INTENSITY_TEXT` **同一措辞口径**
#: （Ruling 133：「模板没给强度」要显式说出来，不留空、不回落）。
_ADDON_INTENSITY_TEXT = "附加模块（模板未指定强度，见 spec §14）"

#: 肌肉量偏低那一档的 warning 文本（P5-A3 逐字给的措辞）。``{module}`` 由调用点填，
#: 于是它同时是「追加了哪个模块」的留痕。
_MUSCLE_LOW_WARNING = (
    "muscle_low_p10: 已追加 {module} 模块；如需进一步调整抗阻比重，"
    "请用教师覆盖（OverrideKind.VOLUME_SCALE / SUBSTITUTE_EXERCISE）"
)

#: ``safety_skipped`` 的三个 token。**字面固定**：它们是「哪一项因缺输入而被跳过」的
#: 机器可读标识，Task 6 会把整个列表落进 JSON 列，改名就是一次数据迁移。
_SKIP_BMI = "bmi_missing"
_SKIP_MUSCLE_MASS = "muscle_mass_missing"
_SKIP_MUSCLE_P10 = "muscle_p10_missing"


@dataclass(frozen=True)
class SafetyInput:
    """安全后置所需的四个输入。字段名与顺序照简报 Interfaces / Produces 逐字。

    ⚠️ **三个 ``None`` 都是合法值**（缺测），且都**不触发**、都在 ``safety_skipped`` 里留痕。
    ``body_fat_abnormal`` 是 ``bool`` 而**不是** ``float | None``：它的来源是 Plan 01 的
    :attr:`app.domain.derive.BodyCompFlag.abnormal`（那一侧的 ``C`` 判定结论），而
    **``False`` 包含「数据缺失所以无从判定」这一整类**（Plan01 Ruling 97③，
    ``app/domain/stratify.py`` 里 ``_REASON`` 上方那段注释逐字讲了它）。故体脂率那一档
    **没有** ``"body_fat_missing"`` 这个 skip token：本模块拿到的已经是一个布尔结论，
    「为什么是 ``False``」是 ``derive.body_comp_flag`` 的账、不是安全层的账。
    ``body_fat_pct`` 原值也在 :class:`~app.domain.prescription.assembler.StudentProfile` 上，
    但**本模块不重新判定它**（那会是同一条规则的第二个住址）。

    ``muscle_p10`` 是 **P10**、不是 Plan 01 体成分 ``C`` 用的 **P20**（口径见模块 docstring）。
    """

    bmi: float | None
    muscle_mass_kg: float | None
    muscle_p10: float | None
    body_fat_abnormal: bool


@dataclass(frozen=True)
class Substitution:
    """一次等价替换的审计记录。字段名与顺序照简报 Interfaces / Produces 逐字。

    spec §7.4 ``:512`` 要求把「原动作、新动作、触发条件、**映射表版本号**」写进
    ``prescription.safety_substitutions``——四样对应 ``original_ref`` / ``substitute_ref`` /
    ``trigger`` / ``equivalence_version``，另加 ``week`` 与 ``day`` 两个定位字段。

    ⚠️ **它是逐 block 实例的**：同一个 ``exercise_ref`` 在 4 周 × 4 课里出现 16 次，就有
    16 条记录（``RED-END-ABN-01`` 的 ``interval_run`` 实测如此）。理由：这是**审计**数据
    （哪一课被换了），教师要能逐课对账；而**待办**数据（``needs_review`` + ``warnings``）
    按 ref 去重，见模块 docstring 第五节。

    ``trigger`` 记的是**第一个**命中的走等价表的触发（:data:`_TRIGGER_MAP` 的迭代序）。
    两个触发都命中时只记 ``"bmi_over_30"``：替换这件事**只发生了一次**（替身是 ``low``
    冲击，第二个触发再走一遍时它已经不是 ``HIGH`` 了），记两条会让教师以为换了两次。
    """

    week: int
    day: int
    original_ref: str
    substitute_ref: str
    trigger: str
    equivalence_version: str


@dataclass(frozen=True)
class SafetyOutcome:
    """一次安全后置的全部产出。字段名与顺序照简报 Interfaces / Produces 逐字。

    ``package`` 是一个**新**的 :class:`~app.domain.prescription.assembler.TrainingPackage`
    （入参那个一个字没改），它的 ``assembly_snapshot`` 有 **15** 个键 = ``assemble`` 的 12 个
    + 本模块追加的 3 个。

    ``needs_review`` **只由「找不到等价动作」置位**（P5-A3 的更正，理由见模块 docstring）。
    Task 6 据此把 ``prescription.status`` 写成 ``needs_review``、教师端标记「需人工复核」。

    ``warnings`` 是给日志与教师端的那几句，**顺序确定**：先 addon 相关（按
    :data:`_TRIGGER_MAP` 的触发序、再按 ``template.addons`` 的书写序），后「找不到替身」
    （按周、课、block 的遍历序，同一 ref 只一条）。
    """

    package: TrainingPackage
    substitutions: tuple[Substitution, ...]
    needs_review: bool
    warnings: tuple[str, ...]


def apply_safety(
    pkg: TrainingPackage,
    inp: SafetyInput,
    eq: EquivalenceTable,
    *,
    template: Template,
    exercises: Mapping[str, ExerciseSpec],
) -> SafetyOutcome:
    """spec §7.4 的三触发后置处理。**纯函数**：不改 ``pkg``、不改 ``template``、不改 ``eq``。

    ⚠️ ``template`` 与 ``exercises`` 是**新增的 keyword-only 形参**（简报的签名给不出 P5-A3
    要求的数据，理由与备选方案见模块 docstring 第一节）。``template`` 提供 ``addons`` 与
    ``weekly_frequency``，``exercises`` 提供替身与追加模块的 ``name`` / ``video_url`` /
    ``impact_level``（**读源、不读模板副本**，P5-A8）。

    处置顺序（**承重**，换序就换语义）：

    1. 判定三个触发，同时把「因缺输入而跳过」的项记进 ``skipped``；
    2. 按 :data:`_TRIGGER_MAP` 把触发名翻成「下调键」与「addon 键」，下调系数**相乘**；
    3. 算出要追加的 addon block（每一课共用同一个 frozen 实例）；
    4. 逐 block：HIGH 且走了等价表 → 查替身（查不到则 ``needs_review`` + 原样保留）、
       然后**一律**乘下调系数并 ``round(…, 1)``；
    5. 把 addon 追加到**每一课的末尾**（既有 block 的顺序与值一个不动）；
    6. 快照 = ``{**pkg.assembly_snapshot, 那 3 个键}``，产出新包。

    ⚠️ 第 4 步**无条件**乘系数（``× 1.0`` 是恒等，且 ``round`` 一个已经 round 过的值仍是它
    自己），于是「没有触发」那一档不需要一条 ``if``——少一个分支就少一个可能写错的地方。
    """
    # ① 三个触发的判定（比较符一律严格；缺输入一律不触发且留痕）
    triggered: list[str] = []
    skipped: list[str] = []
    if inp.bmi is None:
        skipped.append(_SKIP_BMI)
    elif inp.bmi > _BMI_LIMIT:
        triggered.append("bmi_over_30")
    if inp.muscle_mass_kg is None:
        skipped.append(_SKIP_MUSCLE_MASS)
    if inp.muscle_p10 is None:
        skipped.append(_SKIP_MUSCLE_P10)
    if inp.muscle_mass_kg is not None and inp.muscle_p10 is not None:
        if inp.muscle_mass_kg < inp.muscle_p10:
            triggered.append("muscle_low_p10")
    if inp.body_fat_abnormal:
        triggered.append("body_fat_abnormal")

    # ② 跨表翻译 + 下调系数相乘（P5-A9 / P5-A6）
    volume_factor = 1.0
    equivalence_triggers: list[str] = []
    addon_requests: list[tuple[str, str]] = []
    for name in triggered:
        reduction_key, addon_when = _TRIGGER_MAP[name]
        if reduction_key is not None:
            # ⚠️ 不 round：0.8 × 0.9 亲跑是 0.7200000000000001（P5-A6）。系数本身保持
            #    乘积原值（断言它一律用 pytest.approx），被它乘出来的 weekly_volume 才 round。
            volume_factor *= eq.volume_reduction[reduction_key]
            equivalence_triggers.append(name)
        if addon_when is not None:
            addon_requests.append((name, addon_when))

    warnings: list[str] = []
    substitutions: list[Substitution] = []
    needs_review = False
    unresolved: set[str] = set()

    # ③ 追加的 addon block（P5-A3 的追加口径：weekly_volume 0.0 + volume_unit "unspecified"）
    appended: list[AssembledBlock] = []
    for name, addon_when in addon_requests:
        matching = tuple(addon for addon in template.addons if addon.when == addon_when)
        if not matching:
            # 绿层 6 套全部 addons: []（P5-A3 亲扫坐实）→ **不凭空造模块**，只留一条 warning。
            # 造一个模块等于代码替专家写模板；留痕让教师看见，才是「宁可不自动，也不要自动错」。
            warnings.append(
                f"{name}: 模板 {template.template_id} 没有 when == {addon_when!r} 的 addon"
                f"（实测绿层 6 套全部是 addons: []，与 spec §7.4 :510 的冲突已由 Task 3 登记），"
                f"故不凭空造模块——需要它请用教师覆盖（OverrideKind.SUBSTITUTE_EXERCISE / "
                f"VOLUME_SCALE）"
            )
        for addon in matching:
            # ⚠️ 不校验 addon.module 在不在动作库里（单一所有者：加载器已经校验过），
            #    故一个悬空的 module 在这里 surfaces 成 KeyError 而不是 ValueError。
            spec = exercises[addon.module]
            appended.append(
                AssembledBlock(
                    exercise_ref=spec.ref,
                    exercise_name=spec.name,
                    video_url=spec.video_url,
                    impact_level=spec.impact_level,
                    intensity_text=_ADDON_INTENSITY_TEXT,
                    hr_zone=None,
                    structure={},
                    # weekly_volume = 0.0 是**决定不是偷懒**：Addon 没有 structure，量无从算起，
                    # 编造一个数就是把「不知道」讲成「知道」（Plan01 Ruling 134 的同一条纪律）。
                    weekly_volume=0.0,
                    volume_unit="unspecified",
                    sessions_per_week=template.weekly_frequency,
                )
            )
            warnings.append(
                f"addon {addon.module} 的训练量未指定（weekly_volume = 0.0），"
                f"需教师用 VOLUME_SCALE 覆盖"
            )
            if addon_when == _TRIGGER_MAP["muscle_low_p10"][1]:
                warnings.append(_MUSCLE_LOW_WARNING.format(module=addon.module))

    # ④⑤ 逐 block 替换 + 下调，再把 addon 追加到每一课的末尾
    weeks: list = []
    for week in pkg.weeks:
        sessions = []
        for session in week.sessions:
            blocks: list[AssembledBlock] = []
            for block in session.blocks:
                current = block
                if equivalence_triggers and block.impact_level is ImpactLevel.HIGH:
                    # 冲击上限取 LOW：spec §7.4「换低冲击等价动作」，而真表里 10 条映射的
                    # max_impact 全是 low。lookup 按 IMPACT_RANK 过滤，故 ceiling=LOW 只认 low 替身。
                    substitute = eq.lookup(block.exercise_ref, ImpactLevel.LOW)
                    if substitute is None:
                        # Review Focus 第 5 条：**不静默跳过**，且该 block 原样保留
                        needs_review = True
                        if block.exercise_ref not in unresolved:
                            unresolved.add(block.exercise_ref)
                            warnings.append(
                                f"{equivalence_triggers[0]}: 动作 {block.exercise_ref!r} 在等价"
                                f"映射表 v{eq.version} 里找不到冲击 <= "
                                f"{ImpactLevel.LOW.value} 的替身；该 block **原样保留**"
                                f"（不删除、不替换——删掉动作会让训练量静默缩水），"
                                f"处方置 needs_review，教师端标记「需人工复核」"
                            )
                    else:
                        spec = exercises[substitute]
                        # 替身**继承原动作的剂量**（强度文案 / 心率区间 / structure / 单位 /
                        # 周课次全部原样）：换掉的是冲击，不是训练刺激。
                        current = replace(
                            block,
                            exercise_ref=spec.ref,
                            exercise_name=spec.name,
                            video_url=spec.video_url,
                            impact_level=spec.impact_level,
                        )
                        substitutions.append(
                            Substitution(
                                week=week.week,
                                day=session.day,
                                original_ref=block.exercise_ref,
                                substitute_ref=spec.ref,
                                trigger=equivalence_triggers[0],
                                equivalence_version=eq.version,
                            )
                        )
                blocks.append(
                    replace(
                        current,
                        weekly_volume=round(current.weekly_volume * volume_factor, 1),
                    )
                )
            blocks.extend(appended)
            sessions.append(replace(session, blocks=tuple(blocks)))
        weeks.append(replace(week, sessions=tuple(sessions)))

    # ⑥ 快照：assemble 的 12 个键一个不改，追加**至多 3 个**（P5-A7）
    snapshot = {
        **pkg.assembly_snapshot,
        "safety_triggers": triggered,
        "safety_skipped": skipped,
        "safety_volume_factor": volume_factor,
    }
    return SafetyOutcome(
        package=replace(pkg, weeks=tuple(weeks), assembly_snapshot=snapshot),
        substitutions=tuple(substitutions),
        needs_review=needs_review,
        warnings=tuple(warnings),
    )

# backend/tests/domain/test_prescription_match.py
"""模板匹配器 :func:`app.domain.prescription.match_template` 的守卫（Plan 02 Task 4）。

**本文件的核心是一条 32 格穷举**（:data:`_MATRIX_32`）：4 层 × 4 桶（3 个真桶 +
``None``）× 2 体成分 = **32**。它同时是三件事的唯一守卫：

1. **分类结果**：``{NO_LAYER: 8, NO_BUCKET: 6, UNREACHABLE: 3, MATCHED: 15}``
   （简报 Task 4 Step 1 的字面分类；``NO_TEMPLATE`` 与 ``NOT_APPROVED`` 在**满矩阵 +
   18 套全 ``approved``** 的真数据上是 **0 格**，故各由一条附加测试单独守）；
2. **15 个 ``MATCHED`` 各自命中哪一套模板**（``template_id`` 逐个字面写死）；
3. **优先级链的顺序**——这是最容易被漏掉的一件。链是::

       NO_LAYER → NO_BUCKET → NO_TEMPLATE → UNREACHABLE → NOT_APPROVED → MATCHED

   而它的**承重处**是「``NO_BUCKET`` 先于 ``UNREACHABLE``」：``(green, None, abnormal)``
   这一格同时满足「桶为空」与「绿层 + 体成分异常」两个条件，顺序对调之后分类变成
   ``{NO_LAYER: 8, NO_BUCKET: 4, UNREACHABLE: 5, MATCHED: 15}``——**总数仍是 32**。
   即「计数对得上」证明不了顺序对，只有一格一格看期望表才发现（简报 P4-A3）。
   故 :data:`_MATRIX_32` **按链的顺序排列**，并另有一条单格测试
   :func:`test_the_load_bearing_cell_green_none_abnormal_is_no_bucket_not_unreachable`
   把那一格单独钉住。

**期望侧一律字面写死**（硬规矩 #35 / Global Constraint #4）：``status`` 与 15 个
``template_id`` 都**不从** :func:`app.refdata_prescription.templates` 反推。实际侧才是
真数据（18 套 YAML 加载出来的映射），两侧不同源。

⚠️ **本文件守不住什么**（硬规矩 #39）：

* **不守「18 套恰好覆盖满矩阵」**——那是
  :func:`tests.domain.test_prescription_templates.test_exactly_eighteen_templates_cover_the_full_matrix`
  的职责。本文件的穷举**依赖**它：真数据少一格，那一格会被判 ``NO_TEMPLATE`` 而
  :data:`_MATRIX_32` 的期望值是 ``MATCHED``，于是本文件也会红——但红的原因是数据、
  不是匹配器，两条一起看才分得清。
* **不守 ``reachable`` 与 ``is_reachable`` 一致**：匹配器读的是**字段**
  :attr:`Template.reachable`（简报 P4-A2 的裁定），字段与维度组合是否矛盾由加载器
  :func:`app.refdata_prescription.load_templates` 校验。谁绕过加载器手工构造一个
  ``reachable=True`` 的 ``(green, *, abnormal)`` 模板，本文件**不会红**——
  :func:`test_a_hand_built_reachable_green_abnormal_template_is_matched` 把这件事
  显式钉成**期望行为**，免得下一个人以为它是漏洞。
* **不守 ``reason`` 的完整文案**：只钉 ``NO_LAYER`` 那一支必须与 Plan 01 的 Z0 文案
  **逐字相同**（:func:`test_no_layer_reason_is_verbatim_the_stratify_z0_reason`，那是
  Global Constraint #3 的单一所有者要求），其余各支只钉「非空」与「必须出现的关键词」
  （``NOT_APPROVED`` 必须含「待审校」——spec §11.2 那一行的逐字要求；``NO_TEMPLATE``
  必须指出缺哪一格——简报 Task 4「决定」第 3 条）。改一个标点不会红，这是刻意的：
  把整句钉死会让「教师端措辞微调」变成一次需要改测试的变更。
"""
import dataclasses

from app import refdata_prescription as rp
from app.domain.prescription import (
    Layer,
    MatchInput,
    MatchOutcome,
    MatchStatus,
    ReviewStatus,
    match_template,
)

# ---------------------------------------------------------------------------
# 期望侧的字面量（一律不从被测对象反推，硬规矩 #35）
# ---------------------------------------------------------------------------

#: 32 格穷举的期望表：``(层, 主导短板, 体成分异常, 期望 status, 期望 template_id)``。
#:
#: **排列按优先级链的顺序**（``NO_LAYER`` → ``NO_BUCKET`` → ``NO_TEMPLATE`` →
#: ``UNREACHABLE`` → ``NOT_APPROVED`` → ``MATCHED``），故读者从表的排列就能看出
#: 「顺序是被测的」。**``template_id`` 逐个抄自 ``backend/data/prescription/`` 的
#: 18 个文件名**（加载器要求文件名 == ``template_id``，由
#: :func:`tests.domain.test_prescription_templates.test_every_template_id_matches_its_filename`
#: 守），不从 :func:`app.refdata_prescription.templates` 读回来。
#:
#: 主导短板一律写**字面字符串**（``"endurance"`` 一类）而不是 ``WeaknessBucket.X``：
#: :class:`MatchInput` 的 ``dominant_bucket`` 标注就是 ``str | None``（它来自
#: :attr:`app.domain.derive.WeaknessResult.dominant_bucket`，那一侧是 ``str``），
#: 且字面串才构成「期望侧与被测词表不同源」。
_MATRIX_32 = [
    # ── ① NO_LAYER：``insufficient_data`` 层 × 4 桶 × 2 体成分 = 8 格 ──────────
    # Z0 闸门（spec §6.3①）在 valid_count < 4 时不产出分层标签，故这一层的任何学生
    # 都拿不到处方；4 个桶（含 None）与 2 个体成分档一律同判。
    (Layer.INSUFFICIENT, "endurance", False, MatchStatus.NO_LAYER, None),
    (Layer.INSUFFICIENT, "endurance", True, MatchStatus.NO_LAYER, None),
    (Layer.INSUFFICIENT, "strength", False, MatchStatus.NO_LAYER, None),
    (Layer.INSUFFICIENT, "strength", True, MatchStatus.NO_LAYER, None),
    (Layer.INSUFFICIENT, "speed_flexibility", False, MatchStatus.NO_LAYER, None),
    (Layer.INSUFFICIENT, "speed_flexibility", True, MatchStatus.NO_LAYER, None),
    (Layer.INSUFFICIENT, None, False, MatchStatus.NO_LAYER, None),
    (Layer.INSUFFICIENT, None, True, MatchStatus.NO_LAYER, None),
    # ── ② NO_BUCKET：3 个真层 × 桶为 None × 2 体成分 = 6 格 ────────────────────
    (Layer.RED, None, False, MatchStatus.NO_BUCKET, None),
    (Layer.RED, None, True, MatchStatus.NO_BUCKET, None),
    (Layer.YELLOW, None, False, MatchStatus.NO_BUCKET, None),
    (Layer.YELLOW, None, True, MatchStatus.NO_BUCKET, None),
    (Layer.GREEN, None, False, MatchStatus.NO_BUCKET, None),
    # ⚠️ 承重格：它同时满足「桶为空」与「绿层 + 体成分异常」（后者是 UNREACHABLE 的
    # 判据）。链上 NO_BUCKET 在前，故必须判 NO_BUCKET。单独再钉一次，见
    # test_the_load_bearing_cell_green_none_abnormal_is_no_bucket_not_unreachable。
    (Layer.GREEN, None, True, MatchStatus.NO_BUCKET, None),
    # ── ③ NO_TEMPLATE：满矩阵下 0 格 ───────────────────────────────────────────
    # 真数据 18 套覆盖 3 层 × 3 桶 × 2 体成分的全部 18 格，故穷举里走不到这一支。
    # 它由 test_match_rejects_a_missing_matrix_cell 用「从注入的映射里删掉一格」守。
    # ── ④ UNREACHABLE：``(green, *, abnormal)`` 3 套预留位 = 3 格 ──────────────
    # spec §7.1：「按 §6.2 决策表，绿色层必然 NOT C，因此 (green, *, abnormal) 这 3 套
    # 当前不可达」「保留为预留位，不删除…生成器对这 3 套标记 reachable: false，
    # 不参与匹配」。
    (Layer.GREEN, "endurance", True, MatchStatus.UNREACHABLE, None),
    (Layer.GREEN, "strength", True, MatchStatus.UNREACHABLE, None),
    (Layer.GREEN, "speed_flexibility", True, MatchStatus.UNREACHABLE, None),
    # ── ⑤ NOT_APPROVED：18 套今天全是 approved，故 0 格 ────────────────────────
    # 由 test_match_rejects_an_unapproved_template 用 dataclasses.replace 构造一个
    # review_status=PENDING 的副本守（不必改 YAML，故 18 个指纹一个都不动）。
    # ── ⑥ MATCHED：其余 15 格 ─────────────────────────────────────────────────
    (Layer.RED, "endurance", False, MatchStatus.MATCHED, "RED-END-NOR-02"),
    (Layer.RED, "endurance", True, MatchStatus.MATCHED, "RED-END-ABN-01"),
    (Layer.RED, "strength", False, MatchStatus.MATCHED, "RED-STR-NOR-04"),
    (Layer.RED, "strength", True, MatchStatus.MATCHED, "RED-STR-ABN-03"),
    (Layer.RED, "speed_flexibility", False, MatchStatus.MATCHED, "RED-SPD-NOR-06"),
    (Layer.RED, "speed_flexibility", True, MatchStatus.MATCHED, "RED-SPD-ABN-05"),
    (Layer.YELLOW, "endurance", False, MatchStatus.MATCHED, "YEL-END-NOR-08"),
    (Layer.YELLOW, "endurance", True, MatchStatus.MATCHED, "YEL-END-ABN-07"),
    (Layer.YELLOW, "strength", False, MatchStatus.MATCHED, "YEL-STR-NOR-10"),
    (Layer.YELLOW, "strength", True, MatchStatus.MATCHED, "YEL-STR-ABN-09"),
    (Layer.YELLOW, "speed_flexibility", False, MatchStatus.MATCHED, "YEL-SPD-NOR-12"),
    (Layer.YELLOW, "speed_flexibility", True, MatchStatus.MATCHED, "YEL-SPD-ABN-11"),
    (Layer.GREEN, "endurance", False, MatchStatus.MATCHED, "GRN-END-NOR-14"),
    (Layer.GREEN, "strength", False, MatchStatus.MATCHED, "GRN-STR-NOR-16"),
    (Layer.GREEN, "speed_flexibility", False, MatchStatus.MATCHED, "GRN-SPD-NOR-18"),
]

#: 穷举分类的期望计数，**字面写死**（简报 Task 4 Step 1 的 8/6/3/15）。
#: ⚠️ 这四个数**加起来恒为 32**，故它们对「链的顺序」不敏感（顺序对调后是
#: 8/4/5/15，总和仍是 32）——真正钉住顺序的是 :data:`_MATRIX_32` 逐格比对。
_EXPECTED_TALLY = {
    MatchStatus.NO_LAYER: 8,
    MatchStatus.NO_BUCKET: 6,
    MatchStatus.UNREACHABLE: 3,
    MatchStatus.MATCHED: 15,
}


def _inp(layer: Layer, bucket: str | None, abnormal: bool) -> MatchInput:
    return MatchInput(layer=layer, dominant_bucket=bucket, body_comp_abnormal=abnormal)


# ---------------------------------------------------------------------------
# ① 32 格穷举
# ---------------------------------------------------------------------------


def test_thirty_two_cell_matrix_is_classified_cell_by_cell():
    """32 格逐格比对 ``status`` 与 ``template_id``（实际侧 = 真数据，期望侧 = 字面表）。

    **红/绿双输入**（硬规矩 #50）：绿输入 = 今天的 18 套真数据（32 格逐格相符）；
    红输入 = :func:`test_match_rejects_an_unapproved_template` 与
    :func:`test_match_rejects_a_missing_matrix_cell` 两条各自合成的 ``NOT_APPROVED`` /
    ``NO_TEMPLATE`` 态——它们证明「本条 32 格全绿」不是恒真式：把两个判据从
    :func:`match_template` 里删掉，本条会分别红 3 格与 0 格，而那两条会红 1 格。

    **offender 一次性报全**（照 :mod:`tests.architecture.test_layering` 的口径）：
    逐格 ``assert`` 的话第一个红会盖住后面的，而一条链上的顺序错误往往同时打乱多格。
    """
    templates = rp.templates()
    offenders: list[str] = []
    for layer, bucket, abnormal, want_status, want_id in _MATRIX_32:
        got = match_template(_inp(layer, bucket, abnormal), templates)
        where = f"({layer.value}, {bucket}, {'abnormal' if abnormal else 'normal'})"
        if got.status is not want_status:
            offenders.append(f"{where}: status = {got.status.value}，期望 {want_status.value}")
        if want_id is None:
            if got.template is not None:
                offenders.append(f"{where}: 不该带模板，却带了 {got.template.template_id}")
        elif got.template is None:
            offenders.append(f"{where}: 期望命中 {want_id}，实际 template 是 None")
        elif got.template.template_id != want_id:
            offenders.append(f"{where}: 命中 {got.template.template_id}，期望 {want_id}")
        if not got.reason:
            offenders.append(f"{where}: reason 是空的（六种 status 都必须留痕）")
    assert offenders == [], "32 格穷举与期望表不符：\n" + "\n".join(offenders)


def test_thirty_two_cell_matrix_is_exhaustive_and_tallies_to_the_literal_counts():
    """表**本身**的自校：32 行、无重复、覆盖全笛卡尔积、四类计数逐字相符。

    这一条守的是 :data:`_MATRIX_32`，不是 :func:`match_template`（硬规矩 #56：主语要标
    出来）。没有它，「穷举」这个名字就没有守卫——谁删掉一行，上一条测试照样全绿。
    """
    assert len(_MATRIX_32) == 32, f"穷举表应是 32 行，实为 {len(_MATRIX_32)}"
    cells = [(layer, bucket, abnormal) for layer, bucket, abnormal, _s, _t in _MATRIX_32]
    assert len(set(cells)) == 32, "穷举表里有重复的组合"
    # 全笛卡尔积：4 层 × 4 桶 × 2 体成分
    product = {
        (layer, bucket, abnormal)
        for layer in (Layer.RED, Layer.YELLOW, Layer.GREEN, Layer.INSUFFICIENT)
        for bucket in ("endurance", "strength", "speed_flexibility", None)
        for abnormal in (False, True)
    }
    assert set(cells) == product, f"穷举表不是全笛卡尔积：缺 {sorted(product - set(cells))}"

    tally: dict[MatchStatus, int] = {}
    for _layer, _bucket, _abnormal, status, _want_id in _MATRIX_32:
        tally[status] = tally.get(status, 0) + 1
    assert tally == _EXPECTED_TALLY, f"分类计数 = {tally}，期望 {_EXPECTED_TALLY}"


def test_the_load_bearing_cell_green_none_abnormal_is_no_bucket_not_unreachable():
    """``(green, None, abnormal)`` 必须判 **NO_BUCKET**、不是 UNREACHABLE（P4-A3 承重处）。

    这一格是**唯一**能证明「链的顺序被测住了」的输入：它同时满足两个判据。顺序对调后
    32 格的分类从 ``{8, 6, 3, 15}`` 变成 ``{8, 4, 5, 15}``、**总数仍是 32**，故只看计数
    的守卫抓不到；只有把这一格单独钉住，变异「把 ``NO_BUCKET`` 与 ``UNREACHABLE`` 的检查
    顺序对调」才会红（本轮变异 ④ 打的就是它）。
    """
    got = match_template(_inp(Layer.GREEN, None, True), rp.templates())
    assert got.status is MatchStatus.NO_BUCKET, f"实为 {got.status.value}"
    assert got.template is None
    # 反面对照：同一层同一体成分、桶**非**空时判的是 UNREACHABLE（证明两条判据都在场，
    # 而不是「这一格恒判 NO_BUCKET」把 UNREACHABLE 那一支一起关掉了）
    control = match_template(_inp(Layer.GREEN, "endurance", True), rp.templates())
    assert control.status is MatchStatus.UNREACHABLE, f"对照格实为 {control.status.value}"


# ---------------------------------------------------------------------------
# ② 穷举走不到的两个 status
# ---------------------------------------------------------------------------


def test_match_rejects_an_unapproved_template():
    """``review_status != approved`` → **NOT_APPROVED**，且 ``reason`` 含「待审校」。

    出处：spec §7.2「**``review.status != approved`` 的模板拒绝用于生成**」与 §11.2 的
    B 类算法降级表那一行「模板 ``review.status != approved`` | 拒绝生成，返回「模板待审校」，
    教师端提示」——故 ``reason`` 里必须出现「待审校」这三个字，它是教师端的原文。

    **不改 YAML**：18 个文件的字节被
    :func:`tests.domain.test_prescription_templates.test_template_yaml_fingerprints_are_pinned`
    逐个钉住，故这里用 :func:`dataclasses.replace` 造一个 ``PENDING`` 的副本
    （``Template`` 是 frozen dataclass、构造期不校验 ``review_status``，这件事由
    :func:`tests.domain.test_prescription_templates.test_a_pending_template_is_constructible_so_task_4_has_something_to_reject`
    守）。

    ⚠️ **它同时钉住 ``UNREACHABLE`` 先于 ``NOT_APPROVED``**：把两套模板各造一个副本
    （一套不可达 + 未审校、一套可达 + 未审校），前者必须报 ``UNREACHABLE``
    （**规格事实**）而不是 ``NOT_APPROVED``（**流程状态**）。
    """
    templates = dict(rp.templates())
    pending = dataclasses.replace(
        templates["RED-END-ABN-01"], review_status=ReviewStatus.PENDING
    )
    templates["RED-END-ABN-01"] = pending
    got = match_template(_inp(Layer.RED, "endurance", True), templates)
    assert got.status is MatchStatus.NOT_APPROVED, f"实为 {got.status.value}"
    assert got.template is None, "拒绝生成时不得把模板带出去"
    assert "待审校" in got.reason, got.reason

    # UNREACHABLE 先于 NOT_APPROVED：绿层预留位那 3 套即使也标成 PENDING，仍报 UNREACHABLE
    unreachable = dict(rp.templates())
    unreachable["GRN-END-ABN-13"] = dataclasses.replace(
        unreachable["GRN-END-ABN-13"], review_status=ReviewStatus.PENDING
    )
    got2 = match_template(_inp(Layer.GREEN, "endurance", True), unreachable)
    assert got2.status is MatchStatus.UNREACHABLE, f"实为 {got2.status.value}"


def test_match_rejects_a_missing_matrix_cell():
    """注入的映射里少一格 → **NO_TEMPLATE**，且 ``reason`` 指出缺哪一格。

    **这一条守的是「YAML 少了一个文件」不会被当成「这个学生不该有处方」**（简报 Task 4
    Step 1）：两者在返回值上都是「没有模板」，而教师端要看到的是前者——那是一次数据
    故障，需要人去补文件。故 ``reason`` 必须把这一格的三个维度都报出来。

    ⚠️ **删的是注入的字典、不是磁盘上的文件**（Global Constraint #1：``templates`` 由
    调用方注入；本文件也因此一个字节都不碰 ``backend/data/``）。
    """
    templates = {k: v for k, v in rp.templates().items() if k != "RED-STR-NOR-04"}
    assert len(templates) == 17, "本条的前提是恰好删掉一格"
    got = match_template(_inp(Layer.RED, "strength", False), templates)
    assert got.status is MatchStatus.NO_TEMPLATE, f"实为 {got.status.value}"
    assert got.template is None
    # 三个维度都要在 reason 里出现（英文 token：仓内没有素质桶的中文名口径，见
    # app/domain/prescription/match.py 的模块 docstring）
    for needle in ("red", "strength", "normal"):
        assert needle in got.reason, f"reason 里没有 {needle!r}：{got.reason}"
    # 反面对照（硬规矩 #50）：其余 17 格不受影响
    assert match_template(_inp(Layer.RED, "endurance", False), templates).status is (
        MatchStatus.MATCHED
    )


# ---------------------------------------------------------------------------
# ③ 可复现性与公开面
# ---------------------------------------------------------------------------


def test_match_is_deterministic_under_dict_ordering():
    """把注入映射的插入顺序打乱，32 格的 :class:`MatchOutcome` 必须逐个**相等**。

    Plan 01 的 Ruling 100 就是为此把 :data:`app.domain.derive._BUCKET_ORDER` 做成声明序的
    （``derive.py`` 里那句注释逐字写着「故 dominant_bucket 不依赖 dict 的哈希顺序」）。
    匹配器这一侧的同类风险是「按插入顺序取第一个命中者」：加载器只校验 ``template_id``
    唯一、**不校验「一格至多一套模板」**，故两个同维度的模板在理论上可以共存，那时
    「取第一个」就会随字典顺序漂。:func:`match_template` 按 ``sorted(templates)`` 遍历，
    于是「同一份输入 → 同一个结果」与字典顺序无关。

    比对的是整个 :class:`MatchOutcome`（frozen dataclass，``==`` 逐字段比），不是只比
    ``status``：``template`` 那一栏若换成同维度的另一套，``status`` 仍是 ``MATCHED``。
    """
    forward = rp.templates()
    backward = dict(reversed(list(forward.items())))
    assert list(forward) != list(backward), "打乱后的顺序与原顺序相同，本条会空转"
    for layer, bucket, abnormal, _status, _want_id in _MATRIX_32:
        a = match_template(_inp(layer, bucket, abnormal), forward)
        b = match_template(_inp(layer, bucket, abnormal), backward)
        assert a == b, f"({layer.value}, {bucket}, {abnormal}) 下两种字典顺序给出不同结果"


def test_matched_outcome_carries_the_injected_template_object_itself():
    """``MATCHED`` 时 :attr:`MatchOutcome.template` **就是**注入映射里那一个对象（``is``）。

    抄一份出来（``dataclasses.replace`` 一类）会让 Task 6 的装配器拿到一个与
    :func:`app.refdata_prescription.templates` 单例**不同一**的对象：那 18 套是进程内
    共享的只读参考数据，副本会让「教师看到的模板」与「装配用的模板」在内存里分家。
    """
    templates = rp.templates()
    got = match_template(_inp(Layer.RED, "endurance", True), templates)
    assert got.template is templates["RED-END-ABN-01"]


def test_match_status_has_exactly_the_six_pinned_members():
    """:class:`MatchStatus` 恰好 6 个成员，**名字与值都字面写死**（简报 Produces 那一行）。

    两侧不同源（硬规矩 #35）：期望侧是抄进本测试的字面清单，实际侧是枚举本身。
    少一个成员会让某一类结果没有名字可报；改一个**值**会让 Task 9 落库的
    ``prescription.status`` 与已生成的行对不上。

    ⚠️ **声明序不是优先级序**：``MATCHED`` 排第一是照简报的列举序，链的顺序住在
    :func:`match_template` 的 docstring 与 :data:`_MATRIX_32` 的排列里。本条把声明序
    也一并钉住，于是「有人把枚举重排成链序」会红——那是一次需要显式承认的改动。
    """
    assert [(m.name, m.value) for m in MatchStatus] == [
        ("MATCHED", "matched"),
        ("NO_LAYER", "no_layer"),
        ("NO_BUCKET", "no_bucket"),
        ("UNREACHABLE", "unreachable"),
        ("NOT_APPROVED", "not_approved"),
        ("NO_TEMPLATE", "no_template"),
    ]


def test_match_input_and_outcome_are_frozen_dataclasses():
    """两个值对象都是 ``frozen=True`` 的 dataclass，字段名与顺序照简报 Produces 逐字。

    ``frozen`` 是承重的：:class:`MatchOutcome` 会被 Task 9 一路传到落库边界，途中谁
    ``outcome.status = MatchStatus.MATCHED`` 就是一次静默改写。字段**顺序**也钉住：
    Task 9 若按位置构造（``MatchOutcome(tpl, st, why)``），换序就换语义。
    """
    for cls, fields in (
        (MatchInput, ("layer", "dominant_bucket", "body_comp_abnormal")),
        (MatchOutcome, ("template", "status", "reason")),
    ):
        assert dataclasses.is_dataclass(cls), cls
        assert [f.name for f in dataclasses.fields(cls)] == list(fields), cls
        assert all(f.type is not None for f in dataclasses.fields(cls)), cls
    for cls in (MatchInput, MatchOutcome):
        assert cls.__dataclass_params__.frozen is True, f"{cls.__name__} 不是 frozen"


def test_no_layer_reason_is_verbatim_the_stratify_z0_reason():
    """``NO_LAYER`` 的 ``reason`` 与 Plan 01 的 Z0 文案**逐字相同**（Global Constraint #3）。

    唯一所有者是 :data:`app.domain.stratify._REASON` 的 ``RuleId.Z0`` 那一行。
    :mod:`app.domain.prescription.match` 里那一句是**副本**（它插值的是公开的
    ``MIN_VALID_COUNT``，故阈值改了两侧一起改），本条就是「漂移时谁会发现」的那个答案。

    **触私有名**：``_REASON`` 带前导下划线。照本仓既有惯例，生产码不 import 私有名
    （``app/domain/percentile.py`` 的 :func:`~app.domain.percentile.national_norm`
    docstring 逐字写着「不去 import 私有名」），而**测试**可以——先例是
    ``tests/domain/test_percentile.py`` 里那句带行内注释的
    ``from app.domain.indicators import _lower_is_better``。本条要比较的正是它，
    故就地 import 并在此写明理由。

    ⚠️ 两侧刻意**不是**同一份文本：期望侧从 ``stratify`` 取、实际侧从 ``match`` 的输出取，
    谁改了措辞本条就红。这**不违反**硬规矩 #35——#35 禁的是「从被测对象读回来跟自己比」，
    而这里被测的是 ``match``、期望侧来自**另一个模块**。
    """
    from app.domain.stratify import _REASON, RuleId  # 触私有名：本条要比较的正是它

    got = match_template(_inp(Layer.INSUFFICIENT, "endurance", False), rp.templates())
    assert got.status is MatchStatus.NO_LAYER
    assert got.reason == _REASON[RuleId.Z0], (
        f"NO_LAYER 的 reason 与 stratify 的 Z0 文案漂移了：{got.reason!r} != "
        f"{_REASON[RuleId.Z0]!r}"
    )


def test_a_hand_built_reachable_green_abnormal_template_is_matched():
    """**期望行为、不是漏洞**：手工构造一个 ``reachable=True`` 的 ``(green, *, abnormal)``
    模板，匹配器会把它 ``MATCHED`` 出去。

    这是简报 P4-A2 那条裁定的直接后果，也是 :mod:`app.domain.prescription.match` 的
    docstring 里「本函数守不住什么」那一段的可执行版本：匹配器读**字段**
    :attr:`Template.reachable`、不调 :func:`app.domain.prescription.is_reachable`
    （后者是**规则的**唯一所有者，前者的**数据**唯一所有者是 YAML 的 ``reachable`` 键，
    加载器已强制两者一致——匹配器再算一遍就是第三个住址）。故「字段与维度组合矛盾」
    这件事**只有加载器能发现**，绕过加载器就没人发现。

    把这条钉成测试的理由（硬规矩 #39）：不写下来，下一个人会以为匹配器漏了一个判据、
    顺手把 ``is_reachable`` 加回去，于是同一条规则有了两个住址。
    """
    templates = dict(rp.templates())
    templates["GRN-END-ABN-13"] = dataclasses.replace(
        templates["GRN-END-ABN-13"], reachable=True
    )
    got = match_template(_inp(Layer.GREEN, "endurance", True), templates)
    assert got.status is MatchStatus.MATCHED, f"实为 {got.status.value}"
    assert got.template.template_id == "GRN-END-ABN-13"

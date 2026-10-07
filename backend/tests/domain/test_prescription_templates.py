# backend/tests/domain/test_prescription_templates.py
"""18 套处方模板 + ``ImpactLevel`` 维度词表的守卫（Plan 02 Task 2 建、**Task 3 扩**）。

⚠️ **枚举的住址在 Task 2 fix round 1 变过一次**（Plan02 账本 Ruling 96）：它原来住在
``app/domain/prescription/templates.py``（P2-B1 的裁定），现与动作库的三个值对象一起
住在 :mod:`app.domain.prescription.exercises`——它是 ``ExerciseSpec.impact_level`` 与
``IMPACT_RANK`` 的类型，而 Task 3 的模板 dataclass 要引用动作库、不是反过来。
``templates.py`` 只余一句 re-export。

**本文件的 import 刻意仍指向 ``templates``、不改成所有者**：那是 ``templates.py`` 今天
**唯一**的导入方（``app/domain/prescription/__init__.py`` 改成从 ``exercises`` 取了），
而 domain 受 100% 覆盖约束——把这句改成从 ``exercises`` 导入，``templates.py`` 就没人
import、它那 2 条语句立刻变成 ``Miss 2``。顺带它也守着「re-export 与 ``__all__`` 还在」
——fix round 2 起这件事另有**显式**守卫：
:func:`test_templates_module_still_reexports_impact_level`（那句 import 只在**收集期**
响，删掉 ``__all__`` 它是不会红的）。
**文件名不改**：计划的 File Structure 把本文件列为 ``templates.py`` 的配对测试，Task 3
会往这里加模板 dataclass 的守卫；改名超出 Ruling 96 的范围，留给 Task 3 一并决定。

前三条断言的**期望侧都是字面量**，不从被测枚举读回来跟自己比（硬规矩 #35）：取值
``high`` / ``medium`` / ``low`` 与成员数 3 都抄自 spec §4.4 ``:239`` 的 ``exercise`` 行
（「**``impact_level``** ∈ {``high``, ``medium``, ``low``}」，行号取 shell 口径、绑定
commit ``fb5bddb``）。
第 4 条（:func:`test_templates_module_still_reexports_impact_level`，fix round 2 新加）的
期望侧同样是字面量（``["ImpactLevel"]``），实际侧是模块对象的属性与 ``is`` 同一性。

⚠️ **本文件守不住什么**（硬规矩 #39）：

* 它守 ``ImpactLevel`` 这个**词表本身**（下面三条），以及 ``templates.py`` 对它的那一句
  re-export 与 ``__all__``（fix round 2 加的第 4 条，账本 Ruling 107-3）。**不守**
  「``exercises.yaml`` 里每个动作的
  ``impact_level`` 取值合法」——那一条住在 ``tests/test_refdata_prescription.py``
  的 :func:`tests.test_refdata_prescription.test_every_exercise_has_a_valid_impact_level_and_targets`，
  两侧不同源：那边的实际侧来自 YAML 文件，这边的期望侧来自本枚举。
* 不守冲击等级之间的**序**（``high > medium > low``）：``ImpactLevel`` 继承 ``str``，
  故它的 ``<`` 是**字典序**（``"high" < "low" < "medium"``），与冲击序无关。序关系由
  ``test_equivalence_never_maps_to_a_higher_impact_level`` 字面写死。
* 不守 ``templates.py`` / ``exercises.py`` 的**无 I/O**：那是
  :mod:`tests.architecture.test_domain_purity` 的 allow-list 守卫（它扫 ``app/domain``
  全部 ``.py``，建出本子包后扫描面自动扩大，Plan02 账本 P2-D4 亲验不会红）。

--------------------------------------------------------------------------

**Task 3 往本文件加了什么**（简报 Step 1 的 9 条 + 控制者预检 P3-A5/A8/C2/C3 派生的
7 条；生产码基线 ``c29bc69``）：

==========================  ================================================
分组                        条目
==========================  ================================================
18 套模板的**内容**         全笛卡尔积 / 3 套不可达 / 其余 15 套可达 /
                            ``weekly_frequency`` 红 4 黄 3 绿 2 /
                            ``week_deltas`` 长度与减量形状 / ``sessions`` 总数 54 /
                            ``day`` 连续且每课至少 1 个 block / addons 的层归属 /
                            ``template_id`` 与文件名一致
**跨文件**不变量            每个 ``exercise_ref`` 与每个 addon ``module`` 都在动作库里、
                            每个 block 的 ``impact_level`` 与动作库**逐字相同**
                            （P2-B2：``exercises.yaml`` 是唯一所有者，模板里那份是副本）
**指纹**                    18 个文件逐个钉 sha256[:16]（行尾归一化为 LF 之后）
**词表与类型**              ``WeaknessBucket`` ↔ ``ITEM_BUCKET`` 的漂移守卫、
                            ``BodyCompState`` / ``ReviewStatus`` / ``INTENSITY_TYPES`` /
                            ``ADDON_TRIGGERS`` 字面钉住、``is_reachable`` 的真值表、
                            ``Template`` 可在构造期接受 ``PENDING``（P3-A8）
**加载器的响亮失败**        10 种坏形状（简报 ``:281`` 的 6 种 + P3-C3 的 2 种嵌套块缺失
                            + ``impact_level`` 与动作库不符 + ``reachable`` 与维度矛盾）
                            每种都点名**文件 + 行号**（Review Focus 第 1 条）
**列宽**                    ``template_ref`` / ``version`` / ``reviewer`` 三个**没有** CHECK
                            约束、因而不被 ``tests/db/test_models.py`` 那道遍历测试覆盖的
                            ``String(n)`` 列（P3-A5，与 Task 2 的 P2-A5 同型）
==========================  ================================================

⚠️ **本文件的测试会读盘**（``backend/data/prescription/*.yaml``）——这是刻意的：它们守的
是**知识资产的内容**，而内容只存在于磁盘上。被测的**生产码**仍然分两层：值对象与
``is_reachable`` 在 ``app/domain/prescription/templates.py``（无 I/O），解析与校验在
``app/refdata_prescription.py``。故本文件与 ``tests/test_refdata_prescription.py`` 的分工是
「**18 套模板这份资产** vs **加载/校验/投影这套机制**」，不是「domain vs 非 domain」。
"""
import hashlib
import pathlib

import pytest
import yaml

from app import refdata_prescription as rp
from app.db.models.prescription import PrescriptionTemplate
from app.domain.indicators import ITEM_BUCKET
from app.domain.prescription import exercises, templates
from app.domain.prescription.templates import (
    ADDON_TRIGGERS,
    INTENSITY_TYPES,
    TEMPLATE_LAYERS,
    Addon,
    Block,
    BodyCompState,
    ImpactLevel,
    Intensity,
    Layer,
    ReviewStatus,
    Session,
    Template,
    WeaknessBucket,
    is_reachable,
)
from app.domain.stratify import Layer as StratifyLayer


def test_impact_level_values_match_spec_4_4_verbatim():
    """取值与**声明序**逐字等于 spec §4.4 ``:239`` 写的那三个。

    声明序是承重的：``list(ImpactLevel)`` 的顺序被
    ``app/refdata_prescription.py`` 之外的消费者（如将来把词表印给专家审校的脚本）
    当作展示序，而 spec 那一行的书写序就是 high → medium → low。
    """
    assert [member.value for member in ImpactLevel] == ["high", "medium", "low"]
    assert len(ImpactLevel) == 3


def test_impact_level_is_a_str_enum_so_it_round_trips_through_the_db():
    """``ImpactLevel`` 是 ``str`` 子类：``exercise.impact_level`` 那一列是 ``String(8)``。

    不继承 ``str`` 的话，ORM 侧就得处处写 ``.value``。继承 ``str`` 之后
    ``ImpactLevel.HIGH == "high"`` 直接成立，落库与读回都是同一个字符串（下面四条断言）。

    ⚠️ **但「漏写 ``.value`` 会静默存成 ``"ImpactLevel.HIGH"``、撑破 ``String(8)``」不是本仓
    的失效形态**（fix round 3 实测更正；口径与
    ``app/domain/prescription/exercises.py`` 的 ``ImpactLevel`` docstring 完全一致）：``str``
    子类的字符数据**就是值本身**，DBAPI 绑定传的是字符数据而不是 ``str()`` 的返回值，故裸
    ``sqlite3`` 绑定 ``ImpactLevel.HIGH`` 落库实测是 ``'high'``（``typeof=text``、
    ``length()=4``），``String(8).bind_processor(sqlite 方言)`` 实测也返回 ``None``（值原样
    下传）。只有显式写 ``str(x)`` 才得到 ``'ImpactLevel.HIGH'``——那是 **16** 字符，不是
    此前印的 19。而生产路径一律写 ``.value``（``sync_exercises``），故这条路今天不可达。
    """
    assert issubclass(ImpactLevel, str)
    assert ImpactLevel.HIGH == "high"
    assert ImpactLevel.MEDIUM == "medium"
    assert ImpactLevel.LOW == "low"
    # 由字符串反查成员：加载 YAML 时把字面量收敛成枚举就走这一支
    assert ImpactLevel("medium") is ImpactLevel.MEDIUM


def test_impact_level_rejects_a_value_outside_spec_4_4():
    """词表外的值必须**当场炸**，不得静默变成一个第四档。

    第四档（如 ``"very_high"``）的后果不在写入侧而在读取侧：spec §7.4 ``:508`` 的安全
    后置只替换 ``impact_level: high``，一个拼错的 ``"hig"`` 会让 BMI > 30 的学生照旧
    被安排高冲击动作，而全链路没有任何一处报错——正是 Review Focus 第 5 条要防的
    「安全规则命中却被静默跳过」的上游形态。
    """
    for bad in ("very_high", "hig", "HIGH", "", "none"):
        with pytest.raises(ValueError):
            ImpactLevel(bad)


def test_templates_module_still_reexports_impact_level():
    """钉住 ``templates.py`` 的那一句 re-export 与它的 ``__all__``（账本 Ruling 107-3）。

    **这条守卫存在的理由是一种「退出码 0 的静默退化」**（Ruling 103 / 硬规矩 #67 那个形态）：
    ⚠️ **下面这段的数字是 Task 2 时点的历史值，Task 3 之后已经不成立，但失效形态本身仍然
    值得记着**（硬规矩 #19：写下测量条件就要写清时点）——Task 2 结案时 ``templates.py``
    只有 **2** 条语句（``from .exercises import ImpactLevel`` 与 ``__all__ = ["ImpactLevel"]``；
    coverage 表上是 ``2 stmts / 0 branch / 100%``），而它**唯一的导入方**是本文件顶部的
    **两句** import：``from app.domain.prescription import
    exercises, templates``（本条守卫用）与 ``from app.domain.prescription.templates import
    ImpactLevel``（下面三条用）。取证命令（``^`` 锚定行首，故 docstring 里的引文不会自己
    命中自己）::

        git grep -n "^from app.domain.prescription.templates import" -- backend

    Task 2 落盘后**只命中 1 处**，就是本文件顶部那一句 ``…templates import ImpactLevel``；
    另一句 ``from app.domain.prescription import …`` 把模式里的 ``.templates`` 去掉就数得到
    （命中 **2** 处，另一处是 ``tests/test_refdata_prescription.py`` 的
    ``exercises as exercises_mod``、**不含 ``templates``**）。⚠️ **不加 ``^`` 的计数不可用**：
    同一条命令去掉锚，会把 ``templates.py`` 自己 docstring 里的散文与本 docstring 里的
    这段引文一起算进来；把模式再松成 ``prescription.templates`` 更糟——正则里的 ``.``
    连 ``prescription_templates`` 这个**文件名**都匹配，于是它的命中数**每改一次本文件
    的散文就变一次**（Task 2 写这句话的前后就变过一次），不是一个稳定量，故不写进散文。
    这里只留锚定后的那**一个**数；要复核请自己跑上面那条命令（硬规矩 #19/#66）。

    **Task 3 之后这段脆弱性自然消失了**：``templates.py`` 现在有 3 个枚举、5 个 dataclass、
    3 张词表、1 个纯函数与 2 句 re-export，``prescription/__init__.py`` 也从它 import，故
    「没人 import 它 → 语句永不执行 → Miss N 而退出码仍 0」这条路已经堵死（当前 stmts 数
    见报告，**不写在这里**：它会随 Task 4-9 继续涨，写进来就是一条迟早过期的裸数字）。
    **但本条守卫不许删**——它守的从来不是覆盖率，而是**那句 re-export 与 ``__all__`` 还在**：
    删掉 re-export，``from app.domain.prescription.templates import ImpactLevel`` 会在
    **收集期** ImportError（响亮），而把 ``ImpactLevel`` 从 ``__all__`` 里删掉只让它
    「不再是显式公开面」——**没有一条测试会红**（``import *`` 那条路径今天没人走）。
    支 1 就是堵这个口子的。

    **静默退化是怎么发生的**（Task 2 实测复现，task-2-report 的变异 M-B4）：下一个人完全
    可能把这个「只有 re-export 的文件」当残留处理掉——最自然的做法不是删文件（那会在
    **收集期**炸、响亮），而是把本文件顶部那两句 ``templates`` 的 import 都改指所有者
    ``exercises``（一个看起来很合理的「去中间层」清理）。那样 ``templates.py`` 就没有任何
    导入方了 → 它那 2 条语句永不执行 → ``--cov=app/domain --cov-branch`` 报
    ``templates.py 2 stmts / Miss 2 / 0%``（缺的是 ``37-39``）、``TOTAL 441 stmts /
    Miss 2 / 99%``，**而 ``pytest`` 的退出码仍是 0**（Task 2 实测 ``529 passed, 1 skipped``）：
    覆盖率不是断言，只有人去看那张表才发现。**本条守卫堵这个口子的方式是它自己也成为
    一个导入方**——它引用 ``templates`` 这个模块对象，要绕过它就得连它一起删，而删掉它
    本条会 ``NameError`` 而红（Task 2 实测 ``1 failed, 530 passed``、退出码 1）。这就是
    Ruling 107-3 说的「同时把 Ruling 103 那个口子堵上」。

    **两支的主语**（硬规矩 #56）：支 1 钉 ``templates.__all__`` 的**字面内容与长度**；
    支 2 钉 ``templates.ImpactLevel`` 与 ``exercises.ImpactLevel`` 是**同一个对象**
    （``is``，不是 ``==``：``ImpactLevel`` 继承 ``str``，一个本地重定义的同值枚举会让
    ``==`` 成立而 ``is`` 不成立，而那正是「re-export 被换成本地定义」的失效形态）。
    ``Layer`` 的同一支另立一条
    （:func:`test_templates_module_still_reexports_layer`），主语不同故不并在本条里。

    **红/绿双输入**（硬规矩 #50；四个真变异 Task 2 都实跑过，逐支真值见 task-2-report
    §fr2.4）：绿输入 = 今天的真实状态（两支都实跑通过）。红输入：**M-B1**（把 re-export
    换成本地同值的 ``class ImpactLevel`` → **只有支 2 红**，``1 failed, 530 passed``；
    ``==`` 会成立而 ``is`` 不成立，故这一支必须用 ``is``）、**M-B2**（``__all__`` 里删掉
    ``"ImpactLevel"`` → **只有支 1 红**，``1 failed, 530 passed``。⚠️ 顶部那句
    ``from … import ImpactLevel`` 是**显式**导入、不看 ``__all__``，故它不会红——这正是
    需要支 1 的理由）、**M-B3**（整份 ``templates.py`` 删掉 → 本文件在**收集期**
    ImportError、``pytest`` **退出码 2**，根本跑不到覆盖率那一步）、**M-B4**（见上：两处
    import 都改指 ``exercises`` → 本条 ``NameError`` 而红，``1 failed, 530 passed``、
    退出码 1）。⚠️ 那四次的 passed 数是 Task 2 时点的，Task 3 之后基数变了，故这里只作
    历史记录、不当期望值用。

    **本条守不住什么**（硬规矩 #39）：不守 ``ImpactLevel`` 的**取值**（那是上面三条的事），
    也不守 ``prescription/__init__.py`` 的公开面（那 20 个名字由
    ``tests/test_refdata_prescription.py`` 的
    :func:`tests.test_refdata_prescription.test_prescription_public_namespace_is_pinned_verbatim`
    钉住）。**两份 ``__all__`` 必须一起改**（本模块一份、``prescription/__init__.py``
    一份）——Task 2 写在两个模块 docstring 里的这句叮嘱，Task 3 已经照办：支 1 的期望值
    从 ``["ImpactLevel"]`` 扩到 14 个名字，包那边从 7 个扩到 20 个。
    """
    assert templates.__all__ == [
        "ADDON_TRIGGERS",
        "INTENSITY_TYPES",
        "TEMPLATE_LAYERS",
        "Layer",
        "WeaknessBucket",
        "BodyCompState",
        "ReviewStatus",
        "Intensity",
        "Block",
        "Session",
        "Addon",
        "Template",
        "is_reachable",
        "ImpactLevel",
    ]
    assert templates.ImpactLevel is exercises.ImpactLevel


def test_templates_module_still_reexports_layer():
    """钉住 ``templates.py`` 对 ``Layer`` 的那一句 re-export（与上一条同构，主语不同）。

    **为什么是 re-export 而不是新建**（简报 Interfaces / Produces，P3-D4）：分层标签的
    唯一所有者是 :mod:`app.domain.stratify`——``stratification_result.label`` 那一列、
    ``RULE_ORDER`` 与 Z0 闸门都用它。模板的 ``layer`` 维度必须与它**逐字同一**，否则
    Task 4 的匹配器要在一处把 ``"red"`` 翻译成另一个枚举，而翻译表就是第二个所有者
    （Global Constraint #3）。

    **为什么本模块用绝对导入 ``from app.domain.stratify import Layer``、而不是相对的
    ``from ..stratify import Layer``**（P3-D4 要控制者不裁、由实现者选并说明理由）：
    与 Task 2 的选择保持一致。实测依据（``t3_probes/p02_probe_domain.py``，基线
    ``ddccba8``）：全仓 15 条相对导入**全部是 ``level == 1``**、分布 ``{1: 15}``，而
    ``app/domain/`` 既有的 5 个模块（``derive`` / ``indicators`` / ``percentile`` /
    ``stratify`` / ``prescription/exercises``）跨模块引用一律写绝对串
    （``from app.domain.indicators import ITEM_BUCKET``）。选相对导入会让
    ``tests/architecture/test_domain_purity.py`` 与 ``test_layering.py`` 里那两段
    「``level == 2`` 在真仓里**今天仍不存在**」的散文当场变假（账本 Ruling 104 那一格
    由「前瞻」变「真仓形状」），而那两个文件不在本 Task 的授权改动面里。故选绝对导入：
    **零处散文因此变假**，且与本仓既有风格一致。
    """
    assert templates.Layer is StratifyLayer
    assert Layer is StratifyLayer
    # 模板维度只有三个层；``insufficient_data`` 不是合法模板层（spec §6.1 的 Z0 闸门
    # 在那一档**不产出标签**，故没有任何学生会带着它来匹配模板）。加载器必须拒绝它，
    # 拒绝的那条断言在 :func:`test_loader_rejects_a_broken_template` 的参数化用例里。
    assert [member.value for member in Layer] == [
        "red", "yellow", "green", "insufficient_data",
    ]
    assert {t.layer.value for t in rp.templates().values()} == {"red", "yellow", "green"}


# ---------------------------------------------------------------------------
# 期望侧的字面量（一律不从被测 YAML 读回，硬规矩 #35）
# ---------------------------------------------------------------------------

#: 18 个 ``template_id``，**字面写死**。命名格式取自 spec §7.2 ``:454`` 的骨架首行
#: ``template_id: RED-END-ABN-01``，即 ``<层3>-<桶3>-<体成分3>-<序号2>``（大写、连字符、
#: **14 字符**）。三字母缩写里 spec 只给了 ``END`` 与 ``ABN``，其余由本 Task 定：
#: 层 ``RED`` / ``YEL`` / ``GRN``，桶 ``END`` / ``STR`` / ``SPD``，体成分 ``ABN`` / ``NOR``。
#: 末两位是**全局序号 01–18**，枚举序 = 层（红→黄→绿）× 短板
#: （endurance→strength→speed_flexibility）× 体成分（**abnormal→normal**）。
#: ⚠️ 体成分取「异常在前」是为了让 spec ``:454`` 那个字面示例 ``RED-END-ABN-01`` 由这条
#: 规则**原样重现**——spec 只给了这一个 id，任何「normal 在前」的定序都会让它变成 ``-02``，
#: 即与 spec 的字面冲突。全局唯一序号（而不是每层各 01-06）是为了让专家可以只说号不说维度。
TEMPLATE_IDS = (
    "RED-END-ABN-01", "RED-END-NOR-02", "RED-STR-ABN-03", "RED-STR-NOR-04",
    "RED-SPD-ABN-05", "RED-SPD-NOR-06",
    "YEL-END-ABN-07", "YEL-END-NOR-08", "YEL-STR-ABN-09", "YEL-STR-NOR-10",
    "YEL-SPD-ABN-11", "YEL-SPD-NOR-12",
    "GRN-END-ABN-13", "GRN-END-NOR-14", "GRN-STR-ABN-15", "GRN-STR-NOR-16",
    "GRN-SPD-ABN-17", "GRN-SPD-NOR-18",
)

#: spec §7.1 ``:445``「按 §6.2 决策表，绿色层必然 ``NOT C``，因此 ``(green, *, abnormal)``
#: 这 3 套**当前不可达**」；``:447``「保留为**预留位**、标记 ``reachable: false``、
#: 不参与匹配」。字面写死这 3 个 id。
UNREACHABLE_IDS = ("GRN-END-ABN-13", "GRN-STR-ABN-15", "GRN-SPD-ABN-17")

#: spec §7.2 ``:465`` 的行内注释逐字：「红 4 / 黄 3 / 绿 2（指导文件原文）」。
GUIDANCE_WEEKLY_FREQUENCY = {"red": 4, "yellow": 3, "green": 2}

#: spec §7.2 ``:464`` 的 ``microcycle_weeks: 4`` 与 ``:479`` 的
#: ``week_deltas: [1.00, 1.05, 1.10, 0.85]``（行内注释：「第 4 周减量，超量恢复」）。
MICROCYCLE_WEEKS = 4
WEEK_DELTAS = (1.00, 1.05, 1.10, 0.85)

#: 指导文件给的 addons（spec §7.2 ``:480-484`` 的骨架 + ``:487`` 的散文）：
#: 红层「体脂超标追加 10% 能量消耗模块」、黄层「体脂偏高附加 5min HIIT」、
#: 两层都是 ``muscle_low → resistance_priority``（骨架 ``:483-484`` + spec §7.4 ``:509``
#: 「肌肉量 < P10 → 同上，并提高抗阻模块比重」，与层无关）。**绿层指导文件没提** → 空。
GUIDANCE_ADDONS = {
    "red": (("body_fat_over", "energy_expenditure_plus_10pct"),
            ("muscle_low", "resistance_priority")),
    "yellow": (("body_fat_over", "energy_expenditure_plus_5min_hiit"),
               ("muscle_low", "resistance_priority")),
    "green": (),
}

#: 用户已裁定（简报「决定」段）：18 套全部 ``approved`` + 占位审校人 + **固定** ISO 日期。
#: ⚠️ 日期必须是字面量而不是 ``date.today()``：那会让 YAML 每次生成都变、指纹天天红。
#: 这一项已登记进 spec §14 第 **29** 项（P3-A3：编号由计划的 ``d40f36c`` 预分配）。
REVIEWER = "原型自审（占位）"
REVIEWED_AT = "2026-10-06"
TEMPLATE_VERSION = "1.0"

#: 18 个模板 YAML 各自的 sha256 前 16 位（大写），**行尾归一化为 LF 之后**计算，
#: 口径与 :data:`tests.test_refdata_prescription.EXERCISES_FINGERPRINT` 完全相同。
#:
#: **为什么逐个钉、而不是「18 个文件按 id 排序后拼接再哈希成一个值」**（简报 ``:280``
#: 把这个选择留给实现者并要求说明理由）：拼接哈希的报错只能说「这 18 个里有东西变了」，
#: 而这 18 份文件的**全部意义**就是「体育专家可独立审校」（spec §7.2 ``:449``）——
#: 专家改坏其中一份时，必须一眼知道是**哪一份**。逐个钉的代价是「改一个模板要改一行
#: 测试」，而这个代价正是 Task 2 给 ``exercises.yaml`` 立的那道闸的用意：
#: **知识资产的变更必须被显式承认**。键取 ``template_id`` 而不是文件名，于是「把文件改名」
#: 也会让本条红（它会变成一个 ``FileNotFoundError``），顺带钉住了「文件名 == template_id」
#: 这条约定（另有 :func:`test_every_template_id_matches_its_filename` 显式守它）。
TEMPLATE_FINGERPRINTS = {
    "RED-END-ABN-01": "C0C61D2140A521D0",   # 6865 B
    "RED-END-NOR-02": "FE91666F74C08CAF",   # 6863 B
    "RED-STR-ABN-03": "8F4D51E3377FA814",   # 7872 B
    "RED-STR-NOR-04": "3E8C365CD0B4C133",   # 7870 B
    "RED-SPD-ABN-05": "8E396D8BF85B6DBD",   # 7930 B
    "RED-SPD-NOR-06": "0EDDE329A6CA61AE",   # 7928 B
    "YEL-END-ABN-07": "D301AE8D8D3D6B7E",   # 6480 B
    "YEL-END-NOR-08": "F08B64A00D974F18",   # 6478 B
    "YEL-STR-ABN-09": "033CFAA2D1F93503",   # 6132 B
    "YEL-STR-NOR-10": "C1CDF7D18A1F87E4",   # 6130 B
    "YEL-SPD-ABN-11": "FA81CAD1B9050A9E",   # 7211 B
    "YEL-SPD-NOR-12": "524CD251936C79B1",   # 7209 B
    "GRN-END-ABN-13": "89842C7A0D8A6EA0",   # 7293 B（不可达的预留位之一）
    "GRN-END-NOR-14": "3B1DA3AAB8D6A322",   # 5983 B
    "GRN-STR-ABN-15": "91E660991C717944",   # 7092 B（不可达的预留位之一）
    "GRN-STR-NOR-16": "A5B406807FDEF7CC",   # 5782 B
    "GRN-SPD-ABN-17": "9ADB0CAC53A572F1",   # 7020 B（不可达的预留位之一）
    "GRN-SPD-NOR-18": "2389C1A03E6ABBCE",   # 5710 B
}
#: 18 个文件合计 **123 848 B**（取证脚本 ``t3_probes/p06_template_fps.py`` 实跑）。
#: 这个合计**不被任何断言钉住**——它是给人读的口径（硬规矩 #19），逐个钉的 18 个值已经
#: 蕴含它，再钉一次等于给「改一个模板」多一行要改的地方而不增加任何拦截力。


def _fingerprint(path: pathlib.Path) -> str:
    """行尾归一化为 LF 之后取 sha256 前 16 位（大写）。口径同 ``tests/test_refdata.py``。"""
    return hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()[:16].upper()


def _good_template_doc() -> dict:
    """一份**已知合法**的合成模板文档（红层 / 耐力 / 体成分异常 / 4 天），供加载器测试用。

    ⚠️ 它的 ``exercise_ref`` 与 ``impact_level`` 必须与**真动作库**一致（加载器做跨文件
    校验），故用的是 ``interval_run``（``high``）——spec §7.2 ``:470-471`` 骨架里的那一个，
    连 ``intensity`` 与 ``structure`` 也照骨架 ``:472-473`` 逐字抄。
    ``version`` 取 ``"9.9"`` 而不是 ``"1.0"``：真值由那 18 个文件自己的指纹钉住，合成用例
    用一个不可能撞上的号，读断言失败时一眼能分清手里是哪一份。
    """
    return {
        "template_id": "RED-END-ABN-01",
        "version": "9.9",
        "layer": "red",
        "weakness": "endurance",
        "body_comp": "abnormal",
        "reachable": True,
        "review": {
            "status": "approved",
            "reviewer": "合成用例",
            "reviewed_at": "2026-10-06",
        },
        "microcycle_weeks": MICROCYCLE_WEEKS,
        "weekly_frequency": 4,
        "sessions": [
            {
                "day": day,
                "focus": "耐力",
                "blocks": [{
                    "exercise_ref": "interval_run",
                    "impact_level": "high",
                    "intensity": {"type": "hrmax_pct", "low": 60, "high": 70},
                    "structure": {"sets": 4, "work_min": 3, "rest_min": 2},
                }],
            }
            for day in (1, 2, 3, 4)
        ],
        "progression": {"week_deltas": [1.00, 1.05, 1.10, 0.85]},
        "addons": [{"when": "body_fat_over", "module": "energy_expenditure_plus_10pct"}],
    }


def _write_template(tmp_path: pathlib.Path, doc: dict, text: str | None = None):
    """把一份模板文档按 **LF** 落到 ``tmp_path``，文件名 = ``template_id``。

    ``text`` 非 ``None`` 时直接落它（给「不是合法 YAML」那类用例用），否则 ``safe_dump``。
    ``sort_keys=False`` 让键序照文档书写序，于是行号索引与 spec §7.2 骨架的顺序对得上。
    """
    body = text if text is not None else yaml.safe_dump(
        doc, allow_unicode=True, sort_keys=False
    )
    name = f"{doc.get('template_id') or 'RED-END-ABN-01'}.yaml"
    path = tmp_path / name
    path.write_text(body, encoding="utf-8", newline="\n")
    return path


def _template(**overrides) -> Template:
    """直接构造一个 :class:`Template`（绕过加载器），未给的字段取合成用例的默认值。"""
    fields: dict = {
        "template_id": "RED-END-ABN-01",
        "version": "9.9",
        "layer": Layer.RED,
        "weakness": WeaknessBucket.ENDURANCE,
        "body_comp": BodyCompState.ABNORMAL,
        "reachable": True,
        "review_status": ReviewStatus.APPROVED,
        "reviewer": "合成用例",
        "reviewed_at": "2026-10-06",
        "microcycle_weeks": 4,
        "weekly_frequency": 4,
        "sessions": (
            Session(day=1, focus="耐力", blocks=(
                Block(
                    exercise_ref="interval_run",
                    impact_level=ImpactLevel.HIGH,
                    intensity=Intensity(type="hrmax_pct", low=60.0, high=70.0),
                    structure={"sets": 4, "work_min": 3, "rest_min": 2},
                ),
            )),
        ),
        "week_deltas": WEEK_DELTAS,
        "addons": (Addon(when="body_fat_over",
                        module="energy_expenditure_plus_10pct"),),
    }
    fields.update(overrides)
    return Template(**fields)


# ---------------------------------------------------------------------------
# 维度词表与值对象（domain 侧，不读盘）
# ---------------------------------------------------------------------------


def test_template_layers_are_the_first_three_layer_members():
    """:data:`TEMPLATE_LAYERS` 恰好是 ``Layer`` 的前三个成员，**不含** ``insufficient_data``。

    出处：spec §7.1 ``:443`` 的「层(3)」与 §7.2 ``:456`` 的行内注释「``red | yellow |
    green``」；而 ``Layer`` 有**四个**成员（第四个是 ``INSUFFICIENT``，spec §6.1 的 Z0
    闸门在 ``valid_count < 4`` 时产出它、**不分层**）。故「模板维度只有三层」是一条
    **排除**声明，不是「``Layer`` 只有三个成员」——两者的差集正是那个不该被匹配到的档。
    """
    assert TEMPLATE_LAYERS == frozenset({Layer.RED, Layer.YELLOW, Layer.GREEN})
    assert Layer.INSUFFICIENT not in TEMPLATE_LAYERS
    assert len(TEMPLATE_LAYERS) == 3


def test_weakness_bucket_values_are_the_three_item_bucket_names():
    """``WeaknessBucket`` 的取值与**声明序**逐字钉住，并与 ``ITEM_BUCKET`` 对账。

    **两支不同源**（硬规矩 #35 的例外形态，Plan02 账本 P3-A11 亲验）：支 1 的期望侧是
    字面量、实际侧是本枚举；支 2 是**跨所有者对账**——``WeaknessBucket`` 由
    ``templates.py`` 声明，``ITEM_BUCKET`` 由 :mod:`app.domain.indicators` 声明，两个
    声明者互相独立，故这条不是「拿自己跟自己比」。它守的失效形态是：有人往
    ``ITEM_BUCKET`` 加第四个桶（或改掉一个桶名）而忘了同步模板维度，于是分层引擎产出的
    主导短板再也匹配不到任何一套模板——而那是**静默**的（匹配器返回「无模板」，
    不是抛错）。
    """
    assert [member.value for member in WeaknessBucket] == [
        "endurance", "strength", "speed_flexibility",
    ]
    assert {bucket.value for bucket in WeaknessBucket} == set(ITEM_BUCKET.values()) - {None}


def test_body_comp_state_and_review_status_values_match_spec_7_2_verbatim():
    """两个二元词表逐字抄自 spec §7.2 骨架的行内注释（``:458`` 与 ``:461``）。

    **声明序也钉住**：``:458`` 写的是「``normal | abnormal``」、``:461`` 写的是
    「``pending | approved``」，与下面的顺序一致。序本身今天不承重（没有任何消费方按
    ``list(BodyCompState)`` 展示），钉它是为了让「照 spec 那一行的书写序声明」这件事
    可复查——与 :func:`test_impact_level_values_match_spec_4_4_verbatim` 同口径。
    """
    assert [member.value for member in BodyCompState] == ["normal", "abnormal"]
    assert [member.value for member in ReviewStatus] == ["pending", "approved"]
    for enum, bad in ((BodyCompState, "overweight"), (ReviewStatus, "rejected")):
        with pytest.raises(ValueError):
            enum(bad)


def test_intensity_types_and_addon_triggers_are_pinned_verbatim():
    """两张词表字面钉住，且 18 套模板里实际出现的取值都落在词表内。

    ``INTENSITY_TYPES`` 的四个取值出自简报 Interfaces / Produces 对 ``Intensity.type`` 的
    列举（``hrmax_pct`` | ``onerm_pct`` | ``rpe`` | ``none``），其中前两个能在 spec §7.2
    骨架 ``:472`` 与 ``:476`` 逐字找到；``rpe`` 的出处是 spec §8.2 的课堂快评 RPE 0–10
    （Plan 03 的预警侧要用同一套强度语义），``none`` 是「指导文件没给这一层的强度参数」
    时的**显式**取值——留空与写 ``none`` 不是一回事，留空分不清「不需要」与「忘了填」
    （与 ``exercises.yaml`` 的 ``equipment: none`` 同一条理由）。

    ``ADDON_TRIGGERS`` 的两个取值出自 spec §7.2 骨架 ``:481`` 与 ``:483``。
    ⚠️ **它与 :data:`app.domain.prescription.exercises.EQUIVALENCE_TRIGGERS` 是两张不同的
    词表、刻意不合并**：那一张（``bmi_over_30`` / ``muscle_low_p10``）是**走等价表**的两个
    触发（spec §7.4 ``:508-509``），这一张是**走模板 addons**的（spec §7.4 ``:510``，
    「追加模板 ``addons`` 中的能量消耗模块」、**不查等价表**）。两套字面值也不同，
    合并会让「哪条路该走哪张表」在类型上看不出来（Plan02 账本 P2-C3）。
    """
    assert INTENSITY_TYPES == frozenset({"hrmax_pct", "onerm_pct", "rpe", "none"})
    assert ADDON_TRIGGERS == frozenset({"body_fat_over", "muscle_low"})

    loaded = rp.templates()
    used_types = {
        block.intensity.type
        for template in loaded.values()
        for session in template.sessions
        for block in session.blocks
    }
    assert used_types <= INTENSITY_TYPES, sorted(used_types - INTENSITY_TYPES)
    used_when = {addon.when for template in loaded.values() for addon in template.addons}
    assert used_when <= ADDON_TRIGGERS, sorted(used_when - ADDON_TRIGGERS)


def test_is_reachable_is_false_for_exactly_the_green_abnormal_cells():
    """:func:`is_reachable` 的真值表：6 个「层 × 体成分」格里**恰好一格**为假。

    出处：spec §7.1 ``:445``「按 §6.2 决策表，绿色层必然 ``NOT C``，因此
    ``(green, *, abnormal)`` 这 3 套**当前不可达**」。

    **它是「``reachable`` 这一列的唯一所有者」**，两处消费：① 加载器用它校验 YAML 里写的
    ``reachable`` 与维度组合**不矛盾**（矛盾就在加载时响亮失败——Review Focus 第 1 条
    点名的第 4 种坏形状）；② Task 4 的匹配器按它排除预留位（spec §7.1 ``:447``
    「不参与匹配」）。故将来分层规则若真的调整（spec §7.1 ``:447`` 的②「模板位已就绪」），
    **改这一个函数**就能让那 3 套上线；只翻 YAML 里的 ``reachable`` 而不动本函数，
    加载器会拒绝——那是刻意的耦合：一份规则两个住址必然漂移（Global Constraint #3）。

    ``weakness`` 不参与判定，故本函数的签名里没有它（spec 的不可达结论对三个桶同时成立，
    写作 ``(green, *, abnormal)``）。
    """
    false_cells = [
        (layer.value, state.value)
        for layer in (Layer.RED, Layer.YELLOW, Layer.GREEN)
        for state in (BodyCompState.NORMAL, BodyCompState.ABNORMAL)
        if not is_reachable(layer, state)
    ]
    assert false_cells == [("green", "abnormal")]
    assert is_reachable(Layer.GREEN, BodyCompState.NORMAL) is True
    assert is_reachable(Layer.RED, BodyCompState.ABNORMAL) is True


def test_a_pending_template_is_constructible_so_task_4_has_something_to_reject():
    """P3-A8 划归 Task 3 的那一半：证明「构造一个 ``review_status=PENDING`` 的
    :class:`Template` 是**可能的**」，于是 Task 4 的匹配器有东西可拒。

    **为什么这件事需要一条测试**：spec §7.2 ``:451`` 逐字是「**``review.status !=
    approved`` 的模板拒绝用于生成**」。若 ``Template`` 在构造期就把 ``pending`` 挡掉
    （例如 ``__post_init__`` 里 ``raise``），那条 spec 要求就**永远不可能被实现**——
    一个 ``pending`` 模板根本到不了匹配器手里，而「拒绝」与「不存在」在日志上是两回事：
    前者要能告诉教师「这一套还没审校」，后者只会是一个查不到的键。故 ``review_status``
    是**数据**、不是构造期校验；挡它的是 Task 4 的匹配器。

    ``frozen=True`` 的那一支顺带钉住 Task 8 的前提：spec §7.5 ``:519``「覆盖**不修改
    模板**，只在 ``prescription`` 上叠加 override 记录」——模板可就地改写的话，
    一次教师覆盖会污染全进程共享的那个单例。
    """
    pending = _template(review_status=ReviewStatus.PENDING, reviewer=None, reviewed_at=None)
    assert pending.review_status is ReviewStatus.PENDING
    assert pending.review_status == "pending"          # str 子类：可直接与落库值比
    assert pending.review_status is not ReviewStatus.APPROVED
    assert ReviewStatus("pending") is ReviewStatus.PENDING
    assert pending.reviewer is None and pending.reviewed_at is None
    # frozen：换掉整个字段被拦。FrozenInstanceError 是 AttributeError 的子类，
    # 故这里断言父类即可，不必为它多 import 一个模块。
    with pytest.raises(AttributeError):
        pending.review_status = ReviewStatus.APPROVED  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 18 套模板的内容（实际侧一律来自磁盘上的 YAML）
# ---------------------------------------------------------------------------


def test_exactly_eighteen_templates_cover_the_full_matrix():
    """键集**字面写死** 18 个 id，且「层 × 短板 × 体成分」恰为 3×3×2 的全笛卡尔积。

    出处：spec §7.1 ``:443``「``层(3) × 主导短板(3) × 体成分(2) = 18``，与指导文件
    「按层×短板×体成分预制 18 套」字面一致」。

    **无重复**这一半是承重的：``load_templates`` 返回的是以 ``template_id`` 为键的映射，
    两套模板若填了同一个 ``(层, 短板, 体成分)`` 格，映射里会有两个键、而集合只有 18 个
    元素之一被覆盖——于是「18 套」这个数看着对、实际有一格是空的、另一格有两套，
    Task 4 的匹配器会按字典序命中其中一个，**换一次目录遍历序就可能换一个结果**。
    故这里同时钉「键数 == 18」与「格子集合 == 18 个格」。
    """
    loaded = rp.templates()
    assert len(TEMPLATE_IDS) == 18
    assert len(set(TEMPLATE_IDS)) == 18, "字面清单里有重复的 id"
    assert set(loaded) == set(TEMPLATE_IDS), (
        f"少了 {sorted(set(TEMPLATE_IDS) - set(loaded))}，"
        f"多了 {sorted(set(loaded) - set(TEMPLATE_IDS))}"
    )

    expected_cells = {
        (layer, bucket, state)
        for layer in ("red", "yellow", "green")
        for bucket in ("endurance", "strength", "speed_flexibility")
        for state in ("normal", "abnormal")
    }
    assert len(expected_cells) == 18, "spec §7.1 :443 的 3×3×2 不是 18 了"
    actual_cells = {
        (t.layer.value, t.weakness.value, t.body_comp.value) for t in loaded.values()
    }
    assert actual_cells == expected_cells, (
        f"矩阵有洞或有重：缺 {sorted(expected_cells - actual_cells)}、"
        f"多出 {sorted(actual_cells - expected_cells)}"
    )
    assert len(actual_cells) == len(loaded), "两套模板占了同一格（见本条 docstring）"


def test_three_green_abnormal_templates_are_marked_unreachable():
    """spec §7.1 ``:447``：这 3 套「保留为**预留位**、标记 ``reachable: false``、不参与匹配」。

    **它们仍然要有完整的 ``sessions``**——这是本 Task 的一个自主决定，理由三条：
    ① spec ``:447`` 的②逐字是「分层规则未来若调整（例如允许『8 项达标但体成分异常』者
    留在绿色层做体成分专项干预），**模板位已就绪**」，「就绪」意味着内容齐全，空壳不是就绪；
    ② ``:447`` 的①是「维持指导文件『18 套』的字面完整性，**专家评审时无需解释为何只有
    15 套**」，专家要能审的是一套真模板；③ 若它们是空壳，加载器就必须为「预留位」开一条
    豁免分支，于是 18 套里有 3 套走的是另一条校验路径——**那条路径永远不被真数据走过**，
    正是 Review Focus 第 1 条要消灭的静默失效。故本 Task 让它们与其余 15 套**同形**，
    只有 ``reachable`` 一个字段不同。
    """
    loaded = rp.templates()
    assert len(UNREACHABLE_IDS) == 3
    for template_id in UNREACHABLE_IDS:
        template = loaded[template_id]
        assert template.reachable is False, template_id
        assert template.layer is Layer.GREEN, template_id
        assert template.body_comp is BodyCompState.ABNORMAL, template_id
        assert is_reachable(template.layer, template.body_comp) is False
        # 「预留位」不等于「空壳」：结构与其余 15 套同形（见本条 docstring 的①②③）
        assert len(template.sessions) == GUIDANCE_WEEKLY_FREQUENCY["green"], template_id
        assert all(session.blocks for session in template.sessions), template_id


def test_the_other_fifteen_are_reachable():
    """其余 15 套全部 ``reachable: true``（与上一条互补，两条一起穷尽 18 套）。"""
    loaded = rp.templates()
    reachable = {template_id for template_id, t in loaded.items() if t.reachable}
    assert reachable == set(TEMPLATE_IDS) - set(UNREACHABLE_IDS)
    assert len(reachable) == 15
    for template_id in sorted(reachable):
        template = loaded[template_id]
        assert is_reachable(template.layer, template.body_comp) is True, template_id


def test_weekly_frequency_follows_the_guidance_document():
    """逐套核对 ``weekly_frequency`` == spec §7.2 ``:465`` 的「红 4 / 黄 3 / 绿 2（指导文件原文）」。

    同时钉住 :data:`GUIDANCE_WEEKLY_FREQUENCY` 自己（支 1），否则「改了这一份字面量、
    再让 18 套模板跟着改」会让支 2 恒真——两侧就同源了（硬规矩 #35）。

    ⚠️ **本条是 Step 7 变异 ④ 的目标判据**：把某套红层的 ``weekly_frequency`` 改成 3，
    红的应当是本条支 2。但**只改那一个字段**会先撞上加载器的结构校验
    （``len(sessions) == weekly_frequency``，4 != 3），于是在 ``load_templates`` 就抛了、
    所有消费 ``rp.templates()`` 的测试一起报错——那不是本条在开火。要单独验本条，
    必须连第 4 天的 ``session`` 一起删掉（报告里两种都跑了）。
    """
    assert GUIDANCE_WEEKLY_FREQUENCY == {"red": 4, "yellow": 3, "green": 2}
    for template_id, template in sorted(rp.templates().items()):
        expected = GUIDANCE_WEEKLY_FREQUENCY[template.layer.value]
        assert template.weekly_frequency == expected, (
            f"{template_id} 是 {template.layer.value} 层，指导文件给的是每周 {expected} 天，"
            f"YAML 里写的是 {template.weekly_frequency}"
        )
        assert len(template.sessions) == template.weekly_frequency, template_id


def test_week_deltas_length_equals_microcycle_weeks():
    """``week_deltas`` 的长度 == ``microcycle_weeks``，且形状是「前三周递增、第 4 周减量」。

    出处：spec §7.2 ``:464`` 的 ``microcycle_weeks: 4``、``:478-479`` 的
    ``progression.week_deltas: [1.00, 1.05, 1.10, 0.85]``（行内注释逐字：
    「第 4 周减量，超量恢复」）。

    **长度不等是静默失效**：Task 6 的装配按周取系数（spec §7.3 ``:498``「4 周递进：套用
    ``progression.week_deltas``」），3 项配 4 周会让第 4 周取不到值——取 ``deltas[week-1]``
    是 ``IndexError``（响亮），而取 ``deltas[min(week, len) - 1]`` 或 ``itertools.cycle``
    一类「容错」写法就是**第 4 周悄悄回到第 3 周的量**，恰好在最该减量的那一周加量。
    故这条在加载器里也校验一次（:func:`test_loader_rejects_a_broken_template` 的用例 ②），
    两边都守：加载器守「专家改坏一份」，本条守「18 份里有一份与其余不同形」。
    """
    for template_id, template in sorted(rp.templates().items()):
        assert template.microcycle_weeks == MICROCYCLE_WEEKS, template_id
        assert len(template.week_deltas) == template.microcycle_weeks, (
            f"{template_id}: week_deltas 有 {len(template.week_deltas)} 项，"
            f"而 microcycle_weeks 是 {template.microcycle_weeks}"
        )
        assert template.week_deltas == WEEK_DELTAS, template_id
        assert template.week_deltas[-1] < 1.0, f"{template_id} 的第 4 周不是减量周"
        assert all(delta >= 1.0 for delta in template.week_deltas[:-1]), template_id


def test_sessions_total_is_fifty_four():
    """18 套的 ``sessions`` 总数 == **54**（P3-C2 建议的那条强不变量）。

    口径：每套的天数 = 该层的 ``weekly_frequency``（红 4 / 黄 3 / 绿 2，spec §7.2 ``:465``），
    每层有 3 桶 × 2 体成分 = 6 套，故 ``6×4 + 6×3 + 6×2 = 24 + 18 + 12 = 54``。
    实现者复核过控制者给的这个数（派单 §2 要求）：与逐套实数相加一致，见下面按层的分解断言。

    **它的价值是一次性验掉「18 套都写全了」**：``test_exactly_eighteen_templates_cover_the_full_matrix``
    只数键，一套模板若少写一天，那条仍然绿。⚠️ 3 套不可达的预留位**计入**这个 54
    （它们有完整的 2 天，理由见
    :func:`test_three_green_abnormal_templates_are_marked_unreachable`）——若哪天裁定
    它们是空壳，这个数会变成 48，本条会红，那是**期望**的红。
    """
    loaded = rp.templates()
    per_layer: dict[str, int] = {}
    for template in loaded.values():
        per_layer[template.layer.value] = (
            per_layer.get(template.layer.value, 0) + len(template.sessions)
        )
    assert per_layer == {"red": 24, "yellow": 18, "green": 12}
    assert sum(len(t.sessions) for t in loaded.values()) == 54


def test_sessions_are_numbered_from_one_and_carry_at_least_one_block():
    """``day`` 从 1 连续递增、``focus`` 非空、每课至少 1 个 block、``structure`` 只读。

    ``day`` 从 1 递增出自简报 Step 2-5（「``day`` 从 1 递增」）与 spec §7.2 骨架 ``:467``
    的 ``- day: 1``。「至少 1 个 block」出自简报同一节。

    **``day`` 的连续性是承重的**：Task 11 的「本周训练单」要按周次取课（spec §8.4），
    而打卡完成率按处方训练日计（spec §14 第 9 项）——``day`` 若跳号（1, 2, 4），
    「第 3 天该打卡吗」就没有答案，且这种坏数据在 YAML 里一眼看不出来。

    ``structure`` 断言成 ``mappingproxy``：``Block`` 是 ``frozen=True``，但 frozen 只挡
    「换掉整个字段」、挡不住 ``block.structure["sets"] = 99`` 的就地改写，而
    :func:`app.refdata_prescription.templates` 是**进程内共享单例**——一次误写会让之后
    所有装配静默变质。与 ``load_exercises()`` 返回 ``MappingProxyType`` 同一处置。
    """
    for template_id, template in sorted(rp.templates().items()):
        assert [session.day for session in template.sessions] == list(
            range(1, len(template.sessions) + 1)
        ), f"{template_id} 的 day 不是从 1 连续递增"
        for session in template.sessions:
            assert session.focus.strip(), f"{template_id} 第 {session.day} 天的 focus 是空的"
            assert len(session.blocks) >= 1, (
                f"{template_id} 第 {session.day} 天没有任何 block"
            )
            for block in session.blocks:
                assert type(block.structure).__name__ == "mappingproxy", (
                    f"{template_id} 的 structure 是可就地改写的 {type(block.structure).__name__}"
                )
                with pytest.raises(TypeError):
                    block.structure["sets"] = 99  # type: ignore[index]


def test_addons_follow_the_guidance_document():
    """逐套核对 ``addons``：红层两条、黄层两条（体脂那条换成 5min HIIT）、**绿层空**。

    出处：spec §7.2 骨架 ``:480-484``（红层的两条，含行内注释「红层 +10% 能量消耗」）与
    散文 ``:487``（「黄层…**体脂偏高附加 5min HIIT**」）。``muscle_low →
    resistance_priority`` 黄层照抄红层，依据是骨架 ``:483-484`` 没给层限定 +
    spec §7.4 ``:509``「肌肉量 < 同龄同性别 P10 → 同上，并提高抗阻模块比重」也与层无关。

    ⚠️ **绿层的 ``addons`` 是空的，这是一个空洞而不是一个事实**（简报 Step 2-5 裁定：
    「绿层的 addon 指导文件没提 → 绿层模板 ``addons: []``，并在 YAML 注释里写明」）。
    后果要写明（硬规矩 #39）：spec §7.4 ``:510`` 的第三个触发（体脂率异常）对**绿层**学生
    将**无模块可追加**，即那一条安全规则在绿层命中时会静默无事发生。今天这条路不可达
    （绿层必然 ``NOT C``，见 :func:`test_three_green_abnormal_templates_are_marked_unreachable`），
    但 spec §7.4 是按「触发条件」写的、没有层限定，故**分层规则一旦调整它就会变成真漏洞**。
    已作为关切报给控制者（本 Task 只被授权追加 spec §14 的 #29 与 #31，故未自行登记）。

    **addon 与 ``body_comp`` 维度无关**：18 套里同层的 6 套 ``addons`` 完全相同，包括
    ``*-NOR-*`` 那 9 套。理由：addon 是**运行期条件式**的（spec §7.4 的三个触发按学生当下的
    体测值判定），声明它不等于它会触发；而模板的 ``body_comp`` 维度是**分层时点**的粗档。
    把两者绑起来会让一个「分层时体成分正常、期中体脂超标」的学生拿不到能量消耗模块。
    """
    assert GUIDANCE_ADDONS["red"][0] == ("body_fat_over", "energy_expenditure_plus_10pct")
    assert GUIDANCE_ADDONS["yellow"][0] == ("body_fat_over", "energy_expenditure_plus_5min_hiit")
    assert GUIDANCE_ADDONS["green"] == ()
    for template_id, template in sorted(rp.templates().items()):
        actual = tuple((addon.when, addon.module) for addon in template.addons)
        assert actual == GUIDANCE_ADDONS[template.layer.value], (
            f"{template_id}（{template.layer.value} 层）的 addons 是 {actual}，"
            f"指导文件给的是 {GUIDANCE_ADDONS[template.layer.value]}"
        )


def test_every_template_id_matches_its_filename():
    """文件名（去 ``.yaml``）== ``template_id``，且目录里**恰好** 18 个 ``.yaml``。

    这条约定的价值：Review Focus 第 1 条要求报错点名「哪个文件」，而专家审校时手里拿到的
    也是文件名——两者与 ``template_id`` 同名，「文件 ↔ 模板」就不需要第二张对照表
    （多一张表就是多一个所有者，Global Constraint #3）。加载器也校验它，故本条今天
    不可能单独变红；它守的是「加载器那道校验被删掉之后，改名仍然会被抓住」。

    ⚠️ **``len(...) == 18`` 那一支不是装饰**：``load_templates`` 返回以 id 为键的映射，
    目录里多躺一个 ``RED-END-ABN-01 (副本).yaml`` 会让映射里多一个键（若它的 id 不同）
    或直接抛「id 重复」（若相同）——前者会让
    :func:`test_exactly_eighteen_templates_cover_the_full_matrix` 的键集断言红，
    但那条的报错不会说「目录里有个副本文件」，本条会。
    """
    directory = rp.DATA_DIR / rp.PRESCRIPTION_DIRNAME
    on_disk = sorted(path.stem for path in directory.glob("*.yaml"))
    assert len(on_disk) == 18, f"目录里有 {len(on_disk)} 个 .yaml：{on_disk}"
    assert on_disk == sorted(TEMPLATE_IDS)


def test_all_eighteen_share_the_same_review_and_version_block():
    """18 套的审校块与版本号逐字相同（用户已裁定的原型阶段占位）。

    ``reviewed_at`` 是**固定**的 ISO 日期字面量而不是 ``date.today()``：后者会让每次重新
    生成 YAML 都改一个字节、指纹测试天天红（简报「决定」段）。它落库时由
    :func:`app.refdata_prescription.sync_templates` 转成 ``datetime.date``——**domain 侧
    刻意存字符串**，因为 :mod:`tests.architecture.test_domain_purity` 的 allow-list 不放行
    ``datetime``（实测 :data:`ALLOWED_MODULES` 只有 ``dataclasses`` / ``enum`` /
    ``collections`` / ``collections.abc`` / ``numpy`` / ``typing`` 六个串 + ``app.domain``
    前缀），而 Global Constraint #1 不许为了一个日期字段去放宽那道守卫。

    ⚠️ 这 18 个 ``approved`` **不是**审校结果：spec §14 第 **29** 项已登记「须由邹红老师
    实际审校后替换」（P3-A3：编号由计划 ``d40f36c`` 预分配，本 Task 直接写入）。
    """
    for template_id, template in sorted(rp.templates().items()):
        assert template.version == TEMPLATE_VERSION, template_id
        assert template.review_status is ReviewStatus.APPROVED, template_id
        assert template.reviewer == REVIEWER, template_id
        assert template.reviewed_at == REVIEWED_AT, template_id
        assert isinstance(template.reviewed_at, str), (
            f"{template_id}: domain 侧的 reviewed_at 必须是 str（见本条 docstring 的 "
            "allow-list 理由），实为 {type(template.reviewed_at).__name__}"
        )


# ---------------------------------------------------------------------------
# 跨文件不变量（模板 YAML ↔ exercises.yaml）
# ---------------------------------------------------------------------------


def test_every_exercise_ref_exists_in_the_exercise_library():
    """Review Focus 第 1 条点名的第 3 种坏形状：``exercise_ref`` 指向不存在的动作。

    **不校验的后果是装配到某个学生时才炸**：Task 6 的装配第 5 步要从 ``exercise`` 表取
    视频 URL（spec §7.3 ``:499``），一个查不到的 ref 在那里是一次 ``KeyError``，
    报错点在管道深处、离真因（某个 YAML 里的一个拼写）隔三层。故加载器**也**校验它
    （:func:`test_loader_rejects_a_broken_template` 的用例 ③），本条守的是「那道校验
    被删掉之后漂移仍然会被抓住」，并给出一次列出全部悬空引用的可读诊断。

    两侧不同源（硬规矩 #35）：实际侧来自 ``data/prescription/*.yaml``，期望侧来自
    ``data/exercises.yaml``——两份文件、两个所有者。
    """
    library = rp.exercises()
    dangling = [
        (template_id, session.day, block.exercise_ref)
        for template_id, template in sorted(rp.templates().items())
        for session in template.sessions
        for block in session.blocks
        if block.exercise_ref not in library
    ]
    assert dangling == [], f"这些 exercise_ref 在动作库里不存在：{dangling}"


def test_every_block_impact_level_matches_the_exercise_library():
    """模板 block 里那份 ``impact_level`` 必须与动作库**逐字相同**（P2-B2 的漂移守卫）。

    **谁是所有者**：``exercises.yaml``（Plan02 账本 P2-B2）。spec §7.2 骨架 ``:471`` 的
    行内注释逐字是「``impact_level: high`` # 供安全后置处理识别」，即模板字面形状里
    **确实**自带一份——那是**副本**。故本 Task 的处置是「照 spec 的字面形状写、由加载器
    校验一致」（简报 Step 1 明确要求「若你判断应该只保留一个所有者（模板不写、从动作库取），
    **报为关切并说明**，不要擅自改 spec §7.2 的骨架」）。

    ⚠️ **我的判断与那个替代方案**（报为关切）：只保留一个所有者（模板不写、加载器从动作库
    填）在工程上更干净，但它会让 spec §7.2 的骨架失真，而且**专家审校模板时看不到冲击等级**
    ——而冲击等级正是「这一套对 BMI > 30 的学生安不安全」的唯一线索，把它从专家眼前拿走
    是拿审校质量换一致性。**故照骨架写副本 + 双处校验**，代价是这一条守卫必须永远在。

    **漂移的后果是静默的**：一个 block 把 ``high`` 写成 ``medium``，spec §7.4 ``:508`` 的
    安全后置就**不会**去等价表里找替身，BMI > 30 的学生照旧被安排高冲击动作，而全链路
    没有一处报错——正是 Review Focus 第 5 条要防的形态的上游。

    ⚠️ 加载器**也**做这道校验（用例 ⑨），故本条今天在真数据上不可能单独变红：
    ``load_templates`` 会先抛。它守的是「加载器那道校验被削弱/删掉之后漂移仍然会被抓住」。
    """
    library = rp.exercises()
    drifted = [
        (template_id, session.day, block.exercise_ref, block.impact_level.value,
         library[block.exercise_ref].impact_level.value)
        for template_id, template in sorted(rp.templates().items())
        for session in template.sessions
        for block in session.blocks
        if block.exercise_ref in library
        and block.impact_level is not library[block.exercise_ref].impact_level
    ]
    assert drifted == [], (
        "这些 block 的 impact_level 与动作库不符（模板 id, day, ref, 模板写的, 动作库的）："
        f"{drifted}"
    )


def test_every_addon_module_exists_in_the_exercise_library():
    """addon 的 ``module`` 也是 ``exercise_ref``，同样必须在动作库里。

    ``energy_expenditure_plus_10pct`` 与 ``resistance_priority`` 是 spec §7.2 ``:482-484``
    骨架里逐字写着的模块名，``exercises.yaml`` 的头注释明写它「照那个名字命名，避免出现
    『模块名』与『动作 ref』两个所有者」；``energy_expenditure_plus_5min_hiit`` 是本 Task
    按 P3-A4 追加的第 24 个 ref（理由见 ``exercises.yaml`` 里它自己那节的注释）。

    **为什么要单列一条**：上面那条只遍历 ``sessions`` 里的 block，**看不见 addons**——
    而 spec §7.4 ``:510`` 的第三个触发恰恰走 addons 这一路（不查等价表），一个悬空的
    module 会让「体脂率异常 → 追加能量消耗模块」变成一次 ``KeyError``。
    """
    library = rp.exercises()
    dangling = [
        (template_id, addon.when, addon.module)
        for template_id, template in sorted(rp.templates().items())
        for addon in template.addons
        if addon.module not in library
    ]
    assert dangling == [], f"这些 addon module 在动作库里不存在：{dangling}"
    # 反向的空转守卫：addons 不是恰好全空（否则上面那条是空跑而恒绿）
    assert sum(len(t.addons) for t in rp.templates().values()) == 24, (
        "口径：红 6 套 ×2 + 黄 6 套 ×2 + 绿 6 套 ×0 = 24"
    )


# ---------------------------------------------------------------------------
# 闸：指纹（P3-D2 的行尾纪律也在这里收口）
# ---------------------------------------------------------------------------


def test_template_yaml_fingerprints_are_pinned():
    """**改任何一套模板必须先改这条测试**——「知识资产变更需被显式承认」的闸门。

    与 :func:`tests.test_refdata_prescription.test_exercises_yaml_fingerprint_is_pinned`
    同口径、同理由（Ruling 213 的教训）：改一个训练量数字、换一个动作 ref、把某天的
    ``focus`` 改一个字，**都不破坏上面任何一条形状不变量**，只有指纹能挡住它。
    ``D3``（Plan02 账本）：18 个文件一旦被指纹钉住，Task 4-12 都不许再改它们，改了要
    同步本常量。

    ⚠️ **归一化为 LF 之后**再哈希，理由与 Task 2 完全相同（``core.autocrlf`` 在 Git for
    Windows 上缺省为 ``true``，裸字节哈希会随平台配置漂移、新克隆必红）。而
    ``.gitattributes`` 那条 ``backend/data/**/*.yaml text eol=lf`` 是**第一道**保险
    （P3-D2 新加，``backend/data/*.yaml`` 的 ``*`` 不跨 ``/``、盖不住子目录），
    归一化是第二道。下一条例行检查第一道是否真的生效。
    """
    directory = rp.DATA_DIR / rp.PRESCRIPTION_DIRNAME
    assert len(TEMPLATE_FINGERPRINTS) == 18
    assert set(TEMPLATE_FINGERPRINTS) == set(TEMPLATE_IDS)
    for template_id, pinned in sorted(TEMPLATE_FINGERPRINTS.items()):
        path = directory / f"{template_id}.yaml"
        digest = _fingerprint(path)
        assert digest == pinned, (
            f"模板 {template_id} 被改动了：{path.name} 的 sha256 前 16 位是 {digest}，"
            f"钉住的是 {pinned}。这 18 份是专家维护的知识资产，改动必须被显式承认——"
            f"确认改动有意之后更新 TEMPLATE_FINGERPRINTS 里那一行"
        )


def test_every_template_yaml_is_lf_only_in_the_worktree():
    """P3-D2 的收口：18 个模板 YAML 在**工作树里**是纯 LF（0 个 CRLF）。

    **这条守的是 ``.gitattributes`` 那条规则真的生效了**，而它守不住指纹：指纹测试先
    ``replace(b"\\r\\n", b"\\n")``，故工作树全变 CRLF 它**照样绿**。失效形态就是 Plan 01
    的国标评分表事故（硬规矩 #46/#47）：``core.autocrlf=true`` 下一次 ``git checkout``
    把 LF 重写成 CRLF，21412 字节变 21915 字节，而所有「按字节数取证」的散文当场变假。

    ⚠️ **规则文件的覆盖面必须对具体路径亲验**（硬规矩 #61 的扩写）：
    ``.gitattributes`` 里原有的 ``backend/data/*.yaml`` 的 ``*`` **不跨 ``/``**，
    ``git check-attr text eol -- backend/data/prescription/RED-END-ABN-01.yaml`` 在加规则
    之前返回 ``text: unspecified / eol: unspecified``。取证命令与改前改后的输出都在报告里。

    ⚠️ **本条只看工作树字节、不看 index**：一个文件可以在 index 里是 LF、在工作树里是
    CRLF（那正是 ``autocrlf`` 的效果）。要同时看两侧请用
    ``git ls-files --eol -- backend/data/``（每行都应是 ``i/lf w/lf attr/text eol=lf``）。
    """
    directory = rp.DATA_DIR / rp.PRESCRIPTION_DIRNAME
    offenders = []
    for template_id in TEMPLATE_IDS:
        raw = (directory / f"{template_id}.yaml").read_bytes()
        crlf = raw.count(b"\r\n")
        if crlf:
            offenders.append((template_id, crlf, len(raw)))
    assert offenders == [], (
        "这些模板 YAML 在工作树里含 CRLF（.gitattributes 的 "
        "`backend/data/**/*.yaml text eol=lf` 没生效？）：(id, CRLF 数, 字节数) = "
        f"{offenders}"
    )


# ---------------------------------------------------------------------------
# 列宽（P3-A5：没有 CHECK 约束的 String(n) 列不被 test_models.py 那道遍历测试覆盖）
# ---------------------------------------------------------------------------


def test_template_string_column_widths_fit_the_yaml_values():
    """``template_ref`` / ``version`` / ``reviewer`` 三列的宽度容得下 18 套 YAML 的实际值。

    ⚠️ **为什么这三列要在这里另写一条**（P3-A5，与 Task 2 的 P2-A5 同型）：
    ``tests/db/test_models.py`` 的 ``_in_domain_columns()`` 是自描述的（遍历
    ``Base.metadata``、用正则从 ``_in_domain`` 生成的 ``column IN (...)`` CHECK 文本反解），
    故它**只看得见带 ``_in_domain`` CHECK 的列**。``prescription_template`` 的 6 个
    ``String(n)`` 列里，``layer`` / ``weakness`` / ``body_comp`` / ``review_status`` 有 CHECK
    （自动被覆盖），而这**三列的取值域不是封闭集合、没有 CHECK → 完全不被覆盖**。

    **失效形态**（硬规矩 #18）：SQLite **不强制** ``VARCHAR`` 长度，故溢出在本仓的测试里
    永远不报错；换 MySQL / PostgreSQL 才截断，且**炸在读侧不在写侧**——``template_ref``
    被截断后 ``load_templates`` 的键与 DB 行对不上，Task 9 写 ``prescription.template_id``
    时外键查不到，离真因隔一整个批处理周期。

    **两支不同源**：宽度来自 ORM 声明，实际值来自磁盘上的 YAML。第三支把实测最长值
    **字面**钉住，否则「列宽与实际值一起缩水」时前两支同步变化、断言恒真。
    ``template_ref`` 的 14 字符出自 spec §7.2 ``:454`` 的 id 格式
    （``<层3>-<桶3>-<体成分3>-<序号2>``）；``version`` 的 3 是 ``"1.0"``；``reviewer`` 的
    8 是 ``"原型自审（占位）"``（8 个字符，含两个全角括号）。

    ⚠️ **两个零余量的列不在本条里**（它们有 CHECK，故由 ``test_models.py`` 那道遍历测试
    看着）：``body_comp String(8)`` 装 ``"abnormal"``（8）、``review_status String(8)`` 装
    ``"approved"``（8），**都是恰好塞满、零余量**——将来往词表里加一个更长的值，
    宽松后端静默截断。已在 ORM 的列注释里点明。
    """
    loaded = rp.templates()
    table = PrescriptionTemplate.__table__
    longest = {
        "template_ref": max(len(t.template_id) for t in loaded.values()),
        "version": max(len(t.version) for t in loaded.values()),
        "reviewer": max(len(t.reviewer) for t in loaded.values() if t.reviewer),
    }
    for column, length in sorted(longest.items()):
        declared = table.c[column].type.length
        assert declared >= length, (
            f"prescription_template.{column} 声明 String({declared})，"
            f"而 18 套 YAML 里最长值是 {length} 字符——严格长度的后端会静默截断"
        )
    assert longest == {"template_ref": 14, "version": 3, "reviewer": 8}


# ---------------------------------------------------------------------------
# 加载器的响亮失败（Review Focus 第 1 条：加载时炸、点名文件与行号）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutate, needle",
    [
        # ① 简报 :281 的第 1 种：缺 template_id
        (lambda d: d.pop("template_id"), "template_id"),
        # ② 第 2 种：week_deltas 长度与 microcycle_weeks 不符（4 → 3）
        (lambda d: d["progression"].update(week_deltas=[1.0, 1.05, 0.85]), "week_deltas"),
        # ③ 第 3 种：exercise_ref 指向不存在的动作
        (lambda d: d["sessions"][0]["blocks"][0].update(exercise_ref="no_such_move"),
         "exercise_ref"),
        # ④ 第 4 种：layer 是 insufficient_data（它不是合法模板层，见 TEMPLATE_LAYERS）
        (lambda d: d.update(layer="insufficient_data"), "layer"),
        # ⑤ 第 5 种：weekly_frequency 与层不符（红层应是 4）。
        #    ⚠️ 这一格同时会撞上「len(sessions) == weekly_frequency」那道结构校验，
        #    两者都是响亮的 ValueError；needle 取 weekly_frequency，两道校验的报错都含它。
        (lambda d: d.update(weekly_frequency=3), "weekly_frequency"),
        # ⑥ 第 6 种：review.status 是词表外的第三种值
        (lambda d: d["review"].update(status="rejected"), "review.status"),
        # ⑦ P3-C3 新加的第 7 种：嵌套块 review: 整个缺失（Template 把它摊平成
        #    review_status / reviewer / reviewed_at，故缺块必须被点名，不能变成 KeyError）
        (lambda d: d.pop("review"), "review"),
        # ⑧ P3-C3 的另一半：嵌套块 progression: 整个缺失（week_deltas 住在它里面）
        (lambda d: d.pop("progression"), "progression"),
        # ⑨ P2-B2 的漂移：block 的 impact_level 与动作库不符（interval_run 是 high）
        (lambda d: d["sessions"][0]["blocks"][0].update(impact_level="low"), "impact_level"),
        # ⑩ Review Focus 第 1 条点名的最后一种：reachable 与维度组合矛盾。
        #    (red, *, abnormal) 按 is_reachable 是**可达**的，写 false 就是矛盾。
        (lambda d: d.update(reachable=False), "reachable"),
    ],
)
def test_loader_rejects_a_broken_template(tmp_path, mutate, needle):
    """10 种坏形状必须在**加载时**响亮失败，并点名是**哪个文件、哪一行**。

    前 6 种是简报 ``:281`` 列的，⑦⑧ 是 P3-C3 补的两种「嵌套块缺失」（spec §7.2 骨架的
    ``review:``（``:460-463``）与 ``progression:``（``:478-479``）是嵌套块，而 ``Template``
    把它们**摊平**成 ``review_status`` / ``reviewer`` / ``reviewed_at`` / ``week_deltas``，
    故缺块在朴素实现下是一个 ``KeyError: 'review'``——它点不出文件、也说不出是哪个键的
    哪一层），⑨⑩ 分别来自 P2-B2 与 Review Focus 第 1 条。

    **「哪一行」是怎么做到的**（硬规矩 #39：写下守卫能力就要写清它守不住什么）：
    ``yaml.safe_load`` **不保留位置信息**，故加载器另跑一次 ``yaml.compose`` 建一张
    「键路径 → 1 基行号」的索引（:func:`app.refdata_prescription._line_index`）。
    ⚠️ **缺失的键没有自己的位置**，那一档指向的是**它所在的块**的首行（例如缺
    ``review.status`` 时报 ``review:`` 那一行）；索引建不出来（YAML 语法错）时退化成
    PyYAML 自己的 mark，见 :func:`test_loader_reports_the_file_when_a_template_is_not_valid_yaml`。
    故 ``assert "第 " in message`` 守的是「有行号」，不守「行号一定精确到那个键」。

    ⚠️ **本条与 :func:`test_a_wellformed_synthetic_template_round_trips` 是一对**
    （硬规矩 #53）：少了那条已知 GREEN 的对照，「把校验改成一律 raise」能让本条 10 格全绿。
    """
    doc = _good_template_doc()
    mutate(doc)
    path = _write_template(tmp_path, doc)
    with pytest.raises(ValueError) as excinfo:
        rp.load_templates(tmp_path)
    message = str(excinfo.value)
    assert needle in message, message
    assert path.name in message, f"报错没点名文件：{message}"
    assert "第 " in message, f"报错没点名行号（Review Focus 第 1 条）：{message}"


def test_a_wellformed_synthetic_template_round_trips(tmp_path):
    """**已知 GREEN 的干净对照**（硬规矩 #53）：加载器吃得下一份合法的模板 YAML。

    没有这一条，上面 10 格拒绝用例可以靠「一律 raise」全部变绿。它同时把 ``Template``
    的**摊平**结果逐字段钉住：``review`` 嵌套块 → ``review_status`` / ``reviewer`` /
    ``reviewed_at`` 三个字段，``progression`` 嵌套块 → ``week_deltas``（P3-C3）。
    """
    _write_template(tmp_path, _good_template_doc())
    loaded = rp.load_templates(tmp_path)
    assert list(loaded) == ["RED-END-ABN-01"]
    template = loaded["RED-END-ABN-01"]
    assert isinstance(template, Template)
    assert template.version == "9.9"
    assert template.layer is Layer.RED
    assert template.weakness is WeaknessBucket.ENDURANCE
    assert template.body_comp is BodyCompState.ABNORMAL
    assert template.reachable is True
    # review: 嵌套块被摊平成三个字段
    assert template.review_status is ReviewStatus.APPROVED
    assert template.reviewer == "合成用例"
    assert template.reviewed_at == "2026-10-06"
    assert template.microcycle_weeks == 4
    assert template.weekly_frequency == 4
    # progression: 嵌套块被摊平成 week_deltas，且 int 被收敛成 float
    assert template.week_deltas == (1.0, 1.05, 1.1, 0.85)
    assert all(isinstance(delta, float) for delta in template.week_deltas)
    assert [session.day for session in template.sessions] == [1, 2, 3, 4]
    assert all(session.focus == "耐力" for session in template.sessions)
    block = template.sessions[0].blocks[0]
    assert block.exercise_ref == "interval_run"
    assert block.impact_level is ImpactLevel.HIGH
    assert block.intensity.type == "hrmax_pct"
    assert (block.intensity.low, block.intensity.high, block.intensity.value) == (60.0, 70.0, None)
    assert dict(block.structure) == {"sets": 4, "work_min": 3, "rest_min": 2}
    assert tuple((a.when, a.module) for a in template.addons) == (
        ("body_fat_over", "energy_expenditure_plus_10pct"),
    )


def test_loader_preserves_a_pending_review_status_verbatim(tmp_path):
    """**Step 7 变异 ① 的改写版**（P3-A7）：加载器如实保留 ``pending``，不静默当成 ``approved``。

    ⚠️ **原文那条变异在本 Task 内没有可观测后果**：它写的是「把某套模板的
    ``review.status`` 改成 ``pending`` → 加载器仍应成功加载、且把它如实读成
    ``ReviewStatus.PENDING``，但 Task 4 的匹配器必须拒绝它（本 Task 先只验加载）」——
    变异前后行为**完全相同**，故它不是一条变异测试（硬规矩 #65：一条变异判据必须指明
    「哪个断言分支」会开火）。P3-A7 把它改成可观测的版本，就是本条：**它是那条变异的
    目标判据**。

    **它钉的失效形态**：一个「顺手规范化」的加载器（``review_status=ReviewStatus(
    raw.get("status", "approved"))``，或把 ``pending`` 映射成 ``approved`` 以便原型跑通）
    会让 spec §7.2 ``:451``「``review.status != approved`` 的模板拒绝用于生成」在 Task 4
    **无从实现**——匹配器拿到的永远是 ``approved``。而 spec §14 第 29 项登记的正是
    「这 18 个 approved 是占位、须由邹红老师实际审校后替换」：替换之后若加载器把
    ``pending`` 吞掉，一套**没审校过**的模板就会被拿去给学生生成处方，全链路无一处报错。

    ⚠️ **用 ``tmp_path`` 下的合成 YAML，不动那 18 个被指纹钉住的文件**（P3-A7 的要求）。
    ``reviewer`` / ``reviewed_at`` 一并置 ``None``（spec §7.2 骨架 ``:462-463`` 的字面形状），
    顺带钉住「未审校的模板这两个字段是 NULL 而不是空串」——ORM 那两列是 nullable 的。
    """
    doc = _good_template_doc()
    doc["review"] = {"status": "pending", "reviewer": None, "reviewed_at": None}
    _write_template(tmp_path, doc)
    template = rp.load_templates(tmp_path)["RED-END-ABN-01"]
    assert template.review_status is ReviewStatus.PENDING
    assert template.review_status == "pending"
    assert template.review_status is not ReviewStatus.APPROVED
    assert template.reviewer is None
    assert template.reviewed_at is None


def test_loader_rejects_a_second_template_reusing_an_id(tmp_path):
    """两个文件写同一个 ``template_id`` 必须响亮失败（不是「后者覆盖前者」）。

    ⚠️ **这是 ``exercises.yaml`` 那个失效形态的模板侧版本**：PyYAML 对重复的**顶层键**是
    后者覆盖前者、不报错（``exercises.yaml`` 头注释实测记着这件事），而模板是**一文件一套**，
    于是同样的失效换了个形状——``load_templates`` 自己建字典，两个文件同 id 就是一次静默覆盖。
    专家最可能这么撞上它：复制一份 ``RED-END-ABN-01.yaml`` 改名成
    ``RED-END-ABN-01-v2.yaml``、**忘了改文件里的 ``template_id``**（文件名与 id 的约定
    由 :func:`test_every_template_id_matches_its_filename` 守，但那条只看真目录）。
    """
    doc = _good_template_doc()
    _write_template(tmp_path, doc)
    second = tmp_path / "RED-END-ABN-01-copy.yaml"
    second.write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
        encoding="utf-8", newline="\n",
    )
    with pytest.raises(ValueError) as excinfo:
        rp.load_templates(tmp_path)
    message = str(excinfo.value)
    assert "RED-END-ABN-01" in message, message
    assert second.name in message, f"报错没点名是哪一个文件重复了：{message}"


def test_loader_reports_the_file_when_a_template_is_not_valid_yaml(tmp_path):
    """YAML 语法错也要点名文件（PyYAML 自己的报错里只有行列、没有文件名）。

    ``yaml.safe_load`` 抛的是 :class:`yaml.YAMLError`，它**不是** ``ValueError`` 的子类，
    且因为加载器喂给它的是字符串而不是文件对象，它的 mark 里**没有文件名**。故加载器
    把它包成 ``ValueError`` 并把文件名与原始 mark 一起带上：调用方只需要认一种异常类型，
    而行列信息不丢。
    """
    path = _write_template(tmp_path, _good_template_doc(), text="template_id: [unclosed\n")
    with pytest.raises(ValueError) as excinfo:
        rp.load_templates(tmp_path)
    message = str(excinfo.value)
    assert path.name in message, message


def test_loader_reports_a_missing_or_empty_template_directory(tmp_path):
    """目录不存在 → ``FileNotFoundError``；目录里一个 ``.yaml`` 都没有 → ``ValueError``。

    **两者刻意用不同的异常类型**：目录不存在是**部署**问题（``data/prescription/`` 没跟着
    代码一起发出去），空目录是**内容**问题（发出去了但被清空）。混成一种会让运维与专家
    互相踢皮球。口径照 :func:`app.refdata_prescription.load_exercises`（文件不存在抛
    ``FileNotFoundError``、文件为空抛 ``ValueError``）。

    ⚠️ 空目录**必须是响亮的**：Task 4 的匹配器拿到一个空映射会对每个学生返回「无模板」，
    于是 500 人一个处方都不生成、而管道全绿——正是 Review Focus 第 3 条要防的
    「静默跳过」的模板侧版本。
    """
    with pytest.raises(FileNotFoundError, match="处方模板"):
        rp.load_templates(tmp_path / "nope")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="处方模板"):
        rp.load_templates(empty)


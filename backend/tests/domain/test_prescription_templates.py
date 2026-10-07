# backend/tests/domain/test_prescription_templates.py
"""``ImpactLevel`` 维度词表的守卫（Plan 02 Task 2；Ruling 96 起所有者在 ``exercises``）。

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
"""
import pytest

from app.domain.prescription import exercises, templates
from app.domain.prescription.templates import ImpactLevel


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
    ``templates.py`` 今天只有 **2** 条语句（``from .exercises import ImpactLevel`` 与
    ``__all__ = ["ImpactLevel"]``；coverage 表上是 ``2 stmts / 0 branch / 100%``），而它
    **唯一的导入方**是本文件顶部的**两句** import：``from app.domain.prescription import
    exercises, templates``（本条守卫用）与 ``from app.domain.prescription.templates import
    ImpactLevel``（下面三条用）。取证命令（``^`` 锚定行首，故 docstring 里的引文不会自己
    命中自己）::

        git grep -n "^from app.domain.prescription.templates import" -- backend

    本轮落盘后**只命中 1 处**，就是本文件顶部那一句 ``…templates import ImpactLevel``；
    另一句 ``from app.domain.prescription import …`` 把模式里的 ``.templates`` 去掉就数得到
    （命中 **2** 处，另一处是 ``tests/test_refdata_prescription.py`` 的
    ``exercises as exercises_mod``、**不含 ``templates``**）。⚠️ **不加 ``^`` 的计数不可用**：
    同一条命令去掉锚，会把 ``templates.py`` 自己 docstring 里的散文与本 docstring 里的
    这段引文一起算进来；把模式再松成 ``prescription.templates`` 更糟——正则里的 ``.``
    连 ``prescription_templates`` 这个**文件名**都匹配，于是它的命中数**每改一次本文件
    的散文就变一次**（本轮写这句话的前后就变过一次），不是一个稳定量，故不写进散文。
    这里只留锚定后的那**一个**数；要复核请自己跑上面那条命令（硬规矩 #19/#66）。

    **静默退化是怎么发生的**（本轮实测复现，报告的变异 M-B4）：下一个人完全可能把这个
    「只有 re-export 的文件」当残留处理掉——最自然的做法不是删文件（那会在**收集期**炸、
    响亮），而是把本文件顶部那两句 ``templates`` 的 import 都改指所有者 ``exercises``
    （一个看起来很合理的「去中间层」清理）。那样 ``templates.py`` 就没有任何导入方了 →
    它那 2 条语句永不执行 → ``--cov=app/domain --cov-branch`` 报 ``templates.py 2 stmts /
    Miss 2 / 0%``（缺的是 ``37-39``）、``TOTAL 441 stmts / Miss 2 / 99%``，**而 ``pytest``
    的退出码仍是 0**（实测 ``529 passed, 1 skipped``）：覆盖率不是断言，只有人去看那张表
    才发现。**本条守卫堵这个口子的方式是它自己也成为一个导入方**——它引用 ``templates``
    这个模块对象，要绕过它就得连它一起删，而删掉它本条会 ``NameError`` 而红（实测
    ``1 failed, 530 passed``、退出码 1）。这就是 Ruling 107-3 说的「同时把 Ruling 103
    那个口子堵上」。

    **两支的主语**（硬规矩 #56）：支 1 钉 ``templates.__all__`` 的**字面内容与长度**；
    支 2 钉 ``templates.ImpactLevel`` 与 ``exercises.ImpactLevel`` 是**同一个对象**
    （``is``，不是 ``==``：``ImpactLevel`` 继承 ``str``，一个本地重定义的同值枚举会让
    ``==`` 成立而 ``is`` 不成立，而那正是「re-export 被换成本地定义」的失效形态）。

    **红/绿双输入**（硬规矩 #50；四个真变异本轮都实跑过，逐支真值见报告 §fr2.4）：
    绿输入 = 今天的真实状态（两支都实跑通过）。红输入：**M-B1**（把 re-export 换成本地
    同值的 ``class ImpactLevel`` → **只有支 2 红**，``1 failed, 530 passed``；``==`` 会
    成立而 ``is`` 不成立，故这一支必须用 ``is``）、**M-B2**（``__all__`` 改成 ``[]`` →
    **只有支 1 红**，``1 failed, 530 passed``。⚠️ 顶部那句 ``from … import ImpactLevel``
    是**显式**导入、不看 ``__all__``，故它不会红——这正是需要支 1 的理由）、**M-B3**
    （整份 ``templates.py`` 删掉 → 本文件在**收集期** ImportError、``pytest`` **退出码 2**，
    根本跑不到覆盖率那一步）、**M-B4**（见上：两处 import 都改指 ``exercises`` → 本条
    ``NameError`` 而红，``1 failed, 530 passed``、退出码 1）。

    **本条守不住什么**（硬规矩 #39）：不守 ``ImpactLevel`` 的**取值**（那是上面三条的事），
    也不守 ``prescription/__init__.py`` 的公开面（那 7 个名字由
    ``tests/test_refdata_prescription.py`` 的
    :func:`tests.test_refdata_prescription.test_prescription_public_namespace_is_pinned_verbatim`
    钉住）。⚠️ Task 3 往 ``templates.py`` 加模板 dataclass 时，**两份 ``__all__`` 要一起改**
    （本模块一份、``prescription/__init__.py`` 一份），届时支 1 的期望值也要跟着加。
    """
    assert templates.__all__ == ["ImpactLevel"]
    assert templates.ImpactLevel is exercises.ImpactLevel

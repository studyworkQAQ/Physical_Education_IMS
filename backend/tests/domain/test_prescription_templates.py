# backend/tests/domain/test_prescription_templates.py
"""``app.domain.prescription.templates`` 的维度词表守卫（Plan 02 Task 2）。

本 Task 只往 ``templates.py`` 放 :class:`~app.domain.prescription.templates.ImpactLevel`
（Plan02 账本 P2-B1 的裁定：File Structure 说这个模块是「模板的数据结构与维度词表；
不读盘」，``ImpactLevel`` 正是维度词表；**模板的数据结构本身归 Task 3**）。故本文件
今天只守这一个枚举，Task 3 往 ``templates.py`` 加东西时再往这里加对应的守卫。

三条断言的**期望侧都是字面量**，不从被测枚举读回来跟自己比（硬规矩 #35）：取值
``high`` / ``medium`` / ``low`` 与成员数 3 都抄自 spec §4.4 ``:239`` 的 ``exercise`` 行
（「**``impact_level``** ∈ {``high``, ``medium``, ``low``}」，行号取 shell 口径、绑定
commit ``fb5bddb``）。

⚠️ **本文件守不住什么**（硬规矩 #39）：

* 它只守 ``ImpactLevel`` 这个**词表本身**。不守「``exercises.yaml`` 里每个动作的
  ``impact_level`` 取值合法」——那一条住在 ``tests/test_refdata_prescription.py``
  的 :func:`tests.test_refdata_prescription.test_every_exercise_has_a_valid_impact_level_and_targets`，
  两侧不同源：那边的实际侧来自 YAML 文件，这边的期望侧来自本枚举。
* 不守冲击等级之间的**序**（``high > medium > low``）：``ImpactLevel`` 继承 ``str``，
  故它的 ``<`` 是**字典序**（``"high" < "low" < "medium"``），与冲击序无关。序关系由
  ``test_equivalence_never_maps_to_a_higher_impact_level`` 字面写死。
* 不守 ``templates.py`` 的**无 I/O**：那是
  :mod:`tests.architecture.test_domain_purity` 的 allow-list 守卫（它扫 ``app/domain``
  全部 ``.py``，建出本子包后扫描面自动扩大，Plan02 账本 P2-D4 亲验不会红）。
"""
import pytest

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

    不继承 ``str`` 的话，ORM 侧就得处处写 ``.value``，而漏写一处的失效形态是**静默的**：
    SQLite 会把枚举对象按 ``str()`` 存成 ``"ImpactLevel.HIGH"``（19 字符，还会撑破
    ``String(8)``——SQLite 不强制长度，故写侧不报错，换严格长度的后端才截断，
    硬规矩 #18 的那个失效形态）。继承 ``str`` 之后 ``ImpactLevel.HIGH == "high"``
    直接成立，落库与读回都是同一个字符串。
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

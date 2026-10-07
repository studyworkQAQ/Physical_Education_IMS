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
import、它那 2 条语句立刻变成 ``Miss 2``。顺带它也守着「re-export 与 ``__all__`` 还在」。
**文件名不改**：计划的 File Structure 把本文件列为 ``templates.py`` 的配对测试，Task 3
会往这里加模板 dataclass 的守卫；改名超出 Ruling 96 的范围，留给 Task 3 一并决定。

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
* 不守 ``templates.py`` / ``exercises.py`` 的**无 I/O**：那是
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

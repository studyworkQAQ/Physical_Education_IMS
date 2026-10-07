# backend/tests/domain/test_prescription_exercises.py
""":mod:`app.domain.prescription.exercises` 的**分支**守卫（Plan 02 Task 4 建）。

**这个文件为什么存在**：Plan 02 账本 Ruling 107-1 记了一条已知边界——
``EquivalenceTable.lookup()`` 的分支测试当时住在 ``tests/test_refdata_prescription.py``
（domain 测试目录**之外**），失效形态是「删掉那两条测试，``pytest`` 退出码仍是 0，
只有 ``BrPart`` 变红」。Task 3 没做这次搬迁（计划的 File Structure 与 Task 3 的 Files 段
都没有这个文件，新建它超出授权改动面），Ruling 134-1 把它转给 Task 4，本轮落地。

**搬的是哪一条**：``test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable``
（**移动、不是复制**——两份重复的守卫会各自漂移，硬规矩 #51 讲的是「同一段逻辑的两个副本
要逐份修」，而不是「同一条测试要留两份」）。它是 :meth:`EquivalenceTable.lookup` 那个
``for`` + 两个 ``if`` 的**唯一**分支守卫：

* ``mapping.from_ref != ref`` → ``continue``（查不到这个 ref）
* ``IMPACT_RANK[max_impact] >= ceiling_rank`` → ``return``（命中）
* 循环走完 → ``return None``（有映射但上限不够）

⚠️ **本文件守不住什么**（硬规矩 #39）：

* **不守 ``exercises.yaml`` / ``exercise_equivalence.yaml`` 的字节**——那是
  ``tests/test_refdata_prescription.py`` 的两条指纹测试（本文件仍**读**真表，故 YAML 变了
  这里可能跟着红，但红的原因不是分支）。
* **不守 ``IMPACT_RANK`` 的秩值**——那是
  :func:`tests.test_refdata_prescription.test_impact_rank_values_are_pinned_verbatim`
  （Ruling 107-2）。⚠️ **它今天仍住在 domain 测试目录之外**：Ruling 107-1 的原文只授权搬
  ``lookup()`` 的分支测试，而 ``test_refdata_prescription.py`` 的模块 docstring 那句
  「这两条应当搬过去归位」说的是**更宽**的范围（秩值 + 公开面基线）。本轮按 Ruling 134-1③
  的字面范围只搬了 ``lookup()``，理由写在报告里。
* **不守 :func:`app.refdata_prescription.load_equivalence`**——本文件构造的合成表直接
  调 :class:`EquivalenceTable` 的构造器，绕过加载器。
"""
from app import refdata_prescription as rp
from app.domain.prescription.exercises import (
    EquivalenceMapping,
    EquivalenceTable,
    ImpactLevel,
)


def test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable():
    """:meth:`EquivalenceTable.lookup` 的三条语义，各带一个「应当红」与「应当绿」的输入。

    硬规矩 #50：设计守卫必须同时构造两种输入并都跑。这里
    ``ImpactLevel.LOW`` 与 ``ImpactLevel.MEDIUM`` 两个上限对**同一张合成表**给出不同
    答案，才证明 ``impact_ceiling`` 这个参数真的被用上了（否则它可以被删掉而全部测试
    仍然绿）。合成表是必要的：真实的 ``exercise_equivalence.yaml`` 里每条映射的
    ``max_impact`` 都是 ``low``，用它无法区分「上限被尊重」与「上限被忽略」。

    ⚠️ **本条自 Task 4 起住在 ``tests/domain/``**（原住
    ``tests/test_refdata_prescription.py``，账本 Ruling 107-1 / 134-1③）：它是
    :meth:`EquivalenceTable.lookup` 全部分支的唯一守卫，而 ``app/domain/`` 受 100%
    **分支**覆盖约束（Global Constraint #2）——住在 domain 测试目录之外时，删掉它
    ``pytest`` 退出码仍是 0、只有 ``--cov-branch`` 的 ``BrPart`` 会红。
    断言与期望值一个字未改（搬迁前后都是同一批字面量）。
    """
    table = rp.load_equivalence()
    # 真表：high 动作在三个上限下都能查到替身（low <= 任何上限）
    assert table.lookup("interval_run", ImpactLevel.LOW) == "stationary_cycling"
    assert table.lookup("interval_run", ImpactLevel.MEDIUM) == "stationary_cycling"
    assert table.lookup("interval_run", ImpactLevel.HIGH) == "stationary_cycling"
    # 真表：没有映射的 ref → None（Task 7 据此走 needs_review，spec §7.4:514）
    assert table.lookup("challenge_task", ImpactLevel.LOW) is None
    assert table.lookup("__不存在的 ref__", ImpactLevel.LOW) is None

    # 合成表：max_impact=medium 的映射在 LOW 上限下**必须查不到**
    synthetic = EquivalenceTable(
        version="synthetic",
        mappings=(
            EquivalenceMapping(
                from_ref="a", to_ref="b",
                max_impact=ImpactLevel.MEDIUM, when="bmi_over_30",
            ),
        ),
        volume_reduction={},
    )
    assert synthetic.lookup("a", ImpactLevel.MEDIUM) == "b"
    assert synthetic.lookup("a", ImpactLevel.HIGH) == "b"
    assert synthetic.lookup("a", ImpactLevel.LOW) is None

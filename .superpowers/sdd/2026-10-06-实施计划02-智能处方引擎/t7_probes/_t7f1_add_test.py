"""F1-1 Step 1（TDD 的红）：往 tests/pipeline/test_prescription_stage.py 的 B5 节尾
插入 test_trigger_2_survives_the_deletion_of_that_days_stratification_row。

硬规矩 #79：每处替换都 assert 命中次数。UTF-8 无 BOM、行尾保持原样。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]
P = ROOT / "backend" / "tests" / "pipeline" / "test_prescription_stage.py"
src = P.read_text(encoding="utf-8")

ANCHOR = '''    assert rows[d2].trigger_reasons == ["layer_changed"]
    assert rows[d2].valid_to == dt.date(2025, 10, 19)


def test_regeneration_does_not_inherit_teacher_overrides(session, seed_dir):
'''

NEW = '''    assert rows[d2].trigger_reasons == ["layer_changed"]
    assert rows[d2].valid_to == dt.date(2025, 10, 19)


def test_trigger_2_survives_the_deletion_of_that_days_stratification_row(bare):
    """**fix round 1（F1-1）的唯一可执行判据**：删掉「生成那一天」的分层结果行之后，
    触发 2 仍然成立。

    ``prescription.label_at_generation`` 这一列存在的全部理由就是本条测试。在此之前
    「上一张处方生成当时的标签」只能 ``outerjoin`` 回读**同一天**的
    ``stratification_result``，而那一行是**会被删的**——
    :func:`app.pipeline.daily._replay_cleanup` 按 ``batch_id`` 删它（Plan 01 的既有口径），
    于是重放那一天之后 join 返回 ``NULL``：

    * 当时的实际行为：``_last_prescription_of`` 响亮抛 ``ValueError``、整批回滚（那条守卫
      叫 ``test_a_prescription_whose_stratification_row_is_gone_fails_loudly``，
      **已由本条取代**——它钉的那个失效形态在加了本列之后结构上不可达）；
    * 更糟的可能行为：若当初写成 ``join`` 而不是 ``outerjoin``，这个人会**静默**变成
      「没有上一张处方」→ 触发 1 → 天天重发处方、教师覆盖天天被冲掉。

    而 spec §4.3 要的是「任一条结果都能离线复算」：把判定输入快照在处方行上（与 P6-A3
    给 ``microcycle_weeks`` 快照**同构**），触发判定就不再依赖另一张表的行还在不在。

    ⚠️ 红/绿取证（硬规矩 #65）：加列**之前**本条以
    ``ValueError: 学生 … 没有分层结果 …`` 当场报错（红），加列 +
    ``_last_prescription_of`` 改读本列之后绿；两次实测输出记在 Task 7 报告 fix round 1。
    """
    session, sem = bare
    d2 = dt.date(2025, 9, 22)
    b1, b2 = _batch(session, sem, AS_OF), _batch(session, sem, d2)
    student = _student(session, "2025001001")
    _strat_row(session, student, AS_OF, b1, "red")
    assert _generate(session, sem, b1, AS_OF).generated == 1
    assert _count(session, Prescription) == 1

    # 重放 AS_OF 那天会做的事：按批删掉本批的分层结果行（这里按日期删，形状等价）
    session.execute(
        delete(M.StratificationResult).where(M.StratificationResult.computed_on == AS_OF)
    )
    session.flush()
    assert _count(session, M.StratificationResult) == 0, "那一天的分层行已经不在了"

    _strat_row(session, student, d2, b2, "yellow")
    second = _generate(session, sem, b2, d2)
    assert second.generated == 1

    rows = {row.generated_on: row for row in session.scalars(select(Prescription))}
    assert sorted(rows) == [AS_OF, d2]
    # 触发 2 仍然成立：比较对象是处方行上快照的那一个，不是（已删的）分层行
    assert rows[d2].trigger_reasons == ["layer_changed"]
    assert rows[d2].label_at_generation == "yellow"
    assert rows[AS_OF].label_at_generation == "red"
    assert rows[AS_OF].status == "replaced"
    assert rows[d2].status == "active"


def test_regeneration_does_not_inherit_teacher_overrides(session, seed_dir):
'''

assert src.count(ANCHOR) == 1, src.count(ANCHOR)
P.write_text(src.replace(ANCHOR, NEW), encoding="utf-8", newline="")
after = P.read_text(encoding="utf-8")
assert after.count("def test_trigger_2_survives_the_deletion_of_that_days_stratification_row") == 1
print("OK 已插入；新行数 =", after.count("\n"), " 新字节数 =", len(after.encode("utf-8")))

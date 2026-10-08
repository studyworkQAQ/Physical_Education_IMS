# backend/tests/domain/test_prescription_intensity.py
"""HRmax 与目标心率区间 :mod:`app.domain.prescription.intensity` 的守卫（Plan 02 Task 5 的 5.1）。

**期望值一律字面写死**（硬规矩 #35 / Global Constraint #4），且**由实现者独立重算**、
不照抄派单（硬规矩 #44）。重算过程（本机 Python 3.11.1 亲跑 ``repr()``）::

    208 - 0.7 * 20 = 194.0      208 - 0.7 * 18 = 195.4      208 - 0.7 * 25 = 190.5

三个都是**精确的 float**（``repr`` 无尾数），故下面用 ``==`` 而不是 ``pytest.approx``。

**取整方向的可暴露算例**：``194.0 * 60 / 100.0 = 116.4``、``194.0 * 70 / 100.0 = 135.8``
——两个端点都**不是整数**，故「低界向下、高界向上」与「两个都向下」给出不同结果
（``(116, 136)`` vs ``(116, 135)``），:func:`test_hr_zone_rounds_conservatively_outward`
因此真的有牙（简报 5.5 Step 4 的变异 ④ 打的就是它）。
⚠️ **算式写法承重**：``194.0 * 60 / 100.0`` 是 ``116.4``，而 ``194.0 * 0.6`` 是
``116.39999999999999``（亲跑 ``repr``）。两者 ``int()`` 之后同为 116、``ceil`` 之后同为
136，故本文件的断言对这一选择不敏感；但生产侧仍写 ``/ 100.0`` 那一种，因为它离
「百分比」的语义更近、且不给将来的 ``round`` 埋一个 1e-14 的坑。

⚠️ **本文件守不住什么**（硬规矩 #39）：

* **不守 Tanaka 是不是正确的公式**。spec §14 第 14 项已把「Tanaka 还是 ``220 − 年龄``」
  列为待确认事项；本文件钉的是「实现的就是 Tanaka」，不是「Tanaka 对」。
* **不守 ``age_from`` 的闰年语义**。``2000-02-29`` 出生者在非闰年的生日落在哪一天，
  指导文件与 spec 都没给；实现取的是「``(月, 日)`` 元组比较」这一最常见的口径
  （非闰年时生日等效落在 3 月 1 日），**没有测试钉它**（简报把闰年边界砍掉了）。
* **不守生产路径上谁调用 ``measured``**：Plan 01/02 没有任何心率数据
  （``fitness_test_result`` 的 8 个原始列里没有心率），故 ``measured`` 今天只有本文件在调。
"""
import datetime as dt

import pytest

# ⚠️ **从所有者模块直接 import**（``app.domain.prescription.intensity``），不从包的
# ``__init__`` 取：重导出与 ``_PRESCRIPTION_PUBLIC_BASELINE`` 的扩容是简报 5.5 Step 5 的活，
# 在那之前包上还没有这三个名字，从这里 import 才能让 5.1 这一个 commit 自己是绿的。
# 口径照 ``app/domain/prescription/templates.py`` 模块 docstring 那句「**新代码请直接从
# 所有者导入**」。
from app.domain.prescription.intensity import age_from, hr_zone, hrmax

# ---------------------------------------------------------------------------
# 5.1 的三个函数
# ---------------------------------------------------------------------------


def test_tanaka_hrmax_matches_the_independently_recomputed_literals():
    """``208 − 0.7 × age``（Tanaka）在三个年龄上的字面值。

    期望值 ``194.0`` / ``195.4`` / ``190.5`` 由本文件开头的 ``repr()`` 重算得到，
    与派单那张表一致（**两边都对上了**，故不存在「先怀疑自己还是先怀疑表」的分歧）。
    """
    assert hrmax(20) == 194.0
    assert hrmax(18) == 195.4
    assert hrmax(25) == 190.5
    # 19 与 21 是本仓真实在校年龄的两端（app.domain.indicators 的 AGE_GROUPS 以 19/20 分组）
    assert hrmax(19) == 194.7
    assert hrmax(21) == 193.3


def test_hrmax_rejects_a_non_positive_age_and_prints_the_age_it_got():
    """Review Focus 第 4 条：``age <= 0`` **响亮拒绝**，且消息里带实际收到的年龄。

    **为什么不是夹取、不是返回 ``None``**：Tanaka 在 ``age = 0`` 时给 ``208`` bpm，那是一个
    **看起来完全正常**的数字，会被装配成一个危险的目标心率区间——静默产出荒谬值比崩溃危险
    （简报 5.1「决定」第 1 条）。``-5`` 与 ``137`` 是刻意挑的**可辨识**年龄：一条只断言
    ``"0" in message`` 的测试会被任何含 0 的消息蒙混过去。
    """
    for bad_age in (0, -5):
        with pytest.raises(ValueError) as excinfo:
            hrmax(bad_age)
        assert str(bad_age) in str(excinfo.value), (
            f"age={bad_age} 的报错消息里没有它自己，排障时看不出收到了什么："
            f"{excinfo.value}"
        )


def test_hrmax_rejects_an_age_of_100_or_more_and_prints_the_age_it_got():
    """上边界同样是**开区间**：``age >= 100`` 拒绝（``99`` 放行）。

    ``age == 100`` 这一格是边界，必须落在拒绝侧；``99`` 是紧邻的绿档，两者一起才证明
    比较符是 ``>=`` 而不是 ``>``。``138.7`` 是 ``repr(208 - 0.7 * 99)`` 的亲跑字面值
    （精确、无尾数），故写死它而不在断言里重算一遍算式——重算会让期望侧与被测侧同源
    （硬规矩 #35）。
    """
    assert hrmax(99) == 138.7
    for bad_age in (100, 137):
        with pytest.raises(ValueError) as excinfo:
            hrmax(bad_age)
        assert str(bad_age) in str(excinfo.value)


def test_a_measured_hrmax_wins_over_tanaka_and_is_returned_verbatim():
    """``measured`` 非空时**直接返回它**，不做任何换算、不与 Tanaka 取小/取大。

    ⚠️ ``measured`` **今天没有任何生产调用点**（``fitness_test_result`` 的 8 个原始列里
    没有心率）：它是为将来的穿戴设备留的口，本条与下一条是它唯一的消费者。
    ``186.0`` 与 Tanaka 的 ``194.0`` 相差 8 bpm，故「返回的是实测值」这件事可辨识。
    """
    assert hrmax(20, measured=186.0) == 186.0
    assert hrmax(20, measured=None) == 194.0
    # 实测值高于 Tanaka 时同样原样返回（不夹取到公式值）
    assert hrmax(20, measured=201.0) == 201.0


def test_hrmax_rejects_a_measured_value_outside_the_60_to_220_window():
    """实测 HRmax 的合法窗口是**闭区间** ``[60, 220]``：两个端点放行、越界拒绝。

    端点放行与越界拒绝必须**同时**断言，否则「``<=`` 写成 ``<``」这类改法只会红一半、
    而两个方向都是坏值（``60`` bpm 的实测 HRmax 是一个真实的低值，``59.9`` 则说明
    上游读数坏了）。
    """
    assert hrmax(20, measured=60.0) == 60.0
    assert hrmax(20, measured=220.0) == 220.0
    for bad in (59.9, 220.1, 0.0, -3.0):
        with pytest.raises(ValueError):
            hrmax(20, measured=bad)


def test_hr_zone_rounds_conservatively_outward():
    """低界**向下**、高界**向上**：区间略宽比略窄安全（简报 5.1 的 Produces 段）。

    ``hr_zone(194.0, 60, 70)``：低界 ``194.0 × 60 / 100.0 = 116.4`` → ``int()`` → **116**；
    高界 ``194.0 × 70 / 100.0 = 135.8`` → ``-(-135.8 // 1)`` → **136**。
    期望值 ``(116, 136)`` **字面写死**，且与派单那张算例表逐字一致（独立重算后对上了）。

    ⚠️ **``int()`` 只在正数上等价于 ``floor``**（``int(-0.5) == 0`` 而 ``floor(-0.5) == -1``），
    故 :func:`hr_zone` 那条 ``hrmax_bpm <= 0`` 的拒绝**不是可选的**——它是这个等价关系成立的
    前提（简报 P5-A4）。下一条测试钉它。
    """
    assert hr_zone(194.0, 60, 70) == (116, 136)
    # 端点本来就是整数时不额外放宽一格（194.0 × 50 / 100.0 = 97.0，两侧都取到 97）
    assert hr_zone(194.0, 50, 50) == (97, 97)
    # 全域端点：0% 向下取整仍是 0，100% 向上取整不越过 HRmax 自己
    assert hr_zone(200.0, 0, 100) == (0, 200)


def test_hr_zone_rejects_a_non_positive_hrmax():
    """``hrmax_bpm <= 0`` 拒绝（简报 P5-A4 新增的那一条守卫）。

    **它承重的理由不是「0 bpm 荒谬」**（那当然也荒谬），而是：低界用 ``int()`` 向下取整，
    而 ``int()`` 对**负数**是**向零**取整而不是向下（``int(-0.5) == 0``、``floor(-0.5) == -1``）。
    domain 的 allow-list 不放行 ``math``（:data:`tests.architecture.test_domain_purity.ALLOWED_MODULES`
    实测 = ``{dataclasses, enum, collections, collections.abc, numpy, typing}``），故拿不到
    ``math.floor``；把 ``hrmax_bpm <= 0`` 挡在门外之后，``int()`` 的向零取整与 ``floor``
    在本函数的定义域上**恒等价**。删掉这一条，``hr_zone(-194.0, 60, 70)`` 会给出
    ``(-116, -135)`` 这种「低界比高界大」的区间而不报错。
    """
    for bad in (0.0, -1.0, -194.0):
        with pytest.raises(ValueError):
            hr_zone(bad, 60, 70)


def test_hr_zone_rejects_illegal_percentages():
    """``low > high`` / ``low < 0`` / ``high > 100`` 三档一律拒绝。

    三档各挑一个**只有它自己触发**的输入，否则一条断言红了分不清是哪一档失守：
    ``(70, 60)`` 只违反 ``low > high``、``(-1, 60)`` 只违反 ``low < 0``、
    ``(60, 101)`` 只违反 ``high > 100``。
    ``low == high`` 是**合法**的（一个退化成单点的区间），与加载器
    :func:`app.refdata_prescription._intensity` 对 ``hrmax_pct`` 的 ``low >= high`` 拒绝
    **不同口径**——那一侧守的是模板数据的形状，这一侧是一个纯算术函数的定义域。
    """
    for low, high in ((70, 60), (-1, 60), (60, 101)):
        with pytest.raises(ValueError):
            hr_zone(194.0, low, high)
    assert hr_zone(194.0, 0, 100) == (0, 194)


def test_age_from_is_the_completed_years_age_not_a_year_subtraction():
    """**周岁**：生日未过则减 1。「年份相减」会多算一岁。

    三格各是一个不同的分支：生日**当天**（``==``，不减）、生日**前一天**（减 1）、
    生日**后一天**（不减）。``2006-03-15`` 出生、``2026-10-06`` 为 ``as_of``
    （本计划的日期），周岁是 ``20``——年份相减同样给 20，故那一格证明不了什么；
    真正承重的是把 ``as_of`` 挪到 ``2026-03-14``（周岁 19、年份相减 20）与
    ``2026-03-15``（周岁 20）。
    """
    birth = dt.date(2006, 3, 15)
    assert age_from(birth, dt.date(2026, 3, 14)) == 19
    assert age_from(birth, dt.date(2026, 3, 15)) == 20
    assert age_from(birth, dt.date(2026, 3, 16)) == 20
    assert age_from(birth, dt.date(2026, 10, 6)) == 20
    # 年末出生、年初为 as_of：年份相减给 1、周岁给 0
    assert age_from(dt.date(2025, 12, 31), dt.date(2026, 1, 1)) == 0


def test_age_from_accepts_any_object_with_year_month_day():
    """domain **不 import** ``datetime``，故 ``age_from`` 是 duck typing 的。

    ``app/domain/`` 的 allow-list（:data:`tests.architecture.test_domain_purity.ALLOWED_MODULES`）
    不放行 ``datetime``，:mod:`app.domain.prescription.templates` 为此把 ``reviewed_at``
    做成 ``str | None``。本模块的处置不同（**日期要参与算术、折成 ISO 串再解析回来更绕**），
    故只读注入对象的 ``year`` / ``month`` / ``day`` 三个属性。本条钉住「一个不是
    ``datetime.date`` 但带这三个属性的对象同样能用」，即钉住这个 duck typing 契约本身，
    免得下一个人以为可以在这里 ``import datetime``。
    """

    class _FakeDate:
        def __init__(self, year: int, month: int, day: int) -> None:
            self.year, self.month, self.day = year, month, day

    assert age_from(_FakeDate(2006, 3, 15), _FakeDate(2026, 3, 14)) == 19
    assert age_from(_FakeDate(2006, 3, 15), dt.date(2026, 3, 15)) == 20

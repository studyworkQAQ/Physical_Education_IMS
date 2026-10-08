"""HRmax 与目标心率区间（Plan 02 Task 5 的 5.1；spec §7.2 ``:487``、§7.3 ``:496``）。

**三个纯函数，一个都不读盘、不读时钟**（Global Constraint #1）：``age`` 与 ``as_of`` 由
调用方注入，于是「同一份输入 → 同一个输出」（spec §1.3）。

--------------------------------------------------------------------------

**只实现 Tanaka，不实现 FOX、也不抽象出 ``HrmaxFormula`` 枚举**（简报 Task 5 合并说明的
①）：

* 公式 ``HRmax = 208 − 0.7 × age``。本机 Python 3.11.1 亲跑 ``repr``：
  ``208 - 0.7 * 20 = 194.0``、``208 - 0.7 * 18 = 195.4``、``208 - 0.7 * 25 = 190.5``
  ——三个都是**精确 float**（无尾数），故守卫
  ``tests/domain/test_prescription_intensity.py`` 用 ``==`` 而不是 ``pytest.approx``。
* spec §14 第 **14** 项已把「Tanaka 还是 ``220 − 年龄``」列为待确认事项。本模块只落
  Tanaka；将来切换只改**这一处**（``hrmax`` 只有一个生产调用点：
  :func:`app.domain.prescription.assembler.assemble` 的第 1 步），**不需要为此今天就抽象出
  一个枚举**——那是为一个还没发生的需求预付一层间接。

**``hrmax`` 不返回 ``None``、不静默夹取**（Review Focus 第 4 条）：Tanaka 在 ``age = 0`` 时
给 ``208`` bpm，那是一个**看起来完全正常**的数字，会被装配成一个危险的目标心率区间。
**静默产出荒谬值比崩溃危险**，故 ``age <= 0 or age >= 100`` 一律 ``ValueError``，且消息里
带**实际收到的年龄**（排障时第一个要问的就是「上游到底给了几岁」）。

⚠️ **``age`` 的校验对 ``measured`` 那一档同样生效**：``measured`` 非空时公式用不到 ``age``，
但一个荒谬的年龄说明 ``StudentProfile`` 本身坏了（``birth`` 缺失或 ``as_of`` 传错），
那时「心率是实测的所以年龄无所谓」是一个错误的安慰。故校验顺序是**先年龄、后实测值**。

**``measured`` 今天没有任何生产调用点**（硬规矩 #39）：Plan 01/02 **没有任何心率数据**
——``fitness_test_result`` 的 8 个原始列（``app/domain/indicators.py`` 的
:data:`~app.domain.indicators.COLUMN_BY_ITEM` 6 列 + ``height_cm`` / ``weight_kg``）里
没有心率，体成分三列（``muscle_mass_kg`` / ``body_fat_pct`` / ``smi``）里也没有。它是为
将来的穿戴设备留的口，今天只有测试调它。窗口 ``[60, 220]`` 的两端都是**闭**的：
``60`` bpm 是一个真实的低值（运动员静息心率量级），``220`` 是「``220 − 年龄``」那个旧公式
在 0 岁上的取值、也是文献里 HRmax 的常用上界；越界说明上游读数坏了，不是「夹一下就能用」。

--------------------------------------------------------------------------

⚠️ **本模块不 import ``datetime``**（简报 P5-A4 的同一条纪律）：
:data:`tests.architecture.test_domain_purity.ALLOWED_MODULES` 实测 =
``{dataclasses, enum, collections, collections.abc, numpy, typing}``，**``datetime`` 不在其中**，
``math`` 也不在。往 allow-list 里加模块是**扩大 domain 可用面**的架构决策，不是一个 Task
能顺手做的（:mod:`app.domain.prescription.templates` 为此把 ``reviewed_at`` 做成
``str | None`` 而不是 ``datetime.date``，理由逐字写在它的模块 docstring 里）。

于是 :func:`age_from` 的两个日期参数是 **duck typing** 的：本模块只读它们的
``year`` / ``month`` / ``day`` 三个属性，标注写成**前向引用字符串** ``"dt.date"``。
**代价必须写明**（硬规矩 #39）：``dt`` 在本模块的命名空间里**不存在**，故
``typing.get_type_hints(age_from)`` 会抛 ``NameError``。今天全仓没有任何一处调它
（``inspect.signature`` 不求值标注，``tests/domain/test_derive.py`` 的
``test_smi_is_not_an_input_at_all`` 用的正是 ``inspect.signature``），而**换来的是**：
domain 仍然读不到时钟，且标注对人类读者与静态检查器都是准确的。守卫是
``test_age_from_accepts_any_object_with_year_month_day``——它钉住「duck typing」这个契约
本身，免得下一个人以为可以在这里补一句 ``import datetime``。

⚠️ **取整不许用 ``math``**：低界 ``int(x)``（向下）、高界 ``int(-(-x // 1))``（向上）。
``int()`` **只在正数上等价于 ``floor``**（``int(-0.5) == 0`` 而 ``floor(-0.5) == -1``），
故 :func:`hr_zone` 那条 ``hrmax_bpm <= 0`` 的拒绝**不是可选的**——它是这个等价关系成立的
前提。删掉它，``hr_zone(-194.0, 60, 70)`` 会给出 ``(-116, -135)`` 这种「低界比高界大」的
区间而不报错。

**取整方向是保守方向**：低界向下、高界向上，即**区间略宽比略窄安全**。一个偏窄的目标
心率区间会让学生以为「我已经练到位了」而实际上没达到刺激阈值；偏宽最多让他多练一点，
而 §7.4 的安全后置与 §8.2 的课堂 RPE 快评是兜住过量的那两道。

--------------------------------------------------------------------------

⚠️ **本模块守不住什么**（硬规矩 #39）：

* **不守 Tanaka 公式本身对不对**（spec §14 第 14 项待确认）。守的是「实现的就是 Tanaka」。
* **不守 ``age_from`` 的闰年语义**：``2000-02-29`` 出生者在非闰年的生日落在哪一天，
  指导文件与 spec 都没给。本实现取「``(月, 日)`` 元组比较」这一最常见口径，于是非闰年时
  生日**等效落在 3 月 1 日**（``(2, 28) < (2, 29)`` 为真 → 减一岁；``(3, 1) < (2, 29)``
  为假 → 不减）。简报把闰年边界测试砍掉了，故**这一档没有守卫**。
* **不守 ``age`` 与 ``birth``/``as_of`` 的一致性**：那是
  :func:`app.domain.prescription.assembler.assemble` 第 1 步的一致性闸门
  （``age == age_from(birth, as_of)``，不一致抛 ``ValueError``）。本模块的两个函数各管一半，
  谁把它们喂歪了本模块看不出来。
"""

#: Tanaka 公式的截距与斜率：``HRmax = 208 − 0.7 × age``。
#: **私有**：spec §14 第 14 项还没定「Tanaka 还是 ``220 − 年龄``」，把两个系数做成公开面
#: 会让「换公式」变成一次破坏公开契约的改动；今天它们只有 :func:`hrmax` 一个消费者。
_TANAKA_INTERCEPT = 208.0
_TANAKA_SLOPE = 0.7

#: ``age`` 的合法开区间 ``(0, 100)``。**私有**，理由同上；两个端点都是**拒绝**侧
#: （``age == 0`` 给 208 bpm 的荒谬值、``age == 100`` 已超出在校大学生两个数量级）。
_AGE_MIN_EXCLUSIVE = 0.0
_AGE_MAX_EXCLUSIVE = 100.0

#: 实测 HRmax 的合法**闭**区间 ``[60, 220]``。取值理由见模块 docstring 的第 4 段。
_MEASURED_MIN = 60.0
_MEASURED_MAX = 220.0


def hrmax(age: float, measured: float | None = None) -> float:
    """最大心率（bpm）。``measured`` 非空则用它，否则 Tanaka ``208 − 0.7 × age``。

    **校验顺序是先年龄、后实测值**，且**年龄对两档都校验**（理由见模块 docstring）。
    三条 ``ValueError``：``age <= 0``、``age >= 100``、``measured`` 落在 ``[60, 220]`` 之外。
    年龄那两条的消息里带**实际收到的年龄**。

    ⚠️ **不返回 ``None``、不夹取**：Review Focus 第 4 条点名的失效形态是「``birth`` 为空 →
    算出 0 岁 → Tanaka 给 208 bpm → 一个看起来正常的危险区间」。返回 ``None`` 会让下游
    多一个 ``if``、夹取会让荒谬值继续往下流，两者都不如当场炸。

    ⚠️ ``measured`` **今天没有生产调用点**（Plan 01/02 没有任何心率数据），它是为将来的
    穿戴设备留的口——本函数的 ``measured`` 那一支今天只被
    ``tests/domain/test_prescription_intensity.py`` 走过（硬规矩 #39）。
    """
    if age <= _AGE_MIN_EXCLUSIVE or age >= _AGE_MAX_EXCLUSIVE:
        raise ValueError(
            f"年龄 {age} 不在开区间 (0, 100) 内，无法用 Tanaka 公式"
            f"（HRmax = {_TANAKA_INTERCEPT} − {_TANAKA_SLOPE} × age）算最大心率。"
            f"不夹取、不返回 None：age = 0 会给 {_TANAKA_INTERCEPT} bpm 这个"
            f"**看起来完全正常**的值，进而装配出一个危险的目标心率区间"
            f"（Review Focus 第 4 条）。请检查上游的 birth 与 as_of"
        )
    if measured is not None:
        if measured < _MEASURED_MIN or measured > _MEASURED_MAX:
            raise ValueError(
                f"实测最大心率 {measured} bpm 不在闭区间 "
                f"[{_MEASURED_MIN}, {_MEASURED_MAX}] 内：越界说明上游读数坏了，"
                f"夹取会把一个坏读数变成一个看起来可信的心率区间"
            )
        return float(measured)
    return _TANAKA_INTERCEPT - _TANAKA_SLOPE * age


def hr_zone(hrmax_bpm: float, low_pct: float, high_pct: float) -> tuple[int, int]:
    """把「HRmax 的百分比区间」换算成**个体绝对 bpm 区间**（spec §7.3 ``:496`` 的第 2 步）。

    **取整方向**：低界**向下**（``int()``）、高界**向上**（``int(-(-x // 1))``）——
    保守方向，区间略宽比略窄安全（理由见模块 docstring 的倒数第 3 段）。
    ``hr_zone(194.0, 60, 70)`` 亲跑给 ``(116, 136)``：低界 ``194.0 × 60 / 100.0 = 116.4``、
    高界 ``194.0 × 70 / 100.0 = 135.8``，两个端点都不是整数，故这一格真的能暴露取整方向
    （守卫 :func:`tests.domain.test_prescription_intensity.test_hr_zone_rounds_conservatively_outward`，
    简报 5.5 Step 4 的变异 ④ 打的就是它）。

    ⚠️ **算式写 ``× pct / 100.0`` 而不是 ``× (pct / 100)``**：亲跑 ``repr``，
    ``194.0 * 60 / 100.0 = 116.4`` 而 ``194.0 * 0.6 = 116.39999999999999``。两者在本函数
    里取整后同为 ``116``（``194.0 * 0.7 = 135.79999999999998``、向上取整同为 ``136``），
    故断言对这一选择不敏感；仍选前者，因为它离「百分比」的语义更近、且不给将来某个
    ``round(x, 1)`` 埋一个 1e-14 的坑（Plan02 账本 P5-A6 记的正是这一类浮点尾数）。

    **三条 ``ValueError``**：``hrmax_bpm <= 0``（⚠️ **承重**：``int()`` 对负数是向零取整
    而不是向下，故这条拒绝是「``int()`` == ``floor``」这个等价关系的前提，见模块 docstring）、
    ``low_pct > high_pct``、``low_pct < 0``、``high_pct > 100``。
    ``low_pct == high_pct`` 是**合法**的（退化成单点区间）：加载器
    :func:`app.refdata_prescription._intensity` 对模板里 ``hrmax_pct`` 的 ``low >= high``
    拒绝守的是**数据形状**，本函数是一个纯算术函数、守的是**定义域**，两者口径不同是有意的。
    """
    if hrmax_bpm <= 0:
        raise ValueError(
            f"HRmax {hrmax_bpm} bpm 应 > 0：低界用 int() 向下取整，而 int() 对负数是"
            f"**向零**取整（int(-0.5) == 0 而 floor(-0.5) == -1），故这条拒绝是"
            f"「int() 等价于 floor」成立的前提，不是一个可选的健壮性检查"
            f"（domain 的 allow-list 不放行 math，拿不到 math.floor）"
        )
    if low_pct < 0 or low_pct > high_pct or high_pct > 100:
        raise ValueError(
            f"目标心率区间百分比非法: low={low_pct}, high={high_pct}；"
            f"要求 0 <= low <= high <= 100。一个空区间或反区间会让学生拿到一个"
            f"谁也落不进去的目标心率"
        )
    low_bpm = hrmax_bpm * low_pct / 100.0
    high_bpm = hrmax_bpm * high_pct / 100.0
    # 低界向下（int()，此处恒为正数，故等价于 floor）、高界向上（-(-x // 1)）
    return int(low_bpm), int(-(-high_bpm // 1))


def age_from(birth: "dt.date", as_of: "dt.date") -> int:
    """**周岁**：生日未过则减 1（不是「年份相减」）。

    ``as_of`` 由调用方注入，domain 不碰时钟（Global Constraint #1）。生产路径上它是
    :func:`app.domain.prescription.assembler.assemble` 的 ``as_of`` 形参，再上游是
    ``app/pipeline/daily.py`` 的业务日。

    判据是 ``(as_of.month, as_of.day) < (birth.month, birth.day)``：元组比较先比月、
    月相同再比日，与「生日当天算已满一岁」一致（``==`` 时不减）。
    ⚠️ **标注是前向引用字符串**，因为本模块不 import ``datetime``（代价与理由见模块
    docstring 的第 5 段）：只读 ``year`` / ``month`` / ``day``，任何带这三个 ``int`` 属性的
    对象都能喂进来。

    ⚠️ **闰年语义不被守卫**（硬规矩 #39）：``2000-02-29`` 出生者在非闰年的生日等效落在
    **3 月 1 日**（``(2, 28) < (2, 29)`` → 减一岁；``(3, 1) < (2, 29)`` → 不减）。指导文件
    与 spec 都没给这一档，简报也把闰年边界测试砍掉了。
    """
    age = as_of.year - birth.year
    if (as_of.month, as_of.day) < (birth.month, birth.day):
        age -= 1
    return age

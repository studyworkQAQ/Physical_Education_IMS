"""``app.auth.policy`` 的守卫：**登录**限流与锁定（Plan 06 Task 3-B）
+ **绑定**限流与「用途」那一维（Plan 06 Task 10，本文件第 ⑦ 节）。

**这一份文件钉的是「阈值 + 三个动作」在纯 ORM 层的行为**（:mod:`app.auth` 不 import
``fastapi``，故本文件也不需要 ``TestClient``）。HTTP 那一半——「锁内回的是与正常失败
**逐字相同**的 ``401 invalid_credentials``」——住在 ``tests/api/test_auth_api.py``，
因为「哪个码」是 HTTP 的事、本模块只答一个 ``bool``。两份守卫**刻意不合并**，
分工与 ``tests/auth/test_sessions.py`` ↔ ``tests/api/test_auth_api.py`` 逐字相同。

--------------------------------------------------------------------------
⚠️⚠️ 两条**定点变异**守卫（派单 §1 第 6 格点名要的）
--------------------------------------------------------------------------

限流这类代码最坏的失效形态是**静默不生效**：没有报错、没有异常，只是「怎么试都不锁」。
而它偏偏很容易写出来——把 ``counted < max_fails`` 那一行删掉、或把窗口那一格
``at >= now - window`` 删掉，全量测试都照样绿（因为**没有任何既有测试连打五次口令**）。
故本文件里有两条**红档专门为此存在**：

* :func:`test_the_count_really_gates_the_lock` —— 去掉「计数」那一格（把
  ``counted < policy.max_fails`` 改成恒 ``False``，或直接 ``return True``）→ **本条红**：
  它断言「**4** 次失败还没锁、第 **5** 次才锁」，一个恒真的实现会让前半句当场红。
* :func:`test_the_window_really_gates_the_count` —— 去掉「窗口」那一格（把
  ``LoginAttempt.at >= current - policy.window`` 删掉）→ **本条红**：
  它断言「5 次失败**全部落在窗口之外**时不锁」，一个不看时间的实现会数到 5 → 锁。

⚠️ **两条变异都由本 Task 亲跑复现过**（改前绿、改后红），取证见
``task-3-4-report.md`` 的 §2。⚠️ 而它们**不是恒绿的装饰**：两条各自还带一个
「绿档同时在场」的对照拍（硬规矩 #50），故「一律不锁」与「一律锁」两个方向都能红。

--------------------------------------------------------------------------
⚠️⚠️ Plan 06 Task 10 起本文件多两件事要钉：**第二组阈值**与**键的第三维**
--------------------------------------------------------------------------

* **第二组阈值**（``PE_BIND_*``，缺省 **3 / 15 / 60**）：三格一律比登录那一组更严，
  而那是一条算术（出生日期只有约 2 900 个可信取值 ⇒ 5 次 / 15 分钟锁 = 480 次/天
  = 16.5%/天/账号被猜中，3 次 / 60 分钟锁 = 72 次/天 = 2.5%/天/账号）。
  逐字表住在 :mod:`app.auth.policy` 的模块 docstring，本文件钉的是
  「**字面量**是 3/15/60」「三格各自能被自己的环境变量改」「**两组不串线**」。
* **键的第三维**（``purpose``）：⚠️ 它是本件**最容易做错**的一格 ——
  与登录共用一个键的话，「猜出生日期猜错三次」会把那个账号的**登录**也锁掉
  （= 把限流变成拒绝服务），反之亦然。故 :func:`test_the_two_purposes_never_share_a_counter`
  是本波最要紧的一条守卫，而它带的**定点变异**是「把 :func:`app.auth.policy._key`
  改成忽略 ``purpose``」⇒ 那一条当场红（改前绿、改后红，亲跑取证见 Task 10 报告 §5）。

--------------------------------------------------------------------------
⚠️ ``now`` 可注入（同 :func:`app.pipeline.daily.run_daily` 的先例）
--------------------------------------------------------------------------

:func:`test_the_lock_lifts_itself_exactly_when_the_lock_period_has_elapsed` 靠注入
``now`` 走完整条时间线（第 5 次失败 → 锁满前一刻 → 恰好锁满那一刻），
**不睡 15 分钟**。⚠️ 注入的口径与 ``run_daily`` 逐字相同：keyword-only、缺省 ``None``、
``None`` 时取真时钟——故生产路径上一个调用方都不传它，
``git grep "now=" -- backend/app`` 只命中本模块自己与守卫。
"""
import datetime as dt

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import policy
from app.auth.policy import (
    DEFAULT_LOCK_MINUTES,
    DEFAULT_MAX_FAILS,
    DEFAULT_WINDOW_MINUTES,
    LOCK_MIN_ENV_VAR,
    MAX_FAILS_ENV_VAR,
    WINDOW_MIN_ENV_VAR,
    LoginThrottle,
    failure_count,
    is_locked,
    record_failure,
    record_success,
    throttle,
)
from app.auth.sessions import now as session_now
from app.db.models.auth import LoginAttempt
from app.db.session import init_db

#: 三个环境变量名。**字面量**（硬规矩 #35：不从被测模块读回来跟自己比——
#: 那三个 ``*_ENV_VAR`` 常量本身就是被测对象的一半，故这里再写一遍）。
ENV_VARS = ("PE_LOGIN_MAX_FAILS", "PE_LOGIN_WINDOW_MIN", "PE_LOGIN_LOCK_MIN")

#: **绑定**那一组的三个环境变量名（Plan 06 Task 10）。⚠️ 同样是**字面量**、
#: 同样刻意不从 :mod:`app.auth.policy` 的 ``BIND_*_ENV_VAR`` 常量读回来跟自己比。
BIND_ENV_VARS = ("PE_BIND_MAX_FAILS", "PE_BIND_WINDOW_MIN", "PE_BIND_LOCK_MIN")

KIND = "student"
LOGIN = "S2025001"

#: 一个固定的「现在」。⚠️ **naive**：``login_attempt.at`` 与库里其余全部
#: ``DateTime`` 列同口径（``app.auth.sessions.now`` 先转本时区、再摘掉 tzinfo）。
T0 = dt.datetime(2025, 10, 12, 9, 0, 0)


@pytest.fixture()
def session():
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    with Session(eng) as s:
        yield s


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """**每一条**测试都在「**六个**环境变量都没设」的缺省档下跑。

    ⚠️ ``autouse``：少了它，一个在别的测试里 ``monkeypatch.setenv`` 过的进程
    （``monkeypatch`` 会自己撤销，故今天不会发生）或一个在 shell 里设过
    ``PE_LOGIN_MAX_FAILS`` 的人，会让本文件的**全部**阈值断言变成对另一个数的断言。
    失效方向是「守卫测的不是缺省档」，而它是静默的。
    ⚠️ **Plan 06 Task 10 起是六个而不是三个**（+ ``PE_BIND_*`` 那一组）：
    两组阈值走的是**同一份**解析（:func:`app.auth.policy._throttle`），
    故一个在 shell 里设过的 ``PE_BIND_LOCK_MIN`` 会以完全相同的方式污染缺省档断言。
    """
    for name in ENV_VARS + BIND_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _fail_n(db, n, *, kind=KIND, login=LOGIN, at=T0, purpose=policy.PURPOSE_LOGIN):
    """连打 ``n`` 次失败（全部记在同一个时刻 ``at`` 上，故窗口判定是干净的）。

    ⚠️ ``purpose`` 的缺省是**登录**（与五个动作的缺省逐字相同），故本文件既有的
    全部调用方一行都不用改。
    """
    for _ in range(n):
        record_failure(db, kind, login, purpose=purpose, now=at)


# ---------------------------------------------------------------------------
# ① 阈值是**配置**、不是代码
# ---------------------------------------------------------------------------


def test_the_default_threshold_is_five_fails_in_a_fifteen_minute_window_locking_for_fifteen(
        monkeypatch):
    """缺省三格是 **5 / 15 / 15**，且它们钉的是**字面量**、不是 :func:`throttle` 的返回值。

    ⚠️ **两侧刻意不同源**（硬规矩 #35）：期望侧是三个 ``DEFAULT_*`` 常量，
    被测侧是 :func:`throttle` 在「三个环境变量都没设」时的解析结果。
    只钉常量的话，「常量是 5、而 :func:`throttle` 没读它」是绿的；
    只钉解析结果的话，「常量被改成 3」是绿的。两拍合起来才封住。
    ⚠️ 口径与 ``tests/auth/test_passwords.py`` 的
    ``test_the_production_default_iterations_is_at_least_the_owasp_floor`` 逐字相同。
    """
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    assert (DEFAULT_MAX_FAILS, DEFAULT_WINDOW_MINUTES, DEFAULT_LOCK_MINUTES) == (5, 15, 15)
    assert throttle() == LoginThrottle(
        max_fails=DEFAULT_MAX_FAILS,
        window=dt.timedelta(minutes=DEFAULT_WINDOW_MINUTES),
        lock=dt.timedelta(minutes=DEFAULT_LOCK_MINUTES),
    )


def test_all_three_thresholds_are_overridable_each_by_its_own_environment_variable(monkeypatch):
    """三格**各自**可被自己的环境变量覆盖（派单 §1 第 2 格逐字要求）。

    ⚠️ **逐个单独设、每次只设一个**：一次性把三个都设上的话，
    「``PE_LOGIN_WINDOW_MIN`` 被写成了读 ``PE_LOGIN_LOCK_MIN``」这一类串线是看不出来的。
    """
    monkeypatch.setenv(MAX_FAILS_ENV_VAR, "3")
    assert throttle().max_fails == 3
    assert throttle().window == dt.timedelta(minutes=DEFAULT_WINDOW_MINUTES)
    assert throttle().lock == dt.timedelta(minutes=DEFAULT_LOCK_MINUTES)

    monkeypatch.delenv(MAX_FAILS_ENV_VAR)
    monkeypatch.setenv(WINDOW_MIN_ENV_VAR, "1")
    assert throttle().window == dt.timedelta(minutes=1)
    assert throttle().max_fails == DEFAULT_MAX_FAILS

    monkeypatch.delenv(WINDOW_MIN_ENV_VAR)
    monkeypatch.setenv(LOCK_MIN_ENV_VAR, "120")
    assert throttle().lock == dt.timedelta(minutes=120)
    assert throttle().window == dt.timedelta(minutes=DEFAULT_WINDOW_MINUTES)

    # ⚠️ 空字符串按「没设」处理（PowerShell 的 `$env:X = ""` 是「设了一个空值」）
    monkeypatch.setenv(LOCK_MIN_ENV_VAR, "   ")
    assert throttle().lock == dt.timedelta(minutes=DEFAULT_LOCK_MINUTES)

    # ⚠️ ``0`` 是**合法**的（= 关掉那一格），故下界是 0 而不是 1
    monkeypatch.setenv(LOCK_MIN_ENV_VAR, "0")
    assert throttle().lock == dt.timedelta(0)
    monkeypatch.setenv(WINDOW_MIN_ENV_VAR, "0")
    assert throttle().window == dt.timedelta(0)


def test_a_malformed_threshold_is_loud_not_silent(monkeypatch):
    """坏值一律 :class:`ValueError`（响亮），**不静默回落缺省**。

    ⚠️ 口径与 :func:`app.auth.passwords.iterations` 逐字相同：``app.api.errors`` 会把
    ``ValueError`` 折成 **422 ``unprocessable_value``** 并带上消息原文，于是
    「环境变量写错了一个字母」在第一次登录请求上就响，而不是静默地按 5/15/15 跑
    （那时运维看到的现象是「我明明把阈值改成 20 了，怎么还是 5 次就锁」）。

    ⚠️ ``max_fails = 0`` 单独一档：它的意思是「0 次失败就算达到阈值」，于是**每一次**
    登录都在锁里 = 谁都登录不了。故它的下界是 **1**，而两个分钟数的下界是 **0**。

    ⚠️ **逐个单独设坏值**（每次只设一个、其余两个删掉）：一次把三个都设上的话，
    :func:`throttle` 只会在**第一个**上抛，于是「``PE_LOGIN_LOCK_MIN`` 的坏值没人校验」
    这一档是看不出来的。
    """
    for name in ENV_VARS:
        for other in ENV_VARS:
            monkeypatch.delenv(other, raising=False)
        monkeypatch.setenv(name, "不是数字")
        with pytest.raises(ValueError) as excinfo:
            throttle()
        assert name in str(excinfo.value), (name, str(excinfo.value))
        # ⚠️ 报错里必须带上**收到的原文**，否则运维只看到「必须是一个整数」而不知道
        #    自己是不是设错了另一个变量
        assert "不是数字" in str(excinfo.value), str(excinfo.value)

    monkeypatch.setenv(MAX_FAILS_ENV_VAR, "0")
    with pytest.raises(ValueError) as excinfo:
        throttle()
    assert MAX_FAILS_ENV_VAR in str(excinfo.value)
    # ⚠️ 报错必须**指路**：告诉运维「要关掉限流请设 PE_LOGIN_LOCK_MIN=0」，
    #    否则他下一个动作是把 max_fails 设成一个巨大的数（表照样长）。
    assert LOCK_MIN_ENV_VAR in str(excinfo.value)

    monkeypatch.setenv(MAX_FAILS_ENV_VAR, "-1")
    with pytest.raises(ValueError):
        throttle()
    # ⚠️ 先把 max_fails 清干净：否则 throttle 会在**它**上面先抛，
    #    而本拍要验的是 lock 那一格也校验负数（红的原因会被读成「max_fails 的守卫」）。
    monkeypatch.delenv(MAX_FAILS_ENV_VAR)
    monkeypatch.setenv(LOCK_MIN_ENV_VAR, "-5")
    with pytest.raises(ValueError) as excinfo:
        throttle()
    assert LOCK_MIN_ENV_VAR in str(excinfo.value), str(excinfo.value)
    monkeypatch.setenv(LOCK_MIN_ENV_VAR, "5")
    monkeypatch.setenv(WINDOW_MIN_ENV_VAR, "-5")
    with pytest.raises(ValueError) as excinfo:
        throttle()
    assert WINDOW_MIN_ENV_VAR in str(excinfo.value), str(excinfo.value)


def test_a_wider_threshold_really_does_lock_later(session, monkeypatch):
    """**配置真的被用上了**（不是只被解析出来）：把 ``max_fails`` 抬到 3 → 2 次不锁、3 次锁。

    ⚠️ 少了本条，「:func:`throttle` 解析对了、而 :func:`is_locked` 里写死了 5」是绿的。
    那正是「阈值是配置不是代码」这句话的失效形态。
    """
    monkeypatch.setenv(MAX_FAILS_ENV_VAR, "3")
    _fail_n(session, 2)
    assert not is_locked(session, KIND, LOGIN, now=T0)
    record_failure(session, KIND, LOGIN, now=T0)
    assert is_locked(session, KIND, LOGIN, now=T0)


# ---------------------------------------------------------------------------
# ② 两条定点变异守卫（计数 / 窗口）
# ---------------------------------------------------------------------------


def test_the_count_really_gates_the_lock(session):
    """**定点变异 A**：去掉「计数」那一格 → 本条红。

    两拍，红绿同时在场（硬规矩 #50）：

    * **绿档**：``DEFAULT_MAX_FAILS - 1`` = **4** 次失败 → **不锁**。
      一个「一律锁」的实现（``return True``）当场红在这一拍；
    * **红档**：第 **5** 次失败 → **锁**。
      一个「去掉计数判断」的实现（``if counted < max_fails`` 改成恒 ``False``，
      即「只要有失败行就锁」）当场红在**绿档**那一拍；
      而一个「恒不锁」的实现（``return False``）红在本拍。

    ⚠️ 于是「计数被去掉」与「计数被写成恒真」两个方向都有拍看着，
    而本条**不睡任何时间**（全部失败都记在 :data:`T0` 上，判也判在 :data:`T0`）。
    """
    _fail_n(session, DEFAULT_MAX_FAILS - 1)
    assert failure_count(session, KIND, LOGIN, now=T0) == DEFAULT_MAX_FAILS - 1
    assert not is_locked(session, KIND, LOGIN, now=T0), "4 次失败还不该锁（绿档）"

    record_failure(session, KIND, LOGIN, now=T0)
    assert failure_count(session, KIND, LOGIN, now=T0) == DEFAULT_MAX_FAILS
    assert is_locked(session, KIND, LOGIN, now=T0), "第 5 次失败必须锁（红档）"


def test_the_window_really_gates_the_count(session):
    """**定点变异 B**：去掉「窗口」那一格 → 本条红。

    5 次失败**全部落在窗口之外**（比 ``now`` 早 ``window + 1 分钟``）：

    * 按窗口判 → 窗口内 **0** 次 → **不锁**（本条的断言）；
    * 去掉 ``at >= now - window`` → 数到 **5** 次 → 锁 → **本条红**。

    ⚠️ 并且带一个**对照拍**（否则「窗口把所有东西都过滤掉了」与「窗口是对的」
    在颜色上无法区分）：把 ``now`` 挪回到那 5 次失败之后**不到一个窗口**的时刻，
    同一个库、同一批行 → **锁**。两拍之间**只动了 ``now``**，没动库。
    """
    old = T0 - dt.timedelta(minutes=DEFAULT_WINDOW_MINUTES + 1)
    _fail_n(session, DEFAULT_MAX_FAILS, at=old)

    # ① 窗口外：不锁（去掉窗口判断的那一格会让本拍红）
    assert failure_count(session, KIND, LOGIN, now=T0) == 0
    assert not is_locked(session, KIND, LOGIN, now=T0)

    # ② 对照：把 now 挪到那批失败的**一个窗口之内** → 锁（同一批行、同一个库）
    inside = old + dt.timedelta(minutes=1)
    assert failure_count(session, KIND, LOGIN, now=inside) == DEFAULT_MAX_FAILS
    assert is_locked(session, KIND, LOGIN, now=inside)

    # ③ 边界（窗口那一侧）：恰好 ``window`` 之后那一瞬间，最老的一行**仍在窗内**
    #    （``at >= now - lookback`` 的 ``>=`` 是承重的：写成 ``>`` 的话本拍数到 4 而不是 5）
    edge = old + dt.timedelta(minutes=DEFAULT_WINDOW_MINUTES)
    assert failure_count(session, KIND, LOGIN, now=edge) == DEFAULT_MAX_FAILS
    # ⚠️ 而锁**已经解了**：锚点（= old）+ lock 恰好到点。两格的边界是同一个方向
    #    （``>=`` 算在窗内、``<`` 才算在锁内），故它们在这一刻给出「有 5 次失败、但不锁」。
    assert not is_locked(session, KIND, LOGIN, now=edge)
    # ④ 再晚一秒，那一行真的出窗了 → 计数归 0
    assert failure_count(
        session, KIND, LOGIN, now=edge + dt.timedelta(seconds=1)
    ) == 0


def test_the_lock_is_anchored_on_the_latest_failure_and_cannot_be_pushed_back(session):
    """锁**锚在最后一次被记录的失败上**，且锁定期间的尝试**不写行**、故推不后它。

    ⚠️ 这一条守的是「滑动锁」那个失效：若锁定期间也 :func:`record_failure`，
    则一个持续探测的攻击者能让这个账号**永远**锁着，而一个反复重试的**合法用户**
    也会把自己一直锁在里面——后者的失效方向是「真实用户被永久拒之门外」，
    比前者严重（:mod:`app.auth.policy` 的模块 docstring 第一节）。
    ⚠️ 本条**不能**证明端点在锁定档没写行（那是 HTTP 层的事，守卫在
    ``tests/api/test_auth_api.py``），它证明的是：**只要**没人写行，
    锁就在锚点 + ``lock`` 那一刻消失，无论中间被问过多少次。
    """
    _fail_n(session, DEFAULT_MAX_FAILS)
    assert is_locked(session, KIND, LOGIN, now=T0)

    # 锁定期间被问了 50 次（一次都不写行）→ 锚点没动
    for step in range(50):
        assert is_locked(session, KIND, LOGIN, now=T0 + dt.timedelta(seconds=step))
    assert failure_count(session, KIND, LOGIN, now=T0) == DEFAULT_MAX_FAILS

    # 到了锚点 + lock 那一刻，锁自己消失
    assert not is_locked(
        session, KIND, LOGIN, now=T0 + dt.timedelta(minutes=DEFAULT_LOCK_MINUTES)
    )


# ---------------------------------------------------------------------------
# ③ ``now`` 注入：锁满自动解锁（不睡 15 分钟）
# ---------------------------------------------------------------------------


def test_the_lock_lifts_itself_exactly_when_the_lock_period_has_elapsed(session):
    """**派单 §1 第 6 格点名的那条**：锁满之后**自动**解锁，靠注入 ``now`` 走完时间线。

    四拍（逐秒递进，**一次 ``time.sleep`` 都没有**）：

    1. 第 5 次失败的那一刻 → 锁；
    2. ``lock - 1 秒`` → 仍然锁；
    3. **恰好** ``lock`` → **已经解锁**（⚠️ 边界是 ``<``，与
       :func:`app.auth.sessions.resolve` 的 ``expires_at <= current`` 同一条口径：
       边界那一瞬间算「已过」。写成 ``<=`` 的话本拍红）；
    4. 解锁之后**同一个库**上的一次成功登录照常放行（``failure_count`` 已在窗口内
       数到 5，故 ``is_locked`` 的第二个条件才是唯一的解锁依据——这一拍把它钉住）。
    """
    _fail_n(session, DEFAULT_MAX_FAILS)
    lock = dt.timedelta(minutes=DEFAULT_LOCK_MINUTES)

    assert is_locked(session, KIND, LOGIN, now=T0)
    assert is_locked(session, KIND, LOGIN, now=T0 + lock - dt.timedelta(seconds=1))
    assert not is_locked(session, KIND, LOGIN, now=T0 + lock)
    assert not is_locked(session, KIND, LOGIN, now=T0 + lock + dt.timedelta(hours=3))


def test_a_lock_period_longer_than_the_window_is_not_silently_truncated(session, monkeypatch):
    """``lock`` > ``window`` 时锁**真的**按 ``lock`` 算（回看取 ``max(window, lock)``）。

    ⚠️ 这一条守的是一个**静默失效**：若计数的回看只用 ``window``，则「窗口 15 分钟、
    锁 60 分钟」这一档下那 5 行失败会在**锁到期之前**就滑出回看范围，
    于是 ``len(recent)`` 归 0、锁被截断成 15 分钟——配置了 60、实际生效 15，
    而**没有任何一处报错**。:func:`app.auth.policy._lookback` 就是为此存在的。

    ⚠️ 而它**同时**是「``lock`` 与 ``window`` 不是同一个数、故不能互相顶替」的守卫：
    有人会觉得「窗口 15、锁 15，那用窗口当锁不就行了」并把 ``lock`` 那一格删掉——
    在缺省的 5/15/15 下两者**恰好等价**，故删掉之后缺省档一条测试都不会红。
    把 ``lock`` 抬到 60 分钟就把两格分开了。

    ⚠️ **本条不靠 monkeypatch 环境变量**（那一档只能设分钟数、且两格各自独立），
    而是直接换掉 :func:`app.auth.policy.throttle` 的返回值——被测的正是
    :func:`is_locked` 拿到一个 ``lock > window`` 的 :class:`LoginThrottle` 之后怎么算。
    """
    _fail_n(session, DEFAULT_MAX_FAILS)
    original = policy.throttle
    monkeypatch.setattr(
        policy, "throttle",
        lambda: LoginThrottle(max_fails=DEFAULT_MAX_FAILS,
                              window=dt.timedelta(minutes=DEFAULT_WINDOW_MINUTES),
                              lock=dt.timedelta(minutes=60)),
    )
    try:
        # ① 早就出了 15 分钟的**窗口**，而 60 分钟的**锁**还没到 → 仍然锁着。
        #    ⚠️ 这一拍就是「回看只取 window」那个实现会红的地方。
        past_window = T0 + dt.timedelta(minutes=DEFAULT_WINDOW_MINUTES + 1)
        assert is_locked(session, KIND, LOGIN, now=past_window)
        # ② 恰好锁满 60 分钟 → 解锁（边界仍是 ``<``）
        assert not is_locked(session, KIND, LOGIN, now=T0 + dt.timedelta(minutes=60))
        assert is_locked(session, KIND, LOGIN,
                         now=T0 + dt.timedelta(minutes=60) - dt.timedelta(seconds=1))
    finally:
        monkeypatch.setattr(policy, "throttle", original)


# ---------------------------------------------------------------------------
# ④ 成功登录清零
# ---------------------------------------------------------------------------


def test_a_successful_login_clears_the_failure_count(session):
    """**派单 §1 第 4 格**：成功登录**清零**这个 ``(kind, login)`` 的失败计数。

    三拍：

    1. 4 次失败 → 计数 4、不锁；
    2. :func:`record_success` → 计数 **0**、失败行**一行都不剩**、且留下**恰好一行**
       ``ok=True``（:mod:`app.auth.policy` 的 ``record_success`` docstring 交代了
       为什么留这一行：删完就无从区分「从来没失败过」与「失败了但被清了」）；
    3. 清零之后再连打 4 次 → 仍然不锁（**从零开始数**，不是从 4 继续）。
       ⚠️ 少了本拍，「``record_success`` 只删了 ``at`` 最早的几行」这类实现是绿的。
    """
    _fail_n(session, DEFAULT_MAX_FAILS - 1)
    assert failure_count(session, KIND, LOGIN, now=T0) == DEFAULT_MAX_FAILS - 1

    record_success(session, KIND, LOGIN, now=T0 + dt.timedelta(seconds=1))

    assert failure_count(session, KIND, LOGIN, now=T0) == 0
    assert not is_locked(session, KIND, LOGIN, now=T0)
    rows = session.scalars(select(LoginAttempt)).all()
    assert len(rows) == 1, rows
    assert rows[0].ok is True

    _fail_n(session, DEFAULT_MAX_FAILS - 1, at=T0 + dt.timedelta(seconds=2))
    assert failure_count(session, KIND, LOGIN, now=T0 + dt.timedelta(seconds=2)) == \
        DEFAULT_MAX_FAILS - 1
    assert not is_locked(session, KIND, LOGIN, now=T0 + dt.timedelta(seconds=2))


def test_clearing_one_identity_leaves_the_other_one_alone(session):
    """清零是**按 ``(kind, login)``** 的：别人的计数器一行都不动。

    ⚠️ 这一条守的是「``clear_failures`` 的 ``WHERE`` 少写一格」——最坏的一档是
    少写 ``kind``（于是「学号 1」的成功登录会清掉「工号 1」的计数器），
    而它在本仓今天**不可达**（学号与工号的取值域不相交），故只有本条看着它。
    """
    _fail_n(session, DEFAULT_MAX_FAILS, kind="student", login="S1")
    _fail_n(session, DEFAULT_MAX_FAILS, kind="teacher", login="S1")
    _fail_n(session, DEFAULT_MAX_FAILS, kind="student", login="S2")

    record_success(session, "student", "S1", now=T0)

    assert failure_count(session, "student", "S1", now=T0) == 0
    assert failure_count(session, "teacher", "S1", now=T0) == DEFAULT_MAX_FAILS
    assert is_locked(session, "teacher", "S1", now=T0)
    assert failure_count(session, "student", "S2", now=T0) == DEFAULT_MAX_FAILS
    assert is_locked(session, "student", "S2", now=T0)


def test_the_kind_is_part_of_the_key(session):
    """``(kind, login)`` 两格**都**在键里：同一个串在两个 kind 下是两个计数器。

    ⚠️ 学号与工号的取值域今天不相交（``2023120001`` vs ``T0001``），故少了 ``kind``
    这一格在本仓**看不出区别**——那正是它会被「顺手简化」掉的原因，
    而简化的后果是「一个叫 ``1`` 的学号」与「一个叫 ``1`` 的工号」共用一个计数器。
    ⚠️ **本条刻意用同一个串 ``"1"`` 当两个 kind 的 login**：那正是「取值域不相交」
    这个数据事实**不成立**时的形状，故它验的是 schema 而不是数据。
    """
    # 学生那一侧打到 4 次（差一次就锁），教师那一侧一次都没有
    _fail_n(session, DEFAULT_MAX_FAILS - 1, kind="student", login="1")
    assert not is_locked(session, "student", "1", now=T0)
    assert not is_locked(session, "teacher", "1", now=T0)
    assert failure_count(session, "teacher", "1", now=T0) == 0

    # 教师那一侧补到 5 次 → 锁的是**教师**，学生那一侧的计数一格都没动
    _fail_n(session, DEFAULT_MAX_FAILS, kind="teacher", login="1")
    assert is_locked(session, "teacher", "1", now=T0)
    assert not is_locked(session, "student", "1", now=T0), "教师那一格串到学生上来了"
    assert failure_count(session, "student", "1", now=T0) == DEFAULT_MAX_FAILS - 1

    # 教师那一侧清零 → 学生那一侧的 4 次**仍然在**（没有被顺手一起清掉）
    record_success(session, "teacher", "1", now=T0)
    assert failure_count(session, "teacher", "1", now=T0) == 0
    assert failure_count(session, "student", "1", now=T0) == DEFAULT_MAX_FAILS - 1


# ---------------------------------------------------------------------------
# ⑤ 落库与口径
# ---------------------------------------------------------------------------


def test_record_failure_commits_so_the_count_survives_a_second_session():
    """:func:`record_failure` **自己 commit**：换一个 ``Session`` 仍然数得到。

    ⚠️ 这一条守的是限流最阴的一档失效：:func:`app.api.deps.get_db` 刻意**不** commit
    （「什么时候算一个工作单元结束了」只有端点知道），而它在请求结束时 ``close()``
    ——**未提交的事务会被回滚**。于是「不 commit」的实现表现为：每一次登录失败都写了行、
    每一行都在请求结束时被回滚、计数器**恒为 0**、限流**恒不生效**，
    而**没有任何一处报错**。口径与 :func:`app.auth.sessions.issue` 逐字相同。
    """
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    with Session(eng) as first:
        _fail_n(first, DEFAULT_MAX_FAILS)
    with Session(eng) as second:
        assert failure_count(second, KIND, LOGIN, now=T0) == DEFAULT_MAX_FAILS
        assert is_locked(second, KIND, LOGIN, now=T0)
    eng.dispose()


def test_the_recorded_timestamp_is_naive_local_time_and_round_trips(session):
    """``login_attempt.at`` 是 **naive** 本地时刻，且缺省时钟与判定用的是**同一个**口径。

    ⚠️ **这一格是本表最容易错的地方**（:class:`app.db.models.auth.LoginAttempt` 的
    ``at`` 列注释）：SQLite 没有时区类型，而库里其余全部 ``DateTime`` 列存的是
    naive **本地**时间。写 ``dt.datetime.utcnow()`` 的话两侧差 8 小时，
    于是「窗口起点」永远在未来 → 限流**恒不生效**、且没有任何一处报错。

    四拍：

    1. 注入的 ``now`` **逐字**落到那一列上（故本模块自己不取时钟）；
    2. ``at.tzinfo is None``（naive）；
    3. **缺省时钟**写下的行，**缺省时钟**判得出来（自洽）；
    4. 缺省时钟与 :func:`app.auth.sessions.now` 在**一分钟之内**（两者同源）。
       ⚠️ **本机时区是 ``Asia/Shanghai``（+08:00）时第 4 拍才有牙**：在一个 UTC 机器上
       「本地」与「UTC」是同一个数，故它退化成一条恒绿的断言。如实记录（硬规矩 #39）。
       ⚠️ 而「两侧都用 UTC」在第 3 拍上也是自洽的，故第 3 拍挡不住「整体换成 UTC」
       ——那在本表上**不是失效**（本列只有本模块读写，自洽就够）；
       它之所以仍然不该那么写，是因为库里**其余**列是本地时刻，
       而运维拿 ``sqlite3`` 直接看这张表时会看到一堆差 8 小时的行。
    """
    record_failure(session, KIND, LOGIN, now=T0)
    row = session.scalar(select(LoginAttempt).where(LoginAttempt.ok.is_(False)))
    assert row.at == T0
    assert row.at.tzinfo is None

    # ③④ 缺省时钟那一档（不传 now）
    record_failure(session, KIND, LOGIN)
    # ⚠️ 只数得到刚写的那一行：:data:`T0` 是 2025-10-12，早已在回看窗口之外。
    #    于是本拍同时证明「缺省时钟不是 T0」与「缺省时钟与缺省判定自洽」。
    assert failure_count(session, KIND, LOGIN) == 1
    written = session.scalar(
        select(LoginAttempt.at).order_by(LoginAttempt.id.desc())
    )
    assert written.tzinfo is None
    assert abs(session_now() - written) < dt.timedelta(minutes=1)


def test_the_ip_column_is_optional_and_carries_what_the_caller_handed_in(session):
    """``ip`` 可空、且不参与判定：给 / 不给，锁的行为逐字相同。

    ⚠️ **它刻意不进限流键**：进的话攻击者换一个出口 IP 就绕过了整个机制
    （:class:`app.db.models.auth.LoginAttempt` 的 ``ip`` 列注释）。本条把「不参与」
    写成可执行的：两批失败各带一个不同的 IP，合起来仍然算 5 次。
    """
    for index in range(DEFAULT_MAX_FAILS):
        record_failure(session, KIND, LOGIN, ip="10.0.0.%d" % index, now=T0)
    assert is_locked(session, KIND, LOGIN, now=T0)

    record_success(session, KIND, LOGIN, ip=None, now=T0)
    assert failure_count(session, KIND, LOGIN, now=T0) == 0
    row = session.scalar(select(LoginAttempt))
    assert row.ip is None and row.ok is True


# ---------------------------------------------------------------------------
# ⑥ 表本身的形状（CHECK 有牙 / 复合索引的列序）
# ---------------------------------------------------------------------------


def test_the_kind_check_constraint_has_teeth(session):
    """``ck_login_attempt_kind`` 在 SQL 层真的挡得住（不只是写在 DDL 里好看）。

    ⚠️ 本仓约定 2 是「枚举取值域**两处**设防」，而 SQL 那一半在
    ``create_all`` 的内存库上**默认是关的**（SQLite 的 CHECK 是开的，外键才需要
    ``PRAGMA``），故本条直接验：写一个取值域之外的 ``kind`` 必须被数据库自己拒收。
    """
    assert LoginAttempt.KINDS == {"student", "teacher"}
    session.add(LoginAttempt(kind="parent", login="X", ok=False, at=T0))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_the_composite_index_has_the_documented_column_order():
    """``ix_login_attempt_kind_login_at`` 的列序是 ``(kind, login, at)``——**范围列在最后**。

    ⚠️ **列序是承重的、而它不会自己报错**：SQLite 的复合索引只能用到
    「从左到右连续的那几列等值 + 紧随的一列范围」。反过来的 ``(at, kind, login)``
    只用得到 ``at``，于是「这个标识最近 15 分钟失败了几次」退化成一次范围扫描 +
    逐行过滤——而本表是**单调增长**的（原型没有清理任务）。
    失效形态是「限流越来越慢」，没有人会把它归因到索引列序。
    """
    indexes = {index.name: index for index in LoginAttempt.__table__.indexes}
    assert sorted(indexes) == ["ix_login_attempt_kind_login_at"]
    columns = [column.name for column in indexes["ix_login_attempt_kind_login_at"].columns]
    assert columns == ["kind", "login", "at"], columns
    assert indexes["ix_login_attempt_kind_login_at"].unique is False


# ---------------------------------------------------------------------------
# ⑦ Plan 06 Task 10：绑定那一组阈值 + 限流键的「用途」那一维
# ---------------------------------------------------------------------------


def test_the_default_bind_threshold_is_three_fails_in_a_fifteen_minute_window_locking_for_sixty(
        monkeypatch):
    """绑定那一组的缺省三格是 **3 / 15 / 60**，且钉的是**字面量**。

    ⚠️ 与 :func:`test_the_default_threshold_is_five_fails_in_a_fifteen_minute_window_locking_for_fifteen`
    **逐字同一条口径**（两侧不同源：期望侧是三个 ``DEFAULT_BIND_*`` 常量，
    被测侧是 :func:`app.auth.policy.bind_throttle` 在「三个环境变量都没设」时的解析结果）。
    ⚠️ 只钉常量的话，「常量是 3、而 ``bind_throttle`` 没读它」是绿的；
    只钉解析结果的话，「常量被改成 5（= 与登录一样松）」是绿的。两拍合起来才封住。
    """
    for name in BIND_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    assert (
        policy.DEFAULT_BIND_MAX_FAILS,
        policy.DEFAULT_BIND_WINDOW_MINUTES,
        policy.DEFAULT_BIND_LOCK_MINUTES,
    ) == (3, 15, 60)
    assert policy.bind_throttle() == LoginThrottle(
        max_fails=3,
        window=dt.timedelta(minutes=15),
        lock=dt.timedelta(minutes=60),
    )


def test_the_bind_threshold_is_stricter_than_the_login_one():
    """**派单 §2.2 逐字要求**「缺省应当比登录更严」的可执行形式：三个数逐个比。

    ⚠️ 「更严」被拆成三条**可判定**的比较，而不是一句散文：

    * ``max_fails`` 更小（3 < 5）⇒ 更少的猜测预算；
    * ``lock`` 更长（60 > 15）⇒ 每一批猜测之间等得更久；
    * ⇒ **一天能试的次数**更少（``24 h / lock × max_fails``：72 < 480），
      而那才是「一个账号一天内被猜中的概率」的分母。⚠️ 本条**直接算这个数**并断它，
      于是「把 lock 抬长而把 max_fails 抬得更高」这种**看着更严、其实更松**的改动
      会当场红。

    ⚠️ ``window`` 刻意**不比**（两组都是 15）：回看窗口是
    :func:`app.auth.policy._lookback` = ``max(window, lock)``，故绑定那一档的实际回看
    是 **60** 分钟（= 它的 ``lock``），已经比登录那一档的 15 分钟宽 ——
    而「回看更宽」在限流上是**多锁、不少锁**，失效方向安全（那个函数的 docstring 逐字写了）。
    """
    login, bind = throttle(), policy.bind_throttle()
    assert bind.max_fails < login.max_fails, (bind.max_fails, login.max_fails)
    assert bind.lock > login.lock, (bind.lock, login.lock)

    def per_day(policy_) -> float:
        return (dt.timedelta(hours=24) / policy_.lock) * policy_.max_fails

    assert per_day(bind) == 72.0, per_day(bind)
    assert per_day(login) == 480.0, per_day(login)
    assert per_day(bind) < per_day(login)


def test_all_three_bind_thresholds_are_overridable_each_by_its_own_environment_variable(
        monkeypatch):
    """绑定那一组的三格**各自**能被**自己的**环境变量改，且不串到登录那一组。

    ⚠️ 三拍逐个设、逐个断，而**每一拍都顺带断登录那一组没变**：
    少了后半句，「``PE_BIND_MAX_FAILS`` 被写成读 ``PE_LOGIN_MAX_FAILS``」这一类串线
    是看不出来的（两组会一起变，于是「绑定那一组能被改」这句话仍然成立）。
    ⚠️ 而反方向的串线（``PE_LOGIN_*`` 改到了绑定那一组）由
    :func:`test_the_bind_and_login_thresholds_are_not_cross_wired` 钉。
    """
    monkeypatch.setenv("PE_BIND_MAX_FAILS", "2")
    assert policy.bind_throttle().max_fails == 2
    assert policy.bind_throttle().window == dt.timedelta(minutes=15)
    assert policy.bind_throttle().lock == dt.timedelta(minutes=60)
    assert throttle() == LoginThrottle(
        max_fails=5, window=dt.timedelta(minutes=15), lock=dt.timedelta(minutes=15)
    )

    monkeypatch.delenv("PE_BIND_MAX_FAILS")
    monkeypatch.setenv("PE_BIND_WINDOW_MIN", "1")
    assert policy.bind_throttle().window == dt.timedelta(minutes=1)
    assert policy.bind_throttle().max_fails == 3
    assert throttle().window == dt.timedelta(minutes=15)

    monkeypatch.delenv("PE_BIND_WINDOW_MIN")
    monkeypatch.setenv("PE_BIND_LOCK_MIN", "0")
    assert policy.bind_throttle().lock == dt.timedelta(0)
    assert throttle().lock == dt.timedelta(minutes=15)


def test_a_bad_bind_threshold_value_fails_loudly_and_names_its_own_variable(monkeypatch):
    """绑定那一组的坏值也**响亮**，且报错点名的是**它自己那一个**变量。

    ⚠️ 它同时钉住「两组共用一份解析」这件事**没有**把报错文本弄混：
    三个 ``PE_BIND_*`` 各自被设成坏值时，报错里必须出现**那一个**变量名
    （一个把 ``max_var`` 写死成 ``PE_LOGIN_MAX_FAILS`` 的复用会让本条红在
    「运维被指向了一个他没设过的变量」上）。
    ⚠️ 而 ``max_fails = 0`` 那一档的报错还必须**指路**「要关掉限流请把
    ``PE_BIND_LOCK_MIN`` 设成 0」（与登录那一格逐字同一条理由）。
    """
    monkeypatch.setenv("PE_BIND_MAX_FAILS", "不是数字")
    with pytest.raises(ValueError) as excinfo:
        policy.bind_throttle()
    assert "PE_BIND_MAX_FAILS" in str(excinfo.value), str(excinfo.value)
    assert "不是数字" in str(excinfo.value), str(excinfo.value)

    monkeypatch.setenv("PE_BIND_MAX_FAILS", "0")
    with pytest.raises(ValueError) as excinfo:
        policy.bind_throttle()
    assert "PE_BIND_MAX_FAILS" in str(excinfo.value)
    assert "PE_BIND_LOCK_MIN" in str(excinfo.value), str(excinfo.value)

    monkeypatch.delenv("PE_BIND_MAX_FAILS")
    monkeypatch.setenv("PE_BIND_LOCK_MIN", "-5")
    with pytest.raises(ValueError) as excinfo:
        policy.bind_throttle()
    assert "PE_BIND_LOCK_MIN" in str(excinfo.value), str(excinfo.value)

    monkeypatch.delenv("PE_BIND_LOCK_MIN")
    monkeypatch.setenv("PE_BIND_WINDOW_MIN", "-5")
    with pytest.raises(ValueError) as excinfo:
        policy.bind_throttle()
    assert "PE_BIND_WINDOW_MIN" in str(excinfo.value), str(excinfo.value)


def test_the_purpose_dimension_lives_in_the_key_and_leaves_the_login_key_untouched():
    """「用途」那一维**编进键的字符串里**，而**登录那一档的键逐字不变**。

    ⚠️ 两拍各自挡一件事：

    ① 映射本身（``login`` → 裸串、``bind`` → ``bind:`` 前缀）——它是
      :data:`app.auth.policy._KEY_PREFIX_BY_PURPOSE` 的**字面**复读（硬规矩 #35）。
    ② ⚠️⚠️ **登录那一档的键不带任何前缀**：那让 Plan 06 Task 3 起库里已有的
      那些行**不换键**。若给它也加一个前缀（例如 ``login:``），则升级那一刻
      所有正在被锁的账号会**当场解开**、而所有历史失败行会变成一批没人再读的孤儿
      ——两者都是静默的，故必须钉住。

    ⚠️ 五个动作**一律**经 :func:`app.auth.policy._key`（③ 那一拍用 AST 数它：
    **恰好 5 次调用**），故「哪一处忘了把用途编进键」不可能只发生在其中一处。
    """
    assert policy._key(policy.PURPOSE_LOGIN, LOGIN) == LOGIN
    assert policy._key(policy.PURPOSE_BIND, LOGIN) == f"bind:{LOGIN}"
    assert sorted(policy.PURPOSES) == ["bind", "login"]

    # ③ 五个动作各自经 _key 一次（AST 数调用点）。⚠️ 其中三个是 SQL 的 ``WHERE``
    #    （``LoginAttempt.login == _key(...)``）、两个是 ORM 的构造实参
    #    （``LoginAttempt(login=_key(...))``），故两拍各数一半：
    #    少了后一拍，「写行的那两处忘了编键」是绿的（而那两处正是**污染源**）。
    import ast
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2] / "app" / "auth" / "policy.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_key"
    ]
    assert len(calls) == 5, (
        f"_key 的调用点实测 {len(calls)} 处而不是 5 处（五个动作各一次）"
    )
    compared = [
        node.comparators[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Attribute)
        and node.left.attr == "login"
    ]
    assert len(compared) == 3, f"三处 WHERE 里比对 login 的，实测 {len(compared)} 处"
    assert all(
        isinstance(item, ast.Call) and getattr(item.func, "id", None) == "_key"
        for item in compared
    ), [ast.dump(item) for item in compared]
    keywords = [
        keyword.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "LoginAttempt"
        for keyword in node.keywords
        if keyword.arg == "login"
    ]
    assert len(keywords) == 2, f"两处构造 LoginAttempt 的 login=，实测 {len(keywords)} 处"
    assert all(
        isinstance(item, ast.Call) and getattr(item.func, "id", None) == "_key"
        for item in keywords
    ), [ast.dump(item) for item in keywords]


def test_an_unknown_purpose_fails_loudly_in_all_five_actions(session):
    """一个不认识的 ``purpose`` 在**五个**动作上都**响亮地**抛（不是静默地共用一个键）。

    ⚠️ 失效形态是具体的：一个写错的 ``purpose``（例如 ``"binding"``）若被静默接受，
    它会得到一个**没人共享**的键（于是限流恒不生效），或恰好撞上另一个用途的键
    （于是两个用途共用一个计数器 = 把限流变成拒绝服务）。两档都没有报错。
    ⚠️ 五个动作逐个打一遍：只测其中一个的话，另一个漏掉校验也照样全绿
    （口径同 ``tests/api/test_auth_api.py`` 里「两个依赖各测一次」那一条）。
    """
    with pytest.raises(ValueError) as excinfo:
        failure_count(session, KIND, LOGIN, purpose="binding")
    assert "binding" in str(excinfo.value)
    assert "bind" in str(excinfo.value) and "login" in str(excinfo.value)

    with pytest.raises(ValueError):
        is_locked(session, KIND, LOGIN, purpose="binding")
    with pytest.raises(ValueError):
        record_failure(session, KIND, LOGIN, purpose="binding")
    with pytest.raises(ValueError):
        record_success(session, KIND, LOGIN, purpose="binding")
    with pytest.raises(ValueError):
        policy.clear_failures(session, KIND, LOGIN, purpose="binding")

    # ⚠️ 反空转：两个**合法**的取值在五个动作上都不抛
    for purpose in sorted(policy.PURPOSES):
        assert failure_count(session, KIND, LOGIN, purpose=purpose) == 0
        assert is_locked(session, KIND, LOGIN, purpose=purpose) is False


def test_the_two_purposes_never_share_a_counter(session):
    """⚠️⚠️ **交叉不污染**（派单 §2.7 ②：本件最容易做错的一格）。

    四拍，红绿同时在场（硬规矩 #50）：

    ① **绑定打锁 ⇒ 登录不受影响**：3 次绑定失败（= 绑定那一组的阈值）之后，
      ``is_locked(purpose=bind)`` 是 ``True`` 而 ``is_locked(purpose=login)`` 是
      ``False``，且登录那一维的失败计数是 **0**。
      ⚠️ 少了本拍的失效形态是**一次拒绝服务**：一个匿名调用方只要拿别人的学号
      乱猜出生日期，就能把那个人锁在**自己的账号**外面（而他连提示都得不到，
      因为锁定档回的是与「口令不正确」逐字相同的 401）。
    ② **登录打锁 ⇒ 绑定不受影响**：5 次登录失败之后，绑定那一维**没锁**、
      计数是 0。⚠️ 反过来的失效形态是「一个把自己口令输错五次的人绑不上口令」。
    ③ **两个计数各自独立**：绑定失败 2 次 + 登录失败 4 次 ⇒ 两个计数分别是 2 与 4，
      而两个都没锁（各自的阈值是 3 与 5）。⚠️ 本拍挡的是「键相同但阈值不同」
      那种半对的实现（它会让 ①② 在阈值边界上恰好看不出来）。
    ④ **定点变异**：把 :func:`app.auth.policy._key` 改成忽略 ``purpose``
      （``return login``）⇒ ①②③ **三拍全红**（③ 会红在「计数是 6 而不是 2 与 4」）。
      ⚠️ 本条因此是那一次变异的**唯一**绊网：五个动作各自的既有守卫
      （计数 / 窗口 / 锚点 / 清零）在「共用一个键」的实现下**全部照样绿**，
      因为它们只打一个用途。
    """
    # ① 绑定打锁 ⇒ 登录没锁
    _fail_n(session, 3, purpose=policy.PURPOSE_BIND)
    assert is_locked(session, KIND, LOGIN, purpose=policy.PURPOSE_BIND, now=T0) is True
    assert is_locked(session, KIND, LOGIN, now=T0) is False, (
        "绑定打锁把**登录**也锁了：那是把限流变成拒绝服务"
        "（一个匿名调用方拿别人的学号乱猜出生日期，就能把那个人锁在自己账号外面）"
    )
    assert failure_count(session, KIND, LOGIN, now=T0) == 0

    # ② 登录打锁 ⇒ 绑定没锁（用一个**另外的**标识，免得与 ① 的行混在一起）
    other = "S2025002"
    _fail_n(session, 5, login=other)
    assert is_locked(session, KIND, other, now=T0) is True
    assert is_locked(session, KIND, other, purpose=policy.PURPOSE_BIND, now=T0) is False, (
        "登录打锁把**绑定**也锁了：一个把自己口令输错五次的人从此绑不上口令"
    )
    assert failure_count(session, KIND, other, purpose=policy.PURPOSE_BIND, now=T0) == 0

    # ③ 两个计数各自独立（都还没到自己的阈值）
    third = "S2025003"
    _fail_n(session, 2, login=third, purpose=policy.PURPOSE_BIND)
    _fail_n(session, 4, login=third)
    assert failure_count(session, KIND, third, purpose=policy.PURPOSE_BIND, now=T0) == 2
    assert failure_count(session, KIND, third, now=T0) == 4
    assert is_locked(session, KIND, third, purpose=policy.PURPOSE_BIND, now=T0) is False
    assert is_locked(session, KIND, third, now=T0) is False


def test_clearing_one_purpose_leaves_the_other_purposes_rows_alone(session):
    """**清零只清自己那一维**：一次成功的绑定不动登录的行，反之亦然。

    ⚠️ 少了这一格的失效形态是具体的（逐字见
    :func:`app.auth.policy.clear_failures` 的 docstring）：按 ``(kind, login)`` 删的话，
    一次成功的绑定会把那个人**登录**的失败行一起删掉 —— 于是「攻击者先猜错四次口令、
    随后那个人自己绑定成功」会把那四次失败**抹掉**，攻击者又能再猜五次。
    ⚠️ 两个方向各钉一拍（绑定→登录、登录→绑定）：只钉一个的话，
    另一个方向漏掉 ``purpose`` 也照样全绿。
    """
    _fail_n(session, 2, purpose=policy.PURPOSE_BIND)
    _fail_n(session, 4)
    assert failure_count(session, KIND, LOGIN, purpose=policy.PURPOSE_BIND, now=T0) == 2
    assert failure_count(session, KIND, LOGIN, now=T0) == 4

    record_success(session, KIND, LOGIN, purpose=policy.PURPOSE_BIND, now=T0)
    assert failure_count(session, KIND, LOGIN, purpose=policy.PURPOSE_BIND, now=T0) == 0
    assert failure_count(session, KIND, LOGIN, now=T0) == 4, (
        "一次成功的**绑定**把登录的失败计数一起清了"
    )

    record_success(session, KIND, LOGIN, now=T0)
    assert failure_count(session, KIND, LOGIN, now=T0) == 0
    # ⚠️ 绑定那一维此刻只剩它自己那一行 ok=True（上面那次成功留下的），失败计数是 0
    assert failure_count(session, KIND, LOGIN, purpose=policy.PURPOSE_BIND, now=T0) == 0


def test_a_successful_bind_clears_the_bind_counter(session):
    """**派单 §2.6**（成功绑定清零）在 ORM 层的那一半：2 + 1 + 2 次失败**不会**锁。

    ⚠️ 时间线刻意是「2 次失败 → 1 次成功 → 2 次失败」：一个**不清零**的实现
    会在第 5 行失败上锁（累计 4 次 ≥ 3），于是本条红在最后一拍。
    ⚠️ HTTP 那一半是 ``tests/api/test_auth_api.py`` 的
    ``test_a_successful_bind_clears_the_bind_failure_count_over_http``（两份刻意不合并）。
    """
    _fail_n(session, 2, purpose=policy.PURPOSE_BIND)
    assert is_locked(session, KIND, LOGIN, purpose=policy.PURPOSE_BIND, now=T0) is False
    record_success(session, KIND, LOGIN, purpose=policy.PURPOSE_BIND, now=T0)
    _fail_n(session, 2, purpose=policy.PURPOSE_BIND)
    assert is_locked(session, KIND, LOGIN, purpose=policy.PURPOSE_BIND, now=T0) is False
    # ⚠️ 反空转：再来**一次**失败就锁了（3 次 = 阈值）
    record_failure(session, KIND, LOGIN, purpose=policy.PURPOSE_BIND, now=T0)
    assert is_locked(session, KIND, LOGIN, purpose=policy.PURPOSE_BIND, now=T0) is True


def test_the_bind_lock_lifts_itself_exactly_when_the_bind_lock_period_has_elapsed(session):
    """绑定那一档的锁**到点自动解开**，而那个点是 **60** 分钟（不是登录的 15）。

    ⚠️ 靠注入 ``now`` 走完整条时间线，**不睡 60 分钟**（口径与
    :func:`test_the_lock_lifts_itself_exactly_when_the_lock_period_has_elapsed` 逐字相同）。
    ⚠️ 边界用 ``<``：恰好过满 60 分钟的那一刻**已经解锁**。
    ⚠️ ⚠️ 而**回看窗口是 ``max(window, lock)`` = 60 分钟**（:func:`app.auth.policy._lookback`），
    故第 1 次失败会在 ``T0 + 60min`` 那一刻滑出回看范围 —— 于是「计数不够」与「锁到期」
    两档**几乎同时**成立。⚠️ 本条把那一刻前后各取一个时刻断言，
    于是「把 ``_lookback`` 改回裸 ``window``」（= 锁被静默截断成 15 分钟）会当场红：
    ``T0 + 20min`` 那一拍会看到「计数仍然是 3、而锁已经不在了」。
    """
    _fail_n(session, 3, purpose=policy.PURPOSE_BIND)
    bind = policy.PURPOSE_BIND

    assert is_locked(session, KIND, LOGIN, purpose=bind, now=T0) is True
    # 锁满前一刻（+59 分钟）：仍然锁着
    assert is_locked(
        session, KIND, LOGIN, purpose=bind, now=T0 + dt.timedelta(minutes=59)
    ) is True
    # ⚠️ 而登录那一组在 +20 分钟就已经不锁了（它的 lock 是 15）——
    #    两组的时长**确实不同**，本拍把这件事钉住（否则「绑定读了登录那一组阈值」是绿的）
    _fail_n(session, 5, login="S2025009")
    assert is_locked(session, KIND, "S2025009", now=T0 + dt.timedelta(minutes=20)) is False
    assert is_locked(
        session, KIND, LOGIN, purpose=bind, now=T0 + dt.timedelta(minutes=20)
    ) is True, "绑定那一档的锁在 20 分钟就没了：它读的是登录那一组的 lock=15"
    # 恰好锁满那一刻（+60 分钟）：已经解开
    assert is_locked(
        session, KIND, LOGIN, purpose=bind, now=T0 + dt.timedelta(minutes=60)
    ) is False


def test_the_bind_and_login_thresholds_are_not_cross_wired(session, monkeypatch):
    """**两组阈值不串线**：改绑定那一组不动登录的行为，改登录那一组不动绑定的行为。

    ⚠️ 两拍各一个方向（少了任一拍，「:func:`app.auth.policy._policy_of` 恒返回
    ``throttle()``」这种半对的实现会绿在一半上）：

    ① ``PE_BIND_MAX_FAILS=2`` ⇒ 绑定第 **2** 次就锁、而登录**第 5 次**才锁；
    ② ``PE_LOGIN_MAX_FAILS=2`` ⇒ 登录第 **2** 次就锁、而绑定**第 3 次**才锁
      （⚠️ 这一拍同时钉住「绑定那一组没有跟着变松」）。
    """
    monkeypatch.setenv("PE_BIND_MAX_FAILS", "2")
    _fail_n(session, 2, login="S2025011", purpose=policy.PURPOSE_BIND)
    assert is_locked(session, KIND, "S2025011", purpose=policy.PURPOSE_BIND, now=T0) is True
    _fail_n(session, 4, login="S2025012")
    assert is_locked(session, KIND, "S2025012", now=T0) is False
    record_failure(session, KIND, "S2025012", now=T0)
    assert is_locked(session, KIND, "S2025012", now=T0) is True

    monkeypatch.delenv("PE_BIND_MAX_FAILS")
    monkeypatch.setenv("PE_LOGIN_MAX_FAILS", "2")
    _fail_n(session, 2, login="S2025013")
    assert is_locked(session, KIND, "S2025013", now=T0) is True
    _fail_n(session, 2, login="S2025014", purpose=policy.PURPOSE_BIND)
    assert is_locked(
        session, KIND, "S2025014", purpose=policy.PURPOSE_BIND, now=T0
    ) is False, "绑定那一组跟着 PE_LOGIN_MAX_FAILS 变松了：两组阈值串线"
    record_failure(session, KIND, "S2025014", purpose=policy.PURPOSE_BIND, now=T0)
    assert is_locked(
        session, KIND, "S2025014", purpose=policy.PURPOSE_BIND, now=T0
    ) is True

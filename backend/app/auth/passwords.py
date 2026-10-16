"""口令哈希：PBKDF2-SHA256 的**自描述串**（Plan 05A §2.3 采纳的第 1/2/3/4 条工程决定）。

--------------------------------------------------------------------------
存储格式：``pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>``
--------------------------------------------------------------------------

**自描述是为了将来能换算式而不做数据迁移**：换成 argon2 时，旧串仍然能被识别
（第一段就是算式名）与校验（第二、三段给出重算它所需的全部参数），
于是「升级哈希算式」变成一次**登录时顺手重哈希**，而不是一次全表停机迁移。
⚠️ 因此 :func:`verify_password` **必须先解析算式名与迭代次数、再用它们重算**，
不要写死任何一个参数——写死 ``600000`` 的话，一次「把迭代次数抬到 100 万」的运维动作
会让**全部既有口令当场失效**（重算出来的摘要对不上），而失效的形状是「所有人都登录不了」，
不是「一条报错」。

分隔符是 ``$``（与 passlib / Django 的既有惯例同一个），四段固定、不含转义：
base64 的标准字母表是 ``A–Z a–z 0–9 + / =``，**不含 ``$``**，故 ``split("$")``
无歧义，段数不等于 4 就是坏串。

--------------------------------------------------------------------------
⚠️ 迭代次数：生产缺省 **600 000**，测试里 **100 000**
--------------------------------------------------------------------------

600 000 是 OWASP 2023 对 PBKDF2-SHA256 的建议值。**测试里必须调低**，否则每条碰口令的
测试都要 ~0.3 s，套件会从 2 分钟变成半小时——而「调低了忘了调回来」是**静默的**
（生产上只是登录慢一点，没有任何测试会红）。故：

* 生产缺省值是 :data:`PBKDF2_DEFAULT_ITERATIONS` 这个**字面量**；
* 运行时可被环境变量 :data:`PBKDF2_ITERATIONS_ENV_VAR` 覆盖（``tests/conftest.py``
  设成 ``100000``）；
  ⚠️⚠️ **那个测试值自 Plan 06 Task 12（C2）起是 100 000、不再是 1 000**：本波给
  :func:`verify_password` 加了一个**下界**（:data:`PBKDF2_MIN_VERIFY_ITERATIONS`，
  逐字理由见下面那一节），而 1 000 在下界之外 —— 于是「测试进程哈希出来的串自己验不过」。
  ⚠️ 取 100 000 而不是别的数是**实测**出来的两格：① 它恰好等于演示库那一个值
  （``backend/scripts/demo_bootstrap.py`` 的 ``DEMO_PBKDF2_ITERATIONS``，
  spec §13 也逐字写着「演示库哈希用的 PBKDF2_ITERATIONS 是演示值 100 000」），
  故测试进程与演示库从此**同一个工作量**；② 全套件从 159.5 s 变成 161.7 s
  （**+2.25 s / +1.4%**，本机亲跑），因为碰口令的调用实测只有约 45 次。
* ⚠️ **守卫钉住那个字面量**，不是钉 :func:`iterations` 的返回值：
  ``tests/auth/test_passwords.py::test_the_production_default_iterations_is_at_least_the_owasp_floor``
  断言 ``PBKDF2_DEFAULT_ITERATIONS >= 600_000``，并另外用 ``monkeypatch.delenv``
  断言「环境变量没设时 :func:`iterations` **就是**那个字面量」——两拍合起来才封住
  「常量对、但解析函数没读它」这一格。

--------------------------------------------------------------------------
⚠️⚠️ 迭代次数的**上下界**：串里那一段不是可信输入（Plan 06 Task 12 / C2）
--------------------------------------------------------------------------

:func:`verify_password` **必须**从串里读迭代次数（上一节：写死的话一次「把迭代次数
抬到 100 万」的运维动作会让全部既有口令当场失效）。⚠️ 而那一列的值来自**库**，
库可以被恢复脚本、人工 ``UPDATE``、或一次损坏的备份写过 —— 于是「串里那一段」
是一个**半可信输入**，而改前它对两端都**没有界**：

* **上界那一路是一格廉价的 DoS**（老终审 M6）。实测（本机、线性外推，
  三个取样点 100 000 / 200 000 / 400 000 各约 140 ns/次）：一行
  ``pbkdf2_sha256$999999999$…`` 会让**一次登录**占住一个工作线程约 **2.3–2.5 分钟**。
  ⚠️ 而它在**限流之后还是之前**决定了它能不能被限流挡住 —— 实测复核：
  :func:`app.api.routers.auth.login` 把 :func:`app.auth.policy.is_locked` 排在
  :func:`verify_password` **之前**（Task 3 的裁定：锁定档一次 PBKDF2 都不跑），
  故**已锁定**的账号不受影响，而**未锁定**的账号**第一发**就能触发。
* **下界那一路是一格降级**（离线爆破的邀请函）。⚠️ 实测改前：
  一个 ``pbkdf2_sha256$1$<盐>$<按 1 次迭代正确重算的摘要>`` 的串，
  :func:`verify_password` 回 **``True``** —— 即「把某个人的口令列换成一个
  1 次迭代的哈希」之后，那个口令在离线上一秒就能撞出来，而**在线登录照常通过**、
  没有任何一处会响。

故两个界都加在这里、而**阈值常量住在哈希模块自己**（派单逐字要求：
⚠️ **不塞进 :mod:`app.auth.policy`**，那是限流的住址；也不写第二份）：

:data:`PBKDF2_MIN_VERIFY_ITERATIONS` = **100 000**、
:data:`PBKDF2_MAX_VERIFY_ITERATIONS` = **2 000 000**（控制者裁定）。
上界取 2 000 000 的理由是「OWASP 2023 建议 600 000，给到 3.3× 以便将来提高缺省值时
不必改代码」；下界取 100 000 的理由是「它是**演示库**那一个值，也是一个
仍然抗离线的量级（约 14 ms/次 ⇒ 一秒 70 次，而不是 1 次迭代的一秒 70 万次）」。

⚠️⚠️ **两个界都是绝对值、与 :func:`iterations` 的当前配置无关**（本波的一处裁定，
逐字理由如下，因为它是本模块最容易被「顺手改成相对值」的地方）：
本模块的核心性质是「校验**不**依赖当前配置」（:func:`verify_password` 的 docstring
与 ``tests/auth/test_passwords.py`` 的
``test_verify_uses_the_iterations_recorded_in_the_string_not_the_current_setting``
各钉了一半）。⚠️ 若把下界写成 ``min(常量, iterations())``，则一次「把迭代次数抬上去」
的运维动作会让**全部既有口令当场失效**（形状是「所有人都登录不了」）——
那正是上面那一节要防的失效。故两个界一律是字面量。
⚠️ 而「运维把 :data:`PBKDF2_ITERATIONS_ENV_VAR` 设到界外」那一档由
:func:`iterations` **自己**挡（它抛 ``ValueError`` → 422，与既有的坏值口径同一条链）：
于是「配置出一个自己验不过的哈希」在**第一次哈希**上就响，而不是在第一次登录上
以「所有人都登录不了」的形状响。

⚠️ **失效方向**：越界 → :func:`verify_password` 回 ``False``（= 走既有那一档
**401 ``invalid_credentials``**）。⚠️⚠️ **刻意不新增一个可区分的码**，
理由与 Task 3 对 423/429 的改判逐字相同：一个新码就是枚举信号
（「这个账号的口令列坏了」是一个关于**服务端库状态**的比特，不该交给调用方）。
⚠️ 而它**同时写一条 ``WARNING`` 日志**（:data:`_LOGGER`）：那一档在响应上不可见，
若也不进日志，「某个人的口令列被降级了」这件事在系统里**没有任何痕迹** ——
与 :mod:`app.api.audit` 的「审计写不下去也要响亮地 ERROR」是同一条口径。
⚠️ **本模块用的是既有的日志通道**（``logging.getLogger(__name__)``，
与 :mod:`app.main` / :mod:`app.api.errors` / :mod:`app.api.audit` /
:mod:`app.pipeline` 的三处逐字同形），**没有新建一个**。
⚠️ 它**不构成一个日志洪泛面**：走到那一格需要先「标识在册**且**已绑口令」，
故一个匿名调用方打不出来；而未锁定的尝试次数本身被
:data:`app.auth.policy.DEFAULT_MAX_FAILS` 限住（锁定档连 PBKDF2 都不跑）。

⚠️ **代价（硬规矩 #39，如实记）**：一个口令列**真的**坏掉的人，
从今天起得到的是 401「口令不正确」而不是 500 —— 他自己**无从知道**是库坏了。
那一格的可见性在运维侧（日志），不在用户侧（新码就是枚举信号）。
⚠️ 而 :func:`hash_password` 那个**只给测试用**的 ``iteration_count`` 参数
**刻意不校验**这两个界：它的全部用途就是造一个「迭代段是某个特定值」的串，
而「验不过」恰恰是 :func:`verify_password` 那些守卫要造的反例
（它们用 :mod:`hashlib` 自己拼一个串，与一个坏掉的库行同形）。
⚠️ 于是「生产路径上造不出一个验不过的哈希」由 :func:`iterations` 那一档保证
（生产路径**只**经它），而不是由 :func:`hash_password` 保证。

--------------------------------------------------------------------------
⚠️ 比较必须用 :func:`hmac.compare_digest`（第 4 条），且这一条**有变异自证**
--------------------------------------------------------------------------

``==`` 在第一个不同的字节上就返回，故响应耗时与「猜对了几个字节」相关（定时攻击）。
``compare_digest`` 恒定时间。⚠️ **本模块写 ``import hmac`` + ``hmac.compare_digest(…)``
而不是 ``from hmac import compare_digest``**，这是承重的：前者让
``monkeypatch.setattr(hmac, "compare_digest", …)`` 能拦住调用，于是
「有人把它改回 ``==``」这件事**有守卫**
（``tests/auth/test_passwords.py::test_verify_password_calls_a_constant_time_comparison``
把 ``compare_digest`` 换成一个记名替身，断言真档与假档各调用它恰好一次）。
写成 ``from … import`` 的话替身拦不到，那条守卫会**假绿**——它断言的调用次数会恒为 0
而 ``assert calls == []`` 与 ``assert len(calls) == 1`` 里只有后者会红，
但红的原因会被读成「测试自己坏了」。

⚠️ **本模块不引任何新依赖**（第 1 条）：``hashlib`` / ``hmac`` / ``secrets`` /
``base64`` / ``os`` 全是标准库。Plan 01–04 全程零新增依赖，``pyproject.toml``
有 sha256 指纹测试，本计划的新增后端依赖数是 **0**。
"""

import base64
import binascii
import hashlib
import hmac
import logging
import os
import secrets

__all__ = [
    "ALGORITHM",
    "HASH_NAME",
    "KEY_BYTES",
    "MIN_PASSWORD_LENGTH",
    "PBKDF2_DEFAULT_ITERATIONS",
    "PBKDF2_ITERATIONS_ENV_VAR",
    "PBKDF2_MAX_VERIFY_ITERATIONS",
    "PBKDF2_MIN_VERIFY_ITERATIONS",
    "SALT_BYTES",
    "SEPARATOR",
    "ensure_acceptable",
    "hash_password",
    "iterations",
    "verify_password",
]

#: ⚠️ **本模块自 Plan 06 Task 12（C2）起有一个模块级 logger**。
#: 它是**既有通道**（``logging.getLogger(__name__)``，与 :mod:`app.main` /
#: :mod:`app.api.errors` / :mod:`app.api.audit` / :mod:`app.pipeline` 的三处逐字同形），
#: **不是**新建的一个。⚠️ 唯一的用途是那一档在响应上**刻意不可见**的失效
#: （:func:`verify_password` 撞见一个迭代次数越界的库行）——
#: 逐字理由见模块 docstring 的「迭代次数的上下界」那一节。
_LOGGER = logging.getLogger(__name__)

#: 自描述串第一段的字面值，也是 ``hashlib`` 那边的算式标识。
#: ⚠️ 它**同时**是「本仓今天只支持这一种算式」的登记处：将来加 argon2 时，
#: 这里是加第二个常量（``ARGON2ID = "argon2id"``）并在 :func:`verify_password`
#: 的算式分支里多一支，**不是**改这一个串（改了就读不懂全部既有口令）。
ALGORITHM = "pbkdf2_sha256"

#: :func:`hashlib.pbkdf2_hmac` 认的摘要名。它是 ``ALGORITHM`` 去掉 ``pbkdf2_`` 前缀，
#: 但**刻意不从那一个串切出来**：``ALGORITHM`` 是存进库的标识（对外的、不可变的），
#: ``HASH_NAME`` 是 hashlib 的参数（对内的、随标准库的），两者同源会让
#: 「改一个对外标识」变成「改一次算法」。
HASH_NAME = "sha256"

#: 盐的字节数。16 字节 = 128 bit，是 NIST SP 800-132 对随机盐的下限口径。
#: ⚠️ 它决定 base64 段的长度是 24 个字符（``ceil(16/3)*4``），故整串长度是
#: ``len("pbkdf2_sha256$600000$") + 24 + 1 + 44`` = **90**（实测；
#: ⚠️ 本处此前写的是 89，差一格 —— 那个 21 个字符的前缀被数成了 20），
#: 落在 ``String(255)`` 里绰绰有余（列宽留给将来更长的算式名与更多的迭代位数）。
SALT_BYTES = 16

#: 派生密钥的字节数（256 bit，与 ``HASH_NAME`` 同宽）。
#: ⚠️ :func:`verify_password` 用 ``dklen=len(want)`` 重算，故将来改宽不需要迁移：
#: 旧串里那段 base64 的长度**就是**当时的 ``KEY_BYTES``。
KEY_BYTES = 32

#: 自描述串的分隔符。base64 的标准字母表不含它，故 ``split`` 无歧义（模块 docstring）。
SEPARATOR = "$"

#: 覆盖迭代次数的环境变量名。⚠️ **它住在本模块、不住在 ``app.config``**，理由与
#: :data:`app.main.DB_URL_ENV_VAR` / :data:`app.api.routers.pipeline.CSV_DIR_ENV_VAR`
#: 逐字相同：``config.py`` 是全仓依赖图的叶子（只 import :mod:`pathlib`），
#: 给它加一个 ``import os`` 会改掉那个性质，而它持有的应当是**缺省值**、
#: 不是「本层如何在运行时覆盖缺省值」。
PBKDF2_ITERATIONS_ENV_VAR = "PBKDF2_ITERATIONS"

#: 生产缺省的迭代次数（OWASP 2023 对 PBKDF2-SHA256 的建议值）。
#: ⚠️ **这是一个字面量、不是算式**，且被守卫按 ``>= 600_000`` 钉住（模块 docstring 第二节）。
PBKDF2_DEFAULT_ITERATIONS = 600_000

#: ---------------------------------------------------------------------------
#: **迭代次数的上下界**（Plan 06 Task 12 / C2；老终审 M6）
#: ---------------------------------------------------------------------------
#:
#: ⚠️⚠️ **两个阈值住在哈希模块自己**（派单逐字要求）：它们答的是「一次 PBKDF2
#: 该跑多少圈」，而**不是**「多少次失败算一批」—— 后者是 :mod:`app.auth.policy`
#: 的三格。⚠️ 塞进 ``policy.py`` 会让「口令哈希的工作量」这件事有两个住址
#: （而 ``policy`` 今天**一个** :mod:`hashlib` 都不碰），也会让
#: :func:`verify_password` 为了读一个常量去 import 限流模块。
#: ⚠️ 也**不写第二份**：:func:`iterations` 与 :func:`verify_password` 都读这两个对象。
#:
#: 逐字理由、实测取证（999 999 999 次 ≈ 2.3–2.5 分钟 / 1 次迭代的串改前回 ``True``）
#: 与「为什么是绝对值而不是相对 :func:`iterations` 的值」住在模块 docstring 的
#: 「迭代次数的上下界」那一节。
#:
#: ⚠️ **下界 100 000 与演示库那一个值逐字相同**
#: （``backend/scripts/demo_bootstrap.py`` 的 ``DEMO_PBKDF2_ITERATIONS``）——
#: 那不是巧合而是**约束**：演示库的 63 个口令必须在界内，否则 ``demo.ps1`` 灌出来的库
#: 一个账号都登不进去（而 ``smoke.mjs`` 的 18 步会全灭）。守卫是
#: ``tests/auth/test_passwords.py`` 的
#: ``test_the_two_bounds_admit_the_production_default_and_the_demo_value``。
PBKDF2_MIN_VERIFY_ITERATIONS = 100_000

#: 上界。**2 000 000 = OWASP 建议值的 3.3×**（控制者裁定）：给「将来把缺省值抬到
#: 100 万甚至 200 万」留出余量，于是抬缺省值**不必改代码**。
#: ⚠️ 而「抬到 2 000 000 以上」那一档由 :func:`iterations` 当场拒（``ValueError`` → 422），
#: 故「配置出一个自己验不过的哈希」在第一次哈希上就响、而不是在第一次登录上
#: 以「所有人都登录不了」的形状响。
PBKDF2_MAX_VERIFY_ITERATIONS = 2_000_000

#: 口令的最短长度。⚠️ **只判长度，不判复杂度**（不要求大小写/数字/符号混排）：
#: 长度是熵的主要来源，而「必须含一个符号」只是让用户把 ``password`` 写成 ``Passw0rd!``。
#: 计划 §1 的非目标里逐字列了「图形验证码 / 登录失败锁定」，复杂度规则当时与它们是
#: 同一档（原型不做防暴力破解，故复杂度规则的收益为零、成本是真实用户被挡在门外）。
#: ⚠️⚠️ **那一档的前提在 Plan 06 Task 3 之后只对一半成立了**（Plan 07 Task 7 补记，
#: 终审 S1-2 的同族自查挖出来的）：**登录失败锁定已经做了**（同一个 ``(kind, login)``
#: 在窗口内失败到阈值就锁，逐字口径见 ``app/auth/policy.py`` 与 spec §13.4.6），
#: 图形验证码仍然不做。⚠️ 而**本条裁定不变**：复杂度规则挡的是「离线拿到哈希之后爆破」，
#: 与锁定挡的「在线试口令」不是同一件事 —— 长度 8 已经是熵的主要来源，
#: 而「必须含一个符号」只会让用户把 ``password`` 写成 ``Passw0rd!``。
#: ⚠️ 于是改后这一段不再拿「原型不做防暴力破解」当理由（那一句今天是假的）。
#: ⚠️ 前端 ``/bind`` 页会先拦一道（省一次往返），但**本函数是唯一权威**。
MIN_PASSWORD_LENGTH = 8


def _iterations_in_bounds(value: int) -> bool:
    """一个迭代次数**在不在**那两个界之内。⚠️ 它是那个区间在本模块的**唯一判据**
    （:func:`iterations` 与 :func:`verify_password` 都经它），故「配置侧的界」与
    「校验侧的界」不可能漂开 —— 漂开的失效形态是「配置放行的值校验拒收」，
    而那正是「所有人都登录不了」那一档。
    """
    return PBKDF2_MIN_VERIFY_ITERATIONS <= value <= PBKDF2_MAX_VERIFY_ITERATIONS


def iterations() -> int:
    """本次进程要用的迭代次数：环境变量 > :data:`PBKDF2_DEFAULT_ITERATIONS`。

    ⚠️ **在调用时读环境变量、不在 import 时读**：``app.main`` 的模块级
    ``app = create_app()`` 让「import 期读」等价于「必须在 import 之前设好」，
    而 :class:`~fastapi.testclient.TestClient` 的夹具是 function 级的、
    ``monkeypatch.setenv`` 发生在 import **之后**（口径与
    :func:`app.api.routers.pipeline._csv_dir` 逐字相同）。

    空字符串按「没设」处理（``strip()`` 之后判空）：``$env:PBKDF2_ITERATIONS = ""``
    在 PowerShell 里是「设了一个空值」而不是「删掉这个变量」，而 ``int("")`` 是
    ``ValueError``——在一个与真因无关的地方。

    ⚠️ 坏值抛 ``ValueError`` 而不是静默回落到缺省值：``app.api.errors`` 会把
    ``ValueError`` 折成 **422 ``unprocessable_value``** 并**带上消息原文**，
    于是「环境变量写错了一个字母」在第一次碰口令的请求上就响，而不是静默地
    用 600 000 跑（那时测试会慢得莫名其妙，而没人知道为什么）。

    ⚠️⚠️ **Plan 06 Task 12（C2）起它还判那两个界**（:func:`_iterations_in_bounds`）。
    理由是一条**静默的**失效：一个界外的配置值会让 :func:`hash_password` 造出
    :func:`verify_password` **验不过**的串，而症状出现在**登录**上
    （「所有人都登录不了」），离真因（一个环境变量）隔一整层。
    在本函数上拒掉之后，症状变成「第一次哈希就 422 + 消息点名了那个变量与那两格界」。
    ⚠️ 于是「校验不依赖配置」那条性质**没有被破坏**：本函数管的是**产出**侧，
    :func:`verify_password` 读的是**串里那一段**（它一个环境变量都不读）。
    ⚠️ ``0`` / 负数那一档**刻意保留它自己那句报错**（``必须 ≥ 1``）：那两格的成因是
    「写错了一个数」而不是「选了一个界外的工作量」，而 :mod:`hashlib` 对它们的处置
    也不同（``0`` 抛 ``ValueError``、负数派生出一个空摘要），故两句报错各答一件事。
    """
    raw = os.environ.get(PBKDF2_ITERATIONS_ENV_VAR, "").strip()
    if not raw:
        return PBKDF2_DEFAULT_ITERATIONS
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(
            f"{PBKDF2_ITERATIONS_ENV_VAR} 必须是一个正整数，收到 {raw!r}"
        ) from None
    if value < 1:
        raise ValueError(
            f"{PBKDF2_ITERATIONS_ENV_VAR} 必须 ≥ 1（0 会让 hashlib 抛 ValueError，"
            f"负数会让它派生出一个空摘要），收到 {value}"
        )
    if not _iterations_in_bounds(value):
        raise ValueError(
            f"{PBKDF2_ITERATIONS_ENV_VAR} 必须在 "
            f"[{PBKDF2_MIN_VERIFY_ITERATIONS}, {PBKDF2_MAX_VERIFY_ITERATIONS}] 之内，"
            f"收到 {value}：界外的值会造出 verify_password **验不过**的哈希"
            f"（症状是「所有人都登录不了」，离真因隔一整层），故本函数在哈希之前就拒掉它"
        )
    return value


def ensure_acceptable(plain: str) -> str:
    """口令够不够格；不够就抛带**规则原文**的 :class:`ValueError`。

    抛 ``ValueError`` 而不是 ``HTTPException``：本模块不 import ``fastapi``
    （:mod:`app.auth` 的模块 docstring 末节），而 ``ValueError`` 经
    :mod:`app.api.errors` 折成的正是计划 §3.2 要的那一档
    ——**422 ``unprocessable_value``**，消息原文照发。
    ⚠️ 于是「弱口令」与「请求体缺字段」是**两个不同的 422 code**
    （``unprocessable_value`` vs ``request_validation_failed``），
    前端按 ``code`` 分支时不必去猜。

    ``strip()`` **不参与判定**：``"        "``（8 个空格）算够长。理由是全空白口令
    在原型里不是要防的攻击面（它挡不住任何人，而拦下它只是让「我用了一串空格」
    这个真实存在的用户困惑变成一条 422），且**允许空格**是「口令可以是一句短语」
    （passphrase）这条现代建议的前提。
    """
    if len(plain) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"口令至少 {MIN_PASSWORD_LENGTH} 个字符（收到 {len(plain)} 个）。"
            f"⚠️ 本原型不做复杂度规则、也不做找回，故请自己记牢"
        )
    return plain


def hash_password(
    plain: str,
    *,
    salt: bytes | None = None,
    iteration_count: int | None = None,
) -> str:
    """明文 → 自描述串。

    两个关键字参数**只给测试用**（``salt`` 让「同一个明文两次哈希不同」这件事可以被
    钉住而不必靠概率，``iteration_count`` 让「串里那一段确实是重算时用的那一个」可验）。
    ⚠️ 它们是 keyword-only 且缺省 ``None``：生产路径上一个调用方都不传，
    于是「谁在用非缺省的盐」这个问题永远是 ``git grep "salt=" `` 能一眼看完的。

    盐用 :func:`secrets.token_bytes` 而不是 :mod:`random`：后者是梅森旋转，
    状态可以从输出反推，而盐的全部价值在于不可预测。
    """
    if salt is None:
        salt = secrets.token_bytes(SALT_BYTES)
    if iteration_count is None:
        iteration_count = iterations()
    digest = hashlib.pbkdf2_hmac(
        HASH_NAME, plain.encode("utf-8"), salt, iteration_count, dklen=KEY_BYTES
    )
    return SEPARATOR.join(
        (
            ALGORITHM,
            str(iteration_count),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        )
    )


def verify_password(plain: str, stored: str | None) -> bool:
    """明文与自描述串对不对得上。**任何形状不对都回 ``False``、绝不抛**。

    ⚠️ 「绝不抛」是承重的：``stored`` 来自数据库（``student.password_hash`` /
    ``teacher.password_hash``），而本仓**不做迁移**——库里完全可以躺着一个
    别的算式写的串（将来换 argon2 之后的旧行）、一个被人手改坏的串、或 ``NULL``
    （未绑定）。这三种情况在 HTTP 层的正确表现分别是
    「401 ``invalid_credentials``」/「401」/「403 ``password_not_bound``」，
    而**不是** 500。抛异常的话 :mod:`app.api.errors` 的兜底会把它折成 500，
    于是「一个人的口令列坏了」表现为「登录端点炸了」，离真因隔一整层。

    ⚠️ ``NULL`` 那一档**不由本函数判**：调用方（:func:`app.api.routers.auth.login`）
    先看 ``password_hash is None`` 再决定回 403 还是 401，因为两档的 code 不同
    （计划 §3.3：未绑定 403 ``password_not_bound`` vs 密码错 401 ``invalid_credentials``）。
    本函数对 ``None`` 回 ``False`` 只是「不该被调到」时的兜底。

    重算用 ``dklen=len(want)``：**串里那段 base64 的长度就是当时的 ``KEY_BYTES``**，
    故将来改宽不需要迁移（模块 docstring 第一节）。

    ⚠️⚠️ **迭代次数那一段要过两个界**（Plan 06 Task 12 / C2；:func:`_iterations_in_bounds`）。
    它来自库，而库可以被恢复脚本 / 人工 ``UPDATE`` / 一次损坏的备份写过，
    故它是一个**半可信输入**：上界外是一格廉价的 DoS（实测 999 999 999 次
    ≈ 一次登录占住一个工作线程 **2.3–2.5 分钟**），下界外是一格降级
    （实测改前：一个 ``$1$`` 的串配上按 1 次迭代正确重算的摘要**回 ``True``**）。
    ⚠️ 两档一律**回 ``False``**（= 既有那一档 401 ``invalid_credentials``）而**不是抛**：
    「绝不抛」那一段的理由对这一档同样成立（一个人的口令列坏了不该表现成端点炸了），
    而**新增一个可区分的码**同样不行（那是枚举信号，与 Task 3 对 423/429 的改判同一条理由）。
    ⚠️ 而它**写一条 ``WARNING`` 日志**：那一档在响应上刻意不可见，若也不进日志，
    「某个人的口令列被降级了」在系统里就**没有任何痕迹**。
    ⚠️⚠️ **日志里一个字符的 ``stored`` 都不放**：那个串含盐与摘要，
    它就是一份凭据（把它写进日志等于把口令哈希摊给读得到日志的人）。
    故日志只带**算式名与迭代次数**两格。⚠️ 代价（硬规矩 #39）：
    日志里看不出是**哪一个**账号（本函数的签名里没有标识，而给它加一个入参
    会让「校验」与「这是谁」两件事耦在一起）；运维按时间戳与访问日志对齐即可。

    ⚠️ 最后一步是 :func:`hmac.compare_digest`，且必须是**通过 ``hmac`` 模块属性**调用
    （理由与守卫逐字见模块 docstring 第三节）。
    """
    if not stored:
        return False
    parts = stored.split(SEPARATOR)
    if len(parts) != 4:
        return False
    algorithm, raw_iterations, raw_salt, raw_hash = parts
    if algorithm != ALGORITHM:
        # ⚠️ 今天只支持一种算式，故这一支的意思是「库里的串是别的算式写的」。
        # 将来加 argon2 时，这里是加一个 elif 分派，**不是**把上面那个 != 改成 in。
        return False
    try:
        iteration_count = int(raw_iterations)
    except ValueError:
        return False
    if not _iterations_in_bounds(iteration_count):
        # ⚠️ 这一支**同时收掉了改前那个 ``iteration_count < 1``**（0 与负数都在下界外），
        #    故「五档畸形串」的处置逐格不变（改前实测：0 / 负数 / 非数字 / 段数不对 /
        #    空串一律 ``False``），而**新增**的是两端：上界外不再跑 PBKDF2（DoS 收掉）、
        #    下界外不再接受一个降级过的哈希。
        _LOGGER.warning(
            "口令哈希的迭代次数 %s 越出 [%s, %s]，本次校验按「验身不符」处置"
            "（算式 %s）。⚠️ 这一格在响应上刻意不可见（一个新码就是枚举信号），"
            "故它是本条日志唯一的可见性：请查那一行 password_hash 是被什么写坏的"
            "（恢复脚本 / 人工 UPDATE / 损坏的备份）。",
            iteration_count,
            PBKDF2_MIN_VERIFY_ITERATIONS,
            PBKDF2_MAX_VERIFY_ITERATIONS,
            algorithm,
        )
        return False
    try:
        salt = base64.b64decode(raw_salt, validate=True)
        want = base64.b64decode(raw_hash, validate=True)
    except (binascii.Error, ValueError):
        return False
    if not salt or not want:
        # 空盐会让 pbkdf2 退化成一个无盐的纯函数（彩虹表可用），
        # 空摘要会让 compare_digest(b"", b"") 恒真。两档都当坏串。
        return False
    got = hashlib.pbkdf2_hmac(
        HASH_NAME, plain.encode("utf-8"), salt, iteration_count, dklen=len(want)
    )
    return hmac.compare_digest(got, want)

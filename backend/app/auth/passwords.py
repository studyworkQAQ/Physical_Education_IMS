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
⚠️ 迭代次数：生产缺省 **600 000**，测试里 **1 000**
--------------------------------------------------------------------------

600 000 是 OWASP 2023 对 PBKDF2-SHA256 的建议值。**测试里必须调低**，否则每条碰口令的
测试都要 ~0.3 s，套件会从 2 分钟变成半小时——而「调低了忘了调回来」是**静默的**
（生产上只是登录慢一点，没有任何测试会红）。故：

* 生产缺省值是 :data:`PBKDF2_DEFAULT_ITERATIONS` 这个**字面量**；
* 运行时可被环境变量 :data:`PBKDF2_ITERATIONS_ENV_VAR` 覆盖（``tests/conftest.py``
  设成 ``1000``）；
* ⚠️ **守卫钉住那个字面量**，不是钉 :func:`iterations` 的返回值：
  ``tests/auth/test_passwords.py::test_the_production_default_iterations_is_at_least_the_owasp_floor``
  断言 ``PBKDF2_DEFAULT_ITERATIONS >= 600_000``，并另外用 ``monkeypatch.delenv``
  断言「环境变量没设时 :func:`iterations` **就是**那个字面量」——两拍合起来才封住
  「常量对、但解析函数没读它」这一格。

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
import os
import secrets

__all__ = [
    "ALGORITHM",
    "HASH_NAME",
    "KEY_BYTES",
    "MIN_PASSWORD_LENGTH",
    "PBKDF2_DEFAULT_ITERATIONS",
    "PBKDF2_ITERATIONS_ENV_VAR",
    "SALT_BYTES",
    "SEPARATOR",
    "ensure_acceptable",
    "hash_password",
    "iterations",
    "verify_password",
]

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
#: ``len("pbkdf2_sha256$600000$") + 24 + 1 + 44`` = 89，落在 ``String(255)`` 里绰绰有余
#: （列宽留给将来更长的算式名与更多的迭代位数）。
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

#: 口令的最短长度。⚠️ **只判长度，不判复杂度**（不要求大小写/数字/符号混排）：
#: 长度是熵的主要来源，而「必须含一个符号」只是让用户把 ``password`` 写成 ``Passw0rd!``。
#: 计划 §1 的非目标里逐字列了「图形验证码 / 登录失败锁定」，复杂度规则与它们是同一档
#: （原型不做防暴力破解，故复杂度规则的收益为零、成本是真实用户被挡在门外）。
#: ⚠️ 前端 ``/bind`` 页会先拦一道（省一次往返），但**本函数是唯一权威**。
MIN_PASSWORD_LENGTH = 8


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
    if iteration_count < 1:
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

"""``app.auth.passwords`` 的守卫（Plan 05A Task 1-B）。

**两侧不同源**是这一整份文件的口径（硬规矩 #35）：期望侧一律是**字面量**
（``"pbkdf2_sha256"``、``600_000``、``"$"``、四段、24/44 个 base64 字符），
被测侧是 :mod:`app.auth.passwords` 的运行时行为。于是「把常量改了让测试跟着绿」
这件事在本文件里做不到——改常量会红在字面量那一侧。

⚠️ **本文件里有两条守卫是「变异自证」的**（硬规矩 #83）：它们守的性质
（**恒定时间**比较、**用串里记的迭代次数**重算）在今天正确的实现上都是绿的，
而在一个「看起来也对」的错实现上也是绿的——除非把错实现真的写出来跑一遍。
故那两条的 docstring 里逐字写了「把 X 改成 Y，本条会红在哪一行」。
"""
import ast
import base64
import binascii
import datetime as dt
import hashlib
import hmac
import os
import pathlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import passwords
from app.auth.passwords import (
    ALGORITHM,
    HASH_NAME,
    KEY_BYTES,
    MIN_PASSWORD_LENGTH,
    PBKDF2_DEFAULT_ITERATIONS,
    PBKDF2_ITERATIONS_ENV_VAR,
    PBKDF2_MAX_VERIFY_ITERATIONS,
    PBKDF2_MIN_VERIFY_ITERATIONS,
    SALT_BYTES,
    SEPARATOR,
    ensure_acceptable,
    hash_password,
    iterations,
    verify_password,
)
from app.db.models.organisation import Student, Teacher
from app.db.session import init_db

#: 一个够长的口令。⚠️ **刻意含一个非 ASCII 字符**：``plain.encode("utf-8")``
#: 与「按字符数算长度」是两件事，而 :func:`ensure_acceptable` 判的是
#: ``len(plain)``（字符数），哈希用的是 UTF-8 字节——两者混用会让
#: 「8 个汉字的口令」在一个实现里够长、在另一个里不够。
PLAIN = "正确的马钉书 staple-9"


@pytest.fixture()
def session():
    """建好 **26** 张表的内存库会话（用完即关的口径见 ``tests/api/conftest.py``）。"""
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    with Session(eng) as s:
        yield s


# ---------------------------------------------------------------------------
# 迭代次数：生产缺省 ≥ OWASP 的地板，且解析函数真的读那个字面量
# ---------------------------------------------------------------------------


def test_the_production_default_iterations_is_at_least_the_owasp_floor(monkeypatch):
    """**两拍**，缺一不可（计划 §2.3 第 3 条要的那条守卫）。

    ① :data:`PBKDF2_DEFAULT_ITERATIONS` **≥ 600 000**（OWASP 2023 对 PBKDF2-SHA256
       的建议值）。⚠️ 钉的是那个**字面量**，不是 :func:`iterations` 的返回值：
       ``tests/conftest.py`` 把环境变量设成 ``100000``（否则几十条碰口令的测试
       会把套件从 2 分钟拖到半小时），故返回值在测试进程里恒为 100000，
       钉它等于什么都没钉。
    ② **环境变量没设时**，:func:`iterations` 的返回值**就是**那个字面量。
       ⚠️ 少了②，「常量对、但解析函数写成了 ``return 1000``」是绿的；
       少了①，「解析函数对、但常量被调低了」是绿的。两拍合起来才封住
       「测试把它调低了、忘了调回来」这一档——而它是**静默**的
       （生产上只是登录慢一点，没有任何测试会红）。

    ⚠️ ``monkeypatch.delenv(..., raising=False)``：根 conftest 已经把它设成 ``100000``，
    故这一拍**必须先删掉**才测得到缺省档；``raising=False`` 让「本来就没设」也过。
    """
    assert PBKDF2_DEFAULT_ITERATIONS >= 600_000, (
        f"生产缺省的迭代次数是 {PBKDF2_DEFAULT_ITERATIONS}，低于 OWASP 2023 对 "
        f"PBKDF2-SHA256 建议的 600000。⚠️ 若你是为了让测试跑得快而改的它，"
        f"改错了地方：测试进程用的是环境变量 {PBKDF2_ITERATIONS_ENV_VAR}"
        f"（tests/conftest.py 已设成 100000），本字面量是**生产**的缺省值"
    )
    monkeypatch.delenv(PBKDF2_ITERATIONS_ENV_VAR, raising=False)
    assert iterations() == PBKDF2_DEFAULT_ITERATIONS


def test_iterations_reads_the_env_var_at_call_time_and_rejects_a_bad_value(monkeypatch):
    """``iterations()`` 的五档：设了界内的正整数 / 空串 / 非整数 / ``< 1`` / **界外**。

    ⚠️ **在调用时读、不在 import 时读**是承重的（口径与
    :func:`app.api.routers.pipeline._csv_dir` 逐字相同）：``app.main`` 的模块级
    ``app = create_app()`` 让「import 期读」等价于「必须在 import 之前设好」，
    而 ``monkeypatch.setenv`` 发生在 import **之后**。本条因此也是那个性质的守卫：
    它在一个已经 import 完 ``app.auth.passwords`` 的进程里改环境变量、再读回来。

    ⚠️ **空串按「没设」处理**：``$env:PBKDF2_ITERATIONS = ""`` 在 PowerShell 里是
    「设了一个空值」而不是「删掉这个变量」，而 ``int("")`` 是 ``ValueError``
    ——在一个与真因无关的地方。
    ⚠️ **坏值抛 ``ValueError`` 而不是静默回落**：``app.api.errors`` 会把它折成
    **422 ``unprocessable_value``** 并带上消息原文，于是「环境变量写错了一个字母」
    在第一次碰口令的请求上就响。静默回落到 600 000 的表现是「测试慢得莫名其妙」，
    而没人知道为什么。

    ⚠️⚠️ **末一档（界外）是 Plan 06 Task 12（C2）加的**：一个界外的配置值会让
    :func:`hash_password` 造出 :func:`verify_password` **验不过**的串，
    而症状出现在**登录**上（「所有人都登录不了」），离真因隔一整层。
    在 :func:`iterations` 上拒掉之后，症状变成「第一次哈希就 422 + 消息点名两格界」。
    ⚠️ ``0`` / ``-1`` 那一档**刻意保留它自己那句** ``≥ 1``（两档各答一件事：
    「写错了一个数」vs「选了一个界外的工作量」），故本条按 ``match`` 分别钉两句。
    """
    monkeypatch.setenv(PBKDF2_ITERATIONS_ENV_VAR, "123456")
    assert iterations() == 123456

    monkeypatch.setenv(PBKDF2_ITERATIONS_ENV_VAR, "   ")
    assert iterations() == PBKDF2_DEFAULT_ITERATIONS

    monkeypatch.setenv(PBKDF2_ITERATIONS_ENV_VAR, "")
    assert iterations() == PBKDF2_DEFAULT_ITERATIONS

    for bad in ("abc", "1e3", "12.5"):
        monkeypatch.setenv(PBKDF2_ITERATIONS_ENV_VAR, bad)
        with pytest.raises(ValueError, match=PBKDF2_ITERATIONS_ENV_VAR):
            iterations()
    for bad in ("0", "-1"):
        monkeypatch.setenv(PBKDF2_ITERATIONS_ENV_VAR, bad)
        with pytest.raises(ValueError, match="≥ 1"):
            iterations()
    # ⚠️ 两个界**各自**都试一格界外（含端点的内侧，红绿两档都在场，硬规矩 #50）。
    for bad in (
        str(PBKDF2_MIN_VERIFY_ITERATIONS - 1),
        str(PBKDF2_MAX_VERIFY_ITERATIONS + 1),
        "999999999",
    ):
        monkeypatch.setenv(PBKDF2_ITERATIONS_ENV_VAR, bad)
        with pytest.raises(ValueError, match="之内"):
            iterations()
    for good in (
        str(PBKDF2_MIN_VERIFY_ITERATIONS),
        str(PBKDF2_MAX_VERIFY_ITERATIONS),
    ):
        monkeypatch.setenv(PBKDF2_ITERATIONS_ENV_VAR, good)
        assert iterations() == int(good)


# ---------------------------------------------------------------------------
# 自描述串的格式
# ---------------------------------------------------------------------------


def test_the_stored_string_is_the_four_part_self_describing_form():
    """``pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>``，四段、逐段可对拍。

    期望侧全部是**字面量**：算式名、分隔符、盐的 base64 长度（16 字节 → 24 个字符）、
    摘要的 base64 长度（32 字节 → 44 个字符，含一个 ``=`` 填充）。
    ⚠️ 那两个长度是 ``ceil(n/3)*4`` 的结果，**不是**从 :data:`SALT_BYTES` /
    :data:`KEY_BYTES` 反推的（反推就是同源，改一个常量两边一起改、断言恒成立）。

    ⚠️ **自描述是为了将来能换算式而不做数据迁移**（计划 §2.3 第 2 条）：
    换成 argon2 时旧串仍能被识别（第一段）与校验（第二、三段给出重算所需的全部参数）。
    故本条钉的是「串里带着重算它自己所需的一切」，而不只是「串长这样」。
    """
    stored = hash_password(PLAIN, salt=b"A" * SALT_BYTES, iteration_count=4321)
    parts = stored.split(SEPARATOR)
    assert len(parts) == 4, parts
    assert parts[0] == "pbkdf2_sha256" == ALGORITHM
    assert parts[1] == "4321"
    assert parts[2] == base64.b64encode(b"A" * SALT_BYTES).decode("ascii")
    assert len(parts[2]) == 24
    assert len(parts[3]) == 44 and parts[3].endswith("=")
    # 第四段真的是「用前三段重算出来的那一个」（两侧不同源：这里自己调 hashlib）
    assert base64.b64decode(parts[3]) == hashlib.pbkdf2_hmac(
        HASH_NAME, PLAIN.encode("utf-8"), b"A" * SALT_BYTES, 4321, dklen=KEY_BYTES
    )
    assert SEPARATOR == "$"
    assert SALT_BYTES == 16 and KEY_BYTES == 32 and HASH_NAME == "sha256"


def test_the_stored_string_fits_the_column_that_holds_it():
    """生产缺省的迭代次数下，整串长度 **≤ 255**（两列的宽度）。

    ⚠️ 这一条**跑一次真的 600 000 次迭代**（~0.3 s），因为「串有多长」取决于
    迭代次数的**位数**，而本条要量的是**生产缺省**那一个位数下的长度。
    ⚠️ Plan 06 Task 12（C2）起测试进程的环境变量是 ``100000``（6 位），
    与生产缺省的 ``600000``（6 位）**同位数**，故这一格今天不再差字符；
    ⚠️ 而本条**仍然显式传** ``iteration_count=PBKDF2_DEFAULT_ITERATIONS``、
    不靠环境变量：把缺省值抬到 7 位（例如 3 000 000）时，本条会**跟着量到 7 位**，
    而一条读环境变量的版本会静默地量到旧位数 —— 那正是本条要防的假绿。
    ⚠️ 它也是「列宽是 ``String(255)``」这个决定的可执行判据：
    换 MySQL / PostgreSQL（**强制** ``VARCHAR`` 长度）时超长会被静默截断，
    而截断后的串**永远校验不过**——炸在读侧不在写侧，离真因隔一整次登录。
    """
    stored = hash_password(PLAIN, iteration_count=PBKDF2_DEFAULT_ITERATIONS)
    assert len(stored) <= 255, (len(stored), stored)
    assert stored.split(SEPARATOR)[1] == str(PBKDF2_DEFAULT_ITERATIONS)


def test_the_same_password_hashes_differently_every_time():
    """随机盐 ⇒ 同一个明文两次哈希的串不同，而两次都校验得过。

    ⚠️ 显式传 ``salt`` 的那条守卫（上面）钉的是「串里那一段是盐」，
    本条钉的是「**生产路径上**盐是随机的」——两个 keyword 参数的缺省值是 ``None``，
    而 ``None`` 那一支走 :func:`secrets.token_bytes`。少了本条，
    把缺省盐写成一个字面量（``salt=b"pepe"``）是绿的：串仍然四段、
    仍然校验得过，而全校用户的同口令会得到**同一个**哈希（彩虹表可用）。
    """
    first = hash_password(PLAIN)
    second = hash_password(PLAIN)
    assert first != second
    assert first.split(SEPARATOR)[2] != second.split(SEPARATOR)[2], "盐那一段必须不同"
    assert verify_password(PLAIN, first)
    assert verify_password(PLAIN, second)


# ---------------------------------------------------------------------------
# 校验：真档、假档、与**每一个**坏串形状
# ---------------------------------------------------------------------------


def test_verify_roundtrips_and_rejects_a_wrong_password():
    """真档 ``True``、假档 ``False``，且假档**不抛**。

    ⚠️ 三个假档各自挡一个不同的失效：差一个字符、大小写不同、
    以及「用别的明文的哈希来校验」——最后一个是「比较写成了恒真」时会绿的那一格。
    """
    stored = hash_password(PLAIN)
    assert verify_password(PLAIN, stored) is True
    assert verify_password(PLAIN[:-1], stored) is False
    assert verify_password(PLAIN.upper(), stored) is False
    assert verify_password(PLAIN, hash_password("另一个口令，同样够长")) is False


def test_verify_uses_the_iterations_recorded_in_the_string_not_the_current_setting(
    monkeypatch,
):
    """**变异自证之一**：串里记的迭代次数是重算时用的那一个，不是当前配置的那一个。

    三拍：① 用 ``123456`` 次哈希；② 把环境变量改成 ``654321``（模拟「运维把迭代次数
    抬上去了」）；③ 校验**仍然** ``True``。

    ⚠️ **把 :func:`verify_password` 里的 ``iteration_count`` 换成 ``iterations()``
    （或直接换成字面量），本条会红在③**——而那正是计划 §2.3 第 2 条点名要防的失效：
    「校验函数必须先解析算式名与迭代次数、再用它们重算，不要写死」。
    写死的后果是**一次运维动作让全部既有口令当场失效**，形状是「所有人都登录不了」，
    而不是一条报错。

    ⚠️⚠️ **两个数字自 Plan 06 Task 12（C2）起是 123456 / 654321、不再是 1234 / 4321**：
    那一波给校验加了一个**绝对**下界（:data:`PBKDF2_MIN_VERIFY_ITERATIONS`），
    而 1234 在界外 ⇒ 本条会红在③、而红的原因会被读成「串里那一段没被用上」。
    ⚠️ 换数字**不改本条的牙**：两个值都界内、且**互不相等**，故「用了配置值」与
    「用了串里那一段」仍然给出两个不同的摘要（一个 True、一个 False）。
    ⚠️ 而「界是绝对的、不随配置走」正是本条与那两条界守卫**共同**钉住的性质：
    本条钉「抬高配置不会让既有口令失效」，那两条钉「越界的库行一律拒」。

    ⚠️ 顺带钉住 ``ALGORITHM`` 那一段也是**读出来的**：一个别的算式名写的串回 ``False``
    （而不是被当成 pbkdf2 硬算）。将来加 argon2 时，那一支是加一个 ``elif`` 分派，
    **不是**把 ``!=`` 改成 ``in``（后者会让一个 argon2 串被 pbkdf2 硬算、恒 ``False``，
    于是「升级算式」变成「所有人都登录不了」，而同一个失效换了个入口）。
    """
    stored = hash_password(PLAIN, iteration_count=123456)
    assert stored.split(SEPARATOR)[1] == "123456"
    monkeypatch.setenv(PBKDF2_ITERATIONS_ENV_VAR, "654321")
    assert iterations() == 654321, "前提没成立：环境变量没被读到"
    assert verify_password(PLAIN, stored) is True
    assert verify_password("错的口令，但同样够长", stored) is False

    head, iters, salt, digest = stored.split(SEPARATOR)
    assert verify_password(PLAIN, SEPARATOR.join(("argon2id", iters, salt, digest))) is False
    assert verify_password(PLAIN, SEPARATOR.join(("PBKDF2_SHA256", iters, salt, digest))) is False


def test_verify_returns_false_for_every_malformed_shape():
    """**任何**形状不对的串都回 ``False``、**绝不抛**。

    ⚠️ 「绝不抛」是承重的：``stored`` 来自数据库，而本仓**不做迁移**——库里完全可以
    躺着一个别的算式写的串、一个被人手改坏的串、或 ``NULL``（未绑定）。
    抛出去的话 :mod:`app.api.errors` 的兜底会把它折成 **500**，于是
    「一个人的口令列坏了」表现为「登录端点炸了」，离真因隔一整层。
    正确的表现是 **401 ``invalid_credentials``**（``NULL`` 那一档是
    403 ``password_not_bound``，而它**不由本函数判**：两档的 code 不同，
    故由调用方先看 ``password_hash is None``）。

    ⚠️ 12 个形状逐个点名（硬规矩 #116：一条纪律若是以「某个具体的错误值不得出现」的
    形式写下的，守卫必须钉住它的**全部**产生路径）。最后两格尤其阴险：
    空盐会让 pbkdf2 退化成无盐的纯函数，空摘要会让 ``compare_digest(b"", b"")`` 恒真。
    """
    good = hash_password(PLAIN)
    head, iters, salt, digest = good.split(SEPARATOR)
    shapes = {
        "None": None,
        "空串": "",
        "一段": "pbkdf2_sha256",
        "三段": SEPARATOR.join((head, iters, salt)),
        "五段": SEPARATOR.join((head, iters, salt, digest, "多出来的")),
        "算式名不对": SEPARATOR.join(("bcrypt", iters, salt, digest)),
        "迭代次数不是整数": SEPARATOR.join((head, "很多", salt, digest)),
        "迭代次数是 0": SEPARATOR.join((head, "0", salt, digest)),
        "迭代次数是负数": SEPARATOR.join((head, "-1", salt, digest)),
        "盐不是 base64": SEPARATOR.join((head, iters, "!!!不是base64!!!", digest)),
        "空盐": SEPARATOR.join((head, iters, "", digest)),
        "空摘要": SEPARATOR.join((head, iters, salt, "")),
    }
    for label, stored in shapes.items():
        assert verify_password(PLAIN, stored) is False, (label, stored)
    # ⚠️ 反空转：上面那 12 格必须**真的**是坏串，而「好串也一起回 False」是
    # 让本条全绿的最省力写法（例如把 ``verify_password`` 改成 ``return False``）。
    assert verify_password(PLAIN, good) is True


def test_verify_password_calls_a_constant_time_comparison(monkeypatch):
    """**变异自证之二**：最后那一步比较走的是 :func:`hmac.compare_digest`。

    ``==`` 在第一个不同的字节上就返回，故响应耗时与「猜对了几个字节」相关（定时攻击）；
    ``compare_digest`` 恒定时间。⚠️ **这一档没有「行为面」的判据**——
    换成 ``==`` 之后 ``verify_password`` 的返回值**一模一样**，
    故任何只看返回值的守卫都是假绿的。唯一的判据是「那个函数被调用了吗」。

    ⚠️ **把 :mod:`app.auth.passwords` 里那一行 ``return hmac.compare_digest(got, want)``
    改成 ``return got == want``，本条会红在两处**（真档与假档各一处，
    ``calls == []`` 而断言要 ``len(calls) == 1``）。改回来即绿。
    ⚠️ 而这条守卫之所以**能**拦住，前提是生产代码写的是 ``import hmac`` +
    ``hmac.compare_digest(…)``（经模块属性调用）而**不是** ``from hmac import
    compare_digest``（把函数对象绑进本模块命名空间，monkeypatch 换不掉它）。
    那一格写在 :mod:`app.auth.passwords` 的模块 docstring 第三节里。

    ⚠️ 替身**仍然调真的** ``compare_digest``：本条要钉的是「它被调了」，
    不是「它的返回值被改了」，故真档必须仍然 ``True``（否则本条会顺带改掉
    上面几条的结论，红的原因就说不清了）。

    ⚠️ 比较的两个入参也一并钉住：第一个必须是**重算出来的**摘要、
    第二个必须是**串里存的**那一个。少了这半句，
    ``hmac.compare_digest(b"x", b"x")``（恒真）也能让本条绿。
    """
    stored = hash_password(PLAIN)
    want = base64.b64decode(stored.split(SEPARATOR)[3])
    calls: list[tuple[bytes, bytes]] = []
    real = hmac.compare_digest

    def spy(left, right):
        calls.append((left, right))
        return real(left, right)

    monkeypatch.setattr(hmac, "compare_digest", spy)
    assert verify_password(PLAIN, stored) is True
    assert len(calls) == 1, calls
    assert calls[0][1] == want, "第二个入参必须是串里存的那个摘要"
    assert calls[0][0] == want, "真档下重算出来的摘要必须与存的那个逐字相同"

    calls.clear()
    assert verify_password("错的口令，但同样够长", stored) is False
    assert len(calls) == 1, calls
    assert calls[0][1] == want
    assert calls[0][0] != want, "假档下重算出来的摘要必须与存的那个不同"

    # ⚠️ 坏串**不该**走到比较那一步（解析失败就返回了），故 calls 必须是空的。
    # 少了这半句，「先比较、再判格式」这种倒序实现也是绿的，
    # 而它会对一个格式都不对的串跑一次 600 000 轮 pbkdf2（一次免费的 DoS 放大器）。
    calls.clear()
    assert verify_password(PLAIN, "不是四段的串") is False
    assert calls == []


# ---------------------------------------------------------------------------
# 弱口令
# ---------------------------------------------------------------------------


def test_ensure_acceptable_rejects_a_short_password_and_names_the_rule():
    """``ValueError`` + 消息里带那个**数字**（422 ``unprocessable_value`` 的来源）。

    ⚠️ 抛 ``ValueError`` 而不是 ``HTTPException``：``app.auth`` 不 import ``fastapi``
    （:mod:`app.auth` 的模块 docstring 末节），而 ``ValueError`` 经
    :mod:`app.api.errors` 折成的正是计划 §3.2 要的那一档。
    ⚠️ 于是「弱口令」与「请求体缺字段」是**两个不同的 422 code**
    （``unprocessable_value`` vs ``request_validation_failed``），前端按 code 分支不必猜。

    ⚠️ 边界是 ``>=`` 不是 ``>``：恰好 8 个字符**够长**。
    ⚠️ ``strip()`` **不参与判定**（8 个空格够长）：理由逐字见
    :func:`ensure_acceptable` 的 docstring（passphrase 要能含空格）。
    """
    assert MIN_PASSWORD_LENGTH == 8
    assert ensure_acceptable("x" * 8) == "x" * 8
    assert ensure_acceptable(PLAIN) == PLAIN
    assert ensure_acceptable(" " * 8) == " " * 8

    for short in ("", "x", "x" * 7):
        with pytest.raises(ValueError) as excinfo:
            ensure_acceptable(short)
        message = str(excinfo.value)
        assert str(MIN_PASSWORD_LENGTH) in message, message
        assert "口令" in message, message


def test_the_credential_columns_reject_a_value_outside_their_own_domain(session):
    """⚠️ **这一条不是 ``passwords`` 的守卫**，它是「口令哈希写不进别的列」的守卫。

    :func:`hash_password` 的输出是 ASCII（base64 的标准字母表 + ``$`` + 数字），
    而 ``student.password_hash`` / ``teacher.password_hash`` 是 ``String(255)``。
    本条把「真的写进去、真的读回来、逐字相同」跑一遍——SQLite **不强制**
    ``VARCHAR`` 长度，故这一拍在今天不可能红；它存在的理由是**换后端那一天**：
    一个 ``VARCHAR(64)`` 的列会把 90 字符的串静默截断，而截断后的串永远校验不过。
    ⚠️ 于是本条同时钉住「两列的宽度 ≥ 生产串长」（``String(255)`` 那个字面量）。
    """
    stored = hash_password(PLAIN, iteration_count=PBKDF2_DEFAULT_ITERATIONS)
    student = Student(
        student_no="S2025001", name="张三", sex="male",
        birth=dt.date(2006, 3, 4), grade=1,
        password_hash=stored,
    )
    teacher = Teacher(staff_no="T0001", name="李老师", password_hash=stored)
    session.add_all([student, teacher])
    session.commit()
    assert session.get(Student, student.id).password_hash == stored
    assert session.get(Teacher, teacher.id).password_hash == stored
    assert verify_password(PLAIN, session.get(Teacher, teacher.id).password_hash)
    for table in (Student, Teacher):
        width = table.__table__.c.password_hash.type.length
        assert width is not None and width >= len(stored), (table.__tablename__, width)
    # 未绑定 ⇒ NULL，而 NULL 不等于一个哨兵串（计划 §3.3 的两档 code 靠它区分）
    assert session.get(Teacher, teacher.id).password_bound_at is None
    with pytest.raises(IntegrityError):
        session.add(Teacher(staff_no="T0002", name="x", role="校长"))
        session.commit()


def test_a_non_ascii_password_survives_the_roundtrip():
    """中文口令能用（``encode("utf-8")`` 那一格）。

    ⚠️ 本仓的用户界面是中文的，而「口令可以是中文」这件事在 ASCII-only 的实现上
    会以 ``UnicodeEncodeError`` 的形式炸在**登录**端点上（不是绑定端点，
    因为绑定时存的是哈希、登录时才重算——两处都调 ``encode``，但只有登录那一处
    是用户每天都要走的）。
    """
    for plain in ("八个中文字的口令", "パスワード八文字です", "🔒" * 8):
        stored = hash_password(plain)
        assert verify_password(plain, stored) is True
        assert verify_password(plain + " ", stored) is False


def test_the_public_surface_of_the_module_is_the_documented_one():
    """``__all__`` 逐字等于那份清单（硬规矩 #35：不从 ``dir()`` 反推）。

    ⚠️ 它守的是「本模块没有悄悄多出一个公开函数」：``app.auth`` 的 ``__all__``
    是空的、两个成员都按模块引用，故 ``passwords`` 的公开面就是
    「谁能 import 什么」这件事在本仓唯一的登记处。
    """
    assert sorted(passwords.__all__) == sorted([
        "ALGORITHM", "HASH_NAME", "KEY_BYTES", "MIN_PASSWORD_LENGTH",
        "PBKDF2_DEFAULT_ITERATIONS", "PBKDF2_ITERATIONS_ENV_VAR",
        # ⚠️ Plan 06 Task 12（C2）加的两个：迭代次数的上下界。
        #    它们是**公有面**（不是 ``_`` 前缀），因为「界是多少」这件事要能被
        #    守卫与运维文档引用；⚠️ 而判据本身住在私有的
        #    :func:`app.auth.passwords._iterations_in_bounds`（唯一住址），
        #    故本清单加的是**两个数**、不是第二份判据。
        "PBKDF2_MAX_VERIFY_ITERATIONS", "PBKDF2_MIN_VERIFY_ITERATIONS",
        "SALT_BYTES",
        "SEPARATOR", "ensure_acceptable", "hash_password", "iterations",
        "verify_password",
    ])
    for name in passwords.__all__:
        assert hasattr(passwords, name), name
    # ⚠️ 反空转：本模块**不得**导出任何 fastapi / starlette 对象
    # （app.auth 可以在没有 fastapi 的进程里被 import，见包 docstring 末节）。
    assert not hasattr(passwords, "fastapi")
    assert "fastapi" not in dir(passwords) and "starlette" not in dir(passwords)
    # binascii 是 verify_password 用来接 base64 解码失败的，它是标准库、不是导出面
    assert binascii.Error is not None


# ---------------------------------------------------------------------------
# 迭代次数的上下界（Plan 06 Task 12 / C2；老终审 M6）
# ---------------------------------------------------------------------------


def _stored_at(
    count: int, plain: str = PLAIN, salt: bytes | None = None, *, exact: bool = True
) -> str:
    """**自己拼**一个迭代段是 ``count`` 的自描述串（摘要按 ``count`` 正确重算）。

    ⚠️ 刻意**不经** :func:`hash_password`：那个函数的 ``iteration_count`` 参数虽然
    也能造出界外的串，但「一个界外的库行长什么样」这件事的真相在**库里**、
    不在本模块的产出侧 —— 本助手直接用 :mod:`hashlib` 拼，于是它与
    「一次损坏的恢复脚本写出来的那一行」**同形**（摘要是对的，只有迭代段越界）。
    ⚠️ 这一格是承重的：若摘要**不**按 ``count`` 重算，那么「越界被拒」与
    「摘要对不上被拒」在返回值上不可分辨，本组守卫就没有牙了。

    ⚠️ ``exact=False`` 那一档只给**天文的**迭代次数用（``999_999_999``）：
    真按它重算一次摘要要 **2.3 分钟**（本机实测约 140 ns/次），而那正是本组守卫
    要证明**根本不会发生**的事 —— 故那一档放一个占位摘要，牙在「PBKDF2 一次都没跑」
    那一拍上（:func:`test_verify_rejects_an_iteration_count_outside_the_two_bounds`
    的 docstring 逐字解释了为什么判据是**调用次数**而不是返回值）。
    """
    if salt is None:
        salt = b"A" * SALT_BYTES
    if exact and 1 <= count <= PBKDF2_MAX_VERIFY_ITERATIONS:
        digest = hashlib.pbkdf2_hmac(
            HASH_NAME, plain.encode("utf-8"), salt, count, dklen=KEY_BYTES
        )
    else:
        # ⚠️ 两个界**之外**的 ``count`` 一律放占位摘要：``0`` / 负数会让
        #    :mod:`hashlib` 当场抛，而一个天文数字要真算几分钟（那正是本组守卫
        #    要证明**不会发生**的事）。⚠️ 于是「摘要正确而迭代段越界」那一档
        #    由下面 ``1`` / ``1000`` / ``MIN-1`` 三格承担（三格都很便宜、
        #    且改前实测**都回 ``True``**），牙在「PBKDF2 一次都没跑」那一拍上。
        digest = b"\x00" * KEY_BYTES
    return SEPARATOR.join((
        ALGORITHM, str(count),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    ))


def test_verify_rejects_an_iteration_count_outside_the_two_bounds(monkeypatch):
    """**两个界各自的界外一律拒**，且**一次 PBKDF2 都不跑**（DoS 那一格的牙）。

    ------------------------------------------------------------------------
    ⚠️ 改前实测（本机亲跑，逐格）
    ------------------------------------------------------------------------
    * ``$999999999$`` → 改前**真跑** PBKDF2；按三个取样点
      （100 000 / 200 000 / 400 000 各约 140 ns/次）线性外推 ≈ **2.3–2.5 分钟**
      占住一个工作线程 ⇒ 一格**廉价**的 DoS（一行 UPDATE 换服务端几分钟）。
      ⚠️ 而 :func:`app.auth.policy.is_locked` 排在 :func:`verify_password` **之前**
      （``app/api/routers/auth.py`` 实测：520 行 vs 534 行），故**已锁定**的账号
      不受影响，而**未锁定**的账号**第一发**就能触发。
    * ``$1$`` 配上按 1 次迭代**正确重算**的摘要 → 改前回 **``True``**
      （离线爆破的邀请函：一行 UPDATE 就能把某个人的口令降级成一秒可撞）。
      ⚠️ ``$1000$``（改前测试进程用的那一个值）同样回 ``True`` —— 那一格是本波
      把 ``tests/conftest.py`` 抬到 ``100000`` 的原因。

    ------------------------------------------------------------------------
    ⚠️ 「不跑 PBKDF2」的判据是**调用次数**，不是耗时（与
    :func:`test_verify_password_calls_a_constant_time_comparison` 同一条口径）
    ------------------------------------------------------------------------
    耗时断言在本机与噪声同量级，而「上界外有没有真的算」是一件**可以数**的事：
    把 :func:`hashlib.pbkdf2_hmac` 换成一个记名替身，断言界外那几档**一次都没调它**。
    ⚠️ 少了这一拍，「把上界去掉」之后本条**仍然绿**（那个天文数字的串摘要对不上，
    返回值一样是 ``False``），而失效是「一次登录占住服务端几分钟」——
    一条只看返回值的守卫抓不到它。⚠️ 而替身让本条**不会真的挂几分钟**：
    去掉上界之后它当场红在计数上，而不是红在超时上。
    ⚠️ **串在装替身之前就拼好**（替身自己也会数到 :func:`_stored_at` 的那几次调用，
    那会让「一次都没跑」这一拍恒红 —— 一个假红比一个假绿更难查）。

    ⚠️ **红绿两档都在场**（硬规矩 #50）：两个界**各自的内侧端点**
    （``MIN`` 与 ``MAX``）必须**通过**（真跑 PBKDF2，两档摘要都对得上）。
    少了这一拍，「把 :func:`verify_password` 改成恒 ``False``」会让上面那一圈全绿。
    """
    outside = {
        1: _stored_at(1),
        1000: _stored_at(1000),
        PBKDF2_MIN_VERIFY_ITERATIONS - 1: _stored_at(PBKDF2_MIN_VERIFY_ITERATIONS - 1),
        PBKDF2_MAX_VERIFY_ITERATIONS + 1: _stored_at(PBKDF2_MAX_VERIFY_ITERATIONS + 1),
        # ⚠️ 这一档用占位摘要（真算一次要 2.3 分钟，逐字理由见 _stored_at）
        999_999_999: _stored_at(999_999_999, exact=False),
    }
    inside = {
        count: _stored_at(count)
        for count in (PBKDF2_MIN_VERIFY_ITERATIONS, PBKDF2_MAX_VERIFY_ITERATIONS)
    }

    calls: list[int] = []
    real = hashlib.pbkdf2_hmac

    def counted(*args, **kwargs):
        count = args[3] if len(args) > 3 else kwargs["iterations"]
        calls.append(count)
        if count > PBKDF2_MAX_VERIFY_ITERATIONS:
            # ⚠️ **安全阀**（承重的，不是省事）：本条的牙是「一次都没跑」，
            #    而在一个「把上界去掉」的变异体上**真跑** 999 999 999 次要 2.3 分钟
            #    —— 那正是本条要防的那个 DoS。故替身在界外那几档不真算、只记一次调用：
            #    变异体于是**当场红在计数上**，而不是红在超时上。
            return b"\x00" * KEY_BYTES
        return real(*args, **kwargs)

    monkeypatch.setattr(hashlib, "pbkdf2_hmac", counted)

    for count, stored in outside.items():
        calls.clear()
        assert verify_password(PLAIN, stored) is False, count
        assert verify_password("另一个口令，同样够长", stored) is False, count
        assert calls == [], f"迭代次数 {count} 越界，却真的跑了 PBKDF2 {calls}"

    # ⚠️ 反空转：界**内**的两个端点必须通过、且**真的**各跑一次 PBKDF2
    #    （两次校验 ⇒ 两次调用，而**两次都是串里那一个数**，不是配置的那一个）。
    for count, stored in inside.items():
        calls.clear()
        assert verify_password(PLAIN, stored) is True, count
        assert verify_password("另一个口令，同样够长", stored) is False, count
        assert calls == [count, count], (count, calls)


def test_an_out_of_bounds_iteration_count_logs_a_warning_carrying_no_credential(caplog):
    """越界那一档**写一条 ``WARNING``**，而那条日志里**一个字符的凭据都没有**。

    ⚠️ 派单要求「越界 → 拒绝验证 + 写一条日志/审计」，并要求先实测这一档今天
    有没有日志通道。实测：``app/auth/passwords.py`` 改前**没有** logger，
    而本仓**已经有**一条既有通道（``logging.getLogger(__name__)``，
    :mod:`app.main` / :mod:`app.api.errors` / :mod:`app.api.audit` /
    :mod:`app.pipeline` 的三处逐字同形）⇒ 本波**用它**、没有新建一个。

    ⚠️ **为什么必须有日志**：那一档在响应上**刻意不可见**（回既有的
    401 ``invalid_credentials``；一个新码就是枚举信号，与 Task 3 对 423/429 的改判
    同一条理由）。若也不进日志，「某个人的口令列被降级了」在系统里**没有任何痕迹**
    —— 与 :mod:`app.api.audit` 的「审计写不下去也要响亮地 ERROR」是同一条口径。

    ⚠️⚠️ **隐私那一拍是本条的牙**：那个串含**盐与摘要**，它就是一份凭据。
    故断言日志文本里既没有整串、也没有它的盐段与摘要段、更没有明文。
    ⚠️ 少了这一拍，「把 ``stored`` 整个塞进日志」（最省力的写法，
    因为它能告诉运维「是哪一行坏了」）会让本条绿 —— 而那等于把口令哈希
    摊给每个读得到日志的人。
    """
    stored = _stored_at(1)
    _head, iters, salt, digest = stored.split(SEPARATOR)
    with caplog.at_level("WARNING", logger=passwords.__name__):
        assert verify_password(PLAIN, stored) is False
    records = [
        record for record in caplog.records
        if record.levelname == "WARNING" and record.name == passwords.__name__
    ]
    assert len(records) == 1, [r.getMessage() for r in caplog.records]
    message = records[0].getMessage()
    # ⚠️ 运维要能从日志里读出**哪一档坏了**：迭代次数与那两格界都要在。
    assert f"迭代次数 {iters} " in message, message
    assert str(PBKDF2_MIN_VERIFY_ITERATIONS) in message, message
    assert str(PBKDF2_MAX_VERIFY_ITERATIONS) in message, message
    assert ALGORITHM in message, message
    for secret in (stored, salt, digest, PLAIN):
        assert secret not in message, f"日志里出现了凭据的一段：{secret[:12]}…"


def test_the_two_bounds_admit_the_production_default_and_the_demo_value():
    """两个界必须**装得下**本仓真实会产出的那三个迭代次数。

    ⚠️ 三格逐个点名（期望侧一律**从代码里读**，不抄数字）：

    * :data:`PBKDF2_DEFAULT_ITERATIONS`（生产缺省，600 000）；
    * **演示库**那一个值：``backend/scripts/demo_bootstrap.py`` 的
      ``DEMO_PBKDF2_ITERATIONS``。⚠️ 它用 **AST 读**、不 ``import`` 那个脚本
      （脚本在 ``backend/scripts/`` 下、不在包内，而 import 它会跑它的模块体）。
      ⚠️ 这一格是**约束**而不是巧合：演示库的 63 个口令若落在界外，
      ``demo.ps1`` 灌出来的库**一个账号都登不进去**，而 ``smoke.mjs`` 的 18 步会全灭；
    * **测试进程**那一个值（见下面那一条守卫）。

    ⚠️ 于是「把下界抬到 200 000」这一个看起来很安全的动作会当场红 ——
    而改前它会静默地把演示库与测试套件一起打死（症状离真因隔一整层）。
    """
    script = (
        pathlib.Path(__file__).resolve().parents[2] / "scripts" / "demo_bootstrap.py"
    )
    demo_values = [
        node.value.value
        for node in ast.walk(ast.parse(script.read_text(encoding="utf-8")))
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
        and target.id == "DEMO_PBKDF2_ITERATIONS"
        and isinstance(node.value, ast.Constant)
    ]
    assert len(demo_values) == 1, (script, demo_values)
    demo = demo_values[0]

    assert PBKDF2_MIN_VERIFY_ITERATIONS <= PBKDF2_DEFAULT_ITERATIONS
    assert PBKDF2_DEFAULT_ITERATIONS <= PBKDF2_MAX_VERIFY_ITERATIONS
    assert PBKDF2_MIN_VERIFY_ITERATIONS <= demo <= PBKDF2_MAX_VERIFY_ITERATIONS, (
        f"演示库用 {demo} 次迭代，落在 [{PBKDF2_MIN_VERIFY_ITERATIONS}, "
        f"{PBKDF2_MAX_VERIFY_ITERATIONS}] 之外 ⇒ demo.ps1 灌出来的库没人登得进去"
    )
    # ⚠️ 反空转：两个界确实**夹着**生产缺省（否则「抬缺省值不必改代码」那一句是假的）
    assert PBKDF2_MIN_VERIFY_ITERATIONS < PBKDF2_DEFAULT_ITERATIONS
    assert PBKDF2_MAX_VERIFY_ITERATIONS > PBKDF2_DEFAULT_ITERATIONS
    # ⚠️⚠️ **两个阈值本身按字面量钉**（口径与 ``tests/auth/test_policy.py`` 对
    #    ``DEFAULT_MAX_FAILS`` 那三格逐字相同：阈值是**决定**，不是算式，
    #    从被测侧读回来跟自己比是同源断言、什么都证明不了）。
    #    ⚠️ 少了这一拍，「把下界悄悄降到 1」是绿的 —— 而那一档正是本件要收的
    #    「离线爆破的邀请函」（改前实测：一个 ``$1$`` 的串配正确摘要回 ``True``）。
    #    ⚠️ 上界 2 000 000 = OWASP 2023 建议值 600 000 的 **3.3×**（控制者裁定：
    #    给「将来把缺省值抬上去」留余量，于是抬缺省值不必改代码）。
    assert PBKDF2_MIN_VERIFY_ITERATIONS == 100_000
    assert PBKDF2_MAX_VERIFY_ITERATIONS == 2_000_000


def test_the_test_suite_runs_at_an_iteration_count_the_verifier_admits():
    """``tests/conftest.py`` 设的那一个环境变量必须落在两个界**之内**。

    ⚠️ 本条钉的是**一处真实的耦合**：根 conftest 只 import :mod:`os`
    （它刻意不 import ``app.*``，逐字理由见那个文件的模块 docstring），
    故它写的是一个**字面量** ``"100000"`` —— 而那个数必须 ≥ 下界，
    否则「测试进程自己哈希出来的串自己验不过」，全部登录/绑定测试会红在
    一个与真因（一个环境变量）无关的地方。
    ⚠️ 于是「把下界抬上去而忘了改 conftest」由本条**当场**抓住，
    并且报错文本**指路**到那个文件。

    ⚠️ 改前实测的代价（本机亲跑）：``1000`` → ``100000`` 让全套件从 **159.5 s**
    变成 **161.7 s**（+2.25 s / +1.4%），因为碰口令的调用实测只有约 45 次。
    """
    raw = os.environ.get(PBKDF2_ITERATIONS_ENV_VAR, "")
    assert raw.strip(), "根 conftest 没把测试进程的迭代次数设上"
    configured = int(raw)
    assert PBKDF2_MIN_VERIFY_ITERATIONS <= configured <= PBKDF2_MAX_VERIFY_ITERATIONS, (
        f"tests/conftest.py 把 {PBKDF2_ITERATIONS_ENV_VAR} 设成 {configured}，"
        f"落在 [{PBKDF2_MIN_VERIFY_ITERATIONS}, {PBKDF2_MAX_VERIFY_ITERATIONS}] 之外："
        f"测试进程自己哈希出来的串会验不过（全部登录/绑定测试会红在一个与真因无关的地方）"
    )
    assert iterations() == configured

"""``app.deploy`` 的守卫：部署档位与它派生的那几格配置（Plan 06 Task 4-A）。

**这一份文件钉的是纯值**（档位怎么解析、白名单怎么切），HTTP 那一半——
「``prod`` 下 CORS 挂成什么、自检什么时候 ``raise``、匿名读不到档位」——
住在 ``tests/test_main.py``；「请求头身份通道在 ``prod`` 下被强制关」住在
``tests/api/test_auth_api.py``（它要实发一次请求）。三份刻意不合并。

--------------------------------------------------------------------------
⚠️⚠️ 本文件最要紧的一条：认不出的 ``PE_ENV`` **不许**静默落到开发档
--------------------------------------------------------------------------

:func:`test_an_unrecognised_tier_is_loud_and_never_silently_dev` 守的是一个
**静默不安全**的失效：一个把 ``PE_ENV`` 拼错成 ``productionn`` 的运维，
在「认不出就当 dev」的实现下会得到一个**看起来在跑**的开发档服务
——CORS 全开、cookie 不带 ``Secure``、请求头身份通道照环境变量走。
三格全是不安全的那一侧，而它们的症状要等到出事才出现。
故 :func:`app.deploy.tier` 抛 :class:`ValueError`，而 ``app.main`` 有一条模块级的
``app = create_app()``，于是 ``uvicorn app.main:app`` 在一个坏 ``PE_ENV`` 下
**根本起不来**（失效方向 = 「起不来」，与 ``demo.ps1`` 那两道禁区守卫同一个姿势）。

⚠️ 这一格是**对 Plan 05A 既有行为的收紧**：改前 ``PE_ENV=staging`` /
``PE_ENV=development`` 都得到 ``cookie_secure() is False``（安静地不安全），
改后它们抛。故 ``tests/auth/test_sessions.py`` 的
``test_secure_is_on_only_in_production`` 里那一组值从「assert False」换成了
``pytest.raises``——两处各钉一半（那一处钉的是 ``cookie_secure`` 这个消费者，
本文件钉的是 ``tier`` 这个所有者）。
"""
import pytest

from app import deploy
from app.deploy import (
    CORS_ORIGINS_ENV_VAR,
    DEV,
    ENV_VAR,
    PROD,
    PRODUCTION,
    TIER_VALUES,
    cors_origins,
    is_prod,
    tier,
)

#: 三个环境变量名。**字面量**（硬规矩 #35：不从被测模块读回来跟自己比——
#: ``ENV_VAR`` / ``CORS_ORIGINS_ENV_VAR`` 这两个常量本身就是被测对象的一半）。
ALL_ENV_VARS = ("PE_ENV", "PE_CORS_ORIGINS")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """**每一条**测试都在「两个环境变量都没设」的缺省档下起跑。

    ⚠️ ``autouse``：少了它，一个在 shell 里设过 ``PE_ENV=prod`` 的人会让本文件的
    缺省档断言变成对另一档的断言，而失效是静默的（``monkeypatch`` 只撤销它自己设的）。
    """
    for name in ALL_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------------------
# ① 取值域与缺省值
# ---------------------------------------------------------------------------


def test_the_tier_vocabulary_is_exactly_dev_and_prod():
    """取值域**恰好**是 ``{"dev", "prod"}``（派单 §2 第 1 格逐字给的）。

    ⚠️ :data:`PRODUCTION` **不是**第三个值：它是 ``prod`` 的一个 accepted 拼法
    （Plan 05A 的字面量，继续接受的理由见 :mod:`app.deploy` 的模块 docstring 第四节），
    而 :func:`tier` 把它**折成** :data:`PROD`。故 ``TIER_VALUES`` 里没有它。
    ⚠️ 本条因此是「有人往取值域里加了第三个档位」的闸：加档位必须是一次显式的
    清单修改，而不是「``tier()`` 多返回一个串」。
    """
    assert TIER_VALUES == {"dev", "prod"}
    assert DEV == "dev" and PROD == "prod" and PRODUCTION == "production"
    assert ENV_VAR == "PE_ENV" and CORS_ORIGINS_ENV_VAR == "PE_CORS_ORIGINS"
    assert PRODUCTION not in TIER_VALUES


def test_the_default_tier_is_dev(monkeypatch):
    """缺省是 ``dev``；``""`` 与全空白也算「没设」（PowerShell 的 ``$env:X = ""``）。"""
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert tier() == DEV and is_prod() is False
    for value in ("", "   ", "\t"):
        monkeypatch.setenv(ENV_VAR, value)
        assert tier() == DEV, value
        assert is_prod() is False, value
    monkeypatch.setenv(ENV_VAR, DEV)
    assert tier() == DEV and is_prod() is False


def test_both_production_spellings_mean_the_same_tier(monkeypatch):
    """``prod`` 与 ``production`` **折成同一个档位**（大小写与首尾空白先规范化）。

    ⚠️ 少了本条，「有人把 ``production`` 改成别的含义」是绿的——
    而那会让所有按 Plan 05A 那份 spec §13 部署的机器**静默**落到开发档
    （CORS 全开 + cookie 不带 ``Secure`` + 请求头身份通道照环境变量走）。
    ⚠️ ``" prod "`` / ``"PROD"`` 也算：一个环境变量被写成大小写不同的字面量是常见事故，
    而失效方向是「生产上没加 Secure」= 不安全的那一侧（口径与
    ``tests/auth/test_sessions.py::test_secure_is_on_only_in_production`` 逐字相同）。
    """
    for value in ("prod", "PROD", " prod ", "production", "Production", "  PRODUCTION  "):
        monkeypatch.setenv(ENV_VAR, value)
        assert tier() == PROD, value
        assert is_prod() is True, value


def test_an_unrecognised_tier_is_loud_and_never_silently_dev(monkeypatch):
    """**本文件最要紧的一条**：认不出的值一律 :class:`ValueError`，绝不回落 ``dev``。

    判据两拍：

    1. 抛的是 ``ValueError``（经 :mod:`app.api.errors` 折成 422
       ``unprocessable_value`` 并带上消息原文；在 ``app.main`` 的模块级
       ``create_app()`` 那一档上它直接让服务**起不来**）；
    2. ⚠️ **消息里点名了那个环境变量与收到的原文**，且**明写了「刻意不回落到 dev」**
       ——否则运维看到的是一句「无效的环境变量」，而他下一个动作很可能是
       「那就删掉它吧」，删掉之后得到的是一个**安静的开发档服务**。

    ⚠️ 逐个点名测的六个值各有来历：``productionn`` / ``prodd`` 是拼写错误；
    ``development`` / ``staging`` 是**别的系统里合法的档位名**（``RAILS_ENV`` /
    ``NODE_ENV`` 的惯例里有它们，故一个照着惯例写配置的人会写出来）；
    ``1`` / ``true`` 是「以为它是个布尔开关」。六个在改前**全部**静默落到
    ``cookie_secure() is False``。
    """
    for value in ("productionn", "prodd", "development", "staging", "1", "true", "PROD UCTION"):
        monkeypatch.setenv(ENV_VAR, value)
        with pytest.raises(ValueError) as excinfo:
            tier()
        message = str(excinfo.value)
        assert ENV_VAR in message, (value, message)
        assert value.strip().lower() in message, (value, message)
        assert "dev" in message and "prod" in message, (value, message)
        with pytest.raises(ValueError):
            is_prod()


def test_the_tier_is_read_at_call_time_not_at_import_time(monkeypatch):
    """**在调用时读环境变量**：``setenv`` 之后立刻读到新值。

    ⚠️ 这一格是承重的（口径与 :func:`app.auth.passwords.iterations` /
    :func:`app.api.deps.allow_header_identity` 逐字相同）：``app.main`` 有一条
    模块级的 ``app = create_app()``，故「import 期读」等价于「必须在 import 之前设好」，
    而 ``monkeypatch.setenv`` 发生在 import **之后**——本条红就说明有人把解析挪到了
    模块级（那时全部档位断言会变成对「pytest 启动那一刻的环境」的断言）。
    """
    assert tier() == DEV
    monkeypatch.setenv(ENV_VAR, PROD)
    assert tier() == PROD
    monkeypatch.setenv(ENV_VAR, DEV)
    assert tier() == DEV


# ---------------------------------------------------------------------------
# ② PE_CORS_ORIGINS 的解析
# ---------------------------------------------------------------------------


def test_the_cors_whitelist_is_split_on_commas_and_trimmed(monkeypatch):
    """逗号分隔、逐段去空白、**丢掉空段**、不去重也不排序。

    ⚠️ 「丢掉空段」的失效方向是**更窄**：``"https://a.example,"``（尾随一个逗号，
    复制粘贴最常见的形状）解析成 ``["https://a.example"]``，而一个空源本来就不匹配
    任何 ``Origin``。为它拒绝启动是把运维的活儿变难。
    ⚠️ 「不去重也不排序」是刻意的：顺序会原样落进 ``allow_origins``，
    而去重/排序会改变「运维写下来的那张清单」的样子，让「配置文件与运行时不一致」
    这件事更难查。
    """
    monkeypatch.setenv(CORS_ORIGINS_ENV_VAR, "https://a.example, https://b.example")
    assert cors_origins() == ["https://a.example", "https://b.example"]

    monkeypatch.setenv(CORS_ORIGINS_ENV_VAR, "https://a.example,https://b.example,")
    assert cors_origins() == ["https://a.example", "https://b.example"]

    monkeypatch.setenv(CORS_ORIGINS_ENV_VAR, "a,,b, ,c")
    assert cors_origins() == ["a", "b", "c"]

    monkeypatch.setenv(CORS_ORIGINS_ENV_VAR, "b,a,b")
    assert cors_origins() == ["b", "a", "b"], "刻意不去重也不排序"


def test_an_unset_or_blank_cors_whitelist_is_an_empty_list_not_a_wildcard(monkeypatch):
    """缺省（未设 / 空 / 全空白）解析成**空列表**，⚠️ **不是** ``["*"]``。

    ⚠️ 这一格是计划 §4 那句「**缺省空 = 不挂 CORSMiddleware**（即拒绝跨域）」的前提：
    :func:`app.main._install_cors` 按「列表空不空」决定挂不挂，
    而一个「空 → 回落成 ``*``」的解析会让生产档**静默全开**——
    那正是本 Task 要消掉的那一格（改前 ``allow_origins=["*"]`` 是无条件硬编码的）。
    """
    monkeypatch.delenv(CORS_ORIGINS_ENV_VAR, raising=False)
    assert cors_origins() == []
    for value in ("", "   ", ",", ",,,"):
        monkeypatch.setenv(CORS_ORIGINS_ENV_VAR, value)
        assert cors_origins() == [], value


def test_a_wildcard_in_the_whitelist_is_parsed_verbatim_and_never_dropped(monkeypatch):
    """``PE_CORS_ORIGINS=*`` 解析出来就是 ``["*"]``——**本模块不悄悄吃掉那个星号**。

    ⚠️ 拒绝它是 :func:`app.main._selfcheck_prod` 的活（守卫在 ``tests/test_main.py``
    的 ``test_prod_with_a_wildcard_cors_whitelist_refuses_to_start``）。
    ⚠️ **两处各判一半是刻意的**：解析侧悄悄丢掉 ``*`` 的话自检就永远看不到它，
    而运维写下的那个星号会变成一个**静默的**「什么都没允许」——
    他会去查前端，而真因是后端把他的配置吃掉了。
    """
    monkeypatch.setenv(CORS_ORIGINS_ENV_VAR, "*")
    assert cors_origins() == ["*"]
    monkeypatch.setenv(CORS_ORIGINS_ENV_VAR, "https://a.example,*")
    assert cors_origins() == ["https://a.example", "*"]


def test_the_cors_whitelist_is_parsed_the_same_way_in_both_tiers(monkeypatch):
    """:func:`cors_origins` **不判档位**：``dev`` 下问它也给同一个答案。

    ⚠️ 「哪个档位读它」是 :func:`app.main._install_cors` 的事。本条把这个分工钉住：
    若解析函数自己判了档位（``dev`` 下回 ``[]``），则「dev 挂 ``*``」与
    「dev 的白名单是空的」这两件事在本模块里无法区分，
    而 ``tests/test_main.py`` 那几条也就无法只测装配那一层。
    """
    monkeypatch.setenv(CORS_ORIGINS_ENV_VAR, "https://a.example")
    monkeypatch.setenv(ENV_VAR, DEV)
    assert cors_origins() == ["https://a.example"]
    monkeypatch.setenv(ENV_VAR, PROD)
    assert cors_origins() == ["https://a.example"]


# ---------------------------------------------------------------------------
# ③ 本模块自己的形状
# ---------------------------------------------------------------------------


def test_the_module_imports_nothing_but_the_standard_library():
    """本模块**只 import :mod:`os`**——那条性质是可执行的，不是散文。

    ⚠️ 它是 :mod:`app.auth` 的包 docstring 那句承诺的前提：「本包刻意不声明任何 HTTP
    对象……本包可以在没有 ``fastapi`` 的进程里被 import」。而
    :func:`app.auth.sessions.cookie_secure` 要读档位，故本模块被 ``app.auth``
    间接导入——它一旦 ``import fastapi``（或 ``starlette``），那句承诺当场变假，
    而失效是静默的（只是「一个 CLI 进程现在也需要装 fastapi」）。
    ⚠️ 判据是 AST 级的（``ast.parse`` + 数 ``Import`` / ``ImportFrom``），
    不是文本搜索——文本搜索会把 docstring 里的**提及**当成**本身**（硬规矩 #109）。
    """
    import ast
    import pathlib

    path = pathlib.Path(deploy.__file__)
    assert path.name == "deploy.py" and path.parent.name == "app"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = sorted(
        {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
         for alias in node.names}
        | {node.module.split(".")[0] for node in ast.walk(tree)
           if isinstance(node, ast.ImportFrom) and node.module}
    )
    assert imported == ["os"], imported


def test_sessions_env_var_and_production_are_aliases_not_second_copies():
    """:data:`app.auth.sessions.ENV_VAR` / ``PRODUCTION`` 是**别名**（同一个对象）。

    ⚠️ 这一条守的是「搬家之后留下第二份字面量」：Plan 05A 那两个常量住在
    :mod:`app.auth.sessions`，Plan 06 Task 4 把所有者搬来了本模块，
    而两个既有测试文件仍按 ``auth_sessions.ENV_VAR`` 引用它们。
    若那一处改成 ``ENV_VAR = "PE_ENV"``（再写一遍字面量），
    则「改环境变量名」要改两处、漏一处是静默的。用 ``is`` 判（不是 ``==``）：
    两个相等的串也可能是两份字面量。
    """
    from app.auth import sessions

    assert sessions.ENV_VAR is deploy.ENV_VAR
    assert sessions.PRODUCTION is deploy.PRODUCTION

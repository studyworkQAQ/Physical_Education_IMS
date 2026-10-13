"""**部署档位**（``PE_ENV``）的唯一所有者，以及它派生的三格配置（Plan 06 Task 4）。

--------------------------------------------------------------------------
为什么会有这个模块（本仓第四个「环境事实的住址」）
--------------------------------------------------------------------------

``PE_ENV`` 此前住在 :mod:`app.auth.sessions`（:data:`app.auth.sessions.ENV_VAR` 与
:data:`app.auth.sessions.PRODUCTION`），而它只有**一个**消费者：
:func:`app.auth.sessions.cookie_secure`（「cookie 要不要带 ``Secure``」）。
那个模块自己的注释逐字写着「⚠️ 它**只**被 :func:`cookie_secure` 读……
故本仓今天没有第二处『环境』的概念」。

Plan 06 Task 4 让那个前提作废：档位现在要决定**三**件事，而三个消费者住在
**三个不同的层**，其中两个**不许** import 第三个：

==============================  =============================================
消费者                          它要档位回答什么
==============================  =============================================
:func:`app.auth.sessions.cookie_secure`      cookie 要不要带 ``Secure``
:func:`app.api.deps.allow_header_identity`   请求头那条过渡通道开不开（prod **强制关**）
:func:`app.main.create_app`                  CORS 挂不挂、挂成什么；以及**启动自检**
==============================  =============================================

⚠️ **于是它不能住在其中任何一个里**：``app.api`` 与 ``app.auth`` 都**不得** import
``app.main``（``main`` 在 ``api`` 之上、是装配 ``api`` 的那个人；
``tests/architecture/test_layering.py`` 的 :data:`API_ALLOWED_PREFIXES` 逐字把
``app.main`` 列成 RED，理由是导入环）。三份各写一遍「哪些串算生产」的话，
下一个人加一个拼法只会加到其中一份，而漏掉的那一份是**静默**的。
故本模块存在，且 ``app.auth.sessions`` 的 :data:`~app.auth.sessions.ENV_VAR` /
:data:`~app.auth.sessions.PRODUCTION` 从此是**本模块那两个常量的别名**
（同一个对象，不是第二份字面量）。

--------------------------------------------------------------------------
⚠️⚠️ 本模块**只 import :mod:`os`**（承重的性质，不要破坏它）
--------------------------------------------------------------------------

理由与 :mod:`app.config` 的「只 import :mod:`pathlib`」同一条，而更强：
:mod:`app.auth` 的包 docstring 逐字承诺「**本包刻意不声明任何 HTTP 对象**……
本包可以在没有 ``fastapi`` 的进程里被 import」。而 ``cookie_secure`` 要读档位，
故本模块被 ``app.auth`` 间接导入——它一旦 ``import fastapi``（或 ``starlette``），
那句承诺当场变假，而失效是静默的（只是「一个 CLI 进程现在也需要装 fastapi」）。

⚠️ **后果是「启动自检」不住在这里**：自检要看一个**已经装配好的** FastAPI 应用
（它数的是 ``app.user_middleware`` 里到底挂了什么），那是 :mod:`app.main` 的事
（:func:`app.main._selfcheck_prod`）。本模块只提供纯值：档位、白名单、以及
「哪些串算生产」。分工是「**判据在这里、装配与自检在那里**」。

--------------------------------------------------------------------------
⚠️ 取值域：``dev`` / ``prod``（+ 一个 05A 的旧拼法），**别的值一律响亮失败**
--------------------------------------------------------------------------

派单逐字给的是 ``PE_ENV ∈ {dev, prod}``、缺省 ``dev``。而 Plan 05A 落地时用的字面量是
``"production"``（:data:`app.auth.sessions.PRODUCTION`，理由当时写的是「与
``RAILS_ENV`` / ``NODE_ENV`` 一类既有惯例同一个词」），且那个值已经写进了 spec §13
与 ``tests/auth/test_sessions.py``。两格冲突，处置是**都收**、并把 ``prod`` 当正字：

* ``""`` / 未设 → ``dev``（缺省）；
* ``"dev"`` → ``dev``；
* ``"prod"`` **或** ``"production"`` → ``prod``（后者是 05A 的拼法，**继续接受**）；
* **其余一律 :class:`ValueError`**（大小写与首尾空白先规范化：``" PROD "`` 算 ``prod``）。

⚠️⚠️ **最后那一格是本模块最要紧的决定**：若「认不出的值」静默回落到 ``dev``，
则一个把 ``PE_ENV`` 拼错成 ``productionn`` 的运维会得到一个**看起来在跑**的
dev 档服务——CORS 全开、cookie 不带 ``Secure``、请求头身份通道按环境变量走。
三格全是「静默不安全」，而它们的症状要等到出事才出现。故失效方向必须是
**起不来**（与 ``backend/scripts/demo.ps1`` 那两道禁区守卫、
:func:`app.db.session._stamp_unversioned` 的「先比对后 stamp」同一个姿势）。
⚠️ 它确实**在 import 期就响**：``app.main`` 有一条模块级的 ``app = create_app()``，
而 :func:`app.main.create_app` 第一件事就是问档位——故 ``uvicorn app.main:app``
在一个坏 ``PE_ENV`` 下**根本起不来**，报错是 ``ValueError: PE_ENV 只能是 …``。

⚠️ **保留 ``"production"`` 这个旧拼法的理由**（硬规矩 #39，如实记）：它让取值域
从「两个」变成「三个」，与「一个安全开关的取值域越窄越好」
（:func:`app.api.deps.allow_header_identity` 的口径）有张力。而**删掉它更糟**：
spec §13 与既有守卫都在用它，删掉之后所有按 05A 文档部署的机器会**静默**落到
``dev``——正是上面那一格要防的失效。故留着，并由
``tests/test_deploy.py`` 的 ``test_both_production_spellings_mean_the_same_tier``
钉住「两个拼法给出同一个档位」（少了那条，「有人把其中一个改成别的含义」是绿的）。

--------------------------------------------------------------------------
⚠️ ``PE_CORS_ORIGINS``：缺省空 = **不挂 CORSMiddleware**（= 拒绝跨域）
--------------------------------------------------------------------------

计划 §4 逐字要求：``prod`` 下 CORS 从 ``allow_origins=["*"]`` 改成读环境变量
（逗号分隔白名单），**缺省空 = 不挂 CORSMiddleware**。
⚠️ 「不挂」与「挂一个空白名单」在浏览器上**行为相同**（两者都不回
``Access-Control-Allow-Origin``，故跨源 ``fetch`` 一律被浏览器拦下），
故本模块只负责**解析出那个列表**，「挂不挂」由 :func:`app.main.create_app` 按
「列表空不空」决定。⚠️ 而**自检会数 middleware**，故「空列表却仍然挂了 CORS」
这一档会被 :func:`app.main._selfcheck_prod` 抓到（如果它挂的是 ``*``）。

⚠️ **``PE_CORS_ORIGINS=*`` 是一次响亮的失败、不是「允许全部」**：解析出来的就是
``["*"]``（本模块不做任何特殊处理），而自检见到 ``*`` 就 ``raise``
——于是「运维图省事写了个星号」的表现是**服务起不来**，不是一个静默的全开 CORS。
这一格由 ``tests/test_deploy.py`` 与 ``tests/test_main.py`` 各钉一半
（前者钉「解析出来就是 ``*``、没有被悄悄丢掉」，后者钉「装配时 raise」）。

⚠️ 解析口径：按 ``,`` 切、逐段 ``strip()``、**丢掉空段**（``"a,,b,"`` → ``["a","b"]``），
**不去重也不排序**（顺序会原样落进 ``Access-Control-Allow-Origin`` 的匹配逻辑，
而 Starlette 按列表顺序匹配；去重/排序会改变一个「运维写下来的清单」的样子，
让「配置文件与运行时不一致」这件事更难查）。⚠️ 空段被丢掉而不是报错：
``"https://a.example,"``（尾随一个逗号）是复制粘贴最常见的形状，
为它拒绝启动是把运维的活儿变难，而丢掉空段的失效方向是**更窄**（少允许一个空源，
而空源本来就不匹配任何 ``Origin``）。
"""

import os

__all__ = [
    "CORS_ORIGINS_ENV_VAR",
    "DEV",
    "ENV_VAR",
    "PROD",
    "PRODUCTION",
    "TIER_VALUES",
    "cors_origins",
    "is_prod",
    "tier",
]

#: 判「哪个档位」的环境变量名。⚠️ **它是全仓唯一的住址**：
#: :data:`app.auth.sessions.ENV_VAR` 从此是它的别名（同一个 ``str`` 对象）。
ENV_VAR = "PE_ENV"

#: 两个档位的字面值。⚠️ ``prod`` 是**正字**（派单逐字给的取值域）。
DEV = "dev"
PROD = "prod"

#: ``prod`` 的**两个** accepted 拼法（模块 docstring 第四节逐字交代了为什么留旧的那一个）。
#: ⚠️ :data:`app.auth.sessions.PRODUCTION` 从此是 ``"production"`` 那一个的别名。
PRODUCTION = "production"

#: ``tier()`` 的取值域（**两个**值；``PRODUCTION`` 是 ``PROD`` 的别名、不是第三个值）。
#: ⚠️ 它被 ``tests/test_deploy.py`` 按字面钉住（``== {"dev", "prod"}``），
#: 故「有人往取值域里加了第三个档位」必须是一次显式的清单修改。
TIER_VALUES = frozenset({DEV, PROD})

#: ``prod`` 认的那两个拼法（小写、已去空白）。
_PROD_SPELLINGS = frozenset({PROD, PRODUCTION})

#: 跨域白名单的环境变量名（逗号分隔）。⚠️ **只在 ``prod`` 下被读**：
#: ``dev`` 一律挂 ``allow_origins=["*"]``（前端跑在 ``localhost:5173`` 的 vite dev
#: server 上，而演示要在同一台机器的浏览器里点起来）。
CORS_ORIGINS_ENV_VAR = "PE_CORS_ORIGINS"


def tier() -> str:
    """本进程的部署档位：:data:`DEV` 或 :data:`PROD`；认不出的值 → ``ValueError``。

    ⚠️ **在调用时读环境变量、不在 import 时读**（口径与
    :func:`app.auth.passwords.iterations` / :func:`app.api.deps.allow_header_identity`
    逐字相同）：``app.main`` 的模块级 ``app = create_app()`` 让「import 期读」等价于
    「必须在 import 之前设好」，而 ``monkeypatch.setenv`` 发生在 import **之后**。
    ⚠️ 于是本函数**每次调用都重新解析**，而它的全部成本是一次 ``dict`` 查找 +
    一次 ``strip().lower()``。``cookie_secure()`` 每个请求都调它，故这条性质是承重的。

    ⚠️ **空字符串按「没设」处理**：``$env:PE_ENV = ""`` 在 PowerShell 里是
    「设了一个空值」而不是「删掉这个变量」。
    """
    raw = os.environ.get(ENV_VAR, "").strip().lower()
    if not raw or raw == DEV:
        return DEV
    if raw in _PROD_SPELLINGS:
        return PROD
    raise ValueError(
        f"{ENV_VAR} 只能是 {DEV!r} 或 {PROD!r}（也接受 Plan 05A 的旧拼法 "
        f"{PRODUCTION!r}），收到 {raw!r}。⚠️ 刻意**不**回落到 {DEV!r}：一个认不出的"
        f"档位若被当成开发档，得到的是一个 CORS 全开、cookie 不带 Secure、"
        f"请求头身份通道照环境变量走的服务——三格全是静默不安全，"
        f"而它们的症状要等到出事才出现。"
    )


def is_prod() -> bool:
    """是不是生产档。⚠️ 它就是 ``tier() == PROD``，故坏值同样**响亮失败**。"""
    return tier() == PROD


def cors_origins() -> list[str]:
    """:data:`CORS_ORIGINS_ENV_VAR` → 白名单（可能为空列表）。逐格口径见模块 docstring 末节。

    ⚠️ **它不判档位**：``dev`` 下调它会给出一个没人用的列表。
    「哪个档位读它」是 :func:`app.main.create_app` 的事——本模块只提供纯值，
    于是「dev 下白名单是什么」这件事可以被单独测（``tests/test_deploy.py``）。
    ⚠️ **它不特殊处理 ``"*"``**：解析出来就是 ``["*"]``，而拒绝它是
    :func:`app.main._selfcheck_prod` 的活。两处各判一半的理由是「解析」与
    「装配对不对」是两件事：解析侧悄悄丢掉 ``*`` 的话，自检就永远看不到它，
    而运维写下的那个星号会变成一个**静默的**「什么都没允许」。
    """
    raw = os.environ.get(CORS_ORIGINS_ENV_VAR, "")
    return [part.strip() for part in raw.split(",") if part.strip()]

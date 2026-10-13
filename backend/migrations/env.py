"""Alembic 的运行环境：把 26 张表的 ``Base.metadata`` 与库 URL 交给 Alembic（Plan 06 Task 1 建）。

本文件是**工具配置**、不是生产层代码：它不进 ``app/**``，故 ``tests/architecture/``
那两条依赖方向守卫（``SCANNED_DIRS`` 只扫 ``app/`` 下的五个目录）不管它。
⚠️ 但它**在 AST 扫描面内**：``test_layering.py`` 与 ``test_domain_purity.py`` 各有一段
``sorted(BACKEND.rglob("*.py"))`` 的全仓扫描，会对本文件 ``ast.parse(...)`` 并核对
``_package_of(py) == py.parent.parts``。故三条纪律：① UTF-8 无 BOM、可 parse；
② **不使用相对导入**（本文件不是包的一部分，``migrations/`` 下没有 ``__init__.py``）；
③ 不在这里出现 ``pe.db`` 一类的禁区字面量（连接串的唯一所有者见下面 :func:`_resolve_db_url`）。

--------------------------------------------------------------------------
``target_metadata``：唯一真相是 ``app.db.session.Base.metadata``
--------------------------------------------------------------------------

⚠️ **本文件从 ``app.db.session`` 导入 :class:`Base`，而不是从 ``app.db.models``**，
尽管计划正文写的是后者。实测两者是**同一个对象**
（``app.db.models.Base is app.db.session.Base`` → ``True``），但 ``app.db.models.Base``
这个名字的来路是一条**星号导入的副作用**：``models/__init__.py`` 的
``from ._shared import *`` 并不带来 ``Base``（``_shared.py`` 只定义 ``JsonText`` 与
``_in_domain``），真正带过来的是 ``from .organisation import *`` —— 而 ``organisation.py``
自己写的是 ``from app.db.session import Base``，且那些子模块**刻意不定义 ``__all__``**
（理由逐字在 ``models/__init__.py`` 里：定义了就会截断 ``import *``、撞红
``_MODELS_PUBLIC_BASELINE`` 那条守卫）。于是「从 ``models`` 拿 ``Base``」依赖的是
「某个子模块恰好 import 了它、且没有 ``__all__``」这个**非承重**的事实；
从 ``session`` 拿则是从所有者拿。26 张表的注册仍靠 ``import app.db.models`` 那一句
（它与 :func:`app.db.session.init_db` 函数体内那一句同一个形状、同一条理由：
``models`` 反过来要 import ``session`` 的 ``Base``，放模块顶层会构成导入环——
而本文件本来就在 ``app`` 之外，环不成问题，故这里放在模块级即可）。

--------------------------------------------------------------------------
库 URL：三档优先级，与 ``app.main._resolve_db_url`` 同形
--------------------------------------------------------------------------

① ``config.attributes[DB_URL_ATTRIBUTE]`` —— **程序内调用**交进来的那一个
   （:func:`app.db.session.init_db` 与本仓那两条迁移守卫测试都走这一档：
   它们手里已经有一个引擎/一个临时库，不该再去读进程级的环境变量）。
   ⚠️ 那个**键名**的所有者是 :data:`app.db.session.DB_URL_ATTRIBUTE`、不是本文件：
   ``migrations/`` 不是包（没有 ``__init__.py``），而**加载 ``env.py`` 本身就等于跑一次
   迁移**（模块末尾那三行），故 ``session.py`` 不可能反过来 ``import`` 它。
   把键名放在生产者那一边，两个文件之间才有**一条**导入边、而不是两份字面量。
   ⚠️ 走 ``attributes`` 而不是 ``set_main_option("sqlalchemy.url", …)``：后者经
   ``configparser`` 的 ``%`` 插值，URL 里出现一个 ``%`` 就会被当成插值语法当场抛错。
② 环境变量 ``PE_DB_URL`` —— **命令行** ``python -m alembic upgrade head`` 的真值来源，
   与 app 运行时同源（``demo.ps1`` 设的就是它）。⚠️ 变量**名**不在本文件里写第二遍：
   它从所有者 :data:`app.main.DB_URL_ENV_VAR` 导入（本仓对这一族常量一律如此：
   ``PBKDF2_ITERATIONS_ENV_VAR`` / ``CSV_DIR_ENV_VAR`` / ``PE_ALLOW_HEADER_IDENTITY``
   都是「一个环境事实只有一个住址」）。那一句 import 刻意放在**函数体内**：
   ``app.main`` 有一条模块级的 ``app = create_app()``，放进模块顶层会让
   「加载一个迁移环境」顺带装配一次 FastAPI 应用。
③ 都没有 → :class:`RuntimeError`（响亮）。⚠️ **不回落到任何缺省库**：
   ``app.config.DEFAULT_DB_URL`` 逐字指向禁区 ``backend/pe.db``，
   回落过去就是当场建出那个文件。

``alembic.ini`` 的 ``sqlalchemy.url`` 是**空占位、本文件不读它**（理由写在那个文件头）。
⚠️ **``alembic.ini`` 必须保持纯 ASCII**：实测 alembic 1.20.0 用
``encoding="locale"``（本机是 GBK）读那个文件，一行 UTF-8 中文注释就让**每一条**
``alembic`` 命令在启动期抛 ``UnicodeDecodeError: 'gbk' codec can't decode byte 0x80``。
本文件与迁移脚本不受此限（Python 读 ``.py`` 一律按 UTF-8），故中文理由住在这两处。

--------------------------------------------------------------------------
比较口径：四个开关各自的理由
--------------------------------------------------------------------------

``version_table = ALEMBIC_VERSION_TABLE``
    值与 Alembic 的缺省值相同（``"alembic_version"``），显式传是为了让
    「``init_db`` 找哪张表判这个库有没有被纳管」与「alembic 实际写哪张表」
    **只有一份字面量**（所有者是 :data:`app.db.session.ALEMBIC_VERSION_TABLE`）。

``render_as_batch = True``
    SQLite **没有** ``ALTER COLUMN`` / ``DROP CONSTRAINT``：Alembic 的 SQLite 方言在
    渲染出这类语句后，运行迁移时会抛 ``NotImplementedError``。批处理模式改走
    「建新表 → 拷数据 → 改名 → 删旧表」，是 SQLite 上唯一能落地的改法。
    ⚠️ 基线迁移里**一条 ALTER 都没有**（全是 ``create_table``），故这一档今天不改变
    任何输出；开着它是为了**下一条**迁移：改列宽/改可空/加删列的人不该由
    「迁移在甲方现场跑到一半炸开」来发现这件事。

``compare_type = True``
    Alembic 缺省**不比较列类型**，于是「把 ``String(32)`` 改成 ``String(64)``」这类改动
    autogenerate 看不见、Task 2 那条纪律守卫也就抓不到。本仓的列宽是 spec §4 逐字钉的
    （``tests/db/test_models.py`` 有一整套列宽断言），故类型变更必须被当成一次真改动。

``compare_server_default = False``
    实测 26 张表**一个 ``server_default`` 都没有**（列缺省一律由 Python 侧或调用方给，
    见 ``models/_shared.py`` 与 Ruling 21「缺测就是 NULL」），故这一档今天没有可比的对象；
    而 SQLite 反射回来的缺省值是**带引号的原文文本**，与 SQLAlchemy 侧的对象比较极易
    产生「恒有 diff」的噪声——那会让 Task 2 的守卫长期红，进而被下一个人调松。
    ⚠️ 将来真加了 ``server_default`` 的列，请连这一档一起打开并处理噪声，
    不要只在迁移里手写。
"""
from __future__ import annotations

import os
import pathlib
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

#: ``backend/`` 的绝对路径（本文件在 ``backend/migrations/env.py``，故 ``parents[1]``）。
#: ⚠️ 这一段是**无条件**的 sys.path 兜底，与 ``alembic.ini`` 的 ``prepend_sys_path = .``
#: 互补：后者只在 CWD 恰好是 ``backend/`` 时才管用，而前者让
#: ``alembic -c backend/alembic.ini upgrade head``（在仓库根跑）同样成立。
BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import models  # noqa: E402,F401  仅为把 26 张表注册进 Base.metadata
from app.db.session import (  # noqa: E402
    ALEMBIC_VERSION_TABLE,
    DB_URL_ATTRIBUTE,
    Base,
)

#: Alembic 的 ``Config`` 对象（``alembic.ini`` 与程序内 ``set_main_option`` 的那一份）。
config = context.config

# ⚠️ 承重：env.py 用 alembic.ini 的 [loggers]/[handlers]/[formatters] 三节配日志，
#    缺任何一节都会在这里抛 configparser 的缺节错误。
# ⚠️⚠️ ``disable_existing_loggers=False`` **不是可选的**：``logging.config.fileConfig``
#    的缺省值是 ``True``，那会把配置里没有点名的 logger 一律 ``disabled = True``。
#    而 :func:`app.db.session.init_db` 是在 **uvicorn 的 lifespan 里**跑迁移的——
#    用缺省值等于「服务一起来就把 uvicorn 与本应用自己的 logger 全关掉」，
#    此后一条日志都不再输出，而没有任何一处报错。
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

#: autogenerate 的比较基准。**它就是建表的那一份**（同一个 ``Base.metadata`` 对象），
#: 故「模型改了没写迁移」这件事只有一个真相可对。
target_metadata = Base.metadata

#: ``context.configure`` 的两侧（offline / online）共用的口径。**单一所有者**：
#: 四个开关各自的理由写在模块 docstring 的最后一节（``version_table`` 那一条的理由
#: 写在 :data:`app.db.session.ALEMBIC_VERSION_TABLE` 上——它是那个名字的所有者）。
COMPARE_OPTS: dict[str, object] = {
    "target_metadata": target_metadata,
    "render_as_batch": True,
    "compare_type": True,
    "compare_server_default": False,
    "version_table": ALEMBIC_VERSION_TABLE,
}


def _resolve_db_url() -> str:
    """按模块 docstring 那三档解析库 URL；解析不出来就**响亮失败**。"""
    from app.main import DB_URL_ENV_VAR  # 函数体内导入，理由见模块 docstring

    given = config.attributes.get(DB_URL_ATTRIBUTE)
    url = (given or os.environ.get(DB_URL_ENV_VAR) or "").strip()
    if not url:
        raise RuntimeError(
            "Alembic 拿不到数据库 URL：既没有程序内传入的 "
            f"Config.attributes[{DB_URL_ATTRIBUTE!r}]，环境变量 {DB_URL_ENV_VAR} 也没设。"
            f"请设 ${DB_URL_ENV_VAR}（与 app 同源；演示库用 "
            '`python -c "from app.main import DEMO_DB_URL; print(DEMO_DB_URL)"` 读出来）。'
            "⚠️ 刻意不回落到 app.config.DEFAULT_DB_URL：它指向禁区 backend/pe.db。"
        )
    return url


def run_migrations_offline() -> None:
    """离线档（``alembic upgrade head --sql``）：只渲染 DDL、不连库。

    给甲方现场做**升级前审阅**用：先看一遍将要执行哪些语句，再决定跑不跑。
    ``literal_binds=True`` 让参数就地渲染成字面量，输出的 SQL 才能直接拿去读。
    """
    context.configure(
        url=_resolve_db_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **COMPARE_OPTS,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线档：连上库、执行迁移。

    ``NullPool`` 是 Alembic 脚手架的缺省，也是这里要的：迁移是一次性的短连接，
    留着连接池只会让 ``init_db`` 之外多出一条握着库文件的连接。
    ⚠️ 它**刻意不复用**调用方那个引擎：SQLite 的文件库可以被多条连接同时打开，
    而 ``init_db(eng)`` 交进来的引擎此刻一条连接都还没开（``create_engine`` 是惰性的）。
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _resolve_db_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, **COMPARE_OPTS)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

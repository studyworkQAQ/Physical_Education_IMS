"""数据库引擎、会话与**建库/迁移**入口。

本模块提供：声明基类 :class:`Base`、引擎工厂 :func:`engine`、会话类 ``Session``、
建库函数 :func:`init_db`，以及 ``init_db`` 与 ``migrations/env.py`` 之间三个约定的住址
（:data:`ALEMBIC_INI` / :data:`DB_URL_ATTRIBUTE` / :data:`ALEMBIC_VERSION_TABLE`）。
**28** 张表的模型在 :mod:`app.db.models`，通用读写助手在 :mod:`app.db.repo`。
此外在导入时注册一个 ``connect`` 钩子，打开 SQLite 默认关闭的外键强制
（见 :func:`_sqlite_foreign_keys_on`）。

``Session`` 直接就是 ``sqlalchemy.orm.Session`` 类本身，而不是绑定了某个引擎的
``sessionmaker`` 实例。调用方（测试、CLI、管道）自己先造引擎、再 ``Session(eng)``：
这样同一份代码既能跑内存库也能跑磁盘库，且不会在导入期就把数据库 URL 钉死——
测试因此不必依赖任何磁盘文件。

--------------------------------------------------------------------------
Plan 06 Task 1 起：``init_db`` 走 Alembic 迁移链，**「schema 改动 = 重建库」作废**
--------------------------------------------------------------------------

改前本模块教的是「本仓不做迁移（没有 Alembic，也不打算有），故 schema 改动 = 删库重灌」。
那句话对一个要交付给甲方的产品是**错的**：甲方现场那份库里是一学期的真实体测、打卡与
处方，升级一次版本就把库删掉重灌等于把数据删掉。故 Plan 06 引入 ``alembic``
（**本计划唯一新增的后端依赖**，用户 2026-10-13 裁定）并建出迁移链：

* ``backend/alembic.ini`` —— 工具配置。⚠️ 必须**纯 ASCII**（alembic 用
  ``encoding="locale"`` 读它，本机是 GBK，一行中文注释就让每条 ``alembic`` 命令当场
  ``UnicodeDecodeError``），且里面**没有连接串**。
* ``backend/migrations/env.py`` —— 运行环境：``target_metadata`` 取自本模块的
  :attr:`Base.metadata`，库 URL 按「程序内传入 > ``PE_DB_URL`` > 响亮失败」三档解析。
* ``backend/migrations/versions/`` —— 迁移脚本。**它们是代码、不是数据**，入库。

:func:`init_db` 因此有四条路径（三档 + 一条快路径），逐条的实测行为见它自己的 docstring。
「迁移建出来的库 == ``create_all`` 建出来的库」这件事**不靠人眼看 diff**，靠
``tests/db/test_migration_baseline.py`` 那条一致性测试（逐表、逐列的名/类型/可空/默认、
逐索引、逐唯一约束、逐外键），以及 ``tests/db/test_migration_chain.py`` 那条
「模型改了必须配迁移」的纪律守卫。
"""
import pathlib

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import BACKEND_DIR

__all__ = ["Base", "Session", "engine", "init_db"]

#: ``backend/alembic.ini`` 的绝对路径。**它是「迁移链住在哪里」的唯一所有者**：
#: ``script_location`` 由那个文件里的 ``%(here)s/migrations`` 给出（``%(here)s`` =
#: 该 ini 所在目录），故本模块**不再**另存一份 ``MIGRATIONS_DIR`` ——存两份的话，
#: 把 ``migrations/`` 改名的人只会改到其中一份，而 ``Config`` 仍然能加载（另一份指向
#: 一个不存在的目录时报错在很远的地方）。
#: ⚠️ 路径来自 :data:`app.config.BACKEND_DIR`（绝对路径、与 CWD 无关），
#: 故 :func:`init_db` 从仓库根跑与从 ``backend/`` 跑看到的是同一条迁移链。
ALEMBIC_INI: pathlib.Path = BACKEND_DIR / "alembic.ini"

#: 程序内调用把库 URL 交给 ``migrations/env.py`` 时用的 ``Config.attributes`` 键名。
#:
#: ⚠️ **所有者在本模块、不在 ``env.py``**：``migrations/`` 不是包（没有 ``__init__.py``），
#: 而**加载 ``env.py`` 本身就等于跑一次迁移**（它模块末尾就是
#: ``if context.is_offline_mode(): …``），故本模块不可能反过来 import 它。
#: 把键名放在生产者这一边，两个文件之间才有**一条**导入边而不是两份字面量。
#: ⚠️ 走 ``attributes`` 而不是 ``set_main_option("sqlalchemy.url", …)``：后者经
#: ``configparser`` 的 ``%`` 插值，URL 里出现一个 ``%`` 就会被当成插值语法当场抛错。
DB_URL_ATTRIBUTE: str = "pe_db_url"

#: Alembic 版本表的名字。⚠️ **所有者在本模块**，``migrations/env.py`` 从这里 import 它
#: 并显式交给 ``context.configure(version_table=…)``——不写死在两边的话，
#: 「``init_db`` 找哪张表判『这个库有没有被纳管』」与「alembic 实际写哪张表」
#: 就是两份字面量，改一边不改另一边会得到一个**永远走 stamp 那一档**的库
#: （因为它永远找不到那张表），而 stamp 每次都会重写一遍、不报错。
#: 缺省值也是 ``"alembic_version"``（``alembic.runtime.migration`` 的
#: ``opts.get("version_table", "alembic_version")``），本仓显式传是为了让那一条边存在。
ALEMBIC_VERSION_TABLE: str = "alembic_version"


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys_on(dbapi_connection, _record):
    """SQLite 每条连接默认关闭外键强制；不开则全库外键都只是注释。

    实测（不加本钩子）：``PRAGMA foreign_keys`` 读回 ``0``，往 ``derived_metrics``
    插一条 ``batch_id = 999999``（``daily_sync_run`` 里查无此行）**不报错**、照单
    全收。schema 里 20 个 ``ForeignKey`` 因此全部失效，后果是实打实的：

    * ``cleaning_log.student_id``（Ruling 25 的可空外键）分不清「孤儿学号」与
      「错指学号」——两者都表现为 NULL 或一个不存在的 id；
    * ``derived_metrics.batch_id`` / ``stratification_result.batch_id`` 是 Task 10
      幂等重放的唯一依据，没有兜底就意味着 ``delete_by_batch`` 漏删留下的孤儿派生
      行永远不会报错，只会静默抬高红黄绿分布。

    **必须注册在 ``Engine`` 类上，而不是 :func:`engine` 返回的实例上**：测试与管道
    都是自己 ``create_engine(...)`` 再交给 :func:`init_db`，挂在工厂返回值上一个也
    覆盖不到。代价是它对本进程内**每一个**引擎生效——本项目只用 SQLite，故接受；
    将来若真接非 SQLite 后端，分支要加在本监听器内部（按 DBAPI 连接类型判断），
    不能靠缩小注册目标来解决，否则测试路径又会漏掉。

    ⚠️ **Plan 06 Task 1 之后它还多覆盖一个人**：``migrations/env.py`` 自己
    ``engine_from_config(...)`` 出来的那个引擎。这是**要的**——迁移里那些
    ``ForeignKeyConstraint`` 与 ``CheckConstraint`` 要在与运行时同一条口径下生效，
    否则「迁移建出来的库」与「``create_all`` 建出来的库」会在一处看不见的地方不同。
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    """全部 **28** 张表的声明基类（张数由 Plan 02 / Plan 03 / Plan 05A / Plan 06 逐 Task 递增：15 → 18 → 25 → 26 → 27 → 28，归属见 :mod:`app.db.models`；⚠️ 本处此前印的「15 张」是 Plan 01 结案时的数，Plan 03 Task 9 实测更正）。

    ``Base.metadata`` 是**模型侧**的唯一真相：表在 :mod:`app.db.models` 里声明一次，
    内存库那一档的 :func:`init_db` 据此 ``create_all``。

    ⚠️ **Plan 06 Task 1 之后它不再是「唯一一份 DDL」**：``backend/migrations/versions/``
    下那条基线迁移是第二份，而它**必须**手工同步——改模型不写迁移，磁盘库就永远停在旧结构，
    而内存库（测试）已经变了，于是「测试全绿、甲方现场 500」。
    这一份漂移由两条守卫挡着，都不靠人眼：

    * ``tests/db/test_migration_baseline.py`` —— 「``alembic upgrade head`` 建出来的库」
      与「``create_all`` 建出来的库」逐表逐列逐索引逐唯一约束逐外键一致；
    * ``tests/db/test_migration_chain.py`` —— 在 head 上跑一次 autogenerate 比较，
      **应当无 diff**；有 diff 就是「改了模型没写迁移」。

    流程逐字见 spec §13.7。
    """


def engine(url: str) -> Engine:
    """按 URL 造一个引擎。

    ``url`` **没有缺省值**（Plan 02 Task 1，终审 C 组）。此前签名是
    ``def engine(url: str = "sqlite:///pe.db")``，那个字面量是
    :data:`app.config.DEFAULT_DB_URL` 的**第二个所有者**，而且是**相对路径**的那一个：
    ``sqlite:///pe.db`` 由 CWD 决定落在哪个文件，从仓库根跑与从 ``backend/`` 跑会得到两个
    不同的库，而两个都不报错——只是其中一个永远是空的（Plan01 Ruling 190 要消除的正是
    这个形状）。缺省值删掉之后，「用哪个库」这个问题只能由调用方回答，而三个 CLI
    （``app.seed.generate`` / ``app.pipeline.daily`` / ``app.pipeline.backfill``）都已经
    显式传 :data:`app.config.DEFAULT_DB_URL`。

    **删缺省值当天它是死代码**：基线 ``e26347f`` 上 ``git grep -n "engine(" -- backend/app``
    报出的生产调用点只有 3 处（``app/pipeline/backfill.py`` / ``app/pipeline/daily.py`` /
    ``app/seed/generate.py``），全部显式传 URL，没有任何一处依赖缺省值。删它的理由不是
    「今天会错」，而是「它是一个活陷阱」：下一个写 ``engine()`` 的人会静默拿到一个取决于
    CWD 的库。

    ``url`` 缺失时是 ``TypeError``（响亮），不是回退到某个默认库（静默）。
    """
    return create_engine(url)


def _db_file_of(url: URL) -> pathlib.Path | None:
    """``url`` 指向的那个**磁盘**库文件；「没有文件可看」时返回 ``None``。

    返回 ``None`` 的两档，:func:`init_db` 都走 ``create_all`` 快路径：

    ① **内存 SQLite**（``sqlite://``、``sqlite:///:memory:``）。迁移链的三档分支问的是
       「文件在不在 / 里面有没有 ``alembic_version``」，而内存库两问都无意义：它每次都是
       全新的、且活不过一个进程。⚠️ 这一档**就是全部 1340 条测试走的那一条**，
       故它必须是快的（每条测试都跑一次 ``alembic upgrade head`` 会把套件从
       2 分钟拖到不可接受），而「快路径与迁移路径建出同一个 schema」不是假设、
       是 ``tests/db/test_migration_baseline.py`` 的断言。
    ② **非 SQLite 后端**。今天不存在（``app/db/**`` 只有 SQLite 的方言假设，
       例如上面那个 ``PRAGMA`` 钩子），spec §15 把 PostgreSQL 排在第三批。
       ⚠️ 这一档走 ``create_all`` 是一个**已知缺口**：迁移链今天只在 SQLite 上验过，
       真接 PostgreSQL 时必须连它一起接上（``env.py`` 的 ``render_as_batch`` 是
       SQLite 专属的口径，那边要改成 ``False``）。

    判据用的是 ``eng.url`` 这个**已经解析好**的 :class:`~sqlalchemy.engine.URL`
    （``get_backend_name()`` + ``database``），不是子串匹配：``sqlite://``、
    ``sqlite:///:memory:``、``sqlite+aiosqlite:///:memory:`` 三种写法都要认出来
    （与 :func:`app.main._is_memory_sqlite` 同一个理由）。
    ⚠️ **两处口径由 ``tests/db/test_migration_baseline.py`` 钉成一致**：
    那个函数答的是「该不该换 ``StaticPool``」（连接池的事，只关心内存/磁盘），
    本函数答的是「三档分支要看的那个文件在哪」（还要顺带认非 SQLite）。
    两者在「内存库」这一格上重叠，重叠那一格不许漂。
    """
    if url.get_backend_name() != "sqlite":
        return None
    database = url.database
    if database is None or database == ":memory:":
        return None
    return pathlib.Path(database)


def _alembic_config(db_url: str):
    """造一个指向本仓迁移链的 Alembic ``Config``，并把库 URL 交给 ``migrations/env.py``。

    ⚠️ ``alembic`` 一律在**函数体内**导入：模块顶层导入会让「``import app.db.session``」
    顺带加载 alembic + mako，而本模块被全部 1340 条测试间接导入、其中绝大多数走的是
    内存库那条 ``create_all`` 快路径，一辈子用不到迁移。
    """
    from alembic.config import Config

    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes[DB_URL_ATTRIBUTE] = db_url
    return cfg


def _table_columns(eng: Engine, skip: frozenset[str]) -> dict[str, tuple[str, ...]]:
    """``{表名: 排序后的列名元组}``，跳过 ``skip`` 里点名的表（``alembic_version``）。

    ⚠️ 只看**表名与列名**两维，不看类型/索引/约束：这是 :func:`_stamp_unversioned`
    用来判「这份旧库像不像基线」的那把尺子，尺子要的是「会不会让新代码在离真因很远的
    地方 500」，而 500 的两个来源正是缺表与缺列。类型与索引的漂移由
    ``tests/db/test_migration_baseline.py`` 那条更严的一致性测试管（它比的是
    ``upgrade head`` 与 ``create_all`` 两侧，不是旧库）。
    """
    insp = inspect(eng)
    return {
        name: tuple(sorted(column["name"] for column in insp.get_columns(name)))
        for name in sorted(insp.get_table_names())
        if name not in skip
    }


def _assert_shape_matches_revision(eng: Engine, revision: str) -> None:
    """把 ``eng`` 那个既有库的表/列形状与「``revision`` 建出来的库」逐格比对，不一致就抛。

    「``revision`` 建出来的库」是**现算的**：在 ``tempfile`` 下开一个一次性的 SQLite 文件、
    ``upgrade`` 到 ``revision``、再 ``inspect`` 它。⚠️ 刻意**不**拿
    :attr:`Base.metadata` 当基准——那是 **head** 的结构，而本函数要比的是
    **基线**的结构；两者在今天恰好相等（迁移链只有一条），但从第二条迁移起就不等了，
    而那时拿 head 当基准会把一次**合法的**升级判成失败。

    只在 :func:`_stamp_unversioned` 那一档跑，故它那份开销（一次 26 张表的
    ``CREATE TABLE``，实测几十毫秒）一辈子只发生在一个库上**一次**。
    """
    import tempfile

    from alembic import command

    skip = frozenset({ALEMBIC_VERSION_TABLE})
    with tempfile.TemporaryDirectory(prefix="pe-schema-probe-") as tmp:
        probe_db = pathlib.Path(tmp) / "probe.db"
        probe_url = "sqlite:///" + probe_db.as_posix()
        command.upgrade(_alembic_config(probe_url), revision)
        probe_eng = create_engine(probe_url)
        try:
            want = _table_columns(probe_eng, skip)
        finally:
            probe_eng.dispose()

    got = _table_columns(eng, skip)
    if want == got:
        return

    missing = sorted(set(want) - set(got))
    extra = sorted(set(got) - set(want))
    detail = [f"缺表 {missing}" if missing else "", f"多表 {extra}" if extra else ""]
    for name in sorted(set(want) & set(got)):
        if want[name] != got[name]:
            detail.append(
                f"表 {name} 的列不一致：缺 {sorted(set(want[name]) - set(got[name]))}、"
                f"多 {sorted(set(got[name]) - set(want[name]))}"
            )
    raise RuntimeError(
        f"这个库没有 {ALEMBIC_VERSION_TABLE} 表，而它的结构也**不等于**基线迁移 "
        f"{revision} 建出来的结构："
        + "；".join(part for part in detail if part)
        + "。⚠️ 拒绝 stamp：stamp 是「我断言这份库就是基线」，而断言不成立时继续走下去，"
        f"得到的是一个 {ALEMBIC_VERSION_TABLE} 写着基线、结构却不是基线的库——此后每一条"
        "迁移都会在离真因很远的地方炸开。要么这份库比基线更旧（请从备份恢复，或用 "
        "backend/scripts/demo.ps1 重建一份演示库），要么它被人手工改过。"
    )


def _stamp_unversioned(cfg, script, eng: Engine) -> None:
    """档 2：把一个**没有 ``alembic_version`` 表**的既有磁盘库就地纳管（不重建、不丢数据）。

    它做两件事：**先比对、后 stamp**。

    * **stamp 到基线修订、而不是 head**（``script.get_base()``）。语义是：一个没有版本表的
      库，只可能是「引入迁移链之前那版代码用 ``create_all`` 建出来的」，而那版代码的结构
      **按定义**就是基线迁移所描述的结构。stamp 之后紧跟的 ``upgrade head``
      会把基线到 head 之间的每一条迁移照跑一遍——这正是甲方从本版升到下一版时要的事。
    * **stamp 之前先比对结构**（:func:`_assert_shape_matches_revision`）。⚠️ 这一条是
      实现者对计划的**顶回**：计划原文只写「库存在但没有 ``alembic_version`` 表 →
      ``stamp`` 基线」，而那样在「旧库结构与基线不一致」时会**静默错**——stamp 成功、
      ``alembic_version`` 写上基线、结构却还是旧的，此后没有任何一处会再报错。
      比对不过就 :class:`RuntimeError`（失效方向是「起不来」，不是「静默不安全」，
      与 ``demo.ps1`` 那两道禁区守卫同一个姿势）。
    """
    from alembic import command

    # ⚠️ ``ScriptDirectory.get_base()`` 返回的是**修订号字符串**、不是一个 ``Script``
    #    对象（alembic 1.20.0 实测；写成 ``.revision`` 会当场
    #    ``AttributeError: 'str' object has no attribute 'revision'``）。
    #    ⚠️ 迁移链分叉且两支都没有 ``down_revision`` 时它抛 ``alembic.util.CommandError``
    #    （"The script directory has multiple bases"），而 ``versions/`` 被搬空时它返回
    #    ``None``——两档都要的是响亮失败：一条链只能有一个起点，否则「stamp 到哪」
    #    这个问题没有答案；``None`` 传进 ``command.stamp`` 同样会炸，不会静默。
    baseline = script.get_base()
    _assert_shape_matches_revision(eng, baseline)
    command.stamp(cfg, baseline)


def init_db(eng: Engine) -> None:
    """把 ``eng`` 指向的库弄到迁移链的 head。**幂等**，可重复调用。

    ``models`` 在函数体内才导入：它反过来要导入本模块的 :class:`Base`，
    放在模块顶层会构成导入环。

    四条路径（Plan 06 Task 1；三档 + 一条快路径）：

    ==================  ==========================================================
    ``eng`` 指向的库      行为
    ==================  ==========================================================
    内存 / 非 SQLite      ``Base.metadata.create_all``（**快路径**，见
                        :func:`_db_file_of`：全部 1340 条测试走这一条；它与迁移路径
                        建出同一个 schema 由一致性测试钉住）
    文件不存在            ``alembic upgrade head``（**档 1**：建新库，走迁移链、
                        于是新库一出生就带着 ``alembic_version``）
    文件存在、0 字节       同档 1。⚠️ 这一格是实测补的：SQLite 自己就把「零长度文件」
                        当成「一个空库」，而上一次进程被杀在 ``CREATE TABLE`` 中途
                        正好留下这么一个文件；不认它的话，档 2 的比对会看到 0 张表
                        并抛「结构不等于基线」，而正确的处置明明是「当新库建」。
    文件存在、无版本表     ``stamp`` **基线** + ``upgrade head``（**档 2**：甲方手里
                        那份旧库就地纳管，**不重建、不丢数据**；stamp 前先比对结构，
                        见 :func:`_stamp_unversioned`）
    文件存在、有版本表     ``upgrade head``（**档 3**：幂等升到 head；已在 head 时
                        alembic 什么也不做）
    ==================  ==========================================================

    ⚠️ **档 1 与档 3 都不在 ``eng`` 上开连接**：迁移跑在 ``migrations/env.py`` 自己
    ``engine_from_config(...)`` 出来的那个 ``NullPool`` 引擎上。于是
    ``tests/test_main.py::test_module_level_app_uses_the_default_url_without_opening_it``
    那条「import 期不碰库」的性质不受影响，而 ``init_db`` 返回后 ``eng`` 的连接池
    仍然是干净的。

    ⚠️⚠️ **禁区口径一字未改**：``backend/pe.db`` **不得存在**，``backend/data/seed/``
    **恒为 0 文件**。本函数**不会**替你决定用哪个库（``eng`` 是调用方交的），
    但正因为它现在会**建文件**（档 1 的 ``upgrade head`` 与改前的 ``create_all`` 一样
    当场连接），把缺省 URL 指过去就是当场破禁区。重建演示库请走
    ``backend/scripts/demo.ps1``（它第一步就是删旧的 ``pe_demo.db``，并自带两道禁区守卫）；
    确实要用那三个 CLI（``app.seed.generate`` / ``app.pipeline.daily`` /
    ``app.pipeline.backfill``）就**必须**显式传 ``--db-url`` 与 ``--csv-dir``
    （``backend/scripts/demo_bootstrap.py`` 就是这么调的）。
    ⚠️ 那些 CLI 都**没有** ``--recreate`` 开关：删文件比重建索引更诚实，
    而一个「帮你把库删了」的开关本身就是危险动作。**Plan 06 之后更是如此**——
    有了迁移链，「删库」从「升级的必要步骤」降级成「一个只在演示时用的动作」。
    """
    from app.db import models  # noqa: F401  仅为把 29 张表注册进 Base.metadata

    db_file = _db_file_of(eng.url)
    if db_file is None:
        Base.metadata.create_all(eng)
        return

    from alembic import command

    cfg = _alembic_config(eng.url.render_as_string(hide_password=False))
    if not db_file.exists() or db_file.stat().st_size == 0:
        command.upgrade(cfg, "head")
        return

    if not inspect(eng).has_table(ALEMBIC_VERSION_TABLE):
        from alembic.script import ScriptDirectory

        _stamp_unversioned(cfg, ScriptDirectory.from_config(cfg), eng)
    command.upgrade(cfg, "head")

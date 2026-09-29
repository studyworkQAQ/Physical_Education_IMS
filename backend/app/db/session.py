"""数据库引擎、会话与建表入口。

本模块只提供四样东西：声明基类 :class:`Base`、引擎工厂 :func:`engine`、会话类
``Session``、建表函数 :func:`init_db`。14 张表的模型在 :mod:`app.db.models`，
通用读写助手在 :mod:`app.db.repo`。此外在导入时注册一个 ``connect`` 钩子，打开
SQLite 默认关闭的外键强制（见 :func:`_sqlite_foreign_keys_on`）。

``Session`` 直接就是 ``sqlalchemy.orm.Session`` 类本身，而不是绑定了某个引擎的
``sessionmaker`` 实例。调用方（测试、CLI、管道）自己先造引擎、再 ``Session(eng)``：
这样同一份代码既能跑内存库也能跑磁盘库，且不会在导入期就把数据库 URL 钉死——
测试因此不必依赖任何磁盘文件。
"""
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session

__all__ = ["Base", "Session", "engine", "init_db"]


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
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    """全部 14 张表的声明基类。

    ``Base.metadata`` 是建表的唯一真相：表在 :mod:`app.db.models` 里声明一次，
    :func:`init_db` 据此 ``create_all``，不存在第二份需要手工同步的 DDL。
    """


def engine(url: str = "sqlite:///pe.db") -> Engine:
    """按 URL 造一个引擎。缺省落在 ``backend/pe.db``，即演示用的那个库。"""
    return create_engine(url)


def init_db(eng: Engine) -> None:
    """在给定引擎上建出全部表；已存在的表原样跳过，故可重复调用。

    ``models`` 在函数体内才导入：它反过来要导入本模块的 :class:`Base`，
    放在模块顶层会构成导入环。
    """
    from app.db import models  # noqa: F401  仅为把 14 张表注册进 Base.metadata

    Base.metadata.create_all(eng)

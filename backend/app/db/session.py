"""数据库引擎、会话与建表入口。

本模块只提供四样东西：声明基类 :class:`Base`、引擎工厂 :func:`engine`、会话类
``Session``、建表函数 :func:`init_db`。14 张表的模型在 :mod:`app.db.models`，
通用读写助手在 :mod:`app.db.repo`。

``Session`` 直接就是 ``sqlalchemy.orm.Session`` 类本身，而不是绑定了某个引擎的
``sessionmaker`` 实例。调用方（测试、CLI、管道）自己先造引擎、再 ``Session(eng)``：
这样同一份代码既能跑内存库也能跑磁盘库，且不会在导入期就把数据库 URL 钉死——
测试因此不必依赖任何磁盘文件。
"""
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session

__all__ = ["Base", "Session", "engine", "init_db"]


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

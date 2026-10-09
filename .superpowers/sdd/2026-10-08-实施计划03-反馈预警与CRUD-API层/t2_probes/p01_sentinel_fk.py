"""探针：SQLite 在 PRAGMA foreign_keys=ON 下，子表里写「父表不存在的 0」会不会炸。

派单 P3-A1 的决定是「``alert.student_id`` / ``alert.course_section_id`` 都改成
``nullable=False`` + 用 ``0`` 作哨兵」，而这两列在计划的 Interfaces 里都标着 FK。
本探针把那个组合缩到最小可复现形状：一张父表（id 从 1 起自增）+ 一张子表
（NOT NULL 的 FK 列，值写 0）。
"""
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[4] / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import ForeignKey, Integer, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class Parent(Base):
    __tablename__ = "p_parent"
    id: Mapped[int] = mapped_column(primary_key=True)


class Child(Base):
    __tablename__ = "p_child"
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("p_parent.id"), nullable=False)


eng = create_engine("sqlite://")


@event.listens_for(eng, "connect")
def _fk_on(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


Base.metadata.create_all(eng)
with Session(eng) as s:
    print("PRAGMA foreign_keys =", s.execute(text("PRAGMA foreign_keys")).scalar())
    s.add(Parent())
    s.flush()
    print("parent ids =", s.execute(text("select id from p_parent")).scalars().all())
    s.add(Child(parent_id=0))
    try:
        s.flush()
        print("RESULT: parent_id=0 被放行了（哨兵 0 + FK 可行）")
    except Exception as exc:  # noqa: BLE001
        print(f"RESULT: parent_id=0 被拒收 -> {type(exc).__name__}")
        print(f"        orig = {getattr(exc, 'orig', exc)}")

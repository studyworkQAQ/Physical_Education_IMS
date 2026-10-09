"""P5-A1 / A3 / A6 / A4 的 schema 变更取证（Plan 03 Task 5）。

一律运行时口径（硬规矩 #89）：nullable 从 SQLAlchemy 的 Column 对象读，取值域从
_in_domain 生成的约束文本反解（与 test_models.py 的 _in_domain_columns 同一个办法，
但这里独立实现一遍，免得「取证脚本与被测断言同源」）。
"""
import pathlib
import re
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app import config                                    # noqa: E402
from app.db import models as _all_models                  # noqa: E402,F401  触发全部子模块导入
from app.db.models.feedback import ClassSession, TrainingLog  # noqa: E402
from app.db.session import Base                            # noqa: E402

print("=== P5-A4: config ===")
print("TIMEZONE:", repr(config.TIMEZONE))
print("__all__:", config.__all__)
print("DEFAULT_DB_URL endswith pe.db:", config.DEFAULT_DB_URL.endswith("/backend/pe.db"))

print()
print("=== P5-A1: batch_id 的可空性（全部九张带 batch_id 的表）===")
for name, table in sorted(Base.metadata.tables.items()):
    if "batch_id" in table.c:
        col = table.c["batch_id"]
        fks = [fk.target_fullname for fk in col.foreign_keys]
        print(f"  {name:22s} nullable={col.nullable!s:5s} index={col.index!s:5s} fk={fks}")

print()
print("=== P5-A6: ClassSession 的类常量与 rpe_token 列宽 ===")
constants = sorted(
    k for k, v in vars(ClassSession).items()
    if not k.startswith("_") and isinstance(v, (int, str, float, bool, set, frozenset, tuple))
)
print("class constants:", constants)
print("RPE_TOKEN_LEN:", ClassSession.RPE_TOKEN_LEN)
print("rpe_token column length:", ClassSession.rpe_token.property.columns[0].type.length)
print("两者相等:", ClassSession.RPE_TOKEN_LEN
      == ClassSession.rpe_token.property.columns[0].type.length)
# token_urlsafe(n) 的字符数 = ceil(n*4/3) 去掉 padding；12 字节 → 16 字符
import secrets  # noqa: E402
nbytes = ClassSession.RPE_TOKEN_LEN * 3 // 4
sample = secrets.token_urlsafe(nbytes)[: ClassSession.RPE_TOKEN_LEN]
print(f"token_urlsafe({nbytes})[:{ClassSession.RPE_TOKEN_LEN}] 实到长度:", len(sample))
print("样例:", sample)

print()
print("=== P5-A3: TrainingLog.SOURCES 与它的 CHECK ===")
print("SOURCES:", sorted(TrainingLog.SOURCES))
print("FEELINGS:", sorted(TrainingLog.FEELINGS))
checks = {
    c.name: str(c.sqltext)
    for c in TrainingLog.__table__.constraints
    if type(c).__name__ == "CheckConstraint"
}
for k in sorted(checks):
    print(f"  {k} -> {checks[k]}")
longest = max(TrainingLog.SOURCES, key=len)
width = TrainingLog.__table__.c.source.type.length
print(f"最长值 {longest!r}({len(longest)}) vs 列宽 {width}: 够宽={len(longest) <= width}")

print()
print("=== training_log 的全部列（顺序 = Read 模型必须对齐的顺序）===")
cols = [c.name for c in TrainingLog.__table__.columns]
print(len(cols), cols)
print("submitted_at nullable:", TrainingLog.__table__.c.submitted_at.nullable,
      " default:", TrainingLog.__table__.c.submitted_at.default,
      " server_default:", TrainingLog.__table__.c.submitted_at.server_default)

print()
print("=== _in_domain 生成的约束总列数（独立反解一遍）===")
pat = re.compile(r"^\s*(\w+) IN \((.*)\)\s*$")
found = []
for table in Base.metadata.tables.values():
    for c in table.constraints:
        if type(c).__name__ != "CheckConstraint":
            continue
        m = pat.match(str(c.sqltext))
        if m:
            found.append((table.name, m.group(1)))
print("count:", len(found))
print("has training_log.source:", ("training_log", "source") in found)

print()
print("=== 表数 / 模型公有面 ===")
print("tables:", len(Base.metadata.tables))

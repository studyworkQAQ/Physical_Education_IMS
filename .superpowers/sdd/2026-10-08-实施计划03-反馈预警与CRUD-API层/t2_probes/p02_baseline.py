"""探针：行尾口径 + 运行时基线数字（硬规矩 #89：数行尾用 read_bytes()，数字段用运行时）。"""
import pathlib
import subprocess
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[4] / "backend"
sys.path.insert(0, str(BACKEND))

TARGETS = (
    "app/db/models/feedback.py",
    "app/db/models/ops.py",
    "app/db/models/__init__.py",
    "app/db/models/prescription.py",
    "app/db/models/_shared.py",
    "app/db/models/assessment.py",
    "app/db/repo.py",
    "app/pipeline/daily.py",
    "app/pipeline/prescription_stage.py",
    "app/main.py",
    "tests/db/test_models.py",
    "tests/seed/test_generate.py",
    "tests/test_main.py",
    "tests/api/conftest.py",
)

print("core.autocrlf =", subprocess.run(
    ["git", "config", "core.autocrlf"], cwd=BACKEND, capture_output=True, text=True
).stdout.strip() or "(unset)")
print()
print(f"{'file':52s} {'bytes':>8s} {'CRLF':>6s} {'bareLF':>7s}")
for rel in TARGETS:
    raw = (BACKEND / rel).read_bytes()
    crlf = raw.count(b"\r\n")
    bare = raw.count(b"\n") - crlf
    print(f"{rel:52s} {len(raw):8d} {crlf:6d} {bare:7d}")

print()
from app.db.session import Base  # noqa: E402
from app.db import models  # noqa: E402,F401  (register all tables)

tables = Base.metadata.tables
print("len(Base.metadata.tables) =", len(tables))
print("tables =", sorted(tables))
json_cols = sorted(
    f"{t.name}.{c.name}" for t in tables.values() for c in t.columns
    if type(c.type).__name__ == "JsonText"
)
print("len(json_text_columns) =", len(json_cols))
batch_owned = sorted(n for n, t in tables.items() if "batch_id" in set(t.c.keys()))
print("batch_owned =", len(batch_owned), batch_owned)
fk_total = sum(len(c.foreign_keys) for t in tables.values() for c in t.columns)
print("total foreign keys =", fk_total)
_IN_DOMAIN_SQL = __import__("re").compile(r"^\s*(\w+) IN \((.*)\)\s*$")
in_domain = sorted(
    (t.name, _IN_DOMAIN_SQL.match(str(c.sqltext)).group(1))
    for t in tables.values() for c in t.constraints
    if type(c).__name__ == "CheckConstraint" and _IN_DOMAIN_SQL.match(str(c.sqltext))
)
print("len(in_domain_columns) =", len(in_domain))
print("check_constraints_without_in_domain =", sorted(
    f"{t.name}:{c.name}" for t in tables.values() for c in t.constraints
    if type(c).__name__ == "CheckConstraint" and not _IN_DOMAIN_SQL.match(str(c.sqltext))
))
print("public names =", len([n for n in dir(models) if not n.startswith('_')]))
print("len(models.__all__) =", len(models.__all__))

"""终验探针：扫描面、三个指纹、禁区、行尾、公有导入面、7 张表的形状。

全部用运行时口径（硬规矩 #89），一个数都不从源码正则里数。
"""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# ---- 1. 架构守卫的扫描面 -------------------------------------------------
SCANNED_DIRS = ("pipeline", "db", "domain", "api")
total = 0
for name in SCANNED_DIRS:
    files = sorted((BACKEND / "app" / name).rglob("*.py"))
    print(f"  app/{name:9s} {len(files):3d} 个 .py")
    total += len(files)
print(f"扫描面合计 = {total}（基线 38）")

# ---- 2. 三个指纹 ---------------------------------------------------------
def _sha(path: pathlib.Path) -> str:
    """sha256 前 16 位大写，**行尾归一化为 LF 之后**算（与 tests/test_refdata.py 同口径）。"""
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()[:16].upper()

csv_dir = BACKEND / "data"
csv_files = sorted(p for p in csv_dir.rglob("*.csv"))
print("\n=== backend/data ===")
for p in sorted(csv_dir.rglob("*")):
    if p.is_file():
        print(f"  {p.relative_to(BACKEND).as_posix():52s} {len(p.read_bytes()):8d} B  {_sha(p)}")

# ---- 3. 禁区 -------------------------------------------------------------
for forbidden in ("backend/pe.db", "backend/pe.db-journal", "backend/pe.db-wal"):
    p = ROOT / forbidden
    print(f"{forbidden}: {'存在（!!）' if p.exists() else '不存在 OK'}")
seed_dir = BACKEND / "data" / "seed"
print(f"backend/data/seed/: {'存在（!!）' if seed_dir.exists() else '不存在 OK'}")

# ---- 4. git diff on backend/data -----------------------------------------
diff = subprocess.run(
    ["git", "diff", "--stat", "bcf3936", "HEAD", "--", "backend/data"],
    cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
)
print(f"\ngit diff bcf3936 HEAD -- backend/data 输出长度 = {len(diff.stdout.strip())}"
      f"（应为 0）: {diff.stdout.strip()!r}")
ops = subprocess.run(
    ["git", "diff", "--stat", "bcf3936", "HEAD", "--", "backend/app/db/models/ops.py"],
    cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
)
print(f"git diff bcf3936 HEAD -- ops.py 输出长度 = {len(ops.stdout.strip())}（应为 0）")

# ---- 5. 公有导入面 / 子模块 / __all__ ------------------------------------
from app.db import models  # noqa: E402
from app.db.session import Base  # noqa: E402

public = sorted(n for n in dir(models) if not n.startswith("_"))
submodules = sorted(n for n in public if n in {
    "organisation", "assessment", "derived", "prescription", "feedback", "ops"})
print(f"\nmodels 公有名 = {len(public)}（= 基线 {len(public) - len(submodules)} + "
      f"子模块 {len(submodules)}）；子模块 = {submodules}")
print(f"len(models.__all__) = {len(models.__all__)}（应为 14）")

# ---- 6. 七张新表的形状（运行时口径）--------------------------------------
from app.db.models.feedback import (  # noqa: E402
    Alert, ClassSession, MiniTest, Notification, RpeRecord, TrainingLog,
    WeeklyClassReport,
)

print("\n=== 7 张新表 ===")
for model in (ClassSession, RpeRecord, TrainingLog, MiniTest, Alert, Notification,
              WeeklyClassReport):
    table = model.__table__
    columns = list(table.columns)
    constraints = sorted(
        f"{type(c).__name__}:{c.name}" for c in table.constraints
        if c.name and type(c).__name__ in ("UniqueConstraint", "CheckConstraint")
    )
    indexes = sorted(i.name for i in table.indexes if i.name)
    fks = sum(len(c.foreign_keys) for c in columns)
    print(f"\n{model.__tablename__}  列数={len(columns)}  外键={fks}  索引={indexes}")
    for c in columns:
        default = "—" if c.default is None else repr(c.default.arg)
        length = getattr(c.type, "length", None)
        type_name = type(c.type).__name__
        if length is not None:
            type_name = f"{type_name}({length})"
        fk = "".join(f" FK->{f.target_fullname}"
                     + (f"[ON DELETE {f.ondelete}]" if f.ondelete else "")
                     for f in c.foreign_keys)
        print(f"   {c.name:24s} {type_name:16s} "
              f"{'NULL' if c.nullable else 'NOT NULL':9s} default={default:8s}{fk}")
    for name in constraints:
        print(f"   约束 {name}")

# ---- 7. weekly_adjustment 的新约束 ---------------------------------------
from app.db.models.prescription import WeeklyAdjustment  # noqa: E402

print("\n=== weekly_adjustment ===")
print("  约束:", sorted(f"{type(c).__name__}:{c.name}"
                        for c in WeeklyAdjustment.__table__.constraints if c.name))
print("  列数:", len(list(WeeklyAdjustment.__table__.columns)))

"""控制者亲验 Task 5 fix round 1：F1-1 / F1-2 的承重结论 + 一条变异复跑（.pyc 安全）。"""
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

print("### 1. F1-1 weekly_volume_base 的新形状")
from app.domain.indicators import Sex  # noqa: E402
from app.domain.prescription.assembler import StudentProfile, assemble  # noqa: E402
from app.refdata_prescription import exercises, templates  # noqa: E402

lib = exercises()
tpls = templates()
prof = StudentProfile(student_id=1, sex=Sex.MALE, birth=dt.date(2006, 5, 20),
                      age=20, endurance_score=50.0, bmi=31.0, body_fat_pct=None,
                      muscle_mass_kg=None, muscle_p10=None, measured_hrmax=None)
pkg = assemble(prof, tpls["RED-END-ABN-01"], dt.date(2026, 10, 8), exercises=lib)
snap = pkg.assembly_snapshot
wvb = snap["weekly_volume_base"]
print(f"  键数 = {len(snap)}   (必须 12)")
print(f"  weekly_volume_base = {dict(wvb)}   type = {type(wvb).__name__}")
print(f"  MRO = {[c.__name__ for c in type(wvb).__mro__[:4]]}")
print(f"  json.dumps(allow_nan=False) 通过? ", end="")
try:
    s = json.dumps(snap, allow_nan=False, sort_keys=True, default=str)
    print(f"是（{len(s)} 字符）")
except TypeError as e:
    print(f"否 -> {e}")
print("  只读性：", end="")
for op in ("__setitem__", "__delitem__", "pop", "update", "clear", "setdefault",
           "popitem", "__ior__"):
    print(f"{op}={'有' if hasattr(wvb, op) else '无'}", end=" ")
print()
try:
    wvb["min"] = 0.0
    print("  ⚠️ 可写！只读性不成立")
except Exception as e:
    print(f"  写入被拒 -> {type(e).__name__}: {e}")

print()
print("### 2. 18 套模板的 weekly_volume_base 键集分布")
import collections  # noqa: E402
dist = collections.Counter()
for tid in sorted(tpls):
    t = tpls[tid]
    p = StudentProfile(student_id=1, sex=Sex.MALE, birth=dt.date(2006, 5, 20), age=20,
                       endurance_score=70.0, bmi=22.0, body_fat_pct=None,
                       muscle_mass_kg=None, muscle_p10=None, measured_hrmax=None)
    k = tuple(sorted(assemble(p, t, dt.date(2026, 10, 8), exercises=lib)
                     .assembly_snapshot["weekly_volume_base"]))
    dist[k] += 1
print(f"  {dict(dist)}")

print()
print("### 3. F1-2 RPE 值域")
import re  # noqa: E402
for rel in ("app/domain/prescription/intensity.py", "app/domain/prescription/assembler.py",
            "app/domain/prescription/templates.py"):
    src = (BACKEND / rel).read_text(encoding="utf-8")
    hits = [(i + 1, l.strip()[:100]) for i, l in enumerate(src.split("\n"))
            if re.search(r"6.20|Borg", l)]
    print(f"  {rel}: 6-20/Borg 命中 {len(hits)}")
    for n, l in hits:
        print(f"     :{n} {l}")
print("  rpe 值域校验亲测：", end="")
from app.domain.prescription.templates import Intensity  # noqa: E402
from app.domain.prescription.assembler import AssembledBlock  # noqa: E402
import app.domain.prescription.assembler as ASM  # noqa: E402
cands = [n for n in dir(ASM) if "render" in n.lower() or "intensity" in n.lower()]
print(f"assembler 里含 render/intensity 的名字 = {cands}")

print()
print("### 4. domain 纯净性亲扫（math / types / json / os）")
import ast  # noqa: E402
for name in ("intensity", "assembler", "safety", "override"):
    p = BACKEND / "app" / "domain" / "prescription" / f"{name}.py"
    src = p.read_text(encoding="utf-8")
    tree = ast.parse(src)
    imps = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imps |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            imps.add((n.module or "") if n.level == 0 else f"<L{n.level}>{n.module or ''}")
    print(f"  {name:11s} sha16={hashlib.sha256(src.encode()).hexdigest()[:16].upper()} "
          f"imports={sorted(imps)}")

print()
print("### 5. 公开面 + 指纹")
import app.domain.prescription as PKG  # noqa: E402
print(f"  len(__all__) = {len(PKG.__all__)}   (必须 43)")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "3DE598AF38631209"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301")):
    b = (BACKEND / rel).read_bytes()
    got = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    print(f"  {rel:40s} {len(b):7d} B  {got}  {'OK' if got == want else 'MISMATCH!'}")
print(f"  pe.db 存在? {(BACKEND/'pe.db').exists()}")

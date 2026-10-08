# -*- coding: utf-8 -*-
"""Task 5 fix round 1 的实现者自验（口径照控制者的 ``_t5_verify.py``，加本轮的新格）。

只读：不改任何文件。
"""
import ast
import datetime as dt
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

MODULES = ("intensity", "assembler", "safety", "override")


def sha16(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16].upper()


print("### 1. 公开面与扫描面")
import app.domain.prescription as PKG  # noqa: E402
print(f"  len(__all__) = {len(PKG.__all__)}   len(set) = {len(set(PKG.__all__))}  (基线 43)")
scan = {sub: len(list((BACKEND / "app" / sub).rglob("*.py"))) for sub in ("domain", "pipeline", "db")}
print(f"  扫描面 = {scan}  合计 = {sum(scan.values())}  (基线 32)")

print()
print("### 2. 禁区")
EXPECT = {
    "data/national_standard_2014.csv": "D2C8E539E2FA0029",
    "data/exercises.yaml": "3DE598AF38631209",
    "data/exercise_equivalence.yaml": "822CB86A5E998301",
}
for rel, want in EXPECT.items():
    b = (BACKEND / rel).read_bytes()
    got = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    print(f"  {rel:42s} {len(b):7d} B  sha16={got}  {'OK' if got == want else 'MISMATCH!'}")
print(f"  backend/pe.db 存在? {(BACKEND / 'pe.db').exists()}   (必须 False)")
seed = BACKEND / "data" / "seed"
print(f"  backend/data/seed/ 文件数 = "
      f"{len([p for p in seed.rglob('*') if p.is_file()]) if seed.exists() else 'DIR-ABSENT'}")
tpl = sorted((BACKEND / "data" / "prescription").glob("*.yaml"))
print(f"  模板 YAML 数 = {len(tpl)}  总字节 = {sum(p.stat().st_size for p in tpl)}")

print()
print("### 3. 四个新模块：sha256 / import 面 / 违规扫描")
BAD_MOD = {"sqlalchemy", "fastapi", "requests", "httpx", "pydantic_settings", "random",
           "math", "os", "sys", "json", "pathlib", "datetime", "types", "copy", "pickle"}
BAD_CALL = {"now", "today", "time"}
for name in MODULES:
    p = BACKEND / "app" / "domain" / "prescription" / f"{name}.py"
    raw = p.read_bytes()
    src = raw.decode("utf-8")
    tree = ast.parse(src)
    imports = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            imports.add(("." * n.level) + (n.module or ""))
    bad = {m for m in imports if m.split(".")[0] in BAD_MOD}
    attrs = {f"{ast.unparse(v.value)}.{v.attr}" for v in ast.walk(tree)
             if isinstance(v, ast.Attribute)}
    badattr = {a for a in attrs if a.split(".")[-1] in BAD_CALL}
    crlf = raw.count(b"\r\n")
    print(f"  {name:10s} {len(raw):6d} B  sha256[:16]={hashlib.sha256(raw).hexdigest()[:16].upper()}"
          f"  lines={len(src.splitlines())}  CRLF={crlf}")
    print(f"             imports={sorted(imports)}")
    print(f"             违规模块={sorted(bad) or '无'}  违规调用={sorted(badattr) or '无'}")

print()
print("### 4. F1-1：weekly_volume_base 的新类型与那个例子")
from app.domain.indicators import Sex  # noqa: E402
from app.domain.prescription.assembler import (  # noqa: E402
    VOLUME_UNITS, StudentProfile, assemble)
from app.domain.prescription.safety import SafetyInput, apply_safety  # noqa: E402
from app.refdata_prescription import equivalence, exercises, templates  # noqa: E402

lib, store = exercises(), templates()
prof = StudentProfile(student_id=1, sex=Sex.MALE, birth=dt.date(2006, 5, 20), age=20,
                      endurance_score=50.0, bmi=31.0, body_fat_pct=None,
                      muscle_mass_kg=None, muscle_p10=None, measured_hrmax=None)
pkg = assemble(prof, store["RED-END-ABN-01"], dt.date(2026, 10, 8), exercises=lib)
snap = pkg.assembly_snapshot
base = snap["weekly_volume_base"]
print(f"  键数 = {len(snap)}   键序 = {tuple(snap)}")
print(f"  type(weekly_volume_base) = {type(base).__name__}  MRO = "
      f"{[c.__name__ for c in type(base).__mro__[:4]]}")
print(f"  值 = {dict(base)!r}   逐字面 = {base['min']} / {base['reps']}")
print(f"  键集 ⊆ VOLUME_UNITS = {set(base) <= set(VOLUME_UNITS)}   "
      f"含 'unspecified' = {'unspecified' in base}")
print(f"  isinstance(base, dict) = {isinstance(base, dict)}   "
      f"isinstance(base, float) = {isinstance(base, float)}")
print(f"  json.dumps(snap, allow_nan=False) 成功? ", end="")
try:
    text = json.dumps(snap, allow_nan=False, ensure_ascii=False)
    print(f"是（{len(text)} 字符）")
    print(f"     片段 = ...{text[text.index(chr(34) + 'weekly_volume_base'):]!r}")
except (TypeError, ValueError) as exc:
    print(f"否：{type(exc).__name__}: {exc}")

print("  18 套的键集分布：")
dist = {}
for tid in sorted(store):
    b = assemble(prof, store[tid], dt.date(2026, 10, 8),
                 exercises=lib).assembly_snapshot["weekly_volume_base"]
    dist.setdefault(tuple(b), []).append((tid, dict(b)))
for keyset, rows in dist.items():
    print(f"     {keyset}: {len(rows)} 套   例 {rows[0]}")

print()
print("### 5. F1-1：apply_safety 之后的 15 键快照同样能 JSON 化")
outcome = apply_safety(
    assemble(prof, store["RED-END-ABN-01"], dt.date(2026, 10, 8), exercises=lib),
    SafetyInput(bmi=31.0, muscle_mass_kg=24.0, muscle_p10=25.0, body_fat_abnormal=True),
    equivalence(), template=store["RED-END-ABN-01"], exercises=lib)
s15 = outcome.package.assembly_snapshot
print(f"  键数 = {len(s15)}  键序 = {tuple(s15)}")
print(f"  weekly_volume_base = {dict(s15['weekly_volume_base'])!r}  "
      f"type = {type(s15['weekly_volume_base']).__name__}")
print(f"  safety_triggers = {s15['safety_triggers']}  "
      f"safety_volume_factor = {s15['safety_volume_factor']!r}")
t15 = json.dumps(s15, allow_nan=False, ensure_ascii=False)
print(f"  json.dumps(15 键, allow_nan=False) 成功（{len(t15)} 字符）")
print(f"  round-trip 后 weekly_volume_base 的类型 = "
      f"{type(json.loads(t15)['weekly_volume_base']).__name__}")

print()
print("### 6. F1-2：rpe 的值域")
import dataclasses  # noqa: E402
from app.domain.prescription.templates import Intensity  # noqa: E402

tpl = store["RED-END-ABN-01"]
sess = tpl.sessions[0]
for value in (-0.1, 0.0, 7.0, 10.0, 10.1, 13.0):
    blk = dataclasses.replace(sess.blocks[0], intensity=Intensity(type="rpe", value=value))
    t2 = dataclasses.replace(tpl, sessions=(dataclasses.replace(sess, blocks=(blk,)),))
    try:
        got = assemble(prof, t2, dt.date(2026, 10, 8), exercises=lib)
        print(f"  rpe value={value:6} -> OK  intensity_text="
              f"{got.weeks[0].sessions[0].blocks[0].intensity_text!r}")
    except ValueError as exc:
        print(f"  rpe value={value:6} -> ValueError（消息前 60 字）：{str(exc)[:60]}…")

print()
print("### 7. 两处签名扩参（控制者第 5/6 次采纳）")
for name, fn in (("safety", "apply_safety"), ("override", "apply_overrides"),
                 ("assembler", "assemble")):
    p = BACKEND / "app" / "domain" / "prescription" / f"{name}.py"
    tree = ast.parse(p.read_text(encoding="utf-8"))
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == fn:
            a = n.args
            pos = [x.arg for x in a.posonlyargs] + [x.arg for x in a.args]
            kw = [x.arg for x in a.kwonlyargs]
            ret = ast.unparse(n.returns) if n.returns else "?"
            print(f"  {name}.{fn}({', '.join(pos)}"
                  f"{', *, ' + ', '.join(kw) if kw else ''}) -> {ret}")

print()
print("### 8. 控制者实算的那几个算例仍逐格命中")
w1, w4 = pkg.weeks[0], pkg.weeks[3]
b1 = {b.exercise_ref: b for b in w1.sessions[0].blocks}
b4 = {b.exercise_ref: b for b in w4.sessions[0].blocks}
print(f"  interval_run 第 1 周 = {b1['interval_run'].weekly_volume} (期望 38.4)  "
      f"第 4 周 = {b4['interval_run'].weekly_volume} (期望 32.6)")
print(f"  compound_circuit 第 1 周 = {b1['compound_circuit'].weekly_volume} (期望 96.0)  "
      f"第 4 周 = {b4['compound_circuit'].weekly_volume} (期望 81.6)")
print(f"  hr_zone = {b1['interval_run'].hr_zone} (期望 (116, 136))")
print(f"  volume_factor = {snap['volume_factor']} (期望 0.8)  "
      f"band = {snap['volume_factor_band']!r} (期望 'low')")
sys.exit(0)

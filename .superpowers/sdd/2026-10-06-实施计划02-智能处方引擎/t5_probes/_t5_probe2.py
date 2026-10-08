"""新 Task 5 预检 probe 2：把计划 5.2/5.3 里「没说清从哪来」的东西全部实测出来。"""
import collections
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import yaml  # noqa: E402

from app.domain.indicators import ITEM_BUCKET  # noqa: E402
from app.domain.prescription import exercises as EX  # noqa: E402
from app.domain.prescription import templates as TP  # noqa: E402

print("### A. templates.py / exercises.py 的模块级带注解常量")
for mod in (TP, EX):
    print(f"  -- {mod.__name__}")
    for name in dir(mod):
        if name.isupper() and not name.startswith("_"):
            v = getattr(mod, name)
            print(f"     {name} = {sorted(v) if isinstance(v, (frozenset, set)) else v}")

print()
print("### B. __init__.py 的公开面")
import app.domain.prescription as PKG  # noqa: E402
print(f"  len(__all__) = {len(PKG.__all__)}")
print(f"  {sorted(PKG.__all__)}")

print()
print("### C. 18 套模板 YAML 的实际形状")
pdir = BACKEND / "data" / "prescription"
files = sorted(pdir.glob("*.yaml"))
print(f"  文件数 = {len(files)}")
raw0 = yaml.safe_load(files[0].read_text(encoding="utf-8"))
print(f"  顶层键（{files[0].name}）= {sorted(raw0)}")


def walk(d, pre=""):
    out = []
    if isinstance(d, dict):
        for k, v in d.items():
            out.extend(walk(v, f"{pre}.{k}" if pre else str(k)))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            out.extend(walk(v, f"{pre}[]"))
    else:
        out.append(pre)
    return out


paths = collections.Counter()
for f in files:
    for p in walk(yaml.safe_load(f.read_text(encoding="utf-8"))):
        paths[p] += 1
print("  全部 YAML 里出现过的路径（路径 -> 出现次数）：")
for p, c in sorted(paths.items()):
    print(f"     {p:52s} {c}")

print()
print("### D. block 的 structure 键集 与 intensity 形状（这是计划 5.2 第 3 步「模板基准量」的唯一可能来源）")
struct_keys = collections.Counter()
inten_shapes = collections.Counter()
inten_by_layer = collections.defaultdict(set)
nblocks = 0
addon_whens = collections.Counter()
addon_modules = collections.Counter()
for f in files:
    d = yaml.safe_load(f.read_text(encoding="utf-8"))
    layer = d["dimensions"]["layer"] if "dimensions" in d else d.get("layer")
    for s in d["sessions"]:
        for b in s["blocks"]:
            nblocks += 1
            for k in b["structure"]:
                struct_keys[k] += 1
            it = b["intensity"]
            shape = (it["type"], tuple(sorted(k for k in it if k != "type" and it[k] is not None)))
            inten_shapes[shape] += 1
            inten_by_layer[layer].add(it["type"])
    for a in d.get("addons", []):
        addon_whens[a["when"]] += 1
        addon_modules[a["module"]] += 1

print(f"  block 总数 = {nblocks}")
print(f"  structure 键集（键 -> 出现次数）：")
for k, c in struct_keys.most_common():
    print(f"     {k:28s} {c}")
print(f"  intensity 形状（(type, 非空附加键) -> 次数）：")
for k, c in inten_shapes.most_common():
    print(f"     {str(k):52s} {c}")
print(f"  按层的 intensity.type：")
for lay in sorted(inten_by_layer):
    print(f"     {lay:8s} {sorted(inten_by_layer[lay])}")
print(f"  addons.when 取值：{dict(addon_whens)}")
print(f"  addons.module 取值：{dict(addon_modules)}")

print()
print("### E. ADDON_TRIGGERS / EQUIVALENCE_TRIGGERS 与 addons.when 是否对得上")
print(f"  TP.ADDON_TRIGGERS   = {sorted(TP.ADDON_TRIGGERS)}")
print(f"  EX.EQUIVALENCE_TRIGGERS = {sorted(EX.EQUIVALENCE_TRIGGERS)}")
print(f"  YAML addons.when 实际值 = {sorted(addon_whens)}")

print()
print("### F. ITEM_BUCKET 里 endurance 桶的成员（5.2 三档系数的输入）")
for k, v in ITEM_BUCKET.items():
    print(f"     {k:22s} -> {v}")

print()
print("### G. exercise_equivalence.yaml 的 volume_reduction 实际值")
eq = yaml.safe_load((BACKEND / "data" / "exercise_equivalence.yaml").read_text(encoding="utf-8"))
print(f"  顶层键 = {sorted(eq)}")
print(f"  version = {eq['version']!r}  (type={type(eq['version']).__name__})")
print(f"  volume_reduction = {eq['volume_reduction']}")
print(f"  mappings 数 = {len(eq['mappings'])}")
print(f"  两个系数相乘 = {eq['volume_reduction']['bmi_over_30'] * eq['volume_reduction']['muscle_low_p10']}")

print()
print("### H. domain 纯净性守卫会不会拦 math / dataclasses.replace")
g = (BACKEND / "tests" / "architecture" / "test_domain_purity.py").read_text(encoding="utf-8")
import re  # noqa: E402
for name in ("FORBIDDEN", "ALLOW", "_MODULES", "deny", "allow"):
    for m in re.finditer(rf"^{name}\w*\s*[:=].*$", g, re.M):
        print(f"  purity: {m.group(0)[:200]}")
print(f"  purity 里出现 'math' 的行：")
for i, l in enumerate(g.split("\n")):
    if "math" in l:
        print(f"     :{i+1} {l.strip()[:150]}")

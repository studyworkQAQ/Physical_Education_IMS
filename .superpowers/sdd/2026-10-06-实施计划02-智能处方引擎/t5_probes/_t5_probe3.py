"""新 Task 5 预检 probe 3：把 P5-A1/A4/A7 三条 Critical/Important 钉死。"""
import collections
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import yaml  # noqa: E402

print("### A. 每个 block 的 structure 键集组合（决定 weekly_volume 能不能算出来）")
combos = collections.Counter()
examples = {}
for f in sorted((BACKEND / "data" / "prescription").glob("*.yaml")):
    d = yaml.safe_load(f.read_text(encoding="utf-8"))
    for s in d["sessions"]:
        for b in s["blocks"]:
            k = tuple(sorted(b["structure"]))
            combos[k] += 1
            examples.setdefault(k, (f.name, b["exercise_ref"], dict(b["structure"])))
for k, c in combos.most_common():
    print(f"  {c:4d}  {k}")
    print(f"        例：{examples[k][0]} / {examples[k][1]} / {examples[k][2]}")

print()
print("### B. 同一模板内同一 exercise_ref 是否跨 session 重复（决定 weekly_volume 要不要累加）")
dup = 0
for f in sorted((BACKEND / "data" / "prescription").glob("*.yaml")):
    d = yaml.safe_load(f.read_text(encoding="utf-8"))
    refs = [b["exercise_ref"] for s in d["sessions"] for b in s["blocks"]]
    cnt = collections.Counter(refs)
    repeated = {r: n for r, n in cnt.items() if n > 1}
    if repeated:
        dup += 1
        print(f"  {f.name}: 一周内重复的 ref = {repeated}")
print(f"  有重复的模板数 = {dup} / 18")

print()
print("### C. session 数 vs weekly_frequency（决定「一周的课表」这个读法对不对）")
for lay in ("red", "yellow", "green"):
    rows = []
    for f in sorted((BACKEND / "data" / "prescription").glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        if d["layer"] == lay:
            rows.append((len(d["sessions"]), d["weekly_frequency"],
                         [s["day"] for s in d["sessions"]]))
    print(f"  {lay:7s} 模板数={len(rows)} (session数, weekly_frequency) 的 distinct = "
          f"{sorted({(a, b) for a, b, _ in rows})}")
    print(f"          day 取值例：{rows[0][2]}")

print()
print("### D. 两份架构守卫的 ALLOWED_MODULES（math 在不在里面）")
for name in ("test_domain_purity.py", "test_layering.py"):
    p = BACKEND / "tests" / "architecture" / name
    src = p.read_text(encoding="utf-8")
    print(f"  -- {name}  ({len(src.encode('utf-8'))} B)")
    lines = src.split("\n")
    for i, l in enumerate(lines):
        if "ALLOWED_MODULES" in l or "FORBIDDEN" in l:
            # 打印该常量整体（到闭合括号）
            j = i
            while j < len(lines) and "})" not in lines[j] and "}" not in lines[j]:
                j += 1
            print("     " + "\n     ".join(x.rstrip() for x in lines[i:j + 1]))
            break
    print(f"     含 'math' 的行数 = {sum(1 for l in lines if 'math' in l)}")

print()
print("### E. 扫描面（domain 模块数）实测")
dom = sorted((BACKEND / "app" / "domain").rglob("*.py"))
print(f"  app/domain 下 .py 文件数 = {len(dom)}")
for p in dom:
    print(f"     {p.relative_to(BACKEND).as_posix()}")
for sub in ("pipeline", "db"):
    n = len(list((BACKEND / "app" / sub).rglob("*.py")))
    print(f"  app/{sub} 下 .py 文件数 = {n}")

print()
print("### F. 公开面基线测试的实际大小")
p = BACKEND / "tests" / "test_refdata_prescription.py"
src = p.read_text(encoding="utf-8")
i = src.index("_PRESCRIPTION_PUBLIC_BASELINE")
seg = src[i:i + 400]
print("  " + seg.split("]")[0][:80].replace("\n", "\n  ") + " ...")
import re  # noqa: E402
PAIR = re.compile(r'\(\s*"')
seg_end = src.index("]", src.index("= [", i))
print(f"  二元组个数 = {len(PAIR.findall(src[i:seg_end]))}")
for m in re.finditer(r"assert len\(_PRESCRIPTION_PUBLIC_BASELINE\) == (\d+)", src):
    print(f"  字面断言 = {m.group(0)}")

print()
print("### G. BODY_FAT_LIMIT 与 Sex 的实际住址")
d = (BACKEND / "app" / "domain" / "derive.py").read_text(encoding="utf-8").split("\n")
for i, l in enumerate(d):
    if "BODY_FAT_LIMIT" in l:
        print(f"  derive.py:{i+1} {l.rstrip()}")
ind = (BACKEND / "app" / "domain" / "indicators.py").read_text(encoding="utf-8")
for m in re.finditer(r"^class Sex.*$|^Sex = .*$|from .*import.*\bSex\b", ind, re.M):
    print(f"  indicators.py: {m.group(0)}")
for p2 in (BACKEND / "app" / "domain").rglob("*.py"):
    s2 = p2.read_text(encoding="utf-8")
    if "class Sex" in s2:
        print(f"  class Sex 住在 {p2.relative_to(BACKEND).as_posix()}")

print()
print("### H. refdata_prescription 的加载器函数名（Task 5 的测试要吃真仓 YAML）")
rp = (BACKEND / "app" / "refdata_prescription.py").read_text(encoding="utf-8")
for m in re.finditer(r"^def (\w+)\(([^)]*)\)", rp, re.M):
    print(f"  def {m.group(1)}({m.group(2).strip()[:90]})")

print()
print("### I. Task 3 是否已有 impact_level 一致性漂移测试")
for p3 in sorted((BACKEND / "tests").rglob("*.py")):
    s3 = p3.read_text(encoding="utf-8")
    if "impact_level" in s3 and p3.parent.name in ("domain", "prescription") or "templates" in p3.name:
        hits = [i + 1 for i, l in enumerate(s3.split("\n")) if "impact_level" in l]
        print(f"  {p3.relative_to(BACKEND).as_posix()}: 命中行 {hits[:20]}")

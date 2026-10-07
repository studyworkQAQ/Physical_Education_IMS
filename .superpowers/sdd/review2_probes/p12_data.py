import os, sys, re, ast, pathlib, hashlib, shutil, tempfile
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND); os.chdir(BACKEND)
import yaml
from app.domain.prescription.exercises import (ImpactLevel, ExerciseSpec, EquivalenceMapping,
                                               EquivalenceTable, IMPACT_RANK, TARGET_DOMAIN,
                                               EQUIVALENCE_TRIGGERS)
DATA = os.path.join(BACKEND, "data")
EX = os.path.join(DATA, "exercises.yaml")
EQ = os.path.join(DATA, "exercise_equivalence.yaml")
def H(t): print("\n" + "="*72 + "\n## " + t + "\n" + "="*72)

ex_text = open(EX,'rb').read().decode('utf-8')
eq_text = open(EQ,'rb').read().decode('utf-8')
lib_raw = yaml.safe_load(ex_text)
eq_raw  = yaml.safe_load(eq_text)

H("E2.1 exercises.yaml counts")
print("top-level keys =", len(lib_raw))
imp = {}
for k,v in lib_raw.items(): imp.setdefault(v["impact_level"], []).append(k)
for lvl in ("high","medium","low"):
    print("  %-7s %2d : %s" % (lvl, len(imp.get(lvl,[])), sorted(imp.get(lvl,[]))))
print("each entry has exactly the 5 keys ->", all(set(v)=={"name","video_url","impact_level","targets","equipment"} for v in lib_raw.values()))
eqvals = sorted({v["equipment"] for v in lib_raw.values()})
print("distinct equipment (%d):" % len(eqvals), eqvals)
print("equipment claimed list == actual ->", set(eqvals) == {"none","band","step","cone","bike","mat","ball","ladder","medicine_ball"})
longest = {f: max((v[f] for v in lib_raw.values()), key=len) for f in ("name","video_url","equipment")}
longest["ref"] = max(lib_raw.keys(), key=len)
for f,v in longest.items(): print("  longest %-10s = %r  len=%d" % (f, v, len(v)))
print("all refs snake_case ->", all(re.fullmatch(r"[a-z][a-z0-9_]*", k) for k in lib_raw))
print("all video_url == prefix+ref ->", all(v["video_url"] == "https://example.invalid/exercise/"+k for k,v in lib_raw.items()))
print("non-.invalid urls ->", [v["video_url"] for v in lib_raw.values() if ".invalid/" not in v["video_url"]])
print("targets union ->", sorted({t for v in lib_raw.values() for t in v["targets"]}))
print("any empty targets ->", [k for k,v in lib_raw.items() if not v["targets"]])
print("shuttle_run targets ->", lib_raw["shuttle_run"]["targets"])
print("entry line-count per ref (ref line + 5) ->",
      sorted({len([l for l in ex_text.split("\n") if l.strip() and not l.lstrip().startswith("#")]) - 0}))
# top-level key text scan (same method as the guard)
top = [l.split(":",1)[0] for l in ex_text.splitlines() if l and not l[0].isspace() and not l.lstrip().startswith("#") and ":" in l]
print("text-scanned top-level keys =", len(top), " unique =", len(set(top)), " == parsed ->", set(top)==set(lib_raw))

H("E2.2 spec 7.2:487 coverage of the 23 refs")
named487 = ["间歇跑","复合循环","持续跑","台阶训练","自重抗阻","弹力带抗阻","兴趣球类","定向越野","功能性训练"]
by_name = {v["name"]: k for k,v in lib_raw.items()}
for n in named487: print("   %-8s -> %s" % (n, by_name.get(n, "!! MISSING")))
for n in ["高强度间歇训练","能量消耗模块","抗阻优先模块","50 米冲刺间歇","动态拉伸","折返跑","坐位体前屈专项"]:
    print("   %-12s -> %s" % (n, by_name.get(n, "!! MISSING")))
print("all 23 names:", sorted(by_name))

H("E2.3 exercise_equivalence.yaml")
print("version =", repr(eq_raw["version"]), "non-empty str ->", isinstance(eq_raw["version"], str) and eq_raw["version"].strip()!="")
print("bare 1.0 parses as ->", repr(yaml.safe_load("version: 1.0")["version"]), type(yaml.safe_load("version: 1.0")["version"]).__name__)
print("top-level keys =", sorted(eq_raw))
ms = eq_raw["mappings"]
print("mappings =", len(ms))
print("each has exactly 4 keys ->", all(set(m)=={"from","to","max_impact","when"} for m in ms))
print("distinct 'to' (%d):" % len({m["to"] for m in ms}), sorted({m["to"] for m in ms}))
print("distinct 'from' (%d):" % len({m["from"] for m in ms}), sorted({m["from"] for m in ms}))
from collections import Counter
print("when distribution =", dict(Counter(m["when"] for m in ms)))
print("max_impact distribution =", dict(Counter(m["max_impact"] for m in ms)))
print("'to' reuse counts =", dict(Counter(m["to"] for m in ms)))
print("volume_reduction =", eq_raw["volume_reduction"])
rank = {"high":0,"medium":1,"low":2}
esc = [m for m in ms if rank[lib_raw[m["to"]]["impact_level"]] > rank[lib_raw[m["from"]]["impact_level"]]]
print("mappings that ESCALATE impact =", len(esc))
print("all from are high ->", all(lib_raw[m["from"]]["impact_level"]=="high" for m in ms))
print("all to are low   ->", all(lib_raw[m["to"]]["impact_level"]=="low" for m in ms))
print("max_impact == real impact of 'to' ->", all(m["max_impact"]==lib_raw[m["to"]]["impact_level"] for m in ms))
print("all from/to exist in library ->", all(m["from"] in lib_raw and m["to"] in lib_raw for m in ms))
print("when values subset of the two triggers ->", {m["when"] for m in ms} == {"bmi_over_30","muscle_low_p10"})
highs = sorted(k for k,v in lib_raw.items() if v["impact_level"]=="high")
missing = []
for h in highs:
    for trig in ("bmi_over_30","muscle_low_p10"):
        hit = [m for m in ms if m["from"]==h and m["when"]==trig]
        if not hit or lib_raw[hit[0]["to"]]["impact_level"] != "low": missing.append((h,trig))
print("high refs =", len(highs), highs)
print("high refs missing a low substitute =", missing)
low_refs = sorted(k for k,v in lib_raw.items() if v["impact_level"]=="low")
print("low refs (%d) =" % len(low_refs), low_refs)
print("low refs used as a target (%d) =" % len({m["to"] for m in ms}), sorted({m["to"] for m in ms}))
print("energy_expenditure_plus_10pct appears in mappings ->",
      any(m["from"]=="energy_expenditure_plus_10pct" or m["to"]=="energy_expenditure_plus_10pct" for m in ms))
print("challenge_task appears in mappings ->",
      any(m["from"]=="challenge_task" or m["to"]=="challenge_task" for m in ms))

H("E2.4 fingerprints (CRLF-normalised sha256[:16] upper)")
for p in (EX, EQ):
    b = open(p,'rb').read()
    print("  %-42s %6d B  crlf=%d  %s" % (os.path.basename(p), len(b), b.count(b"\r\n"),
          hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()))
print("pinned in test: A6A000F58815FCBB / 0FFB881574AC04F3")

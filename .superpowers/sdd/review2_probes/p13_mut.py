import os, sys, re, ast, pathlib, shutil, tempfile, hashlib
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND); os.chdir(BACKEND)
import yaml
from app.domain.prescription import exercises as ex
from app.domain.prescription.exercises import (ImpactLevel, ExerciseSpec, EquivalenceMapping,
                                               EquivalenceTable, IMPACT_RANK)
DATA = os.path.join(BACKEND, "data")
def H(t): print("\n" + "="*72 + "\n## " + t + "\n" + "="*72)

# ---- rebuild the loader's value objects WITHOUT sqlalchemy (faithful re-implementation) ----
REF_SHAPE = re.compile(r"[a-z][a-z0-9_]*")
EX_KEYS = ("name","video_url","impact_level","targets","equipment")
MAP_KEYS = ("from","to","max_impact","when")
def build_library(path):
    raw = yaml.safe_load(open(path,'rb').read().decode('utf-8'))
    out = {}
    for ref, e in raw.items():
        assert REF_SHAPE.fullmatch(ref), ref
        assert set(e) == set(EX_KEYS), (ref, sorted(set(e) ^ set(EX_KEYS)))
        out[ref] = ExerciseSpec(ref=ref, name=e["name"], video_url=e["video_url"],
                                impact_level=ImpactLevel(e["impact_level"]),
                                targets=frozenset(e["targets"]), equipment=e["equipment"])
    return out
def build_table(path):
    raw = yaml.safe_load(open(path,'rb').read().decode('utf-8'))
    ms = []
    for i, m in enumerate(raw["mappings"]):
        assert set(m) == set(MAP_KEYS), (i, sorted(set(m) ^ set(MAP_KEYS)))
        ms.append(EquivalenceMapping(from_ref=m["from"], to_ref=m["to"],
                                     max_impact=ImpactLevel(m["max_impact"]), when=m["when"]))
    return EquivalenceTable(version=raw["version"], mappings=tuple(ms),
                            volume_reduction=dict(raw["volume_reduction"]))
LIB = build_library(os.path.join(DATA,"exercises.yaml"))
TAB = build_table(os.path.join(DATA,"exercise_equivalence.yaml"))
IMPACT_DESCENDING = ("high","medium","low")   # the test-side literal, copied verbatim
SPEC_7_4_TRIGGERS = frozenset({"bmi_over_30","muscle_low_p10"})

H("E3.1 re-run of test_equivalence_never_maps_to_a_higher_impact_level (real data)")
rank = {v:i for i,v in enumerate(IMPACT_DESCENDING)}
off = []
for m in TAB.mappings:
    s = LIB[m.from_ref].impact_level.value; t = LIB[m.to_ref].impact_level.value
    if rank[t] < rank[s]: off.append("ESCALATE %s(%s)->%s(%s)" % (m.from_ref,s,m.to_ref,t))
    if m.max_impact.value != t: off.append("LIE %s->%s declares %s real %s" % (m.from_ref,m.to_ref,m.max_impact.value,t))
print("offenders =", off, " => guard", "RED" if off else "GREEN")
print("escalation-branch offenders only =", [o for o in off if o.startswith("ESCALATE")])

H("E3.2 re-run of test_every_high_impact_exercise_has_a_low_substitute")
subs = {}
for m in TAB.mappings: subs.setdefault(m.from_ref, {})[m.when] = m.to_ref
highs = sorted(r for r,s in LIB.items() if s.impact_level is ImpactLevel.HIGH)
off2 = []
assert highs
for r in highs:
    for trig in sorted(SPEC_7_4_TRIGGERS):
        tgt = subs.get(r, {}).get(trig)
        if tgt is None: off2.append("%s missing when=%s" % (r,trig))
        elif LIB[tgt].impact_level is not ImpactLevel.LOW: off2.append("%s->%s not low" % (r,tgt))
print("high refs =", highs); print("offenders =", off2, " => guard", "RED" if off2 else "GREEN")

H("E3.3 re-run of test_equivalence_when_values_are_exactly_the_two_spec_7_4_triggers")
obs = {m.when for m in TAB.mappings}
print("observed when ==", SPEC_7_4_TRIGGERS, "->", obs == SPEC_7_4_TRIGGERS)
print("volume_reduction keys ==" , SPEC_7_4_TRIGGERS, "->", set(TAB.volume_reduction) == SPEC_7_4_TRIGGERS)

H("E3.4 re-run of test_volume_reduction_coefficients_are_pinned_verbatim")
print("bmi_over_30 == 0.8 ->", TAB.volume_reduction["bmi_over_30"] == 0.8, type(TAB.volume_reduction["bmi_over_30"]).__name__)
print("muscle_low_p10 == 0.9 ->", TAB.volume_reduction["muscle_low_p10"] == 0.9)
print("all floats and 0<f<1 ->", all(isinstance(f,float) and 0.0<f<1.0 for f in TAB.volume_reduction.values()))

H("E3.5 re-run of test_equivalence_table_has_a_version / only_maps_to_existing")
print("version ==", repr(TAB.version), "== '1.0' ->", TAB.version == "1.0")
print("all endpoints exist ->", all(m.from_ref in LIB and m.to_ref in LIB for m in TAB.mappings))

H("E3.6 re-run of test_lookup_honours_the_impact_ceiling... (real table part)")
print("lookup('interval_run', LOW)    =", TAB.lookup("interval_run", ImpactLevel.LOW))
print("lookup('interval_run', MEDIUM) =", TAB.lookup("interval_run", ImpactLevel.MEDIUM))
print("lookup('interval_run', HIGH)   =", TAB.lookup("interval_run", ImpactLevel.HIGH))
print("lookup('challenge_task', LOW)  =", TAB.lookup("challenge_task", ImpactLevel.LOW))
print("lookup('__nope__', LOW)        =", TAB.lookup("__不存在的 ref__", ImpactLevel.LOW))
syn = EquivalenceTable(version="synthetic",
        mappings=(EquivalenceMapping(from_ref="a",to_ref="b",max_impact=ImpactLevel.MEDIUM,when="bmi_over_30"),),
        volume_reduction={})
print("synthetic lookup(a, MEDIUM) =", syn.lookup("a", ImpactLevel.MEDIUM),
      " (a, HIGH) =", syn.lookup("a", ImpactLevel.HIGH),
      " (a, LOW) =", syn.lookup("a", ImpactLevel.LOW))

H("E4.1 M-A1 simulation: IMPACT_RANK HIGH:0 <-> LOW:2  (4 branches of test_impact_rank_values_are_pinned_verbatim)")
def four_branches(RANK, IL):
    b1 = (RANK == {IL.HIGH:0, IL.MEDIUM:1, IL.LOW:2})
    desc = [l.value for l in sorted(RANK, key=RANK.__getitem__)]
    b2 = (desc == list(IMPACT_DESCENDING))
    b3 = (RANK[IL.LOW] >= RANK[IL.HIGH])
    b4 = (not (RANK[IL.HIGH] >= RANK[IL.LOW]))
    return b1,b2,b3,b4,desc
print("  REAL      :", four_branches(IMPACT_RANK, ImpactLevel))
R1 = {ImpactLevel.HIGH:2, ImpactLevel.MEDIUM:1, ImpactLevel.LOW:0}
print("  M-A1      :", four_branches(R1, ImpactLevel), " (claim: all four fail)")
R2 = {ImpactLevel.HIGH:0, ImpactLevel.MEDIUM:0, ImpactLevel.LOW:0}
print("  M-A2 all0 :", four_branches(R2, ImpactLevel), " (claim: only 支1 and 支4 fail)")

H("E4.2 lookup behaviour under M-A1 / M-A2 (does test_lookup... go red?)")
def lookup_with(RANK, tab, ref, ceiling):
    cr = RANK[ceiling]
    for m in tab.mappings:
        if m.from_ref != ref: continue
        if RANK[m.max_impact] >= cr: return m.to_ref
    return None
for name, R in (("REAL",IMPACT_RANK),("M-A1",R1),("M-A2",R2)):
    real_ok = (lookup_with(R,TAB,"interval_run",ImpactLevel.LOW)=="stationary_cycling"
           and lookup_with(R,TAB,"interval_run",ImpactLevel.MEDIUM)=="stationary_cycling"
           and lookup_with(R,TAB,"interval_run",ImpactLevel.HIGH)=="stationary_cycling"
           and lookup_with(R,TAB,"challenge_task",ImpactLevel.LOW) is None)
    syn_ok = (lookup_with(R,syn,"a",ImpactLevel.MEDIUM)=="b"
          and lookup_with(R,syn,"a",ImpactLevel.HIGH)=="b"
          and lookup_with(R,syn,"a",ImpactLevel.LOW) is None)
    print("  %-6s real-table asserts ok=%s ; synthetic asserts ok=%s" % (name, real_ok, syn_ok))
print("  => M-A1/M-A2 both redden test_lookup_... : the docstring's '2 failed' is consistent")
print("  => neither redden test_equivalence_never_maps_to_a_higher_impact_level (it never reads IMPACT_RANK)")

H("E4.3 does the 'never maps higher' guard read IMPACT_RANK at all? (AST of the test)")
tsrc = pathlib.Path(os.path.join(BACKEND,"tests","test_refdata_prescription.py")).read_text(encoding="utf-8")
tt = ast.parse(tsrc)
for fn in tt.body:
    if isinstance(fn, ast.FunctionDef) and fn.name in (
        "test_equivalence_never_maps_to_a_higher_impact_level",
        "test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable",
        "test_impact_rank_values_are_pinned_verbatim",
        "test_every_high_impact_exercise_has_a_low_substitute"):
        names = sorted({n.id for n in ast.walk(fn) if isinstance(n, ast.Name)})
        uses_rank = "IMPACT_RANK" in names
        uses_desc = "IMPACT_DESCENDING" in names
        print("  %-72s IMPACT_RANK=%-5s IMPACT_DESCENDING=%s" % (fn.name, uses_rank, uses_desc))

H("E5 M-C3 simulation: add a public top-level definition to a COPY of exercises.py, re-run 支5's AST")
tmp = tempfile.mkdtemp(prefix="rv2_mc3_")
cp = os.path.join(tmp, "exercises_mutated.py")
orig = pathlib.Path(ex.__file__).read_bytes()
mut = orig.replace(b"EQUIVALENCE_TRIGGERS: frozenset[str] = frozenset({\"bmi_over_30\", \"muscle_low_p10\"})",
                   b"SUBSTITUTE_POLICY = \"first_match\"\n\nEQUIVALENCE_TRIGGERS: frozenset[str] = frozenset({\"bmi_over_30\", \"muscle_low_p10\"})", 1)
assert mut != orig, "anchor not found"
open(cp,'wb').write(mut)
def defined_set(path):
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    return {n.name for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and not n.name.startswith("_")} | \
           {t.id for n in tree.body if isinstance(n,(ast.Assign,ast.AnnAssign))
                 for t in (n.targets if isinstance(n,ast.Assign) else [n.target])
                 if isinstance(t,ast.Name) and not t.id.startswith("_")}
BASE = ["EQUIVALENCE_TRIGGERS","IMPACT_RANK","TARGET_DOMAIN","EquivalenceMapping","EquivalenceTable","ExerciseSpec","ImpactLevel"]
d0 = defined_set(ex.__file__); d1 = defined_set(cp)
print("  baseline defined == set(_PRESCRIPTION_PUBLIC_BASELINE) ->", d0 == set(BASE))
print("  mutated  defined =", sorted(d1))
print("  mutated  defined == baseline ->", d1 == set(BASE), "  extra =", sorted(d1 - set(BASE)))
print("  => 支5 (AST exhaustiveness) is the ONLY branch that changes: 支1/2/3/4/6 all read __all__ / pkg attrs, untouched")
print("  sha256[:16] original exercises.py =", hashlib.sha256(orig).hexdigest()[:16].upper())
print("  sha256[:16] mutated  copy        =", hashlib.sha256(mut).hexdigest()[:16].upper())
print("  repo file untouched -> sha256[:16] =",
      hashlib.sha256(pathlib.Path(ex.__file__).read_bytes()).hexdigest()[:16].upper())
shutil.rmtree(tmp, ignore_errors=True)

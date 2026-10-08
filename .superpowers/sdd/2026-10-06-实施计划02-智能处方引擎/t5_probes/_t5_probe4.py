"""probe 4：sessions_per_week 的实际分布（P5-A2 的承重数字）+ 一个可字面写死的算例。"""
import collections
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import yaml  # noqa: E402

dist = collections.Counter()
shape_by_layer = collections.defaultdict(collections.Counter)
print("### A. 每个 block 的「一周内出现次数」分布（按层）")
for f in sorted((BACKEND / "data" / "prescription").glob("*.yaml")):
    d = yaml.safe_load(f.read_text(encoding="utf-8"))
    cnt = collections.Counter(b["exercise_ref"] for s in d["sessions"] for b in s["blocks"])
    for s in d["sessions"]:
        for b in s["blocks"]:
            dist[cnt[b["exercise_ref"]]] += 1
            shape_by_layer[d["layer"]][cnt[b["exercise_ref"]]] += 1
print(f"  全体 130 个 block 的 sessions_per_week 分布 = {dict(sorted(dist.items()))}")
for lay in sorted(shape_by_layer):
    print(f"  {lay:7s} {dict(sorted(shape_by_layer[lay].items()))}")

print()
print("### B. 一个可字面写死的算例：RED-END-ABN-01 的第 1 课")
d = yaml.safe_load((BACKEND / "data" / "prescription" / "RED-END-ABN-01.yaml").read_text(encoding="utf-8"))
cnt = collections.Counter(b["exercise_ref"] for s in d["sessions"] for b in s["blocks"])
print(f"  weekly_frequency = {d['weekly_frequency']}  microcycle_weeks = {d['microcycle_weeks']}")
print(f"  week_deltas = {d['progression']['week_deltas']}")
for s in d["sessions"][:1]:
    print(f"  session day={s['day']} focus={s['focus']!r}")
    for b in s["blocks"]:
        st = b["structure"]
        it = b["intensity"]
        if "work_min" in st:
            base = st["work_min"] * st["sets"]
            unit = "min"
        else:
            base = st["rounds"] * st["reps"]
            unit = "reps"
        n = cnt[b["exercise_ref"]]
        print(f"    {b['exercise_ref']:22s} impact={b['impact_level']:6s} "
              f"intensity={it} structure={st}")
        print(f"      -> base={base} {unit}/课  sessions_per_week={n}  weekly_volume={base * n} {unit}/周")

print()
print("### C. 时长类 vs 次数类按层的分布（决定 addon 量口径要不要分单位）")
k = collections.defaultdict(collections.Counter)
for f in sorted((BACKEND / "data" / "prescription").glob("*.yaml")):
    d = yaml.safe_load(f.read_text(encoding="utf-8"))
    for s in d["sessions"]:
        for b in s["blocks"]:
            kind = "duration" if "work_min" in b["structure"] else "reps"
            k[d["layer"]][kind] += 1
for lay in sorted(k):
    print(f"  {lay:7s} {dict(k[lay])}")

print()
print("### D. addons 按层的分布（P5-A3：muscle_low 的 addon 挂在哪几层）")
for f in sorted((BACKEND / "data" / "prescription").glob("*.yaml")):
    d = yaml.safe_load(f.read_text(encoding="utf-8"))
    a = [(x["when"], x["module"]) for x in d["addons"]]
    print(f"  {d['template_id']:16s} layer={d['layer']:7s} body_comp={d['body_comp']:9s} addons={a}")

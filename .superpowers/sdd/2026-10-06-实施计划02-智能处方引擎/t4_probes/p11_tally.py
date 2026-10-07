import collections, sys, pathlib
sys.path.insert(0, "backend")
from app import refdata_prescription as rp
from app.domain.prescription import Layer, MatchInput, MatchStatus, match_template
sys.path.insert(0, "backend/tests/domain")
import importlib.util
spec = importlib.util.spec_from_file_location(
    "tm", "backend/tests/domain/test_prescription_match.py")
tm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tm)

templates = rp.templates()
tally = collections.Counter()
rows = []
for layer, bucket, abnormal, want_status, want_id in tm._MATRIX_32:
    got = match_template(MatchInput(layer=layer, dominant_bucket=bucket,
                                    body_comp_abnormal=abnormal), templates)
    tally[got.status.value] += 1
    assert got.status is want_status, (layer, bucket, abnormal, got.status, want_status)
    rows.append((layer.value, bucket, "abnormal" if abnormal else "normal",
                 got.status.value, got.template.template_id if got.template else None,
                 got.reason))
print("=== 实测分类（32 格）===")
print(dict(tally), "sum =", sum(tally.values()))
print("=== 期望表分类 ===")
exp = collections.Counter(s.value for _l, _b, _a, s, _t in tm._MATRIX_32)
print(dict(exp))
print("=== 六支 reason 各取一例 ===")
seen = set()
for r in rows:
    if r[3] not in seen:
        seen.add(r[3]); print("  %-12s %-52s %s" % (r[3], str(r[:3]), r[5]))
# 另外两支不在穷举里，现场造
import dataclasses
from app.domain.prescription import ReviewStatus
d = dict(templates)
d["RED-END-ABN-01"] = dataclasses.replace(d["RED-END-ABN-01"], review_status=ReviewStatus.PENDING)
o = match_template(MatchInput(layer=Layer.RED, dominant_bucket="endurance", body_comp_abnormal=True), d)
print("  %-12s %s" % (o.status.value, o.reason))
d2 = {k: v for k, v in templates.items() if k != "RED-STR-NOR-04"}
o2 = match_template(MatchInput(layer=Layer.RED, dominant_bucket="strength", body_comp_abnormal=False), d2)
print("  %-12s %s" % (o2.status.value, o2.reason))
print("=== 15 个 MATCHED 的 template_id ===")
print(sorted(r[4] for r in rows if r[3] == "matched"))
print("=== 3 个 UNREACHABLE 的格子 ===")
print([r[:3] for r in rows if r[3] == "unreachable"])

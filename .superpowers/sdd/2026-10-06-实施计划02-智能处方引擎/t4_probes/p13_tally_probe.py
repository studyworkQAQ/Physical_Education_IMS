"""在**当前落盘的** match.py 上跑 32 格穷举，打印分类分布与不符的格子。

被 p12_mutate.py 以子进程调用（每个变异相位一次）。期望侧取自
tests/domain/test_prescription_match.py 的 _MATRIX_32（字面表），故本脚本
既能报「分布」也能报「哪几格与期望表不符」。
"""
import collections
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend"))

from app import refdata_prescription as rp            # noqa: E402
from app.domain.prescription import MatchInput, match_template  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "tm", ROOT / "backend" / "tests" / "domain" / "test_prescription_match.py")
tm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tm)

templates = rp.templates()
tally = collections.Counter()
bad = []
for layer, bucket, abnormal, want_status, want_id in tm._MATRIX_32:
    got = match_template(
        MatchInput(layer=layer, dominant_bucket=bucket, body_comp_abnormal=abnormal),
        templates)
    tally[got.status.value] += 1
    got_id = got.template.template_id if got.template is not None else None
    if got.status is not want_status or got_id != want_id:
        bad.append((layer.value, bucket, "abnormal" if abnormal else "normal",
                    got.status.value, got_id, want_status.value, want_id))

print("TALLY", dict(tally), "sum", sum(tally.values()))
print("MISMATCH", len(bad))
for row in bad:
    print("  cell layer=%s bucket=%s body=%s -> got %s/%s  want %s/%s" % row)

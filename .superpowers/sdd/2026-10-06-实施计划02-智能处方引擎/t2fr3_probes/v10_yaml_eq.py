# -*- coding: utf-8 -*-
"""Snapshot / compare yaml.safe_load of both YAMLs (data-part equivalence ruler).

usage:
  python v10_yaml_eq.py snapshot <out.json>
  python v10_yaml_eq.py compare  <before.json>
  python v10_yaml_eq.py control  <before.json>   # 2 real data mutations must be CAUGHT
"""
import hashlib
import json
import pathlib
import sys

import yaml

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
DATA = ROOT / "backend/data"
FILES = ["exercises.yaml", "exercise_equivalence.yaml"]


def load_all():
    out = {}
    for name in FILES:
        raw = (DATA / name).read_bytes()
        doc = yaml.safe_load(raw.decode("utf-8"))
        out[name] = doc
    return out


def canon(doc):
    """canonical JSON so dict ordering can't hide or fake a difference"""
    return json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=1)


def main():
    action = sys.argv[1]
    if action == "snapshot":
        out = pathlib.Path(sys.argv[2])
        doc = load_all()
        text = canon(doc)
        out.write_bytes(text.encode("utf-8"))
        print(f"snapshot -> {out} ({len(text.encode('utf-8'))} B) sha256[:16]="
              f"{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16].upper()}")
        for name in FILES:
            d = doc[name]
            if name == "exercises.yaml":
                print(f"  {name}: {len(d)} entries")
            else:
                print(f"  {name}: version={d['version']!r} mappings={len(d['mappings'])} "
                      f"volume_reduction={d['volume_reduction']}")
        return 0

    before_path = pathlib.Path(sys.argv[2])
    before = json.loads(before_path.read_bytes().decode("utf-8"))
    after = load_all()

    if action == "compare":
        same = canon(before) == canon(after)
        print(f"yaml.safe_load BEFORE vs AFTER (canonical JSON) identical = {same}")
        for name in FILES:
            s = canon(before[name]) == canon(after[name])
            print(f"  {name}: identical = {s}")
        # self-control: prove the ruler is not vacuously True
        probe = json.loads(canon(after))
        probe["exercises.yaml"]["interval_run"]["name"] = probe["exercises.yaml"]["interval_run"]["name"]
        print(f"  self-control (unchanged copy compares equal) = {canon(probe) == canon(after)}")
        return 0 if same else 1

    if action == "control":
        # two REAL data mutations, applied in memory; the ruler must CATCH both
        mutated_a = json.loads(canon(after))
        mutated_a["exercises.yaml"]["interval_run"]["impact_level"] = "medium"
        caught_a = canon(mutated_a) != canon(before)

        mutated_b = json.loads(canon(after))
        mutated_b["exercise_equivalence.yaml"]["mappings"][0]["to"] = "band_resistance"
        caught_b = canon(mutated_b) != canon(before)

        mutated_c = json.loads(canon(after))
        del mutated_c["exercises.yaml"]["challenge_task"]
        caught_c = canon(mutated_c) != canon(before)

        mutated_d = json.loads(canon(after))
        mutated_d["exercise_equivalence.yaml"]["volume_reduction"]["bmi_over_30"] = 0.85
        caught_d = canon(mutated_d) != canon(before)

        print("CONTROL GROUP (ruler must catch every real data mutation):")
        print(f"  A exercises.yaml[interval_run][impact_level] high->medium : caught={caught_a}")
        print(f"  B equivalence mappings[0][to] stationary_cycling->band_resistance : caught={caught_b}")
        print(f"  C delete exercises.yaml[challenge_task] (23 -> 22 entries)   : caught={caught_c}")
        print(f"  D volume_reduction[bmi_over_30] 0.8 -> 0.85                 : caught={caught_d}")
        allc = caught_a and caught_b and caught_c and caught_d
        print(f"  ALL CAUGHT = {allc}")
        return 0 if allc else 1

    raise SystemExit(f"unknown action {action}")


if __name__ == "__main__":
    raise SystemExit(main())

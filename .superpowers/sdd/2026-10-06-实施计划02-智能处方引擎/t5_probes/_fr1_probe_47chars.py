# -*- coding: utf-8 -*-
"""硬规矩 #82 的自证：账本里要写的「47 字符等长」必须自己数一遍，不照抄派单。

变异 ④ 打的是 `intensity.py` 里 `hr_zone` 的取整方向那一行。
本脚本量原行长、并给出一个**语义相反**的同形改写，量它的长，确认两者等长。
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
SRC = ROOT / "backend" / "app" / "domain" / "prescription" / "intensity.py"
lines = SRC.read_bytes().decode("utf-8").split("\n")
hits = [(i + 1, ln) for i, ln in enumerate(lines) if "return int(low_bpm)" in ln]
print(f"命中 {len(hits)} 处：")
for no, ln in hits:
    print(f"  行 {no}: len={len(ln)}  {ln!r}")
    # 取整方向反过来（低界向上、高界向下）——语义相反、字符数需要实测
    mutated = ln.replace("int(low_bpm)", "int(-(-low_bpm // 1))") \
                .replace("int(-(-high_bpm // 1))", "int(high_bpm)")
    print(f"  变异后: len={len(mutated)}  {mutated!r}")
    print(f"  等长? {len(ln) == len(mutated)}   差 = {len(mutated) - len(ln)}")
sys.exit(0)

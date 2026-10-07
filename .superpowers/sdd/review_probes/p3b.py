# -*- coding: utf-8 -*-
"""Probe P3b: layering:373 那条 Counter 命令，逐字照跑（必须在**仓库根**跑）。"""
import pathlib, collections
c = collections.Counter(p.parts[2] for p in pathlib.Path('backend/app').rglob('*.py') if p.parts[2] in ('pipeline','db','domain'))
print("HEAD 工作树 ->", sorted(c.items()), sum(c.values()))
tot = sum(c.values())
print("单目录被搬空时剩余: %d-%d(db)=%d  %d-%d(pipeline)=%d  %d-%d(domain)=%d" % (
    tot, c['db'], tot - c['db'], tot, c['pipeline'], tot - c['pipeline'], tot, c['domain'], tot - c['domain']))

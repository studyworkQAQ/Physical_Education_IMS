# -*- coding: utf-8 -*-
"""F1-1 的补充实测：dict 子类的只读性还有哪些口子（`|=` / `__init__` 重调 / copy）。"""
import copy
import json
import sys


class _FrozenVolumeMap(dict):
    def _blocked(self, *args, **kwargs):
        raise TypeError("只读")

    __setitem__ = _blocked
    __delitem__ = _blocked
    pop = _blocked
    popitem = _blocked
    clear = _blocked
    update = _blocked
    setdefault = _blocked


m = _FrozenVolumeMap({"min": 48.0})
print(f"hasattr __ior__ = {hasattr(m, '__ior__')}")
try:
    m |= {"reps": 120.0}
    print(f"m |= {{...}} 未抛 → **是个口子**，之后 m = {dict(m)}")
except TypeError as exc:
    print(f"m |= {{...}} 抛 TypeError({exc})，之后 m = {dict(m)}")

m2 = _FrozenVolumeMap({"min": 48.0})
try:
    m2.__init__({"reps": 1.0})
    print(f"m2.__init__({{...}}) 未抛 → 之后 m2 = {dict(m2)}")
except TypeError as exc:
    print(f"m2.__init__ 抛 TypeError({exc})")

m3 = _FrozenVolumeMap({"min": 48.0})
print(f"copy.copy(m3) -> type={type(copy.copy(m3)).__name__} value={dict(copy.copy(m3))}")
print(f"copy.deepcopy(m3) -> type={type(copy.deepcopy(m3)).__name__} "
      f"value={dict(copy.deepcopy(m3))}")
print(f"json.dumps(m3, allow_nan=False) -> {json.dumps(m3, allow_nan=False)}")
print(f"json.dumps(m3, allow_nan=False, sort_keys=True) -> "
      f"{json.dumps(m3, allow_nan=False, sort_keys=True)}")
print(f"m3.keys() 类型 = {type(m3.keys()).__name__}")
print(f"Mapping 注册: ", end="")
import collections.abc as abc
print(f"isinstance(m3, abc.Mapping) = {isinstance(m3, abc.Mapping)}")
try:
    print(f"json.dumps(float('nan'), allow_nan=False) -> {json.dumps(float('nan'), allow_nan=False)}")
except ValueError as exc:
    print(f"json.dumps(nan, allow_nan=False) 抛 ValueError({exc})")
sys.exit(0)

# -*- coding: utf-8 -*-
"""F1-1 的补充实测（二）：`__reduce__` 能否一次修好 copy / deepcopy / pickle。"""
import copy
import json
import pickle
import sys


class _ReadOnlyVolumeMap(dict):
    def _blocked(self, *args, **kwargs):
        raise TypeError("只读")

    __setitem__ = _blocked
    __delitem__ = _blocked
    pop = _blocked
    popitem = _blocked
    clear = _blocked
    update = _blocked
    setdefault = _blocked
    __ior__ = _blocked

    def __reduce__(self):
        return (_ReadOnlyVolumeMap, (dict(self),))


m = _ReadOnlyVolumeMap({"min": 48.0, "reps": 120.0})
for label, fn in (
    ("m |= {...}", lambda: m.__ior__({"x": 1.0})),
    ("m['min'] = 0", lambda: m.__setitem__("min", 0)),
    ("del m['min']", lambda: m.__delitem__("min")),
    ("m.update", lambda: m.update({"min": 0})),
    ("m.pop", lambda: m.pop("min")),
    ("m.popitem", lambda: m.popitem()),
    ("m.clear", lambda: m.clear()),
    ("m.setdefault", lambda: m.setdefault("x", 1)),
):
    try:
        fn()
        print(f"{label}: 未抛 → **口子**，m={dict(m)}")
    except TypeError as exc:
        print(f"{label}: TypeError({exc})")

print(f"m 未被改动 = {dict(m) == {'min': 48.0, 'reps': 120.0}}")
c = copy.copy(m)
d = copy.deepcopy(m)
p = pickle.loads(pickle.dumps(m))
print(f"copy.copy     -> type={type(c).__name__} value={dict(c)} 独立={c is not m}")
print(f"copy.deepcopy -> type={type(d).__name__} value={dict(d)} 独立={d is not m}")
print(f"pickle        -> type={type(p).__name__} value={dict(p)} 独立={p is not m}")
print(f"json.dumps(m, allow_nan=False) -> {json.dumps(m, allow_nan=False)}")
print(f"json.dumps({{'k': m}}, ensure_ascii=False) -> "
      f"{json.dumps({'weekly_volume_base': m}, ensure_ascii=False)}")
print(f"m == 普通 dict -> {m == {'min': 48.0, 'reps': 120.0}}")
print(f"{{**m}} -> type={type({**m}).__name__} value={ {**m} }")
print(f"嵌套快照整体 json.dumps -> "
      f"{json.dumps({'a': 1, 'weekly_volume_base': m, 'l': [1.0]}, allow_nan=False)}")
sys.exit(0)

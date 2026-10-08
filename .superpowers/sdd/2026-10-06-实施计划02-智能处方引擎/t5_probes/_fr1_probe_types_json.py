# -*- coding: utf-8 -*-
"""F1-1 的三项实测（只读 + 一次可还原的临时改动）：

① `import types` 进 domain 会不会让纯净性守卫变红？
   —— 做法：往 assembler.py 顶部临时插一行 `import types`，跑
   `pytest tests/architecture/test_domain_purity.py -q`，然后 `git checkout --` 还原，
   并按硬规矩 #83 清 __pycache__ + 设 PYTHONDONTWRITEBYTECODE=1。
② `json.dumps(types.MappingProxyType({...}), allow_nan=False)` 是否 TypeError？
③ 一个「屏蔽全部 7 个 mutator 的 dict 子类」是否 (a) 仍能被 json.dumps 序列化、
   (b) `m["min"] = 0` 抛 TypeError？
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
ASSEMBLER = BACKEND / "app" / "domain" / "prescription" / "assembler.py"

env = dict(os.environ)
env["PYTHONDONTWRITEBYTECODE"] = "1"


def clean_pyc():
    for d in BACKEND.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)


def part1():
    print("=" * 90)
    print("① import types 进 domain → 纯净性守卫的颜色")
    print("=" * 90)
    original = ASSEMBLER.read_bytes()
    clean_pyc()
    base = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/architecture/test_domain_purity.py", "-q",
         "--no-header", "-p", "no:cacheprovider"],
        cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"[对照 M0：未插 import types] exit={base.returncode}")
    print(base.stdout.strip()[-400:])
    try:
        text = original.decode("utf-8")
        marker = "from collections import Counter\n"
        assert text.count(marker) == 1, text.count(marker)
        patched = text.replace(marker, "import types\n" + marker, 1)
        ASSEMBLER.write_text(patched, encoding="utf-8", newline="\n")
        clean_pyc()
        mut = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/architecture/test_domain_purity.py", "-q",
             "--no-header", "-p", "no:cacheprovider"],
            cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8",
            errors="replace")
        print(f"[变异 M1：插了 import types] exit={mut.returncode}")
        print(mut.stdout.strip()[-1400:])
    finally:
        ASSEMBLER.write_bytes(original)
        clean_pyc()
    after = ASSEMBLER.read_bytes()
    print(f"[还原] sha256 相同 = {after == original}（{len(after)} B）")


def part2():
    print()
    print("=" * 90)
    print("② MappingProxyType 的 JSON 序列化")
    print("=" * 90)
    proxy = types.MappingProxyType({"min": 48.0, "reps": 120.0})
    try:
        out = json.dumps({"weekly_volume_base": proxy}, allow_nan=False)
        print(f"json.dumps 成功: {out}")
    except TypeError as exc:
        print(f"json.dumps 抛 TypeError: {exc}")
    print(f"isinstance(proxy, dict) = {isinstance(proxy, dict)}")


class _FrozenVolumeMap(dict):
    """探针用的最小实现（与将要落进 assembler.py 的那一份同形）。"""

    def _blocked(self, *args, **kwargs):
        raise TypeError("weekly_volume_base 是只读的")

    __setitem__ = _blocked
    __delitem__ = _blocked
    pop = _blocked
    popitem = _blocked
    clear = _blocked
    update = _blocked
    setdefault = _blocked


def part3():
    print()
    print("=" * 90)
    print("③ 屏蔽 mutator 的 dict 子类")
    print("=" * 90)
    m = _FrozenVolumeMap({"min": 48.0, "reps": 120.0})
    print(f"isinstance(m, dict) = {isinstance(m, dict)}")
    try:
        out = json.dumps({"weekly_volume_base": m}, allow_nan=False, sort_keys=False)
        print(f"json.dumps 成功: {out}")
    except TypeError as exc:
        print(f"json.dumps 抛 TypeError: {exc}")
    for label, fn in (
        ("m['min'] = 0", lambda: m.__setitem__("min", 0)),
        ("del m['min']", lambda: m.__delitem__("min")),
        ("m.update(...)", lambda: m.update({"min": 0})),
        ("m.pop('min')", lambda: m.pop("min")),
        ("m.popitem()", lambda: m.popitem()),
        ("m.clear()", lambda: m.clear()),
        ("m.setdefault('x', 1)", lambda: m.setdefault("x", 1)),
    ):
        try:
            fn()
            print(f"{label}: 未抛（**可变，不合格**）")
        except TypeError as exc:
            print(f"{label}: TypeError({exc})")
    print(f"m == {{'min': 48.0, 'reps': 120.0}} -> {m == {'min': 48.0, 'reps': 120.0}}")
    print(f"dict(m) -> {dict(m)}  type={type(dict(m)).__name__}")
    print(f"tuple(m) -> {tuple(m)}")
    print(f"两个同值实例相等 -> {_FrozenVolumeMap({'min': 1.0}) == _FrozenVolumeMap({'min': 1.0})}")
    print(f"{{**m}} 的类型 -> {type({**m}).__name__}，值 -> {{**m}}")
    print(f"repr(m) -> {repr(m)}")
    print(f"hash 可用? -> ", end="")
    try:
        print(hash(m))
    except TypeError as exc:
        print(f"TypeError({exc})")


part1()
part2()
part3()
sys.exit(0)

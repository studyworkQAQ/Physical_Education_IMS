"""Task 9 探针 08：GC14 的**变异自证**（Ruling 1 说本 Task 不要求变异，但 Task 2/3/4/5/7/8
六个实现者都自己做了、控制者六次都采纳；本探针照 Task 8 那个「先写测试 → 变异存活 →
补反例 → killed」的形状办，只不过这里一次就 killed）。

三条变异，各证明 GC14 的一格期望值真的被钉住：

=====  ==========================================================  ==========================
M      变异                                                         它若存活意味着
=====  ==========================================================  ==========================
M1     ``expected[13]["safety_substitution_count"]`` 32 → 0         「32 次替换」没人看着
M2     ``expected[13]["week1_block0_exercise_ref"]``                「blocks[0] 是替身」没人看着
       ``stationary_cycling`` → ``sprint_50m_intervals``
M3     ``input[13]["curr"]["weight_kg"]`` 95.0 → 78.0               「bmi > 30 才触发」没人看着
       （bmi 31.0 → 25.5，触发 1 不再命中）
=====  ==========================================================  ==========================

⚠️ 变异一律打在**真文件**上、跑完立刻从字节备份还原（``try/finally`` + sha256 复核），
不用 ``git checkout``（硬规矩 #46：它会按 core.autocrlf 重写工作树）。
"""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
GOLDEN = BACKEND / "tests" / "fixtures" / "golden_cases.json"
TEST = "tests/integration/test_golden_cases.py"

original = GOLDEN.read_bytes()
sha_before = hashlib.sha256(original).hexdigest()[:16].upper()
backup = pathlib.Path(tempfile.gettempdir()) / "t9_gc14_mutation_backup.json"
shutil.copyfile(GOLDEN, backup)
print(f"原文件 {len(original)} B sha256[:16]={sha_before}，备份 -> {backup}")


def _write(data) -> None:
    dumped = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    GOLDEN.write_bytes(dumped.replace("\n", "\r\n").encode("utf-8"))


def _run() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TEST, "-q", "--no-header", "-x", "--tb=line"],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    tail = "\n".join(proc.stdout.strip().splitlines()[-6:])
    return proc.returncode, tail


def _load() -> dict:
    return json.loads(GOLDEN.read_bytes().replace(b"\r\n", b"\n").decode("utf-8"))


MUTATIONS = [
    ("M1 substitution_count 32 -> 0",
     lambda d: d["expected"][13].__setitem__("safety_substitution_count", 0)),
    ("M2 block0 ref 替身 -> 原 ref",
     lambda d: d["expected"][13].__setitem__(
         "week1_block0_exercise_ref", "sprint_50m_intervals")),
    ("M3 weight_kg 95.0 -> 78.0（bmi 31.0 -> 25.5）",
     lambda d: d["input"][13]["curr"].__setitem__("weight_kg", 78.0)),
]

results = []
try:
    rc, tail = _run()
    print(f"\n[基线] rc={rc}（应为 0）\n{tail}")
    assert rc == 0, "基线就红了，变异结论不可解释"
    for name, mutate in MUTATIONS:
        data = _load()
        mutate(data)
        _write(data)
        rc, tail = _run()
        killed = rc != 0
        results.append((name, killed, rc))
        print(f"\n[{name}] rc={rc} -> {'KILLED' if killed else 'SURVIVED ⚠️'}\n{tail}")
        GOLDEN.write_bytes(original)
finally:
    GOLDEN.write_bytes(backup.read_bytes())
    sha_after = hashlib.sha256(GOLDEN.read_bytes()).hexdigest()[:16].upper()
    print(f"\n还原：sha256[:16] {sha_before} -> {sha_after}，逐字相同={sha_before == sha_after}")
    backup.unlink(missing_ok=True)

print("\n== 汇总 ==")
for name, killed, rc in results:
    print(f"  {'KILLED  ' if killed else 'SURVIVED'} rc={rc}  {name}")
survivors = [name for name, killed, _rc in results if not killed]
print("存活的变异：", survivors if survivors else "0 条（3/3 killed）")
sys.exit(1 if survivors or sha_before != sha_after else 0)

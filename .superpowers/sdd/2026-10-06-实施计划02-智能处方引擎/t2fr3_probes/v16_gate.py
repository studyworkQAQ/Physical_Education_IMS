# -*- coding: utf-8 -*-
"""fr3 post-edit gate: double-direction string check + invariants + fingerprints."""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
CRLF = bytes([13, 10])
LF = bytes([10])


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16].upper()


def norm_fp(b):
    return hashlib.sha256(b.replace(CRLF, LF)).hexdigest()[:16].upper()


def txt(rel):
    return (ROOT / rel).read_bytes().decode("utf-8")


def raw(rel):
    return (ROOT / rel).read_bytes()


fails = []


def expect_absent(tag, rel, needle):
    t = txt(rel)
    n = t.count(needle)
    ok = (n == 0)
    print(f"  {'OK  ' if ok else 'FAIL'} ABSENT [{tag}] {rel} :: {needle[:70]!r} -> {n}")
    if not ok:
        fails.append(f"absent:{tag}:{rel}")


def expect_present(tag, rel, needle, minimum=1):
    t = txt(rel)
    n = t.count(needle)
    ok = (n >= minimum)
    print(f"  {'OK  ' if ok else 'FAIL'} PRESENT[{tag}] {rel} :: {needle[:70]!r} -> {n}")
    if not ok:
        fails.append(f"present:{tag}:{rel}")


print("=" * 78)
print("0. QUERY-MECHANISM CONTROL (a string that must be present, else all "
      "'0 hits' results below are meaningless)")
print("=" * 78)
expect_present("CONTROL", "backend/app/domain/prescription/exercises.py", "class ImpactLevel(str, Enum):")
expect_present("CONTROL", "backend/data/exercises.yaml", "challenge_task:")
expect_present("CONTROL", "Document/2026-09-28-体育闭环原型-设计spec.md", "| **28** |")
expect_present("CONTROL", "backend/tests/db/test_models.py", "def test_all_fifteen_tables_created(session):")

print()
print("=" * 78)
print("1. OLD strings must be GONE (both directions of the #48 gate)")
print("=" * 78)
EX = "backend/app/domain/prescription/exercises.py"
TP = "backend/tests/domain/test_prescription_templates.py"
RP = "backend/app/refdata_prescription.py"
MP = "backend/app/db/models/prescription.py"
TM = "backend/tests/db/test_models.py"
TG = "backend/tests/seed/test_generate.py"
TR = "backend/tests/test_refdata_prescription.py"
EY = "backend/data/exercises.yaml"
QY = "backend/data/exercise_equivalence.yaml"
SPEC = "Document/2026-09-28-体育闭环原型-设计spec.md"

expect_absent("I1", EX, "（19 字符，还撑破 ``String(8)``")
expect_absent("I1", TP, "（19 字符，还会撑破")
expect_absent("I1", EX, "SQLite 会把枚举对象按 ``str()``")
expect_absent("I1", TP, "SQLite 会把枚举对象按 ``str()``")
expect_absent("I2", EX, "改坏任何一份都会让")
expect_absent("I2", EX, "改坏任何一份，``test_equivalence_never_maps_to_a_higher_impact_level``")
expect_absent("I2", TR, "改坏任何一侧都会让")
expect_absent("I2", TR, "改坏任何")
expect_absent("I3", QY, "8 个 low 动作里的 5 个被用到")
expect_absent("I4", TM, "``:163`` / ``:228`` /\n    # ``:472`` 的三处")
expect_absent("I4", MP, "``:24`` / ``:163`` / ``:228`` / ``:472``")
expect_absent("I5", EX, "Plan01 Ruling 19 的口径")
expect_absent("I5", TR, "Plan01 Ruling 19")
expect_absent("I6", EY, "预留为 #29")
expect_absent("I7", SPEC, "编号冲突待 Task 12 处理")
expect_absent("I7", SPEC, "整体后移为 **#29–#35**，并**删掉与本项重复的那一条**")
expect_absent("M1", TR, ":func:`test_impact_level_vocabulary_agrees_with_the_domain_enum`")
expect_absent("M2", RP, "本 Task 的四个函数里计划只点了")
expect_absent("M3", RP, "同一口径）。flush 是必要的")
expect_absent("M4", EY, "spec §7.2 :487 点名的 **12** 项")
expect_absent("M5", TG, "因为那条守卫只遍历 ``DATA_TABLES``")
expect_absent("M5", TG, "落在两个分区之外")
expect_absent("M7", EX, "冲击序由消费方显式声明，今天有两份")
expect_absent("M8", EY, "# 绿层兴趣 / 综合，与两个 addon 模块")
expect_absent("M9", EY, "映射或断言依赖它")
expect_absent("M10", EX, "故专家可以通过调整书写顺序来\n        表达偏好")

print()
print("=" * 78)
print("2. NEW strings must be PRESENT")
print("=" * 78)
expect_present("I1", EX, "**没有任何一种口径给得出 19**")
expect_present("I1", EX, "``String(8).bind_processor(sqlite 方言)`` 实测返回 ``None``")
expect_present("I1", TP, "那是 **16** 字符，不是")
expect_present("I2", EX, "改坏**生产侧** :data:`IMPACT_RANK`（``HIGH: 0 ↔ LOW: 2`` 对调）→")
expect_present("I2", EX, "**``test_equivalence_never_maps_to_a_higher_impact_level`` 保持绿**")
expect_present("I2", EX, "改坏**本字典**（``HIGH: 0 ↔ LOW: 2`` 对调）→")
expect_present("I2", TR, "改坏**本常量**（反序成 ``(\"low\", \"medium\", \"high\")``）→")
expect_present("I2", TR, "**本条只看得到测试侧那一份**")
expect_present("I3", QY, "8 个 low 动作里被用到的是 **4** 个")
expect_present("I3", QY, "band_resistance / dynamic_stretching")
expect_present("I4", TM, 'git grep -n "== 15" --')
expect_present("I4", TM, "在代码基线 ``966eae0`` 上是 ``:169`` / ``:236``")
expect_present("I4", MP, 'git grep -n "== 15" -- backend/tests/db/test_models.py')
expect_present("I4", MP, "``:169`` /\n      ``:236`` / ``:494``")
expect_present("I5", EX, "**spec §4.2**：那张「8 项原始测量」的表里 BMI")
expect_present("I5", EX, "Ruling 17 的关切 1 据此裁定")
expect_present("I5", TR, "spec §4.2：短板判定项 = 6 个，排除 BMI")
expect_present("I6", EY, "「动作库的视频源」排在 **#30**")
expect_present("I7", SPEC, "编号冲突已由计划 02 的 `d40f36c` 处理完毕")
expect_present("I7", SPEC, "**7 项 − 1 项重复 = 6 项、连续编号 #29–#34**")
expect_present("I7", SPEC, "`:682` / `:684` / `:688` / `:707`")
expect_present("M1", TR, ":func:`test_exercise_impact_level_vocabulary_agrees_with_the_domain_enum`\n    分工不同")
expect_present("M2", RP, "主语是**加载侧的四个函数**")
expect_present("M2", RP, "本模块公有函数是 **5** 个")
expect_present("M3", RP, "**只在「不 commit」这半句同口径**")
expect_present("M3", RP, "本函数**既不 commit 也不\n    flush**")
expect_present("M4", EY, "**出处不止一行**")
expect_present("M4", EY, "散文的 12 项 − 可选挑战任务 + 抗阻优先模块（addons 代码块）")
expect_present("M5", TG, "**两条守卫都只遍历「已被分区认领」的表**")
expect_present("M6", EY, "这两个数没有出处")
expect_present("M6", EY, "**不被任何测试守卫**")
expect_present("M6", EY, "工程估计、无出处、不被任何测试守卫")
expect_present("M7", EX, "**两个消费方各一份**")
expect_present("M7", EX, "第三处**期望值**")
expect_present("M8", EY, "本节 5 个条目**跨红 / 黄 / 绿三层**")
expect_present("M9", EY, "没有任何一条\n# 断言会**因为它消失**而变红")
expect_present("M10", EX, "故专家可以通过调整书写顺序来表达偏好，不必引入一个额外的优先级字段。")

print()
print("=" * 78)
print("3. fingerprints / bytes / line endings")
print("=" * 78)
ex_b = raw("backend/data/exercises.yaml")
eq_b = raw("backend/data/exercise_equivalence.yaml")
csv_b = raw("backend/data/national_standard_2014.csv")
print(f"  exercises.yaml            {len(ex_b)} B  CRLF {ex_b.count(CRLF)}  normfp {norm_fp(ex_b)}")
print(f"  exercise_equivalence.yaml {len(eq_b)} B  CRLF {eq_b.count(CRLF)}  normfp {norm_fp(eq_b)}")
print(f"  national_standard_2014.csv{len(csv_b)} B  CRLF {csv_b.count(CRLF)}  normfp {norm_fp(csv_b)}")
if ex_b.count(CRLF) != 0:
    fails.append("exercises.yaml CRLF != 0")
if eq_b.count(CRLF) != 0:
    fails.append("exercise_equivalence.yaml CRLF != 0")
if len(csv_b) != 21412 or norm_fp(csv_b) != "D2C8E539E2FA0029" or csv_b.count(CRLF) != 0:
    fails.append("CSV FORBIDDEN ZONE changed")
tr = txt(TR)
if f'EXERCISES_FINGERPRINT = "{norm_fp(ex_b)}"' not in tr:
    fails.append("EXERCISES_FINGERPRINT constant != recomputed")
    print(f"  FAIL EXERCISES_FINGERPRINT constant mismatch (expect {norm_fp(ex_b)})")
else:
    print(f"  OK   EXERCISES_FINGERPRINT constant == recomputed == {norm_fp(ex_b)}")
if f'EQUIVALENCE_FINGERPRINT = "{norm_fp(eq_b)}"' not in tr:
    fails.append("EQUIVALENCE_FINGERPRINT constant != recomputed")
    print(f"  FAIL EQUIVALENCE_FINGERPRINT constant mismatch (expect {norm_fp(eq_b)})")
else:
    print(f"  OK   EQUIVALENCE_FINGERPRINT constant == recomputed == {norm_fp(eq_b)}")
if tr.count("A6A000F58815FCBB") or tr.count("0FFB881574AC04F3"):
    fails.append("stale fingerprint constant still present")
    print("  FAIL a stale fingerprint constant is still present")
else:
    print("  OK   no stale fingerprint constant left")

sp = raw(SPEC)
spl = sp.decode("utf-8").replace("\r\n", "\n").split("\n")
print(f"  spec: {len(sp)} B  CRLF {sp.count(CRLF)}  lines {len(spl) - 1}  normfp {norm_fp(sp)}")
if sp.count(CRLF) != 974:
    fails.append(f"spec CRLF {sp.count(CRLF)} != 974")

print()
print("=" * 78)
print("4. forbidden zone / hygiene")
print("=" * 78)
print(f"  backend/pe.db exists = {(ROOT / 'backend/pe.db').exists()}")
if (ROOT / "backend/pe.db").exists():
    fails.append("pe.db exists")
seed = ROOT / "backend/data/seed"
nseed = len([p for p in seed.rglob("*") if p.is_file()]) if seed.exists() else -1
print(f"  backend/data/seed files = {nseed}")
if nseed != 0:
    fails.append("data/seed not empty")

print()
print("=" * 78)
print("5. git diff surface")
print("=" * 78)
r = subprocess.run(["git", "diff", "--numstat"], cwd=ROOT, capture_output=True)
print(r.stdout.decode("utf-8", "replace"))
r2 = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True)
print(r2.stdout.decode("utf-8", "replace"))

print()
print("=" * 78)
print(f"RESULT: {'ALL GREEN' if not fails else 'FAILURES -> ' + repr(fails)}")
print("=" * 78)
sys.exit(1 if fails else 0)

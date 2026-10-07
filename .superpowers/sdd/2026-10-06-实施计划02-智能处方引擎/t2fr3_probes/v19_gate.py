# -*- coding: utf-8 -*-
"""fr3 post-edit gate (final): double-direction string check + invariants + fingerprints."""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
CRLF = bytes([13, 10])
LF = bytes([10])

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
CSV = "backend/data/national_standard_2014.csv"


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16].upper()


def norm_fp(b):
    return hashlib.sha256(b.replace(CRLF, LF)).hexdigest()[:16].upper()


def txt(rel):
    return (ROOT / rel).read_bytes().decode("utf-8")


def raw(rel):
    return (ROOT / rel).read_bytes()


fails = []


def A(tag, rel, needle):
    n = txt(rel).count(needle)
    ok = n == 0
    print(f"  {'OK  ' if ok else 'FAIL'} ABSENT  [{tag:4s}] {pathlib.Path(rel).name:34s} {needle[:60]!r} -> {n}")
    if not ok:
        fails.append(f"absent:{tag}:{rel}:{needle[:40]}")


def P(tag, rel, needle, minimum=1):
    n = txt(rel).count(needle)
    ok = n >= minimum
    print(f"  {'OK  ' if ok else 'FAIL'} PRESENT [{tag:4s}] {pathlib.Path(rel).name:34s} {needle[:60]!r} -> {n}")
    if not ok:
        fails.append(f"present:{tag}:{rel}:{needle[:40]}")


print("=" * 100)
print("0. QUERY-MECHANISM CONTROL — these must be present, otherwise every '0 hits' below is meaningless")
print("=" * 100)
P("CTRL", EX, "class ImpactLevel(str, Enum):")
P("CTRL", EY, "challenge_task:")
P("CTRL", SPEC, "| **28** |")
P("CTRL", TM, "def test_all_fifteen_tables_created(session):")
P("CTRL", TR, "def test_equivalence_never_maps_to_a_higher_impact_level():")
P("CTRL", QY, "version: \"1.0\"")
P("CTRL", TG, "def test_table_partition_is_exhaustive():")
P("CTRL", RP, "def sync_exercises(session: Session) -> int:")
P("CTRL", MP, "class Exercise")
P("CTRL", TP, "def test_impact_level_is_a_str_enum_so_it_round_trips_through_the_db():")

print()
print("=" * 100)
print("1. OLD (retracted) strings must be GONE — including every verbatim reproduction")
print("=" * 100)
A("I1", EX, "（19 字符")
A("I1", TP, "（19 字符")
A("I1", EX, "SQLite 会把枚举对象按 ``str()``")
A("I1", TP, "SQLite 会把枚举对象按 ``str()``")
A("I1", EX, "漏写一处的失效形态是**静默的**")
A("I1", TP, "漏写一处的失效形态是**静默的**")
A("I2", EX, "改坏任何")
A("I2", TR, "改坏任何")
A("I2", EX, "今天有两份")
A("I2", EX, "两侧不同源，改坏")
A("I3", QY, "5 个被用到")
A("I4", TM, ":163")
A("I4", TM, ":228")
A("I4", TM, ":472")
A("I4", MP, ":163")
A("I4", MP, ":228")
A("I4", MP, ":472")
A("I5", EX, "Ruling 19")
A("I5", TR, "Ruling 19")
A("I6", EY, "预留为 #29")
A("I7", SPEC, "编号冲突待 Task 12 处理")
A("I7", SPEC, "须把它那 7 项整体后移为")
A("I7", SPEC, "计划 `:681` 与 `:685`")
A("M1", TR, ":func:`test_impact_level_vocabulary_agrees_with_the_domain_enum`")
A("M2", RP, "本 Task 的四个函数里计划只点了")
A("M3", RP, "同一口径）。flush 是必要的")
A("M4", EY, ":487 点名的 **12** 项")
A("M4", EY, ":487 点名的 12 项")
A("M5", TG, "因为那条守卫只遍历")
A("M5", TG, "落在两个分区之外")
A("M8", EY, "# 绿层兴趣 / 综合")
A("M9", EY, "映射或断言依赖它")
A("M10", EX, "调整书写顺序来\n        表达偏好")

print()
print("=" * 100)
print("2. NEW strings must be PRESENT")
print("=" * 100)
P("I1", EX, "**没有任何一种口径给得出 19**")
P("I1", EX, "``String(8).bind_processor(sqlite 方言)`` 实测返回 ``None``")
P("I1", EX, "读回是 ``'high'``（``typeof=text``、SQLite ``length()=4``）")
P("I1", EX, "那是 **16** 字符")
P("I1", TP, "那是 **16** 字符，不是")
P("I1", TP, "``length()=4``")
P("I2", EX, "改坏**生产侧** :data:`IMPACT_RANK`（``HIGH: 0 ↔ LOW: 2`` 对调）→")
P("I2", EX, "**``test_equivalence_never_maps_to_a_higher_impact_level`` 保持绿**")
P("I2", EX, "改坏**本字典**（``HIGH: 0 ↔ LOW: 2`` 对调）→")
P("I2", EX, "各 ``2 failed, 529 passed``")
P("I2", TR, "改坏**本常量**（反序成")
P("I2", TR, "**本条只看得到测试侧那一份**")
P("I2", TR, "两次都是 ``2 failed, 529")
P("I3", QY, "8 个 low 动作里被用到的是 **4** 个")
P("I3", QY, "band_resistance / dynamic_stretching")
P("I3", QY, "各被 2 条复用")
P("I4", TM, 'git grep -n "== 15" --')
P("I4", TM, "在代码基线 ``966eae0`` 上是")
P("I4", TM, "``:169`` / ``:236``")
P("I4", MP, 'git grep -n "== 15" -- backend/tests/db/test_models.py')
P("I4", MP, "现命中 **3** 处")
P("I4", MP, "``:169`` /")
P("I4", MP, "``966eae0``")
P("I5", EX, "**spec §4.2**：那张「8 项原始测量」的表里 BMI")
P("I5", EX, "Ruling 17 的关切 1 据此裁定")
P("I5", EX, "不复述那个错号")
P("I5", TR, "spec §4.2：短板判定项 = 6 个，排除 BMI")
P("I6", EY, "「动作库的视频源」排在 **#30**")
P("I6", EY, "变成 **#30**")
P("I7", SPEC, "编号冲突已由计划 02 的 `d40f36c` 处理完毕")
P("I7", SPEC, "**7 项 − 1 项重复 = 6 项、连续编号 #29–#34**")
P("I7", SPEC, "`:682` / `:684` / `:688` / `:707`")
P("I7", SPEC, "唯一仍可能出现的 #35")
P("M1", TR, ":func:`test_exercise_impact_level_vocabulary_agrees_with_the_domain_enum`")
P("M2", RP, "主语是**加载侧的四个函数**")
P("M2", RP, "本模块公有函数是 **5** 个")
P("M3", RP, "**只在「不 commit」这半句同口径**")
P("M3", RP, "本函数**既不 commit 也不")
P("M4", EY, "**出处不止一行**")
P("M4", EY, "+ 抗阻优先模块（addons 代码块）")
P("M5", TG, "**两条守卫都只遍历「已被分区认领」的表**")
P("M5", TG, "落在**任何**分区之外")
P("M6", EY, "这两个数没有出处")
P("M6", EY, "**不被任何测试守卫**")
P("M6", EY, "工程估计、无出处、不被任何测试守卫")
P("M6", EY, "地面反作用力峰值 ÷ 体重")
P("M7", EX, "**两个消费方各一份**")
P("M7", EX, "第三处**期望值**")
P("M8", EY, "本节 5 个条目**跨红 / 黄 / 绿三层**")
P("M8", EY, "与条目的 `impact_level`")
P("M9", EY, "**因为它消失**而变红")
P("M9", EY, "只证明「等价表里没有的 ref")
P("M10", EX, "故专家可以通过调整书写顺序来表达偏好，不必引入一个额外的优先级字段。")

print()
print("=" * 100)
print("3. bytes / line endings / fingerprints")
print("=" * 100)
ex_b, eq_b, csv_b, sp_b = raw(EY), raw(QY), raw(CSV), raw(SPEC)
print(f"  {EY:44s} {len(ex_b):7d} B  CRLF {ex_b.count(CRLF):5d}  normfp {norm_fp(ex_b)}")
print(f"  {QY:44s} {len(eq_b):7d} B  CRLF {eq_b.count(CRLF):5d}  normfp {norm_fp(eq_b)}")
print(f"  {CSV:44s} {len(csv_b):7d} B  CRLF {csv_b.count(CRLF):5d}  normfp {norm_fp(csv_b)}")
print(f"  {SPEC:44s} {len(sp_b):7d} B  CRLF {sp_b.count(CRLF):5d}  normfp {norm_fp(sp_b)}")
if ex_b.count(CRLF) != 0:
    fails.append("exercises.yaml CRLF != 0")
if eq_b.count(CRLF) != 0:
    fails.append("exercise_equivalence.yaml CRLF != 0")
if (len(csv_b), norm_fp(csv_b), csv_b.count(CRLF)) != (21412, "D2C8E539E2FA0029", 0):
    fails.append("CSV FORBIDDEN ZONE CHANGED")
else:
    print("  OK   CSV forbidden zone untouched (21412 B / D2C8E539E2FA0029 / CRLF 0)")
if sp_b.count(CRLF) != 974 or sp_b.count(LF) != 974:
    fails.append(f"spec line endings changed: CRLF {sp_b.count(CRLF)} / LF {sp_b.count(LF)}")
else:
    print("  OK   spec still 974 lines, all CRLF")
tr = txt(TR)
for name, want in (("EXERCISES_FINGERPRINT", norm_fp(ex_b)),
                   ("EQUIVALENCE_FINGERPRINT", norm_fp(eq_b))):
    if f'{name} = "{want}"' in tr:
        print(f"  OK   {name} == recomputed == {want}")
    else:
        fails.append(f"{name} mismatch, expected {want}")
        print(f"  FAIL {name} != recomputed {want}")
for stale in ("A6A000F58815FCBB", "0FFB881574AC04F3", "AA2BE3D26D1B3B1E"):
    if stale in tr:
        fails.append(f"stale fingerprint {stale} still in test file")
        print(f"  FAIL stale fingerprint {stale} still present")
print("  OK   no stale fingerprint constant left" if not any(
    s in tr for s in ("A6A000F58815FCBB", "0FFB881574AC04F3", "AA2BE3D26D1B3B1E")) else "")

print()
print("=" * 100)
print("4. forbidden zone / hygiene")
print("=" * 100)
pedb = (ROOT / "backend/pe.db").exists()
print(f"  backend/pe.db exists = {pedb}")
if pedb:
    fails.append("pe.db exists")
seed = ROOT / "backend/data/seed"
nseed = len([p for p in seed.rglob("*") if p.is_file()]) if seed.exists() else -1
print(f"  backend/data/seed file count = {nseed}")
if nseed != 0:
    fails.append("data/seed not empty")
for forbidden in (".gitattributes", ".gitignore"):
    r = subprocess.run(["git", "diff", "--name-only", "--", forbidden], cwd=ROOT,
                       capture_output=True)
    if r.stdout.strip():
        fails.append(f"{forbidden} was modified")
        print(f"  FAIL {forbidden} modified")
    else:
        print(f"  OK   {forbidden} untouched")

print()
print("=" * 100)
print("5. git diff surface (numstat)")
print("=" * 100)
print(subprocess.run(["git", "diff", "--numstat"], cwd=ROOT,
                     capture_output=True).stdout.decode("utf-8", "replace"))
print(subprocess.run(["git", "status", "--short"], cwd=ROOT,
                     capture_output=True).stdout.decode("utf-8", "replace"))

print("=" * 100)
print(f"RESULT: {'ALL GREEN' if not fails else 'FAILURES (' + str(len(fails)) + ') -> ' + repr(fails)}")
print("=" * 100)
sys.exit(1 if fails else 0)

"""Task 9 亲验：指纹 / spec §14 行数（数换行口径，硬规矩 #93）/ 夹具 / 重命名的连带。"""
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

print("### 1. 三个指纹（用与测试同一个算法）")
EXPECT = {
    "data/national_standard_2014.csv": "D2C8E539E2FA0029",
    "data/exercise_equivalence.yaml": "822CB86A5E998301",
}
for rel, want in EXPECT.items():
    b = (BACKEND / rel).read_bytes()
    got = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
    print(f"  {rel:40s} {len(b):7d} B CRLF={b.count(bytes([13,10])):3d} {got} "
          f"{'OK 未变' if got == want else '⚠️ 变了！'}")
b = (BACKEND / "data" / "exercises.yaml").read_bytes()
got = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
print(f"  {'data/exercises.yaml':40s} {len(b):7d} B CRLF={b.count(bytes([13,10])):3d} {got} "
      f"{'（P9-A3 预期变了）' if got != '3DE598AF38631209' else '⚠️ 没变？'}")
rf = (BACKEND / "tests" / "test_refdata_prescription.py").read_text(encoding="utf-8")
import re  # noqa: E402
for m in re.finditer(r'^(EXERCISES_FINGERPRINT|EQUIVALENCE_FINGERPRINT)\s*=\s*"([0-9A-F]+)"', rf, re.M):
    print(f"  常量 {m.group(1)} = {m.group(2)}   与实测{'一致' if m.group(2) == got or m.group(1) != 'EXERCISES_FINGERPRINT' else '⚠️ 不一致'}")
print(f"  18 套模板 YAML 总字节 = {sum(p.stat().st_size for p in sorted((BACKEND/'data'/'prescription').glob('*.yaml')))}"
      f"  CRLF 合计 = {sum(p.read_bytes().count(bytes([13,10])) for p in (BACKEND/'data'/'prescription').glob('*.yaml'))}")

print()
print("### 2. spec §14 的行数（数换行 + 校验首尾两行，硬规矩 #93，不用正则抽编号）")
spec = ROOT / "Document" / "2026-09-28-体育闭环原型-设计spec.md"
sb = spec.read_bytes()
st = sb.decode("utf-8")
SL = st.split("\n")
N_LF = st.count("\n")
N_CRLF = sb.count(bytes([13, 10]))
print(f"  spec {len(sb)} B / {len(SL)} 行 / CRLF={N_CRLF} / LF={N_LF}")
s = next(i for i, l in enumerate(SL) if l.startswith("## 14"))
e = next(i for i in range(s + 1, len(SL)) if SL[i].startswith("## "))
rows = [i for i in range(s, e) if SL[i].startswith("| ")]
print(f"  §14 在 :{s+1}-:{e}；以 '| ' 开头的行 = {len(rows)} 个")
hdr = [i for i in rows if SL[i].startswith("| #") or SL[i].startswith("|---")]
body_rows = [i for i in rows if i not in hdr]
print(f"  去掉表头/分隔行 = {len(body_rows)} 个数据行")
print(f"  首行 :{body_rows[0]+1} = {SL[body_rows[0]][:80]}")
print(f"  末行 :{body_rows[-1]+1} = {SL[body_rows[-1]][:80]}")
print(f"  「刻意的空洞」那段还在吗? {'刻意的空洞' in st}")
for pat in ("1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952",
            "2b2649add55205e668c40e287f91592c0bcfcd68599d725030a68fc2400456df",
            "fe0a44e052c7946b", "2ef85d79"):
    print(f"  spec 里 {pat[:20]}… 命中 {st.count(pat)}")

print()
print("### 3. golden_cases.json 仍能解析、例数仍 13、input/expected 的 id 对齐")
gc = BACKEND / "tests" / "fixtures" / "golden_cases.json"
raw = gc.read_bytes()
data = json.loads(raw.decode("utf-8"))
inp, exp = data["input"], data["expected"]
print(f"  {len(raw)} B / sha16={hashlib.sha256(raw).hexdigest()[:16].upper()} / 顶层键={sorted(data)}")
print(f"  len(input)={len(inp)}  len(expected)={len(exp)}")
ids_i = [c["student_id"] for c in inp]
ids_e = [c["student_id"] for c in exp]
print(f"  id 对齐? {ids_i == ids_e}   ids={ids_i}")
print(f"  expected[0] 的键数 = {len(exp[0])}（Plan 01 是 11，Task 9 应 +12 = 23）")
print(f"  expected[0] 的键 = {sorted(exp[0])}")
print(f"  _meta 的键 = {sorted(data['_meta'])}")
print(f"  _meta 里 'Task 10' 命中 = {json.dumps(data['_meta'], ensure_ascii=False).count('Task 10')}")
print(f"  _meta 里 'Plan 01 的 Task 10' 命中 = {json.dumps(data['_meta'], ensure_ascii=False).count('Plan 01 的 Task 10')}")

print()
print("### 4. 13 例的处方相关期望值（顶回 ① 的实测复核）")
for i, e in enumerate(exp):
    tid = e.get("template_id")
    nr = e.get("needs_review")
    ss = e.get("safety_substitutions")
    st_ = e.get("safety_triggers")
    sk = e.get("safety_skipped")
    print(f"  {ids_e[i]:5s} label={e.get('label','?'):18s} template_id={str(tid):16s} "
          f"needs_review={nr!r:6s} subs={len(ss) if isinstance(ss, list) else ss!r} "
          f"triggers={st_} skipped={sk}")

print()
print("### 5. 待清扫第 2 条的重命名连带（_DERIVED_TABLES -> _BATCH_OWNED_TABLES）")
for rel in ("app/pipeline/daily.py", "tests/pipeline/test_daily.py"):
    s2 = (BACKEND / rel).read_text(encoding="utf-8")
    print(f"  {rel}: _DERIVED_TABLES 命中 {s2.count('_DERIVED_TABLES')}  "
          f"_BATCH_OWNED_TABLES 命中 {s2.count('_BATCH_OWNED_TABLES')}")

print()
print("### 6. 公开面 / 扫描面 / 表数（应全部未变）")
import app.domain.prescription as PKG  # noqa: E402
from app.db import models as M  # noqa: E402
print(f"  __all__ = {len(PKG.__all__)}  (应 51)")
print(f"  表数 = {len(M.Base.metadata.tables)}  (应 18)")
tot = sum(len(list((BACKEND / "app" / s).rglob("*.py"))) for s in ("domain", "pipeline", "db"))
print(f"  扫描面 = {tot}  (应 35)")
print(f"  pe.db 存在? {(BACKEND/'pe.db').exists()}   data/seed 文件数 = "
      f"{len(list((BACKEND/'data'/'seed').rglob('*'))) if (BACKEND/'data'/'seed').exists() else 'DIR-ABSENT'}")

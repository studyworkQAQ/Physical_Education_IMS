"""Plan 03 Task 6 亲验 + 结案（Ruling 16 + 控制者错误 #26-#28）。
⚠️ 硬规矩 #109：跑出「不符项」必须先用第二个独立工具复核，才允许写进账本。
⚠️ 硬规矩 #107：谓词先对已知反例验证。
"""
import dataclasses
import hashlib
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
# ⚠️ 本文件在 <plan dir>/t6_probes/ 下，比 _t6_preflight_patch.py（在 <plan dir>/ 下）深一层，
#    故仓库根是 parents[3] 而不是 parents[2]。控制者已为同一个深度错栽过三次
#    （t3_probes / t4_probes / t6_probes），每次都靠下面这条 assert 当场抓住。
ROOT = HERE.parents[3]
BACKEND = ROOT / "backend"
LEDGER = HERE / "progress.md"
assert BACKEND.is_dir(), f"BACKEND 算错了：{BACKEND}"
sys.path.insert(0, str(BACKEND))
ok = True


def chk(label, got, want):
    global ok
    good = got == want
    ok &= good
    print(f"  {'✅' if good else '⚠️'} {label}: 实测 {got!r}  期望 {want!r}")


print("### 1. 扫描面 / 表数 / 公有面")
from app.db import models as M  # noqa: E402
chk("表数", len(M.Base.metadata.tables), 25)
tot = sum(len(list((BACKEND / "app" / s).rglob("*.py"))) for s in ("pipeline", "db", "domain", "api"))
chk("扫描面", tot, 52)
obs = {n for n in dir(M) if not n.startswith("_")}
subs = {"_shared", "organisation", "assessment", "derived", "ops", "feedback", "prescription"}
chk("models 公有面", len(obs - subs), 33)

print("\n### 2. alerts.py 的公开面与 Signals 的字段（P6-A1 + 顶回 3/4/5）")
import app.domain.alerts as AL  # noqa: E402
print(f"  __all__ = {len(AL.__all__)} 个: {sorted(AL.__all__)}")
chk("__all__ 长度", len(AL.__all__), 16)
for name in ("StudentSignals", "ClassSignals", "StudentHit", "ClassHit", "AlertRule", "AlertRules"):
    o = getattr(AL, name, None)
    if o is None or not dataclasses.is_dataclass(o):
        print(f"  ⚠️ {name} 不是 dataclass")
        ok = False
        continue
    fs = [f.name for f in dataclasses.fields(o)]
    print(f"  {name}（{len(fs)} 字段）= {fs}")
ss = [f.name for f in dataclasses.fields(AL.StudentSignals)]
cs = [f.name for f in dataclasses.fields(AL.ClassSignals)]
sh = [f.name for f in dataclasses.fields(AL.StudentHit)]
ch = [f.name for f in dataclasses.fields(AL.ClassHit)]
for want, where, lst in (("rpe_session_ids", "StudentSignals", ss), ("mini_test_ids", "StudentSignals", ss),
                         ("checkin_gap_end", "StudentSignals(顶回4)", ss),
                         ("semester_id", "StudentSignals(顶回5)", ss), ("week", "StudentSignals(顶回5)", ss),
                         ("semester_id", "ClassSignals", cs), ("week", "ClassSignals", cs),
                         ("window_key", "StudentHit", sh), ("subject_key", "StudentHit(顶回3)", sh),
                         ("snapshot", "StudentHit", sh),
                         ("window_key", "ClassHit", ch), ("subject_key", "ClassHit(顶回3)", ch)):
    good = want in lst
    ok &= good
    print(f"  {'✅' if good else '⚠️'} {where} 有 {want}")

print("\n### 3. 顶回 3 的附带发现：subject_key 是 String(24)，前缀必须是 section")
al = M.Base.metadata.tables["alert"]
print(f"  alert.subject_key 类型 = {al.c.subject_key.type}  nullable={al.c.subject_key.nullable}")
uq = [c for c in al.constraints if type(c).__name__ == "UniqueConstraint"]
for c in uq:
    print(f"  UNIQUE {c.name} = {[x.name for x in c.columns]}")
longest = f"section:{2**31 - 1}"
print(f"  最长 subject_key 实测 = {longest!r}（{len(longest)} 字符）  <= 24? {len(longest) <= 24}")
bad = f"course_section:{2**31 - 1}"
print(f"  若用 course_section 前缀 = {len(bad)} 字符  -> 超宽 {len(bad) - 24}")

print("\n### 4. 顶回 6：GREEN_MASTERY 用 >= 而不是 ==（参数名 completion_rate_min）")
src = (BACKEND / "app" / "domain" / "alerts.py").read_text(encoding="utf-8")
print(f"  alerts.py {len(src.encode('utf-8'))} B / {src.count(chr(10))} 行")
import re  # noqa: E402
for i, l in enumerate(src.split("\n")):
    if "completion_rate_min" in l or "completion_rate >=" in l or "completion_rate ==" in l:
        print(f"  :{i+1} {l.strip()[:130]}")

print("\n### 5. 顶回 1：refdata_yaml 的 doc_kind 是必填 keyword-only")
import app.refdata_yaml as RY  # noqa: E402
import inspect  # noqa: E402
print(f"  refdata_yaml 的公开函数 = {sorted(n for n in dir(RY) if not n.startswith('_') and callable(getattr(RY, n)))}")
for n in ("fail", "exact_keys", "as_int", "as_float", "as_optional_text", "line_index"):
    f = getattr(RY, n, None)
    if f is None:
        print(f"  ⚠️ {n} 不存在")
        ok = False
        continue
    sig = inspect.signature(f)
    kw_only = [p.name for p in sig.parameters.values()
               if p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is inspect.Parameter.empty]
    print(f"  {n}{sig}   必填 keyword-only = {kw_only}")

print("\n### 6. 顶回 2：_PRESCRIPTION_PUBLIC_BASELINE 实测是 51 不是 24")
tr = (BACKEND / "tests" / "test_refdata_prescription.py").read_text(encoding="utf-8")
for m in re.finditer(r"assert len\(_PRESCRIPTION_PUBLIC_BASELINE\)\s*==\s*(\d+)", tr):
    print(f"  assert len(...) == {m.group(1)}")
import app.domain.prescription as PP  # noqa: E402
print(f"  app.domain.prescription.__all__ 实测 = {len(PP.__all__)} 个")

print("\n### 7. alert_rules.yaml 的指纹与行尾 + _ALERTS_PUBLIC_BASELINE")
y = (BACKEND / "data" / "alert_rules.yaml").read_bytes()
fp = hashlib.sha256(y.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()
chk("alert_rules.yaml 字节数", len(y), 6037)
chk("CRLF 计数", y.count(b"\r\n"), 0)
chk("sha256[:16]", fp, "E48E3AC82BB45BB7")
print(f"  version 那一行 = {[l for l in y.decode('utf-8').split(chr(10)) if l.startswith('version')]}")
ta = (BACKEND / "tests" / "test_refdata_alerts.py").read_text(encoding="utf-8")
for m in re.finditer(r"assert len\(_ALERTS_PUBLIC_BASELINE\)\s*==\s*(\d+)", ta):
    print(f"  assert len(_ALERTS_PUBLIC_BASELINE) == {m.group(1)}")

print("\n### 8. 三个既有指纹 + data 的 diff 只应多出一行")
for rel, want in (("data/national_standard_2014.csv", "D2C8E539E2FA0029"),
                  ("data/exercises.yaml", "5394B37F01DAC9AC"),
                  ("data/exercise_equivalence.yaml", "822CB86A5E998301")):
    b = (BACKEND / rel).read_bytes()
    chk(rel, hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper(), want)
r = subprocess.run(["git", "diff", "--name-status", "a8d61b4", "HEAD", "--", "backend/data"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
out = (r.stdout or "").strip()
print(f"  git diff --name-status -- backend/data:\n    {out.replace(chr(10), chr(10) + '    ')}")
good = out.strip().splitlines() == ["A\tbackend/data/alert_rules.yaml"]
ok &= good
print(f"  {'✅' if good else '⚠️'} 只多出 alert_rules.yaml 一行")
chk("pe.db 存在?", (BACKEND / "pe.db").exists(), False)

print(f"\n===== 亲验结论：{'全部通过 ✅' if ok else '⚠️ 有不符项（按 #109 先复核再采信）'} =====")

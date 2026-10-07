import os, re, ast, pathlib
ROOT = r"c:\Users\whwenhao\Desktop\Physical_Education_ims"
B = os.path.join(ROOT, "backend")
def rd(rel):
    return open(os.path.join(B, rel),'rb').read().replace(b"\r\n",b"\n").decode("utf-8").split("\n")
def show(rel, pats, ctx=0, label=""):
    L = rd(rel)
    print("\n" + "-"*72)
    print(f"### {rel}   (lines={len(L)-1}) {label}")
    for pat in pats:
        rx = re.compile(pat)
        hits = [(i,s) for i,s in enumerate(L,1) if rx.search(s)]
        print(f"  PATTERN {pat!r} -> {len(hits)} hit(s)")
        for i,s in hits[:20]:
            print(f"    {i:>5}|{s[:250]}")

show(r"tests\db\test_models.py", [r"== 15\b", r"len\(json_text_columns\)", r"len\(_MODELS_PUBLIC_BASELINE\)",
                                  r"恰好 11 列|11 列|今天恰好", r"def test_all_fifteen_tables_created"])
show(r"app\db\models\__init__.py", [r"15 张表|十五", r"九个|9 个", r"from \. import feedback, prescription",
                                    r"约定 2|约定 1|约定 3", r"_in_domain", r"__all__", r"1 张"])
show(r"app\db\models\_shared.py", [r"def _in_domain", r"__all__", r"JsonText"])
show(r"app\refdata.py", [r"^from app\.domain\.tables import", r"def standard|def load_standard", r"_standard_cache",
                         r"MappingProxyType", r"文件名与目录的唯一所有者"])
show(r"app\pipeline\run_stratify.py", [r"^from |^import |re-export|重导出|搬迁"])
show(r"tests\seed\test_generate.py", [r"def test_table_partition_is_exhaustive", r"REFERENCE_TABLES",
                                      r"Base\.metadata\.tables"])
show(r"app\db\session.py", [r"15 张表|14 张表"])
print()
L = rd(r"app\refdata.py")
for n in (7,8,9,21,29,122,194):
    print(f"refdata.py:{n}| {L[n-1][:200]}")
L2 = rd(r"app\pipeline\run_stratify.py")
print()
for n in range(48, 60):
    print(f"run_stratify.py:{n}| {L2[n-1][:200]}")
L3 = rd(r"tests\seed\test_generate.py")
print()
for n in range(480, 536):
    print(f"test_generate.py:{n}| {L3[n-1][:220]}")

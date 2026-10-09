"""Step 0 取证：``tests/db/test_models.py`` 的 11 类命中点，逐格给「运行时现值 vs 新字面量」。

那个文件在 Step 0 之后**收集就炸**（``ImportError: cannot import name 'Alert' from
'app.db.models.feedback'``），pytest 一条也报不出来——故本探针替它把「红在哪」逐格印一遍。
全部数字用运行时口径（硬规矩 #89），不数源码。
"""
import pathlib
import re
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[4] / "backend"
sys.path.insert(0, str(BACKEND))

from app.db.session import Base  # noqa: E402
from app.db import models  # noqa: E402,F401  (把 18 张表注册进 metadata)

tables = Base.metadata.tables
json_cols = [
    f"{t.name}.{c.name}" for t in tables.values() for c in t.columns
    if type(c.type).__name__ == "JsonText"
]
batch_owned = sorted(n for n, t in tables.items() if "batch_id" in set(t.c.keys()))
fk_total = sum(len(c.foreign_keys) for t in tables.values() for c in t.columns)
_IN_DOMAIN = re.compile(r"^\s*(\w+) IN \((.*)\)\s*$")
in_domain = [
    (t.name, _IN_DOMAIN.match(str(c.sqltext)).group(1))
    for t in tables.values() for c in t.constraints
    if type(c).__name__ == "CheckConstraint" and _IN_DOMAIN.match(str(c.sqltext))
]
non_in_domain_checks = [
    f"{t.name}:{c.name}" for t in tables.values() for c in t.constraints
    if type(c).__name__ == "CheckConstraint" and not _IN_DOMAIN.match(str(c.sqltext))
]
public = sorted(n for n in dir(models) if not n.startswith("_"))
submodules = [n for n in public if n in {"organisation", "assessment", "derived",
                                          "prescription", "feedback", "ops"}]

NEW_TABLES = ("class_session", "rpe_record", "training_log", "mini_test",
              "alert", "notification", "weekly_class_report")

ROWS = (
    ("① 函数名 test_all_eighteen_tables_created → twenty_five",
     "def test_all_twenty_five_tables_created 已写进文件", "表还没建 → 该测试收集期 ImportError"),
    ("② expected 集合的 7 个新表名",
     f"实测缺 {sorted(set(NEW_TABLES) - set(tables))}", "缺 7 张 → 集合相等断言红"),
    ("③④ 两处 assert len(tables) == 25（含中文消息里的「25 张表」）",
     f"len(Base.metadata.tables) = {len(tables)}", "18 != 25 → 红"),
    ("⑤ assert len(Base.metadata.tables) == 25（导入面那条守卫里）",
     f"len(Base.metadata.tables) = {len(tables)}", "18 != 25 → 红"),
    ("⑥ assert len(json_text_columns) == 21",
     f"实测 {len(json_cols)}", "14 != 21 → 红"),
    ("⑦ _BATCH_OWNED_TABLES 5 → 9",
     f"实测带 batch_id 的表 {len(batch_owned)} 张 = {batch_owned}", "9 个字面量 vs 5 张实到 → 集合相等红"),
    ("⑧ 那段印着 grep 命令与「3 处本段散文」的注释",
     'git grep -c "== 25" 待表建好后复算', "计数与散文要跟着表数走（硬规矩 #66）"),
    ("⑨ 外键总数（散文，24 → 41）",
     f"实测 {fk_total}", "17 个新外键待建 → 表建好后应是 41"),
    ("⑩ _in_domain 列数（散文，18 → 23）+ 非词表 CHECK（0 → 1）",
     f"实测 in_domain {len(in_domain)}、非 in_domain 的 CHECK {non_in_domain_checks}",
     "5 个新词表列 + 1 处手写 BETWEEN 待建 → 23 / 1"),
    ("⑪ 三处引用 test_all_eighteen_tables_created 这个函数名",
     "已改：test_models.py 两处注释 + models/__init__.py 一处 + prescription.py 两处",
     "函数名改了，引用它的散文必须同步（硬规矩 #66）"),
    ("⑫ 刻意不动：assert len(_MODELS_PUBLIC_BASELINE) == 33（两处）",
     f"实测公有名 {len(public)} 个 = 基线 {len(public) - len(submodules)} + 子模块 {len(submodules)}",
     "P3-A1：7 个新类名走非星号导入 → 公有名仍是 33 + 6，两处 33 一字不改"),
    ("⑬ 刻意不动：_MODELS_SUBMODULES 六个 / models.__all__ 14 个",
     f"实测子模块 {sorted(submodules)}、len(__all__) = {len(models.__all__)}",
     "本 Task 不新增子模块、也不改 __all__"),
    ("⑭ 守卫扩到 11 个表类（Plan 02 的 4 + Plan 03 的 7）",
     "Plan 02 的 4 个今天在 prescription.py；Plan 03 的 7 个尚不存在",
     "收集期 ImportError: cannot import name 'Alert'"),
)

width = max(len(r[0]) for r in ROWS)
for label, got, why in ROWS:
    print(f"{label:<{width}}  |  {got}\n{'':<{width}}  →  {why}\n")

src = (BACKEND / "tests" / "db" / "test_models.py").read_text(encoding="utf-8")
print("test_models.py 的字面量核对（git grep 的运行时替身，硬规矩 #89）：")
for needle in ("== 25", "== 21", "== 33", "== 18"):
    print(f"  {needle!r}: {len(re.findall(re.escape(needle), src))} 处")
print(f"  真断言 assert len(tables) == 25: {src.count('assert len(tables) == 25')} 处")
print("  真断言 assert len(Base.metadata.tables) == 25: "
      f"{src.count('assert len(Base.metadata.tables) == 25')} 处")
for needle in ("eighteen", "twenty_five"):
    print(f"  函数名里的 {needle!r}: {src.count(needle)} 处")
batch_block = re.search(r"_BATCH_OWNED_TABLES = \{(.*?)\}", src, re.S).group(1)
batch_literals = re.findall(r'"([a-z_]+)"', batch_block)
print(f"  _BATCH_OWNED_TABLES 的字面量个数: {len(batch_literals)} -> {sorted(batch_literals)}")

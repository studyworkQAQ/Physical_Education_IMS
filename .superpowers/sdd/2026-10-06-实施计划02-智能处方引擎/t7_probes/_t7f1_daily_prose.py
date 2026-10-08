"""F1-1 连带：test_daily.py 里那张 canonical sha256 取证表的散文同步（硬规矩 #66 / #19）。

一处替换、assert 命中 1 次（硬规矩 #79）。test_daily.py 是 CRLF。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]
P = ROOT / "backend" / "tests" / "pipeline" / "test_daily.py"
src = P.read_text(encoding="utf-8")

OLD = """    ⚠️ **那个字面哈希已经过期两次**（P7-A6；硬规矩 #26：一个修复改变了另一个修复的取证
    基线）。本夹具（``CFG``：60 人 / ``seed=20250828`` / 缺省注入，``D = 2025-09-15``）
    在 Plan 02 Task 7 之后本轮亲跑（``canonical_dump`` 逐字复用，n=1）::

        表集合          sha256                                                            行数合计
        --------------  ----------------------------------------------------------------  --------
        9 张（Plan 01）  1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952   882
        11 张（Task 7）  05c5b2aa4ef2c68d00edf553760fee7cbecb71487108e2e2a3752e7e504d5816   942

    两个哈希都在两次运行之间**逐字相同**（``first == second`` 成立）。**9 张那一行也变了**
    ——不是因为扩表，而是因为 ``run_stratify.input_snapshot_of`` 加了 ``"bmi"`` 与
    ``"snapshot_muscle_p10"`` 两个键（P7-A1 / P7-A3），而 ``stratification_result``
    在那 9 张里。行数 882 → **942** = 882 + 60 张处方 + 0 条周微调。
    ⚠️ **这四个值都不被守卫**（本条刻意不断言字面哈希），它们只是一次取证记录；
    账本与 spec §1.3 印着的 ``fe0a44e052c7946b…`` / 「行数合计 882」由控制者按此回填。
"""

NEW = """    ⚠️ **那个字面哈希已经过期三次**（P7-A6；硬规矩 #26：一个修复改变了另一个修复的取证
    基线）：Task 7 首轮的**扩表**（P7-A5，9 → 11）与 **``input_snapshot`` 加两个键**
    （P7-A1 / P7-A3）各是一次，**fix round 1 给 ``prescription`` 加 ``label_at_generation``
    列**（F1-1，那张表 15 → **16** 列）是第三次。本夹具（``CFG``：60 人 /
    ``seed=20250828`` / 缺省注入，``D = 2025-09-15``）在 fix round 1 之后本轮亲跑
    （``canonical_dump`` 逐字复用，n=1，两遍 ``run_daily``）::

        表集合          sha256                                                            行数合计
        --------------  ----------------------------------------------------------------  --------
        9 张（Plan 01）  1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952   882
        11 张（Task 7）  2b2649add55205e668c40e287f91592c0bcfcd68599d725030a68fc2400456df   942

    两个哈希都在两次运行之间**逐字相同**（``first == second`` 成立）。
    **9 张那一行在 Task 7 首轮变过一次**——不是因为扩表，而是因为
    ``run_stratify.input_snapshot_of`` 加了 ``"bmi"`` 与 ``"snapshot_muscle_p10"`` 两个键
    （P7-A1 / P7-A3），而 ``stratification_result`` 在那 9 张里；**fix round 1 之后它逐字
    未变**（本轮亲验：那一轮只动 ``prescription`` 一张表，而它不在这 9 张里）。
    **11 张那一行两轮各变一次**：首轮是扩表（+60 张处方）与那两个键，fix round 1 是
    ``prescription`` 多了 ``label_at_generation`` 这一列（**列变而行数不变**，仍是
    882 + 60 张处方 + 0 条周微调 = **942**）。
    ⚠️ **这四个值都不被守卫**（本条刻意不断言字面哈希），它们只是一次取证记录；
    账本与 spec §1.3 印着的 ``fe0a44e052c7946b…`` / 「行数合计 882」由控制者按此回填
    （fix round 1 的两个新值也已交回控制者）。
"""

assert src.count(OLD) == 1, src.count(OLD)
P.write_text(src.replace(OLD, NEW), encoding="utf-8", newline="\r\n")
b = P.read_bytes()
print(f"OK  {len(b)} B  CRLF={b.count(bytes([13, 10]))} LF={b.count(bytes([10]))}")
print("   新 11 张值命中次数 =", P.read_text(encoding='utf-8').count("2b2649add55205e6"))
print("   旧 11 张值命中次数 =", P.read_text(encoding='utf-8').count("05c5b2aa4ef2c68d"))

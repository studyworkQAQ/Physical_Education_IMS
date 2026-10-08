"""F1-2 item 3：把两处优化的实测前后值 + 测量条件写进那条时间断言的 docstring。

最小余量 2.03× < 2.5× → 按派单 F1-2 第 3 条，不放宽断言，改为写下实测与条件
（硬规矩 #42：时间断言必须写测量条件）。test_backfill.py 是 CRLF。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]
P = ROOT / "backend" / "tests" / "pipeline" / "test_backfill.py"
src = P.read_text(encoding="utf-8")

OLD = """    ``len(runs) == 112`` **无条件断言**——它是口径不是墙钟，与 trace 钩子无关。
    \"\"\"
"""

NEW = """    ⚠️⚠️ **上面那张表是 Plan 01 的口径**（「本轮 HEAD」指 Plan 01 fix round 3 的 HEAD）：
    「不带 ``--cov`` 28.40–33.95 s」那一行量的是**接入处方阶段之前**的回放。
    **Plan 02 Task 7 接入处方阶段之后本条当场红过一次**，两处优化把它压回基线；
    按硬规矩 #42（余量 < 2× 的时间断言一律是 flaky 断言），fix round 1 把前后值与
    测量条件一并写在这里::

        整学期回放（500 人 ×112 业务日）的 ``elapsed``（= 被断言的那一个量）
        ----------------------------------------------------------------------
        接入处方阶段、**未优化**      52.89 s（另一次亲跑量到 **115.08 s** → 本条当场红）
        两处优化之后（缺省注入）      28.85 s   → 余量 60 / 28.85 = **2.08×**
        两处优化之后（零注入）        28.81 s
        **fix round 1 复测**（n=3）   28.86 / 29.05 / 29.59 s → 最小余量 60 / 29.59 = **2.03×**
        **fix round 1 带 ``--cov``**（n=1） ``elapsed`` = **57.25 s** → 余量 **1.05×**，
                                      被下面那个 ``sys.gettrace()`` 钩子如实 skip
                                      （**钩子今天仍在、仍生效**：skip 出自本文件 ``:182``）

    两处优化都在 ``app/pipeline/prescription_stage.py``（机制逐处写在
    ``_previous_prescriptions`` 与 ``generate_prescriptions`` 的注释里）：

    ① 主查询**同时**按 ``batch_id`` 过滤（那一列 ``index=True``）——只按 ``computed_on``
       单列过滤用不上 ``(student_id, computed_on)`` 那条唯一索引（它**以 ``student_id``
       打头**）→ 全表扫描，而 ``stratification_result`` 到学期末有 **56 000** 行
       （500 × 112）、每行还带一个约 **2 KB** 的 ``input_snapshot``，112 天累计约
       **310 万行**扫描；
    ② 上一张处方的预取用 ``load_only(...)`` 把 4 个大 ``JsonText`` 列**延迟加载**
       ——``training_package`` 是 4 周 ×4 课 ×3 block 的嵌套字典（约 500 个键值对），
       逐人逐日 eager 加载 = 约 **56 000** 次大 JSON 解析，而本阶段**一个字节都不读它**。

    ⚠️ fix round 1 的 **F1-1** 又把 ② 里那次「与 ``stratification_result`` 的连接」整个
    删掉了（触发 2 的标签改从 ``prescription.label_at_generation`` 这一列读，不再回读
    另一张表），故今天 ``load_only`` 留下的是 **7** 个小列。**净效果已含在上面那三行
    28.86 / 29.05 / 29.59 s 里**（它们量的是加列之后的 HEAD）。

    **测量条件**（硬规矩 #42 要求写下）：Windows 10（10.0.26200）/ AMD64 /
    Intel64 Family 6 Model 197 / 16 核，CPython 3.11.1、SQLAlchemy 2.1.3、SQLite 3.39.4、
    pytest 9.1.1、coverage 7.16.2；**本地 SQLite 文件**（不是 ``:memory:``）；
    ``elapsed`` = ``run_backfill`` 那一段的 ``time.perf_counter`` 之差，**不含**
    ``build_dataset`` / ``write_csv`` / ``seed_database``（``--durations`` 口径的
    ``replay`` setup 比它多约 0.4–1.5 s：本轮三次实测 **30.10 / 30.65 / 30.59 s**）；
    n=3 独立干净跑、**不带** ``--cov``、无任何 trace 钩子（探针里 ``assert
    sys.gettrace() is None``）；带 ``--cov=app.domain --cov-branch`` 的那一行是 n=1、
    且**必然**被 skip（1.05× < 2×）。⚠️ 本机墙钟极差本来就大（同一个夹具在优化前
    量到过 52.89 s 与 115.08 s），故 **2.03× 只是刚过硬规矩 #42 的 2× 线**；
    ⚠️ 而它**抓不到「慢但没超 60 s」**——处方阶段若再退化 2×（到约 58 s）本条照样绿。
    上面这些数**一律不被守卫**，被断言的只有 ``elapsed < 60``。

    ``len(runs) == 112`` **无条件断言**——它是口径不是墙钟，与 trace 钩子无关。
    \"\"\"
"""

assert src.count(OLD) == 1, src.count(OLD)
assert src.count("52.89") == 0 and src.count("115.08") == 0, "docstring 里已有同名数字，需人工核"
P.write_text(src.replace(OLD, NEW), encoding="utf-8", newline="\r\n")
b = P.read_bytes()
after = P.read_text(encoding="utf-8")
print(f"OK  {len(b)} B  CRLF={b.count(bytes([13, 10]))} LF={b.count(bytes([10]))}")
for probe in ("52.89", "115.08", "28.86 / 29.05 / 29.59", "57.25", "2.03×", "sys.gettrace()"):
    print(f"   {probe!r:32s} 命中 {after.count(probe)}")

"""把「取证脚本未入库」那两处措辞改成实际的处置（脚本已搬进本工作区的 t2_probes/）。

对 **报告文件** 与 **生成它的 p09** 做同一组字节级替换，于是重跑 p09 仍然逐字复现
修正后的报告（两侧不会漂移）。替换前后都按 read_bytes() 复核，且都要求命中恰好一次。
"""
import hashlib
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
REPORT = HERE.parents[0] / "task-2-report.md"
P09 = HERE / "p09_write_report.py"

PAIRS = (
    (
        "**取证脚本**（全在 `backend/t2_probes/`，**未入库**——与 Plan 02 Task 3 的 `t3_probes/`\n"
        "同一处置；`test_models.py` 里对它的引用因此是「历史取证」性质的）：",
        "**取证脚本**（8 个，全部住在**本工作区**的 `t2_probes/` 下，与控制者的\n"
        "`_preflight.py` 同目录；这与 Plan 02 的 `fr2_probes/` / `fr3_probes/` /\n"
        "`t3_probes/` 是同一个约定——探针**入库、可复现**，`test_models.py` 里对\n"
        "`t2_probes/p01…p03` 的引用因此指向真实存在的文件。⚠️ `backend/` 下**不留**\n"
        "本 Task 的任何临时文件：开工时先建在 `backend/t2_probes/`，收工时按新深度\n"
        "修好每个脚本里「用 `__file__` 反推 backend」的那一行后整体搬过来，\n"
        "并逐个重跑确认可用）：",
    ),
    (
        "**分支** `feature/plan-03-feedback-alert-crud-api`　**基线** `bcf3936`　**HEAD** `fd73788`",
        "**分支** `feature/plan-03-feedback-alert-crud-api`　**基线** `bcf3936`　**HEAD** `fd73788`\n"
        "**工作树**：三个 commit 之后 `backend/` 下零残留（`git status` 只剩本报告与\n"
        "`t2_probes/` 两类 `.superpowers/` 下的未跟踪文件，按惯例由控制者的结案 commit 收）",
    ),
)

for path in (REPORT, P09):
    raw = path.read_bytes()
    before = hashlib.sha256(raw).hexdigest()[:16].upper()
    text = raw.decode("utf-8")
    for old, new in PAIRS:
        assert text.count(old) == 1, (path.name, text.count(old), old[:40])
        text = text.replace(old, new, 1)
    out = text.replace("\r\n", "\n").encode("utf-8")
    path.write_bytes(out)
    after = hashlib.sha256(out).hexdigest()[:16].upper()
    print(f"{path.name:24s} {len(raw)} -> {len(out)} B   sha256[:16] {before} -> {after}"
          f"   CRLF={out.count(bytes([13, 10]))}")

final = REPORT.read_bytes()
print("\nreport:", len(final), "B /", final.count(b"\n"), "lines / BOM",
      final[:3] == bytes([0xEF, 0xBB, 0xBF]))

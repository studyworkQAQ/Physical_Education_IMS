"""把 ① 节表格里「只剩未跟踪的 backend/t2_probes/」那一格改成实际处置（同 p11 的手法）。"""
import hashlib
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
REPORT = HERE.parents[0] / "task-2-report.md"
P09 = HERE / "p09_write_report.py"

OLD = "| 分支 / 工作树 | `feature/plan-03-feedback-alert-crud-api` / 干净 | 同分支，工作树干净（只剩未跟踪的 `backend/t2_probes/`） |"
NEW = ("| 分支 / 工作树 | `feature/plan-03-feedback-alert-crud-api` / 干净 | 同分支；"
       "三个 commit 之后 `backend/` 下**零残留**（`git status -- backend` 无输出），"
       "未跟踪文件只有 `.superpowers/` 下的本报告与 `t2_probes/` 九个脚本 |")

for path in (REPORT, P09):
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    assert text.count(OLD) == 1, (path.name, text.count(OLD))
    out = text.replace(OLD, NEW, 1).replace("\r\n", "\n").encode("utf-8")
    path.write_bytes(out)
    print(f"{path.name:24s} {len(raw)} -> {len(out)} B  sha256[:16] "
          f"{hashlib.sha256(out).hexdigest()[:16].upper()}")

final = REPORT.read_bytes()
print("report:", len(final), "B /", final.count(b"\n"), "lines / BOM",
      final[:3] == bytes([0xEF, 0xBB, 0xBF]), "/ CRLF", final.count(bytes([13, 10])))

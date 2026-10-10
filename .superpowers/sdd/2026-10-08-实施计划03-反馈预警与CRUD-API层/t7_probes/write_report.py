"""把报告正文落到 task-7-report.md（python 写，UTF-8 无 BOM），并复核字节数与行数。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "report_body.md"
DST = HERE.parent / "task-7-report.md"

text = SRC.read_text(encoding="utf-8")
DST.write_bytes(text.encode("utf-8"))  # 显式无 BOM

raw = DST.read_bytes()
CRLF = b"\r\n"
print("路径:", DST)
print("字节数:", len(raw))
print("行数:", raw.decode("utf-8").count("\n") + (0 if raw.endswith(b"\n") else 1))
print("BOM:", raw[:3] == b"\xef\xbb\xbf")
print("CRLF 数:", raw.count(CRLF))
print("首行:", raw.decode("utf-8").splitlines()[0])
print("末行:", raw.decode("utf-8").splitlines()[-1])
# 与源文件逐字节对账（硬规矩 #99：落盘唯一权威是 shell/python，写完要复核）
print("与源逐字节相同:", raw == text.encode("utf-8"))

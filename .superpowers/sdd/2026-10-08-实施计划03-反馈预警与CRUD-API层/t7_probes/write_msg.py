"""写 commit 信息（UTF-8 无 BOM）并打印路径，供 git commit -F 使用。"""
import pathlib
import sys

OUT = pathlib.Path(sys.argv[1])
TEXT = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
OUT.write_bytes(TEXT.encode("utf-8"))  # 显式无 BOM
print(OUT, len(OUT.read_bytes()), "bytes; BOM:", OUT.read_bytes()[:3] == b"\xef\xbb\xbf")

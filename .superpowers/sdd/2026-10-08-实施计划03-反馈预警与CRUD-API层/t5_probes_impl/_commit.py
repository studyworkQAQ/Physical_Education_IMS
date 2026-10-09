"""commit 助手：把消息写成 UTF-8 **无 BOM** 临时文件，git add 指定文件，git commit -F。

用法：python t5_probes/_commit.py <msg_file> <path> [<path> ...]
msg_file 由 Write 工具落盘，本脚本负责剥掉可能存在的 BOM 并复核编码。
"""
import pathlib
import subprocess
import sys
import tempfile

msg_path = pathlib.Path(sys.argv[1])
targets = sys.argv[2:]

raw = msg_path.read_bytes()
if raw.startswith(b"\xef\xbb\xbf"):
    raw = raw[3:]
    print("BOM stripped")
text = raw.decode("utf-8")  # 解码失败即响亮报错
# 规范化行尾：commit 消息里混进 \r 会在 git log 里显示成 ^M
text = text.replace("\r\n", "\n").replace("\r", "\n")
out = pathlib.Path(tempfile.gettempdir()) / "t5_commit_msg.txt"
out.write_bytes(text.encode("utf-8"))
print("msg_bytes:", len(out.read_bytes()), "starts_with_BOM:",
      out.read_bytes().startswith(b"\xef\xbb\xbf"))
print("first_line:", text.splitlines()[0])

for t in targets:
    r = subprocess.run(["git", "add", "--", t], capture_output=True, text=True)
    print("add", t, "->", r.returncode, r.stderr.strip())
    if r.returncode != 0:
        sys.exit(1)

r = subprocess.run(["git", "commit", "-F", str(out)], capture_output=True, text=True,
                   encoding="utf-8")
print("commit rc:", r.returncode)
print(r.stdout.strip())
print(r.stderr.strip())
sys.exit(r.returncode)

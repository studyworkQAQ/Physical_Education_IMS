"""Task 9 通用提交器：``python commit.py <消息文件> <file1> <file2> …``。

消息文件由 Write 工具写在同目录下（``msg_*.txt``）。⚠️ 本脚本**剥掉可能存在的 BOM**
再以 ``git commit -F`` 提交（纪律：commit 信息 UTF-8 **无** BOM），并复核落盘字节。
⚠️ ``git add`` 按文件名逐个加，**不用** ``git add -A``。
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
HERE = pathlib.Path(__file__).resolve().parent


def _run(args: list[str]) -> int:
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    print(proc.stdout.strip())
    if proc.stderr.strip():
        print("[stderr]", proc.stderr.strip())
    return proc.returncode


def main() -> int:
    msg_file = HERE / sys.argv[1]
    files = sys.argv[2:]
    raw = msg_file.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
        msg_file.write_bytes(raw)
        print("剥掉了 BOM")
    assert not raw.startswith(b"\xef\xbb\xbf")
    lines = raw.count(b"\n") + 1
    print(f"消息 {len(raw)} B / {lines} 行")
    rc = _run(["git", "add", "--"] + files)
    if rc:
        return rc
    rc = _run(["git", "commit", "-F", str(msg_file)])
    if rc:
        return rc
    _run(["git", "log", "--oneline", "-1"])
    _run(["git", "status", "--porcelain"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

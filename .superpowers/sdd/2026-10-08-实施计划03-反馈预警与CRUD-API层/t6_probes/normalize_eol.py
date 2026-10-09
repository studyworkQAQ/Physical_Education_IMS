"""把本 Task 新建的 4 个 .py 的工作树行尾从 LF 归一到 CRLF，与仓库其余 .py 一致。

⚠️ **``backend/data/alert_rules.yaml`` 不在名单里**：它被 ``.gitattributes`` 的
``backend/data/*.yaml text eol=lf`` 钉成 LF，且被 sha256[:16] 指纹按字节钉住
（``E48E3AC82BB45BB7``），写成 CRLF 会让指纹与 ``git ls-files --eol`` 双双对不上。

⚠️ **``app/refdata_prescription.py`` 也不在名单里**：它是既有文件、本来就是 CRLF
（``t6_probes/extract_yaml_helpers.py`` 写回时已按 CRLF 还原）。

**为什么可以安全地改工作树而不改 blob**：``core.autocrlf=true`` 下 git 在 ``add`` 时把
CRLF 归一成 LF 存进 index，故 blob 逐字不变、``git status`` 仍然干净（既有那几十个 CRLF
的 .py 就是证据）。改的只是「下一次 checkout 之前工作树长什么样」——不改的话这 4 个文件
会在某次 checkout 时被 git 自己重写成 CRLF，那是一次没有必要的 churn。

**取证**：改前改后各数一遍 ``read_bytes()`` 的 CRLF / LF（硬规矩 #89 的扩写），
并算一遍 ``git hash-object``，证明 blob 逐字不变。
"""
import hashlib
import pathlib
import subprocess

REPO = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
TARGETS = [
    "backend/app/refdata_yaml.py",
    "backend/app/refdata_alerts.py",
    "backend/app/domain/alerts.py",
    "backend/tests/domain/test_alerts.py",
    "backend/tests/test_refdata_alerts.py",
]


def blob(relative: str) -> str:
    done = subprocess.run(["git", "hash-object", relative], cwd=REPO,
                          capture_output=True, text=True)
    return done.stdout.strip()


def stats(path: pathlib.Path) -> tuple[int, int, int, str]:
    raw = path.read_bytes()
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n")
    return len(raw), crlf, lf - crlf, hashlib.sha256(raw).hexdigest()[:16].upper()


for relative in TARGETS:
    path = REPO / relative
    before = stats(path)
    before_blob = blob(relative)
    raw = path.read_bytes()
    if raw.count(b"\r\n"):
        print(f"[skip] {relative} 已经有 CRLF，不动")
        continue
    path.write_bytes(raw.replace(b"\n", b"\r\n"))
    after = stats(path)
    after_blob = blob(relative)
    print(f"{relative}")
    print(f"   改前 bytes={before[0]} CRLF={before[1]} bare_LF={before[2]} "
          f"sha={before[3]} blob={before_blob[:12]}")
    print(f"   改后 bytes={after[0]} CRLF={after[1]} bare_LF={after[2]} "
          f"sha={after[3]} blob={after_blob[:12]}")
    print(f"   blob 逐字不变? {before_blob == after_blob}")

print()
for relative in ["backend/data/alert_rules.yaml", "backend/app/refdata_prescription.py"]:
    path = REPO / relative
    size, crlf, bare, sha = stats(path)
    print(f"[对照] {relative} bytes={size} CRLF={crlf} bare_LF={bare} sha={sha}")

done = subprocess.run(["git", "status", "--short"], cwd=REPO,
                      capture_output=True, text=True, encoding="utf-8")
print("\n[git status --short]\n" + done.stdout)

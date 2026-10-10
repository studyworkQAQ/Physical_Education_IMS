"""Task 9 探针 10：端到端冒烟测试的**变异自证**（3 条，各打一个「层间接缝」）。

本文件的 :func:`test_the_whole_loop_runs_over_real_http` 声称自己是「这个原型系统真的能
跑起来」的唯一可执行判据。一句声称不值钱，故逐条把某个接缝打断、看它是否真的红：

=====  ================================================  ==========================
M      变异（打在**生产代码**上，不是打在测试上）           它断的是哪个接缝
=====  ================================================  ==========================
M1     ``api_router.include_router(pipeline_router)``    api → pipeline
       那一行删掉
M2     ``alert_stage.AUTO_REDUCTION_FACTOR`` 0.8 → 0.85  pipeline(alert) → api(处方侧读)
M3     ``alerts.py`` 推送的标题「减 20%」→「减 25%」      api(alerts) → notify → 学生端
=====  ================================================  ==========================

⚠️ 三条都**只改一个字节级锚点**、跑完立刻从字节备份还原（``try/finally`` + sha256 复核），
不用 ``git checkout``（硬规矩 #46：它按 core.autocrlf 重写工作树）。
⚠️ 目标测试文件是 ``tests/api/test_end_to_end.py``，而 M2 与 M3 还会让
``tests/api/test_alerts_api.py`` / ``tests/pipeline/test_alert_stage.py`` 一起红——
那**正是想要的**：本文件不是唯一的守卫，它是「接缝」那一个维度的守卫。
"""
import hashlib
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
TARGET = "tests/api/test_end_to_end.py"

MUTATIONS = [
    (
        "M1 api_router.include_router(pipeline_router) 那一行删掉",
        "app/api/routers/__init__.py",
        "api_router.include_router(pipeline_router)\n",
        "",
    ),
    (
        "M2 AUTO_REDUCTION_FACTOR 0.8 -> 0.85",
        "app/pipeline/alert_stage.py",
        "AUTO_REDUCTION_FACTOR = 0.8\n",
        "AUTO_REDUCTION_FACTOR = 0.85\n",
    ),
    (
        "M3 推送标题「本周训练量已减 20%」->「本周训练量已减 25%」",
        "app/api/routers/alerts.py",
        'title="本周训练量已减 20%",',
        'title="本周训练量已减 25%",',
    ),
]

TMP = pathlib.Path(tempfile.gettempdir())
backups: dict[pathlib.Path, pathlib.Path] = {}
#: ⚠️ Python 3.11 的 f-string 表达式里**不能有反斜杠**，故两个行尾字节串提成常量。
CRLF_BYTES = b"\r\n"
LF_BYTES = b"\n"
shas_before: dict[str, str] = {}
for _name, _rel, _old, _new in MUTATIONS:
    _b = (BACKEND / _rel).read_bytes()
    shas_before[_rel] = hashlib.sha256(_b).hexdigest()[:16].upper()


def _run(target: str = TARGET) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", target, "-q", "--no-header", "--tb=line"],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    lines = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    return proc.returncode, "\n".join(lines[-8:])


results = []
try:
    rc, tail = _run()
    print(f"[基线] rc={rc}\n{tail}")
    assert rc == 0, "基线就红了，变异结论不可解释"

    for name, rel, old, new in MUTATIONS:
        path = BACKEND / rel
        raw = path.read_bytes()
        backup = TMP / f"t9_mut_{path.name}"
        shutil.copyfile(path, backup)
        backups[path] = backup
        needle = old.replace("\n", "\r\n").encode("utf-8")
        if raw.count(needle) != 1:
            needle = old.encode("utf-8")
        assert raw.count(needle) == 1, f"{name}: 锚点命中 {raw.count(needle)} 次"
        replacement = new.replace("\n", "\r\n").encode("utf-8") if b"\r\n" in needle else new.encode("utf-8")
        path.write_bytes(raw.replace(needle, replacement))
        rc, tail = _run()
        results.append((name, rc != 0, rc))
        print(f"\n[{name}] rc={rc} -> {'KILLED' if rc else 'SURVIVED ⚠️'}\n{tail}")
        path.write_bytes(raw)
finally:
    for path, backup in backups.items():
        path.write_bytes(backup.read_bytes())
        backup.unlink(missing_ok=True)
    print("\n还原复核：")
    for _name, rel, _o, _n in MUTATIONS:
        p = BACKEND / rel
        b = p.read_bytes()
        n_crlf = b.count(CRLF_BYTES)
        n_bare = b.count(LF_BYTES) - n_crlf
        sha = hashlib.sha256(b).hexdigest()[:16].upper()
        same = sha == shas_before[rel]
        print(f"  {rel}: {len(b)} B sha256[:16]={sha}（改前 {shas_before[rel]}，"
              f"逐字相同={same}）CRLF={n_crlf} bare LF={n_bare}")
        assert same, f"{rel} 没有还原成原字节"

print("\n== 汇总 ==")
for name, killed, rc in results:
    print(f"  {'KILLED  ' if killed else 'SURVIVED'} rc={rc}  {name}")
survivors = [n for n, k, _ in results if not k]
print("存活的变异：", survivors if survivors else f"0 条（{len(results)}/{len(results)} killed）")
sys.exit(1 if survivors else 0)

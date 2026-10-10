"""Task 9 探针 11：progress_board 填充口径 + 标准化得分单一所有者的**变异自证**（4 条）。

=====  ==============================================================  ==========================
M      变异                                                            它证明的是
=====  ==============================================================  ==========================
M4     ``shuttle_percentile`` 的 ``0.5 * tied`` → ``0.0 * tied``       「并列取中点」有人看着
M5     ``mini_test_scores`` 的 composite 改成先 round 百分位再平均     「中间步骤不 round」有人看着
M6     ``_composite_of`` 改回读 ``row.normalized_score`` 那一列        「生成时算」这个裁定有人看着
M7     往 ``report_stage.py`` 里塞第二份 ``shuttle_percentile`` 定义    AST 守卫数定义份数 == 1
=====  ==============================================================  ==========================

⚠️ M6 是四条里最要紧的一条：它正是**本次裁定要修的那个缺陷**（读列 → 生产路径上恒 NULL
→ 进步榜全员 unmeasured）。改回去之后 ``tests/pipeline/test_report_stage.py`` 的两条
进步榜测试必须红——若它们不红，说明那两条测试是哑弹（``_mini`` 助手仍在给
``normalized_score`` 喂值）。
⚠️ 一律字节级打补丁、跑完从字节备份还原（``try/finally`` + sha256 复核），不用 ``git checkout``。
"""
import hashlib
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
TMP = pathlib.Path(tempfile.gettempdir())
CRLF_BYTES = b"\r\n"
LF_BYTES = b"\n"

MUTATIONS = [
    (
        "M4 shuttle_percentile: 0.5 * tied -> 0.0 * tied",
        "app/domain/report.py",
        "    return (slower + 0.5 * tied) / len(sample) * 100.0\n",
        "    return (slower + 0.0 * tied) / len(sample) * 100.0\n",
        "tests/domain/test_report.py",
    ),
    (
        "M5 mini_test_scores: composite 先把百分位 round 过再平均",
        "app/domain/report.py",
        "            else round((squat + raw) / 2, SCORE_PRECISION)\n",
        "            else round((squat + round(raw, SCORE_PRECISION)) / 2, SCORE_PRECISION)\n",
        "tests/domain/test_report.py",
    ),
    (
        "M6 _composite_of 改回读 normalized_score 那一列",
        "app/pipeline/report_stage.py",
        '    return mini_test_scores(row.squat_30s_count, row.shuttle_20m_s, sample)["composite"]\n',
        "    return row.normalized_score\n",
        "tests/pipeline/test_report_stage.py",
    ),
    (
        "M7 往 report_stage.py 塞第二份 shuttle_percentile 定义",
        "app/pipeline/report_stage.py",
        "_ONE_DAY = dt.timedelta(days=1)\n",
        "_ONE_DAY = dt.timedelta(days=1)\n\n\ndef shuttle_percentile(seconds, sample):\n"
        "    return (sum(1 for v in sample if v > seconds)) / len(sample) * 100.0\n",
        "tests/domain/test_report.py",
    ),
]

shas_before = {}
for _n, rel, _o, _nw, _t in MUTATIONS:
    shas_before[rel] = hashlib.sha256((BACKEND / rel).read_bytes()).hexdigest()[:16].upper()
print("改前 sha256[:16]:", shas_before)


def _run(target: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", target, "-q", "--no-header", "--tb=line"],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    lines = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    return proc.returncode, "\n".join(lines[-8:])


backups: dict[pathlib.Path, pathlib.Path] = {}
results = []
try:
    for _n, rel, _o, _nw, target in MUTATIONS:
        rc, tail = _run(target)
        assert rc == 0, f"{target} 的基线就红了：\n{tail}"
    print("四条的目标测试基线全绿")

    for name, rel, old, new, target in MUTATIONS:
        path = BACKEND / rel
        raw = path.read_bytes()
        backup = TMP / f"t9_mut3_{path.name}"
        shutil.copyfile(path, backup)
        backups[path] = backup
        needle = old.replace("\n", "\r\n").encode("utf-8")
        replacement = new.replace("\n", "\r\n").encode("utf-8")
        if raw.count(needle) != 1:
            needle = old.encode("utf-8")
            replacement = new.encode("utf-8")
        hits = raw.count(needle)
        assert hits == 1, f"{name}: 锚点命中 {hits} 次"
        path.write_bytes(raw.replace(needle, replacement))
        rc, tail = _run(target)
        results.append((name, rc != 0, rc))
        print(f"\n[{name}] target={target} rc={rc} -> "
              f"{'KILLED' if rc else 'SURVIVED ⚠️'}\n{tail}")
        path.write_bytes(raw)
finally:
    for path, backup in backups.items():
        path.write_bytes(backup.read_bytes())
        backup.unlink(missing_ok=True)
    print("\n还原复核：")
    ok = True
    for rel, sha in shas_before.items():
        b = (BACKEND / rel).read_bytes()
        got = hashlib.sha256(b).hexdigest()[:16].upper()
        n_crlf = b.count(CRLF_BYTES)
        same = got == sha
        ok = ok and same
        print(f"  {rel}: {len(b)} B sha256[:16]={got}（改前 {sha}，逐字相同={same}）"
              f" CRLF={n_crlf} bare LF={b.count(LF_BYTES) - n_crlf}")
    assert ok, "有文件没有还原成原字节"

print("\n== 汇总 ==")
for name, killed, rc in results:
    print(f"  {'KILLED  ' if killed else 'SURVIVED'} rc={rc}  {name}")
survivors = [n for n, k, _ in results if not k]
print("存活的变异：", survivors if survivors else f"0 条（{len(results)}/{len(results)} killed）")
sys.exit(1 if survivors else 0)

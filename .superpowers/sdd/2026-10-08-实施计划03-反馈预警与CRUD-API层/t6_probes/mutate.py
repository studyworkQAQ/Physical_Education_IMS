"""Plan 03 Task 6 的**变异测试**取证脚本（账本 Ruling 1 的唯一例外：本 Task 要求变异）。

5 条规则的比较符各做一次（``>=`` ↔ ``>``、``<`` ↔ ``<=``），断言对应的边界测试变红。

**为什么必须变异**：预警阈值是本系统里唯一会直接改变「给哪个学生推减量 20%」的量，
而这类错误在端到端测试里看不出来——少触发一条预警，500 人的分布测试只动几个百分点。

**流程（每次变异都走全）**：
1. 备份 ``app/domain/alerts.py`` 的原字节到 TEMP；
2. 断言待改的那一段在源码里**恰好命中 1 次**（命中数不对就停手，不写盘）；
3. 写入变异后的字节；
4. **删掉 ``backend/app`` 与 ``backend/tests`` 下全部 ``__pycache__``**（硬规矩 #83：
   不删的话 CPython 可能按 mtime+size 判定缓存仍有效，跑的是**旧**字节，于是变异看起来
   「没让任何测试红」——那是一次假绿，而且是最坏的一种）；
5. 跑两个测试文件，收集 FAILED 名单；
6. **用 python 从 TEMP 备份 ``write_bytes`` 写回原字节**（⚠️ 不用 ``git checkout``：
   ``core.autocrlf=true`` 会按 ``.gitattributes`` 重写工作树，硬规矩 #46/#70）；
7. 再删一次 ``__pycache__``；
8. 三重还原取证：① sha256 与原字节逐字相同；② ``git diff`` 对该文件为空；
   ③ 复跑两个测试文件全绿。

⚠️ **每条变异的结构可达性**（硬规矩 #92）在下面的 ``reachable`` 字段里论证：变异必须
真的被一个**坐在边界上**的输入走到，否则「没红」既可能是尺子坏了、也可能是变异不可达，
两者不可区分（硬规矩 #53）。
"""
import hashlib
import pathlib
import shutil
import subprocess
import sys
import tempfile

BACKEND = pathlib.Path(
    r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend"
)
REPO = BACKEND.parent
TARGET = BACKEND / "app" / "domain" / "alerts.py"
TESTS = ["tests/domain/test_alerts.py", "tests/test_refdata_alerts.py"]
BACKUP = pathlib.Path(tempfile.gettempdir()) / "t6_mutation_backup_alerts.py"

MUTATIONS = [
    dict(
        tag="M1",
        rule="RED_MINITEST_DROP",
        before="        if newer >= older * factor:",
        after="        if newer > older * factor:",
        reachable=(
            "判据是 spec §8.2 口径表 #2 的 score(t) < score(t-1) × 0.95，源码写成它的"
            "否定式（提前返回），故 >= → > 就是把 spec 的 < 改成 <=。可达输入："
            "(88.0, 80.0, 76.0) —— 80.0 × 0.95 == 76.0，恰好坐在边界上，"
            ">= 判「没下降」（不触发）、> 判「下降了」（触发）。"
        ),
        expect="test_minitest_drop_is_strict_at_exactly_five_percent",
    ),
    dict(
        tag="M2",
        rule="RED_RPE_SUSTAINED",
        before="    if sig.rpe_streak >= needed:",
        after="    if sig.rpe_streak > needed:",
        reachable=(
            "判据是 rpe_streak >= streak（spec 逐字「≥ 9」+ 口径表 #1「连续 3 次」）。"
            "可达输入：rpe_streak == 3、streak == 3，恰好坐在边界上，"
            ">= 触发、> 不触发。"
        ),
        expect="test_rpe_sustained_fires_at_exactly_the_streak_threshold",
    ),
    dict(
        tag="M3",
        rule="YELLOW_CHECKIN_GAP",
        before='    if sig.checkin_gap_days >= int(rule.params["gap_days"]):',
        after='    if sig.checkin_gap_days > int(rule.params["gap_days"]):',
        reachable=(
            "判据是 checkin_gap_days >= gap_days（spec「打卡中断 2 天」+ 口径表 #3"
            "「连续 2 个应打卡训练日」）。可达输入：checkin_gap_days == 2、gap_days == 2，"
            "恰好坐在边界上，>= 触发、> 不触发。"
        ),
        expect="test_checkin_gap_fires_at_exactly_the_gap_threshold",
    ),
    dict(
        tag="M4",
        rule="YELLOW_CLASS_RPE_HIGH",
        before='    if sig.mean_rpe > float(rule.params["mean_rpe_max"]):',
        after='    if sig.mean_rpe >= float(rule.params["mean_rpe_max"]):',
        reachable=(
            "判据是 mean_rpe > mean_rpe_max（spec 逐字「课堂 RPE 均值 > 7 分」）。"
            "可达输入：mean_rpe == 7.0、mean_rpe_max == 7.0，恰好坐在边界上，"
            "> 不触发、>= 触发。"
        ),
        expect="test_class_rpe_high_is_strict_at_exactly_seven",
    ),
    dict(
        tag="M5",
        rule="GREEN_MASTERY",
        before='        sig.completion_rate >= float(rule.params["completion_rate_min"])',
        after='        sig.completion_rate > float(rule.params["completion_rate_min"])',
        reachable=(
            "判据是 completion_rate >= completion_rate_min（spec「本周完成度 100%」，"
            "参数名逐字是 _min；用 >= 而不是 == 的三条理由见 _mastery 的 docstring）。"
            "可达输入：completion_rate == 1.0、completion_rate_min == 1.0，"
            "恰好坐在边界上，>= 触发、> 不触发。"
        ),
        expect="test_mastery_fires_at_exactly_full_completion",
    ),
]


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def drop_pycache() -> int:
    """删掉 backend/app 与 backend/tests 下全部 __pycache__（硬规矩 #83），返回删了几个。"""
    removed = 0
    for root in ("app", "tests"):
        for folder in sorted((BACKEND / root).rglob("__pycache__")):
            shutil.rmtree(folder, ignore_errors=True)
            removed += 1
    return removed


def run_tests() -> tuple[int, list[str], str]:
    """跑两个测试文件，返回 (退出码, FAILED 的测试名列表, 末行摘要)。"""
    done = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "--tb=no", "-p", "no:cacheprovider"],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    failed = [
        line.split(" ")[1] for line in done.stdout.splitlines()
        if line.startswith("FAILED ") and len(line.split(" ")) > 1
    ]
    tail = [line for line in done.stdout.splitlines() if line.strip()][-1:]
    return done.returncode, failed, (tail[0] if tail else "")


def git_diff_for(path: pathlib.Path) -> str:
    done = subprocess.run(
        ["git", "diff", "--", str(path.relative_to(REPO))],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return done.stdout


# ---------------------------------------------------------------------------
original = TARGET.read_bytes()
original_sha = hashlib.sha256(original).hexdigest()
BACKUP.write_bytes(original)
print(f"[基线] {TARGET.name} bytes={len(original)} sha256={original_sha[:16].upper()}")
print(f"[基线] 备份 -> {BACKUP}")

code0, failed0, tail0 = run_tests()
print(f"[基线] 未变异时跑两个测试文件：exit={code0} FAILED={len(failed0)} | {tail0}")
if code0 != 0:
    sys.exit("基线就不绿，停手")

results = []
for mutation in MUTATIONS:
    text = original.decode("utf-8")
    hits = text.count(mutation["before"])
    print("\n" + "=" * 78)
    print(f"[{mutation['tag']}] {mutation['rule']}")
    if hits != 1:
        sys.exit(f"  待改的那一段命中 {hits} 次，应恰好 1 次，停手（不写盘）")
    print(f"  变异：{mutation['before'].strip()!r}")
    print(f"     -> {mutation['after'].strip()!r}")
    print(f"  结构可达性：{mutation['reachable']}")

    mutated = text.replace(mutation["before"], mutation["after"], 1)
    TARGET.write_bytes(mutated.encode("utf-8"))
    mutated_sha = sha256(TARGET)
    caches = drop_pycache()
    print(f"  写入变异字节 sha256={mutated_sha[:16].upper()}；删掉 {caches} 个 __pycache__")

    code, failed, tail = run_tests()
    print(f"  跑测试：exit={code} FAILED={len(failed)} | {tail}")
    for name in failed:
        mark = "  <== 边界靶" if name.endswith(mutation["expect"]) else ""
        print(f"      红：{name}{mark}")
    hit_expect = any(name.endswith(mutation["expect"]) for name in failed)
    print(f"  期望的边界测试变红？ {'是' if hit_expect else '*** 否 ***'}"
          f"（{mutation['expect']}）")
    if code == 0 or not hit_expect:
        sys.exit(f"[{mutation['tag']}] 变异没有被边界测试抓住，停手")

    # ---- 三重还原取证 -----------------------------------------------------
    TARGET.write_bytes(BACKUP.read_bytes())
    caches = drop_pycache()
    restored_sha = sha256(TARGET)
    diff = git_diff_for(TARGET)
    code2, failed2, tail2 = run_tests()
    print(f"  还原取证① sha256={restored_sha[:16].upper()} "
          f"{'== 原字节 OK' if restored_sha == original_sha else '*** 不同 ***'}；"
          f"又删了 {caches} 个 __pycache__")
    print(f"  还原取证② git diff 该文件的输出长度 = {len(diff)} "
          f"{'（空，OK）' if diff == '' else '*** 非空 ***'}")
    print(f"  还原取证③ 复跑：exit={code2} FAILED={len(failed2)} | {tail2}")
    if restored_sha != original_sha or diff != "" or code2 != 0:
        sys.exit(f"[{mutation['tag']}] 三重还原取证有一项不通过，停手")
    results.append((mutation["tag"], mutation["rule"], len(failed),
                    mutation["expect"], failed))

# ---------------------------------------------------------------------------
final_sha = sha256(TARGET)
final_bytes = TARGET.read_bytes()
print("\n" + "=" * 78)
print(f"[收尾] {TARGET.name} bytes={len(final_bytes)} sha256={final_sha[:16].upper()} "
      f"{'== 原字节 OK' if final_sha == original_sha else '*** 不同 ***'}")
print(f"[收尾] 字节逐字相同? {final_bytes == original}")
print("\n[汇总] 5 条变异 × 各自红了几条 × 边界靶是否命中")
for tag, rule, count, expect, failed in results:
    print(f"  {tag} {rule:24s} 红 {count} 条；边界靶 {expect} 命中")
    for name in failed:
        print(f"        - {name}")

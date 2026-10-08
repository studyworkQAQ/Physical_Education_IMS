# -*- coding: utf-8 -*-
"""commit 2（F1-3 + F1-4 + F1-5）：计划正文 + 账本追加 + 补丁脚本与取证脚本入库。

`git add` **按文件名逐个加**（不 `-A`）；提交信息用 UTF-8 无 BOM 临时文件 + `git commit -F`。
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
HERE = pathlib.Path(__file__).resolve().parent          # t5_probes/
SDD = HERE.parent                                        # 2026-10-06-实施计划02-…/
MSG = HERE / "_fr1_msg2.txt"

BODY = """docs: Plan02 Task5 fix round 1 的 F1-3/F1-4/F1-5 —— 撤回 P5-A10（控制者错误 #140）+ 硬规矩 #82/#83 入账 + 计划正文 11 处更正

F1-3（Important）：**撤回 P5-A10**。控制者的探针只 grep 了标识符 `BODY_FAT_LIMIT`、
没 grep 注释行，于是把「探针没显示」讲成了「它不存在」。实测 `app/domain/derive.py` 的
定义行**上一行**就是逐字的注释「男 > 20%、女 > 28%，**严格大于**」，故**原计划的行号
`:68-69` 与引文双双正确**。→ **控制者错误 #140**，与同一个 commit（`c8e26b8`）里刚立下的
硬规矩 #80 同型第 **9** 次。

→ **补硬规矩 #82：探针「0 命中」时，必须先用一个已知存在的串验证这条查询本身有效，
才允许把「没查到」讲成「不存在」。** 依据：Ruling 147 的 P5-A13（用一个自己没验证过的
正则去数一个已经有字面断言的量）与本次的 P5-A10 是同一根因的两次发作，而 #80 只覆盖了
「已有字面断言」那一半——「探针 0 命中」这一半它管不到。

F1-4（Important）：**补硬规矩 #83 —— 变异取证与任何「改了又还原」的取证，必须在跑测试前
`shutil.rmtree(__pycache__, ignore_errors=True)` 并设 `PYTHONDONTWRITEBYTECODE=1`；
等长改动 + 同一秒会让 CPython 的 `(mtime 截断到秒, size)` 失效判据不触发，于是加载陈旧
字节码、产出假红或假绿。** 依据是 5.5 变异 ④ 的实测：还原后 sha256 逐字节相同而 pytest
仍报变异行为；本轮用 `t5_probes/_fr1_probe_47chars.py` 独立复核了那两个条件——
`    return int(low_bpm), int(-(-high_bpm // 1))` 与取整方向反过来的改写
`    return int(-(-low_bpm // 1)), int(high_bpm)` **都是 47 字符**（亲跑 len()，差 0）。
它比一般的 flaky 危险在两点：假红会让人怀疑一个**正确的**还原；**假绿**会让人以为
一条守卫还在工作，而变异取证的全部价值就是「M1 必须红」。

F1-5（Minor）：4 条待清扫一次清完 —— ① P5-A2 的 `{2:24, 3:42, 4:64}` 补明是**按 block
计数加权**（去重后是 `{2:12, 3:14, 4:16}` 共 42 个 ref）；② 5.5 补上派单原先漏点的两处
（`_OWNED_MODULES` 3→7、那句 `assert len(...) == 24` 其实是**两句**），标注「实现者超出
派单发现，控制者采纳」；③ 5.3 的 `Consumes` 补列 `Template` / `ExerciseSpec`；
④ 5.5 补上「带 `--cov` 与不带的 passed 数差 1」的口径（那 1 个 skip 是
`tests/pipeline/test_backfill.py` 里既有的墙钟断言，按硬规矩 #42 在 `sys.gettrace()`
非空时主动跳，而 `pytest-cov` 正是靠 `sys.settrace()` 实现的）。

计划正文一共 **11 处**替换（`_t5_fr1_plan_patch.py` 的 E1–E10b），**每处都先 assert 命中
次数**、两遍走（第一遍只 assert、第二遍才替换），另加四道落盘闸门；除 F1-3/F1-5 外还含
F1-1 与 F1-2 的正文对齐（E7/E8/E9）与两处签名扩参的 `Produces` 行（E10a/E10b）——
后三条不在派单的字面清单里，理由逐条写在实现者报告的「我没按本派单做的地方」。
计划 **151 467 B / 938 行 → 159 408 B / 939 行**（纯 CRLF 未变、无 BOM、
`git diff --stat` = 12 insertions / 11 deletions）。

账本 `progress.md` **末尾追加一节**（只用 python `open(..., "a", newline="")`、自己写
`\\r\\n`；**绝不用编辑器工具打开它**——Ruling 116 那次事故里 IDE 把陈旧且截断的缓存写回
磁盘、永久丢了约 107 KB）：**336 427 B / 2 153 行 → 346 910 B / 2 214 行**（纯 CRLF、
无 BOM）。落盘闸门是 `after_text == before_text + payload` **逐字相同**，即前 336 KB
一个字都没被碰过。同一节还记了控制者对两处签名扩参的采纳裁定
（`apply_safety(pkg, inp, eq, *, template, exercises)` 与
`apply_overrides(pkg, records, *, exercises)`，Plan 02 实现者第 **5**、**6** 次顶回成立）。

本轮取证脚本 14 份 + 2 份 commit 信息 + 1 份扫描输出一并入库（口径照账本对
`t5_probe{1,2,3,4}.py` 记的「四份全部入库」，以及 `fr2_probes/` / `fr3_probes/` /
`fr4_probes/` / `t3_probes/` / `t4_probes/` 的既有惯例）。
⚠️ `task-5-report.md` / `task-5-brief.md` / `_mk_brief5.py` / `_t5_verify.py` **仍未入库**
（上一轮也没入库），已在报告里报出请控制者裁定。

代码与测试一个字没动（本轮只改 `Document/` 与 `.superpowers/`）。
"""


def git(*args, check=True) -> str:
    # ⚠️ `core.quotepath=false`：中文路径默认会被 git 转义成 `"\345\256\236…"` 的八进制串，
    #    于是「暂存了什么」与「我想加什么」的集合比对会**全部**对不上（本轮亲跑撞到过）。
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    if check:
        assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout


def rel(p: pathlib.Path) -> str:
    return p.relative_to(ROOT).as_posix()


def main() -> int:
    MSG.write_text(BODY, encoding="utf-8", newline="\n")
    print(f"提交信息 {len(MSG.read_bytes())} B -> {MSG.name}")

    files = [
        rel(ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"),
        rel(SDD / "progress.md"),
        rel(SDD / "_t5_fr1_plan_patch.py"),
    ]
    files += sorted(rel(p) for p in HERE.iterdir() if p.name.startswith("_fr1"))
    files += sorted(rel(p) for p in HERE.iterdir()
                    if p.name.startswith("_plan_") or p.name.startswith("_chk"))
    files = list(dict.fromkeys(files))
    print(f"待加 {len(files)} 个文件：")
    for f in files:
        print(f"  {f}")

    for f in files:
        r = subprocess.run(["git", "add", "--", f], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, (f, r.stderr)
    staged = git("diff", "--cached", "--name-only").split()
    print(f"\n实际暂存 {len(staged)} 个")
    missing = sorted(set(files) - set(staged))
    extra = sorted(set(staged) - set(files))
    assert not missing, f"没加上：{missing}"
    assert not extra, f"多出了：{extra}"
    # 禁区自查：暂存区里不许有 backend/ 的任何东西
    assert not [s for s in staged if s.startswith("backend/")], "暂存区里出现了 backend/"

    r = subprocess.run(["git", "commit", "-F", str(MSG)], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    print(r.stdout)
    print(r.stderr)
    assert r.returncode == 0
    print("commit 2 sha =", git("rev-parse", "--short", "HEAD").strip())
    print(git("log", "--oneline", "-3"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

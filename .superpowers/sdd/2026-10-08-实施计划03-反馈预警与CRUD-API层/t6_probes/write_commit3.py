"""写 commit 3 的信息（UTF-8 无 BOM）到 TEMP，供 git commit -F 用。"""
import os
import pathlib

MESSAGE = """test(alerts): Task 6 变异取证（5 条比较符 × 三重还原）+ 实现者报告

账本 Ruling 1 把本 Task 定为全计划**唯一**要求变异测试的地方：预警阈值是本系统里唯一会
直接改变「给哪个学生推减量 20%」的量，而这类错误在端到端测试里看不出来——少触发一条
预警，500 人的分布测试只动几个百分点。

5 条变异（脚本 t6_probes/mutate.py），**每条都被对应的边界测试抓住**：

  M1 RED_MINITEST_DROP    >= → >   （= spec 的 < 改成 <=）  红 3 条，靶 test_minitest_drop_is_strict_at_exactly_five_percent
  M2 RED_RPE_SUSTAINED    >= → >                            红 9 条，靶 test_rpe_sustained_fires_at_exactly_the_streak_threshold
  M3 YELLOW_CHECKIN_GAP   >= → >                            红 6 条，靶 test_checkin_gap_fires_at_exactly_the_gap_threshold
  M4 YELLOW_CLASS_RPE_HIGH > → >=                            红 2 条，靶 test_class_rpe_high_is_strict_at_exactly_seven
  M5 GREEN_MASTERY        >= → >                            红 5 条，靶 test_mastery_fires_at_exactly_full_completion

每条先论证**结构可达**（硬规矩 #92）：都有一个恰好坐在边界上的输入
（80.0 × 0.95 == 76.0 / streak == 3 / gap == 2 / mean_rpe == 7.0 / completion_rate == 1.0）。
⚠️ M4 最干净（只红 2 条），M1 只让「坐在恰好 5%」的断言红、而 5.1% 与「更早的下降不算」
两条保持绿——这就是「尺子真的在量那个闭区间端点、而不是在量『有没有下降』」的自证
（Task 5 的 M1 用的是同一种论证形状）。

⚠️ M5 的存在本身是一条顶回的证据：若照计划正文写 completion_rate == 1.0，则「== → >=」
在值域 [0, 1] 上**不可分辨**，本 Task 唯一要求的变异对第 5 条规则**没有靶子**。

按硬规矩 #83 的 .pyc 纪律做：每次改完删 backend/app 与 backend/tests 下全部 __pycache__，
跑完**三重还原取证**——① sha256 复原（BF36B469F0FC19C9，5 次全中）② git diff 该文件
输出长度 0 ③ 复跑 70 条全绿。还原一律用 python 从 TEMP 备份 write_bytes 写回，
**不用 git checkout**（core.autocrlf=true 会按 .gitattributes 重写工作树，硬规矩 #46/#70）。

收尾另含 t6_probes/normalize_eol.py：把本 Task 新建的 5 个 .py 的工作树行尾从 LF 归一到
CRLF（与仓库其余 .py 一致）。⚠️ **blob 逐字不变**，双向取证：git hash-object 改前改后
同为 138c8d43d6c0 / 0e4fdaba7cab / fcd7a0d9ad76 / 4168ff4acf40 / 1daa9bfc6de0，
git add 之后 git diff --cached --stat 为空。⚠️ data/alert_rules.yaml **刻意不在名单里**
（.gitattributes 钉了 eol=lf，且被 sha256[:16] 指纹按字节钉住）。

实现者报告 .superpowers/sdd/2026-10-08-实施计划03-反馈预警与CRUD-API层/task-6-report.md
（57 393 B / 648 行 / LF / 0 CRLF / sha256[:16]=5933A5B6AFA771A8），八节：环境与基线复现、
P6-A2 的抽取、alerts.py 的公开面与值类型、alert_rules.yaml 的字节取证、
5 条判据的落地位置与边界测试名、变异取证完整表、顶回 8 处 / 没按派单做 7 处 /
待清扫 5 条 / 关切 6 条、最终验收。

最终验收：**1026 passed**（956 → 1026，+70），app/domain/ **1147 stmts / Miss 0 /
336 branch / BrPart 0 / 100%**（alerts.py 自己 151/0/48/0），表数仍 25、扫描面 51 → 52、
models 基线仍 33、openapi paths 仍 56、三个既有指纹逐字不变、backend/pe.db 仍不存在、
git diff a8d61b4 HEAD -- backend/data 只多出 alert_rules.yaml 一行。fix round **0** 轮。
"""

out = pathlib.Path(os.environ["TEMP"]) / "t6_commit3.txt"
out.write_bytes(MESSAGE.encode("utf-8"))
data = out.read_bytes()
print("wrote", out, len(data), "bytes; BOM:", data.startswith(b"\xef\xbb\xbf"))

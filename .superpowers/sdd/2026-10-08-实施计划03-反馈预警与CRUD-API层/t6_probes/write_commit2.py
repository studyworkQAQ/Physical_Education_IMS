"""写 commit 2 的信息（UTF-8 无 BOM）到 TEMP，供 git commit -F 用。"""
import os
import pathlib

MESSAGE = """feat(alerts): spec §8.2 的 5 条预警规则 —— alert_rules.yaml + domain/alerts.py + refdata_alerts.py

阈值住 data/alert_rules.yaml（spec §4.4 逐字「静态 YAML + 版本号，不入库……改阈值应走
版本控制与评审」），判据住 app/domain/alerts.py（纯函数叶子，无 I/O），加载与校验住
app/refdata_alerts.py（Ruling 96：值类型住 domain、加载器住 domain 外）。

5 条规则的判据与 spec §8.2 的口径逐字对齐：RED_MINITEST_DROP 严格 < 且需 3 个数据点、
RED_RPE_SUSTAINED >= 3、YELLOW_CHECKIN_GAP >= 2 个应打卡训练日、
YELLOW_CLASS_RPE_HIGH 严格 > 7.0（班级作用域）、GREEN_MASTERY 完成度 100% AND 小测提升。
「>=」与「>」两处刻意不同——都照 spec 原文抄（那一条写「≥ 9」、这一条写「> 7」）。

⚠️ window_key 是 alert 表去重键的一半，RED_RPE_SUSTAINED 那一条取的是
**凑满 streak 那一次**的 class_session_id（rpe_session_ids[streak - 1]），不是最后一次：
否则连续第 3、4、5 次快评会得到三个不同的键、插进三行 alert、推三次「减量 20%」，
训练量被连乘成 0.8³ = 0.512，而全链路没有一处报错（Review Focus 第 3 条）。

实现者顶回 5 处（逐条取证见 task-6-report §7）：
① subject_key 的两个前缀（student: / section:）—— app/db/models/feedback.py、
   app/api/schemas/alerts.py、tests/db/test_models.py **三处**已落地的 docstring 都把
   它的算式钉为「唯一所有者是 app.domain.alerts」，而计划的 Interfaces 只给了 window_key；
② StudentSignals.checkin_gap_end —— YELLOW_CHECKIN_GAP 的 window_key 要那个 ISO 串，
   而原字段清单里一个日期字段都没有（P6-A4 只说了「换成调用方已算好的 str」，没加字段）；
③ StudentSignals.semester_id / week —— GREEN_MASTERY 是 **student** 作用域而它的
   window_key 是 semester_id:week，P6-A1 只给 ClassSignals 补了这两个；
④ GREEN_MASTERY 用 >= 而不是计划正文的 ==：参数名逐字是 completion_rate_min（一个
   _min 被 == 消费是自相矛盾的），而 completion_rate 是 [0,1] 的比率故两者对任何合法
   输入逐格等价；更要紧的是写成 == 会让本 Task 唯一要求的变异测试**没有靶子**
   （== → >= 在 [0,1] 上不可分辨，任何测试都不会红）；
⑤「判不了」的留痕要有出口 —— 计划要求 insufficient_points 留痕，但不触发就没有 Hit、
   也就没有 snapshot；而 points_needed 是 YAML 参数，故这个判断必须在 domain（否则
   Task 7 得再读一次那个阈值 = 第二个所有者）。处置：每个求值器返回 (命中, 留痕) 一对，
   evaluate_* 取前半、student_skip_traces / class_skip_traces 取后半，两处不可能漂。

加载器拦的坏形状（Review Focus 第 5 条，一律点名文件 + 行号 + 键路径）：缺 version、
version 不是 str、顶层/rules/规则块不是映射、规则 ID 多一个或少一个、level/scope 值非法、
YAML 的 scope 与 declared_scope() 矛盾（没有这道对账 scope 就是装饰）、params 缺键/多键、
阈值不是数、计数写成小数（streak 要当下标用）、比率不在 (0,1)、计数 < 1、
points_needed != consecutive + 1、YAML 语法错、文件为空、文件不存在。

956 → 1026 passed（+70）。app/domain/ 覆盖率 996/0/288/0 → **1147/0/336/0/100%**
（alerts.py 自己 151 stmts / Miss 0 / 48 branch / BrPart 0）。扫描面 51 → 52
（domain 16 → 17）；表数仍 25；models.__all__ 仍 33；openapi paths 仍 56；
三个既有指纹逐字不变；backend/pe.db 仍不存在。
"""

out = pathlib.Path(os.environ["TEMP"]) / "t6_commit2.txt"
out.write_bytes(MESSAGE.encode("utf-8"))
data = out.read_bytes()
print("wrote", out, len(data), "bytes; BOM:", data.startswith(b"\xef\xbb\xbf"))

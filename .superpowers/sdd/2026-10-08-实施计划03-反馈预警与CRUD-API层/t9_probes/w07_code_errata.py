"""Task 9 落地脚本 07：19 条勘误里**代码/测试侧**的那些（逐条精确串替换 + 命中一次断言）。

⚠️ 字节级替换：这些文件的工作树行尾是**混合**的（``git ls-files --eol`` 实测
run_stratify.py / percentile.py / stratify.py / test_golden_cases.py / test_stratify.py /
test_percentile.py / test_prescription_stage.py 是 w/crlf，而 feedback.py / report.py /
report_stage.py 是 w/lf），按文本读写会统一行尾、制造巨大的无意义 diff。
⚠️ 每一处断言**恰好命中一次**：抄错当场响，不静默漏改。
⚠️ **历史陈述刻意不动**（绑时点的话改了就变假）：只改「今天为真」的那些句子。
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
CRLF = b"\r\n"
LF = b"\n"

EDITS: dict[str, list[tuple[str, str, str]]] = {
    # ------------------------------------------------------------------ #1 + #11
    "app/domain/alerts.py": [
        (
            "#1 AlertRules.version 的留痕去处（Task 7 顶回 4 的裁定）",
            "``version`` 是 spec §4.4 要求的「静态 YAML + **版本号**」的那一半：Task 7 把它写进\n"
            "    ``weekly_adjustment`` 的 ``auto`` 来源留痕，于是一张已经减过量的训练单能回答\n"
            "    「当时是按哪一版阈值判的」。",
            "``version`` 是 spec §4.4 要求的「静态 YAML + **版本号**」的那一半：Task 7 把它写进\n"
            "    **``alert.trigger_snapshot[\"alert_rules_version\"]``**，于是一条已经触发过的预警\n"
            "    能回答「当时是按哪一版阈值判的」。\n"
            "    ⚠️⚠️ **本处此前印的是「写进 ``weekly_adjustment`` 的 ``auto`` 来源留痕」，那句是错的**\n"
            "    （Plan 03 Task 7 的顶回 4）：``weekly_adjustment.reason`` 那一列**刻意不带版本号**，\n"
            "    因为它是 ``UniqueConstraint(\"prescription_id\", \"week\", \"reason\", \"source\")``\n"
            "    的一列——把版本号拼进去等于「**升一次版本号 = 同一周可以再减一次量**」→\n"
            "    ``0.8 × 0.8 = 0.64``，而教师只以为自己减了一次（Review Focus 第 3 条要挡的正是它）。\n"
            "    ``trigger_snapshot`` 是一个 ``JsonText`` 列、**不进去重键**，故版本号落在那里\n"
            "    既可离线复核、又不影响去重。写入点是\n"
            "    :func:`app.pipeline.alert_stage.evaluate_alerts` 里 ``_persist`` 的那一行\n"
            "    ``snapshot = {**hit.snapshot, \"alert_rules_version\": rules.version, **extra}``。",
        ),
        (
            "#11 subject_key 的宽度口径（27/超宽 3 → 25/超宽 1）",
            "#: ⚠️ 是 ``section`` 而不是 ``course_section``：``subject_key`` 是 ``String(24)``，\n"
            "#: 最长形状 ``course_section:2147483647`` 是 27 字符、**超宽 3**；``section:2147483647``\n"
            "#: 是 18 字符、余量 6（``tests/db/test_models.py`` 钉的正是这一个数）。",
            "#: ⚠️ 是 ``section`` 而不是 ``course_section``：``subject_key`` 是 ``String(24)``，\n"
            "#: 最长形状 ``course_section:2147483647`` 是 **25** 字符、**超宽 1**；\n"
            "#: ``section:2147483647`` 是 18 字符、余量 6（``tests/db/test_models.py`` 钉的正是这一个数）。\n"
            "#: ⚠️ **本处此前印的是「27 字符、超宽 3」，两个数都错**（Plan 03 Task 9 实测更正：\n"
            "#: ``len(\"course_section:\") == 15`` + ``len(\"2147483647\") == 10`` = **25**，\n"
            "#: 而列宽 24，故超宽 **1**）。⚠️ **结论不变、前缀仍必须是 ``section``**——超宽 1 与超宽 3\n"
            "#: 在 SQLite 上都不报错（它不强制 ``VARCHAR`` 长度），而换到 MySQL 会**静默截断**，\n"
            "#: 截断后的 ``subject_key`` 会让去重键指向另一个主语。错的只是报告里的那两个数。",
        ),
    ],
    # ------------------------------------------------------------------ #3 + #6
    "app/db/repo.py": [
        (
            "#3 delete_by_batch：九张里清几张 + Alert 是谁接进的",
            "``app/pipeline/daily.py`` 的 ``_replay_cleanup`` **今天清的是上面九张里的五张**\n"
            "    （Plan 01 的三张 + Plan 02 的两张；删的顺序是承重的：``weekly_adjustment``\n"
            "    的 ``prescription_id`` 指向 ``prescription``，而 ``PRAGMA foreign_keys=ON``\n"
            "    真的在强制它，故必须**先删子表**，P7-A4）。Plan 03 那四张里，``Alert`` 与\n"
            "    ``WeeklyClassReport`` 由 Task 8 接进清单，",
            "``app/pipeline/daily.py`` 的 ``_replay_cleanup`` **今天清的是上面九张里的七张**\n"
            "    （Plan 01 的三张派生表 + Plan 02 的 ``prescription`` / ``weekly_adjustment``\n"
            "    + Plan 03 Task 7 的 ``alert`` + Plan 03 Task 8 的 ``weekly_class_report``；\n"
            "    删的顺序是承重的：``weekly_adjustment`` 的 ``prescription_id`` 指向 ``prescription``，\n"
            "    而 ``PRAGMA foreign_keys=ON`` 真的在强制它，故必须**先删子表**，P7-A4）。\n"
            "    ⚠️ **本处此前印的是「五张」与「``Alert`` 与 ``WeeklyClassReport`` 由 Task 8 接进清单」，\n"
            "    两个数都已过期**（Plan 03 Task 9 更正）：``Alert`` 是 **Task 7** 接进的、\n"
            "    ``WeeklyClassReport`` 才是 Task 8，故今天是**七张**。Plan 03 那四张里，",
        ),
        (
            "#6 upsert 的通用面：14 个模型 → 25 个",
            "对 14 个模型通用，不针对任何一张表特化：``key_fields`` 由调用方按该表的自然键",
            "对 **25** 个模型通用（⚠️ 本处此前印的是「14 个」，那是 Plan 01 结案时的表数；"
            "Plan 02 加 4 张、Plan 03 Task 2 加 7 张之后是 25，Plan 03 Task 9 实测更正），"
            "不针对任何一张表特化：``key_fields`` 由调用方按该表的自然键",
        ),
    ],
    # ------------------------------------------------------------------ #6
    "app/db/session.py": [
        (
            "#6 模块 docstring 的表数",
            "``Session``、建表函数 :func:`init_db`。15 张表的模型在 :mod:`app.db.models`，",
            "``Session``、建表函数 :func:`init_db`。**25** 张表的模型在 :mod:`app.db.models`，",
        ),
        (
            "#6 Base 的 docstring 的表数",
            "\"\"\"全部 15 张表的声明基类（张数由 Plan 02 逐 Task 递增，归属见 :mod:`app.db.models`）。",
            "\"\"\"全部 **25** 张表的声明基类（张数由 Plan 02 / Plan 03 逐 Task 递增：15 → 18 → 25，"
            "归属见 :mod:`app.db.models`；⚠️ 本处此前印的「15 张」是 Plan 01 结案时的数，"
            "Plan 03 Task 9 实测更正）。",
        ),
        (
            "#6 init_db 里那句注释的表数",
            "from app.db import models  # noqa: F401  仅为把 15 张表注册进 Base.metadata",
            "from app.db import models  # noqa: F401  仅为把 25 张表注册进 Base.metadata",
        ),
    ],
    # ------------------------------------------------------------------ #5
    "app/db/models/feedback.py": [
        (
            "#5 模块 docstring 的写入方表：notification 那一行",
            "``notification``            §4.6         Task 8 的 ``InAppChannel``\n"
            "``weekly_class_report``     §4.7         管道（Task 9 的 ``report_stage``）",
            "``notification``            §4.6         ``InAppChannel``（Task 7 建、Task 8 加「已读」端点）\n"
            "``weekly_class_report``     §4.7         管道（Task 8 的 ``report_stage``）",
        ),
        (
            "#5 模块 docstring：class_session 那一段的「传导给 Task 8」",
            "正是这个区别的要害（按硬规矩 #86 传导给 Task 8）：``rpe_record.class_session_id`` 是",
            "正是这个区别的要害（按硬规矩 #86 传导给 Task 8，**Task 8 已兑现**：``Alert`` 由 Task 7、\n"
            "``WeeklyClassReport`` 由 Task 8 接进清单，而 ``ClassSession`` 两次都**没有**被接进去）：\n"
            "``rpe_record.class_session_id`` 是",
        ),
        (
            "#5 模块 docstring：「Task 8 可以照常接进清单」",
            "``notification.alert_id`` 带 ``ON DELETE SET NULL``），Task 8 可以照常接进清单。",
            "``notification.alert_id`` 带 ``ON DELETE SET NULL``），故 Task 7 与 Task 8 已经照常把它们\n"
            "接进清单（**谁兑现谁改写**：这两句原先是对 Task 8 的预告，Plan 03 Task 9 按实际发生的事改写）。",
        ),
        (
            "#5 ClassSession.batch_id 列注释里的「传导给 Task 8」",
            "#: 完整理由见模块 docstring（按硬规矩 #86 传导给 Task 8）。",
            "#: 完整理由见模块 docstring（按硬规矩 #86 传导给 Task 8，**已兑现**：Task 7/8 各接了一张\n"
            "#: 新表进清单，``ClassSession`` 两次都没被接进去）。",
        ),
        (
            "#5 Alert.batch_id 列注释：Task 8 → Task 7（已发生）",
            "#: 指向 ``daily_sync_run``：Task 8 会把 ``Alert`` 接进 ``_replay_cleanup``。\n"
            "    #: ⚠️ ``notification.alert_id`` 带 ``ON DELETE SET NULL``，正是为了让那一步\n"
            "    #: 不会连带删掉已经推出去的通知、也不会当场 FK 违例（见 :class:`Notification`）。",
            "#: 指向 ``daily_sync_run``：**Plan 03 Task 7 已把 ``Alert`` 接进 ``_replay_cleanup``**\n"
            "    #: （⚠️ 本处此前印的是「Task 8 会把 ``Alert`` 接进」——接它的是 Task 7，Task 8 接的是\n"
            "    #: ``WeeklyClassReport``；谁兑现谁改写，Plan 03 Task 9 按实际发生的事更正）。\n"
            "    #: ⚠️ ``notification.alert_id`` 带 ``ON DELETE SET NULL``，正是为了让那一步\n"
            "    #: 不会连带删掉已经推出去的通知、也不会当场 FK 违例（见 :class:`Notification`）。",
        ),
        (
            "#5 Notification.alert_id 列注释：Task 8 → Task 7（已发生）",
            "#: ⚠️ ``ON DELETE SET NULL`` 是承重的（计划正文的显式决定）：Task 8 会把 ``Alert``\n"
            "    #: 加进 ``_replay_cleanup``，而本表**不带** ``batch_id``、不进那份清单。",
            "#: ⚠️ ``ON DELETE SET NULL`` 是承重的（计划正文的显式决定）：**Plan 03 Task 7 已把\n"
            "    #: ``Alert`` 加进 ``_replay_cleanup``**（⚠️ 本处此前印的是「Task 8 会把」，接它的是\n"
            "    #: Task 7；谁兑现谁改写，Plan 03 Task 9 按实际发生的事更正），\n"
            "    #: 而本表**不带** ``batch_id``、不进那份清单。",
        ),
        (
            "#5 Notification.prescription_id 列注释：「不是 Task 8 才会发生的事」",
            "#: P7-A4），故「重放那天删掉处方」不是 Task 8 才会发生的事、是现在每天都在发生的事。",
            "#: P7-A4），故「重放那天删掉处方」不是将来某个 Task 才会发生的事、是现在每天都在发生的事。",
        ),
        (
            "#5 WeeklyClassReport.batch_id 列注释：Task 8/9 → Task 8（已发生）",
            "#: 没有子表指着本表，故 Task 8/9 把它接进 ``_replay_cleanup`` 没有\n"
            "    #: ``class_session`` 那个问题。",
            "#: 没有子表指着本表，故 **Plan 03 Task 8 已把它接进 ``_replay_cleanup``**\n"
            "    #: （清单因此从六张扩到七张），没有 ``class_session`` 那个问题。",
        ),
    ],
    # ------------------------------------------------------------------ #5（测试侧的两处预告）
    "tests/db/test_models.py": [
        (
            "#5 test_models：「Task 8 会把 Alert 接进那份清单」",
            ":func:`app.pipeline.daily._replay_cleanup`（Task 8 会把 ``Alert`` 接进那份清单）",
            ":func:`app.pipeline.daily._replay_cleanup`（**Plan 03 Task 7 已把 ``Alert`` 接进那份清单**，"
            "Task 8 又接了 ``WeeklyClassReport``，故今天是七张）",
        ),
        (
            "#5 test_models：「Task 8 会把 Alert 加进」",
            "``alert_id`` 的那一半是计划正文的显式决定：Task 8 会把 ``Alert`` 加进",
            "``alert_id`` 的那一半是计划正文的显式决定：**Plan 03 Task 7 已把 ``Alert`` 加进",
        ),
        (
            "#5 test_models：上一条的后半句（闭合加粗）",
            ":func:`app.pipeline.daily._replay_cleanup`，而 ``notification`` **不带** ``batch_id``、\n"
            "    不进那份清单——重放删掉 alert 时，若这一列是普通外键，",
            ":func:`app.pipeline.daily._replay_cleanup`**，而 ``notification`` **不带** ``batch_id``、\n"
            "    不进那份清单——重放删掉 alert 时，若这一列是普通外键，",
        ),
    ],
    # ------------------------------------------------------------------ #4
    "app/pipeline/prescription_stage.py": [
        (
            "#4 「auto 也留给 Plan 03」已过期",
            "本阶段**不写** ``weekly_adjustment`` 行——``source = \"teacher\"`` 由 Plan 03 的教师端写、\n"
            "``source = \"auto\"``（spec §8.4「预警触发减量 20%」）也留给 Plan 03。本模块对这张表的参与有\n"
            "**两处、都不是写**：① :func:`app.pipeline.daily._replay_cleanup` 按 ``batch_id`` 删它\n"
            "（且**必须排在 ``prescription`` 前面**，P7-A4）；② Task 8 的 :func:`weekly_factors_of`\n"
            "**读**它并转成 :class:`~app.domain.prescription.weekly.WeeklyFactor` 值对象\n"
            "（⚠️ 它今天在生产路径上**没有调用方**、那张表也**没有数据**，理由与守卫口径逐字写在它的\n"
            "docstring 里，P8-A4）。口径：",
            "本阶段**不写** ``weekly_adjustment`` 行——⚠️ **本处此前印的是「``source = \"teacher\"`` 由\n"
            "Plan 03 的教师端写、``source = \"auto\"``（spec §8.4「预警触发减量 20%」）也留给 Plan 03」，\n"
            "两句都已过期**（Plan 03 Task 9 按实际发生的事改写）：``auto`` 那一半**已由 Task 7 落地**\n"
            "（写入方是 :func:`app.pipeline.alert_stage._write_auto_adjustment`，一条 ``red`` 预警落库的\n"
            "同一批里就自动写，**不等教师点击**），``teacher`` 那一半**已由 Task 4 落地**\n"
            "（``POST /api/prescriptions/{id}/overrides`` 的 ``VOLUME_SCALE`` / ``PAUSE`` 两档）。\n"
            "本模块对这张表的参与仍是**两处、都不是写**：\n"
            "① :func:`app.pipeline.daily._replay_cleanup` 按 ``batch_id`` 删它\n"
            "（且**必须排在 ``prescription`` 前面**，P7-A4）；② :func:`weekly_factors_of`\n"
            "**读**它并转成 :class:`~app.domain.prescription.weekly.WeeklyFactor` 值对象\n"
            "（⚠️ 它今天在**生产路径上有两个调用方**了：``GET /api/students/{id}/weekly-sheet``\n"
            "与教师端的 ``GET /api/teacher/students/{id}/weekly-sheet``，两者共用\n"
            ":func:`app.api.routers.prescription._weekly_sheet_response`；那张表也**有数据**了\n"
            "——演示库实测 11 行 ``source=\"auto\"``。P8-A4 当时记的「没有调用方、没有数据」\n"
            "是 Task 8 结案时的状态，Plan 03 Task 9 更正）。口径：",
        ),
    ],
    # ------------------------------------------------------------------ #7 + #9
    "app/refdata_prescription.py": [
        (
            "#7 公有函数个数：5 → 8（AST 实测）",
            "⚠️ 主语是**加载侧的四个函数**（``load_exercises`` / ``exercises`` / ``load_equivalence``\n"
            "    / 本函数），不是本模块的全部公有函数——本模块公有函数是 **5** 个，第 5 个是\n"
            "    ``sync_exercises``（``exercise`` 表的投影入口，不是加载器；fix round 3 补主语，此前只写\n"
            "    「本 Task 的四个函数」，在那个未言明的口径外读起来与实测的 5 个矛盾）。计划只点了加载侧",
            "⚠️ 主语是**加载侧的四个函数**（``load_exercises`` / ``exercises`` / ``load_equivalence``\n"
            "    / 本函数），不是本模块的全部公有函数——⚠️ **本处此前印的是「本模块公有函数是 5 个，\n"
            "    第 5 个是 ``sync_exercises``」，那个 5 是 Plan 02 Task 3 的时点值、今天已过期**\n"
            "    （Plan 03 Task 9 用 AST 实测更正：``ast.parse`` 本文件、数 ``tree.body`` 里\n"
            "    ``FunctionDef`` 且名字不以下划线开头的，得 **8** 个 = 那 4 个加载侧 +\n"
            "    ``sync_exercises`` + ``load_templates`` + ``templates`` + ``sync_templates``；\n"
            "    后三个是 Plan 02 Task 3 建模板那一半时加的，加的时候没回来改这一句）。\n"
            "    ⚠️ 而 fix round 3 补主语那一次的处置**仍然对**（「本 Task 的四个函数」在那个未言明的\n"
            "    口径外读起来与实测矛盾），只是它写下的那个实测值绑错了时点。计划只点了加载侧",
        ),
        (
            "#9 「两段的报错口径刻意不同」没指向 app.refdata_yaml",
            "**两段的报错口径刻意不同**（硬规矩 #39：写下守卫能力时要写明它守不住什么）：动作库那一段",
            "**两段的报错口径刻意不同**（硬规矩 #39：写下守卫能力时要写明它守不住什么；⚠️ 而这两段\n"
            "**今天都由 :mod:`app.refdata_yaml` 实现**——Plan 03 Task 6 把那套机制里通用的 6 个助手\n"
            "抽进了那个公共模块，本模块只留 5 个薄适配器 + 一个 ``_line_index`` 别名，\n"
            "故下面讲的「口径」是 :mod:`app.refdata_yaml` 的口径、由本模块与\n"
            ":mod:`app.refdata_alerts` 两个消费者共用，见本 docstring 第四节）：动作库那一段",
        ),
    ],
    # ------------------------------------------------------------------ #8
    "tests/domain/test_prescription_templates.py": [
        (
            "#8 行号索引的实现住址：refdata_prescription._line_index → refdata_yaml.line_index",
            "``yaml.safe_load`` **不保留位置信息**，故加载器另跑一次 ``yaml.compose`` 建一张\n"
            "    「键路径 → 1 基行号」的索引（:func:`app.refdata_prescription._line_index`）。",
            "``yaml.safe_load`` **不保留位置信息**，故加载器另跑一次 ``yaml.compose`` 建一张\n"
            "    「键路径 → 1 基行号」的索引。⚠️ **那个实现今天住在 :func:`app.refdata_yaml.line_index`**\n"
            "    （Plan 03 Task 6 抽的公共模块）；``app.refdata_prescription._line_index`` 只是它的\n"
            "    **一个别名**（``_line_index = refdata_yaml.line_index``，由\n"
            "    ``tests/test_refdata_alerts.py::test_line_index_is_the_same_object_in_every_consumer``\n"
            "    用 ``is`` 钉住身份）。⚠️ 本处此前只点了那个别名、没点实现的住址，于是照它去改\n"
            "    「行号索引」的人会改到一行赋值语句上（Plan 03 Task 9 更正）。",
        ),
    ],
    # ------------------------------------------------------------------ #12
    "app/api/routers/feedback.py": [
        (
            "#12 「原型没有教师↔班级↔学生授权模型」已被 Task 8 改写",
            "  ⚠️ 原型**没有**「教师 ↔ 班级 ↔ 学生」的授权模型，故任何在册教师可以读任何班的\n"
            "  名单、录任何班的小测（:func:`app.api.deps.require_teacher` 的 docstring 里如实记了\n"
            "  这条代价）。",
            "  ⚠️ **本模块的这四个端点今天只过「在册」闸门、不过任教关系闸门**，故任何在册教师可以\n"
            "  读任何班的名单、录任何班的小测。⚠️ **本处此前印的是「原型没有『教师 ↔ 班级 ↔ 学生』的\n"
            "  授权模型」，那句自 Plan 03 Task 8 起已经不成立**（Task 9 核实后改写）：那个模型\n"
            "  **已经建出来了**——:func:`app.api.deps.require_teaches_section`（班级那一侧，\n"
            "  判据是 ``course_section.teacher_id``）与 :func:`require_teaches_student`（学生那一侧，\n"
            "  判据是 ``enrollment ⋈ course_section.teacher_id`` 且两行的 ``semester_id`` 都必须等于\n"
            "  入参那一个学期），只是**只挂在读的一侧**（教师大屏、班级周报、教师端读单个学生的\n"
            "  本周训练单）。⚠️ 于是「任何在册教师可以跨班」这句话今天只对**写入端点**成立：\n"
            "  本模块的这四个，加上 ``POST …/overrides`` / ``POST …/regenerate`` /\n"
            "  ``POST …/alerts/{id}/handle``。收窄它们是一次一行的改动（把 ``require_teacher`` 换成\n"
            "  ``require_teaches_section``），但那会改掉 Plan 04 教师端的可点范围，故移交 Plan 04。\n"
            "  完整代价记在 :func:`app.api.deps.require_teacher` 的 docstring 里。",
        ),
    ],
    # ------------------------------------------------------------------ #13
    "app/pipeline/alert_stage.py": [
        (
            "#13 两个 skipped 同名不同义（alert_stage 这一侧）",
            "    ``skipped``\n"
            "        ``{rule_id: 「求值过、但判不了」的次数}``——**P7-A3 第 1 条的落点**。",
            "    ``skipped``\n"
            "        ``{rule_id: 「求值过、但判不了」的次数}``——**P7-A3 第 1 条的落点**。\n"
            "        ⚠️⚠️ **它与 :attr:`app.pipeline.report_stage.ReportSummary.skipped` 同名不同义**\n"
            "        （Plan 03 Task 9 写明）：那一格数的是「**名册为空**的教学班数」\n"
            "        （``enrollment`` 里一个学生都没有 → 不写周报行），与本格「哪条规则对哪几个人\n"
            "        判不了」是两个完全不相干的量，且**类型也不同**（那一格是 ``int``、本格是 ``dict``）。\n"
            "        两格都叫 ``skipped`` 是因为它们各自回答「这一次跑**跳过**了什么」，\n"
            "        而两个阶段跳过的是不同种类的东西。⚠️ 合并成一个名字会让下一个人以为\n"
            "        「预警跳过的次数」与「周报跳过的班数」可以相加。",
        ),
    ],
    # ------------------------------------------------------------------ #17
    "app/refdata_alerts.py": [
        (
            "#17 阈值个数：8 → 9",
            "（``level`` / ``scope`` 走枚举，8 个阈值全是数）。保留它是为了与另一个消费者的适配器",
            "（``level`` / ``scope`` 走枚举，**9** 个阈值全是数——逐条 3 / 2 / 1 / 1 / 2；"
            "⚠️ 本处此前印的是「8 个」，Plan 03 的计划正文与派单一路跟着写 8，"
            "而 ``data/alert_rules.yaml`` 实测是 **9** 个，Plan 03 Task 9 用运行时口径更正）。"
            "保留它是为了与另一个消费者的适配器",
        ),
    ],
    "tests/test_refdata_alerts.py": [
        (
            "#17 阈值个数：8 → 9（模块 docstring）",
            "5 条规则的 8 个阈值、版本号、指纹都写在本文件里，**不从**被测模块或那份 YAML 反推。",
            "5 条规则的 **9** 个阈值（逐条 3 / 2 / 1 / 1 / 2）、版本号、指纹都写在本文件里，"
            "**不从**被测模块或那份 YAML 反推。⚠️ 本处此前印的是「8 个阈值」，"
            "Plan 03 Task 9 按 ``data/alert_rules.yaml`` 的运行时口径更正为 9。",
        ),
        (
            "#17 阈值个数：8 → 9（那条测试的 docstring）",
            "\"\"\"版本号、5 个规则 ID、它们的 ``level`` / ``scope`` / 8 个阈值全部逐字对账。",
            "\"\"\"版本号、5 个规则 ID、它们的 ``level`` / ``scope`` / **9** 个阈值全部逐字对账。",
        ),
    ],
    "tests/domain/test_alerts.py": [
        (
            "#17 阈值个数：8 → 9",
            "``.value``、三级、两个作用域、8 个阈值、每一种 ``window_key`` / ``subject_key`` 的成品串",
            "``.value``、三级、两个作用域、**9** 个阈值（逐条 3 / 2 / 1 / 1 / 2）、"
            "每一种 ``window_key`` / ``subject_key`` 的成品串",
        ),
    ],
    # ------------------------------------------------------------------ #10
    "tests/architecture/test_layering.py": [
        (
            "#10 两条下界断言的注释实测值已陈旧（**只改注释、不改断言**）",
            "    #   40 = backend/ 下 .py 的个数下界（Task 4 落地时实测 69）；\n"
            "    #   16 = 全仓相对导入的条数下界（Task 4 落地时实测 18，命令见\n"
            "    #        _imported_modules 的 docstring）；",
            "    #   40 = backend/ 下 .py 的个数下界（**Plan 02 Task 4 落地时实测 69**——那个数绑的是\n"
            "    #        那一个时点，⚠️ **不要把它改成今天的值**：本行是「下界的取法说明」，\n"
            "    #        改成当前值会让下界与实测贴死、一次合法重构就红）；\n"
            "    #        ⚠️ **Plan 03 Task 9 结案时的当前值是 130**（app 82 + tests 47 + scripts 1，\n"
            "    #        命令：`cd backend; python -c \"import pathlib; print(len(pathlib.Path('.').rglob('*.py')))\"`）；\n"
            "    #   16 = 全仓相对导入的条数下界（**Plan 02 Task 4 落地时实测 18**，命令见\n"
            "    #        _imported_modules 的 docstring；⚠️ 同上，那个 18 绑的是 Task 4 的时点。\n"
            "    #        ⚠️ **Plan 03 Task 9 结案时的当前值是 38**）；",
        ),
    ],
}


def _edit(rel: str, triples: list[tuple[str, str, str]]) -> None:
    path = BACKEND / rel
    raw = path.read_bytes()
    crlf = raw.count(CRLF)
    bare = raw.count(LF) - crlf
    all_crlf = bool(crlf) and not bare
    for label, old, new in triples:
        # ⚠️ 两种行尾都试一遍（本仓的文件有 w/crlf、w/lf 与**混合**三种，
        #    `git ls-files --eol` 实测；混合的那一类只能用「哪个命中就用哪个」判定）
        candidates = [
            (old.encode("utf-8"), new.encode("utf-8")),
            (old.replace("\n", "\r\n").encode("utf-8"),
             new.replace("\n", "\r\n").encode("utf-8")),
        ]
        picked = None
        for needle, replacement in candidates:
            if raw.count(needle) == 1:
                picked = (needle, replacement)
                break
        if picked is None:
            # 幂等：已经改过一遍（old 不在、new 在）就跳过，让本脚本可以重跑
            already = any(raw.count(rep) == 1 and raw.count(ndl) == 0
                          for ndl, rep in candidates)
            assert already, (
                f"{rel} / {label}: 两种行尾下锚点都没有**恰好命中一次**"
                f"（LF={raw.count(candidates[0][0])} / CRLF={raw.count(candidates[1][0])}）"
            )
            print(f"    · 跳过（已应用）：{label}")
            continue
        raw = raw.replace(*picked)
    path.write_bytes(raw)
    after = path.read_bytes()
    n_crlf = after.count(CRLF)
    n_bare = after.count(LF) - n_crlf
    print(f"  {rel}: {len(after)} B, CRLF={n_crlf} bare LF={n_bare}"
          f"（改前 CRLF={crlf} bare={bare}）—— {len(triples)} 处")
    assert (n_crlf == 0) == (crlf == 0), f"{rel}: 行尾种类被改了"


print("== 应用 ==")
total = 0
for rel, triples in EDITS.items():
    _edit(rel, triples)
    total += len(triples)
print(f"done; 编辑处数 = {total}，涉及文件 = {len(EDITS)}")
sys.exit(0)

"""``scripts/demo.ps1`` 的**数据准备**那一半（Plan 03 Task 9）。

一条命令把演示库灌好：``init_db`` → ``seed_database``（组织结构）→ ``run_daily``
（**处方生成日**那一次，见下面第四节）→ ``write_csv``（一学期的体测/体成分/问卷 CSV）
→ ``build_demo_feedback``（反馈三源）→ ``run_daily``（**演示日**那一次：九个阶段全走，
含预警与班级周报）→ **绑定演示口令 + 造出第一个管理员**（Plan 05A Task 4，
见 :data:`DEMO_PASSWORD` / :data:`DEMO_ADMIN_STAFF_NO`）。

⚠️ **最后那一步是 Plan 05A 之后新增的、且是必需的**：Plan 05A 把身份从请求头换成了
``pe_session`` cookie，而 cookie 只能由 ``POST /api/auth/login`` 种下、登录又要
``student.password_hash`` / ``teacher.password_hash`` 非空。``seed_database``
灌出来的那两列**全是 NULL**，故不绑口令的演示库上**没有一个人能登录**
（前端每一个页面都被路由守卫弹回 ``/login``，管理台的 26 个写入操作一律 403）。

--------------------------------------------------------------------------
⚠️⚠️ 为什么它是一个脚本、而不是三条 ``python -m …``
--------------------------------------------------------------------------

本仓有三个 CLI 入口——``app.seed.generate`` / ``app.pipeline.backfill`` /
``app.pipeline.daily``——而它们的 ``main()`` 各自把缺省值写死在**禁区**上：
CSV 目录是 :data:`app.config.DEFAULT_CSV_DIR`（``backend/data/seed/``，本仓恒为 0 文件、
一个字节都不许动），库是 :data:`app.config.DEFAULT_DB_URL`（``backend/pe.db``，
**不得存在**）。故 ``demo.ps1`` 里**一条 ``python -m …`` 都没有**：本脚本一律
**import 函数、显式传路径**，两个禁区因此结构上碰不到。

⚠️ 于是它也**刻意不调** :func:`app.pipeline.backfill.run_backfill`：回放的语义是
「把一学期的每个业务日都跑一遍」，而演示要的是「今天有一个能点起来的库」——
**两次** :func:`app.pipeline.daily.run_daily` 就够了（理由见下面第四节），
60 人实测每次约 1 秒，而回放 16 周 ×5 个业务日是分钟级。⚠️ 代价（硬规矩 #39）：
演示库里 ``stratification_result`` / ``derived_metrics`` 只有**两天**的行
（:data:`DEMO_RX_AS_OF` 与 :data:`DEMO_AS_OF`，⚠️ 而这两天落在**同一个学期周**里），
故「周环比流动」（:func:`app.domain.report.layer_flow`）在演示库上恒为
``has_previous = False``（上一周一次批处理都没跑）——教师大屏的流动那一块会是空的。
要它非空就得回放至少两个周日，那是 ``run_backfill`` 的活，留给需要它的人手工跑。

--------------------------------------------------------------------------
⚠️ 业务日期取 :data:`DEMO_AS_OF`（一个**周日**）
--------------------------------------------------------------------------

:func:`app.pipeline.report_stage.is_report_day` 只在 ``weekday() == 6`` 为真，
而 :func:`app.pipeline.daily.run_daily` 是按它决定「跑不跑周报阶段」的。
取一个周一的话 ``weekly_class_report`` 一行都不会有，教师大屏的
``GET /api/dashboard/weekly-class-report/{id}`` 就永远 404——演示少一整块。
⚠️ 而它也**不能太早**：``build_demo_feedback`` 往前造 4 个教学周的课次，
而它对「早于开学日」的周**跳过**，于是太早的 ``as_of`` 会让每个学生只剩 2 条快评、
``RED_RPE_SUSTAINED``（要连续 3 次）永远不触发。两个下界的实测与取值理由逐字写在
:data:`DEMO_AS_OF` 的注释里（本脚本用 ``2025-10-12`` = 学期第 6 周的周日）。

--------------------------------------------------------------------------
⚠️⚠️ 为什么跑**两次** ``run_daily``（Plan 03 全分支终审的 I2）
--------------------------------------------------------------------------

只跑一次（``DEMO_AS_OF`` 那一天）的话，演示库上**三层完成率全是 ``rate: 0.0``**、
``notification`` 表 **0 行**、5 条规则只出现 2 条——即「库里有 628 条
``completed=True`` 的打卡，而周报说三层都是 0%」，且 ``measured == students``、
``rate`` 是 ``0.0`` 而不是 ``null``，读起来像「测过了、就是 0%」，
**这违反本项目最响的那条纪律（「不知道」不得讲成「0」）**。

机制是三个各自合理的决定撞在一起（确定性的、与 ``--as-of`` 无关）：

1. ``DEMO_AS_OF`` **必须**是周日（否则一行周报都没有，见上一节）；
2. ``run_daily`` 让 ``prescription.generated_on = as_of``，于是微周期第 1 周的第 1 个
   训练日**就是那个周日**，而报表窗口里 ``<= as_of`` 的训练日**只有它一天**；
3. :mod:`app.demo_data` 的休息日规则是 ``log_date.weekday() >= 5``，周日一律是休息日
   → :func:`app.pipeline.alert_stage._counted_checkin_days` 的四个条件把它剔掉
   → 分子恒 0。

连带：``completion_rate`` 恒 0 → ``GREEN_MASTERY``（要 ``>= 1.0``）永不触发 →
电子勋章流程不可演示；``notification`` 表 0 行 → 学生端消息中心是空的、
``POST /api/notifications/{id}/read`` 无从演示；``YELLOW_CHECKIN_GAP`` 也因
「窗口里只有 1 个已过的训练日」凑不满 ``gap_days = 2``。

**处置取终审给的 (b) 案：让处方生成日早于 ``as_of``**——先在
:data:`DEMO_RX_AS_OF`（= ``DEMO_AS_OF`` 前 6 天 = 报表周的**周一**）跑一次
``run_daily`` 生成处方，再灌反馈三源，再在 ``DEMO_AS_OF`` 跑第二次。
于是报表窗口里 ``<= as_of`` 的训练日变成 3–4 个（周一到周三/周四，**全是工作日**），
分子不再恒 0。

⚠️ **为什么不取 (a) 案（把 ``app/demo_data.py`` 的休息日规则改成「按处方的训练日反推」）**，
两条实测出来的理由：

* **(a) 结构上离不开 (b) 的那次重排**：``build_demo_feedback`` 今天跑在 ``run_daily``
  **之前**，那时库里**一张处方都没有**，「按处方的训练日反推」无从反推。
  故 (a) = (b) 的重排 + 再动一次 ``demo_data`` 的口径，成本严格更高。
* **重排之后 (a) 已经没有收益**：实测 18 套模板的 ``AssembledSession.day`` 恒为
  ``1..N`` 连续（``training_days_of`` 的 docstring 逐字写了这个口径），故
  ``generated_on`` 落在周一时训练日就是周一到周三/周四，**一个周末都不含**——
  「按周末判休息日」与「按处方训练日反推」在这一格上给出同一个答案。
  而 (a) 要付的代价是 ``app/demo_data.py`` 那 4 条测试的口径全变
  （含一条幂等测试「跑三次逐字不变」），换来的是一份重复的判据。

⚠️ ``DEMO_RX_AS_OF`` 因此是**受约束的**，两个约束都写在它的注释里
（改 ``DEMO_AS_OF`` 的人必须回头看一眼）。
⚠️ 代价（硬规矩 #39）：``demo.ps1`` 多跑一次管道。实测那一次约 1 秒
（60 人 / 三源全空 → 预警与周报阶段都是空转），而 ``demo.ps1`` 的 ``elapsed``
哨兵阈值是 90 s、实测 43.96 / 48.37 s（余量 1.86×），故这一秒吃得下。
⚠️ 第二次 ``run_daily`` 的 ``prescription_count`` 是 **0**：处方是上一批生成的、
这一批一个触发都没命中（分层标签没变、处方也没到期）。**那不是失败**，
下面的复核按库里的**总行数**报，故打印时两个数分开写。

--------------------------------------------------------------------------
⚠️ 它**不建表也不删库**
--------------------------------------------------------------------------

「先删掉旧的 ``pe_demo.db``」是 ``demo.ps1`` 的第一步，**不是本脚本的**。
⚠️ 本处此前给的理由是「``init_db`` 走 ``create_all``，对已存在的表原样跳过，故一个旧库
不会报错、也不会补上新增的 NOT NULL 列」——那一条自 **Plan 06 Task 1** 起**不再成立**：
``init_db`` 现在走 ``backend/migrations/`` 那条 alembic 迁移链，旧库会被 ``upgrade head``
补上新列（而**引入迁移链之前**建的那些库会先被 ``stamp`` 到基线再升，见
:func:`app.db.session.init_db` 的 docstring）。
⚠️ 但「删旧库」这一步**照旧保留**，理由换成了一条更硬的：**演示必须可复现**。
``demo.ps1`` 会打印各表行数、本脚本的 [6/7] 会从库里取一个**真**学号，两样都是
演示时**要念给甲方听的**，而它们只有在「库是从零灌出来的」时候才是同一组数。
把「删文件」留在 shell 里，是因为**只有 shell 知道用户想删哪个文件**；
本脚本收到的是一个 URL，它无权替用户决定「这个文件可以删」。
"""
import argparse
import datetime as dt
import os
import pathlib
import sys

# ⚠️ 本文件在 ``backend/scripts/`` 下，而 ``python scripts/demo_bootstrap.py`` 会把
#    ``backend/scripts`` 放进 sys.path[0]、**不是** ``backend``，故显式补一条。
BACKEND = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.adapters.mock_lepao import MockLePaoAdapter  # noqa: E402
from app.auth.passwords import PBKDF2_ITERATIONS_ENV_VAR, hash_password  # noqa: E402
from app.db.models.feedback import (  # noqa: E402
    Alert,
    ClassSession,
    MiniTest,
    Notification,
    RpeRecord,
    TrainingLog,
    WeeklyClassReport,
)
from app.db.models.organisation import (  # noqa: E402
    CourseSection,
    Enrollment,
    Semester,
    Student,
    Teacher,
)
from app.db.models.prescription import Prescription, WeeklyAdjustment  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.demo_data import build_demo_feedback  # noqa: E402
from app.pipeline.daily import business_now, run_daily  # noqa: E402
from app.seed.config import SeedConfig  # noqa: E402
from app.seed.generate import build_dataset, seed_database, write_csv  # noqa: E402

#: ---------------------------------------------------------------------------
#: **演示口令**（Plan 05A Task 4）。⚠️ 它是**公开**的：本脚本把它打印出来，
#: spec §13 也逐字记着它，登录页的提示里也提到它。
#: ---------------------------------------------------------------------------
#: 为什么必须有它：Plan 05A 之后身份走 `pe_session` cookie，而 cookie 只能由
#: `POST /api/auth/login` 种下、登录又要 `password_hash` 非空。演示库是
#: `seed_database` 灌出来的，那一列**全是 NULL** —— 不绑口令的话演示库上
#: **没有一个人能登录**，前端每一个页面都会被路由守卫弹回 `/login`，
#: 而管理台的 26 个写入操作一律 403（Plan 05A Task 2 之后仅管理员）。
#:
#: ⚠️ **不用 `12345678` 这类**（派单逐字要求）：它能过后端的弱口令检查
#: （`MIN_PASSWORD_LENGTH = 8`，只判长度不判复杂度），但一个演示系统的口令
#: 会被人抄去试别的系统，而 `12345678` 是撞库字典的第一行。
#: 取一个**与项目相关、可读、可打**的串：`pe` = Physical Education（本仓的目录名
#: `Physical_Education_ims`），`demo` 说明它是演示值，`2025` 是演示库那个学年。
#: 12 个字符 > 8 ✓。
DEMO_PASSWORD = "pe-demo-2025"

#: 演示脚本里哈希用的 PBKDF2 迭代次数。
#:
#: ⚠️⚠️ **它低于生产缺省值**（`app.auth.passwords.PBKDF2_DEFAULT_ITERATIONS` =
#: **600 000** = OWASP 2023 对 PBKDF2-SHA256 的建议值），故本脚本必须**打印**它
#: （下面 `[6/7]` 那一行），而生产缺省值**一个字都没变**：
#: 那条守卫（`tests/auth/test_passwords.py` 钉住「生产缺省 ≥ 600 000」）读的是
#: 常量本身，与本脚本无关。
#:
#: **为什么这里可以用低值**（控制者裁定 100 000，实现者复核后**同意**，理由比
#: 「慢」更硬）：迭代次数保护的是**泄漏的哈希**不被离线爆破。而演示库的口令
#: 是**明文公开**的（上面那一行 + spec §13 + 脚本输出），故这里没有任何东西需要
#: 保护 —— 600 000 次迭代只会让 `demo.ps1` 慢 16 秒而换不到一点安全。
#: ⚠️ 实测口径：63 个账号（60 学生 + 3 教师）× 600 000 ≈ 19 s，
#: 而 `demo.ps1` 的 `elapsed` 哨兵阈值是 90 s、Plan 03 实测 43.96 / 48.37 s
#: （余量 1.86×）→ 加上 19 s 余量掉到 1.34×。100 000 则约 3 s。
#:
#: ⚠️ **自描述串让「低值的演示库」与「高值的生产库」可以共存**：
#: `hash_password` 把迭代次数写进串里（`pbkdf2_sha256$<iterations>$<salt>$<hash>`），
#: `verify_password` **先解析出那个数、再用它重算**，故演示库上的登录走 100 000、
#: 生产库上的登录走 600 000，两者都不需要环境变量对齐。
#: ⚠️ 而 uvicorn 那个进程**不设**本变量（`demo.ps1` 里没有它），故演示时经
#: `POST /api/auth/*/bind` 新绑的口令用的是**生产缺省 600 000** ——
#: 这正是「自描述串」那一格的价值：同一个库里两种迭代次数并存且都能校验。
DEMO_PBKDF2_ITERATIONS = 100_000

#: 演示库里**第一个管理员**的工号（Plan 05A Task 4）。
#:
#: ⚠️ **不是 `T0001`**（派单举的例子是「例如 `T0001` 陈国华」，实现者换成了 T0003，
#: 理由是一条实测出来的冲突）：`T0001` 是 `frontend/scripts/smoke.mjs` 全程用的
#: 那个**普通教师**身份，而管理员会**越过任教范围闸门**
#: （`deps.require_teaches_section` / `require_teaches_student` 对 `role='admin'`
#: 放行 —— 计划 §3.6 第 2 条）。于是「把 T0001 提成管理员」会让 smoke 第 7 步的
#: 两拍**由红变绿假象**：
#:   · 「学生 4 不在 T0001 本学期任教的班里 → 403」会变成 **200**（管理员越过了闸门）；
#:   · 「教师侧 /home 对不任教的学生 → 403」同理。
#: 那两拍钉的是**闸门本身**，不是「T0001 这个人」，故正确的处置是让 smoke 继续用
#: 一个 `role='teacher'` 的工号验闸门、另用一个 `role='admin'` 的工号验管理台。
#:
#: ⚠️ 取 `T0003` 而不是 `T0002`：`app.seed.sections.make_sections` 按
#: `teachers[index % len(teachers)]` 轮转发班，60 人 / 3 教师的演示库里
#: 行政班01 → T0001、行政班02 → T0002、行政班03 → T0003。smoke 第 2 步取的是
#: `GET /api/course-sections?limit=5` 的**第一行**（= 行政班01，T0001 的班），
#: 第 8 步的大屏也读它 —— 故 T0001 必须**继续带班**且保持 `role='teacher'`。
#: T0003 带不带班对 smoke 都不重要（它只被用来做管理台的写入）。
DEMO_ADMIN_STAFF_NO = "T0003"

#: ``role`` 那一列上「管理员」的字面值。
#:
#: ⚠️ **本处刻意写字面量、不 import 既有住址**：那一个字面值今天有两个所有者
#: （:attr:`app.db.models.organisation.Teacher.ROLES` 与
#: :data:`app.api.deps.ADMIN_ROLE`）。从一个演示脚本 import ``app.api.deps``
#: 会新加一条 ``scripts → app.api`` 的边，而
#: ``tests/architecture/test_layering.py`` 是 AST 扫 ``backend/`` 下**全部** ``.py``
#: 的（含 ``scripts/``，实测 130 = app 82 + tests 47 + scripts 1）——
#: 为一个字面值去动依赖图不值。
#: ⚠️ 而「写死」的风险由下面 :func:`main` 里那一行**显式断言**顶住：
#: 词表变了（``Teacher.ROLES`` 不再有 ``"admin"``）就当场响，不会静默地
#: 造出一个「role 是一个没人认识的值」的教师行。
DEMO_ADMIN_ROLE = "admin"

#: 演示的业务日期（**周日**，理由见模块 docstring 第三节）。
#:
#: ⚠️ **它不能太早**，两个下界各有一条理由，都是实测撞出来的：
#:
#: * ``>= 开学日 + 2 周``（即 ``>= 2025-09-15``，实取 4 周后的那个周日）：
#:   :func:`app.demo_data._class_sessions_and_rpe` 对
#:   ``session_date < semester.start_date`` 的周**跳过**（「学期还没开学，那天不可能有课」），
#:   而 ``RED_RPE_SUSTAINED`` 的判据是「连续 **3** 次课堂快评 RPE ≥ 9」。
#:   取 ``2025-09-14``（开学后第 2 周的周日）实测只剩 2 个教学周 → 每个学生 2 条快评
#:   → streak 恒 ≤ 2 → **一条预警都不触发**，演示库里教师端的预警队列是空的。
#: * ``>= 开学日 + 5 周``：:func:`app.demo_data._mini_tests` 取「最近的偶数周」，
#:   而 ``RED_MINITEST_DROP`` 要 **3** 个数据点（spec §8.2 的补齐口径 #2）。
#:   开学后第 6 周才有 6 / 4 / 2 三个偶数周。
#:
#: ``2025-10-12`` 同时满足两条：它是学期 ``2025-2026-1``（开学日 2025-09-01，周一）
#: 的**第 6 周的周日**（``semester_week_of`` 给 6），往前 4 个教学周的课次
#: （10-12 / 10-05 / 09-28 / 09-21）**全部落在学期区间内**。
DEMO_AS_OF = dt.date(2025, 10, 12)

#: **处方生成日相对演示日的偏移天数**（6 天）：:data:`DEMO_RX_AS_OF` =
#: :data:`DEMO_AS_OF` 前 6 天，也就是它那个报表周的**周一**。
#:
#: 它是 I2 那次「跑两次 ``run_daily``」的第一次的业务日期，存在的理由逐字见
#: 模块 docstring 第四节。⚠️⚠️ **它受两个约束，改 :data:`DEMO_AS_OF` 的人必须回头核**：
#:
#: 1. ``0 <= 偏移 <= 6``——否则
#:    :func:`~app.domain.prescription.weekly.current_week` 在 ``DEMO_AS_OF`` 那天
#:    会算出第 2 周（甚至越界返回 ``None``），而演示数据只覆盖第 1 周的训练日；
#: 2. ``DEMO_RX_AS_OF + {0, 1, 2, 3}`` 全部是**工作日**（周一到周四）——
#:    18 套模板的 ``AssembledSession.day`` 恒为 ``1..N`` 连续，故训练日就是
#:    「生成日往后数 N 天」；而 :mod:`app.demo_data` 按
#:    ``log_date.weekday() >= 5`` 判休息日、:func:`_counted_checkin_days`
#:    把休息日从分子里剔掉。**取 6 而不是 5** 就是为了让 4 天的那一档
#:    （周一到周四）也全是工作日；取 4 会让训练日撞上周六、取 3 撞上周日。
#:
#: ⚠️ ``DEMO_AS_OF`` 是周日，故「前 6 天」恒为周一，两个约束同时满足。
#: ⚠️ 守卫是 :func:`main` 复核段的 ``offenders``（三层完成率全 0 → 当场报警 + 返回 1）。
DEMO_RX_OFFSET_DAYS = 6


def rx_as_of_of(as_of: dt.date) -> dt.date:
    """``as_of`` 对应的**处方生成日** = 它前 :data:`DEMO_RX_OFFSET_DAYS` 天。

    ⚠️ 提成一个函数是为了让「那个偏移」只有**一个**住址：:data:`DEMO_RX_AS_OF`
    与 ``--as-of`` 被改过时的实际取值都走它，否则两处各写一个 ``timedelta`` 迟早漂。
    两个约束逐字见 :data:`DEMO_RX_OFFSET_DAYS` 的注释。
    """
    return as_of - dt.timedelta(days=DEMO_RX_OFFSET_DAYS)


#: ``DEMO_AS_OF`` 那一次演示默认的处方生成日（``--as-of`` 被改过时由
#: :func:`rx_as_of_of` 现场算，故本常量只是缺省值的展示）。
DEMO_RX_AS_OF = rx_as_of_of(DEMO_AS_OF)

#: 演示库用的学期名。⚠️ ``seed_database`` 写**两条** ``Semester``
#: （``2024-2025-1`` 与 ``2025-2026-1``），故一律按**名字**取、不用
#: ``scalar(select(Semester))``（不带 ``order_by`` 的 ``scalar`` 实测取到先插入的上学年）。
DEMO_SEMESTER = "2025-2026-1"


def _parse_args(argv: "list[str] | None") -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="demo_bootstrap",
        description="把演示库灌好（组织结构 + 体测 CSV + 反馈三源 + 两次每日批处理）",
    )
    parser.add_argument("--db-url", required=True,
                        help="SQLite 的 URL，例如 sqlite:///C:/…/backend/pe_demo.db")
    parser.add_argument("--csv-dir", required=True, type=pathlib.Path,
                        help="三份乐跑 CSV 的落地目录（**不得**是 backend/data/seed/）")
    parser.add_argument("--students", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20250828)
    parser.add_argument("--as-of", type=dt.date.fromisoformat, default=DEMO_AS_OF)
    # ⚠️ 缺省是**演示值** :data:`DEMO_PBKDF2_ITERATIONS`（100 000），不是生产缺省
    #    600 000。理由逐字见那个常量的注释（演示口令是明文公开的，故迭代次数
    #    在这里保护不了任何东西，而 600 000 会让 63 个账号多花约 16 秒）。
    #    要一份生产强度的演示库就显式传 `--pbkdf2-iterations 600000`。
    parser.add_argument("--pbkdf2-iterations", type=int, default=DEMO_PBKDF2_ITERATIONS,
                        help=f"绑定演示口令时 PBKDF2 的迭代次数（缺省 {DEMO_PBKDF2_ITERATIONS}，"
                             f"⚠️ 生产缺省是 600000；见 DEMO_PBKDF2_ITERATIONS 的注释）")
    return parser.parse_args(argv)


def main(argv: "list[str] | None" = None) -> int:
    args = _parse_args(argv)

    # ⚠️ 两个禁区的前置守卫：**响亮失败**而不是写进去再让人去查
    #    （``backend/data/seed/`` 恒为 0 文件、``backend/pe.db`` 不得存在）。
    # ⚠️⚠️ 两道都比 Plan 03 Task 9 那版**宽**（终审的 M2）：
    #    * ``--csv-dir`` 从「等于禁区目录」改成「等于**或落在里面**」——
    #      原口径下 ``--csv-dir backend/data/seed/2025`` 会一路放行，而禁区那条纪律是
    #      「``backend/data/seed/`` 恒为 0 文件」，子目录里的文件同样是破禁区；
    #    * ``--db-url`` 从「串以 ``pe.db`` 结尾」改成「用 :func:`make_url` 剥出数据库
    #      文件路径、``resolve()`` 之后做**大小写无关**比较」——原口径有两个洞：
    #      Windows 上 ``…/PE.DB`` 与 ``…/Pe.Db`` 是同一个文件而 ``endswith`` 认不出来；
    #      反过来 ``…/somepe.db`` 会被它误伤（那一档今天恰好无害，但它说明判据选错了）。
    #      ⚠️ 仍然**保留**「basename 恰好是 ``pe.db`` 就拒」这一支：禁区外的同名文件
    #      本来不该管，但那是一个几乎必然是手误的输入，宁可多拒一次。
    forbidden_csv = (BACKEND / "data" / "seed").resolve()
    csv_dir = args.csv_dir.resolve()
    if csv_dir == forbidden_csv or csv_dir.is_relative_to(forbidden_csv):
        raise SystemExit(
            f"--csv-dir 不得是 {forbidden_csv} 或它下面的子目录（本仓禁区，恒为 0 文件）；"
            f"请用一个临时目录或 backend/ 之外的路径"
        )
    forbidden_db = os.path.normcase(str((BACKEND / "pe.db").resolve()))
    database = make_url(args.db_url).database
    db_basename = "" if database is None else pathlib.Path(database).name
    if db_basename == "pe.db" or (
        database and os.path.normcase(str(pathlib.Path(database).resolve())) == forbidden_db
    ):
        raise SystemExit(
            f"--db-url 指向 {args.db_url}（数据库文件 {database!r}），"
            f"而 backend/pe.db 是本仓禁区（不得存在）；"
            f"演示库请走 app.main.DEMO_DB_URL（backend/pe_demo.db）"
        )

    cfg = SeedConfig(students=args.students, weeks=16, seed=args.seed)
    args.csv_dir.mkdir(parents=True, exist_ok=True)
    # ⚠️ 处方生成日跟着 --as-of 走（唯一所有者是 :func:`rx_as_of_of`，两个约束见
    #    :data:`DEMO_RX_OFFSET_DAYS` 的注释）。
    rx_as_of = rx_as_of_of(args.as_of)

    print(f"[1/7] write_csv(build_dataset({args.students} 人 / 16 周 / seed={args.seed})) "
          f"-> {args.csv_dir}")
    write_csv(build_dataset(cfg), args.csv_dir)

    print(f"[2/7] init_db + seed_database -> {args.db_url}")
    engine = create_engine(args.db_url)
    init_db(engine)
    with Session(engine) as session:
        seed_database(session, cfg)
        session.commit()
        semester_id = session.scalar(
            select(Semester.id).where(Semester.name == DEMO_SEMESTER)
        )
    if semester_id is None:
        raise SystemExit(f"seed_database 没有写出学期 {DEMO_SEMESTER!r}")

    # ⚠️⚠️ 第一次 run_daily 的唯一目的是**把处方的 generated_on 钉在演示日之前**
    #    （I2，理由逐字见模块 docstring 第四节）。它跑在三源全空的库上，故预警与
    #    周报两个阶段都是空转（那一天也不是周日）；⚠️ 而 ``now`` 必须注入成
    #    **那一天**的业务时刻（I1）：不注入的话它会落进真实时钟，而重放路径上
    #    「真实时钟」与任何历史报表周都不相交。
    print(f"[3/7] run_daily({rx_as_of.isoformat()}) —— 处方生成日（I2 的第一次）")
    with Session(engine) as session:
        rx_run = run_daily(
            session, semester_id, rx_as_of.isoformat(),
            MockLePaoAdapter(args.csv_dir), now=business_now(rx_as_of),
        )
        session.commit()
        session.refresh(rx_run)
    print(f"       status={rx_run.status} 处方 {rx_run.prescription_count} 张  "
          f"预警 {rx_run.alert_count} 条（三源还空着，应当是 0）")
    if rx_run.status != "success":
        print(f"       ⚠️ error_summary: {rx_run.error_summary}")

    print(f"[4/7] build_demo_feedback(as_of={args.as_of.isoformat()}) —— 反馈三源")
    with Session(engine) as session:
        demo = build_demo_feedback(session, cfg=cfg, as_of=args.as_of)
        session.commit()
    print(f"       batch_id={demo.batch_id} class_session={demo.class_sessions} "
          f"rpe_record={demo.rpe_records} training_log={demo.training_logs} "
          f"mini_test={demo.mini_tests}")

    print(f"[5/7] run_daily({args.as_of.isoformat()}) —— 九个阶段")
    with Session(engine) as session:
        run = run_daily(
            session, semester_id, args.as_of.isoformat(),
            MockLePaoAdapter(args.csv_dir), now=business_now(args.as_of),
        )
        session.commit()
        session.refresh(run)
    print(f"       status={run.status} 抽取 体测/体成分/问卷 = "
          f"{run.extracted_fitness}/{run.extracted_body_comp}/{run.extracted_survey} "
          f"剔除 {run.dropped_count} 修正 {run.corrected_count}")
    print(f"       分层 红/黄/绿/数据不足 = {run.red_count}/{run.yellow_count}/"
          f"{run.green_count}/{run.insufficient_count}  肌肉量缺线组 {run.muscle_line_gaps}")
    # ⚠️ 本批新生成的处方**是 0**：处方是 [3/7] 那一批生成的，这一批一个触发都没命中
    #    （分层标签没变、处方也没到期）。那不是失败，故与库里的总数分开报（见 [7/7]）。
    print(f"       本批新生成处方 {run.prescription_count} 张（处方生成日是 "
          f"{rx_as_of.isoformat()}，见 [3/7]）  预警 {run.alert_count} 条")
    if run.status != "success":
        print(f"       ⚠️ error_summary: {run.error_summary}")

    # -----------------------------------------------------------------------
    # [6/7] 绑定演示口令 + 造出第一个管理员（Plan 05A Task 4）
    # -----------------------------------------------------------------------
    # ⚠️ **本步是「演示库上有人能登录」的全部前提**（:data:`DEMO_PASSWORD` 的注释）。
    # ⚠️ 哈希一律走 :func:`app.auth.passwords.hash_password`（**单一所有者**）：
    #    自描述串的形状（``pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>``）、
    #    盐的 CSPRNG 来源、迭代次数的取值口径都在那一个函数里。
    #    本脚本**不自己算**：一份手写的 ``hashlib.pbkdf2_hmac(...)`` 会在
    #    「换算式」那一天静默地与 ``verify_password`` 漂开。
    # ⚠️ 迭代次数经**环境变量**注入（``iterations()`` 在**调用时**读它），
    #    故本步只影响这一个进程；``demo.ps1`` 起的 uvicorn 仍然是生产缺省 600 000。
    print(f"[6/7] 绑定演示口令（--pbkdf2-iterations={args.pbkdf2_iterations}，"
          f"⚠️ 生产缺省是 600000）+ 造出第一个管理员")
    os.environ[PBKDF2_ITERATIONS_ENV_VAR] = str(args.pbkdf2_iterations)
    # ⚠️ 词表断言（:data:`DEMO_ADMIN_ROLE` 的注释）：写死的字面值必须仍然是
    #    ``teacher.role`` 的合法取值，否则下面那一行会造出一个「role 没人认识」的行
    #    ——而 DB 的 ``ck_teacher_role`` 会把它挡成 IntegrityError，报错在离真因
    #    很远的一格上（一句 SQLite 原文）。
    if DEMO_ADMIN_ROLE not in Teacher.ROLES:
        raise SystemExit(
            f"DEMO_ADMIN_ROLE={DEMO_ADMIN_ROLE!r} 不在 Teacher.ROLES={sorted(Teacher.ROLES)} 里"
        )
    # ⚠️ naive：库里那几个 DateTime 列存的就是 naive 本地时刻，而
    #    :func:`app.pipeline.daily.business_now` 逐字返回 naive（它的 docstring 第三节）。
    bound_at = business_now(args.as_of)
    with Session(engine) as session:
        students = session.scalars(select(Student)).all()
        teachers = session.scalars(select(Teacher)).all()
        # ⚠️ **在 commit 之前**把要打印的那几格摘成**普通值**：`commit()` 会 expire
        #    全部实例，而 `with Session(...)` 一退出它们就 detached —— 那时再读
        #    `t.staff_no` 抛的是 `DetachedInstanceError`（实测踩过一次：报错在
        #    一行 `print` 的 f-string 里，离真因「ORM 实例的生命周期」隔了两层）。
        teacher_staff_nos = [t.staff_no for t in teachers]
        student_nos = [s.student_no for s in students]
        for row in students:
            row.password_hash = hash_password(DEMO_PASSWORD)
            row.password_bound_at = bound_at
        for row in teachers:
            row.password_hash = hash_password(DEMO_PASSWORD)
            row.password_bound_at = bound_at
        admin = next(
            (t for t in teachers if t.staff_no == DEMO_ADMIN_STAFF_NO), None
        )
        if admin is None:
            # ⚠️ 响亮失败而不是静默跳过：没有管理员的演示库上，管理台的 26 个写入
            #    操作一律 403，而那一档看起来像「前端坏了」（Plan 05A Task 2 的
            #    三拍里「普通教师 403」与「前端忘了带会话」长得一样）。
            raise SystemExit(
                f"演示库里没有工号 {DEMO_ADMIN_STAFF_NO!r} 的教师"
                f"（实有 {[t.staff_no for t in teachers]}）："
                f"改 DEMO_ADMIN_STAFF_NO 或 --students/--teachers 的配置"
            )
        admin.role = DEMO_ADMIN_ROLE
        session.commit()
        student_bound = int(session.scalar(
            select(func.count()).select_from(Student).where(Student.password_hash.is_not(None))
        ))
        teacher_bound = int(session.scalar(
            select(func.count()).select_from(Teacher).where(Teacher.password_hash.is_not(None))
        ))
        admin_rows = session.execute(
            select(Teacher.staff_no, Teacher.name, Teacher.role)
            .where(Teacher.role == DEMO_ADMIN_ROLE)
            .order_by(Teacher.staff_no)
        ).all()
    print(f"       已绑定 学生 {student_bound} 人 / 教师 {teacher_bound} 人")
    print(f"       ⚠️⚠️ 演示口令（**公开**，spec §13 也记着它）：{DEMO_PASSWORD}")
    # ⚠️ 学号那一格的例子**从库里取**（与下一行的教师工号同构，终审 I1）：
    #    本处此前硬编码了 `2025010004`，而演示库的名册是 `app.seed.population`
    #    按「入学年 + 院系 + 序号」现造的，那串**从来不在册** → 照着它登录是
    #    403 password_not_bound（而那句 403 说的是「不在名册上」，会把人支去查后端）。
    #    学号由 `--students` / `--seed` 决定，故任何字面量都会在下次改配置时变假。
    print(f"          学生：任何一个在册学号（{len(student_nos)} 个，例如 {student_nos[0]}）"
          f"+ 上面这一串 → POST /api/auth/login")
    print(f"          教师/管理员：任何一个工号（{', '.join(teacher_staff_nos)}）+ 上面这一串")
    print(f"       管理员（role='admin'，管理台 26 个写入操作仅它可用）：{admin_rows}")
    print(f"       ⚠️ 迭代次数是**演示值** {args.pbkdf2_iterations}"
          f"（生产缺省 600000）；串是自描述的，故两种值可以在同一个库里并存")

    print("[7/7] 复核（全部从库里数出来，不是自报）")
    with Session(engine) as session:
        def count(model) -> int:
            return int(session.scalar(select(func.count()).select_from(model)))

        rows = [
            ("semester", count(Semester)), ("student", count(Student)),
            ("course_section", count(CourseSection)), ("enrollment", count(Enrollment)),
            ("prescription", count(Prescription)),
            ("weekly_adjustment", count(WeeklyAdjustment)),
            ("class_session", count(ClassSession)), ("rpe_record", count(RpeRecord)),
            ("training_log", count(TrainingLog)), ("mini_test", count(MiniTest)),
            ("alert", count(Alert)), ("notification", count(Notification)),
            ("weekly_class_report", count(WeeklyClassReport)),
        ]
        by_rule = dict(
            session.execute(
                select(Alert.rule_id, func.count(Alert.id)).group_by(Alert.rule_id)
            ).all()
        )
        needs_review = int(session.scalar(
            select(func.count()).select_from(Prescription).where(
                Prescription.status == "needs_review"
            )
        ))
        generated_on = sorted({
            str(day) for day in session.scalars(
                select(Prescription.generated_on)
            ).all()
        })
        # ⚠️ 两个 JSON 列**逐行读回来**（不是自报）：它们是 I1 / I2 两个修复的
        #    验收面，也是下面 ``offenders`` 那三格的输入。
        report_rows = session.execute(
            select(
                WeeklyClassReport.course_section_id,
                WeeklyClassReport.checkin_rate_by_layer,
                WeeklyClassReport.alert_summary,
                WeeklyClassReport.suggestion,
            ).order_by(WeeklyClassReport.course_section_id)
        ).all()
    for name, value in rows:
        print(f"       {name:22s} {value}")
    print(f"       预警按规则            {by_rule}")
    print(f"       处方 generated_on     {generated_on}"
          f"（⚠️ 应当**早于** --as-of={args.as_of.isoformat()}，否则报表窗口里"
          f"「<= as_of 的训练日」只有 as_of 一天、而那一天是周日=休息日 → 三层完成率恒 0，"
          f"理由见模块 docstring 第四节）")
    for section_id, rates, summary, suggestion in report_rows:
        three = {
            layer: (rates.get(layer) or {}).get("rate")
            for layer in ("red", "yellow", "green")
        }
        total = sum(sum(level.values()) for level in summary.values())
        print(f"       周报 班 {section_id}: 三层完成率 {three}  "
              f"预警汇总合计 {total}  建议「{suggestion}」")
    print(f"       处方 status=needs_review {needs_review}"
          f"（⚠️ 它只由「安全规则命中却找不到等价动作」置位；上面那批"
          f"「需要人工复核：addon … 的训练量未指定」的 warning 日志**不**改这一列，"
          f"它们说的是「教师需要用 VOLUME_SCALE 给附加模块定一个量」，"
          f"不是「这张处方不能执行」。两者的差别**已写进 spec §7.4**"
          f"（Plan 06 Task 13 结案；改前这一句写的是「已登记为待清扫」））")
    print(f"       站内消息              {rows[11][1]}"
          f"（⚠️ 两条 RED_* 规则**刻意不自动推送**：spec §8.2 逐字"
          f"「教师端弹『降量建议』→ 教师点击 → 推送『减量 20%』」。"
          f"演示时请在教师端点一次 POST /api/alerts/{{id}}/handle，"
          f"学生端的消息中心会再多一条；而 GREEN_MASTERY 的电子勋章与"
          f" YELLOW_CHECKIN_GAP 的补练提醒是**自动**推的，本数字里已经含它们）")
    # ⚠️ 六个「演示有没有东西可看」的判据：少了任何一个，浏览器点起来就是空的。
    #    后三个是 Plan 03 全分支终审之后加的（此前只有前三个，而它只检查「行数 > 0」，
    #    于是 11 条预警就让它通过了、一条警告都不打）。
    offenders = [
        why for why, ok in (
            ("一张处方都没有（分层全是 insufficient_data？）", rows[4][1] > 0),
            ("一条预警都没有（--as-of 太早？见 DEMO_AS_OF 的注释：课次要凑满 3 周）",
             rows[10][1] > 0),
            ("一份班级周报都没有（--as-of 不是周日？is_report_day 只在 weekday()==6 为真）",
             rows[12][1] > 0),
            # --- I2：三层完成率全 0 ------------------------------------------
            # ⚠️ 这一格挡的不是「算错了」而是「演示没东西可看」：rate 是 0.0 而
            #    measured == students 时，教师大屏读起来像「测过了、就是 0%」，
            #    而那违反本项目最响的那条纪律（「不知道」不得讲成「0」）。
            #    成因与修法逐字见模块 docstring 第四节（处方生成日必须早于 --as-of）。
            ("三层完成率全是 0/null（处方生成日没有早于 --as-of？见模块 docstring "
             "第四节与 DEMO_RX_OFFSET_DAYS 的两个约束）",
             bool(report_rows) and any(
                 (rates.get(layer) or {}).get("rate")
                 for _sid, rates, _sum, _sug in report_rows
                 for layer in ("red", "yellow", "green")
             )),
            # --- I2：notification 0 行 ---------------------------------------
            # 学生端消息中心空的 → POST /api/notifications/{id}/read 无从演示。
            ("notification 表 0 行（GREEN_MASTERY 与 YELLOW_* 都没触发？"
             "学生端消息中心会是空的）", rows[11][1] > 0),
            # --- I1：alert_summary 恒为 9 个 0 -------------------------------
            # ⚠️ 成因不是「演示口径、生产不可达」（本处此前逐字这么写，而那句对
            #    app.pipeline.backfill **不成立**：回放的语义逐字就是「把一学期的
            #    每个业务日都跑一遍」，每一个业务日都是历史日）。真正的原因是
            #    run_daily 的 now 此前不可注入 → alert.triggered_at 落在真实时钟上、
            #    与报表周那个历史窗口恒不相交。现已修（now 可注入 + 本脚本传
            #    business_now(as_of)），故这一格是它的守卫。
            ("weekly_class_report.alert_summary 全是 0（run_daily 的 now 没有注入成 "
             "as_of 派生的时刻？见 app.pipeline.daily.business_now）",
             bool(report_rows) and any(
                 sum(level.values()) > 0
                 for _sid, _rates, summary, _sug in report_rows
                 for level in summary.values()
             )),
            # --- Plan 05A Task 4：演示库上得有人能登录 -------------------------
            # ⚠️ 这两格挡的不是「算错了」而是「演示跑不起来」：Plan 05A 之后身份走
            #    pe_session cookie，而 cookie 只能由 POST /api/auth/login 种下、
            #    登录又要 password_hash 非空。少了 [6/7] 那一步的话，前端每一个页面
            #    都会被路由守卫弹回 /login（看起来像「前端坏了」），而管理台的
            #    26 个写入操作一律 403（看起来像「Task 2 改坏了」）。
            #    ⚠️ 判据用**相等**而不是 > 0：只绑了 3 个学生的演示库上，
            #    「随手挑一个学号登录」有 95% 的概率失败，而那看起来像口令错了。
            (f"[6/7] 没有把口令绑全（学生 {student_bound}/{rows[1][1]}、"
             f"教师 {teacher_bound}）：演示库上会有人登录不进去",
             student_bound == rows[1][1] and student_bound > 0 and teacher_bound > 0),
            ("[6/7] 一个 role='admin' 的教师都没有（管理台的 26 个写入操作会一律 403；"
             "DEMO_ADMIN_STAFF_NO 打错了？）", len(admin_rows) >= 1),
        ) if not ok
    ]
    if offenders:
        for why in offenders:
            print(f"       ⚠️ {why}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

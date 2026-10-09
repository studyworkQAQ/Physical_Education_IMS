"""反馈三源的**演示数据**生成器（⚠️ 它不是、也永远不得接进 ``seed_database``）。

Plan 04 的前端要有东西可显示，而 Plan 03 Task 5–9 的采集端点与管道阶段还没落地；
本模块给一个已经 ``seed_database`` 过的库补上 §4.5「反馈三源」里**能离线造出来**的那
四张表：``class_session`` / ``rpe_record`` / ``training_log`` / ``mini_test``。

----------------------------------------------------------------------------
为什么它是一个独立入口，而不是 ``seed_database`` 的一段
----------------------------------------------------------------------------

``tests/seed/test_generate.py`` 有一对守卫：``DATA_TABLES + REFERENCE_TABLES`` 里的表
在 ``seed_database`` 之后必须 **0 行**（``seed_database`` 只写组织结构五张表），
而三个分区必须恰好穷尽 ``Base.metadata``。Plan 03 Task 2 把那 7 张新表全归进了
``DATA_TABLES``（11 → 18），于是「演示数据由 ``seed_database`` 灌」这条路**当场被堵死**。

这与 Plan 02 的 P2-A1 / P3-A1 是同一条纪律：``sync_exercises`` / ``sync_templates``
也不许接进 ``seed_database``（另一条理由是 Global Constraint #10——``app/seed/`` 自
Plan 01 结案后重新冻结）。守卫是
``tests/test_demo_data.py::test_seed_database_still_writes_no_feedback_rows``。

----------------------------------------------------------------------------
刻意**不**造的三张表
----------------------------------------------------------------------------

``alert`` / ``notification`` / ``weekly_class_report`` 一行都不写。它们是 Task 7 / 8 / 9
那三个引擎的**产物**，而演示数据里伪造它们有两个具体坏处：

1. **撞去重键**：``alert`` 上有
   ``UniqueConstraint("rule_id", "subject_key", "semester_id", "window_key")``，
   伪造的行会占掉真实引擎要写的那些键，于是 ``alert_stage`` 第一次真跑就
   ``IntegrityError``——而报错的地方离「谁先写了这行」很远；
2. **让「跑通了」变成假象**：本计划的验收是「预警 → 减量 20% → 学生端看到更新后的
   训练单」这条闭环真的跑通。演示数据里预置好 ``alert`` 与 ``notification``，
   演示时就分不清那条预警是算出来的还是造出来的。

反过来，本模块造的四张表正是那三个引擎的**输入**：造出「某些学生连续三次 RPE ≥ 9」
与「某些学生连续两天没打卡」，Task 7 的 ``RED_RPE_SUSTAINED`` 与 ``YELLOW_CHECKIN_GAP``
才有东西可触发（守卫是
``tests/test_demo_data.py::test_demo_feedback_gives_the_alert_engine_something_to_fire_on``）。

----------------------------------------------------------------------------
三条口径
----------------------------------------------------------------------------

* **时钟由调用方注入**：``as_of`` 是唯一的时间来源，本模块**一次都不读时钟**
  （Global Constraint #1）。全部日期都由 ``as_of`` 与 ``semester.start_date`` 减出来。
  源码级守卫是 ``tests/test_demo_data.py::test_demo_data_never_touches_the_clock``。
* **随机数只有一个入口**：``np.random.default_rng(cfg.seed)``，同种子同输出。
  ``cfg`` 在本模块只用到 ``cfg.seed`` 这一项——学生、教学班、选课关系一律**从库里读**，
  不按 ``cfg.students`` 重造（造第二遍就是第二个所有者，而且会与 ``seed_database``
  写出的组织结构对不上）。
* **幂等靠自然键 upsert**：四张表各按自己的唯一约束走 :func:`app.db.repo.upsert`，
  故跑两次行数不变（守卫是 ``test_build_demo_feedback_is_idempotent``）。
  ⚠️ 这正是 ``class_session`` 需要那条 ``UniqueConstraint`` 的原因：``upsert`` 是
  「先 select 再 update/insert」，没有 DB 兜底时两个写入方会各插一行，
  而下一次 select 撞上 ``MultipleResultsFound``——炸在读侧。
* **不 commit**：与 ``seed_database`` / ``repo.upsert`` 同一口径，事务边界由调用方掌握，
  「整批失败回滚」才成立。

⚠️ ``mini_test.normalized_score`` 写的是**演示口径的近似值**，不是 spec §8.1 那个
「折返得分 = 该教学班内折返秒数的百分位反查」的真算法——那要读整个教学班的行，
是 spec §5 第 7 阶段（Aggregate）的活。近似式与它的出处写在下面那一列的注释里。
"""
import datetime as dt
from dataclasses import dataclass

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import repo
from app.db.models.feedback import ClassSession, MiniTest, RpeRecord, TrainingLog
from app.db.models.organisation import CourseSection, Enrollment, Semester, Student, Teacher
from app.db.models.ops import DailySyncRun
from app.seed.config import SeedConfig

__all__ = ["DemoReport", "build_demo_feedback"]

# ---------------------------------------------------------------------------
# 规模旋钮（本模块是它们的唯一所有者；改这里就改了演示数据的量）
# ---------------------------------------------------------------------------

#: 造最近几个教学周的课次（每周每班一节）。4 周 ≈ 1.5 个月的课。
#: ⚠️ 至少要 **3**：``RED_RPE_SUSTAINED`` 的判据是「连续 3 次课堂快评 RPE ≥ 9」
#: （spec §8.2 的补齐口径 #1），少于 3 节课那条规则在演示库里永远触发不了。
DEMO_SESSION_WEEKS = 4

#: 每节课的节次。固定值而不是随机： ``(course_section_id, session_date, period)``
#: 是 ``class_session`` 的唯一键，随机节次会让「同一节课」在两次运行里落到不同的键上，
#: 幂等就没了。
DEMO_PERIOD = 3

#: 造最近几天的每日打卡。⚠️ 至少要 **3**：``YELLOW_CHECKIN_GAP`` 的判据是
#: 「连续 2 个应打卡训练日未打卡」（spec §8.2 的补齐口径 #3），
#: 再加上「中断结束的那一天」，3 天才凑得出一段可判的中断。
DEMO_CHECKIN_DAYS = 14

#: 最多造几次二次小测（取最近的偶数周）。⚠️ 至少要 **3**：``RED_MINITEST_DROP``
#: 要 3 个数据点才能判「连续两次下降 ≥ 5%」（spec §8.2 的补齐口径 #2）。
DEMO_MINI_TESTS = 4

#: 造进 ``training_log.source`` 的值。⚠️ 那一列今天**没有唯一所有者**
#: （见 ``TrainingLog.source`` 的列注释），``"demo"`` 因此还兼着一个用处：
#: 一眼能认出哪些行是演示数据、哪些是 Task 5 的采集端点写的。
DEMO_SOURCE = "demo"

#: 二次小测的测试项组合（spec §8.1 的指导文件给的就是这两项）。
DEMO_ITEM_COMBO = ("squat_30s", "shuttle_20m")

#: 每 ``HIGH_RPE_EVERY`` 个学生里挑一个造「持续高 RPE」，让红色的那条规则有东西可触发。
#: 取模而不是抽样：抽样会让「谁被挑中」依赖随机流的消耗顺序，而取模是纯函数，
#: 于是 ``test_demo_feedback_gives_the_alert_engine_something_to_fire_on`` 的
#: 「至少有一个学生连续 ≥ 3 次 RPE ≥ 9」这句断言不可能因为换了种子而落空。
HIGH_RPE_EVERY = 10

#: ``RED_RPE_SUSTAINED`` 的阈值（spec §8.2：RPE 连续 ≥ **9**）。
#: ⚠️ 这里的 9 是**演示数据要跨过的门槛**，不是阈值的第二个所有者——
#: 阈值本身归 ``backend/data/alert_rules.yaml``（Task 6）。本模块只是要保证
#: 造出来的数据里有跨过它的样本，否则演示库里那条规则永远不触发。
HIGH_RPE_FLOOR = 9

#: 每 ``LATE_EVERY`` 天造一条 ``late = True`` 的打卡（spec §8.1：22:00 后提交仍入库、
#: 但不计入当日完成）。同样取模而不是抽样，理由见 :data:`HIGH_RPE_EVERY`。
LATE_EVERY = 7

#: 一节课的上课时刻与快评的提交基准时刻（10:30）。
DEMO_CLASS_HOUR = 10
DEMO_CLASS_MINUTE = 30


def _at(day: dt.date, hour: int, minute: int, second: int = 0) -> dt.datetime:
    """把日期与时分秒拼成 ``datetime``。

    ⚠️ 刻意**不用** ``dt.datetime.combine(day, dt.time(...))``：本模块被
    ``tests/test_demo_data.py::test_demo_data_never_touches_the_clock`` 按
    「调用的末段属性名」扫一遍，而那份判据里 ``time`` 是 ``time.time()`` 的替身
    （它抓的是**读时钟**），``dt.time(...)`` 会被同一个末段名误伤。
    直接调 ``dt.datetime(...)`` 构造器既等价、又不与那条守卫打架——
    本模块一个 ``.time`` / ``.now`` / ``.today`` 都不出现，于是那条守卫可以是
    一刀切的末段名判据，不必为「构造器 vs 时钟读取」再开一个例外。
    """
    return dt.datetime(day.year, day.month, day.day, hour, minute, second)


@dataclass(frozen=True)
class DemoReport:
    """:func:`build_demo_feedback` 的返回值：批次号 + 四张表跑完之后的**实际行数**。

    ⚠️ 四个计数是**从库里数出来的**（``select(func.count())``），不是「本函数写了几行」
    的自报。两者的区别正是幂等那条守卫要的东西：第二次调用时「本函数写了几行」是 0
    （全都命中已有行），而「库里有多少行」必须与第一次逐字相同——
    自报的计数会让 ``test_build_demo_feedback_is_idempotent`` 变成一个恒真的断言
    （两次都报 0，或两次都报同一个「打算写多少」的数）。
    """

    batch_id: int
    class_sessions: int
    rpe_records: int
    training_logs: int
    mini_tests: int


def _semester_of(session: Session, as_of: dt.date) -> Semester:
    """``as_of`` 落在哪个学期里。一个都落不进去就**响亮失败**。

    取 ``id`` 最大的那一个：``seed_database`` 写两个学期，区间不重叠，故至多一个命中；
    ``order_by(...).limit(1)`` 是为了让 ``session.scalar`` 在「哪天区间真的重叠了」
    的时候给出一个确定的答案，而不是 ``MultipleResultsFound``。
    """
    semester = session.scalar(
        select(Semester)
        .where(Semester.start_date <= as_of, Semester.end_date >= as_of)
        .order_by(Semester.id.desc())
        .limit(1)
    )
    if semester is None:
        raise ValueError(
            f"as_of={as_of.isoformat()} 不落在任何学期区间内，无从生成演示数据："
            "先跑 app.seed.generate.seed_database（它按 app.seed.config.SEMESTERS 建学期），"
            "或者把 as_of 挪进学期区间"
        )
    return semester


def _demo_batch(session: Session, semester: Semester, as_of: dt.date) -> int:
    """``as_of`` 那一天的 ``daily_sync_run`` 行，返回它的 ``id`` 当 ``batch_id`` 用。

    ⚠️ **演示数据必须有批次号**，因为 ``class_session.batch_id`` 与
    ``training_log.batch_id`` 都是 NOT NULL 的外键。走 ``repo.upsert`` 按
    ``(semester_id, business_date)``——那是 ``daily_sync_run`` 自己的唯一约束，
    故真实管道在 ``as_of`` 那天跑过（或将要跑）时，两边命中的是**同一行**，
    不会造出两个批次。

    ``status`` 显式写 ``"success"``：列上的缺省是 ``"failed"``（Ruling 30，
    保守方向），而演示批次是一次「跑完了」的写入。
    ⚠️ 计数列一律留缺省 0——本模块不假装自己抽取过任何源数据；
    ``alert_count`` 归 Task 7、``prescription_count`` 归 Plan 02 的处方阶段。
    """
    run = repo.upsert(
        session,
        DailySyncRun,
        ("semester_id", "business_date"),
        {
            "semester_id": semester.id,
            "business_date": as_of,
            "started_at": _at(as_of, 2, 0),
            "finished_at": _at(as_of, 2, 5),
            "status": "success",
        },
    )
    session.flush()  # 拿 id 当 batch_id 用（repo.upsert 的契约：insert 分支 flush 前 id 是 None）
    return run.id


def _week_of(semester: Semester, as_of: dt.date) -> int:
    """``as_of`` 是学期的第几周（1-based，与 ``mini_test.week`` 同口径）。"""
    return (as_of - semester.start_date).days // 7 + 1


def _class_sessions_and_rpe(
    session: Session, rng: np.random.Generator, semester: Semester,
    batch_id: int, as_of: dt.date, student_ids: list[int],
) -> None:
    """造课次与课堂快评（spec §4.5「课堂端」+ §8.1 的第一步）。

    只造**行政班**的课次：spec §8.1 的课堂快评发生在上课的教学班里，而分层班
    （提升班 / 强化班 / 拓展班）是阶段二跨班重编出来的，演示阶段拿行政班就够
    ``YELLOW_CLASS_RPE_HIGH``（作用域是「班级」）有东西可算。

    ⚠️ 快评只对**选了那个班的学生**造：``rpe_record`` 没有 ``course_section_id`` 列，
    它通过 ``class_session`` 归属到班，故给没选这个班的学生造快评会造出
    「一个不在这个班的人交了这节课的快评」——教师端的已提交名单于是会超过班级人数。
    """
    sections = session.scalars(
        select(CourseSection)
        .where(
            CourseSection.semester_id == semester.id,
            CourseSection.grouping_mode == "administrative",
        )
        .order_by(CourseSection.id)
    ).all()
    if not sections:
        raise ValueError(
            f"学期 {semester.name} 下没有行政班（grouping_mode='administrative'），"
            "无从造课次：先跑 seed_database"
        )

    # 选课名单一次性取出来：它不随周次变，放进周循环里就是 4 × 班数 次重复查询
    enrolled_by_section = {
        section.id: sorted(
            session.scalars(
                select(Enrollment.student_id).where(
                    Enrollment.course_section_id == section.id
                )
            ).all()
        )
        for section in sections
    }
    # 第 10、20、30… 号学生造「持续高 RPE」，让 RED_RPE_SUSTAINED 有东西可触发
    high_rpe = set(student_ids[::HIGH_RPE_EVERY])

    for week_offset in range(DEMO_SESSION_WEEKS):
        session_date = as_of - dt.timedelta(weeks=week_offset)
        if session_date < semester.start_date:
            continue  # 学期还没开学，那天不可能有课
        for section in sections:
            # 口令 8 位大写十六进制（``rpe_token`` 是 String(16)，余量 8）
            token = format(int(rng.integers(0, 16 ** 8)), "08x").upper()
            cs = repo.upsert(
                session,
                ClassSession,
                ("course_section_id", "session_date", "period"),
                {
                    "course_section_id": section.id,
                    "session_date": session_date,
                    "period": DEMO_PERIOD,
                    "rpe_opened": True,
                    "rpe_token": token,
                    "batch_id": batch_id,
                },
            )
            session.flush()
            for student_id in enrolled_by_section[section.id]:
                # 上界读 RpeRecord.RPE_MAX：值域的唯一所有者是那张表的类常量，
                # 这里不写第二份 10（P3-A5 要的正是这件事）
                if student_id in high_rpe:
                    rpe = int(rng.integers(HIGH_RPE_FLOOR, RpeRecord.RPE_MAX + 1))
                else:
                    rpe = int(rng.integers(4, HIGH_RPE_FLOOR))
                elapsed = round(float(rng.uniform(3.0, 25.0)), 1)
                repo.upsert(
                    session,
                    RpeRecord,
                    ("class_session_id", "student_id"),
                    {
                        "class_session_id": cs.id,
                        "student_id": student_id,
                        "rpe": rpe,
                        # 提交时刻 = 上课那天的 10:30 + 该生的答题耗时（spec §8.1 的
                        # 「10 秒内完成」因此有可看的对照：约一半的人超过 10 秒）
                        "submitted_at": _at(session_date, DEMO_CLASS_HOUR,
                                            DEMO_CLASS_MINUTE)
                        + dt.timedelta(seconds=elapsed),
                        "elapsed_seconds": elapsed,
                    },
                )
    session.flush()


def _training_logs(
    session: Session, rng: np.random.Generator, semester: Semester,
    batch_id: int, as_of: dt.date, student_ids: list[int],
) -> None:
    """造最近 :data:`DEMO_CHECKIN_DAYS` 天的每日打卡（spec §4.5「课外端」+ §8.1）。

    三档都要造出来，否则 Plan 04 的前端与 Task 7 的规则各有一档看不见：

    * **完成**（``completed=True``，有时长与感受）；
    * **未完成**（``completed=False``，时长与感受都是 ``NULL``——包约定 1：缺测是 NULL）；
    * **迟交**（``late=True``，每 :data:`LATE_EVERY` 天一条）。⚠️ 迟交与完成是**两件事**
      （``TrainingLog`` 的类 docstring）：``completed=True`` 且 ``late=True`` 是合法的，
      语义是「练了但交得晚，不计入当日完成」。
    * **休息日**（``is_rest_day=True``，周六周日）。

    中断（``YELLOW_CHECKIN_GAP`` 要的「连续 2 个应打卡训练日未打卡」）由「未完成」
    与「休息日」两档自然产生，不额外造：抽到 ``completed=False`` 的学生本来就成片出现。
    """
    for student_id in student_ids:
        for day_offset in range(DEMO_CHECKIN_DAYS):
            log_date = as_of - dt.timedelta(days=day_offset)
            if log_date < semester.start_date:
                continue
            is_rest_day = log_date.weekday() >= 5
            late = day_offset % LATE_EVERY == LATE_EVERY // 2
            completed = bool(rng.random() < 0.75)
            feeling = None
            duration = None
            if completed:
                duration = round(float(rng.uniform(20.0, 60.0)), 1)
                # 词表**读** ``TrainingLog.FEELINGS``、不在这里抄第二份（单一所有者）。
                # ``sorted`` 是为了让「第 n 个」有确定的含义：集合的迭代顺序不保证稳定，
                # 而本模块的契约是同种子同输出。
                feelings = sorted(TrainingLog.FEELINGS)
                feeling = feelings[int(rng.integers(0, len(feelings)))]
            repo.upsert(
                session,
                TrainingLog,
                ("student_id", "log_date"),
                {
                    "student_id": student_id,
                    "log_date": log_date,
                    "completed": completed,
                    "duration_min": duration,
                    "feeling": feeling,
                    "is_rest_day": is_rest_day,
                    "late": late,
                    "source": DEMO_SOURCE,
                    "batch_id": batch_id,
                },
            )
    session.flush()


def _mini_tests(
    session: Session, rng: np.random.Generator, semester: Semester,
    as_of: dt.date, student_ids: list[int], entered_by: str,
) -> None:
    """造最近 :data:`DEMO_MINI_TESTS` 个**偶数周**的二次小测（spec §4.5「阶段端」）。

    周次从学期周历算出来（``range(2, 本周 + 1)`` 里的偶数，取最后 N 个），
    与 spec §8.1「系统按学期周历自动算出应测周次（偶数周）」同一口径。

    ⚠️ ``normalized_score`` 是**演示口径的近似值**：spec §8.1 的真算法是
    「深蹲得分 = 次数；折返得分 = 该教学班内折返秒数的**百分位反查**；综合分 = 等权平均」，
    而班内百分位反查要读整个班的行、是 spec §5 第 7 阶段（Aggregate）的活。
    这里用 ``45.0 - 折返秒数`` 当折返得分的替身（同样是「越小越好」翻成「越大越好」），
    只为了让前端有一列可显示、且量级与真算法相当（两项都在 15–45 之间，均值 15–45）。
    **Task 9 落地真算法时要覆盖本列**，届时本函数仍是幂等的（upsert 会更新它）。
    """
    current_week = _week_of(semester, as_of)
    weeks = [w for w in range(2, current_week + 1) if w % 2 == 0][-DEMO_MINI_TESTS:]
    for week in weeks:
        tested_on = semester.start_date + dt.timedelta(weeks=week - 1, days=2)
        if tested_on > as_of:
            continue  # 那一周还没到，不该有成绩
        for student_id in student_ids:
            squat = int(rng.integers(15, 40))
            shuttle = round(float(rng.uniform(28.0, 45.0)), 1)
            repo.upsert(
                session,
                MiniTest,
                ("student_id", "semester_id", "week"),
                {
                    "student_id": student_id,
                    "semester_id": semester.id,
                    "week": week,
                    "item_combo": list(DEMO_ITEM_COMBO),
                    "squat_30s_count": squat,
                    "shuttle_20m_s": shuttle,
                    "normalized_score": round((squat + max(0.0, 45.0 - shuttle)) / 2, 2),
                    "tested_on": tested_on,
                    "entered_by": entered_by,
                },
            )
    session.flush()


def build_demo_feedback(
    session: Session, *, cfg: SeedConfig, as_of: dt.date
) -> DemoReport:
    """给一个**已经 ``seed_database`` 过**的库造反馈三源的演示数据，返回行数报告。

    ``cfg`` 只用到 ``cfg.seed``（随机数的种子）；学生、教学班、选课关系、学期一律
    **从库里读**——按 ``cfg.students`` 重造一遍人口就是第二个所有者，而且会与
    ``seed_database`` 写出的组织结构对不上。

    ``as_of`` 是唯一的时间来源（本模块不读时钟），语义是「演示到今天为止」：
    课次是它往前 :data:`DEMO_SESSION_WEEKS` 个教学周、打卡是它往前
    :data:`DEMO_CHECKIN_DAYS` 天、小测是它所在周往前 :data:`DEMO_MINI_TESTS` 个偶数周。

    **不 commit**（与 ``seed_database`` / ``repo.upsert`` 同口径）：调用方决定事务边界。
    **幂等**：四张表各按自己的唯一约束走 ``repo.upsert``，跑两次行数不变。

    库里没有组织结构时**响亮失败**（``ValueError``），不静默造出一个空报告：
    「跑了但一行都没写」与「没东西可写」在返回值上会长得一样，而前者是配置错了。
    """
    rng = np.random.default_rng(cfg.seed)
    semester = _semester_of(session, as_of)
    student_ids = sorted(
        session.scalars(
            select(Student.id)
            .where(
                Student.id.in_(
                    select(Enrollment.student_id).where(
                        Enrollment.semester_id == semester.id
                    )
                )
            )
        ).all()
    )
    if not student_ids:
        raise ValueError(
            f"学期 {semester.name} 下没有任何选课学生，无从造反馈数据：先跑 seed_database"
        )
    teacher_no = session.scalar(
        select(Teacher.staff_no).order_by(Teacher.id).limit(1)
    )
    if teacher_no is None:
        raise ValueError("库里没有教师，``mini_test.entered_by`` 无从填：先跑 seed_database")

    batch_id = _demo_batch(session, semester, as_of)
    _class_sessions_and_rpe(session, rng, semester, batch_id, as_of, student_ids)
    _training_logs(session, rng, semester, batch_id, as_of, student_ids)
    _mini_tests(session, rng, semester, as_of, student_ids, teacher_no)
    session.flush()

    def count(model) -> int:
        return int(session.scalar(select(func.count()).select_from(model)))

    return DemoReport(
        batch_id=batch_id,
        class_sessions=count(ClassSession),
        rpe_records=count(RpeRecord),
        training_logs=count(TrainingLog),
        mini_tests=count(MiniTest),
    )

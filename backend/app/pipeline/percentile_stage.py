"""百分位阶段：把 ``compute_snapshot`` 的产出**物化**进 ``percentile_snapshot``，以及从库里读回。

spec §4.0 规定百分位**必须物化为快照表、禁止实时计算**——实时算会随人群变动漂移，而研究
项目必须能复现任意一天的分层结果。本模块因此是全仓**唯一**写 ``percentile_snapshot`` 的地方，
也是 ``daily.py`` 读判定线的唯一入口。

它同时持有「从库里还原一个待判定队列」这一段（:func:`cohort_from_db`）：百分位阶段与
派生阶段必须看**同一批人、同一个锚点**，否则「P25 是在谁身上算的」与「P25 用在了谁身上」
会静默分叉。放在这里而不是 ``daily.py``，是因为 ``run_percentile`` 的签名由计划钉死
（``session, business_date, batch_id``），它得自己能把队列读出来；``daily.py`` 复用同一个
函数，两条路径因此不可能选出不同的锚点。

**算法一律复用 domain**：分位数只由 :func:`app.pipeline.run_stratify.cohort_snapshot`
（它又只调 :func:`app.domain.percentile.compute_snapshot`）算出，本模块不重算任何一遍。
"""
import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models
from app.domain.indicators import ScoredItem, Sex, age_group_of
from app.domain.percentile import PercentileRow, SnapshotMetric
from app.pipeline.extract import parse_business_date
from app.pipeline.run_stratify import (
    WEEK1_TIMEPOINT, YEAR_STEP, PersonInputs, cohort_snapshot, empty_scores,
)
from app.refdata import standard

__all__ = [
    "Anchor",
    "age_at",
    "assessment_anchor",
    "cohort_from_db",
    "current_semester_of",
    "load_snapshot",
    "needs_recompute",
    "run_percentile",
]


@dataclass(frozen=True)
class Anchor:
    """本次判定的锚点：**每学年的 ``week1``** 那两次体测（Ruling 140）。

    ``curr`` 是 ``<= business_date`` 的最新一个 ``week1`` 批次，``prev`` 是它前面那个。
    ``prev_*`` 为 ``None`` 表示这个人在库里没有上学年记录（新生、或回填还没跑到），
    此时 ``prev_scores is None`` → 趋势 ``INSUFFICIENT``、``annual_change = {}``——
    **合法状态**（Ruling 106），不是异常。
    """

    curr_batch_id: int | None
    prev_batch_id: int | None
    curr_date: dt.date | None
    prev_date: dt.date | None


def age_at(birth: dt.date, reference: dt.date) -> int:
    """``reference`` 那天的周岁年龄。

    与 ``app.seed.population.birth_date`` 严格互逆：生成器按
    ``BIRTH_REFERENCE_DATE = current_semester().start_date`` 把 ``age`` 折算成 ``birth``，
    本函数按同一个参考日折回来，故 ``age_at(birth, 当前学期开学日) == population["age"]``
    逐人成立（已由 ``tests/pipeline`` 的端到端趋势分布交叉验证间接钉住：龄组错一个，
    查的就是另一张评分表，趋势配额对不上）。
    """
    return (
        reference.year - birth.year
        - ((reference.month, reference.day) < (birth.month, birth.day))
    )


def current_semester_of(session: Session, as_of: dt.date) -> models.Semester:
    """「本学年」那个学期：优先 ``is_current``，退化到「包含 ``as_of`` 的那个」。

    它是龄组折算的参考系（Ruling 56：本学年用 ``age_group_of(age)``、上学年用
    ``age_group_of(age - 1)``），也是 ``years_back`` 的基准。找不到就响亮失败：
    静默退回「所有人的龄组都按本学年算」会让上学年的正查得分查错一张表，
    趋势差值带系统性偏差，而趋势是规则 Y4 的唯一输入。
    """
    semester = session.scalar(
        select(models.Semester).where(models.Semester.is_current.is_(True))
    )
    if semester is None:
        semester = session.scalar(
            select(models.Semester).where(
                models.Semester.start_date <= as_of, models.Semester.end_date >= as_of
            )
        )
    if semester is None:
        raise ValueError(
            f"找不到「本学年」的学期：库里没有 is_current=True 的 semester，"
            f"也没有包含 {as_of.isoformat()} 的学期区间。龄组折算与 years_back 都要以它为参考系，"
            f"缺了它只能静默按某一个学期算，那会让上学年的正查得分查错评分表"
        )
    return semester


def assessment_anchor(session: Session, as_of: dt.date) -> Anchor:
    """取 ``<= as_of`` 的最新两个 ``week1`` 批次（降序头两个）。

    **为什么锚在 ``week1`` 而不是「最新的一条体测」**（Ruling 140）：spec §6.3 的「连续两次
    体测」在真实产品里就是每年秋季那一次国标体测，``week8`` / ``week16`` 是学期内的过程
    测量（二次小测），归 spec §8.2 与 Plan 03。

    锚在 ``week1`` 还白得一条端到端交叉验证：这正是 Task 6 ``trend_label`` 的口径
    （Ruling 75② 明写「趋势判据只在 week1 上由构造保证」），于是跑完管道后的趋势分布
    **在零注入下精确等于**生成器的配额。本路径的守卫
    ``tests/pipeline/test_daily.py::test_trend_matches_the_generator_oracle_on_week1_anchors``
    量的正是这一组条件（``CLEAN_CFG``：``dirty`` 四项全 0）——60 人逐人对得上、分布恰好是
    ``allocate_quota(trend_mix, 60)`` = ``{持续下滑:12, 波动大:9, 稳步提升:15, 稳定:24}``。

    **它此前被写成不带条件的等式，那是漏了测量条件**（Ruling 149/153）：换成缺省注入
    （4% 逐项缺测，``seed=20250828``），``national_total`` 对 7 个计分项**全有或全无**，
    同一批 60 人实测 ``{insufficient_data:34, 稳定:11, 稳步提升:7, 持续下滑:4, 波动大:4}``，
    等式不成立（换 seed 时那个 34 会动：60 人的可判数实测在 21–33 之间，样本太小）。
    真不变量是**可判子集上的高一致率**（500 人缺省注入下 291 人可判、280 人一致 = 96.2%，
    数字与成因见 :func:`app.pipeline.run_stratify._from_dataset` 的 docstring）。

    ``WEEK1_TIMEPOINT`` 从 ``run_stratify`` 导入、**不在这里重写 ``"week1"`` 字面量**
    （Ruling 152）：「哪个 timepoint 是评估锚点」只能有一个所有者。此前这里是硬编码字面量、
    内存路径用常量，两处各自漂移时上面那条端到端守卫读的是**本路径**这一处、抓不到另一处
    （fix round 1 的变异 M3 实测：把 ``WEEK1_TIMEPOINT`` 改成 ``"week8"``，**当时那 418 条**
    测试里只有内存路径那条趋势测试红。**418 是当时的套件规模、不是现在的**——fix round 3
    是 428 条；这个数字本身不被守卫，它只是一次变异取证的记录）。现在守卫这道合流的是同一测试文件里的
    ``test_memory_path_and_db_path_agree_at_the_pinned_business_date``。
    """
    rows = session.execute(
        select(models.FitnessTestBatch.id, models.FitnessTestBatch.test_date)
        .where(
            models.FitnessTestBatch.timepoint == WEEK1_TIMEPOINT,
            models.FitnessTestBatch.test_date <= as_of,
        )
        .order_by(models.FitnessTestBatch.test_date.desc())
    ).all()
    curr = rows[0] if rows else None
    prev = rows[1] if len(rows) > 1 else None
    return Anchor(
        curr_batch_id=None if curr is None else curr[0],
        prev_batch_id=None if prev is None else prev[0],
        curr_date=None if curr is None else curr[1],
        prev_date=None if prev is None else prev[1],
    )


def _results_of(session: Session, batch_id: int | None) -> dict[int, models.FitnessTestResult]:
    """某批次的体测成绩，按 ``student_id`` 索引。``batch_id`` 为 ``None`` 时返回空表。"""
    if batch_id is None:
        return {}
    return {
        row.student_id: row
        for row in session.scalars(
            select(models.FitnessTestResult).where(
                models.FitnessTestResult.test_batch_id == batch_id
            )
        )
    }


def _latest_body_comp(session: Session, as_of: dt.date) -> dict[int, models.BodyComposition]:
    """每人 ``<= as_of`` 的**最新一条**体成分（Ruling 121：样本单位是学生，不是测量行）。

    按 ``measured_on`` 升序遍历、后写覆盖，故留下的是最新的一条。``(student_id,
    measured_on)`` 上有唯一约束（Ruling 24），同一天不可能有两条。
    """
    latest: dict[int, models.BodyComposition] = {}
    rows = session.scalars(
        select(models.BodyComposition)
        .where(models.BodyComposition.measured_on <= as_of)
        .order_by(models.BodyComposition.measured_on, models.BodyComposition.id)
    )
    for row in rows:
        latest[row.student_id] = row
    return latest


def _scores_of(row: models.FitnessTestResult | None) -> dict[ScoredItem, int | None]:
    """体测行的 7 个得分列 → ``{ScoredItem: int | None}``。

    列名一律是 ``score_`` + ``ScoredItem`` 的值，故用 ``getattr`` 逐项取（``models.py`` 的
    ``FitnessTestResult`` docstring 明确了这条约定），不另维护一张映射表。**行不存在时返回
    七项全 ``None``**——键必须齐全，``derive`` 的 ``_require_seven_keys``（Ruling 101）
    缺键会 ``KeyError``。
    """
    if row is None:
        return empty_scores()
    return {item: getattr(row, f"score_{item.value}") for item in ScoredItem}


def cohort_from_db(session: Session, as_of: dt.date) -> tuple[list[PersonInputs], Anchor]:
    """从库里还原 ``as_of`` 那天待判定的**全部**学生，返回 ``(persons, anchor)``。

    遍历的是 ``student`` 表的**每一个人**，不是「本批抽到记录的人」：缺测与缺记录都要走
    Z0 闸门并留下 ``insufficient_data`` 一行（Ruling 106 的合法状态），跳过他们会让这些人
    在 ``derived_metrics`` 与 ``stratification_result`` 里凭空消失，而 spec §4.6 要求运维
    记录能数出「本日没分层的人」。

    ``snapshot_muscle_p20`` 一律回填 ``None``（**未解析**）：肌肉量 P20 来自快照，而快照
    正是 :func:`run_percentile` 要产出的东西，此刻还不存在。调用方在物化/读回快照之后用
    :func:`app.pipeline.run_stratify.resolve_muscle_lines` 回填——两条路径共用同一个回填
    函数，故不可能一处查表、另一处凭空给值。

    ``years`` 恒为 ``YEAR_STEP = 1.0``（Ruling 140 的 week1-vs-week1 口径；无历史时也是
    1.0 而不是 0，Ruling 123）。``curr_total`` / ``prev_total`` 取**落库的** ``total_score``
    列，于是 ``derive`` 的 Ruling 118-M1 值校验真的在核对「落库总分」与「落库七项得分」
    是否自洽——它不是空转的。
    """
    anchor = assessment_anchor(session, as_of)
    current = current_semester_of(session, as_of)
    curr_rows = _results_of(session, anchor.curr_batch_id)
    prev_rows = _results_of(session, anchor.prev_batch_id)
    bodies = _latest_body_comp(session, as_of)
    # 批次所属学期 → 该学期开学年，用来算「这条记录是几个学年之前」（Ruling 56）
    year_of_batch: dict[int, int] = {}
    for batch_id in (anchor.curr_batch_id, anchor.prev_batch_id):
        if batch_id is None:
            continue
        year_of_batch[batch_id] = session.scalar(
            select(models.Semester.start_date)
            .join(
                models.FitnessTestBatch,
                models.FitnessTestBatch.semester_id == models.Semester.id,
            )
            .where(models.FitnessTestBatch.id == batch_id)
        ).year

    persons: list[PersonInputs] = []
    for student in session.scalars(select(models.Student).order_by(models.Student.id)):
        age = age_at(student.birth, current.start_date)
        sex = Sex(student.sex)
        curr_row, prev_row = curr_rows.get(student.id), prev_rows.get(student.id)
        prev_back = (
            0 if anchor.prev_batch_id is None
            else current.start_date.year - year_of_batch[anchor.prev_batch_id]
        )
        body = bodies.get(student.id)
        persons.append(
            PersonInputs(
                student_id=student.id,
                sex=sex,
                age_group=age_group_of(age),
                prev_age_group=age_group_of(age - prev_back),
                curr_scores=_scores_of(curr_row),
                prev_scores=None if prev_row is None else _scores_of(prev_row),
                curr_total=None if curr_row is None else curr_row.total_score,
                prev_total=None if prev_row is None else prev_row.total_score,
                years=YEAR_STEP,
                body_fat_pct=None if body is None else body.body_fat_pct,
                muscle_mass_kg=None if body is None else body.muscle_mass_kg,
                snapshot_muscle_p20=None,
            )
        )
    return persons, anchor


def load_snapshot(session: Session, as_of: dt.date) -> list[PercentileRow]:
    """读回 ``<= as_of`` 的**最新一次**物化快照，还原成 domain 的 :class:`PercentileRow`。

    取「最新一次」而不是「等于 ``as_of`` 的那一次」：百分位阶段在无新体测/体成分数据时
    **跳过**（``test_percentile_snapshot_materialized_not_recomputed`` 钉住），故次日没有
    自己的快照行，判定线必须复用上一日的——那正是「物化而非实时计算」的意义：判定线
    只在人群数据真的变了的时候才动。

    一张快照都没有时返回 ``[]``：``lookup_p25`` 于是对每一项都返回 ``None`` →
    ``valid_count = 0`` → 全员 Z0。**不抛异常**：首日之前跑一次管道是完全合法的操作，
    而「没有判定线」这件事本身已经被 ``insufficient_data`` 如实表达。
    """
    computed_on = session.scalar(
        select(func.max(models.PercentileSnapshot.computed_on)).where(
            models.PercentileSnapshot.computed_on <= as_of
        )
    )
    if computed_on is None:
        return []
    rows = session.scalars(
        select(models.PercentileSnapshot)
        .where(models.PercentileSnapshot.computed_on == computed_on)
        .order_by(
            models.PercentileSnapshot.item,
            models.PercentileSnapshot.sex,
            models.PercentileSnapshot.age_group,
        )
    )
    return [
        PercentileRow(
            item=SnapshotMetric(row.item),
            sex=Sex(row.sex),
            age_group=row.age_group,
            p10=row.p10,
            p20=row.p20,
            p25=row.p25,
            p50=row.p50,
            p75=row.p75,
            sample_size=row.sample_size,
            source=row.source,
        )
        for row in rows
    ]


def needs_recompute(session: Session, batch_id: int) -> bool:
    """本批是否要重新物化快照：**本批抽到了新的体测或体成分记录**时才要（计划 Step 3 的字面判据）。

    判据读的是 ``daily_sync_run`` 自己的 ``extracted_fitness`` / ``extracted_body_comp``
    两列（故 ``daily.py`` 必须在调用本函数**之前**把它们写上并 flush）。问卷不计入：
    它不进百分位样本。

    这条判据同时满足计划钉住的两种行为，并且让重放清理清单里的 ``PercentileSnapshot``
    **承重**：

    * **次日无新数据 → 跳过**（``test_percentile_snapshot_materialized_not_recomputed``）：
      水位线已推进到上一个业务日期，本批抽取为 0 条，故不重算，快照行数不变；
    * **同业务日重跑 → 重算**（``test_rerun_same_day_does_not_wipe_percentile_snapshot``，
      Ruling 32）：重跑时水位线取的是**严格早于**本业务日期的上一次成功运行，故同一批
      记录会被再抽一次（``extracted_* > 0``）→ 必须重算。而重算要插的行与上一轮
      **同 ``(semester_id, computed_on, item, sex, age_group)``**，只有先按 ``batch_id``
      删掉当日快照才插得进去。

    **若清理清单漏掉 ``percentile_snapshot``（只有两张派生表），这里会当场
    ``IntegrityError: UNIQUE constraint failed``** ——那正是 Ruling 29 给本表补
    ``batch_id`` 的理由，也是 Ruling 32 要堵的路径：漏删不会静默产出旧快照，
    而是让整批响亮失败并回滚。

    **已否决的另一条判据**（「源数据是否比上一次物化更新」，按日期比较）：它在同日重跑时
    会判定「不必重算」，于是删不删当日快照都看不出差别——**清理清单里的那一项变成空转**，
    而 Ruling 32 的守卫也就抓不到任何东西。更要紧的是它有一条静默路径：源系统补传一条
    ``tested_on <= business_date`` 的记录后重跑同一天，源表经 ``repo.upsert`` 更新了，
    快照却因为「数据日期没变」而**留在上一轮**，P25 于是与它要判定的得分不再是同一批人算的，
    全程不报错。
    """
    row = session.execute(
        select(
            models.DailySyncRun.extracted_fitness,
            models.DailySyncRun.extracted_body_comp,
        ).where(models.DailySyncRun.id == batch_id)
    ).one_or_none()
    if row is None:
        raise ValueError(
            f"daily_sync_run 里查无 id={batch_id}：percentile_snapshot.batch_id 是 NOT NULL "
            f"外键，物化前必须已 upsert 当批运行记录并 flush 取回 id"
        )
    return bool(row[0] or row[1])


def run_percentile(session: Session, business_date: str, batch_id: int) -> int:
    """物化本批的百分位快照，返回**本次写入的行数**（跳过时为 ``0``）。

    ``semester_id`` 从 ``batch_id`` 反查 ``daily_sync_run``：本列 NOT NULL，而计划钉住的
    签名里没有它——快照属于「哪一次运行」，那一次运行自己就带着学期。这也让
    ``percentile_snapshot.semester_id`` 与 ``daily_sync_run.semester_id`` **不可能**分叉。

    前置条件（计划 Step 3）：调用前必须已有当批 ``DailySyncRun`` 行、已 flush 取回 ``id``、
    且 ``extracted_fitness`` / ``extracted_body_comp`` 已写上（:func:`needs_recompute`
    读的就是这两列）。

    **不 commit、不 rollback**：事务边界由 ``daily.py`` 掌握，「整批失败回滚」才成立
    （与 ``repo.upsert`` / ``seed_database`` 同一条口径）。
    """
    as_of = parse_business_date(business_date)
    if not needs_recompute(session, batch_id):
        return 0
    semester_id = session.scalar(
        select(models.DailySyncRun.semester_id).where(models.DailySyncRun.id == batch_id)
    )
    persons, _anchor = cohort_from_db(session, as_of)
    snapshot = cohort_snapshot(persons, standard())
    for row in snapshot:
        session.add(
            models.PercentileSnapshot(
                semester_id=semester_id,
                computed_on=as_of,
                batch_id=batch_id,
                item=row.item.value,
                sex=row.sex.value,
                age_group=row.age_group,
                p10=row.p10,
                p20=row.p20,
                p25=row.p25,
                p50=row.p50,
                p75=row.p75,
                sample_size=row.sample_size,
                source=row.source,
            )
        )
    session.flush()
    return len(snapshot)

"""每日批处理编排：``Extract → Clean → Percentile → Derive → Stratify → Commit``。

spec §5 的十阶段里，Plan 01 落地前五个 + 第十个（提交与运维留痕）。三条贯穿全模块的纪律：

1. **整批单事务**：六个阶段共用一个原子边界，任一步抛异常 → 本批写过的东西全部撤销、
   运行记录落 ``status = "failed"`` 并留错误摘要，然后**原样重抛**（不吞异常：
   ``tests/pipeline/test_daily.py`` 的 ``test_failure_rolls_back_whole_batch`` 用
   ``pytest.raises`` 钉住这一点）。原子边界用 ``session.begin_nested()`` 的 SAVEPOINT
   实现而不是裸 ``session.rollback()``，理由见 :func:`run_daily` 的 docstring。

2. **按 ``(semester_id, business_date)`` 幂等重放**：开头 ``repo.upsert`` 运行记录并
   **flush 取回 ``id``**（插入分支在 flush 前 ``id`` 为 ``None``，而
   ``derived_metrics.batch_id`` / ``stratification_result.batch_id`` /
   ``percentile_snapshot.batch_id`` 都是 NOT NULL）。重放清理是**三张派生表**
   （``DerivedMetrics`` / ``StratificationResult`` / ``PercentileSnapshot``，Ruling 29 +
   32），三张源表**不删**、一律经 ``repo.upsert`` 按业务唯一约束幂等写入（Ruling 24），
   ``CleaningLog`` 按 ``sync_run_id`` 删——**不能用 ``delete_by_batch``**，它那一列不叫
   ``batch_id``，会抛 ``AttributeError``（Ruling 31 刻意设计的响亮失败）。

3. **算法一律复用 domain / ``run_stratify``，不在管道里重算任何一遍**：得分只由
   :func:`app.domain.indicators.score_item` 正查，总分只由
   :func:`app.domain.derive.national_total` 加权，百分位只由
   :func:`app.domain.percentile.compute_snapshot` 计算，派生只由
   :func:`app.domain.derive.derive` 编排，分层只由 :func:`app.domain.stratify.stratify`
   求值，快照的物化与读回只由 :mod:`app.pipeline.percentile_stage` 负责。
   ``stratify_dataset`` 是纯内存版；本模块的落库阶段复用它的
   :func:`~app.pipeline.run_stratify.evaluate` / :func:`~app.pipeline.run_stratify.result_dict`
   / :func:`~app.pipeline.run_stratify.input_snapshot_of`，故离线复算与库里的结果不可能分叉。

``app/pipeline/`` 不在 domain 层，可以碰数据库与时钟；Task 1 的三个 AST 守卫只扫
``app/domain/``。
"""
import argparse
import datetime as dt

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.adapters.base import DataSourceAdapter, parse_batch_key
from app.db import models, repo
from app.domain.derive import national_total
from app.domain.indicators import ScoredItem, Sex, age_group_of
from app.domain.percentile import MIN_SAMPLE
# **``stratify`` 必须绑在本模块的命名空间里**：``test_failure_rolls_back_whole_batch``
# monkeypatch 的是 ``app.pipeline.daily.stratify``。若本模块只调
# ``run_stratify.stratify_dataset``，那次 monkeypatch 会打到 ``run_stratify`` 自己的
# 绑定上、对这里毫无作用，整批照常成功，而断言 ``pytest.raises(RuntimeError)`` 当场失败。
# 这不是两套算法路径：调的是同一个 domain 纯函数，只是调用点在本模块。
from app.domain.stratify import stratify
from app.pipeline import run_stratify
from app.pipeline.clean import clean_body_comp, clean_fitness
from app.pipeline.extract import extract, parse_business_date
from app.pipeline.percentile_stage import (
    age_at, cohort_from_db, current_semester_of, load_snapshot, run_percentile,
)
from app.refdata import standard

__all__ = ["SOURCE_SYSTEM", "run_daily", "semester_by_name", "main"]

# ``fitness_test_batch.source`` 写的是**来源系统**（spec §4.2），不是适配器类名：
# Mock 与将来的 HTTP 实现读的是同一个上游（乐跑），把类名写进这一列会让同一份数据
# 在两种运行方式下留下两个不同的来源值。
SOURCE_SYSTEM = "lepao"


def semester_by_name(session: Session, name: str) -> models.Semester:
    """按 ``Semester.name`` 取学期：CLI ``--semester`` 与幂等键的查找键（``models.py:118``）。

    **不得**改用 ``scalar(select(Semester))`` 取「第一条」（Ruling 173）：``seed_database``
    写**两条** Semester（上学年 ``2024-2025-1`` + 本学年 ``2025-2026-1``），不带
    ``order_by`` 的 ``scalar`` 实测取到的是**先插入的上学年**。那样写功能上不炸——
    :func:`run_daily` 的 ``semester_id`` 只是运行记录与快照的归属、不是数据的归属——
    于是运行记录、``percentile_snapshot.semester_id`` 与幂等键的一半会**静默**挂到上学年，
    而六个阶段的计数看起来全都正常。

    查不到就响亮失败，并在消息里列出库里现有的学期名：``--semester`` 传成学年
    （``2025-2026``）或传成 id 是最常见的两种写法错误，静默退回「第一条」正是上面那个
    缺陷的形状。

    本函数住在这里而不是 ``backfill.py``，是因为 ``backfill`` 建立在 ``daily`` 之上
    （它逐日调 :func:`run_daily`），反向依赖会构成导入环；两个 CLI 因此共用同一个所有者。
    """
    semester = session.scalar(
        select(models.Semester).where(models.Semester.name == name)
    )
    if semester is None:
        existing = [
            row[0] for row in session.execute(select(models.Semester.name)).all()
        ]
        raise ValueError(
            f"semester 表里查无 name={name!r}：--semester 的值是学期**名**"
            f"（如 2025-2026-1），它同时是幂等键 (semester_id, business_date) 的一半。"
            f"库里现有的学期名是 {existing}"
            f"（组织结构由 python -m app.seed.generate 建立）"
        )
    return semester


def _semester_of(
    session: Session, day: dt.date, cache: dict[dt.date, models.Semester]
) -> models.Semester:
    """包含 ``day`` 的那个学期（``start_date <= day <= end_date``）。

    ``fitness_test_batch.semester_id`` 与 ``interest_survey.semester_id`` 都靠它定位。
    **按日期区间查而不是按学年名猜**：``semester`` 表没有 ``academic_year`` 列，
    而 ``Semester.name``（``"2024-2025-1"``）与 ``batch_key`` 的学年段（``"2024-2025"``）
    之间的对应关系是命名习惯、不是约束——按前缀匹配会在有人换个命名风格时静默把
    上学年的体测挂到本学年上。

    查不到就响亮失败：静默挂到 ``run_daily`` 传进来的那个 ``semester_id`` 上会更糟，
    因为那个参数是**运行记录**的学期（幂等键的一半），不是**数据**的学期，
    两者在回填历史时本来就不相等。
    """
    if day in cache:
        return cache[day]
    semester = session.scalar(
        select(models.Semester).where(
            models.Semester.start_date <= day, models.Semester.end_date >= day
        )
    )
    if semester is None:
        raise ValueError(
            f"{day.isoformat()} 不落在任何学期的 [start_date, end_date] 内，"
            f"无从判定它属于哪个学期；fitness_test_batch.semester_id 与 "
            f"interest_survey.semester_id 都是 NOT NULL 外键，猜一个会把上学年的数据"
            f"静默挂到本学年上"
        )
    cache[day] = semester
    return semester


def _fitness_batch(
    session: Session,
    semester: models.Semester,
    timepoint: str,
    test_date: dt.date,
    academic_year: str,
) -> models.FitnessTestBatch:
    """查找或创建体测批次，并**立刻 flush** 取回 ``id``。

    ``fitness_test_result.test_batch_id`` 是 NOT NULL 外键，而 ``repo.upsert`` 的插入分支
    在 flush 前 ``id`` 为 ``None``。批次一共只有「两学年 × 三时点」至多 6 个，逐个 flush
    的代价可以忽略。

    幂等键是 ``(semester_id, timepoint)``：本表没有唯一约束，故靠 ``repo.upsert`` 的
    查找分支兜住——重跑同一业务日期时查到同一行、更新它，不会插出第二个 week1 批次。
    插出第二个的后果是 ``fitness_test_result`` 按 ``(test_batch_id, student_id)`` 去重时
    认不出「这是同一次体测」，同一学生同一时点于是留下两行，百分位样本翻倍且不报错。
    """
    batch = repo.upsert(
        session,
        models.FitnessTestBatch,
        ("semester_id", "timepoint"),
        {
            "semester_id": semester.id,
            "timepoint": timepoint,
            "test_date": test_date,
            "source": SOURCE_SYSTEM,
            "academic_year": academic_year,
        },
    )
    session.flush()
    return batch


def _log_cleaning_entries(
    session: Session, batch_id: int, entries, student_id_by_no: dict[str, int]
) -> None:
    """把 Task 5 的审计条目逐条落成 ``cleaning_log`` 行（spec §4.6）。

    ``student_id`` 解析得到才填、解析不出留 ``NULL``（Ruling 25 的双列设计）：孤儿学号的
    审计记录**正是最该被看见的那一类数据质量问题**，若把 ``student_id`` 做成非空外键，
    它们会被约束直接挡在库外。``original_value`` / ``processed_value`` 是
    :class:`~app.db.models.JsonText`，故 ``None`` 落 SQL ``NULL`` 而不是字符串 ``"None"``、
    ``65.0`` 也不会被 SQLite 的 NUMERIC 亲和性改写成 ``65``。
    """
    for entry in entries:
        session.add(
            models.CleaningLog(
                sync_run_id=batch_id,
                student_no=entry.student_no,
                student_id=student_id_by_no.get(entry.student_no),
                field=entry.field,
                original_value=entry.original_value,
                processed_value=entry.processed_value,
                kind=entry.kind,
                reason=entry.reason,
            )
        )


def _log_unattributable(
    session: Session, batch_id: int, student_no: str, source: str, day: str
) -> None:
    """学号解析不到 ``student`` 表时，为**整条被跳过的记录**留一条审计。

    Task 5 的清洗层已经整条剔除了空学号的记录（Ruling 47）；这里是**另一半**——学号非空
    但库里查无此人。同样必须整条跳过：``fitness_test_result.student_id`` 与
    ``body_composition.student_id`` 都是 NOT NULL 外键，没有归属就写不进去。

    **跳过必须留痕**： silently 丢掉一条记录与「这条记录从来没到过」在库里长得一模一样，
    而 spec §4.6 要求「必须能交代每一条被剔除或修正的数据」。``kind`` 复用
    ``missing_dropped``、``field`` 写 ``student_no``，与 Task 5 的
    ``_unattributable_entry`` 同一口径（**不新增第五个 kind**：那会牵动 Task 3 已建的
    CHECK 约束 ``ck_cleaning_log_kind``）。
    """
    session.add(
        models.CleaningLog(
            sync_run_id=batch_id,
            student_no=student_no,
            student_id=None,
            field="student_no",
            original_value=student_no,
            processed_value=None,
            kind="missing_dropped",
            reason=(
                f"{source} 里学号 {student_no!r}（日期 {day}）在 student 表中查无此人，"
                f"整条记录已跳过：既不入库，也不参与百分位、短板与趋势的任何计算。"
                f"组织结构由 seed_database 建立、不经适配器流入（spec §3.4 骨架先行），"
                f"故这只能是学号写错或该生尚未建档"
            ),
        )
    )


def _replay_cleanup(session: Session, batch_id: int) -> None:
    """重放清理：**三张派生表**按 ``batch_id`` 删，``cleaning_log`` 按 ``sync_run_id`` 删。

    **清理清单是三张表、不是两张**（Ruling 29 给 ``percentile_snapshot`` 补了 ``batch_id``）：
    漏掉 ``PercentileSnapshot`` 会让同日重跑当场 ``IntegrityError: UNIQUE constraint
    failed``——百分位阶段的判据是「本批抽到了新体测/体成分」（
    :func:`~app.pipeline.percentile_stage.needs_recompute`），而同日重跑的水位线取的是
    **严格早于**本业务日期的上一次成功运行，故同一批记录会被再抽一次、快照会被重算，
    重算要插的行与上一轮同 ``(semester_id, computed_on, item, sex, age_group)``
    （Ruling 32 就是为这条路径立的，``test_rerun_same_day_does_not_wipe_percentile_snapshot``
    钉住它）。响亮失败好过静默沿用上一轮的判定线：那会让 P25 与它要判定的得分
    不是同一批人算出来的，而六个阶段的计数看起来全都正常。

    **三张源表不删**（``FitnessTestResult`` / ``BodyComposition`` / ``InterestSurvey``）：
    一律经 ``repo.upsert`` 按各自的业务唯一约束幂等写入（Ruling 24）。删源表的后果是
    「重跑一次就把上一轮抽到的数据弄丢」，而重放的定义是「同一批输入得到同一批输出」。
    注意 ``FitnessTestResult`` 那一列叫 ``test_batch_id``（Ruling 31），
    ``delete_by_batch`` 对它抛 ``AttributeError`` 是**刻意设计**。

    ``CleaningLog`` 同理不能走 ``delete_by_batch``——它那一列叫 ``sync_run_id``。
    不删它就会让重跑把同一批清洗条目**翻倍**（审计记录翻倍意味着「这条数据为什么没了」
    有两个互相矛盾的答案），而 ``_counts()`` 的七元组会当场对不上。
    """
    for model in (
        models.DerivedMetrics,
        models.StratificationResult,
        models.PercentileSnapshot,
    ):
        repo.delete_by_batch(session, model, batch_id)
    session.flush()
    session.execute(
        delete(models.CleaningLog).where(models.CleaningLog.sync_run_id == batch_id)
    )
    session.flush()


def _load_sources(
    session: Session,
    batch_id: int,
    extracted,
    student_by_no: dict[str, models.Student],
    current: models.Semester,
) -> tuple[int, int, int]:
    """Clean + 写三张源表，返回 ``(dropped, corrected, unattributable)``。

    **顺序是承重的**：先清洗、后落库。清洗层负责去重（体测按 ``(student_no, batch_key)``、
    体成分按 ``(student_no, measured_on)``，Ruling 93——**不是 ``tested_on``**）与
    缺测/越界处置；落库一律走 ``repo.upsert`` 按业务唯一约束幂等写入。倒过来会让
    ``repo.upsert`` 静默覆盖重复行、不留任何痕迹。

    正查得分用的龄组按**该记录所属学年**取（Ruling 56）：``age_group_of(age - years_back)``，
    其中 ``age`` 以「本学年开学日」为参考日、``years_back`` 是该批次所属学期与本学年的
    开学年之差。查错一张表的后果是趋势差值带系统性偏差，而趋势是规则 Y4 的唯一输入。

    ``total_score`` 一律用 :func:`~app.domain.derive.national_total`（加权口径的唯一所有者，
    Ruling 63），**不手写 ``Σ w·s // 100``**：``derive`` 的 Ruling 118-M1 值校验会在派生
    阶段拿落库的 ``total_score`` 与落库的七项得分对账，手写口径不等就当场 ``ValueError``。

    ``national_grade`` 一律写 ``None``：spec §4.2 列了「国标等级」这一列，但**全仓与 spec
    都没有给出「总分 → 优秀/良好/及格/不及格」的阈值口径**，自己填一套就是凭空造第二个
    口径（而它会出现在学生端与报表上）。已登记为关切，待控制者裁定。
    """
    table = standard()
    field_ranges = run_stratify.ranges()
    semester_cache: dict[dt.date, models.Semester] = {}
    student_id_by_no = {no: student.id for no, student in student_by_no.items()}

    fitness_clean = clean_fitness(extracted.fitness, field_ranges)
    body_clean = clean_body_comp(extracted.body_comp, field_ranges)
    _log_cleaning_entries(session, batch_id, fitness_clean.entries, student_id_by_no)
    _log_cleaning_entries(session, batch_id, body_clean.entries, student_id_by_no)

    unattributable = 0
    for record in fitness_clean.fitness:
        student = student_by_no.get(record.student_no)
        if student is None:
            unattributable += 1
            _log_unattributable(session, batch_id, record.student_no, "体测", record.tested_on)
            continue
        tested_on = dt.date.fromisoformat(record.tested_on)
        semester = _semester_of(session, tested_on, semester_cache)
        academic_year, timepoint = parse_batch_key(record.batch_key)
        batch = _fitness_batch(session, semester, timepoint, tested_on, academic_year)
        years_back = current.start_date.year - semester.start_date.year
        age_group = age_group_of(
            age_at(student.birth, current.start_date) - years_back
        )
        scores = run_stratify.score_raw(
            run_stratify.record_dict(record), Sex(student.sex), age_group, table
        )
        values = {
            "test_batch_id": batch.id,
            "student_id": student.id,
            "height_cm": record.height_cm,
            "weight_kg": record.weight_kg,
            "vital_capacity_ml": record.vital_capacity_ml,
            "sprint_50m_s": record.sprint_50m_s,
            "sit_and_reach_cm": record.sit_and_reach_cm,
            "standing_jump_cm": record.standing_jump_cm,
            "strength_count": record.strength_count,
            "distance_run_s": record.distance_run_s,
            "total_score": national_total(scores),
            "national_grade": None,
        }
        # 得分列名一律是 "score_" + ScoredItem 的值（models.py 的既有约定），
        # 故逐项生成而不是手抄七行——手抄漏一项会让那一列在重放时**静默存活**为上一轮的值。
        values.update({f"score_{item.value}": scores[item] for item in ScoredItem})
        repo.upsert(
            session, models.FitnessTestResult, ("test_batch_id", "student_id"), values
        )

    for record in body_clean.body_comp:
        student = student_by_no.get(record.student_no)
        if student is None:
            unattributable += 1
            _log_unattributable(
                session, batch_id, record.student_no, "体成分", record.measured_on
            )
            continue
        repo.upsert(
            session,
            models.BodyComposition,
            ("student_id", "measured_on"),
            {
                "student_id": student.id,
                "measured_on": dt.date.fromisoformat(record.measured_on),
                "muscle_mass_kg": record.muscle_mass_kg,
                "body_fat_pct": record.body_fat_pct,
                "smi": record.smi,
                # 适配器契约（RawBodyCompRecord）里没有这两列。**显式写 None** 而不是省略：
                # repo.upsert 的更新分支是 PATCH 语义，省略就等于「沿用上一轮的值」，
                # 那会让一个从未被测过的列看起来像是被测过。
                "weight_kg": None,
                "device": None,
            },
        )

    for record in extracted.survey:
        student = student_by_no.get(record.student_no)
        if student is None:
            unattributable += 1
            _log_unattributable(session, batch_id, record.student_no, "问卷", record.filled_on)
            continue
        filled_on = dt.date.fromisoformat(record.filled_on)
        semester = _semester_of(session, filled_on, semester_cache)
        repo.upsert(
            session,
            models.InterestSurvey,
            ("student_id", "semester_id", "filled_on"),
            {
                "student_id": student.id,
                "semester_id": semester.id,
                "filled_on": filled_on,
                "total_score": record.total,
                "dimensions": dict(record.dimensions),
                "raw_answers": dict(record.raw_answers),
            },
        )
    session.flush()
    return (
        fitness_clean.dropped + body_clean.dropped,
        fitness_clean.corrected + body_clean.corrected,
        unattributable,
    )


def _stratify_and_persist(
    session: Session, batch_id: int, as_of: dt.date
) -> tuple[list[str], int]:
    """Percentile → Derive → Stratify 三个阶段，返回 ``(labels, 缺线组数)``。

    快照**物化后再读回**（``run_percentile`` 写、``load_snapshot`` 读），而不是把内存里
    算出的那份直接往下传：spec §4.0 要求「禁止实时计算」，而只有真的走一遍
    「写进 ``percentile_snapshot`` → 从库里读回」才能证明落库与读回是互逆的
    （``item`` / ``sex`` 两列存的是 ``.value`` 字符串，读回时要重建成枚举；
    ``p10…p75`` 走 SQLite 的 REAL）。跳过这一步的话，一个「存得下、读不回来」的列
    要到 Plan 02 才暴露。

    ``snapshot_muscle_p20`` 由 :func:`~app.pipeline.run_stratify.resolve_muscle_lines`
    回填——与内存路径共用同一个函数，故不可能一处查表、另一处凭空给值（那正是
    Ruling 102 的缺陷形态：``muscle_low`` 永不可达、``C`` 退化成只看体脂率，且不报错）。
    """
    run_percentile(session, as_of.isoformat(), batch_id)
    persons, _anchor = cohort_from_db(session, as_of)
    snapshot = load_snapshot(session, as_of)
    persons = run_stratify.resolve_muscle_lines(persons, snapshot)

    labels: list[str] = []
    for evaluated in run_stratify.evaluate(persons, snapshot):
        result = stratify(evaluated.derived)
        person, derived = evaluated.person, evaluated.derived
        labels.append(result.label.value)
        session.add(
            models.DerivedMetrics(
                student_id=person.student_id,
                computed_on=as_of,
                batch_id=batch_id,
                annual_change=dict(derived.annual_change),
                trend=derived.trend.value,
                weaknesses=[item.value for item in derived.weakness.items],
                weakness_count=derived.weakness.count,
                valid_count=derived.weakness.valid_count,
                body_comp_abnormal=derived.body_comp.abnormal,
                body_comp_reasons=list(derived.body_comp.reasons),
            )
        )
        session.add(
            models.StratificationResult(
                student_id=person.student_id,
                computed_on=as_of,
                batch_id=batch_id,
                label=result.label.value,
                # 逗号连接、不含空格，与 models.py 那一列的注释（"R1,R2,Y1"）逐字对应。
                # **任何路径都至少一项**：Z0 命中时是 "Z0" 而不是空串（Ruling 125），
                # 空串会让 explain() 的 hit_rules[-1] 当场 IndexError。
                hit_rules=",".join(rule.value for rule in result.hit_rules),
                input_snapshot=run_stratify.input_snapshot_of(evaluated, result, snapshot),
                percentile_source=run_stratify.percentile_source_of(person, snapshot),
                valid_from=as_of,
                # 仍生效 → NULL（models.py 的既有语义）。**刻意不去关闭上一日的行**：
                # 「哪一条现在生效」由 ``computed_on`` 最大者唯一确定，而把旧行的
                # valid_to 写成本日会让重放必须同时改写上一批的行——那会破坏
                # 「同一业务日期重跑只动本批」这条幂等边界。已登记为前向约束。
                valid_to=None,
            )
        )
    session.flush()
    return labels, run_stratify.muscle_line_gaps(persons, snapshot)


def _record_failure(
    session: Session, semester_id: int, as_of: dt.date, exc: BaseException
) -> None:
    """失败留痕：**独立小事务**写一条 ``status = "failed"`` 的运行记录（计划 Step 3）。

    本批的全部写入已经被 SAVEPOINT 撤销，这一行是唯一的幸存者——它必须存在，否则
    「这一天跑过、并且失败了」在库里没有任何痕迹，运维只能靠日志猜，而日志会滚掉。
    ``status`` 的默认值本来就是 ``"failed"``（Ruling 30 的保守方向），这里显式再写一次
    是为了同时把 ``error_summary`` 与 ``finished_at`` 落上。

    **留痕本身失败不得盖掉真正的异常**：这一小段包在自己的 try 里，失败时回滚它自己
    并原样吞掉，让调用方的 ``raise`` 把真因抛出去。一个把 ``RuntimeError("boom")``
    换成 ``IntegrityError`` 的错误处理器，等于把唯一的线索删了。
    """
    try:
        repo.upsert(
            session,
            models.DailySyncRun,
            ("semester_id", "business_date"),
            {
                "semester_id": semester_id,
                "business_date": as_of,
                "finished_at": dt.datetime.now(),
                "status": "failed",
                "error_summary": f"{type(exc).__name__}: {exc}",
            },
        )
        session.commit()
    except Exception:  # noqa: BLE001 - 留痕失败不得盖掉真因，见 docstring
        session.rollback()


def run_daily(
    session: Session, semester_id: int, business_date: str, adapter: DataSourceAdapter
) -> models.DailySyncRun:
    """跑一个业务日期的整批，返回该批的 :class:`~app.db.models.DailySyncRun`。

    **``semester_id`` 是运行记录与快照的归属**（幂等键 ``(semester_id, business_date)``
    的一半），**不是数据的归属**：``fitness_test_batch`` 与 ``interest_survey`` 的学期由
    记录自己的日期落在哪个学期区间决定（见 :func:`_semester_of`）。回填历史时两者本来
    就不相等——用 ``--semester 2025-2026-1`` 重放一个 2024 年的业务日期是完全合法的。

    **原子边界用 ``session.begin_nested()``（SAVEPOINT）而不是裸 ``session.rollback()``**，
    这是对计划字面措辞的一处有意偏离，理由是实测的：调用方（``tests`` 的 fixture 与
    Task 11 的 ``backfill``）可能在本函数之前就有**尚未提交**的写入（``seed_database``
    只 flush 不 commit）。裸 ``session.rollback()`` 会把它们一并撤销，于是紧接着写
    「失败运行记录」时 ``daily_sync_run.semester_id`` 指向的 ``semester`` 行已经不存在，
    SQLite 的 ``PRAGMA foreign_keys=ON``（Ruling 27 的钩子）当场
    ``FOREIGN KEY constraint failed``——**错误处理器自己炸了，真因被盖掉**。
    SAVEPOINT 只撤销本批，调用方的待提交内容原样保留，失败记录因此总写得进去。
    对调用方而言语义不变：本批要么全在、要么全不在。

    ``status`` 的三种取值：

    * ``"success"``：整批跑完，每条记录都归到了人头上；
    * ``"partial"``：整批跑完，但有记录因**学号解析不到 ``student`` 表**而被整条跳过
      （已在 ``cleaning_log`` 里逐条留痕）。这是「跑完了，但不是全都进来了」，
      与 ``success`` 必须可区分——否则运维看 status 决定要不要重跑，而重跑也修不好
      一个建档缺失的学号；
    * ``"failed"``：未捕获异常，本批全部回滚（也是 Ruling 30 的默认值：进程崩在中途时
      留下的就是它）。
    """
    as_of = parse_business_date(business_date)
    run = repo.upsert(
        session,
        models.DailySyncRun,
        ("semester_id", "business_date"),
        {
            "semester_id": semester_id,
            "business_date": as_of,
            "started_at": dt.datetime.now(),
            "finished_at": None,
            # **传全部列**：repo.upsert 的更新分支是 PATCH 语义，省略就等于「沿用上一轮的
            # 值」，那会让重放后的计数看起来像是本轮算出来的。处方与预警两列由 Plan 02/03
            # 写入，本批开始时一律归零（重放必须重算它们，见前向约束）。
            "extracted_fitness": 0,
            "extracted_body_comp": 0,
            "extracted_survey": 0,
            "dropped_count": 0,
            "corrected_count": 0,
            "red_count": 0,
            "yellow_count": 0,
            "green_count": 0,
            "insufficient_count": 0,
            "prescription_count": 0,
            "alert_count": 0,
            "status": "failed",
            "error_summary": None,
        },
    )
    # **必须 flush 取回 id**：插入分支在 flush 前 id 为 None，而三张派生表的 batch_id
    # 都是 NOT NULL 外键（repo.upsert 的 docstring 把这条契约写在了那里）。
    session.flush()
    batch_id = run.id

    try:
        with session.begin_nested():
            _replay_cleanup(session, batch_id)
            extracted = extract(session, adapter, as_of.isoformat())
            student_by_no = {
                student.student_no: student
                for student in session.scalars(select(models.Student))
            }
            current = current_semester_of(session, as_of)
            dropped, corrected, unattributable = _load_sources(
                session, batch_id, extracted, student_by_no, current
            )
            # **三个抽取计数必须在百分位阶段之前写上并 flush**：
            # ``percentile_stage.needs_recompute`` 读的就是 ``daily_sync_run`` 的
            # ``extracted_fitness`` / ``extracted_body_comp`` 两列（计划 Step 3「仅在存在
            # 新体测/体成分数据时执行」）。放到最后写的话，那一判断会读到 upsert 时填的 0，
            # 于是**首日也跳过物化**——快照恒为空、全员 Z0，而六个阶段的计数看起来都正常。
            run.extracted_fitness = len(extracted.fitness)
            run.extracted_body_comp = len(extracted.body_comp)
            run.extracted_survey = len(extracted.survey)
            session.flush()
            labels, muscle_gaps = _stratify_and_persist(session, batch_id, as_of)

            run.dropped_count = dropped
            run.corrected_count = corrected
            run.red_count = labels.count("red")
            run.yellow_count = labels.count("yellow")
            run.green_count = labels.count("green")
            run.insufficient_count = labels.count("insufficient_data")
            run.status = "partial" if unattributable else "success"
            # 缺线组数的留痕（Ruling 121 第 4 步）。**不新增第三个 reasons token**
            # （Ruling 97① 冻结了 vocabulary），而 DailySyncRun 上唯一的自由文本列是
            # error_summary，故写在这里并明写「非错误」。已登记为关切：列名与内容不符。
            run.error_summary = (
                None if not muscle_gaps else (
                    f"注意（非错误）：{muscle_gaps} 个 (性别 × 年级组) 组没有肌肉量 P20 "
                    f"判定线——该组 InBody 样本 < {MIN_SAMPLE}，而肌肉量没有国标常模可降级，"
                    f"故整组不产出快照行（Ruling 121 第 4 步）。这些组的 C 只由体脂率决定，"
                    f"逐人的 snapshot_muscle_p20=null 已留在 input_snapshot 里"
                )
            )
            run.finished_at = dt.datetime.now()
            session.flush()
    except Exception as exc:
        _record_failure(session, semester_id, as_of, exc)
        raise
    session.commit()
    return run


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：``python -m app.pipeline.daily --semester 2025-2026-1 --date 2025-09-15``。

    ``--date`` **没有缺省**：给「今天」会让同一条命令在不同日子跑不同的批，而可复现是本
    项目的硬要求（``app/seed/config.py`` 的模块 docstring 为同一件事拒绝过 ``date.today()``）。

    ``--db`` 缺省取 :data:`app.seed.generate.DEFAULT_DB_URL`，与 ``python -m app.seed.generate``
    和 ``python -m app.pipeline.backfill`` 是**同一个所有者**（计划字面写的是相对路径
    ``sqlite:///pe.db``，那取决于 CWD；两个所有者会在有人从仓库根运行时静默指向两个文件）。

    适配器缺省是 :class:`~app.adapters.mock_lepao.MockLePaoAdapter` 读 ``data/seed/`` 下的
    CSV——Plan 01 只有这一个实现；Plan 02 接 HTTP 乐跑时改的就是这一处（函数内导入，故本
    生产模块的顶层依赖图里不出现 Mock）。

    ``run_daily`` 失败时**不捕获**：它已经把 ``status = "failed"`` 的运行记录提交进库，真因
    由 traceback 原样抛出、退出码 1。在这里包一层 try/except 只会把唯一的线索换成一行摘要。
    故正常返回时 ``status`` 只可能是 ``"success"`` 或 ``"partial"``，退出码恒 0。
    """
    from app.adapters.mock_lepao import MockLePaoAdapter
    from app.db.session import engine
    from app.seed.generate import DEFAULT_CSV_DIR, DEFAULT_DB_URL

    parser = argparse.ArgumentParser(
        prog="python -m app.pipeline.daily",
        description="跑单个业务日期的整批（Extract → Clean → Percentile → Derive → Stratify）",
    )
    parser.add_argument(
        "--semester", required=True,
        help="学期名（semester.name，如 2025-2026-1）；它是幂等键的一半，故按名字查",
    )
    parser.add_argument(
        "--date", required=True,
        help="业务日期 ISO（YYYY-MM-DD）。**无缺省**：给「今天」会让同一条命令在不同日子"
             "跑不同的批，与可复现的硬要求冲突",
    )
    parser.add_argument("--db", default=DEFAULT_DB_URL, help=f"数据库 URL（缺省 {DEFAULT_DB_URL}）")
    args = parser.parse_args(argv)

    eng = engine(args.db)
    with Session(eng) as session:
        semester = semester_by_name(session, args.semester)
        run = run_daily(session, semester.id, args.date, MockLePaoAdapter(DEFAULT_CSV_DIR))
        # ⚠️ 一切字段读取都必须在这个 with 块内完成：run_daily 末尾的 commit 已把它们
        #    expire，会话一关就是 DetachedInstanceError（Task 10 关切 10）。
        total = run.red_count + run.yellow_count + run.green_count + run.insufficient_count
        print(
            f"业务日期 {run.business_date.isoformat()}（学期 {semester.name}，"
            f"batch_id={run.id}）status={run.status}"
        )
        print(
            f"抽取 体测 {run.extracted_fitness} / 体成分 {run.extracted_body_comp} / "
            f"问卷 {run.extracted_survey}；剔除 {run.dropped_count}、修正 {run.corrected_count}"
        )
        print(
            f"分层分布（{total} 人）：红 {run.red_count}、黄 {run.yellow_count}、"
            f"绿 {run.green_count}、数据不足 {run.insufficient_count}"
        )
        if run.error_summary:
            # 缺肌肉量 P20 判定线时这里写的是「注意（非错误）」，见 run_daily
            print(f"备注：{run.error_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

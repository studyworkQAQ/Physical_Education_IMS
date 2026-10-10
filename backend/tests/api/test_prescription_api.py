"""处方侧四个**特例端点**（:mod:`app.api.routers.prescription`）与它们依赖的投影层。

**本文件分三批**（与本 Task 的两个 commit 对应）：

* **批次 A —— 投影层**（P4-A1 的 Critical）。这四个端点全部建立在
  :mod:`app.pipeline.prescription_stage` 的几个投影函数上，而 P4-A1 说的是
  「``WeeklySheet`` **不能**直接 JSON 化」（``dataclasses.asdict`` 当场
  ``TypeError: cannot pickle 'mappingproxy' object``）。故本批钉的是：
  block 级投影只有**一个**所有者、它的反向映射逐格可逆、
  以及 ``response_model`` 与投影函数的键集没有漂。
* **批次 B —— 四个端点的行为**（计划 Step 1 点名的那些 + Review Focus 第 1 条）。
* **批次 C —— 前后端对接面**（P4-A5 的 ``securitySchemes``、P4-A3 的
  「请求体不得携带那两个服务端字段」）。

⚠️ **批次 A 的三条住在本文件而不是 ``tests/pipeline/``**：它们的**主语是 HTTP 的 JSON
形状**（前端能不能照着对接），而它们的期望侧一律是**字面写死的键名清单**
（硬规矩 #35），与被测侧（投影函数的输出 / Pydantic 的元数据 / ``/openapi.json``）
三个来源互不同源。

⚠️ **本文件的夹具不碰 ``app.seed``、不碰 ``backend/data/`` 的一个字节**：
分层快照是**手工构造的最小 7 键**（``_profile_of`` 与 ``match_template`` 只读这 7 个），
动作库/模板/等价表走 :mod:`app.refdata_prescription` 的三个进程内单例（**只读** YAML）。
"""
import datetime as dt
import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import refdata_prescription as rp
from app.api.schemas.prescription import (
    AssembledBlockRead,
    AssembledSessionRead,
    AssembledWeekRead,
    OverrideCreate,
    OverrideRecordRead,
    TrainingPackageRead,
    WeeklySheetRead,
)
from app.db.models import Semester, Student, StratificationResult, Teacher
from app.db.models.ops import DailySyncRun
from app.db.models.prescription import Prescription, WeeklyAdjustment
from app.domain.indicators import Sex
from app.domain.prescription.assembler import StudentProfile, TrainingPackage, assemble
from app.domain.prescription.intensity import age_from
from app.domain.prescription.override import OverrideKind, OverrideRecord
from app.domain.prescription.safety import SafetyInput, apply_safety
from app.domain.prescription.weekly import weekly_training_sheet
from app.pipeline.prescription_stage import (
    _block_payload,
    _session_payload,
    override_record_payload,
    override_records_of,
    training_package_from,
    training_package_payload,
    weekly_sheet_payload,
)

D = dt.date
T = dt.datetime

#: 业务日期。**一律显式传**（模块 docstring 里那条「测试不可复现」的对策）：
#: 缺省那一档只由 :func:`test_as_of_defaults_to_the_server_clock` 一条看着。
AS_OF = D(2025, 9, 15)
BIRTH = D(2005, 3, 4)
#: 模板 RED-END-ABN-01 的微周期（``Template.microcycle_weeks``）。
#: ⚠️ 字面写死，不从 ``rp.templates()`` 读回来（硬规矩 #35）。
MICROCYCLE_WEEKS = 4
#: ``valid_to = generated_on + 4 周 − 1 天`` = 第 28 天（闭区间）。
VALID_TO = D(2025, 10, 12)

STUDENT_NO = "S2025001"
OTHER_STUDENT_NO = "S2025002"
TEACHER_STAFF_NO = "T2025001"
TEACHER_HEADERS = {"X-Teacher-Staff-No": TEACHER_STAFF_NO}

#: ``stratification_result.input_snapshot`` 的**最小可用形状**。
#:
#: ⚠️ 生产上那一列有 **28** 个键（``tests/pipeline/test_prescription_stage.py`` 的
#: ``_PINNED_SNAPSHOT_KEYS`` 逐字钉住），而本夹具只给 **7** 个——恰好是
#: :func:`app.pipeline.prescription_stage._profile_of` 读的 5 个
#: （``curr_scores`` / ``bmi`` / ``body_fat_pct`` / ``muscle_mass_kg`` /
#: ``snapshot_muscle_p10``）加 :func:`~app.domain.prescription.match.match_template`
#: 与 :class:`~app.domain.prescription.safety.SafetyInput` 读的 2 个
#: （``dominant_bucket`` / ``C``）。
#: ⚠️ **这是刻意的**：本文件的被测对象是 HTTP 端点，不是快照的键集契约
#: （那一条守卫住在 pipeline 层，且它有 28 个键的完整期望侧）。少给的 21 个键
#: 一个都没有读侧，故它们在本文件里只会拖慢夹具。
#: ⚠️ 六项国标得分一律 **60 分上下**（> P25），故 ``W = 0``；``C = True`` 是**手填**的
#: （生产的 ``C`` 由 ``derive`` 判定），于是匹配到的是 ``RED-END-ABN-01``——
#: 那一套模板**会追加一个 addon block**（``volume_unit == "unspecified"``、
#: ``weekly_volume == 0.0``），而它是
#: :func:`test_an_unspecified_addon_block_comes_back_with_zero_volume` 要的那一档。
SNAPSHOT = {
    "curr_scores": {
        "vital_capacity": 60.0,
        "distance_run": 55.0,
        "pull_up_or_sit_up": 70.0,
        "standing_long_jump": 65.0,
        "shuttle_run": 62.0,
        "sit_and_reach": 58.0,
    },
    "bmi": 21.8,
    "body_fat_pct": 15.0,
    "muscle_mass_kg": 50.0,
    "snapshot_muscle_p10": 25.5,
    "dominant_bucket": "endurance",
    "C": True,
}

#: ``training_package`` 那一列里第 1 周第 1 课第 1 个 block 的 ``exercise_ref``。
#: ⚠️ 字面写死（它是 ``backend/data/exercises.yaml`` 的内容，不是被测代码的输出）。
FIRST_REF = "interval_run"
#: 上面那个 block 的骨架周量（分钟）。RED-END-ABN-01 第 1 周 ``delta = 1.0``、
#: 4 课/周、``structure = {sets: 4, work_min: 3, rest_min: 2}`` → ``(4×3+3×2)×4 = 72``？
#: ⚠️ **不是**：``weekly_volume`` 是**每课基准量 × sessions_per_week × 系数 × delta**，
#: 而基准量按 ``sets × work_min = 12`` 分钟/课（``rest_min`` 不计入训练量），
#: 再乘个体修正系数 ``0.8``（``endurance_score = 57.5`` 落 ``low`` 档）→ ``12 × 4 × 0.8 = 38.4``。
FIRST_VOLUME = 38.4
#: 那一课里 ``volume_unit == "reps"`` 的 block（``compound_circuit``）的骨架周量。
SECOND_VOLUME = 96.0
#: addon block 的 ref（``volume_unit == "unspecified"``、``weekly_volume`` 恒 ``0.0``）。
ADDON_REF = "energy_expenditure_plus_10pct"


def _safety():
    """一张**真实装配 + 安全后置过**的训练包（``RED-END-ABN-01`` + ``C=True``）。

    ⚠️ 走生产的 :func:`~app.domain.prescription.assembler.assemble` +
    :func:`~app.domain.prescription.safety.apply_safety`，不手搓 ``TrainingPackage``：
    手搓的那一份会让「本文件的期望值」与「装配器的实际行为」之间少一道对账，
    而 P4-A1 那条 Critical 讲的正是投影层与 domain 对象之间的接缝。

    ⚠️ **``apply_safety`` 不是可选的一半**：spec §7.2 那个 ``addon``
    （``energy_expenditure_plus_10pct``、``volume_unit == "unspecified"``、
    ``weekly_volume == 0.0``）是**它**追加进 ``weeks`` 的，装配器不产它。
    少了这一半，每课只有 2 个 block（8 个/周而不是 12 个），
    而 :func:`test_an_unspecified_addon_block_comes_back_with_zero_volume`
    与「三个 ``volume_unit`` 并存」那两条会**空转**（``unspecified`` 那一档压根不出现）。
    ⚠️ 实测这一档 ``needs_review is False``、``substitutions`` 为空
    （``C=True`` 触发的是 addon 追加，不是高冲击替换），
    故 :data:`FIRST_REF` / :data:`FIRST_VOLUME` 两个锚点仍然可预测。
    """
    profile = StudentProfile(
        student_id=1,
        sex=Sex.MALE,
        birth=BIRTH,
        age=age_from(BIRTH, AS_OF),
        endurance_score=57.5,  # (60.0 + 55.0) / 2 —— 耐力桶两项的算术均值
        bmi=SNAPSHOT["bmi"],
        body_fat_pct=SNAPSHOT["body_fat_pct"],
        muscle_mass_kg=SNAPSHOT["muscle_mass_kg"],
        muscle_p10=SNAPSHOT["snapshot_muscle_p10"],
        measured_hrmax=None,
    )
    template = rp.templates()["RED-END-ABN-01"]
    package = assemble(profile, template, AS_OF, exercises=rp.exercises())
    return apply_safety(
        package,
        SafetyInput(
            bmi=profile.bmi,
            muscle_mass_kg=profile.muscle_mass_kg,
            muscle_p10=profile.muscle_p10,
            body_fat_abnormal=SNAPSHOT["C"],
        ),
        rp.equivalence(),
        template=template,
        exercises=rp.exercises(),
    )


def _package() -> TrainingPackage:
    """:func:`_safety` 的那一份**生效**训练包（安全后置之后）。"""
    return _safety().package


def _seed(engine, *, status: str = "active", valid_to=D(2025, 10, 12),
          generated_on=AS_OF, overrides: list | None = None,
          second_student: bool = True) -> dict:
    """往内存库里插一套**最小可用**的行，返回 ``{名字: id}``。

    顺序按外键拓扑：``semester`` → ``teacher`` / ``student`` → ``daily_sync_run`` →
    ``stratification_result`` → ``prescription``。
    ⚠️ **用完即关**（``with Session(...)``）：``conftest.py`` 的模块 docstring 交代了
    StaticPool 下全进程只有一条 DBAPI 连接。

    ⚠️ **``training_package`` 走完整的生产路径**（:func:`assemble` + :func:`apply_safety`），
    故 ``assembly_snapshot`` 是 **15** 个键（Plan 02 钉死的「12 + 至多 3」的上界那一格），
    而 addon block 也在里面——它是两条守卫（``unspecified`` 那一档、
    「三个 ``volume_unit`` 并存」）的**前提**，不是可选装饰。
    ⚠️ ``safety_substitutions`` 从 :class:`SafetyOutcome` 原样投影，
    与 :func:`app.pipeline.prescription_stage._prescription_values` 同一份写法；
    本夹具那一档实测为空列表（``C=True`` 触发的是 addon 追加，不是高冲击替换）。
    """
    safety = _safety()
    pkg = safety.package
    substitutions = [
        {
            "week": item.week,
            "day": item.day,
            "original_ref": item.original_ref,
            "substitute_ref": item.substitute_ref,
            "trigger": item.trigger,
            "equivalence_version": item.equivalence_version,
        }
        for item in safety.substitutions
    ]
    assert substitutions == [], "本夹具的锚点假设「没有安全替换」，若变了要重算 FIRST_REF"
    assert safety.needs_review is False
    with Session(engine) as session:
        semester = Semester(
            name="2025-2026-1", start_date=D(2025, 9, 1), end_date=D(2025, 12, 22),
            weeks=16, is_current=True,
        )
        teacher = Teacher(staff_no=TEACHER_STAFF_NO, name="张老师")
        student = Student(
            student_no=STUDENT_NO, name="小明", sex="male", birth=BIRTH,
            department=None, grade=1,
        )
        session.add_all([semester, teacher, student])
        session.flush()
        ids = {
            "semester": semester.id,
            "teacher": teacher.id,
            "student": student.id,
        }
        if second_student:
            other = Student(
                student_no=OTHER_STUDENT_NO, name="小红", sex="female",
                birth=D(2005, 7, 20), department=None, grade=1,
            )
            session.add(other)
            session.flush()
            ids["other_student"] = other.id

        run = DailySyncRun(
            semester_id=semester.id, business_date=AS_OF,
            started_at=T(2025, 9, 15, 2, 0), finished_at=T(2025, 9, 15, 2, 5),
            status="success",
        )
        session.add(run)
        session.flush()
        ids["batch"] = run.id

        session.add(StratificationResult(
            student_id=student.id, computed_on=generated_on, batch_id=run.id,
            label="red", hit_rules="R1", input_snapshot=SNAPSHOT,
            percentile_source="school", valid_from=generated_on, valid_to=None,
        ))
        # 重生成那几条测试要「次日也有一行分层结果」（regenerate 的 as_of 是次日）
        if generated_on == AS_OF:
            session.add(StratificationResult(
                student_id=student.id, computed_on=AS_OF + dt.timedelta(days=1),
                batch_id=run.id, label="red", hit_rules="R1",
                input_snapshot=SNAPSHOT, percentile_source="school",
                valid_from=AS_OF + dt.timedelta(days=1), valid_to=None,
            ))
        session.flush()

        row = Prescription(
            student_id=student.id, generated_on=generated_on, batch_id=run.id,
            template_ref="RED-END-ABN-01", microcycle_weeks=MICROCYCLE_WEEKS,
            label_at_generation="red",
            training_package=training_package_payload(pkg),
            assembly_snapshot=dict(pkg.assembly_snapshot),
            safety_substitutions=substitutions,
            teacher_overrides=[] if overrides is None else overrides,
            previous_had_overrides=False,
            status=status, valid_from=generated_on, valid_to=valid_to,
            trigger_reasons=["first_stratification"],
        )
        session.add(row)
        session.commit()
        ids["prescription"] = row.id
    return ids


@pytest.fixture()
def seeded(engine) -> dict:
    """一套「一个在册教师 + 一个有生效处方的学生 + 一个没有处方的学生」的库。"""
    return _seed(engine)


def _student_headers(ids: dict) -> dict:
    return {"X-Student-Id": str(ids["student"])}


def _sheet(client, ids: dict, as_of: D | None = None):
    params = {} if as_of is None else {"as_of": as_of.isoformat()}
    return client.get(
        f"/api/students/{ids['student']}/weekly-sheet",
        params=params,
        headers=_student_headers(ids),
    )


def _blocks_of_week(payload: dict, week: int) -> list[dict]:
    """一张 ``training_package`` 投影里第 ``week`` 周**全部** block（跨课摊平）。"""
    return [
        block
        for session in payload["weeks"][week - 1]["sessions"]
        for block in session["blocks"]
    ]


def _post_override(client, ids: dict, **body):
    return client.post(
        f"/api/prescriptions/{ids['prescription']}/overrides",
        json=body,
        headers=TEACHER_HEADERS,
    )


# ===========================================================================
# 批次 A —— 投影层（P4-A1 的 Critical）
# ===========================================================================


#: ``_block_payload`` 的 **10** 个键，**逐字写死且按序**（硬规矩 #35）。
#: ⚠️ 期望侧来自 :class:`app.domain.prescription.assembler.AssembledBlock` 的字段名
#: （Plan 02 的 P8-A1 数过：那 10 个字段里只有 ``weekly_volume`` 会被读模型缩放）。
_PINNED_BLOCK_KEYS = [
    "exercise_ref",
    "exercise_name",
    "video_url",
    "impact_level",
    "intensity_text",
    "hr_zone",
    "structure",
    "weekly_volume",
    "volume_unit",
    "sessions_per_week",
]


def test_the_block_projection_is_json_serialisable_without_asdict():
    """**P4-A1 的红线**：``dataclasses.asdict`` 当场炸，而投影函数不炸。

    两拍，缺一个都不能说明问题：

    ① ``json.dumps(dataclasses.asdict(sheet))`` 抛
       ``TypeError: cannot pickle 'mappingproxy' object`` ——**带 ``default=str`` 也一样**，
       因为 ``default`` 只在 ``json`` 遇到「未知类型」时才被调用，而 ``asdict`` 在
       **到达 ``json`` 之前**就死了（它对 ``Mapping`` 只做递归 ``copy.deepcopy``）。
    ② ``json.dumps(weekly_sheet_payload(sheet))`` 与
       ``json.dumps(training_package_payload(pkg))`` 都**成功**，且读回来与投影逐字相等
       （即投影的输出本来就是 JSON 干净的，不依赖 ``default=``）。

    ⚠️ 用 ``RED-END-ABN-01`` + ``C=True`` 的包：它第 1 周就有 ``hr_zone`` 非 ``None``
    的 block（``[116, 136]``）与 ``structure`` 是 ``MappingProxyType`` 的 block，
    于是①不是恒真式。addon block 的 ``structure`` 是普通 ``{}``，
    **只用 addon 的包跑不出那个 TypeError**。
    """
    import dataclasses

    pkg = _package()
    sheet = weekly_training_sheet(pkg, 1, ())

    # 前置：确实有只读映射在场，否则①会因为「没有 mappingproxy」而假绿
    proxy = [
        block.structure
        for session in pkg.weeks[0].sessions
        for block in session.blocks
        if type(block.structure).__name__ == "mappingproxy"
    ]
    assert proxy, "这个包里没有 MappingProxyType，本条会假绿"

    with pytest.raises(TypeError, match="mappingproxy"):
        json.dumps(dataclasses.asdict(sheet))
    with pytest.raises(TypeError, match="mappingproxy"):
        json.dumps(dataclasses.asdict(sheet), default=str)

    for payload in (weekly_sheet_payload(sheet), training_package_payload(pkg)):
        text = json.dumps(payload, ensure_ascii=False)
        assert json.loads(text) == payload


def test_the_block_schema_covers_exactly_the_projection_keys():
    """``response_model`` 那 5 个类的字段集 = 投影函数**真的产出**的键集（含顺序）。

    ⚠️ **这一条是 :class:`AssembledBlockRead` 那个 docstring 里承认的「第二份形状」的
    唯一静态守卫**：``response_model`` 会**过滤掉**模型上没有的键，故投影多产出一个
    字段时它在 HTTP 响应里静默消失。两侧不同源——期望侧是 Pydantic 的
    ``model_fields``，被测侧是投影函数对一个真实 block 的输出。

    ⚠️ 顺带钉住 ``kind`` 的值域**只有一个所有者**（P4-A3）：
    ``OverrideCreate.model_fields["kind"].annotation is OverrideKind``——
    即 schema 里**没有**第二份字符串清单。
    """
    pkg = _package()
    block = pkg.weeks[0].sessions[0].blocks[0]
    session = pkg.weeks[0].sessions[0]

    assert list(_block_payload(block)) == _PINNED_BLOCK_KEYS
    assert list(AssembledBlockRead.model_fields) == _PINNED_BLOCK_KEYS
    assert list(_session_payload(session)) == ["day", "focus", "blocks"]
    assert list(AssembledSessionRead.model_fields) == ["day", "focus", "blocks"]
    assert list(AssembledWeekRead.model_fields) == ["week", "delta", "sessions"]
    assert list(TrainingPackageRead.model_fields) == [
        "template_id", "template_version", "paused", "weeks",
    ]
    assert list(WeeklySheetRead.model_fields) == [
        "week", "factor", "reasons", "sources", "paused", "sessions",
    ]
    assert list(OverrideRecordRead.model_fields) == [
        "kind", "target", "old_value", "new_value", "reason",
        "teacher_staff_no", "applied_at",
    ]
    # P4-A3：kind 的值域直接引 OverrideKind，schema 里没有第二份字符串
    assert OverrideCreate.model_fields["kind"].annotation is OverrideKind


def test_training_package_from_is_the_exact_inverse_of_the_payload():
    """**JSON 列 → ``TrainingPackage`` 的反向映射**逐格可逆（P4-A1 的另一半）。

    ⚠️ 这一半在 Plan 02 结案时**不存在**，而且是它逐字交给 Plan 03 的活
    （``tests/pipeline/test_prescription_stage.py`` 的
    ``test_db_rows_reach_the_read_model_with_their_order_intact`` 那段注释：
    「JSON → ``TrainingPackage`` 的反向映射今天不存在（那是 Plan 03 的 API 层的活）」）。
    没有它，``weekly_training_sheet`` 与 ``apply_overrides`` 都拿不到一个
    ``TrainingPackage``——它们只吃 dataclass，而库里的两个 JSON 列是 dict。

    **三拍**：

    ① 经过一次**真的 JSON 往返**（``dumps`` → ``loads``，即「落库再读回来」）之后
       重建出来的包，它的 ``weeks`` 与原包 ``==``。
       ⚠️ 这一拍同时钉住三个「JSON 没有那个类型」的格子：``hr_zone`` 的
       ``tuple`` ↔ ``list``、``impact_level`` 的枚举 ↔ ``.value``、
       ``structure`` 的 ``MappingProxyType`` ↔ ``dict``
       （``mappingproxy == dict`` 在 CPython 上为真，故 ``==`` 比得出「值相同」）。
    ② 重建之后再投影一次，与库里那一份**逐字相同**（投影是不动点）。
       ⚠️ 这一拍抓的是①抓不到的那类：一个字段在反向时被丢掉、又在正向时补一个缺省值，
       ①的 ``==`` 可能仍然成立（例如 ``paused`` 的缺省是 ``False``），而②会露出来。
    ③ ``assembly_snapshot`` 的**键集**与 ``hrmax`` 那一格原样带过来。
       ⚠️ 只比键集与那一格、不比整个 dict：``week_deltas`` 在 JSON 往返之后是 ``list``
       而原包是 ``tuple``（JSON 没有 tuple），整体 ``==`` 必然为假——
       而那一格没有任何读侧（``apply_overrides`` 只读 ``hrmax``）。
    """
    pkg = _package()
    payload = training_package_payload(pkg)
    snapshot = dict(pkg.assembly_snapshot)
    # 一次真的 JSON 往返 = 「写进 JsonText 列、再读回来」
    payload2 = json.loads(json.dumps(payload, ensure_ascii=False))
    snapshot2 = json.loads(json.dumps(snapshot, ensure_ascii=False))

    restored = training_package_from(payload2, snapshot2)

    assert restored.weeks == pkg.weeks
    assert restored.template_id == pkg.template_id == "RED-END-ABN-01"
    assert restored.template_version == pkg.template_version
    assert restored.paused is pkg.paused is False

    assert training_package_payload(restored) == payload2

    assert sorted(restored.assembly_snapshot) == sorted(snapshot)
    assert restored.assembly_snapshot["hrmax"] == snapshot["hrmax"] == 194.0
    # addon 的 structure 是普通空 dict（模板 block 那一份是 mappingproxy）
    kinds = {
        type(block.structure).__name__
        for week in restored.weeks for s in week.sessions for block in s.blocks
    }
    assert kinds == {"dict"}, kinds


def test_an_override_record_survives_the_json_column_and_keeps_its_order():
    """``OverrideRecord`` ↔ ``teacher_overrides`` 那个 JSON 列表，**双向可逆且不重排**。

    **三拍**：

    ① 7 个键逐字（P4-A3 数过：``OverrideRecord`` 的 7 个字段**全部无缺省**）。
    ② 一次真的 JSON 往返之后读回来，与原记录 ``==``。
       ⚠️ **这一拍成立的前提是 ``applied_at`` 的 ``isoformat()`` 是单射**（硬规矩 #99）：
       写入侧是**不带 tzinfo** 的 ``datetime``，微秒精度，
       :func:`datetime.datetime.fromisoformat` 逐位还原。
    ③ **``applied_at`` 是「倒着」的时候，读回来的顺序仍是入参顺序**——
       即 ``override_records_of`` 一个都不排。
       ⚠️ 这一拍是 P4-A4 那条「不要按 ``applied_at`` 重排序」的守卫：
       Plan 02 的 5.4 定的是「多条覆盖同一目标由**列表顺序**决定、后者胜」，
       而 ``VOLUME_SCALE`` / ``INTENSITY_STEP`` 两档是**增量**的，
       顺序错了结果就错了、且**全程不报错**。
       ⚠️ **四条记录的时刻刻意是递减的**（``10:00 → 09:00 → 09:00 → 08:00``，
       中间两条还相等）：生产上 append 出来的列表时刻恒不减，故「有人给它加了一次
       ``sorted(..., key=applied_at)``」在真实数据上**看不出来**；
       只有喂一份时刻倒序的列表，那个变异才会红。⚠️ 于是本拍是**合成的**输入，
       它守的是实现（不排序），不是生产数据的形状（如实记录，硬规矩 #39）。
    """
    stamps = [
        T(2025, 9, 16, 10, 0, 0),
        T(2025, 9, 16, 9, 0, 0),
        T(2025, 9, 16, 9, 0, 0),
        T(2025, 9, 16, 8, 0, 0),
    ]
    wanted = [
        (OverrideKind.VOLUME_SCALE, None, "1.0", "0.8", "本周月考，减量"),
        (OverrideKind.PAUSE, None, "false", "true", "踝关节不适，暂停"),
        (OverrideKind.INTENSITY_STEP, None, "0", "-5", "强度降一档"),
        (OverrideKind.SUBSTITUTE_EXERCISE, FIRST_REF, FIRST_REF, "brisk_walking",
         "场地积水"),
    ]
    records = [
        OverrideRecord(
            kind=kind, target=target, old_value=old, new_value=new, reason=reason,
            teacher_staff_no=TEACHER_STAFF_NO, applied_at=at,
        )
        for (kind, target, old, new, reason), at in zip(wanted, stamps)
    ]

    payloads = [override_record_payload(record) for record in records]
    assert list(payloads[0]) == [
        "kind", "target", "old_value", "new_value", "reason",
        "teacher_staff_no", "applied_at",
    ]
    assert payloads[0]["kind"] == "volume_scale"  # .value，不是枚举成员
    assert payloads[0]["applied_at"] == "2025-09-16T10:00:00"

    round_tripped = json.loads(json.dumps(payloads, ensure_ascii=False))
    assert override_records_of(round_tripped) == records

    # ③ 的时刻确实是「倒着 + 有一对相等」，否则上面那条 == 对「排过序」无感
    assert [r.applied_at for r in records] == sorted(
        (r.applied_at for r in records), reverse=True
    )
    assert len({r.applied_at for r in records}) == 3
    assert [r.reason for r in override_records_of(round_tripped)] == [
        "本周月考，减量", "踝关节不适，暂停", "强度降一档", "场地积水",
    ]
    assert [r.kind for r in override_records_of(round_tripped)] == [
        OverrideKind.VOLUME_SCALE, OverrideKind.PAUSE,
        OverrideKind.INTENSITY_STEP, OverrideKind.SUBSTITUTE_EXERCISE,
    ]


# ===========================================================================
# 批次 B —— 四个端点的行为
# ===========================================================================


def test_current_prescription_is_404_when_there_is_none(client, seeded):
    """没有生效处方 → **404** 且 ``code == "no_active_prescription"``（计划逐字钉住）。

    ⚠️ 用**另一个学生**（夹具给他插了行、但没给他处方）：于是本条同时证明
    「404 是因为没有处方」而不是「因为整个端点坏了」——同一套夹具下
    :func:`test_the_current_prescription_is_the_active_row` 是 200。

    ⚠️ ``code`` **不是** ``not_found``：那是 :data:`app.api.errors._CODE_BY_STATUS`
    给 ``HTTPException(404)`` 的通用码，而前端要按 ``no_active_prescription`` 分支
    （「等下一次批处理」与「这个 id 打错了」是两种提示）。
    """
    got = client.get(
        f"/api/students/{seeded['other_student']}/prescriptions/current",
        params={"as_of": AS_OF.isoformat()},
        headers={"X-Student-Id": str(seeded["other_student"])},
    )
    assert got.status_code == 404, got.text
    body = got.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "detail"}
    assert body["error"]["code"] == "no_active_prescription"
    assert body["error"]["detail"] is None
    assert "处方不每天重发" in body["error"]["message"]


def test_the_current_prescription_is_the_active_row(client, seeded):
    """200 那一档（硬规矩 #50：只有 404 的话「一律 404」也能让上一条绿）。

    ⚠️ 响应是 ``PrescriptionRead``——**16 列全给**，含 5 个 ``JsonText`` 列
    （``training_package`` 是 4 周 ×4 课 ×3 block 的嵌套字典）。
    本条顺带钉住「``training_package`` 那一列的 block 形状」，
    因为下面那条 Critical 守卫要拿它当期望侧。
    """
    got = client.get(
        f"/api/students/{seeded['student']}/prescriptions/current",
        params={"as_of": AS_OF.isoformat()},
        headers=_student_headers(seeded),
    )
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["id"] == seeded["prescription"]
    assert body["status"] == "active"
    assert body["template_ref"] == "RED-END-ABN-01"
    assert body["generated_on"] == AS_OF.isoformat()
    assert body["valid_to"] == VALID_TO.isoformat()
    assert body["teacher_overrides"] == []
    assert body["previous_had_overrides"] is False
    assert list(body["training_package"]) == [
        "template_id", "template_version", "paused", "weeks",
    ]
    first = body["training_package"]["weeks"][0]["sessions"][0]["blocks"][0]
    assert list(first) == _PINNED_BLOCK_KEYS
    assert first["exercise_ref"] == FIRST_REF
    assert first["weekly_volume"] == FIRST_VOLUME


def test_a_needs_review_prescription_is_still_the_current_one_and_says_so(client, engine):
    """``status == "needs_review"`` 的那一张**照样是 current**，且把 ``status`` 带出来。

    ⚠️ **这一格有张力，本条把它钉住而不是掩盖它**：
    :func:`app.pipeline.prescription_stage.active_or_needs_review` 的 docstring 说
    「一张待人工复核的处方不能被学生端当成生效处方执行」，而计划 Interfaces 逐字写的是
    ``status ∈ {active, needs_review}``。落地口径是**返回它 + 带上 ``status``**，
    于是「该不该让学生照着练」这个判断落在前端（Plan 04 必须挂横幅）。
    反过来做（回 404）更糟：学生会看到「你没有训练单」，而他其实有一张待复核的。

    ⚠️ ``valid_to`` 一并置 ``None``（那一列的注释：``needs_review`` 的处方还没有
    确定的有效期），于是本条同时覆盖了 ``_current_prescription`` 里
    ``valid_to IS NULL`` 那一支。
    """
    ids = _seed(engine, status="needs_review", valid_to=None)
    got = client.get(
        f"/api/students/{ids['student']}/prescriptions/current",
        params={"as_of": AS_OF.isoformat()},
        headers={"X-Student-Id": str(ids["student"])},
    )
    assert got.status_code == 200, got.text
    assert got.json()["status"] == "needs_review"
    assert got.json()["valid_to"] is None


@pytest.mark.parametrize("status", ["replaced", "archived"])
def test_a_replaced_or_archived_prescription_is_not_the_current_one(
    client, engine, status
):
    """``replaced`` / ``archived`` 两档**都不算**当前生效（:data:`CURRENT_STATUSES` 的反面）。

    ⚠️ **``parametrize`` 而不是一个 ``for`` 循环**：两档各要一套**干净的库**，
    而 ``_seed`` 会插一行 ``semester``（``name`` 上有唯一约束），
    同一个 ``engine`` 夹具里跑第二遍会当场 ``IntegrityError``。
    ⚠️ 两档都要跑：只测 ``replaced`` 的话，一个把 ``CURRENT_STATUSES`` 写成
    ``("active", "needs_review", "archived")`` 的改动照样绿。
    """
    ids = _seed(engine, status=status, second_student=False)
    got = client.get(
        f"/api/students/{ids['student']}/prescriptions/current",
        params={"as_of": AS_OF.isoformat()},
        headers={"X-Student-Id": str(ids["student"])},
    )
    assert got.status_code == 404, (status, got.text)
    assert got.json()["error"]["code"] == "no_active_prescription", status


def test_a_day_before_valid_from_is_not_the_current_prescription_yet(client, engine):
    """``valid_from`` **之前**的那一天 → 404（spec §8.4「周一之前先生成、下周一才生效」）。

    ⚠️ 这一条是 ``_current_prescription`` 里 ``valid_from <= as_of`` 那个条件的唯一守卫：
    删掉它，一张「下周一才生效」的处方会在生效日之前就被学生端读到，
    而那正是 :attr:`app.db.models.prescription.Prescription.valid_from` 的列注释
    说要分两列（``generated_on`` 与 ``valid_from``）的理由。
    ⚠️ 那一列的注释也如实记了「今天生产上两者恒相等」，故本夹具是**手工**把它们分开的。
    """
    ids = _seed(engine, generated_on=AS_OF, valid_to=D(2025, 10, 12))
    with Session(engine) as session:
        row = session.get(Prescription, ids["prescription"])
        # generated_on 仍是 AS_OF，而生效日从三天后才开始
        row.valid_from = AS_OF + dt.timedelta(days=3)
        session.commit()
    before = client.get(
        f"/api/students/{ids['student']}/prescriptions/current",
        params={"as_of": (AS_OF + dt.timedelta(days=1)).isoformat()},
        headers={"X-Student-Id": str(ids["student"])},
    )
    assert before.status_code == 404, before.text
    on_or_after = client.get(
        f"/api/students/{ids['student']}/prescriptions/current",
        params={"as_of": (AS_OF + dt.timedelta(days=3)).isoformat()},
        headers={"X-Student-Id": str(ids["student"])},
    )
    assert on_or_after.status_code == 200, on_or_after.text


def test_the_last_day_of_the_microcycle_is_still_current(client, seeded):
    """``valid_to`` 是**闭区间**的末日，故那一天仍然生效（``>=`` 而不是 ``>``）。

    ⚠️ 与 :func:`app.pipeline.prescription_stage.valid_to_of` 那条「差一天、
    而且应该差一天」是同一件事的两端：末日那天旧处方仍然生效，
    次日由触发 3 换新的一张。改成 ``>`` 的话末日当天学生就看不到训练单了。
    """
    last = client.get(
        f"/api/students/{seeded['student']}/prescriptions/current",
        params={"as_of": VALID_TO.isoformat()},
        headers=_student_headers(seeded),
    )
    assert last.status_code == 200, last.text
    after = client.get(
        f"/api/students/{seeded['student']}/prescriptions/current",
        params={"as_of": (VALID_TO + dt.timedelta(days=1)).isoformat()},
        headers=_student_headers(seeded),
    )
    assert after.status_code == 404, after.text
    assert after.json()["error"]["code"] == "no_active_prescription"


def test_weekly_sheet_carries_volume_unit_per_block(client, seeded):
    """每个 block 都带 ``volume_unit``，且**同一周里三个值并存**。

    ⚠️ ``{min, reps, unspecified}`` 这三个字面量就是 Plan 02 的 P8-A1 用来否掉
    「跨单位周总量」的那个实测值域。本条把它钉在 **HTTP 响应**上：
    前端要显示总量，必须自己按这三个值分列。
    """
    got = _sheet(client, seeded, AS_OF)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["week"] == 1
    assert body["factor"] == 1.0
    assert body["reasons"] == [] and body["sources"] == []
    assert body["paused"] is False

    blocks = [b for s in body["sessions"] for b in s["blocks"]]
    assert len(blocks) == 12, "4 课 × 3 block（含 addon）"
    assert all("volume_unit" in b for b in blocks)
    assert {b["volume_unit"] for b in blocks} == {"min", "reps", "unspecified"}
    first = body["sessions"][0]["blocks"][0]
    assert first["exercise_ref"] == FIRST_REF
    assert first["weekly_volume"] == FIRST_VOLUME
    assert first["volume_unit"] == "min"
    assert first["hr_zone"] == [116, 136]
    assert first["structure"] == {"sets": 4, "work_min": 3, "rest_min": 2}
    assert first["sessions_per_week"] == 4
    second = body["sessions"][0]["blocks"][1]
    assert second["volume_unit"] == "reps"
    assert second["weekly_volume"] == SECOND_VOLUME
    assert second["hr_zone"] is None


def test_the_weekly_sheet_blocks_are_field_for_field_the_training_package_ones(
    client, seeded
):
    """⚠️⚠️ **P4-A1 要求的那条 Critical 守卫**：学生端本周训练单里的 block 与
    教师端从 ``GET /api/prescriptions/{id}`` 读到的 ``training_package`` 里的 block
    **逐字段同形**。

    **两侧是两条真的 HTTP 路径、两个 ``response_model``**：

    * 学生侧走 ``WeeklySheetRead`` → ``AssembledSessionRead`` → ``AssembledBlockRead``；
    * 教师侧走 ``PrescriptionRead.training_package: dict``（**没有**嵌套模型，
      故它是投影函数的**原样**输出）。

    ⚠️ 于是本条能抓到「``response_model`` 把投影多产出的字段静默过滤掉了」那一类失效
    ——那正是 :class:`AssembledBlockRead` 的 docstring 里承认的代价，
    而 :func:`test_the_block_schema_covers_exactly_the_projection_keys` 抓不到它
    （那一条比的是**类**与**函数**，两边都不经过 HTTP）。

    ⚠️ **``factor`` 必须是 ``1.0``** 本条才成立（``weekly_training_sheet`` 会缩放
    ``weekly_volume``）：夹具不插任何 ``weekly_adjustment`` 行，故该周系数是裸的 1.0，
    而 ``round(x × 1.0, 1) == x``（装配器已经 round 过一次）。
    ⚠️ 也**必须没有任何教师覆盖**：学生侧走的是
    :func:`app.pipeline.prescription_stage.effective_package`（骨架 × 覆盖），
    教师侧读的是 ``training_package`` 那一列（**永远是算法基线**）。
    两者只在「零覆盖」时相等——而那正是本条要钉的：**同形**说的是字段集与投影规则，
    不是「两侧永远是同一份数据」（它们刻意不是）。

    ⚠️ **非空转**（硬规矩 #50）：断言 block 数与三个 ``volume_unit`` 都在场，
    于是「两边都是空列表」这种恒等不会让它假绿。
    """
    student_side = _sheet(client, seeded, AS_OF)
    assert student_side.status_code == 200, student_side.text
    teacher_side = client.get(f"/api/prescriptions/{seeded['prescription']}")
    assert teacher_side.status_code == 200, teacher_side.text

    sheet = student_side.json()
    package = teacher_side.json()["training_package"]
    assert sheet["factor"] == 1.0, "有系数时两侧的量本就不同，本条要在零系数下比形状"

    blocks = [b for s in sheet["sessions"] for b in s["blocks"]]
    reference = _blocks_of_week(package, 1)
    assert len(blocks) == len(reference) == 12
    assert {b["volume_unit"] for b in blocks} == {"min", "reps", "unspecified"}

    # 逐课、逐 block、逐字段（dict 相等已经含「键集相同」）
    assert sheet["sessions"] == package["weeks"][0]["sessions"]
    for got, want in zip(blocks, reference):
        assert list(got) == _PINNED_BLOCK_KEYS
        assert got == want, got["exercise_ref"]


def test_the_sheet_has_no_cross_unit_total_field(client, seeded):
    """**响应 JSON 里没有一个把 min 与 reps 加在一起的键**（Plan 02 的 P8-A1 传导）。

    ⚠️ 断言方式是**键集相等** + 「任何一层都不出现 ``total``」，不是「某个键不存在」：
    后者会被改名骗过（``total_volume`` → ``volume_sum``），而前者对**加任何一个键**都红。

    ⚠️ 理由逐字照 Plan 02：``volume_unit`` 的值域是 ``{min, reps, unspecified}``
    且同一周里三个并存（上一条钉住了），把它们相加就是 Plan 02 Task 5 的 F1-1 那个
    「混合量纲 float」错误——**48 分钟 + 120 次 = 168 什么？**
    故整份响应里**唯一的 ``float`` 是 ``factor``**，前端要显示总量必须自己按单位分列。
    """
    body = _sheet(client, seeded, AS_OF).json()
    assert set(body) == {"week", "factor", "reasons", "sources", "paused", "sessions"}

    def walk(node, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                assert "total" not in key.lower(), path + "/" + key
                yield from walk(value, path + "/" + key)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                yield from walk(value, f"{path}[{index}]")
        else:
            yield path, node

    leaves = dict(walk(body))
    floats = [path for path, value in leaves.items() if isinstance(value, float)]
    # 顶层的 float **恰好只有 factor** 一个（walk 给出的路径以 "/" 开头，故顶层是
    # count("/") == 1 的那些）。block 里的 weekly_volume 也是 float，但它们
    # **按单位分列**（每一个都与自己的 volume_unit 在同一个 block 里），故不是「跨单位汇总」。
    assert [path for path in floats if path.count("/") == 1] == ["/factor"]
    # 每个 weekly_volume 都与它的 volume_unit 在同一个 block 里（即「分列」是真的）
    for session in body["sessions"]:
        for block in session["blocks"]:
            assert set(block) >= {"weekly_volume", "volume_unit"}


def test_an_unspecified_addon_block_comes_back_with_zero_volume(client, seeded):
    """``volume_unit == "unspecified"`` 的 addon block → ``weekly_volume`` 恒 ``0.0``
    （Plan 02 的 P5-A3 传导第 3 条），**且带一个系数之后仍是 ``0.0``**。

    ⚠️ 两拍：第二拍先 POST 一条 ``volume_scale = 0.5``，再读训练单——
    ``round(0.0 × 0.5, 1) == 0.0``，故那一档不会因为在读模型里被缩放而变成 ``None``
    或消失。⚠️ 它的 ``structure`` 是一个**空 dict**（addon 没有结构键），
    而 ``intensity_text`` 是那句「附加模块（模板未指定强度，见 spec §14）」——
    前端要靠这两格提示「这个附加模块的量待教师指定」。
    """
    before = _sheet(client, seeded, AS_OF).json()
    addons = [
        b for s in before["sessions"] for b in s["blocks"]
        if b["volume_unit"] == "unspecified"
    ]
    assert len(addons) == 4, "每周 4 课各追加一个 addon"
    for addon in addons:
        assert addon["exercise_ref"] == ADDON_REF
        assert addon["weekly_volume"] == 0.0
        assert addon["structure"] == {}
        assert "附加模块" in addon["intensity_text"]

    posted = _post_override(
        client, seeded, kind="volume_scale", target=None, old_value="1.0",
        new_value="0.5", reason="本周月考，减量",
    )
    assert posted.status_code == 200, posted.text
    after = _sheet(client, seeded, AS_OF).json()
    for addon in [
        b for s in after["sessions"] for b in s["blocks"]
        if b["volume_unit"] == "unspecified"
    ]:
        assert addon["weekly_volume"] == 0.0
    # 同一个覆盖对**有量**的 block 确实生效了（否则上一条断言是恒真式）
    assert after["sessions"][0]["blocks"][0]["weekly_volume"] == 19.2


def test_the_weekly_sheet_multiplies_every_adjustment_of_that_week(client, engine, seeded):
    """spec §8.4 的原文：**骨架第 N 周 × 本周调整系数**（P4-A2 的传导）。

    ⚠️ **``weekly_factors_of`` 是 Plan 02 Task 8 已经交付的**（P4-A2：直接调用、
    不要重写），本条钉的是「端点真的调了它、并且**相乘而不是取最后一条**」。

    三条断言各有各的牙：

    * ``factor == 0.7200000000000001`` —— **裸乘积、不 round**（``0.8 × 0.9``）。
      round 一次会让教师端显示的系数与 ``weekly_volume`` 的实际倍数对不上账
      （Plan 02 的 P5-A6）。⚠️ 期望值字面写死，不是 ``0.8 * 0.9`` 现场算
      （那会与被测侧同源，硬规矩 #35）。
    * ``reasons`` / ``sources`` **两条都在**、且顺序 = ``ORDER BY created_at, id``
      （取最后一条会让前一条**消失**，而 spec §8.4 说「可追溯、可回滚」）。
    * ``weekly_volume == 27.6`` —— ``round(38.4 × 0.7200000000000001, 1)``。
      ⚠️ 只有 ``weekly_volume`` 落 round，``factor`` 不落。
    * **第 2 周一件事都没有**（``week=2`` 的调整不进第 1 周的账；过滤是读模型的活）。
    """
    with Session(engine) as session:
        for week, factor, reason, source, at in (
            (1, 0.8, "本周月考，减量", "teacher", T(2025, 9, 15, 18, 0)),
            (1, 0.9, "RED_RPE_SUSTAINED", "auto", T(2025, 9, 16, 9, 0)),
            (2, 0.5, "第二周的事，不该出现在第一周", "teacher", T(2025, 9, 16, 10, 0)),
        ):
            session.add(WeeklyAdjustment(
                prescription_id=seeded["prescription"], batch_id=seeded["batch"],
                week=week, factor=factor, reason=reason, source=source, created_at=at,
            ))
        session.commit()

    body = _sheet(client, seeded, AS_OF).json()
    assert body["factor"] == 0.7200000000000001
    assert body["reasons"] == ["本周月考，减量", "RED_RPE_SUSTAINED"]
    assert body["sources"] == ["teacher", "auto"]
    assert body["sessions"][0]["blocks"][0]["weekly_volume"] == 27.6
    assert body["sessions"][0]["blocks"][1]["weekly_volume"] == 69.1  # round(96 × 0.72…, 1)

    # 第 8 天 = 第 2 周（(8 // 7) + 1）：那一周只有一条 0.5
    week2 = _sheet(client, seeded, AS_OF + dt.timedelta(days=8)).json()
    assert week2["week"] == 2
    assert week2["factor"] == 0.5
    assert week2["reasons"] == ["第二周的事，不该出现在第一周"]
    assert week2["sources"] == ["teacher"]


def test_weekly_sheet_reports_paused_and_keeps_the_sessions(client, seeded):
    """``paused=True`` 时 ``sessions`` **原样保留**（Plan 02 的 P8-A3 传导第 1 条）。

    ⚠️ 三拍，缺一个就有假绿的空间：

    ① POST 一条 ``pause`` 覆盖 → 200；
    ② GET 训练单 → ``paused is True``；
    ③ **``sessions`` 与暂停之前逐字相同**（block 数、每个 ``weekly_volume``）。

    ⚠️ 第③拍是本条的全部价值：「暂停」与「本周量为 0」是两件不同的事，
    在后端把 ``sessions`` 清空会让两者在学生端长得一模一样，
    而前端**只能**靠 ``paused`` 这一格决定渲染什么。
    ⚠️ 而 ``paused`` 只有 ``OverrideKind.PAUSE`` 能置位——
    这也是「本周训练单必须读**覆盖之后**的包」的理由：
    读 ``training_package`` 那一列（算法基线）的话 ``paused`` 永远是 ``False``，
    教师的暂停到不了学生端。
    """
    before = _sheet(client, seeded, AS_OF).json()
    assert before["paused"] is False

    posted = _post_override(
        client, seeded, kind="pause", target=None, old_value="false",
        new_value="true", reason="踝关节不适，本周暂停",
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["training_package"]["paused"] is True

    after = _sheet(client, seeded, AS_OF).json()
    assert after["paused"] is True
    assert after["sessions"] == before["sessions"], "暂停不得清空 sessions（P8-A3）"
    assert [b["weekly_volume"] for s in after["sessions"] for b in s["blocks"]] == [
        b["weekly_volume"] for s in before["sessions"] for b in s["blocks"]
    ]
    # ⚠️ 而库里那一列（算法基线）的 paused 仍是 False —— 覆盖不写进它
    row = client.get(f"/api/prescriptions/{seeded['prescription']}").json()
    assert row["training_package"]["paused"] is False


def test_a_day_beyond_the_microcycle_is_404_with_its_own_code(client, engine):
    """``as_of`` 落在微周期之外 → 404，且 ``code`` 是**它自己的**
    （:data:`OUTSIDE_MICROCYCLE`），不是 ``no_active_prescription``。

    ⚠️ **两个码是两个不同的问题**，故本条同时钉住「它们不混」：
    ``no_active_prescription`` = 你压根没有处方；``outside_microcycle`` =
    你有处方、但你问的那一天不在它的 4 周里。合成一个码的话前端无从区分，
    而两者的正确 UI 完全不同。

    ⚠️ **可达路径**（硬规矩 #39）：``valid_to`` 是 nullable（``needs_review`` 的处方
    还没有确定的有效期），而 ``_current_prescription`` 把 NULL 当「不设终点」放行，
    于是这一行会被选中、而 ``current_week`` 对它返回 ``None``。
    """
    ids = _seed(engine, status="needs_review", valid_to=None)
    far = client.get(
        f"/api/students/{ids['student']}/weekly-sheet",
        params={"as_of": (AS_OF + dt.timedelta(days=100)).isoformat()},
        headers={"X-Student-Id": str(ids["student"])},
    )
    assert far.status_code == 404, far.text
    body = far.json()
    assert body["error"]["code"] == "outside_microcycle"
    assert "current_week 返回 None" in body["error"]["message"]

    # 对照：同一天问 current 仍是 200（那一行确实还挂着），故两个码不是一回事
    current = client.get(
        f"/api/students/{ids['student']}/prescriptions/current",
        params={"as_of": (AS_OF + dt.timedelta(days=100)).isoformat()},
        headers={"X-Student-Id": str(ids["student"])},
    )
    assert current.status_code == 200, current.text


def test_as_of_defaults_to_the_server_clock(client, engine):
    """缺省 ``as_of`` = **服务端当天**（``api`` 是可以碰时钟的那一层）。

    ⚠️ **这是本文件唯一一条依赖真实时钟的测试**（模块 docstring 那条对策的落点：
    其余每条一律显式传 ``as_of``）。它跨过午夜跑会红——那一天里
    ``date.today()`` 变了而夹具的 ``generated_on`` 没变；
    这是一个已知且极窄的窗口，代价换来的是「缺省档真的有人看着」。

    ⚠️ 期望侧在测试里**现场**取 ``dt.date.today()``，而不是硬写一个日期：
    硬写的话本条明天就红，而它的被测对象是「缺省 = 今天」这件事本身。
    """
    today = dt.date.today()
    ids = _seed(
        engine,
        generated_on=today,
        valid_to=today + dt.timedelta(days=27),
        second_student=False,
    )
    got = client.get(
        f"/api/students/{ids['student']}/weekly-sheet",
        headers={"X-Student-Id": str(ids["student"])},
    )
    assert got.status_code == 200, got.text
    assert got.json()["week"] == 1

    current = client.get(
        f"/api/students/{ids['student']}/prescriptions/current",
        headers={"X-Student-Id": str(ids["student"])},
    )
    assert current.status_code == 200, current.text
    assert current.json()["generated_on"] == today.isoformat()


def test_an_empty_override_reason_is_422_with_the_domain_message(client, seeded, engine):
    """``reason`` 为空 → **422**，且消息**原文**是 domain 那一段（Plan 02 传导第 4 条）。

    ⚠️ **API 层刻意不再校验一遍**：那条规则的所有者是
    ``OverrideRecord.__post_init__``，在 schema 上加一个 ``min_length=1`` 就是
    第二个所有者（两处措辞会漂，而前端只看得到其中一处）。
    于是 ``code`` 是 ``unprocessable_value``（``ValueError`` 那一档），
    **不是** ``request_validation_failed``（Pydantic 那一档）——本条把这个区别钉住。

    ⚠️ 第二拍：**库里一个字都没写**（``teacher_overrides`` 仍是 ``[]``）。
    端点是「先算、后写」的，而构造 ``OverrideRecord`` 排在任何写入之前。
    """
    for bad in ("", "   "):
        got = _post_override(
            client, seeded, kind="pause", target=None, old_value="false",
            new_value="true", reason=bad,
        )
        assert got.status_code == 422, got.text
        body = got.json()
        assert body["error"]["code"] == "unprocessable_value"
        assert body["error"]["detail"] is None
        assert "一条没有理由的覆盖对研究毫无价值" in body["error"]["message"]

    with Session(engine) as session:
        row = session.get(Prescription, seeded["prescription"])
        assert row.teacher_overrides == []


def test_a_rejected_override_is_not_persisted(client, seeded, engine):
    """**先算、后写**：一次被 domain 拒绝的覆盖**不得留在库里**。

    ⚠️ 这一条是本端点最要紧的实现纪律的守卫。反过来的顺序（先写再算）会给出一个
    **看起来正常**的结果：响应是 422、而库里多了一条记录，
    于是下一次 GET 训练单照旧生效——教师看到「报错了」，而学生看到「改过了」。

    三档各跑一次（三个都是 ``apply_overrides`` 会抛 ``ValueError`` 的形状）：

    * ``weekly_frequency = "5"`` —— 模板每周只有 4 课，**不夹取**；
    * ``volume_scale = "0"`` —— 把量清零等于处方名存实亡；
    * ``substitute_exercise`` 的 ``target`` 打错 —— 命中 0 个 block，**不静默无事发生**。

    ⚠️ 每档之后都断言 ``teacher_overrides == []``，且训练单仍是骨架原样。
    """
    rejected = [
        dict(kind="weekly_frequency", target=None, old_value="4", new_value="5",
             reason="想加一课"),
        dict(kind="volume_scale", target=None, old_value="1.0", new_value="0",
             reason="想清零"),
        dict(kind="substitute_exercise", target="interval_runn", old_value="interval_runn",
             new_value="brisk_walking", reason="拼错的 ref"),
    ]
    for body in rejected:
        got = _post_override(client, seeded, **body)
        assert got.status_code == 422, (body, got.text)
        assert got.json()["error"]["code"] == "unprocessable_value", body
        with Session(engine) as session:
            row = session.get(Prescription, seeded["prescription"])
            assert row.teacher_overrides == [], body
    sheet = _sheet(client, seeded, AS_OF).json()
    assert sheet["factor"] == 1.0
    assert len(sheet["sessions"]) == 4
    assert sheet["sessions"][0]["blocks"][0]["weekly_volume"] == FIRST_VOLUME


def test_overrides_append_and_the_list_order_decides(client, seeded, engine):
    """**追加**不是替换；且**列表顺序**决定结果（P4-A4 + Plan 02 的 5.4）。

    四拍：

    ① 第一条 ``volume_scale = 0.5`` → ``overrides`` 长度 1、``38.4 → 19.2``；
    ② 第二条 ``volume_scale = 0.5`` → 长度 **2**（不是 1，即没有替换掉前一条）、
       ``19.2 → 9.6``（**相乘**，不是「后者覆盖前者」）；
    ③ 顺序 = POST 的先后（按 ``reason`` 逐个对），⚠️ 而两条的 ``applied_at``
       **很可能相同**（同一秒里连点），故这个顺序**不可能**是从时刻排出来的；
    ④ 库里那一列**确实是 ``[]`` → append → 写回**（P4-A4：那一列是 ``TEXT NOT NULL``
       的 ``JsonText``，不是另一张表），且 ``prescription`` 的**行数没变**。

    ⚠️ 服务端填的那两格也在这里一并钉住：``teacher_staff_no`` == 请求头里那个工号、
    ``applied_at`` 是一个**当天**的时刻（客户端没传它）。
    """
    first = _post_override(
        client, seeded, kind="volume_scale", target=None, old_value="1.0",
        new_value="0.5", reason="第一次减量",
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["prescription_id"] == seeded["prescription"]
    assert len(body["overrides"]) == 1
    assert body["training_package"]["weeks"][0]["sessions"][0]["blocks"][0][
        "weekly_volume"
    ] == 19.2

    second = _post_override(
        client, seeded, kind="volume_scale", target=None, old_value="0.5",
        new_value="0.5", reason="第二次减量",
    )
    assert second.status_code == 200, second.text
    body = second.json()
    assert [item["reason"] for item in body["overrides"]] == [
        "第一次减量", "第二次减量",
    ]
    assert body["training_package"]["weeks"][0]["sessions"][0]["blocks"][0][
        "weekly_volume"
    ] == 9.6
    for item in body["overrides"]:
        assert item["teacher_staff_no"] == TEACHER_STAFF_NO
        assert item["applied_at"].startswith(dt.date.today().isoformat())

    with Session(engine) as session:
        row = session.get(Prescription, seeded["prescription"])
        assert [item["reason"] for item in row.teacher_overrides] == [
            "第一次减量", "第二次减量",
        ]
        assert session.scalar(
            select(func.count()).select_from(Prescription)
        ) == 1, "追加一条覆盖不得新建处方行"
    # 学生端读到的是同一份（覆盖之后）的量
    assert _sheet(client, seeded, AS_OF).json()["sessions"][0]["blocks"][0][
        "weekly_volume"
    ] == 9.6


def test_weekly_frequency_override_lets_the_last_record_win(client, seeded):
    """``weekly_frequency`` 是**设状态**的，故「后者胜」= 列表的最后一条决定终态。

    ⚠️ 与 :func:`test_overrides_append_and_the_list_order_decides` 分工：
    那一条钉的是**增量**档（``volume_scale`` 相乘），本条钉的是**设状态**档
    （``4 → 3 → 2`` 得到 2 课，而不是 3 课）。两档在 Plan 02 的 5.4 里是分开写的，
    而它们的共同点正是「顺序由列表决定」——本条把这一点在 HTTP 上跑通。

    ⚠️ 量的重算也是承重的：``weekly_volume`` 是**周量**，砍课而不改它，
    那个数就在撒谎。``4 → 3`` 是 ``round(38.4 × 3/4, 1) = 28.8``，
    ``3 → 2`` 是 ``round(28.8 × 2/3, 1) = 19.2``——与「一步到位 ``4 → 2``」
    得到同一个数（复合不漂移，Plan 02 的 5.4 逐字写了这件事）。
    """
    for new_value, old_value in (("3", "4"), ("2", "3")):
        got = _post_override(
            client, seeded, kind="weekly_frequency", target=None,
            old_value=old_value, new_value=new_value, reason=f"砍到 {new_value} 课",
        )
        assert got.status_code == 200, got.text
    # 从**学生端**把终态读回来（不必再 POST 一条无意义的覆盖）：本周训练单走的就是
    # effective_package，故它显示的是覆盖之后的那一份。
    sheet = _sheet(client, seeded, AS_OF).json()
    assert len(sheet["sessions"]) == 2
    assert [s["day"] for s in sheet["sessions"]] == [1, 2]
    assert sheet["sessions"][0]["blocks"][0]["weekly_volume"] == 19.2
    assert sheet["sessions"][0]["blocks"][0]["sessions_per_week"] == 2
    # 覆盖作用于**所有周**（_rebuild 逐周逐课），而训练单只显示被问到的那一周，
    # 故「四周都被砍」这一格从教师侧的响应读
    body = _post_override(
        client, seeded, kind="pause", target=None, old_value="false",
        new_value="true", reason="顺便把四周的课次读回来",
    ).json()
    assert [len(w["sessions"]) for w in body["training_package"]["weeks"]] == [2, 2, 2, 2]


def test_regenerate_clears_overrides_and_sets_previous_had_overrides(client, seeded, engine):
    """**覆盖不继承**（spec §7.5）+ ``previous_had_overrides`` 是那一列的唯一载体（P6-A2）。

    五拍，每一拍各钉一件事：

    ① 先 POST 一条覆盖，于是旧那张的 ``teacher_overrides`` 非空；
    ② POST regenerate（``as_of`` = 次日）→ **200**，响应是新那一行；
    ③ 新行的 ``teacher_overrides == []``（覆盖不继承）而
       ``previous_had_overrides is True``——⚠️ **这一格是「界面提示『该生上次存在
       人工覆盖』」的唯一载体**，它**不是** ``assembly_snapshot`` 里的键
       （往快照加键会让 Plan 02 钉死的「12 键 / +3 键」两条守卫变红）；
    ④ ``trigger_reasons == ["teacher_requested"]``（spec §5.2 触发 5，
       且**只有**它：分层标签没变、微周期没到、没有新采集）；
    ⑤ 旧那张被置 ``replaced``、而它的 ``valid_to`` **一个字没改**
       （那一列必须能被离线复算，spec §4.3）。
    """
    posted = _post_override(
        client, seeded, kind="volume_scale", target=None, old_value="1.0",
        new_value="0.8", reason="本周月考，减量",
    )
    assert posted.status_code == 200, posted.text
    old_id = seeded["prescription"]
    next_day = AS_OF + dt.timedelta(days=1)

    got = client.post(
        f"/api/prescriptions/{old_id}/regenerate",
        params={"as_of": next_day.isoformat()},
        headers=TEACHER_HEADERS,
    )
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["id"] != old_id
    assert body["student_id"] == seeded["student"]
    assert body["generated_on"] == next_day.isoformat()
    assert body["teacher_overrides"] == []
    assert body["previous_had_overrides"] is True
    assert body["trigger_reasons"] == ["teacher_requested"]
    assert body["status"] == "active"
    assert body["template_ref"] == "RED-END-ABN-01"
    # 骨架回到算法基线：那一条 0.8 的覆盖不再影响量
    assert body["training_package"]["weeks"][0]["sessions"][0]["blocks"][0][
        "weekly_volume"
    ] == FIRST_VOLUME
    # assembly_snapshot 的键集仍是 Plan 02 钉死的那 12 + 3（本 Task 一个都没加）
    assert len(body["assembly_snapshot"]) == 15

    old = client.get(f"/api/prescriptions/{old_id}").json()
    assert old["status"] == "replaced"
    assert old["valid_to"] == VALID_TO.isoformat(), "换处方不得改写上一张的 valid_to"
    assert [item["reason"] for item in old["teacher_overrides"]] == ["本周月考，减量"]

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Prescription)) == 2


def test_regenerating_twice_on_the_same_day_returns_200_and_one_row(client, seeded, engine):
    """同一天重复点「重新生成」→ 两次都 **200**、库里仍是**一行**（计划的显式决定）。

    ⚠️ **不是 409**：机制是 ``UniqueConstraint("student_id", "generated_on")`` +
    :func:`app.db.repo.upsert`（第二次命中更新分支），而**教师点两次
    「重新生成」不该看到报错**。

    ⚠️ 第二拍（``status`` 仍是 ``active``）是**过度确定**的，如实记录（硬规矩 #39）：
    它有**两条**互不依赖的机制在保——``_replace_previous`` 的严格小于
    （同一天时 ``previous`` 就是正在被 upsert 的那一行，不该动它）与
    ``_prescription_values`` 也写 ``status``（upsert 的更新分支会把它写回 ``active``）。
    本 Task 的变异自证实测：单独把 ``<`` 改成 ``<=``，本条**仍绿**（两步互相抵消）。
    故这一拍钉的是**可观测行为**（教师点两次之后那张处方仍然生效），
    不是其中任何一条实现。
    """
    url = f"/api/prescriptions/{seeded['prescription']}/regenerate"
    params = {"as_of": AS_OF.isoformat()}
    first = client.post(url, params=params, headers=TEACHER_HEADERS)
    assert first.status_code == 200, first.text
    second = client.post(url, params=params, headers=TEACHER_HEADERS)
    assert second.status_code == 200, second.text

    assert first.json()["id"] == second.json()["id"] == seeded["prescription"]
    assert second.json()["status"] == "active"
    assert second.json()["generated_on"] == AS_OF.isoformat()
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Prescription)) == 1


def test_regenerate_for_a_student_without_enough_data_is_422_not_a_silent_noop(
    client, engine, seeded
):
    """``label == insufficient_data`` 的学生点「重新生成」→ **422 且带着原因**。

    ⚠️ **这一条是 Plan 02 报为最高优先级关切的那个形状的落点**：
    :func:`~app.domain.prescription.triggers.evaluate_triggers` 对这一档
    **无条件**返回空 tuple（连 ``teacher_requested=True`` 也不例外），
    而它「没有任何渠道把『为什么返回空 tuple』传出来」——批处理侧用
    ``PrescriptionReport.skipped_reasons`` + 一条 ``warning`` 日志留痕，
    而 HTTP 侧必须**回一个错**，否则教师点了按钮、什么也没发生、又查不出原因。

    ⚠️ 第二拍：库里那一行**一个字没变**（不是一张 ``status`` 被改掉的旧处方）。
    """
    with Session(engine) as session:
        row = session.scalar(
            select(StratificationResult).where(
                StratificationResult.student_id == seeded["student"],
                StratificationResult.computed_on == AS_OF,
            )
        )
        row.label = "insufficient_data"
        session.commit()

    got = client.post(
        f"/api/prescriptions/{seeded['prescription']}/regenerate",
        params={"as_of": AS_OF.isoformat()},
        headers=TEACHER_HEADERS,
    )
    assert got.status_code == 422, got.text
    body = got.json()
    assert body["error"]["code"] == "unprocessable_value"
    assert "insufficient_data" in body["error"]["message"]
    assert "不会有任何效果" in body["error"]["message"]

    after = client.get(f"/api/prescriptions/{seeded['prescription']}").json()
    assert after["status"] == "active"
    assert after["generated_on"] == AS_OF.isoformat()


def test_a_student_cannot_read_another_students_weekly_sheet(client, seeded):
    """**Review Focus 第 1 条的字面形状**：A 用 ``X-Student-Id`` 读 B 的训练单 → 403。

    ⚠️ **红绿两档同时在场**（硬规矩 #50）：只有 403 的话，一个恒抛 403 的闸门也能全绿。
    故四拍：① A 读 B → 403；② B 读 A → 403（方向对称）；③ A 读 A → 200；
    ④ 不带头 → **401**（不是 403：缺身份与越权是两个码，
    ``tests/api/test_scope.py`` 钉的是那两个依赖，本条钉的是它们**真的被挂上了**）。

    ⚠️ 同一个闸门也挂在 ``prescriptions/current`` 上，故第⑤拍一并跑：
    只测 ``weekly-sheet`` 的话，另一个端点漏挂 ``require_scope`` 也照样绿。
    """
    alice = str(seeded["student"])
    bob = str(seeded["other_student"])
    assert alice != bob

    cross = client.get(
        f"/api/students/{bob}/weekly-sheet",
        params={"as_of": AS_OF.isoformat()},
        headers={"X-Student-Id": alice},
    )
    assert cross.status_code == 403, cross.text
    assert cross.json()["error"]["code"] == "forbidden"

    backwards = client.get(
        f"/api/students/{alice}/weekly-sheet",
        params={"as_of": AS_OF.isoformat()},
        headers={"X-Student-Id": bob},
    )
    assert backwards.status_code == 403, backwards.text

    own = client.get(
        f"/api/students/{alice}/weekly-sheet",
        params={"as_of": AS_OF.isoformat()},
        headers={"X-Student-Id": alice},
    )
    assert own.status_code == 200, own.text

    anonymous = client.get(
        f"/api/students/{alice}/weekly-sheet", params={"as_of": AS_OF.isoformat()}
    )
    assert anonymous.status_code == 401, anonymous.text
    assert anonymous.json()["error"]["code"] == "unauthenticated"

    cross_current = client.get(
        f"/api/students/{bob}/prescriptions/current",
        params={"as_of": AS_OF.isoformat()},
        headers={"X-Student-Id": alice},
    )
    assert cross_current.status_code == 403, cross_current.text


def test_the_teacher_side_rejects_an_unknown_or_missing_staff_no(client, seeded, engine):
    """教师侧的三档：**缺头 401** / **不在册 403** / **在册 200**。

    ⚠️ 「不在册 → 403」那一档是 :func:`app.api.deps.require_teacher` 存在的理由：
    ``teacher_staff_no`` 会被写进 ``prescription.teacher_overrides``，
    而 spec §7.5 末段把那些记录当**研究数据**（「学期末回答教师在哪些环节最不信任
    算法」）——一条挂在不存在的人身上的覆盖在事后**无从归属**，等于让它作废。

    ⚠️ 第三拍（在册 → 200）是绿档：没有它，「一律 403」也能让前两拍全绿。
    ⚠️ 第四拍：**403 那一档一个字都没写进库**（闸门在写入之前）。
    """
    url = f"/api/prescriptions/{seeded['prescription']}/overrides"
    body = dict(kind="pause", target=None, old_value="false", new_value="true",
                reason="踝关节不适")

    missing = client.post(url, json=body)
    assert missing.status_code == 401, missing.text
    assert missing.json()["error"]["code"] == "unauthenticated"

    unknown = client.post(url, json=body, headers={"X-Teacher-Staff-No": "WHATEVER"})
    assert unknown.status_code == 403, unknown.text
    assert unknown.json()["error"]["code"] == "forbidden"
    assert "不是一个在册教师" in unknown.json()["error"]["message"]

    blank = client.post(url, json=body, headers={"X-Teacher-Staff-No": "   "})
    assert blank.status_code == 401, blank.text

    with Session(engine) as session:
        assert session.get(Prescription, seeded["prescription"]).teacher_overrides == []

    ok = client.post(url, json=body, headers=TEACHER_HEADERS)
    assert ok.status_code == 200, ok.text
    assert ok.json()["overrides"][-1]["teacher_staff_no"] == TEACHER_STAFF_NO


def test_the_two_post_endpoints_are_the_only_writers_of_that_table(client, seeded):
    """``prescriptions`` 在 CRUD 目录里是 ``writable=False``，故它的 POST/PATCH/DELETE
    **一律 405**——本模块的两个 POST 是那张表**唯一**的写入方。

    ⚠️ 这一条钉的是 :mod:`app.api.routers` 模块 docstring 里那条
    「让重叠不存在」的对策在 Task 4 之后仍然成立：
    ``POST /api/prescriptions`` 根本没有注册，故不存在「泛型 CRUD 与特例端点
    谁先注册谁生效」的耦合。
    ⚠️ 而 ``POST /api/prescriptions/{id}/overrides`` 是**另一条路径**
    （多一段），它不与 ``POST /api/prescriptions`` 同形，故两者不冲突。
    """
    assert client.post("/api/prescriptions", json={}).status_code == 405
    assert client.patch(
        f"/api/prescriptions/{seeded['prescription']}", json={"status": "archived"}
    ).status_code == 405
    assert client.delete(f"/api/prescriptions/{seeded['prescription']}").status_code == 405
    # 绿档：读一侧照常开放
    assert client.get(f"/api/prescriptions/{seeded['prescription']}").status_code == 200
    assert client.get("/api/prescriptions").status_code == 200


# ===========================================================================
# 批次 C —— 前后端对接面（P4-A5 / P4-A3）
# ===========================================================================


def test_the_identity_headers_are_registered_as_openapi_security_schemes(client):
    """**P4-A5**：两个身份请求头在 ``/openapi.json`` 里各有一格 ``apiKey`` securityScheme。

    四拍，每一拍各挡一个失效形态：

    ① ``components.securitySchemes`` **恰好两格**，且每格的 ``type == "apiKey"`` /
       ``in == "header"`` / ``name`` == 那个请求头的字面名。
       ⚠️ 不注册的话 Swagger UI 上**没有地方能填**、生成的 TS 客户端**也不知道要发**，
       前端一接就撞 401 且不知道为什么。
    ② 每个**特例**端点的 ``security`` 指着**对的那一格**（学生侧要学生头、
       教师侧要教师头）。⚠️ 指错了的话 Swagger 会让教师端点收学生头。
    ③ **23 个 CRUD 资源的端点一个都不带 ``security``**：它们不要求身份，
       而 OpenAPI 上多出来的要求会让前端以为每个 CRUD 都要登录。
    ④ spec **顶层没有** ``security``（全局要求）：本仓的口径是「按端点声明」，
       一个全局要求会把 ``/api/health`` 与 ``/docs`` 一起圈进去。

    ⚠️⚠️ **②③ 两拍共用一份 :data:`expected` 清单，而它会随每个 Task 增长**：
    本条写的时候是 Task 4 的 **4** 项，Plan 03 Task 5 起是 **11** 项（+ §8.1 三源采集
    的七个），Task 7 起是 **12** 项（+ ``POST /api/alerts/{alert_id}/handle``），
    Task 8 起是 **17** 项（+ 大屏两个 / 教师端读单个学生的训练单 / 学生首页 /
    通知已读），**Task 9 起是 18 项**（+ ``POST /api/pipeline/run-daily``）。
    ⚠️ ③ 那一拍是「除清单之外无 ``security``」的**全仓级**断言，
    故 Task 8/9 每加一个带身份的特例端点都要回来往这份清单里加一行——
    这是**有意的**：它逼着「哪些端点要身份」这件事有一份可读的全貌，
    而不是散在**六个** router 里各自声明（``catalog`` / ``feedback`` / ``prescription`` /
    ``alerts`` / ``dashboard`` / ``pipeline``——⚠️ 本处此前印的是「七个」，而 router 文件
    自 Task 9 建出 :mod:`app.api.routers.pipeline` 之后**恰好是六个**，计划 File Structure
    在本目录下列的 7 个文件里第 7 个是 ``__init__.py``、它不声明任何端点；
    且 ``catalog`` 那 23 个资源一个 ``Security`` 都不挂，故真正声明的是**五个**）。
    ⚠️ 代价如实记录（硬规矩 #39）：
    它也会因为「有人给一个 CRUD 资源错挂了 ``Security``」而红，
    而那次的报错信息会指向本文件、不是指向犯错的那个 router
    （Task 7 就撞了一次：新端点没登记进清单，③ 那一拍当场红，
    而报错指向的是本文件——**这正是它设计出来的行为**）。
    """
    spec = client.get("/openapi.json").json()
    schemes = spec["components"]["securitySchemes"]
    assert sorted(schemes) == ["X-Student-Id", "X-Teacher-Staff-No"]
    for name, scheme in schemes.items():
        assert scheme["type"] == "apiKey", name
        assert scheme["in"] == "header", name
        assert scheme["name"] == name, name
        assert scheme["description"], name

    paths = spec["paths"]
    expected = {
        # --- Task 4：处方侧四个特例端点 ---
        ("/api/students/{student_id}/prescriptions/current", "get"): "X-Student-Id",
        ("/api/students/{student_id}/weekly-sheet", "get"): "X-Student-Id",
        ("/api/prescriptions/{prescription_id}/overrides", "post"): "X-Teacher-Staff-No",
        ("/api/prescriptions/{prescription_id}/regenerate", "post"): "X-Teacher-Staff-No",
        # --- Task 5：§8.1 三源采集的七个特例端点（三个学生侧 + 四个教师侧）---
        ("/api/rpe-records", "post"): "X-Student-Id",
        ("/api/training-logs", "post"): "X-Student-Id",
        ("/api/students/{student_id}/training-logs/completion-rate", "get"):
            "X-Student-Id",
        ("/api/class-sessions/{class_session_id}/open-rpe", "post"):
            "X-Teacher-Staff-No",
        ("/api/class-sessions/{class_session_id}/rpe-status", "get"):
            "X-Teacher-Staff-No",
        ("/api/mini-tests/batch", "post"): "X-Teacher-Staff-No",
        ("/api/mini-tests/normalized", "get"): "X-Teacher-Staff-No",
        # --- Task 7：预警处置（教师侧一个）---
        # ⚠️ 它是**三段**路径，与泛型工厂为 alerts 注册的 GET /api/alerts/{alert_id}
        #    （两段）不同形，故两者并存、互不吞掉（守卫见
        #    tests/api/test_alerts_api.py::test_the_handle_route_does_not_collide_with_the_generic_crud_ones）。
        ("/api/alerts/{alert_id}/handle", "post"): "X-Teacher-Staff-No",
        # --- Task 8：大屏 / 首页 / 教师端读单个学生 / 通知已读（五个）---
        # ⚠️ 前两个的第一段 dashboard 不是任何资源的路径；第三个的第一段是
        #    teacher（**单数**），而那个资源的路径是 /api/teachers（复数）；
        #    第四个是三段而泛型的 /api/students/{student_id} 是两段；
        #    第五个是三段而 notifications 是 writable=False（泛型工厂**根本不注册**
        #    它的 POST/PATCH）。故五个都与 catalog **不同形**——而 dashboard 这个
        #    router 仍然 include 在 catalog 之前（规则是「特例一律在泛型之前」，
        #    一条不需要逐个 router 去论证「它同形吗」的规则才是能执行的规则）。
        ("/api/dashboard/class/{course_section_id}", "get"): "X-Teacher-Staff-No",
        ("/api/dashboard/weekly-class-report/{course_section_id}", "get"):
            "X-Teacher-Staff-No",
        ("/api/teacher/students/{student_id}/weekly-sheet", "get"):
            "X-Teacher-Staff-No",
        ("/api/students/{student_id}/home", "get"): "X-Student-Id",
        ("/api/notifications/{notification_id}/read", "post"): "X-Student-Id",
        # --- Task 9：手动触发批处理（教师侧一个）---
        # ⚠️ 它的第一段 pipeline **不是任何资源的路径**（23 个资源里没有叫 pipelines 的），
        #    故与 catalog 不同形、顺序不承重；而 pipeline 这个 router 仍然 include 在
        #    catalog 之前（规则是「特例一律在泛型之前」，理由逐字见上面 Task 8 那一段）。
        # ⚠️ **它是本清单里第三个「一段」路径**（另两个是 Task 5 的 ``/api/rpe-records`` 与
        #    ``/api/training-logs``），而一段路径正是「可能与泛型的 ``POST /api/<资源>``
        #    同形」的那一档：那两个资源在 RESOURCES 里是 ``writable=False``（泛型工厂
        #    **根本不注册**它们的 POST），故不重叠；``pipeline`` 则**不是任何资源**
        #    （23 个资源的路径全是复数、它是单数），两者是不同串，也不重叠。
        ("/api/pipeline/run-daily", "post"): "X-Teacher-Staff-No",
    }
    for (key, method), name in expected.items():
        assert paths[key][method]["security"] == [{name: []}], (key, method)

    crud = [
        (key, method)
        for key in paths
        if key.startswith("/api/") and key not in {k for k, _ in expected}
        for method in paths[key]
    ]
    assert len(crud) >= 70, f"CRUD 那一圈只剩 {len(crud)} 个操作，本拍可能空转"
    assert [(k, m) for k, m in crud if paths[k][m].get("security")] == []

    assert spec.get("security") is None


def test_the_override_request_model_cannot_carry_the_two_server_filled_fields(
    client, seeded, engine
):
    """**P4-A3**：请求体是 **5 个字段**的另一个模型，``teacher_staff_no`` 与
    ``applied_at`` 由服务端填——**客户端传了也没用**。

    三拍：

    ① ``OverrideCreate`` 的字段集**恰好**是那 5 个（``OverrideRecord`` 的 7 个减去
       服务端填的两个），且 ``/openapi.json`` 里那个 schema 的 ``required`` 是 4 个
       （``target`` 可空）。⚠️ 这一拍的期望侧从 ``/openapi.json`` **实读**，
       不是照着模型写的（硬规矩 #89：不要凭记忆构造 payload）。
    ② ``OverrideKind`` 在 spec 里是一个**被引用的** schema，它的 ``enum`` 是那 5 个字面
       值——⚠️ **下划线，不是连字符**（P4-A3）。
    ③ **真的有牙**：POST 一个**多带**那两个键的请求体（``teacher_staff_no`` 填一个
       冒充的工号、``applied_at`` 填 1999 年）→ 200，而库里那一条的
       ``teacher_staff_no`` 是**请求头里那个**、``applied_at`` 是**今天**。
       ⚠️ 没有这一拍，①只是一个「模型上没写这两个字段」的静态事实，
       而「冒充别的教师 / 伪造时间」这个失效形态没有任何守卫看着。
    """
    spec = client.get("/openapi.json").json()
    assert list(OverrideCreate.model_fields) == [
        "kind", "target", "old_value", "new_value", "reason",
    ]
    schema = spec["components"]["schemas"]["OverrideCreate"]
    assert sorted(schema["properties"]) == [
        "kind", "new_value", "old_value", "reason", "target",
    ]
    assert sorted(schema["required"]) == ["kind", "new_value", "old_value", "reason"]
    assert spec["components"]["schemas"]["OverrideKind"]["enum"] == [
        "weekly_frequency", "substitute_exercise", "intensity_step",
        "volume_scale", "pause",
    ]

    got = _post_override(
        client, seeded, kind="volume_scale", target=None, old_value="1.0",
        new_value="0.9", reason="冒充与伪造时间的一拍",
        teacher_staff_no="IMPOSTOR", applied_at="1999-01-01T00:00:00",
    )
    assert got.status_code == 200, got.text
    stored = got.json()["overrides"][-1]
    assert stored["teacher_staff_no"] == TEACHER_STAFF_NO
    assert stored["applied_at"].startswith(dt.date.today().isoformat())
    with Session(engine) as session:
        row = session.get(Prescription, seeded["prescription"])
        assert row.teacher_overrides[-1]["teacher_staff_no"] == TEACHER_STAFF_NO
        assert not row.teacher_overrides[-1]["applied_at"].startswith("1999")

    # 域外的 kind → 422（Pydantic 那一档，与 domain 的 ValueError 不同码）
    bad = _post_override(
        client, seeded, kind="weekly-frequency", target=None, old_value="4",
        new_value="3", reason="连字符不是下划线",
    )
    assert bad.status_code == 422, bad.text
    assert bad.json()["error"]["code"] == "request_validation_failed"

"""**端到端冒烟**：一条 HTTP 往返序列走完 spec §1.3 的三段闭环（Plan 03 Task 9）。

--------------------------------------------------------------------------
⚠️⚠️ 本文件是「这个原型系统真的能跑起来」的**唯一可执行判据**
--------------------------------------------------------------------------

Plan 03 的前 8 个 Task 的测试都是**分层**的：``tests/domain/`` 测纯函数、
``tests/pipeline/`` 测阶段、``tests/api/`` 测端点，每一层各自绿。而**分层全绿证明不了
它们接得上**——一个把 ``alert_stage`` 的输出键名写错、或让 ``weekly_factors_of`` 读不到
``source="auto"`` 那一行的改动，可以让 1225 条分层测试全绿而整个闭环断掉。

故本文件的 :func:`test_the_whole_loop_runs_over_real_http` **一条测试走完八步**，
任何一步断了它就红：

=====  ==========================================================  ==========================
步      HTTP 往返                                                     它证明的是
=====  ==========================================================  ==========================
①      ``POST /api/pipeline/run-daily``                            批处理能从 HTTP 触发，
                                                                    产出分层与处方
②      ``GET  /api/students/{id}/prescriptions/current``           学生端读得到**自己的**处方
③      ``POST /api/class-sessions``×3 + ``…/open-rpe``×3            教师建课次、发起快评；
       + ``POST /api/rpe-records``×3（``rpe=9``）                    学生连交三次「太累了」
④      ``POST /api/pipeline/run-daily``（**同一天 = 重放**）        预警阶段读到了那三条快评
⑤      ``GET  /api/alerts``                                        ``RED_RPE_SUSTAINED`` 落了
                                                                    **恰好一条**（去重口径）
⑥      ``POST /api/alerts/{id}/handle`` ``reduce_20pct``           教师点击 → 处置留痕 +
                                                                    推送「减量 20%」
⑦      ``GET  /api/students/{id}/weekly-sheet``                    学生端**当周**的训练单
                                                                    已经是减量之后的
⑧      ``GET  /api/notifications``                                 站内消息真的到了那个人
=====  ==========================================================  ==========================

spec §1.3 的三段因此各归其位：**数据驱动** = ①④（体测 CSV → 分层 → 处方），
**智能处方** = ②⑦（模板 → 训练包 → 本周训练单），**智慧反馈** = ③⑤⑥⑧
（三源采集 → 预警 → 教师处置 → 站内消息）。

--------------------------------------------------------------------------
⚠️ 走的是**真实 HTTP**，不是直接调阶段函数
--------------------------------------------------------------------------

每一步都是一次 ``TestClient`` 的请求（``fastapi.testclient.TestClient``，它内部是
**httpx** 的 ``ASGITransport``，基址恒为 ``http://testserver``）——故被 exercised 的是
「路由匹配 → 依赖注入（``get_db`` / ``current_student`` / ``current_teacher``）→
身份与作用域闸门 → 请求体校验 → 端点体 → ``response_model`` 序列化 → 错误处理器」
这**一整条**，而不只是端点体。直接调 :func:`app.pipeline.daily.run_daily` 与
:func:`app.pipeline.alert_stage.evaluate_alerts` 的版本住在
``tests/pipeline/test_daily.py`` 与 ``tests/pipeline/test_alert_stage.py``，
**两处并列、不合并**：那一组证明阶段本身对，本文件证明**API 层把它们接上了**。

⚠️ 于是本文件里的身份请求头是**承重的**：②⑦ 用 ``X-Student-Id``、
①③⑥ 用 ``X-Teacher-Staff-No``，而 ⑤⑧ 走的是不带 ``security`` 的泛型读端点。
把 :func:`app.api.deps.require_scope` 改坏，本文件会红在 ②（403），
而 ``tests/api/test_scope.py`` 会红在它自己的矩阵上——两条判据不同，不重复。

--------------------------------------------------------------------------
⚠️ 数据从哪来（以及**绝不碰**哪两个禁区）
--------------------------------------------------------------------------

* **组织结构**：:func:`app.seed.generate.seed_database`（60 人 / 16 周 / ``seed=20250828``，
  与 ``tests/pipeline/test_daily.py`` 的 ``CFG`` 同一组参数），只写组织结构、不写体测数据。
* **体测数据**：``write_csv(build_dataset(CFG), tmp_path/…)`` → 由
  :class:`~app.adapters.mock_lepao.MockLePaoAdapter` 在 ①④ 里真的**抽取**进来。
  ⚠️ CSV 目录是 ``tmp_path`` 下的、经 :data:`app.api.routers.pipeline.CSV_DIR_ENV_VAR`
  这个环境变量告诉服务进程，**不是** :data:`app.config.DEFAULT_CSV_DIR`
  （``backend/data/seed/`` 是本仓禁区、恒为 0 文件）。
* **库**：``tests/api/conftest.py`` 的内存 SQLite（``sqlite://`` + ``StaticPool``）。
  ⚠️ 于是本文件跑完**不留任何磁盘文件**（``tmp_path`` 由 pytest 自己回收），
  ``backend/pe.db`` 与 ``backend/data/seed/`` 一个字节都不动。

--------------------------------------------------------------------------
⚠️ 本文件守不住什么（硬规矩 #39）
--------------------------------------------------------------------------

* **不守各阶段自己的算法**：分层分布、预警阈值、装配与等价替换分别由
  ``tests/integration/test_golden_cases.py``（14 例）、``tests/domain/test_alerts.py``
  （5 条规则、100% 分支）与 ``tests/domain/test_prescription_*`` 守。本文件只钉
  「**接得上**」，故它的期望值一律是**链路两端**的量（有没有处方 / 有没有那一条预警 /
  factor 是不是 0.8 / 消息是不是到了那个人），不重复钉中间量。
* **不守 ``weekly_class_report``**：业务日期 ``2025-09-15`` 是**周一**，而
  :func:`app.pipeline.report_stage.is_report_day` 只在周日为真，故 ①④ 两批一份周报都不生成
  （探针实测 ``weekly_class_report`` 行数 = 0）。周报那一环由
  ``tests/pipeline/test_report_stage.py`` 与 ``tests/api/test_dashboard.py`` 守。
  ⚠️ 把它挪到周日会让 ① 的 ``extracted_*`` 与 ④ 的 ``alert_count`` 全部变值
  （水位线与「本周」都跟着挪），故本文件**刻意**用与 ``tests/pipeline/test_daily.py``
  同一个业务日期 ``2025-09-15``：两个文件的数字可以直接对读。
* **不守「减量只发生一次」的**全部**形状**：⑦ 断言 ``factor == 0.8`` 而**不是** ``0.64``，
  这已经是 Review Focus 第 3 条在真实链路上的落点（管道在 ④ 自动减过一次，教师在 ⑥
  又点了一次，而 ⑥ 的 ``adjustment`` 是 ``None`` = 撞上唯一约束、没有第二次减）；
  但「连续第 4、5 次快评不再新开预警」那一档要**三天**数据，本文件是单日的，
  它由 ``tests/pipeline/test_alert_stage.py`` 的 ``window_key`` 那几条守。
"""
import datetime as dt

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routers import pipeline as pipeline_router
from app.api.routers.pipeline import CSV_DIR_ENV_VAR
from app.api.schemas.pipeline import RunDailyCreate, RunDailyResult
from app.config import DEFAULT_CSV_DIR
from app.db.models.feedback import ClassSession, RpeRecord
from app.db.models.ops import DailySyncRun
from app.db.models.organisation import CourseSection, Enrollment, Semester, Teacher
from app.db.models.prescription import Prescription
from app.seed.config import SeedConfig
from app.seed.generate import build_dataset, seed_database, write_csv

#: 60 人 / 16 周 / ``seed=20250828``——与 ``tests/pipeline/test_daily.py`` 的 ``CFG``
#: **同一组参数**（模块 docstring 末节给了理由：两个文件的数字要能直接对读）。
CFG = SeedConfig(students=60, weeks=16, seed=20250828)

#: 业务日期。⚠️ **周一**（``dt.date(2025, 9, 15).weekday() == 0``），故周报阶段一次都不跑；
#: 与 ``tests/pipeline/test_daily.py`` 的 ``D`` 逐字相同。
BUSINESS_DATE = "2025-09-15"

#: 学期名。⚠️ ``seed_database`` 写**两条** ``Semester``（``2024-2025-1`` 与 ``2025-2026-1``），
#: 故一律按**名字**取、不按 ``scalar(select(Semester))``（Ruling 173 的同一条纪律：
#: 不带 ``order_by`` 的 ``scalar`` 实测取到先插入的上学年）。
SEMESTER_NAME = "2025-2026-1"

#: 三节课的日期。⚠️ 三节都 ``<= BUSINESS_DATE``、都落在学期第 2–3 周，
#: 且**三节都在同一个教学班**（``RED_RPE_SUSTAINED`` 的判据是「连续 3 次课堂快评」，
#: 而 :func:`app.pipeline.alert_stage._rpe_rows` 按 ``(session_date, period)`` 排序，
#: 故三节的日期必须递增、``period`` 相同也不影响排序）。
CLASS_DAYS = (dt.date(2025, 9, 10), dt.date(2025, 9, 12), dt.date(2025, 9, 15))

#: 三节课的节次（``class_session`` 的唯一键是 ``(course_section_id, session_date, period)``，
#: 故固定节次 + 三个不同日期 = 三节不同的课）。
PERIOD = 3

#: 学生连交三次的 RPE。⚠️ **9 是 ``alert_rules.yaml`` 的 ``RED_RPE_SUSTAINED.rpe_min``**，
#: 而本文件写**字面量**、不 import 那个阈值（硬规矩 #35：两侧同源的话，把阈值从 9 调到 10
#: 会让本文件与 YAML 一起改、断言恒成立）。调高阈值 → 本文件红在 ⑤（查不到那一条预警），
#: 那正是想要的颜色。
RPE_VALUE = 9

#: ⑥ 那一档推送的标题。⚠️ 字面量取自 spec §8.2 的「推送『减量 20%』」，
#: 与 :mod:`app.api.routers.alerts` 里那一句 ``title=`` 两侧不同源。
REDUCTION_TITLE = "本周训练量已减 20%"


@pytest.fixture()
def seeded(engine, tmp_path, monkeypatch):
    """一个**灌好了组织结构与体测 CSV** 的库，返回 ``{名字: 值}``。

    三件事，顺序承重：

    1. ``write_csv(build_dataset(CFG), …)`` —— 体测数据落成 CSV，等 ① 去抽取；
    2. ``monkeypatch.setenv(CSV_DIR_ENV_VAR, …)`` —— 告诉服务进程去读**那个**目录
       （缺省的 :data:`app.config.DEFAULT_CSV_DIR` 在本仓恒为空）；
    3. ``seed_database(session, CFG)`` + ``commit`` —— 组织结构（学期 / 教师 / 学生 /
       教学班 / 选课）落库。⚠️ **必须 commit**：``conftest`` 的纪律是
       「不要把一个开着事务的 Session 跨请求留着」（``StaticPool`` 下它与请求里的
       ``Session`` 抢同一条 DBAPI 连接），故这里是「用完即关」的形状。

    ⚠️ 它**不**跑 ``run_daily``：那是被测的第 ① 步，必须由 HTTP 触发，
    否则本文件就退化成 ``tests/pipeline/test_daily.py`` 的副本。
    """
    csv_dir = tmp_path / "lepao"
    write_csv(build_dataset(CFG), csv_dir)
    monkeypatch.setenv(CSV_DIR_ENV_VAR, str(csv_dir))
    with Session(engine) as session:
        seed_database(session, CFG)
        session.commit()
        semester_id = session.scalar(
            select(Semester.id).where(Semester.name == SEMESTER_NAME)
        )
        staff_no = session.scalar(select(Teacher.staff_no).order_by(Teacher.id).limit(1))
    return {"csv_dir": csv_dir, "semester_id": semester_id, "staff_no": staff_no}


def _teacher(staff_no: str) -> dict:
    return {"X-Teacher-Staff-No": staff_no}


def _student(student_id: int) -> dict:
    return {"X-Student-Id": str(student_id)}


def _pick_student_with_a_section(engine, semester_id: int) -> tuple[int, int]:
    """挑一个「① 之后有 active 处方、且在本学期某个教学班里」的学生，返回
    ``(student_id, course_section_id)``。

    ⚠️ **它是一次真的查询、不是硬编码的 id**：``seed_database`` 的学生 id 取决于插入序
    （实测 60 人的 id **不是** 1..60 连号，``student_no`` 也不是按 id 升序），
    写死一个 id 会让本文件在生成器改一次编班顺序之后红在一个看不懂的地方。
    ⚠️ 而它**是确定的**：``ORDER BY student_id, course_section_id`` + ``LIMIT 1``，
    而 ``CFG`` 的 ``seed`` 固定，故两次运行挑到同一个人（探针 09 实测 student 1 / section 1）。

    ⚠️ 一个学生可以同时在**两个**班里（seed 的编班是行政班 + 分层班两套，
    60 人 → 120 行 ``enrollment``），故 ``ORDER BY`` 的第二格是承重的：
    少了它，「同一个学生在两行里」会让 ``LIMIT 1`` 取到哪一行取决于查询计划。

    ⚠️ 三张表都要 join：``prescription``（有没有处方）、``enrollment``（在不在班里）、
    ``course_section``（那个班是不是**本学期**的）。少 join ``course_section`` 的话
    会挑到一个「在上学年的班里」的学生，而 ③ 建的课次会落在上学年那个班上，
    于是 :func:`app.pipeline.alert_stage._rpe_rows` 按
    ``CourseSection.semester_id == semester_id`` 过滤时**一条都读不到**——
    ⑤ 查不到预警，而报错信息完全指不出真因（硬规矩 #114：「曾经成立」与「现在成立」
    是两个判据，故学期的限定必须写进这一条查询里）。
    """
    with Session(engine) as session:
        row = session.execute(
            select(Prescription.student_id, Enrollment.course_section_id)
            .join(Enrollment, Enrollment.student_id == Prescription.student_id)
            .join(
                CourseSection, CourseSection.id == Enrollment.course_section_id
            )
            .where(
                Prescription.status == "active",
                Prescription.valid_from <= dt.date.fromisoformat(BUSINESS_DATE),
                Enrollment.semester_id == semester_id,
                CourseSection.semester_id == semester_id,
            )
            .order_by(Prescription.student_id, Enrollment.course_section_id)
            .limit(1)
        ).one()
    return int(row[0]), int(row[1])


def test_the_whole_loop_runs_over_real_http(client, engine, seeded):
    """spec §1.3 的闭环在**一次 HTTP 往返序列**里全部走到（八步，逐步断言）。

    ⚠️ **一条测试、不拆八条**（这是本文件唯一一处刻意违反「一个测试一件事」的地方）：
    拆成八条的话，第 ⑤ 条必须自己重跑 ①–④，于是「八条全绿」与「一条走完八步」
    在证据上等价、而在**可读性**上前者更差——读者要在八个 fixture 之间跳，
    才拼得出「哪一步接着哪一步」。而本条要证明的恰恰是**「接着」这件事本身**。
    代价如实记录：它红的时候只报第一个断掉的步，故每一步的断言都带
    ``f"步骤 {n}: …"`` 的主语（硬规矩 #56），且**一律先断状态码、再断响应体**
    （一个 4xx 的响应体是错误形状，直接取键会得到一句 ``KeyError``，把真因盖掉）。
    """
    headers_teacher = _teacher(seeded["staff_no"])

    # ------------------------------------------------------------------ ①
    response = client.post(
        "/api/pipeline/run-daily",
        json={"business_date": BUSINESS_DATE},
        headers=headers_teacher,
    )
    assert response.status_code == 200, f"步骤 ①: {response.text}"
    first_run = response.json()
    assert first_run["status"] == "success", f"步骤 ①: {first_run['error_summary']}"
    # 两侧不同源：一侧是响应体、一侧是**按名字**从库里查出来的那个学期（Ruling 173）
    assert first_run["semester_id"] == seeded["semester_id"], "步骤 ①: 学期解析错了"
    assert first_run["business_date"] == BUSINESS_DATE, "步骤 ①"
    # 数据源留痕：读的**确实是** tmp 里那三份 CSV，而不是恒为空的缺省目录
    assert first_run["csv_dir"] == seeded["csv_dir"].as_posix(), "步骤 ①: 数据源目录"
    assert first_run["extracted_fitness"] > 0, "步骤 ①: 一条体测都没抽到"
    # 60 人 → 60 张处方（``first_stratification`` 触发），四个分层计数之和必须等于人数
    assert first_run["prescription_count"] == 60, "步骤 ①"
    assert (
        first_run["red_count"] + first_run["yellow_count"]
        + first_run["green_count"] + first_run["insufficient_count"]
    ) == 60, f"步骤 ①: 四个分层计数之和不等于人数：{first_run}"
    # 还没有任何反馈数据 → 一条预警都不该有（``population`` 是「在三源里留过痕的学生」，
    # 此刻三源全空）。⚠️ 这一格是 ④ 那句 ``alert_count == 2`` 的**对照**：
    # 少了它，「预警阶段压根没跑」与「跑了但没触发」在 ④ 上同形。
    assert first_run["alert_count"] == 0, "步骤 ①: 三源还空着，不该有预警"

    # ------------------------------------------------------------------ ②
    student_id, section_id = _pick_student_with_a_section(engine, seeded["semester_id"])
    response = client.get(
        f"/api/students/{student_id}/prescriptions/current",
        params={"as_of": BUSINESS_DATE},
        headers=_student(student_id),
    )
    assert response.status_code == 200, f"步骤 ②: {response.text}"
    prescription = response.json()
    assert prescription["student_id"] == student_id, "步骤 ②"
    assert prescription["status"] == "active", "步骤 ②"
    assert prescription["generated_on"] == BUSINESS_DATE, "步骤 ②"
    prescription_id = prescription["id"]

    # ⚠️ **越权那一格也在本条里**（计划 Review Focus 第 1 条）：换一个学生 id 当身份，
    # 读同一个人的处方必须 403。少了它，②「200」与「任何 id 都 200」在颜色上无法区分。
    other = student_id + 1
    response = client.get(
        f"/api/students/{student_id}/prescriptions/current",
        params={"as_of": BUSINESS_DATE},
        headers=_student(other),
    )
    assert response.status_code == 403, f"步骤 ②（越权对照）: {response.text}"

    # ------------------------------------------------------------------ ③
    session_ids = []
    tokens = []
    for day in CLASS_DAYS:
        created = client.post(
            "/api/class-sessions",
            json={
                "course_section_id": section_id,
                "session_date": day.isoformat(),
                "period": PERIOD,
            },
            headers=headers_teacher,
        )
        assert created.status_code == 201, f"步骤 ③（建课次 {day}）: {created.text}"
        class_session_id = created.json()["id"]
        session_ids.append(class_session_id)

        opened = client.post(
            f"/api/class-sessions/{class_session_id}/open-rpe",
            headers=headers_teacher,
        )
        assert opened.status_code == 200, f"步骤 ③（发起快评 {day}）: {opened.text}"
        body = opened.json()
        assert body["rpe_opened"] is True, "步骤 ③"
        assert body["already_open"] is False, "步骤 ③"
        assert len(body["rpe_token"]) == 16, (
            f"步骤 ③: 口令长度不是 ClassSession.RPE_TOKEN_LEN 那 16 个字符：{body}"
        )
        tokens.append(body["rpe_token"])

        submitted = client.post(
            "/api/rpe-records",
            json={
                "class_session_id": class_session_id,
                "rpe": RPE_VALUE,
                "elapsed_seconds": 20.0,
                "rpe_token": body["rpe_token"],
            },
            headers=_student(student_id),
        )
        assert submitted.status_code == 201, f"步骤 ③（交快评 {day}）: {submitted.text}"
        assert submitted.headers["Location"] == f"/api/rpe-records/{submitted.json()['id']}"
        # ⚠️ 服务端填的两格：``student_id`` 取自请求头、``submitted_at`` 取自服务端时钟
        assert submitted.json()["student_id"] == student_id, "步骤 ③"
        assert submitted.json()["rpe"] == RPE_VALUE, "步骤 ③"

    assert len(set(tokens)) == 3, "步骤 ③: 三节课的口令必须各不相同"
    # ⚠️ 口令是真的承重：拿第一节课的口令去交第二节课 → **403 invalid_rpe_token**。
    # 它挡的是「学生猜 class_session_id 乱交」（spec §4.5 的「快评口令」那一格的用途）。
    # ⚠️ 是 403 而不是 409：端点的四道闸门按「从便宜到贵」排，口令那一道在**插入之前**，
    # 故它先于「一节课一个学生只能交一次」那条唯一约束（409）命中。
    response = client.post(
        "/api/rpe-records",
        json={
            "class_session_id": session_ids[1],
            "rpe": RPE_VALUE,
            "rpe_token": tokens[0],
        },
        headers=_student(student_id),
    )
    assert response.status_code == 403, f"步骤 ③（口令对照）: {response.text}"
    assert response.json()["error"]["code"] == "invalid_rpe_token", (
        f"步骤 ③（口令对照）: {response.json()}"
    )
    # ⚠️ 那一格**没有**被写进库：口令不对时端点在插入之前就返回了，故这个学生的快评
    # 仍是 3 条。少了这一句，「403 之后又多插了一行」这个失效形状没人看着，
    # 而它会让 ④ 的 streak 变成 4（预警照触发，全链路不报错）。
    with Session(engine) as session:
        rpe_rows = session.execute(
            select(RpeRecord.class_session_id).where(RpeRecord.student_id == student_id)
        ).all()
    assert len(rpe_rows) == 3, f"步骤 ③: 这个学生应当恰好 3 条快评，实际 {len(rpe_rows)}"
    assert sorted(row[0] for row in rpe_rows) == sorted(session_ids), "步骤 ③"

    # ------------------------------------------------------------------ ④
    response = client.post(
        "/api/pipeline/run-daily",
        json={"business_date": BUSINESS_DATE},
        headers=headers_teacher,
    )
    assert response.status_code == 200, f"步骤 ④: {response.text}"
    second_run = response.json()
    assert second_run["status"] == "success", f"步骤 ④: {second_run['error_summary']}"
    # 同一天 + 同一个学期 = **重放**：幂等键 (semester_id, business_date) 命中同一行，
    # 故 run id 与 ① 逐字相同，而 _replay_cleanup 已经把上一批的七张表按 batch_id 删掉重算。
    assert second_run["daily_sync_run_id"] == first_run["daily_sync_run_id"], (
        "步骤 ④: 同一天重放应当命中同一条 daily_sync_run"
    )
    assert second_run["prescription_count"] == 60, "步骤 ④: 重放不该翻倍"
    # ⚠️ **2 = 学生级 RED_RPE_SUSTAINED 一条 + 班级级 YELLOW_CLASS_RPE_HIGH 一条**
    # （探针 09 实测）。班级级那一条是必然的：那个班本周只有这三条快评、全是 9，
    # 均值 9.0 > 阈值 7（严格大于）。故这里断 **2** 而不是 1：断 1 会让
    # 「班级级那条静默消失」看不出来。
    assert second_run["alert_count"] == 2, f"步骤 ④: {second_run}"

    # ------------------------------------------------------------------ ⑤
    response = client.get("/api/alerts", params={"limit": 200})
    assert response.status_code == 200, f"步骤 ⑤: {response.text}"
    alerts = response.json()
    assert alerts["total"] == 2, f"步骤 ⑤: {alerts['total']}"
    red = [item for item in alerts["items"] if item["rule_id"] == "RED_RPE_SUSTAINED"]
    assert len(red) == 1, (
        f"步骤 ⑤: RED_RPE_SUSTAINED 应当恰好一条（去重口径 = "
        f"(rule_id, subject_key, semester_id, window_key) 四列唯一），实际 {len(red)} 条"
    )
    alert = red[0]
    assert alert["student_id"] == student_id, "步骤 ⑤"
    assert alert["level"] == "red", "步骤 ⑤"
    assert alert["status"] == "pending", "步骤 ⑤"
    assert alert["semester_id"] == seeded["semester_id"], "步骤 ⑤"
    # ⚠️ window_key 锚在**凑满 streak 那一次**的课次上（Review Focus 第 3 条的全部落点）：
    # 期望侧用 ③ 那三次响应里的**第三个** id 现拼，与被测侧（alert 表那一列）不同源。
    assert alert["window_key"] == f"rpe{session_ids[-1]}", (
        f"步骤 ⑤: window_key 应当锚在凑满 streak 的那一次快评上"
        f"（三节课的 id 是 {session_ids}），实际 {alert['window_key']}"
    )
    assert alert["subject_key"] == f"student:{student_id}", "步骤 ⑤"
    yellow = [item for item in alerts["items"] if item["rule_id"] == "YELLOW_CLASS_RPE_HIGH"]
    assert len(yellow) == 1 and yellow[0]["course_section_id"] == section_id, (
        f"步骤 ⑤: 班级级那一条应当落在这个教学班上：{yellow}"
    )

    # ------------------------------------------------------------------ ⑥
    response = client.post(
        f"/api/alerts/{alert['id']}/handle",
        params={"as_of": BUSINESS_DATE},
        json={"action": "reduce_20pct"},
        headers=headers_teacher,
    )
    assert response.status_code == 200, f"步骤 ⑥: {response.text}"
    handled = response.json()
    assert handled["alert"]["status"] == "handled", "步骤 ⑥"
    assert handled["alert"]["handled_action"] == "reduce_20pct", "步骤 ⑥"
    assert handled["action"] == "reduce_20pct", "步骤 ⑥"
    # ⚠️⚠️ **``adjustment is None`` 是本条最要紧的一格**（Review Focus 第 3 条）：
    # ④ 那一轮预警阶段**已经自动**写过一条 weekly_adjustment(source="auto", factor=0.8)，
    # 故教师这一次点击撞上 uq_weekly_adjustment_prescription_week_reason_source、
    # **没有第二次减量**。少了这一格，「教师点两次 = 0.8 × 0.8 = 0.64」这个失效
    # 在真实链路上就没人看着（⑦ 的 factor == 0.8 只钉了结果、钉不住「没有新写一行」）。
    assert handled["adjustment"] is None, (
        f"步骤 ⑥: 管道在 ④ 已经自动减过量了，教师这一次不该再写一条调整："
        f"{handled['adjustment']}"
    )
    # ⚠️ 而消息**照发**（教师点了「减量 20%」，学生就该被告知，哪怕调整是几天前写的）
    assert handled["notification"] is not None, "步骤 ⑥: 学生该收到一条站内消息"
    assert handled["notification"]["title"] == REDUCTION_TITLE, "步骤 ⑥"
    assert handled["notification"]["recipient_kind"] == "student", "步骤 ⑥"
    assert handled["notification"]["recipient_id"] == student_id, "步骤 ⑥"

    # ------------------------------------------------------------------ ⑦
    response = client.get(
        f"/api/students/{student_id}/weekly-sheet",
        params={"as_of": BUSINESS_DATE},
        headers=_student(student_id),
    )
    assert response.status_code == 200, f"步骤 ⑦: {response.text}"
    sheet = response.json()
    assert sheet["week"] == 1, f"步骤 ⑦: {sheet['week']}"
    # ⚠️ **0.8 而不是 0.64**：减量只发生了一次（见 ⑥ 那一格）
    assert sheet["factor"] == 0.8, f"步骤 ⑦: factor 应当是 0.8（减 20%），实际 {sheet['factor']}"
    assert sheet["reasons"] == ["RED_RPE_SUSTAINED"], f"步骤 ⑦: {sheet['reasons']}"
    assert sheet["sources"] == ["auto"], f"步骤 ⑦: {sheet['sources']}"
    assert sheet["paused"] is False, "步骤 ⑦"
    assert sheet["sessions"], "步骤 ⑦: 本周训练单一个训练日都没有"
    # ⚠️ 训练单是**减量之后**的那一份：block 的 weekly_volume 已经是乘过 0.8 的。
    # 与 ② 读到的 training_package 里同一个 block 相比应当**更小**（两侧不同源：
    # 一侧是 weekly-sheet 的投影、一侧是 prescription 那一列的投影）。
    package_block = prescription["training_package"]["weeks"][0]["sessions"][0]["blocks"][0]
    sheet_block = sheet["sessions"][0]["blocks"][0]
    assert package_block["volume_unit"] == sheet_block["volume_unit"], "步骤 ⑦: 单位不同无法比"
    assert sheet_block["weekly_volume"] == pytest.approx(
        package_block["weekly_volume"] * 0.8, abs=0.05
    ), (
        f"步骤 ⑦: 训练单的量应当是骨架的 0.8 倍："
        f"{package_block['weekly_volume']} → {sheet_block['weekly_volume']}"
    )

    # ------------------------------------------------------------------ ⑧
    response = client.get("/api/notifications", params={"limit": 200})
    assert response.status_code == 200, f"步骤 ⑧: {response.text}"
    mine = [
        item for item in response.json()["items"]
        if item["recipient_kind"] == "student" and item["recipient_id"] == student_id
    ]
    assert len(mine) == 1, (
        f"步骤 ⑧: 这个学生应当恰好收到一条站内消息（两条 RED_* 规则里只有被教师处置的"
        f"那一次推送），实际 {len(mine)} 条：{mine}"
    )
    message = mine[0]
    assert message["title"] == REDUCTION_TITLE, "步骤 ⑧"
    assert message["alert_id"] == alert["id"], "步骤 ⑧: 消息要指回那一条预警"
    assert message["prescription_id"] == prescription_id, "步骤 ⑧"
    assert message["is_read"] is False, "步骤 ⑧: 新消息必须是未读（§9.2 的红点）"
    # ⚠️ 教师那一条（班级级预警的「课堂 RPE 均值偏高」）**不在**上面那个筛选里，
    # 但它在库里，故钉一下总数：2 条 = 学生 1 + 教师 1（探针 09 实测）。
    assert response.json()["total"] == 2, f"步骤 ⑧: {response.json()['total']}"


def test_the_run_daily_result_covers_every_daily_sync_run_column():
    """:class:`RunDailyResult` 投影了 ``daily_sync_run`` 的**全部列**，一列都不漏。

    ⚠️ 两侧不同源（硬规矩 #35）：一侧数 ORM 的 ``__table__.columns``，
    另一侧数 Pydantic 的 ``model_fields``。少了本条，给 ``daily_sync_run`` 加一列
    （例如那条一直在「待清扫」里的 ``report_count``）而忘了投影，端点会**静默**少报一个数，
    而前端只能看到「这一格没有」。

    ⚠️ **``csv_dir`` 是唯一的例外**：它不在那一行上（纯留痕，理由见
    :class:`RunDailyResult` 的 docstring），故期望侧是「列名集合 + 一个 ``csv_dir``」。
    ⚠️ 而 ``id`` 那一列在投影里叫 ``daily_sync_run_id``——泛型 CRUD 的 ``pk_alias``
    用的是同一套「资源名 + _id」的口径，故这一格的改名是**有意的**、写进期望侧。
    """
    columns = {column.name for column in DailySyncRun.__table__.columns}
    fields = set(RunDailyResult.model_fields)
    expected = (columns - {"id"}) | {"daily_sync_run_id", "csv_dir"}
    assert fields == expected, (
        f"投影与表列不一致：少了 {sorted(expected - fields)}、多了 {sorted(fields - expected)}"
    )
    assert len(columns) == 19, (
        f"daily_sync_run 今天有 {len(columns)} 列（本条写的时候是 19）；"
        f"加了列就要同时改 RunDailyResult 与本行——那一格是「运行记录报了些什么」的清单"
    )


def test_run_daily_is_registered_with_the_documented_method_and_security(app):
    """``POST /api/pipeline/run-daily`` 在 OpenAPI 面里的三格：路径、方法、身份头。

    ⚠️ 被测侧用 ``app.openapi()["paths"]`` 而**不是** ``app.routes``：FastAPI 0.141.1 的
    ``include_router`` 是惰性的（折叠成一个 ``_IncludedRouter``），``app.routes`` 只数得出
    5–6 个（Plan 03 的 Task 3/5/7 三个实现者各自独立撞到过这一条，硬规矩 #103：
    两种口径都是运行时的，采**完整**的那一种、把另一种标注为不可用）。

    ⚠️ 它与 ``tests/api/test_prescription_api.py`` 的
    ``test_the_identity_headers_are_registered_as_openapi_security_schemes`` **并列、不合并**：
    那一条守的是「全仓除清单之外无 ``security``」（本端点因此被登记进了它的
    ``expected`` 清单），本条守的是「这一个端点自己长什么样」。
    """
    paths = app.openapi()["paths"]
    assert "/api/pipeline/run-daily" in paths, sorted(
        path for path in paths if "pipeline" in path
    )
    operation = paths["/api/pipeline/run-daily"]
    assert list(operation) == ["post"], f"只该有 POST：{list(operation)}"
    assert operation["post"]["security"] == [{"X-Teacher-Staff-No": []}]
    assert operation["post"]["tags"] == ["pipeline"]
    # ⚠️ 它**不带** ``GET``：一次批处理不是一个可读的资源，「这一批跑得怎么样」
    # 由 ``daily_sync_run`` 那一行的投影在响应体里给（本端点回 200 而不是 201 +
    # Location 的理由逐字见 app/api/routers/pipeline.py 的端点 docstring）。
    assert "get" not in operation


def test_the_csv_dir_comes_from_the_environment_and_not_from_the_request(monkeypatch):
    """数据源目录**只能**由进程级环境变量覆盖，请求体里没有任何一格能指定它。

    ⚠️ 这一条挡的是「让 HTTP 客户端指定服务端去读哪个目录」——在一个**未鉴权**的原型上
    那是一次文件系统探测面（理由逐字见 :mod:`app.api.routers.pipeline` 的模块 docstring
    第三节与 :class:`RunDailyCreate` 的 docstring）。

    判据是**请求模型的字段集**（结构性的保证，不是「多传会 422」）：Pydantic 缺省
    ``extra="ignore"``，故「多传一个 ``csv_dir`` 会被静默丢掉」这件事本身**不是**防线
    ——防线是「那个字段压根不在模型上」，与
    ``tests/api/test_feedback.py::test_the_request_models_cannot_carry_the_server_filled_fields``
    同一条纪律。
    """
    assert set(RunDailyCreate.model_fields) == {"business_date", "semester_id"}
    for banned in ("csv_dir", "adapter", "adapter_kind", "kind", "base_url", "token"):
        assert banned not in RunDailyCreate.model_fields, banned
    # 环境变量那一侧是**唯一**的覆盖口，且空字符串按「没设」处理
    assert CSV_DIR_ENV_VAR == "PE_CSV_DIR"
    monkeypatch.delenv(CSV_DIR_ENV_VAR, raising=False)
    assert pipeline_router._csv_dir() == DEFAULT_CSV_DIR
    monkeypatch.setenv(CSV_DIR_ENV_VAR, "")
    assert pipeline_router._csv_dir() == DEFAULT_CSV_DIR, "空串必须按「没设」处理"
    monkeypatch.setenv(CSV_DIR_ENV_VAR, "Z:/somewhere/else")
    assert pipeline_router._csv_dir().as_posix() == "Z:/somewhere/else"


def test_the_class_session_model_exposes_the_token_length_the_loop_asserts():
    """③ 里那个字面量 ``16`` 与 ``ClassSession.RPE_TOKEN_LEN`` 是一回事（**两侧不同源**）。

    ⚠️ 本条存在的理由与 :func:`test_the_whole_loop_runs_over_real_http` 里那一句
    ``len(body["rpe_token"]) == 16`` 配对：那一句写的是**字面量**（硬规矩 #35），
    于是「专家把口令长度改成 32」会让端到端测试红在一个看不懂的地方。本条把那个字面量
    与它的**所有者**钉在一起，报错信息因此直接说清「是口令长度变了」。
    """
    assert ClassSession.RPE_TOKEN_LEN == 16

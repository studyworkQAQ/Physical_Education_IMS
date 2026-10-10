"""``POST /api/pipeline/run-daily``：手动触发一次每日批处理（Plan 03 Task 9）。

**它是本模块所在的 ``routers/`` 里唯一一个「不读也不写某一张业务表」的端点**：
它调的是 :func:`app.pipeline.daily.run_daily`——九个阶段的编排
（``Extract → Clean → Percentile → Derive → Stratify → Prescribe → Alert → Report → Commit``），
一次请求跑完一整批。故它的耗时与其它端点不是一个量级（60 人的演示库实测约 1 s，
500 人 ×16 周的回放是分钟级），而**原型不做异步任务队列**：一次 HTTP 往返里同步跑完，
前端要自己转圈。这是计划「能跑通 > 参数保真」那条最高准则的直接后果，如实记录。

--------------------------------------------------------------------------
⚠️ 依赖方向：``api → adapters`` 与 ``api → pipeline`` 都是许可方向
--------------------------------------------------------------------------

:data:`tests.architecture.test_layering.API_ALLOWED_PREFIXES` 在 Plan 03 Task 1 就把
``app.adapters`` 列进去了，而它当时**一个消费者都没有**——那份清单的注释逐字写着
理由：``run_daily`` 的第四个参数是**适配器实例**，而 ``build_adapter`` 住在
``app.adapters.factory``，故 Task 9 要么改清单、要么在端点里绕过工厂手搓适配器
（「那才是真的坏味道」）。本模块是那条前瞻的兑现处，**一行清单都没改**。

--------------------------------------------------------------------------
⚠️ 数据源目录：环境变量覆盖，**不接受请求体指定**
--------------------------------------------------------------------------

:data:`CSV_DIR_ENV_VAR` 是「这个服务进程去读哪个目录的 CSV」的唯一覆盖口，口径与
:data:`app.main.DB_URL_ENV_VAR`（``PE_DB_URL``）逐字相同：

* **缺省值的所有者仍是** :data:`app.config.DEFAULT_CSV_DIR`（``backend/data/seed/``）——
  本模块不写第二份路径；
* 空字符串按「没设」处理（``or``）：``$env:PE_CSV_DIR = ""`` 在 PowerShell 里是
  「设了一个空值」而不是「删掉这个变量」，而 ``pathlib.Path("")`` 是**当前目录**，
  于是一次「设成空」的重放会去读 CWD，那是离真因很远的一格；
* **在请求时读、不在 import 时读**：``app.main`` 的模块级 ``app = create_app()`` 让
  「import 期读环境变量」变成「必须在 import 之前设好」，而 :class:`TestClient`
  的夹具是 function 级的、``monkeypatch.setenv`` 发生在 import **之后**。

⚠️ **为什么不让请求体带 ``csv_dir``**：那等于在一个**未鉴权**的原型上开一个
「让任意调用方指定服务端去读哪个目录」的口（一个文件系统探测面），而它换来的只是
「测试少设一个环境变量」。理由逐字写在 :class:`app.api.schemas.pipeline.RunDailyCreate`
的 docstring 里。

⚠️ **代价（硬规矩 #39）**：环境变量是进程级的，故同一个服务进程**不能同时**服务两个
数据源目录。原型只有一个演示库，这一档今天不可达。
"""
import os
import pathlib

from fastapi import APIRouter, Depends, Security
from sqlalchemy.orm import Session

# ⚠️ ``api → adapters`` / ``api → pipeline`` 都是许可方向（模块 docstring 第二节）。
from app.adapters.factory import build_adapter
from app.api.deps import TEACHER_STAFF_NO_SCHEME, current_teacher, get_db, require_teacher
from app.api.schemas.pipeline import RunDailyCreate, RunDailyResult
from app.config import DEFAULT_CSV_DIR
from app.db.models.organisation import Semester
from app.pipeline.daily import run_daily
from app.pipeline.percentile_stage import current_semester_of

__all__ = ["CSV_DIR_ENV_VAR", "router"]

#: 覆盖 :data:`app.config.DEFAULT_CSV_DIR` 的环境变量名（模块 docstring 第三节）。
#:
#: ⚠️ **它住在本模块、不住在 ``app.config``**，理由与 :data:`app.main.DB_URL_ENV_VAR`
#: 逐字相同：``config.py`` 是全仓依赖图的叶子（只 import :mod:`pathlib`），
#: 给它加一个 ``import os`` 会改掉那个性质，而它持有的应当是**缺省值**、
#: 不是「本层如何在运行时覆盖缺省值」。
CSV_DIR_ENV_VAR = "PE_CSV_DIR"

router = APIRouter()


def _csv_dir() -> pathlib.Path:
    """本次要读的数据源目录（环境变量 > :data:`app.config.DEFAULT_CSV_DIR`）。"""
    raw = os.environ.get(CSV_DIR_ENV_VAR, "")
    return pathlib.Path(raw) if raw else DEFAULT_CSV_DIR


@router.post(
    "/api/pipeline/run-daily",
    tags=["pipeline"],
    response_model=RunDailyResult,
    dependencies=[Security(TEACHER_STAFF_NO_SCHEME)],
)
def run_daily_endpoint(
    payload: RunDailyCreate,
    staff_no: str = Depends(current_teacher),
    session: Session = Depends(get_db),
) -> dict:
    """（教师）跑一个业务日期的整批，回**那一条 ``daily_sync_run`` 运行记录**的投影。

    ⚠️ **回 200 不回 201、不带 ``Location``**：与本仓其余动作端点同一条约定
    （:func:`app.api.routers.alerts.handle_alert` / Task 4 的两个 POST /
    Task 5 的 ``open-rpe``）。⚠️ 而它**确实写了一行**（``daily_sync_run``），故这一档
    与「纯操作、不产生新资源」略有不同：不给 ``Location`` 的理由是那一行**没有自己的
    读端点**——``daily_sync_run`` 不在 :data:`app.api.routers.catalog.RESOURCES` 的
    23 个资源里（它是运维表、不是业务实体，spec §4.6 把它与 ``cleaning_log`` 归在一起），
    指一个前端读不到的 URI 是噪音。运行记录的全部内容因此直接在响应体里给。

    ⚠️ **``status == "failed"`` 时仍是 200**，理由与代价逐字见
    :mod:`app.api.schemas.pipeline` 的模块 docstring 末节（一句话：500 的响应体里
    只允许出现 :data:`app.api.errors._INTERNAL_MESSAGE` 那一句，而本档要回的是
    ``error_summary`` 那一句具体的话）。

    **事务边界在本端点**：:func:`app.pipeline.daily.run_daily` 刻意**不 commit**
    （与 :func:`app.db.repo.upsert` / ``generate_prescriptions`` / ``evaluate_alerts`` /
    ``generate_weekly_reports`` 同一条口径：「什么时候算一个工作单元结束了」只有调用方知道），
    故 ``session.commit()`` 写在这里。⚠️ 它**必须无条件执行**：``run_daily`` 在失败档
    已经用 SAVEPOINT 撤销了本批、并用**独立小事务**写下了那条 ``status = "failed"`` 的行，
    不 commit 的话那唯一一行留痕会随请求结束被 ``Session.close()`` 回滚掉——
    于是「这一天跑过、并且失败了」在库里没有任何痕迹，运维只能靠日志猜，而日志会滚掉
    （:func:`app.pipeline.daily._record_failure` 的 docstring 逐字写了这件事）。

    四档失败：

    * **401** —— 缺 ``X-Teacher-Staff-No``（:func:`app.api.deps.current_teacher`）；
    * **403** —— 工号不在册（:func:`app.api.deps.require_teacher`）。⚠️ 本端点**只过
      在册闸门、不过任教关系闸门**：它的主语是「一个业务日期」而不是「一个班或一个学生」，
      而 :func:`app.api.deps.require_teaches_student` 要一个 ``student_id``、
      :func:`app.api.deps.require_teaches_section` 要一个 ``course_section_id``，
      两个都无从填。⚠️ 于是任何在册教师可以重放任何学期——如实记录（硬规矩 #39），
      与那三个写入端点（教师覆盖 / 手动重生成 / 预警处置）同一档关切；
    * **422** —— ``business_date`` 不是合法日期、``semester_id`` 打错了
      （``session.get`` 查无此行）、或库里既没有 ``is_current=True`` 的学期、也没有
      包含 ``business_date`` 的学期区间（三档各是一条 ``ValueError``，
      经 :mod:`app.api.errors` 折成统一形状）；
    * **500** —— 只有基础设施异常（库文件不可写一类）才走到这里：业务失败一律被
      ``run_daily`` 自己接住并落成 ``status = "failed"``。
    """
    require_teacher(session, staff_no)
    if payload.semester_id is not None:
        semester = session.get(Semester, payload.semester_id)
        if semester is None:
            # ⚠️ 抛 ValueError 而不是回 404：与 require_scope / require_teacher 的
            # 「不区分『不存在』与『你没权限』」不同，这一格**没有任何越权信息可泄漏**
            # （semester 是全校共有的时间轴，不是某个人的数据），而 422 说的是
            # 「你这个请求本身没法执行」，比 404 更接近真因。
            raise ValueError(
                f"semester 表里查无 id={payload.semester_id}：daily_sync_run.semester_id 是 "
                f"NOT NULL 外键，而且它是幂等键 (semester_id, business_date) 的一半，"
                f"没有归属就写不进运行记录。要跑本学年请不要传 semester_id"
                f"（服务端会用 current_semester_of 自己解析）"
            )
    else:
        semester = current_semester_of(session, payload.business_date)

    csv_dir = _csv_dir()
    run = run_daily(
        session,
        semester.id,
        payload.business_date.isoformat(),
        build_adapter(csv_dir=csv_dir),
    )
    session.commit()
    session.refresh(run)
    return {
        "daily_sync_run_id": run.id,
        "semester_id": run.semester_id,
        "business_date": run.business_date,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "extracted_fitness": run.extracted_fitness,
        "extracted_body_comp": run.extracted_body_comp,
        "extracted_survey": run.extracted_survey,
        "dropped_count": run.dropped_count,
        "corrected_count": run.corrected_count,
        "red_count": run.red_count,
        "yellow_count": run.yellow_count,
        "green_count": run.green_count,
        "insufficient_count": run.insufficient_count,
        "muscle_line_gaps": run.muscle_line_gaps,
        "prescription_count": run.prescription_count,
        "alert_count": run.alert_count,
        "error_summary": run.error_summary,
        # ⚠️ Windows 上 str(Path) 给反斜杠，故一律 as_posix()：这一格是给**前端**看的留痕，
        # 而 JSON 里一个裸反斜杠是转义字符（口径同 app.config.DEFAULT_DB_URL 那句注释）。
        "csv_dir": csv_dir.as_posix(),
    }

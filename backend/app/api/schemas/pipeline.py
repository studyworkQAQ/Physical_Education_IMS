"""``POST /api/pipeline/run-daily`` 的请求与响应契约（Plan 03 Task 9）。

**本模块不是某个资源的三件套**：它服务的是一个**动作端点**（手动触发一次每日批处理），
与 :mod:`app.api.schemas.alerts` 的 ``AlertHandleCreate`` / ``AlertHandleResult``、
:mod:`app.api.schemas.dashboard` 的 16 个聚合读模型同一档——故它**不进**
``tests/api/test_crud.py::test_the_read_write_matrix_counts_are_pinned`` 数的那
「23 个资源 / 41 个模型」（那条守卫数的是 :data:`app.api.routers.catalog.RESOURCES`）。
它是本包的**第 9 个**模块。

--------------------------------------------------------------------------
⚠️ 为什么要有这个端点（而批处理本来就有 CLI）
--------------------------------------------------------------------------

``python -m app.pipeline.daily --semester … --date …`` 早就跑得通。加一个 HTTP 入口有两条
理由，都是「原型要能被点起来」这一条用户裁定的直接后果：

1. **Plan 04 的教师端要一个「重跑今天」的按钮**。spec §8.2 的闭环是
   「采集 → 预警 → 教师处置 → 学生看到新训练单」，而教师处置的前提是**当天跑过批处理**。
   没有这个端点，演示时必须有人去命令行上敲一条 ``python -m …``，而那正是
   「能用浏览器点起来的原型系统」这句话要消掉的东西。
2. **端到端冒烟测试要走真实 HTTP**（:mod:`tests.api.test_end_to_end`）。那条测试是
   「这个原型系统真的能跑起来」的唯一可执行判据，而它的第一步就是「跑批处理」；
   直接调 :func:`app.pipeline.daily.run_daily` 证明不了 **API 层接得上**
   （前 8 个 Task 的测试都是分层的：domain 纯函数、pipeline 阶段、api 端点各测各的）。

--------------------------------------------------------------------------
⚠️ 响应恒为 200，``status`` 那一格才是「这批成没成」
--------------------------------------------------------------------------

:func:`app.pipeline.daily.run_daily` **不抛**业务失败：它把整批写入放在一个 SAVEPOINT 里，
未捕获异常 → 回滚本批 → 用**独立小事务**写一条 ``status = "failed"`` 的运行记录
（:func:`app.pipeline.daily._record_failure`），然后把那一行返回。故本端点拿到的一律是
一个**已经落库的运行记录**，三种 ``status`` 都是合法产出：

* ``"success"`` —— 整批跑完，每条记录都归到了人头上；
* ``"partial"`` —— 跑完了，但有记录因学号解析不到 ``student`` 表而被整条跳过
  （已在 ``cleaning_log`` 里逐条留痕）；
* ``"failed"`` —— 本批全部回滚，``error_summary`` 是那一句人话。

⚠️ **代价（硬规矩 #39）**：``status == "failed"`` 时 HTTP 码仍是 **200**，故前端必须读
``status``、不能只看状态码——与 ``POST /api/mini-tests/batch`` 那条已登记的关切同形。
**不改成 500 的理由**：:mod:`app.api.errors` 的模块 docstring 逐字写着
「``_INTERNAL_MESSAGE`` 是**唯一**允许出现在 500 响应体里的字符串」（那是一条防泄漏的
纪律：一次 ``KeyError`` 不该把连接串与表结构回给浏览器），而本档要回的恰恰是
``error_summary`` 那一句具体的话。于是两条路里选「200 + ``status``」，把 ``error_summary``
放在响应体里而不是塞进一个 500。⚠️ 而**测试一律断言 ``status == "success"``**，
故这一档在测试里是响的、不是静默的。
"""
import datetime as dt

from pydantic import BaseModel, Field

__all__ = ["RunDailyCreate", "RunDailyResult"]


class RunDailyCreate(BaseModel):
    """``POST /api/pipeline/run-daily`` 的请求体（**2** 个字段）。

    ``business_date``
        业务日期。⚠️ 它是**幂等键的一半**（``uq_daily_sync_run_semester_date`` =
        ``(semester_id, business_date)``），故同一天重复调用是**重放**：
        :func:`app.pipeline.daily._replay_cleanup` 先按 ``batch_id`` 删掉本批的七张表，
        再整批重算。⚠️ 那七张**不含** ``class_session`` / ``rpe_record`` /
        ``training_log`` / ``notification``（前三张是用户实时写入、``batch_id`` 可空或没有，
        最后一张刻意不带 ``batch_id``），故重放**不会**删掉学生刚交的快评与已经推出去的消息。
    ``semester_id``
        运行记录的归属学期。**缺省 = 让服务端自己解析**
        （:func:`app.pipeline.percentile_stage.current_semester_of`：优先 ``is_current``、
        退化到「包含 ``business_date`` 的那个区间」，两者都找不到 → ``ValueError`` → **422**）。
        ⚠️ 给它一个显式值的唯一理由是**重放一个历史学期**——而那时
        :func:`app.pipeline.daily.require_dates_in_semester` 那条 CLI 守卫**不在**本端点上
        （它是 ``main()`` 的活），故一个跨学期组合会在两张派生表的
        ``UniqueConstraint("student_id", "computed_on")`` 上撞出一句人话
        （:func:`app.pipeline.daily._stratify_and_persist` 的 ``raise … from exc``），
        而不是静默留下两套「当前」结果。

    ⚠️ **数据源目录刻意不在请求体里**：让 HTTP 客户端指定「去读哪个目录的 CSV」
    等于开一个文件系统探测口（一个未鉴权的原型上尤其不该有）。它由
    :data:`app.api.routers.pipeline.CSV_DIR_ENV_VAR` 这个**进程级环境变量**覆盖，
    口径与 :data:`app.main.DB_URL_ENV_VAR` 逐字相同（缺省值的所有者是
    :data:`app.config.DEFAULT_CSV_DIR`，环境变量只是本层的运行时覆盖）。
    """

    business_date: dt.date
    semester_id: int | None = Field(default=None, ge=1)


class RunDailyResult(BaseModel):
    """一次批处理的运行记录投影 = ``daily_sync_run`` 那一行的**全部 19 列** + 数据源留痕（**20** 格）。

    ⚠️ **它是 :class:`app.db.models.ops.DailySyncRun` 的投影，不是第二份计数**：
    19 个格子逐个从那一行读出来，故「端点报的数」与「库里的数」结构上不可能不一致。
    ⚠️ 「19 列一个都不漏」由
    ``tests/api/test_end_to_end.py::test_the_run_daily_result_covers_every_daily_sync_run_column``
    钉住：那一侧数的是 ORM 的 ``__table__.columns``、这一侧数的是 Pydantic 的
    ``model_fields``，两侧不同源（硬规矩 #35），故加一列而忘了投影会当场红。
    ⚠️ 而 ``csv_dir`` **不在那一行上**（它是本次实际用的数据源目录，纯留痕）：
    原型的数据源是本地 CSV，而「读了哪个目录」决定了这一批有没有数据——
    缺省目录 :data:`app.config.DEFAULT_CSV_DIR`（``backend/data/seed/``）在本仓**恒为空**，
    于是一次忘了设环境变量的重放会得到「0 条抽取、全员 Z0、而九个阶段的计数看起来都正常」。
    把实际用的目录回给调用方，那一档因此是**看得见的**。

    ⚠️ **周报份数不在这里**（本 Task 的一条裁定，见
    :func:`app.pipeline.daily.run_daily` 调用点那段注释与
    :class:`app.pipeline.report_stage.ReportSummary` 的 docstring）：
    ``daily_sync_run`` 上 ``prescription_count`` 与 ``alert_count`` 两列都有，
    而**周报份数只有日志**。加一列 ``report_count`` 是一次 schema 变更，会连带
    ``_BATCH_OWNED_TABLES`` 之外的多处断言，而收益只是「三个阶段对称」，故不加；
    这个不对称是**有意的**，写在那两处 docstring 里。
    """

    daily_sync_run_id: int
    semester_id: int
    business_date: dt.date
    status: str
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    extracted_fitness: int
    extracted_body_comp: int
    extracted_survey: int
    dropped_count: int
    corrected_count: int
    red_count: int
    yellow_count: int
    green_count: int
    insufficient_count: int
    muscle_line_gaps: int
    prescription_count: int
    alert_count: int
    error_summary: str | None
    csv_dir: str

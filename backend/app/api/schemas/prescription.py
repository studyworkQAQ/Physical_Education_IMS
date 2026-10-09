"""spec §4.4 处方的 4 个资源：**全部只读**，故本模块只有 4 个 ``Read`` 模型。

| 资源路径                          | 表                        | ``writable`` | ``on_delete`` |
| ================================= | ========================= | ============ | ============= |
| ``/api/exercises``                 | ``exercise``               | ❌           | ``forbid``    |
| ``/api/prescription-templates``    | ``prescription_template``  | ❌           | ``forbid``    |
| ``/api/prescriptions``             | ``prescription``           | ❌           | ``restrict``  |
| ``/api/weekly-adjustments``        | ``weekly_adjustment``      | ❌           | ``restrict``  |

**四个只读的理由是三个，不是一个**（计划 Task 3 的显式决定，逐个抄在这里，
因为「只读」这个词在下面三种情况下的含义完全不同）：

1. **``exercise`` / ``prescription_template`` 是参考数据的投影**。spec §4.4 逐字：
   「``exercise_equivalence``（动作等价映射）与 ``alert_rules``（预警阈值）为 ``data/`` 下的
   **静态 YAML + 版本号**，不入库……这是体育专家维护的知识资产而非业务数据，
   改阈值应走版本控制与评审，不应在运行时改数据库」。这两张表是那两份 YAML 的投影
   （:func:`app.refdata_prescription.sync_exercises` / ``sync_templates``），
   **开放 API 写它们会让「YAML 是唯一所有者」这句话变成假的**——下一次 sync 会把
   API 的改动静默覆盖掉。教师要改动作库或模板的审校状态，请改 YAML 走版本控制。
   ⚠️ 这顺手解决了 Plan 02 留给 Plan 03 的第 8 条（``sync_*`` 没有生产调用方）：
   由 Task 9 的 ``POST /api/pipeline/run-daily`` 调一次两者（都幂等），
   于是「YAML → 表」这条投影有了生产入口，而反向的「表 → YAML」刻意不存在。
2. **``prescription`` 有一致性约束**。直接 PATCH 整行会让 ``training_package`` 与
   ``assembly_snapshot`` 失去一致性（后者是「离线复算本张处方」的契约，Task 5 钉死了
   它的 12 个键）。教师覆盖与状态变更走 Task 4 的特例端点。
   ⚠️ 计划 Task 3 曾考虑「``writable=True`` 但只允许改 ``status`` 与
   ``teacher_overrides`` 两列」，并**自己否掉了**：那比走特例端点复杂，
   而原型不需要那个灵活度。
3. **``weekly_adjustment`` 有值域校验**。开放 CRUD 写它会绕过
   :class:`app.domain.prescription.weekly.WeeklyFactor` 的 ``(0, 2]`` 校验
   （Plan 02 留给 Plan 03 的第 4 条）——``factor`` 在 DB 侧**刻意不加 CHECK**
   （合理区间要体育专家给），故 API 是它唯一的闸门，而那个闸门在特例端点上。
   ``source = "auto"`` 由 Task 7 的 ``alert_stage`` 写、``"teacher"`` 由 Task 4 写。

⚠️ **``prescriptions`` 的 ``on_delete`` 是 ``restrict`` 而不是 ``cascade``**：
它确实有一个真子表（``weekly_adjustment.prescription_id``，实测 ``ondelete`` 为 ``None``），
故有微调行的处方删不掉、会得到 409 并点名 ``weekly_adjustment``。
计划里那处「处方作废则微调记录随之作废」的 cascade **不经过 DELETE 端点**，
由 Task 4 的「处方被替换」路径内部使用。于是
:func:`app.api.crud.build_crud_router` 的 ``on_delete="cascade"`` 全库只有
``class-sessions`` 一个用户。

**``JsonText`` 列**（``list_exclude`` 自动探测的对象，P3-B3）：``prescription`` **5 个**
（``training_package`` / ``assembly_snapshot`` / ``safety_substitutions`` /
``teacher_overrides`` / ``trigger_reasons``）、``exercise`` 1 个（``targets``）、
另两张 0 个。**``prescription`` 那 5 个正是 P3-B3 点名的性能风险**：
一张 4 周训练包的 JSON 在 500 人的库上是一次 list 就能拉回几 MB。
"""
import datetime as dt

from pydantic import BaseModel

from app.api.schemas._base import ReadModel
from app.domain.prescription.override import OverrideKind

__all__ = [
    "AssembledBlockRead",
    "AssembledSessionRead",
    "AssembledWeekRead",
    "ExerciseRead",
    "OverrideCreate",
    "OverrideRecordRead",
    "OverrideResultRead",
    "PrescriptionRead",
    "PrescriptionTemplateRead",
    "TrainingPackageRead",
    "WeeklyAdjustmentRead",
    "WeeklySheetRead",
]


class ExerciseRead(ReadModel):
    """``exercise`` 的 7 列，含 1 个 ``JsonText`` 列（``targets``）。

    ⚠️ ``ref`` 是**引用键**而不是 ``id``：模板 YAML 里写的是
    ``exercise_ref: interval_run``，那串字符必须在两次重建库之间稳定，
    而 ``id`` 是代理键、随建库顺序变。故前端展示动作库时应该拿 ``ref`` 当行的身份。
    """

    id: int
    ref: str
    name: str
    video_url: str
    impact_level: str
    targets: list
    equipment: str


class PrescriptionTemplateRead(ReadModel):
    """``prescription_template`` 的 10 列。

    ⚠️ ``template_ref`` 存的是 YAML 里的**逻辑 id**（``YEL-END-NOR-01`` 一类）
    而不是文件路径（计划 Task 3 Step 6 的决定：路径会随目录结构变，
    而 ``template_id`` 是 YAML **内容**的一部分、已被逐个文件的指纹钉住）。
    ⚠️ 本表**没有** ``microcycle_weeks`` 列（实测 10 列）：模板会改版，
    故周期被快照在 :attr:`PrescriptionRead.microcycle_weeks` 上（P6-A3）。
    """

    id: int
    layer: str
    weakness: str
    body_comp: str
    template_ref: str
    version: str
    review_status: str
    reviewer: str | None
    reviewed_at: dt.date | None
    reachable: bool


class PrescriptionRead(ReadModel):
    """``prescription`` 的 **16** 列，含 **5** 个 ``JsonText`` 列。

    ⚠️ **``template_ref`` 与 domain 侧的 ``template_id`` 是同一个东西**（P6-A7）：
    本字段名照 DB 列名（与 :attr:`PrescriptionTemplateRead.template_ref` 同名，
    于是「这张处方按哪一行模板索引生成」在 schema 上就是一次同名字段的连接）。
    **不要**在 API 层把它改名成 ``template_id``——那会造出第三个名字。

    ⚠️ ``valid_to`` 是**闭区间**的末日（``generated_on + microcycle_weeks 周 − 1 天``），
    而 ``stratification_result.valid_to`` 恒为 ``NULL``；两者处置相反且都对，
    完整理由在 :class:`app.db.models.prescription.Prescription` 的 docstring 里。

    ⚠️ ``trigger_reasons`` 是**列表**而不是单值：教师端要能回答
    「为什么今天换了处方」，只留第一条会让「教师手动请求 + 微周期到期」
    看起来只是「教师手动请求」。本模块**不替前端翻译**那些 token
    （``TriggerReason`` 的中文文案归 :mod:`app.domain.prescription.triggers`）。
    """

    id: int
    student_id: int
    generated_on: dt.date
    batch_id: int
    template_ref: str
    microcycle_weeks: int
    label_at_generation: str
    training_package: dict
    assembly_snapshot: dict
    safety_substitutions: list
    teacher_overrides: list
    previous_had_overrides: bool
    status: str
    valid_from: dt.date
    valid_to: dt.date | None
    trigger_reasons: list


class WeeklyAdjustmentRead(ReadModel):
    """``weekly_adjustment`` 的 8 列。

    ⚠️ ``factor`` 的语义是**乘上去**而不是「增减多少」：``1.0`` = 不调整、
    ``0.8`` = 减量 20%（spec §8.4 的字面）。同一周上可以叠多条微调，
    故「本周的量」是 ``骨架第 N 周 × 该周全部 factor`` 的**累乘**
    （:mod:`app.domain.prescription.weekly`），而 ``0.8 × 0.9 = 0.72`` **不是**「−30%」。
    前端要显示「减了多少」，请把累乘结果与 1.0 比，不要逐条相加。

    ``created_at`` NOT NULL 且无缺省（时钟由调用方注入），故它在读模型里是必填的
    ``datetime``。
    """

    id: int
    prescription_id: int
    batch_id: int
    week: int
    factor: float
    reason: str
    source: str
    created_at: dt.datetime


# ---------------------------------------------------------------------------
# Plan 03 Task 4：处方侧四个**特例端点**的模型（不是 CRUD 的三件套）
# ---------------------------------------------------------------------------
#
# ⚠️ **上面那 4 个 ``*Read`` 是 Task 3 建的、一个字没改**；本节全部是新增。
# 本节这些模型**不在** :data:`app.api.routers.catalog.RESOURCES` 里，故
# ``tests/api/test_crud.py::test_every_read_schema_covers_exactly_the_model_columns``
# 那条「41 个模型 / 逐列对齐」的遍历**扫不到它们**——它们对齐的不是 DB 的列，
# 而是 :mod:`app.pipeline.prescription_stage` 那几个投影函数的输出键集，
# 守卫因此另有一条（``test_the_block_schema_covers_exactly_the_projection_keys``）。


class AssembledBlockRead(BaseModel):
    """一个训练块的 JSON 形状 = :func:`app.pipeline.prescription_stage._block_payload`
    的 **10** 个键（逐字同序）。

    ⚠️⚠️ **这是本模块唯一一处「明知道有第二份形状」的地方**，理由与代价都要说清楚
    （硬规矩 #39）：

    * **为什么要有它**：不给 ``response_model`` 的话，``/openapi.json`` 里
      「本周训练单」那一格的响应 schema 是**空的**，Plan 04 的前端只能靠读代码猜形状——
      而 P4-A5 / P4-A6 两条预检更正的全部立意就是「前端要能照 spec 对接」。
    * **代价**：block 的形状于是有两个住址（那个投影函数与本类）。**它们漂移时的失效
      形态是静默的**：``response_model`` 会**过滤掉**模型上没有的键，故投影多产出一个
      字段时它在 HTTP 响应里就这么消失、不报错。
    * **拦它的守卫有两条**，两侧都不同源：
      ① ``test_the_block_schema_covers_exactly_the_projection_keys``——本类的字段名/序
        对 ``_block_payload`` 真的产出的键（一个从类上读、一个从函数输出读）；
      ② ``test_the_weekly_sheet_blocks_are_field_for_field_the_training_package_ones``
        ——**走 HTTP** 把「学生端本周训练单里的 block」与「教师端从
        ``GET /api/prescriptions/{id}`` 读到的 ``training_package`` 里的 block」逐字段比。
        两个端点、两条代码路径，故②能抓到①抓不到的那一类（一侧被 ``response_model``
        过滤掉了字段）。

    ⚠️ ``hr_zone`` 是 ``list[int] | None`` 而**不是** ``tuple``：JSON 没有 tuple，
    投影那一侧显式 ``list(...)``（理由见 :func:`_block_payload`）。
    ⚠️ ``structure`` 是**开放**的 ``dict``：它的键集由模板 YAML 决定
    （``{sets, work_min, rest_min}`` / ``{rounds, reps}`` / addon 的 ``{}`` 三种形状），
    给它定一个 Pydantic 模型就等于把「专家能写哪些结构键」这件事的所有权从 YAML
    搬到 schema 里（Global Constraint #3）。前端按 ``volume_unit`` 分支渲染即可。
    ⚠️ ``impact_level`` 是裸 ``str`` 而不是枚举：它的值域所有者是
    :attr:`app.db.models.prescription.Exercise.IMPACT_LEVELS`（DB 侧）与
    :class:`app.domain.prescription.exercises.ImpactLevel`（domain 侧），
    本模块**不写第三份**；投影那一侧已经把它折成 ``.value`` 了。
    """

    exercise_ref: str
    exercise_name: str
    video_url: str
    impact_level: str
    intensity_text: str
    hr_zone: list[int] | None
    structure: dict
    weekly_volume: float
    volume_unit: str
    sessions_per_week: int


class AssembledSessionRead(BaseModel):
    """一个训练日 = :func:`app.pipeline.prescription_stage._session_payload` 的 3 个键。"""

    day: int
    focus: str
    blocks: list[AssembledBlockRead]


class AssembledWeekRead(BaseModel):
    """微周期的一周 = :func:`app.pipeline.prescription_stage.training_package_payload`
    里 ``weeks`` 那一项的 3 个键。

    ⚠️ ``delta`` 原样带出（教师端要能回答「第 4 周为什么量少了」，答案是模板的
    ``week_deltas`` 末项，而不是「算法决定减量」）。
    """

    week: int
    delta: float
    sessions: list[AssembledSessionRead]


class TrainingPackageRead(BaseModel):
    """``training_package`` 那一列（以及覆盖之后的**生效**包）的 4 个键。

    ⚠️ **它不含 ``assembly_snapshot``**：那一列有自己的字段（见 :class:`PrescriptionRead`），
    投影函数刻意不把它复制进来（同一份数据的第二个住址，Global Constraint #3）。
    """

    template_id: str
    template_version: str
    paused: bool
    weeks: list[AssembledWeekRead]


class WeeklySheetRead(BaseModel):
    """**spec §8.4 的「本周训练单」**（``GET /api/students/{id}/weekly-sheet`` 的响应）。

    6 个键逐字照 P4-A1 的落地口径，也就是
    :func:`app.pipeline.prescription_stage.weekly_sheet_payload` 的输出。

    ⚠️⚠️ **刻意没有任何跨单位的周总量汇总字段**（Plan 02 的 P8-A1 传导到 API 侧）：
    ``volume_unit`` 的实测值域是 ``{min, reps, unspecified}`` 且**同一周里三个并存**，
    把它们相加就是 Plan 02 Task 5 的 F1-1 那个「混合量纲 float」错误
    ——**48 分钟 + 120 次 = 168 什么？** 故本模型里**唯一的 ``float`` 是 ``factor``**。
    **前端要显示总量必须自己按 ``volume_unit`` 分列。**
    守卫是 ``test_the_sheet_has_no_cross_unit_total_field``（按**键集相等**断言，
    于是谁加一个 ``total_volume`` 当场红）。

    ⚠️ **``paused=True`` 时 ``sessions`` 照样带全**（Plan 02 的 P8-A3）：
    「暂停」与「本周量为 0」是两件不同的事，前端靠 ``paused`` 这一格决定渲染什么。
    守卫是 ``test_weekly_sheet_reports_paused_and_keeps_the_sessions``。

    ⚠️ ``factor`` 是**裸乘积、不 round**（``0.8 × 0.9`` 就是 ``0.7200000000000001``）：
    只有 ``weekly_volume`` 落 ``round(…, 1)``。round 一次会让教师端显示的系数与
    ``weekly_volume`` 的实际倍数对不上账（Plan 02 的 P5-A6）。
    """

    week: int
    factor: float
    reasons: list[str]
    sources: list[str]
    paused: bool
    sessions: list[AssembledSessionRead]


class OverrideCreate(BaseModel):
    """**教师覆盖的请求体**：``OverrideRecord`` 那 7 个字段里的**前 5 个**（P4-A3）。

    ⚠️⚠️ **后两个字段刻意不在本模型里**（``teacher_staff_no`` / ``applied_at``），
    而它们**必须由服务端填**：

    * ``teacher_staff_no`` ← ``X-Teacher-Staff-No`` 请求头（:func:`app.api.deps.current_teacher`）。
      让客户端传等于**让它能冒充别的教师**——而 spec §7.5 末段把这些记录当**研究数据**
      （「学期末回答教师在哪些环节最不信任算法」），一个可以随便填的署名让那份数据作废。
    * ``applied_at`` ← 服务端的 ``datetime.now()``。让客户端传等于**让它能伪造时间**，
      而 ``teacher_overrides`` 那个 JSON 列表的顺序是承重的（Plan 02 的 5.4），
      审计时唯一能交叉核对的就是这个时刻。

    ⚠️ 于是**多传这两个键不报错、但会被忽略**（Pydantic 缺省 ``extra="ignore"``）。
    那是有意的：前端从 ``GET`` 读回一条覆盖记录（7 个字段）、原样 POST 回来是**最常见**
    的写法，为它报 422 会让「编辑一条覆盖」变成一个必须手工删键的操作。
    守卫是 ``test_the_override_request_model_cannot_carry_the_two_server_filled_fields``
    ——它钉的是「这两个字段**不在模型上**」（于是服务端填的那一份不可能被请求体覆盖），
    而不是「多传会 422」。

    ⚠️ **``kind`` 的值域直接引 :class:`~app.domain.prescription.override.OverrideKind`**
    （P4-A3：不在 schema 里抄第二份字符串）。实测那 5 个值是 ``weekly_frequency`` /
    ``substitute_exercise`` / ``intensity_step`` / ``volume_scale`` / ``pause``
    ——⚠️ **下划线，不是连字符**（与 URL 的惯例相反，别照着 ``/api/course-sections``
    的写法填）。故一个域外值由 Pydantic 折成 **422 request_validation_failed**。

    ⚠️ **``old_value`` / ``new_value`` 一律 ``str``、不用联合类型**（Plan 02 已定，
    传导第 5 条）：它们要落进一个 JSON 列，异构类型会让那一列的形状不稳定。
    解析失败一律是**响的**（``int("abc")`` / ``float("abc")`` 由 domain 自己抛
    ``ValueError`` → 422），故本模型不写校验器。

    ⚠️ **``reason`` 不在这里校验非空**（Plan 02 传导第 4 条）：那条规则的所有者是
    ``OverrideRecord.__post_init__``，在 API 层再校验一遍就是第二个所有者。
    domain 抛的 ``ValueError`` 经 :mod:`app.api.errors` 折成 **422**，消息原文照发。
    守卫是 ``test_an_empty_override_reason_is_422_with_the_domain_message``。
    """

    kind: OverrideKind
    #: ``None`` = 作用于整包（``weekly_frequency`` / ``pause`` 一律 ``None``；
    #: ``intensity_step`` / ``volume_scale`` 给 ``None`` 表示全部 block）；
    #: ``substitute_exercise`` **必须**给一个 ``exercise_ref``。
    #: ⚠️ 打错的 ``target`` 由 domain 响亮拒绝（``ValueError`` → 422），
    #: **不静默无事发生**——教师会以为自己已经改过了。
    target: str | None = None
    old_value: str
    new_value: str
    reason: str


class OverrideRecordRead(BaseModel):
    """``prescription.teacher_overrides`` 那个 JSON 列表里的一项（**7 个字段**）。

    字段名与顺序 = :class:`~app.domain.prescription.override.OverrideRecord` 的 7 个，
    也就是 :func:`app.pipeline.prescription_stage.override_record_payload` 的输出键。

    ⚠️ ``kind`` 在这里是**裸 ``str``**（与 :class:`OverrideCreate` 的枚举标注不同）：
    读回来的是库里存的 ``.value``，前端拿它当只读文案；再收窄成枚举只会让
    「库里有一个不认识的值」变成一次 500 而不是一条能显示出来的数据。
    ⚠️ ``applied_at`` 是 ``datetime``：投影那一侧写的是 ``.isoformat()``，
    Pydantic 解析回 ``datetime``，再序列化出去仍是 ISO 串（往返一致）。
    """

    kind: str
    target: str | None
    old_value: str
    new_value: str
    reason: str
    teacher_staff_no: str
    applied_at: dt.datetime


class OverrideResultRead(BaseModel):
    """``POST /api/prescriptions/{id}/overrides`` 的响应。

    * ``prescription_id`` —— 被改的那一张。
    * ``overrides`` —— **改完之后的完整列表**，顺序就是列表顺序
      （⚠️ **承重**：Plan 02 的 5.4 定的是「多条覆盖同一目标由列表顺序决定、后者胜」）。
      前端不必自己维护那份列表，直接用它重渲染即可；刚加的那一条恒为 ``overrides[-1]``。
    * ``training_package`` —— **覆盖之后生效**的那一份包（骨架 × 全部覆盖）。
      ⚠️ 库里 ``prescription.training_package`` 那一列**一个字都没改**
      （它永远是算法基线，spec §7.5「下次自动生成回到算法基线」靠的就是这件事），
      这一格是**现算的**投影，故教师能立刻看到自己那一条覆盖的效果。
    """

    prescription_id: int
    overrides: list[OverrideRecordRead]
    training_package: TrainingPackageRead

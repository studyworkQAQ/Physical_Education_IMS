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

from app.api.schemas._base import ReadModel

__all__ = [
    "ExerciseRead",
    "PrescriptionRead",
    "PrescriptionTemplateRead",
    "WeeklyAdjustmentRead",
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

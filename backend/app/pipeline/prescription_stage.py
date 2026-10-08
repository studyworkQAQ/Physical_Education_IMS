"""处方生成阶段：spec §5.2 五触发 → §7.1 匹配 → §7.3 装配 → §7.4 安全后置 → 落库（Plan 02 Task 7）。

它是 :mod:`app.pipeline.daily` 的第六个阶段（``Extract → Clean → Percentile → Derive →
Stratify → **Prescribe** → Commit``），读的是**当天刚写好的** ``stratification_result``
（含它的 ``input_snapshot``），**不重算任何一遍分层**——算法一律复用 domain
（:func:`~app.domain.prescription.match.match_template` /
:func:`~app.domain.prescription.triggers.evaluate_triggers` /
:func:`~app.domain.prescription.assembler.assemble` /
:func:`~app.domain.prescription.safety.apply_safety`），本模块只负责「从库里取输入、
把产出写回库、以及把不可自动化的那一档如实交代出来」。

``app/pipeline/`` 不在 domain 层，可以碰数据库与时钟；Task 1 的三个 AST 守卫只扫
``app/domain/``。

--------------------------------------------------------------------------

**处方不每天重发**（spec §5.2）。分层重算每天跑，而一张 4 周训练包只在
:func:`~app.domain.prescription.triggers.evaluate_triggers` 报出至少一条触发原因时才生成。
于是本阶段的常态是**绝大多数学生被跳过**——``PrescriptionReport.skipped`` 通常远大于
``generated``，这不是故障。守卫是
:func:`~tests.pipeline.test_prescription_stage.test_no_trigger_means_no_new_prescription`。

--------------------------------------------------------------------------

⚠️⚠️ **异常分层：按学生捕获，只有基础设施异常才冒泡**（简报 Task 7「决定」第 2 条）。

本阶段跑在 :func:`app.pipeline.daily.run_daily` 的那个 ``session.begin_nested()``
SAVEPOINT 里，与分层阶段共用一个原子边界。理由与代价是同一件事的两面：

* **理由**：处方失败不该留下「分层写了、处方没写」的半天状态；
* **代价**：SAVEPOINT 内任何未捕获的异常都会让**整批**（分层 + 快照 + 派生）一起回滚。
  一个学生的装配失败因此能掀掉一整天的批处理。

故本模块把异常分成两层，**分界线就是那段 ``try`` 的位置**：

1. **算法/数据异常（按学生捕获）**：``assemble`` 与 ``apply_safety`` 都是纯函数，它们能抛的
   只有 ``ValueError`` / ``KeyError`` / ``TypeError`` 这一类「这一个学生的输入有问题」
   ——年龄荒谬（Review Focus 第 4 条：``hrmax`` 对 ``age <= 0`` / ``>= 100`` 响亮拒绝）、
   ``structure`` 键集不认识、``exercise_ref`` 不在动作库里、模板的 ``week_deltas`` 与
   ``microcycle_weeks`` 不符。这一档**不写处方行**，而是：计入
   ``PrescriptionReport.needs_review``、在 ``skipped_reasons`` 里记
   :data:`ASSEMBLY_ERROR`、写一条 ``warning`` 日志（带学号 / 模板 id / 异常类型与消息），
   然后 ``continue`` 到下一个人。
   ⚠️ **为什么不落一张 ``status = "needs_review"`` 的行**：那一行得带一个
   ``training_package``，而装配已经失败了、没有任何包可写；一个 ``training_package = {}``
   的处方行是**撒谎**（它声称有一张待复核的训练包，而教师打开来是空的、也无从改）。
   「转成 needs_review」因此落在**报表的那一格**上（要人工过目的学生数），不是行上。
   留痕走日志 + 计数，两者都能交代「谁、哪套模板、为什么」。
   守卫：:func:`~tests.pipeline.test_prescription_stage.test_per_student_assembly_failure_does_not_roll_back_the_batch`。
2. **基础设施异常（原样冒泡）**：DB 读写（:func:`_previous_prescriptions` /
   ``repo.upsert`` / ``session.flush``）
   一律在 ``try`` **之外**，故 ``IntegrityError`` / ``OperationalError`` 一类直接抛给
   :func:`app.pipeline.daily.run_daily`，由它回滚整批并写一条 ``status = "failed"`` 的
   运行记录。这是**期望**行为：库写不进去时继续跑只会产出一份与库不符的报表。

--------------------------------------------------------------------------

⚠️ **``prescription.status`` 的映射与它的优先级**（Ruling 10，计划原文没写）：由
:func:`active_or_needs_review` 单点持有——**``needs_review`` 优先于 ``active``**，
一张待人工复核的处方不能被学生端当成生效处方执行（spec §7.4 末段「宁可不自动，
也不要自动错」）。``SafetyOutcome.needs_review`` **只由「安全规则命中却找不到等价动作」
置位**（Task 5 的 P5-A3），故这一档的语义是明确的。换处方时上一张置 ``"replaced"``。
``"archived"`` 今天没有写入方（学期结束/学生离校归档是 Plan 03 的活）。

--------------------------------------------------------------------------

⚠️ **``weekly_adjustment.batch_id`` 的口径**（Task 6 结案时按硬规矩 #86 传导过来的第 3 件事；
同一句话也写在 :attr:`app.db.models.prescription.WeeklyAdjustment.batch_id` 的列注释里）。
本阶段**不写** ``weekly_adjustment`` 行——``source = "teacher"`` 由 Plan 03 的教师端写、
``source = "auto"``（spec §8.4「预警触发减量 20%」）也留给 Plan 03。本模块对这张表的参与有
**两处、都不是写**：① :func:`app.pipeline.daily._replay_cleanup` 按 ``batch_id`` 删它
（且**必须排在 ``prescription`` 前面**，P7-A4）；② Task 8 的 :func:`weekly_factors_of`
**读**它并转成 :class:`~app.domain.prescription.weekly.WeeklyFactor` 值对象
（⚠️ 它今天在生产路径上**没有调用方**、那张表也**没有数据**，理由与守卫口径逐字写在它的
docstring 里，P8-A4）。口径：

* 管道生成的调整行（今天没有）带**本批**的 ``batch_id``；
* **教师手工加的调整行没有批次**，取**该行所属处方当前的 ``batch_id``**；处方尚未落库时
  取本次运行的批次。

⚠️ 这个口径有一条**代价**，如实记录（硬规矩 #39）：教师手工加的调整行因此继承处方的
``batch_id``，而 :func:`app.pipeline.daily._replay_cleanup` 按 ``batch_id`` 整批删——
于是**重放那一天会把教师当天的手工微调一起删掉**。这与「重放同一天的处方会丢掉教师覆盖」
是同一条代价的两个面（``prescription.teacher_overrides`` 同样随 ``_replay_cleanup`` 消失）。
本仓不做迁移、也没有「人工数据豁免于重放」的机制，故不擅自加一个；已登记为关切。

--------------------------------------------------------------------------

⚠️ **日志的分档是刻意的**（噪声与可交代性之间的取舍）：

* **``warning``**（每人一条）：安全后置产出了 ``warnings``（spec §7.4 / Review Focus 第 5 条
  逐字要求「写 ``warning`` 日志」）、模板匹配没匹配上、装配抛异常。三档在生产上都**罕见**。
* **``warning``**（每批一条）：``insufficient_data`` 的人数汇总。⚠️ **这一档刻意不做
  每人一条 ``warning``**，逐人那条走 ``debug``（缺省不输出，开 ``DEBUG`` 就逐人可见）。
  量级（本轮亲跑，500 人 / ``seed=20250828`` / 整学期 112 业务日回放）：缺省注入下
  **每天 2 人**落 Z0（``insufficient_data`` 的分层结果行合计 **224** = 2 × 112，
  处方 **498 / 500** 张），零注入下 **0 人**（处方 **500 / 500**）。逐人 ``warning`` 于是
  是每季 224 条**内容完全相同**的重复警告，而那正好淹掉真正罕见的那几条
  （安全后置的 ``needs_review``、装配失败）。逐人可查的载体本来就在库里：
  ``stratification_result.label``，那一行正是为 Z0 而存在的。
  ⚠️ 60 人的 ``tests/pipeline/test_daily.py`` 夹具在 ``D = 2025-09-15`` 上是 **0** 人
  （实测标签分布 ``{yellow: 29, green: 24, red: 7}``），故那一档只能由
  ``tests/pipeline/test_prescription_stage.py`` 的 ``bare`` 夹具守。
* **``info``**（每批一条）：``generated`` / ``skipped`` / ``needs_review`` 三个计数。
* ``no_trigger`` **一条都不记**：它是常态（处方不每天重发），记了就是纯噪声。

--------------------------------------------------------------------------

⚠️ **``semester_id`` 这个形参不是被接收然后被丢弃的**（Ruling 86 的口径：一个被接收然后
被丢弃的参数是撒谎）。``prescription`` 表**没有** ``semester_id`` 列，故它不落库；
它在这里做两件事：① **前置校验**（:func:`_require_batch_in_semester`）——``batch_id``
那一行 ``daily_sync_run`` 必须属于 ``semester_id``；② 进日志上下文。①挡的是接线错误：
``_replay_cleanup`` 按 ``batch_id`` 删，接错批次会让重放删不到本批的处方行、于是翻倍
（Plan 01 Ruling 32 的同源缺陷）。守卫是
:func:`~tests.pipeline.test_prescription_stage.test_a_batch_from_another_semester_is_rejected_loudly`。
"""
import datetime as dt
import logging
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only

from app.db import models, repo
# ⚠️ **两张处方表刻意不在 ``app.db.models`` 的公有导入面上**（Ruling 97 / Task 6 的顶回 1）：
# 写 ``models.Prescription`` 会当场 AttributeError，而那两条守卫
# （test_plan02_tables_stay_out_of_the_models_public_namespace 与
#  test_models_public_namespace_is_unchanged_by_the_split）也就同时失去意义。
# Prescription 是生成路径要写的行；WeeklyAdjustment 是 Task 8 的 weekly_factors_of 要读的行
# （本模块**仍不写**调整行，见模块 docstring），删除在 daily._replay_cleanup 里。
from app.db.models.prescription import Prescription, WeeklyAdjustment
from app.domain.indicators import ITEM_BUCKET, ScoredItem, Sex
from app.domain.prescription.assembler import StudentProfile, TrainingPackage, assemble
from app.domain.prescription.exercises import EquivalenceTable, ExerciseSpec
from app.domain.prescription.intensity import age_from
from app.domain.prescription.match import MatchInput, MatchStatus, match_template
from app.domain.prescription.safety import SafetyInput, apply_safety
from app.domain.prescription.templates import Template, WeaknessBucket
from app.domain.prescription.triggers import (
    LastPrescription, TriggerInput, evaluate_triggers,
)
from app.domain.prescription.weekly import WeeklyFactor
from app.domain.stratify import Layer

__all__ = [
    "ASSEMBLY_ERROR",
    "INSUFFICIENT_DATA",
    "NO_TRIGGER",
    "REPLACED",
    "PrescriptionReport",
    "active_or_needs_review",
    "generate_prescriptions",
    "profile_of",
    "training_package_payload",
    "valid_to_of",
    "weekly_factors_of",
]

logger = logging.getLogger(__name__)

#: ``PrescriptionReport.skipped_reasons`` 里**三个不属于 ``MatchStatus``** 的键。
#:
#: * :data:`INSUFFICIENT_DATA` —— Z0 闸门（``valid_count < 4``）拦下的学生。
#:   ⚠️ **它必须有**（Task 6 实现者报的最高优先级关切）：
#:   :func:`~app.domain.prescription.triggers.evaluate_triggers` 是纯函数、**没有任何渠道**
#:   把「为什么返回空 tuple」传出来，而这一档会让教师端的「重新生成」按钮**无声失败**
#:   （Review Focus 第 3 条：「不得生成处方，且必须留下可交代的痕迹」）。
#:   取值**读枚举、不写第二份字面串**（Global Constraint #3 单一所有者）：它就是
#:   :attr:`app.domain.stratify.Layer.INSUFFICIENT` 的 ``.value``，与 ``triggers.py``
#:   第 0 条早退读的是同一个所有者（漂移守卫
#:   ``tests/domain/test_prescription_triggers.py::test_insufficient_label_value_is_pinned_verbatim``）。
#: * :data:`NO_TRIGGER` —— 五条触发一条都不成立（今天的常态）。
#: * :data:`ASSEMBLY_ERROR` —— ``assemble`` / ``apply_safety`` 抛了异常（见模块 docstring
#:   的「异常分层」第 1 档）。⚠️ **这一档同时计入 ``needs_review``**，故它既在 ``skipped``
#:   里也在 ``needs_review`` 里——两个计数不是互斥的两半。
INSUFFICIENT_DATA = Layer.INSUFFICIENT.value
NO_TRIGGER = "no_trigger"
ASSEMBLY_ERROR = "assembly_error"

#: 换处方时上一张的 ``status``。取值域是
#: :attr:`app.db.models.prescription.Prescription.STATUSES` 的四个之一。
REPLACED = "replaced"

#: 耐力桶的计分项（实测两项：``vital_capacity`` 与 ``distance_run``）。
#: ⚠️ **从 :data:`app.domain.indicators.ITEM_BUCKET` 派生、不手抄两项**
#: （Global Constraint #3）：``ITEM_BUCKET`` 是「哪一项归哪个桶」的唯一所有者，
#: 桶名那一份取自 :class:`~app.domain.prescription.templates.WeaknessBucket`
#: （``"endurance"`` 的字面串不在本模块出现第二次）。手抄一份
#: ``("vital_capacity", "distance_run")`` 的后果是：国标口径调整（某一项改归别的桶）时
#: 本模块静默算错 ``endurance_score``，而它是装配器三档个体修正系数的唯一输入。
_ENDURANCE_ITEMS: tuple[ScoredItem, ...] = tuple(
    item for item in ScoredItem if ITEM_BUCKET[item] == WeaknessBucket.ENDURANCE.value
)


@dataclass(frozen=True)
class PrescriptionReport:
    """一次处方阶段的产出计数。字段名照简报 Interfaces / Produces 逐字。

    ``generated`` 是**真的写进了 ``prescription`` 表的张数**（含 ``status =
    "needs_review"`` 的那些），也就是 :attr:`app.db.models.ops.DailySyncRun.prescription_count`
    要落的值（守卫
    :func:`~tests.pipeline.test_prescription_stage.test_daily_sync_run_prescription_count_matches_the_report`）。

    ``needs_review`` 是**要人工过目的学生数**，两个来源相加（见模块 docstring 的
    「异常分层」）：① 落库为 ``status = "needs_review"`` 的张数（安全规则命中却找不到
    等价动作，spec §7.4 / Review Focus 第 5 条）；② 装配/安全后置抛异常因而**没有**处方的
    学生数。⚠️ 于是 ``needs_review`` **可以大于** ``generated``，两者不是包含关系。

    ``skipped`` = ``insufficient_data`` + ``no_trigger`` + 五种非 ``MATCHED`` 的
    ``MatchStatus`` + ``assembly_error`` 的人数之和，即「今天来过、但没拿到新处方」的人数。
    恒有 ``generated + skipped == 本日分层结果的行数``（守卫
    :func:`~tests.pipeline.test_prescription_stage.test_report_counts_add_up_to_every_stratified_student`）。

    ``skipped_reasons`` 是**稀疏**的：只出现计数 > 0 的键。这是刻意的——若六个
    ``MatchStatus`` 一律以 0 入字典，``tests`` 里那条
    ``assert "no_bucket" not in report.skipped_reasons``（Ruling 11 的唯一守卫）就会恒假，
    而它要钉的正是「生产路径上 ``NO_BUCKET ⊆ NO_LAYER``、故这一格永远为 0」。
    """

    generated: int
    skipped: int
    needs_review: int
    skipped_reasons: dict[str, int]


def valid_to_of(generated_on: dt.date, microcycle_weeks: int) -> dt.date:
    """``valid_to = generated_on + microcycle_weeks 周 − 1 天``（**首尾都算在内的闭区间**）。

    出处是 :class:`app.db.models.prescription.Prescription` 那一列的注释（Task 6 结案时
    写定的口径）：``microcycle_weeks = 4``、``generated_on = 2026-03-02`` → ``valid_to =
    2026-03-29``，那正是第 **28** 天。

    ⚠️ **``− 1 天`` 是承重的**（简报 Step 2–6 的变异 ④ 打的就是它）：它与
    :func:`~app.domain.prescription.triggers.evaluate_triggers` 触发 3 的 ``>=`` 边界
    **差一天、而且应该差一天**——``2026-03-30 − 2026-03-02 = 28 天 >= 4 × 7`` → 触发 3 在
    ``03-30`` 开火，即新处方在旧处方到期的**次日**生成，两者既不重叠也不留空档。
    删掉 ``− 1 天`` 会让 ``03-30`` 这一天同时被两张处方认领。守卫：
    :func:`~tests.pipeline.test_prescription_stage.test_valid_to_is_generated_on_plus_microcycle_minus_one_day`。

    ``microcycle_weeks`` 从**处方行**取（Task 6 的 P6-A3 把它快照在
    :attr:`~app.db.models.prescription.Prescription.microcycle_weeks` 上），**不硬编码 4**：
    模板会改版，而一张 2026-03 生成的处方必须能在 2027 年离线复算出它当时的 ``valid_to``
    （spec §4.3）。

    ⚠️ 用 ``dt.timedelta(weeks=…)`` 而**不是** ``days=microcycle_weeks * 7``：「一周 7 天」
    这条历法事实的所有者是 :mod:`app.domain.prescription.triggers` 的 ``_DAYS_PER_WEEK``，
    在管道层再写一个 ``* 7`` 就是第二个住址（Global Constraint #3）。
    """
    return generated_on + dt.timedelta(weeks=microcycle_weeks) - dt.timedelta(days=1)


def active_or_needs_review(needs_review: bool) -> str:
    """``prescription.status`` 的映射，**``needs_review`` 优先于 ``active``**（Ruling 10）。

    做成一个独立的小函数而不是在落库那一行写三元表达式，是为了让「优先级」这件事有一个
    可以被单独钉住的名字：一张待人工复核的处方**不得**被学生端当成生效处方执行
    （spec §7.4 末段「宁可不自动，也不要自动错」）。守卫是
    :func:`~tests.pipeline.test_prescription_stage.test_needs_review_wins_over_active_in_the_status_mapping`
    与它的端到端版本
    :func:`~tests.pipeline.test_prescription_stage.test_needs_review_when_no_equivalent_exercise`。

    取值域是 :attr:`app.db.models.prescription.Prescription.STATUSES` 的四个之二；
    另两个（``"replaced"`` / ``"archived"``）不由生成路径写。
    """
    return "needs_review" if needs_review else "active"


def training_package_payload(pkg: TrainingPackage) -> dict:
    """:class:`~app.domain.prescription.assembler.TrainingPackage` → ``prescription.training_package`` 的 JSON 形态。

    ⚠️ **必须显式逐字段摊平，不能 ``dataclasses.asdict``、更不能直接丢给 ``JsonText``**：
    :attr:`~app.domain.prescription.assembler.AssembledBlock.structure` 是
    :class:`types.MappingProxyType`，而 ``json.dumps`` 对它当场
    ``TypeError: Object of type mappingproxy is not JSON serializable``
    （``isinstance(proxy, dict)`` 为 ``False``）——:class:`~app.db.models._shared.JsonText`
    的 ``process_bind_param`` 就是裸 ``json.dumps(value, ensure_ascii=False)``，
    **没有 ``default=`` 兜底**。``dataclasses.asdict`` 也救不了：它对 ``Mapping`` 只做递归
    ``copy.deepcopy``，``MappingProxyType`` 原样留下。

    **``assembly_snapshot`` 刻意不进这一列**：它有自己的列
    （:attr:`~app.db.models.prescription.Prescription.assembly_snapshot`），复制一份进来
    就是同一份数据的第二个住址（Global Constraint #3），而它恰好是 Task 5 用两条键集守卫
    钉死的那 12 + 3 个键。

    枚举一律写 ``.value``：``ImpactLevel`` 继承 ``str``，``json`` 的 C 编码器**认**它，
    但显式 ``.value`` 让落库字节只由内容决定（canonical dump 才可复现，与
    :func:`app.refdata_prescription.sync_exercises` 对 ``targets`` 排序是同一条理由）。

    ⚠️ **``hr_zone`` 显式转 ``list``**：它在 domain 侧是 ``tuple[int, int]``，而 JSON 没有
    tuple——``json.dumps`` 会把它写成数组、读回来是 ``list``。不转的话「写进去的那个对象」
    与「读回来的那个对象」**不相等**（``(116, 137) != [116, 137]``），于是
    ``test_training_package_payload_survives_a_json_round_trip`` 那条 round-trip 断言
    会红，而任何拿内存里的包与库里的行对账的代码都会得到一个假的「不一致」。
    """
    return {
        "template_id": pkg.template_id,
        "template_version": pkg.template_version,
        "paused": pkg.paused,
        "weeks": [
            {
                "week": week.week,
                "delta": week.delta,
                "sessions": [
                    {
                        "day": session.day,
                        "focus": session.focus,
                        "blocks": [
                            {
                                "exercise_ref": block.exercise_ref,
                                "exercise_name": block.exercise_name,
                                "video_url": block.video_url,
                                "impact_level": block.impact_level.value,
                                "intensity_text": block.intensity_text,
                                "hr_zone": (
                                    None if block.hr_zone is None else list(block.hr_zone)
                                ),
                                # MappingProxyType -> dict（见 docstring）
                                "structure": dict(block.structure),
                                "weekly_volume": block.weekly_volume,
                                "volume_unit": block.volume_unit,
                                "sessions_per_week": block.sessions_per_week,
                            }
                            for block in session.blocks
                        ],
                    }
                    for session in week.sessions
                ],
            }
            for week in pkg.weeks
        ],
    }


def weekly_factors_of(session: Session, prescription_id: int) -> list[WeeklyFactor]:
    """一张处方的**全部**周微调行 → :class:`WeeklyFactor` 值对象列表（ORM → domain 的转换）。

    spec §8.4 的两层拆分里，本函数是第二层的**读取口**：训练包是骨架（第一层），微调叠在
    它上面（第二层）；:func:`~app.domain.prescription.weekly.weekly_training_sheet` 把两层
    乘起来，而它要的 ``adjustments`` 就是本函数的返回值。转换只发生在 pipeline 层
    ——**domain 不认识 ORM**（Ruling 97：``WeeklyAdjustment`` 也不在 ``app.db.models`` 的
    公有导入面上，故 import 路径是 ``app.db.models.prescription``）。

    ⚠️ **今天没有生产调用方**（硬规矩 #39）：``weekly_adjustment`` 表**今天 0 行**——
    ``source = "auto"`` 是 Plan 03 的预警落地、``source = "teacher"`` 要等 Plan 03 的教师端
    CRUD API。本函数是给 Plan 03 的 API 层准备的（学生端「本周训练单」那一个 endpoint），
    与 Task 2 的 :func:`app.refdata_prescription.sync_exercises` / ``sync_templates`` 同一条
    先例：**能力先落地、调用方后到**。故它的守卫全部靠**直接插 ``WeeklyAdjustment`` 行**
    喂它（``tests/pipeline/test_prescription_stage.py``），不靠管道产出。

    ⚠️⚠️ **排序必须是 ``ORDER BY created_at, id``**（P8-A4）：``created_at`` 是
    ``DateTime NOT NULL`` **且无缺省**（时钟由调用方注入），故**同一秒批量插入的多条调整
    ``created_at`` 相等**——没有 tie-breaker 时顺序就交给查询计划，换引擎/换计划就可能变。
    ``id`` 作 tie-breaker，与 Task 5（5.4）「多条覆盖同一目标由列表顺序决定」是同一条理由。

    ⚠️ **这个顺序是承重的**，有两个后果：① ``WeeklySheet.reasons`` / ``sources`` 的顺序
    **就是**本列表的顺序（:class:`~app.domain.prescription.weekly.WeeklyFactor` 没有时间戳
    字段，故读模型**结构上不可能**自己排序）；② 相乘的顺序决定浮点尾数
    （``0.8 × 0.9 == 0.7200000000000001``），而那个尾数会出现在教师端显示的系数上。

    ⚠️ **本函数守不住什么**（硬规矩 #39）：``created_at`` 相同时的 ``id`` 顺序在 **SQLite 上
    本来就等于物理扫描顺序**（``INTEGER PRIMARY KEY`` 是 rowid 别名，表是 B-tree，全表扫描
    恒按 rowid 升序），故「删掉 ``, id``」这个变异在 SQLite 上**不会**让数据面的断言变红。
    钉住它的是那条**SQL 形状**断言
    （``test_weekly_factors_of_breaks_a_created_at_tie_by_id``，它检查真正发出的
    ``ORDER BY`` 子句里 ``created_at`` 在 ``id`` 之前）。

    **不按 ``week`` 过滤**：返回的是这张处方**全部周**的调整，挑出第 N 周的那些是
    :func:`~app.domain.prescription.weekly.weekly_training_sheet` 的活（它按
    ``adjustment.week == week`` 过滤）。于是「一次查询 → 四周的训练单」是可能的，
    而不必逐周查四次。

    ⚠️ **「查无此处方」与「有处方但零条调整」都返回空列表，本函数不区分**：两者的正确
    渲染都是「本周没有微调、照骨架执行」，而区分它们需要多查一次 ``prescription``
    ——Plan 03 的 API 层本来就持有那一行（它得先知道 ``generated_on`` 与
    ``microcycle_weeks`` 才能调 :func:`~app.domain.prescription.weekly.current_week`），
    故由它去区分。

    ⚠️ **一条脏行会让本函数抛 ``ValueError``**：:class:`WeeklyFactor` 的 ``__post_init__``
    校验 ``factor ∈ (0, 2]``，而 DB 的 ``weekly_adjustment.factor`` 列**刻意没有** CHECK
    （P8-A6：那是**读模型的语义**、不是数据的形状）。于是「有人绕过 domain 直接写库一条
    ``factor = 0``」会在**读侧**响亮失败，而不是渲染出一张「本周量全是 0」的训练单。
    这是期望行为，但要知道它是读侧抛的（离真因隔了一次查询）。
    """
    rows = session.execute(
        select(WeeklyAdjustment)
        .where(WeeklyAdjustment.prescription_id == prescription_id)
        # ⚠️ 两个排序键都必须显式（P8-A4，理由见 docstring）：created_at 定「创建的先后」，
        #    id 定「同一秒批量插入时的先后」。少写 id 在 SQLite 上碰巧还是对的，换引擎就不一定。
        .order_by(WeeklyAdjustment.created_at, WeeklyAdjustment.id)
    ).scalars().all()
    return [
        WeeklyFactor(
            week=row.week,
            factor=row.factor,
            reason=row.reason,
            source=row.source,
        )
        for row in rows
    ]


def _endurance_score(curr_scores: Mapping[str, object]) -> float | None:
    """``endurance_score`` = 耐力桶那两项国标得分的**算术均值**（spec 最欠定的一步之一）。

    口径逐字照 :mod:`app.domain.prescription.assembler` 的模块 docstring（登记为 spec §14
    #32）：两项都有值 → 均值；**只有一项有值 → 取那一项、不取半值**；两项都无值 → ``None``
    （装配器于是把个体修正系数置 ``1.0``、档名 ``"unknown"``）。

    ⚠️ **这个均值只能在这里算**：``StudentProfile.endurance_score`` 的 docstring 逐字写着
    「那个均值不在本模块算，否则口径就有两个住址」。全仓因此只有本函数一个所有者。

    ``curr_scores`` 是 ``input_snapshot["curr_scores"]``，键是 ``ScoredItem`` 的 ``.value``
    字符串（不是枚举成员）——:func:`app.pipeline.run_stratify.input_snapshot_of` 的
    docstring 解释了为什么必须用 ``.value``。
    """
    present = [
        value
        for value in (curr_scores.get(item.value) for item in _ENDURANCE_ITEMS)
        if value is not None
    ]
    if not present:
        return None
    return sum(present) / len(present)


def _profile_of(
    student: models.Student, snapshot: Mapping[str, object], as_of: dt.date
) -> StudentProfile:
    """``(Student 行, input_snapshot, 业务日期)`` → :class:`StudentProfile`。**纯映射，不查库。**

    逐格的来源（简报 Task 7「``profile_of`` 的输入来源」那一节，逐条对照）：

    ==========================  ==========================================================
    字段                          来源
    ==========================  ==========================================================
    ``student_id`` / ``sex``      ``Student`` 的两列
    ``birth``                     ``Student.birth``
    ``age``                       :func:`~app.domain.prescription.intensity.age_from`
                                  ``(birth, as_of)``，``as_of`` 是业务日期
    ``endurance_score``           ``input_snapshot["curr_scores"]`` 的耐力桶两项，
                                  经 :func:`_endurance_score`
    ``bmi``                       ``input_snapshot["bmi"]``（**原始值**，Task 7 加的键）
    ``body_fat_pct``              ``input_snapshot["body_fat_pct"]``
    ``muscle_mass_kg``            ``input_snapshot["muscle_mass_kg"]``
    ``muscle_p10``                ``input_snapshot["snapshot_muscle_p10"]``（同上，Task 7 加的键）
    ``measured_hrmax``            恒 ``None``（Plan 01/02 没有任何心率数据）
    ==========================  ==========================================================

    ⚠️ **一个键都不回查 ``fitness_test_result`` 重算**（简报 Task 7 的决定 + 守卫
    :func:`~tests.pipeline.test_prescription_stage.test_profile_of_reads_scores_from_input_snapshot_not_from_fitness_test_result`）：
    七项得分与 BMI 原始值都**已经在快照里**（Plan 01 存了得分，Task 7 补了原始值与 P10）。
    回查会产生第二个所有者——同一份身高体重在两处被算成 BMI，任一处改口径就漂移；
    更要紧的是它会让 spec §4.3 的可追溯性失效：快照是「判定当时的输入」，而
    ``fitness_test_result`` 是**会被后续批次 upsert 覆盖的**存量表，读它就等于用今天的
    数据解释昨天的处方。

    ⚠️ **``age`` 与 ``birth`` 同时给**是有意的冗余（:class:`StudentProfile` 的 docstring）：
    :func:`~app.domain.prescription.assembler.assemble` 第 1 步会**对账**
    ``age == age_from(birth, as_of)``，于是一个传错 ``as_of`` 的调用方当场就炸。
    """
    return StudentProfile(
        student_id=student.id,
        sex=Sex(student.sex),
        birth=student.birth,
        age=age_from(student.birth, as_of),
        endurance_score=_endurance_score(snapshot["curr_scores"]),
        bmi=snapshot["bmi"],
        body_fat_pct=snapshot["body_fat_pct"],
        muscle_mass_kg=snapshot["muscle_mass_kg"],
        muscle_p10=snapshot["snapshot_muscle_p10"],
        measured_hrmax=None,
    )


def profile_of(session: Session, student_id: int, as_of: dt.date) -> StudentProfile:
    """**单个学生**的 :class:`StudentProfile`（简报 Interfaces / Produces 钉住的签名）。

    它是 :func:`_profile_of` 的「带两次查询」外壳：读 ``student`` 那一行与 ``as_of`` 当天的
    ``stratification_result``，然后把映射交给同一个纯函数。**映射只有一个所有者**
    （``_profile_of``），故本函数与批处理循环不可能给出两个不同的 ``StudentProfile``。

    ⚠️ **批处理循环不调它**（硬规矩 #39：写下能力就写明谁在用它）：
    :func:`generate_prescriptions` 已经把 ``Student`` 与 ``StratificationResult`` 两行
    握在手里，逐人再查两次是 500 人 ×2 次纯浪费（``tests/pipeline/test_backfill.py`` 的
    ``elapsed < 60`` 是那条代价的守卫）。本函数的调用方是**单个学生**的入口：
    Plan 03 教师端的「给这一个学生重新生成」，以及本模块的测试。

    两档都响亮失败（``ValueError``）：查无此人、或当天没有分层结果。静默返回一个全
    ``None`` 的画像会让装配器给出 ``endurance_score = None`` → 系数 ``1.0`` →
    一张**看起来完全正常**的处方，而它其实建立在「这个人今天没被分层」之上。
    """
    student = session.get(models.Student, student_id)
    if student is None:
        raise ValueError(
            f"student 表里查无 id={student_id}：prescription.student_id 是 NOT NULL 外键，"
            f"没有归属就写不进去"
        )
    result = session.scalar(
        select(models.StratificationResult).where(
            models.StratificationResult.student_id == student_id,
            models.StratificationResult.computed_on == as_of,
        )
    )
    if result is None:
        raise ValueError(
            f"学生 {student_id} 在 {as_of.isoformat()} 没有分层结果"
            f"（stratification_result 查无 (student_id, computed_on) 这一行）："
            f"处方的全部判定输入都取自那一行的 input_snapshot，没有它就无从装配。"
            f"处方阶段必须跑在分层阶段之后（daily.py 的 Prescribe 在 Stratify 之后）"
        )
    return _profile_of(student, result.input_snapshot, as_of)


def _previous_prescriptions(session: Session, as_of: dt.date) -> dict[int, Prescription]:
    """**批级预取**：每个学生「``generated_on <= as_of`` 里最新的那一张处方」。

    返回 ``{student_id: Prescription}``。**它生成当时的分层标签就在这一行上**
    （:attr:`~app.db.models.prescription.Prescription.label_at_generation`），故不必再
    连第二张表，见下面第 3 条。

    ⚠️⚠️ **一次查询、不是每人一次，而且只取需要的列**（本模块承重的性能决定，实测数据
    见下）。三个坑，逐个说：

    1. **逐人查会超时**：整学期回放（500 人 ×112 业务日）逐人查会多出 **56 000** 次
       带 ORM 实例化的 SELECT。口径与 :func:`app.pipeline.percentile_stage.cohort_from_db`
       的批级预取一致。
    2. **整行 ORM 加载会把 ``training_package`` 一起 ``json.loads`` 出来**：
       :class:`~app.db.models.prescription.Prescription` 有 **5** 个 ``JsonText`` 列，
       其中 ``training_package`` 是 4 周 ×4 课 ×3 block 的嵌套字典（约 500 个键值对）。
       而本阶段只需要它的 7 个小列，**一个都不读那 4 个大列**——除了
       ``teacher_overrides``（``previous_had_overrides`` 要判它非空，而它通常是个空列表）。
       故用 ``load_only(...)`` 把 ``training_package`` / ``assembly_snapshot`` /
       ``safety_substitutions`` / ``trigger_reasons`` 四列**延迟加载**：不访问就不解析。
       ⚠️ 这是实测出来的：不延迟时整学期回放多花约 **30 s**（``52.89 s`` vs 基线
       ``28.4–34.0 s``），直接把 ``tests/pipeline/test_backfill.py`` 那条 ``elapsed < 60``
       的余量吃到 **1.1×**（硬规矩 #42 的线是 2×）。
    3. **不再连 ``stratification_result``**（Task 7 fix round 1 的 F1-1）：触发 2 要比的
       「生成当时的标签」现在住在处方行自己的 ``label_at_generation`` 上。**此前这里是
       一个 ``outerjoin``**，按 ``(student_id, computed_on == generated_on)`` 回读同一天
       的 ``stratification_result.label``；那样写有两个毛病：① 那是一个**跨表的隐式
       契约**，没有任何守卫钉住它；② :func:`app.pipeline.daily._replay_cleanup` 按
       ``batch_id`` 删分层行，**重放之后那一天的行可能已经不在了** → join 返回 ``NULL``
       → 触发 2 静默不成立（该换处方的时候不换），与 spec §4.3 的「离线可复算」相反。
       ⚠️ 当年之所以必须连表，是因为「按 ``computed_on`` 单列过滤用不上
       ``(student_id, computed_on)`` 那条唯一索引」→ 全表扫描（学期末 **56 000** 行、
       每行还带一个约 2 KB 的 ``input_snapshot``）；快照到行上之后这次连接整个消失。
       守卫：``tests/pipeline/test_prescription_stage.py`` 的
       ``test_trigger_2_survives_the_deletion_of_that_days_stratification_row``。

    取「最新一张」用**分组子查询**（``max(generated_on) GROUP BY student_id``）而不是把
    全部历史处方拉回来在 Python 里折叠：后者要读的行数随学期线性增长（第 112 天约
    **2 490** 行 ×112 天），而前者只返回**每人一行**。二级排序键在这里不需要：
    ``(student_id, generated_on)`` 上有唯一约束（``uq_prescription_student_day``），
    故 ``(student_id, max(generated_on))`` 至多命中一行。

    ⚠️ **``status`` 不进筛选**：``LastPrescription.status`` 也**不参与任何判据**（Task 6 的
    模块 docstring 倒数第一节给了两条理由：``needs_review`` 抑制触发 3 会让一张有安全问题
    的处方永远挂着不换；``archived`` 被当成「没有上一张」会让学期归档后的重新开学变成一次
    静默的首次生成）。「当前那一张」的定义就是 ``generated_on`` 最新的那一张。

    ⚠️ 标签**刻意不进** ``assembly_snapshot``：那 12 + 3 个键的契约被 Task 5 的两条键集
    守卫钉死，而 P6-A2 已经为 ``previous_had_overrides`` 否掉过「往快照加键」这个方案
    （快照的契约是「离线复算**本张**处方」，而「上一张处方生成当时的标签」是关于
    **另一张**处方的事实）。故它住在处方行自己的列上。
    """
    latest = (
        select(
            Prescription.student_id.label("student_id"),
            func.max(Prescription.generated_on).label("generated_on"),
        )
        .where(Prescription.generated_on <= as_of)
        .group_by(Prescription.student_id)
        .subquery()
    )
    rows = session.execute(
        select(Prescription)
        .options(
            load_only(
                Prescription.student_id,
                Prescription.generated_on,
                Prescription.template_ref,
                Prescription.microcycle_weeks,
                Prescription.label_at_generation,
                Prescription.status,
                Prescription.teacher_overrides,
            )
        )
        .join(
            latest,
            (Prescription.student_id == latest.c.student_id)
            & (Prescription.generated_on == latest.c.generated_on),
        )
    ).scalars().all()
    return {row.student_id: row for row in rows}


def _last_prescription_of(row: Prescription | None) -> LastPrescription | None:
    """:func:`_previous_prescriptions` 的一格 → :class:`LastPrescription`（domain 的值对象）。

    ⚠️ **``template_id`` 对的是 DB 的 ``template_ref`` 列**（Task 6 的 P6-A7）：两者是
    同一串字符（``RED-END-ABN-01`` 一类），只在 ORM 边界上换名字。别去 DB 里找一个叫
    ``template_id`` 的列、也别给 domain 的值对象加一个 ``template_ref`` 字段。

    ⚠️ ``microcycle_weeks`` 取**处方行**上那一份（Task 6 的 P6-A3 把它从模板快照下来），
    不去读今天的模板：模板会改版，而触发 3 要判的是「**上一张**处方的周期到了没有」。

    ⚠️ ``label_at_generation`` **同理**取处方行上那一份（Task 7 fix round 1 的 F1-1）：
    它是触发 2 判据的唯一输入，快照在行上才能离线复算（spec §4.3）。本列 **NOT NULL、
    无缺省**，故**「标签查不到」那一档已经不存在了**——此前那个响亮失败的
    ``ValueError``（以及它那条守卫
    ``test_a_prescription_whose_stratification_row_is_gone_fails_loudly``）在加了本列之后
    **结构上不可达**，已一并删掉；取代它的守卫是
    ``test_trigger_2_survives_the_deletion_of_that_days_stratification_row``
    （删掉那一天的分层行 → 触发 2 仍然成立）。于是本函数是一个**纯映射**、
    不再碰库，也不再属于「基础设施异常」那一侧。
    """
    if row is None:
        return None
    return LastPrescription(
        generated_on=row.generated_on,
        template_id=row.template_ref,
        label_at_generation=row.label_at_generation,
        microcycle_weeks=row.microcycle_weeks,
        status=row.status,
    )


def _latest_assessment(*dates) -> dt.date | None:
    """两张源表的「``<= as_of`` 最新采集日」折成一个（触发 4 的输入），全缺则 ``None``。

    ``None`` 是合法值：:func:`~app.domain.prescription.triggers.evaluate_triggers` 的
    触发 4 对它**短路**（把它当「很久以前」去比会 ``TypeError``，当「今天」去比会天天触发）。
    ``None`` 那一档在生产上意味着「这个学生本学期一次体测/体成分都没采到」——而那必然使他
    ``valid_count = 0`` → Z0 → 在第 ⓪ 步就被 ``insufficient_data`` 拦下，走不到这里。
    """
    present = [day for day in dates if day is not None]
    return max(present) if present else None


def _require_batch_in_semester(session: Session, semester_id: int, batch_id: int) -> None:
    """前置校验：``batch_id`` 那一行 ``daily_sync_run`` 必须属于 ``semester_id``。

    这是 ``semester_id`` 这个形参**没有被丢弃**的证据（见模块 docstring 末节）。
    两档都响亮失败：查无这一行（``prescription.batch_id`` 是 NOT NULL 外键，与
    :func:`app.pipeline.percentile_stage.needs_recompute` 同一条契约），或学期对不上
    （``_replay_cleanup`` 按 ``batch_id`` 删，接错了会让重放删不到本批的处方行、
    于是翻倍——Plan 01 Ruling 32 的同源缺陷）。
    """
    actual = session.scalar(
        select(models.DailySyncRun.semester_id).where(models.DailySyncRun.id == batch_id)
    )
    if actual is None:
        raise ValueError(
            f"daily_sync_run 里查无 id={batch_id}：prescription.batch_id 是 NOT NULL "
            f"外键，生成前必须已 upsert 当批运行记录并 flush 取回 id"
            f"（与 percentile_stage.needs_recompute 同一条契约）"
        )
    if actual != semester_id:
        raise ValueError(
            f"批次 {batch_id} 属于 semester_id={actual}，而调用方传的是 {semester_id}："
            f"两者必须是同一次运行。_replay_cleanup 按 batch_id 删，接错了会让重放"
            f"删不到本批的处方行、于是翻倍（Plan01 Ruling 32 的同源缺陷）"
        )


def generate_prescriptions(
    session: Session,
    semester_id: int,
    batch_id: int,
    as_of: dt.date,
    *,
    templates: Mapping[str, Template],
    exercises: Mapping[str, ExerciseSpec],
    equivalence: EquivalenceTable,
) -> PrescriptionReport:
    """为 ``as_of`` 当天**每一个已分层的学生**求五触发，命中者装配一张处方并落库。

    签名照简报 Interfaces / Produces 逐字。三份参考数据（18 套模板、动作库、等价映射表）
    一律由调用方注入（domain 不读盘 → 管道层读一次、逐人复用），生产路径上来自
    :func:`app.refdata_prescription.templates` / ``exercises`` / ``equivalence`` 三个
    进程内单例。

    **不 commit、不 rollback**：事务边界由 :mod:`app.pipeline.daily` 掌握（与
    :func:`app.db.repo.upsert` / :func:`app.pipeline.percentile_stage.run_percentile`
    同一条口径），「整批失败回滚」才成立。末尾 ``flush`` 一次：``prescription.status`` 的
    CHECK 约束与 ``(student_id, generated_on)`` 的唯一约束只在真正执行 INSERT/UPDATE 时
    才生效，不 flush 的话一次坏写入会推迟到调用方 commit 时才炸，离真因更远
    （与 :func:`app.refdata_prescription.sync_exercises` 同一条理由）。

    幂等：``prescription`` 的 ``UniqueConstraint("student_id", "generated_on")`` +
    :func:`app.db.repo.upsert`，与 Plan 01 的三张派生表同构（Review Focus 第 2 条：
    同一天被两次触发只生成一张处方，而**机制**是那条唯一约束、不是「记得先查一遍」）。
    重放清理见 :func:`app.pipeline.daily._replay_cleanup`（P7-A4：两张新表按 ``batch_id``
    删，且**子表先删**）。

    遍历的是**当天的 ``stratification_result`` 逐行 join ``student``**，不是 ``student``
    表的每一个人：本阶段的输入就是那一行（含 ``input_snapshot``），没有它无从装配。
    ``cohort_from_db`` 逐人写一行分层结果（含 Z0 那一档），故两者的人数今天恒等。
    """
    _require_batch_in_semester(session, semester_id, batch_id)

    # 每人「<= as_of 的最新一次采集日」：触发 4（体测/体成分数据刷新）的唯一输入。
    # **两张源表各一次分组查询、批级预取**，不逐人查（500 人 ×2 次是纯浪费）。
    # func.max 的返回类型由 SQLAlchemy 从参数列推断（sqlalchemy.sql.functions.max 是
    # ReturnTypeFromArguments），故读回来的是 datetime.date 而不是 ISO 字符串。
    latest_fitness = dict(
        session.execute(
            select(
                models.FitnessTestResult.student_id,
                func.max(models.FitnessTestResult.tested_on),
            )
            .where(models.FitnessTestResult.tested_on <= as_of)
            .group_by(models.FitnessTestResult.student_id)
        ).all()
    )
    latest_body = dict(
        session.execute(
            select(
                models.BodyComposition.student_id,
                func.max(models.BodyComposition.measured_on),
            )
            .where(models.BodyComposition.measured_on <= as_of)
            .group_by(models.BodyComposition.student_id)
        ).all()
    )

    generated = skipped = needs_review = 0
    reasons_count: dict[str, int] = {}

    def _skip(key: str) -> None:
        nonlocal skipped
        skipped += 1
        reasons_count[key] = reasons_count.get(key, 0) + 1

    # 每人「当前那一张处方」（生成当时的标签就快照在那一行上），**一次**批级预取
    # （三个坑与实测数据见 _previous_prescriptions 的 docstring：逐人查 / 整行加载 /
    # 连第二张表，各会让整学期回放多花几十秒）。
    previous_index = _previous_prescriptions(session, as_of)

    # ⚠️ **按 ``batch_id`` 过滤、不是只按 ``computed_on``**：``stratification_result`` 上
    # 只有 ``(student_id, computed_on)`` 一条唯一索引，按 ``computed_on`` 单列过滤用不上它
    # → 全表扫描（学期末 56 000 行、每行还带一个约 2 KB 的 ``input_snapshot``），
    # 而 ``batch_id`` 那一列**有索引**。两者同时施加：``batch_id`` 让它走索引，
    # ``computed_on`` 保住「本阶段读的是 as_of 那一天的分层结果」这个契约。
    # 同一批次里两者恒等价（daily._stratify_and_persist 用同一个 as_of 与 batch_id 写）。
    rows = session.execute(
        select(models.StratificationResult, models.Student)
        .join(models.Student, models.Student.id == models.StratificationResult.student_id)
        .where(
            models.StratificationResult.batch_id == batch_id,
            models.StratificationResult.computed_on == as_of,
        )
        .order_by(models.StratificationResult.student_id)
    ).all()

    for result, student in rows:
        label = result.label
        snapshot = result.input_snapshot

        # ⓪ Z0 闸门拦下的学生：**不得生成处方**，且必须留痕（Review Focus 第 3 条）。
        #    ⚠️ 必须在 evaluate_triggers **之前**分出来：那个纯函数对这一档返回空 tuple，
        #    与「五条一条都不成立」的空 tuple **同形**，事后无从区分——而教师端的
        #    「重新生成」按钮对前者是**无声失败**（Task 6 实现者报的最高优先级关切）。
        if label == INSUFFICIENT_DATA:
            _skip(INSUFFICIENT_DATA)
            logger.debug(
                "学生 %s 在 %s 数据不足（valid_count < 4，Z0 闸门），不生成处方；"
                "教师端的「重新生成」对这一档不会有任何效果",
                student.student_no, as_of.isoformat(),
            )
            continue

        outcome = match_template(
            MatchInput(
                layer=Layer(label),
                dominant_bucket=snapshot["dominant_bucket"],
                body_comp_abnormal=snapshot["C"],
            ),
            templates,
        )
        if outcome.status is not MatchStatus.MATCHED:
            _skip(outcome.status.value)
            logger.warning(
                "学生 %s 在 %s 未生成处方：%s（层 %s / 主导短板 %r / 体成分异常 %s）",
                student.student_no, as_of.isoformat(), outcome.reason, label,
                snapshot["dominant_bucket"], snapshot["C"],
            )
            continue
        template = outcome.template

        previous = previous_index.get(student.id)
        hits = evaluate_triggers(
            TriggerInput(
                as_of=as_of,
                current_label=label,
                current_template_id=template.template_id,
                last_prescription=_last_prescription_of(previous),
                latest_assessment_date=_latest_assessment(
                    latest_fitness.get(student.id), latest_body.get(student.id)
                ),
                # 触发 5（教师手动请求）今天在管道侧**恒为 False**：它的写入方是 Plan 03
                # 的教师端。管道若替教师点这个按钮，就等于每天给全员重发处方。
                teacher_requested=False,
            )
        )
        if not hits:
            _skip(NO_TRIGGER)
            continue

        profile = _profile_of(student, snapshot, as_of)
        # ⚠️ 异常分层的第 1 档（见模块 docstring）：这两个纯函数能抛的只有「这一个学生的
        #    输入有问题」，捕获它、留痕、继续下一个人。**DB 读写在 try 之外**，故基础设施
        #    异常照样冒泡到 run_daily 的 SAVEPOINT。
        try:
            package = assemble(profile, template, as_of, exercises=exercises)
            safety = apply_safety(
                package,
                SafetyInput(
                    bmi=profile.bmi,
                    muscle_mass_kg=profile.muscle_mass_kg,
                    muscle_p10=profile.muscle_p10,
                    body_fat_abnormal=snapshot["C"],
                ),
                equivalence,
                template=template,
                exercises=exercises,
            )
        except Exception as exc:  # noqa: BLE001 - 按学生捕获，见模块 docstring「异常分层」
            skipped += 1
            needs_review += 1
            reasons_count[ASSEMBLY_ERROR] = reasons_count.get(ASSEMBLY_ERROR, 0) + 1
            logger.warning(
                "学生 %s 在 %s 的处方装配失败（模板 %s）：%s: %s —— 不生成处方、"
                "计入 needs_review，整批不回滚；这一档要人工过目",
                student.student_no, as_of.isoformat(), template.template_id,
                type(exc).__name__, exc,
            )
            continue

        if previous is not None and previous.generated_on < as_of:
            # 换处方：上一张置 replaced。⚠️ **不改写它的 valid_to**——理由逐字写在
            # Prescription 那一列的注释里（valid_to 必须能从 generated_on +
            # microcycle_weeks 离线复算，spec §4.3；而 Plan 01 的
            # stratification_result.valid_to 恒 NULL 也是同一条纪律：跨批改写上一批的行
            # 会破坏「同一业务日期重跑只动本批」这条幂等边界）。
            # 「哪一张现在生效」由 status 唯一确定，不靠日期区间。
            previous.status = REPLACED

        for warning in safety.warnings:
            # spec §7.4 / Review Focus 第 5 条：安全规则命中却找不到等价动作时「写 warning
            # 日志」，不得静默跳过。warnings 的内容由 domain 产出、顺序确定（先 addon、
            # 后「找不到替身」），本模块只负责把它们说出来。
            logger.warning(
                "学生 %s 的处方（模板 %s）需要人工复核：%s",
                student.student_no, template.template_id, warning,
            )

        status = active_or_needs_review(safety.needs_review)
        repo.upsert(
            session,
            Prescription,
            ("student_id", "generated_on"),
            {
                "student_id": student.id,
                "generated_on": as_of,
                "batch_id": batch_id,
                # ⚠️ DB 列叫 template_ref、domain 字段叫 template_id（P6-A7，同一串字符）
                "template_ref": template.template_id,
                # Task 6 传导的第 1 件事（P6-A3）：漏填会让 valid_to 无从复算，
                # 而触发 3 的判据也读它。
                "microcycle_weeks": template.microcycle_weeks,
                # fix round 1 的 F1-1：触发 2 判据的唯一输入。来源就是**当天刚写好的**
                # stratification_result.label —— 它就在本循环手上的 result 里，
                # 不需要任何额外查询。
                "label_at_generation": label,
                "training_package": training_package_payload(safety.package),
                "assembly_snapshot": dict(safety.package.assembly_snapshot),
                "safety_substitutions": [
                    {
                        "week": item.week,
                        "day": item.day,
                        "original_ref": item.original_ref,
                        "substitute_ref": item.substitute_ref,
                        "trigger": item.trigger,
                        "equivalence_version": item.equivalence_version,
                    }
                    for item in safety.substitutions
                ],
                # 新生成的处方一律没有教师覆盖（spec §7.5：重生成回到算法基线、不继承覆盖）
                "teacher_overrides": [],
                # Task 6 传导的第 2 件事（P6-A2）：这是「界面提示『该生上次存在人工覆盖』」
                # 的**唯一载体**，不是 assembly_snapshot 里的键（往快照加键会让 Task 5
                # 钉死的 12 键 / +3 键两条守卫变红）。首次生成没有「上一张」→ False。
                "previous_had_overrides": bool(
                    previous is not None and previous.teacher_overrides
                ),
                "status": status,
                "valid_from": as_of,
                "valid_to": valid_to_of(as_of, template.microcycle_weeks),
                "trigger_reasons": [reason.value for reason in hits],
            },
        )
        generated += 1
        if safety.needs_review:
            needs_review += 1

    session.flush()
    report = PrescriptionReport(
        generated=generated,
        skipped=skipped,
        needs_review=needs_review,
        skipped_reasons=reasons_count,
    )
    if INSUFFICIENT_DATA in reasons_count:
        # 每批一条、不是每人一条：噪声取舍见模块 docstring 的「日志的分档」。
        # 逐人可查的载体是 stratification_result.label（那一行本来就为 Z0 而存在）。
        logger.warning(
            "学期 %s 批次 %s（%s）：%d 名学生因数据不足（valid_count < 4，Z0 闸门）"
            "没有处方，教师端的「重新生成」对他们不会有任何效果；逐人清单查 "
            "stratification_result.label = %r",
            semester_id, batch_id, as_of.isoformat(),
            reasons_count[INSUFFICIENT_DATA], INSUFFICIENT_DATA,
        )
    logger.info(
        "学期 %s 批次 %s（%s）处方阶段：生成 %d 张、跳过 %d 人、需人工复核 %d 人；"
        "跳过原因 %s",
        semester_id, batch_id, as_of.isoformat(),
        report.generated, report.skipped, report.needs_review,
        dict(sorted(reasons_count.items())),
    )
    return report

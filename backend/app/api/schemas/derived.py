"""spec §4.3 派生与分层的 3 个资源：**全部只读**，故本模块只有 ``Read`` 三件。

| 资源路径                        | 表                       | ``writable`` | ``on_delete`` |
| =============================== | ======================== | ============ | ============= |
| ``/api/percentile-snapshots``    | ``percentile_snapshot``   | ❌           | ``forbid``    |
| ``/api/derived-metrics``         | ``derived_metrics``       | ❌           | ``forbid``    |
| ``/api/stratification-results``  | ``stratification_result`` | ❌           | ``forbid``    |

**为什么三个都只读 + ``forbid``**（计划 Task 3 的显式决定，逐字理由是「批处理产物」）：
它们由 :mod:`app.pipeline.daily` 按业务日期整批算出，删/改它们的正确方式是**重放**
（:func:`app.pipeline.daily._replay_cleanup` 按 ``batch_id`` 删，顺序承重，P7-A4），
而不是从 API 单点删。开放写入还有第二个后果：``stratification_result`` 是
spec §4.3「可追溯性」的核心——教师改一行 ``label``，那条行就无法再离线复算了。

⚠️ **``writable=False`` 意味着 ``CrudSchemas`` 的 ``create`` 与 ``update`` 都是 ``None``**，
POST / PATCH / DELETE 三个路由**根本不注册**（打过去是 Starlette 的 405，
不是「注册了再拒绝」）。故本模块没有 ``*Create`` / ``*Update``，
:func:`app.api.crud.build_crud_router` 在工厂体里对
「``writable=True`` 而 ``create``/``update`` 是 ``None``」这一档会当场抛 ``ValueError``。

**``JsonText`` 列**（``list_exclude`` 自动探测的对象，P3-B3）：
``derived_metrics`` 3 个（``annual_change`` / ``weaknesses`` / ``body_comp_reasons``）、
``stratification_result`` 1 个（``input_snapshot``）、``percentile_snapshot`` 0 个。
它们在 list 端点里**不出现**，在 read-one 里全部出现；
守卫是 ``tests/api/test_crud.py`` 的
:func:`~tests.api.test_crud.test_every_resource_list_omits_json_text_columns_and_read_one_includes_them`。
"""
import datetime as dt

from app.api.schemas._base import ReadModel

__all__ = [
    "DerivedMetricsRead",
    "PercentileSnapshotRead",
    "StratificationResultRead",
]


class PercentileSnapshotRead(ReadModel):
    """``percentile_snapshot`` 的 14 列。**本表没有 ``JsonText`` 列**，故 list 与 read-one
    返回的键集合相同（那一条遍历测试对它退化成一次空集比对，是有意的绿档）。
    """

    id: int
    semester_id: int
    computed_on: dt.date
    batch_id: int
    item: str
    sex: str
    age_group: str
    p10: float
    p20: float
    p25: float
    p50: float
    p75: float
    sample_size: int
    source: str


class DerivedMetricsRead(ReadModel):
    """``derived_metrics`` 的 11 列，含 3 个 ``JsonText`` 列。"""

    id: int
    student_id: int
    computed_on: dt.date
    batch_id: int
    annual_change: dict
    trend: str
    weaknesses: list
    weakness_count: int
    valid_count: int
    body_comp_abnormal: bool
    body_comp_reasons: list


class StratificationResultRead(ReadModel):
    """``stratification_result`` 的 10 列，含 1 个 ``JsonText`` 列（``input_snapshot``）。

    ⚠️ ``hit_rules`` 是**逗号分隔的规则 ID 序列**、最后一项才是命中者（Ruling 132），
    故它是 ``str`` 而不是 ``list``——本模块**不替前端拆开它**：拆开意味着
    「前缀是已评估但未命中的规则」这层语义在 API 边界上消失，而它正是回答
    「这个学生为什么不是红色层」的证据。
    """

    id: int
    student_id: int
    computed_on: dt.date
    batch_id: int
    label: str
    hit_rules: str
    input_snapshot: dict
    percentile_source: str
    valid_from: dt.date
    valid_to: dt.date | None

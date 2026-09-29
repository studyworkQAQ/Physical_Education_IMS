"""HttpLePaoAdapter：乐跑只读接口的骨架（spec §3.4）。

四个方法一律 ``raise NotImplementedError``，但**类现在就建**，并且与
:class:`~app.adapters.mock_lepao.MockLePaoAdapter` 跑同一组契约测试
（``tests/adapters/test_contract.py`` 的参数化把两个实现一起覆盖）。这样做的理由是
把「未来要动的地方」提前圈定：乐跑只读接口的字段一旦确定，改动只落在本文件，
``app/pipeline`` 与 ``app/domain`` 完全不动——它们只认 ``DataSourceAdapter`` 这个契约。

契约形状（未来实现时必须满足，与 Mock 逐条一致）：

* 每日增量同步：``since`` 是 ISO 日期串，**排他**过滤（``> since``），``None`` 表示全量。
  真实实现应把它翻译成乐跑接口的增量参数，而不是拉全量再在客户端过滤
* 四个方法一律返回惰性迭代器（分页拉取时逐页 yield），不返回攒好的 list
* 产出类型固定为 ``base.py`` 的三个数据类与 ``dict``；上游字段名与列名的映射在**本文件**
  完成，不外泄到管道
* 空值必须落成 ``None``，绝不能是 ``0`` 或 ``nan``（Ruling 21：``0`` 会经 ``score_item``
  低侧夹取拿到满分）
* ``fetch_students`` 不支持增量，``since`` 非 ``None`` 时同样返回全量（Ruling 33）；
  第一批里它只属于契约，不被任何管道阶段消费

本文件刻意**不含**任何 HTTP 客户端、重试、鉴权与超时逻辑：接口字段未定时写这些只是
猜测，而猜测出来的重试策略会在真实接口确定后变成需要拆掉的负担。``token`` 只保存在
实例上，实现时不得写进日志或异常消息。
"""
from collections.abc import Iterator

from app.adapters.base import (
    DataSourceAdapter,
    RawBodyCompRecord,
    RawFitnessRecord,
    RawSurveyRecord,
)


class HttpLePaoAdapter(DataSourceAdapter):
    """乐跑只读接口的适配器（骨架）。

    构造时不发任何请求：契约测试要在收集期就实例化它，与 Mock 一起接受同一组断言。
    """

    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url
        self.token = token

    def fetch_students(self, since: str | None) -> Iterator[dict]:
        """学生名册（不支持增量，``since`` 非 ``None`` 时同样返回全量）。"""
        raise NotImplementedError("乐跑只读接口字段未定，见本模块 docstring")

    def fetch_fitness(self, since: str | None) -> Iterator[RawFitnessRecord]:
        """体测记录，按 ``tested_on`` 排他增量拉取。"""
        raise NotImplementedError("乐跑只读接口字段未定，见本模块 docstring")

    def fetch_body_comp(self, since: str | None) -> Iterator[RawBodyCompRecord]:
        """体成分记录，按 ``measured_on`` 排他增量拉取。"""
        raise NotImplementedError("乐跑只读接口字段未定，见本模块 docstring")

    def fetch_survey(self, since: str | None) -> Iterator[RawSurveyRecord]:
        """兴趣问卷，按 ``filled_on`` 排他增量拉取。"""
        raise NotImplementedError("乐跑只读接口字段未定，见本模块 docstring")

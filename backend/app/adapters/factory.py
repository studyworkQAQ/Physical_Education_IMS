"""适配器工厂：把「用哪个数据源实现」这个决定收拢到一处。

**为什么要建它**（Plan 02 Task 1，终审 B）：基线 ``e26347f`` 上
``MockLePaoAdapter(DEFAULT_CSV_DIR)`` 被**硬编码在两处生产代码**里——
``app/pipeline/backfill.py:268`` 与 ``app/pipeline/daily.py:712``（命令::

    git grep -n "MockLePaoAdapter(DEFAULT_CSV_DIR)" -- backend/app/pipeline

）。这与 :mod:`app.adapters.http_lepao` 模块 docstring 里那句承诺直接冲突：

    「乐跑只读接口的字段一旦确定，改动只落在本文件，``app/pipeline`` 与 ``app/domain``
    完全不动——它们只认 ``DataSourceAdapter`` 这个契约。」

有两处硬编码时，换成 HTTP 实现要改**两个** CLI，而漏改一个不会报错——那条管道会安静地
继续读本地 CSV，跑出来的数字看起来完全正常。本模块是那句承诺的兑现处：**换实现只改
这一个文件的 ``_BUILDERS``，或者只改调用方传进来的 ``kind`` 字符串**。

依赖方向（spec §3.3 是 ``pipeline → adapters``）：本模块在 ``adapters`` 里，故它可以
import 两个具体实现；``app/pipeline`` 的两个 CLI 只在 ``main()`` 函数体内 import 本模块，
于是 ``import app.pipeline.daily`` 的顶层依赖图里**仍然不出现任何具体适配器**——这个性质
是 ``daily.py`` 当初写函数内导入的理由，工厂没有把它破坏掉。

:mod:`app.config` 是叶子（只 import ``pathlib``），故 ``adapters → config`` 这条边不可能
造出环。
"""
import pathlib
from collections.abc import Callable

from app.adapters.base import DataSourceAdapter
from app.adapters.http_lepao import HttpLePaoAdapter
from app.adapters.mock_lepao import MockLePaoAdapter
from app.config import DEFAULT_CSV_DIR

__all__ = ["KINDS", "build_adapter"]

#: 合法的 ``kind`` 取值。元组而不是字典的键集合：``KINDS`` 会被写进报错文本，
#: 元组让「有哪几种实现」这件事的顺序是声明序、稳定可复现。
KINDS: tuple[str, ...] = ("mock", "http")


def _build_mock(
    csv_dir: pathlib.Path | None, base_url: str | None, token: str | None
) -> DataSourceAdapter:
    """:class:`~app.adapters.mock_lepao.MockLePaoAdapter` 读本地 CSV 夹具。

    ``csv_dir`` 缺省取 :data:`app.config.DEFAULT_CSV_DIR`（``backend/data/seed/``，
    本仓里恒为空且不入库）。构造函数**不做任何 I/O**，故目录不存在时也不报错——
    四个 ``fetch_*`` 会 yield 空，那是 Mock 的既有契约，本工厂不改它。
    """
    return MockLePaoAdapter(DEFAULT_CSV_DIR if csv_dir is None else csv_dir)


def _build_http(
    csv_dir: pathlib.Path | None, base_url: str | None, token: str | None
) -> DataSourceAdapter:
    """:class:`~app.adapters.http_lepao.HttpLePaoAdapter`（骨架，四个方法一律
    ``NotImplementedError``）。

    ``base_url`` 与 ``token`` **都必填**：``HttpLePaoAdapter.__init__`` 收的是两个无缺省
    的位置参数，缺一个就是 ``TypeError``。在这里显式拒绝而不是让 ``None`` 流进构造函数，
    是因为骨架的 ``__init__`` **不发任何请求**（契约测试要在收集期就实例化它），于是
    ``build_adapter("http")`` 会「成功」返回一个把 ``base_url=None`` 存下来的对象，
    直到有人真去调 ``fetch_*`` 才炸——离真因隔了一整个调用栈。
    """
    if base_url is None or token is None:
        raise ValueError(
            f'kind="http" 需要同时给出 base_url 与 token（收到 base_url={base_url!r}, '
            f"token={'<已给出>' if token is not None else None}）；"
            f"{HttpLePaoAdapter.__name__} 的构造函数不发请求，缺参会被静默存下来、"
            f"到第一次 fetch_* 才炸"
        )
    return HttpLePaoAdapter(base_url, token)


_BUILDERS: dict[str, Callable[..., DataSourceAdapter]] = {
    "mock": _build_mock,
    "http": _build_http,
}


def build_adapter(
    kind: str = "mock",
    *,
    csv_dir: pathlib.Path | None = None,
    base_url: str | None = None,
    token: str | None = None,
) -> DataSourceAdapter:
    """按 ``kind`` 造一个 :class:`~app.adapters.base.DataSourceAdapter`。

    只读与 ``kind`` 对应的那几个参数，其余一律忽略（``kind="mock"`` 时 ``base_url`` /
    ``token`` 不看，``kind="http"`` 时 ``csv_dir`` 不看）。刻意**不**为「传了用不上的
    参数」报错：那会让调用方在两个实现之间切换时必须同时改参数表，而工厂的意义正是让
    切换只动 ``kind`` 一个词。

    ``kind`` 不在 :data:`KINDS` 里时抛 ``ValueError`` 并**列出全部合法取值**——一个拼错的
    ``kind``（``"Mock"``、``"mock_lepao"``）若退化成「用缺省的 mock」，HTTP 那条路径会
    永远走不到，而控制台上一切正常。

    ``token`` 不出现在任何报错文本里（只印「已给出 / None」）：它是凭据，
    :mod:`app.adapters.http_lepao` 的模块 docstring 明确要求它不得进日志、异常消息或
    ``repr``。
    """
    try:
        builder = _BUILDERS[kind]
    except KeyError:
        raise ValueError(
            f"未知的适配器 kind={kind!r}；合法取值是 {list(KINDS)}"
        ) from None
    return builder(csv_dir, base_url, token)

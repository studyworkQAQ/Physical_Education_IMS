"""适配器工厂 ``build_adapter``：kind 分派、参数校验、凭据不外泄。

工厂存在的理由（终审 B）：``MockLePaoAdapter(DEFAULT_CSV_DIR)`` 此前被硬编码在
``app/pipeline/backfill.py`` 与 ``app/pipeline/daily.py`` 两处 ``main()`` 里，换实现要改
两处生产代码，与 ``http_lepao.py`` 承诺的「改动只落在本文件」不符；而漏改一处**不报错**，
那条管道会安静地继续读本地 CSV。
"""
import pytest

from app.adapters.base import DataSourceAdapter
from app.adapters.factory import KINDS, build_adapter
from app.adapters.http_lepao import HttpLePaoAdapter
from app.adapters.mock_lepao import MockLePaoAdapter
from app.config import DEFAULT_CSV_DIR


def test_kinds_are_exactly_mock_and_http():
    """``KINDS`` 字面钉住：加一种实现是一次**有意识**的改动，不是顺手多一个分支。"""
    assert KINDS == ("mock", "http")


def test_default_kind_is_the_mock_adapter_reading_the_default_csv_dir():
    """``build_adapter()`` == 两个 CLI 此前硬编码的那一句。

    ``seed_dir`` 缺省落在 :data:`app.config.DEFAULT_CSV_DIR`（``backend/data/seed/``）。
    构造函数**不做任何 I/O**（Mock 的既有契约：目录不存在也照样构造，四个 ``fetch_*``
    yield 空），故本条不读盘、也不要求那个目录存在——它在本仓里恒为空且不入库。
    """
    adapter = build_adapter()
    assert isinstance(adapter, MockLePaoAdapter)
    assert isinstance(adapter, DataSourceAdapter), "工厂的返回类型契约"
    assert adapter.seed_dir == DEFAULT_CSV_DIR


def test_csv_dir_override_reaches_the_mock_adapter(tmp_path):
    adapter = build_adapter("mock", csv_dir=tmp_path)
    assert isinstance(adapter, MockLePaoAdapter)
    assert adapter.seed_dir == tmp_path


def test_http_kind_builds_the_skeleton_and_needs_both_credentials():
    """``kind="http"`` 造出骨架；缺 ``base_url`` 或 ``token`` 一律**响亮**拒绝。

    ``HttpLePaoAdapter.__init__`` 不发任何请求（契约测试要在收集期就实例化它），所以
    ``base_url=None`` 会被**静默存下来**、直到第一次 ``fetch_*`` 才炸——离真因隔一整个
    调用栈。工厂在这里就拦住。
    """
    adapter = build_adapter("http", base_url="https://lepao.example/api", token="tk")
    assert isinstance(adapter, HttpLePaoAdapter)
    assert adapter.base_url == "https://lepao.example/api"

    with pytest.raises(ValueError) as excinfo:
        build_adapter("http")
    message = str(excinfo.value)
    assert "base_url" in message and "token" in message

    with pytest.raises(ValueError):
        build_adapter("http", base_url="https://lepao.example/api")   # 缺 token
    with pytest.raises(ValueError):
        build_adapter("http", token="tk")                            # 缺 base_url


def test_the_token_never_appears_in_an_error_message():
    """``token`` 是凭据，不得进异常文本（``http_lepao.py`` 的模块 docstring 明确要求）。

    报错里只印「``<已给出>``」这个占位。这条断言用的是一个**不会与任何真实值撞上**的
    哨兵字符串，故它既证明「没泄露」，也证明「报错确实提到了 token 这一项」。
    """
    sentinel = "SENTINEL-TOKEN-DO-NOT-LEAK"
    with pytest.raises(ValueError) as excinfo:
        build_adapter("http", token=sentinel)          # 缺 base_url
    message = str(excinfo.value)
    assert sentinel not in message
    assert "<已给出>" in message


def test_unknown_kind_names_the_legal_values():
    """拼错的 ``kind`` 不得退化成「用缺省的 mock」。

    退化的后果是 HTTP 那条路径永远走不到，而控制台上一切正常——正是工厂要消灭的那类
    静默失效。报错里列出全部合法取值，改的人才知道该写什么。
    """
    with pytest.raises(ValueError) as excinfo:
        build_adapter("Mock")            # 大小写不对
    message = str(excinfo.value)
    assert "'Mock'" in message
    for kind in KINDS:
        assert kind in message

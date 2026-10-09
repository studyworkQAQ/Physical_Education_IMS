"""``tests/api/`` 的公共夹具：一个跑在**内存库**上的 ``TestClient``。

**为什么一律用内存库**（Plan 03 Task 1 的决定）：``backend/pe.db`` 是本仓的禁区
（Global Constraints；``tests/test_config.py`` 的模块 docstring 交代了它的语义——
「``app.seed.generate`` 写出来的那份不可复现的库」）。HTTP 层的测试**没有任何理由**
碰磁盘：它们要的是「一个建好了 18 张表的空库」，而这正是 ``sqlite://`` 给的。
手工演示要用磁盘库时走 ``backend/pe_demo.db``（``app.main.DEMO_DB_URL``，
已进 ``.gitignore``），**不是** ``pe.db``。

**为什么夹具放在 ``tests/api/`` 而不是 ``tests/conftest.py``**：本仓的 ``tests/`` 下
今天**没有**根 conftest（实测：``tests/`` 下 0 个 ``__init__.py``、0 个 ``conftest.py``），
而 ``pyproject.toml`` 的 ``[tool.pytest.ini_options]`` 只有 ``testpaths`` 与 ``pythonpath``
两项。新建一个根 conftest 会让**全部** 31 个既有测试文件都多一个导入期依赖
（``app.main`` → ``fastapi``），而只有 ``tests/api/`` 与 ``tests/test_main.py`` 用得上它。
故这里只管 ``tests/api/``；``tests/test_main.py`` 自带一份同形状的本地夹具
（**两份刻意不合并**：合并的唯一办法是建根 conftest，代价大于重复 6 行）。

**``StaticPool`` 是承重的**：SQLite 的 ``sqlite://`` 是「**每条连接一个独立的库**」，
默认的 ``QueuePool`` 会让 ``init_db`` 建表用的连接与请求里 ``get_db`` 拿到的连接
落在两个不同的内存库上（表现为 ``no such table: student``）。``app.main._build_engine``
在识别到内存 SQLite 时换成 ``StaticPool``，全进程复用同一条连接。

⚠️ 由此推出一条使用纪律：**不要把一个开着事务的 ``Session`` 跨请求留着**——
StaticPool 下它与请求里的 ``Session`` 抢的是同一条 DBAPI 连接。要造数据请用
``with Session(engine) as s: … s.commit()`` 的形状（用完即关），见
``tests/api/test_scope.py`` 的 ``_add_student``。
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from app.db.session import init_db
from app.main import create_app


@pytest.fixture()
def app():
    """一个**独立**的应用实例：每个测试拿到的是自己的空内存库，测试之间不串。

    ⚠️ 建表不在这里做：``create_app`` 只造引擎（惰性，不连接），建表由 lifespan
    或下面的 ``engine`` 夹具触发。这样「造应用」与「碰数据库」是两步，
    ``tests/test_main.py`` 里那条「工厂不得打开缺省库」的断言才有意义。
    """
    return create_app(db_url="sqlite://")


@pytest.fixture()
def engine(app) -> Engine:
    """**建好 18 张表**的引擎。要造数据就用它开 ``Session``。"""
    init_db(app.state.engine)
    return app.state.engine


@pytest.fixture()
def client(app, engine) -> TestClient:
    """``TestClient``。``raise_server_exceptions`` 保持缺省的 ``True``：

    端点里真出了未处理的异常时，测试要**看到那个异常的堆栈**，而不是一个统一的
    500 响应体——后者会把「代码有 bug」伪装成「代码按设计返回了 500」。
    要验 500 映射本身，请像 ``tests/test_main.py`` 那样单独建一个
    ``TestClient(app, raise_server_exceptions=False)``。
    """
    with TestClient(app) as test_client:
        yield test_client

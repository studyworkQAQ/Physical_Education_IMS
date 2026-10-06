"""进程级路径与 URL 缺省值的**唯一所有者**。

本模块是全仓依赖图的一个**叶子**：它只 import :mod:`pathlib`，不 import ``app`` 里的
任何东西，因此任何一层（``adapters`` / ``db`` / ``pipeline`` / ``seed`` / ``refdata``）
都可以安全地 import 它而不可能造出环。spec §3.3 的依赖方向图里没有它的位置，因为它
不是一个层——它是「这个项目在磁盘上长什么样」这一件事的住址。

**为什么要建这个模块**（Plan 02 Task 1，终审 C 组）：这三个值原先住在
``app/seed/generate.py``，于是生产层为了拿一个**路径常量**必须 import 仿真数据生成器。
基线 ``e26347f`` 上 ``git grep -n "from app.seed" -- backend/app/pipeline`` 报出的
4 处 offender 里有 3 处（``daily.py:689``、``backfill.py:234`` 各一处、
``run_stratify.py:49`` 一处）就是为了 ``DEFAULT_CSV_DIR`` / ``DEFAULT_DB_URL``。
把常量搬到这里之后，``app/pipeline`` 与 ``app/seed`` 之间不再有边，
:mod:`tests.architecture.test_layering` 的依赖方向守卫因此转绿。

**``DEFAULT_DB_URL`` 是绝对路径，不是 ``sqlite:///pe.db``**：后者是 CWD 相对路径，
从仓库根跑与从 ``backend/`` 跑会指向**两个不同的文件**，而两个文件都不会报错——
只是其中一个永远是空的（Plan01 Ruling 190 要消除的正是这个形状）。
``app/db/session.py`` 的 :func:`~app.db.session.engine` 也因此**不再带缺省 URL**：
一个函数签名里的 ``"sqlite:///pe.db"`` 字面量是本常量的第二个所有者，而它是相对路径
的那一个。

⚠️ ``DEFAULT_DB_URL`` 指向的 ``backend/pe.db`` **不入库**（``.gitignore``），且本仓
不做迁移——schema 改动等于重建库，见 :mod:`app.db.models` 的模块 docstring。
"""
import pathlib

__all__ = ["BACKEND_DIR", "DEFAULT_CSV_DIR", "DEFAULT_DB_URL"]

#: ``backend/`` 的绝对路径。本文件在 ``backend/app/config.py``，故 ``parent.parent``。
#: 它此前住在 ``app/seed/generate.py``（那里写作 ``pathlib.Path(__file__).resolve().parents[2]``，
#: 与本式等价：``generate.py`` 在 ``backend/app/seed/`` 下，深一层）。
BACKEND_DIR: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent

#: ``python -m app.seed.generate`` 写三类 CSV 的缺省目录，也是
#: :func:`app.adapters.factory.build_adapter` 在 ``kind="mock"`` 且没给 ``csv_dir`` 时
#: 传给 :class:`~app.adapters.mock_lepao.MockLePaoAdapter` 的那个 ``seed_dir``
#: （``app/adapters/factory.py:50``：
#: ``return MockLePaoAdapter(DEFAULT_CSV_DIR if csv_dir is None else csv_dir)``）。
#:
#: ⚠️ **这个缺省值是工厂给的、不是构造函数给的**：``app/adapters/mock_lepao.py:428`` 是
#: ``def __init__(self, seed_dir: pathlib.Path) -> None``——必填位置参数、**没有缺省值**，
#: 故 ``MockLePaoAdapter()`` 会 ``TypeError``（响亮，不静默）。要拿缺省目录请调
#: ``build_adapter()``，不要照本行字面去写构造调用。
#:
#: 该目录**不入库**（``.gitignore``），且在本仓里恒为空——生成器不许被随手跑。
DEFAULT_CSV_DIR: pathlib.Path = BACKEND_DIR / "data" / "seed"

#: 演示用磁盘库的 URL。``as_posix()`` 是承重的：Windows 上 ``str(Path)`` 给出反斜杠，
#: 而 SQLite 的 URL 语法里反斜杠不是路径分隔符，``sqlite:///C:\\…\\pe.db`` 会被当成
#: 一个名字里带反斜杠的相对文件。
DEFAULT_DB_URL: str = f"sqlite:///{(BACKEND_DIR / 'pe.db').as_posix()}"

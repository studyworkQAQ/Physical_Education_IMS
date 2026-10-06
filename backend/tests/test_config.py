"""``app.config`` 三个缺省值的**非同源**断言（硬规矩 #35）。

``tests/adapters/test_factory.py:32`` 那条 ``assert adapter.seed_dir == DEFAULT_CSV_DIR``
两侧**同源于 ``app.config``**：它证明的是「工厂把常量的值原样交给了适配器」，而**不能**
证明那个值本身对——把 ``DEFAULT_CSV_DIR`` 改成 ``BACKEND_DIR / "wrong"`` 它照样绿。
``DEFAULT_DB_URL`` 在 ``tests/`` 下此前**没有任何断言**（``git grep -n "DEFAULT_DB_URL"
-- backend/tests`` 在基线 ``ad1d190`` 上给 2 条命中，两条都是
``tests/architecture/test_layering.py:22-23`` docstring 里引的基线 offender 原文）。
本文件补上缺的那一半：期望值**字面写死在这里**。

**为什么只钉后缀与文件名就够了**：``BACKEND_DIR`` 自己错了**会**变红——
``app/refdata.py:23`` 是 ``DATA_DIR = BACKEND_DIR / "data"``，而
``tests/test_refdata.py:82-83`` 断言 ``refdata.DATA_DIR.name == "data"`` 且
``(refdata.DATA_DIR / "national_standard_2014.csv").is_file()``、``:187`` 再按
``DATA_DIR / STANDARD_FILENAME`` 取那份评分表量指纹 ``D2C8E539E2FA0029``：``BACKEND_DIR``
一错，这两条当场找不到文件。故这里真正裸奔的只剩 ``"data"/"seed"`` 这个后缀与 ``pe.db``
这个文件名。

**本文件不守什么**（硬规矩 #39）：``backend/data/seed/`` **是否存在、是否为空**不由这里管
（它不入库、本仓恒为空，那是各 Task 收工清单里的禁区检查，不是配置值的性质）；
``backend/pe.db`` **不得存在**那条也不在这里断言——它是运行期状态，且把它写进测试会让
「跑过 CLI 的机器上测试变红」这种与配置无关的失败混进来。
"""
from app.config import BACKEND_DIR, DEFAULT_CSV_DIR, DEFAULT_DB_URL


def test_default_csv_dir_and_db_url_are_pinned_by_literal_suffixes():
    """``DEFAULT_CSV_DIR`` 的后缀与 ``DEFAULT_DB_URL`` 的尾部用**字面量**钉住。"""
    assert DEFAULT_CSV_DIR.relative_to(BACKEND_DIR).as_posix() == "data/seed"
    assert DEFAULT_DB_URL.endswith("/backend/pe.db")

"""``app.db.models`` 包内共享的两件基础设施：JSON 列类型与取值域约束生成器。

拆包（Plan 02 Task 1）之前它们与 14 张表同住一个 ``models.py``。放这里而不是塞进六个
表模块里的某一个，是因为**五个**表模块都要用它们（``organisation`` / ``assessment`` /
``derived`` / ``ops``，以及 Plan 02 Task 2 起也用了它们的 ``prescription``）：塞进任何
一个都会让另外几个为了拿一个工具而 import 一个与它毫无关系的小节（例如 ``derived`` 为了
``JsonText`` 去 import ``organisation``）。

模块名带前导下划线，故它不出现在包 ``__init__`` 那份「公有导入面」基线里
（Plan02 Ruling 1 的判据是 ``sorted(n for n in dir(models) if not n.startswith("_"))``）。
"""

import json
from collections.abc import Iterable
from typing import Any

from sqlalchemy import CheckConstraint, Text
from sqlalchemy.types import TypeDecorator


def _in_domain(column: str, allowed: Iterable[str], name: str) -> CheckConstraint:
    """由类常量集合生成 SQL 层的取值域约束。

    约束文本从集合生成而不是手写第二遍：手写两遍迟早会漂移，而漂移是静默的——
    Python 侧放行的值数据库拒收，或反过来数据库放进了 Python 侧读不懂的值。
    取值按字典序排序，使 DDL 文本稳定可复现（同 seed 同 DDL）。
    """
    quoted = ", ".join("'" + v.replace("'", "''") + "'" for v in sorted(allowed))
    return CheckConstraint(f"{column} IN ({quoted})", name=name)


class JsonText(TypeDecorator):
    """把 Python 的 ``dict`` / ``list`` / 标量以 JSON 文本存进 ``TEXT`` 列。

    **为什么不直接用 SQLAlchemy 自带的 ``JSON`` 类型**：它在 SQLite 上渲染成
    ``JSON``，而 SQLite 的亲和性规则里 ``JSON`` 落到 **NUMERIC** 亲和性——凡「看起来
    像数字」的值会被就地转成原生数值存进去，不再是 JSON 文本。实测（Python 3.11.1 /
    SQLAlchemy 2.1.1 / SQLite；探针 = 建一张只有一个 ``JSON`` 列的表、写四个标量后读
    ``select id, typeof(v), v``）：``0.0`` 与 ``65.0`` **都**落 ``typeof='integer'``、
    读回来是 Python ``int`` ``0`` / ``65``（浮点被降成整型），``65.5`` 与 ``65.0000001``
    才落 ``typeof='real'``——NUMERIC 亲和性把**能无损表示成整数**的实数降成整型、其余留
    ``real``。本段此前印的是「``65.0`` 存成 ``real`` 而非文本」，那与它自己下一句的结论
    相反：真存成 ``real 65.0`` 的话读回仍是 ``65.0``，「原值 65.0 kg」就不会被记成
    「原值 65」——正是**降成整型**才造成失真。这条探针**不在测试网里、不被守卫**
    （本仓没有任何测试用 SQLAlchemy 自带的 ``JSON`` 类型），属历史实测，fix round 3 复跑。
    对 ``cleaning_log`` 这种存标量的审计列，这是实打实的失真，而审计记录的全部价值就在于
    原值不被改写。

    以 ``TEXT`` 为底层类型即绕开亲和性转换，同时保留透明 dumps/loads：调用方拿到手的
    仍是原样的 Python 对象，全库 14 个 JSON 形态的列共用这一种落法（这个「14」由
    ``tests/db/test_models.py::test_no_column_uses_builtin_sqlalchemy_json`` 的
    ``len(json_text_columns) == 14`` 钉住，加列时两处一起改；Plan 02 Task 6 之前是 9，
    ``prescription`` 一张表就带来 5 个），不必区分「这一列
    要不要自己 ``json.dumps``」——那种不对称正是会被忘掉、且忘掉后静默出错的地方。
    ``ensure_ascii=False`` 让中文原样落库，用 sqlite3 命令行直接看审计记录时可读。
    ``None`` 存 SQL ``NULL`` 而不是 ``'null'`` 文本，读回也是 ``None``。

    ``cache_ok = True`` 是必需的：缺了它 SQLAlchemy 会对每条用到该列的语句发
    ``SAWarning``（该类型无法生成缓存键），在 ``-W error`` 下直接变成失败。
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return None if value is None else json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return None if value is None else json.loads(value)

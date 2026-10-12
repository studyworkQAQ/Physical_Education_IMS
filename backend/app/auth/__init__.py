"""Plan 05A：鉴权的两个纯服务模块（密码哈希 + 服务端会话）。

**为什么是一个新的顶层包，而不是塞进 ``app/api/`` 或 ``app/db/``**：

* **不塞 ``app/api/``**：密码哈希与会话的签发/校验**不是 HTTP 的事**。
  :func:`app.auth.passwords.hash_password` 是一个纯函数（进去一个明文、出来一个自描述串），
  :func:`app.auth.sessions.issue` 只碰 ORM。把它们放进 ``api`` 会让「换个入口」
  ——CLI 给演示库绑密码（``backend/scripts/demo_bootstrap.py``，Plan 05A Task 4 的活）、
  或将来一个批量吊销会话的运维脚本——也要 import ``fastapi``。
* **不塞 ``app/db/``**：``app/db/`` 今天只有 ``session`` / ``repo`` / ``models`` 三件，
  它的口径是「表长什么样、怎么读写一行」；而「一个明文口令怎么变成一个可以比对的串」
  与「一次登录怎么变成一个可以吊销的行」是**策略**，不是存取。

**依赖方向**（⚠️ 不是散文：``tests/architecture/test_layering.py`` 的 ``SCANNED_DIRS``
自本计划起含 ``"auth"``，故下面两条都被守卫看着）：

* ``app.auth`` 可以 import ``app.db`` 与 ``app.config``
  （``sessions`` 要 ORM 与 :data:`app.config.TIMEZONE`，``passwords`` 要那个迭代次数缺省值）；
* ``app.auth`` **不得** import ``app.api``（反向依赖，与 ``db`` / ``pipeline`` / ``domain``
  同一条禁令），也**不得** import ``app.seed``。

⚠️ 而 ``api → auth`` 是许可方向，由 :data:`API_ALLOWED_PREFIXES` 里本计划新增的
``"app.auth"`` 那一项放行（理由逐字写在那份清单的注释里）。

**两个成员**：

=========================  ======================================================
模块                        职责
=========================  ======================================================
:mod:`.passwords`           PBKDF2-SHA256 的**自描述串**：``hash_password`` / ``verify_password``
:mod:`.sessions`            ``user_session`` 行的签发 / 解析（含滑动过期与当场吊销）/ 吊销，
                            以及 cookie 的参数
=========================  ======================================================

⚠️⚠️ **本包刻意不声明任何 HTTP 对象**（没有 ``APIRouter``、没有 ``Depends``、
没有 ``HTTPException``、也不 import ``starlette``）：判定失败一律**返回 ``None``**
（:func:`app.auth.sessions.resolve`）或**抛 ``ValueError``**
（:func:`app.auth.passwords.ensure_acceptable`），把「折成哪个 HTTP 码」留给
:mod:`app.api.routers.auth` 与 :mod:`app.api.deps`。于是两件事同时成立：
本包可以在没有 ``fastapi`` 的进程里被 import，而 401/403/409/422 的口径
仍然只有 :mod:`app.api.errors` 一个住址。

⚠️ **本包 ``__all__`` 刻意是空的**：两个成员都按模块引用
（``from app.auth import sessions`` / ``from app.auth.passwords import verify_password``），
与 ``app.db.models`` 对 Plan 02/03 那些表类的口径同一条（Ruling 97：
新东西按子模块引用，不往包的公有面上堆名字）。``from . import …`` 那一句是**承重的**：
它是「``app.auth.passwords`` 这个属性名可用」的来源。
"""

from . import passwords, sessions  # noqa: F401

__all__: list[str] = []

"""``app/api/routers/``：路由的汇总包。:func:`app.main.create_app` 只 include 这一个。

**为什么要这一层**：计划的 File Structure 要在本目录下建 7 个 router
（``catalog`` / ``feedback`` / ``prescription`` / ``alerts`` / ``dashboard`` /
``pipeline``，Plan 03 的 Task 3–9 各建自己的）。若 ``create_app`` 逐个 include，
那么每加一个 Task 都要改一次 :mod:`app.main`——而 ``main.py`` 是**应用装配点**，
它上面还压着 ``pe.db`` 禁区那条纪律（模块 docstring 里那段 ⚠️）。
把「有哪些 router」收进本包之后，``create_app`` 的那一句
``application.include_router(api_router)`` **永远不用改**。

⚠️ **include 的顺序是承重的**（计划 S4 那段裁定的由来）：同一个 ``POST`` 路径若被
泛型 CRUD 与某个特例端点**同时注册**，FastAPI 按 ``include_router`` 的先后取先匹配的，
于是「哪一个生效」变成一个没人看得见的耦合。本包的对策不是靠顺序，而是**让那种重叠
不存在**：23 个资源里有专门特例写入口的那些（``rpe-records`` / ``training-logs`` /
``mini-tests`` / ``prescriptions`` / ``weekly-adjustments`` / ``alerts`` /
``notifications``）一律 ``writable=False``，故泛型工厂**不注册**它们的 POST/PATCH。
⚠️ 于是 Task 5/7/8 的特例端点是那些路径上**唯一**的写入方。

**今天的成员**：:mod:`.catalog`（Task 3）与 :mod:`.prescription`（Task 4）。
Task 5/7/8/9 各自往这里加一行 import 与一行 ``include_router``，**不改** :mod:`app.main`。

⚠️ **include 的顺序今天不承重**（但仍然是「先泛型、后特例」）：Task 4 的四个路径
（``/api/students/{student_id}/prescriptions/current`` /
``/api/students/{student_id}/weekly-sheet`` /
``/api/prescriptions/{prescription_id}/overrides`` /
``/api/prescriptions/{prescription_id}/regenerate``）与 :mod:`.catalog` 那 23 个资源的
五个端点**没有一个同形**（段数不同、或末段是字面量而不是占位符），故两种顺序给出
同一套路由匹配。⚠️ 而 ``prescriptions`` 在 ``RESOURCES`` 里是 ``writable=False``，
故它的 POST/PATCH **根本不注册**——``POST /api/prescriptions/{id}/overrides``
在整仓里只有本包这一个写入方，不存在「谁先注册谁生效」的耦合。
"""
from fastapi import APIRouter

from app.api.routers.catalog import router as catalog_router
from app.api.routers.prescription import router as prescription_router

__all__ = ["api_router"]

#: 全部 ``/api/`` 路由的汇总。⚠️ **不带 ``prefix``**：
#: :data:`app.api.routers.catalog.RESOURCES` 里的 23 个路径串已经逐字含 ``/api``
#: （读写矩阵钉的就是 ``/api/course-sections`` 这个形状），
#: 在这里再加一次前缀会变成 ``/api/api/…``。
#: ⚠️ :mod:`.prescription` 的四个路径同样逐字含 ``/api``（同一个约定）。
api_router = APIRouter()
api_router.include_router(catalog_router)
api_router.include_router(prescription_router)

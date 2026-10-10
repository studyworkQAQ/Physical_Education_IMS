"""``app/api/routers/``：路由的汇总包。:func:`app.main.create_app` 只 include 这一个。

**为什么要这一层**：计划的 File Structure 要在本目录下建 7 个 router
（``catalog`` / ``feedback`` / ``prescription`` / ``alerts`` / ``dashboard`` /
``pipeline``，Plan 03 的 Task 3–9 各建自己的）。若 ``create_app`` 逐个 include，
那么每加一个 Task 都要改一次 :mod:`app.main`——而 ``main.py`` 是**应用装配点**，
它上面还压着 ``pe.db`` 禁区那条纪律（模块 docstring 里那段 ⚠️）。
把「有哪些 router」收进本包之后，``create_app`` 的那一句
``application.include_router(api_router)`` **永远不用改**。

⚠️ **include 的顺序是承重的**（计划 S4 那段裁定的由来）：同一个路径若被
泛型 CRUD 与某个特例端点**同时注册**，FastAPI 按 ``include_router`` 的先后取先匹配的，
于是「哪一个生效」变成一个没人看得见的耦合。本包的对策分两半：

* **写入侧（POST / PATCH）：让重叠不存在。** 23 个资源里有专门特例写入口的那些
  （``rpe-records`` / ``training-logs`` / ``mini-tests`` / ``prescriptions`` /
  ``weekly-adjustments`` / ``alerts`` / ``notifications``）一律 ``writable=False``，
  故泛型工厂**不注册**它们的 POST/PATCH，Task 5/7/8 的特例端点是那些路径上
  **唯一**的写入方。
* ⚠️ **读取侧（GET）：靠顺序，因为重叠消不掉。** 泛型工厂为**每个**资源都注册
  ``GET /api/<资源>/{pk}``（只读资源也有），而特例端点里总会出现
  「字面末段 + 同一个前缀」的形状——Task 5 的 ``GET /api/mini-tests/normalized``
  与 ``GET /api/mini-tests/{mini_test_id}`` 就是第一例（**两段、末段一个占位**，
  完全同形）。⚠️ 那一类重叠**没有 ``writable=False`` 那样的开关可用**
  （读端点是泛型工厂的核心产出，关掉它等于关掉整个资源的 read）。
  故对策是**把所有特例 router 一律 include 在 :mod:`.catalog` 之前**：
  字面路径先注册就先匹配，而泛型的 ``{pk}`` 仍然兜住其余全部。
  ⚠️ 顺序与守卫逐字写在下面 :data:`api_router` 的注释里。

**今天的成员**：:mod:`.feedback`（Task 5）、:mod:`.prescription`（Task 4）、
:mod:`.alerts`（Task 7 建 + Task 8 加「通知已读」）、:mod:`.dashboard`（Task 8）、
:mod:`.pipeline`（Task 9）与 :mod:`.catalog`（Task 3）——**按 include 顺序列，不是按
Task 序号**（``catalog`` 恒排最后，理由见下面 :data:`api_router` 的注释）。
⚠️ **Task 9 建出 :mod:`.pipeline` 之后，计划 File Structure 在本目录下列的 7 个文件全部
到位**（``__init__`` + 6 个 router）。⚠️ 本模块开头那句「要在本目录下建 **7 个 router**」
数的其实是**文件数**——它自己列的名字只有 6 个（``catalog`` / ``feedback`` /
``prescription`` / ``alerts`` / ``dashboard`` / ``pipeline``），第 7 个是 ``__init__`` 自己。
两个数都是真的、主语不同，按硬规矩 #56 把主语写清而不是「统一成一个数」。

⚠️ **Task 4 的四个路径与顺序无关**（本处此前写的是「include 的顺序今天不承重」，
那句话在 Task 5 之后已经不成立，按实际改写）：
``/api/students/{student_id}/prescriptions/current`` /
``/api/students/{student_id}/weekly-sheet`` /
``/api/prescriptions/{prescription_id}/overrides`` /
``/api/prescriptions/{prescription_id}/regenerate`` 与 :mod:`.catalog` 那 23 个资源的
五个端点**没有一个同形**（段数不同、或末段是字面量而**前一段**是占位符），
故两种顺序给出同一套路由匹配。⚠️ 而 ``prescriptions`` 在 ``RESOURCES`` 里是
``writable=False``，故它的 POST/PATCH **根本不注册**——
``POST /api/prescriptions/{id}/overrides`` 在整仓里只有本包这一个写入方。
"""
from fastapi import APIRouter

from app.api.routers.alerts import router as alerts_router
from app.api.routers.catalog import router as catalog_router
from app.api.routers.dashboard import router as dashboard_router
from app.api.routers.feedback import router as feedback_router
from app.api.routers.pipeline import router as pipeline_router
from app.api.routers.prescription import router as prescription_router

__all__ = ["api_router"]

#: 全部 ``/api/`` 路由的汇总。⚠️ **不带 ``prefix``**：
#: :data:`app.api.routers.catalog.RESOURCES` 里的 23 个路径串已经逐字含 ``/api``
#: （读写矩阵钉的就是 ``/api/course-sections`` 这个形状），
#: 在这里再加一次前缀会变成 ``/api/api/…``。
#: ⚠️ :mod:`.prescription` 与 :mod:`.feedback` 的路径同样逐字含 ``/api``（同一个约定）。
#:
#: ⚠️⚠️ **include 的顺序自 Plan 03 Task 5 起是承重的**（本处此前逐字写着「今天的顺序
#: 不承重」，按实际改写）：:mod:`.feedback` 的 ``GET /api/mini-tests/normalized``
#: 与泛型工厂为 ``mini-tests`` 注册的 ``GET /api/mini-tests/{mini_test_id}`` **同形**
#: （都是两段、末段一个占位），而 FastAPI 按注册先后取先匹配的。故 ``feedback``
#: **必须排在 ``catalog`` 之前**：排反了的话 ``normalized`` 会被当成 ``mini_test_id``
#: 去转 ``int``，得到 **422** 且消息是「``mini_test_id`` 不是一个整数」——
#: 那个消息会把下一个人支去修前端传的参、而不是修这里的顺序。
#: 守卫是
#: ``tests/api/test_feedback.py::test_the_normalized_route_is_not_swallowed_by_the_generic_read_route``。
#: ⚠️ 顺序对 :mod:`.prescription` 仍**不承重**（它的四个路径与 23 个资源的五个端点
#: 没有一个同形：段数不同、或末段是字面量而前一段是占位），但它**仍然排在
#: ``catalog`` 之前**：规则是「特例一律在泛型之前」，一条不需要逐个 router 去论证
#: 「它同形吗」的规则才是能执行的规则（下一个 Task 的人不必再做一次同形分析）。
api_router = APIRouter()
api_router.include_router(feedback_router)
api_router.include_router(prescription_router)
# ⚠️ Task 7 的 ``POST /api/alerts/{alert_id}/handle`` **今天与 catalog 不同形**
# （三段 vs 泛型 ``/api/alerts/{alert_id}`` 的两段，而泛型的 PATCH 也不同形），
# 故它的顺序**不承重**。但它仍然排在 ``catalog`` 之前：规则是「特例一律在泛型之前」，
# 一条不需要逐个 router 去论证「它同形吗」的规则才是能执行的规则
# （理由逐字见上面 :mod:`.prescription` 那一条的同款注释）。
# ⚠️ **加任何 ``GET /api/alerts/<字面>`` 的子路径之前必须先读这一段**：
# 那会与泛型工厂为 ``alerts`` 注册的 ``GET /api/alerts/{alert_id}`` **完全同形**
# （两段、末段一个占位），于是顺序立刻变成承重的——排反了的话那个字面段会被当成
# ``alert_id`` 去转 ``int``，得到 422 且消息是「``alert_id`` 不是一个整数」，
# 把下一个人支去修前端传的参、而不是修这里的顺序
# （:mod:`.feedback` 的 ``GET /api/mini-tests/normalized`` 就是这个形状的第一例）。
api_router.include_router(alerts_router)
# ⚠️ Task 8 的四个路径**今天与 catalog 也不同形**（实测）：
# ``/api/dashboard/class/{id}`` 与 ``/api/dashboard/weekly-class-report/{id}`` 的第一段
# ``dashboard`` 不是任何资源的路径；``/api/teacher/students/{id}/weekly-sheet`` 的第一段
# 是 ``teacher``（**单数**），而那个资源的路径是 ``/api/teachers``（复数）；
# ``/api/students/{id}/home`` 是三段、泛型的 ``/api/students/{student_id}`` 是两段。
# 故顺序对 :mod:`.dashboard` 仍**不承重**——但它仍然排在 ``catalog`` 之前，
# 理由逐字见上面 :mod:`.prescription` 那一条的同款注释（「特例一律在泛型之前」，
# 一条不需要逐个 router 去论证「它同形吗」的规则才是能执行的规则）。
# ⚠️ 同一条警告对 Task 8 加在 :mod:`.alerts` 里的那个端点也成立：
# ``POST /api/notifications/{id}/read`` 是三段，而 ``notifications`` 是
# ``writable=False``（泛型工厂**根本不注册**它的 POST/PATCH），故两者不重叠。
api_router.include_router(dashboard_router)
# ⚠️ Task 9 的 ``POST /api/pipeline/run-daily`` 的第一段是 ``pipeline``，它**不是任何资源的
# 路径**（23 个资源里没有叫 ``pipelines`` 的），故与 :mod:`.catalog` 不同形、顺序不承重。
# 但它仍然排在 ``catalog`` 之前：规则是「特例一律在泛型之前」，一条不需要逐个 router 去
# 论证「它同形吗」的规则才是能执行的规则（理由逐字见上面 :mod:`.prescription` 那一条）。
api_router.include_router(pipeline_router)
api_router.include_router(catalog_router)

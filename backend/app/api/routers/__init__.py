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

**今天的成员**：:mod:`.auth`（**Plan 05A Task 1**）、:mod:`.feedback`（Task 5）、
:mod:`.prescription`（Task 4）、:mod:`.alerts`（Task 7 建 + Task 8 加「通知已读」）、
:mod:`.dashboard`（Task 8）、:mod:`.pipeline`（Task 9）与 :mod:`.catalog`（Task 3）
——**按 include 顺序列，不是按 Task 序号**（``catalog`` 恒排最后，理由见下面
:data:`api_router` 的注释）。
⚠️ **Task 9 建出 :mod:`.pipeline` 之后，计划 File Structure 在本目录下列的 7 个文件全部
到位**（``__init__`` + 6 个 router）；**Plan 05A Task 1 又建了第 7 个 router
（:mod:`.auth`），故本目录今天是 ``__init__`` + 7 个 router = 8 个 ``.py``**。
⚠️ 本模块开头那句「要在本目录下建 **7 个 router**」
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
from app.api.routers.auth import router as auth_router
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
#: ``tests/api/test_feedback.py::test_the_normalized_route_is_not_swallowed_by_the_generic_read_route``
#: （点状：只钉 ``normalized`` 那一条）与
#: ``…::test_every_literal_tailed_special_route_beats_the_generic_placeholder_route``
#: （清单式：把**全部**末段为字面量的特例路径枚举一遍，今天 3 个）。
#:
#: ⚠️⚠️⚠️ **写路由顺序守卫之前必读：不要用 ``app.routes``**（Plan 03 全分支终审把这句
#: 警告从两个测试的 docstring 里搬到**这里**，理由是本文件才是「特例一律在 ``catalog``
#: 之前 include」这条纪律的住址，而下一个人要写守卫时会先读这里）。
#: 在 **FastAPI 0.141.1 / Starlette 1.7.0** 上 ``include_router`` 是**惰性的**：
#: 它把整个子 router 折叠成**一个** ``_IncludedRouter`` 节点，故 ``len(app.routes)``
#: 实测只有 **6**（4 个内置的 ``/openapi.json`` / ``/docs`` 一类 + ``/api/health`` +
#: 那一个折叠节点），「遍历 ``app.routes`` 找 ``/api/`` 前缀」在这个版本上**只能看见
#: ``/api/health`` 一条**。
#: ⚠️ 终审专门实测过这件事的后果：按 ``app.routes`` 写的路由遮蔽扫描是**假绿**的——
#: 它在今天正确的顺序上报「0 对遮蔽」，在一个把顺序**排反**的最小 app 上**也**报
#: 「0 对遮蔽」。一条两种情况都报同一个数的守卫，等于没有守卫。
#:
#: **可用的口径有两个**（硬规矩 #103：一个探针里有两种口径时，以能拿到全貌的那一种为准，
#: 另一种标注为不可用）：
#:
#: 1. **``app.openapi()["paths"]``** —— 首选。它是完整的（实测 63 个 ``/api/`` 路径模板、
#:    91 个操作），且与前端拿到的那份 spec 同源。⚠️ 它答的是「注册了什么」，
#:    **答不了「谁先匹配」**（OpenAPI 的 paths 是一个映射、没有顺序），
#:    故「遮蔽」这件事仍然要靠**实发一次请求**看落到哪个端点上。
#: 2. **递归展开 ``_IncludedRouter.original_router.routes``** —— 能拿到真的
#:    ``APIRoute`` 对象（含 ``path`` / ``methods`` / ``endpoint``），且**保序**，
#:    于是「谁先匹配」可以离线推。⚠️ 它是**私有类型**（名字前缀有下划线），
#:    换 FastAPI 版本可能就不在了，故用它写的守卫必须先断言
#:    「展开出来的路由数 > ``len(app.routes)``」，否则它会静默退化成上面那个假绿。
#:
#: ⚠️ 于是本仓的既定形状是「**实发请求**」：造一个会被遮蔽的输入
#: （``GET /api/mini-tests/normalized``），断言响应**不是** 422——被泛型的
#: ``GET /api/mini-tests/{mini_test_id}`` 吃掉的话，``normalized`` 会被当成
#: ``mini_test_id`` 去转 ``int``，得到 422 且消息是「``mini_test_id`` 不是一个整数」。
#: ⚠️ 那个 422 尤其阴险：它会把下一个人支去修**前端传的参**、而不是修这里的顺序。
#: ⚠️ 同一条纪律也适用于「哪些端点挂了 ``security``」一类的扫描
#: （见 ``tests/api/test_crud.py::test_every_writable_resource_rejects_an_anonymous_mutation``
#: 的 docstring 第二节，那里逐字记了同一个假绿）。
#: ⚠️ 顺序对 :mod:`.prescription` 仍**不承重**（它的四个路径与 23 个资源的五个端点
#: 没有一个同形：段数不同、或末段是字面量而前一段是占位），但它**仍然排在
#: ``catalog`` 之前**：规则是「特例一律在泛型之前」，一条不需要逐个 router 去论证
#: 「它同形吗」的规则才是能执行的规则（下一个 Task 的人不必再做一次同形分析）。
api_router = APIRouter()
# ⚠️ **Plan 05A Task 1 的 :mod:`.auth` 排在最前**（它是本包第七个成员）。
# 它的五个路径第一段是 ``auth``，而 23 个资源里**没有**叫 ``auths`` 的
# （``/api/auth/students/bind`` 与泛型的 ``/api/students/{student_id}`` 段数与前缀都不同），
# 故顺序对它**不承重**——但它仍然排在最前：规则是「特例一律在泛型之前」，
# 一条不需要逐个 router 去论证「它同形吗」的规则才是能执行的规则
# （理由逐字见下面 :mod:`.prescription` 那一条的同款注释）。
# ⚠️ 而它排在最前还有一层**非顺序**的理由：它是全部其他端点的**前置**
# （生产档下没有 cookie 就一律 401），故 ``/docs`` 上把它排在第一组最符合读的动线。
api_router.include_router(auth_router)
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

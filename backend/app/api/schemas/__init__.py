"""``app/api/schemas/``：23 个资源的 Pydantic 模型，按 spec §4 的小节分模块。

**布局**（与 :mod:`app.db.models` 的分节一一对应，故「一个资源的表与它的 schema」
在两个包里同名同界）：

===========================  =============================================  =====
模块                          资源                                            只读
===========================  =============================================  =====
:mod:`._base`                 ``ReadModel`` / ``one_of``（**共享基础设施**）    —
:mod:`.organisation`          ``semester`` / ``teacher`` / ``student`` /        0
                              ``course_section`` / ``enrollment``
:mod:`.assessment`            ``fitness_test_batch`` / ``fitness_test_result`` / 1
                              ``body_composition`` / ``interest_survey``
:mod:`.derived`               ``percentile_snapshot`` / ``derived_metrics`` /    3
                              ``stratification_result``
:mod:`.prescription`          ``exercise`` / ``prescription_template`` /         4
                              ``prescription`` / ``weekly_adjustment``
:mod:`.feedback`              ``class_session`` / ``rpe_record`` /               3
                              ``training_log`` / ``mini_test``
:mod:`.alerts`                ``alert`` / ``notification`` /                     3
                              ``weekly_class_report``
===========================  =============================================  =====

合计 **23** 个资源、**14** 个只读（只出 ``*Read``）、**9** 个可写（出三件套），
故模型数是 14 + 9 × 3 = **41** 个。守卫是
``tests/api/test_crud.py::test_the_read_write_matrix_counts_are_pinned``
（它数的是 :data:`app.api.routers.catalog.RESOURCES`，不是本包的类）。

⚠️ **``alert`` / ``notification`` / ``weekly_class_report`` 的 schema 住在
:mod:`.alerts`、而它们的表住在 :mod:`app.db.models.feedback`**——这不是漂移，
是照计划 File Structure 的两行清单落的（``schemas/feedback.py`` 四张、
``schemas/alerts.py`` 三张）。⚠️ 而 ``app/db/models/`` 那侧刻意**反过来**
（三张表住在 ``feedback.py``、不住 ``ops.py``），理由是导入机制而不是文档结构
（Plan 03 账本 P3-A1）：``models/__init__.py`` 对 ``ops`` 是星号导入、对 ``feedback``
不是，搬过去会撞 ``_MODELS_PUBLIC_BASELINE`` 那条守卫。
**本包没有那条约束**（``schemas/__init__.py`` 不星号导入子模块、也没有公开面基线），
故按计划的分节走即可。

⚠️ **本包刻意不做**「从 SQLAlchemy 元数据自动生成模型」：那样能省掉 41 个类，
但代价是 OpenAPI 里的字段名与类型都成了推出来的东西——Plan 04 的前端要照着
``/openapi.json`` 写 23 个表单，而一份「按 ``VARCHAR(n)`` 推出来的 ``str``」
既给不出中文标签、也给不出取值域。手写的 41 个类是那个界面的契约。
"""
from app.api.schemas._base import ReadModel, one_of

__all__ = ["ReadModel", "one_of"]

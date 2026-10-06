"""spec §4.4 处方数据模型（**本模块今天刻意是空的**）。

Plan 02 Task 1 建了这个模块但**没有往里放任何表**，因为处方的四张表分属后续任务：

* ``prescription`` / ``prescription_template`` / ``training_package`` 由 **Task 2/3** 建
  （模板与动作库先落地，处方表要引用它们）；
* ``prescription_override``（教师覆盖）与 ``prescription`` 的触发/幂等列由 **Task 9** 建。

留空而不是先建一个空类占位（Plan02 Ruling 5）：一个没有列的 ORM 类会被
``Base.metadata.create_all`` 建成一张**零列以外的空表**，而
``tests/db/test_models.py::test_all_fourteen_tables_created`` 用 ``==`` 钉住了表集合
（Plan01 Ruling 28：用 ``==`` 而不是 ``>=``，正是为了抓「有人提前把计划 02 的表建进来」）。
先建空类等于自己弄红那道守卫，而它红得毫无信息量。

⚠️ 建表时请同时更新那道守卫的 ``expected`` 集合与它的「14 张」措辞。
"""

# -*- coding: utf-8 -*-
"""fr3 edit engine (byte-exact, EOL-preserving, with double-direction verification).

usage: python v09_edit.py <group> [--dry]
group: py | yaml | spec
"""
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
CRLF = bytes([13, 10])


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16].upper()


def norm_fp(b):
    return hashlib.sha256(b.replace(CRLF, b"\n")).hexdigest()[:16].upper()


class File:
    def __init__(self, rel):
        self.path = ROOT / rel
        self.raw = self.path.read_bytes()
        self.n_crlf = self.raw.count(CRLF)
        self.n_lf = self.raw.count(b"\n")
        if self.n_crlf == 0:
            self.eol = "\n"
        elif self.n_crlf == self.n_lf:
            self.eol = "\r\n"
        else:
            raise SystemExit(f"REFUSE: {rel} has MIXED line endings "
                             f"(CRLF {self.n_crlf} / LF {self.n_lf})")
        self.text = self.raw.decode("utf-8").replace("\r\n", "\n")
        self.orig_text = self.text

    def sub(self, tag, old, new, expect=1):
        n = self.text.count(old)
        if n != expect:
            raise SystemExit(f"FAIL[{tag}] {self.path.name}: expected {expect} hit(s) of OLD, "
                             f"got {n}")
        # control: prove the search mechanism itself works
        probe = old[:40]
        if self.text.count(probe) < 1:
            raise SystemExit(f"FAIL[{tag}] search mechanism invalid (probe 0 hits)")
        self.text = self.text.replace(old, new)
        after_old = self.text.count(old)
        after_new = self.text.count(new)
        if after_old != 0 or after_new < expect:
            raise SystemExit(f"FAIL[{tag}] after replace: old={after_old} new={after_new}")
        print(f"  OK [{tag}] old_hits {n}->{after_old} ; new_hits ->{after_new}")

    def write(self, dry):
        out = self.text.replace("\n", self.eol).encode("utf-8")
        eolname = "CRLF" if self.eol == "\r\n" else "LF"
        if dry:
            print(f"  DRY {self.path.name}: {len(self.raw)} -> {len(out)} B ; "
                  f"normfp {norm_fp(self.raw)} -> {norm_fp(out)} ; eol={eolname}")
            return out
        self.path.write_bytes(out)
        chk = self.path.read_bytes()
        if chk != out:
            raise SystemExit(f"FAIL write-verify {self.path}")
        n_crlf = chk.count(CRLF)
        n_lf = chk.count(bytes([10]))
        print(f"  WROTE {self.path.name}: {len(self.raw)} -> {len(chk)} B ; "
              f"CRLF {n_crlf} / LF {n_lf} ; "
              f"normfp {norm_fp(self.raw)} -> {norm_fp(chk)} ; rawsha {sha(self.raw)} -> {sha(chk)}")
        return chk


# ---------------------------------------------------------------------------
# GROUP py : backend/app/** (docstring/comment only) + backend/tests/**
# ---------------------------------------------------------------------------
def group_py(dry):
    files = {}

    # ---------------- exercises.py ----------------
    f = File("backend/app/domain/prescription/exercises.py")
    files[f.path] = f

    f.sub("I1/exercises.py", """    上处处写 ``.value``。漏写一处的失效形态是**静默的**：SQLite 会把枚举对象按 ``str()``
    存成 ``"ImpactLevel.HIGH"``（19 字符，还撑破 ``String(8)``——SQLite 不强制长度，故
    写侧不报错，换严格长度的后端才截断，硬规矩 #18 的那个失效形态）。
""", """    上处处写 ``.value``。

    ⚠️ **「漏写 ``.value`` 会静默存成 ``"ImpactLevel.HIGH"`` 并撑破 ``String(8)``」不是本仓
    的失效形态**（fix round 3 实测更正：此前这里印的机制与字符数都不成立）。实测环境
    Python 3.11.1 / SQLAlchemy 2.1.3，用标准库 ``sqlite3`` 与
    ``sqlalchemy.dialects.sqlite``：

    * ``ImpactLevel`` 是 ``str`` 子类，**它自己的字符数据就是 ``"high"``**，而 DBAPI 绑定
      传下去的是字符数据、不是 ``str()`` 的返回值。``CREATE TABLE t (lv VARCHAR(8))`` 后
      绑定 ``ImpactLevel.HIGH``，读回是 ``'high'``（``typeof=text``、SQLite ``length()=4``）
      ——**既没撑破 ``String(8)``、也不会在严格长度的后端被截断**。
    * ``String(8).bind_processor(sqlite 方言)`` 实测返回 ``None``：值原样下传、不做 ``str()``
      强转，故 ORM 路径与裸 ``sqlite3`` 同结果。
    * 只有**显式**写 ``str(x)`` 才得到 ``'ImpactLevel.HIGH'``，那是 **16** 字符
      （``ImpactLevel`` 11 + ``.`` 1 + ``HIGH`` 4）；``repr()`` 是 26、``format()`` 是 16，
      **没有任何一种口径给得出 19**。
    * 且生产路径根本不会把枚举交给 ORM：``app/refdata_prescription.py`` 的
      ``sync_exercises`` 写的是 ``spec.impact_level.value``
      （``git grep -n "impact_level.value" -- backend/app`` 的唯一命中）。

    故硬规矩 #18 那个「列宽容不下最长值、宽松后端不报错、换严格后端才截断」的失效形态在
    **这一列**上今天**不可达**；这一列的列宽仍由
    ``test_exercise_string_column_widths_fit_the_yaml_values`` 从 YAML 现读现比看着。
""")

    f.sub("I2+M7/exercises.py ImpactLevel docstring", """    无关。冲击序由消费方显式声明，今天有两份、刻意不同源（硬规矩 #35）：生产侧是
    **本模块**的 :data:`IMPACT_RANK`（Ruling 96 之前它叫 ``_IMPACT_RANK``、住在
    :mod:`app.refdata_prescription`），测试侧
    ``tests/test_refdata_prescription.py`` 的 ``IMPACT_DESCENDING``。改坏任何一份都会让
    ``test_equivalence_never_maps_to_a_higher_impact_level`` 变红。
""", """    无关。冲击序由消费方显式声明，今天是**两个消费方各一份**、刻意不同源（硬规矩 #35）：
    生产侧是**本模块**的 :data:`IMPACT_RANK`（Ruling 96 之前它叫 ``_IMPACT_RANK``、住在
    :mod:`app.refdata_prescription`），测试侧是
    ``tests/test_refdata_prescription.py`` 的 ``IMPACT_DESCENDING``。此外 fix round 2 又在
    ``test_impact_rank_values_are_pinned_verbatim`` 里字面写死了第三处**期望值**
    （``{HIGH: 0, MEDIUM: 1, LOW: 2}``）——它是「钉住生产侧那一份」的判据，不是又一个声明者。

    ⚠️ **改坏哪一份、红的是哪几条，两侧不同**（fix round 3 实测更正；此前这里印的
    「改坏任何一份都会让 ``test_equivalence_never_maps_to_a_higher_impact_level`` 变红」
    **对生产侧那一份不成立**，且与下面 :data:`IMPACT_RANK` 自己的注释自相矛盾）。两次变异
    都在 ``2df6825`` 的干净工作树上**串行**实跑，各得 ``2 failed, 529 passed``：

    * 改坏**生产侧** :data:`IMPACT_RANK`（``HIGH: 0 ↔ LOW: 2`` 对调）→
      ``test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable`` 与
      ``test_impact_rank_values_are_pinned_verbatim``（支 1）红；
      **``test_equivalence_never_maps_to_a_higher_impact_level`` 保持绿**——AST 实测
      ``IMPACT_RANK`` 在它函数体里 **0 命中**，它的秩取自
      ``rank = {value: index for index, value in enumerate(IMPACT_DESCENDING)}``。
    * 改坏**测试侧** ``IMPACT_DESCENDING``（反序成 ``("low", "medium", "high")``）→
      ``test_equivalence_never_maps_to_a_higher_impact_level``（10 条映射全部被判「升了冲击」）
      与 ``test_impact_rank_values_are_pinned_verbatim``（支 2）红。
""")

    f.sub("I5/exercises.py TARGET_DOMAIN", """#: 含 ``None``（``ITEM_BUCKET[ScoredItem.BMI] is None``，因为 BMI 天然不属于任何短板桶，
#: Plan01 Ruling 19 的口径），照字面写会把 ``None`` 放进取值域、并让一个空 ``targets``
#: 悄悄合法。由 ``tests/test_refdata_prescription.py`` 的
#: ``test_target_domain_is_the_three_bucket_names_not_the_raw_values`` 钉住这个构造方式。
""", """#: 含 ``None``（``ITEM_BUCKET[ScoredItem.BMI] is None``，因为 BMI 天然不属于任何短板桶），
#: 照字面写会把 ``None`` 放进取值域、并让一个空 ``targets`` 悄悄合法。由
#: ``tests/test_refdata_prescription.py`` 的
#: ``test_target_domain_is_the_three_bucket_names_not_the_raw_values`` 钉住这个构造方式。
#:
#: **「BMI 不归任何短板桶」的出处**（fix round 3 更正：此前这里引的「Plan01 Ruling 19」是
#: **错的引用号**——Plan01 账本的 Ruling 19 讲的是「``raw_from_score`` 对非单调序列抛
#: ``ValueError``，不得返回哨兵」，是反查函数的护栏，与桶归属无关；错误源头是 Plan02 账本
#: P2-A4，账本由控制者勘误）。真正的出处是 **spec §4.2**：那张「8 项原始测量」的表里 BMI
#: 一行的「短板判定项」格是 **否**、备注格逐字是「不入桶」，同节的说明也逐字写着
#: 「**短板判定项 = 6 个**（**排除 BMI**）」，排除理由是「BMI 属身体形态，已由体成分维度
#: ``C`` 覆盖；若同时计入 ``W`` 与 ``C``，一个体脂超标学生会被**重复计数**」。Plan01 账本
#: Ruling 17 的关切 1 据此裁定：「BMI 按 spec §4.2 **不参与短板判定与桶化**，只进国标总分」。
""")

    f.sub("M10/exercises.py lookup 折行", """        故专家可以通过调整书写顺序来
        表达偏好，而不必引入一个额外的优先级字段。
""", """        故专家可以通过调整书写顺序来表达偏好，不必引入一个额外的优先级字段。
""")

    f.sub("I2/exercises.py IMPACT_RANK 注释（把正确版补全）", """#: （硬规矩 #35）：改坏任何一份，``test_equivalence_never_maps_to_a_higher_impact_level``
#: 与 :func:`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable`
#: 之一会红。
""", """#: （硬规矩 #35）。**改坏哪一份、红的是哪几条，两侧不同**（fix round 3 实测，与上面
#: :class:`ImpactLevel` docstring 同一口径；两次变异都在 ``2df6825`` 的干净工作树上串行
#: 实跑，各 ``2 failed, 529 passed``）：
#:
#: * 改坏**本字典**（``HIGH: 0 ↔ LOW: 2`` 对调）→
#:   :func:`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable` 与
#:   ``test_impact_rank_values_are_pinned_verbatim``（支 1）红，而
#:   ``test_equivalence_never_maps_to_a_higher_impact_level`` **不红**（它只读测试侧那份）。
#: * 改坏**测试侧** ``IMPACT_DESCENDING``（反序）→
#:   ``test_equivalence_never_maps_to_a_higher_impact_level`` 与
#:   ``test_impact_rank_values_are_pinned_verbatim``（支 2）红，而上面那条 ``lookup`` **不红**。
""")

    # ---------------- test_prescription_templates.py ----------------
    f = File("backend/tests/domain/test_prescription_templates.py")
    files[f.path] = f
    f.sub("I1/test_prescription_templates.py", """    不继承 ``str`` 的话，ORM 侧就得处处写 ``.value``，而漏写一处的失效形态是**静默的**：
    SQLite 会把枚举对象按 ``str()`` 存成 ``"ImpactLevel.HIGH"``（19 字符，还会撑破
    ``String(8)``——SQLite 不强制长度，故写侧不报错，换严格长度的后端才截断，
    硬规矩 #18 的那个失效形态）。继承 ``str`` 之后 ``ImpactLevel.HIGH == "high"``
    直接成立，落库与读回都是同一个字符串。
""", """    不继承 ``str`` 的话，ORM 侧就得处处写 ``.value``。继承 ``str`` 之后
    ``ImpactLevel.HIGH == "high"`` 直接成立，落库与读回都是同一个字符串（下面四条断言）。

    ⚠️ **但「漏写 ``.value`` 会静默存成 ``"ImpactLevel.HIGH"``、撑破 ``String(8)``」不是本仓
    的失效形态**（fix round 3 实测更正；口径与
    ``app/domain/prescription/exercises.py`` 的 ``ImpactLevel`` docstring 完全一致）：``str``
    子类的字符数据**就是值本身**，DBAPI 绑定传的是字符数据而不是 ``str()`` 的返回值，故裸
    ``sqlite3`` 绑定 ``ImpactLevel.HIGH`` 落库实测是 ``'high'``（``typeof=text``、
    ``length()=4``），``String(8).bind_processor(sqlite 方言)`` 实测也返回 ``None``（值原样
    下传）。只有显式写 ``str(x)`` 才得到 ``'ImpactLevel.HIGH'``——那是 **16** 字符，不是
    此前印的 19。而生产路径一律写 ``.value``（``sync_exercises``），故这条路今天不可达。
""")

    # ---------------- refdata_prescription.py ----------------
    f = File("backend/app/refdata_prescription.py")
    files[f.path] = f
    f.sub("M2/refdata_prescription.py equivalence()", """    本 Task 的四个函数里计划只点了 ``load_exercises`` / ``exercises`` / ``load_equivalence``
    三个；补这一个是为了**对称**：Task 7 的安全后置是逐学生跑的，少了单例就会每人重解析
""", """    ⚠️ 主语是**加载侧的四个函数**（``load_exercises`` / ``exercises`` / ``load_equivalence``
    / 本函数），不是本模块的全部公有函数——本模块公有函数是 **5** 个，第 5 个是
    ``sync_exercises``（``exercise`` 表的投影入口，不是加载器；fix round 3 补主语，此前只写
    「本 Task 的四个函数」，在那个未言明的口径外读起来与实测的 5 个矛盾）。计划只点了加载侧
    那四个里的 ``load_exercises`` / ``exercises`` / ``load_equivalence`` 三个；补
    ``equivalence`` 是为了**对称**：Task 7 的安全后置是逐学生跑的，少了单例就会每人重解析
""")
    f.sub("M3/refdata_prescription.py sync_exercises()", """    **本函数 flush 但不 commit**：事务边界由调用方掌握（与 :func:`app.db.repo.upsert`
    同一口径）。flush 是必要的——``impact_level`` 的 CHECK 约束与 ``ref`` 的 UNIQUE 约束
""", """    **本函数 flush 但不 commit**：事务边界由调用方掌握。⚠️ 与 :func:`app.db.repo.upsert`
    **只在「不 commit」这半句同口径**（fix round 3 更正：此前印的「同一口径」在 flush 上恰好
    相反）——``app/db/repo.py`` 的 ``upsert`` docstring 逐字是「本函数**既不 commit 也不
    flush**：事务边界由调用方掌握」，即它连 flush 也不做；本函数按 ``ref`` 逐条调它，故在
    循环外统一 flush 一次。flush 是必要的——``impact_level`` 的 CHECK 约束与 ``ref`` 的 UNIQUE 约束
""")

    # ---------------- app/db/models/prescription.py ----------------
    f = File("backend/app/db/models/prescription.py")
    files[f.path] = f
    f.sub("I4/models/prescription.py", """Task 9 各自加自己那张时，**必须同步改那道守卫的期望集合、``== 15`` 的三处断言与函数名里的
「fifteen」**（``tests/db/test_models.py`` ``:24`` / ``:163`` / ``:228`` / ``:472``），
以及本文件上面那张表。
""", """Task 9 各自加自己那张时，**必须同步改那道守卫的期望集合、``== 15`` 的三处断言与函数名里的
「fifteen」**，以及本文件上面那张表。⚠️ **按可 grep 的原文找，不要按裸行号找**
（fix round 3 更正：此前这里印的 ``:163`` / ``:228`` / ``:472`` 是 ``fb5bddb`` 上
``== 14`` 的位置；Task 2 把它们改成 ``== 15`` 时那三处就已推移，而本句没跟上——与 fr2
的 CE-7 是同一个失效形态，故本轮按 fr2 对 CE-7 的修法处理：先给可 grep 的原文，再给
绑 commit 的行号）：

* ``git grep -n "== 15" -- backend/tests/db/test_models.py`` 现命中 **3** 处，逐字是
  两处 ``assert len(tables) == 15, "守卫的覆盖面必须先被确认是这 15 张表"`` 与一处
  ``assert len(Base.metadata.tables) == 15``；
* 函数名用 ``git grep -n "test_all_fifteen_tables_created" -- backend`` 找（现命中 4 处：
  ``tests/db/test_models.py`` 的 ``def`` 行与一处注释引用、``app/db/models/__init__.py``
  与本文件各一处按名引用）；
* 若一定要写行号，必须绑 commit：在**代码基线** ``966eae0`` 上它们分别是 ``:169`` /
  ``:236`` / ``:494``（三处 ``==``）与 ``:24``（``def``）。
""")

    # ---------------- tests/db/test_models.py ----------------
    f = File("backend/tests/db/test_models.py")
    files[f.path] = f
    f.sub("I4/test_models.py", """    # 每个 Task 只改自己那一步，并同步改函数名里的英文数词与本文件 ``:163`` / ``:228`` /
    # ``:472`` 的三处 ``==``，以及 ``app/db/models/prescription.py`` 模块 docstring 里那张
    # 「表 → 归属 Task」的表。
""", """    # 每个 Task 只改自己那一步，并同步改：① 函数名里的英文数词；② 本文件里那三处 ``==``
    # 断言——**按可 grep 的原文找，不要按裸行号找**：``git grep -n "== 15" --
    # backend/tests/db/test_models.py`` 现命中 **3** 处，逐字是两处 ``assert len(tables)
    # == 15, "守卫的覆盖面必须先被确认是这 15 张表"`` 与一处 ``assert
    # len(Base.metadata.tables) == 15``（改完表数请重跑这条 grep 确认命中数仍是 3）。
    # ⚠️ 此前这里印的 ``:163`` / ``:228`` / ``:472`` 是 ``fb5bddb`` 上 ``== 14`` 的位置，
    # Task 2 改成 ``== 15`` 时它们就已推移（fix round 3 更正；与 fr2 的 CE-7 同一个失效
    # 形态）——若一定要写行号必须绑 commit：在代码基线 ``966eae0`` 上是 ``:169`` / ``:236``
    # / ``:494``；③ ``app/db/models/prescription.py`` 模块 docstring 里那张
    # 「表 → 归属 Task」的表。
""")

    # ---------------- tests/seed/test_generate.py ----------------
    f = File("backend/tests/seed/test_generate.py")
    files[f.path] = f
    f.sub("M5/test_generate.py", """    **枚举式**的：加第 15 张表之后，新表会静默落在两个分区之外——``seed_database`` 越界
    写它也不会红，因为那条守卫只遍历 ``DATA_TABLES``。
""", """    **枚举式**的：加第 15 张表之后，新表会静默落在**任何**分区之外——``seed_database``
    越界写它也不会红，因为**两条守卫都只遍历「已被分区认领」的表**（下面那条是
    ``DATA_TABLES + REFERENCE_TABLES`` 与 ``ORGANISATION_TABLES`` 两圈），认领之外的表
    两条都看不到。
    （fix round 3 更正两点：① 此前这里写「因为那条守卫只遍历 ``DATA_TABLES``」，那是 Plan
    02 Task 2 **之前**的口径；Task 2 已把「必须为 0」那一圈扩成 ``DATA_TABLES +
    REFERENCE_TABLES``，见
    :func:`test_seed_database_writes_only_organisation_tables_and_is_idempotent` 的
    docstring 与它的 ``for table in DATA_TABLES + REFERENCE_TABLES:``。② 上一句的「两个
    分区」也是 Task 2 之前的口径，今天是三个，故改成「任何分区」。**结论不变**——不在任何
    分区里的表两条守卫都遍历不到——只是理由要跟上当前的遍历对象。）
""")

    # ---------------- tests/test_refdata_prescription.py ----------------
    f = File("backend/tests/test_refdata_prescription.py")
    files[f.path] = f
    f.sub("I2/test_refdata_prescription.py IMPACT_DESCENDING 注释", """#: ``app/refdata_prescription.py``），两侧不同源，改坏任何一侧都会让
#: :func:`test_equivalence_never_maps_to_a_higher_impact_level` 红。
""", """#: ``app/refdata_prescription.py``），两侧刻意不同源（硬规矩 #35）。
#: ⚠️ **改坏哪一侧、红的是哪几条，两侧不同**（fix round 3 实测更正；此前这里印的「改坏任何
#: 一侧都会让 :func:`test_equivalence_never_maps_to_a_higher_impact_level` 红」对生产侧那
#: 一份**不成立**）。两次变异都在 ``2df6825`` 的干净工作树上**串行**实跑，各得
#: ``2 failed, 529 passed``：
#:
#: * 改坏**本常量**（反序成 ``("low", "medium", "high")``）→
#:   :func:`test_equivalence_never_maps_to_a_higher_impact_level`（10 条映射全部被判
#:   「升了冲击」）与 :func:`test_impact_rank_values_are_pinned_verbatim` 的支 2 红；
#: * 改坏**生产侧** ``IMPACT_RANK``（``HIGH: 0 ↔ LOW: 2`` 对调）→
#:   :func:`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable` 与
#:   :func:`test_impact_rank_values_are_pinned_verbatim` 的支 1 红，而「不升冲击」那一条
#:   **保持绿**（AST 实测 ``IMPACT_RANK`` 在它函数体里 0 命中，它只读本常量）。
""")
    f.sub("I5/test_refdata_prescription.py assert 消息", """    assert None in raw_values, "BMI 不归桶（Plan01 Ruling 19），故 None 必在其中"
""", """    # fix round 3 更正：这句此前引的「Plan01 Ruling 19」是**错的引用号**——Plan01 账本的
    # Ruling 19 讲的是「``raw_from_score`` 对非单调序列抛 ``ValueError``，不得返回哨兵」。
    # 「BMI 不归任何短板桶」的出处是 **spec §4.2**（BMI 那一行的「短板判定项」格是「否」、
    # 备注格是「不入桶」；同节说明逐字写着「**短板判定项 = 6 个**（**排除 BMI**）」），
    # Plan01 账本 Ruling 17 的关切 1 据此裁定「BMI 按 spec §4.2 不参与短板判定与桶化」。
    assert None in raw_values, "BMI 不归桶（spec §4.2：短板判定项 = 6 个，排除 BMI），故 None 必在其中"
""")
    f.sub("I2/test_refdata_prescription.py never_maps docstring", """    同一序的第二份、供 :meth:`EquivalenceTable.lookup` 使用；两份刻意不同源，改坏任何
    一份本条都红（硬规矩 #35）。
""", """    同一序的第二份、供 :meth:`EquivalenceTable.lookup` 使用；两份刻意不同源（硬规矩 #35）。
    ⚠️ **本条只看得到测试侧那一份**（fix round 3 实测更正：此前这里印的「改坏任何一份本条
    都红」不成立）——AST 实测 ``IMPACT_RANK`` 在本函数体里 **0 命中**，秩取自
    :data:`IMPACT_DESCENDING`（``rank = {value: index for index, value in
    enumerate(IMPACT_DESCENDING)}``）。变异实跑（``2df6825`` 干净工作树，串行）：反序
    :data:`IMPACT_DESCENDING` → **本条红**（10 条映射全部被判「升了冲击」）；对调生产侧
    ``IMPACT_RANK`` 的 ``HIGH: 0 ↔ LOW: 2`` → **本条保持绿**，红的是
    :func:`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable` 与
    :func:`test_impact_rank_values_are_pinned_verbatim`（两次都是 ``2 failed, 529
    passed``）。即「生产侧的秩被改坏」这件事由那两条看着，本条守的是**数据**（映射表里
    有没有升冲击的行、以及每条声明的 ``max_impact`` 与真实冲击是否一致）。
""")
    f.sub("M1/test_refdata_prescription.py 交叉引用补前缀", """    这条与 :func:`test_impact_level_vocabulary_agrees_with_the_domain_enum` 分工不同：
""", """    这条与 :func:`test_exercise_impact_level_vocabulary_agrees_with_the_domain_enum`
    分工不同（fix round 3 更正：此前这里漏了 ``exercise_`` 前缀，于是这个 ``:func:`` 交叉
    引用指向一个全仓不存在的名字——改前 ``git grep`` 那个短名在 ``backend/`` 下只有本行
    1 处命中。真名在本文件里由 ``def`` 行给出，且 ``app/db/models/prescription.py`` 引的
    一直是**正确**的全名）：
""")

    for p, f in files.items():
        f.write(dry)


if __name__ == "__main__":
    g = sys.argv[1]
    dry = "--dry" in sys.argv
    if g == "py":
        group_py(dry)
    else:
        raise SystemExit(f"unknown group {g}")

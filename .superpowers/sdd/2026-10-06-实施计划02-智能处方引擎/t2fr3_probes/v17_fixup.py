# -*- coding: utf-8 -*-
"""fr3 fix-up pass: remove every verbatim reproduction of a retracted false claim,
so that the double-direction grep gate is unambiguous and no stale citation /
stale bare line number is re-planted into the source.

usage: python v17_fixup.py [--dry]
"""
import sys

sys.path.insert(0, r"C:\Users\whwenhao\AppData\Local\Temp\sdd_fr3")
from v13_edit2 import File  # noqa: E402

DRY = "--dry" in sys.argv

EDITS = []

EX = "backend/app/domain/prescription/exercises.py"
TR = "backend/tests/test_refdata_prescription.py"
EY = "backend/data/exercises.yaml"
TG = "backend/tests/seed/test_generate.py"
MP = "backend/app/db/models/prescription.py"
TM = "backend/tests/db/test_models.py"

EDITS.append((EX, "FU1/I2 不复述被撤销的那句", """    ⚠️ **改坏哪一份、红的是哪几条，两侧不同**（fix round 3 实测更正；此前这里印的
    「改坏任何一份都会让 ``test_equivalence_never_maps_to_a_higher_impact_level`` 变红」
    **对生产侧那一份不成立**，且与下面 :data:`IMPACT_RANK` 自己的注释自相矛盾）。两次变异
""", """    ⚠️ **改坏哪一份、红的是哪几条，两侧不同**（fix round 3 实测更正；此前这里把两份词表
    混成一个主语，声称其中**任何**一份被改坏都会让同一条测试
    ``test_equivalence_never_maps_to_a_higher_impact_level`` 变红——那**对生产侧那一份
    不成立**，且与下面 :data:`IMPACT_RANK` 自己的注释自相矛盾）。两次变异
"""))

EDITS.append((EX, "FU2/I5 不复述错的裁定号", """#: **「BMI 不归任何短板桶」的出处**（fix round 3 更正：此前这里引的「Plan01 Ruling 19」是
#: **错的引用号**——Plan01 账本的 Ruling 19 讲的是「``raw_from_score`` 对非单调序列抛
#: ``ValueError``，不得返回哨兵」，是反查函数的护栏，与桶归属无关；错误源头是 Plan02 账本
#: P2-A4，账本由控制者勘误）。真正的出处是 **spec §4.2**：那张「8 项原始测量」的表里 BMI
""", """#: **「BMI 不归任何短板桶」的出处**（fix round 3 更正：此前这里引的是 Plan01 账本里**另一条**
#: 裁定——那条讲的是「``raw_from_score`` 对非单调序列抛 ``ValueError``，不得返回哨兵」，是
#: 反查函数的护栏、与桶归属无关，即**引用号错**；错误源头是 Plan02 账本 P2-A4，账本由控制者
#: 勘误。本行刻意**不复述那个错号**，免得它被下一次 grep 当成一处有效引用）。真正的出处是
#: **spec §4.2**：那张「8 项原始测量」的表里 BMI
"""))

EDITS.append((TR, "FU3/I2 不复述被撤销的那句", """#: ⚠️ **改坏哪一侧、红的是哪几条，两侧不同**（fix round 3 实测更正；此前这里印的「改坏任何
#: 一侧都会让 :func:`test_equivalence_never_maps_to_a_higher_impact_level` 红」对生产侧那
#: 一份**不成立**）。两次变异都在 ``2df6825`` 的干净工作树上**串行**实跑，各得
""", """#: ⚠️ **改坏哪一侧、红的是哪几条，两侧不同**（fix round 3 实测更正；此前这里把两侧混成一个
#: 主语，声称其中**任何**一侧被改坏都会让
#: :func:`test_equivalence_never_maps_to_a_higher_impact_level` 红——那对生产侧那一份
#: **不成立**）。两次变异都在 ``2df6825`` 的干净工作树上**串行**实跑，各得
"""))

EDITS.append((TR, "FU4/I5 不复述错的裁定号", """    # fix round 3 更正：这句此前引的「Plan01 Ruling 19」是**错的引用号**——Plan01 账本的
    # Ruling 19 讲的是「``raw_from_score`` 对非单调序列抛 ``ValueError``，不得返回哨兵」。
""", """    # fix round 3 更正：这句此前引的是 Plan01 账本里**另一条**裁定（那条讲的是
    # 「``raw_from_score`` 对非单调序列抛 ``ValueError``，不得返回哨兵」），即**引用号错**；
    # 本行刻意不复述那个错号，免得它被下一次 grep 当成一处有效引用。
"""))

EDITS.append((TR, "FU5/I2 不复述被撤销的那句", """    ⚠️ **本条只看得到测试侧那一份**（fix round 3 实测更正：此前这里印的「改坏任何一份本条
    都红」不成立）——AST 实测 ``IMPACT_RANK`` 在本函数体里 **0 命中**，秩取自
""", """    ⚠️ **本条只看得到测试侧那一份**（fix round 3 实测更正：此前这里声称两份里的任何一份
    被改坏本条都会红，**不成立**）——AST 实测 ``IMPACT_RANK`` 在本函数体里 **0 命中**，秩取自
"""))

EDITS.append((EY, "FU6/I6 不复述旧编号那一句", """#                 「动作库的视频源」排在 **#30**（fix round 3 更正：此前这里印的「预留为 #29」
#                 是本文件落地那一刻（`3ea27cc`）的旧编号；紧接着的 `d40f36c` 把 #28 让给本
""", """#                 「动作库的视频源」排在 **#30**（fix round 3 更正：此前这里印的是 **#29**，
#                 那是本文件落地那一刻（`3ea27cc`）的旧编号；紧接着的 `d40f36c` 把 #28 让给本
"""))

EDITS.append((EY, "FU7/M4 不复述旧归属那一句", """# ⚠️ 这 12 项的**出处不止一行**（fix round 3 更正：此前写「spec §7.2 :487 点名的 12 项」，
# 归属不对——数字 12 / 16 / 23 都是对的）。spec §7.2 末尾那段「指导文件给出的层级参数已
# 全部落入模板」的散文确实点名了 **12** 个东西，但**其中一个是「可选挑战任务」**，而本文件
""", """# ⚠️ 这 12 项的**出处不止一行**（fix round 3 更正：此前把这 12 项的归属**全部**记在 §7.2
# 末尾那一行散文名下，归属不对——数字 12 / 16 / 23 都是对的）。spec §7.2 末尾那段「指导
# 文件给出的层级参数已全部落入模板」的散文确实点名了 **12** 个东西，但**其中一个是「可选
# 挑战任务」**，而本文件
"""))

EDITS.append((EY, "FU9/M9 不复述被撤销的那半句", """# 断言会**因为它消失**而变红。⚠️ 后半句要分开说（fix round 3 更正：此前写「没有任何一条
# 映射或断言依赖它」，字面上不成立）——`tests/test_refdata_prescription.py` 的
""", """# 断言会**因为它消失**而变红。⚠️ 这两件事必须分开说（fix round 3 更正：此前把「映射」与
# 「断言」并在同一句里一起否定，其中关于断言的那半句字面上不成立）——
# `tests/test_refdata_prescription.py` 的
"""))

EDITS.append((TG, "FU8/M5 不复述旧理由那一句", """    （fix round 3 更正两点：① 此前这里写「因为那条守卫只遍历 ``DATA_TABLES``」，那是 Plan
    02 Task 2 **之前**的口径；Task 2 已把「必须为 0」那一圈扩成 ``DATA_TABLES +
""", """    （fix round 3 更正两点：① 此前这里把理由写成「那条守卫的遍历对象只有 ``DATA_TABLES``」，
    那是 Plan 02 Task 2 **之前**的口径；Task 2 已把「必须为 0」那一圈扩成 ``DATA_TABLES +
"""))

EDITS.append((MP, "FU10/I4 不复述三个过期裸行号", """（fix round 3 更正：此前这里印的 ``:163`` / ``:228`` / ``:472`` 是 ``fb5bddb`` 上
``== 14`` 的位置；Task 2 把它们改成 ``== 15`` 时那三处就已推移，而本句没跟上——与 fr2
的 CE-7 是同一个失效形态，故本轮按 fr2 对 CE-7 的修法处理：先给可 grep 的原文，再给
绑 commit 的行号）：
""", """（fix round 3 更正：此前这里印的是**三个裸行号**，它们是 ``fb5bddb`` 上 ``== 14`` 的
位置；Task 2 把它们改成 ``== 15`` 时那三处就已推移，而本句没跟上——与 fr2 的 CE-7 是
同一个失效形态，故本轮按 fr2 对 CE-7 的修法处理：先给可 grep 的原文，再给绑 commit 的
行号。那三个过期裸行号本轮**不再复述**，免得下一次 grep 又把它们当成有效位置）：
"""))

EDITS.append((TM, "FU11/I4 不复述三个过期裸行号", """    # ⚠️ 此前这里印的 ``:163`` / ``:228`` / ``:472`` 是 ``fb5bddb`` 上 ``== 14`` 的位置，
    # Task 2 改成 ``== 15`` 时它们就已推移（fix round 3 更正；与 fr2 的 CE-7 同一个失效
    # 形态）——若一定要写行号必须绑 commit：在代码基线 ``966eae0`` 上是 ``:169`` / ``:236``
    # / ``:494``；③ ``app/db/models/prescription.py`` 模块 docstring 里那张
""", """    # ⚠️ 此前这里印的是**三个裸行号**，它们是 ``fb5bddb`` 上 ``== 14`` 的位置，Task 2 改成
    # ``== 15`` 时那三处就已推移（fix round 3 更正；与 fr2 的 CE-7 同一个失效形态；那三个
    # 过期行号本轮**不再复述**）——若一定要写行号必须绑 commit：在代码基线 ``966eae0`` 上是
    # ``:169`` / ``:236`` / ``:494``；③ ``app/db/models/prescription.py`` 模块 docstring 里那张
"""))

by_file = {}
for rel, tag, old, new in EDITS:
    by_file.setdefault(rel, []).append((tag, old, new))

for rel, items in by_file.items():
    f = File(rel)
    for tag, old, new in items:
        f.sub(tag, old, new)
    f.write(DRY)

# -*- coding: utf-8 -*-
import pathlib
MSG = """test: Plan02 Task1 fix round 5，两份矩阵各加 Task 2 那一格绿档（Ruling 67）+ 补正合成树配方（Ruling 68）+ 6 条 Minor 散文

Ruling 67（Important #1）：purity 那份把 Task 2 的形状说成 level == 1，实测是 level == 2
（app/domain/prescription/match.py 的 __package__ 是 app.domain.prescription，包深 3 →
两个点才上溯到 app.domain）。两份 cases 各加一格
("indicators", 2, ("app", "domain", "prescription"), "X", "GREEN")，11 → 12 格；改前
purity 侧 (包深3, level2, GREEN) 是 0 格。两侧这一格颜色都是 GREEN 但判据不同（purity 命中
白名单前缀 app.domain. / layering 不以 app.seed 开头），已按硬规矩 #56 逐句标主语，
layering 侧的注释没有照抄 purity 侧的白名单理由。passed 数不变（只加矩阵格、不加测试函数）。

Ruling 68（Important #2）：purity 印的合成树配方漏了 BACKEND 重定向与「树里 ≥5 个 .py」，
照字面做会 15 行（14 行 + 干净对照行）× 3 列全 RED。两项补齐，并加上「必须先跑一行已知
三列全 GREEN 的干净对照」（硬规矩 #53 的正面表述）；补正后 14 行 × 3 列 = 42 格逐格相符、
FORBIDDEN_IO 的「0 vs 2」也复现，故表本身未动。test_layering.py 那份配方按硬规矩 #51 对齐
（补上 ≥8 个 .py 与干净对照；两处下界不同，已互相点名）。

Minor 1：两份「两个 bug」下面列 3 个 bullet → 改成「两个 bug / 三条变异」，并写明 2≠3 的
理由（Ruling 36 有两半，两半都在 fix round 2 的 1fa9941 里落地），与同段既有的「三条」
「三种」统一。
Minor 2：两份「479 条全绿」绑到 be0f1af^（= 1fa9941），并写明 HEAD 上照做会得到
2 failed, 479 passed；479 那个数在 worktree 上亲跑复现过（原样 / 删守卫各一次，都 rc 0）。
Minor 3：fix 链新增散文里 11 处未绑轮次的「本轮」，绑掉 10 处（purity 4 / layering 4 /
test_models 2），逐处按 git diff 定到 round 1/2/3；剩 1 处在 daily.py:206，受本轮禁区
「daily.py 只许动 Minor 5 那两个散文标签」限制未动，已在任务报告里写明并给出待打的补丁。
Minor 4：test_models.py「两条查询计划逐字复现」→「尾部逐字复现」，并补印 EXPLAIN QUERY PLAN
的 detail 全串（实测以 SEARCH stratification_result 开头，上表只印了尾部）。
Minor 5：daily.py 两个「均值」标「截断到百分位」（20.665 → 20.66、21.035 → 21.03，而
round(_, 2) 分别给 20.66 / 21.04）。只动这两个散文标签，daily.py 代码 0 字节改动。
Minor 6：purity「守卫当场假绿」补主语（layering 那一份对同一个串是正确的 GREEN，不是假绿）。

验收：481 passed；--cov=app/domain --cov-branch 得 399 stmts / Miss 0 / 114 branch /
BrPart 0 / 100%，480 passed, 1 skipped。变异验收 7 相位（M0 不变异 / M1 语义等价改写 /
只改 purity / 只改 layering / 两份都改 / 定向变异 / 定向变异 + 删掉新格）全部符合预期，
其中 M5→M6 的对照证明新加那一格是**承重的**（删掉它，定向变异就抓不到）。
改动面自证（剥 docstring 后逐顶层单元，代码基线 6784d57，带对照组）：两个守卫文件各只有
test_absolute_folding_matches_resolve_name 变了；test_models.py / daily.py 全部单元 SAME；
既有 5 条守卫 assert 与新测试里的 3 条 assert 全部逐字未动。
"""
p = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd\fr5_probes\pe_fr5_commitmsg.txt")
p.write_text(MSG, encoding="utf-8", newline="\n")
print("wrote", p, p.stat().st_size, "bytes")
print(MSG)

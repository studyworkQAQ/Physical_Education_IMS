# -*- coding: utf-8 -*-
"""fix round 5 的落盘脚本：按字节写，CRLF 保持不变，逐条编辑自带双向闸门。"""
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")

PUR = ROOT / "backend/tests/architecture/test_domain_purity.py"
LAY = ROOT / "backend/tests/architecture/test_layering.py"
MOD = ROOT / "backend/tests/db/test_models.py"
DAI = ROOT / "backend/app/pipeline/daily.py"

BEFORE = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (PUR, LAY, MOD, DAI)}

# ==========================================================================
# test_domain_purity.py
# ==========================================================================
P_A_old = (
    "     ``_is_allowed('app.domain.seed')`` -> ``True``）、命中白名单前缀 ``app.domain.`` →\n"
    "     **守卫当场假绿**\n"
    "     （硬规矩 #52：形如 ``f(x) == y`` 的举例必须是真跑过的输出）。\n"
)
P_A_new = (
    "     ``_is_allowed('app.domain.seed')`` -> ``True``）、命中白名单前缀 ``app.domain.`` →\n"
    "     **本守卫当场假绿**。主语必须标出来（硬规矩 #56）：这个「假绿」只属于\n"
    "     :mod:`tests.architecture.test_domain_purity` 这一份——它本该把 ``app.seed`` 判成\n"
    "     offender，却被折出来的 ``app.domain.seed`` 骗过。:mod:`tests.architecture.test_layering`\n"
    "     那一份对**同一个串**判的是 ``app.seed`` 前缀，``_is_forbidden('app.domain.seed')`` 为\n"
    "     ``False``（fix round 5 亲跑）→ 那一份是**正确的 GREEN**、不是假绿。\n"
    "     （硬规矩 #52：形如 ``f(x) == y`` 的举例必须是真跑过的输出）。\n"
)
P_A_absent = "     **守卫当场假绿**\n"

P_B_old = (
    "    **守的是 fix round 2 修掉、而此前仓库里没有任何断言看着的两个 bug**（Plan02 Ruling 46：\n"
    "    谁删掉 ``if level - 1 > len(package): return None``，479 条全绿）：\n"
)


def p_b_new(other_module):
    return (
        "    **守的是 fix round 2 修掉、而此前仓库里没有任何断言看着的两个 bug；下面列的是三条\n"
        "    变异**（``2 ≠ 3`` 不是笔误：Ruling 36 有**两半**——``_absolute`` 接 ``name``、\n"
        "    ``_imported_modules`` 一名一条展开，两半都在 fix round 2 那一个 commit ``1fa9941`` 里\n"
        "    落地；加上 Ruling 35 的越界档，就是「两个 bug / 三条变异」，与下面「三条的复现命令」\n"
        "    「三种变异」是同一个计数）。Plan02 Ruling 46：谁把**两份**的\n"
        "    ``if level - 1 > len(package): return None`` 都删掉，在基线 ``be0f1af^``（= ``1fa9941``，\n"
        "    本测试还不存在的那一次）上全量 **479 passed、退出码 0**。fix round 5 在 ``$env:TEMP``\n"
        "    的 ``git worktree`` 上亲跑复现：原样 ``479 passed in 57.41s``、删掉那 3 行后\n"
        "    ``479 passed in 59.20s``，两次退出码都是 0。⚠️ 别在 HEAD 上照做：HEAD 有 481 条，\n"
        "    同一个变异会得到 ``2 failed, 479 passed``，红的正是本文件与\n"
        "    :mod:`%s` 各一条 ``test_absolute_folding_matches_resolve_name``。\n"
        % other_module
    )


P_B_absent = "479 条全绿"

P_C_old = (
    "    **绿档同时在场**（硬规矩 #50：只放红档会得到一条过紧的守卫）：``level == 1`` 的包内导入\n"
    "    折成 ``app.domain.tables``，必须仍被 :func:`_is_allowed` 放行——Task 2 起\n"
    "    ``app/domain/prescription/`` 子包里的 ``from ..indicators import X`` 正是这一档。\n"
)
P_C_new = (
    "    **绿档同时在场**（硬规矩 #50：只放红档会得到一条过紧的守卫），而且是**两档**：\n"
    "\n"
    "    * ``level == 1`` 的包内导入折成 ``app.domain.tables``，必须仍被 :func:`_is_allowed`\n"
    "      放行（矩阵第 2、3 行）。\n"
    "    * ``level == 2`` 的**跨子包**导入也必须放行（矩阵第 9 行，fix round 5 新加，Plan02\n"
    "      Ruling 67）：Task 2 起 ``app/domain/prescription/match.py`` 里的\n"
    "      ``from ..indicators import X`` 就是这一档。⚠️ 它是 ``level == 2`` 而**不是**\n"
    "      ``level == 1``——那个文件的 ``__package__`` 是 ``app.domain.prescription``（包深 3），\n"
    "      要**两个点**才上溯到 ``app.domain``。fix round 5 亲跑（本机 Python 3.11.1）::\n"
    "\n"
    "          ast.parse('from ..indicators import X') -> level=2 module='indicators' names=['X']\n"
    "          _package_of(BACKEND / 'app/domain/prescription/match.py')\n"
    "              = ('app', 'domain', 'prescription')\n"
    "          _absolute('indicators', 2, ('app', 'domain', 'prescription'), 'X')\n"
    "              = 'app.domain.indicators'\n"
    "          resolve_name('..indicators', 'app.domain.prescription') = 'app.domain.indicators'\n"
    "          _is_allowed('app.domain.indicators') = True   -> 本文件（purity 侧）判 GREEN\n"
    "\n"
    "      改前这一格**不在矩阵里**：那 11 格里 ``(包深 3, level 2, GREEN)`` 是 **0 格**、GREEN\n"
    "      只有 2 格且都在包深 2 / ``level == 1``，于是「Task 2 那个形状在 purity 侧是绿的」这件\n"
    "      事仓库里没有任何断言看着。:mod:`tests.architecture.test_layering` 那一份的同一格也是\n"
    "      GREEN，但**理由不同**：它判的是 ``app.seed`` 前缀，\n"
    "      ``_is_forbidden('app.domain.indicators')`` 为 ``False`` → 不以 ``app.seed`` 开头就放行。\n"
)
P_C_absent = "折成 ``app.domain.tables``，必须仍被 :func:`_is_allowed` 放行——Task 2 起"

P_D_old = (
    '        ("", 2, ("app", "domain"), "seed", "RED"),\n'
    "        # 越界档：resolve_name 抛 ImportError，_absolute 必须返回 None（Ruling 35）\n"
)
P_D_new = (
    '        ("", 2, ("app", "domain"), "seed", "RED"),\n'
    "        # Task 2 的形状（fix round 5 新加，Plan02 Ruling 67）：app/domain/prescription/match.py\n"
    "        # 里的 `from ..indicators import X`——包深 3 → 两个点才上溯到 app.domain，故 level == 2。\n"
    "        # 折成 app.domain.indicators；本文件（purity 侧）命中白名单前缀 app.domain. → GREEN。\n"
    "        # test_layering.py 同一格也是 GREEN，但理由是「不以 app.seed 开头」、不是白名单。\n"
    '        ("indicators", 2, ("app", "domain", "prescription"), "X", "GREEN"),\n'
    "        # 越界档：resolve_name 抛 ImportError，_absolute 必须返回 None（Ruling 35）\n"
)
P_D_absent = P_D_old

P_E = [
    ("      **没枚举进去的包深（包深 4 及更深）不被覆盖**；上面那 11 格矩阵的 ``package`` 入参\n",
     "      **没枚举进去的包深（包深 4 及更深）不被覆盖**；上面那 12 格矩阵的 ``package`` 入参\n",
     "上面那 11 格矩阵"),
    ("    * 矩阵是有限的 11 格：更深的包、更大的 ``level`` 没列进去就不被覆盖。判据既然是\n",
     "    * 矩阵是有限的 12 格：更深的包、更大的 ``level`` 没列进去就不被覆盖。判据既然是\n",
     "矩阵是有限的 11 格"),
    ("    # 上面 11 格的 package 入参是**手写的**，故 _package_of 被改坏时它们照样全绿；而它是\n",
     "    # 上面 12 格的 package 入参是**手写的**，故 _package_of 被改坏时它们照样全绿；而它是\n",
     "# 上面 11 格的 package"),
]

P_F_old = (
    "     :func:`_dotted` 只还原调用表达式自身、代码里没有任何赋值追踪）。下面是合成树上的实测\n"
    "     口径：把 ``DOMAIN`` 指到 ``$env:TEMP`` 下一棵只有 ``app/domain/`` 的合成树，逐条写进\n"
    "     一个探针文件后分别调用三条守卫（本轮亲跑）::\n"
)
P_F_new = (
    "     :func:`_dotted` 只还原调用表达式自身、代码里没有任何赋值追踪）。下面是合成树上的实测\n"
    "     口径（**配方 fix round 5 补正**，Plan02 Ruling 68——改前这一段照字面做会得到**全红**）：\n"
    "     把 ``DOMAIN`` **和** ``BACKEND`` 一起指到 ``$env:TEMP`` 下一棵只有 ``app/domain/`` 的\n"
    "     合成树。``BACKEND`` 也必须改：:func:`_package_of` 里是 ``py.relative_to(BACKEND)``，\n"
    "     只改 ``DOMAIN`` 会让第一条守卫抛 ``ValueError: … is not in the subpath of …``（fix\n"
    "     round 5 亲跑）。树里要放 **≥ 5 个 ``.py``**（含探针文件自己），否则\n"
    "     :func:`_assert_not_empty` 的空转守卫先响（``AssertionError: 只扫到 1 个 .py …``）、\n"
    "     第二三条守卫一起变红。⚠️ **先跑一行已知三列全 GREEN 的干净对照**（探针内容只写\n"
    "     ``x = 1`` 就够；fix round 5 亲跑它确实是 ``GREEN / GREEN / GREEN``）——没有这一行，\n"
    "     「全红」既可能是守卫坏了、也可能是配方少了一项，两者不可区分（硬规矩 #53）。逐条写进\n"
    "     探针文件后分别调用三条守卫（fix round 1 首跑；fix round 5 用补正后的配方复跑，\n"
    "     14 行 × 3 列 = 42 格逐格相符、0 处不符）::\n"
)
P_F_absent = "口径：把 ``DOMAIN`` 指到 ``$env:TEMP`` 下一棵只有 ``app/domain/`` 的合成树"

P_G_old = (
    "    ``_imported_modules``，再跑 ``python -m pytest tests/architecture -q``。本轮实测三种变异\n"
    "    各让**本文件这一条**红、而 :mod:`tests.architecture.test_layering` 那一条**保持绿**——\n"
    "    两份 ``_absolute`` 互相独立，这正是硬规矩 #51 要两份回归测试的原因。断言里印出来的折算值\n"
)
P_G_new = (
    "    ``_imported_modules``，再跑 ``python -m pytest tests/architecture -q``。fix round 3 实测\n"
    "    三种变异各让**本文件这一条**红、而 :mod:`tests.architecture.test_layering` 那一条\n"
    "    **保持绿**——两份 ``_absolute`` 互相独立，这正是硬规矩 #51 要两份回归测试的原因。\n"
    "    断言里印出来的折算值\n"
)
P_G_absent = "q``。本轮实测三种变异"

P_H_old = (
    "    才会被挡。终审 A 说的「14 种写法可绕过」是它自己的枚举，本轮没有逐条复跑；上面三条\n"
    "    是**亲跑基线**的结果，两者方向一致。\n"
)
P_H_new = (
    "    才会被挡。终审 A 说的「14 种写法可绕过」是它自己的枚举，fix round 1 没有逐条复跑；\n"
    "    上面三条是**亲跑基线**的结果，两者方向一致。\n"
)
P_H_absent = "枚举，本轮没有逐条复跑"

P_I_old = (
    "    第 1–7 行是 fix round 1 那次跑的结果，第 8–14 行是 **fix round 2 新增**（Plan02\n"
    "    Ruling 38）；本轮把 14 行**全部重跑了一遍**，前 7 行的颜色逐字复现。\n"
)
P_I_new = (
    "    第 1–7 行是 fix round 1 那次跑的结果，第 8–14 行是 **fix round 2 新增**（Plan02\n"
    "    Ruling 38）；fix round 2 把 14 行**全部重跑了一遍**，前 7 行的颜色逐字复现。fix round 5\n"
    "    又用补正后的配方重跑一遍：**14 行 × 3 列 = 42 格逐格相符、0 处不符**，另加一行干净对照\n"
    "    （探针只写 ``x = 1``）三列全 GREEN。同一次跑也复现了 :data:`FORBIDDEN_IO` 那句\n"
    "    「0 vs 2」：第 9 行 ``__import__(\"os\").listdir(\".\")`` 命中 **0** 个子串，对照组\n"
    "    ``import os`` 换行 ``os.listdir('.')`` 命中 **2** 个（``import os`` / ``os.listdir``）。\n"
    "    ⚠️ 反过来，照**补正前**的字面配方（只重定向 ``DOMAIN``、树里 1 个 ``.py``）跑，\n"
    "    fix round 5 实测**15 行（14 行 + 干净对照行）× 3 列全 RED**：第一条守卫报 ``ValueError``、\n"
    "    第二三条报 ``AssertionError: 只扫到 1 个 .py …``。所以那张表没错，坏的是配方\n"
    "    （Plan02 Ruling 68）。\n"
)
P_I_absent = "Ruling 38）；本轮把 14 行"

PUR_EDITS = [
    ("P-A Minor6 补主语", P_A_old, P_A_new, P_A_absent),
    ("P-B Minor1+2 计数与 commit 绑定", P_B_old,
     p_b_new("tests.architecture.test_layering"), P_B_absent),
    ("P-C Ruling67-1 level 说错", P_C_old, P_C_new, P_C_absent),
    ("P-D Ruling67-2 矩阵加一格", P_D_old, P_D_new, P_D_absent),
    ("P-F Ruling68 配方补正", P_F_old, P_F_new, P_F_absent),
    ("P-G Minor3 :222 绑轮次", P_G_old, P_G_new, P_G_absent),
    ("P-H Minor3 :392 绑轮次", P_H_old, P_H_new, P_H_absent),
    ("P-I Minor3 :544 绑轮次", P_I_old, P_I_new, P_I_absent),
] + [("P-E%d 11->12 格" % (i + 1), o, n, a) for i, (o, n, a) in enumerate(P_E)]

# ==========================================================================
# test_layering.py
# ==========================================================================
L_B_old = (
    "    **绿档同时在场**（硬规矩 #50：只放红档会得到一条过紧的守卫）：``app/db/models/`` 包内\n"
    "    真实存在的那 12 条 ``level == 1`` 相对导入折成 ``app.db.models._shared`` 一类，必须仍被\n"
    "    :func:`_is_forbidden` 放过。⚠️ 矩阵第 7 行 ``(\"\", 2, (\"app\", \"db\", \"models\"), \"seed\")``\n"
)
L_B_new = (
    "    **绿档同时在场**（硬规矩 #50：只放红档会得到一条过紧的守卫）：``app/db/models/`` 包内\n"
    "    真实存在的那 12 条 ``level == 1`` 相对导入折成 ``app.db.models._shared`` 一类，必须仍被\n"
    "    :func:`_is_forbidden` 放过（fix round 1 亲跑数出 12 条；fix round 5 复跑仍是 12 条、\n"
    "    全部 ``level == 1``、全部落在 ``app.db.models`` 包内）。\n"
    "\n"
    "    **矩阵第 9 行是 fix round 5 新加的绿档**（Plan02 Ruling 67）：Task 2 起\n"
    "    ``app/domain/prescription/match.py`` 里的 ``from ..indicators import X``——包深 3 →\n"
    "    **两个点**才上溯到 ``app.domain``，故 ``level == 2``（**不是** ``level == 1``）。\n"
    "    fix round 5 亲跑::\n"
    "\n"
    "        _package_of(BACKEND / 'app/domain/prescription/match.py')\n"
    "            = ('app', 'domain', 'prescription')\n"
    "        _absolute('indicators', 2, ('app', 'domain', 'prescription'), 'X')\n"
    "            = 'app.domain.indicators'\n"
    "        resolve_name('..indicators', 'app.domain.prescription') = 'app.domain.indicators'\n"
    "        _is_forbidden('app.domain.indicators') = False  -> 本文件（layering 侧）判 GREEN\n"
    "\n"
    "    **放行理由与 purity 那一份不同**：本文件放行它是因为它**不以 ``app.seed`` 开头**；\n"
    "    :mod:`tests.architecture.test_domain_purity` 那一份放行它是因为它**命中白名单前缀\n"
    "    ``app.domain.``**。两份这一格颜色相同、判据不同，这不是抄错（硬规矩 #56）。\n"
    "\n"
    "    ⚠️ 矩阵第 7 行 ``(\"\", 2, (\"app\", \"db\", \"models\"), \"seed\")``\n"
)
L_B_absent = ":func:`_is_forbidden` 放过。⚠️ 矩阵第 7 行"

L_C_new = (
    '        ("", 2, ("app", "domain"), "seed", "RED"),\n'
    "        # Task 2 的形状（fix round 5 新加，Plan02 Ruling 67）：app/domain/prescription/match.py\n"
    "        # 里的 `from ..indicators import X`——包深 3 → 两个点才上溯到 app.domain，故 level == 2。\n"
    "        # 折成 app.domain.indicators；本文件（layering 侧）判的是 app.seed 前缀，\n"
    "        # _is_forbidden('app.domain.indicators') = False → 不以 app.seed 开头 → GREEN。\n"
    "        # ⚠️ 与 test_domain_purity.py 同一格的 GREEN **理由不同**（那一份是命中白名单前缀\n"
    "        # app.domain.）：颜色相同、判据不同，这不是抄错（硬规矩 #56）。\n"
    '        ("indicators", 2, ("app", "domain", "prescription"), "X", "GREEN"),\n'
    "        # 越界档：resolve_name 抛 ImportError，_absolute 必须返回 None（Ruling 35）\n"
)

L_D = [
    ("      **没枚举进去的包深（包深 4 及更深）不被覆盖**；上面那 11 格矩阵的 ``package`` 入参\n",
     "      **没枚举进去的包深（包深 4 及更深）不被覆盖**；上面那 12 格矩阵的 ``package`` 入参\n",
     "上面那 11 格矩阵"),
    ("    * 矩阵是有限的 11 格：更深的包、更大的 ``level`` 没列进去就不被覆盖。判据既然是\n",
     "    * 矩阵是有限的 12 格：更深的包、更大的 ``level`` 没列进去就不被覆盖。判据既然是\n",
     "矩阵是有限的 11 格"),
    ("    # 上面 11 格的 package 入参是**手写的**，故 _package_of 被改坏时它们照样全绿；而它是\n",
     "    # 上面 12 格的 package 入参是**手写的**，故 _package_of 被改坏时它们照样全绿；而它是\n",
     "# 上面 11 格的 package"),
]

L_E_old = (
    "    合成树实测（把 ``BACKEND`` / ``APP`` 指到 ``$env:TEMP`` 下一棵形状与 ``backend/app``\n"
    "    相同的树，逐条写进探针文件后直接调用本测试函数）：上述两种写法**改前全绿**、改后全红。\n"
)
L_E_new = (
    "    合成树实测（把 ``BACKEND`` / ``APP`` **两个都**指到 ``$env:TEMP`` 下一棵形状与\n"
    "    ``backend/app`` 相同的树：:func:`_package_of` 里是 ``py.relative_to(BACKEND)``，只改\n"
    "    ``APP`` 会抛 ``ValueError: … is not in the subpath of …``；且 ``pipeline`` / ``db`` /\n"
    "    ``domain`` 三个目录合计要有 **≥ 8 个 ``.py``**（含探针文件自己），否则本文件那条\n"
    "    ``len(scanned) >= 8`` 的空转守卫先响（``AssertionError: 只扫到 1 个 .py …``）、探针的\n"
    "    颜色不可解释，故**必须先跑一行已知 GREEN 的干净对照**（探针只写 ``x = 1``；上面四条\n"
    "    都是 fix round 5 亲跑）。同款配方在 :mod:`tests.architecture.test_domain_purity` 那一份\n"
    "    里下界是 ``>= 5``、重定向的是 ``DOMAIN`` **和** ``BACKEND``，两处 fix round 5 已互相\n"
    "    对齐（Plan02 Ruling 68／硬规矩 #51/#53）。逐条写进探针文件后直接调用本测试函数）：\n"
    "    上述两种写法**改前全绿**、改后全红。\n"
)
L_E_absent = "合成树实测（把 ``BACKEND`` / ``APP`` 指到"

L_F_old = (
    "    这条命令数（本轮亲跑：12 条、全部 ``level == 1``、全部落在 ``app.db.models`` 包内）::\n"
)
L_F_new = (
    "    这条命令数（fix round 1 亲跑；fix round 5 复跑仍是同一个结果：12 条、全部\n"
    "    ``level == 1``、全部落在 ``app.db.models`` 包内）::\n"
)
L_F_absent = "这条命令数（本轮亲跑"

L_G_old = (
    "    ``_imported_modules``，再跑 ``python -m pytest tests/architecture -q``。本轮实测三种变异\n"
    "    各让**本文件这一条**红、而 :mod:`tests.architecture.test_domain_purity` 那一条**保持绿**——\n"
    "    两份 ``_absolute`` 互相独立，这正是硬规矩 #51 要两份回归测试的原因。断言里印出来的折算值\n"
)
L_G_new = (
    "    ``_imported_modules``，再跑 ``python -m pytest tests/architecture -q``。fix round 3 实测\n"
    "    三种变异各让**本文件这一条**红、而 :mod:`tests.architecture.test_domain_purity` 那一条\n"
    "    **保持绿**——两份 ``_absolute`` 互相独立，这正是硬规矩 #51 要两份回归测试的原因。\n"
    "    断言里印出来的折算值\n"
)
L_G_absent = "q``。本轮实测三种变异"

L_H_old = "    # 文件数实测（在**仓库根**跑，一条命令数完三个目录；本轮亲跑）::\n"
L_H_new = "    # 文件数实测（在**仓库根**跑，一条命令数完三个目录；fix round 1 亲跑）::\n"
L_H_absent = "三个目录；本轮亲跑"

L_I_old = "    # 24 − 6(domain) = 18，由上面那条 Counter 命令本轮亲跑得出），本断言拦不住。\n"
L_I_new = "    # 24 − 6(domain) = 18，由上面那条 Counter 命令在 fix round 2 亲跑得出），本断言拦不住。\n"
L_I_absent = "Counter 命令本轮亲跑得出"

LAY_EDITS = [
    ("L-A Minor1+2 计数与 commit 绑定", P_B_old,
     p_b_new("tests.architecture.test_domain_purity"), P_B_absent),
    ("L-B Ruling67-2 绿档段落", L_B_old, L_B_new, L_B_absent),
    ("L-C Ruling67-2 矩阵加一格", P_D_old, L_C_new, P_D_old),
    ("L-E Ruling68 配方对齐", L_E_old, L_E_new, L_E_absent),
    ("L-F Minor3 :150 绑轮次", L_F_old, L_F_new, L_F_absent),
    ("L-G Minor3 :210 绑轮次", L_G_old, L_G_new, L_G_absent),
    ("L-H Minor3 :371 绑轮次", L_H_old, L_H_new, L_H_absent),
    ("L-I Minor3 :385 绑轮次", L_I_old, L_I_new, L_I_absent),
] + [("L-D%d 11->12 格" % (i + 1), o, n, a) for i, (o, n, a) in enumerate(L_D)]

# ==========================================================================
# test_models.py
# ==========================================================================
M_A_old = "    而产生它的脚本此前不在库内（从仓库无法复现）；本轮把它整段抄在下面，在**仓库根**跑\n"
M_A_new = "    而产生它的脚本此前不在库内（从仓库无法复现）；fix round 1 把它整段抄在下面，在**仓库根**跑\n"
M_A_absent = "从仓库无法复现）；本轮把它整段抄在下面"

M_B_old = (
    "    本轮（Plan 02 Task 1 fix round 1）**复跑**了它：``.db`` 字节与两条查询计划**逐字复现**\n"
    "    （5 423 104 / 6 791 168 / +1 368 064 B / +25.23%），但**墙钟中位不复现**——同一个脚本\n"
)
M_B_new = (
    "    本轮（Plan 02 Task 1 fix round 1）**复跑**了它：``.db`` 字节**逐字复现**（5 423 104 /\n"
    "    6 791 168 / +1 368 064 B / +25.23%）；两条查询计划是**尾部逐字复现**——上表最后一列只印\n"
    "    了 ``USING COVERING INDEX …`` 那一段，而 ``EXPLAIN QUERY PLAN`` 的 detail **全串**其实\n"
    "    以 ``SEARCH stratification_result `` 开头（fix round 5 亲跑，两个场景的 detail 全串::\n"
    "\n"
    "        A  SEARCH stratification_result USING COVERING INDEX sqlite_autoindex_stratification_result_1 (student_id=?)\n"
    "        B  SEARCH stratification_result USING COVERING INDEX ix_stratification_result_student_computed (student_id=?)\n"
    "\n"
    "    「逐字」是个强断言，不能用在截断过的引文上）。但**墙钟中位不复现**——同一个脚本\n"
)
M_B_absent = "``.db`` 字节与两条查询计划**逐字复现**"

M_C_old = "    复现脚本（完整内容，本轮亲跑验证过；``#`` 注释处原本是脚本自己的 docstring，为了不与\n"
M_C_new = "    复现脚本（完整内容，fix round 1 亲跑验证过；``#`` 注释处原本是脚本自己的 docstring，为了不与\n"
M_C_absent = "复现脚本（完整内容，本轮亲跑验证过"

MOD_EDITS = [
    ("M-A Minor3 :609 绑轮次", M_A_old, M_A_new, M_A_absent),
    ("M-B Minor4 「逐字」用在截断引文上", M_B_old, M_B_new, M_B_absent),
    ("M-C Minor3 :618 绑轮次", M_C_old, M_C_new, M_C_absent),
]

# ==========================================================================
# daily.py —— 只动 Minor 5 那两个散文标签（都在 docstring 里）
# ==========================================================================
D_A_old = (
    "    基线 **20.48 / 20.85 s**（均值 20.66、组内极差 20.85 − 20.48 = 0.37 s；两个样本\n"
    "    各自只记到百分位，故极差也只能给到这个精度），本 Task 之后\n"
    "    **20.89 / 21.18 s**（均值 21.03、组内极差 0.29 s）→ 差 **+0.37 s = +1.8%**，与两组\n"
)
D_A_new = (
    "    基线 **20.48 / 20.85 s**（均值 20.66，**截断到百分位**：真值 20.665，``round(_, 2)``\n"
    "    同为 20.66；组内极差 20.85 − 20.48 = 0.37 s；两个样本\n"
    "    各自只记到百分位，故极差也只能给到这个精度），本 Task 之后\n"
    "    **20.89 / 21.18 s**（均值 21.03，**截断到百分位**：真值 21.035，``round(_, 2)`` 会给\n"
    "    21.04，故这两个「均值」都不是 ``round()`` 出来的；组内极差 0.29 s）→ 差\n"
    "    **+0.37 s = +1.8%**，与两组\n"
)
D_A_absent = "（均值 20.66、组内极差"

DAI_EDITS = [("D-A Minor5 两个均值标截断口径", D_A_old, D_A_new, D_A_absent)]


def apply(path, edits):
    raw = path.read_bytes().decode("utf-8")
    n_crlf = raw.count("\r\n")
    n_lf = raw.count("\n")
    assert n_crlf == n_lf, (path, n_crlf, n_lf)
    t = raw.replace("\r\n", "\n")
    print("### %s  (%d 处编辑)" % (path.name, len(edits)))
    for name, old, new, absent in edits:
        c = t.count(old)
        assert c == 1, "%s: %s old 命中 %d 次（应为 1）" % (path.name, name, c)
        t = t.replace(old, new, 1)
        assert t.count(new) >= 1, "%s: %s 新串没进去" % (path.name, name)
        assert t.count(absent) == 0, "%s: %s 旧标记仍在（%d 处）" % (path.name, name, t.count(absent))
        print("   OK  %s" % name)
    out = t.replace("\n", "\r\n").encode("utf-8")
    path.write_bytes(out)
    back = path.read_bytes()
    print("   落盘后 sha256[:16] %s -> %s ; bytes %d -> %d ; CRLF %d -> %d"
          % (BEFORE[path][:16], hashlib.sha256(back).hexdigest()[:16],
             len(raw.encode("utf-8")), len(back), n_crlf, back.count(b"\r\n")))
    assert back.decode("utf-8").count("\r\n") == back.count(b"\r\n".decode())
    return back


for p, e in ((PUR, PUR_EDITS), (LAY, LAY_EDITS), (MOD, MOD_EDITS), (DAI, DAI_EDITS)):
    apply(p, e)

# ------------------------------------------------------- 全文件双向闸门（再查一遍）
print()
print("=== 落盘闸门（磁盘读回，双向查）===")
ALL = [(PUR, PUR_EDITS), (LAY, LAY_EDITS), (MOD, MOD_EDITS), (DAI, DAI_EDITS)]
ok = True
for p, edits in ALL:
    t = p.read_bytes().decode("utf-8").replace("\r\n", "\n")
    for name, old, new, absent in edits:
        in_new = t.count(new)
        in_abs = t.count(absent)
        flag = "OK " if (in_new >= 1 and in_abs == 0) else "FAIL"
        if flag == "FAIL":
            ok = False
        print("  %s %-34s %-24s 新串=%d 旧标记=%d" % (flag, p.name, name, in_new, in_abs))
print()
print("闸门结论:", "PASS" if ok else "FAIL")
print("残留「本轮」计数（应为 daily.py 1 处 + test_models.py 1 处已绑轮次那处）:")
for p in (PUR, LAY, MOD, DAI):
    t = p.read_bytes().decode("utf-8").replace("\r\n", "\n").splitlines()
    hits = [(i + 1, l.strip()) for i, l in enumerate(t) if "本轮" in l]
    print("  %-24s %d 处" % (p.name, len(hits)))
    for ln, l in hits:
        print("      :%-4d %s" % (ln, l[:110]))
sys.exit(0 if ok else 1)

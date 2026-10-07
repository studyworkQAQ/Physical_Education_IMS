# Task 1 fix 链结案评审（`ad1d190..6784d57`）

> 评审者：任务评审者（read-only）。评审对象是**四轮 fix**（`6a2938f` / `1fa9941` / `be0f1af` / `6784d57`），
> Task 1 主体 `1df5e8a` 不在范围内（已由 `task-1-review-package.md` 评审过）。
> 全部行号一律 **shell 口径**（python `enumerate` 读字节），绑定 **HEAD = `ef48d33`**（代码基线 `6784d57`）。
> 取证脚本 12 个在 `.superpowers/sdd/review_probes/`（`p1.py`–`p20.py` + `dump.py`/`grep.py`），gitignore、可一键重跑。
> **主工作树一个字节都没动**：两个守卫文件的 sha256 在全部变异实验前后逐字相同（见 §6）。

---

## 1. Spec 合规

### 1.1 计划文档 Task 1 全节（`Document/2026-10-06-实施计划02-智能处方引擎.md:73-161`）

fix 链不改 Task 1 的产出物，只改散文与守卫口径，故 Step 1–8 的验收状态沿用主体评审 + 本轮实测：

| 判据 | 本轮实测命令 | 结果 |
|---|---|---|
| Step 6 全量 PASS | `cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing` | **480 passed, 1 skipped in 225.45s**（= 481 collected；那 1 条 skip 是 `test_backfill.py:182` 的 trace-hook 自觉跳过，既有行为）✓ |
| Step 6 domain 分支覆盖 100% | 同上 | **TOTAL 399 stmts / Miss 0 / 114 branch / BrPart 0 / 100%**，逐格与账本 `:455`/`:535`/`:624` 相符 ✓ |
| 架构守卫单跑 | `cd backend; python -m pytest tests/architecture -q` | **6 passed in 0.19s**（purity 4 + layering 2）✓ |
| Step 7 变异验收（fix 链新增的两个守卫点） | 见 §4 变异表 | **9 相位全部与源码/账本陈述一致** ✓ |
| Step 4 第 1 项（索引作废的替代处置） | `test_models.py:581-721` | 守查询计划 + 两条 UC 列序，未建具名 `Index` ✓ |

### 1.2 Global Constraints 十条（`:19-28`，实测顶层 bullet = **10**，Ruling 53 的更正成立）

| # | 约束 | 状态 |
|---|---|---|
| 1 | `app/domain/` 无任何 I/O | ✓ 三条守卫全绿；allow-list 已从 deny-list 改写并把相对导入折算进白名单 |
| 2 | `app/domain/` 分支覆盖 100%（带 `--cov-branch`） | ✓ 399/0/114/0/100% |
| 3 | 单一所有者 | ✓ `DEFAULT_CSV_DIR`/`DEFAULT_DB_URL`/`BACKEND_DIR` 唯一住址是 `app/config.py`；fix 链没有新开所有者 |
| 4 | 断言两侧不得同源（#35） | ✓ `tests/test_config.py` 两条断言的右侧是字面量；两份 `test_absolute_folding_matches_resolve_name` 的判据锚在 `importlib.util.resolve_name`，**一个折算结果都没写死**（我逐格核过 `cases`，11 格里只有「期望颜色」是字面量，那是判据不是折算值） |
| 5 | 散文必须带口径（#19/#20/#25/#29/#36/#39/#43） | ⚠️ **大体做到，两处不合格**：见 I-2（配方复现不出表）与 M-2/M-3（数字与「本轮」无 commit/轮次绑定） |
| 6 | 行号一律 shell 口径（#30/#37） | ✓ 我抽验的每一处 `文件:行` 引文都命中（见 §3.3） |
| 7 | PowerShell 纪律 | ✓ 未违反；本次评审全程 python 落盘 |
| 8 | 落盘唯一权威是 shell；不得 `git checkout`/`git switch`/`git merge` | ✓ 我一次都没用；基线内容全部用 `git show` / `git archive` 取到内存或 `$env:TEMP` |
| 9 | 禁区 | ✓ `backend/pe.db` 不存在；`backend/data/seed/` **0 文件**；`national_standard_2014.csv` = **21412 B / `D2C8E539E2FA0029` / CRLF 0** |
| 10 | `app/seed/` 重新冻结 | ✓ `git diff --name-only ad1d190..6784d57 -- backend/app/seed backend/data .gitattributes` = **空** |

**Spec 合规判定：✅**（第 5 条的两处不合格已作为 finding 列出，不构成对 spec 的偏离，只构成对项目自身口径纪律的偏离。）

---

## 2. 结论

# **Approved with findings**

**Critical 0 / Important 2 / Minor 6。**

四轮 fix **确实闭合了它们声称闭合的每一条 finding**（§5 逐条核对，0 条被静默丢掉；只有 1 条实现者关切
`C-fr1-4` 在账本里没有处置行，而它本身不需要动作）。**两个守卫今天都是有牙的、不是假绿的**——我独立重建
合成树、独立跑 9 相位变异、独立在两个历史基线上复跑全量，全部与源码/账本陈述相符。

**但本项目唯一反复出现的错误类（印在源码里的陈述与实测不符）又出现了 2 次**，且都在 fix round 2/3 新写的
`+` 行里：一条把 Task 2 的 AST 形状的 `level` 归错了（I-1），一条印的合成树配方漏了两个必要条件、照字面做
复现不出它自己那张表（I-2，而漏的正好是硬规矩 #53 立规矩时要防的那两件事）。两条都**不影响守卫的判定**，
都是散文/取证口径缺陷，故判 Approved with findings 而不是 Needs work。

---

## 3. Findings

### 3.1 Critical（0 条）

无。我专门按「让一条守卫失效」这个角度做了三组攻击性复核，全部守住了：

| 攻击 | 命令 | 结果 |
|---|---|---|
| 删掉越界守卫（两份都删）在**基线 `1fa9941`** 上 | `git archive 1fa9941 backend` → temp → 变异 → `pytest -q` | **479 passed, rc 0**（= 源码 `purity:210`/`layering:198` 印的「479 条全绿」，改前口子是真的）；同一变异在 HEAD 上 **`2 failed, 479 passed`** |
| `parts[:-1]` → `parts`（两份都改）在**基线 `be0f1af`** 上 | `git archive be0f1af backend` → temp → 变异 → `pytest -q` | **481 passed, rc 0**（= `purity:360`/`layering:346` 印的「全量测试都照样通过」，改前口子是真的）；同一变异在 HEAD 上 **`2 failed`** |
| 只变异一份 | 见 §4 表 | **1 failed, 1 passed** ×6 相位，两份互相独立 ✓ |

### 3.2 Important（2 条）

---

#### I-1 `backend/tests/architecture/test_domain_purity.py:230-232` —— 把 Task 2 那个形状的 `level` 归错了，而且那一格在 purity 的矩阵里根本不存在

**原文**（shell 口径，HEAD）::

```
   230|     **绿档同时在场**（硬规矩 #50：只放红档会得到一条过紧的守卫）：``level == 1`` 的包内导入
   231|     折成 ``app.domain.tables``，必须仍被 :func:`_is_allowed` 放行——Task 2 起
   232|     ``app/domain/prescription/`` 子包里的 ``from ..indicators import X`` 正是这一档。
```

**实测命令与输出**（`review_probes/p14.py`）::

```
=== 1. `from ..indicators import X` 的 AST 形状 ===
  ImportFrom(level=2, module='indicators', names=['X'])
  -> level = 2（**不是 1**）；点是 2 个

=== 2. 它在 Task 2 的形状（app/domain/prescription/x.py，包深 3）下折算成什么 ===
  _package_of(app/domain/prescription/x.py) = ('app', 'domain', 'prescription')
  purity ._absolute('indicators', 2, ('app', 'domain', 'prescription')) = 'app.domain.indicators'
  resolve_name('..indicators', 'app.domain.prescription') = 'app.domain.indicators'
  purity ._is_allowed('app.domain.indicators') = True -> GREEN
  layering._is_forbidden('app.domain.indicators') = False -> GREEN

=== 3. 而 docstring 说的那一档（level == 1）是什么形状 ===
  purity 矩阵第 2 行 ('tables', 1, ('app','domain')) -> 'app.domain.tables'  _is_allowed=True
  对应写法是 `from .tables import X`（**一个点**），源文件在 app/domain/ 下（包深 2）
  而 Task 2 的 prescription/match.py 里写 `from .indicators import X` 会折成 'app.domain.prescription.indicators'

=== 4. 两份矩阵的绿档清点（AST 形状）===
  purity: 11 格 ; RED 9 格 / GREEN 2 格
     绿档第 2 行: module='tables' level=1 package=('app','domain') name=''  (包深 2)
     绿档第 3 行: module='' level=1 package=('app','domain') name='tables'  (包深 2)
     包深 3 的行: [7, 9]，其颜色: ['RED', 'RED']
  layering: 11 格 ; RED 8 格 / GREEN 3 格
     绿档第 2/3 行: level=1 package=('app','db','models')  (包深 3)
     绿档第 7 行: level=2 package=('app','db','models') name='seed'  (包深 3)

=== 5. Task 2 形状（包深 3 + level 2 + 合法目标）在 purity 矩阵里有没有 ===
  purity 矩阵里 (包深3, level2, GREEN) 的格数 = 0 []
  layering 矩阵里 (包深3, level2, GREEN) 的格数 = 1 [('', 2, ('app','db','models'), 'seed', 'GREEN')]
```

**为什么是 Important**

1. **印在源码里的 `level` 归错**，而且与账本自己的裁定相反：账本 `:282`（Ruling 28）写的是
   「Task 2 会在 `app/domain/prescription/` 下建子包，那里 `from ..indicators import X` 的
   **`level == 2`** 解析到 `app.domain.indicators`——完全合法」。同一件事，账本说 level 2、源码说 level 1。
2. **硬规矩 #50 的第 ② 项（「绿档要取自计划的下一个 Task」）在 purity 这一份只是名义上满足**：
   矩阵里 `(包深 3, level 2, GREEN)` 的格数 = **0**。Task 2 真建成后，`app/domain/prescription/` 里
   level-2 的合法导入在这条回归测试里**没有格子看着**。
3. 这正是硬规矩 #56 要防的形态的**镜像**：同一句话被写进两个文件，而它只在一个文件里成立
   （`layering:218-220` 的对应句说的是真仓 12 条 level-1 导入，**是对的**）。

**不是 Critical 的理由（我自己核过，守卫没被削弱）**：矩阵的两个 level-1 绿档格足以抓住
`anchor = package[: len(package) - (level - 1)]` 的任何 off-by-one（把 `- (level - 1)` 写成 `- level`，
`('tables', 1, ('app','domain'))` 会折成 `app.tables` ≠ `resolve_name('.tables','app.domain')`
= `app.domain.tables` → 当场红）。而 Task 2 的形状我另跑过，**在 HEAD 的 `_absolute`/`_is_allowed` 下确实是
GREEN**（上面 §2 的实跑），即守卫本身对 Task 2 是正确的，只是这条**回归测试**没有把它钉住、而 docstring 说钉住了。

**建议修法**（两处，都在 `test_domain_purity.py`，layering 那份不要跟着改）

* `:230-232` 改成::

  ```
  **绿档同时在场**（硬规矩 #50：只放红档会得到一条过紧的守卫）：``level == 1`` 的包内导入
  （``app/domain/x.py`` 里的 ``from .tables import X``）折成 ``app.domain.tables``，必须仍被
  :func:`_is_allowed` 放行。⚠️ Task 2 起 ``app/domain/prescription/`` 子包里的
  ``from ..indicators import X`` 是 **``level == 2``、包深 3**（不是 level 1），折成
  ``app.domain.indicators``、同样必须放行（本机 Python 3.11.1 实跑
  ``resolve_name("..indicators", "app.domain.prescription")`` -> ``'app.domain.indicators'``）；
  这一格在下面的 ``cases`` 里是**最后一行**。
  ```

* 往 `cases` 末尾加一行（`:249-250` 自己就写了「往 ``cases`` 里加一行就是加一格覆盖，不必动断言」）::

  ```
  # Task 2 的形状：包深 3 + level 2 + 合法目标（硬规矩 #50 的 ②，取自下一个 Task）
  ("indicators", 2, ("app", "domain", "prescription"), "", "GREEN"),
  ```

  加完矩阵变 12 格，`:245`/`:249`/`:314` 与 `layering:232`/`:236`/`:300` 的「**11 格**」计数要跟着改
  （purity 改 12，layering 仍是 11——**两份从此不同**，按 #56 各自标主语）。

---

#### I-2 `backend/tests/architecture/test_domain_purity.py:523-525` —— 印的合成树配方漏了两个必要条件，照字面做**复现不出**它自己那张 14 行表；漏的正是硬规矩 #53 要防的那两件事

**原文**::

```
   523|     :func:`_dotted` 只还原调用表达式自身、代码里没有任何赋值追踪）。下面是合成树上的实测
   524|     口径：把 ``DOMAIN`` 指到 ``$env:TEMP`` 下一棵只有 ``app/domain/`` 的合成树，逐条写进
   525|     一个探针文件后分别调用三条守卫（本轮亲跑）::
```

**实测命令与输出**

*(a) 照字面只重定向 `DOMAIN`（`review_probes/p18.py`）*::

```
BACKEND = C:\...\Physical_Education_IMS\backend      <- 没跟着改
DOMAIN  = C:\...\Temp\pe_p18_n3s74rq4\app\domain
  G1 抛 ValueError: 'C:\...\Temp\pe_p18_n3s74rq4\app\domain\filler0.py' is not in the subpath of
  G2 GREEN
  G3 RED(AssertionError) <- probe.py:os.listdir

补上 P.BACKEND = 合成树根 之后：
  G1 RED(AssertionError) <- probe.py:1: os
  G2 GREEN
  G3 RED(AssertionError) <- probe.py:os.listdir
```

G1 抛的是 **`ValueError`（`_package_of` 的 `relative_to(BACKEND)`）**，不是一个颜色判定。这与账本
`:512`（控制者错误 #71）**逐字同型**——「第一版 harness 只重定向了 `DOMAIN`、没重定向 `BACKEND`，
于是 `_package_of` 的 `relative_to(BACKEND)` 抛 `ValueError`，14 行探针全部 RED」。硬规矩 #53 就是为它立的。

*(b) 两个都重定向、但树里只有 1 个探针文件（`review_probes/p17.py` 配方 A）*::

```
=== 配方 A（DOMAIN 下只有 1 个探针文件，逐字照 purity:524-525 做）===
  对照 VALUE = 1                   G1 RED(空转守卫) | G2 RED(空转守卫) | G3 RED(空转守卫)
  open('x')                      G1 RED(空转守卫) | G2 RED(空转守卫) | G3 RED(空转守卫)
  __import__("os").listdir(".")  G1 RED(空转守卫) | G2 RED(空转守卫) | G3 RED(空转守卫)
```

`_assert_not_empty` 的 `len(scanned) >= 5` 会先炸，**连「已知 GREEN 的对照行」都一起 RED**——
即硬规矩 #53 说的「『全红』和『harness 坏了』不可区分」。

*(c) 两个条件都补上（5 个干净 filler + probe），14 行全部重跑（`review_probes/p2.py`）*::

```
probe.py 的内容                                         G1     G2     G3       期望 / 判定
control: VALUE = 1 (已知 GREEN 对照)                     GREEN  GREEN  GREEN    OK
1  _f = open; _f('x')                                GREEN  GREEN  GREEN    OK
2  def reopen(): ... 然后 reopen()                     GREEN  GREEN  GREEN    OK
3  def open_ended(): ... 然后 open_ended()             GREEN  GREEN  GREEN    OK
4  只有 docstring:「不要用 datetime.now()，也不要 open(」       GREEN  GREEN  GREEN    OK
5  open('x')                                         GREEN  RED    GREEN    OK
6  import builtins; builtins.open('x')               RED    RED    GREEN    OK
7  import datetime as dt; dt.datetime.now()           RED    RED    GREEN    OK
8  __import__("datetime").datetime.now()             GREEN  GREEN  GREEN    OK
9  __import__("os").listdir(".")                     GREEN  GREEN  GREEN    OK
10 __import__("builtins").open("x")                  GREEN  GREEN  GREEN    OK
11 getattr(__import__("datetime"), "datetime").now() GREEN  GREEN  GREEN    OK
12 eval("__import__('datetime').datetime.now()")     GREEN  GREEN  GREEN    OK
13 def _f(x): return getattr(x, "now")()             GREEN  GREEN  GREEN    OK
14 def _f(table): return table[0]()                  GREEN  GREEN  GREEN    OK

不符行数 = 0

=== 附：FORBIDDEN_IO 子串命中数（purity:573-574）===
  __import__("os").listdir(".")      命中 0 个: []
  对照组 import os / os.listdir         命中 2 个: ['import os', 'os.listdir']
```

**即：那张表的 14×3 = 42 格颜色我全部独立复现、逐字相符；`:573-574` 的 0 vs 2 也复现。
不合格的是印在源码里的那份「怎么跑」，不是跑出来的结论。**

**旁证：两个文件的配方不一致。** `layering:145-146` 写的是::

```
   145|     合成树实测（把 ``BACKEND`` / ``APP`` 指到 ``$env:TEMP`` 下一棵形状与 ``backend/app``
   146|     相同的树，逐条写进探针文件后直接调用本测试函数）：上述两种写法**改前全绿**、改后全红。
```

**它把 `BACKEND` 写进去了**（虽然也漏了「≥8 个 `.py`」——我实测每目录只放 1 个探针时
`test_production_layers_never_import_app_seed` 报 `只扫到 1 个 .py，目录可能被搬空`，补足 filler 后才给出
真实判定 `app/pipeline/probe.py:1: app.seed`）。

**建议修法**：`purity:524-525` 补成::

```
口径：把 ``DOMAIN`` **与 ``BACKEND``** 指到 ``$env:TEMP`` 下同一棵合成树（``BACKEND`` 不跟着改，
:func:`_package_of` 的 ``relative_to`` 会抛 ``ValueError``、G1 全线不是红而是**崩**），树里除探针外
还要有 **≥5 个干净 ``.py``**（否则 ``len(scanned) >= 5`` 的空转守卫会让 14 行连同对照行一起 RED，
「全红」与「harness 坏了」不可区分——硬规矩 #53），逐条写进一个探针文件后分别调用三条守卫
（fix round 2 亲跑）::
```

`layering:145-146` 同理补一句「树里三个被扫目录合计需 **≥8 个 `.py`**」。

---

### 3.3 Minor（6 条）

---

#### M-1 `test_domain_purity.py:209` / `test_layering.py:197` —— 说「两个 bug」，底下列了三个 bullet，同段又说「三条」「三种」

**原文**（purity，layering `:197-207` 逐字同文）::

```
   209|     **守的是 fix round 2 修掉、而此前仓库里没有任何断言看着的两个 bug**（Plan02 Ruling 46：
   ...
   212|     * **越界档**：...
   215|     * **``module`` 为空时接 ``node.names`` 里的那个名字**：...
   218|     * **一个节点带 N 个名字要展开成 N 条**...
   221|     三条的复现命令是同一条（在 ``backend/`` 下）...
   222|     本轮实测三种变异各让**本文件这一条**红...
```

**实测**（`review_probes/p16.py` §3）::

```
  test_domain_purity.py    '两个 bug' 命中 1 次 ; '三条的复现命令' 命中 1 次 ; '三种变异' 命中 1 次
  test_layering.py         '两个 bug' 命中 1 次 ; '三条的复现命令' 命中 1 次 ; '三种变异' 命中 1 次
```

三个 bullet = Ruling 35 的一个 + Ruling 36 的两个形状（「接名字」与「逐个展开」），故「两个 bug」在
**Ruling 计数**口径下可辩；但读者会去数 bullet。**这与 Ruling 55（「三条守卫」vs 4 个 `test_*`）同类**，
而 Ruling 55 是被接受并修掉的。建议改成「两个 bug（Ruling 35 的一个 + Ruling 36 的两个形状，共三档变异）」，
或直接统一写「三档」。

---

#### M-2 `test_domain_purity.py:210` / `test_layering.py:198` —— 「479 条全绿」没有 commit 绑定，在 HEAD 上照字面跑是 `479 passed, 2 failed`

**原文**::

```
   210|     谁删掉 ``if level - 1 > len(package): return None``，479 条全绿）：
```

**实测**（`review_probes/p10.py`）::

```
=== (a) 基线 1fa9941：删掉越界守卫（两份都删），跑全量 ===
  变异后 exit=0  末行=479 passed in 113.73s   （源码陈述：479 条全绿）
  不变异的基线   exit=0  末行=479 passed in 110.82s
```

**陈述在其基线 `1fa9941` 上精确为真**（我复跑到了）。但源码没写基线，而 HEAD 是 **481** 条：
今天照字面做同一变异会得到 **`2 failed, 479 passed in 55.48s`、exit 1**（我实跑过：`review_probes/p21.py`，在 `$env:TEMP` 的 backend 副本上两份都删掉那 3 行；红的正是本轮新加的那两条 `test_absolute_folding_matches_resolve_name`），「全绿」不成立。

**同一个文件里两种口径并存**：`:355-361` / `layering:341-348` 的断言消息**故意不写数字**——
「而在本段断言加上之前，这么改一次全量测试都照样通过」，实现者在报告 `:2750-2751` 明说
「消息末尾**不写死 481**（那个数会随后续 Task 漂）」。round 4 想到了，round 3 没想到。

按硬规矩 #19/#37（数字要能指到产生它的命令；引用要绑 commit）与 #39，建议改成
「基线 ``1fa9941``（fix round 3 之前）上全量 **479 passed、退出码 0**」，或照 `:360` 的写法去掉数字。

---

#### M-3 fix 链新增的散文里「本轮」出现 11 处，只有 1 处绑了轮次

**实测**（`review_probes/p16.py` §2）::

```
  test_domain_purity.py    4 处: [222, 392, 525, 544]   带轮次绑定的: 无
  test_layering.py         4 处: [150, 210, 371, 385]   带轮次绑定的: 无
  daily.py                 2 处: [206, 657]             带轮次绑定的: 无（:657 不在 fix 链改动面内）
  test_models.py           3 处: [609, 612, 618]        带轮次绑定的: [612]
  test_daily.py            1 处: [319]                  （不在 fix 链改动面内）
  test_config.py           0 处
```

入库文件里的「本轮」对下一个读者没有指代对象——这是 Ruling 27-M2 要消灭的
「指针解析不到任何东西」的**时间版**。减轻情节：多数地方附近给了可跑命令
（`layering:150-152`、`:371-373` 都印了完整命令，`:375-376` 还绑了 `e26347f` / `ad1d190`），
故只算措辞问题。**同仓已有正确样板**：`test_models.py:612`「本轮（Plan 02 Task 1 fix round 1）**复跑**了它」。
建议一律写成「fix round N」或绑 commit。

---

#### M-4 `backend/tests/db/test_models.py:612-613` —— 「两条查询计划**逐字复现**」，而表里印的计划不是逐字的

**原文**::

```
   612|     本轮（Plan 02 Task 1 fix round 1）**复跑**了它：``.db`` 字节与两条查询计划**逐字复现**
   613|     （5 423 104 / 6 791 168 / +1 368 064 B / +25.23%），但**墙钟中位不复现**——同一个脚本
```

而 `:596-597` 的表格里印的是 `` ``USING COVERING INDEX sqlite_autoindex_stratification_result_1 (student_id=?)`` ``。

**实测**（`review_probes/p13.py`：用 `ast.get_docstring(fn, clean=False)` 把脚本从 docstring 的字面块里
原样抽出来、落到 `$env:TEMP`、在**仓库根**跑 2 次，`exit = 0`）::

```
--- 第 1 次跑 ---
  A  median=0.2638 ms  min=0.1166  max=1.7504  .db=5423104 B
     plan: SEARCH stratification_result USING COVERING INDEX sqlite_autoindex_stratification_result_1 (student_id=?)
  B  median=0.2744 ms  min=0.1120  max=1.7259  .db=6791168 B
     plan: SEARCH stratification_result USING COVERING INDEX ix_stratification_result_student_computed (student_id=?)
  行数 500*112 = 56000   B/A = 1.040   .db +1368064 B = +25.23%
--- 第 2 次跑 ---
  A  median=0.1739 ms  min=0.1164  max=1.7367  .db=5423104 B
  B  median=0.7048 ms  min=0.1314  max=11.3388 .db=6791168 B
  行数 500*112 = 56000   B/A = 4.054   .db +1368064 B = +25.23%
```

* **`.db` 字节 / 差值 / 百分比 / 行数确实逐字复现**（`5 423 104` / `6 791 168` / `+1 368 064 B` / `+25.23%` / `56000`，两次都一样）✓
* **查询计划的真实 detail 前面还有 `SEARCH stratification_result `**，表里那两格只印了尾部——「逐字复现」对不上字面。
* 顺带贡献第 5、6 个独立墙钟样本：`B/A = 1.040` 与 **`4.054`**（后者单次 max 11.34 ms，机器被占用）。
  这**进一步支持** `:600`/`:613-616` 那句自我撤回是对的，不构成 finding。

**建议**：表格那两格补上 `SEARCH stratification_result ` 前缀（顺带把 `:593-598` 的 `====` 框线重新对齐，
那是账本 `:519` 已记的延后 Minor），或把「逐字复现」改成「``.db`` 字节逐字复现、查询计划的**索引名与前导列**逐字复现」。

---

#### M-5 `backend/app/pipeline/daily.py:226`/`:228` —— 两个「均值」是截断值，其中一个不等于 `round()` 的结果，而标签没写舍入口径

**原文**::

```
   226|     基线 **20.48 / 20.85 s**（均值 20.66、组内极差 20.85 − 20.48 = 0.37 s；两个样本
   228|     **20.89 / 21.18 s**（均值 21.03、组内极差 0.29 s）→ 差 **+0.37 s = +1.8%**，与两组
   230|     ``60 / 21.18 = 2.83×``（硬规矩 #42 的线是 2×）。
```

**实测**（`review_probes/p11.py` §5）::

```
  基线均值   = 20.665000  -> 源码写 20.66 ; round(20.665,2)=20.66 ; 截断=20.66
  本Task均值 = 21.035000  -> 源码写 21.03 ; round(21.035,2)=21.04 ; 截断=21.03
  基线组内极差 = 0.3700 (源码 0.37) ；本Task组内极差 = 0.2900 (源码 0.29)
  差 = 0.370000 s (源码 +0.37) ；百分比 = 1.7905% (源码 +1.8%)
  60 / 21.18 = 2.832861  (源码 2.83×)
```

两个都是**向下截断**、彼此自洽，`+0.37 s` / `+1.8%` / `2.83×` / 两个极差全部对得上，**不影响任何结论**。
只是「均值」这个标签没写舍入口径（硬规矩 #20：转写数字要连量纲/口径一起转写）。
建议写「均值 20.665 / 21.035（未舍入）」或注明「截断到百分位」。
⚠️ 这四个墙钟**样本值本身不可复核**，见 §7。

---

#### M-6 `test_domain_purity.py:146` —— 「**守卫当场假绿**」没标主语，而 layering 的对应句 `:93` 标了

**原文对照**::

```
purity  :145-146|     ``_is_allowed('app.domain.seed')`` -> ``True``）、命中白名单前缀 ``app.domain.`` →
           146|     **守卫当场假绿**
layering:  92-93|     也返回），``app/db/models/x.py`` 里的 ``from ...seed import …`` 就会折成 ``app.db.seed``、
              93|     **不再以 ``app.seed`` 开头** → 本守卫当场假绿（硬规矩 #52）。
```

两句各自只覆盖一个文件、机制也各自专属（purity 引 `_is_allowed` + `app/domain/x.py`；
layering 引 `app.seed` 前缀 + `app/db/models/x.py`），**故不构成硬规矩 #56 的「一句话覆盖两者」**，
两份的**结论我都实跑确认成立**（`review_probes/p1.py` §I）::

```
  purity: _package_of 变异后 app/domain/x.py 里 from ..seed import … 折成 'app.domain.seed'
          _is_allowed('app.domain.seed') = True   startswith('app.domain.') = True
  layering: 变异后 app/db/models/x.py 里 from ...seed import … 折成 'app.db.seed'
            _is_forbidden('app.db.seed') = False
```

只是措辞不对称：建议 purity 也写「**本文件的**守卫当场假绿」。

**§E 全量扫描结果（#56）**：我把两个文件里全部含 `GREEN|RED|假绿|真绿|绿|红|offender|合法` 的行逐条读过
（purity 约 60 行、layering 约 35 行），**除 `purity:146` 这一处外，全部带了主语**，其中做得最好的是
`purity:233-236` 与 `layering:220-223`（「矩阵第 7 行 …… 在**本文件**的白名单下是 RED、
在 `test_layering` 的 `app.seed` 前缀下却是 GREEN」）、`purity:356-360` 与 `layering:341-348`
（两份断言消息各写自己的后果 + 括注对方那一份）、`purity:417-424`（每条写法都带包深与文件名）。
`layering:300-301` / `purity:314-315` 的「**两条守卫共同的**假绿入口」我单独核过：
**对两个文件都成立**（上面的实跑），故这句合并陈述是合法的。

---

## 4. Section C —— 回归测试质量（逐条判据 + 我的独立变异）

| 判据 | 我的验法 | 结果 |
|---|---|---|
| 锚在 `importlib.util.resolve_name`、**没有一个折算结果被写死**（#35） | AST 抽两份 `cases` 逐格核；每格右侧是 `resolve_name("."*level + (module or name), ".".join(package))` 现场调用 | ✓ 11 格里字面量只有 `(module, level, package, name)` 这**四个 AST 形状入参**与**期望颜色**（判据），**折算值 0 个写死**；`level-1 == len(package)` 与越界两档的期望值是 `resolve_name` 抛 `ImportError` → `None`，也不是写死的 |
| 红档与绿档**同时在场**（#50） | 数 `cases` 的颜色列 | purity **RED 9 / GREEN 2**；layering **RED 8 / GREEN 3** ✓（⚠️ 账本 `:538` 只报了后者、没标主语 → 控制者错误 CE-3） |
| 「守不住什么」段仍然准确（round 4 必须已改掉「`_package_of` 不在守卫范围内」） | grep + 读 | ✓ **已改掉**：`purity:240-246` / `layering:227-233` 现在写的是「`_package_of` 由本测试**末尾那一段**看着（Plan02 Ruling 54），但**只在枚举到的那 4 个形状上**……**没枚举进去的包深（包深 4 及更深）不被覆盖**」。第二、三条边界（不扫真仓 / 矩阵有限）逐字未动 ✓。我核了这 4 个形状全部实跑为真（`p1.py` §H：`app/db/models/organisation.py` 与 `__init__.py` 同给 `('app','db','models')`、`app/domain/indicators.py` 给 `('app','domain')`、`app/domain/prescription/match.py` 给 `('app','domain','prescription')`——**磁盘上不存在也能断言**，因为 `_package_of` 是纯路径运算） |
| 两份**互相独立** | 9 相位变异，全部在 `$env:TEMP` 的 backend 副本上做，主工作树 sha256 前后逐字相同 | ✓ 见下表 |
| 两份 `_absolute` / `_package_of` 剥 docstring 后**逐字相同**（#51） | AST 抽函数、剥 docstring、`ast.dump` 比 | ✓ `_absolute`: args `['module','level','package','name']`、defaults 1、stmts 6、**identical = True**；`_package_of`: args `['py']`、defaults 0、stmts 1、**identical = True**。（`_is_allowed`/`_is_forbidden`/`_dotted`/`_hit_forbidden_call`/`_imported_modules` 只在一个文件里，**本来就该不同**） |
| 5 条既有守卫 `assert` 未被改 | AST 抽 4 条 `test_*`（守卫那 4 条）的全部 `assert`、`ast.unparse` 比基线 `ad1d190` | ✓ purity 3 条 + layering 2 条 = **5 条，文本集合相等 = True，逐条与基线逐字相同**；新测试各有 3 条 assert |

**我的独立变异表**（`review_probes/p9.py` + `p12.py`；每次变异都在**剥 docstring 后的 `ast.dump`** 上确认
「真的改了代码」，硬规矩 #53；只跑 `-k absolute` 那两条）：

| 相位 | 变异 | pytest 末行 | 红的是哪一份 | AST 上真的改了 |
|---|---|---|---|---|
| **M0** | 不变异（对照） | `2 passed, 4 deselected` | `[]` | — |
| **M1** | `package[: len(package) - (level - 1)]` → `package[: len(package) - level + 1]`（语义等价，两份都改） | `2 passed, 4 deselected` | `[]` ✓ **尺子不恒红** | True |
| **①** | 删掉 `if level - 1 > len(package): return None`（含注释，3 行）—— 只改 layering | `1 failed, 1 passed` | `['test_layering.py']` ✓ | True |
| **①** | 同上 —— 只改 purity | `1 failed, 1 passed` | `['test_domain_purity.py']` ✓ | True |
| **②** | `tail = module or name` → `tail = module` —— 只改 layering | `1 failed, 1 passed` | `['test_layering.py']` ✓ | True |
| **②** | 同上 —— 只改 purity | `1 failed, 1 passed` | `['test_domain_purity.py']` ✓ | True |
| **③** | `parts[:-1]` → `parts` —— 只改 layering | `1 failed, 1 passed` | `['test_layering.py']` ✓ | True |
| **③** | 同上 —— 只改 purity | `1 failed, 1 passed` | `['test_domain_purity.py']` ✓ | True |
| **③** | 同上 —— 两份都改 | `2 failed, 4 deselected` | 两份都红 ✓ | True |
| **④** | `_imported_modules` 改成只 yield `node.names[0]` —— 只改 purity | `1 failed, 1 passed` | `['test_domain_purity.py']` ✓ | True |
| **④** | 同上 —— 只改 layering | `1 failed, 1 passed` | `['test_layering.py']` ✓ | True |

**④ 的断言原文**（核 `purity:228` / `layering:216` 印的那句）::

```
E   AssertionError: 一名一条的展开失效: ['app.seed'] != ['app.seed', 'app.pipeline']
```

与源码印的 `['app.seed'] != ['app.seed', 'app.pipeline']` **逐字相符** ✓。
另外两档的断言原文也与 `purity:225-227` / `layering:213-215` 印的相符（越界档
`_absolute('domain', 4, ('app','domain'), 'tables') = 'app.domain'`、`tail = module` 档
`_absolute('', 2, ('app','pipeline'), 'seed') = 'app'`，我在 `p1.py` §D/§G 独立算出同值）。

**收工自证**（`p9.py`/`p12.py` 末尾实跑）::

```
  tests/architecture/test_domain_purity.py       440f7167610df187  UNCHANGED
  tests/architecture/test_layering.py            50d776680defc25e  UNCHANGED
```

这两个 sha256[:16] 与实现者报告 `:2643-2644`/`:2878-2879` 的收工值**逐字相符**，
即我拿到并归还的工作树就是 `6784d57` 的状态。

---

## 5. Section B —— 四轮 fix 的 finding 闭合逐条核对

### 5.1 任务评审（Ruling 23–27）：4 Important + 7 Minor → 派了 8 项

| finding | 处置 | 我在 diff / 磁盘上找到的对应改动 | 判定 |
|---|---|---|---|
| **I1**（R23）两条守卫对 `level >= 2` 无条件放行 + docstring 理由错 | 修（R28 接受了实现者对裁定的偏离） | 新增 `_package_of` + `_absolute`；`purity:451-459` 改成折算后走白名单；`layering:166-171` 同法；`purity:157-163` / `layering:133-146` 的错理由改成实测口径 | **CLOSED** ✓ 合成树端到端复跑（`p5.py`）：4 种绕过写法改前全绿、改后全红 |
| **I2**（R24）`purity:196-201` 虚报守卫能力（「顺着 `_dotted` 追赋值」） | 修 | `purity:521-523` 明写「**收益是『不再误报』，不是『多抓漏报』**——本节此前把方向写反了」；`purity:556-561` 补「别名间接不被守卫」 | **CLOSED** ✓ 基线 `ad1d190:199-201` 确有「就能顺着 ``_dotted`` 追到」；`_dotted` 代码里确实没有任何赋值追踪 |
| **I3**（R25）旧 deny-list 的历史陈述与基线源码相反 | 修 | `purity:368-393` 改成实测口径（6 项、无 `os`、三种写法基线全绿 + 控制组） | **CLOSED** ✓ 我用 `git show e26347f:` 落盘亲跑（`p4.py`）：`FORBIDDEN` 在**第 13 行**、**6 项**、**无 `os`**；`:38`/`:40`/`:41` 三处引文逐字相符；`from os import listdir` / `import numpy.random` / `import app.refdata` 三条守卫全绿；控制组 `import sqlalchemy`→G1 RED、`import os`→G3 RED、`os.listdir('x')`→G3 RED |
| **I4**（R26）`min` 折叠的语义方向写反 | 修 | `daily.py:199-217` 与 `test_daily.py:641-650` 两处同改 | **CLOSED** ✓ 我独立重建了那个实验（`p7.py`）：`test_date=09-01` → `09-01=Y … 09-05=Y`、首次 `as_of=09-01`；`test_date=09-05` → `09-01=n … 09-05=Y`、首次 `as_of=09-05`——**与 `daily.py:211-212` 印的两行逐字相符**；`percentile_stage.py:133`/`:176` 两处引文逐字命中 |
| **M1**（R27）`config.py` 说 `DEFAULT_CSV_DIR` 是构造函数的缺省值 | 修 | `config.py:35-46` | **CLOSED** ✓ `factory.py:50` 与 `mock_lepao.py:428` 两处引文逐字命中；`MockLePaoAdapter()` 实跑 `TypeError: ... missing 1 required positional argument: 'seed_dir'` ✓ |
| **M2**（R27）出处指向不入库的文件 | 修 | `daily.py:223-232` 写全墙钟口径；`layering:371-381` 写全 Counter 命令 + `git ls-tree` 交叉核对 | **CLOSED（部分）** ⚠️ 命令写全了、`e26347f`/`ad1d190` 也绑了，但**复现脚本仍不在库内**（源码自己承认：`daily.py:231-232`），四个墙钟数只能标「历史实测，不被守卫」——它标了 ✓。见 §7 不可复核 |
| **M3**（R27）A/B 实测块缺「不被守卫」标签 | 修 | `test_models.py:607-610` + `:618-695` 把复现脚本整段抄进 docstring | **CLOSED** ✓ 我用 AST 抽出来跑通了（`p13.py`，exit 0），**这才是这个处置的真正验收方式** |
| **M4**（R27）实现者报告的 `.py` 总数 21 应为 24 | 账本更正 | — | **CLOSED** ✓ 我独立数：`e26347f` = `db 4 / domain 6 / pipeline 7` = **17**；`ad1d190` 与 `6784d57` = `db 11 / domain 6 / pipeline 7` = **24**，与 `layering:375-376` 逐字相符 |
| **M5**（R27）CLI 没有「schema 改了要重建库」提示 | 转延后 Minor | 账本 `:269` | ✓ 有理由（失效形态是响亮的 `OperationalError`，`pe.db` 不入库），理由成立 |
| **M6**（R27）计划 Task 10 的 `error_summary` 陈述 | 控制者自己改计划正文 | — | ✓ 不在 fix 链范围 |
| **M7**（R27）`app/config.py` 三个值缺非同源测试 | 本轮做 | **新建** `backend/tests/test_config.py`（30 行） | **CLOSED** ✓ 两条断言右侧是字面量（`"data/seed"` / `"/backend/pe.db"`），实跑都为真；docstring 里 4 处引文我逐条核过（`test_factory.py:32`、`git grep DEFAULT_DB_URL -- backend/tests @ad1d190` = **2 条命中、都在 `test_layering.py:22-23`**、`refdata.py:23`、`test_refdata.py:82-83`/`:187` + `D2C8E539E2FA0029`）**全部命中** |
| 附带（`organisation.py:69`） | 转延后 Minor | 账本 `:268` | ✓ 理由成立（Plan 01 遗产、非本 Task 引入） |

### 5.2 fix round 1 复审（Ruling 35–40）：4 Important + 5 Minor

| finding | 处置 | 落地证据 | 判定 |
|---|---|---|---|
| **R35** 负数切片假绿 | 修 | 两份都加 `if level - 1 > len(package): return None`（`purity:183-185` / `layering:120-122`） | **CLOSED** ✓ 我算出并实跑：无守卫时 `('domain',4,('app','domain'),'tables')` → `'app.domain'`、`('seed',5,('app','db','models'),'generate')` → `'app.db.seed'`；`resolve_name` 对同一输入抛 `ImportError`；带守卫时两份都返回 `None` |
| **R36** 只看 `module` 不看 `names` | 修 | `tail = module or name` + `_imported_modules` 按 `names` 逐个 yield | **CLOSED** ✓ 相位 ②/④ 各自单独变红；真仓形状 `app/db/models/__init__.py:74` = `from . import feedback, prescription  # noqa: F401` 命中，且它是我数出的 12 条里**唯一**一条 `module is None`，位置正好是命令输出的**第 7 行**（`layering:154-156` 逐字相符） |
| **R37** 两个 `resolve_name` 举例是假的 | 修 | `purity:133-147` / `layering:84-93`，并把错的版本作为带标注的反例保留 | **CLOSED** ✓ 6 个 `resolve_name` 值我全部实跑逐字相符；`_absolute("seed",2,("app","domain","ind"))` = `'app.domain.seed'`（**不是** `app.domain.seed.generate`，Ruling 63 的更正成立）、`_is_allowed` = `True` |
| **R38** `__import__` 绕过 + 「唯一途径是 import」是假的 | 修（不按基线遗留降级） | `purity:483-492`（`_dotted`）+ `:563-579`（表第 8–14 行） | **CLOSED** ✓ 基线 `ad1d190:166-167` 确有「拿到它的唯一途径是 import」；7 行新增探针我全部实跑为 G/G/G；`FORBIDDEN_IO` 命中数 `0` vs `2` 亦复现 |
| **Minor 1** `13…17` 上界错 | 修 | `layering:383-385` → `13…18`，并写出三个减式 | **CLOSED** ✓ 我跑 `layering:373` 那条 Counter 命令：`24−11=13`、`24−7=17`、`24−6=18` |
| **Minor 2** `test_models.py:600` 撤回不在就地 | 修 | `:594` 表头标签 +`:600-602` 就地补 ⚠️ | **CLOSED** ✓ **两个点值一个没删**（`0.2708`/`0.2941` 仍在 `:596`/`:597`），撤回与指针就在同一句里 |
| **Minor 3** `purity:197-199` 主语与结论深度不匹配 | 修 | `purity:417-424` 分成「**扁平的** `app/domain/x.py`（包深 2）」与「`app/domain/sub/x.py`（包深 3）」 | **CLOSED** ✓ 合成树端到端（`p5.py`）：扁平档 `from ..seed`/`from ...seed` 都 RED；`sub` 档 `from ..tables` GREEN、`from ..seed` GREEN（折成 `app.domain.seed`）、`from ...seed` RED——**四格与 `:417-424` 逐字相符** |
| **Minor 4** `daily.py:226` 极差 0.38 推不出 | 修 | `:226` 改成「组内极差 20.85 − 20.48 = 0.37 s；两个样本各自只记到百分位……」 | **CLOSED** ✓ 算式我核过（见 M-5） |
| **Minor 5** `FORBIDDEN` 排成两行的 `::` 块 | 不修，转延后 Minor（账本 `:406`） | — | ✓ 理由成立：我核过基线**第 13 行**是单行、六项与顺序与 docstring 逐字相同，只是折行 → 无事实错误，纯排版 |
| **R40 范围外观察 5 条** | 1 条维持延后、1 条维持 R33 + 记更正、1 条并入 R38、1 条不修（#42 自觉结果）、1 条不修（M7 的必然代价） | 账本 `:396-401` | ✓ 五条全有处置、理由都成立 |

### 5.3 fix round 2（Ruling 41–47）

| 项 | 处置 | 判定 |
|---|---|---|
| **R41**（控制者 #67）「三种形状全部假绿」错 | 派单判据校正 | ✓ 我独立复跑那张 6 行表（`p1.py` §F/§G、`p5.py`）：`from .. import seed` 在 `app/pipeline`、`app/db`、`app/domain` 三处修后 RED，在 `app/db/models` 处**修前修后都 GREEN、只有折算串从 `app.db` 变成 `app.db.seed`**——Ruling 41 的更正成立 |
| **R42**（控制者 #68）`_is_allowed("app.domain")` 命中的是「相等」支 | 进 fix round 3 | ✓ 见 5.4 |
| **R43/R44**（控制者 #69/#70） | 记错误、无需返工 | ✓ |
| **R45** 实现者第 4 条不成立 | 不接受为控制者错误 | ✓ 判得对：派单给的字面形状 `from .....seed import generate` 的 AST 就是 `module="seed"`，故「折成 `app.db.seed`」精确正确（我实跑确认） |
| **R46** 两个 bug 没有回归测试 | 进 fix round 3 | ✓ 见 5.4；我另在**基线 `1fa9941`** 上复跑确认改前口子是真的（479 passed / rc 0） |
| **R47**（C-fr2-3）不给 `FORBIDDEN_IO` 加 `__import__(` | 转延后 Minor（账本 `:518`） | ✓ 理由成立，且代价已印在 `purity:577-579` |

### 5.4 fix round 3（Ruling 49–58）

| 项 | 处置 | 判定 |
|---|---|---|
| **R42 落地** | `purity:174-179` 改成「命中的是『相等』这一支，不是 `startswith(...)` 那一支」+ 两个实跑值 | **CLOSED** ✓ 我实跑：`'app.domain' == ALLOWED_PACKAGE` → `True`；`.startswith('app.domain.')` → `False`。另两处「白名单前缀 `app.domain.`」（`purity:145` / `:422`）**未被误伤**，且它们说的是 `app.domain.seed` / `app.domain.seed.generate`，`startswith` 实测为 `True`，本来就对 |
| **R46 落地** | 两份各加一条 `test_absolute_folding_matches_resolve_name` | **CLOSED** ✓ 479 → 481；§4 全表 |
| **R49/R50/R51**（控制者 #73/#74/#75） | 记错误 | ✓ 我核了 R51 的实质：`_is_forbidden('app.db.seed')` = False（layering GREEN）、`_is_allowed('app.db.seed')` = False（purity RED）——**同一格在两个文件里判定相反**，实现者把两份的期望颜色列写成不同是**对的** |
| **R52**（实现者 #2，自纠） | 记录 | ✓ 我确认 3.11.1 的 `resolve_name` 对 `level == 0`（不以 `.` 开头）**不抛**、原样返回，故矩阵第 1 行 `("app.seed.generate", 0, ...)` 判据可满足 |
| **R53** 计划正文「六条」→「十条」 | 控制者自己改（`73313f7`） | ✓ 我数了 `:19-28` = **10 条**顶层 bullet |
| **R54** `_package_of` 没有回归测试 | 进 fix round 4 | ✓ 见 5.5 |
| **R55** 模块 docstring 说「三条守卫」 | 进 fix round 4 | ✓ 见 5.5 |
| **R56** 矩阵手写不自动跟进 | 转 Task 2 | ✓ 有理由（Task 2 才有足够的真实形状可扫） |
| **R57** `import importlib.util` 在函数体内 | 维持 | ✓ 取舍已印在 `purity:252-254` / `layering:239-241` |
| **R58** 编号勘误（Ruling 48 永久留空） | 记录 | ✓ 我 grep 全账本：`Ruling 47` 在 `:505`、`Ruling 49` 在 `:558`，中间无 48 |

### 5.5 fix round 4（Ruling 59–66）

| 项 | 处置 | 判定 |
|---|---|---|
| **R54 落地** | `purity:313-362` / `layering:299-348` 各加一段（值断言 4 格 + 错形状断言 + **后果断言 2 格**） | **CLOSED** ✓ 相位 ③ 三格全部按预期红；`_package_of` 变异后 `parts[:-1]`→`parts` 在**基线 `be0f1af`** 上全量 **481 passed / rc 0**（改前口子是真的）；「后果」两格我独立实跑（`p1.py` §I + `p14.py` §2），与报告 `:2757-2758` 的 2×2 表逐格相符（含 purity 侧 `app/db/models/organisation.py` 那一格是 RED→RED、**不是**假绿） |
| **R55 落地** | `purity:8-11` 改成「本文件有 **4 个 `test_*`**：三条架构守卫 + 一条辅助函数的单元测试」 | **CLOSED** ✓ 我 AST 数：purity **4 个** `test_*`、layering **2 个**；layering 模块 docstring 通篇用单数「本守卫」，**无同类计数陈述**，实现者不改是对的 |
| **R55 附带**「同文件里另有 17 处『三条/第三条/两道』逐条核过、全部未动」 | — | ✓ 我 grep 全文件：`三条|第三条|两道` **命中 19 处**，行号 `[8,10,15,64,68,91,221,377,380,388,389,392,405,487,525,556,569,574,611]`；减去本轮新写的 `:8`/`:10` 正好 **17**，且与报告 `:2804-2808` 枚举的 17 个行号**逐字相同** |
| **R59–R64**（控制者 #76–#81） | 6 条全部接受 | ✓ 我抽验了 R63（`_absolute("seed",2,("app","domain","ind"),"generate")` = `'app.domain.seed'`，**不产出** `app.domain.seed.generate`——Ruling 63 成立、硬规矩 #57 立得对）与 R61（`_is_allowed('app.db.seed')` = False → purity RED，故派单那句后果**只在 layering 成立**） |
| **R65** 实现者判「不计入」的 2 条 | 控制者同意不计入 | ✓ 按 Ruling 45/51 口径判得对 |
| **R66** C-fr4-1 → Task 2；C-fr4-3 → Plan 03 预检；编辑工具 9 次 → 写进 #48 适用范围 | — | ✓ 三条全有处置 |

### 5.6 有没有 finding 被静默丢掉？

**只有 1 条，而且它不需要动作**：实现者 fix round 1 的关切 **`C-fr1-4`**（报告 `:1473-1484`：
「派单给的 8 处行号在 `ad1d190` 上仍然准，但 `Read` 工具在这些区段仍系统性少 1」）
在账本里**没有任何处置行**——`grep -n "C-fr1-4" progress.md` → **0 命中**，而同批的
C-fr1-1(R29) / C-fr1-2(R30) / C-fr1-3(R31) / C-fr1-5(R34) / C-fr1-6(R33) 都有。
影响很低（那条本身不要求动作，且它对 `Read` 偏移的归纳「系统性少 1」后来被 Ruling 64 推翻），
但它是派单 §B 点名要找的形态 → 记为控制者错误 **CE-5**。

其余 4 轮的全部 finding（4I+7M / 4I+5M+5范围外 / R41–47 / R49–58 / R59–66 / C-fr1..C-fr4 共 16 条实现者关切）
**逐条都有处置行**，6 条延后 Minor 全部登记在账本 `:268-269`/`:324`/`:406-407`/`:518-519`，无遗漏。

---

## 6. Section D —— 零生产语义改动（我自己验，不采信实现者的脚本）

`review_probes/p8.py`：剥 docstring（`Module`/`FunctionDef`/`ClassDef` 的首个 str-Expr）后 `ast.dump` 比基线 `ad1d190`。

```
=== 剥 docstring 后 ast.dump 与基线 ad1d190 比 ===
  backend/app/config.py                          SAME
  backend/app/pipeline/daily.py                  SAME
  backend/tests/db/test_models.py                SAME
  backend/tests/pipeline/test_daily.py           SAME
  backend/tests/architecture/test_domain_purity.py DIFF
  backend/tests/architecture/test_layering.py    DIFF
  backend/tests/test_config.py                   基线不存在（新文件）
```

**4 个 SAME / 2 个 DIFF（预期例外）/ 1 个新文件。**
⚠️ 派单 §D 只点了 `daily.py` 与 `test_models.py`，**漏了 `config.py` 与 `test_daily.py`**——
fix round 1 也动了这两个（`config.py` +10/−1、`test_daily.py` +9/−4，全是 `#:` 注释与 docstring），
我一并验了，都是 SAME。见 CE-1。

**尺子有效性（硬规矩 #53：对照组变异必须在 AST 上确认它真的改了代码）**::

```
=== 尺子有效性：3 个真语义变异 ===
  backend/app/pipeline/daily.py      把某个 int 常量 +1（AST 层面改 Constant）   AST 上真的改了 -> True（尺子有效）
      自比对照（同一份源码两次 dump 相等）-> True
  backend/app/config.py              把 'seed' 段改成 'wrong'（AST 层面改 Constant） AST 上真的改了 -> True（尺子有效）
      自比对照 -> True
  backend/tests/db/test_models.py    把某个 int 常量 +1                        AST 上真的改了 -> True（尺子有效）
      自比对照 -> True
```

三个变异都是**在 `ast.Constant` 上直接改值**（不是字符串 `replace`），故不会重演控制者错误 #72
（「`elapsed < 60` 只出现在 docstring 里」「`    business_date = ` 根本没匹配上」）；
自比对照为 True，故尺子不恒 False。

**行尾/字节口径**（`core.autocrlf=true`，7 个文件全部纯 CRLF、0 裸 LF、0 乱码）::

```
  backend/app/config.py                             3615 B  CRLF=  52  bare LF=  0  U+FFFD=0
  backend/app/pipeline/daily.py                    47761 B  CRLF= 810  bare LF=  0  U+FFFD=0
  backend/tests/db/test_models.py                  41478 B  CRLF= 721  bare LF=  0  U+FFFD=0
  backend/tests/pipeline/test_daily.py             45685 B  CRLF= 756  bare LF=  0  U+FFFD=0
  backend/tests/architecture/test_domain_purity.py 41613 B  CRLF= 634  bare LF=  0  U+FFFD=0
  backend/tests/architecture/test_layering.py      25789 B  CRLF= 396  bare LF=  0  U+FFFD=0
  backend/tests/test_config.py                      2134 B  CRLF=  30  bare LF=  0  U+FFFD=0
```

（`test_domain_purity.py` 41613 B / 634 CRLF 与 `test_layering.py` 25789 B / 396 CRLF 与实现者报告
`:2643-2644`、`:2703-2704` 逐字相符。）

**fix 链改动面（我另算了一遍「当前文件里哪些行是 `+` 行」，用于界定 §3 的复核范围）**::

```
  test_domain_purity.py +行 403 / -行 29
    区间: 8-11, 17-19, 25-26, 96-104, 108, 110-114, 117-194, 200-364, 368-393, 406-424,
          449, 451-459, 471-492, 521-579
  test_layering.py      +行 287 / -行 12
    区间: 70-130, 133-159, 166-171, 183-350, 363-367, 371-390
```

即 `purity:394-405`、`:425-448`、`:460-470`、`:493-520`、`:580-634` 与 `layering:1-69`、`:131-132`、
`:160-165`、`:172-182`、`:351-362`、`:368-370`、`:391-396` **不在 fix 链范围内**（属主体 `1df5e8a`）。
我对范围内的每一处 prose 都做了实跑复核；范围外的只在被范围内散文引用时才顺手核
（`purity:394-405` 的 `app.refdata` 那段、`layering:18-30` 的 4 处 offender 那段，两处都核过、都成立）。

---

## 7. 我发现的账本 / 派单 / 计划文档的错误（控制者的错误）

> 按事实判。每条注明**成立 / 不成立 / 歧义**并给证据。

### CE-1（**成立**，本轮最实质的一条）派单 §1 的「改动文件」清单与 §D 的验收清单都少报了 3 个文件，且把 `daily.py` 的改动面说小了

派单原文：「改动文件：`test_domain_purity.py`、`test_layering.py`、`test_models.py`（仅 docstring）、
`daily.py`（**仅 `:226` 一处散文数字，已授权**）」；§D 原文：「`daily.py` / `test_models.py` 必须 SAME，
两个守卫文件必须 DIFF」。

**实测**::

```
$ git diff --name-status ad1d190..6784d57
M   Document/2026-10-06-实施计划02-智能处方引擎.md
M   backend/app/config.py
M   backend/app/pipeline/daily.py
M   backend/tests/architecture/test_domain_purity.py
M   backend/tests/architecture/test_layering.py
M   backend/tests/db/test_models.py
M   backend/tests/pipeline/test_daily.py
A   backend/tests/test_config.py
```

**8 个文件，不是 4 个**，其中 `backend/app/config.py` 是**生产代码**、`backend/tests/test_config.py` 是
**新建文件**。逐轮 `--numstat`::

```
ad1d190..6a2938f (round 1):  config.py 10/1   daily.py 27/4   test_models.py 93/3
                             test_daily.py 9/4  test_config.py 30/0(新)  + 两个守卫
6a2938f..1fa9941 (round 2):  daily.py 2/1     test_models.py 3/2        + 两个守卫
1fa9941..be0f1af (round 3):  只有两个守卫
be0f1af..6784d57 (round 4):  只有两个守卫
```

故 `daily.py` 在 fix 链里是 **+29/−5**（round 1 一次 27/4 的大段 docstring 重写 + round 2 的 2/1），
**不是「仅 `:226` 一处散文数字」**。

**佐证：评审包自己是自洽的、错的只是派单的转述。** 评审包 `:46-51` 那一节标题就是
「## 生产代码命中（**必须为空**）」，底下印着::

```
backend/app/config.py
backend/app/pipeline/daily.py
```

——**非空**，即包已经把这个事实摆出来了，派单没有据此改写自己的清单。

**影响**：① 派单 §D 的 SAME/DIFF 清单少了 `config.py` 与 `test_daily.py`（我补验了，都是 SAME）；
② 一个只读派单的评审者会漏掉一个新建的入库测试文件 `tests/test_config.py`（它正是评审 M7 的产出）。
**注：这些改动本身都是被授权的**（R27-M1 授权改 `config.py:35-36`、R27-M7 授权补 `tests/test_config.py`、
R26 授权改 `daily.py` 与 `test_daily.py` 的同一句话两处），所以这是**派单转述错**，不是实现者越界。
形态与 Ruling 44/#67、Ruling 62/#79 同源：**转写归纳、没核原始数据**。

### CE-2（**成立**）账本 `:616` 说「变异验收由控制者独立重跑（**8 相位**）」，而同节的表只有 5 个变异相位、`:718` 自己写的是「**5 相位**」

* 账本 `:630-637` 的表：M0 / M1 / `parts[:-1]→parts` 只改 layering / 只改 purity / 两份都改 / 收工
  = **5 个相位 + 1 行收工**。
* 账本 `:718`：「控制者独立跑完 **5 相位**变异」。
* 账本 `:616`：「（**8 相位**）」。
* 对照 round 3 那节 `:527`/`:544-552`：表里 **6 个相位**，正文没写数字 → 无误。

「8」是实现者 fr4.3 那张表的标签（报告 `:2688`「变异验收（8 相位）」、`:2819` 同），
被转写成了控制者自己的相位数。**这是硬规矩 #54（计数）的形态，也是 Ruling 44/#67 的形态。**

**附带（歧义，不计入控制者错误）**：实现者那张表也只有 **7 行**（M0/M1/M2/M3/M4/M5/M6）
却标「8 相位 / **失败项 0 / 8**」（报告 `:2836-2846`）。我点不出第 8 个相位是什么
（可能把「变异算子的 AST 自证」那 6 行算成 1 相位）。→ 记**歧义**，请实现者/控制者澄清口径。

### CE-3（**成立**，硬规矩 #56 在**立它的同一轮**被违反）账本 `:538` 的「红绿双档」判据没标主语，而它只对 layering 成立

账本 `:538`::

```
| 红绿双档（硬规矩 #50） | 读矩阵 | 红档 8 格 + 绿档 3 格（`level == 1` 包内导入 ×2、`app.db.seed` ×1）✓ |
```

**实测**（`p14.py` §4）：那是 **`test_layering.py`** 的矩阵（RED 8 / GREEN 3）；
**`test_domain_purity.py`** 的矩阵是 **RED 9 / GREEN 2**，而 `app.db.seed` 那一格在 purity 侧是 **RED**、
不是 GREEN。一行判据覆盖两个文件、且只对其中一个成立——**与 Ruling 51(#75)、Ruling 61(#78) 完全同型**，
而 #56 正是在**同一轮**（fix round 4，账本 `:707`）为这个形态立的规矩。
（另：`:540` 那行「明写三条：`_package_of` **不在守卫范围**……」记的是 round 3 的状态，
round 4 已把它改掉，故那行现在与磁盘不符——但它是**当时的亲验记录**，不是当前陈述，我不计为错误。）

### CE-4（**成立**）计划正文 `Document/2026-10-06-实施计划02-智能处方引擎.md:24` 印的「实为 2616 个 LF 行」已经过期（实为 3298）

原文（HEAD `ef48d33`，Ruling 64 的落地）::

```
    24| - **行号一律取 shell 口径**（硬规矩 #30/#37）：…… 报出的文件总行数也偏小
        （`task-1-report.md` 报 1031 行、**实为 2616 个 LF 行**）。
```

**实测**::

```
=== task-1-report.md 的行数口径 ===
  bytes = 243343 ; \n 计数 = 3298 ; \r\n 计数 = 0 ; splitlines() = 3298
```

**2616 在落笔当时是对的**：`## fix round 4` 那节正好从**第 2618 行**起，`3298 − 2616 = 682 = 2617..3298`，
即那个数是在追加 round-4 报告**之前**量的。但它被印进一个**入库**文件、指向一个**不入库且随后就被追加**的文件，
且没有绑定时间点。按硬规矩 #19（数字要能指到产生它的命令）、#37（引用绑定 commit）、#39（写下测量条件），
这类数要么绑时间要么不写。**建议**：改成「（`Read` 当时报 1031 行，python 数出 2616 个 LF 行；
该文件随后被追加到 3298 行——**这类数只对量它的那一刻有效**）」，或干脆只保留「报出的总行数偏小」这个定性结论。
⚠️ `ef48d33` 严格在评审范围 `ad1d190..6784d57` 之外，但它是 HEAD、且是 Ruling 64 的落地，故一并报。

### CE-5（**成立**）账本里没有 `C-fr1-4` 的任何处置行

`grep -n "C-fr1-4" progress.md` → **0 命中**；而 fix round 1 那节（`:292-320`）给了
C-fr1-1(R29) / C-fr1-2(R30) / C-fr1-3(R31) / C-fr1-5(R34) / C-fr1-6(R33) 五条处置，唯独漏了 C-fr1-4
（报告 `:1473-1484`）。影响很低（那条不要求动作），但它是派单 §B 点名要找的「悄悄丢掉」形态。
**顺带核了它的实质**：它说「`Read` 工具在这些区段仍**系统性少 1**」——我抽验一处
（用 `Read` 看 `progress.md` 的 `offset=444, limit=10`）得到的是 `444→Task 1: fix round 2/5 派发…`、
`446→#### Task 1 fix round 2 — 控制者亲验`，**与 shell 口径逐行相符、偏移 0**。
故 Ruling 64 的「0/−1/−2 并存、不可预测」比 C-fr1-4 的「系统性少 1」更准，那条被丢弃的归纳本身也不成立。

### CE-6（**歧义**）两个 commit message / 派单 §1 的项数转述与账本的派单清单对不上

* `6a2938f`：「修 **4 条 Important 散文错误** + 两条架构守卫的相对导入放行」。
  账本 `:271` 的派单清单是「评审 **I1–I4** + Minor **M1/M2/M3/M7**，共 8 项」。
  I1 就是「相对导入放行」（守卫口径，不是散文），故「4 条 Important **散文**错误」里
  只有 I2/I3/I4 三条是散文，而 I1 又被后半句单独列了一次 → **要么算 3 条散文、要么 I1 被重复计入**。
* `1fa9941`：「修两条架构守卫 `_absolute` 的假绿（负数切片 + 忽略 `names`）+ **4 处散文错误**」。
  账本 `:413` 的派单清单是「Ruling **35/36/37/38** + Minor **1–4**」= 8 项，其中散文类是
  R37（2 处 docstring 举例）、R38（1 处）、Minor 1/2/3/4（4 处）= **6 处**（或按 Ruling 计数 2 处）。
  **「4 处」与 6、2 都不符。**

判**歧义**而不是成立：两句都是压缩表述，「4」可能指某个我没还原出的分组口径。
但按硬规矩 #54（计数是最容易被读者当成事实的东西），建议 commit message 里的项数一律
与账本派单清单同口径（「N 项，见账本 Ruling X–Y」）。

### CE-7（**不成立**，正面确认）评审包本身没有错误

派单说评审包「1308 行 / 90750 B」→ **实测逐字相符**。派单说它是「控制者用 python subprocess 生成的
git 原始输出」→ 我把包里 `## git diff -U10` 那一节的 **1251 行**与 `git diff -U10 ad1d190..6784d57`
的实跑输出**逐行比对，完全相等**::

```
  包内 diff 行数 = 1251 ; git 实跑 = 1251 ; 逐行相等 = True
```

`git log --oneline` / `--stat` / `--name-status` 三节也与我实跑一致。**列出来是为了说明我核过，不是漏了。**

### CE-8（**成立**）派单 §2 让人在 Plan 02 账本里读 19 条硬规矩的定义行，其中 11 条不在那份文件里

派单原文（为避免 markdown 把行首的 `#44` 当标题，下面这行加了缩进）：

    `progress.md` — 执行账本……grep `硬规矩 #` 把 #19 / #29 / #30 / #32 / #35 / #39 / #42 / #43 /
    #44 / #46 / #47 / #50 / #51 / #52 / #53 / #54 / #55 / #56 / #57 的定义行都读一遍（散在全文……）

**实测**：Plan 02 账本里的「补硬规矩 #NN」定义行**只有 10 条**::

```
:172 #48   :265 #49   :290 #50   :409 #51   :411 #52
:509 #53   :588 #54   :705 #55   :707 #56   :709 #57
```

**#19 / #29 / #30 / #32 / #35 / #39 / #42 / #43 / #44 / #46 / #47 在 Plan 02 账本里没有定义行**，
它们是 **Plan 01** 立的（我自己在 `.superpowers/sdd/2026-09-28-…/progress.md` 里找到了：
`#19:1864`、`#29:2057`、`#30:2101`、`#32:3368`、`#35:2711`、`#39:3326`、`#42:3844`、`#43:3990`、
`#44:4489`、`#46:4695`、`#47:4738`）。

**这与 Ruling 62（控制者错误 #79：「派单让人在 Plan 02 账本里 grep 硬规矩 #30，那里 0 命中」）
是同一件事的完整版**，而 Ruling 62 已经被写进硬规矩 #55（`:705`）。也就是说：**在立了 #55、
并在同一份派单里要求评审者去读 #55 与 Ruling 62 之后，派单自己又犯了一次 #55 禁的事，
而且这次是 11 条而不是 1 条。** 我因此自己找到了 Plan 01 账本，没有卡住；
但按 #55 的判据（「把读者指向一个东西不在的地方，比不给指引更糟」）必须记一次。

---

## 8. 不可复核项（7 项）

| # | 陈述 | 位置 | 为什么不可复核 |
|---|---|---|---|
| 1 | 整学期回放的 4 个墙钟样本 **20.48 / 20.85 / 20.89 / 21.18 s** | `daily.py:226-228` | 复现要 `git worktree` 把 `e26347f` 检出、两棵树背靠背各跑 n=2；**脚本不在库内**（源码自己在 `:231-232` 承认）。我没有建 worktree（会改主仓的 worktree 列表）。⚠️ **算术部分我复核了**：均值 20.665/21.035、两个极差 0.37/0.29、差 +0.370 s = +1.7905%、`60/21.18 = 2.8329` 全部自洽（见 M-5） |
| 2 | A/B 索引实验的墙钟中位 **0.2708 / 0.2941 ms** 与 **min…max = 0.1385…0.9031 / 0.1698…1.0212 ms** | `test_models.py:596-597`、`:602` | **当次样本**。我用抽出的脚本另跑 2 次得到 `median A/B = 0.2638/0.2744`（B/A=1.040）与 `0.1739/0.7048`（B/A=4.054）、min/max `0.1166…1.7504`/`0.1120…1.7259` 与 `0.1164…1.7367`/`0.1314…11.3388`——点值不可复原。**源码已就地标为「单次采样、方向不可复现」并撤回方向结论，处置正确**；`.db` 字节那一半是**可复核且已复核为真**的 |
| 3 | 「连跑四次，B/A 依次是 **1.086 / 0.944 / 1.019 / 0.989**」 | `test_models.py:614` | 历史四次样本，无法复原其机器状态。（我另给两个样本 1.040 / 4.054，方向同样跨 1.0，**支持**那句撤回） |
| 4 | 「`Read` 工具偏移 **0 / −1 / −2 并存**」「同一行两次调用分别被标 **449 和 450**」 | 计划正文 `:24`、账本 `:693` | 工具行为依赖调用时机与缓冲区状态，无法复现「同一行两次不同号」。我只抽验一处：`Read` 看 `progress.md` 的 `offset=444` 得到 `444→…fix round 2/5 派发`、`446→#### Task 1 fix round 2 — 控制者亲验`，**偏移 0**，与「0/−1/−2 并存」相容、与「系统性少 1」不相容 |
| 5 | 「终审 A 说的『**14 种写法可绕过**』」 | `purity:392-393` | 终审 A 的报告不在库内。**源码自己写了「本轮没有逐条复跑」**（诚实标注 ✓），我也没复跑；我复跑的是它底下那 3 条亲跑基线的写法（全绿）+ 3 条控制组（全红） |
| 6 | 实现者 fr2/fr3/fr4 的全部探针脚本（`fr2_probes/` 11 个、`fr3_probes/` 11 个、`fr4_probes/` 21 个条目） | 报告各节 | 我没有逐个重跑它们。**我用自己另写的 12 个探针独立复现了其中全部关键结论**（14 行表、基线 deny-list、相对导入改前/改后、9+2 相位变异、两条历史「全绿」、`_package_of` 后果 2×2 表、19 处计数），故本评审不依赖它们 |
| 7 | 「同一份 500 人 / `seed=20250828` / 112 业务日数据」这个 A/B 对照的**数据同一性** | `daily.py:225` | 需要重建两棵树的数据生成过程；与 #1 同因 |

---

## 9. 收工自证

```
$ git rev-parse --short HEAD
ef48d33
$ git status --short
（0 行）
$ git branch --show-current
feature/plan-02-prescription-engine
backend/pe.db 存在 = False
backend/data/seed 文件数 = 0
backend/data/national_standard_2014.csv = 21412 B / sha256[:16] D2C8E539E2FA0029 / CRLF 0
两个守卫文件 sha256[:16] = 440f7167610df187 / 50d776680defc25e（全部变异实验前后逐字相同）
```

* **全程未用** `git checkout` / `git restore` / `git switch` / `git merge`；基线内容一律用
  `git show <rev>:<path>` 或 `git archive <rev> backend` 取到内存 / `$env:TEMP`。
* 所有变异实验都在 `$env:TEMP` 的 backend 副本或 `git archive` 导出树上做，**主工作树未被写入**。
* 本次评审的全部产物落在 `.superpowers/sdd/review_probes/`（`.gitignore:10` 覆盖，`git check-ignore` 确认）
  与本文件；`backend/.coverage` 是我跑 `--cov` 那次更新的（`.gitignore:7` 覆盖，非入库文件）。
* 行号一律 shell 口径（python `enumerate` 读字节），绑定 `ef48d33`（代码基线 `6784d57`）。

---

## 10. 一句话给控制者

四轮 fix 的**工程实质是干净的**：0 Critical、零生产语义改动、5 条既有守卫 assert 逐字未动、
两个新守卫点各有两份互相独立的回归测试、判据锚在 `importlib.util.resolve_name` 上而不是锚在某个人的表上、
两条「改前口子是真的」历史陈述我都在历史基线上复跑到了。
**但这个项目唯一反复出现的错误类又中了两次**（I-1 一个 `level` 归错、I-2 一份配方漏了两个必要条件），
而且 I-2 漏的正好是硬规矩 #53 立规矩时要防的那两件事、I-1 的形态正好是硬规矩 #56 要防的那件事——
**两条规矩都是在同一个 Task 里立的，立完当轮就没挡住。**
控制者侧我这轮找到 **6 条成立 + 1 条歧义**（CE-1..CE-6、CE-8），其中 CE-3（#56 在立它的同一轮被违反）
与 CE-8（#55 在要求评审者读 #55 的那份派单里被违反）是**规矩立下当轮即失效**的形态，
比单条数字错更值得记：**「写下规矩」与「遵守规矩」之间仍然没有机制保障**（Plan 01 账本 `:1354` 第 13 条
早就写过这句话）。建议把 #54/#55/#56 从「纪律」升级成**机械动作**：派单发出前用脚本 grep 自己刚写的
编号引用与计数（#55 可机械检查），以及**任何一句话里出现两个守卫的名字或颜色时强制要求带主语前缀**（#56 可机械检查）。

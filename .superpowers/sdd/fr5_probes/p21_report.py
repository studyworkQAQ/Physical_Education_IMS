# -*- coding: utf-8 -*-
"""P21 — 把 fix round 5 的报告追加到 task-1-report.md（读回全文 -> 追加 -> 落盘 -> 双向闸门）。

⚠️ 该报告文件是 **LF-only**（CRLF 0），故追加一律用 '\\n'，并把整个文件按字节写回。
"""
import ast
import hashlib
import importlib.util
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
REPORT = ROOT / ".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md"
BACKEND = ROOT / "backend"

# ------------------------------------------------------- 追加前再核一遍矩阵行号（活证据）
sys.path.insert(0, str(BACKEND))


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, BACKEND / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def cases_of(rel):
    tree = ast.parse((BACKEND / rel).read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "test_absolute_folding_matches_resolve_name")
    for st in ast.walk(fn):
        if isinstance(st, ast.Assign) and any(getattr(t, "id", "") == "cases" for t in st.targets):
            return ast.literal_eval(st.value)


ROWCHK = []
for rel, tag in (("tests/architecture/test_domain_purity.py", "purity"),
                 ("tests/architecture/test_layering.py", "layering")):
    cs = cases_of(rel)
    idx = [i + 1 for i, c in enumerate(cs)
           if c == ("indicators", 2, ("app", "domain", "prescription"), "X", "GREEN")]
    idx7 = [i + 1 for i, c in enumerate(cs) if c[0] == "" and c[1] == 2
            and c[2] == ("app", "db", "models")]
    red = sum(1 for c in cs if c[4] == "RED")
    grn = sum(1 for c in cs if c[4] == "GREEN")
    ROWCHK.append((tag, len(cs), idx, idx7, red, grn))
    print("  %s: %d 格；新格在第 %s 行；('',2,('app','db','models')) 在第 %s 行；RED %d / GREEN %d"
          % (tag, len(cs), idx, idx7, red, grn))

SHA_BEFORE = hashlib.sha256(REPORT.read_bytes()).hexdigest()
old = REPORT.read_bytes().decode("utf-8")
OLD_LINES = len(old.splitlines())
OLD_BYTES = len(REPORT.read_bytes())
assert old.count("## fix round 5") == 0, "本节已存在，不许追加两遍"

HEAD = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
                      capture_output=True).stdout.decode().strip()

SEC = """

---

## fix round 5

**状态：完成（8 条 finding 里 7 条完全落地；Minor 3 有 1 处被派单自己的禁区挡住，按 §10 的口径
停下写明并给出待打的补丁）。commit `%(HEAD)s`（4 files changed / 151 insertions / 39 deletions），
未 push。基线 `d00533c`，代码基线 `6784d57`（`73313f7` / `ef48d33` / `d00533c` 三个 commit 的改动面
亲验各只有 `Document/2026-10-06-实施计划02-智能处方引擎.md` 一个文件，故两个守卫文件与
`daily.py` / `test_models.py` 自 `6784d57` 起未变，AST 尺子的基线取 `6784d57`）。**

本轮探针：`.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/fr5_probes/`（gitignored，
与 fr2/fr3/fr4_probes 同规格保留，便于复核）。原始输出留在同目录 `OUT_p8.txt` /
`OUT_p12.txt` / `OUT_p13.txt` / `OUT_p14.txt` / `OUT_p15.txt` / `OUT_p17.txt` / `OUT_p20.txt`。

### 0. 三个闸门数字（全部亲跑，跑在**最终落盘状态**上，不是中途状态）

| 项 | 命令（在 `backend/` 下） | 我亲跑的结果 |
| --- | --- | --- |
| 全量 | `python -m pytest -q` | **481 passed in 55.53s** ✓（与基线 `6784d57` 的 481 逐字相同；本轮只加矩阵格、不加测试函数） |
| domain 覆盖 | `python -m pytest -q --cov=app/domain --cov-branch --cov-report=term-missing` | **TOTAL 399 stmts / Miss 0 / 114 branch / BrPart 0 / 100%%**；**480 passed, 1 skipped in 118.15s** ✓（那 1 条 skip 是 `test_backfill.py` 的 trace-hook 自觉跳过，既有行为） |
| 架构守卫 | `python -m pytest tests/architecture -q` | **6 passed in 0.08s** ✓ |

⚠️ 上面三个数是在 `p18_rewrap.py`（四处散文重排）之后重跑的，故与 commit 里的字节一一对应。
中途还跑过一次（重排前）：`481 passed in 54.40s` / `480 passed, 1 skipped in 119.23s` /
`399-0-114-0-100%%`，两次一致。

### 1. 8 条 finding 的逐条落地

#### 1.1 Ruling 67-① — `level == 1` 说错了，实为 `level == 2`（已改）

改的是 `test_domain_purity.py` 里 `test_absolute_folding_matches_resolve_name` 的 docstring
（改前 `:230-232`）。**我没有照抄控制者给的 `'app.domain.indicators'`，自己跑了一遍**
（`fr5_probes/p1_ruling67.py`，本机 Python 3.11.1）：

```
ast.parse('from ..indicators import X').body[0]
    -> ImportFrom  level=2  module='indicators'  names=['X']       # 两个点
_package_of(BACKEND / 'app/domain/prescription/match.py')
    -> ('app', 'domain', 'prescription')          # purity 与 layering 两份都给这个
_absolute('indicators', 2, ('app', 'domain', 'prescription'), 'X')
    -> 'app.domain.indicators'                    # 两份都给这个
importlib.util.resolve_name('..indicators', 'app.domain.prescription')
    -> 'app.domain.indicators'                    # 与 _absolute 逐字相同
purity   _is_allowed('app.domain.indicators')    = True    -> purity 侧 GREEN
layering _is_forbidden('app.domain.indicators')  = False   -> layering 侧 GREEN
purity   ALLOWED_PACKAGE  = 'app.domain'  ; 'app.domain.indicators'.startswith('app.domain.') = True
layering FORBIDDEN_PREFIX = 'app.seed'    ; 'app.domain.indicators'.startswith('app.seed.')    = False
```

**控制者那句「这是控制者的推算、不是控制者的实跑」的自我标注是对的，而它的推算成立**：
layering 侧确实是 GREEN。现在我把它变成了实跑，并按硬规矩 #56 在两份文件里各自标了主语
（purity 侧写「命中白名单前缀 `app.domain.`」，layering 侧写「不以 `app.seed` 开头」，
**没有互相照抄理由**）。

新 docstring 里写明的是「包深 3 → 要**两个点**才上溯到 `app.domain`」，并贴了上面这 6 行实跑值。

#### 1.2 Ruling 67-② — purity 矩阵缺 `(包深3, level2, GREEN)` 那一格（已加，两份都加）

`fr5_probes/p1_ruling67.py` 用 **AST 抽 `cases`**（不是手数）逐格打印：

| | 改前 | 改后 |
| --- | --- | --- |
| purity 格数 | 11 | **12** |
| purity `(包深3, level2, GREEN)` | **0 格** | **1 格** = 新加的 `("indicators", 2, ("app","domain","prescription"), "X", "GREEN")` |
| purity RED / GREEN | 9 / 2 | 9 / **3** |
| layering 格数 | 11 | **12** |
| layering `(包深3, level2, GREEN)` | 1 格（是 `("", 2, ("app","db","models"), "seed")`，`module` 为空那一档，**不是** Task 2 的形状） | **2 格** |
| layering RED / GREEN | 8 / 3 | 8 / **4** |

控制者亲验的「purity 侧 `(包深3, level2, GREEN)` 是 0 格、GREEN 只有 2 格且都在包深 2 /
level 1」**我独立复现，成立**。

⚠️ 顺带记一句给账本：Ruling 73 / CE-3 里那句「purity 是 RED 9 / GREEN 2、layering 是
RED 8 / GREEN 3」在**当时**为真，本轮加格后变成 **9/3 与 8/4**——那不是它写错，是矩阵长大了。

新格在两份矩阵里都是**第 9 行**（活证据，追加本节前刚跑的 AST 抽取）：

```
%(ROWCHK)s
```

两份 docstring 里既有的「⚠️ 矩阵第 7 行 `("", 2, ("app","db","models"), "seed")`」引用
**没有错位**：新格插在第 8 行之后，第 7 行仍是第 7 行（上面那段输出里 `idx7` 一列即证）。

**layering 侧也加了同一格**（派单说「建议加」，我加了），理由与派单相同：Task 2 第一天
就会写出这一句合法导入，而 layering 也扫 `app/domain`。layering 那一份的注释写的是
「本文件（layering 侧）判的是 app.seed 前缀，`_is_forbidden(...)` = False → 不以 app.seed
开头 → GREEN」，并明写「与 test_domain_purity.py 同一格的 GREEN **理由不同**……颜色相同、
判据不同，这不是抄错（硬规矩 #56）」——**没有照抄 purity 侧的白名单理由**。

`passed` 数不变（481），因为只往 `cases` 这个数据列表里加了一行，没有新测试函数；
新测试里的 **3 条 `assert` 与基线逐字相同**（见 §3 的 ④）。

#### 1.3 Ruling 68 — 合成树配方照做会全红（已补正，两份对齐）

`fr5_probes/p5_synthtree.py`，两个 phase 都亲跑：

**phase A：照 `test_domain_purity.py` 改前 `:523-525` 的字面配方**（只重定向 `DOMAIN`、
树里只有 `probe.py` 这 1 个 `.py`）：

```
树里的 .py 数 = 1   BACKEND = ...\\backend（未重定向）
row 0（干净对照）-> ('RED','RED','RED')
row 1..14        -> ('RED','RED','RED')  全部
全 RED 的行数 = 15 / 15
G1 -> ValueError: '...\\app\\domain\\probe.py' is not in the subpath of '...\\backend'
G2 -> AssertionError: 只扫到 1 个 .py，app/domain 可能被搬空，三条守卫会一起假绿
G3 -> AssertionError: 只扫到 1 个 .py，app/domain 可能被搬空，三条守卫会一起假绿
```

**与控制者的描述逐字相符**（连「14 行连同干净对照行全 RED」也是：我特意加了对照行，它同样红）。
两条机制分别对应派单点出的两项遗漏：`BACKEND` 未重定向 → G1 抛 `ValueError`；
`.py` 不足 5 个 → G2/G3 被 `_assert_not_empty` 拦下。

**phase B：补正后的配方**（`DOMAIN` 与 `BACKEND` 都重定向、树里 5 个 `.py`）：

```
干净对照行（probe.py 只写 x = 1）-> ('GREEN','GREEN','GREEN')
row 1..14 × 3 列 = 42 格逐格相符、0 处不符
FORBIDDEN_IO 子串命中：__import__("os").listdir(".") = 0 个 ; 对照组 import os / os.listdir('.') = 2 个
```

即**那张 14 行的表本身是对的，坏的只是配方**——所以我一个颜色都没动（与派单一致）。

**两份对齐（硬规矩 #51）**：我先把两处配方都读出来比对（没有照抄控制者的转述）：

| | 改前 | 改后 |
| --- | --- | --- |
| `test_domain_purity.py` | 只说重定向 `DOMAIN`；不提 `.py` 个数；不提干净对照 | `DOMAIN` **和** `BACKEND`；**≥ 5 个 `.py`**（含探针自己）；**必须先跑一行三列全 GREEN 的干净对照**；并写明照改前的字面配方会 15 行全 RED |
| `test_layering.py` | 已有 `BACKEND` / `APP`；不提 `.py` 个数；不提干净对照 | `BACKEND` / `APP` **两个都**（并写明只改 `APP` 会抛 `ValueError`）；**≥ 8 个 `.py`**（对应它自己那条 `len(scanned) >= 8`）；必须先跑干净对照；并互相点名对方的下界（5 vs 8） |

layering 侧那三条也是我亲跑的（`fr5_probes/p10_layering_recipe.py`）：

```
只改 APP、不改 BACKEND           -> ValueError: '...\\app\\pipeline\\m0.py' is not in the subpath of ...
两个都改、树里只剩 1 个 .py       -> AssertionError: 只扫到 1 个 .py，目录可能被搬空: ('pipeline','db','domain')
两个都改、11 个 .py、offender 探针 -> AssertionError：app/pipeline/probe.py:1: app.seed
                                     app/db/probe.py:1: 相对导入上溯到顶层包 app 之外
两个都改、干净对照（x = 1）        -> GREEN
```

#### 1.4 Minor 1 — 「两个 bug」下面列 3 个 bullet（已改，我的选择与理由）

**我的选择：把开头改成「两个 bug；下面列的是三条变异」，并写明 `2 ≠ 3` 的理由**，而不是把
「两个」改成「三个」。理由（`fr5_probes/p7_fr2_code.py`，剥 docstring 后逐函数比
`1fa9941^` 与 `1fa9941` 的 AST）：

```
test_domain_purity.py / test_layering.py，fix round 2（1fa9941）改动的**代码**：
  _absolute           : 签名多一个 name 形参
  _absolute           : + if level - 1 > len(package): return None        <- Ruling 35（越界档）
  _absolute           : - return ".".join(anchor + ((module,) if module else ()))
                        + tail = module or name
                        + return ".".join(anchor + ((tail,) if tail else ()))  <- Ruling 36 的一半
  _imported_modules   : - yield node.lineno, (node.module or ""), node.level
                        + if node.level and not node.module:
                        +     for alias in node.names:
                        +         yield ... alias.name                      <- Ruling 36 的另一半
  test_domain_imports_stay_within_the_allow_list : 跟着改解包（4 元）
```

所以按**代码处**数是 3 处、按 **Ruling** 数是 2 条（35 / 36），而原文那句的主语是
「fix round 2 修掉、而此前仓库里没有任何断言看着的 **bug**」，同段后面又已经有「三条的复现
命令」「三种变异」。把「两个 bug / 三条变异」并写、并点明 Ruling 36 有两半，是唯一能让
整段自洽又不丢信息的写法；改成「三个 bug」会与账本 Ruling 46 的标题（「本轮修掉的**两个**
bug」）以及 Ruling 46 只列了两条变异（①②）对不上。

⚠️ **一处措辞我要提出来**：派单说「前两个才是 fix round 2 修的 bug，第三个是同一条 Ruling 36
的另一半」。**后半成立**（两处都引 Ruling 36）；**前半的「才是」不成立**——第三处
（`_imported_modules` 一名一条展开）的代码改动**同样落在 `1fa9941` 里**（上面那段 AST 比对
就是证据）。故三处都是「fix round 2 修掉的」，只是其中两处同属 Ruling 36。我据此把 docstring
写成「两半都在 fix round 2 那一个 commit `1fa9941` 里落地」，而不是照派单的措辞写。

两份文件都改了（硬规矩 #51）。

#### 1.5 Minor 2 — 「479 条全绿」无 commit 绑定（已绑，两侧都亲跑）

改成绑 `be0f1af^`（= `1fa9941`），并写明「别在 HEAD 上照做：HEAD 有 481 条，同一个变异会得到
`2 failed, 479 passed`」。**两个数我都亲跑了**：

`fr5_probes/p8_wt_479.py` —— 在 `$env:TEMP` 的 `git worktree`（detached 到 `be0f1af^`）上：

```
be0f1af^ = 1fa9941
(a) worktree 原样                          rc=0  末行=479 passed in 57.41s
(b) 两份都删掉越界守卫那 3 行                rc=0  末行=479 passed in 59.20s
判读：「be0f1af^ 上 479 条全绿」为真 = True
worktree remove rc=0 ; WT 还存在? False ; git worktree list 只剩主树 ; 主工作树 git status --short = ''
```

`fr5_probes/p20_dispatch_claims.py` §(d) —— 在 **HEAD（`7b84599`）** 上把两份的越界守卫都删掉跑全量：

```
rc = 1
FAILED tests/architecture/test_domain_purity.py::test_absolute_folding_matches_resolve_name
FAILED tests/architecture/test_layering.py::test_absolute_folding_matches_resolve_name
末行 = 2 failed, 479 passed in 55.38s
还原核对: {'test_domain_purity.py': True, 'test_layering.py': True}   sha256 逐字复原
```

**即评审者那句「在 HEAD 上照字面跑得到 `2 failed, 479 passed`」我独立复现，成立**；红的正是
两份 `test_absolute_folding_matches_resolve_name`，与派单的说法一致。全程未用
`git checkout` / `git restore` / `git switch` / `git merge`（worktree 用 `git worktree add/remove`，
删守卫用 python 按字节写回 + 核 sha256）。

同文件 `:360` 附近那种「故意不写死数字」的样板我没有动——它是**断言消息**，数字会随后续 Task 漂；
而这里绑了 commit 就不会漂。两种口径并存是有理由的，我在 docstring 里把 commit 写死了。

#### 1.6 Minor 3 — fix 链新增散文里的「本轮」（**10/11 已绑；1 处被派单禁区挡住**）

先自己 grep 定位、再逐个 commit 的 `-U0` diff 定轮次（`fr5_probes/probe_benlun.py` +
`p6_round_of_benlun.py`，都不靠控制者或评审者的转述）：

| # | 位置（改前行号） | 内容摘要 | 落在哪个 commit | 我绑成 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 1 | `test_domain_purity.py:222` | 本轮实测三种变异 | `be0f1af` | fix round 3 | ✅ |
| 2 | `test_domain_purity.py:392` | 本轮没有逐条复跑 | `6a2938f` | fix round 1 | ✅ |
| 3 | `test_domain_purity.py:525` | 分别调用三条守卫（本轮亲跑） | `6a2938f` | fix round 1 首跑 + fix round 5 复跑 | ✅ |
| 4 | `test_domain_purity.py:544` | 本轮把 14 行全部重跑了一遍 | `1fa9941` | fix round 2（+ fix round 5 又跑一遍） | ✅ |
| 5 | `test_layering.py:150` | 本轮亲跑：12 条 | `6a2938f` | fix round 1（+ fix round 5 复跑仍是 12 条） | ✅ |
| 6 | `test_layering.py:210` | 本轮实测三种变异 | `be0f1af` | fix round 3 | ✅ |
| 7 | `test_layering.py:371` | 一条命令数完三个目录；本轮亲跑 | `6a2938f` | fix round 1 | ✅ |
| 8 | `test_layering.py:385` | 由那条 Counter 命令本轮亲跑得出 | `1fa9941` | fix round 2 | ✅ |
| 9 | `test_models.py:609` | 本轮把它整段抄在下面 | `6a2938f` | fix round 1 | ✅ |
| 10 | `test_models.py:618` | 完整内容，本轮亲跑验证过 | `6a2938f` | fix round 1 | ✅ |
| 11 | **`backend/app/pipeline/daily.py:206`** | 实测（本轮亲跑：内存库…） | `6a2938f` | —— | ⛔ **未动** |

（`test_models.py:612` 那处本来就绑了「本轮（Plan 02 Task 1 fix round 1）」，是仓内样板，未动。
`daily.py:657` 与 `tests/pipeline/test_daily.py:319` 的「本轮」**不在 fix 链改动面内**——
我用 `git diff -U0 ad1d190 6784d57` 的新增行核过，故不在本轮范围。）

**⛔ 第 11 处为什么没动**：派单 §2 Minor 3 要求「全部绑成 fix round N」，而 §3 禁区写
「**`daily.py` 只许动 Minor 5 那两个散文标签**，一个字节代码都不许改」。这两条对
`daily.py:206` 这一行**不能同时满足**。按 §10「任何一条验收判据按字面不可满足就停下来写明、
按实测做」，我选择**服从禁区**（禁区是显式禁止，工作清单的「全部」是范围含糊），
理由是：不做的代价只是留 1 处歧义指代（且我已在此写明它指 fix round 1），而越界改生产文件的
代价是不可逆的信任损失。**待打的补丁（一行，纯 docstring，代码 0 字节）**：

```
- ``test_date`` 越**小**，满足它的 ``as_of`` 就越**多**。实测（本轮亲跑：内存库，同一个
+ ``test_date`` 越**小**，满足它的 ``as_of`` 就越**多**。实测（fix round 1 亲跑：内存库，同一个
```

请控制者裁定：授权后 30 秒可打完，或折进 Task 2 的预检清单。

#### 1.7 Minor 4 — 「两条查询计划逐字复现」用在截断引文上（已改）

`fr5_probes/p3_p4_plans_and_means.py` §P3 亲跑（临时库、`init_db` 后直接
`explain query plan`，四列全打）：

```
A 整行 = (4, 0, 0, 'SEARCH stratification_result USING COVERING INDEX sqlite_autoindex_stratification_result_1 (student_id=?)')
B 整行 = (4, 0, 0, 'SEARCH stratification_result USING COVERING INDEX ix_stratification_result_student_computed (student_id=?)')
detail 是否以 'SEARCH stratification_result ' 开头 = True（A、B 都是）
```

**评审者的实测成立**：表里只印了 `USING COVERING INDEX …` 那一段，前面还有
`SEARCH stratification_result `。改法取派单给的第一个选项——写成「**尾部逐字复现**」，
并把两个场景的 detail **全串**补印进 docstring（这样引文不再截断，「逐字」这个强断言就有了
可核的对象）。`.db` 字节那一半仍是「逐字复现」（那四个数没有被截断，未动）。

#### 1.8 Minor 5 — `daily.py` 两个「均值」是截断值（已标口径；代码 0 字节改动）

`fr5_probes/p4_means.py` 亲跑：

```
基线   样本 (20.48, 20.85)  和 41.33   真均值 20.665   round(_,2)=20.66   截断=20.66   '%%.2f'='20.66'
       源码印 20.66 -> == round()? True ; == 截断? True       组内极差 0.370000000000001
之后   样本 (20.89, 21.18)  和 42.07   真均值 21.035   round(_,2)=21.04   截断=21.03   '%%.2f'='21.04'
       源码印 21.03 -> == round()? False ; == 截断? True      组内极差 0.28999999999999915
差 = 0.370000000000001 -> 源码 +0.37 s  round(d,2)==0.37 True
百分比 = 1.790466973143 -> 源码 +1.8%%   round(pct,1)==1.8 True
60/21.18 = 2.8328611898016995 -> 源码 2.83x  round(r,2)==2.83 True
21.035.hex() = 0x1.508f5c28f5c29p+4 ; ma.hex() 逐字相同（即 ma 就是 21.035 这个 float）
```

**评审者的判断成立**：`21.03` 只能是截断（`round()` 会给 `21.04`）。`20.66` 那一处两种口径
巧合相同，但同样标成截断才与另一处一致、也才是作者实际做的事。两处都加了
「**截断到百分位**：真值 …，`round(_, 2)` 同为/会给 …」。
`+0.37 s` / `+1.8%%` / `2.83×` 三个数**我独立核过、全部自洽，一个字节没动**（与派单一致）。

⚠️ 这是生产文件：本轮对 `daily.py` 的改动是 **5 insertions / 2 deletions**，
全部在 `_fitness_batch` 的 docstring 里；剥 docstring 后**全部顶层单元 SAME**（§3），
即**代码 0 字节改动**。禁区里那句「只许动 Minor 5 那两个散文标签」我按「两个标签所在的
那一段散文」执行——实际动了 3 行原文、写成 6 行，多出来的是口径说明本身。

#### 1.9 Minor 6 — `purity:146`「守卫当场假绿」缺主语（已补）

改成「**本守卫当场假绿**」并加了一句主语说明。顺手把 layering 侧的对照也实跑了
（`fr5_probes/p10_layering_recipe.py`）：

```
purity   _is_allowed('app.domain.seed')   = True    -> purity 侧是「假绿」（本该 offender 却放行）
layering _is_forbidden('app.domain.seed') = False   -> layering 侧是**正确的 GREEN**、不是假绿
layering FORBIDDEN_PREFIX = 'app.seed' ; 'app.domain.seed'.startswith('app.seed.') = False
```

**评审者「不是事实错误、只是主语纪律」的判断成立**，而且这一格恰好是 Ruling 61（控制者错误
#78）的镜像：同一个折算串在 purity 侧是假绿、在 layering 侧是正确的绿。故补主语时我把这层
对照也写进去了（硬规矩 #56 的正面用法）。

### 2. 变异验收（7 相位；`fr5_probes/p13_mutation.py`，原始输出 `OUT_p13.txt`）

只跑那两条 `test_absolute_folding_matches_resolve_name`。每次变异都在**剥 docstring 后的
`ast.dump`** 上确认真的改了代码；结束按**字节**还原并核 sha256；全程未用
`git checkout` / `git restore`。

| 相位 | 变异内容 | AST 真的变了 | 结果 | 判读 |
| --- | --- | --- | --- | --- |
| **M0** | 不变异（对照） | —— | `2 passed in 0.02s` | 基线绿 ✓ |
| **M1** | `anchor = package[: len(package) - (level - 1)]` → `tuple(list(package)[: len(package) - (level - 1)])`（语义等价，两份都改） | 两份都 True | `2 passed in 0.03s` | **尺子不恒红** ✓ |
| **M2** | `… - (level - 1)` → `… - level`，**只改 purity** | purity True / layering sha256 未变 | `1 failed, 1 passed` | **purity 红、layering 仍绿** ✓ |
| **M3** | 同上，**只改 layering** | layering True / purity sha256 未变 | `1 failed, 1 passed` | **layering 红、purity 仍绿** ✓ |
| **M4** | 同上，两份都改 | 两份都 True | `2 failed in 0.14s` | ✓ |
| **M5** | **定向变异**：在 `_absolute` 里插入「`level == 2` 且包深 3 且 `module` 与 `name` 都非空时返回 `'.'.join(package[:1] + (module,))`」，两份都改 | 两份都 True | `2 failed in 0.15s` | 只有新格那一形状被折错 → 两份都红 ✓ |
| **M6** | = M5，但把**新加的那一格删掉** | 两份都 True | `2 passed in 0.03s` | **只有新格能抓住 M5** ✓ |

**M5 → M6 这一对是本轮最要紧的证据**：M5 是一个「只折错 Task 2 那一形状」的变异，
它在改前的 11 格矩阵下**完全静默**（M6 就是改前的矩阵 + M5 的变异 → 全绿），
只有加了新格才变红。**即 Ruling 67 说的「仓库里没有任何断言看着」是真的，
而新加的那一格是承重的、不是装饰。**

M2/M3 的失败输出里都印着新格那两行 offender，说明新格也**参与**了普通变异的变红：

```
_absolute('indicators', 2, ('app', 'domain', 'prescription'), 'X') = 'app.indicators'，
    而 resolve_name('..indicators', 'app.domain.prescription') = 'app.domain.indicators'
_absolute('indicators', 2, ('app', 'domain', 'prescription'), 'X') = 'app.indicators' 判成 RED、期望 GREEN
```
（第二行只在 purity 侧出现——layering 侧 `'app.indicators'` 同样不以 `app.seed` 开头，
故**本文件**的颜色判定不变、只有折算值那条 offender。这正是硬规矩 #56 要标主语的地方。）

还原核对：`test_domain_purity.py` / `test_layering.py` 的 sha256 **都还原为 True**；
`git status --short` 只列出本轮那 4 个文件。

### 3. 改动面自证（硬规矩 #32 + #53；`fr5_probes/p14_astdiff.py`，原始输出 `OUT_p14.txt`）

尺子：`git show 6784d57:<path>` 取基线（⚠️ blob 是 LF 版，比较前一律归一化）、剥 docstring
（对 `ast.Module` 也剥）、逐顶层单元比 `ast.dump(include_attributes=False)`。

**⓪ 改动面**

```
git diff --name-only HEAD       = 4 个文件（正好是禁区允许的那 4 个）
git diff --numstat HEAD         = daily.py 5/2 ; test_domain_purity.py 73/17 ;
                                  test_layering.py 59/14 ; test_models.py 11/4
git diff --name-only 6784d57 -- backend/     = 同上 4 个
git diff --name-only 6784d57 -- backend/app/ = ['backend/app/pipeline/daily.py']  ← 禁区里只允许这一个
git diff --name-only HEAD -- backend/data/ Document/ = []   ← 本轮工作树没碰 data/ 与 Document/
```

**① 剥 docstring 后逐顶层单元比 —— 实际差异清单（不是「符合预期」四个字）**

| 文件 | 有差异的顶层单元 | 其余单元 |
| --- | --- | --- |
| `test_domain_purity.py` | `['test_absolute_folding_matches_resolve_name']` | `_domain_files` / `_assert_not_empty` / `_imported_modules` / `_package_of` / `_absolute` / `_is_allowed` / `test_domain_imports_stay_within_the_allow_list` / `_dotted` / `_hit_forbidden_call` / `test_domain_has_no_clock_or_file_access` / `test_domain_has_no_filesystem_access` / `<module-level>` **全部未动** |
| `test_layering.py` | `['test_absolute_folding_matches_resolve_name']` | `_py_files` / `_package_of` / `_absolute` / `_imported_modules` / `_is_forbidden` / `test_production_layers_never_import_app_seed` / `<module-level>` **全部未动** |
| `test_models.py` | `[]`（**全部 25 个单元 SAME**） | —— |
| `daily.py` | `[]`（**全部 13 个单元 SAME**） | —— |

与派单的预期逐字相符；`<module-level>` 也没变（我没动任何模块 docstring），
这与上一轮的实测一致：尺子对 `ast.Module` 也剥 docstring。

**② docstring 变化清点**（哪些变了、行数怎么变）

```
test_domain_purity.py  _absolute 51->55 ; test_absolute_folding_matches_resolve_name 50->80 ;
                       test_domain_imports_stay_within_the_allow_list 79->79（Minor 3 换字）;
                       test_domain_has_no_clock_or_file_access 70->87（Ruling 68 配方）
test_layering.py       _imported_modules 29->38（配方对齐 + Minor 3）;
                       test_absolute_folding_matches_resolve_name 54->83
test_models.py         test_single_person_queries_are_index_served 118->125
daily.py               _fitness_batch 60->63
```

**③ 注释清点（AST 的盲区，单独交代）**

```
test_domain_purity.py  46 -> 50 条（+4：新格的 4 行注释；另 1 条 11->12 格改写）
test_layering.py       49 -> 55 条（+6：新格的 6 行注释；另 3 条改写：11->12 格 / :371 / :385）
test_models.py         97 -> 97 条（未动）
daily.py               55 -> 55 条（未动）
```

**④ 既有 5 条守卫 assert 逐字未动**

```
test_domain_purity.py  test_domain_imports_stay_within_the_allow_list   assert 1->1 逐字相同=True
test_domain_purity.py  test_domain_has_no_clock_or_file_access          assert 1->1 逐字相同=True
test_domain_purity.py  test_domain_has_no_filesystem_access             assert 1->1 逐字相同=True
test_layering.py       test_production_layers_never_import_app_seed     assert 2->2 逐字相同=True
合计 5 条，全部逐字未动
新测试里的 assert：purity 3 条 / layering 3 条，且**与基线逐字相同**（只改了 cases 这个数据列表）
```

**⑤ 硬规矩 #51**：两份 `_package_of` / `_absolute` 剥 docstring 后仍**逐字相同**、且都与基线
逐字相同；`_imported_modules` 两份**故意不同**（purity 版 yield 4 元、layering 版 yield 2 元），
这一点在 fix round 4 就已如此，本轮未动。

**⑥ 对照组（硬规矩 #53）——尺子自己被验过**（两个文件各跑一遍，全部通过）

```
① 注入 _absolute 语义变异（anchor 少减 1）      -> 报 DIFF 的单元 = ['_absolute']
② 只把新格的期望颜色 GREEN->RED                 -> 报 DIFF 的单元 = ['test_absolute_folding_matches_resolve_name']
③ 工作树自比                                    -> 报 DIFF 的单元 = []
④ 只改 docstring 一个字符：不剥时 DIFF=True、剥掉后=[]     -> 尺子真的在剥 docstring
⑤ 只改一行注释：AST 报 DIFF=False、逐单元报 DIFF=[]        -> 尺子对注释是**盲的**（故 ③ 单独交代）
```

### 4. 硬规矩 #52 / #57 亲跑清单（本轮写进源码的每一个值）

| 写进源码的值 | 在哪个文件 | 我亲跑的脚本 | 结果 |
| --- | --- | --- | --- |
| `level=2 module='indicators' names=['X']` | purity + layering | `p1_ruling67.py` | 逐字相符 |
| `_package_of(...) = ('app','domain','prescription')` | purity + layering | `p1_ruling67.py` | 逐字相符（两份都给这个） |
| `_absolute('indicators', 2, (...), 'X') = 'app.domain.indicators'` | purity + layering | `p1_ruling67.py` | 逐字相符（**没有照抄控制者给的值**） |
| `resolve_name('..indicators','app.domain.prescription') = 'app.domain.indicators'` | purity + layering | `p1_ruling67.py` | 逐字相符 |
| purity `_is_allowed(...) = True` / layering `_is_forbidden(...) = False` | 各自文件 | `p1_ruling67.py` | 逐字相符 |
| 改前 purity `(包深3,level2,GREEN)` = 0 格 / GREEN 2 格 | purity | `p1_ruling67.py`（改前跑） | 相符 |
| 42 格逐格相符、`FORBIDDEN_IO` 0 vs 2 | purity | `p5_synthtree.py` | 相符 |
| 字面配方 15 行全 RED / G1 `ValueError` / G2 G3 `只扫到 1 个 .py` | purity | `p5_synthtree.py` phase A | 相符 |
| layering 只改 `APP` → `ValueError`；1 个 `.py` → `AssertionError` | layering | `p10_layering_recipe.py` | 相符 |
| `be0f1af^` 上 479 passed（原样 / 删守卫各一次，rc 都 0） | purity + layering | `p8_wt_479.py` | 相符 |
| HEAD 上 `2 failed, 479 passed` | purity + layering | `p20_dispatch_claims.py` §(d) | 相符 |
| `EXPLAIN QUERY PLAN` detail 全串以 `SEARCH stratification_result ` 开头 | test_models | `p3_p4_plans_and_means.py` | 相符 |
| 20.665→20.66 / 21.035→21.03（截断）、`round` 分别 20.66 / 21.04 | daily | `p4_means.py` | 相符 |
| 12 条相对导入、全部 `level == 1`、全在 `app.db.models` | layering | `p6`+ 单行命令 | 相符（fix round 5 复跑仍是 12） |
| `_is_allowed('app.domain.seed')=True` / `_is_forbidden('app.domain.seed')=False` | purity | `p10_layering_recipe.py` | 相符 |

`daily.py` 里那四个整学期回放墙钟样本（20.48 / 20.85 / 20.89 / 21.18 s）我**没有复跑**
（脚本不在库内、需建两棵 worktree 各跑 n=2，评审 Ruling 76-① 已接受为不可复核）；
源码本来就标着「**历史实测，不被守卫**」，符合硬规矩 #39，我只给它们的**标签**补了舍入口径。

### 5. 硬规矩 #56 自查（`fr5_probes/p15_rule56.py`，原始输出 `OUT_p15.txt`）

对 `git diff -U0 HEAD` 的**全部新增行**（150 行）grep 判定/颜色/后果词
（`GREEN` / `RED` / `假绿` / `放行` / `变红` / `变绿` / `全绿` / `全红` / `offender` / `真绿`），
命中 28 行，逐行人工判主语：

- **20 行行内就有主语**（`本文件` / `本守卫` / `purity 侧` / `layering 侧` / `那一份` /
  `第一条守卫` / `第二三条守卫` / `两份` …）。
- **8 行行内没有主语词，但主语在紧邻的上一行或是被点名的函数**，逐条判定如下：
  1. purity「放行（矩阵第 2、3 行）。」← 上一行点名 `:func:`_is_allowed``（只存在于 purity）。
  2. purity「`level == 2` 的跨子包导入也必须仍被 `:func:`_is_allowed` 放行」← **本轮自查后补上的主语**
     （原写「也必须放行」，`p16_rule56_tighten.py` 收紧过）。
  3. purity「`_is_forbidden('app.domain.indicators')` 为 `False` → 不以 `app.seed` 开头就放行。」
     ← 上一行主语是「`test_layering` 那一份」，且 `_is_forbidden` 只存在于 layering。
  4./9. 两份的矩阵数据行 `("indicators", 2, ..., "GREEN")` ← 紧邻上方的注释块已分别写明
     「本文件（purity 侧）…→ GREEN」「本文件（layering 侧）… → GREEN」，且 `cases` 自己的
     注释早就声明「期望颜色是**判据**（本文件的白名单语义 / 本文件的 `app.seed` 前缀语义）」。
  5. purity「改前这一段照字面做会得到**全红**」← 下文逐条点名是哪条守卫抛什么异常。
  6. purity「『全红』既可能是**本文件那三条守卫**坏了…」← **本轮自查后补上的主语**。
  7. layering「上述两种写法**改前全绿**、改后全红」← **改前就有的句子**（本轮只把它挪了一行），
     同句前半已写「直接调用本测试函数」。
  8. layering 注释「`_is_forbidden(...) = False → 不以 app.seed 开头 → GREEN`」← 上一行是
     「本文件（layering 侧）判的是 app.seed 前缀」。

自查发现 2 处可以更好（第 2、6 条），已用 `p16_rule56_tighten.py` 补上行内主语并复核闸门。

### 6. 收工检查（全部亲跑）

| 项 | 结果 |
| --- | --- |
| `git status --short` | **0 行** ✓ |
| HEAD | **`7b84599`**（本轮唯一一个 commit，父是 `d00533c`）✓ |
| 是否 push | **没有** ✓ |
| `backend/pe.db` | **不存在** ✓ |
| `backend/data/seed/` | **0 文件** ✓ |
| `backend/data/national_standard_2014.csv` | **21412 B / sha256[:16] `D2C8E539E2FA0029` / CRLF 0** ✓ |
| `git worktree list` | 只有主工作树（P8 用完 `git worktree remove --force` + `prune`，`WT 还存在? False`）✓ |
| `$env:TEMP` 里本轮的残留 | `pe_fr5_A_*` / `pe_fr5_B_*` / `pe_fr5_O_*` 由脚本自删（打印 `True True`）；`pe_fr5_plan_7pprgs2k`（P3 那次崩在 `rmtree` 之前）已手动删除，`Get-ChildItem $env:TEMP -Filter "pe_fr5*"` 现为空 ✓ |
| 4 个文件的 CRLF | purity 691 / layering 441 / test_models 728 / daily 813，**每个文件 `CRLF 数 == LF 数`**（无裸 LF 混入）✓ |
| `import importlib.util` | 仍在两份的函数体内，未动（账本 Ruling 57）✓ |

⚠️ `$env:TEMP` 下另有 40 多个 `pe_*` 目录/文件是**前几轮**留下的（时间戳 09-30 至今天 08:57，
都早于本轮开工），不是本轮产物，我没动它们。若控制者要一并清掉请明示。

### 7. 我发现的派单错误（逐条判定 + 证据）

按账本 Ruling 45/51/65 的口径：**成立的就认、不成立的就辩、含糊的标歧义**。

| # | 派单原文 | 判定 | 证据 |
| --- | --- | --- | --- |
| **CE-fr5-1** | §1「`.superpowers\\sdd\\2026-10-06-实施计划02-智能处方引擎\\review_probes\\`（评审者留下的 15 个探针，gitignored，可复用）」 | **成立（路径错 + 数目错）** | `p20` §(e)：该路径 `exists() = False`；真实位置是**上一层** `.superpowers\\sdd\\review_probes\\`（全仓 glob 唯一命中）。目录里共 **28 个文件**，其中 `p*.py` 探针 **22 个**（p1–p21 + p3b），不是 15 个；评审报告正文引用过的不同探针是 **12 个**。**这与 Ruling 62 / #79 / 硬规矩 #55 完全同型：把读者指向一个东西不在的地方。** 后果：我按派单找不到它，只好自己另写 12 个探针（`fr5_probes/`），做完之后才在错误路径的上一层撞见评审者的那 22 个。 |
| **CE-fr5-2** | §2 Minor 3「fix 链新增散文里「本轮」**11 处**只有 1 处绑了轮次」+「grep 出全部 **11 处**」 | **歧义**（按「11 处未绑」读则成立，按字面读不成立） | `probe_benlun.py`：`git diff -U0 ad1d190 6784d57 -- backend` 的**新增行**里含「本轮」的是 **12 处**（purity 4 / layering 4 / daily 1 / test_models 3），其中 `test_models.py:612` 已绑 → **未绑 11 处**。所以「11」是「待修数」而不是「出现数」；字面读成「出现 11 处、1 处已绑 → 10 处待修」就少数了一处。评审报告 M-3 的标题同样写「出现 11 处」，而它自己正文那张表加起来是 12（4+4+1+3，另 2 处明标不在改动面内）——**标题与正文自相矛盾**。我按 12/11 的实测做。 |
| **CE-fr5-3** | §2 Minor 3「全部绑成 fix round N」 vs §3「`daily.py` **只许动** Minor 5 那两个散文标签」 | **成立（派单内部冲突，按字面不能同时满足）** | 11 处未绑里有 1 处是 `backend/app/pipeline/daily.py:206`（`p6` 定到 `6a2938f` = fix round 1）。处置见 §1.6：服从禁区、不动，并给出待打的一行补丁。 |
| **CE-fr5-4** | §2 Minor 1「前两个**才是** fix round 2 修的 bug，第三个是同一条 Ruling 36 的另一半」 | **半成立 / 措辞不成立** | 后半成立（bullet 2、3 都引 Ruling 36）。前半的「才是」不成立：`p7_fr2_code.py` 剥 docstring 后逐函数比 `1fa9941^`→`1fa9941`，**`_imported_modules` 的「一名一条展开」同样是 `1fa9941`（fix round 2）改的代码**（两份文件都是）。所以三处都是 round 2 修的，「两个」只是按 Ruling 计数。我据此写「两半都在 fix round 2 那一个 commit `1fa9941` 里落地」，没照抄派单措辞。 |
| **CE-fr5-5** | §2 Ruling 67「控制者推算 `_is_forbidden('app.domain.indicators')` 为 False → 在 layering 侧也是 GREEN，但这是控制者的**推算、不是实跑**」 | **不成立（不是错误，是正面行为）** | 推算本身**成立**（我实跑 `_is_forbidden('app.domain.indicators') = False`）。而控制者主动声明「这是推算不是实跑」正是硬规矩 #60 要的行为，不该记成错误。列在这里只是为了把判定写全。 |
| **CE-fr5-6** | §1「Plan 02 账本的裁定编号从 47 跳到 49，`Ruling 48` 号未使用（已知勘误）」 | **不成立为「错误」，但需要限定口径** | `p20` §(b)：正则 `Ruling (\\d+)` 在 Plan 02 账本里**能匹到 48**——但那是 Ruling 59 的正文与编号勘误行在**谈论**这个空号，不是定义行；标题级扫描确认 `**Ruling 47（` 在 `:509`、`**Ruling 49（` 在 `:562`，**中间没有 `**Ruling 48（`**。故派单的结论对，只是「未使用」应读作「**没有定义行**」。 |
| **CE-fr5-7** | §1「Plan 01 账本约 806 KB / Plan 02 账本约 123 KB」 | **不成立为错误（两个数都对）** | `p20` §(c)：805520 B = **805.5 KB**（十进制）≈ 806 KB ✓；122548 B = **122.5 KB** ≈ 123 KB ✓。（若按 KiB 读则是 787 / 120，派单用的是十进制 KB，与仓内其它字节数口径一致。） |
| **CE-fr5-8** | §0「`d00533c` / `ef48d33` / `73313f7` 三个都只是 `Document/` 下的文档 commit；代码基线是 `6784d57`」 | **不成立为错误（逐字为真）** | `p20` §(a)：三个 commit 各自的 `git diff --name-only <c>^ <c>` 都**只有** `Document/2026-10-06-实施计划02-智能处方引擎.md`；`git diff --name-only 6784d57 d00533c` 也只有它。故 AST 尺子取 `6784d57` 是对的，我照做了。 |
| **CE-fr5-9** | §1「硬规矩 #19/#30/#32/#35/#39/#42/#46/#47 的定义在 Plan 01 账本；#48–#60 在 Plan 02 账本」 | **不成立为错误（抽查全部相符）** | `p20` §(f)：#19/#30/#32/#35/#39/#42/#46/#47 在 Plan 01 账本各有 1–2 处 `硬规矩 #N：` 形式的定义行、在 Plan 02 账本 **0** 处；#48/#50/#51/#52/#53/#56/#57/#58/#59/#60 反过来。**这一条正是 Ruling 74 / 硬规矩 #55 要求的修法，控制者这轮做到了。** |

**小结：9 条里 3 条成立（CE-fr5-1 / 3 / 4 的措辞半条）、1 条歧义（CE-fr5-2）、5 条不成立
（其中 CE-fr5-5 / 8 / 9 是派单做对了的地方，我按 Ruling 76-⑦ 那种「对控制者产物的正面确认」
显式记下来）。** 最重的一条是 **CE-fr5-1**：它是 Ruling 62 / #79 / 74 那个形态（把读者指向
东西不在的地方）的**第四次**发生，而硬规矩 #55 就是为了它立的——立它的同一轮里，控制者
在 §1 别处把 #19–#47 的归属写对了（CE-fr5-9），却在探针路径上又犯了一次。

### 8. 未尽事项 / 关切

1. **`daily.py:206` 那处「本轮」未绑**（§1.6）。要么授权我打那一行补丁，要么折进 Task 2 预检清单。
   这是本轮唯一没有完全落地的 finding。
2. **账本 Ruling 73 / CE-3 的矩阵颜色计数已过时**：本轮加格后 purity 是 RED 9 / GREEN **3**、
   layering 是 RED 8 / GREEN **4**（原记 9/2 与 8/3）。请控制者在账本里给那两个数绑时点
   （同 Ruling 75 / CE-4 对「2616 行」的处置口径）。
3. **`cases` 矩阵仍是手写的**（Ruling 56 已转 Task 2）：本轮把 11 格加到 12 格，
   `package` 入参仍是手写四/三元组，Task 2 建了 `app/domain/prescription/` 之后
   这些形状会变成真仓可扫的东西——那时按 Ruling 66 的建议换成「扫真仓每个 `.py` 与
   `resolve_name` 对拍」会一次性解决 Ruling 54 / 56 / 67 三条。
4. **两份 docstring 的重复度又涨了一截**（C-fr4-3 的量化）：`test_absolute_folding_matches_resolve_name`
   的 docstring 现在 purity 80 行 / layering 83 行，其中约 30 行是逐字或近逐字重复的
   （Minor 1/2 那段 11 行在两份里只差一个模块名）。Plan 03 若加第三个守卫，这一段会变成 3 份。
   不推翻 Ruling 33，只是把量化再往前推一格。
5. **`review_probes` 的路径**（CE-fr5-1）：如果控制者希望后续轮次真能复用评审者的探针，
   派单里应写 `.superpowers\\sdd\\review_probes\\`（在 sdd 根下，不在 plan 目录下）。
6. **本轮没有复跑的既有陈述**：`daily.py` 的四个墙钟样本（Ruling 76-①）、
   `test_models.py` 的 B/A 四次序列（Ruling 76-③）、purity `:392` 终审 A 的「14 种写法」
   （Ruling 76-⑤）。三处源码都已诚实标注「历史实测 / 本轮没有逐条复跑」，符合硬规矩 #39，
   我一个都没动。

### 9. 本轮探针清单（`fr5_probes/`，gitignored）

| 脚本 | 用途 |
| --- | --- |
| `probe_benlun.py` | fix 链新增行里的「本轮」逐处定位（12 处） |
| `p1_ruling67.py` | Ruling 67：AST + `_package_of` / `_absolute` / `_is_allowed` / `_is_forbidden` / `resolve_name` + 两份矩阵逐格计数 |
| `p3_p4_plans_and_means.py` | Minor 4 的 `EXPLAIN QUERY PLAN` 四列全打（P4 那半有格式化 bug，已由 `p4_means.py` 重做） |
| `p4_means.py` | Minor 5 的均值 / 极差 / 百分比 / 倍数算术 |
| `p5_synthtree.py` | Ruling 68：phase A 字面配方（15 行全红）+ phase B 补正配方（42 格）+ `FORBIDDEN_IO` 0 vs 2 |
| `p6_round_of_benlun.py` | 12 处「本轮」逐个 commit 定轮次 |
| `p7_fr2_code.py` | `1fa9941^`→`1fa9941` 剥 docstring 后逐函数比，列出 fix round 2 真正改动的代码 |
| `p8_wt_479.py` | `be0f1af^` 的 `git worktree` 上跑两次全量（原样 / 删守卫），跑完删 worktree |
| `p10_layering_recipe.py` | Minor 6 的两侧对照 + layering 侧合成树配方的三条实测 |
| `p11_repr.py` / `p12_repr_all.py` | 用 `repr()` 打原文，避免手抄缩进出错（第一版编辑脚本就是因为把 4 空格抄成 5 空格而 old 串 0 命中） |
| `do_edits.py` / `do_edits2.py` | 落盘脚本（v1 手抄 old 串失败，v2 改成「按 key 行从磁盘取 old」）+ 双向闸门 |
| `p13_mutation.py` | 7 相位变异验收 + AST 确认 + 字节还原核 sha256 |
| `p14_astdiff.py` | 硬规矩 #32 的改动面自证（含 6 项对照组） |
| `p15_rule56.py` | 硬规矩 #56 自查：对 diff 新增行 grep 判定词、逐行判主语 |
| `p16_rule56_tighten.py` | 自查后补的两处行内主语 |
| `p17_review_final.py` | 落盘后把所有改动区段打出来人读一遍 |
| `p18_rewrap.py` | 四处散文重排（纯 docstring） |
| `p19_commitmsg.py` | 用 UTF-8 写 commit message 临时文件（避开 PowerShell 的 `Add-Content` ANSI 坑） |
| `p20_dispatch_claims.py` | 派单事实性断言逐条亲验（§7 的证据来源），含 HEAD 上「2 failed, 479 passed」的复现 |

**编辑工具本轮的使用情况**：对**入库的 4 个文件**一律用 python 按字节写（0 次编辑工具），
落盘闸门 26 + 2 + 4 = **32 处全部双向查过**（新串在、旧标记不在）。对自己的探针脚本用了
2 次 `SearchReplace`，两次都在随后的运行里得到了预期行为，即都真落盘了——**本轮没有遇到
「报成功而磁盘未写」**，但纪律没松。

**报告文件本身的口径**：追加前 `task-1-report.md` 是 **3298 LF 行 / 243343 B / CRLF 0**，
sha256[:16] `%(SHA16)s`；本节以 `\\n` 追加、整个文件按字节写回，落盘后复核
「`## fix round 5` 恰出现 1 次」+「原有 15 个 `## ` 标题一个不少」+「前 3298 行逐字未变」。
"""

SEC = SEC % {
    "HEAD": HEAD,
    "ROWCHK": "\n".join("  %s: %d 格；新格在第 %s 行；('',2,('app','db','models')) 在第 %s 行；RED %d / GREEN %d"
                        % r for r in ROWCHK),
    "SHA16": SHA_BEFORE[:16],
}

new = old.rstrip("\n") + "\n" + SEC
if not new.endswith("\n"):
    new += "\n"
REPORT.write_bytes(new.encode("utf-8"))

# ---------------------------------------------------------------- 落盘闸门（双向）
back = REPORT.read_bytes()
t = back.decode("utf-8")
print()
print("=== 落盘闸门 ===")
print("  bytes %d -> %d ; LF lines %d -> %d ; CRLF %d -> %d"
      % (OLD_BYTES, len(back), OLD_LINES, len(t.splitlines()),
         back.count(b"\r\n"), back.count(b"\r\n")))
print("  sha256[:16] %s -> %s" % (SHA_BEFORE[:16], hashlib.sha256(back).hexdigest()[:16]))
checks = [
    ("新串在：'## fix round 5' 恰 1 次", t.count("## fix round 5") == 1),
    ("新串在：commit 哈希", ("commit `%s`" % HEAD) in t),
    ("新串在：CE-fr5-1", t.count("CE-fr5-1") >= 2),
    ("新串在：M6 那一行", "只有新格能抓住 M5" in t),
    ("新串在：481 passed in 55.53s", "481 passed in 55.53s" in t),
    ("新串在：399 stmts 那一行", "TOTAL 399 stmts / Miss 0 / 114 branch / BrPart 0 / 100%" in t),
    ("旧内容在：新文件以「原文（去掉尾部空行）+ 一个换行」开头",
     t.startswith(old.rstrip("\n") + "\n")),
    ("旧标题一个不少（15 个 '## '）",
     all(h in t for h in [l for l in old.splitlines() if l.startswith("## ")])),
    ("CRLF 仍为 0", back.count(b"\r\n") == 0),
    ("本节没有追加两遍", t.count("### 9. 本轮探针清单") == 1),
]
allok = True
for name, ok in checks:
    print("  %s %s" % ("OK  " if ok else "FAIL", name))
    allok = allok and ok
print()
print("闸门结论:", "PASS" if allok else "FAIL")
print("最终：%d LF 行 / %d B / CRLF %d" % (len(t.splitlines()), len(back), back.count(b"\r\n")))
print("git status --short =", repr(subprocess.run(["git", "status", "--short"], cwd=str(ROOT),
      capture_output=True).stdout.decode("utf-8", "replace")))
sys.exit(0 if allok else 1)

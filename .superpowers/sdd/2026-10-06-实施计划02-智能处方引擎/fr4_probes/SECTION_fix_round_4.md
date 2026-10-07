## fix round 4

**派单**：Ruling 54（给两份 `_package_of` 补回归断言，**塞进已有的那条测试里、passed 数不变**）
+ Ruling 55（`test_domain_purity.py` 模块 docstring 说「三条守卫」而文件里有 4 个 `test_*`）。
禁区：只许动 `test_domain_purity.py` 与 `test_layering.py`，生产代码一个字节都不许动，
不得改现有 5 条守卫 `assert` 的语义，**不新增测试函数**，`import importlib.util` 维持在
函数体内（Ruling 57）。
**基线**：HEAD = `73313f7`（亲验 `git diff --name-only be0f1af 73313f7` 只含
`Document/2026-10-06-实施计划02-智能处方引擎.md` 一个文件，故**代码基线取 `be0f1af`**，
两个守卫文件自 `be0f1af` 起逐字未变），481 passed / `app/domain` 分支覆盖 100%。
开工时亲验：`git status --short` = **0 行**、`git rev-parse --short HEAD` = `73313f7`、
分支 `feature/plan-02-prescription-engine`、`git config core.autocrlf` = `true`、
`python -V` = `Python 3.11.1`、仓库根与 `backend/` 下**都没有 venv 目录**（硬规矩 #48）。
两个守卫文件开工时的 sha256[:16] = `dffa51f460826436` / `a5afd212bd485ef4`，与 fr3 报告
收工值**逐字相符**，即工作树确实就是 `be0f1af` 的状态。
**产出**：一个 commit **`6784d57`**（不 push、不动 `main`），**481 passed 不变**
（本轮新增测试函数 **0** 条，与派单要求逐字相符）。

行号一律 **shell 口径**（python 读字节数行；本轮实测 `Read` 工具在 `test_layering.py` 上
偏移 **−2**、在 `progress.md` 的 `:300` 处偏移 **0** 而在 `:446`/`:450`/`:588` 处偏移 **−1**、
在 `test_domain_purity.py` 上偏移 **0**，见 fr4.7-④）。改前引用绑定 `be0f1af`、
改后引用绑定 `6784d57`。

| 文件 | 改前行数 | 改后行数 | 字节 | CRLF | 裸LF | sha256[:16]（改后） |
|---|---|---|---|---|---|---|
| `tests/architecture/test_domain_purity.py` | 573 | **635** | 37435 → 41613 | 572 → 634 | 0 | `440f7167610df187` |
| `tests/architecture/test_layering.py` | 342 | **397** | 22144 → 25789 | 341 → 396 | 0 | `50d776680defc25e` |

`git diff --numstat be0f1af HEAD -- backend/` = purity `70 8`、layering `61 6`；commit 汇总
`2 files changed, 131 insertions(+), 14 deletions(-)`（70+61=131、8+6=14，自洽）。
`git diff --name-only 73313f7`（= 本轮工作树改动面）只含这两个守卫文件，
`git diff --name-only be0f1af HEAD -- backend/app/` 命中 **0** 个。

落盘方式：**全程 python 按字节写**（`fr4_probes/pe_fr4_edit.py` / `pe_fr4_edit2.py` /
`pe_fr4_edit3.py`），不用编辑工具改这两个守卫文件。每处替换都按**行号区间 + 指纹**双确认、
自底向上改，落盘后重新读字节逐处 `assert` 新串命中恰 1 次 / 旧串命中 0 次 / 行尾纯 CRLF。
`git checkout` / `git restore` / `git switch` **一次都没用**（基线内容全部用 `git show`
取到内存，并按账本记的坑把 blob 的 LF 换成 CRLF 后才落盘，见 fr4.3 的 M6）。

⚠️ **本轮亲身撞上「编辑工具报成功而磁盘未写」8 次**（工具/磁盘分歧家族的第 48–55 次）：
我对**本报告草稿** `fr4_probes/SECTION_fix_round_4.md` 连做 8 次替换，工具每次都回
「success」并**打印了看起来正确的 diff**，而 `pe_fr4_section_check.py` 逐串实测
**8 / 8 未落盘**（新串命中 0、旧串命中 1）。同一批工具调用对 `fr4_probes/*.py` 的 9 次替换
**全部落盘成功**（每次都用 python 读回 + 实际跑通验证过）。故本轮的处置是：**整文件重写**
（`Write` 落盘后同样读回核串），并把「每次编辑后 shell 读回」从守卫文件扩到**所有**文件。
派单 §0 那条警告是对的，而且它没说的部分是：**失败时会连 diff 一起伪造出来**，只看工具回执
根本发现不了。

### fr4.0 闸门（全部亲跑，命令逐字给出）

| 闸门 | 命令 | 结果 |
|---|---|---|
| 全量测试 | `cd backend; python -m pytest -q` | **481 passed in 101.12s**，rc 0（与基线逐字相同，**passed 数未变**） |
| 全量 `-W error` | `cd backend; python -m pytest -q -W error` | **481 passed in 105.68s**，rc 0，0 error |
| domain 分支覆盖 | `cd backend; python -m pytest -q --cov=app/domain --cov-branch --cov-report=term-missing` | `TOTAL **399** stmts / Miss **0** / **114** branch / BrPart **0** / **100%**`；同一次跑 **480 passed, 1 skipped in 196.34s** |
| 那 1 条 skip 是谁 | 读 `backend/tests/pipeline/test_backfill.py` | `:181` 是 `if sys.gettrace() is not None:`、**`:182` 是 `pytest.skip(`** → 与派单点名的 `test_backfill.py:182` trace-hook 自觉跳过逐字相符，既有行为 |
| 架构守卫单跑 | `cd backend; python -m pytest tests/architecture -q -W error` | **6 passed in 0.17s**（基线 6 → 6，**没有新增测试函数**），0 error |
| 硬规矩 #32（逐顶层单元 + 四组对照） | `python fr4_probes/pe_fr4_astdiff.py .` | **PASS**（rc 0），见 fr4.4 |
| 硬规矩 #51（两份 `_package_of` / `_absolute`） | 同上 ⑤ 段 | **PASS**，见 fr4.5 |
| 变异验收（8 相位） | `python fr4_probes/pe_fr4_mutation.py .` | **失败项 0 / 8**（rc 0），见 fr4.3 |
| 硬规矩 #52（写进 docstring / 断言消息的每个值） | `python fr4_probes/pe_fr4_r52.py .` | **PASS**（rc 0），见 fr4.6 |
| Ruling 42 那句「`:139` 是正确的」复核 | `python fr4_probes/pe_fr4_ruling42b.py .` | **不成立**（rc 0），见 fr4.7-⑥ 与 fr4.8-① |
| 开工预检（4 个形状 + 两个 docstring 的举例 + 计数陈述） | `python fr4_probes/pe_fr4_precheck.py .` | 见 fr4.1 / fr4.2 |
| 「后果」两格的折算实跑 | `python fr4_probes/pe_fr4_compose.py .` | 见 fr4.1 |
| 报告里引的计数与行区间 | `python fr4_probes/pe_fr4_counts.py .` | 见 fr4.2 / fr4.5 |
| 本报告草稿的落盘复核 | `python fr4_probes/pe_fr4_section_check.py .` | 见上面那条 ⚠️ |

禁区与行尾（python 直接读字节，不走 PowerShell 管道）：

```
backend/pe.db exists: False
backend/data/seed/ exists: True  entries: 0
data/national_standard_2014.csv bytes=21412 sha256[:16]=D2C8E539E2FA0029 CRLF=0
backend/tests/architecture/test_domain_purity.py   bytes=41613 CRLF=634 裸LF=0 BOM=False 乱码=False
backend/tests/architecture/test_layering.py        bytes=25789 CRLF=396 裸LF=0 BOM=False 乱码=False
```

收工时 `git status --short` → **0 行**；`git log --oneline -2` = `6784d57` 一个 commit 在
`73313f7` 之上；`git diff --name-only HEAD~1 HEAD` = 那两个守卫文件；分支仍是
`feature/plan-02-prescription-engine`（未 push）。仓库根无临时目录：`.pytest_cache/` 与
`backend/.pytest_cache/` 的 mtime 是 **2026-09-28 18:01 / 17:58**，早于本轮，非我造；
`backend/.coverage` 是本轮 `--cov` 那次跑更新的（`.gitignore:7` 忽略）。
`$env:TEMP` 下我的 `fr4_astdiff.txt` / `fr4_mut.txt` / `fr4_r52.txt` / `fr4_diff_layering.txt`
4 个文件已 `os.unlink`（前 3 个先复制进 `fr4_probes/OUT_*.txt`），commit-message 临时文件
`pe_fr4_commitmsg.txt` 已在 `pe_fr4_commit.py` 里删除。取证脚本 **12 个 + 3 份输出**收在
`.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/fr4_probes/`（`.gitignore:10`、不入库、
可一键重跑；`pe_fr4_counts.py` 口径：合计 16 个条目 = 12 个 `.py` + 3 个 `OUT_*.txt` +
本报告这一节的草稿 `SECTION_fix_round_4.md`）。本轮**没有造合成树**（`_package_of` 是纯路径
运算，不需要临时目录）。

### fr4.1 Ruling 54 — 两份 `_package_of` 的回归断言 ✅

**开工先把派单点名的 4 个形状实跑一遍**（`pe_fr4_precheck.py` ①），确认两份 `_package_of`
给出**同一个**值、且与派单逐字相符：

| `BACKEND /` 之下的相对路径 | 磁盘上存在 | `_package_of` 实跑值（两份一致） |
|---|---|---|
| `app/db/models/organisation.py` | ✅ | `('app', 'db', 'models')` |
| `app/db/models/__init__.py` | ✅ | `('app', 'db', 'models')` ← **与同目录普通模块同包，这一格是 `parts[:-1]` 的全部理由** |
| `app/domain/indicators.py` | ✅ | `('app', 'domain')` |
| `app/domain/prescription/match.py` | ❌（Task 2 才会出现） | `('app', 'domain', 'prescription')` |

**改法**：在两个文件的 `test_absolute_folding_matches_resolve_name` **末尾各加一段**
（purity 改后 `:313-362`、layering 改后 `:299-348`，**各 50 行**），**不新增测试函数**。
三件事：

1. **值断言**（派单要求 2）：`pkg_cases` 四行 `(相对路径, 正确的包, 错形状)`，逐格调
   `_package_of(BACKEND / rel)`，`!= 正确的包` 就进 `pkg_offenders`。
2. **错形状断言**（派单要求 3，硬规矩 #50 的红档）：同一格里 `== ("app","db","models",
   "organisation")` 一类**模块路径**也进 `pkg_offenders`。变异下这两条会**同时**触发
   （4 格值错 + 4 格「是模块路径」），fr4.3 的断言原文里 8 行都在。
3. **后果断言**（超出派单，见 fr4.8-②）：把 `_package_of` 的输出**直接喂给** `_absolute`，
   与 `importlib.util.resolve_name` 对拍 2 格 —— 这样「假绿」这件事是**跑出来的**、
   不只是写在断言消息里（硬规矩 #52 的精神：能跑的别只写成散文）。

`pkg_offenders == []` 的断言消息按派单要求 4 写明后果，**两个文件各写自己的那一份**
（派单给的那句「折成 `app.db.seed`、不再以 `app.seed` 开头」只在 layering 成立，见
fr4.7-③）：purity 侧写「`app/domain/x.py` 里的 `from ..seed import …` 折成
`app.domain.seed`、命中白名单前缀 `app.domain.` → 本文件的守卫假绿（`test_layering.py`
那一份同理：… `app.db.seed` …）」，layering 侧反过来。两段消息里的 4 个折算串**全部实跑过**
（`pe_fr4_r52.py`，见 fr4.6）。消息末尾**不写死 481**（那个数会随后续 Task 漂），
只写「而在本段断言加上之前，这么改一次全量测试都照样通过」，其依据是 fr4.3 的 M6。

「后果」两格的实跑值（`pe_fr4_compose.py`，正常 / 变异两列）：

| 源文件 + 写法 | `_package_of` 正常 | 折算（正常） | `_package_of` 变异后 | 折算（变异后） | purity 判定 | layering 判定 |
|---|---|---|---|---|---|---|
| `app/domain/indicators.py` + `from ..seed` | `('app','domain')` | `app.seed` | `('app','domain','indicators')` | `app.domain.seed` | RED → **GREEN（假绿）** | RED → **GREEN（假绿）** |
| `app/db/models/organisation.py` + `from ...seed` | `('app','db','models')` | `app.seed` | `('app','db','models','organisation')` | `app.db.seed` | RED → RED | RED → **GREEN（假绿）** |

`resolve_name('..seed', 'app.domain')` = `resolve_name('...seed', 'app.db.models')` =
`'app.seed'`，与正常列逐字相同 —— 即判据锚在 Python 自己的语义上，不是锚在我写的元组上。

**docstring 跟着改**（派单要求 5）：两个文件「本测试守不住什么（硬规矩 #39）」段的**第一条**
原文都是「``package`` 入参是**手写的**，故 `_package_of` 不在守卫范围内：谁把它改成返回
『模块名』而不是『包名』，本测试**照样全绿**」——**这一条现在不再成立**，已改成新的能力边界
（两个文件逐字同文，硬规矩 #51）：

```
* :func:`_package_of` 由本测试**末尾那一段**看着（Plan02 Ruling 54），但**只在枚举到
  的那 4 个形状上**：``app/db/models/organisation.py`` 与 ``app/db/models/__init__.py``
  （包深 3；两者必须给出**同一个**包——这一格正是 ``parts[:-1]`` 这个写法的全部理由）、
  ``app/domain/indicators.py``（包深 2）、``app/domain/prescription/match.py``（包深 3，
  Task 2 才会出现的形状；``_package_of`` 是纯路径运算、不碰文件系统，故可以先断言）。
  **没枚举进去的包深（包深 4 及更深）不被覆盖**；上面那 11 格矩阵的 ``package`` 入参
  仍是**手写的**，故矩阵与末尾那一段互不覆盖、谁也不替代谁。
```

第二、三条边界（不扫真仓 / 矩阵有限）逐字未动。

### fr4.2 Ruling 55 — 「三条守卫」的计数 ✅

**先 grep 确认那句的确切位置和措辞**（`pe_fr4_precheck.py` ④，不照抄派单的转述）：
`test_domain_purity.py` 模块 docstring 的**第 8 行**（= 文件第 8 行，shell 口径，基线
`be0f1af`）原文逐字是

```
三条守卫，Plan 02 Task 1 全部改写过一次，改动理由各写在对应测试的 docstring 里：
```

而该文件的 `test_*` 实测 **4 个**：`test_absolute_folding_matches_resolve_name` /
`test_domain_imports_stay_within_the_allow_list` / `test_domain_has_no_clock_or_file_access` /
`test_domain_has_no_filesystem_access`。改成（改后 `:8-11`，原句的其余部分逐字保留）：

```
本文件有 **4 个 ``test_*``**：**三条架构守卫** + 一条**辅助函数的单元测试**
（``test_absolute_folding_matches_resolve_name``，测的是 ``_absolute`` / ``_package_of``
这两个辅助函数，**不是第四条守卫**；Plan02 Ruling 46/54）。三条守卫 Plan 02 Task 1 全部
改写过一次，改动理由各写在对应测试的 docstring 里：
```

**同文件里另有 17 处「三条 / 第三条 / 两道」的表述，逐条核对过、全部未动**
（`pe_fr4_counts.py` ①，shell 口径行号绑定 `6784d57`；全文件正则 `三条|第三条|两道` 共命中
**19** 处，减去本轮新写的 `:8`/`:10` 两处即 17）：`:15`「三条都加 `len(scanned) >= 5` 的空转
守卫」、`:64`「第三条守卫仍是子串匹配」、`:68`「同时绕过时钟与 `open` 两道守卫」、
`:91`（断言消息）「三条守卫会一起假绿」、`:221`「三条的复现命令是同一条」（**指 fix round 3
那三种变异**，不是守卫）、`:377`/`:380`/`:388`/`:389`/`:392`/`:405`（基线守卫的合成树实测段）、
`:487`/`:525`/`:556`/`:569`（G1/G2/G3 探针实测表）、`:574`「第三条子串守卫」、
`:611`「子串黑名单，第三条守卫」。它们说的都是**那三条架构守卫**（或那三种变异），与
`test_*` 的个数无关，改了反而会把真话说错。

**`test_layering.py` 按派单要求一并 grep：无同类计数陈述，故未改。** 证据：该文件
`test_*` 实测 **2 个**，模块 docstring（`:1-47`）通篇用**单数**「本守卫」（`:18`「**本守卫
落地时抓到的 4 处 offender**」、`:29`「之后本守卫转绿」、`:35-36`「不在本守卫范围内」、
`:38`「**本守卫不覆盖什么**」），`4 处 offender` 数的是 offender 而不是守卫条数；
正则 `[一二三四五六七八九十]+\s*条|三条|两道` 在该文件模块 docstring 内**没有**任何关于
守卫条数的命中。读者数出 2 个 `test_*` 也不会与「本守卫」这个单数主语冲突，故派单那句
「如果有同类问题一并修」的条件**不成立**，我没改（改了就是无中生有的 churn）。

### fr4.3 变异验收（8 相位，两份分别做，硬规矩 #50 / #51 / #53）

`pe_fr4_mutation.py`（rc 0）。**派单 ⑤ 的要求逐字落地**：每次变异都在**剥 docstring 后的
`ast.dump`** 上确认「真的改了代码」，并**另加一组「只改 docstring」的对照**证明这个口径
不恒真（控制者上一轮踩过的 #72 形态）。每次变异后按**字节**还原并核 sha256。

先跑变异算子的 AST 自证（两个文件 × 3 个算子）：

```
purity    parts[:-1] -> parts    文本变了=True 剥docstring后AST变了=True（应为 True）OK
purity    等价改写               文本变了=True 剥docstring后AST变了=True（应为 True）OK
purity    只改 docstring         文本变了=True 剥docstring后AST变了=False（应为 False）OK
layering  parts[:-1] -> parts    文本变了=True 剥docstring后AST变了=True（应为 True）OK
layering  等价改写               文本变了=True 剥docstring后AST变了=True（应为 True）OK
layering  只改 docstring         文本变了=True 剥docstring后AST变了=False（应为 False）OK
```

| 相位 | 变异 | purity | layering | pytest |
|---|---|---|---|---|
| **M0** | 不变异（**对照 GREEN**，#53） | GREEN ✅ | GREEN ✅ | `2 passed`，rc 0 |
| **M1** | `parts = py.relative_to(BACKEND).with_suffix("").parts` + `return tuple(list(parts)[: len(parts) - 1])`（**语义等价、AST 变了**，#53 的「尺子不恒红」对照） | GREEN ✅ | GREEN ✅ | `2 passed`，rc 0 |
| **①（M2）** | `parts[:-1]` → `parts`，**只变异 layering** | **GREEN** ✅（未被变异） | **RED** ✅ | `1 failed, 1 passed`，rc 1 |
| **②（M3）** | `parts[:-1]` → `parts`，**只变异 purity** | **RED** ✅ | **GREEN** ✅（未被变异） | `1 failed, 1 passed`，rc 1 |
| **M4** 额外 | 同一变异，**两份都变异** | **RED** ✅ | **RED** ✅ | `2 failed`，rc 1 |
| **M5** 额外 | 两份都变异，但只跑**旧的 4 条守卫**（`-k not test_absolute_folding_…`） | — | — | `4 passed, 2 deselected`，**rc 0** |
| **M6** 额外 | **基线 `be0f1af`** 的两份文件 + 同一变异，跑**全量** | — | — | **`481 passed in 105.24s`，rc 0** |

**失败项 0 / 8**。「只变异一份时另一份保持绿」（①②）是硬规矩 #51 的正面证据。**M5/M6 是
Ruling 54 那个口子在改前真的存在的实测**：变异下 4 条架构守卫**无感**（M5，rc 0），而在
**基线**上做同一变异、全量 **481 passed / rc 0**（M6）—— 即「守卫假绿、而全部 481 条测试
仍然通过」不是推理，是跑出来的。

**M6 的基线取法**（按账本记的坑做归一化）：`git show be0f1af:<path>` 取到内存，
LF → CRLF 后落盘。亲验：purity blob(LF) **36863 B** → CRLF **37435 B**（差 **572** =
CRLF 行数 572）、sha256[:16] `dffa51f460826436`；layering blob(LF) **21803 B** →
CRLF **22144 B**（差 **341** = CRLF 行数 341）、sha256[:16] `a5afd212bd485ef4`。
两个 sha 与本轮**开工前**亲测的工作树值逐字相符（脚本里把这两个值**写死成期望值**再
`assert`，不是拿 `git show` 跟自己比，避免循环自证）。

**红的是哪条断言**（`check()` 从 pytest 输出里抓的断言消息本体，不是收集错误；M2 与 M3
的 10 行 offender 逐字相同，只是红的那一份不同）：

```
E  AssertionError: _package_of 返回的不是**包**（Plan02 Ruling 37/54）：parts[:-1] 写成 parts 会让它返回**模块路径**，…
E    _package_of(BACKEND / 'app/db/models/organisation.py') = ('app', 'db', 'models', 'organisation')，应为**包** ('app', 'db', 'models')
E    _package_of(BACKEND / 'app/db/models/organisation.py') = ('app', 'db', 'models', 'organisation') 是**模块路径**、不是包（parts[:-1] 被写成了 parts）
E    _package_of(BACKEND / 'app/db/models/__init__.py') = ('app', 'db', 'models', '__init__')，应为**包** ('app', 'db', 'models')
E    _package_of(BACKEND / 'app/db/models/__init__.py') = ('app', 'db', 'models', '__init__') 是**模块路径**、不是包（parts[:-1] 被写成了 parts）
E    _package_of(BACKEND / 'app/domain/indicators.py') = ('app', 'domain', 'indicators')，应为**包** ('app', 'domain')
E    _package_of(BACKEND / 'app/domain/indicators.py') = ('app', 'domain', 'indicators') 是**模块路径**、不是包（parts[:-1] 被写成了 parts）
E    _package_of(BACKEND / 'app/domain/prescription/match.py') = ('app', 'domain', 'prescription', 'match')，应为**包** ('app', 'domain', 'prescription')
E    _package_of(BACKEND / 'app/domain/prescription/match.py') = ('app', 'domain', 'prescription', 'match') 是**模块路径**、不是包（parts[:-1] 被写成了 parts）
E    app/domain/indicators.py 里的 from ..seed import …：用 _package_of 的结果折算得到 'app.domain.seed'，而 resolve_name('..seed', 'app.domain') = 'app.seed'
E    app/db/models/organisation.py 里的 from ...seed import …：用 _package_of 的结果折算得到 'app.db.seed'，而 resolve_name('...seed', 'app.db.models') = 'app.seed'
```

**三重还原取证**（脚本末尾实跑）：

```
purity    sha256[:16]=440f7167610df187 与原始一致=True 41613 字节 CRLF=634 裸LF=0
layering  sha256[:16]=50d776680defc25e 与原始一致=True 25789 字节 CRLF=396 裸LF=0
git status --short:  M backend/tests/architecture/test_domain_purity.py
                     M backend/tests/architecture/test_layering.py
（= 本轮自己的两处改动；相位之间的还原一律核 sha256 一致，未用 git checkout / git restore）
```

### fr4.4 硬规矩 #32 闸门（本轮形态：逐顶层单元 + docstring 全量清点 + 注释全量清点 + 四组对照）

`pe_fr4_astdiff.py`（rc 0）。本轮**没有新增顶层单元**，故自证的形状与 fr3 不同：预期
「有差异的顶层单元」= `test_absolute_folding_matches_resolve_name`（两个文件各一）。

```
=== ⓪ 改动面 ===
   git diff --name-only HEAD(73313f7):
      backend/tests/architecture/test_domain_purity.py
      backend/tests/architecture/test_layering.py
   合计 2 个文件；生产代码（backend/app/**）命中 = 0
   git diff --numstat HEAD:  70 8 purity / 61 6 layering
   git diff --name-only be0f1af -- backend/      = 那两个守卫文件
   git diff --name-only be0f1af -- backend/app/  = []（禁区，必须空）

=== ① 剥 docstring 后逐顶层单元比（基线 be0f1af）===
test_domain_purity.py：_domain_files / _assert_not_empty / _imported_modules / _package_of /
   _absolute / _is_allowed / test_domain_imports_stay_within_the_allow_list / _dotted /
   _hit_forbidden_call / test_domain_has_no_clock_or_file_access /
   test_domain_has_no_filesystem_access / <module-level>  → **全部「未动」**
   AST 变了  test_absolute_folding_matches_resolve_name
   → 有差异的顶层单元 = ['test_absolute_folding_matches_resolve_name']
test_layering.py：_py_files / _package_of / _absolute / _imported_modules / _is_forbidden /
   test_production_layers_never_import_app_seed / <module-level>  → **全部「未动」**
   AST 变了  test_absolute_folding_matches_resolve_name
   → 有差异的顶层单元 = ['test_absolute_folding_matches_resolve_name']
```

**⚠️ 派单 §3 预期的 `<module-level>` 实测「未动」**：尺子对 `ast.Module` 也剥 docstring，
故模块 docstring 的改动**不会**让 `<module-level>` 报 DIFF（派单用「若模块 docstring 算在
里面」限定过，这里给出实测答案：**不算**）。为免这个盲区藏东西，脚本另立两节把 AST 看不见
的两类东西全量清点：

```
=== ② docstring 全量清点 ===
test_domain_purity.py  变了 3 处：<module>（Ruling 55 的计数）、_absolute（fr4.8-① 的折算串更正）、
                       test_absolute_folding_matches_resolve_name（「守不住什么」第一条）
                       其余 9 个单元（含 _package_of）逐字未动
test_layering.py       变了 1 处：test_absolute_folding_matches_resolve_name
                       其余 6 个单元（含 <module>、_package_of、_absolute）逐字未动
（四处 diff 全文见 fr4_probes/OUT_astdiff.txt 的 ② 段，都是 unified diff 逐行贴的）

=== ③ 注释全量清点（AST 对注释同样是盲的）===
test_domain_purity.py  注释条数 36 -> 46：改了 1 处（2 行 -> 3 行，fr4.8-③ 的「就地 import」注释）
                       + 新增 9 条（全在 Ruling 54 那一段里）
test_layering.py       注释条数 39 -> 49：同上
```

```
=== ④ 既有 5 条守卫 assert 逐字对比 ===
   test_domain_imports_stay_within_the_allow_list    assert 1→1 逐字相同=True
   test_domain_has_no_clock_or_file_access           assert 1→1 逐字相同=True
   test_domain_has_no_filesystem_access              assert 1→1 逐字相同=True
   test_production_layers_never_import_app_seed      assert 2→2 逐字相同=True
   既有守卫 assert 合计 5 条，全部逐字未动
   新测试里的 assert 条数（工作树）：purity 3、layering 3（基线各 2；多的那一条就是 Ruling 54
   的 `assert pkg_offenders == []`。派单只禁改**既有 5 条守卫 assert** 的语义，未禁在已有的
   那条测试里加断言，且 passed 数不变）

=== ⑥ 对照组（硬规矩 #53，两个文件各跑一遍，全部相符）===
   ① 注入 _package_of 语义变异（parts[:-1] -> parts）→ 报 DIFF 的单元 = ['_package_of']（尺子能报 DIFF）
   ② 基线自比                                        → 报 DIFF 的单元 = []（尺子能报 SAME）
   ③ 只改 _package_of 的 docstring：AST 报 DIFF=True、剥掉后 = []（尺子真的在剥 docstring）
   ④ 只改一行**注释**：AST 报 DIFF=False、逐单元 = []（**尺子对注释是盲的** → 故有 ③ 段）
```

### fr4.5 硬规矩 #51 闸门（两份 `_package_of` / `_absolute` 仍逐字相同）

`pe_fr4_astdiff.py` ⑤ 段：

```
_package_of    两份 identical(excl docstring) = True
               test_domain_purity.py  与基线逐字相同 = True
               test_layering.py       与基线逐字相同 = True
_absolute      两份 identical(excl docstring) = True
               test_domain_purity.py  与基线逐字相同 = True
               test_layering.py       与基线逐字相同 = True
```

**份数清点（硬规矩 #51 要求列出）**：`_package_of` **2 份**、`_absolute` **2 份**，
本轮**都没改代码**（只改了 purity 侧 `_absolute` 的 docstring，layering 侧逐字未动）。
新增的那一段断言也**各写了一份**：`pe_fr4_counts.py` ④ 段把两段逐行比过，
**各 50 行、只有 4 行不同**，而那 4 行正是断言消息里「本文件 / 那一份」的主语与折算串
（purity 侧主写 `app.domain.seed` + 命中白名单前缀、layering 侧主写 `app.db.seed` +
不再以 `app.seed` 开头，各自把对方的形状作为「那一份同理」附在后面）。4 个形状、
2 格后果对拍、`pkg_offenders` 的累积逻辑全部同文。故 #51 的适用面现在是「两份实现 +
两份回归测试 + 两份 `_package_of` 断言段」= **6 处**，每处都写了两次。

### fr4.6 硬规矩 #52 闸门（本轮写进 docstring / 断言消息的每个值都真跑过）

`pe_fr4_r52.py`（rc 0）：

```
=== purity _absolute docstring 里本轮新写的那两个值 ===
  _absolute("seed", 2, ("app", "domain", "ind")) -> 'app.domain.seed'   docstring 写的 'app.domain.seed'  相符=True
  _is_allowed('app.domain.seed')                 -> True                docstring 写的 True               相符=True

=== 两个断言消息里写的折算串（各文件写自己那一份）===
  purity    app/domain/x.py      from ..seed  import …  pkg=('app','domain','x')          folded=app.domain.seed  GREEN  相符=True
  layering  app/db/models/x.py   from ...seed import …  pkg=('app','db','models','x')     folded=app.db.seed      GREEN  相符=True
  （两条都是 GREEN，正是断言消息声称的「假绿」）

=== layering _absolute docstring 原有的那句（本轮未改，复核仍成立）===
  _absolute('seed', 3, ('app','db','models','x')) -> 'app.db.seed'  _is_forbidden=False  相符=True
```

另把 `pe_fr4_precheck.py` ② 段的结果记在这里：**两个 `_package_of` docstring 里原有的 5 个
举例全部是真跑过的输出**（`app/domain/x.py` → `('app','domain')`、`app/domain/sub/x.py` →
`('app','domain','sub')`、`app/pipeline/x.py` → `('app','pipeline')`、`app/db/models/x.py` →
`('app','db','models')`、`app/db/models/__init__.py` → `('app','db','models')`，两份
`_package_of` 各跑一遍、10/10 相符），故 Ruling 54 要求断言的那 4 格与 docstring 的举例
**互不矛盾**。

### fr4.7 我发现的派单错误（5 条成立 + 1 条账本错误 + 2 条不计入）

按派单 §4.7 逐条给实测证据。**没有一条导致判据不可满足**，两件事我全部按派单做了。
按 Ruling 45/51 的口径：不成立的我不认（⑦⑧），成立的我不替派单辩（①–⑥）。

**① 「读最后一节 `#### Task 1 fix round 3 — 控制者亲验`（**Ruling 48–57**）」→ 账本里
根本没有 Ruling 48；那一节含 Ruling 49–57（9 条）。（成立，计一条）**

python 正则扫 `progress.md` 全文（617 行），`Ruling (\d+)` 在 40..57 区间**出现过**的编号是
`[40,41,42,43,44,45,46,47,49,50,51,52,53,54,55,56,57]`，**48 缺失**；`**Ruling 47` 在 `:505`、
`**Ruling 49` 在 `:558`，编号直接跳过 48。整个 sdd 目录里 `Ruling 48\b` 只命中 **1** 处，在
`task-1-review-package.md:4017`，那是 **Plan 01** 的 Ruling 48（一段 `test_clean.py` 的 diff
里写着 `# ② 同学号同批次两行 → 去重，field = WHOLE_RECORD（Ruling 48/50）`），与 Plan 02 无关。
影响：无（我按 49–57 读了那一节；派单同一句里的「#48 在 `:172`」指的是**硬规矩** #48，
两套编号撞在同一个数字上，这也是它容易被写错的原因）。**这是硬规矩 #54 的又一次适用**
（编号/计数错），形态与 Ruling 49/50/53 同族：把一个清单当成连续的，而它有缺口。

**② 「上一轮新增的 `test_absolute_folding_matches_resolve_name` 里，`package` 入参是
**手写的四元组**」→ 实测矩阵里没有任何四元组。（成立，计一条）**

AST 抽出两个文件的 `cases` 字面量：

```
test_domain_purity.py  cases 行数 = 11  每行元素数 = [5]  package 元组的长度分布 = {2: 9, 3: 2}
test_layering.py       cases 行数 = 11  每行元素数 = [5]  package 元组的长度分布 = {2: 7, 3: 4}
```

**两种读法下「四元组」都不成立**：`package` 自己是 **2 元或 3 元**（没有 4 元），而
**case 行是 5 元**（`(module, level, package, name, 期望颜色)`）。账本 Ruling 45 立的口径是
「以 `(module, level, package, name)` 四元组为参数」，fr3 落地时另加了颜色列 → 5 元。
影响：无（`package` 是手写的这一点完全成立，正是 Ruling 54 的立意）。
**这与 ① 同为硬规矩 #54 的适用面**（计数）。

**③ 派单给两个文件描述了**同一个**后果，而它只在 layering 成立、在 purity 实测是 RED。
（成立，计一条 —— Ruling 51 的同型复发）**

派单 §2 Ruling 54 的背景段与要求 4 都写：「让 `_package_of` 返回模块路径，`app/db/models/x.py`
里的 `from ...seed import …` 就会折成 `app.db.seed`、不再以 `app.seed` 开头 → **守卫假绿**」，
并要求把它写进**两个文件**的断言消息。实测（`pe_fr4_compose.py`、`pe_fr4_precheck.py` ③）：

| 那一格 | layering 的 `_is_forbidden('app.db.seed')` | purity 的 `_is_allowed('app.db.seed')` |
|---|---|---|
| `app/db/models/x.py` + `from ...seed` + `_package_of` 变异 | `False` → **GREEN（假绿）✅** | `False` → **RED**（而且 purity 只扫 `app/domain`，这一格根本在它管辖之外） |

**这与 Ruling 51 是同一个形态**（「派单给两个文件指定了同一张矩阵，却写了一个只在一个文件里
成立的判定」），而控制者在 Ruling 51 里已经明说这不是笔误、是复发。处置同 fr3：**两份断言
消息各写自己那一份的后果**，并把对方的形状作为「那一份同理」附在后面（purity 侧写
`app.domain.seed` + 命中白名单前缀；layering 侧写 `app.db.seed` + 不再以 `app.seed` 开头），
两个串都实跑过（fr4.6）。

**④ 「`Read` 工具的行号在本仓部分区段系统性少 1」→ 实测偏移是 **0 / −1 / −2**，
而且 `Read` **对自己都不自洽**。（成立，「少 1」这个量级错；结论仍成立且更该遵守）**

同一个文件、同一次会话里两次 `Read` 调用，对**同一行内容**给出了不同的行号
（`progress.md` 全程未被我改动过）：

| 文件 | 区段锚点（内容） | python 行号 | `Read` 显示的行号 | 偏移 |
|---|---|---|---|---|
| `progress.md` | `**补硬规矩 #48：派单前必须…` | 172 | 172（`Read offset=160`） | **0** |
| `progress.md` | `Ruling 21 记的是 BASE 20.48/20.85 s…` | 300 | 300（`Read offset=300`） | **0** |
| `progress.md` | `亲验清单（全部本机实跑）：` | **450** | **449**（`Read offset=310`）／**450**（`Read offset=450`） | **−1 / 0 ← 自相矛盾** |
| `progress.md` | `#### Task 1 fix round 2 — 控制者亲验…` | **446** | **445**（同一次 `Read offset=310`） | **−1** |
| `progress.md` | `**→ 补硬规矩 #54：更正计划正文时…` | **588** | **587**（`Read offset=488`） | **−1** |
| `test_domain_purity.py` | `def _package_of` | 117 | 117 | **0** |
| `test_layering.py` | `def _package_of` | 70 | 68 | **−2** |
| `test_layering.py` | `def _is_forbidden` | 174 | 172 | **−2** |

另：`Read` 对 `task-1-report.md` 直接报「文件只有 **1031** 行」并拒绝 `offset >= 1031`，
而该文件实测 **189916 字节 / 2616 个 LF / 0 个 CRLF**（fr3 也撞到同一个 1031，当时实测
2152 行）——即 `Read` 连**总行数**都报错了，本轮读前任报告全程只能用 python。
影响：无（我全程用 shell 口径，派单也已经这么要求了）。**但结论比派单说的更强**：偏移
**不是常数**（同一文件里 0 与 −1 并存、跨文件还有 −2），`Read` 甚至对同一行给出过两个
不同的号，故任何「把 `Read` 行号 +1」的换算都不安全，唯一安全的做法就是派单已经给出的
那条——一律 shell 口径。⚠️ 这句话同时是 `task-1-brief.md` Global Constraints 第 6 条与
`Document/2026-10-06-实施计划02-智能处方引擎.md:24` 的**原文**（「`Read` 工具的行号在本仓
部分区段**系统性少 1**，已四次误导」），不只是本轮派单的转写，故要改得改两处，
而两处都在我的禁区里。

**⑤ 派单让我在账本里 grep 硬规矩 **#30**，而 `progress.md` 里 `硬规矩 #30` 命中 **0** 处。
（成立，计一条 —— 与 ① 同族）**

派单 §1.1 原文：「请 grep `硬规矩 #` 把 **#30** / #32 / #35 / #39 / #42 / #50 / #51 / #52 /
#53 / #54 全部读一遍（它们散在全文各处…）」。实测各号在 `progress.md` 里的命中行数：

| 号 | 命中行 | 号 | 命中行 |
|---|---|---|---|
| **#30** | **（无）** | #42 | 62, 183, 185, 296, 300, 400, 455 |
| #32 | 467 | #50 | 290, 497, 538 |
| #35 | 261 | #51 | 409, 466, 539, 554 |
| #39 | 55, 235, 296, 387, 507, 540, 594 | #52 | 411, 578 |
| #48 | 172（定义行） | #53 | 509, 521 |
| #49 | 265（定义行） | #54 | 588（定义行） |

`硬规矩 #30` 只出现在 `task-1-brief.md`（Global Constraints 第 6 条）、
`Document/…计划02…:24`、`task-1-report.md` 与那份陈旧副本里，**账本里一次都没有**
（`硬规矩 #37` 在账本里命中 1 处）。#30/#32/#35/#39/#42 都是 **Plan 01** 立的规矩，
账本里只有引用、没有「补硬规矩 #N」的定义行（#48–#54 才各有 1 行定义）。
影响：无（我按 brief 与 `Document/` 里的原文读了 #30，并按账本里的引用逐处读了其余各号）。
**「它们散在全文各处」对 #30 不成立**，而且 #30 恰好是本轮最该遵守的那条（行号口径）——
与 Ruling 44（把 #50 指到阅读范围之外）同型。

**⑥ 账本 Ruling 42 那句「`:139` 与 `:246` 说的是 `app.domain.seed.generate`（`startswith`
为 True，**正确**），只有 `:167` 是错的」→ 对 `:139` 不成立。（成立；这是**账本**里的错，
不是本轮派单里的错，但它是本轮我改动的直接依据，故一并报）**

`pe_fr4_ruling42b.py` 实跑：`_absolute("seed", 2, ("app","domain","ind"))` =
**`'app.domain.seed'`**，与 `resolve_name('..seed', 'app.domain.ind')` 逐字相同；
要折出 `'app.domain.seed.generate'` 必须把写法换成 `from ..seed.generate import X`
（`module` 带点），而老 `:139` 写的是 `from ..seed import generate`。**关键是动词**：
老 `:139` 用的是「就会**折成**」= `_absolute` 的返回值 → 串错；老 `:246`（今 `:422`）用的是
「**解析到**的是」= 这句 import 语义上取到的对象，`resolve_name('..seed.generate',
'app.domain.sub')` 实跑就是 `'app.domain.seed.generate'` → **对**，本轮未动。
Ruling 42 只核了「那个串是否命中 `app.domain.` 前缀」（True），**没核「`_absolute` 对
`from ..seed import generate` 是否真产出那个串」**（不产出：`generate` 住在 `node.names` 里、
不进折算串，这正是 Ruling 36）；fr3 的实现者照抄了这句判断、还在报告 fr3.1 里写「要求不动」。
处置：见 fr4.8-①（就近更正 `:139`，`:422` 那一处保留）。

**⑦ 派单 §3 预期「`<module-level>`（若模块 docstring 算在里面）」→ 实测不算。（不计入：
派单已用「若」限定，只是把实测答案报回来）**

见 fr4.4：尺子对 `ast.Module` 也剥 docstring，故模块 docstring 的改动不会让 `<module-level>`
报 DIFF；实测有差异的顶层单元 = `['test_absolute_folding_matches_resolve_name']`
（两个文件各一）。为免这个盲区藏东西，已另立 docstring 与注释两节全量清点，并用对照 ④
把「尺子对注释是盲的」显式跑出来。

**⑧ 派单 §2 要求 4 那个 M1 例子是**片段**、不是可直接替换的一行。（不计入：派单用「例如」
限定、意图清楚）**

派单写「例如 `parts[:-1]` → `tuple(list(parts)[: len(parts) - 1])`」，而实现是单行
`return py.relative_to(BACKEND).with_suffix("").parts[:-1]`，里面**没有** `parts` 这个名字，
照字面替换会 `NameError`。我的 M1 实现是先绑一个局部名再返回
（`parts = py.relative_to(BACKEND).with_suffix("").parts` +
`return tuple(list(parts)[: len(parts) - 1])`），AST 变了、语义等价、两条仍绿。

**其余我逐条核过、成立**的派单陈述（列出来表示核过，不是凑数）：分支名与 HEAD `73313f7` ✓、
`73313f7` 只比 `be0f1af` 多一个 `Document/` 的文档 commit 且两个守卫文件自 `be0f1af` 起未变 ✓
（`git diff --name-only be0f1af 73313f7` 只含那个文档）、`core.autocrlf=true` ✓、
Python 3.11.1 / 无 venv ✓、硬规矩 #48 在 `progress.md:172` / #49 `:265` / #50 `:290` ✓
（另 #51 `:409`、#52 `:411`、#53 `:509`、#54 `:588`）、`task-1-brief.md` Global Constraints
**10 条**顶层 bullet（0 条缩进子项）✓、`fr3_probes/` **11 个**脚本 ✓、
`_package_of` 的实现串 `return py.relative_to(BACKEND).with_suffix("").parts[:-1]` 在两个
文件里各命中恰 1 次、逐字相同 ✓、`_package_of` 不碰文件系统（不存在的路径照样算）✓、
4 个点名形状与期望值 ✓（fr4.1 的表）、`test_layering.py:70-77` 的 docstring 已解释
`parts[:-1]` 而此前没有断言 ✓（shell 口径 `:70` 是 `def`、`:71-77` 是 docstring、`:78` 是
`return`）、模块 docstring「三条守卫」而文件里有 4 个 `test_*` ✓、
`test_layering.py` 有 2 个 `test_*` ✓、基线 481 passed ✓、基线 domain `399/0/114/0/100%` ✓、
`--cov` 下 `480 passed, 1 skipped` 且 skip 在 `test_backfill.py:182` ✓、
既有 5 条守卫 assert（purity 1+1+1、layering 2）✓、上一轮两份 `_absolute`
`identical(excl docstring) = True` ✓、`git show` 的 blob 是 LF 版且差值 = CRLF 行数 ✓
（本轮实测 purity 差 572、layering 差 341；派单引的 36103/36666/563 是 fr3 过程中的一个
中间态，机制描述正确）、Ruling 54 背景段那句「守卫假绿、而全部 481 条测试仍然通过」✓
（fr4.3 的 M6 在基线上实测 481 passed / rc 0）。

### fr4.8 超出派单的改动（主动披露，3 处 + 1 处纯风格，全部在这两个守卫文件内）

**① 更正 purity 侧 `_absolute` docstring 里的一处折算串错话（改后 `:141-146`）。**
即 fr4.7-⑥ 那条。原文「`app/domain/x.py` 里的 `from ..seed import generate` 就会折成
`app.domain.seed.generate`、命中白名单前缀 `app.domain.` → 守卫当场假绿」，实跑折成
`app.domain.seed`。改成：

```
就会折成 ``app.domain.seed``（**不是** ``app.domain.seed.generate``：``generate`` 住在
``node.names`` 里、不进折算串，Plan02 Ruling 36；本机 Python 3.11.1 实跑
``_absolute("seed", 2, ("app", "domain", "ind"))`` -> ``'app.domain.seed'``、
``_is_allowed('app.domain.seed')`` -> ``True``）、命中白名单前缀 ``app.domain.`` →
**守卫当场假绿**
```

**结论（假绿）没改，只改串**，与 Ruling 42 的处置口径一致。**为什么本轮就近改而不是留给
控制者**：① 本轮正要给 `_package_of` 加断言，而新断言消息里写的就是 `app.domain.seed`——
不改就会让**同一个文件**里「断言消息说 `app.domain.seed`、docstring 说
`app.domain.seed.generate`」自相矛盾（Ruling 32 的就近修正先例：「两处都是为了让…在同一个
文件内不自相矛盾」）；② 这段 docstring 正是 Ruling 37 说的「`_package_of` 的规格说明」，
本轮的主题就是给它加守卫，留一个假的规格说明在里面与本轮的立意直接冲突。
**layering 侧同一句话写的是 `app.db.seed`、实跑相符，逐字未动**（fr4.4 ② 段实测）；
**今 `:422`（老 `:246`）那一处「解析到的是 `app.domain.seed.generate`」也未动**——它的动词
是「解析到」而不是「折成」，实测相符（fr4.7-⑥）。改完全仓 grep「白名单前缀」在 purity 里
命中 **3** 处：`:145`（本轮更正后的那句）、`:358`（本轮新写的断言消息）、`:422`（未动，正确）。

**② 新断言里多写了一段「后果对拍」（两个文件各 14 行，purity `:341-354`、
layering `:327-340`）。**
派单要求 1–5 只要求断言 `_package_of` 的**值**（等于对的 + 不等于错的）。我另加一段把
`_package_of` 的输出**直接喂给** `_absolute`、与 `resolve_name` 对拍 2 格
（`app/domain/indicators.py` + `from ..seed`、`app/db/models/organisation.py` + `from ...seed`）。
理由：派单要求 4 让「后果」只出现在**断言消息**里，而消息是散文；这一段让后果**可跑**，
且判据锚在 `resolve_name` 上（与本测试已有的 11 格同一个锚，不是新造一张表），
与 Ruling 46「判据不要抄表」的立意一致。成本 14 行 × 2 份，不新增测试函数、不新增文件。

**③ 两处「就地 import」注释的精度修正（每个文件 2 行 → 3 行）。**
原文「模块级 import 会改动本文件的 `<module-level>`，而**本轮**的改动面被钉死在
『**新增**这一条测试函数』之内（Plan02 Ruling 46）」——那条函数是 fix round 3 新增的、
本轮只是往里加一段，故「本轮」「新增」都不再成立。改成「…故这条测试自 fix round 3 起就把
import 留在函数体内、改动面也一直钉死在『这一条测试函数 + docstring』之内（Plan02 Ruling
46/57）」。`import importlib.util` 本身**维持在函数体内未动**（Ruling 57）。
**⚠️ 注释不进 AST**，逐顶层单元的自证对它完全盲（fr4.4 对照 ④ 实测），故这类改动必须靠
fr4.4 ③ 段的注释全量清点来交代，不能只贴 AST 自证。

**④ 一处纯风格**：去掉一个没有占位符的 `f` 前缀（`f"（parts[:-1] 被写成了 parts）"` →
`"（…）"`，两个文件各一处）。它在同一条隐式拼接里，AST 合并成一个 `JoinedStr`，故
`git diff --numstat` 的增删行数不变（仍是 purity `70 8`、layering `61 6`）。
本项目没有配 linter（`backend/pyproject.toml` 里只有 pytest 与 setuptools 配置），
故这不是修 lint，只是不留一个无意义的 `f`。

### fr4.9 关切清单（3 条）

**C-fr4-1【低 → 建议记进 Task 2 预检清单】`_package_of` 的断言仍是手写枚举的 4 格，
Task 2 建了子包之后没人会被提醒去加行。** — 自己重新推导

判据是字面元组（不是 `resolve_name` 那种外部锚），故它**不会过期成假绿**（多加一格就是多一格
覆盖，少一格只是少覆盖），但**也没人会收到提醒**。Task 2 会新建 `app/domain/prescription/`，
届时 `app/domain/prescription/match.py` 从「今天不存在的形状」变成真仓里真实存在的文件，
而矩阵里包深 3 的真实绿档也会多起来。Ruling 56 已经把「扫真仓所有 `ImportFrom` 逐个对拍
`resolve_name`」转给 Task 2，那条方案会**顺带**把 `_package_of` 全覆盖（因为它必须先调
`_package_of` 才能得到 `package`）；建议在 Task 2 的预检清单里明确写一句
「若不做全仓扫描，则至少把 `_package_of` 的断言换成扫真仓每个 `.py`、与
`py.relative_to(BACKEND).parent.parts` 对拍」——那是**非同源**判据（一边是
`with_suffix("").parts[:-1]`、一边是 `.parent.parts`，两种写法对 `__init__.py` 给出同一个
结果，正是这一格要守的东西），且自动跟进以后出现的每一个深度。

**C-fr4-2【低 → 账本自身】Ruling 编号在 48 处有缺口，引用时容易错一位。** — 自己发现

见 fr4.7-①。这不是本轮派单独有的问题：只要编号有洞，任何「Ruling N–M」的区间写法都可能
把不存在的号包进去。建议在 `progress.md` 里补一行（例如在 Ruling 47 之后）
「**Ruling 48 号未用**（编号跳过，无内容）」，成本一行，能挡住下一次同类错误。
`progress.md` 是控制者的账本（且在 gitignore 的 `.superpowers/` 里），对我是禁区，
故本轮**未动**，只记下转给控制者。同一族的问题还有 fr4.7-⑤（硬规矩 #30 在账本里 0 命中）。

**C-fr4-3【低 → 流程】两份重复代码的维护成本本轮又付了一次，且第一次付在「断言段」上。** — 自己重新推导

Ruling 33 裁「本计划内不抽公共模块」，fr1 的延后 Minor 也记了「维护成本极低的判断偏乐观」。
本轮的具体代价：同一段 50 行断言在两个文件里各写一份，其中**只有 4 行不同**（fr4.5 实测），
外加改完后要再跑一次「两份是否仍逐字相同」的闸门。Ruling 33 的三个理由（语义故意不同 /
只有两个文件 / 抽出来会多一个没人守的助手模块）本轮**依然成立**，我不申请推翻；
只是把「重复的账」再记一笔：Plan 03 若加第三个架构守卫，`_package_of` + `_absolute` +
回归测试 + `_package_of` 断言段 = **4 段 × 3 份 = 12 处**要同步，那时抽公共模块的收益会
明显盖过成本。

### fr4.10 本轮**没做**的事

- 没动任何生产代码：`git diff --name-only be0f1af HEAD -- backend/app/` 命中 **0**；
  `git diff --name-only 73313f7` 只含两个守卫文件。
- 没动 `backend/tests/` 下的其他文件、没动 `backend/data/`、没动 `Document/`
  （`73313f7` 那个文档 commit 是控制者的，本轮未再动它一个字节；fr4.7-④ 指出的
  `Document/…:24` 那句「系统性少 1」也在禁区里，未动）。
- **没新增测试函数**：`tests/architecture` 仍 **6 passed**、全量仍 **481 passed**
  （与基线逐字相同）。
- 没改既有 5 条守卫 `assert` 的语义（fr4.4 ④ 段逐字比过：1+1+1+2 = 5 条，全部
  `逐字相同=True`）。
- 没改 `_package_of` / `_absolute` 的**代码**（fr4.4 ⑤ 段：两份都与基线逐字相同）；
  只改了 purity 侧 `_absolute` 的 docstring 一处（fr4.8-①）。
- 没改 `test_layering.py` 的模块 docstring（grep 无同类计数陈述，见 fr4.2）。
- 没动 purity `:422`（老 `:246`）那处「解析到的是 `app.domain.seed.generate`」——它的动词是
  「解析到」、实测相符（fr4.7-⑥）。
- 没把 `import importlib.util` 挪到模块级（Ruling 57 维持）。
- 没把 `_package_of` / `_absolute` 抽成公共模块（Ruling 33 仍有效，见 C-fr4-3）。
- 没给 `FORBIDDEN_IO` 补 `__import__(`（Ruling 47 已判延后 Minor）。
- 没做 Ruling 56 转给 Task 2 的「扫真仓所有 `ImportFrom` 逐个对拍」（本轮不做）。
- 没造合成树、没重定向任何守卫模块的全局（`_package_of` 是纯路径运算，不需要）；
  没跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`（禁区）。
- 没 `git push`；`git checkout` / `git restore` / `git switch` **一次都没用**。
- 没动 `fr3_probes/` 里的 11 个脚本（本轮只**参照**它的变异/还原写法，另写了 `fr4_probes/`
  的 12 个）。
- 没改 `progress.md`（账本）与 `task-1-brief.md`：C-fr4-2 与 fr4.7-④⑤ 指出的三处都在
  我不可动的文件里，只报不改。

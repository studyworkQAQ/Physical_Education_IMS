# Task 4 实现者报告 — 模板匹配器（`match.py`）

> 实现者：Task 4 sub-agent。基线 HEAD `3473dc6`（代码基线 `ab075d3`），分支
> `feature/plan-02-prescription-engine`。本文件是**新建**的（追加/改写前无原件可备份；
> 若后续需要追加，先按硬规矩 #68 做字节备份）。
> 取证脚本全部在 `.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/t4_probes/`
> （`p01`…`p17`，含变异 harness `p12_mutate.py` 与它的完整输出 `mutate_log.txt`）。
> ⚠️ 本文件里所有 sha256 都**标明是裸字节还是归一化后**（硬规矩 #70 扩写）；
> 所有字节数/行数/行尾都用 `read_bytes()` 量（不用 `read_text()`）。
> ⚠️ 本报告与派单一致，**不写裸行号**；凡引用既有文本一律给可 grep 的原文
> （硬规矩 #76）。少数必须复述的地方（例如「计划正文里那个错行号本身」）按 #74 处理：
> 被撤销的原句**不逐字复述**，只描述。

---

## 0. 环境与基线复现（硬规矩 #72/#73）

**依赖冒烟**（开工第一件事，命令逐字照派单）：

```
$ python -c "import sys;print(sys.version)"
3.11.1 (tags/v3.11.1:a7a450f, Dec  6 2022, 19:58:39) [MSC v.1934 64 bit (AMD64)]
$ python -c "import sqlalchemy,pandas,numpy,yaml;print(sqlalchemy.__version__,pandas.__version__,numpy.__version__,yaml.__version__)"
2.1.3 3.0.6 2.4.6 6.0.3
```

**没有撞上** `ImportError: DLL load failed while importing _cache_key_cy`（Ruling 121/122
那个 SAC 拦截）。SQLAlchemy 2.1.3 全程可用，**没有动 site-packages、没有装别的版本、
没有塞 stub**。无 venv（`C:\Python\Lib\site-packages`）。

**开工基线（全部亲跑，逐个与派单 §5 自查清单对账）**：

| 项 | 派单说 | 我实测 | |
|---|---|---|---|
| HEAD | `3473dc6` | `3473dc6` | ✓ |
| `git status --short` | 空 | 空 | ✓ |
| `git diff --name-only ab075d3 3473dc6 -- backend` | 空 | 空 | ✓ |
| Python / SQLAlchemy / pandas / numpy / PyYAML | 3.11.1 / 2.1.3 / 3.0.6 / 2.4.6 / 6.0.3 | 同 | ✓ |
| `python -m pytest -q` | 581 passed | **581 passed in 66.94s** | ✓ |
| `task-4-brief.md` | 24 221 B / 152 行 | **24221 B / 152 行**（sha256[:16] 裸字节 `4479AFE1E71B614C`） | ✓ |
| `progress.md` | 约 299 KB | **299 059 B / 1931 行**（sha256[:16] 裸字节 `A7B38FBB63804BF7`） | ✓ |
| `Base.metadata.tables` | 16 张 | **16 张** | ✓ |
| CSV 指纹 | 21412 B / `D2C8E539E2FA0029` / CRLF 0 | 同 | ✓ |
| `exercises.yaml` | 22739 B / `3DE598AF38631209` / CRLF 0 | 同 | ✓ |
| `exercise_equivalence.yaml` | 8245 B / `822CB86A5E998301` / CRLF 0 | 同 | ✓ |
| `backend/pe.db` | 不存在 | 不存在 | ✓ |
| `backend/data/seed/` | 0 文件 | 0 文件 | ✓ |
| `app.domain.prescription.__all__` | 20 个名字 | 20 个，逐个相符 | ✓ |
| `templates.__all__` | 14 个 | 14 个 | ✓ |
| `ReviewStatus` 成员 | `PENDING="pending"` / `APPROVED="approved"` | 同 | ✓ |
| `is_reachable` 函数体 | `return not (layer is Layer.GREEN and body_comp is BodyCompState.ABNORMAL)` | 逐字相同 | ✓ |
| `Template` 字段 | 14 个 | 14 个，逐个相符 | ✓ |
| `_PRESCRIPTION_PUBLIC_BASELINE` | len == 20，文案含「基线是 20 个名字，抄漏了就当场红」 | 同 | ✓ |
| 全仓相对导入 | 16 条，全部 `level == 1` | **16 条 / `{1: 16}`** = `app/db/models` 13 + `app/domain/prescription` 3 | ✓ |
| `SCANNED_DIRS` 扫描面 | 27（pipeline 7 + db 11 + domain 9） | **27** = 7 + 11 + 9 | ✓ |

**派单给的「可 grep 的原文」逐条亲验**（`git grep -n`）：

* `derive.py` 的 `dominant_bucket`：字段声明在 **:129**、docstring 口径在 **:320** 起、
  赋值处 `dominant_bucket=dominant` 在 **:371**；`_BUCKET_ORDER` 定义在 **:77**、
  消费在 **:352** / **:356**；**:76** 的注释逐字含
  「故 dominant_bucket 不依赖 dict 的哈希顺序（Ruling 100）」——**全部相符** ✓
* **`derive.py:330` 确实是空行**（P4-A5 的更正为真）✓
* `stratify.py`：`_REASON` 在 **:168**，`RuleId.Z0` 那一行是
  `RuleId.Z0: f"有效项不足 {MIN_VALID_COUNT} 项，本日不分层"`（**:169**），
  `MIN_VALID_COUNT = 4` 在 **:82**，`def explain(...)` 在 **:326** ✓
* spec §11.2 那一行（`git grep -n "review.status != approved"`）在 **spec:859**，逐字是
  「| 模板 `review.status != approved` | 拒绝生成，返回「模板待审校」，教师端提示 |」 ✓
  （同一命令还命中 **spec:451**「`review.status != approved` 的模板拒绝用于生成」）
* spec §7.1 的「已知事实」在 **spec:445**、「保留为**预留位**」在 **spec:447** ✓
* 18 套模板的 `review_status` distinct 值**只有 `approved` 一个**（亲跑 `rp.templates()`
  逐个打印）✓ ——故变异 ① 只可能变 `MATCHED`，P4-A4 的更正为真 ✓

**没跑过**：`python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`
（禁区）。**没改过** `backend/data/` 下任何文件、没改 `.gitattributes`、没改 `app/seed/`。

---

## 1. 交付清单

### 1.1 新建（3 个文件）

| 路径 | 字节 / 行 / 行尾 | sha256[:16]（裸字节 = 归一化后，因为是纯 LF） |
|---|---|---|
| `backend/app/domain/prescription/match.py` | 18 589 B / 287 行 / CRLF 0 | `40E08F5587C92F46` |
| `backend/tests/domain/test_prescription_match.py` | 25 936 B / 414 行 / CRLF 0 | `1774173D6C455413` |
| `backend/tests/domain/test_prescription_exercises.py` | 4 841 B / 79 行 / CRLF 0 | `FCCDBEC094F6BD9B` |

⚠️ **三个新文件的工作树行尾是 LF、而 `backend/**.py` 的既有惯例是 `i/lf w/crlf`**
（`git ls-files --eol backend` 亲跑：绝大多数是 `w/crlf`）。这**不是**我引入的新形状：
`git ls-files --eol` 显示 `backend/app/adapters/factory.py`、
`backend/tests/adapters/test_factory.py`、`backend/tests/pipeline/test_percentile_stage.py`
三个文件今天就是 `i/lf w/lf`（都是前几个 Task 新建、之后没被 checkout 过的）。
`git check-attr text eol -- backend/app/domain/prescription/match.py` 得
`text: unspecified / eol: unspecified`，即 `.gitattributes` **不管** `.py`（它只钉
`backend/data/**` 与 `.superpowers/**`），故 `core.autocrlf=true` 下**提交时 CRLF→LF、
检出时 LF→CRLF**：我这三个文件进 index 的 blob 与「假如它们是 CRLF」时**逐字节相同**，
下一次 checkout 会把它们变成 CRLF。**没有任何按字节哈希的守卫覆盖 `.py`**，故不构成风险；
本 Task 不碰 `.gitattributes`（禁区 C2）。

### 1.2 修改（4 个文件；`git diff --numstat -- backend` 亲跑）

| 路径 | +行 / −行 | 改了什么 |
|---|---|---|
| `backend/app/domain/prescription/__init__.py` | +27 / −4 | 加 `from .match import (…)`、`__all__` 追加 4 个名字（20 → **24**）、docstring 三处计数与「谁是所有者」段 |
| `backend/tests/test_refdata_prescription.py` | +69 / −69（净 0 行） | 搬走 `lookup()` 分支测试、`_PRESCRIPTION_PUBLIC_BASELINE` 20 → **24**、`_OWNED_MODULES` 2 → **3**、`assert len(...) == 20` → **24**（两处）、6 处交叉引用与时点 |
| `backend/tests/architecture/test_domain_purity.py` | +141 / −54 | 3 处过期陈述里的 **①③**（各 1 份）、扫真仓对拍（Task 3 转来 ①②）、相对导入计数、`_assert_not_empty` 的时点 |
| `backend/tests/architecture/test_layering.py` | +141 / −49 | 3 处过期陈述里的 **①③**（各 1 份）、扫真仓对拍（同一份逻辑的第二个副本，硬规矩 #51）、相对导入计数、`SCANNED_DIRS` 计数 |

---

## 2. TDD 的红 → 绿链（两次实跑，逐次留证）

### 2.1 红 —— 只有测试、完全没有生产码

先落 `test_prescription_match.py` 与 `test_prescription_exercises.py`，`match.py` 还不存在：

```
$ cd backend; python -m pytest tests/domain/test_prescription_match.py tests/domain/test_prescription_exercises.py -q
=================================== ERRORS ====================================
__________ ERROR collecting tests/domain/test_prescription_match.py ___________
ImportError while importing test module 'C:\...\backend\tests\domain\test_prescription_match.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Python\Lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests\domain\test_prescription_match.py:50: in <module>
    from app.domain.prescription import (
E   ImportError: cannot import name 'MatchInput' from 'app.domain.prescription'
    (C:\...\backend\app\domain\prescription\__init__.py)
=========================== short test summary info ===========================
ERROR tests/domain/test_prescription_match.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.50s
```

**退出码 2**（收集期就炸）。⚠️ 这是一次**收集期**的红、不是断言级的红：
`ImportError` 只证明「名字还不存在」，证明不了「32 格期望表是有牙的」。后者由 §7 的
四个变异分别证明（每个变异都让**具体的断言**开火）。

### 2.2 绿

`match.py` + `prescription/__init__.py` 落地后：

```
$ python -m pytest tests/domain/test_prescription_match.py tests/domain/test_prescription_exercises.py -q
............                                                             [100%]
12 passed in 0.44s
```

全量（最终态，见 §13）：**592 passed**（不带 coverage）/ **591 passed, 1 skipped**
（带 coverage；那 1 个 skip 是 `test_backfill.py` 里 trace-hook 自觉跳过的那条，
可 grep 原文 `检测到 trace 钩子`）。

---

## 3. 交付内容的设计决定

### 3.1 `Layer` 的导入路径：**绝对**，从所有者 `app.domain.stratify` 取（派单要我选并说明）

`match.py` 写的是 `from app.domain.stratify import MIN_VALID_COUNT, Layer`。

理由三条：① **唯一所有者是 `app.domain.stratify`**（`stratification_result.label` 那一列、
`RULE_ORDER` 与 Z0 闸门都用它），`templates.py` 里那一份是 re-export，而它自己的
docstring 逐字写着「**新代码请直接从所有者导入**」；② **与既有写法一致**——
`git grep -n "^from app.domain.stratify import Layer" -- backend/app` 命中
`prescription/__init__.py` 与 `prescription/templates.py` **两处**，本模块是第三处；
③ `prescription/__init__.py` 的 docstring 有一条显式纪律（可 grep 原文
「**每个名字都从它的所有者模块 import、不从二级 re-export 再 re-export**」），
从 `.templates` 取 `Layer` 会与之相悖。

### 3.2 相对 vs 绝对：**「跨包指向所有者用绝对串、同包兄弟用 `level == 1` 相对串」**

`match.py` 的 6 句 import（亲跑 AST）：

```
ImportFrom: [(0, 'collections.abc'), (0, 'dataclasses'), (0, 'enum'),
             (0, 'app.domain.indicators'), (0, 'app.domain.stratify'),
             (1, 'templates')]
Import:     []
```

即 **1 条 `level == 1` 的相对导入**（`from .templates import BodyCompState, ReviewStatus,
Template`），与 `templates.py` 的 `from .exercises import ImpactLevel`、
`__init__.py` 的 `from .exercises/.templates/.match import (…)` 完全同风格；
跨包的两条（`indicators` / `stratify`）用绝对串，与 `exercises.py` 的
`from app.domain.indicators import ITEM_BUCKET` 同风格。**没有一半绝对一半相对。**

**对计数的影响（实测，命令见 §9.3）**：

* 全仓相对导入 **16 → 18**、level 分布仍 `{1: 18}`。
  ⚠️ **不是派单/简报说的 17**——见 §11 的 **CE-2**。
* 两份架构守卫矩阵里 `("indicators", 2, ("app", "domain", "prescription"), "X", "GREEN")`
  那一格（Task 1 fix round 5 为 Task 4 埋的）**仍是「前瞻」、不是真仓形状**
  （账本 Ruling 104 记的同一件事）；我已在**两份**守卫的 docstring 与 `cases` 注释里
  把这一点写明，并把归属改成「Task 1 fix round 5 为 Task 4 的形状埋的」。
* `SCANNED_DIRS` 扫描面 **27 → 28**（`app/domain` 9 → 10）；两份守卫的空转守卫下界
  （`>= 8` 与 `>= 5`）**都没有红**（账本 C1 的预测为真 ✓）。

### 3.3 `reachable`：读**字段**、不调 `is_reachable`（P4-A2 的裁定，照办）

`match.py` 里 `is_reachable` **0 命中**（`git grep -c "is_reachable" --
backend/app/domain/prescription/match.py` → 无输出，即 0 处；只在 docstring 里以
`:func:` 角色**提及**它作为所有者）。模块 docstring 用一整节写明：
规则的唯一所有者是 `templates.is_reachable`、数据的唯一所有者是 YAML 的 `reachable` 键、
加载器已强制两者一致，故匹配器再算一遍就是**第三个住址**（Global Constraint #3），
而且会**掩盖「加载器没校验」这个真故障**。

**并且按硬规矩 #39 写清「本函数守不住什么」**：谁绕过加载器手工构造一个
`reachable=True` 的 `(green, *, abnormal)` 模板，本函数会照常 `MATCHED` 出去、
**没有任何一条测试会红**。这一档我把它**钉成了期望行为**：
`test_a_hand_built_reachable_green_abnormal_template_is_matched`
（用 `dataclasses.replace` 造副本，不碰 YAML），免得下一个人以为这里漏了判据、
顺手把 `is_reachable` 加回来。

### 3.4 `NO_LAYER` 的 `reason` 与 Plan 01 的 Z0 文案**同源**（P4-A7）——但用**副本 + 测试侧漂移守卫**，不 import 私有名

`match.py`：

```python
_NO_LAYER_REASON = f"有效项不足 {MIN_VALID_COUNT} 项，本日不分层"
```

插值的 `MIN_VALID_COUNT` 是 `stratify` 的**公开**名（`from app.domain.stratify import
MIN_VALID_COUNT, Layer`），故「4」这个数仍只有一个住址。

**为什么不 `from app.domain.stratify import _REASON`**：派单说
「`app/domain/percentile.py` 里有一处先例是「触私有名」」——**这句不成立**（§11 的
**CE-1**）。实测 `git grep -n "触私有名" -- backend` 只命中**两个测试文件**；而
`app/domain/percentile.py` 里的两处**恰好是相反的纪律**（可 grep 原文
「不 import 私有名 ``_lower_is_better``（本模块的既有纪律，见 :func:`national_norm`）」
与「不去 import 私有名 :func:`app.domain.indicators._lower_is_better`」）。
故本仓的既有口径是：**生产码不 import 私有名，测试可以**。我照这个口径办：

* `match.py`（生产码）持副本，`#:` 注释块逐条写明「**唯一所有者是
  `app/domain/stratify.py` 的 `_REASON`**」「为什么是副本而不是 import」
  「阈值不复制（插值公开的 `MIN_VALID_COUNT`）」「**漂移时谁会发现**」；
* 漂移守卫是 `test_no_layer_reason_is_verbatim_the_stratify_z0_reason`，
  它**在测试里**就地 `from app.domain.stratify import _REASON, RuleId`，
  行内注释照 `tests/domain/test_percentile.py` 那个先例写「触私有名：本条要比较的正是它」，
  docstring 里把先例与理由都点名了。
* **两侧不同源**（硬规矩 #35 不受影响）：期望侧取自 `stratify`、实际侧取自 `match` 的输出。

实测这一支的 `reason` 逐字是 `有效项不足 4 项，本日不分层`（§4 的表）。

### 3.5 `NO_BUCKET` 的 `reason`：**偏离了简报建议的措辞**，理由如下

简报建议的措辞是「6 个短板判定项全部缺测，无法确定主导短板」。我落地的是：

```
6 个短板判定项全部无效（缺测或无判定线），无法确定主导短板
```

两处刻意的偏离：① 「6」写成 `f"{len(WEAKNESS_ITEMS)} …"`（`WEAKNESS_ITEMS` 是
`app.domain.indicators` 的公开名），**不硬编码数字**——口径照 `stratify.explain()`
（它也是 `f"…{len(WEAKNESS_ITEMS)} 个短板判定项里只有 …"`）；② 「全部缺测」改成
「全部无效（缺测或无判定线）」，因为 `derive.py` 的口径逐字是
「一个有效项都没有（**全缺测或全无判定线**）时为 ``None``」——只写「缺测」会漏掉
「有得分但该 (项, 性别, 年级组) 组没有 P25 判定线」这一整类，而那正是
Global Constraint #5（散文带口径）要防的。

### 3.6 ⚠️ 一个值得记录的语义发现：`NO_BUCKET` 在生产路径上**总是被 `NO_LAYER` 先拦下**

按 `derive.py` 的口径，`dominant_bucket is None` ⟺ `valid_count == 0`；而
`valid_count == 0 < MIN_VALID_COUNT` ⟹ Z0 命中 ⟹ `Layer.INSUFFICIENT`。故
「有真层 + 桶为 None」在**同一次 `compute_derived` + `stratify` 的产物里不可能出现**。

**但这一支不能删**，理由写进了 `match.py` 的行内注释：`MatchInput` 的两个字段来自
**两张不同的表**（`stratification_result.label` 与 `derived_metrics` 的短板结果），
Task 9 完全可能把它们从**不同时点**的两行读回来拼装；那时「有分层标签但没有主导短板」
是一个真实可能的输入，必须报 `NO_BUCKET` 而不是 `KeyError`/静默。
这也解释了为什么 P4-A3 的承重格 `(green, None, abnormal)` 只在**测试构造的输入**上出现
——它的价值是钉住优先级链，不是钉住一条生产路径。**这条不是对 P4-A3 的反驳**：
P4-A3 说的是期望表的分类，那个分类我逐格复现了（§4）。

### 3.7 `NO_TEMPLATE` 的 `reason` 用**英文 token**，不新造中文桶名映射

实测那一支的文案是：

```
处方模板矩阵里缺 (层 red, 主导短板 strength, 体成分 normal) 这一格：那是模板数据缺失，不是这个学生不该有处方
```

仓内**没有**素质桶的中文名口径，而 `stratify.explain()` 的 docstring 为此专门写过一段
（可 grep 原文「``dominant_bucket`` 刻意**不渲染**：仓内没有素质桶的中文名口径…
把英文 token 直接给学生看是文案缺陷，而新造一张中文桶名映射属于新增口径、须先改 spec」）。
我不新造那张映射（那会是第二个所有者、且要先改 spec）。`Layer` 的中文词表
`stratify._LAYER_WORD` 是**私有名**，按 §3.4 的纪律生产码不 import 它。
故这一支的读者定位是**运维/开发**（「矩阵缺一格」是数据故障，不是给家长看的文案），
英文 token 足够定位到该补哪个 YAML 文件；测试用 `("red", "strength", "normal")`
三个子串钉住「必须指出缺哪一格」。

### 3.8 `NOT_APPROVED` 的 `reason` 含「待审校」（spec §11.2 的教师端原文）

实测：`模板待审校（RED-END-ABN-01 的 review.status = pending），拒绝生成处方`。
测试用 `assert "待审校" in got.reason` 钉住那三个字（spec §11.2 逐字要求）。
**没有把整句钉死**：措辞微调不该是一次需要改测试的变更（这一取舍写进了测试文件的
「本文件守不住什么」段）。

### 3.9 遍历序是 `sorted(templates)`，不是 `templates` 的插入序

`match_template` 按 `for template_id in sorted(templates)` 遍历。理由：加载器只校验
`template_id` **唯一**、**不校验「一格至多一套模板」**（`load_templates` 的 docstring
明写它刻意不做「18 套是否恰好覆盖全矩阵」的策略校验），故两个同维度的模板在理论上
可以共存；那时「取第一个命中者」就会随字典插入顺序漂。排序之后
「同一份输入 → 同一个结果」与字典顺序**结构性无关**，
`test_match_is_deterministic_under_dict_ordering` 把这件事钉住
（`dict(reversed(list(...)))`，32 格逐个比整个 `MatchOutcome`，并先断言
「打乱后的顺序与原顺序不同」以免本条空转）。同类先例：Plan 01 的 Ruling 100 把
`derive._BUCKET_ORDER` 做成声明序。

### 3.10 `match.py` **没有** `__all__`

`exercises.py` 也没有（`git grep -n "^__all__" -- backend/app/domain/prescription/`
只命中 `templates.py` 与 `__init__.py`）。`templates.py` 有 `__all__` 是因为它要**显式
声明 re-export**（它自己的 docstring：「``__all__`` 里列着它们，是为了让这次 re-export
是一次**显式**声明」）。`match.py` 只拥有自己的 4 个公有定义、不 re-export 任何东西，
故不写 `__all__`——写了反而会让 `Template` / `ReviewStatus` / `BodyCompState` 看起来
像是从 `match` 导出（那正是 `prescription/__init__.py` 那条纪律要防的）。
⚠️ 我在第一版里确实写了这样一个 `__all__`（并顺带 import 了一个没用到的
`WeaknessBucket`），被自己的落盘闸门探针抓出来后删掉了，见 §12。

### 3.11 `MatchStatus` 的声明序**不是**优先级序

声明序照简报 Produces 那一行的列举序（`MATCHED` 在前），与 `templates.py` 三个枚举
「照 spec 书写序声明」同口径。优先级链住在 `match_template` 的 docstring 与
`_MATRIX_32` 的排列里。`test_match_status_has_exactly_the_six_pinned_members`
把声明序也一并钉住，并在 docstring 里明写「**不要把本枚举重排成链序**」——
免得下一个人以为枚举顺序就是判定顺序。

---

## 4. 32 格穷举的实测分类

**实测（`t4_probes/p11_tally.py` 与 `p13_tally_probe.py` 亲跑，真数据 = `rp.templates()`
的 18 套）**：

```
=== 实测分类（32 格）===
{'no_layer': 8, 'no_bucket': 6, 'unreachable': 3, 'matched': 15} sum = 32
=== 期望表分类 ===
{'no_layer': 8, 'no_bucket': 6, 'unreachable': 3, 'matched': 15}
```

**与 P4-A3 的链 `NO_LAYER → NO_BUCKET → NO_TEMPLATE → UNREACHABLE → NOT_APPROVED → MATCHED`
下的预测 `{8, 6, 3, 15}` 逐字相符** ✓（`NO_TEMPLATE` 与 `NOT_APPROVED` 在满矩阵 +
18 套全 `approved` 的真数据上是 **0 格**，各由一条附加测试守）。

**六支 `reason` 各取一例（实测输出，逐字）**：

| status | 输入 | `reason` |
|---|---|---|
| `no_layer` | `('insufficient_data', 'endurance', 'normal')` | `有效项不足 4 项，本日不分层` |
| `no_bucket` | `('red', None, 'normal')` | `6 个短板判定项全部无效（缺测或无判定线），无法确定主导短板` |
| `unreachable` | `('green', 'endurance', 'abnormal')` | `模板 GRN-END-ABN-13 是预留位（reachable: false），当前不参与匹配` |
| `matched` | `('red', 'endurance', 'normal')` | `匹配到模板 RED-END-NOR-02` |
| `not_approved` | 构造 `RED-END-ABN-01` 的 `PENDING` 副本 | `模板待审校（RED-END-ABN-01 的 review.status = pending），拒绝生成处方` |
| `no_template` | 从注入映射里删掉 `RED-STR-NOR-04` | `处方模板矩阵里缺 (层 red, 主导短板 strength, 体成分 normal) 这一格：那是模板数据缺失，不是这个学生不该有处方` |

**15 个 `MATCHED` 的 `template_id`（实测排序后）**：
`GRN-END-NOR-14` `GRN-SPD-NOR-18` `GRN-STR-NOR-16` `RED-END-ABN-01` `RED-END-NOR-02`
`RED-SPD-ABN-05` `RED-SPD-NOR-06` `RED-STR-ABN-03` `RED-STR-NOR-04` `YEL-END-ABN-07`
`YEL-END-NOR-08` `YEL-SPD-ABN-11` `YEL-SPD-NOR-12` `YEL-STR-ABN-09` `YEL-STR-NOR-10`
（**期望侧是测试里字面写死的**，这一行是实际侧的实测值，两侧不同源。）

**3 个 `UNREACHABLE` 的格子**：`(green, endurance, abnormal)` /
`(green, strength, abnormal)` / `(green, speed_flexibility, abnormal)`
→ `GRN-END-ABN-13` / `GRN-STR-ABN-15` / `GRN-SPD-ABN-17`。

**`_MATRIX_32` 按链的顺序分 6 段排列**（`NO_LAYER` 8 行 → `NO_BUCKET` 6 行 →
`NO_TEMPLATE` 0 行（注释说明为什么是 0 行、由哪条测试守）→ `UNREACHABLE` 3 行 →
`NOT_APPROVED` 0 行（同）→ `MATCHED` 15 行），承重格 `(green, None, abnormal)`
在表里带一条专门的注释，并另有一条单格测试
`test_the_load_bearing_cell_green_none_abnormal_is_no_bucket_not_unreachable`
（含一个反面对照格 `(green, endurance, abnormal)` → `UNREACHABLE`，证明
「这一格恒判 `NO_BUCKET`」没有把 `UNREACHABLE` 那一支一起关掉）。

---

## 5. 新增/搬动测试逐条清单

### 5.1 `backend/tests/domain/test_prescription_match.py`（新建，**11 条**）

| # | 条目 | 守什么 |
|---|---|---|
| 1 | `test_thirty_two_cell_matrix_is_classified_cell_by_cell` | 32 格逐格比 `status` + `template_id` + `template is None` + `reason` 非空；offender 一次性报全 |
| 2 | `test_thirty_two_cell_matrix_is_exhaustive_and_tallies_to_the_literal_counts` | **表自己**的自校：32 行、无重复、恰为全笛卡尔积（4×4×2）、四类计数逐字 = `{8,6,3,15}`。⚠️ 主语是 `_MATRIX_32`、**不是** `match_template`（硬规矩 #56），故它在变异下**不开火**——这是刻意的，见 §7 |
| 3 | `test_the_load_bearing_cell_green_none_abnormal_is_no_bucket_not_unreachable` | P4-A3 的承重格 + 一个反面对照格 |
| 4 | `test_match_rejects_an_unapproved_template` | `NOT_APPROVED` + `reason` 含「待审校」；**并钉住 `UNREACHABLE` 先于 `NOT_APPROVED`**（第二个断言用「不可达 + PENDING」的副本） |
| 5 | `test_match_rejects_a_missing_matrix_cell` | `NO_TEMPLATE` + `reason` 含三个维度 token + 反面对照（其余 17 格不受影响） |
| 6 | `test_match_is_deterministic_under_dict_ordering` | `dict(reversed(...))` 下 32 格的 `MatchOutcome` 逐个 `==` |
| 7 | `test_matched_outcome_carries_the_injected_template_object_itself` | `outcome.template is templates[...]`（不抄副本） |
| 8 | `test_match_status_has_exactly_the_six_pinned_members` | 6 个 `(name, value)` 二元组 + **声明序** |
| 9 | `test_match_input_and_outcome_are_frozen_dataclasses` | 两个值对象都是 frozen dataclass，字段名与**顺序**逐字 |
| 10 | `test_no_layer_reason_is_verbatim_the_stratify_z0_reason` | `NO_LAYER` 的 `reason` == `stratify._REASON[RuleId.Z0]`（测试侧触私有名，先例与理由写在 docstring） |
| 11 | `test_a_hand_built_reachable_green_abnormal_template_is_matched` | 把 §3.3 那个「守不住」钉成**期望行为** |

### 5.2 `backend/tests/domain/test_prescription_exercises.py`（新建，**1 条**，是**搬动**不是新增）

`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable` 从
`tests/test_refdata_prescription.py` **移过来**（Ruling 107-1 → Ruling 134-1③）。
**断言与期望值一个字未改**，只在 docstring 里加了一段「本条自 Task 4 起住在
``tests/domain/``」与失效形态说明。`tests/test_refdata_prescription.py` 的条数
**57 → 56**（亲跑 `--collect-only -q`）。

⚠️ **是「移动」不是「复制」**：Ruling 107-1 的原文写的是「搬/复制过去」，我选**搬**。
两份重复的守卫会各自漂移（硬规矩 #51 讲的是「同一段逻辑的两个副本要逐份修」，
不是「同一条测试要留两份」），而这条测试守的是 `EquivalenceTable.lookup` 的分支，
留在 `tests/test_refdata_prescription.py` 一份、搬到 `tests/domain/` 一份，
删掉任何一份都还有另一份绿着——那正好是它要防的失效形态的反面。

---

## 6. 覆盖率增量的解释（派单要「你报数 + 解释增量」）

```
$ cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing
Name                                   Stmts   Miss Branch BrPart  Cover   Missing
----------------------------------------------------------------------------------
app\domain\__init__.py                     0      0      0      0   100%
app\domain\derive.py                     146      0     54      0   100%
app\domain\indicators.py                  62      0     14      0   100%
app\domain\percentile.py                  94      0     26      0   100%
app\domain\prescription\__init__.py        5      0      0      0   100%
app\domain\prescription\exercises.py      38      0      6      0   100%
app\domain\prescription\match.py          41      0     12      0   100%
app\domain\prescription\templates.py      58      0      0      0   100%
app\domain\stratify.py                    92      0     20      0   100%
app\domain\tables.py                       5      0      0      0   100%
----------------------------------------------------------------------------------
TOTAL                                    541      0    132      0   100%
591 passed, 1 skipped in 141.91s (0:02:21)
```

**Task 3 结案 → Task 4 结案**：`499 stmts / 120 branch` → **`541 stmts / 132 branch`**，
`Miss 0 / BrPart 0 / 100%` 维持。

* **stmts +42** = `match.py` **+41** ＋ `prescription/__init__.py` **+1**（4 → 5：
  新增的那一句 `from .match import (…)`；`__all__` 里追加 4 个字符串**不新增语句**，
  它还是同一个 `ast.Assign`）。
* **branch +12** = `match.py` 的 12 个分支弧，逐个可指认：
  `if inp.layer is Layer.INSUFFICIENT`（2）＋ `if inp.dominant_bucket is None`（2）＋
  `for template_id in sorted(templates)`（2：进循环体 / 正常走完）＋
  `if (…) != wanted`（2）＋ `if not template.reachable`（2）＋
  `if template.review_status is not ReviewStatus.APPROVED`（2）= **12**。
  即控制者「算不准 branch 数」的那个问题答案是 **12**：这条链有 **6 个判定点**，
  每个 2 弧。（口径与 Ruling 108 记的相同：`@dataclass` 生成的
  `__init__`/`__repr__`/`__eq` 不计入、装饰器行计入、docstring 的 `Expr` 不计入。）
* **`BrPart 0`**：6 个判定点的每一支都有测试走到——`NO_LAYER` 真/假由 8 格 / 24 格覆盖；
  `NO_BUCKET` 真/假由 6 格 / 26 格；`for` 的「正常走完」弧由
  `test_match_rejects_a_missing_matrix_cell` 覆盖（其余 31 格都在循环里 `return`）；
  `!= wanted` 的两侧由 32 格里的命中/不命中覆盖；`not reachable` 真/假由 3 格 / 15 格；
  `review_status is not APPROVED` 真/假由 `test_match_rejects_an_unapproved_template` / 15 格。
* **`MatchStatus` 的 6 个成员各至少有一格/一条测试走到**：`NO_LAYER`(8 格) /
  `NO_BUCKET`(6 格) / `UNREACHABLE`(3 格) / `MATCHED`(15 格) /
  `NOT_APPROVED`(附加测试) / `NO_TEMPLATE`(附加测试)。枚举成员本身不产生 branch，
  故这件事**不被覆盖率看见**——它由 #8 那条「6 个成员字面钉住」的测试守。

**passed 增量**：`581 → 592`（不带 coverage）= **+11**，全部来自
`test_prescription_match.py` 的 11 条新测试。
⚠️ **派单说「①②③ 会让 passed 数变化」，实测不成立**（§11 的 **CE-7**）：
① 与 ② 是改写既有测试的**内部实现**（条数不变），③ 是把 1 条测试从 A 文件搬到 B 文件
（`test_refdata_prescription.py` 57 → 56、`test_prescription_exercises.py` 0 → 1，净 0）。

---

## 7. 变异验收（简报 Step 2–5 的 ①②③ + 控制者加的 ④，全部**串行**跑）

harness = `t4_probes/p12_mutate.py`（完整输出 = `t4_probes/mutate_log.txt`，7 733 B）。
每个相位都：① 字节级写入变异；② 在**剥掉 docstring 的 `ast.dump`** 上确认真的改了代码；
③ 跑 32 格 tally（子进程 `p13_tally_probe.py`）；④ 跑全量 `pytest -q`；
⑤ 按字节还原并核 sha256 == `40E08F5587C92F46`。**6 个相位一次串行跑完，
没有与任何别的命令并行**（硬规矩 #62）。

| 相位 | 变异 | `ast.dump` 真变？ | 32 格实测分类 | 与期望表不符的格数 | pytest | 红的是哪条断言 |
|---|---|---|---|---|---|---|
| **M0** | 不变异（已知 GREEN 的对照，硬规矩 #53） | False（应 False ✓） | `{no_layer:8, no_bucket:6, unreachable:3, matched:15}` | 0 | **exit 0，592 passed** | — |
| **MUT-①** | 删掉 `reachable` 检查（整个 `if not template.reachable: return …` 块） | **True** | `{no_layer:8, no_bucket:6, **matched:18**}` | **3** | exit 1，**3 failed, 589 passed** | 见下 |
| **MUT-②** | 删掉 `review_status` 检查（整个 `if … is not ReviewStatus.APPROVED: return …` 块） | **True** | `{8,6,3,15}`（**不变**，穷举里 18 套全 approved） | 0 | exit 1，**1 failed, 591 passed** | `test_match_rejects_an_unapproved_template` |
| **MUT-③** | 删掉 `Layer.INSUFFICIENT` 分支 | **True** | `{**no_template:6**, **no_bucket:8**, unreachable:3, matched:15}` | **8** | exit 1，**2 failed, 590 passed** | 见下 |
| **MUT-④** | 把 `UNREACHABLE` 的判据提到 `NO_BUCKET` **之前** | **True** | `{no_layer:8, **no_bucket:5**, **unreachable:4**, matched:15}`（**总数仍 32**） | **1** | exit 1，**3 failed, 589 passed** | 见下 |
| **M1** | 语义等价改写：`sorted(templates)` → `sorted(templates.keys())` | **True**（AST 真变、运行时值不变） | `{8,6,3,15}` | 0 | **exit 0，592 passed** | — |

**逐条判据（硬规矩 #65：指明哪个断言分支开火）**：

* **MUT-①**（变异 ①）——`3 failed`：
  1. `test_thirty_two_cell_matrix_is_classified_cell_by_cell`，开火的是
     `if got.status is not want_status:` 那一支，**红的正是那 3 格**：
     `(green, endurance, abnormal)` / `(green, strength, abnormal)` /
     `(green, speed_flexibility, abnormal)`，实测逐个报
     `status = matched，期望 unreachable`（且 `template_id` 分别是
     `GRN-END-ABN-13` / `GRN-STR-ABN-15` / `GRN-SPD-ABN-17`）。
  2. `test_the_load_bearing_cell_green_none_abnormal_is_no_bucket_not_unreachable`，
     开火的是它末尾那个**反面对照**断言 `assert control.status is MatchStatus.UNREACHABLE`。
  3. `test_match_rejects_an_unapproved_template`，开火的是它末尾那个
     「`UNREACHABLE` 先于 `NOT_APPROVED`」断言（`GRN-END-ABN-13` 的副本）。
  **与 P4-A4 的更正相符**：3 格全部变成 `MATCHED`、**没有一个变成 `NOT_APPROVED`**
  （18 套全是 `approved`）。
* **MUT-②**（变异 ②）——`1 failed`，且**正是** `test_match_rejects_an_unapproved_template`
  （开火的是 `assert got.status is MatchStatus.NOT_APPROVED`）。
  ⚠️ 32 格穷举在这个变异下**不红**（`MISMATCH 0`）——那是**期望的**：真数据 18 套全
  `approved`，穷举里根本走不到 `NOT_APPROVED` 这一支。这也正是简报要求「附加测试」的理由。
* **MUT-③**（变异 ③）——`2 failed`：
  `test_thirty_two_cell_matrix_is_classified_cell_by_cell`（**8 格**全红：6 格变成
  `no_template`、2 格变成 `no_bucket`——后两格是 `(insufficient_data, None, *)`，
  因为 `NO_LAYER` 那一支没了之后就落到 `NO_BUCKET`）
  与 `test_no_layer_reason_is_verbatim_the_stratify_z0_reason`
  （开火的是 `assert got.status is MatchStatus.NO_LAYER`）。
  **派单的判据「8 个 `NO_LAYER` 组合必须红」逐字成立**（tally 的 `MISMATCH 8`）。
* **MUT-④**（控制者加的 ④，P4-A3 的承重处）——`3 failed`：
  1. `test_the_load_bearing_cell_green_none_abnormal_is_no_bucket_not_unreachable`
     （`assert got.status is MatchStatus.NO_BUCKET`，实为 `unreachable`）；
  2. `test_thirty_two_cell_matrix_is_classified_cell_by_cell`（**1 格**：
     `(green, None, abnormal)`，报 `status = unreachable，期望 no_bucket`）；
  3. `test_a_hand_built_reachable_green_abnormal_template_is_matched`
     （提前返回让那条「手工构造 `reachable=True` 就该 `MATCHED`」的期望行为也变了）。
  **即：穷举测试在这个变异下确实会红，顺序被真的测住了。**
  ⚠️ **但控制者预测的分类数字写反了**——见 §11 的 **CE-3**。
  ⚠️ **`test_thirty_two_cell_matrix_is_exhaustive_and_tallies_to_the_literal_counts`
  在这个变异下不红**，这是**设计如此**：它 tally 的是**期望表自己**（主语是
  `_MATRIX_32`，硬规矩 #56 要求标出来），不是实际结果；它守的是「谁删掉穷举表的一行」，
  不是「谁改了链的顺序」。这一分工写在它自己的 docstring 里。

**还原核验**：6 个相位每一次都 `assert hashlib.sha256(MATCH.read_bytes()).hexdigest() == ORIG_SHA`
通过，最终 `match.py` sha256[:16]（裸字节，纯 LF 故与归一化后同值）= **`40E08F5587C92F46`**
= 开工落盘时的值。

---

## 8. 改动面自证（硬规矩 #32，**带对照组**）

脚本 = `t4_probes/p14_change_surface.py`（尺子 = 「归一化 CRLF→LF 后 `ast.parse` →
剥掉每一层 docstring → `ast.dump` 逐字比对」；基线 = `git show ab075d3:<path>` 的 blob 字节）。

**结果**：基线 `ab075d3` 下 `backend/app` 的 `.py` 共 **44** 个，其中

* **SAME = 43 个**（逐个列名，含 `derive.py` / `indicators.py` / `percentile.py` /
  `stratify.py` / `tables.py` / `prescription/exercises.py` / `prescription/templates.py` /
  `refdata_prescription.py` / `db/**` / `pipeline/**` / `seed/**` / `adapters/**` / `config.py`）
* **DIFF = 1 个**：`backend/app/domain/prescription/__init__.py`（**授权面内**：公开面那几行）
* **新增（基线里没有）= 1 个**：`backend/app/domain/prescription/match.py`（**授权面内**）
* **授权面之外的改动 = 无 ✓**（脚本以此作为退出码判据，实测 exit 0）

**对照组（证明这把尺子既不是恒 SAME、也不是恒 DIFF）**：

| 对照 | 文件 | 变异 | 尺子判定 | 期望 |
|---|---|---|---|---|
| 阳性 1 | `app/domain/stratify.py` | `MIN_VALID_COUNT = 4` → `5` | **DIFF** | DIFF ✓ |
| 阳性 2 | `app/domain/derive.py` | `if score < line:` → `if score <= line:` | **DIFF** | DIFF ✓ |
| 阳性 3 | `app/domain/prescription/exercises.py` | `lookup` 的 `>=` → `>` | **DIFF** | DIFF ✓ |
| 阳性 4 | `app/domain/prescription/templates.py` | `is_reachable` 里 `ABNORMAL` → `NORMAL` | **DIFF** | DIFF ✓ |
| 阴性 1 | `app/domain/stratify.py` | **只改一句 docstring** | **SAME** | SAME ✓ |
| 阴性 2/3 | `tables.py` / `stratify.py` | 自比 | **SAME** | SAME ✓ |

阳性 **4** 个（派单要 2–3 个）、阴性 **3** 个，全部与期望相符。
每个锚点都先用 `t4_probes/p15_anchors.py` 亲验过 `hits == 1`，harness 里再 `assert`
一次命中次数——**命中 0 次就当场炸，不静默跳过**（我第一版就是静默跳过，
9 个变异只真跑了 1 个，见 §12）。对照组全部在内存里做、**一个字都不落盘**，
每个文件跑完后 `assert p.read_bytes() == raw` 且 sha256（归一化后）逐个复核通过。

⚠️ 阴性对照 1（只改 docstring 必须报 SAME）是这一组里**最要紧**的一条：没有它，
「43 个 SAME」可能只是尺子在拿散文差异当代码差异的反面——即尺子**过松**到把
docstring 剥干净之后什么也不比。它证明了「剥 docstring」那一步真的在生效。

---

## 9. 两份架构守卫的改动

### 9.1 三处过期陈述：**改了 5 处、不是 6 处**（② 只有一份）

派单说「两份守卫是同一段逻辑的两个副本（硬规矩 #51），改的时候两份都要查、
报告里列出份数」。亲跑 `git grep -n` 的结果：

| 陈述 | `test_domain_purity.py` | `test_layering.py` | 份数 |
|---|---|---|---|
| ① `pkg_cases` 里那条「子包今天还不存在、将来某个 Task 才会建它」的注释 | ✓ 命中 | ✓ 命中（同一处） | **2** |
| ② allow-list 那条守卫 docstring 里「子包已建出、某个 Task 一写 `from ..indicators import X` 它就开始出现」那半句，而它把 `match.py` 归给了**错的那个 Task** | ✓ 命中 | **0 命中** | **1** |
| ③ `cases` 矩阵里那一格绿档的注释，把「谁加的、为哪个 Task 埋的」记错了**两处** | ✓ 命中 | ✓ 命中（同一处） | **2** |

（三处的可 grep 原文由派单与简报 P4-A6 给出；本报告按硬规矩 #74 **不逐字复述**被撤销的
写法、只描述——否则将来 grep 那些串会同时命中简报、计划与本报告，分不清错误是否还在。）

`git grep -n "这一层子包已经建出" -- backend/tests` **只命中一处**
（`test_domain_purity.py`），故 ② 在 `test_layering.py` 里根本不存在。
**合计改了 5 处**（见 §11 的 **CE-6**）。

改法（三处都按硬规矩 #74：被撤销的写法**不逐字复述**，只描述）：

* **①** 两份都改成「子包自 Task 2 起就存在、Task 3 填满、Task 4 又加了 `match.py`」；
  而且这一段随 ② 的重写一起**整段被替换掉了**（见 §9.2）——手写的 4 格 `pkg_cases`
  连同那条过期注释一起没了，取而代之的是扫真仓。
* **②** 改成「Task 4 的 `match.py` 已落地，但它选的是绝对导入 + `level == 1`，
  故 `level == 2` **将来**谁写才出现」。
* **③** 两份都改成「**Task 1 fix round 5** 为 **Task 4** 的形状埋的一格」，
  并加一段「⚠️ **Task 4 落地后这一格仍是「前瞻」、不是真仓形状**」+ 实测的
  `match.py` import 清单 + Ruling 104 的引用。

### 9.2 Task 3 转来的 ①② —— 我做成「**矩阵 + 扫真仓**」，不是「换成扫真仓」（**对派单的偏离，请裁定**）

两份守卫的 `test_absolute_folding_matches_resolve_name` 里，原来的手写 4 格 `pkg_cases`
被**替换**成一段扫真仓的对拍（这是转来的 ②，照字面做了）；同时**新增**一段扫真仓的
`ImportFrom` 对拍（这是转来的 ①）；**手写的 12 格 `cases` 矩阵保留**。

扫真仓那一段做两件事，`backend/` 下每个 `.py` 都过：

1. `_package_of(py)` 与 `py.relative_to(BACKEND).parent.parts` 对拍（**转来的 ②**，
   C-fr4-1 给的判据逐字照办）。两侧不同源：期望侧是 pathlib 自己的 `parent.parts`，
   被测侧是 `with_suffix("").parts[:-1]`；且 `__init__.py` 与同目录普通模块必须给出
   **同一个**包（那正是 `parts[:-1]` 的全部理由），扫描天然覆盖到 `app/db/models/` 那一对。
2. 它的每个相对导入现场折一次、与 `importlib.util.resolve_name` 对拍（**转来的 ①**）。
   `from . import feedback, prescription` 那种「一个节点两个名字」按 Ruling 36 逐个展开。

**空转守卫**（三个下界 + 五个折算串，全部字面量）：`len(real_py) >= 40`
（实测 69）、`relative_seen >= 16`（实测 18）、
`{"app.db.models._shared", "app.db.models.feedback", "app.domain.prescription.exercises",
"app.domain.prescription.match", "app.domain.prescription.templates"} ⊆ folded`。
第 2 与第 4 个折算串各有专门用意：`app.db.models.feedback` 钉住「一名一条的展开」在
**真仓**上也在场（此前只有合成的 `from .. import seed, pipeline` 那一格），
`app.domain.prescription.match` 钉住本 Task 新加的那一句真的被扫到了。

⚠️ **为什么保留矩阵而不是照字面「换成」**（这条理由也逐字写进了两份守卫的注释）：
真仓今天

* **(a)** 没有任何 `level >= 2` 的相对导入（Task 2/3/4 三轮都刻意选绝对导入，Ruling 104）；
* **(b)** 没有任何越界档（`resolve_name` 抛 `ImportError`、`_absolute` 必须返回 `None` 那一档）；
* **(c)** 没有任何 offender（真仓里没有一句 `import app.seed`；purity 侧也没有一条
  落在白名单外的 import）。

这三类**只有手写的矩阵能提供**。删掉矩阵会让 `_absolute` 的
`if level - 1 > len(package): return None` 与 `_is_allowed` / `_is_forbidden` 的 RED 判定
**同时失去守卫**——那正是 Ruling 35/46 修掉过的那个失效形态（账本逐字记着
「谁把**两份**的 `if level - 1 > len(package): return None` 都删掉，在基线 `1fa9941` 上
全量 **479 passed、退出码 0**」）。而且 **Ruling 56 自己把「换成全仓扫描」的前提写成**
「届时 `level == 2` 的**合法**相对导入开始真实出现，正是把矩阵换成全仓扫描的最佳时机
（那时才有足够的真实形状可扫）」——**那个前提到今天仍未成立**（Ruling 104 已经推翻过它一次）。

**处置**：做成**超集**（矩阵保留 + 扫真仓新增），并在两份守卫的注释里写明
「它是那 12 格矩阵的**补充、不是替代**」+ 上面 (a)(b)(c) 三条实测理由。
**报为对派单字面的偏离，请控制者裁定**（派单明写「若你判断某一项该推到 Task 5，
报为关切并说明理由——不要为了『符合派单』而硬做」；我的判断不是推迟、而是**改做法**，
因为按字面做会削弱守卫）。

⚠️ **两份是同一段逻辑的两个副本，逐份都改了**（硬规矩 #51）：`test_domain_purity.py`
用 `_imported_modules(tree)`（yield 四元组）拿原始入参，`test_layering.py` 的
`_imported_modules(tree, package)` 已经把折算做完了、拿不到 `(module, level, name)`，
故那一份**直接 `ast.walk`**，并在注释里写明为什么刻意不复用它。两份的判据函数不同
（`_is_allowed` vs `_is_forbidden`），故注释里的 (c) 一条措辞不同——这不是抄错。

### 9.3 会变计数（硬规矩 #66：改前先 grep 出全部同类计数）

**先 grep**（`t4_probes/p09_grepfile.py`，逐个模式跑）：`17 条` / `{1: 17}` / `那 4 条` /
`实测 17` 在两份守卫里的命中，改完后**全部 0 命中**（并且用一个已知存在的串验证过
查询本身有效）。

| 计数 | 改前 | 改后（实测） | 出现处 |
|---|---|---|---|
| 全仓相对导入（**当前值**） | 16（Task 3 结案） | **18**，`{1: 18}` = `app/db/models` 13 + `app/domain/prescription` 5 | 两份守卫各 2 处（`_imported_modules` docstring + 测试 docstring）；purity 另在 allow-list 那条的 docstring |
| domain 侧相对导入折算出的**不同串** | 1（`….exercises`） | **3**（`….exercises` / `….match` / `….templates`） | purity 1 处、layering 1 处 |
| `SCANNED_DIRS` 扫描面 | 27（7+11+9） | **28**（7+11+**10**） | layering 的 `test_production_layers_never_import_app_seed` 注释（新加两行时点：Task 3 结案 27、Task 4 后 28，并给出 domain 那 10 个的逐个文件名） |
| 该守卫「单目录被搬空时仍剩几个 .py」 | `13…18`（按 24 算） | **`17…21`**（按 28 算：28−11=17、28−7=21、28−10=18）；旧的 `13…18` **保留**并标明绑它自己的时点 | layering 1 处 |
| purity `_assert_not_empty` 的「domain 有几个 .py」 | 6（绑 `e26347f`） | 保留 6，**新加**「本 Task 落地时实测 **10**」并说明下界 5 为什么**不需要**跟着改 | purity 1 处 |
| 扫真仓那段的空转守卫下界 | —（新加） | `>= 40` 个 .py（实测 69）、`>= 16` 条相对导入（实测 18）、5 个字面折算串 | 两份各 1 组 |

**刻意没改的历史值**（Ruling 106 CE-6 的纪律：绑定时点的历史陈述**不要顺手改**）：
`12 条`（绑 `6a2938f` / `7b84599`）、`14`（绑 `3ea27cc`）、`15 条 / {1: 15}`（绑 `c21767d`）、
`17`（绑 `e26347f`）、`24`（绑 `ad1d190`）、`479 passed`（绑 `1fa9941`）、
`481 条`（绑当时 HEAD）、`2 failed, 529 passed`（绑 `2df6825`）。

---

## 10. Task 3 转来的 4 项，逐条处置

| 项 | 内容 | 处置 |
|---|---|---|
| **①** | `cases` 矩阵换成「扫真仓每个 `.py` 逐个对拍 `resolve_name`」（Ruling 56/66） | **做了，但改成「矩阵 + 扫真仓」的超集**，不是替代。理由与实测证据见 §9.2（按字面做会让 Ruling 35/46 修掉的假绿复活）。**报为对派单的偏离，请裁定。**两份守卫各一份。 |
| **②** | `_package_of` 的断言换成「扫真仓每个 `.py` 与 `py.relative_to(BACKEND).parent.parts` 对拍」（C-fr4-1） | **做了，照字面**。手写的 4 格 `pkg_cases` 整块删掉（连带 ① 那条过期注释），换成扫真仓；**保留了后面那段「把 `_package_of` 的输出喂给 `_absolute`」的后果检查**，因为它用的是真仓里**不存在**的 `level == 2` / `level == 3` 导入，扫描替代不了它（注释里写明了两段互不替代）。两份各一份。 |
| **③** | `EquivalenceTable.lookup()` 的分支测试搬到 `tests/domain/test_prescription_exercises.py`（Ruling 107-1） | **做了，是「搬」不是「复制」**（§5.2 说明为什么）。断言与期望值一个字未改；`test_refdata_prescription.py` 57 → 56 条，新文件 1 条，**passed 数净 0**。连带改了 4 处交叉引用（`IMPACT_DESCENDING` 的 `#:` 注释、`test_equivalence_never_maps_to_a_higher_impact_level` 的 docstring、`test_impact_rank_values_are_pinned_verbatim` 的 docstring 两处）与 2 个不再被使用的 import（`EquivalenceMapping` / `EquivalenceTable`）。 |
| **④** | `test_impact_rank_values_are_pinned_verbatim` 的 docstring 缺「本条之前」这个时点（Ruling 127-5） | **做了**。原句以「今天」开头却讲「本来只有两条间接守卫」（时间态自相矛盾），改成「**本条加入之前**（Task 2 fix round 2 落地，账本 Ruling 107-2）看着它的只有两条**间接**守卫」，并把两条守卫**点名**（原来写的是「上面那条」，而 ③ 搬走之后「上面」已经不成立了）。同一段里的 M-A1 变异记录也补了时点（那两个 passed 数是 Task 2 时点的、且当时 `lookup` 那一条还在本文件里）。 |

**⑤⑥⑦⑧（Task 3 结案清单的另 4 项）**：⑤（两份守卫的「子包今天不存在」注释已过期）
= 本报告的 ①，**已做**；⑥（`match.py` 若写 `level == 2` 相对导入，全仓计数与 level 分布
要更新）= **不适用**（我选了 `level == 1`，`level == 2` 仍不存在；但计数确实变了——
从 16 变 **18**，理由见 CE-2，散文已更新）；⑦（`match.py` 必须拒绝 `Layer.INSUFFICIENT`
与 `review_status != approved`）= **已做**（§4 / §7 的 MUT-③ 与 MUT-②）；
⑧（4 处钉死基线的更新模式，Ruling 136 可复用）= **已复用**（§11 之外的
`_PRESCRIPTION_PUBLIC_BASELINE` 就是照 Ruling 136-1 的「(名字, 所有者模块) 二元组」模式
追加的，且仍是字面清单）。

### 10.1 `_PRESCRIPTION_PUBLIC_BASELINE` 的更新（Ruling 136-1 模式）

* 长度 **20 → 24**，新增 4 项，所有者一律 `app.domain.prescription.match`：
  `("MatchStatus", …)` / `("MatchInput", …)` / `("MatchOutcome", …)` / `("match_template", …)`，
  声明序照 `prescription/__init__.py` 里 `__all__` 的书写序（而后者照 `match.py` 的书写序）。
* `assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 24, "基线是 24 个名字，抄漏了就当场红"`
  与 `assert len(set(names)) == 24, …` —— **两处都改了**（派单点名的那条报错文案也一起改）。
* `_OWNED_MODULES` 从 2 个扩到 **3 个**（加 `app.domain.prescription.match`），
  并在 `#:` 注释里写明：`match.py` 模块级 import 进来的 `WEAKNESS_ITEMS` /
  `MIN_VALID_COUNT` / `Layer` / `BodyCompState` / `ReviewStatus` / `Template`
  **不是**它的公有顶层定义（`_public_top_level_definitions` 只数 `class` / `def` / 赋值），
  故支 5 不会要求它们被第二次重导出。
* **仍是字面清单**（硬规矩 #35），没有改成 `list(pkg.__all__)`。
* 连带改了 5 处散文计数（模块 docstring 的「闸 4」那一段、`_PRESCRIPTION_PUBLIC_BASELINE`
  的 `#:` 注释、`test_prescription_public_namespace_is_pinned_verbatim` docstring 的
  三处「20 个」与「两个模块」）。

---

## 11. 我发现的控制者错误（逐条注明成立 / 不成立 / 歧义 + 证据）

### 11.1 成立

**CE-1（成立，Important）— 派单说「`app/domain/percentile.py` 里有一处先例是「触私有名」」，不成立。**

亲跑 `git grep -n "触私有名" -- backend` 只命中**两处，都是测试文件**：
`backend/tests/domain/test_percentile.py`（那句 `from app.domain.indicators import
_lower_is_better` 带行内注释「触私有名：本条要比较的正是它」）与
`backend/tests/integration/test_golden_cases.py`（「测试触私有名是本项目既有惯例」）。
而 `app/domain/percentile.py` 里的两处**恰好是相反的纪律**，逐字是
「只用公开 API（…），**不 import 私有名** ``_lower_is_better``（本模块的既有纪律，
见 :func:`national_norm`）」与「用公开 API（``score_item`` 比首末两点）自己推一次，
**不去 import 私有名** :func:`app.domain.indicators._lower_is_better`」。

**后果**：派单把「生产码可以 import 私有名」这个先例指错了文件，而真实的先例是
「**测试**可以、**生产码**刻意不」。若照派单办，`match.py` 会
`from app.domain.stratify import _REASON`，成为 domain 生产层第一处私有名 import，
与 `percentile.py` 两处明写的纪律直接冲突。
**我的处置**：生产码持副本（插值公开的 `MIN_VALID_COUNT`）+ 测试侧漂移守卫触私有名
（照 `test_percentile.py` 那个先例，行内注释与 docstring 都写明理由）。见 §3.4。

**CE-2（成立，Important）— 简报 P4-A6 与派单 §2 都预测「`match.py` 写相对导入之后，全仓相对导入的条数会变成 17」。实测是 **18**——两处都少算了一条。**

亲跑（脚本 `t4_probes/p04_counts.py` 与 `p16_final.py`，AST 扫 `backend/app` 全部 `.py`
的 `ImportFrom` 且 `level > 0`）：改前 **16**（`app/db/models` 13 + `app/domain/prescription` 3），
改后 **18**（13 + **5**），level 分布 `{1: 18}`。

**少算的那一条是 `prescription/__init__.py` 的 `from .match import (…)`**——而它不是
「可选的额外一条」，是**同一个 P4-A6 的第 1 项自己要求的**（「公开面重导出 `MatchInput` /
`MatchOutcome` / `MatchStatus` / `match_template`」）。即 P4-A6 的第 1 项与它自己给出的
计数预测互相矛盾。派单 §2 的「控制者的补充裁定」给了两个分支各自的预测值，
**两个分支都少算了 `__init__.py` 那一条**（按硬规矩 #74，这里只描述、不逐字复述）：

* 「沿用绝对导入则全仓计数不变」——不成立。`match.py` 无论如何要从某处拿 `Template`
  （我选的是同包相对串），而**即使它选绝对串**，`prescription/__init__.py` 新增的那一句
  `from .match import (…)` 自己就是一条 `level == 1` 的相对导入，故那个分支的实测值是
  **17**、不是 16。
* 「写 `level == 2` 则计数变成 17、level 分布变成一条 `level 2` 加原来的 `level 1`」——
  那个分支的实测值应是 **18**、分布 `{1: 17, 2: 1}`。

**我的处置**：按实测的 18 写进两份守卫的散文（并把「Task 4 一次加了 2 条、不是 1 条」
与理由写明），扫真仓那段的下界取 `>= 16`（留余量的空转守卫，不是钉死值）。

**CE-3（成立，Important）— P4-A3 预测的「顺序对调后的分类」把两个数写反了。**

三处都写着同一组数（简报 Task 4 全节、账本 P4-A3 节、派单 §2 与 §3 的变异 ④ 判据）：
「顺序反过来之后 `NO_BUCKET` 是 **4**、`UNREACHABLE` 是 **5**」（按硬规矩 #74 只描述
那两个数、不逐字复述整句）。**实测恰好相反：`NO_BUCKET` 是 5、`UNREACHABLE` 是 4。**

**实测（变异 MUT-4，`t4_probes/mutate_log.txt`）**：
`{no_layer: 8, no_bucket: **5**, unreachable: **4**, matched: 15}`，总数仍 32、
与期望表不符的格子 **1** 个 = `(green, None, abnormal)`。

**推导**（与实测一致）：`UNREACHABLE` 的判据是「绿层 + 体成分异常」，在
`{green} × {endurance, strength, speed_flexibility, None} × {abnormal}` = **4** 格上成立
（不是 5）；`NO_BUCKET` 的 6 格里被它抢走的只有 `(green, None, abnormal)` **1** 格，
故剩 **5**（不是 4）。要得到「`UNREACHABLE` 5 格」需要判据在 5 格上成立，
而 4 桶 × 1 层 × 1 体成分最多 4 格。

⚠️ **P4-A3 的承重结论不受影响、而且我逐条复现了**：链
`NO_LAYER → NO_BUCKET → NO_TEMPLATE → UNREACHABLE → NOT_APPROVED → MATCHED` 下
分类是 `{8,6,3,15}`（§4）；顺序对调后**总数仍是 32**，故「计数对得上证明不了顺序对」
这句是真的；`(green, None, abnormal)` 必须判 `NO_BUCKET` 也是真的（MUT-4 下正是它变红）。
**错的只是那两个数。** 按硬规矩 #75（裁定改变「一类做法」时要 grep 全文找同类），
我 grep 了这一组数在简报/账本/派单里的全部出现处：**3 处**，都是同一组错的数。

**CE-4（成立，Important）— 硬规矩 #76 执行得不彻底：简报里的裸行号不是 7 处而是 10 处，且其中 9 处是「当前有效的定位」；更严重的是它们全部指向 `a5bdebe` 的计划文本、而简报自称抽取自 `8631744`。**

亲跑（`t4_probes/p02_scan.py` + `p16_final.py`，正则逐个匹配反引号里的 `:NNN`）：

* **带文件名的 `` `X.py:NNN` `` = 2 处**：`` `derive.py:330` ``（**这一处是被撤销的旧说法**，
  P4-A5 正是在纠正它）与 `` `derive.py:129` ``（**当前有效的定位**）。
* **不带文件名的 `` `:NNN` `` = 8 处**：`` `:320` `` `` `:371` `` `` `:77` `` `` `:352` ``
  `` `:356` `` `` `:326` `` `` `:386-389` `` `` `:392` ``——**8 处全部是「当前有效的定位」**，
  没有一处是被撤销的旧说法。
* 合计 **10 处**（派单说 7 处；若把 `` `:352` ``/`` `:356` `` 算作一处、并只数不带文件名的，
  是 **7** 处——故派单那个 7 可能是这么数出来的，但它同时漏掉了「这 7 处**全都是**
  当前有效的定位」这个更要紧的事实）。

**更要紧的一层（这才是真错误）**：这些 `:NNN` **全部指向 `a5bdebe`（= 更正前）的计划文本**，
而简报头部逐字自称「抽取自 `Document/2026-10-06-实施计划02-智能处方引擎.md` @ commit
`8631744`」。亲跑 `git show <rev>:Document/…md`（脚本 `t4_probes/p17_planlines.py`）：

| 行号 | 在 `a5bdebe`（769 行）上是 | 在 `8631744` / `HEAD`（798 行）上是 |
|---|---|---|
| `:374` | `MatchStatus(str, Enum)`：6 个成员那一行 ✓ | 三处过期陈述的 **②** 那一行 ✗ |
| `:378` | `dominant_bucket is None` 那条决定（含 `derive.py:330`）✓ | 「⚠️ ①②③ 会让 passed 数变化」那一行 ✗ |
| `:380` | spec §11.2 那条决定 ✓ | `**Interfaces:**` ✗ |
| `:381` | 「不做 I/O、不读盘」✓ | `- Consumes: …` ✗ |
| `:385-389` | 32 格算术 + 8/6/3/15 分类 ✓ | `MatchStatus` 那行 / `match_template` 签名 / 空行 / `**决定**` / `dominant_bucket` 那条 ✗ |
| `:392` | 「frozen dataclass 可直接构造、不必改 YAML」✓ | 「不做 I/O、不读盘」 ✗ |
| `:394` | `_BUCKET_ORDER` 与 Ruling 100 那条 ✓ | `- [ ] **Step 1: 写失败测试**` ✗ |

**根因**：`8631744` 往 Task 4 的 Files 段插入了 6 个 P4-A* 更正块，把该节整体下推了
**11 行**（769 → 798 行，全文 +29 行）。控制者**在插入更正之前**算好了这些行号，
插入之后没有重算——这正是账本 Ruling 106 的 **CE-7** 记过的同一形态
（「裸行号已被编辑推走过一次」），也正是硬规矩 #76 要根治的东西。
**故：#76 立了、也开始执行了（P4-A5 确实给了 `git grep` 命令），但同一批更正里
新写下的 9 个裸行号在落盘的那一刻就已经是错的。**

**附带（同源）**：Task 3 结案清单第 ⑦ 项引的「计划 `:255`」（说
「`match.py` 必须拒绝 `Layer.INSUFFICIENT`」）——实测 `plan:255` 在 `a5bdebe` 与 `HEAD`
上**都是空行**（那一带是 Task 3 的 `.gitattributes` 更正块）。真正的出处是
`a5bdebe:379` / `HEAD:390`（可 grep 原文「**`layer == Layer.INSUFFICIENT` → `NO_LAYER`**」）。

**我的处置**：本报告与所有代码散文**一律不写裸行号**，改引用一律给可 grep 的原文
（例如「可 grep 原文 ``有效项不足``」「可 grep ``dominant_bucket: str | None``」）。
上面那张表是**为了举证**才复述行号的，且每一行都标明了「在哪个 rev 上」。

**CE-5（成立，Minor）— 派单说「①②③ 会让 passed 数变化，属预期」。实测三项都不改变 passed 数。**

* **①**（`cases` 矩阵 + 扫真仓）与 **②**（`_package_of` 断言换扫真仓）都是改写
  **既有测试函数的内部实现**，`test_*` 的个数一个字没变（两份守卫各仍是
  「三条架构守卫 + 一条辅助函数的单元测试」= 4 个 `test_*`，purity 的模块 docstring
  那句计数因此**不需要**改）。
* **③** 是把 1 条测试从 A 文件搬到 B 文件：`test_refdata_prescription.py` **57 → 56**、
  `test_prescription_exercises.py` **0 → 1**，**净 0**。
* 实测 `581 → 592` 的 **+11 全部**来自 `test_prescription_match.py` 新建的 11 条。

**CE-6（歧义 → 部分成立，Minor）— 「两份守卫是同一段逻辑的两个副本…改的时候两份都要查」：三处陈述里 ② 只有一份。**

`git grep -n "这一层子包已经建出" -- backend/tests` **只命中 1 处**
（`test_domain_purity.py`）；① 与 ③ 各命中 2 处。故总共改了 **5 处**、不是 6 处（§9.1 的表）。
判**歧义**而不是**成立**：派单没有明说三处都在两份里，而且它正好要求「报告里列出份数」
——那个要求本身就是防这件事的。列出来供控制者核对。

**CE-7（成立，Important，报为对派单的偏离）— 派单/账本要求把 `cases` 矩阵「换成」扫真仓；按字面做会削弱守卫。**

详见 §9.2。核心证据：真仓今天 (a) 0 条 `level >= 2`、(b) 0 个越界档、(c) 0 个 offender，
三类只有手写矩阵能提供；而 Ruling 56 自己把「换成」的前提写成「届时 `level == 2` 的
**合法**相对导入开始真实出现」，Ruling 104 已经证明那个前提没成立（Task 2/3/4 三轮都选
绝对导入）。删掉矩阵会让 Ruling 35/46 修掉过的「479 passed、退出码 0」假绿复活。
**做成超集（矩阵 + 扫真仓），请控制者裁定。**

### 11.2 不成立 / 控制者是对的（我核过，逐条给证据）

按 Ruling 45/51/65：把成立的辩掉与把不成立的认下来是同一种失职。下面这些我**逐项亲验过、
控制者是对的**（也就是派单要我做的「正面确认」）：

1. `git diff --name-only ab075d3 3473dc6 -- backend` **为空** ✓（代码基线确实是 `ab075d3`）
2. 5 个依赖版本逐个相符 ✓；**没有**撞上 SAC 的 `ImportError` ✓
3. 开工 `581 passed` ✓；`499 stmts / Miss 0 / 120 branch / BrPart 0 / 100%` ✓；
   `580 passed, 1 skipped`（带 coverage）✓，那 1 个 skip 确实是 trace-hook 自觉跳过 ✓
4. `task-4-brief.md` **24 221 B / 152 行** ✓（逐字节相符）；`progress.md` **299 059 B** ✓
5. `app.domain.prescription.__all__` = **20 个名字**，且派单列出的 20 个**逐个相符、顺序也相符** ✓
6. `templates.__all__` = **14 个** ✓；`ReviewStatus` 成员 = `PENDING="pending"` /
   `APPROVED="approved"` ✓；`is_reachable` 的函数体**逐字相符** ✓；
   `Template` 的 **14 个字段逐个相符、顺序也相符** ✓
7. `_PRESCRIPTION_PUBLIC_BASELINE` 今天 `len == 20`、报错文案含
   「基线是 20 个名字，抄漏了就当场红」✓
8. P4-A5 的**全部 6 个行号**（`derive.py` 的 129 / 320 / 371 / 77 / 352 / 356）
   **逐个相符**，且 `derive.py:330` **确实是空行** ✓；`_BUCKET_ORDER` 的注释里
   确实逐字写着「故 dominant_bucket 不依赖 dict 的哈希顺序（Ruling 100）」✓
9. P4-A7 的 Z0 文案**逐字相符**（`RuleId.Z0: f"有效项不足 {MIN_VALID_COUNT} 项，本日不分层"`），
   `explain()` 确实在 `stratify.py:326`、其 docstring 里确有「`Z0` 路径单独成句…」那句 ✓
10. spec §11.2 那一行**逐字相符** ✓；18 套模板的 `review.status` distinct 值
    **只有 `approved` 一个** ✓（故 P4-A4 的更正为真）
11. 全仓相对导入今天 **16 条、全部 `level == 1`** ✓；`SCANNED_DIRS` = **27**
    （pipeline 7 + db 11 + domain 9）✓；「加 `match.py` 后是 **28**（domain 变 10）」✓
12. **P4-A3 的链与 `{8,6,3,15}` 分类**：我独立实算 + 实跑，**逐格相符** ✓
    （错的只是「顺序对调后」的那两个数，见 CE-3）
13. 「两份守卫的空转守卫下界（`>= 8` 与 `>= 5`）都不会红」✓（实测两条都绿）
14. 「`match.py` 需要 import 的只有 `dataclasses` / `typing` / `collections.abc` + `app.domain.*`，
    全在 allow-list 内」——**基本成立**：我实际用的是 `collections.abc` / `dataclasses` /
    `enum` + `app.domain.indicators` / `app.domain.stratify` + 同包 `.templates`，
    全部命中 allow-list（`enum` 也在那 6 个串里）；**我没用 `typing`**
    （`X | None` 是 3.10+ 的原生写法）。purity 的三条守卫对 `match.py` 全绿 ✓
15. 「`Template` 是 frozen dataclass、构造期不校验 `review_status`，故不必改 YAML」✓
    （`dataclasses.replace` 造 `PENDING` 副本成功，18 个指纹一个没动）

---

## 12. 我自己本轮犯的错（7 条，全部自纠；其中 3 条是被我自己写的断言/闸门拦下的）

> ⚠️ 另有一条**不是我的错、但必须记**的工具事故，见本节末尾的第 8 条。

1. **`match.py` 第一版 import 了一个没用到的 `WeaknessBucket`，还写了一个 `__all__`
   把 4 个不属于它的名字声明成 re-export**。被**我自己写的落盘闸门探针**
   （`t4_probes/p07_gate_match.py` 的 `must_not` 清单）当场报 `RESID!! 2 WeaknessBucket`
   拦下——顺着查下去发现那个 `__all__` 会给 `Template` / `ReviewStatus` / `BodyCompState`
   造出**第四个住址**（`exercises` → `templates` → `__init__` → `match`），
   与 `prescription/__init__.py` 那条「每个名字都从它的所有者模块 import」的纪律直接冲突。
   两处都删了，并在 `__init__.py` 的 docstring 里把「``Template`` 取自 ``.templates``
   而不是 ``.match``」写明。（残留的 2 处 `WeaknessBucket` 是 docstring 里解释
   「为什么 `dominant_bucket` 标注是 `str | None` 而不是 `WeaknessBucket | None`」的散文，
   是刻意保留的。）
2. **`__init__.py` 的 docstring 第一版自相矛盾**：列了 4 个名字
   （`Template` / `ReviewStatus` / `BodyCompState` / `WeaknessBucket`）却说
   「后者…也 import 了**前三个**」。重读时自己抓出来，改成 3 个名字。
3. **改动面自证的对照组第一版是空跑的**：9 个变异里 **8 个锚点没命中、被静默跳过**，
   只有 1 个真跑了，而脚本照样打印「对照组通过」。这正是「空跑」那个失效形态。
   修法是：另写一个探针（`p15_anchors.py`）先把每个锚点的 `hits` 数打出来，
   harness 里再 `assert text.count(old) == 1`——**命中 0 次就当场炸**；
   最终对照组是 4 个阳性（全部 DIFF）+ 3 个阴性（全部 SAME）。
4. **把简报的「17」直接抄进了两份守卫的散文**，没有先自己数。最终的计数探针
   （`p16_final.py`）跑出 **18** 才发现——即我先信了派单的算术、后才实测。
   修法是两处散文都改成 18，并把「Task 4 一次加了 2 条、不是 1 条」与理由写明
   （这也就是 CE-2）。**教训与账本 Ruling 84/100 那条完全同构：控制者给的数也要自己跑一遍。**
5. **`p08_gate_init.py` 第一版报了 2 个假 MISS**：`__init__.py` 的工作树是 CRLF，
   而我的多行串查模式用的是 `\n`。修法是串查前先归一化，并把「文件是 CRLF」这件事
   一起打印出来。**这条与账本 Ruling 109 记的「用 `read_text()` 量行尾得到假观测」
   是同一族**（都是行尾口径没先确认）。
6. **三处更正说明差点逐字复述被撤销的原句**（硬规矩 #74）：
   `test_refdata_prescription.py` 里那个写错的类名、两份守卫 `cases` 注释里那个错归属、
   以及简报 P4-A6 那个少数了一条的预测。三处都在重读时改成**描述式**
   （「此前举的那个例子用的名字与简报给的不一致」「此前把这一格的归属记错了两处」
   「给出的那个预测少算了一条」），并各自注明「按硬规矩 #74 不再逐字复述」。
   ⚠️ 其中第一处我**先写成了逐字复述、然后自己发现并改掉**——记一条。
7. **`p10_dedent.py` 是一次空转**：SearchReplace 的 diff 回显给每行加了一个前导空格，
   我据此以为落盘的块多缩进了 1 格，写了一个专门的 dedent 脚本去修。脚本自己的
   `changed: 0` + sha256 前后相同（`CFF611A79167BBA5`）证明**文件本来就是对的**。
   没有造成损害（脚本是幂等的、且写前 `assert` 了锚点唯一），但白花了一轮。
   **教训：diff 回显的前导空格不是内容**；要判缩进要用 `repr()` 或直接量字节。

8. **⚠️ 工具/磁盘分歧家族的第 61–63 次（「连 diff 一起伪造」那个形态的第 3 次）：
   对 `task-4-report.md` 的三次编辑全部「报成功 + 回显了看起来正确的 diff」，而磁盘一个字节都没变。**
   发现方式：编辑完之后我跑了自己写的落盘闸门 `t4_probes/p18_gate_report.py`，
   它报 `RESID!!` 三处；我一开始以为是「串查模式写错了」，于是直接量文件——
   `75811 B / sha256[:16] = A673C075FC056050`，与三次编辑**之前**逐字节相同。
   即三次 diff 回显全是伪造的。
   **处置**（照账本 Ruling 135）：改用 python 字节级重写（`t4_probes/p19_fix_report.py`，
   每个锚点先 `assert text.count(old) == 1`、命中数不对就当场炸），
   写完再量：`76440 B / sha256[:16] = A8F56A73C1115CD7`，双向串查 5 个新串全 HAVE、
   7 个旧串全 CLEAN、控制探针 29 命中。
   **并且把闸门扩到了本轮全部 8 个被编辑过的文件**（`t4_probes/p20_landing_gate_all.py`）：
   逐个做「新串 >=1 / 旧串 == 0 / 控制探针 >=1 / `ast.parse` 通过」四道，
   结果 **ALL OK**——即另外 7 个文件的编辑**都真的落盘了**（它们另有独立证据：
   `git diff --numstat` 的 +/− 行数、`pytest --collect-only` 的条数变化、
   运行时 `len(__all__) == 24`、以及 592 passed）。
   **教训**：报告文件是唯一一个「没有测试会替我核」的产物，所以它是这一族事故的高发地
   （Ruling 116 的数据丢失、Ruling 135 的伪 diff 都发生在报告上）；
   **凡改报告，改完立刻量字节，不看 diff 回显。**

---

## 13. 收工自证

```
$ git status --short                     # commit 之前
 M backend/app/domain/prescription/__init__.py
 M backend/tests/architecture/test_domain_purity.py
 M backend/tests/architecture/test_layering.py
 M backend/tests/test_refdata_prescription.py
?? .superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/t4_probes/
?? backend/app/domain/prescription/match.py
?? backend/tests/domain/test_prescription_exercises.py
?? backend/tests/domain/test_prescription_match.py
```

（`git status --short` = 0 行这一条**只能在 commit 之后**取到，见 §13.1。）

| 项 | 结果 |
|---|---|
| `python -m pytest -q` | **592 passed**（M0 相位亲跑，65.59 s） |
| `--cov=app.domain --cov-branch --cov-report=term-missing` | **591 passed, 1 skipped**；`TOTAL 541 stmts / Miss 0 / 132 branch / BrPart 0 / 100%` |
| `Base.metadata.tables` | **16 张**（逐个列名亲跑，与 Task 3 结案时相同） |
| 全仓相对导入 | **18 条**，`{1: 18}` = `app/db/models` 13 + `app/domain/prescription` 5 |
| `SCANNED_DIRS` 扫描面 | **28** = pipeline 7 + db 11 + domain **10** |
| `app.domain.prescription.__all__` | **24 个**（打印过全清单） |
| `_PRESCRIPTION_PUBLIC_BASELINE` | `len == 24`；`assert len(...) == 24, "基线是 24 个名字，抄漏了就当场红"` |
| CSV 指纹 | 21 412 B / `D2C8E539E2FA0029`（归一化后）/ CRLF 0 —— **不变** ✓ |
| `exercises.yaml` | 22 739 B / `3DE598AF38631209` / CRLF 0 —— **不变** ✓ |
| `exercise_equivalence.yaml` | 8 245 B / `822CB86A5E998301` / CRLF 0 —— **不变** ✓ |
| `backend/pe.db` | **不存在** ✓ |
| `backend/data/seed/` | **0 文件** ✓ |
| `backend/data/` | **一个字节都没改**（`git status --short` 里没有它）✓ |
| `.gitattributes` / `app/seed/` | **没碰** ✓ |
| 临时目录 | 无残留（变异 harness 全部在原地改-还原，没用 `$env:TEMP`、没建 worktree）✓ |
| `match.py` 还原核验 | 6 个变异相位每次都 `assert sha256 == 40E08F5587C92F46…` 通过 ✓ |

**一次性脚本的处置**：本轮所有取证脚本都放在派单指定的
`.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/t4_probes/`（`p01`…`p17` +
`mutate_log.txt`），**没有**在 SDD 目录根下留任何 `_xxx.py`。
`git ls-files` 亲跑确认前几轮的 `fr2_probes` / `fr3_probes` / … / `t3_probes`
**都是入库的**，故 `t4_probes/` 一并入库符合既有惯例（硬规矩 #68 修订版第 1 条）。

### 13.1 commit 之后补录

见 §13.2（这一节的数字**只能**在 commit 之后取到，故留到 commit 之后回填；
若本文件在 commit 之后被追加，追加前先按硬规矩 #68 做字节备份）。

---

## 14. 关切与未尽事项

**① 请裁定 §9.2 / CE-7 那个偏离**：`cases` 矩阵我做成「保留 + 新增扫真仓」的超集，
不是派单字面的「换成」。若控制者仍要求「换成」，请同时裁定
`if level - 1 > len(package): return None` 那一行与 RED 判定格由谁守——
真仓今天提供不了这两类输入（实测 (a)(b)(c)）。

**② `test_impact_rank_values_are_pinned_verbatim` 与
`test_prescription_public_namespace_is_pinned_verbatim` 仍住在 domain 测试目录之外。**
`tests/test_refdata_prescription.py` 的模块 docstring 原来那句「这两条应当搬过去归位」
说的范围比 Ruling 134-1③ 授权的**更宽**；我按授权的字面范围只搬了 `lookup()`，
并把理由与这个范围差异写进了那个 docstring（可 grep 原文
「**Task 4 只搬走了 ``lookup()`` 的分支测试**」）。**请裁定这两条归 Task 5 还是 Task 12
的散文清扫。** 我的看法：`test_prescription_public_namespace_is_pinned_verbatim`
**不该**搬进 `test_prescription_exercises.py`——它守的是**整个包**的公开面
（Task 4 之后横跨 `exercises` / `templates` / `match` 三个所有者 + 借来的 `stratify`），
放进一个叫 `…_exercises` 的文件里名不副实；要归位应该是另建一个
`tests/domain/test_prescription_public_face.py` 一类，那是**新增授权面**。

**③ `NO_BUCKET` 在生产路径上是否真的不可达，需要 Task 9 落地时复核。**
按今天的口径（§3.6）它被 `NO_LAYER` 恒先拦下，存在的理由是「Task 9 从两张表、
可能两个时点拼 `MatchInput`」。**如果 Task 9 的装配方式保证两个字段永远来自同一次
`compute_derived` + `stratify`，那这一支就是死代码**——它不会让覆盖率变红
（32 格穷举用构造的输入覆盖它），但会是一个「永不执行的取值」（与账本 Ruling 134-7
对 `Intensity.rpe` 的处置同类）。**记进 Task 9 预检清单。**

**④ `match_template` 的 `NO_TEMPLATE` 文案用英文 token，教师端可能读不懂。**
§3.7 说明了为什么不新造中文桶名映射（要先改 spec、且会是第二个所有者）。
但 spec §11.2 的 B 类降级表里，`NO_TEMPLATE` 这一档**根本没有行**
（那张表只有「模板 `review.status != approved`」与安全替换的 `needs_review`、
新生无历史体测三行）——即「模板矩阵缺一格」这件事在 spec 里**没有规定的教师端措辞**。
**建议 Task 12 登记进 spec §14**（我没有自行占编号）。

**⑤ `MatchOutcome` 只有 3 个字段，Task 9 落库时可能不够。**
`prescription` 表要记「为什么没生成」，而 `status` + `reason` 是给人读的；
如果 Task 9 还要按 status 做统计（例如「今天有几个人落 `NO_LAYER`」），
它会需要 `MatchStatus` 的**值**稳定——`test_match_status_has_exactly_the_six_pinned_members`
已经把 6 个 `(name, value)` 二元组连同声明序一起钉住了，改一个值就会红。
**这一条是「已经守住了」的正面通报，不是待办。**

**⑥ 三个新文件的工作树行尾是 LF、而 `backend/**.py` 的惯例是 `w/crlf`**（§1.1）。
不影响任何守卫（`.py` 不被指纹钉、`.gitattributes` 不管 `.py`、进 index 的 blob 相同），
且仓内已有 3 个同类先例。**报出来只为让控制者知道下一次 checkout 会把它们变成 CRLF**，
届时若有人在报告里引用这三个文件的**裸字节** sha256，那个数会变假
（本报告同时给了裸字节与归一化后两个口径，归一化后的值不会变）。

**⑦ 变异 ④ 的实现方式需要控制者认可。**
派单说「把 `NO_BUCKET` 与 `UNREACHABLE` 的检查顺序对调」。我的实现里
`UNREACHABLE` 的判据是**读到字段之后**才成立的（在循环内），而 `NO_BUCKET` 在循环外，
故「对调」在我的代码结构里不能靠交换两个 `if` 完成。我采用的变异是
**在 `NO_BUCKET` 之前插入一个 `is_reachable` 口径的提前判定**
（`if inp.layer is Layer.GREEN and inp.body_comp_abnormal: return … UNREACHABLE …`），
这在语义上正是「`UNREACHABLE` 的判据先于 `NO_BUCKET` 的判据」，
且它复现了 P4-A3 描述的全部特征（总数仍 32、只有承重格变、期望表被真的钉住）。
另一种做法（把 `NO_BUCKET` 的检查挪进循环、放到 `not template.reachable` 之后）我也推演过：
它会让 `(green, None, abnormal)` 落到 **`NO_TEMPLATE`**（桶为 `None` 匹配不到任何模板），
分类变成 `{no_layer:8, no_bucket:5, no_template:1, unreachable:3, matched:15}`——
同样能让穷举测试红，但它验的是「`NO_BUCKET` 晚于 `NO_TEMPLATE`」而不是 P4-A3 点名的那一处。
**我选了前者**（它才是 P4-A3 的承重处）。

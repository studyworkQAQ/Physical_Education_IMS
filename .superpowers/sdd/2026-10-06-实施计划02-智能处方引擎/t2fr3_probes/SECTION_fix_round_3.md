
## fix round 3 — 收尾评审的 7 条 Important + 10 条 Minor（全部是「印在源码里的陈述与实测不符」）

派单：Task 2 fix round 3。开工基线 **HEAD `2df6825`**（代码基线 **`966eae0`**）、分支 `feature/plan-02-prescription-engine`、工作树干净。
本轮**零生产语义改动**：`backend/app/**` 只改 docstring 与注释；`backend/data/**` 只改注释行；`backend/tests/**` 只改 docstring 与注释，**外加派单授权的 3 处代码级字面量**（两个指纹常量 + 一条 assert 消息）；`Document/` 只改 spec §14 第 28 项最后一格。
本节所有数字都由本轮实跑产生。取证脚本刻意**放在仓库外**（`$env:TEMP\sdd_fr3\`，11 个 `v*.py`），理由见 fr3.11-①。

---

### fr3.0 环境与基线复现（硬规矩 #73：先冒烟、把版本记进报告）

冒烟（派单 §0 要求的开工第一件事）：

```
$ python -c "import sys,sqlalchemy,pandas,numpy,yaml;print(sys.version.split()[0],sqlalchemy.__version__,pandas.__version__,numpy.__version__,yaml.__version__)"
3.11.1 2.1.3 3.0.6 2.4.6 6.0.3
```

即 **Python 3.11.1 / SQLAlchemy 2.1.3 / pandas 3.0.6 / numpy 2.4.6 / PyYAML 6.0.3**，与派单 §0 逐字相符；SQLAlchemy 确实是 Ruling 122 之后的 **2.1.3**（不是被 Smart App Control 拦掉的 2.1.1），无 venv。**本节以下所有 passed 数与覆盖率都绑定这一组版本。**

开工基线（改动之前，串行实跑）：

```
$ git rev-parse --short HEAD ; git branch --show-current ; git status --short
2df6825
feature/plan-02-prescription-engine
（空 —— 工作树干净）

$ cd backend ; python -m pytest -q
531 passed in 64.18s
```

→ 与派单 §5 的「HEAD = 2df6825 / git status --short = '' / 531 passed」相符（控制者那次是 59.68 s，本机 64.18 s；耗时不是判据，passed 数才是）。

---

### fr3.1 派单 §5「控制者自查清单」的逐条复验（Ruling 84/100/109 的下游正面确认）

口径全部是 `read_bytes()`：字节数 = `len(b)`；行数 = `b.count(b"\n")`（这些文件都以换行结尾）；CRLF 数 = `b.count(b"\r\n")`；指纹 = `sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16].upper()`。
「BEFORE」列由 `git show HEAD:<path>` 的 blob 按该文件自己的行尾约定还原得到（`backend/**` 的 blob 是 LF、工作树是 CRLF，故 `.py` 与 `Document/*.md` 做了 LF→CRLF；`backend/data/*.yaml` 与 `*.csv` 由 `.gitattributes:14-16` 钉成 `eol=lf`，blob 与工作树逐字相同，不还原）。

#### (1) 待改文件 + 禁区文件（11 个）

| 文件 | BEFORE 字节 / 行 / CRLF / 指纹 | 与派单 §5 是否相符 | AFTER 字节 / 行 / CRLF / 指纹 |
|---|---|---|---|
| `app/domain/prescription/exercises.py` | 12384 / 200 / 200 / `E06CBE6A96D28051` | ✅ | 16915 / 254 / 254 / `3E13D9E322C9D9A4` |
| `app/refdata_prescription.py` | 22400 / 406 / 406 / `875F0DC917984CC5` | ✅ | 23225 / 413 / 413 / `EE0279B00D4AFB1B` |
| `app/db/models/prescription.py` | 8976 / 131 / 131 / `660CC93E44EBD1BA` | ✅ | 10088 / 143 / 143 / `A2F2839FF80B4B53` |
| `data/exercises.yaml` | 13358 / 267 / **0** / `A6A000F58815FCBB` | ✅ | 17609 / 307 / **0** / `63033BBD7F68CC1F` |
| `data/exercise_equivalence.yaml` | 7841 / 126 / **0** / `0FFB881574AC04F3` | ✅ | 8245 / 130 / **0** / `822CB86A5E998301` |
| `tests/test_refdata_prescription.py` | 54774 / 921 / 921 / `B969FFF932185E53` | ✅ | 57852 / 952 / 952 / `63444B1FDAA9445C` |
| `tests/domain/test_prescription_templates.py` | 10697 / 147 / 147 / `97AE1A3DE28615C7` | ✅ | 11248 / 153 / 153 / `13E422CC719F01F5` |
| `tests/db/test_models.py` | 43904 / 750 / 750 / `0161112C2D9CA6A3` | ✅ | 44669 / 757 / 757 / `974C1FFB917684ED` |
| `tests/seed/test_generate.py` | 65501 / 1179 / 1179 / `AEAE90C8CFDFB4C2` | ✅ | 66351 / 1188 / 1188 / `966DB7C3C96BFC99` |
| `Document/…设计spec.md` | 85847 / 974 / 974 / `D935A6FD94C8C2C2` | ✅ | 87126 / **974** / **974** / `9E8689A895AB27BB` |
| `data/national_standard_2014.csv`（禁区） | 21412 / 503 / 0 / `D2C8E539E2FA0029` | ✅ | **21412 / 503 / 0 / `D2C8E539E2FA0029`（一个字节未动）** |

（路径都相对 `backend/`，最后一行除外。spec 那一行 AFTER 的**行数与 CRLF 数都没变**——I7 是「一行换一行」，见 fr3.6-(4)。）

#### (2) 锚点命中数（9 个，逐字复核）

| 派单 §5 的陈述 | 我的实测（改前） | 判定 |
|---|---|---|
| `exercises.py` 的 `'ImpactLevel.HIGH'` **4 次** | 4 | ✅ |
| `exercises.py` 的 `'任何一份'` **2 次** | 2 | ✅ |
| `exercises.py` 的 `'Ruling 19'` **1 次** | 1 | ✅ |
| `test_refdata_prescription.py` 的 `'Ruling 19'` **1 次** | 1 | ✅ |
| `exercise_equivalence.yaml` 的 `'5 个'` **1 次** | 1 | ✅ |
| `test_models.py` 的 `':163'` **1 次** | 1 | ✅ |
| `prescription.py` 的 `':163'` **1 次** | 1 | ✅ |
| `exercises.yaml` 的 `'#29'` **1 次** | 1 | ✅ |
| spec 的 `'#29'` **1 次** | 1 | ✅ |

#### (3) 其余逐支

| 派单 §5 的陈述 | 我的实测 | 判定 |
|---|---|---|
| `== 15` 在 `test_models.py` 的 `:169` / `:236` / `:494` | `git grep -n "== 15" -- backend/tests/db/test_models.py` → **恰好这 3 处** | ✅ |
| 函数名 `test_all_fifteen_tables_created` 在 `:24`，另 `:492` 有一处注释引用 | `:24` 是 `def` 行；`:492` 是注释引用；全仓 `git grep` 另有 `app/db/models/__init__.py:80` 与 `app/db/models/prescription.py:17` 两处按名引用（共 **4** 处） | ✅（并补出派单没提的另 2 处） |
| 计划 `:688` 逐字确认「动作库的视频源」是 §14 的 **#30** | `2df6825` 上计划 `:688` 逐字含「**#30** 动作库的视频源（占位 `.invalid` URL；⚠️ Task 2 已把它写进 `exercises.yaml` 的头注释…）」 | ✅ |
| spec 第 28 项在 `:933` | `:933` 行首是 `| **28** | **`exercise_equivalence.yaml` 的 `volume_reduction` 两个系数…` | ✅ |
| `SCANNED_DIRS` = pipeline 7 + db 11 + domain **9** = **27** | 实跑两份守卫自己的 `TL._py_files()`：**7 / 11 / 9 = 27**；`TP._domain_files()` = **9** | ✅ |
| 禁区：CSV `21412 B` / `D2C8E539E2FA0029` / CRLF 0；`pe.db` 不存在；`data/seed` 0 文件 | 三项**全部逐字相符**（改后复验仍相符） | ✅ |
| 评审产物：review 91077 B / 776 行；review-package 210927 B / 3229 行；progress 233921 B / 1544 行；report 127827 B / 969 行 | **四份全部逐字相符** | ✅ |
| Python 3.11.1 / SQLAlchemy 2.1.3 / pandas 3.0.6 / numpy 2.4.6 / PyYAML 6.0.3 | 逐字相符（见 fr3.0） | ✅ |
| `531 passed` + domain `441 / Miss 0 / 120 / BrPart 0 / 100%` + `530 passed, 1 skipped` | 改前改后各跑一遍，**四个数字全部逐字复现**（见 fr3.8） | ✅ |

#### (4) ⚠️ 派单 §2.3 里两个指纹常量的**行号是错的**（值是对的）→ 记 **CE-fr3-1**

派单 §2.3 写：

```
:53  EXERCISES_FINGERPRINT   = "A6A000F58815FCBB"
:56  EQUIVALENCE_FINGERPRINT = "0FFB881574AC04F3"
```

实测（改前 `backend/tests/test_refdata_prescription.py`）：

```
  53| from app.domain.prescription.exercises import (
  54|     EquivalenceMapping,
  55|     EquivalenceTable,
  56|     IMPACT_RANK,
  57|     ImpactLevel,
  58| )
  …
  69| EXERCISES_FINGERPRINT = "A6A000F58815FCBB"
  72| EQUIVALENCE_FINGERPRINT = "0FFB881574AC04F3"
```

即两个常量在 **`:69` / `:72`**，不是 `:53` / `:56`；`:53`–`:58` 是 `from app.domain.prescription.exercises import (…)` 那个 import 块（**这大概就是误锚的来路**：`:53` 确实是「从 `exercises` 导入」这件事的位置）。**两个指纹值本身逐字正确**，故不影响本轮任何判据；但它是硬规矩 #61（派单里的每个行号发出前 shell 亲验）的又一次落空，且**收尾评审者报的 `:69` / `:72` 是对的**（review `:448` 与 `:338`），即这一格上评审者比派单准。

**派单 §5 其余每一条我都复验过，全部相符**；除本条外没有发现第二处不符。

---

### fr3.2 七条 Important 的逐条落地

每条给：① 我对评审者指控的**独立复核**（不采信、自己跑）；② 判定；③ 落地位置与改后原文要点。

#### I-1 `str(ImpactLevel.HIGH)` 的字符数印错（16 不是 19）+「SQLite 会按 `str()` 存」这个机制不成立 — **成立**，2 份副本都改

**我的独立复核**（纯 Python + 标准库 `sqlite3` + `sqlalchemy.dialects.sqlite`，SQLAlchemy 2.1.3）：

```
str(ImpactLevel.HIGH)      = 'ImpactLevel.HIGH'   len = 16
len('ImpactLevel.HIGH')    = 16
repr(ImpactLevel.HIGH)     = <ImpactLevel.HIGH: 'high'>   len = 26
format(ImpactLevel.HIGH)   = 'ImpactLevel.HIGH'   len = 16
ImpactLevel.HIGH.value     = 'high'   len = 4
isinstance(x, str)         = True
raw sqlite3 bind ImpactLevel.HIGH -> value='high' typeof=text length()=4
raw sqlite3 bind str(...)         -> value='ImpactLevel.HIGH' typeof=text length()=16
String(8).bind_processor(sqlite dialect) = None
```

三层都复现了评审者的结论，并**补上了评审者标为「不可复核」的那一层**（review `:260`）：`String(8).bind_processor(sqlite 方言)` 在本机 SQLAlchemy 2.1.3 上**实测返回 `None`**——即 `String` 类型在 SQLite 方言下**不做** `str()` 强转、值原样下传，与裸 `sqlite3` 的结果一致。所以「机制错」这一层从「按方言实现推定」升级成「本机实测」。

⚠️ **顺带核出评审者一处数字错**：review `:257` 写「`repr()` 是 **27**」，实测 `len(repr(ImpactLevel.HIGH))` = **26**（`<` + `ImpactLevel`(11) + `.` + `HIGH`(4) + `:` + 空格 + `'high'`(6) + `>` = 26）。**不影响该条 finding 成立**（16 / 26 / 16 三种口径都给不出 19），但按 Ruling 45/51/65 的纪律报出来 → 记 **RE-fr3-1**。

**落地**（2 份，硬规矩 #51）：
* `backend/app/domain/prescription/exercises.py` 的 `ImpactLevel` docstring —— 删掉「SQLite 会把枚举对象按 `str()` 存成 `"ImpactLevel.HIGH"`（19 字符，还撑破 `String(8)`…）」整句，换成 4 支实测清单（`str` 子类的字符数据就是值本身 → 裸 `sqlite3` 落库 `'high'` / `typeof=text` / `length()=4`；`bind_processor` 实测 `None`；`str(x)` 才给 16 字符，`repr()` 26、`format()` 16，**没有任何一种口径给得出 19**；生产路径写的是 `spec.impact_level.value`），并明写「故硬规矩 #18 那个失效形态在**这一列**上今天**不可达**；列宽仍由 `test_exercise_string_column_widths_fit_the_yaml_values` 现读现比看着」。
* `backend/tests/domain/test_prescription_templates.py` 的 `test_impact_level_is_a_str_enum_so_it_round_trips_through_the_db` docstring —— 同口径改正，并显式写明「口径与 `exercises.py` 的 `ImpactLevel` docstring 完全一致」。

我**没有**采用评审者建议的「最省修法」（只留「继承 `str` 让 `==` 成立」那半句、把机制整段删掉）。理由：这一列的列宽守卫（硬规矩 #18）是本项目踩过一次的真实缺陷类型，把「为什么这一列今天不可达」写清楚比删掉更有价值；而我写的每一句都有上面那次实跑支撑（硬规矩 #19/#29/#52）。

#### I-2 「改坏 `IMPACT_RANK` 也会让 `test_equivalence_never_maps_to_a_higher_impact_level` 红」不成立 — **成立**，3 份副本都改 + 1 处自相矛盾已统一

**我的独立复核**（AST，改前）：

```
test_equivalence_never_maps_to_a_higher_impact_level                     def@:302-334 IMPACT_RANK=False IMPACT_DESCENDING=True
test_every_high_impact_exercise_has_a_low_substitute                     def@:352-391 IMPACT_RANK=False IMPACT_DESCENDING=False
test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable  def@:434-465 IMPACT_RANK=False IMPACT_DESCENDING=False
test_impact_rank_values_are_pinned_verbatim                              def@:468-523 IMPACT_RANK=True  IMPACT_DESCENDING=True
```

**四行与 review `:284-287` 逐字相符**；`:434` 确实是 `test_lookup_honours_…` 的 `def` 行（review `:294` 的旁证成立）；`:317` 确实是 `rank = {value: index for index, value in enumerate(IMPACT_DESCENDING)}`。
并且我**没有停在 AST**：按派单 §3 的要求把两次变异真跑了一遍（结果见 fr3.5），**实测与静态结论一致**——改坏生产侧 `IMPACT_RANK` 时「不升冲击」那一条**恒绿**。

**落地**（3 份 + 1 份补全，硬规矩 #51/#56）：
1. `exercises.py` 的 `ImpactLevel` docstring —— 改成「改坏哪一份、红的是哪几条，**两侧不同**」的两支清单，每支都写明实测红的测试名与 `2 failed, 529 passed`（硬规矩 #52：举例必须是真跑过的输出）。
2. `exercises.py` 的 `IMPACT_RANK` 注释（改前的 `:90-96`，即评审者说的「正确版」）—— 那句「A 与 B **之一**会红」按我的两次实测**为真但不完整**（fr2 新增的 `test_impact_rank_values_are_pinned_verbatim` 在两次变异里都红，而它不在那两项里）。故按硬规矩 #66 一并更新成两支清单，与 (1) 同口径。⚠️ **这一处超出了派单 §2.1 I2 行点名的位置**（派单只要求「把两处统一成正确的那个说法」）；我判断「统一」的终点必须是**同一个且完整**的说法，否则统一完仍留下一处漏项，故带上，并在此显式报备。
3. `test_refdata_prescription.py` 的 `IMPACT_DESCENDING` 注释（改前 `:85-86`）。
4. `test_refdata_prescription.py` 的 `test_equivalence_never_maps_to_a_higher_impact_level` docstring（改前 `:308-309`）—— 明写「**本条只看得到测试侧那一份**」+ AST 0 命中 + 两次变异的红/绿归属 + 「本条守的是**数据**」。

#### I-3 `exercise_equivalence.yaml:33` 的「8 个 low 动作里的 **5** 个被用到」是 **4** — **成立**，已改

**我的独立复核**（`yaml.safe_load` 实算）：

```
low (8): band_resistance, bodyweight_resistance, brisk_walking, dynamic_stretching,
         functional_training, pnf_stretching, sit_and_reach_drill, stationary_cycling
distinct 'to' (4): bodyweight_resistance, brisk_walking, functional_training, stationary_cycling
'to' reuse counts: {stationary_cycling: 4, brisk_walking: 2, bodyweight_resistance: 2, functional_training: 2}
low refs NOT used (4): band_resistance, dynamic_stretching, pnf_stretching, sit_and_reach_drill
```

→ **4**，且与原句自己列出的 4 个名字自相矛盾（评审者的「自相矛盾」判读成立）；同句的「`stationary_cycling` 被 **4** 条复用」**为真** ✅。

**落地**：`5 个` → `**4** 个`，并按评审者建议把未被用到的 4 个点名（`band_resistance` / `dynamic_stretching` / `pnf_stretching` / `sit_and_reach_drill`），补一句「将来加映射时优先从它们里挑」；同时补上「其余三个各被 2 条复用」（实测）。⚠️ 这一改**动了被指纹钉住的文件** → 见 fr3.4。

#### I-4 `test_models.py` 三处 `==` 的行号在改它们的那一笔里就过期了 — **成立**，2 份副本都按 fr2 对 CE-7 的修法处理

**我的独立复核**：

```
$ git grep -n "== 15" -- backend/tests/db/test_models.py
backend/tests/db/test_models.py:169:    assert len(tables) == 15, "守卫的覆盖面必须先被确认是这 15 张表"
backend/tests/db/test_models.py:236:    assert len(tables) == 15, "守卫的覆盖面必须先被确认是这 15 张表"
backend/tests/db/test_models.py:494:    assert len(Base.metadata.tables) == 15
```

并且**独立确认了「那三个行号是 `fb5bddb` 的位置」**（不只是「今天不对」）：Plan02 账本 P2-A6（`progress.md:1007`）逐字写着「亲验 `tests/db/test_models.py`：`assert len(tables) == 14` 在 **`:163`、`:228`**，`assert len(Base.metadata.tables) == 14` 在 **`:472`**；函数名 `test_all_fourteen_tables_created` 在 **`:24`**」——即 P2-A6 亲验当时是**对的**，是 Task 2 自己把 `== 14` 改成 `== 15` 时推移了行号而两处散文没跟上。评审者的归因成立。

**落地**（按派单 §2.1 I4 的要求：「先给可 grep 的原文、再给绑定 commit 的行号」，**不是**把数字换成新的）：
* `backend/app/db/models/prescription.py` 模块 docstring —— 删掉那 4 个裸行号，改成两条 `git grep` 命令 + 各自的逐字原文 + 「在**代码基线** `966eae0` 上它们分别是 `:169` / `:236` / `:494`（三处 `==`）与 `:24`（`def`）」。
* `backend/tests/db/test_models.py` 的 `test_all_fifteen_tables_created` 注释 —— 同一口径，并明写「改完表数请重跑这条 grep 确认命中数仍是 3」。
* 两处都明写「此前印的是**三个裸行号**、它们是 `fb5bddb` 上 `== 14` 的位置」+「与 fr2 的 CE-7 是同一个失效形态」+「那三个过期行号本轮**不再复述**」（理由见 fr3.7-(3)）。

#### I-5 「BMI 不归任何短板桶」引的裁定号错了 — **成立**，2 份源码都改（账本按派单留给控制者）

**我的独立复核**（Plan01 账本 805 520 B）：

```
:170| **Ruling 19 — `raw_from_score` 对非单调序列抛 `ValueError`，不得返回哨兵。**
:171| 评审实测 `raw_from_score(T, BMI, 80, MALE, G) = 0.0`（哨兵泄漏）…
:133| 裁定接受，依据：① BMI 按 spec §4.2 **不参与短板判定与桶化**，只进国标总分；…
       （:133 属于 :115 的 **Ruling 17** 之下的「关切 1（BMI 非单调区间映射）」，:131 是该关切的标题行）
```

→ 评审者的定位**逐字相符**：Ruling 19 讲的是反查函数的非单调护栏，「BMI 不进短板桶」在 Ruling 17 关切 1 的依据 ①。本仓其余 3 处 `Ruling 19` 用法（`app/domain/percentile.py:131`、`data/README_national_standard.md:129`、`tests/domain/test_indicators.py:268`）都指 `raw_from_score`，**用法正确、本轮不动**。

**我比评审者多追了一层出处**：Ruling 17 关切 1 的依据 ① 自己写的是「BMI 按 **spec §4.2** 不参与短板判定与桶化」，而 spec §4.2 里这个口径有两处**可 grep 的逐字原文**：

```
:210| | 1 | BMI（身高/体重派生） | kg/m² | 越接近正常越好 | 15 | **否** | 不入桶 |
:220| > - **短板判定项 = 6 个**（**排除 BMI**），`W` 的分母是 6。排除理由：BMI 属身体形态，已由体成分维度 `C` 覆盖；若同时计入 `W` 与 `C`，一个体脂超标学生会被**重复计数**…
```

**落地**（2 份）：
* `exercises.py` 的 `TARGET_DOMAIN` 注释 —— 出处改成 **spec §4.2**（给出上面那两格的逐字原文与排除理由）+ Plan01 账本 **Ruling 17 关切 1** 的裁定原文；并明写此前引的是「Plan01 账本里**另一条**裁定（讲 `raw_from_score` 对非单调序列抛 `ValueError`），即**引用号错**」+「错误源头是 Plan02 账本 P2-A4，账本由控制者勘误」。
* `test_refdata_prescription.py` 的 assert 消息 —— `"BMI 不归桶（Plan01 Ruling 19），故 None 必在其中"` → `"BMI 不归桶（spec §4.2：短板判定项 = 6 个，排除 BMI），故 None 必在其中"`，并在它上面加 5 行注释交代更正与真正的出处。⚠️ 这是本轮 `backend/tests/**` 里**唯一一处非 docstring/注释的改动**（它是 assert 的**消息**字面量，不改判定），派单 §2.1 I5 行明确点名了这个位置。

**账本 P2-A4（`progress.md:999`）与 CE-7 / Ruling 121 的勘误按派单留给控制者，我没动账本。**

#### I-6 `exercises.yaml:21-22` 的「预留为 **#29**」已被 `d40f36c` 作废，今天是 **#30** — **成立**，已改（派单已授权改 `backend/data/exercises.yaml`）

**我的独立复核**（用 `git show <rev>:<plan>`，**没有 checkout**）：

```
fb5bddb 计划 :681| - [ ] **Step 3: spec 勘误与 §14 补项（本计划累计 7 项，#28–#34）**
fb5bddb 计划 :685| - §14 补：**#28** 18 套模板的审校状态…；**#29** 动作库的视频源（占位 `.invalid` URL）；…
2df6825  计划 :682| - [ ] **Step 3: spec 勘误与 §14 补项（本 Task 追加 **6 项，#29–#34**）**
2df6825  计划 :688| - §14 补（**#28 已由 Task 2 追加…**）：**#29** 18 套模板的审校状态…**#30** 动作库的视频源（占位 `.invalid` URL；⚠️ Task 2 已把它写进 `exercises.yaml` 的头注释…）
$ git show --stat --oneline d40f36c → 1 file changed, 7 insertions(+), 4 deletions(-)   # 只改计划文档
$ git log --oneline fb5bddb..2df6825 -- Document/…设计spec.md → 3ea27cc（只此一笔）
```

→ 评审者的三层判读全部成立：那句话在 `3ea27cc` 写下那一刻为真、被紧接着的 `d40f36c` 作废、而 `c21767d`/`966eae0` 都没动 `backend/data/`（改动面纪律），于是它留在了 HEAD 上。**正确答案确实一直在账本里**（Ruling 93 写「重排后是 #30」）。

**落地**：`预留为 #29` → `排在 **#30**`，并把整条因果链写进注释（`3ea27cc` 时的旧编号 → `d40f36c` 把 #28 让给本文件的 volume_reduction 项 → Task 12 清单去重后整体前移一位 → 原 #29 变成 #30），另引计划正文那一行的逐字原文。⚠️ 这一改**动了被指纹钉住的文件** → 见 fr3.4。

#### I-7 spec §14 第 28 项「影响面」格里的编号交代已被执行掉、且处方与实际结果不符 — **成立**，已改（派单已授权改这一格）

**我的独立复核**：三层问题逐层验过（计划 `:682`/`:684`/`:688`/`:707` 的逐字原文见 fr3.2 I-6 与 fr3.6-(4)；`git diff --numstat fb5bddb..2df6825 -- Document/…spec.md` = **`1  0`**，即 spec 在评审区间里只被 `3ea27cc` 加过那一行、`d40f36c` 没碰它 ✅）。
「处方与结果不符」这一层我算过：spec 原文开的处方是「7 项**整体后移为 #29–#35**，并**删掉**重复的一条」→ 7 个号 − 1 项 = 6 项但**号段宽 7**（留一个空洞、最大号 #35）；实际执行的是**去重后连续编号 #29–#34**（6 项、无空洞）。两个结果确实不一样，且照 spec 那句办事会**凭空造出一个 #35**。

**落地**：只替换 `:933` 那一行**最后一格**里从「⚠️ **编号冲突待 Task 12 处理**」起到行尾（`|` 之前）的 273 个字符，换成 942 个字符的**既成事实陈述**：
* 「已由计划 02 的 `d40f36c` 处理完毕」+ 完整的 7→6 去重前移映射（原 #28→#29、#29→#30、#30→#31、#31→#32、~~原 #32~~ 删除、#33→#33、#34→#34）；
* `27 + 1（Task 2）+ 6（Task 12）= **34**`；
* 显式否定旧处方（「**不是**此前这里写的『整体后移为 #29–#35』——照那句执行会…凭空多出一个 **#35** 并留下一个空洞」），并写明「Task 12 若照它办事会把已经正确的计划正文再改一遍」；
* 逐字依据 + 计划行号**绑 `2df6825`**（`:682` / `:684` / `:688` / `:707`），并交代此前引的 `:681`/`:685` 是 `fb5bddb` 的位置；
* **补一条评审者没提的事实**：计划 `:689` 自己留了一个**条件性** #35（若 Task 7 落地时发现本项正文没覆盖「提高抗阻比重」的处置，才由 Task 7 追加为 #35）。不写这一句，改后的格子会被读成「#35 永不存在」，那是**新的不准确**。

**改动面自证**：`git diff -U0` 只有 **1 个 hunk `@@ -933 +933 @@`、+1/−1 行**；新旧两行的**公共前缀是 926 个字符**（分歧点正好落在最后一格的「⚠️ **编号冲突」之后）；两行的 `|` 计数都是 **6**（表格结构未变）；两行都以 `| **28** |` 开头；文件**行数与 CRLF 数都仍是 974**（见 fr3.1 表）。spec 其余部分一个字节未动。

---

### fr3.3 十条 Minor 的逐条落地（全部修）

| # | 位置（改前行号） | 我的独立复核 | 判定 | 落地 |
|---|---|---|---|---|
| **M-1** | `test_refdata_prescription.py:599` | `git grep -n "test_impact_level_vocabulary_agrees_with_the_domain_enum"` → `backend/` 下**只有这 1 处命中**，全仓没有这个函数；真名 `test_exercise_impact_level_vocabulary_agrees_with_the_domain_enum` 的 `def` 在 `:566`；`app/db/models/prescription.py:83` 引的是**正确**全名 | **成立** | 补 `exercise_` 前缀，并写明「改前那个短名在 `backend/` 下只有本行 1 处命中」+「`prescription.py` 引的一直是正确全名」 |
| **M-2** | `refdata_prescription.py:356` | 本模块 `def` 逐个数：`_exercise_spec`(:96，私有) / `load_exercises`(:178) / `exercises`(:220) / `_equivalence_mapping`(:232，私有) / `load_equivalence`(:282) / `equivalence`(:353) / `sync_exercises`(:366) → **公有 5 个**，评审者给的 5 个行号**逐个相符** | **成立** | 主语补成「**加载侧的四个函数**（`load_exercises` / `exercises` / `load_equivalence` / 本函数）」+ 明写「本模块公有函数是 **5** 个，第 5 个是 `sync_exercises`（投影入口，不是加载器）」（硬规矩 #56） |
| **M-3** | `refdata_prescription.py:374-375` | `app/db/repo.py:39` 逐字是「本函数**既不 commit 也不 flush**：事务边界由调用方掌握，「整批失败回滚」才成立。」 | **成立**（这是**因果机制陈述错误**，硬规矩 #29，不是排版） | 收紧成「与 `upsert` **只在「不 commit」这半句同口径**……`upsert` docstring 逐字是「本函数**既不 commit 也不 flush**」，即它连 flush 也不做；本函数按 `ref` 逐条调它，故在循环外统一 flush 一次」 |
| **M-4** | `exercises.yaml:33-37` | spec `:487` 那段散文逐字点名 12 个东西：间歇跑 / 复合循环 / 能量消耗模块 / 持续跑 / 台阶训练 / 自重 / 弹力带抗阻 / HIIT / 兴趣球类 / 定向越野 / 功能性训练 / **可选挑战任务**；`抗阻优先模块`（`resistance_priority`）在 `:484` 的 `addons` 代码块里、**散文没有它**；而本文件把「可选挑战任务」算作补项 7（`:256`） | **成立**（数字 12/16/23 都对，**归属不对**） | 改成「spec §7.2 点名的 12 项」并加一段精确归属：**散文的 12 项 − 可选挑战任务 + 抗阻优先模块（`addons` 代码块）= 本文件的 12 项**；并说明「能量消耗模块」两处都点了、是同一个东西不重复计数。⚠️ **我没照抄评审者建议的措辞**（「`:487` 与两个 addon 模块名（`:482`/`:484`）合计点名的 12 项」）——`:487` 已经点了「能量消耗模块」，照那句写会把同一个模块数两次，等于用一个新的不准确换掉旧的不准确 → 记 **RE-fr3-2**（finding 成立、建议措辞不成立） |
| **M-5** | `test_generate.py:506` | 同一文件 `:567` 逐字是 `for table in DATA_TABLES + REFERENCE_TABLES:`；`:541-542` 明写 Task 2 把遍历对象从 `DATA_TABLES` 扩成 `DATA_TABLES + REFERENCE_TABLES`；本 docstring 自己的 `:510` 也说「认领进 `DATA_TABLES` / `REFERENCE_TABLES` 的表…」 | **成立**（结论仍真、**理由在 HEAD 上不准确**） | 改成「因为**两条守卫都只遍历『已被分区认领』的表**（`DATA_TABLES + REFERENCE_TABLES` 与 `ORGANISATION_TABLES` 两圈）」+ 标时点（那是 Task 2 **之前**的口径）+ 明写「**结论不变**」。⚠️ **顺带修了同一句里的第二处过期计数**：上一句「新表会静默落在**两个**分区之外」也是 Task 2 之前的口径（今天三个分区），改成「落在**任何**分区之外」（硬规矩 #66）；这一处评审者没提，我在报告里显式报备 |
| **M-6** | `exercises.yaml:91` 与 `:155` | 两处逐字确认：「快走把冲击峰值从跑的 **2–3 倍体重**降到约 **1.2 倍**」/「反复落地 = 反复 **2–3 倍体重**冲击」。spec 全文搜不到这两个数；本轮也拿不出可引用的指导文件 / 运动处方规范条文 | **成立** | 按硬规矩 #19 的第二个分支处理（给不出出处 → 明写不被守卫）：在首现处（`brisk_walking` 那节）加 9 行——**工程估计、无出处**、单位口径「地面反作用力峰值 ÷ 体重（无量纲倍数）」、**不被任何测试守卫**、**不得被 Task 7 当成 spec 条文或医学阈值引用**，并对比 `volume_reduction` 两个系数的处置（那两个**已**登记进 spec §14 第 28 项）；第二处（`plyometric_jump`）加一句短标注 + 指回首现处 |
| **M-7** | `exercises.py:55` | fr2 之后字面写下这个序的地方确实有**三处**：`IMPACT_RANK`（生产）、`IMPACT_DESCENDING`（测试侧元组，`:87`）、`test_impact_rank_values_are_pinned_verbatim` 的字面字典（`:512-516`，逐字确认） | **成立** | 「今天有两份」→「今天是**两个消费方各一份**」，并单列第三处：「此外 fix round 2 又在 `test_impact_rank_values_are_pinned_verbatim` 里字面写死了第三处**期望值**（`{HIGH: 0, MEDIUM: 1, LOW: 2}`）——它是『钉住生产侧那一份』的**判据**，不是又一个**声明者**」（把「声明者」与「期望值」分开数，正是评审者要的口径） |
| **M-8** | `exercises.yaml:217-241` | 节标题 `:218` 是「**绿层**兴趣 / 综合，与两个 addon 模块」；本节 5 个条目：`interest_ball_games`(:221) / `functional_training`(:228) / `hiit`(:236，其注释 `:235` 写「spec §7.2 :487『体脂偏高附加 5min HIIT』（**黄层**）」）/ `energy_expenditure_plus_10pct`(:249，其注释 `:243-244` 写「`when: body_fat_over`，**红层** +10% 能量消耗」）/ `challenge_task`(:262，其注释 `:256` 写「spec §7.2 :487 的**绿层**写…可选挑战任务」）。spec `:487` 亲验：HIIT 确属黄层 | **成立** | 节标题去掉「绿层」→「兴趣 / 综合，与两个 addon 模块」，并加 7 行逐条层归属（绿/绿/**黄**/**红**/绿）+ 一句提醒「这里的『层』是**红/黄/绿分层**，与条目的 `impact_level`（**冲击**）是两个不同维度」 |
| **M-9** | `exercises.yaml:259-261` | 实算 `challenge_task` 既不是任何映射的 `from`、也不是任何映射的 `to`（`'challenge_task' in any mapping endpoint? False`）→「只有指纹会红」**为真** ✅；而 `test_refdata_prescription.py:449` 逐字是 `assert table.lookup("challenge_task", ImpactLevel.LOW) is None`，确实把这个 ref **硬编码**进了断言；`lookup` 只查等价表（`exercises.py` 的 `lookup` 实现里只有 `self.mappings`）→ 删掉该 ref 那条**仍然绿** | **成立**（「只有指纹会红」真、「没有任何一条**断言**依赖它」字面不成立） | 拆成两句：「没有任何一条**映射**依赖它（实测既不是 `from` 也不是 `to`）」+「也没有任何一条断言会**因为它消失**而变红」，并点名那条硬编码断言与「仍然绿、只是探针语义变弱（它不再证明『动作库里有、等价表里没有的 ref 返回 None』，只证明『等价表里没有的 ref 返回 None』）」 |
| **M-10** | `exercises.py:191-192` | 逐字确认折行点落在「来 / 表达」之间 | **成立**（纯排版） | 重排成一行：「故专家可以通过调整书写顺序来表达偏好，不必引入一个额外的优先级字段。」 |

---

### fr3.4 ⚠️ 指纹联动（派单 §2.3）

两个 YAML 都被本轮改动（I3 改 `exercise_equivalence.yaml`；I6 + M-4 + M-6 + M-8 + M-9 改 `exercises.yaml`），故两个指纹常量都同步更新。

**口径**（与 `tests/test_refdata.py`、`test_refdata_prescription.py` 的 `_fingerprint()` 一致）：**先归一化再哈希** —— `hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16].upper()`。

| 文件 | 改前 字节 / CRLF / 指纹 | 改后 字节 / CRLF / 指纹 |
|---|---|---|
| `backend/data/exercises.yaml` | 13358 B / **CRLF 0** / `A6A000F58815FCBB` | **17609 B / CRLF 0 / `63033BBD7F68CC1F`** |
| `backend/data/exercise_equivalence.yaml` | 7841 B / **CRLF 0** / `0FFB881574AC04F3` | **8245 B / CRLF 0 / `822CB86A5E998301`** |

代码里的两个常量（`backend/tests/test_refdata_prescription.py`，改后在 `:69` / `:72`）：

```
EXERCISES_FINGERPRINT   = "63033BBD7F68CC1F"
EQUIVALENCE_FINGERPRINT = "822CB86A5E998301"
```

**三道核对**（都由脚本从磁盘现算，不是我手抄）：
1. 两个 YAML 改后 **CRLF = 0**（`.gitattributes:14` 的 `backend/data/*.yaml text eol=lf` 未被破坏）；行数 267→307 与 126→130。
2. 常量值 == 从磁盘现算的指纹（脚本直接读 YAML 字节、算完再用正则替换常量，**两处不可能各说各话**）。
3. 三个**旧值**（`A6A000F58815FCBB` / `0FFB881574AC04F3`，以及我在中途一轮算出、随后又被 fix-up 覆盖的 `AA2BE3D26D1B3B1E`）在改后的测试文件里**全部 0 命中**——即没有留下一个过期常量。

⚠️ **`national_standard_2014.csv` 一个字节未动**：改前改后都是 `21412 B / CRLF 0 / D2C8E539E2FA0029`（fr3.1 表最后一行 + fr3.8 的收工自证各验一次）。

⚠️ **本轮 YAML 被改了两趟**（第一趟落 6 条 finding，第二趟是 fr3.7-(3) 那次「不复述被撤销原句」的收紧），故 `exercises.yaml` 有过一个中间指纹 `AA2BE3D26D1B3B1E`（17530 B）。**最终值以 `63033BBD7F68CC1F`（17609 B）为准**，中间值只在本节留档，免得控制者在两趟日志之间对不上号。

---

### fr3.5 变异验收（硬规矩 #50 / #52 / #53 / #62 / #65）—— I2 那句被撤销的陈述，我把**正确版**实跑了一遍

派单 §3 要求「顺手把正确的说法验一遍」。三次运行**全部串行**、一次一个相位、不与任何别的命令并行（硬规矩 #62）。

**harness**：`$env:TEMP\sdd_fr3\v08_mut.py`，`apply` / `restore` / `status` 三个动作。每次 `apply` 都：
① 断言待改的原串在文件里**恰好 1 处**命中、且变异后的串**0 处**命中（防重复施加）；
② 先做字节备份并断言 `sha256(backup) == sha256(original)`；
③ 写盘后回读、断言回读字节 == 要写的字节；
④ **在 AST 上确认这次变异真的改了代码**（`ast.dump(before) != ast.dump(after)`，硬规矩 #53）。
每次 `restore` 都断言「回读字节与备份**逐字节相同**」并打印新旧 sha。

**相位 0 — 干净对照（已知 GREEN，跑在一切变异之前）**

```
$ cd backend ; python -m pytest -q
531 passed in 64.18s
```

**相位 1 — M-PROD：改坏生产侧 `IMPACT_RANK`（`HIGH: 0 ↔ LOW: 2` 对调）**

```
M-PROD APPLIED: 12384 B -> 12384 B ; sha 1FC9AA42A6B93BF5 -> 73BFC57CFF1D8A3F
  ast.dump changed on disk = True
  old hits now = 0 ; new hits now = 1

$ python -m pytest -q -rf --tb=line
FAILED tests/test_refdata_prescription.py::test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable - AssertionError: assert None == 'stationary_cycling'
FAILED tests/test_refdata_prescription.py::test_impact_rank_values_are_pinned_verbatim - AssertionError: assert {<ImpactLevel...OW: 'low'>: 0} == {<ImpactLevel...OW: 'low'>: 2}
2 failed, 529 passed in 62.13s

M-PROD RESTORED: 12384 B -> 12384 B ; sha 1FC9AA42A6B93BF5 ; byte-identical-to-backup=True ; old_present=1 new_present=0
```

→ **红的是 2 条**：`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable`（`lookup("interval_run", MEDIUM)` 返回 `None` 而不是 `stationary_cycling`）与 `test_impact_rank_values_are_pinned_verbatim` 的**支 1**（整个字典的字面值）。
→ **`test_equivalence_never_maps_to_a_higher_impact_level` 保持绿**。**这就是 I2 那一句被撤销的实证**：改坏生产侧的秩，「不升冲击」那一条**恒绿**。

**相位 2 — M-TEST：改坏测试侧 `IMPACT_DESCENDING`（反序成 `("low", "medium", "high")`）**

```
M-TEST APPLIED: 54774 B -> 54774 B ; sha EF94366A343A23F2 -> 309AED3EA2E0AC70
  ast.dump changed on disk = True

$ python -m pytest -q -rf --tb=line
FAILED tests/test_refdata_prescription.py::test_equivalence_never_maps_to_a_higher_impact_level - AssertionError: interval_run(high) -> stationary_cycling(low) 升了冲击
FAILED tests/test_refdata_prescription.py::test_impact_rank_values_are_pinned_verbatim - AssertionError: assert ['high', 'medium', 'low'] == ['low', 'medium', 'high']
2 failed, 529 passed in 64.40s

M-TEST RESTORED: 54774 B -> 54774 B ; sha EF94366A343A23F2 ; byte-identical-to-backup=True ; old_present=1 new_present=0
```

→ **红的是 2 条**：`test_equivalence_never_maps_to_a_higher_impact_level`（10 条映射**全部**被判「升了冲击」，offender 列表 10 项）与 `test_impact_rank_values_are_pinned_verbatim` 的**支 2**（按秩排出来的成员序 ≠ 测试侧那份降序元组）。
→ `test_lookup_honours_…` **保持绿**（它不用 `IMPACT_DESCENDING`）。

**两次实测的完整归属表**（这张表就是写进 4 处散文的那个口径，硬规矩 #52/#56：每句都标主语）：

| 变异对象 | `test_equivalence_never_maps_to_a_higher_impact_level` | `test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable` | `test_impact_rank_values_are_pinned_verbatim` | 合计 |
|---|---|---|---|---|
| **生产侧** `IMPACT_RANK`（`HIGH:0 ↔ LOW:2`） | **绿** | **红** | **红**（支 1） | `2 failed, 529 passed` |
| **测试侧** `IMPACT_DESCENDING`（反序） | **红**（10 条 offender） | 绿 | **红**（支 2） | `2 failed, 529 passed` |

**旁证一致性**：这两次结果与账本 Ruling 108 记的 fr1 变异 M-B（`1 failed, 527 passed`，红在 `:434`）方向一致——fr1 时还没有 `test_impact_rank_values_are_pinned_verbatim`，故那时只红 1 条（`lookup`）；fr2 加了那条之后，同一个生产侧变异应当红 **2** 条，我的实测正是 2 条，且 fr2 的 docstring（改前 `:493-496`）自己就写着「M-A1 → `2 failed, 529 passed`（另一条红的是 `test_lookup_honours_…`）」。三处**互不依赖**的记录给出同一个数。

**还原自证**：两个相位结束后 `git status --short` 为空、两个文件的 `sha256` 都回到开工值（`1FC9AA42A6B93BF5` / `EF94366A343A23F2`，与 fr3.1 表里 `E06CBE6A96D28051` / `B969FFF932185E53` 是同一份字节的「裸字节 sha」与「归一化 sha」两种口径）。**全程没有用 `git checkout` / `restore` / `switch` / `merge`。**

---

### fr3.6 改动面自证

#### (1) `backend/app/**` —— 硬规矩 #32：剥 docstring 后 `ast.dump` 与 `966eae0` 比，**44/44 全 SAME**

基线取 `git show 966eae0:<path>`（**没有 checkout**）；剥 docstring = 对 `Module` / `ClassDef` / `FunctionDef` / `AsyncFunctionDef` 四种节点删掉 `body[0]` 的字符串常量 `Expr`；`ast.dump(..., include_attributes=False)`，故行号推移不参与比对（注释根本不进 AST）。

```
backend/app/** python files: 44  (baseline 966eae0)

[MAIN]  ast.dump(strip docstrings) SAME = 44/44 ; DIFF = []
[CTRL-1] ast.dump(WITH docstrings)  SAME = 41/44 ; DIFF count = 3
           docstring-changed: backend/app/db/models/prescription.py
           docstring-changed: backend/app/domain/prescription/exercises.py
           docstring-changed: backend/app/refdata_prescription.py
[CTRL-2] injecting real semantic mutations into the current tree; the stripped-AST gate must catch every one
  exercises.py: IMPACT_RANK HIGH 0 -> 2                ast-changed-by-mutation=True gate-caught-vs-baseline=True
  exercises.py: lookup >= -> >                         ast-changed-by-mutation=True gate-caught-vs-baseline=True
  refdata_prescription.py: drop .value                 ast-changed-by-mutation=True gate-caught-vs-baseline=True
  refdata_prescription.py: remove session.flush()      ast-changed-by-mutation=True gate-caught-vs-baseline=True
[CTRL-3] baseline-vs-baseline on a file NOT touched this round
  backend/app/domain/indicators.py: bytes-identical-to-baseline(LF-normalised)=True ; stripped-AST SAME=True
```

* **对照组 ①**（不剥 docstring）：41/44 SAME、**3 个文件 DIFF**，且 DIFF 的正好是本轮改过 docstring 的那 3 个 → 证明「剥 docstring」这一步真在做事、主判定不是恒真。
* **对照组 ②**（往当前工作树注入 4 个**真语义变异**）：4/4 都被闸门抓到；且每个变异都先在 AST 上确认「它真的改了代码」（硬规矩 #53）。
* **对照组 ③**：本轮没碰的 `indicators.py` 与基线**逐字节相同**（LF 归一化后）→ 主判定的 SAME 不是「所有文件都被判 SAME」的空转。

再加一道更细的尺子（把「只改 docstring/注释」这句话变成可数的证据）——**剥 docstring 后逐文件枚举代码级字面常量**，与 `966eae0` 比：

```
changed files under backend/ (7 .py); code-level literal constants that differ from 966eae0 (docstrings stripped):
  backend/app/db/models/prescription.py:                -0 / +0
  backend/app/domain/prescription/exercises.py:         -0 / +0
  backend/app/refdata_prescription.py:                  -0 / +0
  backend/tests/db/test_models.py:                      -0 / +0
  backend/tests/domain/test_prescription_templates.py:  -0 / +0
  backend/tests/seed/test_generate.py:                  -0 / +0
  backend/tests/test_refdata_prescription.py:           -3 / +3
      - 'A6A000F58815FCBB'                                        + '63033BBD7F68CC1F'
      - '0FFB881574AC04F3'                                        + '822CB86A5E998301'
      - 'BMI 不归桶（Plan01 Ruling 19），故 None 必在其中'          + 'BMI 不归桶（spec §4.2：短板判定项 = 6 个，排除 BMI），故 None 必在其中'
TOTAL differing code-level literals = 6
```

→ **`backend/app/**` 的代码级字面量差异 = 0**；`backend/tests/**` 只有 **3 处**，全部是派单授权的（2 个指纹常量 = 派单 §2.3；1 条 assert 消息 = 派单 §2.1 I5 行点名的位置）。**没有第 4 处。**

#### (2) `backend/data/**` —— `yaml.safe_load` 前后比对（比 `ast.dump` 更适合 YAML 的尺子）+ **带对照组**

尺子：把两份 YAML 各自 `yaml.safe_load`，再做 `json.dumps(..., sort_keys=True)` 规范化（这样键序不可能掩盖或伪造差异），比规范化后的字符串。

**改前快照**（在任何编辑之前落盘）：`yaml_before.json` 6640 B，`sha256[:16]=D9929B0163243A29`；同时打印 `exercises.yaml: 23 entries` / `exercise_equivalence.yaml: version='1.0' mappings=10 volume_reduction={'bmi_over_30': 0.8, 'muscle_low_p10': 0.9}`。

**主判定（改后）**：

```
yaml.safe_load BEFORE vs AFTER (canonical JSON) identical = True
  exercises.yaml: identical = True
  exercise_equivalence.yaml: identical = True
  self-control (unchanged copy compares equal) = True
```

**对照组（4 个真数据变异，尺子必须全抓到）**：

```
CONTROL GROUP (ruler must catch every real data mutation):
  A exercises.yaml[interval_run][impact_level] high->medium            : caught=True
  B equivalence mappings[0][to] stationary_cycling->band_resistance    : caught=True
  C delete exercises.yaml[challenge_task] (23 -> 22 entries)           : caught=True
  D volume_reduction[bmi_over_30] 0.8 -> 0.85                          : caught=True
  ALL CAUGHT = True
```

→ 尺子**不恒 True**（4/4 真变异都被抓到），而真实改动判为 identical。派单 §3 点名的四个不变量另有一次直接实算：**动作数 23 / 映射数 10 / `version` `"1.0"` / `volume_reduction` `{bmi_over_30: 0.8, muscle_low_p10: 0.9}`** —— 改前改后逐字相同。

再加一道**逐行**尺子（把「只改注释行」变成可数的证据）：`git diff -U0` 里每一条 `+`/`-` 行，去掉 diff 标记后必须以 `#` 开头：

```
backend/data/exercises.yaml:            +48 / -8 lines ; non-comment additions=0 ; non-comment deletions=0
backend/data/exercise_equivalence.yaml:  +6 / -2 lines ; non-comment additions=0 ; non-comment deletions=0
```

#### (3) `backend/tests/**` —— 测试函数清单未变

```
test-function inventory (def test_*) baseline vs current, whole backend/tests tree
  baseline 966eae0: 22 files, 390 test functions
  current       : 22 files, 390 test functions
  files whose test-function set changed: NONE
```

→ **没有新增/删除/改名任何测试函数**（390 = 390，逐文件集合相同），与「passed 数必须仍是 531」自洽（531 与 390 的差来自 parametrize）。另 4 个改动的测试文件里，3 个 `ast.dump`（剥 docstring）**SAME**，第 4 个只差上面那 3 处授权字面量。

#### (4) `Document/` —— 只改了 §14 第 28 项那一格

```
Document/2026-09-28-体育闭环原型-设计spec.md: hunks=['@@ -933 +933 @@'] +1 / -1
  OLD line length = 1192      NEW line length = 1861
  common prefix length = 926
  common prefix tail = '…改这两个数会直接改变 BMI > 30 与肌肉量 < P10 学生身上红/黄层处方的训练量。**Task 7 不得把它们当成 spec 条文引用。** ⚠️ **编号冲突'
  old cells (pipe count) = 6 ; new cells = 6
  old row starts with '| **28** |' = True ; new row starts with '| **28** |' = True
```

→ **1 个 hunk、1 行换 1 行**；分歧点落在最后一格内（公共前缀 926 字符，正好到「⚠️ **编号冲突」为止）；表格结构未变（`|` 数 6→6）；文件行数 974→974、CRLF 974→974。`.gitattributes` / `.gitignore` **未动**（`git diff --name-only` 对这两个文件为空）。

---

### fr3.7 落盘闸门（硬规矩 #48 升级口径）与一处我主动加的收紧

#### (1) 双向串查 —— 全部命中，`RESULT: ALL GREEN`

不用编辑工具做本轮任何一处生产文件改动。全部改动由一个字节级替换引擎落盘（`$env:TEMP\sdd_fr3\v09_edit.py` / `v13_edit2.py` / `v17_fixup.py` / `v18_fp.py`），每处替换都当场做四件事：
① 断言 OLD 在文件里**恰好 N 处**命中（N 由我指定，本轮全部是 1），不符就 `SystemExit`、**整个文件不写**；
② **查询机制自证**：先断言 OLD 的前 40 个字符至少 1 处命中（防「查询本身失效导致的 0 命中」，派单 §0 的第 ③ 条）；
③ 替换后断言 **OLD 残留 = 0** 且 **NEW 命中 ≥ N**；
④ 写盘后**回读**并断言回读字节 == 要写的字节，然后打印改前/改后的字节数、CRLF/LF 数、归一化指纹与裸字节 sha。

行尾处理：先把整份文件按字节读入、判定它是**纯 CRLF** 还是**纯 LF**（混合就 `SystemExit` 拒绝改），在 LF 归一化的文本上做替换，再按该文件自己的约定还原。→ 9 个 `.py`/`.md` 保持 CRLF、2 个 YAML 保持 LF（改后 CRLF 仍是 0）。

最后再跑一遍**独立的**总闸门（`v19_gate.py`，不复用编辑引擎的任何状态）：**10 条查询机制对照 + 33 条「旧串必须 0 命中」+ 51 条「新串必须 ≥1 命中」+ 指纹/字节/行尾/禁区/diff 面**，结果 `RESULT: ALL GREEN`（中途唯一一次 FAIL 是我自己写错了一个 needle：把 `读回是 'high'` 记成 `落库读回是 'high'`；改正 needle 后全绿——**不是文件没写对**，我在这一节把这次自纠记下来，免得控制者看到两份日志对不上）。

#### (2) 缩进/空白敏感改动的额外抽查

`repr()` 抽查：改动前我用 `repr()` 逐行打印过每一处 OLD 的原文（含前导空格），因此抓到过一次真错——`app/db/models/prescription.py` 的那三行是**模块 docstring、顶格无缩进**，我第一版按 4 空格缩进写 OLD，`--dry` 立刻报 `expected 1 hit(s) of OLD, got 0`，**没有写坏任何文件**。`tests/db/test_models.py`（4 空格）与 `tests/seed/test_generate.py`（4 空格）两处也各自 `repr()` 核过。

#### (3) ⚠️ 我主动加的一道收紧：**不在源码里复述被撤销的原句**（本轮的一个判断，请控制者裁）

第一趟改完之后我做双向串查，发现一个问题：我在 8 处「更正说明」里**逐字引用了被撤销的那句话**（例如「此前这里印的『改坏任何一份都会让 …… 变红』」）。这么写的坏处是——`git grep "改坏任何"` / `git grep "Ruling 19"` / `git grep ":163"` 这类**基于串查的复核**（本项目最常用的复核手段）会**照样命中**，而下一个人无法只凭 grep 结果区分「这是一条仍然生效的断言」还是「这是一句已被撤销的断言的引文」。硬规矩 #48 的双向闸门也会因此变得含混（「旧串残留 = 0」这一半判不出来）。

于是我加做了第二趟（`v17_fixup.py`，11 处），把所有**可能被误当成有效陈述**的复述改成描述式：
* 「改坏任何一份都会让 X 变红」→「此前这里把两份词表混成一个主语，声称其中**任何**一份被改坏都会让同一条测试 X 变红——那**对生产侧那一份不成立**」；
* 「Plan01 Ruling 19」→「此前这里引的是 Plan01 账本里**另一条**裁定（那条讲的是 `raw_from_score` 对非单调序列抛 `ValueError`），即**引用号错**；本行刻意**不复述那个错号**，免得它被下一次 grep 当成一处有效引用」；
* 三个过期裸行号 `:163`/`:228`/`:472` → 「此前这里印的是**三个裸行号**，它们是 `fb5bddb` 上 `== 14` 的位置……那三个过期行号本轮**不再复述**」（这也正好落回 I4 的修法：**不在散文里留裸行号**）。

结果：改后 `git grep` 这些旧串在**本轮涉及的 10 个文件里全部 0 命中**（fr3.7-(1) 的 33 条 ABSENT 检查）。
**保留复述的两处**，因为它们不属于「可能被误当成有效陈述」这一类，请控制者核我的判断：
* `refdata_prescription.py`：「此前只写『本 Task 的四个函数』」「此前印的『同一口径』」——这两个短语不是事实断言、也不是引用号/行号，只是**缺主语**，引号里保留反而更能说明改了什么；
* spec `:933`：「**不是**此前这里写的『整体后移为 **#29–#35**』」——I7 的全部要点就是「照那句执行会造出一个 #35」，不把旧处方摆出来并显式否定，Task 12 无从知道自己差点踩什么。

---

### fr3.8 验收判据逐条

| 判据 | 实测 | 判定 |
|---|---|---|
| 版本冒烟（硬规矩 #73） | `3.11.1 2.1.3 3.0.6 2.4.6 6.0.3` | ✅ 见 fr3.0 |
| `backend/app/**` 只改 docstring / 注释 | 剥 docstring 后 `ast.dump` 与 `966eae0` 比 **44/44 SAME**；代码级字面量差异 **0** | ✅ fr3.6-(1) |
| `backend/data/**` 只改注释行；23 / 10 / `"1.0"` / `{0.8, 0.9}` 不变 | `git diff -U0` 的 +/- 行**全部**以 `#` 开头（+54 / −10，非注释 0）；`safe_load` 规范化 JSON **identical**；对照组 4/4 caught | ✅ fr3.6-(2) |
| 两个 YAML 保持纯 LF | CRLF **0** / **0** | ✅ fr3.4 |
| 两个指纹常量同步且等于现算值 | `63033BBD7F68CC1F` / `822CB86A5E998301`，三个旧值 0 命中 | ✅ fr3.4 |
| `national_standard_2014.csv` 一个字节未动 | `21412 B / CRLF 0 / D2C8E539E2FA0029`（改前改后同值） | ✅ |
| **passed 数仍是 531** | `531 passed in 58.82s`（改后）；改前 `531 passed in 64.18s` | ✅ 不新增/删除测试函数（390 = 390） |
| domain 覆盖率 **441 / Miss 0 / 120 / BrPart 0 / 100%** | `TOTAL 441  0  120  0  100%`，`530 passed, 1 skipped in 135.72s`；逐模块与派单一致（`derive 146/54`、`indicators 62/14`、`percentile 94/26`、`stratify 92/20`、`tables 5/0`、`prescription/exercises 38/6`、`prescription/templates 2/0`、`prescription/__init__ 2/0`、`domain/__init__ 0/0`）；那 1 个 skip 是 `test_backfill.py` 的 trace-hook 自觉跳过 | ✅ |
| 两个架构守卫全绿、扫描面不变 | `pytest -q tests/architecture` → **6 passed**；`SCANNED_DIRS` 实跑 **pipeline 7 + db 11 + domain 9 = 27**；`_domain_files()` = 9；两道空转下界（`>= 8` / `>= 5`）未动 | ✅ |
| 变异验收（串行、带已知 GREEN 对照、AST 确认变异生效、还原逐字节自证） | 相位 0/1/2 见 fr3.5；两次各 `2 failed, 529 passed`；还原后 `git status --short` 为空、sha 回到开工值 | ✅ |
| `Document/` 只改 §14 第 28 项那一格；保持 CRLF | 1 hunk `@@ -933 +933 @@`、+1/−1、`\|` 数 6→6、974 行 / 974 CRLF 不变 | ✅ fr3.6-(4) |
| `.gitattributes` / `.gitignore` 未动 | `git diff --name-only` 对两者为空 | ✅ |
| 禁区：`backend/pe.db` 不存在、`backend/data/seed/` 0 文件 | `pe.db exists = False`；`data/seed` 文件数 **0** | ✅ |
| 未跑 `app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` | 本轮只跑过 `pytest`（含 `--cov`）与只读的 `git show` / `git grep` / `git diff` / `git log` / `git ls-tree`；**没有 checkout / restore / switch / merge / rebase** | ✅ |
| 一个 commit、不 push | 见 fr3.10 | ✅ |
| `git status --short` 0 行、无临时目录残留 | 见 fr3.10 | ✅ |

---

### fr3.9 我发现的控制者错误 / 评审者错误（逐条注明成立 / 不成立 / 歧义 + 证据）

按 Ruling 45/51/65 的纪律：**把不成立的指控认下来和把成立的辩掉是同一种失职**，故 (2) 也逐条列出我核过但**不成立**的怀疑。

#### (1) 成立（3 条）

| # | 位置 | 原文 | 我的实测 | 严重度 |
|---|---|---|---|---|
| **CE-fr3-1** | **派单 §2.3** | `:53  EXERCISES_FINGERPRINT = "A6A000F58815FCBB"` / `:56  EQUIVALENCE_FINGERPRINT = "0FFB881574AC04F3"` | 改前实测两个常量在 **`:69` / `:72`**；`:53`–`:58` 是 `from app.domain.prescription.exercises import (…)` 那个 import 块。**两个指纹值本身逐字正确**，故不影响本轮任何判据。**收尾评审者报的 `:69`/`:72` 是对的**（review `:448`/`:338`），即这一格上评审者比派单准 | 成立（Minor：行号错；硬规矩 #61 的又一次落空——但这次只错行号、没错值，比 Ruling 119 的 CE-1/2/3 轻） |
| **CE-fr3-2** | **`.gitattributes`（`.superpowers/**` 那一段的注释）** | 「这些文件的工作树本来就是**混合**的（`task-1-report.md` 纯 LF、**`task-2-report.md` 与 `progress.md` 纯 CRLF**）」 | 实测：`task-1-report.md` 245229 B / LF 3325 / CRLF 0 → **纯 LF** ✅；`progress.md` 233921 B / LF 1544 / CRLF 1544 → **纯 CRLF** ✅；`task-2-report.md` 127827 B / LF 969 / **CRLF 946 / 裸 LF 23** → **MIXED**，不是纯 CRLF ❌（裸 LF 全在第 **2–24** 行，即报告头部）。⚠️ **账本自己 `:1406` 记的是正确的**（「`task-2-report.md` **MIXED**（CRLF 946 + 裸 LF 23）」），即 `.gitattributes` 的注释与账本**自相矛盾**。附带实测：`task-2-brief.md` 也是 MIXED（LF 159 / CRLF 150 / 裸 LF 9），而那段注释没提它 | 成立（Minor：注释与账本不一致。**我没改**——派单 §3 明写「`.gitattributes` / `.gitignore` 不许动」，且属性本身（`-text`）是对的、错的只是解释性注释。请控制者改） |
| **RE-fr3-1** | **`task-2-review.md:257`（评审者）** | 「`repr()` 是 **27**、`format()` 是 16」 | 实测 `len(repr(ImpactLevel.HIGH))` = **26**（`<` + `ImpactLevel`(11) + `.` + `HIGH`(4) + `:` + 空格 + `'high'`(6) + `>`）；`format()` = 16 ✅。**不影响 I-1 成立**（16 / 26 / 16 三种口径都给不出 19），只是支撑数据里有一个数错 | 成立（Minor，评审者的支撑数字错；finding 本身不受影响） |

#### (2) 歧义 / 建议措辞不成立（1 条）

| # | 位置 | 判读 |
|---|---|---|
| **RE-fr3-2** | **`task-2-review.md:497`（M-4 的「建议」列）** | **finding 成立、建议的措辞不成立。** 评审者建议改成「spec §7.2 `:487` 与**两个 addon 模块名**（`:482`/`:484`）合计点名的 12 项」。实测 spec `:487` 那段散文**已经**点了「体脂超标追加 10% 能量消耗模块」，即 `:482` 的 `energy_expenditure_plus_10pct` 与散文里那一个是**同一个模块**；照建议的措辞写，会把它数两次，等于**用一个新的不准确换掉旧的不准确**。正确的算术是：**散文的 12 项 − 可选挑战任务 + 抗阻优先模块（`:484`）= 本文件的 12 项**（散文点了 12 个东西、其中一个是本文件算作补项 7 的「可选挑战任务」；本文件这 12 项里的「抗阻优先模块」只出现在 `addons` 代码块）。我按这个精确版落地，并在 YAML 注释里把「能量消耗模块两处都点了、是同一个东西、不重复计数」明写出来 |

#### (3) 不成立（我核过、控制者/评审者是对的）—— 正面确认

| 我核的对象 | 亲验结果 | 判定 |
|---|---|---|
| 派单 §5 的**全部**待改文件字节/行数/CRLF/指纹（10 个）+ 禁区 CSV | **11/11 逐字相符**（fr3.1 表 (1)，每行都标了 `OK`） | ✅ 不成立（派单对） |
| 派单 §5 的**全部**锚点命中数（9 个） | **9/9 逐字相符**（fr3.1 表 (2)） | ✅ 不成立 |
| 派单 §5 的 `== 15` 位置 / 函数名位置 / 计划 `:688` / spec `:933` / `SCANNED_DIRS` 27 / 禁区三项 / 4 份评审产物字节与行数 / 依赖版本 / 531 passed / 441-0-120-0-100% | **逐条相符**（fr3.1 表 (3) + fr3.0 + fr3.8） | ✅ 不成立 |
| 派单 §0「代码基线是 `966eae0`，`2df6825`/`31c9212`/`1191170`/`7296793`/`23388c7`/`23325de`/`8e6a38f` 七笔不动 `backend/`」 | `git log --oneline -14` 逐笔对上；`git show --stat 966eae0` = 4 个 M、全在 `backend/tests/`；`git show --stat d40f36c` = 1 file（只改计划文档） | ✅ 不成立 |
| 派单 §2.1 I5「源头是控制者账本 P2-A4 写错、已传播进 2 份源码；账本由控制者自己改」 | Plan02 账本 `:999`（P2-A4）逐字含「BMI 天然不属于任何短板桶，Plan 01 Ruling 19 的口径」；`:1437`/`:1449` 已把它记为 CE-7 / 控制者错误 #121 | ✅ 不成立（且账本已自纠，我按派单**没有**动账本） |
| 派单 §2.1 I7「只许改第 28 项那一格；保持 CRLF（974 行 / 974 CRLF）」 | 按字面**可满足**，已做到（fr3.6-(4)：1 hunk、+1/−1、`\|` 6→6、974/974 不变） | ✅ 不成立（判据可满足） |
| 派单 §3「passed 数必须仍是 531（本轮不新增/删除测试函数）」 | 按字面**可满足**，已做到（531 = 531；`def test_*` 清单 390 = 390、逐文件集合相同） | ✅ 不成立 |
| 评审者 I-2 的 AST 四行表、`:434` 是 `lookup` 那条的 `def` 行、`:317` 是秩那一行 | **逐字复现**（fr3.2 I-2），并用两次真变异把静态结论升级为动态实证 | ✅ 不成立（评审者对） |
| 评审者 I-3 的 8/4/4 三个数与 reuse counts | **逐字复现**（fr3.2 I-3） | ✅ 不成立 |
| 评审者 I-6/I-7 的计划行号与 `git show d40f36c --stat`、`git diff --numstat fb5bddb..966eae0 -- spec` = `1 0` | **逐字复现**（fr3.2 I-6/I-7） | ✅ 不成立 |
| 评审者 M-1/M-2/M-3/M-5/M-7/M-8/M-9/M-10 的每一处行号与引文 | **逐条核过、全部相符**（fr3.3 表第 3 列给了我自己的实测口径） | ✅ 不成立 |
| 评审者 I-1 的「机制错」结论 | 成立，且我**补上了它标为『不可复核』的那一层**：`String(8).bind_processor(sqlite 方言)` 实测 `None` | ✅ 不成立（评审者对，我补强） |
| 评审者 §4.1 的 CE-1..CE-7 与 §4.2 的 CE-8 | 我抽验了可独立复核的 4 条：**CE-6**（`e09e5f6` 上 `assert len(scanned) >= 8` 不在 `:172`）——本轮无关、未复算；**CE-7**（账本 `:999` 引错 Ruling 19）**逐字复核成立**；**CE-4/CE-5**（评审包「禁区命中」那一节标题与输出自相矛盾）——我核了实质禁区三项**全部未被侵犯**（CSV 指纹 ✅、`data/seed/` 0 文件 ✅、`backend/data` 里既有 3 个文件在 `fb5bddb..966eae0` 的 name-status 里 0 命中 ✅），故评审者「实质禁区未被侵犯、错的是标题口径」的判读成立 | ✅ 不成立（评审者对） |

#### (4) 我按字面**无法**照办、故按实测做的一处（派单 §2.1 I2）

派单 §2.1 I2 行写「⚠️ 同文件 `exercises.py:94-96` 写的是**正确版**（『之一会红』）——**把两处统一成正确的那个说法**」。我实测那句**为真但不完整**：两次变异里 `test_impact_rank_values_are_pinned_verbatim` **都**红，而它不在那句列的两项之内（fr2 加它的时候没回改这句，正是 M-7 的同一个根因）。**照字面「统一成那个说法」会留下一处漏项**，与硬规矩 #56/#66 冲突。故我把**三处**都统一成同一个**完整**的两支清单（含实测的 `2 failed, 529 passed` 与逐条测试名），并在 fr3.2 I-2 的落地清单第 2 项显式报备这处超出点名位置的改动。

---

### fr3.10 收工自证

```
$ git status --short
（0 行 —— commit 之后）

$ git log --oneline -1
（本轮那一个 commit；短哈希见本轮返回给控制者的消息）

$ git show --stat --oneline HEAD
 11 files changed …   # 10 个源文件 + task-2-report.md（本节）
```

* **一个 commit、不 push**；`.superpowers/` 的报告改动**并进同一个 commit**（硬规矩 #68 修订版第 1 条）。
* **三个指纹**：CSV `D2C8E539E2FA0029`（未变）；`exercises.yaml` `63033BBD7F68CC1F`、`exercise_equivalence.yaml` `822CB86A5E998301`（新值，且与代码里两个常量逐字相同）。
* **无临时目录残留**：本轮所有取证脚本与中间产物都在仓库外的 `$env:TEMP\sdd_fr3\`（11 个 `v*.py` + 1 份 `yaml_before.json` + `backup\` 下 2 份变异前备份 + 本节草稿 + 报告备份）。仓库内**没有**新建任何目录或文件；`backend/pe.db` 不存在、`backend/data/seed/` 0 文件、`.pytest_cache/` 与 `__pycache__/` 与 `.coverage` 都在 `.gitignore` 里（`git status --short` 为 0 行即为证）。
* **报告追加的字节备份**（硬规矩 #68 修订版第 2 条）：追加前把 `task-2-report.md` 整份复制到
  `$env:TEMP\sdd_fr3\backup\task-2-report.md.pre-fr3`，追加后核对「**追加前的全文是追加后全文的前缀**」并打印两者的字节数与 `sha256[:16]`（见下面 fr3.10-(1)）。

#### (1) 本报告文件的落盘自证

```
备份（硬规矩 #68 修订版第 2 条）
  路径    $env:TEMP\sdd_fr3\backup\task-2-report.md.pre-fr3
  字节    __BK_SIZE__ B     sha256[:16] __BK_SHA__
追加前的 task-2-report.md
  字节    __PRE_SIZE__ B    行 __PRE_LINES__    CRLF __PRE_CRLF__ + 裸 LF __PRE_BARE__
  sha256[:16] __PRE_SHA__
```

本节以 **CRLF** 追加（与该文件第 25 行起的主体一致；那 23 个裸 LF 全在第 2–24 行的报告头部，本轮一个字节没动它）。

追加之后由脚本**回读磁盘**做三道核对，输出逐字贴在**本轮的 commit message 里**——不写回本文件，因为把它写回文件会让文件自己的字节数与 sha 再次变化（这正是 Ruling 116/118 那一类自指陷阱）：

1. 「**追加前的全文是追加后全文的前缀**」（`post.startswith(pre)`）；
2. **双向串查**（硬规矩 #48 升级口径）：本节的新串命中 ≥ 1，且**追加前那份的最后 80 个字符**在追加后仍然**恰好 1 处**命中（即旧尾巴没被截断、也没被复制成两份）；
3. **字节数 / CRLF 数 / 裸 LF 数 == 追加前 + 本节**（逐字节拼接，不多不少）。

---

### fr3.11 关切与未尽事项

**① 本轮取证脚本刻意放在仓库外（`$env:TEMP\sdd_fr3\`），与前几轮的 `frN_probes/` 惯例不同 —— 请控制者裁是否要补入库。**
仓库里已经有 `…/fr2_probes/`、`…/fr3_probes/`、`…/fr4_probes/`（都是 `8e6a38f` 那一笔随 `.superpowers/` 整目录入库的、**Task 1** 的 fix round 探针）与 `…/review2_probes/`（收尾评审者的）。**`fr3_probes` 这个名字已经被 Task 1 占用了**，我这一轮是 Task 2 的 fix round 3，若照惯例建目录会与它撞名/混淆；而建 `t2fr3_probes/` 又要多入库十几个文件。派单 §3 的收工自证要求「无临时目录残留」，我按最保守的读法办（仓库内零新增文件），代价是**审计链里没有本轮的脚本原件**——为此我把每个脚本的关键代码与**全部原始输出**都逐字贴进了本节。若控制者认为脚本本身必须入库，我可以再做一笔 `docs:` commit 把 `$env:TEMP\sdd_fr3\` 的 11 个 `v*.py` 拷进 `…/t2fr3_probes/`。

**② 账本 P2-A4（`progress.md:999`）里那个错引用号仍在，按派单归控制者改。**
本轮我已把它从**两份源码**里清掉（I5），但账本 `:999` 那句「Plan 01 Ruling 19 的口径」还在原地。评审者 review `:418` 也提醒过「顺手把账本 P2-A4 那句一起勘误，否则 Task 3/4 会第三次抄它」——**Task 3 的模板加载器同样要处理 `targets` 的取值域**，若它照账本抄，这会是第三次传播。请控制者在下一轮派单之前先勘误账本（账本 `:1437`/`:1449` 已经把它记成 CE-7 / #121，只差把 `:999` 那句本体改掉）。

**③ `.gitattributes` 的注释与账本自相矛盾（CE-fr3-2），我不许动那个文件。**
错的是「`task-2-report.md` 纯 CRLF」这半句（实测 MIXED：946 CRLF + 23 裸 LF，裸 LF 全在第 2–24 行），账本 `:1406` 记的是对的。属性 `-text` 本身没问题、不需要改；只是那段注释是**解释为什么要用 `-text`** 的论据，论据里有一个假事实。顺带：`task-2-brief.md` 也是 MIXED（150 CRLF + 9 裸 LF），那段注释没提它。**这件事对下游的实际影响**：任何「按统一行尾假设去算这份文件的字节数」的脚本都会算错——本轮我追加本节时就是逐字节读、按 CRLF 追加、并显式核了追加前后的 CRLF 数（946 → 见 fr3.10-(1)）。

**④ I-7 改后的那一格仍然引**计划行号**（`:682`/`:684`/`:688`/`:707`），我只做到了「绑 commit」，没做到「不写裸行号」。**
派单只授权改这一格，而这一格是**给项目负责人（邹红老师）看的清单**，写成四条 `git grep` 命令的可读性太差；故我按硬规矩 #37 的第二个分支办（写明 commit：`2df6825`）。**风险**：计划文档在 Task 12 还会被改，届时这四个行号会第四次过期。**建议**：Task 12 Step 3 落地时顺手把这一格的行号换成「计划 Task 12 Step 3 的标题行 / 其下的『P2-A3 的后续更正』整段 / §14 补项清单行 / 『计划完成后的状态』那一条」这种可 grep 的描述（我已经在格子里同时写了这四处的**逐字原文片段**，所以即使行号过期，靠原文也找得到）。

**⑤ 我给 `exercises.py` 的 `IMPACT_RANK` 注释做了超出点名位置的更新（fr3.2 I-2 落地清单第 2 项、fr3.9-(4)）。**
理由与判断都写在那两处了；如果控制者认为「统一成 `:94-96` 那个说法」应当**逐字**照办（即保留「之一会红」这个不完整但为真的表述），请回退我这一处——它与其他两处是独立的文本块，回退不影响 I2 的主修。

**⑥ 一处我没有改、但认为该报的过期计数（超出本轮 17 条的范围，故不顺手改）。**
`backend/tests/test_refdata_prescription.py` 的 `test_impact_rank_values_are_pinned_verbatim` docstring（改前 `:479-483`）写「今天看着它的本来只有**两条间接**守卫：上面那条…与 `test_lookup_honours_…`」——这句在 fr2 的语境里是对的（它说的正是「在本条之前」），但**它没有写「本条之前」这个时点**，读起来像在描述当前状态，而当前状态是**三条**（含它自己）。这与 M-7 同源（fr2 加了三处新东西、旧散文没跟着改），但评审者没点它、派单也没授权，且改它需要重写那段的时间态表述——**报给控制者，建议并入 Task 3 的散文清扫或下一轮**。（我这轮已经在同文件的 `IMPACT_DESCENDING` 注释里写了完整的三支归属表，所以「读起来像当前状态」的误导已经被隔壁那段抵消了一部分。）

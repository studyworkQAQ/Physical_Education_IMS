# Task 9 简报 — 黄金用例延伸到训练包 + spec 勘误 + 9 条待清扫（Plan 02 的收尾 Task）

> 本简报由控制者从 `Document/2026-10-06-实施计划02-智能处方引擎.md`（226515 B / 1105 行）按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + 重编号对照表 + Global Constraints + Review Focus + File Structure + **Task 9 全节（含预检更正 P9-A1..A8）** + **「计划完成后的状态」与「计划边界说明」两节**。

## 0. 派单说明（控制者写，不在计划正文里）

**代码基线**：见 `git log --oneline -1`（分支 `feature/plan-02-prescription-engine`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **793 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**（带 `--cov` 时 `792 passed, 1 skipped`）。
**表数 18**（`prescription` **16 列**、`weekly_adjustment` **8 列**）；`__all__` = **51**；`_MODELS_PUBLIC_BASELINE` = **33（刻意不动，Ruling 97）**；扫描面 **35**（本 Task 不新增文件，仍 35）。
**环境**：Python 3.11.1（**无 venv**）、SQLAlchemy **2.1.3**、pandas 3.0.6、numpy 2.4.6、PyYAML 6.0.3。
⚠️ **开工第一件事（硬规矩 #73）**：跑 `python -c "import sqlalchemy, pandas, numpy, yaml; print(sqlalchemy.__version__)"` 并记进报告。**若撞上 `ImportError: DLL load failed`，立刻停手报回控制者。**

## 0.1 ⚠️ 本 Task 的三条「第一次」（Plan 02 前 8 个 Task 都没做过）

1. **第一次动一个被指纹钉住的 `backend/data/` 文件**（P9-A3 要改 `exercises.yaml` 的头注释）。前 8 个 Task 一个字节都没动过 `backend/data/`。
2. **第一次改 Plan 01 的黄金用例夹具**（`golden_cases.json`）—— 它是 spec §12 的**唯一可执行判据**。
3. **第一次改 spec 正文**（前 8 个 Task 只改计划与账本）—— 而 spec 是**需求文档**，改它等于改契约。**每一处都要按 Plan 01 的勘误格式：原文 + 更正 + 理由 + Ruling/§14 编号。**

## 0.2 ⚠️ 3 条 Critical（逐条照办，不要按计划原文的字面做）

- **P9-A1**：**计划原文（P7-A2 那条连带）要求「给 13 例追加两个输入字段 `height_cm` 与 `weight_kg`」是假的** —— 它们**已经在夹具里**，嵌在 `input[i]["curr"]` 与 `["prev"]` 两个子映射里（13 例逐例全有），**不在顶层**。`_meta.bmi` 还逐字写着「**BMI 不在 input 里**：它由身高体重合成，口径与生成器逐字一致——`bmi = round(weight_kg / (height_cm / 100) ** 2, 1)`」。而 `run_stratify.py` 里算 BMI **得分**的那一行本来就是从 `raw.get("height_cm")` / `raw.get("weight_kg")` 读的（`raw` 就是 `curr`）。
  → **不给夹具加顶层副本**（那是**第二个住址**，违反 Global Constraint #3，且与 `_meta.bmi` 明写的设计意图相反）。**改成让 `_from_golden_cases` 从 `case["curr"]` 读这两个值。**
  ⚠️ **连带**：Task 7 留下的守卫 `test_golden_case_path_defaults_the_three_new_inputs_to_none` 的断言会**变成假的**（`bmi` 不再是 `None`）。**它不是「被删掉的守卫」，而是「处置变了、契约跟着变」**：改成钉「`snapshot_muscle_p10` 仍是 `None`（13 人 < MIN_SAMPLE=30，肌肉量组不产出行）而 `height_cm`/`weight_kg` 来自 `curr`」，`bmi` 的期望值改成**逐例实算**的字面值。
  ⚠️ 这条改动让 13 例的 `input_snapshot` 从「`bmi` 全 `None`」变成「各有其值」 → **spec §7.4 的三档安全触发第一次在黄金用例里真的可达**，而本 Task 要断言的 `needs_review` / `safety_substitutions` 从此**不再恒为假绿**。
- **P9-A2**：**spec §14 的真实形状**（控制者亲测，并为此记了自己一条错误 #155）：§14 在 spec 的 `## 14. 待确认事项清单` 那一节，表格行号是 **1–29 与 31**（**共 30 行**），**最大编号 31**，且 **`#30` 是一个刻意留的空洞** —— spec 自己在表格下方逐字写着「⚠️ 编号 #30 与本表之间有一个刻意的空洞：#29 与 #31 由 Plan 02 **Task 3** 写入……而 **#30 / #32 / #33 / #34** 留给计划 Task 12 Step 3 的清单」。
  → **计划里「27 → 34 项」两个数都错**（那是控制者用正则数表格行数出来的，正则漏了加粗编号的 18–31 行）。**正确算术：起点 30 行 / 最大编号 31 → 本 Task 追加 7 项（`#30` 填补空洞 + `#32`/`#33`/`#34` + `#35`/`#36`/`#37`）→ 终点 37 行 / 最大编号 37 / 无空洞。**
  ⚠️ **那段「刻意的空洞」的说明必须一并删掉或改写**（空洞被填了，说明就成了假的）。
  ⚠️ 编号 **18–31 行在 spec 里是加粗写的**（`| **18** | ...`），**你追加的 7 行照 1–17 的不加粗格式写还是照 18–31 的加粗格式写，自己判断并说明理由**（控制者倾向：**照 18–31 的加粗格式**，因为那一批也是「实现期发现的空洞」，与 #30/#32–#37 同类）。
- **P9-A3**：`backend/data/exercises.yaml` 的头注释里明写「⚠️ 这一条**尚未登记进 spec §14**：Task 2 只被授权追加第 28 项（`volume_reduction` 系数），而计划 02 的 Task 12 Step 3 那份 §14 补项清单里……」（另一处在文件中部写着「已按 Plan02 账本 P2-A3 登记进 spec §14 第 28 项」）。**你一旦把 `#30`（动作库的视频源）写进 §14，那句「尚未登记」就变成假的** → 要改它。
  ⚠️⚠️ **这是 Plan 02 第一次动一个被指纹钉住的文件**：`EXERCISES_FINGERPRINT` 实测是 `3DE598AF38631209`，**改一个字节就要同步 `tests/test_refdata_prescription.py` 里那个常量**。
  **程序（照做，顺序承重）**：① 先算新指纹（`sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16].upper()`）；② 改 YAML；③ **立刻用 `read_bytes()` 复核 `CRLF` 计数仍为 0**（`.gitattributes` 给 `backend/data/*.yaml` 钉了 `text eol=lf`，写成 CRLF 会让指纹与 `git ls-files --eol` 双双对不上）；④ 改常量；⑤ 跑那条指纹测试确认绿；⑥ 另两个指纹（`D2C8E539E2FA0029` 的 CSV 与 `822CB86A5E998301` 的 `exercise_equivalence.yaml`）**必须逐字不变**，报告里给出三个的实测值。
  **⚠️ 不许用 `git checkout` 还原**（`core.autocrlf=true` 会按属性重写工作树，硬规矩 #46/#70）。要还原就用 python 从 TEMP 备份写回原字节。

## 0.3 其余 5 条（简报的预检总表里有完整实测依据）

- **P9-A4**：黄金用例测试实测**只有 1 条**断言标签（`test_golden_cases_match_expected_labels`），另 3 条是 500 人分布测试。夹具形状 = **顶层 `{_meta, input, expected}`、`input` 与 `expected` 各是长度 13 的 list、按顺序一一对应**（`_meta.input_schema.student_id` 逐字写着「结果按 input 顺序一一对应 expected」）。→ **新加一条 `test_golden_cases_reach_the_training_package`（13 例参数化），不动既有那条**（既有那条守 Plan 01 的「标签」那一环，混在一起红的时候分不清是哪一环断了，硬规矩 #56）。⚠️ **`expected` 是 list 不是 dict** → 新字段要**逐例按顺序**加，**加错一格不会报错、只会让 13 例的期望值集体张冠李戴**。要有一条守卫断言 `[c["student_id"] for c in input] == [c["student_id"] for c in expected]`（若今天没有，本 Task 加）。
- **P9-A5**：`_meta` 里有 **3 处 Plan-01 时代的陈旧 Task 编号**（`_meta.purpose` 的「GC13，**Task 10** Step 0.7 补」、`_meta.expected_from` 的「**Task 10** 的 `stratify_dataset(list)`」、`_meta.input_schema.snapshot_muscle_p20` 的「**Task 10** 已落地它的生产者」）。**Plan 02 重编号后已经没有 Task 10 了**（原 Task 10 = 新 Task 7）→ 改成「**Plan 01 的 Task 10**」以消歧。⚠️ 这会改 `golden_cases.json` 的字节，但它**不被指纹钉住**（实测 `tests/` 下没有任何断言比对它的 sha256），故只需复核 JSON 仍能 `json.loads` 且例数仍 **13**。
- **P9-A6**：`_meta.percentile_note` 逐字写着「故本夹具此前印的「**28 行**」已过期，现在是 **24 行**」—— **夹具自己已经做过一次「散文过期」的自我更正**。**照它的格式办**：若发现 `_meta` 里还有别的过期数字，**就地更正并注明是哪个 commit 改的**，不要另起一节。
- **P9-A7**：待清扫第 1 条实测确认在 `assembler.py`，原文逐字是「按课再除一次才是单课量（**Task 8 的「本周训练单」读模型要自己决定怎么摊**）」，而 **Task 8 的决定是「不摊」**。→ 改成「Task 8 的读模型**不摊**：缩放只是 `weekly_volume × factor`，`sessions_per_week` 是骨架的结构属性、不参与缩放（P8-A1）」。⚠️ **这会改 domain 代码文件**，改完必须重跑覆盖率确认仍 **100%**。
- **P9-A8**：计划 Task 9 的 Step 3 原写「八个模块」，**实际是 9 个实质模块**（`exercises` / `templates` / `match` / `intensity` / `assembler` / `safety` / `override` / `triggers` / `weekly`）+ 包 `__init__.py`。计划正文已更正，**你复核一下改对了没有**。

## 0.4 §1.3 的 canonical sha256 回填（Task 7 结案时控制者实测，你只需写进 spec）

spec 的 `## 1. 背景与目标` 那一段里今天印着 `fe0a44e052c7946b425515fbaaa78f09e32320917a927cd10c8947aea3abfd8f` 与「行数合计 **882**」，**两处都已过期**。新值（夹具 = 60 人 / `seed=20250828` / 缺省注入 / `D=2025-09-15`，两遍 `run_daily`、`first == second` 成立）：

| 覆盖面 | 旧值 | **新值** | 行数合计 | 是谁改的 |
|---|---|---|---|---|
| **9 张**（Plan 01 的 `PIPELINE_TABLES`） | `fe0a44e052c7946b…` | **`1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952`** | **882（未变）** | `c5599db`（给 `input_snapshot` 加两个键）—— ⚠️ **不是扩表造成的** |
| **11 张**（Task 7 之后） | — | **`2b2649add55205e668c40e287f91592c0bcfcd68599d725030a68fc2400456df`** | **942** = 882 + 60 处方 + 0 调整 | `c7f2edb` 扩表 + `f0623b3` 加列 |

⚠️ **必须保留 spec 里那段历史记录**（终审 B 报的 886 行 / sha `2ef85d79…` / 基线 `728325a` / `percentile_snapshot` 28 行 → Ruling 214 让 BMI 的 4 个组不再产出退化常模行 → 24 行 → 886 → 882）—— **它是「一个修复改变了另一个修复的取证基线」的记录（Ruling 229），删掉就丢了因果链**。新值**追加**在它后面，不要覆盖。
⚠️ **两个值都不被任何守卫钉住**（那条测试断言的是 `assert first == second`，不是与字面哈希相等）→ 勘误里要写明这一点，否则下一个人会以为改代码会让某条测试变红。
⚠️ **你不必自己重测这两个值**（控制者已实测并写进账本 Ruling 152）；但**若你改了任何会影响它们的代码**（本 Task 的 P9-A1 会改 `_from_golden_cases`，**那是黄金用例路径、不是 60 人夹具路径**，理论上不影响），**必须重测并在报告里说明**。

## 0.5 9 条待清扫（Ruling 145 攒下来的，本 Task 一次性清完；计划正文里已落成一张表）

1. `assembler.py` 那句「Task 8 要自己决定怎么摊」（P9-A7，**会改 domain 代码**）
2. `_DERIVED_TABLES` 这个常量名（Task 6 已从三张扩到五张，名字里的「派生」不再准确）
3. `daily.py` / `backfill.py` 散文里的「三张派生表」（Task 7 已把 `_replay_cleanup` 扩到五张，**现在过期了**）
4. `test_repo.py` 的「九条 `ck_*`」（Task 6 加了两条 CHECK，Task 7 又加了一条）
5. RST 表的列宽
6. `valid_from` 没有区分测试
7. ⚠️ **这一条是「不要做」**：`weekly_adjustment.factor` 无范围 CHECK 是 **P8-A6 刻意裁定的**（`(0, 2]` 是读模型的语义、不是数据的形状，Plan 03 可能要放宽上界）。**只需把理由写进 docstring（Task 8 已写），不要加 CHECK。** 列在这里只是防止有人以为漏了
8. `repo.delete_by_batch` 的 docstring 里「今天 `_replay_cleanup` 只清三张」
9. `test_backfill.py` 那条 docstring **开头**仍印着 Plan 01 的 `17.98–18.92 s（3.2–3.3× 余量）` 且无时间限定词，而 Task 7 补的实测段在它**下面** → 顺序上先读到过期值

**逐条给结论**：改了 / 为什么不用改 / 改在哪。**第 7 条必须写「刻意不做」并引 P8-A6。**

## 1. 执行强度（账本 Ruling 145）

**目标 1–2 轮 fix round**（Task 6 与 Task 8 用了 0 轮、Task 5 与 Task 7 各 1 轮）。**⚠️ 但本 Task 是 Plan 02 的收尾**，除了代码还要清 9 条散文、回填 2 个 sha256、补 7 项 §14、改 1 个指纹 —— **控制者预期它的评审要与 Task 7 同档。**

**保留（一条不许砍）**：TDD；`app/domain/` 分支覆盖 **100%**；**每一处「跑一次生产、把输出粘进 fixture」的期望值都必须逐条人读确认**（计划原文逐字写着「**不要 blindly 固化**」——Plan 01 的 `reason` 字段就是这么漂移的，Ruling 145/210）；单一所有者；断言两侧不同源；架构守卫全绿；**Plan 01 与 Task 5/6/7/8 的全部既有测试仍全绿**。
**取消**：纯散文精度导致的**额外** fix round（本 Task 就是那一次「一次性清扫」）。**但 Critical 级一律当场修。**

**变异**：本 Task **不要求新的变异**（它主要是 fixture 与散文）。**但要复跑一条既有变异证明尺子没被 fixture 改动弄钝**：控制者建议复跑 Task 7 的变异 ④（删掉 `valid_to` 的 `-1 day`），因为它与黄金用例的 `valid_to` 期望值直接相关。按硬规矩 #83 的 `.pyc` 纪律做。

## 2. 硬约束

1. **`app/domain/` 无任何 I/O**（本 Task 只改 `assembler.py` 的注释，但纪律照旧）。实测 `ALLOWED_MODULES = {dataclasses, enum, collections, collections.abc, numpy, typing}`。
2. **`app/domain/` 分支覆盖 100%**（`Miss 0 / BrPart 0`），基线 **996 / 288**。
3. **单一所有者**：P9-A1 的整个理由就是它（不给夹具加第二份身高体重）。
4. **断言两侧不得同源**：期望值字面写在测试/fixture 里（硬规矩 #35）。
5. **TDD**：能先写测试的先写测试。**⚠️ 但「跑一次生产把输出粘进 fixture」这一步是例外**——它本质是固化实测值，故**必须逐条人读确认**并在报告里给出「我读了哪几条、怎么确认的」。
6. **禁区**：`backend/pe.db`（不得存在）、`backend/data/seed/`（0 文件）。`backend/data/` 里**只许改 `exercises.yaml`**（P9-A3），**CSV 与 `exercise_equivalence.yaml` 与 18 套模板 YAML 一个字节都不许动**。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**（会写前两个禁区）；要数据集就在 python 里 `build_dataset(cfg)`。
7. **PowerShell**：`;` 分隔；不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑写临时 `.py`。**所有写文件走 python**（`Add-Content` 会静默写坏中文；`golden_cases.json` 与 spec 都是中文密集文件）。
8. **`git add` 按文件名逐个加**。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。**不要 push。**
9. **数键/字段/成员/表格行一律用运行时口径**（`len(dict)` / `len(dataclasses.fields(...))` / `len(list(...columns))` / 数换行 + 校验首尾两行），**绝不用正则数源码**（硬规矩 #89）。**⚠️ 硬规矩 #93 就是为这一条立的**：控制者本次用正则数 spec §14 的行，正则漏了加粗编号的 18–31 行，数出 17 而实为 30，**差点把一条真的自洽的编号体系报成 Critical**。这是该族错误的**第 4 次**（#139 跨行元组 / #147 大写键 / #153 `read_text()` 换行 / #155 加粗编号）。
10. **数行尾/字节数用 `read_bytes()`，不用 `read_text()`**（Python 通用换行会把 `\r\n` 翻成 `\n`，#89 的扩写）。

## 3. ⚠️ 若你认为简报/计划某条决定是错的，**顶回来**

Plan 02 到目前为止实现者顶回控制者 **23 次，23 次都是对的**。最近 2 次（账本 Ruling 154）：「派单要求的那条 tie-breaker 测试在 SQLite 上**结构上不可能变红**（`INTEGER PRIMARY KEY` = rowid 别名，全表扫描恒按 rowid 升序），照字面写只会得到一条恒绿的假守卫」、「派单的字面 `7` 会造出第二个住址」。
**⚠️ 本 Task 尤其要顶回来**：控制者在预检里已经犯了 #155（用正则数出假的 §14 项数），而 P9-A2 的更正本身也是控制者第二次实测的结果 —— **若你实测到第三个数，你的数优先。**
顶回时：① 不要静默偏离；② 在报告的「关切」节写明「哪条决定、为什么错、你的替代方案、代价」；③ 若能同时给两个版本，先实现你认为对的那个。

## 4. 报告

写进 `task-9-report.md`。⚠️ **必须用 python 写**（`write_bytes` 一次性，或 `open(..., "a", encoding="utf-8", newline="")` 追加），**不要用 Write/SearchReplace 工具反复改它**（IDE 曾把陈旧且截断的缓存写回磁盘、永久丢了约 107 KB）。

至少 8 节：① 环境与基线复现；② **13 例的新 `expected` 字段逐例列表 + 「我怎么人读确认的」**（这是本 Task 的核心交付，计划原文要求「不要 blindly 固化」）；③ P9-A1 的 `_from_golden_cases` 改动与那条守卫的契约变化；④ **P9-A3 的指纹程序六步的逐步取证**（含三个指纹的实测值与 CRLF 计数）；⑤ spec 的 §14 七项与勘误各处（逐处给「原文 → 更正 → 理由 → 编号」）；⑥ 9 条待清扫的逐条结论；⑦ 变异复跑 + 最终验收（passed 数 793 → ?、覆盖率四格、`__all__`、扫描面、表数、`git diff -- backend/data` 只含 `exercises.yaml`）；⑧ commit sha + 关切 + 没按派单做的地方（0 处也要写「0 处」）。

## 5. 交回控制者

最终回复里给出（**简洁，不要贴大段代码**）：
1. commit sha 与各自一句话说明
2. passed 数（793 → ?）与带 `--cov` 的四格（996/0/288/0 → ?）
3. **`EXERCISES_FINGERPRINT` 的旧值与新值**，另两个指纹是否逐字不变，`exercises.yaml` 的 CRLF 计数
4. **spec §14 的最终行数与最大编号**（用「数换行 + 校验首尾两行」的口径，**不要用正则抽编号**）
5. 13 例里**几例有处方、几例断言「无处方」**，以及 `needs_review` / `safety_substitutions` 在几例里**真的非空**（这是 P9-A1 的验收点）
6. 9 条待清扫的逐条结论（改了 / 为什么不用改）
7. 复跑的那条变异的结论
8. `__all__`（51，应不变）、扫描面（35，应不变）、表数（18，应不变）
9. **你顶回控制者的地方**
10. **你没按派单做的地方**（0 处也要写「0 处」）
11. 报告的字节数与行数

---


# 实施计划 02：智能处方引擎

> **For agentic workers:** REQUIRED SUB-SKILL: 用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务实施本计划。步骤用 checkbox（`- [ ]`）语法便于跟踪。

**Goal:** 把 Plan 01 产出的红黄绿分层结果，按「层 × 主导短板 × 体成分」装配成可复现、可审校、可被教师覆盖的 4 周运动处方，并接进每日批处理管道。

**Architecture:** `app/domain/prescription/` 是无 I/O 的纯函数叶子层（匹配、强度换算、装配、安全后置、覆盖、触发判定），模板与动作等价映射是 `backend/data/` 下带版本号的静态 YAML（体育专家可独立审校），`app/pipeline/prescription_stage.py` 负责落库与幂等。处方**不每天重发**——只有 spec §5.2 的五个触发条件之一成立时才生成，而分层重算仍然每天跑。

**Tech Stack:** Python 3.11.1、SQLAlchemy 2.1、SQLite（`PRAGMA foreign_keys=ON`）、PyYAML、pytest + pytest-cov。不引入新依赖。

**Spec:** `Document/2026-09-28-体育闭环原型-设计spec.md` —— 本计划实现 **§4.4（处方数据模型）、§5.2（五个触发条件）、§7.1–7.5（智能处方层全部）、§8.4（骨架 + 周微调两层拆分）、§11.2（B 类算法降级）、§12（`domain/` 100% 分支覆盖 + 黄金用例延伸到训练包）**。

**上游状态（Plan 01 已交付，commit `1355541`）：** `453 passed / 0 failed`、`app/domain/` 分支覆盖 **100%**（392 stmts / 112 branch）、14 张表、13 例黄金用例、500 人 ×112 业务日整学期回放 28.4–34.0 s。**执行账本**：`.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md`（234 条裁定、47 条硬规矩，**gitignore 不入库**）。本计划的每个 Task 都受那 47 条硬规矩约束，其中对本计划最要命的十条见 Global Constraints。

---

---

## ⚠️ Task 重编号对照表（2026-10-08 用户裁定后）

用户裁定「后端算法层面要求不是很高，够产出合理的 4 周训练包即可」，故原 Task 5/6/7/8 合并、原 Task 12 砍掉性能压测。本计划从 **12 个 Task 变成 9 个**：

| 原编号 | 新编号 | 处置 |
|---|---|---|
| Task 1–4 | Task 1–4 | 不变（**已全部结案**，HEAD `dfa7580`，592 passed） |
| Task 5 `intensity.py` | **Task 5 的 5.1** | 合并；砍掉 FOX 公式与 `HrmaxFormula` 枚举 |
| Task 6 `assembler.py` | **Task 5 的 5.2** | 合并；砍掉三档系数的 10 组穷举矩阵 |
| Task 7 `safety.py` | **Task 5 的 5.3** | 合并；**安全关键的决定一条没砍** |
| Task 8 `override.py` | **Task 5 的 5.4** | 合并；砍掉五种 kind 的穷举边界 |
| Task 9 两张表 + 五触发 | **Task 6** | 保留，原文不动 |
| Task 10 接入管道 | **Task 7** | 保留，原文不动 |
| Task 11 本周训练单读模型 | **Task 8** | 保留，原文不动 |
| Task 12 黄金用例 + 性能 + 勘误 | **Task 9** | 保留，**删掉 p95 性能压测**（Step 2） |

**⚠️ 已结案的 Task 1–4 正文里的交叉引用未逐条重写**（用户同日裁定「砍文档精度」）。读那四节时若撞到 `Task 5`–`Task 12` 的字样，一律按上表折算；其中「**Task 7 只需写入 `prescription_count`**」（Task 1 节）、「若你判断某一项该推到 Task 5」（Task 4 节）、以及 Task 2/3 节里指向 `safety.py` 与 §14 清单的四处已就地更正；**其余保持原样、按上表折算**。

**同日裁定的执行强度调整**（记进账本作为正式裁定）：**保留** TDD、`app/domain/` 分支覆盖 100%、安全关键路径的变异测试、每个 Task 一轮评审、控制者预检扫描；**取消**「纯散文精度导致的 fix round」（注释里某个数字与实测不符不再单独开一轮，攒到 Task 9 一次性清扫）与「控制者对每个数字的独立复跑」。目标：每个 Task 从 3–6 轮往返降到 **1–2 轮**。

## Global Constraints

- **`app/domain/` 无任何 I/O**：不得 import `sqlalchemy` / `fastapi` / `requests` / `httpx` / `pydantic_settings` / `random`；不得出现 `datetime.now` / `date.today` / `time.time` / `open(`；不得出现 `read_csv` / `read_text` / `Path(` / `__file__` / `json.load` / `os.listdir` / `import os`。**时间与随机数一律由调用方注入**，参考表一律由 `app/refdata.py` 加载后**作为参数传入**。守卫是 `tests/architecture/test_domain_purity.py`（Task 1 会把它从 deny-list 改成 allow-list）。
- **`app/domain/` 分支覆盖 100%**（spec §12）。验收命令**必须带 `--cov-branch`**：`cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing` → `Miss 0 / BrPart 0`。
- **单一所有者**：任何常量/词表/权重只允许有一个住址。Plan 01 为此立过 6 条裁定（Ruling 35/36/63/152/156/190）。本计划新增的 `ITEM_BUCKET` 消费、模板维度词表、`impact_level` 词表、`exercise_ref` 词表都必须指向唯一所有者，且**各有一条漂移测试**。
- **断言两侧不得同源**（硬规矩 #35）：期望值一律**字面写在测试里**，不从被测常量读回来跟自己比。Plan 01 因此吃过三次亏（Ruling 166/186/216-M3）。
- **散文必须带口径**（硬规矩 #19/#20/#25/#29/#36/#39/#43）：注释与 docstring 里出现的每个数字都要能指到产生它的那条命令；每个因果机制都要附 `文件:行 + 引文`；尺寸/时长/速率必须带单位与进制、带 n 与区间；**不得印未经多样本验证的概率模型**；凡写下测量条件，必须同时写「哪条测试会在它失效时变红」，写不出来就标「历史实测，不被守卫」。
- **行号一律取 shell 口径**（硬规矩 #30/#37）：`Read` 工具的行号在本仓**不可靠，且不是一个可以补偿的固定偏移**——Plan 02 Task 1 fix round 4 实测偏移 **0 / −1 / −2 在不同区段并存**，且**同一行内容两次调用分别被标 449 和 450**（对自己都不自洽），报出的文件总行数也偏小（`task-1-report.md` 在 fix round 4 落笔当时：`Read` 报 1031 行、实为 2616 个 LF 行；**该文件持续增长，这是一时点样本、不是稳定量**）。此前已四次误导，故一律不用。行号引用绑定 commit。
- **PowerShell**：分隔用 `;`，不支持 `&&`/`||`；**没有 heredoc**；**反引号会被吃掉**；`python -c` 里字符串一律用单引号，需要双引号就写临时 `.py`（放 `$env:TEMP`）。**所有写文件走 python**（`Add-Content` 静默写坏中文）。commit 信息用 python 写 UTF-8 临时文件 + `git commit -F`。
- **落盘唯一权威是 shell**；**`git checkout` / `git switch` / `git merge` 会按 `core.autocrlf` 重写工作树**（硬规矩 #46），事后必须复核所有「按字节哈希」的断言。`backend/data/` 已由 `.gitattributes` 钉为 `eol=lf`，**本计划新增的 YAML 必须落进同一条规则**。
- **禁区**：`backend/pe.db`（不得存在）、`backend/data/seed/`（0 文件）、`backend/data/national_standard_2014.csv`（sha256[:16] 恒为 `D2C8E539E2FA0029`，由指纹测试守卫）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**（会写前两个禁区）；要数据集就在 python 里 `build_dataset(cfg)`，要落 CSV 就 `write_csv(ds, <临时目录>)`。
- **`app/seed/` 自 Plan 01 结案后重新冻结**（Task 1 的依赖迁移会动它一次，见 Task 1 的解冻范围，之后不再动）。

## Review Focus

spec 是愿景文档：它说系统必须做什么，没说它会遇到什么。下面五类输入/状态是 spec **没有覆盖**、而一个真实使用者最可能撞上的，每类都在拥有该代码的 Task 里补了测试：

1. **模板 YAML 被专家改坏**（少一个键、`week_deltas` 长度与 `microcycle_weeks` 不符、`exercise_ref` 指向不存在的动作、`reachable: true` 但维度组合不可达）→ 必须在**加载时**响亮失败并指出是哪个文件哪一行，而不是在装配到某个学生时才炸。归属 Task 3。
2. **同一个学生在同一天被两次触发**（管道重跑、或教师手动请求与自动触发撞上）→ 必须产出一条处方而不是两条，且第二次是幂等的 no-op 或明确的 `replaced`。归属 Task 6。
3. **学生当天没有分层结果**（`valid_count < 4` → `insufficient_data`，Z0 闸门拦下）→ **不得生成处方**，且必须留下可交代的痕迹（不是静默跳过）。Plan 01 实测缺省注入下 500 人有 2 人落这一档。归属 Task 6。
4. **年龄缺失或异常**（`Student.birth` 为空、或算出年龄 ≤ 0 / ≥ 100）→ Tanaka 公式会给出荒谬的 HRmax（如 `208 − 0.7×0 = 208`），进而给出危险的目标心率区间。必须响亮拒绝或降级到 `needs_review`，**不得静默装配**。归属 Task 5（5.1）。
5. **安全规则命中但 `exercise_equivalence.yaml` 里找不到等价动作**（spec §7.4 明写「不静默跳过」）→ 处方状态置 `needs_review`、写 `warning` 日志、教师端标记「需人工复核」。这是 spec 唯一一处显式要求「宁可不自动，也不要自动错」的地方，必须有测试钉住**它没有被静默跳过**。归属 Task 5（5.3）。

---

## File Structure

**新建（生产）**

| 路径 | 职责 |
|---|---|
| `backend/app/config.py` | `DEFAULT_DB_URL` / `DEFAULT_CSV_DIR` 的唯一所有者（从 `app/seed/generate.py` 迁入，Task 1） |
| `backend/app/adapters/factory.py` | `build_adapter(kind, **kw) -> DataSourceAdapter`，CLI 与将来的 FastAPI 依赖注入共同消费（Task 1） |
| `backend/app/domain/prescription/__init__.py` | 公开面重导出 |
| `backend/app/domain/prescription/exercises.py` | **动作库的值对象**：`ImpactLevel` / `ExerciseSpec` / `EquivalenceMapping` / `EquivalenceTable`；**不读盘**（Ruling 96：与 `app/domain/tables.py` 的 `StandardTable` 同构——值类型住 domain、加载器住 domain 外、加载器 import 值类型） |
| `backend/app/domain/prescription/templates.py` | 模板的**数据结构**（`@dataclass(frozen=True)`）与维度词表；**不读盘**（`ImpactLevel` 自 Ruling 96 起住在 `exercises.py`，本模块按 domain 内部依赖方向 import 或 re-export） |
| `backend/app/domain/prescription/match.py` | 层 × 主导短板 × 体成分 → 模板（含 `reachable` 与 `review.status` 判定） |
| `backend/app/domain/prescription/intensity.py` | HRmax 与目标心率区间（**简化版只实现 Tanaka**，见 Task 5 的 5.1） |
| `backend/app/domain/prescription/assembler.py` | spec §7.3 的六步装配（Task 5 的 5.2） |
| `backend/app/domain/prescription/safety.py` | spec §7.4 的三触发后置处理 + 等价动作替换（Task 5 的 5.3） |
| `backend/app/domain/prescription/override.py` | spec §7.5 的教师覆盖叠加（Task 5 的 5.4） |
| `backend/app/domain/prescription/triggers.py` | spec §5.2 的五触发条件求值 |
| `backend/app/domain/prescription/weekly.py` | spec §8.4 的「本周训练单 = 骨架第 N 周 × 系数」 |
| `backend/app/refdata_prescription.py` | 加载 **`exercises.yaml`（Task 2）**、18 套模板 YAML（Task 3）与 `exercise_equivalence.yaml`，**校验后**交给 domain（domain 不读盘）；并持有 `sync_exercises(session)`（Ruling 89/P2-A1：不接进 `app/seed/`） |
| `backend/app/pipeline/prescription_stage.py` | 落库、幂等、`prescription_count` 计数 |
| `backend/data/prescription/*.yaml` | 18 套模板，一套一文件，体育专家可独立审校 |
| `backend/data/exercise_equivalence.yaml` | 低冲击等价动作映射 + **版本号** |
| `backend/data/exercises.yaml` | 动作库的**源**（`exercise` 表由它 seed，理由见 Task 2） |

**新建（测试）**：`backend/tests/domain/test_prescription_{templates,match,intensity,assembler,safety,override,triggers,weekly}.py`、`backend/tests/test_refdata_prescription.py`、`backend/tests/pipeline/test_prescription_stage.py`、`backend/tests/architecture/test_layering.py`

**修改**：`backend/app/db/models.py`（Task 1 拆包 + 4 张新表 + `daily_sync_run` 两列 + 索引）、`backend/app/pipeline/daily.py`（接入处方阶段）、`backend/app/pipeline/{daily,backfill}.py`（改用 `app.config` 与适配器工厂）、`backend/tests/integration/test_golden_cases.py`（黄金用例延伸到训练包）、`Document/…设计spec.md`（§14 补 4 项、§7.2 补 speed_flexibility 空洞的勘误）

**`models.py` 拆包**（终审 C 组第 23 项）：Plan 02 加 4 张表、Plan 03 还要加 7 张，届时约 25 张 / 70 KB。Task 1 把 `models.py` 拆成 `models/{organisation,assessment,derived,prescription,feedback,ops}.py` + `models/__init__.py` 重导出，**保持 `from app.db import models` 与 `models.X` 的既有写法不变**（`test_all_fourteen_tables_created` 的 `==` 断言同步改成「按 Plan 递增的期望值」，Ruling 28 的意图不变）。

---

---

## Task 9: 黄金用例延伸 + spec 勘误（**不做性能压测**）

### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `9e46abe`，取证脚本 `t9_probes/_t9_probe{1,2}.py`）

**测试基线**：`793 passed`；`app/domain/` **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**；**18 张表**；`__all__` **51**；扫描面 **35**。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P9-A1** | **Critical** | **P7-A2 那条「必须给 13 例追加两个输入字段 `height_cm` 与 `weight_kg`」是错的**——它们**已经在夹具里**，只是**嵌在 `input[i]["curr"]` 与 `["prev"]` 两个子映射里**（13 例全有，实测逐例确认），**不在顶层**。`_meta.bmi` 还逐字写着「**BMI 不在 input 里**：它由身高体重合成，口径与生成器逐字一致——`bmi = round(weight_kg / (height_cm / 100) ** 2, 1)`」。而 `run_stratify.py` 里算 BMI **得分**的那一行本来就是从 `raw.get("height_cm")` / `raw.get("weight_kg")` 读的（`raw` 就是 `curr`）。 | **不给夹具加顶层副本**（那是**第二个住址**，违反 Global Constraint #3，且与 `_meta.bmi` 明写的设计意图相反）。**改成让 `_from_golden_cases` 从 `case["curr"]` 读这两个值。** ⚠️ **连带：Task 7 留下的那条守卫 `test_golden_case_path_defaults_the_three_new_inputs_to_none` 的断言会变成假的**（`bmi` 不再是 `None`）——**它不是「被删掉的守卫」，而是「处置变了、契约跟着变」**：改成钉「`snapshot_muscle_p10` 仍是 `None`（13 人 < MIN_SAMPLE=30，肌肉量组不产出行）而 `height_cm`/`weight_kg` 来自 `curr`」，并把 `bmi` 的期望值改成**逐例实算**的字面值。**⚠️ 这条改动会让 13 例的 `input_snapshot` 从「`bmi` 全 `None`」变成「各有其值」，故 spec §7.4 的三档安全触发第一次在黄金用例里真的可达。** |
| **P9-A2** | **Critical** | **控制者错误 #155**：预检探针用 `^\|\s*(\d+)\s*\|` 这个正则去数 spec §14 的行，**只匹配到未加粗的 1–17**，而 **18–31 行写作 `\| **18** \|`（编号加粗）** → 数出「最大 17、共 17 项」，据此准备把「计划一路写的 27 → 34 项」报成 Critical。**实测真相**：§14 在 spec 的 `:935-:975`，行号 **1–29 与 31**（**共 30 行**），**最大编号 31**，且 **`#30` 是一个刻意留的空洞**——`:972` 逐字写着「**⚠️ 编号 #30 与本表之间有一个刻意的空洞**：#29 与 #31 由 Plan 02 **Task 3** 写入……而 **#30 / #32 / #33 / #34** 留给计划 Task 12 Step 3 的清单」。 | ① **计划的「27 → 34」两个数都错**：实测**起点是 30 行 / 最大编号 31**。② **Task 9 要补的是 7 项：#30（填补那个空洞）+ #32 / #33 / #34 + 三个后来才发现的 #35（addon 量口径与「提高抗阻比重」的处置，P5-A3）/ #36（`weekly_volume` 的基准量口径，P5-A1）/ #37（spec §5.2 只看标签的空洞，Task 6 关切 2）**。③ **补完之后 §14 = 37 行、最大编号 37、无空洞**。④ **`:972` 那段「刻意的空洞」的说明必须一并删掉或改写**（空洞被填了，说明就成了假的）。⑤ **本条同时更正「计划完成后的状态」那节的「spec §14 从 27 项扩到 34 项」**。 |
| **P9-A3** | **Critical** | **`exercises.yaml` 的头注释里明写「⚠️ 这一条**尚未登记进 spec §14**：Task 2 只被授权追加第 28 项（`volume_reduction` 系数），而计划 02 的 Task 12 Step 3 那份 §14 补项清单里……」**（实测在该文件的头注释区，另有一处在 `:124` 写着「已按 Plan02 账本 P2-A3 登记进 spec §14 第 28 项」）。Task 9 一旦把 #30（动作库的视频源）写进 §14，**那句「尚未登记」就变成假的**。 | **本 Task 要改 `backend/data/exercises.yaml` 的头注释** —— ⚠️⚠️ **这是 Plan 02 第一次动一个被指纹钉住的文件**：`EXERCISES_FINGERPRINT` 实测是 `3DE598AF38631209`，改一个字节就要**同步 `tests/test_refdata_prescription.py` 里那个常量**。程序：① 先算新指纹（`sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16].upper()`）；② 改 YAML；③ **立刻用 `read_bytes()` 复核 `CRLF 计数仍为 0`**（`.gitattributes` 给 `backend/data/*.yaml` 钉了 `text eol=lf`，写成 CRLF 会让指纹与 `git ls-files --eol` 双双对不上）；④ 改常量；⑤ 跑那条指纹测试确认绿。**⚠️ 不许用 `git checkout` 还原**（`core.autocrlf=true` 会按属性重写工作树，硬规矩 #46/#70）。 |
| P9-A4 | Important | 黄金用例测试实测**只有 1 条**断言标签的测试（`test_golden_cases_match_expected_labels`），另 3 条是 500 人分布测试（`test_target_layer_distribution_within_tolerance` / `test_trend_agrees_with_the_generator_oracle_on_the_decidable_subset` / `test_trend_discrepancies_vanish_without_outlier_injection`）。夹具形状是**顶层 `{_meta, input, expected}`、`input` 与 `expected` 各是长度 13 的 list、按顺序一一对应**（`_meta.input_schema.student_id` 逐字写着「结果按 input 顺序一一对应 expected」）。 | **新加一条 `test_golden_cases_reach_the_training_package`（13 例参数化），不动既有那条**。理由：既有那条守的是 Plan 01 的「标签」那一环，把训练包的断言塞进去会让它红的时候**分不清是哪一环断了**（硬规矩 #56：主语要写清）。⚠️ **`expected` 是 list 不是 dict** → 新字段要**逐例按顺序**加，加错一格就整条错位，而那**不会报错、只会让 13 例的期望值集体张冠李戴**。要有一条守卫断言 `[c["student_id"] for c in input] == [c["student_id"] for c in expected]`（若今天没有，本 Task 加）。 |
| P9-A5 | Important | `golden_cases.json` 的 `_meta` 里有 **3 处 Plan-01 时代的陈旧 Task 编号**：`_meta.purpose` 的「GC13，**Task 10** Step 0.7 补」、`_meta.expected_from` 的「这也是 **Task 10** 的 `stratify_dataset(list)` 应当走的链路」、`_meta.input_schema.snapshot_muscle_p20` 的「**Task 10** 已落地它的生产者」。 | **Plan 02 重编号后已经没有 Task 10 了**（原 Task 10 是新 Task 7），故这三处在今天的语境下会被读成 Plan 02 的 Task。改成「**Plan 01 的 Task 10**」以消歧。⚠️ 这会改 `golden_cases.json` 的字节 → 但它**不被指纹钉住**（实测 `tests/` 下没有任何断言比对它的 sha256），故只需复核 JSON 仍能 `json.loads` 且例数仍 13 |
| P9-A6 | Important | `_meta.percentile_note` 逐字写着「故本夹具此前印的「**28 行**」已过期，现在是 **24 行**」——**夹具自己已经做过一次「散文过期」的自我更正**。 | **照它的格式办**：本 Task 若发现 `_meta` 里还有别的过期数字，**就地更正并注明是哪个 commit 改的**，不要另起一节。这也是 Ruling 145「待清扫一次性清完」的落点 |
| P9-A7 | Minor | 待清扫清单第 1 条（Task 8 报的）实测确认在 `assembler.py` 里，原文逐字是「按课再除一次才是单课量（**Task 8 的「本周训练单」读模型要自己决定怎么摊**）」。而 **Task 8 的决定是「不摊」**（缩放只是 `weekly_volume × factor`，没有跨 block 的摊销）。 | 那句注释现在指向一个**与它暗示相反的决定** → 改成「Task 8 的读模型**不摊**：缩放只是 `weekly_volume × factor`，`sessions_per_week` 是骨架的结构属性、不参与缩放（P8-A1）」 |
| P9-A8 | Minor | 计划 Task 9 的 Step 3 仍写「新增的 `app/domain/prescription/` **八个**模块全部纳入」（实测命中 1 处），而实际是 **9 个实质模块**（`exercises` / `templates` / `match` / `intensity` / `assembler` / `safety` / `override` / `triggers` / `weekly`）+ 包 `__init__.py`。「计划完成后的状态」那节在 Ruling 146 已改对，**这一句漏改**。 | 改成「**9 个实质模块**」并逐个列名。**⚠️ 控制者自查**：Ruling 146 那次更正**只改了一处、漏了这一处**，而当时我在账本里写的是「已同步」——与 #151 同族（把「打算改全」讲成「已经改全」） |

**⚠️ 本 Task 的三条「第一次」**（都要格外小心）：
1. **第一次动被指纹钉住的 `backend/data/` 文件**（P9-A3）—— 前 8 个 Task 一个字节都没动过。
2. **第一次改 Plan 01 的黄金用例夹具**（`golden_cases.json`）—— 它是 spec §12 的唯一可执行判据。
3. **第一次改 spec 正文**（前 8 个 Task 只改计划与账本）—— 而 spec 是**需求文档**，改它等于改契约，**每一处都要按 Plan 01 的勘误格式**（原文 + 更正 + 理由 + Ruling/§14 编号）。

**扫描面**：本 Task **不新增文件**，扫描面仍 **35**。


**Files:** Modify `backend/tests/fixtures/golden_cases.json`、`backend/tests/integration/test_golden_cases.py`、`Document/…设计spec.md`、**`backend/app/pipeline/run_stratify.py`（`_from_golden_cases` 从 `case["curr"]` 读身高体重；P9-A1）**、**`backend/tests/pipeline/test_prescription_stage.py`（Task 7 那条守卫的契约跟着变；P9-A1）**、**⚠️ `backend/data/exercises.yaml`（头注释里那句「尚未登记进 spec §14」会变成假的；P9-A3）**、**⚠️ `backend/tests/test_refdata_prescription.py`（`EXERCISES_FINGERPRINT` 要跟着改；P9-A3）**、**`backend/app/domain/prescription/assembler.py`（待清扫第 1 条；P9-A7）**

**spec §12 的要求**：黄金用例「断言完整链路：原始值 → 国标得分 → 百分位 → 短板 → 标签 → **模板 → 训练包**」。Plan 01 做到了「标签」，本 Task 把它延伸到「训练包」。

- [ ] **Step 1: 13 例黄金用例延伸到训练包**

对 13 例里的**每一例**（`insufficient_data` 那例除外，它应当断言「无处方」）追加 `expected` 字段：`template_id`、`match_status`、**`label_at_generation`（fix round 1 的 F1-1 追加，取舍见下面那条 ⚠️）**、`weeks[0].sessions[0].blocks[0].exercise_ref`、`hr_zone`（若该 block 是 `hrmax_pct`）、`weekly_volume`（第 1 周）、`needs_review`。

⚠️ **这些期望值怎么来**：**跑一次生产、把输出粘进 fixture，然后逐条人读确认每个数字是对的**——Plan 01 的 `reason` 字段就是这么漂移的（Ruling 145），而 Ruling 210 那次「编造的机制」也是这么进源码的。**不要 blindly 固化。** 特别是 `weekly_volume`：它依赖 Task 5（5.2）那个「spec 没给口径」的三档系数，人读时要确认档位选对了。

⚠️ **P7-A2 的连带 —— ⛔ 已被 P9-A1 撤回（控制者错误 #155 的同一次预检里查出的）**：原文这里要求「给 13 例追加两个输入字段 `height_cm` 与 `weight_kg`」，**而这两个字段已经在夹具里**（嵌在 `input[i]["curr"]` 与 `["prev"]` 两个子映射里，13 例全有），且 `_meta.bmi` 逐字写着「**BMI 不在 input 里**：它由身高体重合成」——**加顶层副本就是第二个住址**（Global Constraint #3），与夹具明写的设计意图相反。**正确做法见 P9-A1：改 `_from_golden_cases` 从 `case["curr"]` 读。**下面那段的**诊断仍然成立**（Task 7 之后黄金用例路径的 `"bmi"` 确实全是 `None`、安全触发确实一档都走不到），**只是修法错了**。理由：Task 7 的 `run_stratify` 黄金用例路径对这两个字段用的是 `case.get(...)`（缺省 `None`，因为 Task 7 不许改本 fixture），故 Task 7 之后 13 例的快照里 `"bmi"` 全是 `None` → **spec §7.4 的三档安全触发在黄金用例里一档都走不到**，而本 Task 要断言的 `needs_review` 与 `safety_substitutions` 因此恒为假绿。**补值的方法**：从生成器 `app.seed.fitness._anthropometrics` 的口径反推（它也算到 1 位小数），或直接给每例一组能让 BMI 落在想要的档位上的身高体重，**并在 `_meta` 里写明每例的 BMI 与它命中的触发**。⚠️ 补完之后 `bmi_of(height_cm, weight_kg)` 的结果要与该例既有的 `score_bmi` **档位一致**（否则同一例的输入自相矛盾），这条一致性要有测试。

⚠️ **`label_at_generation` 要不要进 13 例的 `expected`？决定：要**（fix round 1 交回控制者、控制者倾向「要」，Task 7 的实现者**同意并给出边界**）。它是 `prescription.label_at_generation` 那一列——触发 2 判据的**唯一输入**、F1-1 新加——而 Task 9 是**最后一个能钉住它的地方**。⚠️ 但必须写清它钉得住什么、钉不住什么，否则就是一条看起来强、其实弱的守卫（硬规矩 #39 的反面）：
* **钉得住**：处方行上那一列填的是**当天分层结果的那一个标签**，且与黄金用例里已逐条人读确认的 `expected.label` **逐字相等**（两侧不同源：一侧是 fixture 的字面量、一侧是库里的列）。抓的是「填错了来源」——填成 `dominant_bucket`、填成昨天的标签、或压根忘了填（NOT NULL 会在写侧炸，但 fixture 侧的相等断言才把「填的是哪一个」钉住）。
* **钉不住**：**触发 2 本身**——黄金用例是**单日**的，而触发 2 要两天。故本条**不是** Task 7 那条 `test_trigger_2_survives_the_deletion_of_that_days_stratification_row` 的替代，两条**并列**。
* ⚠️ **`insufficient_data` 那一例没有处方**（Z0 闸门），故 13 例里只有 **12** 例能断言它（与 `template_id` / `needs_review` 同一档处置）。
* ⚠️ 对**已匹配**的处方，`label_at_generation` 与 `template_ref` 的前三字符（`RED` / `YEL` / `GRN`）**恒等**——匹配器就是按 `Layer(label)` 选模板的。故它与 `template_id` **不是两份独立的证据**；它多出来的那一份价值是「与 `expected.label` 这个**已人读的字面量**同源比对」，而不是「多一个字段」。**别把它写成两条互相印证的守卫。**

⚠️ **GC09 的脆性会传导**：Plan 01 记录 GC09 的六项得分**恰好全在国标 P25 线上**（margin 全 0.0），常模上移 1 分它就 W=6、由绿翻红。本 Task 给它加 `template_id` 期望后，**换常模会让它的模板也从绿层跳到红层**——这是**期望行为**，但要写进 fixture 的 `_meta`，否则下一个人会以为是回归。

- [ ] **Step 2: ~~性能验收~~ —— 本计划不做（用户裁定 2026-10-08）**

> 原文这里是「spec §1.3 单人处方生成 p95 < 3 秒」的压测（n=500、量 min/p50/p95/max、并合并报告 500 人整学期回放）。**用户裁定：原型阶段不做性能压测**——本项目的首要目标是「能跑通的管理型原型系统 + 增删改查 + 已有的大数据算法」，不是性能工程。
> 
> **删掉它丢掉了什么**：spec §1.3 的两条量化验收（单人处方 p95 < 3 s、500 人整学期回放 < 60 s）在本计划结束时**处于「未测量」状态**，不是「已达标」。
> **兜底**：Task 7 的全量测试本来就会跑一次整学期回放；若它的墙钟时间相对 Plan 01 的 28.4–34.0 s 出现**数量级**恶化，Task 7 的报告必须写出来。这不是 p95 断言，只是一条量级哨兵。
> **将来要补**：spec §1.3 的勘误（Step 2 最后一条）要写明「本原型未验收」，别让它读起来像已通过。

- [ ] **Step 2: spec 勘误与 §14 补项（⚠️ P9-A2 更正：本 Task 追加 **7 项：#30 / #32 / #33 / #34 / #35 / #36 / #37**）**

⚠️ **P2-A3 的后续更正（Task 2 实现后）**：原文这里是「7 项，#28–#34」。**#28 已被 Task 2 用掉**（`volume_reduction` 两个系数无 spec 出处，见 Task 2 的 P2-A3 裁定：「值在哪一刻被写死就在哪一刻登记」），而原文 #32 正是同一主题（§7.4 的跑量下调系数）——**两项重复**。故本 Task 的清单整体前移一位、并删掉重复的那项：原 #28→**#29**、原 #29→**#30**、原 #30→**#31**、原 #31→**#32**、~~原 #32~~（**删除**，已由 Task 2 的 #28 覆盖）、原 #33→**#33**、原 #34→**#34**。**7 项 − 1 项重复 = 6 项**，而 **⛔ P9-A2：上面这一整段的算术全部作废**（控制者错误 #155 —— 探针用正则数表格行，只匹配到未加粗的 1–17，而 18–31 行写作 `| **18** |`）。**实测真相**：spec §14 在 `:935-:975`，行号 **1–29 与 31**（**共 30 行**），**最大编号 31**，且 **`#30` 是一个刻意留的空洞**（spec 自己在那一段下方逐字写着「⚠️ 编号 #30 与本表之间有一个刻意的空洞：#29 与 #31 由 Plan 02 **Task 3** 写入……而 **#30 / #32 / #33 / #34** 留给计划 Task 12 Step 3 的清单」）。**故本 Task 的正确算术是：起点 30 行 / 最大编号 31 → 追加 7 项（#30 填补空洞 + #32/#33/#34 + #35/#36/#37）→ 终点 37 行 / 最大编号 37 / 无空洞。** ⚠️ **那段「刻意的空洞」的说明必须一并删掉或改写**（空洞被填了，说明就成了假的）。

（Ruling 12 曾把原文的「6 项」更正为「7 项」；Task 2 落地后**又回到 6 项**——但这次是因为**原 #32 与 Task 2 的 #28 重复而被删**，不是数错。「27 → 34」这个总数在两次更正里都成立。）

- §14 补（**#28 已由 Task 2 追加：`volume_reduction` 的两个系数**；**#29 与 #31 已由 Task 3 追加**（**P9-A2 实测坐实：三者都在表里**）——按 P2-A3 立的原则「值在哪一刻被写死就在哪一刻登记」，见 Task 3 的 P3-A3）：**#30** 动作库的视频源（占位 `.invalid` URL；⚠️ Task 2 已把它写进 `exercises.yaml` 的头注释，本项是把它正式登记进 §14）；**#32** §7.3 步骤 3 的个体修正系数三档阈值与性别系数（工程约定）；**#33** §5.2 触发 4「学期末数据刷新」的口径（任何新采集即触发，不限 week16）；**#34** §8.4 同周多调整的合成方式（相乘）；**#35**（P5-A3）附加模块（`addons`）的训练量口径 —— 本原型置 `weekly_volume = 0.0` + `volume_unit = "unspecified"` + 一条 warning，交由教师用 `OverrideKind.VOLUME_SCALE` 覆盖，**并含「提高抗阻模块比重」的处置**（肌肉量 < P10 时追加 `resistance_priority` 模块）；**#36**（P5-A1）`weekly_volume` 的基准量口径 —— `Block.structure` 里没有「量」这个字段，时长类 `work_min × sets`（分钟/课）、次数类 `rounds × reps`（次/课）、**`rest_min` 不计入量**；**#37**（Task 6 关切 2）spec §5.2 的真实空洞 —— 五个触发条件都只看分层标签，而模板匹配还吃 `dominant_bucket`（`W`）与体成分状态（`C`）、这两个每天都重算，故「标签不变但 `W`/`C` 变了 → 该换模板」这一类学生五条一条都不成立，今天全靠触发 4 的工程口径兜住；**须与 #33 绑在一起交代、不分成两项**。
  - ~~§7.4 的跑量下调系数与「提高抗阻比重」的处置~~ —— **本项删除（已并入 #28）**。但「**提高抗阻比重**」的处置（spec §7.4 `:509` 的「并提高抗阻模块比重」，计划 Task 5（5.3）决定「不自动、只提示」）**尚未登记**，故**并进 #28 的「影响面」格里一起交代**，由 Task 5（5.3）落地时确认 #28 的正文已覆盖它；若没覆盖，Task 9 追加为 **#35**。
- ~~§7.2 加勘误：指明 `speed_flexibility` 桶的参数空洞。~~ —— **本项已由 Task 3 完成**（P3-A9 的裁定：写模板的人正是撞见空洞的人，隔 9 个 Task 再补勘误只会让 YAML 注释里的「见 spec §14 第 N 项」长期指向一个不存在的条目）。**⚠️ 且空洞比这一行说的大得多**（Task 3 实现者发现、控制者独立实算坐实）：不只是 `speed_flexibility` 桶，而是**整个黄层与绿层都没有任何强度数值**——18 套模板的 130 个 block 里 **82 个是 `intensity: {type: none}`**，按层统计 `intensity.type` 是 **绿 `{none}`、黄 `{none}`、红 `{hrmax_pct, none, onerm_pct}`**。spec §7.2 `:487` 只给了红层的 `60–70% HRmax` 与 `70% 1RM`，黄层写的是「持续跑+台阶训练」「自重+弹力带抗阻」（**动作名，没有强度**）、绿层写的是「兴趣球类/定向越野/功能性训练」（同样只有动作名）。**故原文那句「黄层按耐力那套的量」引用的是一个不存在的量。**Task 3 已把 6 条勘误写进 spec §7.2，本 Task 只需**复核**它们仍然成立。
- §7.3 加勘误：「耐力国标得分」的口径（`vital_capacity` 与 `distance_run` 两项得分的均值）。
- §4.4 加勘误：`prescription_template` 用 `template_ref`（逻辑 id）而不是「YAML 路径」，理由见 Task 3。
- §4.6 加勘误：`daily_sync_run` 补 `muscle_line_gaps` 列，`error_summary` 不再承载「注意（非错误）」文本。
- **§14 补 #37（Task 6 实现者发现的 spec §5.2 真实空洞）**：五个触发条件**都只看分层标签**（`current_label` vs `label_at_generation`），而模板匹配还吃 `dominant_bucket`（`W`）与体成分状态（`C`）——**这两个每天都重算**。故「标签不变、但 `W` 或 `C` 变了 → 该换模板」这一类学生，**五条触发一条都不成立**，今天全靠触发 4 的工程口径（「任何新采集即刷新」）兜住。**若将来把触发 4 收窄成「只在 week16」，就会真的漏人。**→ 登记 §14 并**与触发 4 的口径（#33）绑在一起交代**，不要分成两项。
- §1.3 加勘误：「单人处方生成 p95 < 3 秒」与「500 人整学期回放 < 60 s」**本原型均未验收**（用户裁定 2026-10-08 删掉性能压测）。勘误要写明「未测量」，**不得**写成「已达标」。
- **§1.3 的 canonical sha256 回填（P7-A6 / Task 7 结案时实测）**：spec `:45` 那一段今天印的是 `fe0a44e052c7946b425515fbaaa78f09e32320917a927cd10c8947aea3abfd8f` 与「行数合计 **882**」，**两处都已过期**。新值（夹具 = 60 人 / `seed=20250828` / 缺省注入 / `D=2025-09-15`，两遍 `run_daily`、`first == second` 成立）：
  - **9 张表**（Plan 01 的 `PIPELINE_TABLES`）= `1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952`，行数合计 **882（未变）**。⚠️ **它变了不是因为扩表**（`prescription` 不在那 9 张里），而是因为 **`c5599db` 给 `input_snapshot` 加了两个键**。
  - **11 张表**（Task 7 之后）= `2b2649add55205e668c40e287f91592c0bcfcd68599d725030a68fc2400456df`，行数合计 **942** = 882 + 60 处方 + 0 调整。
  - ⚠️ **必须保留 spec `:46` 那段历史记录**（终审 B 报的 886 行 / sha `2ef85d79…` / 基线 `728325a` / `percentile_snapshot` 28 行 → Ruling 214 让 BMI 的 4 个组不再产出退化常模行 → 24 行 → 886 → 882）—— **它是「一个修复改变了另一个修复的取证基线」的记录（Ruling 229），删掉就丢了因果链**。新值**追加**在它后面，不要覆盖。
  - ⚠️ **两个值都不被任何守卫钉住**（那条测试断言的是 `first == second`，不是与字面哈希相等）→ 勘误里要写明这一点，否则下一个人会以为改代码会让某条测试变红。

- [ ] **Step 3: 全量 + 覆盖率 + 变异 + Commit**

`pytest -q` 全绿（**期望数自己数**，基线 **793**）；`--cov=app.domain --cov-branch` → **Miss 0 / BrPart 0 / 100%**（**P9-A8 更正：不是「八个模块」，是 9 个实质模块** —— `exercises` / `templates` / `match` / `intensity` / `assembler` / `safety` / `override` / `triggers` / `weekly`，另加包 `__init__.py`；基线 **996 stmts / 288 branch**）；`tests/architecture` 全绿（扫描面 **35**，本 Task 不新增文件）。

- [ ] **Step 4: 待清扫清单（Ruling 145 攒下来的 9 条，本 Task 一次性清完）**

| # | 来自 | 内容 |
|---|---|---|
| 1 | Task 8 | **`assembler.py` 里那句「Task 8 的读模型要自己决定怎么摊」**（P9-A7）—— Task 8 的决定是**不摊**，那句注释指向一个与它暗示相反的决定 |
| 2 | Task 8 | `_DERIVED_TABLES` 这个常量名（Task 6 已从三张扩到五张，名字里的「派生」不再准确） |
| 3 | Task 8 | `daily.py` / `backfill.py` 散文里的「三张派生表」（**Task 6 的实现者刻意没改**，因为当时仍为真；Task 7 已把 `_replay_cleanup` 扩到五张，**现在过期了**） |
| 4 | Task 8 | `test_repo.py` 的「九条 `ck_*`」（Task 6 加了两条 CHECK，Task 7 又加了一条） |
| 5 | Task 8 | RST 表的列宽 |
| 6 | Task 8 | `valid_from` 没有区分测试 |
| 7 | Task 8 | `weekly_adjustment.factor` 无范围 CHECK（**P8-A6：这是刻意的**，只需把理由写进 docstring，**不要加 CHECK**） |
| 8 | Task 7 | `repo.delete_by_batch` 的 docstring 里「今天 `_replay_cleanup` 只清三张」 |
| 9 | Task 7 | `test_backfill.py` 那条 docstring **开头**仍印着 Plan 01 的 `17.98–18.92 s（3.2–3.3× 余量）` 且无时间限定词，而 Task 7 补的实测段在它**下面** → 顺序上先读到过期值 |

⚠️ **第 1 条会改 `assembler.py`（domain 代码）**，故改完必须重跑覆盖率确认仍 **100%**（注释改动不影响 stmts/branch，但要坐实）。⚠️ **第 7 条是「不要做」的一条**——它已经在 P8-A6 里裁定过了，列在这里只是防止有人以为漏了。

---

## 计划完成后的状态

- 表：**18 张**（Plan 01 的 14 + `exercise` / `prescription_template` / `prescription` / `weekly_adjustment`）
- `app/domain/` 分支覆盖仍 **100%**，`app/domain/prescription/` 新增 **9 个实质模块**（`exercises` / `templates` / `match` / `intensity` / `assembler` / `safety` / `override` / `triggers` / `weekly`）+ 包 `__init__.py`
- `backend/data/`：18 套模板 YAML + `exercises.yaml` + `exercise_equivalence.yaml`（都带版本号与指纹测试，都 `eol=lf`）
- spec §14 从 **30 行 / 最大编号 31（`#30` 是刻意留的空洞）** 扩到 **37 行 / 最大编号 37 / 无空洞**（**P9-A2 更正**：原文写「27 项扩到 34 项」，两个数都错——探针用正则数表格行、漏了加粗编号的 18–31 行）
- 500 人整学期回放**含处方生成**的耗时**不做压测**（用户裁定删掉 Task 9 的 Step 2）；Task 7 的全量测试会顺带跑一次，只作**数量级哨兵**（相对 Plan 01 的 28.4–34.0 s）
- 单人处方 p95 **本计划不测量**；spec §1.3 那条验收在计划结束时处于「未测量」状态，由 Task 9 Step 2 在 spec 里写明
- 终审 C 组 11 项架构债**全部清偿**

## 计划边界说明

- **Plan 03 的**（⚠️ **范围已由用户 2026-10-08 扩大**：CRUD API 层从 Plan 04 提前到 Plan 03）：`weekly_adjustment` 的 `auto` 来源（预警触发减量）、`class_session` / `rpe_record` / `training_log` / `mini_test` / `alert` / `notification` / `weekly_class_report` 七张表、§8.1–8.3 的三源采集与预警规则、§8.5 班级周报、**覆盖全部实体的 FastAPI CRUD 层**（学生/教师/班级/学期/体测/体成分/模板/动作库/处方/反馈/预警）、`HttpLePaoAdapter` 落地（含终审 B 数的约 40 条新契约测试）。
- **Plan 04 的**：Vue3 学生端 H5 与教师大屏、spec §9 的全部页面（**`api/` 层已移到 Plan 03**，见上条）。本计划只交付**读模型**（`weekly.py` 的 `WeeklySheet`），不交付 HTTP 端点。
- **本计划不做**：处方模板的自动优化/机器学习、真实视频源、真实 1RM 实测（`onerm_pct` 类 block 的 `intensity_text` 只渲染文字，不换算成绝对重量——**没有 1RM 数据源**，与 HRmax 同理，登记 §14）、`alert_count` 列的写入。
- **依赖顺序（重编号后）**：Task 1 必须先做（它改 schema 与依赖方向，影响后续每个 Task）。Task 2 → 3 → 4 严格串行（动作库 ← 模板 ← 匹配）。**Task 5 依赖 4**（内部 5.1 → 5.2 → 5.3/5.4，其中 5.3 与 5.4 可并行）。**Task 6 依赖 4–5**。Task 7 依赖 6。Task 8 依赖 5.2/5.4 与 6。Task 9 最后。
- **进度**：Task 1–4 已结案（HEAD `dfa7580`，`592 passed`，`app/domain/` 541 stmts / 132 branch / **100%**，16 张表，SQLAlchemy **2.1.3**）。**Task 5–9 未开始。**

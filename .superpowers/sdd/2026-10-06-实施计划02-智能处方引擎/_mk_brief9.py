"""抽 task-9-brief.md：计划头部 + 对照表 + GC + RF + File Structure + Task 9 全节 + 尾部两节。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
OUT = HERE / "task-9-brief.md"

text = PLAN.read_bytes().decode("utf-8")
nl = "\r\n" if "\r\n" in text else "\n"
L = text.split(nl)


def find(prefix, start=0):
    for i in range(start, len(L)):
        if L[i].startswith(prefix):
            return i
    raise AssertionError(f"锚点未找到: {prefix!r}")


i_t1 = find("## Task 1: ")
i_t9 = find("## Task 9: ")
i_end = find("## 计划完成后的状态")
print(f"[plan] bytes={len(text.encode('utf-8'))} lines={len(L)}  t1={i_t1+1} t9={i_t9+1} end={i_end+1}")
assert i_t1 < i_t9 < i_end

DISPATCH = f"""# Task 9 简报 — 黄金用例延伸到训练包 + spec 勘误 + 9 条待清扫（Plan 02 的收尾 Task）

> 本简报由控制者从 `Document/2026-10-06-实施计划02-智能处方引擎.md`（{len(text.encode('utf-8'))} B / {len(L)} 行）按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + 重编号对照表 + Global Constraints + Review Focus + File Structure + **Task 9 全节（含预检更正 P9-A1..A8）** + **「计划完成后的状态」与「计划边界说明」两节**。

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
  **程序（照做，顺序承重）**：① 先算新指纹（`sha256(path.read_bytes().replace(b"\\r\\n", b"\\n")).hexdigest()[:16].upper()`）；② 改 YAML；③ **立刻用 `read_bytes()` 复核 `CRLF` 计数仍为 0**（`.gitattributes` 给 `backend/data/*.yaml` 钉了 `text eol=lf`，写成 CRLF 会让指纹与 `git ls-files --eol` 双双对不上）；④ 改常量；⑤ 跑那条指纹测试确认绿；⑥ 另两个指纹（`D2C8E539E2FA0029` 的 CSV 与 `822CB86A5E998301` 的 `exercise_equivalence.yaml`）**必须逐字不变**，报告里给出三个的实测值。
  **⚠️ 不许用 `git checkout` 还原**（`core.autocrlf=true` 会按属性重写工作树，硬规矩 #46/#70）。要还原就用 python 从 TEMP 备份写回原字节。

## 0.3 其余 5 条（简报的预检总表里有完整实测依据）

- **P9-A4**：黄金用例测试实测**只有 1 条**断言标签（`test_golden_cases_match_expected_labels`），另 3 条是 500 人分布测试。夹具形状 = **顶层 `{{_meta, input, expected}}`、`input` 与 `expected` 各是长度 13 的 list、按顺序一一对应**（`_meta.input_schema.student_id` 逐字写着「结果按 input 顺序一一对应 expected」）。→ **新加一条 `test_golden_cases_reach_the_training_package`（13 例参数化），不动既有那条**（既有那条守 Plan 01 的「标签」那一环，混在一起红的时候分不清是哪一环断了，硬规矩 #56）。⚠️ **`expected` 是 list 不是 dict** → 新字段要**逐例按顺序**加，**加错一格不会报错、只会让 13 例的期望值集体张冠李戴**。要有一条守卫断言 `[c["student_id"] for c in input] == [c["student_id"] for c in expected]`（若今天没有，本 Task 加）。
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

1. **`app/domain/` 无任何 I/O**（本 Task 只改 `assembler.py` 的注释，但纪律照旧）。实测 `ALLOWED_MODULES = {{dataclasses, enum, collections, collections.abc, numpy, typing}}`。
2. **`app/domain/` 分支覆盖 100%**（`Miss 0 / BrPart 0`），基线 **996 / 288**。
3. **单一所有者**：P9-A1 的整个理由就是它（不给夹具加第二份身高体重）。
4. **断言两侧不得同源**：期望值字面写在测试/fixture 里（硬规矩 #35）。
5. **TDD**：能先写测试的先写测试。**⚠️ 但「跑一次生产把输出粘进 fixture」这一步是例外**——它本质是固化实测值，故**必须逐条人读确认**并在报告里给出「我读了哪几条、怎么确认的」。
6. **禁区**：`backend/pe.db`（不得存在）、`backend/data/seed/`（0 文件）。`backend/data/` 里**只许改 `exercises.yaml`**（P9-A3），**CSV 与 `exercise_equivalence.yaml` 与 18 套模板 YAML 一个字节都不许动**。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**（会写前两个禁区）；要数据集就在 python 里 `build_dataset(cfg)`。
7. **PowerShell**：`;` 分隔；不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑写临时 `.py`。**所有写文件走 python**（`Add-Content` 会静默写坏中文；`golden_cases.json` 与 spec 都是中文密集文件）。
8. **`git add` 按文件名逐个加**。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。**不要 push。**
9. **数键/字段/成员/表格行一律用运行时口径**（`len(dict)` / `len(dataclasses.fields(...))` / `len(list(...columns))` / 数换行 + 校验首尾两行），**绝不用正则数源码**（硬规矩 #89）。**⚠️ 硬规矩 #93 就是为这一条立的**：控制者本次用正则数 spec §14 的行，正则漏了加粗编号的 18–31 行，数出 17 而实为 30，**差点把一条真的自洽的编号体系报成 Critical**。这是该族错误的**第 4 次**（#139 跨行元组 / #147 大写键 / #153 `read_text()` 换行 / #155 加粗编号）。
10. **数行尾/字节数用 `read_bytes()`，不用 `read_text()`**（Python 通用换行会把 `\\r\\n` 翻成 `\\n`，#89 的扩写）。

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

"""

parts = [
    DISPATCH,
    nl.join(L[0:i_t1]).rstrip(),
    "",
    "---",
    "",
    nl.join(L[i_t9:]).rstrip(),   # Task 9 + 尾部两节，一直到文件末
    "",
]
body = nl.join(parts)
if nl != "\n":
    body = body.replace("\r\n", "\n").replace("\n", nl)
OUT.write_bytes(body.encode("utf-8"))
chk = OUT.read_bytes().decode("utf-8")
print(f"[out] {OUT.name}  bytes={len(chk.encode('utf-8'))} lines={chk.count(nl)}")
for probe in ("P9-A1", "P9-A3", "P9-A8", "## Task 9:", "## Global Constraints",
              "## 计划完成后的状态", "## 计划边界说明", "1f043f2a", "EXERCISES_FINGERPRINT",
              "待清扫", "#37"):
    print(f"  含 {probe!r}: {chk.count(probe)}")
for bad in ("## Task 8:", "## Task 1:"):
    print(f"  不含 {bad!r}: {chk.count(bad) == 0}")

"""Task 9 预检更正（P9-A1..A8）+ 账本 Ruling 155 + 硬规矩 #89 的第 4 次违反记录。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
LEDGER = HERE / "progress.md"
edits = []


def patch(path, pairs):
    raw = path.read_bytes()
    t = raw.decode("utf-8")
    nl = "\r\n" if "\r\n" in t else "\n"
    b0 = (len(raw), t.count(nl))
    for old, new, count, label in pairs:
        if nl != "\n":
            old = old.replace("\r\n", "\n").replace("\n", nl)
            new = new.replace("\r\n", "\n").replace("\n", nl)
        n = t.count(old)
        assert n == count, f"[{label}] 期望 {count}，实为 {n}\n  old={old[:90]!r}"
        t = t.replace(old, new)
        edits.append((label, n))
    path.write_bytes(t.encode("utf-8"))
    c = path.read_bytes().decode("utf-8")
    print(f"[{path.name}] {b0[0]} B / {b0[1]} 行 -> {len(c.encode('utf-8'))} B / {c.count(nl)} 行 "
          f"CRLF={c.count(chr(13)+chr(10))} LF={c.count(chr(10))}")


PRE = """
### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `9e46abe`，取证脚本 `t9_probes/_t9_probe{1,2}.py`）

**测试基线**：`793 passed`；`app/domain/` **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**；**18 张表**；`__all__` **51**；扫描面 **35**。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P9-A1** | **Critical** | **P7-A2 那条「必须给 13 例追加两个输入字段 `height_cm` 与 `weight_kg`」是错的**——它们**已经在夹具里**，只是**嵌在 `input[i]["curr"]` 与 `["prev"]` 两个子映射里**（13 例全有，实测逐例确认），**不在顶层**。`_meta.bmi` 还逐字写着「**BMI 不在 input 里**：它由身高体重合成，口径与生成器逐字一致——`bmi = round(weight_kg / (height_cm / 100) ** 2, 1)`」。而 `run_stratify.py` 里算 BMI **得分**的那一行本来就是从 `raw.get("height_cm")` / `raw.get("weight_kg")` 读的（`raw` 就是 `curr`）。 | **不给夹具加顶层副本**（那是**第二个住址**，违反 Global Constraint #3，且与 `_meta.bmi` 明写的设计意图相反）。**改成让 `_from_golden_cases` 从 `case["curr"]` 读这两个值。** ⚠️ **连带：Task 7 留下的那条守卫 `test_golden_case_path_defaults_the_three_new_inputs_to_none` 的断言会变成假的**（`bmi` 不再是 `None`）——**它不是「被删掉的守卫」，而是「处置变了、契约跟着变」**：改成钉「`snapshot_muscle_p10` 仍是 `None`（13 人 < MIN_SAMPLE=30，肌肉量组不产出行）而 `height_cm`/`weight_kg` 来自 `curr`」，并把 `bmi` 的期望值改成**逐例实算**的字面值。**⚠️ 这条改动会让 13 例的 `input_snapshot` 从「`bmi` 全 `None`」变成「各有其值」，故 spec §7.4 的三档安全触发第一次在黄金用例里真的可达。** |
| **P9-A2** | **Critical** | **控制者错误 #155**：预检探针用 `^\\|\\s*(\\d+)\\s*\\|` 这个正则去数 spec §14 的行，**只匹配到未加粗的 1–17**，而 **18–31 行写作 `\\| **18** \\|`（编号加粗）** → 数出「最大 17、共 17 项」，据此准备把「计划一路写的 27 → 34 项」报成 Critical。**实测真相**：§14 在 spec 的 `:935-:975`，行号 **1–29 与 31**（**共 30 行**），**最大编号 31**，且 **`#30` 是一个刻意留的空洞**——`:972` 逐字写着「**⚠️ 编号 #30 与本表之间有一个刻意的空洞**：#29 与 #31 由 Plan 02 **Task 3** 写入……而 **#30 / #32 / #33 / #34** 留给计划 Task 12 Step 3 的清单」。 | ① **计划的「27 → 34」两个数都错**：实测**起点是 30 行 / 最大编号 31**。② **Task 9 要补的是 7 项：#30（填补那个空洞）+ #32 / #33 / #34 + 三个后来才发现的 #35（addon 量口径与「提高抗阻比重」的处置，P5-A3）/ #36（`weekly_volume` 的基准量口径，P5-A1）/ #37（spec §5.2 只看标签的空洞，Task 6 关切 2）**。③ **补完之后 §14 = 37 行、最大编号 37、无空洞**。④ **`:972` 那段「刻意的空洞」的说明必须一并删掉或改写**（空洞被填了，说明就成了假的）。⑤ **本条同时更正「计划完成后的状态」那节的「spec §14 从 27 项扩到 34 项」**。 |
| **P9-A3** | **Critical** | **`exercises.yaml` 的头注释里明写「⚠️ 这一条**尚未登记进 spec §14**：Task 2 只被授权追加第 28 项（`volume_reduction` 系数），而计划 02 的 Task 12 Step 3 那份 §14 补项清单里……」**（实测在该文件的头注释区，另有一处在 `:124` 写着「已按 Plan02 账本 P2-A3 登记进 spec §14 第 28 项」）。Task 9 一旦把 #30（动作库的视频源）写进 §14，**那句「尚未登记」就变成假的**。 | **本 Task 要改 `backend/data/exercises.yaml` 的头注释** —— ⚠️⚠️ **这是 Plan 02 第一次动一个被指纹钉住的文件**：`EXERCISES_FINGERPRINT` 实测是 `3DE598AF38631209`，改一个字节就要**同步 `tests/test_refdata_prescription.py` 里那个常量**。程序：① 先算新指纹（`sha256(path.read_bytes().replace(b"\\r\\n", b"\\n")).hexdigest()[:16].upper()`）；② 改 YAML；③ **立刻用 `read_bytes()` 复核 `CRLF 计数仍为 0`**（`.gitattributes` 给 `backend/data/*.yaml` 钉了 `text eol=lf`，写成 CRLF 会让指纹与 `git ls-files --eol` 双双对不上）；④ 改常量；⑤ 跑那条指纹测试确认绿。**⚠️ 不许用 `git checkout` 还原**（`core.autocrlf=true` 会按属性重写工作树，硬规矩 #46/#70）。 |
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

"""

patch(PLAN, [
    ("## Task 9: 黄金用例延伸 + spec 勘误（**不做性能压测**）\n\n**Files:**",
     "## Task 9: 黄金用例延伸 + spec 勘误（**不做性能压测**）\n" + PRE + "\n**Files:**",
     1, "P9 插入预检更正总表"),

    # Files 行（P9-A3 要改 exercises.yaml）
    ("**Files:** Modify `backend/tests/fixtures/golden_cases.json`、`backend/tests/integration/test_golden_cases.py`、`Document/…设计spec.md`",
     "**Files:** Modify `backend/tests/fixtures/golden_cases.json`、`backend/tests/integration/test_golden_cases.py`、"
     "`Document/…设计spec.md`、**`backend/app/pipeline/run_stratify.py`（`_from_golden_cases` 从 `case[\"curr\"]` 读身高体重；P9-A1）**、"
     "**`backend/tests/pipeline/test_prescription_stage.py`（Task 7 那条守卫的契约跟着变；P9-A1）**、"
     "**⚠️ `backend/data/exercises.yaml`（头注释里那句「尚未登记进 spec §14」会变成假的；P9-A3）**、"
     "**⚠️ `backend/tests/test_refdata_prescription.py`（`EXERCISES_FINGERPRINT` 要跟着改；P9-A3）**、"
     "**`backend/app/domain/prescription/assembler.py`（待清扫第 1 条；P9-A7）**",
     1, "P9-A1/A3/A7 Files 行"),

    # P7-A2 那条连带（P9-A1 撤回它）
    ("⚠️ **P7-A2 的连带（Task 7 预检时按硬规矩 #86 当场补进来）**：本 Task 除了给每例追加 `expected` 字段，"
     "**还必须给 13 例追加两个输入字段 `height_cm` 与 `weight_kg`**。",
     "⚠️ **P7-A2 的连带 —— ⛔ 已被 P9-A1 撤回（控制者错误 #155 的同一次预检里查出的）**："
     "原文这里要求「给 13 例追加两个输入字段 `height_cm` 与 `weight_kg`」，**而这两个字段已经在夹具里**"
     "（嵌在 `input[i][\"curr\"]` 与 `[\"prev\"]` 两个子映射里，13 例全有），"
     "且 `_meta.bmi` 逐字写着「**BMI 不在 input 里**：它由身高体重合成」——**加顶层副本就是第二个住址**"
     "（Global Constraint #3），与夹具明写的设计意图相反。**正确做法见 P9-A1：改 `_from_golden_cases` 从 `case[\"curr\"]` 读。**"
     "下面那段的**诊断仍然成立**（Task 7 之后黄金用例路径的 `\"bmi\"` 确实全是 `None`、安全触发确实一档都走不到），"
     "**只是修法错了**。",
     1, "P9-A1 撤回 P7-A2 的修法"),

    # §14 的编号（P9-A2）
    ("- [ ] **Step 2: spec 勘误与 §14 补项（本 Task 追加 **4 项：#30 / #32 / #33 / #34**）**",
     "- [ ] **Step 2: spec 勘误与 §14 补项（⚠️ P9-A2 更正：本 Task 追加 **7 项：#30 / #32 / #33 / #34 / #35 / #36 / #37**）**",
     1, "P9-A2 Step 2 标题"),

    ("§14 总数仍是 `27 + 1（Task 2）+ 6（本 Task）= **34**`，与「计划完成后的状态」那段的「27 → 34」**恰好一致**"
     "（那个数字本来就是对的，只是分配方式变了）。",
     "**⛔ P9-A2：上面这一整段的算术全部作废**（控制者错误 #155 —— 探针用正则数表格行，"
     "只匹配到未加粗的 1–17，而 18–31 行写作 `| **18** |`）。**实测真相**：spec §14 在 `:935-:975`，"
     "行号 **1–29 与 31**（**共 30 行**），**最大编号 31**，且 **`#30` 是一个刻意留的空洞**"
     "（spec 自己在那一段下方逐字写着「⚠️ 编号 #30 与本表之间有一个刻意的空洞：#29 与 #31 由 Plan 02 **Task 3** 写入……"
     "而 **#30 / #32 / #33 / #34** 留给计划 Task 12 Step 3 的清单」）。"
     "**故本 Task 的正确算术是：起点 30 行 / 最大编号 31 → 追加 7 项（#30 填补空洞 + #32/#33/#34 + #35/#36/#37）"
     "→ 终点 37 行 / 最大编号 37 / 无空洞。** ⚠️ **那段「刻意的空洞」的说明必须一并删掉或改写**（空洞被填了，说明就成了假的）。",
     1, "P9-A2 作废旧算术"),

    ("- §14 补（**#28 已由 Task 2 追加：`volume_reduction` 的两个系数**；**#29 与 #31 已由 Task 3 追加**",
     "- §14 补（**#28 已由 Task 2 追加：`volume_reduction` 的两个系数**；**#29 与 #31 已由 Task 3 追加**（**P9-A2 实测坐实：三者都在表里**）",
     1, "P9-A2 坐实 28/29/31"),

    ("**#34** §8.4 同周多调整的合成方式（相乘）。",
     "**#34** §8.4 同周多调整的合成方式（相乘）；"
     "**#35**（P5-A3）附加模块（`addons`）的训练量口径 —— 本原型置 `weekly_volume = 0.0` + "
     "`volume_unit = \"unspecified\"` + 一条 warning，交由教师用 `OverrideKind.VOLUME_SCALE` 覆盖，"
     "**并含「提高抗阻模块比重」的处置**（肌肉量 < P10 时追加 `resistance_priority` 模块）；"
     "**#36**（P5-A1）`weekly_volume` 的基准量口径 —— `Block.structure` 里没有「量」这个字段，"
     "时长类 `work_min × sets`（分钟/课）、次数类 `rounds × reps`（次/课）、**`rest_min` 不计入量**；"
     "**#37**（Task 6 关切 2）spec §5.2 的真实空洞 —— 五个触发条件都只看分层标签，"
     "而模板匹配还吃 `dominant_bucket`（`W`）与体成分状态（`C`）、这两个每天都重算，"
     "故「标签不变但 `W`/`C` 变了 → 该换模板」这一类学生五条一条都不成立，今天全靠触发 4 的工程口径兜住；"
     "**须与 #33 绑在一起交代、不分成两项**。",
     1, "P9-A2 补 #35/#36/#37"),

    # §1.3 的 sha256 回填（Task 7 结案时算出的两个新值）
    ("- §1.3 加勘误：「单人处方生成 p95 < 3 秒」与「500 人整学期回放 < 60 s」**本原型均未验收**"
     "（用户裁定 2026-10-08 删掉性能压测）。勘误要写明「未测量」，**不得**写成「已达标」。",
     "- §1.3 加勘误：「单人处方生成 p95 < 3 秒」与「500 人整学期回放 < 60 s」**本原型均未验收**"
     "（用户裁定 2026-10-08 删掉性能压测）。勘误要写明「未测量」，**不得**写成「已达标」。\n"
     "- **§1.3 的 canonical sha256 回填（P7-A6 / Task 7 结案时实测）**：spec `:45` 那一段今天印的是 "
     "`fe0a44e052c7946b425515fbaaa78f09e32320917a927cd10c8947aea3abfd8f` 与「行数合计 **882**」，"
     "**两处都已过期**。新值（夹具 = 60 人 / `seed=20250828` / 缺省注入 / `D=2025-09-15`，两遍 `run_daily`、`first == second` 成立）：\n"
     "  - **9 张表**（Plan 01 的 `PIPELINE_TABLES`）= `1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952`，"
     "行数合计 **882（未变）**。⚠️ **它变了不是因为扩表**（`prescription` 不在那 9 张里），"
     "而是因为 **`c5599db` 给 `input_snapshot` 加了两个键**。\n"
     "  - **11 张表**（Task 7 之后）= `2b2649add55205e668c40e287f91592c0bcfcd68599d725030a68fc2400456df`，"
     "行数合计 **942** = 882 + 60 处方 + 0 调整。\n"
     "  - ⚠️ **必须保留 spec `:46` 那段历史记录**（终审 B 报的 886 行 / sha `2ef85d79…` / 基线 `728325a` / "
     "`percentile_snapshot` 28 行 → Ruling 214 让 BMI 的 4 个组不再产出退化常模行 → 24 行 → 886 → 882）—— "
     "**它是「一个修复改变了另一个修复的取证基线」的记录（Ruling 229），删掉就丢了因果链**。新值**追加**在它后面，不要覆盖。\n"
     "  - ⚠️ **两个值都不被任何守卫钉住**（那条测试断言的是 `first == second`，不是与字面哈希相等）→ 勘误里要写明这一点，"
     "否则下一个人会以为改代码会让某条测试变红。",
     1, "P7-A6 sha256 回填"),

    # 待清扫清单（9 条）+ 八个模块（P9-A8）
    ("`pytest -q` 全绿（**期望数自己数**）；`--cov=app.domain --cov-branch` → **Miss 0 / BrPart 0 / 100%**"
     "（新增的 `app/domain/prescription/` 八个模块全部纳入）；`tests/architecture` 全绿。",
     "`pytest -q` 全绿（**期望数自己数**，基线 **793**）；`--cov=app.domain --cov-branch` → **Miss 0 / BrPart 0 / 100%**"
     "（**P9-A8 更正：不是「八个模块」，是 9 个实质模块** —— `exercises` / `templates` / `match` / `intensity` / "
     "`assembler` / `safety` / `override` / `triggers` / `weekly`，另加包 `__init__.py`；"
     "基线 **996 stmts / 288 branch**）；`tests/architecture` 全绿（扫描面 **35**，本 Task 不新增文件）。\n\n"
     "- [ ] **Step 4: 待清扫清单（Ruling 145 攒下来的 9 条，本 Task 一次性清完）**\n\n"
     "| # | 来自 | 内容 |\n"
     "|---|---|---|\n"
     "| 1 | Task 8 | **`assembler.py` 里那句「Task 8 的读模型要自己决定怎么摊」**（P9-A7）—— Task 8 的决定是**不摊**，"
     "那句注释指向一个与它暗示相反的决定 |\n"
     "| 2 | Task 8 | `_DERIVED_TABLES` 这个常量名（Task 6 已从三张扩到五张，名字里的「派生」不再准确） |\n"
     "| 3 | Task 8 | `daily.py` / `backfill.py` 散文里的「三张派生表」（**Task 6 的实现者刻意没改**，因为当时仍为真；"
     "Task 7 已把 `_replay_cleanup` 扩到五张，**现在过期了**） |\n"
     "| 4 | Task 8 | `test_repo.py` 的「九条 `ck_*`」（Task 6 加了两条 CHECK，Task 7 又加了一条） |\n"
     "| 5 | Task 8 | RST 表的列宽 |\n"
     "| 6 | Task 8 | `valid_from` 没有区分测试 |\n"
     "| 7 | Task 8 | `weekly_adjustment.factor` 无范围 CHECK（**P8-A6：这是刻意的**，只需把理由写进 docstring，"
     "**不要加 CHECK**） |\n"
     "| 8 | Task 7 | `repo.delete_by_batch` 的 docstring 里「今天 `_replay_cleanup` 只清三张」 |\n"
     "| 9 | Task 7 | `test_backfill.py` 那条 docstring **开头**仍印着 Plan 01 的 `17.98–18.92 s（3.2–3.3× 余量）` "
     "且无时间限定词，而 Task 7 补的实测段在它**下面** → 顺序上先读到过期值 |\n\n"
     "⚠️ **第 1 条会改 `assembler.py`（domain 代码）**，故改完必须重跑覆盖率确认仍 **100%**（注释改动不影响 stmts/branch，"
     "但要坐实）。⚠️ **第 7 条是「不要做」的一条**——它已经在 P8-A6 里裁定过了，列在这里只是防止有人以为漏了。",
     1, "P9-A8 + 待清扫清单"),

    # 计划完成后的状态：§14 的数字（P9-A2）
    ("- spec §14 从 27 项扩到 **34 项**",
     "- spec §14 从 **30 行 / 最大编号 31（`#30` 是刻意留的空洞）** 扩到 **37 行 / 最大编号 37 / 无空洞**"
     "（**P9-A2 更正**：原文写「27 项扩到 34 项」，两个数都错——探针用正则数表格行、漏了加粗编号的 18–31 行）",
     1, "P9-A2 尾部数字"),
])

# ============ 账本 ============
lb = LEDGER.read_bytes()
lt = lb.decode("utf-8")
lnl = "\r\n" if "\r\n" in lt else "\n"
print(f"[ledger before] bytes={len(lb)} lines={lt.count(lnl)}")

BODY = """

---

### Task 9: 黄金用例延伸 + spec 勘误 — 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`9e46abe`（Task 8 结案，工作树干净）。**测试基线**：`793 passed`；domain **996/0/288/0/100%**；**18 张表**；`__all__` **51**；扫描面 **35**。
**取证脚本**：`t9_probes/_t9_probe{1,2}.py`（两份入库）。

#### Ruling 155 — 预检查出 3 Critical / 3 Important / 2 Minor，计划正文更正 9 处；**其中一条 Critical 是控制者自己刚写进去的假事实**

| # | 级别 | 实测事实 | 处置 |
|---|---|---|---|
| **P9-A1** | **Critical** | **P7-A2 那条「必须给 13 例追加两个输入字段 `height_cm` 与 `weight_kg`」是假的**——它们**已经在夹具里**，嵌在 `input[i]["curr"]` 与 `["prev"]` 两个子映射里（**13 例逐例确认全有**），**不在顶层**。`_meta.bmi` 还逐字写着「**BMI 不在 input 里**：它由身高体重合成，口径与生成器逐字一致——`bmi = round(weight_kg / (height_cm / 100) ** 2, 1)`」。而 `run_stratify.py` 里算 BMI **得分**的那一行本来就是从 `raw.get("height_cm")` / `raw.get("weight_kg")` 读的（`raw` 就是 `curr`）。 | **不给夹具加顶层副本**（那是**第二个住址**，违反 GC#3，且与 `_meta.bmi` 明写的设计意图相反）。**改成让 `_from_golden_cases` 从 `case["curr"]` 读。** ⚠️ **连带**：Task 7 留下的守卫 `test_golden_case_path_defaults_the_three_new_inputs_to_none` 的断言会变成假的 —— **它不是「被删掉的守卫」，而是「处置变了、契约跟着变」**：改成钉「`snapshot_muscle_p10` 仍是 `None`（13 人 < MIN_SAMPLE=30，肌肉量组不产出行）而 `height_cm`/`weight_kg` 来自 `curr`」，`bmi` 的期望值改成**逐例实算**的字面值。⚠️ 这条改动让 13 例的 `input_snapshot` 从「`bmi` 全 `None`」变成「各有其值」，**spec §7.4 的三档安全触发第一次在黄金用例里真的可达** |
| **P9-A2** | **Critical** | **控制者错误 #155**：预检探针用 `^\\|\\s*(\\d+)\\s*\\|` 去数 spec §14 的行，**只匹配到未加粗的 1–17**，而 **18–31 行写作 `\\| **18** \\|`（编号加粗）** → 数出「最大 17、共 17 项」，据此**准备把「计划一路写的 27 → 34 项」报成 Critical**。**实测真相**：§14 在 spec 的 `:935-:975`，行号 **1–29 与 31**（**共 30 行**），**最大编号 31**，且 **`#30` 是一个刻意留的空洞**——spec 自己在表下方逐字写着「⚠️ 编号 #30 与本表之间有一个刻意的空洞：#29 与 #31 由 Plan 02 **Task 3** 写入……而 **#30 / #32 / #33 / #34** 留给计划 Task 12 Step 3 的清单」。**即：Task 2 的 #28、Task 3 的 #29 与 #31 都真的落进了 spec，计划那套编号是自洽的；只有「27 → 34」这个总数是错的。** | ① **计划的「27 → 34」两个数都错**：实测**起点 30 行 / 最大编号 31**。② Task 9 要补 **7 项**：**#30**（填补空洞）+ **#32 / #33 / #34** + 三个后来才发现的 **#35**（addon 量口径与「提高抗阻比重」的处置，P5-A3）/ **#36**（`weekly_volume` 的基准量口径，P5-A1）/ **#37**（spec §5.2 只看标签的空洞，Task 6 关切 2）。③ 补完 **§14 = 37 行 / 最大编号 37 / 无空洞**。④ **那段「刻意的空洞」的说明必须一并删掉或改写**（空洞被填了，说明就成了假的）。⑤ 同步更正「计划完成后的状态」那节的「27 → 34」 |
| **P9-A3** | **Critical** | `exercises.yaml` 的头注释里明写「⚠️ 这一条**尚未登记进 spec §14**：Task 2 只被授权追加第 28 项（`volume_reduction` 系数），而计划 02 的 Task 12 Step 3 那份 §14 补项清单里……」（另一处在 `:124` 写着「已按 Plan02 账本 P2-A3 登记进 spec §14 第 28 项」）。**Task 9 一旦把 #30（动作库的视频源）写进 §14，那句「尚未登记」就变成假的。** | **本 Task 要改 `backend/data/exercises.yaml` 的头注释** —— ⚠️⚠️ **这是 Plan 02 第一次动一个被指纹钉住的文件**（前 8 个 Task 一个字节都没动过）：`EXERCISES_FINGERPRINT` 实测 `3DE598AF38631209`，改一个字节就要**同步 `tests/test_refdata_prescription.py` 里那个常量**。**程序**：① 先算新指纹（`sha256(path.read_bytes().replace(b"\\r\\n", b"\\n")).hexdigest()[:16].upper()`）；② 改 YAML；③ **立刻用 `read_bytes()` 复核 CRLF 计数仍为 0**（`.gitattributes` 给 `backend/data/*.yaml` 钉了 `text eol=lf`）；④ 改常量；⑤ 跑指纹测试确认绿。**⚠️ 不许用 `git checkout` 还原**（`core.autocrlf=true` 会按属性重写工作树，硬规矩 #46/#70） |
| P9-A4 | Important | 黄金用例测试实测**只有 1 条**断言标签（`test_golden_cases_match_expected_labels`），另 3 条是 500 人分布测试。夹具形状 = **顶层 `{_meta, input, expected}`、`input` 与 `expected` 各是长度 13 的 list、按顺序一一对应**（`_meta.input_schema.student_id` 逐字写着「结果按 input 顺序一一对应 expected」）。 | **新加一条 `test_golden_cases_reach_the_training_package`（13 例参数化），不动既有那条**（既有那条守 Plan 01 的「标签」那一环，混在一起红的时候分不清是哪一环断了，硬规矩 #56）。⚠️ **`expected` 是 list 不是 dict** → 新字段要**逐例按顺序**加，**加错一格不会报错、只会让 13 例的期望值集体张冠李戴**。要有一条守卫断言 `[c["student_id"] for c in input] == [c["student_id"] for c in expected]`（若今天没有，本 Task 加） |
| P9-A5 | Important | `_meta` 里有 **3 处 Plan-01 时代的陈旧 Task 编号**（`_meta.purpose` 的「GC13，**Task 10** Step 0.7 补」、`_meta.expected_from` 的「**Task 10** 的 `stratify_dataset(list)`」、`_meta.input_schema.snapshot_muscle_p20` 的「**Task 10** 已落地它的生产者」）。 | **Plan 02 重编号后已经没有 Task 10 了**（原 Task 10 = 新 Task 7），故这三处在今天的语境下会被读成 Plan 02 的 Task → 改成「**Plan 01 的 Task 10**」以消歧。⚠️ 这会改 `golden_cases.json` 的字节，但它**不被指纹钉住**（实测 `tests/` 下没有任何断言比对它的 sha256），故只需复核 JSON 仍能 `json.loads` 且例数仍 13 |
| P9-A6 | Important | `_meta.percentile_note` 逐字写着「故本夹具此前印的「**28 行**」已过期，现在是 **24 行**」—— **夹具自己已经做过一次「散文过期」的自我更正**。 | **照它的格式办**：本 Task 若发现 `_meta` 里还有别的过期数字，**就地更正并注明是哪个 commit 改的**，不要另起一节。这也是 Ruling 145「待清扫一次性清完」的落点 |
| P9-A7 | Minor | 待清扫第 1 条（Task 8 报的）实测确认在 `assembler.py`，原文逐字是「按课再除一次才是单课量（**Task 8 的「本周训练单」读模型要自己决定怎么摊**）」。而 **Task 8 的决定是「不摊」**。 | 改成「Task 8 的读模型**不摊**：缩放只是 `weekly_volume × factor`，`sessions_per_week` 是骨架的结构属性、不参与缩放（P8-A1）」。⚠️ **这会改 domain 代码文件**，改完必须重跑覆盖率确认仍 100% |
| P9-A8 | Minor | 计划 Task 9 的 Step 3 仍写「新增的 `app/domain/prescription/` **八个**模块全部纳入」（实测命中 1 处），而实际是 **9 个实质模块**。 | 改成「9 个实质模块」并逐个列名。**⚠️ 控制者自查**：Ruling 146 那次更正**只改了「计划完成后的状态」那节、漏了这一处**，而当时账本里写的是「已同步」——**与 #151 同族**（把「打算改全」讲成「已经改全」） |

**⚠️ 本 Task 的三条「第一次」**：① **第一次动被指纹钉住的 `backend/data/` 文件**（P9-A3）；② **第一次改 Plan 01 的黄金用例夹具**（spec §12 的唯一可执行判据）；③ **第一次改 spec 正文**（前 8 个 Task 只改计划与账本）—— 而 spec 是**需求文档**，改它等于改契约，**每一处都要按 Plan 01 的勘误格式**（原文 + 更正 + 理由 + Ruling/§14 编号）。

**待清扫清单已在计划正文里落成一张 9 行的表**（Task 5 的 1 条 + Task 7 的 3 条 + Task 8 的 5 条），其中**第 7 条是「不要做」的一条**（`weekly_adjustment.factor` 无范围 CHECK 是 P8-A6 刻意裁定的，列进去只是防止有人以为漏了）。

**扫描面**：本 Task **不新增文件**，仍 **35**。

**→ 硬规矩 #89 的第 4 次违反（控制者错误 #155）**：#89 立于 Ruling 151，正文是「数键 / 数字段 / 数成员时，一律用运行时口径，绝不用正则去数源码——正则的字符类会静默漏掉它没想到的形状（大写键、跨行元组、注释里的同名词）」。本次是**同一规矩的第 4 次违反**（#139 跨行元组 / #147 大写键 / #153 `read_text()` 换行 / **#155 加粗编号**），**每一次都是「字符类没想到的形状」**。#89 的括号里已经列了三种形状，**这次是第四种**。
**→ 补硬规矩 #93：数 Markdown 表格的行数用「数换行 + 校验首尾两行的内容」，不用正则抽编号；数任何带格式（加粗、斜体、代码围栏）的文本里的项，先把格式剥掉再数。** 依据：#155 —— 一条规矩列了三种例外、第四次撞上第四种，说明**列举例外这个做法本身是错的**，要改成「换一个不依赖形状的方法」。

**计划正文更正**：`_t9_preflight_patch.py`，**9 处替换全部命中 1 次**（硬规矩 #79）。

**下一步**：抽 `task-9-brief.md` → 派实现者。**按 Ruling 145，目标 1–2 轮。⚠️ 本 Task 是 Plan 02 的收尾，除了代码还要清 9 条散文、回填 2 个 sha256、补 7 项 §14、改 1 个指纹——控制者预期它的评审要与 Task 7 同档。**
"""

if lnl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", lnl)
assert "Ruling 155" not in lt, "Ruling 155 已存在"
LEDGER.write_bytes((lt.rstrip("\r\n") + BODY).encode("utf-8"))
c2 = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c2.encode('utf-8'))} lines={c2.count(lnl)} "
      f"CRLF={c2.count(chr(13)+chr(10))} LF={c2.count(chr(10))}")
for k in ("Ruling 155", "硬规矩 #93", "控制者错误 #155", "P9-A1", "P9-A8", "1f043f2a", "2b2649add"):
    print(f"  {k}: {c2.count(k)}")
print(f"\n[edits] {len(edits)} 处：")
for lab, n in edits:
    print(f"  {n}x  {lab}")

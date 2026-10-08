# -*- coding: utf-8 -*-
"""Task 5 fix round 1 的**计划正文**补丁（F1-3 + F1-5 + F1-1/F1-2 的正文对齐）。

纪律（硬规矩 #79）：**每一处替换都先 `assert` 命中次数**，不符就整体不落盘。
写文件一律走 python：`Document/` 下的 md 是**纯 CRLF / 无 BOM**，编辑器工具会引入 CRLF 混乱。

改动清单（10 处）：

=====  ==================================================================
编号    内容
=====  ==================================================================
E1      F1-3：P5-A10 的「更正」列整格重写为「撤回」（控制者错误 #140 + 硬规矩 #82）
E2      F1-3：5.3 正文里被 P5-A10 改坏的 `BODY_FAT_LIMIT` 描述恢复成可核的原文引用
E3      F1-5①：P5-A2 的分布 `{2:24, 3:42, 4:64}` 补明是**按 block 计数加权**
E4      F1-5②：5.5 Step 5 补上 `_OWNED_MODULES` 3→7 与第二句 `assert len(set(names))`
E5      F1-5③：5.3 的 `Consumes` 补列 `Template` / `ExerciseSpec`
E6      F1-5④：5.5 Step 5 补上「带 `--cov` 与不带的 passed 数差 1」的口径
E7      F1-2：P5-A5 的 `rpe` 值域 6–20 → **0–10**、`value=13` → `value=7`
E8      F1-2：Step 1 那条 `value=13` → `value=7`，并补上 F1-2 新增的边界测试名
E9      F1-1：六步口径第 6 步的 `weekly_volume_base` 从 `float` 改成分列的只读 Mapping
E10     两处签名扩参（控制者第 5/6 次采纳）：5.3 的 `apply_safety` 与 5.4 的 `apply_overrides`
=====  ==================================================================

⚠️ E9 与 E10 **不在派单的字面清单里**（派单 F1-5 只列了 4 条），但它们是同一类缺陷：
计划正文与已落地的代码矛盾，Task 6/8 的实现者照抄就会错。已在报告的
「你没按本派单做的地方」里显式列出。
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
assert PLAN.is_file(), f"计划正文不在预期位置：{PLAN}"

# --------------------------------------------------------------------------
# (编号, old 子串, new 子串, 期望命中次数)
# ⚠️ old / new 一律**单行**（不含 \n），因为计划正文是纯 CRLF，跨行替换会踩换行口径。
# --------------------------------------------------------------------------
EDITS = []

# --- E1：P5-A10 的「更正」列整格重写（F1-3）---------------------------------
EDITS.append((
    "E1",
    "| 按硬规矩 #78 改成**可 grep 的原文片段**，不写裸行号；「严格大于」的说法降级为"
    "「与 Plan 01 同口径，由实现者复核引文后写明」 |",
    "| **撤回**。控制者的探针只 grep 了标识符 `BODY_FAT_LIMIT`、没 grep 注释行，于是把"
    "「探针没显示」讲成了「它不存在」。实测 `app/domain/derive.py` 的定义行**上一行**就是"
    "逐字的注释「男 > 20%、女 > 28%，**严格大于**」，故**原计划的行号 `:68-69` 与引文双双"
    "正确**。→ **控制者错误 #140**，与硬规矩 #80 同型第 **9** 次。**→ 补硬规矩 #82：探针"
    "「0 命中」时，必须先用一个已知存在的串验证这条查询本身有效，才允许把「没查到」讲成"
    "「不存在」。**（依据：账本 Ruling 147 的 P5-A13 与本次的 P5-A10 是同一根因的两次发作，"
    "而 #80 只覆盖了「已有字面断言」那一半。） |",
    1,
))

# --- E2：5.3 正文恢复可核的原文引用（F1-3）-----------------------------------
EDITS.append((
    "E2",
    "（`BODY_FAT_LIMIT`，住在 `app/domain/derive.py`，**按可 grep 的原文找、不要按裸行号找**；"
    "P5-A10 实测它是**一行 dict 定义**`BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}` "
    "+ 一处消费，原文写的「`:68-69` 明写严格大于」**行号口径错、引文控制者未核**，"
    "由实现者复核后写明）",
    "（`BODY_FAT_LIMIT`，住在 `app/domain/derive.py`，**按可 grep 的原文找、不要按裸行号找**"
    "——硬规矩 #78 仍成立。可 grep 的原文有三处，**实现者已逐字复核**：① 那**一行 dict "
    "定义** `BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}`；② 它的**唯一消费点** "
    "`body_fat_pct > limit`；③ 定义行**上一行**那句逐字注释「体成分异常 C 的体脂率阈值"
    "（spec §6.3②）：男 > 20%、女 > 28%，**严格大于**」。故**原计划写的「`:68-69` 明写"
    "严格大于」行号与引文双双正确**，P5-A10 的「更正」已撤回（控制者错误 #140））",
    1,
))

# --- E3：P5-A2 的分布口径（F1-5①）-------------------------------------------
EDITS.append((
    "E3",
    "全体 130 个 block 的「一周内出现次数」分布 = **`{2: 24, 3: 42, 4: 64}`**，按层是",
    "全体 130 个 block 的「一周内出现次数」分布 = **`{2: 24, 3: 42, 4: 64}`**"
    "（⚠️ **这个分布是按 block 计数加权的**、不是按模板计数：按 `exercise_ref` 去重是 "
    "`{2: 12, 3: 14, 4: 16}` 共 **42** 个 ref，各乘以自己的 `sessions_per_week` 才得到 "
    "`{2: 24, 3: 42, 4: 64}` 共 **130** 个 block —— fix round 1 / F1-5① 补明），按层是",
    1,
))

# --- E4：5.5 Step 5 的两处漏点（F1-5②）--------------------------------------
EDITS.append((
    "E4",
    "（**新值自己数并字面写死**，同时改同文件里那句 `assert len(...) == 24`）。",
    "（**新值自己数并字面写死**，同时改同文件里那句 `assert len(...) == 24`）。"
    "⚠️ **同一节还有两处必须跟着改，派单原先漏点**（fix round 1 / F1-5② 补明；"
    "**实现者超出派单发现，控制者采纳**）：① `_OWNED_MODULES` 从 **3** 个模块扩到 **7** 个"
    "——那一份的支 5「公开面对 `_OWNED_MODULES` 里各模块的**公有顶层定义**穷尽」只对"
    "**本包拥有**的模块成立，而 Task 5 新建的 `intensity` / `assembler` / `safety` / "
    "`override` 四个都是本包拥有的，不加进去就等于**放弃这四个模块的穷尽守卫**"
    "（谁往 `assembler.py` 加一个公有顶层定义而不重导出，全量测试照样绿）；"
    "② 那句 `assert len(...) == 24` 其实是**两句**——"
    "`assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 43` 与 `assert len(set(names)) == 43`"
    "（后者钉「基线里没有重名」），**两句都要改**：只改前一句的话，一份把同一个名字抄了"
    "两遍的基线仍然全绿。",
    1,
))

# --- E5：5.3 的 Consumes（F1-5③）-------------------------------------------
EDITS.append((
    "E5",
    "**Consumes:** 5.2 的 `TrainingPackage` / `AssembledBlock`、Task 2 的 `EquivalenceTable` "
    "/ `ImpactLevel`",
    "**Consumes:** 5.2 的 `TrainingPackage` / `AssembledBlock`、Task 2 的 `EquivalenceTable` "
    "/ `ImpactLevel` / **`ExerciseSpec`**、Task 3 的 **`Template`**"
    "（⚠️ 后两个是 fix round 1 / F1-5③ 补的：`apply_safety` 的签名已扩参成 "
    "`(pkg, inp, eq, *, template, exercises)`，`Consumes` 要跟上）",
    1,
))

# --- E6：5.5 Step 5 的 --cov 口径（F1-5④）----------------------------------
EDITS.append((
    "E6",
    "- [ ] 全量 `pytest -q` 的 passed 数**自己数**（基线 592，硬规矩 #44：期望值不得照抄派单）。",
    "- [ ] 全量 `pytest -q` 的 passed 数**自己数**（基线 592，硬规矩 #44：期望值不得照抄派单）。"
    "⚠️ **带 `--cov` 与不带的 passed 数差 1**（fix round 1 / F1-5④ 补明，**免得下一个 Task "
    "的实现者以为丢了一条测试**）：不带 `--cov` 是 `N passed`，带 "
    "`--cov=app.domain --cov-branch` 是 `N-1 passed, 1 skipped`。那 **1 个 skip** 是 "
    "`tests/pipeline/test_backfill.py` 里**既有**的墙钟断言——它按硬规矩 #42 在 "
    "`sys.gettrace()` 非空时**主动跳**，而 `pytest-cov` 正是靠 `sys.settrace()` 实现的，"
    "故一开覆盖率它就跳。Task 5 落地时实测：不带 `--cov` **679 passed**、带 `--cov` "
    "**678 passed, 1 skipped**（两个数指的是同一套测试）。",
    1,
))

# --- E7：P5-A5 的 rpe 值域（F1-2）------------------------------------------
EDITS.append((
    "E7",
    "`rpe` 那一档**不可达但必须被覆盖**（domain 分支 100%）→ 用**手工构造**的 "
    "`Intensity(type=\"rpe\", value=13)` 测。`Intensity.value` 的语义随 `type` 变"
    "（`onerm_pct` 是百分比、`rpe` 是 6–20），写进 docstring |",
    "`rpe` 那一档**不可达但必须被覆盖**（domain 分支 100%）→ 用**手工构造**的 "
    "`Intensity(type=\"rpe\", value=7)` 测。`Intensity.value` 的语义随 `type` 变"
    "（`onerm_pct` 是 1RM 的百分比、`rpe` 是 **0–10** 的自觉受累程度），写进 docstring。"
    "⚠️ **本行原先把 `rpe` 的值域写成 Borg 经典的 6–20，那是错的，fix round 1 / F1-2 已更正"
    "为 0–10**（下面一律用「**那套标度**」指被撤回的写法，不再逐字复述，好让「全仓扫该串"
    "应当只剩这一次显式否定」这道闸门可用）：spec 全篇的 RPE 都是 0–10 标度，四处逐字可 "
    "grep——`rpe_record` 表字段「RPE 0–10」、§8.2 小标题「课堂端 RPE（0–10 主观疲劳）」、"
    "`RED_RPE_SUSTAINED`「RPE 连续 ≥ 9 分」、`YELLOW_CLASS_RPE_HIGH`「课堂 RPE 均值 > 7 分」、"
    "大屏异常名单「RPE > 8」；**四处在「那套标度」上都读不通**（「连续 ≥ 9」在那套标度上"
    "只是中高档，在 0–10 上已贴近力竭）。而 `templates.py` 的 `INTENSITY_TYPES` 注释本来就"
    "写着「`rpe` 的出处是 spec §8.2 的课堂快评 RPE 0–10」，故改前的 `assembler.py` "
    "**与它自己的上游矛盾**。**这是跨计划契约**：Plan 03 的实现者若把「9 分」读成那套标度的"
    "中高档，阈值语义整个错位。手工构造的值随之从 `13` 改成 `7`（13 在 0–10 上非法），"
    "并**新增一道 `[0, 10]` 的运行时拒绝**（与 `hr_zone` 那道 `0 <= low <= high <= 100` "
    "对称；加载器只校字段形状、不校值域，故没有它一份 `rpe: 13` 的 YAML 会渲染成学生端的"
    "「RPE 13」——一个看起来完全正常的谎；且可证明不会让任何真仓模板炸，`rpe` 在 18 套里"
    "出现 **0** 次） |",
    1,
))

# --- E8：Step 1 的那条测试名（F1-2）----------------------------------------
EDITS.append((
    "E8",
    "  - `test_rpe_intensity_renders_text_without_an_hr_zone`（**P5-A5**：手工构造 "
    "`Intensity(type=\"rpe\", value=13)`，真仓无此档）",
    "  - `test_rpe_intensity_renders_text_without_an_hr_zone`（**P5-A5**：手工构造 "
    "`Intensity(type=\"rpe\", value=7)`，真仓无此档；⚠️ 原先写的 `value=13` 在 **0–10** "
    "标度上非法，fix round 1 / F1-2 改成 `7`，断言的 `intensity_text` 随之从 `\"RPE 13\"` "
    "改成 `\"RPE 7\"`）\r\n"
    "  - `test_rpe_value_outside_zero_to_ten_is_rejected`（**F1-2 新增**：`rpe` 的值域是"
    "**闭**区间 `[0, 10]`，四个边界值 `-0.1` / `0.0` / `10.0` / `10.1` 各一档）",
    1,
))

# --- E9：六步口径第 6 步的 weekly_volume_base（F1-1）------------------------
EDITS.append((
    "E9",
    "`weekly_volume_base` = **未乘个体系数、未乘 `week_deltas` 的周量总和**（`float`，"
    "`round(…, 1)`）。",
    "`weekly_volume_base` = **未乘个体系数、未乘 `week_deltas` 的周量**，"
    "**按 `volume_unit` 分列**（⚠️ **fix round 1 / F1-1 更正**：原文写的是「周量总和"
    "（`float`，`round(…, 1)`）」，那是**混合量纲**的——`RED-END-ABN-01` 会得到 `168.0` = "
    "`48.0 min + 120.0 reps`，**一个把分钟和次数加在一起的数没有意义**，而它要落进 "
    "`prescription.assembly_snapshot` 这个 JSON 列、并在 Plan 03/04 被前端读出来展示，"
    "与本节 P5-A1 自己立的「两种单位不可通约」互相打脸）。改后是**只读**的 "
    "`Mapping[str, float]`：**键 = 实际出现过的 `volume_unit`**（⚠️ **不要硬写死键集**；"
    "18 套亲扫的键集分布是 `{(\"min\",): 10, (\"reps\",): 6, (\"min\", \"reps\"): 2}`，"
    "即 **16/18 套只有一个单位**；`\"unspecified\"` 一档 **0** 次出现，因为 `assemble` 跑在 "
    "`apply_safety` **之前**、那时还没有 addon block），**值 = 该单位下的周量之和**、"
    "`round(…, 1)`；`RED-END-ABN-01` 逐字面是 `{\"min\": 48.0, \"reps\": 120.0}`"
    "（`min` = 4 课 × `3 × 4`、`reps` = 4 课 × `3 × 10`）。**键数仍是 12**——变的是这一格的"
    "**类型**，键集契约一个字没动。⚠️ **「只读」与「JSON 化」在这里互斥**：`types` 不在 "
    "domain 的 allow-list 里（亲跑：往 `assembler.py` 插一句 `import types`，"
    "`test_domain_imports_stay_within_the_allow_list` 立刻报 offender），而 "
    "`MappingProxyType` 又**不是** `json` 默认可序列化的类型（亲跑抛 "
    "`TypeError: Object of type mappingproxy is not JSON serializable`）→ 落地是一个"
    "**屏蔽了全部 8 个 mutator 的私有 `dict` 子类** `_ReadOnlyVolumeBase`，两条都过"
    "（`isinstance(m, dict)` → `json` 的 C 编码器认它）。故配**四条守卫**：分列字面值 / "
    "键集 ⊆ `VOLUME_UNITS` 且不含 `\"unspecified\"`（18 套）/ 8 个 mutator 全 `TypeError` / "
    "`json.dumps(snap, allow_nan=False)`；`apply_safety` 之后那 **15** 个键另配一条"
    "（那才是 Task 6 真正落库的那一份）。",
    1,
))

# --- E10a：5.3 的 apply_safety 签名（控制者第 5 次采纳）---------------------
EDITS.append((
    "E10a",
    "- `apply_safety(pkg: TrainingPackage, inp: SafetyInput, eq: EquivalenceTable) "
    "-> SafetyOutcome`",
    "- `apply_safety(pkg: TrainingPackage, inp: SafetyInput, eq: EquivalenceTable, "
    "*, template: Template, exercises: Mapping[str, ExerciseSpec]) -> SafetyOutcome`"
    "（⚠️ **两个 keyword-only 形参是 fix round 1 控制者采纳的实现者顶回（第 5 次）**："
    "`TrainingPackage` 里**没有** `addons` / `weekly_frequency`，故 P5-A3 要求的「追加"
    "**模板自己的** `when == \"body_fat_over\"` 的 addon」、addon 的 `exercise_name` / "
    "`video_url` / `impact_level`「从 `exercises[addon.module]` 取」、`sessions_per_week` = "
    "`template.weekly_frequency` 三件事**一件都给不出来**；等价替换同样需要动作库——替身的"
    "名字、URL 与冲击等级只能从 `ExerciseSpec` 取（P5-A8：读**源**、不读模板里的冗余副本）。"
    "三个位置参数与原文逐字一致，新增的两个是 keyword-only，口径照 `assemble` 的 "
    "`*, exercises`）",
    1,
))

# --- E10b：5.4 的 apply_overrides 签名（控制者第 6 次采纳）------------------
EDITS.append((
    "E10b",
    "- `apply_overrides(pkg: TrainingPackage, records: Sequence[OverrideRecord]) "
    "-> TrainingPackage`",
    "- `apply_overrides(pkg: TrainingPackage, records: Sequence[OverrideRecord], "
    "*, exercises: Mapping[str, ExerciseSpec]) -> TrainingPackage`"
    "（⚠️ **keyword-only 的 `exercises` 是 fix round 1 控制者采纳的实现者顶回（第 6 次）**："
    "`SUBSTITUTE_EXERCISE` 若只换 `exercise_ref`，那个 block 会留着**旧动作**的中文名与"
    "视频 URL —— 学生扫码看到的是被换掉的那个动作，那是「一个看起来正常的谎」。"
    "替身的 `name` / `video_url` / `impact_level` 只能从 `ExerciseSpec` 取，与 5.3 同一条"
    "理由（P5-A8））",
    1,
))


def main() -> int:
    raw = PLAN.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "计划正文不该有 BOM"
    text = raw.decode("utf-8")
    crlf_before = text.count("\r\n")
    bare_lf_before = text.count("\n") - crlf_before
    assert bare_lf_before == 0, f"计划正文应为纯 CRLF，实测裸 LF {bare_lf_before} 个"
    lines_before = len(text.split("\r\n"))
    print(f"改前：bytes={len(raw)}  CRLF={crlf_before}  裸LF={bare_lf_before}  "
          f"lines(split)={lines_before}  splitlines={len(text.splitlines())}")

    # F1-2 的扫描闸门：改前计划正文里 `6–20` 恰好 1 处（P5-A5 那一格）、`6-20` 与 `Borg` 0 处。
    # ⚠️ 改后**不是 0**：E7 的更正句里刻意保留了一次「不是 Borg 经典的 6–20」这个**显式否定**，
    # 因为这是一条跨计划契约（Plan 03 的实现者读的就是这一格），显式否定比沉默更能挡住
    # 下一次「改回 Borg」。故闸门写成「改后恰好 1 处，且那一处必须是否定句」。
    TOKENS = ("6\u201320", "6-20", "Borg")
    before_hits = {t: text.count(t) for t in TOKENS}
    print(f"改前的 F1-2 扫描闸门：{before_hits}")
    assert before_hits == {"6\u201320": 1, "6-20": 0, "Borg": 0}, before_hits

    # 第一遍：只 assert 命中次数，不落盘（任何一处不符就整体不动）
    for tag, old, new, want in EDITS:
        got = text.count(old)
        assert got == want, f"{tag}: 命中 {got} 次、期望 {want} 次\n  old 前 80 字：{old[:80]}"
        assert "\n" not in new.replace("\r\n", ""), f"{tag}: new 里混进了裸 LF"
        print(f"{tag:5s} 命中 {got} 次 ✓  （old {len(old)} 字 → new {len(new)} 字）")

    # 第二遍：真替换
    for tag, old, new, _want in EDITS:
        text = text.replace(old, new, 1)

    # 落盘闸门 ①：**替换型**的旧串一律 0 命中（硬规矩 #74 的同一手法）。
    # ⚠️ **追加型**（``old in new``，即新文本以旧文本为子串、只在末尾续写）在这一道上
    #    天然不可能 0 命中——那正是「追加」的定义。它的真闸门是下面第 ④ 道（新标记串恰好
    #    1 处），故这里跳过并**逐条打印**是哪几条追加型，免得「跳过了」变成静默。
    append_type = []
    for tag, old, new, _want in EDITS:
        if old in new:
            append_type.append(tag)
            continue
        assert text.count(old) == 0, f"{tag}: 落盘闸门失败，旧串仍命中 {text.count(old)} 次"
    print(f"追加型（闸门 ① 跳过、由闸门 ④ 接管）= {append_type}")
    # 落盘闸门 ②：F1-2 的三个串各只剩 E7 那一次显式否定
    after_hits = {t: text.count(t) for t in TOKENS}
    print(f"改后的 F1-2 扫描闸门：{after_hits}")
    assert after_hits == {"6\u201320": 1, "6-20": 0, "Borg": 1}, after_hits
    negation = "**本行原先把 `rpe` 的值域写成 Borg 经典的 6–20，那是错的"
    assert text.count(negation) == 1, "那一次命中必须是 E7 的显式否定句"
    # 落盘闸门 ③：5.3 正文里那句自我指控必须 0 命中（E2 删掉的正是它）。
    # ⚠️ 表格里 P5-A10 的**事实列**仍留着「**行号口径错**，且…引文控制者未核」那一句：
    #    派单只要求「把它的『更正』列整格重写」，故事实列一个字没动，改由紧邻的「更正」列
    #    以「**撤回**」开头整格反驳。已在报告的「你没按本派单做的地方 / 观察」里显式列出，
    #    请控制者裁定要不要连事实列一起划掉。
    gone = "**行号口径错、引文控制者未核**"
    assert text.count(gone) == 0, f"落盘闸门失败：{gone!r} 仍命中 {text.count(gone)} 次"
    # 落盘闸门 ④：新串各命中预期的次数（`控制者错误 #140` 刻意出现两次：E1 的撤回格 + E2 的正文）
    for token, want in {
        "**撤回**。控制者的探针只 grep 了标识符": 1,
        "控制者错误 #140": 2,
        "硬规矩 #82": 1,
        "**这个分布是按 block 计数加权的**": 1,
        "`_OWNED_MODULES` 从 **3** 个模块扩到 **7** 个": 1,
        "`assert len(set(names)) == 43`": 1,
        "带 `--cov` 与不带的 passed 数差 1": 1,
        "`rpe` 是 **0–10** 的自觉受累程度": 1,
        "test_rpe_value_outside_zero_to_ten_is_rejected": 1,
        "**按 `volume_unit` 分列**": 1,
        "_ReadOnlyVolumeBase": 1,
        "*, template: Template, exercises: Mapping[str, ExerciseSpec]": 1,
        "（⚠️ **keyword-only 的 `exercises` 是 fix round 1 控制者采纳的实现者顶回（第 6 次）**": 1,
        "（⚠️ **两个 keyword-only 形参是 fix round 1 控制者采纳的实现者顶回（第 5 次）**": 1,
    }.items():
        got = text.count(token)
        assert got == want, f"新串命中 {got} 次、期望 {want}：{token[:60]}"

    out = text.encode("utf-8")
    crlf_after = text.count("\r\n")
    bare_lf_after = text.count("\n") - crlf_after
    assert bare_lf_after == 0, f"改后出现裸 LF {bare_lf_after} 个"
    PLAN.write_bytes(out)

    check = PLAN.read_bytes()
    after = check.decode("utf-8")
    lines_after = len(after.split("\r\n"))
    print()
    print(f"改后：bytes={len(check)}  CRLF={after.count(chr(13) + chr(10))}  "
          f"裸LF={bare_lf_after}  lines(split)={lines_after}  "
          f"splitlines={len(after.splitlines())}")
    print(f"字节增量 = {len(check) - len(raw)} B   行数增量 = {lines_after - lines_before}")
    bom = check.startswith(b"\xef\xbb\xbf")
    print(f"BOM = {bom}")
    assert bom is False
    return 0


if __name__ == "__main__":
    sys.exit(main())

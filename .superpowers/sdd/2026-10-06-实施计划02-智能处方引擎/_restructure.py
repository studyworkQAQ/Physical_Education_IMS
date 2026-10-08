"""重构计划 02：Task 5/6/7/8 合并为新 Task 5，Task 9/10/11/12 顺延为 6/7/8/9。

用法：cd 到仓库根，python <本脚本>
每一步替换都 assert 命中次数，命中数不符就抛异常、不写盘。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
NEW5 = Path(__file__).with_name("_task5_new.md")

raw = PLAN.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
text = raw.decode("utf-8-sig")
nl = "\r\n" if "\r\n" in text else "\n"
print(f"[in] bytes={len(raw)} bom={bom} nl={'CRLF' if nl == chr(13)+chr(10) else 'LF'} "
      f"crlf={text.count(chr(13)+chr(10))} lf={text.count(chr(10))}")

new5 = NEW5.read_bytes().decode("utf-8-sig")
new5 = new5.replace("\r\n", "\n")
if nl != "\n":
    new5 = new5.replace("\n", nl)

edits = []


def sub(old, new, count=1, label=""):
    """精确替换，命中数必须等于 count。old/new 里的 \n 一律折成本文件的实际行尾。"""
    global text
    if nl != "\n":
        old = old.replace("\r\n", "\n").replace("\n", nl)
        new = new.replace("\r\n", "\n").replace("\n", nl)
    n = text.count(old)
    assert n == count, f"[{label}] 期望命中 {count}，实为 {n}: {old[:70]!r}"
    text = text.replace(old, new)
    edits.append((label or old[:40], n))


# ---- 1. 把老 Task 5..8 四节整体换成新的合并节 -------------------------
A = "## Task 5: HRmax 与目标心率区间（`intensity.py`）"
B = "## Task 9: `prescription` / `weekly_adjustment` 表 + 五触发条件（`triggers.py`）"
ia, ib = text.index(A), text.index(B)
assert ia < ib
dropped = text[ia:ib]
print(f"[splice] 删掉 {len(dropped)} 字符 / {dropped.count(nl)} 行（老 Task 5-8）")
text = text[:ia] + new5.rstrip("\r\n") + nl + nl + "---" + nl + nl + text[ib:]
edits.append(("splice Task5-8 -> new Task5", 1))

# ---- 2. 四个标题顺延 -------------------------------------------------
sub("## Task 9: `prescription` / `weekly_adjustment` 表 + 五触发条件（`triggers.py`）",
    "## Task 6: `prescription` / `weekly_adjustment` 表 + 五触发条件（`triggers.py`）",
    1, "heading 9->6")
sub("## Task 10: 处方生成阶段接入管道（`prescription_stage.py`）",
    "## Task 7: 处方生成阶段接入管道（`prescription_stage.py`）",
    1, "heading 10->7")
sub("## Task 11: 「本周训练单」读模型（spec §8.4）",
    "## Task 8: 「本周训练单」读模型（spec §8.4）",
    1, "heading 11->8")
sub("## Task 12: 黄金用例延伸 + 性能验收 + spec 勘误",
    "## Task 9: 黄金用例延伸 + spec 勘误（**不做性能压测**）",
    1, "heading 12->9")

# ---- 3. 剩余各节里的交叉引用 -----------------------------------------
sub("而是 Task 10 的落库幂等", "而是 Task 7 的落库幂等", 1, "xref 10->7 (幂等)")
sub("- Consumes: Task 4–9 全部；", "- Consumes: Task 4–6 全部；", 1, "xref 4-9 -> 4-6")
sub("→ Task 7 的口径是**不触发 + 留痕**",
    "→ Task 5（5.3）的口径是**不触发 + 留痕**", 1, "xref safety 7->5")
sub("Task 9 建的 ORM 表类叫 **`WeeklyAdjustment`**",
    "Task 6 建的 ORM 表类叫 **`WeeklyAdjustment`**", 1, "xref 9->6 (ORM)")
sub("那应该走 Task 8 的 `PAUSE` 覆盖",
    "那应该走 Task 5（5.4）的 `PAUSE` 覆盖", 1, "xref PAUSE 8->5")
sub("与 Task 9 的触发 3 同一口径", "与 Task 6 的触发 3 同一口径", 1, "xref 触发3 9->6")
sub("它依赖 Task 6 那个「spec 没给口径」的三档系数",
    "它依赖 Task 5（5.2）那个「spec 没给口径」的三档系数", 1, "xref 三档 6->5")
sub("计划 Task 7 决定「不自动、只提示」", "计划 Task 5（5.3）决定「不自动、只提示」",
    1, "xref 抗阻 7->5")
sub("由 Task 7 落地时确认 #28 的正文已覆盖它；若没覆盖，Task 7 追加为 **#35**。",
    "由 Task 5（5.3）落地时确认 #28 的正文已覆盖它；若没覆盖，Task 9 追加为 **#35**。",
    1, "xref #35 归属")
sub("归属 Task 9。\n3. **学生当天没有分层结果**", "归属 Task 6。\n3. **学生当天没有分层结果**",
    1, "ReviewFocus 2 归属")
sub("Plan 01 实测缺省注入下 500 人有 2 人落这一档。归属 Task 9。",
    "Plan 01 实测缺省注入下 500 人有 2 人落这一档。归属 Task 6。",
    1, "ReviewFocus 3 归属")
sub("必须有测试钉住**它没有被静默跳过**。归属 Task 7。",
    "必须有测试钉住**它没有被静默跳过**。归属 Task 5（5.3）。",
    1, "ReviewFocus 5 归属")
sub("**不得静默装配**。归属 Task 5。", "**不得静默装配**。归属 Task 5（5.1）。",
    1, "ReviewFocus 4 归属")
sub("**Task 10 只需写入 `prescription_count`**", "**Task 7 只需写入 `prescription_count`**",
    1, "xref Task10 in Task1")
sub("若你判断某一项该推到 Task 5，报为关切",
    "若你判断某一项该推到 Task 5（原文写作时的 Task 5 = 今天的 5.1），报为关切",
    1, "xref Task5 in Task4")
sub("Task 12 Step 3 的清单（计划 `:688`）里", "Task 9（原 Task 12）Step 2 的清单里",
    1, "xref Task12 in Task3 (a)")
sub("**P3-A9：这一项与 Task 12 Step 3 的「spec 勘误」重叠**（计划 `:682`）",
    "**P3-A9：这一项与 Task 9（原 Task 12）Step 2 的「spec 勘误」重叠**",
    1, "xref Task12 in Task3 (b)")

# ---- 4. 删掉新 Task 9 的性能验收 Step 2，Step 3/4 顺延 ---------------
P_START = "- [ ] **Step 2: 性能验收 —— spec §1.3「单人处方生成 p95 < 3 秒」**"
P_END = "- [ ] **Step 3: spec 勘误与 §14 补项"
ps, pe = text.index(P_START), text.index(P_END)
removed = text[ps:pe]
print(f"[perf] 删掉 {len(removed)} 字符 / {removed.count(nl)} 行（p95 性能验收）")
NOTE = (
    "- [ ] **Step 2: ~~性能验收~~ —— 本计划不做（用户裁定 2026-10-08）**" + nl + nl
    + "> 原文这里是「spec §1.3 单人处方生成 p95 < 3 秒」的压测（n=500、量 min/p50/p95/max、"
    + "并合并报告 500 人整学期回放）。**用户裁定：原型阶段不做性能压测**——本项目的首要目标是"
    + "「能跑通的管理型原型系统 + 增删改查 + 已有的大数据算法」，不是性能工程。" + nl
    + "> " + nl
    + "> **删掉它丢掉了什么**：spec §1.3 的两条量化验收（单人处方 p95 < 3 s、500 人整学期回放 < 60 s）"
    + "在本计划结束时**处于「未测量」状态**，不是「已达标」。" + nl
    + "> **兜底**：Task 7 的全量测试本来就会跑一次整学期回放；若它的墙钟时间相对 Plan 01 的 "
    + "28.4–34.0 s 出现**数量级**恶化，Task 7 的报告必须写出来。这不是 p95 断言，只是一条量级哨兵。" + nl
    + "> **将来要补**：spec §1.3 的勘误（Step 2 最后一条）要写明「本原型未验收」，别让它读起来像已通过。" + nl
    + nl
)
text = text[:ps] + NOTE + text[pe:]
edits.append(("delete perf Step2", 1))

sub("- [ ] **Step 3: spec 勘误与 §14 补项", "- [ ] **Step 2: spec 勘误与 §14 补项",
    1, "renumber Step3->2")
sub("- [ ] **Step 4: 全量 + 覆盖率 + 变异 + Commit**",
    "- [ ] **Step 3: 全量 + 覆盖率 + 变异 + Commit**", 1, "renumber Step4->3")
sub("、`backend/tests/pipeline/test_prescription_perf.py`（新建）", "", 1, "drop perf file")
sub("- §1.3 加勘误：「单人处方生成 p95 < 3 秒」的口径（不含 DB 写入，n=500，测量条件）。",
    "- §1.3 加勘误：「单人处方生成 p95 < 3 秒」与「500 人整学期回放 < 60 s」**本原型均未验收**"
    "（用户裁定 2026-10-08 删掉性能压测）。勘误要写明「未测量」，**不得**写成「已达标」。",
    1, "§1.3 勘误改为未验收")

# ---- 5. 头部：Spec 行、File Structure、重编号对照表 -------------------
sub("§11.2（B 类算法降级）、§1.3（单人处方 p95 < 3 秒）、§12",
    "§11.2（B 类算法降级）、§12", 1, "Spec 行删掉 §1.3")
sub("| `backend/app/domain/prescription/intensity.py` | HRmax 与目标心率区间（Tanaka / 220−age 可切换） |",
    "| `backend/app/domain/prescription/intensity.py` | HRmax 与目标心率区间（**简化版只实现 Tanaka**，见 Task 5 的 5.1） |",
    1, "FileStructure intensity")
sub("| `backend/app/domain/prescription/assembler.py` | spec §7.3 的六步装配 |",
    "| `backend/app/domain/prescription/assembler.py` | spec §7.3 的六步装配（Task 5 的 5.2） |",
    1, "FileStructure assembler")
sub("| `backend/app/domain/prescription/safety.py` | spec §7.4 的三触发后置处理 + 等价动作替换 |",
    "| `backend/app/domain/prescription/safety.py` | spec §7.4 的三触发后置处理 + 等价动作替换（Task 5 的 5.3） |",
    1, "FileStructure safety")
sub("| `backend/app/domain/prescription/override.py` | spec §7.5 的教师覆盖叠加 |",
    "| `backend/app/domain/prescription/override.py` | spec §7.5 的教师覆盖叠加（Task 5 的 5.4） |",
    1, "FileStructure override")

TABLE = (
    "---" + nl + nl
    + "## ⚠️ Task 重编号对照表（2026-10-08 用户裁定后）" + nl + nl
    + "用户裁定「后端算法层面要求不是很高，够产出合理的 4 周训练包即可」，故原 Task 5/6/7/8 合并、"
    + "原 Task 12 砍掉性能压测。本计划从 **12 个 Task 变成 9 个**：" + nl + nl
    + "| 原编号 | 新编号 | 处置 |" + nl
    + "|---|---|---|" + nl
    + "| Task 1–4 | Task 1–4 | 不变（**已全部结案**，HEAD `dfa7580`，592 passed） |" + nl
    + "| Task 5 `intensity.py` | **Task 5 的 5.1** | 合并；砍掉 FOX 公式与 `HrmaxFormula` 枚举 |" + nl
    + "| Task 6 `assembler.py` | **Task 5 的 5.2** | 合并；砍掉三档系数的 10 组穷举矩阵 |" + nl
    + "| Task 7 `safety.py` | **Task 5 的 5.3** | 合并；**安全关键的决定一条没砍** |" + nl
    + "| Task 8 `override.py` | **Task 5 的 5.4** | 合并；砍掉五种 kind 的穷举边界 |" + nl
    + "| Task 9 两张表 + 五触发 | **Task 6** | 保留，原文不动 |" + nl
    + "| Task 10 接入管道 | **Task 7** | 保留，原文不动 |" + nl
    + "| Task 11 本周训练单读模型 | **Task 8** | 保留，原文不动 |" + nl
    + "| Task 12 黄金用例 + 性能 + 勘误 | **Task 9** | 保留，**删掉 p95 性能压测**（Step 2） |" + nl
    + nl
    + "**⚠️ 已结案的 Task 1–4 正文里的交叉引用未逐条重写**（用户同日裁定「砍文档精度」）。"
    + "读那四节时若撞到 `Task 5`–`Task 12` 的字样，一律按上表折算；"
    + "其中计划 `:130`（Task 1 节）与 `:378`（Task 4 节）已就地更正，其余保持原样。" + nl
    + nl
    + "**同日裁定的执行强度调整**（记进账本作为正式裁定）：**保留** TDD、`app/domain/` 分支覆盖 100%、"
    + "安全关键路径的变异测试、每个 Task 一轮评审、控制者预检扫描；**取消**「纯散文精度导致的 fix round」"
    + "（注释里某个数字与实测不符不再单独开一轮，攒到 Task 9 一次性清扫）与「控制者对每个数字的独立复跑」。"
    + "目标：每个 Task 从 3–6 轮往返降到 **1–2 轮**。" + nl + nl
)
sub("## Global Constraints", TABLE + "## Global Constraints", 1, "insert 对照表")

# ---- 6. 尾部两节 ----------------------------------------------------
sub("- `app/domain/` 分支覆盖仍 **100%**，新增 8 个模块",
    "- `app/domain/` 分支覆盖仍 **100%**，`app/domain/prescription/` 新增 **9 个实质模块**"
    "（`exercises` / `templates` / `match` / `intensity` / `assembler` / `safety` / `override` / "
    "`triggers` / `weekly`）+ 包 `__init__.py`",
    1, "尾部 模块数")
sub("- 500 人整学期回放**含处方生成**仍在 spec §1.3 的 `< 60 s` 内",
    "- 500 人整学期回放**含处方生成**的耗时**不做压测**（用户裁定删掉 Task 9 的 Step 2）；"
    "Task 7 的全量测试会顺带跑一次，只作**数量级哨兵**（相对 Plan 01 的 28.4–34.0 s）",
    1, "尾部 回放")
sub("- 单人处方 p95 **实测值待 Step 2 量出**（本计划不预设它达标）",
    "- 单人处方 p95 **本计划不测量**；spec §1.3 那条验收在计划结束时处于「未测量」状态，"
    "由 Task 9 Step 2 在 spec 里写明",
    1, "尾部 p95")
sub("- **Plan 03 的**：`weekly_adjustment` 的 `auto` 来源（预警触发减量）、"
    "`class_session` / `rpe_record` / `training_log` / `mini_test` / `alert` / `notification` / "
    "`weekly_class_report` 七张表、§8.1–8.3 的三源采集与预警规则、§8.5 班级周报、"
    "`HttpLePaoAdapter` 落地（含终审 B 数的约 40 条新契约测试）。",
    "- **Plan 03 的**（⚠️ **范围已由用户 2026-10-08 扩大**：CRUD API 层从 Plan 04 提前到 Plan 03）："
    "`weekly_adjustment` 的 `auto` 来源（预警触发减量）、"
    "`class_session` / `rpe_record` / `training_log` / `mini_test` / `alert` / `notification` / "
    "`weekly_class_report` 七张表、§8.1–8.3 的三源采集与预警规则、§8.5 班级周报、"
    "**覆盖全部实体的 FastAPI CRUD 层**（学生/教师/班级/学期/体测/体成分/模板/动作库/处方/反馈/预警）、"
    "`HttpLePaoAdapter` 落地（含终审 B 数的约 40 条新契约测试）。",
    1, "边界 Plan03")
sub("- **Plan 04 的**：FastAPI `api/` 层、`services/`、Vue3 学生端 H5 与教师大屏、spec §9 的全部页面。"
    "本计划只交付**读模型**（`weekly.py` 的 `WeeklySheet`），不交付 HTTP 端点。",
    "- **Plan 04 的**：Vue3 学生端 H5 与教师大屏、spec §9 的全部页面"
    "（**`api/` 层已移到 Plan 03**，见上条）。"
    "本计划只交付**读模型**（`weekly.py` 的 `WeeklySheet`），不交付 HTTP 端点。",
    1, "边界 Plan04")
sub("- **依赖顺序**：Task 1 必须先做（它改 schema 与依赖方向，影响后续每个 Task）。"
    "Task 2 → 3 → 4 严格串行（动作库 ← 模板 ← 匹配）。Task 5/6/7/8 可在 Task 4 之后并行。"
    "Task 9 依赖 4–8。Task 10 依赖 9。Task 11 依赖 6/8/9。Task 12 最后。",
    "- **依赖顺序（重编号后）**：Task 1 必须先做（它改 schema 与依赖方向，影响后续每个 Task）。"
    "Task 2 → 3 → 4 严格串行（动作库 ← 模板 ← 匹配）。**Task 5 依赖 4**"
    "（内部 5.1 → 5.2 → 5.3/5.4，其中 5.3 与 5.4 可并行）。"
    "**Task 6 依赖 4–5**。Task 7 依赖 6。Task 8 依赖 5.2/5.4 与 6。Task 9 最后。" + nl
    + "- **进度**：Task 1–4 已结案（HEAD `dfa7580`，`592 passed`，`app/domain/` "
    "541 stmts / 132 branch / **100%**，16 张表，SQLAlchemy **2.1.3**）。"
    "**Task 5–9 未开始。**",
    1, "边界 依赖顺序")

# ---- 写盘 -----------------------------------------------------------
out = text.encode("utf-8")
if bom:
    out = b"\xef\xbb\xbf" + out
PLAN.write_bytes(out)
print(f"[out] bytes={len(out)} nl={'CRLF' if nl == chr(13)+chr(10) else 'LF'} "
      f"crlf={text.count(chr(13)+chr(10))} lf={text.count(chr(10))} lines={text.count(nl)}")
print(f"[edits] {len(edits)} 处：")
for lab, n in edits:
    print(f"  {n}x  {lab}")

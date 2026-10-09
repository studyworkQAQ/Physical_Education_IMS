"""Plan 03 Task 2 预检更正（P3-A1..A6）+ 账本 Ruling 6。逐条 assert 命中次数（硬规矩 #79）。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-08-实施计划03-反馈预警与CRUD-API层.md"
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
    print(f"[{path.name}] {b0[0]} B / {b0[1]} 行 -> {len(c.encode('utf-8'))} B / {c.count(nl)} 行")


PRE = """
### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `a44968f`，取证脚本 `t2_probes/_preflight.py`）

**测试基线**：`824 passed`；`app/domain/` **996/0/288/0/100%**；**18 张表**；扫描面 **38**（pipeline 8 + db 11 + domain 16 + api 3）。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P3-A1** | **Critical** | **`models/__init__.py` 对 `ops.py` 是 `from .ops import *`（星号导入，实测在该文件的 import 段），而对 `feedback.py` 与 `prescription.py` 是 `from . import feedback, prescription`（非星号）。** 故把 `alert` / `notification` / `weekly_class_report` 三张表放进 `ops.py`，会让 `Alert` / `Notification` / `WeeklyClassReport` **三个类名自动进入 `models` 的公有命名空间** → `assert observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE)` **当场红**，且**唯一的「修法」是把基线从 33 抬到 36——而那正是 Ruling 97 逐字禁止的**（「往基线里加新名字等于把『拆包没改导入面』偷换成『拆包后的现状』，断言两侧就同源了」）。 | **7 张表全部放进 `models/feedback.py`，`ops.py` 一张都不加。** 三个理由：① `feedback.py` 走的是**非星号**导入，7 个类名**自动**留在包的公有面之外，**与 Plan 02 的 `prescription.py` 完全同一个机制**，零新增守卫；② **`feedback.py` 自己的 docstring 已经认领了 `weekly_class_report`** —— 逐字写着「打卡记录、RPE、二次小测、**班级周报（`weekly_class_report`，spec §4.7`）全部属 Plan 03，由它填充**」，即 Plan 02 Task 1 建这个空壳时的意图就是 §4.5–§4.7 全归它；③ spec 的 §4.5/§4.6/§4.7 分节是**文档结构**、不是 Python 模块布局的约束。**⚠️ `feedback.py` 那段「本模块今天刻意是空的」的 docstring 必须整段重写**（否则它会说「这里是空的」而文件里有 7 张表）。 |
| **P3-A2** | **Important** | **`test_models.py` 的命中点比计划正文说的多得多**（计划说「六处」，那是抄 Plan 02 Task 6 的数）。实测（按可 grep 的原文，不用裸行号）：① 函数名 `test_all_eighteen_tables_created`；② **两处** `assert len(tables) == 18, "守卫的覆盖面必须先被确认是这 18 张表"`（**中文消息里也有 18**）；③ `assert len(Base.metadata.tables) == 18`；④ `assert len(json_text_columns) == 14`；⑤ `_BATCH_OWNED_TABLES = {…}` 那五张；⑥ 一段 docstring 逐字写着「有 `batch_id` 列的表**恰好**是 `_BATCH_OWNED_TABLES` 那**五张**」；⑦ `assert observed == _BATCH_OWNED_TABLES`；⑧ **一段注释逐字印着 grep 命令与「3 处本段的散文」的计数**；⑨ 另一段注释提到 `len(json_text_columns) == 14` 与 `_BATCH_OWNED_TABLES`；⑩ 一处注释「⚠️ Task 9 把它从 `_DERIVED_TABLES` 改名为 `_BATCH_OWNED_TABLES`」；⑪ **三处**引用 `test_all_eighteen_tables_created` 这个**函数名**；⑫ **两处** `assert len(_MODELS_PUBLIC_BASELINE) == 33`（**这个不动**，见 P3-A1）。 | **合计约 11 类命中点（不含 ⑫ 那两处刻意不动的）**，全部列进 Step 0 的表。⚠️ **这正是硬规矩 #88 要防的形状**：计划抄了上一个 Task 的「六处」，而实际是 11 类。**改完必须跑一次全量、把红掉的相等断言逐个收进来**，不要只 grep 那个数。新值：表数 **25**、`json_text_columns` **14 → 21**（7 个新 `JsonText` 列：`mini_test.item_combo`、`alert.trigger_snapshot`、`weekly_class_report` 的 5 个）、`_BATCH_OWNED_TABLES` **5 → 9**、函数名 `eighteen → twenty_five`。 |
| **P3-A3** | **Important** | **`_BATCH_OWNED_TABLES` 不只住在测试里**：实测命中 `app/db/models/__init__.py`、`app/db/models/prescription.py`（两处）、`app/pipeline/daily.py`、`tests/db/test_models.py`（六处）。**它是生产代码里的常量，测试那一份是镜像。** | **改的是生产代码那一份**（`app/db/models/__init__.py` 或 `prescription.py`——**先实测它到底定义在哪个文件**，`__init__.py:8` 可能只是重导出），测试那一份跟着改。⚠️ **两处必须同时改**，否则 `assert observed == _BATCH_OWNED_TABLES` 会红在一个看不懂的地方。**并要按硬规矩 #86 回扫 Task 7/8**：`_replay_cleanup` 的清单在 `daily.py`，它读的就是这个常量。 |
| **P3-A4** | **Important** | `weekly_adjustment` 今天的约束实测 = `ck_weekly_adjustment_source`（CHECK）+ 2 个 FK（`prescription_id`、`batch_id`）+ `ix_weekly_adjustment_batch_id`（非唯一索引）。**没有任何 `UniqueConstraint`。** 8 列 = `id / prescription_id / batch_id / week / factor / reason / source / created_at`。 | S2 那条 `UniqueConstraint("prescription_id", "week", "reason", "source")` 是**全新**的。⚠️ **加了它之后 `repo.upsert` 对这张表的 key_fields 口径要复核**（Plan 02 的 `weekly_factors_of` 是只读的，故今天没有 upsert 路径；Task 7 会写它）。**并要有一条测试钉住「同处方 + 同周 + 同原因 + 同来源」插第二次会 `IntegrityError`**——这是 Review Focus 第 3 条（重复触发不得把系数连乘成 `0.512`）的 DB 层那一半。 |
| P3-A5 | Minor | `_in_domain(column: str, allowed: Iterable[str], name: str) -> CheckConstraint` ✓、`JsonText(TypeDecorator)` ✓、`DailySyncRun` 实测 **19 列**含 `alert_count` 与 `prescription_count` ✓、`DailySyncRun.STATUSES = {'success','partial','failed'}`、`CleaningLog.KINDS` 4 个值——**值域一律是类常量 + `_in_domain`**，与计划正文一致。 | 无需更正。**但 `rpe_record.rpe` 的 `BETWEEN 0 AND 10` 是整数区间不是词表**，`_in_domain` 不适用 → 计划正文已写明这一条**手写 `CheckConstraint`**，实测 `ops.py` 里也没有整数区间的先例，故这是本计划第一处手写 CHECK，**要在类常量上写 `RPE_MIN = 0` / `RPE_MAX = 10` 供测试引用**（否则测试里的 `0` 与 `10` 就是两个没有出处的魔数）。 |
| P3-A6 | Minor | **控制者自查**：计划正文写 `models/feedback.py` 是「**475 B** 的空壳」，实测 `read_bytes()` 是 **475 B**、而 `read_text().encode("utf-8")` 是 **467 B** —— **差 8 字节 = 8 个 CRLF**，即**这个文件在磁盘上是 CRLF**。 | 数字本身没错（`475 B` 是磁盘字节数），**但口径要写明**：`backend/app/` 下的 `.py` 文件**混用 CRLF 与 LF**（`.gitattributes` 只钉了 `backend/data/**` 与 `.superpowers/**`，`app/` 走 `core.autocrlf=true`）。**改这个文件时要保持它原有的行尾**（用 `read_bytes()` 量、用 `newline=""` 写），否则一次编辑会把 8 行行尾全改掉、让 `git diff` 看起来整文件重写。 |

"""

patch(PLAN, [
    ("## Task 2: 反馈与预警的 7 张表 + 演示数据\n\n**Files:**",
     "## Task 2: 反馈与预警的 7 张表 + 演示数据\n" + PRE + "\n**Files:**",
     1, "P3 插入预检更正总表"),

    # P3-A1：7 张表全进 feedback.py
    ("**Files:** Modify `backend/app/db/models/feedback.py`（475 B 空壳 → 4 张表）、`backend/app/db/models/ops.py`（+3 张表）、",
     "**Files:** Modify `backend/app/db/models/feedback.py`（**475 B 空壳 → 7 张表**，⚠️ P3-A1：`ops.py` **一张都不加**）、",
     1, "P3-A1 Files 行"),
    ("Modify `backend/app/db/models/feedback.py`（**475 B 空壳 → 7 张表**，⚠️ P3-A1：`ops.py` **一张都不加**）、"
     "`backend/app/db/models/__init__.py`（导入子模块，**不改 `__all__`**）、",
     "Modify `backend/app/db/models/feedback.py`（**475 B 空壳 → 7 张表**，⚠️ P3-A1：`ops.py` **一张都不加**）、"
     "`backend/app/db/models/__init__.py`（**⚠️ P3-A3：`_BATCH_OWNED_TABLES` 的生产代码那一份可能住在这里，先实测**；"
     "`__all__` 不改）、",
     1, "P3-A3 Files 行"),

    # P3-A1：7 张表放哪两个子模块 → 全放 feedback.py
    ("- **7 张表放哪两个子模块**：`class_session` / `rpe_record` / `training_log` / `mini_test` → **`models/feedback.py`**（spec §4.5「反馈三源（高频）」）；"
     "`alert` / `notification` / `weekly_class_report` → **`models/ops.py`**（spec §4.6 的标题逐字是「**预警与运维**」，"
     "而 `weekly_class_report` 与 `daily_sync_run` 同为批处理产物）。**⚠️ 不新建子模块** —— "
     "`_MODELS_SUBMODULES` 是「拆包新增的**六个**子模块名」且有一条守卫钉住它，加第七个要改基线，"
     "而 spec 的分组本来就能落进既有两个模块。",
     "- **⚠️ P3-A1 更正：7 张表全部放 `models/feedback.py`，`ops.py` 一张都不加。** "
     "原文这里说「`alert` / `notification` / `weekly_class_report` → `models/ops.py`（spec §4.6 的标题逐字是『**预警与运维**』）」——"
     "**照做会当场撞红 Ruling 97 那条守卫**：实测 `models/__init__.py` 对 `ops.py` 是 **`from .ops import *`（星号导入）**，"
     "而对 `feedback.py` 与 `prescription.py` 是 **`from . import feedback, prescription`（非星号）**。"
     "故放进 `ops.py` 的三个类名会**自动进入 `models` 的公有命名空间**，让 "
     "`assert observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE)` 红，"
     "而**唯一的「修法」是把基线从 33 抬到 36——那正是 Ruling 97 逐字禁止的**"
     "（「往基线里加新名字等于把『拆包没改导入面』偷换成『拆包后的现状』，断言两侧就同源了」；"
     "Plan 02 的实现者顶回过控制者一次同样的指令，控制者采纳了，见 Plan 02 账本 Ruling 150 的顶回 1）。\n"
     "  **全放 `feedback.py` 的三个理由**：① 它走**非星号**导入，7 个类名**自动**留在包的公有面之外，"
     "**与 Plan 02 的 `prescription.py` 完全同一个机制**，零新增守卫；② **`feedback.py` 自己的 docstring 已经认领了 "
     "`weekly_class_report`** —— 逐字写着「打卡记录、RPE、二次小测、**班级周报（`weekly_class_report`，spec §4.7）"
     "全部属 Plan 03，由它填充**」，即 Plan 02 Task 1 建这个空壳时的意图就是 §4.5–§4.7 全归它；"
     "③ spec 的 §4.5/§4.6/§4.7 分节是**文档结构**、不是 Python 模块布局的约束。\n"
     "  **⚠️ 连带三件事**：(a) `feedback.py` 那段「**本模块今天刻意是空的**」的 docstring **必须整段重写**"
     "（否则它会说「这里是空的」而文件里有 7 张表），重写时**保留它指向 `prescription.py` docstring 的那句交叉引用**；"
     "(b) **`_MODELS_SUBMODULES` 与 `_MODELS_PUBLIC_BASELINE` 都不动**（仍是六个子模块 / 33 个名字）；"
     "(c) `test_plan02_tables_stay_out_of_the_models_public_namespace` 那条守卫**要扩到 11 个表类**"
     "（Plan 02 的 4 个 + 本计划的 7 个），**函数名里的 `plan02` 要不要改成 `plan02_and_03` 由实现者判断并说明理由**。",
     1, "P3-A1 七张表的归属"),

    # P3-A2：命中点从「六处」改成实测的 11 类
    ("- **`test_models.py` 要改的命中点（按硬规矩 #88：先跑一次全量、把红掉的相等断言逐个收进来，不要只 grep 那个数）**："
     "Plan 02 Task 6 的经验是「表数这一个事实的副本」有**六处**，而「别的事实被同一改动证伪」另有**两处**。",
     "- **⚠️ P3-A2 更正：`test_models.py` 的命中点是约 11 类，不是「六处 + 两处」**（那是 Plan 02 Task 6 的数，抄过来就错了）。"
     "**按硬规矩 #88：先跑一次全量、把红掉的相等断言逐个收进来，不要只 grep 那个数。** 实测清单见预检总表的 P3-A2 那一格。",
     1, "P3-A2 命中点数"),

    # P3-A3：_BATCH_OWNED_TABLES 的两份
    ("`_BATCH_OWNED_TABLES`（Plan 02 Task 9 把 `_DERIVED_TABLES` 改成了这个名字；**带 `batch_id` 的表**要从 **5 张扩到 9 张**",
     "**⚠️ P3-A3：`_BATCH_OWNED_TABLES` 不只住在测试里**——实测命中 `app/db/models/__init__.py`、"
     "`app/db/models/prescription.py`（两处）、`app/pipeline/daily.py`、`tests/db/test_models.py`（六处）。"
     "**它是生产代码里的常量，测试那一份是镜像；先实测它到底定义在哪个文件（`__init__.py` 那一处可能只是重导出），"
     "改定义那一份、再改镜像，两处必须同时改。** `_BATCH_OWNED_TABLES`（Plan 02 Task 9 把 `_DERIVED_TABLES` 改成了这个名字；"
     "**带 `batch_id` 的表**要从 **5 张扩到 9 张**",
     1, "P3-A3 _BATCH_OWNED_TABLES 的两份"),

    # P3-A4：weekly_adjustment 的唯一约束是全新的
    ("⚠️ 加完要跑一次全量、把红掉的相等断言逐个收进来（硬规矩 #88）。",
     "⚠️ 加完要跑一次全量、把红掉的相等断言逐个收进来（硬规矩 #88）。"
     "**⚠️ P3-A4：`weekly_adjustment` 今天没有任何 `UniqueConstraint`**（实测约束 = `ck_weekly_adjustment_source` + "
     "2 个 FK + `ix_weekly_adjustment_batch_id` 非唯一索引），故这一条是**全新**的。"
     "**要有一条测试钉住「同处方 + 同周 + 同原因 + 同来源」插第二次会 `IntegrityError`** —— "
     "这是 Review Focus 第 3 条（重复触发不得把系数连乘成 `0.8³ = 0.512`）的 **DB 层那一半**"
     "（应用层那一半是 Task 7 的 `window_key`）。"
     "⚠️ 加完之后 `repo.upsert` 对这张表的 `key_fields` 口径要复核（Plan 02 的 `weekly_factors_of` 是只读的、"
     "今天没有 upsert 路径；**Task 7 才会写它**，故本 Task 只需保证约束在、不必建 upsert 路径）。",
     1, "P3-A4 唯一约束是全新的"),

    # P3-A5：rpe 的整数区间 CHECK（锚点逐字取自计划正文，控制者亲跑 read_bytes 后抄的）
    ("（**⚠️ 用 `_in_domain` 不合适——它是整数区间不是词表**，故这一条**手写 "
     "`CheckConstraint(\"rpe BETWEEN 0 AND 10\", name=\"ck_rpe_record_rpe\")`**，"
     "并在类常量上写 `RPE_MIN = 0` / `RPE_MAX = 10` 供测试引用）",
     "（**⚠️ 用 `_in_domain` 不合适——它是整数区间不是词表**（P3-A5 实测坐实："
     "`_in_domain(column, allowed: Iterable[str], name)` 只吃字符串词表，而 `ops.py` 里也**没有整数区间的先例**，"
     "故这是本计划第一处手写 CHECK），故这一条**手写 "
     "`CheckConstraint(\"rpe BETWEEN 0 AND 10\", name=\"ck_rpe_record_rpe\")`**，"
     "并在类常量上写 `RPE_MIN = 0` / `RPE_MAX = 10` 供测试引用"
     "（**否则测试里的 `0` 与 `10` 就是两个没有出处的魔数**，而 spec §8.2 的 `RED_RPE_SUSTAINED`（连续 ≥ 9）与 "
     "`YELLOW_CLASS_RPE_HIGH`（均值 > 7）两个阈值都建立在这个值域上））",
     1, "P3-A5 rpe 的整数区间 CHECK"),
])

# ============ 账本 ============
lb = LEDGER.read_bytes()
lt = lb.decode("utf-8")
lnl = "\r\n" if "\r\n" in lt else "\n"
print(f"[ledger before] bytes={len(lb)} lines={lt.count(lnl)}")

BODY = """

---

### Task 2: 反馈与预警的 7 张表 + 演示数据 — 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`a44968f`（Task 1 结案，工作树干净）。**测试基线**：`824 passed`；domain **996/0/288/0/100%**；**18 张表**；扫描面 **38**。
**取证脚本**：`t2_probes/_preflight.py`（一份，Ruling 1 的口径）。

#### Ruling 6 — 预检查出 1 Critical / 3 Important / 2 Minor，计划正文更正 7 处

**P3-A1（Critical）是本轮唯一但最重的一条：计划把 3 张表放进 `models/ops.py`，照做会当场撞红 Ruling 97 那条守卫，而唯一的「修法」正是 Ruling 97 逐字禁止的那一个。**

实测机制：`models/__init__.py` 对 **`ops.py` 是 `from .ops import *`（星号导入）**，而对 `feedback.py` 与 `prescription.py` 是 **`from . import feedback, prescription`（非星号）**。故：
- 放进 `ops.py` 的 `Alert` / `Notification` / `WeeklyClassReport` 三个类名会**自动进入 `models` 的公有命名空间** → `assert observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE)` 红（多出 3 个名字）；
- 而消掉这条红的唯一办法是**把 `_MODELS_PUBLIC_BASELINE` 从 33 抬到 36** —— **那正是 Plan 02 的实现者顶回过、控制者采纳过的那条禁令**（Plan 02 账本 Ruling 150 的顶回 1：「往基线里加新名字等于把『拆包没改导入面』偷换成『拆包后的现状』，断言两侧就同源了（硬规矩 #35），而 `…is_unchanged_by_the_split` 这个函数名会当场变成谎话」）。

**裁定：7 张表全部放 `models/feedback.py`，`ops.py` 一张都不加。** 三个理由：① `feedback.py` 走非星号导入，7 个类名**自动**留在公有面之外，**与 Plan 02 的 `prescription.py` 完全同一个机制**，零新增守卫；② **`feedback.py` 自己的 docstring 已经认领了 `weekly_class_report`** —— 逐字写着「打卡记录、RPE、二次小测、**班级周报（`weekly_class_report`，spec §4.7）全部属 Plan 03，由它填充**」，即 **Plan 02 Task 1 建这个空壳时的意图就是 §4.5–§4.7 全归它**，而本计划的作者（控制者）没读那段 docstring 就按 spec 的章节标题分了模块；③ spec 的 §4.5/§4.6/§4.7 分节是**文档结构**、不是 Python 模块布局的约束。

**⚠️ 连带三件事已写进计划**：(a) `feedback.py` 那段「**本模块今天刻意是空的**」的 docstring **必须整段重写**（否则它会说「这里是空的」而文件里有 7 张表），重写时**保留它指向 `prescription.py` docstring 的那句交叉引用**；(b) `_MODELS_SUBMODULES`（六个子模块）与 `_MODELS_PUBLIC_BASELINE`（33）**都不动**；(c) `test_plan02_tables_stay_out_of_the_models_public_namespace` 要**扩到 11 个表类**（Plan 02 的 4 个 + 本计划的 7 个），函数名里的 `plan02` 要不要改成 `plan02_and_03` 由实现者判断并说明理由。

**→ 控制者错误 #4**：分模块时**照着 spec 的章节标题分**，没有先实测 `models/__init__.py` 的导入方式。**这与 Plan 02 的控制者错误 #148 同型**（那次是「只核了 `LastPrescription.microcycle_weeks` 有没有住址，没把 5 个字段逐个对到列上」）——**都是「对着文档的形状推理，没对着代码的实际机制推理」**，而 Plan 02 的 25 次顶回里**每一次**的实现者理由都是这一句。
**→ 补硬规矩 #100：把一个类/函数放进某个既有模块之前，必须先实测那个模块是怎么被重导出的（星号 vs 具名 vs `from . import x`）——「放进哪个文件」在有重导出的包里不是排版问题，是公开面问题。** 依据：P3-A1 / 控制者错误 #4；Plan 02 的 Ruling 97 与 Ruling 150 顶回 1 已经为同一件事付过两次学费，这是第三次。

**其余 5 条**（详见计划正文的预检总表）：
- **P3-A2（Important）**：`test_models.py` 的命中点是**约 11 类**，不是计划抄来的「六处 + 两处」（那是 Plan 02 Task 6 的数）。逐类列进了 Step 0 的表。新值：表数 **25**、`json_text_columns` **14 → 21**、`_BATCH_OWNED_TABLES` **5 → 9**、函数名 `eighteen → twenty_five`；**`_MODELS_PUBLIC_BASELINE` 的 33 刻意不动**（P3-A1）。
- **P3-A3（Important）**：`_BATCH_OWNED_TABLES` **不只住在测试里** —— 实测命中 `app/db/models/__init__.py`、`app/db/models/prescription.py`（两处）、`app/pipeline/daily.py`、`tests/db/test_models.py`（六处）。**它是生产代码里的常量，测试那一份是镜像**；先实测定义在哪个文件（`__init__.py` 那一处可能只是重导出），**两处必须同时改**，否则 `assert observed == _BATCH_OWNED_TABLES` 会红在一个看不懂的地方。
- **P3-A4（Important）**：`weekly_adjustment` 今天**没有任何 `UniqueConstraint`**（实测约束 = `ck_weekly_adjustment_source` + 2 个 FK + `ix_weekly_adjustment_batch_id` 非唯一索引，8 列），故 S2 那条是**全新**的。要有一条测试钉住「同处方 + 同周 + 同原因 + 同来源」插第二次会 `IntegrityError` —— 这是 Review Focus 第 3 条的 **DB 层那一半**（应用层那一半是 Task 7 的 `window_key`）。
- **P3-A5（Minor）**：`_in_domain(column, allowed: Iterable[str], name)` 实测**只吃字符串词表**，而 `ops.py` 里**没有整数区间的先例** → `rpe BETWEEN 0 AND 10` 是本计划第一处手写 CHECK，**必须在类常量上写 `RPE_MIN = 0` / `RPE_MAX = 10`**，否则测试里的 `0` 与 `10` 是两个没有出处的魔数（而 spec §8.2 的「连续 ≥ 9」与「均值 > 7」都建立在这个值域上）。
- **P3-A6（Minor，控制者自查）**：计划写 `feedback.py` 是「475 B 的空壳」——实测 `read_bytes()` **475 B**、`read_text().encode("utf-8")` **467 B**，**差 8 字节 = 8 个 CRLF**，即**这个文件在磁盘上是 CRLF**。数字没错但口径要写明：`backend/app/` 下的 `.py` **混用 CRLF 与 LF**（`.gitattributes` 只钉了 `backend/data/**` 与 `.superpowers/**`），**改它时要保持原有行尾**（`read_bytes()` 量、`newline=""` 写），否则一次编辑会把 8 行行尾全改掉、让 `git diff` 看起来整文件重写。**⚠️ 这是硬规矩 #89 扩写（数行尾用 `read_bytes()`）的又一次现身**——这次它没有导致误判，但差 8 字节这件事本身只有在两个口径都量了才看得见。

**计划正文更正**：`_t2_preflight_patch.py`，**7 处替换全部命中 1 次**（硬规矩 #79）。

**下一步**：抽 `task-2-brief.md` → 派实现者。**按 Ruling 1，目标 0–1 轮。**
"""

if lnl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", lnl)
SENT = "Ruling 6 — 预检查出 1 Critical"
assert SENT not in lt, f"{SENT!r} 已存在"
LEDGER.write_bytes((lt.rstrip("\r\n") + BODY).encode("utf-8"))
c2 = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c2.encode('utf-8'))} lines={c2.count(lnl)}")
for k in ("Ruling 6", "硬规矩 #100", "控制者错误 #4", "P3-A1", "P3-A6", "from .ops import *"):
    print(f"  {k}: {c2.count(k)}")
print(f"\n[edits] {len(edits)} 处：")
for lab, n in edits:
    print(f"  {n}x  {lab}")

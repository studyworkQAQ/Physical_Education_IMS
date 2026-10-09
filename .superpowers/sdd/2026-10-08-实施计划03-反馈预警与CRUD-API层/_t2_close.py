"""Plan 03 Task 2 结案：删陈旧 pe_demo.db + 账本 Ruling 7 + 硬规矩 #101 + 传导给 Task 6/8。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BACKEND = ROOT / "backend"
LEDGER = HERE / "progress.md"

# ---- 1. 删掉陈旧的演示库（控制者自己的产物，实现者刻意没动）----
demo = BACKEND / "pe_demo.db"
if demo.exists():
    sz = demo.stat().st_size
    demo.unlink()
    print(f"[demo] 删掉陈旧的 pe_demo.db（{sz} B / 18 张表）—— 下次跑 uvicorn 会按 25 张表重建")
else:
    print("[demo] pe_demo.db 不存在")
print(f"[demo] 删后存在? {demo.exists()}   pe.db 存在? {(BACKEND/'pe.db').exists()}")

# ---- 2. 账本 ----
b = LEDGER.read_bytes()
t = b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"[ledger before] bytes={len(b)} lines={t.count(nl)}")

BODY = """

---

## ✅ Task 2: complete (commits bcf3936..fd73788, 0 fix round)

**交付**：`d07a252`（Step 0：表数 18→25 的全部命中点先改测试，**刻意红**：4 failed / 790 passed / 1 collection error）、`78fa495`（7 张表全在 `models/feedback.py` + `weekly_adjustment` 唯一约束 + 全部散文同步 → 841 passed）、`fd73788`（`app/demo_data.py` + 4 条测试 → 845 passed）。

**验收（控制者本机亲跑复核，探针 `t2_probes/_verify.py` 已入库；全部 15 项 ✅）**：
- 全量 **824 → 845 passed**（+17 在 `tests/db/test_models.py`：`def test_` 30 → 47；+4 在 `tests/test_demo_data.py`）；带 `--cov` **844 passed, 1 skipped**
- `app/domain/` 四格 **996 / Miss 0 / 288 / BrPart 0 / 100% 逐字未变**（本 Task 不加 domain 代码）✓
- **表数 18 → 25** ✓；`len(json_text_columns)` **14 → 21** ✓；`DATA_TABLES` **11 → 18** ✓；外键 24 → **41**；`_in_domain` 列 18 → **23**
- **P3-A1 落地证据**：`_MODELS_PUBLIC_BASELINE` **仍 33**（两处断言一字未动）、`_MODELS_SUBMODULES` **仍六个**、**7 个新类名进公有面的数量 = 0**、`git diff bcf3936 HEAD -- backend/app/db/models/ops.py` **输出为空（一个字节没改）** ✓；守卫改名 `test_plan02_and_plan03_tables_stay_out_of_the_models_public_namespace` 并扩到 **11 个表类**
- **7 张表的列数与约束逐个亲验**：`class_session` **7** 列 / `uq_class_session_section_date_period`；`rpe_record` **6** / `ck_rpe_record_rpe` + `uq_rpe_record_session_student`；`training_log` **10** / `ck_training_log_feeling` + `uq_training_log_student_day`；`mini_test` **10** / `uq_mini_test_student_semester_week`；`alert` **14** / `ck_alert_level` + `ck_alert_status` + `ck_alert_subject_is_exactly_one` + `uq_alert_rule_subject_semester_window`；`notification` **10** / `ck_notification_recipient_kind` + `ck_notification_channel`；`weekly_class_report` **12** / `uq_weekly_class_report_section_semester_week`
- **`weekly_adjustment` 仍 8 列**（本 Task 只加约束不加列）+ 新 `uq_weekly_adjustment_prescription_week_reason_source`（4 列：`prescription_id` / `week` / `reason` / `source`）✓
- **`notification` 的两个 FK 都带 `ondelete='SET NULL'`**（`alert_id` → `alert.id`、`prescription_id` → `prescription.id`）✓
- **扫描面仍 38** ✓（`app/demo_data.py` 是 `app/` 根下模块，不在 `SCANNED_DIRS` 任何一项里，与 `app/main.py` 同档）
- **P3-A6 落地**：`feedback.py` 现在 **43 360 B / 679 行 / 纯 CRLF**（保持了它原有的行尾，没有一次编辑把 8 行行尾全改掉）；「本模块今天刻意是空的」已消失、星号导入的理由已写进去 ✓
- **禁区**：三个指纹 `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` **逐字不变**、CRLF 均 0；`git diff bcf3936 HEAD -- backend/data` **为空**；`pe.db` **不存在**；`data/seed/` **0 文件**

### Ruling 7 — 实现者顶回 3 处，**全部采纳**（Plan 03 的第 5–7 次顶回；累计 **31 次，31 次都对**）

**顶回 1（Critical，采纳 → 控制者错误 #5）：「`alert` 用 `0` 作哨兵」这个方案在结构上跑不起来。**
计划的原文是「`student_id` 与 `course_section_id` 都改成 `nullable=False` + 用 `0` 作哨兵（学生级预警 `course_section_id = 0`、班级级预警 `student_id = 0`）」，理由是要绕开「SQLite 的 UNIQUE 对 NULL 是 NULL ≠ NULL，两列可空会让去重约束对班级级预警静默失效」。
**实现者用最小复现探针（`p01_sentinel_fk.py`）证明它跑不起来**：那两列**都是外键**，而 `PRAGMA foreign_keys=ON` 的钩子挂在 **`Engine` 类**上（故内存库与磁盘库都生效），父表 `student` / `course_section` **没有 `id = 0` 的行** → **每一条哨兵行当场 `FOREIGN KEY constraint failed`**。
⚠️ **更严重的是它的失效时机**：照派单做的话，**本 Task 一条测试都抓不到**（本 Task 不写 `alert` 行），缺陷要到 **Task 7 第一次真的落一条预警**时才爆 —— 而那已经是三个 Task 之后。
**实现者的替代设计（控制者亲验已落地）**：两列**保持可空**，**新增一个 NOT NULL 的 `subject_key: VARCHAR(24)`** 承担去重键的「主语位」（形如 `"student:123"` / `"class:45"`），去重键从 5 列降到 **4 列**（`rule_id` / `subject_key` / `semester_id` / `window_key`），并加 **`ck_alert_subject_is_exactly_one`**（`student_id` 与 `course_section_id` **恰好一个非空**）把「两列都可空」重新收紧。**这与 `CleaningLog` 的 `student_no` / `student_id` 双列承载 Ruling 25 是同一形状**（一个 NOT NULL 的逻辑主语 + 一个可空的 FK），即**本仓已有的先例**。并留了反证测试。
**→ 补硬规矩 #101：用哨兵值（`0` / `""` / `-1`）代替 NULL 之前，必须先确认那一列不是外键 —— 或者父表真的有那一行。** 依据：控制者错误 #5。**⚠️ 这一族与硬规矩 #92（要求一条测试变红前先论证破坏在结构上可达）是同一件事的两面**：#92 管「守卫能不能红」，#101 管「数据能不能写进去」，**两者都是「先论证结构上可行，再写进计划」**。

**顶回 2（采纳）**：`class_session` **需要一条 `UniqueConstraint(course_section_id, session_date, period)`**，而计划给另外 5 张表都点了唯一约束、**唯独漏了它**。理由成立：`repo.upsert` 是「先 select 再写」，没有 DB 兜底会炸在读侧的 `MultipleResultsFound`；而且 **`class_session` 不能进 `_replay_cleanup`**（`rpe_record.class_session_id` 是 **NOT NULL 外键**、而 `rpe_record` 是**用户实时写入**的，重放不该删掉学生刚交的快评）→ **upsert 是它唯一的幂等手段**。
**⚠️ 这条连带传导给 Task 8**（实现者已把它写进 `feedback.py` / `repo.py` / `daily.py` 三处）：**`ClassSession` 有 `batch_id` 但不得进 `_replay_cleanup`**。→ 故 `_BATCH_OWNED_TABLES` 的 9 张与 `_replay_cleanup` 的清单**不是同一份**：前者是「有 `batch_id` 列的表」，后者是「重放时按批删的表」。**这个区分要在 Task 7/8 的正文里写明**，否则下一个人会以为两个清单该一样。

**顶回 3（采纳）**：**`notification.prescription_id` 也要 `ondelete="SET NULL"`**，派单只点了 `alert_id`。理由成立且更紧急：**`prescription` 今天就已经在 `_replay_cleanup` 里**（Plan 02 Task 7 加的），少了这一个 `ondelete`，**第一条指向处方的通知落库后、下一次重放同一天就炸在 `delete_by_batch` 上**。控制者亲验两个 FK 都带 `SET NULL` ✓。

### 控制者错误 #6 —— P3-A3 的「两份」是假的

预检的 P3-A3 逐字写着「`_BATCH_OWNED_TABLES` **不只住在测试里** —— 实测命中 `app/db/models/__init__.py`、`app/db/models/prescription.py`（两处）、`app/pipeline/daily.py`、`tests/db/test_models.py`（六处）。**它是生产代码里的常量，测试那一份是镜像**」。
**实现者用 AST 取证（`p03_batch_owned.py`）证明它只有一份定义**（`tests/db/test_models.py`），**`app/` 下那 8 处全是散文引用、没有一处赋值** → **不存在「生产代码常量 + 测试镜像」，没有第二份可改**。那 8 处「五张」的说法已全改成「九张」。
**⚠️ 这与 Plan 02 的控制者错误 #155 是同一形状**（用文本命中数当成「定义的份数」）—— **#155 是「正则数表格行漏了加粗编号」，本次是「grep 命中数把散文引用当成了定义」**。两者都是硬规矩 #89 要防的事，而 #89 的正文只说了「数键/字段/成员」，**没说「数定义」**。
**→ 硬规矩 #89 再扩写：数「一个名字有几份定义」时，用 AST（`ast.parse` 后找 `ast.Assign` / `ast.AnnAssign` 的 target），不要用文本命中数——散文引用、注释、docstring 里的同名提及都会被算进去。**

### 11 处偏离派单字面：全部追认

除上面 3 处顶回外另 8 处：① P3-A3 无第二份可改（见 #6）；② 守卫改名（理由成立：本条守的是「每一批新表都按子模块引用」，名字只写一个计划会让下一个计划另起第三条同型守卫）；③ **`mini_test` 是 10 列不是 11**（被它自己写的形状测试当场抓出）；④ **多改 6 个派单没列的文件**（全是硬规矩 #66 的散文同步，含 `_shared.py` / `prescription.py` 那「三处同一事实」的 14 → 21）；⑤ `tests/api/test_scope.py` 实测**不依赖表数**故未改（只改了 `conftest.py` 两处散文）；⑥ `DemoReport` 字段形状自定；⑦ 多写一条 demo 测试（`test_demo_feedback_gives_the_alert_engine_something_to_fire_on`）；⑧ **派单 0.1(a) 自相矛盾**（「必须整段重写」与「保留那句交叉引用」两句打冲突）**按后半句办** —— 即重写整段、但不保留那句已不适用的交叉引用，改成说明为什么 7 张表都住在这里。**⚠️ 这是本计划自审（Ruling 3）漏掉的第 7 处自相矛盾，由实现者抓出。**

### `demo_data` 的口径与一条额外的变异取证

四条测试：`test_build_demo_feedback_is_idempotent`（**跑三次逐字不变** 16 / 480 / 1680 / 480，**计数是从库里数出来的、不是自报**）、`test_demo_data_never_touches_the_clock`（**词表从 `tests/seed/test_generate.py` import、不抄第二份** + 4 组自证 + 1 组负对照）、`test_seed_database_still_writes_no_feedback_rows`（**这条守的是 P3-A1 的分区决定**）、`test_demo_feedback_gives_the_alert_engine_something_to_fire_on`。
**实现者自跑了一条变异**（Ruling 1 说本 Task 不要求变异，它自己加了）：把 `_training_logs` 的 upsert 换成裸 `add` → 幂等那条当场红，还原后 sha256 逐字一致。**这是「新守卫有牙」的自证，控制者采纳。**

### 待清扫：**11 条**（推 Task 9），Critical 级遗留 **0** 处

最要紧的两条：① **`ops.py` 的 docstring 仍写「`alert` / `notification` 属计划 03」**（按 P3-A1 的要求它**0 字节未改**，而 `feedback.py` 与 `models/__init__.py` 两处已显式纠正 → **三份文档里有一份是旧的**）；② **`backend/pe_demo.db` 是 Task 1 留下的陈旧演示库（18 张表）** —— 下次跑 uvicorn 时 `create_all` 会补出 7 张新表，但**不会**给已存在的 `weekly_adjustment` 补那条新唯一约束，**演示库上那道 DB 兜底会静默缺席**。实现者没删（那是控制者的产物）→ **控制者本轮已删掉**（`pe_demo.db` 172 032 B / 18 张表 → 已删，下次跑 uvicorn 会按 25 张表重建）。**⚠️ 这也是一条通用教训：演示库是「不可复现的产物」，与 `pe.db` 禁区的性质相同，只是它可重建故不进禁区清单。→ 记进 Task 9 的 `demo.ps1` 要求：脚本第一步必须删掉旧的 `pe_demo.db`。**

### ⚠️ 按硬规矩 #86 回扫 Task 6/7/8（本 Task 结案改变了它们的前提）

1. **Task 6**：`StudentHit` / `ClassHit` 除了 `window_key` **还必须产出 `subject_key`**（形如 `"student:<id>"` / `"class:<id>"`，`VARCHAR(24)`）—— 它是 `uq_alert_rule_subject_semester_window` 的四列之一，而**去重键已经从 5 列变成 4 列**（`rule_id` / `subject_key` / `semester_id` / `window_key`）。计划 Task 6 的正文写的还是 5 列（含 `student_id` 与 `course_section_id`），**Task 6 预检时必须更正**。
2. **Task 7**：`alert_stage` 落 `alert` 行时要填 `subject_key`，且 **`ck_alert_subject_is_exactly_one`** 要求 `student_id` 与 `course_section_id` **恰好一个非空** —— 学生级预警填 `student_id`、班级级填 `course_section_id`，**不能两个都填、也不能两个都不填**。
3. **Task 8**：`_replay_cleanup` 的清单**不含 `class_session`**（顶回 2 的连带），故 `_BATCH_OWNED_TABLES`（9 张，「有 `batch_id` 列的表」）与 `_replay_cleanup` 的清单（**8 张**：Plan 02 的 5 张 + `alert` + `weekly_class_report` + …**Task 7/8 落地时自己数**）**不是同一份**。这个区分要写进 `daily.py` 的 docstring。
4. **Task 9**：`demo.ps1` 的第一步必须删掉旧的 `pe_demo.db`（待清扫第 2 条）。

**下一步**：抽 `task-3-brief.md` → 派实现者（泛型 CRUD 工厂 + 23 个资源）。
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
SENT = "Task 2: complete (commits bcf3936..fd73788"
assert SENT not in t, f"{SENT!r} 已存在"
LEDGER.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)}")
for k in ("Ruling 7", "硬规矩 #101", "控制者错误 #5", "控制者错误 #6", "subject_key", "845 passed"):
    print(f"  {k}: {c.count(k)}")

"""F1-1 Step 2：给 prescription 加 label_at_generation 列 + 改读法 + 同步测试。

四处文件、逐处 assert 命中次数（硬规矩 #79）。行尾按各文件既有口径写回
（models/prescription.py 与 test_models.py 是 CRLF，prescription_stage.py 与
test_prescription_stage.py 是 LF）——实测：read_text 的通用换行会把 CRLF 读成 \\n，
故写回时用 newline="\\r\\n" 复原。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"


def edit(rel: str, pairs: list[tuple[str, str]], crlf: bool) -> None:
    p = BACKEND / rel
    src = p.read_text(encoding="utf-8")
    for old, new in pairs:
        n = src.count(old)
        assert n == 1, f"{rel}: 命中 {n} 次（应为 1）：{old[:70]!r}"
        src = src.replace(old, new)
    p.write_text(src, encoding="utf-8", newline="\r\n" if crlf else "")
    print(f"OK {rel}  ({len(pairs)} 处)  -> {len(p.read_bytes())} B")


# ---------------------------------------------------------------------------
# 1. app/db/models/prescription.py（CRLF）
# ---------------------------------------------------------------------------
edit("app/db/models/prescription.py", [
    (
        "from ._shared import JsonText, _in_domain\n",
        "from ._shared import JsonText, _in_domain\n"
        "# 值域的**单一所有者**（本包约定 2）：``label_at_generation`` 存的就是\n"
        "# ``stratification_result.label`` 那一族值，故 CHECK 直接引它的类常量、不在本模块\n"
        "# 再声明第二份词表。``derived`` 不 import 本模块，无环（``derived`` 自己也是这么\n"
        "# 引 ``organisation.Student`` 的）。\n"
        "from .derived import StratificationResult\n",
    ),
    (
        "    另有四列 spec §4.4 **没有**，逐列的依据写在各自注释里：``microcycle_weeks``（P6-A3）、\n"
        "    ``previous_had_overrides``（P6-A2）、``batch_id``（与 Plan 01 三张派生表同构）、\n"
        "    以及 ``(student_id, generated_on)`` 的唯一约束（Review Focus 第 2 条）。\n",
        "    另有**四列** spec §4.4 **没有**，逐列的依据写在各自注释里：``microcycle_weeks``（P6-A3）、\n"
        "    ``previous_had_overrides``（P6-A2）、``label_at_generation``（**Task 7 fix round 1 的\n"
        "    F1-1**，控制者错误 #148：Task 6 预检时逐个核了 ``microcycle_weeks`` 有没有住址，\n"
        "    却没把 :class:`~app.domain.prescription.triggers.LastPrescription` 的**五个字段逐个对到\n"
        "    列上**——四个有列、只有它没有）、``batch_id``（与 Plan 01 三张派生表同构），\n"
        "    以及 ``(student_id, generated_on)`` 的唯一约束（Review Focus 第 2 条）。\n",
    ),
    (
        "    microcycle_weeks: Mapped[int] = mapped_column(Integer)\n",
        "    microcycle_weeks: Mapped[int] = mapped_column(Integer)\n"
        "    #: **生成当时的分层标签**（Task 7 fix round 1 的 F1-1 新增）。触发 2 的判据逐字是\n"
        "    #: ``current_label != last_prescription.label_at_generation``，故本列是那条判据的\n"
        "    #: **唯一输入**。理由与 :attr:`microcycle_weeks`（P6-A3）**完全同构**：处方要能\n"
        "    #: **离线复算**触发判定（spec §4.3「任一条结果都能离线复算」），就把判定输入\n"
        "    #: 快照在处方行上。\n"
        "    #:\n"
        "    #: ⚠️ **在此之前它没有住址**，``app.pipeline.prescription_stage`` 只能按\n"
        "    #: ``(student_id, computed_on == generated_on)`` 去 ``outerjoin`` 回读同一天\n"
        "    #: ``stratification_result.label``。那有三个具体失效形态：①\n"
        "    #: :func:`app.pipeline.daily._replay_cleanup` 按 ``batch_id`` 删 ``stratification_result``\n"
        "    #: 的行——**重放之后那一天的分层行可能已经不在了**，join 返回 ``NULL`` → 触发 2\n"
        "    #: **静默不成立**（该换处方的时候不换）；② join 的条件是一个**跨表的隐式契约**，\n"
        "    #: 没有任何守卫钉住它；③ 它让「处方的触发判定」依赖另一张表的行还在不在。\n"
        "    #: 守卫：``tests/pipeline/test_prescription_stage.py`` 的\n"
        "    #: ``test_trigger_2_survives_the_deletion_of_that_days_stratification_row``\n"
        "    #: （删掉那一天的分层行 → 触发 2 仍然成立）与 ``tests/db/test_models.py`` 的\n"
        "    #: ``test_prescription_label_at_generation_shares_its_domain_with_the_label_column``。\n"
        "    #:\n"
        "    #: **列宽与 CHECK 都与 ``stratification_result.label`` 同口径**（硬规矩 #18）：值域直接引\n"
        "    #: :attr:`StratificationResult.LABELS`，**不在本类再声明第二份词表**（本包约定 2 的\n"
        "    #: 「类常量是唯一真相」在这里的读法是「那个类常量只有一个」）。最长者\n"
        "    #: ``\"insufficient_data\"`` 是 **17** 字符（Ruling 144 的同一个值），``String(20)``\n"
        "    #: 余量 3，与那一列逐字相同——两处长度不同就是一个没人看得见的漂移。\n"
        "    #: ⚠️ 值域**含** ``insufficient_data`` 而生产上写不进那一档（Z0 闸门在 upsert 之前就\n"
        "    #: ``continue``）；**刻意不收窄成三个**——收窄就要在本类另立一份词表，即第二个所有者。\n"
        "    #: 对照 :attr:`PrescriptionTemplate.LAYERS`：那里收窄成三个是因为模板的 ``layer`` 真的\n"
        "    #: 可能被人写成 ``insufficient_data``、需要 DB 拒收，两处的取舍不同而理由相同。\n"
        "    label_at_generation: Mapped[str] = mapped_column(String(20), nullable=False)\n",
    ),
    (
        "    **列宽**（硬规矩 #18）：``status`` 的取值域里最长者是 ``\"needs_review\"``（**12**），\n"
        "    声明 ``String(16)``，余量 4；``template_ref`` 与\n"
        "    :attr:`PrescriptionTemplate.template_ref` 同宽（``String(32)``，今天最长 14、余量 18）。\n"
        "    ``status`` 带 ``_in_domain`` CHECK，故被\n",
        "    **列宽**（硬规矩 #18）：``status`` 的取值域里最长者是 ``\"needs_review\"``（**12**），\n"
        "    声明 ``String(16)``，余量 4；``template_ref`` 与\n"
        "    :attr:`PrescriptionTemplate.template_ref` 同宽（``String(32)``，今天最长 14、余量 18）；\n"
        "    ``label_at_generation`` 与 ``stratification_result.label`` 同宽（``String(20)``，\n"
        "    最长者 ``\"insufficient_data\"`` 是 **17**、余量 3，Ruling 144 的同一个值）。\n"
        "    ``status`` 与 ``label_at_generation`` 带 ``_in_domain`` CHECK，故被\n",
    ),
    (
        "    __table_args__ = (\n"
        "        _in_domain(\"status\", STATUSES, \"ck_prescription_status\"),\n",
        "    __table_args__ = (\n"
        "        _in_domain(\"status\", STATUSES, \"ck_prescription_status\"),\n"
        "        # 值域引 StratificationResult.LABELS（单一所有者），约束名照本表既有风格\n"
        "        # ck_<表名>_<列名>。\n"
        "        _in_domain(\n"
        "            \"label_at_generation\",\n"
        "            StratificationResult.LABELS,\n"
        "            \"ck_prescription_label_at_generation\",\n"
        "        ),\n",
    ),
], crlf=True)

# ---------------------------------------------------------------------------
# 2. app/pipeline/prescription_stage.py（LF）
# ---------------------------------------------------------------------------
edit("app/pipeline/prescription_stage.py", [
    (
        "2. **基础设施异常（原样冒泡）**：DB 读写（:func:`_current_prescriptions` /\n"
        "   :func:`_labels_at` / :func:`_last_prescription_of` / ``repo.upsert`` / ``session.flush``）\n",
        "2. **基础设施异常（原样冒泡）**：DB 读写（:func:`_previous_prescriptions` /\n"
        "   ``repo.upsert`` / ``session.flush``）\n",
    ),
    (
        "def _previous_prescriptions(\n"
        "    session: Session, as_of: dt.date\n"
        ") -> dict[int, tuple[Prescription, str | None]]:\n"
        "    \"\"\"**批级预取**：每个学生「``generated_on <= as_of`` 里最新的那一张处方」+ **它生成当天的分层标签**。\n"
        "\n"
        "    返回 ``{student_id: (Prescription, label | None)}``；``label is None`` 表示那一天的\n"
        "    ``stratification_result`` 行不在了（:func:`_last_prescription_of` 对它响亮失败）。\n"
        "\n"
        "    ⚠️⚠️ **一次查询、不是每人一次，而且只取需要的列**（本模块承重的性能决定，实测数据\n"
        "    见下）。三个坑，逐个说：\n",
        "def _previous_prescriptions(session: Session, as_of: dt.date) -> dict[int, Prescription]:\n"
        "    \"\"\"**批级预取**：每个学生「``generated_on <= as_of`` 里最新的那一张处方」。\n"
        "\n"
        "    返回 ``{student_id: Prescription}``。**它生成当时的分层标签就在这一行上**\n"
        "    （:attr:`~app.db.models.prescription.Prescription.label_at_generation`），故不必再\n"
        "    连第二张表，见下面第 3 条。\n"
        "\n"
        "    ⚠️⚠️ **一次查询、不是每人一次，而且只取需要的列**（本模块承重的性能决定，实测数据\n"
        "    见下）。三个坑，逐个说：\n",
    ),
    (
        "       而本阶段只需要它的 6 个小列，**一个都不读那 4 个大列**——除了\n",
        "       而本阶段只需要它的 7 个小列，**一个都不读那 4 个大列**——除了\n",
    ),
    (
        "    3. **标签与处方在一条 SQL 里连接**，而不是「先取处方、再按 ``computed_on IN (days)``\n"
        "       取标签」：``stratification_result`` 上只有 ``(student_id, computed_on)`` 一条唯一\n"
        "       索引，**按 ``computed_on`` 单列过滤用不上它** → 全表扫描，而那张表到学期末有\n"
        "       **56 000** 行、每行还带一个约 2 KB 的 ``input_snapshot``。连接写法走的是同一条\n"
        "       唯一索引，每天只碰 **500** 行。\n",
        "    3. **不再连 ``stratification_result``**（Task 7 fix round 1 的 F1-1）：触发 2 要比的\n"
        "       「生成当时的标签」现在住在处方行自己的 ``label_at_generation`` 上。**此前这里是\n"
        "       一个 ``outerjoin``**，按 ``(student_id, computed_on == generated_on)`` 回读同一天\n"
        "       的 ``stratification_result.label``；那样写有两个毛病：① 那是一个**跨表的隐式\n"
        "       契约**，没有任何守卫钉住它；② :func:`app.pipeline.daily._replay_cleanup` 按\n"
        "       ``batch_id`` 删分层行，**重放之后那一天的行可能已经不在了** → join 返回 ``NULL``\n"
        "       → 触发 2 静默不成立（该换处方的时候不换），与 spec §4.3 的「离线可复算」相反。\n"
        "       ⚠️ 当年之所以必须连表，是因为「按 ``computed_on`` 单列过滤用不上\n"
        "       ``(student_id, computed_on)`` 那条唯一索引」→ 全表扫描（学期末 **56 000** 行、\n"
        "       每行还带一个约 2 KB 的 ``input_snapshot``）；快照到行上之后这次连接整个消失。\n"
        "       守卫：``tests/pipeline/test_prescription_stage.py`` 的\n"
        "       ``test_trigger_2_survives_the_deletion_of_that_days_stratification_row``。\n",
    ),
    (
        "    ⚠️ ``prescription`` 表**没有** ``label`` 列（Task 6 建表时就没加），而\n"
        "    ``assembly_snapshot`` 那 12 + 3 个键里**也没有**它（Task 5 用两条键集守卫钉死了那份\n"
        "    契约，P6-A2 已经为 ``previous_had_overrides`` 否掉过「往快照加键」这个方案）。\n"
        "    故标签只能从**同一天**的 ``stratification_result`` 读——两张表由同一个批次在同一个\n"
        "    SAVEPOINT 里写，那一行本该存在。**彻底修它要给 ``prescription`` 加一列\n"
        "    ``label_at_generation``**，那是改一张已结案的表（硬规矩 #11；本仓不做迁移 = 重建库），\n"
        "    已登记为关切交回控制者裁定。\n"
        "    \"\"\"\n",
        "    ⚠️ 标签**刻意不进** ``assembly_snapshot``：那 12 + 3 个键的契约被 Task 5 的两条键集\n"
        "    守卫钉死，而 P6-A2 已经为 ``previous_had_overrides`` 否掉过「往快照加键」这个方案\n"
        "    （快照的契约是「离线复算**本张**处方」，而「上一张处方生成当时的标签」是关于\n"
        "    **另一张**处方的事实）。故它住在处方行自己的列上。\n"
        "    \"\"\"\n",
    ),
    (
        "    rows = session.execute(\n"
        "        select(Prescription, models.StratificationResult.label)\n"
        "        .options(\n"
        "            load_only(\n"
        "                Prescription.student_id,\n"
        "                Prescription.generated_on,\n"
        "                Prescription.template_ref,\n"
        "                Prescription.microcycle_weeks,\n"
        "                Prescription.status,\n"
        "                Prescription.teacher_overrides,\n"
        "            )\n"
        "        )\n"
        "        .join(\n"
        "            latest,\n"
        "            (Prescription.student_id == latest.c.student_id)\n"
        "            & (Prescription.generated_on == latest.c.generated_on),\n"
        "        )\n"
        "        # outerjoin：标签缺失时仍要返回那一行，好让 _last_prescription_of 响亮失败，\n"
        "        # 而不是让这个人**静默**变成「没有上一张处方」→ 触发 1 → 又生成一张。\n"
        "        .outerjoin(\n"
        "            models.StratificationResult,\n"
        "            (models.StratificationResult.student_id == Prescription.student_id)\n"
        "            & (models.StratificationResult.computed_on == Prescription.generated_on),\n"
        "        )\n"
        "    ).all()\n"
        "    return {row.student_id: (row, label) for row, label in rows}\n",
        "    rows = session.execute(\n"
        "        select(Prescription)\n"
        "        .options(\n"
        "            load_only(\n"
        "                Prescription.student_id,\n"
        "                Prescription.generated_on,\n"
        "                Prescription.template_ref,\n"
        "                Prescription.microcycle_weeks,\n"
        "                Prescription.label_at_generation,\n"
        "                Prescription.status,\n"
        "                Prescription.teacher_overrides,\n"
        "            )\n"
        "        )\n"
        "        .join(\n"
        "            latest,\n"
        "            (Prescription.student_id == latest.c.student_id)\n"
        "            & (Prescription.generated_on == latest.c.generated_on),\n"
        "        )\n"
        "    ).scalars().all()\n"
        "    return {row.student_id: row for row in rows}\n",
    ),
    (
        "def _last_prescription_of(\n"
        "    pair: tuple[Prescription, str | None] | None\n"
        ") -> LastPrescription | None:\n",
        "def _last_prescription_of(row: Prescription | None) -> LastPrescription | None:\n",
    ),
    (
        "    ⚠️ ``microcycle_weeks`` 取**处方行**上那一份（Task 6 的 P6-A3 把它从模板快照下来），\n"
        "    不去读今天的模板：模板会改版，而触发 3 要判的是「**上一张**处方的周期到了没有」。\n"
        "\n"
        "    标签查不到就响亮失败（``ValueError``）：静默拿今天的标签去比会让触发 2 变成一个\n"
        "    每天都可能开火（或永远不开火）的假判据，而它决定「换不换处方」。\n"
        "\n"
        "    ⚠️ 它在**基础设施异常**那一侧（模块 docstring 的「异常分层」第 2 档）：\n"
        "    这里抛的 ``ValueError`` 会冒泡到 ``run_daily``、回滚整批。\n"
        "    \"\"\"\n"
        "    if pair is None:\n"
        "        return None\n"
        "    row, label = pair\n"
        "    if label is None:\n"
        "        raise ValueError(\n"
        "            f\"学生 {row.student_id} 在 {row.generated_on.isoformat()} 没有分层结果，\"\n"
        "            f\"而他当天有一张处方（id={row.id}）：触发 2 要比的是「生成当时的标签」，\"\n"
        "            f\"没有它就只能静默拿今天的标签去比，而那会让触发 2 变成一个每天都可能开火\"\n"
        "            f\"（或永远不开火）的假判据。两张表本该由同一批次在同一个 SAVEPOINT 里写\"\n"
        "        )\n"
        "    return LastPrescription(\n"
        "        generated_on=row.generated_on,\n"
        "        template_id=row.template_ref,\n"
        "        label_at_generation=label,\n",
        "    ⚠️ ``microcycle_weeks`` 取**处方行**上那一份（Task 6 的 P6-A3 把它从模板快照下来），\n"
        "    不去读今天的模板：模板会改版，而触发 3 要判的是「**上一张**处方的周期到了没有」。\n"
        "\n"
        "    ⚠️ ``label_at_generation`` **同理**取处方行上那一份（Task 7 fix round 1 的 F1-1）：\n"
        "    它是触发 2 判据的唯一输入，快照在行上才能离线复算（spec §4.3）。本列 **NOT NULL、\n"
        "    无缺省**，故**「标签查不到」那一档已经不存在了**——此前那个响亮失败的\n"
        "    ``ValueError``（以及它那条守卫\n"
        "    ``test_a_prescription_whose_stratification_row_is_gone_fails_loudly``）在加了本列之后\n"
        "    **结构上不可达**，已一并删掉；取代它的守卫是\n"
        "    ``test_trigger_2_survives_the_deletion_of_that_days_stratification_row``\n"
        "    （删掉那一天的分层行 → 触发 2 仍然成立）。于是本函数是一个**纯映射**、\n"
        "    不再碰库，也不再属于「基础设施异常」那一侧。\n"
        "    \"\"\"\n"
        "    if row is None:\n"
        "        return None\n"
        "    return LastPrescription(\n"
        "        generated_on=row.generated_on,\n"
        "        template_id=row.template_ref,\n"
        "        label_at_generation=row.label_at_generation,\n",
    ),
    (
        "    # 每人「当前那一张处方」与它生成当天的分层标签，**一次**批级预取（三个坑与实测数据\n"
        "    # 见 _previous_prescriptions 的 docstring：逐人查 / 整行加载 / 按 computed_on 单列过滤\n"
        "    # 各会让整学期回放多花几十秒）。\n",
        "    # 每人「当前那一张处方」（生成当时的标签就快照在那一行上），**一次**批级预取\n"
        "    # （三个坑与实测数据见 _previous_prescriptions 的 docstring：逐人查 / 整行加载 /\n"
        "    # 连第二张表，各会让整学期回放多花几十秒）。\n",
    ),
    (
        "        previous_pair = previous_index.get(student.id)\n"
        "        previous = None if previous_pair is None else previous_pair[0]\n",
        "        previous = previous_index.get(student.id)\n",
    ),
    (
        "                last_prescription=_last_prescription_of(previous_pair),\n",
        "                last_prescription=_last_prescription_of(previous),\n",
    ),
    (
        "                \"microcycle_weeks\": template.microcycle_weeks,\n",
        "                \"microcycle_weeks\": template.microcycle_weeks,\n"
        "                # fix round 1 的 F1-1：触发 2 判据的唯一输入。来源就是**当天刚写好的**\n"
        "                # stratification_result.label —— 它就在本循环手上的 result 里，\n"
        "                # 不需要任何额外查询。\n"
        "                \"label_at_generation\": label,\n",
    ),
], crlf=False)

# ---------------------------------------------------------------------------
# 3. tests/db/test_models.py（CRLF）
# ---------------------------------------------------------------------------
edit("tests/db/test_models.py", [
    (
        "    1. **有 CHECK 约束的列**——从 :func:`_in_domain` 生成的约束文本反解（今天 **17** 列：\n",
        "    1. **有 CHECK 约束的列**——从 :func:`_in_domain` 生成的约束文本反解（今天 **18** 列：\n",
    ),
    (
        "       ``review_status``、以及 **Task 6 新增的 ``prescription.status`` 与\n"
        "       ``weekly_adjustment.source``**）。\n",
        "       ``review_status``、**Task 6 新增的 ``prescription.status`` 与\n"
        "       ``weekly_adjustment.source``**、以及 **Task 7 fix round 1（F1-1）新增的\n"
        "       ``prescription.label_at_generation``**）。\n",
    ),
    (
        "        template_ref=\"RED-END-ABN-01\", microcycle_weeks=4,\n",
        "        template_ref=\"RED-END-ABN-01\", microcycle_weeks=4,\n"
        "        label_at_generation=\"red\",\n",
    ),
    (
        "def test_weekly_adjustment_source_check_rejects_unknown_values(session):\n",
        "def test_prescription_label_at_generation_shares_its_domain_with_the_label_column(session):\n"
        "    \"\"\"**F1-1（Task 7 fix round 1）**：``label_at_generation`` 与 ``stratification_result.label``\n"
        "    同口径——同宽（**20**）、同一个 CHECK 值域，且那个值域**只有一个所有者**。\n"
        "\n"
        "    本列是触发 2（``current_label != last_prescription.label_at_generation``）的唯一输入，\n"
        "    快照在处方行上才能离线复算（spec §4.3；理由逐字写在 ``Prescription`` 那一列的注释里）。\n"
        "    两处各持一份词表就是漂移的温床，故 ``_in_domain`` 的值域直接引\n"
        "    :attr:`M.StratificationResult.LABELS`——本条把这件事钉住：**两列的 CHECK 文本除了\n"
        "    列名以外逐字相同**，且两侧都不是从被测模块现拼的（硬规矩 #35：期望值字面写死）。\n"
        "\n"
        "    列宽对**字面量 20** 断言而不是互相比（互相比的话两列一起变窄也全绿），并对\n"
        "    **字面量 17** 断言「最长的那个真实值塞得下」——17 = ``len(\"insufficient_data\")``\n"
        "    （Ruling 144 的同一个值；SQLite 不强制长度，故溢出只在换严格后端时才炸、且炸在读侧）。\n"
        "    \"\"\"\n"
        "    column = Prescription.__table__.c.label_at_generation\n"
        "    assert column.nullable is False, \"触发 2 的判据不许为空：NULL 会让它静默不成立\"\n"
        "    assert column.default is None, \"也不得有缺省值：它必须是生成当时那个标签的显式快照\"\n"
        "    assert column.type.length == 20\n"
        "    assert M.StratificationResult.__table__.c.label.type.length == 20\n"
        "    longest = \"insufficient_data\"\n"
        "    assert len(longest) == 17\n"
        "    assert len(longest) <= column.type.length\n"
        "\n"
        "    checks = {c.name: str(c.sqltext) for c in Prescription.__table__.constraints\n"
        "              if type(c).__name__ == \"CheckConstraint\"}\n"
        "    label_checks = {c.name: str(c.sqltext)\n"
        "                    for c in M.StratificationResult.__table__.constraints\n"
        "                    if type(c).__name__ == \"CheckConstraint\"}\n"
        "    assert checks[\"ck_prescription_label_at_generation\"] == (\n"
        "        \"label_at_generation IN ('green', 'insufficient_data', 'red', 'yellow')\"\n"
        "    )\n"
        "    # 单一所有者：两列的值域部分逐字相同（同一个类常量生成的）\n"
        "    assert checks[\"ck_prescription_label_at_generation\"].split(\" IN \", 1)[1] == \\\n"
        "        label_checks[\"ck_stratification_result_label\"].split(\" IN \", 1)[1]\n"
        "\n"
        "    stu, run = _prescription_context(session)\n"
        "    fields = _prescription_fields(stu, run)\n"
        "    del fields[\"label_at_generation\"]\n"
        "    session.add(Prescription(**fields))\n"
        "    with pytest.raises(IntegrityError) as excinfo:\n"
        "        session.flush()\n"
        "    assert \"prescription.label_at_generation\" in str(excinfo.value)\n"
        "    session.rollback()\n"
        "\n"
        "    stu, run = _prescription_context(session)\n"
        "    session.add(Prescription(**_prescription_fields(stu, run, label_at_generation=\"blue\")))\n"
        "    with pytest.raises(IntegrityError) as excinfo:\n"
        "        session.flush()\n"
        "    assert \"ck_prescription_label_at_generation\" in str(excinfo.value)\n"
        "\n"
        "\n"
        "def test_weekly_adjustment_source_check_rejects_unknown_values(session):\n",
    ),
], crlf=True)

# ---------------------------------------------------------------------------
# 4. tests/pipeline/test_prescription_stage.py（LF）：删掉那条已不可达的守卫
# ---------------------------------------------------------------------------
OLD = '''def test_a_prescription_whose_stratification_row_is_gone_fails_loudly(bare):
    """触发 2 的比较对象（「生成当时的标签」）查不到时**响亮失败**，不静默拿今天的标签去比。

    ``prescription`` 表没有 ``label`` 列、``assembly_snapshot`` 那 15 个键里也没有它
    （Task 5 钉死了那份契约，P6-A2 已经为 ``previous_had_overrides`` 否掉过「往快照加键」），
    故标签只能从**同一天**的 ``stratification_result`` 读。那一行本该由同一个批次在同一个
    SAVEPOINT 里写下；它不在，说明有人手工清理过、或撞上了 Plan 01 Ruling 212 那个
    跨学期重放的形状。

    ⚠️ 静默退化的后果是**双向**的：拿今天的标签去比，触发 2 会变成一个每天都可能开火
    （天天换处方、教师覆盖天天被冲掉）或永远不开火（该换的不换）的假判据。
    **彻底修它要给 ``prescription`` 加一列 ``label_at_generation``**——那是改一张已结案的表
    （硬规矩 #11；本仓不做迁移 = 重建库），已登记为 Task 7 报告的关切。
    """
    session, sem = bare
    d2 = dt.date(2025, 9, 22)
    b1, b2 = _batch(session, sem, AS_OF), _batch(session, sem, d2)
    student = _student(session, "2025001001")
    _strat_row(session, student, AS_OF, b1, "red")
    assert _generate(session, sem, b1, AS_OF).generated == 1

    session.execute(
        delete(M.StratificationResult).where(M.StratificationResult.computed_on == AS_OF)
    )
    session.flush()
    _strat_row(session, student, d2, b2, "yellow")

    with pytest.raises(ValueError) as exc:
        _generate(session, sem, b2, d2)
    assert "没有分层结果" in str(exc.value)
    assert "触发 2" in str(exc.value)


'''
NEW = '''# ⚠️ 这里原有一条 ``test_a_prescription_whose_stratification_row_is_gone_fails_loudly``
# （Task 7 首轮交付）：它钉的是「触发 2 的比较对象查不到时响亮抛 ``ValueError``」，
# 而那个失效形态的前提是「标签只能 ``outerjoin`` 回读同一天的 ``stratification_result``」。
# **fix round 1 的 F1-1 给 ``prescription`` 加了 ``label_at_generation`` 列**（判定输入快照
# 在处方行上，与 P6-A3 给 ``microcycle_weeks`` 快照同构），该前提消失 → 那个 ``ValueError``
# 分支**结构上不可达**，守卫随之删掉。取代它的是 B5 节的
# ``test_trigger_2_survives_the_deletion_of_that_days_stratification_row``：同一个数据形状
# （删掉那一天的分层行），断言的是**相反**的结论——触发 2 仍然成立、整批不回滚。


'''
edit("tests/pipeline/test_prescription_stage.py", [(OLD, NEW)], crlf=False)

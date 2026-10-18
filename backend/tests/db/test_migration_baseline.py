"""迁移链的一致性：``alembic upgrade head`` 建出来的库 == ``create_all`` 建出来的库。

--------------------------------------------------------------------------
为什么这个文件存在（Plan 06 Task 1 的**核心判据**）
--------------------------------------------------------------------------

Plan 06 之前，本仓的建表只有一条路：``Base.metadata.create_all``。Plan 06 Task 1 引入
``alembic`` 之后变成了**两条**：磁盘库走 ``backend/migrations/versions/`` 那条迁移链，
内存库（= 全部 1340 条测试走的那一档）仍然走 ``create_all``。

于是「迁移写得对不对」这件事**不能靠人眼看 diff**：那条基线迁移是 566 行、26 张表、
255 个列、9 个索引、21 条唯一约束、41 条外键、29 条 CHECK，而人眼在 30 KB 的自动生成
代码里漏掉一个 ``unique=True`` 是必然事件、不是意外事件。本文件的
:func:`test_alembic_upgrade_head_and_create_all_agree_table_by_table` 就是那把尺子：
它把两侧**各自建成一个真的库**、再用 :func:`sqlalchemy.inspect` 反射回来做规范化比较，
逐表、逐列（名/类型/可空/默认）、逐索引、逐唯一约束、逐外键（另加主键与 CHECK）。

⚠️ **两侧都是「反射回来的结构」，这一点是承重的**：比较的两边都经过 SQLite 的
DDL 渲染与 SQLAlchemy 的反射，于是 ``VARCHAR`` vs ``VARCHAR(64)`` 这类
「同一件事的两种写法」在两侧会以同一种写法出现，比较因此不会因渲染差异假红。
「模型侧的类型串」与「反射侧的类型串」是否也对得上，由
:func:`test_the_migrated_database_matches_base_metadata_table_by_table` 另外钉
（那一条拿 ``col.type.compile(dialect=sqlite.dialect())`` 与 ``str(insp_col["type"])``
比，是**跨口径**的比较，故它单独一条、不与前一条合并）。

--------------------------------------------------------------------------
本文件同时钉住 ``init_db`` 的**四条路径**
--------------------------------------------------------------------------

:func:`app.db.session.init_db` 的三档 + 一条快路径各有一条集成测试，全部用
``tmp_path`` 下的**临时磁盘库**（⚠️ 一个字节都不落进 ``backend/``：``backend/pe.db``
是禁区、``backend/data/**`` 一个字节不许动）：

* 快路径（内存 SQLite）—— :func:`test_init_db_on_memory_sqlite_never_touches_the_chain`
  与 :func:`test_the_memory_fast_path_agrees_with_the_migration_path`
* 档 1（文件不存在 → ``upgrade head``）——
  :func:`test_init_db_creates_a_missing_database_through_the_migration_chain`
* 档 1b（0 字节文件当新库）——
  :func:`test_init_db_treats_a_zero_length_file_as_a_new_database`
* 档 2（旧库无版本表 → 比对 + ``stamp`` 基线，**不丢数据**）——
  :func:`test_init_db_stamps_a_legacy_database_and_keeps_its_rows`
  与它的失败方向 :func:`test_init_db_refuses_to_stamp_a_database_that_is_not_the_baseline`
* 档 3（已有版本表 → 幂等 ``upgrade head``）——
  :func:`test_init_db_is_idempotent_on_an_already_versioned_database`

⚠️ **测试档走 ``create_all``、生产档走 alembic，这个不对称是本文件存在的唯一理由**：
只要 :func:`test_alembic_upgrade_head_and_create_all_agree_table_by_table` 绿，
「1340 条测试验的那个 schema」与「甲方现场建出来的那个 schema」就是同一个东西；
它一红，那个不对称立刻从「性能取舍」变成「测试在验一个不存在的库」。
（实测代价：让每条测试都跑一次 ``upgrade head`` 会给 132 秒的套件加上分钟级的开销，
而一次 ``upgrade head`` 实测约 0.4 秒 × 上千个夹具。）
"""
import pytest
from sqlalchemy import create_engine, inspect, make_url, text
from sqlalchemy.dialects import sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from app.db import models as M  # noqa: F401  仅为把 29 张表注册进 Base.metadata
from app.db.session import (
    ALEMBIC_INI,
    ALEMBIC_VERSION_TABLE,
    Base,
    _alembic_config,
    _db_file_of,
    init_db,
)

#: 基线迁移的修订号。**字面量**（硬规矩 #35：期望值不从被测代码读回来跟自己比）。
#: 实际值现算自 ``backend/migrations/versions/``（``ScriptDirectory.get_base()``），
#: 两侧不同源，故「有人重新生成了一遍基线、修订号变了」会当场红——那是**要的**：
#: 基线修订号是 :func:`app.db.session._stamp_unversioned` 往甲方旧库里写的那个值，
#: 它悄悄变了就意味着「已经被 stamp 过的库」与「即将被 stamp 的库」写着两个不同的号。
BASELINE_REVISION = "53e5a548c40e"

#: 迁移链**头**的修订号（Plan 06 Task 3 起它不再等于基线）。同样是**字面量**。
#:
#: ⚠️ **为什么要两个修订号字面量而不是「head 从 ``get_heads()`` 读回来」**：
#: 这两格答的是两个不同的问题。``BASELINE_REVISION`` 答「:func:`app.db.session._stamp_unversioned`
#: 往甲方旧库里写的那一个号是哪个」——它必须**永远**是基线，与链有多长无关；
#: ``HEAD_REVISION`` 答「一条全新的库 ``upgrade head`` 之后应当停在哪个号」。
#: 从 ``get_heads()`` 读回来跟自己比是同源断言，它证明不了「链没有意外分叉」、
#: 也证明不了「新加的这条迁移真的被挂到了链的末端」（一个 ``down_revision`` 写错的
#: 迁移会造出**两个**头，而 ``get_heads()`` 那一侧会照样把两个都报出来）。
#: ⚠️ 于是「有人新加了一条迁移」会**当场红**在本文件的两处
#: （:data:`HEAD_REVISION` 与 :func:`test_the_chain_has_exactly_one_head_today`），
#: 而那正是**要的**：改这两格的人正好是应当去读 spec §13.7 那个人。
#: ⚠️ **Plan 06 Task 5 把它从 ``0b7da3d20211`` 抬到 ``7f3923d8af84``**（第三条迁移，
#: 加 ``audit_log`` 一张表）。⚠️ 而 :data:`BASELINE_REVISION` **一个字都没动**
#: ——那正是上面那一条要防的失效形态。
#: ⚠️ **Plan 06 Task 11 是同一件事的第三次**：抬到 ``0ac943e0da9b``（第四条迁移，
#: ``login_attempt.login`` 的列宽 ``VARCHAR(32)`` → ``VARCHAR(64)``）。
#: ⚠️⚠️ 那一条与前三条**形状不同**，故它把本文件的两格分开了：前三条各自**加一张表**
#: （26 → 27 → 28），第四条**一张表都不加**（仍然 28），它只改一列的**类型**。
#: 于是 :data:`EXPECTED_TABLES` / :data:`EXPECTED_TABLE_COUNT_WITH_VERSION` /
#: 下面那五个规模字面量**一格都没变**，变的只有 :data:`HEAD_REVISION` 与
#: :func:`test_the_chain_has_exactly_one_head_today` 里的修订数。
#: ⚠️ 而它**能被 autogenerate 看见**全靠 ``migrations/env.py`` 的 ``compare_type = True``
#: （那个开关的 docstring 举的例子逐字就是「把 ``String(32)`` 改成 ``String(64)``」）。
HEAD_REVISION = "a1af54889103"

#: **30** 张表的名字。**字面量**，与 ``tests/db/test_models.py`` 的 ``expected`` 集合
#: 同值但**刻意各写一份**：那一份钉的是「模型声明了这 30 张」，本份钉的是
#: 「迁移链建出了这 30 张」。两侧同源（都从 ``Base.metadata`` 读）的话，
#: 「基线漏了一张表」这件事就永远抓不到。
#: ⚠️ Plan 06 Task 3 加了 ``login_attempt``（第 27 张，住在 ``models/auth.py``，
#: 由**第二条**迁移 ``0b7da3d20211`` 建，**不在基线里**）；
#: **Plan 06 Task 5 加了 ``audit_log``（第 28 张，住在 ``models/audit.py``，
#: 由第三条迁移 ``7f3923d8af84`` 建，同样不在基线里）**——
#: **Plan 08 Task 1 加了 ``read_audit_log``（第 29 张，⚠️ 与 ``audit_log`` 同住
#: ``models/audit.py``，由第五条迁移 ``03331a689ee4`` 建，同样不在基线里）**——
#: **Plan 08 Task 4 加了 ``bind_token``（第 30 张，⚠️ 与 ``user_session`` /
#: ``login_attempt`` 同住 ``models/auth.py``，由第六条迁移 ``a1af54889103`` 建，
#: 同样不在基线里）**——
#: 故本集合钉的是「**整条链**建出这 30 张」，不是「基线建出这 26 张」。
EXPECTED_TABLES = frozenset({
    "semester", "teacher", "student", "course_section", "enrollment",
    "fitness_test_batch", "fitness_test_result", "body_composition",
    "interest_survey", "percentile_snapshot", "derived_metrics",
    "stratification_result", "daily_sync_run", "cleaning_log", "exercise",
    "prescription_template", "prescription", "weekly_adjustment",
    "class_session", "rpe_record", "training_log", "mini_test", "alert",
    "notification", "weekly_class_report", "user_session", "login_attempt",
    "audit_log", "read_audit_log", "bind_token",
})

#: 迁移建出来的库里应当有的表数 = **30** 张业务表 + 1 张 ``alembic_version``。
EXPECTED_TABLE_COUNT_WITH_VERSION = 31

# 下面五个规模字面量都是**把 30 张表逐个加总**得到的（Plan 06 Task 1 实测于 26 张，
# 命令与逐表明细见 task-1-2-report.md 的 §2；Task 3 加 ``login_attempt`` 一张，
# 带来 **6** 列（id / kind / login / ok / at / ip）、**1** 个索引
# （``ix_login_attempt_kind_login_at``，全库第一个复合索引）、**1** 条 CHECK
# （``ck_login_attempt_kind``）、**0** 个唯一约束与 **0** 个外键，
# 故 255→261 / 9→10 / 21 不变 / 41 不变 / 29→30；
# **Task 5 加 ``audit_log`` 一张，带来 9 列（id / at / subject_kind / subject_id /
# staff_no / method / path / status / target）、1 个索引
# （``ix_audit_log_subject_kind_at``，全库第二个复合索引）、1 条 CHECK
# （``ck_audit_log_subject_kind``）、0 个唯一约束与 0 个外键**（``subject_id`` 刻意
# 不是外键，逐字理由见 ``app/db/models/audit.py`` 的模块 docstring 第二节），
# 故 261→270 / 10→11 / 21 不变 / 41 不变 / 30→31；
# **Plan 08 Task 1 加 ``read_audit_log`` 一张（9 列 / 1 个索引 / 1 条 CHECK），
# 故 …→279 / …→12 / 21 不变 / 41 不变 / …→32**；
# ⚠️⚠️ **Plan 08 Task 4 加 ``bind_token`` 一张，带来 9 列（id / token_id / token_hash /
# kind / login / issued_at / expires_at / used_at / issued_by）、1 个索引
# （``ix_bind_token_kind_login_expires_at``，全库**第四个**复合索引）、
# **1 个唯一约束**（``token_id`` —— ⚠️ 本仓**第 22 个**，也是 ``user_session`` 的
# 主键之外第一个「靠唯一约束承载安全不变量」的一格：两行共用一个选择子会让
# ``find`` 返回不确定的那一行）、1 条 CHECK（``ck_bind_token_kind``）与 0 个外键**
# （``login`` 存的是学号/工号**原文**，而多态外键在 SQL 里不存在），
# 故 279→**288** / 12→**13** / 21→**22** / 41 不变 / 32→**33**）。
# ⚠️ 它们是 :func:`_normalized_schema` 那六维比较的
# **空转守卫**：比较函数指错目录 / 反射到空库时，两侧的字典都是空的、逐格比较一条
# 差异也报不出来，于是「假绿」与「真一致」在颜色上无法区分。这五个数把「两侧都真的
# 有东西」钉住。
EXPECTED_COLUMN_COUNT = 288
EXPECTED_INDEX_COUNT = 13
EXPECTED_UNIQUE_COUNT = 22
EXPECTED_FOREIGN_KEY_COUNT = 41
EXPECTED_CHECK_CONSTRAINT_COUNT = 33

#: 那 21 个 JSON 形态的列在 DDL 里一律落 ``TEXT``（:class:`app.db.models._shared.JsonText`
#: 的 ``impl = Text``）。⚠️ 这一格是**跨口径**比较里最容易漂的一个：``JsonText`` 是
#: ``TypeDecorator``，autogenerate 会把它渲染成 ``app.db.models._shared.JsonText()``
#: 这个限定名（且**不生成 import**，见基线迁移的模块 docstring），而反射回来是 ``TEXT``。
EXPECTED_JSON_TEXT_TYPE = "TEXT"


def _normalized_schema(insp) -> dict[str, dict[str, tuple]]:
    """把一个**已建好**的库规范化成可逐格比较的结构（六个维度）。

    ⚠️ ``alembic_version`` 一律剔除：它只存在于迁移那一侧（``create_all`` 不建它），
    留着就会成为一条**恒定的**假差异，而下一个人「修」它的办法是把它加进
    ``Base.metadata``——那才是真的坏。

    六维各自规范化成什么：

    * ``columns`` —— ``(列名, 类型串, 可空, 缺省)`` 的**有序**元组（列序是有意义的：
      SQLite 的 ``INSERT`` 不带列名时按位置对，``demo_bootstrap.py`` 与三个 CLI 都
      写 CSV/SQL，列序漂了不会报错、只会串列）；
    * ``indexes`` / ``unique`` / ``checks`` —— 排序后的元组（这三样在 DDL 里无序，
      不排序就会因为 alembic 与 ``create_all`` 的**生成顺序**不同而假红）；
    * ``foreign_keys`` —— 排序后的 ``(本表列, 被引表, 被引列, ondelete, onupdate)``；
      ⚠️ ``ondelete`` 必须进来：``notification`` 的两条外键是 ``ON DELETE SET NULL``，
      漏掉它的话「迁移把级联语义丢了」这一档抓不到；
    * ``primary_key`` —— 主键列的元组。

    类型串一律 ``str(...).upper()`` 并把连续空白折成一个：反射回来的写法两侧同源
    （都是 SQLite 的 DDL 渲染），故这一层规范化只是防「大小写/空白」这类噪声，
    不试图把 ``VARCHAR`` 与 ``VARCHAR(64)`` 当成同一个东西——**那 two 是不同的类型**，
    把它们折成一个正是本文件要抓的失效。
    """
    out: dict[str, dict[str, tuple]] = {}
    for name in sorted(insp.get_table_names()):
        if name == ALEMBIC_VERSION_TABLE:
            continue
        out[name] = {
            "columns": tuple(
                (
                    column["name"],
                    " ".join(str(column["type"]).split()).upper(),
                    bool(column["nullable"]),
                    column.get("default"),
                )
                for column in insp.get_columns(name)
            ),
            "indexes": tuple(sorted(
                (index["name"], tuple(index["column_names"]), bool(index["unique"]))
                for index in insp.get_indexes(name)
            )),
            "unique": tuple(sorted(
                (uq["name"], tuple(uq["column_names"]))
                for uq in insp.get_unique_constraints(name)
            )),
            "foreign_keys": tuple(sorted(
                (
                    tuple(fk["constrained_columns"]),
                    fk["referred_table"],
                    tuple(fk["referred_columns"]),
                    fk["options"].get("ondelete"),
                    fk["options"].get("onupdate"),
                )
                for fk in insp.get_foreign_keys(name)
            )),
            "primary_key": tuple(insp.get_pk_constraint(name)["constrained_columns"]),
            "checks": tuple(sorted(
                (" ".join((ck["sqltext"] or "").split()).upper(), ck["name"])
                for ck in insp.get_check_constraints(name)
            )),
        }
    return out


@pytest.fixture(scope="module")
def migrated(tmp_path_factory):
    """``alembic upgrade head`` 建出来的那个磁盘库（**整个模块只建一次**）。

    module 级是刻意的：一次 ``upgrade head`` 实测约 0.4 秒，而本文件有六条测试要用它。
    ⚠️ 库落在 ``tmp_path_factory`` 下（pytest 的临时目录），**不在 ``backend/`` 里**。
    """
    path = tmp_path_factory.mktemp("migrated") / "migrated.db"
    url = "sqlite:///" + path.as_posix()
    from alembic import command

    command.upgrade(_alembic_config(url), "head")
    eng = create_engine(url)
    yield {"url": url, "path": path, "engine": eng, "schema": _normalized_schema(inspect(eng))}
    eng.dispose()


@pytest.fixture(scope="module")
def created(migrated, tmp_path_factory):
    """``Base.metadata.create_all`` 建出来的那个磁盘库（**整个模块只建一次**）。

    ⚠️ 用磁盘库而不是内存库：内存 SQLite 的 ``sqlite://`` 是「每条连接一个独立的库」，
    ``create_all`` 与 ``inspect`` 若不在同一条连接上就会看到两个不同的库
    （``app.main._build_engine`` 的 docstring 逐字交代了这件事）。磁盘库没有这个坑，
    而本文件要比的正是「结构」，与连接池无关。
    """
    path = tmp_path_factory.mktemp("created") / "created.db"
    eng = create_engine("sqlite:///" + path.as_posix())
    Base.metadata.create_all(eng)
    yield {"url": "sqlite:///" + path.as_posix(), "path": path,
           "engine": eng, "schema": _normalized_schema(inspect(eng))}
    eng.dispose()


# ---------------------------------------------------------------------------
# 迁移链自身的形状
# ---------------------------------------------------------------------------

def test_the_baseline_revision_literal_is_the_only_base_of_the_chain():
    """钉住 :data:`BASELINE_REVISION`：它就是 ``migrations/versions/`` 里那个唯一的起点。

    ⚠️ 这一条同时是**空转守卫**：``versions/`` 被搬空时 ``get_base()`` 返回 ``None``
    （于是本条红），迁移链分叉成两个起点时它抛 ``alembic.util.CommandError``
    （于是本条炸）——两种都不会假绿。
    """
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_alembic_config("sqlite://"))
    assert script.get_base() == BASELINE_REVISION
    # 一条链只能有一个起点：分叉且两支都没有 down_revision 时 get_base() 会抛，
    # 这里再显式数一遍，让「为什么只许一个」这件事有个断言可看。
    assert script.get_bases() == [BASELINE_REVISION]


def test_the_chain_has_exactly_one_head_today():
    """今天这条链**只有一个头**，而且它是 :data:`HEAD_REVISION`（= 第 **4** 条迁移）。

    ⚠️ **Plan 06 Task 3 兑现了本条 docstring 此前写下的那句预告**——它逐字是
    「本条会在下一条迁移落地时红，那是**要的**：改这条断言的人正好是应当去读
    spec §13.7 那个人（他要确认自己写的是『加一条 revision』而不是『重生成基线』）」。
    落地时改的是两格：``heads`` 的期望值从 ``[BASELINE_REVISION]`` 换成
    ``[HEAD_REVISION]``，修订数从 ``1`` 换成 ``2``。
    ⚠️ **Plan 06 Task 5 是同一件事的第二次**：修订数 ``2`` → ``3``、
    ``HEAD_REVISION`` ``0b7da3d20211`` → ``7f3923d8af84``，两格都红了、都按事实改了。
    ⚠️ **Plan 06 Task 11 是第三次**：修订数 ``3`` → ``4``、``HEAD_REVISION``
    ``7f3923d8af84`` → ``0ac943e0da9b``（改 ``login_attempt.login`` 的列宽，
    ⚠️ **不加表**，故本文件的表数与五个规模字面量一格都没动）。
    ⚠️ **基线那一个字面量一个字都没动**（:data:`BASELINE_REVISION` 仍是
    ``53e5a548c40e``，且 :func:`test_the_baseline_revision_literal_is_the_only_base_of_the_chain`
    仍钉着「它就是链的唯一一起点」）——这正是那一条要防的失效形态：
    「重新生成一遍基线」会让已经被 stamp 过的甲方库与即将被 stamp 的库写着两个不同的号。
    ⚠️ **函数名里的 ``one_head`` 指的是「一个头」、不是「一条迁移」**：
    链长成 N 条时仍然只该有一个头，而两个头意味着分叉（``init_db`` 的
    ``upgrade head`` 在分叉时会当场抛 ``CommandError``，但那是一个离真因很远的报错）。
    ⚠️ ``get_heads()`` 返回的是 ``list``（不是 tuple），故期望侧也写 list。
    """
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_alembic_config("sqlite://"))
    heads = script.get_heads()
    assert heads == [HEAD_REVISION], heads
    assert len(list(script.walk_revisions())) == 6
    # ⚠️ 反空转的第三拍：基线**仍然是**那个唯一的起点，且它不是头
    #    （少了本行，「有人把四条迁移压成一条新的基线」会让上面两格同时成立）。
    assert script.get_base() == BASELINE_REVISION
    assert BASELINE_REVISION != HEAD_REVISION


def test_the_migrated_database_carries_the_version_table_at_the_head(migrated):
    """档 1 建出来的库**一出生就带着** ``alembic_version``，且写着**头**的修订号。

    ⚠️ 函数名此前是 ``…at_the_baseline``——那在链只有一条迁移时为真（基线 == 头），
    Plan 06 Task 3 加了第二条之后两格分开了，故按事实改名（硬规矩 #66）。

    ⚠️ 这一格是整条纪律的地基：新库若不写版本表，它下次开库时就会落进
    :func:`app.db.session.init_db` 的**档 2**（stamp），而 stamp 那一档的前提是
    「这是一个引入迁移链之前的旧库」——前提错了，比对就会替它兜住（结构相等时
    stamp 是幂等的），但那份开销与那份混淆都是白付的。
    ⚠️⚠️ **而 Plan 06 Task 3 之后前提错了兜不住了**：一个「其实是新库、只是没写版本表」
    的库，其结构是 **head** 的（29 张表），而档 2 比对的是**基线**（26 张表），
    于是 :func:`app.db.session._assert_shape_matches_revision` 会抛
    「多表 ['audit_log', 'login_attempt']」
    ——响亮，但报错离真因有一层。故本条从「省一份开销」升级成「不让服务起不来」。
    ⚠️ **Plan 06 Task 5 又把那一格抬了一格**（head 从 27 张涨到 28 张、
    「多表」清单从 1 个名字涨到 2 个），而基线**仍然是 26 张**（第三条迁移同样
    只往链尾加，一个字都没回头改基线）。
    """
    insp = inspect(migrated["engine"])
    assert insp.has_table(ALEMBIC_VERSION_TABLE)
    with migrated["engine"].connect() as conn:
        rows = conn.execute(text(f"SELECT version_num FROM {ALEMBIC_VERSION_TABLE}")).all()
    assert [row[0] for row in rows] == [HEAD_REVISION]
    assert len(insp.get_table_names()) == EXPECTED_TABLE_COUNT_WITH_VERSION


# ---------------------------------------------------------------------------
# 核心判据：两侧结构逐格一致
# ---------------------------------------------------------------------------

def test_alembic_upgrade_head_and_create_all_agree_table_by_table(migrated, created):
    """**本 Task 的核心判据**：迁移建出来的库与 ``create_all`` 建出来的库逐格一致。

    比较六个维度（:func:`_normalized_schema`）：列（名/类型/可空/缺省，**含列序**）、
    索引、唯一约束、外键（含 ``ondelete`` / ``onupdate``）、主键、CHECK 约束。
    ⚠️ 后两维**超出**计划正文点名的清单（计划写的是「逐表逐列逐索引」）：
    主键漂了会让 ``repo.upsert`` 的 ``ON CONFLICT`` 目标错掉，而 29 条 CHECK 是
    本仓「枚举取值域两处设防」的 SQL 那一半（:mod:`app.db.models` 的约定 2）——
    ``autogenerate`` **会**渲染 CHECK（实测 29/29 都在基线里），但没有人盯的话，
    下一个重新生成基线的人不会知道这一格是承重的。

    失败消息把差异**逐表逐维**列出来，而不是甩两个 30 KB 的字典。
    """
    left, right = migrated["schema"], created["schema"]

    assert set(left) == EXPECTED_TABLES, sorted(set(left) ^ EXPECTED_TABLES)
    assert set(right) == EXPECTED_TABLES, sorted(set(right) ^ EXPECTED_TABLES)

    diffs: list[str] = []
    for name in sorted(EXPECTED_TABLES):
        for dimension in ("columns", "indexes", "unique", "foreign_keys",
                          "primary_key", "checks"):
            if left[name][dimension] != right[name][dimension]:
                diffs.append(
                    f"{name}.{dimension}\n"
                    f"    alembic    : {left[name][dimension]}\n"
                    f"    create_all : {right[name][dimension]}"
                )
    assert not diffs, "迁移建出来的库与 create_all 建出来的库不一致：\n  " + "\n  ".join(diffs)


def test_the_scale_literals_hold_on_both_sides(migrated, created):
    """五个规模字面量在**两侧**都成立（:func:`_normalized_schema` 那六维的空转守卫）。

    ⚠️ 少了本条，上面那条逐格比较在「两侧都反射到空库」时同样全绿。
    """
    for label, side in (("alembic", migrated), ("create_all", created)):
        schema = side["schema"]
        assert len(schema) == len(EXPECTED_TABLES)
        assert sum(len(t["columns"]) for t in schema.values()) == EXPECTED_COLUMN_COUNT, label
        assert sum(len(t["indexes"]) for t in schema.values()) == EXPECTED_INDEX_COUNT, label
        assert sum(len(t["unique"]) for t in schema.values()) == EXPECTED_UNIQUE_COUNT, label
        assert sum(len(t["foreign_keys"]) for t in schema.values()) == \
            EXPECTED_FOREIGN_KEY_COUNT, label
        assert sum(len(t["checks"]) for t in schema.values()) == \
            EXPECTED_CHECK_CONSTRAINT_COUNT, label


def test_the_migrated_database_matches_base_metadata_table_by_table(migrated):
    """迁移建出来的库 vs ``Base.metadata``：**逐表**核对列数/索引/唯一/外键/CHECK。

    ⚠️ 这一条与上面那条**不重叠**：上面比的是「两个反射回来的库」，本条比的是
    「反射回来的库」与「模型侧的元数据对象」——跨口径，故类型串要走
    ``col.type.compile(dialect=sqlite.dialect())``（``JsonText`` 这个 ``TypeDecorator``
    在模型侧编译成 ``TEXT``、反射回来也是 ``TEXT``，两侧才对得上）。
    计划正文要的「逐表核对生成的 migration 与 ``Base.metadata`` 是否一致」就是本条。
    """
    insp = inspect(migrated["engine"])
    dialect = sqlite.dialect()
    diffs: list[str] = []
    counts = {"columns": 0, "indexes": 0, "unique": 0, "foreign_keys": 0, "checks": 0}

    assert sorted(insp.get_table_names()) == sorted(set(Base.metadata.tables) |
                                                    {ALEMBIC_VERSION_TABLE})

    for name in sorted(Base.metadata.tables):
        table = Base.metadata.tables[name]
        want_columns = [
            (
                column.name,
                " ".join(str(column.type.compile(dialect=dialect)).split()).upper(),
                bool(column.nullable),
            )
            for column in table.columns
        ]
        got_columns = [
            (
                column["name"],
                " ".join(str(column["type"]).split()).upper(),
                bool(column["nullable"]),
            )
            for column in insp.get_columns(name)
        ]
        if want_columns != got_columns:
            for want, got in zip(want_columns, got_columns):
                if want != got:
                    diffs.append(f"{name}: metadata={want} 迁移库={got}")
            if len(want_columns) != len(got_columns):
                diffs.append(
                    f"{name}: 列数 metadata={len(want_columns)} 迁移库={len(got_columns)}"
                )
        counts["columns"] += len(want_columns)
        pairs = (
            ("indexes", len(table.indexes), len(insp.get_indexes(name))),
            ("unique",
             len([c for c in table.constraints
                  if c.__class__.__name__ == "UniqueConstraint"]),
             len(insp.get_unique_constraints(name))),
            ("foreign_keys",
             len([c for c in table.constraints
                  if c.__class__.__name__ == "ForeignKeyConstraint"]),
             len(insp.get_foreign_keys(name))),
            ("checks",
             len([c for c in table.constraints
                  if c.__class__.__name__ == "CheckConstraint"]),
             len(insp.get_check_constraints(name))),
        )
        for dimension, want, got in pairs:
            counts[dimension] += want
            if want != got:
                diffs.append(f"{name}.{dimension}: metadata={want} 迁移库={got}")

    assert not diffs, "迁移建出来的库与 Base.metadata 不一致：\n  " + "\n  ".join(diffs)
    # 规模字面量再对一遍（这一侧是 metadata，不是反射）
    assert counts["columns"] == EXPECTED_COLUMN_COUNT
    assert counts["indexes"] == EXPECTED_INDEX_COUNT
    assert counts["unique"] == EXPECTED_UNIQUE_COUNT
    assert counts["foreign_keys"] == EXPECTED_FOREIGN_KEY_COUNT
    assert counts["checks"] == EXPECTED_CHECK_CONSTRAINT_COUNT


def test_the_json_text_columns_land_as_text_on_both_sides(migrated, created):
    """那 **21** 个 :class:`~app.db.models._shared.JsonText` 列在两侧都落 ``TEXT``。

    ⚠️ 单独一条的理由：``JsonText`` 是本仓唯一自定义的 ``TypeDecorator``，
    而它是 autogenerate 唯一渲染不出来的东西（基线迁移里那 21 处
    ``app.db.models._shared.JsonText()`` 全靠一句**手工补的** import 才不 ``NameError``）。
    「21」这个数与 ``tests/db/test_models.py`` 的 ``len(json_text_columns) == 21``
    是同一件事的两面，故这里从**模型侧**数、在**两个库**上各验一遍。
    """
    json_columns = {
        (table.name, column.name)
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, M.JsonText)
    }
    assert len(json_columns) == 21, sorted(json_columns)

    for label, side in (("alembic", migrated), ("create_all", created)):
        for table_name, column_name in sorted(json_columns):
            got = dict(
                (item[0], item[1]) for item in side["schema"][table_name]["columns"]
            )[column_name]
            assert got == EXPECTED_JSON_TEXT_TYPE, f"{label}: {table_name}.{column_name}={got}"


def test_the_check_constraints_have_teeth_on_the_migrated_database(migrated):
    """迁移建出来的库上，SQL 层的取值域约束**真的挡得住**（不是只写在 DDL 里好看）。

    ⚠️ 这一条验的是 :mod:`app.db.models` 约定 2 的**后半句**在迁移路径上仍然成立：
    「每个枚举式列都同时给出类常量集合与 SQL 层 ``CheckConstraint``」。
    ``create_all`` 那一侧早就有 ``tests/db/test_models.py`` 的一组测试盯着，
    而迁移那一侧今天之前**一条都没有**——一个漏掉 CHECK 的基线会让「绕过 ORM 直接写库」
    （``demo_bootstrap.py`` 与任何将来的运维脚本都是那个形状）把脏值写进去且不报错。
    """
    eng = migrated["engine"]
    good = ("INSERT INTO exercise (ref, name, video_url, impact_level, targets, equipment) "
            "VALUES ('probe-ok', '探针', 'https://example.invalid/x', 'high', '[]', 'none')")
    bad = good.replace("'probe-ok'", "'probe-bad'").replace("'high'", "'sideways'")

    try:
        with eng.begin() as conn:
            conn.execute(text(good))
        with pytest.raises(IntegrityError):
            with eng.begin() as conn:
                conn.execute(text(bad))
        # 那一行脏值确实没进去（IntegrityError 是**数据库**抛的，不是 SQLAlchemy 提前拦的）
        with eng.connect() as conn:
            assert conn.execute(
                text("SELECT count(*) FROM exercise WHERE ref = 'probe-bad'")
            ).scalar() == 0
    finally:
        # ⚠️ ``migrated`` 是 **module 级**夹具，本文件后面还有测试要用它；
        #    把探针行删掉，别让一条测试给下一条留状态。
        with eng.begin() as conn:
            conn.execute(text("DELETE FROM exercise WHERE ref LIKE 'probe-%'"))


# ---------------------------------------------------------------------------
# init_db 的四条路径（集成，全部用 tmp_path 下的临时磁盘库）
# ---------------------------------------------------------------------------

def test_init_db_creates_a_missing_database_through_the_migration_chain(tmp_path):
    """**档 1**：文件不存在 → ``alembic upgrade head``，新库一出生就带版本表。"""
    path = tmp_path / "fresh.db"
    assert not path.exists()
    eng = create_engine("sqlite:///" + path.as_posix())

    init_db(eng)

    assert path.exists() and path.stat().st_size > 0
    insp = inspect(eng)
    assert insp.has_table(ALEMBIC_VERSION_TABLE)
    with eng.connect() as conn:
        assert conn.execute(
            text(f"SELECT version_num FROM {ALEMBIC_VERSION_TABLE}")
        ).scalar() == HEAD_REVISION
    assert set(insp.get_table_names()) == set(EXPECTED_TABLES) | {ALEMBIC_VERSION_TABLE}
    eng.dispose()


def test_init_db_treats_a_zero_length_file_as_a_new_database(tmp_path):
    """**档 1b**：0 字节的库文件当新库建，**不**落进档 2 的比对。

    ⚠️ 这一格是实测补出来的：SQLite 自己就把「零长度文件」当成「一个空库」，
    而上一次进程被杀在 ``CREATE TABLE`` 中途正好留下这么一个文件。不认它的话，
    档 2 的结构比对会看到 0 张表、抛「结构不等于基线」，而正确的处置明明是
    「当新库建」——一个 0 字节文件把服务卡在起不来的状态上，是这一格不认的代价。
    """
    path = tmp_path / "zero.db"
    path.write_bytes(b"")
    assert path.stat().st_size == 0
    eng = create_engine("sqlite:///" + path.as_posix())

    init_db(eng)

    insp = inspect(eng)
    assert insp.has_table(ALEMBIC_VERSION_TABLE)
    assert set(insp.get_table_names()) == set(EXPECTED_TABLES) | {ALEMBIC_VERSION_TABLE}
    eng.dispose()


def test_init_db_stamps_a_legacy_database_and_keeps_its_rows(tmp_path):
    """**档 2**：``create_all`` 出来的旧库（无版本表）被就地纳管，**一行数据都不丢**。

    这一条就是「甲方现场升级版本时不能丢数据」那个需求本身的可执行判据：
    旧库是**改前**那版代码用 ``create_all`` 建的，里面已经有一学期的数据；
    ``init_db`` 不许重建它、不许删它的行，只许把 ``alembic_version`` 补上。

    ⚠️⚠️ **Plan 08 Task 1 起本条多验一格**：链从 4 长到 5 之后，那一次紧跟在 stamp
    后面的 ``upgrade head`` 要**连着跑三条**迁移（2 → 3 → 5）在一份**带着数据**的旧库上。
    计划 §9 最后那一句逐字要求「实现者要实测『带着数据的库 upgrade head 之后一切仍绿』」
    ——本条就是那一格取证的**常驻**形式（一次性的亲跑取证见本 Task 报告 §3）。

    ⚠️⚠️ **Plan 06 Task 3 改掉了「怎么造这个旧库」**（本条此前是
    ``Base.metadata.create_all(eng)`` 一行）。原因是链长了第二条之后那一行**不再是
    一个旧库**：``create_all`` 建的是 **head** 的结构（29 张表，含 ``login_attempt``、``audit_log`` 与 **Plan 08 Task 1 的 ``read_audit_log``**），
    而档 2 的前提是「这是一份引入迁移链之前那版代码建出来的库」= **基线**的结构
    （26 张表）。实测（亲跑）：那一行会让
    :func:`app.db.session._assert_shape_matches_revision` 抛
    ``RuntimeError: …多表 ['login_attempt']``，本条当场红。
    ⚠️ **红的那一条其实抓到了一个真的语义漂移**，不是「测试写得不够灵活」：
    在只有一条迁移的链上，「基线结构」与 ``create_all`` 的结构**恰好相等**，
    于是旧写法看起来是对的；从第二条迁移起两格分开，而「甲方手里的旧库」
    永远是**基线**那一格。故新写法是「``upgrade`` 到基线 → 删掉版本表」，
    它造出来的正是「结构 == 基线、而库里没有 ``alembic_version``」这个形状
    ——也就是档 2 的**判据本身**（:func:`app.db.session._stamp_unversioned` 的
    「先比对、后 stamp」）。
    ⚠️ **于是本条现在多验了一格**：stamp 到基线之后紧跟的 ``upgrade head``
    真的把第二条迁移跑在了那份带数据的旧库上（``login_attempt`` 被建出来、
    ``semester`` 那一行还在）。这正是甲方现场升级的完整形状。
    """
    from alembic import command

    path = tmp_path / "legacy.db"
    url = "sqlite:///" + path.as_posix()
    # ① 造一个「结构 == 基线」的库：upgrade 到 BASELINE_REVISION（不是 head）
    command.upgrade(_alembic_config(url), BASELINE_REVISION)
    eng = create_engine(url)
    # ② 摘掉版本表，让它退化成「引入迁移链之前那版代码建的库」那个形状
    with eng.begin() as conn:
        conn.execute(text(f"DROP TABLE {ALEMBIC_VERSION_TABLE}"))
        # ③ 灌一行业务数据（它必须在 stamp + upgrade head 之后仍然在）
        conn.execute(text(
            "INSERT INTO semester (id, name, start_date, end_date, weeks, is_current) "
            "VALUES (1, '2025-2026-1', '2025-09-01', '2026-01-20', 20, 1)"
        ))
    assert not inspect(eng).has_table(ALEMBIC_VERSION_TABLE)
    # ⚠️ 反空转：这个「旧库」确实是**基线**的形状（26 张表、没有 login_attempt、
    #    没有 audit_log、也没有 read_audit_log），否则下面那一格
    #    「upgrade head 把第二、三、五条迁移跑上了」就无从谈起。
    # ⚠️ 那个 ``- 4`` 是**「head 比基线多几张表」+ 1 张版本表**：
    #    Plan 06 Task 3 之后是 ``- 2``（多 1 张 + 版本表），Task 5 之后是 ``- 3``
    #    （多 2 张：``login_attempt`` 与 ``audit_log``），
    #    **Plan 08 Task 1 之后是 ``- 4``**（多 3 张：再加 ``read_audit_log``）。
    #    ⚠️ 刻意写成算式而不是字面量 26：它因此随 ``EXPECTED_TABLE_COUNT_WITH_VERSION``
    #    一起动，而「基线是 26 张」这个事实由 ``BASELINE_REVISION`` 那一条迁移自己钉住
    #    （:func:`test_the_baseline_revision_literal_is_the_only_base_of_the_chain`）。
    assert not inspect(eng).has_table("login_attempt")
    assert not inspect(eng).has_table("audit_log")
    assert not inspect(eng).has_table("read_audit_log")
    assert not inspect(eng).has_table("bind_token")
    # ⚠️ 减数是 **5**：四张「不由基线迁移建」的表（``login_attempt`` / ``audit_log`` /
    #    ``read_audit_log`` / ``bind_token``）+ 那一张基线库里也没有的 ``alembic_version``
    #    （本档刻意只 ``create_all`` 基线那些表、不写版本表，故它不在）。
    #    ⚠️ Plan 08 Task 4 把它从 4 抬到 5（+ ``bind_token``）。
    assert len(inspect(eng).get_table_names()) == EXPECTED_TABLE_COUNT_WITH_VERSION - 5

    init_db(eng)

    insp = inspect(eng)
    assert insp.has_table(ALEMBIC_VERSION_TABLE), "旧库没有被纳管"
    with eng.connect() as conn:
        assert conn.execute(
            text(f"SELECT version_num FROM {ALEMBIC_VERSION_TABLE}")
        ).scalar() == HEAD_REVISION, "纳管完不是停在头上（stamp 到基线之后必须 upgrade head）"
        assert conn.execute(text("SELECT count(*) FROM semester")).scalar() == 1, "数据丢了"
        assert conn.execute(text("SELECT name FROM semester WHERE id = 1")).scalar() == \
            "2025-2026-1"
    # 第二、三、五条迁移真的跑上了：head 的全部 29 张表都在
    # （含基线里没有的那三张：``login_attempt`` / ``audit_log`` / ``read_audit_log``）。
    # ⚠️⚠️ **本条就是计划 §9 最后那一句要的那一格取证**：
    #    「若切换前甲方已经在试用库里写了数据，不许 ``-Reset``，只做 ``upgrade head``；
    #    实现者要实测『带着数据的库 upgrade head 之后一切仍绿』」。
    #    本条造的正是一份**带着一行业务数据**的旧库（``semester`` 那一行），
    #    而它断言的是 stamp + ``upgrade head`` 之后**那一行逐字还在**
    #    （含 ``name``），且链停在头上。⚠️ 于是「迁移 5 跑在一份有数据的库上」
    #    这一格在本条上是被钉住的，不是推断出来的。
    assert set(inspect(eng).get_table_names()) == set(EXPECTED_TABLES) | {ALEMBIC_VERSION_TABLE}
    # 纳管之后再调一次 init_db 走的是档 3，仍然幂等、仍然不丢数据
    init_db(eng)
    with eng.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM semester")).scalar() == 1
    eng.dispose()


def test_init_db_refuses_to_stamp_a_database_that_is_not_the_baseline(tmp_path):
    """**档 2 的失败方向**：结构不等于基线的旧库 → ``RuntimeError``，**拒绝 stamp**。

    ⚠️ 这一条是实现对计划的**顶回**留下的守卫：计划原文只写「库存在但没有
    ``alembic_version`` 表 → ``stamp`` 基线」，而那样在「旧库结构与基线不一致」时
    会**静默错**——stamp 成功、版本表写着基线、结构却还是旧的，此后没有任何一处
    会再报错，只会在离真因很远的地方 500。失效方向必须是「起不来」。

    ⚠️ 红绿两档同时在场（硬规矩 #50）：绿的那一半是上面
    :func:`test_init_db_stamps_a_legacy_database_and_keeps_its_rows`（结构相等 → 放行）。
    """
    path = tmp_path / "broken.db"
    eng = create_engine("sqlite:///" + path.as_posix())
    with eng.begin() as conn:
        # 一张列不全的 semester（缺 4 列）+ 一张根本不该存在的表 + 少 25 张表
        conn.execute(text("CREATE TABLE semester (id INTEGER PRIMARY KEY, name VARCHAR(32))"))
        conn.execute(text("CREATE TABLE totally_unexpected (id INTEGER PRIMARY KEY)"))

    with pytest.raises(RuntimeError) as excinfo:
        init_db(eng)

    message = str(excinfo.value)
    # 报错必须**指名道姓**，否则运维拿到的是一句「结构不一致」而无从下手
    assert "semester" in message and "end_date" in message, message
    assert "totally_unexpected" in message, message
    assert "student" in message, message  # 缺表那一档也要报出来
    assert not inspect(eng).has_table(ALEMBIC_VERSION_TABLE), "抛了却仍然写了版本表"
    eng.dispose()


def test_init_db_is_idempotent_on_an_already_versioned_database(tmp_path):
    """**档 3**：已有版本表 → ``upgrade head``，连跑三次结果不变（幂等）。"""
    path = tmp_path / "versioned.db"
    eng = create_engine("sqlite:///" + path.as_posix())
    init_db(eng)  # 档 1
    before = _normalized_schema(inspect(eng))

    init_db(eng)  # 档 3
    init_db(eng)  # 档 3 再来一次

    assert _normalized_schema(inspect(eng)) == before
    with eng.connect() as conn:
        assert conn.execute(
            text(f"SELECT count(*) FROM {ALEMBIC_VERSION_TABLE}")
        ).scalar() == 1, "版本表被写成了多行（多头的形状）"
    eng.dispose()


def test_init_db_on_memory_sqlite_never_touches_the_chain():
    """**快路径**：内存库走 ``create_all``，不建版本表、不碰磁盘。

    ⚠️ 这一档就是**全部 1340 条测试**走的那一条，故它必须是快的、且必须不落文件。
    """
    eng = create_engine("sqlite://", poolclass=StaticPool)
    init_db(eng)
    insp = inspect(eng)
    assert set(insp.get_table_names()) == set(EXPECTED_TABLES)
    assert not insp.has_table(ALEMBIC_VERSION_TABLE), "内存库不该被 stamp"
    eng.dispose()


def test_the_memory_fast_path_agrees_with_the_migration_path(migrated):
    """快路径（内存 ``create_all``）与迁移路径建出**同一套表与列**。

    ⚠️ 这一条把「测试档走另一条路」那个不对称真正兜住：
    :func:`test_alembic_upgrade_head_and_create_all_agree_table_by_table` 比的是两个
    **磁盘**库，而 1340 条测试用的是**内存**库——内存库那一档由本条覆盖。
    """
    eng = create_engine("sqlite://", poolclass=StaticPool)
    init_db(eng)
    try:
        assert _normalized_schema(inspect(eng)) == migrated["schema"]
    finally:
        eng.dispose()


# ---------------------------------------------------------------------------
# 两个「内存库」判据不许漂
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "sqlite://",
    "sqlite:///:memory:",
    "sqlite+aiosqlite:///:memory:",
    "sqlite:///C:/somewhere/pe_demo.db",
    "sqlite:///relative.db",
    "sqlite:////abs/path/x.db",
])
def test_db_file_of_agrees_with_is_memory_sqlite_on_memory_versus_disk(url):
    """:func:`app.db.session._db_file_of` 与 :func:`app.main._is_memory_sqlite` 在
    「内存 vs 磁盘」这一格上**逐字一致**。

    ⚠️ 两者是**两个所有者**、答的是两个问题：前者答「三档分支要看的那个磁盘文件在哪」
    （顺带认非 SQLite），后者答「该不该换 ``StaticPool``」。它们在内存库这一格上重叠，
    而重叠的那一格漂了的话，症状是「测试走内存库建表、生产走 alembic 建表，
    而两边建的不是同一个 schema」——那正是本文件其余部分要防的事，故这里单独钉一条。
    """
    from app.main import _is_memory_sqlite

    assert (_db_file_of(make_url(url)) is None) == _is_memory_sqlite(url), url


def test_db_file_of_returns_none_for_a_non_sqlite_backend():
    """非 SQLite 后端 → ``None``（走快路径），这是**刻意的**、且与上面那条不冲突。

    ⚠️ 上面那条参数化矩阵刻意**不含**非 SQLite 的 URL：``_is_memory_sqlite`` 对
    ``postgresql+psycopg://…`` 答 ``False``（它只关心内存/磁盘），而 ``_db_file_of``
    答 ``None``（它还要顺带认后端）。两者在那一格上**故意不同**，本条把那个不同
    写成一条断言，免得下一个人「顺手对齐」成 ``_db_file_of`` 也返回一个路径——
    那会让 alembic 拿一个 PostgreSQL URL 去跑一条只在 SQLite 上验过的迁移链
    （``render_as_batch`` 是 SQLite 专属口径，见 ``migrations/env.py``）。
    """
    assert _db_file_of(make_url("postgresql+psycopg://u:p@h/db")) is None


def test_alembic_ini_exists_where_session_says_it_is():
    """:data:`app.db.session.ALEMBIC_INI` 真的指着一个存在的文件（空转守卫）。

    ⚠️ 少了本条，``ALEMBIC_INI`` 拼错时 ``Config(...)`` 不报错（它只存路径），
    报错要等到 ``ScriptDirectory`` 去找 ``script_location``，离真因有两层。
    """
    assert ALEMBIC_INI.is_file(), ALEMBIC_INI
    assert ALEMBIC_INI.name == "alembic.ini"
    assert ALEMBIC_INI.parent.name == "backend"
    assert (ALEMBIC_INI.parent / "migrations" / "env.py").is_file()

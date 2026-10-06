# backend/tests/db/test_models.py
import datetime as dt
import re
import types
import pytest
from sqlalchemy import JSON as BuiltinJson, create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from app.db.session import Base, init_db, Session
from app.db import models as M
from app.domain.derive import Trend
from app.domain.indicators import AGE_GROUPS, CLEANING_FIELDS, Sex
from app.domain.percentile import (
    PercentileRow, SnapshotMetric, summarize_source,
)
from app.domain.stratify import RULE_ORDER, RuleId

@pytest.fixture
def session():
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    with Session(eng) as s:
        yield s

def test_all_fourteen_tables_created(session):
    expected = {"semester","teacher","student","course_section","enrollment",
        "fitness_test_batch","fitness_test_result","body_composition",
        "interest_survey","percentile_snapshot","derived_metrics",
        "stratification_result","daily_sync_run","cleaning_log"}
    # Ruling 28：用 == 而不是 >=。「第一批只建这 14 张」是真实的范围边界，>= 抓不到
    # 有人提前把计划 02（处方 / 运动记录）或计划 03（预警 / 通知）的表建进来——那种
    # 提前建表会逼出一次本该不存在的迁移，而超集断言对它完全无感。
    assert set(inspect(session.get_bind()).get_table_names()) == expected

def test_daily_sync_run_business_date_is_unique(session):
    sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025,9,1),
                     end_date=dt.date(2026,1,20), weeks=16, is_current=True)
    session.add(sem); session.flush()
    d = dt.date(2025, 9, 15)
    session.add(M.DailySyncRun(semester_id=sem.id, business_date=d, status="success"))
    session.flush()
    session.add(M.DailySyncRun(semester_id=sem.id, business_date=d, status="success"))
    with pytest.raises(IntegrityError):
        session.flush()

def test_stratification_label_domain(session):
    assert M.StratificationResult.LABELS == {
        "red", "yellow", "green", "insufficient_data"}

def test_grouping_mode_domain(session):
    assert M.CourseSection.GROUPING_MODES == {"administrative", "stratified"}

def test_timepoint_domain(session):
    assert M.FitnessTestBatch.TIMEPOINTS == {"week1", "week8", "week16"}


# ---------------------------------------------------------------------------
# Ruling 27：SQLite 的外键强制
# ---------------------------------------------------------------------------

def test_sqlite_foreign_keys_are_enforced(session):
    """SQLite 每条连接默认 ``foreign_keys=OFF``，钩子必须真的把它打开。

    会话按测试一贯的方式产生（``create_engine`` + ``init_db``），因此这条断言验的
    正是注册在 ``Engine`` **类**上的那个钩子——挂在 ``engine()`` 返回值上的话，这条
    路径一个也覆盖不到，PRAGMA 会照旧读回 0，而 schema 里 20 个外键全是装饰。
    """
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_orphan_batch_id_is_rejected(session):
    """``derived_metrics.batch_id`` 是 Task 10 幂等重放的唯一依据，必须真有兜底。

    外键不强制时，``delete_by_batch`` 漏删留下的孤儿派生行永远不会报错，只会静默
    抬高红黄绿分布。这条测试就是那个兜底的回归：批号在 ``daily_sync_run`` 里查无
    此行时，插入必须被数据库自己拒收。
    """
    stu = M.Student(student_no="2025001001", name="张三", sex="male",
                    birth=dt.date(2006, 3, 4), grade=1)
    session.add(stu); session.flush()
    session.add(M.DerivedMetrics(student_id=stu.id, computed_on=dt.date(2025, 9, 15),
                                 batch_id=999_999, annual_change={}, trend="stable",
                                 weaknesses=[], weakness_count=0, valid_count=6,
                                 body_comp_abnormal=False, body_comp_reasons=[]))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "FOREIGN KEY constraint failed" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Ruling 30：DailySyncRun.status 的默认值
# ---------------------------------------------------------------------------

def test_daily_sync_run_status_defaults_to_failed(session):
    """运行记录常在跑完之前就入库，此时 status 必须落到保守的那一侧。

    默认取 ``"failed"``：进程崩在中途，这一行留下的就是 failed——崩溃被记成失败
    只是难看，被记成成功则是谎报一次并没有发生的完整运行，而下游看 status 决定要
    不要重跑，谎报成功会让这一天永远不再重跑。
    """
    column = M.DailySyncRun.__table__.columns["status"]
    assert column.nullable is False, "本列不许为空，故必须有默认值"
    assert column.default.arg == "failed"

    sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
                     end_date=dt.date(2026, 1, 20), weeks=16, is_current=True)
    session.add(sem); session.flush()
    # 只给必需的三样： semester_id / business_date，status 一律不传
    run = M.DailySyncRun(semester_id=sem.id, business_date=dt.date(2025, 9, 15))
    session.add(run); session.flush()
    run_id = run.id
    session.expire_all()

    assert session.get(M.DailySyncRun, run_id).status == "failed", "落库后须读回 failed"
    # 显式给出时仍以显式值为准，默认值不得覆盖真实结局
    other = M.DailySyncRun(semester_id=sem.id, business_date=dt.date(2025, 9, 16),
                           status="success")
    session.add(other); session.flush(); other_id = other.id
    session.expire_all()
    assert session.get(M.DailySyncRun, other_id).status == "success"


# ---------------------------------------------------------------------------
# Student.SEXES ↔ domain.indicators.Sex 的一致性
# ---------------------------------------------------------------------------

def test_student_sexes_match_domain_sex_enum(session):
    """两处字面量此前只是「碰巧相同」，没有任何东西钉住它。

    db 层没有 import ``Sex``（Task 3 的接口约定是「Consumes: 无」，且纯度约束管的是
    ``app/domain/`` 自己的导入，不管谁 import 它），代价就是漂移只能靠这条测试抓：
    一旦 ``Sex`` 多出一个值而 ``Student.SEXES`` 没跟上，db 会拒收 domain 的合法值。
    """
    assert {s.value for s in Sex} == M.Student.SEXES

    # percentile_snapshot.sex 复用同一常量，故顺带钉住 DDL 里的取值域也一致
    checks = {c.name: str(c.sqltext) for c in M.PercentileSnapshot.__table__.constraints
              if type(c).__name__ == "CheckConstraint"}
    assert checks["ck_percentile_snapshot_sex"] == "sex IN ('female', 'male')"


# ---------------------------------------------------------------------------
# JsonText 约定的结构守卫
# ---------------------------------------------------------------------------

def _is_builtin_json(type_) -> bool:
    """判断一个列类型是不是 SQLAlchemy 自带的 ``JSON``（含 ``TypeDecorator`` 的底层）。"""
    if isinstance(type_, BuiltinJson):
        return True
    impl = getattr(type_, "impl", None)  # TypeDecorator 的真实落库类型
    return isinstance(impl, type) and issubclass(impl, BuiltinJson)


def test_no_column_uses_builtin_sqlalchemy_json():
    """``JsonText`` 已是全库约定，任何一列退回自带 ``JSON`` 都要当场炸。

    自带 ``JSON`` 在 SQLite 上是 NUMERIC 亲和性：``original_value = 0.0`` 会存成
    ``integer 0``、读回 ``int 0``，审计记录里的「原值 65.0 kg」变成「原值 65」。
    行为侧已有 ``test_json_text_keeps_float_and_none`` 覆盖，这条是结构侧的守卫——
    它不看某一列的行为，而是遍历 14 张表的每一列，让「新加的模型忘了这条约定」也
    逃不掉。
    """
    tables = Base.metadata.tables
    assert len(tables) == 14, "守卫的覆盖面必须先被确认是这 14 张表"

    offenders = [
        f"{table.name}.{column.name}"
        for table in tables.values()
        for column in table.columns
        if _is_builtin_json(column.type)
    ]
    assert offenders == [], f"这些列用了自带 JSON，必须换成 JsonText：{offenders}"

    # 守卫自己也得有牙：八个 JSON 形态的列确实被遍历到了，不是空跑
    json_text_columns = sorted(
        f"{table.name}.{column.name}"
        for table in tables.values()
        for column in table.columns
        if type(column.type).__name__ == "JsonText"
    )
    assert len(json_text_columns) == 8, json_text_columns
    assert "cleaning_log.original_value" in json_text_columns


# ---------------------------------------------------------------------------
# Ruling 31：``batch_id`` 一词专指 daily_sync_run 的外键
# ---------------------------------------------------------------------------

# 全库唯一允许拥有 ``batch_id`` 列的三张派生表——即 ``delete_by_batch`` 的合法目标。
_DERIVED_TABLES = {"derived_metrics", "stratification_result", "percentile_snapshot"}


def test_fitness_test_result_has_no_batch_id_attribute():
    """``FitnessTestResult`` 不得再有 ``batch_id`` 属性，那条外键叫 ``test_batch_id``。

    这是 Ruling 31 的回归守卫，也是它唯一的存在理由：没有这条断言，改名会被后人当成
    一次「不够简洁」的重命名而顺手改回去。改回去的代价是静默删源数据——
    ``fitness_test_batch.id`` 只有 1/2/3（week1/week8/week16），``daily_sync_run.id``
    按业务日递增（一学期 1…112），故误调
    ``delete_by_batch(session, FitnessTestResult, sync_run_id)`` 时，凡
    ``sync_run_id ∈ {1, 2, 3}`` 都会**匹配上并删掉真实的源体测成绩**（实测 3 → 2 行、
    返回 1、无任何异常）。两列都是 int：外键拦不住（每个值各自合法，Ruling 27 的钩子
    在这里帮不上忙），``AttributeError`` 也拦不住（属性存在）。删**源**数据比删派生行
    严重得多——派生行重算就回来了，源体测数据删了就是删了。

    改名后本表没有 ``batch_id`` 属性，那一脚踩下去是响亮的 ``AttributeError``，与
    ``CleaningLog`` 用 ``sync_run_id`` 而非 ``batch_id`` 的既有设计同一口径。
    """
    assert not hasattr(M.FitnessTestResult, "batch_id")
    assert hasattr(M.FitnessTestResult, "test_batch_id")

    # 改名只换名字、不换语义：这条外键仍指向体测批次，不是 daily_sync_run
    column = M.FitnessTestResult.__table__.c.test_batch_id
    assert [fk.target_fullname for fk in column.foreign_keys] == ["fitness_test_batch.id"]


def test_only_derived_tables_expose_batch_id():
    """命名规则必须机器可查，不能只是「大家记得」的约定。

    遍历 ``Base.metadata``，有 ``batch_id`` 列的表**恰好**是三张派生表。``batch_id``
    在本项目里专指「指向 ``daily_sync_run`` 的外键」，也就是 ``delete_by_batch`` 可据以
    删除的归属键；任何别的父表都得用可区分的名字（``fitness_test_result.test_batch_id``
    指体测批次、``cleaning_log.sync_run_id`` 指同步运行）。

    只断言列名还不够——名字对了语义错了才是 Ruling 31 要防的失效，故同时断言这三列
    真的指向 ``daily_sync_run``。
    """
    tables = Base.metadata.tables
    assert len(tables) == 14, "守卫的覆盖面必须先被确认是这 14 张表"

    observed = {
        name for name, table in tables.items() if "batch_id" in set(table.c.keys())
    }
    assert observed == _DERIVED_TABLES, (
        f"batch_id 专指 daily_sync_run 的外键，实到 {sorted(observed)}"
    )

    for name in sorted(_DERIVED_TABLES):
        column = tables[name].c.batch_id
        assert [fk.target_fullname for fk in column.foreign_keys] == [
            "daily_sync_run.id"
        ], f"{name}.batch_id 必须指向 daily_sync_run"


# ---------------------------------------------------------------------------
# Ruling 121 / 137（Task 10 Step 0.2、0.3）：两个新取值域与 domain 的一致性
# ---------------------------------------------------------------------------

def _snapshot_row(source: str) -> PercentileRow:
    """一行只为了拿 ``source`` 的快照行（``summarize_source`` 只读这一列）。"""
    return PercentileRow(
        item=SnapshotMetric.SPRINT_50M, sex=Sex.MALE, age_group=AGE_GROUPS[0],
        p10=1.0, p20=2.0, p25=3.0, p50=4.0, p75=5.0, sample_size=30, source=source,
    )


def test_percentile_snapshot_item_domain_matches_snapshot_metric(session):
    """``percentile_snapshot.item`` 的取值域与 domain 的 ``SnapshotMetric`` 逐字一致。

    与 ``Student.SEXES`` 同一条处置：db 层不 import domain，代价是两处需人工同步，
    漂移只能靠这条测试抓。**两个方向都致命**：少了 ``muscle_mass_kg``，Task 10 物化
    肌肉量行时会被自己刚加的 CHECK 拒收（响亮，但整批回滚）；多一个 domain 不认的值，
    库里就存得下一行 ``lookup_p20`` 永远匹配不上的判定线（静默）。
    """
    assert {m.value for m in SnapshotMetric} == M.PercentileSnapshot.ITEMS

    checks = {c.name: str(c.sqltext) for c in M.PercentileSnapshot.__table__.constraints
              if type(c).__name__ == "CheckConstraint"}
    assert "ck_percentile_snapshot_item" in checks
    sqltext = checks["ck_percentile_snapshot_item"]
    assert sqltext.startswith("item IN (")
    # 肌肉量是 Ruling 121 才进来的那一个：它是 spec §6.3② 那条 P20 判定线的样本
    assert "'muscle_mass_kg'" in sqltext
    for value in M.PercentileSnapshot.ITEMS:
        assert f"'{value}'" in sqltext


def test_percentile_source_domain_covers_the_producer_codomain(session):
    """``percentile_source`` 的取值域必须容得下生产者 :func:`summarize_source` 的**全部**输出。

    ``"none"`` 是 Ruling 137 补的第三值（``valid_count = 0``，即「没有用过任何判定线」）。
    少了它，Z0 那条路径在 Task 10 落库时会被 CHECK 约束拒收——而那正是最需要留痕的一类人；
    而拿 ``"school"`` 去填更糟：它会声称「这个人的判定线来自校内百分位」，可他根本没有
    判定线，那是一条凭空造出的可追溯性。
    """
    assert M.StratificationResult.PERCENTILE_SOURCES == {"school", "national", "none"}

    produced = {
        summarize_source([]),                                        # 一行都没用过
        summarize_source([_snapshot_row("school")]),
        summarize_source([_snapshot_row("national")]),
        # 混用：任一项降级即 national（保守侧）
        summarize_source([_snapshot_row("school"), _snapshot_row("national")]),
    }
    assert produced == {"none", "school", "national"}, "生产者的值域恰好是这三个"
    assert produced <= M.StratificationResult.PERCENTILE_SOURCES

    checks = {c.name: str(c.sqltext)
              for c in M.StratificationResult.__table__.constraints
              if type(c).__name__ == "CheckConstraint"}
    assert checks["ck_stratification_result_percentile_source"] == (
        "percentile_source IN ('national', 'none', 'school')"
    )
    # String(8) 刚好容得下最长的 "national"，不得有人往里塞更长的 token
    assert max(len(value) for value in produced) <= \
        M.StratificationResult.__table__.c.percentile_source.type.length


# ---------------------------------------------------------------------------
# Ruling 144 / 硬规矩 #18：列宽必须容得下取值域里最长的那个值
# ---------------------------------------------------------------------------

# :func:`app.db.models._in_domain` 生成的约束文本形如 ``column IN ('a', 'b')``（取值按
# 字典序排序、单引号转义为两个单引号）。从文本反解出「列 → 允许值集合」，表就是
# **自描述**的：Plan 02/03 新加的表与列自动被覆盖，不必回来手抄第二张清单——手抄的清单
# 就是第二个所有者，迟早与 DDL 漂移（Ruling 35/36 的单一所有者原则）。
_IN_DOMAIN_SQL = re.compile(r"^\s*(\w+) IN \((.*)\)\s*$")
_QUOTED_VALUE = re.compile(r"'((?:[^']|'')*)'")


def _in_domain_columns() -> dict[tuple[str, str], set[str]]:
    """遍历 ``Base.metadata``，反解每条 ``_in_domain`` CHECK 约束的列名与允许值集合。"""
    parsed: dict[tuple[str, str], set[str]] = {}
    for table in Base.metadata.tables.values():
        for constraint in table.constraints:
            if type(constraint).__name__ != "CheckConstraint":
                continue
            match = _IN_DOMAIN_SQL.match(str(constraint.sqltext))
            if match is None:
                continue  # 不是取值域约束（本库今天没有这类 CHECK）
            values = {
                v.replace("''", "'") for v in _QUOTED_VALUE.findall(match.group(2))
            }
            parsed[(table.name, match.group(1))] = values
    return parsed


def test_string_column_widths_fit_their_value_domains():
    """凡 ``String(n)`` 列存枚举值或固定词表，``n`` 必须 ≥ 该域内最长值的长度。

    SQLite **不强制** ``VARCHAR`` 长度，故这类溢出在测试里永远不报错——Ruling 144 的
    ``derived_metrics.trend String(16)`` 就是这样漏了 7 个任务：``Trend.INSUFFICIENT.value``
    = ``"insufficient_data"`` 是 17 字符，500 人首批实测有 **209 行（41.8%）**往这一列写它。
    换 MySQL / PostgreSQL 会截断成 ``"insufficient_dat"``，读回来 ``Trend(...)`` 当场
    ``ValueError``——**炸在读侧不在写侧**，离真因隔一整个批处理周期。

    取值域的两个来源，都不是手抄的第二份清单：

    1. **有 CHECK 约束的列**——从 :func:`_in_domain` 生成的约束文本反解（今天恰好 10 列：
       ``student.sex``、``course_section.grouping_mode``、``fitness_test_batch.timepoint``、
       ``percentile_snapshot`` 的 ``source`` / ``sex`` / ``item``、``stratification_result``
       的 ``label`` / ``percentile_source``、``daily_sync_run.status``、``cleaning_log.kind``）。
    2. **没有 CHECK 约束、但取值域有唯一所有者的四列**——见下方注释里各自的出处。
    """
    domains = _in_domain_columns()
    # 空转守卫：正则写错会静默匹配到 0 列而全绿（那时 offenders 恒为空）。
    assert len(domains) >= 10, f"反解出的受约束列数不对，正则可能失配：{sorted(domains)}"

    # 无 CHECK 约束的四列，取值域各自指向生产里的唯一所有者：
    # · ``derived_metrics.trend``       ← :class:`app.domain.derive.Trend` 的成员值
    #   （写入处 ``pipeline/daily.py`` 的 ``trend=derived.trend.value``），最长 17。
    # · ``stratification_result.hit_rules`` ← ``",".join(RuleId.value)``。Z0 路径恰为
    #   ``"Z0"``、非 Z0 路径是 7 条分层规则的已评估前缀，**两者互斥**（Ruling 132），
    #   故生产最大值是非 Z0 的完整前缀 ``"R1,R2,Y1,Y2,Y3,Y4,G1"`` = **20**，不是把 Z0
    #   也串起来的 23（Ruling 148）。
    # · ``percentile_snapshot.age_group`` ← :data:`app.domain.indicators.AGE_GROUPS`
    #   （全仓唯一口径），最长 5。
    # · ``cleaning_log.field`` ← :data:`app.domain.indicators.CLEANING_FIELDS`
    #   （**Plan 02 Task 1 新增**，Plan01 Ruling 156 的落点：这一列此前**没有任何所有者**，
    #   13 个字段名散落在 ``clean.py`` 的 9 个写入点上）。最长 17 = ``"vital_capacity_ml"``。
    #   它与清洗层实际产出的一致性由
    #   ``tests/pipeline/test_clean.py::test_cleaning_fields_cover_every_produced_field``
    #   钉住（那一侧从两个记录数据类的 ``fields()`` 推导，两侧不同源）。
    domains[("derived_metrics", "trend")] = {t.value for t in Trend}
    domains[("stratification_result", "hit_rules")] = {
        ",".join(rule.value for rule in RULE_ORDER if rule is not RuleId.Z0),
        RuleId.Z0.value,
    }
    domains[("percentile_snapshot", "age_group")] = set(AGE_GROUPS)
    domains[("cleaning_log", "field")] = set(CLEANING_FIELDS)

    offenders: list[str] = []
    for (table_name, column_name), values in sorted(domains.items()):
        column = Base.metadata.tables[table_name].c[column_name]
        width = getattr(column.type, "length", None)
        if width is None:
            continue  # Text 一类无长度限制，不存在截断风险
        longest = max(values, key=len)
        if width < len(longest):
            offenders.append(
                f"{table_name}.{column_name} 声明 String({width})，"
                f"取值域里最长的却是 {longest!r}（{len(longest)} 字符）"
            )
    # 一次性报全：一列一个 assert 的话，第一个红会盖住后面的。
    assert offenders == [], "列宽容不下取值域（严格长度的后端会静默截断）：\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# Plan 02 Task 1：models.py 拆包的导入面基线（Plan02 Ruling 1）
# ---------------------------------------------------------------------------

# 拆包**之前**在基线 ``e26347f`` 上实测的 ``app.db.models`` 公有导入面，逐字抄进来。
# 取法（在 ``backend/`` 下跑，一次性取证，之后不再重跑——重跑就是拿拆包后的结果当基线）::
#
#     python -c "from app.db import models; import json; print(json.dumps(sorted(n for n in dir(models) if not n.startswith('_')), ensure_ascii=False))"
#
# **不从拆包后的 ``models`` 读回来跟自己比**（硬规矩 #35）：那样两侧同源，漏导出一个类
# 两边一起少一个、恒等成立。这 33 个名字里既有 14 张表的类，也有 ``Base`` / ``JsonText``
# 这两个真正被跨模块引用的基础设施，还有一批**偶然公有**的名字（``dt`` / ``json`` /
# ``Boolean`` / ``mapped_column`` …）——它们本来就是单文件 ``models.py`` 的模块级 import，
# 因此出现在 ``dir()`` 里。保留它们是判据「逐字相同」的应有代价：宁可多保住几个没人用的
# 名字，也不要让判据松到抓不住「漏导出一个类」。
_MODELS_PUBLIC_BASELINE = [
    "Any", "Base", "BodyComposition", "Boolean", "CheckConstraint", "CleaningLog",
    "CourseSection", "DailySyncRun", "Date", "DateTime", "DerivedMetrics", "Enrollment",
    "FitnessTestBatch", "FitnessTestResult", "Float", "ForeignKey", "Integer",
    "InterestSurvey", "Iterable", "JsonText", "Mapped", "PercentileSnapshot", "Semester",
    "StratificationResult", "String", "Student", "Teacher", "Text", "TypeDecorator",
    "UniqueConstraint", "dt", "json", "mapped_column",
]

# 拆包**新增**的六个子模块名。它们是包的结构性属性（``from .x import *`` 必然在父包上
# 留下 ``x`` 这个属性），不是导入面，故从比对里排除。
_MODELS_SUBMODULES = frozenset({
    "organisation", "assessment", "derived", "prescription", "feedback", "ops",
})

# 拆包前的 ``__all__``（14 张表的声明序，spec §4.1→§4.6）
_MODELS_ALL_BASELINE = [
    "Semester", "Teacher", "Student", "CourseSection", "Enrollment",
    "FitnessTestBatch", "FitnessTestResult", "BodyComposition", "InterestSurvey",
    "PercentileSnapshot", "DerivedMetrics", "StratificationResult",
    "DailySyncRun", "CleaningLog",
]


def test_models_public_namespace_is_unchanged_by_the_split():
    """``app.db.models`` 拆成包之后，公有导入面**逐字未变**（Plan02 Ruling 1）。

    这是「``from app.db import models`` 与 ``models.X`` 的既有写法不变」这句散文的
    **唯一可执行判据**：散文不可执行，而「漏导出一个类」的失效形态是运行时才
    ``AttributeError``——恰好是这条要求要防的事。

    排除六个子模块名之前先断言两件事，好让排除本身不可能吞掉一次真回归：

    1. 排除集与基线**不相交**（若哪天有人把一个表模块命名为 ``derived`` 之外又与基线
       重名，这条会先红）；
    2. 排除集里的每个名字**确实是一个模块**（若 ``organisation`` 哪天变成了一个类，
       这条会红，而它就不该再被排除）。
    """
    assert len(_MODELS_PUBLIC_BASELINE) == 33, "基线是 33 个名字，抄漏了就当场红"
    assert not (_MODELS_SUBMODULES & set(_MODELS_PUBLIC_BASELINE)), (
        "排除集与基线相交，排除会吞掉真名字："
        f"{sorted(_MODELS_SUBMODULES & set(_MODELS_PUBLIC_BASELINE))}"
    )
    for name in sorted(_MODELS_SUBMODULES):
        assert isinstance(getattr(M, name, None), types.ModuleType), (
            f"{name} 不再是子模块，就不该继续被排除在导入面比对之外"
        )

    observed = {n for n in dir(M) if not n.startswith("_")}
    assert observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE), (
        f"少了 {sorted(set(_MODELS_PUBLIC_BASELINE) - observed)}，"
        f"多了 {sorted(observed - _MODELS_SUBMODULES - set(_MODELS_PUBLIC_BASELINE))}"
    )
    assert list(M.__all__) == _MODELS_ALL_BASELINE

    # 私有名里有一个是**承重的**：约束文本生成器。它带前导下划线故不在上面的比对里，
    # 但 tests/db/test_models.py 自己的注释与将来的迁移脚本都按
    # ``app.db.models._in_domain`` 引用它，故单独钉一条。
    assert callable(M._in_domain)
    # 14 张表一个不少地注册进了同一个 metadata（拆包最容易漏的就是这个）
    assert len(Base.metadata.tables) == 14
    for name in _MODELS_ALL_BASELINE:
        assert getattr(M, name).__tablename__ in Base.metadata.tables


# ---------------------------------------------------------------------------
# Plan 02 Task 1 Step 4：fitness_test_result.tested_on 与 daily_sync_run 的计数列
# ---------------------------------------------------------------------------

def _semester_and_student(session):
    sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
                     end_date=dt.date(2026, 1, 20), weeks=16, is_current=True)
    session.add(sem)
    session.flush()
    stu = M.Student(student_no="2025001001", name="张三", sex="male",
                    birth=dt.date(2006, 3, 4), grade=1)
    session.add(stu)
    session.flush()
    batch = M.FitnessTestBatch(semester_id=sem.id, timepoint="week1",
                               test_date=dt.date(2025, 9, 1))
    session.add(batch)
    session.flush()
    return sem, stu, batch


def test_fitness_test_result_tested_on_is_required(session):
    """``fitness_test_result.tested_on`` NOT NULL 且无缺省：漏传必须**当场炸**。

    这一列是「本条成绩是哪一天测的」的唯一所有者，而百分位阶段靠它按业务日期截断
    （``percentile_stage._results_of`` 的 ``tested_on <= as_of``）。做成可空的代价是
    静默的：``NULL <= as_of`` 在 SQL 里恒为 **NULL**（不是 TRUE 也不是 FALSE），
    ``WHERE`` 因此把那一行**悄悄丢掉**，于是「这个学生今天没有成绩」与「这个学生的成绩
    没写日期」在库里长得一模一样，而前者会让他走 Z0 → ``insufficient_data``。
    """
    _sem, stu, batch = _semester_and_student(session)
    column = M.FitnessTestResult.__table__.c.tested_on
    assert column.nullable is False, "本列不许为空，故必须显式给值"
    assert column.default is None, "也不得有缺省值：缺省会让「忘了写」看起来像「写了」"

    session.add(M.FitnessTestResult(test_batch_id=batch.id, student_id=stu.id,
                                    height_cm=172.5))
    with pytest.raises(IntegrityError) as excinfo:
        session.flush()
    assert "fitness_test_result.tested_on" in str(excinfo.value)
    # 失败的 flush 让会话进入「必须回滚」状态；回滚把上面那三行夹具也一起撤掉
    # （它们从未 commit），故正向那一段重新建一次。
    session.rollback()
    _sem, stu, batch = _semester_and_student(session)

    # 给了值就照常落库、读回同一个日期
    day = dt.date(2025, 9, 4)
    session.add(M.FitnessTestResult(test_batch_id=batch.id, student_id=stu.id,
                                    tested_on=day, height_cm=172.5))
    session.flush()
    session.expire_all()
    assert session.scalar(select(M.FitnessTestResult)).tested_on == day


def test_daily_sync_run_carries_the_plan02_count_columns(session):
    """``muscle_line_gaps`` / ``prescription_count`` / ``alert_count`` 三列都在、都默认 0。

    ⚠️ **``prescription_count`` 与 ``alert_count`` 是 Plan 01 就建好的**：基线 ``e26347f``
    的 ``app/db/models.py:614-615`` 已经有这两列（``git grep -n "prescription_count" --
    backend/app`` 可复验）。Plan 02 计划原文写的「spec §4.6 明确列了『处方生成数、
    预警触发数』两列，**Plan 01 没建**」与基线不符，故 Task 1 没有新增它们，本测试只是
    把「三列都在、都默认 0」钉住，免得后面的人以为要再建一次。

    ``muscle_line_gaps`` 是本 Task **真正新增**的那一列，它取代了此前写进
    ``error_summary`` 的「注意（非错误）：N 个组没有肌肉量 P20 判定线……」自由文本
    （Plan02 Ruling 13：直接切、不双写）。默认 0 与其余计数列同一条理由——运行记录常在
    跑完之前就入库（要先拿到 ``id`` 当 ``batch_id`` 用），此时它是「还没数」而不是「未知」。
    """
    columns = M.DailySyncRun.__table__.columns
    for name in ("muscle_line_gaps", "prescription_count", "alert_count"):
        assert name in columns, f"daily_sync_run 缺列 {name}"
        assert columns[name].nullable is False, f"{name} 不许为空"
        assert columns[name].default.arg == 0, f"{name} 的默认值必须是 0"

    sem = M.Semester(name="2025-2026-1", start_date=dt.date(2025, 9, 1),
                     end_date=dt.date(2026, 1, 20), weeks=16, is_current=True)
    session.add(sem)
    session.flush()
    run = M.DailySyncRun(semester_id=sem.id, business_date=dt.date(2025, 9, 15))
    session.add(run)
    session.flush()
    run_id = run.id
    session.expire_all()
    got = session.get(M.DailySyncRun, run_id)
    assert (got.muscle_line_gaps, got.prescription_count, got.alert_count) == (0, 0, 0)
    # error_summary 不再承载缺线提示：一个成功的运行它就是 NULL
    assert got.error_summary is None


# ---------------------------------------------------------------------------
# Plan 02 Task 1 Step 4 第 1 项：单人「当前分层」查询必须走索引
# ---------------------------------------------------------------------------

#: 两条生产读法：教师大屏点一个人看「他现在什么层」，以及看他的派生指标。
_SINGLE_PERSON_QUERIES = (
    ("stratification_result",
     "select id from stratification_result "
     "where student_id = 1 order by computed_on desc limit 1"),
    ("derived_metrics",
     "select id from derived_metrics "
     "where student_id = 1 and computed_on <= '2025-09-15' "
     "order by computed_on desc limit 1"),
)


def test_single_person_queries_are_index_served(session):
    """两条单人查询必须走 ``(student_id, computed_on)`` 索引，不得全表扫、不得另建临时 B-tree。

    **这条测试取代了计划 Step 4 第 1 项要的显式 ``Index``**，理由是本仓实测那条索引是
    **冗余**的：Plan01 Ruling 212 已经给这两张表加了
    ``UniqueConstraint("student_id", "computed_on")``，而 SQLite 会为 UNIQUE 约束自动建出
    一条同列序的索引（``sqlite_autoindex_<table>_1``），查询规划器已经在用它。

    实测（本机、CPython 3.11 + SQLAlchemy 2.1 + SQLite；500 人 × 112 业务日 = **56000 行**
    ``stratification_result``；每条查询 300 次、随机学号、``random.Random(20250828)``；
    落磁盘库后按 ``.db`` 文件字节量体积）：

    ==============================  ==================  ==================  =====================
    场景                             单次墙钟中位 (ms)    ``.db`` 字节        EXPLAIN QUERY PLAN
    ==============================  ==================  ==================  =====================
    A 仅 UniqueConstraint 的自动索引        0.2708           5 423 104        ``USING COVERING INDEX sqlite_autoindex_stratification_result_1 (student_id=?)``
    B A + 显式 ``Index(student_id, computed_on)``  0.2941      6 791 168        ``USING COVERING INDEX ix_stratification_result_student_computed (student_id=?)``
    ==============================  ==================  ==================  =====================

    B/A = **1.086**（即加了索引**没有变快**，中位数还慢了 8.6%，n=300，两个场景各自
    min…max = 0.1385…0.9031 与 0.1698…1.0212 ms，区间完全重叠），而文件体积
    **+1 368 064 B = +25.23%**（十进制百分比；计划原文写的代价是「+2.7% 文件体积」，
    与本次实测差一个量级）。计划原文的收益数字「57.9 ms → 0.2 ms（258×）」因此只能来自
    一个**没有**那条 UNIQUE 约束的 schema——即 Plan01 Ruling 212 落地之前的状态。

    所以本测试守的是**结果**（走索引、不全表扫、不排序）而不是**机制**（某条具名索引存在）。
    这样它同时挡住两种回归：有人删掉 UNIQUE 约束而没补索引，以及有人加了一条列序不对的
    索引（如 ``(computed_on, student_id)``——前导列不是 ``student_id`` 时这条查询用不上它）。
    """
    # 用会话自己那条连接：``session.get_bind()`` 给的是 ``Engine``，SQLAlchemy 2.x 上它
    # 没有 ``.execute``；而另开一条连接会离开本会话的事务（夹具是 ``sqlite:///:memory:``，
    # 是否还是同一个库取决于连接池策略，不该由本测试来赌）。
    conn = session.connection()
    for table, query in _SINGLE_PERSON_QUERIES:
        detail = [row[3] for row in conn.execute(text("explain query plan " + query))]
        assert len(detail) == 1, f"{table} 的查询计划不止一步：{detail}"
        plan = detail[0]
        assert "SCAN" not in plan, f"{table} 走了全表扫：{plan}"
        assert "USING" in plan and "INDEX" in plan, f"{table} 没用索引：{plan}"
        # 前导列必须是 student_id：列序反过来的索引对这条查询毫无用处
        assert "student_id=?" in plan, f"{table} 的索引前导列不是 student_id：{plan}"
        # 排序由索引本身供给；出现这一句就说明规划器另建了临时 B-tree
        assert "TEMP B-TREE" not in plan, f"{table} 为 ORDER BY 另建了临时 B-tree：{plan}"

    # 守卫自己也得有牙：那条自动索引确实在库里，且列序是 (student_id, computed_on)
    for table in ("stratification_result", "derived_metrics"):
        uniques = {u["name"]: u["column_names"]
                   for u in inspect(conn).get_unique_constraints(table)}
        assert uniques[f"uq_{table}_student_day"] == ["student_id", "computed_on"], uniques


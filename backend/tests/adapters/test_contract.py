# backend/tests/adapters/test_contract.py
"""DataSourceAdapter 契约测试。

``tests/fixtures/lepao_sample/`` 下的四个迷你 CSV 是**契约的可执行定义**（进版本控制）：
文件名、列序、空单元格语义、``since`` 排他边界都由这里钉死，Task 6 的 ``write_csv``
必须逐列对齐，Task 10 的管道必须按同一语义消费。

覆盖范围要说清楚：与 ``HttpLePaoAdapter`` **共享**的只有
``test_satisfies_adapter_contract``（``isinstance`` + 四个方法可调用）与
``test_http_skeleton_raises_for_every_method``；其余全是 Mock 专属的行为测试。HTTP 真实
实现落地时必须为它补齐同一组行为断言，别把本文件当成「两个实现都验过了」。
"""
import pathlib, pytest
from app.adapters.base import DataSourceAdapter, RawFitnessRecord
from app.adapters.mock_lepao import MockLePaoAdapter
from app.adapters.http_lepao import HttpLePaoAdapter

# 下面是契约扩展用例需要的导入（brief Step 1 的原文用例只用上面四行）
import csv, dataclasses, json, math, types, typing
from app.adapters.base import (
    FITNESS_COLUMNS,
    FITNESS_FILENAME,
    STUDENT_COLUMNS,
    SURVEY_COLUMNS,
    SURVEY_FILENAME,
    TIMEPOINTS,
    RawBodyCompRecord,
    RawSurveyRecord,
    make_batch_key,
    parse_batch_key,
)
from app.adapters.mock_lepao import TEXT_COLUMNS

FIXTURE = pathlib.Path(__file__).parents[1] / "fixtures" / "lepao_sample"

def implementations():
    return [MockLePaoAdapter(FIXTURE), HttpLePaoAdapter("https://api.lepao.example", "t")]

def _write_fitness_row(tmp_path, **overrides):
    """往 ``tmp_path`` 写一个单行 ``fitness.csv``，供错误路径与 ``since`` 边界用例复用。"""
    row = dict.fromkeys(FITNESS_COLUMNS, "")
    row.update({"student_no": "2024010101", "batch_key": "2025-2026|week1",
                "tested_on": "2025-09-04"})
    row.update(overrides)
    with (tmp_path / FITNESS_FILENAME).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FITNESS_COLUMNS)
        writer.writeheader()
        writer.writerow(row)
    return row

def _write_survey_row(tmp_path, **overrides):
    """往 ``tmp_path`` 写一个单行 ``survey.csv``（JSON 列缺省是合法值）。"""
    row = {
        "student_no": "2024010101",
        "filled_on": "2025-09-03",
        "total": "19.0",
        "dimensions": json.dumps({"运动乐趣": 4.0}, ensure_ascii=False),
        "raw_answers": json.dumps({"q01": 4}),
    }
    row.update(overrides)
    with (tmp_path / SURVEY_FILENAME).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SURVEY_COLUMNS)
        writer.writeheader()
        writer.writerow(row)
    return row

@pytest.mark.parametrize("adapter", implementations(), ids=["mock", "http"])
def test_satisfies_adapter_contract(adapter):
    assert isinstance(adapter, DataSourceAdapter)
    for m in ("fetch_students", "fetch_fitness", "fetch_body_comp", "fetch_survey"):
        assert callable(getattr(adapter, m))

def test_mock_yields_raw_fitness_records():
    recs = list(MockLePaoAdapter(FIXTURE).fetch_fitness(None))
    assert len(recs) == 3 and all(isinstance(r, RawFitnessRecord) for r in recs)

def test_mock_parses_empty_cell_as_none():
    # CSV 契约：空字符串 → None，绝不可解析为 0 或 nan
    recs = list(MockLePaoAdapter(FIXTURE).fetch_fitness(None))
    assert any(r.vital_capacity_ml is None for r in recs)

def test_mock_returns_iterator_not_list():
    import types
    assert isinstance(MockLePaoAdapter(FIXTURE).fetch_fitness(None), types.GeneratorType)

@pytest.mark.parametrize("method", [
    "fetch_students", "fetch_fitness", "fetch_body_comp", "fetch_survey"])
def test_every_fetch_method_returns_a_generator(method):
    """**四个**方法都必须是生成器，不只 ``fetch_fitness``。

    ``fetch_students`` 的写法是 ``return self._students()``：惰性完全来自 ``_students``
    是个生成器函数。只断言 ``fetch_fitness`` 的话，哪天有人把 ``_students`` 改成列表推导，
    没有一条测试会红，而契约（Task 10 依赖的「先攒成 list 会让 500 人 × 两学年 × 三时点
    在内存里同时存在两份」）已经被破坏。
    """
    assert isinstance(getattr(MockLePaoAdapter(FIXTURE), method)(None),
                      types.GeneratorType)

def test_missing_dir_yields_empty_not_raises(tmp_path):
    assert list(MockLePaoAdapter(tmp_path / "nope").fetch_fitness(None)) == []

def test_http_adapter_declares_not_implemented():
    with pytest.raises(NotImplementedError):
        next(HttpLePaoAdapter("https://x", "t").fetch_fitness(None))

def test_http_adapter_does_not_expose_token():
    """token 必须是私有属性：公开属性会被 ``vars(adapter)`` 一类的日志路径直接带出去。"""
    adapter = HttpLePaoAdapter("https://api.lepao.example", "SECRET-TOKEN-xyz")
    assert not hasattr(adapter, "token")
    assert adapter._token == "SECRET-TOKEN-xyz"
    assert "SECRET-TOKEN-xyz" not in repr(adapter)
    assert "api.lepao.example" in repr(adapter)


# ---------------------------------------------------------------------------
# CSV 契约：文件名与列序（列序 = 数据类字段声明顺序）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,record_cls", [
    ("fitness.csv", RawFitnessRecord),
    ("body_comp.csv", RawBodyCompRecord),
    ("survey.csv", RawSurveyRecord),
])
def test_fixture_header_equals_dataclass_field_order(filename, record_cls):
    """夹具表头必须逐列、逐序等于数据类字段序——契约不靠口头约定，靠这条断言。"""
    with (FIXTURE / filename).open(newline="", encoding="utf-8-sig") as handle:
        header = tuple(next(csv.reader(handle)))
    assert header == tuple(f.name for f in dataclasses.fields(record_cls))

def test_fixture_students_header_matches_contract():
    """students.csv 没有对应数据类（``fetch_students`` 产出 dict），列序在此显式钉死。"""
    with (FIXTURE / "students.csv").open(newline="", encoding="utf-8-sig") as handle:
        header = tuple(next(csv.reader(handle)))
    assert header == ("student_no", "name", "sex", "birth", "department", "grade")

def test_wrong_column_order_raises(tmp_path):
    """列序写错必须在抽取处响亮失败，不能靠 DictReader 按名取值把契约漂移吞掉。"""
    columns = [f.name for f in dataclasses.fields(RawFitnessRecord)]
    swapped = [columns[1], columns[0], *columns[2:]]
    row = dict.fromkeys(swapped, "")
    row["student_no"], row["batch_key"], row["tested_on"] = (
        "2024010101", "2025-2026|week1", "2025-09-04")
    with (tmp_path / "fitness.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=swapped)
        writer.writeheader()
        writer.writerow(row)
    with pytest.raises(ValueError, match="表头"):
        list(MockLePaoAdapter(tmp_path).fetch_fitness(None))

def test_header_mismatch_names_the_first_differing_position(tmp_path):
    """表头报错要点名**第一处**不一致的列号与两边的列名。

    11 列的 ``fitness.csv`` 只打印「期望列表 + 实际列表」，等于让人用肉眼 diff 两行
    11 项的数组去找那一处错位——错误消息存在的意义就是省掉这次 diff。
    """
    columns = list(FITNESS_COLUMNS)
    swapped = [columns[1], columns[0], *columns[2:]]
    with (tmp_path / FITNESS_FILENAME).open("w", newline="", encoding="utf-8") as handle:
        handle.write(",".join(swapped) + "\n")
    with pytest.raises(ValueError,
                       match=r"第 1 列（下标 0）期望 'student_no'，实际 'batch_key'"):
        list(MockLePaoAdapter(tmp_path).fetch_fitness(None))

    # 少一列时指向被吃掉的那一列，而不是抛 IndexError
    with (tmp_path / FITNESS_FILENAME).open("w", newline="", encoding="utf-8") as handle:
        handle.write(",".join(columns[:-1]) + "\n")
    with pytest.raises(ValueError,
                       match=r"第 11 列（下标 10）期望 'distance_run_s'，实际 '（缺列）'"):
        list(MockLePaoAdapter(tmp_path).fetch_fitness(None))

@pytest.mark.parametrize("extra_fields", [0, 1])
def test_ragged_row_is_rejected(tmp_path, extra_fields):
    """行字段数与表头不符必须报错：``DictReader`` 会悄悄吸收两种畸形。

    短行被 ``restval=None`` 补齐（症状是「最后几列全为缺测」，与真实缺测无法区分），
    多出来的字段被塞进 ``row[None]``（直接消失）。方向上安全——补出来的是 ``None``/``""``
    而不是 ``0`` 或 ``nan``，按名取值也不会错位——但生产方少写一列这件事必须被看见。
    """
    values = ["2024010101", "2025-2026|week1", "2025-09-04"]
    if extra_fields:
        values = ["2024010101", *[""] * (len(FITNESS_COLUMNS) - 1), "多出来的一格"]
    with (tmp_path / FITNESS_FILENAME).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(FITNESS_COLUMNS)
        writer.writerow(values)
    with pytest.raises(ValueError,
                       match=r"fitness\.csv 第 2 行字段数与表头不符：期望 11 列，实际 "):
        list(MockLePaoAdapter(tmp_path).fetch_fitness(None))

def test_contract_constants_live_in_base_module():
    """Ruling 36：八个契约常量住在 ``base.py``，生产方不必 import 某个实现来拿列序。

    同时钉住 ``mock_lepao`` 只是 import 了**同一个对象**，没有偷偷留第二份清单。
    """
    from app.adapters import base, mock_lepao
    names = ("STUDENTS_FILENAME", "FITNESS_FILENAME", "BODY_COMP_FILENAME",
             "SURVEY_FILENAME", "STUDENT_COLUMNS", "FITNESS_COLUMNS",
             "BODY_COMP_COLUMNS", "SURVEY_COLUMNS")
    for name in names:
        assert hasattr(base, name), f"{name} 应住在 base.py"
        assert getattr(mock_lepao, name) is getattr(base, name), f"{name} 存在第二份真相"
    assert base.FITNESS_COLUMNS == tuple(
        f.name for f in dataclasses.fields(RawFitnessRecord))
    assert base.BODY_COMP_COLUMNS == tuple(
        f.name for f in dataclasses.fields(RawBodyCompRecord))
    assert base.SURVEY_COLUMNS == tuple(
        f.name for f in dataclasses.fields(RawSurveyRecord))
    assert base.STUDENT_COLUMNS == (
        "student_no", "name", "sex", "birth", "department", "grade")


# ---------------------------------------------------------------------------
# CSV 契约：空单元格语义（承重：Ruling 21 的 0 分陷阱）
# ---------------------------------------------------------------------------

def test_missing_measure_keeps_row_and_stays_none():
    """缺测那一行不能被丢掉，缺的那一格必须是 ``None``（不是 0、不是 nan）。

    ``0`` 会经 ``score_item`` 的低侧夹取拿到满分：50 米跑与耐力跑的 0.0 秒都是 100 分，
    一个缺测项因此会给体能最差的学生送上 20% 权重的满分，还同时抹掉两个桶的短板。
    """
    recs = {r.student_no: r for r in MockLePaoAdapter(FIXTURE).fetch_fitness(None)}
    assert len(recs) == 3
    missing = recs["2024010102"]
    assert missing.vital_capacity_ml is None
    assert missing.sprint_50m_s is not None  # 同一行的其他测量值照常带出

def test_real_zero_stays_zero_and_is_not_confused_with_missing():
    """合法的 ``0`` 与合法的**负值**都必须原样保留，不得被当成缺测。

    引体向上 0 次是真实成绩；坐位体前屈 ``-1.3`` cm 同样是真实成绩（Ruling 21 明确把
    负的坐位体前屈列为真实值——指尖够不到脚尖就是负数）。夹具第 2 行同时钉住这两半：
    ``strength_count=0``、``sit_and_reach_cm=-1.3``。
    """
    recs = {r.student_no: r for r in MockLePaoAdapter(FIXTURE).fetch_fitness(None)}
    assert recs["2024010102"].strength_count == 0.0
    assert recs["2024010102"].strength_count is not None
    assert recs["2024010102"].sit_and_reach_cm == -1.3
    assert recs["2024010102"].sit_and_reach_cm is not None

def test_no_numeric_cell_becomes_nan_or_inf():
    """三个源的每一个 ``float``（含 ``dimensions`` 的每一个值）都必须是有限的。"""
    ad = MockLePaoAdapter(FIXTURE)
    for records in (ad.fetch_fitness(None), ad.fetch_body_comp(None),
                    ad.fetch_survey(None)):
        for record in records:
            for field in dataclasses.fields(record):
                value = getattr(record, field.name)
                if isinstance(value, float):
                    assert math.isfinite(value), f"{field.name} 读出了非有限值"
                if field.name == "dimensions":
                    # raw_answers 声明为无类型 dict，不在浮点契约内（见 _json_object）
                    assert value, "dimensions 不应为空"
                    for key, score in value.items():
                        assert isinstance(score, float), f"dimensions[{key!r}] 不是 float"
                        assert math.isfinite(score), f"dimensions[{key!r}] 读出了非有限值"

def test_body_comp_empty_cell_becomes_none():
    recs = {r.student_no: r for r in MockLePaoAdapter(FIXTURE).fetch_body_comp(None)}
    assert recs["2024010102"].smi is None
    assert recs["2024010102"].body_fat_pct is not None

def test_nan_literal_cell_is_rejected(tmp_path):
    """契约要求缺测写空字符串；读到 ``nan``/``inf`` 字面量必须报错而不是静默透传。

    pandas 的 ``to_csv`` 缺省把 NaN 写成空串，但手写 ``str(float('nan'))`` 就会漏出
    ``nan`` 字面量——``float("nan")`` 解析成功，随后所有比较都为假，缺测会被当成
    一个既不低于也不高于任何阈值的幽灵值一路带到分层。
    """
    columns = [f.name for f in dataclasses.fields(RawFitnessRecord)]
    row = dict.fromkeys(columns, "")
    row.update(student_no="2024010101", batch_key="2025-2026|week1",
               tested_on="2025-09-04", vital_capacity_ml="nan")
    with (tmp_path / "fitness.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerow(row)
    with pytest.raises(ValueError, match="vital_capacity_ml"):
        list(MockLePaoAdapter(tmp_path).fetch_fitness(None))

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nan_literal_inside_dimensions_json_is_rejected(tmp_path, bad):
    """``dimensions`` 这个 JSON 列同样不得漏进 ``nan``/``inf``（Ruling 39 的消费侧）。

    这条路径比数值列更隐蔽：``json.dumps`` 缺省 ``allow_nan=True`` **写得出来**，
    ``json.loads`` 缺省又**读得回来**，``float(nan)`` 也不抛——两头都不报错，于是
    Task 6 一旦漏了 ``allow_nan=False``，一个 nan 就能原样写盘、原样读回，最后在与任何
    阈值比较时恒为假。下面的 ``assert "NaN" in dumped`` 就是在钉住「攻击面确实成立」。
    """
    dumped = json.dumps({"运动乐趣": bad})          # 缺省 allow_nan=True
    assert "NaN" in dumped or "Infinity" in dumped
    _write_survey_row(tmp_path, dimensions=dumped)
    with pytest.raises(ValueError,
                       match=r"survey\.csv 第 2 行 dimensions 的维度值是非有限值"):
        list(MockLePaoAdapter(tmp_path).fetch_survey(None))

def test_error_message_names_file_line_and_column(tmp_path):
    """报错必须同时带**文件名 + 行号 + 列名**——这是全模块的主张，得有条测试钉住。

    500 人 × 两学年 × 三时点的 CSV 里，一个裸 ``ValueError: could not convert string to
    float: '四千'`` 只能靠肉眼找那一格；``match`` 里把三者写全，消息退化就会红。
    """
    _write_fitness_row(tmp_path, vital_capacity_ml="四千")
    with pytest.raises(ValueError,
                       match=r"fitness\.csv 第 2 行 vital_capacity_ml 不是合法数值: '四千'"):
        list(MockLePaoAdapter(tmp_path).fetch_fitness(None))


# ---------------------------------------------------------------------------
# since 增量语义（Ruling 33）：排他过滤，None 表示全量
# ---------------------------------------------------------------------------

def test_since_none_returns_everything_from_every_source():
    ad = MockLePaoAdapter(FIXTURE)
    assert len(list(ad.fetch_students(None))) == 3
    assert len(list(ad.fetch_fitness(None))) == 3
    assert len(list(ad.fetch_body_comp(None))) == 3
    assert len(list(ad.fetch_survey(None))) == 3

def test_since_is_exclusive_on_fitness_tested_on():
    """日期恰等于 ``since`` 的那条必须被排除——水位线是「已经同步过」的意思。"""
    got = [r.tested_on for r in MockLePaoAdapter(FIXTURE).fetch_fitness("2025-06-18")]
    assert got == ["2025-09-04", "2025-10-22"]

def test_since_is_exclusive_on_body_comp_measured_on():
    got = [r.measured_on for r in MockLePaoAdapter(FIXTURE).fetch_body_comp("2025-10-22")]
    assert got == ["2025-12-17"]

def test_since_is_exclusive_on_survey_filled_on():
    got = [r.filled_on for r in MockLePaoAdapter(FIXTURE).fetch_survey("2025-10-21")]
    assert got == ["2025-12-16"]

def test_since_after_every_row_yields_empty():
    assert list(MockLePaoAdapter(FIXTURE).fetch_fitness("2026-01-01")) == []

def test_non_iso_since_raises_value_error():
    """水位线格式写错必须立刻炸，不能静默退化成「全量」或「空」。"""
    with pytest.raises(ValueError, match="since"):
        list(MockLePaoAdapter(FIXTURE).fetch_fitness("10/09/2025"))

def test_record_dated_exactly_since_is_excluded(tmp_path):
    """排他语义的最小复现：记录日期 == 水位线 → 不返回；早一天 → 返回。"""
    _write_fitness_row(tmp_path, tested_on="2025-09-04")
    assert list(MockLePaoAdapter(tmp_path).fetch_fitness("2025-09-04")) == []
    assert len(list(MockLePaoAdapter(tmp_path).fetch_fitness("2025-09-03"))) == 1

def test_time_suffixed_record_date_raises_instead_of_breaking_exclusion(tmp_path):
    """带 ``T`` 的记录日期必须报错，不能悄悄判成「晚于水位线」（Ruling 38）。

    实测（Python 3.11.1）字符串比较 ``'2025-09-04T10:00' > '2025-09-04'`` 为 **True**，
    而两者其实是同一天：排他语义被击穿，恰在水位线上的那条记录会被永久重复抽取，水位线
    再也推不过它。真实乐跑接口完全可能返回这种带时间的日期串。
    """
    assert "2025-09-04T10:00" > "2025-09-04"          # 钉住「字符串比较确实是错的」
    _write_fitness_row(tmp_path, tested_on="2025-09-04T10:00")
    with pytest.raises(ValueError, match=r"fitness\.csv 第 2 行 tested_on 不是合法的 ISO 日期"):
        list(MockLePaoAdapter(tmp_path).fetch_fitness("2025-09-04"))

@pytest.mark.parametrize("tested_on", ["2025-9-5", "04/09/2025", "2025-09-04 10:00"])
def test_non_padded_or_non_iso_record_date_raises_when_filtering(tmp_path, tested_on):
    """记录侧日期不是零填充 ``YYYY-MM-DD`` → 在过滤时响亮失败。

    ``'2025-9-5' > '2025-10-01'`` 实测为 **True**（实际更早），字典序比较对非定宽日期
    根本不成立。修法里指定的 ``date.fromisoformat`` **不接受** ``2025-9-5``（实测
    Python 3.11.1 抛 ``ValueError``），所以这一类日期是「报错」而不是「按日历排对」：
    比原先的静默多抽更容易定位到写错的生产方，也与契约新写的「必须零填充」一致。
    """
    _write_fitness_row(tmp_path, tested_on=tested_on)
    with pytest.raises(ValueError, match=r"fitness\.csv 第 2 行 tested_on 不是合法的 ISO 日期"):
        list(MockLePaoAdapter(tmp_path).fetch_fitness("2025-10-01"))

def test_compact_iso_record_date_is_accepted_when_filtering(tmp_path):
    """``20250904`` 是 ``date.fromisoformat`` 接受的紧凑写法，按日历正确排序、不报错。"""
    _write_fitness_row(tmp_path, tested_on="20250904")
    assert list(MockLePaoAdapter(tmp_path).fetch_fitness("2025-09-04")) == []
    assert len(list(MockLePaoAdapter(tmp_path).fetch_fitness("2025-09-03"))) == 1

def test_record_date_format_is_only_enforced_when_filtering(tmp_path):
    """全量拉取（``since=None``）不解析日期，格式问题原样交给 Task 5 的清洗层。

    这是有意的不对称：全量模式不需要比较，此时把「日期写得非规范」升级成中断整条管道，
    等于抢走清洗层该记一条 ``cleaning_log`` 的活（与 ``student_no`` 缺失的处理一致）。
    增量模式必须解析才能比较，故在那里强制。
    """
    _write_fitness_row(tmp_path, tested_on="2025-9-5")
    got = [r.tested_on for r in MockLePaoAdapter(tmp_path).fetch_fitness(None)]
    assert got == ["2025-9-5"]


def test_fetch_students_ignores_since_and_returns_full_set():
    """Ruling 33：``fetch_students`` 不支持增量，``since`` 非 None 时同样返回全量。"""
    ad = MockLePaoAdapter(FIXTURE)
    assert len(list(ad.fetch_students("2025-09-04"))) == 3

def test_fetch_students_yields_dicts_keyed_by_header():
    rows = list(MockLePaoAdapter(FIXTURE).fetch_students(None))
    assert all(isinstance(row, dict) for row in rows)
    assert set(rows[0]) == {"student_no", "name", "sex", "birth", "department", "grade"}
    assert {row["student_no"] for row in rows} == {
        "2024010101", "2024010102", "2024010103"}
    assert {row["sex"] for row in rows} == {"male", "female"}

def test_students_sex_values_are_validated_against_domain_enum(tmp_path):
    """``sex`` 的取值域归 Task 2 的 ``Sex`` 枚举；写错必须在抽取那一行就炸。

    产出的是普通 ``str``（枚举的 value）而不是枚举成员：``str(Sex.MALE)`` 是
    ``"Sex.MALE"``，枚举混进原始 dict 后会被日志或入库路径写成错值。
    """
    rows = list(MockLePaoAdapter(FIXTURE).fetch_students(None))
    assert [row["sex"] for row in rows] == ["male", "female", "male"]
    assert all(type(row["sex"]) is str for row in rows)

    with (tmp_path / "students.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(STUDENT_COLUMNS)
        writer.writerow(["2024010101", "林思远", "男", "2006-03-12", "计算机学院", "2"])
    with pytest.raises(ValueError, match="sex 值非法"):
        list(MockLePaoAdapter(tmp_path).fetch_students(None))


# ---------------------------------------------------------------------------
# 其余两个源的类型与 JSON 列
# ---------------------------------------------------------------------------

def test_mock_yields_raw_body_comp_records():
    recs = list(MockLePaoAdapter(FIXTURE).fetch_body_comp(None))
    assert len(recs) == 3 and all(isinstance(r, RawBodyCompRecord) for r in recs)
    assert all(isinstance(r.measured_on, str) for r in recs)

def test_mock_yields_raw_survey_records_with_json_columns():
    recs = list(MockLePaoAdapter(FIXTURE).fetch_survey(None))
    assert len(recs) == 3 and all(isinstance(r, RawSurveyRecord) for r in recs)
    for record in recs:
        assert isinstance(record.total, float)
        # spec §10.9：5 维度 × 5 点李克特
        assert len(record.dimensions) == 5
        assert all(isinstance(v, float) and 1 <= v <= 5 for v in record.dimensions.values())
        assert isinstance(record.raw_answers, dict) and record.raw_answers

def test_missing_file_yields_empty_for_every_source(tmp_path):
    """目录存在但 CSV 不在：一律 yield 空。Task 6 只写三类 CSV 时管道照样能跑。"""
    ad = MockLePaoAdapter(tmp_path)
    assert list(ad.fetch_students(None)) == []
    assert list(ad.fetch_fitness(None)) == []
    assert list(ad.fetch_body_comp(None)) == []
    assert list(ad.fetch_survey(None)) == []


# ---------------------------------------------------------------------------
# batch_key 格式：parse_batch_key / make_batch_key 是唯一所有者
# （Task 10 不得自己 split("|")，Task 6 不得自己 f"{ay}|{tp}"——Ruling 33/35）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key,expected", [
    ("2025-2026|week1", ("2025-2026", "week1")),
    ("2024-2025|week16", ("2024-2025", "week16")),
    ("2025-2026|week8", ("2025-2026", "week8")),
])
def test_parse_batch_key_happy_path(key, expected):
    assert parse_batch_key(key) == expected

@pytest.mark.parametrize("key", [
    "2025-2026week1",     # 缺分隔符
    "2025-2026|week9",    # 时点不在 {week1, week8, week16} 域内
    "2025-2026|week1|x",  # 分隔符多于一个
    "25-26|week1",        # 学年不是「四位-四位」
    "2025-2026|",         # 时点为空
    "",                   # 空串
])
def test_parse_batch_key_rejects_malformed(key):
    with pytest.raises(ValueError):
        parse_batch_key(key)

@pytest.mark.parametrize("timepoint", sorted(TIMEPOINTS))
def test_make_batch_key_is_the_exact_inverse_of_parse_batch_key(timepoint):
    """Ruling 35：写侧也只有一个所有者——往返必须恒等，覆盖全部合法时点。"""
    key = make_batch_key("2025-2026", timepoint)
    assert key == f"2025-2026|{timepoint}"
    assert parse_batch_key(key) == ("2025-2026", timepoint)
    assert make_batch_key(*parse_batch_key(key)) == key

@pytest.mark.parametrize("academic_year,timepoint", [
    ("25-26", "week1"),            # 学年不是「四位-四位」
    ("2025-2026", "week9"),        # 时点越域
    ("2025-2026", ""),             # 时点为空
    ("2025-2026|week1", "week1"),  # 学年里混进分隔符 → 会造出三段键
    ("", "week1"),
])
def test_make_batch_key_rejects_malformed(academic_year, timepoint):
    """构造时就炸：畸形键放过去，要等到 Task 10 解析或入库 CHECK 才报错，隔了两三层。"""
    with pytest.raises(ValueError):
        make_batch_key(academic_year, timepoint)

def test_fixture_batch_keys_survive_a_parse_make_roundtrip():
    """夹具里的每个 ``batch_key`` 都必须能被「解析 → 重新构造」还原（读写两侧同一格式）。"""
    for record in MockLePaoAdapter(FIXTURE).fetch_fitness(None):
        assert make_batch_key(*parse_batch_key(record.batch_key)) == record.batch_key


# ---------------------------------------------------------------------------
# 文本列的分派（M6：显式点名，不反射 field.type）
# ---------------------------------------------------------------------------

def test_text_column_set_matches_dataclass_declarations():
    """``TEXT_COLUMNS`` 必须与三个数据类里声明为 ``str`` 的字段完全一致。

    用 ``typing.get_type_hints`` 而不是 ``field.type`` 取声明：前者对
    ``from __future__ import annotations``（延迟注解）同样成立，所以这条漂移测试不会因为
    base.py 哪天改了注解求值时机而失效。``filled_on`` 虽不经 ``_build``（``RawSurveyRecord``
    单独构造），但它同样走 ``_text_cell``，故一并纳入这份集合。
    """
    declared = {
        f.name
        for cls in (RawFitnessRecord, RawBodyCompRecord, RawSurveyRecord)
        for f in dataclasses.fields(cls)
        if typing.get_type_hints(cls)[f.name] is str
    }
    assert declared == set(TEXT_COLUMNS)

def test_all_digit_student_no_stays_text(tmp_path):
    """``float("2024010101")`` 是**成功**的（实测得 ``2024010101.0``）。

    所以「文本列走文本解析」这件事不能靠注解反射的运气：一旦分派走偏，学号会静默变成
    浮点数，一处都不报错。这条用例与上一条一起钉住显式点名的分派。
    """
    assert float("2024010101") == 2024010101.0        # 钉住「走偏不会抛错」这个前提
    _write_fitness_row(tmp_path, student_no="2024010101")
    record = next(iter(MockLePaoAdapter(tmp_path).fetch_fitness(None)))
    assert record.student_no == "2024010101"
    assert type(record.student_no) is str
    assert type(record.batch_key) is str and type(record.tested_on) is str


# ---------------------------------------------------------------------------
# 抽象基类与 HTTP 骨架
# ---------------------------------------------------------------------------

def test_adapter_base_is_abstract():
    with pytest.raises(TypeError):
        DataSourceAdapter()

@pytest.mark.parametrize("method", [
    "fetch_students", "fetch_fitness", "fetch_body_comp", "fetch_survey"])
def test_http_skeleton_raises_for_every_method(method):
    """spec §3.4：骨架先行，四个方法都还没实现，但契约形状与 Mock 完全一致。"""
    adapter = HttpLePaoAdapter("https://api.lepao.example", "t")
    with pytest.raises(NotImplementedError):
        next(getattr(adapter, method)(None))

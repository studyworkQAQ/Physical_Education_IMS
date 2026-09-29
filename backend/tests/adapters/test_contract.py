# backend/tests/adapters/test_contract.py
"""DataSourceAdapter 契约测试：Mock 与 HTTP 两个实现跑同一组契约。

``tests/fixtures/lepao_sample/`` 下的四个迷你 CSV 是**契约的可执行定义**（进版本控制）：
文件名、列序、空单元格语义、``since`` 排他边界都由这里钉死，Task 6 的 ``write_csv``
必须逐列对齐，Task 10 的管道必须按同一语义消费。
"""
import pathlib, pytest
from app.adapters.base import DataSourceAdapter, RawFitnessRecord
from app.adapters.mock_lepao import MockLePaoAdapter
from app.adapters.http_lepao import HttpLePaoAdapter

# 下面是契约扩展用例需要的导入（brief Step 1 的原文用例只用上面四行）
import csv, dataclasses, math
from app.adapters.base import RawBodyCompRecord, RawSurveyRecord, parse_batch_key
from app.adapters.mock_lepao import STUDENT_COLUMNS

FIXTURE = pathlib.Path(__file__).parents[1] / "fixtures" / "lepao_sample"

def implementations():
    return [MockLePaoAdapter(FIXTURE), HttpLePaoAdapter("https://api.lepao.example", "t")]

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

def test_missing_dir_yields_empty_not_raises(tmp_path):
    assert list(MockLePaoAdapter(tmp_path / "nope").fetch_fitness(None)) == []

def test_http_adapter_declares_not_implemented():
    with pytest.raises(NotImplementedError):
        next(HttpLePaoAdapter("https://x", "t").fetch_fitness(None))


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
    """合法的 ``0`` 必须原样保留：引体向上 0 次是真实成绩，不是缺测。"""
    recs = {r.student_no: r for r in MockLePaoAdapter(FIXTURE).fetch_fitness(None)}
    assert recs["2024010102"].strength_count == 0.0
    assert recs["2024010102"].strength_count is not None

def test_no_numeric_cell_becomes_nan_or_inf():
    ad = MockLePaoAdapter(FIXTURE)
    for records in (ad.fetch_fitness(None), ad.fetch_body_comp(None)):
        for record in records:
            for field in dataclasses.fields(record):
                value = getattr(record, field.name)
                if isinstance(value, float):
                    assert math.isfinite(value), f"{field.name} 读出了非有限值"

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
# batch_key 格式：parse_batch_key 是唯一所有者（Task 10 不得自己 split("|")）
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

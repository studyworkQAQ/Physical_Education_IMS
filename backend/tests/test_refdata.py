"""参考表加载与进程内缓存的约束：CSV 只允许 app/refdata.py 读。

⚠️ **本文件是 ``national_standard_2014.csv`` 的唯一守卫**（Ruling 213）。那张表是本仓
**唯一不可由代码重推**的知识资产（其余产物都能由 ``app/seed`` 重新生成），而它由
**体育测量学专家手工编辑**。终审在它上面做了 6 次变异，**4 次 428 条测试全绿**，含
「整行删除一档」——原因是本文件原有的档位数断言两侧同源于那一份 CSV（硬规矩 #35）。
现在有三道闸，改动评分表**必然**先撞上其中至少一道：

1. :func:`test_national_standard_csv_fingerprint_is_pinned` —— 文件哈希指纹；
2. :func:`test_segment_counts_are_pinned_verbatim` —— 28 组档位数**字面写死**；
3. :func:`app.refdata._validate_group` 的四条表级不变量（由本文件下面 4 条测试钉住）。
"""
import collections
import csv
import dataclasses
import hashlib

import pytest

from app import refdata
from app.domain.tables import StandardTable
from app.domain.indicators import AGE_GROUPS, Sex, ScoredItem

CSV_HEADER = "item,sex,age_group,score,raw_value\n"
# 两行合法数据 + 第三行待参数化注入的非法值，非法行落在 CSV 第 4 行
GOOD_ROWS = ("bmi,male,大一、大二,80,0\n"
             "bmi,male,大一、大二,100,20\n")

# ``national_standard_2014.csv`` 的 sha256 前 16 位（大写十六进制）。
# **本轮亲算**（``hashlib.sha256(path.read_bytes()).hexdigest()[:16].upper()``），
# 与账本 ``progress.md`` Ruling 223 记的 ``D2C8E539E2FA0029`` 逐字一致；文件 21412 字节、
# 502 个数据行。
STANDARD_FINGERPRINT = "D2C8E539E2FA0029"

# 28 组各自的档位数，**字面写死、不从 CSV 读回**（硬规矩 #35：断言两侧不得同源）。
# 期望值的来源是 ``data/README_national_standard.md``：BMI 是官方「区间 → 得分」的
# 6 个闭区间端点 + ``0``/``999`` 两个哨兵 = **8** 档；引体向上（男）官方及格段只有
# 76/72/68/64/60 五档有实测次数、78/74/70/66/62 五档留空，故是 **15** 档（女生
# 1 分钟仰卧起坐是完整 20 档）；其余各项都是完整的 **20** 档。
# 合计 4×8 + 2×15 + 22×20 = **502** 行 = 该 CSV 的数据行数。
EXPECTED_SEGMENT_COUNTS: dict[tuple[str, str, str], int] = {
    ("bmi", "male", "大一、大二"): 8,
    ("bmi", "male", "大三、大四"): 8,
    ("bmi", "female", "大一、大二"): 8,
    ("bmi", "female", "大三、大四"): 8,
    ("vital_capacity", "male", "大一、大二"): 20,
    ("vital_capacity", "male", "大三、大四"): 20,
    ("vital_capacity", "female", "大一、大二"): 20,
    ("vital_capacity", "female", "大三、大四"): 20,
    ("sprint_50m", "male", "大一、大二"): 20,
    ("sprint_50m", "male", "大三、大四"): 20,
    ("sprint_50m", "female", "大一、大二"): 20,
    ("sprint_50m", "female", "大三、大四"): 20,
    ("sit_and_reach", "male", "大一、大二"): 20,
    ("sit_and_reach", "male", "大三、大四"): 20,
    ("sit_and_reach", "female", "大一、大二"): 20,
    ("sit_and_reach", "female", "大三、大四"): 20,
    ("standing_jump", "male", "大一、大二"): 20,
    ("standing_jump", "male", "大三、大四"): 20,
    ("standing_jump", "female", "大一、大二"): 20,
    ("standing_jump", "female", "大三、大四"): 20,
    ("pull_up_or_sit_up", "male", "大一、大二"): 15,
    ("pull_up_or_sit_up", "male", "大三、大四"): 15,
    ("pull_up_or_sit_up", "female", "大一、大二"): 20,
    ("pull_up_or_sit_up", "female", "大三、大四"): 20,
    ("distance_run", "male", "大一、大二"): 20,
    ("distance_run", "male", "大三、大四"): 20,
    ("distance_run", "female", "大一、大二"): 20,
    ("distance_run", "female", "大三、大四"): 20,
}


def _csv_group_counts(path):
    """独立于 load_standard 再数一遍 CSV，用于交叉核对每组的档位数。"""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return len(rows), collections.Counter(
        (r["item"], r["sex"], r["age_group"]) for r in rows)


def test_data_dir_points_at_backend_data():
    assert refdata.DATA_DIR.name == "data"
    assert (refdata.DATA_DIR / "national_standard_2014.csv").is_file()

def test_load_standard_returns_frozen_table():
    t = refdata.load_standard()
    assert isinstance(t, StandardTable)
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.segments = {}

def test_segments_mapping_is_read_only():
    # frozen=True 只是浅冻结：挡得住「换掉整个字段」，挡不住 segments[key] = ... 就地改写。
    # 而 standard() 是进程内共享单例，一次误写会让之后所有查表静默变质，
    # spec §1.3 的逐人可追溯性也就没了，所以映射本身必须是只读视图。
    t = refdata.load_standard()
    key = next(iter(t.segments))
    with pytest.raises(TypeError):
        t.segments[key] = ((0.0, 0),)
    with pytest.raises(TypeError):
        del t.segments[key]

def test_standard_is_cached_singleton():
    assert refdata.standard() is refdata.standard()

def test_table_covers_every_item_sex_agegroup():
    # 键集必须**恰好等于** 项 × 性别 × 年级组 的全笛卡尔积：0 缺失、0 孤儿。
    # 只断言「每组 >= 2 档」是抓不住的——CSV 里一个拼错的 item 会把某一行从正确的组
    # 悄悄摘走、另立一个孤儿键，该组从 20 档变 19 档，缺掉的那一档会让整个区间的
    # 查表结果偏移，而任何地方都不报错，短板判定还会静默漏项。
    t = refdata.load_standard()
    expected_keys = {(i.value, s.value, ag)
                     for i in ScoredItem for s in Sex for ag in AGE_GROUPS}
    assert set(t.segments) == expected_keys
    # 每组档位数必须等于 CSV 里该组的行数（再独立数一遍，不复用 load_standard 的解析）
    total, per_group = _csv_group_counts(refdata.DATA_DIR / refdata.STANDARD_FILENAME)
    assert total == sum(per_group.values()) == sum(len(v) for v in t.segments.values())
    mismatched = {k: (len(t.segments[k]), per_group[k])
                  for k in expected_keys if len(t.segments[k]) != per_group[k]}
    assert mismatched == {}

@pytest.mark.parametrize("column,bad_value", [
    ("item", "vital_capacty"),          # 拼错：少一个 i
    ("sex", "Male"),                     # 大小写不符枚举值
    ("age_group", "大一-大二"),           # 分隔符不符官方年级组名
])
def test_malformed_csv_raises_with_line_number(tmp_path, column, bad_value):
    # 三个分组列必须逐行按枚举校验，且报错要能直接定位到 CSV 行号与非法值本身，
    # 否则录错一个字的人得靠肉眼在 502 行里找。
    values = {"item": "bmi", "sex": "male", "age_group": "大一、大二",
              "score": "60", "raw_value": "28"}
    values[column] = bad_value
    bad = tmp_path / "bad.csv"
    bad.write_text(
        CSV_HEADER + GOOD_ROWS + ",".join(values.values()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        refdata.load_standard(bad)
    message = str(excinfo.value)
    assert "第 4 行" in message        # 表头 1 行 + 合法 2 行，非法行是第 4 行
    assert bad_value in message
    assert f"{column} 值非法" in message

def test_missing_csv_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        refdata.load_standard(tmp_path / "nope.csv")


# ---------------------------------------------------------------------------
# Ruling 213：评分表的三道闸
# ---------------------------------------------------------------------------


def test_national_standard_csv_fingerprint_is_pinned():
    """**改表必须先改这条测试**——这是「知识资产变更需被显式承认」的闸门（Ruling 213 ②）。

    ``national_standard_2014.csv`` 是本仓唯一不可由代码重推的文件，而它由体育测量学专家
    手工编辑。终审在它上面做了 6 次变异（M1 改 ``raw_value``、M4 改另一处 ``raw_value``、
    **M6 整行删除**、M7 改 ``score``、M5/M8 破坏升序），其中 **4 次 428 条测试全绿**——
    改一个数值不破坏任何形状不变量，只有指纹能挡住它。

    期望值 :data:`STANDARD_FINGERPRINT` 是**字面量**，实际值现算自磁盘上的文件，
    两侧不同源（硬规矩 #35）。

    红了的正确处置**不是**把新哈希抄进来就算了：先在 ``data/README_national_standard.md``
    的「复核结论」里登记这次改动的来源与逐格核对结果，再更新本常量与
    :data:`EXPECTED_SEGMENT_COUNTS`（若档位数变了）。
    """
    path = refdata.DATA_DIR / refdata.STANDARD_FILENAME
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16].upper()
    assert digest == STANDARD_FINGERPRINT, (
        f"国标评分表被改动了：sha256 前 16 位是 {digest}，钉住的是 {STANDARD_FINGERPRINT}。"
        f"这张表是本仓唯一不可由代码重推的知识资产，改动必须被显式承认——"
        f"请先在 data/README_national_standard.md 登记来源与逐格核对，再更新本常量"
    )


def test_segment_counts_are_pinned_verbatim():
    """28 组各自的档位数**字面写死**在 :data:`EXPECTED_SEGMENT_COUNTS` 里（Ruling 213 ③）。

    这条与上面 ``test_table_covers_every_item_sex_agegroup`` 的档位数断言**不是一回事**，
    差别正在硬规矩 #35：那一条比的是「``len(t.segments[k])`` == **同一份 CSV 里该组的
    行数**」，两侧都从被改的文件数，删一行两边同时少一、**恒等**（终审 M6 因此 428 全绿）。
    本条的期望侧是测试里的字面量、实际侧经 :func:`app.refdata.segment_count`
    （此前**全仓零调用者**）取，删一行只有一侧变，当场红。

    offender 一次性报全（Ruling 157：循环里逐条 assert 会在第一例就停、证据被截断）。
    """
    t = refdata.load_standard()
    offenders = {
        key: (refdata.segment_count(t, ScoredItem(key[0]), Sex(key[1]), key[2]), want)
        for key, want in EXPECTED_SEGMENT_COUNTS.items()
        if refdata.segment_count(t, ScoredItem(key[0]), Sex(key[1]), key[2]) != want
    }
    assert offenders == {}, f"(实际档位数, 期望档位数): {offenders}"
    # 键集也必须与全笛卡尔积一致：少写一组等于那一组没人守（两侧仍是字面量 vs 生产解析）
    assert set(EXPECTED_SEGMENT_COUNTS) == {
        (i.value, s.value, ag) for i in ScoredItem for s in Sex for ag in AGE_GROUPS
    }
    assert sum(EXPECTED_SEGMENT_COUNTS.values()) == 502


def _write(tmp_path, rows):
    path = tmp_path / "std.csv"
    path.write_text(CSV_HEADER + "".join(row + "\n" for row in rows), encoding="utf-8")
    return path


def test_load_standard_rejects_a_score_outside_the_official_vocabulary(tmp_path):
    """表级不变量 ③：``score`` 必须属 :data:`app.refdata.OFFICIAL_SCORES`。

    这是终审 **M7**（同组 ``score 64→65``）的形状：65 不是国标 2014 的任何档位分，
    改前它 428 全绿——因为 ``test_indicators.py`` 的 ``official`` 与 ``_official_scores``
    两处都**从被改的同一份 CSV** 取词表（硬规矩 #35 的又一例）。改后加载当场 ``ValueError``。
    """
    path = _write(tmp_path, [
        "standing_jump,male,大一、大二,60,200",
        "standing_jump,male,大一、大二,65,210",     # ← 65 不在官方词表里
        "standing_jump,male,大一、大二,70,220",
    ])
    with pytest.raises(ValueError) as excinfo:
        refdata.load_standard(path)
    message = str(excinfo.value)
    assert "第 3 行" in message and "score=65" in message
    assert "官方档位分" in message


def test_load_standard_rejects_duplicate_raw_value_within_a_group(tmp_path):
    """表级不变量 ②：组内 ``raw_value`` 不得重复（排序后即严格升序）。

    两行同 ``raw_value`` 时 ``score_item`` 的「就低取档」结果取决于 CSV 行序，而
    ``load_standard`` 会排序、行序按设计不承重——即同一份数据换个行序就换答案。
    报错必须同时给出**两端**的行号，手工维护这张表的人才定位得到。
    """
    path = _write(tmp_path, [
        "standing_jump,male,大一、大二,60,200",
        "standing_jump,male,大一、大二,64,210",
        "standing_jump,male,大一、大二,66,210",     # ← 与上一行同 raw_value
    ])
    with pytest.raises(ValueError) as excinfo:
        refdata.load_standard(path)
    message = str(excinfo.value)
    assert "raw_value 重复" in message
    assert "第 3 行" in message and "第 4 行" in message


def test_load_standard_rejects_non_monotonic_scores_for_a_non_bmi_item(tmp_path):
    """表级不变量 ④：非 BMI 项沿 ``raw_value`` 方向的 ``score`` 必须单调（不增或不减）。

    这是终审 **M5 / M8**（破坏组内升序）真正该撞上的那道闸——改前它们只红了 1 条，
    而红的是**集成层的趋势分布测试**（碰巧撞上），不是任何表级校验。非单调会让
    ``score_item`` 的就低取档、``_lower_is_better`` 的方向推断与 ``national_norm`` 的
    端点比较同时失效。
    """
    path = _write(tmp_path, [
        "standing_jump,male,大一、大二,60,200",
        "standing_jump,male,大一、大二,50,210",     # ← 越大越好项却降了一档
        "standing_jump,male,大一、大二,70,220",
    ])
    with pytest.raises(ValueError) as excinfo:
        refdata.load_standard(path)
    message = str(excinfo.value)
    assert "非单调" in message and "[60, 50, 70]" in message


def test_load_standard_rejects_a_group_with_fewer_than_two_segments(tmp_path):
    """表级不变量 ①：每组至少 :data:`app.refdata.MIN_SEGMENTS_PER_GROUP` 档。

    一档的组会让 ``score_item`` 的首末夹取退化成常数（任何输入都得同一个分）、
    ``national_norm`` 的量程 ``hi - lo`` 为 0（五个分位点全等）。
    """
    path = _write(tmp_path, ["standing_jump,male,大一、大二,60,200"])
    with pytest.raises(ValueError) as excinfo:
        refdata.load_standard(path)
    message = str(excinfo.value)
    assert "只有 1 档" in message and "第 [2] 行" in message


def test_bmi_groups_are_exempt_from_the_monotonicity_check(tmp_path):
    """**反向守卫**：单调性校验必须排除 BMI，否则会把正确的表判成错的（Ruling 213 的 ⚠️）。

    BMI 是官方「区间 → 得分」的非单调映射（两头 80、中间 100），CSV 用 ``0`` 与 ``999``
    两个哨兵把 ``≤17.8`` 与 ``≥28.0`` 两个开口区间封成有限档位序列
    （``data/README_national_standard.md``：「哨兵 ``0`` 和 ``999`` 不是国标数值」）。
    真实表里 BMI 四组的得分序列是 ``80, 80, 100, 100, 80, 80, 60, 60``——**它就该不单调**。
    本条用真实表的 BMI 四组原样重放：把它当非 BMI 项校验会当场 ``ValueError``。
    """
    t = refdata.load_standard()
    for sex in Sex:
        for age_group in AGE_GROUPS:
            key = (ScoredItem.BMI.value, sex.value, age_group)
            rows = t.segments[key]
            scores = [score for _, score in rows]
            # 前置：这一组确实非单调（否则本条测不到豁免）
            assert not all(b >= a for a, b in zip(scores, scores[1:]))
            assert not all(b <= a for a, b in zip(scores, scores[1:]))
            path = _write_rows(tmp_path, key, rows)
            assert refdata.load_standard(path).segments[key] == rows


def _write_rows(tmp_path, key, rows):
    item, sex, age_group = key
    path = tmp_path / f"bmi_{sex}_{age_group}.csv"
    path.write_text(
        CSV_HEADER + "".join(
            f"{item},{sex},{age_group},{score},{raw}\n" for raw, score in rows
        ),
        encoding="utf-8",
    )
    return path

"""参考数据加载：全项目唯一允许读 ``backend/data/*.csv`` 的模块。

依赖方向是 refdata → domain：这里把 CSV 解析成 app/domain/tables.py 的
StandardTable，再交给 domain 的纯函数使用；进程内缓存也放在这里而不是 domain。
domain 因此保持为无 I/O 的叶子（Ruling 15），不会隐式依赖磁盘上某个 CSV 是否存在。

本模块是 ``backend/data/`` 这个**目录常量**与**国标评分表 / 指标区间表两个文件名**的唯一
所有者：``BACKEND_DIR`` 取自 :mod:`app.config`（叶子，只 import ``pathlib``，故
refdata → config 不可能造出环），``DATA_DIR`` / ``STANDARD_FILENAME`` /
``RANGES_FILENAME`` 都住在这里。

``RANGES_FILENAME`` 原先住在 ``app/seed/generate.py``，于是生产层为了拿一个**文件名字符串**
必须 import 仿真数据生成器（基线 ``e26347f`` 的 ``app/pipeline/run_stratify.py:49``）；
搬到这里之后 ``pipeline → seed`` 那条边消失，且它与 ``DATA_DIR`` 住在同一个模块里，
「哪个文件在哪个目录」这件事不必再跨两个模块拼。

⚠️ **处方侧那两个 YAML 的文件名不住这里**（Plan 02 Task 2）：``EXERCISES_FILENAME`` 与
``EQUIVALENCE_FILENAME`` 住在 :mod:`app.refdata_prescription`，与它们唯一的加载器同处一个
模块。理由是 ``DATA_DIR`` 这一份仍然是唯一的（那边从本模块 import 它），而「哪个文件在
哪个目录」这件事已经由 ``DATA_DIR`` 回答完了；把两个本模块从不加载的文件名也搬进来，只会
让 ``app/refdata.py`` 承担一份处方侧的知识。
"""
import csv
import pathlib
import types

from app.config import BACKEND_DIR
from app.domain.indicators import AGE_GROUPS, ScoredItem, Sex, segment_thresholds
from app.domain.tables import StandardTable

DATA_DIR = BACKEND_DIR / "data"
STANDARD_FILENAME = "national_standard_2014.csv"
#: 各测量字段的合理区间表（清洗层的越界保护与 ``non_positive_is_missing`` 标记都读它）。
#: 只有文件名住在这里，**加载器是** :func:`app.pipeline.clean.load_ranges`——本模块只负责
#: 国标评分表的解析，不把两种格式各异的参考表混在一个加载器里。
RANGES_FILENAME = "indicator_ranges.yaml"

# 国标 2014 的**单项标准分词表**（0–100 段；加分表 2-3~2-6 不在本仓，见
# ``data/README_national_standard.md`` 的「未纳入本表的内容」）。官方档位是
# 100/95/90/85/80，然后 78→60 每隔 2 分一档，再 50/40/30/20/10，共 **20** 个取值。
#
# **它必须是字面量、不得从 CSV 数出来**（硬规矩 #35：断言两侧不得同源）：
# ``tests/domain/test_indicators.py`` 现有的 ``official = {listed for _, listed in segments}``
# 与 ``_official_scores(...)`` 两处都是从被校验的同一份 CSV 里取词表，故「表里混进一个
# 国标不存在的分（如 65）」在那些测试下**恒等成立**。本常量是这条校验唯一的独立一侧。
OFFICIAL_SCORES: frozenset[int] = frozenset({
    100, 95, 90, 85, 80,
    78, 76, 74, 72, 70, 68, 66, 64, 62, 60,
    50, 40, 30, 20, 10,
})

# 每组档位数下限。2 是「能表达一个方向」的最小值：一档的组让 ``score_item`` 的首末夹取
# 退化成常数、``national_norm`` 的 ``[lo, hi]`` 量程为 0。实测本表最少的一组是
# **8 档**（BMI 的四个组），故这条只是防「整组被删到只剩一行」这类事故的下界。
MIN_SEGMENTS_PER_GROUP = 2

_standard_cache: StandardTable | None = None


def _validate_group(
    csv_path: pathlib.Path, key: tuple[str, str, str], rows: list[tuple[float, int, int]]
) -> None:
    """一组 ``(项, 性别, 年级组)`` 的**表级不变量**校验，违例带 **CSV 行号**响亮失败。

    ``rows`` 每项是 ``(raw_value, score, line_num)``。四条不变量（Ruling 213）：

    1. **档位数 >= :data:`MIN_SEGMENTS_PER_GROUP`**；
    2. **组内 ``raw_value`` 无重复**（排序后严格升序）——两行同 ``raw_value`` 会让
       :func:`~app.domain.indicators.score_item` 的「就低取档」取决于行序，而 CSV 的行序
       按设计是**不承重的**（``load_standard`` 会排序），即同一份数据换一下行序就换答案；
    3. **``score`` 属 :data:`OFFICIAL_SCORES`**——一个国标里不存在的分（65、92）会让系统
       单项分与学校官方体测报表无法逐格对账，而 spec §12 的黄金用例与 §1.3 的可追溯性
       正是要拿真实报表校验的；
    4. **非 BMI 项沿 ``raw_value`` 方向 ``score`` 单调**（不增或不减皆可）。
       ⚠️ **BMI 必须排除**：它是官方「区间 → 得分」的非单调映射（两头 80、中间 100），
       CSV 用 ``0`` 与 ``999`` 两个哨兵把开口区间封成有限档位序列
       （``data/README_national_standard.md`` 的「BMI 是非单调的区间映射」一节），
       得分序列 ``80, 80, 100, 100, 80, 80, 60, 60`` 既不单调不减也不单调不增——
       把 BMI 一起校验会**把正确的表判成错的**。方向单调是
       :func:`~app.domain.indicators._lower_is_better` 与
       :func:`~app.domain.indicators.score_item` 就低取档的前提，也是
       :func:`~app.domain.percentile.national_norm` 端点比较能推方向的前提。

    **为什么校验要住在加载器里而不是只写在测试里**：这张 CSV 是本仓**唯一不可由代码重推**
    的知识资产（其余产物都能由 ``app/seed`` 重新生成），而它由**体育测量学专家手工维护**。
    终审实测 6 次变异里 **4 次 428 条测试全绿**，含「整行删除一档」——原因是
    ``tests/test_refdata.py`` 的档位数断言两侧同源于这一份 CSV（硬规矩 #35）。测试侧的
    指纹与字面档位数是**第二道**闸，本函数是**第一道**：它让坏表在**任何**消费者手上
    都加载不出来，而不是只在跑到那条测试时才红。
    """
    item, sex, age_group = key
    label = f"{item}/{sex}/{age_group}"
    lines = sorted(line for _, _, line in rows)
    if len(rows) < MIN_SEGMENTS_PER_GROUP:
        raise ValueError(
            f"国标评分表 {csv_path} 的 {label} 组只有 {len(rows)} 档"
            f"（第 {lines} 行），少于下限 {MIN_SEGMENTS_PER_GROUP} 档："
            f"一档的组会让 score_item 的首末夹取退化成常数、national_norm 的量程为 0"
        )
    ordered = sorted(rows)
    for (raw_a, _sa, line_a), (raw_b, _sb, line_b) in zip(ordered, ordered[1:]):
        if raw_a == raw_b:
            raise ValueError(
                f"国标评分表 {csv_path} 的 {label} 组里第 {line_a} 行与第 {line_b} 行的 "
                f"raw_value 重复（都是 {raw_a!r}）：同一原始值对应两个档位时，"
                f"score_item 的就低取档结果取决于 CSV 行序，而行序按设计不承重"
            )
    for raw, score, line_no in rows:
        if score not in OFFICIAL_SCORES:
            raise ValueError(
                f"国标评分表 {csv_path} 第 {line_no} 行（{label}, raw_value={raw!r}）的 "
                f"score={score} 不是国标 2014 的官方档位分；合法词表是 "
                f"{sorted(OFFICIAL_SCORES, reverse=True)}（OFFICIAL_SCORES）"
            )
    if item == ScoredItem.BMI.value:
        return
    scores = [score for _, score, _ in ordered]
    non_decreasing = all(b >= a for a, b in zip(scores, scores[1:]))
    non_increasing = all(b <= a for a, b in zip(scores, scores[1:]))
    if not (non_decreasing or non_increasing):
        raise ValueError(
            f"国标评分表 {csv_path} 的 {label} 组沿 raw_value 升序的得分序列非单调："
            f"{scores}（第 {lines} 行）。除 BMI 外的 24 组必须是「越大越好」（不减）或"
            f"「越小越好」（不增）之一——非单调会让 score_item 的就低取档、"
            f"_lower_is_better 的方向推断与 national_norm 的端点比较同时失效。"
            f"若这一组确实是区间型映射（像 BMI），请把它的 item 改成 bmi 而不是放宽本校验"
        )


def load_standard(path: pathlib.Path | None = None) -> StandardTable:
    """读取国标评分表 CSV 并构造不可变的 StandardTable。

    CSV 列为 ``item, sex, age_group, score, raw_value``；同一 (项, 性别, 年级组)
    的行按 raw_value 升序聚成档位序列，所以 CSV 里的行序不影响结果。
    ``path`` 缺省为 ``DATA_DIR / STANDARD_FILENAME``，文件不存在抛 FileNotFoundError。

    三个分组列逐行按枚举校验，不合法即抛 ``ValueError`` 并带上 **CSV 行号与 offending 值**。
    不校验的后果是静默的：一个拼错的 ``item``（如 ``vital_capacty``）会把那一行的档
    从正确的组里悄悄摘走、另立一个孤儿键——该组从 20 档变 19 档，缺掉的那一档会让
    整个区间的查表结果偏移，而任何地方都不报错。

    **整表读完后还要过一遍 :func:`_validate_group` 的表级不变量**（Ruling 213）：
    组内 ``raw_value`` 无重复、每组 ≥ :data:`MIN_SEGMENTS_PER_GROUP` 档、
    ``score ∈`` :data:`OFFICIAL_SCORES`、非 BMI 项沿 ``raw_value`` 方向 ``score`` 单调。
    枚举校验只挡得住「分组列写错」，挡不住「数值写错」或「整行被删」——终审实测
    6 次评分表变异里 **4 次 428 条测试全绿**，含**整行删除一档**。

    ``segments`` 装入 ``MappingProxyType``：``frozen=True`` 只挡住换掉整个字段，挡不住
    ``segments[key] = ...`` 的就地改写，而 ``standard()`` 是进程内共享单例，一次误写
    会让之后所有查表静默变质，spec §1.3 的可追溯性也就没了。底层 dict 是本函数的
    局部变量、不外泄，故这个只读视图是有效的。
    """
    csv_path = DATA_DIR / STANDARD_FILENAME if path is None else pathlib.Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"国标评分表缺失: {csv_path}")
    grouped: dict[tuple[str, str, str], list[tuple[float, int, int]]] = {}
    # utf-8-sig：兼容带 BOM 的 CSV，避免 BOM 混进第一列列名
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            # line_num 是已从源文件读过的行数，比 enumerate 更准（能处理跨行引号字段）
            line_no = reader.line_num
            try:
                item = ScoredItem(row["item"])
            except ValueError:
                raise ValueError(
                    f"国标评分表 {csv_path} 第 {line_no} 行 item 值非法: {row['item']!r}；"
                    f"合法值: {[i.value for i in ScoredItem]}"
                ) from None
            try:
                sex = Sex(row["sex"])
            except ValueError:
                raise ValueError(
                    f"国标评分表 {csv_path} 第 {line_no} 行 sex 值非法: {row['sex']!r}；"
                    f"合法值: {[s.value for s in Sex]}"
                ) from None
            age_group = row["age_group"]
            if age_group not in AGE_GROUPS:
                raise ValueError(
                    f"国标评分表 {csv_path} 第 {line_no} 行 age_group 值非法: {age_group!r}；"
                    f"合法值: {list(AGE_GROUPS)}"
                )
            key = (item.value, sex.value, age_group)
            # 行号随值一起带下去：表级不变量是**跨行**的（重复 raw_value、单调性），
            # 报错时只有带上两端的行号，手工维护这张表的人才定位得到。
            grouped.setdefault(key, []).append(
                (float(row["raw_value"]), int(row["score"]), line_no)
            )
    for key, rows in grouped.items():
        _validate_group(csv_path, key, rows)
    return StandardTable(
        segments=types.MappingProxyType(
            {
                key: tuple((raw, score) for raw, score, _ in sorted(rows))
                for key, rows in grouped.items()
            }
        )
    )



def standard() -> StandardTable:
    """进程内单例：评分表是只读参考数据，一个进程加载一次即可。"""
    global _standard_cache
    if _standard_cache is None:
        _standard_cache = load_standard()
    return _standard_cache


def segment_count(
    table: StandardTable, item: ScoredItem, sex: Sex, age_group: str
) -> int:
    """该 (项, 性别, 年级组) 的档位数，供评分表完整性校验。

    **消费者是 ``tests/test_refdata.py`` 的 ``test_segment_counts_are_pinned_verbatim``**
    （Ruling 213 第 ③ 条）：那条测试把 **28 组**各自的档位数**字面写死**在测试里，
    再经本函数取实际值来比——两侧因此不同源（硬规矩 #35）。本函数此前**全仓零调用者**，
    而同文件 ``test_table_covers_every_item_sex_agegroup`` 的档位数断言两侧都从**被改的
    同一份 CSV** 数，删一行两边同时少一、恒等，这就是终审 M6（整行删除）能 428 全绿的原因。
    """
    return len(segment_thresholds(table, item, sex, age_group))

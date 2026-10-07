# backend/tests/test_refdata_prescription.py
"""动作库两份 YAML 的加载 / 校验 / ``exercise`` 表投影（Plan 02 Task 2）。

本文件是 ``backend/data/exercises.yaml`` 与 ``backend/data/exercise_equivalence.yaml``
的**唯一守卫**，角色与 ``tests/test_refdata.py`` 对国标评分表的角色同构（Ruling 213
的教训照搬）：这两份是体育专家手工维护的知识资产，**改一个值往往不破坏任何形状
不变量**，只有指纹能挡住它。故本文件同时下四道闸（第 4 道是 Task 2 fix round 2 加的，
Plan02 账本 Ruling 107；前三道的口径一个字未改）：

1. **指纹**（:func:`test_exercises_yaml_fingerprint_is_pinned` /
   :func:`test_equivalence_yaml_fingerprint_is_pinned`）——任何字节改动都红；
2. **跨文件不变量**（等价映射只指向存在的动作、**永不升冲击**、每个 ``high`` 都有
   ``low`` 替身）——这三条是 spec §7.4 安全后置的成立前提；
3. **字面钉住的常量**（``volume_reduction`` 的两个系数、RFC 2606 占位符 URL 形状、
   四个无 CHECK 约束列的列宽）——两侧不同源（硬规矩 #35）。
4. **domain 公开面**（``IMPACT_RANK`` 的秩值、``app.domain.prescription.__all__`` 的 7 个
   名字）——同样字面钉住、两侧不同源。⚠️ 这一道**不是**在守 YAML：它守的是 Ruling 96 搬进
   ``app/domain/prescription/`` 那批对象的公开面，寄住在本文件是因为本文件已经是那批对象的
   消费者（``IMPACT_DESCENDING`` 与 ``IMPACT_RANK`` 的两侧不同源就在这里对账）。**Task 3
   建 ``tests/domain/test_prescription_exercises.py`` 时这两条应当搬过去归位**（账本
   Ruling 107-1 已把「``lookup()`` 的分支测试住在 domain 测试目录之外」转成 Task 3 的预检
   项，同一次搬迁即可）。

⚠️ **本文件守不住什么**（硬规矩 #39）：

* **不守「模板 YAML 里的 ``exercise_ref`` 都存在」**——那个测试归 Task 3（Plan02 账本
  P2-C1：原文把它列进本 Task 的变异 ②，而它在本 Task 里根本不存在）。今天删掉一个
  没人引用的 ``exercise_ref``，本文件**只有指纹会红**。
* **不守 ``impact_level`` 与模板 block 里那份副本一致**——同上，归 Task 3 的加载器
  （P2-B2 裁定 ``exercises.yaml`` 是唯一所有者）。
* **不守 ``sync_exercises`` 被谁调用**：本 Task 刻意**不**接进 ``seed_database``
  （P2-A1：那会违反 Global Constraint #10 的 ``app/seed/`` 冻结，并撞上
  ``tests/seed/test_generate.py`` 的「只写组织结构五张表」守卫）。谁在生产路径上灌
  ``exercise`` 表，是 Task 9/10 接管道时的事。
"""
import ast
import hashlib
import pathlib
import re
import types

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import refdata_prescription as rp
from app.db.models.prescription import Exercise
from app.db.session import init_db
from app.domain import prescription as prescription_pkg
from app.domain.indicators import ITEM_BUCKET
from app.domain.prescription import exercises as exercises_mod
from app.domain.prescription.exercises import (
    EquivalenceMapping,
    EquivalenceTable,
    IMPACT_RANK,
    ImpactLevel,
)

# ---------------------------------------------------------------------------
# 期望侧的字面量（一律不从被测 YAML 读回，硬规矩 #35）
# ---------------------------------------------------------------------------

#: ``exercises.yaml`` 的 sha256 前 16 位（大写十六进制），**行尾归一化为 LF 之后**计算。
#: 归一化的理由与 ``tests/test_refdata.py`` 的 ``STANDARD_FINGERPRINT`` 完全相同
#: （Ruling 231）：``core.autocrlf`` 在 Git for Windows 上缺省为 ``true``，裸字节哈希会
#: 随平台配置漂移、新克隆必红。``backend/data/*.yaml`` 已由 ``.gitattributes:14`` 钉成
#: ``eol=lf``，故这里的归一化是**第二道保险**而不是唯一依赖。
EXERCISES_FINGERPRINT = "63033BBD7F68CC1F"

#: ``exercise_equivalence.yaml`` 的同口径指纹。
EQUIVALENCE_FINGERPRINT = "822CB86A5E998301"

#: ``targets`` 的取值域 = ``ITEM_BUCKET`` 的三个桶名（P2-A4）。
#: ⚠️ **不能写成 ``set(ITEM_BUCKET.values())``**：那个集合有 **4** 个元素、含 ``None``
#: （``ITEM_BUCKET[ScoredItem.BMI] is None``，因为 BMI 天然不属于任何短板桶），照字面写
#: 会把 ``None`` 放进取值域、并让一个空 ``targets`` 悄悄合法。下面
#: :func:`test_target_domain_is_the_three_bucket_names_not_the_raw_values` 把这件事钉住。
TARGET_DOMAIN = frozenset(v for v in ITEM_BUCKET.values() if v is not None)

#: 冲击等级的**降序**（高 → 低）。字面写死，不从 ``ImpactLevel`` 派生：枚举继承 ``str``，
#: 它的 ``<`` 是字典序（``"high" < "low" < "medium"``），与冲击序无关，故序关系必须由
#: 消费方显式声明。生产侧那份在 ``app/domain/prescription/exercises.py`` 的
#: ``IMPACT_RANK``（Ruling 96 之前它叫 ``_IMPACT_RANK``、住在
#: ``app/refdata_prescription.py``），两侧刻意不同源（硬规矩 #35）。
#: ⚠️ **改坏哪一侧、红的是哪几条，两侧不同**（fix round 3 实测更正；此前这里把两侧混成一个
#: 主语，声称其中**任何**一侧被改坏都会让
#: :func:`test_equivalence_never_maps_to_a_higher_impact_level` 红——那对生产侧那一份
#: **不成立**）。两次变异都在 ``2df6825`` 的干净工作树上**串行**实跑，各得
#: ``2 failed, 529 passed``：
#:
#: * 改坏**本常量**（反序成 ``("low", "medium", "high")``）→
#:   :func:`test_equivalence_never_maps_to_a_higher_impact_level`（10 条映射全部被判
#:   「升了冲击」）与 :func:`test_impact_rank_values_are_pinned_verbatim` 的支 2 红；
#: * 改坏**生产侧** ``IMPACT_RANK``（``HIGH: 0 ↔ LOW: 2`` 对调）→
#:   :func:`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable` 与
#:   :func:`test_impact_rank_values_are_pinned_verbatim` 的支 1 红，而「不升冲击」那一条
#:   **保持绿**（AST 实测 ``IMPACT_RANK`` 在它函数体里 0 命中，它只读本常量）。
IMPACT_DESCENDING = ("high", "medium", "low")

#: spec §7.4 ``:508-509`` 的两个走等价表的触发条件（``:510`` 的「体脂率异常」走模板
#: ``addons``、**不走等价表**，故 ``when`` 只有这两个取值，Plan02 账本 P2-C3 亲验）。
SPEC_7_4_TRIGGERS = frozenset({"bmi_over_30", "muscle_low_p10"})

#: RFC 2606 保留 TLD ``.invalid`` 保证不可解析，故占位符不会被误当成真链接。
#: 用户已裁定：**不编造真实链接**，真实视频源待 spec §14 登记后由项目组提供。
PLACEHOLDER_PREFIX = "https://example.invalid/exercise/"


def _fingerprint(path: pathlib.Path) -> str:
    """行尾归一化为 LF 之后取 sha256 前 16 位（大写）。口径同 ``tests/test_refdata.py``。"""
    return hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()[:16].upper()


@pytest.fixture
def session():
    """内存库会话。**刻意不用磁盘库**：``backend/pe.db`` 是本 Task 的禁区。"""
    eng = create_engine("sqlite://")
    init_db(eng)
    with Session(eng) as s:
        yield s


def _write_yaml(tmp_path: pathlib.Path, text: str, name: str = "exercises.yaml") -> pathlib.Path:
    """把一段 YAML 字面量按 LF 落到 ``tmp_path``，返回路径。"""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


GOOD_EXERCISE_YAML = """\
interval_run:
  name: 间歇跑
  video_url: https://example.invalid/exercise/interval_run
  impact_level: high
  targets: [endurance]
  equipment: none
bodyweight_resistance:
  name: 自重抗阻
  video_url: https://example.invalid/exercise/bodyweight_resistance
  impact_level: low
  targets: [strength]
  equipment: mat
"""


# ---------------------------------------------------------------------------
# 闸 1：指纹
# ---------------------------------------------------------------------------


def test_exercises_yaml_fingerprint_is_pinned():
    """**改动作库必须先改这条测试**——「知识资产变更需被显式承认」的闸门。

    期望值 :data:`EXERCISES_FINGERPRINT` 是测试里的字面量，实际值现算自磁盘，两侧
    不同源（硬规矩 #35）。红了的正确处置**不是**把新哈希抄进来就算了：先确认这次改动
    是有意的（专家审校 / Task 3 追加 ``exercise_ref``），再更新本常量；若改动同时动了
    ``impact_level``，还要复核
    :func:`test_equivalence_never_maps_to_a_higher_impact_level` 与
    :func:`test_every_high_impact_exercise_has_a_low_substitute` 是否仍然成立。

    ⚠️ Plan 02 Task 3 被**明确允许**往 ``exercises.yaml`` 追加 ``exercise_ref``（简报
    Step 1），届时它必须同步更新本常量并在自己的报告里列出追加了哪些、为什么。
    """
    path = rp.DATA_DIR / rp.EXERCISES_FILENAME
    digest = _fingerprint(path)
    assert digest == EXERCISES_FINGERPRINT, (
        f"动作库被改动了：sha256 前 16 位是 {digest}，钉住的是 {EXERCISES_FINGERPRINT}。"
        f"这份 YAML 是专家维护的知识资产、且是 exercise_ref 与 impact_level 的唯一所有者，"
        f"改动必须被显式承认——确认改动有意之后更新本常量"
    )


def test_equivalence_yaml_fingerprint_is_pinned():
    """等价映射表的同口径指纹。

    **为什么这一份也要指纹**（简报 Step 2 只点了 ``exercises.yaml``，本条是实现者按
    Ruling 213 的教训补的）：把某条映射的 ``to`` 从一个 ``low`` 动作换成**另一个**
    ``low`` 动作，不破坏下面任何一条形状不变量——目标仍存在、仍不升冲击、``high`` 仍
    有 ``low`` 替身、``version`` 仍非空——**六条语义测试会全绿**。这与终审 M4（改评分表
    一处 ``raw_value``、全仓只有指纹红）是同一个失效形态。
    """
    path = rp.DATA_DIR / rp.EQUIVALENCE_FILENAME
    digest = _fingerprint(path)
    assert digest == EQUIVALENCE_FINGERPRINT, (
        f"等价映射表被改动了：sha256 前 16 位是 {digest}，钉住的是 {EQUIVALENCE_FINGERPRINT}。"
        f"这份表驱动 spec §7.4 的安全替换，且它的 version 会被写进 "
        f"prescription.safety_substitutions——改动必须被显式承认，并考虑是否要升 version"
    )


# ---------------------------------------------------------------------------
# 闸 2：取值域与跨文件不变量
# ---------------------------------------------------------------------------


def test_target_domain_is_the_three_bucket_names_not_the_raw_values():
    """:data:`TARGET_DOMAIN` 的构造方式本身要被钉住（P2-A4）。

    这条守的是**守卫自己的口径**：``set(ITEM_BUCKET.values())`` 与
    ``frozenset(v for v in ITEM_BUCKET.values() if v is not None)`` 差一个 ``None``，
    而差这一个 ``None`` 的后果是「空 ``targets`` 悄悄合法」——因为校验写法通常是
    ``set(targets) <= DOMAIN``，``None`` 在不在 ``DOMAIN`` 里对**非空** ``targets`` 毫无
    影响，只有「一个动作不瞄准任何素质桶」这种真正该拒绝的输入才暴露差别。
    """
    raw_values = set(ITEM_BUCKET.values())
    assert len(raw_values) == 4, sorted(repr(v) for v in raw_values)
    # fix round 3 更正：这句此前引的是 Plan01 账本里**另一条**裁定（那条讲的是
    # 「``raw_from_score`` 对非单调序列抛 ``ValueError``，不得返回哨兵」），即**引用号错**；
    # 本行刻意不复述那个错号，免得它被下一次 grep 当成一处有效引用。
    # 「BMI 不归任何短板桶」的出处是 **spec §4.2**（BMI 那一行的「短板判定项」格是「否」、
    # 备注格是「不入桶」；同节说明逐字写着「**短板判定项 = 6 个**（**排除 BMI**）」），
    # Plan01 账本 Ruling 17 的关切 1 据此裁定「BMI 按 spec §4.2 不参与短板判定与桶化」。
    assert None in raw_values, "BMI 不归桶（spec §4.2：短板判定项 = 6 个，排除 BMI），故 None 必在其中"
    assert TARGET_DOMAIN == {"endurance", "strength", "speed_flexibility"}
    assert None not in TARGET_DOMAIN


def test_every_exercise_has_a_valid_impact_level_and_targets():
    """每个动作的 ``impact_level`` 与 ``targets`` 都落在**代码侧**的取值域里。

    两侧不同源：期望侧来自 :class:`ImpactLevel`（domain 枚举）与 ``ITEM_BUCKET``
    （Plan 01 的桶化口径），实际侧来自 ``exercises.yaml``。先断言期望侧等于 spec §4.4
    与 §6.1 的字面词表，免得「枚举本身被改坏」时两侧一起漂（硬规矩 #35）。
    """
    assert {level.value for level in ImpactLevel} == {"high", "medium", "low"}
    assert TARGET_DOMAIN == {"endurance", "strength", "speed_flexibility"}

    library = rp.load_exercises()
    assert library, "动作库为空：Task 3 的 18 套模板将无 ref 可引"
    offenders = []
    for ref, spec in library.items():
        if spec.impact_level not in set(ImpactLevel):
            offenders.append(f"{ref}.impact_level={spec.impact_level!r}")
        if not spec.targets:
            offenders.append(f"{ref}.targets 为空：一个不瞄准任何素质桶的动作无法被模板选用")
        unknown = spec.targets - TARGET_DOMAIN
        if unknown:
            offenders.append(f"{ref}.targets 含非桶名 {sorted(unknown)}")
        if spec.impact_level.value not in IMPACT_DESCENDING:
            offenders.append(f"{ref}.impact_level={spec.impact_level.value!r} 不在冲击序里")
    assert offenders == [], "\n".join(offenders)


def test_exercise_refs_are_snake_case_and_unique_keys():
    """``ref`` 的形状与唯一性。

    唯一性由 YAML 的映射语义保证吗？**不保证**：PyYAML 的 ``safe_load`` 对重复键是
    **后者覆盖前者、不报错**（实测 ``yaml.safe_load("a: 1\\na: 2") == {"a": 2}``）。
    于是「专家复制一段忘了改 ref」会让一个动作**静默消失**——它从键集里被顶掉，
    而 Task 3 的模板若引用了它就会在加载时炸（那还是好的），若没引用就无人发现。
    本条用**原始文本**数一遍顶层键出现次数，与解析后的键集对账，两侧不同源。
    """
    path = rp.DATA_DIR / rp.EXERCISES_FILENAME
    text = path.read_text(encoding="utf-8")
    library = rp.load_exercises()

    top_level_keys = [
        line.split(":", 1)[0] for line in text.splitlines()
        if line and not line[0].isspace() and not line.lstrip().startswith("#")
        and ":" in line
    ]
    assert len(top_level_keys) == len(set(top_level_keys)), (
        "exercises.yaml 有重复的顶层键，PyYAML 会静默用后者覆盖前者："
        f"{sorted(k for k in top_level_keys if top_level_keys.count(k) > 1)}"
    )
    assert set(top_level_keys) == set(library), (
        f"解析出的键集与文本里的顶层键不符：文本多 "
        f"{sorted(set(top_level_keys) - set(library))}、少 "
        f"{sorted(set(library) - set(top_level_keys))}"
    )
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", ref) for ref in library), sorted(
        ref for ref in library if not re.fullmatch(r"[a-z][a-z0-9_]*", ref)
    )


def test_video_urls_are_rfc2606_placeholders_keyed_by_ref():
    """视频 URL 一律是 ``https://example.invalid/exercise/<ref>`` 形状的占位符。

    用户已裁定「**不编造真实链接**」：``.invalid`` 是 RFC 2606 保留 TLD，DNS 保证不可
    解析，故占位符不可能被误当成一个真能打开的视频源，也不会指向某个恰好注册了的
    域名。spec §7.3 ``:499`` 的装配第 5 步会把这个 URL 填进训练包的二维码，所以它的
    「假」必须是**响亮可识别**的假。

    ⚠️ 项目组提供真实视频源时**本条会变红，那是设计意图**：换 URL 是一次需要被显式
    承认的知识资产变更（同指纹那两条的处置口径），届时要连带更新本条与指纹常量。
    """
    library = rp.load_exercises()
    offenders = [
        f"{ref}: {spec.video_url!r}"
        for ref, spec in library.items()
        if spec.video_url != f"{PLACEHOLDER_PREFIX}{ref}"
    ]
    assert offenders == [], "视频 URL 不是约定的占位符形状：\n" + "\n".join(offenders)


def test_equivalence_table_only_maps_to_existing_exercises():
    """等价映射的两端都必须在动作库里。

    失效形态是实打实的：``to`` 指向一个不存在的 ref 时，spec §7.4 的安全替换会产出一个
    **装配不出来的动作**——Task 7 拿它去查动作库得 ``None``，于是要么当场 ``KeyError``
    （好在装配到某个学生时才炸，而不是在专家改 YAML 时炸），要么被写成一次静默跳过，
    而那正是 spec §7.4 ``:514`` 明令禁止的。``from`` 指向不存在的 ref 则更隐蔽：那条
    映射永远匹配不上，等于**该动作没有低冲击替身**，BMI > 30 的学生照旧被安排它。
    """
    library = rp.load_exercises()
    table = rp.load_equivalence()
    offenders = [
        f"{m.from_ref} -> {m.to_ref}（{'from' if m.from_ref not in library else ''}"
        f"{'/' if m.from_ref not in library and m.to_ref not in library else ''}"
        f"{'to' if m.to_ref not in library else ''} 不在动作库）"
        for m in table.mappings
        if m.from_ref not in library or m.to_ref not in library
    ]
    assert offenders == [], "等价映射指向动作库里不存在的 ref：\n" + "\n".join(offenders)


def test_equivalence_never_maps_to_a_higher_impact_level():
    """**安全属性的核心**：等价替换只能持平或降低冲击，绝不上升。

    序关系 ``high > medium > low`` **字面写死**在 :data:`IMPACT_DESCENDING` 里，不从
    ``ImpactLevel`` 派生（它继承 ``str``，字典序是 ``high < low < medium``，与冲击序
    完全无关）。生产侧 ``app/domain/prescription/exercises.py`` 的 ``IMPACT_RANK`` 是
    同一序的第二份、供 :meth:`EquivalenceTable.lookup` 使用；两份刻意不同源（硬规矩 #35）。
    ⚠️ **本条只看得到测试侧那一份**（fix round 3 实测更正：此前这里声称两份里的任何一份
    被改坏本条都会红，**不成立**）——AST 实测 ``IMPACT_RANK`` 在本函数体里 **0 命中**，秩取自
    :data:`IMPACT_DESCENDING`（``rank = {value: index for index, value in
    enumerate(IMPACT_DESCENDING)}``）。变异实跑（``2df6825`` 干净工作树，串行）：反序
    :data:`IMPACT_DESCENDING` → **本条红**（10 条映射全部被判「升了冲击」）；对调生产侧
    ``IMPACT_RANK`` 的 ``HIGH: 0 ↔ LOW: 2`` → **本条保持绿**，红的是
    :func:`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable` 与
    :func:`test_impact_rank_values_are_pinned_verbatim`（两次都是 ``2 failed, 529
    passed``）。即「生产侧的秩被改坏」这件事由那两条看着，本条守的是**数据**（映射表里
    有没有升冲击的行、以及每条声明的 ``max_impact`` 与真实冲击是否一致）。

    这条为什么是核心：spec §7.4 的两个触发（BMI > 30 / 肌肉量 < P10）本身就是**关节
    负荷过高**的医学指征，一次「换成更高冲击」的替换会把安全后置处理器变成伤害放大器，
    而它披着「已按映射表处理过」的外衣，教师端看不出异常。
    """
    library = rp.load_exercises()
    table = rp.load_equivalence()
    rank = {value: index for index, value in enumerate(IMPACT_DESCENDING)}

    offenders = []
    for mapping in table.mappings:
        source = library[mapping.from_ref].impact_level.value
        target = library[mapping.to_ref].impact_level.value
        if rank[target] < rank[source]:
            offenders.append(
                f"{mapping.from_ref}({source}) -> {mapping.to_ref}({target}) 升了冲击"
            )
        # 映射自己声明的 max_impact 必须与 to 的真实冲击一致：不一致意味着这张表在
        # 撒谎，而 lookup 正是按 max_impact 过滤的（它不看动作库）。
        if mapping.max_impact.value != target:
            offenders.append(
                f"{mapping.from_ref} -> {mapping.to_ref} 声明 max_impact="
                f"{mapping.max_impact.value}，而 {mapping.to_ref} 的真实冲击是 {target}"
            )
    assert offenders == [], "\n".join(offenders)


def test_equivalence_table_has_a_version():
    """``version`` 必须是非空字符串。

    spec §7.4 ``:512`` 要求每次替换把「原动作、新动作、触发条件、**映射表版本号**」写进
    ``prescription.safety_substitutions``。没有版本号，一张已生成的处方就无法回答
    「当时是按哪一版映射表替换的」——而这份表由专家维护、会改，可追溯性（spec §1.3）
    正依赖这个字段。空串也要拒：它能通过 ``is not None``，写进 JSON 后却什么都说明不了。
    """
    table = rp.load_equivalence()
    assert isinstance(table.version, str)
    assert table.version.strip() != "", "version 为空：safety_substitutions 将记不下映射表版本"
    # 字面钉住当前版本，升版必须是一次显式改动
    assert table.version == "1.0"


def test_every_high_impact_exercise_has_a_low_substitute():
    """**每个** ``high`` 动作都必须有一个 ``low`` 等价物，且两个触发条件各有一个。

    ⚠️ 测试名按**描述**改过（Plan02 账本 P2-C2：原文叫
    ``test_every_impact_level_has_at_least_one_low_substitute``，名字说「每个 impact
    level」而描述只要求 ``high``）。要求 ``medium`` 也备一个 ``low`` 替身是**过紧的
    守卫**：spec §7.4 ``:508-509`` 的两个触发都只替换 ``impact_level: high`` 的动作，
    给永不发生的场景写断言正是硬规矩 #50 的反面，而它的代价是真的——为了喂饱这条断言
    就得往 ``exercise_equivalence.yaml`` 塞一堆永不被查到的映射，把一张专家审校表变成
    噪声。

    反过来这条**必须**存在：一个 ``high`` 动作没有 ``low`` 替身时，BMI > 30 的安全规则
    会命中但无解，直接落进 Review Focus 第 5 条的 ``needs_review`` 路径。那条路径本身是
    对的（spec §7.4 ``:514``「宁可不自动，也不要自动错」），但**因为动作库缺条目**而
    天天触发它，等于把可自动处理的学生全推给人工复核。
    """
    library = rp.load_exercises()
    table = rp.load_equivalence()

    substitutes: dict[str, dict[str, str]] = {}
    for mapping in table.mappings:
        substitutes.setdefault(mapping.from_ref, {})[mapping.when] = mapping.to_ref

    offenders = []
    high_refs = sorted(
        ref for ref, spec in library.items() if spec.impact_level is ImpactLevel.HIGH
    )
    assert high_refs, "动作库里没有任何 high 冲击动作：本条将空转全绿"
    for ref in high_refs:
        by_trigger = substitutes.get(ref, {})
        for trigger in sorted(SPEC_7_4_TRIGGERS):
            target = by_trigger.get(trigger)
            if target is None:
                offenders.append(f"{ref}（high）缺 when={trigger} 的等价物")
            elif library[target].impact_level is not ImpactLevel.LOW:
                offenders.append(
                    f"{ref}（high）在 when={trigger} 下映射到 {target}，"
                    f"而它的冲击是 {library[target].impact_level.value}、不是 low"
                )
    assert offenders == [], "\n".join(offenders)


def test_equivalence_when_values_are_exactly_the_two_spec_7_4_triggers():
    """``when`` 的取值域恰好是 spec §7.4 走等价表的那两个触发。

    spec §7.4 ``:510`` 的第三个触发（体脂率异常）走的是「追加模板 ``addons`` 中的能量
    消耗模块」，**不查等价表**（Plan02 账本 P2-C3 亲验）。故 ``when`` 出现第三个取值
    就意味着有人在等价表里实现了一个不属于它的机制，而 Task 7 的消费端永远不会传它
    ——那条映射是死代码，且它占的位置会让人以为第三个触发也被覆盖了。
    """
    table = rp.load_equivalence()
    observed = {mapping.when for mapping in table.mappings}
    assert observed == SPEC_7_4_TRIGGERS, (
        f"when 的取值域应为 {sorted(SPEC_7_4_TRIGGERS)}，实到 {sorted(observed)}"
    )
    assert set(table.volume_reduction) == SPEC_7_4_TRIGGERS, (
        f"volume_reduction 的键应恰好是两个触发，实到 {sorted(table.volume_reduction)}"
    )


def test_volume_reduction_coefficients_are_pinned_verbatim():
    """两个跑量下调系数**字面钉住**（Plan02 Ruling 7）。

    ⚠️ **这两个数在 spec 里没有出处**（Plan02 账本 P2-A3）：spec §7.4 ``:508`` 只写
    「跑量**按映射表下调**」、没给任何数，``:509``（肌肉量 < P10）写「同上」。spec 里
    唯一出现的「系数 0.8」在 ``:604``，那是**预警触发的减量 20%**
    （``weekly_adjustment(系数 0.8, 原因 RED_RPE_SUSTAINED)``，属 Plan 03），与 §7.4 的
    安全后置跑量下调是**两个不同机制**；``0.9`` 在 spec 里根本没有对应物。故本条期望侧
    是「**本设计的默认规定**」，已登记进 spec §14 第 28 项与 YAML 注释；Task 7 消费时
    **不得把它们当成 spec 条文引用**。

    系数为什么必须 < 1 且 > 0：> 1 是「安全触发反而加量」，<= 0 是把训练量清零、
    处方名存实亡。这两条也在这里一并钉住，免得有人把 0.8 改成 8。
    """
    table = rp.load_equivalence()
    assert table.volume_reduction["bmi_over_30"] == 0.8
    assert table.volume_reduction["muscle_low_p10"] == 0.9
    for trigger, factor in table.volume_reduction.items():
        assert isinstance(factor, float), f"{trigger} 的系数应是 float，实为 {type(factor)}"
        assert 0.0 < factor < 1.0, f"{trigger} 的系数 {factor} 不在 (0, 1) 内"


def test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable():
    """:meth:`EquivalenceTable.lookup` 的三条语义，各带一个「应当红」与「应当绿」的输入。

    硬规矩 #50：设计守卫必须同时构造两种输入并都跑。这里
    ``ImpactLevel.LOW`` 与 ``ImpactLevel.MEDIUM`` 两个上限对**同一张合成表**给出不同
    答案，才证明 ``impact_ceiling`` 这个参数真的被用上了（否则它可以被删掉而全部测试
    仍然绿）。合成表是必要的：真实的 ``exercise_equivalence.yaml`` 里每条映射的
    ``max_impact`` 都是 ``low``，用它无法区分「上限被尊重」与「上限被忽略」。
    """
    table = rp.load_equivalence()
    # 真表：high 动作在三个上限下都能查到替身（low <= 任何上限）
    assert table.lookup("interval_run", ImpactLevel.LOW) == "stationary_cycling"
    assert table.lookup("interval_run", ImpactLevel.MEDIUM) == "stationary_cycling"
    assert table.lookup("interval_run", ImpactLevel.HIGH) == "stationary_cycling"
    # 真表：没有映射的 ref → None（Task 7 据此走 needs_review，spec §7.4:514）
    assert table.lookup("challenge_task", ImpactLevel.LOW) is None
    assert table.lookup("__不存在的 ref__", ImpactLevel.LOW) is None

    # 合成表：max_impact=medium 的映射在 LOW 上限下**必须查不到**
    synthetic = EquivalenceTable(
        version="synthetic",
        mappings=(
            EquivalenceMapping(
                from_ref="a", to_ref="b",
                max_impact=ImpactLevel.MEDIUM, when="bmi_over_30",
            ),
        ),
        volume_reduction={},
    )
    assert synthetic.lookup("a", ImpactLevel.MEDIUM) == "b"
    assert synthetic.lookup("a", ImpactLevel.HIGH) == "b"
    assert synthetic.lookup("a", ImpactLevel.LOW) is None


def test_impact_rank_values_are_pinned_verbatim():
    """:data:`IMPACT_RANK` 的**秩值本身**被字面钉住（Plan02 账本 Ruling 107-2）。

    ``IMPACT_RANK`` 自 Ruling 96 起是 domain 的**公开面**（``from app.domain.prescription
    import IMPACT_RANK`` 可用），而 :meth:`EquivalenceTable.lookup` 的全部判据就是
    ``IMPACT_RANK[mapping.max_impact] >= IMPACT_RANK[impact_ceiling]``。**秩值整体对调会把
    「安全替换」变成「升冲击替换」**：spec §7.4 的两个触发（BMI > 30 / 肌肉量 < P10）本身
    就是关节负荷过高的医学指征，而换出来的动作披着「已按映射表处理过」的外衣，教师端看不出
    异常——与 :func:`test_equivalence_never_maps_to_a_higher_impact_level` 防的是同一件事，
    只是那一条从**数据**侧查（映射表里有没有升冲击的行）、本条从**序本身**查。

    今天看着它的本来只有两条**间接**守卫：上面那条（用测试侧字面的 :data:`IMPACT_DESCENDING`）
    与 :func:`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable`
    （用合成表的三个上限）。fix round 1 的变异 M-B（``HIGH: 0 ↔ LOW: 2`` 对调）实测只让
    **其中 1 条**红（账本 Ruling 108），而且红的不是「秩值被改了」这件事本身。本条把它变成
    **直接**的红：秩值一改，支 1 就开火。

    **期望侧字面写死**（硬规矩 #35）：``0`` / ``1`` / ``2`` 三个整数是抄进本测试的，
    **不从 ``ImpactLevel`` 派生**（它继承 ``str``，``sorted(ImpactLevel)`` 给的是字典序
    ``high < low < medium``，与冲击序无关），也**不从 ``IMPACT_RANK`` 自己读回来跟自己比**
    （那样两侧同源，秩值整体对调也恒等成立）。

    **红/绿双输入**（硬规矩 #50）：绿输入 = 今天的真值（支 1、支 2、支 3 都实跑通过）；
    红输入 = Task 7 的安全后置会撞上的**反方向**（支 4：拿 high 的替身去顶 low 的上限，
    必须判「不可以」）。只有支 3 的话，把三个秩值改成同一个数也能全绿。改生产码的真变异
    本轮实跑过两个（逐支真值见报告 §fr2.4）：**M-A1** = ``HIGH: 0 ↔ LOW: 2`` 对调 →
    **四支全部不成立**、``2 failed, 529 passed``（另一条红的是
    :func:`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable`；
    fix round 1 的同一个变异只有 ``1 failed``，故**本条正是新增的那一条红**）。
    **M-A2** = 三个秩值全改成 ``0``（序被抹平）→ **支 2 与支 3 仍是绿的**，只有支 1 与
    支 4 不成立、``2 failed, 529 passed``。这就是支 4 存在的理由：序被抹平时正方向那一支
    抓不到东西。

    **四支的主语**（硬规矩 #56）：支 1 = 整个字典的字面值；支 2 = 按秩排出来的成员序与
    测试侧那份**独立**的降序元组 :data:`IMPACT_DESCENDING` 交叉（两侧不同源）；
    支 3 = 正方向可替换；支 4 = 反方向不可替换。

    **本条守不住什么**（硬规矩 #39）：它钉**秩值**，不钉「``lookup`` 用 ``>=`` 而不是
    ``>``」——那一支由上面那条 lookup 测试看着（fix round 1 的变异 M-A 打的是它）。故
    M-A 与本条的变异打的是**不同断言分支**（硬规矩 #65）。它也没有独立的一支钉「键集恰好
    等于 ``ImpactLevel`` 的成员集」：那件事由支 1 的字面字典顺带钉住（少一个键或多一个键
    都会让 ``==`` 不成立）。
    """
    # 支 1：整个字典的字面值（键是枚举成员、值是字面整数）
    assert IMPACT_RANK == {
        ImpactLevel.HIGH: 0,
        ImpactLevel.MEDIUM: 1,
        ImpactLevel.LOW: 2,
    }
    # 支 2：按秩升序排出来的成员序，必须等于测试侧独立声明的降序元组
    descending = [level.value for level in sorted(IMPACT_RANK, key=IMPACT_RANK.__getitem__)]
    assert descending == list(IMPACT_DESCENDING)
    # 支 3（绿输入）：秩越大冲击越低，故 low 的替身可以顶 high 的上限
    assert IMPACT_RANK[ImpactLevel.LOW] >= IMPACT_RANK[ImpactLevel.HIGH]
    # 支 4（红输入）：反过来必须不成立，否则「升冲击替换」会被判成合法
    assert not IMPACT_RANK[ImpactLevel.HIGH] >= IMPACT_RANK[ImpactLevel.LOW]


# ---------------------------------------------------------------------------
# 闸 3：ORM 侧（列宽 / 约束 / 投影）
# ---------------------------------------------------------------------------


def test_exercise_string_column_widths_fit_the_yaml_values():
    """四个**没有** ``_in_domain`` CHECK 的列，列宽必须容得下 YAML 里的实际最长值。

    ⚠️ **Plan02 账本 P2-A5**：``tests/db/test_models.py`` 的
    ``test_string_column_widths_fit_their_value_domains`` 是**自描述**的（从
    ``_in_domain`` 生成的 ``column IN (...)`` CHECK 文本反解取值域），故它**只看得见
    带 CHECK 的列**。``Exercise`` 的 5 个 ``String(n)`` 列里只有 ``impact_level`` 有
    CHECK，``ref`` / ``name`` / ``video_url`` / ``equipment`` 的取值域不是封闭集合、
    **完全不被那道测试覆盖**，只能在这里另写。

    两侧不同源：期望侧是 ORM 声明的 ``.type.length``，实际侧从 ``exercises.yaml`` 现读。
    SQLite **不强制** ``VARCHAR`` 长度，故溢出在本仓的测试里永远不报错——Ruling 144 的
    ``derived_metrics.trend String(16)`` 就是这样漏了 7 个任务（``"insufficient_data"``
    是 17 字符），换 MySQL / PostgreSQL 会截断，且**炸在读侧不在写侧**。
    """
    library = rp.load_exercises()
    longest = {
        "ref": max((spec.ref for spec in library.values()), key=len),
        "name": max((spec.name for spec in library.values()), key=len),
        "video_url": max((spec.video_url for spec in library.values()), key=len),
        "equipment": max((spec.equipment for spec in library.values()), key=len),
    }
    offenders = []
    for column_name, value in sorted(longest.items()):
        width = Exercise.__table__.c[column_name].type.length
        if width is None or width < len(value):
            offenders.append(
                f"exercise.{column_name} 声明 String({width})，"
                f"YAML 里最长的却是 {value!r}（{len(value)} 字符）"
            )
    assert offenders == [], "列宽容不下取值域（严格长度的后端会静默截断）：\n" + "\n".join(offenders)
    # 守卫自己也得有牙：四个列都真的被量到了，不是一个空循环
    assert len(longest) == 4, sorted(longest)


def test_exercise_impact_level_vocabulary_agrees_with_the_domain_enum():
    """ORM 的类常量与 domain 枚举是同一个词表（Global Constraint #3 的漂移测试）。

    ``Exercise.IMPACT_LEVELS`` 是 SQL CHECK 约束的**唯一真相**（约束文本由
    :func:`app.db.models._in_domain` 从它生成，见 ``app/db/models/__init__.py`` 的
    约定 2），:class:`ImpactLevel` 是 Python 侧的唯一真相。两份必须逐字相同，否则
    一侧放行、另一侧拒收，而失效发生在离真因一整个批处理周期之外的读侧。
    """
    assert Exercise.IMPACT_LEVELS == {level.value for level in ImpactLevel}
    assert Exercise.IMPACT_LEVELS == {"high", "medium", "low"}


def test_exercise_ref_is_unique_at_the_db_level(session):
    """``exercise.ref`` 唯一：它是 ``sync_exercises`` 的幂等键，也是模板引用的目标。

    没有这条约束，一次「upsert 的查询没命中」就会插出第二行同 ref 的动作，而
    ``select(Exercise).where(ref == ...)`` 随后返回哪一行取决于行序——训练包里的视频
    二维码因此可能在两次装配之间换掉，且没有任何一处报错。
    """
    session.add(Exercise(ref="interval_run", name="间歇跑",
                         video_url="https://example.invalid/exercise/interval_run",
                         impact_level="high", targets=["endurance"], equipment="none"))
    session.flush()
    session.add(Exercise(ref="interval_run", name="间歇跑（重复）",
                         video_url="https://example.invalid/exercise/interval_run",
                         impact_level="high", targets=["endurance"], equipment="none"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_exercise_impact_level_check_rejects_unknown_value(session):
    """SQL 层的 CHECK 真的在拦：``impact_level`` 写 ``"very_high"`` 必须 ``IntegrityError``。

    这条与 :func:`test_exercise_impact_level_vocabulary_agrees_with_the_domain_enum`
    分工不同（fix round 3 更正：此前这里漏了 ``exercise_`` 前缀，于是这个 ``:func:`` 交叉
    引用指向一个全仓不存在的名字——改前 ``git grep`` 那个短名在 ``backend/`` 下只有本行
    1 处命中。真名在本文件里由 ``def`` 行给出，且 ``app/db/models/prescription.py`` 引的
    一直是**正确**的全名）：
    那条比的是**两份词表一致**，这条验的是**约束真的被建进 DDL 并生效**。少一条就会漏：
    词表一致但 ``__table_args__`` 忘了挂 ``_in_domain``，Python 侧全绿而数据库照收脏值。
    """
    session.add(Exercise(ref="probe", name="探针",
                         video_url="https://example.invalid/exercise/probe",
                         impact_level="very_high", targets=["endurance"], equipment="none"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_sync_exercises_projects_every_ref_and_is_idempotent(session):
    """``sync_exercises`` 把 YAML 投影成 ``exercise`` 行，重跑不翻倍、返回行数恒定。

    **只在内存库会话里验**（Plan02 账本 D3）：``backend/pe.db`` 与 ``backend/data/seed/``
    是本 Task 的禁区，故这里绝不跑 ``python -m app.seed.generate`` 一类的 CLI。
    """
    library = rp.load_exercises()
    written = rp.sync_exercises(session)
    session.commit()
    assert written == len(library)
    # **下界**而不是 ``== 23``：条目数的精确值已经由
    # :func:`test_exercises_yaml_fingerprint_is_pinned` 钉住（少一个条目哈希就变），再钉一次
    # 等于给 Task 3 增加一个必须同步更新的常量——而简报 Step 1 明确允许 Task 3 往
    # ``exercises.yaml`` **追加** ``exercise_ref``，且只要求它更新指纹常量。20 这个下界取自
    # 计划 Task 2 的「预估 20–30 个」，它抓的是「动作库被截断成几条」这类事故，
    # 不抓「加了一个动作」。
    assert written >= 20, f"动作库只剩 {written} 条，低于计划预估的 20–30 的下界"

    rows = session.execute(select(Exercise)).scalars().all()
    assert len(rows) == written
    assert {row.ref for row in rows} == set(library)

    # 逐列对账：DB 行必须与 YAML 的投影逐字段相同（targets 落库为排序后的 list，
    # 因为 frozenset 不能直接 JSON 序列化，且排序让落库字节与遍历序无关）
    for row in rows:
        spec = library[row.ref]
        assert row.name == spec.name
        assert row.video_url == spec.video_url
        assert row.impact_level == spec.impact_level.value
        assert row.targets == sorted(spec.targets)
        assert row.equipment == spec.equipment

    # 幂等：重跑一次，行数与返回值都不变
    assert rp.sync_exercises(session) == written
    session.commit()
    assert session.scalar(select(func.count()).select_from(Exercise)) == written


def test_sync_exercises_updates_a_changed_field_in_place(session):
    """YAML 改了值，重跑必须**更新**那一行而不是插第二行（upsert 的 PATCH 语义）。

    这一条与上一条不重复：上一条验的是「同样的输入跑两次」，这条验的是「输入变了」。
    失效形态是 ``exercise`` 表随每次改 YAML 而膨胀，且旧行还在——模板按 ref 查时
    命中哪一行取决于行序。
    """
    rp.sync_exercises(session)
    session.commit()
    before = session.scalar(select(func.count()).select_from(Exercise))

    session.execute(
        Exercise.__table__.update()
        .where(Exercise.__table__.c.ref == "interval_run")
        .values(name="被改坏的名字")
    )
    session.commit()
    assert rp.sync_exercises(session) == before
    session.commit()
    assert session.scalar(select(func.count()).select_from(Exercise)) == before
    row = session.scalar(select(Exercise).where(Exercise.ref == "interval_run"))
    assert row.name == rp.load_exercises()["interval_run"].name == "间歇跑"


# ---------------------------------------------------------------------------
# 加载器的响亮失败（Review Focus 第 1 条的同构要求，作用于动作库这一侧）
# ---------------------------------------------------------------------------


def test_load_exercises_is_read_only_and_cached():
    """``load_exercises()`` 返回只读视图；``exercises()`` 是进程内单例。

    形状照 ``app/refdata.py`` 的 ``load_standard()`` + ``standard()`` **这一对**
    （Plan02 账本 P2-A9：``load_standard`` 只加载不缓存，单例是另一个函数）。
    只读是承重的：``exercises()`` 被全进程共享，一次 ``library["x"] = ...`` 的就地改写
    会让之后所有装配静默变质，而 ``frozen=True`` 只挡「换掉整个字段」、挡不住这个。
    """
    first = rp.exercises()
    assert first is rp.exercises(), "exercises() 不是单例：每次调用都重读磁盘"
    assert isinstance(first, types.MappingProxyType), type(first)
    assert rp.load_exercises() is not rp.load_exercises(), (
        "load_exercises() 不该缓存：它与 load_standard() 同口径，缓存是 exercises() 的职责"
    )
    with pytest.raises(TypeError):
        first["interval_run"] = None  # type: ignore[index]
    assert rp.equivalence() is rp.equivalence()


def test_load_exercises_reports_the_file_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="动作库"):
        rp.load_exercises(tmp_path / "nope.yaml")


def test_load_equivalence_reports_the_file_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="等价映射表"):
        rp.load_equivalence(tmp_path / "nope.yaml")


@pytest.mark.parametrize(
    "mutant, needle",
    [
        ("", "为空"),
        ("[]\n", "顶层结构"),
        ("interval_run:\n  name: 间歇跑\n  video_url: https://example.invalid/exercise/interval_run\n"
         "  impact_level: very_high\n  targets: [endurance]\n  equipment: none\n", "impact_level"),
        ("interval_run:\n  name: 间歇跑\n  video_url: https://example.invalid/exercise/interval_run\n"
         "  impact_level: high\n  targets: []\n  equipment: none\n", "targets"),
        # ``bmi`` 是 ScoredItem 而不是桶名（ITEM_BUCKET[BMI] is None），照字面写
        # set(ITEM_BUCKET.values()) 会把 None 放进取值域、让这一条悄悄合法（P2-A4）
        ("interval_run:\n  name: 间歇跑\n  video_url: https://example.invalid/exercise/interval_run\n"
         "  impact_level: high\n  targets: [bmi]\n  equipment: none\n", "targets"),
        ("interval_run:\n  name: 间歇跑\n  video_url: https://example.invalid/exercise/interval_run\n"
         "  impact_level: high\n  targets: [endurance]\n", "equipment"),
        ("interval_run:\n  name: 间歇跑\n  video_url: https://example.invalid/exercise/interval_run\n"
         "  impact_level: high\n  targets: [endurance]\n  equipment: none\n  coach: 张老师\n", "coach"),
        ("Interval_Run:\n  name: 间歇跑\n  video_url: https://example.invalid/exercise/x\n"
         "  impact_level: high\n  targets: [endurance]\n  equipment: none\n", "ref"),
        ("interval_run:\n  name: 间歇跑\n  video_url: ''\n"
         "  impact_level: high\n  targets: [endurance]\n  equipment: none\n", "video_url"),
    ],
)
def test_load_exercises_rejects_a_malformed_library(tmp_path, mutant, needle):
    """坏 YAML 必须在**加载时**响亮失败，并点名是哪个文件、哪个 ref、哪个字段。

    不校验的后果是静默的：一个拼错的 ``impact_level`` 会让该动作**永远不被** spec §7.4
    的安全后置识别成 high，BMI > 30 的学生照旧被安排它，而全链路没有一处报错。
    """
    path = _write_yaml(tmp_path, mutant)
    with pytest.raises(ValueError) as excinfo:
        rp.load_exercises(path)
    message = str(excinfo.value)
    assert needle in message, message
    assert path.name in message, f"报错没点名文件：{message}"


@pytest.mark.parametrize(
    "mutant, needle",
    [
        ("mappings: []\nvolume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n", "version"),
        ("version: ''\nmappings: []\n"
         "volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n", "version"),
        ("version: '1.0'\nvolume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n", "mappings"),
        ("version: '1.0'\nmappings: []\n", "volume_reduction"),
        ("version: '1.0'\nmappings: []\nvolume_reduction: {bmi_over_30: 0.8}\n", "volume_reduction"),
        ("version: '1.0'\nmappings: []\n"
         "volume_reduction: {bmi_over_30: 1.8, muscle_low_p10: 0.9}\n", "volume_reduction"),
        ("version: '1.0'\nmappings:\n  - {from: a, to: b, max_impact: low, when: body_fat_over}\n"
         "volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n", "when"),
        ("version: '1.0'\nmappings:\n  - {from: a, to: b, max_impact: very_low, when: bmi_over_30}\n"
         "volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n", "max_impact"),
        ("version: '1.0'\nmappings:\n  - {from: a, to: b, when: bmi_over_30}\n"
         "volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n", "max_impact"),
        ("version: '1.0'\nmappings:\n  - {from: a, to: b, max_impact: low}\n"
         "volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n", "when"),
        ("[]\n", "顶层结构"),
    ],
)
def test_load_equivalence_rejects_a_malformed_table(tmp_path, mutant, needle):
    """坏等价表同样必须在加载时响亮失败，并点名文件与出错的那条映射。"""
    path = _write_yaml(tmp_path, mutant, name="exercise_equivalence.yaml")
    with pytest.raises(ValueError) as excinfo:
        rp.load_equivalence(path)
    message = str(excinfo.value)
    assert needle in message, message
    assert path.name in message, f"报错没点名文件：{message}"


def test_a_wellformed_minimal_library_round_trips(tmp_path):
    """**已知 GREEN 的干净对照**（硬规矩 #53）：上面两批拒绝用例全红的前提是加载器本身能
    吃下一份合法的 YAML。少了这一条，「把校验改成一律 raise」也能让全部拒绝用例变绿。
    """
    path = _write_yaml(tmp_path, GOOD_EXERCISE_YAML)
    library = rp.load_exercises(path)
    assert set(library) == {"interval_run", "bodyweight_resistance"}
    assert library["interval_run"].impact_level is ImpactLevel.HIGH
    assert library["interval_run"].targets == frozenset({"endurance"})
    assert isinstance(library["interval_run"].targets, frozenset)

    eq_path = _write_yaml(
        tmp_path,
        "version: '9.9'\n"
        "mappings:\n"
        "  - {from: interval_run, to: bodyweight_resistance, max_impact: low, when: bmi_over_30}\n"
        "volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}\n",
        name="exercise_equivalence.yaml",
    )
    table = rp.load_equivalence(eq_path)
    assert table.version == "9.9"
    assert len(table.mappings) == 1
    assert table.lookup("interval_run", ImpactLevel.LOW) == "bodyweight_resistance"


# ---------------------------------------------------------------------------
# 闸 4：domain 公开面基线（Plan 02 Task 2 fix round 2，账本 Ruling 107-4）
# ---------------------------------------------------------------------------

#: ``app.domain.prescription.__all__`` 的字面基线，**声明序**照
#: ``app/domain/prescription/__init__.py`` 里 ``__all__`` 的书写序逐字抄进来（三个词表常量
#: 在前、四个类型在后）。取法（在 ``backend/`` 下跑，一次性取证）::
#:
#:     python -c "from app.domain import prescription as p; print(p.__all__)"
#:
#: ⚠️ **不从 ``dir(prescription_pkg)`` 反推**（硬规矩 #35）：那样两侧同源，漏重导出一个名字
#: 两边一起少一个、恒等成立。**而且 ``dir()`` 本身还不可复现**：亲跑 ``dir(pkg)`` 的公有名
#: 是 ``['EQUIVALENCE_TRIGGERS', 'EquivalenceMapping', 'EquivalenceTable', 'ExerciseSpec',
#: 'IMPACT_RANK', 'ImpactLevel', 'TARGET_DOMAIN', 'exercises']``——最后那个 ``exercises``
#: 是**子模块属性**，只有在「已经有谁 import 过它」时才出现，故 ``dir()`` 的内容随导入顺序
#: 漂。这也是 ``tests/db/test_models.py`` 那边要靠 ``_MODELS_SUBMODULES`` 显式排除六个子模块
#: 名的原因；本基线钉 ``__all__`` 而不是 ``dir()``，一次就把这个问题绕开。
#:
#: **与 ``_MODELS_PUBLIC_BASELINE`` 的理由不同**（硬规矩 #56，别把那段注释的理由抄过来）：
#: 那 33 个名字是「``models.py`` 拆包前后导入面逐字不变」的**历史快照**，里面含一批**偶然
#: 公有**的名字（``dt`` / ``json`` / ``Boolean`` / ``mapped_column`` …），保留它们是「逐字
#: 相同」这个判据的应有代价。而这 7 个是 Task 2 **刻意选出**的公开面：每一个都是 Ruling 96
#: 搬进 domain 的动作库对象或词表，**没有一个是顺带公有的**（``exercises.py`` 模块级 import
#: 进来的 ``Mapping`` / ``dataclass`` / ``Enum`` / ``ITEM_BUCKET`` 四个名字在
#: ``dir(exercises)`` 里也是公有的、共 11 个，而它们**一个都没被重导出**、也不在本基线里，
#: 支 5 的 AST 口径把它们排除在外）。故本基线的性质是**逐 Task 递增**（Task 3 往
#: ``templates.py`` 加模板对象时同步追加），不是「冻结」。
_PRESCRIPTION_PUBLIC_BASELINE = [
    "EQUIVALENCE_TRIGGERS",
    "IMPACT_RANK",
    "TARGET_DOMAIN",
    "EquivalenceMapping",
    "EquivalenceTable",
    "ExerciseSpec",
    "ImpactLevel",
]


def test_prescription_public_namespace_is_pinned_verbatim():
    """``app.domain.prescription`` 的公开面被字面钉住（Plan02 账本 Ruling 107-4）。

    ``app/db/models`` 那边有 ``_MODELS_PUBLIC_BASELINE``（33 个名字）钉住拆包前后的导入面，
    domain 这个包**没有**对应的守卫——而它的 ``__all__`` 在 Task 2 从 1 个名字扩到 7 个，
    Task 3-9 每个 Task 都要往里追加。

    **失效形态**（硬规矩 #39，逐条给主语）：

    * 谁往 ``__all__`` 里**加**了一个名字（Task 3 的 ``Template`` 一类）却没同步本基线
      → **支 2 红**；
    * 谁把 ``__all__`` 里一个名字**删掉** → **支 2 红**；谁只删 ``from .exercises import (…)``
      里的一个名字而留着 ``__all__`` 里那一个 → **支 4 红**（``__all__`` 谎报：
      ``from app.domain.prescription import *`` 会在运行期 ``AttributeError``，而那条路径
      今天没有任何测试走）；
    * 谁往 ``exercises.py`` 加了新的**公有顶层定义**却忘了重导出 → **支 5 红**。⚠️ 这一支
      是**唯一**抓得住这个方向的：那种情况下 ``__all__`` 根本没变，支 2 与支 4 都不会响；
    * 谁把 ``exercises.py`` 里某个对象**改名** → 支 4 与支 5 一起红；
    * 谁把 ``__all__`` **重排**成字母序 → 支 2 红（支 3 是这一支的反面对照：基线自己不是
      字母序，故支 2 真的在钉顺序）。

    **它守不住什么**：不守这 7 个名字各自的**取值**——``IMPACT_RANK`` 的秩值由
    :func:`test_impact_rank_values_are_pinned_verbatim` 钉、``TARGET_DOMAIN`` 与
    ``EQUIVALENCE_TRIGGERS`` 由闸 2 那两条钉、``ImpactLevel`` 的词表由
    ``tests/domain/test_prescription_templates.py`` 钉；也不守 ``templates.py`` 的
    ``__all__``（那是**另一份**，由那个文件 fix round 2 新加的第 4 条守卫钉住。两份
    ``__all__`` 必须一起改，这句话同时写在 ``templates.py`` 与 ``prescription/__init__.py``
    的 docstring 里）。

    **红/绿双输入**（硬规矩 #50）：绿输入 = 今天的真实状态（支 1-5 实跑通过）；红输入 =
    支 6 在测试内**合成**的两种失同步状态（多一个 ``Template`` / 少最后一个名字），比对
    必须判不相等——它证明支 2 那条相等断言对「多一个」与「少一个」都敏感、不是恒真式
    （**M-C1 实测：支 6b 真的开了火**，见下）。
    改生产码的真变异本轮实跑过三个（逐支真值见报告 §fr2.4），**各打不同的支**：
    **M-C1**（``__all__`` 里删掉 ``ImpactLevel``，7 → 6）→ **支 2 红**，且**支 6b 也一起红**
    （那种状态下 ``list(__all__)`` 恰好等于 ``baseline[:-1]``，故支 6 不是装饰），
    ``1 failed, 530 passed``；**M-C2**（只删 ``from .exercises import (…)`` 里的
    ``ImpactLevel``、``__all__`` 里留着）→ **只有支 4 红**，``1 failed, 530 passed``；
    **M-C3**（往 ``exercises.py`` 加一个公有顶层定义 ``SUBSTITUTE_POLICY`` 而**不**重导出、
    ``__all__`` 一个字没改）→ **只有支 5 红**，``1 failed, 530 passed``——这一支是那个
    方向上**唯一**的守卫，没有它这件事就完全静默。

    **六支的主语**（硬规矩 #56）：支 1 = 基线自己；支 2 = ``__all__`` 的内容**与声明序**；
    支 3 = 声明序不是字母序；支 4 = ``__all__`` 不许谎报；支 5 = 公开面对 ``exercises.py``
    的公有顶层定义**穷尽**；支 6 = 反面对照。
    """
    baseline = set(_PRESCRIPTION_PUBLIC_BASELINE)
    # 支 1：基线自校（口径照 tests/db/test_models.py 的 len(_MODELS_PUBLIC_BASELINE) == 33）
    assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 7, "基线是 7 个名字，抄漏了就当场红"
    # 支 2（绿输入）：内容与**声明序**都逐字相同
    assert list(prescription_pkg.__all__) == _PRESCRIPTION_PUBLIC_BASELINE
    # 支 3：基线不是字母序，故支 2 真的在钉顺序（重排成 sorted() 会让支 2 红）
    assert sorted(_PRESCRIPTION_PUBLIC_BASELINE) != _PRESCRIPTION_PUBLIC_BASELINE
    # 支 4：__all__ 不许谎报。先断言所有者侧取到的不是 None，否则 `None is None` 会让
    #       这一支退化成恒真（假绿）。
    for name in _PRESCRIPTION_PUBLIC_BASELINE:
        owner = getattr(exercises_mod, name, None)
        assert owner is not None, (
            f"所有者模块 exercises 上没有 {name}，同一性比对会退化成 None is None"
        )
        assert getattr(prescription_pkg, name, None) is owner, (
            f"{name} 在包上取不到、或取到的不是 exercises 里的那个对象（公开面谎报）"
        )
    # 支 5：穷尽。期望侧仍是**字面基线**，实际侧是 AST 扫源码（不是 dir()，故不构成 #35 的
    #       同源）。只有顶层**定义**算数：模块级 import 进来的名字（Mapping / dataclass /
    #       Enum / ITEM_BUCKET）不算，它们本来也不该被重导出。
    tree = ast.parse(pathlib.Path(exercises_mod.__file__).read_text(encoding="utf-8"))
    defined = {
        node.name for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and not node.name.startswith("_")
    } | {
        target.id
        for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name) and not target.id.startswith("_")
    }
    assert defined == baseline, (
        "exercises.py 的公有顶层定义与公开面基线不同步："
        f"只在源码里（加了却没重导出）= {sorted(defined - baseline)}；"
        f"只在基线里（已被删掉或改名）= {sorted(baseline - defined)}"
    )
    # 支 6（红输入，硬规矩 #50）：合成的两种失同步状态，比对必须判不相等
    assert list(prescription_pkg.__all__) != _PRESCRIPTION_PUBLIC_BASELINE + ["Template"]
    assert list(prescription_pkg.__all__) != _PRESCRIPTION_PUBLIC_BASELINE[:-1]

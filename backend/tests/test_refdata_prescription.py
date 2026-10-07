# backend/tests/test_refdata_prescription.py
"""动作库两份 YAML 的加载 / 校验 / ``exercise`` 表投影（Plan 02 Task 2）。

本文件是 ``backend/data/exercises.yaml`` 与 ``backend/data/exercise_equivalence.yaml``
的**唯一守卫**，角色与 ``tests/test_refdata.py`` 对国标评分表的角色同构（Ruling 213
的教训照搬）：这两份是体育专家手工维护的知识资产，**改一个值往往不破坏任何形状
不变量**，只有指纹能挡住它。故本文件同时下三道闸：

1. **指纹**（:func:`test_exercises_yaml_fingerprint_is_pinned` /
   :func:`test_equivalence_yaml_fingerprint_is_pinned`）——任何字节改动都红；
2. **跨文件不变量**（等价映射只指向存在的动作、**永不升冲击**、每个 ``high`` 都有
   ``low`` 替身）——这三条是 spec §7.4 安全后置的成立前提；
3. **字面钉住的常量**（``volume_reduction`` 的两个系数、RFC 2606 占位符 URL 形状、
   四个无 CHECK 约束列的列宽）——两侧不同源（硬规矩 #35）。

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
from app.domain.indicators import ITEM_BUCKET
from app.domain.prescription.templates import ImpactLevel

# ---------------------------------------------------------------------------
# 期望侧的字面量（一律不从被测 YAML 读回，硬规矩 #35）
# ---------------------------------------------------------------------------

#: ``exercises.yaml`` 的 sha256 前 16 位（大写十六进制），**行尾归一化为 LF 之后**计算。
#: 归一化的理由与 ``tests/test_refdata.py`` 的 ``STANDARD_FINGERPRINT`` 完全相同
#: （Ruling 231）：``core.autocrlf`` 在 Git for Windows 上缺省为 ``true``，裸字节哈希会
#: 随平台配置漂移、新克隆必红。``backend/data/*.yaml`` 已由 ``.gitattributes:14`` 钉成
#: ``eol=lf``，故这里的归一化是**第二道保险**而不是唯一依赖。
EXERCISES_FINGERPRINT = "A6A000F58815FCBB"

#: ``exercise_equivalence.yaml`` 的同口径指纹。
EQUIVALENCE_FINGERPRINT = "0FFB881574AC04F3"

#: ``targets`` 的取值域 = ``ITEM_BUCKET`` 的三个桶名（P2-A4）。
#: ⚠️ **不能写成 ``set(ITEM_BUCKET.values())``**：那个集合有 **4** 个元素、含 ``None``
#: （``ITEM_BUCKET[ScoredItem.BMI] is None``，因为 BMI 天然不属于任何短板桶），照字面写
#: 会把 ``None`` 放进取值域、并让一个空 ``targets`` 悄悄合法。下面
#: :func:`test_target_domain_is_the_three_bucket_names_not_the_raw_values` 把这件事钉住。
TARGET_DOMAIN = frozenset(v for v in ITEM_BUCKET.values() if v is not None)

#: 冲击等级的**降序**（高 → 低）。字面写死，不从 ``ImpactLevel`` 派生：枚举继承 ``str``，
#: 它的 ``<`` 是字典序（``"high" < "low" < "medium"``），与冲击序无关，故序关系必须由
#: 消费方显式声明。生产侧那份在 ``app/refdata_prescription.py`` 的 ``_IMPACT_RANK``，
#: 两侧不同源，改坏任何一侧都会让
#: :func:`test_equivalence_never_maps_to_a_higher_impact_level` 红。
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
    assert None in raw_values, "BMI 不归桶（Plan01 Ruling 19），故 None 必在其中"
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
    完全无关）。生产侧 ``app/refdata_prescription.py`` 的 ``_IMPACT_RANK`` 是同一序的
    第二份、供 :meth:`EquivalenceTable.lookup` 使用；两份刻意不同源，改坏任何一份本条
    都红（硬规矩 #35）。

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
    synthetic = rp.EquivalenceTable(
        version="synthetic",
        mappings=(
            rp.EquivalenceMapping(
                from_ref="a", to_ref="b",
                max_impact=ImpactLevel.MEDIUM, when="bmi_over_30",
            ),
        ),
        volume_reduction={},
    )
    assert synthetic.lookup("a", ImpactLevel.MEDIUM) == "b"
    assert synthetic.lookup("a", ImpactLevel.HIGH) == "b"
    assert synthetic.lookup("a", ImpactLevel.LOW) is None


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

    这条与 :func:`test_impact_level_vocabulary_agrees_with_the_domain_enum` 分工不同：
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

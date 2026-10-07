"""处方侧参考数据（``backend/data/`` 下的 YAML）的加载、校验与 ``exercise`` 表投影。

**本模块分两段**（Plan02 账本 P2-B3：File Structure 只说它「加载 18 套模板 YAML 与
``exercise_equivalence.yaml``」，漏了 ``exercises.yaml``，故把分段写在这里，免得 Task 3
重写整个 docstring）：

===========================  =========  ======================================
段                            归属 Task   内容
===========================  =========  ======================================
动作库 + 等价映射表           **Task 2**  ``exercises.yaml`` / ``exercise_equivalence.yaml``
                                          的加载器、值对象、``sync_exercises``
18 套处方模板                 Task 3      ``data/prescription/*.yaml`` 的加载器与校验
===========================  =========  ======================================

依赖方向与 :mod:`app.refdata` 相同：refdata_prescription → domain（把 YAML 解析成值对象
再交给 domain 的纯函数），domain 因此保持为无 I/O 的叶子（Global Constraint #1），不会
隐式依赖磁盘上某个 YAML 是否存在。``DATA_DIR`` 取自 :mod:`app.refdata`（它取自
:mod:`app.config`），本模块只新增**处方侧那两个 YAML 的文件名**。

⚠️ **值对象为什么住在这里而不是 ``app/domain/prescription/``**：Plan02 账本 P2-B1 裁定
``templates.py`` 本 Task **只放 ``ImpactLevel``**（模板的数据结构归 Task 3），故
:class:`ExerciseSpec` / :class:`EquivalenceMapping` / :class:`EquivalenceTable` 与它们的
唯一加载器同住。这与 :mod:`app.pipeline.clean` 的 ``FieldRange``（也是「加载器自己持有
它解析出来的值对象」）同一形状。**代价要写明**（硬规矩 #39）：``app/domain/`` 的
allow-list 守卫只放行 ``app.domain`` 前缀与 5 个标准库模块，故 domain 的纯函数（Task 7 的
``safety.py``）**不能 import 这三个类型来做类型标注**，只能按 ``Mapping`` / duck typing
接；若 Task 3/7 认为标注更重要，把这三个值对象搬进 ``app/domain/prescription/`` 是一次
Modify（那个包 Task 3 已经在改），搬完本模块改成从 domain import 即可。

**本模块同时是 ``exercise`` 表的灌数据入口**（:func:`sync_exercises`）。它刻意**不在**
``app/seed/``：Plan02 账本 P2-A1 的裁定，理由有三——① Global Constraint #10 把
``app/seed/`` 自 Plan 01 结案后重新冻结；② ``seed_database`` 的 docstring 明写它「**只**写
组织结构五张表」，而 ``tests/seed/test_generate.py`` 的
``test_seed_database_writes_only_organisation_tables_and_is_idempotent`` 把这句话变成了守卫；
③ ``exercise`` 是**参考数据**、不是仿真人口数据，与 ``app/seed/`` 的职责本就不同类，它的
同类是 :mod:`app.refdata`。
"""
import pathlib
import re
import types
from collections.abc import Mapping
from dataclasses import dataclass

import yaml
from sqlalchemy.orm import Session

from app.db.models.prescription import Exercise
from app.db.repo import upsert
from app.domain.indicators import ITEM_BUCKET
from app.domain.prescription.templates import ImpactLevel
from app.refdata import DATA_DIR

#: 动作库的**源**（``exercise`` 表由它投影）。``exercise_ref`` 与每个动作的
#: ``impact_level`` 都以这份文件的键集/字段为**唯一所有者**（Global Constraint #3）。
EXERCISES_FILENAME = "exercises.yaml"

#: 低冲击等价动作映射 + 映射表版本号 + 跑量下调系数。spec §4.4 ``:243`` 明写它与
#: ``alert_rules`` 一样是「``data/`` 下的**静态 YAML + 版本号**，不入库」。
EQUIVALENCE_FILENAME = "exercise_equivalence.yaml"

#: 每个动作必需的键，恰好这五个（多一个少一个都在加载时响亮失败）。
_EXERCISE_KEYS = ("name", "video_url", "impact_level", "targets", "equipment")

#: 每条等价映射必需的键。``from`` / ``to`` / ``max_impact`` / ``when`` 的字面形状取自
#: 计划 Task 2 Step 3。
_MAPPING_KEYS = ("from", "to", "max_impact", "when")

#: ``exercise_ref`` 的形状：小写字母开头，后续只允许小写字母 / 数字 / 下划线。
#: 收紧形状的理由是它是**跨文件的引用键**（模板 YAML 与等价表都按它引用），一个大小写
#: 混用的 ref 在 YAML 里看不出问题，而 Windows 的文件系统大小写不敏感、Linux 敏感，
#: 将来若有人按 ref 找文件就会在两个平台上表现不同。
_REF_SHAPE = re.compile(r"[a-z][a-z0-9_]*")

#: ``targets`` 的取值域：``ITEM_BUCKET`` 的三个桶名。
#: ⚠️ **不是 ``set(ITEM_BUCKET.values())``**（Plan02 账本 P2-A4）：那个集合有 **4** 个元素、
#: 含 ``None``（``ITEM_BUCKET[ScoredItem.BMI] is None``，因为 BMI 天然不属于任何短板桶，
#: Plan01 Ruling 19 的口径），照字面写会把 ``None`` 放进取值域、并让一个空 ``targets``
#: 悄悄合法。由 ``tests/test_refdata_prescription.py`` 的
#: ``test_target_domain_is_the_three_bucket_names_not_the_raw_values`` 钉住这个构造方式。
TARGET_DOMAIN: frozenset[str] = frozenset(
    bucket for bucket in ITEM_BUCKET.values() if bucket is not None
)

#: spec §7.4 ``:508-509`` 里**走等价表**的两个触发条件（``when`` 的取值域）。
#: ``:510`` 的第三个触发（体脂率异常）走的是「追加模板 ``addons`` 中的能量消耗模块」、
#: **不查等价表**，故它不在这里（Plan02 账本 P2-C3 亲验）。
EQUIVALENCE_TRIGGERS: frozenset[str] = frozenset({"bmi_over_30", "muscle_low_p10"})

#: 冲击等级的**降序**排名（0 = 冲击最高）。
#: ⚠️ 不能靠 ``ImpactLevel`` 的比较得出序：它继承 ``str``，``<`` 是字典序
#: （``"high" < "low" < "medium"``），与冲击序无关。测试侧另有一份**字面写死**的
#: ``IMPACT_DESCENDING``（``tests/test_refdata_prescription.py``），两份刻意不同源
#: （硬规矩 #35）：改坏任何一份，``test_equivalence_never_maps_to_a_higher_impact_level``
#: 与 :func:`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable`
#: 之一会红。
_IMPACT_RANK: dict[ImpactLevel, int] = {
    ImpactLevel.HIGH: 0,
    ImpactLevel.MEDIUM: 1,
    ImpactLevel.LOW: 2,
}

_exercises_cache: Mapping[str, "ExerciseSpec"] | None = None
_equivalence_cache: "EquivalenceTable | None" = None


@dataclass(frozen=True)
class ExerciseSpec:
    """``exercises.yaml`` 的一个条目。

    ``ref`` 是 ``exercise_ref`` 的**唯一所有者**（Global Constraint #3）：模板 YAML 与
    ``exercise_equivalence.yaml`` 都按它引用动作，而它的键集就住在那份 YAML 的顶层键上。
    Task 3 的模板加载器必须校验「每个 ``exercise_ref`` 都在动作库里」，违例在加载时响亮
    失败（Review Focus 第 1 条）。

    ``impact_level`` 同样是单一所有者（Plan02 账本 P2-B2）：**本字段是「这个动作是哪一档
    冲击」的唯一真相**。spec §7.2 ``:470-471`` 的模板 YAML 字面形状里每个 block 也自带一份
    ``impact_level``，那是**副本**；**负责校验一致的是 Task 3 的模板加载器**（不一致就在
    加载时响亮失败，与 ``exercise_ref`` 的处置同构）——本模块只加载动作库、看不到模板，
    故校验不住这件事，这一点必须写明（硬规矩 #39）。

    ``targets`` 是 ``frozenset``：一个动作可以同时瞄准多个素质桶（如折返跑既是耐力也是
    速度），而桶的**顺序不承重**（Task 4 的匹配按主导短板桶查，不按序）。用 ``frozenset``
    而不是 ``tuple`` 正是为了在类型上排除「顺序有意义」这个误读。
    """

    ref: str
    name: str
    video_url: str
    impact_level: ImpactLevel
    targets: frozenset[str]
    equipment: str


@dataclass(frozen=True)
class EquivalenceMapping:
    """``exercise_equivalence.yaml`` 的 ``mappings`` 里的一条。

    ``from_ref`` 是被替换的动作（今天全是 ``high`` 冲击），``to_ref`` 是替身，
    ``max_impact`` 是这条映射**自己声明**的替身冲击上限，``when`` 是触发条件。

    ``max_impact`` 与 ``to_ref`` 的真实冲击必须一致——:meth:`EquivalenceTable.lookup`
    是按 ``max_impact`` 过滤的、**不看动作库**，故一张撒谎的表会让 lookup 返回一个冲击
    高于上限的动作。这条一致性由
    ``tests/test_refdata_prescription.py::test_equivalence_never_maps_to_a_higher_impact_level``
    钉住（它同时验「不升冲击」与「声明与真实一致」两件事）。
    """

    from_ref: str
    to_ref: str
    max_impact: ImpactLevel
    when: str


@dataclass(frozen=True)
class EquivalenceTable:
    """一张完整的低冲击等价映射表（spec §4.4 ``:243``：静态 YAML + **版本号**，不入库）。

    ``version`` 会被 Task 7 写进 ``prescription.safety_substitutions``（spec §7.4 ``:512``
    要求记录「原动作、新动作、触发条件、**映射表版本号**」），于是一张已生成的处方能回答
    「当时是按哪一版映射表替换的」。

    ``volume_reduction`` 的两个系数是「跑量按映射表下调」（spec §7.4 ``:508-509``）的
    具体数值。⚠️ **它们在 spec 里没有出处**（Plan02 账本 P2-A3）：``:508`` 只写「按映射表
    下调」、没给任何数，``:509`` 写「同上」。spec 里唯一出现的「系数 0.8」在 ``:604``，
    那是**预警触发的减量 20%**（``weekly_adjustment(系数 0.8, 原因 RED_RPE_SUSTAINED)``，
    属 Plan 03），与本表的跑量下调是**两个不同机制**；``0.9`` 在 spec 里根本没有对应物。
    故这两个数是**本设计的默认规定**，已登记进 ``exercise_equivalence.yaml`` 的注释与
    spec §14 第 28 项；**Task 7 消费时不得把它们当成 spec 条文引用**。
    """

    version: str
    mappings: tuple[EquivalenceMapping, ...]
    volume_reduction: Mapping[str, float]

    def lookup(self, ref: str, impact_ceiling: ImpactLevel) -> str | None:
        """``ref`` 在冲击不超过 ``impact_ceiling`` 的前提下的替身；查不到返回 ``None``。

        返回 ``None`` **不是**「静默跳过」：spec §7.4 ``:514`` 明写「安全规则命中但映射表
        找不到等价动作时，不静默跳过」——生成 ``warning`` 级日志、处方状态置
        ``needs_review``、教师端标记「需人工复核」。故 Task 7 拿到 ``None`` 必须走那条路径
        （Review Focus 第 5 条），而不是把原动作留在训练包里。

        命中条件是 ``_IMPACT_RANK[max_impact] >= _IMPACT_RANK[impact_ceiling]``，即映射
        声明的上限**不高于**调用方给的上限。取**第一条**命中者：``mappings`` 的顺序就是
        YAML 里的书写顺序（``load_equivalence`` 不重排），故专家可以通过调整书写顺序来
        表达偏好，而不必引入一个额外的优先级字段。
        """
        ceiling_rank = _IMPACT_RANK[impact_ceiling]
        for mapping in self.mappings:
            if mapping.from_ref != ref:
                continue
            if _IMPACT_RANK[mapping.max_impact] >= ceiling_rank:
                return mapping.to_ref
        return None


def _exercise_spec(path: pathlib.Path, ref: object, entry: object) -> ExerciseSpec:
    """校验并构造一个 :class:`ExerciseSpec`，违例带**文件名 + ref + 字段名**响亮失败。

    ⚠️ **报错点不出 YAML 行号**（硬规矩 #39：写下守卫能力时必须写明它守不住什么）：
    ``yaml.safe_load`` 不保留位置信息，要行号得改用 ``yaml.compose`` 逐节点读
    ``start_mark``。本 Task 不做——Review Focus 第 1 条对「哪个文件哪一行」的要求是针对
    **18 套模板 YAML**（Task 3）的，那边一个文件一套模板、行号是定位的唯一手段；动作库
    是**单文件多条目**，``ref`` 就足以定位到那 6 行。
    """
    if not isinstance(ref, str) or _REF_SHAPE.fullmatch(ref) is None:
        raise ValueError(
            f"动作库 {path} 的动作 ref {ref!r} 形状非法：只允许小写字母开头、"
            f"后续为小写字母/数字/下划线（正则 {_REF_SHAPE.pattern}）"
        )
    if not isinstance(entry, dict):
        raise ValueError(
            f"动作库 {path} 的 {ref} 应为「属性名 → 值」的映射，"
            f"实为 {type(entry).__name__}"
        )
    missing = [key for key in _EXERCISE_KEYS if key not in entry]
    if missing:
        raise ValueError(
            f"动作库 {path} 的 {ref} 缺键 {missing}；必需的键恰好是 {list(_EXERCISE_KEYS)}"
        )
    unexpected = sorted(set(entry) - set(_EXERCISE_KEYS))
    if unexpected:
        raise ValueError(
            f"动作库 {path} 的 {ref} 有多余的键 {unexpected}；必需的键恰好是 "
            f"{list(_EXERCISE_KEYS)}。多余的键会被静默忽略，而它通常意味着改名后忘了删"
            f"旧的那一个——例如把 equipment 改写成 equipments，读到的就永远是旧值"
        )

    name = entry["name"]
    if not isinstance(name, str) or not name.strip():
        raise ValueError(
            f"动作库 {path} 的 {ref} 的 name 应为非空字符串（学生端要显示它），实为 {name!r}"
        )
    video_url = entry["video_url"]
    if not isinstance(video_url, str) or not video_url.strip():
        raise ValueError(
            f"动作库 {path} 的 {ref} 的 video_url 应为非空字符串"
            f"（spec §7.3 :499 的装配第 5 步会把它填进训练包的二维码），实为 {video_url!r}"
        )
    equipment = entry["equipment"]
    if not isinstance(equipment, str) or not equipment.strip():
        raise ValueError(
            f"动作库 {path} 的 {ref} 的 equipment 应为非空字符串"
            f"（无器械请写 none 而不是留空：留空分不清「不需要器械」与「忘了填」），"
            f"实为 {equipment!r}"
        )
    try:
        impact_level = ImpactLevel(entry["impact_level"])
    except ValueError:
        raise ValueError(
            f"动作库 {path} 的 {ref} 的 impact_level 值非法: {entry['impact_level']!r}；"
            f"合法值: {[level.value for level in ImpactLevel]}（spec §4.4 :239）。"
            f"拼错的档位不会被 spec §7.4 的安全后置识别成 high，"
            f"BMI > 30 的学生会照旧被安排高冲击动作，而全链路没有一处报错"
        ) from None
    targets_raw = entry["targets"]
    if not isinstance(targets_raw, list) or not targets_raw:
        raise ValueError(
            f"动作库 {path} 的 {ref} 的 targets 应为**非空**列表，实为 {targets_raw!r}："
            f"一个不瞄准任何素质桶的动作无法被 18 套模板中的任何一套选用"
        )
    unknown = [bucket for bucket in targets_raw if bucket not in TARGET_DOMAIN]
    if unknown:
        raise ValueError(
            f"动作库 {path} 的 {ref} 的 targets 含非桶名 {unknown}；"
            f"合法值: {sorted(TARGET_DOMAIN)}（来自 app.domain.indicators.ITEM_BUCKET 的"
            f"三个桶名；⚠️ bmi 不是桶名——BMI 不归任何短板桶，ITEM_BUCKET[BMI] is None）"
        )
    return ExerciseSpec(
        ref=ref,
        name=name,
        video_url=video_url,
        impact_level=impact_level,
        targets=frozenset(targets_raw),
        equipment=equipment,
    )


def load_exercises(path: pathlib.Path | None = None) -> Mapping[str, ExerciseSpec]:
    """读取动作库 YAML 并构造「``exercise_ref`` → :class:`ExerciseSpec`」的只读映射。

    顶层结构是**以 ref 为键的映射**（不是一个列表）：这样「``exercise_ref`` 的唯一所有者
    是 ``exercises.yaml`` 的**键集**」这句话在文件形状上就成立，而不必靠「列表里每项有个
    ``ref`` 字段、且它们互不重复」这条需要额外校验的约定。

    ⚠️ **PyYAML 对重复的顶层键是后者覆盖前者、不报错**（实测
    ``yaml.safe_load("a: 1\\na: 2") == {"a": 2}``），故「专家复制一段忘了改 ref」会让一个
    动作**静默消失**。本函数看不出来（它拿到的已经是覆盖后的 dict），守卫在
    ``tests/test_refdata_prescription.py::test_exercise_refs_are_snake_case_and_unique_keys``
    ——那条用**原始文本**数一遍顶层键、与解析结果对账，两侧不同源。

    ``path`` 缺省为 ``DATA_DIR / EXERCISES_FILENAME``；文件不存在抛 ``FileNotFoundError``。
    返回 :class:`types.MappingProxyType`：``frozen=True`` 只挡住换掉整个字段，挡不住
    ``library[ref] = ...`` 的就地改写，而 :func:`exercises` 是进程内共享单例，一次误写会
    让之后所有装配静默变质（与 ``StandardTable.segments`` 同一处置，见
    :func:`app.refdata.load_standard` 的 docstring）。底层 dict 是本函数的局部变量、
    不外泄，故这个只读视图是有效的。

    **返回类型标注是 ``Mapping`` 而不是计划里写的 ``dict``**：运行时对象是
    ``MappingProxyType``，它**不是** ``dict`` 的实例（``isinstance(MappingProxyType({}),
    dict)`` 为 ``False``），标 ``dict`` 会是一个假标注。这与 ``StandardTable.segments``
    声明为 ``Mapping[...]``、由加载方装入 ``MappingProxyType`` 的既有口径一致。
    """
    yaml_path = DATA_DIR / EXERCISES_FILENAME if path is None else pathlib.Path(path)
    if not yaml_path.is_file():
        raise FileNotFoundError(f"动作库缺失: {yaml_path}")
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if raw is None:
        raise ValueError(
            f"动作库 {yaml_path} 为空：Task 3 的 18 套模板将没有任何 exercise_ref 可引"
        )
    if not isinstance(raw, dict):
        raise ValueError(
            f"动作库 {yaml_path} 的顶层结构应为「exercise_ref → 属性映射」，"
            f"实为 {type(raw).__name__}"
        )
    library = {ref: _exercise_spec(yaml_path, ref, entry) for ref, entry in raw.items()}
    return types.MappingProxyType(library)


def exercises() -> Mapping[str, ExerciseSpec]:
    """进程内单例：动作库是只读参考数据，一个进程加载一次即可。

    与 :func:`app.refdata.standard` 同口径（Plan02 账本 P2-A9：``load_standard`` 只负责
    加载、**不缓存**，单例是另一个函数）。
    """
    global _exercises_cache
    if _exercises_cache is None:
        _exercises_cache = load_exercises()
    return _exercises_cache


def _equivalence_mapping(
    path: pathlib.Path, index: int, item: object
) -> EquivalenceMapping:
    """校验并构造一条 :class:`EquivalenceMapping`，违例点名文件与是第几条。"""
    if not isinstance(item, dict):
        raise ValueError(
            f"等价映射表 {path} 的 mappings[{index}] 应为映射，实为 {type(item).__name__}"
        )
    missing = [key for key in _MAPPING_KEYS if key not in item]
    if missing:
        raise ValueError(
            f"等价映射表 {path} 的 mappings[{index}] 缺键 {missing}；"
            f"必需的键恰好是 {list(_MAPPING_KEYS)}"
        )
    unexpected = sorted(set(item) - set(_MAPPING_KEYS))
    if unexpected:
        raise ValueError(
            f"等价映射表 {path} 的 mappings[{index}] 有多余的键 {unexpected}；"
            f"必需的键恰好是 {list(_MAPPING_KEYS)}"
        )
    for key in ("from", "to"):
        value = item[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"等价映射表 {path} 的 mappings[{index}] 的 {key} 应为非空的 exercise_ref，"
                f"实为 {value!r}"
            )
    when = item["when"]
    if when not in EQUIVALENCE_TRIGGERS:
        raise ValueError(
            f"等价映射表 {path} 的 mappings[{index}]"
            f"（{item['from']} → {item['to']}）的 when 值非法: {when!r}；"
            f"合法值: {sorted(EQUIVALENCE_TRIGGERS)}——spec §7.4 :508-509 只有这两个触发"
            f"走等价表，:510 的「体脂率异常」走模板 addons 的能量消耗模块、**不查本表**"
        )
    try:
        max_impact = ImpactLevel(item["max_impact"])
    except ValueError:
        raise ValueError(
            f"等价映射表 {path} 的 mappings[{index}] 的 max_impact 值非法: "
            f"{item['max_impact']!r}；合法值: {[level.value for level in ImpactLevel]}"
        ) from None
    return EquivalenceMapping(
        from_ref=item["from"],
        to_ref=item["to"],
        max_impact=max_impact,
        when=when,
    )


def load_equivalence(path: pathlib.Path | None = None) -> EquivalenceTable:
    """读取 ``exercise_equivalence.yaml`` 并构造 :class:`EquivalenceTable`。

    校验顺序是 **version → volume_reduction → mappings**：前两个是**表级**属性（缺了整张
    表就没法用），第三个是**条目级**的，逐条报错时要点名是第几条，故放最后。

    ⚠️ **本函数不做跨文件校验**（硬规矩 #39）：它**不检查** ``from`` / ``to`` 是否真的在
    动作库里，因为那会让「删掉 ``exercises.yaml`` 里一个没人引用的 ref」连带把等价表也
    判成坏的，从而掩盖真正该红的那一条。跨文件不变量由
    ``tests/test_refdata_prescription.py::test_equivalence_table_only_maps_to_existing_exercises``
    守；若 Task 7 认为它必须在**加载时**而不是**测试时**被挡住，把校验加在这里即可，
    届时要连带调整那条测试与简报 Step 5 的变异 ②（「只有指纹测试会红」将不再成立）。
    """
    yaml_path = DATA_DIR / EQUIVALENCE_FILENAME if path is None else pathlib.Path(path)
    if not yaml_path.is_file():
        raise FileNotFoundError(f"等价映射表缺失: {yaml_path}")
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(
            f"等价映射表 {yaml_path} 的顶层结构应为映射"
            f"（version / mappings / volume_reduction 三个键），实为 {type(raw).__name__}"
        )

    version = raw.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(
            f"等价映射表 {yaml_path} 的 version 缺失或不是非空字符串，实为 {version!r}："
            f"spec §7.4 :512 要求把**映射表版本号**写进 prescription.safety_substitutions，"
            f"没有它一张已生成的处方就无法回答「当时是按哪一版映射表替换的」"
        )

    volume_reduction = raw.get("volume_reduction")
    if not isinstance(volume_reduction, dict):
        raise ValueError(
            f"等价映射表 {yaml_path} 的 volume_reduction 缺失或不是映射，"
            f"实为 {volume_reduction!r}：spec §7.4 :508-509 的两个触发都要求"
            f"「跑量按映射表下调」，下调多少就住在这个键里"
        )
    if set(volume_reduction) != EQUIVALENCE_TRIGGERS:
        raise ValueError(
            f"等价映射表 {yaml_path} 的 volume_reduction 的键应恰好是 "
            f"{sorted(EQUIVALENCE_TRIGGERS)}，实为 {sorted(volume_reduction)}"
        )
    for trigger, factor in sorted(volume_reduction.items()):
        if not isinstance(factor, float) or not 0.0 < factor < 1.0:
            raise ValueError(
                f"等价映射表 {yaml_path} 的 volume_reduction[{trigger!r}] = {factor!r} "
                f"不在 (0.0, 1.0) 内：> 1 是「安全触发反而加量」，<= 0 是把训练量清零、"
                f"处方名存实亡"
            )

    if "mappings" not in raw:
        raise ValueError(
            f"等价映射表 {yaml_path} 缺 mappings 键：没有映射，spec §7.4 的"
            f"「high 冲击动作换低冲击等价动作」就一条也做不了"
        )
    mappings_raw = raw["mappings"]
    if not isinstance(mappings_raw, list):
        raise ValueError(
            f"等价映射表 {yaml_path} 的 mappings 应为列表，实为 {type(mappings_raw).__name__}"
        )
    return EquivalenceTable(
        version=version,
        mappings=tuple(
            _equivalence_mapping(yaml_path, index, item)
            for index, item in enumerate(mappings_raw)
        ),
        volume_reduction=types.MappingProxyType(dict(volume_reduction)),
    )


def equivalence() -> EquivalenceTable:
    """进程内单例，与 :func:`exercises` 同口径。

    本 Task 的四个函数里计划只点了 ``load_exercises`` / ``exercises`` / ``load_equivalence``
    三个；补这一个是为了**对称**：Task 7 的安全后置是逐学生跑的，少了单例就会每人重解析
    一次 YAML，而 spec §1.3 给单人处方生成的预算是 p95 < 3 秒。
    """
    global _equivalence_cache
    if _equivalence_cache is None:
        _equivalence_cache = load_equivalence()
    return _equivalence_cache


def sync_exercises(session: Session) -> int:
    """把动作库投影进 ``exercise`` 表，返回写入的行数（幂等）。

    按 ``ref`` 走 :func:`app.db.repo.upsert`：有则更新非键列、无则插入，故**重跑不翻倍**，
    且 YAML 改了某个字段时那一行被**就地更新**而不是插出第二行。返回值恒等于动作库条目数
    ——「写入行数」的口径是**本次 upsert 触及的行数**，不是「新插入的行数」；这样它对
    首次灌库与重跑给出同一个数，调用方不必区分两种情况。

    **本函数 flush 但不 commit**：事务边界由调用方掌握（与 :func:`app.db.repo.upsert`
    同一口径）。flush 是必要的——``impact_level`` 的 CHECK 约束与 ``ref`` 的 UNIQUE 约束
    只在真正执行 INSERT/UPDATE 时才生效，不 flush 的话一次坏投影会推迟到调用方 commit
    时才炸，离真因更远。

    ⚠️ **它不删除 YAML 里已经不存在的行**（硬规矩 #39）：从一个动作库里删掉一个动作，
    ``sync_exercises`` 之后那一行仍在表中。这是刻意的——``prescription``（Task 9）会按
    ``exercise_ref`` 引用历史处方里的动作，删行会让已生成的处方指向一个查不到的动作。
    若要真的下线一个动作，那是一次需要人工确认的迁移，不该由一个幂等同步函数顺手做掉。

    ⚠️ **谁在生产路径上调用它，本 Task 没有决定**：Plan02 账本 P2-A1 明确禁止把它接进
    ``seed_database``（那会撞上「只写组织结构五张表」的守卫），故今天它只有测试这一个
    调用方。接进管道是 Task 9/10 的活。
    """
    library = exercises()
    for spec in library.values():
        upsert(
            session,
            Exercise,
            ("ref",),
            {
                "ref": spec.ref,
                "name": spec.name,
                "video_url": spec.video_url,
                "impact_level": spec.impact_level.value,
                # frozenset 不能直接 JSON 序列化，且它的迭代序跨进程不稳定；
                # 排序让落库字节只由内容决定，canonical dump 才可复现。
                "targets": sorted(spec.targets),
                "equipment": spec.equipment,
            },
        )
    session.flush()
    return len(library)

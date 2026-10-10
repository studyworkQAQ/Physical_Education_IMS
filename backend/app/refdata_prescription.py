"""处方侧参考数据（``backend/data/`` 下的 YAML）的加载、校验与 ``exercise`` 表投影。

**本模块分两段**（Plan02 账本 P2-B3：File Structure 只说它「加载 18 套模板 YAML 与
``exercise_equivalence.yaml``」，漏了 ``exercises.yaml``，故把分段写在这里，免得 Task 3
重写整个 docstring）：

===========================  =========  ======================================
段                            归属 Task   内容
===========================  =========  ======================================
动作库 + 等价映射表           **Task 2**  ``exercises.yaml`` / ``exercise_equivalence.yaml``
                                          的加载器与 ``sync_exercises``（值对象自 Ruling 96
                                          起住 ``app/domain/prescription/exercises.py``）
18 套处方模板                 **Task 3**  ``data/prescription/*.yaml`` 的加载器与校验
                                          （``load_templates`` / ``templates``）与
                                          ``sync_templates``（``prescription_template`` 表的
                                          投影入口；值对象住
                                          ``app/domain/prescription/templates.py``）
===========================  =========  ======================================

**两段的报错口径刻意不同**（硬规矩 #39：写下守卫能力时要写明它守不住什么；⚠️ 而这两段
**今天都由 :mod:`app.refdata_yaml` 实现**——Plan 03 Task 6 把那套机制里通用的 6 个助手
抽进了那个公共模块，本模块只留 5 个薄适配器 + 一个 ``_line_index`` 别名，
故下面讲的「口径」是 :mod:`app.refdata_yaml` 的口径、由本模块与
:mod:`app.refdata_alerts` 两个消费者共用，见本 docstring 第四节）：动作库那一段
点名「文件 + ``ref`` + 字段名」而**点不出行号**（``_exercise_spec`` 的 docstring 里写着
理由：``yaml.safe_load`` 不保留位置信息，而动作库是**单文件多条目**，``ref`` 就足以定位到
那 6 行）；模板那一段**必须点出行号**，因为它是一文件一套、每套 40–60 行，行号是定位的
唯一手段（Review Focus 第 1 条的原文要求「指出是哪个文件哪一行」）。实现方式是另跑一次
``yaml.compose`` 建一张「键路径 → 1 基行号」的索引（:func:`_line_index`）。
⚠️ **代价**：每份模板解析两次。18 份文件、进程内只加载一次（:func:`templates` 是单例），
故这笔开销与 spec §1.3 的 p95 < 3 秒预算无关。
⚠️ **它守不住**：缺失的键**没有自己的位置**，那一档报到的是**它所在的块**的首行
（例如缺 ``review.status`` 时报 ``review:`` 那一行）；YAML 语法错时索引根本建不出来，
那一档退化成 PyYAML 自己的 mark（已包成 ``ValueError`` 并带上文件名）。

⚠️ **Plan 03 Task 6 把那套机制里通用的 6 个助手抽进了 :mod:`app.refdata_yaml`**
（P6-A2：计划原文给的处置是「**直接照抄那套形状**，不要另发明一套」，而「照抄」在字面上
等于复制、**复制就是第二个所有者**，Global Constraint #3）。本模块从此只留 5 个**薄适配器**
（:func:`_fail` / :func:`_exact_keys` / :func:`_as_int` / :func:`_as_float` /
:func:`_as_optional_text`，各一句「转发 + 绑 :data:`_DOC_KIND`」）与一个别名
:data:`_line_index`。⚠️ **报错文本逐字不变**：那 6 个助手的逻辑只有
:mod:`app.refdata_yaml` 一份，而 ``doc_kind`` 由本模块绑成 ``"处方模板"``
（它原先是硬编码在 ``_fail`` 里的前缀；搬进共用模块之后若不参数化，
``alert_rules.yaml`` 被改坏时就会报「处方模板 …/alert_rules.yaml 第 3 行」）。
守卫是 ``tests/test_refdata_alerts.py``（AST 钉「6 个名字各只有一处定义」与
「适配器只转发」，另加 ``_line_index is refdata_yaml.line_index`` 的身份比对）。

依赖方向与 :mod:`app.refdata` 相同：refdata_prescription → domain（把 YAML 解析成值对象
再交给 domain 的纯函数），domain 因此保持为无 I/O 的叶子（Global Constraint #1），不会
隐式依赖磁盘上某个 YAML 是否存在。``DATA_DIR`` 取自 :mod:`app.refdata`（它取自
:mod:`app.config`），本模块只新增**处方侧那两个 YAML 的文件名**。

⚠️ **值对象不住在这里**（Plan02 账本 Ruling 96；Task 2 fix round 1 搬迁）：
:class:`~app.domain.prescription.exercises.ExerciseSpec` /
:class:`~app.domain.prescription.exercises.EquivalenceMapping` /
:class:`~app.domain.prescription.exercises.EquivalenceTable` 三个值对象，连同
``ImpactLevel`` 与三张词表（``IMPACT_RANK`` / ``TARGET_DOMAIN`` /
``EQUIVALENCE_TRIGGERS``），都住在 :mod:`app.domain.prescription.exercises`；本模块从
那里 import 它们，只负责**加载**。**为什么必须搬**：
:mod:`tests.architecture.test_domain_purity` 的 allow-list 只放行 6 个标准库模块串
（``dataclasses`` / ``enum`` / ``collections`` / ``collections.abc`` / ``numpy`` /
``typing``）与 ``app.domain`` 前缀，**不放行 domain → 非 domain 的 import**。值对象若住
在这里，Task 7 的 ``app/domain/prescription/safety.py`` 就拿不到这三个类型做标注，而
spec §7.4 的等价替换恰恰要调 ``EquivalenceTable.lookup()``。**分层照抄本仓既有先例**：
``StandardTable`` 这个值类型住 :mod:`app.domain.tables`，解析 CSV 的 ``load_standard()``
/ ``standard()`` 住 :mod:`app.refdata`（``app/refdata.py:29`` 写的是
``from app.domain.tables import StandardTable``）。

**代价要写明**（硬规矩 #39）：搬进 domain 之后，这些值对象从此受 **domain 分支覆盖
100%** 约束（Global Constraint #2），而 :meth:`~app.domain.prescription.exercises.EquivalenceTable.lookup`
的分支今天**全部由 ``tests/test_refdata_prescription.py`` 覆盖**——即一条 domain 代码的
覆盖率住在 domain 测试目录之外。删那条测试里的任何一个 ``lookup`` 断言，红的不是它自己，
是 ``--cov=app/domain --cov-branch`` 的 BrPart。

**本模块同时是 ``exercise`` 与 ``prescription_template`` 两张表的灌数据入口**
（:func:`sync_exercises` / :func:`sync_templates`）。它们刻意**不在**
``app/seed/``：Plan02 账本 P2-A1 的裁定（P3-A1 把同一条裁定传导到 Task 3），理由有三——
① Global Constraint #10 把 ``app/seed/`` 自 Plan 01 结案后重新冻结；② ``seed_database`` 的
docstring 明写它「**只**写组织结构五张表」，而 ``tests/seed/test_generate.py`` 的
``test_seed_database_writes_only_organisation_tables_and_is_idempotent`` 把这句话变成了守卫；
③ 这两张表都是**参考数据**、不是仿真人口数据，与 ``app/seed/`` 的职责本就不同类，它们的
同类是 :mod:`app.refdata`。
"""
import datetime as dt
import pathlib
import re
import types
from collections.abc import Mapping

import yaml
from sqlalchemy.orm import Session

from app import refdata_yaml
from app.db.models.prescription import Exercise, PrescriptionTemplate
from app.db.repo import upsert
from app.domain.prescription.exercises import (
    EQUIVALENCE_TRIGGERS,
    TARGET_DOMAIN,
    EquivalenceMapping,
    EquivalenceTable,
    ExerciseSpec,
    ImpactLevel,
)
from app.domain.prescription.templates import (
    ADDON_TRIGGERS,
    INTENSITY_TYPES,
    TEMPLATE_LAYERS,
    Addon,
    Block,
    BodyCompState,
    Intensity,
    Layer,
    ReviewStatus,
    Session as TemplateSession,
    Template,
    WeaknessBucket,
    is_reachable,
)
from app.refdata import DATA_DIR

#: 动作库的**源**（``exercise`` 表由它投影）。``exercise_ref`` 与每个动作的
#: ``impact_level`` 都以这份文件的键集/字段为**唯一所有者**（Global Constraint #3）。
EXERCISES_FILENAME = "exercises.yaml"

#: 低冲击等价动作映射 + 映射表版本号 + 跑量下调系数。spec §4.4 ``:243`` 明写它与
#: ``alert_rules`` 一样是「``data/`` 下的**静态 YAML + 版本号**，不入库」。
EQUIVALENCE_FILENAME = "exercise_equivalence.yaml"

#: 18 套处方模板的目录名（``DATA_DIR / PRESCRIPTION_DIRNAME``）。spec §7.2 ``:449``
#: 「每套模板一个文件，体育专家可独立审校」。
#: ⚠️ 与上面两个**文件名**常量不同，它是一个**目录名**：一文件一套，故 ``load_templates``
#: 的 ``path`` 参数收的是目录、不是文件。
#: ⚠️ 这个子目录的行尾属性由 ``.gitattributes`` 的 ``backend/data/**/*.yaml text eol=lf``
#: 单独钉住（Plan02 账本 P3-D2）：原有的 ``backend/data/*.yaml`` 那条的 ``*`` **不跨
#: ``/``**，盖不住子目录，于是 ``core.autocrlf=true`` 下一次 checkout 会把 18 份模板全部
#: 重写成 CRLF——那正是 Plan 01 国标评分表事故的原型（硬规矩 #46/#47）。守卫是
#: ``tests/domain/test_prescription_templates.py`` 的
#: ``test_every_template_yaml_is_lf_only_in_the_worktree``。
PRESCRIPTION_DIRNAME = "prescription"

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

_exercises_cache: Mapping[str, ExerciseSpec] | None = None
_equivalence_cache: EquivalenceTable | None = None


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

    ⚠️ 主语是**加载侧的四个函数**（``load_exercises`` / ``exercises`` / ``load_equivalence``
    / 本函数），不是本模块的全部公有函数——⚠️ **本处此前印的是「本模块公有函数是 5 个，
    第 5 个是 ``sync_exercises``」，那个 5 是 Plan 02 Task 3 的时点值、今天已过期**
    （Plan 03 Task 9 用 AST 实测更正：``ast.parse`` 本文件、数 ``tree.body`` 里
    ``FunctionDef`` 且名字不以下划线开头的，得 **8** 个 = 那 4 个加载侧 +
    ``sync_exercises`` + ``load_templates`` + ``templates`` + ``sync_templates``；
    后三个是 Plan 02 Task 3 建模板那一半时加的，加的时候没回来改这一句）。
    ⚠️ 而 fix round 3 补主语那一次的处置**仍然对**（「本 Task 的四个函数」在那个未言明的
    口径外读起来与实测矛盾），只是它写下的那个实测值绑错了时点。计划只点了加载侧
    那四个里的 ``load_exercises`` / ``exercises`` / ``load_equivalence`` 三个；补
    ``equivalence`` 是为了**对称**：Task 7 的安全后置是逐学生跑的，少了单例就会每人重解析
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

    **本函数 flush 但不 commit**：事务边界由调用方掌握。⚠️ 与 :func:`app.db.repo.upsert`
    **只在「不 commit」这半句同口径**（fix round 3 更正：此前印的「同一口径」在 flush 上恰好
    相反）——``app/db/repo.py`` 的 ``upsert`` docstring 逐字是「本函数**既不 commit 也不
    flush**：事务边界由调用方掌握」，即它连 flush 也不做；本函数按 ``ref`` 逐条调它，故在
    循环外统一 flush 一次。flush 是必要的——``impact_level`` 的 CHECK 约束与 ``ref`` 的 UNIQUE 约束
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


# ---------------------------------------------------------------------------
# Task 3：18 套处方模板（``data/prescription/*.yaml``）
# ---------------------------------------------------------------------------

#: 每套模板必需的顶层键，恰好这十二个（多一个少一个都在加载时响亮失败）。
#: 字面形状取自 spec §7.2 ``:453-485`` 的 YAML 骨架。
_TEMPLATE_KEYS = (
    "template_id", "version", "layer", "weakness", "body_comp", "reachable",
    "review", "microcycle_weeks", "weekly_frequency", "sessions", "progression",
    "addons",
)

#: ``review:`` 嵌套块的键（骨架 ``:460-463``）。:class:`Template` 把它**摊平**成
#: ``review_status`` / ``reviewer`` / ``reviewed_at`` 三个字段（Plan02 账本 P3-C3）。
_REVIEW_KEYS = ("status", "reviewer", "reviewed_at")

#: ``progression:`` 嵌套块的键（骨架 ``:478-479``），摊平成 ``week_deltas``。
_PROGRESSION_KEYS = ("week_deltas",)

_SESSION_KEYS = ("day", "focus", "blocks")
_BLOCK_KEYS = ("exercise_ref", "impact_level", "intensity", "structure")
_INTENSITY_KEYS = ("type", "low", "high", "value")
_ADDON_KEYS = ("when", "module")

#: ``template_id`` 的形状：``<层3>-<桶3>-<体成分3>-<序号2>``，共 **14** 字符。
#: 出处是 spec §7.2 ``:454`` 的骨架首行 ``template_id: RED-END-ABN-01``。
#: 收紧形状的理由与 ``_REF_SHAPE`` 相同（它是跨文件的引用键：文件名、``template_ref``
#: 列、Task 9 的 ``prescription.template_id`` 都按它引用），另加一条：它决定了
#: ``prescription_template.template_ref String(32)`` 的余量（18 字符），
#: 一个不受约束的 id 会把那个余量悄悄吃光（硬规矩 #18）。
_ID_SHAPE = re.compile(r"[A-Z]{3}-[A-Z]{3}-[A-Z]{3}-[0-9]{2}")

#: ``reviewed_at`` 的形状（ISO 8601 的日历日期）。⚠️ 只查形状、不查它是不是一个真日期：
#: ``2026-02-31`` 会通过本正则。真日期校验发生在落库那一步
#: （:func:`sync_templates` 的 ``dt.date.fromisoformat``，它会对 ``02-31`` 抛 ``ValueError``）。
#: **不在这里也校一次**是有意的：domain 侧的 allow-list 不放行 ``datetime``，而本模块
#: 若为了「早一点炸」把 ``fromisoformat`` 提前到加载期，就等于把落库语义抄进加载器
#: ——两个住址、迟早漂移（Global Constraint #3）。
_DATE_SHAPE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

#: 每层的 ``weekly_frequency``。spec §7.2 ``:465`` 的行内注释逐字：
#: 「红 4 / 黄 3 / 绿 2（指导文件原文）」。
#: ⚠️ **它是本模块私有的第二份**（测试侧另有一份字面量
#: ``tests/domain/test_prescription_templates.py::GUIDANCE_WEEKLY_FREQUENCY``），
#: 两侧刻意不同源（硬规矩 #35）：加载器这一份的职责是「专家把某一套的天数改错时在加载期
#: 就炸」，测试那一份的职责是「加载器这一份被改错时仍然有一侧钉着指导文件原文」。
_GUIDANCE_FREQUENCY = {Layer.RED: 4, Layer.YELLOW: 3, Layer.GREEN: 2}

#: ``Intensity.type`` 各自要求哪几个字段有值（四种组合互斥）。
#: ``hrmax_pct`` / ``onerm_pct`` 两行出自 spec §7.2 骨架 ``:472`` 与 ``:476`` 的字面形状；
#: ``rpe`` 与 ``none`` 的字段要求由本 Task 按同一逻辑推得（一个标量 / 无标量），
#: 今天 18 套模板里没有 ``rpe`` 的用例（指导文件没给 RPE 目标值），故那一行**不被真数据
#: 走过**——它是给 Plan 03 的预警侧留的位置（硬规矩 #39：写下能力就写明守不住什么）。
_INTENSITY_FIELDS = {
    "hrmax_pct": ("low", "high"),
    "onerm_pct": ("value",),
    "rpe": ("value",),
    "none": (),
}

_templates_cache: Mapping[str, Template] | None = None


#: 本模块加载的那些 YAML 的**文档种类**，绑进 :func:`app.refdata_yaml.fail` 的报错前缀。
#: ⚠️ 它此前是硬编码在 ``_fail`` 里的 ``f"处方模板 {path} …"``；Plan 03 Task 6 把那 6 个
#: 助手抽进 :mod:`app.refdata_yaml` 之后（P6-A2），前缀必须由**各消费者自己**说清，
#: 否则 ``alert_rules.yaml`` 被改坏时会报「处方模板 …/alert_rules.yaml 第 3 行」。
_DOC_KIND = "处方模板"

#: 行号索引不需要 ``doc_kind``，故直接别名引用**同一个函数对象**（不是副本）。
#: 守卫是 ``tests/test_refdata_alerts.py`` 的
#: ``test_line_index_is_the_same_object_in_every_consumer``（``is`` 比对）。
_line_index = refdata_yaml.line_index


def _fail(path, lines, key_path, message) -> ValueError:
    """**薄适配器**：转发给 :func:`app.refdata_yaml.fail` 并绑上本模块的 :data:`_DOC_KIND`。

    ⚠️ **本函数除本 docstring 外只许有那一句**：行号索引怎么用、查不到时怎么退到父路径、
    那一档的措辞是什么，全部住在 :mod:`app.refdata_yaml`；这里再写一遍就是第二个所有者
    （Global Constraint #3）。守卫是 ``tests/test_refdata_alerts.py`` 的
    ``test_every_consumer_binds_doc_kind_through_a_one_statement_adapter``
    （AST 数函数体长度 + 查那一句在调谁）。**保留适配器而不是逐点改 44 处调用**的理由见
    :mod:`app.refdata_yaml` 的模块 docstring（逐点改就是 44 次「有机会改坏一条被测试逐字
    钉住的报错文本」的机会）。

    ``key_path`` / ``lines`` / ``message`` 三个参数的语义逐字见
    :func:`app.refdata_yaml.fail`。
    """
    return refdata_yaml.fail(path, lines, key_path, message, doc_kind=_DOC_KIND)


def _exact_keys(path, lines, where, raw, required, label) -> None:
    """薄适配器；理由与「只许一句」的守卫逐字见 :func:`_fail` 的 docstring。"""
    refdata_yaml.exact_keys(path, lines, where, raw, required, label,
                            doc_kind=_DOC_KIND)


def _as_int(path, lines, where, raw, label) -> int:
    """薄适配器；理由与「只许一句」的守卫逐字见 :func:`_fail` 的 docstring。"""
    return refdata_yaml.as_int(path, lines, where, raw, label, doc_kind=_DOC_KIND)


def _as_float(path, lines, where, raw, label) -> float:
    """薄适配器；理由与「只许一句」的守卫逐字见 :func:`_fail` 的 docstring。"""
    return refdata_yaml.as_float(path, lines, where, raw, label, doc_kind=_DOC_KIND)


def _as_optional_text(path, lines, where, raw, label) -> str | None:
    """薄适配器；理由与「只许一句」的守卫逐字见 :func:`_fail` 的 docstring。"""
    return refdata_yaml.as_optional_text(path, lines, where, raw, label,
                                         doc_kind=_DOC_KIND)


def _intensity(path, lines, where, raw) -> Intensity:
    """校验并构造一个 :class:`Intensity`。

    ``type`` 决定哪几个字段**必须**有值、哪几个**必须**没有（见 :data:`_INTENSITY_FIELDS`）。
    **两个方向都要校验**：只查「该有的有」的话，``{type: hrmax_pct, low: 60, high: 70,
    value: 70}`` 会被照收，而 Task 5 拿它算心率区间时 ``value`` 与 ``low/high`` 谁优先
    就成了一个没有答案的问题。

    ⚠️ **键集这里刻意不用 :func:`_exact_keys` 的「恰好」语义**：``type`` 必填，而
    ``low`` / ``high`` / ``value`` 三个按 ``type`` 决定要不要写（``{type: none}`` 就该只有
    一个键）。故本函数自己查两件事——``type`` 在、且不许有 ``_INTENSITY_KEYS`` 之外的
    第五个键——再逐 ``type`` 查「该有的有、不该有的没有」。
    """
    if not isinstance(raw, dict):
        raise _fail(
            path, lines, where,
            f"intensity 应为「属性名 → 值」的映射（spec §7.2 :472 的字面形状是流式映射"
            f"``{{type: hrmax_pct, low: 60, high: 70}}``），实为 {type(raw).__name__}"
        )
    if "type" not in raw:
        raise _fail(
            path, lines, where,
            f"intensity 缺键 ['type']；它必填，另三个键（low / high / value）按 type 决定"
        )
    unexpected = sorted(set(raw) - set(_INTENSITY_KEYS))
    if unexpected:
        raise _fail(
            path, lines, where,
            f"intensity 有多余的键 {unexpected}；合法的键恰好是 {list(_INTENSITY_KEYS)}"
        )
    kind = raw["type"]
    if kind not in INTENSITY_TYPES:
        raise _fail(
            path, lines, where + ("type",),
            f"intensity.type 值非法: {kind!r}；合法值: {sorted(INTENSITY_TYPES)}"
            f"（spec §7.2 :472/:476 给了前两个，rpe 与 spec §8.2 的课堂快评同一套语义，"
            f"none 表示指导文件未给这一层的强度参数）"
        )
    required = _INTENSITY_FIELDS[kind]
    forbidden = tuple(k for k in ("low", "high", "value") if k not in required)
    values: dict[str, float | None] = {"low": None, "high": None, "value": None}
    for field in required:
        if raw.get(field) is None:
            raise _fail(
                path, lines, where + (field,),
                f"intensity.type 是 {kind!r}，故 {field} 必填且必须是数字，"
                f"实为 {raw.get(field)!r}"
            )
        values[field] = _as_float(path, lines, where + (field,), raw[field], f"intensity.{field}")
    for field in forbidden:
        if raw.get(field) is not None:
            raise _fail(
                path, lines, where + (field,),
                f"intensity.type 是 {kind!r}，它只用 {list(required) or '（不用任何数值）'}，"
                f"故 {field} 必须省略或为 null，实为 {raw[field]!r}——留着它会让"
                f"Task 5 面对「两套强度参数谁优先」这个没有答案的问题"
            )
    if kind == "hrmax_pct" and values["low"] >= values["high"]:
        raise _fail(
            path, lines, where,
            f"intensity 的 low ({values['low']}) 应严格小于 high ({values['high']})："
            f"一个空区间或反区间会让 Task 5 装配出一个谁也落不进去的目标心率区间"
        )
    return Intensity(type=kind, **values)


def _block(path, lines, where, raw, library) -> Block:
    """校验并构造一个 :class:`Block`，含两道**跨文件**校验（P2-B2 / Review Focus 第 1 条）。"""
    _exact_keys(path, lines, where, raw, _BLOCK_KEYS, "block")
    ref = raw["exercise_ref"]
    if not isinstance(ref, str) or _REF_SHAPE.fullmatch(ref) is None:
        raise _fail(
            path, lines, where + ("exercise_ref",),
            f"exercise_ref {ref!r} 形状非法：只允许小写字母开头、后续为小写字母/数字/下划线"
            f"（正则 {_REF_SHAPE.pattern}，与动作库的键同一形状）"
        )
    if ref not in library:
        raise _fail(
            path, lines, where + ("exercise_ref",),
            f"exercise_ref {ref!r} 在动作库里不存在（``exercises.yaml`` 的 "
            f"{len(library)} 个键里没有它）。不校验的话这里不会炸，Task 6 装配第 5 步从 "
            f"``exercise`` 表取视频 URL（spec §7.3 :499）时才会炸——报错点在管道深处、"
            f"离真因隔三层"
        )
    declared = raw["impact_level"]
    actual = library[ref].impact_level
    try:
        declared_level = ImpactLevel(declared) if isinstance(declared, str) else None
    except ValueError:
        declared_level = None
    if declared_level is not actual:
        raise _fail(
            path, lines, where + ("impact_level",),
            f"exercise_ref {ref!r} 的 impact_level 写的是 {declared!r}，而动作库"
            f"（唯一所有者，Plan02 账本 P2-B2）里是 {actual.value!r}。两份必须逐字相同"
            f"（合法值只有 {[level.value for level in ImpactLevel]}）："
            f"spec §7.4 :508 的安全后置只替换 impact_level: high，写低了它就不会去等价表"
            f"找替身，BMI > 30 的学生照旧被安排高冲击动作，而全链路没有一处报错"
        )
    return Block(
        exercise_ref=ref,
        impact_level=actual,
        intensity=_intensity(path, lines, where + ("intensity",), raw["intensity"]),
        structure=_structure(path, lines, where + ("structure",), raw["structure"]),
    )


def _structure(path, lines, where, raw) -> Mapping[str, object]:
    """校验 ``structure`` 并返回**只读**视图。

    ⚠️ **键集不受约束**（硬规矩 #39）：spec 只给了两个字面例子（``:473`` 的
    ``{sets: 4, work_min: 3, rest_min: 2}`` 与 ``:477`` 的 ``{rounds: 3, reps: 10}``），
    **没有**给键的词表，故本 Task 不编一个。只查两件事：它是个非空映射、且键都是字符串
    （Task 6 的装配器要按键取值，一个整数键会让它在两份模板上走不同分支）。
    """
    if not isinstance(raw, dict) or not raw:
        raise _fail(
            path, lines, where,
            f"structure 应为**非空**映射（训练量住在这里：组数/次数/时长/间歇），"
            f"实为 {raw!r}"
        )
    bad = [key for key in raw if not isinstance(key, str)]
    if bad:
        raise _fail(
            path, lines, where,
            f"structure 的键应全是字符串，实有 {bad}（{[type(k).__name__ for k in bad]}）"
        )
    return types.MappingProxyType(dict(raw))


def _session(path, lines, where, raw, library) -> TemplateSession:
    """校验并构造一个 :class:`Session`（``day`` 的连续性由调用方按整套查）。"""
    _exact_keys(path, lines, where, raw, _SESSION_KEYS, "session")
    day = _as_int(path, lines, where + ("day",), raw["day"], "session.day")
    focus = raw["focus"]
    if not isinstance(focus, str) or not focus.strip():
        raise _fail(
            path, lines, where + ("focus",),
            f"session.focus 应为非空字符串（学生端「本周训练单」要显示它，spec §8.4），"
            f"实为 {focus!r}"
        )
    blocks_raw = raw["blocks"]
    if not isinstance(blocks_raw, list) or not blocks_raw:
        raise _fail(
            path, lines, where + ("blocks",),
            f"session.blocks 应为**非空**列表（一个训练日至少要有一个训练块），"
            f"实为 {blocks_raw!r}"
        )
    return TemplateSession(
        day=day,
        focus=focus,
        blocks=tuple(
            _block(path, lines, where + ("blocks", position), item, library)
            for position, item in enumerate(blocks_raw)
        ),
    )


def _addon(path, lines, where, raw, library) -> Addon:
    """校验并构造一个 :class:`Addon`（``module`` 也是一个 ``exercise_ref``）。"""
    _exact_keys(path, lines, where, raw, _ADDON_KEYS, "addon")
    when = raw["when"]
    if when not in ADDON_TRIGGERS:
        raise _fail(
            path, lines, where + ("when",),
            f"addon.when 值非法: {when!r}；合法值: {sorted(ADDON_TRIGGERS)}"
            f"（spec §7.2 :481/:483）。⚠️ 别与等价表的 when 混起来：那张表的取值域是 "
            f"{sorted(EQUIVALENCE_TRIGGERS)}，走的是 spec §7.4 :508-509 的两个触发；"
            f"addon 走的是 :510 的「体脂率异常 → 追加能量消耗模块」、**不查等价表**"
        )
    module = raw["module"]
    if not isinstance(module, str) or module not in library:
        raise _fail(
            path, lines, where + ("module",),
            f"addon.module {module!r} 在动作库里不存在：它是一个 exercise_ref"
            f"（spec §7.2 :482/:484 的字面值 ``energy_expenditure_plus_10pct`` 与 "
            f"``resistance_priority`` 都是动作库的键）"
        )
    return Addon(when=when, module=module)


def _review(path, lines, raw) -> tuple[ReviewStatus, str | None, str | None]:
    """校验 ``review:`` 嵌套块并**摊平**成三个值（Plan02 账本 P3-C3）。

    ⚠️ **缺块不能是 ``KeyError``**：``Template`` 把 ``review`` 摊平成
    ``review_status`` / ``reviewer`` / ``reviewed_at``，于是朴素实现会写
    ``raw["review"]["status"]``——专家删掉整个 ``review:`` 块时那是一次
    ``KeyError: 'review'``，它点不出文件、也说不出是三个字段里的哪一层。
    """
    _exact_keys(path, lines, ("review",), raw, _REVIEW_KEYS, "review 嵌套块")
    status = raw["status"]
    try:
        review_status = ReviewStatus(status)
    except (ValueError, TypeError):
        raise _fail(
            path, lines, ("review", "status"),
            f"review.status 值非法: {status!r}；合法值: "
            f"{[member.value for member in ReviewStatus]}（spec §4.4 :238）。"
            f"⚠️ 一个词表外的值不会被 spec §7.2 :451 的「!= approved 就拒绝用于生成」"
            f"当成 pending——它会被当成「既不是 pending 也不是 approved」的第四态，"
            f"而 Task 4 的匹配器只认前两个"
        ) from None
    reviewer = _as_optional_text(path, lines, ("review", "reviewer"),
                                 raw["reviewer"], "review.reviewer")
    reviewed_at = raw["reviewed_at"]
    if reviewed_at is not None:
        if not isinstance(reviewed_at, str) or _DATE_SHAPE.fullmatch(reviewed_at) is None:
            raise _fail(
                path, lines, ("review", "reviewed_at"),
                f"review.reviewed_at 应为 ISO 8601 的日历日期字符串（``YYYY-MM-DD``）或 "
                f"null，实为 {type(reviewed_at).__name__} 的 {reviewed_at!r}。"
                f"⚠️ YAML 里**不加引号**的 ``2026-10-06`` 会被 PyYAML 解析成 "
                f"``datetime.date`` 而不是字符串——那会让 domain 侧的 "
                f"``Template.reviewed_at`` 类型随引号漂（``app/domain/`` 的 allow-list "
                f"不放行 ``datetime``），故 18 份模板一律加引号"
            )
    return review_status, reviewer, reviewed_at


def _week_deltas(path, lines, raw, microcycle_weeks: int) -> tuple[float, ...]:
    """校验 ``progression:`` 嵌套块并**摊平**成 ``week_deltas``（Plan02 账本 P3-C3）。

    三条校验，出处分别是：
    * **长度 == ``microcycle_weeks``** —— spec §7.2 ``:464`` 的 ``microcycle_weeks: 4`` 与
      ``:479`` 的 4 项 ``[1.00, 1.05, 1.10, 0.85]``。长度不符是**静默失效**：Task 6 按周
      取系数（spec §7.3 ``:498``），3 项配 4 周时「容错」写法会让第 4 周悄悄回到第 3 周的量，
      恰好在最该减量的那一周加量。
    * **末项 < 1.0** —— ``:479`` 的行内注释逐字「第 4 周减量，超量恢复」。
    * **其余各项 >= 1.0** —— 同上：微周期的前几周是递增负荷，一个 < 1.0 的中间项意味着
      「减量周」出现了两次，而超量恢复的前提是只有一次。
    """
    _exact_keys(path, lines, ("progression",), raw, _PROGRESSION_KEYS, "progression 嵌套块")
    raw_deltas = raw["week_deltas"]
    if not isinstance(raw_deltas, list) or not raw_deltas:
        raise _fail(
            path, lines, ("progression", "week_deltas"),
            f"progression.week_deltas 应为**非空**列表，实为 {raw_deltas!r}"
        )
    deltas = tuple(
        _as_float(path, lines, ("progression", "week_deltas", position), item,
                  f"week_deltas[{position}]")
        for position, item in enumerate(raw_deltas)
    )
    if len(deltas) != microcycle_weeks:
        raise _fail(
            path, lines, ("progression", "week_deltas"),
            f"week_deltas 有 {len(deltas)} 项，而 microcycle_weeks 是 {microcycle_weeks}"
            f"——两者必须相等，否则 Task 6 按周取系数时最后一周会取不到值"
            f"（spec §7.2 :464 与 :479）"
        )
    if deltas[-1] >= 1.0:
        raise _fail(
            path, lines, ("progression", "week_deltas", len(deltas) - 1),
            f"week_deltas 的末项是 {deltas[-1]}，应 < 1.0：spec §7.2 :479 的行内注释是"
            f"「第 4 周减量，超量恢复」，末项不减量就没有超量恢复"
        )
    ramping = [(position, delta) for position, delta in enumerate(deltas[:-1], 1) if delta < 1.0]
    if ramping:
        raise _fail(
            path, lines, ("progression", "week_deltas"),
            f"week_deltas 的前 {len(deltas) - 1} 项应各自 >= 1.0（递增负荷），"
            f"实有 {ramping}——中间再插一个减量周会让「减量」出现两次"
        )
    return deltas


def _template(path: pathlib.Path, library: Mapping[str, ExerciseSpec]) -> Template:
    """校验并构造一套 :class:`Template`，违例带**文件名 + 行号**响亮失败。

    校验顺序是「**先形状、后语义、跨文件最后**」：形状错（缺键、类型不对）会让后面的语义
    校验拿不到值，跨文件校验（``exercise_ref`` / ``impact_level`` / addon ``module``）
    要逐 block 走，放最后可以让「一份模板同时有多处坏」时报的是**最靠前的那一处**，
    而不是一个深埋在 block 里的错。
    """
    text = path.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        # PyYAML 的 mark 里有行列、但**没有文件名**（喂给它的是字符串而不是文件对象），
        # 且 YAMLError 不是 ValueError 的子类。包一层让调用方只需认一种异常类型。
        raise ValueError(f"处方模板 {path} 不是合法的 YAML：{exc}") from exc
    lines = _line_index(text)

    if raw is None:
        raise _fail(path, lines, (), "文件为空：一套模板都没有内容")
    _exact_keys(path, lines, (), raw, _TEMPLATE_KEYS, "模板顶层")

    template_id = raw["template_id"]
    if not isinstance(template_id, str) or _ID_SHAPE.fullmatch(template_id) is None:
        raise _fail(
            path, lines, ("template_id",),
            f"template_id {template_id!r} 形状非法：应为 <层3>-<桶3>-<体成分3>-<序号2>"
            f"（正则 {_ID_SHAPE.pattern}，共 14 字符），照 spec §7.2 :454 的骨架首行"
            f" ``RED-END-ABN-01``"
        )
    if template_id != path.stem:
        raise _fail(
            path, lines, ("template_id",),
            f"template_id 是 {template_id!r}，而文件名是 {path.name!r}——两者必须同名，"
            f"否则「文件 ↔ 模板」需要第二张对照表（多一张表就是多一个所有者，"
            f"Global Constraint #3），且报错里的文件名与专家手里的文件名对不上"
        )

    version = raw["version"]
    if not isinstance(version, str) or not version.strip():
        raise _fail(
            path, lines, ("version",),
            f"version 应为非空字符串，实为 {type(version).__name__} 的 {version!r}。"
            f"⚠️ YAML 里**不加引号**的 ``1.0`` 会被 PyYAML 解析成 float，而 ``1.10`` 会"
            f"变成 ``1.1``——版本号静默变形，故 18 份模板一律加引号"
            f"（口径同 ``exercise_equivalence.yaml`` 的 ``version: \"1.0\"``）"
        )

    layer_raw = raw["layer"]
    try:
        layer = Layer(layer_raw)
    except (ValueError, TypeError):
        raise _fail(
            path, lines, ("layer",),
            f"layer 值非法: {layer_raw!r}；合法值: "
            f"{[member.value for member in Layer]}（spec §7.2 :456）"
        ) from None
    if layer not in TEMPLATE_LAYERS:
        raise _fail(
            path, lines, ("layer",),
            f"layer 是 {layer.value!r}，它**不是合法的模板层**：合法值只有 "
            f"{sorted(member.value for member in TEMPLATE_LAYERS)}。"
            f"``insufficient_data`` 是 spec §6.1 Z0 闸门（valid_count < 4）的产物，"
            f"那一档**不产出分层标签**，故没有任何学生会带着它来匹配模板；"
            f"以它为层的模板行会被 DB 的 CHECK 拒收，也会被 Task 4 的匹配器永远查不到"
        )
    try:
        weakness = WeaknessBucket(raw["weakness"])
    except (ValueError, TypeError):
        raise _fail(
            path, lines, ("weakness",),
            f"weakness 值非法: {raw['weakness']!r}；合法值: "
            f"{[member.value for member in WeaknessBucket]}（spec §7.2 :457）。"
            f"⚠️ ``bmi`` 不是桶名（Plan02 账本 P2-A4）"
        ) from None
    try:
        body_comp = BodyCompState(raw["body_comp"])
    except (ValueError, TypeError):
        raise _fail(
            path, lines, ("body_comp",),
            f"body_comp 值非法: {raw['body_comp']!r}；合法值: "
            f"{[member.value for member in BodyCompState]}（spec §7.2 :458）"
        ) from None

    reachable = raw["reachable"]
    if not isinstance(reachable, bool):
        raise _fail(
            path, lines, ("reachable",),
            f"reachable 应为布尔值（spec §7.1 :447 的 ``reachable: false``），"
            f"实为 {type(reachable).__name__} 的 {reachable!r}"
        )
    expected_reachable = is_reachable(layer, body_comp)
    if reachable is not expected_reachable:
        raise _fail(
            path, lines, ("reachable",),
            f"reachable 写的是 {reachable}，而 (layer={layer.value}, "
            f"body_comp={body_comp.value}) 这一格按 "
            f"app.domain.prescription.templates.is_reachable 是 {expected_reachable}"
            f"——两者矛盾（Review Focus 第 1 条点名的坏形状）。规则的唯一所有者是那个"
            f"函数（出处 spec §7.1 :445「绿色层必然 NOT C，故 (green, *, abnormal) 3 套"
            f"当前不可达」）；分层规则若真的调整，**改那个函数**，只翻 YAML 里这一行"
            f"是不够的——一条规则两个住址必然漂移（Global Constraint #3）"
        )

    review_status, reviewer, reviewed_at = _review(path, lines, raw["review"])

    microcycle_weeks = _as_int(path, lines, ("microcycle_weeks",),
                               raw["microcycle_weeks"], "microcycle_weeks")
    if microcycle_weeks < 1:
        raise _fail(
            path, lines, ("microcycle_weeks",),
            f"microcycle_weeks 应 >= 1，实为 {microcycle_weeks}"
        )
    weekly_frequency = _as_int(path, lines, ("weekly_frequency",),
                               raw["weekly_frequency"], "weekly_frequency")
    expected_frequency = _GUIDANCE_FREQUENCY[layer]
    if weekly_frequency != expected_frequency:
        raise _fail(
            path, lines, ("weekly_frequency",),
            f"weekly_frequency 是 {weekly_frequency}，而 {layer.value} 层按指导文件应是 "
            f"{expected_frequency}（spec §7.2 :465 的行内注释逐字：「红 4 / 黄 3 / 绿 2"
            f"（指导文件原文）」）"
        )

    sessions_raw = raw["sessions"]
    if not isinstance(sessions_raw, list) or not sessions_raw:
        raise _fail(
            path, lines, ("sessions",),
            f"sessions 应为**非空**列表（每套模板的天数 = weekly_frequency = "
            f"{weekly_frequency}），实为 {sessions_raw!r}"
        )
    if len(sessions_raw) != weekly_frequency:
        raise _fail(
            path, lines, ("sessions",),
            f"sessions 有 {len(sessions_raw)} 项，而 weekly_frequency 是 "
            f"{weekly_frequency}——每套模板的天数就是它的周频次（简报 Step 2-5）"
        )
    sessions = tuple(
        _session(path, lines, ("sessions", position), item, library)
        for position, item in enumerate(sessions_raw)
    )
    days = [session.day for session in sessions]
    if days != list(range(1, len(sessions) + 1)):
        raise _fail(
            path, lines, ("sessions",),
            f"sessions 的 day 应从 1 连续递增到 {len(sessions)}，实为 {days}"
            f"——跳号会让「第 N 天该不该打卡」没有答案（打卡完成率按处方训练日计，"
            f"spec §14 第 9 项）"
        )

    week_deltas = _week_deltas(path, lines, raw["progression"], microcycle_weeks)

    addons_raw = raw["addons"]
    if not isinstance(addons_raw, list):
        raise _fail(
            path, lines, ("addons",),
            f"addons 应为列表（**可以是空列表**：指导文件没给绿层附加模块，故绿层 6 套"
            f"写 ``addons: []``），实为 {type(addons_raw).__name__}"
        )
    addons = tuple(
        _addon(path, lines, ("addons", position), item, library)
        for position, item in enumerate(addons_raw)
    )

    return Template(
        template_id=template_id,
        version=version,
        layer=layer,
        weakness=weakness,
        body_comp=body_comp,
        reachable=reachable,
        review_status=review_status,
        reviewer=reviewer,
        reviewed_at=reviewed_at,
        microcycle_weeks=microcycle_weeks,
        weekly_frequency=weekly_frequency,
        sessions=sessions,
        week_deltas=week_deltas,
        addons=addons,
    )


def load_templates(directory: pathlib.Path | None = None) -> Mapping[str, Template]:
    """读取 ``data/prescription/*.yaml`` 并构造「``template_id`` → :class:`Template`」的只读映射。

    **一文件一套**（spec §7.2 ``:449``「每套模板一个文件，体育专家可独立审校」），故
    ``directory`` 收的是**目录**、不是文件（与 :func:`load_exercises` 收文件不同）。
    遍历序取 ``sorted(glob)``：字典序，故「同一份输入 → 同一个映射」与文件系统无关，
    重复 id 的报错也总是点名同一对文件（可复现，spec §1.3）。

    ⚠️ **重复的 ``template_id`` 必须响亮失败**：这是 ``exercises.yaml`` 那个失效形态
    （PyYAML 对重复顶层键后者覆盖前者、不报错）的模板侧版本——本函数自己建字典，两个文件
    同 id 就是一次静默覆盖，18 套里少一套而没有人知道。守卫是
    ``test_loader_rejects_a_second_template_reusing_an_id``。

    ⚠️ **本函数不做「18 套是否恰好覆盖全矩阵」的校验**（硬规矩 #39）：那是一条**策略**
    （spec §7.1 ``:443`` 的 3×3×2），不是形状不变量，把它写进加载器会让「加第 19 套」
    与「专家改坏一套」报同一种错。它由
    ``tests/domain/test_prescription_templates.py::test_exactly_eighteen_templates_cover_the_full_matrix``
    按**字面写死**的 18 个 id 守（硬规矩 #35）。同理，每层的 ``weekly_frequency`` 与
    addons 的层归属也在测试侧另有一份字面量（见 :data:`_GUIDANCE_FREQUENCY` 的注释）。

    返回 :class:`types.MappingProxyType`，理由与 :func:`load_exercises` 完全相同：
    ``frozen=True`` 只挡住换掉整个字段，挡不住 ``store[id] = ...`` 的就地改写，而
    :func:`templates` 是进程内共享单例，一次误写会让之后所有匹配静默变质。
    每个 :class:`Block` 的 ``structure`` 也是只读视图（同一理由）。
    """
    folder = DATA_DIR / PRESCRIPTION_DIRNAME if directory is None else pathlib.Path(directory)
    if not folder.is_dir():
        raise FileNotFoundError(f"处方模板目录缺失: {folder}")
    paths = sorted(folder.glob("*.yaml"))
    if not paths:
        raise ValueError(
            f"处方模板目录 {folder} 里一个 .yaml 都没有：Task 4 的匹配器会对每个学生返回"
            f"「无模板」，于是 500 人一个处方都不生成、而管道全绿——那正是 Review Focus "
            f"第 3 条要防的静默跳过，故这里必须响亮失败"
        )
    library = exercises()
    store: dict[str, Template] = {}
    origin: dict[str, pathlib.Path] = {}
    for path in paths:
        template = _template(path, library)
        if template.template_id in store:
            raise ValueError(
                f"处方模板 {path}：template_id {template.template_id!r} 与 "
                f"{origin[template.template_id]} 重复。一文件一套，故 id 必须唯一——"
                f"否则后读到的那份会静默覆盖先读到的，18 套里少一套而没有人知道"
                f"（与 exercises.yaml 的重复顶层键同一失效形态）"
            )
        store[template.template_id] = template
        origin[template.template_id] = path
    return types.MappingProxyType(store)


def templates() -> Mapping[str, Template]:
    """进程内单例：18 套模板是只读参考数据，一个进程加载一次即可。

    与 :func:`exercises` / :func:`equivalence` 同口径（Plan02 账本 P2-A9：``load_*`` 只负责
    加载、**不缓存**，单例是另一个函数）。

    **单例同时是 spec §1.3 的 p95 < 3 秒预算的前提**：Task 4 的匹配是逐学生跑的，少了单例
    就会每人重解析 18 份 YAML——而每份还要跑一次 ``yaml.compose`` 建行号索引
    （见 :func:`_line_index`），即每份解析两遍。
    """
    global _templates_cache
    if _templates_cache is None:
        _templates_cache = load_templates()
    return _templates_cache


def sync_templates(session: Session) -> int:
    """把 18 套模板投影进 ``prescription_template`` 表，返回写入的行数（幂等）。

    与 :func:`sync_exercises` 同口径，包括三件事：① 按 ``template_ref`` 走
    :func:`app.db.repo.upsert`，故**重跑不翻倍**、且 YAML 改了某个字段时那一行被**就地
    更新**；② 返回值的口径是「本次 upsert 触及的行数」而不是「新插入的行数」，于是首次
    灌库与重跑给出同一个数；③ **flush 但不 commit**，事务边界由调用方掌握。
    三条的理由逐字见 :func:`sync_exercises` 的 docstring（含它与 ``repo.upsert``
    「只在『不 commit』这半句同口径」的那个更正）。

    ⚠️ **它是全模块唯一一处 ``str`` → ``datetime.date`` 的转换**：``reviewed_at`` 在 domain
    侧是 ISO 字符串（``app/domain/`` 的 allow-list 不放行 ``datetime``，理由见
    ``app/domain/prescription/templates.py`` 的模块 docstring），而
    ``prescription_template.reviewed_at`` 那一列是 ``Date``。转换放这里是**边界**的正确
    位置：加载器已经用 ``_DATE_SHAPE`` 查过形状，故 ``fromisoformat`` 只可能在一个
    「形状对但不是真日期」的值上炸（``2026-02-31``），而那一炸正是它该炸的地方。

    ⚠️ **它不删除 YAML 里已经不存在的行**（硬规矩 #39，与 :func:`sync_exercises` 同）：
    从 ``data/prescription/`` 里删掉一个文件，``sync_templates`` 之后那一行仍在表中。
    这是刻意的——Task 9 的 ``prescription`` 会按 ``template_ref`` 引用历史处方用过的模板，
    删行会让已生成的处方指向一个查不到的模板。真要下线一套模板是一次需要人工确认的迁移。

    ⚠️ **谁在生产路径上调用它，本 Task 没有决定**（同 :func:`sync_exercises`）：P3-A1
    明确禁止把它接进 ``seed_database``（那会撞上「只写组织结构五张表」的守卫），故今天它
    只有测试这一个调用方。接进管道是 Task 9/10 的活。
    """
    store = templates()
    for template in store.values():
        upsert(
            session,
            PrescriptionTemplate,
            ("template_ref",),
            {
                "layer": template.layer.value,
                "weakness": template.weakness.value,
                "body_comp": template.body_comp.value,
                "template_ref": template.template_id,
                "version": template.version,
                "review_status": template.review_status.value,
                "reviewer": template.reviewer,
                "reviewed_at": (
                    None
                    if template.reviewed_at is None
                    else dt.date.fromisoformat(template.reviewed_at)
                ),
                "reachable": template.reachable,
            },
        )
    session.flush()
    return len(store)

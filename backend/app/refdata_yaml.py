"""``backend/data/`` 下 YAML 参考数据的**共用校验与报错助手**（Plan 03 Task 6 抽取，P6-A2）。

**为什么有这个模块**：Plan 02 Task 3 给 :mod:`app.refdata_prescription` 写了一套
「YAML 被专家改坏时在**加载期**响亮失败、并点名**文件名 + 行号 + 键路径**」的机制
（:func:`line_index` / :func:`fail` / :func:`exact_keys` / :func:`as_int` /
:func:`as_float` / :func:`as_optional_text`）。Plan 03 Task 6 要给
``data/alert_rules.yaml`` 写第二个加载器（:mod:`app.refdata_alerts`），而计划正文给的
处置是「**直接照抄那套形状**，不要另发明一套」——⚠️ **「照抄」在字面上等于复制，而复制
就是第二个所有者**（Global Constraint #3：任何常量/词表/阈值只允许有一个住址）。故把
通用的那 6 个搬进本模块，两个加载器都从这里 import。

**搬家时改了两件事**（两件都不是可选的）：

1. **去掉前导下划线**：它们在 :mod:`app.refdata_prescription` 里是私有的，跨模块之后
   就是公开 API，留着一个下划线会让「它是给外人用的」这件事读不出来。
2. **多出一个 ``doc_kind`` 参数**（⚠️ **计划的 P6-A2 没提这一条，而不加就是错的**）：
   原来 ``_fail`` 的消息前缀是**硬编码**的 ``f"处方模板 {path} {where}：{message}"``。
   原样搬过来的话，:mod:`app.refdata_alerts` 报出来的会是
   「处方模板 …/data/alert_rules.yaml 第 3 行：…」——指着一份预警阈值文件说它是处方模板。
   Review Focus 第 5 条要的正是「必须在加载时响亮失败**并指出是哪个键**」，一个说错文件
   种类的前缀会让那句话变成假话。故 ``doc_kind`` 是**必填的关键字参数、没有缺省值**：
   带缺省值的前缀会让「忘了传」静默退化成另一种文档的措辞，而那恰好是本模块要消灭的
   那一类静默失效。

**两个消费者各自绑自己的 ``doc_kind``**：:mod:`app.refdata_prescription` 与
:mod:`app.refdata_alerts` 都保留 5 个**薄适配器**（``_fail`` / ``_exact_keys`` /
``_as_int`` / ``_as_float`` / ``_as_optional_text``），每个的函数体只有一句
「转发 + 绑 ``doc_kind``」；:func:`line_index` 不需要 ``doc_kind``，故两处直接别名引用
同一个函数对象。

⚠️ **薄适配器不是第二个所有者**：判据、行号索引的构造、「缺失的键退到父路径」的措辞、
``bool`` 的排除、``int`` → ``float`` 的收敛，全部只有本模块一份；适配器绑的是**每份
文件自己的文档种类**，那本来就是各加载器的知识（一个加载器只知道自己在读什么）。
保留适配器而不是逐点改调用的理由是可读性与改动面：:mod:`app.refdata_prescription` 里
这 6 个名字共有 **57** 处调用点（AST 实测 ``ast.Call`` 计数：``_fail`` 44 +
``_exact_keys`` 6 + ``_as_int`` 3 + ``_as_float`` 2 + ``_as_optional_text`` 1 +
``_line_index`` 1），逐点加一个关键字参数就是 57 次「有机会改坏一条被测试逐字钉住的
报错文本」的机会（``tests/domain/test_prescription_templates.py`` 里有两条
``pytest.raises(..., match="处方模板")``）。

**单一所有者由机器守，不靠散文**：``tests/test_refdata_alerts.py`` 的
``test_the_six_shared_yaml_helpers_have_exactly_one_definition_site`` 用 AST 扫
``backend/app/`` 下全部 ``.py``，要求这 6 个名字**各只有一处** ``def``、且那一处在本文件里
（硬规矩 #89 的再扩写：数「一个名字有几份定义」用 AST，不用正则数源码）。谁再复制一份
到某个加载器里，那条当场红。

依赖方向：本模块只 import :mod:`pathlib` 与 :mod:`yaml`，**不 import ``app`` 里的任何
东西**，故它不可能造出环（与 :mod:`app.config` 同档，后者只 import :mod:`pathlib`）。
⚠️ 它在 ``app/`` 根下，**不在** ``tests/architecture/test_layering.py`` 的
:data:`~tests.architecture.test_layering.SCANNED_DIRS`（``("pipeline", "db", "domain",
"api")``）任何一项里，故架构守卫不扫它、**扫描面也不因它而涨**——与 ``app/main.py`` /
``app/config.py`` / ``app/refdata.py`` / ``app/refdata_prescription.py`` 同档。

⚠️ **本模块守不住什么**（硬规矩 #39）：它只提供**报错的形状**，不提供任何一份 YAML 的
键集或取值域——那些住在各加载器里（``_TEMPLATE_KEYS`` / ``_RULE_KEYS`` …）。它也不做
跨文件校验（``exercise_ref`` 是否在动作库里一类），理由逐字写在
:func:`app.refdata_prescription.load_equivalence` 的 docstring 里。
"""
import pathlib

import yaml

__all__ = [
    "line_index",
    "fail",
    "exact_keys",
    "as_int",
    "as_float",
    "as_optional_text",
]


def line_index(text: str) -> dict[tuple, int]:
    """把一份 YAML 折成「键路径 → **1 基**行号」的索引，供报错点名行号用。

    ``yaml.safe_load`` **不保留位置信息**，故另跑一次 :func:`yaml.compose` 拿节点树、
    从每个节点的 ``start_mark`` 取行号。键路径的元素是**映射的键**（``str``）与
    **列表的下标**（``int``），例如 ``("sessions", 0, "blocks", 1, "exercise_ref")``。

    **映射的每一项记的是「键所在行」而不是「值所在行」**：``review:`` 与它下面缩进的
    ``status: pending`` 不在同一行，专家要改的是 ``review:`` 那一块，报键所在行更好定位。
    实现上靠 ``setdefault``：父节点先写 ``index[child] = 键行``，再递归进值节点，
    值节点的 ``setdefault`` 就不会覆盖它。

    ⚠️ **代价**：每份 YAML 因此解析两次。两个消费者都是**进程内只加载一次**
    （:func:`app.refdata_prescription.templates` 与 :func:`app.refdata_alerts.alert_rules`
    都是单例），故这笔开销与 spec §1.3 的 p95 < 3 秒预算无关。

    ⚠️ **它守不住**（硬规矩 #39）：① **缺失的键没有条目**，故 :func:`fail` 对缺失档要退到
    父路径，报的是「它所在的块」的行；② 空文档 ``yaml.compose`` 返回 ``None``，
    本函数返回空索引（那一档由「文件为空」的报错接管，不需要行号）；③ 重复的键在节点树里
    是**两项**、在 ``safe_load`` 的结果里只有一项，故索引里后写的那一项会覆盖前一项的行号
    ——与 PyYAML「后者覆盖前者」的语义一致，不是 bug。
    """
    root = yaml.compose(text, Loader=yaml.SafeLoader)
    index: dict[tuple, int] = {}
    if root is None:
        return index

    def walk(node: object, path: tuple) -> None:
        index.setdefault(path, node.start_mark.line + 1)
        if isinstance(node, yaml.MappingNode):
            for key_node, value_node in node.value:
                key = key_node.value if isinstance(key_node, yaml.ScalarNode) else "?"
                child = path + (key,)
                index[child] = key_node.start_mark.line + 1
                walk(value_node, child)
        elif isinstance(node, yaml.SequenceNode):
            for position, item in enumerate(node.value):
                walk(item, path + (position,))

    walk(root, ())
    return index


def fail(
    path: pathlib.Path,
    lines: dict[tuple, int],
    key_path: tuple,
    message: str,
    *,
    doc_kind: str,
) -> ValueError:
    """**造**（不抛）一个带**文档种类 + 文件名 + 行号**的 ``ValueError``，由调用方 ``raise``。

    ``key_path`` 在索引里查不到时（缺失的键、或索引根本建不出来）退到最近的父路径，
    并在行号后面**明写**这是「所在的块」而不是那个键自己——含糊地报一个行号比报不出行号
    更坏，因为它会把专家指到一行没问题的代码上（硬规矩 #39）。

    ``doc_kind`` 是**必填的关键字参数、没有缺省值**，理由见模块 docstring 的第 2 条：
    它原先是硬编码的 ``"处方模板"``，搬进共用模块之后必须由各加载器自己说清在读什么。
    """
    line = lines.get(key_path)
    approx = line is None
    if approx:
        for depth in range(len(key_path) - 1, -1, -1):
            if key_path[:depth] in lines:
                line = lines[key_path[:depth]]
                break
    if line is None:
        where = "行号不可得（索引建不出来）"
    elif approx:
        where = f"第 {line} 行（缺失的键没有自己的位置，指到它所在的块）"
    else:
        where = f"第 {line} 行"
    return ValueError(f"{doc_kind} {path} {where}：{message}")


def exact_keys(
    path: pathlib.Path,
    lines: dict[tuple, int],
    where: tuple,
    raw: object,
    required: tuple[str, ...],
    label: str,
    *,
    doc_kind: str,
) -> None:
    """校验一个映射的键**恰好**是 ``required``（缺与多都响亮失败），并校验它是个映射。

    「多出来的键也要炸」的理由照抄 :func:`app.refdata_prescription._exercise_spec`：
    多余的键会被静默忽略，而它通常意味着改名后忘了删旧的那一个——例如把 ``week_deltas``
    改写成 ``weekly_deltas``，读到的就永远是旧值。

    ``label`` 是**这个映射自己**的人话名字（``"模板顶层"`` / ``"review 嵌套块"``），
    与 ``doc_kind``（**整份文件**的种类）是两个不同粒度的东西，故两个参数都在。
    """
    if not isinstance(raw, dict):
        raise fail(
            path, lines, where,
            f"{label}应为「属性名 → 值」的映射，实为 {type(raw).__name__}",
            doc_kind=doc_kind,
        )
    missing = [key for key in required if key not in raw]
    if missing:
        raise fail(
            path, lines, where,
            f"{label}缺键 {missing}；必需的键恰好是 {list(required)}",
            doc_kind=doc_kind,
        )
    unexpected = sorted(set(raw) - set(required))
    if unexpected:
        raise fail(
            path, lines, where,
            f"{label}有多余的键 {unexpected}；必需的键恰好是 {list(required)}。"
            f"多余的键会被静默忽略，而它通常意味着改名后忘了删旧的那一个",
            doc_kind=doc_kind,
        )


def as_int(path, lines, where, raw, label, *, doc_kind: str) -> int:
    """校验并返回一个 ``int``。⚠️ **显式排除 ``bool``**：``isinstance(True, int)`` 为真，
    于是 ``day: true`` 会被朴素实现读成 ``1``——一个静默的坏值。"""
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise fail(
            path, lines, where,
            f"{label}应为整数，实为 {type(raw).__name__} 的 {raw!r}",
            doc_kind=doc_kind,
        )
    return raw


def as_float(path, lines, where, raw, label, *, doc_kind: str) -> float:
    """校验并返回一个 ``float``（``60`` 收敛成 ``60.0``）。同样显式排除 ``bool``。

    **收敛成 ``float`` 是承重的**：消费者要拿这些数做算术与比较（Plan 02 Task 5 算
    ``HRmax × low / 100``；Plan 03 Task 6 比 ``mean_rpe > mean_rpe_max``），
    而 YAML 里 ``low: 60`` 解析出来是 ``int``、``low: 60.5`` 是 ``float``——同一个字段
    两种类型会让「区间端点含不含」这类比较在两份文件上行为不同。

    ⚠️ **它对「必须是整数」的键不适用**（``consecutive: 2`` / ``streak: 3`` 一类）：
    那一类用 :func:`as_int`，否则 ``2.0`` 会被照收、而它是一个不该出现的写法
    （``streak: 2.5`` 次快评没有意义）。
    """
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        raise fail(
            path, lines, where,
            f"{label}应为数字，实为 {type(raw).__name__} 的 {raw!r}",
            doc_kind=doc_kind,
        )
    return float(raw)


def as_optional_text(path, lines, where, raw, label, *, doc_kind: str) -> str | None:
    """校验并返回一个「``None`` 或非空字符串」（``review.reviewer`` 用它）。

    ``None`` 是合法值：spec §7.2 骨架 ``:462`` 的字面形状就是 ``reviewer: null``
    （一个 ``pending`` 的模板天然还没有审校人）。但**空串不合法**——留空分不清
    「没有审校人」与「忘了填」（与 ``exercises.yaml`` 的 ``equipment: none`` 同一条理由）。
    """
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise fail(
            path, lines, where,
            f"{label}应为 None 或非空字符串（留空分不清「没有」与「忘了填」），实为 {raw!r}",
            doc_kind=doc_kind,
        )
    return raw

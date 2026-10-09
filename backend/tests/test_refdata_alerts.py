# backend/tests/test_refdata_alerts.py
"""``alert_rules.yaml`` 的加载器 :mod:`app.refdata_alerts` 与共用助手 :mod:`app.refdata_yaml`
的守卫（Plan 03 Task 6）。

**两道闸，各守一件事**：

* **闸 A（共用助手的单一所有者）**：计划正文对第二个 YAML 加载器给的处置是「**直接照抄
  那套形状**，不要另发明一套」。⚠️ 「照抄」在字面上等于复制，而**复制就是第二个所有者**
  （Global Constraint #3）。故那 6 个通用助手被抽进 :mod:`app.refdata_yaml`，两个加载器
  都从它 import。这一件事**不能靠散文守**：一个模块 docstring 里写着「本模块的助手来自
  refdata_yaml」，与那个模块里躺着一份 30 行的副本，读起来一样。故 5 支全部机器可查。
* **闸 B（YAML 被改坏要在加载时响亮失败）**：Review Focus 第 5 条。``alert_rules.yaml``
  是全系统**唯一**会直接改变「给哪个学生推减量 20%」的东西（账本 Ruling 1 因此把本 Task
  定为全计划唯一要求变异测试的地方），而它由体育专家手工维护、走版本控制与评审
  （spec §4.4 逐字：「静态 YAML + 版本号，不入库……不应在运行时改数据库」）。
  一个改坏的阈值必须在**加载期**炸、并点名**文件名 + 行号 + 键路径**，
  而不是在某个学生触发预警时才炸——后者离真因隔三层，且只在 500 人里动了几个百分点。

**闸 B 的每一条都用「把真 YAML 改坏一处」的方式构造**（:func:`_broken`），而不是手写一份
坏文件：手写的话，坏文件与真文件的差别可能不止一处，于是「红的原因」是猜的。改一处的
做法让每条测试的因果唯一。

**期望侧一律字面写死**（硬规矩 #35）：6 个助手名、5 个适配器名、两个 ``doc_kind`` 措辞、
5 条规则的 8 个阈值、版本号、指纹都写在本文件里，**不从**被测模块或那份 YAML 反推。
"""
import ast
import hashlib
import importlib
import inspect
import pathlib
import re
import types

import pytest
import yaml

from app import refdata_alerts, refdata_yaml
from app.domain import alerts as alerts_domain
from app.domain.alerts import AlertLevel, AlertScope, RuleId
from app.refdata import DATA_DIR

# ---------------------------------------------------------------------------
# 闸 A 的字面量
# ---------------------------------------------------------------------------

#: ``backend/app/``。支 A1 的扫描面：``app/`` 下全部 ``.py``（含子包），不含 ``tests/``。
APP_DIR = pathlib.Path(refdata_yaml.__file__).resolve().parent

#: 抽出来的 6 个通用助手。**字面写死**，不读 ``refdata_yaml.__all__``（硬规矩 #35）：
#: 谁往 ``__all__`` 里加一个名字而忘了在 :mod:`app.refdata_yaml` 里定义它，
#: 支 A1 的 ``sites`` 就是空列表 → 当场红。
_SHARED_HELPERS = (
    "line_index",
    "fail",
    "exact_keys",
    "as_int",
    "as_float",
    "as_optional_text",
)

#: 5 个**需要绑 ``doc_kind``** 的助手 → 各消费者里对应的私有适配器名。
#: :func:`app.refdata_yaml.line_index` 不需要 ``doc_kind``，故它不在这张表里
#: （它由支 A3 的身份比对看着）。
_ADAPTERS = {
    "_fail": "fail",
    "_exact_keys": "exact_keys",
    "_as_int": "as_int",
    "_as_float": "as_float",
    "_as_optional_text": "as_optional_text",
}

#: 消费者 → 它给自己那份 YAML 绑的**文档种类**。措辞字面写死：支 A4 要拿它去比报错文本的
#: 开头，两侧因此不同源（一侧是本字面量，另一侧是 ``refdata_yaml.fail`` 现拼出来的串）。
_CONSUMERS = {
    "app.refdata_prescription": "处方模板",
    "app.refdata_alerts": "预警规则",
}

# ---------------------------------------------------------------------------
# 闸 B 的字面量
# ---------------------------------------------------------------------------

#: ``alert_rules.yaml`` 的 sha256 前 16 位（大写十六进制），**行尾归一化为 LF 之后**计算。
#: 口径逐字同 ``tests/test_refdata_prescription.py`` 的 ``EXERCISES_FINGERPRINT`` 与
#: ``tests/test_refdata.py`` 的 ``STANDARD_FINGERPRINT``。
#: ⚠️ **它钉的是「阈值不许在跑测试的间隙被人改掉」**：``alert_rules.yaml`` 是本系统唯一
#: 直接决定「给哪个学生推减量 20%」的一份数据，而它的改动按 spec §4.4 必须走版本控制与
#: 评审——指纹让「悄悄改一个数」这件事在 CI 上当场红。
#:
#: ⚠️ **落地时的取证**（``read_bytes()`` 口径，硬规矩 #89 的扩写；脚本
#: ``t6_probes/yaml_stats.py``）：本文件 **6 037 B / 85 个 LF / 0 个 CRLF / 无 BOM**，
#: 首行是那条 ``# 预警阈值 ……`` 注释、末行是 ``GREEN_MASTERY`` 的 ``params``。
#: ``.gitattributes`` 的 ``backend/data/*.yaml text eol=lf`` 已覆盖它（它直接在
#: ``backend/data/`` 下、不在子目录），故这个指纹与 ``core.autocrlf`` 无关。
ALERT_RULES_FINGERPRINT = "E48E3AC82BB45BB7"

#: spec §8.2 判据表 + 那张「四项均待确认」的口径表，逐条抄成阈值。
#: ⚠️ 与 ``tests/domain/test_alerts.py`` 的 ``_SPEC_PARAMS`` 是**两份独立的字面量**：
#: 那一份钉 domain 的行为，这一份钉 YAML 的内容。两份都写死，于是「改坏哪一侧都有人红」。
#: ⚠️ ``rpe_min`` 写 ``9.0`` 而不是 ``9``：加载器把它归一成 ``float``
#: （口径同 ``refdata_yaml.as_float`` 的 docstring——同一个字段两种类型会让比较行为
#: 在两份文件上不同）。
_SPEC_PARAMS = {
    "RED_MINITEST_DROP": {"drop_pct": 0.05, "consecutive": 2, "points_needed": 3},
    "RED_RPE_SUSTAINED": {"rpe_min": 9.0, "streak": 3},
    "YELLOW_CHECKIN_GAP": {"gap_days": 2},
    "YELLOW_CLASS_RPE_HIGH": {"mean_rpe_max": 7.0},
    "GREEN_MASTERY": {"completion_rate_min": 1.0, "improve_pct": 0.03},
}
_SPEC_LEVELS = {
    "RED_MINITEST_DROP": "red",
    "RED_RPE_SUSTAINED": "red",
    "YELLOW_CHECKIN_GAP": "yellow",
    "YELLOW_CLASS_RPE_HIGH": "yellow",
    "GREEN_MASTERY": "green",
}
_SPEC_SCOPES = {
    "RED_MINITEST_DROP": "student",
    "RED_RPE_SUSTAINED": "student",
    "YELLOW_CHECKIN_GAP": "student",
    "YELLOW_CLASS_RPE_HIGH": "class",
    "GREEN_MASTERY": "student",
}
_SPEC_VERSION = "1.0"

#: ``app.domain.alerts`` 与 ``app.refdata_alerts`` 的公开面（P6-A5）。
#: ⚠️ **形状照 ``tests/test_refdata_prescription.py`` 的 ``_PRESCRIPTION_PUBLIC_BASELINE``**：
#: ``(名字, 所有者模块)`` 二元组 + 一条 ``assert len(...) == N``。
#: ⚠️ 两份基线的**主语不同**，不要混起来：那一份钉的是 ``app.domain.prescription`` 这个
#: **包**的 ``__all__``（实测 **51** 个二元组、9 个所有者模块），本份钉的是本 Task 新建的
#: 两个模块自己的公开面。故 ``app.domain.alerts`` **不进** ``_OWNED_MODULES``
#: （那个清单的主语是「处方包拥有的模块」），``refdata_prescription.py`` 的 8 个公有函数
#: 也**从来不在**那一份里（它没有 ``__all__``、也没有任何基线钉它——简报 P6-A5 把这件事
#: 记成「24 个二元组」，实现者顶回，逐字取证见 task-6-report §2）。
#:
#: ``app.domain.alerts`` 那 16 个的**声明序**照 ``alerts.__all__`` 的书写序逐字抄进来；
#: ``app.refdata_alerts`` 那 3 个照它的书写序（文件名常量 → 加载器 → 单例）。
_ALERTS_PUBLIC_BASELINE = [
    ("AlertLevel", "app.domain.alerts"),
    ("RuleId", "app.domain.alerts"),
    ("AlertScope", "app.domain.alerts"),
    ("SUBJECT_PREFIX_STUDENT", "app.domain.alerts"),
    ("SUBJECT_PREFIX_SECTION", "app.domain.alerts"),
    ("AlertRule", "app.domain.alerts"),
    ("AlertRules", "app.domain.alerts"),
    ("StudentSignals", "app.domain.alerts"),
    ("ClassSignals", "app.domain.alerts"),
    ("StudentHit", "app.domain.alerts"),
    ("ClassHit", "app.domain.alerts"),
    ("evaluate_student", "app.domain.alerts"),
    ("evaluate_class", "app.domain.alerts"),
    ("student_skip_traces", "app.domain.alerts"),
    ("class_skip_traces", "app.domain.alerts"),
    ("declared_scope", "app.domain.alerts"),
    ("ALERT_RULES_FILENAME", "app.refdata_alerts"),
    ("load_alert_rules", "app.refdata_alerts"),
    ("alert_rules", "app.refdata_alerts"),
]

#: ``app.refdata_alerts`` **没有** ``__all__``（P6-A5：照 ``refdata_prescription.py`` 的形状办），
#: 故它的公开面用 AST 数（``class`` / ``def`` / 赋值，不看 ``dir()``——``dir()`` 会把模块级
#: import 进来的 ``AlertRules`` / ``RuleId`` 也算成它的公有名，与被测的公开面同源）。
_NO_ALL_MODULES = ("app.refdata_alerts",)


def _fingerprint(path: pathlib.Path) -> str:
    """行尾归一化为 LF 之后取 sha256 前 16 位（大写）。口径同 ``tests/test_refdata.py``。"""
    return hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()[:16].upper()


def _definitions_of(name: str) -> list[str]:
    """``backend/app/`` 下所有 ``def <name>`` 的**顶层定义点**（``app/x/y.py`` 形式，升序）。

    按 ``ast.FunctionDef`` 数，不按正则：正则既数不出嵌套的 ``def``（本模块不关心，但
    ``line_index`` 里就有一个内层的 ``walk``），也会把 docstring 里提到的 ``def fail``
    当成一份定义。⚠️ 内层 ``def`` 也会被 :func:`ast.walk` 收到，故这里**只取顶层**
    （``tree.body``）：一个模块私有的内层辅助函数不构成「第二份所有者」。
    """
    hits: list[str] = []
    for py in sorted(APP_DIR.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                hits.append(py.relative_to(APP_DIR.parent).as_posix())
    return hits


def _code_of(node: ast.FunctionDef) -> list[ast.stmt]:
    """一个函数的**代码句**（去掉它自己的 docstring）。

    ⚠️ 不去掉的话判据会要求「适配器连一句 docstring 都不许写」——而本仓的纪律恰恰相反
    （硬规矩 #19：写下口径）。``ast.get_docstring`` 只在首句是字符串常量的 ``Expr`` 时
    返回非 ``None``，故它同时也是「首句是不是 docstring」的判据。
    """
    body = list(node.body)
    if ast.get_docstring(node) is not None:
        body = body[1:]
    return body


def _public_top_level_definitions(module) -> set[str]:
    """AST 扫一个模块的**公有顶层定义**（``class`` / ``def`` / 赋值），不看 ``dir()``。

    形状逐字照 ``tests/test_refdata_prescription.py`` 的同名助手（两份测试助手刻意各留一份：
    ``tests/`` 不是一个包，跨测试文件 import 会把两个文件的命运绑在一起，而它们守的是
    两个不同的公开面）。
    """
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    return {
        node.name for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and not node.name.startswith("_")
    } | {
        target.id
        for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name) and not target.id.startswith("_")
    }


def _real_text() -> str:
    """磁盘上那份真 YAML 的文本（LF）。改坏一处再加载，因果因此唯一（见模块 docstring）。"""
    path = DATA_DIR / refdata_alerts.ALERT_RULES_FILENAME
    return path.read_bytes().decode("utf-8")


def _broken(tmp_path: pathlib.Path, mutate) -> pathlib.Path:
    """把真 YAML **解析成 dict → 改一处 → 重新 dump** 成 ``tmp_path`` 下的一份文件。

    ⚠️ 走 dict 而不是文本替换：文本替换很容易一次改坏两处（缩进、行尾），于是「红的
    原因」变成猜的。``yaml.safe_load`` 每次现解析出一份**新的** dict，故 ``mutate`` 的
    就地改动只影响这一次，也不会碰到磁盘上那份真文件。
    """
    document = yaml.safe_load(_real_text())
    mutate(document)
    path = tmp_path / "broken_alert_rules.yaml"
    path.write_bytes(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True).encode("utf-8")
    )
    return path


# ===========================================================================
# 闸 A：6 个共用助手只有一个所有者（P6-A2）
# ===========================================================================


def test_the_six_shared_yaml_helpers_have_exactly_one_definition_site():
    """支 A1：6 个助手在 ``app/`` 下**各只有一处** ``def``，且都在 :mod:`app.refdata_yaml`。

    ⚠️ **这一支单独抓不住「复制回加载器」**（复制品通常带前导下划线、名字不同），
    它抓的是另一个方向：谁在别的模块里**再定义一个同名的** ``fail`` / ``as_int``。
    与支 A2 合起来才封住两个方向（硬规矩 #51：两份守卫各守一个方向）。
    """
    offenders: list[str] = []
    for name in _SHARED_HELPERS:
        sites = _definitions_of(name)
        if sites != ["app/refdata_yaml.py"]:
            offenders.append(f"{name}: 定义点是 {sites}，应恰好是 ['app/refdata_yaml.py']")
    assert offenders == [], (
        "共用 YAML 助手出现了第二个所有者（Global Constraint #3 / P6-A2）：\n"
        + "\n".join(offenders)
    )
    # 空转守卫：APP_DIR 指错时 rglob 返回空、上面每条都得到 []，offenders 反而非空——
    # 但为了不让「指错目录」与「真有第二份」报同一种错，这里单独钉一下扫描面本身。
    assert len(list(APP_DIR.rglob("*.py"))) >= 20, f"扫描面可能被指错了: {APP_DIR}"


def test_every_consumer_binds_doc_kind_through_a_one_statement_adapter():
    """支 A2：每个消费者的 5 个 ``_`` 适配器**只转发**，不重实现。

    判据是三条同时成立：① 函数体**恰好一句**（除去它自己的 docstring，见
    :func:`_code_of`）；② 那一句（``return …`` 或裸表达式）是对
    ``refdata_yaml.<同名去掉下划线>`` 的调用；③ 调用里带了 ``doc_kind=`` 关键字。
    三条合起来把「把 30 行逻辑复制回加载器」这个形状排除掉——那种情况下 ① 就不成立。

    ⚠️ **这一支是那个方向上唯一的守卫**：复制品的名字带下划线（支 A1 数不到）、行为
    又完全正确（闸 B 全绿），只有「函数体长度 + 它在调谁」这个**结构**会露馅。

    ⚠️ **为什么不用「源码里搜 ``yaml.compose``」这类判据**：那会随实现细节漂
    （哪天 :func:`app.refdata_yaml.line_index` 改了实现，这条守卫就变成一条与
    「有没有第二份所有者」无关的断言）。「函数体一句 + 调的是谁」与被调方的内部实现无关。
    """
    offenders: list[str] = []
    for module_name in _CONSUMERS:
        module = importlib.import_module(module_name)
        tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
        bodies = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        for adapter, shared in _ADAPTERS.items():
            node = bodies.get(adapter)
            if node is None:
                offenders.append(f"{module_name} 里没有 {adapter}")
                continue
            code = _code_of(node)
            if len(code) != 1:
                offenders.append(
                    f"{module_name}.{adapter} 的函数体有 {len(code)} 句"
                    "（除去它自己的 docstring），应恰好 1 句"
                    "（多于 1 句 = 逻辑被复制回了加载器，P6-A2 要消灭的正是这个）"
                )
                continue
            statement = code[0]
            if isinstance(statement, ast.Return):
                call = statement.value
            elif isinstance(statement, ast.Expr):
                call = statement.value
            else:
                offenders.append(
                    f"{module_name}.{adapter} 的那一句是 {type(statement).__name__}，"
                    "应是 return 或一个裸调用"
                )
                continue
            if not (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "refdata_yaml"
                and call.func.attr == shared
            ):
                offenders.append(
                    f"{module_name}.{adapter} 的那一句不是在调 refdata_yaml.{shared}"
                )
                continue
            if not any(kw.arg == "doc_kind" for kw in call.keywords):
                offenders.append(
                    f"{module_name}.{adapter} 调 refdata_yaml.{shared} 时没有绑 doc_kind="
                )
    assert offenders == [], (
        "共用 YAML 助手的适配器不是「只转发」（P6-A2）：\n" + "\n".join(offenders)
    )


def test_line_index_is_the_same_object_in_every_consumer():
    """支 A3：``_line_index`` 在各消费者里**就是** :func:`app.refdata_yaml.line_index`。

    :func:`app.refdata_yaml.line_index` 不需要 ``doc_kind``，故它没有适配器、而是直接
    别名引用，``is`` 因此必须成立。⚠️ 一份副本会同时骗过支 A1（名字不同）与闸 B
    （行为完全正确），只有身份比对抓得住它。
    """
    for module_name in _CONSUMERS:
        module = importlib.import_module(module_name)
        assert module._line_index is refdata_yaml.line_index, (
            f"{module_name}._line_index 不是 app.refdata_yaml.line_index 那个对象："
            "它被复制了一份（P6-A2 要消灭的第二个所有者）"
        )


def test_doc_kind_is_bound_per_consumer_and_has_no_default():
    """支 A4：``doc_kind`` 是**必填关键字参数**，且每个消费者绑的是自己那份措辞。

    两半都要钉：

    * **没有缺省值**——``inspect.signature`` 上它必须是 ``Parameter.empty``。带缺省值的
      话，「新加载器忘了传」会静默用别人的文档种类去报错，而那正是本参数要防的事。
    * **绑对了**——各消费者的 ``_fail`` 现拼出来的消息必须以它自己那个中文措辞开头。
      期望侧是 :data:`_CONSUMERS` 里的字面量，实际侧是 ``refdata_yaml.fail`` 拼出来的串，
      两侧不同源（硬规矩 #35）。

    ⚠️ **为什么 ``doc_kind`` 必须存在**（计划的 P6-A2 没提，实现者顶回后补的）：
    ``fail`` 的消息前缀原先在 :mod:`app.refdata_prescription` 里**硬编码**成
    ``"处方模板"``。原样搬进共用模块的话，``alert_rules.yaml`` 被改坏时报出来的会是
    「处方模板 …/alert_rules.yaml 第 3 行」——指着一份预警阈值文件说它是处方模板，
    Review Focus 第 5 条要的「指出是哪个文件哪一行哪个键」当场变成假话。
    """
    signature = inspect.signature(refdata_yaml.fail)
    parameter = signature.parameters["doc_kind"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, parameter.kind
    assert parameter.default is inspect.Parameter.empty, (
        f"doc_kind 有了缺省值 {parameter.default!r}：忘了传的加载器会静默用别人的措辞报错"
    )

    lines = refdata_yaml.line_index("version: '1.0'\n")
    for module_name, doc_kind in _CONSUMERS.items():
        module = importlib.import_module(module_name)
        error = module._fail(
            pathlib.Path("data/x.yaml"), lines, ("version",), "探针消息",
        )
        assert isinstance(error, ValueError), type(error)
        assert str(error).startswith(f"{doc_kind} "), (
            f"{module_name} 的报错前缀不是 {doc_kind!r}：{str(error)[:60]}"
        )
        assert "探针消息" in str(error)


def test_refdata_yaml_does_not_import_anything_from_app():
    """支 A5：:mod:`app.refdata_yaml` 是叶子——不 import ``app`` 里的任何东西。

    与 :mod:`app.config` 同档的理由：一个**被两个加载器共用**的模块若反过来 import 它的
    消费者，环就出来了。它今天只 import :mod:`pathlib` 与 :mod:`yaml`，本支把这件事钉住，
    于是「将来有人为了方便把 ``DATA_DIR`` 搬进来」会当场红（那会让
    ``app.refdata_yaml → app.refdata → app.domain`` 这条边出现，共用助手从此不再是叶子）。
    """
    tree = ast.parse(pathlib.Path(refdata_yaml.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(("." * node.level) + node.module)
    assert [name for name in imported if name.split(".")[0] == "app"] == [], imported
    assert sorted(imported) == ["pathlib", "yaml"], imported


def test_fail_names_the_enclosing_block_when_a_key_has_no_position_of_its_own():
    """:func:`app.refdata_yaml.fail` 的**三档措辞**各钉一条（含两档反面对照，硬规矩 #50）。

    三档是：① 键自己在索引里 → 只写「第 N 行」；② 键**不在**索引里（缺失的键没有自己的
    位置）→ 退到最近的父路径并**明写**这是「它所在的块」；③ 索引根本建不出来（空文档）
    → 明写「行号不可得」。

    ⚠️ ② 与 ③ 那两句「明写」是承重的：含糊地报一个行号比报不出行号**更坏**，因为它会把
    专家指到一行没问题的代码上（硬规矩 #39）。而这一档**只能在这里测**——两个加载器的
    「缺键」路径传的都是**块自己的**键路径（它在索引里），故走的是 ① 那一档。
    """
    text = "rules:\n  RED_RPE_SUSTAINED:\n    level: red\n"
    lines = refdata_yaml.line_index(text)
    where = pathlib.Path("data/x.yaml")

    present = refdata_yaml.fail(
        where, lines, ("rules", "RED_RPE_SUSTAINED", "level"), "level 坏了",
        doc_kind="预警规则")
    assert "第 3 行" in str(present), str(present)
    assert "所在的块" not in str(present), str(present)

    absent = refdata_yaml.fail(
        where, lines, ("rules", "RED_RPE_SUSTAINED", "scope"), "缺 scope",
        doc_kind="预警规则")
    assert "第 2 行" in str(absent), str(absent)
    assert "缺失的键没有自己的位置，指到它所在的块" in str(absent), str(absent)

    unindexed = refdata_yaml.fail(where, {}, ("rules",), "文件为空", doc_kind="预警规则")
    assert "行号不可得（索引建不出来）" in str(unindexed), str(unindexed)
    for error in (present, absent, unindexed):
        assert isinstance(error, ValueError), type(error)
        assert str(error).startswith("预警规则 "), str(error)
        assert "data" in str(error) and "x.yaml" in str(error), str(error)


# ===========================================================================
# 闸 B-1：``alert_rules.yaml`` 的字节（指纹 / 行尾 / version 的引号）
# ===========================================================================


def test_alert_rules_yaml_fingerprint_is_pinned():
    """指纹逐字钉住：谁在跑测试的间隙改了一个阈值，本条当场红。

    期望值 :data:`ALERT_RULES_FINGERPRINT` 是**字面量**，实际值现算自磁盘，两侧不同源
    （硬规矩 #35）。⚠️ **确认改动是有意之后才更新那个常量**，且更新它等于承认
    「给哪些学生推减量 20%」这件事变了——按 spec §4.4 它要走版本控制与评审。
    """
    path = DATA_DIR / refdata_alerts.ALERT_RULES_FILENAME
    digest = _fingerprint(path)
    assert digest == ALERT_RULES_FINGERPRINT, (
        f"预警阈值被改动了：sha256 前 16 位是 {digest}，钉住的是 "
        f"{ALERT_RULES_FINGERPRINT}。确认改动有意之后更新本文件那一行常量。"
    )


def test_alert_rules_yaml_is_lf_only_in_the_worktree():
    """工作树里这份 YAML 一个 CRLF 都没有（硬规矩 #89 的扩写：数行尾用 ``read_bytes()``）。

    ``.gitattributes`` 的 ``backend/data/*.yaml text eol=lf`` 已经盖住它（它直接在
    ``backend/data/`` 下、不在子目录），本条是**第二道保险**而不是唯一依赖：
    ``core.autocrlf`` 在 Git for Windows 上缺省为 ``true``，而指纹是按字节算的
    （口径同 ``tests/domain/test_prescription_templates.py`` 的
    ``test_every_template_yaml_is_lf_only_in_the_worktree``）。
    """
    path = DATA_DIR / refdata_alerts.ALERT_RULES_FILENAME
    raw = path.read_bytes()
    crlf = raw.count(b"\r\n")
    assert crlf == 0, f"{path.name} 里有 {crlf} 个 CRLF，指纹会随平台配置漂"
    newlines = raw.count(b"\n")
    assert newlines >= 20, f"只数到 {newlines} 行，文件可能被写空了"
    assert not raw.startswith(b"\xef\xbb\xbf"), "带 BOM 的 YAML 会让首键解析不出来"


def test_version_is_quoted_in_the_raw_text_so_pyyaml_keeps_it_a_string():
    """``version`` 那一行在**原始文本**里就是带引号的 ``version: "1.0"``。

    ⚠️ YAML 里不加引号的 ``1.0`` 会被 PyYAML 解析成 ``float``，而 ``1.10`` 会变成
    ``1.1``——版本号静默变形（Plan 02 Task 3 踩过，18 份模板因此一律加引号）。
    加载器那一侧也校验它是 ``str``（:func:`test_loader_rejects_a_version_that_is_not_a_string`），
    两侧各守一半：本条守**文件里写的是什么**，那一条守**读出来的类型**。

    ⚠️ 判据用原始文本而不是解析结果：``yaml.safe_load`` 已经把引号吃掉了，
    从解析结果反推「有没有加引号」是不可能的。
    """
    version_lines = [
        line for line in _real_text().split("\n") if line.startswith("version:")
    ]
    assert version_lines == ['version: "1.0"'], version_lines


def test_each_rule_id_appears_exactly_once_in_the_raw_text():
    """5 个规则 ID 在原始文本里各出现**恰好一次**（``rules:`` 下的键位）。

    ⚠️ **PyYAML 对重复的键是后者覆盖前者、不报错**（口径同
    ``refdata_prescription.load_exercises`` 的 docstring），故「专家复制一段忘了改 ID」
    会让一条规则**静默消失**、而加载器拿到的是覆盖后的 dict、看不出问题。
    本条用**原始文本**数一遍，与解析结果对账，两侧不同源。
    """
    text = _real_text()
    for name in _SPEC_PARAMS:
        hits = re.findall(rf"^\s{{2}}{re.escape(name)}:\s*$", text, flags=re.MULTILINE)
        assert len(hits) == 1, f"{name} 在 rules: 下出现了 {len(hits)} 次，应恰好 1 次"


# ===========================================================================
# 闸 B-2：加载器读对了那份 YAML
# ===========================================================================


def test_load_alert_rules_reads_the_five_spec_rules_verbatim():
    """版本号、5 个规则 ID、它们的 ``level`` / ``scope`` / 8 个阈值全部逐字对账。

    期望侧是 :data:`_SPEC_PARAMS` / :data:`_SPEC_LEVELS` / :data:`_SPEC_SCOPES` 三个
    字面量（出处：spec §8.2 的判据表与那张「四项均待确认」的口径表），实际侧现读自磁盘。
    ⚠️ 这条与指纹那条**分工**：指纹挡「任何字节变了」，本条挡「变的那一个字节是不是
    一个阈值」——一次纯注释改动会让指纹红而本条绿，那正是「改注释不用评审阈值」的形状。
    """
    loaded = refdata_alerts.load_alert_rules()
    assert loaded.version == _SPEC_VERSION
    assert isinstance(loaded.version, str), type(loaded.version)
    assert [rule_id.value for rule_id in loaded.rules] == list(_SPEC_PARAMS)
    for name, params in _SPEC_PARAMS.items():
        rule = loaded.rules[RuleId(name)]
        assert rule.rule_id is RuleId(name)
        assert rule.level is AlertLevel(_SPEC_LEVELS[name])
        assert rule.scope is AlertScope(_SPEC_SCOPES[name])
        assert dict(rule.params) == params, f"{name} 的阈值与 spec §8.2 不一致"
        assert loaded.params_of(RuleId(name)) == rule.params
    assert len(loaded.rules) == 5


def test_the_rules_mapping_is_read_only_and_the_singleton_is_cached():
    """``rules`` 是只读视图；``alert_rules()`` 是单例；``load_alert_rules()`` **不**缓存。

    口径逐字同 :func:`app.refdata_prescription.templates`（Plan02 账本 P2-A9：``load_*``
    只加载不缓存，单例是另一个函数）。只读是承重的：``alert_rules()`` 被全进程共享
    （Task 7 的 ``alert_stage`` 逐学生逐班跑），一次 ``rules[RuleId.X] = …`` 的就地改写
    会让之后所有求值静默变质，而 ``AlertRules.frozen=True`` 只挡「换掉整个字段」。
    """
    loaded = refdata_alerts.load_alert_rules()
    assert isinstance(loaded.rules, types.MappingProxyType), type(loaded.rules)
    with pytest.raises(TypeError):
        loaded.rules[RuleId.GREEN_MASTERY] = None  # type: ignore[index]
    with pytest.raises(TypeError):
        loaded.rules[RuleId.RED_RPE_SUSTAINED].params["streak"] = 99  # type: ignore[index]
    assert refdata_alerts.alert_rules() is refdata_alerts.alert_rules(), (
        "alert_rules() 不是单例：每次调用都重解析一遍 YAML（含一次 yaml.compose 建行号索引）"
    )
    assert refdata_alerts.load_alert_rules() is not refdata_alerts.load_alert_rules(), (
        "load_alert_rules() 不该缓存：缓存是 alert_rules() 的职责"
    )


def test_the_real_yaml_drives_the_spec_boundaries_end_to_end():
    """把**磁盘上那份** YAML 喂给 domain，spec §8.2 的 5 个边界必须逐个成立。

    ⚠️ 这一条是闸 B 与 ``tests/domain/test_alerts.py`` 的**接缝**：那一份用的是测试自己
    构造的规则，故「有人把 YAML 里的 ``9`` 改成 ``8``」在它那边一声不响（指纹那条会红，
    但红的原因是「字节变了」而不是「行为变了」）。本条把真配置接上真求值器，
    于是那一次改动会同时红两条、且**这一条的失败消息说的是行为**。
    """
    from app.domain.alerts import ClassSignals, StudentSignals, evaluate_class, evaluate_student

    rules = refdata_alerts.alert_rules()

    def student(**overrides):
        fields = dict(
            student_id=7, semester_id=1, week=10,
            rpe_streak=0, rpe_session_ids=(),
            mini_test_scores=(), mini_test_ids=(),
            checkin_gap_days=0, checkin_gap_end="2026-10-08",
            completion_rate=None, mini_test_improved=False,
        )
        fields.update(overrides)
        return StudentSignals(**fields)

    # RED_RPE_SUSTAINED：3 次触发、2 次不触发
    assert len(evaluate_student(
        student(rpe_streak=3, rpe_session_ids=(1, 2, 3)), rules)) == 1
    assert evaluate_student(student(rpe_streak=2, rpe_session_ids=(1, 2)), rules) == ()
    # RED_MINITEST_DROP：恰好 5% 不触发、5.1% 触发
    assert evaluate_student(
        student(mini_test_scores=(88.0, 80.0, 76.0), mini_test_ids=(1, 2, 3)), rules) == ()
    assert len(evaluate_student(
        student(mini_test_scores=(88.0, 80.0, 75.9), mini_test_ids=(1, 2, 3)), rules)) == 1
    # YELLOW_CHECKIN_GAP：2 天触发、1 天不触发
    assert len(evaluate_student(student(checkin_gap_days=2), rules)) == 1
    assert evaluate_student(student(checkin_gap_days=1), rules) == ()
    # YELLOW_CLASS_RPE_HIGH：恰好 7.0 不触发、7.1 触发
    section = dict(course_section_id=3, semester_id=1, week=10, student_count=31)
    assert evaluate_class(ClassSignals(mean_rpe=7.0, **section), rules) == ()
    assert len(evaluate_class(ClassSignals(mean_rpe=7.1, **section), rules)) == 1
    # GREEN_MASTERY：100% + 有提升触发、99% 不触发
    assert len(evaluate_student(
        student(completion_rate=1.0, mini_test_improved=True), rules)) == 1
    assert evaluate_student(
        student(completion_rate=0.99, mini_test_improved=True), rules) == ()


# ===========================================================================
# 闸 B-3：YAML 被改坏 → 加载时响亮失败，并点名文件 + 行号 + 键路径
# ===========================================================================


def _raises_naming_file_and_line(tmp_path, mutate, *fragments):
    """把真 YAML 改坏一处，断言它 ``ValueError``、且消息点名**文件 + 行号 + 给定片段**。

    「行号」的判据是消息里出现 ``第 <数字> 行``——这是 Review Focus 第 5 条要的
    「指出是哪个键」的落点（``refdata_yaml.fail`` 的三档措辞里，「缺失的键」那一档会
    额外写明「指到它所在的块」，故这里只钉「有一个行号」而不钉具体数字：数字随改坏方式漂）。
    """
    path = _broken(tmp_path, mutate)
    with pytest.raises(ValueError) as caught:
        refdata_alerts.load_alert_rules(path)
    message = str(caught.value)
    assert path.name in message, f"消息里没有文件名：{message}"
    assert re.search(r"第 \d+ 行", message), f"消息里没有行号：{message}"
    for fragment in fragments:
        assert fragment in message, f"消息里缺 {fragment!r}：{message}"
    return message


def test_loader_rejects_a_missing_version(tmp_path):
    """缺 ``version`` → 响亮失败（spec §4.4 要求「静态 YAML + **版本号**」）。"""
    def drop(document):
        del document["version"]
    _raises_naming_file_and_line(tmp_path, drop, "version")


def test_loader_rejects_a_version_that_is_not_a_string(tmp_path):
    """``version: 1.0``（**不加引号** → PyYAML 给一个 ``float``）→ 响亮失败。

    ⚠️ 这一档是 Plan 02 Task 3 踩过的那个坑的预警侧版本：``1.10`` 不加引号会变成
    ``1.1``，而 ``alert.rule_id`` 与 ``weekly_adjustment`` 的 ``auto`` 来源都要能回答
    「当时是按哪一版阈值判的」。
    """
    def unquote(document):
        document["version"] = 1.0
    message = _raises_naming_file_and_line(tmp_path, unquote, "version", "float")
    assert "引号" in message, message


def test_loader_rejects_a_top_level_that_is_not_a_mapping(tmp_path):
    """顶层不是映射 → 响亮失败。"""
    path = tmp_path / "list_alert_rules.yaml"
    path.write_bytes(b"- RED_RPE_SUSTAINED\n- GREEN_MASTERY\n")
    with pytest.raises(ValueError, match="list"):
        refdata_alerts.load_alert_rules(path)


def test_loader_rejects_an_empty_file_and_a_missing_file(tmp_path):
    """空文件与文件不存在各是一档，且都不许静默变成「零条规则」。

    ⚠️ 「零条规则」是 Review Focus 第 5 条点名的静默失效：500 人一个预警都不触发、
    管道全绿、教师端一片祥和。
    """
    empty = tmp_path / "empty_alert_rules.yaml"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="为空"):
        refdata_alerts.load_alert_rules(empty)
    missing = tmp_path / "nope_alert_rules.yaml"
    with pytest.raises(FileNotFoundError, match="预警规则"):
        refdata_alerts.load_alert_rules(missing)


def test_loader_rejects_a_file_that_is_not_valid_yaml(tmp_path):
    """YAML 语法错 → ``ValueError``（不是 ``yaml.YAMLError``），且带上文件名。

    PyYAML 的 mark 里有行列、但**没有文件名**（喂给它的是字符串而不是文件对象），
    且 ``YAMLError`` 不是 ``ValueError`` 的子类；包一层让调用方只需认一种异常类型
    （口径逐字同 ``refdata_prescription._template``）。
    """
    path = tmp_path / "syntax_alert_rules.yaml"
    path.write_bytes(b"version: '1.0'\nrules: [\n  RED_RPE_SUSTAINED: {level: red}\n")
    with pytest.raises(ValueError) as caught:
        refdata_alerts.load_alert_rules(path)
    assert path.name in str(caught.value)
    assert not isinstance(caught.value, yaml.YAMLError)


def test_loader_rejects_rules_that_are_not_a_mapping(tmp_path):
    """``rules`` 不是映射 → 响亮失败。"""
    def to_list(document):
        document["rules"] = ["RED_RPE_SUSTAINED"]
    _raises_naming_file_and_line(tmp_path, to_list, "rules")


def test_loader_rejects_a_rule_id_the_code_does_not_know(tmp_path):
    """**多出一个没人认识的规则 ID** → 响亮失败。

    ⚠️ 这是 Review Focus 第 5 条里最阴的一档：专家照 spec 加了一条新规则、忘了改代码。
    静默忽略的话那条新规则**永远不生效**，而 YAML 看起来完全正常、评审也过了。
    """
    def add_unknown(document):
        document["rules"]["RED_SLEEP_DEBT"] = {
            "level": "red", "scope": "student", "params": {"nights": 3},
        }
    _raises_naming_file_and_line(tmp_path, add_unknown, "RED_SLEEP_DEBT")


def test_loader_rejects_a_missing_rule_id(tmp_path):
    """**少一条**规则同样响亮失败（``RuleId`` 的 5 个成员必须都在 YAML 里）。"""
    def drop_one(document):
        del document["rules"]["GREEN_MASTERY"]
    _raises_naming_file_and_line(tmp_path, drop_one, "GREEN_MASTERY")


def test_loader_rejects_a_rule_block_that_is_not_a_mapping(tmp_path):
    """某条规则不是映射 → 响亮失败。"""
    def to_scalar(document):
        document["rules"]["YELLOW_CHECKIN_GAP"] = 2
    _raises_naming_file_and_line(tmp_path, to_scalar, "YELLOW_CHECKIN_GAP")


def test_loader_rejects_a_rule_with_a_missing_or_extra_key(tmp_path):
    """某条规则的键不是恰好 ``level`` / ``scope`` / ``params`` → 响亮失败（缺与多都拦）。"""
    def drop_key(document):
        del document["rules"]["RED_RPE_SUSTAINED"]["level"]
    _raises_naming_file_and_line(tmp_path, drop_key, "RED_RPE_SUSTAINED", "level")

    def add_key(document):
        document["rules"]["RED_RPE_SUSTAINED"]["severity"] = 3
    _raises_naming_file_and_line(tmp_path, add_key, "RED_RPE_SUSTAINED", "severity")


def test_loader_rejects_an_illegal_level_or_scope(tmp_path):
    """``level`` / ``scope`` 取值非法 → 响亮失败，并列出合法值。

    ⚠️ 一个词表外的 ``level``（``"orange"``）不会被任何人当成 red——它会被 DB 的
    ``ck_alert_level`` 在 Task 7 落库时拒收，报错点离真因隔两层。
    """
    def bad_level(document):
        document["rules"]["RED_RPE_SUSTAINED"]["level"] = "orange"
    _raises_naming_file_and_line(
        tmp_path, bad_level, "level", "orange", "red", "yellow", "green")

    def bad_scope(document):
        document["rules"]["YELLOW_CLASS_RPE_HIGH"]["scope"] = "school"
    _raises_naming_file_and_line(
        tmp_path, bad_scope, "scope", "school", "student", "class")


def test_loader_rejects_a_rule_whose_yaml_scope_disagrees_with_the_code(tmp_path):
    """YAML 的 ``scope`` 与 :func:`app.domain.alerts.declared_scope` 不一致 → 响亮失败。

    ⚠️ **没有这一条，``scope`` 就是装饰**：班级级规则拿不到 ``StudentSignals``，故
    「哪一套 evaluator 处理哪条规则」只能由代码决定；专家把 YAML 里的 ``scope`` 一翻
    而代码不跟着翻，就是一件**什么也不发生**的事（而他会以为发生了）。
    口径同 ``refdata_prescription._template`` 对 ``reachable`` 的处置：两份必须对账，
    矛盾就在加载期炸，并说明**哪一份是所有者**。
    """
    def flip(document):
        document["rules"]["GREEN_MASTERY"]["scope"] = "class"
    message = _raises_naming_file_and_line(
        tmp_path, flip, "GREEN_MASTERY", "scope", "declared_scope")
    assert "class" in message and "student" in message


def test_loader_rejects_params_with_a_missing_key(tmp_path):
    """``params`` 缺一个键 → 响亮失败，并列出**恰好**该有的那几个。"""
    def drop_param(document):
        del document["rules"]["GREEN_MASTERY"]["params"]["improve_pct"]
    message = _raises_naming_file_and_line(tmp_path, drop_param, "improve_pct")
    assert "缺键" in message, message
    assert "completion_rate_min" in message, message


def test_loader_rejects_params_with_an_extra_key(tmp_path):
    """``params`` 多一个键 → 响亮失败。

    ⚠️ 「多出来的键也要炸」的理由照抄 :func:`app.refdata_yaml.exact_keys`：多余的键会被
    静默忽略，而它通常意味着改名后忘了删旧的那一个——例如把 ``streak`` 改写成
    ``streak_min``，读到的就永远是旧值。
    ⚠️ 故这一条与上一条**刻意分成两次改动**：一次既删又加时，``exact_keys`` 先报
    「缺键」，「多余的键」那半句根本不会出现，一条测试就同时钉不住两件事。
    """
    def add_param(document):
        document["rules"]["RED_RPE_SUSTAINED"]["params"]["streak_min"] = 3
    message = _raises_naming_file_and_line(tmp_path, add_param, "streak_min")
    assert "多余" in message, message


def test_loader_rejects_a_threshold_that_is_not_a_number(tmp_path):
    """阈值不是数 → 响亮失败（``streak: "3"`` 是文本替换最常见的坏形状）。"""
    def to_text(document):
        document["rules"]["RED_RPE_SUSTAINED"]["params"]["streak"] = "3"
    _raises_naming_file_and_line(tmp_path, to_text, "streak", "str")

    def to_bool(document):
        document["rules"]["YELLOW_CHECKIN_GAP"]["params"]["gap_days"] = True
    message = _raises_naming_file_and_line(tmp_path, to_bool, "gap_days", "bool")
    assert "整数" in message, message


def test_loader_rejects_a_count_written_as_a_float(tmp_path):
    """计数类阈值写成小数 → 响亮失败。

    ⚠️ ``streak`` 要被当成**下标**用（``window_key`` 取 ``rpe_session_ids[streak - 1]``），
    一个 ``2.0`` 会在那一步抛 ``TypeError: list indices must be integers``——
    报错点在 domain 深处、离「YAML 里写错了一个数」隔三层。故在加载期就拦。
    """
    def to_float(document):
        document["rules"]["RED_RPE_SUSTAINED"]["params"]["streak"] = 3.0
    _raises_naming_file_and_line(tmp_path, to_float, "streak", "整数")


def test_loader_rejects_a_ratio_or_count_out_of_range(tmp_path):
    """阈值是数、但**语义上不可能** → 响亮失败。

    四档各是一种静默失效：

    * ``drop_pct: 5.0``（把「5%」写成 5.0）→ 判据里的 ``1 - 5.0 = -4.0``，
      于是 ``newer >= older × -4.0`` 对任何正分数都成立 → **这条规则永不触发**；
    * ``improve_pct: 0.0`` → 「任一指标改善 ≥ 0%」恒真，于是**每个完成度达标的学生
      每周都拿一张绿牌**，绿牌从此不代表任何事；
    * ``streak: 0`` → ``rpe_streak >= 0`` 恒真，于是**每个学生每周一张红牌**，
      而 ``window_key`` 会去取 ``rpe_session_ids[0 - 1]``——一个恰好不报错、
      却指着**最早**那一次快评的下标（于是去重键锚在一个随 streak 变的位置上，
      Review Focus 第 3 条的连乘又回来了）；
    * ``completion_rate_min: 1.5`` → 完成度是个 ``[0, 1]`` 的比率，``>= 1.5`` 恒假，
      于是**绿牌永不触发**。
    """
    def huge_ratio(document):
        document["rules"]["RED_MINITEST_DROP"]["params"]["drop_pct"] = 5.0
    _raises_naming_file_and_line(tmp_path, huge_ratio, "drop_pct")

    def zero_ratio(document):
        document["rules"]["GREEN_MASTERY"]["params"]["improve_pct"] = 0.0
    _raises_naming_file_and_line(tmp_path, zero_ratio, "improve_pct")

    def zero_count(document):
        document["rules"]["RED_RPE_SUSTAINED"]["params"]["streak"] = 0
    _raises_naming_file_and_line(tmp_path, zero_count, "streak")

    def over_one_rate(document):
        document["rules"]["GREEN_MASTERY"]["params"]["completion_rate_min"] = 1.5
    _raises_naming_file_and_line(tmp_path, over_one_rate, "completion_rate_min")


def test_loader_rejects_points_needed_that_is_not_consecutive_plus_one(tmp_path):
    """``points_needed`` 必须 == ``consecutive + 1``，否则响亮失败。

    ⚠️ 这是一条**跨参数**的不变量，而它的失效是静默的：``consecutive: 2`` 配
    ``points_needed: 5`` 时，domain 会拿到 5 个点却只查**最后 2 对**下降
    （判据本身没错），于是「需 3 个数据点」这条 spec 口径表 #2 的要求悄悄变成了
    「需 5 个数据点才够格被检查」——首次触发的周次跟着漂，而 YAML 看起来完全合理。
    """
    def mismatch(document):
        document["rules"]["RED_MINITEST_DROP"]["params"]["points_needed"] = 5
    message = _raises_naming_file_and_line(
        tmp_path, mismatch, "points_needed", "consecutive")
    assert "3" in message, message


def test_loader_names_the_rule_when_one_of_its_keys_is_missing(tmp_path):
    """某条规则缺 ``params`` → 响亮失败，并点名**是哪条规则**缺了**哪个键**。

    ⚠️ 行号报到的是那条规则**块的首行**（缺的键没有自己的位置）；
    :func:`app.refdata_yaml.fail` 那一档的措辞由
    :func:`test_fail_names_the_enclosing_block_when_a_key_has_no_position_of_its_own`
    直接单元测，本条只钉「加载器把规则 ID 与键名都带进了消息」。
    """
    def drop_key(document):
        del document["rules"]["YELLOW_CHECKIN_GAP"]["params"]
    _raises_naming_file_and_line(
        tmp_path, drop_key, "YELLOW_CHECKIN_GAP", "params", "缺键")


# ===========================================================================
# 闸 B-4：公开面基线（P6-A5）
# ===========================================================================


def test_alerts_public_namespace_is_pinned_verbatim():
    """``app.domain.alerts`` 与 ``app.refdata_alerts`` 的公开面被字面钉住（P6-A5）。

    **形状照 ``test_prescription_public_namespace_is_pinned_verbatim``**，六支同构：

    * **支 1** 基线自校（长度与无重名）；
    * **支 2** 内容与**声明序**：``app.domain.alerts`` 那 16 个逐字等于它的 ``__all__``
      （⚠️ ``app.refdata_alerts`` **没有** ``__all__``，照 ``refdata_prescription.py``
      的形状办，故它那一半由支 5 的 AST 口径看着）；
    * **支 3** 声明序不是字母序（于是支 2 真的在钉顺序）；
    * **支 4** 不许谎报：逐名字到**它自己的所有者**上取同一性；
    * **支 5** 穷尽：AST 扫公有顶层定义，与基线互为充要；
    * **支 6** 反面对照（硬规矩 #50）：两种合成的失同步态必须判不相等。

    ⚠️ **``app.domain.alerts`` 刻意不进 ``test_refdata_prescription.py`` 的
    ``_OWNED_MODULES``**：那个清单的主语是「**处方包**拥有的模块」，而本模块与
    ``prescription/`` 无隶属关系（它住 ``app/domain/`` 顶层）。
    """
    names = [name for name, _owner in _ALERTS_PUBLIC_BASELINE]
    # 支 1
    assert len(_ALERTS_PUBLIC_BASELINE) == 19, "基线是 19 个名字，抄漏了就当场红"
    assert len(set(names)) == 19, f"基线里有重名：{names}"
    assert len({owner for _n, owner in _ALERTS_PUBLIC_BASELINE}) == 2

    # 支 2：alerts.py 写了 __all__（P6-A5 要求：它是 domain 模块，与
    #       app/domain/prescription/*.py 同档，那些都写），故逐字对声明序。
    domain_names = [n for n, o in _ALERTS_PUBLIC_BASELINE if o == "app.domain.alerts"]
    assert list(alerts_domain.__all__) == domain_names
    assert len(domain_names) == 16

    # 支 3
    assert sorted(names) != names, "基线被排成字母序了，支 2 就不再钉声明序"

    # 支 4
    for name, owner in _ALERTS_PUBLIC_BASELINE:
        owner_module = importlib.import_module(owner)
        owned = getattr(owner_module, name, None)
        assert owned is not None, (
            f"所有者模块 {owner} 上没有 {name}，同一性比对会退化成 None is None"
        )

    # 支 5：穷尽（AST 口径，不与 dir() 同源）
    for owner in _NO_ALL_MODULES:
        module = importlib.import_module(owner)
        expected = {n for n, o in _ALERTS_PUBLIC_BASELINE if o == owner}
        defined = _public_top_level_definitions(module)
        assert defined == expected, (
            f"{owner} 的公有顶层定义与公开面基线不同步："
            f"只在源码里（加了却没登记）= {sorted(defined - expected)}；"
            f"只在基线里（已被删掉或改名）= {sorted(expected - defined)}"
        )
    # alerts.py 那一份用 __all__ 与 AST 互为充要（它写了 __all__，故两侧都能取）
    defined_domain = _public_top_level_definitions(alerts_domain)
    assert defined_domain == set(domain_names), (
        f"app.domain.alerts 的公有顶层定义与 __all__ 不同步："
        f"只在源码里 = {sorted(defined_domain - set(domain_names))}；"
        f"只在 __all__ 里 = {sorted(set(domain_names) - defined_domain)}"
    )

    # 支 6（红输入，硬规矩 #50）
    assert list(alerts_domain.__all__) != domain_names + ["__NOT_IN_THE_PUBLIC_FACE__"]
    assert list(alerts_domain.__all__) != domain_names[:-1]


def test_refdata_alerts_does_not_write_an_all_and_does_not_import_the_db():
    """``app.refdata_alerts`` **不写** ``__all__``（P6-A5），且**不 import** ``app.db``。

    后半句是分层：加载器的职责是「YAML → 值对象」，落库是 Task 7 的
    ``app/pipeline/alert_stage.py`` 的活（口径同 :mod:`app.refdata_prescription`，
    它 import ``app.db`` 只为 ``sync_*`` 两个投影入口，而本模块**没有**投影入口
    ——``alert_rules`` 不入库，spec §4.4 逐字「不入库」）。
    """
    assert getattr(refdata_alerts, "__all__", None) is None
    tree = ast.parse(pathlib.Path(refdata_alerts.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(("." * node.level) + node.module)
    assert [n for n in imported if n.startswith("app.db")] == [], imported
    # ⚠️ 字面钉住整张 import 表（硬规矩 #35 的期望侧）：``app`` 是
    #    ``from app import refdata_yaml`` 那一句的模块串（被导入的名字住在 node.names 里，
    #    口径见 tests/architecture/test_domain_purity.py 的 _imported_modules docstring）。
    assert sorted(imported) == [
        "app", "app.domain.alerts", "app.refdata", "pathlib", "types", "yaml",
    ], sorted(imported)


def test_the_filename_constant_is_the_only_owner_of_the_yaml_name():
    """``alert_rules.yaml`` 这个文件名只有 :data:`refdata_alerts.ALERT_RULES_FILENAME` 一份。

    AST 扫 ``backend/app/`` 下全部 ``.py``，要求那个字面串**只出现在这一个模块里**
    （硬规矩 #89 的再扩写：数「一个名字有几份定义」用 AST，这里数的是「一个字面串有几份」，
    口径是 ``ast.Constant``，不是正则——正则会把 docstring 里的举例也算成一份所有者，
    而散文里提一提不构成第二个住址）。
    """
    literal = "alert_rules.yaml"
    homes: list[str] = []
    for py in sorted(APP_DIR.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == literal:
                homes.append(py.relative_to(APP_DIR.parent).as_posix())
                break
    assert homes == ["app/refdata_alerts.py"], homes
    assert refdata_alerts.ALERT_RULES_FILENAME == literal
    assert (DATA_DIR / literal).is_file()

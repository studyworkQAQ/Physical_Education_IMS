# backend/tests/test_refdata_alerts.py
"""``app/refdata_yaml.py``（共用 YAML 助手）的**单一所有者**守卫（Plan 03 Task 6，P6-A2）。

计划正文对第二个 YAML 加载器给的处置是「**直接照抄那套形状**，不要另发明一套」。
⚠️ 「照抄」在字面上等于复制，而**复制就是第二个所有者**（Global Constraint #3）。
故那 6 个通用助手被抽进 :mod:`app.refdata_yaml`，两个加载器
（:mod:`app.refdata_prescription` / :mod:`app.refdata_alerts`）都从它 import。

**本文件守的就是「抽干净了」这件事**，而它**不能靠散文**：一个模块 docstring 里写着
「本模块的助手来自 refdata_yaml」，与那个模块里躺着一份 30 行的副本，两者读起来一样。
故三支全部是机器可查的：

* **支 1（定义点唯一）**：AST 扫 ``backend/app/`` 下全部 ``.py``，6 个名字各只允许有
  **一处** ``def``、且那一处在 :mod:`app.refdata_yaml`（硬规矩 #89 的再扩写：数「一个
  名字有几份定义」用 AST，不用正则数源码——正则数不出「同名但换了个前导下划线」的那一份）。
* **支 2（适配器只转发、不重实现）**：每个消费者里的 ``_fail`` / ``_exact_keys`` /
  ``_as_int`` / ``_as_float`` / ``_as_optional_text`` 的函数体必须**恰好一句**、且那一句
  是对 ``refdata_yaml.<同名>`` 的调用并带上 ``doc_kind=``。⚠️ 这一支是**唯一**抓得住
  「把逻辑复制回加载器」的：那种情况下支 1 仍然全绿（复制品叫 ``_fail``、不叫 ``fail``），
  而行为也仍然全对——只有「函数体长度 + 它在调谁」这个形状会露馅。
* **支 3（``_line_index`` 是同一个对象，不是副本）**：身份比对（``is``）。它不需要
  ``doc_kind``，故两处直接别名引用；``is`` 因此必须成立。

⚠️ **``doc_kind`` 为什么必须存在**（计划的 P6-A2 没提，实现者顶回后补的）：
``fail`` 的消息前缀原先在 :mod:`app.refdata_prescription` 里**硬编码**成 ``"处方模板"``。
原样搬进共用模块的话，``alert_rules.yaml`` 被改坏时报出来的会是「处方模板
…/alert_rules.yaml 第 3 行」——指着一份预警阈值文件说它是处方模板，Review Focus 第 5 条
要的「指出是哪个文件哪一行哪个键」当场变成假话。它是**必填关键字参数、没有缺省值**，
于是「忘了传」是 ``TypeError``（响亮）而不是「静默用别人的措辞」。
:func:`test_doc_kind_is_bound_per_consumer_and_has_no_default` 把这两半都钉住。

**期望侧一律字面写死**（硬规矩 #35）：6 个名字、5 个适配器名、两个 ``doc_kind`` 的中文
措辞都写在本文件里，**不从** :data:`app.refdata_yaml.__all__` 反推。
"""
import ast
import importlib
import inspect
import pathlib

import pytest

from app import refdata_yaml

#: ``backend/app/``。支 1 的扫描面：``app/`` 下全部 ``.py``（含子包），不含 ``tests/``。
APP_DIR = pathlib.Path(refdata_yaml.__file__).resolve().parent

#: 抽出来的 6 个通用助手。**字面写死**，不读 ``refdata_yaml.__all__``（硬规矩 #35）：
#: 谁往 ``__all__`` 里加一个名字而忘了在 :mod:`app.refdata_yaml` 里定义它，
#: 支 1 的 ``definitions[name]`` 就是空列表 → 当场红。
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
#: （它由支 3 的身份比对看着）。
_ADAPTERS = {
    "_fail": "fail",
    "_exact_keys": "exact_keys",
    "_as_int": "as_int",
    "_as_float": "as_float",
    "_as_optional_text": "as_optional_text",
}

#: 消费者 → 它给自己那份 YAML 绑的**文档种类**。措辞字面写死：支 4 要拿它去比报错文本的
#: 开头，两侧因此不同源（一侧是本字面量，另一侧是 ``refdata_yaml.fail`` 现拼出来的串）。
_CONSUMERS = {
    "app.refdata_prescription": "处方模板",
}


def _definitions_of(name: str) -> list[str]:
    """``backend/app/`` 下所有 ``def <name>`` 的**定义点**（``app/x/y.py`` 形式，升序）。

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


def test_the_six_shared_yaml_helpers_have_exactly_one_definition_site():
    """支 1：6 个助手在 ``app/`` 下**各只有一处** ``def``，且都在 :mod:`app.refdata_yaml`。

    ⚠️ **这一支单独是抓不住「复制回加载器」的**（复制品通常带前导下划线、名字不同），
    它抓的是另一个方向：谁在别的模块里**再定义一个同名的** ``fail`` / ``as_int``。
    与支 2 合起来才封住两个方向（硬规矩 #51：两份守卫各守一个方向）。
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
    # 反向空转守卫：APP_DIR 指错时 rglob 返回空、上面每条都得到 []，offenders 反而非空——
    # 但为了不让「指错目录」与「真有第二份」报同一种错，这里单独钉一下扫描面本身。
    assert len(list(APP_DIR.rglob("*.py"))) >= 20, f"扫描面可能被指错了: {APP_DIR}"


def test_every_consumer_binds_doc_kind_through_a_one_statement_adapter():
    """支 2：每个消费者的 5 个 ``_`` 适配器**只转发**，不重实现。

    判据是三条同时成立：① 函数体**恰好一句**（除去它自己的 docstring，见
    :func:`_code_of`）；② 那一句（``return …`` 或裸表达式）是对
    ``refdata_yaml.<同名去掉下划线>`` 的调用；③ 调用里带了 ``doc_kind=`` 关键字。
    三条合起来把「把 30 行逻辑复制回加载器」这个形状排除掉——那种情况下 ① 就不成立。

    ⚠️ **为什么不用「源码里搜 ``yaml.compose``」这类判据**：那会随实现细节漂
    （哪天 :func:`app.refdata_yaml.line_index` 改了实现，这条守卫就变成一条与
    「有没有第二份所有者」无关的断言）。「函数体一句 + 调的是谁」是**结构**判据，
    与被调方的内部实现无关。
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
            if len(_code_of(node)) != 1:
                offenders.append(
                    f"{module_name}.{adapter} 的函数体有 {len(_code_of(node))} 句"
                    "（除去它自己的 docstring），应恰好 1 句"
                    "（多于 1 句 = 逻辑被复制回了加载器，P6-A2 要消灭的正是这个）"
                )
                continue
            statement = _code_of(node)[0]
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
    """支 3：``_line_index`` 在各消费者里**就是** :func:`app.refdata_yaml.line_index`。

    :func:`app.refdata_yaml.line_index` 不需要 ``doc_kind``，故它没有适配器、而是直接
    别名引用。``is`` 因此必须成立：一份副本会让支 1 与支 2 同时全绿（副本叫
    ``_line_index``、函数体也只有一句 ``return``……不，它会是 30 行），故本支是
    「别名而不是复制」这件事**最直接**的判据。
    """
    for module_name in _CONSUMERS:
        module = importlib.import_module(module_name)
        assert module._line_index is refdata_yaml.line_index, (
            f"{module_name}._line_index 不是 app.refdata_yaml.line_index 那个对象："
            "它被复制了一份（P6-A2 要消灭的第二个所有者）"
        )


def test_doc_kind_is_bound_per_consumer_and_has_no_default():
    """支 4：``doc_kind`` 是**必填关键字参数**，且每个消费者绑的是自己那份措辞。

    两半都要钉：

    * **没有缺省值**——``inspect.signature`` 上它必须是 ``Parameter.empty``。带缺省值的
      话，「新加载器忘了传」会静默用别人的文档种类去报错，而那正是本参数要防的事。
    * **绑对了**——各消费者的 ``_fail`` 现拼出来的消息必须以它自己那个中文措辞开头。
      期望侧是 :data:`_CONSUMERS` 里的字面量，实际侧是 ``refdata_yaml.fail`` 拼出来的串，
      两侧不同源（硬规矩 #35）。
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
    """支 5：:mod:`app.refdata_yaml` 是叶子——不 import ``app`` 里的任何东西。

    与 :mod:`app.config` 同档的理由：一个**被两个加载器共用**的模块若反过来 import 它的
    消费者，环就出来了。它今天只 import :mod:`pathlib` 与 :mod:`yaml`，本支把这件事钉住，
    于是「将来有人为了方便把 ``DATA_DIR`` 搬进来」会当场红（那会让
    ``app.refdata_yaml → app.refdata → app.config`` 这条边出现，而
    :mod:`app.refdata` 自己又 import ``app.domain``，共用助手从此不再是叶子）。
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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))

"""**依赖清单守卫**：后端 ``pyproject.toml`` 与前端 ``package.json`` 的依赖表逐字钉死。

--------------------------------------------------------------------------
为什么会有这个文件（控制者 2026-10-13 的新裁定）
--------------------------------------------------------------------------

Plan 06 Task 1 引入 ``alembic`` 时，控制者发现：**今天没有任何东西拦「悄悄加一个后端
依赖」**。他以为有的那一条 sha256 指纹测试，钉的其实是 ``backend/data/**``
（国标 CSV / 指标区间 / 18 套处方模板），与依赖表毫无关系。

于是「**alembic 是用户批准的唯一新增后端依赖**」这句话在 Plan 06 Task 1 落地的那一刻
是**真的**，而在下一秒就变成一句**没人看着**的话：任何一次 ``pip install X`` +
往 ``pyproject.toml`` 里加一行，全量 1370 条测试**一条都不会红**。
前端那一侧同理——``frontend/package.json`` 的 ``"//"`` 注释里逐字写着
「本前端**零新增依赖**（Plan 01 至本波全程）」，而那也只是一句散文。

本文件把那两句话变成可执行的：**依赖表的单一所有者是本文件里那四份字面清单**，
加一个依赖必须改这里 = **一个刻意的动作**（而不是「顺手 ``pip install``」）。

--------------------------------------------------------------------------
⚠️ 判据是**显式清单**、不是哈希（控制者逐字要求）
--------------------------------------------------------------------------

一个 sha256 指纹也能钉住「不许变」，而它有两个致命缺点：

1. **报错时看不出多了什么**。运维/下一个实现者拿到的是一串十六进制，
   他必须自己去 ``git diff`` 那个文件才知道变的是哪一行——而「指纹红了」
   在历史上（本仓的 ``backend/data/**`` 那四个指纹）恰恰是**最容易被调松**的一类守卫，
   因为「更新指纹」看起来是一次机械动作；
2. **它把「加了什么」与「改了顺序/注释」混成一档**。一份显式清单只对**集合**敏感
   （本文件按 ``sorted(...)`` 比较），故「把依赖表里的两行换个顺序」不会红，
   而「多了一个 ``requests``」会红，且报错里逐字印出那个名字。

故报错消息里**实测与期望两侧都打出来**，并额外给出「多了什么 / 少了什么」两个差集。

--------------------------------------------------------------------------
⚠️ 它守不住什么（硬规矩 #39）
--------------------------------------------------------------------------

* **它不守「装了什么」**：判据是两份**清单文件**，不是 ``pip list`` / ``node_modules``。
  于是一个「装了但没写进清单」的依赖是抓不到的（而它会让代码在甲方的机器上
  ``ImportError``）。⚠️ 那一档今天由**全量测试**兜住：本机没装就跑不过。
  反过来「写进清单但没装」同样由全量测试兜住。
* **它不守传递依赖**：``alembic`` 自己带一个 ``Mako``（实测 1.4.3），
  ``fastapi`` 带 ``starlette`` 与 ``pydantic``。本清单刻意**不**重复钉它们
  （重复钉就是第二个所有者，而它们的版本由上游的 ``pyproject`` 决定）。
  ⚠️ 唯一的例外是 ``alembic==1.20.0`` 那一格**精确钉死**——理由逐字写在
  ``backend/pyproject.toml`` 里那条依赖旁边的注释上（autogenerate 会把它自己对 DDL
  的渲染写进**入库的迁移脚本**，故「用哪个 alembic 生成的」是迁移脚本本身的一部分事实）。
* **它不守 ``frontend/package-lock.json``**：那一份是 npm 自己写的、体量巨大、
  且它的内容由 ``package.json`` + registry 状态决定。钉它会让「一次 ``npm install``
  换了个镜像」变成一次守卫失败。⚠️ 于是「同一个 ``package.json`` 在不同时间
  ``npm install`` 出不同的树」这一档今天没有守卫，如实记录。

--------------------------------------------------------------------------
⚠️ 本文件**只 import 标准库**（``tomllib`` 是 3.11 的新增，``json`` 是老朋友）
--------------------------------------------------------------------------

``tomllib`` 因此**不是**一个新依赖（它在 ``requires-python = ">=3.11"`` 的范围内是
标准库）。⚠️ 刻意**不用** ``tomli`` / ``pytoml`` 一类三方包：为了读一个 TOML 而加一个
依赖，恰好是本文件要防的那件事。
"""
import json
import tomllib

from app.config import BACKEND_DIR

#: ``backend/pyproject.toml`` 与 ``frontend/package.json``。⚠️ **字面路径**，
#: 不从任何被测模块读回来：``BACKEND_DIR`` 来自 :mod:`app.config`（它是
#: 「这个项目在磁盘上长什么样」的唯一住址），而仓库根是它的 ``parent``。
PYPROJECT = BACKEND_DIR / "pyproject.toml"
PACKAGE_JSON = BACKEND_DIR.parent / "frontend" / "package.json"

#: ---------------------------------------------------------------------------
#: **后端**：``[project] dependencies``（**排序后逐字**等于本清单）
#: ---------------------------------------------------------------------------
#:
#: ⚠️ **七项**，其中**只有一项**带精确版本（``alembic==1.20.0``）——
#: 那一格的理由逐字写在 ``pyproject.toml`` 里它旁边的注释上，本处不复述第二份。
#: ⚠️ 它是「本计划唯一新增的后端依赖」（用户 2026-10-13 裁定），
#: 故 Plan 06 结案时本清单**必须**仍然是这七项；第八项就是一次需要用户重新批准的动作。
BACKEND_DEPENDENCIES = [
    "alembic==1.20.0",
    "fastapi",
    "numpy",
    "pandas",
    "pyyaml",
    "sqlalchemy>=2.0",
    "uvicorn[standard]",
]

#: ---------------------------------------------------------------------------
#: **后端**：``[project.optional-dependencies]`` 的全部组（今天只有一个 ``dev``）
#: ---------------------------------------------------------------------------
#:
#: ⚠️ **组名也被钉住**：少了这一格，「新加一个 ``[project.optional-dependencies] test``」
#: 是一次**静默**的动作（本文件的其余断言一条都不会碰到它）。
BACKEND_OPTIONAL_GROUPS = ["dev"]

BACKEND_DEV_DEPENDENCIES = [
    "httpx",
    "pytest",
    "pytest-cov",
]

#: ---------------------------------------------------------------------------
#: **后端**：``[build-system] requires``
#: ---------------------------------------------------------------------------
#:
#: ⚠️ 它**也是**一张依赖表（构建期装的），故一并钉住：一个「顺手加个
#: ``setuptools-scm``」的动作与「顺手加个 ``requests``」在「甲方机器上多装了一个包」
#: 这件事上没有区别。
BACKEND_BUILD_REQUIRES = [
    "setuptools>=68",
]

#: ---------------------------------------------------------------------------
#: **前端**：``dependencies`` 与 ``devDependencies``（两个集合各自排序后逐字相等）
#: ---------------------------------------------------------------------------
#:
#: ⚠️ **钉的是键与版本区间两者**（``"vue": "^3.5.43"`` 整个 ``"名: 区间"`` 串），
#: 因为「把 ``^`` 改成 ``*``」与「加一个新包」在「甲方的构建产物会变」这件事上
#: 是同一类动作。⚠️ 于是 ``npm update`` 之后 ``package.json`` 里的区间若被 npm 改写，
#: 本守卫会红——那是**要的**（一次依赖升级应当是一个刻意的动作）。
#: ⚠️ ``frontend/package.json`` 的 ``"//"`` 注释逐字写着「本前端**零新增依赖**
#: （Plan 01 至本波全程；派单允许的 Playwright/Puppeteer 最终没有引入）」，
#: 本清单是那一句的可执行形式。
FRONTEND_DEPENDENCIES = [
    "pinia: ^3.0.4",
    "vue: ^3.5.43",
    "vue-router: ^4.6.4",
]

FRONTEND_DEV_DEPENDENCIES = [
    "@types/node: ^24.13.3",
    "@vitejs/plugin-vue: ^6.0.10",
    "@vue/tsconfig: ^0.9.1",
    "openapi-typescript: ^7.13.0",
    "typescript: ~5.9.3",
    "vite: ^8.3.4",
    "vue-tsc: ^3.3.13",
]

#: ``package.json`` 里**允许存在**的「依赖形状」的键。⚠️ 钉住它的理由与
#: :data:`BACKEND_OPTIONAL_GROUPS` 逐字相同：一个 ``peerDependencies`` /
#: ``optionalDependencies`` / ``bundledDependencies`` 是**同一类**东西，
#: 而它今天一个都没有；不钉的话「加一个 ``optionalDependencies``」是静默的。
FRONTEND_DEPENDENCY_KEYS = ["dependencies", "devDependencies"]


def _diff_message(label: str, actual: list[str], expected: list[str]) -> str:
    """一份**两侧都印出来**的报错（控制者逐字要求：不要用 sha256，要看得出多了什么）。"""
    added = sorted(set(actual) - set(expected))
    removed = sorted(set(expected) - set(actual))
    return (
        f"{label} 与守卫里写死的清单不一致。\n"
        f"  实测（{len(actual)} 项，已排序）: {sorted(actual)}\n"
        f"  期望（{len(expected)} 项，已排序）: {sorted(expected)}\n"
        f"  多了: {added}\n"
        f"  少了: {removed}\n"
        f"  ⚠️ 加一个依赖必须是一次**刻意的动作**：改本文件里那一份清单"
        f"（它是依赖表的单一所有者），并在 commit 信息里说明谁批准了它。"
        f"后端今天被批准的新增依赖只有 alembic 一个（用户 2026-10-13 裁定），"
        f"前端新增依赖是 0。"
    )


def _pyproject() -> dict:
    assert PYPROJECT.is_file(), PYPROJECT
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)


def _package_json() -> dict:
    assert PACKAGE_JSON.is_file(), PACKAGE_JSON
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


def _flat(mapping: dict) -> list[str]:
    """``{"名": "区间"}`` → ``["名: 区间", …]``（⚠️ 分隔符是 ``": "``，与 npm 自己的
    ``npm ls --json`` 输出同形，故报错里的串可以直接拿去搜）。"""
    return [f"{key}: {mapping[key]}" for key in mapping]


# ---------------------------------------------------------------------------
# 后端
# ---------------------------------------------------------------------------


def test_the_backend_runtime_dependencies_are_exactly_the_approved_seven():
    """``[project] dependencies`` **排序后逐字**等于 :data:`BACKEND_DEPENDENCIES`。

    ⚠️ 这是本文件的主守卫：它把「alembic 是用户批准的唯一新增后端依赖」
    从一句散文变成一个红/绿的判据。
    """
    document = _pyproject()
    actual = sorted(document["project"]["dependencies"])
    assert actual == sorted(BACKEND_DEPENDENCIES), _diff_message(
        "backend/pyproject.toml [project] dependencies", actual, BACKEND_DEPENDENCIES
    )
    # ⚠️ 反空转：清单本身不是空的、且它真的有七项（少了本行，
    #    「把期望清单删空、把依赖表也删空」会两侧同为 [] 而全绿）
    assert len(BACKEND_DEPENDENCIES) == 7
    assert "alembic==1.20.0" in actual


def test_the_backend_optional_dependency_groups_are_exactly_dev():
    """``[project.optional-dependencies]`` **只有 ``dev`` 一组**，且它的清单也逐字相等。

    ⚠️ 两格：① 组名集合 == ``{"dev"}``（新加一组必须是一次显式的清单修改）；
    ② ``dev`` 那一组的依赖排序后逐字等于 :data:`BACKEND_DEV_DEPENDENCIES`。
    """
    document = _pyproject()
    groups = document["project"].get("optional-dependencies", {})
    assert sorted(groups) == sorted(BACKEND_OPTIONAL_GROUPS), (
        f"[project.optional-dependencies] 的组变了：实测 {sorted(groups)}、"
        f"期望 {sorted(BACKEND_OPTIONAL_GROUPS)}。⚠️ 新加一组等于新开一张依赖表，"
        f"而本文件对其余各组一条断言都没有 —— 故加组必须连它的清单一起加进本文件。"
    )
    actual = sorted(groups["dev"])
    assert actual == sorted(BACKEND_DEV_DEPENDENCIES), _diff_message(
        "backend/pyproject.toml [project.optional-dependencies].dev",
        actual, BACKEND_DEV_DEPENDENCIES,
    )
    assert len(BACKEND_DEV_DEPENDENCIES) == 3


def test_the_backend_build_requires_are_unchanged():
    """``[build-system] requires`` 也是**一张依赖表**，故一并钉住。"""
    document = _pyproject()
    actual = sorted(document["build-system"]["requires"])
    assert actual == sorted(BACKEND_BUILD_REQUIRES), _diff_message(
        "backend/pyproject.toml [build-system] requires", actual, BACKEND_BUILD_REQUIRES
    )
    assert document["build-system"]["build-backend"] == "setuptools.build_meta"


# ---------------------------------------------------------------------------
# 前端
# ---------------------------------------------------------------------------


def test_the_frontend_dependency_maps_are_exactly_the_documented_ones():
    """``dependencies`` 与 ``devDependencies`` **两个集合各自**排序后逐字相等。

    ⚠️ **本仓此前没有这一条**（实现者按派单 §3 的要求先 ``Grep`` 过：
    ``frontend/scripts/`` 下的三个 ``.mjs`` 分别是 ``check-tokens``（色值唯一住址）、
    ``check-dist``（生产构建里没有 ``adoptFromUrl``）与 ``smoke``（联调），
    没有一个是依赖守卫；``backend/tests/**`` 下也一条都没有）。
    故本条是**新建的唯一所有者**，而不是「把既有的那一条扩成含 devDependencies」
    ——派单 §3 要求的是后者**若已存在**，实测不存在。
    """
    document = _package_json()
    actual_runtime = _flat(document.get("dependencies", {}))
    actual_dev = _flat(document.get("devDependencies", {}))

    assert sorted(actual_runtime) == sorted(FRONTEND_DEPENDENCIES), _diff_message(
        "frontend/package.json dependencies", actual_runtime, FRONTEND_DEPENDENCIES
    )
    assert sorted(actual_dev) == sorted(FRONTEND_DEV_DEPENDENCIES), _diff_message(
        "frontend/package.json devDependencies", actual_dev, FRONTEND_DEV_DEPENDENCIES
    )
    # ⚠️ 反空转：两份期望清单都不是空的
    assert len(FRONTEND_DEPENDENCIES) == 3
    assert len(FRONTEND_DEV_DEPENDENCIES) == 7


def test_the_frontend_has_no_other_dependency_shaped_key():
    """``package.json`` 里**不得**出现第二张依赖表（``peerDependencies`` 一类）。

    ⚠️ 判据是「键名以 ``ependencies`` 结尾的，恰好是
    :data:`FRONTEND_DEPENDENCY_KEYS` 那两个」，而不是一份硬编码的黑名单：
    npm 认的依赖形状键至少有五个（``dependencies`` / ``devDependencies`` /
    ``peerDependencies`` / ``optionalDependencies`` / ``bundledDependencies``），
    逐个列出来的话下一个新形状（npm 将来加的）会静默溜过去。
    ⚠️ 用后缀匹配而不是 ``== "dependencies" or …``：它同时抓住
    ``peerDependenciesMeta`` 这类**元数据**键——那一类今天也没有，
    而它同样是一次「往依赖这一格里加东西」的动作。
    """
    document = _package_json()
    observed = sorted(
        key for key in document
        if key.endswith("ependencies") or key.endswith("ependenciesMeta")
    )
    assert observed == sorted(FRONTEND_DEPENDENCY_KEYS), (
        f"frontend/package.json 里出现了本守卫不认的依赖形状键：实测 {observed}、"
        f"期望 {sorted(FRONTEND_DEPENDENCY_KEYS)}。⚠️ 新加一张依赖表必须连它的清单"
        f"一起加进本文件（否则「前端零新增依赖」那句话当场变假，而没有任何测试会红）。"
    )


def test_both_manifests_really_are_the_two_files_the_guard_thinks_they_are():
    """**空转守卫**：两份清单文件真的存在、真的在守卫以为的位置、真的有内容。

    ⚠️ 少了本条，「``BACKEND_DIR.parent`` 不是仓库根」（例如 ``app.config`` 被搬家、
    或前端目录被改名）会让上面那几条**全部**以 ``assert … .is_file()`` 的样子红，
    而报错位置在依赖守卫里、真因在路径常量里。本条把两件事分开报。
    ⚠️ 它**同时**钉住「前端目录叫 ``frontend``」这个事实：
    那是一个跨包的约定（``smoke.mjs`` / ``check-dist.mjs`` / Plan 06 Task 7 的
    ``serve.ps1`` 都按它写路径），而本文件是今天唯一一处从**后端**读它的地方。
    """
    assert PYPROJECT.name == "pyproject.toml" and PYPROJECT.parent.name == "backend"
    assert PACKAGE_JSON.name == "package.json" and PACKAGE_JSON.parent.name == "frontend"
    assert PYPROJECT.parent.parent == PACKAGE_JSON.parent.parent, "两份清单不在同一个仓库根下"

    document = _pyproject()
    assert document["project"]["name"] == "pe-backend"
    assert document["project"]["requires-python"] == ">=3.11"
    frontend = _package_json()
    assert frontend["name"] == "physical-education-ims-frontend"
    assert frontend["private"] is True
    # ⚠️ ``tomllib`` 是 Python 3.11 的标准库（``requires-python = ">=3.11"``），
    #    故本文件**没有**为了读 TOML 而加依赖——那恰好是它要防的事。
    assert tomllib.__name__ == "tomllib"

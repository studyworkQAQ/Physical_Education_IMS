# Plan 03 Task 1 实现者报告 —— FastAPI 骨架 + 依赖注入 + 作用域闸门

> **分支** `feature/plan-03-feedback-alert-crud-api`　**基线** `69b4218`　**结案** `2832a27`
> **结论一句话**：824 passed（基线 807 + 15 + 2），覆盖率四格 **996 / 0 / 288 / 0 / 100% 逐字未变**，
> 扫描面 **35 → 38**，三个禁区指纹逐字不变，`backend/pe.db` **仍不存在**，
> **1 轮 fix round**（修掉一处我自己写出来的假绿断言），**顶回派单 3 处**。

---

## ① 环境与基线复现

### 1.1 import 冒烟（硬规矩 #73）

```
cd backend
python -c "import sqlalchemy, fastapi, uvicorn, httpx, pydantic, yaml; print(sqlalchemy.__version__, fastapi.__version__)"
→ 2.1.3 0.141.1
```

六个包全部导入成功、退出码 0，**没有撞上 `ImportError: DLL load failed`**
（Plan 02 撞过的那一次 Windows Smart App Control 拦 `.pyd`）。故按派单继续开工。

其余版本（`pip show` 与计划正文逐字一致，未复跑）：Starlette 1.7.0 / Pydantic 2.13.5 /
uvicorn 0.54.0 / httpx 0.28.1 / pandas 3.0.6 / numpy 2.4.6 / PyYAML 6.0.3。
Python 3.11.1、**无 venv**（`C:\Python`）。
**本 Task 没有引入任何新依赖**：`backend/pyproject.toml` 一个字没改。

### 1.2 基线逐项复核（开工时亲跑，不是抄派单）

| 项 | 派单/简报声称 | 实测 | 一致 |
|---|---|---|---|
| 分支 | `feature/plan-03-feedback-alert-crud-api` | 同 | ✅ |
| 基线 commit | 派单说 `69b4218`；**简报正文说 `5b4a10c`** | HEAD = `69b4218` | ⚠️ 见下 |
| 工作树 | 干净 | `git status --porcelain` 空 | ✅ |
| 测试基线 | 807 passed | **807 passed in 86.60s**，退出码 0 | ✅ |
| 覆盖率基线 | 996 / 0 / 288 / 0 | **TOTAL 996　0　288　0　100%**，`806 passed, 1 skipped` | ✅ |
| 表数 | 18 | `len(Base.metadata.tables)` = **18** | ✅ |
| 扫描面 | 35（pipeline 8 + db 11 + domain 16） | `[('adapters',5),('api',0),('db',11),('domain',16),('pipeline',8),('seed',8)]` → **8+11+16 = 35** | ✅ |

⚠️ **基线 commit 的两个值不冲突**：`69b4218` 是 `5b4a10c` 的子提交，且是一次**纯 docs**
提交——`git diff 5b4a10c 69b4218 -- backend` **输出为空**（亲跑），它只动了
`Document/…实施计划03….md` 与 `.superpowers/sdd/2026-10-08-…/` 下的 5 个文件。
故简报（从 `5b4a10c` 时的树抽出）与派单（`69b4218`）对 `backend/` 说的是同一棵树。
本报告一律以 **`69b4218`** 为基线（那是开工时 HEAD 的实际值）；
第 ⑤ 节的 `backend/data` diff **两个 rev 都跑了**，都为空。

### 1.3 既有测试目录惯例实测（派单第 4 节点名要的那个实测）

```
cd backend
python -c "import pathlib; print([str(p) for p in pathlib.Path('tests').rglob('__init__.py')])"
→ []
```

* `tests/` 下 **31 个 `.py`**，`__init__.py` **0 个**，根 `tests/conftest.py` **0 个**。
* `pyproject.toml` 的 `[tool.pytest.ini_options]` 只有两行：`testpaths = ["tests"]` 与
  `pythonpath = ["."]`，**没有** `rootdir` / `consider_namespace_packages`。
* → **`tests/api/__init__.py` 没有建**（派单原文是「若既有测试目录有这个惯例就先实测」，
  实测结论是「没有这个惯例」，故按它自己的条件分支不建）。
* basename 冲突检查：31 个既有文件名里**没有** `test_main.py` / `test_scope.py` /
  `conftest.py`（`collections.Counter` 数过，`dup: []`）。`importmode=prepend` 下
  无 `__init__.py` 时 basename 必须唯一，这一条因此是承重的。

### 1.4 `DEFAULT_DB_URL` 今天指向什么（派单坑 #1 要求先实测）

```
DEFAULT_DB_URL = 'sqlite:///C:/Users/whwenhao/Desktop/Physical_Education_IMS/backend/pe.db'
```

**确实就是禁区 `pe.db`**（绝对路径，`as_posix()`）。而且
`tests/test_config.py::test_default_csv_dir_and_db_url_are_pinned_by_literal_suffixes`
用 `assert DEFAULT_DB_URL.endswith("/backend/pe.db")` 把它**字面钉死**了
→ 本 Task **不能改 `app/config.py`**，只能在 `app/main.py` 这一层做覆盖。这条实测
直接决定了下面 3.1 与 ⑥.2 的做法。

---

## ② 六个交付物的最终签名（运行时口径，`inspect.signature` 逐字抄）

```
app.main.create_app(*, db_url: str | None = None) -> fastapi.applications.FastAPI
app.api.deps.get_db(request: starlette.requests.Request) -> collections.abc.Iterator[sqlalchemy.orm.session.Session]
app.api.deps.current_student(x_student_id: int | None = Header(None)) -> int
app.api.deps.current_teacher(x_teacher_staff_no: str | None = Header(None)) -> str
app.api.deps.require_scope(session: sqlalchemy.orm.session.Session, student_id: int, requester_id: int) -> None
```

`Page`（Pydantic `BaseModel`，2 个字段）：

```
limit : int  default=50  metadata=[Ge(ge=1), Le(le=200)]
offset: int  default=0   metadata=[Ge(ge=0)]
Page()                      -> {'limit': 50, 'offset': 0}
Page(limit=200, offset=7)   -> {'limit': 200, 'offset': 7}
```

三个常量与三份 `__all__`（`len()` 口径）：

```
DB_URL_ENV_VAR = 'PE_DB_URL'
DEMO_DB_URL    = 'sqlite:///C:/Users/whwenhao/Desktop/Physical_Education_IMS/backend/pe_demo.db'
DEFAULT_DB_URL = 'sqlite:///C:/Users/whwenhao/Desktop/Physical_Education_IMS/backend/pe.db'

app.api.deps.__all__   = ['Page','current_student','current_teacher','get_db','require_scope']  len=5
app.api.errors.__all__ = ['error_response','register_error_handlers']                           len=2
app.main.__all__       = ['DB_URL_ENV_VAR','DEMO_DB_URL','create_app']                          len=3
app/api/__init__.py    = 0 字节（计划 File Structure 写「空」，与 app/db/__init__.py 同惯例）
```

`create_app(db_url="sqlite://")` 返回的对象：

```
type: FastAPI | title: 体育闭环原型系统 | version: 0.3.0
routes: ['/api/health', '/docs', '/docs/oauth2-redirect', '/openapi.json', '/redoc']   len=5
exception_handlers: 7 = 我注册的 6 个（Exception / HTTPException / IntegrityError /
    NoResultFound / RequestValidationError / ValueError）+ FastAPI 自带的
    WebSocketRequestValidationError
user_middleware: [CORSMiddleware]
state.engine.url: sqlite://            pool: StaticPool
（磁盘 URL 时 pool 是 QueuePool、checkedout() == 0）
```

### 2.1 与计划 Interfaces 的差异（两处，都在 ⑥.2 顶回清单里）

| 计划写的 | 实际交付 | 为什么 |
|---|---|---|
| `get_db() -> Iterator[Session]` | `get_db(request: Request) -> Iterator[Session]` | 无参版本只能从**模块级全局**取引擎，于是同进程里的两个应用会共用后建的那个引擎；而 `tests/api/conftest.py` 的 `app` 夹具是 function 级的 |
| `db_url` 缺省时取 `DEFAULT_DB_URL` | 缺省时先看 `PE_DB_URL` 环境变量，再看 `DEFAULT_DB_URL` | `uvicorn app.main:app` 加载的是**模块级** `app`，命令行上没有任何位置能塞 `db_url`；没有这个口子，Step 4 与 `pe.db` 禁区不可兼得 |

其余四个（`create_app` / `current_student` / `current_teacher` / `require_scope` / `Page`）
与计划**逐字相同**。`GET /api/health` 的响应形状也逐字相同：
`{"status": "ok", "tables": <int>, "students": <int>}`。

---

## ③ 架构守卫加 `api` 层的做法

### 3.1 实测：两份守卫**各自**怎么发现「哪些目录属于哪一层」

派单坑 #3 要求先实测这件事，两份的答案**不一样**：

| | `test_layering.py` | `test_domain_purity.py` |
|---|---|---|
| 发现目录的机制 | **一份硬编码的目录名清单** `SCANNED_DIRS = ("pipeline","db","domain")`，交给 `_py_files(relative_dir)` 去 `APP / relative_dir` 下 `rglob("*.py")` | **一条硬编码路径常量** `DOMAIN = parents[2]/"app"/"domain"`，`_domain_files()` 只 `rglob` 它自己那一个目录 |
| 会不会自动收进新目录 | **不会**（清单要人加） | **不会**（而且它压根不想知道别的目录） |
| 判定函数 | `_is_forbidden`（**黑名单**：`app.seed` 前缀，`.` 边界） | `_is_allowed`（**白名单**：`ALLOWED_MODULES` 6 项 + `app.domain` 前缀） |
| 空转守卫 | `root.is_dir()` + `len(scanned) >= 8` | `DOMAIN.is_dir()` + `_assert_not_empty` 的 `len(scanned) >= 5` |

`ALLOWED_MODULES` 与 `_absolute` / `resolve_name` 那套相对导入折算机制
**不会因为多一层而误判**，理由是它们的输入只有「源文件所在的包」：

* `_package_of(py)` = `py.relative_to(BACKEND).with_suffix("").parts[:-1]`，
  对 `app/api/routers/x.py` 给出 `("app","api","routers")`——包深自动跟进，
  不需要有人为新一层加行。这一点**已经被既有守卫自己看着**：
  `test_absolute_folding_matches_resolve_name` 末尾那段「扫真仓」把 `backend/` 下
  **每个** `.py` 的 `_package_of(py)` 与 `py.relative_to(BACKEND).parent.parts` 对拍
  （Plan02 Ruling 66 / C-fr4-1），我新加的 7 个 `.py` 因此自动进了那一圈，全绿。
* purity 的白名单只作用于 `app/domain/**`，`app/api/` 里 import `fastapi` / `pydantic`
  与它**完全无关**。
* `_imported_modules` 的「一名一条展开」与 `_absolute` 的越界档都只依赖 `(module, level, package)`
  三个入参，与「有几层」无关。**两份 `_absolute` 一个字都没动**
  （硬规矩 #51 要求两份逐字相同，动一边就破坏它）。

### 3.2 照哪一套机制加的

**只改了 `test_layering.py`，一个字没动 `test_domain_purity.py`**（后者不在计划的
Modify 清单里，且它的机制与「加一层」无关）。具体五处：

1. `SCANNED_DIRS` 加第四项 `"api"` → 既有的
   `test_production_layers_never_import_app_seed` **自动**把 `app/api/**` 纳入
   「不得 import `app.seed`」的约束（不需要为它写第二份扫描循环）。
2. 新增 `API_PREFIX = "app.api"` 与 `API_ALLOWED_PREFIXES`（10 项）+ `_is_api_allowed()`。
   判定口径**照抄** `_is_forbidden` 的 `.` 边界写法（`module == prefix or
   module.startswith(prefix + ".")`），不另发明一套。
3. 新增 `test_api_layer_dependency_direction_is_one_way`：**复用同一份**
   `_py_files` / `_package_of` / `_imported_modules`（故函数内导入也被覆盖），
   只换判定函数。正向扫 `api`，反向扫「`SCANNED_DIRS` 减掉 `api`」——
   写成减法而不是硬列三个目录名，于是**将来再加一层会自动纳入反向约束**，
   不必有人记得同步第二处清单（单一所有者）。
4. 新增 `test_api_allow_list_matches_on_dot_boundaries`：22 格判定矩阵
   （13 GREEN + 9 RED），是第 3 条的**红档半边**（硬规矩 #50：真仓今天一条 offender
   都没有，只有矩阵能证明这条守卫不是恒绿）。期望颜色一律字面写死（硬规矩 #35）。
5. 抬 `len(scanned)` 的空转下界（见 3.3）。

**`API_ALLOWED_PREFIXES` 的取值与计划 Interfaces 的差异**（两处，各有理由，都写进了注释）：

* **多列 `app.adapters`**。计划写的是「`db` / `domain` / `pipeline` / `refdata*` /
  `config` / `notify`」。spec §3.3 里 `adapters` 在 `pipeline` **下面**
  （`pipeline → adapters`），故 `api → adapters` 不是反向。它今天用不上，
  但 **Task 9 的 `POST /api/pipeline/run-daily` 会撞上**：
  `app.pipeline.daily.run_daily` 的第四个参数是**适配器实例**
  （`daily.py` 的 CLI 那一行是 `run_daily(session, semester.id, args.date, build_adapter())`），
  而 `build_adapter` 住在 `app.adapters.factory`。不列进来的话 Task 9 要么改本清单、
  要么在端点里绕过工厂手搓适配器。
* **`refdata*` 按 `.` 边界展开成三个具体串**（`app.refdata` / `app.refdata_prescription` /
  `app.refdata_alerts`），不用裸前缀。理由：`app.refdata_prescription` 与 `app.refdata`
  之间是**下划线**而不是点，故裸 `startswith("app.refdata")` 与「按 `.` 边界匹配」
  对 `app.refdatax` 给出**不同**答案。矩阵里 `("app.refdatax","RED")` 那一格就是钉这件事的。
  `app.refdata_alerts` 由 Task 6 建、**今天还不存在**——allow-list 里列一个尚不存在的
  模块是**许可、不是断言**，列在这里正是为了兑现 S6 的「后面 8 个 Task 不再动本文件」。
* **刻意不在清单里**：`app.seed`（既有那条守卫已经挡着，本清单是第二道，判据不同）、
  `app.main`（它在 `api` **之上**、是装配 `api` 的那个人，`api` 反过来 import 它就是导入环）、
  `app.demo_data`（Task 2 的演示数据生成器；端点要造演示数据是一次需要**显式改清单**的
  决定，不是顺手一句 import）。三格都在矩阵里列成 RED。

### 3.3 下界断言抬到了什么值、依据是什么

**只有一条下界需要抬**：`test_production_layers_never_import_app_seed` 里那句
`assert len(scanned) >= 8` → **`>= 18`**。取法是「**四个目录各自的地板之和**」：

```
18 = pipeline 5 + db 5 + domain 5 + api 3
```

* `5` **沿用** `test_domain_purity._assert_not_empty` 已经为 domain 定下的那个数
  （那里实测 6 取 5，给「两个模块合并」这类合法重构留一格）——**不另发明一个**。
  `pipeline`（实测 8）与 `db`（实测 11）用同一个数，因为它们的失效形状相同
  （「整层被搬空」）。
* `api` 取 **3** = 本 Task 落地时 `app/api/` 的实测文件数（`__init__.py` / `deps.py` /
  `errors.py`）。

⚠️ **这一条是对 S6 裁定的一处修正解读，见 ⑥.2 第 3 条**：S6 的措辞是
「下界断言由本 Task 一次性抬到位（含 `api` 那一层），后面 8 个 Task 不再动它」，
并举例「`app/api/` 本计划要建约 15 个 `.py`」。**若把「抬到位」读成「抬到计划结束时
的值」，那条断言今天当场红**——`app/api/` 今天只有 3 个 `.py`，
写下界 18 会让 `len(scanned)` = 38 仍然绿、但写下界 56（计划建满时的聚合值）就是
`38 >= 56` → 红。**下界只能在它已经成立的前提下抬**，故只能抬到「今天的地板之和」= 18。
而「后面 8 个 Task 不再动它」这个目标**照样达成了**，理由是一个单调性论证：
计划剩下的 8 个 Task 只**增加** `app/api/` / `app/domain/` / `app/pipeline/` 下的 `.py`
（File Structure 的新建清单里没有一处删除或合并），故 `len(scanned)` 只增不减，
一个已经成立的下界永远不会被后续 Task 击穿。

顺带把派单举的那个数核准一下：派单说「`app/api/` 本计划要建**约 15 个** `.py`」，
按计划 File Structure 逐行数出来是 **18 个**（`api` 根 4 = `__init__` / `deps` / `crud` /
`errors`；`schemas/` 7 = `__init__` + organisation/assessment/derived/prescription/feedback/alerts；
`routers/` 7 = `__init__` + catalog/feedback/prescription/alerts/dashboard/pipeline）。
`app/main.py` 在 `app/` 根下、**不计入** `app/api/`。故计划建满时聚合值是
pipeline 10 + db 11 + domain 17 + api 18 = **56**，不是 53。这两个数都写进了断言上方的注释。

**代价（硬规矩 #39）也写进了注释**：18 仍挡不住「某一个目录被搬到只剩它自己的地板」。
最坏的一格是 api：建满时（56）把它搬回只剩 3 个是 41 ≥ 18，**仍然绿**。
那一档的兜底与本文件原来的口径相同——`domain` 由 purity 的 `>= 5` 看着；
`pipeline` / `db` / `api` 被搬空时 `tests/pipeline/` / `tests/db/` / `tests/api/`
会在**收集期**就 ImportError；目录被整个删掉则由 `_py_files` 里的 `root.is_dir()` 当场拦下。

**新守卫自己的三条空转下界**（同样是字面量、同样给了推导）：

```
len(api_py)     >= 3    # app/api/ 的 .py 下界 = 本 Task 实测 3（计划建满后 18，故 3 是下界不是预测）
len(reverse_py) >= 15   # 反向那一圈（pipeline+db+domain）= 5×3，与上面那个 18 同源；实测 35
"app.db.models.organisation" in api_folded   # 绿档：app/api/ 下今天唯一一条 app.* 导入
```

第三条是**绿档**（硬规矩 #50）：少了它，「`api_folded` 是空集（循环空转了）」与
「api 一条 `app.*` 都没 import」在颜色上无法区分。

### 3.4 扫描面 35 → **38**

| | pipeline | db | domain | api | 合计 |
|---|---|---|---|---|---|
| 基线 `69b4218` | 8 | 11 | 16 | — | **35** |
| Task 1 结案 | 8 | 11 | 16 | **3** | **38** |
| 计划建满（预测） | 10 | 11 | 17 | 18 | 56 |

（+3 = `app/api/__init__.py` / `deps.py` / `errors.py`。）

### 3.5 取证：三格探针证明新守卫**有牙**、不是恒绿

⚠️ 账本 Ruling 1 裁定本 Task「不做变异」，故只跑**三格**最小取证，
探针脚本写在 `$env:TEMP` 下、每格都在 `try/finally` 里还原现场、跑完即删
（`git status` 与 `app/**/_probe*` 双重复核：无残留）。

| 格 | 变异 | 期望 | 实测 |
|---|---|---|---|
| **G1** | 在内存里把 `_is_api_allowed` 换成**裸 `startswith`** | 判定矩阵红 | **RED** ✅ 报出三格：`_is_api_allowed('app.dbx') 判成 GREEN、期望 RED` / `'app.api_'` / `'app.refdatax'` |
| **G1 对照** | 原样 | 绿 | **GREEN** ✅（`test_api_allow_list_matches_on_dot_boundaries` 与 `test_api_layer_dependency_direction_is_one_way` 都通过） |
| **G2** | 往 `app/domain/_probe_reverse.py` 落一行 `from app.api import deps` | 新方向守卫红 | **exit=1** ✅ `test_api_layer_dependency_direction_is_one_way` 红（`AssertionError: api 层的依赖方向被破坏…`）**且** `test_domain_imports_stay_within_the_allow_list` **也**红 |
| **G3** | 往 `app/api/_probe_seed.py` 落一行 `from app.seed.generate import DEFAULT_DB_URL` | 方向守卫与既有 seed 守卫都红 | **exit=1** ✅ `test_api_layer_dependency_direction_is_one_way` 红 **且** `test_production_layers_never_import_app_seed` 红 |
| 还原 | 删掉两个探针文件后复跑 `tests/architecture` | 8 passed | **exit=0，8 passed in 0.54s** ✅ |

**G2 是派单坑 #3 那个问题的直接答案**：`domain` 的纯净性守卫**不会**因为多了 `api`
这一层而误判——它是**正确地**抓到了 `domain` 里的 `app.api`（`app.api` 既不在
`ALLOWED_MODULES` 六项里、也不匹配 `app.domain.` 前缀）。于是「`domain` 不许 import `api`」
这件事今天有**两份**守卫在看着：purity 的白名单（判据：不在名单里）与
layering 的反向匹配（判据：命中 `app.api` 前缀）。两份颜色相同、判据不同，
这与本仓既有的「两份 `_absolute` 各配一份回归测试」（硬规矩 #51/#56）是同一个形状。

### 3.6 两条下界**刻意未动**（`>= 40` / `>= 16`）

`test_layering.py` 与 `test_domain_purity.py` 里各有一份：

```
assert len(real_py) >= 40      # backend/ 全树 .py 个数下界（注释里记的实测值是 69）
assert relative_seen >= 16     # 全仓相对导入条数下界（注释里记的实测值是 18）
```

三条理由，一条比一条硬：

1. **它们数的是 `backend/` 全树，与「加一层」无关**。本 Task 亲跑：
   `len(real_py)` = **90**（注释里那个 69 是 Plan 02 Task 4 的时点值，Task 5–9 又长了 21 个），
   `relative_seen` = **36**（注释里的 18 同理）。两条都远远成立，没有一条被本次改动证伪。
2. **`api` 层刻意全用绝对导入**，故 `relative_seen` **一格都没涨**
   （`app/api/deps.py` 写的是 `from app.db.models.organisation import Student`，
   与 Plan02 Ruling 104 记的「Task 2/3/4 三轮都刻意选绝对导入」同一个选择）。
   `relative_seen` 的实测值从 18 涨到 36 是 **Plan 02 Task 5–9 的功劳、不是本 Task 的**。
3. **它们在两份文件里各有一份镜像，只改一边会破坏硬规矩 #51**
   （「两份 `_absolute` 逐字相同，故回归测试也必须各有一份」）。而计划的 Modify 清单里
   **只有 `test_layering.py`**、没有 `test_domain_purity.py`——只抬一边就会让两份漂移。
   要抬就得两份一起抬，那是一次独立的、与「加 api 层」无关的改动，不该夹在本 Task 里。

⚠️ **注释里那两个「实测值」今天是陈旧的**（69 → 90、18 → 36）。**我没有去改它们**，
理由是那些数字都**绑着自己的时点**（Plan02 账本 Ruling 106 的 CE-6 就是为这件事立的规矩：
「这个数在它绑定的时点上是真的、不要顺手改成今天的值」）。
但它们**没有标注是哪个 Task 的时点值**，读的人会以为是当前值——这一条进了 ⑥.1 待清扫。

### 3.7 硬规矩 #88：改完跑一次全量、把红掉的相等断言逐个收进来

```
cd backend; python -m pytest -q
→ 824 passed in 80.21s   退出码 0
```

**一条都没红**。这一点值得单独说一句，因为 Plan 02 Task 6 的教训是
「漏的两格不是『表数这一个事实的副本』，而是『别的事实被同一改动证伪』」。
本 Task 之所以没有连带的相等断言，是因为它**不建表、不改 domain、不改 `__all__`**：
`tests/db/test_models.py` 的三处 `==`、`tests/seed/test_generate.py` 的
`partitioned == actual`、`_MODELS_PUBLIC_BASELINE` 的 33、
`json_text_columns` 的 14、`app.domain.prescription.__all__` 的 51 ——
这五个事实**一个都没被本次改动碰到**（`git diff 69b4218 HEAD --stat` 只有 9 个文件，
`backend/app/db/` 与 `backend/app/domain/` 下**一个文件都没有**）。

---

## ④ Step 4 手工冒烟

### 4.1 起服务的命令（逐字，PowerShell）

```powershell
cd c:\Users\whwenhao\Desktop\Physical_Education_ims\backend
$env:PE_DB_URL = python -c "from app.main import DEMO_DB_URL; print(DEMO_DB_URL)"
# → PE_DB_URL = sqlite:///C:/Users/whwenhao/Desktop/Physical_Education_IMS/backend/pe_demo.db
python -m uvicorn app.main:app --port 8000
```

uvicorn 的启动输出：

```
INFO:     Started server process [54432]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

⚠️ **第二行是承重的**：`python -c "from app.main import DEMO_DB_URL; print(DEMO_DB_URL)"`
把「演示库叫什么」的**唯一所有者**（`app/main.py` 的 `DEMO_DB_URL`）读进环境变量，
而不是在命令行里再敲一遍那个路径（敲第二遍就是第二个所有者）。
这一行同时**顺手证明了** `import app.main` 不会建出 `pe.db`：它在 `PE_DB_URL` 还没设好的
情况下执行了一次 `app = create_app()`，而 4.3 的复核显示 `pe.db` 仍然不存在。

计划的命令 `python -m uvicorn app.main:app --port 8000` **逐字未变**（第三行）。

### 4.2 响应原文（`urllib.request` 打的真 HTTP 请求，不是 TestClient）

**`GET /api/health` → 200**，`content-type: application/json`，响应体**逐字**：

```json
{"status":"ok","tables":18,"students":0}
```

其余六个端点/方法：

| 请求 | 状态 | 取证 |
|---|---|---|
| `GET /openapi.json` | 200 | `info.title` = 体育闭环原型系统，`info.version` = 0.3.0，`len(paths)` = **1**，`paths` = `['/api/health']` |
| `GET /docs` | 200 | `text/html; charset=utf-8`，1 023 B |
| `GET /redoc` | 200 | `text/html; charset=utf-8`，905 B |
| `OPTIONS /api/health`（`Origin: http://localhost:5173`，`Access-Control-Request-Headers: X-Student-Id`） | 200 | `access-control-allow-origin: *`／`access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT, QUERY`／`access-control-allow-headers: X-Student-Id` ← **自定义头能穿过预检**，Plan 04 的 Vite dev server 因此可用 |
| `GET /api/health` 带 `X-Student-Id: 1` | 200 | `{"status":"ok","tables":18,"students":0}`（health 不要求身份，符合计划） |
| `GET /api/nope`（路由不存在） | 404 | `{"error":{"code":"not_found","message":"Not Found","detail":null}}` ← **统一形状、不是 HTML 错误页**，这一格是 `errors.py` 那个 `HTTPException` 处理器在真服务上的证据 |

服务已停（`StopCommand`）。

### 4.3 ⚠️ 跑完立刻复核 `backend/pe.db`（派单坑 #1 点名的那条）

```
pe.db              exists=False
pe.db-journal      exists=False
pe.db-wal          exists=False
pe.db-shm          exists=False
pe_demo.db         exists=True  bytes=172032
pe_demo.db-journal exists=False
pe_demo.db-wal     exists=False
pe_demo.db-shm     exists=False
```

**结论：`backend/pe.db` 仍不存在（连同它的三个伴生文件），禁区未破。**
`pe_demo.db` 建出 172 032 字节，且 `git status --porcelain` 里**看不到它**
→ `.gitignore` 那四行生效。它被**留在工作树里**（没删）：它是 gitignore 挡住的
演示产物，删不删都不影响版本控制，而留着它是「服务真的跑起来了」的物证。

`backend/data/seed/` 文件数 **0**（禁区未破）。

---

## ⑤ 最终验收

### 5.1 测试与覆盖率

| | 基线 `69b4218` | 结案 `2832a27` | 差 |
|---|---|---|---|
| `python -m pytest -q` | 807 passed | **824 passed**（退出码 0） | **+17** |
| 同上 + `--cov` | `806 passed, 1 skipped` | **`823 passed, 1 skipped`** | **+17** |
| stmts | 996 | **996** | 0 |
| Miss | 0 | **0** | 0 |
| branch | 288 | **288** | 0 |
| BrPart | 0 | **0** | 0 |
| 覆盖率 | 100% | **100%** | 0 |

**四格逐字未变**，因为本 Task **没有增加任何 `app/domain/` 代码**
（`git diff 69b4218 HEAD --stat` 的 9 个文件里，`backend/app/` 下只有
`api/__init__.py` / `api/deps.py` / `api/errors.py` / `main.py` 四个新文件，
`app/domain/` 一个字节没动）。

+17 的构成：`tests/test_main.py` **10** + `tests/api/test_scope.py` **5** +
`tests/architecture/test_layering.py` **2**。

**Plan 01/02 的 807 条既有测试一条都没退步**（824 = 807 + 17，没有 skip 数变化、
没有 xfail 变化，退出码 0）。

### 5.2 表数

`len(Base.metadata.tables)` = **18**（本 Task 不建表，Task 2 之后是 25）。
`/api/health` 在真服务上回的也是 `18`。
`tests/test_main.py::test_health_reports_the_table_count` 里那个 `18` 是**字面量**，
Task 2 的同步清单里要改成 25（这一条已写进该测试的 docstring）。

### 5.3 三个禁区指纹（`sha256(read_bytes().replace(b"\r\n", b"\n"))[:16].upper()`）

| 指纹 | 文件 | 实测 | 字节 | CRLF | LF |
|---|---|---|---|---|---|
| `D2C8E539E2FA0029` | `backend/data/national_standard_2014.csv` | **逐字相同** ✅ | 21412 | 0 | 503 |
| `5394B37F01DAC9AC` | `backend/data/exercises.yaml` | **逐字相同** ✅ | 23247 | 0 | 368 |
| `822CB86A5E998301` | `backend/data/exercise_equivalence.yaml` | **逐字相同** ✅ | 8245 | 0 | 130 |

（扫了 `backend/data/` 下全部 22 个 `.csv`/`.yaml`，三个指纹各命中一次、无重复。）
三份文件的 **CRLF 计数都是 0**，与 `.gitattributes` 的 `text eol=lf` 一致。

### 5.4 `backend/data` 的 git diff（简报要 `5b4a10c`、派单要 `69b4218`，**两个都跑**）

```
git diff 69b4218     -- backend/data  → 空（0 字节）
git diff 69b4218 HEAD -- backend/data → 空（0 字节）
git diff 5b4a10c     -- backend/data  → 空（0 字节）
git diff 5b4a10c HEAD -- backend/data → 空（0 字节）
git status --porcelain -- backend/data → 干净
```

### 5.5 本 Task 的改动面

```
 .gitignore                                  |  17 ++
 backend/app/api/__init__.py                 |   0
 backend/app/api/deps.py                     | 157 ++++++
 backend/app/api/errors.py                   | 153 ++++++
 backend/app/main.py                         | 218 ++++++++
 backend/tests/api/conftest.py               |  64 +++
 backend/tests/api/test_scope.py             | 213 +++++++
 backend/tests/architecture/test_layering.py | 323 +++++++++++-
 backend/tests/test_main.py                  | 318 +++++++++++
 9 files changed, 1450 insertions(+), 13 deletions(-)
```

`-13` 全部落在 `test_layering.py`（被改写的 `>= 8` 那段注释与 `SCANNED_DIRS` 那一行）。
**`backend/app/db/` 与 `backend/app/domain/` 下没有任何文件被改**。

### 5.6 落盘纪律复核

7 个新文件 + 2 个改动文件，全部 **CRLF、无 BOM、无裸 LF**（`read_bytes()` 口径，
硬规矩 #89）：`test_layering.py` 60 349 B / 860 CRLF / 0 裸 LF；
`.gitignore` 1 265 → 2 444 B / 39 → 56 CRLF / 0 裸 LF；
`app/main.py` 12 236 B、`app/api/deps.py` 9 400 B、`app/api/errors.py` 8 157 B、
`tests/test_main.py` 15 583 B、`tests/api/test_scope.py` 10 400 B、
`tests/api/conftest.py` 3 569 B、`app/api/__init__.py` 0 B。

`git add` **一律按文件名逐个加**（7 + 2 = 9 次），没有用 `-A` / `.`。
两个 commit 的信息都是 python 写的 UTF-8 **无 BOM** 临时文件 + `git commit -F`
（写前先验：`bom False`、`decode('utf-8')` 通过）。

---

## ⑥ 待清扫 / 关切 / 顶回 / 没按派单做的地方

### 6.1 待清扫（**6 条**，纯散文精度或「今天不成问题、将来会成问题」，按 Ruling 1 不返工）

1. **`test_layering.py` 里那两个「实测值」注释陈旧了**：`40 = backend/ 下 .py 的个数下界
   （Task 4 落地时实测 69）` 与 `16 = 全仓相对导入的条数下界（Task 4 落地时实测 18）`
   ——今天的实测值是 **90** 与 **36**。它们**绑的是 Plan 02 Task 4 的时点**、
   按 Ruling 106 / CE-6 的规矩不该顺手改，但它们**没写出自己是哪个时点的值**，
   读的人会当成当前值。建议：把「Task 4 落地时」改成「Plan 02 Task 4（`c21767d` 前后）落地时」，
   再各补一行当前值。**两份文件都要改**（硬规矩 #51）。
2. **本仓没有任何 logging 配置**。`errors.py` 的 500 处理器用 `_LOGGER.exception(...)`
   记堆栈，演示时它会打到 uvicorn 接管的 stderr（可用），但**没有落到文件**、
   也没有格式与轮转。Plan 04 要真给人演示的话得配一次 `logging`。
3. **`StaticPool` 没有 `checkedout()`**（本机实测 `AttributeError: 'StaticPool' object has
   no attribute 'checkedout'`）。今天两条用到它的断言都跑在**磁盘** URL 上
   （`QueuePool`），故撞不上；但谁将来想在**内存库**应用上断言「工厂期没连接」，
   得换判据。建议在 `app/main.py` 的 `_build_engine` docstring 里补一句。
4. **`/api/health` 的 `tables` 不校验磁盘库真的建了那些表**：它读的是
   `Base.metadata`（Python 对象），故一个「连到了旧库、缺 7 张新表」的场景它会答 25
   而随后的查询会炸。原型阶段可接受；要更严就换成
   `len(sqlalchemy.inspect(engine).get_table_names())`（一次真查询）。
   `students` 那一格已经是一次真查询，故这个缺口今天不是全裸。
5. **`Page` 今天没有任何生产调用点**（Task 3 才用）。它作为 FastAPI 依赖的用法已由
   `tests/api/test_scope.py::test_page_caps_limit_at_two_hundred` 的 `/probe/page`
   探针验过（`?limit=201` → 422、`?limit=10&offset=20` → 200），
   但「23 个资源各挂一个 `Page`」这个形状要到 Task 3 才被真的行使。
6. **`/api/health` 今天直接写在 `create_app` 里**，而计划 File Structure 说
   `app/api/routers/__init__.py` 是「`create_app()` 只 include 这一个」的汇总点。
   Task 3 建出 `routers` 包之后，要不要把 health 也搬进去是一个待定决定
   （搬的话 `tests/test_main.py` 那两条**不用改**，它们只认路径不认住址）。
   不搬的理由也成立：health 是应用级的存活探针、不是某个资源的 CRUD。

### 6.2 关切（含**顶回派单 3 处**）

派单第 7 节说「若你认为简报/计划某条决定是错的，顶回来」。本 Task 顶回 **3 处**，
另有 **1 处对计划的补充**（不算顶回，因为它不与任何决定冲突）。
四处都**先实现了我认为对的那个版本**，没有静默偏离。

**顶回 1：`get_db` 的签名必须多一个 `request: Request` 参数。**

* **哪条决定**：计划 Interfaces 写 `get_db() -> Iterator[Session]`。
* **为什么错**：一个无参的 `get_db()` 拿不到引擎。引擎是 `create_app(db_url=…)`
  按注入的 URL 造的，而无参函数只能从**模块级全局**取它。于是同一进程里的两个应用
  （`create_app(db_url=A)` 与 `create_app(db_url=B)`）会共用**后建的那一个**引擎——
  而 `tests/api/conftest.py` 的 `app` 夹具是 **function 级**的，每个测试都建一个新应用。
  那种共享会让「A 的测试读到了 B 的库」，症状是间歇性的空结果，离真因极远。
  这正是派单第 7 节说的那个形状：**控制者对着「签名长什么样」推理，
  实现者对着「夹具是什么作用域」推理。**
* **替代方案**：`get_db(request: Request)`，从 `request.app.state.engine` 取。
  `Request` 是 FastAPI 里唯一能从依赖内部拿到「当前这个 app」的入口。
* **代价**：**对调用方零代价**——端点里仍然写 `session: Session = Depends(get_db)`
  （`tests/test_main.py` 的三个探针与 `tests/api/test_scope.py` 的
  `/probe/student/{student_id}` 都是这个形状），FastAPI 自己会把 `request` 注进来。
  Task 3 的 `build_crud_router` 因此**不需要知道这件事**。
  真正的代价只有「报告的签名与计划的签名差一个参数」，以及后面 8 个 Task 的实现者
  若照计划正文抄 `get_db()` 会当场 `TypeError`（响亮，不静默）。

**顶回 2：必须给 `create_app` 加一个 `PE_DB_URL` 环境变量覆盖口子。**

* **哪条决定**：计划 Interfaces 写「`db_url` 缺省时取 `app.config.DEFAULT_DB_URL`」，
  而计划 Step 4 的命令是 `python -m uvicorn app.main:app --port 8000`，
  计划的决定又说「`pe.db` 仍然是禁区——起 uvicorn 时**必须显式传 `db_url`**」。
* **为什么错**：这三条**互相不可能同时成立**。`uvicorn app.main:app` 加载的是
  **模块级**的 `app`（计划 File Structure 逐字要求 `create_app()` + `app = create_app()`），
  那个对象由 `create_app()` **无参**建出——**命令行上没有任何位置能塞 `db_url`**。
  而 `DEFAULT_DB_URL` 实测就是 `sqlite:///…/backend/pe.db`（1.4 节）。
  于是照字面执行 Step 4，只有两种结局：① lifespan 建表 → **当场建出禁区的 `pe.db`**；
  ② 不建表 → `/api/health` 的 `students` 查询炸成 500，演示失败。
  派单坑 #1 已经嗅到了这个冲突（它说「起 uvicorn 时必须显式传 `db_url`，
  不能让它落到 `DEFAULT_DB_URL`」），但**没有给出「怎么传」的机制**——
  而模块级 `app` 这个形状恰好堵死了所有函数参数级别的传法。
* **替代方案**：优先级 `db_url` 实参 > `PE_DB_URL` 环境变量 > `DEFAULT_DB_URL`。
  于是 Step 4 变成两行（4.1 节），**计划的那条 uvicorn 命令逐字不变**。
  `DEMO_DB_URL` 与 `DB_URL_ENV_VAR` 都在 `app/main.py` 里有唯一所有者、
  都被 `tests/test_main.py` 钉住。
* **为什么不住在 `app/config.py`**：那个模块是全仓依赖图的**叶子**
  （它的 docstring 明写「只 import `pathlib`」，任何一层都能安全 import 它而不可能造出环），
  给它加 `import os` 会改掉那个性质；而且 `tests/test_config.py` 用
  `DEFAULT_DB_URL.endswith("/backend/pe.db")` 把那个常量**字面钉死**了。
  **`DEFAULT_DB_URL` 的值一个字没改**，改的只是「本层如何在运行时覆盖它」。
* **代价**：多一个环境变量名要记（已写进 `.gitignore` 的注释与 `app/main.py` 的
  模块 docstring，两处都给了逐字可粘的三行命令）；以及「环境里意外留了 `PE_DB_URL`」
  会让服务连到意料之外的库——故 `tests/test_main.py` 那条模块级 app 的测试用
  `monkeypatch.delenv` + `importlib.reload` 把环境**受控**（见 6.4 第 2 条）。

**顶回 3：S6 的「下界一次性抬到位」不能按字面读成「抬到计划结束时的值」。**

* **哪条决定**：派单第 3 节坑 2 的「⚠️ S6 的裁定：下界断言由本 Task 一次性抬到位
  （含 `api` 那一层），后面 8 个 Task 不再动它。故抬的时候要给足余量
  （例如 domain 会从 16 涨到 17、`app/api/` 本计划要建约 15 个 `.py`）」。
* **为什么错**：**「给足余量」与「下界」在方向上是相反的**。下界断言
  `len(scanned) >= N` 要成立，`N` 必须 ≤ **当前**实测值。若按「计划建满时 api 有 15–18 个」
  去给余量、把 `N` 写成 53 或 56，那么本 Task 落地当天 `len(scanned)` = 38 → **当场红**，
  而且它会一直红到 Task 8 才转绿——那正是「让守卫在中间 7 个 Task 里不可用」的形状。
  派单举的那个数也偏小：逐行数 File Structure 是 **18** 个而不是 15 个（3.3 节给了逐行清单），
  故「建满时的聚合值」是 56 而不是 53。
* **替代方案**：抬到「**今天已经成立的、四个目录各自地板之和**」= `5+5+5+3 = 18`
  （从 8 抬了 10 格），并把「后面 8 个 Task 不再动它」这个目标改用一个**单调性论证**
  来兑现：剩下的 8 个 Task 只**增加** `app/api/` / `app/domain/` / `app/pipeline/` 下的
  `.py`（File Structure 的新建清单里没有一处删除或合并），故 `len(scanned)` 只增不减，
  一个已经成立的下界永远不会被后续 Task 击穿。**目标达成了，只是达成方式不是「写个大数」。**
* **代价**：18 比 56 松得多，「某一个目录被搬到只剩它自己的地板」这一档仍然拦不住
  （3.3 节末尾给了准确的算术与那一档的三重兜底）。这是**下界这个机制的固有代价**，
  与本 Task 无关；写成 56 也拦不住它，只会额外换来 7 个 Task 的红。

**补充（不算顶回）：`errors.py` 在计划枚举的四条映射之外多注册了两个处理器。**

计划写的是「`domain ValueError → 422`、`IntegrityError → 409`、`NoResultFound → 404`、
其余 → 500」+「**统一响应形状** `{"error": {"code","message","detail"}}`」。
我只做前四条的话，「统一形状」这个决定**不成立**：`require_scope` 抛的
`HTTPException(403)`、`current_student` 抛的 `HTTPException(401)`、Starlette 自己的
404/405、以及请求体校验的 `RequestValidationError` 都仍然是 FastAPI 缺省的
`{"detail": …}` 形状——而这四个恰恰是 CRUD API 里**最常见**的错误来源。
故多注册了 `HTTPException`（原状态码，`code` 由状态码折算，`headers` 照转）与
`RequestValidationError`（422，`detail` 放 `jsonable_encoder(exc.errors())` 那份结构化清单，
这正是计划把 `detail` 标成 `Any | None` 而不是 `str` 的用处）。
两处都有测试：`tests/api/test_scope.py` 的 401/403/422 三格断言的是**整份响应体**，
`tests/test_main.py::test_the_catch_all_handler_does_not_swallow_http_exceptions`
专门守「兜底的 `Exception` 处理器不得把 `HTTPException` 吞成 500」。

**其余关切（不是顶回，是给后面 8 个 Task 的提示）**：

* ⚠️ **`require_scope` 我给它加了第二支**（计划正文只写了「不匹配 → 403」）：
  `requester_id` 在 `student` 表里查无此人时**也** 403。
  理由：不查库的闸门只能比对两个整数，于是 `X-Student-Id: 999999` 会被放行到端点里、
  只靠下游的 404 兜底——而下游的 404 意思是「没有这行数据」，不是「你不是这个人」，
  两者混在一起之后前端无法区分「我确实没有打卡记录」与「我根本没登录成任何人」。
  这也让 `session` 这个形参**真正承重**（否则它是一个未使用的参数）。
  **代价（Task 5 的实现者要注意）**：每次调用多一次 `SELECT`；
  以及**若在测试里用一个没有该学生的 session 调 `require_scope`，会拿到 403 而不是通过**。
  「pure gate」的准确含义是**只判定、不改状态**（不 commit、不写库、不缓存、返回 `None`），
  **不是**「不碰数据库」——这条口径在 `deps.py` 的 docstring 与那条测试的 docstring 里都写了。
* ⚠️ **教师不走 `require_scope`**（`requester_id: int`，而教师身份是工号字符串）。
  教师端的跨学生访问（大屏、班级周报）按设计是合法的，但它的边界
  （「这个教师在不在册」）今天**没有任何守卫**。Task 8 要自己定。
* ⚠️ **`X-Student-Id: abc` → 422 而不是 401**。这是计划写下的
  `x_student_id: int | None = Header(None)` 标注的直接后果（非整数在**进函数之前**
  就被 FastAPI 的请求校验拦下）。不构成漏洞（两个码都拒绝访问），
  但前端要知道「没有头」与「头格式错」是两个码。已由
  `tests/api/test_scope.py::test_a_non_integer_identity_header_is_422` 钉住口径。
* ⚠️ **`app/main.py` 不被任何架构守卫扫**：它在 `app/` 根下、不属于任何一层子目录，
  而 `_py_files` 只按目录扫。这是有意的（它是 `api` **之上**的装配点，
  必须能 import `app.api`，把它归进「不得依赖 api」那一圈会自相矛盾）。
  但代价是「`main.py` 不得 import `app.seed`」这件事**没有守卫**。
  要补的话得给 `_py_files` 加一个「根下的散模块」清单——本 Task 没做，
  因为它会改到一个被 Plan 02 三份规格说明钉着的函数。
* ⚠️ **`API_ALLOWED_PREFIXES` 少列了 `app.demo_data`**（Task 2 的演示数据生成器）。
  这是**刻意的**：端点要造演示数据是一次需要显式改清单的决定。
  但 Task 2/8 的实现者若真撞上这条红，正确处置是**改清单并写明理由**，
  而不是把那句 import 挪进函数体（挪进去也会被 `ast.walk` 抓到）。

### 6.3 fix round（**1 轮**，目标 0–1 轮）

只有 **1 轮**，修的是**我自己写出来的一处假绿断言**（不是实现的问题）：

* **症状**：三条测试红，报
  `assert 'sqlite:///C%3A/Users/…/injected.db' == 'sqlite:///C:/Users/…/injected.db'`。
* **真因**：Windows 上 `str(engine.url)` 会把盘符里的 `:` **百分号编码**成 `%3A`。
* ⚠️ **而这里有一个比红更坏的东西**：同一个原因让
  `assert str(engine.url) != DEFAULT_DB_URL` **恒真**——它在改之前是**绿**的，
  而它证明的**不是**「没有落到缺省库」，只是「盘符被编码了」。
  那正是一条恒绿的假守卫（派单第 7 节引的 Plan 02 那个「结构上不可能变红」的形状）。
  **是红的那一条把绿的这一条一起暴露出来的**——若我只修红的、不改绿的，
  这处假绿会一直留在树上。
* **处置**：三处一律改成 `make_url(...)` 的**结构化**比对
  （`URL.__eq__` 比的是解析后的各段，不受渲染方式影响），
  并把「为什么不能比 `str()`」写进那条测试的 docstring（含实测的 `%3A` 原文）。
  顺带给 `test_pe_db_url_env_var_overrides_the_default` **补上**了
  `!= make_url(DEFAULT_DB_URL)` 那一格（它此前没有这一格）。
* **复跑**：15 passed（`tests/test_main.py` + `tests/api/test_scope.py`），
  随后全量 824 passed、覆盖率四格不变。

同一轮里还修了两处我自己写的**垃圾断言**（都是草稿残留，不是设计问题）：
`assert teacher.request`（无意义的占位）与 `assert create_app is not None`
（连同它所在的那条测试一起删了——它想守的性质已由其余 5 条覆盖：
探针没挂上的话它们会以 404 而不是 401/403/200 红掉）。

### 6.4 没按派单做的地方（**6 处**）

1. **`tests/api/__init__.py` 没建**。派单第 4 节的原文是
   「`backend/tests/api/__init__.py`（**若既有测试目录有这个惯例就先实测**）」——
   实测结论是 `tests/` 下 31 个 `.py`、`__init__.py` **0 个**，故按派单**自己的条件分支**不建。
   （这是照办不是偏离，但列出来免得控制者以为漏了。）
2. **`conftest.py` 提供的是 `app` / `engine` / `client` 三个夹具，不是计划说的一个 `client`**。
   计划 Step 1 的原文是「`client` fixture（`TestClient(create_app(db_url="sqlite://"))`，
   内存库 + `StaticPool`，并在 fixture 里 `Base.metadata.create_all`）」。
   拆成三个的理由：`tests/api/test_scope.py` 要在**发请求之前**先插两行学生，
   而插完的 `Session` 必须**关掉**（`StaticPool` 下全进程只有一条 DBAPI 连接，
   留一个开着事务的 `Session` 会与请求里 `get_db` 的 `Session` 抢它），
   把「建表」塞进 `client` 夹具里做不到这件事。建表落在 `engine` 夹具里、
   调的是 `init_db`（它内部就是 `Base.metadata.create_all`），语义与计划一致。
3. **计划说 3 + 3 = 6 条测试，实际交付 5 + 10 = 15 条**（另加守卫 2 条 = 17）。
   多出来的 9 条各覆盖一个「计划里写了、但没人验」的性质：
   异常映射 5 条（`errors.py` 是 Create 文件，不测就是裸奔）、
   缺省 URL 解析 2 条（**这两条守的正是 `pe.db` 禁区**）、
   `Page` 边界 1 条（「上界 200」否则是一句没人验的散文）、
   非整数身份头 1 条（422 vs 401 的口径）。
   计划点名的 6 条**一条没少、名字逐字未改**。
4. **计划 Step 3 的反向断言写的是「`app/domain/**` 与 `app/db/**` 里出现 `app.api` 一律红」，
   我扩到了 `pipeline`**（实现成「`SCANNED_DIRS` 减掉 `api`」）。
   理由：spec §3.3 的方向图里 `api → pipeline`，故 `pipeline → api` 同样是反向；
   而写成减法之后「将来再加一层」会自动纳入约束，不必有人记得同步第二处清单。
   代价：0（`pipeline` 今天一条 `app.api` 都没有，G2 那格探针证明这一圈有牙）。
5. **简报 §0.5 要求报告 `git diff 5b4a10c HEAD -- backend/data`、派单第 9 节要求
   `69b4218`——两个都跑了**（5.4 节，四条全空）。这不算偏离，但两份文档给的 rev 不同，
   故按「都跑」处置。
6. **报告写作的时点**：派单说「建议 2 个 commit」，我照做了；
   但**本报告不在这两个 commit 里**（它在两个 commit 之后写、且 `.superpowers/**`
   按 `.gitattributes` 是 `-text` 双向零转换）。若控制者要把它入库，需要第三个 commit。

### 6.5 Critical 级问题（会让生产代码错 / 守卫假绿 / 数据不可追溯）

**当场修掉的：1 处** —— 6.3 那处假绿断言（`str(engine.url) != DEFAULT_DB_URL` 恒真）。
它符合「会让守卫假绿」的定义，故按 Ruling 1 当场修了，没有留进待清扫。

**遗留的：0 处。**

---

## ⑦ commit sha

| sha | 说明 | 改动 |
|---|---|---|
| **`59eb771`** | `feat(api): Plan03 Task 1 —— FastAPI 骨架 + 依赖注入 + 作用域闸门（第 1/2 个 commit）` | 7 files changed, 1123 insertions(+)：`app/api/{__init__,deps,errors}.py`、`app/main.py`、`tests/api/{conftest,test_scope}.py`、`tests/test_main.py` |
| **`2832a27`** | `test(architecture): Plan03 Task 1 —— 守卫加 api 层 + pe_demo.db 进 .gitignore（第 2/2 个 commit）` | 2 files changed, 327 insertions(+), 13 deletions(-)：`tests/architecture/test_layering.py`、`.gitignore` |

基线 `69b4218` → 结案 `2832a27`，共 2 个 commit、9 个文件、
**1 450 insertions / 13 deletions**。分支 `feature/plan-03-feedback-alert-crud-api`，
**未 push、未切分支、未碰 main**。工作树干净（`git status --porcelain` 空，
`pe_demo.db` 被 `.gitignore` 挡住）。

### 作用域闸门那三条测试的名字（派单第 9 节点名要的）

计划 Step 1 点名的三条，**名字逐字未改**，都在 `backend/tests/api/test_scope.py`：

1. `test_missing_identity_header_is_401`
2. `test_a_student_cannot_read_another_students_row`
3. `test_require_scope_is_a_pure_gate`

同文件另有本 Task 加的两条（6.4 第 3 条）：
`test_a_non_integer_identity_header_is_422`、`test_page_caps_limit_at_two_hundred`。

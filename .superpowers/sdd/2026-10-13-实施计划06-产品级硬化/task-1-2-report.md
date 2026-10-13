# 实施计划 06 · Task 1 + Task 2 实现者报告 —— 数据库迁移基线 + 迁移链纪律

> 分支 `p06/migrations`（从 `main` 的 `5131c12` 起）。**未 push、未碰 main。**
> 实现范围：计划文档 `Document/2026-10-13-实施计划06-产品级硬化.md` 的 §1（Task 1）与 §2（Task 2）。
> 交付口径：**这是要给甲方的产品级系统**，现场升级版本**不能丢数据**。

---

## ① 环境（硬规矩 #73：开工第一件事）

开工自检（`node --version; python --version; python -c "import fastapi, sqlalchemy; …"`）：

| 项 | 实测值 |
|---|---|
| Node | **v24.19.0** |
| npm | 11.17.0（`npm run build` 那条链带出来的） |
| Python | **3.11.1**（**无 venv**，`python -m pip install` 装进系统 site-packages） |
| FastAPI | **0.141.1** |
| SQLAlchemy | **2.1.3** |
| Pydantic | **2.13.5** |
| SQLite（`sqlite3.sqlite_version`） | **3.39.4**（⚠️ 承重：档 2 的定点变异用了 `ALTER TABLE … DROP COLUMN`，SQLite 3.35 起才支持） |
| git `core.autocrlf` | **true**（⇒ blob 里是 LF、工作树里是 CRLF；本报告所有「行尾」结论都是**工作树**口径） |

装完 alembic 之后（`python -m pip install alembic`）：

| 项 | 实测值 |
|---|---|
| **alembic** | **1.20.0**（`alembic --version` → `alembic 1.20.0`；`alembic.__version__` 同值） |
| Mako（alembic 的传递依赖，pip 一起装上的） | **1.4.3** |
| MarkupSafe | 3.0.3（已在，Mako 的依赖） |
| typing-extensions | 4.16.0（已在） |

⚠️ **「新增依赖只有 alembic 一个」这句话要精确地说**：`pyproject.toml` 里只加了一行
`alembic==1.20.0`，但 pip 会连带装上 **Mako**（alembic 渲染 `script.py.mako` 用它）。
本仓**刻意不重复钉 Mako**——那一层由 alembic 自己的 `install_requires` 声明，
在这里再钉一遍就是第二个所有者（改 alembic 版本的人只会改到其中一份）。

端口实测（开工时）：`netstat -ano | Select-String ":8000|:5173"` → **两条都没有**。
⚠️ 派单说「后端 8000 长跑中、vite 5173 长跑中」，实测**两个都没在监听**。
收工时两者都已由我起起来（后端走 `demo.ps1 -Port 8000`，前端 `npm run dev`），见 §⑦。

---

## ② 基线迁移的逐表核对结果

### ②.1 目录名选择与理由

选了 **`backend/migrations/`**（不是 `alembic/`）。理由：**按角色命名，不按工具命名**。
`backend/` 因此读作 `app/ data/ migrations/ scripts/ tests/` —— 五个目录各答一个问题
（代码 / 知识资产 / 结构变更史 / 运维入口 / 测试），而 `alembic/` 答的是「今天谁生成了它」。
工具是可换的（`backend/alembic.ini` 已经把这个工具的名字放在了它该在的位置），
「这个项目的库结构是怎么一版一版走到今天的」不是。

`alembic.ini` 的 `script_location = %(here)s/migrations`，`%(here)s` 是 ini 自己所在的目录
（= `backend/`），故**与 CWD 无关**；`migrations/env.py` 里另有一段无条件的
`sys.path.insert(0, BACKEND_DIR)`，于是从仓库根跑 `alembic -c backend/alembic.ini …` 也成立。

### ②.2 `alembic.ini` 的 url 怎么处理

**`sqlalchemy.url =`（恒为空），`migrations/env.py` 刻意不读它。**
连接串的唯一所有者是「`PE_DB_URL` 环境变量（名字在 `app.main.DB_URL_ENV_VAR`）
或程序内传入的 `Config.attributes["pe_db_url"]`（键名在 `app.db.session.DB_URL_ATTRIBUTE`）」。
理由与 `app/db/session.py::engine()` 当年删掉 `sqlite:///pe.db` 缺省值完全相同：
**连接串写两遍，就一定有一遍是相对路径的那一遍，而两个都不报错**——只是其中一个永远是空库。
`env.py` 的三档优先级与 `app.main._resolve_db_url` 同形：

1. `config.attributes[DB_URL_ATTRIBUTE]` —— 程序内调用（`init_db` 与两条守卫测试）；
2. `os.environ[DB_URL_ENV_VAR]` —— 命令行 `python -m alembic upgrade head`；
3. 都没有 → `RuntimeError`（**响亮**）。⚠️ **刻意不回落到 `app.config.DEFAULT_DB_URL`**：
   它逐字指向禁区 `backend/pe.db`，回落过去就是当场建出那个文件。

⚠️ 走 `attributes` 而不是 `set_main_option("sqlalchemy.url", …)`：后者经 configparser 的
`%` 插值，URL 里出现一个 `%` 就会被当成插值语法当场抛错。

### ②.3 autogenerate 对 SQLite 的局限——**实测**（不是照抄文档）

对**空库** autogenerate 是它最可靠的用法，本 Task 实测确认：26 张表全部检出，
且 **29 条 `CheckConstraint` 也被渲染出来了**（这一点派单没提，而它是承重的：
那 29 条 CHECK 是本仓「枚举取值域两处设防」的 SQL 那一半，见 `app/db/models/__init__.py`
约定 2；漏掉它们不会有任何报错，只会让「绕过 ORM 直接写库」把脏值写进去）。

⚠️ 而**两个真实的坑**是派单没有预告、实测撞出来的，都写进了 spec §13.7：

| # | 坑 | 实测证据 |
|---|---|---|
| 1 | **自定义 `TypeDecorator` 的 import 不生成**。本仓 21 个 JSON 形态的列用 `app.db.models._shared.JsonText`，autogenerate 把它渲染成 `app.db.models._shared.JsonText()` 这个**限定名**、却不生成 import | 刚生成出来的基线在 `upgrade()` 的**第一张表**上就是 `NameError: name 'app' is not defined`（`53e5a548c40e_baseline.py:30`，`sa.Column('targets', app.db.models._shared.JsonText(), nullable=False)`）。修法：手工补一句 `import app.db.models._shared` |
| 2 | **`alembic.ini` 不能含非 ASCII**。`alembic.util.compat.read_config_parser` 用 `encoding="locale"`（本机 = GBK）读它 | 一行 UTF-8 中文注释 ⇒ **每一条** `alembic` 命令在启动期抛 `UnicodeDecodeError: 'gbk' codec can't decode byte 0x80 in position 30: illegal multibyte sequence`。⚠️ 这包括 `init_db` 里那几次**程序内**调用，也就是**服务起不来**。故 `alembic.ini` 全篇英文，中文理由住在 `migrations/env.py` 与 spec §13.7（两者都由 Python 按 UTF-8 读），并有一条守卫钉住（见 §⑤） |

另实测三格「不是坑但要知道」的事实：

* `render_as_batch=True` 会让 9 个 `ix_*_batch_id` 索引被渲染成
  `op.batch_alter_table(...)` 里的 `batch_op.create_index(...)`。对一份**空的**基线库，
  代价只是 9 次「建新表 → 拷 0 行 → 改名」，正确性不受影响（由 §④ 的一致性测试判）。
* alembic 写迁移文件用 `alembic.ini` 的 `output_encoding`（本仓显式钉成 `utf-8`；
  缺省会落到平台 locale = GBK），行尾在 Windows 上是 **CRLF、无 BOM**
  —— 与 `backend/` 下既有 `.py` 的主流一致（实测 **133/140** 个文件是纯 CRLF、0 个带 BOM），
  故**不需要**再做一次行尾规范化。
* `-m` 后面的消息会被 alembic 折成**文件名的一部分**（slug）：实测 `-m "编码探针"`
  生成 `d009fc344a65_编码探针.py`。故基线用 ASCII 的 `-m "baseline"`、再手工把 docstring
  写成中文（中文文件名在 git 里没问题，但在 PowerShell 里 `git add` 要额外加引号）。

### ②.4 逐表核对：迁移建出来的库 vs `Base.metadata`

方法：对空库 `alembic upgrade head` 到一个临时文件 → `sqlalchemy.inspect()` 反射；
另一侧直接读 `Base.metadata`，列类型用 `col.type.compile(dialect=sqlite.dialect())`
编译成字符串（`JsonText` 是 `TypeDecorator`，模型侧编译成 `TEXT`、反射回来也是 `TEXT`）。
比较五维：**列（名 + 类型串 + 可空，含列序）/ 索引数 / 唯一约束数 / 外键数 / CHECK 数**。
（这一份核对同时也是常驻测试
`tests/db/test_migration_baseline.py::test_the_migrated_database_matches_base_metadata_table_by_table`。）

| 表 | 列数 (m/r) | 索引 (m/r) | 唯一 (m/r) | 外键 (m/r) | CHECK (m/r) |
|---|---|---|---|---|---|
| `alert` | 14/14 | 1/1 | 1/1 | 4/4 | 3/3 |
| `body_composition` | 8/8 | 0/0 | 1/1 | 1/1 | 0/0 |
| `class_session` | 7/7 | 1/1 | 1/1 | 2/2 | 0/0 |
| `cleaning_log` | 9/9 | 0/0 | 0/0 | 2/2 | 1/1 |
| `course_section` | 6/6 | 0/0 | 0/0 | 2/2 | 1/1 |
| `daily_sync_run` | 19/19 | 0/0 | 1/1 | 1/1 | 1/1 |
| `derived_metrics` | 11/11 | 1/1 | 1/1 | 2/2 | 0/0 |
| `enrollment` | 4/4 | 0/0 | 1/1 | 3/3 | 0/0 |
| `exercise` | 7/7 | 0/0 | 1/1 | 0/0 | 1/1 |
| `fitness_test_batch` | 6/6 | 0/0 | 0/0 | 1/1 | 1/1 |
| `fitness_test_result` | 21/21 | 0/0 | 1/1 | 2/2 | 0/0 |
| `interest_survey` | 7/7 | 0/0 | 1/1 | 2/2 | 0/0 |
| `mini_test` | 10/10 | 0/0 | 1/1 | 2/2 | 0/0 |
| `notification` | 10/10 | 0/0 | 0/0 | 2/2 | 2/2 |
| `percentile_snapshot` | 14/14 | 1/1 | 1/1 | 2/2 | 3/3 |
| `prescription` | 16/16 | 1/1 | 1/1 | 2/2 | 2/2 |
| `prescription_template` | 10/10 | 0/0 | 1/1 | 0/0 | 4/4 |
| `rpe_record` | 6/6 | 0/0 | 1/1 | 2/2 | 1/1 |
| `semester` | 6/6 | 0/0 | 1/1 | 0/0 | 0/0 |
| `stratification_result` | 10/10 | 1/1 | 1/1 | 2/2 | 2/2 |
| `student` | 9/9 | 0/0 | 1/1 | 0/0 | 1/1 |
| `teacher` | 6/6 | 0/0 | 1/1 | 0/0 | 1/1 |
| `training_log` | 11/11 | 1/1 | 1/1 | 2/2 | 2/2 |
| `user_session` | 8/8 | 0/0 | 0/0 | 0/0 | 2/2 |
| `weekly_adjustment` | 8/8 | 1/1 | 1/1 | 2/2 | 1/1 |
| `weekly_class_report` | 12/12 | 1/1 | 1/1 | 3/3 | 0/0 |
| **合计** | **255/255** | **9/9** | **21/21** | **41/41** | **29/29** |

（`m` = `Base.metadata`，`r` = 迁移建出来后反射回来的。外键一栏数的是
`ForeignKeyConstraint` 的**个数**，不是 `ForeignKey` 对象数——`session.py` 的
`_sqlite_foreign_keys_on` docstring 里那个「20 个 `ForeignKey`」是另一个口径的历史数字，
两者不是一回事。）

**结论：26 张表全一致，0 处不一致。** 主键也逐表核对过（26 张表各 1 个，全是 `('id',)`），
列类型串逐列核对过（含 21 个 `JsonText` 列一律落 `TEXT`）。

### ②.5 基线迁移的规模（实测）

`backend/migrations/versions/53e5a548c40e_baseline.py`：**566 行 / 33 373 字节 / CRLF / 无 BOM**，
`revision = 53e5a548c40e`、`down_revision = None`。
列类型分布（`sa.Column(…)` 的第二个参数，实测计数，合计 255 = 上面的列数）：

| 类型 | 个数 |
|---|---|
| `sa.Integer` | 100 |
| `sa.String` | 60 |
| `sa.Float` | 23 |
| `app.db.models._shared.JsonText` | **21**（与 `tests/db/test_models.py` 钉的「21 个 JSON 列」同值） |
| `sa.Date` | 20 |
| `sa.DateTime` | 15 |
| `sa.Boolean` | 9 |
| `sa.Text` | 7 |

⚠️ **基线里 0 行数据**：`op.bulk_insert` 与 `op.execute` 各 0 次调用，非 docstring 的
字符串常量里没有一条以 `INSERT` / `UPDATE` / `DELETE` 开头。守卫是
`test_migration_chain.py::test_the_migration_scripts_carry_no_data`。

---

## ③ `init_db` 三档（+ 一条快路径）的实测

`init_db` 在 `backend/app/db/session.py`（原来就在那儿；改前是 3 行 `create_all`）。
四条路径各跑了一次真库（探针：`%TEMP%` 下的临时 SQLite 文件，`backend/` 下一个字节没留）：

| 档 | 库的状态 | 实测行为 | 实测输出 |
|---|---|---|---|
| **快路径** | `sqlite:///:memory:` / `sqlite://` | `Base.metadata.create_all`，**不碰 alembic** | `表数 = 26  alembic_version = None` |
| **档 1** | 文件**不存在** | `alembic upgrade head` | `调用前文件存在 = False` → `表数 = 27  alembic_version = 53e5a548c40e`，`建出文件 = True  大小 = 270336` |
| **档 1b** | 文件存在、**0 字节** | 同档 1 | `表数 = 27  alembic_version = 53e5a548c40e` |
| **档 3** | 文件存在、**有** `alembic_version` | `alembic upgrade head`（幂等） | 连跑两次：`53e5a548c40e -> 53e5a548c40e  表数 = 27`；版本表恒 **1 行** |
| **档 2** | 文件存在、**无** `alembic_version`（`create_all` 建的旧库 + 1 行数据） | **先比对结构、后** `stamp 53e5a548c40e`，再 `upgrade head` | `stamp 前：表数 = 26  alembic_version = None  semester 行数 = 1` → `stamp 后：表数 = 27  alembic_version = 53e5a548c40e  semester 行数 = 1`（**那一行数据没丢**） |
| **档 2 失败方向** | 文件存在、无版本表、结构**不等于**基线（一张缺 4 列的 `semester` + 一张 `totally_unexpected` + 少 25 张表） | `RuntimeError`，**拒绝 stamp**、**不写版本表** | 报错指名道姓：`缺表 ['alert', 'body_composition', …25 张…]；多表 ['totally_unexpected']；表 semester 的列不一致：缺 ['end_date', 'is_current', 'start_date', 'weeks']、多 []` |

`_db_file_of(url)` 的四格判据实测（`None` = 走快路径）：

| URL | 返回 |
|---|---|
| `sqlite://` | `None` |
| `sqlite:///:memory:` | `None` |
| `postgresql+psycopg://u:p@h/db` | `None`（⚠️ 刻意：非 SQLite 后端今天不走迁移链，见 §⑥ 关切 3） |
| `sqlite:///C:/x/y.db` | `C:\x\y.db` |

### ③.1 测试档走哪条路，以及为什么这样够

**测试档走 `create_all` 快路径**（全部 1370 条测试）。实测调用面：`tests/**` 下
**18** 个文件的文本里出现 `init_db`，其中 2 个是本 Task 新建的，故**16 个既有测试文件**
的夹具在调它，且全部是 `create_engine("sqlite:///:memory:")` 或 `sqlite://`
（`tests/api/conftest.py` 的 `app` 夹具是 **function 级**，即每个测试一个新应用、
一次 `init_db`）。

代价实测：一次 `alembic upgrade head` ≈ **0.4 秒**（一个 2.08 秒的探针里跑了 2 次 upgrade
+ 3 次 check）。若让每条测试都走 alembic，光 `tests/api/` 那一个 function 级夹具就要
按测试条数量级地付这 0.4 秒：1370 × 0.4s ≈ **9 分钟**（这是**上界**——实际调用点少于
测试条数——但无论取哪一格，都远超出「142 秒的套件」可接受的范围）。

「兜底」不是一条测试，是**三条**，且**其中一条正是派单没点名的那一格**：

1. `test_alembic_upgrade_head_and_create_all_agree_table_by_table` —— 两个**磁盘**库
   （`upgrade head` vs `create_all`）反射回来逐格比（六维，见 §④）；
2. `test_the_memory_fast_path_agrees_with_the_migration_path` —— ⚠️ **这一条才是真正
   兜住测试档的**：它把**内存库**（= 测试实际走的那一档）与迁移建出来的磁盘库比同一套
   六维结构。少了它，第 1 条比的是「两个磁盘库」，而 1370 条测试用的**恰恰不是磁盘库**；
3. `test_the_scale_literals_hold_on_both_sides` —— 五个规模字面量（255/9/21/41/29）在
   **两侧**都成立，防「两侧都反射到空库 ⇒ 逐格比较一条差异也报不出来」的假绿。

另有一条把「两个『内存库』判据不许漂」钉住：
`test_db_file_of_agrees_with_is_memory_sqlite_on_memory_versus_disk`（6 格参数化）——
`app.db.session._db_file_of` 与 `app.main._is_memory_sqlite` 是**两个所有者**、答两个问题
（前者答「三档分支要看的那个磁盘文件在哪」，后者答「该不该换 `StaticPool`」），
它们在「内存库」这一格上重叠，重叠那一格漂了的症状正是「测试与生产建的不是同一个 schema」。
非 SQLite 那一格两者**刻意不同**，由
`test_db_file_of_returns_none_for_a_non_sqlite_backend` 单独写成一条断言，
免得下一个人「顺手对齐」。

### ③.2 真路径的端到端验证（`init_db` 走 alembic 的两条真链）

* **`demo.ps1 -DryRun`** → 退出码 **0**。日志里明确出现
  `INFO [alembic.runtime.migration] Running upgrade -> 53e5a548c40e, 基线迁移：…`，
  `[2/7] init_db + seed_database` 之后 `[7/7] 复核` 的 13 个行数全部正常
  （`student 60 / prescription 60 / training_log 840 / alert 32 / weekly_class_report 5 …`），
  两道禁区守卫都过（`backend\pe.db 不存在、backend\data\seed\ 仍为 0 文件 ✓`）。
* **`demo.ps1 -Port 8000`**（uvicorn 真起）→ 启动日志里 lifespan 又跑了一次 `init_db`：
  这次是**档 3**（库已存在且有版本表），alembic 只打了
  `Context impl SQLiteImpl` / `Will assume non-transactional DDL` 两行、
  **没有** `Running upgrade`（= 幂等，什么也没做），随后
  `INFO: Application startup complete.` / `INFO: Uvicorn running on http://127.0.0.1:8000`。
  `GET /api/health` → `{"status":"ok","tables":26,"students":60}`
  （`tables` 取自 `Base.metadata`，故 `alembic_version` 不会把它顶成 27）。
  ⚠️ 这两行 uvicorn 日志**出现在 alembic 的 `fileConfig` 之后**，正好验证了
  `disable_existing_loggers=False` 那一处修复（缺省 `True` 会把它们全关掉，见 §⑥ 顶回 5）。
* **`npm run smoke`** → **18/18 步全绿、499 断言 0 红、退出码 0**，打的就是上面这个
  由 alembic 建出来的演示库。（派单没要求跑它；跑它的理由是**演示库的建法变了**，
  而 smoke 是唯一一条从浏览器打到数据库的链。）

---

## ④ 一致性测试的「先红后绿」取证

**变异**：把基线迁移里 `ix_alert_batch_id` 那个索引整块删掉（`op.batch_alter_table('alert', …)`
+ `batch_op.create_index(batch_op.f('ix_alert_batch_id'), ['batch_id'], unique=False)` 两行）。

**红输出**（`python -m pytest tests/db/test_migration_baseline.py -k "agree_table_by_table or scale_literals" -q`，退出码 **1**）：

```
>       assert not diffs, "迁移建出来的库与 create_all 建出来的库不一致：\n  " + "\n  ".join(diffs)
E       AssertionError: 迁移建出来的库与 create_all 建出来的库不一致：
E           alert.indexes
E             alembic    : ()
E             create_all : (('ix_alert_batch_id', ('batch_id',), False),)
E       assert not ["alert.indexes\n    alembic    : ()\n    create_all : (('ix_alert_batch_id', ('batch_id',), False),)"]
>           assert sum(len(t["indexes"]) for t in schema.values()) == EXPECTED_INDEX_COUNT, label
E           AssertionError: alembic
E           assert 8 == 9
FAILED tests/db/test_migration_baseline.py::test_alembic_upgrade_head_and_create_all_agree_table_by_table - AssertionError: 迁移建出来的库与 create_all 建出来的库不一致：
FAILED tests/db/test_migration_baseline.py::test_the_scale_literals_hold_on_both_sides - AssertionError: alembic
2 failed, 21 deselected in 2.32s
```

两条同时红：逐格比较那条**指名道姓**报出 `alert.indexes` 两侧的实际值，
规模守卫那条报 `8 == 9`（前者告诉你哪一格、后者告诉你「不是空转」）。

**还原复核**：改前 `sha256[:16] = 4D4757D45D0E1EA5`，改后 `77897BF41C99920C`，
还原后 `4D4757D45D0E1EA5`、**逐字一致 = True**（走**字节**替换，不碰行尾）。

**绿**：还原后 `tests/db/test_migration_baseline.py` + `tests/db/test_migration_chain.py`
合计 **30 passed**（23 + 7）。

⚠️ 顺带一提：这条一致性测试比派单点名的四维（表 / 列 / 索引 / 唯一约束 / 外键）
**多了两维**——主键与 **CHECK 约束**。加 CHECK 的理由是它**承重且无声**：
29 条 CHECK 是「枚举取值域两处设防」的 SQL 那一半，autogenerate 今天会渲染它们
（实测 29/29），但没有人盯的话，下一个重新生成基线的人不会知道这一格不能丢。
另有一条 `test_the_check_constraints_have_teeth_on_the_migrated_database` 直接往
**迁移建出来的库**里插一个 `impact_level='sideways'`，断言 `IntegrityError`
（并断言那一行确实没进去）——「写在 DDL 里」与「数据库真的拒收」是两件事。

---

## ⑤ Task 2 守卫的「先红后绿」取证

守卫是 `tests/db/test_migration_chain.py::test_the_migration_chain_is_in_sync_with_the_models`：
在**空库 upgrade 到 head 之后**跑 `alembic.command.check(cfg)`（= `autogenerate --check`
的程序内等价物，走的是**与生产完全相同**的 `alembic.ini` / `env.py` / `COMPARE_OPTS`），
**应当无 diff**；有 diff 时 alembic 抛 `alembic.util.exc.AutogenerateDiffsDetected`。

**变异**（派单点名的那一种：临时给某个模型加一列）：给
`app/db/models/organisation.py` 的 `Student` 加
`drift_probe: Mapped[str | None] = mapped_column(String(16))`，**不写迁移**。

**红输出**（`python -m pytest tests/db/test_migration_chain.py -k in_sync_with_the_models -q`，退出码 **1**）：

```
>           command.check(_alembic_config(url))
>           raise util.AutogenerateDiffsDetected(
E           alembic.util.exc.AutogenerateDiffsDetected: New upgrade operations detected: [('add_column', None, 'student', Column('drift_probe', String(length=16), table=<student>))]
FAILED tests/db/test_migration_chain.py::test_the_migration_chain_is_in_sync_with_the_models - alembic.util.exc.AutogenerateDiffsDetected: New upgrade operations detected: [('add_column', None, 'student', Column('drift_probe', String(length=16), table=<student>))]
1 failed, 6 deselected in 1.81s
```

报错**直接说出了缺哪一列、什么类型**，运维不需要再去猜。

**还原复核**：改前 `sha256[:16] = B271AE495A3CC59C`，改后 `4BE4B530AA40AED5`，
还原后 `B271AE495A3CC59C`、**逐字一致 = True**。

**绿**：还原后 7 条全绿。

### ⑤.1 它为什么不是一条恒绿的守卫（红绿两档**常驻**在套件里）

一次性的「先红后绿」取证证明的是**今天**它有牙；而 `env.py` 的
`target_metadata` 一旦被改回 alembic 脚手架的缺省值 `None`，比较就有一侧是空的、
于是**永远无 diff**——那是一次静默的、以后不会再有人验证的失效。故本文件另留了
**两条常驻定点变异**，走的是与真守卫**完全相同**的代码路径：

| 常驻变异 | 实测结果 |
|---|---|
| `ALTER TABLE semester DROP COLUMN is_current`（= 模型有、库里没有） | `AutogenerateDiffsDetected: … ('add_column', None, 'semester', Column('is_current', Boolean(), …))` |
| `DROP INDEX ix_alert_batch_id` | `AutogenerateDiffsDetected: … ('add_index', Index('ix_alert_batch_id', Column('batch_id', Integer(), …)))` |

两条各钉一个维度（列比较 / 索引比较），于是「把 `compare_type` 关掉」或
「把 `render_as_batch` 那一档改坏导致索引渲染丢失」都会红。
⚠️ 选 `semester.is_current` 是有理由的：`semester` 是 26 张表里**唯一**既没有索引
也没有 CHECK 的表，故 `DROP COLUMN` 在 SQLite 上不会撞到「该列被索引/约束引用」那一档，
变异是干净的。

另两条常驻守卫钉住「基线迁移的形状」与「工具配置的形状」：

* `test_the_migration_scripts_carry_no_data` —— 计划正文逐字要求的「基线里不带数据」。
  判据是 **AST 级**的（不许调 `op.bulk_insert` / `op.execute`；非 docstring 的字符串常量
  第一个词不许是 `INSERT`/`UPDATE`/`DELETE`）。⚠️ 刻意不做子串搜索：docstring 里的
  **提及**不是**本身**（硬规矩 #109），而子串搜索还会把 `'updated_at'` 这种**列名**
  判成一条 `UPDATE` 语句。
* `test_alembic_ini_is_pure_ascii_and_carries_no_connection_string` —— 把 §②.3 那个
  GBK 的坑钉住（`raw.decode("ascii")` 抛就是红），并顺带断言 `sqlalchemy.url` 恒为空
  （用 **GBK** 解码后交给 configparser，即 alembic 自己的读法；`raw=True` 是承重的，
  因为 `script_location` 的值里有 `%(here)s`）。
* `test_the_migration_scripts_are_utf8_without_bom_and_parse` —— `migrations/**` 在
  `tests/architecture/` 那两条 `sorted(BACKEND.rglob("*.py"))` + `ast.parse` 的扫描面内，
  一个 BOM 或一处语法错误会让**架构测试**炸在很远的地方；本条让真因报在真因上。
  同时断言 `migrations/**` 里**没有相对导入**（那两条守卫会核对
  `_package_of(py) == py.parent.parts`，而 `migrations/` 不是包）。
* `test_the_guard_is_not_vacuous_because_the_chain_really_has_revisions` —— 把
  「迁移链是空的」与「迁移链不同步」报成两种不同的错。

---

## ⑥ 待清扫 / 关切 / 没按派单做的 / **顶回**

### ⑥.1 顶回（**6 处**，其中 2 处 Critical）

**顶回 1（Critical）——「`alembic.ini` 里留空占位 + 注释说明」这一条照做会让服务起不来。**
派单 §1.2 要求「`alembic.ini` 里留空占位 + **注释说明**『真值在 PE_DB_URL，与 app 同源』」。
实测：alembic 1.20.0 的 `alembic.util.compat.read_config_parser` 用 `encoding="locale"`
（中文 Windows = GBK）读那个文件，**一行 UTF-8 中文注释**就让每一条 `alembic` 命令在启动期抛
`UnicodeDecodeError: 'gbk' codec can't decode byte 0x80 in position 30`。
⚠️ 这不只是「命令行不能用」：`init_db` 的档 1/2/3 全都走 `Config(str(ALEMBIC_INI))`，
也就是**uvicorn 起不来**，而报错在 `configparser` 里、离真因有三层。
**处置**：`alembic.ini` 全篇改成纯 ASCII 英文（内容照派单要求：`sqlalchemy.url` 空占位 +
说明真值在 `PE_DB_URL`），中文理由搬到 `migrations/env.py` 与 spec §13.7
（两者都由 Python 按 UTF-8 读），并加一条常驻守卫
`test_alembic_ini_is_pure_ascii_and_carries_no_connection_string` 钉住。

**顶回 2（Critical）——「把 alembic 加进 `backend/requirements.txt`」做不到：那个文件不存在。**
派单 §1.1 写「加进 `backend/requirements.txt` 与 `backend/pyproject.toml` 的依赖表
（**两处都要**）」。实测：`Get-ChildItem -Recurse -Filter "requirements*.txt"` 在全仓
（排除 `node_modules`）返回 **0 个文件**；`backend/` 下只有 `pyproject.toml` 一份依赖清单。
新建一份 `requirements.txt` 等于给「本仓依赖哪些包」造**第二个所有者**，
而这正是本仓一路在消除的形状（`engine()` 删掉 `sqlite:///pe.db` 缺省值、
`DEMO_DB_URL` 不在 `demo.ps1` 里敲第二遍、`DB_URL_ENV_VAR` 只有一个住址……）。
**处置**：只改 `backend/pyproject.toml`，并把版本**精确钉死**（`alembic==1.20.0`，
全表唯一一个 `==`；理由写在它上方那段注释里：autogenerate 会把它自己对 DDL 的渲染
写进**入库的**迁移脚本，换一个版本就可能换一种渲染，故「用哪个 alembic 生成的」
是迁移脚本本身的一部分事实）。

**顶回 3——「有一个测试钉着依赖清单的 sha256 指纹（Plan 02 立的）→ 它会红」不成立。**
派单 §1.1 与计划 §1 最后一条都断言加依赖会撞红一条「依赖清单指纹测试」，并要求
「按硬规矩 #88 先跑全量把红收进来、更新指纹、并在该测试的 docstring 里写明
『alembic 是计划 06 用户批准的唯一新增后端依赖』」。
实测：`backend/tests/**` 下 **6** 个文件用 `hashlib`，钉的全是 `backend/data/**` 的知识资产
——`STANDARD_FINGERPRINT = D2C8E539E2FA0029`（国标评分表）、
`EXERCISES_FINGERPRINT = 5394B37F01DAC9AC`（动作库）、
`EQUIVALENCE_FINGERPRINT = 822CB86A5E998301`（等价映射）、
`ALERT_RULES_FINGERPRINT = E48E3AC82BB45BB7`（预警阈值）、
`TEMPLATE_FINGERPRINTS`（18 套处方模板），**没有一条钉依赖清单**。
`git grep -n "pyproject\|requirements" -- backend/tests` 只命中
`tests/api/conftest.py:12` 的一句 docstring（讲 `[tool.pytest.ini_options]` 只有两项）。
交叉验证：改完 `pyproject.toml` 之后跑全量，**红的只有我自己新加的那两条文件里的东西**，
既有 1340 条一条都没红（1370 passed）。
**处置**：没有指纹要更新。「alembic 是本计划唯一被批准的新增后端依赖」这句话改为写在
①`pyproject.toml` 那一行依赖上方的注释里、②spec §13.7 的最后一段、③本报告。
⚠️ 顺带一条**关切**：既然没有这条守卫，「悄悄加依赖」在本仓今天**没有任何东西会拦**
（前端有 `smoke.mjs` 第 17 步那族静态守卫，后端没有对应物）。是否要补一条
「`pyproject.toml` 的 `dependencies` 数组逐字钉住」的守卫，建议交控制者裁定
（我没有擅自加：那会超出本 Task 的范围，而且它的期望值该由谁拥有需要先定）。

**顶回 4——采纳派单点出的②：档 2 的 `stamp` 之前必须先比对结构。**
计划 §1 原文只写「库存在但**没有** `alembic_version` 表 → **`alembic stamp <基线>`**」，
那在「旧库结构与基线不一致」时会**静默错**：`stamp` 成功、版本表写上基线、结构却还是旧的，
此后没有任何一处会再报错，只会在离真因很远的地方 500 —— 正是本仓一路在消除的失效形状。
**处置**：实现 `_assert_shape_matches_revision`（把**基线修订**现算到一个一次性临时库上、
`inspect` 它，与旧库比**表名 + 每表列名**两维），不一致就 `RuntimeError`，
报错指名道姓（缺哪些表、哪张表缺哪些列、多哪些表）并给出处置建议。
失效方向是「起不来」，与 `demo.ps1` 那两道禁区守卫同一个姿势。实测见 §③ 最后一行。
⚠️ **刻意不拿 `Base.metadata` 当基准**：那是 **head** 的结构，从第二条迁移起两者就不等了，
拿 head 当基准会把一次**合法的**升级判成失败（甲方从版本 N 升到 N+1 时，
他手里的库正是「无版本表 + 结构 = 版本 N 的基线」）。
⚠️ 已知边界（登记为关切 2）：比对只到**表名 + 列名**，类型/宽度/索引/CHECK 层面的漂移
不在档 2 的范围内（那由开发期那两条守卫挡）。

**顶回 5——采纳派单点出的③：`batch_alter_table` 的纪律**提前**落地，不只是写进文档。**
派单问「本波只有基线、没有 alter，但纪律一节要不要提前写明」。答：**要，而且不止写明**。
`migrations/env.py` 的 `COMPARE_OPTS` 里**今天就把 `render_as_batch=True` 打开了**——
基线里一条 ALTER 都没有，故它**不改变本波任何输出**（实测：9 个索引被包进
`batch_alter_table`，一致性测试仍 0 差异）；开着它是为了**下一条**迁移：
SQLite 没有 `ALTER COLUMN` / `DROP CONSTRAINT`，不开的话改列宽/改可空的迁移会
**在甲方现场跑到一半** `NotImplementedError`，而那时库已经改了一半。
纪律同时写进 spec §13.7 的「人审不可省」第 2 条（并提醒：批处理会**重建整张表**，
故人审时要额外确认索引、CHECK、外键的 `ondelete` 有没有跟着过来）。
⚠️ 另加一格派单没提的：`compare_type=True`（alembic 缺省**不比较列类型**，
于是「把 `String(32)` 改成 `String(64)`」autogenerate 看不见、Task 2 的守卫也就抓不到；
而本仓的列宽是 spec §4 逐字钉的）。`compare_server_default=False` 也写了理由
（实测 26 张表 **0** 个 `server_default`，开了只会造 SQLite 反射噪声、让守卫长期红进而被下一个人调松）。

**顶回 6——派单点出的①「测试档继续走 `create_all` + 一致性测试兜底」够不够：够，但兜底必须是三条、且其中一条派单没点名。**
派单邀请的反驳是「你可能认为测试档也该走 alembic，给出耗时实测」。耗时实测见 §③.1
（一次 upgrade ≈ 0.4 秒；16 个既有测试文件的夹具在调 `init_db`，其中 `tests/api/` 那一个是
function 级 ⇒ 上界 1370 × 0.4s ≈ 9 分钟）。
我的结论是**不改测试档**，但「兜底」不能只是那一条一致性测试：它比的是**两个磁盘库**，
而 1370 条测试用的**恰恰是内存库**。故我**额外加了**
`test_the_memory_fast_path_agrees_with_the_migration_path`（内存库 vs 迁移库，同一套六维比较）。
⚠️ 少了这一条，「测试档走另一条路」这个不对称就**没有被任何东西覆盖**——
一致性测试会绿，而它绿的那件事与测试实际走的那条路无关。

### ⑥.2 没按派单做的（**5 处**，全部有理由）

1. **没建 `backend/requirements.txt`**（顶回 2）。
2. **没更新任何「依赖清单 sha256 指纹」，也没在任何测试 docstring 里写
   「alembic 是唯一被批准的新增依赖」**（顶回 3：那条测试不存在）。这句话改写在
   `pyproject.toml` 的注释与 spec §13.7 里。
3. **`target_metadata` 从 `app.db.session.Base` 取，不是派单写的 `app.db.models.Base`。**
   实测 `app.db.models.Base is app.db.session.Base` → **True**（同一个对象，故派单的要求
   在语义上满足了），但 `app.db.models.Base` 这个名字的来路是一条**星号导入的副作用**：
   `models/__init__.py` 的 `from ._shared import *` 并不带来 `Base`（`_shared.py` 只定义
   `JsonText` 与 `_in_domain`），真正带过来的是 `from .organisation import *`，
   而 `organisation.py` 自己写的是 `from app.db.session import Base`；那些子模块
   **刻意不定义 `__all__`**（定义了就会截断 `import *`、撞红 `_MODELS_PUBLIC_BASELINE` 那条守卫）。
   于是「从 `models` 拿 `Base`」依赖的是「某个子模块恰好 import 了它、且没有 `__all__`」
   这个**非承重**的事实。从所有者拿则不然。理由逐字写在 `env.py` 的模块 docstring 里。
4. **一致性测试比派单点名的四维多了两维**（主键 + CHECK）。理由见 §④ 末尾。
5. **额外改了 6 处已成谎话的散文**（派单没点名，硬规矩 #66 要求）：
   `app/db/models/__init__.py` 与 `app/config.py` 的「本仓不做迁移 / 没有 Alembic，也不打算有」、
   `app/main.py` 两处 `create_all`、`scripts/demo.ps1` 与 `scripts/demo_bootstrap.py` 的
   「第一步必须删旧库」那条**理由**（⚠️ 删库这一步**照旧保留**，理由换成「演示必须可复现」：
   `demo.ps1` 打印的各表行数与 `demo_bootstrap.py` 的 [6/7] 从库里取的那个真学号都是
   要念给甲方听的）、`.gitignore` 里 `pe_demo.db` 那条的括注。
   另加 spec 三处（§13.1 / §13.2 / §13.4.3），见 §⑦。

### ⑥.3 关切（**8 条**）

1. **演示库现在是脏的**。`smoke.mjs` 自己声明「本脚本**已经写脏了演示库**」
   （它建了一节课、一条快评、一次打卡、处置了一条预警、建了一个删不掉的学期）。
   ⚠️ 下次演示前必须重跑 `backend\scripts\demo.ps1`。
2. **档 2 的结构比对只到「表名 + 列名」**。若甲方那份旧库是「列都在、但类型/宽度/索引不同」，
   档 2 会放行。要不要把比对扩到类型与索引（代价：一次 `inspect` 的六维比较，
   代码可以直接复用一致性测试那个 `_normalized_schema` 的形状），建议交 Task 9 终审裁定。
3. **非 SQLite 后端不走迁移链**（`_db_file_of` 对 `postgresql+psycopg://…` 返回 `None`
   ⇒ 走 `create_all` 快路径）。spec §15 把 PostgreSQL 排在第三批；届时必须连它一起接上，
   并把 `env.py` 的 `render_as_batch` 改成 `False`（那是 SQLite 专属口径）。
   已写在 `_db_file_of` 的 docstring 里，但**今天没有守卫**（本仓没有第二个后端的测试环境）。
4. **alembic 的 INFO 日志会打到 stderr**（`Context impl SQLiteImpl` /
   `Will assume non-transactional DDL` / `Running upgrade -> …`）。在 PowerShell 里 stderr
   会被渲染成 `NativeCommandError` 红字（**不是**错误，退出码仍是 0，实测过两次）。
   嫌吵就把 `alembic.ini` 的 `[logger_alembic] level` 从 `INFO` 调到 `WARNING`——
   但我建议**留着**：甲方现场升级时，「哪一条迁移被跑了」是唯一有价值的现场证据。
5. **`backend/migrations/README` 是 alembic 生成的 38 字节存根**
   （逐字就是 `Generic single-database configuration.`），与本仓的实际口径不符
   （我们的连接串不在 ini 里）。留着是因为它是 alembic 的约定文件；
   要改就改成一句指向 spec §13.7 的话。**未改**（不在派单范围内，且它不影响任何行为）。
6. **`fileConfig(..., disable_existing_loggers=False)` 这一处修复没有专门的守卫。**
   它是实测出来的真坑（缺省 `True` 会在 uvicorn 的 lifespan 里把 uvicorn 与应用自己的
   logger 全 `disabled`，此后一条日志都不再输出、且**没有任何一处报错**），
   今天的证据是 §③.2 里「alembic 的 fileConfig 之后 uvicorn 的 INFO 仍然出现」。
   要不要补一条常驻守卫（例如断言 `env.py` 的源码里 `fileConfig` 那一行带这个 kwarg），
   交控制者裁定——它属于「AST 扫源码找一句话」那族守卫，本仓有先例但也有争议。
7. **一致性测试用 module 级夹具**（两个库各建一次，6 条测试共用），
   与本仓「夹具一律 function 级」的惯例不同。理由写在夹具 docstring 里
   （一次 `upgrade head` ≈ 0.4 秒 × 6）。若控制者认为惯例优先，改成 function 级会让
   `tests/db/` 这两个文件从 8.1 秒涨到约 12 秒。
8. **一致性测试没有加 `@pytest.mark.slow`**。计划 §1 逐字要求「那条一致性测试
   每跑一次全量就执行一次」，加标记会让这个性质失效，故**没加**。
   实测代价：新增的两个文件单独跑 **8.11 秒**；全量套件的单次运行噪声约 ±10 秒
   （改前 132.46s、改后两次 142.54s / 133.00s），故这 8 秒**落在噪声里**、
   无法从全量口径上单独量出来（见 §⑦.1 那条 ⚠️）。

### ⑥.4 待清扫（**3 条**）

1. `.superpowers/sdd/2026-10-13-实施计划06-产品级硬化/` 是本 Task 新建的账本目录，
   里面只有本报告；探针脚本一律写在 `%TEMP%` 并已删除（见 §⑦ 末尾），
   **没有**留在工作树里（架构守卫会 AST 解析工作树全部 `.py`，含未入库的）。
2. 本波起的两个长跑服务（`demo.ps1 -Port 8000`、`npm run dev`）**仍在运行**。
   若要交回一个干净的机器状态，需要 `Ctrl-C` 掉它们。
3. `backend/pe_demo.db` 是脏的（关切 1）；它已在 `.gitignore` 里，不会入库。

### ⑥.5 我自己造成、已修好的一处破坏（如实记，硬规矩 #39）

编辑 `backend/scripts/demo.ps1` 的 `.DESCRIPTION` 时，编辑工具**剥掉了文件头的 UTF-8 BOM**。
后果是**当场可用**的：PowerShell 5.1 对无 BOM 的 `.ps1` 按系统 ANSI（GBK）解码，
于是整个脚本变成 mojibake 并**解析失败**（`Unexpected token '绂佸尯澶嶆牳锛歜ackend\pe.db' …`
+ 4 条 `Missing closing '}'`），`demo.ps1` 一行都跑不了。
发现路径：跑 `demo.ps1 -DryRun` 时它当场炸（**不是**靠人眼复核发现的）。
处置：把 BOM 加回去（`bytes([0xEF,0xBB,0xBF]) + 原内容`），复核
`git diff --stat -- backend/scripts/demo.ps1` 只剩 **9 insertions / 3 deletions**
（= 我本来要改的那一段），没有整文件的行尾/BOM 噪声；随后 `demo.ps1 -DryRun`
与 `-Port 8000` 都跑通（§③.2）。
⚠️ **教训（值得进账本）**：本仓有一批 `.ps1` 是 **UTF-8 + BOM** 的，
而「行尾与 BOM」那条纪律此前只交代了 `backend/app/**` / `backend/data/**` / `Document/**`，
**没有交代 `.ps1` 的 BOM 是承重的**。凡是用会重写整个文件的编辑方式碰 `.ps1`，
都必须复核 BOM。我另外把全部 9 个改过的文件逐个与 `HEAD` 对了一遍 BOM 与行尾主流
（只有 `demo.ps1` 一处不符，已修）。

---

## ⑦ 最终验收

### ⑦.1 后端测试

| 项 | 改前（`5131c12`，本 session 亲跑） | 改后 | 判 |
|---|---|---|---|
| `python -m pytest -q` | **1340 passed**，132.46s（pytest 自报）/ **134.48s**（`Measure-Command` 墙钟） | **1370 passed**；耗时两次实测：开发中途 **142.54s**、收工时在**已提交状态**上复跑 **133.00s**（墙钟 144.45s / —） | ✅ **+30 条、0 红** |
| `--cov=app/domain --cov-branch` | 派单口径：1339 passed + 1 skipped（**耗时未在本 session 测**） | **1369 passed, 1 skipped**，266.49s / 268.64s 墙钟 | ✅ 同样 +30 |
| `app/domain/` 覆盖率四格 | **1268 / 0 / 376 / 0 / 100%** | **1268 / 0 / 376 / 0 / 100%** | ✅ **一格未动** |
| 新增两个测试文件 | — | `tests/db/test_migration_baseline.py` **23** 项（18 个函数，其中 1 条 6 格参数化）+ `tests/db/test_migration_chain.py` **7** 项 = **30** | ✅ 与 +30 对上 |

⚠️ **耗时那一格要如实读**：全量套件在本机的**单次运行噪声约 ±10 秒**（改后两次实测
142.54s 与 133.00s，改前 132.46s），故「改前改后」的差值只能报成一个区间
**+0.5…+10 秒**，不能报成一个确定的数。**可归因的增量**用另一种量法：把新增的两个文件
单独跑，实测 **8.11 秒**（`pytest tests/db/test_migration_baseline.py
tests/db/test_migration_chain.py -q` → `30 passed in 8.11s`）——这 8 秒里含十余次
`alembic upgrade head`（module 级夹具 1 次 + 每条集成测试各 1 次 + 档 2 的结构比对
每次都要现算一个临时基线库）与 3 次 `command.check`。

⚠️ 新增模块自己的覆盖率：本 Task **没有新增 `app/domain/` 下的模块**
（新增的生产代码全在 `app/db/session.py`，不在覆盖率口径的 `--cov=app/domain` 里），
故「新增模块覆盖率单独报」这一格**不适用**。`app/db/session.py` 新增的那几个函数
由 §③ 那 8 条集成测试逐档覆盖（四条路径 + 失败方向 + 两个判据的一致性）。

### ⑦.2 派单点名的每个既有常量（**全部运行时实测**，硬规矩 #89 / #111）

| 项 | 派单给的基线 | 实测 | 判 |
|---|---|---|---|
| 表数 `len(Base.metadata.tables)` | 26 | **26** | ✅ |
| 扫描面（`SCANNED_DIRS` 五个目录的 `.py` 合计） | 66 | **66**（pipeline 10 + db 12 + domain 18 + api 23 + auth 3） | ✅ |
| 端点 `app.openapi()["paths"]` | 71 路径 / 99 操作 | **71 / 99** | ✅ |
| GET 数 | 60（15 匿名 + 45 挂 security） | **60**（匿名 **15** + 挂 security **45**） | ✅ |
| `securitySchemes` | 3 格 | **3** | ✅ |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（`dir(models)` 的公有名减七个子模块名） | ✅ |
| 黄金用例 | 14 | **14**（`golden_cases.json` 的 `input` / `expected` 各 14 条） | ✅ |
| `backend/` 下 `.py` 的个数 | 派单未给（架构守卫的下界是 `>= 40`；Plan 03 Task 9 结案时 130） | **144**（+4 = `migrations/env.py`、基线迁移、两个新测试文件） | ✅ 下界不动 |
| `npm run build` | 退出码 0；CSS 65.20 kB / JS 167.03 kB | 退出码 **0**；`index-CM7Fwkho.css` **65.20 kB** / `index-eWDO9FkM.js` **167.03 kB**，`✓ built in 365ms` | ✅ **逐字不变**（本波不碰前端） |
| `npm run smoke`（派单未要求，我加跑的） | 18 步 / 499 断言 / 退出码 0 | **18/18 步全绿 · 499 断言 0 红 · 退出码 0** | ✅ |

### ⑦.3 依赖清单

⚠️ **没有「依赖清单新指纹」可报**（顶回 3：本仓不存在那条指纹测试，也不存在
`requirements.txt`）。改的是 `backend/pyproject.toml` 的 `dependencies` 数组，逐字如下
（**+1 行依赖，其余六项一字未动**）：

```toml
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "sqlalchemy>=2.0",
    "pandas",
    "numpy",
    "pyyaml",
    "alembic==1.20.0",
]
```

`backend/pyproject.toml` 改后：**1842 字节 / CRLF / 无 BOM / sha256[:16] = `B43FF464679BAEB3`**
（改前 492 字节的 blob，+14 行注释与那 1 行依赖）。
`[project.optional-dependencies].dev` 三项（pytest / pytest-cov / httpx）**未动**。
**前端 `package.json` 一个字节未动**（`git status` 里没有它），故前端新增依赖 **0**。

### ⑦.4 禁区与数据指纹

| 项 | 实测 | 判 |
|---|---|---|
| `backend/data/national_standard_2014.csv` | `D2C8E539E2FA0029` | ✅ 与钉住值逐字相同 |
| `backend/data/exercises.yaml` | `5394B37F01DAC9AC` | ✅ |
| `backend/data/exercise_equivalence.yaml` | `822CB86A5E998301` | ✅ |
| `backend/data/alert_rules.yaml` | `E48E3AC82BB45BB7` | ✅ |
| `backend/data/prescription/*.yaml` | **18** 个文件 | ✅（18 个模板指纹由 `test_template_yaml_fingerprints_are_pinned` 逐个钉，全量 1370 条绿 ⇒ 18 个都对） |
| `git diff 5131c12 HEAD -- backend/data` | **空**（`git diff --quiet` 退出码 0；`git status --porcelain -- backend/data` 也是空） | ✅ |
| `backend/pe.db` 存在 | **False** | ✅ |
| `backend/data/seed/` 递归文件数 | **0**（目录存在、0 文件） | ✅ |
| `backend/pe_demo.db` | 存在（演示库，**已在 `.gitignore`**，未入库；`git status` 里没有它） | ✅ |
| `demo.ps1` 自带的两道禁区守卫 | `-DryRun` 与 `-Port 8000` 两次都打印 `禁区复核：backend\pe.db 不存在、backend\data\seed\ 仍为 0 文件 ✓` | ✅ |

### ⑦.5 spec（`Document/2026-09-28-体育闭环原型-设计spec.md`）

| 项 | 改前（开工时 `read_bytes()` 复核） | 改后 |
|---|---|---|
| 字节数 | **205 466** | **215 556** |
| 行数（CRLF 数） | **1 675** | **1 795** |
| CRLF / bareLF | 1675 / **0** | 1795 / **0** |
| BOM | **无** | **无** |
| `sha256[:16]` | **`A4C072354CA82AA5`**（与派单给的逐字相同） | **`F4A5653C5249ACF1`** |

改动是**四处**（一律用 python 改、`read_bytes()`/`write_bytes()` 往返，全程 CRLF）：

1. **新增 §13.7「改数据库模型（`app/db/models/**`）的流程 —— Plan 06 Task 1 起必须配一条迁移」**
   （插在 §13.6 之后、§14 之前；`###` 级，与 §13.1–§13.6 同级）。内容：四步流程
   （改模型 → `alembic revision --autogenerate` → **人审** → 守卫绿）、
   autogenerate 的**三个已知会错**的地方（`JsonText` 的 import / SQLite 的批处理 / 改名认不出来）、
   另两格实测事实（`-m` 的中文会进文件名；alembic 按 `output_encoding` 写 UTF-8 + CRLF）、
   两条守卫各自的判据与「红了说明什么」、`init_db` 四条路径的表、
   档 2「先比对」那条顶回的完整交代与已知边界、`alembic.ini` 必须纯 ASCII 的实测证据、
   连接串的唯一所有者、以及「新增依赖只有 alembic 一个 + 为什么它是全表唯一 `==` 钉死的」。
2. §13.1 那一句「`init_db` 走 `create_all`……而本仓不做迁移，故『schema 改动 = 重建库』」
   → 按实际改写，改前那句**逐字留在原地**（硬规矩 #39）。
3. §13.2 代码块里那句注释「lifespan 里的 init_db 会 create_all」→ 同上。
4. §13.4.3 那一段「`init_db` 走 `create_all`，对已存在的表原样跳过、不会补列……
   旧演示库会在第一次碰口令的请求上 500」→ 按实际改写，并**如实交代处置变了**：
   那种旧库今天会被档 2 的结构比对**当场拒绝**（`RuntimeError`，服务起不来），
   而不是在离真因很远的地方 500。

⚠️ 派单只要求「在 spec §13 加一小节」。第 2/3/4 处是**额外**改的，理由是硬规矩 #66：
「本仓不做迁移」这句话在 spec 里有三处、在代码散文里有六处，只加一节新流程而不改它们，
spec 就会**自相矛盾**（§13.1 教人删库、§13.7 教人写迁移），而下一个人读到的是先出现的那一句。

### ⑦.6 本波全部改动（`git diff --stat 5131c12 HEAD` 的口径）

| 文件 | 性质 |
|---|---|
| `backend/pyproject.toml` | 改（+14 行：1 行依赖 + 13 行注释） |
| `backend/alembic.ini` | **新**（4 250 B，纯 ASCII，CRLF） |
| `backend/migrations/env.py` | **新**（12 251 B，CRLF） |
| `backend/migrations/script.py.mako` | **新**（732 B，alembic 生成、行尾规范化成 CRLF） |
| `backend/migrations/README` | **新**（38 B，alembic 生成的存根；见关切 5） |
| `backend/migrations/versions/53e5a548c40e_baseline.py` | **新**（33 373 B / 566 行，CRLF） |
| `backend/app/db/session.py` | 改（6 321 → 22 634 B；`init_db` 四条路径 + 4 个私有辅助 + 3 个约定常量 + 散文） |
| `backend/tests/db/test_migration_baseline.py` | **新**（34 480 B / 23 项） |
| `backend/tests/db/test_migration_chain.py` | **新**（16 628 B / 7 项） |
| `backend/app/db/models/__init__.py`、`backend/app/config.py`、`backend/app/main.py`、`backend/scripts/demo.ps1`、`backend/scripts/demo_bootstrap.py`、`.gitignore` | 改（**只改散文**，一行可执行代码都没动；`demo.ps1` 那处含 BOM 复原，见 §⑥.5） |
| `Document/2026-09-28-体育闭环原型-设计spec.md` | 改（+120 行，见 §⑦.5） |
| `.superpowers/sdd/2026-10-13-实施计划06-产品级硬化/task-1-2-report.md` | **新**（本报告） |

⚠️ **`backend/app/**` 的可执行代码只改了 `app/db/session.py` 一个文件**；
其余五个 `app/**` 与 `scripts/**` 文件的改动**全部在 docstring / 注释 / comment-based help 里**
（`git diff` 逐行核过）。这是刻意的：本 Task 的行为面只有「库怎么建」这一件事。

### ⑦.7 commit sha

| # | sha | 一句话 |
|---|---|---|
| ① | **`e73ed57`** | `feat(db): Plan 06 Task 1 ① —— 引入 alembic + 26 张表的基线迁移`（6 files changed, 917 insertions） |
| ② | **`83c378a`** | `feat(db)!: Plan 06 Task 1 ② —— init_db 改走迁移链（三档 + 内存库快路径）+ 一致性守卫`（8 files changed, 979 insertions, 45 deletions） |
| ③ | **自指，无法印在这里**（见 §⑦.8） | `test(db)+docs(spec)+docs(sdd): Plan 06 Task 2 —— 迁移链纪律守卫 + spec §13.7 + 实现者报告` |

### ⑦.8 ③ 的 sha 为什么印不进本报告

本报告**随 ③ 一起入库**，故 ③ 的 sha 是它自己内容的一部分哈希 —— 印进去就会改变它、
从而改变 sha（自指）。处置：③ 的 sha 与「本报告字节数 == 入库 blob 字节数」的复核结果
写在**交回控制者**的那一席（`git log --oneline -1` 与
`git cat-file -s $(git rev-parse HEAD:<本报告路径>)` 两个实测值）。
⚠️ 本报告入库前用 python 写、`read_bytes()` 复核过行尾与 BOM：
**LF / 无 BOM**，与 `.superpowers/sdd/` 下既有报告一致
（实测 `2026-10-12-实施计划05A-…/task-1-2-report.md`：83 303 B / CRLF 0 / bareLF 986 / 无 BOM）。

### ⑦.9 探针与临时文件的清理

全部探针脚本写在 `%TEMP%`（**不在工作树里**，故架构守卫的
`sorted(BACKEND.rglob("*.py"))` 扫不到它们），共 **16** 个：
`pe_probe_env.py`（spec 四格 + 基线测试尾部）、`pe_probe_eol.py`（行尾主流）、
`pe_to_crlf.py`（行尾规范化工具）、`pe_probe_meta.py`（`Base.metadata` 26 表规模）、
`pe_probe_initdb.py`（`init_db` 四条路径）、`pe_probe_consistency.py`（六维规范化比较 +
`command.check` 试跑）、`pe_probe_metadata.py`（§②.4 那张逐表核对表的生成器）、
`pe_probe_chain.py`（Task 2 守卫的负对照机制 + SQLite 版本）、
`pe_probe_redgreen.py`（§④/§⑤ 两次先红后绿的取证）、
`pe_probe_encoding.py`（alembic 写迁移文件的编码）、
`pe_probe_eolcheck.py` / `pe_probe_bom.py`（改过文件的行尾与 BOM 复核）、
`pe_probe_accept.py`（§⑦.2 那张常量表）、`pe_patch_spec.py` / `pe_patch_spec2.py`
（spec 的两次改写）、`pe_write_msgs.py`（commit 消息）。
`migrations/versions/` 下由 encoding 探针生成的两个一次性修订文件
（`69600e750eb1_encoding_probe.py`、`d009fc344a65_编码探针.py`）与其 `__pycache__`
**已全部删除**，实测 `migrations/versions/` 下只剩 `53e5a548c40e_baseline.py` 一个
**迁移脚本**（`git ls-files backend/migrations` 实测入库的就是 `README` / `env.py` /
`script.py.mako` / `versions/53e5a548c40e_baseline.py` 四个 + `backend/alembic.ini`；
目录下另有 `.gitignore` 覆盖的 `__pycache__/`，是跑测试时 alembic 加载版本文件的产物）。
%TEMP% 下的探针与它们生成的临时库（`pe-initdb-probe-*` / `pe-consistency-probe-*` /
`pe-chain-probe-*` / `pe-schema-probe-*` / `pe_baseline_*.db`）在收工时**已实测删除**
（复核脚本数出删掉 **42** 项、`%TEMP%` 下本波残留 0 项；工作树里也没有游离的
`pe_*.py`）。⚠️ 两个例外：`%TEMP%\pe_serve8000.txt` 与 `pe_vite.txt` 是那两个**仍在跑**
的服务的 tee 日志，被进程占用而 `PermissionError` 删不掉——停掉服务后即可删（待清扫 2）。
⚠️ 另有 `%TEMP%` 下三个**不是本波的**残留（`pe_t1_probe`、`pe_t4_probe.py`、
`pe_t4_probe_out.txt`，命名与本波的 `pe_probe_*` 不同族），**刻意没动**。

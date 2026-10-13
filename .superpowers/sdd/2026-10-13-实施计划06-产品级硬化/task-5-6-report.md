# Plan 06 Task 5 + Task 6 实现者报告 —— 请求审计留痕 / 备份与恢复脚本

> 分支 `p06/audit-backup`（自 `main` 的 `912f3b4` 起，**未 push、未碰 main**）。
> 派单：实施计划 06 的 §5（Task 5 请求审计留痕）+ §6（Task 6 备份与恢复）。
> 目标口径：**要交付给甲方的产品级系统** —— 运维要能回答「谁在什么时候对什么做了什么」，
> 以及「库坏了怎么回到昨天的状态」。
> **四个 commit**：`5af9384`（①）/ `0aa137a`（②）/ `3142abc`（③）/ ④（spec + smoke 传导
> + 本报告）。⚠️ **④ 的 sha 不写在本文件里**——本报告就在那个 commit 内部，
> 自嵌 commit sha 与自嵌 digest 是同一类问题（没有不动点）；sha 见**给控制者的回信**。
> ⚠️ 派单「建议 4 个 commit」，**实际就是 4 个**，但①②的**切分线与派单不同**
> （派单把「中间件 + 隐私守卫」放进①，实现者放进了②）——理由与取证见 §6.3 第 1 条。
> 结论速览：**顶回 1 处**（`at` 由 UTC 改 naive **本地**时刻）、**核过维持 2 处**、
> **没按派单做的 3 处**（逐条见 §6.3）；后端 **1426 → 1465 collected**（**+39** = 20 条审计
> + 19 条备份恢复，⚠️ **既有测试一条判据都没改**，改的只有「计数」）；表数 **27 → 28**；
> `smoke.mjs` **18 步 / 499 断言 / 退出码 0**；`app/domain/` 覆盖率四格
> **1268/0/376/0/100%**（一格未退）；**新增依赖 = 0**；`backend/data/**` **零字节改动**。

---

## 1. 环境

开工第一件事（硬规矩 #73），逐字实测：

```
$ node --version; npm --version; python --version
v24.19.0
11.17.0
Python 3.11.1
$ python -c "import alembic, fastapi, sqlalchemy, starlette; ..."
alembic 1.20.0
fastapi 0.141.1
sqlalchemy 2.1.3
starlette 1.7.0
$ python -c "import sys; print(sys.executable)"
C:\Python\python.exe          # ⚠️ 无 venv
```

| 格 | 实测 | 与派单给的基线 |
|---|---|---|
| Node / npm | v24.19.0 / 11.17.0 | ✅ 逐字相同 |
| Python | 3.11.1（`C:\Python`，**无 venv**） | ✅ |
| alembic / FastAPI | 1.20.0 / 0.141.1 | ✅ |
| SQLAlchemy / starlette | 2.1.3 / **1.7.0** | ✅ |
| 后端基线全量 | **1426 passed**（`137.63 s`，**不带** `--cov`） | ✅ 逐字复跑过 |
| 端口 | 8000（`demo.ps1`，只为跑 `smoke.mjs` 与 `npm run build` 的对照） | — |

⚠️ **「1426」这一格的口径要说清**（否则与终测的「1464 passed + 1 skipped」对不上账）：
本仓**唯一**一条会 skip 的测试是 `tests/pipeline/test_backfill.py:299` 那条**既有的**
「trace 钩子哨兵」（`if sys.gettrace() is not None: pytest.skip(...)`），它**只在带
`--cov` 时才 skip**。故同一个提交点：不带 `--cov` 是 `1426 passed / 0 skipped`，
带 `--cov=app.domain --cov-branch` 是 `1425 passed / 1 skipped`——**collected 恒为 1426**。
终测同理：`1464 passed + 1 skipped` = **1465 collected** = 1426 + 39。**两个口径都记在这里**，
以免控制者拿「1426 passed」去减「1464 passed」得到 38 而怀疑少了一条。

⚠️ **行尾与 BOM 一律实测、不假设**（派单 §3 点了上一波 `.ps1` 被剥 BOM 的事故）。
开工先量了每一个将要改的文件的 `bytes / lines / crlf / bareLF / bom`，改完再量一遍；
`backend/scripts/demo.ps1` 实测是 **UTF-8 + BOM + CRLF**（20167 B / crlf 273 / 裸 LF 0）。
⚠️ 本 Task **只改了它注释里的一个数**（`# 27 张表` → `# 28 张表`，落在 commit ①，
`git show 5af9384 --stat` 里是 `2 +-` = 一行换一行），改前改后**都复量过**
（`bom=True`、`crlf=273`、字节数 20167 **未变**——那一行的两个数字等宽）。
本 Task 新写的两个 `.ps1` 也是 **BOM + CRLF**，且**钉成守卫**（§5.4）。

⚠️ **探针一律放 `$env:TEMP\t56_probes\`**：删除前那一刻实测该目录 **35 个文件**
（`p00`–`p28` 的 `.py` 探针 **29** 个 + `p18`/`p20` 两个 `.ps1` 探针 + `msg1`–`msg4`
四个 commit 消息临时文件；29 + 2 + 4 = 35），跑完不入库，**收尾时整目录删除**（§7.9）。
⚠️ 其中 `p24`–`p28` 是**写本报告时**才加的（不动点渲染、三轮措辞修订、写 commit 消息），
故本节第一次落笔时那个清单是短的；⚠️ 而 `p28` 正是把这一行改对的那一个 ——
它**自己**也在被数的 35 个里，删除时一起删掉，故这一格自洽。
所有文件编辑都走 python：`read_bytes` → **在 LF 口径下匹配替换** → 折回 CRLF → `write_bytes`，
每一处替换都带**期望命中数断言**（命中数不符就当场抛，不静默少改）。
⚠️ 这一格是**撞出来的**：多行 `SearchReplace` 在本仓（CRLF）上**匹配失败**过若干次，
而失败的样子是「报找不到」而不是「改错」，故一律改走 python 脚本。

---

## 2. 审计的实测矩阵（逐格）

### 2.1 落地口径

**一张表 + 一个中间件 + 一个只读端点**，判据只有**一个**住址：

```
audit_log（第 28 张表）      backend/app/db/models/audit.py
中间件 + should_record()     backend/app/api/audit.py
GET /api/audit-logs          backend/app/api/routers/audit.py（+ schemas/audit.py）
建表迁移                     backend/migrations/versions/7f3923d8af84_audit_log.py
```

`should_record` 的**全部内容**是 `method.upper() in AUDITED_METHODS`，
`AUDITED_METHODS = frozenset({"POST", "PATCH", "DELETE"})`。**没有任何路径白名单**。

⚠️ 派单 §1 第 2 条要求「login / logout / 两个 bind 本就是 POST，故自然覆盖 —— **核实**，
不要写第二份判据」。**核实结果**（实读 `app/api/routers/auth.py` 的五个装饰器）：
四个都是 `@router.post` → 自然覆盖；第五个 `GET /api/auth/me` **刻意不记**（它是读）。
故本模块**一个以 `/api/` 开头的字符串常量都没有**，这一格被**钉成结构事实**
（AST 扫 `app/api/audit.py`，见守卫 `test_the_four_auth_events_are_all_covered_by_the_single_method_predicate`）。

### 2.2 活体矩阵（探针 `p01_audit_matrix.py`，真起 `TestClient`、真打请求、真查库）

下面每一行都是**本报告写作时重跑一遍**的实测输出（不是抄早前的记录）：

| # | 动作 | 期望 | 实测 |
|---|---|---|---|
| ① | 匿名两次读（`GET /api/health`、`GET /api/standards`） | **0 行** | 状态码 `(200, 200)`、**行数 0**；顺带 `/api/health` 的 `tables=28` ✅ |
| ② | 学生绑定（`POST /api/auth/students/bind`，体里有 `birth` + 明文口令） | 1 行 | `id=1 kind=anonymous sid=None staff=None POST /api/auth/students/bind -> 204 target=None` |
| ② | 登录 + 一次写（`POST /api/auth/login` → `POST /api/training-logs`） | **恰好 2 行** | `id=2 kind=student sid=1 POST /api/auth/login -> 200`；`id=3 kind=student sid=1 POST /api/training-logs -> 201` ✅ |
| ③ | **错口令**登录 | 1 行且 `anonymous` | `401`；`id=5 kind=anonymous sid=None staff=None POST /api/auth/login -> 401` ✅ |
| ③ | 匿名写 | 1 行且 `anonymous` | `401`；`id=6 kind=anonymous … POST /api/training-logs -> 401` ✅ |
| ③ | 匿名 POST 一个**不存在**的路径 | 1 行 | `404`；`id=7 kind=anonymous … POST /api/definitely-not-a-route -> 404 target=None` ✅（探测行为正是要留的东西） |
| ④ | 管理员 `PATCH /api/students/1` | 1 行、`target='1'` | `200`；`id=10 kind=teacher sid=2 staff=T0003 PATCH /api/students/1 -> 200 target='1'` ✅ |
| ④ | 管理员 `POST /api/semesters`（路径无参数） | 1 行、`target=None` | `201`；`id=11 … POST /api/semesters -> 201 target=None` ✅ |
| ⑦ | `POST /api/auth/logout` | 1 行且**保住**登出者的身份 | `204`；`id=14 kind=teacher sid=2 staff=T0003 POST /api/auth/logout -> 204` ✅ |

### 2.3 `GET /api/audit-logs` 的三档（其实是**六**档）状态码

| 身份 | 档 | 实测 |
|---|---|---|
| 管理员（`T0003`，`role='admin'`） | cookie | **200** |
| 普通教师 | cookie | **403** |
| 学生 | cookie | **403** |
| 匿名 | — | **401** |
| 学生（dev 档请求头 `X-Student-Id`） | header | **401**（学生**没有**读审计的身份，故请求头那一档直接 401，不是 403） |
| 教师（dev 档请求头 `X-Teacher-Staff-No`，非管理员） | header | **401**（`current_teacher` 在请求头档只认管理员那一族，与本仓既有口径一致） |

⚠️ 派单只要求「教师 403、学生 403、匿名 401」三档；**实测把 dev 档的两条请求头路径也打了**，
因为它们走的是**另一条**身份解析分支（`deps.current_teacher` 的 header 支 vs cookie 支），
只测 cookie 会漏掉「请求头档也能读审计」这一类错。

信封与分页（实测）：

```
信封键 = ['items', 'limit', 'offset', 'total']   total = 13  limit = 50  offset = 0
items[0] = {'id': 13, 'at': '2026-10-13T21:51:51.780093', 'subject_kind': 'student',
            'subject_id': 1, 'staff_no': None, 'method': 'POST',
            'path': '/api/auth/login', 'status': 200, 'target': None}
```

⚠️ `ORDER BY id DESC`（最新在前），且 **`total` 与 `items` 共用同一个 WHERE**
（守卫 `test_total_and_items_share_the_same_filter`：过滤之后 `total` 必须等于**过滤后**的行数，
否则运维会看到「total 13 而 items 只有 2 条」这种自相矛盾的页）。

### 2.4 过滤（**两个**参数，派单上限 3）

| 查询 | 实测 | 说明 |
|---|---|---|
| `?subject_kind=anonymous` | `total 6`，返回行的 kinds = `{'anonymous'}` | ✅ |
| `?method=delete`（**小写**） | `total 0` | ✅ 先 `upper()` 再校验，故小写是**合法输入**、答案是「真没有删除」 |
| `?method=PATCH` | `total 1`，methods = `{'PATCH'}` | ✅ |
| `?method=GET` | **422** | ⚠️ **刻意**：`GET` 不在 `AUDITED_METHODS` 里。若做成「静默 0 行」，运维会读成「今天没有 GET」——而真相是「本表根本不记 GET」。**422 是唯一不骗人的答案** |
| `?subject_kind=ghost` | **422** | 同上，取值域引 `AuditLog.SUBJECT_KINDS`，不是字面词表 |
| `?limit=2&offset=1` | `items 2`、`total 13`、ids `[12, 11]` | ✅ 分页与排序对得上 |

### 2.5 它**不进** `catalog.RESOURCES`（派单 §1 第 5 条）

`catalog.RESOURCES` 仍是 **23 行**、一个字未动。守卫
`test_the_audit_table_is_not_a_resource_and_has_no_write_endpoint` 同时钉两格：
① `AuditLog.__tablename__` 不在 `RESOURCES` 的键里；② 全仓 openapi 里**没有任何**
指向 `/api/audit-logs` 的 `post`/`patch`/`delete`（它是**只读**的，审计表被写就等于证据可被改）。
⚠️ 走泛型工厂会得到四个错（写端点、名册语义、`normalized_scores` 对账、前端 23 行的反查），
逐条写在 `routers/audit.py` 的模块 docstring 第一节。

⚠️ **它自己不产生审计行**（它是 GET），故「审计页自己喂自己」这个自我放大回路不存在
（实测 `审计端点自己的 GET 有没有被记？ -> False`）。

### 2.6 定点变异（派单 §1 第 6 条 ⑥）

`test_the_two_mutations_of_the_record_predicate_are_caught` 把变异打在
**`AUDITED_METHODS` 这个模块级全局**上（`should_record` 在**调用时**读它），
于是变异走的是与真守卫**完全相同**的那条代码路径，而不是旁路：

| 变异 | 打在哪 | 哪条守卫红 | 实测 |
|---|---|---|---|
| **A：把 GET 也记** | `AUDITED_METHODS |= {"GET"}` | ②「匿名读 = 0 行」的 `_rows(engine) == []` | ✅ 红，多出来的那一行是 `GET /api/health` |
| **B：把写不记** | `AUDITED_METHODS = frozenset()` | ①「登录 + 一次写 = 恰好 2 行」的 `len(added) == 2` | ✅ 红，`added` 是空 |

⚠️ 两格都**真发请求**。只断言 `should_record("GET") is True` 是**静态**的，
它证明不了中间件真的照那个判据写库——「判据对、而中间件没接上」是这类改动最常见的坏法。

---

## 3. 隐私守卫的取证（派单 §1 第 3 条 + 第 6 条 ④）

### 3.1 行为面：真发一次带口令的请求，然后把落库的**每一行 × 全部 9 列**逐列扫

守卫 `test_a_login_with_a_password_leaves_no_trace_of_that_password_in_the_audit_row`：

1. **真发**一次学生绑定（体里有 `birth` 与明文口令 `pe-demo-2025`）与一次登录（体里有明文口令）；
2. 把 `audit_log` 落库的**每一行 × 全部 9 列**都 `str()` 一遍，扫四个探针串：
   口令原文 / `birth` 的 ISO 串（`2007-03-08`）/ 它的紧凑串（`20070308`）/ `"password"` 这个词本身；
3. 断言 `offenders == []`。

**活体取证**（探针 `p01`，本报告写作时重跑）：

```
⑧ 隐私扫描：14 行 × 9 列
   列名 = ['id', 'at', 'subject_kind', 'subject_id', 'staff_no', 'method', 'path', 'status', 'target']
   → offenders = []
```

⚠️ **列名取自字面量 `EXPECTED_COLUMNS`、不从 `AuditLog.__table__` 读回来**（硬规矩 #35）。
两侧同源的话，将来谁加一列 `body`，遍历会**自动**多扫一列、守卫**仍然绿**——
而那正是唯一会漏秘密的改法。字面量的好处是：加一列会让「9 列」这条断言**当场红**，
逼人回来重读这一节。

⚠️ 并有一拍**反空转**：用 `app.auth.passwords.verify_password` 证明那一串口令
**确实**被提交过（否则这条守卫是在扫一批从未接触过秘密的行，绿得毫无意义）。

### 3.2 结构面：把「不记请求体」钉成三条**代码性质**，而不是一句承诺

| 守卫 | 它钉的事实 | 口径 |
|---|---|---|
| `test_the_audit_module_never_reads_the_request_body` | `app/api/audit.py` 里**没有** `.body()` / `.json()` / `.form()` / `.stream()` 的**调用** | ⚠️ **AST 判、不是文本搜索**：本模块的 docstring 里恰好就有那几个词的**提及**（硬规矩 #109「提及不是本身」），文本口径会当场误报 |
| `test_no_audit_schema_mentions_a_credential_or_a_body` | 三个 schema 的**字段名**里不出现 `password` / `birth` / `body` / `secret` / `credential` / `token` | 挡住「将来给 `AuditLogRead` 加一个 `body` 字段」这一档 |
| `test_the_method_column_deliberately_has_no_check_constraint` | `audit_log` 的 **9 列全是标量**、**一个 `JsonText` 都没有** | ⚠️ 「没有能装请求体的列」是比「不往列里写」更强的一格：前者让漏秘密在**类型上**就不可能 |

⚠️ 第三条守卫同时钉了**另一个**决定：`method` 列**刻意没有 CHECK 约束**。
理由是「记与不记」的判据只有**一个**住址（`AUDITED_METHODS`），
若在库里再钉一份取值域，就成了**第二份判据**；且那样一来 §2.6 的**定点变异 A**
会红在 `IntegrityError` 上、而不是红在**行数**上——后者才是运维真正会看到的坏法。
这一格是**有意的重复性缺失**，故写成守卫，免得将来有人「顺手补个 CHECK」。

---

## 4. 迁移

### 4.1 第三条迁移

```
backend/migrations/versions/7f3923d8af84_audit_log.py
  revision      = '7f3923d8af84'
  down_revision = '0b7da3d20211'      # ← Task 3 的 login_attempt
  6594 字节 / 105 行 / CRLF 105 / 裸 LF 0 / **无 BOM** / sha256[:16] = 91babe51bb33e535
```

链实测（`alembic history`，本报告写作时重跑）：

```
<base> -> 53e5a548c40e, 基线迁移：把 Plan 06 之前那 26 张表一次性建出来（Plan 06 Task 1）。
53e5a548c40e -> 0b7da3d20211, 迁移 2：加 ``login_attempt`` 一张表（Plan 06 Task 3）。
0b7da3d20211 -> 7f3923d8af84 (head), 迁移 3：加 ``audit_log`` 一张表（Plan 06 Task 5）。
$ python -m alembic heads   → 7f3923d8af84 (head)          # 单头
$ python -m alembic check   → No new upgrade operations detected.   rc=0
```

⚠️ **`alembic check` 干净**是这一节最硬的一格：它证明「模型」与「迁移」**没有漂移**
（本 Task 加了表也加了迁移，若哪一格漏了，`check` 会当场报出待生成的操作）。

### 4.2 生成方式是 autogenerate，diff **恰好两行**

用 `alembic revision --autogenerate` 生成，**人审之后**的 diff 恰好两行：

```
INFO  [alembic.autogenerate.diff] Detected added table 'audit_log'
INFO  [alembic.autogenerate.diff] Detected added index 'ix_audit_log_subject_kind_at' on ('subject_kind', 'at')
```

⚠️ 「恰好两行」是**判据**而不是描述：多出一行就意味着模型里还有别的漂移被顺手带进来了。
落地的 DDL（`upgrade()`）：

```python
op.create_table('audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('at', sa.DateTime(), nullable=False),
    sa.Column('subject_kind', sa.String(length=16), nullable=False),
    sa.Column('subject_id', sa.Integer(), nullable=True),
    sa.Column('staff_no', sa.String(length=32), nullable=True),
    sa.Column('method', sa.String(length=8), nullable=False),
    sa.Column('path', sa.String(length=256), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.Column('target', sa.String(length=64), nullable=True),
    sa.CheckConstraint("subject_kind IN ('anonymous', 'student', 'teacher')",
                       name='ck_audit_log_subject_kind'),
    sa.PrimaryKeyConstraint('id'))
with op.batch_alter_table('audit_log', schema=None) as batch_op:
    batch_op.create_index('ix_audit_log_subject_kind_at', ['subject_kind', 'at'], unique=False)
```

⚠️ `downgrade()` 是**真能跑**的（先 drop index 再 drop table，走 `batch_alter_table`
以适配 SQLite），不是 `pass`。

### 4.3 索引：派单给了「`(at)` 或 `(subject_kind, at)`」二选一，实现者选**后者**

`ix_audit_log_subject_kind_at (subject_kind, at)`。理由：运维的两问都是
「**某个主体**在**某段时间**里干了什么」（`WHERE subject_kind='anonymous' AND at BETWEEN …`
正是 §2.4 那个过滤端点的形状），复合索引对这两问都命中；
而单列 `(at)` 对第一问只能扫时间段内的全部行。
⚠️ 复合索引的**最左前缀**是 `subject_kind`，故「只按时间、不按主体」的那一问**用不上它**——
这是本格的代价，如实记（§6.2 第 3 条）。

### 4.4 纪律格

| 格 | 实测 |
|---|---|
| `alembic.ini` 纯 ASCII | ✅ `4250 字节 / ascii=True / bom=False`（派单逐字要求；它的 `output_encoding = utf-8` 正是为了让迁移文件里的中文 docstring 不以本机 GBK 落盘） |
| 迁移文件行尾 | ✅ CRLF 105 / 裸 LF 0 / 无 BOM（与 `backend/**` 一致） |
| `render_as_batch` / `compare_type` | ✅ 沿用 `migrations/env.py` 既有设置，**一个字没改** |
| `tests/db/test_migration_chain.py` | ✅ 链长 **3**、单头、`down_revision` 逐格对得上（改的只有计数） |
| `tests/db/test_migration_baseline.py` | ✅ `HEAD_REVISION='7f3923d8af84'`、`walk_revisions()` == **3**、`EXPECTED_TABLE_COUNT_WITH_VERSION` = **29**（28 + `alembic_version`）、列 **270**、索引 **11**、唯一 **21**、外键 **41**、CHECK **31** |

⚠️ **表数「28」与「29」这两个数并存是有意的、且被写成注释**：
`GET /api/health` 数的是 `Base.metadata`（**28**，不含 `alembic_version`），
磁盘上 `sqlite_master` 里是 **29**。`restore.py` 的自检打印的是后者，
故它的输出里**逐字写着**这句提醒（见 §5.3 的实测输出），免得运维以为恢复错了库。

### 4.5 表数 27 → 28 的**全量传导**（派单 §1 第 6 条）

commit ① 一共动了 **22 个文件**（`git show 5af9384 --stat`：611 insertions / 151 deletions），
其中「计数」那一类逐格如下。**每一处都用带期望命中数断言的 python 脚本改**，
命中数不符就抛（§1）：

| 住址 | 改前 → 改后 |
|---|---|
| `app/main.py` 的 `/api/health` docstring | 27 → **28** |
| `app/db/session.py` / `app/db/models/__init__.py` / `migrations/env.py` 的表数陈述 | 27 → **28** |
| `app/api/crud.py` / `app/api/routers/catalog.py` / `models/feedback.py` / `models/prescription.py` / `pipeline/report_stage.py` 里的相关计数 | 逐格 +1 |
| `backend/scripts/demo.ps1` 的注释 | `# 27 张表` → `# 28 张表`（**BOM/CRLF 未动**） |
| `tests/db/test_models.py` | 函数名 `test_all_twenty_seven_tables_created` → **`…twenty_eight…`**；`expected` 集合 + `audit_log`；3 处 `== 27` → `== 28`；`_MODELS_SUBMODULES` 7 → **8**；`_NON_PUBLIC_TABLE_CLASSES` + `("audit", ("AuditLog",))`（checked 13 → **14**）；`_in_domain` 那一圈 28 → **29** |
| `tests/seed/test_generate.py` | **新开第五个分区** `AUDIT_TABLES = ("audit_log",)`（⚠️ 见 §6.3 第 3 条）；穷尽性守卫的**并集**与**长度之和**都加它 |
| `tests/db/test_migration_baseline.py` | 见 §4.4 |
| `frontend/scripts/smoke.mjs` 第 1 步 | `tables == 27` → `== 28`（**两处**） |
| `frontend/scripts/smoke.mjs` 第 12 步（openapi 四格） | ⚠️ **落在 commit ④**，见 §6.3 第 2 条 |

⚠️ **Ruling 97 那一格**：`audit_log` 住进**新建的** `app/db/models/audit.py`（**非**星号导入），
**不是** `ops.py`（它是 `from … import *`）。若放进 `ops.py`，`AuditLog` 会顺着星号进
`app.db.models` 的公有面，撞 `_MODELS_PUBLIC_BASELINE == 33` 那条守卫——
而那条守卫**刻意不抬**（抬它等于允许「新表默认对外可见」）。
`tests/db/test_models.py` 的 `_NON_PUBLIC_TABLE_CLASSES` 因此多了一格 `("audit", ("AuditLog",))`，
把「它**必须**不在公有面」钉成正向断言。

---

## 5. 备份与恢复的端到端取证

### 5.1 形态与「新增依赖 = 0」

```
backend/scripts/backup.py     28039 B / 501 行 / CRLF / 无 BOM   ← 承重
backend/scripts/restore.py    22069 B / 393 行 / CRLF / 无 BOM   ← 承重
backend/scripts/backup.ps1     3826 B /  73 行 / CRLF / **BOM**  ← 薄包装
backend/scripts/restore.ps1    4866 B /  91 行 / CRLF / **BOM**  ← 薄包装
backend/tests/test_backup_restore.py  55877 B / 1059 行 / 19 条守卫
```

⚠️ **新增依赖 = 0**：备份走标准库 `sqlite3` 的 `.backup()`、校验走 `hashlib`、
路径走 `pathlib`。`tests/test_dependencies.py` 那份清单**一字未动**，
本 Task 收尾时重跑 **6 passed**（§7.4）。
守卫 `test_neither_script_copies_files_or_adds_a_dependency` 用 **AST** 钉两格：
① 两个脚本里**没有** `shutil` 的 import、也没有 `shutil.copyfile` / `copy2` 的调用；
② 两个脚本的 import 全部落在标准库与本仓之内。

### 5.2 备份（探针 `p14_backup_probe.py`，本报告写作时重跑）

```
== ① 备份 ==
   备份文件 = pe-20261013T030405Z.db   286720 字节
   侧车     = pe-20261013T030405Z.db.sha256
   侧车内容 = 'sha256=f1937c97ab2104482ac41d01f66a4fab641f389607978257912a1d541cfd69d9\nbytes=286720\n'
   read_sidecar = {'sha256': 'f1937c97…', 'bytes': 286720}
   sha256_of(dest)[:16] = f1937c97ab210448        # ← 与侧车逐字吻合

== ② 文件名与 label ==
   backup_name()      = pe-20261013T030405Z.db     # naive
   backup_name(naive) = pe-20261013T030405Z.db     # 同一串
   backup_name(+08)   = pe-20261013T030405Z.db     # ⚠️ 带时区的也被折成同一个 UTC 名字
   label 那一份       = pe-20261013T030405Z-pre-restore.db

== ⑥ 在线备份期间可以并发写吗 ==
   写事务进行中仍然备份成功： pe-20261013T135044Z.db 286720 字节
   （且那个**未提交**的事务不在备份里 —— 快照语义，不是「拷到一半」）
```

**`.backup()` 而不是复制文件**（派单 §2 第 2 条）：`sqlite3.Connection.backup()` 走
SQLite 自己的在线备份接口（`sqlite3_backup_init/_step/_finish`），在**一个读事务里**逐页拷，
故拿到的永远是某一时刻的**一致快照**，且**不阻塞写**——那是「每天夜里 cron 一次、
服务不停机」能成立的前提。⚠️ 与 `shutil.copyfile` 的差别**不是快慢、是正确性**：
一次写事务的新页此刻可能还在 `-journal`（rollback 模式）或 `-wal`（WAL 模式）里，
主库文件**不是一个自洽的库**；复制出来的那一份可能少半个事务，
恢复上去是 `file is not a database`——或者更糟：**能打开、而某些行是半截的**。

**库路径与 app 同源**（派单 §2 第 4 条）：`db_path_from_url` **复用**
`app/db/session.py` 的 `make_url` 与 `_db_file_of`，**没有写第二个解析器**。
优先级实测：

```
== ④ 缺省解析 ==
   没设 PE_DB_URL → …\backend\pe_demo.db          # ← 与 demo.ps1 同一个缺省
   设了 PE_DB_URL → …\Temp\…\target.db
   显式实参        → …\Temp\…\explicit.db          # --db-url 最高
   内存库拒绝 ✓ → 这个 URL 不指向一个磁盘上的 SQLite 文件，故备份/恢复无从谈起：'sqlite://'
```

⚠️ **刻意不回落 `DEFAULT_DB_URL`**：那个常量指向 `backend/pe.db`，
而 `pe.db` 是本仓的**禁区**（它不得存在）。回落它等于「配置写错时，
静默去操作一个禁区路径」；现在的行为是**当场拒绝并说清为什么**。

**禁区守卫**（派单 §2 第 6 条）实测三档全部拒绝，且**在写任何文件之前**：

```
== ③ 禁区守卫 ==
   拒绝 ✓ sqlite:///…/backend/pe.db
        → 拒绝操作 …\backend\pe.db：backend/pe.db 是本仓的**禁区**（它不得存在）…
   拒绝 ✓ sqlite:///…/backend/data/x.db
        → 拒绝操作 …\backend\data\x.db：backend/data/** 是专家维护的知识…
   拒绝 ✓ sqlite:///…/backend/../backend/pe.db        # ⚠️ 绕路径也被挡：先 Path.resolve()
        → 拒绝操作 …\backend\pe.db：…
```

### 5.3 恢复（探针 `p15_restore_probe.py`，本报告写作时重跑）

**四步的顺序是承重的**：① 校验侧车 → ② 探写锁 → ③ 自动备份当前库（后路）→ ④ 覆盖。
任何一步失败都发生在**动手之前**，故「拒绝」永远等于「目标库一字节未动」。

```
== ① 建库灌 1 行 → 备份 → 改那一行 → 恢复 ==
   建好：  备份点的名字
   备份：  pe-20261013T030405Z.db
   改后：  改坏了的名字
   恢复后：备份点的名字                                    ← ✅ 回到备份点
   自检：  {'tables': 29, 'revision': '7f3923d8af84', 'students': 0}
   后路：  pe-20261013T135053Z-pre-restore.db              ← ✅ 覆盖前自动备份了当前库

== ② 篡改侧车 sha → 拒绝 ==
   拒绝 ✓ → 侧车文件 …\pe-20261013T030405Z.db.sha256 的 sh…    退出码 = 2
   改回来之后 verify ✓ → {'sha256': '22bb5ae875fd4a35…', 'bytes': 286720}

== ③ 篡改备份文件 1 字节 → 拒绝 ==
   拒绝 ✓ → 拒绝恢复 pe-…Z.db：sha256 不吻合。侧车说 22bb5ae875fd4a35…，实测 fdc2ca681ddf2b60…。
            ⚠️ 这一份被动过（哪怕只改了 1 个字节），恢复上去得到的是一个坏库——
            而它**看起来**是好的，故本脚本一律拒绝。请换一份备份
   改回来之后 verify ✓ → sha256 22bb5ae875fd4a35

== ④ 侧车丢了 → 拒绝 ==
   拒绝 ✓ → 侧车文件不存在：…\pe-20261013T030405Z.db.sha256

== ⑤ 目标库被写锁占住 → 一句人话 ==
   拒绝 ✓ → 目标库 …\target.db 正被别的进程占着（SQLite 报 database is locked）：
            **请先停服务**再恢复。⚠️ 恢复要覆盖整个库文件，而一个正在写的 uvicorn 会让…
   锁放掉之后放行 ✓

== ⑥ 目标库不存在 → 恢复到一个新位置 ==
   后路 = None （应当是 None：没有东西可丢）
   自检 = {'tables': 29, 'revision': '7f3923d8af84', 'students': 0}

== ⑦ --no-verify 那一档 ==
   跳过校验仍然恢复成功，sidecar = None 后路 = None

== ⑨ 禁区：恢复到 pe.db ==
   拒绝 ✓ → 拒绝操作 …\backend\pe.db：backend/pe.d…
   backend/pe.db 存在吗 -> False
```

`main()` 的实测打印（退出码 **0**）——⚠️ 这就是甲方运维会看到的那一屏：

```
== 厦大体育数智系统 · 恢复 ==
   备份   …\backups\pe-20261013T030405Z.db
   目标   …\target.db
   ⚠️ 恢复会**覆盖**目标库。请先停服务（Ctrl-C 那个 uvicorn）。
   校验   sha256 22bb5ae875fd4a35… / 286720 字节 ✓
   后路   …\backups\pe-20261013T135055Z-pre-restore.db（覆盖前自动备份的当前库；恢复错了就用它再恢复一次）
   字节   286720

   自检   sqlite_master 里的表数 = 29
          alembic_version = 7f3923d8af84
          student 行数 = 0

   ⚠️ 表数比 GET /api/health 报的**多 1**：health 数的是 Base.metadata
      （不含 alembic_version），本自检数的是磁盘上的表。
   现在可以起服务了：backend\scripts\demo.ps1 -Port 8000（⚠️ 它会**删掉**
   演示库重灌，故要保住刚恢复的这份请手工起 uvicorn，见 demo.ps1 的模块注释）。
   rc = 0
```

**退出码约定**：`0` = 成功；`2` = **拒绝执行**（校验不过 / 禁区 / 源不存在 / 目标被占），
此时目标库**一字节未动**；`1` = 意料之外的异常。
⚠️ `2` 与 `1` 分开是有用的：cron 里 `2` 意味着「人得来看一下选错了哪一份」，
`1` 意味着「脚本或环境坏了」。

### 5.4 两个 `.ps1`：**BOM + CRLF**，且被守卫钉住

派单 §2 第 1 条点了上一波的实现者被工具剥掉 BOM 导致 PowerShell 5.1 解析失败。
**本 Task 把那个事故原地复现了一遍**，作为「为什么必须钉守卫」的取证：

```
# 探针 p18_ps1_probe.ps1 —— 4082 B / bom=False / crlf=0 / lf=72（用写文件工具直接落盘的版本）
$ powershell -NoProfile -ExecutionPolicy Bypass -File …\p18_ps1_probe.ps1
At …\p18_ps1_probe.ps1:2 char:27
+ $ErrorActionPreference = "Stop"
+                           ~~~~~
Unexpected token 'Stop"
…
Write-Host "==' in expression or statement.          ← 第 1 行的中文注释被按 GBK 解码、吞掉了引号
```

⚠️ 机理：无 BOM 时 PowerShell 5.1 按**平台 ANSI（本机 GBK）**解码脚本，
UTF-8 的中文字节被拆成别的字符，其中**恰好包含引号**，于是从第一行起语法就崩了。
修法是**`b"\xef\xbb\xbf" + CRLF`** 用 python 写（探针 `p16_write_ps1.py`），
落成 `p20_ps1_probe.ps1`（`3426 B / bom=True / crlf=77`）→ 一次通过。

入库的两个 `.ps1` 因此都是 **BOM + CRLF**，且这一格**不靠人记**，靠守卫
`test_the_two_ps1_wrappers_are_utf8_with_bom_and_crlf`（逐字节量 `bom` / `crlf` / 裸 `LF`）。

**`.ps1` 端到端实测**（探针 `p20_ps1_probe.ps1`，PowerShell 5.1，本报告写作时重跑，`rc=0`）：

```
== 1) 语法解析（不执行）==
   backup.ps1  解析 OK, token=138, 语法错误=0
   restore.ps1 解析 OK, token=200, 语法错误=0

== 3) backup.ps1 ==                       退出码 = 0；产出 .db=1 .sha256=1
== 4) 改坏 + restore.ps1 ==
   name = BROKEN                          ← 改坏后
   退出码 = 0
   name = PS1-PROBE                       ← ✅ 恢复回备份点
   后路那一份 = 2 个: pe-…Z-pre-restore.db  pe-…Z-pre-restore.db.sha256
== 5) 篡改侧车 -> restore.ps1 ==
   恢复失败（拒绝执行）：拒绝恢复 pe-…Z.db：字节数不吻合。侧车说 1，实测 286720（差 286719 字节）…
   退出码 = 2（应当非 0）                  ← ✅
== 6) 禁区: --DbUrl 指到 backend\pe.db ==
   备份失败：拒绝操作 …\backend\pe.db：backend/pe.db 是本仓的**禁区**（它不得存在）…
   退出码 = 2（应当非 0）                  ← ✅
   backend\pe.db 存在吗 -> False           ← ✅ 禁区路径**没有**被创建出来
OK
```

⚠️ **薄包装的边界也被钉成守卫**：`.ps1` 里只允许「切目录 / 传参数 / 交回退出码」，
承重的逻辑一律在 `.py`。守卫扫的是 **`#>` 之后的代码段**
（`<# .DESCRIPTION #>` 里**提及** `sqlite3` / `Get-FileHash` 是文档，不是实现——
硬规矩 #109 的又一格；⚠️ 第一版扫全文，当场误报），断言：
代码段里**没有** `sqlite3` / `Get-FileHash` / `Copy-Item` 的实际调用、
`python` **恰好被调用一次**、且有一拍 `Set-Location $Backend`
（否则 `python scripts/backup.py` 这个相对路径会在别的 cwd 下找不到文件）。

### 5.5 `.gitignore` 与「一个备份都没入库」

`.gitignore` 加了 **一行** `backend/backups/`（`3945 B / 74 行 / CRLF / 无 BOM`）。
⚠️ 派单要求「核实没把别的放进来」——**核实结果**：本次 diff 只有那一条 hunk、
只加了那一行与它的说明注释，**没有**顺手改任何既有规则。
守卫 `test_backups_are_gitignored_and_none_is_tracked` 钉两格：
① `git check-ignore backend/backups/x.db` 命中；② `git ls-files backend/backups` **为空**。
收尾实测：`backend/backups/` 目录**不存在**（§7.2），即**没有任何备份产物入库**。

### 5.6 19 条守卫的清单

```
端到端      test_backup_then_restore_puts_the_changed_row_back
两种篡改    test_a_tampered_sidecar_makes_restore_refuse
            test_a_tampered_backup_file_makes_restore_refuse
后路        test_restoring_leaves_a_pre_restore_safety_net
            test_the_safety_net_is_skipped_when_there_is_nothing_to_lose
逃生口      test_no_verify_and_no_auto_backup_are_explicit_escapes
可读的错    test_a_locked_target_answers_with_a_readable_error
在线语义    test_the_backup_is_taken_online_while_a_write_transaction_is_open
零依赖      test_neither_script_copies_files_or_adds_a_dependency
侧车两格    test_the_sidecar_carries_both_facts
路径同源    test_the_db_path_comes_from_the_same_owner_as_the_app
禁区        test_the_forbidden_paths_are_refused
坏输入      test_a_missing_or_empty_source_is_refused_before_writing_anything
            test_the_sidecar_parser_reports_which_line_is_broken
自检        test_the_selfcheck_reports_what_is_really_on_disk
BOM/CRLF    test_the_two_ps1_wrappers_are_utf8_with_bom_and_crlf
gitignore   test_backups_are_gitignored_and_none_is_tracked
真库零改动  test_the_two_scripts_never_touch_the_real_database_or_the_data_directory
main 的口径 test_the_two_mains_return_zero_and_print_measured_facts
```

⚠️ **`test_the_two_scripts_never_touch_the_real_database_or_the_data_directory` 改过一次口径，
如实记**：第一版是**文本**口径（扫两个脚本的源码里有没有 `pe.db` 这个字符串常量），
结果它把**禁区守卫自己的 assert 消息**也判成 offender（那句消息里必须点名 `pe.db`
才能说清禁的是哪个）——**文本口径分不清「点名禁区」与「操作禁区」**。
改成**行为面**：动作前后对 `backend/data/**` 逐文件量 `(大小, sha256)` 快照并比对、
外加 `backend/pe.db` 不存在、外加 `backend/backups/` 没多出文件。

⚠️ **`test_a_tampered_backup_file_makes_restore_refuse` 也改过一次断言**：
第一版断言「篡改 1 字节之后那个文件**仍能打开**」（想说明「坏库看起来是好的」），
实测是 `sqlite3.DatabaseError: database disk image is malformed`——
第 100 个字节恰好落在 b-tree 页头上，于是「看起来是好的」这一档**在这个偏移上不成立**。
删掉那一拍，换成更强的两格：**sha 变了**、而**字节数没变**
（后者证明侧车那两格**不冗余**：一个只校验字节数的实现会**放行**这次篡改）。

---

## 6. 待清扫 / 关切 / 没按派单做的 / 顶回

### 6.1 待清扫（3 条）

1. **读审计（GET）今天不记** —— 见 §6.2 第 1 条。这是**派单口径**、实现者核过不顶回，
   但它的代价必须挂账：「**一个教师翻了哪些学生的健康档案**」今天在库里查不到。
   ⚠️ 要补的**正确**做法是**另开一张读审计表**（体量、留存期、清理策略都不同），
   **不是**把 GET 塞进 `audit_log`（99 个操作里 60 个是 GET，一屏学生详情就打出 5–8 行，
   这张表会**当天**变成全库最大的表，而它**没有**清理任务）。已写进 spec §13.9 的已知局限。
2. **`audit_log` 没有清理/归档任务** —— 它单调增长。甲方现场跑一年之后，
   `ix_audit_log_subject_kind_at` 仍然好用，但**备份文件**会跟着变大
   （今天 286720 B 是空库）。建议下一波加「保留 N 天 + 归档到冷文件」的任务，
   与 `backup.py` 的 `backups/` 目录一起管。
3. **管理台没有审计页面** —— 派单 §1 第 5 条逐字写「管理台页面本波不做」，
   故运维今天只能 `curl`/浏览器直接打 `GET /api/audit-logs`。
   ⚠️ 端点是**齐的**（分页 + 两个过滤），前端那一格是纯体力活。
4. **`Document/**` 没有钉行尾**，故 spec 的「字节数」是一个**随检出环境变**的数
   （工作树 253238 B / 入库 blob 251031 B，见 §7.7）。⚠️ 这不是本 Task 引入的，
   但本 Task 是**第一个把 spec 的字节数印进报告**的（前两份报告印的是别的文件）。
   正确的修法是给 `Document/**` 加 `.gitattributes` 规则，⚠️ 而那会重写几十个文件，
   应由控制者单独裁一次，不该夹在本 Task 里。
5. **索引对「只按时间、不按主体」那一问用不上** —— 复合索引最左前缀是 `subject_kind`（§4.3）。
   若运维的主用法其实是「给我最近 200 条，不管谁」，那今天的 `ORDER BY id DESC LIMIT 200`
   走的是**主键**、也够快；但 `WHERE at BETWEEN …`（不带 `subject_kind`）会全表扫。
   挂账，等看到真实用法再决定要不要补一个单列 `(at)`。

### 6.2 顶回（**1 处真顶回 + 2 处核过维持**）

派单 §4 说「若认为某条是错的一定顶回来」，并点了三处最可能的。**逐条回**：

#### ① 真顶回：`at` **不是** UTC，而是 naive **本地**时刻

派单 §1 第 1 条写 `at`(UTC)。**实现者顶回**，落地成 naive 本地时刻
（`app.auth.sessions.now()`，与本仓其余**全部** DateTime 列同一个所有者）。三条理由：

1. **一致性**：本库其余每一格 DateTime（`user_session.expires_at`、`login_attempt.at`、
   `training_log.submitted_at`、`leave_request.*`……）**都是** naive 本地。
   只有 `audit_log.at` 是 UTC 的话，任何跨表的时间比较都**静默差 8 小时**，
   而 SQLite 的 `DateTime` **不带时区**，故这个错**不会报错**、只会给运维错答案。
2. **它与 `login_attempt` 记的是同一批事件**：一次失败的登录会同时落一行
   `login_attempt` 与一行 `audit_log`。运维对账时最常用的动作就是
   「把这两张表按时间并排看」——若一张 UTC 一张本地，同一次尝试的两行**差 8 小时**，
   这个对账**当场失效**。
3. **文件名那一侧已经是 UTC 了**：`backup.py` 的 `pe-<UTC ts>.db` 用 UTC
   （因为文件名要跨机器可比、且不能带 `:`）。**两格各自选对的口径**，
   而不是「全都 UTC」——库里给运维看的是本地，文件名给机器排的是 UTC。

⚠️ 顶回的**代价**如实记：`at` 不带时区，故若甲方把库搬到另一个时区的机器上，
历史行的「本地」就失去了参照。这一格写进了 spec §13.9（含「要改成 UTC 的正确做法是
**整库一起改**、不是只改这一列」）。

#### ② 核过、**维持**派单：恢复前自动备份**不是**多余的

派单 §4 问「恢复前自动备份是否多余」。**核过，维持**，理由是它挡的失效**唯一**：
「**人选错了备份**」。校验（sha256 + 字节数）能挡住「这一份坏了」，
挡不住「这一份是好的、但不是我想要的那一份」——那是一份**完好**的旧库，
校验全绿，覆盖上去之后**没有任何机制**能回到覆盖前。
⚠️ 成本是**一次在线备份**（今天 286720 B，毫秒级），换的是「恢复错了还能再恢复一次」。
实测取证见 §5.3 ①（`后路 = pe-…Z-pre-restore.db`）。
⚠️ 并有一格**跳过**：目标库不存在或 0 字节时**不做**后路（没有东西可丢），
守卫 `test_the_safety_net_is_skipped_when_there_is_nothing_to_lose` 钉住
（否则「恢复到一个全新位置」会在 `backups/` 里留一个 0 字节的垃圾后路）。
⚠️ 也留了显式逃生口 `--no-auto-backup`（守卫 `test_no_verify_and_no_auto_backup_are_explicit_escapes`），
但**默认是开**的。

#### ③ 同意派单：`target` 从**路径模板**取，**绝不**解析响应体

派单 §4 说「不要解析响应体，从路径模板取，取不到就空」。**同意，照做**。
落地口径比「路径模板」再窄一格：取 `request.scope["path_params"]`，
**当且仅当它恰好一个键**时取那个值的**原文字符串**，否则 `None`。

- ⚠️ **不做 `int()`**：`PATCH /api/students/abc`（422）那一行若做转换会**抛**，
  于是那一行**消失**——而那正是审计最该留的一格（有人在拿垃圾打写端点）。
  原文字符串让它留下 `target='abc'`。
- ⚠️ **多个路径参数时取 `None`、不拼接**：拼接（`"1/2"`）会造出一个
  **既不是 id 也不是模板**的第三种口径，运维没法用它做等值过滤。
  宁可空。本仓今天只有 0 或 1 个路径参数，故这一格是**为将来**留的。
- ⚠️ **不解析响应体**的三条理由：① 那要读 `response.body`，而 `BaseHTTPMiddleware`
  拿到的是流，读它就得重建响应（一份新的失效面）；② 响应体里可能有**秘密**
  （§3 的整节纪律会被一处「顺手取个 id」破掉）；③ 它与 `path` **同源**，
  故信息量是零——`path` 已经逐字写着 `/api/students/1` 了。
  `target` 的价值是**把 id 单独拎出来当列**，好做等值过滤与索引，不是提供新信息。

守卫 `test_the_target_column_comes_from_the_path_and_never_from_the_response_body`：
真发一次 `PATCH /api/students/1`（响应体里有 `"id": 1` 与一堆别的数字），
断言 `target == "1"`；再真发一次响应体里**含 1 而路径不含**的请求，断言 `target is None`。

#### ④ 派单点的第四处「GET 一律不记」——**核过、不顶回**

派单 §4 也把它列为最可能的顶回之一（「是否该给管理台的读也记」）。
**核过，不顶回**，三条理由：① 体量与噪声（§6.1 第 1 条）；
② 自我放大（审计端点自己是 GET，记 GET 会让这张表**自己喂自己**、且**没有**清理任务）；
③ 「做了什么」的**全部**语义都在写里——一次读**不改变**任何状态，
它的风险是**隐私**风险，而隐私风险的正确落点是**另一张表**（不同的留存期、不同的可见性）。
⚠️ 而它的**代价**如实记在 §6.1 第 1 条，并写进 spec §13.9 的已知局限。

### 6.3 没按派单做的（**3 处**）

1. **commit ① 的切分线与派单建议不同**。派单建议 ① = 「`audit_log` 模型 + 迁移 +
   **中间件 + 隐私守卫**」；实现的 ① = 「模型 + 迁移 + **表数 27→28 的全量传导**」，
   中间件与隐私守卫在 ②。
   **理由**：派单 §3 同时要求「**尽量让每个中间 commit 也自洽**」，而这两条**互相冲突**——
   若把中间件放进 ①，① 里就有一个**已接线**的中间件、而**表数那一圈还没同步**
   （`test_models.py` 的 `== 27`、`smoke.mjs` 的 `tables == 27`、health 的 docstring……），
   于是 ① **红一片**。按实现的切法，① 是「加了一张**没人用**的表 + 把所有计数同步到位」，
   ② 是「接线 + 端点 + 20 条守卫」，**两个都自洽**。
   ⚠️ **实测取证**：用 `git stash push --include-untracked` 把工作树清干净、
   在 **`5af9384` 上跑全量 = 1426 passed**（与基线逐字相同，因为 ① **一条新测试都没加**，
   只改既有测试的**计数**）；在 **`0aa137a` 上 = 1446 passed**（1426 + 20）。
   ⚠️ ③（`3142abc`）是**纯新增**（6 个文件、2131 insertions、0 deletions），
   故它天然自洽（1446 + 19 = 1465 collected）。
2. **`frontend/scripts/smoke.mjs` 的 openapi 四格落在 ④、不在 ②**。
   派单建议 ② 含「传导同步（表数/openapi/smoke）」。实际 ② 只同步了**后端**的 openapi 五格
   （`tests/api/test_prescription_api.py`），`smoke.mjs` 第 12 步那四格
   （71→72 / 99→100 / 81→82 / 60→61）落在 ④。
   **理由**：`smoke.mjs` 要**真起服务**才能验（它打的是 `http://127.0.0.1:8000/openapi.json`），
   而实现者是在 ④ 这一波才重灌演示库、跑通 `18/18 · 499 断言 · 退出码 0`。
   ⚠️ **代价如实记**：这意味着 **`0aa137a` 上跑 `smoke.mjs` 会红 4 拍**
   （第 12 步的四个数字）。②的自洽性因此只对**后端全量**成立、不对 smoke 成立。
   若控制者要求「每个 commit 都能跑 smoke」，这一格需要 rebase 挪动，
   ⚠️ 实现者**没有**擅自 rebase（那会重写三个已有 commit 的 sha）。
   ⚠️ `smoke.mjs` 第 1 步的 `tables == 28`（**两处**）**在 ①**里，
   因为那一格与后端表数是同一条口径、必须同步落地。
3. **`audit_log` 归进新开的第五个分区 `AUDIT_TABLES`，而不是塞进 `AUTH_TABLES`；
   且新建 `models/audit.py` 子模块，而不是放进 `ops.py`**。
   派单没点这两格，但它们是「加一张表」的必然选择，故记在这里。
   - **分区**：`tests/seed/test_generate.py` 的穷尽性守卫原本有四个分区
     （`CORE_TABLES` / `AUTH_TABLES` / `OPS_TABLES` / `PRESCRIPTION_TABLES`）。
     `audit_log` **可以**塞进 `AUTH_TABLES`（它记的主体确实是身份），
     但那个分区的**名字**是「auth」，而审计**不是**鉴权的一部分
     （它是鉴权**之后**的留痕，且 `subject_kind` 有一档是 `anonymous` = **鉴权失败**）。
     塞进去会让「按名字找表」这个最常见的动作指向错处。故**新开第五个**
     `AUDIT_TABLES = ("audit_log",)`，并把穷尽性守卫的**并集**与**长度之和**都加上它
     （⚠️ 后者是关键：只加并集的话，「新开一个空分区」不会被发现）。
   - **子模块**：见 §4.5 的 Ruling 97 那一格（`ops.py` 是星号导入，
     放进去会撞 `_MODELS_PUBLIC_BASELINE == 33`）。

### 6.4 其它关切（不阻塞，但控制者该知道）

1. **审计行写在响应之后、且写失败不影响响应**。`AuditMiddleware` 在 `call_next` 返回**之后**
   写库，且 `record()` 自己开 `Session`、自己 `commit`、异常**吞掉**（记 log）。
   ⚠️ 这是一个**有意的取舍**：审计写失败（例如库满了）不该让一次**已经成功**的业务写
   在客户端看起来失败——那会导致「业务其实成了、而用户以为没成、于是再点一次」。
   代价是：**审计可能丢行**。若甲方要求「审计不可丢」，正确做法是把审计写进
   **业务同一个事务**（那要求中间件能拿到业务的 Session，是一次结构性改动），
   或者写成 append-only 文件。**今天没做**，挂账。
2. **`install_audit` 排在 `_install_cors` 之前** → Starlette 的栈是**后加的在外**，
   故 **CORS 在外、审计在内**。两格好处：① **预检**（`OPTIONS`）不进审计
   （它不是业务动作，量还很大）；② 审计看到的 `status` 与浏览器**最终收到**的一致
   （CORS 头是在外层加的，不改 status）。
   ⚠️ 且它**不影响** `_selfcheck_prod`（那个自检只数 `CORSMiddleware`，实测未动）。
3. **`at` 的分辨率是微秒，但同一毫秒内的两行仍可能同 `at`**，故排序**不用** `at`、
   用 **`id DESC`**（单调、唯一）。`at` 只用于**过滤**与**给人看**。
4. **`subject_id` 刻意不建外键**（与 `user_session.student_id` 那一格的决定**相反**，
   且相反的**理由**写在 `models/audit.py` 的 docstring 里）：
   留痕必须在**主体消失之后**仍然可读。若建外键，删一个学生会让他的历史审计行
   要么**删不掉学生**、要么**级联删掉证据**——两个都是错的。
   ⚠️ 代价：`subject_id` 可能指向一个已不存在的行，故端点**不做** join、
   前端也**不该**拿它去查名册。
5. **两档部署都工作**（dev 的请求头档 / prod 的 cookie 档），守卫
   `test_the_audit_trail_is_written_in_both_deployment_tiers` 用 `monkeypatch` 把
   `PE_ENV` 打到 `production` 再真发一次写，断言审计行**照样**落库
   （⚠️ 中间件在**身份解析之后**取 subject，而两档的解析路径不同，
   故这一格是**必须**测的，不是凑数）。
6. **两个 `.ps1` 的「CRLF」依赖 `core.autocrlf=true`** —— 这是复核 §7.7 那一格时
   **顺带量出来的**，且它**不是**本 Task 引入的：入库 blob 实测是
   `backup.ps1` 3753 B / `restore.ps1` 4775 B / `demo.ps1` 19894 B，**三个都是 LF**，
   而工作树是 3826 / 4866 / 20167 B、**三个都是 CRLF**（差恰好等于各自的行数）。
   即「`.ps1` 检出成 CRLF」靠的是本机 `core.autocrlf=true`，**不是**仓库里钉的规则。
   ⚠️ **BOM 不受影响**（它在 blob 里逐字存在，实测三个都是 `bom=True`），
   故在 `autocrlf=false` 的机器上检出，PowerShell 5.1 仍然读得对（有 BOM 就按 UTF-8 解码，
   LF 行尾 PowerShell 也接受）——**脚本仍然能跑**。
   ⚠️ 会红的是**守卫** `test_the_two_ps1_wrappers_are_utf8_with_bom_and_crlf`
   （它断言 0 个裸 LF）。⚠️ 而那条守卫的**第三拍**正是为此设的 canary：
   它同时量既有的 `demo.ps1`，故「检出环境变了」会让它**一起**红、而不是只红新文件
   ——那一拍的断言消息逐字写着「既有那一款 `demo.ps1` 的形状变了，本条的『同款』判据要跟着改」。
   实现者**没有**去改 `.gitattributes`（理由同 §7.7 那条），改为**如实挂账**：
   若甲方现场要在 Linux/WSL 上检出这个仓库并跑那两个 `.ps1`，
   正确做法是给 `backend/scripts/*.ps1` 加一条 `text eol=crlf`。

---

## 7. 最终验收

### 7.1 全量回归与覆盖率

```
$ python -m pytest -q --cov=app.domain --cov-branch
Name                                   Stmts   Miss Branch BrPart  Cover
TOTAL                                   1268      0    376      0   100%
1464 passed, 1 skipped, 1 warning in 474.81s (0:07:54)
```

| 格 | 基线（`912f3b4`） | 终测（分支 tip） |
|---|---|---|
| collected | **1426** | **1465**（+39 = 20 审计 + 19 备份恢复） |
| 带 `--cov` | 1425 passed + 1 skipped | **1464 passed + 1 skipped** |
| 不带 `--cov` | **1426 passed** / 137.63 s | （未复跑；①②上分别实测 1426 / 1446 passed） |
| `app/domain/` 覆盖率四格 | 1268 / 0 / 376 / 0 / **100%** | **1268 / 0 / 376 / 0 / 100%** ← **逐字未退** |

⚠️ `app/domain/` **一个文件都没改**（本 Task 全在 `db` / `api` / `scripts` / `tests`），
故那四格**必然**不变；把它列出来是当作「没有偷偷动领域层」的取证。

### 7.2 禁区与真库（派单 §2 第 6 条）

| 格 | 实测 |
|---|---|
| `backend/pe.db` 存在吗 | **False** ✅ |
| `backend/data/seed/` 文件数 | **0** ✅ |
| `backend/backups/` | **不存在** ✅（没有任何备份产物入库） |
| `git diff 912f3b4 HEAD -- backend/data` | **空**（rc=0，**0 个文件**）✅ ← `backend/data/**` 一字节未动 |
| `git ls-files backend/backups` | **空** ✅ |

**四个数据指纹现算命中**（与 spec 钉住的那四个逐字相同）：

```
D2C8E539E2FA0029 → backend/data/national_standard_2014.csv
5394B37F01DAC9AC → backend/data/exercises.yaml
822CB86A5E998301 → backend/data/exercise_equivalence.yaml
E48E3AC82BB45BB7 → backend/data/alert_rules.yaml
```

处方模板 YAML **18** 个；`test_template_yaml_fingerprints_are_pinned` → **1 passed**；
那四个指纹所在的 3 个 refdata 测试文件 → **32 passed**。

### 7.3 依赖清单守卫

```
$ python -m pytest tests/test_dependencies.py -q
6 passed          ← 一字不红（清单**一字未动**，新增依赖 = 0）
```

### 7.4 前端：`smoke.mjs` 与 `npm run build`

⚠️ 跑之前**先重灌演示库**（`backend\scripts\demo.ps1 -Port 8000`）——
上一波 smoke 会把演示库写脏，而 `smoke.mjs` 的第 1 步与若干计数拍要求纯净库。

```
$ node scripts/smoke.mjs
…  步数 18/18 全绿 · 断言 499 绿 / 0 红
退出码 = 0
第 12 步（openapi 反查）= 102/102
$ npm run build
退出码 = 0
dist/assets/index-CM7Fwkho.css    65.20 kB
dist/assets/index-eWDO9FkM.js    167.03 kB      ← **两个哈希与基线逐字相同**
```

⚠️ **产物哈希未变**是这一节最有用的一格：本 Task **一个前端源文件都没改**
（只改了 `frontend/scripts/smoke.mjs`，那是**测试脚本**、不进 bundle），
故哈希必须逐字相同；若它变了，说明有东西被意外带进了构建。

⚠️ `smoke.mjs` 的两处传导：

| 步 | 格 | 改前 → 改后 | 落在哪个 commit |
|---|---|---|---|
| 1 | `/api/health` 的 `tables`（**两处**） | 27 → **28** | ① `5af9384` |
| 12 | 路径模板 / 操作 / 挂 security / GET | 71→**72** / 99→**100** / 81→**82** / 60→**61** | ④（⚠️ 见 §6.3 第 2 条） |
| 12 | **匿名 GET** / `securitySchemes` | **15** / **3**（**两格都不变**） | — |

### 7.5 openapi 五格（后端那一侧的同一条对账）

`tests/api/test_prescription_api.py` 那条**全仓级**断言，按硬规矩 #88 **先跑全量收进来**：

| 格 | 改前 | 改后 |
|---|---|---|
| `/api/` 路径模板 | 71 | **72** |
| 操作 | 99 | **100** |
| 挂 `security` | 81 | **82** |
| GET | 60（15 匿名 + 45 挂） | **61**（**15** 匿名 + **46** 挂） |
| `components.securitySchemes` | 3 | **3**（不变） |

⚠️ 新端点声明的是既有的 **`X-Teacher-Staff-No`**（实测
`/api/audit-logs security = [{'X-Teacher-Staff-No': []}]`），**没有**引入第四个 scheme；
⚠️ 且「值恰好是 `pe_session` 的操作**恰好两个**」那一拍**也不变**
（与本仓既有口径「cookie 那一格只由 `/api/auth/me` 与 `POST /api/auth/logout` 声明」一致）。
`expected` 清单 23 → **24** 项；`crud` 那一圈仍是 **76**（100 − 24），
故 `>= 70` 的空转下界**刻意不抬**。

### 7.6 架构守卫的扫描面

| 格 | 改前 | 改后 |
|---|---|---|
| `SCANNED_DIRS` 扫描面 | 67 | **71**（`db` 12→**13**、`api` 23→**26**） |
| 反向那一圈（`SCANNED_DIRS` − `api`） | 44 | **45**（只有 `db` 涨 1） |
| 两个下界 | `>= 21` / `>= 20` | **刻意不抬**（21 ≤ 71、20 ≤ 45 都成立） |

⚠️ **`API_ALLOWED_PREFIXES` 一个字都没动**：`api → api`（层内）本来就许可，
故 `deps.py` 与 `routers/auth.py` 那句 `from app.api.audit import …` **不需要**第十三项；
`db/models/audit.py` 只 import `app.db.session` 与它的两个兄弟子模块（`._shared` / `.auth`），
也不越界。⚠️ 那四个新模块里**唯一一条跨模块的新边**是
`api/schemas/audit.py → api/audit`（它要 `AUDITED_METHODS` 当 `method` 过滤参数的取值域），
**同层**，故同样落在 `app.api` 那一项里。

### 7.7 spec 与文档

```
Document/2026-09-28-体育闭环原型-设计spec.md
  改前 228987 B / 1906 行
  改后 253238 B / 2207 行（splitlines）/ CRLF 2207 / 裸 LF 0 / **无 BOM**
       sha256[:16] = 1768d63f769a1f9d
```

新增/改动**四处**：

| 处 | 内容 |
|---|---|
| **§13.9 请求审计留痕（新）** | 六个小节：记什么不记什么（含四档表）／隐私纪律是**结构性质**／「谁做的」从哪来／⚠️ `at` 是 naive 本地（**含对派单的顶回**）／`target` 从路径取／端点仅管理员／两档部署都工作。已知局限里**逐字挂着** §6.1 第 1 条 |
| **§13.10 备份与恢复（新）** | 三个小节：`.backup()` **不是**复制文件／恢复四步的顺序是承重的／库路径与 app **同源** |
| **§13.5 五格** | 71→**72** / 99→**100** / 81→**82** / 60→**61**（15 匿名 + 46 挂）/ `securitySchemes` **3**；表数 27→**28**；并**逐字写明**「Task 5 加的那一格是 `GET /api/audit-logs`」 |
| **§13.4 连带口径表** | 那一行加了「⚠️ **Plan 06 Task 5 起是 72**，+ `GET /api/audit-logs`，见 §13.5/§13.9」；⚠️ 而**历史陈述一个字没改**（硬规矩 #66 的另一半：绑时点的陈述在它绑定的时点上是真的） |

⚠️ 编辑口径同 §1：python `read_bytes` → LF 匹配 → 折回 CRLF → `write_bytes`，
改完复量 `crlf=2207 / bareLF=0 / bom=False`。

⚠️⚠️ **上面那个 253238 B 是「工作树」口径，入库 blob 是 251031 B**（= 253238 − 2207 个 CR）。
本机 `core.autocrlf` 实测是 **`true`**，而 `.gitattributes` **只**给四类东西钉了行尾
（`backend/data/**` 与 `.superpowers/**` 用 `-text`/`eol=lf`、`*.woff2` 与品牌 svg 用
`-text`/`binary`）——`Document/**` **不在**其中，故 spec 是「index LF / 工作树 CRLF」。
⚠️ 后果：**换一台 `autocrlf=false` 的机器检出，spec 就是 251031 B**，本节印的那个数当场变假。
实现者**没有**擅自给 `Document/**` 加 `.gitattributes` 规则（那会重写几十个文件、
制造一个巨大的无意义 diff —— 正是 `.gitattributes` 自己的注释里写着不做的理由），
改为**在这里注明口径**，并挂进 §6.1 待清扫。

### 7.8 四个 commit

```
5af9384  feat(db)!: Plan 06 Task 5 ① —— audit_log 一张表 + 第三条迁移 + 表数 27→28 的全量传导
         22 files / 611 insertions / 151 deletions      自洽性：实测 1426 passed（§6.3 第 1 条）
0aa137a  feat(api)!: Plan 06 Task 5 ② —— 审计中间件接线 + GET /api/audit-logs + 20 条守卫
         11 files / 1890 insertions / 12 deletions      自洽性：实测 1446 passed
                                                        ⚠️ 但 smoke.mjs 在这一 commit 上红 4 拍（§6.3 第 2 条）
3142abc  feat(scripts): Plan 06 Task 6 —— 在线备份 + 校验恢复（.py 承重、.ps1 是薄包装）
          6 files / 2131 insertions / 0 deletions       自洽性：纯新增，天然自洽（1465 collected）
④        docs(sdd): spec §13.9/§13.10 + smoke 第 12 步四格 + Task 5/6 实现者报告
          3 files（spec / smoke.mjs / 本报告）
         ⚠️ 它的 sha **不在本文件里**：本报告就在 ④ 内部，自嵌 sha 没有不动点。
         sha 与 `git cat-file -s` 的对账结果写在给控制者的回信里（§7.10 同此理由）
```

⚠️ **未 push、未碰 `main`**；分支 `p06/audit-backup` 的起点是 `main` 的 `912f3b4`。
⚠️ commit 消息一律用 python 写 **UTF-8 无 BOM** 的临时文件 + `git commit -F`
（四个消息文件在 `$env:TEMP\t56_probes\msg{1,2,3,4}.txt`），
`git add` **按文件名逐个加**（没有一次 `git add -A` / `git add .`）。

### 7.9 收尾清扫

| 项 | 状态 |
|---|---|
| `$env:TEMP\t56_probes\`（**35 个文件** = 29 个 `.py` + 2 个 `.ps1` + 4 个 commit 消息临时文件，逐字清单见 §1） | **整目录已删**（删完复验：`os.path.isdir` → **False**） |
| 8000 端口上的 demo uvicorn（后台 job） | **已停** |
| 演示库 `backend/pe_demo.db` | ⚠️ **被 smoke 写脏**（这是 `smoke.mjs` 的正常副作用）；控制者若要干净演示库，跑 `backend\scripts\demo.ps1 -Port 8000` 重灌即可（它第一步就删库） |
| `backend/pe.db` / `backend/data/seed/` / `backend/backups/` | **False / 0 / 不存在**（§7.2） |
| 工作树 | 干净（④ 之后 `git status --short` 为空） |

### 7.10 本报告自身的度量

⚠️ 派单要求「python 写；复核字节数与入库 blob 一致」。落地方式与实测：

```
本报告  65614 字节 / 998 行（splitlines）/ CRLF **0** / 裸 LF **998** / **无 BOM**
`git cat-file -s <入库 blob>` = 65614      ← 与磁盘上**逐字相同** ✅
```

⚠️ **字节数与行数是自嵌的、且收敛**：把占位符换成数字之后，这两格的**文本宽度**就固定了
（5 位 / 3 位），故「按模板渲染 → 重量 → 再渲染」会稳定；探针 `p24_report_finalize.py`
逐趟打印 `(B, L)` 直到不动点，实测**第 3 趟**逐字重复了第 2 趟的实测值
（⚠️ 第 1→2 趟那个差是**宽度**从 1 位涨到 5 位造成的，不是震荡）。
⚠️ **而 digest 刻意不自嵌**：哈希没有可求的不动点（把 digest 写进内容就改变了 digest），
故本报告只钉**字节数**这一格与 `git cat-file -s` 对账；blob 的 sha1 与本报告文件的
sha256[:16] 写在**给控制者的回信**里（那两处不在文件内，故不构成自嵌）。
⚠️ **而这一格对本报告恰好成立**：`.gitattributes` 里有 `.superpowers/**  -text`
（双向零转换），故本报告的**工作树字节 == 入库 blob 字节**，与 `core.autocrlf` 无关
（⚠️ spec 就**没有**这个待遇，见 §7.7 与 §6.1 第 4 条）。
⚠️ `.superpowers/sdd/**` 的既有两份报告实测都是 **LF + 无 BOM**
（`task-1-2-report.md` 52607 B / crlf 0；`task-3-4-report.md` 62599 B / crlf 0），
故本报告同口径；写入走 python（`read_bytes` → 归一 → `write_bytes`），写完**复量**一遍。

---

## 8. 交回控制者（派单 §6 的 8 项）

1. **commit sha 与自洽性**：`5af9384` / `0aa137a` / `3142abc` / ④。
   ①**实测 1426 passed**、②**实测 1446 passed**、③**纯新增天然自洽**。
   ⚠️ **一处不自洽如实报**：`smoke.mjs` 第 12 步的四格落在 ④，故 **`0aa137a` 上跑 smoke 会红 4 拍**
   （后端全量在那一 commit 上是全绿的）。理由与「为什么不 rebase」见 §6.3 第 2 条。
2. **审计实测矩阵 + 隐私取证**：§2.2（九档，含「登录+一次写 = 恰好 2 行」「匿名读 = 0 行」
   「鉴权失败 = 1 行 anonymous」）／§2.3（**六**档状态码，比派单要求多测了 dev 请求头两档）／
   §3.1（**14 行 × 9 列 → `offenders = []`**，列名取自字面量、含反空转那一拍）。
3. **迁移**：`7f3923d8af84`（`down_revision = 0b7da3d20211`）／autogenerate diff **恰好两行**／
   `alembic check` **干净**、`heads` **单头**、链长 **3**／`alembic.ini` **纯 ASCII**（4250 B）／
   表数 **28**（health 口径）与 **29**（磁盘口径，含 `alembic_version`）／
   全量传导 **22 个文件**（§4.5）。
4. **三档状态码 + openapi 五格**：管理员 **200** / 教师 **403** / 学生 **403** / 匿名 **401**
   （+ dev 请求头两档 **401**）／**72 / 100 / 82 / 61（15 匿名 + 46 挂）/ 3**（§7.5）。
5. **备份恢复取证 + `.ps1` 的 BOM/CRLF + gitignore**：§5.2–§5.3（端到端回到备份点、
   两种篡改各自拒绝、写锁给「请先停服务」、自检 `tables=29 / revision=7f3923d8af84`）／
   §5.4（**事故原地复现**：无 BOM → `Unexpected token 'Stop"`；入库两个 `.ps1` 都是
   **BOM + CRLF** 且被守卫钉住；PowerShell 5.1 端到端 `rc=0`，篡改侧车 `rc=2`、禁区 `rc=2`）／
   §5.5（`.gitignore` **只加一行** `backend/backups/`，且**一个备份都没入库**）。
6. **机械格**：**1426 → 1465 collected**（1464 passed + 1 skipped）／覆盖率四格
   **1268/0/376/0/100%（逐字未退）**／扫描面 **67 → 71**、反向圈 **44 → 45**、
   `API_ALLOWED_PREFIXES` **未动**／四个数据指纹**现算命中** + 模板 YAML **18** 个 +
   指纹守卫 **1 passed** + refdata **32 passed**／`git diff … -- backend/data` **空**／
   `pe.db` **不存在**／`data/seed` **0 文件**／`smoke.mjs` **18/18 · 499 断言 · rc=0**／
   `npm run build` **rc=0** 且**产物哈希逐字未变**／依赖守卫 **6 passed**（**新增依赖 0**）／
   spec **253238 B / 2207 行 / CRLF / 无 BOM / sha256[:16] = `1768d63f769a1f9d`**。
7. **顶回与没按派单做的**：**顶回 1 处**（`at` 由 UTC 改 naive 本地时刻，三条理由 + 代价，§6.2 ①）；
   **核过维持 2 处**（恢复前自动备份**不是**多余、§6.2 ②；`target` 从路径取，§6.2 ③）；
   派单点的第四处「GET 一律不记」**核过不顶回**、但代价挂账（§6.2 ④ + §6.1 第 1 条）。
   **没按派单做的 3 处**：commit ①/② 的切分线、smoke 四格落在 ④、
   `AUDIT_TABLES` 新分区 + `models/audit.py` 新子模块（§6.3）。
8. **待清扫 + 本报告度量**：**待清扫 5 条**（读审计不记／`audit_log` 无清理归档／
   管理台无审计页／索引对「只按时间」那一问用不上，§6.1）+ **关切 5 条**（§6.4，
   其中第 1 条「审计写失败会丢行」是**取舍**、要改需要结构性改动）；
   探针 **29 个文件整目录已删**；本报告 **65614 字节**，与入库 blob `git cat-file -s` **逐字相同**（§7.10）。

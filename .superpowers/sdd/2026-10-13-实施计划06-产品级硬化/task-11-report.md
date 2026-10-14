# Plan 06 Task 11 · 交付前收口波（第一批：3 件正确性修 + 5 件产品面清扫）—— 实现者报告

分支 `p06/correctness-and-product-sweep`（从 `main` 的 **`27eab30`** 起）。
**7 个 commit**（A1 / A1 漏网面 / A2 / A3 / B1+B2+B3 / B4+B5 / spec+报告），
**不 push、不碰 main**。工作树在最后一个 commit 之后干净。

> ⚠️ 本报告与 spec 的口径：**凡是能从别处读出来的数，一律现算并写明是怎么算的**
> （硬规矩 #111）；**凡是「我看代码里没写」一律不算取证**（#109）；
> 每一件都跑了**定点变异**（#50）。

---

## ① 环境

| 格 | 实测 |
|---|---|
| 开工第一件事（硬规矩 #73） | `node --version` → **v24.19.0**；`python --version` → **Python 3.11.1**（无 venv） |
| npm / FastAPI / SQLAlchemy / alembic | **11.17.0** / **0.141.1** / **2.1.3** / **1.20.0**（`pip show` 与 `npm --version` 现算，见 §⑨ 末尾） |
| 仓库根 | `c:\Users\whwenhao\Desktop\Physical_Education_ims` |
| 起点 | HEAD = **`27eab30`**，工作树干净、与 origin 同步 |
| 探针目录 | `$env:TEMP\p06t11\`（TEMP 里那约 114 个旧 `pe_*` 探针**本波一个都没删**，按派单 §3） |
| ⚠️ 5173 上那个 vite | **PID 20240**，**不是本波起的** → 按纪律**没杀它**；dev 档 smoke 改用 **5174** + `PE_WEB_BASE` |
| 本波起过又停掉的进程 | `demo.ps1 -Port 8000`（3 次）、`serve.ps1 -Port 8020`（2 次）、`npm run dev -- --port 5174`（1 次）——**全部已停**，§⑨ 有复验 |
| 编辑姿势 | 一律走 `$env:TEMP\p06t11\ed.py`（二进制读 → `\n` 归一 → 替换 → 还原 CRLF → 二进制写），**每改完一个文件当场核** `git ls-files --eol` |

---

## ② A1 · `login_attempt.login` 列宽 32 → **64**，配迁移链的**第 4 条**

### ②-1 改前实测（临时库 + 模型反射，两个口径都对过）

```
login_attempt.id      Integer()          length=None
login_attempt.kind    String(length=16)  length=16
login_attempt.login   String(length=32)  length=32   ← 本件要改的那一格
login_attempt.ok      Boolean()          length=None
login_attempt.at      DateTime()         length=None
login_attempt.ip      String(length=64)  length=64
user_session.id       String(length=64)  length=64
student.student_no    String(length=32)  length=32
teacher.staff_no      String(length=32)  length=32

_KEY_PREFIX_BY_PURPOSE = {'login': '', 'bind': 'bind:'}
最长前缀 = 5（'bind:'）；名册列宽上界 = 32  ⇒ 最长键长 = 37
经 policy._key() 实取的最长绑定键长度 = 37
login 列声明宽度 = 32   ⇒ 声明宽度 ≥ 最长键长? **False**   ← bug
```

临时库 `upgrade head`（改前，3 条迁移）之后的 `PRAGMA table_info(login_attempt)`：

```
(0,'id','INTEGER',1,None,1) (1,'kind','VARCHAR(16)',1,None,0) (2,'login','VARCHAR(32)',1,None,0)
(3,'ok','BOOLEAN',1,None,0) (4,'at','DATETIME',1,None,0)     (5,'ip','VARCHAR(64)',0,None,0)
alembic_version = ['7f3923d8af84']   heads = ['7f3923d8af84']   revisions = 3
```

### ②-2 为什么是 **64**（三条理由，逐字也写进了那一列的注释）

① 37 的下一个**整齐上界**（2 的幂）；② 与同表 `ip` 列、以及 `user_session.id`
**逐字同宽** —— 本仓的「宽字符串」只有 32 / 64 两档，不引第三个数；
③ 给「将来再加一个用途前缀」留余量（再加一个 `unbind:`，7 个字符，也只有 39）。

⚠️ **不改短前缀**（派单 §5 ① 问的那一格）：把 `"bind:"` 换成 `"b"` 会让库里已有的
绑定键**换键** —— 与 §13.4.11 顶回「不给登录档加前缀」同一条理由（换键会让正在被锁的
账号**当场解开**、并留下一批没人再读的孤儿行）。加宽列**不动任何一行的值**。

### ②-3 迁移 `0ac943e0da9b`（`Revises: 7f3923d8af84`），**batch_alter_table**，可 downgrade

`autogenerate` 的 diff **恰好一行**（在临时库上生成，⚠️ 不碰 `backend/data/**`、
不碰演示库、不碰禁区 `pe.db`，口径逐字照 spec §13.7 第 ② 步）：

```
INFO [alembic.autogenerate.compare.types] Detected type change
     from VARCHAR(length=32) to String(length=64) on 'login_attempt.login'
```

```python
def upgrade() -> None:
    with op.batch_alter_table('login_attempt', schema=None) as batch_op:
        batch_op.alter_column('login', existing_type=sa.VARCHAR(length=32),
                              type_=sa.String(length=64), existing_nullable=False)

def downgrade() -> None:
    with op.batch_alter_table('login_attempt', schema=None) as batch_op:
        batch_op.alter_column('login', existing_type=sa.String(length=64),
                              type_=sa.VARCHAR(length=32), existing_nullable=False)
```

⚠️ **为什么必须 `batch_alter_table`**：SQLite **没有** `ALTER COLUMN`，批处理
（建新表 → **拷数据** → 改名 → 删旧表）是这条链上唯一能落地的改法
（`migrations/env.py` 的 `render_as_batch = True`）。⚠️ 而它是**本链第一条改既有列**的
迁移（前三条各**加一张表**，它们的 `downgrade` 是 `drop_table`），故「拷数据」那一格是
一个**新的失效面**：一个写坏的批处理在 `upgrade` 时不报错，症状是甲方现场升级完
限流记录少了一半。
⚠️ **人审只做了两件事**：把生成器给的非 ASCII 文件名
（`…_login_加宽到_string_64.py`）改成 ASCII 的 `…_login_widen_to_64.py`
（另外三条全是 ASCII，而一个非 ASCII 文件名在 `git ls-files` 里会被转义成八进制），
以及写出那段 docstring —— **DDL 一个字都没改**。
⚠️ 而它**能被 autogenerate 看见**全靠 `compare_type = True`；那个开关的 docstring
举的例子逐字就是「把 `String(32)` 改成 `String(64)`」。关掉它的话本条迁移会生成成
**空文件**、而 §13.7 那条一致性守卫也会跟着**假绿**。

### ②-4 upgrade / downgrade 实测（临时库，一整圈）

| 步 | `alembic_version` | `PRAGMA` 的 `login` | 行 |
|---|---|---|---|
| `upgrade head` | `0ac943e0da9b` | **`VARCHAR(64)`** | — |
| 灌两行（一个 **37 字符**绑定键 `bind:` + 32 个 `X`、一个裸工号 `T0001`） | | | `('student','bind:XXX…',0,37)` / `('teacher','T0001',1,5)` |
| `downgrade -1` | `7f3923d8af84` | **`VARCHAR(32)`** | **两行逐字都在**（37 仍是 37） |
| 再 `upgrade head` | `0ac943e0da9b` | **`VARCHAR(64)`** | **两行仍逐字相同** |

⚠️ 宽度一律用**裸 `PRAGMA table_info`** 读、不用 `sqlalchemy.inspect`：批处理会
**换掉整张表**，而 `Inspector` 带一个 `info_cache` —— 缓存住的话「downgrade 真的把
宽度改回去了」这一格会**假绿**。
⚠️ **`downgrade` 在 SQLite 上可用且不丢行**（它不强制长度）；换 PostgreSQL 的话
`VARCHAR(32)` 装不下 37 个字符、downgrade 会**当场失败**，换 MySQL 会**静默截断**。
故「回滚 = 安全」在本条上**不成立**，一次真实的回滚要先确认库里没有 >32 字符的键
（已写进迁移 4 的 docstring）。

链形状：`heads = ['0ac943e0da9b']`、`base = 53e5a548c40e`、**4** 个修订、**4** 个脚本、
**单头**。

### ②-5 「声明宽度 ≥ 最长键长」那条守卫怎么做到**不硬编码 37**

`tests/auth/test_policy.py::test_the_login_column_is_at_least_as_wide_as_the_longest_key_the_policy_writes`：

* **最长键长是量出来的**：真的走一遍 `record_failure`，对 `sorted(policy.PURPOSES)`
  的**每一个**用途灌一个「名册列宽那么长」的原文（`"X" * max(Student.student_no.length,
  Teacher.staff_no.length)`，⚠️ 两个宽度都**从模型读**），再把写进去的行读回来量长度；
* 期望侧（`LoginAttempt.login` 的 `type.length`）与被测侧（量出来的键长）因此
  **两个来源**：一个来自 `models/auth.py`，一个来自 `policy._key` 的真实行为 + 名册列宽；
* 四拍：① 往返逐字（写进去的键 == `policy._key(purpose, 最长原文)`）；② **声明 ≥ 实写**
  （本条的牙）；③ 字面钉 **64**（口径与 `test_models.py` 那十几处 `.type.length == 32`
  逐字相同）；④ 反空转（最长键**严格长于**名册原文 ⇒ 至少有一个用途带前缀）。
* ⚠️ ② 与 ③ **各挡一件事**：只有 ② 的话，把列改窄到 40 仍然绿（40 ≥ 37），
  而下一次加一个 8 字符的前缀才红；只有 ③ 的话，加宽名册列到 64 而列宽不动**也**绿。

**定点变异四拍**（逐个亲跑）：

| 变异 | 结果 | 报错原文（节选） |
|---|---|---|
| ① 列宽 64 → **32**（= 回到改前） | **红** | `login_attempt.login 声明 32，而本模块实际会写进去的最长键是 37 个字符（= 最长前缀 + 名册列宽 32）… assert 32 >= 37` |
| ② 前缀 `bind:` → `binding:`（8 字符，最长键 40 ≤ 64） | **绿** | 正确行为（40 装得下） |
| ③ 列宽 **40** + 前缀 `binding:`（40 == 40，② 那拍过） | **红** | 红在 ③ 的字面量上：`assert 40 == 64` |
| ④ 前缀 → **60** 字符（最长键 60 + 32 = **92**） | **红** | `声明 64，而…最长键是 **92** 个字符… assert 64 >= 92` ← ⚠️ **它报的是 92 而不是 37，这就是「不硬编码」的可执行证明** |

### ②-6 `init_db` 重灌后**演示库**实测

`backend\scripts\demo.ps1 -Port 8000` 走的是 `init_db` → `alembic upgrade head`，日志里
四条迁移逐条跑上（含 `Running upgrade 7f3923d8af84 -> 0ac943e0da9b, 迁移 4：…`）。
重灌之后只读打开 `pe_demo.db` 实测：

```
PRAGMA table_info(login_attempt) →
  [(0,'id','INTEGER',1,None,1), (1,'kind','VARCHAR(16)',1,None,0),
   (2,'login','VARCHAR(64)',1,None,0),        ← **64**
   (3,'ok','BOOLEAN',1,None,0), (4,'at','DATETIME',1,None,0), (5,'ip','VARCHAR(64)',0,None,0)]
alembic_version = [('0ac943e0da9b',)]
GET /api/health  = {"status":"ok","tables":28,"students":60}
```

### ②-7 同步的守卫（**四处**，`Grep` 出来的全部）

| 文件 | 改了什么 |
|---|---|
| `tests/db/test_migration_baseline.py` | `HEAD_REVISION` `7f3923d8af84` → **`0ac943e0da9b`**；`len(list(script.walk_revisions())) == 3` → **`== 4`**；docstring 补「Task 11 是同一件事的第三次」+「第四条**不加表**，故表数与五个规模字面量一格都没动」 |
| `tests/db/test_migration_chain.py` | **新增** `test_the_column_width_migration_round_trips_and_keeps_every_row`（②-4 那一整圈，含 37 字符键）；模块 docstring 新增一节交代「本文件还钉住改既有列的那一条迁移」 |
| `tests/auth/test_policy.py` | **新增** ②-5 那条；`from app.db.models.organisation import Student, Teacher` |
| `tests/test_backup_restore.py` | ⚠️ **首跑漏掉的三处**：`result["selfcheck"]["revision"]`、`restore.selfcheck(db)["revision"]`、`restore.main` 的 stdout 里那三处头修订号字面量。它们**红了**（`3 failed / 1531 passed`），故单独一个 commit `b7be09f` 补齐，并各加一句注释点明「每加一条迁移，这两处一起红、一起改」 |

⚠️ **如实记（硬规矩 #39）：commit `44cae44` 那一个 sha 自身不是全绿的**
（`3 failed / 1531 passed`），`b7be09f` 把它补齐。⚠️ 而那三处红是**设计如此** ——
它们与 `HEAD_REVISION` 刻意是**两个所有者**（一个答「备份/恢复往返之后磁盘上写着
哪个号」、一个答「一条全新的库 `upgrade head` 之后停在哪个号」），
「每加一条迁移一起红」正是那条纪律在起作用。⚠️ 而 `tables` 那两格
（**29** 磁盘 / **28** health）一个字都没动 —— 第四条迁移不加表。

### ②-8 ⚠️ 顺手实测到的**同族**第二格（派单要求「一并报进报告，但只修这一列」）

`audit_log.path` 是 **`String(256)`**，而它存的是**请求路径的原文**
（`app/api/audit.py` 的 `record(path=…)`，来源是 ASGI 的 `scope["path"]`，**客户端可控**）。
一个超过 256 字符的路径在 PostgreSQL 上会**报错**、在 MySQL 上会**静默截断**
—— 与 A1 同一族。⚠️ 差别有两格：① 它今天**没有**「声明宽度 ≥ 实际写入」的守卫；
② 它的实际写入长度不由本仓的 schema 决定，而由**调用方**决定（uvicorn/h11 的请求行
上界远大于 256）。**本波只修 `login_attempt.login`**，这一格登记为待清扫（§⑧）。
`audit_log.target` 是 `String(64)`，存的是路径里那个 pk 的 `str(value)`（泛型 CRUD 的
成员路径 pk 是 `int`，实际最长约 19 字符），今天看不出同类问题，一并登记复核。

---

## ③ A2 · 全仓唯一一处 invalid escape sequence

### ③-1 扫描姿势（派单给了两个选项，我选后者并说明为什么）

派单举的 `python -W error::SyntaxWarning -c "import compileall; …"` **在本机抓不到它**：
Python **3.11** 上 invalid escape 是 **`DeprecationWarning`**，`SyntaxWarning` 是
**3.12 起**才有的类别。亲跑取证：

| 命令（`__pycache__` 已清） | 退出码 | stderr |
|---|---|---|
| `python -c "import app.main"` | 0 | **空** ← Python 的缺省过滤器把「不是在 `__main__` 里触发的 `DeprecationWarning`」一律吞掉 |
| `python -W error::SyntaxWarning -c "import app.main"` | **0** | **空** ← ⚠️ 3.11 上那一格不是 SyntaxWarning |
| `python -W error::DeprecationWarning -c "import app.main"` | **1** | `File "…\app\main.py", line 1 … SyntaxError: invalid escape sequence '\s'` |

故选的姿势是：**对全仓每个 `.py` 跑一次 `compile(source, path, "exec")`，
外面套 `warnings.catch_warnings(record=True)` + `simplefilter("always")`，
按警告的「文本里含 `invalid escape sequence`」判、不按类别判**。三格理由：
① `compile` 不吃 `__pycache__`（一个热的 `.pyc` 根本不再编译，警告也就不发）；
② 不触发 import 副作用（`app.main` 有一条模块级的 `app = create_app()`）；
③ **按文本判**而不是按类别判 —— 按类别判的话，本条守卫会在**升级 Python 的那一天
静默失效**（3.11 的 `DeprecationWarning` → 3.12 的 `SyntaxWarning`），
而那正是它要防的失效方向。

### ③-2 改前几条警告、在哪些文件

**全仓扫描面 593 个 `.py`（当时的实测值），恰好 1 条警告、在 1 个文件里**：

```
backend\app\main.py:1: invalid escape sequence '\s'
```

⚠️ 报的是**第 1 行**（模块 docstring 的起始行号），真因在第 **41** 行那条 Windows 路径：

```
    powershell -ExecutionPolicy Bypass -File scripts\serve.ps1
```

`main.py` 里含反斜杠的行实测只有 3 行：**41**（那一处裸 `\s`）、**329/330**
（`"\\n  - "` 与 `"\\n  - ".join(…)`，两处都是**正确**的转义）。

### ③-3 修法与「语义无损」的可执行证明

选**给那个 docstring 加 `r` 前缀**（而不是把 `\s` 写成双反斜杠）。两条理由：
一个字符的改动；且对「将来再往那个 docstring 里写一条 Windows 路径」**免疫**。

⚠️ **语义无损是量出来的、不是看出来的**（分两步做，正是为了让第一步的取证干净）：

| 步 | `app.main.__doc__` sha256[:16] | 长度 | 反斜杠个数 | invalid escape | 源文件以 `r` 开头 |
|---|---|---|---|---|---|
| 改前 | `fc0b13c44457999c` | 3377 | 1 | **1** | False |
| **只加 `r` 前缀**（一个字都不加） | **`fc0b13c44457999c`** | **3377** | **1** | **0** | **True** |
| 再补那段说明散文（**有意**改 `__doc__`） | `df1e7d03a5fb13ac` | 4119 | 4 | **0** | True |

⚠️ 代价（如实记）：raw 之后那个 docstring 里**再也写不出一个真的换行转义**。
今天它一个都没有（反斜杠只出现 1 次，就是那个路径分隔符），故这一格是空的。

### ③-4 新守卫的覆盖面 + `pytest` warnings summary 改前改后

新文件 `backend/tests/architecture/test_source_hygiene.py`（**2 条**）：

* `test_no_python_file_in_the_repository_carries_an_invalid_escape_sequence`
  —— ⚠️ **全仓扫描**（`REPO_ROOT` 下全部 `.py`，改后实测 **595** 个：
  `.superpowers/sdd/**` 393 + `backend/app/**` 95 + `backend/tests/**` 60 +
  `.superpowers/_snapshots/**` 38 + `backend/migrations/**` 5 + `backend/scripts/**` 4），
  **不是只扫 `main.py`**。三拍：offenders 为空 / 扫描面 ≥ **150**（`backend/` 单独就有 164）/
  **已知反例** `backend/app/main.py` **在**扫描面里
  （⚠️ 少了第三拍，往 `EXCLUDED_DIRS` 加一项 `app` 就能让本条恒绿）。
* `test_main_module_docstring_is_raw_so_its_windows_path_stays_verbatim`
  —— 钉「**修法本身**没被撤回」：源文件以 `r` + 三个双引号开头、那条路径逐字还在、
  且 `__doc__` 里的反斜杠个数 == 源文件那段 docstring 里的反斜杠个数
  （= 没有一个转义被解释掉）。少了本条，下一个人把 `r` 删掉（例如为了写一个 `\n`）
  会让上一条红，而报错指向的是「全仓有 1 处 invalid escape」—— 离真因有一层。

⚠️ `.superpowers/sdd/**` 的探针脚本**刻意不排除**：它们是**真的会被跑**的 `.py`。
⚠️ 如实记一格机器相关性：那 38 个 `_snapshots` 下的文件在 `.gitignore` 第 18 行里，
故**本机 595、一份新克隆上 557**；下界取 150 正是为了让这一格**不影响红绿**。

`pytest` 的 `warnings summary` 一节改前改后（`tests/test_main.py -q`，⚠️ **先清掉 25 个
`__pycache__`**，否则热 `.pyc` 让警告压根不发）：

| | 改前 | 改后 |
|---|---|---|
| `tests/test_main.py -q` | `23 passed, **3 warnings**` | `23 passed, **1 warning**` |
| 多出来的那两条 | `app\main.py:1: DeprecationWarning: invalid escape sequence '\s'`（同一格被记两次：一次挂文件、一次挂那条测试） | — |
| 全量套件（`--cov=app/domain --cov-branch`） | — | `1541 passed, 1 skipped, **1 warning**`，而那 1 条是 `fastapi/testclient.py` 的 `StarletteDeprecationWarning`（与本件无关） |

**定点变异三拍**：① 去掉 `r` 前缀 → **两条都红**；② 往**另一个**文件
（`app/refdata.py`）末尾塞一行 `_P06T11_PROBE = "C:\some\windows\path"` → **红，且点名
`…\backend\app\refdata.py:223: invalid escape sequence '\s'`**（⚠️ 这就是「它是全仓扫描、
不是只扫 main.py」的可执行证明）；③ 把 `EXCLUDED_DIRS` 加一项 `"app"` → **红在第 ③ 拍**
（`backend/app/main.py 不在扫描面里`）。三拍复原后 `tests/architecture` **10 passed**。

---

## ④ A3 · `gen:api` 改成从**离线** `create_app()` 取 spec

### ④-1 改前怎么跑的（先实测）

`frontend/package.json`：

```json
"gen:api": "openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api/generated/schema.d.ts"
```

⚠️⚠️ 输入是一个 **URL**，于是「产物新不新」取决于 **8000 上此刻跑的是哪一份代码**。

### ④-2 改后怎么跑的

```json
"gen:api": "python ../backend/scripts/dump_openapi.py --out node_modules/.cache/pe-openapi.json && openapi-typescript node_modules/.cache/pe-openapi.json -o src/api/generated/schema.d.ts"
```

（⚠️ `&&` 在本仓的 npm scripts 里**既有先例**：`"build": "vue-tsc -b && vite build"`。
npm 在 Windows 上用 `cmd.exe` 跑 scripts，故 `&&` 合法 —— 与本仓「PowerShell 5.1 没有
`&&`」那条纪律不冲突，那一条说的是**我手敲的命令**。）

新文件 `backend/scripts/dump_openapi.py`：`create_app(db_url="sqlite://")` →
`app.openapi()` → `json.dumps` → 写文件。**不起服务、不占端口**。
⚠️ 先实测过 `openapi-typescript --help`：它的 `[input]` 只认**路径或 URL**、
没有 stdin 档，故中间产物走 `node_modules/.cache/`（gitignored，父目录不存在会 `mkdir -p`）。

### ④-3 ⚠️⚠️ `pe.db` 仍不存在的取证（派单点名的那一格）

`create_app()` 会不会触发 `init_db` 建库 —— **先实测**，答案是**不会**，两格挡住：

1. **显式**传 `db_url="sqlite://"`（内存库），故 `app.main._resolve_db_url` 既不读
   `PE_DB_URL`、也**不回落**到逐字指向禁区的 `app.config.DEFAULT_DB_URL`；
2. **从不进 lifespan** —— `init_db` 住在 `create_app` 返回的那个应用的 `_lifespan` 里，
   而脚本**只调** `app.openapi()`、从不 `async with`、也从不起 uvicorn
   （`create_engine` 本身是惰性的：不连接、不建文件）。

⚠️ 而这两格都**有断言**、不是「我看代码里没写」（#109）：
脚本自己在 dump 的**前后各查一次**禁区（前一次存在就 refuse to run，
后一次存在就非 0 退出并点名是本脚本建的）；新守卫还在**子进程**里跑一遍
（那才是 `npm run gen:api` 真正跑的形状），四拍：
① `backend/pe.db` 不存在；② `PE_DB_URL` 指的那个磁盘库**也**不存在
（= 证明它**不尊重** `PE_DB_URL`：OpenAPI 文档与「连的是哪个库」无关）；
③ stdout 上**只有**那份 JSON（人类可读的话一律走 stderr，故 `>` 重定向也是对的）；
④ dump 出来的路径数 ≥ 70。

亲跑的 `pe.db` 复核（每一次都记了）：改模型前后、跑 `dump_openapi.py` 前后、
跑 `npm run gen:api` 前后、`import app.main` 前后 —— **一律 `False`**。

### ④-4 产物**逐字相同**的取证

```
$ git diff --exit-code -- frontend/src/api/generated/schema.d.ts
（无输出）  退出码 = 0        ← 产物逐字未变
```

⚠️ 如实记一格**既有**行为（不是本波引入的）：`openapi-typescript` 写出的产物是 **LF**，
而工作树里那一份是 checkout 出来的 **CRLF**，故裸字节哈希会变
（527 633 B `44714FAF62E65E18` → 517 231 B `F32F4E2CE0DEF6D2`）而 `git diff` 为空
（`git ls-files --eol` 改前 `i/lf w/crlf`、跑完 `i/lf w/lf`）。
**每一次跑完都把它还原成 CRLF**（本报告写作时它是 `i/lf w/crlf`、527 633 B、
sha `44714FAF62E65E18`，与开工时逐字相同）。⚠️ 这一格改前改后**都有**，
已登记为待清扫（§⑧）。

### ④-5 耗时改前改后

| | 改前 | 改后 |
|---|---|---|
| `npm run gen:api` | **1.64 s**、退出码 0 | **2.33–2.94 s**、退出码 0 |
| 其中 | 一次 HTTP GET + `openapi-typescript` | `dump_openapi.py` **1.71 s** + `openapi-typescript` **0.17 s**（它自己打印 `[170ms]`）+ npm 开销 |
| **前置条件** | ⚠️ **8000 上必须有一个跑着当前代码的 uvicorn** | **无** |

⚠️ 改后**慢 0.7–1.3 s**（Python 要 import FastAPI + 装配一次应用），换来的是
**去掉一个硬前置条件**。⚠️ 而「不依赖在跑的服务」是**亲跑取证**的、不是推断的：
先 `Stop-Process` 掉 `demo.ps1` 的 uvicorn、确认 `GET /api/health` **超时**
（`Invoke-WebRequest : The operation has timed out`），再跑 `npm run gen:api`
→ **退出码 0**、产物 sha 与刚才逐字相同。

⚠️ 顺带取证：离线 dump 的那份字节与 `GET /openapi.json` 的**响应体字节**完全相等 ——
两侧都是 **417 032** 字节、sha256[:16] 都是 `4c8123a9a8903753`、`逐字节相同? True`
（`render_spec` 逐字用了 `starlette.responses.JSONResponse.render` 的四个参数）。

### ④-6 一致性守卫**加强后的形状** —— ⚠️ **顶回派单 A3 的第 ④ 点**

派单写的是「**加强它**：让它也从离线 `create_app()` 取（这样它比的两侧都不依赖在跑的服务，
『两边都旧』这一档结构性消失）」。

⚠️ **实测：它本来就是离线的。** `tests/api/conftest.py` 的 `app` 夹具逐字是
`return create_app(db_url="sqlite://")`（第 44 行），`client` 夹具是
`with TestClient(app) as test_client`（第 67 行）；而那条守卫读 spec 的姿势是
`spec = client.get("/openapi.json").json()` —— **进程内**、一个端口都不占。
故它比的两侧（磁盘上的 `schema.d.ts` ↔ 进程内的 spec）**都不依赖在跑的服务**，
「两边都旧」在结构上**不可能**发生。⚠️ Task 10 那一次事故是 `gen:api` **自己**读了
旧进程（于是产物陈旧），而守卫**恰恰会红**（它拿新代码的 spec 去比一份陈产物）——
派单对那一格的归因是反的。

故那一条上**没有可加强的东西**；改成加了三条**新的**（都在
`tests/api/test_prescription_api.py`，与既有的产物一致性守卫住在一起）：

| 新守卫 | 钉的是 |
|---|---|
| `test_the_offline_dump_is_byte_identical_to_the_http_endpoint` | 离线取法与 HTTP 取法**按字节**相同。⚠️ 刻意不按「解析之后的字典相等」判：字典相等放得过「缩进变了 / 中文被转义成 `\uXXXX` 了」那两档，而它们会让产物的**换行方式**变，于是一次 `git diff` 上出现上万行与真因无关的改动 |
| `test_running_the_dump_script_as_a_subprocess_never_creates_the_forbidden_database` | ④-3 那四拍 |
| `test_the_gen_api_script_reads_the_offline_dump_and_not_a_running_service` | `package.json` 的 `gen:api` 命令串里**必须**含 `dump_openapi.py`，且 `http://` / `https://` / `127.0.0.1` / `localhost` **四个都不许出现**。⚠️ 少了本条，把 `gen:api` 改回读 URL 不会让任何测试红 —— 那正是 Task 10 踩过的那一格 |

**定点变异两拍**：① 把 `gen:api` 改回
`openapi-typescript http://127.0.0.1:8000/openapi.json …` → **第 ③ 条红**
（`assert 'dump_openapi.py' in '…'`，报错里点名那一整串）；
② 把 `render_spec` 的 `indent=None` 改成 `indent=2` → **第 ① 条红**（字节对账失败）。
两拍复原后 `tests/api/test_prescription_api.py` **35 passed**（含既有的产物一致性守卫，
它自己单跑 **0.34 s**）。

---

## ⑤ B1 + B2 · 缺失产物 404 + 两类缓存头

判据的**唯一所有者**仍然是 `app/static.py`，而它自本波起有**三格**（改前两格）：
`is_reserved()`（API 面）→ `_candidate_under()`（解析 + 越界复核）→
**`is_asset_request()`（B1 新加的第三格）**；缓存头另有一个住址 **`cache_control_for()`**（B2）。

### ⑤-1 先实测 `dist` 的真实布局（派单要求「不要凭空假设」）

```
frontend/dist：index.html（根上唯一一个文件）+ assets/（28 个文件）
扩展名分组：.html 1 / .css 8 / .js 14 / .woff2 4 / .svg 2
```

⚠️ **根级没有任何静态文件**：`frontend/index.html` 里既没有 `<link rel="icon">`、
也没有字体外链（品牌 svg `xmu-emblem-vodJYAz_.svg` / `xmu-wordmark-Dwm-zgk-.svg`
与 4 个自托管 woff2 **都被打包器收进了 `assets/`**）。
故派单点名的「`/*.svg`、`/*.woff2` 这类**根级**静态文件」今天在 `dist` 里**一格都没有**
—— 那一格挡的是**打错的 URL**（`/favicon.ico`、`/robots.txt`、`/site.webmanifest`），
而不是真实产物。

### ⑤-2 判据两格（`is_asset_request`）

① 以 `ASSETS_PREFIX`（= `"/" + ASSETS_URL_DIR + "/"` = `/assets/`，⚠️ 带那个结尾的斜杠）
开头；② **单段**路径（`lstrip("/")` 之后不含 `/`）且扩展名在 `_MEDIA_TYPES` 里。
⚠️ 第 ② 格**刻意不放宽到多段**：那会把一个字面的 `/%2e%2e/secret.txt` 从 200 改成 404
（两档都不泄漏任何字节），但那是本件**范围之外**的一次行为变更。
⚠️ 于是裸 `/assets`（那个**目录**）不算，照旧 fallback（给一个目录列表等于把产物结构
告诉任何匿名调用方）。

### ⑤-3 Task 7 那张 **13 格 fallback 矩阵**逐格复跑（产品档、真 `dist`、`http.client` 拿原始状态码）

| # | 路径 | 状态 | content-type | 字节 | cache-control |
|---|---|---|---|---|---|
| 1 | `/` | **200** | `text/html; charset=utf-8` | 2729 | `no-cache` |
| 2 | `/login` | **200** | 同上 | 2729 | `no-cache` |
| 3 | `/bind` | **200** | 同上 | 2729 | `no-cache` |
| 4 | `/s/home` | **200** | 同上 | 2729 | `no-cache` |
| 5 | `/s/weekly-sheet` | **200** | 同上 | 2729 | `no-cache` |
| 6 | `/t/dashboard` | **200** | 同上 | 2729 | `no-cache` |
| 7 | `/t/students/1` | **200** | 同上 | 2729 | `no-cache` |
| 8 | `/admin` | **200** | 同上 | 2729 | `no-cache` |
| 9 | `/admin/` | **200** | 同上 | 2729 | `no-cache` |
| 10 | `/admin/students/1` | **200** | 同上 | 2729 | `no-cache` |
| 11 | `/this-route-does-not-exist` | **200** | 同上 | 2729 | `no-cache` |
| 12 | `/apixyz` | **200** | 同上 | 2729 | `no-cache` |
| 13 | `/documentary` | **200** | 同上 | 2729 | `no-cache` |

**13/13 一格都没变**（13 行的响应体互相**逐字节相同**，脚本里按「同上」印的就是这一格）。
⚠️ 而 `cache-control: no-cache` 是**新增**的（改前一个头都没有）—— 那不是「改了 fallback
的判据」，是 B2 的第二类头。

### ⑤-4 新的 404 格（B1）

| 路径 | 改前 | 改后实测 |
|---|---|---|
| `/assets/does-not-exist.js` | **200** `text/html` 2729 B | **404** `application/json`，体 = `{"error":{"code":"not_found","message":"Not Found","detail":null}}`（66 B，⚠️ 与 `/api/nope` **同款**） |
| `/assets/index-DEADBEEF.css` | 200 | **404** 同款 |
| `/assets/xmu-emblem-not-hashed.svg` | 200 | **404** 同款 |
| `/robots.txt` | 200 | **404** 同款 |
| `/favicon.ico` | 200 | **404** 同款 |
| `/site.webmanifest` | 200 | **404** 同款 |

⚠️ `HEAD` 同答（`_SpaRoute` 收 GET 与 HEAD 两个方法）：`HEAD /assets/does-not-exist.js`
→ **404**、体 **0 B**。⚠️ 6 格**都不带任何 `cache-control`**（一个 `not_found` 不该被
中间缓存存下来：甲方运维补上一次构建之后，那一个 404 必须**当场**消失）。

真产物 6 个（原字节 + 对的 content-type + 新的缓存头）：

| 路径 | 状态 | 字节 | content-type | cache-control |
|---|---|---|---|---|
| `/assets/index-DaycGB6S.js` | 200 | 167 954 | `text/javascript; charset=utf-8` | `public, max-age=31536000, immutable` |
| `/assets/index-CPgg7MK0.css` | 200 | 65 204 | `text/css; charset=utf-8` | 同上 |
| `/assets/xmu-emblem-vodJYAz_.svg` | 200 | 52 095 | `image/svg+xml` | 同上 |
| `/assets/hanken-grotesk-var-latin-CaVRRdDk.woff2` | 200 | 34 704 | `font/woff2` | 同上 |
| `/assets/StudentDetail-oGny8jrh.js` | 200 | 39 022 | `text/javascript; charset=utf-8` | 同上 |
| `/assets/AuditLogList-CBAg61k7.js` | 200 | 9 446 | `text/javascript; charset=utf-8` | 同上 |

（⚠️ 这张表是 B1+B2 落地**当时**那份 `dist` 上的哈希；B4 之后重建过，
新哈希见 §⑨。）

### ⑤-5 两类缓存头的原文 + `/api` 的**反向**断言

* `/assets/*` → **`Cache-Control: public, max-age=31536000, immutable`**
* `index.html`（**含 13 格 fallback**）→ **`Cache-Control: no-cache`**
  （`/index.html` 直接请求也是 `no-cache`，且带 `etag="f52f7448e9e1c0937bf93ae…"`
  与 `last-modified`，故 `no-cache` 的那一次回源校验是一个 **304**）
* ⚠️ 判据是「**发的那个文件**是不是 `index.html`」、**不是**「URL 是不是 `/index.html`」：
  按 URL 判的话 `/t/dashboard` 那一格一个头都拿不到，浏览器会按**启发式**缓存它
  （`Last-Modified` 距今的 10%），于是「升级后一部分用户白屏几天」照样发生、只是换了个 URL
* ⚠️ `no-cache` **不是** `no-store`（派单 §5 ③ 问的那一格，逐字理由见 spec §13.11.6）

**`/api` 那四个面 + 三格方法语义，实测一个 `cache-control` 都没有**：

| | 状态 | cache-control | content-type |
|---|---|---|---|
| `GET /api/health` | 200 | **`<无>`** | `application/json` |
| `GET /openapi.json` | 200 | **`<无>`** | `application/json` |
| `GET /docs` | 200 | **`<无>`** | `text/html; charset=utf-8` |
| `GET /redoc` | 200 | **`<无>`** | `text/html; charset=utf-8` |
| `GET /docs/oauth2-redirect` | 200 | **`<无>`** | `text/html; charset=utf-8` |
| `GET /api/nope` | 404 | **`<无>`** | `application/json` |
| `GET /api/students?limit=1` | 401 | **`<无>`** | `application/json` |
| `POST /api/nope` | **404** ✓ | `<无>` | |
| `POST /login` | **404** ✓ | `<无>` | |
| `POST /api/health` | **405** ✓ | `<无>` | |
| `DELETE /api/semesters` | **405** ✓ | `<无>` | |

⚠️ 最后四行是 spec §13.11.2 那一条（「产品档不改 `/api` 的任何一格可观察行为」）
的既有取证，**逐格复跑、一格都没变**。⚠️ 而 pytest 侧那条守卫
（`test_no_cache_control_is_added_to_the_api_the_contract_or_the_two_doc_pages`）
比的是**更强**的一格：「给了 `static_dist` 与不给，两份响应头**逐字相同**」——
单侧断言（「产品档上没有 cache-control」）证明不了「产品档没有**加**什么」。
⚠️ `date` 头刻意排掉（它一秒一跳，比它等于给守卫装一个偶发的红）。

目录穿越四格（B1 之后**一律 404**）：`/%2e%2e/secret.txt`、
`/assets/%2e%2e/%2e%2e/backend/pe_demo.db`、`/assets/%2E%2E/secret.txt`、
`/../secret.txt` → 4 格全 **404** + `application/json`，**没有一行发出秘密文件的字节**。
⚠️ 如实记：Task 7 那张 HTTP 穿越矩阵的**后四行从 200 变成了 404**
（`/assets/%2E%2E/secret.txt`、`/assets/%2e%2e/secret.txt`、以及两个字面 `../secret.txt`
—— httpx 会把点段折成 `/secret.txt`，一个根级的 `.txt`）。⚠️ 那张表的**判据一格都没变**
（它要的从来只是「不泄漏字节」，而 200 `index.html` 与 404 统一形状**都**满足它），
故那是一次「更诚实」的改动、不是一次安全性改动。已同步
`test_a_traversal_over_http_never_reaches_a_file_outside_dist` 的期望表与 docstring，
并**另加一拍反空转**（六格都变 404 之后，「整个应用都 404 了」也会绿 ——
故补断 `/login` 仍是 `index.html`、`/assets/app.js` 仍是原字节）。

### ⑤-6 守卫与定点变异

`tests/test_serve.py`：**30 → 34 条**（B1+B2 加 4 条），并把
`test_resolve_static_path_answers_exactly_the_three_documented_cases` **改名**为
`…four_documented_cases`（判据从三档变四档，硬规矩 #66；⚠️ 前三档的期望值一个字都没改）。

| 变异 | 结果 |
|---|---|
| ① 把 `resolve_static_path` 里新加的那一段整块去掉（回到「一律 fallback」） | **4 条红**（含 `assert 200 == 404`） |
| ② 把 `NO_CACHE` 改成长缓存（= 甲方升级后用户白屏那一档） | **红**：`assert 'public, max-age=31536000, immutable' == 'no-cache'` |
| ③ 把 `cache_control_for` 改成**按 URL** 判（`url_path == "/" + INDEX_HTML`） | **红**：`KeyError: 'cache-control'`（13 格 fallback 拿不到头） |
| ④ 挂一个全局中间件给 `/api` 也加一条缓存头 | **2 条红**（反向断言：`+ 'cache-control': 'public, max-age=60'`） |

四拍复原后 `tests/test_serve.py` **34 passed**（B3 那一条落地之后是 **35 passed**）。

---

## ⑥ B3 · `serve.ps1` 也**强制**清掉 `PE_ALLOW_HEADER_IDENTITY`

### ⑥-1 `demo.ps1` 的姿势（照抄，⚠️ 不写第二套）

`backend/scripts/demo.ps1` 第 154–162 行那 **9 行**（含它上面那一行注释）就是那一段：
`$HeaderIdentityInherited = …GetEnvironmentVariable(…)` →
`Remove-Item Env:\PE_ALLOW_HEADER_IDENTITY -ErrorAction SilentlyContinue` →
`$HeaderIdentityNow = …` → `if (-not [string]::IsNullOrEmpty($HeaderIdentityNow)) { throw … }`
→ 两个 `…Shown` 变量（打印**实测值**，不打印一句写死的话）。

⚠️ **落地方式就是「现场从 `demo.ps1` 里切出那一段、逐字贴进 `serve.ps1`」**
（脚本 `b3_serve.py` 先 `index()` 切片、再拼接，故**不存在第二份手抄本**）。
两条守卫都是**现场从 `demo.ps1` 切出来**再断言 `serve.ps1` 里有它
（期望侧是 `demo.ps1` 的**文件内容**，两侧不同源 ⇒「两份漂了」当场红）。

### ⑥-2 改前改后

改前（`serve.ps1` ③b 段末）：

```powershell
$HeaderIdentity = [Environment]::GetEnvironmentVariable('PE_ALLOW_HEADER_IDENTITY')
if (-not [string]::IsNullOrEmpty($HeaderIdentity)) {
    Write-Host "   ⚠️⚠️ PE_ALLOW_HEADER_IDENTITY 本进程实测 = $HeaderIdentity：dev 档下它会**打开**请求头身份通道"
    …
    Write-Host "      生产档（PE_ENV=prod）下 app.api.deps 一律忽略它；本脚本**不**替你清掉它"
    Write-Host "      （与 demo.ps1 不同：那一个是演示、必须强制关；本脚本是部署入口，开关归运维）。"
}
```

⚠️⚠️ **那句话前半句对、后半句危险**：产品档**缺省留在 `dev` 档**（§13.11.3：同源 http 上跑
prod 档，浏览器会拒收 `Secure` cookie，症状是「登录 200、下一个请求 401」），
而 `allow_header_identity()` **只在 `PE_ENV=prod` 下恒回 `False`**。于是
「dev 档 + 运维不小心设了那个变量」= **请求头身份通道开着** = **绕过整个鉴权**
（`X-Student-Id` / `X-Teacher-Staff-No` 没有签名、没有过期、没有吊销，
任何人都可以自称任何学号，**含管理员那个工号 `T0003`**）。
而它的失效方向是静默的：服务照常起、健康检查照常 200、脚本只在一个几十行的启动输出里
印一行 ⚠️。

改后：③b2 段 = 一大段说明注释（含「不给开关」的裁定与顶回）+ **`demo.ps1` 那 9 行逐字副本** +

```
   PE_ALLOW_HEADER_IDENTITY 进本脚本时实测 <实测值> → 本进程已**强制**清成 未设（= 生产缺省 "0"：只认 pe_session cookie；⚠️ 请求头身份通道**已关闭**）
```

⚠️ **不给产品档一个显式开关**（派单 §5 ④ 问的那一格，与控制者倾向一致，**不顶回**）：
产品档就是产品档。要一个认请求头的**开发档**，请在另一个终端里
`$env:PE_ALLOW_HEADER_IDENTITY = "1"` 再手工起 uvicorn（`demo.ps1` 的注释里逐字写着那一格）。

### ⑥-3 ⚠️ 真发请求取证（设了环境变量再跑 `serve.ps1`）

起服务前本 shell 里 `$env:PE_ALLOW_HEADER_IDENTITY = "1"`（实测 `=1`），
`scripts\serve.ps1 -Port 8020 -SkipBuild` 打印：

```
   PE_ALLOW_HEADER_IDENTITY 进本脚本时实测 =1 → 本进程已**强制**清成 未设（= 生产缺省 "0"：只认 pe_session cookie；⚠️ 请求头身份通道**已关闭**）
   档位            = dev（cookie 的 Secure = False）
   进程 PID = 37448
   http://127.0.0.1:8020/api/health → 200（轮询 1 次）
```

在那一个**起着的服务**上真发请求（`http.client`，原始状态码）：

| 请求 | 状态 | 体 |
|---|---|---|
| `GET /api/students/4/home` + `X-Student-Id: 4` | **401** | `{"error":{"code":"unauthenticated","message":"缺少身份：需要一…` |
| `GET /api/teacher/students/4/home` + `X-Teacher-Staff-No: T0001` | **401** | 同款 |
| `GET /api/audit-logs` + `X-Teacher-Staff-No: T0003`（**管理员那个工号**） | **401** | 同款 |
| **对照**：`POST /api/auth/login`（`2023120001` + 演示口令） | **200** | `Set-Cookie: pe_session=OzqqKjY7-j_b5JXPmSArbxJQYJWmi…` |
| **对照**：`GET /api/students/4/home` 带那个 cookie | **200** | 1769 B |

⚠️ 后两行是**反空转**：它们证明「不是整个应用都 401 了」，而是**只有请求头那一档**被关掉。

### ⑥-4 BOM / CRLF 复核

| 文件 | 字节 | BOM | CRLF | 裸 LF | `git ls-files --eol` |
|---|---|---|---|---|---|
| `scripts/serve.ps1`（改后） | **25 376** | **在**（`ef bb bf`） | **387** | **0** | `i/lf w/crlf attr/text eol=crlf` |
| `backend/scripts/demo.ps1`（变异 ③ 复原后） | **20 167** | **在** | **273** | **0** | `i/lf w/crlf attr/text eol=crlf` |

⚠️ `.gitattributes` **一条都没碰**（`git diff 27eab30 HEAD -- .gitattributes` 空）。

### ⑥-5 守卫与定点变异

新守卫 `tests/test_serve.py::test_serve_ps1_force_clears_the_header_identity_channel_with_the_same_lines_demo_ps1_uses`
（**四拍**）：① 从 `demo.ps1` **现场切出**那一段、断言 `serve.ps1` 里**逐字**有它；
② 改前那个只打印用的裸 `$HeaderIdentity` 变量与「开关归运维」那句**不在语句里**
（⚠️ 判据只扫语句行、把 `#` 注释滤掉：新加的那一大段注释**逐字引用**了改前那句原文
来说明为什么改判，而**提及不是本身**，#109 —— 首跑就是红在自己的说明文字上）；
③ 那一次 `Remove-Item` 排在 `Start-Process` 与 `-- ④ 健康检查 --` **之前**
（子进程继承的是本进程**当时**的环境块，清晚了等于没清）；④ 打印的是两个**实测**变量、
且说的是「已关闭」。

`smoke.mjs` 第 17 步 ⑤ 是**行为面**那一拍（与 ① 那条 `demo.ps1` 的守卫同一条姿势）：
先占住一个端口（`net.Server.listen(0)` 拿实际分到的那一个）再交给 `-Port`，
于是脚本停在 ③d 的端口预检 —— 那一步排在强制清 ③b2 **之后**、起子进程 ③e **之前**，
故它打印了那一行、却**一个 uvicorn 都不起**。实测输出：

```
    先占住 127.0.0.1:53070，再把它交给 -Port（于是脚本会停在 ③d 的端口预检、一个 uvicorn 都不起）
    PE_ALLOW_HEADER_IDENTITY 进本脚本时实测 =1 → 本进程已**强制**清成 未设（= 生产缺省 "0"：… ⚠️ 请求头身份通道**已关闭**）
```

⚠️ **首跑踩过一条路，如实记**：原先想用一个认不出的 `PE_ENV` 让它停在 ③c（档位自检），
而 ③a 那一次 `python -c 'from app.main import DEMO_DB_URL'` **更早就炸了**
（`import app.main` → 模块级 `create_app()` → `deploy.tier()` 抛 `ValueError`），
于是脚本停在强制清**之前**、那一行压根没打印 —— **探针红在自己身上**
（dev 档 smoke 首跑 3 条红全在这一拍）。改成占端口之后绿。

**定点变异三拍**：① 删掉那一次 `Remove-Item` → **红**；② 把它挪到 `$Proc.WaitForExit()`
之后 → **红**（⚠️ 如实记：它红在第 ① 拍「逐字同款」上而不是第 ③ 拍「顺序」上，
因为删/挪那一行先破坏了那一段的逐字副本 —— 两拍指向同一件事）；
③ **只给 `demo.ps1` 那一段改一个字**（「请手工清掉它再重跑。」→「…之后再重跑一次。」）
→ **红**（⚠️ 这就是「逐字同款」是**双向**的可执行证明）。三拍复原后绿。

---

## ⑦ B4 + B5

### ⑦-1 B4 · 那「4 处」实测是 **7 个组件 / 24 个调用点**

⚠️ **先如实记一格：Task 8 登记的「前端 4 处 `limit: 200`」数少了。** 那 4 个是**组件**
（`TeacherNav.vue` + 既有的 `AlertQueue.vue` / `Dashboard.vue` / `ClassReport.vue`），
而今天 `limit: 200` 出现在 **7 个组件 / 24 个调用点**：

| 组件 | 发数 | 读的资源 | 演示库上 `total`（**管理员档 = 全表**，最坏的那一档） |
|---|---|---|---|
| `components/TeacherNav.vue` | 4 | teachers / course-sections / enrollments / students | 3 / 5 / 120 / 60 |
| `views/teacher/AlertQueue.vue` | 5 | alerts / students / course-sections / teachers / enrollments | 32 / 60 / 5 / 3 / 120 |
| `views/teacher/ClassReport.vue` | 4 | teachers / course-sections / weekly-class-reports / students | 3 / 5 / 5 / 60 |
| `views/teacher/Dashboard.vue` | 6 | teachers / course-sections / enrollments / alerts / students / class-sessions | 3 / 5 / 120 / 32 / 60 / 8 |
| `views/teacher/StudentDetail.vue` | 3 | mini-tests / stratification-results / alerts | 180 / 120 / 32 |
| `views/student/MiniTest.vue` | 1 | mini-tests | 180 |
| `views/student/RpeEntry.vue` | 1 | class-sessions | 8 |
| **合计** | **24** | 9 个不同的资源 | **9 个都 < 200** ⇒ 今天一格都不触发 |

（⚠️ `class-sessions` 在 smoke 跑过之后是 10 —— smoke 第 2/4 步各建一节课；
`training_log` 已经 **840** 行，而它走的是既有的 `collectPages` **翻页收集**、不在这一族里。）

**24 处一律走同一个助手** —— 留三处不走的话，那三处的静默截断还在。

### ⑦-2 助手的形状（`frontend/src/api/endpoints.ts`，与既有的 `collectPages` 同住一处）

* `SINGLE_PAGE_LIMIT = 200` —— 那 24 处的**唯一住址**（改前这个字面量在 7 个组件里
  各写了一遍，最多的写了 6 遍）；
* `listOnePage(fetchPage, what, limit = SINGLE_PAGE_LIMIT)` → `OnePage<T> extends Page<T>`，
  多出来两格：`missing`（`Math.max(0, total - items.length)`）与 `note`
  （一句带**两个数**的人话）。⚠️ 它 `extends Page<T>`，故调用点的 `.items` / `.total`
  **一行都不用改** —— 24 处改动的**下游代码是 0 行**；
* `truncationNoteOf(pages)` → 合成一句，一个都没截断时回 **`null`**
  （⚠️ 不是 `''`：`''` 会让 `v-if` 为真、渲染出一个**空的** `<p>` = 今天多了一个 DOM 节点）；
* 7 个组件各自把 `note` 绑进模板：`<p v-if="data?.truncation" class="t-block__note">`
  （学生端两页用 `s-block__note`；`TeacherNav` 用它自己的 `truncation` ref，
  渲染成 `<nav>` 之外的**第二个根节点**，因为 `.tnav` 是一个 4 列 grid、塞进去会占掉一格跑道）。
  ⚠️ 两个类都是**既有**的（`styles/teacher.css:101` 与 `styles/student.css:76`），
  故**一条新 CSS 都没加** ⇒ `npm run check:tokens` 的扫描面仍是 **36**、下界仍是 25、全绿。

### ⑦-3 ⚠️ 为什么是「返回一个 note」而不是「抛错」（派单 §5 ⑤ 问的那一格，**顶回**「抛错」）

三条理由，第一条是**实测**的：

1. 那 7 个组件的 `catch` 一律写的是 `err instanceof ApiError ? err : null`
   （`Dashboard.vue:167`、`ClassReport.vue:223`、`StudentDetail.vue:229/242/340`、
   `Dashboard.vue:399/420` …），一个**非** `ApiError` 的异常会被**静默吞掉**
   （只进 `console.error`）。于是「抛错」在这一族页面上**恰恰是看不见的那一档**，
   而派单逐字要求「必须是用户看得见的，不能只是 `console.warn`」；
2. 抛错会让**整屏失败**（`Promise.all` 一发被截断，另外五发的数据也一起没了），
   而「数据没取全」的正确表现是「照实说 + 把取到的那一部分给用户看」；
3. 红色横幅也不对：截断是「数据没取全」、**不是**「出事了」，而 `ApiErrorBanner.vue`
   的文件头逐字写着「用红色横幅渲染『不是坏了』的那几档会教用户忽略红色横幅 ——
   而下一次真正的 `forbidden` 就会被一起忽略掉」。

故它渲染成一条 **note** —— 与本仓既有的 `collectPages` → `truncated` →
`.s-block__note` **完全同一条口径**（`CheckIn.vue:540`、`Notifications.vue:167`、
`RpeEntry.vue:202` 已经这么渲染了）。

### ⑦-4 「不改任何一处今天的显示结果」的取证

`note` 只在 `missing > 0` 时非 `null`，而演示库上那 **9 个资源在 `limit=200` 下
`total == items.length`**（smoke 第 17 步 ⑦③ 那 9 行逐个打印：
`teachers 3/3`、`students 60/60`、`course-sections 5/5`、`enrollments 120/120`、
`alerts 32/32`、`class-sessions 10/10`、`weekly-class-reports 5/5`、`mini-tests 180/180`、
`stratification-results 120/120`）⇒ `note` 恒为 `null`、`v-if` 恒假。
`smoke.mjs` 第 14 步那 **122** 条 DOM 断言（needle + 矩形重叠/溢出几何 + surface class）
**两档全绿**。

⚠️ **如实记一格（硬规矩 #39）**：Vue 3 对一个 `v-if` 为假的分支会留一个 `<!--v-if-->`
**注释**占位节点，故 `outerHTML` 会多出若干个注释节点（**不是元素**、不占布局、
`toPlainText` 剥完逐字相同）。⚠️ 而本波**没有**跑一次「改前 build vs 改后 build」的
逐字节 DOM diff —— 那要留一份改前的 `dist` 与改前的 7 个组件、重建两次；
上面那一串（`note` 恒 null + 第 14 步 122 条两档全绿 + `v-if` 为假只留注释节点）
是本波给出的替代取证。**这一格如实登记为「取证强度低于派单字面要求」**。

### ⑦-5 B4 的守卫（smoke 第 17 步 ⑦，四拍）+ 定点变异

| 拍 | 内容 | 实测 |
|---|---|---|
| ⑦① | `src/**` 的**代码**里（剥 JS/HTML/CSS 注释之后）**0 处**裸 `limit: 200`；反空转两拍：扫描面 ≥ 30（**实测 46** 个 `.vue/.ts`）、`SINGLE_PAGE_LIMIT = 200` 与 `limit: number = SINGLE_PAGE_LIMIT` 都还在、`Math.max(0, page.total - page.items.length)` 那个算式还在 | `[]` |
| ⑦② | 那 **7 个**组件**逐个**都①走 `listOnePage` + `truncationNoteOf`、②把那句话**绑进了模板**（`v-if="…truncation"` + 一个 `[ts]-block__note` 类）；反空转：清单**恰好 7 个** | `[]` |
| ⑦③ | 9 个资源在 `limit=200` 下 `total == items.length`（⇒ 今天一处都不截断） | 9/9 |
| ⑦④ | `GET /api/alerts?limit=1` → `items` 恰好 **1** 行、`total` = **32** ⇒ `missing = 31 > 0`、`note` 非 `null`（⚠️ 派单点名的正是「可以用一个 `limit=1` 的调用触发它，不必造 200 行数据」） | `{"items":1,"total":32}` |

**定点变异两拍**（把 ⑥⑦ 的源码面谓词单独跑一遍）：
① `AlertQueue.vue` 的一处改回裸 `listAlerts({ limit: 200 })` → **⑦① 红**
（点名 `src/views/teacher/AlertQueue.vue`）；
② 把 `AlertQueue.vue` 模板里那个 `<p v-if="data?.truncation">` **删掉** → **⑦② 红**
（`「助手 true / 渲染 false」`，⚠️ 即「走了助手而没画出来」正是本拍要抓的那一档）。

### ⑦-6 B5 · router 相撞面的**实测清单**

守卫在 `smoke.mjs` 第 17 步 ⑥。⚠️ 相撞面**不是手写清单**：对每一对 (i 静态, j 带参)，
建一个「**只有 j 一条路由**」的 `createMemoryHistory()` router，问它「i 那个路径命中你吗」
—— 于是「什么叫会被吃掉」只有一个所有者（**vue-router 自己的匹配实现**），
守卫不自作主张写一份正则。

实测 `routes` 数组 **20** 条 path 字面量（⚠️ 比第 14 步那 **16** 条**渲染**路由多 4 条：
`/s` 与 `/t` 两条重定向、`/` 那条 root、以及 `/:pathMatch(.*)*` 那条兜底）：

```
[ 0] 静态 /login            [ 5] 静态 /s/weekly-sheet   [10] 静态 /t             [15] 静态 /admin
[ 1] 静态 /bind             [ 6] 静态 /s/check-in       [11] 静态 /t/dashboard   [16] 静态 /admin/audit-logs
[ 2] 静态 /                 [ 7] 静态 /s/rpe            [12] 静态 /t/report      [17] 带参 /admin/:resource
[ 3] 静态 /s                [ 8] 静态 /s/mini-test      [13] 静态 /t/alerts      [18] 带参 /admin/:resource/:id
[ 4] 静态 /s/home           [ 9] 静态 /s/notifications  [14] 带参 /t/students/:studentId
                                                        [19] 带参 /:pathMatch(.*)*
```

**相撞面 17 对**（左 = 静态，右 = 会吃掉它的带参路由）：

* **1 对**是 Task 9 点名的那一对：**`[16] /admin/audit-logs ←会被← [17] /admin/:resource`**；
* 另外 **16 对**一律是「某条静态路径 ←会被← `[19] /:pathMatch(.*)*`」
  （`/login` `/bind` `/` `/s` `/s/home` `/s/weekly-sheet` `/s/check-in` `/s/rpe`
  `/s/mini-test` `/s/notifications` `/t` `/t/dashboard` `/t/report` `/t/alerts`
  `/admin` `/admin/audit-logs`）；
* ⚠️ `/admin/:resource/:id` 与 `/t/students/:studentId` **一对都没有**
  （20 条里没有任何一条**三段全静态**的路径）。

**倒序 0 处。**

⚠️ **两拍各挡一件事**（派单 §5 ⑥ 问的那一格：**两种都用**，并说明为什么单一一种不够）：
vue-router 4 按「静态段 > 动态段」**打分**，故整棵树建起来之后 `resolve()` 命中的
**永远**是静态那一条 —— 「解析结果对」证明不了「声明顺序对」，而后者才是读代码时能
回答「谁先匹配」的那一格（`src/router/index.ts:242-244` 的注释逐字写着这个理由）。
故 ① 断言每一对里静态那条的**下标 < 带参那条的下标**（**有牙的那一条**），
② 断言 `resolve()` 逐个静态路径命中的是它自己（钉的是「相撞面算得对」）。

⚠️ 计算期间就地静音 `console.warn`：一个「只有 j 一条路由」的 router 去 resolve 别的路径，
**不命中就是它要的答案**，而 vue-router 会为每一次不命中打一条
`[Vue Router warn]: No match found for location with path …`（**实测 96 条**）。

**定点变异一拍**：把 `/admin/audit-logs` 整个对象挪到 `/admin/:resource` 之后 →
① **红**（倒序 `[[17,16]]`，报 `'/admin/:resource 排在了 /admin/audit-logs 之前'`），
而 ② **仍然绿**（`resolve 命中错的 0 处`）—— ⚠️ 那正是「② 单独不够」的**可执行证明**。
复原后 `router/index.ts` 与原文**逐字节相同**。

---

## ⑧ 待清扫 / 关切 / 没按派单做的 / **顶回**

### ⑧-1 **顶回**（4 处；另 3 处派单点名问的，复核后**维持原裁定**）

| # | 派单原文 | 顶回 / 维持 | 理由（逐字取证在正文） |
|---|---|---|---|
| 1 | A3 ④「**加强**一致性守卫：让它也从离线 `create_app()` 取」 | ⚠️ **顶回** | 实测**它本来就是离线的**：`tests/api/conftest.py:44` 是 `create_app(db_url="sqlite://")`、`:67` 是 `TestClient(app)`，守卫读 spec 的姿势是 `client.get("/openapi.json")` —— 进程内、一个端口都不占。故「两边都旧」在结构上**不可能**；Task 10 那一次事故是 `gen:api` **自己**读了旧进程，而守卫**恰恰会红**。派单对那一格的归因是反的。**改成加了三条新的**（§④-6） |
| 2 | A2 ①「`python -W error::SyntaxWarning -c …` 或逐个 `ast.parse` + `catch_warnings`，你选并说明」 | ⚠️ **顶回派单举的第一种** | `python -W error::SyntaxWarning -c "import app.main"` 在 **Python 3.11 上退出码 0、stderr 空** —— 那一格在 3.11 是 `DeprecationWarning`。故守卫**按警告的文本判、不按类别判**（按类别判会在升级 Python 那天静默失效） |
| 3 | B4「抽一个共用的取值助手（⚠️ 单一所有者；**4 处**都走它）」 | ⚠️ **更正台账**（不是顶回裁定） | 实测是 **7 个组件 / 24 个调用点**（Task 8 数的是**组件**、且漏了 `StudentDetail` / `MiniTest` / `RpeEntry` 三个）。**24 处一律走同一个助手** —— 留三处不走的话，那三处的静默截断还在 |
| 4 | B4「形状你选（抛错 → 页面显示可读的错误块 / 或返回一个 `truncated` 标记）」 | ⚠️ **顶回「抛错」那一支** | 那 7 个组件的 `catch` 一律是 `err instanceof ApiError ? err : null`，一个非 `ApiError` 的异常会被**静默吞掉**（只进 `console.error`）⇒「抛错」在这一族页面上**恰恰是看不见的那一档**，而派单逐字要求「必须是用户看得见的」。三条理由见 §⑦-3 |
| 5 | A1 ①「64 是否该取别的宽度、或『不加宽而改短前缀』是否更好」 | **维持 64，不顶回** | 三条理由见 §②-2；⚠️ 而「改短前缀」更差：它会让库里已有的绑定键**换键**（正在被锁的账号当场解开 + 一批孤儿行），加宽列**不动任何一行的值** |
| 6 | B2 ③「`no-cache` vs `no-store` 与 `max-age` 取值」 | **维持 `no-cache` + 一年 `immutable`，不顶回** | `no-store` 会让每一次导航都重下 2 729 B 的入口文档，换来的「中间人一个字节都不许留」在本档没有意义（`index.html` 不含按身份而变的东西、也不含凭据）。逐字理由已写进 spec §13.11.6 |
| 7 | B3 ③「若你认为产品档应当给一个显式开关…**顶回来**」 | **不给开关，与控制者倾向一致** | 产品档就是产品档；要开发档请在另一个终端里 `$env:PE_ALLOW_HEADER_IDENTITY = "1"` 再手工起 uvicorn |

### ⑧-2 没按派单做的（**1 处**）

* **A3 ④「加强一致性守卫让它也从离线取」——无需做**（顶回 #1）。
  ⚠️ 除此之外派单 §1/§2 的每一格都做了；§3 那一组「本波不要做」的**一条都没碰**
  （两处坏 `:func:` 引用、spec §13.6 的旧 URL、`_enrolled_sections` 查两次、
  `feedback.py` 三个只被散文引用的 import、不可达的 `assert orphan is not None`、
  `$env:TEMP` 那约 114 个旧 `pe_*` 探针、smoke 第 14 步的 dev server 新鲜度、
  `demo.ps1` 的 addon warning 散文、smoke 对 `/s/mini-test` 的静态 needle、
  以及那 11 条延后台账）。
  ⚠️ 而派单 §3 末尾那句「若你在做 A/B 时发现其中某条与你的改动**冲突**，那就地处理并如实记」
  —— 本波**没有**碰到这类冲突（`feedback.py` 一行都没改）。

### ⑧-3 本波**新登记**的待清扫（6 条）

1. ⚠️ **`audit_log.path` 是 `String(256)`，而它存的是客户端可控的请求路径原文**
   （`scope["path"]`）—— 与 A1 同一族（声明可能窄于实际写入），而它今天**没有**
   「声明宽度 ≥ 实际写入」的守卫。本波按派单要求**只修 `login_attempt.login`**（§②-8）。
2. `audit_log.target` 是 `String(64)`，存路径里那个 pk 的 `str(value)`；泛型 CRUD 的
   成员路径 pk 是 `int`（最长约 19 字符），但特例端点的 `target` 取法要再核一遍。
3. **迁移 4 的 `downgrade` 在 PostgreSQL / MySQL 上不安全**（前者会当场失败、
   后者会静默截断）：一次真实的回滚要先确认库里没有 >32 字符的键。
4. `frontend/src/api/generated/schema.d.ts` 的**工作树行尾**是 CRLF，而
   `npm run gen:api` 写出的是 **LF**（`git diff` 为空、故不影响入库，但
   `git ls-files --eol` 会从 `w/crlf` 变成 `w/lf`）。⚠️ 这是**既有**行为、不是本波引入；
   本波每次跑完都还原成 CRLF。要根治得让 `gen:api` 之后接一次行尾归一。
5. `smoke.mjs` 第 17 步此前那句「**不需要后端**也不需要前端起着」自本波起
   **只对 ①–⑥ 成立**（⑦ 的 ③④ 两拍要打真端点）。已把那一格改进那一段的注释里。
6. `smoke.mjs` 第 17 步 ⑤ 那一拍会 spawn 一次 `powershell` + 两次 `python`
   （`serve.ps1` 的 ③a 与 ③c 各一次），实测约 3–5 s；① 那一拍本来就要 spawn 一次
   `demo.ps1 -DryRun`（约 15 s）。两步合起来是 smoke 30 s 里的一半。

### ⑧-4 关切（2 条）

* ⚠️ `login_attempt.login`（**64**）与 `student.student_no` / `teacher.staff_no`（**32**）
  的列宽**不再逐字相同** —— 两处散文（`models/auth.py` 的模块 docstring 与列注释）
  都已改。⚠️ 而「名册列宽」与「限流键列宽」现在是**两个数**：将来加宽名册列时
  那条守卫会**自动红**（它的最长键长是从名册列宽推出来的），那是**要的**。
* ⚠️ B1 顺带把目录穿越 HTTP 矩阵的**后四行从 200 改成了 404**（§⑤-5）。
  判据（「不泄漏字节」）一格都没变，但那是本件**范围之外**的一次可观察行为变更，
  已如实写进 `test_serve.py` 那条守卫的 docstring 与期望表。

---

## ⑨ 最终验收

### ⑨-1 后端

| 格 | 基线（`27eab30`） | 本波 |
|---|---|---|
| 全量（`--cov=app/domain --cov-branch`） | 1529 passed + 1 skipped | **1541 passed + 1 skipped**（270.47 s）← **净新增 12 条**（A1 2 + A2 2 + A3 3 + B1/B2 4 + B3 1） |
| 全量（不带 `--cov`） | 1530 passed | **1542 passed**（那 1 条 skip 在不带 `--cov` 时是 pass，与基线同一格；⚠️ 本波只亲跑了带 `--cov` 那一档，1542 是 `1541 + 1` 的折算，**如实记**） |
| `app/domain/` 覆盖率四格 | 1268 / 0 / 376 / 0 / **100%** | **1268 / 0 / 376 / 0 / 100%**（**一格未变**） |
| `warnings summary` | 1 starlette + 2 invalid escape（冷 `__pycache__` 时） | **只剩 1 条 starlette** |
| 表数（health 口径） | 28 | **28** |
| **迁移链** | 3 单头（`53e5a548c40e` → `0b7da3d20211` → `7f3923d8af84`） | **4 单头**（… → **`0ac943e0da9b`**） |
| 架构守卫扫描面 | 71 | **71**（`pipeline 10 + db 13 + domain 18 + api 26 + auth 4`） |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（未改；守卫绿） |
| `_MODELS_SUBMODULES` | 8 | **8**（`models/` 下 9 个 `.py` 减去 `_shared`） |
| 黄金用例 | 14 | **14**（`tests/integration/test_golden_cases.py` 收集 19 条，id 到 `[13-GC14]`） |
| 未定型响应（`test_prescription_api.py` 的 `expected`） | 26 | **26** |
| 依赖清单守卫 | 后端 7+3+1、前端 3+7 | **一字不红**（`dependencies` 3 / `devDependencies` 7 / 后端 `dependencies` 7 + `alembic==1.20.0` + `dev` 3；**新增依赖 0**） |

⚠️ **不带 `--cov` 那一档的 `1542` 是折算、不是亲跑**（派单 §4「运行时口径」要求跑起来量，
故如实标出）。⚠️ 而中间那次**不带** `--cov` 的全量跑（A1+A2 落地之后）实测
`3 failed / 1531 passed`，`1531 + 3 = 1534 = 1530 + 4`（A1 2 条 + A2 2 条），
与本波最终收集数**逐格对得上**；那 3 条红就是 §②-7 那三处漏网的头修订号字面量。

### ⑨-2 openapi 五格（**一格都没变**）

```
路径 74 / 操作 102 / 挂 security 84 / GET 63（匿名 15 + 挂 security 48）/ securitySchemes 3
非 /api 的路径模板 = []          ← catch-all 0 个漏进 paths
```

### ⑨-3 前端

| 格 | 基线 | 本波 |
|---|---|---|
| `npm run build` | 退出码 0 | **退出码 0**（4 s；`vue-tsc -b` + `vite build`，140 modules） |
| 产物哈希 | `index-CPgg7MK0.css` / `index-DaycGB6S.js` / `StudentDetail-oGny8jrh.js` / `AuditLogList-CBAg61k7.js` | **`index-CDpHJuAb.css`** / **`index-C6s8jbPM.js`** / **`StudentDetail-AI7GaiQq.js`** / **`AuditLogList-B0av5me7.js`**（⚠️ 四个都变了：B4 改了 7 个组件与 `endpoints.ts`；⚠️ `AuditLogList` 也变是因为 `endpoints.ts` 是它的依赖之一） |
| `check:tokens` | 绿（扫描面 36、下界 25） | **绿**（扫描面 **36**、下界 25 —— ⚠️ **一格未退**，因为一条新 CSS 都没加） |
| `check:dist` | 绿 | **绿**（25 个产物文件 / 778 426 字符；`adoptFromUrl` 0 次、两个字体 CDN 各 0 次） |
| 路由条数 | smoke 的 `ROUTES` **16** / `router/index.ts` 的 `routes` **20** | **16 / 20**（未改） |
| **smoke dev 档** | 18 步 / 591 断言 / 退出码 0 | **18/18 步 · 616 断言 · 退出码 0 · 30.1 s**（后端 8000 + vite **5174**） |
| **smoke 产品档** | 18 步 / 591 断言 / 退出码 0 | **18/18 步 · 616 断言 · 退出码 0 · 28.2 s**（`serve.ps1 -Port 8020 -SkipBuild`，同源） |
| 新增依赖 | 0 | **0** |

### ⑨-4 禁区与卫生

| 格 | 实测 |
|---|---|
| `backend/pe.db` 存在 | **False**（本波每一次跑完都复核过：改模型前后、`dump_openapi.py` 前后、`npm run gen:api` 前后、`import app.main` 前后、smoke 两档前后） |
| `backend/data/seed/` 文件数 | **0** |
| `git diff 27eab30 HEAD -- backend/data` | **空**（`--exit-code` 退出码 **0**）← `backend/data/**` **一字节未动** |
| 四个数据指纹（sha256[:16] 大写，CRLF→LF 归一） | **`D2C8E539E2FA0029`** → `national_standard_2014.csv`；**`5394B37F01DAC9AC`** → `exercises.yaml`；**`822CB86A5E998301`** → `exercise_equivalence.yaml`；**`E48E3AC82BB45BB7`** → `alert_rules.yaml` —— **四个逐字命中** |
| 18 个模板指纹 | `C0C61D2140A521D0` RED-END-ABN-01 / `FE91666F74C08CAF` RED-END-NOR-02 / `8F4D51E3377FA814` RED-STR-ABN-03 / `3E8C365CD0B4C133` RED-STR-NOR-04 / `8E396D8BF85B6DBD` RED-SPD-ABN-05 / `0EDDE329A6CA61AE` RED-SPD-NOR-06 / `D301AE8D8D3D6B7E` YEL-END-ABN-07 / `F08B64A00D974F18` YEL-END-NOR-08 / `033CFAA2D1F93503` YEL-STR-ABN-09 / `C1CDF7D18A1F87E4` YEL-STR-NOR-10 / `FA81CAD1B9050A9E` YEL-SPD-ABN-11 / `524CD251936C79B1` YEL-SPD-NOR-12 / `89842C7A0D8A6EA0` GRN-END-ABN-13 / `3B1DA3AAB8D6A322` GRN-END-NOR-14 / `91E660991C717944` GRN-STR-ABN-15 / `A5B406807FDEF7CC` GRN-STR-NOR-16 / `9ADB0CAC53A572F1` GRN-SPD-ABN-17 / `2389C1A03E6ABBCE` GRN-SPD-NOR-18 —— **18 个**（`backend/data/**` 共 24 个文件 = 18 模板 + 5 个数据/说明 + 1 个 README） |
| `git ls-files frontend/dist` | **0 个**（`frontend/.gitignore:18` 是 `dist/`） |
| `git ls-files backend/backups` | **0 个** |
| `.gitattributes` | **一条都没碰** |
| 本波起的进程 | **全部已停**：`Get-NetTCPConnection -State Listen` 在 5173/5174/8000/8010/8020 上只剩 **5173 PID 20240**（⚠️ **不是本波起的**，按纪律没杀） |
| `$env:TEMP\p06t11` | 报告写完 → commit → **删掉并复验**（见 §⑨-6） |

### ⑨-5 spec

| 格 | 基线 | 本波 |
|---|---|---|
| 工作树字节 | 366 608 B | **397 490 B** |
| 行数 | 3 356 | **3 717** |
| 行尾 | 全 CRLF / 无 BOM | **全 CRLF（3717 个）/ 无 BOM**（`mixed = False`） |
| sha256[:16]（**工作树**口径，与派单同口径） | `b132f04d6f7efac8` | **`3921e779c9edd54d`** |
| sha256[:16]（**LF 归一**口径） | `e6fda1c134866ade` | **`fa6a3680407aaf6d`** |
| 入库 blob 字节 | 363 252 B | 见 §⑨-6 |
| `git ls-files --eol` | `i/lf w/crlf attr/text eol=crlf` | **同**（`i/lf w/crlf attr/text eol=crlf`） |

改了 **7 处**：① §13.4.11 那条「列宽」残余 → 标 **已收**（原文照留当证据）；
② §13.4.11 那句「不动 schema、不动迁移（迁移链仍 3）」→ 如实标注**说过头了**；
③ §13.4.10 的 openapi 五格那一句 → 补「Task 11 起迁移链是 4，而 openapi 五格一格都没变」；
④ §13.11.4 末那条「已知局限（打错的 `/assets/*.js` 是 200）」→ 标 **已收**，
并如实记「**没有**走『给 `/assets` 进保留前缀清单』那一条路」；
⑤ §13.11.3 加一条 B3；⑥ §13.11.4 的「断言数此后长了 N 次」追加 **591 → 616**；
⑦ **新增三个小节**：§13.11.6（缺失产物 404 + 两类缓存头）、§13.11.7（`serve.ps1`
也强制关）、§13.12（Task 11 的三件正确性修 + 两件前端清扫，5 个子节）。

### ⑨-6 commit 链与行尾复核

```
37f915c feat(frontend): 单页取值不许静默截断（B4）+ router 静态段必须排在 :resource 之前（B5）（Task 11）
ffe328e feat(serve): 产品档三件清扫 —— 缺失产物 404 + 两类缓存头 + serve.ps1 强制关请求头身份（Task 11 / B1+B2+B3）
4f58dda feat(build): gen:api 改成从进程内的 create_app() 取 spec，不再依赖「在跑的服务」（Task 11 / A3）
b7be09f fix(tests): 同步 test_backup_restore.py 里三处钉「迁移链头修订号」的字面量（A1 的漏网面）
af8d4d0 fix(main): app/main.py 的模块 docstring 改成 raw，收掉全仓唯一一处 invalid escape（Task 11 / A2）
44cae44 fix(db): login_attempt.login 列宽 32 → 64，配迁移链第 4 条（Plan 06 Task 11 / A1）
<最后一个> docs: Plan 06 Task 11 —— spec 7 处（新增 §13.11.6 / §13.11.7 / §13.12）+ 实现者报告
```

**每个中间 commit 是否自洽**：

| commit | 自洽？ |
|---|---|
| `44cae44`（A1） | ⚠️ **不是**：`3 failed / 1531 passed` —— 漏了 `test_backup_restore.py` 里那三处头修订号字面量。**如实记**（派单允许「做不到就如实记」） |
| `b7be09f` | ✅ 补齐（`tests/test_backup_restore.py` 19 passed）；到这一个 sha 为止全绿 |
| `af8d4d0`（A2） | ✅ 自洽（新守卫 2 条绿；全仓 0 条 invalid escape） |
| `4f58dda`（A3） | ✅ 自洽（⚠️ 派单 §4 提示「若某个中间 commit 上守卫会红，如实记」—— **没有红**：产物逐字未变，故既有的产物一致性守卫在这个 sha 上照旧绿；而 `package.json` 的 `gen:api` 与 `dump_openapi.py` 与那三条新守卫在**同一个** commit 里） |
| `ffe328e`（B1+B2+B3） | ✅ 自洽（`tests/test_serve.py` 35 passed） |
| `37f915c`（B4+B5） | ✅ 自洽（`npm run build` 退出码 0；smoke 两档各 616 断言全绿 —— ⚠️ 那两跑是在**这一个 sha** 上做的） |

**本波改过的 24 个文件逐个 `git ls-files --eol`**（⚠️ 本机 `core.autocrlf=true`，
故**两个口径都报**：入库 blob 一律 `i/lf`，工作树 `w/crlf`）：

```
i/lf w/crlf attr/                backend/app/auth/policy.py
i/lf w/crlf attr/                backend/app/db/models/auth.py
i/lf w/crlf attr/                backend/app/main.py
i/lf w/crlf attr/                backend/app/static.py
i/lf w/crlf attr/                backend/migrations/versions/0ac943e0da9b_login_attempt_login_widen_to_64.py
i/lf w/crlf attr/                backend/scripts/dump_openapi.py
i/lf w/crlf attr/                backend/tests/api/test_prescription_api.py
i/lf w/crlf attr/                backend/tests/architecture/test_source_hygiene.py
i/lf w/crlf attr/                backend/tests/auth/test_policy.py
i/lf w/crlf attr/                backend/tests/db/test_migration_baseline.py
i/lf w/crlf attr/                backend/tests/db/test_migration_chain.py
i/lf w/crlf attr/                backend/tests/test_backup_restore.py
i/lf w/crlf attr/                backend/tests/test_serve.py
i/lf w/crlf attr/                frontend/package.json
i/lf w/crlf attr/                frontend/scripts/smoke.mjs
i/lf w/crlf attr/                frontend/src/api/endpoints.ts
i/lf w/crlf attr/                frontend/src/components/TeacherNav.vue
i/lf w/crlf attr/                frontend/src/views/student/MiniTest.vue
i/lf w/crlf attr/                frontend/src/views/student/RpeEntry.vue
i/lf w/crlf attr/                frontend/src/views/teacher/AlertQueue.vue
i/lf w/crlf attr/                frontend/src/views/teacher/ClassReport.vue
i/lf w/crlf attr/                frontend/src/views/teacher/Dashboard.vue
i/lf w/crlf attr/                frontend/src/views/teacher/StudentDetail.vue
i/lf w/crlf attr/text eol=crlf   scripts/serve.ps1          ← ⚠️ BOM 也在（25 376 B / 387 CRLF / 0 裸 LF）
```

⚠️ **0 个文件是 `w/lf`**、**0 个文件带意外的 BOM**、`.gitattributes` 一条都没碰。
⚠️ 两份**新**文件（`test_source_hygiene.py` / `dump_openapi.py`）由 Write 工具落盘时是 LF，
当场用 python 二进制模式归一成 CRLF（与同目录既有文件同款）之后才 commit。

### ⑨-7 版本口径（现算）

`node --version` → **v24.19.0**；`npm --version` → **11.17.0**；
`python --version` → **Python 3.11.1**；`fastapi` **0.141.1** / `sqlalchemy` **2.1.3** /
`alembic` **1.20.0** / `starlette` **1.7.0** / `pytest` **9.1.1** / `pytest-cov` **7.1.0**
（一律 `importlib.metadata.version(…)` 现算，不是抄派单）。

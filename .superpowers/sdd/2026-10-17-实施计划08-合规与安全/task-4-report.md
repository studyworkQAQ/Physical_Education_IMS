# 实施计划 08 · Task 4 实现者报告（**续做**）—— 绑定验身材料：一次性绑定令牌

> 分支 `p08/bind-token`。接手时 HEAD = **`1751bbe`**（控制者打的那个 WIP 检查点，
> 39 个文件 **+4 643 / −200**、**一个正式 commit 都没有**）。
> 本波在它上面打了 **5** 个正式 commit（sha 见 §9.13），`main` 仍是 **`8e7df10`**、
> ⚠️ **一次都没 push**、**一次都没碰 main**、**没有 revert / cherry-pick 那个 WIP**。
>
> ⚠️ 本报告**刻意不印自己的字节数与 sha256**（不动点问题；Plan 07 Task 8 在这一族
> 连踩四次，教训在它报告的 §8.6）。

---

## ① 环境 + 接手现场 + 开工/收尾五格

### 1.1 环境

| 格 | 值 |
|---|---|
| Node / Python | **v24.19.0** / **Python 3.11.1**（⚠️ 开工第一件事跑的，无 venv） |
| 仓库根 / 分支 / HEAD | `c:\Users\whwenhao\Desktop\Physical_Education_ims` / **`p08/bind-token`** / **`1751bbe`** |
| `main` | **`8e7df10`**（Task 3 结案）；⚠️ 全程未动、未 push |
| 接手时工作树 | `git status --porcelain` **空**（干净） |
| PowerShell | 5.1（`;` 分隔、无 `&&`、⚠️ `python -c` 嵌双引号会被吃掉 ⇒ 一律写临时脚本文件） |
| 我自己的探针目录 | `%TEMP%\p08t4b\`（⚠️ 收尾删净并复验，见 §9.11） |

### 1.2 ⚠️⚠️ 接手现场最重要的一格：**WIP 的全量 pytest 今天是绿的**

派单 §1 第 1 条把这格称为「本波最重要的一格」。**逐字实测**（`backend/` 下
`python -m pytest -q --no-cov`）：

```
1753 passed, 1 warning in 289.29s (0:04:49)
```

* **0 failed / 0 skipped / 0 error**。基线（`main` = `8e7df10`）是 **1728 passed**
  ⇒ **+25**：`tests/api/test_bind_token.py` 的 **24** 条 + `tests/db/test_migration_chain.py`
  新增的那 **1** 条迁移往返守卫（`test_the_bind_token_migration_round_trips_and_keeps_every_other_row`）。
* ⚠️ **但 WIP 不是「全绿」**：后端绿，**前端 smoke 是红的**。我第一发就跑了一遍
  dev 档 smoke（在修任何东西之前），实测 **16/18 步 · 810 绿 / 6 红 · 退出码 1**：
  1. 第 12 步 `§S2-①`「**3** 个匿名 POST」→ 实测 **4** 个（多了 `POST /api/auth/bind-with-token`）；
  2. 第 12 步 路径模板 `75` → 实测 **77**；
  3. 第 12 步 操作 `103` → 实测 **106**；
  4. 第 12 步 挂 security `85` → 实测 **87**；
  5. 第 12 步 GET `64` → 实测 **65**；
  6. 第 17 步 ④ `src/**/*.vue` 的代码里「引号包着的 `—`」实测 **3 处**
     （`ResourceIndex.vue:480 / 513 / 514`），而那一格的唯一住址是 `src/present.ts` 的 `UNKNOWN`。
  ⚠️ 六条**全部**是「前一位改完产品面、没有同步钉这些数的守卫」这一族，
  **没有一条是产品缺陷**；六条本波全修（§6.4 与 §7）。
* ⚠️ 前一位**没做完的**（控制者已知的四格）我逐格复核并做完了：
  全量 pytest（✅ 本来就是绿的，本波又跑了两遍）、重建 `dist`（§6）、
  变异取证（§7）、报告（本文件）。

### 1.3 WIP 那 39 个文件各做了什么（⚠️ 逐个实测读过，不采信 commit 信息）

`git diff main HEAD --name-only` 实测 **39** 个文件（含 spec）。分四族：

| 族 | 文件 | 做了什么（实测） |
|---|---|---|
| **新增 · 产品** | `backend/app/auth/bind_tokens.py` | 令牌那一层的**唯一所有者**：`mint` / `split` / `issue` / `find` / `matches` / `is_expired` / `consume` / `outstanding` 八个函数 + 四格常量（`TOKEN_ID_BYTES` 12 / `SECRET_BYTES` 24 / `SEPARATOR` `"."` / `BIND_TOKEN_TTL` 7 天）。⚠️ 模块 docstring 把全部设计口径都写了（我按派单要求**先读了它**） |
| **新增 · 迁移** | `backend/migrations/versions/a1af54889103_bind_token.py` | 迁移 **6**：`bind_token` 一张表（9 列）+ 一个复合索引 `ix_bind_token_kind_login_expires_at` + 一个 `UNIQUE(token_id)`；`downgrade` = `drop_index` + `drop_table` |
| **新增 · 守卫** | `backend/tests/api/test_bind_token.py` | **24** 条守卫（7 条派单点名的 + 4 条结构性 + 2 条账面 + 其余） |
| **后端 · 端点与模型** | `app/api/routers/auth.py`（+3 个端点、`PE_ALLOW_SELF_BIND` 开关与 `allow_self_bind()`、3 个新 code）、`app/api/schemas/auth.py`（5 个新模型）、`app/db/models/auth.py`（`BindToken`）、`app/auth/policy.py`（`PURPOSE_BIND_TOKEN` + 键前缀 `bindtoken:`）、`app/api/errors.py`（`_SENSITIVE_INPUT_KEYS` 加 `token` / `token_hash`）、`app/main.py`（装配期调一次 `allow_self_bind()`）、`app/api/audit.py` / `read_audit.py` / `crud.py` / `catalog.py` / `session.py` / `static.py` / `models/__init__.py` / `models/audit.py` / `models/prescription.py` / `auth/__init__.py` / `schemas/audit.py` | 三个新端点 + 计数散文同步 + 读审计对新端点的归类 |
| **后端 · 既有守卫同步** | `tests/api/{test_auth_api,test_column_widths,test_crud,test_prescription_api,test_read_audit_api}.py`、`tests/auth/test_policy.py`、`tests/db/{test_migration_baseline,test_migration_chain,test_models}.py`、`tests/seed/test_generate.py`、`tests/{test_backup_restore,test_main,test_serve}.py` | 表数 29→30、`EXPECTED_*` 五格、openapi 五格、`expected` 27→29、`_NON_PUBLIC_TABLE_CLASSES` 15→16 等 |
| **前端** | `scripts/smoke.mjs`（+134）、`src/api/auth.ts`（+195）、`src/api/generated/schema.d.ts`（+502）、`src/views/admin/ResourceIndex.vue`（+261）、`src/views/auth/Bind.vue`（+146） | 管理台第 **06** 块签发面板 + 台账、`/bind?token=…` 令牌档、`gen:api` 产物、smoke 新拍 |
| **文档** | `Document/2026-09-28-…设计spec.md` | ⚠️ **只改了 2 行**（`git diff -U0` 实测：§13.15 第 10 条与 §15 D2 里的 `75/103/85` → `77/106/87`）⇒ **§13.26 / §1.2 第 4 条 / §13.15 第 4 条 / §15 台账全部是本波补的**（§8） |

⚠️ **行尾如实记**：前一位在 **10** 个文件里留下了裸 LF（8 个 `w/mixed` + 2 个新 `.py` 是
`w/lf`）。本波全部归一成 CRLF，⚠️ **入库 blob 一个字节都没变**（`git diff --numstat`
对那 10 个文件全为空；`git hash-object backend/app/main.py` == `HEAD:backend/app/main.py`
逐字相同 = `1017a4fac81a08db9c6b3be17d0b1c779d7a108c`；而 `git add` 那 8 个文件之后
`git diff --cached --numstat` 也是**空的**）。逐文件见 §10。

### 1.4 开工五格 / 收尾五格

| # | 格 | **开工**（2026-10-18 17:2x） | **收尾**（见 §9.12） |
|---|---|---|---|
| 1 | PID **29848**（甲方试用档 uvicorn） | `"python.exe","29848","Console","1","32,104 K"` **在** | **在** |
| 2 | PID **31576**（cloudflared） | `"cloudflared.exe","31576","Console","1","34,564 K"` **在** | **在** |
| 3 | `backend/pe_trial.db` | **1 597 440 B** / sha256[:16] **`07976CDED7AEDFD6`**；`LastWriteTime` **2026-10-17 20:13:51** | **逐字未变**（同字节、同 sha、同 mtime） |
| 4 | `frontend/dist` | **29 文件 / 695 914 B**；`index.html` **2 729 B / `88E146D579856A3E`** | ⚠️ **变了**（本波**被授权**重建，派单 §0 逐字允许）：**27 文件 / 707 713 B**；`index.html` **2 567 B / `141C673FD0BB4B57`** —— 新旧对照与「29→27 为什么」见 §6.2 |
| 5 | 本机 `127.0.0.1:8030/api/health`（匿名 GET） | **200** `{"status":"ok","tables":29,"students":60,"trial":true}` | **200**、**逐字相同**（⚠️ `tables` 仍是 **29**：迁移 6 由控制者在切换窗口做，我一次都没对它跑 `alembic upgrade`） |

⚠️ **格 4 引出一格 Critical 级的关切**（新前端 + `main` 后端的中间态**此刻已经在甲方那条
活链接上生效**）：逐字实测与处置建议见 **§8.1**，⚠️ 那也是本波**唯一一处顶回**。

⚠️ 全程**没杀/没重启** PID 29848 与 31576；**没** `-Reset`、**没**写 `pe_trial.db`、
**没**对它跑 `alembic`；对它**只发过匿名 GET**（§8.1 那张表的 9 发全是 GET）。
⚠️ 不是我们的进程**一个都没动**：43520（vite 5173）/ 38900（`npm run dev`）/
14368 / 16404（两个 `@deepseek-ai/dsh web`）/ 29848 / 31576 收尾逐个量到**仍在**。

---

## ② 计划 §4 六条的逐条对账表（⚠️ 每格都是**本波实测**）

| # | 计划 §4 的要求 | 前一位 | 本波实测取证 |
|---|---|---|---|
| ① | **管理员签发一次性绑定令牌**（新表 `bind_token`：单次使用、有有效期、指向一个具体的学号/工号） | ✅ **已做** | 权限矩阵实测：匿名 **401** / 在册教师（T0001）**403** / 管理员（T0003）**201**。表 **9 列**（`id / token_id / token_hash / kind / login / issued_at / expires_at / used_at / issued_by`）。**单次使用**：第 1 发 **204**、第 2 发 **409 `bind_token_spent`**，且 `used_at IS NOT NULL` 的行数 = **1**。**有效期**：`expires_at` 改成 1 分钟前 → **403 `bind_token_expired`**；改成 1 微秒前（边界）→ 同样 **403**（判据是 `<=`）。**指向具体账号**：给 A 的令牌去绑 B → 拒（守卫 `test_a_token_for_one_student_cannot_bind_another` 绿） |
| ② | **自助绑定不删**，加一个**环境变量开关**，⚠️ **缺省仍开** | ✅ **已做** | `SELF_BIND_ENV_VAR = "PE_ALLOW_SELF_BIND"`、`SELF_BIND_DEFAULT = "1"`（实测读到）。**缺省仍开的取证**：`delenv` 之后 `allow_self_bind()` = **True**，且**实发**一次 `POST /api/auth/students/bind` → **204**。`=0` 之后学生侧与教师侧各 **403**（message 逐字见 §4.2）。坏值 `true`/`2`/`yes`/`off` 四个**全部** `ValueError`；空串按「没设」→ **True** |
| ③ | **迁移链 5 → 6**，⚠️ `downgrade` **必须真能跑** | ✅ **已做**（代码 + 常驻守卫都在） | ⚠️ 我**自己独立复跑了一整圈**（不是采信那条守卫）：逐字取证见 **§5** |
| ④ | 签发落在既有 `/admin` 资源里（⚠️ **不新开页面** ⇒ 路由数仍 16）；`RESOURCES` 23 会不会变 24？**实测并报** | ✅ **已做**（前一位**顶回了 23→24**，我复核后**同意**） | **路由数仍 16**、`routes` 数组仍 **20**（smoke 第 17 步 ⑥ 绿；⚠️ 而它是不是真的承重，本波用 **M8** 变异证明了：加第 17 条路由 → 那一拍 **红**，`actual=21 expected=20`）。**`RESOURCES` 实测仍 23**（进程内 `len(RESOURCES)`）⇒ ⚠️ **派单说的「若变了，说明书 §5 / README / smoke / `test_crud` 四处要同步」因此一处都不用改**（如实报） |
| ⑤ | 令牌字面量**只在签发那一刻显示一次**，⚠️ **库里存哈希、不许存明文**（**真去库里查**） | ✅ **已做** | ⚠️ 我用**两种不同源的方法**查了（SQL 面 + **库文件原始字节面**），**6 个串各 0 命中**；反空转那一格同时量到选择子在原始字节里命中 **4** 次。逐字见 **§3.3** |
| ⑥ | 令牌那一档**接上同一条限流**（`3/15/60`，按标识），⚠️ **不许绕过** | ✅ **已做** | `policy._policy_of(PURPOSE_BIND_TOKEN) == policy.bind_throttle()` = **True**；`bind_throttle()` 实测 = `max_fails 3 / window 0:15:00 / lock 1:00:00`。**时延签名**：第 1–3 发 **113–117 ms**（各一次 PBKDF2）→ 第 4–6 发 **12–14 ms**（**一次 PBKDF2 都不跑**）。逐字见 **§4.3** |

**结论**：**六条前一位全部做了**（形状是对的，我逐格实测复核过、**没有采信**任何一条注释）。
**本波补的是它们外面的那一圈**：smoke 六条红（§1.2）、`dist` 重建（§6）、
`gen:api` 复核（§6.3）、两处过期计数散文（§6.5）、迁移 6 的**独立**往返探针（§5）、
**8** 格定点变异（§7）、以及**全部文档**（§8：spec §13.26 一节 + §1.2/§13.15 第 4 条 +
§15 台账 B9/D7 + README 一节 + 说明书三处）。

---

## ③ 令牌那一层

### 3.1 形状与分隔符

| 格 | 实测值 | 唯一所有者 |
|---|---|---|
| 明文总长 | **49** 个字符 | `bind_tokens.mint()` |
| 分隔符 | **`.`**（1 个，⚠️ 实测 `plain.count(".") == 1`） | `bind_tokens.SEPARATOR` |
| 两段长 | **16** + **32**（实测 `seg_lens == [16, 32]`） | `TOKEN_ID_BYTES = 12` / `SECRET_BYTES = 24`（URL-safe base64：`ceil(12/3)*4 = 16`、`ceil(24/3)*4 = 32`，都是 3 的倍数故**无 `=` 填充**） |
| 熵 | 选择子 **96 bit**（不是秘密，要的是唯一约束不碰撞）/ 秘密 **192 bit**（是凭据） | 同上（逐字理由在那两个常量的注释里） |
| 有效期缺省 | **7 天**（`dt.timedelta(days=7)`） | `bind_tokens.BIND_TOKEN_TTL`；⚠️ **刻意不做成环境变量**（三条理由在那个常量的注释里，本波复核后**同意**） |

⚠️ 分隔符为什么是 `.` 而不是 `$`：`$` 是 `app.auth.passwords.SEPARATOR`，两个分隔符同词
会让「一个令牌串里出现 `$`」变成一件读代码时要想一下的事。守卫
`test_the_token_shape_and_ttl_have_a_single_owner` 里有一拍**专门**钉住
`SEPARATOR not in "<URL-safe base64 的 64 个字符>"`。

### 3.2 哈希口径与它的**唯一所有者**

* ⚠️ **复用 `app.auth.passwords`，全仓没有第二个 PBKDF2**。落地是两行：
  签发 `hash_password(secret)`、校验 `verify_password(secret, token_hash)`。
* 库里那一格**实测**：`token_hash` = `pbkdf2_sha256$600000$<盐>$<哈希>`，
  **4** 段、**90** 个字符、算法名 `pbkdf2_sha256`、迭代次数 **600000**
  （= 生产缺省，与 `student.password_hash` 逐字同形）。
* **唯一所有者** = `backend/app/auth/passwords.py`。⚠️ 那不是「我看它没写第二份」：
  守卫 `test_the_token_hash_reuses_the_password_module_and_no_second_pbkdf2_exists`
  的第 ② 拍**按 AST 数**全仓 `app/**` 里 `hashlib.pbkdf2_hmac` 的调用点，
  断言**恰好一处**且在 `passwords.py`；第 ① 拍断言 `bind_tokens.py` 的源码里
  **不出现** `hashlib` / `pbkdf2` 两个名字。
* ⚠️ **「从串里读迭代次数」这条性质是承重的**：运维把 `PBKDF2_ITERATIONS` 从 600 000
  抬到 1 000 000 之后，**未使用的旧令牌照旧验得过**。一个自己写的确定性哈希会把这条
  性质弄丢，失效形状是「迎新周发出去的几百张令牌当场一起失效」。

### 3.3 ⚠️⚠️ 「库里真没有明文」的取证（**两法、不同源**）

前一位的守卫扫的是 **SQL 面**（三个串 × 全库每一列）。我**另加了一法**：
把库文件（连 `-wal` / `-shm`）读成**原始字节串**再扫 —— 那一法能抓到
「SQL 读不出来、但留在空闲页 / 未 checkpoint 的 WAL 里」的那一档。

探针：`%TEMP%\p08t4b\probe_a.py`（⚠️ **文件库**、不是内存库；⚠️ 与守卫不同源）。
扫的串**6 个**（比守卫多一倍：两张令牌各三个）：

| 串 | SQL 面（30 张表 / **235** 个非空单元格） | **原始字节面**（**307 200 B**，`-wal`/`-shm` 实测 **0** 个） |
|---|---|---|
| 令牌 C 的整个明文 | **0** | **0** |
| 令牌 C 的 `secret` 那一段 | **0** | **0** |
| 兑换 C 时提交的新口令 | **0** | **0** |
| 令牌 A 的整个明文 | **0** | **0** |
| 令牌 A 的 `secret` 那一段 | **0** | **0** |
| 兑换 A 时提交的新口令 | **0** | **0** |

**反空转**（⚠️ 少了这一格，「扫描面写空了」与「真没有明文」不可分辨）：
* 同一份 **307 200 B** 的字节串里，**选择子 `token_id` 命中 4 次**（它是明文、
  它**应当**在库里；⚠️ 4 次而不是 1 次，因为 SQLite 的表页 + 索引页各存一份，
  且本探针签发过多张令牌）；
* `bind_token` 表**实测 5 行**（不是空表）、`sqlite_master` 实测 **31** 张表
  （30 张业务表 + `alembic_version`）、扫到的非空单元格 **235** 个（不是 0）。

⚠️ 顺带一格：**明文也不进审计**。守卫 `test_the_plaintext_token_never_reaches_the_audit_row`
真的发一次带令牌的兑换、然后把那一行的**全部 9 列**逐列扫；
⚠️ 也不进 **422 的回显**（`TokenBindCreate.token` 是 `SecretStr`，
且 `app/api/errors.py` 的 `_SENSITIVE_INPUT_KEYS` 实测含 `token` 与 `token_hash`
两个键 —— 两道**合起来**才封住「缺 `password` ⇒ `input` 是整个请求体 ⇒ 把同一份
请求体里的令牌明文回显出去」）。

### 3.4 ⚠️ 「选择子单独不是凭证」的取证

| 交什么 | HTTP | `code` |
|---|---|---|
| `<**真的** token_id>.<编造的 32 字符秘密>` | **403** | `forbidden` |
| `<**编造的** 16 字符>.<编造的 32 字符秘密>` | **403** | `forbidden` |
| ⚠️ 两档的**响应体原始字节** | **逐字节相同**（实测 `r.content == r2.content` → `True`） | |
| `nodot-at-all`（形状不对，0 个分隔符） | **403** | `forbidden`（⚠️ 不是 422：`split` 绝不抛，逐字理由在它的 docstring） |

⚠️ 「逐字节相同」那一格是承重的：若「已用过 / 已过期 / 不存在」三档可区分，
一个只拿到 `token_id`（例如从一条被截断的日志里）的人就能判出这个选择子在不在库里。
⚠️ 而**成本**也对：「选择子查无此行」那一档**一次 PBKDF2 都不跑**
（`find` 是一次唯一索引上的点查），与 §4.3 的锁定档同一条形状。

---

## ④ 开关与限流

### 4.1 环境变量名与缺省

| 格 | 实测 |
|---|---|
| 变量名 | **`PE_ALLOW_SELF_BIND`**（`auth_router.SELF_BIND_ENV_VAR`，守卫按字面量钉） |
| 缺省 | **`"1"` = 开**（`SELF_BIND_DEFAULT`） |
| 认得的两格 | `"1"` / `"0"`；⚠️ **其余一律 `ValueError`**（`true` / `2` / `yes` / `off` 四个实测全抛），空串按「没设」处理 → `True` |
| 读它的时机 | **请求时**（不是 import 时）+ **装配期一次**（`create_app` 调它，故一个坏值让服务**起不来**、报错文本点名了那个变量） |
| ⚠️ 它**不读** `PE_ENV` | 与 `allow_header_identity` 刻意不同档：自助绑定是**产品功能**（甲方今天正在用），生产档强制关会让交付物「上线即不可用」 |

### 4.2 ⚠️ 「缺省仍开」的取证 + 关掉之后怎么响亮

**缺省仍开**（这一拍是「不破坏既有交付」的唯一证据）：

* `monkeypatch`/`os.environ` 里**删掉**那个变量 → `allow_self_bind()` 回 **`True`**；
* ⚠️ 并且**实发**一次 `POST /api/auth/students/bind`（学号 + 出生日期 + 新口令）→ **204**；
* ⚠️ 守卫 `test_the_default_tier_is_byte_for_byte_the_pre_task_4_behaviour` 更狠：
  它在**同一个进程**里跑两遍同样的五发请求（一遍未设、一遍 `=0`），
  断言两档**只在**那一条 message 上不同。

**关掉之后**（`PE_ALLOW_SELF_BIND=0`，同一进程）：

* `POST /api/auth/students/bind` → **403**，响应体逐字：

```json
{"error":{"code":"forbidden","message":"本部署已经关掉了自助绑定（学号 + 出生日期 / 工号 + 姓名）：请改用教务干事签发的一次性绑定令牌（POST /api/auth/bind-with-token）。⚠️ 运维口径：这一档由环境变量 PE_ALLOW_SELF_BIND=0 决定（缺省是 1 = 开；把它设回 1 即恢复今天的行为）","detail":null}}
```

* `POST /api/auth/teachers/bind` → 同样 **403 `forbidden`**；
* ⚠️ **令牌那一档不受影响**：开关设成 `0` 的**同一进程**里，兑换一张**已用过**的令牌
  得到的仍是 **409 `bind_token_spent`**（不是那一档 403）⇒ 「先签发令牌、验证流程通了、
  再关开关」这个顺序中间**没有任何一刻**是「谁都绑不上」。

⚠️ message 里**点名了 `PE_ALLOW_SELF_BIND` 与它的缺省值**：这一档的读者是**运维**，
故它**刻意**与「验身材料不符」那一档可区分（与 §4.3 那条「三档 403 逐字节相同」
**不冲突** —— 那一族防的是**匿名探测者**，而本档只在**开关被显式关掉**的部署上出现）。

### 4.3 ⚠️ 令牌档接上 `3/15/60` 的**时延签名**

阈值与「哪个用途用哪一组」的唯一判据：

```
policy.bind_throttle()  = max_fails 3 / window 0:15:00 / lock 1:00:00
policy.throttle()       = max_fails 5 / window 0:15:00 / lock 0:15:00
policy._policy_of(PURPOSE_BIND_TOKEN) == policy.bind_throttle()   → True
policy._policy_of(PURPOSE_BIND)       == policy.bind_throttle()   → True
sorted(policy.PURPOSES) = ['bind', 'bind_token', 'login']
```

⇒ ⚠️ **没有第二组环境变量**：令牌那一档读的就是 `PE_BIND_MAX_FAILS` /
`PE_BIND_WINDOW_MIN` / `PE_BIND_LOCK_MIN` 那三个（§13.4.11 的同一组）。

**时延签名**（探针 `probe_a3.py`：同一个真 `token_id` + 逐次翻转一个字符的假秘密，
600 000 次迭代）：

| 发 | HTTP | `code` | 实测 ms | 读法 |
|---|---|---|---|---|
| 1 | 403 | `forbidden` | **116.8** | 跑了一次 PBKDF2 |
| 2 | 403 | `forbidden` | **113.2** | 同上 |
| 3 | 403 | `forbidden` | **116.8** | 同上（第 3 次失败 ⇒ 两把键都达到阈值） |
| 4 | 403 | `forbidden` | **14.1** | ⚠️ **锁定档：一次 PBKDF2 都不跑** |
| 5 | 403 | `forbidden` | **13.6** | 同上 |
| 6 | 403 | `forbidden` | **11.9** | 同上 |
| 锁定后交**真令牌** | **403** | `forbidden` | **13.2** | ⚠️ 锁定档排在验秘密**之前**，故真令牌也进不去 |
| 另一个学号的令牌 | **204** | — | **200.0** | ⚠️ 锁是**按键**的、不是全局的 |

⇒ **8.5×** 的差就是「锁定档不跑哈希」的可量取证（与 §1.2 第 15 条那一格同一条形状）。
⚠️ 六发的响应体**逐字节相同**（`_BIND_TOKEN_FORBIDDEN_MESSAGE` 一个住址）。

**两把键各写三行**（`login_attempt` 实测 8 行）：

```
bind:2025099201            ok=0   ×3      ← (kind, "bind", 学号)
bindtoken:fYW7hIPqMaicHY9Z ok=0   ×3      ← (kind, "bind_token", token_id)
bindtoken:RMMoGEFVtnV-yS13 ok=1   ×1      ← 另一个学号成功兑换（record_success 清零）
bind:2025099202            ok=1   ×1
```

⚠️ **第 4–6 发一行都没写**（`policy` 的「锁定期间不写行」= 防滑动锁），
⚠️ 而那张**被打了 6 发的令牌 `used_at` 仍是 NULL**（验不过 ⇒ 不作废）。

⚠️ **如实记一格残余**：「选择子查无此行」那一档**刻意不计数**（两把键都需要 `kind`，
而那一格只能从令牌行上读），故一个匿名调用方可以**无限次**打那一档，
每次的成本是一次索引未命中 ⇒ 它落在 §15 **B4**（反代级全局限速）里，不是新账。

---

## ⑤ 迁移 6（`a1af54889103`）

### 5.1 链与头

| 格 | 实测 |
|---|---|
| `migrations/versions/*.py` | **6** 个（`53e5a548c40e` → `0b7da3d20211` → `7f3923d8af84` → `0ac943e0da9b` → `03331a689ee4` → **`a1af54889103`**） |
| `alembic heads` | **`a1af54889103 (head)`** —— **一行、单头**，退出码 **0** |
| `alembic current`（往返之后） | **`a1af54889103 (head)`** |
| **残差 diff** | **0** —— `alembic check` 实测输出 **`No new upgrade operations detected.`**、退出码 **0**；常驻守卫 `test_the_migration_chain_is_in_sync_with_the_models` 绿 |
| 表数 | **29 → 30**（`sqlite_master` **30 → 31**，含 `alembic_version`）；`Base.metadata.tables` 进程内实测 **30** |
| `EXPECTED_*` 五格（前一位已同步，本波复核） | 表 **31** / 列 **288** / 索引 **13** / 唯一 **22** / 外键 **41** / CHECK **33** |

### 5.2 ⚠️⚠️ `downgrade` 真跑一整圈（**带真实演示数据**，照 Task 1 的姿势）

探针 `%TEMP%\p08t4b\probe_mig6.py`。⚠️ **不是**在一个空库上跑：先用
`demo_bootstrap.py` 灌一个**60 人 / 840 行打卡**的库（= 甲方试用库的同款形状），
再灌 **2 行 `bind_token`**（一行学生未用、一行教师已用），然后回滚。

| 步 | 命令 | 退出码 | 实测 |
|---|---|---|---|
| ① 灌库 | `demo_bootstrap.py --db-url sqlite:///%TEMP%/p08t4b/mig6.db` | **0** | **31** 张表、`alembic_version` = `a1af54889103`；`training_log` **840** 行、`student` **60** 行、`bind_token` **0** 行 |
| ② 灌 2 行令牌 | 直接 SQL INSERT | — | `bind_token` = **2** 行（内容摘要 `96077EA8376C8B58`） |
| ③ **`alembic downgrade -1`** | | **0** | `Running downgrade a1af54889103 -> 03331a689ee4`；**30** 张表；`alembic_version` = **`03331a689ee4`**；`bind_token` **不在** `sqlite_master` 里；索引 `ix_bind_token_kind_login_expires_at` **也不在** |
| ④ **其余每一张表逐字还在** | 逐表逐行 `repr()` 后取 sha256 | — | **29 张业务表 / 合计 2 591 行的摘要逐个相同**；⚠️ 唯一变的是 `alembic_version` 自己（`9B55E63ABC1CAFC2` → `1806D4FCA036220C`）—— **那正是回滚要做的事** |
| ⑤ **`alembic upgrade head`** | | **0** | `Running upgrade 03331a689ee4 -> a1af54889103`；**31** 张表；`bind_token` **回来了且是空的（0 行）**；⚠️ 其余 29 张表的摘要**仍然逐个相同** |

### 5.3 ⚠️ 「带着数据的库 `upgrade head` 之后一切仍绿」（计划 §9 最后一格）

在上面 ⑤ 之后的**同一个库**上起 app（`create_app(db_url=…)` + `TestClient`）：

| 发 | 结果 |
|---|---|
| `GET /api/health` | **200** `{"status":"ok","tables":30,"students":60,"trial":false}` |
| `GET /api/students?limit=5`（教师头） | **200** |
| `GET /api/auth/bind-tokens`（管理员头） | **200** |
| `POST /api/auth/bind-tokens`（给 `2025060001`，先把它的 `password_hash` 置回 NULL） | **201** |
| `POST /api/auth/bind-with-token`（用刚签发的那一张） | **204** |
| `bind_token` 行数 | **1** |

⇒ 甲方那份试用库（今天停在迁移 5、**1 597 440 B**）在切换窗口里 `upgrade head`
之后**不会**坏。⚠️ 我**一次都没对它跑过 alembic**（派单逐字禁止）。

### 5.4 ⚠️ 回滚的两格实话（写进了 §13.26.7）

* **回滚会丢数据**：`bind_token` 里装的是**已签发过**的凭据台账，删掉不可重推
  ⇒ 要回滚请先跑 `backend/scripts/backup.py`。
* ⚠️ **正确的回滚姿势是「代码与迁移一起退」**（`git revert` 那个 commit）：
  只退迁移不退代码的话，模型上还有 `BindToken`、三个端点还在，
  于是一个回滚过迁移的库会让它们一律 **500**（`no such table: bind_token`）。
  ⚠️ 而**只退迁移不会把任何人锁在门外**（两个自助端点照旧工作，`PE_ALLOW_SELF_BIND`
  缺省是 `1`）—— 那一格是计划 §4「要做得可回退」的**数据库侧**的一半。

---

## ⑥ 前端与重建

### 6.1 路由数 / `RESOURCES`

| 格 | 基线 | 本波实测 | |
|---|---|---|---|
| **路由数** | **16** | **16**（smoke 第 14 步 18/18 绿、第 17 步 ⑥ 绿） | ✅ |
| `routes` 数组的 `path` 字面量 | **20** | **20**（第 17 步 ⑥ 的 `expected=20`） | ✅ |
| **`RESOURCES`** | **23** | **23**（进程内 `len(RESOURCES)` 现量） | ✅ ⚠️ **没变 24** |

⚠️ **`RESOURCES` 23 → 24 值不值**（派单顶回候选 ④）：前一位**顶回了**、
我复核后**同意不顶回**。承重的那一条理由是：泛型工厂的 `create_row` 逐字是
`model(**payload.model_dump())` ⇒ **每一列都必须来自请求体**，
而「服务端生成秘密、明文只回一次」与那个形状**结构上互斥**
（那个形状下 `token_hash` 只能由**客户端**交上来 = 「任何人可以给任何人设一个
自己知道的口令」）。守卫 `test_bind_token_is_not_a_generic_crud_resource` 把它钉成
**三拍**（`len(RESOURCES) == 23` / 里面没有 `bind_token` / openapi 上**没有**
`/api/bind-tokens` 那个泛型路径形状），⚠️ 外加两拍方法面
（`bind-tokens` 只有 `get`+`post`、`bind-with-token` 只有 `post` ⇒
「单次使用」不许被一个 PATCH 改回去）。
⚠️ **于是派单说的「若变了，说明书 §5 / README / smoke / `test_crud` 四处要同步」
一处都不用改**（如实报）。

### 6.2 ⚠️ 重建时刻与新旧哈希对照（**本波重建了两次**）

| | **旧**（= 今天发给甲方的那一份，`main` 建出来的） | 中间态（17:39 那一次） | **新**（最终那一次） |
|---|---|---|---|
| 重建时刻 | — | **2026-10-18 17:39:23** | **2026-10-18 18:01:23** |
| 文件数 / 合计字节 | **29** / **695 914 B** | 27 / 707 704 B | **27** / **707 713 B** |
| `index.html` | **2 729 B** / **`88E146D579856A3E`** | 2 567 B / `C86B067A572612AC` | **2 567 B** / **`141C673FD0BB4B57`** |
| entry JS | `index-D20kCqH-.js`（**176.00 kB**） | `index-CXR8Tblz.js`（251.91 kB） | **`index-Ch2KuVNg.js`**（**251.91 kB** = 251 917 B） |
| entry CSS | `index-D2BHlq_t.css` | `index-BuNW43q3.css`（66.66 kB） | **`index-BuNW43q3.css`** |
| `AuditLogList` | `AuditLogList-D4b80VTl.js` | `AuditLogList-DbQU-xpI.js` | **`AuditLogList-BiaLuu7Z.js`** |
| `ResourceIndex` | `ResourceIndex-BJ2I7mJE.js` | `ResourceIndex-I9RGaulu.js` | **`ResourceIndex-Dycvqe3G.js`** |
| 共享 chunk | **`SectionHead-BVjmK34h.js`（71.67 kB）** + `SectionHead-D8xp8nwc.css` | **不见了** | **不见了** |

⚠️⚠️ **两次重建**的理由（如实记）：第一次（17:39）是对 WIP 的原样重建，
它跑完之后 smoke 才告诉我 `ResourceIndex.vue` 里那三处硬编码的 `'—'`（§1.2 第 6 条红）；
修完（改成 import `present.ts` 的 `UNKNOWN`）必须**再建一次**，
否则产物里仍然是那三处字面量。⚠️ 渲染结果**逐字不变**（`UNKNOWN === '—'`）。

⚠️⚠️ **文件数 29 → 27 不是丢了东西**，本波**用对照实验证明了**：
用 `git worktree add %TEMP%\p08t4b\wt_main main` + 一个指向仓库 `node_modules` 的
junction，在 **`main`** 上跑了一次 `npm run build`，产物**逐字等于**在发的那一份：
**29 文件 / 695 914 B / `index.html` 2 729 B**，且 `SectionHead-BVjmK34h.js` = **71.67 kB**、
`index-D20kCqH-.js` = **176.00 kB**。⇒ 那一个 `SectionHead-*.js` **不是**
「`SectionHead.vue` 一个组件」，而是 rollup 给「被很多懒加载 chunk 共用、
但不被静态 entry 独占」的那一批模块开的**共享 chunk**（71.67 kB）。
本波 `auth.ts` / `Bind.vue` / `ResourceIndex.vue` 三处改动之后，那一批模块的
「可达入口集合」变了，rollup 把它们**并进了 entry**：
**176.00 + 71.67 ≈ 247.67 kB**，+ Task 4 的新代码 ≈ **251.91 kB** = 新的
`index-Ch2KuVNg.js`。⚠️ 内容一格没丢，实测：`section__chip` / `section__label` /
`section__rule` 三个类名**在** `index-Ch2KuVNg.js` 里、CSS **在** `index-BuNW43q3.css` 里。
⚠️ 那个 worktree 收尾已 `git worktree remove --force` + `prune`（`git worktree list`
实测只剩主工作树一行），⚠️ 且它**一次都没碰主工作树**（`git status` 全程为空）。

### 6.3 `gen:api` 复核 + `schema.d.ts` 行尾

* 重跑 `npm run gen:api`：`dump_openapi` 报 **453 555 字节 / 77 路径 / 106 操作**、
  `openapi-typescript 7.13.0` 退出码 **0**；⚠️ 跑完 **`git status --porcelain` 为空**
  ⇒ **前一位确实重跑过**，产物与今天的后端散文**逐字相符**。
* `git ls-files --eol frontend/src/api/generated/schema.d.ts` = **`i/lf  w/lf  attr/`**。
  ⚠️ 这就是派单逐字点名的那个**特例**（工具写 LF、`autocrlf` checkout 成 CRLF，
  差值 == 行数，两份 `hash-object` 成同一个 blob ⇒ 可逆成立）。
  ⚠️ 本波**刻意没有**把它归一成 CRLF：`gen:api` 每跑一次就会把它写回 LF，
  归一它是无谓的 churn（如实记，与 §10 那一格一起读）。

### 6.4 两个构建守卫

| 守卫 | 基线 | 本波 | |
|---|---|---|---|
| `npm run check:tokens` | 36 个文件 / 下界 25 / 0 offender | **36 个文件**（6 个 `.css` + 30 个 `.vue`）/ **0 offender** / 退出码 **0** | ✅ |
| `npm run check:dist` | 绿（56 个文件 / 1 387 647 字符） | **全绿** / 退出码 **0**；⚠️ 扫描面 **56 个文件 / 1 422 299 字符**（基线 1 387 647，**+34 652** = Task 4 的新源面）；`adoptFromUrl` **0** 次、两条 CDN 各 **0** 次、4 条「会变假的渲染正文」各 **0** 次，⚠️ 而谓词的**反空转三格都在**（4 组「抓得到改前 / 放过改后」逐个 ✓） | ✅ |
| `npx vue-tsc -b` | 绿 | **退出码 0**（两次重建各跑一次） | ✅ |

⚠️ **两个守卫都在**最终**那一份产物（18:01:23 那一次）上重跑过**：
① 收尾时单独各跑一次（上面表里的数就是那一次的）；② 而 smoke 的**第 15 步**
本来就把它们各跑一次，故三档 smoke（dev / 产品档 / 试用档）里它们**又各绿了三遍**
（`check-tokens：退出码 0` / `check-dist：退出码 0` 四条断言在三档里逐个 ✓）。
⚠️ 如实记一处差值：17:39 那一次构建的 `check:dist` 扫描面是 **1 422 278** 字符，
18:01 那一次是 **1 422 299**（**+21**）—— 那 21 个字符正是
`ResourceIndex.vue` 改成 `import { onDeleteZh, UNKNOWN }` 与三处 `?? UNKNOWN` 的差。
⚠️ 而 `vue-tsc -b` 在 18:01 那一次里也跑过（`npm run build` = `vue-tsc -b && vite build`，
退出码 **0** ⇒ 两个都绿）。


### 6.5 ⚠️ 两处过期计数散文（本波改正，⚠️ 都只是注释、一句断言都没改）

1. `backend/tests/api/test_prescription_api.py`：Task 4 那段注释里
   「`crud` 那一圈的操作数**不变**（76 = 103 − 27）」—— ⚠️ **本波真的动了**，
   而且那句算式**一直少减了 2**（`/api/rpe-records` 与 `/api/training-logs` 两个路径
   因为在 `expected` 里而被**整条**排除，它们的 `GET` 也从 `crud` 出去了）。
   实测：`main` 上是 **74**、本波之后是 **75**（+ 那个**匿名**的
   `POST /api/auth/bind-with-token`：它不在 `expected` 里，故按「路径不在 `expected`
   就算 `crud`」的判据落进来，与 `login` 和两个自助 `bind` 同档）。
   ⚠️ 上面**五段历史注释逐字保留**（硬规矩 #66），活的那一句断言只有 `>= 70`
   （它从未依赖那个算式，故五波都没红）。
2. `backend/tests/architecture/test_layering.py`：按既有体例补了一段
   「Plan 08 Task 4 给 `auth` 加了第 5 个成员 `bind_tokens.py`」⇒
   扫描面 **73 → 74**（pipeline 10 + db 14 + domain 18 + api 27 + auth **5**）、
   反向那一圈 **46 → 47**；两个下界（`>= 21` / `>= 20`）刻意不抬（21 ≤ 74、20 ≤ 47）。

---

## ⑦ 守卫与定点变异

### 7.1 守卫条数（⚠️ 派单点名的 8 条逐条都在，我逐条实测复核过）

`tests/api/test_bind_token.py` = **24** 条；另加 `tests/db/test_migration_chain.py`
的 **1** 条迁移往返守卫、`tests/db/test_models.py` / `test_migration_baseline.py` /
`tests/api/test_column_widths.py` / `tests/auth/test_policy.py` 里同步的那几拍。

| 派单点名 | 守卫 | 本波复核 |
|---|---|---|
| ① 令牌**单次使用** | `test_the_second_redemption_of_one_token_is_refused_and_the_first_one_wins` | ✅ 我另用探针实测：第 1 发 204 / 第 2 发 **409 `bind_token_spent`** |
| ② **过期** | `test_an_expired_token_is_refused_with_its_own_code` | ✅ 探针实测 403 `bind_token_expired` + 边界（1 μs）也 403 |
| ③ **哈希入库而明文不入库**（真去库里查） | `test_the_plaintext_token_and_its_secret_never_reach_any_column_of_any_table` | ✅ **我另加了一法**（原始字节面），结论一致（§3.3） |
| ④ **选择子单独不是凭证** | `test_the_selector_alone_is_not_a_credential` | ✅ 探针实测两档 403 且响应体逐字节相同（§3.4） |
| ⑤ **开关关掉 → 响亮**，且**缺省仍开** | `test_the_self_bind_switch_is_open_by_default` + `test_turning_the_switch_off_refuses_both_self_service_endpoints_loudly` + `test_the_switch_reads_one_and_zero_and_raises_on_anything_else` + `test_the_default_tier_is_byte_for_byte_the_pre_task_4_behaviour` | ✅ 四条**四拍**，探针独立复跑（§4.2） |
| ⑥ **令牌档接上限流** | `test_the_token_tier_is_throttled_on_both_keys_and_the_fourth_shot_is_refused` + `test_a_successful_redemption_clears_both_keys` | ✅ **时延签名**是我的探针另量的（守卫不量时延，量的是 `login_attempt` 的行数与前缀 ⇒ ⚠️ **两法不同源**，§4.3） |
| ⑦ **`downgrade` 往返** | `test_the_bind_token_migration_round_trips_and_keeps_every_other_row` | ✅ 我另用真 CLI 跑了一整圈（§5.2） |
| ⑧ **路由数仍 16** | smoke 第 14 步 + 第 17 步 ⑥ | ✅ ⚠️ 并用 **M8** 变异证明它**承重** |

### 7.2 ⚠️⚠️ 8 格定点变异（每格：改 → 跑整个文件 → **逐字节还原** → 复绿）

驱动器 `%TEMP%\p08t4b\mutate.py`（M8 另走 `%TEMP%\p08t4b\m8.py` + 一整轮 smoke）。
每格的还原判据是**三拍**：① 目标文件的 sha256 与改前**逐字相同**；
② `git diff --name-only -- <file>` **为空**；③ 复跑那一整个文件**全绿**。

| # | 变异（改的是**产品代码**） | 跑 | 结果 | 红在哪几条 | 还原 sha | `git diff` | 复绿 |
|---|---|---|---|---|---|---|---|
| **M1** | `bind_tokens.consume` 的 `UPDATE … WHERE used_at IS NULL` + `rowcount` 判据整个换成 `return True`（= **把「单次使用」的判据去掉**） | `test_bind_token.py` | **红 ✓**（3 failed / 21 passed，5.31 s） | `…second_redemption…` / `…one_account_may_hold_several_live_tokens…` / `…listing_never_returns_the_plaintext…` | ✅ | 空 | **24 passed** |
| **M2** | `bind_tokens.is_expired` → `return False`（**把「过期」的判据去掉**） | 同上 | **红 ✓**（1 failed / 23 passed，3.89 s） | `test_an_expired_token_is_refused_with_its_own_code` | ✅ | 空 | **24 passed** |
| **M3** | `issue` 的 `token_hash=hash_password(secret)` → `token_hash=secret`（**把哈希换成明文存**） | 同上 | **红 ✓**（**11** failed / 13 passed，2.78 s） | 含 `…plaintext_token_and_its_secret_never_reach_any_column_of_any_table` / `…plaintext_token_never_reaches_the_audit_row` / `…token_hash_reuses_the_password_module…` 等 11 条 | ✅ | 空 | **24 passed** |
| **M4** | `auth.SELF_BIND_DEFAULT` `"1"` → `"0"`（**把开关的缺省值反过来**） | 同上 | **红 ✓**（3 failed / 21 passed，3.65 s） | `…self_bind_switch_is_open_by_default` / `…switch_reads_one_and_zero_and_raises…` / `…default_tier_is_byte_for_byte_the_pre_task_4_behaviour` | ✅ | 空 | **24 passed** |
| **M5** | `bind_with_token` 里那一次「两把键任一锁住就 403」的判定 → `if False:`（**把令牌那一档的限流绕过**） | 同上 | **红 ✓**（1 failed / 23 passed，4.17 s） | `test_the_token_tier_is_throttled_on_both_keys_and_the_fourth_shot_is_refused` | ✅ | 空 | **24 passed** |
| **M6** | `catalog.RESOURCES` 的 `students` 那一行 `"read_scope": READ_SCOPE_STAFF` → `None`（**把 RESOURCES 的清单放宽** = 把含 `birth` 的名册收回匿名可读） | `test_crud.py` | **红 ✓**（**6** failed / 45 passed，9.49 s） | `…read_scope_tiers_are_pinned_to_those_seven_zero_thirteen_one_and_two` / `…two_roster_resources_admit_only_staff_reads` / `…student_keyed_resources_admit_four_read_tiers` / `…all_twenty_three_resources_are_listable` / `…scope_hook_rejects_a_mismatched_identity_with_403` / `…weekly_class_reports_are_scoped…` | ✅ | 空 | **51 passed** |
| **M7** | `bind_tokens.matches` → `return True`（**把「选择子不是凭证」那一拍去掉**） | `test_bind_token.py` | **红 ✓**（3 failed / 21 passed，3.40 s） | `test_the_selector_alone_is_not_a_credential` / `…successful_redemption_clears_both_keys` / `…token_tier_is_throttled…` | ✅ | 空 | **24 passed** |
| **M8** | `frontend/src/router/index.ts` **加第 17 条路由**（`/admin/m8-probe`）（**把 §4「不新开页面」的判据放宽**） | **一整轮 dev 档 smoke**（重灌库 + 重起 uvicorn 8041 + **重起** vite 5199） | **红 ✓**（**17/18 步 · 815 绿 / 1 红 · 退出码 1**） | 第 17 步 ⑥「`routes` 数组里的 `path` 字面量条数」→ **`actual=21 expected=20`** | ✅ sha256 `9f598078cf5c9ea5a0ab0d93a8e27406d65954ca2918dc75dd91f5b04d763524` 逐字相同 | 空（`git status --porcelain` 亦为空） | **18/18 · 816 绿 / 0 红 · 退出码 0** |

⇒ **8 格全红、8 格全部逐字节还原、8 格全部复绿**。

⚠️ M8 的**一格如实记**：加第 17 条路由之后**只有第 17 步 ⑥ 那一拍红**，
第 14 步（16 条路由的 DOM 取证）**仍然绿** —— 因为它迭代的是**自己那份写死的 16 条清单**，
多出来的那一条**根本不会被访问**。⚠️ 那不是假绿（它的判据是「这 16 条各自渲染正确」，
不是「只有这 16 条」），但它说明「不新开页面」这一格**唯一的牙**是第 17 步 ⑥
那个字面量计数 ⇒ 那一条**不能删**。

### 7.3 ⚠️ 有没有抓到前一位留下的**假绿**？—— **没有**，但我逐条核过高风险的几条

派单逐字点了两处前科（Plan 06 终审的自指守卫、Plan 07 Task 8 的子串前缀假绿）。
本波逐条核过 `test_bind_token.py` 里**期望侧最可能与被测侧同源**的 5 条：

| 守卫 | 期望侧 | 被测侧 | 判定 |
|---|---|---|---|
| `…self_bind_switch_is_open_by_default` | ① 读 `auth_router.SELF_BIND_DEFAULT` 这个**常量**（⚠️ 同源）② `delenv` 之后**实发一次**自助绑定断言 **204**（⚠️ 不同源） | HTTP 响应 | ✅ **两拍合起来才封住**，且它的 docstring 逐字写了「只钉常量的话『常量是 1、而 `allow_self_bind` 写反了』是绿的；只发请求的话『函数对、而常量被改成 0』是绿的」⇒ **不是假绿**（M4 实测两拍**都**红了） |
| `…token_shape_and_ttl_have_a_single_owner` | **字面量** 16 / 32 / `16+1+32` / `"."` / `timedelta(days=7)` + `width.declared_width(token_id 列)` | **200 次真实 `mint()`** | ✅ 不同源 |
| `…token_tier_is_throttled_on_both_keys…` | `policy.DEFAULT_BIND_*` 三个**字面量**（3/15/60）+ `login_attempt` 的**行数与前缀**（3+3=6） | HTTP 状态码 + DB 行 | ✅ 不同源（M5 实测红） |
| `…plaintext_token_and_its_secret_never_reach_any_column…` | 签发那一刻**手里握着的**明文串 | **全库每一列** | ✅ 不同源（M3 实测红；⚠️ 我另用原始字节面独立复跑，§3.3） |
| `…token_hash_reuses_the_password_module…` | **AST** 数全仓 `hashlib.pbkdf2_hmac` 的调用点 == 1 | 源码 | ✅ 不同源 |

⚠️ 一格**接近同源、但按本仓既有惯例可接受**：`…throttled…` 里那三行
`assert policy.DEFAULT_BIND_MAX_FAILS == 3`（期望侧与被测侧读的是同一个常量）。
它的**牙**不在这三行（在 `login_attempt` 的行数上），而这三行钉的是
「**所有者**是 `app.auth.policy`、端点一个阈值字面量都不写」这条惯例
（与 `tests/auth/test_policy.py` 的同款断言同族）。⚠️ 如实记、**不改**。

### 7.4 ⚠️ 一格 pytest 调用面的 quirk（**预存**，不是本波缺陷）

把 `tests/api/test_prescription_api.py tests/architecture/test_layering.py
tests/test_main.py tests/api/test_bind_token.py` 四个一起传给 pytest ⇒
**20 errors**，一律是 `fixture 'client' not found`。

⚠️ **它是预存的**：把 `test_bind_token.py` 换成**本波一个字节都没碰过**的
`tests/api/test_auth_api.py`，同样报 **41 errors** 同一句 ⇒ 与本波无关。
⚠️ 而两个**正规**调用面都是绿的：全量（不带参数）**1753 passed / 0 error**；
`tests/api/test_bind_token.py` 单文件 **24 passed**；
`test_layering.py + test_auth_api.py` 两文件 **49 passed**；
`test_main.py + test_bind_token.py` 两文件 **51 passed**。
⇒ 只在**那一种四文件组合**下复现（怀疑与跨目录 conftest 的收集有关），
**已如实记为关切**（§8.5），本波**不修**（它不在计划 §4 的范围里，
而修它要动 `tests/` 的 conftest 布局 = 一次结构性改动）。

---

## ⑧ 待清扫 / 关切 / 没按派单做的 / **顶回**

### 8.1 ⚠️⚠️ **顶回（1 处，Critical 级运维面）：「新前端 + 旧后端」这个中间态**此刻已经在甲方那条活链接上生效**，而派单说的「你不必担心」低估了它**

派单 §0 逐字写着：「⚠️ 控制者会在你之后做切换窗口 = 迁移 + 重启，
故『新前端 + 旧后端』这个中间态由控制者负责收尾，**你不必担心**」。
⚠️ 而计划 §9 对这一格的描述是「**重建会让甲方已打开的页面懒加载 404**」。
**本波实测：暴露面比那一句大两格。**

`serve.ps1` 是把 `frontend/dist` 交给 `StaticFiles` **按请求从磁盘读**的，
故 `npm run build` 一落地，**甲方那条 8030 立刻就在发新前端**（不需要重启）。
⚠️ 九发**匿名 GET**（派单逐字允许的那一档；⚠️ 一发登录/写入都没发）实测：

| 请求 | 实测 | 读法 |
|---|---|---|
| `GET /api/health` | **200** `{"status":"ok","tables":29,…,"trial":true}` | 后端仍是**迁移 5** |
| `GET /openapi.json` | **200 / 428 074 B** | ⚠️ 那是 **`main`** 的契约（75 路径 / 103 操作），不是今天的 453 555 |
| `GET /` | **200 / 2 567 B** | ⚠️ **已经是新的 `index.html`**（改前 2 729 B） |
| `GET /assets/index-Ch2KuVNg.js` | **200 / 251 917 B** | 新 entry 在发 |
| `GET /assets/index-D20kCqH-.js` | **404** `not_found` | ⚠️ 旧 entry **已从磁盘上没了** |
| `GET /assets/AuditLogList-D4b80VTl.js` | **404** | ⚠️ **已打开的页面**懒加载 → 404（= 计划 §9 说的那一格） |
| `GET /assets/SectionHead-BVjmK34h.js` | **404** | 同上（那个共享 chunk 本波并进了 entry） |
| `GET /api/auth/bind-tokens` | **404** `not_found` | ⚠️⚠️ **这是派单没提到的那一格**：新前端的 `/admin` 第 **06** 块在 `onMounted` 里**自动**调它 |
| `GET /api/read-audit-logs` | **401** `unauthenticated` | （对照：Task 1 的端点**在**，故 8030 跑的确实是 `main` 的代码） |

⇒ **两格甲方看得见的后果**：
1. **已经打开着页面的甲方**：任何一次懒加载（换页到审计留痕 / 学生详情 / 大屏）→ **404** →
   那一页白屏，要 Ctrl-F5；
2. **Ctrl-F5 之后的甲方**：拿到新前端 ⇒ 打开 `/admin` 会**自动**发一次
   `GET /api/auth/bind-tokens` → **404** → `reloadLedger()` 的 catch 里
   ⚠️ **`throw err`**（`ResourceIndex.vue:104`，逐字注释写着「交给 `app.config.errorHandler`
   挂横幅」）⇒ **页面顶上挂一条全局错误横幅** + 第 06 块里一句「台账读不到」。
   ⚠️ 其余功能**不受影响**（`onMounted` 那一句是 `void …catch(() => undefined)`，
   故没有未处理的 rejection；签发按钮点了会得到后端那句 404 原文）。

⚠️ **顶回的具体内容**：不是「不该重建 dist」（派单授权得对，不重建就验不到产品档），
而是**「你不必担心」那一句要改成「你要立刻收尾」**。给控制者三个选项，按代价排：

* **(a) 推荐：立刻做切换窗口**（`alembic upgrade head` + 重启 PID 29848 + 通知甲方 Ctrl-F5）。
  ⚠️ 三件事在同一个窗口里做完（计划 §9 逐字要求），⚠️ **不许 `-Reset`**。
  本波已实测「带着 840 行打卡数据的库 `upgrade head` 之后一切仍绿」（§5.3），
  且**备份已经在**（`backend/backups/pe_trial-pre-migration5-20261017-201257.db`，
  1 589 248 B，实测仍在、未入库）。
* **(b) 若切换窗口今天做不了**：把 `dist` **回滚**成 `main` 那一份。
  ⚠️ 配方本波已经验证过（§6.2 那个 worktree 对照实验）：
  `git worktree add <tmp> main` → 一个指向仓库 `node_modules` 的 junction →
  在 `<tmp>/frontend` 里 `npm run build` → 把 `<tmp>/frontend/dist` 整个拷回来。
  产物**逐字等于**改前那一份（29 / 695 914 / `88E146D579856A3E`）。
* **(c) 最小止血**（若两件事都做不了）：只把 `dist/index.html` 与
  `dist/assets/**` 里的**旧文件**补回去（新旧并存）⇒ 已打开的页面不再 404。
  ⚠️ 而它**治不了**第 2 格（新 `index.html` 仍然会调那个不存在的端点），
  故 (c) 只是半格止血。

⚠️ **本波没有自己做 (a) 也没有做 (b)**：派单逐字规定「切换窗口由控制者排，
实现者**不要自己切**」，而 (b) 会让本波的验收格（`dist` 新旧对照 + 产品档 smoke）
失去意义。如实报，等控制者裁定。

### 8.2 顶回（其余候选，逐个核过 ⇒ **不顶回**）

派单 §3 列了 6 个最可能顶回的候选，⚠️ **除 §8.1 那一处外，其余 5 个我都核过并同意**：

| 候选 | 我核了什么 | 结论 |
|---|---|---|
| ① §1.2 / §13.15 第 4 条的口径 | `SELF_BIND_DEFAULT` 实测 `"1"`；`delenv` 之后**实发**一次自助绑定 → **204** | ✅ **同意控制者的倾向**：改成「**已给出收掉它的手段，但缺省仍开；要收掉需显式设环境变量**」，**不划成「已收」**。⚠️ 而且我另加了一条理由：把缺省改成「关」也**买不到**多少 —— `birth` 对全校任何教职仍然可读，一个教职仍然可以拿它去 `POST /api/auth/login` 逐个探测 ⇒ **真正收掉它是 Task 5 的活** |
| ② 开关的变量名与缺省 | `PE_ALLOW_SELF_BIND` / `"1"`；坏值**响亮失败**（四个坏值实测全 `ValueError`）、装配期与请求期**两个**响的地方 | ✅ **同意**。「认不出 ⇒ 关」的失效方向是把甲方挡在门外、「认不出 ⇒ 开」是静默不安全，故取第三条（与 `app.deploy.tier` 对 `PE_ENV` 同一条口径） |
| ③ 令牌的有效期缺省 | `BIND_TOKEN_TTL` = 7 天的**三条理由** + 「刻意不做成环境变量」那一条 | ✅ **同意**。7 天盖得住「周五签发、周一绑定」，且短到「泄漏了也会自己死」；⚠️ 与会话那 2 小时**刻意不是一个量级** |
| ④ `RESOURCES` 23 → 24 值不值 | 泛型工厂 `create_row` = `model(**payload.model_dump())`；守卫的三拍 + 方法面两拍 | ✅ **同意前一位的顶回**（保持 **23**）。⚠️ 于是派单说的「四处清单要同步」**一处都不用改** |
| ⑤ 说明书 / README 改不改 | 说明书 §5 那句话在开关缺省仍开时**仍然是真话**；但 §4 路线三确实多了一格、§6 ② 那条须知确实该改口径 | ✅ **判断 = 都要改**：说明书**三处**（路线三加第 6 步 / §5 `/bind` 那一行**追加**两档 / §6 ② 改口径），README **加一节**（姿势照 Task 2 / Task 3 的「运维：…」） |
| ⑥ WIP 的某一格形状该不该推倒重来 | 逐格实测（§2 / §3 / §4 / §5） | ✅ **不该**。六条要求的形状**都是对的**，缺的只是「外面那一圈」（smoke 计数 / dist / 文档 / 取证） |

⚠️ **`progress.md` 本波不续**（控制者裁定，Task 3 也没续）⇒ **同意，不顶回**。

### 8.3 没按派单做的（**3 处**，逐个报）

1. **commit 切分与派单建议的不同**。派单建议 5 个：①把 WIP 带绿（后端 + 迁移 6 +
   `downgrade` 取证）②守卫 + 变异 ③前端 + dist + `gen:api` + openapi 五格
   ④smoke 三档 ⑤文档 + 报告。⚠️ 而实测 **WIP 的后端本来就是绿的**（§1.2），
   真正红的是**前端 smoke**；且 ②③④ 三件**不产生任何入库改动**
   （变异逐字节还原、dist 与 `gen:api` 产物都是 gitignored、smoke 是只读的），
   故「每个 commit 自洽」这个要求下**无法**按那五刀切。
   **实际切的 5 刀**：`e56bfe3`（前端 smoke 六红里的 6 条 + `UNKNOWN`）→
   `32d25c0`（两处过期计数散文；⚠️ 同时交代了 10 个文件的行尾归一 = **零 blob 变化**）→
   `d2e0111`（spec）→ `5f941bb`（README + 说明书）→ 本报告那个 commit。
   ⚠️ **第一个正式 commit 确实把 WIP 带绿了**（`e56bfe3` 之后 smoke 三档全绿、
   pytest 1753 全绿）—— 只是「带绿」的对象是**前端**而不是后端。
2. **`schema.d.ts` 刻意没有归一成 CRLF**（§6.3 / §10）：派单把它列为**特例**，
   而 `gen:api` 每跑一次就把它写回 LF ⇒ 归一它是无谓的 churn。
3. **`backend/pe_demo.db` 我没有删**（它实测**存在**，1 642 496 B）。
   ⚠️ 派单的禁区清单里只有 `backend/pe.db`（实测 **False**）与 `backend/data/seed/`
   （实测 **0** 文件）；`pe_demo.db` 是 `app.main.DEMO_DB_URL` 那一份**正常**的演示库、
   已 gitignore（`git ls-files` **0** 命中），⚠️ 且它的 `LastWriteTime` 实测是
   **2026-10-17 18:51:56**（= **本波开工之前**，⚠️ 不是我建的）。删它不在派单范围里，
   故**不动**（如实报）。

### 8.4 待清扫（**2 条**，⚠️ 都**已登记进 §15**，不占本报告的账）

* **B9** · `bind_token` 是**第五张**单调增长的表，而 `retention.py` 只清四张
  （⚠️ 它装的是**凭据台账**，故窗口应当与写审计同档 = **不少于 1 年**，
  而**不是**读审计那 90 天；且「只清**已过期且已用过**的行」是更保守的判据）。
* **D7** · 绑定令牌**没有撤销端点**：发错了只能重签，而旧的那一张最多再活 7 天。
  ⚠️ 要做得先裁「撤销是让它**不能用**（加 `revoked_at` = 迁移 7）还是把行**删掉**
  （= 抹掉一条凭据台账，与 B9 同族）」，且新增的那一档判定**同样要排在验秘密之后**
  （否则就是一个新的枚举信号）。

### 8.5 关切（**4 条**，给控制者 / 下一波）

1. ⚠️⚠️ **§8.1 那个中间态**（Critical 级，**要立刻收尾**）。
2. **pytest 的四文件组合 quirk**（§7.4）：`fixture 'client' not found`，
   ⚠️ **预存**（换成本波没碰过的 `test_auth_api.py` 同样报），
   两个正规调用面都绿。⚠️ 它会让「跑一个子集」这个动作给出**假红**，
   下一个人容易误判成自己改坏了。要不要治由控制者裁定（治它要动 `tests/` 的
   conftest 布局）。
3. **`bind_token` 上没有外键**（`login` 存的是学号/工号**原文**）：
   与 §1.2 第 8 条 `user_session.subject_id` 逐字同一条取舍（多态外键在 SQL 里不存在）。
   ⚠️ 代价：签发之后账号被删掉，只能在**兑换那一刻**回查 subject 行时才发现，
   而那一档**刻意**与「令牌不正确」共用同一个 403（守卫
   `test_a_token_whose_target_vanished_is_refused_like_a_bad_token` 钉着）。
4. **一个账号可以同时持有多张未使用的令牌**（`outstanding` 只用于**提示**、不是闸门）：
   裁定不做的理由（拒发会让「学生把令牌弄丢了」卡住教务干事 7 天，而本波没有撤销端点）
   写进了 §13.26.8 第 3 条，⚠️ **不占台账编号**。

---

## ⑨ 最终验收

### 9.1 后端测试

| 格 | 基线（`main` = `8e7df10`） | 本波 | |
|---|---|---|---|
| 全量 `--no-cov` · **接手时**（WIP 原样） | 1728 passed | **1753 passed**, 1 warning in **289.29 s** | ✅ **+25**、**0 failed / 0 skipped / 0 error** |
| 全量 `--no-cov` · **本波改完之后** | — | **1753 passed**, 1 warning in **413.46 s**（⚠️ 那一遍与 smoke 并发跑，故慢） | ✅ **0 红** |
| 全量带 `--cov`（三个口径各跑一遍） | 1727 + 1 skipped | **1752 passed, 1 skipped**（三个口径**三次都是这个数**） | ✅ **+24 / +1 skipped** |
| `tests/api/test_bind_token.py` | 不存在 | **24 条**，单文件 **24 passed**（3.4–4.3 s） | ✅ |

### 9.2 覆盖率三口径**四格**（⚠️ 每格都是本波亲跑，`--cov-branch`）

| 口径 | 基线（Stmts / Miss / Branch / BrPart） | 本波 | Cover | |
|---|---|---|---|---|
| `--cov=app/domain` | 1268 / 0 / 376 / 0 | **1268 / 0 / 376 / 0** | **100%** | ✅ **逐字相同**（`app/domain/**` 本波累计 **0 diff**；583.90 s） |
| `--cov=app` | 7432 / 204 / 1792 / 116 | **7 615 / 209 / 1 836 / 119** | 96% | ⚠️ **变了，如实报**（638.73 s）；差值 **+183 / +5 / +44 / +3**，见下 |
| `--cov=scripts --cov=app.static` | 1172 / 217 / 336 / 49 | **1 172 / 217 / 336 / 49** | 80% | ✅ **四格逐字相同**（579.48 s；本波对 `scripts/**` 与 `app/static.py` 的**可执行语句**一格都没改） |

⚠️ **`Cover` 列不是基线**（spec §12 有裁定），本波照旧**只把四格当基线**。

⚠️ **第二口径那 +183 的账**（如实报，⚠️ 只报到「差值 + 逐模块**现值**」这一层）：
最大的一格是**新模块** `app\auth\bind_tokens.py` = **60 / 0 / 10 / 0 / 100%**
（⚠️ **一个 Miss 都没有**、**一个 BrPart 都没有**）。其余散在本波碰过的那几个
`app/**` 模块上，逐模块**现值**如下（`--cov=app --cov-branch` 亲跑）：

| 模块 | Stmts / Miss / Branch / BrPart / Cover |
|---|---|
| `app\auth\bind_tokens.py`（**新**） | **60 / 0 / 10 / 0 / 100%** |
| `app\api\routers\auth.py`（+3 个端点 + 开关） | 162 / 5 / 54 / 3 / 96% |
| `app\api\schemas\auth.py`（+5 个模型） | 57 / 0 / 0 / 0 / **100%** |
| `app\db\models\auth.py`（+`BindToken`） | 41 / 0 / 0 / 0 / **100%** |
| `app\auth\policy.py`（+`PURPOSE_BIND_TOKEN`） | 89 / 1 / 12 / 1 / 98% |
| `app\api\errors.py`（+`token` / `token_hash` 两个脱敏键） | 56 / 0 / 10 / 1 / 98% |
| `app\api\read_audit.py` | 67 / 2 / 8 / 0 / 97% |
| `app\api\audit.py` | 57 / 5 / 4 / 0 / 92% |
| `app\main.py` | 94 / 0 / 26 / 0 / **100%** |
| **TOTAL** | **7 615 / 209 / 1 836 / 119 / 96%** |

⚠️ 逐模块的**改前**值本波**没有**复跑（那要在 `main` 的 worktree 上再来一轮 10 分钟的
`--cov=app`），故这一格的账**只报到差值与新模块的现值**、不做逐模块的对账加法
（硬规矩 #39：没量的不讲成量了）。⚠️ 而**三个口径的 passed 数三次都是
`1752 passed, 1 skipped`**（那 1 条 skipped 与本波无关，基线上也是它）。

### 9.3 schema / 迁移 / 结构面

| 格 | 基线 | 本波（现量） | |
|---|---|---|---|
| **表数** | **29**（`sqlite_master` **30**） | **30**（`sqlite_master` **31**）；`Base.metadata.tables` = **30**；⚠️ 甲方那一份仍是 **29**（我没给它跑迁移） | ✅ +1 = `bind_token` |
| **迁移链** | **5 单头**（… → `03331a689ee4`） | **6 单头**：`migrations/versions` 下 **6** 个 `.py`；`alembic heads` 退出码 **0**、**1 个头** = `a1af54889103 (head)` | ✅ |
| **残差 diff** | **0** | **0**（`alembic check` → `No new upgrade operations detected.`，退出码 **0**；常驻守卫绿） | ✅ |
| **`downgrade` 真跑** | 迁移 5 跑过 | **迁移 6 跑过一整圈**（带 2 591 行数据；§5.2） | ✅ |
| 扫描面（`test_layering.py`） | **73** | **74**（pipeline 10 + db 14 + domain 18 + api 27 + auth **5**）；反向那一圈 **46 → 47** | ✅ |
| `_MODELS_PUBLIC_BASELINE` | **33** | **33**（AST 现量；`BindToken` **不进**星号导入面） | ✅ 不变 |
| `_MODELS_SUBMODULES` | **8** | **8**（`models/` 下 **10** 个 `.py` − `__init__` − `_shared`） | ✅ 不变 |
| `_NON_PUBLIC_TABLE_CLASSES` | **15** | **16**（4 组：4 + 7 + **3** + 2；`auth` 那一组多了 `BindToken`） | ✅ +1 |
| 黄金用例 / **`RESOURCES`** / router 模块 | 14 / **23** / 8 | **14** / **23** / **8**（`app/api/routers` 下 **9** 个 `.py` = 8 个模块 + `__init__`） | ✅ 三格全不变 |
| `EXPECTED_*`（`test_migration_baseline.py`） | 30 / 279 / 12 / 21 / 41 / 32 | **31 / 288 / 13 / 22 / 41 / 33** | ✅（表 +1、列 +9、索引 +1、唯一 +1、外键 **+0**、CHECK +1） |

### 9.4 openapi（⚠️ 本波加了 3 个操作 ⇒ **五格全变**，逐个报新值）

| 格 | 基线 | 本波（`scripts/dump_openapi.py` 现量，退出码 **0**） | |
|---|---|---|---|
| **路径模板** | 75 | **77**（+ `/api/auth/bind-tokens` 与 `/api/auth/bind-with-token`） | ✅ |
| **操作** | 103 | **106**（+ 三个） | ✅ |
| **挂 security** | 85 | **87**（⚠️ **只 +2**：兑换那一档是**匿名**的） | ✅ |
| **GET** | 64（15 匿名 + 49） | **65**（**15** 匿名 + **50**） | ✅ 匿名 GET **不变** |
| **securitySchemes** | 3 | **3**（两个都挂既有的 `X-Teacher-Staff-No`） | ✅ 不变 |
| **字节 / sha256[:16]** | **428 074 B** / **`E58C0305788D84D1`** | **453 555 B** / **`5B4029FB98AC27E9`** | ⚠️ **变了，如实报**（+25 481 B = 三个新端点的 schema + description） |
| **未定型响应** | 24 | **24**（`GET /api/auth/bind-tokens` 有 `response_model=BindTokenPageRead` ⇒ 定型） | ✅ 不变 |
| **`expected`（特例清单）** | 27 | **29**（`assert len(expected) == 29` 绿；⚠️ 26 格单 scheme + 1 格元组 = 27？⇒ 实测 **29 条 / 28 个路径**，`bind-tokens` 一个路径占两条） | ✅ |
| **catch-all** | 0 | **0**（守卫绿） | ✅ |
| `crud` 那一圈 | **74**（⚠️ 散文写的是 76，§6.5 已勘误） | **75** | ✅ |
| spec 顶层 `security` | 无 | **无** | ✅ |

⚠️ **钉这些数的断言全部同步过**（本波实测四处）：
`tests/test_main.py` 的 `OPENAPI_CELLS`（77/106/87/65/15/3/24，前一位已改）·
`tests/api/test_prescription_api.py` 的 `expected`（29）与 `all_security`（87）·
`app/static.py` / `app/api/audit.py` / spec 里的**计数散文**
（`PROSE_OPENAPI_CELLS` 那 5 组正则**全绿** ⇒ 没有第三处过期）·
⚠️ **`frontend/scripts/smoke.mjs` 第 12 步那五格 = 本波改的**（前一位漏了，§1.2）。

### 9.5 前端

| 格 | 基线 | 本波 | |
|---|---|---|---|
| `frontend/dist` | 29 文件 / 695 914 B；`index.html` 2 729 B / `88E146D579856A3E` | **27 文件 / 707 713 B**；`index.html` **2 567 B / `141C673FD0BB4B57`**；重建时刻 **2026-10-18 18:01:23**（⚠️ 29→27 的对照实验见 §6.2） | ⚠️ **重建了**（派单授权） |
| 路由数 / `routes` 数组 | **16** / **20** | **16** / **20** | ✅ 不变 |
| `check:tokens` | 36 / 下界 25 | **36 个文件、0 offender、退出码 0** | ✅ |
| `check:dist` | 绿（56 / 1 387 647） | **绿、退出码 0**（56 个文件 / **1 422 299** 字符） | ✅ |
| `gen:api` | — | 重跑一次 ⇒ **`git status --porcelain` 为空**；`schema.d.ts` = `i/lf w/lf`（特例） | ✅ |
| **新增依赖** | 0 / 0 | **后端 0 / 前端 0**（`tests/test_dependencies.py` 绿；⚠️ 令牌那一层只用标准库 `secrets` / `dataclasses` / `datetime`） | ✅ |
| **smoke · dev 档** | 18 步 / **811** | **18/18 全绿 · 816 绿 / 0 红 · 退出码 0**（后端 8041 = 我起的 uvicorn + `PE_DB_URL` 指到 `%TEMP%\p08t4b\smoke_dev.db`；前端 = **我自己起的 5199 那个 vite**，`PE_API_TARGET=http://127.0.0.1:8041`；⚠️ 一次都没碰 5173） | ✅ **+5** |
| **smoke · 产品档** | 18 步 / **811** | **18/18 全绿 · 816 绿 / 0 红 · 退出码 0**（`serve.ps1 -Port 8042 -SkipBuild` + `PE_DB_URL` → `%TEMP%\p08t4b\smoke_prod.db`；health 实测 `tables:30`；⚠️ 一次都没查 node、一次都没调 npm） | ✅ **+5** |
| **smoke · 试用档** | 18 步 / **843** | **18/18 全绿 · 848 绿 / 0 红 · 退出码 0**（`trial.ps1 -Port 8043` + `PE_DB_URL` → `%TEMP%\p08t4b\smoke_trial.db`，⚠️ **不带 `-Reset`**，由 `trial.ps1` 自己灌；它自己建的 CSV 目录是 `pe_trial_csv_52864`，⚠️ **没碰** 8030 在用的 `pe_trial_csv_41684`；health 实测 `"trial":true` / `tables:30`） | ✅ **+5** |
| **smoke · 公网档** | 778（Plan 07 Task 8 时点） | **没跑** | ⚠️ 派单逐字禁止（⚠️ 而那条隧道今天本来就是死的：`Meta` 虚拟网卡把任何域名都答进 `198.18.0.0/15`） |

⚠️ **断言数只增不减**：811 → **816** / 811 → **816** / 843 → **848**（各 **+5**）。
⚠️ **判据一格都没放宽**（硬规矩 #92）：唯一改过期望值的那一拍是 §S2-①「匿名 POST 数」
**3 → 4**，而它的**前半句** `anonWrites.every((s) => s.includes('/api/auth/'))` **一个字都没动**
⇒ 它仍然同时钉住「23 个资源上一个匿名写都没有」。

### 9.6 依赖 / 禁区 / 入库面（⚠️ 每格都是本波亲跑）

| 格 | 判据 | 本波实测 | |
|---|---|---|---|
| 四个数据指纹 | `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` / `E48E3AC82BB45BB7` | `national_standard_2014.csv` **21 412 B → `D2C8E539E2FA0029`** · `exercises.yaml` **23 247 B → `5394B37F01DAC9AC`** · `exercise_equivalence.yaml` **8 245 B → `822CB86A5E998301`** · `alert_rules.yaml` **6 037 B → `E48E3AC82BB45BB7`** | ✅ 四个**逐字不变** |
| 18 个模板指纹 + 入库文件 | 18 / 24 | `data/prescription/*.yaml` = **18** 个、合计 **123 848 B**；`git ls-files -- backend/data` = **24** | ✅ |
| `git diff 8e7df10 HEAD -- backend/data` | 空 | **空**（⚠️ 工作树对 HEAD 也是空） | ✅ |
| `backend/pe.db` | 不得存在 | **False** | ✅ |
| `backend/data/seed/` | **0** 文件 | **0** | ✅ |
| 八处 gitignore 项 | 未入库 | `git ls-files` 对 `pe.db` / `pe_demo.db` / `pe_trial.db` / `backend/backups` / `frontend/dist` / `tools` / `.trial` / `dist-pack` **各 0 命中** | ✅ |
| 七份 manifest + `.gitattributes` + `.gitignore` + `alembic.ini` | 一个字都不许改 | `git diff 8e7df10 HEAD --` 逐个跑：`backend/pyproject.toml` / `frontend/package.json` / `frontend/package-lock.json` / `.gitattributes` / `.gitignore` / `backend/alembic.ini` **各零 diff** | ✅ |
| `backend/backups/` 里控制者那份 | 别删、别入库 | **仍在**：`pe_trial-pre-migration5-20261017-201257.db` = **1 589 248 B** / `68F299423D312CC6`；⚠️ 未入库（`backups/` 那一格 `git ls-files` = 0） | ✅ |

### 9.7 文档的三个口径

| 文件 | 工作树 bytes / lines / sha256[:16] | 入库 blob bytes / sha256[:16] | 行尾 |
|---|---|---|---|
| **spec** | **955 443** / **9 265** / **`CBCA4037B118BF81`** | **946 178** / **`E63C85C4437FBF30`**（git blob id `4d5b5980c18885d636ee3958ab4976bf0e2c47c3`） | 全 **CRLF**（**9 265**）、**0** 裸 LF、**0** 裸 CR、无 BOM |
| **甲方试用说明书** | **34 385** / **179**（上限 **200**） | **34 206** / **`3F0CD86BBE48E02D`** | 同上 |
| **README** | **13 189** / **186** | **13 003** / **`58F209DD3418260D`** | 同上 |

⚠️ spec 的「工作树 − blob」差值 = 955 443 − 946 178 = **9 265** = **恰好等于 CRLF 行数**
（那正是「`Document/**` 的工作树字节 ≠ blob 字节，按设计」的可执行形式）。
⚠️ **两个口径怎么算的**（⚠️ 用 `main` 复核过这套算法本身）：「工作树」那一格是磁盘字节的
sha256[:16]；「入库 blob」那一格是**把 CRLF 折成 LF 之后**那一份字节的 sha256[:16]
（⚠️ **不是** git 的 object id）。复核：`git cat-file blob main:<spec>` 实测
**915 085 B / 0 个 CRLF / 8 968 个 LF / sha256[:16] = `369730DB152CF882`** ——
与派单给的基线**逐字相同**，故本波报的 `E63C85C4437FBF30` 与它是同一个口径。
⚠️ 三份的「工作树 − blob」差值各自**恰好等于**自己的 CRLF 行数
（spec 9 265 / README 186 / 说明书 179），⚠️ 而三份的 `git hash-object`
都**逐字等于** index 里那一份（`4d5b5980…` / `9279fd60…` / `2c689d73…`）。
⚠️ **双向逐字节可逆已亲验**：正向 `git hash-object` == index blob（`4d5b5980…`）；
反向 `git checkout-index -f --prefix <空目录>/` 出来的那一份 == 工作树，
**955 443 B 逐字相同**（实测 `True`）。

**spec 改了什么**（§8.2 的口径落地）：

* **新增 §13.26**（八小节，照 §13.24 / §13.25 的体例）：三个新端点 · 令牌的形状与分隔符 ·
  哈希口径与它的唯一所有者 · 有效期/单次使用/不自动登录 · 限流怎么接上同一条 `3/15/60`
  （含时延签名）· **§13.26.6 那一句必须念的实话** · 迁移 6 与它的 `downgrade` ·
  **§13.26.8 那四件刻意不做的事**。⚠️ 一个数都不抄第二份（四格常量、TTL、阈值
  一律**指向** `bind_tokens.py` 与 `policy.py`）。
* **§1.2 第 4 条**：⚠️ **没有划掉**（它今天仍然成立），在末尾**追加**一段
  「**已给出收掉它的手段，而 ⚠️⚠️ 缺省仍然开着**」，⚠️ 历史原文**逐字保留**。
* **§13.15 交付须知第 4 条**：同上（**不划掉**），并写明「**念给甲方时请照这一句念**：
  今天**默认**的形状与上一波**逐字相同**；要真的收掉它，请在起服务之前设
  `PE_ALLOW_SELF_BIND=0`」；⚠️ Task 15 那一次的两条链实测**逐字保留**为历史，
  另加本波的两档实测与三格实话。
* **§15 台账 41 → 43 条在册 / 7 组、已划掉仍 14 条**：补 **B9** 与 **D7**
  （⚠️ 两个号都逐个核过**没被占用**：B 组用到 B8、D 组用到 D6；
  ⚠️ 现量复核 = A3 + B9 + C5 + D7 + E3 + F10 + G20 = **57** 条 −
  **14** 条划掉（B1/B2/B3/F3/F7 五条行首 `~~` + G 组 9 条）= **43** 在册 ✓）；
  **划掉 0 条**（理由逐字写在那一段里：开关缺省仍开）。

**说明书改了三处**（⚠️ **179 行**，上限 200；无内部术语、无写死的公网主机名、无 `&&`）：
§4 路线三加**第 6 步**（怎么签发，⚠️ 并如实写明「**试用库上这一格签发不出去**」——
63 个账号都已绑定，而它拒发给一个已绑定的账号）· §5 `/bind` 那一行**追加**
「这一页现在有两档」（⚠️ **原话仍然是真话**，故不删）· §6 须知 ② 改成
「**有了收掉它的手段，而缺省没有收**」+ 三格实话。

**README 加了一节**「运维：绑定口令的两条路（⚠️ 自助绑定**缺省仍然开着**）」：
一张两行的表 + 一段 `PE_ALLOW_SELF_BIND=0` 的命令 + **五句实话**。

### 9.8–9.13 收尾（逐个复核）

* **9.8 `progress.md`**：⚠️ **本波不续**（控制者裁定，Task 3 也没续；那是结案波的活）。
  ⚠️ **我同意，没有顶回**。
* **9.9 我自己起的进程全部已停**：8041（uvicorn，前后起了三次）/ 5199（vite，起了三次）/
  8042（`serve.ps1` 产品档）/ 8043（`trial.ps1` 试用档）—— 收尾用一份**白名单**脚本
  （只允许 8040–8059 与 5199，故 8030 / 5173 / 8000 结构上碰不到）逐个量，
  实测 **`REMAINING_LISTEN_IN_WHITELIST=`（空）**；⚠️ 最后又用
  `Get-NetTCPConnection -State Listen` 全表扫了一次 8040–8059 与 5199，
  实测 **`(none)`**。
* **9.10 不是我们的进程一个都没动**：⚠️ **收尾时逐个 `tasklist` 又量了一遍**，
  六个受保护 PID **全部仍在**：`29848 python.exe`（甲方试用档 uvicorn，34 204 K）·
  `31576 cloudflared.exe`（37 096 K）· `43520 node.exe`（vite 5173）·
  `38900 node.exe`（`npm run dev`）· `14368 node.exe` · `16404 node.exe`
  （两个 `@deepseek-ai/dsh web`）。⚠️ 全程**一次都没杀/没重启** 29848 与 31576、
  **没** `-Reset`、**没**写 `pe_trial.db`（⚠️ 它的 `LastWriteTime` 收尾实测仍是
  **2026-10-17 20:13:51**、字节与 sha256 与开工时**逐字相同**）、
  **没**对它跑过一条 `alembic`，对它**只发过匿名 GET**（§8.1 那九发）。
* **9.11 `%TEMP%\p08t4b`（我的探针目录）已删净并复验**：删除**之后**逐个
  `Test-Path` 实测 `p08t4b` = **False**、`p08t4b_rev`（反向可逆复核用的空目录）= **False**、
  `pe_trial_csv_52864`（**我那次** `trial.ps1` 建的 CSV 目录）= **False**、
  `p08t4b_pytest0.txt` = **False**；收尾时 `%TEMP%` 下 `p08t4b*` 的通配实测**0 命中**
  （⚠️ 最后那一份收尾复核脚本本身也删了）。
  ⚠️ **没删的三样逐个复验仍在**：`p07ctl` = **True**、
  `pe_trial_csv_41684`（8030 那个服务**正在用**的 `PE_CSV_DIR`）= **True**、
  `pe_tunnel_8030`（活隧道的日志目录）= **True**；⚠️ 且 `%TEMP%` 下 `pe_trial_csv_*`
  的通配收尾实测**只剩 `pe_trial_csv_41684` 一个**。
  ⚠️ 一格如实记：`trial.ps1` 说自己「**退出时**才删那个 CSV 目录」，而我是用
  `StopCommand` 停的它 ⇒ 它**没来得及**删，故 `pe_trial_csv_52864` 是**我手工删的**。
* **9.12 收尾五格**：见 §1.4 那张表的右半边（⚠️ 格 4 是**被授权的重建**、
  格 1/2/3/5 **逐字未变**）。
* **9.13 commit**：`e56bfe3` → `32d25c0` → `d2e0111` → `5f941bb` → 本报告那个 commit。
  ⚠️ **没有 push**（⚠️ 本仓**有** `origin` = `https://github.com/studyworkQAQ/Physical_Education_IMS.git`，而收尾实测 `main` 仍是 **`8e7df10`**、`git worktree list` 只有主工作树一行、`git status --porcelain` **空**）；⚠️ 那个 WIP（`1751bbe`）**原样保留**在
  分支上（**没有** revert / cherry-pick / rebase）。

---

## ⑩ 行尾复核（⚠️ 逐个被改文件；判据是**双向逐字节可逆**，不是「工作树 == blob」）

**口径**：spec 与 `Document/**/*.md` = **CRLF**（`attr/text eol=crlf`）、
`.ps1` = **CRLF + BOM**（本波**一个 `.ps1` 都没改**）、
`.py` / `.ts` / `.mjs` / `.vue` 工作树 = **CRLF**（入库 blob = **LF**，`attr/` 为空、
靠 `core.autocrlf=true`，实测 `git config core.autocrlf` = **`true`**）、
`.superpowers/**` = **LF**（`-text`，工作树 == blob）。

⚠️ **每改完一个文件当场核一次**（一律走**二进制模式**的 Python 脚本，
`%TEMP%\p08t4b\{normalize_eol,edit1,edit2,edit3,edit_spec1,edit_spec2,edit_docs,m8,mutate}.py`；
⚠️ 一次都没用编辑工具直接改仓库文件，也**一次都没用** `sed`/`awk`/heredoc）。

| 文件 | 接手时 | 本波之后 | 双向可逆 |
|---|---|---|---|
| `Document/…设计spec.md` | `i/lf w/crlf attr/text eol=crlf` | **同**（955 443 B / 9 265 CRLF / **0** 裸 LF / **0** 裸 CR / 无 BOM） | ✅ **亲验**：正向 `hash-object` = `4d5b5980…` == index blob；反向 `checkout-index` 到空目录 == 工作树（955 443 B 逐字相同） |
| `README.md` | `i/lf w/crlf attr/` | **同** | ✅ 差值 == CRLF 行数 |
| `Document/…甲方试用说明书.md` | `i/lf w/crlf attr/text eol=crlf` | **同** | ✅ 差值 == CRLF 行数 |
| `frontend/scripts/smoke.mjs` | ⚠️ **`w/mixed`**（104 个裸 LF） | **`w/crlf`**（0 裸 LF） | ✅ **blob 一个字节都没变** |
| `frontend/src/views/admin/ResourceIndex.vue` | `w/crlf` | `w/crlf` | ✅ |
| `frontend/src/api/generated/schema.d.ts` | ⚠️ **`w/lf`**（派单点名的**特例**） | **`w/lf`**（**刻意不动**，§6.3） | ✅ 两份 `hash-object` 成**同一个 blob** |
| `backend/app/auth/bind_tokens.py` | ⚠️ **`w/lf`**（新增文件，工具直接写的） | **`w/crlf`** | ✅ blob 未变 |
| `backend/tests/api/test_bind_token.py` | ⚠️ **`w/lf`**（1 294 个裸 LF） | **`w/crlf`** | ✅ blob 未变 |
| `backend/app/api/routers/auth.py` | ⚠️ **`w/mixed`**（**394** 个裸 LF） | **`w/crlf`** | ✅ blob 未变 |
| `backend/app/api/read_audit.py` | ⚠️ `w/mixed`（1） | `w/crlf` | ✅ |
| `backend/app/main.py` | ⚠️ `w/mixed`（11） | `w/crlf` | ✅ **亲验**：`hash-object` = `1017a4fac81a08db9c6b3be17d0b1c779d7a108c` == `HEAD:backend/app/main.py` 逐字相同 |
| `backend/tests/api/test_auth_api.py` | ⚠️ `w/mixed`（2） | `w/crlf` | ✅ |
| `backend/tests/api/test_column_widths.py` | ⚠️ `w/mixed`（9） | `w/crlf` | ✅ |
| `backend/tests/api/test_prescription_api.py` | ⚠️ `w/mixed`（24） | `w/crlf` | ✅ |
| `backend/tests/db/test_models.py` | ⚠️ `w/mixed`（21） | `w/crlf` | ✅ |
| `backend/tests/architecture/test_layering.py` | `w/crlf`（前一位**没碰**它） | `w/crlf` | ✅ |
| `.superpowers/sdd/…/task-4-report.md`（本文件） | — | **纯 LF / 无 BOM**（`-text`，工作树 == blob） | ✅ |

⚠️ **合计**：前一位留下 **10** 个文件的行尾不一致（8 个 `w/mixed` 共 **566** 个裸 LF +
2 个新 `.py` 是 `w/lf`），本波**全部归一**；⚠️ 而那一次归一**一个 blob 都没改**
（`git diff --numstat` 对那 10 个文件全为空、`git add` 之后 `git diff --cached --numstat`
也是空 ⇒ 它们在 commit 里**一个字节都不占**）。
⚠️ 本波**自己**没有再制造一次行尾事故（`git ls-files --eol` 逐个核过，
**0 个 `w/mixed`**）。

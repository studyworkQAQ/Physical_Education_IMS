# Plan 06 Task 12 实现者报告 —— 交付前收口波 · 第二批（**代码级** C1–C7）

> 分支 `p06/code-sweep`（从 `main` 的 **`5f0ce7b`** 起）。⚠️ **没有 push、没有碰 main**
> （main 上那 7 个待推 commit 由控制者重试）。
> 本波只做**代码级**的 7 件；纯散文/台账那一组是下一波（Task 13），**一件都没顺手做**。

---

## ① 环境

| 格 | 实测 |
|---|---|
| `node --version` / `python --version`（硬规矩 #73，开工第一件事） | **v24.19.0** / **Python 3.11.1**（无 venv） |
| `npm --version` | **11.17.0** |
| 起点 | HEAD = **`5f0ce7b`**，工作树干净 |
| 探针目录 | `$env:TEMP\p06t12\`（TEMP 里那约 118 个旧 `pe_*` 探针**一个都没删**，按派单 §6） |
| ⚠️ 5173 上那个 vite | **PID 20240**，**不是本波起的** → 按纪律**没杀它**；dev 档 smoke 用 **5174** + `PE_WEB_BASE` |
| 本波起过又停掉的进程 | `demo.ps1 -Port 8000`（**3** 次）、`npm run dev -- --port 5174`（**1** 次）、`scripts\serve.ps1 -Port 8020 -SkipBuild`（**1** 次）——**全部已停**（§⑧ 有复验） |
| 编辑姿势 | 新文件走 Write、改动走 SearchReplace；**每个文件改完当场用 python（二进制模式）归一 CRLF** 并核 `git ls-files --eol`（§⑨ 逐个报） |

---

## ② C1 · 客户端可控列的**宽度炸弹**

### ②-1 全面实测表（**整张表**，派单逐字要求）

**模型侧枚举**：`Base.metadata` 里声明了**有限宽度** `String(n)` 的列，实测 **68** 格
（`Text` / `JsonText` 那类无界列不计 —— 它们没有宽度可炸）。
**写入侧回溯**：从三个方向交叉 —— ① 请求的**元数据**（路径 / 路径段 / 请求头 / 方法令牌）；
② 请求**体**（9 个可写资源的 Create/Update schema）；③ 服务端产出（管道 / seed / 领域算式 / 常量）。

**A. 今天真会超的（5 格，改前实测）**

| 表.列 | 声明 | 值的来源 | 客户端可控？ | 改前实测最长写入 | 今天会不会超 |
|---|---|---|---|---|---|
| `audit_log.path` | 256 | `request.url.path` **原文** | **是（匿名）** | **401** | **会** |
| `audit_log.target` | 64 | `scope["path_params"]` **原文**（`target_of`） | **是（匿名）** | **400** | **会** |
| `audit_log.staff_no` | 32 | 开发档的 `X-Teacher-Staff-No` **请求头原文** | **是（开发档）** | **400** | **会** |
| `login_attempt.login` | 64 | `_key(purpose, 请求体的标识原文)` | **是（匿名）** | **505** | **会** |
| `semester.name` | 32 | `POST /api/semesters` 请求体 | **是（管理员）** | **500** | **会**（改前是 **201**） |

**B. 客户端可控、但改前就被判据夹住的（2 格）**

| 表.列 | 声明 | 判据（改前实测） | 结论 |
|---|---|---|---|
| `audit_log.method` | 8 | `should_record` 那道方法闸门在 `record` **之前**：一个 **400 字符**的方法令牌 → **405**、审计行**一行都不多**；实测 `method` 列的取值域 = `{POST, PATCH}`、最长 **5** | 有界（**不截断**） |
| `login_attempt.ip` | 64 | 三个调用方一律交 `request.client.host`（套接字对端），全仓**没有任何一处**解析 `X-Forwarded-For`；实测最长写入 **10**（`testclient`） | **今天不是**客户端可控；仍**防御性**设防（那一列的注释点名预留了 XFF 那个将来） |

**C. 派单点名要实测、而答案是「今天根本不存」的（`user_agent`）**

| 格 | 实测 |
|---|---|
| 全库有没有名字含 `agent` 的列 | **0**（`SELECT` 遍历 `Base.metadata` 全部 28 张表 × 全部列） |
| `user_session` 的列清单 | `id, kind, subject_id, role, created_at, expires_at, last_seen_at, revoked_at`（**8** 列，**没有** `ip`、**没有** `user_agent`） |
| `login_attempt` 的列清单 | `id, kind, login, ok, at, ip`（**6** 列，**没有** `user_agent`） |
| `audit_log` 的列清单 | `id, at, subject_kind, subject_id, staff_no, method, path, status, target`（**9** 列） |
| 端到端取证 | 真发一条 **2 000 字符 `User-Agent` + 2 000 字符 `Referer`** 的 `POST /api/auth/login`（403），然后把 `audit_log` 与 `login_attempt` 的**全部列**逐列扫探针（`"U"*20` / `"R"*20`）→ **0 命中**（守卫 `test_a_two_thousand_character_user_agent_leaves_no_trace_in_any_column`） |
| 处置 | ⚠️ 按控制者裁定**不新增审计列**（要纳入 UA 得先重裁 §13.9 那条隐私口径的边界）。已登记待清扫（§⑦ 第 1 条） |

**D. 请求体那一侧（类 4，15 格）** —— 从 `catalog.RESOURCES` 里 `writable=True` 的
**9** 个资源**推出来**（表 × 该表 Create/Update schema 上真实存在的字符串列），
不是手写清单：`body_composition.device`、`course_section.{grouping_mode,name,schedule_text}`、
`fitness_test_batch.{academic_year,source,timepoint}`、`semester.name`、
`student.{department,name,sex,student_no}`、`teacher.{name,role,staff_no}`。
⚠️ 实测：**全仓 `app/api/schemas/**` 里 `max_length` 出现 0 次**，故改前这 15 格
一律**无界**；`POST /api/semesters` 带一个 500 字符的学期名改前是 **201**、落库 **500** 个字符。
⚠️ 改前那一轮齐射里其余 POST 回 422 是**枚举校验器**（`one_of`）先响，不是长度校验。

**E. 服务端所有（类 5，41 格）** —— 逐表给了理由，全清单住在
`tests/api/test_column_widths.py` 的 `_SERVER_OWNED`（它是「这一格我核过了」的取证）。
其中三格值得点名：`student.password_hash` / `teacher.password_hash`（`hash_password`
的自描述串，实测**恒 90 字符**、与口令原文多长无关）、`user_session.id`
（`secrets.token_urlsafe(48)` = 64，另有既有守卫）、`class_session.rpe_token`
（`_new_rpe_token()` 截到 `RPE_TOKEN_LEN`）。
⚠️ 特例端点里唯一一处「身份派生」的写入是 `mini_test.entered_by`（类 3）：
`batch_mini_tests` 的**第一行**就是 `require_staff(session, staff_no)`，
故写进来的一定是 `teacher.staff_no` 上真实存在的值 ⇒ 有界（守卫量「本列 ≥ 来源列」）。

**F. 明确不在本波范围的一格（如实记）**：CSV 摄取路径（`app/pipeline/extract.py` /
`clean.py`）的字段值来自**甲方上游的导出文件**，不是 HTTP 客户端可控
（`POST /api/pipeline/run-daily` 是本模块唯一的写端点，**没有** `UploadFile` / `Form`，
`_csv_dir()` 读的是环境变量）。⇒ 已登记待清扫（§⑦ 第 2 条）。

### ②-2 截断标记的形状与理由

`app/db/width.py` 的 `OVERLONG_SUFFIX = "…[cut]"`（**6** 字符），
`truncate` 保留前 `width - 6` 个字符再接上它 ⇒ **总长恰好等于声明宽度**（派单逐字要求
「不许把总长推过声明宽度」）。四条理由：

1. **尾缀而不是前缀**：`audit_log.path` 要答「对**哪一个**做了什么」，信息全在**前**半段
   （`/api/students/12` 那一截）；限流键同理（`bind:` 那个前缀是「用途」那一维）。
2. **`…` 而不是 `...`**：一个字符顶三个，而在窄列上（`String(16)`）`width-6` 与 `width-8`
   差 12.5% 的可用信息。
3. **`[cut]` 而不是只留一个 `…`**：一个孤零零的 `…` 会出现在**真实数据**里
   （省号式缩写、复制粘贴的引文），于是「被截过」与「本来就有省略号」不可分辨。
4. **单一所有者**：标记的字面量只在 `app/db/width.py` 出现一次，三个收口点都经它。

### ②-3 `ip` / `method` / `subject_kind` 各自怎么处置

| 列 | 处置 | 理由 |
|---|---|---|
| `login_attempt.ip` | **哨兵** `<over:N>`（`overlong_sentinel`） | ⚠️ **顶回派单的「截断」**：截一个 IP 会得到一个**语法上仍像 IP 的假 IP**。哨兵形状 `<over:原文长度>` 里 `<`/`>` 不在 IP 的文本形式里、也不在本仓的工号/学号形状里 ⇒ 不可能被误读成真值；⚠️ 而它**保住了长度**（「送了 400 字符」与「送了 4 000 字符」是不同的探测强度） |
| `audit_log.staff_no` | **哨兵**（同上） | 同一类推到了工号上：那一格的用途是**指认一个人**，截断它 = 指认到一个不存在的人（一句假话），而哨兵是一句实话 |
| `audit_log.method` | **不截、不落哨兵**（先实测有没有校验：**有** —— `should_record` 那道闸门） | 截一个方法名只会造出一个不存在的方法；「哪些方法被记」的唯一所有者是 `should_record`（那一列连 DB 层的 CHECK 都刻意没有，理由写在列注释里） |
| `audit_log.subject_kind` | 同上（判据 = `AuditLog.SUBJECT_KINDS` + DB 的 `ck_audit_log_subject_kind`） | 取值域三档、最长 `anonymous` = 9 ≤ 16 |
| 请求体的 15 格 | **拒绝**（`ensure_fits` → `ValueError` → 422 `unprocessable_value`） | ⚠️ **顶回「截断」**：截断一个 `student.name` 会得到一个**看起来正常的假姓名**写进名册 —— 那是**数据损坏**，比拒绝一次请求坏得多 |

⚠️ 于是「一条守卫扫全面」不等于「一个动作治全部」：**四类四种处置**，
而「哪一列走哪一档」的决定写在**调用方**（语义在那儿），`app/db/width.py` 只持有
「宽度」这一件事的知识（标记形状 / 哨兵形状 / 怎么从模型读声明宽度）。

⚠️ **顶回派单的一处实现选择**：派单说的是「写入时按声明宽度截断 + 可辨识标记」，
实现者对**请求体的业务字段**与**有格式的身份/地址**两类改用了「拒绝」与「哨兵」，
理由如上（派单本身给了「顶回来并给出你的方案」的口子，并点名了 `ip` 那一格）。

⚠️ **另一处顶回**：不做全局 `before_flush` 钩子（看起来更「扫得全」）。三条理由：
① 钩子在 flush 时才跑，抛出来的是 `IntegrityError` 一族 → **409**，而「客户端送了超宽字段」
是请求校验错误、正确的码是 **422**（与 `one_of` 把枚举越界从 409 挪到 422 同一条口径）；
② 它会把三档处置压成一档；③ 它会连带管住管道与 seed（那些值来自仓库内的 YAML，
不是客户端），把一条关于**信任边界**的纪律铺到不需要它的地方。

### ②-4 端到端四格取证（运行时口径）

**(a) 内存库 + `TestClient`**（守卫 `test_an_overlong_volley_leaves_every_row_bounded_and_every_response_unchanged`）：
五发超宽齐射（400 字符路径 / 400 字符路径段 / 400 字符工号头 / 400 字符学号的匿名绑定 /
2 000 字符 UA 的登录）——

| 格 | 实测 |
|---|---|
| ① 业务响应码 | **404 / 422 / 403 / 403 / 403**，与改前**逐字相同**（⚠️ 本波**没有新增任何一个可区分的码**） |
| ② 审计行**存在** | **5 行**（五条请求各一行，一行都没被静默丢弃） |
| ③ 有界 + 带标记 | `path` = **256**（= 声明宽度）以 `…[cut]` 结尾；`target` = **64** 以 `…[cut]` 结尾；`login` = **64** 以 `…[cut]` 结尾且以 `bind:eeee…` 开头；`staff_no` = **`<over:400>`**（10 字符，`c` 一个都没混进去） |
| ④ `GET /api/audit-logs` 读得回来 | 管理员 **200**、`total == 5`，且响应体里那一格的 `path` / `target` / `staff_no` 与库里**逐字相同**（读路径没有第二次加工） |
| 汇总那一拍 | 齐射之后**逐列扫全库 28 张表**：实写长度 > 声明宽度的 = **0 格**（改前是 5 格） |

**(b) 真服务 + 真演示库**（`demo.ps1 -Port 8000`，然后直接读 `pe_demo.db`）：

```
POST  /<400 个 a>            → 404 ；audit_log#1  method=POST  path 长度 256  status 404  path 尾 'aaaaaa…[cut]'  target NULL
PATCH /api/students/<400 b>  → 401 ；audit_log#2  method=PATCH path 长度 256  status 401  path 尾 'bbbbbb…[cut]'  target 长度 64 尾 'bbbbbb…[cut]'
```
⚠️ 两行都**存在**（不是被吞掉），两格都**恰好等于**声明宽度且**带标记**。
产品档（`serve.ps1 -Port 8020`）上同样两发：404 / 401，形状一致。

**(c) 管理台审计页的 DOM（不溢出、不重叠）** —— ⚠️ **实测结论与派单的预设相反**：

改前 `smoke.mjs` 第 14 步的布局守卫在 `/admin/audit-logs` 上**红了 2 条**：

```
✗ admin-audit-logs：没有文本内容重叠 → td「/api/students/bbbbbb」与 span「405」、
                                       与 td「bbbbbbbbbbbbbbbbbbbb」各重叠 ratio 1（完全覆盖）
✗ admin-audit-logs：没有非故意的横向溢出 → scrollWidth 1927 / clientWidth 413（path 那一格）
                                          scrollWidth  484 / clientWidth 413（target 那一格）
```
成因：`.a-table td` 虽然写着 `white-space: nowrap; max-width: 340px; overflow: hidden;
text-overflow: ellipsis`，而 **`max-width` 在自动表格布局下对 `<td>` 不生效**，
一条 256 字符、**中间没有一个空格**的路径把那一格撑开了。
修法**不新写一条 CSS**：给 `path` / `target` / `staff_no` 三列（**恰好**就是三个
客户端可控的列）挂上**既有的** `.a-cell--wrap`（`styles/admin.css`：
`white-space: normal; word-break: break-word`）。⇒ **一条新 CSS 都没加、
一个色值裸值都没引**，`npm run check:tokens` 扫描面仍然 **36**（下界 25）全绿。
改后第 14 步 `admin-audit-logs` 那一条路由的三拍布局守卫（无文本重叠 /
无非故意横向溢出 / 整页无横向滚动条）**两档都全绿**。

### ②-5 守卫与定点变异

守卫 `tests/api/test_column_widths.py`（**13** 条）。形状是「**一张全覆盖的分类账** +
每类各自的牙」：五个类（`_REQUEST_METADATA` 5 / `_DOMAIN_BOUNDED` 6 /
`_IDENTITY_DERIVED` 1 / 类 4 推出 **15** / `_SERVER_OWNED` **41**）**两两不相交**、
且**并集 == 全库 68 格** ⇒ **加一列就必须回答**「它的值从哪来、由谁收口」。
⚠️ 期望侧的宽度一律经 `app.db.width.declared_width` **从模型读**，
**文件里没有一个宽度数字**（唯一出现的字面量是「灌多长」那一侧 = 被测侧，硬规矩 #35）。

**定点变异 7 处，逐个红**（跑完 sha256 复核 4 个文件**逐字还原**）：

| # | 变异 | 结果 |
|---|---|---|
| M1 | `audit.record` 的 `path` 不再截断 | **RED**（`AssertionError: 401`） |
| M2 | `width.truncate` 去掉标记（变成静默截断） | **RED**（`宽度 8 × 原文 9 截完是 'xxxxxxxx'：没有以 '…[cut]' 结尾 = 静默截断`） |
| M3 | `policy._key` 不收口 | **RED**（`AssertionError: 405`） |
| M4 | `crud.create_row` 去掉 `ensure_fits` | **RED**（`POST /api/semesters` 又变 201，响应体里那 500 个 `s` 原样落库） |
| M5 | `audit.record` 的 `staff_no` 改成截断而不是哨兵 | **RED**（`cccc…[cut]` ≠ `<over:400>`） |
| M6 | `crud.update_row` 去掉 `ensure_fits` | **RED**（PATCH 那一拍） |
| M7 | `audit.record` 的 `target` 不再截断 | **RED**（`AssertionError: 400`） |

---

## ③ C2 · `verify_password` 的迭代次数上下界（老终审 M6）

### ③-1 改前实测（逐格）

| 档 | 改前 `verify_password` 的处置 |
|---|---|
| ① 迭代数 **0** | `False`（既有 `< 1` 那一支） |
| ② 迭代数 **负数**（`-1`） | `False`（同上） |
| ③ 迭代数 **非数字**（`很多`） | `False`（`int()` 的 `ValueError` 被接住） |
| ④ 段数不对（**3** 段 / **5** 段） | `False`（`len(parts) != 4`） |
| ⑤ **空串** / `None` | `False`（`if not stored`） |
| ★ 迭代数 **1** + 按 1 次**正确重算**的摘要 | **`True`** ← 下界那一格的实证 |
| ★ 迭代数 **999999999** | **真跑 PBKDF2** ← 上界那一格的实证 |

⚠️ **五档畸形串改前就已经一律 `False`**，本波**一格都没改它们的处置**；
新增的只有两端。

**DoS 代价的量化**（不真跑 999 999 999 次，用三个取样点线性外推）：

| 迭代数 | 实测耗时 | 每次 | ⇒ 999 999 999 次 |
|---|---|---|---|
| 100 000 | 13.9 ms | 138.9 ns | **≈ 2.3 分钟** |
| 200 000 | 28.4 ms | 141.9 ns | **≈ 2.4 分钟** |
| 400 000 | 58.8 ms | 147.1 ns | **≈ 2.5 分钟** |

⚠️ **限流挡不挡得住**（派单点名要先实测）：`app/api/routers/auth.py` 里
`is_locked` 在 **520** 行、`verify_password` 在 **534** 行 ⇒ 锁定档**一次 PBKDF2 都不跑**。
故**已锁定**的账号不受影响，而**未锁定**的账号**第一发**就能触发。

### ③-2 上下界、唯一所有者、失效方向

| 格 | 落地 |
|---|---|
| 下界 | `PBKDF2_MIN_VERIFY_ITERATIONS = 100_000` |
| 上界 | `PBKDF2_MAX_VERIFY_ITERATIONS = 2_000_000`（= OWASP 600 000 的 **3.3×**，控制者裁定） |
| **唯一所有者** | **哈希模块自己**（`app/auth/passwords.py`）；⚠️ **没有**塞进 `policy.py`（那是限流的住址，而 `policy` 今天一个 `hashlib` 都不碰），⚠️ 也**没有**第二份 —— `iterations()` 与 `verify_password()` 都经同一个私有判据 `_iterations_in_bounds` |
| 失效方向 | 越界 → 回既有的 **401 `invalid_credentials`**（`verify_password` 回 `False`）。⚠️ **没有新增可区分的码**（理由与 Task 3 对 423/429 的改判逐字相同：新码就是枚举信号） |
| 日志 | 一条 **`WARNING`**。⚠️ 先实测这一档今天有没有日志通道：`passwords.py` 改前**没有** logger，而本仓**已有**一条既有通道（`logging.getLogger(__name__)`，`app/main.py` / `app/api/errors.py` / `app/api/audit.py` / `app/pipeline` 三处逐字同形）⇒ **用它、没有新建一个**。⚠️ 日志里**一个字符的 `stored` 都不放**（那个串含盐与摘要 = 一份凭据），只带算式名与迭代次数 |

⚠️⚠️ **两个界都是绝对值、与 `iterations()` 的当前配置无关**（本波的一处裁定）：
本模块的核心性质是「校验**不**依赖当前配置」（既有守卫
`test_verify_uses_the_iterations_recorded_in_the_string_not_the_current_setting` 钉着它）。
若写成 `min(常量, iterations())`，一次「把迭代次数抬上去」的运维动作会让**全部既有口令
当场失效**（形状是「所有人都登录不了」）—— 那正是模块 docstring 第一节要防的失效。
⚠️ 而「运维把环境变量设到界外」那一档改由 `iterations()` **自己**挡
（`ValueError` → 422，与既有的坏值口径同一条链）：于是「配置出一个自己验不过的哈希」
在**第一次哈希**上就响。

⚠️ **下界 100 000 与演示库那一个值逐字相同**（`demo_bootstrap.py` 的
`DEMO_PBKDF2_ITERATIONS`，spec §13.4.3 也记着它）—— 那不是巧合而是**约束**：
演示库的 63 个口令必须在界内，否则 `demo.ps1` 灌出来的库一个账号都登不进去、
`smoke.mjs` 会全灭。守卫用 **AST** 读那个脚本的常量（不 import 它），
故「把下界抬到 200 000」会当场红。

⚠️ **连带改一格测试环境（如实记）**：`tests/conftest.py` 的 `PBKDF2_ITERATIONS`
从 **1000** 抬到 **100000**（1000 在新下界之外 ⇒「测试进程自己哈希出来的串自己验不过」）。
取 100 000 是实测出来的：① 它恰好等于演示库那一个值；② 全套件 **159.5 s → 161.7 s**
（**+2.25 s / +1.4%**，本机亲跑，因为碰口令的调用实测只有约 **45** 次）。
两者的耦合由 `test_the_test_suite_runs_at_an_iteration_count_the_verifier_admits` 钉住。
⚠️ 连带改了 3 处**因此变成假的散文/字面量**：`test_passwords.py` 的
`iterations()` 那一档的 `1234` → `123456`、「串里那一段」那一档的
`1234/4321` → `123456/654321`（⚠️ 换数字**不改那条守卫的牙**：两个值都界内且互不相等，
故「用了配置值」与「用了串里那一段」仍给出两个不同摘要），以及
`test_auth_api.py` 两处「设成 1000 / 一次哈希约 1 ms」的说明。

### ③-3 守卫与定点变异

`tests/auth/test_passwords.py` **13 → 17 条**。新增四条：界外五档一律拒**且一次
PBKDF2 都不跑**（⚠️ 判据是替身的**调用次数**、不是耗时 —— 少了这一拍「把上界去掉」
仍然绿，因为界外的串摘要对不上、返回值一样是 `False`；⚠️ 替身带一个**安全阀**：
界外那几档不真算，故变异体**当场红在计数上**而不是红在 2.3 分钟的超时上）、
越界那一条 `WARNING` 里**没有任何凭据的一段**（逐格扫整串 / 盐段 / 摘要段 / 明文）、
两个界装得下**生产缺省 + 演示库那一个值**、测试进程的配置值落在界内。
⚠️ 两个阈值**按字面量钉**（口径与 `test_policy.py` 对 `DEFAULT_MAX_FAILS` 那三格相同：
阈值是**决定**、不是算式）。

**定点变异 5 处，逐个红**（跑完 sha256 复核**逐字还原**）：

| # | 变异 | 结果 |
|---|---|---|
| M1 | `verify_password` 的界退回改前的 `< 1` | **RED** |
| M2 | 去掉那一条 `WARNING`（静默拒绝） | **RED** |
| M3 | `iterations()` 不判界 | **RED** |
| M4 | 下界降到 **1** | **RED** |
| M5 | 上界抬到 **10 亿** | **RED**（`迭代次数 999999999 越界，却真的跑了 PBKDF2 [999999999, 999999999]`） |

⚠️ 顺带修一格事实：`SALT_BYTES` 的注释里「整串长度 = 89」实测是 **90**
（那个 21 个字符的前缀被数成了 20）。

---

## ④ C3 · 会话恢复那一帧 `ANONYMOUS`（老终审 M7）

### ④-1 实测方法与结论（**两档分别量**）

方法：`smoke.mjs` 第 14 步新增 §C3 —— 用 CDP 的 **`Fetch` 域把 `/api/auth/me`
这一个请求扣住**，于是「me 还没回来」那一帧会**停在那里**、可以从容取样。
⚠️ 刻意**不**用「把整个网络拖慢」：那会连 JS 产物一起拖住，取样到的就是
「什么都还没挂载」的白屏，证明不了任何事（本机实测踩过，那一拍因此加了
「取样不是白屏」的断言）。⚠️ 判档**复用**第 14 步上面那 16 条路由已经算出来的
`TIERS_SEEN`（档是**服务**的属性、不是某一帧 DOM 的属性）。

| 档 | `me` 被扣住时那一帧的 DOM | 结论 |
|---|---|---|
| **产品档**（`serve.ps1`，同源 8020） | **已挂载**（会话条画出来了）；改前 `roleLabel` 画 **`ANONYMOUS`**、`session.summary` 说 **「未登录」**、页脚把同一句抄一遍 | **会被看见** ⇒ **修** |
| **dev 档**（vite 5174） | **根本还没挂载**（DOM 停在 `index.html` 的占位上） | 那一帧**结构上不可达**（`main.ts` 的 DEV 那一支先 `await ensureRestored()` 再 `mount()`） |

⚠️ 而 M7 的**另一半**（「已登录的用户被弹去 `/login` 再弹回来」）在**两档都不可达**，
且**前几波已经修掉了**：`router.beforeEach` 在任何判定之前 `await session.ensureRestored()`，
而 `status` 的初值是 `'unknown'` 不是 `'anon'`（`stores/session.ts` 文件头末节逐字写了这条口径）。
⇒ **本波给那一半加守卫把它钉住**（否则下一个人把 `await` 挪走是静默的）。

### ④-2 改了什么

给「我是谁」那两格一个 **pending 档**（判据的唯一住址 = store 新加的 `isPending`
getter，`= status === 'unknown' || status === 'restoring'`）：

| 位置 | 改前 | 改后 |
|---|---|---|
| `session.summary`（页脚 + 会话条都读它） | `'未登录'` | `'身份未确认…'` |
| `IdentitySwitcher.vue` 的 `roleLabel` | `'ANONYMOUS'` | `'PENDING…'` |

⚠️ **不用 `v-if` 白屏**（那也是一帧坏体验）、**不藏报头**（布局跳动）、
**不阻塞首屏**（会把「后端没起」变成白屏）—— 即 spec §13.4.2 那三个被否掉的方案
**一个都没用**，而这是**第四个**方案：报头照旧无条件渲染，只是那一帧**不说假话**。
⚠️ 措辞与本仓既有的 pending 口径逐字同族（`读取中…` / `加载中…` / `登出中…` /
`名单加载中…`）⇒ **一条新 CSS 都没加**、`check:tokens` 一格未退（扫描面仍 **36**）。
⚠️ `isPending` **刻意不等于** `!isAuthenticated`：「问过了、答案是匿名」那一档
**照旧**说「未登录」/ 画 `ANONYMOUS`（那是真话）。

### ④-3 守卫（两半，两档都跑）

* **运行时**（`smoke.mjs` 第 14 步 §C3，产品档 **8** 拍 / dev 档 **7** 拍）：
  前提（`me` 真的被扣住）、认得出构建档、①没有 `ANONYMOUS`、②没有「未登录」、
  ③（dev）应用还没挂载 / ③④（prod）已挂载且说的是 `PENDING…` + `身份未确认…` +
  `会话状态 restoring`、⑤没有被弹去 `/login`、⑥放行后落定成 `authed`
  且 pending 那两句都消失、⑦落定后是 `ADMIN` + `管理员 T0003`、
  ⑧**反空转**：清掉 cookie 再访 `/login`，匿名那一档**照旧**说「未登录」/ 画 `ANONYMOUS`
  （少了本拍，「把 pending 判据写成恒真」会让上面几拍全绿）。
* **结构面**（`smoke.mjs` 第 17 步新增 ⑧，**6** 条）：初值是 `'unknown'` 不是 `'anon'`；
  `await ensureRestored()` 的下标 **<** 第一个 `session.isAuthenticated` 的下标；
  `=== 'restoring'` 这个谓词在 `src/**` 的**代码**里**恰好 1 处**（= `isPending`，
  扫描面 ≥ 30 个 `.vue/.ts` 反空转）；`isPending` 那个 getter 真的存在且两档都算；
  两个消费者都走它；两句真话都还在。⚠️ 第 17 步的标题因此从「静态守卫 7 条」改成 **8 条**。

⚠️ **顶回 spec**：§13.4.2 那一段此前逐字写着「**它不是 bug，请不要去『修』它**」。
本波顶回并改写了那一句（原文的三个替代方案照留），理由：那三个方案否的是
「抄进 `localStorage` / 藏起报头 / 阻塞首屏」，而「那一帧不许说谎」是第四个方案、
那三个代价一个都不付。已在 spec §13.4.2 与 §13.13.3 逐字记录。

---

## ⑤ C4–C7 逐条

### C4 · 坏引用（派单点了 2 处，实测 **12** 处）

**全仓清单**（扫描面 = `backend/` 下全部 `.py`；引用总数 **5 055** 条，
按角色：`func` 2 861 / `data` 748 / `mod` 687 / `class` 541 / `attr` 195 / `meth` 23）：

| # | 位置 | 坏在哪 | 处置 |
|---|---|---|---|
| 1 | `tests/api/test_crud.py:591` | `…admit_the_read_tiers` 少了 **`four`**（派单点名的第 1 处） | 改成真名 |
| 2 | `app/api/routers/catalog.py:177` | 同上（派单点名的第 2 处；⚠️ 它用的是**裸双反引号**、不是 `:func:` 角色 —— 派单写的行号是 172，实测在 **177**） | 改成真名 |
| 3 | `tests/api/test_audit_api.py:627` | `test_anonymous_read_writes_no_audit_row` 少了 **`an_`** | 改成真名 |
| 4 | `tests/conftest.py:15` | `app.auth.passwords.PBKDF2_ITERATIONS` —— 那个模块里**没有**这个名字（真名是 `PBKDF2_ITERATIONS_ENV_VAR` / `PBKDF2_DEFAULT_ITERATIONS`） | 改成真名 |
| 5 | `app/api/routers/dashboard.py:34` | `…dashboard_and_the_stored_report_agree…` → 真名是 `…dashboard_agrees_with_the_stored_report…` | 改成真名 |
| 6 | `app/db/models/organisation.py:104` | `test_the_credential_columns_never_appear…` → 真名是 `test_no_credential_column_appears…` | 改成真名 |
| 7 | `scripts/dump_openapi.py:47` | `test_the_offline_openapi_dump_never_creates…` → 真名是 `test_running_the_dump_script_as_a_subprocess_never_creates…` | 改成真名 |
| 8 | `tests/db/test_models.py:804` | `test_plan02_and_plan03_tables_stay_out…` → 真名是 `test_new_tables_stay_out…` | 改成真名 |
| 9 | `tests/test_serve.py:1126` | `…prints_the_prod_tier_reminder` → 真名多一段 `_instead_of_offering_a_switch` | 改成真名 |
| 10–12 | `tests/api/test_column_widths.py` ×2、`app/auth/passwords.py` ×1 | **本波自己写坏的**（一个指着自己没写出来的常量、一个指着改了名的助手、一个多写了一个 `both_`） | 改成真名 ⚠️ 如实记：新守卫**当场**把它们抓出来了 |

⚠️ 另有 **8 处 / 6 个名字**是**刻意**提到的历史名或预留名（「改前它叫 X」/
「本条替代了 X」/「这里原有一条 X」/「原文叫 X」/「这个名字是留给下一个人看的」），
按「绑时点的历史陈述不要改成今天的样子」那条纪律**一律不改**，
逐个连同理由登记进守卫的 `_HISTORICAL` 清单。

**守卫**（`tests/architecture/test_docstring_references.py`，**3** 条，成本实测 **4.5 s**
= 全套件的 2.6%）：主判据 + 历史名清单**反腐烂**（每个名字确实还被提着、且确实**不在**
索引里 ⇒ 「往清单里塞一个真名字来骗绿」做不到）+ 解析器对**已知反例**会报
（反例取的就是那 12 处改前的原文，绿档是它们各自的真名 + 三格「形状麻烦而名字是真的」：
类属性 / 标准库 / `starlette.routing.Router.not_found`）。

⚠️ **派单问「值不值得加」—— 没有顶回，但第一版被实测否掉了**：
「把 `A.B.C` 折成 `import_module(A.B)` + `getattr(C)`、裸名折成本模块有没有它」那一版
在 5 055 条上报出 **401** 处「解析不到」，而真坏的只有 6 处（**信噪比 1.5%**）。
假阳性来自**六族**：类属性（`AuditLog.SUBJECT_KINDS`）/ 标准库模块（`pathlib`、`zoneinfo`）/
内置名（`ValueError`）/ Sphinx 的**相对**模块名（`.ops`，实测 **21** 处）/
Sphinx 的 `~` 前缀 / 需要**逐段** import 的 `starlette.routing.Router.not_found`
（⚠️ 本机实测 `hasattr(Router, "not_found") is True`，它是真的）。
一条恒红 400 处的守卫会被下一个人立刻调松或删掉 —— 那比没有守卫更坏。
故判据换成**六级放行**（`…` 省略号前缀匹配 → `~` → 相对模块名按包补全 →
逐段 import → 全仓 AST 名字索引（约 1.7 万个名字）/ 内置 → 测试文件名主干），
实测**误报 0**。
⚠️ **代价（如实记）**：名字索引那一档是**宽松**的，故本条守的是「**凭空不存在**的名字」
（那 12 处全是这一类），**不守**「名字存在但指的是另一个东西」（那要理解语义）。
⚠️ 定点变异 1 处红（往 `app/db/width.py` 塞一条指不到真名的引用 →
主判据点名报出 `app/db/width.py:116`）。

### C5 · `_enrolled_sections` 一次请求查两次 → 收一次

**实测是哪条路径**：`app/api/routers/feedback.py` 的 `normalized_scores`（1324 行）与
`normalized_scores_self`（1487 行）两个端点，各自**先**为了「行级裁班」调一次
`_enrolled_sections(session, semester_id)`，**再**调 `_normalized_sections` ——
而后者内部（1034 行）又调了同一个函数、同一个 `semester_id`。
⇒ 那两条路由一次请求查**两遍** `enrollment`；第三条路由
（`dashboard.teacher_student_normalized`）经 `_normalized_self_body` 只查一遍。

**两次结果恒等吗**：恒等 —— 同一个 `semester_id`、同一个函数、中间**没有任何写入**
（三个端点全是 GET，而 GET 一律不写库；`should_record` 也不记它们）。

**收法**：把 `sections_of` 变成 `_normalized_sections` 与 `_normalized_self_body` 的
**必填**入参，三个端点各自查一次、交进去；`dashboard` 那一侧因此多 import 一个
`_enrolled_sections`。⚠️ **刻意不给 `None` 缺省**：给了的话「忘传就自己查」这一支
会**静默**地把双查询放回来。⚠️ **不引入缓存/请求级状态**（派单点名可以顶回的那一格）：
一次函数传参就够了，加一层缓存是给「同一个 Session 上的同一条 SELECT」再造一个所有者。

**取证**：既有守卫 + smoke 复跑 —— `tests/api` + `tests/architecture` **311 条全绿**、
全套件 **1561 passed + 1 skipped 全绿**、smoke **两档全绿**（第 13 步那 72 条断言
逐字钉的就是这三个端点的响应体，一条都没变）。

### C6 · `feedback.py` 只被散文引用的 import（派单说 3 个，实测 **5** 个）

AST 实测：`MiniTestBatchFailure` / `NormalizedEntryRead`（散文 **8** 处）/
`NormalizedSectionRead` / `RpeSubmissionRead` / `UnassignedEntryRead` ——
五个在本模块的**代码**里一处都没用到（既不在任何标注里、也不在任何 `response_model=` 上）。

**处置：删（5 个全删）**，三条理由：① 本模块**没有** `__all__`，故它们不是
「对外重导出的公有面」，`app.api.schemas.feedback` 才是它们的住址、那里一个都没少；
② 本仓确有「文档点名要它住在这儿」的**语义住址**惯例，而它的形状是**一条守卫钉住
那个 import 被引用**（先例：`app/api/deps.py` 的 `from app.deploy import is_prod` +
`tests/architecture/test_layering.py` 的 allow-list 那一条），这 5 个**既没有**那样的守卫
也没有那样的注释；③ 散文里的引用一律是**说明性**的（「本端点只投影出
`NormalizedEntryRead` 那三格」），读的人要的是那个**类**，而 import 到本模块只会让
`git grep` 多出一个假的「消费者」。

⚠️ **它今天为什么不红**（派单点名要实测）：`tests/architecture/test_layering.py`
只看**依赖方向**（`api → api` 层内许可）、不看「import 了有没有用」；而本仓**没有**
任何一条 unused-import 守卫（实测：`tests/architecture/` 三个文件里没有一个 AST 遍历
`ast.Import` / `ast.ImportFrom` 再比对使用的判据）。⇒ 那 5 个是**静默**积下来的，
删掉它们不需要改任何守卫。⚠️ 本波**没有**顺手加一条 unused-import 守卫：
它要先给全仓定一条「什么时候允许一个只被散文引用的 import」的口径
（那正是本条的裁定：**不允许**），超出本波范围，已登记待清扫（§⑦ 第 4 条）。

### C7 · 不可达的 `assert orphan is not None` —— **实测可达，故保留**（顶回派单）

派单的裁定是「删（硬规矩 #39 死代码）」，并要求「删之前实测确认它真不可达；
**若有测试走到它，它就不是不可达的，那就保留并把取证报进报告**」。

**实测**：把 `app/api/crud.py:1103` 那一行换成一句必炸的 `raise RuntimeError("C7-PROBE")`，
跑 `tests/api` + `tests/integration` + `tests/architecture` →
**28 条测试走到它**（`/api/alerts` 与 `/api/notifications` 两个多态键资源的教师档读，
一律经 `_require_orphan_row_readable`）；跑完 sha256 复核**逐字还原**。
⇒ **它不是不可达的，保留**。

⚠️ 而那行注释改前逐字写着「（反空转，**不可达**）」—— 那半句是**错的**，已按实测改写：
「**跑不到**」与「**跑到了也不会红**」是两个不同的性质，改前把它们混成了一格。
今天成立的是后者（`where is None` 那一支上面已经 `raise` 掉了，而 `_orphan_condition`
只在 `owner.orphan is not None` 时才回一个非 `None` 的表达式）。
⚠️ 保留它的理由：它是「那两条性质漂开了」时**唯一**会响的地方，而删掉它的收益是 0
（一行 assert）、代价是把一档**静默**失效放回来。

---

## ⑥ 隐私纪律复核

| 守卫 | 复跑结果 |
|---|---|
| `test_the_audit_module_never_reads_the_request_body`（AST 结构性质：`audit` 模块永不读 body） | **PASSED** |
| `test_a_login_with_a_password_leaves_no_trace_of_that_password_in_the_audit_row`（真发一次带口令的 login，然后扫那一行的全部 9 列） | **PASSED** |
| `test_no_audit_schema_mentions_a_credential_or_a_body` | **PASSED** |
| 本波新增 `test_a_two_thousand_character_user_agent_leaves_no_trace_in_any_column`（真发 2 000 字符 UA + Referer，扫两张表**全部列**） | **PASSED** |
| 本波新增 `test_no_user_agent_is_stored_anywhere_and_no_column_was_added_by_this_wave` | **PASSED** |

（五条一次跑：`5 passed in 0.23s`。）

**本波有没有新增审计列**：**没有**。`audit_log` 仍然 **9** 列、`login_attempt` 仍然 **6** 列、
`user_session` 仍然 **8** 列、表数仍然 **28**（由上面第 5 条守卫按字面量钉住）。
⚠️ 本波截断的是 `path` / `target` / 限流键，**不是** body；⚠️ 而 `User-Agent`
今天**根本没存**（§②-1 的 C 表），故按控制者裁定**不加**。

---

## ⑦ 待清扫 / 关切 / 没按派单做的 / **顶回**

### 顶回（**5** 处）

| # | 顶回什么 | 理由（详址） |
|---|---|---|
| 1 | **C1：请求体的 15 格用「拒绝」而不是「截断」** | 截断一个 `student.name` = 一个看起来正常的假姓名写进名册 = **数据损坏**。派单给了「截断/校验/拒绝三选一」的口子（§②-3） |
| 2 | **C1：`ip` 与 `staff_no` 用「哨兵」而不是「截断」** | 派单自己点名了这一格（「截一个 IP 会得到一个假 IP」）；实现者把同一类推到了 `staff_no`（截一个工号 = 指认到一个不存在的人）。哨兵形状 `<over:N>` 还保住了「原文有多长」（§②-3） |
| 3 | **C1：不做全局 `before_flush` 钩子** | 三条理由：失效方向是 409 而不是 422 / 会把三档处置压成一档 / 会连带管住管道与 seed（§②-3） |
| 4 | **C3：spec §13.4.2 那句「它不是 bug，请不要去『修』它」** | 那三个被否掉的方案否的是「抄 localStorage / 藏报头 / 阻塞首屏」，而「那一帧不许说谎」是**第四个**方案、三个代价一个都不付（§④-2、spec §13.13.3） |
| 5 | **C7：那句 assert 不删** | 实测 **28 条测试走到它** ⇒ 它不是不可达的；派单逐字要求这一档「保留并把取证报进报告」（§⑤-C7） |

⚠️ 另有一处**没有顶回但改了实现选择**（如实记）：C2 的两个界做成**绝对值**、
并**连带**让 `iterations()` 也判界。派单给的是「上界 2 000 000 / 下界 100 000」，
两个数**逐字采纳**；改的是「相对 `iterations()` 还是绝对」那一格 ——
相对值会让「抬高迭代次数」这一次运维动作把全部既有口令打死，
而它与本模块的核心性质（校验不依赖配置）直接冲突（§③-2）。

### 待清扫（**6** 条，本波新登记）

1. **`User-Agent` 要不要进审计**：今天全库没有任何一列存它（实测），故它不是宽度炸弹；
   要纳入得先重裁 spec §13.9 那条「审计不落任何请求体」隐私口径的**边界**
   （UA 不是 body，但它同样是客户端原文）。⚠️ 本波按控制者裁定**没加**。
2. **CSV 摄取路径的字段长度没有校验**：`app/pipeline/extract.py` / `clean.py` 写进
   `body_composition.device`（32）/ `fitness_test_batch.source`（32）/
   `fitness_test_result.national_grade`（16）一族的值来自**甲方上游的导出文件**。
   它不是 HTTP 客户端可控（`run-daily` 是本模块唯一的写端点、没有 `UploadFile`），
   而一个上游改字段格式就能让它在 PG 上炸。⚠️ 正确的收口点不是 `app/db/width.py`
   （那一档的失效方向应当是「进 `cleaning_log` 剔除」而不是 422）。
3. **`app/api/crud.py` 的 `create_row` 走 `repo.upsert` 那一支**：`ensure_fits` 排在
   `upsert` **之前**，故「撞自然键 → 409」那一档也先过了长度校验。⚠️ 于是
   「一个超宽的更新 + 一个撞键」得到的是 **422** 而不是 409 —— 两档都拒绝，
   而口径变了（如实记，今天没有守卫钉「撞键优先于长度」）。
4. **unused-import 守卫**：本仓没有（§⑤-C6 实测）。要加得先定「什么时候允许一个
   只被散文引用的 import」这条口径。
5. **`app/db/width.py:161` 那一支没有覆盖**（`truncate` 的「极窄列」退化：
   `width <= len(OVERLONG_SUFFIX)`）：全库最窄的 `String(n)` 是 `String(8)`、
   而标记是 6 字符，故今天**不可达**（它是许可而不是断言，硬规矩 #39）。
   `app/domain/` 的 100% 不受影响（本模块不在 `app/domain/` 下）。
6. **`_HISTORICAL` 那 6 个名字**：等哪一天有人把那些测试建回来，清单要跟着删
   （守卫的第 ② 拍会红并指路）。

### 关切（**2** 条）

1. **`ensure_fits` 是一次逐列的 Python 循环**：9 个可写资源的 POST/PATCH 各多一次
   「遍历请求体的键 + 查列宽」。实测在演示库上 smoke 两档耗时与基线同量级
   （dev 30.1 s → 本波未单独计时；产品档 28.2 s → **30.7 s**），
   ⚠️ 而那 2.5 s 的差里含本波**新增的 16 条断言**（其中 §C3 要扣住一次 `me`
   并轮询到落定），故不能全记在这一格上。
2. **审计行的 `path` 被截断后，「两条只在第 257 个字符之后不同的路径」会撞成同一格**：
   标记让「被截过」可见，但**不保留**被切掉的那一段。⚠️ 判定可接受：一条 256 字符以上
   的路径本来就不是一个业务路径（今天最长的路径模板是 47 字符），而审计要答的
   「对哪一个做了什么」在前 250 个字符里已经答完了。

### 没按派单做的（**3** 处，逐个如实记）

1. **C7 没删**（派单裁定「删」）—— 实测可达，按派单自己给的那条口径保留（§⑤-C7）。
2. **C6 删了 5 个而不是 3 个** —— AST 实测是 5 个（派单说「三个」）。
3. **C4 的行号与派单不同** —— 派单写 `catalog.py:172`，实测那一处在 **177**
   （172 是同一节里另一行）；`test_crud.py:590` 实测在 **591**。⚠️ 两处都改了。

---

## ⑧ 最终验收

### ⑧-1 后端

| 格 | 基线 | 本波 |
|---|---|---|
| 全量（`--cov=app/domain --cov-branch`） | 1541 passed + 1 skipped（270.47 s） | **1561 passed + 1 skipped**（**288.49 s** / 墙钟 290.81 s）← **净新增 20 条**（C1 13 + C2 4 + C4 3） |
| 全量（不带 `--cov`） | 1542 passed（Task 11 是折算） | **1562 passed**（本机**亲跑**，164.22 s；那 1 条 skip 在不带 `--cov` 时是 pass，与基线同一格） |
| `app/domain/` 覆盖率四格 | 1268 / 0 / 376 / 0 / **100%** | **1268 / 0 / 376 / 0 / 100%**（**一格未变**，18 个文件逐个 100%） |
| 表数 | 28 | **28** |
| **迁移链** | 4 单头 | **4 单头**（`53e5a548c40e → 0b7da3d20211 → 7f3923d8af84 → 0ac943e0da9b`，`get_heads()` = 1 个）← ⚠️ **本波一格 schema 都没动** |
| 架构守卫扫描面 | 71 | **72**（`pipeline 10 + db **14** + domain 18 + api 26 + auth 4`；db 涨 1 是 `db/width.py`）；两个下界（`>= 21` / `>= 20`）**刻意不抬**，反向那一圈 45 → **46** |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（`width.py` 住在 `app/db/`、**不在** `app/db/models/`，故那一格一个名字都没多） |
| `_MODELS_SUBMODULES` | 8 | **8**（同上） |
| 黄金用例 | 14 | **14**（`tests/integration/test_golden_cases.py` 收集 **19** 条，id 到 `[13-GC14]`） |
| 未定型响应（`test_prescription_api.py` 的 `expected`） | 26 | **26**（`assert len(expected) == 26` 全绿） |
| 新增依赖 | 0 | **0**（`tests/test_dependencies.py` 全绿；`app/db/width.py` 只 import `typing` 与 `sqlalchemy`） |

### ⑧-2 openapi 五格（**一格都没变**）

| 格 | 基线 | 本波 |
|---|---|---|
| 路径 | 74 | **74** |
| 操作 | 102 | **102** |
| 挂 `security` 的操作 | 84 | **84** |
| GET | 63（15 匿名 + 48 挂 security） | **63（15 匿名 + 48 挂 security）** |
| `securitySchemes` | 3 | **3** |
| catch-all 路径 | 0 | **0** |

⚠️ 离线的 `gen:api` **没有跑**（本波没有改任何端点签名、任何 schema、任何 security，
故 `schema.d.ts` 不需要重生；⚠️ 也就没有 Task 11 那一格「跑完 `gen:api` 要把
`schema.d.ts` 从 LF 还原成 CRLF」的复核需求）。

### ⑧-3 前端

| 格 | 基线 | 本波 |
|---|---|---|
| `npm run build` | 退出码 0 | **退出码 0**（`vue-tsc -b` 也过） |
| 产物哈希 | `index-CDpHJuAb.css` / `index-C6s8jbPM.js` / `StudentDetail-AI7GaiQq.js` / `AuditLogList-B0av5me7.js` | **`index-v1XDnUhk.css` / `index-DwZqq7MF.js` / `StudentDetail-D-ttLtZL.js` / `AuditLogList-BKStMt_y.js`** |
| 路由条数 | smoke 的 `ROUTES` **16** / `router/index.ts` 的 `routes` **20** | **16 / 20**（未改） |
| `check:tokens` | 绿（扫描面 36、下界 25） | **绿**（扫描面 **36**、下界 25 —— ⚠️ **一格未退**：一条新 CSS 都没加） |
| `check:dist` | 绿（25 个产物 / 778 426 字符） | **绿**（**25** 个产物 / **780 131** 字符；`adoptFromUrl` 0 次、两个字体 CDN 各 0 次、三条自校都在） |
| **smoke dev 档** | 18 步 / 616 断言 / 退出码 0 / 30.1 s | **18/18 步 · 632 断言 · 0 红 · 退出码 0**（后端 8000 + vite **5174**） |
| **smoke 产品档** | 18 步 / 616 断言 / 退出码 0 / 28.2 s | **18/18 步 · 633 断言 · 0 红 · 退出码 0 · 30.7 s**（`scripts\serve.ps1 -Port 8020 -SkipBuild`，同源） |

⚠️ **产物哈希那两格是两档对拍取证的**（不是推的）：把 `session.ts` 与
`IdentitySwitcher.vue` 换回 `HEAD` 的 blob 内容再构建，**逐字复现了基线的四个哈希**；
换回本波的改动再构建，得到上面那四个。⚠️ `index.css` 的**字节数没变**（65.20 kB）
而哈希变了：**Vue SFC 的 scope id 由文件内容推出**，改一个 `.vue` 的 `<script>`
就会换掉它那个 `data-v-` 属性、于是它那段 CSS 的选择器全变 ——
即「CSS 哈希变了」是**改了一个 SFC 的机械后果**，不是一次样式改动。
（⚠️ 第二次改 `AuditLogList.vue` 之后又构建了一次，`index-*.js` 变成
`index-BCWjM00F.js`、`AuditLogList-BKStMt_y.js` 等；`dist/` 在 `.gitignore` 里、不入库。）
⚠️ 断言数 **+16**：第 14 步 §C3 的 8 拍（dev 档 7 拍，故两档差 1）+ 第 17 步 ⑧ 的 6 拍
+ 第 14 步 `admin-audit-logs` 那一条路由**新增的 2 拍**（布局守卫在超宽值下从红变绿，
不是新断言，⚠️ 如实记：那 2 拍改前就存在、只是**红了**）。

### ⑧-4 禁区与卫生

| 格 | 实测 |
|---|---|
| `backend/pe.db` 存在 | **False** |
| `backend/data/seed/` 文件数 | **0** |
| `git diff 5f0ce7b HEAD -- backend/data --exit-code` | 退出码 **0**、输出 **0 字节** ← `backend/data/**` **一字节未动** |
| 四个数据指纹（sha256[:16] 大写，CRLF→LF 归一） | `D2C8E539E2FA0029` → `national_standard_2014.csv`；`5394B37F01DAC9AC` → `exercises.yaml`；`822CB86A5E998301` → `exercise_equivalence.yaml`；`E48E3AC82BB45BB7` → `alert_rules.yaml` —— **四个逐字命中** |
| 18 个模板指纹 | **18/18 逐字命中**（`C0C61D2140A521D0` RED-END-ABN-01 … `2389C1A03E6ABBCE` GRN-SPD-NOR-18）；`backend/data/**` 共 **24** 个文件 |
| `git ls-files frontend/dist` | **0 个** |
| `git ls-files backend/backups` | **0 个** |
| `.gitattributes` | `git diff 5f0ce7b HEAD -- .gitattributes --exit-code` 退出码 **0** = **一条都没碰** |
| ⚠️ `app.seed.generate` / `backfill` / `daily` | **一次都没跑**（要数据一律走 `demo.ps1`） |
| 本波起的进程 | **全部已停**：`Get-NetTCPConnection -State Listen` 在 5173/5174/8000/8010/8020 上只剩 **5173 PID 20240**（⚠️ **不是本波起的**，按纪律没杀） |
| `$env:TEMP\p06t12` | 报告写完 → commit → **删掉并复验** |

### ⑧-5 spec

| 格 | 基线 | 本波 |
|---|---|---|
| 工作树字节 | 397 490 B | **425 949 B** |
| 行数 | 3 717 | **4 038** |
| 行尾 | 全 CRLF / 无 BOM | **全 CRLF（4 038 个）/ 裸 LF 0 / 无 BOM**（`mixed = False`） |
| sha256[:16]（**工作树**口径） | `3921e779c9edd54d` | **`f083261a4985dad5`** |
| sha256[:16]（**LF 归一**口径） | `fa6a3680407aaf6d` | **`1e6a44addc96d7b0`** |
| 入库 blob 字节 | 393 773 B | 见 §⑧-6（commit 之后复核） |
| `git ls-files --eol` | `i/lf w/crlf attr/text eol=crlf` | **同**（`i/lf w/crlf attr/text eol=crlf`） |

改了 **3 处**：① §13.4.2 那一段 M7 的「**它不是 bug，请不要去『修』它**」→ 顶回并改写
（原文那三个被否掉的方案**照留**当证据，新增「第四个方案」那一整段）；
② §13.11.4 的「断言数此后长了 N 次」追加 **616 → 632（dev）/ 633（产品档）**
与两档的亲跑结果；③ **新增 §13.13**（Task 12 的 7 个子节，C1–C7 各一节）。

### ⑧-6 commit 链

| sha | 一句话 | 自洽？ |
|---|---|---|
| **`4d8a705`** | `fix(db)`: 客户端可控的串不许超过它那一列的声明宽度（C1） | ✅ 自洽（`app/db/width.py` + 三个收口点 + 13 条守卫 + `test_layering.py` 的扫描面散文；单跑该 commit 全套件绿） |
| **`addeb27`** | `fix(auth)`: `verify_password` 的迭代次数要有上下界（C2 / 老终审 M6） | ✅ 自洽（两个阈值 + `iterations()` 判界 + conftest 抬到 100000 + 4 条新守卫 + 3 处因此变假的散文） |
| **`44a6577`** | `fix(frontend)`: 会话恢复那一帧不许说「未登录」/ 画 ANONYMOUS（C3 / M7） | ✅ 自洽（`isPending` + 两个消费者 + smoke 两半守卫） |
| **`a4aab88`** | `chore(backend)`: 四处代码级清扫（C4–C7） | ✅ 自洽（12 处坏引用 + 新守卫 3 条 + C5 收一次 + C6 删 5 个 import + C7 改注释） |
| **`<本次>`** | `docs`: spec 3 处（§13.4.2 / §13.11.4 / 新增 §13.13）+ 实现者报告 + C1 的审计页折行 | ✅ |

⚠️ **一处如实记**：C1 的**前端**那一半（`AuditLogList.vue` 的 `a-cell--wrap`）与
`smoke.mjs` 的 §C3 修正（按档分支、`TIERS_SEEN`、路径分隔符归一）**没有**挤进
`44a6577`，而是落在最后一个 commit 里 —— 因为它们是**跑完两档 smoke 之后**才实测出来的
（改前那两条布局守卫在超宽值下是红的）。⚠️ 于是 `44a6577` 那一个 commit 单独 checkout
出来跑 smoke 会在 `admin-audit-logs` 的布局守卫上红 2 条（**后端**测试全绿）；
`4d8a705`（C1 后端）同样如此。⚠️ 这是本波**唯一**一处「中间 commit 不完全自洽」，
按 Task 11 那条口径如实记在这里。

---

## ⑨ 行尾复核（逐个被改文件）

⚠️ 两个口径都报（本机 `core.autocrlf=true`：工作树 CRLF、入库 blob LF）。

| 文件 | `git ls-files --eol` | 工作树 | commit |
|---|---|---|---|
| `backend/app/db/width.py`（新） | `i/lf w/crlf attr/` | 15 522 B / 230 CRLF / **0 裸 LF** / 无 BOM | `4d8a705` |
| `backend/app/api/audit.py` | `i/lf w/crlf attr/` | 28 131 B / 444 CRLF / 0 / 无 BOM | `4d8a705` |
| `backend/app/auth/policy.py` | `i/lf w/crlf attr/` | 49 597 B / 777 CRLF / 0 / 无 BOM | `4d8a705` |
| `backend/app/api/crud.py` | `i/lf w/crlf attr/` | 159 948 B / 2 358 CRLF / 0 / 无 BOM | `4d8a705` + `a4aab88` |
| `backend/tests/api/test_column_widths.py`（新） | `i/lf w/crlf attr/` | 51 693 B / 928 CRLF / 0 / 无 BOM | `4d8a705` + `a4aab88` |
| `backend/tests/architecture/test_layering.py` | `i/lf w/crlf attr/` | 72 371 B / 999 CRLF / 0 / 无 BOM | `4d8a705` |
| `backend/app/auth/passwords.py` | `i/lf w/crlf attr/` | 28 488 B / 440 CRLF / 0 / 无 BOM | `addeb27` + `a4aab88` |
| `backend/tests/conftest.py` | `i/lf w/crlf attr/` | 4 612 B / 67 CRLF / 0 / 无 BOM | `addeb27` + `a4aab88` |
| `backend/tests/auth/test_passwords.py` | `i/lf w/crlf attr/` | 41 612 B / 710 CRLF / 0 / 无 BOM | `addeb27` |
| `backend/tests/api/test_auth_api.py` | `i/lf w/crlf attr/` | 125 549 B / 2 214 CRLF / 0 / 无 BOM | `addeb27` |
| `frontend/src/stores/session.ts` | `i/lf w/crlf attr/` | 18 112 B / 335 CRLF / 0 / 无 BOM | `44a6577` |
| `frontend/src/components/IdentitySwitcher.vue` | `i/lf w/crlf attr/` | 20 364 B / 505 CRLF / 0 / 无 BOM | `44a6577` |
| `frontend/scripts/smoke.mjs` | `i/lf w/crlf attr/` | 282 679 B / 4 028 CRLF / 0 / 无 BOM | `44a6577`（+ 末次 commit 的 §C3 修正） |
| `backend/app/api/routers/feedback.py` | `i/lf w/crlf attr/` | 97 622 B / 1 536 CRLF / 0 / 无 BOM | `a4aab88` |
| `backend/app/api/routers/dashboard.py` | `i/lf w/crlf attr/` | 66 185 B / 1 078 CRLF / 0 / 无 BOM | `a4aab88` |
| `backend/app/api/routers/catalog.py` | `i/lf w/crlf attr/` | 66 445 B / 977 CRLF / 0 / 无 BOM | `a4aab88` |
| `backend/app/db/models/organisation.py` | `i/lf w/crlf attr/` | 9 680 B / 175 CRLF / 0 / 无 BOM | `a4aab88` |
| `backend/scripts/dump_openapi.py` | `i/lf w/crlf attr/` | 10 752 B / 208 CRLF / 0 / 无 BOM | `a4aab88` |
| `backend/tests/api/test_crud.py` | `i/lf w/crlf attr/` | 245 681 B / 4 447 CRLF / 0 / 无 BOM | `a4aab88` |
| `backend/tests/api/test_audit_api.py` | `i/lf w/crlf attr/` | 54 490 B / 1 018 CRLF / 0 / 无 BOM | `a4aab88` |
| `backend/tests/db/test_models.py` | `i/lf w/crlf attr/` | 154 746 B / 2 468 CRLF / 0 / 无 BOM | `a4aab88` |
| `backend/tests/test_serve.py` | `i/lf w/crlf attr/` | 87 771 B / 1 555 CRLF / 0 / 无 BOM | `a4aab88` |
| `backend/tests/architecture/test_docstring_references.py`（新） | `i/lf w/crlf attr/` | 23 870 B / 399 CRLF / 0 / 无 BOM | `a4aab88` |
| `Document/…设计spec.md` | `i/lf w/crlf attr/text eol=crlf` | 425 949 B / 4 038 CRLF / 0 / 无 BOM | 末次 commit |
| `frontend/src/views/admin/AuditLogList.vue` | 见末次 commit 后的复核 | — | 末次 commit |
| 本报告 `.superpowers/sdd/…/task-12-report.md`（新） | `i/lf w/lf attr/-text`（与既有 9 份报告同口径） | LF / 无 BOM | 末次 commit |

⚠️ `.gitattributes` 一条都没碰（`git diff 5f0ce7b HEAD -- .gitattributes --exit-code`
退出码 **0**）。⚠️ Task 11 实测到的「跑完 `gen:api` 要把 `schema.d.ts` 从 LF 还原成
CRLF」那一格本波**不适用**（`gen:api` 一次都没跑，`schema.d.ts` 一字节未动）。

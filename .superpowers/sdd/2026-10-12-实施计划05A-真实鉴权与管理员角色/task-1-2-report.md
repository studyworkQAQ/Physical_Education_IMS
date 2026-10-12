# 实施计划 05A · Task 1 + Task 2 · 实现者报告

> **日期**：2026-10-12 · **分支**：`feature/plan-05a-auth` · **起点**：`1d1b6e8`
> **派单范围**：Task 1（后端鉴权核心：schema + 密码 + 会话 + 5 个端点）+ Task 2（授权口径改造）
> **不在范围内**：§4（前端）、Task 3 / Task 4 / Task 5
> **commit 链**：`afb1886` → `1da7f9f` → `640d81e` → `b446c9a` → `8596043` → （本报告）
> **结论**：**1331 passed**（1270 → 1331，+61）；`app/domain/` 覆盖率四格**逐字不变**；
> 禁区一个字节没动；**新增后端依赖数 = 0**；`pyproject.toml` 一个字节没动。
> **顶回控制者 9 处**（其中 3 处是「计划的诊断本身错了」）；**没按派单做的地方 4 处**。

---

## ① 环境与基线复现

### 1.1 硬规矩 #73：版本实测

```
python -c "import fastapi, sqlalchemy, starlette, pydantic; print(...)"
→ 0.141.1 2.1.3 1.7.0 2.13.5
```

| 项 | 实测 | 派单说的 | 一致 |
|---|---|---|---|
| FastAPI | 0.141.1 | 0.141.1 | ✅ |
| SQLAlchemy | 2.1.3 | 2.1.3 | ✅ |
| Starlette | 1.7.0 | 1.7.0 | ✅ |
| Pydantic | 2.13.5 | 2.13.5 | ✅ |
| Python | 3.11.1（无 venv） | 3.11.1 | ✅ |

⚠️ **没有撞上 `ImportError: DLL load failed`**（Smart App Control 没拦 `.pyd`），故按派单继续。

### 1.2 开工时的服务与仓库状态

* `Get-NetTCPConnection -LocalPort 8000,5173 -State Listen` → **两个都还起着**：
  `::1:5173`（vite，PID 16316）与 `127.0.0.1:8000`（uvicorn，PID 19068）。
  ⚠️ 那个 uvicorn 跑的是**上一波的代码**（没有 `--reload`），指向 `backend/pe_demo.db`。
  **我没有动它**（杀别人的进程是一次不需要的外部副作用），本波全部取证走 `TestClient`。
  ⚠️ 交接给控制者：要用它手工验证 Plan 05A，**必须重启**，而且 `pe_demo.db` 必须**先删**
  ——`create_all` 对已存在的表原样跳过，不会给 `student` / `teacher` 补那 5 个新列，
  旧库上的鉴权端点会以「列不存在」在离真因很远的地方 500。
* `git status --short` → 干净；`git rev-parse --abbrev-ref HEAD` → `feature/plan-05a-auth`；
  `git log --oneline -1` → `1d1b6e8`。**全程没切分支、没 push、没碰 main。**

### 1.3 基线复现

| 项 | 起点实测 | 派单说的 |
|---|---|---|
| `python -m pytest -q` | **1270 passed** in 120.25 s | 1270 passed ✅ |
| `--cov=app.domain --cov-branch` | **1268 / 0 / 376 / 0 / 100%**，1330 passed + 1 skipped | 逐字相同 ✅ |
| 表数 | 25 | 25 ✅ |
| `_MODELS_PUBLIC_BASELINE`（运行时口径） | 33 | 33 ✅ |
| 扫描面（`SCANNED_DIRS` 四项） | **60** = pipeline 10 + db 11 + domain 18 + api 21 | 60 ✅ |
| `/api/` 路径模板 / 操作 | **66 / 94** | 66 / 94 ✅ |
| 挂 `security` 的操作 | **46** | 46 ✅ |
| GET（匿名 / 挂 security） | **59（48 / 11）** | 59（48 / 11）✅ |
| mutating 操作 | 35（**35 个全挂 security**） | — |
| `len(app.routes)` | **6**（⚠️ 假绿口径，只作对照） | 派单已警告 ✅ |
| 外键总数 / `JsonText` 列 / `_in_domain` 列 / `String(n)` 列 | 41 / 21 / 24 / 61 | — |

### 1.4 ⚠️ 派单第 3 节那 4 处「要实测」的答复

| # | 计划/派单说的 | **实测结果** | 处置 |
|---|---|---|---|
| 1 | §3.2「`teacher` 表是否有 `name` 列请实现者实测」 | **有**。`teacher` 的列实测是 `['id', 'staff_no', 'name']` | 假设成立，**不需要顶回**；教师的验身材料就是「工号 + 姓名」 |
| 2 | §3.2 学生的出生日期列名写作 `birth_date` | **列名是 `birth`**（`student` 的列实测是 `['id','student_no','name','sex','birth','department','grade']`） | **顶回 1 处**：请求体字段也叫 `birth`（本仓约定「Pydantic 字段名与 DB 列名逐字相同」，`StudentCreate.birth` 已在前，前端从 `GET /api/students` 拿到的也是 `birth`）。逐字理由写在 `app/api/schemas/auth.py::StudentBindCreate` 的 docstring 里 |
| 3 | §3.1「架构守卫那两条下界断言会不会红，要实测确认」 | **一条都没红**（它们都是 `>=`）。逐条实测：`len(real_py) >= 40`（实到 **140**）、`len(scanned) >= 18`（实到 **66**）、`len(api_py) >= 3`（实到 **23**）、`len(reverse_py) >= 15`（实到 **43**）、`len(cases) >= 22`（实到 **26**） | 我把其中**两个下界按既有取法抬了**（`len(scanned)` 18 → **21**、`len(reverse_py)` 15 → **20**），因为 `SCANNED_DIRS` 多了第五项 `"auth"`，而那两个数的语义逐字是「各目录地板之和」（18 = 5+5+5+3 → 21 = 5+5+5+3+3；15 = 5×3 → 20 = 5×4）。`len(cases) >= 22` **刻意不抬**（它的语义只是「矩阵没被写空」，取法与那两个不同，已在那条断言上方写明两者的差别） |
| 4 | Task 2「挂 security 的操作数 46 → ?（实测）」 | **48** | ⚠️ 而这 **+2 全部来自 Task 1-C**（`GET /api/auth/me` 与 `POST /api/auth/logout` 挂第三个 scheme `pe_session`）；**Task 2 自己贡献 0**——管理员就是一行 `teacher`，故管理台写操作的载体仍然是 `X-Teacher-Staff-No`，改的只是**判定**、不是**声明** |

---

## ② Schema（5 列 + 1 张新表）

### 2.1 逐列定义

**`student`（+2 列，共 9 列）** — `app/db/models/organisation.py`

| 列 | 类型 | 可空 | 备注 |
|---|---|---|---|
| `password_hash` | `String(255)` | ✅ NULL = 未绑定 | 存自描述串；生产迭代次数下实测 **90** 字符 |
| `password_bound_at` | `DateTime` | ✅ | 服务端盖，绑定那一刻 |

**`teacher`（+3 列，共 6 列）**

| 列 | 类型 | 可空 | 备注 |
|---|---|---|---|
| `role` | `String(16)` | ❌ | `default=Teacher.DEFAULT_ROLE`（`"teacher"`）；CHECK `ck_teacher_role`：`role IN ('admin', 'teacher')`；类常量 `Teacher.ROLES = {"teacher","admin"}` 是唯一真相 |
| `password_hash` | `String(255)` | ✅ | 同 `student` |
| `password_bound_at` | `DateTime` | ✅ | 同 `student` |

**`user_session`（新表，8 列）** — `app/db/models/auth.py::UserSession`

| 列 | 类型 | 可空 | 备注 |
|---|---|---|---|
| `id` | `String(64)` **PK** | ❌ | `secrets.token_urlsafe(48)` → 恰好 64 字符。⚠️ **不是自增整数**：自增 id 可枚举，而它就是要放进 cookie 的那个值 |
| `kind` | `String(16)` | ❌ | CHECK `ck_user_session_kind`：`kind IN ('student', 'teacher')`；词表唯一所有者是 `UserSession.KINDS` |
| `subject_id` | `Integer` | ❌ | ⚠️ **刻意不是外键**（见 2.3） |
| `role` | `String(16)` | ❌ | CHECK `ck_user_session_role`：`role IN ('admin', 'student', 'teacher')`；⚠️ 冗余存一份（见 2.4） |
| `created_at` / `expires_at` / `last_seen_at` | `DateTime` | ❌ | 滑动过期落在后两格 |
| `revoked_at` | `DateTime` | ✅ | 登出 = 写这一列（**不删行**） |

⚠️ 按本包约定 2「枚举取值域两处设防」，三个新枚举列都同时有**类常量**与**由它生成的 SQL CHECK**
（`_in_domain`），故 `_in_domain` 反解出的受约束列数 **24 → 27**，
`test_string_column_widths_fit_their_value_domains` 的遍历**自动**覆盖它们（列宽 16 对最长值 `"teacher"` = 7 绰绰有余）。

### 2.2 计数变化

| 量 | 起点 | 现在 | 说明 |
|---|---|---|---|
| 表数 | 25 | **26** | `user_session` |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（⚠️ 顶回） | 见 2.5 |
| `models.__all__` | 14 | **14**（一个字没动） | 同上 |
| `models` 的子模块 | 6 | **7**（+ `auth`） | `_MODELS_SUBMODULES` 与其 `== 7` 断言同步 |
| 扫描面 | 60 | **66** | pipeline 10 + db **12**（+`models/auth.py`）+ domain 18 + api **23**（+`routers/auth.py`、+`schemas/auth.py`）+ **auth 3** |
| 外键总数 | 41 | **41**（不变） | `user_session.subject_id` 刻意不是外键 |
| `JsonText` 列 | 21 | **21**（不变） | 新表没有 JSON 列 |
| `String(n)` 列 | 61 | **67** | +6（两个 `password_hash`、`teacher.role`、`user_session` 的 `id`/`kind`/`role`） |
| `_in_domain` 受约束列 | 24 | **27** | +3 |

### 2.3 ⚠️ `user_session.subject_id` 无外键的代价与那条守卫

多态外键在 SQL 里不存在（一个 `REFERENCES` 只能指一张表；两张表各建一个可空外键还要求
「恰好一个非空」这条互斥，而 SQLite 的 CHECK 能表达互斥、却表达不了「非空的那一个必须真的存在」）。
连带三件事，逐字写在 `app/db/models/auth.py` 的模块 docstring 第二节：

1. `app.api.crud._child_tables` **探测不到它**（那个函数扫 `foreign_keys`），
   故 `DELETE /api/students/{id}` 的 `restrict` 那一档看不见会话行；
2. 删学生**不会**级联删他的会话行 → 孤儿会话行；
3. **处置**：吊销必须在**解析会话时**做（不是计划写的「登录时」——见**顶回 5**）。

**那两条守卫的名字**（一份在 ORM 层、一份在 HTTP 层，刻意不合并）：

| 层 | 守卫 | 断言 |
|---|---|---|
| ORM | `tests/auth/test_sessions.py::test_a_session_whose_subject_has_been_deleted_is_revoked_in_the_row` | 删学生后 `resolve` 回 `None`，**且**会话行**还在**（证明它不是外键级联）、**且** `revoked_at` 被写上（证明「拒绝」与「吊销」两件事都发生了） |
| ORM（教师那一侧） | `tests/auth/test_sessions.py::test_the_teacher_variant_of_the_deleted_subject_guard` | 同上的教师版；⚠️ 它守的失效形态是「删掉一个离职的教务干事，他的管理台权限还在」 |
| HTTP | `tests/api/test_auth_api.py::test_a_session_whose_subject_has_been_deleted_is_revoked_on_the_next_request` | 删学生 → 他的旧 cookie **立刻 401 `unauthenticated`**（**不是 500**、也不是照常放行），且 `revoked_at` 被写上 |

⚠️ 「**不是 500**」这一格尤其要紧：一个天真的实现会在 `Identity.name` 上撞 `AttributeError`
（`None.name`），经 `app.api.errors` 的兜底折成 500 + 一句固定的「服务器内部错误」——
于是运维看到的是一串 500，而真因是「有人从名册上删了一个人」。

⚠️ 另有 `tests/auth/test_sessions.py::test_subject_id_is_deliberately_not_a_foreign_key`
把「出向外键数是 0」钉成结构面事实：若哪天有人「顺手补上一个外键」（它只能指向两张表中的一张，
故补上去就是**错的**），本条当场红。

### 2.4 `role` 冗余的落地与它的代价（⚠️ 顶回 2：代价被实测更正）

**落地**：`UserSession.role` 存签发那一刻的值（学生恒为 `"student"`、教师是 `teacher.role`）；
`app.auth.sessions.resolve` 直接把它交给 `Identity.role`，`GET /api/auth/me` 与登录响应体回的就是它。

**控制者裁定的代价**（计划 §3.1）：「冗余了则『管理员被降权成教师』不会立刻生效——要等他重新登录」。

⚠️ **实现者复核后：那半句在安全档上不成立**。后端的两道 role 闸门
（`app.api.deps.require_admin` 与 `require_teaches_section` / `require_teaches_student`
里「管理员越过」那一支）都经 `require_staff`，而它查的是 **`teacher` 表**、
**不是** `user_session.role`。故：

| 事 | 降权之后 |
|---|---|
| 管理台的写操作（`require_admin`） | **立刻** 403 |
| 任教闸门的「管理员越过」（`require_teaches_*`） | **立刻**失去（下一次请求就 403） |
| `GET /api/auth/me` 与登录响应体里的 `role` | **滞后**，要等重新登录 |

于是真实代价是 **UI 一致性**（被降权的人在重登之前，前端仍会把他送到 `/admin`，
然后每一次写都吃一个 403），**失效方向是安全的**。
守卫：`tests/api/test_auth_api.py::test_demoting_an_admin_takes_the_console_away_immediately_but_not_the_me_projection`
（钉后端立刻生效 + `me` 滞后）与
`tests/auth/test_sessions.py::test_a_demoted_admin_keeps_the_role_recorded_on_his_live_session`（钉会话行不变）。
**两条各钉一半，都在场。**

**结论：维持「冗余」的裁定**，但把理由换成了上面这一条（三处散文已按实测更正：
`app/db/models/auth.py` 模块 docstring 第三节、`app/api/schemas/organisation.py::TeacherUpdate`、
`tests/auth/test_sessions.py` 那条守卫的 docstring）。
⚠️ 顺带一条：冗余**并没有**省掉那次 JOIN——`resolve` 无论如何都要回查 subject 行
（2.3 的「subject 已删当场吊销」要求它），故它买到的是「降权不需要重新登录」这件事**可以不做**。

### 2.5 ⚠️ 顶回 1：`_MODELS_PUBLIC_BASELINE` 仍是 **33**，`__all__` 一个字没动

计划 §3.1 写的是「`_MODELS_PUBLIC_BASELINE` **33 → ?**（新增 `UserSession` 等公开名）」，
派单第 1 节写的是「`_MODELS_PUBLIC_BASELINE` **33**（本波会变，**实测新值**）」，
计划同一节还逐字要求「`models/__init__.py` 的 `__all__` 要加」。

**这三句与本仓的 Ruling 97 直接冲突**，而 Ruling 97 有一条**在场的守卫**：
`tests/db/test_models.py::test_models_public_namespace_is_unchanged_by_the_split` 钉的是
**拆包之前**（基线 `e26347f`）实测的 33 个公有名，而它自己的 docstring 逐字把
「基线被更新成含新名字」列为**它要防的失效形态**（两侧同源，硬规矩 #35）。
Plan 02 Task 6 已经为同一件事**顶回过一次派单**（那次派单要求把基线从 33 抬到 35），
处置是「不重导出、不动基线、另加一条守卫」；Plan 03 Task 2 又沿用了同一条纪律（7 张表）。

**处置**：`UserSession` 放进新的子模块 `app/db/models/auth.py`，
`models/__init__.py` 对它是 **非星号**导入（`from . import auth, feedback, prescription`），
故它**不进**公有导入面、也**不进** `__all__`；写入方按
`from app.db.models.auth import UserSession` 引用。

**实测证据**：`len({n for n in dir(models) if not n.startswith('_')} - 七个子模块名) == 33`，
「多出来的名字」清单为空；`len(models.__all__) == 14`。
连带把那条守卫从 **11 个表类扩到 12 个**，并把它**改成计划无关的名字**
（`test_plan02_and_plan03_tables_stay_out_of_the_models_public_namespace` →
`test_new_tables_stay_out_of_the_models_public_namespace`）——理由写在它自己的 docstring 里：
「名字只写一个计划会让下一个计划的实现者以为新表由别处守」，而 Plan 03 那次改名给的正是这个理由；
「每来一个计划就把名字加长一格」显然不是可执行的规则。连带 4 处散文引用一并更新
（`models/__init__.py` 2、`pipeline/daily.py` 1、`pipeline/prescription_stage.py` 1）。
`_PLAN02_AND_03_TABLE_CLASSES` 同时改名为 `_NON_PUBLIC_TABLE_CLASSES`。

### 2.6 ⚠️ 计划没提、实测撞出来的两处 schema 连带（都已收进来）

1. **`tests/seed/test_generate.py::test_table_partition_is_exhaustive` 会红**（按集合相等判
   「三个分区恰好穷尽 `Base.metadata`」）。**处置**：新增**第四个分区**
   `AUTH_TABLES = ("user_session",)`，而不是把它塞进 `DATA_TABLES`——那一份的名字与 docstring
   逐字写着「经适配器与管道流入的仿真数据」，而 `user_session` 一个字都不由管道写；
   也不塞进 `ORGANISATION_TABLES`（那一份的判据是「`seed_database` **必须**写它」，
   而演示库刚灌完时会话表**必然 0 行**）。同步改了「四张清单长度之和 == 并集」、
   「seed 阶段 0 行」那一圈的遍历对象、以及那条 `assert AUTH_TABLES == ("user_session",)`。
   ⚠️ **派单与计划的「完整同步清单」都没有这一格**，是跑到红才发现的（已写进
   `tests/db/test_models.py` 那段清单的第 ④ 格）。
2. **`tests/api/test_crud.py::test_every_table_has_a_single_column_primary_key` 的前提半句失效**：
   它的 docstring 逐字写着「25 张表的主键都是 INTEGER」，而 `user_session.id` 是 `String(64)`。
   **处置**：不删那半句、也不让它变成一句假话，而是**显式例外化**——加一拍
   「26 张里恰好 1 张的主键不是整数，而它是 `user_session`」。
   ⚠️ 它不动摇 `_purge_where`：那个函数只在 `on_delete="cascade"` 那一档被调用，
   而 `user_session` 不是 23 个 CRUD 资源之一，故它的主键类型永远不会被读到。

### 2.7 ⚠️ 凭据列不得出现在任何响应体里（计划完全没提，实现者实测出来的洞）

**洞的形状**：`TeacherRead` / `StudentRead` 的字段是**显式清单**（本来就没有 `password_hash`），
但**泛型 list 端点不走 `response_model`**（它显式只 SELECT `kept` 那些列、手工拼 dict），
故 `GET /api/teachers` 与 `GET /api/students` 会**匿名原样返回全校的口令哈希**。
离线爆破一个 PBKDF2-SHA256 串在 GPU 上是几小时的事，而哈希一旦泄漏**无法撤销**
（原型没有找回流程），且用户复用口令是常态。

**处置**：用本仓既有的「两半」机制（Plan 03 收尾小修波为 `class_session.rpe_token` 建的那一套）：

| 半 | 住址 | 本波的改动 |
|---|---|---|
| 读模型 | `tests/api/test_crud.py::_SERVER_GENERATED_HIDDEN_COLUMNS`（档 2） | +2 行：`/api/students`、`/api/teachers` 各 `("password_hash",)`；大小断言 1 → **3**，并**新增一份逐格点名的字面清单**（让「加第四行」必须是一次显式登记） |
| list | `app/api/routers/catalog.py::RESOURCES` 的 `list_exclude` | +2 行：`students` 与 `teachers` 各 `"list_exclude": ("password_hash",)`；`declares_list_exclude` 断言 1 → **3** |
| Create/Update | `tests/api/test_crud.py::_SERVER_FILLED_COLUMNS`（档 1） | +2 行：两列都由绑定端点填，客户端传了也没用。⚠️ 那一格是承重的：能被 POST 写进去的口令哈希等于「任何人可以给任何人设一个自己知道的口令」，即绕过绑定流程的验身材料本身 |

⚠️ **`password_bound_at` 反过来是暴露的**（档 1 的语义正是「服务端填、但要暴露」）：
它不是凭据，而「谁还没注册」正是教务干事在管理台上要看的。
代价如实记：匿名 `GET /api/teachers` 因此泄漏「哪些工号已注册」，
而计划 §3.3 已经裁定接受同一档泄漏（登录的两档 code 本身就给出这个信号）。
⚠️ `teacher.role` 也暴露（前端路由守卫要靠它），且 **`TeacherCreate` / `TeacherUpdate` 有 `role`**
（缺省 `teacher`，走 `one_of` → 422 而不是 DB CHECK 的 409）：
「谁能造出一个管理员」的答案是「已经是管理员的人」（`POST /api/teachers` 仅管理员可调）。

守卫：`tests/api/test_crud.py::test_every_read_schema_covers_exactly_the_model_columns`（结构面）、
`…::test_every_resource_list_omits_json_text_columns_and_read_one_includes_them`（list 那一半）、
`tests/api/test_auth_api.py::test_no_credential_column_appears_in_any_response_body`（鉴权端点这一侧，
逐字扫响应体文本）、`…::test_no_auth_schema_mentions_a_credential_column`（五个模型的 `model_fields`）。

---

## ③ 密码（`app/auth/passwords.py`）

### 3.1 自描述串的格式与解析

```
pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
```

| 段 | 内容 | 长度 |
|---|---|---|
| 1 | `ALGORITHM = "pbkdf2_sha256"` | 13 |
| 2 | 迭代次数（十进制） | 6（生产）/ 4（测试） |
| 3 | `base64.b64encode(secrets.token_bytes(16))` | 24 |
| 4 | `base64.b64encode(digest)`，`KEY_BYTES = 32` | 44（含一个 `=`） |

生产缺省下实测整串 **90** 字符（测试的 1000 次下是 88）。列宽 `String(255)` 由
`tests/auth/test_passwords.py::test_the_stored_string_fits_the_column_that_holds_it` 钉住
（⚠️ 那一条**跑一次真的 600 000 次迭代**，因为串长取决于迭代次数的**位数**，
用测试值量出来会短 2 个字符——那正是它要防的假绿）。

**解析**（`verify_password`）：`split("$")` → 段数必须 4 → 第 1 段必须等于 `ALGORITHM`
→ 第 2 段 `int()` → 第 3/4 段 `b64decode(..., validate=True)` → 用**串里记的**迭代次数与
`dklen=len(want)` 重算 → `hmac.compare_digest`。
⚠️ **12 个坏串形状逐个回 `False`、绝不抛**（`None` / 空串 / 一段 / 三段 / 五段 /
算式名不对 / 迭代次数不是整数 / 是 0 / 是负数 / 盐不是 base64 / 空盐 / 空摘要），
由 `test_verify_returns_false_for_every_malformed_shape` 逐个点名 + 一拍反空转
（好串必须 `True`，否则「把 `verify_password` 改成 `return False`」也能全绿）。
⚠️ 最后两格尤其阴险：空盐会让 pbkdf2 退化成无盐的纯函数（彩虹表可用），
空摘要会让 `compare_digest(b"", b"")` **恒真**。
⚠️ 「绝不抛」是承重的：抛出去会被 `app.api.errors` 的兜底折成 **500**，
于是「一个人的口令列坏了」表现为「登录端点炸了」。

### 3.2 `PBKDF2_ITERATIONS` 的两个值与那条守卫

| | 值 | 住址 |
|---|---|---|
| **生产缺省** | **600 000**（OWASP 2023 对 PBKDF2-SHA256 的建议值） | `app.auth.passwords.PBKDF2_DEFAULT_ITERATIONS`（字面量） |
| **测试** | **1 000** | `backend/tests/conftest.py`（**新建的根 conftest**）里 `os.environ.setdefault("PBKDF2_ITERATIONS", "1000")` |
| 覆盖口 | 环境变量 `PBKDF2_ITERATIONS` | `app.auth.passwords.PBKDF2_ITERATIONS_ENV_VAR` |

**那条守卫的名字**：
`tests/auth/test_passwords.py::test_the_production_default_iterations_is_at_least_the_owasp_floor`

⚠️ **它是两拍，缺一不可**：① `PBKDF2_DEFAULT_ITERATIONS >= 600_000`（钉**字面量**，
不是 `iterations()` 的返回值——测试进程里那个恒为 1000，钉它等于什么都没钉）；
② `monkeypatch.delenv` 之后 `iterations() == PBKDF2_DEFAULT_ITERATIONS`。
少了②，「常量对、但解析函数写成了 `return 1000`」是绿的；少了①，「解析函数对、但常量被调低了」是绿的。
断言消息里逐字写了「若你是为了让测试跑得快而改的它，改错了地方」。

⚠️ **`iterations()` 在调用时读环境变量、不在 import 时读**（口径与
`app.api.routers.pipeline._csv_dir` 相同），守卫
`test_iterations_reads_the_env_var_at_call_time_and_rejects_a_bad_value` 钉住五档：
正整数 / 全空白 / 空串（三档都回缺省）+ 非整数 + `< 1`（两档抛 `ValueError`，
经 `app.api.errors` 折成 **422 `unprocessable_value`** 并带消息原文——
静默回落到 600 000 的表现是「测试慢得莫名其妙」，而没人知道为什么）。

### 3.3 ⚠️ `compare_digest` 变异自证的三重还原证据（硬规矩 #83）

生产代码写的是 `import hmac` + `return hmac.compare_digest(got, want)`
（**不是** `from hmac import compare_digest`），故 `monkeypatch.setattr(hmac, "compare_digest", spy)`
拦得到。守卫是
`tests/auth/test_passwords.py::test_verify_password_calls_a_constant_time_comparison`
（替身**仍然调真的** `compare_digest`，故真档仍 `True`；并钉住两个入参：
第一个是**重算出来的**摘要、第二个是**串里存的**那一个；另有一拍钉「坏串根本走不到比较那一步」，
否则「先比较、再判格式」这种倒序实现也是绿的，而它会对一个格式都不对的串跑一次 600 000 轮 pbkdf2
——一次免费的 DoS 放大器）。

**变异取证**（探针 `$env:TEMP\pe05a_probe\w07_mutation.py`，改前改后各删一次 `__pycache__`）：

| 步 | 证据 |
|---|---|
| 0 起点 | `sha256(app/auth/passwords.py)` = **`b8e69484daf2f83a7583d38643db25ac6423728de2f61c155124ea0c0feeed12`**，**14438 B**，CRLF=265、strayCR=0；删掉 **23** 个 `__pycache__` 目录；复跑 → **13 passed**，exit 0 |
| 1 变异 | 把 `    return hmac.compare_digest(got, want)` 换成 `    return got == want`；sha256 = **`799f69fdf5a05e75c06229e58ee242a2ee367e889e6c7523f196378635fdcf34`**；再删 6 个 `__pycache__` |
| 2 跑守卫 | exit **1**，**`1 failed, 12 passed`**；红的那一条正是 `test_verify_password_calls_a_constant_time_comparison`，红在 `assert len(calls) == 1` → `AssertionError: []` / `assert 0 == 1` |
| 3 还原（三重） | ① `sha256` 复原为 `b8e69484…eed12`（逐字相同）；② `TARGET.read_bytes() == before_bytes` → **True**（字节级复原）；③ 复跑 → **13 passed**，exit 0。⚠️ 变异时 `app/auth/passwords.py` **还未入库**，故 `git diff` 那一格是平凡真；**commit 之后复验**：`git status --short` 干净、`git diff 1d1b6e8 HEAD -- backend/app/auth/passwords.py` 只含本波的正常改动 |

⚠️ **这一档没有「行为面」的判据**：换成 `==` 之后 `verify_password` 的返回值**一模一样**，
故任何只看返回值的守卫都是假绿的——唯一的判据是「那个函数被调用了吗」。这句话逐字写在守卫的 docstring 里。

### 3.4 `bind` 的竞态：判据是**影响行数**

**实现**（`app/api/routers/auth.py::_bind_credential`）：

```python
result = session.execute(
    update(model)
    .where(model.id == row.id, model.password_hash.is_(None))   # ← 检查在 WHERE 里
    .values(password_hash=hash_password(plain), password_bound_at=bound_at)
    .execution_options(synchronize_session=False)
)
return result.rowcount          # ← 判据
```

`rowcount == 0` → **409 `password_already_bound`**（+ `session.rollback()`）。
⚠️ **不是**「先 SELECT 出 `password_hash is None`、再 UPDATE」（check-then-act）：
两个并发请求的 SELECT 都在任何一个 UPDATE 之前发生，于是**两个都能过**，
第二个 UPDATE 覆盖第一个的哈希，而两个请求都拿到 204——
用户以为自己的口令生效了，实际生效的是另一个人的（而另一个人可能是攻击者：
他知道验身材料、抢先绑定，于是受害者的「绑定成功」是一次**静默的账号接管**）。

**那条守卫怎么写的**（`tests/api/test_auth_api.py::test_the_second_of_two_concurrent_binds_is_409_not_a_silent_overwrite`）：

1. 先正常绑定一次（204）；
2. 用 `monkeypatch` 给 `app.api.routers.auth._bind_credential` 套一个**记名替身**
   （它调真的实现、把返回的 `rowcount` 抄进一个 list）；
3. 再发一次绑定（**换一个口令**）→ 断言 `409` + `code == "password_already_bound"`，
   **并断言 `seen == [0]`** ← 这一拍是「机制」，不是「症状」；
4. **对照拍**：把 `password_hash` 手工置回 `NULL` 再绑一次 → 断言 `seen == [1]`
   （少了这一拍，「`_bind_credential` 恒返回 0」也能让第 3 拍绿）；
5. **没有静默覆盖**的正面证据：409 之后用**第一个**口令登录 → 200，
   用第二个口令登录 → 401 `invalid_credentials`。

⚠️ **为什么必须量 rowcount 而不只是断 409**：两次请求是**串行**发的，
故一个 check-then-act 的实现第二次读到的已经是非 NULL、也会回 409——
「第二个请求是 409」对它是绿的。只有 `rowcount == 0` 才区分得开两者。
`execution_options(synchronize_session=False)` 的理由也写在了函数 docstring 里
（两个调用方在 `rowcount == 1` 之后都不再读那个 ORM 实例，故不需要同步 identity map）。

### 3.5 弱口令

`ensure_acceptable(plain)` 抛 `ValueError`（`MIN_PASSWORD_LENGTH = 8`），
经 `app.api.errors` 折成 **422 `unprocessable_value`** + 消息原文（含那个数字）。
⚠️ **刻意不用 Pydantic 的 `min_length=`**：那会给 **422 `request_validation_failed`**，
而计划 §3.2 要的是 `unprocessable_value`。于是「口令太短」与「请求体缺字段」
在前端是**两档**（前者提示「至少 8 个字符」，后者是前端自己的 bug）。
⚠️ 只判长度、不判复杂度；`strip()` 不参与判定（passphrase 要能含空格）。
守卫 `test_ensure_acceptable_rejects_a_short_password_and_names_the_rule`（边界是 `>=`：恰好 8 个够长）。
⚠️ 中文/日文/emoji 口令由 `test_a_non_ascii_password_survives_the_roundtrip` 钉住
（`len()` 判的是字符数、`encode("utf-8")` 用的是字节数，两者混用会让「8 个汉字的口令」
在一个实现里够长、在另一个里不够）。

---

## ④ 会话（`app/auth/sessions.py`）

### 4.1 cookie 的参数逐个（`cookie_kwargs` 是唯一住址）

| 参数 | 实际值 | 理由（逐字写在 `cookie_kwargs` 的 docstring 里） |
|---|---|---|
| `key` | **`pe_session`** | `SESSION_COOKIE_NAME`，全仓唯一住址（`SESSION_COOKIE_SCHEME` 与三个身份依赖都从它读） |
| `value` | `secrets.token_urlsafe(48)` → **64** 字符 | 不透明、不可枚举；宽度与 `user_session.id` 的 `String(64)` 逐字对齐 |
| `max_age` | **7200** | `int(SESSION_TTL.total_seconds())`，`SESSION_TTL = timedelta(hours=2)`。⚠️ **与 `expires_at` 同源**（计划 §3.4 点名要防「一个写 7200 一个写 86400」） |
| `path` | **`/`** | 缺省的 path 是「当前 URL 的目录」，那会让 `/api/auth/login` 设的 cookie 只在 `/api/auth/` 下可见 |
| `httponly` | **True** | JS 读不到 ⇒ XSS 拿不走。⚠️ 代价：前端无法自己判「我登录了吗」，只能靠 `me` 的 401（Task 3 的路由守卫正是这么写的） |
| `secure` | **False**（仅 `PE_ENV=production` 时 True） | 原型跑在明文 HTTP 上，而带 `Secure` 的 cookie **在明文 HTTP 上根本不会被浏览器存下来** ⇒「一律加 Secure」的表现是「本地演示谁都登录不了」 |
| `samesite` | **`lax`**（小写） | Starlette 只认 `"lax"`/`"strict"`/`"none"`/`False`；写 `"Lax"` 会原样落进响应头，而部分浏览器不接受大小写不对的 `SameSite`（于是它退化成缺省行为，CSRF 那一半论证就没了） |
| `domain` | **不设** | 不传 = 宿主限定，正是同源部署要的。写 `domain="localhost"` 会让 cookie 对 `*.localhost` 全部子域可见，那是计划 §3.5 那条 CSRF 论证**挡不住**的一档 |

守卫 `tests/auth/test_sessions.py::test_the_cookie_carries_exactly_the_documented_parameters`
（期望侧是**字面量** dict，不从 `cookie_kwargs` 反推；并断言 `"domain" not in kwargs`）
+ `test_secure_is_on_only_in_production`（六种非生产值 + 三种大小写/空白变体的生产值）
+ HTTP 层实测 `tests/api/test_auth_api.py::test_login_sets_the_cookie_with_the_documented_parameters`
（逐字扫 `Set-Cookie` 串，生产/非生产两档）。

### 4.2 ⚠️ 实测出来的坑：`expires=0` 渲染出的是**当前时刻**

`expired_cookie_kwargs()` 第一版写的是 `expires=0`（想着「= 1970-01-01T00:00:00Z」）。
**实测**登出的 `Set-Cookie`：

```
pe_session=""; expires=Mon, 12 Oct 2026 02:43:37 GMT; HttpOnly; Max-Age=0; Path=/; SameSite=lax
```

Starlette 把 `int` 的 `expires` 当成**「从现在起多少秒」**（`datetime.now(utc) + timedelta(seconds=expires)`），
不是 Unix 时间戳。一个「此刻到期」的 cookie 在边界上算不算过期由客户端决定。
**处置**：改成一个 **aware** 的 `datetime`（`EPOCH = datetime(1970,1,1,tzinfo=utc)`，
两种语义下都是同一个值；带 tzinfo 是因为 RFC 6265 的 `Expires` 一律按 GMT 渲染）。
`Max-Age=0` 仍是主判据（RFC 6265 里 `Max-Age` 优先于 `Expires`）。
⚠️ `expired_cookie_kwargs` **从 `cookie_kwargs` 派生**（只覆盖 `value`/`max_age`/`expires`），
因为 RFC 6265 的删除按 `(name, domain, path)` 三元组匹配，`path` 差一个字符就删不掉那一格
（表现为「登出之后又自动登进去」）；守卫
`test_the_expired_cookie_matches_the_live_one_on_every_matching_parameter` 钉住
「除了那三格，其余逐字相同」（生产档下 `secure` 也要相同，否则删不掉）。

### 4.3 滑动过期的实现

`resolve(db, token)` 走到最后一行才：

```python
row.expires_at = current + SESSION_TTL
row.last_seen_at = current
db.commit()
```

不变量：`expires_at - last_seen_at == SESSION_TTL` 恒成立，`last_seen_at - created_at` 是「用了多久」。
⚠️ **不做 refresh 令牌**（计划 §3.3 末段）：服务端持有那一行，故「活跃用户永不掉线、
不活跃用户两小时后掉线」同时成立，不需要两种令牌。
⚠️ **代价如实记**：每个带有效 cookie 的请求都写一次库（一次 `UPDATE`）。
原型是单进程 + SQLite，可忽略；生产要收敛有两条现成的路（只在剩余 TTL 低于一半时才推 /
把 `last_seen_at` 放内存定期落库），两条都**不在本计划里**。
⚠️ **不带 cookie 时 `resolve` 的成本是零次数据库访问**（第一档 `if not token` 在 `db.get` 之前就返回），
这正是 **1270 条既有测试一条都不用改**的原因。
守卫 `tests/auth/test_sessions.py::test_resolve_slides_the_expiry_and_updates_last_seen`
（判据是不变量、不是墙钟；并**换一个 Session** 读，证明它真的 commit 了）
+ HTTP 层 `tests/api/test_auth_api.py::test_the_sliding_expiry_pushes_expires_at_forward_on_an_authenticated_request`
（把 `expires_at` 拨到只剩 1 分钟 → 发一次请求 → 又变回整整一个 TTL）。

### 4.4 「过期 / 吊销不能用」的守卫

| 档 | 守卫 | 断言 |
|---|---|---|
| token 为空 / 空白 / 查无此行 | `test_resolve_returns_none_for_every_unusable_shape` | 三格都回 `None` |
| **已吊销** | 同上 + `test_revoke_writes_revoked_at_and_is_idempotent` | `None`；`revoked_at` 被写上；**行没有被删**（留痕）；第二次 `revoke` 回 `False` |
| **已过期** | 同上 | `None`，⚠️ 且 `revoked_at` **保持 NULL**（过期不等于被吊销：前者是审计事实、后者不是，混起来会让「谁在什么时候被踢了」失去答案） |
| 边界 `expires_at == now` | 同上 | `<=` 判，故恰好那一刻**也算过期**（否则一个 TTL 为 0 的会话会在签发的同一瞬间可用） |
| HTTP：登出后被偷的那一份 | `test_an_old_cookie_stops_working_the_moment_the_user_logs_out` | 登出 204 + `Set-Cookie` 过期；**显式把登出前那一串塞回 cookie jar** 再打 `me` → 401（⚠️ 只靠 `TestClient` 的 jar 的话，第一拍的 `Set-Cookie` 已经把它清掉了，第二拍打出去的是「没有 cookie」——那当然是 401，证明不了「被偷的那一份失效了」） |
| HTTP：过期 | `test_an_expired_session_is_401_but_is_not_marked_as_revoked` | 401 + `revoked_at is None` |
| HTTP：伪造 / 别库签发 / 空串 | `test_a_forged_or_foreign_cookie_is_401` | 三档 401；另加「两个学生的 token 不串号」 |
| HTTP：跨 kind | `test_a_cookie_of_one_kind_cannot_be_used_as_the_other` | 教师 cookie 打学生端点 → **403**（不是 401：请求者已经登录了，只是不是这一类人）；反之亦然 |

### 4.5 `role` 冗余的落地

见 **2.4**（含实测更正与两条守卫）。

---

## ⑤ 五个端点逐个（`app/api/routers/auth.py`）

⚠️ **是 5 个不是 6 个**（计划自审第 4 条自己抓出来的数错，实现者确认）：
另一个会话里的《实施计划 05》数出 6 个是因为它有 **refresh**，本计划不做 refresh、改用滑动过期。

| # | 路径 | 方法 | 身份 | OpenAPI `security` | 成功码 |
|---|---|---|---|---|---|
| 1 | `/api/auth/students/bind` | POST | **匿名** | 无 | **204**（无响应体，**不自动登录**） |
| 2 | `/api/auth/teachers/bind` | POST | **匿名** | 无 | **204** |
| 3 | `/api/auth/login` | POST | **匿名** | 无 | **200** + `Set-Cookie` + 六格身份 |
| 4 | `/api/auth/logout` | POST | **cookie 会话** | `[{"pe_session": []}]` | **204** + `Set-Cookie` 过期 |
| 5 | `/api/auth/me` | GET | **cookie 会话** | `[{"pe_session": []}]` | **200** + 六格身份（与 login 逐字同形） |

### 5.1 请求体字段

| 端点 | 字段（`model_fields` 的声明序） |
|---|---|
| `students/bind` | `student_no: str`、**`birth: dt.date`**（⚠️ 顶回：不是 `birth_date`）、`password: SecretStr` |
| `teachers/bind` | `staff_no: str`、`name: str`、`password: SecretStr` |
| `login` | `kind: str`（`one_of` → `UserSession.KINDS`）、`login: str`（**一个字段装学号或工号**）、`password: SecretStr` |

⚠️ **`login` 用一个字段而不是两个可选字段**：两个可选字段要一条「恰好一个非空」的互斥校验，
而 Pydantic 表达它要靠 `model_validator`，出错时 `loc` 是 `("body",)`（指不到具体字段），
前端不知道该把红框画在哪个输入框上。一个字段 + 一个 `kind` 下拉框与计划 §4.1 的登录页形状逐字对应。
⚠️ **`kind` 只有两个值，管理员不在里面**（管理员就是一行 `role='admin'` 的 `teacher`，
用 `kind="teacher"` 登录，前端按响应体的 `role` 决定跳 `/admin` 还是 `/t/dashboard`）。
⚠️ **`password` 是 `SecretStr`**，理由与它**挡不住**的那一档逐字见 `app/api/schemas/auth.py` 的模块 docstring。

### 5.2 响应体（`SessionIdentityRead`，六格，login 与 me **逐字同形**）

```json
{"kind": "student", "id": 1, "name": "张三", "role": "student",
 "student_no": "S2025001", "staff_no": null}
```

⚠️ `student_no` / `staff_no` **互斥**（学生那一档只填前者）。两格而不是一个 `login` 的理由：
前端要按 `kind` 显示「学号」或「工号」两个不同的中文标签，一个字段名给不出标签；
而 `Identity.login` 那一格是给**服务端闸门**用的（`require_staff` 一族以工号为主语）。
守卫 `test_login_and_me_return_exactly_the_same_body_and_role_decides_the_landing`
（三种身份各一份**字面** dict，且 `login` 与 `me` 逐字相等；并断言管理员的 `kind` 仍是 `"teacher"`）。

### 5.3 每一档错误的 code 与状态码（逐个）

三个自定义 code 的唯一住址是 `app/api/routers/auth.py` 的三个常量
（`PASSWORD_ALREADY_BOUND` / `PASSWORD_NOT_BOUND` / `INVALID_CREDENTIALS`）。
⚠️ 它们**不走** `HTTPException`：`app.api.errors._CODE_BY_STATUS` 只能按状态码折出六个 code，
故这三个经 `error_response(...)` 直接出去（那是全仓唯一写 `{"error": {...}}` 这个字面量的地方，
**单一所有者没有被绕过**）。⚠️ 从端点里 `return error_response(…)` 而不是 `raise` 是可以的：
FastAPI 见到返回值是 `Response` 实例就原样发出、**不经过** `response_model` 校验，
故一个 204 的端点也能回一个 409 的 JSON 体。

**`POST /api/auth/students/bind`**（`teachers/bind` 逐档同构，只有 message 里点的是「工号」）

| 档 | 码 | `code` | message | 顺序为什么在这里 |
|---|---|---|---|---|
| 口令 < 8 字符 | **422** | `unprocessable_value` | 「口令至少 8 个字符（收到 N 个）。⚠️ 本原型不做复杂度规则、也不做找回，故请自己记牢」 | **排最前**：纯本地判定、不碰库，故一次弱口令尝试不会变成一次数据库查询（一个不需要账号就能打出来的 DoS 面） |
| 请求体缺字段 / `birth` 不是合法日期 | **422** | `request_validation_failed` | 「请求参数校验未通过」+ `detail`（⚠️ **已按键名脱敏**，见 5.4） | Pydantic 那一档 |
| 学号**不在册** | **403** | `forbidden` | **「学号或验身材料不正确，无法绑定口令」** | ⚠️ 与下一档**共用 code + 共用同一句 message** |
| 出生日期**不符** | **403** | `forbidden` | **同上，逐字相同** | 区分两者等于把「哪些学号在册」逐个字告诉一个匿名调用方。⚠️ 实现是**一个 `or`**，不是两个 `if`：分开之后「顺手给第二档换一句更具体的 message」就会把信号泄漏出去 |
| 已经绑定过 | **409** | `password_already_bound` | 「这个学号已经绑定过口令了：一个账号只能绑定一次。⚠️ 本原型不做口令找回，故忘了口令要找教务干事重灌那一行（把 `student.password_hash` 置回 NULL）」 | ⚠️ **排在 403 之后**：反过来的话，一个不知道出生日期的攻击者就能读出「这个学号绑定过了没有」——那正是上一档要防的信号，从一个别的口子漏出去 |
| 成功 | **204** | — | 空体、**无 `Set-Cookie`** | 绑定成功即已认证的话，「验身材料泄漏」就直接等于「账号被接管」 |

守卫：`test_bind_student_success_is_204_and_stores_a_verifiable_hash`、
`test_bind_student_gives_the_same_code_and_message_for_a_stranger_and_a_wrong_birth`
（三拍，含**两个响应体逐字相同** + 「message 里不得出现学号 / `不在册` / `出生`」）、
`test_bind_student_the_error_tiers_are_in_the_documented_order`（含「用错的出生日期打一个**已绑定**的学号 → 403 而不是 409」那一拍）、
`test_bind_teacher_is_the_same_shape_with_staff_no_and_name`（含「多带一个 `role` 键被忽略、`teacher.role` 仍是 `teacher`」）。

**`POST /api/auth/login`**

| 档 | 码 | `code` | 备注 |
|---|---|---|---|
| `kind` 不在 `{student, teacher}` | **422** | `request_validation_failed` | 走 `one_of` |
| 请求体缺字段 | **422** | `request_validation_failed` | ⚠️ `detail` **不回显口令**（见 5.4） |
| 学号/工号**不在册**，或在册但 `password_hash IS NULL` | **403** | `password_not_bound` | message 引导用户去绑定 |
| 口令**不对** | **401** | `invalid_credentials` | message「口令不正确」 |
| 成功 | **200** | — | `Set-Cookie` + 六格身份 |

⚠️ **两档必须区分**（计划 §3.3），而它**确实泄漏「这个学号在不在册」**——控制者裁定接受，
三条理由（原型不做防枚举 / 绑定流程本身需要这个信号，不然用户不知道自己是「没注册」还是「口令错」，
而两者的下一步动作**相反** / `GET /api/students` 今天就匿名返回全部 60 人）。
⚠️ 于是它与 `students/bind` 的口径**相反**（那里两档要不可区分，这里两档要可区分），
两处各写一段散文说明、刻意不合并。守卫 `test_login_distinguishes_not_bound_from_a_wrong_password`
（三档 + 「两档的 message 必须不同」）。
⚠️ **不做登录失败计数 / 账号锁定**（计划 §1 的非目标）。代价如实记：
一个知道学号的人可以无限次试口令，而 600 000 次迭代意味着**服务端**每次尝试要花 ~0.3 s，
于是「试口令」同时是一个**廉价的 CPU DoS**。已登记为待清扫。

**`POST /api/auth/logout`**

| 档 | 码 | `code` |
|---|---|---|
| 没有有效会话（未登录 / 已过期 / 已吊销） | **401** | `unauthenticated`（由 `deps.current_session` 抛） |
| 成功 | **204** | 空体 + `Set-Cookie` 过期 |

⚠️ **cookie 设在「本函数返回的那一个 `Response` 实例」上，不是注入的 `response` 参数上**。
这是承重的：FastAPI 只在端点**返回非 `Response` 对象**时才把注入响应的 headers 合并进最终响应
（`get_request_handler` 的 else 那一支才有 `response.headers.raw.extend(sub_response.headers.raw)`）。
于是「注入 `response` + `set_cookie` + `return Response(status_code=204)`」这个看起来很自然的写法会
**静默丢掉那个 `Set-Cookie`**——表现为「登出成功了、服务端那一行也吊销了，而浏览器的 cookie 还在」，
于是下一次请求带着一个已吊销的 cookie 撞 401，而不是干净地回到登录页。
⚠️ `login` 那一侧**不受影响**（它返回 dict + `response_model`，走的正是会合并 headers 的那一支）。
⚠️ **幂等**的准确含义是「服务端不会因为重复登出而报错或改坏数据」（`revoke` 对已吊销的 token 回 `False`），
**不是**「重复登出回同一个码」——第二次会先撞 401。如实记录。

**`GET /api/auth/me`**

| 档 | 码 | `code` |
|---|---|---|
| 没有有效会话 | **401** | `unauthenticated` |
| 成功 | **200** | 六格身份 |

⚠️ **它与 `logout` 都刻意不回落请求头**（`deps.current_session` 的 docstring 逐字写了理由）：
一个由请求头伪造出来的「我是谁」既没有 `Set-Cookie` 可种、也没有 `user_session` 行可吊销，
于是 `logout` 会变成一件什么也不做的事、`me` 会变成一句谎话（它回不出 `role`，
因为请求头那一档没有 role）——而前端的路由守卫（`/admin/*` 要 `role == 'admin'`）
会拿到一个 `undefined`，失效方向是安全的（少给权限），但形状是
「管理员进了 `/admin` 看到一句『你不是管理员』」，离真因很远。

### 5.4 ⚠️ 计划完全没提、实现者实测出来的第二个洞：422 逐字回显明文口令

**取证**（改之前）：

```
POST /api/auth/login {"kind":"student","password":"我的超级机密口令"}     # 漏了 login
→ 422 {"error":{"code":"request_validation_failed","message":"请求参数校验未通过","detail":[
       {"type":"missing","loc":["body","login"],"msg":"Field required",
        "input":{"kind":"student","password":"我的超级机密口令"}}]}}
```

Pydantic v2 的 `errors()` 每一格都带 `input`，而 `missing` 那一档的 `input` 是**整个请求体**。
它泄漏给的是**提交它的那个人**（不是第三方），故不是越权；但那份响应体会被浏览器 devtools、
反代访问日志、APM 采样与前端错误上报各存一份，而口令是**跨系统复用**的
（用户拿同一个口令登别的站是常态）。CWE-209 / CWE-532 那一类。

⚠️ **`SecretStr` 挡不住这一档**：`missing` 发生在**任何字段被解析之前**，
故 `input` 里那一格还是原始 `str`。`SecretStr` 只挡「`password` 字段自己校验失败」那一档。

**处置**（`app/api/errors.py`）：一层**按键名**的递归脱敏
（`_SENSITIVE_INPUT_KEYS = {"password", "password_hash", "rpe_token"}` → `_REDACTED = "***"`），
外加「`loc` 的末段是敏感键名时，`input` 整格脱敏」（与字段类型无关，
故将来有人把一个口令字段写成裸 `str` 时它仍然挡得住）。**两道合起来才封住。**
⚠️ 按**键名**而不是按端点路径：按路径就要维护一份「哪些路径收口令」的清单，
而加第 6 个鉴权端点时忘了加进去是静默的；按键名的失效方向是安全的
（多脱敏一个不敏感的键，只是 422 的 `detail` 里少一格调试信息）。
⚠️ `loc` 与 `msg` **原样保留**，故前端仍然说得出「哪一格错了」。
守卫：`tests/api/test_auth_api.py::test_a_validation_error_never_echoes_the_submitted_password`
（7 个端点 × 失败形状，逐个断言那个明文串**不出现在响应体的任何位置**，
+ 反空转「`loc` 里仍然点名 `password`」+「那个串确实被提交上去了」）
与 `…::test_the_redactor_is_recursive_and_only_keyed_on_the_name`
（递归 / list 展开 / **只认键名**：一个值等于口令但键名不敏感的格子**不脱敏**，
那是已知且被接受的边界，不是待修的 bug）。

### 5.5 双通道（`app/api/deps.py`）

`PE_ALLOW_HEADER_IDENTITY` 缺省 **`"0"`**（`ALLOW_HEADER_IDENTITY_DEFAULT`），
只有字面 `"1"` 算开（`"true"`/`"yes"`/`"2"` 都算关；失效方向是安全的——
写错一个值会**关掉**过渡通道，表现为测试全 401，响亮）。
**在请求时读环境变量**（口径与 `_csv_dir` / `iterations()` 相同）。

| 依赖 | cookie 是学生 | cookie 是教师 | 没有 cookie |
|---|---|---|---|
| `current_student` | → `subject_id` | → **403 `forbidden`** | 通道开：有头用头、缺头 401；**通道关（生产缺省）：一律 401，请求头被完全忽略** |
| `current_teacher` | → **403 `forbidden`** | → **工号**（`Identity.login`） | 同上 |
| `current_session`（新） | → `Identity` | → `Identity` | → **401**，⚠️ **永不回落请求头** |

⚠️ **403 而不是 401**：请求者**已经登录了**，只是不是这个端点要的那一类人
（`unauthenticated` 说的是「我不知道你是谁」，而这里我们知道）。与 `require_scope` 同一条口径。
⚠️ **`current_teacher` 交出的是工号字符串**（两档同形），故教师侧全部闸门
（`require_staff` 一族）与写进 `prescription.teacher_overrides` 的 `teacher_staff_no` 那一格
**一行都不用改**——这是「双通道过渡」能不动 1270 条测试的第二个原因
（第一个是「不带 cookie 时 `resolve` 零次数据库访问」）。
守卫 `test_a_cookie_identity_reaches_the_same_gates_as_the_header_one`
（同一个端点、两条通道，状态码与 `code` 逐字相同，且 message 里含那个工号）。

⚠️ **缺省是 0 的那条守卫**：
`tests/api/test_auth_api.py::test_the_header_identity_channel_is_closed_by_default`，四拍：
① `ALLOW_HEADER_IDENTITY_DEFAULT == "0"`（字面量）；② `monkeypatch.delenv` 后
`allow_header_identity() is False`；③ **重建一个 app**（`create_app(db_url="sqlite://")`），
匿名带 `X-Student-Id: 1` 读 `/api/students/1/home` → **401 `unauthenticated`**，
教师那一侧同样（`/api/teacher/students/1/weekly-sheet` + `X-Teacher-Staff-No`）；
④ **对照拍**：把开关打开，同一个请求**不是 401**（是 403，因为 `require_scope`
的第二支查不到那个在册学生）——少了这一拍，「把 `current_student` 改成一律抛 401」也能让 ③ 绿，
而那会毁掉全部 1270 条既有测试所依赖的那条通道。
⚠️ 它的绿档半边另有 `test_the_header_channel_still_carries_the_existing_1270_tests`：
那 1270 条测的是**业务规则**（只是顺带用了请求头），没有一条的**主语**是「请求头通道开着」；
少了本条，「把过渡通道整个删掉」会红在 1270 个离真因很远的地方，
而报错信息里没有一处会提到 `PE_ALLOW_HEADER_IDENTITY`。

### 5.6 ⚠️ 一处「计划/我本以为的行为」被实测推翻（已按实际改写）

`current_student` 的 docstring 第一版写的是「带 cookie 时『非整数的头 → 422』那一格不再触发」。
**实测是错的**：FastAPI 在**依赖体运行之前**就把 `Header` 参数解析并校验完了，
故 `X-Student-Id: abc` + 一个有效的 cookie 得到的是 **422**、不是 200。
于是「生产档下请求头被忽略」要精确到：请求头**不参与身份判定**，但它**仍然被解析**。
如实记录（硬规矩 #39）：它不构成漏洞（两个码都拒绝访问），
但一个「顺手带着历史请求头」的前端在生产档下会看到 422。
彻底摘掉它要把标注从 `int | None` 改成 `str | None` 并自己转 `int`——
而那会让「非整数的头」折成 **422 `unprocessable_value`** 而不是既有的
**422 `request_validation_failed`**（`tests/api/test_scope.py::test_a_non_integer_identity_header_is_422`
钉住了后者），为一个不影响安全的形状去改一个既有 code 不划算。
守卫 `test_a_malformed_identity_header_is_422_even_next_to_a_valid_cookie`
（并含一拍「一个**合法但属于别人**的头在带 cookie 时完全不起作用」——那一格才是「忽略请求头」的真意思）。

---

## ⑥ Task 2：授权口径改造

### 6.1 `require_admin` / `require_staff` 的落地位置

| 名字 | 住址 | 判定 | 消费者 |
|---|---|---|---|
| `require_staff(session, staff_no) -> str` | `app/api/deps.py`（**由 `require_teacher` 改名**，返回 role） | 在册教职（`teacher` 表里有这一行 **且** `role ∈ {teacher, admin}`）→ 403 否则 | `alerts.py`（`alerts/{id}/handle`）、`feedback.py` ×4（`open-rpe` / `rpe-token` / `rpe-status` / `mini-tests/batch`）、`pipeline.py`（`run-daily`）、`prescription.py` ×2（`overrides` / `regenerate`）、以及 `require_teaches_section` / `require_teaches_student` 内部 |
| `require_admin(session, staff_no) -> str` | `app/api/deps.py`（**新增**） | `require_staff` + `role == 'admin'` → 403 否则 | `app/api/crud.py::_require_admin_identity` ← `build_crud_router(require_admin=True)` ← `RESOURCES` 的 **9 行**，即 9 × POST/PATCH/DELETE = **26** 个写入操作 |
| `require_teaches_section` / `require_teaches_student` | `app/api/deps.py`（**加管理员越过那一支**） | `require_staff(...) == ADMIN_ROLE` → **直接返回** | `dashboard.py` ×4（班级大屏 / 班级周报 / 教师端读单个学生的 weekly-sheet 与 home） |
| 常量 | `ADMIN_ROLE = "admin"`、`STAFF_ROLES = frozenset(Teacher.ROLES)` | — | 词表的唯一所有者仍是模型类常量（本包约定 2） |

⚠️ **`require_teacher` 没有保留**：它会与 `require_staff` 同义，而「两个公开名、一个判定」
是本仓最反对的形状。起点那 **89 处**（12 个文件）一并处理：**35 处 → `require_staff`**、
**54 处 → `require_admin`**；另在解释「这一格此前叫什么」的散文里**刻意**留下 **6 处**历史提及
（`git grep -c require_teacher -- backend` 今天仍报 6 处，全在散文里：`deps.py` 2、`crud.py` 2、`catalog.py` 2）。

### 6.2 ⚠️ 顶回 3：计划 §3.6 第 3 条在行为上是 **no-op**

计划写的是「**新增**一个 `require_staff` 依赖 = `role in {"teacher","admin"}`」，
把 `open-rpe` / `rpe-token` / `mini-tests/batch` / `alerts/{id}/handle` / `teacher/students/*` 改成它，
理由是「管理员接管的是管理台，不是把教师赶出课堂功能」。

**实现者实测：那一格在行为上什么都没改。** 旧 `require_teacher` 的实现是

```python
if session.scalar(select(Teacher.id).where(Teacher.staff_no == staff_no)) is None:
    raise HTTPException(403, ...)
```

它**从不看 role**（`role` 这一列在 Plan 05A 之前根本不存在），而**管理员就是一行 `teacher`**
（用户裁定「接管管理台」落地成一个标签、不是第三张表），故它本来就放行管理员。

**结论：控制者的产品判断（「教师保留课堂功能」）是对的，而它诊断的动作（「新增一个依赖」）是多余的。**
真正需要做的三件事：① **改名**（让「教师或管理员」在名字上成立，否则下一个人会以为
`require_teacher` 只放行 `role='teacher'`）；② **返回 role**（`require_admin` 与两道任教闸门要用它）；
③ **显式校验 role 的取值域**（把计划那句 `role in {"teacher","admin"}` 变成可执行的，
今天恒真、故是**许可而不是断言**，它挡的是「有人绕过 ORM 直接写库」与
「将来给 `ROLES` 加第三个值而 HTTP 层的口径没跟着定」——后者会让那个新角色**静默地**
拿到全部课堂功能的权限）。
守卫 `tests/api/test_auth_api.py::test_require_staff_admits_both_roles_while_require_admin_admits_only_one`
（四档失败逐个点名 + 「两档 message 必须不同」）与
`…::test_a_plain_teacher_keeps_the_classroom_endpoints_and_loses_the_console`
（**课堂功能保留**那一半：普通教师读自己那个班的大屏仍是 200、读别人的班仍是 403；
**管理台失去**那一半：同一个教师 POST 一个学期是 403、管理员是 201）。

### 6.3 ⚠️ 管理员越过任教范围闸门的**实测复核结果**（派单 §4 第 2 条）

派单要求复核「一个不带任何班的教师今天访问 `/api/dashboard/class/{id}` 会发生什么」。
**探针**：`$env:TEMP\pe05a_probe\p05_admin_gate.py`（空库 + 一个宽学期 + 三个教师
（带班的 T1 / 不带班的 T2 / 不带班的管理员 A1）+ 一个学生 + 一个归 T1 的班 + 一条选课行）。

| 端点 | 带班教师 T1 | **不带班教师 T2** | 管理员 A1（不带班） |
|---|---|---|---|
| `GET /api/dashboard/class/1` | **200**（回整屏） | **403**「教学班 1 不是教师 'T2' 任教的班（或这个班不存在）：判据是 `course_section.teacher_id`」 | **200**（与 T1 逐字同形） |
| `GET /api/dashboard/weekly-class-report/1` | **404** `no_weekly_report` | **403**（同上） | **404** `no_weekly_report` |
| `GET /api/teacher/students/1/weekly-sheet` | **404** `no_active_prescription` | **403**「学生 1 不在教师 'T2' 于学期 1 任教的任何教学班里」 | **404** `no_active_prescription` |
| `POST /api/semesters` | **403**「身份 'T1' 不是管理员（`teacher.role == 'teacher'`）」 | **403**（同上） | **201** |
| `POST /api/semesters`（匿名） | **401** | **401** | **401** |

**复核结论：控制者的推论在代码里成立。** 闸门确实按任教关系判（404 说明「已过闸门、只是没数据」，
403 说明「闸门给的」），而不带任何班的人——**管理员的常态**——确实一律 403。
故不放行的话，管理员登录进 `/admin` 之后点教师大屏会**全部 403**，
`role='admin'` 就只剩「能改管理台」这一半意义。
守卫 `test_an_admin_passes_the_teaching_gates_that_stop_a_classless_teacher`
（三个端点 × 三种身份，且断言「管理员与**带班教师**同一档、而不是与不带班的教师同一档」；
请求头与 cookie **两条通道各测一次**）。
⚠️ **代价（硬规矩 #39）**：管理员因此能读**全校任何班、任何学生**的数据，
而本仓没有「哪个教务干事管哪个院系」这一格。原型可接受（一个学校通常只有一两个干事），
已登记为关切、待写进 spec §13。

### 6.4 两条既有守卫改成了什么

**① `test_every_writable_resource_rejects_an_anonymous_mutation`
→ `test_every_writable_resource_admits_only_an_admin_mutation`**（`tests/api/test_crud.py`）

从两拍扩成**三拍**（匿名 **401** / 普通教师 **403** / 管理员**放行**），
函数名也改了：旧名只说了第一拍，而本条今天守的是「**恰好**管理员能写」——
一个只守「匿名被挡」的名字会让下一个人以为「教师也能写」是本条认可的现状。
连带改名的散文引用 **6 处**（`app/api/crud.py` 2、`app/api/routers/catalog.py` 2、
`app/api/routers/__init__.py` 1、`tests/api/test_prescription_api.py` 1）。

⚠️ **「管理员放行」那一拍用的是 `PATCH {}` → 200，不是 POST → 201**（对派单「管理员 201」的一处偏离，
记在 §7.3）：`{}` 会让 POST 落到 **422**（请求体校验），而 422 与 200 都只证明「闸门放行了」，
但 422 **证明不了**写入真的能成；而 `PATCH {}` 因为 `exclude_unset=True` 是「一个键都不改」，
故 9 个资源**共用同一份请求体**就能拿到 200。
「管理员真的能建一行、真的能删一行」另开一条
`test_an_admin_can_create_and_delete_while_a_teacher_cannot`：
POST → **201** + `Location` 头、PATCH → 200、DELETE → **204**、
缺省 `role` 是 `teacher`（少给权限，不是多给）、`role` 可由管理员显式给出（提权）、
`role` 的取值域由 **Pydantic** 判 → **422 `request_validation_failed`**（不是 DB CHECK 的 409）。
两条守卫**并列、不合并**：前者管「9 个资源逐个都放行管理员」（`admitted == 9` 反空转），
后者管「放行之后写入真的走得通」。
⚠️ 新增的 `plain_teacher_headers` 夹具是 `admin_headers` 的**红档半边**（硬规矩 #50）：
少了它，「把 `require_admin` 改回 `require_staff`」是**静默**的（全部写入测试照旧全绿，
因为管理员也是一种教职）——而那正是本 Task 要防的那一次退化。
`teacher_headers` → `admin_headers` 全文件 **39 处**、`TEACHER_STAFF_NO` → `ADMIN_STAFF_NO` **4 处**
（⚠️ 用 `TEACHER_STAFF_NO(?!_SCHEME)` 的负向预查，否则会连带把 `TEACHER_STAFF_NO_SCHEME` 改坏）。

**② `test_the_identity_headers_are_registered_as_openapi_security_schemes`
→ `test_the_identity_schemes_are_registered_as_openapi_security_schemes`**（`tests/api/test_prescription_api.py`）

⚠️ 改名（`headers` → `schemes`）是因为第三个 scheme `pe_session` 是 `in: cookie` 的、不是请求头；
连带 3 处散文引用（`test_feedback.py` / `test_end_to_end.py` / `test_dashboard.py` 各一处）。
它的 docstring 逐字写着「每加一个带身份的特例端点都要回来加一行——这是**有意的**」，
故本波改它是它的**正常演化**。改了六格：

| 格 | 起点 | 现在 |
|---|---|---|
| `sorted(schemes)` | `["X-Student-Id", "X-Teacher-Staff-No"]` | `["X-Student-Id", "X-Teacher-Staff-No", "pe_session"]` |
| 每个 scheme 的 `in` | 一律 `"header"` | 按一份**字面** dict 分两档（两个 `header` + `pe_session` 是 `cookie`）。⚠️ 写反的后果是具体的：生成的 TS 客户端会去发一个名叫 `pe_session` 的**请求头**，而服务端读的是 `request.cookies`，于是前端「照 spec 写了」却恒 401 |
| `expected` 清单 | **20** 项 | **22** 项（+ `("/api/auth/me","get")` 与 `("/api/auth/logout","post")`，两格值是 `"pe_session"`——本清单里**唯一**两格不是请求头名的） |
| 挂 `security` 的操作数 | **46**（20 + 26） | **48**（22 + 26） |
| 新增一拍 | — | 「`pe_session` 恰好挂在那两个 auth 操作上」（少了它，「把 cookie scheme 也挂到 26 个 CRUD 写入上」会让上面两格一起红，而报错信息指向算式、不是「谁挂错了」） |
| `crud` 那一圈的空转下界 | `>= 70` | **不抬**（实测 74 → 77；它是「本拍没空转」的地板，不是「有多少个 CRUD 操作」的登记处） |

⚠️ **口径为什么又变了**（写进了那条守卫的 docstring）：这两格既不是「按人收窄的读端点」
（前面 20 格的那条理由），也不是「管理台的写操作」——它们说的是**会话本身**。
「我是谁」与「把我登出」两件事的判据只能是那个 cookie，
故它们挂 cookie scheme 是本仓第一次出现「`security` 的值不是请求头名」。
⚠️ 而 `/api/auth/*` 的另三个端点（两个 bind + login）**刻意不挂**：它们就是拿来**换** cookie 的，
要求 cookie 就成了「先登录才能登录」。

### 6.5 收红（硬规矩 #88：先跑一次全量、把红掉的逐个收进来）

改完 Task 2 跑全量 → **4 条既有测试红**，根因**同一个**：它们用普通教师写管理台
（`class_session` 是 9 个可写资源之一）。

| 测试 | 处置 |
|---|---|
| `test_feedback.py::test_a_session_created_over_http_has_a_null_batch_id_and_survives_replay` | 新增 `ADMIN_HEADERS`（`A2025001`，`_seed` 里多插一行 `role='admin'`），把那一发 `POST /api/class-sessions` 换过去 |
| `test_feedback.py::test_the_rpe_token_route_is_409_when_there_is_no_token_to_read` | 同上（那一发 `PATCH /api/class-sessions/{id}`） |
| `test_feedback.py::test_submitting_rpe_fills_submitted_at_server_side` | 同上（那一发 `POST /api/class-sessions`） |
| `test_end_to_end.py::test_the_whole_loop_runs_over_real_http` | 把全链路那**一个**身份提成管理员（`seed_database` 建的教师一律是缺省的 `role='teacher'`，故在夹具里显式 `teacher.role = "admin"`）。理由：全链路要用同一个身份打**两类**端点（管理台的 `POST /api/class-sessions` ×3 与课堂功能的 `run-daily` / `open-rpe` / `mini-tests/batch` / `alerts/{id}/handle`），故那个身份必须同时是管理员——现实里跑演示与录数据的那个人正是教务干事 |

⚠️ **`test_feedback.py` 里只换了那 3 处，其余教师侧调用一律仍用 `TEACHER_HEADERS`**：
`open-rpe` / `rpe-token` / `rpe-status` / `mini-tests/batch` 是**课堂功能**，教师保留。
于是那个文件**同时是**「课堂功能保留」的回归守卫——把 `TEACHER_HEADERS` 一律换成
`ADMIN_HEADERS` 会让它全绿，而 `tests/api/test_auth_api.py` 会红（这条互锁关系写在了
`ADMIN_HEADERS` 的注释里）。

⚠️ Task 1-C 也收过一次红（1 条）：`test_the_identity_headers_…` 的
`sorted(schemes) == [...]`（+ `pe_session`），处置见 6.4 ②。

---

## ⑦ 待清扫 / 关切 / 没按派单做的地方 / 顶回

### 7.1 待清扫（12 条）

| # | 条目 | 归谁 |
|---|---|---|
| 1 | **撤掉 `demo.ps1` 的 `PE_ALLOW_HEADER_IDENTITY=1`**（有意的过渡态；前端登录页落地之后演示库就不该再接受伪造的请求头） | Task 5 |
| 2 | **`user_session` 的过期行清理任务**（原型不做定时进程，故那张表单调增长；`DELETE FROM user_session WHERE expires_at < now − 7 天`）。⚠️ 是**空间**问题、不是安全问题——「过期/吊销不能用」有守卫 | 生产 |
| 3 | **登录端点的速率限制**（600 000 次迭代 ⇒ 一个请求换服务端 ~0.3 s，「试口令」同时是一个廉价的 CPU DoS；计划 §1 的非目标逐字列了「登录失败锁定」，但没提 DoS 这一面） | 生产 |
| 4 | **CSRF 双重提交令牌**：仅当部署改成**跨源**时才需要（那时还要 ① `allow_origins` 显式白名单 ② `allow_credentials=True` ③ cookie 加 `Secure` **且** `SameSite=None`）。原型按同源部署，故计划 §3.5 那两条（`SameSite=Lax` + 变更类请求必须带 JSON body ⇒ 触发预检）够用。⚠️ 那句「若生产改成跨源，这条论证就失效」要**逐字**写进 spec | Task 5 / 生产 |
| 5 | **`GET /api/students` 今天匿名返回全部 60 人的 `birth`，而 `birth` 正是学生的绑定验身材料**；`GET /api/teachers` 同理返回 `name`（教师的验身材料之一）。⚠️ 于是「绑定要验身材料」这件事的防护强度**受限于那 48 个匿名 GET** | **Task 5（必须收紧）** |
| 6 | **`password_bound_at` 匿名可读**（`StudentRead` / `TeacherRead` 都含它），故匿名调用方能读出「哪些学号/工号已注册」。⚠️ 与计划 §3.3 已裁定接受的那一档泄漏同源（登录的两档 code 本身就给出这个信号），但它是**列表级**的、一次拿全部 | Task 5 一并裁定 |
| 7 | **`require_staff` + `_teacher_id_of` 是两次查询**（在册那一档）。收敛成一次要把 `_teacher_id_of` 改成返回 `(id, role)` 并让 `require_staff` 复用它——一次签名改动、不是一次语义改动，超出本 Task 范围 | 后续 |
| 8 | **`revoke_all_for(kind, subject_id)`（「一键登出全部设备」）没做**：`logout` 只吊销当前这一个会话，多设备登录是合法状态 | 后续 |
| 9 | **`demo_bootstrap.py` 要给演示库的学生/教师绑定一个已知的演示口令并打印出来，还要造出第一个管理员**（`POST /api/teachers` 仅管理员可调，故第一个管理员只能由脚本直接写 ORM）。⚠️ **今天演示库上管理台的写操作一律 403**，`demo.ps1` 的打印已经写明这一点 | **Task 4** |
| 10 | **spec §1.2 与 §13 要改**（§13 加「登录」那一节：五个端点、cookie 的六格、`Swagger UI 设不了 HttpOnly cookie 故 /docs 上要先打 login`、冗余 role 的真实代价、管理员越过任教闸门的权限放大、跨源部署那一档） | Task 5 |
| 11 | **重启那个还起着的 uvicorn（`127.0.0.1:8000`，PID 19068）并删掉旧的 `pe_demo.db`**：它跑的是上一波的代码，而 `create_all` 不会给已存在的表补那 5 个新列 | 控制者 |
| 12 | **`Teacher.ROLES` 与 `UserSession.ROLES` 是两份词表**（后者 = 前者 ∪ `{student}`），一致性靠守卫而不是靠构造。⚠️ 若给 `Teacher.ROLES` 加第三个角色（例如 `principal`）而忘了加会话那一份，失效形态是**登录时一个 409 `integrity_conflict`**，离真因隔一整层 | 后续 |

### 7.2 关切（6 条，硬规矩 #39）

1. **管理员能读全校任何班、任何学生**（越过了任教范围闸门），而本仓没有「哪个干事管哪个院系」这一格。
2. **绑定端点的验身材料本身匿名可读**（学生的 `birth`、教师的 `name`）：
   它挡的是「不知道材料的人」，**不挡**「读过那两张列表的人」。计划 §3.2 自己点出了这个权衡。
3. **登录泄漏「这个学号在不在册」**（403 `password_not_bound` vs 401 `invalid_credentials`）：
   控制者裁定接受（三条理由见 5.3）。
4. **每个带有效 cookie 的请求都写一次库**（滑动过期）。原型可忽略，生产的两条收敛路见 4.3。
5. **一个格式错的 `X-Student-Id` 在带有效 cookie 时仍然 422**（FastAPI 在依赖体之前就解析了 Header）。
   不构成漏洞（两个码都拒绝访问），但「生产档下请求头被忽略」这句话要精确到「不参与身份判定、仍然被解析」。
6. **三个写入端点仍然只过在册闸门、不过任教关系闸门**（`POST …/overrides` / `POST …/regenerate` /
   `POST …/alerts/{id}/handle`）：任何在册教师（含管理员）可以覆盖任何学生的处方。
   ⚠️ **这一条是 Plan 03 Task 8 就登记过的既有关切，本波没有改它**（收窄它们是一次一行的改动：
   `require_staff` → `require_teaches_student`，但那会改掉 Plan 04 教师端的可点范围，超出本波范围）。

### 7.3 没按派单做的地方（**4 处**）

| # | 派单/计划说的 | 我做的 | 理由 |
|---|---|---|---|
| 1 | §3.1「`_MODELS_PUBLIC_BASELINE` **33 → ?**（新增 `UserSession` 等公开名）」+「`models/__init__.py` 的 `__all__` 要加」 | 基线**仍 33**、`__all__` **一个字没动**、`UserSession` 按子模块引用 | **顶回 1**（见 2.5）：与 Ruling 97 及其在场守卫直接冲突，而 Plan 02 Task 6 已经为同一件事顶回过一次派单 |
| 2 | §2.1「`app/config.py` 加 `PE_ALLOW_HEADER_IDENTITY`」 | 加在 **`app/api/deps.py`**（`ALLOW_HEADER_IDENTITY_ENV_VAR` / `ALLOW_HEADER_IDENTITY_DEFAULT` / `allow_header_identity()`） | **顶回 4**（见 7.4）：本仓已有**三处**同型先例，且 `config.py` 自己的 docstring 逐字写着「只 import `pathlib`」 |
| 3 | Task 2 验收「那条遍历型守卫扩成三拍（匿名 401 / 教师 403 / **管理员 201**）」 | 三拍是 401 / 403 / **`PATCH {}` → 200**（9 个资源逐个），另开一条测 **POST → 201** + DELETE → 204 | 见 6.4 ①：`{}` 会让 POST 落到 422，而 422 证明不了「写入真的能成」；为 9 个资源各造一份合法请求体是 9 份会随 schema 漂开的字面量。**201 有守卫，只是不在遍历那一条里** |
| 4 | §3.1「**登录时**校验『subject 还在不在册』，不在就当场吊销」 | 校验放在 **每次 `resolve`**（即每个带 cookie 的请求），登录时不额外校验 | **顶回 5**（见 7.4）：派单自己要求的那条守卫是「删掉一个学生 → 他的旧 cookie **立刻** 401」，而「登录时校验」在结构上**做不到**它（学生是在登录**之后**被删的）。⚠️ 计划的两处措辞互相矛盾，我按守卫要求的那一侧办 |

### 7.4 顶回控制者的地方（**9 处**，其中 3 处是「计划/派单的判断本身错了」）

| # | 顶回什么 | 类型 | 证据 |
|---|---|---|---|
| **1** | §3.1「`_MODELS_PUBLIC_BASELINE` 33 → ?、`__all__` 要加」 | **计划的决定与本仓在场守卫冲突** | Ruling 97 + `test_models_public_namespace_is_unchanged_by_the_split`（它的 docstring 逐字把「基线被更新成含新名字」列为它要防的失效形态）；Plan 02 Task 6 与 Plan 03 Task 2 已两次沿用同一条纪律。实测：公有名仍 **33**、「多出来的名字」清单为空、`__all__` 仍 14 |
| **2** | §3.2 学生的出生日期列名 `birth_date` | **计划引用了一个不存在的东西** | 实测 `student` 的列是 `['id','student_no','name','sex','birth','department','grade']`。请求体字段因此叫 `birth`（本仓约定：Pydantic 字段名与 DB 列名逐字相同） |
| **3** | §3.6 第 3 条「新增一个 `require_staff` 依赖 = `role in {teacher, admin}`」 | **⚠️ 控制者的诊断本身错了**（产品判断对、动作多余） | 旧 `require_teacher` 的实现只查「工号在不在 `teacher` 表里」、**从不看 role**，而管理员就是一行 `teacher` ⇒ 它本来就放行管理员，那一格在行为上是 **no-op**。真正要做的三件事见 6.2 |
| **4** | §2.1「`app/config.py` 加 `PE_ALLOW_HEADER_IDENTITY`」 | **计划与本仓既有先例冲突** | `config.py` 的 docstring 逐字写着「本模块不 import `zoneinfo`…只 import `pathlib`」，而 `main.DB_URL_ENV_VAR` / `pipeline.CSV_DIR_ENV_VAR` / `passwords.PBKDF2_ITERATIONS_ENV_VAR` **三处**先例都把「环境变量覆盖口」放在消费者那侧、把「缺省值」留在唯一住址。⚠️ 缺省值 `"0"` 仍然是字面量、仍然有唯一住址，且**仍然有守卫钉住**（四拍，见 5.5） |
| **5** | §3.1「**登录时**校验『subject 还在不在册』」 | **⚠️ 计划的两处措辞互相矛盾** | 派单 §2 第 2 条要求的那条守卫是「删掉一个学生 → 他的旧 cookie **立刻** 401」，而「登录时校验」在结构上做不到它（学生是在登录**之后**被删的）。故校验放在每次 `resolve`。⚠️ 顺带：`resolve` 无论如何都要回查 subject 行（`me` 要 `name` 与学号/工号），故那一查不是纯开销 |
| **6** | §3.1「冗余了则『管理员被降权成教师』不会立刻生效」 | **⚠️ 控制者的诊断本身错了**（裁定可以维持，理由要换） | 实测：后端两道 role 闸门都经 `require_staff`，而它查 **`teacher` 表**、不是 `user_session.role` ⇒ 降权对**权限立刻生效**；滞后的只有 `me` 与登录响应体（前端路由的判据）。故真实代价是 **UI 一致性**、不是安全。守卫 `test_demoting_an_admin_takes_the_console_away_immediately_but_not_the_me_projection` |
| **7** | 计划完全没提：**泛型 list 端点会匿名泄漏 `password_hash`** | **计划漏了一格**（实测出来的洞） | `list_rows` 不走 `response_model`，故把哈希从 `*Read` 上摘掉堵不住 `GET /api/students` / `GET /api/teachers`。处置见 2.7（用 Plan 03 收尾小修波为 `rpe_token` 建的那套「两半」机制） |
| **8** | 计划完全没提：**422 的 `detail` 会逐字回显明文口令** | **计划漏了一格**（实测取证见 5.4） | Pydantic v2 的 `errors()[*]["input"]`；`missing` 那一档的 `input` 是整个请求体。`SecretStr` 挡不住它。处置：`app/api/errors.py` 加一层按键名的递归脱敏 |
| **9** | 计划 §3.1 的「完整同步清单」漏了 **2 格** | **计划漏了两格** | ① `tests/seed/test_generate.py::test_table_partition_is_exhaustive`（按集合相等判「三个分区恰好穷尽」）→ 新增第四个分区 `AUTH_TABLES`；② `tests/api/test_crud.py::test_every_table_has_a_single_column_primary_key` 的前提半句「25 张表的主键都是 INTEGER」→ `user_session.id` 是 `String(64)`，故显式例外化而不是让它变成一句假话 |

⚠️ **另外三处「实测推翻了我自己的第一版实现」**（不是顶回控制者，但同样记录，硬规矩 #39）：
`expires=0` 在 Starlette 里渲染成**当前时刻**（4.2）、
`logout` 的 cookie 必须设在**返回的**那个 `Response` 上而不是注入的那个（5.3）、
「带 cookie 时格式错的头不再触发 422」是**错的**（5.6）。

⚠️ **控制者裁定但我复核后维持的 2 处**（派单 §4 第 1、3 条）：
`role` 冗余（**维持**，但理由换成了 2.4 那一条）、
教师特例端点改成 `require_staff`（**维持产品判断**，但动作是改名而不是新增，见 6.2）。

---

## ⑧ 最终验收

### 8.1 测试与覆盖率

| 项 | 起点 | **结案** |
|---|---|---|
| `python -m pytest -q` | 1270 passed / 120.25 s | **1331 passed / 131.90 s**（+61） |
| `--cov=app.domain --cov-branch` | 1268 / **0** / 376 / **0** / **100%**，1269 passed + 1 skipped | **1268 / 0 / 376 / 0 / 100%**，1330 passed + 1 skipped，235.45 s |

⚠️ **覆盖率四格逐字不变**（本波**没有**改 `app/domain/` 下任何文件，
`git diff 1d1b6e8 HEAD -- backend/app/domain` 为空）。

**+61 条的分布**：`tests/auth/test_passwords.py` **13** + `tests/auth/test_sessions.py` **19**
（两份合计 **32**）+ `tests/api/test_auth_api.py` **28** + `tests/api/test_crud.py` **1**
（`test_an_admin_can_create_and_delete_while_a_teacher_cannot`）= **61**。
⚠️ 另有 **7 条既有守卫被改写**（不是新增）：表数的 5 处字面断言 + 表分区穷尽性 +
主键类型例外 + `_SERVER_FILLED_COLUMNS` / `_SERVER_GENERATED_HIDDEN_COLUMNS` /
`declares_list_exclude` 三处计数 + `test_the_identity_schemes_…` 六格 +
`test_every_writable_resource_admits_only_an_admin_mutation` 三拍。

### 8.2 计数面

| 量 | 起点 | **结案** |
|---|---|---|
| 表数 | 25 | **26** |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（⚠️ 顶回 1） |
| `models` 的子模块 | 6 | **7**（+ `auth`） |
| 扫描面 | 60 | **66**（pipeline 10 + db **12** + domain 18 + api **23** + **auth 3**） |
| 架构守卫的下界 | `scanned >= 18`、`reverse >= 15` | **21**、**20**（取法：各目录地板之和；`api_py >= 3`、`real_py >= 40`、`cases >= 22` **刻意不抬**） |
| `/api/` 路径模板 | 66 | **71**（+5，全是 `/api/auth/*`） |
| 操作 | 94 | **99**（+5） |
| 挂 `security` 的操作 | 46 | **48**（+2：`me`、`logout`；⚠️ **Task 2 贡献 0**） |
| GET（匿名 / 挂 security） | 59（48 / 11） | **60（48 / 12）** |
| mutating（挂 security） | 35（**35**） | **39（36）** ← 3 个不挂的是两个 bind + login（**必须**匿名） |
| `securitySchemes` | 2 | **3**（+ `pe_session`，唯一一个 `in: cookie`） |
| 外键总数 | 41 | **41**（`subject_id` 刻意不是外键） |
| `_in_domain` 受约束列 | 24 | **27** |
| `String(n)` 列 / `JsonText` 列 | 61 / 21 | **67 / 21** |
| `len(app.routes)`（⚠️ 假绿口径，只作对照） | 6 | **6** |
| `backend/**/*.py` | 130 | **140** |

### 8.3 禁区与五个指纹

| 判据 | 结果 |
|---|---|
| `Test-Path backend\pe.db` | **False** ✅ |
| `backend/data/seed/` 文件数（`-Recurse`） | **0** ✅（目录存在但为空） |
| `git diff 1d1b6e8 HEAD -- backend/data` | **空** ✅ |
| `git status --short -- backend/data` | **空** ✅ |
| 前 4 个指纹（由测试字面量钉住） | **全绿**：`tests/test_refdata.py` + `test_refdata_alerts.py` + `test_refdata_prescription.py` = **107 passed**，其中 `test_national_standard_csv_fingerprint_is_pinned`（`D2C8E539E2FA0029`）、`test_alert_rules_yaml_fingerprint_is_pinned`（`5394B37F01DAC9AC`）、`test_exercises_yaml_fingerprint_is_pinned`（`822CB86A5E998301`）、`test_equivalence_yaml_fingerprint_is_pinned`（`E48E3AC82BB45BB7`） |
| 第 5 个（18 套处方模板；⚠️ 合计指纹的组合算法已失传） | 按派单改用**两个判据**：① `test_template_yaml_fingerprints_are_pinned` **passed**（18 个逐文件指纹）；② `git diff 1d1b6e8 HEAD -- backend/data` **为空** |
| 三个 CLI（`app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`） | **一个都没跑** ✅ |
| 探针脚本的位置 | 全部在 `$env:TEMP\pe05a_probe\`（**7 个探针 + 12 个写入器**），仓库里 0 个；每个都先 `python -m py_compile` 过（硬规矩 #108）。⚠️ **收工后按派单纪律删掉**，故本报告引用的一律是它们的**输出原文**（逐字抄进各节），不是可复跑的路径 |

### 8.4 `pyproject.toml`

| 判据 | 结果 |
|---|---|
| `git diff 1d1b6e8 HEAD -- backend/pyproject.toml` | **空** ✅（一个字节没动） |
| sha256 | `4bfacc372ba60a3a0d11eb29e9b70a77d65022f9575ad2146c2f04f8de448fed` |
| **新增后端依赖数** | **0** ✅（密码用 `hashlib` / `hmac` / `secrets` / `base64`，会话用服务端表 + `zoneinfo` / `os` / `dataclasses`，全是标准库；⚠️ **没有** `pyjwt` / `passlib` / `bcrypt`） |
| `requires` 与 `[dependency-groups].dev` 的同步 | **不适用**（两处都没动） |

### 8.5 文件形状（行尾 / BOM）

改过或新增的 **45 个文件**（`git diff --stat 1d1b6e8 HEAD -- backend`：45 files changed,
**5548 insertions(+), 373 deletions(-)**）里，`.py` 共 **44 个**：
**全部纯 CRLF、无 BOM、无游离 CR**（探针 `p07_accept.py` 逐个 `read_bytes()` 量过，异常 **0** 个）。
`backend/scripts/demo.ps1` 是**UTF-8 带 BOM + 纯 CRLF**（11047 → 12620 B，BOM=True、bareLF=0、strayCR=0），
`PSParser::Tokenize` 语法错误 **0** 个。`backend/data/**` 一个字节没动，故 `.gitattributes` 的 `eol=lf` 那几条无关。

⚠️ **一次自己踩的坑，如实记**（它对下一个实现者有用）：第一版写入器把文件按
`text.replace("\n", "\r\n")` 写回，而 `text` 是从**本来就是 CRLF** 的文件读出来的，
于是每一行变成 `\r\r\n`——`git diff --stat` 当场报出「17 个文件、每个文件的**每一行**都变了」。
处置：写一个归一化器（去掉全部 `\r`、再统一加回 `\r\n`）修回 18 个文件，
并把它变成**每次写入之后都跑一遍**的固定动作（`git status` + `read_bytes()` 量 strayCR）。
⚠️ 教训是：`read_bytes().decode()` 之后要**先** `.replace("\r", "")` 再做替换，
否则「保留原有行尾」这个好意图会造出第三种行尾。

### 8.6 commit 链

| sha | 一句话 |
|---|---|
| `afb1886` | **Task 1-A**：`user_session` 表 + `student`/`teacher` 加 5 列（表数 25 → 26）；`_MODELS_PUBLIC_BASELINE` 仍 33（顶回）；凭据列的两个住址（`*Read` 摘掉 + `list_exclude`）；表分区加第四份 `AUTH_TABLES` |
| `1da7f9f` | **Task 1-B**：`app/auth` 两个纯服务模块（pbkdf2 自描述串 + 会话签发/解析/吊销/滑动过期 + cookie 参数）+ **32** 条守卫（含 `compare_digest` 的变异自证）+ 只 import `os` 的根 conftest |
| `640d81e` | **Task 1-C**：`/api/auth` 的五个端点 + `deps.py` 的双通道（缺省 `"0"`）+ `current_session` + 第三个 securityScheme + **422 按键名脱敏** + 架构守卫加 `auth` 层 + 全仓级 security 断言改口径（46 → 48） |
| `b446c9a` | **Task 2**：管理台归管理员（`require_admin`）+ `require_teacher` → `require_staff`（89 处）+ 管理员越过任教闸门 + 两条既有守卫改写（三拍 / 三个 scheme）+ 收红 4 条 |
| `8596043` | `demo.ps1` 设 `PE_ALLOW_HEADER_IDENTITY=1`（有意的过渡态，Task 5 撤掉）+ 把「身份用请求头传」那段打印改成两条通道的实话 |
| （下一个） | 本报告 |

⚠️ **没有 push**、**没有切分支**、**没有碰 `main`**；`git add` 一律按文件名逐个加
（每次 `git add` 之前都先跑 `git status --short`），commit 信息一律用 python 写 UTF-8 **无 BOM**
临时文件 + `git commit -F`。

---

*报告结束。字节数与行数见提交后的复核记录（`.superpowers/**` 在 `.gitattributes` 里是 `-text`，
故工作树字节与入库 blob 逐字节相同）。*

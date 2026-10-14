> **Plan 06 Task 14 · 全分支终审席（只读、对抗性复核）**
> 复核区间 **`5131c12`..`127d3bf`（51 个 commit）**，HEAD = `127d3bf`，工作树干净、与 origin 同步。
> 本席**没有修改仓库里任何一个文件**：28 次定点变异一律**逐字节还原**（还原后 `git status --porcelain` 空、
> `git diff HEAD` 退出码 0，逐次记录见 §②/§⑥）；探针一律写在 `$env:TEMP\p06t14\`，收尾删净并复验（§⑧）。
> ⚠️ 本文件是**本席唯一一次写入**，写完**不 commit**（照派单：控制者下一波连同修复一起提交）。

**结论一句话**：**0 条 S1、2 条 S2、7 条 S3、5 条 S4**。这个仓库今天**可以交甲方**，
而交付前**必须**先改掉 §⑧ 8.3 的第一条 S2（管理台首页那段与鉴权实物**相反**的散文，9 行文案、不动代码/迁移/守卫），
并在交付说明里念清 §⑧ 那 9 条注意事项。前面 13 个波次的自报数字**抽验 40+ 格，错 0 格**（§⑦）。

---

## ① 复核范围、环境、起过的服务

### 1.1 区间两端与 commit 数（自己数的，不采信派单）

| 格 | 实测 | 怎么测的 |
|---|---|---|
| 第一条属于 Plan 06 的 commit | **`5131c12`** `docs(plan): 实施计划 06 —— 产品级硬化（迁移 / 生产安全与运维 / 教师读范围）` | `git log --oneline -80`，逐条读 commit 信息里的 `Plan 06 Task N` / `实施计划 06` |
| 区间起点（父） | **`297e846`** `docs(brand): 补两处用户可见旧名 …` | `git rev-parse 5131c12^` |
| 区间终点 | **`127d3bf`**（= HEAD = origin/main） | `git rev-parse HEAD`、`git log --oneline origin/main -1` |
| **commit 数** | **51**（含计划文档那一条；`5131c12..127d3bf` 是 50） | `git rev-list --count 5131c12^..127d3bf` |
| 累计 diff | **109 files changed, 38537 insertions(+), 1169 deletions(-)** | `git diff 5131c12^..127d3bf --stat` |

⚠️ **以累计 diff 为主**（照派单），逐文件的分布：新增的产品代码集中在
`backend/app/{static,deploy}.py`、`app/api/{audit.py,crud.py,deps.py,routers/{audit,auth,catalog,dashboard,feedback}.py}`、
`app/auth/{policy,passwords,sessions}.py`、`app/db/{width,session}.py`、`app/db/models/{audit,auth}.py`、
`backend/migrations/**`（4 条 + `env.py`）、`backend/scripts/{backup,restore,dump_openapi,serve_app,demo*}`、
`scripts/serve.ps1`；测试 +8 个新文件（`test_audit_api` / `test_column_widths` / `test_policy` /
`test_migration_baseline` / `test_migration_chain` / `test_backup_restore` / `test_dependencies` / `test_deploy` /
`test_serve` / `test_dashboard`）；前端 12 个文件。
⚠️ **`app/domain/**` 在 109 个文件里一个都没有**（`app/pipeline/report_stage.py` 只改了 2 行）——
这一格是 §② 那个「覆盖率四格 13 波一字未动」的**全部答案**的前半。

### 1.2 环境（硬规矩 #73：开工第一件事亲跑）

```
node --version   → v24.19.0
python --version → Python 3.11.1        （无 venv，C:\Python\python.exe）
npm --version    → 11.17.0
```

FastAPI / SQLAlchemy / alembic 的版本以 `pyproject.toml` 与 `alembic` 自报为准（`alembic==1.20.0` 是全表唯一精确钉死的一项）。

### 1.3 本席起过哪些服务、PID、是否全停

| 服务 | 命令 | 端口 | PID（历次） | 收尾 |
|---|---|---|---|---|
| 后端演示档 | `backend\scripts\demo.ps1 -Port 8000` | 8000 | uvicorn 43900 → 39032 → 616 → 42892 → 35868 → 37108（每次重灌换一个） | **已停**（监听数 0） |
| 产品档 | `scripts\serve.ps1 -Port 8020`（一次不带 `-SkipBuild`、一次带） | 8020 | 39444 → 41316 | **已停**（监听数 0） |
| 前端 dev | `npx vite --port 5174 --strictPort`（`PE_API_TARGET=http://127.0.0.1:8000`） | 5174 | 33320 → 42348 | **已停**（监听数 0） |
| ⚠️ **不是本席起的** vite | — | **5173** | **20240** | **一个字节都没碰**（收尾复测仍在监听） |

收尾复验（`Get-NetTCPConnection -LocalPort 8000,8020,5174,5173 -State Listen`）：**只剩 5173 / PID 20240**。
`Get-Process python,node` 收尾只剩 4 个 node（PID 14368 / 15204 / 16404 / 20240，全部是本席开工之前就存在的）。

⚠️ **如实记一处本席自己造成的事故（已完全复原）**：中途有两个变异驱动进程并发跑了约 4 分钟
（一个我以为已经因 `UnicodeDecodeError` 死掉、其实还活着），于是同一时刻有两个驱动在改产品文件。
处置：`Stop-Process` 两个驱动 → `git checkout --` 还原那 3 个被留下的文件 → `git status --porcelain` 空 →
`git diff --exit-code HEAD` 退出码 **0**。此后改成**单驱动**（PowerShell 编排 + Python 只负责改/还原文件），
`OUT_sb6.txt` 里每一次变异后都印了 `restore` 的 sha 与 `git status: []`，逐次可对账。
⚠️ 那 4 分钟里跑出来的一版 smoke 基线（17/18 步、2 红）**已作废、不进任何结论**；
本席报的 dev 档基线是**单驱动、干净库**上重跑的那一次（18/18 · **637 绿 / 0 红** · 退出码 **0**）。

### 1.4 演示库的卫生

`backend/pe_demo.db` 是本席**反复重灌**过的（`demo.ps1` 的第一步就是删库重灌），且被
`POST /api/alerts/1/handle`、若干次失败的 `bind`（写 `login_attempt`）、两次超长路径探测（写 `audit_log`）写脏过。
它**已进 `.gitignore`**（实测 `git check-ignore -v` 命中 `.gitignore:42`），故 `git status` 一个字节都不显示。
⚠️ 交回控制者时它是脏的：要一份干净的演示库请重跑 `backend\scripts\demo.ps1`。

---

## ② F1 · 守卫的强度：28 次定点变异 + 覆盖率四格的真相

### 2.1 变异结果表（后端 23 次 + 前端 5 次 = **28 次**；22 红 / 6 绿 / 1 未完成）

⚠️ 每一次的姿势都是：**改一处产品代码 → 跑点名的守卫 → 逐字节还原 → `git status --porcelain` 复验为空**。
还原一律按**字节**（保存原始 `bytes` 再写回；前端那一批另按 sha256[:16] 对账，见 `OUT_sb6.txt`）。

| # | 改了哪一处产品代码（一字不差） | 跑什么 | 红没红 | 还原后 `git status` |
|---|---|---|---|---|
| M01 | `app/auth/policy.py`：`_KEY_PREFIX_BY_PURPOSE` 的 `"bind:"` → `""`（两个用途共用一个计数器） | `tests/auth/test_policy.py` + `tests/api/test_auth_api.py` | **红** | 空 |
| M02 | `app/auth/policy.py`：`_key` 不再过 `db_width.truncate`（原样返回 505 字符的键） | `test_policy.py` + `test_column_widths.py` | **红** | 空 |
| M03 | `app/db/width.py`：`OVERLONG_SUFFIX = "…[cut]"` → `"..."` | `test_column_widths.py` | ⚠️ **绿（16 passed）** | 空 |
| M03b | 同上 → `"      "`（**6 个空格**：等宽而**不可见**） | `test_column_widths.py` | ⚠️ **绿** | 空 |
| M03c | 同上 → `"…"`（孤零零一个省略号，会自然出现在真实数据里） | `test_column_widths.py` | ⚠️ **绿** | 空 |
| M04 | `app/db/models/auth.py`：`login` 的 `String(64)` → `String(32)` | `test_migration_chain.py` + `test_policy.py` + `test_column_widths.py` | **红** | 空 |
| M05 | `app/static.py`：`RESERVED_PREFIXES` 去掉 `"/docs"` | `tests/test_serve.py` | **红** | 空 |
| M06 | `app/static.py`：`cache_control_for` 的 index.html 那一支 `NO_CACHE` → `None` | `test_serve.py` | **红** | 空 |
| M07 | `app/static.py`：`is_asset_request` 的 `/assets/` 那一支 `True` → `False`（缺失产物退回 fallback） | `test_serve.py` | **红** | 空 |
| M08 | `app/api/deps.py`：`allow_header_identity` 去掉 `if is_prod(): return False` | `tests/api/test_auth_api.py` | **红** | 空 |
| M09 | `app/deploy.py`：`tier()` 认不出的值静默 `return DEV`（不再 `raise`） | `test_deploy.py` + `test_main.py` | **红**（`test_an_unrecognised_tier_is_loud_and_never_silently_dev`：`DID NOT RAISE ValueError`） | 空 |
| M10 | `app/auth/passwords.py`：`PBKDF2_MIN_VERIFY_ITERATIONS = 100_000` → `1` | `tests/auth/test_passwords.py` | **红** | 空 |
| M11 | `app/api/routers/catalog.py`：第一处 `"read_scope": READ_SCOPE_STAFF_TAUGHT,` → `"read_scope": None,` | `test_crud.py` + `tests/db/test_models.py` | **红** | 空 |
| M12 | `app/db/session.py`：`ALEMBIC_VERSION_TABLE` `"alembic_version"` → `"alembic_version_x"` | `test_migration_baseline.py` + `test_migration_chain.py` | **红** | 空 |
| M13 | `app/api/audit.py`：`AUDITED_METHODS` 加 `"GET"` | `tests/api/test_audit_api.py` | **红** | 空 |
| M14 | `app/db/models/__init__.py`：`__all__` 多导出一个名字（抬 `_MODELS_PUBLIC_BASELINE`） | `tests/db/test_models.py` | **红** | 空 |
| M15 | `app/db/models/audit.py`：`path` 的 `String(256)` → `String(64)` | `test_column_widths.py` + `test_migration_chain.py` + `test_audit_api.py` | **红**（报错点名「最长路径模板 56 字符 × 2 ≮ 64」） | 空 |
| M17 | `app/static.py`：`is_reserved` 退化成裸 `startswith(prefix)` | `test_serve.py` | **红**（`/apixyz 不该是保留前缀`） | 空 |
| M18 | `app/static.py`：`_SpaRoute.matches` 不再拒非 GET/HEAD | `test_serve.py` | **红**（`POST /api/nope` 从 404 变 405） | 空 |
| M20 | `app/api/crud.py`：`_taught_filter` 去掉第二根轴（`return owned`） | `test_crud.py` | **红**（1 failed / 42 passed） | 空 |
| M21a | `app/api/deps.py`：`taught_section_ids` 去掉 `CourseSection.semester_id == semester_id` | 5 个 api/auth 测试文件（185 条） | ⚠️ **绿** | 空 |
| M21b | 同上，去掉 `Enrollment.semester_id == semester_id` | 同上 | ⚠️ **绿** | 空 |
| M21c | **两格一起去掉** | + `tests/api/test_dashboard.py`（185 条） | **红 2 条**（`test_teaching_last_semester_does_not_grant_access_this_semester` / `…_to_the_home_page`，各 `assert 200 == 403`） | 空 |
| M23 | `app/api/crud.py`：`_orphan_condition` 去掉承重的那一格 `IS NULL` | `test_crud.py`（50 条） | ⚠️ **绿** | 空 |
| S01 | `frontend/src/present.ts`：`export const UNKNOWN = '—'` → `'0'` | `smoke.mjs`（dev 档，干净库） | **红**（637→636，第 17 步 ④「那个唯一住址**还在**」） | 空（sha 复原 `096d6305663660f2`） |
| S02 | `frontend/src/api/endpoints.ts`：`SINGLE_PAGE_LIMIT = 200` → `1` | 同上 | **红 5 条**（学生详情页三格真取证 `DOM=[] API=["57.67"]/["32.0"]/["83.3"]` + ⑦① 反空转） | 空（sha 复原） |
| S04 | `frontend/src/views/admin/AuditLogList.vue`：列头 `label: '身份类型'` → `'身份种类'` | 同上 | ⚠️ **绿（637/0）** | 空（sha 复原） |
| S05 | `frontend/src/router/index.ts`：`path: '/admin/audit-logs'` → `'/admin/auditlog'` | 同上 | **红 2 条**（第 14 步 6 条 needle 全缺 + 第 17 步 ⑥「相撞面必须**包含** (/admin/audit-logs, /admin/:resource) 那一对 → 17 对」） | 空（sha 复原） |
| S07 | `backend/app/api/audit.py`：`AUDITED_METHODS` 加 `"GET"` | 同上 | **红**（审计页第一页被 GET 行挤掉，needle `/api/auth/login` 缺） | 空（sha 复原） |
| S10 | `frontend/src/present.ts`：`shuttle_20m_s` 的标签加一个 `X`（**反例对照**：smoke 不看这一格） | 同上 | ⚠️ **未完成**（如实记，见 §2.4） | 空（sha 复原 `096d6305663660f2`） |

**统计：28 次真跑，22 红 / 6 绿 / 1 未完成。**

### 2.2 那 6 次「绿」逐个定性（**不许一律报成假守卫**）

| 绿的那一次 | 它是假守卫吗 | 判据（**都有取证**） |
|---|---|---|
| **M03 / M03b / M03c**（截断标记） | ⚠️ **是**（自指型）→ **S2** | `tests/api/test_column_widths.py:447` 逐字是 `suffix = width.OVERLONG_SUFFIX`：**期望侧与被测侧同源**。守卫钉的是「截完以**本模块自己声明的**那个标记结尾、且总长恰好等于声明宽度」，**钉不住**「那个标记在真实数据里辨不辨得出来」。而 `app/db/width.py:62-64` 用一整段论证了为什么必须是 `[cut]`：「一个孤零零的 `…` 会出现在**真实数据**里……于是『这一格被截过』与『这一格本来就有个省略号』不可分辨」，派单也逐字要求「不许静默截断」。**换成 6 个空格 = 静默截断，而全仓 16 条守卫全绿。** |
| **M21a / M21b**（单格 `semester_id`） | **不是**（已知边界，且**代码里自己登记了**） | `app/api/deps.py:1088-1096` 逐字写着「单独去掉任一个都不红 —— **两个一起去掉**才红 2 条」。本席**照它说的做了**：M21c 两格一起去掉 → **恰好红 2 条**、且红在 `tests/api/test_dashboard.py` 那两条（`assert 200 == 403`）。⇒ 那句自述**逐字为真**。它是一格真实的守卫面盲区（→ **S3**），不是一条假守卫。 |
| **M23**（`IS NULL`） | **不是**（被 DB 约束兜住，故变异**语义等价**） | `app/api/crud.py:806-813` 自己写了「由 `ck_alert_subject_is_exactly_one` 强制，于是本格在**今天的写入方**下与不加它等价」。本席**实测那条 CHECK 有牙**：往一份演示库副本里 INSERT「`student_id` 与 `course_section_id` 都非空」→ `IntegrityError CHECK constraint failed: ck_alert_subject_is_exactly_one`；「两格都空」→ 同样被拒。⇒ 那个泄漏形状**在库层面写不进去**，变异不红是**正确**的。 |
| **S04**（审计页列头） | ⚠️ **needle 歧义**（不是守卫假，是判据挑错了元素）→ **S4/S3** | 页面上有**两处**「身份类型」：过滤器下拉的标签（`AuditLogList.vue:331`）与列头（`:116`）。本席只改了列头那一处，needle 被过滤器那一处满足了 ⇒ 637/0 全绿。 |

### 2.3 ⚠️ 覆盖率四格「13 个波次一字未动」的真相（派单点名要查清）

**结论：那一格数字是真的、也**必然**不动，而它作为一个「质量指标」是误导性的。** 三格实测事实：

1. **`app/domain/` 是本计划刻意不动的那一层。** 109 个文件的累计 diff 里**没有一个** `backend/app/domain/**`
   文件（唯一沾边的是 `app/pipeline/report_stage.py` 的 2 行）。故 1268 stmts / 376 branch 这两个分母
   **在结构上不可能变**，「一格未动」不是守卫的功劳、是**改动面的事实**。
2. **而 `--cov=app/domain` 这个口径把 Plan 06 新增的全部模块排除在扫描面之外。** 本席亲跑两遍全量：

   | 命令 | 结果 | 墙钟 |
   |---|---|---|
   | `python -m pytest -q --cov=app/domain --cov-branch` | **1564 passed, 1 skipped**；`TOTAL 1268 0 376 0 100%`（18 个文件逐个 100%） | **304.33 s** |
   | `python -m pytest -q --cov=app --cov-branch` | **1564 passed, 1 skipped**；`TOTAL **7295** **201** **1772** **115** **96%**` | **322.90 s** |

   ⇒ `app/domain/` 的 1268 条语句只占全 `app/` 的 **17.4%**。本计划新增/改写的那些模块在**全 `app/` 口径**下是：
   `app/static.py` 75/3 **96%**、`app/api/audit.py` 57/5 **92%**、`app/api/crud.py` 356/17 **93%**、
   `app/api/deps.py` 131/5 **94%**、`app/auth/policy.py` 88/1 **98%**、`app/auth/passwords.py` 70/0 **100%**、
   `app/db/width.py` 32/0 **100%**、`app/deploy.py` 21/0 **100%**、`app/db/session.py` 74/0 **99%**。
   **这些数一份报告都没报过**（计划 §10 第 1 条要求「新增模块自己的覆盖率单独报」，13 波一律只报那四格）。
3. ⚠️ **`backend/scripts/**` 两个口径都不在扫描面里**（它们不在 `app/` 下）。而那正是本计划交付的**运维承重面**。
   本席用「真的会跑它们的那三个测试文件」量了一遍（`--cov=scripts --cov=app.static`，89 passed / 22.55 s）：

   | 模块 | Stmts | Miss | Cover |
   |---|---|---|---|
   | `scripts/backup.py` | 142 | 14 | **88%** |
   | `scripts/restore.py` | 110 | 17 | **80%** |
   | `scripts/dump_openapi.py` | 39 | 20 | **45%** |
   | `scripts/serve_app.py` | 20 | 1 | **92%** |
   | `scripts/demo_bootstrap.py` | 145 | 145 | **0%**（那三个测试文件根本不碰它） |
   | `app/static.py` | 75 | 3 | 96% |
   | **TOTAL** | **531** | **200** | **62%** |

   ⇒ 「100%」这四个字覆盖的是全仓 **1268 / (7295 + 531) ≈ 16%** 的可执行语句。→ 报成 **S3**（盲区/误导性指标），
   ⚠️ **不是** S2：那四格数字本身**逐字为真**、口径也**逐字写明**是 `app/domain/`，没有一处撒谎；
   撒谎的是「13 波都拿它当质量总账的第一格」这个**读法**。

### 2.4 如实记：本席没查透的两格

* **S10（反例对照）未完成**：那一次 smoke 跑到第 14 步时本机已经积了 **43 个**遗留的无头 Edge 进程
  （本席自己的 CDP 探针 + 6 轮 smoke 留下的），页面取样出现 `.app` 的 `class=""`（外壳还没挂上 class）
  这一类**负载型假红**，与变异无关。本席**杀掉了那一次运行**而不是把它的红当成结论，
  并把 `present.ts` 按 sha 还原（`096d6305663660f2`）。⇒ 「smoke 有没有**恒绿**的拍」这一格，
  本席的证据是 **S04**（一次真绿）与 **M03 家族**（三次真绿），不是 S10。
* **`check:tokens` / `check:dist` 没有单独跑**：两档 smoke 的**第 15 步**各 8/8 条断言全绿
  （那一步就是跑这两个守卫），故本席采信第 15 步、没有另起一次。它们的**内部**强度（扫描面 36 / 下界 25、
  25 产物 / 780 131 字符）本席**没有做定点变异**——如实记为未查透。

---

## ③ F2 · 鉴权与权限的接缝（全部运行时取证）

⚠️ 取证姿势：**在 `$env:TEMP` 下复制一份演示库**，用进程内 `TestClient(create_app(db_url=<副本>))` 打，
于是「建一个不带班的教师」「把管理员降权」这类**破坏性**动作一个字节都不落到仓库里；
另外两档（`PE_ENV=prod`、真 HTTP 的两档）各自单独实测。探针：`p05_auth2.py` / `p06_bind.py` /
`p07_bind2.py` / `p08_throttle.py` / `p09_iters.py` / `p17_claims.py` / `p30_final.py`。

### 3.1 本席自己构造的跨档组合 × 实测状态码矩阵

| 组合（**都是本席构造的**，不是既有夹具） | 实测 | 判 |
|---|---|---|
| **一个不带任何班的教师**（管理员 `POST /api/teachers` 造 `T9001` → `bind` 204 → `login` 200） | `/api/students?limit=200` → **200 total=60**（含 `birth`）；`/api/alerts` `/api/weekly-class-reports` `/api/training-logs` → **200 total=0**；`/api/dashboard/class/1` → **403**；`/api/teacher/students/4/weekly-sheet` → **403**；`/api/audit-logs` → **403** | ✅ 第四/五档收得干净；⚠️ 名册那一档是 `"staff"`（**任何**教职全读），见 §3.2 |
| **学生 id 与教师 id 同号**（演示库 `student.id=4` 与 `teacher.id=4`＝本席新建的 `T9001` **真的同号**） | 学生 `2023120001`（`id=4`）的 `/api/auth/me` → `{'kind':'student','id':4,'role':'student',…}`；同一个库上 `T9001` 的 `/me` → `{'kind':'teacher','id':4,…}`；学生读 `/api/students/4/home` → **200**、读 `/api/students/5/home` → **403**；学生读 `/api/teacher/students/4/normalized` → **403**（跨 kind） | ✅ 两档 `subject_id` 各自按 `kind` 解引用，同号不串 |
| **同时是某班任课教师、又是站内信收件人**（`notification.recipient_kind='teacher'`，第二根轴 `teacher_self`） | 演示库上 `recipient_kind` 实测 **19 行全是 `'student'`** ⇒ 这一格**在演示库上不可达**（如实记）；本席改用**变异**取证：M20 把第二根轴整个拿掉 → `test_crud.py` **红**（1 failed / 42 passed，diff 里少了那个班的 id） | ✅ 守卫有牙；⚠️ 演示库上没有这一档的真数据，故 smoke/演示都看不见它 |
| **管理员被降权成教师之后**（`PATCH /api/teachers/3 {"role":"teacher"}`，**同一个会话**继续打） | `/api/audit-logs` → 立刻 **403**；`POST /api/teachers` → 立刻 **403**；`/api/auth/me` → **仍然 `role: 'admin'`**；**重新登录**之后 `/me` → `role: 'teacher'`、`/api/audit-logs` → **403** | ✅ **spec §1.2 第 7 条今天仍然逐字成立**（权限立刻生效、`role` 要等重登）；⚠️ 后果见 §3.6 |
| 教师 cookie 打学生专用端点 | `/api/students/4/home` → **403**「当前会话是 teacher（T0001），而本端点要的是学生身份」 | ✅ |
| 学生 cookie 打教师/管理台端点 | `/api/dashboard/class/2` → **403**；`/api/audit-logs` → **403**；`/api/students?limit=200` → **403**；`/api/teachers` → **403** | ✅ |
| **匿名 + 伪造请求头**（dev 档，`PE_ALLOW_HEADER_IDENTITY` 未设） | `X-Teacher-Staff-No: T0003` → **401**；`X-Student-Id: 4` → **401**（报文里逐字写「请求头 X-Student-Id 被忽略」） | ✅ |
| **匿名 + 伪造请求头**（`PE_ENV=prod` **且** `PE_ALLOW_HEADER_IDENTITY=1`） | → **401**，且装配期打了**一次** warning「PE_ALLOW_HEADER_IDENTITY=1 在 PE_ENV=prod 下**被忽略**」；M08 把那一支拿掉 → 守卫**红** | ✅ 强制关，且守卫有牙 |
| 匿名读 23 个资源的 list | **200 的只有 7 个**（`semesters` / `course-sections` / `fitness-test-batches` / `class-sessions` / `exercises` / `prescription-templates` / `percentile-snapshots`），另 **16 个一律 401**；`GET /api/students/1`（read-one）匿名 **401** | ✅ 与 §13.4.4 那张五档表逐格相符 |

**五档分布自己数了一遍**（`catalog.RESOURCES` 实测 `len == 23`）：
`read_scope` = `None` **7** / `"student_self"` **0** / `"staff_taught"` **13** / `"staff_taught_section"` **1** / `"staff"` **2**
⇒ **7 / 0 / 13 / 1 / 2 逐字为真**。另：`writable` **9** / 只读 **14**；`on_delete` = `restrict` **12** / `forbid` **10** / `cascade` **1**。

**第四档的收窄量自己量了一遍**（cookie 通道、真 HTTP）：

| 资源 | T0001（班 1+3） | T0002（班 2+4） | T0003（admin） | 学生 #4 | 匿名 |
|---|---|---|---|---|---|
| `/api/training-logs` total | **574** | **588** | **840** | **14** | 401 |
| `/api/alerts` total | **21** | **23** | **32** | **1** | 401 |
| `/api/weekly-class-reports` total（第五档） | **2** | **2** | **5** | 403 | 401 |
| `/api/notifications` total | **12** | **15** | **19** | **1** | 401 |
| `/api/students` total（`"staff"` 档） | **60** | **60** | **60** | 403 | 401 |
| `/api/mini-tests/normalized?semester_id=2&week=6` 的 `sections` | **[1, 3]** | — | **[1,2,3,4,5]**（降权前） | 只自己的班 | 401 |

⇒ 与 spec §1.2 第 13 条、§13.4.7、§13.4.8 的实测数字**逐格相符**（574 / 588 / 21 / 23 / 840 / 32）。

### 3.2 ⚠️ 一个跨波次接缝：**名册那一档仍然是「任何教职全读」，而它正是绑定口令的验身材料**

**运行时取证的完整链条**（`p06_bind.py` / `p07_bind2.py`，库是 `$env:TEMP` 下的副本）：

1. 管理员建一个**不带任何班**的教师 `T9101`（`POST /api/teachers` → **201**），匿名 `bind` → **204**，`login` → **200**；
2. 这个教师 `GET /api/students?limit=200` → **200 total=60**，每一行的键实测是
   `['birth','department','grade','id','name','sex','student_no']`，**60 行全部带 `birth`**；
   同一个人 `GET /api/teachers?limit=200` → **200**，键 `['id','name','role','staff_no']`；
3. 管理员再建一个**还没绑定**的学生 `2026999999`（`birth=2008-03-07`）→ **201**；
4. **一个匿名调用方**拿第 2 步读到的那一个 `birth` 去 `POST /api/auth/students/bind` → **204**，
   再 `POST /api/auth/login` → **200**、`/api/auth/me` → 那一个学生；
5. 教师那一侧同形：匿名拿 `/api/teachers` 里的 `name` 去 `POST /api/auth/teachers/bind`（新教师 `T9102`）→ **204**；
6. 对**已绑定**的账号重复 bind → **409 `password_already_bound`**（实测 **270 B**）。

**这一格不是新发现，spec 逐字登记过**：§13.4.4 的五档表里 `"staff"` 那一行写着
「**2**：`students` / `teachers`（Plan 05A Task 5 的两份名册，**各含绑定口令的全部验身材料**）」，
§1.2 第 4 条更逐字写着「一个**已登录的教职**仍然能替任何还没绑定的账号抢先绑口令
（他本来就读得到全部验身材料，限流对他一次就猜中的那一档**零收益**），生产要换成不可猜的验身材料」。
⇒ **本席复核为「文档与实物一致」，不报成 S1/S2**，而报进 §⑧ 的**交付必须说明**清单（第 4 条）。
⚠️ 而 Task 8/8b 把 13 个学生键资源收到任教范围、却**刻意**把两份名册留在 `"staff"` 档，
这个**接缝**是本席在全部 13 波报告里唯一没看到有人**并列陈述**过的一格
（各波都只报「13 行收窄了」与「`"staff"` 从 3 行变 2 行」，没有一处把「收窄后的残余 = 名册仍是全校 + 含 `birth`」
写成一句给甲方念的话）。

### 3.3 产品档缺省留在 `dev` 档：**对交付不是 Critical，而是一格必须念清的注意事项**

实测 `scripts\serve.ps1 -Port 8020`（不带任何环境变量）的打印与实际行为：

```
PE_ENV          = 未设（= dev 档）
档位            = dev（cookie 的 Secure = False）
⚠️ Secure 只在 prod 开，故在**明文 http** 上跑 prod 档，浏览器会拒收会话 cookie
   （症状是「登录 200、下一个请求 401」）。同源 http 的产品档请留在缺省的 dev 档。
```

| 安全性质 | `serve.ps1` 缺省（dev） | `PE_ENV=prod`（本席实测） |
|---|---|---|
| cookie 的 `Secure` | **关**（实测 `Set-Cookie: pe_session=…; HttpOnly; Max-Age=7200; Path=/; SameSite=lax`，**无 `Secure`**） | **开**（实测同一串末尾多 `; Secure`） |
| CORS | 挂 `allow_origins=["*"]`（不带 credentials） | 读 `PE_CORS_ORIGINS`，缺省空 = **一个 CORSMiddleware 都不挂** |
| 请求头身份通道 | 按环境变量；⚠️ 而 **`serve.ps1` 自己强制清掉它**（实测打印「进本脚本时实测 未设 → 本进程已**强制**清成 未设」；M08 证明 `prod` 那一支的守卫有牙） | **强制关**（`allow_header_identity()` 恒 `False`） |
| 启动自检 | 不跑 | 跑（CORS 挂成 `*` 或 Secure 没开 → `raise`，**服务起不来**） |
| `/docs` `/redoc` `/openapi.json` | **公开 200** | **仍然公开 200**（本席在 `PE_ENV=prod` 下实测：`/docs` 200、`/openapi.json` 200） |

**判断**：这一格**不是** S1。三条理由，都有取证：
① 缺省留 dev 是**同源 http 上唯一能登录**的一档（prod 会开 `Secure`，明文 http 上浏览器拒收 cookie ⇒
「登录 200、下一个请求 401」），把它反过来缺省成 prod 会让甲方**照文档一条命令起服务却登不进去**；
② 那一档**唯一**真正危险的东西（请求头身份通道）被 `serve.ps1` **强制清掉**、且 Task 11 专门把
「不给 `-Prod` 开关」的理由逐字打印在 ⑤ 那一段里；
③ 它是**响亮**的：脚本每次启动都把「档位 = dev（cookie 的 Secure = False）」印在屏幕上，
`PE_ENV` 写错一个字母会**当场 `ValueError` 起不来**（M09 变异证明那条守卫有牙）。
⇒ 报成 **§⑧ 交付说明第 1 条**（必须念给甲方运维：**上 HTTPS 反代之后要自己设 `PE_ENV=prod` + `PE_CORS_ORIGINS`**），
并把「`/docs` 两档都公开」单独立一条 **S4**（§⑤）。

### 3.4 bind 限流：键**不会**撞车（两个方向都实测了）

| 实测 | 结果 |
|---|---|
| **交叉不污染**（同一学号 `2023120001`）：连打 **4** 次「材料不符」的 bind | 4 次一律 **403**（第 4 次已在锁定档，响应与「材料不符」**逐字节相同**，实测 **108 B**）；紧接着用**正确口令**登录 → **200**，`login_attempt` 里那个键逐字是 `('student','2023120001',ok=1)`，而 bind 的三行是 `('student','bind:2023120001',ok=0)` ⇒ **两个键真的分开** |
| 反方向：连打 **6** 次错口令登录（登录侧锁死）后再打一次 bind | bind 仍然回 **403「材料不正确」**（不是登录侧那个锁），库里 6 行 `2023120001` + 3 行 `bind:2023120001` ⇒ **互不污染** |
| **超长 login 会不会撞成同一个限流键**（派单点名）：`student_no` = `"A"*500`、`"A"*499+"B"`、`"A"*59`、`"A"*60` | 落库的键只有两种、**长度都恰好 64**：`bind:` + 53 个 `A` + `…[cut]`（前三个超宽的**撞成同一个**，3 行）与 `bind:` + 59 个 `A`（**未截断**，1 行）。`max(length(login))` 实测 **64** = 声明宽度，**一个字节都没超** |
| ⚠️ 撞车会不会**伤到合法用户** | **不会**：合法键最长 = `len("bind:") + 名册列宽` = **15**（实测 `bind:2023120001`），被截过的键**恒等于 64**，两者长度不同 ⇒ **永不相撞**。撞只发生在「两个都不在册的超宽垃圾键」之间（`app/auth/policy.py:418-429` 逐字这么论证，本席实测复核为真） |
| ⇒ 「一个人探测能让另一个人被锁」这个拒绝服务 | **在 bind 这一档不成立**（垃圾键指向的标识本来就不在册）。⚠️ 而**在 login 这一档成立且是刻意的**：限流键是 `(kind, login)`、**不含 IP**，故一个匿名调用方拿别人的学号连错 5 次能把那个人锁 15 分钟 —— spec §1.2 第 15/16 条 + §15 的 **B4** 逐字登记了它（「按标识、不按 IP；生产要补反代级全局限速」） |

### 3.5 口令迭代上下界：**下界意味着「一份用更低迭代数写的库会全体登不进来，而只有一行日志说清」**

实测（`p09_iters.py`，直接调 `verify_password`）：

| 串里那一段迭代数 | `verify_password(正确口令)` | `verify_password(错口令)` |
|---|---|---|
| 1 000 / 50 000 / 99 999 | **False** | False |
| **100 000**（下界） / 600 000（缺省） / **2 000 000**（上界） | **True** | False |
| 2 000 001 / 999 999 999 | **False** | False |

配置侧同样有牙：`PBKDF2_ITERATIONS=1000` 或 `=5000000` → `iterations()` **当场 `ValueError`**
（报文逐字：「界外的值会造出 verify_password **验不过**的哈希（症状是「所有人都登录不了」，离真因隔一整层）」）；
未设 → **600000**；演示库实测 `pbkdf2_sha256$100000$…` = **恰好等于下界**（`demo.ps1 [6/7]` 自己打印了
「迭代次数是**演示值** 100000（生产缺省 600000）」）。

**这一格意味着什么**（派单点名的问法）：
* 失效方向是**安全**的那一侧（一个界外的串**验不过**，而不是**跑得慢**或**被当成合法**），
  且**响应上刻意不可分辨**（一律 401，不给枚举信号）——两档都是对的裁定；
* ⚠️ 而它的**代价**是：甲方现场若有一份用 **< 100 000** 次迭代写出来的 `password_hash`
  （例如从别的系统迁过来、或一次人工 `UPDATE`、或一份用旧配置恢复上去的备份），
  表现是**所有人都登录不了**，而唯一的可见性是**一行日志**：
  「口令哈希的迭代次数 50000 越出 [100000, 2000000]，本次校验按「验身不符」处置…请查那一行 password_hash 是被什么写坏的」。
  ⇒ 报成 **S4**（交付说明里要点명「日志里出现这一句 = 库里的哈希是界外迭代数写的」）。
* **演示库那个值恰好等于下界**这件事本身**不是**问题（它是一个自描述串，600 000 与 100 000 可以同库并存，
  `demo.ps1` 逐字这么打印），而它是一格**贴边**：将来谁把下界抬到 200 000，演示库当场全体登不进来。
  ⚠️ 本席**没有找到**任何一条守卫钉住「演示库那个值 ≥ `PBKDF2_MIN_VERIFY_ITERATIONS`」——如实记，
  但它今天在 `demo_bootstrap.py` 的常量与 `passwords.py` 的下界**同一个数**上，故不报成发现。

### 3.6 会话 pending 那一帧：两档实测 + **一格新的卡住形态**

* **产品档**（`serve.ps1` 8020，本席用 CDP 真渲染 16 条路由）：`/login` 那一帧的 DOM 里出现的是
  `会话状态 anon`（已登录页面上是 `会话状态 authed`），**没有** `ANONYMOUS` / 「未登录」那两句假话；
  **dev 档**（vite 5174）同一帧出现的是 `当前身份 | ANONYMOUS | 未登录`——⚠️ 而这一档是**匿名 jar**
  （`/login`、`/bind` 两条路由本来就匿名），故它说的是真话，与 §13.13.3 那张表逐字一致
  （「dev 档那一帧结构上不可达」指的是**已登录**用户的那一帧）。
* 运行时那一半的守卫本席**没有另起 CDP 的 `Fetch` 域去扣 `/api/auth/me`**（smoke 第 14 步 §C3 已经这么做，
  两档各 637/0 全绿 ⇒ 采信）；本席补的是**结构面**的复核：`stores/session.ts:157-159` 的 `isPending`
  是**唯一判据**，两个消费者（`summary` `:188`、`IdentitySwitcher` 的 `roleLabel`）都走它。
* ⚠️ **本席查到一格新的卡住形态（`isPending` 引入的、没有超时）**：
  `router/index.ts:319-332` 的 `beforeEach` 在任何判定之前 `await session.ensureRestored()`，
  而 `ensureRestored`（`stores/session.ts:259-286`）与 `api/client.ts` **都没有任何超时**
  （`client.ts` 只把 `signal?: AbortSignal` 当**可选入参**转交，`fetchMe()` 不传它）。
  ⇒ 一个**接了 TCP 连接却不响应**的 `/api/auth/me`（反代挂住、SQLite 写锁长时间不放开）
  会让页面**无限期**停在「身份未确认…」，既不落 `authed` 也不落 `anon`、也不弹去 `/login`，
  用户手上**没有任何一个可点的出路**（那一帧连「重试」都没有）。
  ⚠️ **这一条是静态推断 + 代码取证，本席没有做运行时取证**（要一个故意挂住的 `/api/auth/me`），
  照硬规矩 #89/#103 **降级**报成 **S3**、并在现象里标注「静态推断，未取证」。

---

## ④ F3 · 产品档的交付可用性（甲方运维视角）

### 4.1 一条命令起产品档：**能**

`powershell -ExecutionPolicy Bypass -File scripts\serve.ps1 -Port 8020`（**不带任何环境变量**）实测全过程：
① 工具链 `python Python 3.11.1` / `node v24.19.0` → ② 判新鲜度「源面 **64** 个文件，最新 mtime =
`frontend\src\api\generated\schema.d.ts`；构建戳 `dist\index.html` = …；源面比构建戳**新** → 要构建」→
`npm run build`（`✓ 140 modules transformed`、`✓ built in 393ms`，产物 29 个文件，
其中 `index-v1XDnUhk.css` 65.20 kB / `index-BCWjM00F.js` 168.82 kB / `StudentDetail-BQenvJ7d.js` 39.16 kB /
`AuditLogList-DmETt2XK.js` 9.55 kB —— **四个哈希与 Task 13 报的逐字相同**）→ ③ `PE_DB_URL` 未设 ⇒
回落到 `app.main.DEMO_DB_URL`（`backend/pe_demo.db`）→ ④ 健康检查「轮询 **1** 次」200 → ⑤ 打印。
第二次用 `-SkipBuild` 起，同样 200。

| 派单点名的三档 | 实测 / 判 |
|---|---|
| **没有 `frontend/dist` 的干净检出上会怎样** | ⚠️ **未能核验**（本席的检出上 `dist` 已存在，而删掉它去试会破坏「不改仓库」的纪律）。**代码面取证**：`serve.ps1:149-154` 那一支是「`dist\index.html` 不在 → `$NeedBuild = $true` → 自己跑 `npm run build`」，`-SkipBuild` 时则 `throw "-SkipBuild 要求 dist 已经在：缺 …"`；再下一道是 `app/static.py:478-484` 的**装配期** `FileNotFoundError`（报文里逐字给了三条出路）。⇒ 失效方向是**响亮**的 |
| **没灌过数据的库上会怎样** | 部分核验：`serve.ps1` **刻意不灌数据**（② 那段逐字写了分工），而起服务时 `init_db` 会走迁移链把**空库**建到 head（`demo.ps1` 的日志实测：一个空库上四条迁移逐条 `Running upgrade …`，约 1 秒）。⇒ 起得来、`/api/health` 200、`tables=28`、`students=0`；前端页面会是空态。⚠️ 本席**没有**在一个真·空库上起一次产品档（如实记） |
| **`PE_DB_URL` 没设时回落到哪儿、会不会把禁区 `backend/pe.db` 建出来** | ✅ 回落到 `app.main.DEMO_DB_URL`（= `backend/pe_demo.db`），**刻意不**回落到 `app.config.DEFAULT_DB_URL`（= 禁区）。另有第二道守卫 `serve.ps1:223-225`：URL 以 `pe.db` 结尾就当场 `throw`。本席**实测**了同族的第三道：`backup.ps1 -DbUrl sqlite:///…/backend/pe.db` → **退出码 2**「禁区…那个文件**不得存在**」；`restore.ps1 --db-url` 同 → **退出码 2**。全程 `backend/pe.db` **不存在**（收尾复测 `Test-Path` = **False**） |

### 4.2 备份与恢复：**完整流程实测通过**，含派单点名的那一格

一律用**交付的那两个 `.ps1`**（不是直接调 `.py`），库与备份目录都在 `$env:TEMP` 下（探针 `p19_backup.py`）：

| 步 | 命令 | 实测 |
|---|---|---|
| ① 建一个**链 3** 的库 | `alembic upgrade 7f3923d8af84` + 插两行标记数据 | `alembic_version = 7f3923d8af84`、`login_attempt.login` 的类型实测 **`VARCHAR(32)`**、29 张表 |
| ② 备份它 | `backup.ps1 -DbUrl <chain3> -Dir <tmp>` | **退出码 0**；产物 `pe-20261014T183121Z.db`（**286720** 字节）+ 侧车 `….db.sha256`；打印 `sha256 3a7c965de17e0144…` |
| ③ **把链 3 的备份恢复到链 4 的库上** | `restore.ps1 <名字> -Dir <tmp> -DbUrl <live(chain4)>` | **退出码 0**；四步都打印了（校验 ✓ / 后路 `pe-…-pre-restore.db` / 覆盖 / 自检）；自检逐字印出 **`alembic_version = 7f3923d8af84`**、`表数 29`、`student 行数 1`（原来 60）；恢复后实测 `login_attempt.login` 退回 **`VARCHAR(32)`** |
| ④ **再起服务（= `init_db`）会怎样** | `init_db(engine(<live>))` | 日志实测 `Running upgrade 7f3923d8af84 -> 0ac943e0da9b, 迁移 4：…列宽 VARCHAR(32) → VARCHAR(64)`；恢复后 `alembic_version = **0ac943e0da9b**`、`login` 回到 **`VARCHAR(64)`**、**两行标记数据都还在**（`student_no='2099000001'` 与 `semester.name='CHAIN3-MARKER'`） |
| ⑤ 改一个字节的备份 | 翻掉第 100 个字节 → `restore.ps1` | **退出码 2**、**目标库一个字节都没动**；报文逐字「侧车说 3a7c965de17e0144…，实测 8efa7d6314f1d6c5…。⚠️ 这一份被动过（哪怕只改了 1 个字节）…」 |
| ⑥ **服务起着的时候恢复**（写锁那一档） | 另一个连接 `BEGIN IMMEDIATE` + 一条未提交的 UPDATE，再 `restore.ps1` | **退出码 2**；报文是一句**人话**「目标库 … 正被别的进程占着（SQLite 报 database is locked）：**请先停服务**再恢复。… ⚠️ 而本检测是**尽力**的：SQLite 的锁是事务级的，一个开着连接却空闲的服务不持锁，故「没报错」不等于「服务停了」」 |
| ⑦ **在线**备份（uvicorn 正开着那个库） | `backup.ps1 -DbUrl <正在被 :8000 服务的 pe_demo.db>` | **退出码 0**，1 589 248 字节 + 侧车 ⇒ 「备份可以在服务跑着的时候做」这一句为真 |

**⇒ 派单点名的「链 3 备份 + 链 4 代码」不是 Critical**：它会**自愈**（下一次 `init_db` 自己 `upgrade head`），
数据一行不丢，而 `restore.py` 的自检**如实印出**了那个更旧的版本号。
⚠️ 残余报成 **S4**：`restore.py` 只**印**版本号、**不判**「备份的版本比当前代码旧」，
于是一个不知道 `7f3923d8af84` 是什么的运维看不出这一格；且从「恢复完」到「下一次起服务」之间，
那个库**确实**停在链 3（此时若跑一个**不**经 `init_db` 的工具，它看到的是 32 宽的列）。

### 4.3 升级路径：**自动**，且文档写清了

* **自动**：`init_db` 走迁移链（`app/db/session.py`），实测一个链 3 的库上它自己 `upgrade head`（④ 那一行日志）；
  `demo.ps1` 的模块注释逐字写着「**现在 `init_db` 走 alembic 迁移链**，旧库会被 `upgrade head` 补齐」
  与「⚠️ **生产上不要删库**：甲方现场那份库里是一学期的真实数据。升级版本走迁移链（`init_db` 会自己 `upgrade head`），
  改模型的流程见 spec §13.7」；`serve.ps1` 的 ④ 那段注释也写了「一个要 `upgrade head` 的旧库上更久」。
* **迁移链形状自己验了一遍**（`ScriptDirectory` + `compare_metadata`）：`heads = ['0ac943e0da9b']`（**单头**），
  四条修订 `53e5a548c40e → 0b7da3d20211 → 7f3923d8af84 → 0ac943e0da9b`。
* ⚠️ **一处文档缺口（S3）**：仓库根**没有 README**（`Glob *.md` 在根目录**0 个命中**）。
  甲方运维拿到的唯一「怎么跑」的活文档是 **487 278 B / 4601 行**的 spec §13，
  以及两个 `.ps1` 的注释与启动打印。⇒ 交付时要么附一页纸的 run book，要么明写「运行方式在 spec §13.1/§13.6/§13.11」。
* ⚠️ **另一处（S3）**：spec §13.6 那段代码块写的是 `npm install && npm run dev`，
  而**本仓的目标运维环境是 Windows PowerShell 5.1**（两个 `.ps1` 的注释里逐字交代过 PS 5.1 的坑），
  PS 5.1 **不支持 `&&`** ⇒ 照抄会当场报「标记 `&&` 不是此版本中的有效语句分隔符」。

### 4.4 文档里印出来的 URL **逐条真发请求**（Task 13 刚修过 2 条撒谎的 → 核它修对了没有）

| 出处 | 那条 URL | 实测 | 判 |
|---|---|---|---|
| `demo.ps1` ⑥「不登录也点得通的三条」 | `GET /api/health` | **200** `{"status":"ok","tables":28,"students":60}` | ✅ Task 13 改后的注释「三格」**为真** |
| 同上 | `GET /api/semesters?limit=50` | **200**，有行（`2024-2025-1` …） | ✅ Task 13 换掉 `/api/exercises` 是对的 |
| 同上 | `GET /api/percentile-snapshots?limit=50` | **200**，有行 | ✅ |
| `demo.ps1` ⑥ 的两条 ⚠️ | `GET /api/exercises?limit=50` / `GET /api/prescription-templates?limit=50` | 各 **200** 而 `{"items":[],"total":0}` | ✅ 脚本印的那两句警告**为真** |
| `demo.ps1` ⑥「这 8 条一律要登录会话」 | 匿名逐个打 | **8/8 一律 401** | ✅ 那一句为真 |
| ⚠️ 同上，**登录之后** | `GET /api/students/1/prescriptions/current?as_of=2025-10-12`、`GET /api/students/1/weekly-sheet?as_of=2025-10-12` | 用**教师** T0001 的 cookie 打 → **403**「当前会话是 teacher（T0001），而本端点要的是学生身份：一个教师/管理员的 cookie 不能当学生用」 | ⚠️ **S3**：这 8 条印在同一句「**登录后**可以这样点」下面，而**其中 2 条是学生专用**。脚本自己的账号清单同时给了教师与管理员，一个照它登录成教师的运维点这两条会当场吃 403 —— 与 Task 13 刚修掉的那 2 条**同一类**失效（念给甲方听时露馅），只是这一格漏了 |
| 同上，另外 6 条 | `alerts` / `alerts/{id}/handle` / `notifications` / `dashboard/class/1` / `mini-tests/normalized`（`run-daily` 本席**刻意不打**，照派单） | 教师 cookie 下各 **200**（`handle` 200 并回处置后的 alert） | ✅ |
| `serve.ps1` ⑤ | `/` `/api/health` `/docs` `/openapi.json`（8020） | **200 / 200 / 200 / 200** | ✅ |
| spec §13.6 的 **16 条路由** | 产品档 8020 上逐条真发 `GET` | **16/16 一律 200 + `text/html; charset=utf-8`**（SPA fallback，各 2729 B 的 `index.html`） | ✅ 与 §13.6 那张表逐条相符（表里 20 条记录 = 16 条叶子 + `/`、`/s`、`/t`、catch-all 四条不渲染的） |
| ⚠️ `demo.ps1` / `serve.ps1` 都印「管理台（**23** 个资源的增删改查）」，而 `demo.ps1 [6/7]` 印「管理台 **26** 个写入操作仅它可用」 | 自己数 | `len(catalog.RESOURCES) == **23**`、`writable` **9**、只读 **14**；26 = 9×(POST+PATCH) + 8×DELETE（`semesters` 是 `forbid`，实测 `DELETE /api/semesters` → **405**） | ✅ **两个数都对**、口径不同（资源数 vs 操作数），不是矛盾 |

### 4.5 审计页（`/admin/audit-logs`）的交付可用性

| 格 | 实测 |
|---|---|
| 非 admin 访问 | 后端：教师 T0001 `GET /api/audit-logs` → **403**（报文点名 `teacher.role == 'teacher'`）；学生 → **403**；匿名 → **401**。前端：路由 `requires: 'admin'` ⇒ 普通教师被 `beforeEach` 弹回 `/t/dashboard` + 一句 `session.notice`（smoke 第 14 步两拍钉住） |
| 分页与两个过滤 | 端点带 `subject_kind` / `method` 两个过滤参数（`endpoints.ts:945-969`），页面把两个下拉都画出来了（CDP 实测渲染文本里有「身份类型」「subject_kind=（不限）」）；顺序 `id DESC`（最新在前） |
| 超长 `path` 的截断标记 | ✅ **运行时取证**：`POST /api/<305 字符>` → 落库 `audit_log.path` **恰好 256** 字符、**尾部逐字是 `…[cut]`**；`PATCH /api/students/<400 个 9>` → `audit_log.target` **恰好 64** 字符、尾部同样 `…[cut]`（且这一行在 **401** 上也照样写了） |
| 「读不记 GET」 | ✅ 库里 `select count(*) from audit_log where method='GET'` = **0**；`method` 的分布实测只有 `POST 32 / DELETE 4`。页面上也把这一格摊开写了（「⚠️ GET 一律不记，故「谁读过什么」查不到」）⇒ **交付说明第 3 条** |

---

## ⑤ F4 + F5 · SPA fallback / 缓存头 / 静态服务的安全面 + 数据与 schema 一致性

### 5.1 本席**自构**的 fallback 矩阵（36 格；Task 7 的 13 格 + Task 11 的 6 格**之外**的那些加粗）

一律用**裸 socket** 打（`http.client` / `urllib` 会规范化路径，取不到证据），产品档 8020，探针 `p03_fallback.py`：

| 方法 | 路径 | 状态 | content-type | Cache-Control | 判 |
|---|---|---|---|---|---|
| GET | `/` `/login` `/s/home` `/admin/audit-logs` | 200 | text/html | **no-cache** | ✅ fallback |
| GET | **`/LOGIN`** | 200 | text/html | no-cache | ✅（前端路由大小写不敏感是 fallback 的正确去处） |
| GET | **`/API/health`** / **`/Api/Health`** | **200** | **text/html** | no-cache | ⚠️ **S4**：`is_reserved` 大小写敏感 ⇒ 一个大小写打错的监控探针会拿到 **200 + 一份 HTML** 并判「服务活着」。不泄漏任何数据（FastAPI 的路由同样大小写敏感），失效方向是**误导**而不是泄漏 |
| GET | **`/s/home/`**（尾斜杠）/ **`//s//home`**（双斜杠） | 200 | text/html | no-cache | ✅ |
| GET | **`/assets`**（不带尾斜杠） | **200** | text/html | no-cache | ✅ **刻意**（`ASSETS_PREFIX` 带尾斜杠；给一个目录列表等于把产物结构告诉匿名调用方，`static.py:172-177` 逐字写了理由） |
| GET | **`/assets/`**（带尾斜杠） | **404** | application/json | — | ✅ 不给目录列表 |
| GET | `/assets/nope-XYZ.js` | **404** | application/json | — | ✅ Task 11 / B1 |
| GET | `/assets/index-v1XDnUhk.css`（真产物） | 200 | **text/css; charset=utf-8** | **public, max-age=31536000, immutable** | ✅ 65 204 B |
| GET | **`/%2f%2fetc/passwd`** | 200 | text/html | no-cache | ✅ 字面串走 fallback（`static.py:288-296` 逐字解释了为什么**不做第二次解码**才是对的） |
| GET | **`/..%2f..%2fpe.db`** / **`/%2e%2e/%2e%2e/backend/pe.db`** | **404** | application/json | — | ✅ 越界 → `None` → 404（**不是** index.html） |
| GET | **`/C:/Windows/win.ini`**（Windows 盘号绝对路径） | **404** | application/json | — | ✅ `is_relative_to` 兜住了 pathlib 那个「右边绝对路径吃掉左边」的坑 |
| GET | **`/` + 300 个 `a`**（> 256，与 Task 12 的截断相互作用） | 200 | text/html | no-cache | ✅ 正常 fallback；**同一发**在 `audit_log` 上落库 256 + `…[cut]`（§4.5） |
| GET | **`/assets/` + 300 个 `a` + `.js`** | **404** | application/json | — | ✅ 超长产物名不退回 index.html |
| GET | **`/s/home?x=1#frag`** | 200 | text/html | no-cache | ✅ |
| GET | **`/robots.txt`** / **`/favicon.ico`** | **404** | **application/json** | — | ⚠️ **S4**：这两格是 `is_asset_request` 第 ② 格（单段 + 扩展名在表里）的**正确**去处，而后果是浏览器标签上**没有图标**、且 `/favicon.ico` 回的是一份 JSON。`frontend/index.html` 里既没有 `<link rel="icon">` 也没有 `public/`（`static.py:162-169` 逐字记着这一格实测布局） |
| GET | `/index.html` | 200 | text/html | **no-cache** + `etag` | ✅ |
| GET | `/openapi.json` `/docs` `/redoc` | **200** | json / html / html | 一个缓存头都没加 | ⚠️ 见 §5.3 |
| GET | `/docs/nope` `/api/nope` | 404 | application/json | — | ✅ 统一错误形状（不是 200 的 HTML） |
| **HEAD** | `/login` / `/assets/index-v1XDnUhk.css` | 200 / 200 | 同 GET，**body 0 字节**，缓存头与 GET 逐字相同 | ✅ |
| **OPTIONS** / **TRACE** | `/login` | **404** / **404** | application/json | — | ✅ `_SpaRoute` 对非 GET/HEAD 连 `PARTIAL` 都不给（M18 变异证明这条守卫有牙） |
| POST | `/login` / `/api/nope` | **404** / **404** | application/json | — | ✅ |
| **DELETE** | `/api/semesters` | **405** | application/json | — | ✅ api 路由的 `PARTIAL` 胜出（smoke 第 10 步逐字断言这一格） |
| PUT | `/s/home` | 404 | application/json | — | ✅ |

### 5.2 缓存头 × 鉴权的相互作用：**没有缓存投毒的形状**

派单点名的问法是「有没有哪一格响应带了 `Set-Cookie` 却又带了可缓存的头」。实测（`p30_final.py`，裸 socket 读原始头）：

| 响应 | `Set-Cookie` | `Cache-Control` | `Pragma` | `Expires` | `ETag` |
|---|---|---|---|---|---|
| `POST /api/auth/login` → **200** | **有**（`pe_session=…; HttpOnly; Max-Age=7200; Path=/; SameSite=lax`） | **None** | None | None | — |
| `POST /api/auth/logout` → **204** | **有** | **None** | None | None | — |
| `GET /api/health` / `/openapi.json` / `/docs` / `/api/students?limit=1` / `/api/auth/me` | 无 | **None** | — | — | — |
| SPA 的 `index.html`（13 格 fallback + `/index.html`） | **无** | `no-cache` | — | — | **有** |
| `/assets/*`（带内容哈希） | **无** | `public, max-age=31536000, immutable` | — | — | **有** |

⇒ **两档都不成立**：① 带 `Set-Cookie` 的两格**一个缓存头都没有**；② 带可缓存头的两格**一个 `Set-Cookie` 都没有**。
`cache_control_for` 只被 `_spa` 调（`static.py:491-499`），而 `/api/*` `/openapi.json` `/docs` `/redoc`
在 `is_reserved` 那一格就返回 `None`、根本走不到发文件那一步（M06 变异证明 `no-cache` 那一支有守卫）。

### 5.3 ⚠️ `/docs` 与 `/openapi.json` 在**两档都公开**：判断 + 最小处置

**实测**：`PE_ENV=prod` + `PE_CORS_ORIGINS` 未设的进程内应用上，`GET /docs` → **200**、`GET /openapi.json` → **200**
（417 032 字节、74 路径 / 102 操作全在里面）；产品档 8020 上同样 200。`RESERVED_PREFIXES` 逐字含 `/docs` 与 `/redoc`，
`static.py:152-159` 的理由是「这四项都是 FastAPI 已经注册好的真路由」——**它管的是「不要被 fallback 接走」，
不是「要不要公开」**，而「要不要公开」今天**没有任何一处裁定**。

**判断：对甲方交付这算一格问题，但是 S4、不是 S1/S2。** 三条理由：
① 它**不泄漏任何一行数据**（102 个操作里 84 个挂 `security`，15 个匿名 GET 全部是参考数据/群体统计，
本席逐条实测过匿名 200 的那 7 个资源里没有一个含学生键）；
② 它泄漏的是**攻击面地图**：全部路径、参数名、请求体 schema、以及三个 securityScheme 的名字
（`pe_session` / `X-Teacher-Staff-No` / `X-Student-Id`）——⚠️ 而其中**两个请求头 scheme 在生产档是死的**
（`allow_header_identity()` 在 `prod` 下恒 `False`），故那份地图上有两格是**过时的假线索**，
一个照它发伪造请求头的攻击者会一律吃 401（本席实测）；
③ 交付形态是**内网同源单进程**，而 `/docs` 同时是甲方自己验收时最有用的一格（`demo.ps1` 与 `serve.ps1`
都把它当**卖点**打印出来）。

**最小处置**（若产品负责人裁定要收）：`create_app` 在 `is_prod()` 时传 `docs_url=None, redoc_url=None, openapi_url=None`
（FastAPI 的三个既有入参，**零新增依赖、零迁移**），并把 `RESERVED_PREFIXES` 那四项的注释同步一句；
⚠️ 代价是 openapi 五格守卫与 `gen:api` 的取法都要跟着判档（`gen:api` 自 Task 11 起走**进程内** `create_app()`，
故它不受影响——这一点是本席核过的）。**本席不擅自改**（超出只读席的权限，且这是一次口径决定）。

### 5.4 模型 ↔ 迁移 ↔ 实库：**残差 diff = 0 行**（Task 11 说的「恰好一行」今天已经是 0）

用 alembic 自己的 `compare_metadata`（不是读代码），两个库各量一遍：

| 库 | `get_current_heads()` | `compare_metadata(ctx, Base.metadata)` |
|---|---|---|
| 一个**全新**跑到 head 的临时库 | `('0ac943e0da9b',)` | **0 operation(s)** |
| **正在被 :8000 服务的那份演示库** | `('0ac943e0da9b',)` | **0 operation(s)** |

⇒ 「模型 ↔ 迁移 ↔ 实库三者一致」今天**逐字成立**。链形状：`heads = ['0ac943e0da9b']`（**单头**），
四条修订 `('0ac943e0da9b','7f3923d8af84') ('7f3923d8af84','0b7da3d20211') ('0b7da3d20211','53e5a548c40e') ('53e5a548c40e',None)`。

### 5.5 表数（两个口径自己各数一遍）

| 口径 | 实测 |
|---|---|
| `GET /api/health` 的 `tables` | **28** |
| `sqlite_master where type='table'` | **29**（多出来的那一张逐字是 `alembic_version`） |
| 29 个名字 | `alembic_version, alert, audit_log, body_composition, class_session, cleaning_log, course_section, daily_sync_run, derived_metrics, enrollment, exercise, fitness_test_batch, fitness_test_result, interest_survey, login_attempt, mini_test, notification, percentile_snapshot, prescription, prescription_template, rpe_record, semester, stratification_result, student, teacher, training_log, user_session, weekly_adjustment, weekly_class_report` |

⇒ 自报的「28 张表（health 口径；`sqlite_master` 29 含 `alembic_version`）」**逐字为真**，
且 `serve.ps1` ④ 那一步与 `restore.py` 的自检**都主动印了这一格差别**（不是等人去发现）。

### 5.6 宽度炸弹：**第 6 格没找到**，而「找不找得到」这件事本身有一条**活的**遍历守卫

* **扫描面自己数了一遍**：全库「声明了有限宽度的 `String(n)`」列 = **68** 格（与 Task 12 报的 68 逐字相同），
  最窄的宽度是 **8**（⇒ `truncate` 那一支「极窄列（`width <= 6`）」**今天确实不可达**，
  而它仍然返回一个不超宽的串 —— 本席读了 `width.py:151-162`，那一格是**许可**、不是死代码，
  与 Task 12 报的「删掉它 → 宽度 1 时返回 501 个字符」同一结论）。
* **五格逐个复核声明宽度**：`audit_log.path` **256**、`audit_log.target` **64**、`audit_log.staff_no` **32**、
  `login_attempt.login` **64**、`semester.name` **32** —— 与自报逐字相同；
  **实写长度**本席各打了一发超宽的真请求：path 落库 **256**、target 落库 **64**、限流键落库 **64**（§3.4/§4.5）。
* ⚠️ **本席另找了一遍第 6 格**，方法是「哪些**特例端点**（不经泛型 CRUD）会把客户端可控的串写进一个 `String(n)` 列」：
  * `POST /api/alerts/{id}/handle` 的 `note` → **不落库**（`alerts.py:42-47`：只记 `handled_action`，
    而它是三个模块常量之一；`AlertHandleCreate` 只有两个键）⇒ 不是炸弹；
  * `POST /api/rpe-records` 的 `rpe_token` → 只**比对**不落库；`training_log.source` → 恒为
    `feedback.CHECKIN_SOURCE` 那一个模块常量（`test_column_widths.py:253-257` 逐字这么分类）；
  * `login_attempt.ip` → 三个调用方一律交 `request.client.host`，**全仓没有一处解析 `X-Forwarded-For`**
    （`policy.py:438-459` 逐字记着这一格，且仍然设防走 `overlong_sentinel`）；
  * `user_session.id` → `secrets.token_urlsafe`，另有自己的守卫。
  ⇒ **没找到第 6 格**。⚠️ 而这不是靠本席读得全：**`test_every_declared_width_column_is_classified_and_the_classes_are_disjoint`
  是一条活的遍历守卫**——五个类两两不相交、并集 == 全库每一格 `String(n)`，而**类 4（请求体）刻意不是一张清单**、
  是从 `catalog.RESOURCES` 里 `writable=True` 的那些资源**推出来**的（`test_column_widths.py:270-313`）。
  M15（把 `audit_log.path` 改成 64）当场红、M04（把 `login` 改回 32）当场红 ⇒ 这条遍历守卫**有牙**。
* ⚠️ **CSV 摄取路径（§15 的 C3）本席复核为「真的还没做」**：`db_width.ensure_fits` 在整个 `app/` 下
  只有**两个**调用点，都在 `app/api/crud.py`（`:2268` 的 POST、`:2312` 的 PATCH）；
  `app/pipeline/extract.py` / `clean.py` **一处都没有**。
  **判断：这个延后对交付可接受**，三条理由：① 那一族列（`body_composition.device` 32 /
  `fitness_test_batch.source` 32 / `fitness_test_result.national_grade` 16）的值来自**甲方上游的导出文件**，
  不是 HTTP 客户端可控（`run-daily` 是唯一的写端点、没有 `UploadFile`）；② 本仓今天**只跑 SQLite**，
  而 SQLite 不校验 `VARCHAR(n)` ⇒ 症状是「静默存下」，不是崩；③ 正确的收口点是 `cleaning_log` **剔除**
  而不是 422（数据管道的既有形状），交付前动它会改掉管道语义。
  ⚠️ 而它是**跨后端的定时炸弹**（换 PostgreSQL 那天上游改一次字段格式就能让每日批处理炸），
  spec §15 的 C3 逐字这么登记 ⇒ 报成 **交付说明第 9 条**（换后端之前先做 C3）。

### 5.7 禁区与四个数据指纹 + 18 个模板指纹：**现算，全部相符**

| 格 | 实测（本席现算，不采信任何报告） |
|---|---|
| `backend/data/**` 文件数 | **24** |
| 四个数据指纹（sha256[:16]，小写打印） | `national_standard_2014.csv` **d2c8e539e2fa0029** ✅ / `exercises.yaml` **5394b37f01dac9ac** ✅ / `exercise_equivalence.yaml` **822cb86a5e998301** ✅ / `alert_rules.yaml` **e48e3ac82bb45bb7** ✅ —— 与自报的四个大写串**逐字相同** |
| 18 个模板指纹 | 18 个 YAML 逐个 sha256[:16] 与 `tests/domain/test_prescription_templates.py:343-362` 的 `TEMPLATE_FINGERPRINTS` **18/18 全部相符**（`C0C61D2140A521D0` … `2389C1A03E6ABBCE`）；18 个文件合计 **123 848 B**，与该文件 `:363` 那句「合计 123 848 B」**逐字相同** |
| ⚠️ 顺带验到的一格 | 本席算的是**裸字节**哈希（没做 LF 归一化），而那条守卫的口径是「行尾归一化为 LF 之后」——两者**结果相同** ⇒ 说明 `.gitattributes` 的 `backend/data/**/*.yaml text eol=lf` **真的生效了**、工作树上就是 LF |
| `backend/pe.db` | **不存在**（`Test-Path` = False，且 `backup.ps1` / `restore.ps1` 显式指它时各 **退出码 2**） |
| `backend/data/seed/` | 目录存在、**0 文件**（`-Recurse` 口径） |
| `frontend/dist` 未入库 | ✅ `git ls-files frontend/dist` **空**，且 `git check-ignore -v` 命中 `frontend/.gitignore:18:dist/` |
| `backend/backups/` 未入库 | ✅ `git ls-files backend/backups` **空**，`git check-ignore -v` 命中 `.gitignore:59:backend/backups/` |
| `.gitattributes` | 入库、**13 831 B / 174 CRLF / 0 裸 LF**；10 条活规则里含 Plan 06 Task 7 顶回后加的 `Document/**/*.md text eol=crlf`、`.superpowers/** -text`、`backend/data/**/*.yaml text eol=lf`、`*.woff2 binary`、两个 `*.ps1 text eol=crlf` |
| 全仓行尾 | `git ls-files --eol`：**898** 个文件；index = `lf 822 / crlf 46 / -text 21 / mixed 1 / none 8`。⚠️ 那**唯一一个 `mixed`** 是 `.superpowers/sdd/2026-10-06-实施计划02-…/task-2-report.md`（`attr/-text`，Plan 02 的旧报告），**不在本计划范围内**、也不是本计划改的 |

---

## ⑥ F6 + F7 · 前端的产品质量 + 测试与 smoke 的可信度

### 6.1 16 条路由 × 两档真渲染（CDP + 无头 Edge，本席自己的探针 `p11_render.mjs`，不是复用 smoke）

⚠️ 姿势：本席**另写**了一个 CDP 探针（`Network.setCookie` 种 `pe_session`、`Page.navigate`、
`Runtime.evaluate` 抓 `innerText` / `.stat` 对 / 布局谓词 / 溢出），身份用**真登录**换来的 cookie，
两档各跑一遍 16 条路由（dev = vite 5174 + 后端 8000；产品档 = 同源 8020）。

| 路由 | jar | dev（DOM 字节 / 文本 / 横向溢出 / `pageSW`） | 产品档（同四格） | 判 |
|---|---|---|---|---|
| `/login` | 匿名 | 147 639 / 858 / **0** / 1440 | 7 849 / 713 / **0** / 1440 | ✅ |
| `/bind` | 匿名 | 147 124 / 1023 / **0** | 8 305 / 878 / **0** | ✅ |
| `/s/home` | 学生 #4 | 152 053 / 1217 / **0** / **375** | 12 883 / 1170 / **0** / **375** | ✅ 四格 `108.0 / 100.0 / 1 / 1` |
| `/s/weekly-sheet` | 学生 | 158 327 / 2155 / **0** / 375 | 19 499 / 2108 / **0** / 375 | ✅ |
| `/s/check-in` | 学生 | 158 399 / 1730 / **0** / 375 | 18 691 / 1683 / **0** / 375 | ✅ 「最近 14 行（共 14 行）」⇒ **不截断** |
| `/s/rpe` | 学生 | 157 973 / 1613 / **0** / 375 | 18 555 / 1566 / **0** / 375 | ✅ 空态文案「本周没有还没交的快评」+ 口径解释（**不撒谎**） |
| `/s/mini-test` | 学生 | 156 930 / 1543 / **0** / 375 | 15 983 / 1496 / **0** / 375 | ✅ 六个 StatBlock：`66.67 / 98.3 / 35.0` + `63.75 / 92.5 / 35.0` |
| `/s/notifications` | 学生 | 151 398 / 1828 / **0** / 375 | 12 609 / 1781 / **0** / 375 | ✅ 「消息总数 1 条」 |
| `/t/dashboard` | T0001 | 210 360 / 3093 / **0** / 1425 | 40 205 / 3007 / **0** / 1425 | ✅（见下面那条 ⚠️） |
| `/t/report` | T0001 | 199 982 / 3055 / **0** / 1440 | 37 851 / 2969 / **0** / 1440 | ✅ |
| `/t/alerts` | T0001 | 220 675 / 14112 / **0** / 1425 | 70 235 / 14026 / **0** / 1425 | ✅ |
| `/t/students/1` | T0001 | 184 846 / 7799 / **0** / 1425 | 37 056 / 7713 / **0** / 1425 | ✅ 三格 `20.50 / 15.0 / 26.0` |
| `/admin` | T0003 | 161 727 / 4645 / **0** / 1425 | 22 497 / 4559 / **0** / 1425 | ⚠️ **S2**（§3 那条散文） |
| `/admin/students` | T0003 | 152 837 / 1369 / **0** / 1440 | 13 354 / 1283 / **0** / 1440 | ✅ 「共 60 行」（admin 档**应当**是全校口径） |
| `/admin/students/1` | T0003 | 146 382 / 601 / **0** / 1440 | 7 595 / 601 / **0** / 1440 | ✅ |
| `/admin/audit-logs` | T0003 | 153 455 / 2306 / **0** / 1440 | 15 422 / 2399 / **0** / 1440 | ✅ 九列 + 两个过滤 + 四段口径散文 |

**逐条结论**：**16/16 在两档都真渲染出来了**（无白屏、无「被守卫弹去 /login」、`location` 与请求的路径一致）；
**横向溢出 32/32 格全 0**；学生端 6 条的 `pageScrollWidth` **恰好 375**（= `innerWidth`，H5 那一档不出血）；
教师端/管理台的 `pageSW` 是 1425 或 1440（≤ `innerWidth`）；`.app` 的 surface class 在两档都正确
（只有 `/t/dashboard` 是 `surface-board`，其余 `surface-base`）。
⚠️ 本席的探针**没有**跑 smoke 那个两两求交的重叠谓词（只跑了溢出那一半），
故「文本内容重叠」这一格本席**采信 smoke 第 14 步**（两档各 136/136 条断言全绿，其中含每条路由的重叠拍）。

⚠️ **一格本席一度以为是缺陷、查清后不是**（如实记，因为它正是「跨波次接缝」最容易误报的形状）：
`/t/dashboard` 在 dev 档那一帧抓到 `.stat` = `红色层 7 / 黄色层 3 / 绿色层 4 / 名册人数 30`，
而 `GET /api/dashboard/class/1?week=6&as_of=2025-10-12` 回的是
`roster_size=30`、`by_layer={red:3, yellow:17, green:10, insufficient_data:0}`（**3+17+10 = 30**，自洽）。
两者对不上 ⇒ 本席追查：那一页有 **5 秒轮播**（`Dashboard.vue:44-52` 逐字写了 `:key="sectionId"` +
`<Transition mode="out-in">` + `StatBlock` 的 `rollTo`），而本席的探针是**固定 2.6 s** 取一帧、
不是轮询到内容落定；且 `7/3/4` 之和 **14** 恰等于 `demo.ps1 [7/7]` 报的「班 1 预警汇总合计 **15**」
**减去本席自己刚才 `POST /api/alerts/1/handle` 处置掉的那 1 条** ⇒ 那三格是 **ALERTS** 块的按级别汇总，
不是 LAYERS 块。**结论：非缺陷**，是本席探针的取样时机 + 本席自己把库写脏了。
⚠️ 而 smoke 第 14 步在**同一页**有真取证（期望侧取 API、被测侧用 CDP 抓 `.stat__label`/`.stat__value`，
两侧不同源），两档各 136/136 全绿 ⇒ 那一格有守卫。

### 6.2 UI 上的「全校口径残留」（教师数据隔离的可感知性）

用 **T0001**（只任教班 1 + 3）的 cookie 真渲染 + 真发请求，逐个面找「有没有哪一处仍是全校口径」：

| 面 | 实测 | 判 |
|---|---|---|
| `/t/dashboard` `/t/report` `/t/alerts` `/t/students/:id` 四条教师页 | 页面文本里**没有出现** `共 60 行` / `840` / `全校 60` 一类全校标记（本席的探针带了一个 6 串标记表逐页扫） | ✅ |
| 教师页背后的 API | `training-logs` **574**（不是 840）、`alerts` **21**（不是 32）、`weekly-class-reports` **2**（不是 5）、`mini-tests/normalized` 的 `sections` **[1,3]**（不是 5 个）、教师侧变体对不在他班里的学生 #4 → **403** | ✅ 五档收窄在 UI 上**可感知** |
| ⚠️ **一处真的残留**：管理台 `/admin/*` | `/admin/students` 渲染「**共 60 行**」。⚠️ 而这是**正确的**：那一档的 jar 是 **admin**（T0003 越过任教范围），且 `/admin/*` 的路由 `requires: 'admin'` ⇒ 普通教师**根本进不去**（会被 `beforeEach` 弹回 `/t/dashboard` + 一句 notice） | ✅ 非缺陷 |
| ⚠️ **另一处需要念清**：任何教职（**含不带班的**）打开 `/admin/students`… | 进不去（`requires: 'admin'`）；但**直接打 API** `GET /api/students?limit=200` → **200 / total=60 / 每行含 `birth`** | ⚠️ 这就是 §3.2 那一格：**API 面上的全校名册对任何教职开放**，而 UI 面把它藏在管理台后面。⇒ 报进 §⑧ 交付说明第 4 条 |

### 6.3 `listOnePage` 的截断提示：**真触发了，而且文案不撒谎**

派单点名「演示库上 9 个资源 `total` 都 < 200 故提示恒不显示 → 自己造一个 > limit 的情况」。
本席用**定点变异**造它（`S02`：`SINGLE_PAGE_LIMIT = 200` → `1`），dev 档真跑 smoke：

* 结果 **红 5 条**（`步数 16/18 · 632 绿 / 5 红`），逐条：
  `t-student-detail：DOM 里出现了 6 条关键内容 → 缺 "小测综合分"`、
  以及**三条真取证**「`DOM=[] API=["57.67"]`」/「`DOM=[] API=["32.0"]`」/「`DOM=[] API=["83.3"]`」
  （期望侧是 HTTP 响应体、被测侧是 CDP 抓的 DOM ⇒ 两侧不同源，`DOM=[]` 说明那一屏**真的没渲染出数**）、
  加第 17 步 `⑦① 反例：那个唯一住址**还在**…而它仍然是 200、且缺省参数用的就是它`。
* ⇒ **两件事同时得证**：① `SINGLE_PAGE_LIMIT` 是**承重**的（改它当场红 5 条，不是一条恒绿的常量）；
  ② smoke 第 17 步 ⑦ 那一族（源码面「0 处裸 `limit: 200`」+ 7 个组件逐个断言「走助手 + 绑进模板」+
  行为面「`limit=1` 时 alerts 回 items 1 行 / total 32」）**有牙**。
* ⚠️ **如实记一格没查透的**：本席**没有**在 DOM 上**看见**那句 `⚠️ 这一屏的数据没取全：…` 真的渲染出来
  （S02 那一跑里学生详情页先因为取不到数据而缺 needle，本席的红是「数没渲染」而不是「提示渲染了」）。
  那句文案的**渲染面**证据来自 smoke 第 17 步 ⑦ 的「7 个组件逐个断言它被绑进了模板」+
  `truncationNoteOf` 的唯一住址（`endpoints.ts:1056-1062`）；本席另做了一次变异 **S09**
  （把那句文案改字）**没有跑完**（见 §2.4 的负载说明）。⇒ 「文案不撒谎」这一格本席给的是
  **代码面 + 守卫面**的证据，不是 DOM 面的直接取证。

### 6.4 审计页与名册页的中文排版

* **审计页**：Task 12 给它加过折行（`AuditLogList.vue` 的列定义里有 `wrap: false/true` 逐列声明）；
  CDP 实测 `overflowCount = 0`、`pageScrollWidth = 1440 = innerWidth`、`innerText` 2306/2399 字符（两档），
  九列 + 四段口径散文都渲染出来了。⚠️ 长 `path`（256 字符 + `…[cut]`）在页面上的**显示**本席**没有**造出真数据来看
  （演示库上最长的那一行是本席探测留下的，而本席的渲染探针在那之前就跑完了）⇒ 如实记为**未取证**。
* **名册页**（`/admin/students`）：`overflowCount = 0`、`pageSW = 1440`；表格是 `overflow-x: auto` 的容器
  （smoke 的溢出谓词**刻意放行**这一档，理由逐字写在 `smoke.mjs:2230-2239`：管理台 21 列的表是**故意**可滚的）。
* ⚠️ **「好不好看」本席没有能力判**（只读席 + 无截图预算）：本席能给的是**机器可判**的三格
  （重叠 0 / 非故意溢出 0 / 整页不出血），以及「`—` 与 `0` 不混淆」那一格（`present.ts:52` 的 `UNKNOWN = '—'`
  是唯一住址，S01 变异证明它有守卫；实测页面上 `dashes` 计数：`/s/weekly-sheet` 13 处、`/t/report` 14 处、
  `/admin` 22 处 —— 都是「不知道」在显示成破折号，**不是** 0）。

### 6.5 F7 · `smoke.mjs` 的可信度

**(a) 两档各一整遍亲跑**：

| 档 | 命令 | 实测 |
|---|---|---|
| **产品档**（同源） | `PE_API_BASE=PE_WEB_BASE=http://127.0.0.1:8020` + `serve.ps1 -Port 8020 -SkipBuild` | **18/18 步 · 637 绿 / 0 红 · 退出码 0** |
| **dev 档** | `PE_API_BASE=http://127.0.0.1:8000` + `PE_WEB_BASE=http://localhost:5174` | **18/18 步 · 637 绿 / 0 红 · 退出码 0** |

逐步断言数（产品档那一跑，本席自己从输出里抄的）：
第 2 步 10 / 3 步 9 / 4 步 7 / 5 步 9 / 6 步 10 / 7 步 41 / 8 步 14 / 9 步 13 / 10 步 17 / 11 步 6 /
**12 步 124** / 13 步 72 / **14 步 136** / 15 步 8 / 16 步 72 / **17 步 59**（+ 第 0/1 步 30）= **637**。
⇒ 派单点名的「第 14 步那 122 条 DOM 断言」今天实测是 **136** 条（Task 9 加了审计页那一条路由 + Task 10/13 加的真取证）。

**(b) ⚠️ 632/633 → 637/637 那个差的真相：是正当收敛，判据一条都没放宽。**
Task 12 报的是 dev **632** / 产品档 **633**（差 1，因为 §C3 在产品档是 8 拍、dev 档 7 拍）；
Task 13 报的是两档各 **637**。逐字算术（task-13-report §④-3 + spec §13.11.4）：
**dev `632 + 3（小测页真取证）+ 2（§D7 dev 新鲜度两拍）= 637`**、
**产品档 `633 + 3 + 1（§D7 新鲜度在产品档只有一拍「跳过」的说明拍）= 637`**。
⇒ 那个 ±1 是被**两边各加断言**抵掉的，**不是**把某一档的判据放宽：
`§C3` 的 8/7 两档差**今天仍然存在**（§13.13.3 那张表逐字记着「产品档**已挂载**、dev 档**根本还没挂载**」这个
真实差别），新抵进来的是 `§D7` 的 2/1 差。⚠️ 本席**核了这个说法的可执行面**：
`smoke.mjs:2351-2397` 的 §D7 那一段**确实**按档分支（产品档 `fetch /src/router/index.ts` 拿到的是
`text/html` ⇒ `served = null` ⇒ 打印「这是**产品档**…本拍跳过」，只跑反空转那一拍），
且它的判据两侧**不同源**（期望侧从磁盘读 `router/index.ts`、被测侧问 dev server 要它此刻服务的那一份），
并**明确避开**了「用状态码判档」那个陷阱（注释里逐字写了「产品档的 SPA fallback 对 `/src/router/index.ts`
也回 200」）。⇒ **硬规矩 #92 没有被违反**。

**(c) 15 条「故意弄坏」实验**（派单要 15 条；本席在**前端/smoke** 这一侧完成 **5 条**、
在后端守卫那一侧完成 **23 条**，合计 **28 条**，逐条见 §2.1）：

| smoke 的弄坏实验 | 红没红 | 红在哪 |
|---|---|---|
| S01 `UNKNOWN` `—` → `0` | **红 1** | 第 17 步 ④「那个唯一住址**还在**」 |
| S02 `SINGLE_PAGE_LIMIT` 200 → 1 | **红 5** | 学生详情页三条真取证 `DOM=[]` + needle + ⑦① |
| S04 审计页**列头**「身份类型」→「身份种类」 | ⚠️ **绿（637/0）** | needle 被**过滤器**那一处同名串满足了（→ **S3/S4**） |
| S05 路由 `/admin/audit-logs` → `/admin/auditlog` | **红 2** | 第 14 步 6 条 needle 全缺 + 第 17 步 ⑥ 相撞面反空转 |
| S07 后端 `AUDITED_METHODS` 加 GET | **红 1** | 审计页第一页被 GET 行挤掉，needle `/api/auth/login` 缺 |
| S10 反例对照（smoke 不看的标签） | ⚠️ **未完成** | 负载型假红，本席**杀掉**了那一跑、按 sha 还原（§2.4） |

⇒ **有没有「不红」的**：**有 1 条（S04）**，而它的成因是 **needle 歧义**（同一个串在页面上有两处），
不是「断言结构上不可能红」。⚠️ 而 S04 这一格有实际含义：**审计页那九列的列头文案今天没有任何守卫**
（改列头不红），只有过滤器标签与 `subject_kind` 那个 slug 被钉住。→ 报成 **S3**（第 7 条）。

**(d) 黄金用例 14 条：它们钉的是什么，本计划改了这么多读的一侧它们有没有跟着变**

* 钉的是**领域层的可追溯性**：`tests/fixtures/golden_cases.json` 的 `input` / `expected` 两格，
  由 `tests/integration/test_golden_cases.py:28-49` 断言「原始值 → 得分 → 百分位 → 短板 → 标签」全链路，
  14 例 = GC01..GC14（`:42` 逐字记着「Plan 03 Task 9 加的第 14 例 GC14」）。
* **本计划一个字节都没动它**：`backend/tests/fixtures/golden_cases.json` **不在** 109 个文件的累计 diff 里。
* **判断：这是好事，不是盲区。** 黄金用例钉的是 `app/domain/**`，而 §2.3 已经证明本计划**刻意不动那一层**
  （109 个文件里 0 个 `app/domain/**`）；读的一侧（`read_scope` 五档）改的是**谁能看到哪一行**，
  不改**一行的值怎么算**。⇒ 「14 条一条都没变」与「`app/domain/` 覆盖率四格一格没动」是**同一件事的两个面**，
  两者互相印证。⚠️ 反过来说：**读的一侧今天没有黄金用例级的端到端取证**
  （「T0001 该看见哪 41 个人」这一格靠的是 `test_crud.py` 的夹具 + smoke 第 12/13 步的数字），
  而本席**自己量了一遍**那些数字（§3.1 那张表：574 / 588 / 21 / 23 / 2 / 5 / [1,3]），全部相符。

**(e) 1565 条里本计划新增了多少 + 抽 5 条核「真的在测行为」**

* 自报 **+225**（开工 collected **1340** → 结案 **1565**）。本席**核了终值**：
  `1564 passed + 1 skipped`（两遍，`--cov=app/domain` 304.33 s / `--cov=app` 322.90 s）⇒ collected **1565** ✅。
  ⚠️ 开工那一个 **1340** 本席**无法核验**（要 checkout 到 `297e846` 再跑一遍，那会破坏「只读」纪律）——如实记。
* 抽 5 条新增的核「在测行为还是在测自己」：

| 守卫 | 它测什么 | 本席怎么核 | 判 |
|---|---|---|---|
| `test_the_two_purposes_never_share_a_counter`（`test_policy.py`） | 两个限流用途不共用计数器 | **M01**（把 `"bind:"` 前缀改成 `""`）→ **红** | ✅ 测行为 |
| `test_a_locked_login_answers_byte_for_byte_like_an_ordinary_wrong_password` | 锁定档与「口令错」**逐字节**相同 | 本席**真发**了 4 次错材料 bind + 6 次错口令登录，两档响应体实测各 **108 B** / 401，且 §13.4.11 那张表的「实测 108 B」**逐字相符** | ✅ 测行为 |
| `test_the_login_column_is_at_least_as_wide_as_the_longest_key_the_policy_writes` | 声明宽度 ≥ 真写进去的最长键 | **M04**（`String(64)` → `String(32)`）→ **红**；本席另**真发**了一个 500 字符的 `student_no`，落库 `max(length(login)) = **64**` | ✅ 测行为（期望侧走真写入，**不是**自指） |
| `test_the_migration_chain_is_in_sync_with_the_models` | 链 head 与今天的模型残差 = 0 | **M12**（换掉 `ALEMBIC_VERSION_TABLE`）→ **红**；本席另用 `compare_metadata` 独立量出 **0 operation(s)** | ✅ 测行为 |
| `test_the_truncation_owner_never_widens_and_never_cuts_silently` | 「恒不超宽」+「恒留标记」 | **M02**（`_key` 不再截断）→ **红** ✅；⚠️ 而 **M03/M03b/M03c**（换掉标记本身）→ **三次全绿** | ⚠️ **半自指**：宽度那一半有牙，「不静默」那一半的期望侧读的是被测侧同一个常量 → **S2** |

---

## ⑦ F8 · 文档的真话率：**41 条可验证断言逐条真验，错 0 条、无法核验 3 条**

### 7.1 逐条核验表

| # | 断言（出处） | 实测 | 判 |
|---|---|---|---|
| 1 | 后端 **1564 passed + 1 skipped**（带 `--cov`）（§13.14.4） | `1564 passed, 1 skipped, 1 warning in 304.33s` | ✅ |
| 2 | 不带 `--cov` 是 **1565 passed** | `--cov=app` 那一遍同样 `1564 passed, 1 skipped`（collected 1565） | ✅（口径：那 1 skipped 是带 `--cov` 才跳的 trace 钩子档） |
| 3 | `app/domain/` 四格 **1268 / 0 / 376 / 0 / 100%** | `TOTAL 1268 0 376 0 100%`（18 个文件逐个 100%） | ✅ |
| 4 | 表数 **28**（health 口径）/ `sqlite_master` **29** | 28 / 29 | ✅ |
| 5 | 迁移链 **4 单头** `53e5a548c40e → 0b7da3d20211 → 7f3923d8af84 → 0ac943e0da9b` | `heads=['0ac943e0da9b']`，四条修订逐字同序 | ✅ |
| 6 | openapi **74 路径 / 102 操作 / 挂 security 84 / GET 63（15 匿名 + 48 挂 security）/ schemes 3** | 74 / 102 / 84 / 63（15+48）/ `['pe_session','X-Teacher-Staff-No','X-Student-Id']` | ✅ 五格逐字相符 |
| 7 | 前端 **16 条路由**（`routes` 数组 **20**） | smoke `ROUTES.length == 16`（断言原文「学生端 6 + 教师端 4 + 管理台 **4** + 鉴权 2」）；`routes` 数组本席逐条数 = **20** | ✅ |
| 8 | `smoke.mjs` **18 步 / 两档各 637 断言 / 退出码 0** | 产品档 18/18·637/0·0；dev 档 18/18·637/0·0 | ✅ |
| 9 | `npm run build` 退出码 0 + 四个产物哈希 | 退出码 0；`index-v1XDnUhk.css` / `index-BCWjM00F.js` / `StudentDetail-BQenvJ7d.js` / `AuditLogList-DmETt2XK.js` **四个逐字相同** | ✅ |
| 10 | `check:tokens` 绿（扫描面 36 / 下界 25）、`check:dist` 绿（25 产物 / 780 131 字符） | 两档 smoke **第 15 步各 8/8 条断言全绿**（那一步就是跑这两个守卫） | ✅（**间接**：本席没有单独跑，见 §2.4） |
| 11 | 新增依赖**只有 alembic 一个**（`alembic==1.20.0`）；前端新增 **0** | `pyproject.toml` 的 `dependencies` = 6 项既有 + **`alembic==1.20.0`**（全表唯一 `==`）、`dev` = 3；`package.json` `dependencies` **3** / `devDependencies` **7** | ✅ |
| 12 | 扫描面 **72**（pipeline 10 + db 14 + domain 18 + api 26 + auth 4） | 本席自己数 `.py` 文件：10 / 14 / 18 / 26 / 4 = **72** | ✅ 逐格相符 |
| 13 | `_MODELS_PUBLIC_BASELINE` **33**、`_MODELS_SUBMODULES` **8** | `test_models.py:777` 断 `== 33`、`:897` 断 `== 8`；**M14**（多导出一个名字）→ **红** | ✅ 且守卫有牙 |
| 14 | 黄金用例 **14** | `test_golden_cases.py:29` 逐字「14 个手工构造的典型学生」；夹具**不在**累计 diff 里 | ✅ |
| 15 | `read_scope` 五档 **7 / 0 / 13 / 1 / 2** | 本席从 `catalog.RESOURCES` 现数：`None 7 / staff_taught 13 / staff 2 / staff_taught_section 1`（`student_self` 0） | ✅ |
| 16 | 第二根轴 `StudentOwner.orphan`（判据 `taught_section` / `teacher_self`） | `crud.py:829-845` 两档；**M20** 拿掉它 → **红** | ✅ |
| 17 | 四个数据指纹 + **18** 个模板指纹 | 4/4 相符；18/18 相符；18 个文件合计 **123 848 B**（与 `test_prescription_templates.py:363` 逐字相同） | ✅ |
| 18 | `backend/pe.db` 不存在 / `backend/data/seed/` **0 文件** / `frontend/dist` 未入库 | False / 0 / `git ls-files` 空 + `check-ignore` 命中 | ✅ |
| 19 | spec **487 278 B / 4601 行 / 全 CRLF / 裸 LF 0 / 无 BOM / sha256[:16] `d5fe2ec56c333ef9`** | 487278 B / 4601 CRLF / 裸 LF **0** / BOM **False** / **`d5fe2ec56c333ef9`** | ✅ 五格逐字相符 |
| 20 | §13.4.11 的「锁定档回的是与材料不符**逐字节相同**的 403，实测 **108 B**」 | 实测 **108** 字节 | ✅ |
| 21 | §13.4.11 的「409 `password_already_bound` 实测 **270 B**」 | 实测 **270** 字节 | ✅ |
| 22 | §13.13.1 的「一个 500 字符的学号 → 改前落库 **505**」+ 收口后「恒不超过声明宽度」 | 落库 `max(length(login)) = **64**` = 声明宽度 | ✅ |
| 23 | §13.13.1 的「68 格 `String(n)`」 | 本席现数 **68** | ✅ |
| 24 | §13.9 的「`audit_log` **9** 列」「GET 一律不记」 | 9 列（`id/at/subject_kind/subject_id/staff_no/method/path/status/target`）；`method='GET'` 的行数 **0** | ✅ |
| 25 | §13.11.6 的「缺失产物 404 / index.html `no-cache` / `/assets/*` `immutable`」 | §5.1 + §5.2 逐格实测 | ✅ |
| 26 | §13.11.2 的「不改 `/api` 的任何一格可观察行为」 | `DELETE /api/semesters` **405**、`POST /api/nope` **404**、`GET /api/health` **200**、`GET /api/nope` **404**（**M18** 把 `_SpaRoute` 拿掉 → 守卫红在 `assert 405 == 404`） | ✅ |
| 27 | §13.8 的「认不出的 `PE_ENV` → 服务**起不来**」 | **M09** → `DID NOT RAISE ValueError` 当场红 | ✅ |
| 28 | §13.8 / §13.4 的「prod 下 cookie 带 `Secure`、请求头通道强制关」 | prod 的 `Set-Cookie` 末尾有 `; Secure`、dev 没有；prod + `PE_ALLOW_HEADER_IDENTITY=1` 下伪造头 **401** + 一次装配期 warning | ✅ |
| 29 | §13.10 的「备份可在线做、恢复必须先停服务」「退出码 0/2/1 三档」 | §4.2 七步逐个实测（在线备份 0、篡改 2、写锁 2、禁区 2） | ✅ |
| 30 | §13.10 的「自检打印的表数比 health **多 1**」 | 自检印 `表数 = 29`、health 印 `tables: 28` | ✅ |
| 31 | §13.12.1 的「迁移 4 的 `downgrade` 改回 32」+「只在 SQLite 上验证过」 | `0ac943e0da9b_….py:105-123` 的 docstring 逐字给了三格实测事实与两种跨后端失效 | ✅（文档面；本席**没有**真跑 `downgrade`） |
| 32 | §13.7 的「`init_db` 会自己 `upgrade head`」 | 链 3 的库上实测 `Running upgrade 7f3923d8af84 -> 0ac943e0da9b` | ✅ |
| 33 | §13.6 的 16 条路由清单（逐条路径 + `meta.requires`） | 与 `router/index.ts` 的 20 条记录**逐条相符**；16 条叶子页两档真渲染各 200 | ✅ |
| 34 | §15 **A2**「`moss` 实测 **35 处 / 13 个文件**」 | 本席 grep：**35 occurrences across 13 files** | ✅ 逐字相符 |
| 35 | §15 **D1**「印在渲染文本里的后端模块路径 **15 处 / 10 个页面文件**」 | 本席按 `<code…>….py` 口径 grep：**15 处 / 10 文件**，且逐文件分布（StudentDetail 3、AlertQueue 2、MiniTest 2、ResourceList 2、Bind/Dashboard/Home/RpeEntry/Notifications/AuditLogList 各 1）**逐格相符** | ✅ 逐字相符 |
| 36 | §15 **A3**「`src/api/auth.ts` 手写了一个 `SessionIdentity`」 | `auth.ts:70` `export interface SessionIdentity {` 仍在 | ✅ 真的还没做 |
| 37 | §15 **C3**「CSV 摄取路径的字段长度没有校验」 | `db_width.ensure_fits` 全 `app/` 下只有 **2** 个调用点，都在 `crud.py`；`pipeline/extract.py`/`clean.py` **0** 处 | ✅ 真的还没做 |
| 38 | §15 **B1**「读审计（谁翻了哪些学生的档案）今天查不到」 | `audit_log` 里 `method='GET'` **0 行**；审计页自己把这一格摊开写在页面上 | ✅ 真的还没做 |
| 39 | §15 **C1**「`progress_board` 仍是 JSON 列」 | `GET /api/dashboard/class/1` 的响应体里 `progress_board.top` 逐条带 `student_id` + `change_pct` | ✅ 真的还没做 |
| 40 | §15 **B2/B3**「没有保留/清理任务」 | `audit_log` 实测单调增长（本席探测后 36 行）；`user_session` / `login_attempt` 同样没有清理路径（`smoke.mjs` 收尾那段逐字承认「3 行 user_session 删不掉…过期行的清理任务是原型刻意不做的一档」） | ✅ 真的还没做 |
| 41 | `demo.ps1` / `serve.ps1` 打印的 URL | 逐条真发（§4.4） | ⚠️ **10 条对、2 条会露馅**（→ **S3** 第 1 条） |

### 7.2 §1.2 台账里标注为「已收掉」的那几条 + §13.4.4 的 I6：**真的收掉了吗**

| 条 | 台账怎么标 | 本席的运行时复核 | 判 |
|---|---|---|---|
| **§1.2 第 13 条**（教师的任教范围闸门不扩到泛型读） | ~~划掉~~「**已收**（第四档 `staff_taught`）」 | T0001 `training-logs` **574**（不是 840）、`alerts` **21**（不是 32）；T0002 **588 / 23**；不带班的 T9001 **0 / 0**；管理员 **840 / 32**。**M11**（把一档退回 `None`）→ 红 | ✅ **真收掉了**，且台账引的那四个数字（574/588/21/23）本席**逐个复现** |
| **§1.2 第 14 条**（`mini-tests/normalized` 仍匿名） | ~~划掉~~「**已收**（匿名 → 401 + 裁班 + schema 级摘列 + 教师侧变体）」 | 匿名 **401**；学生 #4 **200** 只自己的班；T0001 的 `sections` = **[1,3]**；`/normalized/me` 学生 **200** / 教师 **403**；教师侧变体 `/api/teacher/students/1/normalized` 对自己班 **200**、对不在班里的 #4 **403** | ✅ **真收掉了**（三格全对） |
| **§1.2 第 17 条**（无主行对任何教师都不可见） | ~~划掉~~「**已修**（第二根轴 `orphan`）」 | **M20**（拿掉第二根轴）→ **红**（1 failed / 42 passed）；**M23**（拿掉 `IS NULL`）→ 绿，而 DB 的 `ck_alert_subject_is_exactly_one` **实测有牙**（两格都非空 / 都空各被拒一次）⇒ 泄漏形状写不进去。⚠️ 演示库上「班级级预警」实测 **0 行**、`notification.recipient_kind` **19 行全是 `'student'`** ⇒ **这一格在演示库上不可达**，台账自己也逐字这么写了 | ✅ **真修掉了**（守卫面）；⚠️ **无真数据可演示**（如实记，与台账一致） |
| **§1.2 第 18 条**（`weekly-class-reports` 跨教师） | ~~划掉~~「**已收**（第五档 `staff_taught_section`）」 | T0001 list `total` = **2**（管理员 **5**）；read-one 对班 2/4/5 → **403**（台账逐字这么写）；openapi 五格本席实测 **74/102/84/63/3**，与台账说的「一个字节都没变」相容 | ✅ **真收掉了** |
| **§13.4.4 的 I6**（44 个匿名 GET 放行整套学生键健康档案） | 「已被安全收紧波收掉」+ 键级取证 | 匿名 list **200 的只有 7 个**（全是不含学生键的参考数据/群体统计），另 **16 个一律 401**；匿名 read-one（`/api/students/1`）**401**；openapi 的**匿名 GET 实测 15**（不是 44） | ✅ **真收掉了**（44 → 15，且剩下的 15 里没有一个含学生键） |

### 7.3 §15 的 16 条延后台账：**抽 6 条核「是不是真的都还没做」**

A2（`moss` 35/13 仍在）、A3（`SessionIdentity` 仍手写）、B1（GET 一行不记）、B2/B3（无清理任务）、
C1（`progress_board` 仍是 JSON 列）、C3（`ensure_fits` 不在管道里）—— **6/6 真的都还没做**。
⚠️ **反过来查了派单点名的那一档**（「若有一条其实已经做了而台账说没做，那也是发现」）：
**没有找到这样的条目**。台账里唯一被**划掉**的是 **F3**（`gen:api` 的行尾），
而 §13.14.6 逐字写了「本波实测后**划掉**」并给了实测（`gen:api` 写出 517 231 B / 10 402 个裸 LF 而 `git diff` 为空）
⇒ 划掉是**如实**的，不是漏账。

### 7.4 计划 §10 那 5 条验收口径：**本席自己对一遍**

| # | 计划原文（要点） | 本席的独立对账 | 判 |
|---|---|---|---|
| 1 | 后端 passed 只增不减；`app/domain/` 四格不许退；**新增模块自己的覆盖率单独报** | `1564+1`（两遍亲跑）✅；四格 `1268/0/376/0/100%` ✅；⚠️ **「新增模块自己的覆盖率」13 波一份报告都没报过** —— 本席替它报了：全 `app/` **7295/201/1772/115/96%**，`backend/scripts/**` **两个口径都不扫**（单独量是 531/200/**62%**） | ⚠️ **部分达标**（前两句 ✅，第三句**没兑现**）→ **S3** |
| 2 | `smoke.mjs` 在**产品档**下 18 步全绿、退出码 0 | 产品档 **18/18 · 637/0 · 退出码 0**（本席亲跑，`serve.ps1 -Port 8020 -SkipBuild` + 同源两个基址） | ✅ |
| 3 | 四个数据指纹 + 18 个模板指纹逐字不变；`pe.db` 不存在；`data/seed/` 0 文件 | 4/4 + 18/18 现算相符；`pe.db` **False**；`data/seed/` **0**；`git ls-files backend/data` = **24** | ✅ |
| 4 | **新增依赖只有 alembic 一个**；前端新增 0 | 后端 `dependencies` 7 项（6 既有 + `alembic==1.20.0`）、`dev` 3；前端 3 + 7；`tests/test_dependencies.py` 在全量跑里**一条都没红** | ✅ |
| 5 | 每个 Task 一份预检探针；变异测试在 Task 3/8 要求 | Task 13 自己标了 **⚠️ 部分**（探针落在 `$env:TEMP` 并删净，故不可复核）；变异实测**超额**（Task 3/8/8b/9/10/11/12/13 都做了） | ⚠️ **部分达标**（与 Task 13 的自评一致，本席**同意**它的自评） |

⇒ 本席的对账结果与 Task 13 的自评（**4 ✅ / 1 ⚠️**）**只在第 1 条上更严一格**：
Task 13 把第 1 条标成 ✅，而它的后半句「新增模块自己的覆盖率单独报」**没有兑现**（→ **S3**）。

---

## ⑧ F9 · 交付就绪度的总判断 + 全部发现的分级汇总

### 8.1 总判断（**不含糊**）

**1）这个仓库今天能不能直接交给甲方？——能，条件是先把下面那**一条**改掉。**

按 spec §13 走一遍的实测结果：**起服务 ✅**（`serve.ps1` 一条命令，产品档 200）／
**灌演示数据 ✅**（`demo.ps1`，`[7/7]` 十三个行数逐个印出来）／
**演示 16 条路由 ✅**（两档 CDP 真渲染 16/16、横向溢出 0）／
**备份恢复 ✅**（七步全过，含链 3 备份 + 链 4 代码那一格自愈）／
**审计留痕 ✅**（写请求逐行落库、超长路径截断带标记、管理台有只读页）／
**smoke 两档 637/637 ✅**／**后端 1564+1 ✅**／**残差 diff 0 ✅**／**禁区四格全清 ✅**。

**唯一一条「交付前必须改」的阻塞项是 S2-①**：管理台首页 `/admin` 上那段「三个口径」散文
（`frontend/src/views/admin/ResourceIndex.vue:101-109`）**与今天的鉴权实物相反**，而它是甲方**打开管理台就看到**的一屏。
它是 **9 行文案**、不动后端、不动迁移、不动守卫。

**2）若不能，最小阻塞项（按严重度）：** 只有 1 条 —— **S2-①**。
（S2-② 是**守卫面**的洞、不是产品面的洞：今天 shipped 的行为是对的，故它不阻塞交付，但它阻塞「下一波敢改 `width.py`」。）

**3）交付时必须一并说明的注意事项（9 条，逐条都有本席的实测）：**

1. **产品档缺省是 `dev` 档**。`serve.ps1` 不带环境变量起的服务：cookie **不带 `Secure`**、CORS 挂 `["*"]`、
   启动自检**不跑**。上 HTTPS 反代之后**必须**自己设 `PE_ENV=prod` + `PE_CORS_ORIGINS=<白名单>`
   （脚本刻意没有 `-Prod` 开关，理由它自己印在 ⑤ 那一段）。⚠️ 而**请求头身份通道两档都是关的**
   （`serve.ps1` 与 `demo.ps1` 都**强制清**掉 `PE_ALLOW_HEADER_IDENTITY`，`prod` 下代码里也恒 `False`）。
2. **演示口令是公开的**（`pe-demo-2025`，`demo.ps1 [6/7]` 与 spec §13 都印着它），
   且演示库的哈希用 **100 000** 次迭代（= 下界）；生产缺省是 **600 000**。甲方现场**必须**重灌名册 + 换口令。
3. **读审计今天不记 GET**：「谁翻过哪个学生的健康档案」在库里**查不到**（`audit_log` 里 `method='GET'` 实测 **0** 行）。
   审计页自己把这一格摊开写在页面上；要它得另开一张表（§15 的 **B1**）。
4. ⚠️ **任何教职账号（含一个不带任何班的新教师）都能一次 `GET /api/students?limit=200` 读到全校 60 人的名册，
   含 `birth`**；而 `birth` 正是学生绑定口令的**唯一验身材料** ⇒ 一个教职可以替任何**还没绑定**的账号抢先绑口令
   （本席完整跑通了这条链：匿名 bind **204** → login **200**）。教师那一侧同形（`/api/teachers` 给 `name`）。
   **这是 spec §1.2 第 4 条与 §13.4.4 五档表逐字登记过的已接受残余**，不是本计划引入的，
   而**交付时必须念给甲方听**（生产处置：换成不可猜的验身材料 —— 一次性绑定链接 / 校园卡后台校验）。
5. **被降权的管理员在重登之前，`/api/auth/me` 仍然回 `role: 'admin'`** ⇒ 前端还会把他送进 `/admin`，
   然后每一次读写都吃一个 **403**（**权限**是立刻生效的：本席实测降权后同一个会话 `audit-logs` 当场 403）。
   spec §1.2 第 7 条逐字登记过它，失效方向是**安全**的（少给权限）。
6. **三张表单调增长、没有清理任务**：`audit_log` / `login_attempt` / `user_session`（§15 的 **B2/B3**）。
   而 §13.10 的备份是**整库**备份 ⇒ 备份文件跟着一起变大。跑一学期之前要先把归档作业定下来。
7. **备份不加密**：`backend/backups/` 下是一份**明文** SQLite（里面是全校学生的健康档案）。
   `backup.ps1 -Dir D:\pe-backups` 已经支持落到别的盘（加密卷）；也**不做**保留策略（不会自己删旧备份）。
8. **限流是按标识、不按 IP**：一个匿名调用方拿别人的学号连错 **5** 次口令能把那个人锁 **15** 分钟
   （bind 那一侧是 **3** 次锁 **60** 分钟），而锁定档回的响应与「口令错」**逐字节相同**（**108 B**）⇒
   被锁的合法用户得不到任何提示。生产要在**反代**那一层补全局限速（§15 的 **B4**）。
9. **换数据库后端之前必须先做 §15 的 C3**（CSV 摄取路径的字段长度今天无校验）与**迁移 4 的 `downgrade` 重写**
   （它是 SQLite 专用的 `batch_alter_table`，PG 上会当场失败、MySQL 上会静默截断 ⇒ 两个绑定键撞成同一个）。

**4）本席这一席的置信度**

| 面 | 置信度 | 查了什么 / **没查透什么** |
|---|---|---|
| **F1 守卫强度** | **高** | 28 次定点变异（22 红 / 6 绿 / 1 未完成），6 次绿逐个定性、其中 3 次是**同一条自指守卫**；覆盖率四格的真相用**两遍全量亲跑** + 一次 `--cov=scripts` 定量。**没查透**：`check:tokens` / `check:dist` 的**内部**强度（只采信 smoke 第 15 步的 8/8）；S10 反例对照未完成 |
| **F2 鉴权接缝** | **高** | 9 组自构组合 × 真状态码；五档分布自己数；两档 cookie 头逐字对比；限流两方向 + 超长键撞车 + 迭代上下界 8 个取值；降权 immediacy；roster→bind 接管链完整跑通。**没查透**：`orphan` 第二根轴在**真数据**上的行为（演示库上那一档 0 行，只能用变异取证）；**pending 帧无超时**那一格是静态推断 |
| **F3 交付可用性** | **中高** | 一条命令起产品档 ×2（含 rebuild 与 `-SkipBuild`）；备份/恢复七步全跑（含链 3→链 4、篡改、写锁、禁区、在线备份）；文档 URL 逐条真发；16 条路由真发。**没查透**：**真·干净检出**（无 `frontend/dist`）与**真·空库**上起产品档（只做了代码面取证）；`alembic downgrade` 没真跑 |
| **F4 + F5** | **高** | 自构 **36 格** fallback（裸 socket，含大小写 / 双斜杠 / `%2f` / `..%2f` / 盘号绝对路径 / 300 字符 / HEAD / OPTIONS / TRACE / `/assets` 无尾斜杠）；缓存头 × Set-Cookie 全矩阵；残差 diff 用 `compare_metadata` 两个库各量一遍（**0**）；68 格 `String(n)` 现数；四指纹 + 18 模板指纹现算。**没查透**：`/docs` 公开那一格只给了判断，没有替产品负责人裁定 |
| **F6 前端质量** | **中** | 16 条路由 × 两档 CDP 真渲染（DOM 字节 / 文本 / 溢出 / `.app` class / StatBlock 对）；教师隔离在 UI 与 API 两面各查一遍；截断提示用变异真触发。**没查透**：① **重叠谓词**没自己跑（采信 smoke）；② **「好不好看」没有能力判**（无截图预算）；③ 截断提示的**文案渲染**没在 DOM 上直接看见；④ 审计页上 256 字符 + `…[cut]` 的**显示**没造真数据看；⑤ `/t/dashboard` 那一帧本席取样在轮播过渡帧上（已解释为非缺陷，但**没有**做稳定帧二次取证） |
| **F7 smoke 可信度** | **中高** | 两档各一整遍亲跑（637/637 ×2）；5 条弄坏实验（4 红 1 绿）；632/633→637/637 的算术与**代码面**都核了；黄金用例 14 条的归属核了；新增守卫抽 5 条核「在测行为」。**没查透**：弄坏实验只做了 **5** 条（派单要 15 条；本席把另外 23 条花在后端守卫上，合计 28 条）；`+225` 的**起点 1340** 无法核验（要 checkout 旧 commit） |
| **F8 文档真话率** | **高** | **41 条**可验证断言逐条真验（**错 0 条 / 无法核验 3 条**：`check:tokens`/`check:dist` 的内部数字是间接采信、开工 collected 1340 无法回溯、迁移 4 的 `downgrade` 没真跑）；台账「已收掉」5 条逐个运行时复核；§15 抽 6 条核「真没做」+ 反查「有没有其实做了的」（0 条）；计划 §10 五条自己对账 |
| **F9 总判断** | **高** | 结论建立在上面七面的实测上 |

### 8.2 全部发现的分级汇总表

**S1（Critical）：0 条。**
⚠️ 本席**敢说 0** 的依据（不是「没查到」，是「查了这些面都没查到」）：
① 鉴权的**每一档**都真发过请求（匿名 / 学生 / 教师 / 不带班的教师 / 管理员 / 降权后的管理员 / 伪造请求头 × 两档），
没有一个组合多给了一行数据；② 越界的**每一种形状**都真打过（`..%2f` / `%2e%2e` / 盘号绝对路径 / 超长路径 /
大小写 / 双斜杠 / 五个 HTTP 方法），**一个字节都没泄漏**、且失效方向一律是 404 而不是 200；
③ 备份/恢复的**四条失效路径**（篡改 / 写锁 / 禁区 / 跨链版本）都是**响亮**的（退出码 2 或自愈），
且恢复**之前**先留后路；④ 迁移链与模型**残差 0**，`init_db` 自动 `upgrade head`；
⑤ 审计**不因超宽请求而消失**（截断到 256 + 可辨识标记，401 上也照写）；
⑥ 28 次定点变异里**没有一次**是「删掉一格安全检查而全仓绿」（6 次绿逐个定性，见 §2.2）；
⑦ 数据丢失面：四个数据指纹 + 18 个模板指纹 + 24 个文件 + 三个禁区，**现算全部相符**。

| 级别 | 条数 | 一句话标题 |
|---|---|---|
| **S2** | **2** | ① 管理台首页那段「三个口径」散文与今天的鉴权实物**相反**（读是匿名的 / 48 个匿名 GET / 写要教师身份 / `require_teacher` / 去身份切换器选教师）② `OVERLONG_SUFFIX` 的「不许静默截断」守卫是**自指**的：换成 6 个空格全仓不红 |
| **S3** | **7** | ① `demo.ps1` 的 8 条「登录后可以这样点」里 **2 条是学生专用**（教师会话 403），脚本没说每条要哪种身份 ② 覆盖率口径：`--cov=app/domain` = 产品语句的 **17.4%**，`backend/scripts/**` **两个口径都不扫**；计划 §10 第 1 条后半句「新增模块自己的覆盖率单独报」**没兑现** ③ `taught_student_ids` 的两格 `semester_id` **单独去掉任一格全仓不红**（代码里自己登记的边界，本席实测复核为真：两格一起去掉才红 2 条）④ `_orphan_condition` 的 `IS NULL` docstring 说「承重」而**无守卫**（被 DB 的 CHECK 兜住，实测那条 CHECK 有牙）⑤ **会话恢复没有超时**：`/api/auth/me` 挂住时页面无限期停在「身份未确认…」（**静态推断，未取证**）⑥ 仓库根**没有 README**，且 spec §13.6 的运行命令用了 PS 5.1 不支持的 `&&` ⑦ smoke 的 `身份类型` needle **歧义**（页面上两处同串）⇒ 审计页九列的**列头文案今天没有任何守卫** |
| **S4** | **5** | ① `/API/health`（大小写变体）在产品档回 **200 + index.html**（大小写打错的监控探针会误判「服务活着」）② `/favicon.ico` 与 `/robots.txt` 回 **404 + application/json**（浏览器标签上没图标）③ `/docs` `/redoc` `/openapi.json` 在**两档都公开**（74 路径 / 102 操作 / 417 KB 契约对匿名开放；含两个在生产档已经死掉的请求头 scheme）④ 迭代下界的代价：一份用 **< 100 000** 次迭代写的库会**全体登不进来**，唯一可见性是一行日志 ⑤ `restore.py` 只**印**恢复后的 `alembic_version`、**不判**「备份的版本比当前代码旧」，且从恢复完到下一次起服务之间那个库真的停在旧链上 |

### 8.3 逐条发现（按派单给的形状）

```
【S2】管理台首页那段「三个口径」散文与今天的鉴权实物相反
- 面：F6 + F8
- 现象：frontend/src/views/admin/ResourceIndex.vue:101-109 渲染出来的三句（CDP 两档实测原文，
  OUT_render.txt 第 76 / 168 行）：
    「**读是匿名的**：23 个资源的列表与详情都不需要身份（后端 **48 个匿名 GET** 里就包括这 23 个 list 与 23 个 read-one）」
    「**写要教师身份**：9 个可写资源的 POST / PATCH / DELETE 全挂了 require_teacher，匿名写是 401」
    「故在没选教师身份时…要先去左上角的身份切换器选一个教师」
  实测（p17_claims.py，真 HTTP :8000）：23 个资源里匿名 list 200 的只有 **7** 个、另 **16** 个 **401**；
  `GET /api/students/1` 匿名 **401**；openapi 的匿名 GET 实测 **15**（不是 48）；
  `POST /api/students` 用**教师** T0001 的 cookie → **403**「身份 'T0001' 不是管理员…仅 role='admin' 可用」；
  `require_teacher` 这个名字今天在 app/api/deps.py 里**不存在**（Plan 05A Task 2 改名成 require_staff）；
  「左上角的身份切换器」在产品档**不渲染**（DEV-only：产品档那一帧的会话条实测是「会话状态 authed」，
  dev 档才有「开发期请求头 | 学生 | 教师 | 不发头」那一块）。
- 为什么是问题：失效方向**静默**（smoke 的 admin-index needles 是
  ['资源目录','23 resources','可写 9','只读 14','体育专家维护的知识资产']，一条都不碰那三句 ⇒ 637/0 全绿）。
  受害者是**甲方**：读「读是匿名的」会以为全校健康档案对公网开放（于是拒收、或自己去"修"一处本来是对的鉴权）；
  读「写要教师身份」会**低估**管理台的保护（实际是仅管理员）；读「去身份切换器选一个教师」会去找一个
  在产品档上**不存在**的控件。⚠️ 这与 Task 13 刚修掉的那 2 条撒谎 URL 是**同一类**失效，只是漏在 UI 上。
- 最小处置：改 ResourceIndex.vue:101-109 三句散文（读要身份：7 个参考数据资源匿名、16 个要教职或本人；
  写**仅管理员** require_admin，教师 403；删掉/改写「身份切换器」那半句）。
  **不动后端、不动迁移、不动 openapi**（⇒ 不需要重跑 gen:api）。
  ⚠️ 建议同时给 smoke 的 admin-index 加一条 needle（例如「仅管理员」或「require_admin」）把这一段钉住，
  否则下一次它还会漂。
- 取证可复现性：$env:TEMP\p06t14\p17_claims.py（HTTP 实测）+ p11_render.mjs（CDP 两档渲染原文）；
  两个都可重跑（要 demo.ps1 :8000 + vite :5174 或 serve.ps1 :8020 起着）。
```

```
【S2】「不许静默截断」那条守卫是自指的：把截断标记换成 6 个空格，全仓一条守卫都不红
- 面：F1
- 现象：定点变异三次（p10_mutate.py M03 / p12_mutate2.py M03b、M03c），
  app/db/width.py:116 的 `OVERLONG_SUFFIX = "…[cut]"` 分别改成 `"..."`、`"      "`（6 个空格）、`"…"`，
  `pytest tests/api/test_column_widths.py` 三次**全绿（16 passed）**，每次还原后 git status 空。
  成因在守卫自己身上：test_column_widths.py:447 逐字是 `suffix = width.OVERLONG_SUFFIX`
  ⇒ 期望侧与被测侧**同源**；它钉的是「截完以**本模块自己声明的**那个标记结尾 + 总长恰好等于声明宽度」，
  钉不住「那个标记在真实数据里**辨不辨得出来**」。
  而 app/db/width.py:62-64 用一整段论证了为什么必须是 `[cut]`：
  「一个孤零零的 `…` 会出现在**真实数据**里…于是『这一格被截过』与『这一格本来就有个省略号』不可分辨」，
  派单也逐字要求「不许静默截断」。
- 为什么是问题：失效方向**静默**。有人把标记换成不可见的 6 个空格之后，`audit_log.path` 的
  「这一行被切过」在库里与审计页上**看不出来**了，而 `len == 256` 那一格仍然绿、
  `test_the_truncation_owner_never_widens…` 仍然绿。受害者是**读审计的教务/运维**（与 §13.9 的
  「审计要能指认『对哪一个做了什么』」直接冲突）。⚠️ 今天 shipped 的行为是**对的**
  （本席实测 305 字符路径落库 256 且尾部逐字 `…[cut]`、400 字符路径参数落库 target 64 且尾部 `…[cut]`），
  故这一条是**守卫面**的洞、不是产品面的洞。
- 最小处置：给那条守卫加一拍**字面量**断言 `assert width.OVERLONG_SUFFIX == "…[cut]"`
  （这是一次**刻意的第二所有者**，与 `_MODELS_PUBLIC_BASELINE` 钉 33、`TEMPLATE_FINGERPRINTS` 钉 18 个 sha
  同一条姿势 —— 本仓已经反复用过这一招）；或加「标记不得是任何合法路径/工号的子串」那一档。
  不动产品代码、不动迁移。
- 取证可复现性：$env:TEMP\p06t14\p10_mutate.py（M03）、p12_mutate2.py（M03b/M03c），
  输出 OUT_mutate.txt / OUT_mutate2.txt（每次变异都印了 exit code + 还原后的 git status + 文件 sha256[:16]）。
```

```
【S3-①】demo.ps1 的 8 条「登录后可以这样点」里有 2 条是学生专用，教师会话点了是 403
- 面：F3 + F8
- 现象：backend/scripts/demo.ps1:245-255 印「一条闭环（spec §1.3 的三段）**登录后**可以这样点」，
  头两条是 `GET /api/students/1/prescriptions/current?as_of=2025-10-12` 与
  `GET /api/students/1/weekly-sheet?as_of=2025-10-12`。实测用**教师** T0001 的 cookie 打这两条 →
  **403**「当前会话是 teacher（T0001），而本端点要的是学生身份：一个教师/管理员的 cookie 不能当学生用」；
  另 5 条（alerts / handle / notifications / dashboard/class/1 / mini-tests/normalized）教师档各 **200**。
  ⚠️ 而脚本自己的账号清单同时给了「教师 T0001 / T0002」与「管理员 T0003」，
  且**没有**说这 8 条各自要哪一种身份。（本席也核了它**巧合**能通的那一档：脚本 [6/7] 从库里打印的那个
  「真例子」学号是 2025060001，而它恰好是 `student.id = 1` ⇒ 照那个例子登录成学生，这两条就通了。）
- 为什么是问题：失效方向**响亮但误导**（403 的报文说的是「一个教师的 cookie 不能当学生用」，
  而演示者会先怀疑后端坏了）。受害者是**做演示的人**（可能是甲方自己）。
  与 Task 13 刚修的 2 条撒谎 URL **同一类**（那一次的判据逐字是「念给甲方听时会当场露馅」）。
- 最小处置：给那 8 条各标一个身份（例如行尾加 `# 学生` / `# 教师或管理员`），
  或把那 2 条学生专用的挪到「用学生身份点」的小节下。**只改 demo.ps1 的打印**，不动端点。
  ⚠️ 而 smoke 第 17 步 ① 会读 demo.ps1 的打印，改完要重跑一次 smoke。
- 取证可复现性：$env:TEMP\p06t14\p13_urls.py（OUT_urls.txt 逐条状态码）。
```

```
【S3-②】覆盖率口径：那四格「100%」量的是产品语句的 17.4%，而 backend/scripts/** 两个口径都不扫
- 面：F1 + F8
- 现象：见 §2.3 的三张表（两遍全量亲跑 + 一次 --cov=scripts）。
  `--cov=app/domain` → TOTAL 1268/0/376/0/100%；`--cov=app` → TOTAL **7295/201/1772/115/96%**；
  `--cov=scripts`（跑真的会调它们的那三个测试文件）→ backup.py 88% / restore.py 80% /
  dump_openapi.py **45%** / serve_app.py 92% / demo_bootstrap.py **0%**，TOTAL 531/200/**62%**。
- 为什么是问题：**不是撒谎**（那四格逐字为真、口径也逐字写明是 app/domain/），
  而是**误导性的读法**：13 份报告都把它当质量总账的第一格，而本计划新增的 ~5900 行产品代码
  与 ~1300 行运维脚本**一个都不在那个口径里**。计划 §10 第 1 条后半句
  「（新增模块自己的覆盖率**单独报**）」**13 波一份都没兑现**。受害者是**下一个接手的人**
  （他会以为「100%」是全仓的）。
- 最小处置：不改代码、不改守卫。把 §2.3 那三张表落进 spec（§13.14.4 的数字总账加两行：
  全 `app/` 的 7295/201/1772/115/96%、`backend/scripts/**` 的 531/200/62% 并明写「两个既有口径都不扫它」），
  并把 §10 第 1 条的对账从 ✅ 改成 ⚠️ 部分达标（与 Task 13 对第 5 条的处置同一条姿势）。
- 取证可复现性：$env:TEMP\p06t14\cov_domain.txt / cov_app.txt / cov_scripts.txt（三份原始输出）。
```

```
【S3-③】taught_student_ids 的两格 semester_id：单独去掉任一格，全仓 185 条测试一条都不红
- 面：F1 + F2
- 现象：p16_round4.py 亲跑四遍（每遍 185 条，含 tests/api/test_dashboard.py）：
  基线 exit 0；**只**去掉 `CourseSection.semester_id == semester_id` → exit **0**；
  **只**去掉 `Enrollment.semester_id == semester_id` → exit **0**；
  **两格一起去掉** → exit **1**、**恰好红 2 条**
  （test_teaching_last_semester_does_not_grant_access_this_semester /
  …_to_the_home_page，各 `assert 200 == 403`）。每次还原后 git status 空。
- 为什么是问题：这一格**代码里自己登记了**（app/api/deps.py:1088-1096 逐字：
  「单独去掉任一个都不红 —— 两个一起去掉才红 2 条」，并说明了缺的那一档是什么形状、
  「本仓今天没有那样的夹具 —— 如实记为已知边界」）。⇒ **本席的结论是「那句自述逐字为真」**，
  报成 S3 而不是 S2：它是一格**真实的守卫面盲区**（「上学期教过 ≠ 这学期能读」这条性质
  只有两格**同时**被拿掉才会响），而失效方向是**多给数据**（静默）。受害者是**学生的隐私**。
- 最小处置：补一个夹具 —— 一条「`enrollment.semester_id` 是本学期、而它指向的
  `course_section.semester_id` 是上学期」的行（deps.py 自己指明这正是缺的那一档），
  于是单格去掉也会红。**不动产品代码、不动迁移。**
- 取证可复现性：$env:TEMP\p06t14\p16_round4.py（OUT_round4.txt 四遍逐条）。
```

```
【S3-④】_orphan_condition 的 IS NULL 那一格：docstring 说它「承重」，而它没有守卫
- 面：F1
- 现象：M23（app/api/crud.py:829-830 的 `if orphan.by == ORPHAN_BY_TAUGHT_SECTION:
  conditions.append(getattr(model, owner.column).is_(None))` → `if False:`）
  → `pytest tests/api/test_crud.py` **50 passed、exit 0**（不红）。
- 为什么是问题 / **为什么它不是缺陷**：本席**实测那条 DB 约束有牙** ——
  往演示库副本里 INSERT「student_id 与 course_section_id 都非空」→
  `IntegrityError CHECK constraint failed: ck_alert_subject_is_exactly_one`；
  「两格都空」→ 同样被拒（约束原文 `CHECK ((student_id IS NULL) <> (course_section_id IS NULL))`）。
  ⇒ 那一格在**今天的写入方 + 今天的 DDL** 下与不加它**语义等价**，而 crud.py:806-813 的 docstring
  逐字这么写了（「故本格在今天的写入方下与不加它等价；而它是『将来有人给学生级预警也填上班』时
  唯一挡得住的一格」）。⇒ 报成 S3（**守卫面**盲区：那一格的价值只在将来，而将来它不会响），
  **不是** S2。
- 最小处置：给 test_crud.py 加一条**直接构造**那个形状的守卫（绕过 CHECK 的唯一办法是断言
  「CHECK 存在且文本逐字是 `(student_id IS NULL) <> (course_section_id IS NULL)`」），
  于是「将来有人放宽那条 CHECK」会先红在这一条上。**不动产品代码。**
- 取证可复现性：$env:TEMP\p06t14\p12_mutate2.py（M23）+ p15_round3.py（CHECK 有牙的两次 INSERT）。
```

```
【S3-⑤】会话恢复没有超时：/api/auth/me 挂住时页面无限期停在「身份未确认…」
- 面：F2 + F6
- 现象（⚠️ **静态推断 + 代码取证，未做运行时取证**，照硬规矩 #89/#103 如实标注并降级）：
  frontend/src/router/index.ts:319-332 的 beforeEach 在任何判定之前 `await session.ensureRestored()`；
  frontend/src/stores/session.ts:259-286 的 ensureRestored **没有任何超时**；
  frontend/src/api/client.ts 只把 `signal?: AbortSignal` 当**可选入参**转交（:318 / :393），
  而 `api/auth.ts` 的 `fetchMe()` **不传它**。
  ⇒ 一个接了 TCP 连接却不响应的 /api/auth/me（反代挂住、SQLite 长时间写锁）会让页面停在
  「身份未确认…」/ `PENDING…` **没有上限**，既不落 authed 也不落 anon、也不弹去 /login。
- 为什么是问题：这是 Task 12 / C3 那一帧修好之后**新出现**的卡住形态（改前那一帧会说「未登录」——
  一句假话，但用户至少有一个「去登录」的出路；改后那一句是真话，而**出路没有了**）。
  失效方向**静默**（没有报错、没有横幅，只是一直转）。受害者是**任何一次网络/后端卡顿下的终端用户**。
  ⚠️ 与 §13.13.3 的裁定**不冲突**（那一节的三条代价「不抄 localStorage / 不藏报头 / 不阻塞首屏」
  一个都没付），本席说的只是「阻塞**没有上限**」这一格。
- 最小处置：给 ensureRestored 那一次 fetchMe 挂一个 `AbortSignal.timeout(N)`（N 建议 10 s），
  超时按**既有的「后端不可达」那一支**处置（退回 `unknown` + `asked` 保持 false + `throw`
  ⇒ 守卫放行、让页面自己的错误横幅说真因）。**零新增依赖**（Node/浏览器都自带），
  不动后端、不动迁移；⚠️ 要同步 smoke 第 17 步 ⑧ 那 6 条断言里的「那个谓词在 src/** 里恰好 1 处」。
- 取证可复现性：**未能复现**（要一个故意挂住的 /api/auth/me；本席的 CDP 探针没有实现 Fetch 域的
  「扣住不放」）。⇒ 本条**只有静态证据**，故标 S3、不标 S2。
```

```
【S3-⑥】仓库根没有 README，而 spec §13.6 的运行命令用了 PowerShell 5.1 不支持的 &&
- 面：F3 + F8
- 现象：① `Glob *.md`（仓库根）→ **0 个命中**；甲方运维拿到的唯一「怎么跑」的活文档是
  **487 278 B / 4601 行**的 Document/2026-09-28-…spec.md §13（+ 两个 .ps1 的注释与启动打印）。
  ② spec:2645 那段代码块逐字是 `npm install && npm run dev`，而本仓的目标运维环境是 Windows
  PowerShell **5.1**（两个 .ps1 的注释里逐字交代过 PS 5.1 的坑：BOM / ANSI 代码页 / 没有 `&&`），
  PS 5.1 上 `&&` 会当场报「标记 "&&" 不是此版本中的有效语句分隔符」。
- 为什么是问题：失效方向**响亮**（`&&` 当场报错），而「没有 README」是**静默**的
  （运维会在一个 4601 行的设计 spec 里找运行方式）。受害者是**甲方运维**。
- 最小处置：① 把 §13.6 那一段的 `&&` 换成 `;`（或拆成两行），与 §13.1/§13.11 既有的
  `powershell -ExecutionPolicy Bypass -File …` 姿势一致；② 交付时附一页纸的 run book
  （或明写「运行方式在 spec §13.1 / §13.6 / §13.11」）。**不动代码、不动守卫。**
  ⚠️ 本席**不建议**新建 README.md（那会是第 4 个「怎么跑」的所有者：spec §13、两个 .ps1 的注释、README）。
- 取证可复现性：Glob（根目录 *.md = 0）+ Read spec:2643-2649。
```

```
【S3-⑦】smoke 的「身份类型」needle 歧义 ⇒ 审计页九列的列头文案今天没有任何守卫
- 面：F7
- 现象：S04（frontend/src/views/admin/AuditLogList.vue:116 的列定义
  `{ key: 'subject_kind', label: '身份类型', wrap: false }` → `label: '身份种类'`）
  → smoke **637 绿 / 0 红、退出码 0**（不红）。成因：页面上有**两处**「身份类型」——
  过滤器下拉的标签（AuditLogList.vue:331）与列头（:116），而第 14 步那条 needle
  被过滤器那一处满足了。
- 为什么是问题：失效方向**静默**。审计页那九列的**列头文案**（本仓「九格全是标量、一个都不多」的
  那一格在 UI 上的唯一可见面）今天改字不会响。受害者是**读审计的教务**（列头对不上后端字段名时，
  「subject_kind 是什么」这一格就无从对照）。⚠️ 严重度**低于** S2：那一页的**数据**有真取证
  （needle 里有 `/api/auth/login` 那一格 = 后端给的真行），漂的只是列头文字。
- 最小处置：把那条 needle 换成一个**只在列头出现**的串（例如与 `key` 同排的另一个列头，
  或改成「按 `.a-table th` 抓九个列头逐字比 `AuditLogRead` 的九格」——后者与 §13.9
  「九格一个都不多」的既有裁定同一条口径）。**只改 smoke.mjs**，不动产品代码。
- 取证可复现性：$env:TEMP\p06t14\p29_driver.ps1 的 `[2]` 那一轮（OUT_sb6.txt）。
```

```
【S4-①】/API/health（大小写变体）在产品档回 200 + index.html
- 面：F4
- 现象：裸 socket 打 `GET /API/health` 与 `GET /Api/Health` → 各 **200 / text/html; charset=utf-8 /
  no-cache / 2729 B**（= index.html）。成因：app/static.py:160 的 RESERVED_PREFIXES 与
  is_reserved 的判据都是**大小写敏感**的，而 Starlette 的路由匹配同样大小写敏感
  ⇒ `/API/health` 既不是保留前缀、也不是真端点，于是走 fallback。
- 为什么是问题：失效方向**误导**（不是泄漏：一个 200 的 HTML 里没有任何数据）。
  受害者是**甲方运维的监控探针**（一个把 `/API/health` 写错的 uptime 检查会**永远绿**）。
- 最小处置：**可以不改**（本席倾向不改：把 is_reserved 改成大小写不敏感会让 `/API/*` 一律 404，
  而 `/LOGIN` 一类前端路由的大小写变体今天回 index.html 是**对的**，两者要分开判就得再加一档判据）。
  若一定要改，最小形状是「`is_reserved` 里对 `/api` 那一项额外比一次 `url_path.lower()`」，
  并给 test_serve.py 的 13 格矩阵加两格。
- 取证可复现性：$env:TEMP\p06t14\p03_fallback.py（36 格矩阵，OUT 直接打在终端上）。
```

```
【S4-②】/favicon.ico 与 /robots.txt 回 404 + application/json
- 面：F4 + F6
- 现象：两格各 **404 / application/json / 66 B**。成因：app/static.py:284-309 的 is_asset_request
  第 ② 格（**单段**路径 + 扩展名在 _MEDIA_TYPES 里）⇒ 磁盘上没有它就 404、**不** fallback；
  而 frontend/dist 的根级**只有** index.html（static.py:162-169 逐字记着这一格实测布局：
  「根级没有任何静态文件…既没有 <link rel="icon">、也没有字体外链」）。
- 为什么是问题：失效方向**静默且只是难看**（浏览器标签上没有图标；一个爬 robots.txt 的
  爬虫拿到一份 JSON 404）。受害者是**看演示的人**（标签上空一个格子）。
  ⚠️ 而 404 本身是**正确**的裁定（回一份 200 的 index.html 才是撒谎）。
- 最小处置：给 frontend/ 加一个 `public/favicon.ico`（或 index.html 里一行 `<link rel="icon">`）。
  ⚠️ 加了之后 static.py 那段「根级没有任何静态文件」的实测陈述与
  `cache_control_for` 的第 ③ 格（「其余今天一格都没有」）会**过期**，两处注释要同步；
  且 `check:dist` 的扫描面（25 产物）会变。⇒ 交付前**不建议**动，登记即可。
- 取证可复现性：同上（p03_fallback.py）。
```

```
【S4-③】/docs、/redoc、/openapi.json 在两档都公开（含 prod）
- 面：F4 + F9
- 现象：PE_ENV=prod 的进程内应用上 `GET /docs` → **200**、`GET /openapi.json` → **200**
  （417 032 B、74 路径 / 102 操作 / 3 个 securityScheme 全在里面）；产品档 8020 上同样 200（1191 B / 905 B 的 HTML）。
  ⚠️ 而 §13.11 与 static.py 的 RESERVED_PREFIXES 只管「它们不要被 fallback 接走」，
  **「要不要公开」今天没有任何一处裁定**（启动自检只查 CORS 与 Secure）。
- 为什么是问题：它泄漏的是**攻击面地图**，不是数据（84/102 个操作挂 security；15 个匿名 GET
  本席逐个实测过，没有一个含学生键）。⚠️ 而那份地图上还有**两格假线索**：
  `X-Student-Id` / `X-Teacher-Staff-No` 两个 securityScheme 在 prod 下是**死的**
  （allow_header_identity() 恒 False，本席实测伪造头 401）。
  受害者是**甲方的安全评审**（他们会问「为什么生产上 Swagger 是开的」）。
- 最小处置（**若**产品负责人裁定要收）：create_app 在 is_prod() 时传
  `docs_url=None, redoc_url=None, openapi_url=None`（FastAPI 的三个既有入参，零新增依赖、零迁移），
  并同步 RESERVED_PREFIXES 那四项的注释。⚠️ `gen:api` **不受影响**（它自 Task 11 起走进程内
  `create_app()` + `app.openapi()`，不打 HTTP —— 本席核过 dump_openapi.py 的取法）。
  ⚠️ 本席**不擅自改**：那会改掉 demo.ps1 / serve.ps1 都把 /docs 当卖点打印的那一格，是一次口径决定。
- 取证可复现性：$env:TEMP\p06t14\p05_auth2.py（§2 那一段，prod 档）+ p03_fallback.py（8020）。
```

```
【S4-④】迭代下界的代价：一份用 < 100 000 次迭代写的库会全体登不进来，唯一可见性是一行日志
- 面：F2
- 现象：实测 verify_password 对串里那一段迭代数的判定 ——
  1000 / 50000 / 99999 / 2000001 / 999999999 一律 **False**（正确口令也 False），
  100000 / 600000 / 2000000 → **True**；界外那一档**每次都打一行日志**
  「口令哈希的迭代次数 50000 越出 [100000, 2000000]，本次校验按「验身不符」处置…
  请查那一行 password_hash 是被什么写坏的（恢复脚本 / 人工 UPDATE / 损坏的备份）」。
  配置侧同样有牙：PBKDF2_ITERATIONS=1000 / 5000000 → iterations() **当场 ValueError**；
  未设 → 600000；演示库实测 `pbkdf2_sha256$100000$…` = **恰好等于下界**。
- 为什么是问题：失效方向是**安全**的（界外的串验不过，而不是被当成合法），响应上也**刻意不可分辨**
  （一律 401，不给枚举信号）—— 两档裁定都对。⚠️ 代价是**症状离真因隔一整层**：
  甲方现场若有一份用更低迭代数写的 password_hash（从别的系统迁来 / 人工 UPDATE / 一份用旧配置恢复的备份），
  表现是「**所有人都登录不了**」，而唯一的线索在**日志**里。
  ⚠️ 演示库那个值**贴在下界上**：将来谁把下界抬到 200 000，演示库当场全体登不进来
  （本席**没有找到**任何守卫钉住「演示库那个值 ≥ PBKDF2_MIN_VERIFY_ITERATIONS」——如实记）。
- 最小处置：**不改代码**（这一档的行为是对的）。交付说明里点明一句
  「日志里出现『迭代次数 N 越出 [100000, 2000000]』= 库里那一行哈希是界外迭代数写的，
  要重灌那一行（把 password_hash 置回 NULL 让它重绑）」；
  可选：给 tests/auth/test_passwords.py 加一条「demo_bootstrap 的 DEMO_PBKDF2_ITERATIONS
  ≥ PBKDF2_MIN_VERIFY_ITERATIONS」（把那个贴边钉住）。
- 取证可复现性：$env:TEMP\p06t14\p09_iters.py（8 个取值 × 正确/错误口令）。
```

```
【S4-⑤】restore.py 只印恢复后的 alembic_version，不判「备份的版本比当前代码旧」
- 面：F3
- 现象：把一份**链 3**（head = 7f3923d8af84、login_attempt.login = VARCHAR(32)）的备份恢复到
  一份**链 4** 的库上 → **退出码 0**，自检如实印出 `alembic_version = 7f3923d8af84`；
  之后再跑一次 init_db（= 起服务）→ 日志 `Running upgrade 7f3923d8af84 -> 0ac943e0da9b`、
  版本号回到 **0ac943e0da9b**、列宽回到 **VARCHAR(64)**、**标记数据一行都没丢**。
- 为什么是问题：**不是 Critical**（它自愈、且自检说的是真话）。残余是两格：
  ① 一个不知道 `7f3923d8af84` 是什么的运维**看不出**这一格（脚本不比对、不警告）；
  ② 从「恢复完」到「下一次起服务」之间，那个库**真的停在链 3** ——
  此时若跑一个**不经** init_db 的工具（例如直接 sqlite3 查、或一个旧的报表脚本），
  它看到的是 32 宽的列。失效方向**静默**。受害者是**甲方运维**。
- 最小处置：restore.py 的 ④ 自检多印一句人话（把恢复后的版本号与
  `ScriptDirectory.get_heads()` 比一次，不同就印「⚠️ 这一份备份的迁移版本比当前代码**旧**，
  起服务时 init_db 会自己 upgrade head 补齐；在补齐之前请不要用别的工具直接读这个库」）。
  **只加打印、不改 DDL、不改四步的顺序**（顺序是承重的，§13.10 逐字写了理由）。
  ⚠️ 会动到 tests/test_backup_restore.py 里三条钉「迁移链头修订号」的字面量（Task 11 已经同步过一次）。
- 取证可复现性：$env:TEMP\p06t14\p19_backup.py（OUT_backup.txt 七步逐条原文）。
```

### 8.4 收尾复验（派单逐条要求）

| 格 | 实测 |
|---|---|
| 8000 / 8020 / 5174 的占用数 | **0 / 0 / 0** |
| 5173（**不是本席起的**那个 vite） | **仍在监听，PID 20240**，一个字节都没碰 |
| `backend/pe.db` | **不存在**（`Test-Path` = False） |
| `backend/data/seed/` | **0 文件**（`-Recurse` 口径） |
| `git status --porcelain` | **空**（本席写这份报告之前；写完之后就只剩这一份报告） |
| `git diff --exit-code HEAD` | 退出码 **0**（28 次变异全部逐字节还原） |
| HEAD | `127d3bf`（与开工时相同；本席**没有** commit / push / 建分支） |
| 残留的 node 进程 | 4 个（PID 14368 / 15204 / 16404 / 20240），全部是本席开工**之前**就存在的 |
| `$env:TEMP\p06t14\`（本席全部探针与原始输出）与 CDP 的临时 profile 目录 | 写完本报告后**删净并复验**（复验结果写在交回控制者那一份回复里；⚠️ 本报告**刻意不把自己的字节数写进自己**——那是自指，Task 13 的报告 §⑨ 逐字交代过同一条纪律） |

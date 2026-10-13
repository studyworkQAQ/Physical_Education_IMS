# Plan 06 Task 3 + Task 4 实现者报告 —— 登录限流与锁定 / 生产档配置与启动自检 / 依赖清单守卫

> 分支 `p06/auth-prod`（自 `main` 的 `f4057a1` 起，**未 push、未碰 main**）。
> 派单：实施计划 06 的 §3（Task 3）+ §4（Task 4）+ 控制者新裁定的「依赖清单守卫」。
> 目标口径：**要交付给甲方的产品级系统**。
> **五个 commit**：`180aa90` / `72f772d` / `d5af9c5` / `9eac668` / `8f00b00`
> （+ 一条报告补记，逐条见 §7.6）。⚠️ 派单「建议 4 个 commit」，实际是 5 + 1：
> 第 ⑤ 条是写本报告时复核出来的一个**报错质量**问题（不是行为问题），
> 第 ⑥ 条只是把 ⑤ 补记进本报告。
> 结论速览：**顶回 0 处**、**没按派单做的 3 处**（逐条见 §7.3）、后端 **1370 → 1426（全绿）**、
> 表数 **26 → 27**、`smoke.mjs` **18 步 / 499 断言 / 退出码 0**（与基线逐字相同）、
> `app/domain/` 覆盖率四格 **1268/0/376/0/100%**（一格未退）。

---

## 1. 环境

开工第一件事（硬规矩 #73），逐字实测：

```
$ node --version; python --version; python -c "import alembic, fastapi; print(alembic.__version__, fastapi.__version__)"
v24.19.0
Python 3.11.1
1.20.0 0.141.1
```

| 格 | 实测 | 与派单给的基线 |
|---|---|---|
| Node / npm | v24.19.0 / 11.17.0 | ✅ 逐字相同 |
| Python | 3.11.1（**无 venv**，`C:\Python`） | ✅ |
| alembic / FastAPI | 1.20.0 / 0.141.1 | ✅ |
| SQLAlchemy / starlette | 2.1.3 / **1.7.0** | ✅（starlette 那一格是本 Task 新实测的：`_selfcheck_prod` 要读 `Middleware.cls` / `.kwargs`，故把版本记在这里） |
| 后端基线全量 | **1369 passed + 1 skipped**（= 1370 collected）、`--cov` 244.84 s | ✅ 逐字复跑过 |
| 端口 | 8000（`demo.ps1`）/ 5173（vite，沿用上一波的进程）；**另临时起 8012** 做「锁满自动解锁」的活体取证（见 §2.3） | — |

⚠️ **开工先重跑了 `backend\scripts\demo.ps1 -Port 8000`**（派单逐字要求：演示库被上一波
smoke 写脏）。整个 Task 期间一共重跑了 **3 次**（每次 smoke / 活体矩阵之前各一次），
每次第一步都删旧库、每次 ⑤ 那两道禁区守卫都通过（`backend\pe.db` 不存在、
`backend\data\seed\` 仍为 0 文件）。

⚠️ 探针一律放 `$env:TEMP`（`pe_eol_probe.py` / `pe_sync{1..4}.py` / `pe_rename.py` /
`pe_norm.py` / `pe_mutation_probe.py` / `pe_lockprobe.py` / `pe_live_matrix.py` /
`pe_dep_mutation.py` / `pe_metrics.py` / `pe_spec*.py` / `pe_commit{1,2,3}.py` 等 15 个），
写完 `py_compile`、跑完不入库。⚠️ 所有文件编辑都用 python 的 `read_bytes` →
**在 LF 口径下替换** → 折回 CRLF → `write_bytes`，并逐个复核「改前改后 BOM 与行尾」
（`backend/scripts/demo.ps1` 是 **UTF-8 + BOM**，实测改前改后都是 `bom=True`、
字节数 20167 → 20167，那一处只把注释里的 `# 26 张表` 改成 `# 27 张表`）。

---

## 2. 限流的实测矩阵（逐格）

### 2.1 规则（落地口径）

```
recent = 这个 (kind, login) 上 at >= now - max(window, lock) 的 ok=False 行
if len(recent) < max_fails: 不锁
else: 锁 iff now - max(recent.at) < lock
```

缺省 `max_fails=5` / `window=15min` / `lock=15min`，三格各有环境变量
（`PE_LOGIN_MAX_FAILS` / `PE_LOGIN_WINDOW_MIN` / `PE_LOGIN_LOCK_MIN`），
唯一所有者是 `backend/app/auth/policy.py::LoginThrottle`。

四档处置（**顺序是承重的**，锁定档排在最前）：

| 档 | 响应 | 写 `login_attempt` | 跑 PBKDF2 |
|---|---|---|---|
| 已锁 | **401 `invalid_credentials`**（与「口令错」逐字节相同） | **不写** | **不跑** |
| 口令验不过 | 401 `invalid_credentials` | 一行 `ok=false` | 跑 |
| 口令对了 | 200 + `Set-Cookie` | **删掉该标识全部行** + 一行 `ok=true` | 跑 |
| 不在册 / 未绑定 | 403 `password_not_bound` | **一行都不写** | 不跑 |

⚠️ **`max(window, lock)` 而不是裸 `window`** 是实现者补的一格（派单没写）：
`lock > window` 时若只回看 `window`，失败行会在**锁到期之前**滑出窗口，于是
「配了锁 60 分钟、实际生效 15 分钟」而**没有一处报错**。守卫是
`tests/auth/test_policy.py::test_a_lock_period_longer_than_the_window_is_not_silently_truncated`。
⚠️ 代价：`lock > window` 时计数窗口也跟着变宽（= 多锁不少锁，失效方向安全）；
**缺省档 `window == lock`，两者逐字等价**。

### 2.2 活体矩阵 A —— 真 uvicorn `127.0.0.1:8000`，**缺省阈值 5 / 15min / 15min**

演示库刚由 `demo.ps1` 重灌（60 学生 / 3 教师 / 口令 `pe-demo-2025`）。逐格亲跑：

| 身份 | 场景 | 状态码 | body 的 `error.code` | body 的 `error.message` |
|---|---|---|---|---|
| **匿名**（编造的学号 `ZZZ9999999`，不在册） | 第 1 次 | **403** | `password_not_bound` | 这个学号还没有绑定口令（或不在名册上）：请先走绑定流程（POST /api/auth/students/bind） |
| 同上 | 第 2 / 3 / 4 次 | **403** | `password_not_bound` | 逐字相同 |
| 同上 | **第 5 次** | **403** | `password_not_bound` | 逐字相同（⚠️ **不锁**：403 那一档一行都不写） |
| 同上 | **第 6 次** | **403** | `password_not_bound` | 逐字相同（6 次响应体**逐字节**相同，脚本里 `assert len(bodies) == 1`） |
| **教师 T0002** | 连错 1 / 2 / 3 / 4 次 | **401** | `invalid_credentials` | 口令不正确 |
| 同上 | 第 **5** 发换**正确**口令 | **200** | —（`{kind,id,name,role,student_no,staff_no}`）+ `Set-Cookie: pe_session=…` | ⚠️ **4 次失败没有把它锁住**（缺省阈值 5 的绿档对照） |
| **学生 2023120001** | 正常登录 | **200** | `{"kind":"student","id":4,"name":"赵锦程","role":"student","student_no":"2023120001","staff_no":null}` | — |
| **教师 T0001** | 正常登录 | **200** | `{"kind":"teacher","id":1,"name":"陈国华","role":"teacher",…,"staff_no":"T0001"}` | — |
| **管理员 T0003** | 正常登录 | **200** | `{"kind":"teacher","id":3,"name":"赵志刚","role":"admin",…,"staff_no":"T0003"}` | — |

### 2.3 活体矩阵 B —— 真 uvicorn `127.0.0.1:8012`，`PE_LOGIN_WINDOW_MIN=5` / `PE_LOGIN_LOCK_MIN=1`

⚠️ **为什么另起一个档**：「锁满自动解锁」在缺省的 15 分钟锁上要真的等 15 分钟。
把两个环境变量调小之后走的是**完全相同的代码路径**（同一个 `pe_demo.db`、同一份
`app/auth/policy.py`、同一份 `app/api/routers/auth.py`），只是阈值不同 ——
这与单测里注入 `now` 是同一件事的两种做法，两条都做了（§3.2）。

| 身份 | 场景 | 状态码 | body（原文） |
|---|---|---|---|
| **学生 2023120001** | 连错第 1 次 | **401** | `{"error":{"code":"invalid_credentials","message":"口令不正确","detail":null}}` |
| 同上 | 连错第 2 / 3 / 4 次 | **401** | 逐字节相同（**不锁**） |
| 同上 | 连错第 **5** 次 | **401** | 逐字节相同（这一发之后进入锁定） |
| 同上 | **锁内**第 6 / 7 / 8 发（错口令） | **401** | **逐字节相同**（脚本里 `assert raw == ordinary[1]`） |
| 同上 | **锁内 + 正确口令** | **401** | **逐字节相同**，且**没有** `Set-Cookie`（`assert not cookie`） |
| 同上 | **等 61 秒**（锁 1 分钟）后 + 正确口令 | **200** | `{"kind":"student","id":4,"name":"赵锦程",…}` + `Set-Cookie` → **锁满自动解锁，没有人工干预** |
| 同上 | 解锁后再连错 4 次，第 5 发换正确口令 | **200** | ⚠️ **成功登录清零**：计数器从 0 重新开始，不是从 5 继续 |

⚠️ **一次意外的活体取证**（如实记，硬规矩 #39）：第一次跑矩阵 A 时探针有个
unpack bug 崩在第 1 发上，而**那一发已经发出去了**；修好重跑又发了 4 发 →
`teacher/T0002` 累计 **5** 行 `ok=false` → 第 6 发拿**正确**口令回来的是
**401 `invalid_credentials`**（逐字与错口令那一档相同）。当时演示库里的行是：

```
(9,  'teacher', 'T0002', 0, '2026-10-13 17:44:48.774434', '127.0.0.1')
(10, 'teacher', 'T0002', 0, '2026-10-13 17:45:02.585513', '127.0.0.1')
(11, 'teacher', 'T0002', 0, '2026-10-13 17:45:02.614067', '127.0.0.1')
(12, 'teacher', 'T0002', 0, '2026-10-13 17:45:02.639753', '127.0.0.1')
(13, 'teacher', 'T0002', 0, '2026-10-13 17:45:02.665715', '127.0.0.1')
```

即：**跨两次进程、跨 14 秒累积到 5 次就锁**，而锁内那一次「口令其实是对的」
在响应上完全看不出来。重灌演示库后重跑，矩阵 A 的第 ③ 拍（4 次失败 + 正确口令
→ **200**）如预期通过。

### 2.4 演示库上的落库取证（同一次 run 之后直接读 `pe_demo.db`）

```
alembic_version            : [('0b7da3d20211',)]          ← head，不是基线
sqlite_master 表数          : 28  = 27 张业务表 + alembic_version
login_attempt DDL          : CREATE TABLE login_attempt (
                               id INTEGER NOT NULL, kind VARCHAR(16) NOT NULL,
                               login VARCHAR(32) NOT NULL, ok BOOLEAN NOT NULL,
                               at DATETIME NOT NULL, ip VARCHAR(64),
                               PRIMARY KEY (id),
                               CONSTRAINT ck_login_attempt_kind
                                 CHECK (kind IN ('student', 'teacher')))
ix_login_attempt_kind_login_at : CREATE INDEX … ON login_attempt (kind, login, at)
login_attempt 行（smoke 跑完）: 8 行，**全部 `ok=1`**（见下）
```

⚠️ 那 8 行是 `smoke.mjs` 留下的，**一行 `ok=0` 都没有** —— 这是派单 §1 第 7 格要的
「实测 smoke 对同一 `(kind,login)` 的失败次数上界」的**库级证据**：
`(teacher,T0001)` / `(teacher,T0003)` / `(student,2023120001)` / `(student,2024090001)` /
`(student,2025060001)` / `(student,2025050001)` / `(teacher,SMOKE16)` / `(teacher,SMOKE16C)`
各 1 行 `ok=1`，`ip` 全是 `127.0.0.1`（真 uvicorn 的 `request.client.host`）。

### 2.5 传导实测（派单 §1 第 7 格）—— 既有 1370 条测试的失败次数上界

用一个 pytest 插件（`$env:TEMP\pe_lockprobe.py`，`PYTHONPATH` 指过去、`-p pe_lockprobe`）
包住 `app.auth.policy.record_failure` 与 `is_locked`，**只观测不改行为**，跑一次全量：

```
record_failure 总次数: 107
上界（全部）                        = 8   ← 全部来自本波新增的测试
上界（**排除本波新增的测试**）        = 1   ← 既有 1370 条的真实上界
   那条是: tests/api/test_auth_api.py::test_the_second_of_two_concurrent_binds_is_409_not_a_silent_overwrite
   既有测试里失败次数 >= 3 的: （空）
is_locked 返回 True 的次数: 109 —— **撞上锁的 15 条全是本波新增的**，既有测试 0 条
阈值（本进程实测）: LoginThrottle(max_fails=5, window=900s, lock=900s)
```

结论：**既有 1370 条对同一 `(kind, login)` 的失败次数上界是 1**，缺省阈值 5 有
**5 倍余量**，故 ① 一条既有测试都没改 ② **没有给测试开任何后门环境变量**
（派单逐字禁止的那种）。⚠️ 而「全量绿」本身**证明不了**这件事 ——
锁内与口令错的响应逐字相同，故一条既有测试就算撞了锁也可能照样绿；
所以这一格必须靠插件实测，不能靠颜色。

`smoke.mjs` 那一侧：对同一 `(kind, login)` 最多制造 **1** 次被计数的失败
（第 16 步 ⑥），且被同一步的 ⑦（成功登录）当场清零 → **重复跑不会累积、不会自锁**
（§2.4 的 8 行全 `ok=1` 就是证据）。逐格取证写进了 `smoke.mjs` 的文件头，
并按派单要求写明它依赖 **`PE_LOGIN_MAX_FAILS >= 2`**（设成 1 的话第 16 步 ⑥
那一次失败就会锁住 `SMOKE16`，⑦ 拿正确口令也进不去 → 红在第 16 步 ⑦）。
⚠️ **没有改 smoke 用不同标识、也没有给它开后门环境变量**。

---

## 3. 「锁内 == 正常失败」的取证 + `now` 注入

### 3.1 逐字节取证（三层，各钉一层）

1. **HTTP 单测**（`tests/api/test_auth_api.py::test_a_locked_login_answers_byte_for_byte_like_an_ordinary_wrong_password`）：
   比 `response.content` 的**原始字节**（不是解析后的 `dict` —— 解析后比较会把
   「键序不同」与「多一格空白」两档漏掉，而一个探测者读的正是字节）+
   `content-type` + `error.code` == `"invalid_credentials"` + `error.message` == `"口令不正确"`
   + `error.detail is None` + 状态码 401（**不是** 423、**不是** 429）。
   ⚠️ **第 5 拍**：锁内拿**正确的口令**也是同一个 401（`rightful.content == ordinary.content`）。
2. **message 只有一个住址**：`app/api/routers/auth.py::_INVALID_CREDENTIALS_MESSAGE`
   是本 Task 从端点里的内联字面量**提上来的模块常量**。改前锁内那一档不存在，
   故那一格是内联的；改后同一句 message 有**两个来源**，写两遍的话下一个人
   「顺手给其中一处加一句『账号已被暂时锁定』」就会把枚举信号送回去，
   而**没有任何别的测试会红**（那一句在既有断言下是合法的 401）。
3. **活体**（§2.3 的 B 矩阵）：真 uvicorn 上 4 发锁内响应体与第 1 发**逐字节**相同，
   且锁内 + 正确口令**没有** `Set-Cookie`。

⚠️ **一个反过来证明改判有效的观察**：本文件的守卫要判「锁了没有」，
**都得绕过响应体**（`tests/api/test_auth_api.py::_is_locked_now` 直接问
`app.auth.policy.is_locked`，因为从 HTTP 层根本读不出来）。活体矩阵 B 同理。

⚠️ **残留的旁路信号（如实记）**：锁定档不跑 PBKDF2，故它比「真的验一次口令」快约
0.3 s，能测时序的调用方仍可判出「被锁了」。**它不构成新泄漏** ——
判「被锁了」要先判「这个标识绑过口令」，而后者由 `403 password_not_bound`
那一档**明文**给出（Plan 05A §3.3 的既有裁定，控制者显式接受）。
要抹平它得在锁定档也跑一次假哈希，而那恰好把本档要省的 CPU 又花回去了
（与本档存在的理由相反）。已写进 spec §1.2 第 15 条。

### 3.2 `now` 怎么注入的

与 `app.pipeline.daily.run_daily` 的先例**逐字同形**：keyword-only、缺省 `None`、
`None` 时取真时钟（`app/auth/policy.py::_clock` → `app.auth.sessions.now()`，
即**先转 `Asia/Shanghai` 再摘掉 tzinfo** 的 naive 本地时刻）。

```python
def is_locked(db, kind, login, *, now: dt.datetime | None = None) -> bool: ...
def record_failure(db, kind, login, *, ip=None, now: dt.datetime | None = None) -> None: ...
def record_success(db, kind, login, *, ip=None, now: dt.datetime | None = None) -> None: ...
```

于是「锁满自动解锁」那条守卫（`test_the_lock_lifts_itself_exactly_when_the_lock_period_has_elapsed`）
把整条时间线**四拍**跑完，**一次 `time.sleep` 都没有**：

| 拍 | 注入的 `now` | 期望 |
|---|---|---|
| ① | `T0`（第 5 次失败的那一刻） | **锁** |
| ② | `T0 + lock − 1s` | **锁** |
| ③ | `T0 + lock`（**恰好**锁满） | **已解锁**（边界是 `<`，与 `sessions.resolve` 的 `expires_at <= current` 同一条口径；写成 `<=` 本拍就红） |
| ④ | `T0 + lock + 3h` | **已解锁** |

另有 `test_the_lock_is_anchored_on_the_latest_failure_and_cannot_be_pushed_back`：
锁定期间**问 50 次**（每次 `now` 递进 1 秒），锚点一动不动、计数仍是 5，
到 `T0 + lock` 那一刻自己解开 —— 它钉的是「锁定档不写行 ⇒ 不是滑动锁」。

⚠️ 生产路径上**一个调用方都不传 `now`**（`app/api/routers/auth.py` 的三处调用
都不传），故 `git grep "now=" -- backend/app` 只命中 `app/pipeline/daily.py`
与本模块自己。

### 3.3 定点变异（派单 §1 第 6 格逐字要求的两格 + 五条自加的）

`$env:TEMP\pe_mutation_probe.py` 亲跑：备份 → 打变异 → 跑
`tests/auth/test_policy.py tests/api/test_auth_api.py` → 还原 → 复核 sha256[:16]。
改前对照 **53 passed / rc=0**；还原后复跑 **53 passed / rc=0**；
两份文件 sha 改前改后逐字相同（`policy.py B8D8E6CB9BCE144A`、`auth.py 447E39FE0157C57E`）。

| # | 变异 | 结果 | 红的条数与代表 |
|---|---|---|---|
| A | **去掉计数**（删 `if failure_count(...) < max_fails: return False`） | **RED** | 10 红：`test_the_count_really_gates_the_lock`（派单点名的那一格）、`test_a_successful_login_clears_the_failure_count`、HTTP 侧 5 条，**外加一条既有测试** `test_login_distinguishes_not_bound_from_a_wrong_password`（它「1 次错 + 1 次对」，恒锁实现会让绿档那一发变 401） |
| B | **去掉窗口**（`_lookback` 恒回 10 年） | **RED** | 2 红：`test_the_window_really_gates_the_count`（派单点名的那一格）、`test_the_recorded_timestamp_is_naive_local_time_and_round_trips` |
| C | 成功登录**不清零**（删 `clear_failures` 那一句） | **RED** | 6 红：`test_a_successful_login_clears_the_failure_count`（+ HTTP 那条）、`test_clearing_one_identity_leaves_the_other_one_alone`、`test_the_kind_is_part_of_the_key`、`test_the_attempt_rows_carry_…` |
| D | **403 那一档也计数**（端点里补一次 `record_failure`） | **RED** | 1 红：`test_the_not_bound_tier_records_nothing_so_it_cannot_lock_anyone_out` |
| E | **锁内回 423**（= 计划 §3 的原文，控制者改判要防的正是它） | **RED** | 5 红：`test_a_locked_login_answers_byte_for_byte_like_an_ordinary_wrong_password`、`test_the_lock_is_per_identity_not_per_process`、`test_the_locked_tier_never_hashes_a_password`、`test_the_locked_tier_writes_no_row_so_the_lock_cannot_slide`、`test_the_threshold_is_configuration_not_code_over_http` |
| F | **整个锁定档删掉** | **RED** | 5 红（同上那五条） |
| G | **锁内也写一行**（滑动锁 + 表被打满） | **RED** | 1 红：`test_the_locked_tier_writes_no_row_so_the_lock_cannot_slide` |

**7 / 7 全红。**

---

## 4. 迁移

| 格 | 实测 |
|---|---|
| 新迁移文件 | `backend/migrations/versions/0b7da3d20211_login_attempt.py` |
| 修订号 / `down_revision` | `0b7da3d20211` / `53e5a548c40e`（= 基线，**链没有分叉**） |
| 文件 sha256[:16] / 字节 / 行尾 | **`279484F4D5BA1B37`** / 5238 B / **CRLF 90/90、UTF-8 无 BOM**（与基线同款，实测过基线是 CRLF 566/566） |
| 基线迁移 | **一个字都没动**：`53e5a548c40e_baseline.py` 33373 B / sha256[:16] `4D4757D45D0E1EA5` / CRLF 566/566 |
| 链的形状 | `ScriptDirectory.get_base()` = `53e5a548c40e`、`get_heads()` = `['0b7da3d20211']`、`walk_revisions()` = **2** |

### 4.1 autogenerate 的 diff **只含新表**（逐字取证）

对一个先 `alembic upgrade head`（= 升到基线）的临时库跑
`python -m alembic revision --autogenerate -m "login_attempt"`：

```
INFO  [alembic.autogenerate.compare.tables]       Detected added table 'login_attempt'
INFO  [alembic.autogenerate.compare.constraints]  Detected added index
      'ix_login_attempt_kind_login_at' on '('kind', 'login', 'at')'
```

**两行、没有第三行** —— 即其余 26 张表与基线建出来的库**逐格一致**，
本 Task 只加了一张表。生成出来的 `upgrade()` 只有 `op.create_table('login_attempt', …)`
（6 列 + 1 条 CHECK + 主键）与一个 `op.batch_alter_table(...) → batch_op.create_index(...)`
（`render_as_batch=True` 的后果，与基线里那 9 个 `ix_*_batch_id` 同形）。
⚠️ **本表没有 `JsonText` 列**，故**不需要**基线迁移里那句承重的
`import app.db.models._shared`（alembic 会把自定义 `TypeDecorator` 渲染成限定名却不生成
import）。人审只做了「写 docstring」一件事，**DDL 一个字都没改**。

### 4.2 纪律守卫仍绿

`tests/db/test_migration_chain.py` **5 条全绿**，其中：

* `test_the_migration_chain_is_in_sync_with_the_models` —— 在 **head**（现在是
  `0b7da3d20211`）上跑 `alembic.command.check`，**无 diff**。⚠️ 这就是派单点名的那条
  「加了 `login_attempt` 表必须配一条新迁移，否则守卫红」的守卫，它现在绿。
* 两条定点变异（删 `semester.is_current` / 删 `ix_alert_batch_id`）仍然各自红 →
  守卫**有牙**、不是恒绿。
* `test_the_migration_scripts_carry_no_data` 扫的是 `versions/*.py` 全部脚本
  （现在 2 个），新迁移不含 `op.bulk_insert` / `op.execute`、非 docstring 的字符串常量
  没有一个以 `INSERT`/`UPDATE`/`DELETE` 开头 → 绿。
* `test_alembic_ini_is_pure_ascii_and_carries_no_connection_string` → 绿
  （`alembic.ini` **一个字都没动**，仍是 4250 B / 纯 ASCII / 无 BOM / `sqlalchemy.url` 为空）。
* `test_the_migration_scripts_are_utf8_without_bom_and_parse` → 绿（新迁移无 BOM、可 parse、无相对导入）。

`tests/db/test_migration_baseline.py` **18 条全绿**，其中三格是**本 Task 改了期望侧**的：

* 新增 `HEAD_REVISION = "0b7da3d20211"` 字面量（此前只有一个修订号常量，因为链只有一条时
  head == baseline）。⚠️ `BASELINE_REVISION` **一个字都没动** ——
  `init_db` 档 2 往甲方旧库里 stamp 的仍然是基线号。
* `test_the_chain_has_exactly_one_head_today` 的 docstring 此前**逐字预告**了
  「本条会在下一条迁移落地时红，那是**要的**」；本 Task 兑现了它（`heads` 期望值换成
  `[HEAD_REVISION]`、修订数 1 → 2），并**加了一拍**：`get_base()` 仍是
  `BASELINE_REVISION` 且 `BASELINE_REVISION != HEAD_REVISION`（少了这一拍，
  「把两条迁移压成一条新基线」会让上面两格同时成立）。
* ⚠️ **`test_init_db_stamps_a_legacy_database_and_keeps_its_rows` 是真红了、且红得有价值**：
  它改前用 `Base.metadata.create_all(eng)` 造「甲方手里的旧库」，而在链长了第二条之后
  那一行造出来的是 **head** 的结构（27 张表），档 2 比对的是**基线**（26 张表），
  于是 `_assert_shape_matches_revision` 抛 `RuntimeError: …多表 ['login_attempt']`。
  这不是「测试写得不够灵活」，是它抓到了一个**真的语义漂移**：在只有一条迁移的链上
  「基线结构」与「`create_all` 结构」恰好相等，从第二条起两格分开，而甲方手里的旧库
  永远是**基线**那一格。新写法是「`upgrade` 到 `BASELINE_REVISION` → `DROP TABLE
  alembic_version` → 灌一行业务数据」，并且**多验了一格**：stamp 之后紧跟的
  `upgrade head` 真的把第二条迁移跑在了那份带数据的旧库上（`login_attempt` 建出来、
  `semester` 那一行还在）。改名一处：
  `test_the_migrated_database_carries_the_version_table_at_the_baseline` → `…_at_the_head`。

七个规模字面量（改前 → 改后，全部实测复核）：

| 字面量 | 改前 | 改后 | 增量来历 |
|---|---|---|---|
| `EXPECTED_TABLES` | 26 个名字 | **27** | + `login_attempt` |
| `EXPECTED_TABLE_COUNT_WITH_VERSION` | 27 | **28** | 同上 |
| `EXPECTED_COLUMN_COUNT` | 255 | **261** | + 6（id / kind / login / ok / at / ip） |
| `EXPECTED_INDEX_COUNT` | 9 | **10** | + `ix_login_attempt_kind_login_at`（**全库第一个复合索引**） |
| `EXPECTED_UNIQUE_COUNT` | 21 | **21** | 不变 |
| `EXPECTED_FOREIGN_KEY_COUNT` | 41 | **41** | 不变（本表一个外键都没有） |
| `EXPECTED_CHECK_CONSTRAINT_COUNT` | 29 | **30** | + `ck_login_attempt_kind` |

### 4.3 表数 26 → 27 的同步清单（`test_all_twenty_seven_tables_created` 那段的 ①–⑧）

①–⑦ 是既有清单，**⑧ 是本 Task 实测出来的新一格**（`test_migration_baseline.py`
的七个规模字面量；它只在有了迁移链之后才存在，而它是清单里唯一「不改就红在
**另一个文件**」的一格）：

| 格 | 落点 | 状态 |
|---|---|---|
| ① 函数名里的英文数词 | `test_all_twenty_six_tables_created` → **`test_all_twenty_seven_tables_created`**；全仓 **11 处 / 7 文件**，亲跑复核**处数与构成都没变** | ✅ |
| ② 本文件三处 `==` | `git grep -n "== 27" -- backend/tests/db/test_models.py` 现命中 **7** 处 = 3 真断言 + 4 散文，与改前 `"== 26"` 的 7 处**构成相同** | ✅ |
| ③ `models/prescription.py` 的归属表 | 「全库 **27** 张表 = … + **Plan 06 Task 3 的 1 张**（`login_attempt`）」 | ✅ |
| ④ `tests/seed/test_generate.py` 的分区 | `AUTH_TABLES` 1 → **2** 张（`login_attempt` 与 `user_session` 同属「运行时由 HTTP 请求写、seed 阶段 0 行」）；⚠️ **顺手清掉了 Plan 05A 留下的一份逐字重复**（那整段注释 + 赋值 + 断言在文件里**连着出现了两遍**，两份字面量恰好相同故没有任何测试会红，只是让「`AUTH_TABLES` 是谁」有了两个所有者；本次抬到两张表必须改两处，故合并成一处） | ✅ |
| ④' `tests/test_main.py` 的表数 | 三处 26 → 27 | ✅ |
| ⑤ `json_text_columns == 21` / `_BATCH_OWNED_TABLES` | **两个都不变**（本表 6 列全是标量、不是管道产物） | ✅ |
| ⑥ 外键总数 41 / `_in_domain` 列数 | 41 **不变**；`_in_domain` 列数 27 → **28**（+ `login_attempt.kind`） | ✅ |
| ⑦ `tests/api/test_crud.py` 两处 | `len(Base.metadata.tables) == 27` ×2；⚠️ 「整数主键的例外」仍**只有 `user_session` 一个**（`login_attempt.id` 是 `Integer`） | ✅ |
| ⑧ `test_migration_baseline.py` 七个规模字面量 | 见 §4.2 的表 | ✅ |

连带更新的散文计数（`26 张表` → `27 张表`、以及函数改名），涉及 **16 个文件**：
`app/main.py`、`app/db/session.py`、`app/db/models/__init__.py`、`app/api/crud.py`、
`app/api/routers/catalog.py`、`app/pipeline/report_stage.py`、`migrations/env.py`、
`tests/api/conftest.py`、`tests/api/test_crud.py`、`tests/test_notify.py`、
`tests/test_demo_data.py`、`tests/db/test_migration_chain.py`、`tests/auth/test_sessions.py`、
`backend/scripts/demo.ps1`（⚠️ **UTF-8+BOM 保住了**，实测改前改后都是 `bom=True`、
20167 B → 20167 B）、`frontend/scripts/smoke.mjs`、`tests/db/test_models.py`。
⚠️ 逐处命中数不复述（硬规矩 #111：能从 `git diff f4057a1 HEAD` 读出来的数一律视为过期）；
可复核的命令是 `git grep -n "27 张表" -- backend frontend`。
⚠️ **刻意留作 26 的五处**（它们说的是**基线**、不是当前总数，改了就是假话）：
基线迁移自己的 docstring、`0b7da3d20211` docstring 里「其余 26 张表与基线一致」那一句、
`test_migration_baseline.py` 模块 docstring 的「那条基线迁移是 566 行、26 张表」、
`app/db/session.py::_assert_shape_matches_revision` 的「一次 26 张表的 CREATE TABLE」
（它 upgrade 到的正是**基线**）、以及 `test_models.py` / `prescription.py` 里
「改前是 `"== 26"` 的 7 处」那两句历史陈述。
⚠️ 架构守卫的扫描面 **66 → 67**（`app/auth/` 3 → 4 个文件），两个下界
（`>= 21` / `>= 20`）**刻意不抬**，理由逐字写进了 `test_layering.py`。

---

## 5. 生产档三格 + 自检 raise 的取证；dev 下 1370 是否全绿

### 5.1 新模块 `app/deploy.py`（**只 import `os`**，有一条 AST 级守卫钉住这件事）

⚠️ **为什么必须是一个新模块**（派单没点名这一格，实现者的决定）：档位现在决定**三**件事，
三个消费者住在三个不同的层，而其中两个**不许** import 第三个
（`app.api` 与 `app.auth` 都不得 import `app.main` —— `API_ALLOWED_PREFIXES` 逐字把
`app.main` 列成 RED，理由是导入环）。三份各写一遍「哪些串算生产」的话，
下一个人加一个拼法只会加到其中一份，而漏掉的那一份是**静默**的。
⚠️ 它**只 import `os`**：`app.auth` 的包 docstring 承诺「本包可以在没有 `fastapi` 的
进程里被 import」，而 `cookie_secure()` 要读档位，故 `deploy` 被 `app.auth` 间接导入 ——
它一旦 import starlette，那句承诺当场变假、且失效是静默的。
⚠️ 于是「启动自检」**不住在 deploy 里**（它要看一个已装配好的 FastAPI 应用），
住在 `app/main.py::_selfcheck_prod`。分工是「判据在这里、装配与自检在那里」。
⚠️ 连带：`API_ALLOWED_PREFIXES` 加了**第十二项** `app.deploy`（+ 判定矩阵两格
GREEN/RED）；`deps.py` 那一句刻意写成 `from app.deploy import is_prod` 而**不是**
`from app import deploy` —— 后者在 AST 上是 `ImportFrom(module="app")`，折出来是裸串
`"app"`，而 `"app"` 在那份矩阵里是 RED（一个已登记的假阳性）。

### 5.2 三格 + 自检，逐格取证

| 格 | 实现 | 守卫（全部实跑绿） |
|---|---|---|
| **① CORS** | `app/main.py::_install_cors`：`dev` → `allow_origins=["*"]`（一个字没改）；`prod` → 读 `PE_CORS_ORIGINS`（逗号分隔），**空 = 一个 `CORSMiddleware` 都不挂**；非空 = 那张白名单 + `allow_credentials=True` | `test_prod_without_a_whitelist_mounts_no_cors_middleware_at_all`（数 `user_middleware` == `[]` **并实发一次带 `Origin` 的跨源请求**，断言 200 而 `access-control-allow-origin` **不出现**）；`test_prod_with_a_whitelist_echoes_only_the_listed_origins`（清单内的源逐字回显 + `allow-credentials: true`；**清单外的源一个 CORS 头都不给** = 红绿两档同时在场）；`test_the_dev_tier_still_mounts_the_wildcard_cors_and_no_secure_cookie`（dev 那一档**逐字未变**，含实发请求拿到 `access-control-allow-origin: *`） |
| **② cookie `Secure` 仅 prod 开** | `cookie_secure()` 现在就是 `deploy.is_prod()`。⚠️ **核实结果：05A 那一格不是派单以为的样子** —— 改前逐字是 `os.environ.get("PE_ENV","").strip().lower() == "production"`，即它认的字面量是 **`production`**、不是派单给的 **`prod`**。处置是**都收**（`prod` 是正字、`production` 作为 05A 的旧拼法继续接受）：删掉旧拼法会让所有按 05A 那份 spec §13 部署的机器**静默**落到开发档。`sessions.ENV_VAR` / `sessions.PRODUCTION` 从此是 `deploy` 那两个常量的**别名**（`is` 判，不是第二份字面量；有一条守卫专门钉这个 `is`） | `test_the_production_tier_holds_all_three_documented_properties_at_once` 第 ② 拍；`tests/auth/test_sessions.py::test_secure_is_on_only_in_production`（`production` / `Production` / `"  PRODUCTION  "` / `prod` / `PROD` / `" prod "` 六个都算生产；`""` / `dev` / `DEV` 不算） |
| **③ `PE_ALLOW_HEADER_IDENTITY` 在 prod 下强制 0** | `allow_header_identity()` 第一句就是 `if is_prod(): return False`；warning 日志由 `create_app` 在装配时打**一条**（逐请求打会把日志淹掉，而「这个开关在生产上被设成了 1」是一个**部署事实**、不是一个请求事实） | `tests/api/test_auth_api.py::test_the_header_identity_channel_is_forced_off_in_the_production_tier`（两个环境变量**同时**设上 → 判定 `False` + **实发**学生侧与教师侧各一次伪造请求头 → **401 `unauthenticated`**；**对照拍**：切回 `dev`、开关一个字不动 → 同一个请求是 **403** 而不是 401，故「把 `allow_header_identity` 改成恒 `False`」这一档会红）；`test_prod_logs_exactly_one_warning_when_the_header_identity_switch_is_set`（建**两个**应用 → `caplog` 里**恰好两条**、都是 `WARNING`、都含「忽略」）；`test_dev_logs_no_warning_about_the_header_identity_switch`（dev 下设成 1 **不打** warning，且判定是 `True` —— 少了本条「无条件打」是绿的，而 `tests/conftest.py` 恰恰把它设成 `"1"`） |
| **④ 启动自检** | `app/main.py::_selfcheck_prod`，`create_app` 的**最后一件事**（故它数的是这个应用**最终的样子**）。两格：任何一个 `CORSMiddleware` 的 `allow_origins` 含 `"*"` → offender；`cookie_secure()` 为假 → offender。**一次报全**（`RuntimeError` 里两格都列出来） | 三条**定点变异**（下表）+ 两条对照拍 |

### 5.3 自检的三条定点变异（证明它不是恒绿的装饰）

| 变异 | 结果 | 守卫 |
|---|---|---|
| `PE_CORS_ORIGINS=*`（**运维真的会犯的错**） | `create_app` **`RuntimeError`** | `test_prod_with_a_wildcard_cors_whitelist_refuses_to_start`（报错点名 `PE_CORS_ORIGINS` 与 `PE_ENV`、含那个 `*`、并明写「**不设它**是合法的那一档」；另有一拍：星号**混在清单里**（`https://pe.xmu.edu.cn,*`）同样响）。⚠️ 解析侧**刻意不悄悄吃掉那个星号**（`tests/test_deploy.py::test_a_wildcard_in_the_whitelist_is_parsed_verbatim_and_never_dropped`）：吃掉的话自检就永远看不到它，而运维写下的 `*` 会变成一个**静默的**「什么都没允许」 |
| `monkeypatch` 把 `app.main.cookie_secure` 改假 | `create_app` **`RuntimeError`** | `test_the_selfcheck_raises_when_the_secure_cookie_is_off_in_prod`。⚠️ 这一格在**构造上**不可能为假（`cookie_secure()` 就是 `is_prod()`），故它必须靠变异来证明有牙；它挡的是「有人把 `cookie_secure` 改成读别的变量」 |
| 绕过 `_install_cors`、装配完再 `add_middleware(CORSMiddleware, allow_origins=["*"])` | `create_app` **`RuntimeError`** | `test_the_selfcheck_catches_a_wildcard_cors_mounted_behind_its_back`。⚠️ 这一条钉的是自检的**判据来源**：它读 `application.user_middleware`（实测 starlette 1.7.0 的 `Middleware` 带 `.cls` / `.kwargs`），不是「我打算挂什么」。一个只看意图的自检在这一档下会**绿着放行**一个全开的 CORS |
| 两格**同时**坏 | 一次 `raise` 里**两格都报** | `test_the_selfcheck_reports_every_offender_at_once`（`message.count("\n  - ") == 2`） |
| 坏的 `PE_ENV`（`productionn`） | `create_app` **`ValueError`** | `test_an_unrecognised_tier_refuses_to_build_an_app` + `tests/test_deploy.py::test_an_unrecognised_tier_is_loud_and_never_silently_dev`（6 个值逐个：`productionn` / `prodd` / `development` / `staging` / `1` / `true`；报错点名变量 + 带上收到的原文 + **明写「刻意不回落到 dev」**） |
| **对照**：dev 下 | `_selfcheck_prod` 是 **no-op**（连 `user_middleware` 都不数） | `test_the_selfcheck_is_a_no_op_in_the_dev_tier`。⚠️ 少了它，「自检不分档」会让**每一条**建应用的测试当场 raise |

⚠️ **「起不来」这个失效方向的落点**：`app.main` 有一条模块级的 `app = create_app()`，
故 `PE_ENV=prod` + 一份不合法的配置会让 **`import app.main` 就抛**，
`uvicorn app.main:app` **根本起不来**（与 `demo.ps1` 那两道禁区守卫、
`app/db/session.py::_stamp_unversioned` 的「先比对后 stamp」同一个姿势）。

### 5.4 ⚠️ `/api/health` 与 `/openapi.json` **不泄漏 `PE_ENV`**（派单 §2 第 5 格）

派单说「若你想加一格『当前档位』，先顶回来问」—— **实现者没加**，且把它做成了守卫：

`tests/test_main.py::test_health_and_openapi_never_leak_the_deployment_tier_to_an_anonymous_caller`
的判据是「**两档下逐字节相同**」：`dev`（不设 `PE_CORS_ORIGINS`）与
`prod`（`PE_CORS_ORIGINS=https://pe.xmu.edu.cn`）各建一个应用、各发一次
`GET /api/health` 与 `GET /openapi.json`，断言
`dev_health == prod_health` 且 `dev_openapi == prod_openapi`（比 `.content` 的原始字节），
外加 `/api/health` 的键集合**恰好**是 `{status, tables, students}`（字面量）、
且那个**实例相关**的白名单域名不出现在任何一份响应体里。

⚠️ **判据刻意不是「响应体里搜不到某个词」**（实现者复核后改掉了第一版）：
FastAPI 会把**端点的 docstring** 渲染成 OpenAPI 的 operation `description`，
而 `login` 的 docstring 里逐字写着 `PE_ENV=production` / `PE_LOGIN_MAX_FAILS`
一类**机制名** —— 那是产品文档、不是本实例的档位；搜词会把它们误判成泄漏，
而下一个人「修」它的办法是删注释（硬规矩 #109 的形状）。
**逐字节相同则一举封死**：响应体在两档下一模一样，就**按定义**不可能携带任何关于
「本实例跑在哪一档」的信息。⚠️ 连带把 `create_app` 的 `description=` 也改写成
**与档位无关**的一段（改前它逐字写着「CORS 仍允许全部来源，上线前要收紧成显式白名单」，
那句话在 prod 下已经是假的）。

### 5.5 dev 下 1370 条一条都不许红

**dev 下全量 1425 passed + 1 skipped（= 1426 collected）**，其中基线那 1370 条
**一条都没改**（唯一改过的一条既有测试是
`tests/auth/test_sessions.py::test_secure_is_on_only_in_production`，见 §7.3 第 ② 处）。
`tests/conftest.py` **一个字都没动**（它只设 `PE_ALLOW_HEADER_IDENTITY=1` 与
`PBKDF2_ITERATIONS=1000`，**不设 `PE_ENV`** → 全部测试跑在 dev 档）。

---

## 6. 依赖清单守卫（控制者的新裁定）

### 6.1 先 Grep：前端那条守卫**今天不存在**

派单说「前端那条守卫今天可能已存在 —— 先 `Grep`，若已存在就不要造第二个所有者」。
**实测不存在**，故本 Task 新建了**唯一**的所有者（不是「扩既有的一条」）：

```
$ Grep -n "package\.json|pyproject" --glob *.py            → 6 处命中，全在 .superpowers/ 的历史报告、
                                                             app/auth/passwords.py 的一句散文、
                                                             tests/api/conftest.py 的一句散文
$ Grep -n "devDependencies|dependencies" --glob *.py        → 41 处命中，全是 FastAPI 的
                                                             dependencies=[Security(...)]，与依赖表无关
$ ls frontend/scripts                                        → check-dist.mjs / check-tokens.mjs /
                                                             shots.mjs / smoke.mjs —— 没有一个是依赖守卫
```

`frontend/package.json` 的 `"//"` 注释里那句「本前端**零新增依赖**（Plan 01 至本波全程）」
此前**只是散文**。控制者以为有的那条 sha256 指纹测试钉的确实是 `backend/data/**`
（`tests/test_refdata.py::STANDARD_FINGERPRINT = "D2C8E539E2FA0029"` 等），与依赖表无关
—— 实现者复核后**确认控制者的判断成立**。

### 6.2 新守卫 `backend/tests/test_dependencies.py`（**6** 条，只 import `json` + `tomllib`）

⚠️ `tomllib` 是 **Python 3.11 的标准库**（`requires-python = ">=3.11"`），
故**为了读 TOML 而没有加任何依赖** —— 那恰好是本文件要防的事。
⚠️ 判据是**显式清单**、不是 sha256（控制者逐字要求）：报错里**实测与期望两侧都打出来**，
另给「多了 / 少了」两个差集。

**后端期望清单**（`sorted` 后逐字相等）：

| 表 | 项数 | 内容 |
|---|---|---|
| `[project] dependencies` | **7** | `alembic==1.20.0` / `fastapi` / `numpy` / `pandas` / `pyyaml` / `sqlalchemy>=2.0` / `uvicorn[standard]` |
| `[project.optional-dependencies]` 的**组名** | **1** | `dev`（⚠️ 组名也被钉住：少了这一格，「新加一个 `[project.optional-dependencies] test`」是一次**静默**的动作） |
| `…optional-dependencies.dev` | **3** | `httpx` / `pytest` / `pytest-cov` |
| `[build-system] requires` | **1** | `setuptools>=68`（⚠️ 它**也是**一张依赖表：一个「顺手加个 `setuptools-scm`」与「顺手加个 `requests`」在「甲方机器上多装了一个包」这件事上没有区别） |

**前端期望清单**（钉的是 **`"名: 区间"`** 整个串，因为「把 `^` 改成 `*`」与「加一个新包」
在「甲方的构建产物会变」这件事上是同一类动作）：

| 表 | 项数 | 内容 |
|---|---|---|
| `dependencies` | **3** | `pinia: ^3.0.4` / `vue: ^3.5.43` / `vue-router: ^4.6.4` |
| `devDependencies` | **7** | `@types/node: ^24.13.3` / `@vitejs/plugin-vue: ^6.0.10` / `@vue/tsconfig: ^0.9.1` / `openapi-typescript: ^7.13.0` / `typescript: ~5.9.3` / `vite: ^8.3.4` / `vue-tsc: ^3.3.13` |
| **依赖形状的键** | **2** | `dependencies` / `devDependencies`。判据是「键名以 `ependencies` 或 `ependenciesMeta` 结尾的**恰好**是这两个」，**不是**一份硬编码黑名单：npm 认的形状键至少五个（+ `peer` / `optional` / `bundled`），逐个列出来的话下一个新形状会静默溜过去 |

### 6.3 定点变异：**9 / 9 全红**（`$env:TEMP\pe_dep_mutation.py` 亲跑）

改前对照 **6 passed / rc=0**；每条变异跑完逐字节还原，两份文件 sha256[:16] 改前改后相同
（`pyproject.toml B43FF464679BAEB3`、`package.json B30888C39510DB57`）；还原后复跑 **6 passed**。

| # | 变异 | 结果 | 红在哪条 |
|---|---|---|---|
| 1 | 后端 runtime 加一个 `requests` | **RED** | `…runtime_dependencies_are_exactly_the_approved_seven` |
| 2 | 后端 `dev` 组加一个 `black` | **RED** | `…optional_dependency_groups_are_exactly_dev` |
| 3 | 后端新开一个 `[project.optional-dependencies.test]` 组 | **RED** | 同上 |
| 4 | 后端 `[build-system] requires` 加 `setuptools-scm` | **RED** | `…build_requires_are_unchanged` |
| 5 | 前端 `dependencies` 加 `axios` | **RED** | `…frontend_dependency_maps_are_exactly_the_documented_ones` |
| 6 | 前端 `devDependencies` 加 `playwright`（⚠️ 派单当年允许过、最终没引的那一个） | **RED** | 同上 |
| 7 | 前端新开一张 `peerDependencies` | **RED** | `…has_no_other_dependency_shaped_key` |
| 8 | 把 `alembic==1.20.0` 放宽成 `alembic>=1.20.0` | **RED** | `…runtime_dependencies…`（⚠️ 那一格精确钉死的理由逐字在 `pyproject.toml` 里：autogenerate 会把它自己对 DDL 的渲染写进**入库的**迁移脚本） |
| 9 | 把 `vue: ^3.5.43` 改成 `vue: *` | **RED** | `…frontend_dependency_maps…` |

### 6.4 报错样例（变异 1 的原文，控制者要的「看得出多了什么」）

```
E  AssertionError: backend/pyproject.toml [project] dependencies 与守卫里写死的清单不一致。
E      实测（8 项，已排序）: ['alembic==1.20.0', 'fastapi', 'numpy', 'pandas', 'pyyaml',
                             'requests', 'sqlalchemy>=2.0', 'uvicorn[standard]']
E      期望（7 项，已排序）: ['alembic==1.20.0', 'fastapi', 'numpy', 'pandas', 'pyyaml',
                             'sqlalchemy>=2.0', 'uvicorn[standard]']
E      多了: ['requests']
E      少了: []
E      ⚠️ 加一个依赖必须是一次**刻意的动作**：改本文件里那一份清单（它是依赖表的单一
E      所有者），并在 commit 信息里说明谁批准了它。后端今天被批准的新增依赖只有
E      alembic 一个（用户 2026-10-13 裁定），前端新增依赖是 0。
```

⚠️ **它守不住什么**（硬规矩 #39，逐字写进了那个文件的模块 docstring）：
① 它守的是两份**清单文件**，不是 `pip list` / `node_modules`，故「装了但没写进清单」
抓不到（那一档由全量测试兜住：本机没装就跑不过）；② 它**不守传递依赖**
（`alembic` 自己带 Mako 1.4.3、`fastapi` 带 starlette/pydantic；重复钉就是第二个所有者）；
③ 它**不守 `frontend/package-lock.json`**（那一份由 npm 自己写、体量巨大、内容还随
registry 状态变；钉它会让「一次 `npm install` 换了个镜像」变成一次守卫失败）——
于是「同一个 `package.json` 在不同时间 install 出不同的树」这一档今天没有守卫。

---

## 7. 待清扫 / 关切 / 没按派单做的 / **顶回** + 最终验收

### 7.1 顶回：**0 处**

派单 §5 要求「若顶回 0 处，显式写并说明核过哪些决定」。**本波顶回 0 处**，
逐条核过的决定如下（每一条都复核后**同意**，故没有顶回）：

| # | 派单/控制者的决定 | 实现者复核结论 |
|---|---|---|
| ① | **控制者对计划 §3 的改判**：锁内回 401 而不是 423/429 | **同意**。派单 §5 点名这一条最可能被顶回（「你若认为产品上必须给被锁用户提示，给出既不给枚举信号又能提示的方案」）。实现者认真找过那种方案，**三个都不成立**：(a) 在 `message` 里加一句「账号已被暂时锁定」→ 那就是 423 的等价物，枚举信号一模一样（423 的信息量全在那一句上，不在状态码上）；(b) 加一个响应头（`X-PE-Locked: 1`）→ 同一个信号换了个载体，且它会被反代/APM 各存一份；(c) 只对「已经登录过一次的浏览器」提示（按 cookie 分档）→ 被锁的人**恰恰是登不进去的那个人**，他手里没有有效 cookie，故那一档对他恒不可达。⚠️ 而「不给提示」的代价是**有界**的：锁最多 15 分钟、锁内的重试**不写行**（故不会把锁推后）、且用户看到的仍然是那句**正确的下一步动作**（「口令不正确」→ 重输；他重输到锁满之后就进去了）。⚠️ 于是产品上真正缺的是**运维侧的可见性**（「谁被锁过」），而那**恰好是 Task 5 的 `audit_log`**，派单自己也这么裁定了（「锁的可见性留给 Task 5」）。故不顶回。 |
| ② | `login_attempt` 存 `login` **原文** | **同意**（派单允许顶回，实现者不顶）。它是**限流键**不是凭据：查询形状是 `WHERE kind=? AND login=? AND at>=?`，哈希之后仍然要按同一个键等值查（**不减少任何一次查询**），换来的只是「拿到库的人读不出被试过的是哪些学号」—— 而那一句**今天已经不成立**：同一个库里 `student.student_no` / `teacher.staff_no` 就是原文，且本列的取值域恰好是那两列的子集。学号/工号在本系统里**不是秘密**（印在校园卡上、念在课堂上、是 `GET /api/students` 的响应体字段）。故存原文，列宽与那两列**逐字相同**（`String(32)`）。⚠️ 若甲方将来裁定学号是个人敏感信息，正确的处置是给**整份名册**做脱敏，而不是只哈希这一列（只哈希它会给运维一个假的安全感）。 |
| ③ | **不给 smoke 开后门环境变量** | **可行，且实测不需要**（派单 §5 点名这一条可能被顶回）。§2.5 的插件实测：smoke 对同一 `(kind,login)` 最多 **1** 次被计数的失败、且被同步的 ⑦ 当场清零 → 一次绿的 run 结束时 `login_attempt` 里 **0 行 `ok=false`**（§2.4 的库级取证：8 行全 `ok=1`）。故重复跑不累积、不自锁，缺省阈值 5 有 5 倍余量。⚠️ 按派单要求把「它依赖 `PE_LOGIN_MAX_FAILS >= 2`」写进了 `smoke.mjs` 的文件头（含逐格取证与「设成 1 会红在第 16 步 ⑦」的失效形态）。 |
| ④ | 「阈值是配置不是代码」+ 三个环境变量名 | 同意，逐字落地（`PE_LOGIN_MAX_FAILS` / `PE_LOGIN_WINDOW_MIN` / `PE_LOGIN_LOCK_MIN`）。实现者**补了一格**：`max_fails` 下界是 **1**、两个分钟数下界是 **0**（`max_fails=0` 的意思是「0 次失败就达到阈值」= 谁都登录不了，而报错会指向一个与真因无关的地方；两个分钟数的 `0` 是**合法**的 = 关掉那一格）。⚠️ 且报错里**指路**：「要关掉限流请把 `PE_LOGIN_LOCK_MIN` 设成 0」—— 否则运维的下一个动作是把 `max_fails` 设成一个巨大的数，而那**仍然每次失败都写一行库**。 |
| ⑤ | `PE_ENV ∈ {dev, prod}`、缺省 dev | 同意，但**与 05A 既有实现冲突**（05A 认的字面量是 `production`）。处置见 §5.2 第 ② 格：**两个拼法都收**、`prod` 是正字。⚠️ 这不是顶回（派单没禁止接受旧拼法），而是一次**冲突消解**，逐字记在 §7.3 第 ② 处。 |
| ⑥ | 启动自检的失效方向必须是 `raise` | 同意，且**加强**了一格：`PE_ENV` 取到**认不出的值**时也 `raise`（改前 `staging` / `productionn` 都静默落到「开发档」= CORS 全开 + cookie 不带 Secure + 请求头身份通道照环境变量走，三格全是静默不安全）。 |
| ⑦ | 依赖清单守卫用显式列表、不用 sha256；前端若已有守卫就扩它 | 同意。**实测前端守卫不存在**（§6.1 的三条 Grep 取证），故新建了唯一的所有者，而不是造第二个。 |

### 7.2 关切（本波没做、但如实登记）

| # | 关切 | 严重度 | 处置建议 |
|---|---|---|---|
| C1 | **`bind` 两个端点没有限流**。派单 §1 把 Task 3 限定在「登录」，故实现者**没有**扩范围。⚠️ 而 `POST /api/auth/students/bind` 的验身材料是「学号 + **出生日期**」，一个匿名调用方可以无限次猜（`403 forbidden` 那一档对「不在册」与「出生日期不符」**已经是同码同 message**，故它不泄漏，但它也**不被限速**）。⚠️ **不能直接复用本波的机制**：`login_attempt` 的键是 `(kind, login)`，而绑定失败与登录失败**必须分开计数**（否则一个把出生日期打错五次的新生会连带被锁在**登录**外面，而他根本还没有口令）。要做得给键加一个「用途」维度（或另建一张表）。已写进 spec §1.2 第 4 条的残余风险那一格。 | **中** | Plan 06 Task 5/9 或交付前收尾波；一次「加一列 `purpose`」的迁移 + `policy` 的三个动作各加一个入参 |
| C2 | **没有按 IP 的全局速率限制**。本波的限流键是 `(kind, login)`，故它挡「针对某一个账号的口令猜测」，**不挡**「一个匿名调用方把 15 个匿名 GET 打满」，也**不挡**「每次换一个编造的学号去试」（后者落到 403 那一档，而那一档刻意不计数）。 | 中 | 生产在**反代**那一层做（nginx `limit_req` / `limit_conn`）而不是在应用里再写一份：反代看得到真实客户端 IP，而应用看到的可能是反代自己。已写进 spec §1.2 第 16 条 |
| C3 | **`login_attempt` 单调增长**（与 `user_session` 同一条既有待清扫）。原型没有清理任务。⚠️ 而本表**比 `user_session` 好一点**：成功登录会把那个标识的行全删掉，故活跃用户的行不会堆积；堆的是「被反复试错、而从来没人成功登录过」的标识。 | 低 | 与 `user_session` 的过期行清理**合成一个**任务：`DELETE FROM login_attempt WHERE at < now − 30 天` |
| C4 | **跨站部署仍然登不上**：prod + 白名单那一档给了 `allow_credentials=True`（兑现了 spec §13.4.5 那五件事的 ①②），而 ③ 的后半句 `SameSite=None` 没做（`samesite` 恒为 `"lax"`），④⑤ 也没做。⚠️ 按**同源**部署（Plan 06 Task 7 的那个档）不触发这一档。 | 低（同源部署下不可达） | 真的要多源部署时按 spec §13.4.5 那五件事一起改 |
| C5 | **`app/auth/policy.py` 的 `clear_failures` 今天只有一个生产调用方**（`record_success`）。它在 `__all__` 里，故不是死代码，但属于「有能力、无第二个生产调用方」的一档（硬规矩 #39）。留着它的理由是「清零」这件事要有一个可被守卫单独调用的住址。 | 极低 | 不动 |

### 7.3 **没按派单做的**（3 处，逐条）

| # | 派单原文 | 实际做的 | 为什么 |
|---|---|---|---|
| ① | §1 第 1 格「新表 `login_attempt`：`id` / `kind` / `login` / `ok` / `at` / `ip`（可空，取 `request.client.host`）」 | **逐字照做**，但**多加了一个复合索引** `ix_login_attempt_kind_login_at`（派单没提索引） | 限流那一次查询的形状是「两列等值 + 一列范围」，而本表**单调增长**（C3）。没有索引的话每一次登录都要全表扫描一次；列序把范围列放最后是承重的（反过来的 `(at, kind, login)` 在 SQLite 上只用得到第一列）。⚠️ 它是**全库第一个复合索引**（此前 9 个 `ix_*_batch_id` 都是单列 `index=True`），故 `EXPECTED_INDEX_COUNT` 9 → 10 |
| ② | §2 第 2 格「cookie `Secure` 仅 prod 开（05A 既有，**核实它真的是这样**，若不是就修）」 | **核实结果：不是派单以为的那样**，故**修了**。05A 认的字面量是 **`production`**（`app/auth/sessions.py::PRODUCTION`），而派单的取值域是 `{dev, prod}`。处置：`prod` 是正字、`production` **继续接受**，判据搬进新模块 `app/deploy.py`，`sessions.ENV_VAR` / `sessions.PRODUCTION` 变成它的**别名** | 只认 `prod` 会让所有按 05A 那份 spec §13（逐字写着「`Secure` **仅** `PE_ENV=production`」）部署的机器**静默**落到开发档 —— 三格全是静默不安全，正是本 Task 要消掉的失效方向。⚠️ **连带改了一条既有测试**：`tests/auth/test_sessions.py::test_secure_is_on_only_in_production` 改前逐字断言 `"prod"` 给 `cookie_secure() is False`、`"development"` / `"staging"` / `"production-ish"` 也给 `False`；现在 `"prod"` 给 `True`、后三个**抛 `ValueError`**。**它是红着改过来的**，不是顺手扩的 |
| ③ | §6「**建议 4 个 commit**：① 模型 + 迁移 + policy；② 限流接线 + 4 条守卫；③ Task 4；④ 依赖清单守卫 + spec + 报告」 | **照做了 4 个 commit，但文件归属与派单的语义边界有 3 处偏移**（`git add` 是按**文件名**的，本仓纪律不用 `git add -i` 的分片暂存） | (a) `tests/api/test_auth_api.py` 里有 **1 条属于 Task 4** 的守卫（`test_the_header_identity_channel_is_forced_off_in_the_production_tier`），它随 commit ② 进来；(b) `app/main.py` 里那一句 `# 仅为把 27 张表注册进 Base.metadata` 属于 commit ① 的表数同步清单，而整份文件只能进 commit ③；(c) **`tests/test_main.py` 同理**：它的 26→27 三格属于 commit ①、Task 4 的 13 条属于 commit ③，整份文件进了 ③ —— ⚠️ **后果是 commit ① 与 ② 上 `tests/test_main.py` 的 2 条会红**（`test_health_reports_the_table_count` 与 `test_create_app_accepts_an_injected_db_url`，都是 `tables == 26`），**分支 tip（commit ④）上全绿**。如实记，硬规矩 #39 |

### 7.4 待清扫（本波新增 **4** 条；上一波登记的 6 条品牌波 + `session→identity` 桥 + `moss` 命名债**一条都没动**）

| # | 条目 | 来历 |
|---|---|---|
| S1 | `login_attempt` 与 `user_session` 的**过期行清理任务**合成一个（C3） | 本波 |
| S2 | `bind` 两个端点的限流（C1，要一个「用途」维度，不能直接复用本波的键） | 本波 |
| S3 | 反代级的**全局**速率限制（C2） | 本波 |
| S4 | 跨站部署那五件事的 ③④⑤（`SameSite=None` / 前端 `credentials: 'include'` / CSRF 双重提交令牌）（C4） | 本波（①② 已兑现） |
| S5 | ⚠️ 上一波登记的「`app/auth/sessions.py` 的 `ENV_VAR` / `PRODUCTION` 是 `PE_ENV` 的唯一住址」**已作废**：本波把所有者搬去了 `app/deploy.py`，那两个名字现在是**别名**。若有别处文档还写着旧住址，要跟着改（实现者已改：spec §13.4.2 / §13.8、`client.ts`、`vite.config.ts`、`smoke.mjs`） | 本波 |
| S6 | `frontend/src/api/generated/schema.d.ts` 是**生成物**（`npm run gen:api`）。本波重新生成过（+41/−9 行，全是 docstring 里的注释），⚠️ 而它**不被任何守卫钉住**：下一次改后端 docstring 而忘了 `gen:api` 是静默的。建议给它挂一条「与 `/openapi.json` 一致」的守卫（Plan 06 Task 7 的 `serve.ps1` 正好要动这一块） | 本波实测发现 |

### 7.5 最终验收（逐格实测）

| 格 | 基线 | **本波实测** | |
|---|---|---|---|
| 后端全量 | 1370（1369 passed + 1 skipped） | **1426（1425 passed + 1 skipped）**，`238.62 s`（⚠️ 在**分支 tip `8f00b00`** 上亲跑，即含第 ⑤ 条 refactor 之后；中途在 `d5af9c5` 上跑过一次，同样是 1425 + 1 / `237.89 s`） | ✅ **+56** |
| 新增的 56 条 | — | `tests/auth/test_policy.py` **17** + `tests/api/test_auth_api.py` **+9** + `tests/test_deploy.py` **11** + `tests/test_main.py` **+13** + `tests/test_dependencies.py` **6** = **56** | ✅ 逐文件 `--collect-only` 复核 |
| `app/domain/` 覆盖率四格 | 1268 / 0 / 376 / 0 / **100%** | **1268 / 0 / 376 / 0 / 100%**（`--cov=app/domain --cov-branch`，`TOTAL` 行逐字） | ✅ 一格未退（本波一个字都没动 `app/domain/`） |
| 表数 | 26 | **27**（`Base.metadata` / `/api/health` 的 `tables` / 演示库 `sqlite_master` 是 **28** = 27 + `alembic_version`） | ✅ |
| 扫描面（`SCANNED_DIRS` 五个目录） | 66 | **67**（auth 3 → 4） | ✅ 下界 21 / 20 刻意不抬 |
| OpenAPI | 71 路径 / 99 操作 / **81** 挂 security / GET 60（**15** 匿名）/ `securitySchemes` **3** | **71 / 99 / 81 / 60（15）/ 3**（`X-Student-Id` / `X-Teacher-Staff-No` / `pe_session`） | ✅ **五格逐字未变**（`login` 多的那个 `request: Request` 不进 OpenAPI） |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（`LoginAttempt` 走非星号导入，不进公有面；Ruling 97） | ✅ |
| 黄金用例 | 14 | **14**（`golden_cases.json` 的 `input` / `expected` 各 14） | ✅ |
| 四个数据指纹（sha256[:16]，行尾归一化为 LF 后） | `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` / `E48E3AC82BB45BB7` | **逐字相同**（`national_standard_2014.csv` 21412 B / `exercises.yaml` 23247 B / `exercise_equivalence.yaml` 8245 B / `alert_rules.yaml` 6037 B） | ✅ |
| 18 个模板指纹 | 18 个 | **18 个**，逐个 sha256[:16] 与字节数已实测（`RED-END-ABN-01 C0C61D2140A521D0 6865 B` … `GRN-SPD-NOR-18 2389C1A03E6ABBCE 5710 B`），且 `tests/test_refdata_prescription.py` 全绿 | ✅ |
| `git diff f4057a1 HEAD -- backend/data` | 空 | **空**（`git status --porcelain -- backend/data` 也是空） | ✅ |
| `backend/pe.db` | 不存在 | **False**（不存在） | ✅ |
| `backend/data/seed/` | 0 文件 | **0 个文件** | ✅ |
| `smoke.mjs` | 18 步 / 499 断言 / 退出码 0 | **18/18 全绿 · 499 绿 / 0 红 · 退出码 0**（逐步：25/5/10/9/7/9/10/41/14/13/17/6/102/24/109/8/63/27） | ✅ **三格逐字未变**（⚠️ 中途实测过一次 17/18 · 498 绿 / 1 红，红的是第 1 步 `tables == 26`；改成 27 之后 18/18） |
| `npm run build` | 退出码 0 / CSS 65.20 kB / JS 167.03 kB | **退出码 0** / `index-CM7Fwkho.css` **65.20 kB**（gzip 9.79）/ `index-eWDO9FkM.js` **167.03 kB**（gzip 58.52） | ✅ **产物内容哈希逐字相同**（本波前端只改注释） |
| 新增依赖 | 后端 0（alembic 是 Task 1 的）/ 前端 0 | **后端 0 / 前端 0**，且现在**有守卫钉住**（§6） | ✅ |
| spec | 215556 B / 1795 行 / CRLF / — | **228987 B / 1906 行 / 纯 CRLF（1906 CRLF、1906 LF、0 裸 LF）/ 无 BOM / sha256[:16] = `B28601F29D772C9A`** | ✅ 新增 §13.4.6（登录限流与锁定）、§13.8（部署档位与启动自检）、§1.2 第 15/16 两条已知局限，并改写第 2/3 条、§13.4.2 的 login 行与 cookie 七参数、§13.4.5、§13.5、§13.6、§13.7 |
| 迁移链 | 1 条（`53e5a548c40e`） | **2 条**：base `53e5a548c40e`（未动）→ head **`0b7da3d20211`**（5238 B / sha256[:16] `279484F4D5BA1B37` / CRLF 90/90 / 无 BOM） | ✅ |

⚠️ **禁区纪律**：全程**没有**跑 `app.seed.generate` / `app.pipeline.backfill` /
`app.pipeline.daily`；要数据一律走 `backend/scripts/demo.ps1`（它自带两道禁区守卫，
三次重跑三次通过）。`backend/data/**` **一个字节都没动**。

### 7.6 commit

| # | sha | 一句话 |
|---|---|---|
| ① | **`180aa90`** | `feat(db,auth): Plan 06 Task 3 ① —— login_attempt 表 + 迁移 0b7da3d20211 + app/auth/policy`（21 文件） |
| ② | **`72f772d`** | `feat(api)+test(auth): Plan 06 Task 3 ② —— 登录限流接线 + 26 条守卫（含 7 条定点变异取证）`（4 文件） |
| ③ | **`d5af9c5`** | `feat(deploy,main)!: Plan 06 Task 4 —— PE_ENV 生产档三格 + 启动自检（失效方向 = 起不来）`（10 文件） |
| ④ | **`9eac668`** | `test(deps)+docs(spec)+docs(sdd): 依赖清单守卫 + spec §13.4.6/§13.8 + 实现者报告`（6 文件：`tests/test_dependencies.py` / spec / `schema.d.ts` 重新生成 / `smoke.mjs` 的一处注释 / `test_layering.py` 的扫描面散文 / 本报告） |
| ⑤ | **`8f00b00`** | `refactor(auth): policy 的环境变量解析让报错**点名是哪一格**（_minutes → _int_from_env）`。⚠️ 写本报告时复核出来的一个**报错质量**问题、不是行为问题：改前 `_minutes(env_var, default)` 一个函数读三格，于是「必须 ≥ 0（负数会让**窗口起点**跑到未来去…）」那一句对 `PE_LOGIN_MAX_FAILS` 是**一句假话**（它不是时长、没有窗口起点），而函数名叫 `_minutes` 却同时读一个**次数**本身就是味道。改后 `_int_from_env(env_var, default, noun)`，`noun` 进报错文本，那一段时长专属的解释搬去 `throttle()` 的 docstring（它只对两个分钟数成立）。⚠️ **三格的取值域与下界一个字都没变**，守卫一个字都没改就仍然全绿（97 passed 亲跑）—— 那几条断言的是「报错含**变量名** + 含收到的原文 + 含 `PE_LOGIN_LOCK_MIN` 那句指路」，**不是**某一句逐字的散文 |
| ⑥ | 本条 commit | `docs(sdd): 报告补记第 ⑤ 条 commit`（只动本报告；⚠️ 它同时让本报告的字节数/sha 变化，故 §7.5 与交接消息里印的是**本条之后**的值） |

⚠️ **未 push、未碰 `main`**（派单逐字要求）。
⚠️ commit ① 与 ② 上 `tests/test_main.py` 的 2 条会红（§7.3 第 ③ 处），**分支 tip 全绿**
（`8f00b00` 上亲跑：见 §7.5 的第一行）。

⚠️ **交接时的工作树是 clean 的**（`git status --porcelain` 空），且**未 push**。
⚠️ 留在磁盘上的运行期状态：`backend/pe_demo.db`（已进 `.gitignore`）由 `demo.ps1`
重灌过 **3** 次，最后一次之后又跑过 `smoke.mjs` 与 §2.3 的活体矩阵，故它**是脏的**
（`smoke.mjs` 文件头那一段逐字交代了它脏在哪 5 样东西上）—— 下一个人要演示请先重跑
`backend\scripts\demo.ps1 -Port 8000`。`backend/pe.db` **不存在**（禁区未破）。
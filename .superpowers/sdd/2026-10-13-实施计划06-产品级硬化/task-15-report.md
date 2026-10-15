# Plan 06 Task 15 —— 终审修复波 + 🏁 全计划结案 · 实现者报告

> **本波是 Plan 06 的最后一波。** 目标口径：交付给甲方的产品级系统。
> ⚠️ 一律**先实测再改**（硬规矩 #89/#103/#107/#109/#111）：14 条发现里每一条都有
> 改前 / 改后的对比取证，每一次定点变异都**逐字节还原**并 `git status` 复验为空。
> ⚠️ 本报告不复述 spec：产品口径住在 spec §13.14.7 / §13.14.8 / §13.15 / §15，
> 本文件只答「做了什么、量到什么、哪一处与派单或终审不一致」。

**6 个 commit**（⚠️ 与派单建议的切法有一处偏差，见 §⑥-3）：

| # | sha | 一句话 | 自洽？ |
|---|---|---|---|
| ① | `031c641` | 终审报告（Task 14）**原样入库**（一个字节未改） | ✅ 纯文档 |
| ② | `cd485c3` | **A 组**（A1 管理台散文 + A2 字面量拍）；⚠️ 同时带上 B7 的 smoke 那一块 | ✅ 两档 smoke 各 655/0 |
| ③ | `f1ef2be` | **B 组**（B1 demo.ps1 / B3 夹具 / B4 CHECK / B5 超时 / B6 README + `&&`） | ✅ |
| ④ | `02aca1f` | **C 组**（C1 大小写 / C5 restore 比对；C2·C3·C4 = 取证不改代码） | ✅ |
| ⑤ | `197368f` | **D1–D5 的 spec + 账本部分**（§13.14.7 / §13.14.8 🏁 / §13.15 / §15 / progress.md） | ✅ 纯文档 |
| ⑥ | 本 commit | 本报告 + spec 里那两行终值（照 Task 13 的 `127d3bf` 先例）；⚠️ 它自己的 sha **写不进它自己**，故记在 commit 信息与交回里 | ✅ 纯文档 |

---

## ① 环境 + 终审报告入库前的字节 / sha 复核

**开工第一件事（硬规矩 #73）**：`node --version; python --version; git --version` →
**v24.19.0 / Python 3.11.1 / git 2.55.0.windows.5**（与派单给的口径逐字相符；无 venv）。

**开工时的仓库状态**：`git status --porcelain` 只有一行 —— 那份**未跟踪**的终审报告；
HEAD = **`127d3bf`** on `main`。分支 `p06/final-review-fixes` 从它起。

**终审报告入库前的三格复核**（派单逐字要求「若不一致，如实报并停止」）：

| 格 | 派单给的口径 | 本波实测 | 判 |
|---|---|---|---|
| 字节数 | 126 925 B | **126 925 B** | ✅ |
| 行数 | 1 174 行 | **1 174 行** | ✅ |
| 行尾 / BOM | 全 LF / 无 BOM | **CRLF 0 / 裸 LF 1174 / BOM False** | ✅ |
| sha256[:16] | `0fc628b5a90485a4` | **`0fc628b5a90485a4`** | ✅ |

⇒ **四格全部相符**，故入库。入库后 `git cat-file -s :<path>` = **126 925**（= 工作树字节数），
`git ls-files --eol` = `i/lf w/lf attr/-text`（与同目录另外 11 份报告逐字同形）。

**环境的其他格**：FastAPI 0.141.1 / SQLAlchemy 2.1.3 / alembic 1.20.0（`pyproject.toml`
与 `package.json` **一个字都没改**）。⚠️ 5173 上那个**不是本波起的** vite（PID 20240）
**一个字节都没碰**，本波自己起的是 **5174**（`npm run dev` 实测打印
「Port 5173 is in use, trying another one... → Local: http://localhost:5174/」）。

**本波起过的服务**（收尾一律停掉，见 §⑦）：`demo.ps1 -Port 8000`（**4** 次，每次重灌演示库；⚠️ 另有 **1** 次 `-DryRun` 试跑，它**不写** `backend/pe_demo.db`，见 §⑦ 收尾复验）、
`serve.ps1 -Port 8020 -SkipBuild`（**2** 次）、一个手工 `uvicorn :8001`
（`PE_ALLOW_HEADER_IDENTITY=1`，专供 C3 取证）、`npm run dev`（5174，仍在跑，收尾停）。

---

## ② A 组（S2 两条 · 必须修）

### A1 = S2-① · 管理台首页 `/admin` 那段「三个口径」散文与鉴权实物相反

**（a）那 9 行改前 / 改后的原文**

改前（`frontend/src/views/admin/ResourceIndex.vue:100-110`，逐字）：

```html
<p>
  <strong>读是匿名的</strong>：{{ total }} 个资源的列表与详情都不需要身份
  （后端 48 个匿名 GET 里就包括这 23 个 list 与 23 个 read-one）。
</p>
<p>
  <strong>写要教师身份</strong>：{{ writable.length }} 个可写资源的
  POST / PATCH / DELETE 全挂了 <code class="data">require_teacher</code>，
  匿名写是 <code class="data">401 unauthenticated</code>。
  故在没选教师身份时，「新建 / 编辑 / 删除」按钮<strong>不出现</strong>
  —— 页面上会写明要先去左上角的身份切换器选一个教师。
</p>
```

改后（三段；⚠️ 第三段是本波**新加**的，因为「身份从哪来」这件事改前那一句是假的、
而删掉它会留下一个空洞）：

```html
<p>
  <strong>读要身份，只有 {{ ANONYMOUS_READABLE }} 个例外</strong>：
  {{ total }} 个资源里匿名可读的只有那 {{ ANONYMOUS_READABLE }} 个
  <strong>不含任何学生键</strong>的参考数据（学期 / 教学班 / 体测批次 /
  百分位快照 / 动作库 / 处方模板 / 课堂课次），另
  {{ total - ANONYMOUS_READABLE }} 个一律要 <code class="data">pe_session</code> cookie
  —— 匿名打过去是 <code class="data">401 unauthenticated</code>。
  ⚠️ 那 {{ total - ANONYMOUS_READABLE }} 个还各有一道<strong>范围闸门</strong>：
  <code class="data">students</code> / <code class="data">teachers</code> 两行是
  「任何在册教职」（⚠️ 它们正是绑定口令的验身材料，故匿名一律不给），
  13 行是「教师只读自己<strong>本学期任教班</strong>的学生」，
  1 行（<code class="data">weekly-class-reports</code>）是「只读自己本学期任教的班」。
  学生会话只读得到自己那一份。
  （后端 openapi 上匿名 GET 一共 {{ ANONYMOUS_GETS }} 个 = 这
  {{ ANONYMOUS_READABLE }} 个资源的 list 与 read-one 各 {{ ANONYMOUS_READABLE }} 个
  + <code class="data">/api/health</code>；另有 3 个匿名 POST = 登录与两个绑定。）
</p>
<p>
  <strong>写仅管理员</strong>：{{ writable.length }} 个可写资源的
  POST / PATCH / DELETE（一共 {{ writeOps }} 个操作）一律挂
  <code class="data">require_admin</code>：匿名是 <code class="data">401 unauthenticated</code>，
  学生是 <code class="data">403 forbidden</code>，而一个
  <code class="data">role='teacher'</code> 的<strong>普通教师也是
  <code class="data">403</code></strong>（报文逐字是「不是管理员」）。
  故没登录成管理员时，「新建 / 编辑 / 删除」按钮<strong>不出现</strong>。
  ⚠️ 课堂功能（大屏 / 周报 / 三源采集 / 预警处置）走的是
  <strong>另一道</strong>闸门 <code class="data">require_staff</code>（教师或管理员都放行），
  不受这一格影响；而 <code class="data">require_teacher</code> 这个名字自 Plan 05A Task 2 起
  <strong>已经不存在</strong>（它当时判的是「任何在册教师可写」，改名成了
  <code class="data">require_staff</code>）。
</p>
<p>
  <strong>身份从哪来</strong>：<code class="data">/login</code> 页登录
  （<code class="data">POST /api/auth/login</code> 换一个 <code class="data">HttpOnly</code> 的
  <code class="data">pe_session</code> cookie；首次使用先走 <code class="data">/bind</code>
  自绑口令）。⚠️ 报头下面那条会话栏在<strong>产品档</strong>上
  只有「当前身份 + 登出」；那两个身份下拉框是 <strong>DEV-only</strong>
  的开发工具（判据是编译期常量 <code class="data">import.meta.env.DEV</code>，
  生产构建里整个被摇掉），故<strong>换身份请登出再登录</strong>，
  不要去找切换器。
</p>
```

⚠️ **文风照本仓既有口径**：第三段「删除策略三档」一个字未动（它今天仍为真）；
新写的三段一律保留「为什么是这样」（为什么那 7 个可以匿名、为什么 `students`/`teachers`
两行是「任何在册教职」、为什么课堂功能不受影响、为什么切换器在产品档不存在）。

**（b）本波自己实测的数字**（`demo.ps1 -Port 8000` + 真 HTTP，⚠️ 一个都没抄终审报告）：

| 格 | 实测 | 改前页面写的 |
|---|---|---|
| 23 个资源里**匿名 list 200** 的 | **7** 个：`semesters` / `course-sections` / `fitness-test-batches` / `percentile-snapshots` / `exercises` / `prescription-templates` / `class-sessions` | 「23 个都不需要身份」 |
| 匿名 list **401** 的 | **16** 个（其余全部） | — |
| 匿名 `GET /api/students/1` | **401** `unauthenticated` | 「详情都不需要身份」 |
| openapi 上没有 `security` 键的**操作** | **18** 个 | — |
| 其中**匿名 GET** | **15** 个（= 7 个 list + 7 个 read-one + `/api/health`） | 「48 个匿名 GET」 |
| 其中**匿名 POST** | **3** 个（`/api/auth/login` + 两个 `bind`） | — |
| `POST /api/students` 匿名 | **401** `unauthenticated` | 「401」✅（这一格改前是对的） |
| `POST /api/students` **学生** cookie | **403**「一个学生的 cookie 不能当教师用」 | — |
| `POST /api/students` **教师 T0001** | **403**「身份 'T0001' 不是管理员（teacher.role == 'teacher')…仅 role='admin' 可用」 | 「写要教师身份」 |
| `POST /api/students` **管理员 T0003** | **422**（过了身份闸门、倒在请求体校验上） | — |
| 泛型写入操作数 | **26**（9 POST + 9 PATCH + 8 DELETE；`forbid` 那 10 个不注册 DELETE） | — |
| `require_teacher` 这个名字 | 全 `app/` 里 **6** 处命中**全在 docstring / 注释里**（`crud.py:202,1523` / `deps.py:805,812` / `catalog.py:22,328`），**没有**一个可调用对象 | 「全挂了 `require_teacher`」 |
| 身份切换器（两个下拉框） | `IdentitySwitcher.vue` 的 `③ DEV-only` 那一块，判据 `const IS_DEV = import.meta.env.DEV` ⇒ **产品档不渲染** | 「要先去左上角的身份切换器选一个教师」 |

⚠️ 顺带实测到一格**比终审更强**的事实：那 2 条学生专用端点（`/api/students/{id}/prescriptions/current`
与 `/weekly-sheet`）连**管理员**都是 **403**（终审只测了教师）—— 已写进 B1 的标注。

**（c）新 needle 的无歧义取证**（派单逐字要求「先实测页面上有没有第二处同串」）

| needle | 在渲染出来的正文里出现 | 判 |
|---|---|---|
| `读要身份，只有 7 个例外` | **恰好 1 处**（smoke 断言实测 `1 处`） | ✅ 无歧义 |
| `写仅管理员` | **恰好 1 处** | ✅ 无歧义 |
| `换身份请登出再登录` | **恰好 1 处** | ✅ 无歧义 |

⚠️ 而「无歧义」这件事**不靠人眼**：本波给 `ROUTES` 加了一个 `uniqueNeedles` 字段，
smoke 第 14 步对里面每一条都断言「在 `toPlainText` 之后的正文里**恰好 1 处**」——
两处同串（终审 S3-⑦ 的失效形状）会当场红。

**（d）两个写死的计数为什么可以写死**（本文件唯一一处，页面自己的纪律是「一个都不写死」）

`ANONYMOUS_READABLE = 7` 与 `ANONYMOUS_GETS = 15` **派生不出来**：
「哪几行匿名可读」的唯一所有者是后端 `app/api/routers/catalog.py` 的 `read_scope` 那一列
（五档表在它的模块 docstring 里），而**前端目录 `catalog/resources.ts` 刻意不带这一格**
（它带的是渲染要用的 `writable` / `onDelete` / `displayFields`）。故本波把它们做成
**具名常量 + 一段「刻意的第二所有者」注释 + 两道守卫**（与本仓 `_MODELS_PUBLIC_BASELINE`
钉 33、18 个模板钉 sha256 同一条姿势）：

1. smoke **第 12 步新加 5 拍**：期望侧从 `/openapi.json` **现量**（「哪些操作没有 `security` 键」），
   被测侧从 `ResourceIndex.vue` 的**源码**里正则读出那两个字面量 —— 两侧不同源。
   实测输出：`openapi 上没有 security 键的操作 18 个（GET 15 / 写 3）`、
   `其中集合 GET 匿名的资源 7 个：semesters, course-sections, fitness-test-batches,
   percentile-snapshots, exercises, prescription-templates, class-sessions`；
   5 拍全绿（含 2 条反空转：那 7 个里不含 `students`/`teachers`、3 个匿名写操作全在 `/api/auth/*`）。
2. smoke **第 14 步 3 条 `uniqueNeedles`**（上表）。

⚠️ 而「26 个写入操作」那一格**能**现算，故写成 `const writeOps = computed(() =>
writable.value.length * 2 + deleteCount.value)`（9×2 + 8 = 26），**没有写死**。

**（e）定点变异**：把 `<strong>写仅管理员</strong>` 改回 `<strong>写要教师身份</strong>`
（= 改前那句假话的核心）→ smoke **653 绿 / 2 红、退出码 1**，红的正是
`admin-index：DOM 里出现了 8 条关键内容 → 缺 "写仅管理员"` 与
`needle "写仅管理员" 在正文里恰好 1 处 → 0 处`；还原后 sha256[:16] 逐字节复原
`910e1122a032f42d`（与本波改完时同一个值），`git status` 对该文件为空。

**（f）不动后端 ⇒ 不需要重跑 `gen:api`**：本波**一个进 openapi 的 docstring 都没改**
（`git diff 127d3bf HEAD --stat -- backend/app/api backend/app/main.py` 里只有
`app/static.py` 与 `app/api/deps.py`，前者是 C1 的判据、后者是 B3 的**注释**；
两者都不进 openapi 的 `description`）。⚠️ 复核口径：openapi 五格实测
**74 / 102 / 84 / 63（15 匿名 + 48）/ 3**，与基线**逐格相同**（见 §⑦）。

### A2 = S2-② · 「不许静默截断」那条守卫是自指的

**（a）字面量拍**（新增 `tests/api/test_column_widths.py::test_the_overlong_marker_is_literally_the_visible_cut_token`）：

```python
assert width.OVERLONG_SUFFIX == "…[cut]", (
    f"截断标记被改成了 {width.OVERLONG_SUFFIX!r}。它必须逐字是「一个 … + [cut]」"
    f"这六个字符：逐字理由见 app/db/width.py:62-64（一个孤零零的 … 会出现在真实"
    f"数据里，于是「被截过」与「本来就有个省略号」不可分辨 = **静默截断**）。"
    f"⚠️ 本拍**刻意**硬编码字面量：期望侧读 width.OVERLONG_SUFFIX 就是自指（终审 S2-②）。"
)
assert len(width.OVERLONG_SUFFIX) == 6
```

⚠️ docstring 里逐字写清了「为什么这一拍必须硬编码」（模块 docstring 那条
「期望侧必须从模型声明推出来」的纪律针对的是**宽度**——一个会随表结构漂的量，
而这里钉的是**标记的形状**——它不从任何一张表推得出来，而「从被测模块自己的常量推」
就是自指），并指向 `width.py:62-64` 那段论证、以及本仓既有的三处同款姿势
（`_MODELS_PUBLIC_BASELINE` 钉 33 / `TEMPLATE_FINGERPRINTS` 钉 18 个 sha256 /
`test_sessions.py:552` 钉 `SESSION_TTL == dt.timedelta(hours=2)`）。

**（b）「改前 3 绿 / 改后 1 红」的变异取证**（`pytest tests/api/test_column_widths.py`）：

| 变异（`app/db/width.py` 的 `OVERLONG_SUFFIX`） | **改前**（新拍还没加） | **改后**（新拍加上） |
|---|---|---|
| 基线（不变异） | exit 0 · **16 passed** | exit 0 · **17 passed** |
| `"..."` | exit **0** · 16 passed ⇒ **绿（守卫没响）** | exit **1** · 1 failed / 16 passed ⇒ **红** |
| `"      "`（6 个空格，**等宽而不可见**） | exit **0** · 16 passed ⇒ **绿** | exit **1** · 1 failed ⇒ **红** |
| `"…"`（一个孤零零的省略号） | exit **0** · 16 passed ⇒ **绿** | exit **1** · 1 failed ⇒ **红** |

⚠️ 派单只要求「改成 6 个空格 → 新守卫必须红」，本波把终审那三次**全跑了一遍**
⇒ **改前 3 绿 / 改后 3 红**（超额）。每次还原后 `width.py` 的 sha256[:16] 逐字节复原
**`fe6f82b4a1ed95d8`**（6 次全部 `byte-identical=True`），`git status -- backend/app/db/width.py`
**空**。⚠️ 红的报文里带着理由原文（「…逐字理由见 app/db/width.py:62-64…」），
故下一个人不需要去翻报告。

**（c）A2-③ 同族自查：全仓「期望侧直接读被测模块常量」的完整清单与逐个判断**

扫描面 = `backend/tests/**`（全部 `.py`）+ `frontend/scripts/**`。三条正则：
① `^\s*\w+\s*=\s*<mod>.<CONST>`（局部别名）② `(assert|==) … == <mod>.<CONST>`（直接比较）
③ `\b(in|not in)\s+<mod>.<CONST>`（成员判定）。命中 **18** 处：

| # | 住址 | 形状 | 它是不是也让某条守卫永绿？ |
|---|---|---|---|
| 1 | `tests/api/test_column_widths.py:447` | `suffix = width.OVERLONG_SUFFIX` | ⚠️ **是真洞**（终审 S2-② 点名的那一处）→ **已修** |
| 2 | `tests/api/test_column_widths.py:657` | 同上（端到端那一拍：305 字符路径落库 256 + 尾部标记） | ⚠️ **同族真洞** → 同一拍字面量断言一次性收掉 |
| 3 | `tests/api/test_column_widths.py:958` | 同上（极窄列退化那一支） | ⚠️ **同族真洞** → 同上 |
| 4 | `tests/test_backup_restore.py:989` | `real_backups = backup.BACKUPS_DIR` | ❌ 不是洞：读的是**位置**（要在动作前后各快照一次那个目录），断言的是「没有多出文件」，与常量的值无关；改了 `BACKUPS_DIR` 本条仍然量的是**新的那个真目录** |
| 5 | `tests/auth/test_policy.py:1017` | `bind = policy.PURPOSE_BIND` | ❌ 不是洞：它是**输入标签**（传给 `is_locked(purpose=…)`），而期望侧（59 / 60 / 20 分钟三个时刻）是**字面量**；同文件另有 `test_the_bind_and_login_thresholds_are_not_cross_wired` 钉两组阈值不串线 |
| 6 | `tests/auth/test_policy.py:860` | `for purpose in policy.PURPOSES` | ❌ 不是洞：遍历**输入域**，不是期望值 |
| 7 | `tests/test_refdata.py:187` | `path = refdata.DATA_DIR / refdata.STANDARD_FILENAME` | ❌ 不是洞：读**文件位置**，期望侧是那一份指纹字面量与行数 |
| 8-10 | `tests/test_refdata_prescription.py:223 / 241 / 312` | `path = rp.DATA_DIR / rp.<X>_FILENAME` | ❌ 同上（三份 YAML 的位置） |
| 11-13 | `tests/domain/test_prescription_templates.py:825 / 967 / 997` | `directory = rp.DATA_DIR / rp.PRESCRIPTION_DIRNAME` | ❌ 同上（18 个模板的目录）；期望侧是 18 个 sha256 **字面量** |
| 14-15 | `tests/test_serve.py:850 / 1007` | `getattr(r, "path", None) == static.SPA_ROUTE_PATH` | ❌ 不是洞：它是在 `app.routes` 里**找出**那条 catch-all（身份判定），断言的是「它排在最后」与「恰好一条」；而 `SPA_ROUTE_PATH` 的**值**由 Task 7 的 13 格 fallback 矩阵按真 URL 钉住（改了它，`/admin` 那些深链接会当场 404） |
| 16 | `tests/test_serve.py:842` | `routes[-1].path == static.SPA_ROUTE_PATH` | ❌ 同 14 |
| 17 | `tests/test_serve.py:845` | `sum(… == static.SPA_ROUTE_PATH …) == 1` | ❌ 同 14 |
| 18 | `tests/api/test_auth_api.py:1512` | `row.expires_at - row.last_seen_at == auth_sessions.SESSION_TTL` | ❌ **不是洞，但值得记**：它单看是自指的，而 `tests/auth/test_sessions.py:551-552` 另有两拍 `kwargs["max_age"] == int(SESSION_TTL.total_seconds()) == 7200` 与 `SESSION_TTL == dt.timedelta(hours=2)`（**字面量**）⇒ 那一格已经钉住，本处只是复用 |

⇒ **真洞 1 族 / 3 个住址**（#1–#3），一拍字面量断言全部收掉；其余 **15** 处逐个给了理由。
⚠️ **没有超过 5 处**，故不需要「只修真洞、其余登记待清扫」那一档。
⚠️ 前端 `frontend/scripts/**`（`smoke.mjs` / `check-tokens.mjs` / `check-dist.mjs`）
**0** 处同族命中：它们读源码一律是「读文本 + 正则」，期望侧是字面量
（例如 `const WANT_COLUMNS = [['行 id','id'], …]`）。

---

## ③ B 组（S3 七条）

### B1 = S3-① · `demo.ps1` 那 8 条 URL × 身份矩阵

**逐条真发请求实测**（`demo.ps1 -Port 8000`，4 档身份各用**对应身份的 cookie**）：

| # | URL | 匿名 | **学生**（`2025060001`） | **教师**（T0001） | **管理员**（T0003） | 标注 |
|---|---|---|---|---|---|---|
| 1 | `GET /api/students/1/prescriptions/current?as_of=2025-10-12` | 401 | **200** | **403** | **403** | 【学生本人】教师/管理员 403 |
| 2 | `GET /api/students/1/weekly-sheet?as_of=2025-10-12` | 401 | **200** | **403** | **403** | 【学生本人】教师/管理员 403 |
| 3 | `GET /api/alerts?limit=50` | 401 | 200（只自己那一份） | **200** | 200 | 【教师或管理员】 |
| 4 | `POST /api/alerts/{id}/handle?as_of=2025-10-12` | 401 | **403** | **200** | 200（见下注） | 【教师或管理员】学生 403 |
| 5 | `GET /api/notifications?limit=50` | 401 | 200（只自己那一份） | **200** | 200 | 【三档都行】 |
| 6 | `GET /api/dashboard/class/1?week=6&as_of=2025-10-12` | 401 | **403** | **200** | 200 | 【教师或管理员】学生 403 |
| 7 | `POST /api/pipeline/run-daily` | 401 | **403** | **200** | 200 | 【教师或管理员】学生 403 |
| 8 | `GET /api/mini-tests/normalized?semester_id=2&week=6` | 401 | 200（只自己那一行） | **200** | 200 | 【三档都行】 |

⚠️ 注：#4 的「管理员 200」是**另跑一次**量到的 —— 同一次跑里教师先把它处置了，
管理员再打就是 **409 `alert_not_pending`**（那正是「一条预警只能处置一次」的口径）。
⚠️ #7 是**破坏性**的（会把周报的「预警汇总」清零），故排在最后跑、之后重灌演示库。

**处置选择**：那 2 条学生专用的 → **标注，不换成教师能点的例子**。理由：它们正是
spec §1.3 三段闭环的头两段（处方 → 训练单），换掉等于把闭环拆了；而脚本自己的
`[6/7]` 那一步会打印一个**真**学号，标清身份之后演示者会先登成学生。
⚠️ 并且如实写明「`/students/1/` 是**那一个学生自己的 id**；演示库上 `[6/7]` 印的例子
恰好是 id 1，故照着点就通 —— 而那是**巧合不是契约**（`demo_bootstrap` 取的是
`student_nos[0]`、**没有 ORDER BY**），换过 `--students` / `--seed` 之后请自己核一次」。

**`.ps1` 的三格纪律**（前几波剥掉过 BOM 四次）：改完当场核 —— `git ls-files --eol` =
`i/lf w/crlf attr/text eol=crlf`、BOM 位 = **True**、字节 **21 898 → 25 480**；
另用 `[System.Management.Automation.Language.Parser]::ParseFile` 复核语法 = **0 个 parse error**。

### B2 = S3-② · 覆盖率口径（**兑现计划 §10 第 1 条后半句**）

⚠️ **没有改覆盖率配置、`pyproject.toml` 一个字都没动**（那会让四格的历史断链）。
三个口径都是本波亲跑：

| 口径 | 命令 | TOTAL（Stmts / Miss / Branch / BrPart / Cover） | 墙钟 | 测试结果 |
|---|---|---|---|---|
| **四格**（十三波一直报的那一个） | `pytest -q --cov=app/domain --cov-branch` | **1268 / 0 / 376 / 0 / 100%**（18 个文件逐个 100%） | **346.10 s** | **1572 passed, 1 skipped** |
| 全 `app/` | `pytest -q --cov=app --cov-branch` | **7300 / 201 / 1774 / 115 / 96%** | **376.37 s** | 1571 passed + 1 failed（那 1 条是 C5 第一版 import alembic 撞的既有守卫，**已修**，见 §④-C5）+ 1 skipped |
| `backend/scripts/**`（⚠️ **两个既有口径都不扫它**） | `pytest -q --cov=scripts --cov=app.static --cov-branch tests/test_backup_restore.py tests/test_serve.py tests/api/test_prescription_api.py` | **583 / 206 / 164 / 22 / 64%** | **24.29 s** | **93 passed** |

⇒ 「100%」那四个字覆盖的是全仓 **1268 / (7300 + 583) ≈ 16%** 的可执行语句。

**本计划新增 / 改动模块各自的覆盖率**（派单点名的 14 个 + 本波另外量到的 4 个）：

| 模块 | Stmts | Miss | Branch | BrPart | Cover | 未覆盖的行 |
|---|---|---|---|---|---|---|
| `app/api/crud.py` | 356 | 17 | 160 | 17 | **93%** | 1317, 1712, 1722, 1735, 1743, 1755, 1764, 1796, 1804, 1809, 1819, 1828, 1838, 1848, 1863, 1873, 1879 |
| `app/api/deps.py` | 131 | 5 | 50 | 3 | **94%** | 680-685, 705, 870 |
| `app/api/routers/catalog.py` | 17 | 0 | 2 | 0 | **100%** | — |
| `app/static.py` | 80 | 3 | 28 | 1 | **96%** | 392, 408-411 |
| **`app/api/audit.py`**（⚠️ 派单写的「`app/audit.py`」实测**不存在**；真名与住址是这一个） | 57 | 5 | 4 | 0 | **92%** | 389-391, 412-413 |
| `app/auth/policy.py` | 88 | 1 | 12 | 1 | **98%** | 676 |
| `app/auth/passwords.py` | 70 | 0 | 22 | 0 | **100%** | — |
| `app/db/width.py` | 32 | 0 | 16 | 0 | **100%** | — |
| `app/deploy.py` | 21 | 0 | 4 | 0 | **100%** | — |
| `backend/scripts/backup.py` | 142 | 14 | 40 | 6 | **88%** | 167-168, 276, 307, 408->410, 436, 476, 494-501 |
| `backend/scripts/restore.py` | 157 | 23 | 52 | 12 | **82%** | 93->96, 142, 199, 253->258, 308, 317->301, 321-322, 401, 422-423, 431, 439-442, 465-467, 477-484 |
| `backend/scripts/dump_openapi.py` | 39 | 20 | 8 | 2 | **45%** → §15 F4 | 106, 126-127, 168-204, 208 |
| `backend/scripts/serve_app.py` | 20 | 1 | 6 | 1 | **92%** | 79 |
| `backend/scripts/demo_bootstrap.py` | 145 | 145 | 30 | 0 | **0%** → §15 F4 | 117-629 |
| `app/db/session.py` | 74 | 0 | 16 | 1 | **99%** | 249->248 |
| `app/api/errors.py` | 56 | 0 | 10 | 1 | **98%** | 148->152 |
| `app/auth/sessions.py` | 91 | 0 | 20 | 0 | **100%** | — |
| `app/api/routers/audit.py` | 22 | 0 | 6 | 0 | **100%** | — |

⚠️ `restore.py` 从终审量的 110 stmts / 80% 长到 **157 / 82%** —— 本波 C5 加了
`code_head_revisions()` 与那一段打印，而新增的两条守卫（正例 + 反空转）把它**跑到了**。

**写进 spec 的那段诚实性措辞（原文，§13.14.7）**：

> ⚠️⚠️ **本节同时兑现了 B2（终审 S3-②）要的那一格文档诚实性**：
> 十三个波次报的「覆盖率四格 **1268 / 0 / 376 / 0 / 100%**」量的是 **`app/domain/`**
> 这一层（口径逐字写在命令里：`--cov=app/domain`），而它是本计划
> **刻意不动**的一层：`5131c12..127d3bf` 那 **109** 个文件的累计 diff 里
> **一个 `backend/app/domain/**` 文件都没有**（唯一沾边的是
> `app/pipeline/report_stage.py` 的 2 行）。⚠️ 于是 1268 stmts / 376 branch
> 这两个**分母在结构上不可能变**，「十三波一格未动」**不是守卫的功劳、
> 是改动面的事实**。⚠️⚠️ 故那四格**不是本计划的质量总账**：
> 它们说的是「Plan 06 一行都没碰的那一层仍然 100%」，而本计划新增/改写的
> ~5 900 行产品代码与 ~1 300 行运维脚本**一个都不在那个口径里**。

⚠️ `demo_bootstrap.py 0%` 与 `dump_openapi.py 45%` 如实进 **§15 F4**，
**没有为了好看去补测试**（并写清为什么它今天不影响可信度：前者每一次都被
`demo.ps1` 真跑、后者有一条按**字节**对账的守卫）。

### B3 = S3-③ · `taught_student_ids` 的两格 `semester_id` **分开钉**

**走了派单的强选项（造夹具），没有顶回**，因为实测成本**成比例**：
`tests/api/test_dashboard.py` 的 `_seed(engine)` 已经给全了需要的行
（`ids["semester"]` / `ids["section"]` = 张老师**本学期**的班 / `ids[OUTSIDER_NO]`），
两条新测试各只需**一行混合行**（≈ 30 行含注释），不动既有夹具族、不动演示数据、
不动产品代码、不动迁移（链仍是 4）。

| 新测试 | 造的那一行 | 它单独钉住哪一格 |
|---|---|---|
| `test_an_enrollment_from_last_semester_pointing_at_this_semesters_section_is_not_mine` | `Enrollment(semester_id=<上学期>, student_id=outsider, course_section_id=<张老师**本学期**的班>)` | `Enrollment.semester_id == semester_id`（子查询那一格此时**满足**，故本格是唯一挡住它的） |
| `test_a_section_from_last_semester_does_not_make_this_semesters_enrollment_mine` | `CourseSection(semester_id=<上学期>, teacher_id=张老师)` + `Enrollment(semester_id=<本学期>, course_section_id=<那个上学期的班>)` | `taught_section_ids` 里的 `CourseSection.semester_id == semester_id`（`Enrollment` 那一格此时**满足**） |

**定点变异取证**（`pytest tests/api/test_dashboard.py -k semester`，基线 **5 passed**）：

| 变异 | 结果 | 红的是哪几条 |
|---|---|---|
| 只去掉 `Enrollment.semester_id == semester_id` | exit **1** · 1 failed / 4 passed | **恰好** `test_an_enrollment_from_last_semester_…`（T1）；T2 绿、既有那 2 条绿 |
| 只去掉 `taught_section_ids` 里的 `CourseSection.semester_id == semester_id` | exit **1** · 1 failed / 4 passed | **恰好** `test_a_section_from_last_semester_…`（T2）；T1 绿、既有那 2 条绿 |
| 两格一起去掉 | exit **1** · 4 failed / 1 passed | T1 + T2 + 既有的 `test_teaching_last_semester_does_not_grant_access_this_semester` 与 `…_to_the_home_page` |

⇒ 终审量到的「单独去掉任一格 185 条一条不红」**今天不再成立**：两格各自单独可观测。
三次还原后 `deps.py` 的 sha256[:16] 逐字节复原 **`ca8f0572e4911737`**、`git status` 空。

⚠️ 连带修正：`app/api/deps.py:1088-1096` 那段自述里「本仓今天没有那样的夹具 ——
如实记为已知边界」**已经过期**，按事实改写（保留 Task 8 当时的实测事实、
加上本波那两条夹具的名字与三次变异的结果）。⚠️ 那两行混合行**库层面可写**
（两列各自都是合法外键，而本仓**刻意**没有一条 CHECK 把它们绑在一起），
故没有动 schema。

### B4 = S3-④ · `ck_alert_subject_is_exactly_one` 的守卫

新增 `tests/api/test_crud.py::test_the_alert_subject_check_constraint_exists_by_name_and_shape_in_model_and_ddl`，
**两面各钉一次**（两侧不同源）：

* **① 模型元数据**：`Alert.__table__.constraints` 里恰好有 **1** 个
  `CheckConstraint` 叫 `ck_alert_subject_is_exactly_one`，而它的 `sqltext` 里
  `student_id IS NULL` 与 `course_section_id IS NULL` **各出现 1 次**、且含 `<>`。
  ⚠️ 形状一律**从元数据读**，一个字面量都不抄；⚠️ 唯一写死的是**约束的名字**
  （那是一个**决定**、不是一个算式，口径与本仓 `PBKDF2_MIN_VERIFY_ITERATIONS == 100_000`
  与 `OVERLONG_SUFFIX == "…[cut]"` 逐字相同）。
* **② 实库的 DDL**：`SELECT sql FROM sqlite_master WHERE type='table' AND name=<Alert.__tablename__>`
  里那个名字与那两列都在。⚠️ `engine` 夹具走的是 `init_db` → **alembic 迁移链**
  （不是 `create_all(models)`），故 ② 量到的是**迁移写出来的** DDL，与 ① 的模型元数据
  **不同源**：「模型上有、迁移里漏了」与反过来都会红。
* **反空转**：`alert` 表上**还有** ≥ 2 个别的 CHECK（实测 `ck_alert_level` / `ck_alert_status`），
  故 ① 不是「一张没有任何 CHECK 的表上恰好有 1 个叫这名字的」那种空转形状。

**定点变异**：把那条 `CheckConstraint(...)` 从**模型**上去掉 → 新守卫**红**
（报文：`alert 上叫 ck_alert_subject_is_exactly_one 的 CHECK 有 0 个；全部 CHECK 的名字
= ['ck_alert_level', 'ck_alert_status']`），而 `tests/db/test_migration_chain.py`
那 **8** 条照旧绿；还原后 `feedback.py` sha256[:16] 逐字节复原 **`df28b861bf8075c5`**。
⚠️ **只在临时库上试、没有生成任何新迁移**：变异期间与还原之后各跑一次
`tests/db/test_migration_chain.py` + `test_migration_baseline.py` = **8 passed / 31 passed**，
迁移链**仍是 4 单头**（§⑦）。

**另测那条 CHECK「有牙」**（终审实测过，本波在**演示库的一份临时副本**上重做一遍）：
克隆一行真预警、只改两个作用域列 —— 「两格都非空」与「两格都空」两次 INSERT
各得 `sqlite3.IntegrityError: CHECK constraint failed: ck_alert_subject_is_exactly_one`；
临时目录跑完删掉并复验（`temp dir removed: True`）。

### B5 = S3-⑤ · 会话恢复的超时（**先取证，再修**）

**（a）改前的运行时取证**（终审那一格标的是「静态推断、未取证」，本波补上）。
手法照终审用的那一招：CDP 的 **`Fetch` 域只扣住 `/api/auth/me` 这一个请求**
（⚠️ **不拖慢全网** —— 那会连 JS 产物一起拖住，取样到的就是「什么都还没挂载」的白屏）。
产品档（`serve.ps1 -Port 8020 -SkipBuild`，`dist` 是本次构建的）、管理员 cookie、
导航到 `/admin/audit-logs`、扣住 **19 s**：

| 取样点 | DOM 正文 | 挂载了？ | 「身份未确认」 | 会话状态 | 「未登录」/ANONYMOUS | 超时字样 | 审计页渲染了？ |
|---|---|---|---|---|---|---|---|
| +2 147 ms | 1 111 字符 | ✅ | ✅ | `restoring` | ❌ | ❌ | ❌ |
| +6 190 ms | **1 111** | ✅ | ✅ | `restoring` | ❌ | ❌ | ❌ |
| +11 085 ms | **1 111** | ✅ | ✅ | `restoring` | ❌ | ❌ | ❌ |
| +18 608 ms | **1 111** | ✅ | ✅ | `restoring` | ❌ | ❌ | ❌ |

放行之后 **262 ms** 落定 `authed`（审计页真渲染出来）。
⇒ **终审的静态推断成立**：阻塞**没有上限**，页面无限期停在「身份未确认…」，
既不落 `authed` 也不落 `anon`、也不弹去 `/login`、也没有任何横幅。

**（b）修**（时长 **10 s**，理由：实测 `/api/auth/me` 从放行到落定是 **262 ms**，
10 s ≈ 它的 **38 倍** ⇒ 一次正常的慢查询/慢反代不会误触；而一个真挂住的连接也不会
让人等过「以为页面坏了」那条线。终审建议的区间是 8–10 s）：

| 改动 | 文件 | 它做什么 |
|---|---|---|
| `fetchMe(signal?: AbortSignal)` → `apiRequest('GET','/api/auth/me', { signal })` | `src/api/auth.ts` | 把那一次请求变成可中断的（`client.ts` 早就支持转交，只是没人传） |
| `export const RESTORE_TIMEOUT_MS = 10_000`（唯一所有者）+ `SessionStatus` 加第五档 `'timed_out'` + `ensureRestored` 里 `AbortSignal.timeout(...)` 与 `isRestoreTimeout()` 那一支 | `src/stores/session.ts` | 有界等待；到点 → `status='timed_out'` + 一句 `notice` + `asked` 保持 `false`（下次导航再试）+ 仍然 `throw`（守卫放行） |
| `summary`：`if (state.status === 'timed_out') return '身份确认超时…'`（**排在 pending 之前**） | `src/stores/session.ts` | 会话条与页脚不再无限期说「身份未确认…」 |
| `roleLabel`：`if (session.status === 'timed_out') return 'TIMEOUT'`；actions 区加一个 `⟳ 刷新页面`（复用既有 `.btn .btn--primary .btn--sm`）；那一档**不给**「去登录」 | `src/components/IdentitySwitcher.vue` | 一个**可读的错误态 + 一个刷新入口**；⚠️ **一行新 CSS 都没加、一个色值裸值都没引** |

⚠️ `'timed_out'` **刻意不算** `isPending`（pending 说的是「还在路上、别急着下结论」，
而超时是一个**已经落定的负面答案**），故 `isPending` 的两档判据**逐字未变** ⇒
smoke 第 17 步 ⑧③ 那条「那个谓词在 `src/**` 里恰好 1 处」照旧成立（实测绿）。
⚠️ 守卫是 smoke 第 17 步 ⑧ **新加的 5 拍**（源码结构面）：⑧⑥ `AbortSignal.timeout(RESTORE_TIMEOUT_MS)`
真的传了 + `fetchMe` 真的把 `signal` 转交给 `apiRequest`（少了后半格，前半格就是空转）；
⑧⑦ 上限是一个**具名字面量**且落在 5–30 s（实测打印 `RESTORE_TIMEOUT_MS = 10000 ms`）
+ `'timed_out'` 不算 pending；⑧⑧ 超时之后**有出路**（`setNotice` + `TIMEOUT` + `⟳ 刷新页面`
+ `location.reload()`）。⚠️ **运行时那一档刻意不进 smoke**：它要给每一步加 10 s 墙钟，
而两档今天各 ~30 s（§13.11.4 记着「结构面守卫吃掉约 1/4」那一笔账，再加 1/3 就不成比例了）。

**（c）改后的同一次取证**（扣住 16 s）：

| 取样点 | DOM 正文 | 「身份未确认」 | 会话状态 | 超时字样 | 审计页渲染了？ |
|---|---|---|---|---|---|
| +2 137 ms | 1 111 | ✅ | `restoring` | ❌ | ❌ |
| +6 188 ms | **1 111** | ✅ | `restoring` | ❌ | ❌ |
| **+11 097 ms** | **3 468** | ❌ | **`timed_out`** | ✅ | ✅（`<h2>` = 审计留痕） |
| +15 585 ms | **3 468** | ❌ | `timed_out` | ✅ | ✅ |

超时那一帧逐格实测（CDP 直接读元素）：

```
role pill      : "TIMEOUT"
summary        : "身份确认超时…"
status text    : "会话状态 timed_out"
notice (.switcher__warn): "身份确认超时：10 s 内 GET /api/auth/me 没有回答（后端或反向代理挂住了）。
                           请刷新页面重试；若反复出现，去查后端日志。"
action buttons : ["⟳ 刷新页面|btn btn--primary btn--sm"]     ← 恰好一个，且用的是既有 class
page h1/h2     : ["厦大体育数智系统","审计留痕"]              ← 路由放行了、页面真渲染了
footer         : 不再说「未登录」
```

⚠️ 一个如实记的观察：超时之后浏览器那一次 `Fetch.continueRequest` 会报
`Invalid InterceptionId` —— 因为前端已经**自己 abort 了那一次 fetch**，
那正是 `AbortSignal.timeout()` 生效的**第三份**证据（不是缺陷）。

### B6 = S3-⑥ · 仓库根 README + spec §13.6 的 `&&`

**（a）README**：新建 `README.md`，**60 行**（控制者裁定的上界「不超过 60 行」，实测恰好 60）。
内容是「这是什么 / 三条命令跑起来（`demo.ps1` / `serve.ps1` / `npm run dev`，含 PS 5.1 语法）/
起来之后看哪儿（4 条 URL）/ 演示账号去哪儿看 / 16 条路由去哪儿看 / 接口文档 / 交付须知在 §13.15」。
⚠️ **每一条命令与 URL 都真跑过再写**：

| 写进 README 的 | 本波怎么验的 | 实测 |
|---|---|---|
| `powershell -ExecutionPolicy Bypass -File backend\scripts\demo.ps1 -Port 8000` | 真跑 **4** 次（+1 次 `-DryRun` 试跑） | 灌 60 人 → `[7/7]` 十三个行数逐个印出 → uvicorn 起在 :8000 |
| `powershell -ExecutionPolicy Bypass -File scripts\serve.ps1 -Port 8020` | 真跑 **2** 次（其中一次带 `-SkipBuild`） | 健康检查 `{"status":"ok","tables":28,"students":60}` → 前端 + API 同源在 :8020 |
| `cd frontend; npm install; npm run dev` | `npm install` 真跑 | `up to date, audited 93 packages`，退出码 **0**；⚠️ `package.json` 与 `package-lock.json` **一格未变**（`git status` 对这两个文件为空）。`npm run dev` 真跑 → `VITE v8.3.4 ready in 301 ms` / **`Local: http://localhost:5174/`**（5173 被别的进程占着） |
| `npm run build`（README 里没写，而 `serve.ps1` 会自己判新鲜度） | 真跑 **3** 次 | 退出码 **0**（含 `vue-tsc -b`，故类型也过了） |
| `http://<host>/` | `Invoke-WebRequest` | **200** `text/html; charset=utf-8` 2 729 B |
| `http://<host>/api/health` | 同上 | **200** `application/json` **41 B** = `{"status":"ok","tables":28,"students":60}`（三格，故 README 逐字写「三格」） |
| `http://<host>/docs` · `/redoc` · `/openapi.json` | 同上 | **200** / 1 023 B · **200** / 905 B · **200** / **417 032 B** |
| `http://<host>/login`（SPA fallback） | 同上 | **200** `text/html` 2 729 B |
| `http://localhost:5174/` 与 `/login` | 同上 | **200** `text/html` 2 525 B（vite 的 dev 壳） |
| 「16 条路由的唯一所有者是 `frontend/src/router/index.ts` 的 `routes` 数组」 | 数 | `routes` 数组（第 122–298 行）里 `path:` 字面量 = **20**；smoke 钉的可导航叶子页 = **16** |
| 「演示账号由 `demo.ps1` 的 `[6/7]` 从库里打印」 | 真跑 | `[6/7]` 实测印出口令 `pe-demo-2025`、`学生：…（60 个，例如 2025060001）`、`管理员 … [('T0003','赵志刚','admin')]` |

**行尾**（派单要求「实测 `core.autocrlf` 会怎么处理它，报两个口径」，且**不要为它改
`.gitattributes`**）：

| 口径 | 实测 |
|---|---|
| **工作树** | **2 864 B / 60 行 / CRLF 60 / 裸 LF 0 / 无 BOM** / sha256[:16] `26acb1e8e2cca67f` |
| **入库 blob** | **2 804 B / LF**（`git cat-file -s :README.md` = 2804） |
| `git ls-files --eol` | **`i/lf    w/crlf  attr/`** ← `attr/` 为空 = **仓库根的 `.md` 今天没有任何 attribute 钉扎**（`git check-attr -a README.md` 输出为空，实测） |
| `core.autocrlf` | **`true`** ⇒ 提交时 CRLF→LF 归一、检出时 LF→CRLF 展开，**两个口径都对**、`git diff` 为空 |

⚠️ `.gitattributes` **一条都没碰**（禁碰项）。

**（b）spec §13.6 的 `&&`**：`npm install && npm run dev` → **拆成两行**，并写清
**为什么也不改成 `;`**（`;` 在 PS 5.1 里不看前一条的退出码，于是 `npm install` 失败也会
接着跑 `npm run dev`，而后者会报一个离真因很远的错「找不到 vite」）。

**（c）全仓 `&&` 清单**（`Document/**/*.md` + 新 README，**不含** `.superpowers/**` 历史账本）
—— 实测 **29** 处，逐个报：

| 处数 | 住址 | 判 |
|---|---|---|
| **1** | `Document/2026-09-28-体育闭环原型-设计spec.md:2645`（`npm install && npm run dev`） | ⚠️ **真问题 → 已修** |
| **4** | Plan 01 / 02 / 03 / 04 / 05B 五份计划文档里各一处「**PowerShell 5.1**：`;` 分隔、不支持 `&&`/`||`」 | ❌ 不是问题：那是**警告本身**（在告诉读者不要用 `&&`），不是给 PS 用户的命令 |
| **24** | `Document/2026-09-28-实施计划01-数据基座与分层引擎.md` 的 `Run:` 行（`cd backend && pytest …` 一族） | ⚠️ **部分顶回：不改**。那份文档的**第 31 行**已逐字声明「本仓库在 Windows / PowerShell 下开发：所有 `Run:` 命令中出现的 `&&` 一律按 `;` 执行」⇒ 它们**不是**「给 PS 用户写的假命令」；而把它们改成 `;` 会让第 31 行那句声明失去指代对象（于是还得改它）—— 那是一份**绑时点**的历史计划文档（与 Plan 06 的计划文档「一个字都不许改」同一条纪律）。已登记 **§15 F5** |
| **0** | 新 `README.md` | ✅ 0 处 |
| **0** | spec §13.1 / §13.6 / §13.11（三处运行口径的活文档） | ✅ 修完之后 0 处 |

⚠️ 另实测：`frontend/package.json` 的 `gen:api` 脚本里有一个 `&&`
（`python … && openapi-typescript …`）—— **那不是给 PS 用户的**：npm 在 Windows 上用
`cmd.exe` 跑 script，`&&` 在那里是合法的；且 `package.json` 是禁碰项。如实记，不改。

### B7 = S3-⑦ · smoke 的 `身份类型` needle 歧义 + 审计页九列列头

**（a）先实测「身份类型」在页面上出现在哪两处**：`AuditLogList.vue:116` 的**列头**
（`{ key: 'subject_kind', label: '身份类型', wrap: false }`）与 `:331` 的**过滤器下拉标签**
（`<label class="a-pager__where">身份类型 <select …>`）。经 `toPlainText`
（标签 → 空格 + 折叠空白）之后两处的下文不同：列头是 `身份类型 subject_kind`
（`<th>` 里紧跟一个 `<code>{{ column.key }}</code>`），过滤器是 `身份类型 （不过滤） 教师 · teacher …`。

**（b）needle 换成无歧义的**：`'身份类型'` → **`'身份类型 subject_kind'`**，
并**同时**进新加的 `uniqueNeedles`（断言它在正文里**恰好 1 处**）⇒「无歧义」这件事
从此是**守卫**、不是人眼。实测：`admin-audit-logs：needle "身份类型 subject_kind" 在正文里恰好 1 处 → 1 处` ✅。

**（c）九列列头逐个断言**（⚠️ 中文文案一律**实测**，不抄派单）。
smoke 用 CDP 抓 `.a-table thead th` 的 `[label 文本, code 里的 slug]` 二元组，与一份
**字面量**期望逐字对拍（期望侧 = 字面量，被测侧 = 渲染出来的 DOM，两侧不同源）：

```
DOM 实测 9 个列头：["行 id","时刻","身份类型","身份 id","工号","方法","路径","状态码","对象"]
                   [["行 id","id"],["时刻","at"],["身份类型","subject_kind"],["身份 id","subject_id"],
                    ["工号","staff_no"],["方法","method"],["路径","path"],["状态码","status"],["对象","target"]]
后端那一行的键顺序：["id","at","subject_kind","subject_id","staff_no","method","path","status","target"]
```

⇒ 三拍全绿：① 列头**恰好 9 个**（`AuditLogRead` 的九格，一个都不多）；
② 九列的中文文案 + slug **逐个逐字相同、且顺序相同**；
③ **交叉验证**：九列的 slug 与后端 `GET /api/audit-logs` 真回的那一行的**键顺序**
逐字相同（DOM vs HTTP，两侧不同源 ⇒「列头对不上后端字段名」会红）。
⚠️ 第三拍是 §13.9 那条「九格全是标量、一个都不多」的裁定在 UI 上的**唯一可见面**。

**（d）定点变异 —— 复现终审那一格改前改后的对比**：把 `AuditLogList.vue:116` 的
`label: '身份类型'` 改成 `'身份种类'`（= 终审的 S04）：

| | smoke（dev 档，干净库） |
|---|---|
| **改前**（终审实测，本波复核同一形状） | **637 绿 / 0 红 · 退出码 0** ⇒ needle 被过滤器那一处满足了 |
| **改后**（本波实测） | **652 绿 / 3 红 · 退出码 1**，红的三条逐字是：`admin-audit-logs：DOM 里出现了 6 条关键内容 → 缺 "身份类型 subject_kind"`、`needle "身份类型 subject_kind" 在正文里恰好 1 处 → 0 处`、`§S3-⑦ 九列的中文列头文案 + 字段 slug 逐个逐字相同 → DOM=[[…"身份种类","subject_kind"…]]` |

还原后 `AuditLogList.vue` 的 sha256[:16] 逐字节复原 **`238345d1fb910b16`**，
`git status` 对该文件为空。

---

## ④ C 组（S4 五条）

### C1 = S4-① · `/API/health` 大小写变体

**判据的唯一所有者是 `app/static.py` 的 `is_reserved`**，改成**两趟比**：
第一趟逐字比全部四项（`RESERVED_PREFIXES`），第二趟把 `url_path` 折成小写、
只比新常量 `RESERVED_PREFIXES_CASE_INSENSITIVE`（今天只有 `/api` 一项，
而 `/api` 那一个字面量由新的私有 `_API_PREFIX` 持有 ⇒ **本模块只写一遍**）。
⚠️ 边界口径在两趟里**是同一条**（「等于，或以 `前缀 + "/"` 开头」），
故 `/APIXYZ` 与 `/API-HEALTH` 照旧**不是**保留前缀。

**大小写矩阵（产品档 :8020，裸 socket，路径逐字发出、不被任何一层归一化）**：

| 路径 | **改前** | **改后** |
|---|---|---|
| `/api/health` | 200 · `application/json` · 41 B | **200 · `application/json` · 41 B**（逐字未变） |
| `/API/health` | ⚠️ **200 · `text/html; charset=utf-8` · 2 729 B**（= index.html） | ✅ **404 · `application/json` · 66 B** |
| `/Api/Health` | ⚠️ 200 · text/html · 2 729 B | ✅ **404 · application/json · 66 B** |
| `/apI/HEALTH` | ⚠️ 200 · text/html · 2 729 B | ✅ **404 · application/json · 66 B** |
| `/api/nope` | 404 · application/json · 66 B | **404 · application/json · 66 B**（逐字未变） |
| `/API/nope` | ⚠️ 200 · text/html · 2 729 B | ✅ **404 · application/json · 66 B**（与 `/api/nope` **同款**） |
| `/LOGIN` | 200 · text/html · 2 729 B | **200 · text/html · 2 729 B**（刻意不动） |
| `/Admin` | 200 · text/html · 2 729 B | **200 · text/html · 2 729 B**（刻意不动） |
| `/DOCS` | 200 · text/html · 2 729 B | **200 · text/html · 2 729 B**（刻意不动） |
| `/docs` `/redoc` `/openapi.json` | 200 · 1 023 / 905 / 417 032 B | **200 · 逐字未变** |
| `/index.html` | 200 · text/html · 2 729 B | **200 · 逐字未变** |
| `/assets/xmu-emblem-vodJYAz_.svg` | 200 · `image/svg+xml` · 52 095 B | **200 · 逐字未变** |
| `/favicon.ico` `/robots.txt` | 404 · application/json · 66 B | **404 · 逐字未变**（见 C2） |

⚠️ **只有 `/api` 这一项放宽**的理由（不是省事，是**消费者不同**）：`/api/*` 是机器面
（监控探针、脚本、前端 `fetch` 之后的 `JSON.parse`），一个 200 的 HTML 在那一面是一句
会**静默**骗人的话（探针永远绿、`JSON.parse` 在离真因很远的地方炸）；
而 `/docs` 与前端路由是人手敲的，回 `index.html` 之后前端 router 会把人弹到该去的地方
（`/LOGIN` → `/:pathMatch(.*)*` → `/s/home` → 守卫 → `/login`），那一档改回 404 JSON
反而是把人拦在一个白屏上。

**不许影响的三组守卫 · 全部复跑**：`tests/test_serve.py`（含 Task 7 的 **13** 格 fallback
矩阵 `test_a_missing_product_file_answers_the_unified_404_and_the_thirteen_cells_still_fall_back`、
Task 11 的 **6** 格 404 `test_an_unknown_path_under_a_reserved_prefix_answers_the_unified_404`、
`/api/*` 的可观察行为 `test_the_api_the_contract_and_the_two_doc_pages_are_not_shadowed`）
+ `tests/architecture`（含 spec §13.11.2 那条守卫与 `_is_api_allowed` 的边界口径）
= **50 passed / exit 0**。

**新增 2 条守卫**（各带反空转）：
`test_the_api_prefix_is_matched_case_insensitively_but_the_human_routes_are_not`
（判据层：8 格大小写变体是保留前缀 / 8 格「另三项 + 前端路由」**不是** /
4 格边界串 `/APIXYZ` `/API-HEALTH` `/Apixyz` `/api-health` 照旧不是 /
新清单是 `RESERVED_PREFIXES` 的**子集**且一律小写且以 `/` 开头）；
`test_an_uppercase_api_path_answers_the_unified_404_and_not_index_html`
（HTTP 层：5 格 404 + 统一形状 + 不含 `PE-SPA-FIXTURE`；反空转 ① 小写 `/api/health`
照旧 **200 JSON**、② `/DOCS` 与 `/LOGIN` 照旧回 index.html —— 少了这两拍，
「把 `is_reserved` 整个改成大小写不敏感」会是绿的，而那正是终审点名不要的形状）。

### C2 = S4-② · `/favicon.ico` 与 `/robots.txt`

**先实测，三种情况落在第 ② 种**：

| 实测格 | 结果 |
|---|---|
| `frontend/index.html` 里 `<link rel="icon"` 的命中 | **0 处**（整个文件里 `link rel` / `icon` 一个都没有；只有 `<title>厦大体育数智系统</title>`） |
| `frontend/dist` 的根级 | **只有 `index.html`**（其余 25 个产物全在 `assets/`） |
| `frontend/public/` | **不存在** |
| `/favicon.ico`（产品档） | **404 · `application/json` · 66 B** |
| `/robots.txt`（产品档） | **404 · `application/json` · 66 B** |
| 品牌 svg 在产物里 | `dist/assets/xmu-emblem-vodJYAz_.svg` → **200 · `image/svg+xml` · 52 095 B**（⚠️ 文件名**带内容哈希**，故不能在 `index.html` 里写死路径） |

⇒ 不是「引用了一个不存在的路径」（第 ① 种），也不是「今天已经有图标」（第 ③ 种），
而是**第 ② 种**：引用没错（压根没引用），只是 `/favicon.ico` 这个**约定路径**上没有文件。
**按控制者裁定：不加文件**（不为了浏览器约定往仓库塞一个二进制），`robots.txt` **也不加**
（内网系统不需要，加了反而是一格要维护的东西）。

**标签上到底有没有图标的取证**：`<link rel="icon">` 0 处 + `/favicon.ico` 404
⇒ 浏览器**没有**任何图标可用（无头 Edge 的那一次 CDP 取证里 DOM 内 `link[rel~=icon]`
命中 0 个；而 404 本身是**正确**的裁定 —— 回一份 200 的 index.html 才是撒谎，
终审对这一格的判断本波复核为真）。⚠️ 若要加，代价是**三处已写下的实测陈述会过期**
（`app/static.py:162-169` 那段「根级没有任何静态文件…既没有 `<link rel="icon">`」、
`cache_control_for` 的第 ③ 格「其余今天一格都没有」、`check:dist` 的扫描面 **25** 个产物）
⇒ 登记 **§15 D4**（需甲方裁定），本波不动。

### C3 = S4-③ · `/docs` 两档都公开 + 那两个「生产档已死的请求头 scheme」

**维持控制者裁定：保持公开、不加开关**（产品档实测 `/docs` 200 / 1 023 B、
`/redoc` 200 / 905 B、`/openapi.json` 200 / **417 032 B**）。两件事都落了：
① 写进 **§13.15 第 10 条**（含「若甲方要求内网限定，请在**反代**上加一层 basic auth
或 IP 白名单 —— 本仓不在应用里做」）；② 写进 **§15 D2**（标成「需甲方裁定」，
并给出「若硬要在应用里做」的最小形状与要同步的三处）。

**那两个 scheme 是不是假契约 —— 本波专门取证，结论：不是。**

openapi 上的三个 `securitySchemes` 与它们的引用面（实测）：

| scheme | 形状 | 被多少个操作引用 |
|---|---|---|
| `pe_session` | `apiKey` in **cookie** | **2**（`GET /api/auth/me` / `POST /api/auth/logout`） |
| `X-Teacher-Staff-No` | `apiKey` in **header** | **73** |
| `X-Student-Id` | `apiKey` in **header** | **36** |

**两档对照实测**（`GET /api/students?limit=1` + 一个伪造的 `X-Teacher-Staff-No: T0001`）：

| 进程 | `PE_ALLOW_HEADER_IDENTITY` | 不带头 | 带伪造头 |
|---|---|---|---|
| `serve.ps1 -Port 8020`（产品档，脚本**强制清**掉它） | 未设 | **401** `unauthenticated` | **401** `unauthenticated` |
| 本波手工起的 `uvicorn :8001`（`$env:PE_ALLOW_HEADER_IDENTITY="1"`，dev 档） | `=1` | **401** | ✅ **200**，且**真回名册**（`{"items":[{"id":1,"student_no":"2025060001","name":"周晨阳",…}]}`） |

⇒ 那两个 scheme 是一条**有文档、需显式 opt-in 的开发期通道**（§13.11.7 / `demo.ps1` 的
注释逐字交代过「要在本机临时打开它，请在另一个终端里设 `=1` 再起 uvicorn」），
**不是**「没有任何端点真认那两个头」的假契约 ⇒ **不顶回、不摘**。
⚠️ 摘掉的成本已写进 **§15 D3**：`securitySchemes` 从 **3** 变、openapi 五格全变、
`gen:api` 要重跑、**26** 个特例端点清单要同步，而换来的只是「一份对匿名开放的地图上少两格」；
⚠️ 并且明确写了「**不要**只摘 scheme 不收文档 —— 那会造出一份『看不出身份怎么传』的契约，
比今天更坏」。

### C4 = S4-④ · 迭代下界 —— ⚠️ **顶回：派单要加的守卫今天已经存在**

**派单要求**：加一条守卫钉住「演示库/演示账号写哈希用的迭代数 ≥ `PBKDF2_MIN_VERIFY_ITERATIONS`」，
两侧都不许硬编码。**实测结果**：那一格**已经有守卫**，而且形状与派单要求的逐字相符 ——
`backend/tests/auth/test_passwords.py:637`
`test_the_two_bounds_admit_the_production_default_and_the_demo_value`：

* **被测侧**：用 **AST** 从 `backend/scripts/demo_bootstrap.py` 读出
  `DEMO_PBKDF2_ITERATIONS`（⚠️ 不 `import` 那个脚本，因为它在包外、import 会跑它的模块体）；
* **期望侧**：`assert PBKDF2_MIN_VERIFY_ITERATIONS <= demo <= PBKDF2_MAX_VERIFY_ITERATIONS`
  （从 `app.auth.passwords` 读常量）；
* ⚠️ 而 `PBKDF2_MIN_VERIFY_ITERATIONS == 100_000` 与 `PBKDF2_MAX_VERIFY_ITERATIONS == 2_000_000`
  在**同一条测试的第 684-685 行按字面量钉住**（那条测试自己的注释逐字写了为什么：
  「阈值是**决定**、不是算式，从被测侧读回来跟自己比是同源断言、什么都证明不了」）；
* ⚠️ 它的 docstring 甚至逐字预告了终审点名的那一格：「于是『把下界抬到 200 000』
  这一个看起来很安全的动作会当场红 —— 而改前它会静默地把演示库与测试套件一起打死」。

**两处迭代数的住址（派单点名要实测「演示库的哈希是谁写的」）**：

| 住址 | 值 | 谁用它 | 钉它的守卫 |
|---|---|---|---|
| `backend/scripts/demo_bootstrap.py:199` `DEMO_PBKDF2_ITERATIONS` → `--pbkdf2-iterations` 的 **default**（:312）→ `os.environ[PBKDF2_ITERATIONS_ENV_VAR]`（:433）→ `iterations()` → `hash_password(DEMO_PASSWORD)`（:455/:458） | **100 000** | 演示库那 **63** 个账号（60 学生 + 3 教师）的 `password_hash` | 上面那一条（AST 读脚本 + 字面量钉下界） |
| `app/auth/passwords.py:201` `PBKDF2_DEFAULT_ITERATIONS`（环境变量未设时 `iterations()` 的返回值） | **600 000** | 运行时经 `POST /api/auth/*/bind` **新绑**的口令（`demo.ps1` 起的 uvicorn **不设**那个环境变量） | `test_the_production_default_iterations_is_at_least_the_owasp_floor:85`（`>= 600_000` **字面量**）+ `:668` 的 `MIN <= DEFAULT` |

⇒ **派单说的「若那一格是 `iterations()` 的缺省值…那要钉的是两处」成立，而两处今天都已经被钉住**。
实测演示库：`password_hash` 里出现过的迭代数**只有一个取值 `100000`**
（T0001 那一行前两段 = `pbkdf2_sha256$100000$…`），与 `demo.ps1 [6/7]` 打印的
「迭代次数是**演示值** 100000（生产缺省 600000）」一致。

**定点变异两次都红**（证明那条既有守卫**有牙**，不是本波臆断）：

| 变异 | 结果 |
|---|---|
| 基线（`test_the_two_bounds_admit_…` 单跑） | exit **0** · 1 passed |
| `DEMO_PBKDF2_ITERATIONS` 100_000 → **99_999**（= 派单点名的「把演示写入路径的迭代数改成 99 999」） | exit **1** · 1 failed，报文逐字：`演示库用 99999 次迭代，落在 [100000, 2000000] 之外 ⇒ demo.ps1 灌出来的库没人登得进去`（`test_passwords.py:670`） |
| `PBKDF2_MIN_VERIFY_ITERATIONS` 100_000 → **200_000**（= 终审点名的「将来谁把下界抬到 200 000」） | exit **1** · **9 failed / 8 passed**（含 :684 那一条字面量拍） |

两次还原后 sha256[:16] 逐字节复原（`demo_bootstrap.py` = **`6b620ff33146dd3c`**、
`passwords.py` = **`a2bcfa26668f1a11`**），`git status` 对这两个文件为空。
⚠️ **不改下界**（终审判定失效方向安全，100 000 是 OWASP 2023 建议值 600 000 的合理下界）；
⚠️ **不加重复守卫**（加一条同判据的就是第二个所有者）。
⚠️ 那一格的**交付说明**已写进 §13.15 第 2 条（含「日志里出现『迭代次数 N 越出
[100000, 2000000]』= 库里那一行哈希是界外迭代数写的，要重灌那一行」的处置）。

### C5 = S4-⑤ · `restore.py` 比对 `alembic_version`

新增 `restore.code_head_revisions()`（⚠️ **只用标准库**：`configparser` 读 `alembic.ini`
的 `script_location`（`interpolation=None`，因为 `%(here)s` 是 alembic 自己的插值）
+ `ast` 读 `versions/*.py` 的 `revision` / `down_revision`（⚠️ 两档都认：`ast.Assign`
与 alembic 模板写出来的 `ast.AnnAssign` —— 本仓四份迁移实测一律是后者），
再取「没人当父亲的那一个」）。恢复完之后与自检读到的 `revision` 比一次，
不一致就印一段响亮的 ⚠️；**退出码仍然是 0**（不硬失败）。

**那一句 ⚠️ 的原文**（端到端真跑一次抓下来的 stdout，逐字）：

```
   自检   sqlite_master 里的表数 = 29
          alembic_version = 7f3923d8af84
          student 行数 = 0

   ⚠️⚠️⚠️ 这一份备份的迁移版本比**当前代码旧**：
      备份停在    7f3923d8af84
      代码的 head  0ac943e0da9b
      ⇒ 从**现在**到**下一次起服务**之间，这个库真的停在那条旧链上：
        此时若用一个**不经** init_db 的工具直接读它（sqlite3 命令行、
        一个旧的报表脚本），它看到的是**旧结构**（例如被某一条迁移
        改宽过的那一列仍然是旧宽度）。⚠️ 在补齐之前请不要这样读它。
      ⇒ 起服务时 init_db 会自己 upgrade head 补齐（本仓实测过这一档：
        日志里会出现一行 Running upgrade <备份停的那个> -> <head>、
        被迁移改过的那一列回到新值、标记数据一行都没丢），
        故本脚本**刻意不把它当成失败**（退出码仍然是 0）。
```

⚠️ 打印里**刻意不含任何修订号字面量**（两个号都是现读的），故下一条迁移落地之后
这一段自动跟着走；`code_head_revisions()` 实测返回 `('0ac943e0da9b',)`。
⚠️ 读不出链头时（alembic 不可用一类）印另一句人话「本脚本**没能**比对……请自己核一次
`alembic heads` 再起服务」，**不让一次已经成功的恢复变成失败**。

**端到端复现终审那七步**（一律在 `$env:TEMP` 的临时库上，**一个字节都没碰禁区**）：

| 步 | 做什么 | 实测 |
|---|---|---|
| ① | 用 `ScriptDirectory` 取 head 的 `down_revision`，`command.upgrade(cfg, <它>)` 建一个**链 3** 的库 | revision = **`7f3923d8af84`** |
| ② | 往它里面放一行**标记数据**（`semester.name = "旧链上的标记行"`） | ✅ |
| ③ | `backup.create_backup(...)` | 备份 + `.sha256` 侧车都写出 |
| ④ | `init_db` 建一个**链 4** 的目标库（revision = `0ac943e0da9b`） | ✅ |
| ⑤ | `restore.main([<备份名>, "--dir", …, "--db-url", <目标>])` | 退出码 **0**；校验/后路/字节/自检四段照印；**那一段 ⚠️ 逐字印出**（两个修订号都在） |
| ⑥ | 恢复完**立刻**再读一次 | `selfcheck(...)["revision"] == "7f3923d8af84"` ⇒ 库里**真的**停在旧链上（不是打印完就自己补齐了） |
| ⑦ | 再跑一次 `init_db`（= 起服务） | revision → **`0ac943e0da9b`**；标记数据那一行**逐字还在**（`_semester_name(target) == "旧链上的标记行"`）⇒ **会自愈**，故本波**没有**改成硬失败 |

**新增 2 条守卫**：正例（上面七步，`test_restore_warns_loudly_when_the_backup_sits_on_an_older_migration_chain`）
+ **反空转**（`test_a_backup_that_is_already_at_head_does_not_get_that_warning`：
一份 head 的备份恢复上去**不得**打那一句 —— 少了它，「把判据写成恒真」会让正例全绿，
而「狼来了」喊多了运维会开始忽略所有 ⚠️）。`tests/test_backup_restore.py` **21 passed**。

**定点变异**：把那一句比对改成 `if False:` → 正例**红**、反空转**绿**
（`1 failed, 1 passed`，红的正是正例）；还原后 `restore.py` sha256[:16] 逐字节复原
**`c693a63f81a6741f`**，`git status` 对它只剩本波**有意**的那一处修改。

⚠️ **一处如实记的返工**：`code_head_revisions()` 的第一版写的是
`ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_heads()`，
它把既有守卫 `test_neither_script_copies_files_or_adds_a_dependency` **弄红了**
（报文逐字：`restore.py 引入了非标准库的依赖 ['alembic']：本波新增依赖 = 0
（备份用标准库 sqlite3 + hashlib）`）。那条守卫的立意是「备份/恢复这两个脚本是
**救急工具**，不该拖着一条 ORM/迁移依赖链」——本波**认同它**，故**不改守卫、改自己**
（换成 `ast` + `configparser` 的纯标准库实现）。⚠️ 代价如实写进那个函数的 docstring：
它成了「迁移链的头是谁」这个问题的**第二个读点**（alembic 自己是第一个），
而它们会一起漂的那一档由 `tests/db/test_migration_chain.py` 挡住（那一份逐字钉住
**4 单头**与四个修订号，且它走的是 alembic 自己的 `ScriptDirectory`）⇒ 两侧不同源、不是自指。

---

## ⑤ D 组（结案）

### D1 · 终审报告入库 + spec §13.14.7

* 报告入库 = commit **`031c641`**，**原样、一个字不改**（入库前的四格复核见 §①）。
* **§13.14.7**（新增）= 终审的账面（区间 / 分级 / 28 次变异 / 41 条断言 / 总判断 /
  计划 §10 的终审对账 / 置信度）+ **本波对 14 条的逐条处置表**（修 11 / 不修 3，
  每条写明落在哪个 commit）+ **B2 要的那一段文档诚实性措辞**（原文见本报告 §③-B2）
  + 三个覆盖率口径的两张表。
* ⚠️ **计划文档 `Document/2026-10-13-实施计划06-产品级硬化.md` 一个字都没改**
  （`git diff 127d3bf HEAD --stat` 里没有它，见 §⑦）；
  ⚠️ **11 份历史波次报告一个字都没改**（账本不改写，硬规矩 #66）。
  ⚠️ 同理，账本 `progress.md` 里 Task 14 那一段「（本波之后的下一波，尚未做）」
  **原文照留**，只在它上面**加**一行「本段由 Task 15 标注为已过期」的引注。

### D2 · 新增 spec §13.15「交付须知」（**11 条**）

11 条**逐条自己复核过**（不抄终审）。结果：**10 条今天仍成立**，
**1 条的一个数字复现不出来**（第 8 条的 `108 B`）—— 如实写在 §13.15 那一行里，
本报告 §③/§④ 与本节下面各有一格取证：

| # | 一句话 | 本波复核结论 |
|---|---|---|
| 1 | 产品档缺省是 **dev** 档（无 `Secure`、CORS `*`、启动自检不跑；上 HTTPS 后必须自设 `PE_ENV=prod` + `PE_CORS_ORIGINS`；请求头身份通道**两档都关**） | ✅ **仍成立**。`serve.ps1` 实测印 `PE_ENV = 未设（= dev 档）` / `档位 = dev（cookie 的 Secure = False）` / `PE_ALLOW_HEADER_IDENTITY … 强制清成 未设`；进程内实测 `deploy.tier()='dev'`、`cookie_kwargs()['secure']=False`、`CORSMiddleware allow_origins=['*']`；`PE_ENV=prod` 时 `secure=True` 且 `allow_header_identity()` 两档都 `False`；伪造头在 :8020 上 → **401** |
| 2 | 演示口令**公开**、演示库哈希用 **100 000** 次迭代（生产缺省 600 000） | ✅ **仍成立**（库里只出现过 `100000` 这一个取值）。⚠️ 而终审说的「无守卫钉住」**不成立**（见 §④-C4） |
| 3 | **读审计不记 GET** | ✅ **仍成立**：演示库 `audit_log` 里 `method='GET'` **0 行**（POST 27 / PATCH 0 / DELETE 0） |
| 4 | ⚠️ 任何教职（含不带班的新教师）能一次读到全校 60 人名册含 `birth`，并据此替未绑定账号抢绑口令 | ✅ **仍成立，本波完整跑通两条链**：① 管理员建一个**不带任何班**的新教师 → 他自绑 **204** → 登录 **200** → `GET /api/students?limit=200` **200 / total=60 / 每行都带 `birth`**（而**匿名**同一条是 401）；② 再建一个**未绑定**的教职 → 他读到那一行的 `name` → **匿名** `POST /api/auth/teachers/bind` **204** → 用那个口令登录 **200**（= 账号被接管）。⚠️ 它是 §1.2 第 4 条**已登记**的残余、不是本计划引入的，而**必须念给甲方听** |
| 5 | 被降权的管理员重登前 `/me` 仍回 `role: admin`（前端会送他进 `/admin` 然后每次写都 403；**权限**是立刻生效的） | ✅ **仍成立**：T0003 用自己的会话 `PATCH /api/teachers/3 {role:'teacher'}` → 200；**同一份 cookie** 的 `/me` 仍回 `role: 'admin'`；而同一份 cookie 读 `/api/audit-logs` 当场 **403 forbidden**；重登后 `/me` 才回到 `role: 'admin'`（本波把它改回去了） |
| 6 | 三张表单调增长、**无清理任务**，而备份是整库备份 | ✅ **仍成立**：`audit_log` 27 / `login_attempt` 3 / `user_session` 11 行（一次演示之后）；产品源码（排除 `tests/`）里 `DELETE FROM 那三张表` / `retention` / `purge_old` / `archive_` 命中 **0** 处 |
| 7 | **备份不加密**、不做保留策略 | ✅ **仍成立**：`backup.py` 里 `encrypt*` / `cipher*` / `Fernet` **0** 处、`retention*` / `prune*` **0** 处（`.unlink` 的 3 处命中全在**注释**里，逐字说的是「**刻意不**先 unlink 目标」）；`backup.ps1 -Dir` 开关在 |
| 8 | 限流**按标识不按 IP**，锁定档响应与「口令错」逐字节相同（**108 B**） | ⚠️ **性质仍成立、那个字节数复现不出来**。实测：`policy._key(purpose, login)` 的签名里**没有 ip**；缺省阈值登录 **5 / 15 / 15**、绑定 **3 / 15 / 60**（`DEFAULT_MAX_FAILS=5` / `DEFAULT_WINDOW_MINUTES=15` / `DEFAULT_LOCK_MINUTES=15` / `DEFAULT_BIND_*=3/15/60`）；学生 `2025060001` 连错 5 次之后第 6 次的响应体与第 1 次**逐字节相同**（**82 B** / 401 `invalid_credentials` / message 逐字「口令不正确」），⚠️ 而**锁内用正确口令登录也是同一份 82 B**。三种组合实测：学生 401 = **82 B**、教师 403 `password_not_bound` = **181 B** —— **没有一档是 108 B** |
| 9 | 换数据库后端之前必须先做 §15 C3 + 重写迁移 4 的 `downgrade` | ✅ **仍成立**：迁移 4 的 `downgrade` 实测用 `batch_alter_table`，docstring 逐字写着「**本条的 `downgrade` 只在 SQLite 上验证过；换后端时这一格要重写**」+ PG 当场失败 / MySQL 静默截断两档失效 |
| 10 | （本波新增，= C3）`/docs` `/redoc` `/openapi.json` **两档都公开**；要收请在**反代**上加一层 | ✅ 实测三格各 **200**（1 023 / 905 / **417 032** B）。⚠️ 并写清那两个请求头 scheme **不是假契约**（开发档 opt-in 之后是活的） |
| 11 | （本波新增，= B2）**覆盖率那三个口径怎么读** | ✅ 三个口径本波亲跑（346.10 s / 376.37 s / 24.29 s），18 个模块逐个报在 §13.14.7 |

⚠️ 本节刻意只做**索引 + 一句话**，口径正文一律在它指的那一节（不做第二个所有者）；
⚠️ 它**不替代** §15（本节说「交付那一天要念什么」，§15 说「下一波要做什么、为什么今天不做」）。

### D3 · §15 延后台账补充：**16 → 21 条 / 6 组**

一律照既有体例（加粗小标题 + 项目符号 + 「是什么 / 为什么不做 / 怎么做」三格 + 一个指针），
**没有另起一套**：

| 新增 | 组 | 一句话 |
|---|---|---|
| **D2** | D 需产品负责人 / 甲方裁定 | `/docs` 两档都公开（为什么不做 + 若甲方要收怎么做 + `gen:api` 不受影响） |
| **D3** | D | openapi 上那两个请求头 scheme（本波实测**是活的** ⇒ 不摘；摘的成本五格 + 「不要只摘 scheme 不收文档」） |
| **D4** | D | 浏览器标签上没图标（实测三格 + 为什么不加 + 若要加要同步的三处） |
| **F4** | F 守卫与惯例 | `backend/scripts/**` 的覆盖率缺口（`demo_bootstrap.py 0%` / `dump_openapi.py 45%`；**没有**为了好看补测试，并写清为什么它今天不影响可信度 + 若要抬怎么做） |
| **F5** | F | Plan 01 计划文档里那 24 处 `&&`（**部分顶回不改**，理由与「若要清的正确形状」） |

⚠️ §15 的引言处也**加**了一行「Task 15 又补 5 条 → 今天 21 条 / 6 组」的标注
（原文一个字未改）。

### D4 · `progress.md` 续上本波

**16 862 B / 234 行 → 24 960 B / 341 行**（全 LF、无 BOM、`attr/-text`，两口径相同）。
先 Grep 了它今天的体例（`### Task N —— **一句话**（commit）` + 四个项目符号
「做了什么 / 账面 / 顶回 / 报告」），照它续：

* Task 14 那一段「（本波之后的下一波，尚未做）」**原文照留** + 上面加一行引注标注已过期；
* 新增 **Task 14（实际做的那一波）** 与 **Task 15** 两节；
* §2 那张 Task 13 时点的表**一个字未改**；
* 末尾新增 **§3 🏁 Plan 06 全计划结案的总账**（每格自己实测）：
  collected **1340 → 1573**、smoke **499 → 655**、路由 **15 → 16**、表 **26 → 28**
  （`sqlite_master` 口径 **26 → 29**，含 `alembic_version`）、迁移链 **0 → 4 单头**
  （残差 diff **0**）、依赖 **+1**（后端 alembic / 前端 0）、顶回 **185 → 198**、
  另加三行本波才开始量的（全 `app/` **7300/201/1774/115/96%**、
  `scripts/**`+`static.py` **583/206/164/22/64%**、交付面活文档 **0 → README 60 行 + §13.15 11 条**）。

### D5 · §13.14.8 🏁 实施计划 06 全计划结案

先看前几个计划怎么写的：`Grep "🏁" Document/*.md` → **0 命中**；
`git log --all --grep="🏁"` → **1** 命中 = `a5f16b1`
「docs: Plan02 Task 9 结案 + 🏁 Plan 02 全计划结案 —— 793 → 807 passed，spec §14 30 → 37 行（Ruling 156/157）」。
⇒ 那个符号此前的住址是**结案 commit 的信息**，spec 里没有先例；本波照它的口径
**两处都用**（§13.14.8 的标题 + 本波第 ⑥ 个 commit 的信息），并在节首注明这一格来历。

内容三块：**①** 波次一览（13 波 + 终审 + 修复波；前 13 行**指回 §13.14.2 不抄第二遍**，
只补最后两行 + 顶回数）；**②** 计划 §10 五条的**结案对账**；**③** 今天的全部基线数字。

**② 的最终对账 —— 采信终审那一版（3 ✅ / 2 ⚠️），再按 B2 兑现改判第 1 条**：

| # | 终审判 | **结案时点** | 本波给的判断与理由 |
|---|---|---|---|
| 1 | ⚠️ 部分（前两句 ✅，后半句「新增模块自己的覆盖率单独报」13 波没兑现） | **✅** | **可以改判**：那半句本波**兑现了**（三个口径亲跑 + 18 个模块逐个报进 §13.14.7 与 §13.15 第 11 条）。⚠️ 两条约束：① §13.14.3 里 Task 13 时点的那个 ⚠️ **一个字没改**（账本不改写）；② 「13 波都没报」这一格**事实不因改判而消失**，故改判写在**结案时点**那张表里、并逐字注明「兑现的时点是最后一波」 |
| 2 | ✅ | **✅** | 产品档 **18/18 · 655/0 · 退出码 0**（本波亲跑；dev 档同数） |
| 3 | ✅ | **✅** | 四指纹 + 18 模板指纹现算相符、`pe.db` False、`data/seed/` 0、`git diff 127d3bf HEAD -- backend/data` **空** |
| 4 | ✅ | **✅** | `tests/test_dependencies.py` 一字不红；本波新增依赖 **0**（`AbortSignal.timeout` / `ast` / `configparser` 全是自带的） |
| 5 | ⚠️ 部分 | **⚠️ 部分** | 探针仍落在 `$env:TEMP\p06t15\` 并在收尾删净 ⇒ 可复核面是报告里的实测数字；变异测试**超额**（本波又做了 **11** 次） |

⇒ **4 ✅ / 1 ⚠️**。

---

## ⑥ 待清扫 / 关切 / 没按派单做的 / **顶回**

### 1) 顶回（**3 处 / 0 次 Critical**）⇒ 累计 **195 → 198**

| # | 顶回什么 | 理由与取证 |
|---|---|---|
| **1** | **C4**：派单要「加一条守卫钉住演示库那个迭代数 ≥ 下界」 | **那条守卫今天已经存在**（`tests/auth/test_passwords.py:637`，AST 读脚本 + 字面量钉下界），两次定点变异都红（`99_999` → 红在 :670；下界抬到 `200_000` → 红 9 条）。⇒ 不加重复守卫、不改下界。⚠️ 连带**顶回终审 S4-④ 的那半句**「本席**没有找到**任何守卫钉住『演示库那个值 ≥ `PBKDF2_MIN_VERIFY_ITERATIONS`』—— 如实记」：它与实物不符（那条测试的 docstring 甚至逐字预告了「把下界抬到 200 000 会当场红」） |
| **2** | **B6-②**：派单要「`Grep` 全部活文档……看还有没有别处给 PS 用户写了 `&&` → **一并修**」 | Plan 01 那 **24** 处 `Run:` 行**不修**：那份文档的**第 31 行**已逐字声明「所有 `Run:` 命令中出现的 `&&` 一律按 `;` 执行」⇒ 它们不是「给 PS 用户的假命令」；而改它们会让第 31 行那句声明失去指代对象（于是还得改它）—— 那是一份**绑时点**的历史计划文档（与 Plan 06 计划文档「一个字都不许改」同一条纪律）。⇒ 登记 **§15 F5**，逐个报清 |
| **3** | **B5 的错误态形状**：派单说「用既有的错误态组件/类（**`ApiErrorBanner.vue` 那一族**）」 | 落在**就地说明（`session.notice` → `.switcher__warn`）+ 一个复用既有 `.btn .btn--sm` 的「⟳ 刷新页面」按钮**，而**不是** `ApiErrorBanner`。理由：横幅只吃 `ApiError`，而超时那一档后端**一个字都没回**（抛的是 `DOMException`）；要合成一个 `ApiError` 就得 ① 往 `client.ts` 的 `ERROR_CODES` 加一个**前端独有**的 code（那一份逐字是「后端 `errors.py` 的 code 清单**镜像**」）② 往 `ApiErrorBanner` 的 `BRANCHES` 加一条（它的 docstring 逐字钉着「全部 **17** 个具名 code 都在表里」）③ 否则 `describeCode` 的兜底会印一句**假话**（「后端回了一个前端不认识的错误码」）。⇒ 三处新所有者 + 一句假话，换一个与就地说明同信息的横幅，不划算。⚠️ 派单要求的**实质**（「一个可读的错误态 + 一个刷新入口 + 用既有的组件/类 + 不新写 CSS 裸值 + `check:tokens` 不许退」）**逐格都满足了**：`check:tokens` 实测 **36 个文件（下界 25）全绿、退出码 0**、一行新 CSS 都没加 |

### 2) 没按派单做的（**2 处，都如实记**）

| # | 派单怎么说 | 本波怎么做 | 为什么 |
|---|---|---|---|
| **1** | 「建议 6 个 commit：… ⑤ D1–D4 …；⑥ D5 结案 + 本波报告」 | commit **⑤ 含 D1–D5 的 spec 部分**（§13.14.7 + §13.14.8 + §13.15 + §15 + `progress.md`），commit ⑥ 只有本报告 + spec 里那两个终值数字 | §13.14.7 / §13.14.8 / §13.15 是同一节区间里**连续的三块新增**，拆开会在 spec 里留下一个「§13.14.7 与 §13.15 之间空着一节」的中间态。⚠️ 与 Task 13 的 `127d3bf` 同一条先例（最后一个 commit 补上本波各 commit 的 sha 与 spec 终值） |
| **2** | 「commit ② = A1 + A2（两条 S2）；commit ③ = B 组（7 条 S3）」 | commit **② 同时带上了 B7 的 smoke 那一块** | B7 与 A1 的改动落在**同一个文件**（`smoke.mjs`）、共用同一批新机制（`uniqueNeedles`），拆成两个 commit 会留下一个半改的中间态。⚠️ B7 的**取证**仍写在 commit ③ 的信息里，代码在 ② —— 已在 ② 的 commit 信息与 §③-B7 两处注明 |

### 3) 待清扫（**3** 条，本波新登记的）

1. **`session → identity` 那座桥与 `'timed_out'` 的交互**：本波给 `SessionStatus` 加了第五档，
   而 `stores/identity.ts`（持久化的那一份）对超时**一无所知**（它只被 `adopt()` 写）。
   今天无害（超时那一支调 `forget()`，而 `forget()` 会 `clearIdentity()`），
   而它是 §15 **A1**（拆那座桥）那一波要一并处理的第三格。
2. **`demo.ps1` 那 8 条标注是「印出来给人看的」而不是可执行判据**：本波逐条真发请求实测过，
   而**没有**给它加守卫（要加就得让 smoke 或一个后端测试去 spawn 一次 `demo.ps1` 并解析
   它的打印 —— 第 17 步 ① 已经为另一件事付过一次 spawn 的墙钟，§13.11.4 记着那笔账）。
   ⚠️ 于是「将来某个端点的身份口径变了、而那段标注没跟着变」这一档**仍然静默**；
   它与 Task 13 修掉的那 2 条撒谎 URL 同族，只是本波把「实测一次」的成本付掉了。
3. **B5 的运行时那一档没有 smoke 守卫**：只有第 17 步 ⑧ 的 5 拍**源码结构面**。
   ⚠️ 刻意的（要给每一步加 10 s 墙钟），而代价是「有人把 `AbortSignal.timeout` 挪到
   一个不影响 `fetchMe` 的地方」这一档只有结构面那 5 拍挡着。若要补，正确的形状是
   一个**单独**的 npm script（例如 `smoke:timeout`），而不是塞进第 14 步。

### 4) 关切（**2** 条）

1. **`ResourceIndex.vue` 那两个写死的计数**（`ANONYMOUS_READABLE = 7` / `ANONYMOUS_GETS = 15`）
   是本波在**前端**引入的第一处「刻意第二所有者」。它有守卫（smoke 第 12 步 5 拍），
   而守卫跑在 smoke 里、不在 `vue-tsc` 里 ⇒ **只改后端 `read_scope` 而忘改前端**这一档
   要等到有人跑 smoke 才响。⚠️ 本波**没有**把它挪进 `catalog/resources.ts`
   （给 23 行各加一个 `readScope` 字段是一次跨 23 行 + 接口 + smoke 第 12 步的改动，
   与「9 行文案修复」不成比例）；若 Plan 07 要动前端目录，建议一并做掉。
2. **`is_reserved` 的第二趟比是「折小写之后比」**，而 HTTP 路径里可能出现
   percent-encoded 的大小写变体（`/%41pi/health`）。⚠️ 本波**实测过** `scope["path"]`
   是**已解码**的那一份（`resolve_static_path` 的 docstring 逐字交代了这一点），
   故 `/%41pi/health` 解码后就是 `/Api/health` ⇒ 已被新判据盖住；
   而**双重编码**（`%2541`）解码一次之后是字面的 `%41pi/health`，它既不是保留前缀、
   也不是真端点 ⇒ 照旧走 fallback 回 index.html。⚠️ 那一档与改前**逐字同形**
   （不是本波引入的回归），且失效方向是「回一份 200 的 HTML」而不是泄漏；
   如实记，不动。

---

## ⑦ 最终验收（全部本波亲测）

### 后端

| 格 | 基线（终审亲验） | **今天** |
|---|---|---|
| `pytest -q --cov=app/domain --cov-branch` | 1564 passed + 1 skipped / 304 s | **1572 passed, 1 skipped** / **346.10 s** |
| `pytest -q --cov=app --cov-branch` | 1564 + 1 / 322.90 s | **1572 passed, 1 skipped** / **376.37 s**（⚠️ 那一次跑出过 `1 failed, 1571 passed`，失败的是 C5 第一版 import alembic 撞的既有守卫，**已修**，修完 `tests/test_backup_restore.py` 21 passed） |
| collected | 1565 | **1573**（**+8** = A2 1 + B3 2 + B4 1 + C1 2 + C5 2） |
| `app/domain/` 覆盖率四格 | 1268 / 0 / 376 / 0 / **100%** | **1268 / 0 / 376 / 0 / 100%**（**一格未动**） |
| `--cov=app` TOTAL | 7295 / 201 / 1772 / 115 / 96% | **7300 / 201 / 1774 / 115 / 96%**（stmts +5 = C1 给 `static.py` 加的那几行；Miss **一格未增**） |
| `--cov=scripts`（+`app.static`）TOTAL | 531 / 200 / **62%** | **583 / 206 / 164 / 22 / 64%**（`restore.py` 110/17/80% → **157/23/82%**） |
| 表数（`/api/health` 口径 / `sqlite_master`） | 28 / 29 | **28 / 29** |
| 迁移链 | 4 单头（`53e5a548c40e → 0b7da3d20211 → 7f3923d8af84 → 0ac943e0da9b`） | **4 单头，逐字相同**（`ScriptDirectory.get_heads() == ['0ac943e0da9b']`，`len == 1`，链长 **4**） |
| 模型 ↔ 迁移残差 diff | 0 operation | **0 operation**（在 `$env:TEMP\p06t15\_residual.db` 上 `upgrade head` + `compare_metadata`，跑完删掉并复验 `True`） |
| openapi 五格 | 74 / 102 / 84 / 63（15 匿名 + 48）/ 3 | **74 / 102 / 84 / 63（15 匿名 + 48）/ 3**（**一格未变** ⇒ `gen:api` 确实不需要重跑） |
| catch-all 漏进 `paths` | 0 | **0** |
| 未定型响应 | 24 | **24** |
| 扫描面 | 72（10+14+18+26+4） | 相关守卫**一条都没红**（全量 1572 passed 蕴含）；本波另量到 `check:tokens` **36**（下界 25）、`check:dist` **25** 产物 |
| `_MODELS_PUBLIC_BASELINE` / `_MODELS_SUBMODULES` / 黄金用例 | 33 / 8 / 14 | **33 / 8 / 14**（`tests/db/test_models.py` + `tests/integration/test_golden_cases.py` = **66 passed**） |
| 依赖清单守卫 | 一字不红 | `tests/test_dependencies.py` + `tests/architecture` = **19 passed / exit 0** |

### 前端

| 格 | 基线 | **今天** |
|---|---|---|
| `npm run build` | 退出码 0 | 退出码 **0**（含 `vue-tsc -b`） |
| 产物哈希 | `index-v1XDnUhk.css` / `index-BCWjM00F.js` / `StudentDetail-BQenvJ7d.js` / `AuditLogList-DmETt2XK.js` | **`index-ah7DZvEq.css`（65.20 kB）/ `index-DBx0Mneu.js`（169.54 kB）/ `StudentDetail-Cf1DShvQ.js` / `AuditLogList-BNxWsd2d.js` / `ResourceIndex-DqalY3wm.js`** |
| `check:tokens` | 绿（36 / 下界 25） | **绿（36 个文件 / 下界 25）· 退出码 0**（「tokens.css 之外一个色值字面量都没有」） |
| `check:dist` | 绿（25 产物 / 780 131 字符） | **绿（25 个产物 / 784 248 字符）· 退出码 0**（`adoptFromUrl` 0 次、两个字体 CDN 各 0 次） |
| 新增依赖 | 0 | **0**（`npm install` 实测 `up to date, audited 93 packages`，`package.json` 与 `package-lock.json` **一格未变**） |
| 路由 | 16 条（`routes` 数组 20） | **16 / 20**（逐字未变） |
| **smoke dev 档**（后端 8000 + vite **5174**） | 18 步 / 637 断言 / 退出码 0 | **18/18 步 · 655 绿 / 0 红 · 退出码 0**（第 12 步 124→**129**、第 14 步 136→**144**、第 17 步 59→**64**；+18） |
| **smoke 产品档**（`serve.ps1 -Port 8020 -SkipBuild`，同源） | 18 步 / 637 断言 / 退出码 0 | **18/18 步 · 655 绿 / 0 红 · 退出码 0** |

### 禁区与收尾

| 格 | 实测 |
|---|---|
| 四个数据指纹（现算 sha256[:16] 大写） | `national_standard_2014.csv` = **`D2C8E539E2FA0029`** ✅ / `exercises.yaml` = **`5394B37F01DAC9AC`** ✅ / `exercise_equivalence.yaml` = **`822CB86A5E998301`** ✅ / `alert_rules.yaml` = **`E48E3AC82BB45BB7`** ✅（**4/4 逐字相符**） |
| 18 个模板指纹 | `backend/data/prescription/*.yaml` = **18** 个；指纹守卫（`-k fingerprint`）**3 passed**，且全量 1572 passed 蕴含它们一条都没红 |
| `git ls-files backend/data` | **24** 个文件（与基线逐字相同） |
| `git diff 127d3bf HEAD -- backend/data` | **空** |
| `git status --porcelain -- backend/data` | **空** |
| `backend/pe.db` | **不存在**（`Test-Path` = False） |
| `backend/data/seed/` | **0 文件**（`-Recurse` 口径） |
| `frontend/dist` / `backend/backups` 入库 | `git ls-files frontend/dist backend/backups` = **空**（都没入库） |
| 三个禁跑 CLI（`app.seed.generate` / `backfill` / `daily`） | **一次都没跑**（要数据一律 `demo.ps1`） |
| 本波起的进程 | 见下面那一段收尾复验 |
| `$env:TEMP\p06t15\` 与 `pe_demo_csv_*` | 见下面那一段收尾复验 |

### 区间与账

| 格 | 值 |
|---|---|
| Plan 06 全区间 | `5131c12..HEAD` = **56** 个 commit（⚠️ **含** `5131c12` 自己那一个则是 **57**，与 §13.14.2 把「计划入库 `5131c12`（1）」算作第一波同一条口径；两个数差的就是区间端点自己） |
| 累计 diff（`git diff --shortstat 5131c12 HEAD`） | 到 commit ⑤ `197368f` = **111 files / +41 081 / −1 198**；到 commit ⑥（本 commit）= **112 files / +42 206 / −1 198**。⚠️ commit ⑥ 自己的 `--stat` 是「2 files / +1 127 / −2」，而端点到端点只多了 **+1 125 / −0**（= 本报告的行数） —— 它改掉的那一行正是 commit ⑤ **新加**的，两个端点一比就并成一行。⇒ 累计数一律以 `git diff --shortstat 5131c12 HEAD` **现算**为准，**不要把逐 commit 的增量相加**（本波第一次写这两个数时就是相加的，多算了 1 个 `+` 与 1 个 `−`，当场实测发现并改掉） |
| 本波（`127d3bf..HEAD`） | 到 commit ⑤ = **5** 个 commit / **18 files / +2 644 / −44**；到 commit ⑥ = **6** 个 commit / **19 files / +3 769 / −44**（同一条并账效应，实测） |
| 终审报告的区间（复核） | `5131c12..127d3bf` = **50**（`git rev-list --count`）/ **51**（含端点）⇒ 终审报的 51 是**含端点**口径，与 §13.14.2 一致，**不是错** |
| 顶回累计 | 185 → 195（Task 13）→ **198**（本波 +3 / 0 次 Critical） |

### 收尾复验（本波起的进程 / `$env:TEMP` / 那些「一个字都不许改」的东西）

| 格 | 实测 |
|---|---|
| 本波起过的 5 类服务 | **全部停掉**。`Get-NetTCPConnection -State Listen` 在 **8000 / 8001 / 8020 / 5174** 上命中 **0** 个监听 |
| ⚠️ 5173 上那个**别人的** vite | **一个字节都没碰**：收尾复验时它**仍在**（`LocalPort 5173 / OwningProcess **20240**`，与开工时**同一个 PID**）—— 它还在，正是「没去动它」的证据 |
| 演示库重灌 | 收尾又真跑了一次 `demo.ps1 -Port 8000`（`[1/7]` → `[7/7]` 全部走完、十三个行数逐个印出、「禁区复核：`backend\pe.db` 不存在、`backend\data\seed\` 仍为 0 文件 ✓」），起服务之后停掉 ⇒ `backend/pe_demo.db` **1 589 248 B** / sha256[:16] `8593924853855627`（⚠️ 它在 `.gitignore` 里，`git status --short --ignored` 显示 `!!`，**不入库**） |
| ⚠️ 顺手量到 `demo.ps1` 的两条**调用姿势**（不是脚本的缺陷，是调用方的坑 ⇒ 本波**没改**脚本） | ① `-DryRun` **不写** `backend/pe_demo.db`：库与 CSV 都落到 `$env:TEMP\pe_demo_dryrun_<pid>\`（脚本自己印的那一句：「`-DryRun`：库与 CSV 都落在 …（跑完删掉，`backend/` 下不留文件）」）⇒ 想**重灌演示库**必须用不带 `-DryRun` 的那一发；② 把它的输出接进 `2>&1 \| …` 会让 PowerShell 把 alembic 打在 **stderr** 上的 `INFO [alembic.runtime.migration]` 当成**终止性错误**（脚本第 63 行是 `$ErrorActionPreference = "Stop"`）⇒ 退出码 **1** 而数据只灌到一半。直接跑（不接管道）就正常 —— 本波唯一接了管道的那一发（就是那 1 次 `-DryRun` 试跑）正是这么挂的；那 **4** 次重灌都是直接跑的 |
| `$env:TEMP` 清扫（`pe_demo*`） | 删掉 **7** 个目录：`pe_demo_csv_22604 / 27892 / 30896 / 42408 / 6780 / 7336` + 一次 `-DryRun` 中断留下的 `pe_demo_dryrun_34768`；删完复验 `Get-ChildItem $env:TEMP -Filter "pe_demo*"` = **0** |
| `$env:TEMP\p06t15\`（本波探针 **64** 个文件 + 一个 `__pycache__\`） | ⚠️ 它是**写这份报告的那些探针**（共用的 `editlib.py` + 各条发现的取证/变异脚本），删掉就没法再改本报告 ⇒ 顺序上**必然**落在最后一个 commit 之后。本 commit 之后立刻 `Remove-Item -Recurse -Force` 并复验「存在? **False**」，复验结果写在交回里 |
| **计划文档一个字未改** | `Document/2026-10-13-实施计划06-产品级硬化.md` 最后一次被碰是 **`5131c12`**（它自己入库那一次，`git log -1 -- <它>`）；实测 **8 574 B / 85 行 / CRLF 85 / 裸 LF 0 / 无 BOM** / sha256[:16] `dff004a6c0ccc3c7`，`git ls-files --eol` = `i/lf w/crlf attr/text eol=crlf` |
| **11 份历史波报告一份未改** | `git diff --name-only 127d3bf HEAD` 在那个目录里只有 **3** 个名字：`progress.md`（D4 续账，派单点名要的）/ `task-14-review.md`（D1 原样入库）/ `task-15-report.md`（本文件）⇒ 另外 **11** 份 `task-*-report.md` **一个都不在里面** |
| `Document/` 下只动了 spec | `git diff --name-only 127d3bf HEAD -- Document/` = **只有** spec 那一个名字 |
| 最后一轮定点复跑 | `pytest tests/test_refdata.py tests/test_refdata_alerts.py tests/test_config.py tests/auth/test_passwords.py tests/test_backup_restore.py tests/test_serve.py tests/api/test_column_widths.py tests/api/test_crud.py tests/api/test_dashboard.py -q` → **247 passed / 0 failed / 退出码 0**（30.99 s）。⚠️ 这一轮是**故意挑的**：它同时盖住「四个数据指纹 + 18 套模板指纹」那几条守卫、C4 顶回时引的那条（`tests/auth/test_passwords.py:637`）、以及本波改过的 **5** 个后端测试文件 |
| 工作树 | `git status --short` = **空**；`git status --short --ignored` 只有 `!! backend/pe_demo.db` 与 `!! frontend/dist/` 两条（`backend/backups/` 本波没产生过文件，故不在里面） |
| 本波 **6** 个 commit | `031c641`（终审报告原样入库）/ `cd485c3`（A 组两条 S2 + B7 的 smoke 块）/ `f1ef2be`（B 组 7 条 S3）/ `02aca1f`（C 组 5 条 S4）/ `197368f`（D1–D5 的 spec 与账本）/ **本 commit**（本报告 + spec 那两行终值） |

---

## ⑧ 行尾复核（逐个被改文件，两个口径）

⚠️ 本机 `core.autocrlf=true`。口径：spec 与 `Document/**/*.md` = **CRLF**、
`.ps1` = **CRLF + BOM**、py/ts/mjs/vue 入库 blob = **LF**、`.superpowers/**` = **LF**（`-text`）。
⚠️ 全部编辑走 **Python 二进制模式**（一个共用的 `editlib`：读字节 → 判 EOL/BOM →
按 `\n` 归一后做**恰好一次**的替换 → 按原 EOL/BOM 写回；替换数不为 1 就当场 `SystemExit`），
**每改完一个文件当场核** `git ls-files --eol`。

| 文件 | `git ls-files --eol` | 工作树 | 入库 blob | BOM |
|---|---|---|---|---|
| `.superpowers/…/task-14-review.md` | `i/lf w/lf attr/-text` | 126 925 B / LF | **126 925 B**（`git cat-file -s` 实测，与工作树逐字相同） | 无 |
| `.superpowers/…/progress.md` | `i/lf w/lf attr/-text` | 24 960 B / LF | **24 960 B** | 无 |
| `.superpowers/…/task-15-report.md`（本文件） | `i/lf w/lf attr/-text` | **1 125 行 / 全 LF（裸 LF 1125、CR 0）** —— ⚠️ 它自己的**字节数与 sha256 是自指的、写不进它自己**（改一次就变一次），故那两个数落在本 commit 的信息里与交回里 | **与工作树逐字相同**（`git cat-file -s` 实测） | 无 |
| `Document/2026-09-28-体育闭环原型-设计spec.md` | `i/lf w/crlf attr/text eol=crlf` | **522 729 B / 4 868 行 / CRLF 4868 / 裸 LF 0** / sha256[:16] `c7fb8050332b4536`（⚠️ commit ⑤ 时是 521 996 B / `a9b9869cf5d0b18c`，差的 733 B 就是 commit ⑥ 补的那两行终值） | **517 861 B**（LF，= 工作树 − CRLF 数） | 无 |
| `README.md`（**新文件**） | `i/lf w/crlf attr/`（⚠️ `attr/` 为空 = 根目录 `.md` **无钉扎**） | **2 864 B / 60 行 / CRLF** / sha256[:16] `26acb1e8e2cca67f` | **2 804 B**（LF） | 无 |
| `backend/scripts/demo.ps1` | `i/lf w/crlf attr/text eol=crlf` | 25 480 B / CRLF | LF | **有**（实测 True） |
| `backend/scripts/restore.py` | `i/lf w/crlf attr/` | 28 626 B / CRLF | LF | 无 |
| `backend/app/static.py` | `i/lf w/crlf attr/` | 35 407 B / CRLF | LF | 无 |
| `backend/app/api/deps.py` | `i/lf w/crlf attr/` | 77 739 B / CRLF | LF | 无 |
| `backend/tests/api/test_column_widths.py` | `i/lf w/crlf attr/` | 63 564 B / CRLF | LF | 无 |
| `backend/tests/api/test_crud.py` | `i/lf w/crlf attr/` | 251 234 B / CRLF | LF | 无 |
| `backend/tests/api/test_dashboard.py` | `i/lf w/crlf attr/` | 120 670 B / CRLF | LF | 无 |
| `backend/tests/test_serve.py` | `i/lf w/crlf attr/` | 92 527 B / CRLF | LF | 无 |
| `backend/tests/test_backup_restore.py` | `i/lf w/crlf attr/` | 65 914 B / CRLF | LF | 无 |
| `frontend/scripts/smoke.mjs` | `i/lf w/crlf attr/` | 314 768 B / CRLF | LF | 无 |
| `frontend/src/views/admin/ResourceIndex.vue` | `i/lf w/crlf attr/` | 17 760 B / CRLF | LF | 无 |
| `frontend/src/api/auth.ts` | `i/lf w/crlf attr/` | 12 762 B / CRLF | LF | 无 |
| `frontend/src/stores/session.ts` | `i/lf w/crlf attr/` | 24 187 B / CRLF | LF | 无 |
| `frontend/src/components/IdentitySwitcher.vue` | `i/lf w/crlf attr/` | 22 824 B / CRLF | LF | 无 |

⚠️ **`.gitattributes` 一条都没碰**（禁碰项）；⚠️ `frontend/src/views/admin/AuditLogList.vue`
被 B7 的定点变异改过一次，**已逐字节还原**（sha256[:16] `238345d1fb910b16`），
`git status` 对它为空 ⇒ 不在上表里。

⚠️ **`gen:api` 本波一次都没跑**（openapi 五格逐格未变、一个进 openapi 的 docstring 都没改），
故 `schema.d.ts` 的行尾**不需要复核**；⚠️ 而派单点名要本波自己实测一遍
「Task 13 顶回过说『blob 本来就 LF、`git diff` 为空 ⇒ 不需要还原』」那一格 ——
本波**没有重跑 `gen:api`**（跑了就会改一个与本波无关的产物），故**复核方式是查现状**：
`git ls-files --eol -- frontend/src/api/generated/schema.d.ts` = `i/lf w/crlf attr/`，
`git status` 对它为空 ⇒ **今天工作树是 CRLF、blob 是 LF、`git diff` 为空**，
与 Task 13 的结论一致（两个口径都要报，而「入库」这一侧不需要手工还原）。

---

## ⑨ 🏁 全计划结案的自评

### 做得好的（**不是运气**）

1. **「期望侧与被测侧不同源」这一条纪律在本波结出了第三次果实**。A1 的两个写死计数
   由 smoke 从 `/openapi.json` 现量来对拍、B4 的 CHECK 由「模型元数据 vs 迁移写出的 DDL」
   两面各钉一次、B7 的九列由「DOM vs 后端响应体的键顺序」交叉验证 —— 三处都不是
   「读回来跟自己比」，故三处都能真响（B7 的变异实测 **3 红**、B4 的变异实测红、
   A1 的变异实测 **2 红**）。
2. **A2 那一族「自指守卫」的自查做全了**（18 处逐个判定，真洞 1 族 3 住址），
   而不是只修终审点名的那一处。⚠️ 而它同时暴露了一条元规律：
   **凡是被测模块自己声明的「形状类」常量（标记、哨兵、词表），期望侧只能用字面量钉**；
   本仓今天有三处这样的字面量拍（`SESSION_TTL` / `PBKDF2_MIN_VERIFY_ITERATIONS` /
   `OVERLONG_SUFFIX`），第四处候选是 `overlong_sentinel` 的 `<over:N>` 形状
   （本波**核过**：它的期望侧写的是 `f"<over:{OVERLONG}>"`，是字面量拼出来的 ⇒ 不是洞）。
3. **B5 先取证再改**，而取证用的是终审指出的那一招（只扣 `/api/auth/me`、不拖慢全网）。
   ⚠️ 改后那一次取证里「浏览器报 `Invalid InterceptionId`」反而是第三份证据
   （前端真的 abort 了那一次 fetch）—— 一个没预料到的旁证。
4. **B3 走了强选项**（造夹具）而不是弱选项（AST 守卫），因为实测成本成比例
   （既有 `_seed` 已经把需要的行都给全了）。⚠️ 而它顺手把 `deps.py` 里一句
   **已经过期的自述**改对了 —— 那一格比新增的两条测试更值钱（下一个人不会再
   照着「本仓今天没有那样的夹具」去绕路）。
5. **C5 撞了既有守卫之后改自己、不改守卫**。那条守卫（「救急脚本不拖 ORM 依赖链」）
   是有立意的，而第一版实现违背了它；改成纯标准库之后**覆盖率还从 80% 抬到 82%**
   （因为新增的两条守卫把新代码跑到了）。

### 是运气的（**不该记成功劳**）

1. **C4 那条守卫恰好已经存在**。本波是「查到它存在」而不是「想到要加它」——
   终审席没查到（它逐字写了「本席没有找到」），本波查到了，差别只在于
   **谁先去 `tests/auth/test_passwords.py` 里搜了一遍 `MIN_VERIFY`**。
   ⚠️ 这暴露一格流程问题：**「加一条守卫」之前应当先搜一遍同族守卫**，
   而本仓今天没有任何机制强制这一步（派单也没有）。
2. **`/API/health` 那一格今天没有造成任何真实损害**。它是「一个打错的探针会永远绿」，
   而甲方现场今天还没有探针 ⇒ 修它的收益是**将来**的，本波无法证明「不修会出事」。
3. **smoke 的 655 断言里有 18 条是本波加的**，而本波**没有**对它们做「反例对照」
   （终审的 S10 那一格也没做完）：只有 A1 与 B7 各做了一次定点变异。
   ⚠️ 于是「本波新加的 18 条里有没有恒绿的」这一格，证据是**2 次变异**（都红了）
   + 每条都带反空转拍，而不是 18 次变异。如实记。

### 留给 Plan 07 的最大三格风险

1. **§13.15 第 4 条（教职全读名册 + 可抢绑未绑定账号）**。它是 §1.2 第 4 条**已登记**的
   残余、不是 Plan 06 引入的，而它是今天**唯一**一格「一个合法账号能拿到不属于自己的
   隐私、并据此接管另一个账号」的形状。⚠️ 本波**完整跑通**了它（匿名 bind **204** →
   login **200**），故它不是理论风险。生产处置必须换掉**验身材料**
   （一次性绑定链接 / 校园卡后台校验），而那不是加一道闸门能解决的。
2. **`session → identity` 那座桥（§15 A1）+ 本波新加的第五档状态**。本波给
   `SessionStatus` 加了 `'timed_out'`，而 `stores/identity.ts`（**持久化**的那一份）
   对它一无所知；今天无害（超时那一支调 `forget()` → `clearIdentity()`），
   而它是那座桥上的**第三格**耦合。⚠️ 拆桥那一波要一并处理，且它是 17 个文件的改动。
3. **`backend/scripts/**` 的覆盖率与「换后端」那一格（§15 F4 + C3 + 迁移 4 的 `downgrade`）**。
   `demo_bootstrap.py` **0%**（145 行）而它是「演示库怎么来的」的唯一所有者；
   而一旦甲方要换 PostgreSQL，今天有**三处**会同时响（CSV 摄取路径的字段长度无校验、
   迁移 4 的 `downgrade` 是 SQLite 专用姿势、`width.py` 那三档处置的语义在 MySQL
   非严格模式下会变成静默截断）。⚠️ 三处**都已在 §15 登记**，而它们是 Plan 07
   唯一一组「不动就会在换后端那天同时炸」的东西。

### 一句话总判断

**这个仓库今天能交给甲方** —— 终审判定的唯一交付阻塞项（S2-①）已修好并被守卫钉住，
其余 13 条各有处置（修 11 / 不修 3，三条都有理由与台账），计划 §10 五条是
**4 ✅ / 1 ⚠️**，两档 smoke **655/655 · 退出码 0**、后端 **1572 passed + 1 skipped**、
禁区四格全清。⚠️ 而交付那一天**必须把 §13.15 那 11 条念给甲方听** ——
尤其第 **1** 条（产品档缺省是 dev 档）与第 **4** 条（教职全读名册 + 可抢绑）。

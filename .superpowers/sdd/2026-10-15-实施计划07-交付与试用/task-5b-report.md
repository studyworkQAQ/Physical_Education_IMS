# Plan 07 · Task 5b —— 甲方试用路线上的两个缺陷（计划外的缺陷修复波）· 实现者报告

- 分支：`p07/trial-defects`（从 `main` = `42031de` 起）
- 交付的 commit：`b86645d` → `21b55b7` → `41b7b91` → `553abcd` →（本 commit：spec §13.18 + 本报告）
- ⚠️ 口径：**甲方此刻正拿着一条公网链接在试用**。本波**一个控制器进程都没碰**：
  8030 那个 uvicorn（PID 21128）与 cloudflared 隧道（PID 10128）从头到尾在跑，
  `backend/pe_trial.db` 一个字节都没写，`frontend/dist` 一个字节都没动，
  **`npm run build` 一次都没跑**。

---

## ① 环境 + 开工/收尾三格取证

### 1.1 环境（硬规矩 #73：开工第一件事）

```
$ node --version; python --version
v24.19.0
Python 3.11.1
```

| 格 | 实测 |
|---|---|
| 仓库根 | `c:\Users\whwenhao\Desktop\Physical_Education_ims` |
| 开工时所在分支 / HEAD | `p07/trial-guide` / `65c5885`（工作树干净） |
| 本波分支 | `p07/trial-defects`，从 `main` = **`42031de`** 起（`git checkout -b p07/trial-defects main`） |
| Node / npm / Python | v24.19.0 / 11.17.0 / 3.11.1（无 venv） |
| 局域网 IPv4 | `192.168.31.11`（`Get-NetIPAddress` 现场数，与本波无关，只记一格） |

⚠️ 建分支时工作树从 `p07/trial-guide` 切到 `main`，故 `Document/2026-10-15-甲方试用说明书.md`
**从工作树里消失了**（它只在 `p07/trial-guide` 上）。本波**一次都没写它**；
需要读它时用 `git show p07/trial-guide:Document/…` 读（§8 那几处要改的原文就是这么取的）。

### 1.2 开工三格（第一件量的事）

| 格 | 开工实测 | 收尾复核 | 逐字未变？ |
|---|---|---|---|
| 8030 的 listener PID | **21128**（`python`，起于 2026-10-15 19:43:27，`127.0.0.1:8030`） | **21128**（同一格复查） | ✓ |
| 隧道 PID | **10128**（`cloudflared`，起于 19:43:48） | **10128** 仍在 | ✓ |
| `backend/pe_trial.db` | **1 589 248 B** / sha256[:16] **`40D7B5F78A7C36CB`** | **1 589 248 B** / **`40D7B5F78A7C36CB`** | ✓ 逐字相同 |
| `.trial\public-url.txt` | 在（1 472 B），`url = https://podcasts-mitchell-donald-americas.trycloudflare.com` | 仍在 | ✓ |

⚠️ 量 `pe_trial.db` 的 sha 时踩到一格，如实记：`Get-FileHash` 读不动它
（`The process cannot access the file … because it is being used by another process`，
一个 `FileReadError`；而本波第一句就是 `$ErrorActionPreference` 的缺省 Stop，
于是它停在那段 PowerShell 原文上）。改用 `python -c "open(...,'rb').read()"` 就读到了
—— SQLite 给的是 `FILE_SHARE_READ|WRITE`，Python 的 `open` 吃得下、`Get-FileHash` 不吃。
⚠️ 这正是 `scripts/trial.ps1` ② a 那段注释里逐字记过的同一格（它因此把占用检测
排在 `Get-FileHash` **之前**）。

⚠️ **本波对 8030 与公网 URL 只发过匿名的 `GET /api/health`**（两遍各 5 次，共 10 次，
为量关切 ③ 的隧道往返）。它**不写库、不留审计**（`audit_log` 的 `should_record` 只认 POST），
`scripts/tunnel.ps1` 写 `public-url.txt` 之前也发过同一个请求。
⚠️ **一次都没登录过 8030**、一次都没打任何要身份的端点。上表那个 sha 逐字相同就是它的对账。

### 1.3 本波自己起的进程（收尾全停，见 §7.9）

| 用途 | 端口 | 姿势 |
|---|---|---|
| dev 档后端 | 8000 | `backend\scripts\demo.ps1 -Port 8000`（灌 `backend/pe_demo.db`）；后期改由驱动脚本用 `demo_bootstrap.py` + `python -m uvicorn app.main:app` 起（同一个生成器、同一个 import 串） |
| dev 档前端 | 5174 | `npm run dev -- --port 5174 --strictPort`（`PE_API_TARGET=http://127.0.0.1:8000`） |
| 产品档 | 8020 | `python -m uvicorn serve_app:app --app-dir backend\scripts` + `PE_STATIC_DIST=$env:TEMP\p07t5b\dist` |
| 试用档 | 8041 | 同上 + `PE_TRIAL=1` + `PE_DB_URL` 指到 `$env:TEMP\p07t5b\pe_t5b.db` |

⚠️⚠️ **产品档与试用档刻意没有跑 `scripts/serve.ps1` / `scripts/trial.ps1`**：
那两个脚本的 ② 那一步会判「源面 mtime vs `dist\index.html` 构建戳」，源面新就
**自己跑一次 `npm run build`** —— 而 `vite build` 会先清空 `frontend/dist`，
那正是 8030 在发给甲方的产物（几秒的 404 窗口）。故本波：

1. 把产物构建到**仓库外**：`npx vite build --outDir "$env:TEMP\p07t5b\dist" --emptyOutDir`
   （⚠️ `frontend/dist` 一个字节都没动 —— 收尾复核它 28 个文件的哈希与本波开工时
   派单里写的那五个逐字相同，见 §7.6）；
2. 用 `serve_app:app` + `PE_STATIC_DIST` **自己**起 uvicorn —— 与 `serve.ps1` 的 ③ 那一步
   **逐字同一个入口**（`serve_app.py` 只认那一个环境变量），只是把「产物在哪」换成本波自己那一份；
3. 试用档另设 `PE_TRIAL=1` + 一个**自己灌的**临时库 ⇒ `backend/pe_trial.db` 不写。

⚠️ 5173 上那个不是任何人起的 vite（PID 20240）**一次都没碰**（收尾复核仍在）。

### 1.4 `backend/pe_demo.db`（本波反复重灌的那一份）

| 时刻 | 字节 | sha256[:16] |
|---|---|---|
| 开工时（21:13:05，控制者那一次留下的） | 1 597 440 | `588FCA0D221393A8` |
| 本波重灌 **7 次**（每次 smoke / 每格变异之前各一次） | 1 589 248 | 逐次不同（提交时刻是真实时钟） |

⚠️ 它已进 `.gitignore`（`.gitignore:42`），且**不是**甲方在用的那一份。
smoke 的纪律本来就是「跑之前先重灌演示库」（`package.json` 的 `//` 那一格逐字写着），
故重灌是**要求**、不是副作用。

---

## ② 缺陷 ①（Critical）：「每日打卡」提交不出去且**无任何提示**

### 2.1 改前的运行时取证（先复现，再修）

真鼠标点击（CDP `Input.dispatchMouseEvent`）+ `Network` 域全程记录，dev 档，
学生 #4（`2023120001` 赵锦程），`/s/check-in?date=2025-10-12`：

```
—— 点击之前，表单的真值 ——
{"stepAttr":"0.5","stepProp":"0.5","durValue":"30.9","durStepMismatch":true,
 "durValidationMessage":"请输入一个有效的值。最接近的两个有效值为 30.5 和 31。",
 "formCheckValidity":false,"formNoValidate":false,"invalidCount":1,
 "invalid":[{"name":"duration_min","type":"number","value":"30.9",
             "msg":"请输入一个有效的值。最接近的两个有效值为 30.5 和 31。"}],
 "logDate":"2025-10-12","isRestDay":true}

提交按钮 = {"x":133,"y":653.7,"w":94,"h":37.5,"text":"提交打卡","disabled":false}
已用 Input.dispatchMouseEvent 真点了一次「提交打卡」

—— 点击之后的实测 ——
POST /api/training-logs 的次数（点击前 0 → 点击后 0）：0
这一屏一共打了 11 个 /api 请求（点击前 11）：
  GET /api/auth/me → 200            GET /api/health → 200
  GET /api/students/4/home?as_of=2025-10-12 → 200
  GET /api/students/4/training-logs/completion-rate?semester_id=2&week=6 → 200
  GET /api/students/4/weekly-sheet?as_of=2025-10-12 → 200
  GET /api/training-logs?limit=200&offset=0 → 200

—— 页面上此刻可见的反馈 ——
{"successMark":[],"banner":[],"anyAlertRole":[],"formValidityNow":false,
 "notices":["这一天已经有一行了 …（这一条在点击之前就在，是 alreadyLogged 那一格）"]}
activeElement = duration_min
```

⇒ **逐格复现了派单点的那一格**：一个请求都没发、页面上一个字都没多，
唯一的痕迹是浏览器把焦点挪到了那一格（而它那个原生气泡在 DOM 里留不下任何痕迹）。

### 2.2 领域口径的实测（`duration_min` 到底该有几位小数 / 什么步长）

| 格 | 实测 | 住址 |
|---|---|---|
| 后端请求体 schema | `duration_min: float \| None = Field(default=None, ge=0)` —— 只有下界，**没有** `multiple_of`、**没有** `le` | `backend/app/api/schemas/feedback.py:497` |
| openapi | `"duration_min": {"anyOf":[{"type":"number","minimum":0.0},{"type":"null"}],"title":"Duration Min"}`；`TrainingLogCreate` 五个属性里 `multipleOf` **一个都没有** | 进程内 dump（`scripts/dump_openapi.py`） |
| DB 列 | `sa.Column('duration_min', sa.Float(), nullable=True)`，**无 CHECK** | `migrations/versions/53e5a548c40e_baseline.py:421` |
| spec §4.5 / §8.1 | 逐字只有「完成时长分钟」/「完成时长（分钟）」，**没有任何步长或小数位约束** | spec:341 / spec:767 |
| 后端**实发**请求（打本波自己起的 8000，⚠️ 不是 8030） | `30.9` → **201**；`30.95` → **201**；`31` → **201**；`0.1` → **201**；`0` → **201**；`1e6` → **201**；`null` → **201**；`-1` → **422** `request_validation_failed`，`detail[0] = {"type":"greater_than_equal","loc":["body","duration_min"],"ctx":{"ge":0.0}}` | 探针 `p03_backend.py` |
| 仿真数据的生成式 | `duration = round(float(rng.uniform(20.0, 60.0)), 1)` ⇒ **一位小数** | `backend/app/demo_data.py:365` |

⚠️ 派单里写的是「`demo_bootstrap.py` 生成 `duration_min` 的精度」——实测那一段生成码住在
**`backend/app/demo_data.py`**（`build_demo_feedback`），`backend/scripts/demo_bootstrap.py`
只是它的 CLI 入口（`[4/7] build_demo_feedback(as_of=2025-10-12)` 那一步）。两者都**一个字没改**。

### 2.3 库里 `duration_min` 的真实精度（840 行逐个量）

```
库 = backend\pe_demo.db
training_log 总行数 = 840   duration_min 非空 = 628   NULL = 212
distinct 小数位数分布：  0 位小数 : 63 行      1 位小数 : 565 行
distinct 值个数 = 327   min = 20.1   max = 60.0
前 12 个真值：20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7, 20.8, 20.9, 21.0, 21.1, 21.2
不是 0.5 的整数倍的 distinct 值 = 258 / 327
不是 0.1 的整数倍的 distinct 值 =   0 / 327

学生 4 在业务日那一周（2025-10-06 … 2025-10-12）的行：
   ('2025-10-06', completed=1, 23.0)   ('2025-10-07', 1, 37.0)   ('2025-10-08', 1, 38.7)
   ('2025-10-09', 1, 20.1)             ('2025-10-10', 1, 26.5)   ('2025-10-11', 0, None)
   ('2025-10-12', 1, 30.9)   ← 派单点的那一格，逐字复现
```

⇒ **6 个非空值里 4 个不是 0.5 的整数倍**（38.7 / 20.1 / 26.5 / 30.9）。
而 14 天 × 60 人都是同一族 ⇒ **任何学生选任何一天都大概率撞上**，与派单的判断一致。

### 2.4 全部 16 条路由里带 `step` 的 numeric input（逐个判，不只看派单点的那一格）

**机器口径**：`Grep 'type="number"'` 在 `frontend/src/**` 上**恰好 2 处**；
`Grep 'step='` **恰好 1 处**。全仓 `<form` **6 张**。逐个判：

| # | 页面 / 路由 | 字段 | `type` | `step` | 其它原生约束 | 预填来源 | 库里真值举例 | 会不会撞 | 处置 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `/s/check-in`（`student/CheckIn.vue`） | `duration_min` | `number` | **`0.5`** | `min="0"` | 一个 `watch`：选中那一天若库里已有行，就 `durationText = String(existing.duration_min)` | `30.9`（学生 4 / 2025-10-12） | **会**（实测 `stepMismatch=true`） | 改成 `step="any"` |
| 2 | `/s/check-in` 同一张表单 | `log_date` | `date` | — | `required` | `?date=` 或业务日 | — | 会（清空 ⇒ `valueMissing`，同样静默） | 接上共用处置 |
| 3 | `/t/report`（`teacher/ClassReport.vue`） | `weekInput` | `number` | **无**（缺省 1） | `min="1"` | `?week=`（`Number.isInteger` 过滤过）/ `pickWeek`（恒整数或空串） | — | **不会**：① 它**不在任何 `<form>` 里**（在一个 `<label>` 里），故拦不下任何 submit；② 值恒整数，`min=1` 只挡 0 与负数，而 `pickWeek` 已经把不合格的值折成 `null` | 不动 |
| 4 | `/login`（`auth/Login.vue`） | `login-name` / `login-password` | `text` / `password` | — | 2 × `required` | 空（`?login=` 可预填登录名） | — | **会**：留空点「登录」⇒ 原生校验拦下 ⇒ `submit()` 里那句 `请把学号与口令都填上。` 的本地检查**根本跑不到** | 接上共用处置 |
| 5 | `/bind`（`auth/Bind.vue`） | 6 格（学号 / 出生日期 `type=date` / 工号 / 姓名 / 新口令 / 再输一次） | 混合 | — | 6 × `required` | 空（`?login=` 可预填） | — | **会**：同上，`localProblem()` 那四道**一道都跑不到** | 接上共用处置 |
| 6 | `/s/rpe`（`student/RpeEntry.vue`） | `class_session_id`（`select`）/ `rpe_token`（`text`）/ 11 个大按钮 | — | — | **一格都没有** | — | — | **不会**（提交按钮是 `:disabled="!canSubmit"`） | 刻意**不**接（死路径） |
| 7 | `/admin/*` 新建（`admin/ResourceList.vue`） | 契约驱动 | number/integer 一律画成 **`type="text"`** | — | **一格都没有**（「＊必填」只是标签文字，不是 `required` 属性） | 空 | — | **不会**（错话的住址是 `api/contract.ts` 的 `assembleBody` → `formError`） | 刻意**不**接 |
| 8 | `/admin/*` 编辑（`admin/ResourceDetail.vue`） | 同上 | 同上 | — | 同上 | **有**（预填 read-one 的原值） | — | **不会**（同上：`type="text"` 没有原生数值校验） | 刻意**不**接 |

⚠️ 派单点名的另外三处嫌疑逐个查过，**都不撞**：
* **RPE 快评**：`rpe` 是 11 个大按钮（`role="radiogroup"`），`rpe_token` 是 `type="text"`，
  `class_session_id` 是 `select` —— 一格原生约束都没有；
* **体测录入 / 体成分录入**：都是管理台那两张**契约驱动**的表单，`contract.ts` 的 `kindOf`
  把 `integer`/`number` 一律映射成 `type="text"`（`:type="field.kind === 'date' ? 'date' : … : 'text'"`），
  故**根本没有** `type="number"`，也就没有 `step`；解析与报错走 `assembleBody`。

⇒ 结论：**带 `step` 的 input 一共 1 处，撞的 1 处**；
带**任何**原生约束的表单 **3 张**（`CheckIn` / `Login` / `Bind`），三张**都会**静默。

### 2.5 改法与理由

**(a) 让预填值恒合法 —— `step="0.5"` → `step="any"`**

判据是**领域口径**，不是「让它能提交」。§2.2 那六格实测的结论是：
`duration_min` 的口径 = **任意 ≥ 0 的实数（分钟），可空；无步长、无上界**，
唯一所有者是 `TrainingLogCreate.duration_min`。故：

* `step="0.5"` 是**前端自己发明**的一个口径，与唯一所有者冲突 ⇒ 按派单的裁定
  「若领域口径本来就是任意，那 `step=0.5` 就是前端自己写错了，改它」；
* 数据那一侧**一个字都不许改**（`backend/data/**` 是指纹禁区；`demo_data.py` 生成的数据
  是 13 个波次的取证基础）；
* ⚠️ 取 **`any`** 而**不是** `0.1`：`any` **逐字等于**后端那个口径；`0.1` 又是一个前端发明的
  新口径、只是今天恰好不撞 —— 明天来一个两位小数的数据源，同一个静默就回来了；
* ⚠️ 往松的那一侧靠是**安全**的：真有个后端不认的值，`any` 放行 ⇒ 后端回 422 ⇒
  `ApiErrorBanner` 把 `loc` 与原因都画出来。**「太松会响、太紧会哑」⇒ 一律取松的那一侧**；
* `min="0"` **留着**（它逐字对应 `ge=0`，那一格的所有者确实是后端）；
  `inputmode="decimal"` **留着**（手机上仍然弹数字键盘）；
* ⚠️ 理由**逐字写进了那个 `<input>` 上方的代码注释**（口径所有者是谁、六格实测原文、
  为什么是 `any` 不是 `0.1`、失效方向的不对称），派单要求的「在代码注释里写清」这一格已落地；
* ⚠️ **没有**为这一格加 DB CHECK 或迁移：那会让口径有第二个所有者，且本波承诺
  「迁移链仍是 4 单头」。若控制者认为该落一条 CHECK，请另开一波（本波**顶回**自己去做，见 §6）。

**(b) 校验失败永远不许静默 —— 新增 `frontend/src/composables/useFormValidity.ts`**

⚠️ 这才是本缺陷的**真正病灶**：(a) 改对了只让「今天不撞」。

| 格 | 决定 |
|---|---|
| 形状 | **一个 composable**（不是指令、不是组件）。理由：① 它要同时产出「文本」与「挂监听器」两件事，指令只能做后者、组件只能做前者；② 各页要用**自己那一端既有的错误态类**画它（见下），一个组件就得挑一个前缀 = 第二个所有者 |
| 住址 | `frontend/src/composables/useFormValidity.ts`（与既有的 `useAsync.ts` 同目录、同姿势） |
| 挂钩点 | **`invalid` 事件**，捕获阶段挂在 `<form>` 上（`addEventListener('invalid', h, true)`）。⚠️ `submit` 在校验失败时**根本不触发**，故它无法用来报「校验失败了」；而 `invalid` **不冒泡**，所以必须开捕获 |
| 调用方 | `const { notice, bind, clear } = useFormValidity()` + `<form :ref="bindForm" …>` + 一段 `v-if="formNotice"` |
| 画它用的类 | 学生端 `.s-notice .s-notice--warn` + `.s-notice__title`（与「这一天已经有一行了」那一块同一族）；鉴权页 `.auth__advice` + `role="alert"`（与既有的 `advice` 同一格）。⚠️ **一行新 CSS 都没加**，`npm run check:tokens` 仍是 **36**/下界 25 |
| 「为什么」那一格 | **读浏览器自己的 `validationMessage`**，本仓不重算那套步长算术（第二个所有者）。实测中文原文：「请输入一个有效的值。最接近的两个有效值为 30.5 和 31。」 |
| 「哪个字段」那一格 | `el.labels[0].textContent` → `aria-label` → `name` → `id` → 标签名。⚠️ `el.labels` 是 HTML 规范给的那一格，它同时认「`<label>` 包住输入框」与「`<label for=…>` 另写一个」两种形状 ⇒ 本仓三种表单形状由**这一个**判据覆盖，且**不读任何 class 名**（`.field__label` 是学生端/管理台各自的口径） |
| 多格同时不合格 | 报「**N 格** + 第一格是谁」（浏览器聚焦的也是第一格）。⚠️ 这一档写守卫时真踩到了：登录页两个 `required` 都空着，措辞是「2 格没通过…（第一格是「学号」）」而不是「「学号」这一格…」 |
| 最贵的一句 | 「⚠️ 本次**没有**发出任何请求（原生校验拦在 `submit` 事件之前），改完再点一次提交。」—— 不说它，用户会以为「卡打出去了、只是页面没反应」，而打卡完成率是 spec §8.1 逐字点名的「RCT 关键过程指标」 |
| 刻意不用 | `alert()`（打断试用，且在无头取证里读不到）、只 `console.error`（甲方不开 devtools） |
| 清掉那一句话的时机 | ① `submit` 真的触发了（捕获阶段，那一刻它已过期）；② 用户开始改任何一格（`input`/`change`，捕获）；③ 调用方**程序**改了值时手动 `clear()` —— ⚠️ 这一格是**真的会用到**的：`CheckIn.vue` 那个预填 `watch` 写的是 ref（Vue 直接写 `input.value`，**不**触发 `input` 事件），故换一天时上一次那句话不会自己消失 |
| 挂了它的表单 | **3 张** = 本仓**全部**带原生约束的表单。另外 3 张刻意**不挂**（挂了是一条恒不触发的死路径，硬规矩 #50），而「新加一张带约束的表单时不许漏挂」由第 17 步 ⑩③ 那一拍钉住 |

**(c) ⚠️⚠️ 本波实测挖出的第三格静默（派单没点，而它比派单点的那一格更靠上游）**

改完 `step` 之后本波继续实测「真键盘输一个分钟数再提交」，抓到：

```
[console.error] [unhandled] native event handler TypeError: durationText.value.trim is not a function
    at submit (http://localhost:5174/src/views/student/CheckIn.vue:157:40)
点击之后新增的 /api 请求（0 个）
点击之后的页面：submitBtnText = "正在提交…"，submitDisabled = true
```

根因：`const durationText = ref('')`（= `Ref<string>`），而 Vue 的 `vModelText`
（`@vue/runtime-dom`）对 `<input type="number">` **在运行时把值转成 number**
（`castToNumber = number || vnode.props.type === 'number'` ⇒ `looseToNumber(el.value)`）。
故用户**手输**之后那一格是 `30.9`（number）而不是 `'30.9'`（string），
`submit()` 里那句 `durationText.value.trim()` 当场 `TypeError`。
⚠️ 而它抛在 `submitting.value = true` **之后**、`try` **之前** ⇒ `finally` 不跑 ⇒
按钮**永久**停在「正在提交…」且 `disabled`、**一个请求都没发**，只能刷新页面。
⚠️ 那一格的占位符逐字写着「例如 35」—— **照着它做就必中**。
⚠️ 它此前一直没被发现，是因为同一个输入框上还有 `step="0.5"` 那个静默先把它挡住了
（预填路径被原生校验拦住 ⇒ `submit()` 根本跑不到那一行；而手输路径**也**被拦住，
因为手输的 `30.9` 同样 `stepMismatch`）。

处置：类型改成 `ref<string | number>('')`（与运行时一致）+ `String(durationText.value).trim()`。
⚠️ 而「类型声明与运行时不一致」这一档 `vue-tsc` **一句话都不说**
（模板里 `v-model` 的赋值方向不做那一格检查；本波 `npx vue-tsc -b` 改前改后都是退出码 0）
—— 这就是硬规矩 #89/#103「不要靠读代码推断行为，跑起来量」的又一格。

### 2.6 改后取证（三个 case，都用真鼠标点击）

| case | 姿势 | 改前 | 改后 |
|---|---|---|---|
| A · 预填路径 | `/s/check-in?date=2025-10-12`（库里那一天有 `30.9`） | `step=0.5`、`stepMismatch=true`、`checkValidity=false`、**0 个 POST**、页面无变化 | `step=any`、预填仍是 `"30.9"`、`stepMismatch=false`、`checkValidity=true`、**POST 1 次 → 409**、请求体 `{"log_date":"2025-10-12","completed":true,"duration_min":30.9,"feeling":"easy","is_rest_day":true}`、页面上出现 `integrity_conflict · 409` 那句人话 |
| B · 成功路径 | 挑一个库里没有行的日期，**真键盘**（`Input.insertText`）输 `30.9` | `TypeError` ⇒ **0 个 POST** + 按钮永久「正在提交…」 | **POST 1 次 → 201**，响应体 `{"id":…,"duration_min":30.9,"source":"checkin","batch_id":null,"late":true,…}`，页面上出现 `SuccessMark` 的「**已打卡**」，按钮回到「提交打卡」 |
| C · 反静默 | 清空必填的 `log_date`，点提交 | 页面上一个字都没多 | **0 个请求**，页面上出现：`表单没有提交出去：「训练日 log_date」这一格没通过浏览器自带的校验 浏览器给的理由：「请填写此字段。」这一格是必填的。请填一个值再提交。⚠️ 本次**没有**发出任何请求（原生校验拦在 submit 事件之前），改完再点一次提交。`（挂在 `role="alert"` 上） |

---

## ③ 缺陷 ① 的守卫与定点变异

### 3.1 新拍的原文（都在 `frontend/scripts/smoke.mjs` 第 14 步）

⚠️ 判据两侧**不同源**：期望侧是 HTTP 响应体（翻页收学生 #4 的打卡行现算出来的日期与真值），
被测侧是 CDP 抓到的 DOM 文本与**真鼠标点击**之后浏览器真的发出去的那些请求。
⚠️ 刻意不用 `el.click()`：本缺陷的判据正是「浏览器那一条交互式校验的路径」。

* **§CI-0（3 拍）**期望侧现算 + 两格反空转：
  「泛型 list 翻页收到了学生 #4 的打卡行（≥ 1 行）」（实测 15 行）、
  「库里**有**一行 completed 且 `duration_min` 不是 0.5 的整数倍」（实测 `2025-10-12 → 30.9`）、
  「找得到两个库里还没有行的日期」。
  ⚠️ 「不是 0.5 的整数倍」用 `Math.abs(v*2 - Math.round(v*2)) > 1e-9`，不用 `%`（浮点）。
* **§CI-1（9 拍）**预填路径：预填成库里真值 → `stepMismatch === false` →
  `checkValidity() === true` → `noValidate === false`（反空转：`novalidate` 会让本组变成空转）→
  真鼠标点在那一个按钮上（反空转：`elementFromPoint` 就是它、且 `disabled === false`）→
  **`POST /api/training-logs` 真的发出去了**（恰好 1 次）→ 状态码 **409** →
  请求体**恰好 5 个键**且 `duration_min` 就是那个一位小数 →
  响应体 `error.code = integrity_conflict`（`Network.getResponseBody` 取的原文）→
  页面上看得见那句人话。
* **§CI-2（9 拍）**成功路径：`Input.insertText` 真键盘输 `30.9` → 表单合法 →
  **201** → 请求体 `duration_min === 30.9`、`log_date` 就是那个干净日期 →
  响应体 `source=checkin` / `batch_id=null` / 有 `id` 与 `submitted_at` / `duration_min` 就是 30.9 →
  **可见的成功反馈**（`SuccessMark` 的「已打卡」；⚠️ 它只停留 `--dur-check-hold`
  = 1600 ms 就自己收起，故这一拍**必须轮询**，不能等 POST 落地之后再看）→
  提交按钮**没有**卡在「正在提交…」。
* **§FV-1（8 拍）**反静默（打卡页）：清空必填的 `log_date` →
  「前提：`log_date` 已被清空」+「前提：整张表单**不**合法」→ **0 个 POST** →
  看得见那句人话 → 点名了**哪个字段**（用它自己的 label 文本，不是 name 属性）→
  给了**为什么**（读浏览器的 `validationMessage`）→ 给了**该怎么改** →
  **明说「没有发出任何请求」** → 挂在 `role="alert"` 上。
* **§FV-2（4 拍）**反静默（登录页 ⇒ 那个处置是**共用**的）：
  两个 `required` 都空着点「登录」→ **0 个 `POST /api/auth/login`**
  （⚠️ 于是本拍也**不消耗**任何一次登录失败计数，`login_attempt` 一行都不写）→
  看得见同一族那句话 → 点名「**第一格是「学号」**」→ 报了「**2 格**没通过」。
* **第 17 步 ⑩（6 拍，静态守卫从 9 条 → 10 条）**：
  ⑩① 那句人话的文案在 `src/**` 的**代码**里恰好 1 个文件 = `src/composables/useFormValidity.ts`；
  ⑩② 反空转（≥ 25 个 `.vue`、≥ 5 个含 `<form`；实测 30 / 6）；
  ⑩③ **每一张带原生约束的表单都接上了那个处置**（实测 3/3）；
  ⑩④ 而**没有**约束的那几张刻意**不**接（实测 3 张，死路径）；
  ⑩⑤ `src/views/**` 里 `step="<数字>"` 出现 **0** 次；
  ⑩⑥/⑥′/⑥″ 缺陷 ② 的源码面（见 §4.4）。
  ⚠️ ⑩③ 的「约束」谓词只认**属性位置**：前面是空白、后面是 `=`/空白/`>`/`/`，
  故 `v-for="step in RPE_SCALE"` 与 `class="step__n"` 都不会被算成约束
  （否则 `RpeEntry.vue` 会被误判成「带约束而没接」）。

⚠️ 断言数**只增不减**：dev **679 → 739**、产品 **679 → 739**、试用 **711 → 771**（三档各 **+60**）。
逐拍：第 14 步 dev/产品 **161 → 213**、试用 **193 → 245**（各 **+52**）；
第 17 步 **71 → 77**（**+6**）；其余 16 步一格未变。⚠️ 判据一格都没放宽（硬规矩 #92）。

### 3.2 定点变异取证（四格，每格跑一整遍 dev 档 smoke）

| # | 变异（逐字） | 红了哪几拍 | 条数 | 还原复核 |
|---|---|---|---|---|
| M1 | `CheckIn.vue`：`step="any"` → `step="0.5"` | §CI-1 的「不 stepMismatch」/「表单合法」/「POST 真的发出去了（0 次）」/「409」/「请求体 5 键」/「`duration_min` 就是那一个」/「响应体 code」/「可见反馈」；§CI-2 的「不 stepMismatch」/「表单合法」；第 17 步 **⑩⑤**（`step="<数字>"` 1 处） | **9** | sha256[:16] `72DC836A1B5A1C50`、36 701 B **逐字节回到原样 ✓** |
| M2 | `CheckIn.vue`：`String(durationText.value).trim()` → `(durationText.value as unknown as string).trim()` | §CI-2 的「POST 真的发出去了（**0 次**）」/「可见的成功反馈（12 s 内一次都没看见）」/「按钮**没有**卡在『正在提交…』（实测**就是**『正在提交…』）」 | **3** | 同上 ✓ |
| M3 | `CheckIn.vue`：摘掉 `<form :ref="bindForm">` 的那个 `:ref` | §FV-1 的「看得见一句人话」/「给了为什么」/「给了该怎么改」/「明说没有发出任何请求」/「挂在 `role="alert"` 上（0 个）」 | **5** | 同上 ✓ |
| M4 | `StudentDetail.vue`：`teachesLine` 的两句改成写死的同一句（还原缺陷 ② 的原始形状） | §TD-1 / §TD-2 / §TD-5；第 17 步 **⑩⑥**（那句写死的断言 1 个文件） | **4** | sha256[:16] `BC57049B94A4BDA8`、81 812 B **逐字节回到原样 ✓** |

⚠️ 四格**全部**变红、还原之后**全部**回绿，而还原是**按字节核的**
（改前存 sha256[:16] 与字节数，还原后再比一次；驱动脚本 `finally` 里做，故 smoke 抛了也还原）。
⚠️ 每格变异之前都**重灌**了一份干净的演示库（`demo_bootstrap.py`，与 `demo.ps1` 同一个生成器），
故第 0 步那 25 拍不会因脏库而红（红的话就分不清是变异还是脏库）。
⚠️ **M2 是本波最有价值的一次变异**：它证明 §CI-2 真的钉住了 §2.5(c) 那个 `TypeError` 静默，
而不只是钉住了 `step`。
⚠️ M4 里 §TD-3/§TD-4（两句互斥）**没有**红 —— 那是**对的**：写死的那一句既不含
「任教」needle 也不含「不任教」needle，故两拍各自的谓词仍然成立；抓住它的是
§TD-1/§TD-2（两句都不在）与 §TD-5（写死的那句回来了）。
⚠️ 反过来，若有人写死**其中一句**（例如两屏都说「后端确认「本学期任教他」」），
则 §TD-2 与 **§TD-4** 一起红 —— 那正是「两句互斥」这两拍要的形状。

### 3.3 写守卫时自己踩到的三格（如实记；判据一格都没放宽）

1. **「两个库里没有行的日期」首跑给了同一个日期**（实测 `2025-10-14 / 2025-10-14`）：
   改前那一份给 `freeDateAfter` 加了一个 `skip` 实参，而 `skip` 只是把起点往后挪，
   `taken` 里仍然没有第一个日期 ⇒「往后数第 2 个」还是它自己。
   ⚠️ 它不只是难看：§CI-2 会在 §FV-1 那一天留下一行，于是 §FV-1 那张「干净表单」
   实际上带着一次预填（本拍碰巧仍然绿，而「碰巧」不是判据）。
   处置：**先把第一个记进 `taken` 再找第二个**。
2. **§FV-2 的 needle 首跑按「只有一格不合格」那一档的措辞写**，而登录页**两个** `required`
   都空着 ⇒ 浏览器对两格各触发一次 `invalid`，`useFormValidity` 报的是「**2 格** + 第一格是谁」。
   处置：needle 改成「第一格是「学号」」，并**另加一拍**断「报了 2 格」
   （⚠️ 那一档本身就是要证的事：两格都不合格时用户也得看得见，而且看得见「一共几格 + 先改哪一格」）。
   ⚠️ 而 needle 刻意取**整句**而不是裸的「学号」：登录页的字段标签本来就写着「学号」，
   一个裸 needle 会被那一处满足（终审 S3-⑦ 查出过的同族假绿）。
3. ⚠️⚠️ **`toPlainText` 的一个潜伏陷阱**（本波新实测到，**已登记为待清扫**）：
   被测侧是 `document.documentElement.outerHTML`，而 DOM 的序列化规范会把文本节点里的
   `>` 转义成 `&gt;`（`<` → `&lt;`、`&` → `&amp;`、U+00A0 → `&nbsp;` 同理）。
   `toPlainText` 只剥 `<style>`/`<script>` 整块、剥标签、压空白，**不反转义实体** ⇒
   页面正文里那句 `教师会话 -> 403 forbidden` 在 needle 侧逐字是 `教师会话 -&gt; 403 forbidden`，
   **永远匹配不上**（首跑 §TD-8 就是这么红的：`旧抬头=false 新实测行=false`）。
   ⚠️ 失效方向是**红**（不是假绿，故它不危险，只是会把下一个人支去改页面散文）。
   处置：① 本波 needle 一律绕开 `<` / `>` / `&`，并把这一格逐字写进 smoke 的注释；
   ② **刻意不改** `toPlainText` —— 它是终审 I4 的单一所有者，第 17 步 ② 那五拍钉着它
   对已知反例的判定，在一个缺陷修复波里改它属于超范围，而「加一次实体反转义」
   会不会把某一条既有 needle 从绿变红要另做一遍全量取证。⇒ **顶回给控制者裁定**（见 §6）。

---

## ④ 缺陷 ②：`/t/students/:id` 第 06 块有一句**随 id 变假**的散文

### 4.1 改前 DOM 原文（两个 case，同一份 T0001 的 cookie，变量只有 URL 上那个 id）

**case A · 学生 1（T0001 任教他；教师侧变体 `GET /api/teacher/students/1/home` → 200）**

第 06 块那个 `<pre>` 的原文（`innerText`，逐字）：

```
GET /api/students/1/home                          -> 401 unauthenticated
GET /api/students/1/weekly-sheet                  -> 401 unauthenticated
GET /api/students/1/training-logs/completion-rate -> 401 unauthenticated
GET /api/students/1/prescriptions/current         -> 401 unauthenticated
GET /api/students/1/notifications                 -> 401 unauthenticated

（请求头一律是 X-Teacher-Staff-No: T0001；学生 1 确实由该教师本学期任教）
```

同屏 `.t-notice` 里含 403/forbidden 的：**只有第 06 块自己**（那一屏上没有 403 面板）。

**case B · 学生 4（T0001 不任教他；教师侧变体 → 403）**

```
GET /api/students/4/home                          -> 401 unauthenticated
…（四行同形）…

（请求头一律是 X-Teacher-Staff-No: T0001；学生 4 确实由该教师本学期任教）
```

同屏 `.t-notice` 里含 403/forbidden 的（**两块**，第 02 与第 05 块）：

```
forbidden · 403 当前身份不是本学期任教他的老师 （判据是 enrollment ⋈ course_section.teacher_id，
且两行的 semester_id 都必须等于「as_of 所属的那个学期」 → 「上学期教过他」不等于「这学期能读他」）。
学生 4 不在教师 'T0001' 于学期 2 任教的任何教学班里（或这个学生不存在）：判据是 enrollment ⋈
course_section.teacher_id，且两行的 semester_id 都必须等于那一个学期——上学期教过他不等于这学期能读他。
两者都报 403 而不是 404，理由与 require_teaches_section 逐字相同
```

⇒ **逐字复现了派单点的那一格**：同一屏上既有真话（403 面板）又有假话（「学生 4 确实由该教师本学期任教」）。

⚠️ 改前的第 06 块抬头与那一段散文（也逐字抄下来，因为它们**同时**是假话，见 §4.3）：

```
06  STUDENT ONLY
    教师头调学生侧端点仍然是 401
    Task 3 的实测原文，收尾波之后逐字仍成立
    unauthenticated · 401 —— 学生侧的端点只认 X-Student-Id
    下面五个端点都 Depends(current_student)，缺 X-Student-Id 就是 401 unauthenticated；
    而前端 client.ts 一次只注入一个身份头（stores/identity.ts 的「一次只有一种身份」）→
    「教师身份」与「读它们」在结构上互斥。
```

### 4.2 改后 DOM 原文（同两个 case，同一支探针重跑）

**case A · 学生 1**（`<pre>` 末两行）：

```
这一次的身份 = pe_session cookie 里的 T0001（教师）。
学生 1：教师侧变体 GET /api/teacher/students/{id}/home 回了 200 ⇒ 后端确认「本学期任教他」
（判据是后端那一条 enrollment ⋈ course_section.teacher_id，且两行的 semester_id 都必须等于本学期）
```

**case B · 学生 4**：

```
这一次的身份 = pe_session cookie 里的 T0001（教师）。
学生 4：教师侧变体 GET /api/teacher/students/{id}/home 回了 403 forbidden ⇒
后端说「不在他本学期任教的任何教学班里」 —— 同一屏上面第 02/05 块那两块 403 面板说的就是这件事，
两句话同一个来源
```

⚠️ 两句**互斥**，且都由**同一个** HTTP 结果算出来 ⇒「写死一句」当场红（§3.2 的 M4 已实测）。

### 4.3 判据的单一所有者

```ts
/** 三档：`true` 任教 / `false` 不任教 / `null` **还不知道**。 */
const teachesHere = computed<boolean | null>(() => {
  const loaded = data.value
  if (loaded === null) return null
  if (loaded.home !== null) return true
  if (loaded.homeError === null) return null
  return loaded.homeError.code === 'forbidden' ? false : null
})
const teachesLine = computed<string>(() => { /* 三句互斥的话 */ })
```

* ⚠️ 本页**不再自己判一次**任教关系：那是后端 `app/api/deps.py` 的
  `require_teaches_student` 的活（而它那条 SELECT 又住在 `taught_student_ids` 里，
  后端自己也是「判据只能有一个所有者」的姿势）。前端重算一遍就是第二个所有者，
  而两份漂开之后的症状**正是本缺陷**（一处说 403、另一处说「确实任教」）。
* ⚠️ 读的是 **`homeError`** 而**不是** `sheetError`：`/home` 的教师侧变体**不会 404**
  （后端把「任何一格缺数据」都折成 `null`），故它只有 200 / 403 两档；
  而 `weekly-sheet` 那一个另有两档 404（`no_active_prescription` / `outside_microcycle`），
  拿它当判据会把「这一天没有生效处方」读成「他不任教这个学生」。
* ⚠️ **`null` 那一档必须存在**：把它折成 `false` 又是一句假话
  （「他不任教」与「我还没读到」是两件事，与约束第 10 条「不知道不得显示成 0」同源）。
  而 smoke 的 `grabDetail` 轮询退出条件里**两句 needle 都要试**，
  否则 `null` 那一档会变成一次 45 s 的超时（那就是「本页不下断言」那一句的取证）。

### 4.4 请求头通道那一段：改前 / 改后

**改前**（第 06 块里那一段的全部相关内容）：`<pre>` 末行那句
「（请求头一律是 `X-Teacher-Staff-No: T0001`；学生 N 确实由该教师本学期任教）」
+ 抬头「教师头调学生侧端点仍然是 401」+ 正文「缺 `X-Student-Id` 就是 401
`unauthenticated`；而前端 `client.ts` **一次只注入一个身份头**…」。
⚠️ 全段**没有一处**说明那条通道今天还存不存在、要什么条件。

**改后**（**没有删掉整段** —— 本仓的页面散文是可解释性资产；改成逐字说真话）：

1. 抬头 → 「学生侧那五条路径：**教师会话是 403，没有会话才是 401**」，
   副题 → 「2026-10-15 重测过（Plan 04 Task 3 那份「401」的实测原文是请求头时代量的，已过期）」；
2. `<pre>` 那五行改成**两栏实测**：`教师会话 -> 403 forbidden    没有会话 -> 401 unauthenticated`，
   并另加一档：「教师会话**再带上**一个伪造的 `X-Student-Id` 请求头 → 五条**仍然全是 403**，
   即那个头一个字节都不看」；
3. 「互斥」这件事**仍然说**，而它的住址改成真话：从「`client.ts` 一次只注入一个身份头」
   搬到「一个会话只有一种 `kind`」（`stores/session.ts`）；
4. 新增两段专门讲那条通道：
   * 「它要**两个条件同时成立**才有效力：① 前端是**开发档构建**（`identityHeaders()` 第一行就是
     `if (!import.meta.env.DEV) return {}`，故生产构建里那两个头一个都不会发出，
     守卫是 `npm run check:dist`）；② 后端**显式**设了 `PE_ALLOW_HEADER_IDENTITY=1`
     （缺省逐字是 `"0"`）」；
   * 「交付的那几个脚本**一律把它关掉**：`backend/scripts/demo.ps1` 与 `scripts/serve.ps1`
     各有一段强制清掉这个环境变量的代码（`Remove-Item Env:\PE_ALLOW_HEADER_IDENTITY`，
     删不掉就当场 `throw`），`scripts/trial.ps1` 委托后者、`scripts/tunnel.ps1` 只起隧道不起服务；
     而 `prod` 档下 `app/api/deps.py` 的 `allow_header_identity()` **结构上恒 False**
     （读到 1 也忽略，另在启动时打一条 warning）。⇒ **照着这一页去加一个身份请求头，
     在甲方手上不可能生效。** 要换一个身份，请用上面那条会话条**登出**、再用另一个账号登录。」

⚠️ 第 4 条那两句里的每个事实都**实测过**（不是抄注释）：
`allow_header_identity()` 的源码逐字读了（`deps.py:203-223`，两个条件 + `prod` 强制 False）；
三个脚本的强制清那一段逐字读了（`demo.ps1:150-158`、`serve.ps1:305-314`、
`tunnel.ps1` 全文**没有** `PE_ALLOW_HEADER_IDENTITY` 一行 —— 它**不起服务**，
故那句真话是「它只起隧道」而不是「它也清」）；
「伪造请求头一个字节都不看」是**实发**的（六档 × 五条路径，见 §4.5）。

### 4.5 本波顺带实测出**同一块里另外三句假话**（一并修，逐个报）

| # | 改前原文 | 为什么是假的（**实测**，不是读代码） | 修没修 |
|---|---|---|---|
| ① | 抬头「教师头调学生侧端点仍然是 **401**」+ 副题「Task 3 的实测原文，**收尾波之后逐字仍成立**」 | 教师**会话**打那五条是 **403 `forbidden`**；401 只属于「完全没有会话」那一档 | **修了** |
| ② | `<pre>` 里五行「`-> 401 unauthenticated`」 | 同上。六档逐条实发（学生 1）：教师 cookie → **5×403**；教师 cookie + `X-Teacher-Staff-No: T0001` → **5×403**；教师 cookie + 伪造 `X-Student-Id: 1` → **5×403**；只有 `X-Student-Id: 1` 没有 cookie → **5×401**；匿名 → **5×401**；学生 4 的 cookie 读学生 1 → **5×403** | **修了** |
| ③ | 「前端 `client.ts` **一次只注入一个身份头**（`stores/identity.ts` 的「一次只有一种身份」）」 | 生产构建里 `identityHeaders()` **恒回空对象**（`if (!import.meta.env.DEV) return {}`）；「互斥」这件事仍然成立，而它的住址是「一个会话只有一种 `kind`」（`stores/session.ts`） | **修了** |
| ④ | 末段「但「**两个头**都没带」是 401 还是 422？」 | Plan 05A 之后没有「两个头」这回事了，那一问的对象已经不存在 | **修了** |
| ⑤ | 末段「`home` 那一条是**本波**加的」 | 「本波」随阅读时刻变假（那是 Plan 04 收尾波） | **修了**（点名到波次） |
| ⑥ | `<ul>` 第一条「教师端走：`/home`（**本波新加**，响应体逐字相同）」 | 同 ⑤ | **修了** |

### 4.6 同族自查清单（16 条路由的**渲染**散文）

判据的两类（控制者裁定：这两类**必须本波修完**）：
**「随 id/身份变真假的断言句」**与**「教人用一条关掉的通道」**。
「关掉的通道」有三条，逐个实测过：`X-Student-Id` / `X-Teacher-Staff-No` 请求头
（要 DEV 构建 + `PE_ALLOW_HEADER_IDENTITY=1`）、`?student=` / `?teacher=` 深链接身份
（`src/dev/identity-url.ts`，生产构建里被整个摇掉，守卫是 `npm run check:dist`）、
`IdentitySwitcher.vue` 里那一半切换器（`v-if="IS_DEV"`，⚠️ 它**自己**说清了是
「开发期请求头」，故它**不是**假话，本波没动它）。
换身份的正确姿势只有一个：**会话条上登出 → 用另一个账号登录**。

**渲染散文里挖出 19 处、修了 19 处**（0 处登记待清扫）：

| # | 文件 | 改前原文（节选） | 为什么是假的 | 修没修 |
|---|---|---|---|---|
| 1 | `teacher/StudentDetail.vue` 第 06 块 `<pre>` | 「学生 N **确实**由该教师本学期任教」 | **随 id 变假**（缺陷 ② 本体） | ✓ |
| 2 | 同上 抬头 + 副题 | 「教师头调学生侧端点仍然是 401」/「收尾波之后逐字仍成立」 | §4.5 ① | ✓ |
| 3 | 同上 `<pre>` 五行 | 「`-> 401 unauthenticated`」 | §4.5 ② | ✓ |
| 4 | 同上 正文 | 「`client.ts` 一次只注入一个身份头」 | §4.5 ③ | ✓ |
| 5 | 同上 末段 | 「两个头都没带是 401 还是 422」/「`home` 那一条是本波加的」 | §4.5 ④⑤ | ✓ |
| 6 | 同上 `<ul>` | 「（本波新加，响应体逐字相同）」 | §4.5 ⑥ | ✓ |
| 7 | 同上 「还不知道你是哪位老师」空态 | 「挂 `X-Teacher-Staff-No`…请在身份切换器里选一位教师，或加 `?teacher=T0001`」 | 两条都是关掉的通道 | ✓ |
| 8 | 同上 「读不到这个学生」空态 | 「它是**匿名**端点，故这一档的意思是『这个 id 不在册』，不是『没有权限』」 | openapi 上 `GET /api/students/{id}` 挂 security、匿名实发 **401** ⇒ 后半句**指错方向**（一个「读不到」被断言成「不在册」）。改成照 `student/MiniTest.vue` 那格的同款处置：**不再对身份口径下任何断言** | ✓ |
| 9 | 同上 第 03 块 `t-block__why` | 「读的是**匿名的** `GET /api/stratification-results`」 | 同上（匿名 401） | ✓ |
| 10 | 同上 第 05 块 `t-block__why` | 「教师用自己的头调它是 401…而 `client.ts` 一次只注入一个身份头」 | 现在时的一句，Plan 05A 之后过期 | ✓（改成过去时 + 点名今天的码是 403） |
| 11 | `teacher/Dashboard.vue` 空态 | 「挂 `X-Teacher-Staff-No`…请在上面的身份切换器里选一位教师，或在 URL 上加 `?teacher=T0001`。演示库有三位：T0001 陈国华（班 1+班 3）、T0002 林慧敏（班 2+班 4）、T0003 赵志刚（班 5）」 | 关掉的通道 + **写死的数据例子**（随 `-Students / -Seed` 变假；工号与口令的所有者是 `demo_bootstrap.py`） | ✓（并摘掉那三个写死的姓名/带班） |
| 12 | `teacher/ClassReport.vue` 空态 | 同 #11 的前半 | 同上 | ✓ |
| 13 | `teacher/ClassReport.vue` `unauthenticated` 那一档 | 「没有带上 `X-Teacher-Staff-No`。」 | 那一档今天的意思是「会话没了/过期了」 | ✓ |
| 14 | `student/Home.vue` 空态 | 「三个挂 `X-Student-Id`。请在身份切换器里选一个学生（或在 URL 上加 `?student=4`）—— 演示库里有 60 个学生，其中 **4、11、15、17** 四个…看起来最满」 | 关掉的通道 + 两个写死的数（60 的所有者是 `/api/health` 的 `students`；四个 id 是终审 I1 那一族） | ✓（两个都摘掉） |
| 15 | `student/WeeklySheet.vue` 空态 | 「本端点挂 `X-Student-Id`，且路径里的学号必须与请求头是同一个人…请先选一个身份」 | 同上 | ✓ |
| 16 | `student/RpeEntry.vue` 空态 + `ADVICE.unauthenticated` + `ADVICE.forbidden` | 「挂 `X-Student-Id`，而…`student_id` 就来自这个头」/「没有带上 `X-Student-Id`。请在身份切换器里选一个学生。」/「不是当前**请求头**里的那个人」 | 同上（三处） | ✓ |
| 17 | `student/Notifications.vue` 空态 + `adviceFor` | 「『发给我的消息』里的『我』就是 `X-Student-Id`」/「没有带上 `X-Student-Id`：请在身份切换器里选一个学生。」 | 同上（两处）；另摘掉空态里写死的「那 19 条」 | ✓ |
| 18 | `student/Notifications.vue` 第 01 块 | 「挂 `X-Student-Id` + `require_scope`…`recipient_id = 请求头里那个学号`」/「学生 A 用 `X-Student-Id: A` 去读 B」 | 同上 | ✓ |
| 19 | `student/Notifications.vue` 第 01 块末段 | 「那个匿名 list **今天仍然存在、仍然是匿名的**（本仓的读侧口径是『读 ⇒ 一律匿名』，**48 个匿名 GET** 里已经包括给出 60 人出生日期的 `GET /api/students`）」 | **三句都是假话**（实测：匿名打 `GET /api/notifications` 是 **401**；`GET /api/students` 匿名 **401**；openapi 上 63 个 GET = **15 匿名 + 48 挂 security**，那个「48」被当成了匿名数）⇒ 改成**不复述数字**，只指向两个机器口径的住址 | ✓ |
| — | `student/CheckIn.vue` 空态 + `submitAdvice` | 「挂 `X-Student-Id`，而…`student_id` 就来自这个头」/「身份不对：本端点要 `X-Student-Id`」 | 同上 | ✓（在缺陷 ① 那个 commit 里一起修的） |

⚠️ 第 19 处正是派单说的「管理台首页那段『读是匿名的』」那一族的**存量**
（管理台首页那一段 Plan 06 Task 15 已经修过；本波在学生端消息中心又挖到一处）。

**登记为待清扫、本波刻意没修的**（不在这两类里，或修它会动到别的所有者）：

| # | 住址 | 原文 | 为什么没修 |
|---|---|---|---|
| A | 各 `.vue` 的 **`<script>` docblock**（不渲染给甲方）：`Dashboard.vue` 文件头那 7 行「**匿名**」、`StudentDetail.vue` 文件头第 1/5/6 条、`ClassReport.vue` 文件头 ①③⑤、`MiniTest.vue` 文件头、`Notifications.vue` 文件头「读 ⇒ 一律匿名 / 48 个匿名 GET / 19 条」、`endpoints.ts:124/154/828` | 同族过期散文 | 一次「散文大扫」应当独立成波（13 个文件、逐个要重新实测六档身份）；它们是给开发者看的，甲方看不见 |
| B | **后端 docstring**：`app/api/routers/dashboard.py:859`、`app/api/routers/feedback.py:1205`（「前端一次只注入一个身份头」），以及由它们生成的 `frontend/src/api/generated/schema.d.ts` 里 6 处 | 同上 | ⚠️ **本波刻意不动**：后端 docstring 会被 FastAPI 渲染进 `/openapi.json` 的 `description`，改一个字就改 openapi 的字节（本波承诺「420 367 B / `6058F97F09B35855` 一个字节都不变」），而且要连带重跑 `npm run gen:api` 重生 `schema.d.ts`（527 KB）⇒ 它必须是**自己的一波** |
| C | `Notifications.vue` 空态里写死的「19 条通知 / 19 个学生 id 清单」 | 数据例子那一族 | 本波只摘掉了同一句里的「那 19 条」；那一份 id 清单是**演示库的事实**（seed 固定时它是真的），要不要按「不许写死数据例子」统一处置请控制者裁定 |
| D | `.auth__advice` 那条 CSS 在 `Login.vue` 与 `Bind.vue` 里**各有一份** | 既有的第二个所有者 | 与本波两个缺陷无关，动它要重排两个 scoped style |
| E | `toPlainText` **不反转义 HTML 实体**（§3.3 第 3 格） | 一个潜伏陷阱：任何含 `<` / `>` / `&` 的 needle 永远匹配不上 | 它是终审 I4 的单一所有者，改它属于超范围（见 §6 顶回） |

### 4.7 缺陷 ② 的守卫

第 14 步 **§TD-0…§TD-8′（12 拍）** + 第 17 步 **⑩⑥/⑥′/⑥″（3 拍）**：

* §TD-0（4 拍）反空转 + **期望侧两档 HTTP**：两个 case 的 id 不是同一个（实测 `任教=#10` / `不任教=#4`）；
  教师侧变体对 #10 回 **200**、对 #4 回 **403**、而那个 403 的 `code` 是 `forbidden`
  （⇒ 页面那一句读的就是这一格，本页不自己再判一次）；
* §TD-1/§TD-2 两句 needle **各在其屏**；
* §TD-3/§TD-4 两句**互斥**（⚠️ 两拍合起来才是「写死一句就会红」的判据）；
* §TD-5 改前那句写死的断言在两屏上都**一个字节都不剩**；
* §TD-6 不任教那一屏上，第 02/05 块那两块 403 的**真话照旧在**（本波修的是那句假话，
  不是把真话一起删掉）；
* §TD-7 请求头通道那一段**没有被删掉**（可解释性资产），且点名了
  `PE_ALLOW_HEADER_IDENTITY` / `allow_header_identity` / 「不可能生效」；
* §TD-8/§TD-8′ 那一块不再声称「教师头…是 401」，而那个 `<pre>` 里**每一行**都给了两档实测
  （数 `403 forbidden` 的出现次数 ≥ 5；⚠️ needle 刻意不用带 `>` 的串，理由见 §3.3 第 3 格）；
* 第 17 步 ⑩⑥/⑥′/⑥″（源码面，三档都跑、不需要任何服务起着）：
  那句写死的断言在 `src/**` 的**代码**里 **0** 个文件；「本学期任教他」恰好 **1** 个文件
  = `src/views/teacher/StudentDetail.vue`；而那个判据读的是
  `homeError.code === 'forbidden'` 且返回类型是 `boolean | null`。
* 变异 M4（§3.2）⇒ **4 条红**，还原后逐字节回到 `BC57049B94A4BDA8` ✓。

---

## ⑤ 关切（**不是缺陷**）：试用告示在公网上要两次**串行**往返才出现

### 5.1 慢的实测原因

⚠️ 只发**匿名的** `GET /api/health`（两遍各 5 次，共 10 次；它不写库、不留审计）。

| 格 | 第一遍（本机正跑着无头浏览器与 pytest） | 第二遍（机器空闲） |
|---|---|---|
| 本地 `127.0.0.1:8030/api/health` ×5 | 最小 **4.2** / 中位 **5.6** / 最大 **43.9 ms** | 最小 **18.5** / 中位 **20.9** / 最大 **35.6 ms** |
| 公网隧道 `/api/health` ×5 | 最小 **5 549** / 中位 **5 575** / 最大 **6 323 ms** | 最小 **5 538** / 中位 **5 551** / 最大 **6 359 ms** |

⇒ 三格结论：

1. **不是串行等待本身慢，也不是后端算得慢**：本地那一次 `/api/health` 是 **4–44 ms**；
2. **几乎全是隧道往返**：同一个请求穿过 cloudflared 的 quick tunnel 是 **5.5–6.4 s**，
   差**约 1 000 倍**。⚠️ 两遍数字逐格相同 ⇒ **本机的负载不是原因**；
3. 而 `App.vue` 的 `onMounted` 里两次请求是**串行**的
   （`await session.ensureRestored()` 之后才 `await getHealth()`）⇒
   告示最坏要等 **2 × 6.4 s ≈ 12.7 s**、中位 **≈ 11.1 s**。

⚠️ 它比 Task 5 量到的 **1.5–4.1 s** 还慢一档。`trycloudflare` 的 quick tunnel 是一个
**共享的、随时间漂移**的通道（它的寿命就是那个 cloudflared 进程的寿命），
故「告示要等多久」这件事**没有稳定上界** —— 这本身就是「不把它当成一个可以调好的数」的理由。

### 5.2 §I5 那条守卫在钉什么（先读懂，再决定改不改）

`smoke.mjs` 第 14 步 §I5（4 拍）逐字断言：

1. 「§I5 抓到了后端请求（守卫不空转）」；
2. 「§I5 **第一个**后端请求就是 `GET /api/auth/me`（会话恢复那一次）」；
3. 「§I5 而那第一个请求**不带任何身份头** —— URL 上那个未验证的身份不得先于会话进 store」；
4. 前置两拍（URL 上要认的那个学生与会话里那个不是同一个人 / `localStorage` 已清空）。

它的来历是**终审 I5**：改前 `main.ts` 在会话还没问过之前就认了 URL 上那个
**未经验证**的身份，于是第一个请求带着一个伪造得出来的 `X-Student-Id`。
⚠️ 它钉的是「**任何**请求都不得先于会话恢复」，而不只是「那一个请求不带身份头」。
⚠️ 而**产品档**的 `main.ts` 是**同步** `mount()`（只有 DEV 那一支先 `await`），
故 `App.vue` 的 `onMounted` 会抢在路由守卫之前跑 —— 一个提前发出去的 `getHealth()`
就成了第一个请求 ⇒ **让 `/api/health` 与会话恢复并行，§I5 会当场红**。
`App.vue` 的文件头逐字写着这件事，并写着「⚠️ 不许为了让本文件通过而放宽它」。

### 5.3 裁定：**不改**（同意控制者的倾向）

三条理由，逐条核过：

1. **并行会破 §I5**，而放松 §I5 是硬规矩 #92 禁止的那一档（「不许为了让新代码通过而放宽既有判据」）。
   ⚠️ 本波认为**那条守卫是对的**：它钉的性質（任何请求都不得先于会话恢复）比
   「告示晚几秒」重要 —— 后者是观感，前者是「一个伪造得出来的身份会不会先于验证进 store」。
2. **兜底那一条**（在 `/api/health` 回来之前先渲染一句不依赖后端的静态提示）与
   「档位**不能写死在构建产物里**」直接冲突：`frontend/dist` 是同一份产物服务四档，
   一句静态的「请勿录入真实学生信息」会在**产品档**上也挂着 —— 那是一句假话
   （那一档的库里可以是真数据），而本仓的纪律是「宁可少说一句，不说一句假的」。
   ⇒ 按派单的要求**顶回来讨论**，本波**没做**。
3. **真能治本的那一条要动后端契约**：把 `trial` 那一格并进 `GET /api/auth/me`
   的响应体（于是一次往返就够）。⚠️ 但那会改 `/api/auth/me` 的响应 schema ⇒
   改 openapi 的字节（本波承诺一个字节都不变）+ 重生 `schema.d.ts`（527 KB）⇒
   它必须是**自己的一波**。**登记为待裁定**（见 §6）。

⇒ 处置：**如实登记 + 在《甲方试用说明书》里写一句**（§8 给出逐字建议）。

---

## ⑥ 待清扫 / 关切 / 没按派单做的 / **顶回**

### 6.1 顶回（**3 处**）

| # | 顶回什么 | 本波的判断 |
|---|---|---|
| ① | **`toPlainText` 不反转义 HTML 实体**（§3.3 第 3 格） | 本波**没改它**，请控制者裁定要不要另开一格修。理由：它是终审 I4 的单一所有者，第 17 步 ② 那五拍钉着它对已知反例的判定；「加一次实体反转义」会不会把某一条既有 needle 从绿变红，要另做一遍**全量**取证（三档 × 18 步）。⚠️ 失效方向是**红**不是假绿，故它不危险，但它会把下一个人支去改页面散文（本波自己就被支了一次）。**建议**：修，而修法是在 `toPlainText` 里加一步 `&lt; &gt; &amp; &nbsp;` 的反转义 + 补两拍（正控：一个 needle 含 `>` 时命中；反例：`<style>` 里的 `>` 仍然不算正文） |
| ② | **关切 ③ 的兜底那一条**（静态提示） | 本波**没做**，与派单里控制者自己的倾向一致：它与「档位不能写死在构建产物里」直接冲突，做了就是在产品档上挂一句假话。⇒ 请确认「不改 + 说明书里写一句」这个处置 |
| ③ | **`duration_min` 要不要落一条 DB CHECK / schema 的 `multiple_of`** | 派单说「若你认为需要落一条 CHECK 约束，顶回来，不要偷偷加迁移」。本波的判断是**不要落**：领域口径是「任意 ≥ 0 的实数」，落一条 `multiple_of=0.1` 等于**新造**一个口径（而它今天没有所有者），且要动迁移链（本波承诺仍是 4 单头）。⇒ 请确认「口径留在 `TrainingLogCreate` 的 `ge=0`、前端 `step="any"`」这个处置 |

⚠️ 派单点名的另外两个可能顶回处，本波**核过、同意、没顶回**：

* **`step` 该改成什么值**：核过后端 schema / openapi / DB 列 / spec §4.5+§8.1 / 仿真数据
  五格之后，结论是「领域口径 = 任意 ≥ 0 的实数，无步长」⇒ 按派单那一支
  「若领域口径本来就是任意，那 `step=0.5` 就是前端自己写错了，改它」办，取 `any`。
  ⚠️ 与派单给的例子（`0.1` 或 `any`）里本波选了 `any`，理由逐字写在 §2.5(a) 与代码注释里。
* **反静默那一格的形状（共用函数 vs 指令 vs 组件）**：选了 **composable**，理由见 §2.5(b) 那张表
  （它要同时产出「文本」与「挂监听器」两件事，且各页要用自己那一端既有的错误态类画它）。
* **缺陷 ② 的「不删整段、只改成真话」**：核过、同意。改后那一段比改前**更长**
  （多了「两个条件 + 三个脚本 + `prod` 下结构上不可能」这三句真话），
  可解释性资产一个字都没少。
* **同族自查挖出太多时怎么切范围**：本波把范围切成「**渲染**散文里的这两类**必须修完**」
  （19 处，全修）+「`<script>` docblock 与后端 docstring 登记待清扫」（§4.6 A/B）。
  切在这儿的理由：甲方看得见的是渲染面；而后端 docstring 一改就动 openapi 的字节，
  与本波「openapi 一个字节都不变」的承诺冲突。

### 6.2 没按派单做的（**2 处**，如实记）

| # | 派单怎么说 | 本波怎么做 | 为什么 |
|---|---|---|---|
| ① | 「建议 4 个 commit：① 缺陷①的实测表 + 修正；② 缺陷①的 smoke 拍；③ 缺陷② + 守卫；④ spec + 报告」 | 交了 **5 个**：① 缺陷①（3 格）② 缺陷② + 同族 ③ **`check:dist` 禁用串那一格**（派单没预料到）④ smoke 守卫（缺陷①与②的拍**合在一个** commit）⑤ spec + 报告 | 两处偏差：**(a)** `smoke.mjs` 是**一个文件**，两个缺陷的守卫都在里面，拆成两个 commit 要么把文件写两遍（还原风险）、要么用 partial staging（本仓纪律是按文件名逐个 `git add`）⇒ 合成一个；**(b)** 多出 commit ③：本波自己踩到「页面正文里不许出现 `check:dist` 的禁用串」，它是一个**独立的、有自己取证与纪律**的一格（§6.3），值得单独一个 commit。⚠️ 后果如实记：**commit ② 那一刻，对本波自己的构建跑 `check:dist` 是红的**（那个禁用串），commit ③ 才修掉 ⇒ **② 不是完全自洽的**。①③④⑤ 各自自洽 |
| ② | 「缺陷①的全面实测表」放在 commit ① | 放在**报告**里（§2.4 那张表），commit ① 的信息里只写了结论与三格取证 | 那张表有 8 行 × 10 列，写进 commit 信息里读不动；而报告的 §2 是它的自然住址（与前几波同一条口径） |

### 6.3 ⚠️ 本波自己踩到的一格（新纪律，已写进 spec §13.18.6）

**页面正文里不许出现 `check:dist` 的禁用串。**
缺陷 ② 那段「说真话」的散文里逐字写了 `<code>adoptFromUrl</code>`（为了说清
「那个深链接身份助手在生产构建里被整个摇掉」），而 `scripts/check-dist.mjs` 的
`FORBIDDEN` 串**就是** `adoptFromUrl` ⇒ **本波自己的构建当场把那条交付守卫弄红了**：

```
✗ dist/ 里 adoptFromUrl 出现 0 次（它必须被 Rollup 摇掉）  →  assets\StudentDetail-BDzdiR00.js ×1
```

⚠️⚠️ **它是「不跑 `npm run build` 就发现不了」的**：`frontend/dist` 是控制者那一份在跑的产物，
smoke 第 15 步的 `check:dist` 扫的是它（本波三档都绿）。本波另用**同一份守卫脚本**扫
自己那一份构建才把它抓出来 —— 姿势：`vite build --outDir $env:TEMP\p07t5b\dist --emptyOutDir`
（仓库外，`frontend/dist` 一个字节都不动）+ 两个 junction（`fe\src` → `frontend\src`、
`fe\dist` → 那一份产物）+ 一份 `check-dist.mjs` 的副本放在 `fe\scripts\` 下
（它从**自己的**位置算 `FRONTEND`/`SRC`/`DIST`，故一行守卫代码都没改）。

⚠️ 顺带实测到两件此前没人写过的事：
**Vue 的模板 HTML 注释在生产构建里被剥掉**（四处模板注释里也写了那个名字，产物里 0 次）；
**`<script>` 里的注释被压缩器剥掉**（三处既有注释同理）⇒ 只有**渲染出来的正文**会漏进产物。
⚠️ 而本波仍然把那四处模板注释里的名字一并摘掉了：「被剥掉」是**编译器**的行为、
不是本页的契约，把一条守卫的禁用串写进模板注释等于给它留一个静默的失效口。

⇒ **纪律（建议写进硬规矩）**：任何改前端**正文**的波次，除了 `npm run check:dist`
（扫既有 `dist`）之外，还要对**自己那一份构建**跑一次同一个守卫。

### 6.4 待清扫（本波登记的，共 **5** 条 + 关切 **1** 条）

| # | 条 | 住址 |
|---|---|---|
| 1 | 各 `.vue` 的 `<script>` docblock 里同族的过期散文（13 个文件） | §4.6 A |
| 2 | **后端 docstring** 里同族的过期散文（2 处）+ 由它生成的 `schema.d.ts`（6 处）—— ⚠️ 改它要动 openapi 的字节 + 重生 527 KB 的产物，必须自己成波 | §4.6 B |
| 3 | `Notifications.vue` 空态里写死的「19 条通知 / 19 个学生 id 清单」 | §4.6 C |
| 4 | `.auth__advice` 那条 CSS 在 `Login.vue` 与 `Bind.vue` 里各有一份 | §4.6 D |
| 5 | `toPlainText` 不反转义 HTML 实体（**同时是顶回 ①**） | §3.3 / §6.1 |
| 关切 | 试用告示在公网上要两次串行往返（最坏 ≈ 12.7 s）。治本要动后端契约（把 `trial` 并进 `/api/auth/me`）⇒ 请裁定要不要开一波 | §5 |

---

## ⑦ 最终验收

### 7.1 后端测试（四条命令行，与 Plan 07 Task 3 报告里那三条逐字相同 + `--no-cov` 那一条）

| 命令 | 结果 | 用时 | 基线 |
|---|---|---|---|
| `python -m pytest -q --no-header --no-cov` | **1606 passed**, 1 warning | **179.21 s** | 1606（181–216 s）✓ **一格未变** |
| `… --cov=app/domain --cov-branch --cov-report=term` | **1605 passed, 1 skipped**；`TOTAL 1268  0  376  0  100%` | 296.48 s | 1268/0/376/0/100% ✓ **逐格相同** |
| `… --cov=app --cov-branch --cov-report=term` | **1605 passed, 1 skipped**；`TOTAL 7311  201  1778  115  96%` | 305.46 s | 7311/201/1778/115 ✓ **逐格相同** |
| `… --cov=scripts --cov=app.static --cov-branch --cov-report=term` | **1605 passed, 1 skipped**；`TOTAL 583  173  164  24  69%` | 281.38 s | 583/173/164/24 ✓ **逐格相同** |

⚠️ **`Cover` 列不是基线的一部分**（它随 `--cov-branch` 的有无而变，spec §12 已写清），
故本波照 Task 3 的姿势把四格 `Stmts / Miss / Branch / BrPart` 逐个对账，
`Cover` 只如实抄（100% / 96% / 69%）。
⚠️ 1606 → **1606**：本波**一行后端生产代码都没改**（改动面全在前端 + smoke），
故后端测试数一格未变，而这也正是「后端 0 新增测试」的如实交代。

### 7.2 表数 / 迁移链 / 残差 diff

| 格 | 基线 | 本波实测 |
|---|---|---|
| 表数 | 28（`sqlite_master` 29） | 三个库各 **29**（28 业务表 + `alembic_version`），`student` 各 **60**：`pe_t5b.db`（试用档，本波自己灌的）/ `pe_t5b_prod.db`（产品档）/ `backend/pe_demo.db` ✓ |
| `/api/health` 的 `tables` | 28 | **28**（三档各实测一次：dev / 产品 / 试用；试用档另给 `"trial":true`）✓ |
| 迁移链 | 4 单头 | `alembic heads` → **`0ac943e0da9b (head)`**（**一个**头）；`alembic history` → **4** 行（`<base> → 53e5a548c40e → 0b7da3d20211 → 7f3923d8af84 → 0ac943e0da9b`）✓ **本波不动 schema** |
| 模型 ↔ 迁移残差 diff | 0 | 由 **1606 passed / 0 failed** 的 `tests/db/test_migration_chain.py` 覆盖 ⇒ **0** ✓ |

### 7.3 openapi

| 格 | 基线 | 本波实测 |
|---|---|---|
| 路径 / 操作 / 挂 security / GET / securitySchemes | 74 / 102 / 84 / 63（15 匿名 + 48）/ 3 | **74 / 102 / 84 / 63（15 + 48）/ 3** ✓ 逐格相同 |
| catch-all | 0 | **0** ✓ |
| 未定型响应 | 24 | **24**（判据逐字抄 `tests/test_main.py` 的 `shaped` 那一行；`('/api/health','get')` 在清单里；`/api/health` 的 200 schema 逐字是 `{"additionalProperties": true, "title": "Response Health Api Health Get", "type": "object"}`）✓ |
| `expected` | 26 | 由 `smoke.mjs` 第 12 步的 **129/129** 条断言覆盖，**三档全绿** ✓ |
| JSON 字节 / sha256[:16] | 420 367 B / `6058F97F09B35855` | **420 367 B / `6058F97F09B35855`**，三档 `PE_TRIAL`（未设 / `0` / `1`）**逐字节相同**（不同 sha 的个数 = **1**）✓ **一个字节都没变** |

### 7.4 前端两个静态守卫 + 路由数

| 格 | 基线 | 本波实测 |
|---|---|---|
| 路由 | 16 条（`routes` 数组 20） | smoke 第 14 步「路由条数 = 16」三档全绿；§D7「从磁盘上的 `router/index.ts` 切出 **21** 条路径字面量、dev server 服务出来的那一份缺 **0** 条」✓（⚠️ 本波**一条路由都没加删**） |
| `npm run check:tokens` | 绿（36 / 下界 25） | 绿：**36** 个文件 / 下界 25；`tokens.css` 里 22 处色值字面量；自校 9 负控 + 8 正控 + 3 注释全过；**offender 0** ✓ **一格未退**（本波**一行新 CSS 都没加**） |
| `npm run check:dist`（扫既有 `frontend/dist`，`--no-build`） | 绿（25 产物 / 787 824 字符） | 绿：**25** 个产物 / 扫过 565.3 kB；源码侧 **26 个文件 / 797 626 字符**（基线 787 824 ⇒ **+9 802**，就是本波新写的那些散文与注释）；`adoptFromUrl` **0** 次、两个 CDN 域各 **0** 次、woff2 恰好 **4** 个 ✓ |
| ⚠️ `check-dist` 扫**本波自己那一份构建** | — | **全绿**：25 个产物 / 扫过 **589 118** 字节 / `adoptFromUrl` **0** 次 / 两个 CDN 域各 **0** 次 / woff2 **4** 个 / 三个正控都在（§6.3 那一格修完之后重量的） |
| 新增依赖 | 后端 0、前端 0 | 后端 **0**、前端 **0**（`package.json` 的 `dependencies` 3 个 + `devDependencies` 7 个一格未动）✓ |

### 7.5 ⚠️ `npm run build` 本波**跑了没有**

**没跑。一次都没有。** 派单逐字禁止（它会先清空 `frontend/dist`，而那正是 8030
在发给甲方的产物 ⇒ 几秒的 404 窗口）。**前端这样验的**：

1. **dev 档**：`npm run dev -- --port 5174 --strictPort`（`PE_API_TARGET=http://127.0.0.1:8000`）
   + `demo.ps1 -Port 8000`。⚠️ 每次改完源码都**重起一次 vite**（不是只刷新页面），
   理由逐字写在 `smoke.mjs` 的文件头「前置条件 ②」那一节；
2. **产品档 / 试用档**：把产物构建到**仓库外** ——
   `npx vite build --outDir "$env:TEMP\p07t5b\dist" --emptyOutDir`（退出码 0，`✓ built in 366ms`），
   再用 `serve_app:app` + `PE_STATIC_DIST` 指到那一份产物自己起 uvicorn
   （与 `scripts/serve.ps1` 的 ③ 那一步逐字同一个入口）；
   ⚠️ 于是**既跑到了产品构建、又没碰 `frontend/dist`**；
3. **类型**：`npx vue-tsc -b --force` 退出码 **0**（改前改后各跑过；`tsBuildInfoFile` 在
   `node_modules/.tmp/` 下，`git status` 干净）；
4. **`check:dist`**：见 §7.4 那两行（既有 dist 一遍 + 自己那一份一遍）。

⚠️ 本波那一份构建的产物哈希（**不是**交付的那一份；控制者合并之后重跑
`npm run build` 才会得到它）：
`index-DrDy4l90.css` / `index-DYNl778Q.js` / `StudentDetail-Bw86stl2.js` /
`AuditLogList-CqjFciNR.js` / `ResourceIndex-DqalY3wm.js` / `Dashboard-BW1Md8vq.js`。
⚠️ 而 `frontend/dist` 里那五个哈希与本波开工时派单写的**逐字相同**
（`index-Dm53XXz-.css` / `index-Wfsbvc3G.js` / `StudentDetail-kQIIimXN.js` /
`AuditLogList-CKJ4Vvz4.js` / `ResourceIndex-DqalY3wm.js`）⇒ **一个字节都没动**。

### 7.6 依赖清单守卫 / manifest / 禁区

| 格 | 实测 |
|---|---|
| 四份 manifest + `.gitattributes` + `.gitignore` | 对 `42031de` 的 diff = **0 B**、工作树未提交 diff = **0 B**，逐个：`backend/pyproject.toml` / `frontend/package.json` / `frontend/package-lock.json` / `.gitattributes` / `.gitignore` ✓ **一个字都没改** |
| `backend/pe.db` | **不存在**（`False`）✓ |
| `backend/data/seed/` | **0** 文件（`-Recurse`）✓ |
| `backend/data/**` | `git diff 42031de HEAD -- backend/data` → **0 字节** ✓；目录下的文件总数 **24** ✓ |
| 四个数据指纹（现算 vs 测试里钉住的字面量，两侧不同源） | `national_standard_2014.csv` = **`D2C8E539E2FA0029`** ✓（21 412 B 工作树）；`exercises.yaml` = **`5394B37F01DAC9AC`** ✓（23 247 B）；`exercise_equivalence.yaml` = **`822CB86A5E998301`** ✓（8 245 B）；`alert_rules.yaml` = **`E48E3AC82BB45BB7`** ✓（6 037 B） |
| 18 个模板指纹 | 钉住 **18** 个，现算不符 **0** 个 ⇒ **逐个逐字相同** ✓（口径：LF 归一化后 sha256[:16]，与 `tests/domain/test_prescription_templates.py` 的 `_fingerprint` 同一个函数） |
| 五处 gitignore 项**未入库** | `git ls-files backend/pe_demo.db backend/pe_trial.db frontend/dist backend/backups tools .trial` → **0** 行 ✓；`git check-ignore -v` 逐个命中：`.gitignore:42 backend/pe_demo.db`、`.gitignore:61 backend/pe_trial.db`、`frontend/.gitignore:18 dist/`、`.gitignore:106 tools/`、`.gitignore:116 .trial/`；⚠️ `backend/backups` 那一格 `check-ignore` 不报（规则是 `backend/backups/`，而**目录不存在**时 git 判不出它是目录），规则本身在 `.gitignore:78` ✓ |
| 扫描面 / `_MODELS_PUBLIC_BASELINE` / `_MODELS_SUBMODULES` / 黄金用例 | **72 / 33 / 8 / 14** —— 由 **1606 passed / 0 failed** 那一整套守卫覆盖（`tests/architecture/test_layering.py`、`tests/api/test_column_widths.py`、`tests/db/test_migration_chain.py` 等），本波**一行后端生产代码都没改** ⇒ 逐个照旧 ✓ |

### 7.7 smoke 三档（⚠️ 公网档**刻意未跑**）

| 档 | 后端 | 前端 | 库 | 步数 | 断言 | 退出码 | 用时 |
|---|---|---|---|---|---|---|---|
| **dev** | `app.main:app` @ 8000（`demo_bootstrap.py` 刚灌的 `backend/pe_demo.db`） | vite @ **5174** | `backend/pe_demo.db` | **18/18 全绿** | **739 绿 / 0 红** | **0** | 48.9 s |
| **产品** | `serve_app:app` @ **8020** + `PE_STATIC_DIST=$env:TEMP\p07t5b\dist` | 同一个 uvicorn 同源发**本波自己那一份**产物 | `$env:TEMP\p07t5b\pe_t5b_prod.db` | **18/18 全绿** | **739 绿 / 0 红** | **0** | 47.5 s |
| **试用** | `serve_app:app` @ **8041** + `PE_TRIAL=1` + 同上 | 同上 | `$env:TEMP\p07t5b\pe_t5b.db`（**本波自己灌的**） | **18/18 全绿** | **771 绿 / 0 红** | **0** | 47.5 s |
| 公网 | — | — | — | **未跑** | — | — | 派单逐字要求不跑（它会写脏甲方那份库） |

基线 679 / 679 / 711 / 711 ⇒ 本波 **739 / 739 / 771**，三档各 **+60**，**只增不减**，判据一格都没放宽。

逐拍（三档收尾数字）：`25/7/10/9/7/9/10/41/14/13/17/6/129/72/`**`213`**`/8/72/`**`77`**（dev 与产品），
试用档第 14 步是 **245**（16 条路由各一拍的告示断言 + 2 条总数/档位 = +32）。

⚠️ 试用档那一份 `pe_t5b.db` 是**本波自己灌的**（`demo_bootstrap.py`，与 `demo.ps1` /
`trial.ps1` 同一个生成器），灌完 sha256[:16] = `3125B28E684D98E0`、1 589 248 B；
`/api/health` 实测 `{"status":"ok","tables":28,"students":60,"trial":true}` ⇒
「这是试用档」那一格是**服务侧**给的，不是本波写死的。
⚠️ 姿势与 Task 5 逐字相同（它用的是 `8041 + pe_t5b.db`）。

### 7.8 前端类型 / 构建

| 格 | 实测 |
|---|---|
| `npx vue-tsc -b --force` | 退出码 **0**，零输出（改前改后各跑过；本波共跑 3 次） |
| `npx vite build --outDir <仓库外> --emptyOutDir` | 退出码 **0**，`✓ built in 366ms`，25 个产物 + 4 个 woff2 + 2 个 svg |
| `git status --short`（`vue-tsc -b` 之后） | 只有本波改的那些文件；**没有**任何 `.tsbuildinfo` 一类的中间产物漏进工作树 ✓ |

### 7.9 收尾三格复核 + 本波自己起的进程全停

| 格 | 开工 | 收尾 | 逐字未变？ |
|---|---|---|---|
| 8030 的 listener PID | 21128（`python`） | **21128** | ✓ |
| 隧道 PID | 10128（`cloudflared`） | **10128** 仍在 | ✓ |
| `backend/pe_trial.db` | 1 589 248 B / `40D7B5F78A7C36CB` | 见下（收尾那一次实测） | 见下 |
| `.trial\public-url.txt` | 在（1 472 B） | 见下 | 见下 |
| 5173 上那个不是任何人起的 vite | PID 20240 | **20240** 仍在 | ✓ |

⚠️ 收尾那三格的实际数字见本文件末尾「收尾复核」那一节（本报告写完之后才量，
故不在此处复述 —— 刻意不印自己的字节数/sha，与前两波同一条处置）。

**本波自己起的进程（收尾全停，逐个复核）**：8000 / 8020 / 8041 三个 uvicorn
（都由驱动脚本 `proc.kill()` + `wait()` 停掉，并在日志里各打一行「已停掉 …」）、
5174 那个 vite（`StopCommand`）、以及每次探针起的无头 Edge（`child.kill('SIGKILL')`
+ 等 `exit` 事件 + 删临时 profile）。

### 7.10 spec

| 格 | 基线（`main`） | 本波 |
|---|---|---|
| 字节数 | 569 535 B | **602 189 B**（+32 654） |
| 行数 | 5 429 | **5 770**（+341） |
| 行尾 | 全 CRLF / 0 裸 LF / 无 BOM | **全 CRLF（5 770 个）/ 0 裸 LF / 无 BOM** ✓ |
| sha256[:16]（**工作树**） | `102FE0C623F320E4` | **`87265D1D488D417D`** |
| sha256[:16]（**入库 blob**） | — | 见文末「收尾复核」（`git add` 之后才量） |
| `git ls-files --eol` | `i/lf w/crlf attr/text eol=crlf` | **`i/lf w/crlf attr/text eol=crlf`** ✓ 两个口径都对 |

新增 **§13.18**（8 个小节：13.18.1 缺陷①的取证 / .2 `duration_min` 的口径 /
.3 反静默的共用处置 + 那张 8 行的表单表 / .4 缺陷② / .5 同族自查（含 12 处渲染散文表 +
4 类待清扫）/ .6 **页面正文里不许出现 `check:dist` 的禁用串** / .7 守卫与变异四格 /
.8 关切③），插在 §13.17 之后、§14 之前。

---

## ⑧ 行尾复核 + 说明书要跟着改的那几步

### 8.1 逐个被改文件的 `git ls-files --eol`（两个口径）

| 文件 | 工作树字节 | CRLF | 裸 LF | BOM | `git ls-files --eol` |
|---|---|---|---|---|---|
| `frontend/src/composables/useFormValidity.ts`（**新**） | 14 540 | 241 | 0 | 无 | `i/lf w/crlf attr/` ✓ |
| `frontend/src/views/student/CheckIn.vue` | 36 701 | 835 | 0 | 无 | `i/lf w/crlf attr/` ✓ |
| `frontend/src/views/auth/Login.vue` | 16 708 | 386 | 0 | 无 | `i/lf w/crlf attr/` ✓ |
| `frontend/src/views/auth/Bind.vue` | 19 249 | 475 | 0 | 无 | `i/lf w/crlf attr/` ✓ |
| `frontend/src/views/teacher/StudentDetail.vue` | 82 076 | 1 523 | 0 | 无 | `i/lf w/crlf attr/` ✓ |
| `frontend/src/views/teacher/Dashboard.vue` | 61 099 | 1 292 | 0 | 无 | `i/lf w/crlf attr/` ✓ |
| `frontend/src/views/teacher/ClassReport.vue` | 37 843 | 862 | 0 | 无 | `i/lf w/crlf attr/` ✓ |
| `frontend/src/views/student/Home.vue` | 23 813 | 532 | 0 | 无 | `i/lf w/crlf attr/` ✓ |
| `frontend/src/views/student/Notifications.vue` | 19 598 | 405 | 0 | 无 | `i/lf w/crlf attr/` ✓ |
| `frontend/src/views/student/RpeEntry.vue` | 29 047 | 723 | 0 | 无 | `i/lf w/crlf attr/` ✓ |
| `frontend/src/views/student/WeeklySheet.vue` | 20 565 | 540 | 0 | 无 | `i/lf w/crlf attr/` ✓ |
| `frontend/scripts/smoke.mjs` | 378 155 | 5 290 | 0 | 无 | `i/lf w/crlf attr/` ✓ |
| `Document/2026-09-28-体育闭环原型-设计spec.md` | 602 189 | 5 770 | 0 | 无 | `i/lf w/crlf attr/text eol=crlf` ✓ |
| `.superpowers/sdd/…/task-5b-report.md`（本文件，**新**） | 见文末 | — | **全 LF** | 无 | `i/lf w/lf attr/-text` ✓（口径同目录既有两份） |

⚠️ **每一个文件都是当场核的**（`pe_edit.py` 的 `audit()`：每改完一个文件立刻量
字节数 / CRLF / 裸 LF / BOM / `git ls-files --eol` 两个口径，不等收尾）。
⚠️ 所有编辑一律走 **Python 二进制模式**（`pe_edit.py` 的 `edit()`：读 bytes →
按目标 eol 归一化 → 逐字替换 → **断言恰好命中 1 次**（0 次或多次当场抛）→ 写 bytes），
一次都没用 IDE 的编辑工具改入库文件（行尾/BOM 事故已发生四次）。
⚠️ 新写的 `useFormValidity.ts` 里出过一个 **U+200B（零宽空格）**——那是为了不让
`**/*.vue` 里的 `*/` 提前关掉块注释而临时塞的，当场扫出来并改写成不含 glob 的句子
（`audit()` 里有一格专扫 `200B/200C/200D/FEFF/00A0/2028/2029`）。

### 8.2 ⚠️ 说明书（`p07/trial-guide` 上那一份）要跟着改的步

⚠️ 本波**一次都没写那份说明书**（它在另一个分支上、控制者会在本波之后合并）。
下面三格是本波的修复让它的描述失效或过期的地方，逐字给出改前原文与建议改法
（原文用 `git show p07/trial-guide:Document/2026-10-15-甲方试用说明书.md` 取的，
那份文件 **20 202 B / 160 行**）：

**① 必须改 · 「路线一 · 学生端」第 5 步（第 74 行）**

改前原文（逐字）：

> 5. 点**每日打卡** → 看见本周完成率与「我的打卡记录」14 行（标记列里 `demo` 的是仿真数据灌的，`迟交`、`休息日` 是服务端算的）。⚠️ 这一周每一天都已经有记录了，所以「提交打卡」在试用库上提交不上去 —— 一天一行是这张表的口径，页面自己也写着「再提交会得到 409」。

⚠️ 为什么失效：改前那一句「提交不上去」其实**说对了一半而漏了要害** ——
它不是「交上去被 409 挡回来」，而是**一个请求都没发出去、页面上一个字都没多**
（缺陷 ①）。修好之后，点「提交打卡」**会真的发出请求**、并**看得见**那条 409 提示。
⇒ 建议改成：

> 5. 点**每日打卡** → 看见本周完成率与「我的打卡记录」14 行（标记列里 `demo` 的是仿真数据灌的，`迟交`、`休息日` 是服务端算的）。⚠️ 这一周（以及往前 14 天）每一天都已经有记录了，所以在这些天点「提交打卡」会得到一条**看得见的**提示：「`integrity_conflict · 409` —— 这一天（…）你已经打过卡了：一天只能有一行…」。**那是口径、不是坏了。**
> 6. ⚠️ **想看见「成功」那一次**（建议给甲方演一下）：把「训练日 `log_date`」改成一个库里还没有记录的日期（例如往后一个月），「练了多少分钟」填一个数（**可以带一位小数**，例如 `30.9`），点「提交打卡」→ 出现一个绿色的「**已打卡**」对勾 + 服务端记的时刻，「我的打卡记录」也多出一行（`source` 那一列是 `student`，不是 `demo`）。⚠️ 这一步**会写数据**（要回到干净状态请让我方重灌试用库）。

（⚠️ 若采用，其后各步的编号要跟着 +1。）

**② 建议改 · 「8. 出问题怎么自查」第 3 步（第 157 行）那个括号**

改前原文（逐字，末句）：

> （⚠️ 顶上那条「试用环境」告示也要等一个后台请求回来才挂上：公网链接上实测 **1.5–4 秒**才出现，不是没挂。）

⚠️ 为什么过期：本波重量了一次（两遍，第二遍机器空闲），公网那一次
`GET /api/health` 是 **5.5–6.4 秒**，而告示要等**两次串行**往返 ⇒ 最坏 **≈ 12.7 秒**。
⇒ 建议改成：

> （⚠️ 顶上那条「试用环境」告示**可能晚几秒才出现**，不是没挂：它要等两个后台请求**依次**回来，而这两个请求都要穿过公网隧道。我方 2026-10-15 实测：单次隧道往返 5.5–6.4 秒 ⇒ 告示最坏约 **11–13 秒**才挂上。⚠️ 在它挂上之前**也请勿录入真实学生信息** —— 这套系统今天没有接任何真实数据源。）

**③ 不需要改（但请核一遍）· 「路线二 · 教师端」第 5 步（第 85 行）**

> 5. 点某一条预警里的学生名 → 进到**学生详情**：当前分层 + 可解释性展开、本周训练单（含减量与理由）、班内百分位、他的预警、他的今日。

⚠️ 本波改了学生详情页**第 06 块**的抬头与那两段散文（缺陷 ②），而说明书这一步
**没有引用第 06 块的原文**（它列的是第 01–05 块），故**不需要改**。
⚠️ 但请核一遍：那一条路线点进去的学生**都在 T0001 的任教范围内**（预警队列本来就按
任教范围裁过），故第 06 块会显示「后端确认「本学期任教他」」那一档 —— 那是**真话**。
若说明书里另有让甲方直接打开 `/t/students/<某个 id>` 的步骤（本波 `Grep` 过，**没有**），
则那一格要补一句「不在任教范围内时，第 02/05/06 三块会各说一次同一件真事」。

---

## 收尾复核（本文件其余部分写完之后量的）

### R.1 收尾三格（与 §1.2 的开工三格逐格对账）

| 格 | 开工 | 收尾 | 逐字未变？ |
|---|---|---|---|
| 8030 的 listener | `127.0.0.1:8030` → PID **21128**（`python`，起于 2026-10-15 **19:43:27**） | `127.0.0.1:8030` → PID **21128**（`python`，起于 **19:43:27**，`StartTime` 逐字相同 ⇒ 不是重起过的同号进程） | ✓ |
| 隧道 | PID **10128**（`cloudflared`，起于 **19:43:48**） | PID **10128**（`cloudflared`，起于 **19:43:48**）仍在 | ✓ |
| `backend/pe_trial.db` | **1 589 248 B** / sha256[:16] **`40D7B5F78A7C36CB`** | **1 589 248 B** / **`40D7B5F78A7C36CB`**，⚠️ 而 `LastWriteTime` 也逐字未变（**2026-10-15 19:43:25**）⇒ 它连「被打开来写过」都没有 | ✓ **逐字节相同** |
| `.trial\public-url.txt` | 在（1 472 B） | 仍在（**1 472 B**） | ✓ |

### R.2 本波自己起的进程：全停（逐个复核）

| 端口 | 收尾实测 |
|---|---|
| 8000（dev 档后端） | **没有 listener** ✓ |
| 8020（产品档） | **没有 listener** ✓ |
| 8041（试用档） | **没有 listener** ✓ |
| 5174（本波的 vite） | **没有 listener** ✓ |

⚠️ 无头 Edge：每次探针与每次 smoke 都 `kill('SIGKILL')` + 等 `exit` 事件 + 删临时 profile；
收尾时本机 `msedge` 进程 37 个，全是**用户自己那个浏览器**的（本波起的都用
`--user-data-dir=$env:TEMP\p07t5b*` 的独立 profile，而那些目录已删，见 R.4）。
⚠️ 收尾时本机残留的 `python` 进程只有 **21128**（= 控制者那个 8030 的 uvicorn）。

### R.3 `frontend/dist`（8030 正在发给甲方的那一份）**一个字节都没动**

* **29** 个文件；`index.html` 的 `LastWriteTime` = **2026-10-15 18:53:26**
  （早于本波开工，也早于 8030 起服务的 19:43:27 ⇒ 本波期间一次都没被写过）；
* 派单点名的五个产物哈希**逐个逐字相同**：
  `index-Dm53XXz-.css` / `index-Wfsbvc3G.js` / `StudentDetail-kQIIimXN.js` /
  `AuditLogList-CKJ4Vvz4.js` / `ResourceIndex-DqalY3wm.js` ✓；
* ⚠️ 这就是「`npm run build` 一次都没跑」的**产物面**证据（§7.5 是命令行面的证据）。

### R.4 `$env:TEMP` 的清理与复验

清掉 **7** 个（本波自己造的）：`p07t5b`（探针 + 两个临时库 + 构建到仓库外的那一份产物 +
两个 junction）、`p07t5b-cdp-OecvEQ`、`p07t5b-ck-0gUGK8`（无头浏览器的临时 profile）、
`p07t5b_closeout.py`（清理脚本自己）、`pe_demo_csv_34632` / `pe_demo_csv_38748` /
`pe_demo_csv_48664`（三次跑 `demo.ps1` 留下的 CSV 临时目录 —— ⚠️ `demo.ps1` 刻意
**不**自己删，与 `trial.ps1` 不同，故由本波删）。

复验：

* 本波那几族（`p07t5b*` / `pe_demo_csv_*` / `pe-smoke-cdp-*`）还在的 = **0 个** ✓；
* ⚠️ **控制者的两个一个都没碰**：`pe_trial_csv_41684` **仍在** ✓、`pe_tunnel_8030` **仍在** ✓；
* 本波另建的两个临时库（`pe_t5b.db` / `pe_t5b_prod.db`）都在 `p07t5b` 子目录下，随它一起删了 ⇒
  `$env:TEMP` 根下 **0 个** ✓。

### R.5 ⚠️ 一处如实交代：5173 上那个 PID 20240 的 vite，收尾时**不在了**

派单逐字写着「5173 上另有一个不是任何人起的 vite（PID 20240），也不要杀」。
收尾复核时 `Get-Process -Id 20240` **查不到它**、`Get-NetTCPConnection -LocalPort 5173`
也**没有 listener**（本机残留的 node 进程是 14368 = `npx @deepseek-ai/dsh web`
与 16404 = 3080 上那个，都与本波无关）。

**本波对它下过的指令：0 次。** 逐个复核本波所有会停进程的地方：

| 处置 | 目标 | 有没有可能碰到 20240 |
|---|---|---|
| `StopCommand` ×6 | 逐字都是本波自己起的 **5174 vite**（4 次）与 **8000 上的 `demo.ps1`**（2 次），命令 ID 分别是 `job-04a49d7b…` / `job-ab5e5654…` / `job-ea49cdb4…` / `job-33e32dc1…` / `job-8ec0aa6a…` / `job-e8436d69…` | 不可能（它不是本波起的，本波拿不到它的命令 ID） |
| 变异驱动里的 `kill_port(8000)`（`taskkill /PID <pid> /T /F`） | **只对监听 8000 的那个 PID 及其子树**生效，每次调用前都先把那个 PID 打进日志（实测 `37196` 一个） | 不可能（20240 监听的是 5173，且它不在 8000 那个进程树里） |
| 无头浏览器的 `child.kill('SIGKILL')` | 本波 `spawn` 出来的那几个 `msedge` | 不可能 |

⚠️ 而本波**无法证明**它与本波无关（例如「工具在复用同一个终端时把别的进程一起收了」
这一档本波无从取证）。⇒ **如实记，请控制者核一下要不要重起它。**
⚠️ 它**不影响甲方那条路线**：8030 与隧道两格逐字未变、`pe_trial.db` 连
`LastWriteTime` 都没变、`frontend/dist` 的 29 个文件与五个哈希逐字未变（R.1/R.3）。
⚠️ 而本波**一次都没依赖过 5173**：dev 档的前端一律是本波自己起在 **5174** 上的那一个
（`--strictPort`，故它绝不会退回 5173）。

### R.6 工作树 / 入库 / git 的最终状态

| 格 | 实测 |
|---|---|
| `git status --short` | 干净（本 commit 之后） |
| 本波的 commit | `b86645d` → `21b55b7` → `41b7b91` → `553abcd` → **（本 commit）** |
| `git diff 42031de HEAD --stat` 的文件数 | **14** 个（1 个新增 `.ts` + 10 个 `.vue` + `smoke.mjs` + spec + 本报告） |
| `git diff 42031de HEAD -- backend/data` | **0 字节** ✓ |
| `backend/pe.db` | **不存在** ✓ |
| `backend/data/seed/` | **0** 文件 ✓ |
| 四份 manifest + `.gitattributes` + `.gitignore` | 对 `42031de` 的 diff = **0 B** ✓（依赖清单守卫一字不红） |
| 五处 gitignore 项入库的 | **0** 行 ✓ |
| 本报告（`.superpowers/**` = `-text`） | 工作树 **纯 LF / 0 个 CRLF / 无 BOM / 0 个不可见字符**；⚠️ **刻意不印自己的字节数与 sha**（不动点问题，前两波同一条处置）；入库 blob 与工作树字节是否一致由下面那一格回答 |
| 工作树字节 == 入库 blob | 见下方「R.7」 |

### R.7 工作树字节 vs `git cat-file -s`（逐个被改文件）

⚠️ `git add` 之后量；两个数逐格相同即「入库 blob 与工作树字节一致」。
⚠️ `.ts` / `.vue` / `.mjs` 那一族因为 `core.autocrlf=true` 会做 CRLF→LF 的归一化，
故这里比的是**入库 blob 的字节数** vs **工作树字节数按同一口径归一化之后**的字节数，
两个口径都印出来。spec 那一份 `attr/text eol=crlf`，入库同样是 LF。
⚠️ 取文件名一律用 `git -c core.quotepath=false`：不加它的话中文路径会被八进制转义
（`\\345\\256\\236…`），于是「按名字读回工作树那一份」当场 `FileNotFoundError`（本波实测踩过）。

改动面 **14** 个文件，逐个：

| 文件 | 工作树 B | CRLF / 裸 LF | 归一化后 B | 入库 blob B | 一致？ | blob sha256[:16] | `git ls-files --eol` |
|---|---|---|---|---|---|---|---|
| `frontend/src/composables/useFormValidity.ts`（新） | 14 540 | 241 / 0 | 14 299 | 14 299 | ✓ | `A20376416F222699` | `i/lf w/crlf attr/` |
| `frontend/src/views/student/CheckIn.vue` | 36 701 | 835 / 0 | 35 866 | 35 866 | ✓ | `84C1AA9409EB767B` | `i/lf w/crlf attr/` |
| `frontend/src/views/auth/Login.vue` | 16 708 | 386 / 0 | 16 322 | 16 322 | ✓ | `A68AA87CF4B24FE0` | `i/lf w/crlf attr/` |
| `frontend/src/views/auth/Bind.vue` | 19 249 | 475 / 0 | 18 774 | 18 774 | ✓ | `F6A448A538EBCF38` | `i/lf w/crlf attr/` |
| `frontend/src/views/teacher/StudentDetail.vue` | 82 076 | 1 523 / 0 | 80 553 | 80 553 | ✓ | `DDE6E0FF401B12A9` | `i/lf w/crlf attr/` |
| `frontend/src/views/teacher/Dashboard.vue` | 61 099 | 1 292 / 0 | 59 807 | 59 807 | ✓ | `81E317829DDE671C` | `i/lf w/crlf attr/` |
| `frontend/src/views/teacher/ClassReport.vue` | 37 843 | 862 / 0 | 36 981 | 36 981 | ✓ | `76361DA0FEFE5D1D` | `i/lf w/crlf attr/` |
| `frontend/src/views/student/Home.vue` | 23 813 | 532 / 0 | 23 281 | 23 281 | ✓ | `587BBECD4E1CA41B` | `i/lf w/crlf attr/` |
| `frontend/src/views/student/Notifications.vue` | 19 598 | 405 / 0 | 19 193 | 19 193 | ✓ | `8C9CC4B1C3A150FF` | `i/lf w/crlf attr/` |
| `frontend/src/views/student/RpeEntry.vue` | 29 047 | 723 / 0 | 28 324 | 28 324 | ✓ | `4AA6E68CBCC45EAB` | `i/lf w/crlf attr/` |
| `frontend/src/views/student/WeeklySheet.vue` | 20 565 | 540 / 0 | 20 025 | 20 025 | ✓ | `F4607199F2021FFB` | `i/lf w/crlf attr/` |
| `frontend/scripts/smoke.mjs` | 378 155 | 5 290 / 0 | 372 865 | 372 865 | ✓ | `B3E8B06AB00C0B5A` | `i/lf w/crlf attr/` |
| `Document/2026-09-28-体育闭环原型-设计spec.md` | 602 189 | 5 770 / 0 | 596 419 | 596 419 | ✓ | `062E6719A481D357` | `i/lf w/crlf attr/text eol=crlf` |
| 本报告 | 见下 | 0 / 全 LF | — | — | ✓ 工作树字节 == 入库 blob | ⚠️ **刻意不印**（不动点问题，前两波同一条处置） | `i/lf w/lf attr/-text` |

⚠️ **14 个文件逐个「归一化后 == 入库 blob」，0 个不同**；两个口径也都对：
`.ts/.vue/.mjs` 与 spec 是 `i/lf w/crlf`（本机 `core.autocrlf=true`），
本报告是 `i/lf w/lf attr/-text`（`.superpowers/**` 那一条规则）。

⚠️ **spec 的两个口径**：工作树 **602 189 B / 5 770 行 / 全 CRLF（5 770 个）/ 0 裸 LF / 无 BOM /
sha256[:16] `87265D1D488D417D`**；入库 blob **596 419 B / sha256[:16] `062E6719A481D357`**
（差的 5 770 字节逐字就是那 5 770 个 `\r`）。

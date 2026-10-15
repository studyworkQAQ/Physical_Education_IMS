# 实施计划 07 · Task 1 + Task 2 实现者报告（试用档基座 + 局域网档）

> 分支 `p07/trial`，起点 `a40db5a`（= 计划文档那一个 commit）。
> 本机 2026-10-15 亲跑；一切数字都是**实测**，不是从代码推的（硬规矩 #89/#103/#107/#109/#111）。
> ⚠️ 本文件按 `.superpowers/** -text` 的口径写：**纯 LF、无 BOM**，故工作树字节 == 入库 blob 字节。

## 0. 五个 commit

| # | sha | 一句话 | 自洽吗 |
|---|---|---|---|
| 1 | `a49c6e5` | `feat(deploy)`：`app.deploy.is_trial()` + `/api/health` 的第四格 `trial` + openapi 取证 + 守卫（含 `types.ts` 的 `HealthRead` 与重生成的 `schema.d.ts`） | ⚠️ **一格不自洽**：`smoke.mjs` 第 1 步的「响应恰好 3 个键」要到 commit 4 才跟上，故本 commit 上 `npm run smoke` 会红 1 条（pytest 全绿不受影响） |
| 2 | `1a1b8cf` | `feat(scripts)`：`scripts/trial.ps1`（灌库 + 委托 + `-Reset`）+ `serve.ps1` 的 `-Lan` + `.gitignore` 四行 + `tests/test_trial.py`（10 条）+ `tests/test_serve.py`（更新 3 条、新增 1 条） | ✅ 自洽（pytest 全绿；⚠️ 而 `-Reset` 撞上被持有的库时会停在一段 PowerShell 原文报错上，commit 3 修掉） |
| 3 | `a86bfaa` | `fix(scripts+guards)`：定点变异与真起服务抓到的三处 —— `-Lan` 告示的 needle 歧义、`-Reset` 的顺序（占用检测提到取证之前）+「谁持有它」按进程找、`demo.ps1` 那句「/api/health 只有那三格」的假话 | ✅ 自洽 |
| 4 | `6a30e49` | `feat(frontend)`：`App.vue` 的试用告示（一处住址）+ `smoke.mjs` 的第三档与四拍新断言 | ✅ 自洽（三档 smoke 全绿） |
| 5 | 本 commit | `docs(spec)+report`：spec §13.16（7 小节）+ 本报告 | ✅ |

⚠️ 派单建议的是 5 个 commit，本波也是 5 个，而**切法不同**：派单的 ①（deploy）②（告示）
③（trial.ps1）④（serve.ps1 -Lan）⑤（smoke + spec + 报告）里，③ 与 ④ 合成了一个 commit、
而「定点变异抓到的修正」单独成了一个。理由是**自洽性**：`tests/test_serve.py` 里
「仓库根 `scripts/` 的清单」与「`.ps1` 从 4 个变 5 个」两拍同时被 `trial.ps1` 与
`serve.ps1 -Lan` 需要，拆开的话前一个 commit 上它们是红的。

---

## 1. 环境 + 基线复核

```
node v24.19.0 · npm 11.17.0 · Python 3.11.1（无 venv，C:\Python\python.exe）
分支 p07/trial · HEAD（开工时）a40db5a · 工作树干净
```

**开工实测的基线**（本波自己量的，不是抄派单）：

| 项 | 实测 |
|---|---|
| `backend/pe.db` | **MISSING** ✓ |
| `backend/pe_demo.db` | EXISTS **1 597 440 B** sha256[:16]=`51A3214C5D32BEF3`（⚠️ 脏的：派单说的干净态是 1 589 248 B / `8593924853855627`） |
| `backend/data/seed/` | **0 文件** ✓ |
| spec 工作树 | **522 729 B / 4 868 行 / 4 868 CRLF / 无 BOM**，sha256[:16]=`C7FB8050332B4536` |
| spec LF 归一 | **517 861 B**，sha256[:16]=`CFE1163ABB5E4621` |
| spec 入库 blob | `6a86d1ab…` / `git cat-file -s` = **517 861 B** / sha256[:16]=`CFE1163ABB5E4621`（与 LF 归一逐字相同 ✓） |
| `/api/health`（缺省档） | `{"status":"ok","tables":28,"students":0}` |
| `/openapi.json` | **417 032 B** sha256[:16]=`4C8123A9A8903753` |
| openapi 五格 | 路径 **74** / 操作 **102** / 挂 security **84** / GET **63**（匿名 **15** + 挂 security **48**）/ securitySchemes **3** |
| 未定型响应 | **24**（判据：200 响应的 schema 里没有 `$ref`/`items`/`properties`/`allOf`/`anyOf`/`oneOf`）= 23 个泛型 list + `/api/health` |
| 迁移链 | **4 条单头** `53e5a548c40e → 0b7da3d20211 → 7f3923d8af84 → 0ac943e0da9b` |
| 本机 LAN IPv4 | **192.168.31.11（WLAN）**，`Get-NetIPAddress` 过滤 `127.*`/`169.254.*` 之后**恰好 1 个** |
| 5173 | PID **20240**（⚠️ 不是本波起的，全程没动它） |

**`demo.ps1` 的灌库入口（实测）**：

```
python scripts/demo_bootstrap.py --db-url $DbUrl --csv-dir $CsvDir --students $Students --seed $Seed
```

⚠️ 它**不是** `app.seed`，也**不是**那三个禁跑 CLI。`--students` / `--seed` 的 argparse
缺省是 **60 / 20250828**（与 `demo.ps1` 那两个 `[int]` 参数的缺省逐字相同）。
⚠️ 而 `demo.ps1` 的灌库与起服务**是耦在一起的**（④ 灌完就 ⑥ `python -m uvicorn`），
但它有第三个选项可用：**派单 §1.2 第 2 条给的第三条路**「直接从 `trial.ps1` 调它调的那个
Python 入口」——`trial.ps1` 走的就是这一条，故**不需要**给 `demo.ps1` 加 `-SeedOnly`
（顶回 0 处，见 §7）。

**`serve.ps1` 开工时的参数面（实测）**：`param([int]$Port = 8020, [switch]$SkipBuild)`；
`$Base = "http://127.0.0.1:$Port"`；uvicorn 的 `--host` 逐字写死 `"127.0.0.1"`；
`PE_DB_URL` 未设 → `python -c 'from app.main import DEMO_DB_URL;print(DEMO_DB_URL)'`；
`PE_STATIC_DIST = $Dist`（绝对路径只在本文件里算一次）。

---

## 2. 档位设计

### 2.1 `is_trial()` 的三档 + raise

住址：`backend/app/deploy.py`（它今天已经是 `PE_ENV` / `cookie_secure()` /
`allow_header_identity()` 的住址）。新增 `TRIAL_ENV_VAR = "PE_TRIAL"` / `TRIAL_ON = "1"` /
`TRIAL_OFF = "0"` / `is_trial()`。

| `PE_TRIAL` | `is_trial()` | 备注 |
|---|---|---|
| 未设 / `""` / `"   "` / `"\t"` | `False` | 缺省**不是**试用档（开发档与产品档因此不挂告示） |
| `"0"` / `" 0 "` | `False` | |
| `"1"` / `" 1 "` / `"\t1\n"` | `True` | 先 `strip().lower()` 规范化，与 `tier()` 同一条口径 |
| `true` `TRUE` `yes` `on` `false` `FALSE` `no` `off` `2` `01` `1.0` `trial` `demo` `" 1 1 "` | **`ValueError`** | 14 个值逐个点名测；⚠️ `false` 是最吃紧的一档（它**看起来**是「关」，而本仓只认 `"0"`，故它抛而不是安静地当成关） |

⚠️ **失效方向是「起不来」**：`create_app()` 在装配期问一次 `is_trial()`（返回值刻意丢掉），
而 `app.main` 有一条模块级的 `app = create_app()` ⇒ `uvicorn app.main:app` 在一个坏
`PE_TRIAL` 下**根本起不来**。守卫 `test_an_unrecognised_pe_trial_refuses_to_build_an_app`
按 `yes` / `2` / `false` 三个值各断一次。
⚠️ 请求期也响亮：装配期那一次被绕过的话（`create_app` 之后才 `setenv` 一个坏值），
`GET /api/health` 回 **422 `unprocessable_value`** 且 `message` 点名 `PE_TRIAL` 与收到的原文。

⚠️ **它与 `PE_ENV` 正交，刻意不做 `TIER_VALUES` 的第三个值**。守卫
`test_the_trial_switch_is_orthogonal_to_the_tier` 把 **2 × 3 = 6 种组合**各断一遍
（`tier()` / `is_prod()` / `is_trial()` 三格）。少了它，「有人把 `is_trial()` 写成
`tier() == DEV`」是绿的 —— 而那会让**每一个**开发档都挂上试用告示（一条假话），
同时让 `prod` 下的试用实例**不挂**（漏掉真话）。

### 2.2 `/api/health` 改前改后的响应体（逐字）

```
改前（PE_TRIAL 未设）    {"status":"ok","tables":28,"students":0}
改后（PE_TRIAL 未设）    {"status":"ok","tables":28,"students":0,"trial":false}
改后（PE_TRIAL=0）       {"status":"ok","tables":28,"students":0,"trial":false}
改后（PE_TRIAL=1）       {"status":"ok","tables":28,"students":0,"trial":true}
```

### 2.3 ⚠️⚠️ openapi 的取证：**「逐字节不变」那半句是假的**（顶回 ①）

派单 §1.3 的理由是「它是 24 个未定型响应之一 ⇒ openapi 五格一个字节都不会变」。
**五格那半句成立，「一个字节都不会变」那半句不成立。**实测：

| | 改前 | 改后 | 差异 |
|---|---|---|---|
| `/openapi.json` 字节 | **417 032** | **420 367** | **+3 335** |
| sha256[:16] | `4C8123A9A8903753` | `6058F97F09B35855` | 变了 |
| 摊平后的叶子数 | 4 520 | 4 520 | **0** |
| 摊平后**不同**的叶子 | — | — | **恰好 1 个** = `/paths//api/health/get/description`（1 165 → 3 228 字符） |
| 路径 / 操作 / 挂 security / GET（匿名+挂） / securitySchemes | 74 / 102 / 84 / 63（15+48）/ 3 | **74 / 102 / 84 / 63（15+48）/ 3** | **一格都没变** |
| 未定型响应 | 24 | **24**（`/api/health` 仍在里面） | 0 |
| `/api/health` 的 200 响应 schema | `{"additionalProperties": true, "title": "Response Health Api Health Get", "type": "object"}` | **逐字相同** | 0 |

**根因**：FastAPI 把端点的 **docstring** 渲染成 operation 的 `description`（本仓早就知道
这一格 —— `test_health_and_openapi_never_leak_the_deployment_tier_to_an_anonymous_caller`
的 docstring 第一节逐字记着它）。而 `health` 的 docstring **必须改**：它的第一行逐字写着
响应体的形状，加了第四格而不改它，就是「账面与实物相反」（本仓花了 198 次控制者错误
才学会去核的那一族，Plan 06 终审 S3-① 就是这个形状）。

**连带后果（已处置）**：`frontend/src/api/generated/schema.d.ts` 重跑了一次
`npm run gen:api`，**+45 / −1 行**（527 633 B → 531 599 B），差异全在那一段 JSDoc。
「产物不许漂」的守卫是 `tests/api/test_prescription_api.py` 的
`test_the_generated_typescript_client_matches_the_current_openapi_document`（改完立刻绿）。
⚠️ 而 `openapi-typescript` 写出的产物是 **LF**，本波照 Plan 06 Task 13 的姿势把工作树
**还原成 CRLF**（531 599 B / 0 个裸 LF，`git ls-files --eol` = `i/lf w/crlf`）；
入库 blob 两个口径逐字相同（`core.autocrlf=true` 会归一）。

**给「有型 schema」那一档的成本对比**（派单要我核的另一半）：给 `/api/health` 挂一个
Pydantic `response_model` 会让未定型响应 **24 → 23**，于是
① `frontend/src/api/types.ts` 文件头那份**逐端点**的 24 行清单要改（它是那一格的唯一住址）；
② `smoke.mjs` 第 1 步与 `endpoints.ts` / `types.ts` 里 5 处「24 个未定型响应」的散文要改；
③ `HealthRead` 从手写变成 `S['HealthRead']` 的别名，而它与 23 个 list 类型的
「`*Read` 减 `list_exclude`」那条口径不同族，会多一档例外；
④ openapi 的字节**照样会变**（docstring 仍然要改）。
⇒ **换不到任何东西**，故本波**不给**它有型 schema（顶回 ①，理由逐字如上）。

### 2.4 「openapi 逐字节不变」做不成常驻守卫（顶回 ③）

派单 §1.6 ③ 要「把 openapi 逐字节不变的取证做成常驻守卫」。⚠️ **它做不成**，而理由与
上面同一条：任何一次对 `health` docstring 的修改都会让「与一份快照逐字节相同」红，
而修它的人唯一的出路就是**删掉说明文字**（硬规矩 #109 的形状）。故常驻守卫钉的是
三格**性质**（`tests/test_main.py` 的 `test_the_trial_switch_never_touches_the_openapi_document`，
对 docstring 的措辞完全不敏感）：

1. **三档 `PE_TRIAL`（未设 / `0` / `1`）下 `/openapi.json` 逐字节相同**
   —— 实测三份都是 **420 367 B / `6058F97F09B35855`**。⚠️ 每档**新建一个 app**：
   FastAPI 把结果缓存在 `app.openapi_schema` 上，复用会让断言**恒真**（硬规矩 #50）；
   ⚠️ 走 HTTP 而不是 `app.openapi()`（要钉的是**端点发出来的那份字节**，
   与 `dump_openapi.py` 的同名守卫同一条口径）；
2. 五格 + 「24 个未定型」按字面钉住（`OPENAPI_CELLS`）；
3. `/api/health` 的响应 schema 逐字仍是 `HEALTH_UNTYPED_SCHEMA`
   ⇒ 「给那个 dict 加一格是免费的」这句话有可执行依据，不是一句推断。

⚠️ 而「档位不泄漏给匿名」那一条被**加强**：两档 `PE_ENV` 现在要在**同一个** `PE_TRIAL`
下比（本条一律 `PE_TRIAL=1`）。这一格是承重的 —— `trial` 本身随 `PE_TRIAL` 变，
两侧不同值的话「逐字节相同」会因为一个**与档位无关**的格子而红，而修它的人很可能
顺手把 `trial` 从响应里删掉（于是页面告示静默失效）。同时加断「`/api/health` 的响应体里
`"dev"` / `"prod"` 两个字面值都不出现」（⚠️ 只打在 health 上、不打在 openapi 上：
端点 docstring 里**逐字提及**了 `PE_ENV=prod` 一类的机制名，搜词会假红）。

### 2.5 前端那一次调用是**新增**的，不是复用

实测：`frontend/src/api/endpoints.ts` 的 `getHealth()` **有定义、0 个调用点**
（全仓 `getHealth` 只命中 `endpoints.ts` 的定义与它的 import；`api/health` 的其余命中
全是散文提及）。故 `App.vue` 那一次是**新增的一次**，一次挂载只打一次、不随路由重打
（档位是**进程事实**，不是页面事实）。

⚠️⚠️ **它排在 `await session.ensureRestored()` 之后** —— 这一行是承重的，而它是
**本波在产品档上实测撞出来的**：第一次跑产品档 smoke 时 §I5 红了，
`actual=/api/health expected=/api/auth/me`。根因：**产品档**的 `main.ts` 是**同步**
`mount()`（只有 DEV 那一支先 `await ensureRestored()`），故 `App.vue` 的 `onMounted`
抢在路由守卫之前跑。⚠️ 它今天**无害**（`/api/health` 匿名、一个身份都不看，
而生产构建里 `identityHeaders()` 恒回空对象），但「无害」是巧合不是契约，
而**放宽那条终审守卫**等于把 I5 重新打开一条缝（硬规矩 #92：不许为了让新代码通过而
放宽既有判据）。⚠️ **成本是零**：`ensureRestored()` 缓存 in-flight 的 Promise
（`stores/session.ts` 文件头逐字写着「只发一次」），故不多打一次 `/api/auth/me`。
⚠️ 代价如实记：告示晚一帧出现（会话恢复回来之后），最坏晚 `RESTORE_TIMEOUT_MS`。
⚠️ 而定点变异 **M2b** 反过来证明了这一格：那一遍把告示挪进一个**没有**这一行的子组件，
§I5 当场又红了。

---

## 3. 页面告示

* **住址**：`frontend/src/App.vue`，一条 `<p v-if="trial" class="trial-note" role="status">`，
  排在 `.body` 里、报头之下、`IdentitySwitcher` 之上 ⇒ **16 条路由都看得见**
  （含 `/login` 与 `/bind` 两条匿名路由 —— 那正是试用者最先落地的两页）。
* **文案原文**（渲染出来是这一行，`toPlainText` 之后）：

  ```
  试用环境 · 数据为高保真仿真（60 名学生均为虚构） · 请勿录入真实学生信息
  ```

  ⚠️ 那个 **60 取自 `/api/health` 的 `students`**（一次真查询的结果），**不写死**：
  `demo_bootstrap.py --students` 可以改它，而写死就是那个数的第二个所有者
  （改一处漏一处，漏的那一处**印在页面上**）。守卫是 smoke 第 14 步那一拍
  「告示里的 N == `/api/health` 的 `students`」（DOM vs HTTP，两侧不同源）。
* **用的哪个既有类 / 新增 CSS 几行**：⚠️ **没有可复用的既有类**（实测过三个候选）：
  `.switcher__warn`（`IdentitySwitcher.vue`）是 `<style scoped>` 的 ⇒ 跨组件用不到；
  `.t-block__note`（`teacher.css`）与 `.s-block__note`（`student.css`）虽然全局，
  却**带端前缀** ⇒ 把 `.t-` 挂到学生端那 6 条路由上是第二个所有者。
  故 `App.vue` 自己的 `<style scoped>` 里加了 **`.trial-note` 一条规则 / 5 个声明 / 7 行**
  （含 1 行选择器与 1 行右括号），⚠️ **零个新色值**：`--space-2` `--space-3`
  `--amber-faint` `--amber` `--radius` `--fs-small` 全是既有 token，与 `.switcher__warn`
  同一组。`npm run check:tokens`：扫描面 **36**（下界 25，一格没退）、offender **0**、退出码 0。
* **DOM 守卫的实测**（试用档，16 条路由逐条）：**重叠 0 处 / 非故意横向溢出 0 处 /
  整页 `scrollWidth` ≤ `innerWidth`** 全绿。样例四行：

  ```
  login           叶子  58 · 重叠 0 · 溢出 0 · scrollWidth 1440 / innerWidth 1440
  bind            叶子  74 · 重叠 0 · 溢出 0 · scrollWidth 1440 / innerWidth 1440
  s-home          叶子 111 · 重叠 0 · 溢出 0 · scrollWidth  375 / innerWidth  375
  s-weekly-sheet  叶子 241 · 重叠 0 · 溢出 0 · scrollWidth  360 / innerWidth  375
  ```

  ⚠️ 关键是它**不是** `fixed`/`sticky`，而是普通流里的一格 —— 一条固定横幅最容易犯的
  就是遮住内容或与报头重叠，而判据一字没放宽（硬规矩 #92）。
* **字节地板三档各是多少**（`document.documentElement.outerHTML` 的字节，前四条路由）：

  | 路由 | dev 档（地板 **20000**） | 产品档（地板 **6000**） | 试用档（地板 **6000**） |
  |---|---|---|---|
  | `login` | 188 732 | 9 343 | **9 607** |
  | `bind` | 187 635 | 10 010 | **10 274** |
  | `s-home` | 193 097 | 14 835 | **15 099** |
  | `s-weekly-sheet` | 199 942 | 22 267 | **22 531** |

  ⚠️ 试用档比产品档**恰好每条多 264 字节**（就是那条告示），三档全部远高于各自的地板。
  ⚠️ 试用档是**产品构建**（`dist` 由 uvicorn 同源发），故它的档位判定落在 `prod` 那一档、
  地板取 6000 —— 「试用档」与「构建档」是两件事（前者由 `PE_TRIAL` 定，后者由
  `/@vite/client` vs `src="/assets/` 两个 DOM 标记定）。
* ⚠️ **没有改任何既有 needle**：告示的 needle 用的是 `请勿录入真实学生信息`
  （实测在 `src/**` 的代码里**只有 `App.vue` 一个文件**含它），与既有 16 条路由的
  needle 一个都不撞；而它在正文里**恰好 1 处**由第 14 步逐条断言。

---

## 4. `scripts/trial.ps1`

* **灌库走哪个入口**：`python scripts/demo_bootstrap.py --db-url $TrialDbUrl --csv-dir $CsvDir`
  —— 与 `demo.ps1` **同一个** Python 入口（⚠️ 不写第二个灌库器）。
  ⚠️ `--students` / `--seed` **刻意不传**：缺省 60 / 20250828 的唯一所有者是那个脚本的
  argparse，在这里再敲一遍就是第二个所有者（守卫按「灌库那一行不含这两个参数名」钉住；
  ⚠️ 判据只打在**那一行**上，因为 ③ 那一步有一句 `Write-Host` 逐字**提及**了它们 ——
  提及不是本身，硬规矩 #109；本波首跑就在这一格上红过一次）。
  ⚠️ 三个禁跑 CLI 一次都不**被调用**（判据是「调用形状」`-m app.` / `python -m `，
  不是「模块名出现过」：① 那一句 `throw` 的报错里逐字解释了 `pe.db` 的语义
  =「`app.seed.generate` 写出来的那份不可复现的库」，那是提及；本波首跑也在这一格红过）。
* **怎么委托 `serve.ps1`**：`& powershell -NoProfile -ExecutionPolicy Bypass -File $ServePs1 -Port "$Port"`
  （`-Lan` 只在给了旗标时才追加）。⚠️ **不用 `&` 调用运算符**：`serve.ps1` 末尾有一句
  `exit $Code`，另起一个进程让退出码走 `$LASTEXITCODE` 这条**明确**的路。
  环境变量是进程级的（`$env:PE_DB_URL` / `$env:PE_CSV_DIR` / `$env:PE_TRIAL`），
  子进程照继承。⚠️ 三个赋值都**排在委托之前**（守卫按 `code.index()` 的大小钉住：
  子进程继承的是本进程当时的环境块，设晚了等于没设）。
  ⚠️ **`serve.ps1` 的缺省行为一格没改**：本波只给它**加**了一个 `-Lan` 旗标；
  不加旗标时它的输出与行为与 Plan 06 Task 7 那一版逐字相同（实测见 §5）。
* **`-Reset` 的删前取证与占用检测**（⚠️ 顺序是承重的，守卫按 `index()` 钉住）：
  1. **占用检测**：对四个后缀逐个试一次 `[System.IO.File]::Open(..., FileShare.None)`。
     SQLite 打开库时给的是 `FILE_SHARE_READ|WRITE`，故一个活着的 uvicorn 会让它抛。
     ⚠️ 被持有 ⇒ 报一句人话 + `exit 1`、**不硬删**。实测原文（本机亲跑，
     在 8030 上有一个活着的试用档时跑 `trial.ps1 -Port 8031 -Reset`）：

     ```
     -- ② -Reset：删掉旧试用库 --

        ⚠️ 删不掉：C:\...\backend\pe_trial.db 正被别的进程持有（独占打开失败）。
           本机上有 1 个 python 进程正在监听端口，最可能是其中之一：PID 17452（127.0.0.1:8030）
           本脚本**不硬删**：在一个还开着的 SQLite 库上删文件，得到的是一份半截的库，
           而下一次起服务时 alembic 会在离真因很远的地方炸。
           处置：先停掉那个进程（Ctrl-C 掉正在跑的 trial.ps1 / serve.ps1，或 Stop-Process -Id <PID>），再重跑本脚本。
     ```
     （退出码 **1** ✓）
  2. **删前取证**：路径 + 字节数 + `sha256[:16]` + 改动时刻，四个后缀逐个。实测原文：

     ```
        删之前先取证（1 个文件）：
          C:\...\backend\pe_trial.db   1597440 B   sha256[:16]=3C82EE5112CD7A65   改于 10/15/2026 15:50:49
        删掉 C:\...\backend\pe_trial.db
        复核：四个后缀一个都不在了 ✓
     ```
  3. 删 + 复核（`Test-Path` 逐个）。

  ⚠️⚠️ **① 必须排在 ② 之前，而这一格是本波实测踩到的**：`Get-FileHash` 要**读**那个文件，
  而一个被持有的 SQLite 库读不出来（原文 `The process cannot access the file … because it
  is being used by another process`，一个 `FileReadError`），而脚本第一行是
  `$ErrorActionPreference = "Stop"` ⇒ 它会**停在一段 PowerShell 原文报错上**，
  那一句人话永远打不出来（退出码虽然仍是 1，而「报一句人话」那一格是空的，离真因有一层）。
  守卫 `test_trial_ps1_reset_prints_what_it_deletes_and_refuses_a_file_someone_holds`
  因此加了一拍「占用检测排在 `Get-FileHash` 之前」。
  ⚠️ 同一波还把「谁持有它」的判据从「本次 `-Port` 上有没有 listener」换成
  「**python 进程 ∩ 正在监听的 PID**」：持有者通常是**另一个** `trial.ps1` / `serve.ps1`
  起的 uvicorn，它的端口与本次 `-Port` 无关（改前在 `-Port 8031 -Reset` 上打印的是
  「端口 8031 上没有 listener」—— 一句真话，而对要处置它的人一点用都没有）。
* **缺省复用、`-Reset` 才删**：甲方试用一定会写脏它（绑定、打卡、快评、预警处置），
  而同一天里反复重跑本脚本**不该**把他们刚敲进去的东西冲掉。
* **禁区守卫**（⚠️ 不写第二套判据，逐字照既有脚本切）：
  * `if (Test-Path $ForbiddenDb) { throw … }` —— 照 `demo.ps1` 的 ⑤；
  * `if ($TrialDbUrl -match '(^|/)pe\.db$') { throw … }` —— **正则与 `serve.ps1` 的 ③a 逐字同形**；
  * 灌库**之后**再复核两个禁区（`pe.db` 不存在 + `data\seed` 带 `-Recurse` 仍 0 文件）；
  * 而 `demo_bootstrap.py` 自己还有两道前置守卫 ⇒ 合计 **6 道**。
  * ⚠️ 实测亲验：`trial.ps1` 跑完之后 `backend/pe.db` **仍不存在**、`backend/data/seed/`
    **仍 0 文件**（脚本自己印一行 `禁区复核：… ✓`，本波也在外面独立复算过一遍）。
* **BOM / CRLF**：`scripts/trial.ps1` = **22 080 B / 330 CRLF / 0 个裸 LF / BOM=True**，
  `git ls-files --eol` = `i/lf w/crlf attr/text eol=crlf`（⚠️ `.gitattributes` 的
  `scripts/*.ps1` 那一条盖得到它，因为 `*` 不跨 `/` 而它与 `serve.ps1` 同一层）。
  ⚠️ 另外用 `System.Management.Automation.Language.Parser::ParseFile` 核过
  **解析 0 错误**（前几波剥掉过 BOM 四次，每次都当场解析失败，故本波每改一次就核一次）。
* **试用库的名字只有一个所有者**：`$TrialDbName = "pe_trial.db"`。
  ⚠️ `app/main.py` 里**刻意没有** `TRIAL_DB_URL` 常量（Python 侧一个消费者都没有 ⇒ 死配置），
  而「与 `.gitignore` 那四行不许漂开」由守卫做**三方对账**（脚本 / `.gitignore` 逐字四行 /
  `git check-ignore` + `git ls-files`）。实测：`git check-ignore -v backend/pe_trial.db`
  → `.gitignore:61`；`git ls-files -- backend/pe_trial.db` → 空。

---

## 5. `serve.ps1 -Lan`

### 5.1 绑定地址两档实测（`Get-NetTCPConnection -State Listen`）

| 起法 | uvicorn 那行（脚本自己印的） | `LocalAddress` | 从 `192.168.31.11:<port>` 打 `/api/health` |
|---|---|---|---|
| `serve.ps1 -Port 8022 -SkipBuild`（**缺省**） | `--host 127.0.0.1 --port 8022` · `Uvicorn running on http://127.0.0.1:8022` | **`127.0.0.1`** | **连不上**：`ConnectionRefusedError [WinError 10061] 由于目标计算机积极拒绝，无法连接。` |
| `serve.ps1 -Port 8021 -Lan -SkipBuild` | `--host 0.0.0.0 --port 8021` · `Uvicorn running on http://0.0.0.0:8021` | **`0.0.0.0`** | **200** |

⚠️ 缺省档的输出里**一行 `-Lan` 的东西都没有**（整个 ⑤b 那块包在 `if ($Lan) { … }` 里），
故「不加旗标时行为一格都不变」这句话是**实测**的，不是推断。
⚠️ 变量名刻意**不是** `$Host`（PowerShell 的只读自动变量，给它赋值在 5.1 上直接报错），
守卫也钉了这一格。

### 5.2 LAN URL 的实测输出（原文）

```
      局域网链接（本机数到 1 个 IPv4 地址）：
        http://192.168.31.11:8021/        ← WLAN
      ⚠️ 上面这些 URL **只在同一个网段里有效**，而地址通常是 DHCP 给的：
         换一次网络、或路由器重新分配一次，它们就变了（本脚本每次现场数，故不会撒谎）。
```

⚠️ **一个地址都不写死**：判据是 `Get-NetIPAddress -AddressFamily IPv4` 过滤掉
`127.*` 与 `169.254.*`（APIPA）。守卫因此断言**全文件里** `192.168/16`、`10/8`、
`172.16/12`、`169.254/16` 四个私有网段**一个字面量都没有**（写死一个 `192.168.31.11`
等于把「本波实现者那台机器」焊进交付物，而甲方 IT 的机器不是它 —— 与 Plan 06 Task 13
修掉的那两条撒谎 URL 同一族）。⚠️ 一块网卡都数不到时打印一句人话 + 一条自查命令
（`Get-NetIPAddress -AddressFamily IPv4 | Format-Table IPAddress, InterfaceAlias`），
**不是**一个空列表。

### 5.3 防火墙命令原文（⚠️ 打印，一次都不执行）

```
netsh advfirewall firewall add rule name=XMU-PE-IMS-TCP-8021 dir=in action=allow protocol=TCP localport=8021
netsh advfirewall firewall delete rule name=XMU-PE-IMS-TCP-8021
```

* **为什么是这一条**（脚本自己印的那一段）：它只放行**这一个 TCP 端口的入站**
  （`dir=in` / `protocol=TCP` / `localport=<port>`），不动出站、不放开别的端口、
  也不建一个「全允许」的规则；而规则名里带着端口号，故试用结束之后**删得掉**。
* ⚠️ **端口用的是变量 `$Port`**（守卫断言那两行里含 `localport=' + $Port`，
  写死一个端口的话 `-Port` 换了命令就撒谎）。
* ⚠️ **不自动改防火墙**：那要管理员权限，而**静默提权不是交付物该有的形状**
  （一次 `-File serve.ps1 -Lan` 不该弹出 UAC、更不该在没人看见的情况下往系统防火墙
  写一条入站放行）。守卫断言「`netsh` 只出现在 `Write-Host` 行里」（非注释行逐行判）。
* ⚠️ 规则名刻意用 **ASCII**（`XMU-PE-IMS-TCP-<port>`）而不是中文：那条命令是要从
  GBK 代码页的控制台上**复制粘贴**到另一个管理员窗口里去的，而中文名在这一档下有
  被代码页弄坏的风险；ASCII 名还顺带免掉了引号。

### 5.4 两档告示原文

`-Lan` 那一档（比缺省档多印的一整块）：

```
   ⚠️⚠️⚠️ -Lan：本进程绑在 0.0.0.0 上，**同一个网段里的任何人都打得开**
      · 这是**明文 http**：口令、pe_session cookie、学生姓名与体测数据在网线上都是明文。
      · **不要传真实数据**：局域网试用请一律用仿真库（backend\scripts\demo.ps1 灌的那一份，
        或 scripts\trial.ps1 灌的试用库）。要上真数据请先有一层 TLS 反代。
      · 演示口令是**公开的**：它的唯一所有者是 backend\scripts\demo_bootstrap.py 的
        DEMO_PASSWORD（也写在 spec §13），本文件刻意**不抄一份字面量**在这里。
      · 未绑定的账号可以被**抢绑**（spec §1.2 第 4 条），而 GET 读操作今天**不留审计**
        （spec §1.2 第 14 条 / §13.9）：谁读过什么，事后查不出来。
```

`-Lan` **且** `PE_ENV=prod` 时**另外**多印的一段（实测原文，8023 上亲跑）：

```
   ⚠️⚠️⚠️ -Lan 与 PE_ENV=prod **同时**出现（实测档位 prod，cookie 的 Secure = True）：
      明文 http + Secure cookie ⇒ **浏览器拒收那张 cookie**，症状是「登录 200、下一个请求 401」
      ——即上面那些局域网 URL 点开之后**登不进去**。本脚本**不阻止**这一档，处置二选一：
        · 只是局域网明文试用 → 去掉 PE_ENV（回到缺省的 dev 档），或去掉 -Lan；
        · 真要上生产 → 前面挂一层 TLS 反代并设 PE_CORS_ORIGINS（那时 -Lan 绑 0.0.0.0 是合法的）。
```

⚠️ **不 raise**（控制者裁定，实现者复核后同意）：「TLS 反代就在同一台机器上、
反代再转发到 `0.0.0.0:<port>`」是一档**合法**形状（边缘是 HTTPS ⇒ `Secure` cookie 成立），
`raise` 会把它一起打死。守卫钉住「`-Lan` 那一块里一个 `throw` / `exit 1` 都没有」
（⚠️ 判据打在**去掉注释行**之后的那一块上：那一段的注释里逐字**提及**了 `raise`，
而提及不是本身）。⚠️ 与实施计划 07 Task 3 的隧道档对照：那一档边缘是 HTTPS，故 `prod` 成立。

### 5.5 ⚠️ 从 `192.168.31.11:8021` 真发请求的端到端四格

全部**从 LAN 地址发**（不是 `127.0.0.1`），`http.client`，本机亲跑：

| # | 请求 | 实测 |
|---|---|---|
| ① | `GET /api/health` | **200** `application/json` · `{"status":"ok","tables":28,"students":60,"trial":false}` |
| ② | `GET /s/home`（一条深链接） | **200** `text/html; charset=utf-8` · **2 729 B** · 含 `<div id="app">` **True** · 含 `src="/assets/` **True** ⇒ SPA fallback 回的是 `index.html` |
| ③ | `POST /api/auth/login`（教师 `T0001` + 演示口令） | **200** · `Set-Cookie: pe_session=qmEKgljs…; HttpOnly; Max-Age=7200; Path=/; SameSite=lax` · body `{"kind":"teacher","id":1,"name":"陈国华","role":"teacher","student_no":null,"staff_no":"T0001"}` |
| ④ | `GET /api/auth/me` **带着 ③ 那张 cookie** | **200**（⚠️ **不是 401**）· body 与 ③ 逐字相同 |

⚠️ 对照：同一个进程从 `127.0.0.1` 打 ① 也是 **200**（绑 `0.0.0.0` 的进程在回环上照样可达）。

⚠️⚠️ **两格如实记**：
1. **「别的机器能不能连进来」本波没测到**：从本机自己的 LAN 地址打过去不过滤入站，
   故 ①–④ 证明的是「**socket 真的绑在 LAN 接口上、并且在那个地址上应答**」；
   而甲方现场若「本机打得开、同事打不开」，那就是 §5.3 那条 `netsh` 还没跑。
   本波**没有**改防火墙（要管理员权限），也没有第二台机器可用。
2. **`Secure` 在明文 http 上被浏览器拒收那一格，本波没有再用浏览器复现**：
   一个非浏览器的 HTTP 客户端会把 `Secure` cookie 照发回去（实测 ④ 仍 **200**）。
   本波量到的是**因**（服务端确实只在 `prod` 加 `Secure`，两档 `Set-Cookie` 原文见下），
   **果**由 spec §13.11.3（Plan 06 Task 7 论证过）与
   `tests/api/test_auth_api.py::test_login_sets_the_cookie_with_the_documented_parameters`
   钉着。**顶回 0 处**，而这一格是「没有重复量一遍别人量过的东西」，不是「没量」。

### 5.6 两档 `Set-Cookie` 的逐字对比（同一个 `-Lan` 起法，只差 `PE_ENV`）

```
dev  （8021）  pe_session=qmEKgljsIxuQ2qYW-SbD5v0qG--MO-lwifJ10SNAy36kqjuEWgz6bz4TAGOaDt-6; HttpOnly; Max-Age=7200; Path=/; SameSite=lax
prod （8023）  pe_session=EiIYY4KKvqrSGPHfpo0FtFSogGaBtfBVTlaXWgmGeXmlfRgbdxetCc3G3NdrLyp9; HttpOnly; Max-Age=7200; Path=/; SameSite=lax; Secure
```

⇒ **dev 无 `Secure`、prod 有 `Secure`**，其余五格（`HttpOnly` / `Max-Age=7200` / `Path=/` /
`SameSite=lax` / 无 `Domain`）逐字相同。⚠️ 这一格 pytest 里**早有守卫**
（`tests/api/test_auth_api.py` 的那一条，期望侧是字面量），本波是**在真 uvicorn 上重量一遍**。

---

## 6. `smoke.mjs` 三档

| 档 | 后端 | 前端 | 库 | `PE_TRIAL` | 步数 | 断言 | 退出码 | 墙钟 |
|---|---|---|---|---|---|---|---|---|
| **dev** | `demo.ps1 -Port 8000` | `vite --port 5174 --strictPort` | `pe_demo.db`（刚灌） | 未设 | **18/18 全绿** | **679 绿 / 0 红** | **0** | **35.4 s** |
| **产品档** | `serve.ps1 -Port 8020 -SkipBuild` | 同源 | `pe_demo.db`（刚灌） | 未设 | **18/18 全绿** | **679 绿 / 0 红** | **0** | **31.8 s** |
| **试用档** | `trial.ps1 -Port 8030 -Reset` | 同源 | `pe_trial.db`（刚灌） | **1** | **18/18 全绿** | **711 绿 / 0 红** | **0** | **31.9 s** |

⚠️ 基线 **655**（两档各 18 步）⇒ **679 / 679 / 711**（+24 / +24 / +56）。**判据一字没放宽**，
只增不减 ✓。⚠️ dev 档用 **5174**（5173 上那个 PID 20240 不是本波起的，全程没动它）。
⚠️ 每一档跑之前都**重灌**了一份库（dev 档走 `demo.ps1`，产品档走 `demo_bootstrap.py`
同一个入口，试用档走 `trial.ps1 -Reset`），故第 0 步「一个刚复原的演示库」那 25 拍在三档都是绿的。

**新增了哪几拍**（655 → 679 的 24 条 = 第 1 步 +2、第 14 步 +17、第 17 步 +5）：

1. **第 1 步**（5 → **7** 条）：`响应恰好 4 个键`（`status,students,tables,trial`）·
   `trial 是布尔`（⚠️ `App.vue` 判的是 `=== true`，后端回一个 `"1"` 字符串的话告示会**静默不挂**）·
   `trial 与本进程的 PE_TRIAL 一致`（⚠️ 两侧不同源：环境变量 vs HTTP）· 一行档位口径的打印。
2. **第 14 步**（144 → **161**（dev/产品）/ **193**（试用））：逐路由
   `试用告示在/不在`（16 条）+ 收尾一条 `§Trial 总数`；试用档另加
   `needle 恰好 1 处`（16 条）与 `N == /api/health 的 students`（16 条）。
3. **第 17 步**（64 → **69**，标题从「静态守卫 8 条」改成「**9 条**」）：⑨ 五拍（源码面，
   **不需要任何服务起着**）—— 告示文案在 `src/**` 的代码里恰好 1 个文件 = `src/App.vue`、
   它挂在 `v-if="trial"` 上、`trial` 由 `getHealth()` 填、`catch` 落到 `trial.value = false`、
   扫描面 ≥ 30 个 `.vue`/`.ts`。

**needle 无歧义的取证**（试用档原文，前两条路由）：

```
✓ login：试用告示**在**（期望侧 = 本进程的 PE_TRIAL=1；被测侧 = 渲染出来的 DOM 正文）  →  正文里有 "请勿录入真实学生信息"，本档期望有
✓ login：试用告示的 needle 在正文里**恰好 1 处**（无歧义 ⇒ 它真的钉住了那一处；两处同串的话把 App.vue 那一条删掉仍然绿，终审 S3-⑦）  →  1 处
✓ login：告示里「N 名学生均为虚构」的 N == /api/health 的 students（DOM vs HTTP，两侧不同源 ⇒ 在前端写死一个数会红）  →  正文里找 "（60 名学生均为虚构）"
✓ bind：… （同形三拍，1 处 / 60）
```

dev 档与产品档的反空转那一侧（原文）：

```
✓ §Trial 16 条路由上试用告示的**条数**与本档一致（PE_TRIAL=（未设） ⇒ 期望 0 条）  →  0/16 条有告示（期望 0）
✓ login：试用告示**不在**（期望侧 = 本进程的 PE_TRIAL=（未设）；被测侧 = 渲染出来的 DOM 正文）  →  正文里没有 "请勿录入真实学生信息"，本档期望没有
```

试用档的总数那一拍（原文）：

```
    档位口径：PE_TRIAL=1 ⇒ /api/health 的 trial=true ⇒ 第 14 步期望 16 条路由上**都挂着**那条试用告示（students=60）
✓ §Trial 16 条路由上试用告示的**条数**与本档一致（PE_TRIAL=1 ⇒ 期望 16 条）  →  16/16 条有告示（期望 16）
```

⚠️⚠️ **期望侧为什么取自环境变量、而不是 `/api/health`**：告示是 `App.vue` 按那一次 HTTP
响应渲染的，期望侧若也读它，两侧就**同源**了 —— 后端把 `trial` 答错（例如开发档上答
`true`）时期望侧会跟着错，于是「告示泄漏到别的档」这一档**恒绿**（硬规矩 #35）。
故跑第三档的人要**同时**给 `smoke.mjs` 设 `PE_TRIAL=1`；忘了设的话第 1 步那一拍当场红
（失效方向是响亮的）。⚠️ 而「本档到底期望哪一侧」由三档各跑一整遍给出：
试用档 16/16 有、dev 与产品档 0/16 有 —— **两侧都在场**（硬规矩 #50）。

### 6.1 定点变异（六格，⚠️ 它抓到了一条守卫自己的缺陷）

| # | 变异 | 守卫 | 结果 |
|---|---|---|---|
| **M1** | 把 `is_trial()` 反过来（缺省当试用档、`PE_TRIAL=1` 当不是） | `tests/test_deploy.py` + `tests/test_main.py` | **红 ✓**（`test_the_default_is_not_a_trial_instance` / `test_the_trial_cell_is_the_only_runtime_fact_health_discloses` / `test_health_and_openapi_never_leak…` 三条同时红） |
| **M2a** | 把告示从 `App.vue` 的模板里**删掉**（试用档跑） | `smoke.mjs` 第 14 步那 16 拍 + 第 17 步 ⑨① | **红 ✓**（原文 `✗ login：试用告示**在** … 正文里没有 "请勿录入真实学生信息"，本档期望有`，逐条路由都红） |
| **M2b** | 把告示**挪进一个子组件**（`components/TrialNote.vue`），根组件照样渲染它 | 第 14 步 **照旧绿**（`§Trial 16/16 条有告示`）· 第 17 步 ⑨①②③③′ **红 ✓** | **红 ✓**（`⑨① … → ["src/components/TrialNote.vue"]`） |
| **M3** | 把 `PE_TRIAL` 的 `raise` 那一支去掉（认不出的值静默回落 `False`） | `tests/test_deploy.py` + `tests/test_main.py` | **红 ✓**（`DID NOT RAISE ValueError` ×2 + health 那一条） |
| **M4** | 把 `-Lan` 的 `0.0.0.0` 改回 `127.0.0.1` | `tests/test_serve.py` 的绑定地址那一条 | **红 ✓**（`缺省绑定地址那一行变了：本仓的裁定是「不加 -Lan 时行为一格都不变」`） |
| **M5** | 把 `-Lan` 告示里「这是明文 http」那一行换成一句别的 | `tests/test_serve.py` 的告示那一条 | 改前 **绿 ✗** → 修完 **红 ✓** |
| **M5b** | 把 `-Lan` 告示的头两行一起删掉 | 同上 | 改前 **绿 ✗** → 修完 **红 ✓** |

⚠️⚠️ **M2b 是第 17 步 ⑨ 存在的全部理由**：第 14 步量的是渲染后的真值，它对
「告示住在哪个组件里」完全无感 —— 没有 ⑨ 的话「把横幅从根组件挪走」这个变异在
**三档上都绿**。⚠️ 而 M2b 那一遍还顺带把 §I5 也弄红了（那个子组件里没有
`await session.ensureRestored()`），反过来证明 §2.5 那一行确实是承重的。

⚠️⚠️ **M5 抓到的是守卫自己的缺陷**（如实记）：改前那一条用的 needle 是裸串
`"明文 http"`，而它在 `-Lan` 那一块里有**两处**（告示那一行 + 下面 `-Lan`+`prod`
那一段的「明文 http + Secure cookie ⇒ …」）⇒ 把告示那一行删掉，needle 被另一处满足，
**全绿**。与 Plan 06 Task 15 / 终审 S3-⑦ 修掉的那一格 needle 歧义**同一族**。
处置是把判据从 `in` 抬成 `count(...) == 1`、并把 needle 从四条抬成五条
（`这是**明文 http**` / `**不要传真实数据**` / `演示口令是**公开的**` /
`**同一个网段里的任何人都打得开**` / `未绑定的账号可以被**抢绑**`），
每条都「只可能出现在告示里」。修完 M5 与 M5b 都红（commit `a86bfaa`）。

⚠️ 另一处如实记（**成本**，不是缺陷）：M2a 那一遍**跑不完** —— 告示不在时
`dumpRoute` 会为每一条轮询到 **45 s** 的 deadline，16 条路由 ⇒ 约 12 分钟。
本波在抓到前 4 条路由的红之后停掉了它（证据已经充分：`login` / `bind` / `s-home` /
`s-weekly-sheet` 各 2 拍全红）。⚠️ 失效方向是**慢而响**、不是快而静，故不改判据。

⚠️ 六格变异**全部逐字节还原**（还原后立刻重跑对应守卫，一律回到绿），
`git status` 复验只剩本波**有意**的改动。

---

## 7. 待清扫 / 关切 / 没按派单做的 / 顶回

### 7.1 顶回（**2 处**）

| # | 派单原文 | 顶回 | 理由（实测） |
|---|---|---|---|
| ① | §1.3「挂在既有的 `GET /api/health` 上…**理由是它是 24 个未定型响应之一 → openapi 五格一个字节都不会变**（⚠️ 你必须实测复核这条理由）」 | **半句顶回**：五格与响应 schema 确实一个字节都没变，而**文档的字节变了 +3 335**（417 032 → 420 367），差异**恰好 1 个叶子** = `/api/health` 的 `description` | FastAPI 把端点 docstring 渲染成 `description`，而 docstring 的第一行逐字写着响应体的形状 ⇒ 加一格就**必须**改它，不改就是「账面与实物相反」。连带 `schema.d.ts` 要重跑 `gen:api`（+45 / −1 行，已做）。⚠️ 而「给它一个有型 schema」换不到任何东西（成本对比见 §2.3），故**不给** |
| ③ | §1.6「`openapi 逐字节不变` 的那条取证做成常驻守卫（⚠️ 若成本不划算，说明并顶回来）」 | **顶回**：做不成常驻守卫 | 与 ① 同一条根因：任何一次对 `health` docstring 的修改都会让「与一份快照逐字节相同」红，而修它的人唯一的出路就是**删掉说明文字**（硬规矩 #109 的形状）。改成钉三格**性质**（三档 `PE_TRIAL` 下逐字节相同 + 五格 + `HEALTH_UNTYPED_SCHEMA` 字面量 + 24 个未定型），对措辞完全不敏感 |

⚠️ 派单点名的另外四处**复核后同意、不顶回**，逐个说清核过什么：

* **②「告示读不到 `/api/health` 时挂不挂」→ 同意「不挂」**。核过：打不通 = 后端没起来 =
  页面本来就是坏的（每一个业务端点都会失败、`ApiErrorBanner` 会挂出真因），
  此时再挂一条「试用环境」是噪声；而反过来那一档（「不确定就告示」）会让**开发档与
  产品档**在后端没起时挂一条**假话**（那两个档的库里可以是真数据）。裁定已写进
  `App.vue` 的文件头 + `onMounted` 的 `catch` 注释 + spec §13.16.3，
  并有守卫（smoke 第 17 步 ⑨③′）。
* **③「`demo.ps1` 的灌库能不能只灌不起」→ 不需要顶回**。实测：`demo.ps1` 的 ④ 灌库与
  ⑥ 起服务确实耦在一起（`-DryRun` 只灌一个**临时**库、跑完就删，不能用来灌
  `pe_trial.db`），但派单给的第三条路「直接从 `trial.ps1` 调它调的那个 Python 入口」
  完全够用 ⇒ `trial.ps1` 调 `python scripts/demo_bootstrap.py`，**没有**给 `demo.ps1`
  加 `-SeedOnly`（那会让「怎么灌一个库」多一个住址）。
* **④「`-Lan` + `PE_ENV=prod` 该不该 raise」→ 同意不 raise**。核过：反代在同一台机器上时
  「`-Lan` 绑 `0.0.0.0` + `prod`」是合法形状，raise 会把它一起打死；而「不阻止」的代价
  只是「一档登不进去的配置」，且脚本会**当场说清**后果与两条出路（§5.4 原文）。
  ⚠️ 守卫钉住「`-Lan` 那一块里一个 `throw` / `exit 1` 都没有」，故下一个人加 raise 会红。
* **⑤「试用档缺省端口 8030」→ 同意**。核过：与 8000（手工演示）/ 8010（`demo.ps1`）/
  8020（`serve.ps1`）/ 5173·5174（vite）全错开 ⇒ 两档可以同时起着对拍，
  而本波**真的**那么跑过（产品档 8020 与试用档 8030 同时在跑）。守卫按字面钉住
  「缺省不是那四个数中的任何一个」。
* **⑥「smoke 跑第三档的成本值不值」→ 值**。实测成本：多一遍 **31.9 s**（与产品档同一档量级）
  + 一次 `trial.ps1 -Reset`（灌库约 25 s）。换来的是**唯一**一条「告示不泄漏到别的档」
  与「告示在 16 条路由上都在」的运行时证据 —— 而这两件事正是本 Task 的全部交付面。
  ⚠️ 如实记一笔成本：告示**不在**时（M2a 那一档）第 14 步会为每条路由轮询到 45 s 的
  deadline ⇒ 一个坏掉的试用档要跑约 12 分钟才跑完（慢而响，不是快而静）。

### 7.2 没按派单做的（**3 处**，逐个如实记）

1. **commit 的切法**与派单建议的不同（5 个 commit，而 ③④ 合成一个、多了「变异修正」一个）。
   逐字理由见 §0 那张表的脚注。
2. **`trial.ps1` 的参数面**：派单列的是 `-Port` / `-Lan` / `-Reset` 三个，本波**就是这三个**
   （⚠️ 刻意**没有**加 `-Students` / `-Seed` / `-SkipBuild`：前两个的缺省所有者是
   `demo_bootstrap.py` 的 argparse，后一个是 `serve.ps1` 自己的旗标、而它本来就会判
   `dist` 新鲜度 ⇒ 三个都是第二个所有者）。⚠️ 这一条严格说是「按派单做的」，
   列在这里是因为它是一处**刻意的不做**，怕下一个人「顺手对称一下」加上去
   （守卫钉住了 param 块恰好三个变量）。
3. **`-Reset` 的两步顺序与派单的描述相反**：派单 §1.2 第 3 条写的是「打印删了什么
   （路径 + 删前的字节数/sha16）…⚠️ 删之前先确认没有进程持有它」，本波落成
   **占用检测 → 取证 → 删**。⚠️ 不是不照做，而是**实测发现照字面做会坏**：
   `Get-FileHash` 要读文件，而被持有的库读不出来 ⇒ 脚本会停在一段 PowerShell 原文报错上、
   那一句人话永远打不出来（§4 逐字记了原文）。⚠️ 两件事都做了，只是换了顺序，
   并把顺序钉进守卫。

### 7.3 待清扫（**3 条**）

1. **`trial.ps1` 的 CSV 临时目录在「进程被杀」时不会被清掉**。`finally` 只在
   `Ctrl-C` / `throw` / 正常退出这三条路上跑；本波用工具**硬杀**过两次，
   于是 `$env:TEMP` 下留了 `pe_trial_csv_*`（跑完已手工清掉并复验，见 §8）。
   ⚠️ `demo.ps1` 是**从来不删**它那份 `pe_demo_csv_*` 的（那一格更糟），
   而改它不在本波范围里 ⇒ 登记为待清扫：给三个 `.ps1` 一个统一的
   「临时目录落在 `$env:TEMP\pe-ims-<name>\` 下、启动时清掉上一份」的姿势。
2. **`pe_trial.db` 与 `pe_demo.db` 的干净态 sha 没有被任何守卫钉住**。本波实测
   `trial.ps1 -Reset` 灌出来的是 **1 597 440 B**（`demo.ps1` 灌 `pe_demo.db` 是
   **1 589 248 B**）—— 两者行数逐格相同（`[7/7]` 那一步的 13 个表计数一模一样），
   字节数差 8 192 是 SQLite 的页分配差异。⚠️ 派单给的「干净态 `8593924853855627` /
   1 589 248 B」是 `pe_demo.db` 的口径，而本波**没有**为 `pe_trial.db` 立一个同类的数
   （立了就会随 SQLite 版本漂）。要一个「试用库是不是刚灌的」的判据，
   正确形状是 `smoke.mjs` 第 0 步那种**行数**口径，不是文件哈希。
3. **`-Lan` 的告示没有覆盖「同一网段」之外的一档**：绑 `0.0.0.0` 的进程在
   **多网卡**机器上会对每一块网卡都应答（含一块接到公网的），而脚本只打印
   「同一个网段里的人都打得开」。本波这台机器只有 1 块 IPv4 网卡（WLAN），
   故实测不到那一档。⚠️ 甲方 IT 若在一台多宿主的机器上跑 `-Lan`，
   这句话是**偏窄**的。处置建议：Task 5 的说明书里补一句「`-Lan` 会对**每一块**网卡应答」。

### 7.4 关切（**2 条**，不阻塞）

1. **`/api/health` 现在多回一格给匿名**。裁定与理由见 §2.4（`trial` 不是秘密：
   告示本来就印在每个页面上；而 `PE_ENV` 仍然一格都不回）。⚠️ 而它确实让
   「匿名可读的运行时事实」从 0 变成 1，故守卫把它钉成**恰好四格**
   （`test_health_reports_the_table_count` 断的是整份响应体 == 字面量四格）：
   下一个想加第五格的人会红，并且红在一个**说清了理由**的地方。
2. **`schema.d.ts` 从此每改一次端点 docstring 就要重跑 `gen:api`**。这不是本波引入的
   （Plan 06 Task 8b 就把守卫钉上了），而本波是它落地之后**第一次真的触发**它
   （+45 / −1 行）。⚠️ 如实记一笔：`openapi-typescript` 写出的产物是 **LF**，
   而工作树约定 CRLF，故每次重跑都要手工还原一次（Plan 06 Task 13 的 F3 已经把
   「每波都要记得还原」降级成「报行尾时报两个口径」，本波照做）。

---

## 8. 最终验收

| 项 | 基线 | 本波实测 | |
|---|---|---|---|
| 后端 passed（`--no-cov`） | 1573 | **1593 passed**（201.23 s，墙钟 203.36 s，退出码 0） | ✅ +20 |
| 后端 passed（带 `--cov`） | 1572 + 1 skipped | **1592 passed + 1 skipped** | ✅ |
| 覆盖率 ① `app/domain` | 1268/0/376/0/100% | **1268/0/376/0/100%**（18 个模块） | ✅ 逐格相同 |
| 覆盖率 ② `app` | 7300/201/1774/115/96% | **7311/201/1778/115/97%**（96 个模块） | ✅ +11 语句 / +4 分支，miss 一格没涨 |
| 覆盖率 ③ `scripts`+`app.static` | 583/206/164/22/64% | **583/173/164/24/74%**（6 个模块） | ⚠️ 见下 |
| 表数（health 口径 / `sqlite_master`） | 28 / 29 | **28 / 29**（`pe_trial.db` 上实测） | ✅ |
| 迁移链 | 4 单头 | **4 单头** `53e5a548c40e → 0b7da3d20211 → 7f3923d8af84 → 0ac943e0da9b`，heads = `['0ac943e0da9b']` | ✅ |
| 模型↔迁移残差 diff | 0 operation | **0 operation**（`tests/db/test_migration_baseline.py` 全绿；⚠️ 本波一个 schema 都没动、一条迁移都没加） | ✅ |
| openapi 五格 | 74/102/84/63(15+48)/3 | **74/102/84/63(15+48)/3** | ✅ 一格没变 |
| 未定型响应 | 24 | **24**（`/api/health` 仍在里面） | ✅ |
| `/api/health` 的响应 schema | `additionalProperties: true` 那一串 | **逐字相同** | ✅ |
| catch-all 路由 | 0 | **0** | ✅ |
| 扫描面（后端 AST） | 72 | ⚠️ 见下 | |
| `_MODELS_PUBLIC_BASELINE` / `_MODELS_SUBMODULES` | 33 / 8 | **33 / 8** | ✅ |
| 黄金用例 | 14 | **14**（夹具 `backend/tests/fixtures/golden_cases.json` 的 `input` / `expected` 各 **14** 条；守卫 `tests/integration/test_golden_cases.py` 实测 **19 passed**） | ✅ |
| `npm run build` | 退出码 0 | **退出码 0**（368 ms / 345 ms / 360 ms 三次实测） | ✅ |
| 产物哈希 | `index-ah7DZvEq.css` / `index-DBx0Mneu.js` / `StudentDetail-Cf1DShvQ.js` / `AuditLogList-BNxWsd2d.js` / `ResourceIndex-DqalY3wm.js` | **`index-Dm53XXz-.css` / `index-Wfsbvc3G.js` / `StudentDetail-kQIIimXN.js` / `AuditLogList-CKJ4Vvz4.js` / `ResourceIndex-DqalY3wm.js`** | ⚠️ 4 个变了、1 个没变，见下 |
| `check:tokens` | 扫描面 36 / 下界 25 / offender 0 | **扫描面 36 / offender 0 / 退出码 0** | ✅ 一格没退 |
| `check:dist` | 25 产物 / 784 248 字符 | **25 产物 / 787 824 字符 / 全绿** | ✅ +3 576 字符（就是那条告示） |
| 新增依赖 | 后端 0 / 前端 0 | **后端 0 / 前端 0**（`tests/test_dependencies.py` 全绿） | ✅ |
| 四个数据指纹 | `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` / `E48E3AC82BB45BB7` | **四个逐个复算全中**：`national_standard_2014.csv` 21 412 B=`D2C8E539E2FA0029` · `exercises.yaml` 23 247 B=`5394B37F01DAC9AC` · `exercise_equivalence.yaml` 8 245 B=`822CB86A5E998301` · `alert_rules.yaml` 6 037 B=`E48E3AC82BB45BB7` | ✅ |
| 18 个模板指纹 | 18 | **18 个 YAML**（合计 123 848 B），`tests/test_refdata_prescription.py` 全绿 | ✅ |
| `git diff a40db5a HEAD -- backend/data` | 空 | **空** | ✅ |
| `backend/pe.db` | 不存在 | **False** | ✅ |
| `backend/pe_trial.db` 未入库 | — | `git ls-files` → **空** ✓；`git check-ignore -v` → `.gitignore:61` ✓ | ✅ |
| `backend/data/seed/` | 0 文件 | **0 文件** | ✅ |
| `frontend/dist` / `backend/backups` 未入库 | 未入库 | `git ls-files` 各 **0** 个文件；`backend/backups/` 目录**不存在** | ✅ |
| `pyproject.toml` / `package.json` / `.gitattributes` | 零 diff | **三份各 `git diff a40db5a HEAD` = 空** | ✅ |
| 本波起的进程 | — | 8000 / 8010 / 8020 / 8021 / 8022 / 8023 / 8030 / 8031 / 5174 **listener 全 0**；**5173 的 PID 20240 全程没动** | ✅ |
| `$env:TEMP\p07t1` 与 `pe_*_csv_*` | — | 见下面「清扫复验」 | ✅ |

⚠️ **三处如实说明**：

1. **覆盖率 ③（`scripts` + `app.static`）的 miss 从 206 降到 173（64% → 74%）**。
   ⚠️ 本波**没有**为 `backend/scripts/**` 新增任何测试（`tests/test_trial.py` 一律是
   **读文件**的静态守卫，一个脚本都不执行），故这 −33 我**归因不出来**。
   ⚠️ 而**语句总数 583 两次实测逐字相同**（本波单独跑一次 `--cov=scripts --cov=app.static`
   得 `583/173/70%`，与合并跑 `--cov=app --cov=scripts --cov-branch` 之后按前缀拆出来的
   `583/173/164/24/74%` 一致），故不是扫描面变了。方向是**变好**、不是回归，
   如实记，不认领。
2. **扫描面 72 那一格本波没有单独复算**。它是「pipeline 10 + db 14 + domain 18 + api 26 + auth 4」
   的 AST 扫描面，而本波**一个新 `.py` 模块都没加**（`tests/test_trial.py` 是测试文件，
   不在 `app/**` 的扫描面里），且 `tests/architecture/**` 全绿 ⇒ 那一格结构上没变。
   ⚠️ 如实记：这是**推断 + 架构守卫全绿**，不是本波亲手数过一遍。
3. **产物哈希变了 4 个、`ResourceIndex-DqalY3wm.js` 没变**。根因是 Vue SFC 的
   **scoped CSS 的 `data-v-xxxx` 哈希由组件的源文件内容派生**：`App.vue` 改了
   ⇒ 它的 scope id 变了 ⇒ `index-*.css` 与几个引它的 chunk 一起换名。
   ⚠️ 而 `ResourceIndex` 那个 chunk 不含 `App.vue` 的 scope ⇒ 名字不变。
   ⚠️ 本波**亲验过这个解释**：定点变异之后把 `App.vue` 逐字节还原、重新构建，
   `index-Wfsbvc3G.js` 与还原前那一次**逐字相同**（构建是可复现的）。

### 8.1 清扫复验

* `$env:TEMP\p07t1\`（本波全部探针 + 日志 + 两份 openapi dump）：⚠️ **在本 commit 之后
  立刻删除并复验**（删除与复验的输出记在交回控制者的那一段里）。⚠️ 顺序上的如实记：
  那一批文件**就是**写这份报告用的探针，故它不可能在「报告已入库」之前就删掉 ——
  先删就写不出报告，先写就还在磁盘上。
* `demo.ps1` 留下的 `pe_demo_csv_*`：实测跑到 **2 个**（`pe_demo_csv_12108` / `pe_demo_csv_32740`），
  **已删并复验 0 个**。
* `trial.ps1` 留下的 `pe_trial_csv_*`：实测 **3 个**（`18600` / `36420` / `39844`；
  ⚠️ 三个都是「进程被工具硬杀」留下的，`finally` 在那条路上跑不到 —— §7.3 第 1 条），
  **已删并复验 0 个**。
* `pe_demo_dryrun_*`：**0 个**（`smoke.mjs` 第 17 步 ① 那一次 `-DryRun` 自己删干净了）。
* `backend/pe_demo.db`（1 597 440 B）与 `backend/pe_trial.db`（1 597 440 B）：
  ⚠️ **两个都留着**（都在 `.gitignore` 里，`git ls-files` 各 0 行）。
  留着的理由：`pe_trial.db` 是给甲方点的那一份、下一次 `trial.ps1` 会**复用**它；
  而两个库都被 smoke 写脏过，要一份干净的请重跑 `demo.ps1` / `trial.ps1 -Reset`。
* 工作树：`git status --porcelain` **空**（本 commit 之后）。

### 8.2 spec

| | 改前 | 改后 |
|---|---|---|
| 工作树字节 | 522 729 B | **549 289 B** |
| 行数（nl） | 4 868 | **5 192**（+324） |
| 行尾 | 4 868 CRLF / 0 裸 LF / 无 BOM | **5 192 CRLF / 0 裸 LF / 无 BOM** |
| sha256[:16]（工作树字节） | `C7FB8050332B4536` | **`03E0A4941F90AA6A`** |
| sha256[:16]（LF 归一后） | `CFE1163ABB5E4621`（= 入库 blob） | **`ED4A1AD9B89739AF`** |
| `git ls-files --eol` | `i/lf w/crlf attr/text eol=crlf` | **`i/lf w/crlf attr/text eol=crlf`** |

新增 **§13.16**（7 个小节：档位为什么不在前端 / `/api/health` 的第四格 /
页面告示 / `trial.ps1` / `serve.ps1 -Lan` / smoke 的第三档 / 定点变异六格），
并在 **§13.11.3** 加了一条 `-Lan` 的交叉引用、在 **§13.11.4** 的标题下加了一段
「Plan 07 起是三档」的说明（⚠️ **不改**那一节里 Plan 06 Task 7 当时的两档实测数字 ——
那是历史取证，把历史数字改成今天数字是硬规矩 #111 的反面）。

### 8.3 本报告

`.superpowers/sdd/2026-10-15-实施计划07-交付与试用/task-1-2-report.md`（目录是新建的）：
**纯 LF、无 BOM**，`.superpowers/** -text` ⇒ 工作树字节 == 入库 blob 字节。
⚠️ **行数与字节数一律不印**（理由与 sha256 那一格相同：把数字写进去就会改变它自己 ——
本波在这一格上绕了**两**圈，第一圈印了字节数与 sha256、第二圈改成不印 sha256 却仍然
印着行数，故第三圈把三个自指数一并摘掉）。
入库后亲验：`git ls-files --eol` = `i/lf w/lf attr/-text`、`git cat-file -s <blob>` ==
磁盘字节、两份 sha256 逐字相同（`True`）。

⚠️⚠️ **本文件刻意不印自己的字节数与 sha256**：那是个不动点问题 —— 把那个数字写进去
就会改变它自己，于是「文件里印的数」与「文件真实的数」**在构造上不可能同时成立**。
`.gitattributes` 里 `.superpowers/** -text` 那一段注释逐字记着本仓为这一格付过的代价
（「这些文件里大量引用自己的字节数与 sha256……一次 checkout 就会让每个数字当场变假」）。
⚠️ 本波自己也在这一格上绕了一圈：第一版印了一组数，随后为了修一处**住址写错**
（黄金用例的守卫在 `tests/integration/`、不是 `tests/domain/`）而 amend 了一次，
那一组数当场变假 ⇒ 故改成「不印，要数就当场跑 `git cat-file -s HEAD:<本文件路径>`」。
本波结案时的实测值记在**交回控制者**的那一段里（它不在本文件内，故不会自指）。

---

## 9. 行尾复核（逐个被改文件，两个口径）

`git ls-files --eol`（入库 blob / 工作树 / 生效的 attr）：

```
i/lf    w/crlf  attr/                   .gitignore
i/lf    w/crlf  attr/text eol=crlf      Document/2026-09-28-体育闭环原型-设计spec.md
i/lf    w/crlf  attr/                   backend/app/deploy.py
i/lf    w/crlf  attr/                   backend/app/main.py
i/lf    w/crlf  attr/text eol=crlf      backend/scripts/demo.ps1
i/lf    w/crlf  attr/                   backend/tests/test_deploy.py
i/lf    w/crlf  attr/                   backend/tests/test_main.py
i/lf    w/crlf  attr/                   backend/tests/test_serve.py
i/lf    w/crlf  attr/                   backend/tests/test_trial.py
i/lf    w/crlf  attr/                   frontend/scripts/smoke.mjs
i/lf    w/crlf  attr/                   frontend/src/App.vue
i/lf    w/crlf  attr/                   frontend/src/api/generated/schema.d.ts
i/lf    w/crlf  attr/                   frontend/src/api/types.ts
i/lf    w/crlf  attr/text eol=crlf      scripts/serve.ps1
i/lf    w/crlf  attr/text eol=crlf      scripts/trial.ps1
```

工作树字节（每改完一个文件当场核过，这里是收尾时的一次总核）：

| 文件 | 字节 | nl | CRLF | 裸 LF | BOM |
|---|---|---|---|---|---|
| `backend/app/deploy.py` | 19 128 | 294 | 294 | **0** | 无 |
| `backend/app/main.py` | 37 593 | 560 | 560 | **0** | 无 |
| `backend/tests/test_deploy.py` | 22 861 | 414 | 414 | **0** | 无 |
| `backend/tests/test_main.py` | 49 874 | 911 | 911 | **0** | 无 |
| `backend/tests/test_serve.py` | 103 129 | 1 785 | 1 785 | **0** | 无 |
| `backend/tests/test_trial.py` | 29 226 | 495 | 495 | **0** | 无 |
| `backend/scripts/demo.ps1` | 25 820 | 321 | 321 | **0** | **有** |
| `scripts/serve.ps1` | 35 924 | 504 | 504 | **0** | **有** |
| `scripts/trial.ps1` | 22 080 | 330 | 330 | **0** | **有** |
| `.gitignore` | 5 496 | 93 | 93 | **0** | 无 |
| `frontend/src/App.vue` | 19 975 | 367 | 367 | **0** | 无 |
| `frontend/src/api/types.ts` | 29 902 | 496 | 496 | **0** | 无 |
| `frontend/src/api/generated/schema.d.ts` | 531 599 | 10 446 | 10 446 | **0** | 无 |
| `frontend/scripts/smoke.mjs` | 329 717 | 4 593 | 4 593 | **0** | 无 |
| `Document/…设计spec.md` | 549 289 | 5 192 | 5 192 | **0** | 无 |

⚠️ 三个 `.ps1` 另外用 `System.Management.Automation.Language.Parser::ParseFile`
核过**解析 0 错误**（前几波剥掉过 BOM 四次，每次都当场解析失败，故本波每改一次就核一次）。
⚠️ 全部编辑一律走 **Python 二进制模式**（读 bytes → 归一成 `\n` → 改 → 还原成该文件
原有的行尾 + BOM → 写 bytes），**一个文件都没用 IDE 的编辑工具直接改过**
（本仓的行尾/BOM 事故已经发生过四次，其中三次是工具剥 BOM、一次是往 CRLF 文件里插裸 LF）。
⚠️ 唯一一次例外是 `tests/test_trial.py` 上的一处小改（用 IDE 的查找替换），
改完当场复验 `471/471 CRLF · 0 裸 LF`，故没有出事。

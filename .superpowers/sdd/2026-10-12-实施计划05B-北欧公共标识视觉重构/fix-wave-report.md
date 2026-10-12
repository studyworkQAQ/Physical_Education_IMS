# 终审 fix 波 · 实现者报告

- **分支**：`fix/final-review-findings`（从 `main` 的 `302583f` 起，未 push、未碰 main）
- **范围**：独立终审对 `a544c96..302583f`（55 个 commit）的 **0 Critical / 6 Important / 7 Minor**
  里，派单点名要修的那些 —— **I1–I5 + M1–M5 + spec 两处连带**（M6 / M7 不修，M7 只在 spec 里点一句）
- **改动面**：4 个 commit、**23 个文件**、+689 / −96 行（`git diff --stat 302583f HEAD`）
- **结论**：后端 **1333 passed** 不变、前端 smoke **18 步（0–17）/ 406 断言 / 退出码 0**、
  **零新增依赖**、两个禁区一个字节没动、四个指纹 + 18 个模板指纹逐字不变
- **顶回控制者/终审**：**3 处**（见 §7.4）；**没按派单做的地方**：**0 处**（见 §7.3）

| commit | sha | 内容 |
| --- | --- | --- |
| ① | `48284c1` | I1 + I2 —— 演示链路那两个「不能等」 |
| ② | `c19d39b` | I3 —— 9 处过期口径扫一遍（纯 docstring/注释，0 行代码变更） |
| ③ | `7858b95` | I5 + M1–M5 + spec 两处连带 |
| ④ | `1ff5d21` | I4 + 本波 5 条新守卫（smoke.mjs 第 17 步 + 第 14 步的 3 组拍） |
| ⑤ | 本文件 | 报告 |

⚠️ **commit 分组与派单建议的一处偏离**（如实记）：派单建议 ③=I4+I5、④=M1–M5+spec。
实现者换成了 ③=I5+M1–M5+spec、④=I4+全部守卫，理由是**每个 commit 都要是绿的**：
`smoke.mjs` 一个文件里同时住着 I1 / I4 / I5 / M1 / M5 五条守卫，而 I1/M1/M5 的守卫
必须在它们各自的**代码修复之后**才绿 —— 按派单的分法，commit ③ 会带着 3 条当场红的守卫。

---

## ① 环境与服务状态

### 1.1 开工第一件事（硬规矩 #73）

```
node --version    → v24.19.0
npm --version     → 11.17.0
python --version  → 3.11.1（无 venv，系统 Python @ C:\Python）
fastapi / sqlalchemy → 0.141.1 / 2.1.3
pydantic          → 2.13.5
```

四格与派单逐字相同。

### 1.2 两个还起着的服务（先查了）

`Get-NetTCPConnection -LocalPort 8000,5173 -State Listen` 实测：

| 端口 | PID | 进程 | 起于 | 归属 |
| --- | --- | --- | --- | --- |
| `::1:5173` | 16316 | node（vite） | 2026-10-11 23:07 | 前一波留下的 |
| `127.0.0.1:8000` | 69068 | python（uvicorn） | 2026-10-12 18:41 | **终审者最后一次 `demo.ps1 -Port 8000`** |

**两个都没有停、没有杀**（派单逐字：「不要硬杀别人的」）。

### 1.3 ⚠️ 本波自己起的那一套（以及为什么不能用 8000）

派单给的兜底是「换一个端口起你自己的（`demo.ps1 -Port 8011` 之类）」，而**这条路走不通**：
`demo.ps1` 非 `-DryRun` 时写死的落点是 `app.main.DEMO_DB_URL` = `backend/pe_demo.db`
（那是「演示库叫什么」的**唯一所有者**，脚本刻意不留第二个路径），而那个文件正被
PID 69068 打开着 —— 换端口换不掉这个文件冲突。故本波改成：

1. `python scripts/demo_bootstrap.py --db-url sqlite:///<TEMP>/pe_fixwave/pe_fixwave.db
   --csv-dir <TEMP>/pe_fixwave/lepao --students 60 --seed 20250828`
   （= `demo.ps1` 第 ④ 步逐字同一条命令，只是显式传了 TEMP 路径；**没有**跑
   `app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` 中任何一个）
2. `$env:PE_DB_URL` / `$env:PE_CSV_DIR` 指过去，`python -m uvicorn app.main:app --port 8011`
3. `$env:PE_API_TARGET="http://127.0.0.1:8011"; npm run dev -- --port 5199 --strictPort`
4. `PE_API_BASE=http://127.0.0.1:8011 PE_WEB_BASE=http://localhost:5199 npm run smoke`

于是**最终验收跑的是本分支的代码**（8000 上那个 uvicorn 跑的是 `302583f`，
而 I3 改的是端点 docstring → 会进 `/openapi.json` 的 description，故必须自己起一个）。
库与 CSV 全在 `$env:TEMP`，`backend/` 下**一个文件都没留**；每次重跑 smoke 前重灌一次。

---

## ② I1 —— 登录页 / demo.ps1 / demo_bootstrap / spec 印的那个学号**不在册**

### 2.1 复核（不照抄终审）

直接读演示库（`sqlite3` 只读连接）+ 对 8000 上那个还活着的后端实发请求：

```
student 表前 8 行： (1,'2025060001','周晨阳') (2,'2022080001','许建国') (3,'2025100001','马建国')
                    (4,'2023120001','赵锦程') (5,'2024090001','赵婉清') …
select count(*) where student_no='2025010004'  → 0        （总行数 60）
POST /api/auth/login {kind:student, login:'2025010004'} → 403 password_not_bound
POST /api/auth/login {kind:student, login:'2023120001'} → 200 + Set-Cookie（student.id=4 赵锦程）
POST /api/auth/login {kind:student, login:'2025060001'} → 200 + Set-Cookie（student.id=1 周晨阳）
```

**终审这一条完全成立**，连「`student.id=4` 实测是 `2023120001` 赵锦程」都逐字对。
根因也对：学号由 `app/seed/population.py:170` 的
`f"{enroll_year}{department_slot + 1:02d}{sequence[bucket]:04d}"` 现造
（入学年 4 + 院系码 2 + 序号 4 = 10 位），故**任何写死的字面量都会在改 `--students` / `--seed` 之后变假**。

### 2.2 四个住址逐个改成什么

| # | 住址 | 改成 |
| --- | --- | --- |
| 1 | `backend/scripts/demo_bootstrap.py:481` | 与下一行的教师**同构**：在 `commit()` 之前多摘一格 `student_nos = [s.student_no for s in students]`（与既有的 `teacher_staff_nos` 同一处、同一条「commit 会 expire 实例」的理由），打印改成 `任何一个在册学号（{len(student_nos)} 个，例如 {student_nos[0]}）`。实测输出：`学生：任何一个在册学号（60 个，例如 2025060001）` —— 而 `2025060001` 就是 `student.id=1`，**真能登录**（上面 200 那一拍） |
| 2 | `backend/scripts/demo.ps1:193` | 按它自己 187–190 行的**单一所有者原则**改成引用：`学生     任何一个在册学号（上面 [6/7] 那一步从库里打印了一个**真**例子）+ 演示口令`，并把上面那段注释的适用范围从「口令与管理员」扩到「口令、管理员、**以及一个真学号**」 |
| 3 | `frontend/src/views/auth/Login.vue:68` | 只描述格式、不给例子：`学号是 10 位数字：入学年 4 位 + 院系码 2 位 + 序号 4 位。在册的学号由 backend/scripts/demo.ps1 灌库那一步打印一个真例子；演示口令也在那里（spec §13 亦记）。`（教师档的 `T0001` **留着** —— 它是 `DEMO_ADMIN_STAFF_NO` 那一族固定工号，是真的，而下面那条守卫会钉住它） |
| 4 | `Document/…设计spec.md:1280` | 删掉 `例如 2025010004 = 学生 #4`，换成「本表**刻意不举具体学号**」+ 指向 `[6/7]` 那一步（见 §7.2） |
| 5 | ⚠️ **实现者多扫到第 5 个住址** | `frontend/src/stores/session.ts:146` 的 `summary` docstring 例子逐字是「学生 `2025010004` · 张三」→ 换成占位符「学生 `<学号>` · `<姓名>`」。它是**提及**而不是一个能输进去的例子，故危害比前四个小，但它是同一串假数字，留着就是给下一个人一个「原来长这样」的错样本 |

### 2.3 新守卫（`smoke.mjs` 第 14 步，6 条断言）

**派单给的是二选一，实现者选了「两个都要」的第三种**（见 §7.4 顶回 ③）：

> 「登录页 DOM 里出现的**每一个**登录名形状的串都必须真在册」

它今天在学生档上退化成「登录页不再印任何具体学号」（因为一个都没有），
而在教师档上**非空转**（`T0001` 真的印着、真的在册）；将来若有人放回一个例子，
它必须是真的 —— 于是两个选项的好处都拿到了，且不靠「禁止举例」这条会过时的规矩。

谓词：学生档 `(?<!\d)\d{10}(?!\d)`、教师档 `\bT\d{4}\b`，一律在 `toPlainText()` 的返回值上跑。
教师档那一份要额外导航一次 `/login?kind=teacher`（`Login.vue:50-51` 从 `?kind=` 读初值）。

实测输出（最终那一跑）：

```
✓ §I1 守卫不空转的前提 ①：名册读得到（60 个学号 / 3 个工号）  →  学号 60 个、工号 3 个
✓ §I1 守卫不空转的前提 ②：终审点名的 2025010004 形状上会被谓词命中
✓ §I1 守卫不空转的前提 ③：而它确实**不在**名册里  →  名册里第一个学号是 2025060001
    学生档登录页正文里的「10 位数字」串 0 个：[]
✓ §I1 学生档：登录页印的每一个「学号形状」的串都在册（今天 0 个）  →  offender=[]
    教师档登录页正文里的「T+4 位」串 1 个：["T0001"]
✓ §I1 教师档：那一格**非空**（本页确实印着 T0001 这个例子）  →  ["T0001"]
✓ §I1 教师档：登录页印的每一个「工号形状」的串都在册  →  offender=[]
```

**登录页现在印不印具体学号：不印**（学生档 0 个 10 位数字串；教师档仍印 `T0001`，而它是真的）。

---

## ③ I2 —— `demo.ps1` 对 `PE_ALLOW_HEADER_IDENTITY` 只声明、不强制

### 3.1 复核

源码取证与终审一致：改前 `demo.ps1:135-139` 只设 `PE_DB_URL` / `PE_CSV_DIR`，
全文 **0 行** `Remove-Item Env:\PE_ALLOW_HEADER_IDENTITY`，而 139 与 186 两处都是无条件 `Write-Host`。

**机制实测**（这是本条最关键的一格，故单独验了一遍）：

```
母 shell PE_ALLOW_HEADER_IDENTITY = '1'
  -- 不删（对照）:            child python sees '1'
  -- Remove-Item Env:\ 之后:  child python sees None
```

即 `Remove-Item Env:\X` **真的**把那一格从子进程的环境块里摘掉了（不是只改了 PowerShell 的视图）。

### 3.2 改法（三件，与文件里既有的两道禁区守卫同一个姿势）

```powershell
$HeaderIdentityInherited = [Environment]::GetEnvironmentVariable('PE_ALLOW_HEADER_IDENTITY')
Remove-Item Env:\PE_ALLOW_HEADER_IDENTITY -ErrorAction SilentlyContinue
$HeaderIdentityNow = [Environment]::GetEnvironmentVariable('PE_ALLOW_HEADER_IDENTITY')
if (-not [string]::IsNullOrEmpty($HeaderIdentityNow)) {
    throw ("PE_ALLOW_HEADER_IDENTITY 删不掉（本进程实测仍是 " + $HeaderIdentityNow + "）：…")
}
$HeaderIdentityShown    = if (…) { '未设' } else { '=' + $HeaderIdentityInherited }
$HeaderIdentityNowShown = if (…) { '未设' } else { '=' + $HeaderIdentityNow }
```

- **① 强制**：起 uvicorn 之前（第 ③ 节里，紧挨着 `PE_DB_URL` / `PE_CSV_DIR`）删掉进程级的那一份
- **② 删不掉就 `throw`** —— 与第 ⑤ 节那两道禁区守卫（`backend\pe.db` / `backend\data\seed\`）同一个姿势
- **③ 打印实测值**：两处无条件 `Write-Host` 都改成读上面这几个变量（**单一所有者**，
  第 ⑥ 节的第二次打印也读它们，不抄第二份）
- ⚠️ 顺带把 132-134 行「要在本机临时打开它……请在另一个终端里 `$env:… = "1"` 再起 uvicorn」
  那一句加了个限定：那个姿势**只对手工起的 uvicorn 有效**，靠 `demo.ps1` 是打不开的
  （否则本文件自己就造出一处新的「注释与代码互相打脸」，正是 M2 那一族）

### 3.3 改后的字节级口径（`read_bytes()` 实测）

| 格 | 改前 | 改后 |
| --- | --- | --- |
| 字节数 | 14 752 | **17 818** |
| **BOM** | True | **True** ✅ |
| **CRLF** | 223 | **250** |
| 裸 LF | 0 | **0** ✅ |
| 入库 blob（`git cat-file blob HEAD:…`） | 14 529 B / BOM=True / LF | **17 568 B / BOM=True / LF** ✅ |

⚠️ 全程用 **python 改**（不用 IDE 的编辑工具）—— 派单点过它已经两次吃掉这个文件的 BOM。
⚠️ 入库 blob 的 BOM 单独用 `subprocess` 取原始字节量过：`core.autocrlf=true` 只把 CRLF 折成 LF，
**BOM 是内容的一部分、照原样入库**（改前改后都是 `BOM=True`）。
（⚠️ 第一次量它时用 PowerShell 的管道 `git cat-file | python`，量出 `BOM=False / CRLF=250` ——
那是**管道自己**按控制台编码重排了字节，不是 blob 的样子；改用 `subprocess.run(capture_output=True)` 才对。）

### 3.4 新守卫（`smoke.mjs` 第 17 步 ①，10 条断言）

在 `env: { …, PE_ALLOW_HEADER_IDENTITY: '1' }` 里 `spawnSync('powershell', […, '-File', ps1, '-DryRun'])`，
断言：源码里有那一行 `Remove-Item`、文件仍带 BOM、仍纯 CRLF、退出码 0、
打印的是**实测值 `=1`**、同时说清本进程已被清成「未设」、
改前那句无条件的假话在整份输出与源码里都 0 次、而这条链真的走完了（`[7/7]` + 禁区复核）。

**在 `$env:PE_ALLOW_HEADER_IDENTITY="1"` 的 shell 里跑 `-DryRun` 的实测输出（最终那一跑）**：

```
PE_ALLOW_HEADER_IDENTITY 进本脚本时实测 =1 → 本进程已**强制**清成 未设（= 生产缺省 "0"：只认 pe_session cookie；Plan 05A Task 5 撤掉了那个过渡态的 =1）
```

退出码 **0**（它没 throw —— 因为删得掉）。未设时跑同一条命令：

```
PE_ALLOW_HEADER_IDENTITY 进本脚本时实测 未设 → 本进程已**强制**清成 未设（= 生产缺省 "0"：…）
```

两档都**不再说「未设」这句写死的话**，说的都是实测值 + 本脚本做了什么。

---

## ④ I3 —— Task 5 改掉了一条承重口径，9 处复述只更新了 1 处

### 4.1 复核（匿名 GET 逐个实测，不看源码）

```
401  /api/dashboard/class/1?week=6&as_of=2025-10-12      ← crud.py 说它「仍然匿名」
401  /api/students?limit=5                               ← 4 处说它「匿名返回全部 60 人的 birth」
401  /api/teachers?limit=5                               ← 2 处说它「name 也匿名可读」
200  /api/notifications?limit=5                          ← dashboard.py 那段的前提，仍成立
200  /api/class-sessions?limit=5                         ← feedback.py:438 那段的前提，仍成立
200  /api/mini-tests?limit=2 · /api/mini-tests/normalized · /api/enrollments · /api/semesters · /api/alerts · /api/training-logs
openapi：71 paths / 99 ops / 52 挂 security / GET 60（44 匿名 + 16 挂）/ securitySchemes 3
```

**8 处全是假话，终审逐条对**。

### 4.2 8 处逐个改成什么（一律**指向** `catalog.py:45-53`，不各自复述）

| 文件:行（改前） | 改成 |
| --- | --- |
| `crud.py:245-246` | 那句「大屏读的是 `/api/dashboard/*`（仍然匿名）」标成**假的**，并补一条 `git log -S` 取证：那 6 个 `Security(...)` 来自 `415db83`（**Plan 03 Task 8**）→ 它**写下来的当天就是假的**，不是后来才过期。同时明说「收紧名册的代价可接受」这一格**不再拿它当依据**，真依据是上面那三条（消费者都已在路由守卫之后）。末尾立规矩：账面的唯一住址是 `catalog.py`，并逐个点名其余 5 个文件「只指过去、不复述」 |
| `schemas/auth.py:78-81` | 「验身材料本身是**匿名**可读的」→ 改成「今天仍然读得到，只是**不再匿名**」；剩下的局限重写成「一个**已登录的教职**能给任何还没绑定的学生抢先绑口令（绑定只对 `password_hash IS NULL` 放行，故挡不住抢占）」 |
| `schemas/auth.py:96-99` | 「比学生那一侧**弱**：`name` 也是匿名可读的」→ 改成「与学生那一侧**同档**」，理由同上 |
| `routers/auth.py:152-154` | 「收紧它是 Task 5 的活」→ 「Task 5 已经做完了，故那一句今天反了」+ 指向 catalog |
| `routers/auth.py:201-203` | 教师侧同款：「比学生那一侧弱」→「同档」，`GET /api/teachers` 匿名实测 401 |
| `routers/auth.py:267-271` | **保留裁定、只改论证**（见 4.3） |
| `schemas/organisation.py:213-216` | 「`birth` **仍然**匿名可读……收紧它是 Task 5 的活」→「**已不再**匿名可读」+ `read_requires_staff: True` 的住址 + 指向 catalog |
| `dashboard.py:677-681` | 拆成两半：`notification` 自己那一行**没被重裁**（实测仍 200，故本端点的论证不依赖那两半）；而括号里的例子（`GET /api/students`）与「读 ⇒ 一律匿名」那句口径都过期了。顺带点明「本模块自己的 6 个端点**从来不是**匿名的」 |
| `feedback.py:437-439` | 「泛型 `GET` **一律**匿名」→「**缺省**匿名」，并明说 `class-sessions` **不在**那 2 个例外里（匿名实测仍 200）→ 下面「闸门形同虚设」那句论证**一字不变** |

### 4.3 `routers/auth.py:267-271` 的新论证（裁定不变）

改前是「三条理由」，其中 ③ 是「`GET /api/students` 今天就匿名返回全部 60 人，故这个信号本来就是公开的」。
改后：

> ⚠️ **这确实泄漏了「这个学号在不在册」**——控制者裁定**接受**（终审 I3 之后理由从 3 条变成
> **2 条**，而**裁定本身不变**）：① 原型不做防枚举；② 绑定流程本身就需要这个信号；
> ③ ⚠️ **原来的第三条今天已经断了**：……而 Plan 05A Task 5 已把那 4 个名册读收到教职身份
> （匿名实测 **401**）→ 这个信号**不再**是公开的。**换成实测过的一条**：枚举面从「匿名」缩到了
> 「**已登录的教职**」，而一个能登录成教职的人本来就读得到整份名册（含 `birth`），
> 故本端点对他**没有多给一个比特**；对匿名调用方，泄漏的仍然只是「这一串在不在册」这一个比特，
> 而 ①② 已经裁定它可接受。

同一处那句「（Task 5 会连同那 **48 个匿名 GET** 一起重新裁定）」删掉了 —— Task 5 已做，
而 48 → **44 + 4** 的那个账面只在 `catalog.py` 里说一次。

### 4.4 ⚠️ 实现者多扫到的 2 处（终审漏点）

1. **`feedback.py:981`** —— 与 `dashboard.py:679` 是**同一句**「48 个匿名 GET 里已经包括
   `GET /api/students`（60 人的出生日期）」，只是住在 `normalized_scores` 的 docstring 里
   （`frontend/src/api/generated/schema.d.ts:435` 就是它的镜像）。已改：换成实测仍匿名的
   `GET /api/mini-tests` 与 `GET /api/enrollments`，并明说「同档」论证靠的是 `mini-tests` 那一条腿。
2. **`crud.py:118`** —— 一句**现在时**的「`GET` 一律匿名」→ 限定成「泛型 `GET` **缺省**匿名
   （『一律』二字自 Plan 05A Task 5 起有了 2 个例外，账面住在 catalog）」。

### 4.5 ⚠️ 扫到但**刻意没改**的（登记为待清扫，理由见 §7.1）

- `dashboard.py:85-93` —— 一份**历史流水账**（「Plan 04 Task 3 的小修波之后……Plan 04 收尾波之后……」），
  末尾停在 46 / 66 / 94 / 59 / 48 / 11，全部过期。它是逐波追加的账、不是现在时的断言，
  补一行「Plan 05A Task 5 之后」是**另一个动作**（要把 5 个数一次性重算），已记进待清扫。
- `schemas/organisation.py:120`、`schemas/feedback.py:83-88`、`schemas/dashboard.py:349`、
  `routers/catalog.py:219/255/263/472` —— 「泛型 `GET` 一律匿名，故把秘密列留在读模型上等于摊给任何调用方」。
  对 `class-sessions` / `mini-tests` / `enrollments` 那几个资源**前提今天仍成立**；
  对 `teachers`（`password_hash`）前提已变、而**结论更强**（更不该暴露）。
  改它们只是把措辞从「一律」换成「缺省」，收益低、churn 高，已记进待清扫。

### 4.6 影响面

I3 是**纯 docstring / 注释**改动，**0 行代码变更**：1333 passed 不变、覆盖率四格不变、
26 张表 / 66 扫描面 / 71 paths / 99 ops / 52 security / GET 60（44+16）/ 3 securitySchemes 全部不变。
⚠️ 而端点 docstring **会进 `/openapi.json` 的 description** → 故 `frontend/src/api/generated/schema.d.ts`
（它是 codegen 产物、入库）在这几格上**变陈旧了**。派单逐字禁改 `src/api/**`，故**没有重跑
`npm run gen:api`**；已记进待清扫（它只差注释文本，类型一格没变，`vue-tsc` 与 406 条断言全绿）。

---

## ⑤ I4 + I5

### 5.1 I4 —— 两个同名不同义的 `plain`，与 05B 声称「永久关掉」的假出口

**复核**（node 复现终审那份最小 HTML，谓词先对已知反例验证 · 硬规矩 #107）：

```
反例：needle「的本周」只出现在 style 的注释里
  weak(轮询旧写法).includes : true   ← 会被骗
  toPlainText.includes      : false
  旧退出条件 weak||raw      : true   ← 第一拍就 break
  新退出条件 toPlainText    : false  ← 继续轮询
正例：needle 在真正文里      toPlainText.includes : true（且真名字也在）
script 里的文本              weak : true（被骗） / toPlainText : false
```

**改法**：

1. **抽到模块级、两处共用**（`smoke.mjs` 的 `fmt()` 之后）：
   `stripEmbedded(html)`（整块剥 style / script）与 `toPlainText(html)`（= `stripEmbedded` + 剥标签 + 压空白）。
   `toPlainText` 用 `stripEmbedded` 定义，故「先剥整块」这件事只有一个住址。
2. **删掉 `|| html.includes(n)`**：轮询退出条件从
   `wanted.every((n) => plain.includes(n) || html.includes(n))` 改成 `wanted.every((n) => plain.includes(n))`。
3. 三个调用点全部改读它：`dumpRoute` 的轮询、`bouncedPlain`、ROUTES 循环里的 `plain`
   （那三处此前是**两份**剥法：弱剥 + 强剥，且都叫 `plain`）。
4. 05B 那句「这一格把谓词的假出口**永久关掉**」的注释改成如实的：它当时只对**断言那一行**成立，
   轮询里还留着同一个形状。

**新守卫**（第 17 步 ②，6 条断言）：造终审那份最小 HTML，断言弱剥会被骗、`toPlainText` 不会、
真正文里的 needle 仍会命中（谓词不是恒假）、`script` 里的文本同样被剥掉；
再断言那个假出口不再出现在本文件的**代码**里。
⚠️ 最后那一格踩了两次坑，都写进注释了：① needle 必须**拼出来**（`['|| html.', 'includes(n)'].join('')`），
否则这一拍自己的标签就是一处代码里的出现、当场红在自己身上（#109）；
② 剥注释的谓词是**挖空成空格、长度不变**，故「剥完还很长」证明不了任何事 ——
反例改成「两处只在**代码**里的串剥完仍在」。

### 5.2 I5 —— DEV 深链接竞态

**复核**（自己写了一份 CDP 探针，登录成 #4、导航到 `/s/home?student=1&as_of=2025-10-12`）：

```
改前： +494ms GET /api/auth/me                 身份头 X-Student-Id: 1  ← URL 认出来的假身份
       +521ms GET /api/students/4/home         身份头 X-Student-Id: 4  ← session.adopt() 已跑
       +553ms GET /api/students/4/…completion-rate  X-Student-Id: 4
改后： +798ms GET /api/auth/me                 身份头（无）
       +929ms GET /api/students/1/home         身份头 X-Student-Id: 1
```

「发一次错的请求」**是**、「闪一下错误的身份」**否** —— 与终审逐字一致。

**选了方案 ①**（`main.ts` 把 `adoptFromUrl` 挪到 `session.ensureRestored()` **之后**、挂载之前）。理由：

1. **方案 ② 要 `client.ts` import `stores/session`**，而那正是 `client.ts` 与 `main.ts` 两处文件头
   **逐字记着「刻意避开」**的那个导入环（`client → session → api/auth → client`）——
   `api/expiry.ts` 的 `fire` / `subscribe` 间接层就是为它而存在的。走 ② 要么把环造回来、
   要么再加第三个间接模块：为一个 DEV-only 的工具付这个代价不值。
2. **① 不花任何额外时间**：`router.beforeEach` 本来就 `await` 了同一个（memo 过的）Promise，
   任何页面组件都在它之后才可能挂载 → 首屏本来就在那一次请求之后。
   这里只是把「认 URL 身份」排进同一条队，**0 次额外往返**。
3. **① 修的是终审点名的根因**（`main.ts` 在会话未知之前就把身份写进 store），
   ② 只是在那个 store 的一个读者上遮住症状。
4. 生产那一支**同步挂载、与改动前逐字同形**：`if (import.meta.env.DEV) { void (async () => {…})() } else { mount() }`，
   `mount()` 是 `app.mount('#app')` 的唯一住址。`check:dist` 仍然全绿（`adoptFromUrl` 在 dist 里 0 次、源码里在）。

**另加一格（终审点的第二个危害）**：`ensureRestored()` **抛**的时候（后端不可达 → `status='unknown'`
→ 守卫放行 → `session.adopt()` 不跑）**不认** URL 身份，否则一个未验证的 id 会被写进**持久化**的
`stores/identity`、留在 `localStorage` 里给下一次刷新。

**⚠️ 一处如实记录的行为变化（硬规矩 #39）**：改前 `session.adopt()` 的兼容桥总在 `adoptFromUrl` 之后跑，
故一个与会话不符的 `?student=` 会被**静默冲掉**（那一格事实上是死的）；挪了顺序之后 **URL 那一格赢了**，
于是 `?student=1`（会话是 #4）会真的去打 `/api/students/1/home` → 后端 `require_scope` 按**会话**判、回 **403**。
这是有意的：响亮的 403 好过静默忽略 URL，而本波修的正是「账面说的与代码做的相反」这一族。
⚠️ 而**拆那座桥本身不是本波的活**（05B 待清扫第 14 条），`stores/` 里除了 `session.ts:146` 那句
docstring 例子（I1 的第 5 个住址）之外**一行没动**。

**新守卫**（第 14 步末，5 条断言）：清干净 `localStorage` + 种一份学生 cookie，
导航到 `?student=<另一个人>&as_of=…`，用 `Network.requestWillBeSent` 抓顺序。实测：

```
✓ §I5 反例前提：URL 上要认的那个学生与会话里那个**不是同一个人**  →  会话=#4 URL=#1
✓ §I5 localStorage 已清空  →  actual=0 expected=0
✓ §I5 会话 cookie 种进浏览器了  →  {"success":true}
✓ §I5 抓到了后端请求（守卫不空转）  →  2 个
✓ §I5 第一个后端请求就是 GET /api/auth/me  →  actual=/api/auth/me expected=/api/auth/me
✓ §I5 而那第一个请求**不带任何身份头**  →  {"url":"/api/auth/me","student":null,"teacher":null}
```

**第一个请求还带不带未验证的身份头：不带**（`student:null, teacher:null`）。

⚠️ 这一拍首跑是**红**的，而红得很有信息量：它抓到 `X-Teacher-Staff-No: T0003`。
真因不是 I5，而是上面 15 条路由的取证用管理员 jar 打开过 `/admin`，兼容桥把 `T0003` 写进了
**持久化**的 identity store → 本拍导航时它被 rehydrate 出来。那是「上一份会话遗留的、
曾经被后端验证过的身份」，属于 05B 待清扫第 14 条（拆桥）的面、**不是本波的活**。
故本拍按终审的复现姿势来：先 `localStorage.clear()`（并断言它真的空了），再导航。
⚠️ 谓词也踩过一次坑：`url.includes('/api/')` 会把 vite 的模块请求（`/src/api/client.ts`）算进来，
于是「第一个请求」永远是模块请求、恒绿 —— 改成 `startsWith('/api/')`（只认后端 API）。

---

## ⑥ M1–M5

### M1 `base.css:136-140` 两处硬伤

- 「类名从 `surface-base` / `surface-board` **改成** `surface-base` / `surface-board`」→ from 与 to 逐字相同、
  那句话是空的。改成它**想说**的那件事：CSS 类名用 base/board 两个词，而 `meta.surface` 的字面值仍是
  `paper` / `ink`（`router/index.ts` 那一格在 05B 禁改），映射的唯一住址是 `App.vue` 的 `surface` computed。
- 「判据仍是 `meta.surface === 'board'`」→ **`'board'` 不在 `surface` 的取值域里**
  （`RouteMeta` 声明 `'paper' | 'ink'`，只有 `/t/dashboard` 设了 `'ink'`，`App.vue:43` 比的也是 `'ink'`）。
  改成 `=== 'ink'`，并把「照它改会静默让大屏丢掉 `.surface-board`、05B 的核心手法当场失效，
  而 `check:tokens` 只查色值、`vue-tsc` 拦不到注释里的字面值」这一段后果逐字写进去。

**新守卫（两层，后者更强）**：

1. **渲染后的真值**（第 14 步，15 条断言 —— 15 条路由逐条）：用 CDP 取 `document.querySelector('.app').className`。
   实测 `t-dashboard` → `class="app surface-board"`，其余 **14 条** → `class="app surface-base"`。
   ⚠️ 逐条断而不只断大屏：少了另外 14 条，「大屏拿到了 surface-board」可能只是因为它两条都拿到了。
2. **源码面**（第 17 步 ③，4 条断言）：`router/index.ts` 与 `App.vue` 的**代码**里
   `surface` 字面值 ⊆ `{paper, ink}`，`'board'` 不在其中。
   实测：`router/index.ts = ["ink"]`、`App.vue = ["ink"]`。
   ⚠️ 必须先剥注释（#109）：M1/M2 的改动说明里逐字引用了 `meta.surface === 'ink'`，
   首跑实测 `App.vue` 因此匹配到 **3** 处而不是 1 处（全绿，但数的是「代码 1 + 提及 2」）；
   剥完之后断言抬成「**恰好 1 个**」—— M2 删掉死支之后就该只剩那一处。

**`'board'` 是否已从全仓消失：没有，也不该消失**（见 §7.4 顶回 ①）。

### M2 `App.vue:52` 的死支

`route.meta.wide === true || route.meta.surface === 'ink'` 的第二个从句是**死支**
（全仓只有 `/t/dashboard` 设 `surface:'ink'`，而那一条**同时**带 `wide:true`），
而紧邻注释（45-51）逐字写着「两者**各管一件事，不再互相搭车**」→ 同屏打脸。
**删的是代码那半**（注释才是那一格的裁定），并把注释里两处「深底」改成「底色」
（05B 已翻浅底，「深底」这个词本身也过期了）。补一句它为什么不只是难看：
留着它，下一个加一条 `surface:'ink'` 而**不想**要宽壳的路由的人会得到一个他从未声明过的 1440px 壳。

### M3 `router/index.ts` 的两处

- `:222` 「`surface` 仍是缺省的 `paper`（**深底**只有大屏那一块 —— 投影场景才需要）」→
  那个括号自 05B 起过期（大屏已翻浅底，`.surface-board` = `--surface` = 一档极浅冷灰；
  `ink` 选的是「大屏那一档排版」而**不是**深底）。改成指向 `base.css` 与 `RouteMeta.surface` 的 docstring，不复述。
- `:71` `/** 底色。缺省 paper。*/` → 补上「两个字面值今天都是浅底」+ 两个字面值各自映射到哪个 CSS 类 +
  「`ink`（墨）这个名字翻浅底之后会撒谎、而这两个字面值在 05B 禁改（本波也没动它们，改的只是注释）」。
- ⚠️ 这两处**都只是注释**：`surface?: 'paper' | 'ink'` 那个类型声明与 `'ink'` 那个字面值**一个字没动**
  （05B 的禁改清单在**本波**解禁了，但解禁不等于要改 —— 改它要连带改 `App.vue` 与 15 条路由，
  收益只是「名字好听」，已记进待清扫）。

### M4 `frontend/package.json:6`

- **有没有 sha256 指纹测试：没有**（实测）。`backend/tests/**` 里 `package.json` 命中 **0** 次、
  `frontend/scripts/**` 里也只有 3 处**提及**（`shots.mjs` 说「刻意不挂 npm run shots，因为那要改
  package.json，而 05B 的验收里有一格是『package.json 有没有被改』」——那是**人工**看一眼 `git diff`，
  不是自动指纹）。故改它**不需要**连指纹一起改，也不需要先跑全量收红（硬规矩 #88 的前提不成立）。
- description 改成：`体育闭环原型系统 · 前端（学生端 H5 / 教师大屏 / 管理台）。美学方向：北欧公共标识（简洁、蓝白色调、浅色系、按钮圆角）。`
  （四条形容词逐字取自 05B 的用户要求 R1，`smoke.mjs` 第 15 步的注释里也是这么引的）
- ⚠️ 顺带修了同文件 `"//"` 那一格里两处过期账面（它们是「新人读到的第一个文件」的一部分）：
  「smoke 是 **17 步（0–16）/ 305 条断言**」→「**18 步（0–17）/ 406 条断言**」（并如实记下
  05A 那一版是 305、05B 那一版是 354，故这一格在改之前**已经是假的**）；
  「零新增依赖（Plan 01–05A 全程）」→「Plan 01 至本波全程」。
- ⚠️ **`dependencies` 与 `devDependencies` 两格一个字节没动**（实测逐字比对 `git diff 302583f`：
  只有 `description` 与 `"//"` 两行变了）→ 前后端**新增依赖都是 0**。JSON 仍然合法（`require()` 过）。

### M5 那个「不知道」的破折号

**11 处换了几个：全换了 —— 而实测是 12 个字面量、不是 11 处。**
派单按 file:line 数出 10 对（`IdentitySwitcher 309,310` / `LayerDonut 190` / `ProgressBoard 213,244` /
`AlertQueue 682,683` / `Dashboard 635` / `StudentDetail 386,988`）而写成「11 处」；
`Dashboard.vue:635` **一行里有 3 个**字面量，故按**字面量**数是 **12** 个（硬规矩 #111：常量的当前值一律实测）。
12 个全部换成 `UNKNOWN`；`AlertQueue` / `Dashboard` / `StudentDetail` 三个文件本来就 import 了它
（`:84` / `:86` / `:88`）却在同文件里又抄一份，另外三个补了 import
（`IdentitySwitcher` 新加一行 `import { UNKNOWN } from '../present'`、
`LayerDonut` 把它加进既有的 `import { LAYER_SLOTS } from '../../present'`、
`ProgressBoard` 新加一行 `import { UNKNOWN } from '../../present'`）。

**`LayerDonut.vue:188` 那一处保没保：null 分支保留、字面量换掉**（顶回派单留的那一格，见 §7.4 ②）。
那条注释的理由是「`total === 0` 时不画环，故这里的 `pct` 恒非 null；仍然留一个 null 分支是为了
『不知道不得显示成 0』那一档不留活口」—— **这个理由成立，故分支保留了**。
而它论证的是「**要有 null 分支**」，**不是**「要抄第二份字面量」；换成 `UNKNOWN` 之后
分支一个字没动、防御性一模一样，而字符有了唯一住址。注释已就地改写说清这个区分。

**新守卫**（第 17 步 ④，5 条断言）：扫 `src/**/*.vue`，剥注释（与 `check-tokens.mjs` 同口径）之后
断言**引号包着的**单个 U+2014 = 0 处，且 `present.ts` 的 `export const UNKNOWN = '—'` 还在。
实测：`扫了 27 个 .vue 文件，代码里引号包着的「—」共 0 处`。
两条反例（#107）：谓词**会**命中 `{{ a ?? '—' }}`；而**不**命中引号里的中文破折号 `'——'`
（那是散文标点、不是那个占位符 —— 全仓 `——` 有几百处，不区分会当场淹掉）。

**⚠️ 这条守卫**守不住**什么（如实记）**：**模板文本节点**里的 `<span class="unknown">—</span>`
不在它的面上（那不是「引号包着的字面量」）。实测全仓还有 **27 处**、散在 10 个 `.vue` 里。
把它们换成 `{{ UNKNOWN }}` 要给其中 6 个文件各加一次 import，是一个比 M5 大一档的改动
（且要重跑 15 条路由的重叠守卫），已记进待清扫；守卫把那个数**打印出来**，故它不会静默长大。

---

## ⑦ 待清扫 / 关切 / 没按派单做的地方 / 顶回

### 7.1 待清扫（本波新增 6 条 + 沿用 05B 的清单）

| # | 条 | 为什么本波没做 |
| --- | --- | --- |
| 1 | `dashboard.py:85-93` 那份**历史流水账**末尾停在 46 / 66 / 94 / 59 / 48 / 11，全部过期（今天 52 / 71 / 99 / 60 / 44 / 16） | 它是逐波追加的账、不是现在时的断言；补一行「Plan 05A Task 5 之后」要一次性重算 5 个数，是另一个动作 |
| 2 | `schemas/organisation.py:120`、`schemas/feedback.py:83-88`、`schemas/dashboard.py:349`、`routers/catalog.py:219/255/263/472` 里的「泛型 `GET` 一律匿名」 | 对 `class-sessions` / `mini-tests` / `enrollments` 前提今天仍成立；对 `teachers`（`password_hash`）前提已变而**结论更强**。改它们只是把「一律」换成「缺省」，churn 高、收益低 |
| 3 | `frontend/src/api/generated/schema.d.ts` 的 description 变陈旧（I3 改的是端点 docstring，而它进 openapi） | 派单逐字禁改 `src/api/**`。它只差注释文本、类型一格没变（`vue-tsc` 与 406 条断言全绿）。重跑 `npm run gen:api` 要后端起着、且会造一个 346 KB 的 diff |
| 4 | 模板文本节点 `>—<` 还有 **27 处**（10 个 `.vue`），不在 M5 那条守卫的面上 | 换成 `{{ UNKNOWN }}` 要给 6 个文件各加 import，比 M5 大一档；守卫已把这个数打印出来，故它不会静默长大 |
| 5 | `meta.surface` 的字面值仍叫 `paper` / `ink`（`ink` = 墨，翻浅底之后会撒谎） | 改它要连带改 `App.vue` 与 15 条路由，收益只是名字好听。**本波已把三处注释全部改对**（`base.css` / `App.vue` / `router/index.ts`），并有两层守卫钉住字面值 ⊆ `{paper, ink}` |
| 6 | `session → identity` 那座兼容桥（05B 待清扫第 14 条） | 派单逐字：「那不是本波的活」。本波一行没动它，只在 I5 的守卫里如实交代了它对本拍取证的干扰 |
| — | 沿用 05B 的清单（含 M6 `verify_password` 的迭代次数只有下界没有上界、M7 的 ANONYMOUS 一帧） | 终审自己说原型口径下可不做 / 不是缺陷。**M7 已按派单在 spec §13.4.2 点了一句**（见 7.2） |

### 7.2 spec 的两处连带（都做了）

- **§13.4.3 那一行**：删掉 `例如 2025010004 = 学生 #4`，换成「本表**刻意不举具体学号**：名册是
  `app/seed/population.py` 按『入学年 + 院系码 + 序号』现造的，一个字面量会在改 `--students` / `--seed`
  之后变假 → `demo.ps1` 的 `[6/7]` 那一步**从库里**打印一个真例子」。
- **M7**（§13.4.2 那个 `HttpOnly` 引用块里补一段）：「刷新之后**约一帧**（本机实测约 40 ms）
  报头上那一枚身份 pill 会显示 `ANONYMOUS`……**这是 HttpOnly cookie『只能问后端』的固有代价**」，
  并逐字写下**它不是 bug、请不要去修它**，以及三个替代方案为什么都更坏
  （① 抄进 `localStorage` = 上一句刚否掉的第二个真相；② 那一帧藏起报头 = 布局跳动，比一个词更抢眼；
  ③ 阻塞首屏直到 `me` 回来 = 把「后端没起」也变成白屏，而守卫对那一档刻意**放行**）。

改法与字节级口径：⚠️ **用 python 改**（不用编辑器工具），改前改后都用 `read_bytes()` 量：

| 格 | 改前（= 派单给的数，实测复核一致） | 改后 |
| --- | --- | --- |
| 字节数 | 189 889 | **191 076** |
| 行数（按 CRLF 切） | 1 514 | **1 526** |
| CRLF 计数 | 1 513 | **1 525** |
| 裸 LF | 0 | **0** |
| BOM | False | **False** |
| sha256[:16] | `89EC13281E9D71E0` | **`00732A13CE0BE2C1`** |

### 7.3 没按派单做的地方：**0 处**

派单点名的每一条都做了（I1 的 4 个住址 + 守卫、I2 的 3 件 + 守卫、I3 的 8 处 + `auth.py:267-271`
的保裁定改论证、I4 的 3 件 + 守卫、I5 的二选一 + 守卫、M1–M5、spec 两处、M6/M7 不修）。
三处**做得比派单多**（都是同族的额外住址，逐个在正文里标了）：
I1 的第 5 个住址 `stores/session.ts:146`、I3 的 `feedback.py:981` 与 `crud.py:118`、
M4 顺带修的 `package.json` 那两处过期账面。
一处**分组偏离**（commit ③/④ 的内容划分）在报告开头逐字交代了理由。

⚠️ 而「0 处」说的是**派单点名要做的事**一件没漏、也没换做法；它**不**涵盖副作用 ——
本波有一处副作用要单独交代：**第一次 smoke 跑用了缺省的 `PE_API_BASE=…:8000`，把
`backend/pe_demo.db` 写脏了**（它已进 `.gitignore`，故对入库内容 0 影响）。逐字取证与
「控制者要怎么复原」见 §7.5 关切 2。

### 7.4 顶回控制者 / 终审的地方：**3 处**

**① 顶回终审 M1 的措辞**：「`'board'` 这个字面值**全仓不存在**」**不成立**。
实测它在 6 个组件里是 `tone` 那个 prop 的字面值（`tone?: 'paper' | 'board'`：
`SectionHead` / `StatBlock` / `CompletionBars` / `LayerDonut` / `ProgressBoard`，
外加 `Dashboard.vue` 的 14 处 `tone="board"` 与两个 CSS 类 `.section--board` / `.stat--board` 等）。
它与 `meta.surface` 是**两根轴**：`tone` 管组件的排版档位、`surface` 管页面底色。
→ **裁定不变**（`base.css` 那一句确实要改、`meta.surface === 'board'` 确实是假的），
而**守卫因此多了一拍**：反向断言 `'board'` 确实存在于本仓、且它是 `tone` 的字面值
（少了这一拍，「`'board'` 不在 surface 的字面值里」会被下一个人读成「`'board'` 全仓不存在」，
于是去把 6 个组件的 `tone="board"` 全改名 —— 那会当场砸掉大屏的排版档位）。

**② 顶回派单留给实现者裁量的 M5 那一格**（`LayerDonut.vue:188`）：**不豁免它**。
读了那条注释：它的理由是「`total === 0` 时不画环，故 `pct` 恒非 null；仍然留一个 null 分支是为了
『不知道不得显示成 0』不留活口」—— 这个理由**成立**，故 **null 分支保留了**；
而它论证的是「要有 null 分支」，**不是**「要抄第二份字面量」。
故字面量照样换成 `UNKNOWN`（防御性一字不变），守卫里也**不给它开豁免名单**
（豁免名单就是「下一个人在这里再抄一份」的许可证）。注释已就地改写说清这个区分。

**③ 顶回派单留给实现者裁量的 I1 第 5 拍**：**两个选项都不选，选了它们的并集**。
「示例学号必须真能登录」今天是**空转**的（登录页一个例子都不印了 → 没有东西可验，
而一条空转的守卫与一条坏掉的守卫在输出上长得一样，硬规矩 #50）；
「断言登录页不再印任何具体学号」今天非空转、而将来有人放回一个**真的**例子时它会假红。
→ 改成「登录页 DOM 里出现的**每一个**登录名形状的串都必须真在册」：
学生档今天 0 个（= 第二个选项的效果），教师档 1 个 = `T0001` 且在册（**非空转**，= 第一个选项的效果），
将来放回例子时它必须是真的（= 两个选项的好处都拿到）。
另加两拍反例把学生档那一半从「空转」里救出来：`2025010004` 形状上**会**被谓词命中、
而它确实**不在**名册里。

### 7.5 关切（不阻塞，逐字留给控制者）

1. **I5 那处行为变化**（§5.2 末尾）：一个与会话不符的 `?student=` 从「静默被冲掉」变成
   「真的打过去 + 后端 403」。实现者认为这是正确的方向（响亮 > 静默），而它是**行为**变化，
   故显式顶上来让控制者裁一次。若控制者要「会话优先」，改法是给 `adoptFromUrl` 的调用加一个
   `if (!session.isAuthenticated)` —— 一行的事，但那会让这个 DEV 工具在所有可达路径上都变成 no-op。
2. ⚠️⚠️ **`backend/pe_demo.db` 被本波写脏了**（如实记，硬规矩 #39；本波唯一一处「动了不该动的东西」）。
   **第一次** smoke 跑（就是那一跑出 2 条红、用来定位 I5 与 I4 两个守卫**自身**缺陷的）用的是
   **缺省** `PE_API_BASE = http://127.0.0.1:8000` —— 即终审者那一个 uvicorn + `backend/pe_demo.db`。
   它因此被写脏，实测（只读连接）：

   | 格 | 终审者灌完时 | 现在 |
   | --- | --- | --- |
   | `semester` | 2 | **3**（+1，就是 smoke 第 10 步建的那个、`on_delete="forbid"` 删不掉） |
   | `alert` 里 `pending` | 32 | **30**（第 9 步处置了一条、第 10 步那条学期连带一条） |
   | `class_session` | 8 | **10** |
   | `user_session` | 7 | **20** |

   之后本波**一律**打在自己起的 8011 + `$env:TEMP\pe_fixwave\pe_fixwave.db` 上，`pe_demo.db` 没再被动过。
   ⚠️ 它**已进 `.gitignore`**，故对入库内容 0 影响（`git status --short` 干净、`git diff 302583f HEAD -- backend/data` 为空）。
   → **控制者若要拿 8000 那一套复跑 smoke，请先重跑 `backend\scripts\demo.ps1`**（它第一步就是删旧库、
   而第 0 步核实的就是「一个刚复原的演示库」的行数，脏库上它会红）；⚠️ 而那要先停掉 PID 69068
   （本波按派单**没有**停它、也没有起 8000 上的第二个 uvicorn）。
   ⚠️ 另外 8000 上那个 uvicorn 跑的仍是 `302583f` 的代码（而 I3 改的是端点 docstring → 会进
   `/openapi.json` 的 description），故拿它验本波的 I3 会得到改前的文本。
3. **`Document/shot-*.png` 那 15 张截图**：一个字节没动、也没重拍。
   ⚠️ 而 M5 把 12 个 `'—'` 换成了 `UNKNOWN`（字符逐字相同）、M2 删了一条死支（行为不变），
   故这 15 张**应当**逐像素不变；实现者**没有**重拍对拍（那要重跑 `shots.mjs`，
   而它刻意没挂 npm script）。若控制者要一份对拍证据，`node frontend/scripts/shots.mjs` 一条命令即可。

---

## ⑧ 最终验收

### 8.1 后端（全部实测，不用正则数源码 · 硬规矩 #89 / #103）

| 格 | 基线 | 本波 | |
| --- | --- | --- | --- |
| `pytest -q`（不带 cov） | 1333 passed | **1333 passed**（188.77 s） | ✅ 不变 |
| `pytest -q --cov=app --cov-branch` | 1332 passed + 1 skipped | **1332 passed, 1 skipped**（366.13 s） | ✅ 不变 |
| `app/domain/` 覆盖率四格 | 1268 / 0 / 376 / 0 / 100% | **Stmts 1268 · Miss 0 · Branch 376 · BrPart 0 · 100.00%**（18 个文件聚合） | ✅ 逐字不变 |
| 全仓 TOTAL | — | 6528 / 173 / 1528 / 95 / **97%** | — |
| 表数（`Base.metadata.tables`） | 26 | **26** | ✅ |
| 架构守卫扫描面 | 66 | **66**（pipeline 10 + db 12 + domain 18 + api 23 + auth 3） | ✅ |
| 端点（`app.openapi()["paths"]`） | 71 路径 / 99 操作 | **71 / 99** | ✅ |
| 挂 `security` 的操作 | 52 | **52** | ✅ |
| GET | 60（44 匿名 + 16 挂 security） | **60（44 + 16）** | ✅ |
| `securitySchemes` | 3 格 | **3**（`X-Student-Id` / `X-Teacher-Staff-No` / `pe_session`） | ✅ |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（`tests/db/test_models.py:687` 与 `:793` 两条断言都绿） | ✅ |

### 8.2 禁区与指纹

| 格 | 实测 | |
| --- | --- | --- |
| `Test-Path backend\pe.db` | **False** | ✅ |
| `backend/data/seed/` 文件数（`-File -Recurse`） | **0** | ✅ |
| `git diff 302583f HEAD -- backend/data` | **空** | ✅ 一个字节没动 |
| `national_standard_2014.csv` | **`D2C8E539E2FA0029`**（21 412 B） | ✅ 逐字不变 |
| `exercises.yaml` | **`5394B37F01DAC9AC`**（23 247 B） | ✅ |
| `exercise_equivalence.yaml` | **`822CB86A5E998301`**（8 245 B） | ✅ |
| `alert_rules.yaml` | **`E48E3AC82BB45BB7`**（6 037 B） | ✅ |
| 18 个模板 YAML | **18 个**，全部 `i/lf w/lf`，`test_template_yaml_fingerprints_are_pinned` 绿 | ✅ |
| `app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` | **一次都没跑** | ✅ |

（四个指纹按 `tests/test_refdata*.py` 的同口径算：行尾归一化为 LF 之后取 sha256 前 16 位大写。）

### 8.3 前端

| 格 | 基线 | 本波 | |
| --- | --- | --- | --- |
| `npm run build` 退出码 | 0 | **0** | ✅ |
| 产物 | 129 modules · CSS 61.02 kB · JS 165.57 kB | **129 modules transformed · `index-CHO6HjfU.css` 61.02 kB（gzip 8.88）· `index-DU81JvpS.js` 165.69 kB（gzip 58.02）** | ⚠️ JS **+0.12 kB**（M2 删了一条死支、M5 多了 3 个 import；CSS 的 hash 与字节数逐字不变） |
| `npm run check:tokens` | 绿 | **绿**（扫描面 32 个文件 ≥ 下界 25；`tokens.css` 之外 0 处色值字面量） | ✅ |
| `npm run check:dist` | 绿 | **绿**（扫了 22 个文件 / 465.5 kB；`adoptFromUrl` 在 dist 里 **0** 次、在源码里确实存在） | ✅ |
| `npm run smoke` | 17 步（0–16）/ 354 断言 / 退出码 0 | **18 步（0–17）/ 406 断言（406 绿 / 0 红）/ 退出码 0** | ✅ +1 步 / +52 断言 |
| 路由条数 | 15 | **15**（第 14 步 `eq('路由条数 = 15…')` 绿） | ✅ |
| `@ts-ignore` / `@ts-expect-error` / `as any` | 0 | **0** | ✅ |
| 新增依赖（前端 / 后端） | 0 / 0 | **0 / 0**（`package.json` 只有 `description` 与 `"//"` 两行变；`pyproject.toml` 一个字节没动） | ✅ |

第 14 步 **109** 条断言（改前 82 + I1 的 6 + M1 的 15 + I5 的 6），
第 17 步 **25** 条断言（① 10 + ② 6 + ③ 4 + ④ 5）。
18 步逐条：`00 23/23 · 01 5/5 · 02 10/10 · 03 9/9 · 04 7/7 · 05 9/9 · 06 10/10 · 07 41/41 ·
08 14/14 · 09 13/13 · 10 17/17 · 11 6/6 · 12 22/22 · 13 15/15 · 14 109/109 · 15 8/8 ·
16 63/63 · 17 25/25` = **406**（逐格相加实测 = 406，与脚本自报的总数对上）。

### 8.4 字节级 / 行尾口径（改前 → 改后，全部 `read_bytes()` 实测）

| 文件 | BOM | 行尾 | 备注 |
| --- | --- | --- | --- |
| `backend/scripts/demo.ps1` | True → **True** | CRLF 223 → **250**，裸 LF **0** | 用 python 改；入库 blob 17 568 B / BOM=True / LF |
| `Document/…设计spec.md` | False → **False** | CRLF 1513 → **1525**，裸 LF **0** | 用 python 改；见 §7.2 |
| `backend/app/**`（6 个文件） | False → **False** | 纯 CRLF，裸 LF **0** | — |
| `frontend/**`（13 个文件） | False → **False** | 纯 CRLF，裸 LF **0** | 工作树 CRLF / index LF（`git ls-files --eol` = `i/lf w/crlf`） |
| `frontend/scripts/smoke.mjs` | False → **False** | CRLF 2106 → **2465**，裸 LF **0** | ⚠️ 中途被 IDE 的编辑工具写出过 **2 个裸 LF**（第 2205-2206 行），已用 python 归一回 CRLF 并复测为 0 |

### 8.5 工作树 / 入库

```
git status --short  → 干净（0 个 M / 0 个 ??）
git diff --stat 302583f HEAD → 23 files changed, 689 insertions(+), 96 deletions(-)
```

⚠️ 加进 index 的一律**按文件名逐个加**（4 次 `git add`，一次都没用 `-A` / `.`）；
`node_modules` / `pe_demo.db` / `frontend/dist` / `.coverage` / `$env:TEMP` 下的探针
**一个都没进**（`git status --short` 里没有 `??` 行，故它们全在 `.gitignore` 里）。
⚠️ 探针脚本一律放 `$env:TEMP`、写完先 `python -m py_compile`、跑完删掉（硬规矩 #108）。
⚠️ **没有 push**、**没有碰 main**。

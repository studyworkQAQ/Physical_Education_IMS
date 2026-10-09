# Task 1 简报 — FastAPI 骨架 + 依赖注入 + 作用域闸门

> 本简报由控制者从 `Document/2026-10-08-实施计划03-反馈预警与CRUD-API层.md` 按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + Global Constraints + Review Focus + File Structure + **Task 1 全节**。Task 2–9 的正文不在本简报里。

## 0. 派单说明（控制者写，不在计划正文里）

**这是 Plan 03 的第一个 Task，也是整个项目第一次有 HTTP 层**——Plan 01/02 交付的是一个批处理系统（`python -m app.pipeline.daily`），今天 `backend/app/api/` 目录**不存在**、`app/main.py` **不存在**。你这个 Task 做完，`uvicorn app.main:app` 就能起得来、`/api/health` 与 `/docs` 就能打开。后面 8 个 Task 全部建在你这一层上。

**代码基线**：`5b4a10c`（分支 `feature/plan-03-feedback-alert-crud-api`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **807 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**（带 `--cov` 时 `806 passed, 1 skipped`）。
**表数基线**：**18 张**（本 Task 不建表；Task 2 之后是 25）。
**架构守卫扫描面基线**：**35**（pipeline 8 + db 11 + domain 16）。**本 Task 要给它加 `api` 这一层**，故扫描面会涨——**涨了多少要在报告里写明**（S6 的裁定：下界断言由本 Task 一次性抬到位，后面 8 个 Task 不再动它）。
**环境**：Python 3.11.1（**无 venv**）、SQLAlchemy **2.1.3**、**FastAPI 0.141.1 / Starlette 1.7.0 / Pydantic 2.13.5 / uvicorn 0.54.0 / httpx 0.28.1（全部已装，`pyproject.toml` 早已声明，本 Task 不引入任何新依赖）**、pandas 3.0.6、numpy 2.4.6、PyYAML 6.0.3。

⚠️ **开工第一件事（硬规矩 #73）**：跑
`python -c "import sqlalchemy, fastapi, uvicorn, httpx, pydantic, yaml; print(sqlalchemy.__version__, fastapi.__version__)"`
把版本记进报告。**若撞上 `ImportError: DLL load failed`（Windows Smart App Control 拦 `.pyd`），立刻停手、在报告里写明、结束任务交回控制者** —— 不要动系统安全设置、不要升降级依赖。（Plan 02 撞过一次，文件一个字节都没变也被拦，最后是换 SQLAlchemy 补丁版本解决的。）

## 0.1 ⚠️ 本 Task 的三个坑（控制者预检时查出，逐条照办）

1. **`pe.db` 禁区 vs「要真的把服务跑起来」**：Global Constraints 写着 `backend/pe.db` **不得存在**（Plan 01 立它是因为 `app.seed.generate` 会写它、而那份数据不可复现）。**但 Step 4 要你手工起一次 uvicorn。** 决定：**测试一律用内存库**（`sqlite://` + `StaticPool`，`conftest.py` 提供）；**手工演示用 `backend/pe_demo.db`**（新文件名，**要加进 `.gitignore`**）。**`pe.db` 仍然是禁区**——起 uvicorn 时**必须显式传 `db_url`**，不能让它落到 `DEFAULT_DB_URL`（那大概率就是 `pe.db`）。⚠️ **跑完 Step 4 之后立刻用 python 核实 `backend/pe.db` 仍不存在**，并把结论写进报告。这条是本 Task 最容易破的禁区。
2. **架构守卫今天不认识 `api` 这一层**：`test_layering.py` 扫的是 `("pipeline", 7)` / `("db", 11)` / `("domain", 16)` 三个目录、有一批下界断言（`>=5` / `>=8` / `>=16` / `len(real_py) >=40` 之类）。**加一层会让这些下界与「扫描面」的实测值同时变**。⚠️ **按硬规矩 #88：改完跑一次全量、把红掉的相等断言逐个收进来**，不要只 grep 那个数——Plan 02 Task 6 的教训是「漏的两格不是『表数这一个事实的副本』，而是『别的事实被同一改动证伪』」。
3. **`api` 层的依赖方向要显式定死**：`api` 可以 import `db` / `domain` / `pipeline` / `refdata*` / `config` / `notify`；**反向一律禁止**（`domain` 与 `db` 都不许 import `api`）。⚠️ **`domain` 的纯净性守卫会不会因为多了 `api` 这一层而误判？** 先实测：`test_domain_purity.py` 与 `test_layering.py` 各自怎么发现「哪些目录属于哪一层」的，**照它既有的机制加**，不要另发明一套。

## 0.2 执行强度（账本 Ruling 1）

**目标 0–1 轮 fix round。**
- **保留（一条不许砍）**：TDD 先红后绿；`app/domain/` 分支覆盖 100%（本 Task 不加 domain 代码，故四格应保持 **996 / 288**，若变了要说明为什么）；单一所有者；断言两侧不同源；架构守卫全绿；**Plan 01/02 的 807 条既有测试一条都不许退步**。
- **不做变异**（Ruling 1 的裁定：变异只在 Task 6 的预警阈值要求）。
- **取消**：纯散文精度 → 记进报告的「待清扫」清单，不返工。**但 Critical 级（会让生产代码错、会让守卫假绿、会让数据不可追溯）一律当场修。**

## 0.3 纪律

- **分支** `feature/plan-03-feedback-alert-crud-api`。**不要 push、不要切分支、不要碰 main。**
- **PowerShell**：`;` 分隔，不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑写临时 `.py`。**所有写文件走 python**（`Add-Content` 会静默写坏中文）。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。
- **`git add` 按文件名逐个加**，不要 `git add -A` / `git add .`。
- **禁区**：`backend/pe.db`（不得存在，见 0.1 第 1 条）、`backend/data/seed/`（0 文件）、`backend/data/**` **一个字节都不许动**（三个指纹 `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301`）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**。
- **数键/字段/成员/目录里的文件数一律用运行时口径**（`len(...)`），**绝不用正则数源码**；**数行尾/字节数用 `read_bytes()`，不用 `read_text()`**（Python 通用换行会把 `\r\n` 翻成 `\n`）。硬规矩 #89/#93。
- **⚠️ 不要用编辑器工具反复改 `.superpowers/` 下的文件**（IDE 曾把陈旧且截断的缓存写回磁盘，Plan 02 永久丢了约 107 KB；就在昨天它又截断了 `task-3-report.md` 与 `task-4-report.md`，靠 git 才救回来）。**报告一律用 python 写。**

## 0.4 ⚠️ 若你认为简报/计划某条决定是错的，**顶回来**

Plan 02 里实现者顶回控制者 **25 次，25 次都是对的**。最关键的几次：「派单要求把 `_MODELS_PUBLIC_BASELINE` 从 33 抬到 35 —— 照做会破坏一条有意的架构守卫、让断言两侧同源、让函数名变成谎话」、「派单要求的那条 tie-breaker 测试在 SQLite 上**结构上不可能变红**（`INTEGER PRIMARY KEY` = rowid 别名），照字面写只会得到一条恒绿的假守卫」、「派单声称控制者已经改了计划正文的 4 处，实测 0/4 在树上」。
共同点：**控制者对着「当前目录形状」推理，实现者对着「守卫实际能抓到什么」推理。你在代码现场，你的判断优先。**
顶回时：① 不要静默偏离；② 在报告的「关切」节写明「哪条决定、为什么错、你的替代方案、代价」；③ 若能同时给两个版本，先实现你认为对的那个。

## 0.5 报告

写进 `c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd\2026-10-08-实施计划03-反馈预警与CRUD-API层\task-1-report.md`。⚠️ **必须用 python 写**（`write_bytes` 一次性，或 `open(..., "a", encoding="utf-8", newline="")` 追加）。

至少 7 节：① 环境与基线复现（含 import 冒烟的版本）；② `create_app` / `get_db` / `current_student` / `current_teacher` / `require_scope` / `Page` 的最终签名（运行时口径，`inspect.signature`）；③ **架构守卫加 `api` 层的做法**（你实测到它今天怎么发现目录与层的、你照哪一套机制加的、下界断言抬到了什么值、扫描面从 35 变成几）；④ Step 4 的手工冒烟（起 uvicorn 的命令、`/api/health` 的响应原文、**跑完复核 `backend/pe.db` 仍不存在**）；⑤ 最终验收（passed 数 807 → ?、覆盖率四格、表数 18、三个指纹、`git diff 5b4a10c HEAD -- backend/data` 为空）；⑥ 待清扫清单 / 关切 / **没按派单做的地方（0 处也要写「0 处」）**；⑦ commit sha。

## 0.6 交回控制者

最终回复里给出（**简洁，不要贴大段代码**）：commit sha 与说明 / passed 数 / 覆盖率四格 / 扫描面 35 → ? 与下界断言的新值 / `create_app` 的签名 / `/api/health` 的响应原文 / `pe.db` 是否仍不存在 / 作用域闸门的三条测试名字 / 顶回控制者的地方 / 没按派单做的地方 / 待清扫条数 / 报告的字节数与行数。

---


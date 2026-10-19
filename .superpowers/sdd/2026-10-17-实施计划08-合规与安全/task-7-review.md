# Plan 08 · Task 7 = 全分支终审（对抗性 · 只读）

> 终审席：**对抗性只读审稿人**。范围 `732963f..03f54da`（34 commit / 77 文件 / +23 449 −491，⚠️ 本波亲量，逐字相符）。
> 现场：`main` = `03f54da`，工作树干净（`git status --porcelain` = 空，本波每轮复验）。
> ⚠️ 本报告是本波**唯一**新增/修改的入库文件。全程未改任何既有文件、未建分支、未 push、未动 `main` 历史。
> ⚠️ 纪律遵守：未杀/重启 PID 36876 与 57488、未跑 `npm run build`、未对 8030 或公网 URL 发任何登录/写入请求（只发过匿名 GET）、未 `-Reset`、未写 `pe_trial.db`、未对它跑迁移或清理、未跑三个禁跑 CLI、`backend/data/**` 一字节未动。

---

## ① 结论摘要

| 严重度 | 条数 | 编号 |
|---|---|---|
| **S1 · 交付阻塞** | **1** | **R7-S1-1**（`serve.ps1` 缺省会重建 `dist` ⇒ 今天**任何**一次产品档 smoke / `serve.ps1`（不带 `-SkipBuild`）都会当着甲方的面换掉活链接的前端；而 mtime 判据**此刻已被触发**） |
| **S2 · 应当修** | **3** | R7-S2-1（迁移 1/2/3 无 `downgrade` 往返守卫，§8 那句「每一个 `downgrade` 都真跑过一遍」**今天不成立**）· R7-S2-2（`bind_token` 明文令牌**没有任何一处**在库里落痕的守卫是「扫库」形状，全靠代码路径推断 ⇒ 已用实物库补证，但守卫面缺一条）· R7-S2-3（读审计的「46/18/64」散文在 `tests/api/test_read_audit_api.py` 里**六处**已过期，而它是那两条字面量常量的**紧邻注释**） |
| **S3 · 建议** | **4** | R7-S3-1（`check:dist` 源码侧字符数随 `schema.d.ts` 工作树行尾漂一整份行数 = 11 127）· R7-S3-2（`rpe-token` 的「谁领了口令」不记，已自认并登记待清扫）· R7-S3-3（`/admin` 与 `/bind` 两处新散文只有正向 needle、无反向禁用串，M6a/M6b 复现见第 3 组）· R7-S3-4（`progress.md` 六波都没续 + 「公网档 778」陈旧） |
| **S4 · 记录** | **3** | R7-S4-1（`backend/pe_demo.db` 此刻存在于工作树，gitignored、未入库）· R7-S4-2（甲方一次都没用过令牌 ⇒ `bind_token` 0 行）· R7-S4-3（`read_audit.py` 模块 docstring 一处「63 个 GET」 stale） |

### 交付能不能放行

⚠️ **可以有条件放行**：唯一那条 **S1 不是代码缺陷，而是一条运维地雷**，它**不阻塞代码交付**，但**阻塞「结案波照常规姿势跑一遍产品档 smoke」**这个动作。

⇒ **裁定建议**：**结案波（Task 8）一律用 `-SkipBuild`**（产品档 `serve.ps1 -Port 8020 -SkipBuild`、试用档 `trial.ps1 -Port 804x -SkipBuild`），并且**不要在切换窗口之外跑任何会重建 `dist` 的命令**。这一条只要写进结案波的派单就够了，**不需要改产品代码**。

⚠️ 而三条 S2 里，**R7-S2-1（迁移 1/2/3 的 `downgrade`）是本计划 §8 验收口径里逐字写着的一条**（「迁移链 4 → 6，且**每一个** `downgrade` 都真跑过一遍」）⇒ 它**必须在结案前有一个明确处置**（要么补上，要么在 spec §15 台账上把它改成一条如实的、点名到具体迁移号的局限，并同步改计划 §8 那半句）。**不许沉默地放过**。

⚠️ 其余各格（后端 1774 passed、openapi 六格 + 字节/sha、表数、迁移链单头、残差 diff、数据指纹、依赖清单、六份 manifest 零 diff、`pe.db` 不存在、`data/seed` 0 文件、八处 gitignore 项一个都没入库）**全部对得上账面**，逐格取证见 §②。

---

## ② 第 1 组 · 计划 §8 验收口径逐格重量

⚠️ 一格都没采信报告，全部本波亲量。命令与时点：2026-10-19，本机 Node v24.19.0 / Python 3.11.1 / PowerShell 5.1。

### 2.1 后端与覆盖率

| 格 | 账面基线 | **本波实测** | 判定 |
|---|---|---|---|
| `pytest -q --no-cov` | 1774 passed | ✅ **1774 passed / 0 failed**，417.00 s，退出码 0 | ✅ 相符（⚠️ 时延长于基线区间 291–348 s，因为本波同时跑了其它探针抢 CPU；时延不是账面格） |
| 带 `--cov` | 1773 + 1 skipped | ✅ **1773 passed / 1 skipped / 0 failed**，601.36 s，退出码 **0**（⚠️ 时延长于基线 455 s，同样是本波并行探针抢 CPU） | ✅ 相符 |
| 覆盖率 ① `app/domain` | 1268 / 0 / 376 / 0 / 100% | ✅ **18 个文件 / 1268 / 0 / 376 / 0 / 100.00%**（四格逐字相同） | ✅ 相符 |
| 覆盖率 ② `app` | 7661 / 209 / 1860 / 121 | ✅ **98 个文件 / 7661 / 209 / 1860 / 121**（四格逐字相同） | ✅ 相符 |
| 覆盖率 ③ `scripts` + `app.static` | 1172 / 217 / 336 / 49 | ✅ **7 个文件（6 个 `scripts/**` + `app/static.py`）/ 1172 / 217 / 336 / 49**（四格逐字相同） | ✅ 相符 |
| — 交叉核对 | ② + ③ − `app/static.py`(80) = TOTAL | ✅ 7661 + 1172 − 80 = **8753** = 本波那一次 `TOTAL` 行的 Stmts（**8753 / 423 / 2168 / 169 / 94%**，四格逐字相同） | ✅ 相符 |
| — 命令 | 三口径一次跑 | ✅ 本波亲跑 `python -m pytest -q --cov=app --cov=scripts --cov=app.static --cov-branch --cov-report=term-missing`，再按前缀聚合（`app/domain/**` / `app/**` / `scripts/**` + `app/static.py`）；⚠️ `Cover` 列**不当基线**（spec §12 有裁定），本处只报四格 | — |


### 2.2 数据库与迁移

| 格 | 账面基线 | **本波实测** | 判定 |
|---|---|---|---|
| 表数 | 30（`sqlite_master` **31**） | ✅ `Base.metadata.tables` = **30**；空库 `alembic upgrade head` 之后 `sqlite_master` 里 `type='table'` = **31**（30 张业务表 + `alembic_version`），另有 37 个 `index` | ✅ 相符 |
| 迁移链 | **6 单头** | ✅ `alembic heads` = **`a1af54889103 (head)`**（**1 个头**）；`alembic history` = **6** 条，逐字 `<base>` → `53e5a548c40e` → `0b7da3d20211` → `7f3923d8af84` → `0ac943e0da9b` → `03331a689ee4` → `a1af54889103`；新建库的 `alembic_version` = `a1af54889103` | ✅ 相符 |
| 残差 diff | **0** | ✅ 由 `tests/db/test_migration_chain.py` 的「在 head 上跑 autogenerate 比较，应当无 diff」那一拍钉住；本波 `pytest -q --no-cov` **1774 passed / 0 failed**，故它绿（⚠️ 本波**另外**亲跑了一次真库 `alembic upgrade head`，退出码 **0**） | ✅ 相符 |
| 扫描面 | **74** | ✅ 由 `tests/architecture/test_layering.py` 钉住；`pytest` 全绿 ⇒ 那一格今天仍是它自己量到的值（⚠️ 本波未独立重量该数，见 §⑩「我没查的」） | ⚠️ 间接 |
| `_MODELS_PUBLIC_BASELINE` | **33** | ✅ `tests/db/test_models.py:818/945` 两处 `assert len(...) == 33`；全绿 | ✅ 相符 |
| `_MODELS_SUBMODULES` | **8** | ✅ `tests/db/test_models.py:948` `assert len(...) == 8`；全绿 | ✅ 相符 |
| `_NON_PUBLIC_TABLE_CLASSES` | **16** | ✅ 由 `tests/db/test_models.py` 那条漂移测试钉住；全绿（⚠️ 本波未独立数那 16 个，见 §⑩） | ⚠️ 间接 |
| 黄金用例 | **14** | ✅ 亲量 `backend/tests/fixtures/golden_cases.json`（51 619 B）：顶层 3 键（`_meta` / `input` / `expected`），`input` = **14** 项、`expected` = **14** 项 | ✅ 相符 |
| `RESOURCES` | **23** | ✅ 亲量 `from app.api.routers.catalog import RESOURCES` → `len` = **23** | ✅ 相符 |
| router 模块 | **8** | ✅ 亲量 `backend/app/api/routers/*.py`（除 `__init__.py`）= **8** 个：`alerts / audit / auth / catalog / dashboard / feedback / pipeline / prescription` | ✅ 相符 |
| 前端路由 | **16**（`routes` 数组 **20**） | ✅ 亲量 `frontend/src/router/index.ts`（27 868 B，**唯一**一个 router 文件）的 `routes` 数组：`path:` 字面量 **20** 处 | ✅ 数组 20 相符（⚠️ 「16」的口径是 smoke 第 14 步真跑的那 16 条，本波按三档 smoke 实测复核，见 2.4） |

### 2.3 openapi（⚠️ 全部亲量：`python backend/scripts/dump_openapi.py --out %TEMP%\p08t7b\openapi_probe.json`）

| 格 | 账面基线 | **本波实测** | 判定 |
|---|---|---|---|
| 字节 | **455 301 B** | ✅ **455 301 B** | ✅ |
| sha256[:16] | **`7D75650765F2B65D`** | ✅ **`7D75650765F2B65D`** | ✅ |
| 路径 | **77** | ✅ **77**（其中 `/api/` 前缀 **77**，非 `/api/` **0**） | ✅ |
| 操作 | **106** | ✅ **106** | ✅ |
| 挂 security | **87** | ✅ **87** | ✅ |
| GET | **65**（15 匿名 + 50） | ✅ **65** = **15** 匿名 + **50** 挂 security（判据逐字取 `tests/test_main.py` 的 `OPENAPI_CELLS` 那一套：`not op.get("security")`） | ✅ |
| securitySchemes | **3** | ✅ **3** = `X-Teacher-Staff-No` / `pe_session` / `X-Student-Id` | ✅ |
| catch-all | **0** | ✅ **0**（无 `{...path}` 形状的路径；path item 里也**没有**任何非 HTTP 方法的键） | ✅ |
| 未定型响应 | **24** | ✅ **24**（判据：200 响应 schema 里不含 `$ref/items/properties/allOf/anyOf/oneOf`；`/api/health` 在清单里） | ✅ |
| `expected` | **29** | ✅ **29**（亲量：从 `tests/api/test_prescription_api.py` 的 `expected = {` … `crud = [` 那段正则抽出 **29** 个 `("/api/…", "get|post|…")` 键，对应 **28** 个唯一路径） | ✅ |
| `crud` | **75** | ✅ **75**（亲量：`/api/` 路径里不在 `expected` 路径集上的全部操作 = **75**；⚠️ 守卫只钉下界 `>= 70`，75 是现量的） | ✅ |
| `security == [pe_session]` 的操作 | **2** | ✅ **2** = `POST /api/auth/logout` + `GET /api/auth/me` | ✅ |

### 2.4 前端静态守卫与 smoke

| 格 | 账面基线 | **本波实测** | 判定 |
|---|---|---|---|
| `check:tokens` | **36** / 下界 25 | ✅ 亲跑：扫描面 **36** 个文件（下界 25）、9 个负控 0 命中、8 个正控全命中、`tokens.css` 里 22 处色值字面量、退出码 **0** | ✅ 相符 |
| `check:dist` 产物侧 | **23 个 / 596.2 kB** | ✅ 亲跑 `node scripts/check-dist.mjs --no-build`：扫了 **23** 个文件（**596.2 kB** = 610 477 bytes），跳过 4 个非文本；4 个自托管 woff2 = 97 348 bytes；退出码 **0** | ✅ 相符 |
| `check:dist` 源码侧 | **56 个 / 1 428 951 字符** | ⚠️ 亲量 **56 个 / 1 440 078 字符** = 基线 **+11 127** | ⚠️ **对不上，但是判据漂、不是产品缺陷** ⇒ 见 **R7-S3-1** |
| smoke 三档 | dev **818** / 产品 **818** / 试用 **850** | *（见 2.5，需要起自己的实例）* | — |
| 新增依赖 | 后端 **0** / 前端 **0** | ✅ `git diff 732963f HEAD -- backend/pyproject.toml frontend/package.json frontend/package-lock.json .gitattributes .gitignore backend/alembic.ini` = **空**（0 文件）；⚠️ 亲读两份 manifest：后端 7 项运行时依赖（`fastapi`/`uvicorn[standard]`/`sqlalchemy>=2.0`/`pandas`/`numpy`/`pyyaml`/`alembic==1.20.0`）+ 3 项 dev；前端 3 项 dependencies（`pinia`/`vue`/`vue-router`）+ 7 项 devDependencies，**Plan 08 一个都没加** | ✅ 相符 |

### 2.5 数据、禁区与入库面

| 格 | 账面基线 | **本波实测** | 判定 |
|---|---|---|---|
| 四个数据指纹 | `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` / `E48E3AC82BB45BB7` | ✅ 亲量（行尾归一化为 LF 之后的 sha256[:16]）：`national_standard_2014.csv` = `D2C8E539E2FA0029` · `exercises.yaml` = `5394B37F01DAC9AC` · `exercise_equivalence.yaml` = `822CB86A5E998301` · `alert_rules.yaml` = `E48E3AC82BB45BB7`。**四个全中、一个不缺** | ✅ 相符 |
| 18 个模板指纹 | 18 | ✅ 亲量 `backend/data/prescription/*.yaml` = **18** 个文件，逐个算了 sha256[:16]，与 `tests/domain/test_prescription_templates.py` 的 `TEMPLATE_FINGERPRINTS`（`assert len(...) == 18`）同源同数；全绿 | ✅ 相符 |
| `backend/data` 入库文件 | **24** | ✅ `git ls-files backend/data` = **24** 个（6 个根文件 + 18 个 prescription 模板）；工作树同样 24 个 / 合计 **198 722 B** | ✅ 相符 |
| `git diff 732963f HEAD -- backend/data` | 空 | ✅ **空**（`--stat` 一行都没输出） | ✅ 相符 |
| `backend/pe.db` | **不存在** | ✅ 不存在（`pe.db` / `pe.db-wal` / `pe.db-shm` 三个都不在） | ✅ 相符 |
| `backend/data/seed/` | **0 文件** | ✅ 目录在、`entries = 0` | ✅ 相符 |
| 八处 gitignore 项 | 一个都不入库 | ✅ `git ls-files` 里搜 `pe.db*` / `pe_demo.db*` / `pe_trial.db*` / `backend/backups/` / `backend/data/seed/` / `frontend/dist/` / `tools/` / `.trial/` / `dist-pack/` / `.coverage` / `.env` / `node_modules` ⇒ **0 命中** | ✅ 相符 |
| 控制者那两份备份 | 别删也别入库 | ✅ 仍在：`backend/backups/pe_trial-pre-migration5-20261017-201257.db` **1 589 248 B** · `pe_trial-pre-migration6-20261018-194744.db` **1 597 440 B**；⚠️ 本波一个字节都没动 | ✅ 相符 |
| `frontend/dist` | **27 文件 / 708 583 B** | ✅ 亲量 **27** 个文件 / 合计 **708 583 B**；`index.html` **2 567 B / sha256[:16] `7EF16470CD6CE9BB`**；`assets/index-DG9aiaVT.js` **252 261 B** + `assets/index-D_BSV8Ho.css` **66 664 B** ⇒ **逐字相符，本波 0 次 build** | ✅ 相符 |

### 2.6 文档账面

| 文件 | 账面 | **本波实测** | 判定 |
|---|---|---|---|
| spec `Document/2026-09-28-体育闭环原型-设计spec.md` | 1 050 415 B / 10 115 行 / 全 CRLF / 0 裸 LF / 无 BOM / `EBC2499CEB2FB1BB` | ✅ **1 050 415 B / 10 115 LF / 10 115 CRLF / 0 裸 LF / 无 BOM / sha256[:16] `EBC2499CEB2FB1BB`**（⚠️ 五格全中） | ✅ 相符 |
| README | 15 478 B / 208 行 | ✅ **15 478 B / 208 行 / 全 CRLF / 无 BOM** | ✅ 相符 |
| 甲方试用说明书 | 37 123 B / 179 行（上限 200） | ✅ **37 123 B / 179 行 / 全 CRLF / 无 BOM** ⇒ 距上限还有 **21** 行 | ✅ 相符 |
| 计划文档 | 26 016 B / 226 行 | ✅ **26 016 B / 226 行 / 全 CRLF / 无 BOM** | ✅ 相符 |
| `backend/pe_trial.db` | 1 630 208 B / mtime 2026-10-19 12:30:48 | ✅ **1 630 208 B / mtime 2026-10-19 12:30:48.211841 / sha256[:16] `382B507454143274`**（⚠️ 本波全程只读，收尾复量，见 §⑨） | ✅ 相符 |

### 2.7 ⚠️ 第 1 组里**唯一对不上**的一格：`check:dist` 源码侧字符数（R7-S3-1）

**账面 1 428 951 字符，本波实测 1 440 078 字符，差 +11 127。**

**根因已定位到实物**（不是产品缺陷）：

```
frontend/src/api/generated/schema.d.ts
  工作树：574 499 B / 11 127 个换行 / **11 127 个 CRLF / 0 个裸 LF** / 无 BOM
  UTF-8 解码后字符数        = 444 354
  行尾归一化为 LF 之后字符数 = 433 227      ← 差 **11 127**，与 check:dist 那一格的差**逐字相同**
  index blob = 41437e228b4318434cc05f67b3dcea4922f60496（= Task 6 报的 `hash-object`，✅ 相符）
  git hash-object（含 autocrlf 归一化）= 同一个 blob ⇒ `git status --porcelain` = **空**
  core.autocrlf = true
```

⇒ 判据是「扫到 ≥ 20 个文件 / ≥ 100 kB」这个**下界**，故它**仍然绿**（56 个 / 1 440 078 字符）。漂的只是**报告里那个数**。

⚠️ **这正是派单预警的那一格**（「`check:dist` 的源码侧字符数会随 `schema.d.ts` 的工作树行尾漂一整份行数」）。**裁定建议**：结案波**不要把 1 428 951 抄进 spec 当账面**；要抄就抄「**56 个文件 / 字符数是一个下界、随 `core.autocrlf` 漂**」，或者干脆照 `package.json` 那个 `//` 键已经用过的姿势——**删数而不是改数**（硬规矩 #111：凡是能从别处读出来的数，一律视为过期）。

⚠️ **连带的一条**（本波顺手量到，见 §③/第 3 组）：`schema.d.ts` 与另外三个 `.vue` 的**工作树 mtime 都是 2026-10-19 11:47:20**（±5 ms，一次批量写回），而它们的**内容**最后一次改动是 01:49:52 的 `35d7bb0` / `98effb1`，`dist` 的构建戳是 **02:27:05** ⇒ **内容上 `dist` 与 `src` 是同步的**，而 **mtime 上不同步**。这就是 R7-S1-1 的引信。


---

## ③ 第 2 组 · 计划 §6 点名的本计划重心面（五格）

### 3.1 读审计的覆盖面

#### 3.1.1 那 18 条「不记」逐个复核（⚠️ 派单点名：有没有一条其实读到了某个具体学生的健康数据）

**归类表的实物**：`backend/app/api/read_audit.py` 的 `READ_CLASSES`（**11** 类，前 **7** 类 `sensitive=True`、后 **4** 类 `False`）+ `READ_ROUTES`（**65** 行「路由模板 → 归类」）。亲量：`65 − 47 = 18`，与模块 docstring 的「47 记 / 18 不记」逐字相符。

| # | 「不记」的类 | 覆盖的路由（本波逐行数） | 它给的理由 | **本波判定** |
|---|---|---|---|---|
| 1–14 | `REFERENCE_DATA`（14 条） | `/api/semesters`(+`{id}`) · `/api/course-sections`(+`{id}`) · `/api/fitness-test-batches`(+`{id}`) · `/api/percentile-snapshots`(+`{id}`) · `/api/exercises`(+`{id}`) · `/api/prescription-templates`(+`{id}`) · `/api/class-sessions`(+`{id}`) | 「群体/参考数据，**一行学生键都没有**」+「**全部匿名可读**，故就算记也答不出『谁』」 | ✅ **站得住**。两半都亲验：① 亲读 `app/db/models/derived.py` 的 `PercentileSnapshot`（最容易被误判的一张），列是 `id / semester_id / computed_on / batch_id / item / sex / age_group / p10…p75 / sample_size / source`，**一个学生键都没有**（分组键是 `(sex, age_group, item)`）；② 亲量 openapi 的 **15** 个匿名 GET = 这 **14** 条 + `/api/health`，**逐条对上**（⇒ 「匿名可读」不是散文，是契约面事实） |
| 15 | `OPS_PROBE` | `/api/health` | 只回三格计数、不含任何人的数据；被 `tunnel.ps1` 每 60 s 打一次 | ✅ **站得住**。亲量它的响应 schema 是 `additionalProperties: true` 那一档（`HEALTH_UNTYPED_SCHEMA`），四格是 `status/tables/students/trial`，**全是计数与布尔** |
| 16 | `SELF_SESSION` | `/api/auth/me` | 只回**请求者自己**那五格，结构上不可能披露别人的数据；而它是全仓调用频率最高的 GET | ✅ **站得住**。亲量它的响应是 `kind/login/name/role/subject_id`，`subject_id` 恒取自会话 ⇒ **无第二个人的数据**。⚠️ 而它**不是**「学生读自己档案不记」那一档（那一档的裁定是**记**，见 3.1.3） |
| 17–18 | `CLASS_TOKEN_OPS`（2 条） | `/api/class-sessions/{class_session_id}/rpe-status` · `/api/class-sessions/{class_session_id}/rpe-token` | 键是 `{class_session_id}`、**不含任何学生键**；⚠️ 自认 `rpe_token` 是一格**秘密**、「谁读过它」看着像该记，但它是**一次写的前置**而不是一次读的产物，随后那一次 `POST /api/rpe-records` 在 `audit_log` 里有一行 | ⚠️ **理由成立、但取舍是真的**（见 **R7-S3-2**）。亲验链闭合：甲方那份活库的 `audit_log` 36 行里 **`POST /api/rpe-records` 有 2 行、`POST /api/class-sessions/1/open-rpe` 有 2 行** ⇒ 「口令 → 交快评」那条链在写审计那侧**确实完整**。**但它答不出「谁在 open-rpe 之后、任何学生提交之前把口令读走了」**——那一格今天库里查不到 |

⇒ **判定：18 条里 0 条「其实读到了某个具体学生的健康数据」**。⚠️ 唯一一处**真的是秘密**而非健康数据的是 `rpe-token`，而它已被实现者自己如实登记为待清扫（不是瞒着的）。

#### 3.1.2 ⚠️ Task 4 / Task 5 之后新增的端点归类了吗（派单点名）

**归类了。** openapi 从 75 路径 / 103 操作变成 **77 / 106**（本波亲量，见 §2.3），多出来的是：

| 新端点 | 方法 | 归类 | 取证 |
|---|---|---|---|
| `/api/auth/bind-tokens` | **GET** | ✅ **`CREDENTIAL_STATE`**（Task 4 为此**新开的第 11 类**） | `READ_ROUTES` 第 378 行逐字 `"/api/auth/bind-tokens": "CREDENTIAL_STATE"`；⚠️ 而它**已经在甲方那份活库里真跑过**：`read_audit_log` 的 21 个 distinct `route` 里有一条 `/api/auth/bind-tokens`，**1 行**（管理员 09:39–09:51 那一次走查），⚠️ 而同一时刻 `bind_token` 表是 **0 行** ⇒ 它记的是「**谁翻过令牌台账**」这个动作本身，与台账空不空无关。**这一格是活的实物证据，不是纸面归类** |
| `/api/auth/bind-tokens` | POST | 不适用（**写**） | 走 `audit_log` 的方法判据（三个写方法之一） |
| `/api/auth/bind-with-token` | POST | 不适用（**写**） | 同上；⚠️ 它**刻意匿名**（拿令牌的人此刻还没有身份），故它不挂 scheme，`securitySchemes` 仍是 3 |

⚠️ **Task 5 一个端点都没加**（它只改值不改 schema），故 openapi 五格在它那一波逐字未变——本波亲量确认今天的五格 = **77 / 106 / 87 / 65（15+50）/ 3**，与 Task 6 报的逐字相同。

#### 3.1.3 「不许悄悄落后于路由」那条守卫真的盖住了吗

**盖住了，而且两侧不同源。** 亲读 `backend/tests/api/test_read_audit_api.py:292-324`：

* **期望侧** = `client.get("/openapi.json")` 里**活的** GET 路径集合（`live`）；
* **被测侧** = `READ_ROUTES` 那**一张字面量表**（`classified`）；
* **两个方向都响**：`classified - live != {}` → 红（「已经不是路由了」）；`live - classified != {}` → 红（「**没有被归类**」）；
* **反空转**：`assert len(live) >= 64`（本波实测 `live` = **65**）；
* **判据单一所有者**另有一条 AST 守卫（`:327-383`）：`is_sensitive_read` 的函数体里只许出现 `READ_CLASSES` / `READ_ROUTES` 两个名字，出现第三个判据来源就红；且全仓 `READ_ROUTES` **只被赋值 1 次**。
* ⚠️ **失效方向是「不记」+ 守卫会红**（`is_sensitive_read` 对没归类的路由返回 `False`）⇒ 静默的那一半被守卫接住了，形状是对的。

⚠️ **本波另外做了「塞一个假路由」的实测**（派单点名），见 §⑤ 第 4 组的变异 **M7-1**。

#### 3.1.4 ⚠️ 甲方活库上的实物取证（只读打开，`mode=ro` URI）

`backend/pe_trial.db`（`version_num` = `a1af54889103` = 链尾）：

```
read_audit_log 146 行 · 9 列 = id/at/subject_kind/subject_id/staff_no/route/student_id/status/target
  by route（21 个 distinct，全部落在「47 记」那一侧）：
     30 /api/students                27 /api/teachers              24 /api/enrollments
     12 /api/alerts                  11 /api/dashboard/class/{course_section_id}
      6 /api/students/{student_id}/home
      5 /api/students/{student_id}/training-logs/completion-rate
      4 /api/students/{student_id}/weekly-sheet
      3 /api/dashboard/weekly-class-report/{course_section_id}
      3 /api/training-logs           3 /api/weekly-class-reports
      2 /api/mini-tests               2 /api/mini-tests/normalized
      2 /api/stratification-results   2 /api/stratification-results/{stratification_result_id}
      2 /api/students/{student_id}    2 /api/teacher/students/{student_id}/home
      2 /api/teacher/students/{student_id}/normalized
      2 /api/teacher/students/{student_id}/weekly-sheet
      1 /api/auth/bind-tokens         1 /api/rpe-records
  by subject_kind：teacher 126 · student 20 · **anonymous 0**   ← 「匿名一律不记」在实物上成立
  by status     ：200 → 145 · **403 → 1**                        ← 被拒的读**也留痕**（学生 id 4 打 /api/students）
  staff_no      ：T0001 81 · T0003 45 · NULL 20（学生那 20 行）
  student_id    ：有值 123 · NULL 23（名册/班级聚合那一档，与 READ_CLASSES 的自认逐字相符）
  target        ：max(length) = **2**（就是一个 id）⇒ **一个请求体字节都没落**
  ⚠️ 落在「18 条不记」那 18 个模板上的行数 = **0**（用 IN (…) 逐条查过）
audit_log 36 行 · 9 列（含 method/path，不含 route）：全 POST
  /api/auth/login 21 · /api/auth/logout 7 · /api/training-logs 4 · /api/rpe-records 2 · /api/class-sessions/1/open-rpe 2
login_attempt 4 行 · 6 列 = id/kind/login/ok/at/ip
```

⚠️ **只读打开没有改文件**：探针前后 `pe_trial.db` 逐字节相同（**1 630 208 B / sha256[:16] `382B507454143274` / mtime 2026-10-19 12:30:48.211841**，前后两次量到同一个值）。

⚠️ **顺手量到一格有价值的实物**（不是缺陷，是 §1.2 第 16 条的活证据）：`login_attempt.ip` 的 **4 行全是 `38.45.155.89`**（= cloudflared quick tunnel 的出口）。代码侧本来就诚实（`app/auth/policy.py:474-488` 逐字写着「三个调用方一律交 `request.client.host`…本仓**没有任何一处**解析 `X-Forwarded-For`」，`app/db/models/auth.py:302-307` 写着「它只是事后线索、不参与限流判定」），spec §13.4.6 那张表与 §1.2 第 16 条也逐字交代了「挂上反代之后它记的是反代自己」⇒ **今天这一格是如实登记的已知局限，本波给它在甲方现场补了一份实物取证**。⚠️ 但**甲方试用说明书里没有这一句**（说明书全文搜 `IP` 只命中「本机 IPv4」那一处）⇒ 见 **R7-S4-4**。

### 3.2 清理与备份的破坏性操作有没有静默路径

#### 3.2.1 `--dry-run` 真的不删吗（⚠️ 本波自己真跑了）

**真不删，而且比「行数不变」更强：一个字节都没写。**

本波在 `%TEMP%\p08t7b\retention_probe.db` 上灌了一份真库（`alembic upgrade head` 建 31 张表，再按四张表的判据各灌「该删的」与「不该删的」），然后跑真 CLI：

```
灌完：user_session 5 · login_attempt 4 · audit_log 3 · read_audit_log 4   （合计 16）
      库 sha256[:16] = 8367D202C0C27FD1 / 307 200 B
python scripts/retention.py --db-url <TEMP 库> --dry-run   → 退出码 0
      预告：user_session 2（窗口 7 天）· login_attempt 3（30 天）· audit_log 2（365 天）· read_audit_log 3（90 天）= 合计 10
      ⚠️ 这 4 个数与本波**独立算出来的期望值逐字相同**（期望侧不是从它读回来的）
      跑完：5 / 4 / 3 / 4（一行没少），库 sha256[:16] 仍是 8367D202C0C27FD1
      它自己印的那一句：「DRY-RUN：**一行都没删**（复核：四张表的总行数与进来时逐字相同，16 → 16）」
```

⚠️ 结构上也对得上：`clean()` 里 `dry_run` 那一档走的是 `eng.connect()`（**不开写事务**），而 `DELETE` 的构造点在 `if dry_run: return …` **之后** ⇒ 「打印完再删」这个形状在代码里不存在。

#### 3.2.2 「预告 → 删 → 复核」的对账真的成立吗

**成立，而且对不上就整批回滚。** 同一份库上去掉 `--dry-run` 再跑：

```
python scripts/retention.py --db-url <TEMP 库>   → 退出码 0
   合计：将删 10 行 → 开始删…
   实删（逐表）：user_session 预告 2 / 实删 2 / 删完仍满足判据 0
                login_attempt 预告 3 / 实删 3 / 删完仍满足判据 0
                audit_log     预告 2 / 实删 2 / 删完仍满足判据 0
                read_audit_log 预告 3 / 实删 3 / 删完仍满足判据 0
   合计：预告 10 == 实删 10 ✓（不符就整批回滚、一行都不删）
   复核：四张表上「仍满足判据的行」合计 0（恒为 0）
跑完：user_session 3 · login_attempt 1 · audit_log 1 · read_audit_log 1  ← 与本波独立算的期望**逐格相同**
```

⚠️ ** survivors 逐个查过身份**（不是只数行数）：
* `user_session` 活下来的三行 `expires_at` = `+1 天` / `+3 天` / **`−1 天`** ⇒ 第三行**按日历已经过期**，而它落在 7 天窗口**之内**故不删。**这正是 `TableSpec` docstring 那条裁定的实物**：判据锚在 `expires_at < now − N 天`，故「删掉一个**未过期**的会话、把人踢下线」这一档对任何窗口都不可达；
* `audit_log` 活下来的是 `−100 天` 那一行（365 天窗口之内）⇒ **「写审计不少于 1 年」这一格在实物上成立**；
* `read_audit_log` 活下来的是 `−45 天` 那一行（90 天窗口之内），而 `−100 天` 那一行被删 ⇒ **读审计窗口确实短于写审计**（两条不同的判据在同一次跑里各自生效）。

⚠️ 而它**在删之前**还印了一段响亮的「本 CLI **不会**自动备份」+ 三条理由 + 该先跑哪一条命令（`backup.ps1`）⇒ **失效方向是响亮的**，没有静默路径。

#### 3.2.3 ⚠️ `BEGIN IMMEDIATE` 那一格（Task 2 说没有它 `clear_failures` 能在 COUNT 与 DELETE 之间插一脚造成假红）——**真的成立吗**

**成立。本波做了行为实测（不是读代码推断）**：拿 `retention._engine(url, immediate=…)` 各造一个引擎、开一个事务并跑一句 `SELECT`（这就把事务开起来了），然后**从第三条连接**（`sqlite3.connect(…, timeout=0.4)`）尝试一次 `INSERT`：

| 档 | 并发写那一次的结果 | 判定 |
|---|---|---|
| `immediate=True`（**真删**那一档） | **WRITE BLOCKED**（0.504 s）→ `sqlite3.OperationalError: database is locked` | ✅ 写锁**在预告之前**就拿到了，「预告 → 删 → 复核」是一个不可分割的临界区 ⇒ 对账**恒**相符，那一格报错只可能是真问题 |
| `immediate=False`（**`--dry-run`** 那一档） | **WRITE SUCCEEDED**（0.015 s） | ✅ 只读探查**不挡**正在给甲方服务的那个进程的写——与 `_engine` docstring 那句「`--dry-run` 那一档不装这两个钩子」逐字相符 |

⇒ **Task 2 那一句不是散文**：没有 `BEGIN IMMEDIATE`，第三条连接的写在 0.015 s 内就成功了；有了它，同一条写在 0.5 s 后被 SQLite 自己挡住。而 `app.auth.policy.clear_failures`（一次成功登录当场删掉那个标识的 `login_attempt` 行）正是这样一条写。

⚠️ **代价也如实**：写锁被握住的时间是那 4 次 `COUNT` + 4 次 `DELETE` 的墙钟；`--dry-run` 不取锁，故「服务跑着的时候先看一眼」是安全的。

#### 3.2.4 `backup.ps1 -Keep` 的删除清单真的逐个打印吗

**真的逐个打印，而且删完还复核一遍。** 本波用 `%TEMP%\p08t7b\bk\` 当备份目录（⚠️ **刻意不碰 `backend/backups/`**，控制者那两份一个字节都没动），先做 5 份，再 `backup.ps1 -DbUrl <TEMP 库> -Dir <TEMP 目录> -Keep 2`：

```
   保留策略  --keep 2（判据 = **文件名里的 UTC 时间戳**，新→旧；所有者 backup.BACKUP_NAME_RE）
   现存      5 份认得出时间戳的备份 + 0 个认不出的东西（**一律不碰**）
   ⚠️⚠️ 下面这一步**不可逆**：将删 3 份（连它们各自的 .sha256 侧车一起）：
      · pe-20261019T085847Z.db    307308 B  sha256 7f99a96af4fbeea9…  侧车 ✓
      · pe-20261019T085844Z.db    307308 B  sha256 00d6e8dc34231b89…  侧车 ✓
      · pe-20261019T085813Z.db    307200 B  sha256 9d818df66ae1796c…  侧车 ✓
   合计：将删 3 份 / 921816 B → 开始删…
   实删 3 份 + 3 个侧车（921816 B）。复核：目录里认得出时间戳的备份剩 2 份
      （== min(--keep 2, 现存 5) ✓）、那 3 个文件名与它们的侧车都已不在、认不出的那 0 个东西一个都没动。
```

* ✅ **逐个**打印（文件名 / 字节数 / sha256 前 16 位 / 侧车在不在）；
* ✅ **侧车跟着一起删**（亲验：`-Keep 2` 之后目录里只剩 2 个 `.db` + 2 个 `.sha256`）；
* ✅ **认不出时间戳的东西一律不碰**（那一档是「不误删别人的文件」的防线，它自己印出来）；
* ✅ **`-Keep 0` 被拒**：退出码 **2**，报错逐字「`--keep` 要 ≥ 1（收到 0）：它的字面意思是『一份都不留』…**故本 CLI 在做任何一次写之前就拒绝：这一次备份也没有做**」——本波亲验目录里的文件数**一个都没变**（4 → 4）；
* ✅ **缺省不删**：不给 `-Keep` 的那一次只产出 1 份 + 1 个侧车，目录里原有的 4 份**一份都没动**（与 Task 3 之前的行为逐字相同）。

#### 3.2.5 ⚠️ 缺 `PE_BACKUP_KEY` 时那段 ⚠️ 告示真的在吗

**在，而且它自己声明了「不因任何别的环境变量而闭嘴」。** 本波把 `PE_BACKUP_KEY` 删掉再跑一次，stdout 逐字含：

```
   形状   **明文档**（产物头是 SQLite 自己的格式串，任何 SQLite 客户端直接打开）
   ⚠️⚠️⚠️ 这一份是**明文**的：它是一个可以直接用任何 SQLite 客户端打开的
      整库副本，里面是全校学生的**出生日期、体成分、体测结果、运动处方与预警**。
      …… ⇒ 要加密请设一个环境变量、再跑一次同一条命令 ……
      ⚠️ 口令**丢了就打不开**（本仓刻意不做密钥托管），请把它记在与备份**分开**的地方。
      ⚠️ 本段告示**不因任何别的环境变量而闭嘴**：$PE_BACKUP_KEY 不在，这一份就是明文的，
        而那一格必须响（而不是静默产出一份看起来一样的备份）。
```

⚠️ **退出码是 0 而不是 raise**——与计划 §3 第 3 条的裁定逐字相同（「不加密并打印一段响亮的 ⚠️…而不是 raise」）。

⚠️ **加密那一档也亲验到产物头**（不是只读代码）：同一个库、设上 `PE_BACKUP_KEY` 之后连做 3 份，产物头前 16 字节逐字是 **`PEBACKUP` + 版本 + KDF 参数**，字节数 **307 308**（明文档 **307 200**，差 108 B = 头 + 尾部 32 B HMAC）；不设那一份的头是 **`SQLite format 3\0`**。⇒ 「按**产物头**认、不按扩展名」这句话在实物上成立（两档文件名与侧车形状逐字相同）。

#### 3.2.6 ⚠️ `restore` 吃错密钥时是响亮还是静默（派单 §3 第 3 条点名的那一档）

**响亮，而且目标库一个字节都没被碰。** 本波用一把**错的**口令去恢复一份**真的加密档**：

```
$env:PE_BACKUP_KEY = "a-different-wrong-key-123"
python scripts/restore.py pe-20261019T090021Z-pre-restore.db --dir <TEMP> --db-url <TEMP 目标库>
→ 退出码 2
   形状   **加密档**（产物头 PEBACKUP）⇒ 先验尾部那 32 字节的 HMAC-SHA256、验过了才解密
          口令来自 $PE_BACKUP_KEY（⚠️ 本脚本刻意不印它的任何一部分）
   恢复失败（拒绝执行）：拒绝解密 …：HMAC-SHA256 **验不过**。
     ⚠️ 只有两种可能，而它们在密码学上不可分辨：① 口令不是加密这一份时用的那一个；
        ② 这一份产物被改过（哪怕只改了 1 个字节，或只改了一个字节的位置）。
     ⚠️ 本脚本**一步都没有解密**（先验 MAC、验不过就不往下走），故目标库**没有被改动**、
        也没有产出一个坏库。
     ⚠️ 处置：确认那一个口令（它没有第二个后门：--no-verify 跳的是侧车那一格，
        **HMAC 这一格跳不掉**），或换一份备份
```

* ✅ **目标库 sha256 前后逐字相同**（`DBDA0B375F807426…` → 同一串）⇒ **没有静默产出坏数据的路**；
* ✅ **`--no-verify` 跳不掉 MAC**（它只跳侧车那一格）⇒ 没有绕过口；
* ✅ **口令的任何一部分都不印**（长度/sha/base64 都不印）。

⚠️ 顺带量到恢复那一侧的另外三格（都是好方向）：① 它**先校验侧车**（`sha256 … / 307200 字节 ✓`）；② 覆盖前**自动留一份 `-pre-restore` 后路**，而本波实测那一份后路**是加密档**（`PEBACKUP` 头，因为当时 `PE_BACKUP_KEY` 在）；③ 覆盖后**自检**（`sqlite_master` 表数 31 / `alembic_version` = `a1af54889103` / `student` 行数），并**如实说明**「表数比 `/api/health` 报的多 1」的原因。⚠️ 而当 `PE_BACKUP_KEY` 在、被恢复的却是明文档时，它会**主动说一句**「它是在设那个变量之前做的」⇒ 不误导运维。

### 3.3 令牌那一格的失效方向（⚠️ 全部行为实测，不读代码推断）

本波把 `backend/pe_demo.db` **复制**到 `%TEMP%\p08t7b\token_probe2.db`（⚠️ 仓库里那一份一个字节没动），把其中一个学生的 `password_hash` 置回 `NULL` 造出一个「未绑定账号」，然后用 `TestClient` 真跑整条链。

| # | 查什么 | **实测取证** | 判定 |
|---|---|---|---|
| 1 | 签发 | `POST /api/auth/bind-tokens`（管理员 `T0003`）→ **201**，响应体七格 `{id, kind, login, token, issued_at, expires_at, issued_by}`；明文 = **`L5u4xSBNxGDojCtw.mERhtd-GJegOvaHm5C0rxlB6FsFFI6M7`** = 选择子 **16** 字符 + `.` + 秘密 **32** 字符（= `TOKEN_ID_BYTES 12` / `SECRET_BYTES 24` / `SEPARATOR "."` 的 base64url 形状）；`issued_at 2026-10-19T17:19:46` → `expires_at 2026-10-26T17:19:46` ⇒ **TTL 恰好 7 天**（= `BIND_TOKEN_TTL`） | ✅ |
| 2 | **哈希入库而明文不入库**（⚠️ 派单要求「自己去库里扫」） | 本波**扫了全库 31 张表的每一列**（`select * from <每一张表>`，逐行拼串后做子串匹配）：**明文令牌命中 0 张表**、**秘密那一段命中 0 张表**；**只有选择子 `token_id` 落在 `bind_token` 一张表里**（那是查找键，落库是对的）。库里那一格逐字是 `pbkdf2_sha256$600000$BNHl1c7ZD55dyOd3l8l…`（**90** 字符，自描述串 = 算法 + 迭代数 + 盐 + 摘要） | ✅ |
| 3 | **选择子单独不是凭证** | 五档逐个真发：只交选择子 `L5u4xSBNxGDojCtw` → **403**；选择子 + `AAAA…`（32 个 A）→ **403**；选择子 + **秘密去掉最后一个字符** → **403**；`garbage` → **403**；空串 → **403**。⚠️ 五档的响应体**逐字相同**（`{"error":{"code":"forbidden","message":"绑定令牌不正确，无法绑定口令","detail":null}}`）⇒ **没有 oracle**：从响应上分辨不出「选择子不存在」与「秘密错」 | ✅ |
| 4 | **单次使用** | 第 1 次真兑换 → **204**（`student.password_hash` 从 `NULL` 变成非空、`bind_token.used_at` 落上时刻）；第 2 次拿**同一串** → **409 `bind_token_spent`**，报文逐字「这个绑定令牌已经用过了：一张令牌只能兑换一次。⚠️ 若你刚刚才绑定成功，请直接登录；真的忘了口令，要找教务干事把那一行的 `password_hash` 置回 NULL 再重签一张」 | ✅ 响亮 |
| 5 | **过期** | 再签一张、把 `expires_at` 改到 `2020-01-01` → **403 `bind_token_expired`**，报文把**到期时刻与签发时刻都印出来**，并如实写「过期令牌不能续期，而本波**没有**撤销端点」 | ✅ 响亮 + 如实 |
| 6 | 台账读不回明文 | `GET /api/auth/bind-tokens`（管理员）→ **200**，响应体**既不含明文、也不含秘密那一段**；`items` 每行七格（9 列减去 `token_id` 与 `token_hash`） | ✅ |
| 7 | **接上 `3/15/60` 那条限流 + 时延签名**（⚠️ 派单点名「锁定档一次 PBKDF2 都不跑」） | 用**真选择子 + 错秘密**连发 6 次，逐次量墙钟：<br>第 1 次 **187.8 ms** · 第 2 次 **183.5 ms** · 第 3 次 **216.9 ms** · 第 4 次 **20.5 ms** · 第 5 次 **26.3 ms** · 第 6 次 **26.0 ms**<br>⇒ **前三次约 190 ms（跑了一次 600 000 迭代的 PBKDF2）、从第 4 次起掉到约 20–26 ms（≈ 1/8，一次 PBKDF2 都不跑）**。`login_attempt` 上**恰好 3 行** `kind='student' / login='bind:2022080001' / ok=0`（= `DEFAULT_BIND_MAX_FAILS`），第 4 次起**不再加行**。⚠️ 六次的响应体**逐字相同**（与登录那一条同一条裁定：锁定档不给枚举信号） | ✅ **限流真接上了，时延签名清楚** |
| 8 | ⚠️ **`PE_ALLOW_SELF_BIND` 缺省仍开**（派单说这是「本计划最重要的一句实话」） | 三档逐个真跑：① **变量未设** → `POST /api/auth/students/bind`（学号 + 出生日期）**走到业务判定**（回 409 `password_already_bound`，因为那个账号已绑定）⇒ **开关是开的**；② **`=0`** → 学生与教师两个自助绑定端点**都 403**，报文逐字点名「由环境变量 `PE_ALLOW_SELF_BIND=0` 决定（缺省是 `1` = 开；把它设回 `1` 即恢复今天的行为）」并指路令牌端点；③ **`=yes`（认不出的值）** → `create_app` **当场抛 `ValueError`**，报文点名那个变量与那两格取值 ⇒ **服务起不来**，不静默落到某一档 | ✅ **缺省仍开 = 抢绑今天没有默认收掉** |
| 9 | 那句实话有没有被藏起来 | ⚠️ **没有**。`app/api/crud.py:756-758` 逐字写着「**这一格是纵深防御，不是『抢绑已收掉』**（如实记）：要真的关掉那一档还得**显式**设 `PE_ALLOW_SELF_BIND=0`，而管理员那一档今天**照旧**读到完整值」；甲方试用说明书 §6 须知 ② 也逐字写着「⚠️⚠️ **而今天默认仍然是老的形状**（这一句请务必念给你们的运维）…正确的切换顺序是『先签发令牌、确认流程通了、再关开关』」 | ✅ 两处都如实 |
| 10 | 防呆：给一个**已绑定**的账号签发 | → **409**，报文逐字「一张发给它的令牌**永远兑换不了**（绑定只对 `password_hash IS NULL` 的行放行），故本端点拒发。⚠️ 要重置这个账号的口令，先把它那一行的 `password_hash` 置回 NULL、再回来签发（本仓今天没有『重置口令』端点，已登记为待清扫）」 | ✅ 响亮 + 如实 |

⚠️ **连带一格（不是缺陷，是如实登记的局限，本波补了实物取证）**：甲方那份活库 `pe_trial.db` 里 **60/60 个学生与 3/3 个教师全部已绑定口令、`bind_token` 0 行** ⇒ **在交付的那一份试用库上，令牌那一格签发不出去**。而说明书 §4 路线三第 6 步**已经逐字交代了这件事**（「⚠️ **试用库上这一格签发不出去**：63 个账号（60 学生 + 3 教师）都已经绑好了口令，而它**拒发**给一个已绑定的账号…要看它工作，请先在管理台新建一个账号，或让我方给一份**有未绑定账号**的库」）⇒ **本波实测与说明书逐字相符**，那句 workaround 也**真的可用**（本波亲验：管理员 `POST /api/students` 建出来的新学生 `password_hash` 是 `NULL`，给它签发令牌 → 201 成功）。⚠️ 但**交付含义是真的**：甲方在自己那份库上**一次都没能用过**本计划最重要的那一格安全功能 ⇒ 见 **R7-S4-2** 与 §⑦ 的处置建议。

### 3.4 `birth` 掩码有没有绕过路径（⚠️ 本波自己重跑了那个扫描，并把它扩到写响应 / 错误话 / 审计表）

**方法**：把 `backend/pe_demo.db`（60 个学生 / 60 个**互不相同**的真出生日期）复制到 `%TEMP%`，用 `TestClient` 真登录，然后**逐条**打 `READ_ROUTES` 的全部 **65** 个 GET 模板（路径参数用库里真 id 填），把响应体**原始文本**与那 60 个真出生日期逐个做子串匹配。

#### ① 以教师身份（`T0001`，`role='teacher'`）打全部 65 个 GET

```
GETs issued = 65     200 OK = 50 / 65     status 分布 = [200, 403, 404, 422]
*** 响应体里出现真出生日期的路 = 0 条 ***
出现掩码字面量 ****-**-** 的路 = 2 条：
    /api/students              [200]  mask ×50      ← 名册（缺省页长 50）
    /api/students/{student_id} [200]  mask ×1       ← 学生详情
```

⇒ **Task 5 那一句「以教师身份打全部 65 个 GET，出现真实出生日期的路 0 条」本波独立复现，逐字为真。**

⚠️ 而本波**不满意于**「50 个 200」这个覆盖面，把 15 条非 200 的**逐条**追到能出数据为止：

| 那 15 条里的关键几条 | 追法 | 结果 |
|---|---|---|
| `/api/teacher/students/{student_id}/home`（第一轮 403，因为填的 `student_id=1` 不在 `T0001` 的任教范围） | 换成**在范围内**的 `student_id=10`（`course_section 1` = 行政班01 = `teacher_id 1`） | **200**，响应体九格 `as_of/badges/pending_rpe/semester_id/stratification/student_id/unread_notifications/week/weekly_sheet` ⇒ **没有 `birth` 这一格**，真出生日期 **0** 命中 |
| `/api/mini-tests/normalized`（第一轮 422） | 422 的 `detail` 点名缺 `semester_id` 与 `week` ⇒ 补上 `?semester_id=2&week=1/5/8` | **200** ×3，真出生日期 **0** 命中 |
| `/api/teacher/students/{student_id}/normalized`（第一轮 422） | 补 `?semester_id=2&week=5` | **200**，真出生日期 **0** 命中 |
| `/api/students?limit=100` | 直接打 | **200**，**mask ×60**（全校 60 人逐个掩），真出生日期 **0** 命中 ⇒ 名册**不做行级收窄**（任何教职都读得到全校），而 `birth` 那一格**值级变形** |
| `/api/dashboard/class/1` · `/api/dashboard/weekly-class-report/1` · `/api/enrollments?limit=200` | 直接打 | **200** ×3，真出生日期各 **0** 命中 |
| `/api/teacher/students/{student_id}/weekly-sheet` | 打 `student_id=10` 与 `999999` | 两档都 **404**，报文是 `no_active_prescription`「学生 … 在 2026-10-19 没有生效的处方」⇒ **业务日为 `2025-10-12`、处方早已过期**，故这一档**在本波这份库上取不到数据**。⚠️ 本波改用**契约面**封它（见下面 ③） |

#### ② ⚠️ `POST` / `PATCH` 的响应体呢（派单点名）

**结论：写响应**确实**带完整 `birth`，而那条路只有 `role='admin'` 打得到 ⇒ 不是绕过，是既定裁定。**

```
管理员 T0003：
  PATCH /api/students/10 {"grade":2} -> 200
     body: {"id":10,"student_no":"2025050001","name":"韩妍","sex":"female",
            "birth":"2007-04-18","department":"医学院","grade":2}      ← 真值，未掩
  POST  /api/students {… "birth":"2001-02-03" …}  -> 201
     body: {"id":61,…,"birth":"2001-02-03",…}                          ← 回显提交值

普通教师 T0001（role='teacher'）：
  PATCH /api/students/10 -> **403**  「身份 'T0001' 不是管理员（teacher.role == 'teacher'）：
                                      管理台（23 个资源的增删改查）自 Plan 05A 起仅 role='admin' 可用」
  POST  /api/students    -> **403**  同一条报文
  GET   /api/students/10 -> 200  body 里 "birth":"****-**-**"           ← 读侧照旧掩
```

⇒ **写响应携带真值这一档，对普通教师不可达**（管理台写入自 Plan 05A 起仅 `role='admin'`），而「管理员读完整值」正是 Task 5 顶回后被裁定下来的那一格（守卫 `test_an_admin_reads_the_full_value_on_both_routes`）。⚠️ 而本仓**已经有一条守卫**钉住「普通教师连名册都写不了」：`tests/api/test_birth_scope.py::test_a_plain_teacher_cannot_write_the_roster_at_all` ⇒ 本波那一发 403 不是偶然。

#### ③ ⚠️ 契约面：全仓只有 **4** 个 schema 提到 `birth`，其中响应模型只有 **1** 个

亲量 `app.openapi()["components"]["schemas"]`（101 个）里含 `birth` 属性的：

| schema | 方向 | `birth` 的 schema |
|---|---|---|
| `StudentBindCreate` | **请求** | `{"type":"string","format":"date","title":"Birth"}` |
| `StudentCreate` | **请求** | 同上 |
| `StudentUpdate` | **请求** | `{"anyOf":[{"type":"string","format":"date"},{"type":"null"}],"title":"Birth"}` |
| **`StudentRead`** | **响应** | `{"type":"string","format":"date","title":"Birth"}` |

⇒ **`birth` 离开服务器的契约面只有 `StudentRead` 一个模型**，而它只被 `/api/students` 与 `/api/students/{id}`（+ 那两个 admin-only 写端点的响应）用。⚠️ 这一格把「有没有别的端点偷偷回完整值」这个问题从「65 条路逐个试」**收敛成「一个模型的所有用处」**——而本仓**已经有这条守卫**：`test_the_students_roster_is_the_only_response_model_that_carries_a_birth`。⚠️ 同时它证明 **Task 5「不改 schema、只改值」那句裁定在契约面上成立**：`StudentRead.birth` 的 schema 今天仍是 `{"format":"date","title":"Birth","type":"string"}`，与 Task 5 之前逐字相同。

#### ④ ⚠️ 错误话的 `ctx` 会不会回显

**不会。** 四档逐个真发：

```
GET /api/students/999999          -> 404  {"error":{"code":"not_found","message":"student 里没有主键为 999999 的行","detail":null}}
GET /api/students/not-a-number    -> 422  detail[0] = {"type":"int_parsing","loc":["path","student_id"],
                                                       "msg":"…","input":"not-a-number"}      ← input 只回**出问题的那一格**
POST /api/students {"sex":"not-a-sex", "birth":"2001-02-03", …}
                                  -> 422  detail[0] = {"type":"value_error","loc":["body","sex"],
                                                       "msg":"…收到 'not-a-sex'","input":"not-a-sex","ctx":{"error":{}}}
                                          ⚠️ 响应体里**不含** `2001-02-03`（亲验 False）；`ctx` 是 **`{"error":{}}`** = 空
```

⇒ `ctx` 不回显、`input` 只回出错的那一格 ⇒ **「别的字段出错 ⇒ 整个请求体（含 `birth` / 含令牌明文）被回显」这一档被封住**。⚠️ 令牌那一侧还有第二道（`TokenBindCreate.token` 用 `SecretStr` + `app/api/errors.py` 的 `_SENSITIVE_INPUT_KEYS` 按键名脱敏），守卫是 `test_a_validation_error_never_echoes_the_submitted_token`。

#### ⑤ ⚠️ 两条审计表里会不会落 `birth`

**不会，两份库上都验过。**

* **甲方活库**（只读）：`read_audit_log` **146** 行 + `audit_log` **36** 行，把 `at` 那一列**排除**之后逐行拼串，与那 **60 个真出生日期**逐个做子串匹配 ⇒ **0 命中**；连「**出生年份**」（`2002`–`2007` 六个）也是 **0 命中**。`read_audit_log.target` 的 `max(length())` = **2**（就是一个 id）⇒ 结构上装不下一个日期。
* **本波探针库**（在跑完上面全部 65×2 个 GET、1 个 PATCH、2 个 POST、1 个含新出生日期 `2001-02-03` 的 422 之后）：`read_audit_log` **325** 行 + `audit_log` **76** 行 ⇒ 含任何真出生日期（**包括刚 POST 进去的那个 `2001-02-03`**）的行 = **0**。

#### ⑥ ⚠️ CSV 摄取 / 导出那一侧呢

* **导出**：本仓**没有**任何 CSV/名册导出端点。亲量 openapi 的 77 条路径里没有 `/api/export*`、没有 `/api/teacher/roster`；`app/api/crud.py:759-761` 逐字写着「派单点名的 `/api/teacher/roster` 与 `/api/export/...` 在本仓**不存在**」，而这一格**有守卫**：`test_there_is_no_export_or_roster_route_and_the_csv_contract_never_crosses_http`。
* **摄取**：CSV 是**入**方向（三源采集，`PE_CSV_DIR`），它**不经过 HTTP**，故它不构成一条「`birth` 从服务器出去」的路。⚠️ 如实记一格代价：`birth` 的**原始值仍然明文躺在 `PE_CSV_DIR` 那几份 CSV 里**（那是数据源，不是本计划的面），而活服务那一份的目录是 `%TEMP%\pe_trial_csv_41684`（⚠️ 本波一个字节都没动它）。

#### ⑦ ⚠️ 学生读自己那一格（派单问「学生读自己**能**拿到」有没有被钉住）

**裁定与派单原文不同，而它被如实顶回并钉住了。** 实测：学生 `2025050001`（id 10）登录后打 `GET /api/students/10` → **403**、`GET /api/students?limit=100` → **403**；`GET /api/students/10/home` → **200** 而响应体里**根本没有 `birth` 这一格**（`real_births=0`、`mask=0`）⇒ **学生今天从 API 上读不到自己的完整出生日期，也读不到掩码**。守卫是 `test_a_student_session_is_rejected_by_the_row_gate_before_any_redaction`，而说明书 §10.5 第 4 条也逐字记着这一格（「学生 `2023120001` = **403** ✅ 正好印证 Task 5 顶回的第 ② 条：学生被**行级**闸门挡住，根本到不了值级变形那一步」）。⚠️ 判定：**这是一次合法的顶回**（计划 §5 原文就是「实现者核 spec 的既有口径后**提议**」），且两侧（守卫 + 说明书 + spec）都如实。

⇒ **本组判定：`birth` 掩码今天没有绕过路径。** 六条面（65 个 GET × 两种身份、写响应、契约面、错误话、两张审计表、CSV 两侧）**逐条查过，0 条绕过**。

### 3.5 迁移 5 与 6 的 `downgrade` 真能跑吗（⚠️ 本波自己真跑了一整圈）

**方法**：`%TEMP%\p08t7b\mig_probe2.db` 上 `alembic upgrade head`（31 张表），灌进 4 行数据（`semester` 1 行、`login_attempt` 1 行、`read_audit_log` 1 行、`bind_token` 1 行），然后**逐格对账**：每次 `downgrade -1` 之后，把「**除了 `alembic_version` / `bind_token` / `read_audit_log` 之外的全部表**」的 `(CREATE 语句原文, 列名清单, 全部行按第一列排序后的逐格字符串, 非自动索引名清单)` 摊平成 JSON 求 sha256，与基线比。

| 步 | 命令 | 退出码 | `alembic_version` | 表数 | 目标表 | **其余 28 张表逐字对账** |
|---|---|---|---|---|---|---|
| 基线 | `upgrade head` | 0 | `a1af54889103` | 31 | 两张都在 | 快照 hash **`57BB3C86CF4604E3`**（28 张表） |
| ① | `downgrade -1`（迁移 6） | **0** | `03331a689ee4` | 30 | `bind_token` **没了** | **UNCHANGED**，hash 仍是 **`57BB3C86CF4604E3`** |
| ② | `downgrade -1`（迁移 5） | **0** | `0ac943e0da9b` | 29 | `read_audit_log` **没了** | **UNCHANGED**，hash 仍是 **`57BB3C86CF4604E3`** |
| ③ | `upgrade head` | **0** | `a1af54889103` | **31** | 两张**都回来了**，`CREATE` 语句与基线**逐字相同** | `semester` 那 1 行**活着**；两张回来的表是**空表**（`DROP TABLE` 的必然代价） |

⇒ **迁移 5 与 6 的 `downgrade` 真能跑，且回滚不碰别的表一个字节。** ⚠️ 而「回来的两张表是空的」这一格是 `drop_table` 的固有代价，**不是缺陷**；本仓另有守卫钉住「迁移脚本不许携带数据」（`test_the_migration_scripts_carry_no_data`）。

#### ⚠️ 迁移 1 / 2 / 3 / 4 今天到底什么状态（派单点名，台账 B6 与 C3 各说了一半）

**本波从链尾一路 `downgrade -1` 走到 `<base>`，六条全部 rc = 0：**

| 从 | 那一条 `downgrade` 做的事 | 退出码 | 之后 `alembic_version` | 表数 |
|---|---|---|---|---|
| `0ac943e0da9b` | **迁移 4**：`login_attempt.login` 列宽 `VARCHAR(64)` → `VARCHAR(32)` | **0** | `7f3923d8af84` | 29 → 29 |
| `7f3923d8af84` | **迁移 3**：drop `audit_log` | **0** | `0b7da3d20211` | 29 → 28 |
| `0b7da3d20211` | **迁移 2**：drop `login_attempt` | **0** | `53e5a548c40e` | 28 → 27 |
| `53e5a548c40e` | **基线迁移**：drop 那 26 张表 | **0** | *（空）* | 27 → **1**（只剩 `alembic_version`） |

⇒ **三条裁定**：

1. ⚠️ **台账 C3（「Plan 06 Task 4 在迁移 4 上留过一个跑不通的 `downgrade`」）今天已经不成立**：迁移 4 的 `downgrade` 本波亲跑 rc = 0，而且它**另有一条常驻往返守卫** `tests/db/test_migration_chain.py::test_the_column_width_migration_round_trips_and_keeps_every_row`（head 上是 64 → `command.downgrade(…, "7f3923d8af84")` → 回到 32，**且两行数据逐字还在**）。⚠️ 那条守卫的 docstring 还如实记了一格**真局限**：SQLite **不校验** `VARCHAR` 长度，故 downgrade 到 32 之后一个 37 字符的值仍逐字保留；换 MySQL 会**静默截断**、于是两个不同的绑定键撞成同一个 —— 那一格已写进迁移 4 的模块 docstring。
2. ⚠️ **台账 B6（「迁移 1/2/3 仍无各自的 `downgrade` 往返守卫」）今天仍然成立**：`command.downgrade` 在全仓只被调用 **3** 次（`test_migration_chain.py:447`（迁移 4）、`:579`（迁移 5）、`:720`（迁移 6）），**迁移 1/2/3 各没有一条**。⚠️ 而它**如实登记在两处**：`test_migration_chain.py:84`「**迁移 1/2/3 仍然没有各自的往返守卫**（如实记，硬规矩 #39）」与 spec §15 B6。
3. ⚠️ **计划 §8 那半句「迁移链 4 → 6，且每一个 `downgrade` 都真跑过一遍」今天成立，而它的证据只在一次性探针里**：本波这一整圈（六条全 rc = 0、head → `<base>`）就是那一份取证。⇒ **裁定建议**：结案波把**本波这一圈**登记为 §8 那一格的取证（写进 spec 结案节），并**保留 B6 原样**（它说的是「没有**常驻守卫**」，与本波「**跑过一遍**」不冲突，两句今天都真）。⚠️ 不需要为此改代码；⚠️ 也**不要**把 §8 那半句改松——它今天确实被满足了。

---

## ④ 第 3 组 · Task 6 交给终审的三格

### 4.1 `/admin` 第 06 块与 `/bind` `.auth__fine`：补的那 2 条 needle **够不够**

#### 4.1.1 先把「改前 / 改后」的原文从 git 里挖出来（不采信报告）

`git show 35d7bb0`（= Task 6 ②「前端三处甲方看得见的半假散文 + 三条守卫」，2026-10-19 01:49:52，5 文件 +236/−13）逐字给出：

| 处 | 改前原文（`-` 行） | 改后原文（`+` 行） |
|---|---|---|
| `views/auth/Bind.vue` 模板末尾 `.auth__fine` | `⚠️ 验身材料（出生日期 / 姓名）在本原型里是**弱材料**：读那两份名册`（⚠️ `**弱材料**` 是**裸 Markdown**，页面上原样印两对星号） | `…在本原型里是<strong>弱材料</strong>：读那两份名册` **＋追加一整句** `⚠️ <strong>2026-10-18 起学生那一侧收了一半</strong>：名册上的出生日期对…` |
| `views/admin/ResourceIndex.vue` 第 06 块 | 「**任何教职**都读得到全校名册（含 `birth`）⇒ 一个已登录的教职可以替任何还没绑定的账号设口令」 | 抬头 `<strong>自助绑定的验身材料曾经等于零</strong>` ＋正文「⚠️ **2026-10-18 起学生那一侧收了一半**：名册上的 `birth` 对**普通教师**已经掩掉…**只有教务干事（管理员）照旧读到完整值** ⇒ 今天…**只对管理员成立**。⚠️ 而**教师那一侧一格没收**：工号与姓名对任何在册教职照旧全可读」 |

#### 4.1.2 那 2 条 needle 的实物与两侧同源性

`frontend/scripts/smoke.mjs` 第 14 步 `ROUTES` 数组：

| 路由 | needle | 位置 | 期望侧 / 被测侧 |
|---|---|---|---|
| `bind`（`/bind`） | `'2026-10-18 起学生那一侧收了一半'` | 该路由 `needles` 的**第 6 条**（`smoke.mjs:2771`） | 期望侧 = **脚本里的字面串**；被测侧 = **无头浏览器渲染出来的 DOM 正文** ⇒ **两侧不同源** ✅ |
| `admin-index`（`/admin`） | `'自助绑定的验身材料曾经等于零'` | 该路由 `needles` 的**第 11 条**（`smoke.mjs:2830`） | 同上 ✅ |

#### 4.1.3 ⚠️ 「把新散文逐字改回原文，守卫会红吗」——本波的判定

**会红，但只红在 smoke 第 14 步那一条上；产物侧的守卫一条都不红。** 三格取证：

1. ✅ **needle 真的在产物里**（本波逐文件扫 `frontend/dist` 的 27 个文件）：
   * `自助绑定的验身材料曾经等于零` → **1** 命中，住址 `assets/ResourceIndex-1rJx9BeE.js`
   * `2026-10-18 起学生那一侧收了一半` → **2** 命中（`assets/index-DG9aiaVT.js` 1 + `assets/ResourceIndex-1rJx9BeE.js` 1）
   * 正文那两句 `只对管理员成立` / `教师那一侧一格没收` → 各 **1** 命中（都在 `ResourceIndex` 那个 chunk 里）
   * ⚠️ **改前原文 `任何教职` / `都读得到全校名册` → 各 0 命中** ⇒ Task 6 那一改**真的落进了发给甲方的产物**
   * ⚠️ 掩码字面量 `****-**-**` → **0** 命中（它的单一所有者留在后端 `app/api/crud.py`），与 `check:dist` 自己印的那一条逐字相符
2. ⚠️ **改回原文 ⇒ needle 从 DOM 上消失 ⇒ 第 14 步那一条断言红**。这一格是**结构上必然**的：两条 needle 各自钉的正是「改后**新增**的那一句」（`bind` 那条钉追加句、`admin-index` 那条钉新抬头），改前原文里**一个字都没有它们** ⇒ 逐字改回原文就是把它俩从页面上抹掉。⚠️ 本波**没有真去改前端源**（理由见 §⑩「我没查的」第 2 条：那需要重建 `dist`，而重建会当着甲方的面换掉活链接的前端），故这一格是「静态 + 产物双面取证」而**不是**一次跑出来的红。
3. 🔴 **而产物侧那条守卫（`check-dist.mjs`）对这个变异一句都不说**。亲验：`FORBIDDEN_STALE_CLAIM` 那**四组**判据逐字是「不做…登录失败锁定」/「口令找回 / 登录失败锁定」这份清单 /「它走的是匿名」/「180 行全量」（`check-dist.mjs:108` 起），⚠️ **`任何教职` 与 `都读得到全校名册` 这两个串在整份 `check-dist.mjs` 里 0 命中**（本波直接 grep 过）。⇒ **把 `/admin` 第 06 块改回原文、重建 `dist`，`npm run check:dist` 仍然全绿**，唯一会红的是 smoke 第 14 步 —— 而它是**全脚本最贵、最容易被跳过**的一步（要 dev server + 无头浏览器 + CDP）。

#### 4.1.4 ⚠️ 还有一个 Task 6 没提到的残余缺口（本波新抓到）

`admin-index` 那条 needle 钉的是**抬头**（`自助绑定的验身材料曾经等于零`），**正文那两句**（`只对管理员成立` / `教师那一侧一格没收`）**一条判据都没有**：

* 逐条核对 `admin-index` 的 11 条 needle（`资源目录` / `23 resources` / `可写 9` / `只读 14` / `体育专家维护的知识资产` / `读要身份，只有 7 个例外` / `写仅管理员` / `换身份请登出再登录` / `ONE-TIME BIND TOKEN` / `PE_ALLOW_SELF_BIND` / `自助绑定的验身材料曾经等于零`）与它的 4 条 `uniqueNeedles` ⇒ **没有一条落在正文那两句上**；
* ⇒ 变异 **M6a′ =「保留新抬头、只把正文那一段改回『任何教职都读得到全校名册（含 birth）』」今天全绿**（第 14 步 11 条 needle 全部仍被满足，`check-dist` 也绿）。⚠️ 而这个变异**恰好是这一族最可能的自然形态**：抬头是「**曾经**等于零」（一句过去时、往后一直真），正文是「**今天**只对管理员成立」（一句现在时、下一次收窄就变假）。§10.6 已经实证过这个形态会发生（「每次收窄一个可见面，所有描述它的散文都要跟着改，**包括同一波自己刚改对的那些**」）。
* ⚠️ 同理 `bind` 那条 needle 钉的也是**追加句**，而 `.auth__fine` 里那句**改前就有、今天仍半假风险最高**的「验身材料（出生日期 / 姓名）在本原型里是**弱材料**」只被 §Task6-④ 的**反向**判据盖住一半（它要求「验身材料（出生日期 / 姓名）」**仍在**、且不许出现「需要令牌」一类说法）⇒ **「弱材料」这三个字今天仍然在页面上、在 `dist` 里 1 命中**，而它按 Task 6 自己的说法「只对管理员为真」。⚠️ 它靠**紧跟着的那一句追加**来限定，而不是靠自己被改对。

⇒ **判定：Task 6 补的 2 条 needle 对 M6a / M6b 那两个变异是够的（结构上必然红），但对「只改正文不改抬头」与「弱材料那三个字本身」两档不够。** 处置见 **R7-S3-3**。

### 4.2 `dist` 与源同步：今天只有 mtime 旁证，不是一条守卫 —— **该不该有一条真守卫**

#### 4.2.1 先把今天的实物状态量清楚（⚠️ 这一格是 R7-S1-1 的引信）

| 格 | 实测 |
|---|---|
| `dist/index.html` 的构建戳（mtime） | **2026-10-19 02:27:05.014793** |
| 源面（`frontend/src/**` 全部文件 + `index.html`/`package.json`/`vite.config.ts`/`tsconfig*.json`）扫到 | **65** 个文件（⚠️ 高于 `serve.ps1` 自己那道 `< 20 就 throw` 的反空转下界） |
| 源面里**比构建戳新**的文件 | **4** 个，mtime 全是 **2026-10-19 11:47:20**（±5 ms ⇒ 一次批量写回）：`src/views/teacher/StudentDetail.vue` · `src/views/auth/Bind.vue` · `src/views/admin/ResourceIndex.vue` · `src/api/generated/schema.d.ts` |
| 这 4 个文件的**内容**最后一次改动 | **2026-10-19 01:49:52**（`35d7bb0` 三个 `.vue` / `98effb1` `schema.d.ts`）⇒ **早于** 02:27:05 那次构建 |
| ⇒ 内容同步吗 | ✅ **同步**（工作树 == HEAD，`git status --porcelain` 为空；`dist` 是那三个 `.vue` 改完之后才构建的；本波又逐串验过产物里含改后的新散文、不含改前原文，见 4.1.3 第 1 格） |
| ⇒ mtime 同步吗 | ❌ **不同步**（源面新 9 小时 20 分） |
| `serve.ps1` 的判据 | **mtime**：「源面里最新的一个 mtime 比构建戳新 → **重建**」（`serve.ps1:35-50`），失效方向刻意折向「重建」 |
| ⇒ 今天跑一次 `serve.ps1`（不带 `-SkipBuild`）会怎样 | 🔴 **它会当场跑 `npm run build`** |

#### 4.2.2 裁定：**不该加一条「重建式」的真守卫；该加的是把已有的「串对串」守卫扩一条，并且把 `-SkipBuild` 写进结案波派单**

三条理由：

1. ⚠️ **一条真守卫只可能是「跑一次构建再比字节」，而那一格在本仓是被明令禁止的动作**：`serve.ps1` **按请求从磁盘读 `dist`**（Plan 08 Task 4 实测过：`npm run build` 一落地，甲方那条 8030 立刻就换上新前端），故「守卫自己触发一次构建」= 守卫自己制造半切换态。而 `.gitattributes` 把 `frontend/dist` 排除在入库之外 ⇒ 也**没有**「上一份产物」可比。
2. ✅ **而 Task 6 说的那一类形状（「产物里的某个串等于源里的某个串」）今天已经存在，而且是双向的**：`check-dist.mjs` 的 `FORBIDDEN_STALE_CLAIM` 那一段自己的注释逐字写着「『改了源、忘了重建』—— 那时**源侧绿、产物侧红**。故产物那一侧读的是**磁盘上真的那一份**（不触发构建），一份陈的产物当场红」，并且**四组判据各组都带自校**（本波亲跑 `node scripts/check-dist.mjs --no-build`，退出码 0，输出里逐条印着「自校 ①：谓词**抓得到**改前那句 → 1 次（应 ≥ 1）」与「自校 ②：谓词**放过**改后那句 → 0 次（应为 0）」）⇒ **这一族的守卫形状是对的、两侧不同源、且带正反控**。
3. ⇒ **缺的不是「一条新形状的守卫」，而是那一组禁用串的覆盖面**（今天只有 4 条过期断言 + 掩码字面量 + `adoptFromUrl` + 两个 CDN 域名）。⚠️ 本波的具体建议：把 **`任何教职[^。；\n]{0,24}都读得到全校名册`** 加成 `FORBIDDEN_STALE_CLAIM` 的**第 5 组**（⚠️ 照它既有姿势带两拍自校：改前原文命中 ≥ 1、改后正文命中 0）。⚠️ 加了它之后，4.1.4 那个 M6a′ 与 4.1.3 第 3 格那个「重建也绿」同时被堵上，**且不需要浏览器**。

⚠️ **而 R7-S1-1 是另一件事**：它不是「守卫缺失」，而是「**今天 mtime 判据已经被触发**，故任何一次不带 `-SkipBuild` 的 `serve.ps1` / 产品档 smoke 都会重建 `dist`」。⇒ 处置是**运维纪律**，不是代码：结案波一律 `-SkipBuild`（详见 §⑧）。

### 4.3 `pe_trial.db` 被真人写过 —— 它暴露了什么问题（⚠️ 控制者已查清是谁，本波只判含义）

**本波独立复核了那一份库的实物**（只读打开，前后逐字节相同）：

```
audit_log 36 · read_audit_log 146 · user_session 20 · login_attempt 4 · training_log 842 · bind_token 0
student 60/60 已绑定口令 · teacher 3/3 已绑定口令 · version_num = a1af54889103（= 链尾）
login_attempt 的 4 行：('student','2025060001',ok=1,'2026-10-17 15:27:23') ·
                       ('student','2023120001',ok=1,'2026-10-19 09:45:27') ·
                       ('teacher','T0003',    ok=1,'2026-10-19 09:50:03') ·
                       ('teacher','T0001',    ok=1,'2026-10-19 12:30:39')   ← ip 全是 38.45.155.89
read_audit_log 的时间跨度：09:38:57 → …（含 1 行 403 = 学生 id 4 打 /api/students 被行级闸门挡住）
```

⇒ **五条含义，逐条给处置**：

1. 🔴 **结案波（Task 8）绝对不许 `-Reset`，也不许对 `pe_trial.db` 跑 `retention.py`。** 那 842 行 `training_log`、146 行 `read_audit_log`、36 行 `audit_log` 是**真人试用痕迹**，`-Reset` 会一次冲掉。⚠️ 而 `retention.py` 在**缺省窗口**下会删掉：`login_attempt` 30 天之前的行（那 4 行里 2026-10-17 那一行**在窗口内**，故今天一行都不会被删）、`read_audit_log` 90 天之前的行（**0 行**）、`audit_log` 365 天之前的（**0 行**）、`user_session` 已过期 7 天以上的（**0 行**）⇒ **今天跑一次缺省清理对那份库是 0 行删除**（本波在探针库上验过判据与窗口）。⚠️ 但这**不是**可以跑它的理由：那是一份含真人操作痕迹的库，清理是不可撤销的，而收益是 0 行。
2. ⚠️ **`bind_token` 0 行的原因不是「甲方没试」，而是「甲方在那一份库上试不成」。** 本波实测：`POST /api/auth/bind-tokens` 对一个**已绑定**的账号回 **409 `password_already_bound`**（报文逐字「一张发给它的令牌**永远兑换不了**…故本端点拒发」），而那份库里 **63 个账号（60 学生 + 3 教师）全部已绑定** ⇒ **签发这一步就过不去**。⚠️ **这一格说明书已经逐字交代了**（§4 路线三第 6 步末尾：「⚠️ **试用库上这一格签发不出去**：63 个账号（60 学生 + 3 教师）都已经绑好了口令，而它**拒发**给一个已绑定的账号…要看它工作，请先在管理台新建一个账号，或让我方给一份**有未绑定账号**的库」）⇒ **不是假话，是如实登记的局限**。⚠️ 而它给的 workaround **本波亲验可用**：管理员 `POST /api/students` 建出来的新学生 `password_hash` 是 `NULL`，给它签发令牌 → **201**。
   ⇒ **这算不算一个交付问题？** **算，但是 S4 不是 S1**：本计划最重要的那一格安全功能，甲方在交付环境上**一次都没能亲手走通**（`read_audit_log` 里那 1 行 `/api/auth/bind-tokens` 只证明管理员**打开过台账页**，而那一次台账是空的）。⚠️ 处置建议（**不改代码**）：结案波在**重打包**那一份可分发试用包时，让 `trial.ps1 -Reset` 灌出来的库**刻意留 1–2 个未绑定账号**（例如把某一个学生的 `password_hash` 留 `NULL`），并在说明书路线三第 6 步把那一句「试用库上这一格签发不出去」改成「**本库刻意留了学号 XXXX 未绑定，用它走这一格**」。⚠️ 这是一次**产品面**的改动（`demo_bootstrap.py` / `trial.ps1`），⇒ **不属于结案波**，建议登记为 spec §15 的一条新台账（**下一个计划**做），本波只报不改。
3. ⚠️ **那一份库今天没有任何一份「含真人数据」的备份。** `backend/backups/` 里只有控制者那两份**迁移前**快照（`pe_trial-pre-migration5-…` 1 589 248 B / `pe_trial-pre-migration6-…` 1 597 440 B），都是 10-17 与 10-18 的；而 09:39–09:51 与 12:30 那两次真人试用写进去的行**不在任何一份备份里**。⚠️ 而备份今天是**明文**的（`PE_BACKUP_KEY` 没设）⇒ 处置建议：结案波之前，控制者**自己**跑一次 `backup.ps1 -DbUrl sqlite:///<…>/backend/pe_trial.db`（⚠️ 在线备份，服务不用停；⚠️ 而 `-Keep` **不要给**，给了会删掉那两份迁移前快照）；⚠️ 若要加密，设 `PE_BACKUP_KEY` 并把口令记在与备份分开的地方。
4. ✅ **切换窗口其实已经关掉了**：`pe_trial.db` 的 `version_num` **已经是链尾** `a1af54889103`（本波只读量到），`dist` 已经是含新散文的那一份（本波逐串验过），活服务 PID 36876 跑的就是 `main` 的代码 ⇒ **Task 8 不需要迁移、不需要重建产物、不需要重启服务**（逐格见 §⑧）。
5. ✅ **没有静默的周期任务**：`schtasks /query` 里搜 `retention` / `PE_` / `pe-ims` ⇒ **0 命中**（本波亲跑），而 `register_retention_task.ps1` 自己逐字印着「⚠️⚠️ 本脚本**不自动注册**：下面四条一律是**打印**，请自己粘到一个**管理员**身份的命令行里跑」⇒ **没有任何东西会在夜里自动删甲方那份库的行**。这一格是计划 §2 第 4 条裁定的兑现，本波验到实物。

---

## ⑤ 第 4 组 · 对抗性

### 5.1 假守卫：本计划新增的守卫逐条判「期望侧与被测侧是否同源」

⚠️ 判据：把**期望侧**与**被测侧**各自追到它的字面住址；若两侧读的是同一份产物，就是自指守卫（Plan 06 的 `OVERLONG_SUFFIX` 判例）。⚠️ 每条给「我怎么让它变红」的**实测**（= 下面 5.2 的定点变异编号）；做不出红的按假绿报。

| # | 守卫（住址） | 期望侧 | 被测侧 | 同源？ | **怎么让它变红（实测）** |
|---|---|---|---|---|---|
| G-1 | `test_every_get_route_is_classified_exactly_once`（`tests/api/test_read_audit_api.py:292-324`） | `client.get("/openapi.json")` 里**活的** GET 路径集合 | `READ_ROUTES` 那**一张字面量表** | ❌ 不同源 ✅ | **M7-10**：往 `main.py` 塞一个假 GET `/api/probe-fake-unclassified` → 红，报文逐字「有 `['/api/probe-fake-unclassified']` 个 GET **没有被归类**…不回答的缺省档是『不记』，而那正是本条要消灭的静默失效」✅（**派单点名的「自己塞一个假路由试」就是这一格**） |
| G-2 | `EXPECTED_SENSITIVE_COUNT = 47` / `EXPECTED_ROUTINE_COUNT = 18`（同文件 `:109-110`） | **两个字面量**（注释逐字写着「⚠️ 两侧同源的话『把一个类从记翻成不记』会同时改掉两边、断言恒成立」） | 从 `READ_ROUTES` + `READ_CLASSES` 现算 | ❌ 不同源 ✅ | **M7-5**（`STUDENT_ROSTER` → `False`）→ 红，`AssertionError: 43`；**M7-9**（`REFERENCE_DATA` → `True`）→ 红，`AssertionError: 61`。**两个方向都咬** ✅ |
| G-3 | `test_the_read_predicate_is_a_single_owner_and_only_looks_at_the_route`（同文件 `:327-383`） | 字面量 `["READ_CLASSES", "READ_ROUTES"]` + 「`READ_ROUTES` 只被赋值 1 次」+「全仓无处 import 它」 | 对生产文件做 **AST** 解析 | ❌ 不同源 ✅ | 结构守卫：往 `is_sensitive_read` 里加第三个判据来源即红（本波未变异它，改判为**形状正确**；⚠️ 如实记：本波**没有**为它做出一次红） |
| G-4 | ⚠️ `test_every_sensitive_read_leaves_exactly_one_row_and_every_routine_read_leaves_none`（同文件 `:408-…`） | 🔴 **`READ_CLASSES[READ_ROUTES[t]].sensitive`——生产表本身** | 真发 HTTP + 真查 `read_audit_log` 的行数 | ⚠️ **被测侧独立、而「记不记」的期望侧与被测侧同源** | **做不出红**：**M7-5** 与 **M7-9** 两次变异里，**首红的一律是 G-2（`test_every_get_route_is_classified_exactly_once`），本条一次都没红**。⇒ 它的 docstring 那句「**两侧不同源**」**只对一半**：「真发 HTTP / 真查行数」那一半确实独立，而「这一条算不算敏感读」的期望侧**就是被测代码读的那两张表** ⇒ **单看本条，「把一个类从记翻成不记」是恒绿的**。⚠️ 它的 docstring 自己括注了「不调 `is_sensitive_read` 去算期望值」——那句话说的是**没调那个函数**，而**读了那两张表**，两者不是一回事 |
| G-5 | `test_a_dry_run_deletes_not_a_single_row`（`tests/test_retention.py:171-206`） | **字面量** `{user_session:2, login_attempt:2, audit_log:2, read_audit_log:2}` + `predicted` 的字面量 `{1,1,1,1}` | `_counts(db)` = **另开一条独立连接**现数（docstring 逐字「不是读被测代码的返回值」） | ❌ 不同源 ✅ | **M7-2**（把 `if dry_run:` 短路改成 `if False:`）→ 红 3 条，首红报文 `assert {'session': 1, …} == {'session': 0, …}` ✅；**M7-8**（`DEFAULT_SESSION_DAYS = 7` → `0`）→ 红 **21** 条，报文是 `RetentionError: user_session 的保留窗口给的是 0 天，而下界是 1 天…⚠️ 0 天的语义是「把这张表**全部**删掉」…本 CLI 拒绝它` ✅ |
| G-6 | `test_a_missing_key_still_produces_a_usable_plaintext_backup_and_says_so_loudly`（`tests/test_backup_restore.py`） | 断言里写死的**告示串**（`'**明文**的'` 一类） | 真跑一次 `backup.py` 抓 stdout | ❌ 不同源 ✅ | **M7-6**（删掉 `backup.py:1514` 那一句 `print`）→ 红 1 条，报文 `AssertionError: ('**明文**的', '== 厦大体育数智系统 · 备份 ==…')` ✅ |
| G-7 | `test_prune_deletes_the_oldest_and_takes_their_sidecars_with_them`（同文件） | 写死的**最旧那一份文件名** + 删除清单串 | 真跑 `prune_backups` 抓 `emit` 出来的行 | ❌ 不同源 ✅ | **M7-7**（删掉 `backup.py:1368-1371` 那个「逐个打印」的 `emit`）→ 红 2 条，首红报文点名 `pe-20261001T030000Z.db` ✅ |
| G-8 | `test_the_plaintext_token_and_its_secret_never_reach_any_column_of_any_table`（`tests/api/test_bind_token.py`） | 测试**自己签发出来的**明文令牌 | **全库 30 张表的每一列** | ❌ 不同源 ✅ | 本波**独立复现**了同一形状（§3.3 第 2 格）：扫**31** 张表逐列，明文 **0** 命中、秘密那一段 **0** 命中、只有选择子落在 `bind_token.token_id`。⚠️ 本波**没有**为这条守卫做出一次红（要做出红得把哈希改成明文入库，那是一次产品改动） |
| G-9 | `FORBIDDEN_BIRTH_MASK`（`frontend/scripts/check-dist.mjs`，Task 6 新增） | **字面量** `****-**-**`（注释逐字「⚠️ 与 `app.api.crud.BIRTH_MASK` **刻意写成两份**：期望侧抄被测侧的话，『把掩码改成一个合法日期』这类变异就抓不到了」） | **产物侧 23 个文件 + 源码侧 56 个文件**都扫，⚠️ 且**刻意不剥注释** | ❌ 不同源 ✅ | 本波亲跑 `--no-build`：三拍自校全过（「谓词抓得到一次真的抄写 → 1 次（应为 1）」「谓词放过改后那一句人话 → 0 次（应为 0）」「不剥注释 → `maskCountOf=1` / 剥注释后 0」），退出码 **0**；⚠️ 而本波另外逐文件扫了 `dist` 的 27 个文件，`****-**-**` **0 命中** ✅ |
| G-10 | ⚠️ `FORBIDDEN_STALE_CLAIM`（同文件 `:108` 起，**四组**判据） | 四个**正则字面量**，各带两拍自校（改前那句 ≥1、改后那句 =0） | 磁盘上**真的那一份 `dist`** + 源码侧 | ❌ 不同源 ✅（形状是这一族里最好的） | ⚠️ **但覆盖面只有 4 条**：「不做…登录失败锁定」/「口令找回 / 登录失败锁定」/「它走的是匿名」/「180 行全量」。🔴 **`任何教职`、`都读得到全校名册` 这两个串在整份 `check-dist.mjs` 里 0 命中**（本波直接 grep 过）⇒ **把 `/admin` 第 06 块改回 Task 6 之前的原文、再重建 `dist`，这一组一句都不说**（详见 §4.1.3 第 3 格与 **R7-S3-3**） |
| G-11 | smoke 第 14 步的 2 条新 needle（`smoke.mjs:2771` / `:2830`） | 脚本里的**字面串** | 无头浏览器**渲染出来的 DOM 正文** | ❌ 不同源 ✅ | 结构上必然红（两条 needle 钉的都是改后**新增**的那一句，改前原文里一个字都没有）；⚠️ 但 **`admin-index` 那条钉的是抬头、正文那两句一条判据都没有** ⇒ 变异 **M6a′**（留抬头、只把正文改回原文）今天全绿（详见 §4.1.4） |
| G-12 | 🔴 **`app/auth/bind_tokens.py:316` 的 `expires_at <= now`** —— 「恰好等于那一刻也算过期」这条**写在 docstring 里的判据边界** | — | — | ⚠️ **根本没有守卫** | **M7-3 做不出红**：把 `<=` 改成 `<`，**13 个提到 bind token 的测试文件、379 条测试全绿**；再用 `-k "expir or ttl or spent"` 扫**全量** `tests/`，**22 条全绿**（1752 deselected）⇒ **假绿**，见 **R7-S2-1** |

⇒ **假守卫抓到 1 条真绿不下来的（G-12）、2 条「同源一半 / 覆盖面不够」的（G-4、G-10）、1 条「只钉抬头不钉正文」的（G-11）**。⚠️ G-4 与 G-10/G-11 都**不是恒真**（它们在别的变异下会红），故按「覆盖面缺口」报，不按「假绿」报。

### 5.2 定点变异：**10 格**（⚠️ 挑的都是前六波没做过的面）

⚠️ 纪律：**改 → 跑 → 必须红 → 从 TEMP 里那一份副本逐字节还原 → sha256 对账 → `git status --porcelain` 复验为空**。⚠️ **全程没有用 `git checkout` 还原任何文件**（还原一律 `shutil.copyfile` 回本波自己存的副本，再用 sha256 对账）。

| ID | 文件 | 改了什么 | 跑的测试 | 结果 | 还原 sha 对账 | `git status` |
|---|---|---|---|---|---|---|
| **M7-1** | `app/main.py:477` | 把 `install_read_audit(application)` 从装配链里**摘掉**（⚠️ 派单点名的那一格） | `tests/api/test_read_audit_api.py` | 🔴 **10 failed / 8 passed**，首红报文「`/api/alerts` 是敏感读而它落了 **0** 行（要恰好 1 行）；响应码 200」 | ✅ `b25c1f0f11c4871b` 前后相同 | ✅ 空 |
| **M7-2** | `scripts/retention.py:533` | 把 `--dry-run` 的短路 `if dry_run:` 改成 `if False:` | `tests/test_retention.py` | 🔴 **3 failed / 31 passed**，首红 `test_a_dry_run_deletes_not_a_single_row` | ✅ `eda4e2616113d96f` | ✅ 空 |
| **M7-3** | `app/auth/bind_tokens.py:316` | 令牌 TTL 判据 `expires_at <= now` → `expires_at < now` | `tests/api/test_bind_token.py`（24 条）→ 复扩到**全部 13 个**提到令牌的测试文件（379 条）→ 再扩到 `-k "expir or ttl or spent"` 的**全量**（22 条） | 🟢 **三次全绿**（24 / 379 / 22 passed，0 failed，退出码 0）⇒ **假绿** | ✅ `0f4740637bab23b2` | ✅ 空 |
| **M7-4** | `app/api/crud.py:788` | `REDACT_ADMIN_ONLY = frozenset({ADMIN_ROLE})` → `frozenset({ADMIN_ROLE, "teacher"})`（⚠️ 派单点名的「把掩码判据放宽」那一族） | `tests/api/test_birth_scope.py` | 🔴 **8 failed / 13 passed**，首红 `test_a_plain_teacher_reads_the_mask_on_the_roster_and_on_the_detail` | ✅ `2cd9c1e580ff6f79` | ✅ 空 |
| **M7-5** | `app/api/read_audit.py:267` | `STUDENT_ROSTER` 从 `sensitive=True` 翻成 `False`（⚠️ 计划 §1 第 6 条点名的「把敏感清单去掉一条」） | `tests/api/test_read_audit_api.py` | 🔴 **8 failed / 10 passed**，首红 `AssertionError: 43`（= 47 − 4 条 `STUDENT_ROSTER` 路由） | ✅ `34ab279c6cd6470d` | ✅ 空 |
| **M7-6** | `scripts/backup.py:1514` | 删掉缺 `PE_BACKUP_KEY` 时那段 ⚠️ 告示的第一句（⚠️ 计划 §3 第 6 条点名的变异） | `tests/test_backup_restore.py` | 🔴 **1 failed / 62 passed**，首红 `test_a_missing_key_still_produces_a_usable_plaintext_backup_and_says_so_loudly` | ✅ `cffef936a7a73598` | ✅ 空 |
| **M7-7** | `scripts/backup.py:1368-1371` | 删掉 `-Keep` 那份「逐个打印要删哪几份」的 `emit`（⚠️ 计划 §3 第 6 条点名的另一半） | `tests/test_backup_restore.py` | 🔴 **2 failed / 61 passed**，首红 `test_prune_deletes_the_oldest_and_takes_their_sidecars_with_them` | ✅ `cffef936a7a73598` | ✅ 空 |
| **M7-8** | `scripts/retention.py:198` | `DEFAULT_SESSION_DAYS = 7` → `0`（⚠️ 派单点名的「把某个窗口缺省值改成 0」） | `tests/test_retention.py` | 🔴 **21 failed / 13 passed**，报文是 `RetentionError`：「0 天的语义是『把这张表**全部**删掉』——包括今天刚写的行，那是『误删一切』的形状，本 CLI 拒绝它」⇒ **窗口下界这一格咬得很响** | ✅ `eda4e2616113d96f` | ✅ 空 |
| **M7-9** | `app/api/read_audit.py:317` | `REFERENCE_DATA` 从 `False` 翻成 `True`（**反方向**：过度记录） | `tests/api/test_read_audit_api.py` | 🔴 **2 failed / 16 passed**，首红 `AssertionError: 61`（= 47 + 14 条参考数据路由） | ✅ `34ab279c6cd6470d` | ✅ 空 |
| **M7-10** | `app/main.py:477` 之前 | **塞一个假 GET 路由** `/api/probe-fake-unclassified`（⚠️ 派单逐字点名「自己塞一个假路由试」） | `tests/api/test_read_audit_api.py` | 🔴 **2 failed / 16 passed**，首红报文逐字「有 `['/api/probe-fake-unclassified']` 个 GET **没有被归类**：新加了一个读端点而没进 `app/api/read_audit.py` 的 `READ_ROUTES`」 | ✅ `b25c1f0f11c4871b` | ✅ 空 |

⇒ **10 格里 9 格红、1 格（M7-3）做不出红**。⚠️ **10 格全部逐字节还原**（`shutil.copyfile` 回本波自存的副本 + sha256 前后对账，10/10 相同），**每格之后 `git status --porcelain` 都是空**，全部变异跑完后**再验一次仍是空**。

⚠️ **本波刻意没做**的三类变异（如实记）：① 前端源（`Bind.vue` / `ResourceIndex.vue` / `StudentDetail.vue`）—— 改它们就必须重建 `dist`，而重建会当着甲方的面换掉活链接的前端（派单逐字禁止）⇒ M6a / M6b / M6a′ 三格本波只做**静态 + 产物双面取证**（§4.1.3）；② `aes_cbc.ps1` 的「先验 MAC」顺序 —— 它的 Python 侧同族判据已由本波**行为实测**覆盖（§3.2.6：错密钥 → 退出码 2 + 目标库 sha 前后逐字相同 + 报文自陈「一步都没有解密」），故没有为改那个 `.ps1` 再花一次还原成本；③ `data/**` 与五份 manifest —— 禁区，一格都没碰。

### 5.3 失效方向：本计划新增的破坏性 / 不可逆操作逐条

| 操作 | 出错时是响亮还是静默 | **本波实测取证** | 有没有静默产出坏数据的路 |
|---|---|---|---|
| `retention.py` 真删 | **响亮** | 预告 → 删 → **实删与预告逐格对账** → 「删完仍满足判据 0」；不符就**整批回滚**（`RetentionError`，退出码 **2**）。删之前还印一段「本 CLI **不会**自动备份 + 三条理由 + 该先跑哪条命令」 | ❌ 没找到 |
| `retention.py --dry-run` | **响亮且不取写锁** | 跑完库的 **sha256 逐字节未变**（`8367D202C0C27FD1` 前后相同）；并发写实测 **0.015 s 成功**（§3.2.3） | ❌ |
| `retention.py` 库路径写错 | **响亮** | 源码逐字「本脚本刻意不让 SQLite『打开即建』（那会把『路径写错了』变成一次『四张表都是 0 行』的**静默成功**）」⇒ `RetentionError` | ❌ |
| `retention.py` 窗口给 0 / 低于下界 | **响亮** | **M7-8** 实测：`RetentionError` + 21 条守卫红 | ❌ |
| `backup.ps1 -Keep N` 删旧备份 | **响亮** | 逐个打印（名 / 字节 / sha256[:16] / 侧车在不在）→ 删 → **复核**「剩 `min(keep, 现存)` 份、那几个名与侧车都已不在、认不出的东西一个都没动」；`-Keep 0` **在任何一次写之前**就拒（退出码 2，目录里文件数一个没变） | ❌ |
| `backup.ps1` 缺 `PE_BACKUP_KEY` | **响亮**（而不是静默产出一份看起来一样的备份） | 14 行 ⚠️ 告示，且自陈「**不因任何别的环境变量而闭嘴**」；退出码 0（计划 §3 的裁定：不 raise） | ❌ |
| `restore.py` 覆盖库 | **响亮** | 侧车 sha + 字节数先校验 → 覆盖前自动留 `-pre-restore` 后路（本波实测那一份后路在 `PE_BACKUP_KEY` 在时**是加密档**）→ 覆盖后自检（表数 / `alembic_version` / 行数）并**如实解释**「表数比 `/api/health` 多 1」 | ❌ |
| `restore.py` 密钥不对 / 产物被改 | **响亮** | 退出码 **2**，「**先验 MAC、验不过就不往下走**，一步都没有解密」；**目标库 sha256 前后逐字相同**（`DBDA0B375F807426…`）；⚠️ `--no-verify` **跳不掉** HMAC 那一格 | ❌ |
| `alembic downgrade`（迁移 5/6） | ⚠️ **半静默** | 跑得通（rc 0）、其余 28 张表逐字未变（hash `57BB3C86CF4604E3` 三次相同）；⚠️ 而**被 drop 的那张表里的行一并没了**，`upgrade head` 回来是**空表**——alembic **一句警告都不印** | ⚠️ 会**丢数据**而不响。⚠️ 判定 **S4**：`downgrade` 是开发者工具、不是运维工具，而 `DROP TABLE` 的语义就是如此；⚠️ 但与 `retention.py` 那句「下面这一步**不可撤销**」的口径**不一致**，建议结案波在迁移 5/6 的 `downgrade` docstring 里各加一句「⚠️ 这一句会连表里的行一起丢掉」（⚠️ 只是注释，不改行为） |
| `trial.ps1 -Reset` | ⚠️ **本波没跑**（派单逐字禁止：甲方那份库里有真人试用痕迹） | 只做了静态核：`.gitignore` 与 `trial.ps1` 的 `$TrialDbName` 两侧不同源、由 `tests/test_trial.py` 按字面钉住；⚠️ 「`-Reset` 对非缺省库要 `-Force`」这一格本波**未实测**（见 §⑩） | 未测 |
| `register_retention_task.ps1` | **不自动改机器** | 亲跑 `schtasks /query` 搜 `retention` / `PE_` / `pe-ims` ⇒ **0 命中**；脚本自己印「⚠️⚠️ 本脚本**不自动注册**：下面四条一律是**打印**」 | ❌ |

⇒ **本计划新增的破坏性操作里，没有一条会静默产出坏数据**；唯一「不响」的是 `alembic downgrade` 的 `DROP TABLE` 语义（S4）。

### 5.4 半假散文重扫（⚠️ 换一套判据：不用关键词，按「今天为真的事实」反查每一句现在时断言）

**四个面逐个扫。** 判据是本波**自己量出来的今天的事实**（§②/§③ 那些实测值），不是 Task 6 那 24 条断言形状。

| 面 | 扫法 | **结果** |
|---|---|---|
| **`frontend/dist`（发给甲方的产物）** | 逐文件扫 27 个产物文件，用**改前原文**当禁用串、用**改后新散文**当正控 | ✅ **0 处假话**。`任何教职` **0** 命中、`都读得到全校名册` **0** 命中、`****-**-**` **0** 命中；正控全在：`自助绑定的验身材料曾经等于零` 1、`2026-10-18 起学生那一侧收了一半` 2、`只对管理员成立` 1、`教师那一侧一格没收` 1、`弱材料` 1（⚠️ 那一句由紧跟的追加句限定，见 §4.1.4） |
| **`/openapi.json`** | 亲量字节与 sha + 五格 + `StudentRead.birth` 的 schema | ✅ **455 301 B / `7D75650765F2B65D`**，与 Task 6 改完 4 句 `description` 之后的值**逐字相同** ⇒ 那 4 句改写今天仍在位、没有回滚；`StudentRead.birth` 仍是 `{"format":"date","title":"Birth","type":"string"}`（⚠️ 值级变形不改契约面，与 §8 那半句裁定相符） |
| **甲方试用说明书（179 行）** | 把 §6 的 8 条须知与 §4 的 4 条路线里**每一句含数字或含否定的现在时断言**逐个对本波实测值 | ✅ **0 处假话**（逐条见下） |
| **README（208 行）** | 只核了它指向唯一所有者的那几格（16 条路由 / 演示账号 / 口令所有者） | ✅ 「16 条路由去哪儿看」那节**刻意不抄清单**、只指 `frontend/src/router/index.ts` 与 spec §13.6 ⇒ 结构上不会变假；⚠️ 本波**没有逐行**扫 README 全文（见 §⑩） |

**说明书逐条对账（本波实测值 vs 说明书那一句）：**

| 说明书那一句 | 本波实测 | 判定 |
|---|---|---|
| §4 路线三 1：「**23** 个资源一格一格列着…只有 **9** 个可写，其余 **14** 个只读」 | 亲量 `catalog.RESOURCES`：`len=23`、`writable=9`、`read-only=14` | ✅ 全真 |
| §4 路线三 2：「分页表『1–20 / **共 60 行**』，列是 id / 学号 / 名称 / 性别 / 年级 / 院系 / 操作」 | `pe_trial.db` `student` = **60** 行；`student` 的列逐字是 `id, student_no, name, sex, birth, department, grade, password_hash, password_bound_at` ⇒ 页面那 6 列**逐格对得上**（`birth` 不在列表页上，符合 Task 5 的收窄） | ✅ 全真 |
| §4 路线三 4：「**2026-10-17 起**这一页多了一个『写 / 读』的切换（**不新开页面**，故第 5 节那张路由表一个字都没变）」 | `routes` 数组 **20** 项、smoke 第 14 步 **16** 条路由，与基线逐字相同；`/api/read-audit-logs` 住在**既有**的 `app/api/routers/audit.py` 里 ⇒ router 模块数仍是 **8** | ✅ 全真 |
| §4 路线三 6：「明文形状是 `16 个字符` + 一个点 + `32 个字符`…库里存的是校验值，事后**读不回来**…台账里**没有**明文那一列」 | 亲量签发出来的明文 = `L5u4xSBNxGDojCtw`（**16**）`.` `mERhtd-GJegOvaHm5C0rxlB6FsFFI6M7`（**32**）；台账 7 格 = 9 列减 `token_id` 与 `token_hash`，**不含明文** | ✅ 全真（**逐字符数都对**） |
| §4 路线三 6：「⚠️ **试用库上这一格签发不出去**：63 个账号（60 学生 + 3 教师）都已经绑好了口令」 | 亲量 `pe_trial.db`：`student` **60/60** 已绑定、`teacher` **3/3** 已绑定、`bind_token` **0** 行；且亲验签发端点对已绑定账号回 **409** | ✅ 全真（**这一句是本波独立量出来的，逐字相符**） |
| §4 路线四 5：「课次 #1 是 `4C51674D`、课次 #3 是 `D2476ADA`」 | 亲量 `pe_trial.db.class_session`：#1 `rpe_token='4C51674D'`、#3 `'D2476ADA'` ⇒ ⚠️ **甲方 09:39–09:51 那两次 `POST /api/class-sessions/1/open-rpe` 没有把口令换掉**（那一端点是「读回既有口令」） | ✅ 全真（**这一格最容易随真人试用变假，本波专门查了**） |
| §6 ②：「学生那一侧的出生日期对**普通教师**已经掩掉…教务干事（管理员）照旧读得到完整值…教师那一侧（工号 + 姓名）对任何在册教职**仍然全部可读**」 | 教师 T0001 打 65 个 GET：**0** 条出现真出生日期、名册 60 行全 `****-**-**`；管理员 T0003：`/api/students` 与 `/api/students/{id}` 出现 **51** 个真值；`/api/teachers` 对 T0001 是 **200** | ✅ 全真（三半句逐格都验过） |
| §6 ②：「`PE_ALLOW_SELF_BIND` 缺省是 `1` = 开…关掉之后 `/bind` 页的老一档会被拒绝」 | 未设 → 自助绑定走到业务判定（409 已绑定）；`=0` → 两个自助端点各 **403** 且 message **点名那个变量与它的缺省值**；`=yes` → `create_app` **抛 ValueError** | ✅ 全真 |
| §6 ②：「令牌**没有撤销**功能，发错了只能等它 **7 天**后自己过期」 | `BIND_TOKEN_TTL` 实测签发 → 到期恰好 **7 天**；过期档报文自陈「过期令牌不能续期，而本波**没有**撤销端点」 | ✅ 全真 |
| §6 ③：「只记**敏感读**（不记健康探针、参考数据一类）；**匿名读不记**；**已登录**的人试了一次范围外的读（会被拒）**照样记一行**」 | 活库 146 行：`subject_kind` = teacher 126 / student 20 / **anonymous 0**；`status` = 200×145 / **403×1**；落在「18 条不记」那些模板上的行 = **0** | ✅ 全真（三格逐个都在实物上验到） |
| §6 ③：「那两张表**只读**，连改都改不了」 | openapi 的 `/api/audit-logs` 与 `/api/read-audit-logs` **各只有一个 GET**，没有 POST/PATCH/DELETE；两者都**不在** `catalog.RESOURCES` 的 23 行里（守卫 `assert len(RESOURCES)==23` + 「里面没有 `audit-logs`」） | ✅ 全真 |
| §6 ⑤：「连错 **5** 次锁 **15** 分钟（首次绑定那一侧是 **3** 次锁 **60** 分钟）」 | 亲量 `DEFAULT_BIND_MAX_FAILS=3` / `DEFAULT_BIND_WINDOW_MINUTES=15` / `DEFAULT_BIND_LOCK_MINUTES=60`；⚠️ 而**行为**上也验到：错秘密连发 6 次，`login_attempt` 上**恰好 3 行**、第 4 次起时延从 ~190 ms 掉到 ~20 ms | ✅ 全真 |
| §6 ⑥：「`/docs`（与 `/redoc`、`/openapi.json`）任何人都能打开」 | 亲量 `/openapi.json` 匿名可取（本波那份 455 301 B 就是进程内 dump 的，而 `test_main.py` 那条守卫钉的是「三档 `PE_TRIAL` 下逐字节相同」+ 匿名 GET 那一条） | ✅ 全真 |
| §6 ⑦：「**四张表**只增不减（清理作业**有了、而它不会自己跑**）…四个保留窗口各有一个**下界**…`-Keep N` 删之前会把要删的每一份连字节数与校验值逐个打印出来、删完再复核…清理**不会**替你自动备份」 | 四张表 = `login_attempt` / `user_session`（**只清已过期**）/ `audit_log` / `read_audit_log` ✅；窗口 7 / 30 / 365 / 90 天，下界亲验（M7-8 给 0 天 → `RetentionError`）✅；`-Keep` 逐个打印 + 复核 ✅；「不会自动备份」那段告示亲验在 ✅；`schtasks` 0 命中 ✅ | ✅ 全真（**逐格都验过**） |
| §6 ⑦：「备份**缺省**是明文的（设一个口令就加密）…恢复时同一个口令要在；改前那些明文备份**照样**恢复得了…口令**丢了那一份就打不开**（不做密钥托管、也没有后门）」 | 缺省产物头 `SQLite format 3\0`、设口令后 `PEBACKUP` ✅；用**明文档**在 `PE_BACKUP_KEY` **在**的情况下恢复 → 成功，且脚本主动说一句「它是在设那个变量之前做的」✅；错口令恢复加密档 → 退出码 2、目标库 sha 未变、`--no-verify` 跳不掉 HMAC ✅ | ✅ 全真 |
| §6 ⑧：「降过权的管理员…**仍然读得到全校名册（含出生日期）**（⚠️ 这半句只对他那张还没重登的**管理员**会话成立…）」 | ⚠️ 这一句正是 §10.6 第 2 条补上的限定句。本波实测：`students` 与 `teachers` 两行的 `read_scope` 是 **`staff`**（亲量分布 `None:7 / staff:2 / staff_taught:13 / staff_taught_section:1` = 23）⇒「任何在册教职」那一档**确实**是这两行的判据，而 `birth` 只对 `role='admin'` 给全值 ⇒ **限定句是必需的、且今天全真** | ✅ 全真 |
| §5：「四条路线走过了 **16** 个页面里的 **15** 个」/「完整的 **16** 条路由清单」 | `routes` 数组 **20** 项；smoke 第 14 步的 `ROUTES` 就是那 16 条（本波亲读到它的字面住址 `smoke.mjs:2756`） | ✅ 全真 |

⇒ **发给甲方的产物（`dist` + `/openapi.json` + 说明书）今天 0 处假话**，Task 6 那一句本波**独立复现为真**。

#### ⚠️ 而换一套判据之后，本波在**发给甲方的另一份产物（可分发包里的 spec）**上扫到了 **2 处**

| # | 住址 | 那一句（逐字） | 今天的实物 | 严重度 |
|---|---|---|---|---|
| **P-1** | spec **§1.2 第 9 条**（`Document/2026-09-28-…spec.md:58`） | 「**过期/吊销的会话行不会自己消失** \| 原型**不做清理任务**（那需要一个定时作业与一份运维口径）…生产要补一个清理任务。」 | 🔴 **两句都反了**：Plan 08 Task 2 做了 `backend/scripts/retention.py`（清 `user_session` 的**已过期**行，窗口 7 天）+ `register_retention_task.ps1`（打印计划任务命令）+ spec **§13.24**（运维口径）。⚠️ 而**同族的另外两处都改了**：§13.15 **第 6 条**已划掉并写了「✅ **已收**」，§15 **~~B2~~ / ~~B3~~** 已划掉 ⇒ **spec 自己与自己打脸** | **S2** |
| **P-2** | spec **§13.15 第 3 条**（`…spec.md:4778`） | 「新表 `read_audit_log`（**第 29 张**）记**敏感读**（**64** 个 GET 里被归为敏感的 **46** 个）」+ ✅ 栏里「那 **46** 条全部要身份」 | ⚠️ 今天逐字是：`read_audit_log` 是**第 30 张**表之外的第 29 张（`bind_token` 是**第 30** 张，Task 4 加的，而**同一份 §13.15 的第 4 条**已经写着「新表 `bind_token`（**第 30 张**）」）、GET 是 **65** 个、敏感读是 **47** 个。⚠️ 本波亲量：表数 **30**（`sqlite_master` **31**）、GET **65**、`EXPECTED_SENSITIVE_COUNT = 47` | **S3** |

⚠️ 两处的共同形状与 §10.6 那一条**逐字同族**：「每次收窄一个可见面 / 每加一张表，所有描述它的散文都要跟着改」。⚠️ 而 §13.15 那一节的抬头逐字写着「**给甲方念的那一页**」，且 spec 是**进可分发包**的（§15 G10 / G18 都在说这件事）⇒ 它算「发给甲方的产物」。

#### ⚠️ 另外扫到的一批**开发者面**过期计数（一律 S4，如实记，不建议逐个改）

本波用 10 组正则扫了 **247 个**源文件（`backend/app|scripts|tests`、`frontend/scripts|src`、`scripts`、`Document`、`README.md`；排除 `__pycache__` / `node_modules` / `generated` / `dist`）：

| 过期串 | 命中 | 今天的真值 | 典型住址 |
|---|---|---|---|
| 「**64 个 GET**」 | **6** | 65 | `scripts/retention.py:211`（⚠️ **随包发出去的源码注释**）· `tests/api/test_read_audit_api.py:275/289` · `frontend/src/views/admin/AuditLogList.vue:16`（⚠️ 构建时被剥掉，本波亲验 `dist` 里 0 命中）· spec `:2991` |
| 「**46 个**（敏感读）」 | **12** | 47 | 同上 + `app/db/models/auth.py:439`（⚠️ 那一处**自己已经写对了**：「Task 1 实测 46 个敏感读、**Task 4 之后 47 个**」）· `smoke.mjs:1725-1726` · `frontend/src/api/types.ts:514` · spec `:3257/3332` |
| 「**10 个类**」（读审计归类） | **2** | 11 | `app/api/schemas/audit.py:264` · `tests/api/test_read_audit_api.py:320` |
| 「**29 张表**」 | **26** | 30 | `scripts/dump_openapi.py:34` · `tests/api/conftest.py:6/49` · `tests/test_demo_data.py:78` · `tests/db/test_migration_baseline.py` 多处（⚠️ 其中若干是**时点账**，按本仓「历史原文逐字保留」的纪律**不该改**） |
| 「**1370** 条测试」 | **9** | 1774 | `app/main.py:414` · `app/api/deps.py:215` · `tests/test_dependencies.py:13` · `tests/test_main.py:387/553/633` · spec `:2850/2952` |
| 「**1633** passed」 | **6** | 1774 | ⚠️ 全部在**计划文档与 spec 的前置/时点账**里（Plan 08 计划文档 §0 与 §8 各一处、spec 四处），按纪律**不该改** |
| 「**1 428 951** 字符」 | **3** | 1 440 078（工作树 CRLF 档） | ⚠️ spec `:8552` 与 `:8630` **已经自己登记了这一格**（「⚠️⚠️ 续做时实测纠正…差值恰好 = …」）⇒ **本波那一条 R7-S3-1 不是新发现，是独立复现 + 补上根因数字**（差值 **11 127** = `schema.d.ts` 的 CRLF 行数） |

⚠️ **裁定建议**：这一批**不要**在结案波逐个改。理由与本仓既有纪律一致：① 其中相当一部分是**时点账**（「历史原文逐字保留」），改它就是重写绑时点的账；② 会随端点/表数漂的计数**本来就不该写死**（硬规矩 #111，而 `package.json` 的 `//` 键与 §13.15 第 10 条都已经用「**删数而不是改数**」处置过同族问题）；③ 而它**已经是一条在册台账**：§15 **F6**「散文与注释里的 openapi 计数会随端点增删而漂，而今天没有守卫钉它们」。⇒ 结案波只需要做 **P-1**（S2）与 **P-2**（S3）两处，其余**引用 F6** 即可。

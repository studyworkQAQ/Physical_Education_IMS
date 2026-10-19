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

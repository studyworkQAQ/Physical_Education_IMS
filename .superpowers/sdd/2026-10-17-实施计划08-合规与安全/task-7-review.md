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

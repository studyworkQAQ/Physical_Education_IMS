"""Plan 03 Task 1 结案：账本追加 Ruling 4（顶回 3 + 补充 1 + 偏离 6 的裁定）+ Ruling 5（评审席的调整）。"""
from pathlib import Path

P = Path(__file__).with_name("progress.md")
b = P.read_bytes()
t = b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"[before] bytes={len(b)} lines={t.count(nl)}")

BODY = """

---

## ✅ Task 1: complete (commits 69b4218..2832a27, 1 fix round)

**交付**：`59eb771`（`create_app` + `deps` + `errors` + `conftest` + `test_main.py` + `test_scope.py`，7 files / 1123 insertions）、`2832a27`（守卫加 `api` 层 + `.gitignore` 加 `pe_demo.db` + Step 4 冒烟取证）。

**验收（控制者本机亲跑复核，探针 `t1_probes/_verify.py` 已入库）**：
- 全量 **807 → 824 passed**（+17 = `test_main.py` 10 + `test_scope.py` 5 + `test_layering.py` 2）；带 `--cov` **823 passed, 1 skipped**
- `app/domain/` 四格 **996 / Miss 0 / 288 / BrPart 0 / 100% 逐字未变**（本 Task 不加 domain 代码，`app/domain/` 一个字节没动）✓
- **扫描面 35 → 38**（pipeline 8 + db 11 + domain **16** + **api 3**）；`backend` 全树 `.py` = **90**
- `app/api/` 今天 **3 个文件**（`__init__.py` 0 B、`deps.py` 9 400 B、`errors.py` 8 157 B）—— File Structure 列的 18 个是**计划结束时的形状**，Task 3–8 才建满
- **反向依赖亲扫**：`app/{domain,db,pipeline,seed}` 下**没有任何文件**含 `app.api` ✓
- **`/api/health` 响应原文** `{"status":"ok","tables":18,"students":0}`；`/openapi.json` 200（`paths=['/api/health']`）、`/docs` 200、`/redoc` 200、CORS 预检 200（`allow-origin: *`、`allow-headers: X-Student-Id`）、`/api/nope` → 404 `{"error":{"code":"not_found","message":"Not Found","detail":null}}`
- **禁区**：`backend/pe.db` **不存在**（连 `-journal`/`-wal`/`-shm` 四个全 False）✓；`pe_demo.db` 建出 172 032 B 且被 `.gitignore:38` 挡住（`git check-ignore -v` 亲验）✓；三个指纹 `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` **逐字不变**、CRLF 均 0；`git diff 69b4218 HEAD -- backend/data` **为空**；`data/seed/` 0 文件
- **签名亲验**（`inspect.signature`，与报告逐字一致）：`create_app(*, db_url: str | None = None) -> FastAPI`、`get_db(request: Request) -> Iterator[Session]`、`current_student(x_student_id: int | None = Header(None)) -> int`、`current_teacher(x_teacher_staff_no: str | None = Header(None)) -> str`、`require_scope(session, student_id: int, requester_id: int) -> None`；`Page.limit: int = 50 [Ge(1), Le(200)]`、`Page.offset: int = 0 [Ge(0)]`
- **偏离 ① 亲验成立**：`tests/` 下 34 个 `.py`、`__init__.py` **0 个** → 不建 `tests/api/__init__.py` 是对的（派单自己给的就是条件分支）
- **作用域闸门三条测试**（Review Focus 第 1 条）：`test_missing_identity_header_is_401`、`test_a_student_cannot_read_another_students_row`、`test_require_scope_is_a_pure_gate`
- **实现者自证的「新守卫有牙」三条探针**：G1（`_is_api_allowed` 换成裸 `startswith` → 判定矩阵红 3 格）、**G2（`app/domain/` 落一行 `from app.api import deps` → 新方向守卫红 **且** purity 白名单守卫也红 —— 这是坑 #3 的直接答案：不是误判，是正确地抓到了）**、G3（`app/api/` 落一行 `from app.seed.generate import …` → 方向守卫与既有 seed 守卫都红），还原后 `tests/architecture` 8 passed

### Ruling 4 — 实现者顶回 3 处 + 补充 1 处，**全部采纳**（Plan 03 的第 1–4 次顶回；累计 Plan 02 的 25 次 → **29 次，29 次都对**）

**顶回 1（采纳）**：`get_db` **必须多一个 `request: Request` 参数**。理由成立：无参版本只能从**模块级全局**取引擎 → 同进程两个应用会共用后建的引擎，而 `conftest` 的 `app` 夹具是 **function 级**（每个测试一个新 app、新引擎）。**对调用方零代价**（端点里仍写 `Depends(get_db)`，FastAPI 自己注入 `Request`）。控制者亲验签名确实是 `get_db(request: Request)`。

**顶回 2（采纳 → 控制者错误 #1，Plan 03 编号）**：**计划的三条要求互相不可能同时成立。** ① `db_url` 缺省取 `DEFAULT_DB_URL`；② Step 4 用 `uvicorn app.main:app`（模块级 `app` 由 `create_app()` **无参**建出，**命令行上没有任何位置能塞 `db_url`**）；③ 必须显式传 `db_url`、不落缺省。而 **`DEFAULT_DB_URL` 实测逐字就是 `sqlite:///…/backend/pe.db`**（控制者亲验）→ 三条凑一起的唯一结果就是 **Step 4 一跑就破 `pe.db` 禁区**。
实现者的处置：**加 `PE_DB_URL` 环境变量覆盖口子**（`DB_URL_ENV_VAR = 'PE_DB_URL'`），`create_app` 的取值序是「显式 `db_url` > 环境变量 > `DEFAULT_DB_URL`」，Step 4 的命令变成 `$env:PE_DB_URL = python -c "from app.main import DEMO_DB_URL; print(DEMO_DB_URL)"` 再 `python -m uvicorn app.main:app --port 8000`（**计划原命令逐字未变**）。
**⚠️ 控制者的坑 #1 嗅到了这个冲突**（逐字写着「起 uvicorn 时**必须显式传 `db_url`**，不能让它落到 `DEFAULT_DB_URL`」）**却没给「怎么传」的机制** —— 这是 Plan 02 控制者错误 #151 的同型（**指出了问题而没给出路径，等于把矛盾交给实现者**）。**→ 补硬规矩 #98：派单里写「必须 X、不得 Y」时，若 X 与 Y 在既有机制下不能同时成立，必须同时给出「怎么做到 X 而不 Y」的机制；给不出就是计划有洞，不是实现者的问题。**

**顶回 3（采纳 → 控制者错误 #2）**：**S6 的「下界一次性抬到位」不能按字面读成「抬到计划结束时的值」。** 控制者的原文是「抬的时候要给足余量（例如 domain 会从 16 涨到 17、`app/api/` 本计划要建约 15 个 `.py`）」—— **而「给足余量」与「下界」方向相反**：真按 53/56 写，Task 1 当场就红、并一路红到 Task 8。
实现者的处置：**抬到「今天已成立的地板之和」= 18**（pipeline 5 + db 5 + domain 5 + api 3；**5 沿用 `test_domain_purity.py` 已定下的那个数、不另发明**，api 的 3 是本 Task 实测），而「后面 8 个 Task 不再动它」用**单调性论证**兑现（剩下 8 个 Task 只增文件、不删不合并）。**并顺带核准了控制者数的另一个错**：计划 File Structure 逐行数出来 `app/api/` 是 **18** 个 `.py` 而不是派单说的「约 15」，故建满时聚合值是 **56** 不是 53。
**⚠️ 它还刻意没动 `>= 40` 与 `>= 16` 两条**，理由三条都成立：它们数的是 `backend/` 全树（实测已长到 90 / 36，两条都仍成立）、与「加一层」无关；`api` 层全用绝对导入故 `relative_seen` 一格没涨；**更要紧的是它们在 `test_domain_purity.py` 里各有一份镜像，只改一边破坏硬规矩 #51**，而 purity 不在计划的 Modify 清单里。

**补充 1（采纳）**：`errors.py` 在计划枚举的 4 条映射（`ValueError`→422 / `IntegrityError`→409 / `NoResultFound`→404 / 其余→500）之外**多注册了 `HTTPException` 与 `RequestValidationError` 两个处理器**。理由成立：**否则「统一响应形状」不成立** —— 403 / 401 / 404 / 请求校验 422 会仍是 FastAPI 缺省的 `{"detail": …}`，而这四个恰恰是 CRUD API 最常见的错误。**计划那句「统一响应形状 `{"error": {"code","message","detail"}}`」与它自己列的 4 条映射自相矛盾**（4 条盖不住「统一」这个词）→ **控制者错误 #3**。

### 实现者自查出的一处假绿（fix round 1，控制者认为这是本 Task 最有价值的一件事）

**Windows 上 `str(engine.url)` 把盘符的 `:` 编码成 `%3A`**，于是 `assert str(engine.url) != DEFAULT_DB_URL` **恒真** —— 它证明的不是「没落到缺省库」，只是「盘符被编码了」。**是红的那条把绿的这条一起暴露出来的**；三处一律改成 `make_url(...)` 结构化比对。
**⚠️ 这正是硬规矩 #92/#94 那一族的第 5 个成员**（#92：要求一条测试变红前先论证破坏在结构上可达；#94：说「某个分支可达」时要给出「它会被求值成真的那组输入在哪」）。**本次的形状是第三种：一条测试恒真，因为它比的是两个经过不同编码的字符串。**
**→ 补硬规矩 #99：断言「A 不等于 B」或「A 等于 B」时，若 A 与 B 任一侧经过了序列化/编码/格式化（`str(url)`、`repr()`、`json.dumps`、`os.fspath`），必须先证明这个变换是**单射**——否则断言可能在比较两个编码产物而不是两个值。URL、路径、日期是三个高发区。** 依据：本次的 `%3A`；Plan 02 的 #153（`read_text()` 把 `\\r\\n` 翻成 `\\n`）是同一族在「读取」那一侧的发作。

### 6 处偏离派单字面：全部追认

① `tests/api/__init__.py` **没建**（控制者亲验 `tests/` 下 34 个 `.py`、`__init__.py` **0 个** → 按派单自己的条件分支不建）；② `conftest` 提供 `app`/`engine`/`client` **三个**夹具而非一个 `client`（`test_scope` 要在发请求前插两行学生，而 `StaticPool` 下那个 Session 必须关掉）；③ 计划说 6 条测试、实际 **15** 条（多出的 9 条各覆盖一个「计划写了但没人验」的性质；**点名的 6 条一条没少、名字未改**）；④ Step 3 的反向断言从「domain + db」扩到「`SCANNED_DIRS` 减 api」（**含 pipeline**，覆盖面更大）；⑤ 简报写基线 `5b4a10c`、派单写 `69b4218`，**两个 rev 都跑了**（控制者承认这是自己的不一致：简报是扫描前抽的）；⑥ 报告不在这 2 个 commit 里（照 Plan 02 惯例由控制者提 `docs:`）。

### 待清扫（推 Task 9）：**6 条**，Critical 级遗留 **0** 处

其中两条值得先记：① `test_layering.py` 里 `>= 40` / `>= 16` 的**注释实测值已陈旧**（写着 69→90、18→36，绑的是 Plan 02 Task 4 的时点但没标注）；② **`StaticPool` 没有 `checkedout()`**（本机实测 `AttributeError`；今天两条用到它的断言都跑在磁盘 URL 的 `QueuePool` 上，故撞不上 —— **但它是一颗等着被踩的雷**，Task 3 的 CRUD 测试全跑在内存库上时会撞上）。

### Ruling 5 — Plan 03 的评审席调整（控制者裁定，代价写明）

**裁定**：Plan 03 的「独立评审者」席位**折进控制者亲验**，不再每个 Task 派一个 reviewer subagent。计划 Ruling 1 原本把「每个 Task 一轮评审」列在**保留**项里，**本条是对它的收窄**。
**理由**：用户两次裁定「只要能运行起来的原型系统就好」，而 Plan 02 的实测成本是**每个 Task 一轮评审 = 一次完整的 subagent 往返**（9 个 Task 共 10 轮 fix round、25 次顶回），其中相当比例花在文档自洽上。
**代价（必须写明，不许美化）**：**控制者亲验抓不到「控制者自己规定的东西是错的」这一类**——而 Plan 02 的 25 次顶回里**全部 25 次都是这一类**（#151「声称已改而未改」、#156「把可求值讲成会命中」、#154「要求一条结构上不可能变红的测试」）。**独立评审者是唯一能抓到它的席位。**
**缓解措施（三条，都要执行）**：① **实现者的每一处顶回一律先假定成立**，控制者必须**独立重导出**它的依据才能裁定（本 Task 三条都重导出了：`DEFAULT_DB_URL` 亲验确实是 `pe.db`、`Page` 的约束亲验、`tests/` 下 `__init__.py` 数亲验为 0）；② 每个 Task 的派单里**必须逐字写「若你认为本派单某条决定是错的，顶回来」**并给出 Plan 02 的顶回战绩（29/29）；③ **全分支终审照旧派独立评审者**（技能要求的最强模型那一席不省）。
**⚠️ 若某个 Task 的实现者顶回 0 处，控制者要在账本里写明「本 Task 无顶回」并**加倍**亲验**——29/29 的命中率意味着「0 处顶回」更可能是派单太粗、实现者没读出来，而不是计划真的对。

**下一步**：抽 `task-2-brief.md` → 派实现者（7 张表 + 演示数据）。
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
SENT = "Task 1: complete (commits 69b4218..2832a27"
assert SENT not in t, f"{SENT!r} 已存在"
P.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = P.read_bytes().decode("utf-8")
print(f"[after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)} "
      f"CRLF={c.count(chr(13)+chr(10))} LF={c.count(chr(10))}")
for k in ("Ruling 4", "Ruling 5", "硬规矩 #98", "硬规矩 #99", "控制者错误 #1", "控制者错误 #3", "824 passed"):
    print(f"  {k}: {c.count(k)}")

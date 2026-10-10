"""Plan 03 Task 9 结案（含控制者错误 #38：第 6 次探针工具选错）+ commit。"""
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LEDGER = HERE / "progress.md"
b = LEDGER.read_bytes()
t = b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"[ledger before] bytes={len(b)} lines={t.count(nl)}")

BODY = """

---

### ⚠️ 控制者亲验跑出的一处「不符项」经复核是**探针工具选错**（控制者错误 #38，本计划第 6 次）

`_t9_close.py` 的第 4 节报了两条 ⚠️：「`demo.ps1` 含禁区命令 `seed.generate`（2 处）与 `pipeline.backfill`（1 处）」。按硬规矩 #109 用第二个独立工具（`Grep` 带上下文）复核，**坐实是假发现**：

那些字样**只出现在脚本自己的 docstring 里、用来解释「为什么本脚本一条 `python -m …` 都没有」** —— 逐字是「⚠️ **一条 `python -m …` 都没有**：`app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` 三个 CLI 的 `main()` 各自把缺省值写死在**两个禁区**上（`backend/data/seed/` 与 `backend/pe.db`）。故本脚本一律调 `scripts/demo_bootstrap.py`，那里面是 import 函数 + 显式传路径」。另一处 `pe.db` 的命中是脚本**自己的禁区复核输出行**（`Write-Host "   禁区复核：backend\\pe.db 不存在、backend\\data\\seed\\ 仍为 0 文件 ✓"`）与两个守卫变量（`$ForbiddenDb` / `$ForbiddenCsv`）。

**⚠️ 这与 Task 5 结案时那次假发现（`'顺序今天不承重' in ri` 匹配到的是那句更正说明里对旧文本的引用）**完全同形**：谓词匹配到了「对某物的提及」，而控制者把它当成了「某物本身」。** 这是硬规矩 #109 立的理由，而它**第 2 次生效**（第 1 次是 Task 5 的 include 顺序）。
**→ 控制者错误 #38。⚠️ 本计划的 6 次探针工具错逐条**：#12（文本计数核一张数据驱动的表）、#22（`callable()` 把 Pydantic 模型类当函数）、#24（`str.find()` 量到 import 行的字母序 + 子串匹配到对旧文本的引用，**一次两处**）、路径深度错 **3 次**（`t3_probes` / `t4_probes` / `t6_probes`，每次都靠 `assert BACKEND.is_dir()` 当场抓住）、#38（本次）。
**→ 硬规矩 #109 扩写：谓词匹配到「文本里出现某个串」时，必须再问一句「这是**它本身**，还是**对它的提及**（docstring / 注释 / 更正说明里的引用 / 守卫变量名）」。判据是看命中行的上下文，不是看命中数。** 依据：#24 与 #38 是同一条谓词错误的两次发作。

**⚠️ 顺带核到实现者做得比派单要求的更多**（值得记）：`demo_bootstrap.py` **自带两道前置守卫** —— `--csv-dir` 撞上 `backend/data/seed` 或 `--db-url` 以 `pe.db` 结尾**都当场 `SystemExit`**；`demo.ps1` 还**自己印一行禁区复核**。**派单只要求「第一步删掉旧的 `pe_demo.db`、显式设 `PE_DB_URL`」，而它把禁区做成了脚本自己会拦的东西** —— 这与 Task 1 把 `api` 层预先加进守卫 allow-list、Task 8 主动加 `schemas/dashboard.py` 是同一种形状：**实现者在「满足派单」之外多做的那一格，往往是把一条纪律变成机器会拦的东西。**

### Task 9 亲验的其余各节全部通过 ✅

- 全量 **1244 passed**（控制者本机亲跑，121.79 s）
- 表数 **25**；扫描面 **60**（pipeline 10 + db 11 + domain 18 + api 21）；**`/api/` 路径模板 63、操作数 91、挂 `security` 的 18**；`/api/pipeline/run-daily` **在线**
- **黄金用例 14 个**（控制者亲验；⚠️ 顶层键是 `['_meta', 'input', 'expected']`，**用例列表在 `input` 那一格**，控制者第一版探针假定了键名叫 `cases` 故数出 3 —— **这是本轮的第 5 次探针工具错，与 #38 同一次跑出**）
- **`golden_cases.json` 51 619 B / CRLF 959 / bare LF 0**；as-is 指纹 **`39FC9C29D9106C47`**、CRLF→LF 指纹 **`9FB1C619F896D418`**（两个都与实现者报的逐字相同）
- **四个既有指纹逐字不变**；`git diff cf9ad7a HEAD -- backend/data` **为空**；`pe.db` **不存在**；`data/seed/` **0 文件**
- **标准化得分的单一所有者**：AST 亲验 `shuttle_percentile`（`app/domain/report.py:599`）与 `mini_test_scores`（`:654`）**各只有一份定义、都在 `app/domain/report.py`** ✅（派单说的「定义份数 == 1」是「**一个住址**」，而那一个住址里有**两个**函数定义，故守卫断言 2）
- **Ruling 20 的事实控制者用 `openapi()` 独立复核坐实**：`POST /api/class-sessions` 的 `security` **为空（匿名可写）**；而**挂了 `security` 的 9 个 POST 端点全部是特例端点**（`open-rpe` / `rpe-records` / `training-logs` / `mini-tests/batch` / `overrides` / `regenerate` / `alerts/…/handle` / `notifications/…/read` / `pipeline/run-daily`），**泛型 CRUD 的写入侧一个都没有** → 裁定归 Plan 04 的第一件事（见 Ruling 20）

**Task 9 结案口径**：**0 fix round**（唯一的「不符项」经查是控制者的探针错，不构成发现）。

---

## 🏁 Plan 03 全部 9 个 Task 完成

| Task | commit 区间 | passed | fix round | 顶回 |
|---|---|---|---|---|
| 1 FastAPI 骨架 + 作用域闸门 | `69b4218..2832a27` | 824 | 1 | 3 |
| 2 反馈与预警的 7 张表 | `bcf3936..fd73788` | 845 | 0 | 3 |
| 3 泛型 CRUD + 23 个资源 | `40a7a0e..e88afaf` | 876 | 0 | 7 |
| 4 处方侧四个特例端点 | `9062b37..95c7f76` | 910 | 0 | 7 |
| 5 §8.1 三源采集七个端点 | `acd3f53..c61dc3c` | 956 | 0 | 8 |
| 6 预警规则（5 条，变异 5/5） | `a8d61b4..caf80c5` | 1026 | 0 | 8 |
| 7 预警落地 + auto 来源 | `6d0c8d2..5fe289c` | 1097 | 0 | 5 |
| 8 班级周报 + 大屏/首页（变异 24/24） | `6127fc7..d100ff5` | 1225 | 0 | 4 |
| 9 GC14 + 端到端冒烟 + demo.ps1 | `cf9ad7a..4a8b792` | **1244** | 0 | 6 |

**最终状态**：**1244 passed**；`app/domain/` **1268 stmts / Miss 0 / 376 branch / BrPart 0 / 100%**；**25 张表**；**63 个 `/api/` 路径模板、91 个操作**；扫描面 **60**；**14 个黄金用例**；五个指纹逐字不变；`pe.db` 不存在、`data/seed/` 0 文件。
**顶回累计 73 次、73 次都对**（Plan 02 的 25 + Plan 03 的 48）；**控制者错误累计 38 条**；**硬规矩从 #94 增到 #115**；**Ruling 1–20**。

**下一步**：全分支终审（**Ruling 5 保留的那一席独立评审者**）→ `finishing-a-development-branch` → 写 Plan 04（Vue3 前端）。
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
SENT = "Plan 03 全部 9 个 Task 完成"
assert SENT not in t, f"{SENT!r} 已存在"
LEDGER.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)}")
for k in ("控制者错误 #38", "1244 passed", "73 次", "Plan 03 全部 9 个 Task 完成", "硬规矩 #109 扩写"):
    print(f"  {k}: {c.count(k)}")

print("\n[git] 提交")
subprocess.run(["git", "add", ".superpowers/sdd/2026-10-08-实施计划03-反馈预警与CRUD-API层/"],
               cwd=str(ROOT), check=True)
r = subprocess.run(["git", "commit", "-m",
                    "docs(sdd): Plan03 Task 9 结案 —— 1244 passed，14 个黄金用例，端到端冒烟八步走通，demo.ps1 真机跑通；"
                    "Plan 03 的 9 个 Task 全部完成（Ruling 19/20 + 硬规矩 #115 + 控制者错误 #35-#38，顶回累计 73/73）"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
out = (r.stdout or r.stderr).strip().splitlines()
print("  " + (out[1] if len(out) > 1 else out[0] if out else "(无输出)"))
r = subprocess.run(["git", "log", "--oneline", "-1"], cwd=str(ROOT), capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print(f"  HEAD = {(r.stdout or '').strip()}")
r = subprocess.run(["git", "status", "--short"], cwd=str(ROOT), capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print(f"  git status -> {(r.stdout or '').strip() or '（干净）'}")

"""Ruling 158：Plan 02 合入 main 并推送（用户裁定）。追加到 Plan 02 的账本末尾。"""
from pathlib import Path

P = Path(__file__).with_name("progress.md")
b = P.read_bytes()
t = b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"[before] bytes={len(b)} lines={t.count(nl)}")

BODY = """

---

### ✅ Ruling 158 — Plan 02 合入 `main` 并推送（用户裁定 2026-10-08）

**用户裁定（AskUserQuestion，两问都选推荐项）**：
1. Plan 02 的 75 个 commit 怎么处置 → **「合进 main 并推送，再开 Plan 03 分支」**
2. Plan 03 的范围 → **「照原裁定：反馈 + 预警 + 全系统 CRUD API」**（前端仍留 Plan 04）

**处置与亲验（全部控制者本机实跑）**：
1. **合入方式 = fast-forward**（`git merge --ff-only feature/plan-02-prescription-engine`）。**与 Plan 01 同口径**——Plan 01 也是 ff 合入（`main` 与 `feature/plan-01-data-foundation` 今天都停在 `1355541`，没有 merge commit），故 Plan 02 也不造 merge commit，历史保持线性。
2. **合入前**：分支领先 `main` **75** 个 commit、落后 **0**，工作树干净。
3. **合入后在 `main` 上复跑全量**：`cd backend; python -m pytest -q` → **807 passed in 107.31s**（与特性分支上的 807 逐字一致）。⚠️ 这一步不可省——`git checkout` 会按 `core.autocrlf` 重写工作树（硬规矩 #46），而 `backend/data/` 的三个指纹是按字节钉的。
4. **合入后复核三个指纹**（在 `main` 上）：CSV `D2C8E539E2FA0029`、`exercises.yaml` **`5394B37F01DAC9AC`**（Task 9 改过的新值）、`exercise_equivalence.yaml` `822CB86A5E998301` —— 三个都与测试里的常量一致（807 passed 已经包含那三条指纹测试，故这一步是双保险）。
5. **推送**：`git push origin main` → `1355541..a5f16b1  main -> main`；`git push -u origin feature/plan-02-prescription-engine` → `* [new branch]`，并设好 upstream。**与 Plan 01 同口径**（`origin/feature/plan-01-data-foundation` 也留在远端）。
6. `main` 与 `origin/main` 现在都在 **`a5f16b1`**。

**⚠️ 未做的事（刻意）**：没有删特性分支（Plan 01 的也没删）；没有 force push；没有动 `git config`。

**Plan 03 的入口状态**：
- 从 `main`（`a5f16b1`）开新分支
- **807 passed**、`app/domain/` **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**、**18 张表**、`app.domain.prescription.__all__` **51**、`_MODELS_PUBLIC_BASELINE` **33**、架构守卫扫描面 **35**
- spec §14 **37 项、无空洞**
- SQLAlchemy **2.1.3**、Python 3.11.1（**无 venv**）、pandas 3.0.6、numpy 2.4.6、PyYAML 6.0.3
- ⚠️ **Plan 02 留给 Plan 03 的 10 条清单在上一节（「🏁 Plan 02 全计划结案」）里**，写 Plan 03 时必须逐条传导（硬规矩 #86）。其中三条最容易漏：**GC14（BMI > 30 的新黄金用例）**、**CRUD 层必须在写入侧复用 `WeeklyFactor` 的 `(0, 2]` 校验**、**`models/feedback.py` 今天是一个 475 B 的空壳**（加表时要改它的 docstring，并遵守 `_MODELS_SUBMODULES` 与 `_MODELS_PUBLIC_BASELINE` 的纪律）。
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
# ⚠️ 哨兵必须带上本节独有的措辞：账本里已有一处「Ruling 158」是**对 Plan 01 的 Ruling 158 的
# 交叉引用**（讲「把别人的 grep 结果写成控制者亲跑」），裸查 "Ruling 158" 会假阳性
# —— 控制者错误 #158：为防重复追加而写的守卫，自己就是一个没验证过的查询（硬规矩 #80/#91）。
SENTINEL = "Ruling 158 — Plan 02 合入 `main` 并推送"
assert SENTINEL not in t, f"{SENTINEL!r} 已存在，勿重复追加"
assert t.count("Ruling 158") == 1, "预期改前恰好 1 处（Plan 01 的交叉引用）"
P.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = P.read_bytes().decode("utf-8")
print(f"[after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)} "
      f"CRLF={c.count(chr(13)+chr(10))} LF={c.count(chr(10))}")
for k in ("Ruling 158", "a5f16b1", "807 passed", "5394B37F01DAC9AC", SENTINEL):
    print(f"  {k[:44]!r}: {c.count(k)}")

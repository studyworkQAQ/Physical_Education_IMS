"""Task 8 结案：账本追加 Ruling 154（顶回 2 处采纳 + 偏离 4 处追认 + 控制者错误 #154）。"""
from pathlib import Path

P = Path(__file__).with_name("progress.md")
b = P.read_bytes()
t = b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"[before] bytes={len(b)} lines={t.count(nl)}")

BODY = """

---

## ✅ Task 8 结案（「本周训练单」读模型 `weekly.py`，spec §8.4）

**fix round 用了 0 轮**（Plan 02 **第四次**零 fix round：Task 3、Task 4、Task 6、Task 8）。**Critical 零遗留。Plan 01 与 Task 5/6/7 的全部既有测试仍全绿。**

### 交付与验收（全部控制者本机亲跑复核，探针 `t8_probes/_t8_verify.py` 已入库）

| 项 | Task 7 结案基线 | Task 8 结案 |
|---|---|---|
| commit | `197147f` | **`cbb61c5`（`weekly.py` + 37 条 domain 测试）→ `eb3de22`（`weekly_factors_of` + 6 条 pipeline 测试 + 公开面）** |
| 全量 `pytest -q` | 750 passed | **793 passed**（+43 = domain 37 + pipeline 6） |
| 带 `--cov` | 749 passed, 1 skipped | **792 passed, 1 skipped** |
| `app/domain/` 覆盖率 | 951 / Miss 0 / 274 / BrPart 0 / 100% | **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**（`weekly.py` 自己 **44 stmts / 14 branch / 100%**） |
| `__all__` | 47 | **51**（+4：`WeeklyFactor` / `WeeklySheet` / `current_week` / `weekly_training_sheet`；**控制者亲验「去掉四个新名后剩 47」成立**） |
| `_PRESCRIPTION_PUBLIC_BASELINE` | 47 | **51**（**两句 `assert len` 都改了**，含失败消息里的「47 个名字」）；`_OWNED_MODULES` 八 → **九**（加了 `weekly`） |
| 扫描面 | 34（domain 15） | **35**（domain **16** + pipeline 8 + db 11） |
| 表数 / `models` 公有面 | 18 / 33 | **18 / 33 均未变**（Ruling 97 完好） |
| 禁区 | 三个指纹 | **逐字不变**；`git diff 43c0db2 HEAD -- backend/data` **为空**；`golden_cases.json` 未改（27 346 B / `8C787701EA70EF90`）；`pe.db` 不存在 |

**控制者亲验的承重结论**（**独立实算，不照抄报告**，硬规矩 #44）：
- `WeeklyFactor` **4 个字段**（`week:int / factor:float / reason:str / source:str`）、`WeeklySheet` **6 个字段**（`week / factor / reasons / sources / sessions / **paused:bool**`）—— **P8-A3 落地** ✓。且 `WeeklySheet` **唯一的 float 字段是 `factor`** → **跨单位的周总量在结构上无处可放**（P8-A1 的要求由类型系统兜住，不只是 docstring）
- **`current_week` 的 6 个边界逐格命中控制者的独立实算**（`generated_on = 2026-03-02`、`microcycle_weeks = 4`）：Δ `+0d → 1`、`+6d → 1`、`+7d → 2`、`+27d → 4`、`+28d → None`、**`−1d → None`（不是 0、不是 1）** —— **P8-A7 落地** ✓
- **跨模块一致性亲跑**：Δ`+27d` → `current_week = 4` 且 `MICROCYCLE_EXPIRED = False`；Δ`+28d` → `current_week = None` 且 `MICROCYCLE_EXPIRED = True`。两格 `(cw is None) == expired` **均为 True** ✓
- **单一所有者亲核**：`triggers._DAYS_PER_WEEK = 7`；`weekly.py` 的代码是 `week = elapsed_days // _DAYS_PER_WEEK + 1`，且 **`if elapsed_days < 0: return None` 排在整除之前**。`'// 7'` 在文件里命中若干处，**全部在 docstring 里**（解释「`.days // 7` 对负数向下取整 → `pkg.weeks[-1]` 会静默取到最后一周」这个危害），**代码里没有第二份 `7`** ✓
- `weekly.py` **27 857 B / 422 行**，import 面 = `{<L1>assembler, <L1>triggers, collections.abc, dataclasses}`，**无违规**（同包兄弟走 level 1 相对导入，与既有口径一致）✓

### Ruling 154 — 实现者第 22、23 次顶回控制者，**2 处全部采纳**；4 处偏离全部追认

**顶回 1（采纳）—— P8-A7 的字面 `7` 会造出第二个住址。** 派单写的是 `week = (as_of - generated_on).days // 7 + 1`，**字面照做就是在 `weekly.py` 里写第二份 `7`**，而 Global Constraint #3（单一所有者）是硬约束。实现者改成 `from .triggers import _DAYS_PER_WEEK`，并指出**这条所有权不是本 Task 新立的**：Task 7 已经在 `valid_to_of` 的 docstring 里写定「『一周 7 天』这条历法事实的所有者是 `triggers._DAYS_PER_WEEK`，在管道层再写一个 `* 7` 就是第二个住址」。跨模块 import 私有名有先例（`models/organisation.py` 的 `from ._shared import _in_domain`）。**代价**：多一条依赖边。⚠️ **实现者同时指出：import 保证不了 `//`+1 与 `>=` 的等价关系**，故 P8-A7 要求的那条跨模块一致性测试**照样写了** —— 控制者亲验它确实存在且成立。**这个「即使消除了字面重复、语义等价仍需独立守卫」的判断是对的。**

**顶回 2（采纳 → 控制者错误 #154）—— P8-A4 要求的 tie-breaker 测试在 SQLite 上结构上不可能变红。** 派单要求「构造两行 `created_at` 相同、`id` 不同的调整，断言顺序由 `id` 决定」。实现者指出：`weekly_adjustment.id` 是 `INTEGER PRIMARY KEY` = **rowid 别名**，表是 B-tree，**全表扫描恒按 rowid 升序** → 删掉 `ORDER BY` 里的 `, id` 之后**数据面那两行断言仍然全绿**。**照字面写只会得到一条恒绿的假守卫。**
处置：数据面照写（**钉契约**，即使今天恒绿）+ **另加一条 SQL 形状断言**（用 `before_cursor_execute` 事件钩子抓真发出去的语句，断言 `ORDER BY` 里 `.created_at` 在 `.id` 之前）。**实现者跑了第 3 条变异（删掉 `, id`）实测：只有 SQL 形状那一条红、数据面两条仍绿** —— 坐实了它的判断。**代价**：绑 SQLAlchemy 的 SQL 渲染文本。
**⚠️ 这与 P6-A1 / 控制者错误 #150 / #152 是同一根因的第 4 次**：派单要求一个**结构上不可达**的东西（那次是「重放翻倍」、上次是「一条不存在的守卫」、这次是「一条不可能变红的测试」）。
**→ 补硬规矩 #92：要求一条测试「在某种破坏下变红」时，必须先论证那种破坏**在结构上可达**。若不可达（唯一约束挡住了、rowid 顺序保证了、类型系统排除了），那条测试就是恒绿的假守卫——要么改判据、要么改成钉契约并**明写它今天恒绿、以及哪一条守卫才有牙**。** 依据：#150 / #152 / #154 与 P6-A1，四次同一形状。

**4 处偏离派单字面：全部追认**
| # | 偏离 | 裁定 |
|---|---|---|
| ① | 硬约束 #8「所有写文件走 python」：**源码**用 IDE 写文件工具（避开 PowerShell 引号与中文损坏，即那条规矩的立意），**报告与全部探针脚本用 python**；两个 commit 信息文件由工具产出后**用 python 复核**「无 BOM / 0 CRLF / UTF-8 可解码」（2596 B、3364 B）。对 `.superpowers/` 下的**既有**文件一次都没用过写文件工具 | **追认**。硬约束 #8 的立意是「别让 PowerShell 静默写坏中文」，而不是「禁用一切编辑器」；实现者既避开了立意要防的失效、又对产出物做了字节级复核，**比字面遵守更到位** |
| ② | 变异做了 **3** 条而非 2 条 | **追认**（第 3 条正是顶回 2 的取证，少了它那条顶回就没有证据） |
| ③ | commit ① 不含公开面扩容 | **追认**（派单自己建议放 ②；且实现者确认 commit ① 那个树上 `__all__` 仍是 47、两边自洽全绿——**中间态可运行**，这是硬规矩 #11 的正面执行） |
| ④ | 报告不 commit（沿用 Task 5/6/7，结案 `docs:` 归控制者）；控制者的 `_mk_brief8.py` / `task-8-brief.md` 一次都没 `git add` | **追认**（分工正确） |

### 实现者报的 3 条关切（控制者裁定）

1. **`factor` 的 `(0, 2]` 只在读侧拦** → **一条脏库行会让学生端打开训练单时 500**。**裁定：接受，本计划不修。** 理由：① DB 那一层刻意不加 CHECK 是 P8-A6 的决定（`(0, 2]` 是读模型的语义、不是数据的形状，Plan 03 可能要放宽上界）；② 脏行只能由「绕过 domain 直接写库」产生，而那条路径今天不存在（Plan 03 的 CRUD API 才会开）；③ **Plan 03 的 CRUD 层必须在写入侧复用同一个校验** —— **这条要写进 Plan 03 的计划**，不能靠 `weekly.py` 的 docstring 传话。实现者已把它逐字写进 docstring ✓
2. **`weekly_factors_of` 对打错的 `prescription_id` 静默返回 `[]`**。**裁定：接受。** 与「该处方本周没有调整」**不可区分**，但那两件事对读模型的产出是**同一个**（`factor == 1.0`、`sessions` 与骨架相同），故不构成失效；已写进 docstring ✓
3. **待清扫第 1 条值得控制者先看**：`assembler.py` 的 `AssembledBlock.weekly_volume` 注释说「Task 8 的读模型要自己决定怎么摊」，而 **Task 8 的决定是「不摊」**（缩放只是 `× factor`，没有跨 block 的摊销）→ 那句注释现在指向一个**与它暗示相反的决定**。**裁定：按 Ruling 145 推到 Task 9 一次性清扫**（它是 Task 5 已结案文件里的纯散文，且不影响任何行为）。⚠️ 但 Task 9 的清扫清单**必须点名它**，否则会漏。

**待清扫合计 5 条**（全是纯散文精度，推 Task 9）。

### Task 9 的入口状态

- 代码基线 **`eb3de22`** + 本轮结案 commit
- **793 passed**、domain **996 / Miss 0 / 288 / BrPart 0 / 100%**、**18 张表**、`__all__` **51**、`_MODELS_PUBLIC_BASELINE` **33（不动）**、扫描面 **35**
- SQLAlchemy **2.1.3**、Python 3.11.1（无 venv）
- ⚠️ **Task 9 要注意的四处**：
  1. **硬规矩 #86 的回扫（Task 8 结案时扫出）**：黄金用例要断言 `weekly_volume`（第 1 周），而它自 Task 5 起带 `volume_unit` → **`expected` 里必须连单位一起钉**（如 `{"weekly_volume": 38.4, "volume_unit": "min"}`）。只钉那个 float 会漏掉「单位串了」这个失效形态。
  2. **P7-A2 的连带**：13 例要**补两个输入字段** `height_cm` / `weight_kg`，否则快照里 `"bmi"` 全是 `None`、spec §7.4 的三档安全触发一档都走不到，而要断言的 `needs_review` / `safety_substitutions` 会**恒为假绿**。补值要与该例既有的 `score_bmi` **档位一致**。
  3. **P7-A7 的连带**：黄金用例还要断言 `label_at_generation`，但**它与 `template_ref` 不是两份独立证据**（对已匹配的处方，`label_at_generation` 与 `template_ref` 前三字符 `RED/YEL/GRN` 恒等，因为匹配器就按 `Layer(label)` 选模板）；且 `insufficient_data` 那例无处方 → **只有 12 例能断言**。
  4. **canonical sha256 的回填**：9 张 = `1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952`（882 行）、11 张 = `2b2649add55205e668c40e287f91592c0bcfcd68599d725030a68fc2400456df`（942 行）→ 写进 spec §1.3 的勘误，并注明**它们都不被守卫钉住**。
  5. **待清扫清单**：Task 5 的 1 条 + Task 7 的 3 条 + Task 8 的 5 条 = **9 条**，其中 Task 8 的第 1 条（`assembler.py` 那句「怎么摊」）**必须点名**。
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
assert "Ruling 154" not in t, "Ruling 154 已存在"
P.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = P.read_bytes().decode("utf-8")
print(f"[after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)} "
      f"CRLF={c.count(chr(13)+chr(10))} LF={c.count(chr(10))}")
for k in ("Ruling 154", "硬规矩 #92", "控制者错误 #154", "996 stmts", "_DAYS_PER_WEEK"):
    print(f"  {k}: {c.count(k)}")

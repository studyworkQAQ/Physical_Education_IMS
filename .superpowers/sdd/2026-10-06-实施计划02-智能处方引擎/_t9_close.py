"""Task 9 结案 + Plan 02 全计划结案：账本追加 Ruling 156/157，计划边界补 GC14 的空白归属。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
LEDGER = HERE / "progress.md"
edits = []

# ---------- 计划：把「安全触发在黄金用例里不可达」这个空白写进边界说明 ----------
raw = PLAN.read_bytes()
t = raw.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
OLD = ("- **本计划不做**：处方模板的自动优化/机器学习、真实视频源、真实 1RM 实测")
NEW = ("- **⚠️ 本计划留下的一个已知空白（Task 9 的顶回 ①，控制者裁定归属 Plan 03）**："
       "**spec §7.4 的三档安全触发在 13 例黄金用例里一档都没有真的命中**。实测（控制者亲跑）："
       "`needs_review` 非空 = **0** 例、`safety_substitutions` 非空 = **0** 例；`body_fat_abnormal` 命中 **5** 例"
       "（GC01/04/05/12/13，与已人读的 `C=true` 逐例吻合，但它在 P9-A1 **之前**也已可达）、"
       "`bmi_over_30` 从「结构上不可求值」变成「**可求值但不命中**」（13 例的 `bmi` 全落在 **[18.9, 25.7]**，无一 > 30，"
       "等价表根本没被查过）、`muscle_low_p10` **仍结构上不可达**（13 人 < MIN_SAMPLE=30 → P10 恒 `None`）。"
       "**P9-A1 的真实效果**已钉进夹具：`safety_skipped` 从 `[\"bmi_missing\", \"muscle_p10_missing\"]` 变成 "
       "`[\"muscle_p10_missing\"]`。"
       "**为什么不当场补**：补法只有两种——① 改 13 例里某一例的身高体重（那是**改 Plan 01 已逐条人读确认的输入**，"
       "为一个 Plan 02 的关注点回溯改 Plan 01 的夹具，代价与收益不成比例）；② **新加一例 GC14（BMI > 30）**。"
       "**裁定：走 ②，归 Plan 03** —— 因为 Plan 03 的预警层（`RED_*` 规则）同样需要高 BMI 与低肌肉量的学生样本，"
       "**两个计划共用同一例新增夹具**，现在加会加两次。"
       "**⚠️ 在那之前，这三档的守卫由 Task 5 的 `safety.py` 单元测试与 Task 7 的 "
       "`test_needs_review_when_no_equivalent_exercise`（端到端）承担，不是无守卫，只是不在黄金用例里。**"
       "这一条已写进夹具的 `_meta.caveats_training_package` 与新测试的 docstring，"
       "**不会靠散文传话**。\n"
       "- **本计划不做**：处方模板的自动优化/机器学习、真实视频源、真实 1RM 实测")
n = t.count(OLD)
assert n == 1, f"边界说明锚点命中 {n} 次"
t = t.replace(OLD, NEW)
edits.append(("计划边界补 GC14 空白归属", n))
PLAN.write_bytes(t.encode("utf-8"))
c = PLAN.read_bytes().decode("utf-8")
print(f"[plan] {len(raw)} B / {raw.decode('utf-8').count(nl)} 行 -> "
      f"{len(c.encode('utf-8'))} B / {c.count(nl)} 行 CRLF={c.count(chr(13)+chr(10))} LF={c.count(chr(10))}")

# ---------- 账本 ----------
lb = LEDGER.read_bytes()
lt = lb.decode("utf-8")
lnl = "\r\n" if "\r\n" in lt else "\n"
print(f"[ledger before] bytes={len(lb)} lines={lt.count(lnl)}")

BODY = """

---

## ✅ Task 9 结案（黄金用例延伸到训练包 + spec 勘误 + 9 条待清扫）—— **Plan 02 的最后一个 Task**

**fix round 用了 0 轮**（Plan 02 **第五次**零 fix round：Task 3、4、6、8、9）。**Critical 零遗留。**

### 交付与验收（全部控制者本机亲跑复核，探针 `t9_probes/_t9_verify.py` 已入库）

| 项 | Task 8 结案基线 | Task 9 结案（= Plan 02 终态） |
|---|---|---|
| commit | `9e46abe` | **`e7a01d2`（P9-A1）→ `7a18852`（13 例延伸到训练包）→ `874b9f2`（P9-A3 指纹）→ `61078c4`（spec 勘误 + §14 七项 + 9 条待清扫）→ `3b4ff97`（报告自身）** |
| 全量 `pytest -q` | 793 passed | **807 passed**（+14 = 1 条对齐守卫 + 13 例参数化）；带 `--cov` **806 passed, 1 skipped** |
| `app/domain/` 覆盖率 | 996 / Miss 0 / 288 / BrPart 0 / 100% | **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**（**四格逐字未变** —— 本 Task 只改了 `assembler.py` 的注释） |
| `__all__` / `_MODELS_PUBLIC_BASELINE` / 扫描面 / 表数 | 51 / 33 / 35 / 18 | **51 / 33 / 35 / 18 全部未变** ✓ |
| **`EXERCISES_FINGERPRINT`** | `3DE598AF38631209`（22 739 B） | **`5394B37F01DAC9AC`**（**23 247 B**，**CRLF = 0**）—— **Plan 02 第一次也是唯一一次动被指纹钉住的文件**；常量已同步，控制者亲验「常量 == 实测」 |
| 另两个指纹 | `D2C8E539E2FA0029` / `822CB86A5E998301` | **逐字未变**（21 412 B / 8 245 B，CRLF 均 0）；18 套模板 YAML **123 848 B、CRLF 合计 0** 未变 |
| `golden_cases.json` | 27 346 B / `8C787701EA70EF90` / `expected` 11 键 | **43 571 B / `A08B6AE9A463BBA3`**；`expected` **23 键**（+12）；`input` 与 `expected` **各 13 例、id 逐格对齐**（控制者亲验 `[c["student_id"] for c in input] == [... expected]` 为 True）；`_meta` 新增 `caveats_training_package` / `expected_schema` / `training_package_provenance` 三节 |
| spec | 98 755 B / §14 **30 行 / 最大编号 31 / `#30` 是空洞** | **128 328 B / 1 093 行**；§14 **37 行 / 最大编号 37 / 1–37 连续无空洞**（控制者按硬规矩 #93 用「数 `\\|` 开头的连续行 + 校验首尾两行」复核：首行 `\\| 1 \\| 18 套模板的维度拆分…`、末行 `\\| **37** \\| **§5.2 的真实空洞…`） |
| canonical sha256 | spec 印 `fe0a44e0…` / 882 | **两个新值都已落进 spec**（9 张 `1f043f2a…` / 882、11 张 `2b2649add…` / 942），**且 `fe0a44e0…` 与 `2ef85d79…` 那段历史记录被保留**（Ruling 229 的因果链没丢） |

**控制者亲验的 P9-A1 验收点（顶回 ① 的复核，逐例）**：13 例里 **12 例有处方、1 例（GC10，`valid_count=3<4` → Z0）断言「无处方」**（其余 10 键全 `null`）。`needs_review` 非空 = **0** 例；`safety_substitutions` 非空 = **0** 例。`safety_triggers` 实测：`body_fat_abnormal` 命中 **5** 例（GC01/04/05/12/13）、`bmi_over_30` **0** 例、`muscle_low_p10` **0** 例；`safety_skipped` 12 例全是 `["muscle_p10_missing"]`（**P9-A1 之前是 `["bmi_missing", "muscle_p10_missing"]`** —— 这就是那条 Critical 更正的可观测效果）。

**变异复跑（证明尺子没被 fixture 改动弄钝）**：实现者复跑了 Task 7 的变异 ④（删 `valid_to_of` 的 `-1 day`）→ **4 failed**（`test_valid_to_is_generated_on_plus_microcycle_minus_one_day`、`test_prescriptions_are_generated_for_every_stratified_student`、`test_a_layer_change_regenerates_and_replaces`、`test_regeneration_does_not_inherit_teacher_overrides`）。**另跑一条自证变异**（`_SEX_FACTOR` 女 `0.9 → 1.0`）→ **3 failed / 15 passed**，红的恰好是 GC03/GC05/GC12、而标签测试与分布测试全绿 → **新 fixture 不是恒绿、且没有越界去守标签**。按硬规矩 #83 的纪律做（前后清 16 个 `__pycache__`、`PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider`、从 TEMP 备份字节级还原）。

**9 条待清扫的逐条结论**：**7 条改了**（`assembler.py` 的「怎么摊」→「不摊」，改完覆盖率复跑仍 100%；`_DERIVED_TABLES` → `_BATCH_OWNED_TABLES` 连带 9 处散文 + 守卫函数名；`daily.py` 2 处 + `backfill.py` 1 处的「三张派生表」；`test_repo.py` 的「九条 `ck_*`」→「**十**条」（全库今天 **18** 条，运行时口径）；2 张 RST 表的列宽；`repo.delete_by_batch` 的 docstring；`test_backfill.py` 的过期余量提到最前面）、**1 条刻意不做**（第 7 条：`weekly_adjustment.factor` 无 CHECK 是 P8-A6 的裁定，只复核了理由已在 `weekly.py` 3 处 + `prescription_stage` 1 处，**一个字节没改**）、**1 条部分做**（第 5 条：另 5 张三段式表量出来了但没改——折行单元格的归属无法脚本化，3 张在 domain 下，纯排版项收益/风险不划算）。

### Ruling 156 — 实现者第 24、25 次顶回控制者，**2 处全部采纳**；3 处偏离全部追认

**顶回 ①（Critical，采纳 → 控制者错误 #156）**：派单说 P9-A1 让「spec §7.4 的三档安全触发**第一次在黄金用例里真的可达**」，并把「`needs_review` / `safety_substitutions` 在几例里**真的非空**」列为验收点。**实测两档都是 0 例** —— 控制者把「**分支变得可求值**」讲成了「**触发会命中**」。这两件事差一层：P9-A1 让 `bmi` 从 `None` 变成有值，于是 `bmi > 30` 这个比较**第一次能被求值**；但 13 例的 `bmi` 全落在 **[18.9, 25.7]**，**无一 > 30**，故比较恒为假、等价表根本没被查过。`muscle_low_p10` 那一档**仍结构上不可达**（13 人 < MIN_SAMPLE=30 → P10 恒 `None`）。
实现者的处置正确：**没有去改 GC 的身高体重**（那是改 Plan 01 已逐条人读确认的**输入**，而派单只授权改 `expected` / `_meta`；且「给每例一组能让 BMI 落到想要档位的身高体重」那句正在被 ⛔ 撤回的段落里），改为把 `safety_triggers` / `safety_skipped` **逐例钉进 fixture**，并在 `_meta.caveats_training_package` 与新测试的 docstring 里**逐字写明不可达**。
**控制者裁定**：采纳，并**把这个空白正式记进计划的「计划边界说明」**（归属 **Plan 03**，走「新加一例 GC14（BMI > 30）」而不是改既有 13 例；理由：Plan 03 的预警层同样需要高 BMI 与低肌肉量样本，**两个计划共用同一例新增夹具**，现在加会加两次）。**⚠️ 在那之前这三档由 Task 5 的 `safety.py` 单元测试与 Task 7 的 `test_needs_review_when_no_equivalent_exercise`（端到端）守卫 —— 不是无守卫，只是不在黄金用例里。**
**→ 补硬规矩 #94：说「某个分支现在可达了」时，必须同时给出「它会被求值成真的那组输入在哪」；给不出就是「可求值」而不是「会命中」，两个词不许混用。** 依据：#156 —— 这与硬规矩 #92（要求一条测试变红前先论证破坏在结构上可达）是**同一条纪律的两半**：#92 管「守卫能不能红」，#94 管「分支能不能真」。

**顶回 ②（Minor，采纳 → 控制者错误 #157）**：派单说 `fe0a44e0…` 与「行数合计 882」**两处都已过期**。实测 **882 对那 9 张表仍为真**（`c5599db` 只改列内容、不改行数），过期的是「**9 张就是全部覆盖面**」这个**隐含前提**（今天是 11 张）。实现者在勘误里两处都写清了、**没把 882 讲成错数**。

**3 处偏离派单字面：全部追认**（① 顶回 ①；② **多做**：P9-A5 只列 `_meta` 的 3 处陈旧 Task 编号，实现者同时改了 GC13 `note` 的 2 处、「（Task 9 关切 6）」1 处、`test_golden_cases.py` 导入行的 `# Task 10 提供` —— **同一缺陷的其它住址**，硬规矩 #75 的正面执行；③ **多做**：待清扫第 2 条只要求改常量名，实现者同时改了守卫函数名 `test_only_derived_tables_expose_batch_id` → `test_only_batch_owned_tables_expose_batch_id`（5 处引用）与 `_replay_cleanup` 首行措辞）。

---

## 🏁 Plan 02 全计划结案（智能处方引擎）

**9 个 Task 全部结案**（原 12 个，按用户 2026-10-08 的裁定合并成 9 个，Ruling 146）。**分支 `feature/plan-02-prescription-engine`，未 push。**

### 从 Plan 01 的终点到 Plan 02 的终点

| 项 | Plan 01 结案（`1355541`） | **Plan 02 结案** |
|---|---|---|
| 全量 `pytest -q` | 453 passed | **807 passed**（+354） |
| `app/domain/` 覆盖率 | 392 stmts / 112 branch / **100%** | **996 stmts / 288 branch / Miss 0 / BrPart 0 / 100%** |
| 表数 | 14 | **18**（+`exercise` / `prescription_template` / `prescription` / `weekly_adjustment`） |
| `app/domain/prescription/` | 不存在 | **9 个实质模块** + 包 `__init__.py`；`__all__` **51** 个名字 |
| `backend/data/` | 1 个 CSV | + **18 套模板 YAML**（123 848 B）+ `exercises.yaml`（23 247 B）+ `exercise_equivalence.yaml`（8 245 B），**全部 CRLF = 0、全部 `eol=lf`** |
| 架构守卫扫描面 | — | **35**（pipeline 8 + db 11 + domain 16）；两份守卫（`test_domain_purity.py` / `test_layering.py`）全绿 |
| spec §14 | 27 项（Plan 01 结束时） | **37 行 / 最大编号 37 / 无空洞** |
| 终审 C 组架构债 | 11 项未清 | **全部清偿**（Task 1） |
| fix round 总数 | — | **Task 1: 5（用满上限）／Task 2: 3／Task 3: 0／Task 4: 0／Task 5: 1／Task 6: 0／Task 7: 1／Task 8: 0／Task 9: 0** = **10 轮** |

### 交付的能力（spec 的哪几节真的落地了）

- **§4.4**（处方数据模型）：4 张表全部建成
- **§5.2**（五个触发条件）：`triggers.py` 的 `evaluate_triggers` 返回**全部**命中的触发（不是第一个），Z0 闸门早退排在最前
- **§7.1–7.5**（智能处方层全部）：18 套模板 + 匹配器（6 档 `MatchStatus`、32 格穷举）+ 装配（§7.3 六步）+ 安全后置（§7.4 三触发 + 等价替换 + addon 追加）+ 教师覆盖（§7.5 五种）
- **§8.4**（骨架 + 周微调两层拆分）：`weekly.py` 的 `WeeklySheet` 读模型 + `weekly_adjustment` 表（`auto` 来源留 Plan 03）
- **§11.2**（B 类算法降级）：「模板 `review.status != approved` → 拒绝生成」已落地
- **§12**（`domain/` 100% 分支覆盖 + 黄金用例延伸到训练包）：**两条都达成**
- **§1.3**（单人处方 p95 < 3 s）：**未测量**（用户裁定删掉性能压测），已在 spec 里写明「未测量」而不是「已达标」

### 控制者错误总计：**157 条**（Plan 01 60 + Plan 02 **97**）

Plan 02 的 97 条里，**本会话（Task 5–9）占 #139–#157 共 19 条**。**实现者顶回控制者 25 次，25 次都是对的**（实现者自己犯错 3 次，全部自纠）。评审者 4 次、复审者 1 次。

**本会话新立的硬规矩**：#78（计划正文不写裸行号）／#79（批量改文档走 python + 逐条 `assert 命中次数`）／#80（不要用探针去数一个已有字面断言的量）／#81（合并计划正文时必须重新实测被引用的量）／#82（探针「0 命中」的自证义务）／#83（`.pyc` 陈旧：变异取证前清 `__pycache__` + `PYTHONDONTWRITEBYTECODE=1`）／#84（Critical 级裁定必须点名计划正文哪一行要跟着改）／#85（一个量能用两种算法得到时必须写明是哪一种 + 给对拍数）／#86（**每个 Task 结案时扫一遍后续所有 Task 的前提**）／#87（「把某个基线数字抬上去」之前先读那条断言的 docstring）／#88（列同步清单时跑一次全量测试、把红掉的相等断言收进来）／#89（数键/字段/成员用运行时口径，绝不用正则数源码；数行尾用 `read_bytes()`）／#90（声称「控制者已经做了 X」之前先 shell 取证）／#91（派单里提到的每一条既有守卫先 `git grep` 核实它存在）／#92（要求一条测试变红前先论证破坏在结构上可达）／#93（数 Markdown 表格行用「数换行 + 校验首尾两行」）／**#94（说「某个分支可达」时必须给出「它会被求值成真的那组输入在哪」）**。

**⚠️ 一个必须写下来的模式**：#139 / #147 / #153 / #155 是**同一族错误的四次发作**（探针的产物被当成事实），而 #80 / #82 / #89 / #93 是**为它立的四条规矩** —— **每立一条、下次就撞上一个新形状**。#93 的正文因此不再列举例外，而是改成「**换一个不依赖形状的方法**」。**这是本会话最重要的一条元教训：列举例外的规矩挡不住第五次。**

### Plan 02 留给 Plan 03 的清单（**必须传导，硬规矩 #86**）

1. **GC14（BMI > 30 的新黄金用例）** —— 顶回 ① 的空白，Plan 03 的预警层同样需要高 BMI 与低肌肉量样本，**两个计划共用同一例**。
2. **`weekly_adjustment` 的 `auto` 来源**（预警触发减量 20%）—— 表与 `WeeklyFactor.source` 的值域今天已支持、`weekly.py` 已能正确处理，但**没有生产者**。
3. **七张反馈/预警表**：`class_session` / `rpe_record` / `training_log` / `mini_test` / `alert` / `notification` / `weekly_class_report`。⚠️ **`models/feedback.py` 今天是一个 475 B 的空壳**（只有 docstring 交代「这里为什么没有表」），加表时要把那段 docstring 改掉，并注意 `_MODELS_SUBMODULES`（「拆包新增的**六个**子模块名」）与 `_MODELS_PUBLIC_BASELINE`（**33，Ruling 97 刻意不动**）的纪律。
4. **CRUD API 层必须在写入侧复用 `WeeklyFactor` 的 `(0, 2]` 校验**（Task 8 关切 1：`factor` 只在读侧拦，**一条脏库行会让学生端打开训练单时 500**）。**不能靠 `weekly.py` 的 docstring 传话。**
5. **`prescription_template` 今天没有 `microcycle_weeks` / `weekly_frequency` 两列**（P6-A3 刻意没加）—— 教师端要展示模板周期时再加，并同步 `sync_templates` 与 `_MODELS_PUBLIC_BASELINE` 的纪律。
6. **spec §14 的 #37**（§5.2 只看标签的空洞）：若 Plan 03 把触发 4 收窄成「只在 week16」，**「标签不变但 `W`/`C` 变了」的学生就会真的漏人**。
7. **`daily_sync_run.alert_count` 列已存在但从未被写过**（Plan 01 建好、Plan 02 只写 `prescription_count`）。
8. **`sync_exercises` / `sync_templates` 今天仍没有生产调用方**（P3-A1 禁止接进 `seed_database`；Task 7 的管道阶段也没接）→ Plan 03 的 CRUD 层或一个迁移脚本要接手。
9. **`HttpLePaoAdapter` 落地**（含终审 B 数的约 40 条新契约测试）。
10. **本仓仍没有依赖锁文件、仍没有 venv** → 「807 passed」这个数字绑在 SQLAlchemy **2.1.3** 上，而 Smart App Control 的判定可以随云端信誉翻转（Ruling 121/122：文件一个字节没变也会被拦）。**Plan 03 开工第一件事仍是那条 import 冒烟。**
"""

if lnl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", lnl)
assert "Ruling 156" not in lt, "Ruling 156 已存在"
LEDGER.write_bytes((lt.rstrip("\r\n") + BODY).encode("utf-8"))
c2 = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c2.encode('utf-8'))} lines={c2.count(lnl)} "
      f"CRLF={c2.count(chr(13)+chr(10))} LF={c2.count(chr(10))}")
for k in ("Ruling 156", "Ruling 157", "硬规矩 #94", "控制者错误 #156", "控制者错误 #157",
          "Plan 02 全计划结案", "807 passed"):
    print(f"  {k}: {c2.count(k)}")
print(f"\n[edits] {len(edits)} 处：")
for lab, n in edits:
    print(f"  {n}x  {lab}")

"""Task 5 结案：① 补 P5-A10 的事实列（顶回第 6 处采纳）② 账本追加 Ruling 148 ③ 打印验收数。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-06-实施计划02-智能处方引擎.md"
LEDGER = HERE / "progress.md"

# ---------- ① 计划正文：P5-A10 的事实列 ----------
raw = PLAN.read_bytes()
t = raw.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
OLD = ("| P5-A10 | Minor | `BODY_FAT_LIMIT` 实测**只有 `derive.py` 的一行定义**"
       "（`BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}`）+ 一处消费；"
       "计划 5.3 写的是「`derive.py:68-69`」，**行号口径错**，且「明写严格大于」的引文控制者未核。 |")
NEW = ("| P5-A10 | Minor | **控制者错误 #140（本条的「事实」本身是假的，fix round 1 撤回）**："
       "控制者的探针只 grep 了标识符 `BODY_FAT_LIMIT`、**没 grep 注释行**，于是把「我的探针没显示它」"
       "讲成了「它不存在」，进而指控原计划「行号口径错、引文未核」。实测 `app/domain/derive.py` 的"
       "定义行**上一行**就是逐字注释「体成分异常 C 的体脂率阈值（spec §6.3②）：男 > 20%、女 > 28%，"
       "**严格大于**。」——**原计划的 `:68-69` 与引文双双正确，本条无事实可更正。** |")
n = t.count(OLD)
assert n == 1, f"P5-A10 事实列锚点命中 {n} 次，不是 1"
t = t.replace(OLD, NEW)
PLAN.write_bytes(t.encode("utf-8"))
chk = PLAN.read_bytes().decode("utf-8")
print(f"[plan] bytes={len(chk.encode('utf-8'))} lines={chk.count(nl)} "
      f"CRLF={chk.count(chr(13)+chr(10))} LF={chk.count(chr(10))} (相等即纯CRLF)")

# ---------- ② 账本追加 ----------
lb = LEDGER.read_bytes()
lt = lb.decode("utf-8")
lnl = "\r\n" if "\r\n" in lt else "\n"
print(f"[ledger before] bytes={len(lb)} lines={lt.count(lnl)}")

BODY = """

---

## ✅ Task 5 结案（处方装配（简化版）：`intensity.py` + `assembler.py` + `safety.py` + `override.py`）

**fix round 用了 1 轮**（Ruling 145 的目标是 1–2 轮 ✓；对比 Task 1 用满 5 轮、Task 2 用 3 轮）。**Critical 始终 0 遗留。**

### 交付与验收（全部控制者本机亲跑复核）

| 项 | Task 4 结案基线 | Task 5 结案 |
|---|---|---|
| commit | `dfa7580` | **`d78120a` → `1c5b9bb` → `5f05dda` → `14673aa` → `fc8f5a8` → `fe3a6df` → `f9b6ed5`**（7 个） |
| 全量 `pytest -q` | 592 passed | **679 passed**（+87） |
| 带 `--cov` | — | **678 passed, 1 skipped**（那 1 个 skip 是 `tests/pipeline/test_backfill.py` 既有的墙钟断言，`sys.gettrace()` 非空时按硬规矩 #42 主动跳；口径已写进计划 5.5） |
| `app/domain/` 覆盖率 | 541 stmts / Miss 0 / 132 branch / BrPart 0 / **100%** | **905 stmts / Miss 0 / 262 branch / BrPart 0 / 100%** |
| 四个新模块各自 | — | `intensity` 27/12、`assembler` 124→(fr1 后)/38、`safety` 96/40、`override` 96/38，**各 100%** |
| `__all__` | 24 | **43**（+19：intensity 3 / assembler 8 / safety 4 / override 4） |
| `_PRESCRIPTION_PUBLIC_BASELINE` | 24 个二元组 | **43**；`_OWNED_MODULES` **3 → 7**（实现者超出派单发现：支 5 的「穷尽」判据只对这个清单成立，不加进去则「往 `safety.py` 加个新常量却忘了重导出」会完全静默） |
| 架构守卫扫描面 | 28（pipeline 7 + db 11 + domain 10） | **32**（domain 14）；**两份守卫一个字都没改**（四个下界 `>=5`/`>=8`/`relative_seen>=16`/`len(real_py)>=40` 实测 14/32/30/77 全部仍满足） |
| 表数 | 16 | **16**（本 Task 不建表，Task 6 才建） |
| 四个模块 sha256[:16] | — | `intensity` `9D8336D25A2DF196`、`assembler` `D443187E541379CE`、`safety` `BC471A4B5161D10C`、`override` `1E2E088C886B4990` |
| 禁区指纹 | `D2C8E539E2FA0029` / `3DE598AF38631209` / `822CB86A5E998301` | **三个逐字不变**；`pe.db` 不存在、`data/seed/` 0 文件、`git diff fc8f5a8 HEAD -- backend/data` 为空 |

**控制者亲验的承重结论**（探针 `t5_probes/_t5_verify.py` 与 `_t5_fr1_verify.py`，均入库）：
- `assembly_snapshot` **恰好 12 个键**；`weekly_volume_base` = **`{"min": 48.0, "reps": 120.0}`**（`RED-END-ABN-01` + 男 20 岁 + `endurance_score=50`），运行时类型 `_ReadOnlyVolumeBase`（`dict` 子类、屏蔽 8 个 mutator），**`json.dumps(allow_nan=False)` 通过**（317 字符），就地写入被 `TypeError` 拒绝且错误消息自带理由。
- **18 套模板的 `weekly_volume_base` 键集分布 = `{("min",): 10, ("reps",): 6, ("min","reps"): 2}`**，`"unspecified"` 出现 **0** 次（addon 是 `apply_safety` 阶段才追加的，`assemble` 的快照里不该有它 —— 这一格亲验通过）。
- 控制者实算的算例**逐格命中**：`interval_run` 第 1 周 `38.4 min` / 第 4 周 `32.6`、`compound_circuit` `96.0 reps` / `81.6`、`hr_zone(194.0, 60, 70) == (116, 136)`、`volume_factor 0.8` / `band 'low'`、`hrmax 194.0` / `formula 'tanaka'`、`paused False`、`weeks 4`。
- **RPE 值域已统一为 0–10**：`intensity.py` 与 `templates.py` 对 `6-20`/`Borg` **0 命中**，`assembler.py` 的 5 处命中**全部是显式否定语境**（「**不是** Borg 经典的 6–20」）。
- domain 纯净性**亲扫**（不靠守卫）：四个模块的 import 面里**没有 `math` / `types` / `json` / `os` / `sys` / `pathlib` / `datetime`**，相对导入**全部 level 1**。

### Ruling 148 — 实现者第 7–12 次顶回控制者，**6 处全部采纳**；7 处偏离全部追认

**顶回 1（采纳，控制者错误 #141）**：F1-1 的口径「所有 block 的 `base × sessions_per_week` 之和」**字面照做会把课数乘两遍**（得 `{"min":192.0,"reps":480.0}`），而派单自己又把改前的 `168.0` 分解成 `48.0 min + 120.0 reps` —— **同一段派单里两个口径互相打**。实现者取「逐 `(session, block)` 累加 `base`」，与派单的分解式一致，且与「`base × sessions_per_week` 按不同 ref 求和」在真仓 **18/18 逐格相等**。→ **补硬规矩 #85：给口径时，若同一个量能用两种算法得到，必须写明是哪一种，并给一个能对拍的具体数。**

**顶回 2（采纳）**：F1-1 的决策树**漏了一格** —— 控制者给的备选是「`MappingProxyType` 不行就用 `collections.abc.Mapping` 的自定义子类」，但**后者同样不可 JSON 序列化**，于是第一条备选走到头还是落到第二条（存裸 `dict`、只读靠约定），而那会让派单**同时**要求的测试③（`pytest.raises(TypeError)`）无法成立。实现者找到第三个构造：`dict` 的子类 + 屏蔽 8 个 mutator —— **同时满足「JSON 可序列化」与「就地写入抛 TypeError」**。控制者亲验通过。

**顶回 3（采纳）**：F1-2 里控制者写「不要顺手加 `0 <= value <= 10` 的运行时校验，除非……」，前提是「值域校验属于加载器」。实现者指出 **`hr_zone` 已经在同一层校验 `hrmax_pct` 的值域**，故那句话与**本仓已有做法**自相矛盾。实现者选择加校验 + 四值边界测试（`-0.1`/`0.0`/`10.0`/`10.1`），控制者采纳。

**顶回 4（采纳，控制者错误 #142）**：F1-5③ 让实现者补 5.3 的 `Consumes`（漏列 `Template` / `ExerciseSpec`），前提是「签名已经扩参了」。实现者指出**计划正文里 5.3/5.4 的 `Produces` 两行当时仍是旧签名** —— 只补 `Consumes` 会让**同一节自相矛盾**。故连签名一起改（补丁 E10a/E10b）。

**顶回 5（采纳 → 硬规矩 #84）**：F1-1 是 **Critical 级裁定**，但派单**没要求同步计划正文** —— 六步口径的第 6 步仍写着 `weekly_volume_base` 是「`float`，`round(…, 1)`」，而 **Task 6/8 的实现者读的就是那一行**。实现者主动补成 E9。
**→ 补硬规矩 #84：凡 Critical 级的口径裁定，派单必须同时点名「计划正文哪一节哪一句要跟着改」。否则修好了代码、留下了计划，下一个 Task 的实现者会照旧口径重犯一遍。** 依据：本次 F1-1；同型的前例是 Plan 01 的硬规矩 #11（改了 Interfaces 却没改照抄它的 Step，吃过 6 次）。

**顶回 6（采纳，控制者本轮自己落地）**：F1-3 让实现者「只改 P5-A10 那一行的**更正列**」，结果**事实列仍写着「行号口径错、引文控制者未核」，与更正列的「撤回」当面对打**。实现者对照 Ruling 147 的 P5-A13（同为控制者错误，**事实列**直接以「控制者错误 #139：…」开头）指出本仓惯例是连事实列一起改，并报请裁定。**裁定：照 P5-A13 的惯例**，控制者本轮已亲自把事实列整格重写（补丁命中 1 次，计划 → 见下方字节数）。**这不再开一轮 fix round**（Ruling 145：纯散文精度不单独开轮）。

**7 处偏离派单字面的处置**：
| # | 偏离 | 裁定 |
|---|---|---|
| ① | 没走 F1-1 的 fallback（`types` 不放行那条） | **追认**（见顶回 2，第三解更好） |
| ② | 实现取「逐 `(session,block)` 累加 `base`」 | **追认**（见顶回 1） |
| ③ | 加了 `[0,10]` 校验（派单允许但倾向不加） | **追认**（见顶回 3） |
| ④ | 计划正文多改 3 处（E9/E10a/E10b） | **追认**（见顶回 4/5） |
| ⑤ | 只读映射做成私有的 `_ReadOnlyVolumeBase` → `__all__` **43→43** 而非 44 | **追认**。理由成立：它是实现细节，导出它会让支 5 的「穷尽」判据要求它也进基线，而它对消费者无意义 |
| ⑥ | 入库范围比字面清单大（14 份取证脚本 + 2 份 commit 信息 + 1 份扫描输出） | **追认**（用户已裁 `.superpowers/` 纳入 git；取证脚本入库是 Plan 02 的既有惯例） |
| ⑦ | `task-5-report.md` / `task-5-brief.md` / `_mk_brief5.py` / `_t5_verify.py` 等**仍未入库** | **裁定：入库。** `task-1..4-report.md` 与 `-brief.md` 全部已入库，Task 5 的裸露面是**唯一的例外**，而 Ruling 116 立 `.superpowers/` 入库的立意正是「审计链不留缺口」。控制者本轮随结案 commit 一起入库 |

### 控制者亲跑的变异复跑（硬规矩 #83 的程序有效性验证）

控制者独立复跑了**变异 ②**（`safety.py` 的 `needs_review = True`），**刻意做成等长替换**（`True` → `None`，锚点 43 字符 == 替换串 43 字符），正好复现硬规矩 #83 描述的陷阱条件：

| 相位 | 结果 |
|---|---|
| 清 `__pycache__` + `PYTHONDONTWRITEBYTECODE=1` + `-p no:cacheprovider` | 清掉 5 个目录（第二次跑是 0 个，因为已禁写） |
| **M0**（不变异） | `2 passed, 677 deselected`，exit 0 |
| 变异后 sha256 | `BC471A4B5161D10C` → **`53C57434FD5AAEEE`**（变了） |
| **变异后跑** | `1 failed, 1 passed`，exit 1 —— `FAILED tests/domain/test_prescription_safety.py::test_missing_equivalent_sets_needs_review_and_keeps_the_block - assert None is True`（开火的正是 `assert outcome.needs_review is True` 那一句，与实现者报的分支逐字一致） |
| 还原后 sha256 | **`BC471A4B5161D10C`**（与原始逐字相同） |
| **还原后重跑** | `2 passed`，exit 0 |

**结论：尺子有效（不恒绿），且 `.pyc` 陷阱在硬规矩 #83 的程序下没有发作。**

⚠️ **诚实交代一处覆盖不足**：控制者用 `-k needs_review` 只选中 **2** 条测试，其中 **1** 条变红。实现者报的第二条 `test_a_partially_solvable_table_…` **名字里没有 `needs_review`**，故**控制者的复跑没有覆盖它**。**「实现者说两条红、控制者只验了一条红」——不得把它讲成两条都验过。**（硬规矩 #56：主语与范围要写清。）

### 待清扫（推到 Task 9，Ruling 145）

fix round 1 已清掉 5 条（P5-A2 的块数加权口径、5.5 漏点 `_OWNED_MODULES` 与第二句 assert、5.3 的 `Consumes`+`Produces`、`--cov` 差 1 的口径、P5-A10 撤回）。**剩余 1 条推 Task 9**：计划 Task 9 的 Step 3 仍写「新增的 `app/domain/prescription/` **八个**模块全部纳入」，而实际是 **9 个实质模块**（`exercises`/`templates`/`match`/`intensity`/`assembler`/`safety`/`override`/`triggers`/`weekly`）——「计划完成后的状态」那节已经改对，Task 9 的 Step 3 这一句漏改。

### Task 6 的入口状态

- 代码基线 **`f9b6ed5`** + 本轮结案 commit（含 P5-A10 事实列补丁、账本、未入库文件）
- **679 passed**、domain **905 / Miss 0 / 262 / BrPart 0 / 100%**、**16 张表**、`__all__` **43**、扫描面 **32**
- SQLAlchemy **2.1.3**、Python 3.11.1（无 venv）
- ⚠️ **Task 6 要注意的两处口径**：① `assembly_snapshot` 是 **12 键**，`apply_safety` 之后是 **15 键**（多 `safety_triggers` / `safety_skipped` / `safety_volume_factor`），**Task 6 落库的是 15 键那一份**，且两份都已由 `json.dumps(allow_nan=False)` 守卫；② `weekly_volume_base` 是 **`Mapping[str, float]`（按单位分列）不是 `float`** —— Task 6 的 `prescription.assembly_snapshot` 与 Task 9 的黄金用例期望值都要按这个形状写。
"""

if lnl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", lnl)
assert "Ruling 148" not in lt, "Ruling 148 已存在"
lt2 = lt.rstrip("\r\n") + BODY
LEDGER.write_bytes(lt2.encode("utf-8"))
c2 = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c2.encode('utf-8'))} lines={c2.count(lnl)} "
      f"CRLF={c2.count(chr(13)+chr(10))} LF={c2.count(chr(10))}")
for k in ("Ruling 148", "硬规矩 #84", "硬规矩 #85", "控制者错误 #140", "控制者错误 #141",
          "控制者错误 #142", "53C57434FD5AAEEE"):
    print(f"  {k}: {c2.count(k)}")

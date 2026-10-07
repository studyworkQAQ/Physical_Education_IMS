import pathlib
import subprocess
import os

ROOT = pathlib.Path('.')
WS = ROOT / '.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎'

# ---------- (a) 账本：Task 4 预检 ----------
L = WS / 'progress.md'
src = L.read_text(encoding='utf-8')
MARK = ('Task 3 结案。**下一步：Task 4（模板匹配器 `match.py`）预检。** 代码基线 `ab075d3`、'
        '**581 passed**、**16 张表**、domain **499/120/100%**、SQLAlchemy 2.1.3。')
if src.count(MARK) != 1:
    c = [l for l in src.split('\n') if l.startswith('Task 3 结案。**下一步：Task 4')]
    assert len(c) == 1, c
    MARK = c[0]

NEW = """
---

### Task 4: 模板匹配器 — 预检扫描（Pre-flight，控制者亲跑）

**基线**：`a5bdebe`（代码基线 `ab075d3`），581 passed，domain 499/120/100%，16 张表，SQLAlchemy 2.1.3。
**方法**：硬规矩 #49 + #76（**本轮起派单里不许出现裸行号，一律给可 grep 的原文**）。全部证据来自控制者本机 shell 实跑（脚本 `.superpowers/sdd/_pf4.py`，跑完删除）。

#### A. 计划文本需更正的事实（**6 处已落盘**）

**P4-A6（Important，已更正）— Task 4 的 Files 段只列了 2 个新建文件，而本 Task 必然要动另外 4 处。**

原文：「**Files:** Create `backend/app/domain/prescription/match.py`、`backend/tests/domain/test_prescription_match.py`」。**漏掉的**：
1. `app/domain/prescription/__init__.py` —— 公开面要重导出 `MatchInput` / `MatchOutcome` / `MatchStatus` / `match_template`，`__all__` 从 **20** 扩到 20+N
2. `tests/test_refdata_prescription.py` —— `_PRESCRIPTION_PUBLIC_BASELINE`（控制者实跑：今天是 **20 个 `(名字, 所有者模块)` 二元组**，`assert len(...) == 20` 的报错文案是「基线是 20 个名字，抄漏了就当场红」）**两处都要改**
3. `tests/architecture/test_domain_purity.py` 与 `test_layering.py` —— **三处已过期/写错的陈述**（见下）
4. **Task 3 转来的 4 项**（账本 Ruling 134-1）

**三处过期/写错的陈述（控制者亲扫定位，按可 grep 的原文给）**：
- `# Task 2 会新建 app/domain/prescription/ 子包（今天不存在）` —— **子包自 Task 2 起就存在、Task 3 已填满 12 个公有定义**
- `但 ``app/domain/prescription/`` 这一层子包已经建出，Task 3 的 ``match.py`` 一写` —— **`match.py` 是 Task 4 的，不是 Task 3 的**
- `# Task 2 的形状（fix round 5 新加，Plan02 Ruling 67）：app/domain/prescription/match.py` —— 那一格矩阵是 **Task 1 fix round 5** 为 **Task 4** 的形状埋的，**归属写错了两处**（既不是 Task 2 加的、也不是 Task 2 的形状）

**⚠️ 这三处正是 Task 3 实现者报的关切 ⑨**（它说「用例本身正确，那两个文件不在授权面」）——**它是对的，而控制者在 Ruling 134-9 里把它转给了 Task 4，所以本轮必须真的授权**。

**另有两组会变的计数**（散在两份守卫的 docstring 里多处，改前先 grep，硬规矩 #66）：全仓相对导入今天 **16 条**（全部 `level == 1`）；架构守卫扫描面今天 **27**（pipeline 7 + db 11 + domain **9**），加 `match.py` 后是 **28**（domain 变 10）。

**P4-A1（Important，已更正）— Consumes 清单漏了 `ReviewStatus` 与 `is_reachable`。**

亲跑 `app.domain.prescription.__all__` = **20 个名字**、`templates.__all__` = **14 个**，两者都含 `ReviewStatus`（成员 `PENDING="pending"` / `APPROVED="approved"`）与 `is_reachable`。原文只列了 `Template` / `WeaknessBucket` / `BodyCompState` / `Layer`。**`ReviewStatus` 是 `NOT_APPROVED` 的判据来源，`is_reachable` 是 `reachable` 规则的唯一所有者**——而后者的 docstring 里明写「**两处消费**：① 加载器用它校验 YAML…；② **Task 4 的匹配器按它排除预留位**」。**即 Task 3 已经为 Task 4 设计好了接口，而计划的 Consumes 清单不知道这件事。**
**附带核实**：Task 3 已把 `Layer` **re-export** 进 `templates`（`templates.__all__` 里有它），故 `from .templates import Layer` 与 `from app.domain.stratify import Layer` 都可用；**唯一所有者是 `app.domain.stratify`**，选哪条路径要在 docstring 里说明。

**P4-A2（Important，已更正）— 「先查 `reachable`」有歧义：查字段还是调函数？**

亲跑 `is_reachable` 的函数体：`return not (layer is Layer.GREEN and body_comp is BodyCompState.ABNORMAL)`，其 docstring 自称「``reachable`` 的**唯一所有者**」，并说加载器用它校验 YAML 写的 `reachable` 与维度组合不矛盾（矛盾就在加载时响亮失败）。

**裁定：`match.py` 读**字段** `template.reachable`，不调 `is_reachable`。** 理由：① `is_reachable` 是**规则的**唯一所有者、YAML 的 `reachable` 字段是**数据的**唯一所有者，**加载器已强制两者一致**——匹配器再算一遍就是**第三个住址**（违反 Global Constraint #3）；② `match_template` 是消费者，吃的是「已过校验的 `Template`」，重新推导会**掩盖「加载器没校验」这个真故障**；③ 读字段让 `:392` 那类**直接构造 `Template` 实例**的测试行为可预测。
**但 `match.py` 的 docstring 必须写明**（硬规矩 #39）：规则的所有者是 `is_reachable`，本函数只消费加载器已校验过的字段；**若有人绕过加载器手工构造了一个 `reachable` 与维度矛盾的 `Template`，本函数不会发现**。

**P4-A3（Important，已更正）— 完整的优先级链原文没有给出，而 32 格穷举的期望表完全依赖它。**

原文只说了相邻的一对（`reachable` 先于 `review_status`）。**控制者按 `:386-389` 的分类独立实算 32 格**：

```
NO_LAYER 8 / NO_BUCKET 6 / UNREACHABLE 3 / MATCHED 15  —— 与原文的 8/6/3/15 逐字相符
```

而这个分类**只在下面这条链下成立**：`NO_LAYER → NO_BUCKET → NO_TEMPLATE → UNREACHABLE → NOT_APPROVED → MATCHED`。

**承重的两处**：
- **`NO_BUCKET` 必须先于 `UNREACHABLE`**：`(green, None, abnormal)` 这一格同时满足「桶为空」与「绿层+异常」，**原文的 6 个 `NO_BUCKET` 里包含它**。若顺序反过来，分类变成 `{NO_LAYER:8, NO_BUCKET:4, UNREACHABLE:5, MATCHED:15}`——**总数仍是 32**。**这是「顺序承重」最隐蔽的形态：错了也不会让计数对不上**，只有一个一个格子看期望表才发现。
- **`NO_TEMPLATE` 必须先于 `UNREACHABLE`/`NOT_APPROVED`**：查不到模板就没有 `reachable` / `review_status` 可读。

**P4-A4（Minor，已更正）— 变异 ① 的后果写错了一半。**

原文：「把 `reachable` 检查删掉 → 3 个 `UNREACHABLE` 组合会变成 `NOT_APPROVED` **或** `MATCHED`」。亲跑 18 套 YAML：`review.status` 的 distinct 值**只有 `approved` 一个**，故**只可能是 `MATCHED`，不可能是 `NOT_APPROVED`**。**按硬规矩 #65，变异判据要写明哪个断言分支开火**——这里是穷举测试里那 3 格的 `status` 期望值。

**P4-A5（Important，已更正）— `:378` 引的 `derive.py:330` 是**空行**。**

亲跑定位：字段声明 `dominant_bucket: str | None` 在 `derive.py:129`（`WeaknessResult` 的字段）、口径说明在 `:320` 起的 docstring、赋值处 `dominant_bucket=dominant` 在 `:371`；`_BUCKET_ORDER` 在 `:77`、消费在 `:352`/`:356`。
**「Ruling 175 补的测试」控制者没有核**（那是 Plan 01 账本里的裁定号，本轮没去查）——**已在更正里明写「实现者若要引用它，自己核一遍」**，而不是把一个未核的引用留给下游。
**⚠️ 这是硬规矩 #76（派单不许出现裸行号）立完之后，控制者第一次在预检里主动把裸行号换成「可 grep 的原文 + `git grep` 命令」**：更正文本给的是 `git grep -n "dominant_bucket" -- backend/app/domain/derive.py`。

**P4-A7（Minor，已更正）— 「复用 `stratify.explain()` 的 Z0 文案口径」没有给出确切原文，实现者会自己造第二套。**

亲跑取到：`app/domain/stratify.py` 的 `_REASON` 映射里 `RuleId.Z0` 对应 f-string **`f"有效项不足 {MIN_VALID_COUNT} 项，本日不分层"`**；`explain()` 在 `:326`，其 Z0 分支说明是「`Z0` 路径单独成句：它没有颜色可报，要说的是「为什么没有分层结果」以及下一步」。→ **`NO_LAYER` 的 `reason` 应当与这条同源**：要么 import `_REASON[RuleId.Z0]`，要么逐字引用并注明出处；**不要另写一句意思相近的话**（那就是第二个所有者，违反 Global Constraint #3）。

#### B. 核对通过、无需更正（控制者实跑）

- **`:385-389` 的 32 格算术**：4 层 × 4 桶（3 真桶 + `None`）× 2 体成分 = **32** ✓；四类 **8/6/3/15** 逐字相符、且**互斥**（控制者按优先级链独立分类后求和 = 32）✓
- **`:394` 的 `_BUCKET_ORDER` 与 Ruling 100**：`derive.py:77` 定义、`:352`/`:356` 消费、`:76` 的注释逐字写着「故 dominant_bucket 不依赖 dict 的哈希顺序（**Ruling 100**）」、`:323` 的 docstring 写「声明序取先出现者」→ **计划的引用为真** ✓
- **`:380` 的 spec §11.2 引文**：spec `:859` 逐字是「模板 `review.status != approved` | 拒绝生成，返回「模板待审校」，教师端提示」→ **相符** ✓（同一张表 `:860` 是安全替换的 `needs_review`，`:861` 是新生无历史体测）
- **`:392` 的「frozen dataclass 可直接构造、不必改 YAML」**：Task 3 已按 P3-A8 证好（`Template` 是 frozen dataclass、构造期不校验）✓
- **`:381` 的「不做 I/O、不读盘」**：由 `test_domain_purity.py` 的 allow-list 机器可查地钉住 ✓；`match.py` 需要 import 的只有 `dataclasses` / `typing` / `collections.abc` + `app.domain.*`，**全在 allow-list 内**
- **架构守卫的矩阵已经预埋了 `match.py` 这一格**：`test_domain_purity.py` 的 `cases` 里有 `("app/domain/prescription/match.py", ("app","domain","prescription"), …)`，且 docstring 明写「`level == 2` 的**跨子包**导入也必须仍被 `_is_allowed` 放行（矩阵第 9 行）……`app/domain/prescription/match.py` 里的 `from ..indicators import X` 就是这一档」→ **Task 1 fix round 5 埋的那一格绿档，到本 Task 才真的从「前瞻」变成「真仓形状」**（前提是 `match.py` 选相对导入；账本 Ruling 104 记的今天全仓 16 条相对导入**全是 `level == 1`**，故仍是前瞻）

#### C. Global Constraints 冲突

- **C1**：`match.py` 进 `app/domain/prescription/` → **domain 纯净性守卫的扫描面自动扩大**（`SCANNED_DIRS` 27 → 28、`app/domain` 9 → 10）。亲验两份守卫的空转守卫下界（`>= 8` 与 `>= 5`）**都不会红** ✓
- **C2**：禁区四项不变。本 Task **不碰** `backend/data/`（18 个 YAML 已被指纹钉住，改了要同步 18 个指纹）、**不碰** `app/seed/`、**不碰** `.gitattributes`
- **C3**：domain 覆盖率 **100% 必须维持**。⚠️ `match.py` 有一条 6 分支的优先级链，**每一支都要有测试走到**（`BrPart 0`）；而 32 格穷举**天然覆盖全部分支**——这也是为什么穷举表要字面写死而不是从 `templates` 反推（硬规矩 #35）

#### 预检小结

**6 处计划更正已落盘（P4-A1…A7，无 Critical）**，其中 **5 处 Important**（A1 Consumes 漏两项 / A2 `reachable` 读法歧义 / A3 优先级链缺失 / A5 `derive.py:330` 是空行 / A6 Files 段漏 4 处）+ **2 处 Minor**（A4 变异后果 / A7 Z0 文案未给原文）。

**⚠️ 一个值得记的正面观察**：本轮预检**没有查出 Critical**，而 Task 2 与 Task 3 各有 2 处。原因不是运气——**Task 4 的计划正文只有 41 行、且不碰数据文件与 schema**（对比 Task 2 的 55 行 + 两个 YAML + 一张表、Task 3 的 69 行 + 18 个 YAML + 一张表 + spec 两处）。**即：计划文本越长、触碰的既有资产越多，预检查出的缺陷就越多。** 这条对 Task 9（两张表 + 五触发条件）与 Task 10（接入管道）是预警——那两个 Task 的正文都很长。

**控制者错误计数**：本轮预检查出的 6 处都是**计划编写期（`e26347f`）就存在的缺陷**，与 Task 2/3 预检的 P2-A*/P3-A* 同源，故合并记 **#132**（一次预检不足，覆盖 6 处）。**Plan 02 累计 72 次，Plan 01 60 次，合计 132 次。**
**⚠️ 但 P4-A5 要单独说一句**：它是**控制者在预检里第一次主动把裸行号换成可 grep 的原文**（硬规矩 #76 立完之后的第一次执行），而它查出的正是「计划引的行号是空行」。**#76 立刻产生了回报。**

Task 4: 预检完成（6 处计划更正已落盘、无 Critical、0 条新硬规矩），派发中。代码基线 `ab075d3`、581 passed、16 张表、domain 499/120/100%。
"""

L.write_text(src.replace(MARK, MARK + "\n" + NEW, 1), encoding='utf-8')
print('(a) LEDGER OK', len(L.read_bytes()))
out = L.read_bytes().decode('utf-8')
for k in ('Task 4: 模板匹配器 — 预检扫描', 'P4-A6（Important', 'P4-A1（Important', 'P4-A2（Important',
          'P4-A3（Important', 'P4-A4（Minor', 'P4-A5（Important', 'P4-A7（Minor',
          'B. 核对通过、无需更正', 'Task 4: 预检完成'):
    print('    %-34s %d' % (k, out.count(k)))

# ---------- (b) commit ----------
tmp = pathlib.Path(os.environ['TEMP']) / 'pe_cm12.txt'
tmp.write_bytes(
    ("docs: Task 4 预检更正计划正文 6 处（P4-A1..A7）+ 账本预检节\n\n"
     "无 Critical（Task 2/3 各 2 处）。5 处 Important：\n"
     "- Consumes 漏了 ReviewStatus 与 is_reachable（Task 3 已为 Task 4 设计好接口，计划不知道）\n"
     "- 「先查 reachable」歧义：裁定读字段、不调 is_reachable（否则是规则的第三个住址）\n"
     "- 完整优先级链缺失：NO_LAYER→NO_BUCKET→NO_TEMPLATE→UNREACHABLE→NOT_APPROVED→MATCHED，\n"
     "  而 32 格穷举的 8/6/3/15 只在这条链下成立；(green,None,abnormal) 的顺序错了总数仍是 32\n"
     "- 引的 derive.py:330 是空行（真实位置 :129/:320/:371）\n"
     "- Files 段只列 2 个新建文件，实际必然要动另外 4 处（含 Task 3 转来的 4 项与\n"
     "  两份架构守卫里三处已过期/写错的陈述）\n"
     "2 处 Minor：变异①的后果只可能是 MATCHED（18 套全 approved）；Z0 文案未给原文。\n\n"
     "硬规矩 #76（派单不许出现裸行号）立完后第一次执行即产生回报：P4-A5 查出的正是空行。\n").encode('utf-8'))
subprocess.run(['git', 'add', '-A', 'Document', '.superpowers'], capture_output=True, text=True)
r = subprocess.run(['git', 'commit', '-q', '-F', str(tmp)], capture_output=True, text=True)
print()
print('(b) commit rc =', r.returncode, r.stderr.strip()[:200])
tmp.unlink()
head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
print(subprocess.run(['git', 'log', '--oneline', '-2'], capture_output=True, text=True).stdout)
print('git status --short = %r' % subprocess.run(['git', 'status', '--short'],
                                                 capture_output=True, text=True).stdout)

# ---------- (c) 抽 Task 4 简报（硬规矩 #48：从已提交状态抽）----------
st = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True).stdout
assert st.strip() == '', '工作树不干净，不能抽简报'
PLAN = ROOT / 'Document/2026-10-06-实施计划02-智能处方引擎.md'
blob = subprocess.run(['git', 'show', 'HEAD:Document/2026-10-06-实施计划02-智能处方引擎.md'],
                      capture_output=True).stdout
wt = PLAN.read_bytes()
assert blob.replace(b'\r\n', b'\n') == wt.replace(b'\r\n', b'\n')
print('(c) blob == worktree (normalized) ✓  HEAD =', head)

LL = wt.decode('utf-8').replace('\r\n', '\n').split('\n')
h_t1 = next(i for i, l in enumerate(LL) if l.startswith('## Task 1'))
h_t4 = next(i for i, l in enumerate(LL) if l.startswith('## Task 4'))
h_t5 = next(i for i, l in enumerate(LL) if l.startswith('## Task 5'))
print('    Task1 @%d  Task4 @%d  Task5 @%d  Task4 节 %d 行' % (h_t1 + 1, h_t4 + 1, h_t5 + 1, h_t5 - h_t4))

preamble = [
    '# Task 4 简报 — 模板匹配器（`match.py`）',
    '',
    '> 抽取自 `Document/2026-10-06-实施计划02-智能处方引擎.md` @ commit `%s`'
    '（控制者用 python 从**已提交**状态抽，抽前验过工作树干净、blob 与工作树内容一致 —— 硬规矩 #48）。' % head,
    '> 内容 = 计划头部（**Global Constraints 10 条** / **Review Focus 5 条** / **File Structure**）'
    ' + **Task 4 全节**。',
    '> ⚠️ Task 4 全节里的 `P4-A1 … P4-A7` 标记是**控制者预检的更正与裁定**，完整依据在账本 '
    '`.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md` 的 '
    '`### Task 4: 模板匹配器 — 预检扫描（Pre-flight，控制者亲跑）` 一节。'
    '**以更正后的正文为准**；正文里凡写「原文……」的都是已被作废的旧说法。',
    '> ⚠️ **本 Task 最重要的两条裁定**：**P4-A3**（完整优先级链 '
    '`NO_LAYER → NO_BUCKET → NO_TEMPLATE → UNREACHABLE → NOT_APPROVED → MATCHED`，'
    '32 格穷举的 8/6/3/15 只在这条链下成立）与 **P4-A2**（读 `template.reachable` **字段**、'
    '不调 `is_reachable` 函数）。',
    '> ⚠️ 硬规矩的**定义**分两处：**#1–#47 在 Plan 01 账本** '
    '`.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md`（约 806 KB）；'
    '**#48–#76 在 Plan 02 账本**（上面那个 progress.md，约 296 KB）。'
    '**Plan 02 账本的裁定编号从 47 跳到 49，`Ruling 48` 号未使用**（已知勘误）。',
    '',
]
body = LL[:h_t1] + ['---', ''] + LL[h_t4:h_t5]
OUT = WS / 'task-4-brief.md'
OUT.write_bytes(('\n'.join(preamble + body)).encode('utf-8'))
o = OUT.read_bytes()
ot = o.decode('utf-8')
print()
print('    WROTE %s  %d B  %d 行' % (OUT.name, len(o), ot.count('\n')))
MUST = ['## Global Constraints', '## Review Focus', '## File Structure', '## Task 4: 模板匹配器',
        'P4-A1', 'P4-A2', 'P4-A3', 'P4-A4', 'P4-A5', 'P4-A6', 'P4-A7',
        'NO_LAYER  →  NO_BUCKET', 'is_reachable', '_PRESCRIPTION_PUBLIC_BASELINE',
        'match_template', 'MatchStatus', 'UNREACHABLE', 'NOT_APPROVED', 'NO_TEMPLATE',
        'Step 1', 'Step 2', 'Step 6', '32 个组合', 'test_match_is_deterministic_under_dict_ordering',
        '有效项不足', 'dominant_bucket', 'git grep -n "dominant_bucket"']
missing = [k for k in MUST if k not in ot]
print('    missing markers =', missing or 'NONE')
MUSTNOT = ['Create `backend/app/domain/prescription/match.py`、`backend/tests/domain/test_prescription_match.py`\n',
           '（`derive.py:330`，Ruling 175 补的测试）',
           '会变成 `NOT_APPROVED` 或 `MATCHED`']
print('    superseded survived =', [k[:40] for k in MUSTNOT if k in ot] or 'NONE')
gc = ot[ot.index('## Global Constraints'):ot.index('## Review Focus')]
print('    Global Constraints bullets =', len([x for x in gc.split('\n') if x.startswith('- ')]))
print('    简报里裸行号形态 `:NNN` 的出现次数 =', ot.count('`:1') + ot.count('`:2') + ot.count('`:3'))

import os
import pathlib
import subprocess

ROOT = pathlib.Path('.')

# ---------- (a) 账本 :999 的错交叉引用（Ruling 124 -> Ruling 121） ----------
WS = ROOT / '.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎'
L = WS / 'progress.md'
src = L.read_text(encoding='utf-8')
OLD = '⚠️ **出处勘误（Ruling 124 / 控制者错误 #115）**'
NEW = ('⚠️ **出处勘误（Ruling 121 / 控制者错误 #115；本行原先误标为「Ruling 124」，'
       '而 Ruling 124 讲的是 `.gitattributes` 的注释，见 :1526 —— 又一次引错裁定号，'
       '硬规矩 #55 的同类）**')
assert src.count(OLD) == 1, src.count(OLD)
src = src.replace(OLD, NEW, 1)

# ---------- (b) 计划 :741 的重复归属（CE-3）+ 空洞范围被低估 ----------
P = ROOT / 'Document/2026-10-06-实施计划02-智能处方引擎.md'
praw = P.read_bytes()
assert praw.count(b'\r\n') == praw.count(b'\n')
ptxt = praw.decode('utf-8').replace('\r\n', '\n')
POLD = '- §7.2 加勘误：指明 `speed_flexibility` 桶的参数空洞。'
PNEW = ('- ~~§7.2 加勘误：指明 `speed_flexibility` 桶的参数空洞。~~ —— **本项已由 Task 3 完成**'
        '（P3-A9 的裁定：写模板的人正是撞见空洞的人，隔 9 个 Task 再补勘误只会让 YAML 注释里的'
        '「见 spec §14 第 N 项」长期指向一个不存在的条目）。'
        '**⚠️ 且空洞比这一行说的大得多**（Task 3 实现者发现、控制者独立实算坐实）：'
        '不只是 `speed_flexibility` 桶，而是**整个黄层与绿层都没有任何强度数值**——'
        '18 套模板的 130 个 block 里 **82 个是 `intensity: {type: none}`**，'
        '按层统计 `intensity.type` 是 **绿 `{none}`、黄 `{none}`、红 `{hrmax_pct, none, onerm_pct}`**。'
        'spec §7.2 `:487` 只给了红层的 `60–70% HRmax` 与 `70% 1RM`，'
        '黄层写的是「持续跑+台阶训练」「自重+弹力带抗阻」（**动作名，没有强度**）、'
        '绿层写的是「兴趣球类/定向越野/功能性训练」（同样只有动作名）。'
        '**故原文那句「黄层按耐力那套的量」引用的是一个不存在的量。**'
        'Task 3 已把 6 条勘误写进 spec §7.2，本 Task 只需**复核**它们仍然成立。')
assert ptxt.count(POLD) == 1, ptxt.count(POLD)
ptxt = ptxt.replace(POLD, PNEW, 1)
P.write_bytes(ptxt.replace('\n', '\r\n').encode('utf-8'))
pa = P.read_bytes()
print('(b) PLAN bytes %d -> %d  纯CRLF=%s' % (len(praw), len(pa), pa.count(b'\r\n') == pa.count(b'\n')))

# ---------- (c) 账本：Task 3 亲验 + 结案 + Ruling 129-136 ----------
MARK = ('Task 3: 预检完成（11 处计划更正已落盘 + Task 12 的 §14 清单已同步、1 处 Critical、'
        '2 条新硬规矩 #75），派发中。代码基线 `c29bc69`、531 passed、15 张表、domain 441/120/100%。')
if src.count(MARK) != 1:
    cands = [l for l in src.split('\n') if l.startswith('Task 3: 预检完成')]
    assert len(cands) == 1, cands
    MARK = cands[0]

NEWSEC = """
#### Task 3 实现 — 控制者亲验（commit `4af83bc` + `ab075d3`，531 → **581 passed**，15 → **16 张表**）

**判定：Task 3 交付合格；两处 Critical 裁定（P3-A1 / P3-D2）都被正确执行；实现者另查出计划与 spec 的一个更大空洞（Ruling 133），并抓出控制者 4 条错误。**

亲验清单（全部控制者本机实跑，脚本 `.superpowers/sdd/_w.py`，跑完删除）：

| 项 | 亲验方式 | 结果 |
| --- | --- | --- |
| 581 passed | `cd backend; python -m pytest -q` | **581 passed in 64.03s** ✓ |
| domain 100% | `--cov=app/domain --cov-branch --cov-report=term-missing` | **499 stmts / Miss 0 / 120 branch / BrPart 0 / 100%**、`580 passed, 1 skipped` ✓；`templates.py` **58 stmts / 0 branch**、`prescription/__init__.py` **4 stmts**（441 + 56 + 2 = 499 ✓，**branch +0**） |
| 表数 | `len(Base.metadata.tables)` | **16**，`prescription_template` 在 ✓ |
| 改动面 | `git diff --name-status c29bc69 ab075d3` | **14 M + 74 A**；**`-- backend/app/seed`、`-- national_standard_2014.csv`、`-- backend/data/seed` 命中 0** ✓（**P3-A1 的裁定被执行：`app/seed/` 一个字没动**）；`exercises.py` 与 `exercise_equivalence.yaml` **0 命中、逐字未改** ✓ |
| 18 个 YAML | 逐个读字节 | **18 个文件、CRLF 全部 = 0**、合计 **123 848 B** ✓ |
| **P3-D2 生效** | `git ls-files --eol -- backend/data/` + `git check-attr` | **23 行全部 `i/lf w/lf attr/text eol=lf`**（不合形状 **0** 行）；`check-attr` 对 `backend/data/prescription/RED-END-ABN-01.yaml` 返回 **`text: set` / `eol: lf`**（改前是 `unspecified`）✓ |
| 指纹联动 | 自己算归一化 sha256[:16] | `exercises.yaml` **22 739 B / CRLF 0 / `3DE598AF38631209`**，与 `test_refdata_prescription.py` 里的 `EXERCISES_FINGERPRINT` **逐字相同** ✓；`exercise_equivalence.yaml` 仍是 **8245 B / CRLF 0 / `822CB86A5E998301`** ✓；CSV 仍是 **21412 B / `D2C8E539E2FA0029`** ✓ |
| ref 数与列宽 | 自己 `yaml.safe_load` | **24 个 ref**（23+1）；最长 `energy_expenditure_plus_5min_hiit` = **33** ≤ `String(48)` ✓ |
| 18 格全笛卡尔积 | 自己聚合 | 18 个 id 全唯一；`{(layer, weakness, body_comp)}` **== 3×3×2 的完整笛卡尔积** ✓ |
| `weekly_frequency` | 自己按层聚合 | **red {4} / yellow {3} / green {2}** ✓（spec §7.2 `:465` 的指导文件原文） |
| `sessions` 总数 | 自己数 | **54**（red 24 / yellow 18 / green 12）—— **控制者预检算的 54 成立** ✓ |
| 3 套不可达 | 自己筛 | `GRN-END-ABN-13` / `GRN-SPD-ABN-17` / `GRN-STR-ABN-15`，**恰为 `(green, *, abnormal)`** ✓；三套各有 **2 个 session**（**内容齐全**，符合实现者对 spec §7.1 `:447`②「模板位已就绪」的解读）✓ |
| `week_deltas` / `microcycle_weeks` | 自己聚合 | distinct 只有 **`(1.0, 1.05, 1.1, 0.85)`**、`microcycle_weeks` 全是 **4** ✓（spec `:479`） |
| 审校三元组 | 自己聚合 | `review.status` 全 **`approved`**、`reviewer` 全 **`原型自审（占位）`**、`reviewed_at` 全 **`2026-10-06`**（**固定日期，不是 `date.today()`**）✓ |
| `version` 的类型陷阱 | 自己查 `type()` | 全 18 套的 `version` 都是 **`str`**（不是 float）✓ —— 实现者在 §7.2 勘误里点了这个 PyYAML 陷阱（`1.0` 不加引号会被解析成 float），**已正确规避** |
| 引用完整性 | 自己比 | 模板引用的 **18 个 `exercise_ref` 全部在动作库里**（悬空 0）✓ |
| **P2-B2 的双所有者守卫** | 自己逐 block 比 | **130 个 block 的 `impact_level` 与动作库逐条一致，不一致 0** ✓ |
| addons | 自己聚合 | red 有 `body_fat_over → energy_expenditure_plus_10pct` 与 `muscle_low → resistance_priority`；yellow 有 `body_fat_over → energy_expenditure_plus_5min_hiit` 与 `muscle_low → resistance_priority`；**green 全空** ✓（与 P3 预检的裁定一致） |

**Ruling 129（CE-1，成立，控制者错误 #126，⚠️ 复用历史行号第 5 次）— 派单 §5 给的 `test_models.py:169/:236/:494` 与 `:492` 是 `966eae0` 上的位置，代码基线 `c29bc69` 上实测是 `:176/:243/:501` 与 `:499`。**

控制者亲跑三个 rev 复核：

```
966eae0 (750 行)：:24 函数名 | :169 / :236 / :494 三处 == 15 | :492 注释引用
c29bc69 (757 行)：:24 函数名 | :176 / :243 / :501 三处 == 15 | :499 注释引用
HEAD    (774 行)：:24 test_all_sixteen_tables_created | :184 / :253 / :518 三处 == 16 | :516 注释引用
```

**「3 处」这个数是对的，三个行号全错。** 账本 P3-A11 还把它记成「核对通过 ✓」——**因为我只核了「有几处」，没核「在哪几行」**（硬规矩 #57 的形态：核了推论没核输入）。

**⚠️ 最刺眼的一点**：Task 2 fix round 3 已经在 `test_models.py:36-41` 写下了「**按可 grep 的原文找，不要按裸行号找**：`git grep -n "== 15" -- backend/tests/db/test_models.py`」这段注释——**防我这个错误的守卫，就印在我引用的那个文件里，而我在派单里照样给了裸行号**。这是硬规矩 #61 扩写（Ruling 123）之后的**第一次再犯**。
**→ 补硬规矩 #76：派单里不许出现裸行号；需要指位置时一律给「可 grep 的原文片段 + `git grep` 命令」，行号只能作为绑定 rev 的辅助信息且必须标注 rev。** 依据：CE-7（fr2）→ Ruling 123（fr3-1）→ 本轮 CE-1，**同一个失效形态连续三轮**。

**Ruling 130（CE-3，成立，控制者错误 #127）— P3-A9 裁定「§7.2 勘误归 Task 3、Task 12 清单减一项」，但计划 `:741` 的 Task 12 清单里「§7.2 加勘误」原封不动地留着。**

亲验：`§7.2 加勘误` 在计划里出现在 Task 3 的 `:328`（P3-A9 的裁定）**与 Task 12 的 `:741`** 两处。**同一件事两处归属**——这正是硬规矩 #75（裁定改变了「一类做法」时要 grep 计划全文找同类）与 #66（同类陈述逐个更新）要防的形态，**而 #75 是我在写 P3-A1 的裁定时刚立的，同一轮就违反了**（第 4 次「立规矩的当轮违反」，前三次：#56→Ruling 73、#55→Ruling 74、#58→Ruling 102）。**已改**（并把空洞范围一并更正，见 Ruling 133）。

**Ruling 131（CE-2 / CE-4，成立，控制者错误 #128 / #129）**
- **CE-2（Minor）**：派单说「Task 3 追加 ref 的 5 项连带清单」在 `task-2-report.md` 的 `## fix round 3` 节，实测在 **`:639-640`（主体报告 §7 第 9 项）**，fr3 从 `:971` 起。**指向了错的位置**（硬规矩 #55/#61 的同类，第 5 次）。
- **CE-4（Minor，方法论）**：派单 §5 的「待改文件」表**一行里混了两个口径而没标注**——`bytes` 与 `CRLF` 是**工作树**值、`行` 与 `sha16` 是 **blob（LF）** 值。实现者逐行核出「工作树 bytes == blob bytes + CRLF 行数」12 行全部成立、12 个 sha 全部匹配 blob。**表头写的是「read_bytes 口径」，而按 `read_bytes()` 直接哈希得到的是另一个值**（如 `refdata_prescription.py` 实为 `97CD375BF47B7089`，表里给的 `EE0279B00D4AFB1B` 是归一化后的）。**→ 补进硬规矩 #70：报 sha256 时必须写明是「裸字节」还是「行尾归一化后」，同一张表里不许混用两种口径而不标注。**

**Ruling 132（CE-5 / CE-6 / CE-7 / CE-8 的处置）**
- **CE-5（不成立）**：派单说「3 套 unreachable 要不要有完整 `sessions`，控制者没法替你定」——实现者指出 **spec §7.1 `:447`② 已经给了答案**（「分层规则未来若调整…**模板位已就绪**」，空壳不是就绪）。**它是对的、我那句是多余的推诿**；控制者的倾向与它一致，故结果无差。**不计控制者错误**（派单同时给了倾向与理由，没有造成误动作），但**记下这个形态：把一个 spec 已回答的问题包装成「留给实现者定」，是把预检没做完的代价转嫁下去。**
- **CE-6（不成立，正面确认）**：基线测试态、依赖版本、12 行字节数、`.gitattributes` 四条规则、`check-attr` 改前输出、`Layer` / `ITEM_BUCKET` / 动作库 23 键、`SCANNED_DIRS` 27、`git diff c29bc69..ddccba8 -- backend` 为空 —— **逐项实测相符**。
- **CE-7（歧义，不计）**：简报「202 行」在 LF 口径下成立（`split('\n')` 口径 203）。**这是行尾口径的又一个侧面**，并入 Ruling 131 的 CE-4。
- **CE-8（歧义，不计）**：派单说加「8 个 dataclass」，实现者实加 **12 个公有顶层定义**（另加 `TEMPLATE_LAYERS` / `INTENSITY_TYPES` / `ADDON_TRIGGERS` 三个词表与 `is_reachable` 一个纯函数），故公开面 **7 → 20**。**四个新增的必要性它逐条给了理由**（词表是「合法取值」的唯一所有者、`is_reachable` 是 §7.1 `:445` 那条规则的唯一所有者）——**控制者采纳，且认为这比派单的「8 个」更好**：把 `reachable` 的判定规则做成一个纯函数，比让 18 个 YAML 各自写死布尔值更符合硬规矩 #3（单一所有者）。**派单说「8 个」是照抄计划 `:259-263` 的清单，没有算上词表与规则函数。**

**Ruling 133（实现者的新发现，控制者独立实算坐实，⚠️ 比计划已知的空洞大得多）— 整个黄层与绿层都没有任何强度数值。**

计划 `:285-289` 只把 `speed_flexibility` 桶（红/黄各 2 套 = 4 套）当成空洞，并给了处置「红/黄层的 speed_flexibility 模板用**该层已给出的强度区间**（红 60–70% HRmax、**黄层按耐力那套的量**）」。

**控制者独立实算 18 套 YAML 的 130 个 block**：
```
intensity.type distinct = ['hrmax_pct', 'none', 'onerm_pct']
按层 = { green: ['none'],  yellow: ['none'],  red: ['hrmax_pct', 'none', 'onerm_pct'] }
130 个 block 里 type == 'none' 的 = 82
```
**即黄层与绿层的全部 block 都没有强度数值**，而不只是 speed_flexibility 那 4 套。亲读 spec §7.2 `:487` 确认根因：它只给了**红层**的 `60–70% HRmax` 与 `70% 1RM`；**黄层**写的是「持续跑+台阶训练」「自重+弹力带抗阻」（**只有动作名**）、**绿层**写的是「兴趣球类/定向越野/功能性训练」（同样只有动作名）。

**→ 计划那句「黄层按耐力那套的量」引用的是一个不存在的量。** 这是 **P2-A2 / P2-A3 那个「借自本仓（或 spec）另一处真实机制」形态的第三次发生**，而前两次都在 Task 2 预检时被查出来了——**这一处藏在 Task 3 的 Step 2-5 正文里，预检时我核了 `:487` 的引文逐字相符（P3-A11），却没核「黄层按耐力那套的量」这半句是否有出处**。核了引文、没核基于引文的推论，**又是硬规矩 #57 的形态**。

**处置**：实现者的做法**正确**——12 套写 `{type: none}`、**不编造运动生理学参数**（Global Constraint 与计划 `:292` 的第 1 条都是这个意思），并把这个空洞写进 spec §7.2 的 6 条勘误之一。控制者已把计划 `:741` 一并更正（原文只说「指明 `speed_flexibility` 桶的参数空洞」，**范围被低估**）。**⚠️ 这直接影响 Task 5 与 Task 6**：`intensity.py` 的 HRmax 换算与 `assembler.py` 的第 2 步「模板给百分比 → 装配为个体绝对 bpm 区间」**对 82 个 block 无输入可用**，两个 Task 都必须显式处理 `type: none`（渲染成文字建议而不是绝对区间）。**已记进 Task 5 / Task 6 的预检清单第一项。**

**Ruling 134（实现者 9 条关切的裁定）**
1. **「带进 Task 3 的清单」10 项只做了 5 项，①②③⑧ 没做**（要改 `tests/architecture/*` 或新建 `tests/domain/test_prescription_exercises.py`，超出简报 Task 3 的 Files 段授权）→ **裁定：转 Task 4 预检清单**。理由：Task 4 建 `match.py`（domain 下又一个新模块），会**再次改变架构守卫的扫描面与相对导入计数**，那正是把 `cases` 矩阵换成「扫真仓逐个对拍 `resolve_name`」、把 `_package_of` 断言换成「扫真仓与 `parent.parts` 对拍」的最佳时机（Ruling 56 / 66 已这么裁过）。**⑧（`test_impact_rank_values_are_pinned_verbatim` 的 docstring 缺时点）也一并归 Task 4。**
2. **`hiit` 没有任何模板引用、但等价表有它 2 条映射（删不得）** → **接受为预期**。亲验：动作库 24 个 ref 里**没被任何模板 block 引用的有 6 个**——`brisk_walking` / `stationary_cycling`（都是等价表的**替换目标**）、`energy_expenditure_plus_10pct` / `energy_expenditure_plus_5min_hiit` / `resistance_priority`（都是 **addon 模块**，走 `addons` 不走 `blocks`）、`hiit`（等价表里出现）。**即「不被模板引用」不等于「没人用」**，这 6 个各有各的消费方。**但 `hiit` 的消费方只有等价表**，若 Task 7 落地后发现它既不是任何替换的目标也不是任何来源，就该删——**记进 Task 7 预检清单**。
3. **绿层 `addons: []` 让 spec §7.4 `:510`（体脂率异常 → 追加能量消耗模块）对绿层无模块可追加** → **接受为已知边界**，实现者**没有自行占 §14 编号**（正确，它只被授权 #29/#31）。**裁定：归 Task 7 登记**——`safety.py` 实现 §7.4 的三个触发时，「绿层 + 体脂率异常」这一格会真实出现（绿层的 `C` 判定为假，但 §7.4 的第三个触发是「体脂率异常」而不是 `C`，两者不等价），**那时才知道它是「无动作」还是「需要新模块」**。
4. **`hiit`(high, 有映射) 与 `energy_expenditure_plus_5min_hiit`(medium, 无映射) 的不对称** → BMI > 30 的黄层学生会「主项被换掉、追加模块原样保留」。**裁定：归 Task 7 预检裁一次**（那是 `safety.py` 的语义决定，不是动作库的）。**这条是本轮最有价值的前瞻发现之一。**
5. **`structure` 的键没有 spec 条文定义语义，而 Task 6 必须认得那五个键** → 已登记进 #31 的影响面 ✓。**记进 Task 6 预检清单。**
6. **18 套里同一套每一天 `focus`/`blocks` 完全相同**（指导文件没按周内第几天给参数）→ **接受**，改它就得编造。已并入 #29 ✓。
7. **`Intensity` 的 `rpe` 档今天无真数据用例**（18 套的 `intensity.type` 只有 `hrmax_pct` / `onerm_pct` / `none`）→ **接受**。`rpe` 是 spec §7.2 与 Task 5/6 要用的档（RPE 是 §8.2 课堂快评的量），**今天没有模板用它不是缺陷**；但**它是一个「枚举成员无消费者」的状态，Task 5 落地时必须让它有用例**，否则 domain 覆盖率虽然不受影响（枚举成员不产生 branch），却留了一个永不执行的取值。
8. **账本 P2-A4 的错引用号仍在 `progress.md:999`** → **不成立**：控制者已在 Task 2 fr3 那轮就地勘误（`:999` 现在带「⚠️ 出处勘误」段）。**但该勘误自己引错了裁定号**（写「Ruling 124」，实际是 Ruling 121）——**实现者 grep 到的正是那段勘误里被复述的旧号**。**这恰好是硬规矩 #74 说的形态：更正说明里逐字复述了被撤销的原句，于是串查会命中、让人以为错误还在。** 控制者已把裁定号改对，并按 #74 把复述改成描述式。
9. **`test_domain_purity.py:369-371` 与 `test_layering.py:386-388` 的「子包今天不存在」注释已过期**（`app/domain/prescription/` 从 Task 2 起就存在了；用例本身正确）→ **成立，转 Task 4 预检清单**（与第 1 项同一批，都要动 `tests/architecture/*`）。

**Ruling 135（实现者自纠 6 条，记录）**
两处 grep 计数是**预测的**（实为 6/5 而不是 7/4）；**编辑工具对报告文件「报成功而磁盘未写」并回显了 diff**（文件与备份逐字节相同才查出来）→ 改 python 字节级重写 + 双向串查。**这是工具/磁盘分歧家族的第 60 次**，也是「连 diff 一起伪造」这个形态的第二次。另 4 条见报告 §9.3。**6 条全部自纠，其中 2 条被它自己写的断言/闸门拦下**——硬规矩 #53 与 #48 的升级版正在起作用。

**Ruling 136（实现者对四处钉死基线的处置，控制者裁定都接受）**
1. `_PRESCRIPTION_PUBLIC_BASELINE` 从「7 个裸名字」改成「**20 个 `(名字, 所有者模块)` 二元组**」+ `len == 20`。理由（成立）：公开面现在横跨三个所有者模块（`exercises` / `templates` / 包本身），**硬编码单一模块会对新名字全部取到 `None`**；改成二元组后仍是**字面清单**（没有从被测对象反推，硬规矩 #35 守住）。
2. `:951` 那条负向断言的哨兵从 `+ ["Template"]` 换成 `"__NOT_IN_THE_PUBLIC_FACE__"`。理由（成立，且这正是派单要求它「重新想用意并说明」的那一条）：**`Template` 真的进入公开面之后，`baseline + ["Template"]` 退化成「多一个已有名字」，守的东西悄悄换了**；换成一个永不在公开面的哨兵串，才继续守「基线不是当前值加一」。
3. `templates.__all__` 的字面清单从 1 个扩到 **14 个**，**守卫本身没删** ✓（硬规矩 #67 的要求）。
4. `REFERENCE_TABLES` 的**定义（`:496`）与钉死断言（`:542`）两处同步**改成 `("exercise", "prescription_template")` ✓（P3-A6 第 4 项）。

**控制者错误计数**：Task 1 共 33 次（#61–#93）、Task 2 共 23 次（#94–#123 中的 Task 2 部分）、**Task 3 预检 2 次（#124 = P3-A1 的裁定未传导、#125 = P3-D2 的 `.gitattributes` 覆盖面没验）+ Task 3 实现轮 4 次（#126 CE-1 行号 / #127 CE-3 重复归属 / #128 CE-2 指错位置 / #129 CE-4 口径混用）+ Ruling 133 那处「黄层按耐力那套的量」无出处（#130）+ 账本 `:999` 引错裁定号（#131）** = **Plan 02 累计 71 次**；Plan 01 60 次，**合计 131 次**。
**实现者 3 次**（全部自纠）。**评审者 4 次**。**复审者 1 次**。

**补硬规矩 #76（派单不许出现裸行号）与 #70 的扩写（sha256 必须标明裸字节还是归一化）**，定义见 Ruling 129 / 131。

---

## ✅ Task 3 结案（18 套模板 + `prescription_template` 表 + 加载器）

**commit**：`4af83bc`（主体，53 个条目）+ `ab075d3`（报告补 commit 后证据）。
**测试**：Task 2 结案 **531** → Task 3 **581 passed**（+50）。
**覆盖**：`app/domain/` **499 stmts / Miss 0 / 120 branch / BrPart 0 / 100%**（Task 2 结案是 441/120；**stmts +58、branch +0**）。
**表数**：15 → **16**。
**fix round**：**0/5**（一次通过，没有 fix round）——这是 Plan 02 迄今唯一一轮零 fix 的 Task。
**Critical**：**0**。两处 Critical 都在**预检**阶段被控制者自己查出并改掉（P3-A1 / P3-D2），**没有进到实现**。

**交付**：18 个模板 YAML（`backend/data/prescription/`，123 848 B，CRLF 全 0）、`prescription_template` 表、`templates.py` 的 12 个公有定义、`load_templates()` / `templates()` / `sync_templates(session)`、`tests/domain/test_prescription_templates.py` 从 4 条扩到 **42 条**、`.gitattributes` 加 `backend/data/**/*.yaml text eol=lf`、`exercises.yaml` 追加 `energy_expenditure_plus_5min_hiit`（24 个 ref，指纹 `3DE598AF38631209`）、spec §14 追加 **#29 / #31**、spec §7.2 加 **6 条勘误**。

**⚠️ 带进 Task 4 的清单**：① `cases` 矩阵换成扫真仓对拍 `resolve_name`（Ruling 56/66）② `_package_of` 断言换成扫真仓对拍 `parent.parts`（C-fr4-1）③ `lookup()` 的分支测试搬到 `tests/domain/test_prescription_exercises.py`（Ruling 107-1）④ `test_impact_rank_values_are_pinned_verbatim` 的 docstring 缺时点（Ruling 134-1）⑤ 两份架构守卫的「子包今天不存在」注释已过期（Ruling 134-9）⑥ `match.py` 若写 `level == 2` 相对导入，全仓计数与 level 分布要更新（Task 2 fr2 改过的那几段散文）⑦ **`match.py` 必须拒绝 `Layer.INSUFFICIENT`**（计划 `:255`）与 **`review_status != approved` 的模板**（spec §7.2 `:451`），且 Task 3 已把「构造一个 `PENDING` 的 `Template` 是可能的」证好了（P3-A8）⑧ 4 处钉死基线的更新模式（Ruling 136）可复用。
**⚠️ 带进 Task 5 / 6 的清单（Ruling 133，最要紧）**：**82 个 block 的 `intensity.type == 'none'`**，`intensity.py` 与 `assembler.py` 必须显式处理「模板没给强度」这一档（渲染文字建议，不换算绝对区间）；`structure` 的五个键没有 spec 语义（Task 6 要认得它们）；`Intensity.rpe` 今天无消费者，Task 5 要给它用例。
**⚠️ 带进 Task 7 的清单**：`hiit`(high, 有映射) 与 `energy_expenditure_plus_5min_hiit`(medium, 无映射) 的不对称；绿层 `addons: []` 与 spec §7.4 `:510` 的冲突（并登记 §14）；`hiit` 是否真有消费方。

Task 3 结案。**下一步：Task 4（模板匹配器 `match.py`）预检。** 代码基线 `ab075d3`、**581 passed**、**16 张表**、domain **499/120/100%**、SQLAlchemy 2.1.3。
"""

L.write_text(src.replace(MARK, MARK + "\n" + NEWSEC, 1), encoding='utf-8')
out = L.read_bytes().decode('utf-8')
print()
print('(a)(c) LEDGER OK', len(L.read_bytes()))
for k in ('Task 3 实现 — 控制者亲验', 'Ruling 129（', 'Ruling 130（', 'Ruling 131（', 'Ruling 132（',
          'Ruling 133（', 'Ruling 134（', 'Ruling 135（', 'Ruling 136（',
          '## ✅ Task 3 结案', '补硬规矩 #76', 'Ruling 121 / 控制者错误 #115'):
    print('  %-30s %d' % (k, out.count(k)))

# ---------- (d) commit ----------
tmp = pathlib.Path(os.environ['TEMP']) / 'pe_cm11.txt'
tmp.write_bytes(
    ("feat: Plan02 Task3 处方模板（账本 Ruling 129-136 + Task 3 结案）+ 计划 :741 重复归属更正\n\n"
     "Task 3 一次通过、零 fix round：531 -> 581 passed、15 -> 16 张表、domain 441/120 -> 499/120 仍 100%。\n"
     "18 套模板 YAML（123848 B、CRLF 全 0）+ prescription_template 表 + load_templates/sync_templates。\n"
     "P3-D2 生效：git ls-files --eol 23 行全部 i/lf w/lf attr/text eol=lf。\n\n"
     "Ruling 133（实现者发现、控制者独立实算坐实）：整个黄层与绿层没有任何强度数值——\n"
     "130 个 block 里 82 个是 intensity:{type:none}，按层是 绿{none}/黄{none}/红{hrmax_pct,none,onerm_pct}。\n"
     "计划原文「黄层按耐力那套的量」引用的是一个不存在的量（spec §7.2:487 只给了红层的数值）。\n"
     "已更正计划 :741（那里还把「§7.2 加勘误」重复归属给 Task 12，与 P3-A9 的裁定冲突）。\n"
     "直接影响 Task 5/6：intensity.py 与 assembler.py 必须显式处理 type:none 这一档。\n\n"
     "控制者错误累计 131 次（本轮 +6：复用历史行号第 5 次、裁定未传导到计划另一处、\n"
     "指错报告位置、sha256 口径混用、黄层强度无出处、账本引错裁定号）。补硬规矩 #76。\n").encode('utf-8'))
subprocess.run(['git', 'add', '-A', 'Document', '.superpowers'], capture_output=True, text=True)
r = subprocess.run(['git', 'commit', '-q', '-F', str(tmp)], capture_output=True, text=True)
print()
print('commit rc =', r.returncode, r.stderr.strip()[:200])
tmp.unlink()
print(subprocess.run(['git', 'log', '--oneline', '-3'], capture_output=True, text=True).stdout)
print('git status --short = %r' % subprocess.run(['git', 'status', '--short'],
                                                 capture_output=True, text=True).stdout)

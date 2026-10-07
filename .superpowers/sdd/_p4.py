import pathlib

ROOT = pathlib.Path('.')

# ============ (a) 计划正文 Task 4 的 7 处更正 ============
P = ROOT / 'Document/2026-10-06-实施计划02-智能处方引擎.md'
praw = P.read_bytes()
assert praw.count(b'\r\n') == praw.count(b'\n')
ptxt = praw.decode('utf-8').replace('\r\n', '\n')

E = []

# P4-A6: Files 段严重不全
E.append((
    '**Files:** Create `backend/app/domain/prescription/match.py`、'
    '`backend/tests/domain/test_prescription_match.py`',
    '**Files:**\n'
    '- Create: `backend/app/domain/prescription/match.py`、`backend/tests/domain/test_prescription_match.py`\n'
    '- Modify（⚠️ **P4-A6：原文一个字都没提，但本 Task 必然要动**）：\n'
    '  - `backend/app/domain/prescription/__init__.py` —— 公开面重导出 `MatchInput` / `MatchOutcome` / '
    '`MatchStatus` / `match_template`（`__all__` 从 **20** 个名字扩到 20+N）\n'
    '  - `backend/tests/test_refdata_prescription.py` —— `_PRESCRIPTION_PUBLIC_BASELINE`'
    '（今天是 **20 个 `(名字, 所有者模块)` 二元组**）与它的 `assert len(...) == 20`'
    '（可 grep 原文：`基线是 20 个名字，抄漏了就当场红`）**两处都要改**；'
    '**新基线仍必须是字面清单**，不得改成 `list(pkg.__all__)`（硬规矩 #35）。'
    '更新模式照 Task 3 的 Ruling 136-1\n'
    '  - `backend/tests/architecture/test_domain_purity.py` 与 `test_layering.py` —— '
    '**三处已过期/写错的陈述**（控制者亲扫定位，按可 grep 的原文找）：\n'
    '    ① `# Task 2 会新建 app/domain/prescription/ 子包（今天不存在）` —— '
    '**子包自 Task 2 起就存在、Task 3 已填满**；\n'
    '    ② `但 ``app/domain/prescription/`` 这一层子包已经建出，Task 3 的 ``match.py`` 一写` —— '
    '**`match.py` 是 Task 4 的，不是 Task 3 的**；\n'
    '    ③ `# Task 2 的形状（fix round 5 新加，Plan02 Ruling 67）：app/domain/prescription/match.py` —— '
    '那一格矩阵是 **Task 1 fix round 5** 为 **Task 4** 的形状埋的，归属写错了两处。\n'
    '    另：全仓相对导入的计数今天是 **16**（全部 `level == 1`），'
    '`match.py` 若写相对导入会变 17；架构守卫的扫描面今天是 **27**'
    '（pipeline 7 + db 11 + domain 9），加 `match.py` 后是 **28**——'
    '**这些数散在两份守卫的 docstring 里多处，改前先 grep（硬规矩 #66）**\n'
    '  - **本 Task 还要接手 Task 3 转来的 4 项**（账本 Ruling 134-1，都在这两个架构守卫文件与 '
    '`tests/domain/` 下）：① `cases` 矩阵换成「扫真仓每个 `.py` 逐个对拍 `resolve_name`」'
    '（Ruling 56/66，可一次性解决 Ruling 54/56/67 三条）；② `_package_of` 的断言换成'
    '「扫真仓每个 `.py` 与 `py.relative_to(BACKEND).parent.parts` 对拍」（C-fr4-1）；'
    '③ `EquivalenceTable.lookup()` 的分支测试搬到新建的 '
    '`tests/domain/test_prescription_exercises.py`（Ruling 107-1：它今天住在 '
    '`tests/test_refdata_prescription.py`，失效形态是「删那两条测试、`pytest` 退出码仍 0、'
    '只有 `BrPart` 变红」）；④ `test_impact_rank_values_are_pinned_verbatim` 的 docstring '
    '缺「本条之前」这个时点（Ruling 127-5）。\n'
    '    **⚠️ ①②③ 会让 passed 数变化，属预期，逐条说明。若你判断某一项该推到 Task 5，'
    '报为关切并说明理由——不要为了「符合派单」而硬做。**'))

# P4-A1: Consumes 清单不全
E.append((
    '- Consumes: Task 3 的 `Template` / `WeaknessBucket` / `BodyCompState`；'
    'Plan 01 的 `app.domain.stratify.Layer`',
    '- Consumes: Task 3 的 `Template` / `WeaknessBucket` / `BodyCompState` / '
    '**`ReviewStatus`**（`NOT_APPROVED` 要用，控制者实跑其成员 = '
    '`PENDING="pending"` / `APPROVED="approved"`）/ **`is_reachable`**（见 P4-A2）；'
    'Plan 01 的 `app.domain.stratify.Layer`'
    '（⚠️ **P4-A1：原文漏了 `ReviewStatus` 与 `is_reachable` 两个**——'
    '前者是 `NOT_APPROVED` 的判据来源，后者是 `reachable` 规则的**唯一所有者**，'
    '而它的 docstring 里明写「**两处消费**：① 加载器…；② **Task 4 的匹配器按它排除预留位**」。'
    '另注：Task 3 已把 `Layer` **re-export** 进 `templates`，故 `from .templates import Layer` '
    '与 `from app.domain.stratify import Layer` 都可用；'
    '**唯一所有者是 `app.domain.stratify`，选哪条路径要在 docstring 里说明**）'))

# P4-A2 + P4-A3: reachable 的读法 + 完整优先级链
E.append((
    '实现要点：匹配键是 `(layer.value, dominant_bucket, "abnormal" if body_comp_abnormal else "normal")`；'
    '先查 `reachable`、再查 `review_status`，**顺序是承重的**——'
    '一套既不可达又未审校的模板应该报 `UNREACHABLE`（那是规格事实）而不是 `NOT_APPROVED`（那是流程状态）。'
    '**把这个顺序的理由写进 docstring。**',
    '实现要点：匹配键是 `(layer.value, dominant_bucket, "abnormal" if body_comp_abnormal else "normal")`。\n'
    '\n'
    '⚠️ **P4-A3：完整的优先级链原文没有给出，而 32 格穷举的期望表完全依赖它。** '
    '原文只说了相邻的一对（`reachable` 先于 `review_status`）。'
    '**控制者按 `:386-389` 的分类实算过 32 格**，得到 `{NO_LAYER: 8, NO_BUCKET: 6, '
    'UNREACHABLE: 3, MATCHED: 15}`（**与原文的 8/6/3/15 逐字相符**），'
    '而这个分类**只在下面这条链下成立**：\n'
    '\n'
    '```\n'
    'NO_LAYER  →  NO_BUCKET  →  NO_TEMPLATE  →  UNREACHABLE  →  NOT_APPROVED  →  MATCHED\n'
    '```\n'
    '\n'
    '**承重的两处**：\n'
    '- **`NO_BUCKET` 必须先于 `UNREACHABLE`**：`(green, None, abnormal)` 这一格'
    '同时满足「桶为空」与「绿层+异常」，**原文的 6 个 `NO_BUCKET` 里包含它**，'
    '所以它必须判 `NO_BUCKET`。若顺序反过来，分类会变成 `{NO_LAYER:8, NO_BUCKET:4, '
    'UNREACHABLE:5, MATCHED:15}`——**总数仍是 32，穷举测试仍会「通过」某个版本，'
    '但期望表就换了**。这是「顺序承重」最隐蔽的形态：错了也不会让计数对不上。\n'
    '- **`NO_TEMPLATE` 必须先于 `UNREACHABLE`/`NOT_APPROVED`**：查不到模板就没有 '
    '`reachable` / `review_status` 可读。\n'
    '- `UNREACHABLE` 先于 `NOT_APPROVED`（原文已给）：一套既不可达又未审校的模板报 '
    '`UNREACHABLE`（**规格事实**）而不是 `NOT_APPROVED`（**流程状态**）。\n'
    '\n'
    '**把整条链与这三处理由写进 `match_template` 的 docstring**，'
    '并在穷举测试里**按链的顺序组织期望表**（读者能从表的排列看出顺序是被测的）。\n'
    '\n'
    '⚠️ **P4-A2：「先查 `reachable`」有歧义——查的是 `Template.reachable` 这个**字段**，'
    '还是调 `is_reachable(...)` 这个**函数**？** 控制者实跑：`is_reachable` 的函数体是 '
    '`return not (layer is Layer.GREEN and body_comp is BodyCompState.ABNORMAL)`，'
    '它的 docstring 自称「``reachable`` 的**唯一所有者**」，并说加载器用它校验 YAML 里写的 '
    '`reachable` 与维度组合不矛盾（矛盾就在加载时响亮失败）。\n'
    '\n'
    '**裁定：`match.py` 读**字段** `template.reachable`，不调 `is_reachable`。** 理由：'
    '① `is_reachable` 是**规则的**唯一所有者，而**数据的**唯一所有者是 YAML 的 `reachable` 字段，'
    '加载器已经强制两者一致——匹配器再算一遍就是**第三个住址**（违反 Global Constraint #3）；'
    '② `match_template` 是**消费者**，它吃的是「已经过校验的 `Template`」，'
    '重新推导会掩盖「加载器没校验」这个真故障；'
    '③ 读字段让 `test_match_rejects_an_unapproved_template` 那类'
    '**直接构造 `Template` 实例**的测试（`:392`）行为可预测——'
    '构造时写什么 `reachable` 就是什么。\n'
    '**但 `match.py` 的 docstring 必须写明**：规则的所有者是 '
    ':func:`app.domain.prescription.templates.is_reachable`，本函数只消费加载器已校验过的字段；'
    '**若有人绕过加载器手工构造了一个 `reachable` 与维度矛盾的 `Template`，本函数不会发现**'
    '（硬规矩 #39：写清守不住什么）。'))

# P4-A7: Z0 文案的确切原文
E.append((
    '`reason` 要复用 Plan 01 `stratify.explain()` 的 Z0 文案口径，不要另造一套说法。',
    '`reason` 要复用 Plan 01 `stratify.explain()` 的 Z0 文案口径，不要另造一套说法。'
    '**（P4-A7：控制者实跑取到确切原文，免得实现者自己造第二套）**'
    '`app/domain/stratify.py` 的 `_REASON` 映射里，`RuleId.Z0` 对应的是 '
    'f-string **`f"有效项不足 {MIN_VALID_COUNT} 项，本日不分层"`**；'
    '`explain()` 在 `:326`，其 Z0 分支的说明是「`Z0` 路径单独成句：它没有颜色可报，'
    '要说的是「为什么没有分层结果」以及下一步」。'
    '**`NO_LAYER` 的 `reason` 应当与这条同源**——'
    '要么直接复用 `_REASON[RuleId.Z0]`（import 它），要么逐字引用并注明出处；'
    '**不要另写一句意思相近的话**（那就是第二个所有者）。'))

# P4-A5: derive.py:330 是空行
E.append((
    'Plan 01 的 `find_weaknesses` 在 6 项全缺测时返回 `dominant_bucket = None`'
    '（`derive.py:330`，Ruling 175 补的测试）',
    'Plan 01 的 `find_weaknesses` 在 6 项全缺测时返回 `dominant_bucket = None`'
    '（⚠️ **P4-A5：原文引的 `derive.py:330` 是**空行**。**控制者实跑定位的真实位置**：'
    '字段声明 `dominant_bucket: str | None` 在 `derive.py:129`（`WeaknessResult` 的字段）、'
    '口径说明在 `:320` 起的 docstring、赋值处 `dominant_bucket=dominant` 在 `:371`；'
    '「按声明序取先出现者」的 `_BUCKET_ORDER` 在 `:77`、消费在 `:352`/`:356`。'
    '**原文说的「Ruling 175 补的测试」控制者没有核**（那是 Plan 01 账本里的裁定号，'
    '本轮没去查）——**实现者若要引用它，自己核一遍**（硬规矩 #52/#61）。'
    '**按可 grep 的原文找：`git grep -n "dominant_bucket" -- backend/app/domain/derive.py`**）'))

# P4-A4: 变异 ① 的后果写错了
E.append((
    '变异：① 把 `reachable` 检查删掉 → 3 个 `UNREACHABLE` 组合会变成 `NOT_APPROVED` 或 `MATCHED`，'
    '穷举测试必须红；',
    '变异：① 把 `reachable` 检查删掉 → **3 个 `UNREACHABLE` 组合会全部变成 `MATCHED`**，'
    '穷举测试必须红（⚠️ **P4-A4：原文写「变成 `NOT_APPROVED` 或 `MATCHED`」——'
    '18 套模板今天**全部** `review.status: approved`（控制者实跑：`review.status` 的 distinct 值'
    '只有 `approved` 一个），故删掉 `reachable` 检查后**只可能是 `MATCHED`，不可能是 `NOT_APPROVED`**。'
    '按硬规矩 #65，变异判据要写明**哪个断言分支**开火：这里是穷举测试里那 3 格的 '
    '`status` 期望值）；'))

n = 0
for old, new in E:
    c = ptxt.count(old)
    assert c == 1, ('anchor %d 次: %r' % (c, old[:70]))
    ptxt = ptxt.replace(old, new, 1)
    n += 1
P.write_bytes(ptxt.replace('\n', '\r\n').encode('utf-8'))
pa = P.read_bytes()
pat = pa.decode('utf-8')
print('(a) 计划更正 %d 处  bytes %d -> %d  纯CRLF=%s'
      % (n, len(praw), len(pa), pa.count(b'\r\n') == pa.count(b'\n')))
for k in ('P4-A1', 'P4-A2', 'P4-A3', 'P4-A4', 'P4-A5', 'P4-A6', 'P4-A7',
          'NO_LAYER  →  NO_BUCKET', 'is_reachable', '_PRESCRIPTION_PUBLIC_BASELINE',
          '有效项不足 {MIN_VALID_COUNT} 项，本日不分层'):
    print('    %-46s %d' % (k, pat.count(k)))

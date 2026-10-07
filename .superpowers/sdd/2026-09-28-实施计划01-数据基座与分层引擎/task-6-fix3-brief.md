# Task 6 — Fix Round 3 派单简报

分支：`feature/plan-01-data-foundation`
基线 commit：`1fbc35f`（工作树干净，勿 rebase、勿 reset、勿切分支）

fix round 2 的复审判 **PASS_WITH_CONCERNS**：上一轮的 C1/C2/M1/M2/M5 与 4 条 Minor **全部真修好**，新增 Critical **0** 条。本轮只修复审新发现的 **3 条必修 Minor + 1 条注释**，范围很小，**不要顺手做别的**。

---

## 0. 环境（照旧，本项目已因这些吃过 9 次写盘事故）

- Windows + **PowerShell**：分隔用 `;`，**绝不用 `&&`**；**没有 heredoc**（多行脚本写临时 `.py`，**用完删掉**）。
- **没有 venv**。`pytest` **必须在 `backend/` 下跑**。`bash` 需要时先 `$env:PATH = "C:\Program Files\Git\bin;$env:PATH"`。
- **每次编辑后用 shell 复核字节真落盘**（`Select-String -Path <file> -Pattern "<独特串>" -SimpleMatch`），不要只信工具返回值。
- **不得创建或触碰 `backend/pe.db`**（Ruling 68），**不得重新生成 `backend/data/seed/*.csv`**（那三个文件刚被控制者删掉，它们是 fix round 1 的过期产物；`data/seed/` 现在是空目录，保持它空）。需要 CSV 就写到 `%TEMP%` 下的临时目录。
- 只提交**一个** commit。
- 做不到 / 认为简报写错了 → **写进报告关切**，不要静默绕过、不要自作主张改设计。前两轮 16 条关切里有 **8 条证明是控制者自己写错了**，上报矛盾是这份工作最有价值的产出。

---

## 1. 先读

1. `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/task-6-review-round2.md` 的 `### Minor` 段（复审报告，64137 字节）——本轮 4 条任务的原始描述与取证。
2. `progress.md` 的 `### Task 6` 段末尾「本轮一并处置的复审 Minor」与「延后 Minor」两个清单——**哪些必修、哪些明确延后不要碰**，以那里为准。
3. `backend/tests/seed/test_generate.py:489-600`（AST 守卫与它的 20 条自证测试 + 1 条负对照）。
4. `backend/app/seed/generate.py:333-365`（`_cell`）。
5. `backend/app/seed/fitness.py` 的 `:606`、`:618`（两处 `ValueError`）与 `:805`、`:813`（两处 `RuntimeError`）。
6. `backend/app/seed/fitness.py:509-572`（`_delta_target_windows`，特别是 `:558`）。

---

## 2. 任务

### 2.1 AST 随机源守卫补 `np.random.*` 旧式全局函数（必修）

**现状缺口**（控制者已亲验 `test_generate.py:509-512`）：`RNG_SOURCES` 覆盖的是「造生成器 / 播种 / 派生子流」那一类名字（`RandomState`、`Generator`、`SeedSequence`、`seed`、`PCG64` 系、`spawn`、`fork`），**完全没有覆盖 `np.random.rand` / `normal` / `uniform` / `random` / `randint` / `choice` / `shuffle` / `permutation` / `standard_normal` 这些旧式全局采样函数**。

**为什么这是必修而不是洁癖**：这些函数从 numpy 的**全局单例 RNG** 取数，是货真价实的「隐藏第二随机源」——它不受 `cfg.seed` 控制，会让「同种子字节级一致」静默失效，而且失效方式是最难查的那种：每次跑都是合法数据，只是每次都不一样。这个 AST 守卫是可复现性的**最后防线**（前两道是「唯一根生成器」与「SHA256 取证」，两者都只能事后发现、不能定位），漏掉正门等于没有守卫。

**要做**：
- 在 `RNG_SOURCES` 之外新增一个**独立**的禁用集合（例如 `RNG_GLOBAL_FUNCS`），装 numpy 旧式全局采样函数名。**不要把它们混进 `RNG_SOURCES`**——两个集合的语义不同（一个是「造源」，一个是「用全局源」），混在一起会让违规消息失去指向性。
- `_offenders_in` 里按现有的「末段属性名」方式匹配（`head = text.rsplit(".", 1)[-1]`），使 `np.random.normal(...)`、`numpy.random.normal(...)`、`from numpy.random import normal` + `normal(...)` 三种写法**一律抓住**。注意第三种：`from numpy.random import normal` 之后调用点的 `head` 就是 `normal`，与第一种同形，所以按末段名匹配天然覆盖——但要**确认** `import` 那一行本身也不会漏（现有代码对 `from random import …` 有专门分支，`from numpy.random import …` 有没有？请核实，没有就补）。
- **小心误伤**：`Generator` 对象上也有 `.normal()` / `.uniform()` / `.choice()` / `.shuffle()` / `.permutation()` / `.integers()` 方法，而**那是唯一合法的用法**（根生成器被显式传进每个生成器）。按「末段属性名」一刀切会把合法调用全部判成违规，`app/seed/` 立刻全红。所以匹配必须**带上接收者**：只有当 `text` 形如 `np.random.<fn>` / `numpy.random.<fn>`（即末段名的前一段是 `random`、再前一段是 `np`/`numpy`）或裸 `<fn>`（来自 `from numpy.random import <fn>`）时才算违规；`rng.normal(...)`、`self._rng.uniform(...)` 这类**必须放行**。请在 docstring 里把这条区分写清楚，并**用测试双向钉住**（违规的抓、合法的放）。
- **自证测试**：按本轮已立的规矩（守卫必须自带自证测试），为**每一种**新增禁用写法各加一条参数化用例，形式与现有 20 条一致——把违规源码写进 `tmp_path` 下的假模块，断言 `_offenders_in` 对它返回违规。同时加**负对照**：把 `app/seed/` 里现有的合法 `rng.normal(...)` / `rng.uniform(...)` / `rng.permutation(...)` / `rng.integers(...)` 调用喂进去，断言**零违规**。

### 2.2 `_cell` 补 `np.floating`（必修）

**现状缺口**（控制者已亲验 `generate.py:353-365`）：分支是 `None` → `dict` → `float` → `np.integer` → 兜底 `return value`。而 **`np.float32` 不是 Python `float` 的子类**（只有 `np.float64` 是），也不是 `np.integer`，于是它**掉进兜底分支原样返回**：
- 绕过 `repr(float(value))` 转换 → numpy 2.x 的 `repr(np.float32(1.5))` 是 `'np.float32(1.5)'`，这种字符串会原样落进 CSV，适配器 `float()` 解析时抛 `ValueError` 并中断整批抽取；
- **同时绕过 `math.isfinite` 检查** → `np.float32('nan')` 会把字面量 `nan` 写进 CSV。

**为什么必修**：`allow_nan=False` + 写侧有限性检查是 Ruling 39 的承重设计（一个 NaN 能原样写盘、原样读回、全程零报错，最后在与任何阈值比较时恒为假）。被一个 `float32` 整体绕过去，等于这条防线不存在。docstring 里那句「生成器目前每一处都包了 `float(...)`，所以这条缺陷尚未触发」正是**「尚未触发」不等于「不可达」**——守卫的价值就在于把「将来漏包一次」从运行时事故变成结构性不可达，而它现在对 `float16/32/longdouble` 做不到这件事。

**要做**：把浮点分支的判据从 `isinstance(value, float)` 扩成 `isinstance(value, (float, np.floating))`（`np.floating` 覆盖 `float16/32/64/longdouble`），进分支后先 `value = float(value)` 再做有限性检查与 `repr`。`np.integer` 分支保持不变。更新 docstring 说明为什么判据必须是 `np.floating` 而不是 `np.float64`（**在注释里写明「只有 `np.float64` 是 `float` 的子类」这个 numpy 事实**，否则后来人会以为 `isinstance(value, float)` 已经够了）。

**测试**：
- `np.float32(1.5)` → `'1.5'`（不是 `'np.float34(1.5)'` 之类的 repr 泄漏）；`np.float16`、`np.longdouble` 同样各一条；
- `np.float32('nan')` 与 `np.float64('inf')` 都**必须抛 `ValueError`**，且异常消息里含原值；
- 负对照：`float('nan')` 仍抛（既有行为不得回归）、`np.int64(3)` 仍返回 `3`、`None` 仍返回 `""`、`dict` 仍走 `allow_nan=False`；
- **一条端到端**：构造一个含 `np.float32` 值的记录，走完整 `write_csv` 落盘路径，断言 CSV 文本里**既不含 `np.float32(`、也不含 `nan`**（复审说 m2 的既有测试是这么做的，请沿用同一手法——只断言 `_cell` 的返回值抓不住「落盘时被别的路径绕过」）。

### 2.3 四条响亮失败守卫补自证测试（必修）

**现状**（复审取证，控制者已核实行号）：`fitness.py:606`、`:618` 两处 `ValueError` 与 `:805`、`:813` 两处 `RuntimeError` **零测试覆盖**。复审用合成输入证明它们**真会抛**（不是死代码），但没有任何测试钉住「在什么条件下抛、抛出的消息里有什么」。

**为什么必修**：本轮刚为 AST 守卫立了「守卫必须自带自证测试，否则『守卫存在』与『守卫有效』是两件没人分得清的事」的规矩，同一轮里 4 条新守卫却一条都没测——双重标准。更重要的是这 4 条守卫全是**「宁可炸也不静默产出错数据」**的设计：`:606`/`:618` 是可行池不足（Ruling 65/70 的核心，静默改标签会让 `trend_label` 这个真值说谎），`:805`/`:813` 是校正循环不收敛（静默放行会产出一个标签与数据不符的学生，而 `trend_label` 是 Task 8 的对账基准、Y4 的唯一输入）。**一条从不被测试触发的守卫，等价于一条没人知道还在不在的守卫。**

**要做**：为 4 条各写至少 1 条测试，用**合成输入**（手工构造的 `curr` / `bmi_delta` / `free` / 配额字典等，不要靠调 `SeedConfig` 去撞）直接打到抛出的那一行，断言：
- 抛的是**正确的异常类型**；
- **消息里含关键数字**——`:606`/`:618` 必须报出「需要数与实有数」（这是 Ruling 65 明写的要求，请核实消息真的有，没有就补上），`:805`/`:813` 必须报出学生标识与迭代轮数（便于定位是哪个学生、哪一类标签不收敛）。
- 其中「池不足」那两条，请**额外**构造一个能真实触发的 `SeedConfig`（例如把 `trend_mix` 里 `持续下滑` 的比例调到池装不下），断言 `build_dataset` 整体抛 `ValueError` 而不是静默少生成几个人——这条比合成输入更接近真实失效路径。

### 2.4 `_delta_target_windows:558` 的零宽窗口补注释（必修，只写注释，不改逻辑）

**现状**（复审取证）：`:558` 的 `magnitude = w_free * max(0.0, room - profile.jitter - CORRECTION_RESERVE) / 100.0` 里那个 `max(0.0, …)` 钳位，让 **133/489** 名「稳定」池学生以**零宽窗口 + 零校正预留**被放行。实测 `RuntimeError` 0 次，说明当前不咬人。

**为什么不改逻辑只补注释**：零宽窗口意味着 `Delta_target` 被强制成单点、零预留意味着一旦量化把它推出去就**没有校正空间**——这是一颗需要写明「为何可接受」的哑弹，而不是一颗可以假装不存在的哑弹。控制者已裁定**本轮不改行为**（改窗口公式会平移随机流、让全部 CSV 字节与已取证哈希作废，代价与收益不成比例；且「稳定」类的 `Delta_target` 名义区间本来就只有 `U(−2,+2)` 宽，被钳成单点损失很小）。

**要做**：在 `:558` 附近补一段注释，写清三件事：
1. `max(0.0, …)` 钳位会产生**零宽窗口**，实测 500 人配置下有 133/489 名「稳定」池学生落入；
2. 为什么可以接受：零宽 ⇒ `Delta_target` 取单点 ⇒ 该生的 `Delta` 完全由 BMI 贡献与落档量化决定，而「稳定」的判据是 `|Delta| < 5` 这个**开区间**，单点目标落在区间中央时量化噪声（最多 ±7.65 分）…… **⚠️ 这一条你自己算一遍再写**：如果算下来单点目标 + 零预留其实**不安全**（即量化可能把它推出 ±5），那就**不要写「可以接受」**，改为在注释里如实写明这是一个已知的未爆哑弹、并把它列进报告的关切交给控制者裁定。**不要为了让注释好看而写一个你自己都不信的论证。**
3. 与 `CORRECTION_RESERVE` 的关系：预留为 0 时校正循环的第一步就无空间，`:805`/`:813` 那两条 `RuntimeError` 是它唯一的兜底。

---

## 3. 明确不要做的事

- **不改任何生成逻辑**（趋势模型、抖动、表下溢出、编班、龄组、两趟拆分）。本轮 2.1–2.3 是守卫与测试，2.4 是注释。
- **不动复审明确延后的 3 条 Minor**：`_correction_move` 的 3 条 0 命中分支（不删）、m4 自证测试的分辨力（不收紧到 ±0.05）、以及上面 2.4 的窗口公式（不改）。
- 不动 `app/domain/indicators.py`（`ITEM_WEIGHTS` 已就位）。
- 不实现 Task 8 的 `classify_trend` / `national_total` / `derive`。
- 不做 `latent_mean` / `latent_sd` 的二分法调参（Task 9）。
- 不动 `write_csv` 的三文件契约、`make_batch_key`、日期零填充。不加 `students.csv`。
- 不放宽任何既有断言（等号改容差、全称改存在量词、`==` 改 `in` 都算放宽）。基线 **280 passed**，本轮结束时既有 280 条必须仍全绿且断言未改。
- 不做本简报未要求的重构、注释补全、类型标注。

---

## 4. 交付

1. 一个 commit，message 形如：
   `fix: AST 守卫补 numpy 全局随机源，_cell 补 np.floating，四条响亮失败守卫补自证测试`
2. 把本轮内容**追加**到 `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/task-6-report.md` **末尾**（新章节标题 `## Fix Round 3`）。该文件现 109955 字节，**只追加，不要重写**。报告须含：
   - 新旧测试数（**280** → 新值）与 `-W error` 结果、耗时；
   - 2.1 的**双向**取证：新增禁用写法逐条被抓的清单 + `app/seed/` 现有合法 `rng.*` 调用零违规的证明；
   - 2.2 的 CSV 文本级取证（落盘后 grep 不到 `np.float32(` 与 `nan`）；
   - 2.3 四条守卫各自的触发条件、异常类型、消息全文；
   - 2.4 你自己算的那笔账（单点目标 + 零预留在 ±5 开区间下到底安不安全），以及据此写下的注释原文；
   - **三个 CSV 的 SHA256 前 16 位是否仍为 `498AA3256678B01A` / `1234025C05843B27` / `835A98FCC0779B51`**。本轮不改生成逻辑，**哈希必须逐字不变**；若变了，说明你动到了不该动的东西，请在报告里第一行就说明并解释。取证一律走 `%TEMP%` 临时目录、两次独立进程、不碰 `pe.db`、不写 `backend/data/seed/`。
   - **关切章节**（照旧欢迎）；
   - **前向约束章节**（若无新增，写「无新增，沿用 fix round 2 的清单」）。
3. 报告写完后用 shell 复核文件确实变长（`(Get-Item <report>).Length`），末尾附 `git log --oneline -1` 与 `git status --short` 输出（后者应为空）。
4. 临时探针文件与临时 CSV 目录全部删除，并逐个 `Test-Path` 复核为 `False`。

## 5. 最终返回给我什么

一段简明总结：commit 哈希、测试数变化（280 → ?）、`-W error` 是否洁净、**三个 CSV 哈希是否逐字未变**、2.1 双向取证结果、2.2 的 CSV 文本级取证结果、2.3 四条守卫的异常类型与消息要点、2.4 你算出来的结论（安全 / 不安全）与据此写的注释、**你上报的每一条关切（原文摘要，不要精简掉）**、以及 `git status --short` 的输出。

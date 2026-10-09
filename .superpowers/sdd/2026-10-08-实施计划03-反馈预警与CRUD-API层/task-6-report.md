# Task 6 实现者报告 —— 预警规则：`alert_rules.yaml` + `app/domain/alerts.py` + `app/refdata_alerts.py`

> 分支 `feature/plan-03-feedback-alert-crud-api`；基线 commit `a8d61b4`（工作树干净）。
> 本 Task 三个 commit：`834fa34`（抽 `refdata_yaml.py`）→ `f08e9ce`（预警规则主体）→ **本次 commit**（变异取证 + 收尾；sha 见 `git log --oneline -1`）。
>
> **一句话结论**：**1026 passed**（956 → 1026，+70），`app/domain/` 覆盖率
> **1147 stmts / Miss 0 / 336 branch / BrPart 0 / 100%**，**5 条变异全部被边界测试抓住、
> 三重还原取证全部通过**，表数仍 **25**、扫描面 **51 → 52**、`models.__all__` 仍 **33**、
> openapi paths 仍 **56**、三个既有指纹**逐字不变**、`backend/pe.db` **仍不存在**。
> **顶回控制者 8 处**（含 1 处 Critical 级）、**没按派单做 7 处**、**待清扫 5 条**、**关切 6 条**。
> **fix round 0 轮**（主体 70 条测试一次跑绿）。

---

## §1 环境与基线复现

### 1.1 开工第一件事：import 冒烟（硬规矩 #73）

```
cd backend; python -c "import sqlalchemy, fastapi, uvicorn, httpx, pydantic, yaml; print(sqlalchemy.__version__, fastapi.__version__, yaml.__version__)"
-> 2.1.3 0.141.1 6.0.3
```

**没有撞上 `ImportError: DLL load failed`**（Smart App Control 没拦 `.pyd`），故按派单继续。
Python **3.11.1**、无 venv、`core.autocrlf` = **true**。

### 1.2 基线复现（开工时亲跑，与派单给的数逐个相符）

| 项 | 派单给的 | 实测 | 相符 |
|---|---|---|---|
| 分支 | `feature/plan-03-feedback-alert-crud-api` | 同 | ✅ |
| 基线 commit | `a8d61b4`，工作树干净 | 同（`git status --short` 空） | ✅ |
| `python -m pytest -q` | 956 passed | **956 passed, 1 warning in 152.10s** | ✅ |
| `--cov=app.domain --cov-branch` | 996 / 0 / 288 / 0 / 100% | 同（955 passed, 1 skipped） | ✅ |
| 表数 | 25 | **25** | ✅ |
| 扫描面 | 51（pipeline 8 + db 11 + domain 16 + api 16） | **51** | ✅ |
| `app/domain/` 的 `.py` | 16 | **16** | ✅ |
| openapi paths（端点） | 56 | **56**（operations 84） | ✅ |
| `backend/pe.db` | 不得存在 | **不存在** | ✅ |
| `backend/data/seed/` | 0 文件 | **存在、0 文件** | ✅ |
| 三个既有指纹 | `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` | **三个逐字不变** | ✅ |

⚠️ **端点的计数口径要写清**：`create_app()` 的 `app.routes` 里只有 **6** 项
（4 个 docs 路由 + 1 个 `_IncludedRouter` + 1 个 `/api/health`）——FastAPI 0.141.1 /
Starlette 1.7.0 把 `include_router` 折成了一个惰性的 `_IncludedRouter`，**逐条数
`app.routes` 会数出 1 个 `/api` 端点而不是 56 个**。本报告的「56」是
`len(app.openapi()["paths"])`（operations = 84），与 Task 5 报的那个数同口径。
探针在 `t6_probes/invariants.py`。

⚠️ **`_MODELS_PUBLIC_BASELINE` 与 `models.__all__` 是两个数**：`len(models.__all__)` 实测
**14**，而基线是 **33** 个 `(名字, 所有者模块)` 二元组（Ruling 97：Plan 02 的四个表类与
Plan 03 的七个表类**刻意都不在** `app.db.models` 的 `__all__` 里）。本 Task 一个表类都没加，
故两者都不动；守卫 `tests/db/test_models.py -k public_namespace` **2 passed**。

---

## §2 P6-A2 的抽取：`app/refdata_yaml.py`

### 2.1 6 个函数的签名（改名去掉前导下划线 + **多出一个 `doc_kind`**）

| 原（`refdata_prescription.py` 私有） | 新（`app/refdata_yaml.py` 公开） |
|---|---|
| `_line_index(text: str) -> dict[tuple, int]` | `line_index(text: str) -> dict[tuple, int]` |
| `_fail(path, lines, key_path, message) -> ValueError` | `fail(path, lines, key_path, message, *, doc_kind: str) -> ValueError` |
| `_exact_keys(path, lines, where, raw, required, label) -> None` | `exact_keys(path, lines, where, raw, required, label, *, doc_kind: str) -> None` |
| `_as_int(path, lines, where, raw, label) -> int` | `as_int(path, lines, where, raw, label, *, doc_kind: str) -> int` |
| `_as_float(path, lines, where, raw, label) -> float` | `as_float(path, lines, where, raw, label, *, doc_kind: str) -> float` |
| `_as_optional_text(path, lines, where, raw, label) -> str \| None` | `as_optional_text(path, lines, where, raw, label, *, doc_kind: str) -> str \| None` |

⚠️ **`doc_kind` 是计划没提、而不加就是错的一条**（顶回 #1，逐字取证见 §7.1）：
原 `_fail` 的末行是硬编码的 `return ValueError(f"处方模板 {path} {where}：{message}")`。
原样搬进共用模块的话，`alert_rules.yaml` 被改坏时会报
「**处方模板** …/data/alert_rules.yaml 第 3 行：…」——指着一份预警阈值文件说它是处方模板，
Review Focus 第 5 条要的「指出是哪个文件哪一行哪个键」当场变成假话。
它是**必填的 keyword-only 参数、没有缺省值**，于是「新加载器忘了传」是 `TypeError`（响亮）
而不是「静默用别人的措辞」。

`refdata_yaml.py` 写了 `__all__`（6 个名字），只 import `pathlib` 与 `yaml`、
**不 import `app` 里的任何东西**（它是叶子，否则 `refdata_yaml → refdata → domain` 这条边
会让共用助手不再是叶子）。

### 2.2 `refdata_prescription.py` 改了几处

**3 处**（diff **+49 / −126**；字节 66 752 → 64 157，行 1 229 → 1 152）：

1. **模块 docstring 加一段**：说明抽取、`doc_kind` 的由来、以及「报错文本逐字不变」。
2. **加一行 import**：`from app import refdata_yaml`。
3. **把 141 行的 6 个定义换成 49 行的适配器块**：`_DOC_KIND = "处方模板"`、
   `_line_index = refdata_yaml.line_index`（别名，**同一个函数对象**）、
   5 个「一句转发 + 绑 `doc_kind`」的薄适配器。

⚠️ **57 处调用点一个字都没动。** AST 实测（`ast.Call` 计数，探针见 §2.3）：
`_fail` **44** + `_exact_keys` **6** + `_as_int` **3** + `_as_float` **2** +
`_as_optional_text` **1** + `_line_index` **1** = **57**。逐点加一个关键字参数就是
**57 次「有机会改坏一条被测试逐字钉住的报错文本」的机会**——
`tests/domain/test_prescription_templates.py:1246` 与 `:1250` 各有一条
`pytest.raises(..., match="处方模板")`。

### 2.3 `_PRESCRIPTION_PUBLIC_BASELINE` 是否仍 24？——**它不是 24，实测是 51**（顶回 #2）

**结论「不动」成立，但派单给的理由与数都是错的**：

* `tests/test_refdata_prescription.py:1124` 逐字是
  `assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 51, "基线是 51 个名字，抄漏了就当场红"`
  （下一行 `assert len(set(names)) == 51`）。**不是 24。**
* 它的主语**不是** `refdata_prescription.py` 的公开面，而是
  **`app.domain.prescription` 这个包的 `__all__`**：51 个二元组的所有者是
  `_OWNED_MODULES`（`:1011`）里那 **9** 个 `app.domain.prescription.*` 模块
  （+ 一个 `app.domain.stratify` 的 `Layer`）。支 2 断言的是
  `list(prescription_pkg.__all__) == names`。
* `refdata_prescription.py` 自己的公开面（AST 实测 **8** 个公有函数：
  `load_exercises` / `exercises` / `load_equivalence` / `equivalence` / `sync_exercises` /
  `load_templates` / `templates` / `sync_templates`，外加 3 个文件名/目录名常量）
  **今天没有任何基线钉它**。
* 故「搬私有助手不动那份基线」这件事成立，而理由不是「搬的是私有函数」，
  而是**那份基线根本不覆盖这个模块**。本 Task 落地后它仍是 **51**（`pytest
  tests/test_refdata_prescription.py -q` 全绿）。

⚠️ **顺带发现的一条过期散文**（记进 §7.3 待清扫）：`refdata_prescription.py` 的
`equivalence()` docstring 写「本模块公有函数是 **5** 个，第 5 个是 `sync_exercises`」，
AST 实测是 **8** 个——那是 Plan 02 Task 3 自己在同一次里加了
`load_templates` / `templates` / `sync_templates` 之后没跟着改的。

### 2.4 单一所有者的机器守卫（`tests/test_refdata_alerts.py` 闸 A，6 条）

| 支 | 测试名 | 守什么 |
|---|---|---|
| A1 | `test_the_six_shared_yaml_helpers_have_exactly_one_definition_site` | AST 扫 `backend/app/` 全部 `.py`，6 个名字**各只有一处顶层 `def`**、且在 `app/refdata_yaml.py`（硬规矩 #89 的再扩写：数「一个名字有几份定义」用 AST） |
| A2 | `test_every_consumer_binds_doc_kind_through_a_one_statement_adapter` | 两个消费者的 5 个适配器：函数体**恰好一句**（除去 docstring）+ 那一句在调 `refdata_yaml.<同名>` + 带了 `doc_kind=` |
| A3 | `test_line_index_is_the_same_object_in_every_consumer` | `module._line_index is refdata_yaml.line_index`（**身份**比对，副本骗得过 A1 与闸 B） |
| A4 | `test_doc_kind_is_bound_per_consumer_and_has_no_default` | `doc_kind` 是 `KEYWORD_ONLY` 且 `default is Parameter.empty`；两个消费者各自的 `_fail` 现拼出的消息以 `"处方模板 "` / `"预警规则 "` 开头 |
| A5 | `test_refdata_yaml_does_not_import_anything_from_app` | `sorted(imported) == ["pathlib", "yaml"]` |
| A6 | `test_fail_names_the_enclosing_block_when_a_key_has_no_position_of_its_own` | `fail` 的**三档措辞**（键在索引里 / 不在 / 索引建不出来）各钉一条 + 两档反面对照 |

⚠️ **A1 与 A2 各守一个方向**（硬规矩 #51）：A1 抓「在别处再定义一个同名的 `fail`」，
A2 抓「把 30 行逻辑复制回加载器、名字带下划线」——后者 A1 数不到、行为又完全正确，
只有「函数体长度 + 它在调谁」这个**结构**会露馅。

⚠️ **A2 的红是亲眼看过的**（TDD 先红后绿）：在改 `refdata_prescription.py` **之前**跑，
`2 failed, 3 passed`——A2 报 `_fail` 的函数体有 **5** 句、`_exact_keys` **5** 句、
`_as_int` **2** 句、`_as_float` **2** 句、`_as_optional_text` **3** 句；A3 报
`<function _line_index at 0x…> is <function line_index at 0x…>` 为假。
两条红的原因都是「逻辑还在加载器里」，正是它们该红的原因。

---

## §3 `app/domain/alerts.py` 的公开面与全部值类型（运行时口径）

`__all__` **16** 个名字（声明序，`tests/test_refdata_alerts.py` 的
`_ALERTS_PUBLIC_BASELINE` 逐字抄了这 16 个 + `refdata_alerts` 的 3 个 = **19**）：

```
AlertLevel, RuleId, AlertScope,
SUBJECT_PREFIX_STUDENT, SUBJECT_PREFIX_SECTION,
AlertRule, AlertRules,
StudentSignals, ClassSignals, StudentHit, ClassHit,
evaluate_student, evaluate_class, student_skip_traces, class_skip_traces,
declared_scope
```

`_public_top_level_definitions(app.domain.alerts)` 实测 **16**，与 `__all__` 互为充要
（AST 口径，不与 `dir()` 同源）。文件 **39 831 B / 721 行**。

### 3.1 三个枚举（运行时口径：`len(list(Enum))`）

| 枚举 | 成员数 | `(name, value)` 逐字 |
|---|---|---|
| `AlertLevel` | **3** | `(RED, red) (YELLOW, yellow) (GREEN, green)` |
| `RuleId` | **5** | `(RED_MINITEST_DROP, RED_MINITEST_DROP) (RED_RPE_SUSTAINED, RED_RPE_SUSTAINED) (YELLOW_CHECKIN_GAP, YELLOW_CHECKIN_GAP) (YELLOW_CLASS_RPE_HIGH, YELLOW_CLASS_RPE_HIGH) (GREEN_MASTERY, GREEN_MASTERY)` |
| `AlertScope` | **2** | `(STUDENT, student) (CLASS, class)` |

三个都继承 `str`（`alert.level` / `rule_id` 是普通字符串列、`trigger_snapshot` 是
`JsonText` 列，继承 `str` 之后 `json.dumps` 直接接受）。`RuleId` 的成员名与 `.value`
**逐字相同**，声明序 == spec §8.2 表格行序，且它是承重的（返回 tuple 的序）。

### 3.2 六个值类型的字段（`dataclasses.fields(...)`，硬规矩 #89）

| 类型 | 字段数 | 字段名（声明序） |
|---|---|---|
| `AlertRule` | **4** | `rule_id, level, scope, params` |
| `AlertRules` | **2** | `version, rules`（+ 方法 `params_of`） |
| `StudentSignals` | **11** | `student_id, semester_id, week, rpe_streak, rpe_session_ids, mini_test_scores, mini_test_ids, checkin_gap_days, checkin_gap_end, completion_rate, mini_test_improved` |
| `ClassSignals` | **5** | `course_section_id, semester_id, week, mean_rpe, student_count` |
| `StudentHit` | **5** | `rule_id, level, subject_key, window_key, snapshot` |
| `ClassHit` | **5** | `rule_id, level, subject_key, window_key, snapshot` |

⚠️ **P6-A1 要求的 4 个字段都在**（`rpe_session_ids` / `mini_test_ids` / `semester_id` /
`week`），**另有 4 个是实现者顶回后补的**（`student_id` / `checkin_gap_end` /
`ClassSignals.course_section_id`，以及 `StudentSignals` 上那份 `semester_id` / `week`）
——逐条取证见 §7.1 的顶回 #3/#4/#5。

**每个字段都有消费者**（硬规矩 #110 的反向；表逐字写在 `StudentSignals` 与
`ClassSignals` 的 docstring 里，并由
`test_the_signal_dataclasses_have_exactly_the_fields_the_rules_need` 钉住字段清单）：
唯一的例外是 `ClassSignals.student_count`，它**不是判据**、只进 snapshot 与留痕
（spec §8.2 没有「班上人数太少就不报」这一条，编一个下限就是编一条没人评审过的规则）。

### 3.3 两个前缀常量与 `declared_scope`

* `SUBJECT_PREFIX_STUDENT == "student"`、`SUBJECT_PREFIX_SECTION == "section"`。
  ⚠️ **是 `section` 而不是 `course_section`**：`alert.subject_key` 是 `String(24)`，
  `course_section:2147483647` 是 **27** 字符、**超宽 3**；`section:2147483647` 是 **18**
  字符、余量 6（`tests/db/test_models.py:2236-2239` 钉的正是这一个数）。
* `declared_scope(rule_id)` 是**代码侧**的作用域声明（哪一套求值器处理它），
  加载器拿它与 YAML 的 `scope` 对账（见 §4.3）。

### 3.4 `snapshot` 的口径

**「本规则读到的每一个信号值 + 它比过的每一个 YAML 阈值」**，实现上就是
`{"<字段名>": <值>, …, **rule.params}`。理由：snapshot 落进 `alert.trigger_snapshot`，
它要能让人**几年后离线**回答「这条预警为什么触发」——只存观测值的话，还得回去查当时
那一版 YAML（而它可能已经改过）。键名分别取 `StudentSignals`/`ClassSignals` 的字段名
与 YAML 的参数名，于是每个键都能对回到一个住址。

⚠️ `snapshot` 是**普通 `dict`**、不是只读视图：`types` 不在 domain 的 allow-list 里，
故 domain 侧做不出 `MappingProxyType`（加载器那一侧对 `AlertRules.rules` 与每条
`params` 都做了）。它每次求值**新建一个**，故两条命中不共享同一个 dict——
`test_evaluate_is_deterministic_and_does_not_mutate_its_input` 钉的就是这件事
（`first[0].snapshot == second[0].snapshot` 且 `is not`）。

---

## §4 `backend/data/alert_rules.yaml`

### 4.1 字节取证（`read_bytes()` 口径，硬规矩 #89 的扩写；脚本 `t6_probes/yaml_stats.py`）

| 项 | 值 |
|---|---|
| 字节数 | **6 037 B** |
| 行数（LF 计数） | **85** |
| **CRLF 计数** | **0** |
| BOM | **无** |
| **sha256[:16]** | **`E48E3AC82BB45BB7`** |
| 首行 | `# 预警阈值 —— spec §8.2 的 5 条规则 + spec §4.4 的「静态 YAML + 版本号」。` |
| 末行（非空） | `    params: {completion_rate_min: 1.0, improve_pct: 0.03}` |
| `version` 那一行（原始文本） | `version: "1.0"`（**带引号**，恰好 1 行以 `version:` 开头） |
| 5 个规则 ID 在 2 空格缩进处各出现 | **各 1 次**（重复键会让 PyYAML 静默覆盖，故用原始文本对账） |

`.gitattributes` 的 `backend/data/*.yaml text eol=lf` 已覆盖它（它直接在 `backend/data/`
下、不在子目录），故这个指纹与 `core.autocrlf` 无关。指纹常量写在
`tests/test_refdata_alerts.py::ALERT_RULES_FINGERPRINT`，算法逐字同
`EXERCISES_FINGERPRINT`（`hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16].upper()`）。

### 4.2 数据部分逐字照计划

`version: "1.0"` + 5 条规则的 `level` / `scope` / `params`，**9 个阈值逐字照计划给的那份**
（`drop_pct: 0.05` / `consecutive: 2` / `points_needed: 3` / `rpe_min: 9` / `streak: 3` /
`gap_days: 2` / `mean_rpe_max: 7.0` / `completion_rate_min: 1.0` / `improve_pct: 0.03`）。
⚠️ **派单与计划都说「8 个阈值」，运行时口径数出来是 9 个**（`sum(len(r.params) for r in
load_alert_rules().rules.values())` → `9`；逐条 `3 / 2 / 1 / 1 / 2`），见 §7.3 待清扫 #5。
**计划给的那份之外只加了注释**（阈值出处、`>=` 与 `>` 的区别、类型口径、「加一条新规则要
改两处」、四项均待确认的状态），见 §7.2 的「没按派单做 #2」。

### 4.3 加载器 `app/refdata_alerts.py`（**427 行 / 25 644 B**）拦的坏形状

Review Focus 第 5 条：**一律点名文件 + 行号 + 键路径**（走 §2 那套共用助手）。

| # | 坏形状 | 测试 |
|---|---|---|
| 1 | 文件不存在 | `test_loader_rejects_an_empty_file_and_a_missing_file`（`FileNotFoundError`，消息含「预警规则」） |
| 2 | 文件为空（`raw is None`） | 同上（消息含「为空」+「500 人一个预警都不触发、而管道全绿」） |
| 3 | YAML 语法错 | `test_loader_rejects_a_file_that_is_not_valid_yaml`（包成 `ValueError`、带文件名，**不是** `yaml.YAMLError`） |
| 4 | 顶层不是映射 | `test_loader_rejects_a_top_level_that_is_not_a_mapping` |
| 5 | 顶层键不是恰好 `version` / `rules` | `test_loader_rejects_a_missing_version` |
| 6 | **`version` 不是 `str`**（不加引号的 `1.0` → float） | `test_loader_rejects_a_version_that_is_not_a_string`（消息含「引号」）；文件侧另由 `test_version_is_quoted_in_the_raw_text_so_pyyaml_keeps_it_a_string` 用**原始文本**钉 |
| 7 | `rules` 不是映射 | `test_loader_rejects_rules_that_are_not_a_mapping` |
| 8 | **多出一个没人认识的规则 ID** | `test_loader_rejects_a_rule_id_the_code_does_not_know`（`RED_SLEEP_DEBT`） |
| 9 | 少一条规则 | `test_loader_rejects_a_missing_rule_id` |
| 10 | 某条规则不是映射 / 键不是恰好 `level`/`scope`/`params` | `test_loader_rejects_a_rule_block_that_is_not_a_mapping`、`test_loader_rejects_a_rule_with_a_missing_or_extra_key` |
| 11 | `level` / `scope` 值非法 | `test_loader_rejects_an_illegal_level_or_scope`（消息列出合法值） |
| 12 | **YAML 的 `scope` 与 `declared_scope()` 矛盾** | `test_loader_rejects_a_rule_whose_yaml_scope_disagrees_with_the_code` |
| 13 | `params` 缺键 / 多键 | `test_loader_rejects_params_with_a_missing_key`、`test_loader_rejects_params_with_an_extra_key` |
| 14 | 阈值不是数（含 `bool`） | `test_loader_rejects_a_threshold_that_is_not_a_number` |
| 15 | **计数写成小数**（`streak: 3.0`） | `test_loader_rejects_a_count_written_as_a_float` |
| 16 | 比率不在 `(0,1)` / `completion_rate_min` 不在 `(0,1]` / 计数 `< 1` | `test_loader_rejects_a_ratio_or_count_out_of_range`（4 档） |
| 17 | **`points_needed != consecutive + 1`** | `test_loader_rejects_points_needed_that_is_not_consecutive_plus_one` |
| 18 | 规则块缺键时点名是哪条规则 | `test_loader_names_the_rule_when_one_of_its_keys_is_missing` |

第 12 / 15 / 16 / 17 四项是**计划没要求**的加固，逐条理由见 §7.2 的「没按派单做 #4」。

⚠️ **它守不住什么**（硬规矩 #39，逐字写在 `refdata_alerts.py` 的模块 docstring 里）：
① 不校验阈值「对不对」，只校验「可不可能」（`mean_rpe_max: 3.0` 会被照收，而它会让
每个班每周都吃一张黄牌——「这个数合不合理」是专家的评审职责，spec §4.4 那句
「走版本控制与评审」说的就是这件事）；② **不校验 RPE 的值域 0–10**，因为
Global Constraints 逐字写「RPE 的值域 0–10 的唯一所有者是 spec §8.2……**不要在本计划里
写第三份**」；③ 不校验 `version` 与规则集的关系（加了第 6 条规则而 `version` 仍是
`"1.0"` 会被照收——自动升号会让「改阈值要评审」看起来像一次自动手续）。

### 4.4 公开面基线 `_ALERTS_PUBLIC_BASELINE`（P6-A5）

**长度 19**（`app.domain.alerts` **16** + `app.refdata_alerts` **3**），
`assert len(...) == 19` + `assert len(set(names)) == 19` + 所有者恰好 **2** 个模块。
六支同构于 `test_prescription_public_namespace_is_pinned_verbatim`：
支 1 基线自校 / 支 2 `list(alerts.__all__) == ` 那 16 个（**含声明序**）/
支 3 不是字母序 / 支 4 逐名字到所有者上取同一性（先断言不是 `None`，否则退化成
`None is None` 的假绿）/ 支 5 AST 穷尽（`refdata_alerts` 那 3 个 + `alerts` 的
`__all__` 与 AST 互为充要）/ 支 6 两档合成的失同步态。

`app.refdata_alerts` **不写 `__all__`**（照 `refdata_prescription.py` 的形状办，
`test_refdata_alerts_does_not_write_an_all_and_does_not_import_the_db` 钉住），
它的 3 个公开名是 `ALERT_RULES_FILENAME` / `load_alert_rules` / `alert_rules`。
`app.domain.alerts` **写 `__all__`**（P6-A5 要求，与 `app/domain/prescription/*.py` 同档）。
⚠️ `app.domain.alerts` **刻意不进** `test_refdata_prescription.py` 的 `_OWNED_MODULES`
（那个清单的主语是「**处方包**拥有的模块」，本模块与 `prescription/` 无隶属关系）。

---

## §5 五条规则的判据逐条落地位置与边界测试名

行号是 `backend/app/domain/alerts.py` 的**当前工作树**行号（`grep -n` 口径）。

| # | 规则 | 判据（源码逐字） | 落地位置 | **边界测试（变异靶）** |
|---|---|---|---|---|
| 1 | `RED_MINITEST_DROP` | `if newer >= older * factor:` → `return None, None`（`factor = 1.0 - drop_pct`，即 spec 口径表 #2 的 `score(t) < score(t-1) × 0.95` 的**否定式**） | `_minitest_drop` 起于 **:431**，判据在 **:459**，`window_key=f"mt{sig.mini_test_ids[-1]}"` 在 **:465** | `tests/domain/test_alerts.py::test_minitest_drop_is_strict_at_exactly_five_percent` |
| 2 | `RED_RPE_SUSTAINED` | `if sig.rpe_streak >= needed:` | `_rpe_sustained` 起于 **:470**，判据在 **:484**，`window_key=f"rpe{sig.rpe_session_ids[needed - 1]}"` 在 **:489** | `::test_rpe_sustained_fires_at_exactly_the_streak_threshold` |
| 3 | `YELLOW_CHECKIN_GAP` | `if sig.checkin_gap_days >= int(rule.params["gap_days"]):` | `_checkin_gap` 起于 **:495**，判据在 **:505**，`window_key=f"gap{sig.checkin_gap_end}"` 在 **:510** | `::test_checkin_gap_fires_at_exactly_the_gap_threshold` |
| 4 | `YELLOW_CLASS_RPE_HIGH` | `if sig.mean_rpe > float(rule.params["mean_rpe_max"]):` | `_class_rpe_high` 起于 **:562**，判据在 **:582**，`window_key=f"{sig.semester_id}:{sig.week}"` 在 **:587** | `::test_class_rpe_high_is_strict_at_exactly_seven` |
| 5 | `GREEN_MASTERY` | `sig.completion_rate >= float(rule.params["completion_rate_min"]) and sig.mini_test_improved` | `_mastery` 起于 **:516**，判据在 **:545**，`window_key=f"{sig.semester_id}:{sig.week}"` 在 **:552** | `::test_mastery_fires_at_exactly_full_completion` |

两个 dispatch 表：`_STUDENT_EVALUATORS` **:602**（4 条）、`_CLASS_EVALUATORS` **:610**（1 条）。
契约校验 `_require_parallel` **:402**。

### 5.1 每条规则的边界测试**各钉两侧**（硬规矩 #50）

* **#1**：`(88.0, 80.0, 76.0)` 恰好 5.00% → **不**触发；`(88.0, 80.0, 75.9)` → 触发。
  另有 `test_minitest_drop_only_reads_the_last_consecutive_plus_one_scores` 钉
  「只看最后 `consecutive + 1` 个点」（`(88,80,70,69)` 不触发、`(60,88,80,70)` 触发）。
* **#2**：`rpe_streak == 3` → 触发；`== 2` → 不触发（`test_rpe_sustained_does_not_fire_below_the_streak_threshold`）。
* **#3**：`== 2` → 触发；`== 1` → 不触发（`test_checkin_gap_does_not_fire_after_a_single_missed_training_day`）。
* **#4**：`mean_rpe == 7.0` → **不**触发；`7.1` → 触发（同一条测试里两半都断言）。
* **#5**：`completion_rate == 1.0` + improved → 触发；`0.99` → 不触发；
  `1.0` + `improved=False` → 不触发（`test_mastery_needs_both_halves_of_the_conjunction`）。

### 5.2 `window_key` 的去重语义（Review Focus 第 3 条）

`test_a_longer_rpe_streak_reuses_the_same_window_key_so_the_dedup_key_holds` 是**正面复现**：
`streak` 3 → 4 → 5 三次求值给出 `["rpe103", "rpe103", "rpe103"]`，
`len(set(keys)) == 1`。⚠️ 若算式取 `rpe_session_ids[-1]`，三次会得到
`rpe103` / `rpe104` / `rpe105` → 三行 `alert` → 三次「减量 20%」→ `0.8³ = 0.512`，
而全链路没有一处报错。
`test_rpe_window_key_is_anchored_at_the_session_that_completed_the_streak` 钉另一半
（`streak=3` 与 `streak=5` 都得 `"rpe103"`）。

⚠️ **`RED_MINITEST_DROP` 刻意用另一套口径**（`mini_test_ids[-1]`，随最后一次小测前进）：
小测不是每堂课都有的，一次新小测是一次**新的观测窗口**；而快评每堂课都有，
锚在最后一次会让键天天变。

### 5.3 「判不了 ≠ 没问题」的留痕

| 规则 | 判不了的那一档 | 留痕 | 测试 |
|---|---|---|---|
| `RED_MINITEST_DROP` | `len(mini_test_scores) < points_needed` | `{"insufficient_points": n, "points_needed": 3}` | `test_minitest_drop_leaves_a_trace_instead_of_firing_when_points_are_short` |
| `YELLOW_CLASS_RPE_HIGH` | `mean_rpe is None` | `{"insufficient_points": 0, "student_count": n, "mean_rpe_max": 7.0}` | `test_class_rpe_high_leaves_a_trace_when_no_one_submitted_rpe_this_week` |
| `GREEN_MASTERY` | `completion_rate is None` | `{"missing": "completion_rate", "completion_rate_min": 1.0}` | `test_mastery_leaves_a_trace_when_the_completion_rate_is_missing` |

⚠️ **实现方式**（顶回 #7）：每个求值器返回 `(命中, 留痕)` **一对**，
`evaluate_student` / `evaluate_class` 取前半、`student_skip_traces` / `class_skip_traces`
取后半，于是「什么时候判不了」在代码里**只有一处**（`_Evaluator` 的注释写着理由：
拆成两套函数各判一次的话，`points_needed` 会被读两遍，而两份判断迟早不一致）。

---

## §6 变异取证的完整表（脚本 `t6_probes/mutate.py`，5 条全跑）

**基线**：`app/domain/alerts.py` = **39 110 B**、sha256 = **`BF36B469F0FC19C9`**
（⚠️ 这是变异当时的 LF 工作树字节；收尾时按 §7.2 的「没按派单做 #6」归一成 CRLF，
**blob 逐字不变**，故 sha256 变成 `6E6AAC8A55427415` 而 `git hash-object` 仍是
`fcd7a0d9ad76`）。未变异时跑两个测试文件：`exit=0 FAILED=0 | 70 passed in 1.24s`。

**每次变异的流程**：备份原字节到 TEMP → 断言待改那一段**恰好命中 1 次**（不对就停手、
不写盘）→ 写变异字节 → **删 `backend/app` 与 `backend/tests` 下全部 `__pycache__`**
（硬规矩 #83；不删的话 CPython 可能按 mtime+size 判定缓存有效、跑的是旧字节，
于是变异看起来「没让任何测试红」——那是一次假绿，而且是最坏的一种）→ 跑测试收 FAILED
名单 → **用 python 从 TEMP 备份 `write_bytes` 写回**（⚠️ 不用 `git checkout`：
`core.autocrlf=true` 会按 `.gitattributes` 重写工作树，硬规矩 #46/#70）→ 再删一次
`__pycache__` → 三重还原取证。

| # | 规则 | 变异（源码逐字） | 结构可达性（硬规矩 #92：坐在边界上的那个输入） | 红了几条 | **边界靶命中** | 三重还原取证 |
|---|---|---|---|---|---|---|
| **M1** | `RED_MINITEST_DROP` | `if newer >= older * factor:` → `if newer > older * factor:`（= 把 spec 口径表 #2 的 `<` 改成 `<=`） | `(88.0, 80.0, 76.0)`：`80.0 × 0.95 == 76.0`，恰好坐在边界上；`>=` 判「没下降」（不触发）、`>` 判「下降了」（触发） | **3** | ✅ `test_minitest_drop_is_strict_at_exactly_five_percent` | ① sha256 `BF36B469F0FC19C9` == 原字节 ② `git diff` 该文件输出长度 **0** ③ 复跑 `exit=0 FAILED=0 \| 70 passed in 1.56s` |
| **M2** | `RED_RPE_SUSTAINED` | `if sig.rpe_streak >= needed:` → `>` | `rpe_streak == 3`、`streak == 3`；`>=` 触发、`>` 不触发 | **9** | ✅ `test_rpe_sustained_fires_at_exactly_the_streak_threshold` | ① 同 ② **0** ③ `70 passed in 1.34s` |
| **M3** | `YELLOW_CHECKIN_GAP` | `if sig.checkin_gap_days >= int(rule.params["gap_days"]):` → `>` | `checkin_gap_days == 2`、`gap_days == 2`；`>=` 触发、`>` 不触发 | **6** | ✅ `test_checkin_gap_fires_at_exactly_the_gap_threshold` | ① 同 ② **0** ③ `70 passed in 1.30s` |
| **M4** | `YELLOW_CLASS_RPE_HIGH` | `if sig.mean_rpe > float(rule.params["mean_rpe_max"]):` → `>=` | `mean_rpe == 7.0`、`mean_rpe_max == 7.0`；`>` 不触发、`>=` 触发 | **2** | ✅ `test_class_rpe_high_is_strict_at_exactly_seven` | ① 同 ② **0** ③ `70 passed in 1.32s` |
| **M5** | `GREEN_MASTERY` | `sig.completion_rate >= float(rule.params["completion_rate_min"])` → `>` | `completion_rate == 1.0`、`completion_rate_min == 1.0`；`>=` 触发、`>` 不触发 | **5** | ✅ `test_mastery_fires_at_exactly_full_completion` | ① 同 ② **0** ③ `70 passed in 1.38s` |

**收尾**：`alerts.py` = 39 110 B、sha256 `BF36B469F0FC19C9` == 原字节、
`final_bytes == original` → **True**。

### 6.1 逐条的 FAILED 名单（5 行摘要的展开）

* **M1（红 3）**：`test_minitest_drop_is_strict_at_exactly_five_percent` **（边界靶）**、
  `test_the_thresholds_come_from_the_rules_not_from_literals_in_this_module`、
  `tests/test_refdata_alerts.py::test_the_real_yaml_drives_the_spec_boundaries_end_to_end`。
  ⚠️ 后两条红的原因与边界靶**同一个**：它们各自也坐在那条边界上
  （前者用 `(100.0, 95.0, 90.25)`，`95.0 == 100.0 × 0.95`；后者用真 YAML + `(88.0, 80.0, 76.0)`）。
  **变异只让「坐在恰好 5% 上」的断言红**，`test_minitest_drop_fires_on_two_consecutive_five_percent_drops`
  与 `test_minitest_drop_only_reads_the_last_consecutive_plus_one_scores` 两条**保持绿**
  ——这就是「尺子真的在量那个闭区间端点、而不是在量『有没有下降』」的自证
  （Task 5 的 M1 用的是同一种论证形状）。
* **M2（红 9）**：`test_student_hits_carry_a_student_subject_key_and_class_hits_a_section_one`、
  `test_rpe_window_key_is_anchored_at_the_session_that_completed_the_streak`、
  `test_a_longer_rpe_streak_reuses_the_same_window_key_so_the_dedup_key_holds`、
  `test_both_dedup_keys_fit_their_db_columns`、
  `test_rpe_sustained_fires_at_exactly_the_streak_threshold` **（边界靶）**、
  `test_the_thresholds_come_from_the_rules_not_from_literals_in_this_module`、
  `test_a_student_can_hit_several_rules_at_once_in_declaration_order`、
  `test_evaluate_is_deterministic_and_does_not_mutate_its_input`、
  `test_the_real_yaml_drives_the_spec_boundaries_end_to_end`。
  ⚠️ **红 9 条不是尺子松，而是 `rpe_streak=3` 是本文件里最常用的那一档输入**
  （`window_key` 的 4 条、纯函数性质的 1 条都用它）；
  `test_rpe_sustained_does_not_fire_below_the_streak_threshold`（`streak=2`）
  与 `test_the_two_evaluators_never_mix_scopes`（`streak=9`）**保持绿**，
  故红的确实只是「恰好 3」那一档。
* **M3（红 6）**：`test_checkin_gap_window_key_uses_the_iso_date_injected_by_the_caller`、
  `test_both_dedup_keys_fit_their_db_columns`、
  `test_checkin_gap_fires_at_exactly_the_gap_threshold` **（边界靶）**、
  `test_the_thresholds_come_from_the_rules_not_from_literals_in_this_module`、
  `test_a_student_can_hit_several_rules_at_once_in_declaration_order`、
  `test_the_real_yaml_drives_the_spec_boundaries_end_to_end`。
  `test_checkin_gap_does_not_fire_after_a_single_missed_training_day`（`gap=1`）**保持绿**。
* **M4（红 2）**：`test_class_rpe_high_is_strict_at_exactly_seven` **（边界靶）**、
  `test_the_real_yaml_drives_the_spec_boundaries_end_to_end`。
  ⚠️ **这是 5 条里最干净的一条**：只让「坐在恰好 7.0 上」的断言红，
  `test_class_rpe_high_leaves_a_trace_when_no_one_submitted_rpe_this_week`（`mean_rpe=None`）
  与 `test_the_two_evaluators_never_mix_scopes`（`mean_rpe=10.0`）都**保持绿**。
* **M5（红 5）**：`test_class_and_mastery_window_keys_are_semester_colon_week`、
  `test_mastery_fires_at_exactly_full_completion` **（边界靶）**、
  `test_a_student_can_hit_several_rules_at_once_in_declaration_order`、
  `test_the_two_evaluators_never_mix_scopes`、
  `test_the_real_yaml_drives_the_spec_boundaries_end_to_end`。
  `test_mastery_needs_both_halves_of_the_conjunction`（`0.99`）**保持绿**；
  ⚠️ `test_the_thresholds_come_from_the_rules_not_from_literals_in_this_module` 这条
  **保持绿**是**对的**：它用 `completion_rate=0.95` 配 `completion_rate_min=0.9`，
  `0.95 > 0.9` 与 `0.95 >= 0.9` 同真，故它本来就坐不到那个边界上。

⚠️ **M5 的存在本身就是顶回 #6 的证据**：若照计划正文写成 `completion_rate == 1.0`，
则「`==` → `>=`」在值域 `[0, 1]` 上**不可分辨**，本 Task 唯一要求的变异测试对第 5 条规则
**没有靶子**（任何测试都不会红）。写成 `>=` 之后 `>=` → `>` 让 5 条红、边界靶命中。

---

## §7 顶回 / 没按派单做 / 待清扫 / 关切

### 7.1 顶回控制者的地方 —— **8 处**（Plan 02 25/25、Plan 03 25/25，本次 8 处）

| # | 级别 | 派单/计划说的 | 代码现场的实测 | 处置 |
|---|---|---|---|---|
| **1** | **Important** | P6-A2：「把那 6 个搬进 `app/refdata_yaml.py`（改名去掉前导下划线），两处都从它 import」 | 原 `_fail` 的末行是**硬编码前缀** `return ValueError(f"处方模板 {path} {where}：{message}")`。原样共用的话 `alert_rules.yaml` 的报错会说「处方模板 …/alert_rules.yaml 第 3 行」——Review Focus 第 5 条要的「指出是哪个文件」当场变假话。而 `tests/domain/test_prescription_templates.py:1246`/`:1250` 有两条 `match="处方模板"`，故前缀**不能改** | 6 个函数各多一个 **`doc_kind` 必填 keyword-only 参数、无缺省值**；两个消费者各绑自己的措辞（`"处方模板"` / `"预警规则"`）。**报错文本逐字不变**，那两条 `match=` 仍绿。守卫 = 闸 A4 |
| **2** | **Important** | P6-A2 与 P6-A5 各说一次「`_PRESCRIPTION_PUBLIC_BASELINE`（**24 个二元组**）不动」 | 实测 **51**（`:1124` 逐字 `== 51`），且它钉的是 **`app.domain.prescription.__all__`**（`_OWNED_MODULES` 九个模块 + `Layer`），**与 `refdata_prescription.py` 的公开面无关**——后者 8 个公有函数，今天**没有任何基线钉它** | 结论「不动」采纳（落地后仍 **51**、`tests/test_refdata_prescription.py` 全绿），但**理由换掉**：不是「搬的是私有函数」，而是「那份基线根本不覆盖这个模块」。`_ALERTS_PUBLIC_BASELINE` 因此按**自己**的口径建（19），不去对齐那个 24 |
| **3** | **Critical** | Interfaces 里 `StudentHit` / `ClassHit` 只有 `rule_id` / `level` / `window_key` / `snapshot`；P6-A1 也只补了两个 id 元组 | **`subject_key` 无处可算**，而它是 `UniqueConstraint("rule_id", "subject_key", "semester_id", "window_key")` 的一列，且**三处已落地的代码逐字把它的算式钉给本模块**：`app/db/models/feedback.py:588-590`（「算式的唯一所有者是 Task 6 的 `app.domain.alerts`，本模块**不声明**前缀常量」）、`app/api/schemas/alerts.py:55`（「那个前缀算式的唯一所有者是 Task 6 的 `app.domain.alerts`，**前端不要自己拼它**」）、`tests/db/test_models.py:1416-1417` 与 `:1830`（「`subject_key` 的算式只有 `app.domain.alerts` 一个所有者」）。不做的话 Task 7 只能在 `alert_stage` 里自己拼前缀——正是三处 docstring 点名不许的第二个所有者 | `StudentSignals` 加 **`student_id`**、`ClassSignals` 加 **`course_section_id`**，两个 Hit 各加 **`subject_key`**，两个前缀常量 **`SUBJECT_PREFIX_STUDENT` / `SUBJECT_PREFIX_SECTION`** 住 `alerts.py`。⚠️ 附带发现：`subject_key` 是 `String(24)`，而 `course_section:2147483647` 是 **27** 字符、**超宽 3**，故前缀必须是 `section`（`tests/db/test_models.py:2236-2239` 钉的就是 `section:2147483647` = 18 字符） |
| **4** | **Critical** | `StudentSignals` 字段清单里**一个日期字段都没有**；P6-A4 只说了处置倾向（「把日期字段换成调用方已算好的 `str`」）却没把它加进清单 | `YELLOW_CHECKIN_GAP` 的 `window_key` 算式逐字是 `f"gap{中断结束日的 ISO 串}"`（判据表 + `app/db/models/feedback.py:613` 两处）→ **带不出来**。这与 P6-A1 是同一类缺陷、同一个成因（硬规矩 #110：逐字段回问「这个值从哪个入参来」），只是漏在另一条规则上 | `StudentSignals` 加 **`checkin_gap_end: str`**（调用方注入的 ISO 串；domain 不 import `datetime`、也不调 `isoformat()`，P6-A4 的裁定照办）。守卫 = `test_checkin_gap_window_key_uses_the_iso_date_injected_by_the_caller` |
| **5** | **Critical** | P6-A1 只给 **`ClassSignals`** 补 `semester_id` 与 `week` | **`GREEN_MASTERY` 是 student 作用域**（计划自己给的那份 YAML 逐字 `scope: student`，spec §8.2 的作用域列同），而它的 `window_key` 是 `f"{semester_id}:{week}"`（判据表 + `app/db/models/feedback.py:614` 两处）→ 在 `StudentSignals` 上**同样带不出来** | `StudentSignals` 也加 **`semester_id: int`** 与 **`week: int`**。守卫 = `test_class_and_mastery_window_keys_are_semester_colon_week`（一条测试里两个作用域各钉一次，于是「只补了一边」会红） |
| **6** | **Important** | 判据表：`GREEN_MASTERY` 写「`completion_rate == 1.0`（**不是 `>=`**，spec 逐字「100%」）」；而同一份 YAML 的参数名逐字是 **`completion_rate_min`** | 三条互相咬合的问题：① 一个叫 `_min` 的阈值被 `==` 消费是自相矛盾的（它就不是一个 min），下一个人改 YAML 会以为改它就能改行为；② `completion_rate` 是「打卡数 ÷ 应打卡训练日数」，值域 `[0, 1]`，故 `>= 1.0` 与 `== 1.0` 对**任何合法输入逐格等价**——spec 的「100%」没有被放宽；③ **写成 `==` 会让本 Task 唯一要求的变异测试对第 5 条规则没有靶子**（`==` → `>=` 在 `[0, 1]` 上不可分辨，任何测试都不会红），而派单逐字要求「5 条规则的比较符各做一次（`>=` ↔ `>`、`<` ↔ `<=`）」——`==` 不在这个变异集里 | 用 **`>=`**。三条理由逐字写进 `_mastery` 的 docstring，并按硬规矩 #39 写明它守不住什么（`completion_rate > 1.0` 时两者分岔；domain **刻意不夹取**，夹取就是把「比率该是多少」这条口径抄进 domain = 第二个所有者；方向上绿牌多给一张的代价远小于红牌多推一次减量）。**M5 的实跑结果就是这条顶回的证据**：`>=` → `>` 让 5 条红、边界靶命中 |
| **7** | **Important** | 判据表：「数据点不足 3 个 → 不触发 + **在 `snapshot` 里留痕** `"insufficient_points": n`」 | **不触发就没有 Hit，也就没有 `snapshot`**——留痕无处可放。而 `points_needed: 3` 是 YAML 的一个参数，故「够不够点」这个判断**必须在 domain**（否则 Task 7 得再读一次那个阈值 = 第二个所有者），且它今天**没有任何消费者**（`improve_pct` 至少还有 Task 7 那个交代的去处） | 每个求值器返回 **`(命中, 留痕)` 一对**；新增两个纯函数 **`student_skip_traces` / `class_skip_traces`** 取后半。于是「什么时候判不了」在代码里**只有一处**（拆成两套函数各判一次的话 `points_needed` 会被读两遍、两份判断迟早不一致）。`GREEN_MASTERY` 的 `completion_rate is None` 那一档**一并留痕**（计划只写了「不触发」）——三档是同一件事，一个本周没有应打卡训练日的学生与一个天天打卡的学生在教师端不该看起来一样 |
| **8** | Minor | P6-A2：「两处都从它 import」（字面读法是加载器直接用那 6 个公开名） | 那 6 个名字在 `refdata_prescription.py` 里共有 **57** 处调用点（AST 实测 `_fail` 44 / `_exact_keys` 6 / `_as_int` 3 / `_as_float` 2 / `_as_optional_text` 1 / `_line_index` 1）。逐点加一个关键字参数 = **57 次改坏一条被测试逐字钉住的报错文本的机会** | 落地成「**逻辑只有一份**（`app/refdata_yaml.py`）+ 每个消费者各留 **5 个一句转发的薄适配器**与 1 个别名」。⚠️ 薄适配器**不是**第二个所有者：判据、行号索引、退到父路径的措辞、`bool` 的排除、`int → float` 的收敛全在共用模块；适配器绑的是**每份文件自己的文档种类**，那本来就是各加载器的知识。单一所有者由 **AST 机器守**（闸 A1 定义点唯一 + A2 函数体恰好一句且在调谁 + A3 `is` 身份比对），不靠散文 |

⚠️ **顶回 #3/#4/#5 是同一条纪律的三次应用**：P6-A1 自己给出的判据（硬规矩 #110：
「定义一个纯函数的输出结构时，逐字段回问『这个值从哪个入参来』」）在**两个去重键**上
逐字段跑一遍，缺的 4 个字段就自己浮出来了。P6-A1 只跑了 `window_key` 的一半
（两条学生级规则的 id）与 `ClassSignals`，没跑 `subject_key`、也没跑
`YELLOW_CHECKIN_GAP` 与 `GREEN_MASTERY` 的 `window_key`。

### 7.2 没按派单做的地方 —— **7 处**

1. **`refdata_prescription.py` 的改法不是派单的字面形状**（= 顶回 #8）：派单写
   「改成从 `refdata_yaml` import 那 6 个，**删掉本地副本**」。实际是**删掉了 6 份实现**
   （−126 行），但留了 5 个一句转发的薄适配器 + 1 个别名（+49 行）。
   「副本」（逻辑的第二份）确实删干净了，删掉的是**绑定层**不是**实现层**。
2. **`alert_rules.yaml` 在计划给的逐字内容之外加了注释**（33 行注释 / 22 行数据）。
   **数据部分逐字不变**：`version: "1.0"` + 5 × (`level` / `scope` / `params`) 与计划给的
   那份逐字相同（`test_load_alert_rules_reads_the_five_spec_rules_verbatim` 拿
   `_SPEC_PARAMS` / `_SPEC_LEVELS` / `_SPEC_SCOPES` 三个字面量对账）。加注释的理由：
   这份文件按 spec §4.4 是**给体育专家手工维护**的，而 5 个阈值里 4 个在 spec §8.2 的
   口径表里被标成「**均待确认**」——不写出处的话，下一个人分不清「这个数是 spec 定的」
   与「这个数是工程约定」。口径同 `exercises.yaml`（23 247 B 里大量注释）。
3. **`tests/test_refdata_alerts.py` 的闸 A（6 条）不在派单的 Create 语义里**：派单说这个
   文件是 `refdata_alerts.py` 的测试（P6-A5 只要求它建 `_ALERTS_PUBLIC_BASELINE`）。
   把共用助手的单一所有者守卫放进来，是因为**它是 P6-A2 那条裁定的唯一机器守卫**
   （散文守不住：一个 docstring 写着「助手来自 refdata_yaml」与那个模块里躺着一份
   30 行的副本，读起来一样），而它没有别的自然住址（`tests/test_refdata_prescription.py`
   的主语是处方侧）。⚠️ 于是本文件今天有**两个主语**，模块 docstring 的第一段就写了这件事。
4. **加载器多做了 4 类计划没要求的校验**：① YAML 的 `scope` 与 `declared_scope()` 对账
   （没有它 `scope` 就是装饰：专家把它一翻而代码不跟着翻，是一件**什么也不发生**的事，
   而他会以为发生了；口径同 `refdata_prescription._template` 对 `reachable` 的处置）；
   ② 比率不在 `(0,1)` / `completion_rate_min` 不在 `(0,1]` / 计数 `< 1`
   （`drop_pct: 5.0` 会让那条规则**永不触发**、`streak: 0` 会让**每个学生每周一张红牌**
   且 `window_key` 去取 `rpe_session_ids[-1]`，两者都静默）；
   ③ `points_needed == consecutive + 1`（不等的话判据本身不会错，但「需 3 个数据点」
   会悄悄变成「需 N 个点才够格被检查」，首次触发的周次跟着漂）；
   ④ 计数必须是 `int` 而不是 `float`（`streak` 要当**下标**用，`3.0` 会在 domain 深处抛
   `TypeError`，离真因隔三层）。四类的共同点是**失效静默**，与 Review Focus 第 5 条同向。
5. **变异测试跑的是两个测试文件（70 条）而不是全量 1026 条**：5 个边界靶与它们的全部
   连带都在这两个文件里（`alerts.py` 的消费者今天只有它们），跑全量只会把 5 × 200 秒
   加进取证而不增加任何信息。⚠️ **收尾另跑了两次全量**（还原后 `1026 passed`、
   带 cov `1025 passed, 1 skipped`）确认还原是干净的。
6. **5 个新 `.py` 的工作树行尾从 LF 归一到 CRLF**（`t6_probes/normalize_eol.py`）：
   Write 工具落盘是 LF，而仓库其余 `.py` 在 `core.autocrlf=true` 下都是 CRLF。
   ⚠️ **双向取证 blob 逐字不变**：`git hash-object` 改前改后同为
   `138c8d43d6c0` / `0e4fdaba7cab` / `fcd7a0d9ad76` / `4168ff4acf40` / `1daa9bfc6de0`，
   `git add` 之后 `git diff --cached --stat` **为空**、`git status --short` 只剩两个未入库
   探针。⚠️ **`backend/data/alert_rules.yaml` 刻意不在名单里**（它被 `.gitattributes`
   钉成 LF、且被指纹按字节钉住）。⚠️ 归一后复跑
   `tests/domain/test_alerts.py + tests/test_refdata_alerts.py + tests/architecture +
   tests/test_refdata_prescription.py + tests/domain/test_prescription_templates.py`
   → **176 passed**；再复跑**全量** `python -m pytest -q` → **1026 passed, 1 warning
   in 170.56s**（即 §8.1 那个数的第二次独立取证，两次都在最终工作树状态上跑的）。
7. **`AlertLevel` 与 `Alert.LEVELS` 逐字相等的那条断言住在 `tests/domain/test_alerts.py`**
   （`test_alert_level_is_the_owner_and_the_db_check_domain_is_its_mirror`）——派单说
   「改为加一条测试断言两者逐字相等」但没指定住处。选 domain 侧是因为**所有者在 domain**；
   它从测试里 import `app.db.models.feedback`（测试不受分层守卫约束，
   `SCANNED_DIRS` 只扫 `app/` 下四个目录）。

### 7.3 待清扫 —— **5 条**（纯散文精度，Ruling 5 的「取消」档；无 Critical）

1. `app/refdata_prescription.py` 的 `equivalence()` docstring：「本模块公有函数是 **5** 个，
   第 5 个是 `sync_exercises`」——AST 实测 **8** 个（Plan 02 Task 3 自己加了
   `load_templates` / `templates` / `sync_templates` 之后没跟着改）。**本 Task 没动它的
   公开面**，故那句在改动前后同样假。
2. `tests/domain/test_prescription_templates.py:1104`：「实现方式是另跑一次 `yaml.compose`
   建一张『键路径 → 1 基行号』的索引（`:func:`app.refdata_prescription._line_index`）」
   ——那个**实现**今天住在 `app/refdata_yaml.py`，`_line_index` 在 `refdata_prescription`
   里只是一个别名。引用仍可解析（故不红），但「实现住在哪」这句过期了。
3. `app/refdata_prescription.py` 模块 docstring 的「两段的报错口径刻意不同」那一段
   （`:20-30`）没有指向 `app/refdata_yaml`——那套机制今天的住址。本 Task 在 `:31` 之后
   补了一段说明抽取，但**没有改写那一段本身**（改写它属于「动别人 Task 的散文」，
   且它今天仍然真）。
4. `app/refdata_alerts.py` 的 `_as_optional_text` 适配器**今天没有调用者**
   （`alert_rules.yaml` 里没有可空文本字段）。保留理由逐字写在它的 docstring 与模块
   docstring 里（与另一个消费者的适配器清单**逐字同形**，且它同时是闸 A2 的一个反面对照）。
   若将来仍无人用，可以在某个 Task 里连同 A2 的 `_ADAPTERS` 清单一起收窄。
5. **阈值个数的口径**：派单与计划都说「8 个阈值」，而 5 条规则的 `params` 逐个数下来是
   **9** 个（`drop_pct` / `consecutive` / `points_needed` / `rpe_min` / `streak` /
   `gap_days` / `mean_rpe_max` / `completion_rate_min` / `improve_pct`）。运行时口径实测
   `sum(len(r.params) for r in load_alert_rules().rules.values())` → **9**，
   逐条 `{'RED_MINITEST_DROP': 3, 'RED_RPE_SUSTAINED': 2, 'YELLOW_CHECKIN_GAP': 1,
   'YELLOW_CLASS_RPE_HIGH': 1, 'GREEN_MASTERY': 2}`。⚠️ 本报告的 §4.2 与 §3 一律按
   运行时口径说 **9** 个；那个「8」大概是把 `points_needed` 当成了 `consecutive` 的推论
   而没数进去（它确实由 §4.3 第 17 项那条不变量约束着）。**代码与测试一律用 9。**

### 7.4 关切（给 Task 7 与后续）—— **6 条**

1. **`student_skip_traces` / `class_skip_traces` 必须有消费者**，否则「判不了」的留痕
   仍然只活在 domain 的返回值里，而「这个学生这周为什么没有预警」依旧无从回答。
   口径同 `app/domain/prescription/triggers.py` 对 `insufficient_data` 的交代
   （「本模块只负责返回空 tuple，留痕是调用方的职责」）。落点建议：`daily_sync_run`
   的计数或一条 `warning` 日志。
2. **`rpe_session_ids` 必须按时间升序、且长度 == `rpe_streak`**。domain 校**长度**
   （`_require_parallel`，`:402`），**校不了顺序**——它拿不到 `class_session.session_date`。
   顺序错了 `window_key` 会锚到错误的那一次快评上，Review Focus 第 3 条的连乘就回来了。
   契约写在 `StudentSignals` 与 `_require_parallel` 的 docstring 里，**守卫归 Task 7**。
3. **`rpe_min`（9）与 `improve_pct`（0.03）由 Task 7 消费**（分别算 `rpe_streak` 与
   `mini_test_improved`）。Task 7 若不读它们，它们就是死配置——`alert_rules.yaml` 的
   注释与 `_rpe_sustained` / `_mastery` 的 docstring 都已经把这句话写明了
   （计划判据表对 `improve_pct` 的要求就是这个：「要在 docstring 里写明它由谁消费」）。
4. **`completion_rate` 必须由 Task 7 夹在 `[0, 1]`**：一个 > 1.0 的值会让 `GREEN_MASTERY`
   触发（`>=` 与 `==` 在这一档分岔，见顶回 #6）。方向上是安全的一侧（绿牌不改训练量），
   但 Task 7 的一个 off-by-one 会被它掩盖。
5. **`checkin_gap_days` 的语义有一半住在调用方**：「连续未打卡的**应打卡训练日**数，
   休息日不计入中断」（spec §8.2 口径表 #3）由 Task 7 按处方算；domain 不知道什么是训练日。
   这是本模块唯一一处「判据的语义有一半在 domain 之外」的地方，已在 `_checkin_gap` 的
   docstring 里写明。
6. **`AlertRules.params_of` 今天没有生产调用者**（domain 内部的 5 个求值器收整个
   `AlertRule`——判据要 `params`、命中要 `level`，两者必须来自同一行配置，分开取就有了
   「读到两条不同规则的阈值与级别」的可能）。它是计划 Interfaces 逐字要求的方法，
   留给 Task 7（例如周报里说明「本周按哪一版阈值判的」）。

---

## §8 最终验收

### 8.1 测试与覆盖率

| 命令 | 基线（`a8d61b4`） | 本 Task 落地后 |
|---|---|---|
| `cd backend; python -m pytest -q` | 956 passed | **1026 passed**, 1 warning in 101.29s |
| `… -q --cov=app.domain --cov-branch --cov-report=term-missing` | 996 / Miss **0** / 288 / BrPart **0** / **100%**（955 passed, 1 skipped） | **1147 / Miss 0 / 336 / BrPart 0 / 100%**（**1025 passed, 1 skipped**, 203.36s） |
| `app/domain/alerts.py` 单行 | —（不存在） | **151 stmts / Miss 0 / 48 branch / BrPart 0 / 100%** |
| `tests/architecture` | 8 passed | **8 passed** |
| `tests/db/test_models.py -k public_namespace` | 2 passed | **2 passed** |

**四个新数：`1147` / `0` / `336` / `0`（100%）** —— stmts 与 branch 各涨了
**+151** 与 **+48**（全部来自 `alerts.py`），而 **`Miss` 与 `BrPart` 仍是 0**、覆盖率仍是
**100%**（spec §12 的硬要求）。⚠️ 带 `--cov` 时是 `1025 passed, 1 skipped`、不带时
`1026 passed`——那 1 条 skip 是既有的（基线同样是 `955 / 956`），与本 Task 无关。

**既有 956 条一条都没退步**（1026 − 70 新增 = 956）。新增的 70 条 =
`tests/domain/test_alerts.py` **35** + `tests/test_refdata_alerts.py` **35**
（`pytest --collect-only -q` 口径；后者 = 闸 A 的 **6** 条 + 闸 B 的 **29** 条）。
⚠️ 分批：commit 1 只落地了闸 A 的 **5** 条（956 → **961**），commit 2 再加 **65** 条
（domain 侧 35 + 闸 A 的第 6 条 + 闸 B 的 29 条）→ **1026**。

### 8.2 各项不变量（探针 `t6_probes/invariants.py`）

| 项 | 基线 | 落地后 | 判 |
|---|---|---|---|
| 扫描面 | 51（pipeline 8 + db 11 + domain 16 + api 16） | **52**（8 + 11 + **17** + 16） | ✅ 只涨 domain 一格，与 P6-A3 的预测逐字相符 |
| `app/domain/` 的 `.py` | 16 | **17**（顶层 7 = `__init__` / **`alerts`** / `derive` / `indicators` / `percentile` / `stratify` / `tables`，+ `prescription/` 10） | ✅ `alerts.py` 在**顶层**（与 `prescription/` 无隶属关系） |
| 表数 | 25 | **25** | ✅ 本 Task 不建表 |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（`models.__all__` 仍 14） | ✅ 不动 |
| openapi paths（端点） | 56 | **56**（operations 84） | ✅ 本 Task 不加端点 |
| `app/refdata_yaml.py` / `app/refdata_alerts.py` 在 `SCANNED_DIRS` 里？ | — | **都不在**（`app/` 根下，与 `main.py` / `config.py` / `refdata.py` 同档） | ✅ 故扫描面**不因它们而涨**（52 = 51 + 1，那 1 是 `alerts.py`） |
| `_PRESCRIPTION_PUBLIC_BASELINE` | 51 | **51** | ✅ 不动（⚠️ 派单说的 24 是错的，见顶回 #2） |
| `_ALERTS_PUBLIC_BASELINE` | —（不存在） | **19**（domain 16 + refdata_alerts 3） | ✅ 新建 |
| `alerts.__all__` | — | **16** | ✅ |

### 8.3 禁区与指纹

| 项 | 判 |
|---|---|
| `national_standard_2014.csv` = `D2C8E539E2FA0029` | ✅ 逐字不变 |
| `exercises.yaml` = `5394B37F01DAC9AC` | ✅ 逐字不变 |
| `exercise_equivalence.yaml` = `822CB86A5E998301` | ✅ 逐字不变 |
| `backend/data/alert_rules.yaml` | ✅ 新增，`E48E3AC82BB45BB7` / 6 037 B / 85 LF / **0 CRLF** / 无 BOM |
| `git diff a8d61b4 HEAD --name-status -- backend/data` | ✅ **只有一行**：`A  backend/data/alert_rules.yaml` |
| `backend/pe.db` | ✅ **不存在**（探针一律显式设 `PE_DB_URL` 到 TEMP；探针库也没被建出来） |
| `backend/data/seed/` | ✅ 存在、**0 文件** |
| `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` | ✅ **一次都没跑** |
| 分支 / push / main | ✅ 全程在 `feature/plan-03-feedback-alert-crud-api`，**没 push、没碰 main** |
| 探针住址 | ✅ 一律在 `.superpowers/sdd/…/t6_probes/`（**9** 个：`extract_yaml_helpers.py` / `write_commit1.py` / `yaml_stats.py` / `invariants.py` / `write_commit2.py` / `mutate.py` / `normalize_eol.py` / `write_report.py` / `write_commit3.py`），**`backend/` 下一个都没留**（硬规矩 #108：架构守卫会 AST 解析工作树里的全部 `.py`，含未入库的）；每个写完都先 `python -m py_compile` 过一遍 |

### 8.4 三个 commit

| sha | 内容 |
|---|---|
| **`834fa34`** | `refactor(refdata):` 抽 `app/refdata_yaml.py`（6 个助手 + `doc_kind`）+ `refdata_prescription.py` 改成 5 个薄适配器 + 1 个别名 + `tests/test_refdata_alerts.py` 的闸 A 5 条。**956 → 961 passed**（既有 956 条一条没退步，报错文本逐字不变） |
| **`f08e9ce`** | `feat(alerts):` `data/alert_rules.yaml` + `app/domain/alerts.py` + `app/refdata_alerts.py` + `tests/domain/test_alerts.py`（35 条）+ `tests/test_refdata_alerts.py` 的闸 A 第 6 条与闸 B 29 条（共 +65）。**961 → 1026 passed**，`app/domain/` **1147/0/336/0/100%** |
| **本次 commit** | `test(alerts):` 变异取证（5 条 × 三重还原，脚本 `t6_probes/mutate.py`）+ 收尾（`normalize_eol.py`、本报告）。sha 见 `git log --oneline -1` |

⚠️ **fix round：0 轮**（`tests/domain/test_alerts.py` 的 35 条与 `tests/test_refdata_alerts.py`
的闸 A 第 6 条 + 闸 B 29 条，在实现落地后**一次跑绿**：`70 passed in 1.28s`；
两个测试文件在写实现之前先跑过红，红的原因是
`ImportError: cannot import name 'refdata_alerts' from 'app'`——正是「功能还没有」。
⚠️ 闸 A 的前 5 条另有一次**先红**：在改 `refdata_prescription.py` 之前跑，
`2 failed, 3 passed`，红的原因逐字见 §2.4 末尾）。

---

## 附：本 Task 落地的文件（字节 / 行，`read_bytes()` 口径，行尾归一之后）

| 路径 | 字节 | 行 | 行尾 |
|---|---|---|---|
| `backend/app/refdata_yaml.py` | 13 022 | 239 | CRLF（blob 与 LF 版逐字相同） |
| `backend/app/refdata_alerts.py` | 25 644 | 427 | CRLF（同上） |
| `backend/app/domain/alerts.py` | 39 831 | 721 | CRLF（同上） |
| `backend/tests/domain/test_alerts.py` | 42 485 | 795 | CRLF（同上） |
| `backend/tests/test_refdata_alerts.py` | 53 118 | 989 | CRLF（同上） |
| `backend/data/alert_rules.yaml` | **6 037** | **85** | **LF（刻意，指纹 + `.gitattributes`）** |
| `backend/app/refdata_prescription.py`（改） | 64 157 | 1 152 | CRLF（原本就是；−2 595 B / −77 行） |

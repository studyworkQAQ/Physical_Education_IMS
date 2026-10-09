"""Plan 03 Task 6：计划更正（P6-A1..A5）+ 账本 Ruling 15 + 生成派单头。一次跑完。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-08-实施计划03-反馈预警与CRUD-API层.md"
LEDGER = HERE / "progress.md"
HEAD = HERE / "_dispatch_head_6.md"
edits = []


def patch(path, pairs):
    raw = path.read_bytes()
    t = raw.decode("utf-8")
    nl = "\r\n" if "\r\n" in t else "\n"
    b0 = (len(raw), t.count(nl))
    for old, new, count, label in pairs:
        if nl != "\n":
            old = old.replace("\r\n", "\n").replace("\n", nl)
            new = new.replace("\r\n", "\n").replace("\n", nl)
        n = t.count(old)
        assert n == count, f"[{label}] 期望 {count}，实为 {n}\n  old={old[:90]!r}"
        t = t.replace(old, new)
        edits.append((label, n))
    path.write_bytes(t.encode("utf-8"))
    c = path.read_bytes().decode("utf-8")
    print(f"[{path.name}] {b0[0]} B / {b0[1]} 行 -> {len(c.encode('utf-8'))} B / {c.count(nl)} 行")


PRE = """
### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `4e7cc08`，取证脚本 `t6_probes/_preflight.py`，**写完先 `py_compile` 过一遍**——硬规矩 #108）

**测试基线**：`956 passed`；`app/domain/` **996/0/288/0/100%**；**25 张表**；扫描面 **51**（pipeline 8 + db 11 + domain **16** + api 16）；**56 个端点在线**。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P6-A1** | **Critical** | **`StudentSignals` 带不出 `window_key`。** 计划的字段清单是 `rpe_streak: int` / `mini_test_scores: tuple[float, ...]` / `checkin_gap_days: int` / `completion_rate: float \\| None` / `mini_test_improved: bool` —— **一个 id 都没有**。而 `StudentHit.window_key` 的算式逐字要「`f\"rpe{第 3 次快评的 class_session_id}\"`」与「`f\"mt{mini_test_scores 最后一项的 id}\"`」。**`ClassSignals` 同样缺**：它只有 `mean_rpe` / `student_count`，而 `YELLOW_CLASS_RPE_HIGH` 与 `GREEN_MASTERY` 的 `window_key` 是 `f\"{semester_id}:{week}\"`。 | **`StudentSignals` 加两个与既有字段平行的 id 元组**：`rpe_session_ids: tuple[int, ...]`（与 `rpe_streak` 平行，取**触发那一次**的 id）与 `mini_test_ids: tuple[int, ...]`（与 `mini_test_scores` 平行，同序）。**`ClassSignals` 加 `semester_id: int` 与 `week: int`。** ⚠️ **为什么把 id 放进 domain 而不是让 Task 7 在 I/O 层拼 `window_key`**：`window_key` 是**去重键**，而它承重的是 Review Focus 第 3 条（「同一次触发只有一条 alert、只推一次减量 20%」）——**放在 domain 里它是纯函数、能被单元测试穷举；放在 `alert_stage` 里它只能靠集成测试撞**。Plan 02 的同一条纪律是「值类型住 domain、加载器住 domain 外」 |
| **P6-A2** | **Important** | **YAML 报错的那套助手是 `refdata_prescription.py` 的私有函数**，实测共 16 个，其中**通用的有 6 个**：`_line_index(text) -> dict[tuple, int]`、`_fail(path, lines, key_path, message) -> ValueError`、`_exact_keys(path, lines, where, raw, required, label) -> None`、`_as_float(...)`、`_as_int(...)`、`_as_optional_text(...)`。计划 Task 6 的决定写「**直接照抄那套形状**，不要另发明一套」—— **「照抄」在字面上等于复制，而复制就是第二个所有者。** | **抽公共模块 `app/refdata_yaml.py`**，把那 6 个通用助手搬进去（**改名去掉前导下划线**，因为它们跨模块了），`refdata_prescription.py` 与 `refdata_alerts.py` 都从它 import。⚠️ **这与 Plan 02 遗留的那条 Minor 是同一条纪律**（「两份守卫的重复代码在 Plan 03 加第三个守卫时必须抽公共模块」）。⚠️ **搬的是私有助手，不改 `refdata_prescription.py` 的公开面** → `_PRESCRIPTION_PUBLIC_BASELINE`（**24 个二元组**）**不动**；**指纹测试钉的是 YAML 文件、不是 `.py`** → 也不动。⚠️ `app/refdata_yaml.py` 在 `app/` 根下，**不在 `SCANNED_DIRS` 任何一项里**（与 `app/main.py` / `app/config.py` / `app/refdata.py` 同档），故架构守卫不扫它 |
| **P6-A3** | 确认（无需改） | **两份守卫的下界全是 `>=`**：`test_domain_purity.py` 的 `len(scanned) >= 5`、`len(real_py) >= 40`、`relative_seen >= 16`；`test_layering.py` 的 `len(scanned) >= 18`（= pipeline 5 + db 5 + domain 5 + api 3）、`len(api_py) >= 3`、`len(reverse_py) >= 15`、`len(cases) >= 22`。**加一个 domain 模块（16 → 17，扫描面 51 → 52）不会让任何一条红。** | **S6 的裁定兑现了：本 Task 不需要动任何下界断言。** 报告里只需写明扫描面 51 → 52 |
| **P6-A4** | 确认（无需改） | **`ALLOWED_MODULES` 实测 = `{collections, collections.abc, dataclasses, enum, numpy, typing}`** —— `alerts.py` 要的 `dataclasses` / `enum` / `collections.abc` / `typing` **全在里面**。 | **不需要改 purity 守卫。** ⚠️ 但 `alerts.py` **不得 import `datetime`**（不在白名单）→ `window_key` 里要用的日期串**必须由调用方传进来**（Task 7 传 ISO 串），**不能在 domain 里 `date.isoformat()`**……⚠️ **更正：`isoformat()` 是实例方法，不需要 import `datetime`**，故只要 `StudentSignals` / `ClassSignals` 里的日期字段**由调用方注入**（`datetime.date` 对象本身也不需要 import 就能当参数类型——但**注解里写 `dt.date` 就需要 import**）。**决定：注解一律用字符串形式或干脆不注解那两个字段的具体类型，避免 import `datetime`**；实现者若发现绕不过去，**顶回来** |
| **P6-A5** | Minor | **`refdata_prescription.py` 没有 `__all__`**（实测 `getattr(RP, '__all__', '（无）')` → 无），它的公开面是靠 `test_refdata_prescription.py` 的 `_PRESCRIPTION_PUBLIC_BASELINE`（**24 个 `(名字, 所有者模块)` 二元组** + `assert len(...) == 24`）从**外部**钉住的。 | `refdata_alerts.py` **照它的形状办：不写 `__all__`**，改在 `tests/test_refdata_alerts.py` 里建一份 **`_ALERTS_PUBLIC_BASELINE`**（`app.domain.alerts` 的公开名 + `refdata_alerts` 的公开名，逐个带所有者模块），并 `assert len(...) == <自己数>`。**⚠️ 数用运行时口径**（硬规矩 #89） |

"""

patch(PLAN, [
    ("## Task 6: 预警规则 —— `alert_rules.yaml` + `app/domain/alerts.py`\n\n**Files:**",
     "## Task 6: 预警规则 —— `alert_rules.yaml` + `app/domain/alerts.py`\n" + PRE + "\n**Files:**",
     1, "P6 插入预检更正总表"),

    # P6-A1：StudentSignals / ClassSignals 补 id
    ("  - `StudentSignals`（frozen）：**一个学生在某一周的全部输入**（`rpe_streak: int`（当前连续 ≥ 阈值的次数）/ "
     "`mini_test_scores: tuple[float, ...]`（按周次升序，最近 3 个）/ `checkin_gap_days: int`（连续未打卡的**应打卡训练日**数）/ "
     "`completion_rate: float | None` / `mini_test_improved: bool`）\n"
     "  - `ClassSignals`（frozen）：`mean_rpe: float | None` / `student_count: int`",
     "  - `StudentSignals`（frozen）：**一个学生在某一周的全部输入**（`rpe_streak: int`（当前连续 ≥ 阈值的次数）/ "
     "`mini_test_scores: tuple[float, ...]`（按周次升序，最近 3 个）/ `checkin_gap_days: int`（连续未打卡的**应打卡训练日**数）/ "
     "`completion_rate: float | None` / `mini_test_improved: bool`）"
     "**⚠️ P6-A1 更正：还要加两个与既有字段平行的 id 元组 —— `rpe_session_ids: tuple[int, ...]`"
     "（与 `rpe_streak` 平行，`window_key` 要取**触发那一次**的 `class_session_id`）与 "
     "`mini_test_ids: tuple[int, ...]`（与 `mini_test_scores` **同序**，`window_key` 要取最后一项的 `mini_test.id`）。"
     "原清单里一个 id 都没有，而 `StudentHit.window_key` 的算式逐字要它们** —— 照原清单写，"
     "`window_key` 在 domain 里根本拼不出来**\n"
     "  - `ClassSignals`（frozen）：`mean_rpe: float | None` / `student_count: int`"
     "**⚠️ P6-A1 更正：还要加 `semester_id: int` 与 `week: int`** —— "
     "`YELLOW_CLASS_RPE_HIGH` 与 `GREEN_MASTERY` 的 `window_key` 是 `f\"{semester_id}:{week}\"`，原清单里两个都没有\n"
     "  **⚠️ 为什么把 id 放进 domain 而不是让 Task 7 在 I/O 层拼 `window_key`**：`window_key` 是**去重键**，"
     "它承重的是 Review Focus 第 3 条（「同一次触发只有一条 alert、只推一次减量 20%」）—— "
     "**放在 domain 里它是纯函数、能被单元测试穷举；放在 `alert_stage` 里它只能靠集成测试撞**。"
     "Plan 02 的同一条纪律是「值类型住 domain、加载器住 domain 外」（Ruling 96）",
     1, "P6-A1 Signals 补 id"),

    # P6-A2：抽公共模块，不是照抄
    ("- **加载器与 domain 的分层照 Plan 02 的既有做法**（Ruling 96）：**值类型住 domain（`alerts.py`）、加载器住 domain 外（`refdata_alerts.py`）、"
     "加载器 import 值类型**。`load_alert_rules(path=None) -> AlertRules` + `alert_rules()` 单例"
     "（**`load_*` 只加载不缓存，单例是另一个函数**，P2-A9）。",
     "- **加载器与 domain 的分层照 Plan 02 的既有做法**（Ruling 96）：**值类型住 domain（`alerts.py`）、加载器住 domain 外（`refdata_alerts.py`）、"
     "加载器 import 值类型**。`load_alert_rules(path=None) -> AlertRules` + `alert_rules()` 单例"
     "（**`load_*` 只加载不缓存，单例是另一个函数**，P2-A9）。\n"
     "- **⚠️ P6-A2 更正：YAML 报错的那套助手要抽成公共模块 `app/refdata_yaml.py`，不是「照抄」。** "
     "实测它是 `refdata_prescription.py` 的 **16 个私有函数**，其中**通用的有 6 个**："
     "`_line_index(text) -> dict[tuple, int]`、`_fail(path, lines, key_path, message) -> ValueError`、"
     "`_exact_keys(path, lines, where, raw, required, label) -> None`、`_as_float(...)`、`_as_int(...)`、`_as_optional_text(...)`。"
     "**原文说「直接照抄那套形状」，而「照抄」在字面上等于复制、复制就是第二个所有者。** "
     "**把那 6 个搬进 `app/refdata_yaml.py`（改名去掉前导下划线，因为它们跨模块了），两处都从它 import。** "
     "⚠️ **这与 Plan 02 遗留的那条 Minor 是同一条纪律**（「两份守卫的重复代码在 Plan 03 加第三个守卫时必须抽公共模块」）。"
     "⚠️ **搬的是私有助手、不改 `refdata_prescription.py` 的公开面** → `_PRESCRIPTION_PUBLIC_BASELINE`（**24 个二元组**）**不动**；"
     "**指纹测试钉的是 YAML 文件、不是 `.py`** → 也不动。"
     "⚠️ `app/refdata_yaml.py` 在 `app/` 根下，**不在 `SCANNED_DIRS` 任何一项里**"
     "（与 `app/main.py` / `app/config.py` / `app/refdata.py` 同档），故架构守卫不扫它、扫描面也不因它而涨。",
     1, "P6-A2 抽公共模块"),

    # P6-A5：不写 __all__，建 _ALERTS_PUBLIC_BASELINE
    ("- **指纹测试**：`alert_rules.yaml` 加一条 sha256[:16] 指纹（照 `exercises.yaml` / `exercise_equivalence.yaml` 的口径），"
     "**防止有人在跑测试的间隙改阈值**。",
     "- **指纹测试**：`alert_rules.yaml` 加一条 sha256[:16] 指纹（照 `exercises.yaml` / `exercise_equivalence.yaml` 的口径，"
     "算法逐字是 `hashlib.sha256(path.read_bytes().replace(b\"\\r\\n\", b\"\\n\")).hexdigest()[:16].upper()`），"
     "**防止有人在跑测试的间隙改阈值**。⚠️ **`.gitattributes` 的 `backend/data/*.yaml text eol=lf` 已覆盖它**"
     "（它直接在 `backend/data/` 下，不在子目录），**但写完仍要用 `read_bytes()` 复核 CRLF 计数为 0**（硬规矩 #89 的扩写）。\n"
     "- **⚠️ P6-A5：公开面基线守卫照 `test_refdata_prescription.py` 的形状办** —— 实测 `refdata_prescription.py` "
     "**没有 `__all__`**，它的公开面是靠 `_PRESCRIPTION_PUBLIC_BASELINE`（**24 个 `(名字, 所有者模块)` 二元组** + "
     "`assert len(...) == 24`）从**外部**钉住的。故 `refdata_alerts.py` **也不写 `__all__`**，"
     "改在 `tests/test_refdata_alerts.py` 里建一份 **`_ALERTS_PUBLIC_BASELINE`**"
     "（`app.domain.alerts` 与 `app.refdata_alerts` 的公开名，逐个带所有者模块）+ `assert len(...) == <自己数>`。"
     "**⚠️ 数用运行时口径**（硬规矩 #89）。⚠️ **`app.domain.alerts` 要写 `__all__`**（它是 domain 模块，"
     "与 `app/domain/prescription/*.py` 同档，那些都写）。",
     1, "P6-A5 公开面基线守卫"),
])

# ============ 账本 ============
lb = LEDGER.read_bytes()
lt = lb.decode("utf-8")
lnl = "\r\n" if "\r\n" in lt else "\n"
print(f"[ledger before] bytes={len(lb)} lines={lt.count(lnl)}")

BODY = """

---

### Task 6: 预警规则（`alert_rules.yaml` + `app/domain/alerts.py`）— 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`4e7cc08`。**测试基线**：`956 passed`；domain **996/0/288/0/100%**；**25 张表**；扫描面 **51**；**56 个端点在线**。
**取证脚本**：`t6_probes/_preflight.py`（一份，Ruling 1 的口径）。⚠️ **按硬规矩 #108 先 `python -m py_compile` 过一遍再跑**（架构守卫会 AST 解析工作树里的全部 `.py`，含未入库的探针；Task 5 的实现者就撞过一次：探针里一句含反斜杠的 f-string 让 `test_absolute_folding_matches_resolve_name` 红 2 条）。

#### Ruling 15 — 预检查出 1 Critical / 1 Important / 2 确认 / 1 Minor，计划正文更正 4 处

**P6-A1（Critical）：`StudentSignals` 带不出 `window_key`。** 计划的字段清单是 `rpe_streak: int` / `mini_test_scores: tuple[float, ...]` / `checkin_gap_days: int` / `completion_rate: float | None` / `mini_test_improved: bool` —— **一个 id 都没有**。而 `StudentHit.window_key` 的算式逐字要「`f"rpe{第 3 次快评的 class_session_id}"`」与「`f"mt{mini_test_scores 最后一项的 id}"`」。**`ClassSignals` 同样缺**：它只有 `mean_rpe` / `student_count`，而 `YELLOW_CLASS_RPE_HIGH` 与 `GREEN_MASTERY` 的 `window_key` 是 `f"{semester_id}:{week}"`。
**裁定**：`StudentSignals` 加 `rpe_session_ids: tuple[int, ...]`（与 `rpe_streak` 平行）与 `mini_test_ids: tuple[int, ...]`（与 `mini_test_scores` **同序**）；`ClassSignals` 加 `semester_id: int` 与 `week: int`。
**⚠️ 为什么把 id 放进 domain、而不是让 Task 7 在 I/O 层拼 `window_key`**：`window_key` 是**去重键**，它承重的是 Review Focus 第 3 条（「同一次触发只有一条 alert、只推一次减量 20%」，否则 `0.8³ = 0.512`）—— **放在 domain 里它是纯函数、能被单元测试穷举；放在 `alert_stage` 里它只能靠集成测试撞**。这与 Plan 02 的 Ruling 96（「值类型住 domain、加载器住 domain 外」）是同一条纪律。
**→ 控制者错误 #25**：**写「输出结构体有一个字段 X」时，没有回头核「输入结构体带得出 X 吗」**。这与 Plan 03 的控制者错误 #17（`TrainingPackage` 没有 `weekly_frequency`）、Plan 02 的 #148（`LastPrescription` 的 5 个字段没逐个对到列上）是**同一族的第 3 次** —— 都是「在一个结构里引用另一个结构的字段，没核对方手上有没有它」。
**→ 补硬规矩 #110：定义一个纯函数的输出结构时，逐字段回问「这个值从哪个入参来」；答不上来就是入参缺字段，而不是「实现时再想办法」。** 依据：#25 / #17 / #148。**⚠️ 这一族已经三次了，而三次都是预检或实现者抓到的、没有一次是控制者写的时候自己抓到的。**

**P6-A2（Important）：YAML 报错的那套助手是 `refdata_prescription.py` 的私有函数，「照抄」等于复制、复制就是第二个所有者。** 实测它有 **16 个私有函数**，其中**通用的 6 个**是 `_line_index(text) -> dict[tuple,int]`、`_fail(path, lines, key_path, message) -> ValueError`、`_exact_keys(path, lines, where, raw, required, label) -> None`、`_as_float(...)`、`_as_int(...)`、`_as_optional_text(...)`。
**裁定：抽公共模块 `app/refdata_yaml.py`**，把那 6 个搬进去（**改名去掉前导下划线**，因为它们跨模块了），`refdata_prescription.py` 与 `refdata_alerts.py` 都从它 import。⚠️ **这与 Plan 02 遗留的那条 Minor 是同一条纪律**（「两份守卫的重复代码在 Plan 03 加第三个守卫时必须抽公共模块」）—— 那次说的是架构守卫，这次说的是 YAML 加载器，**形状一样**。
⚠️ **搬的是私有助手、不改 `refdata_prescription.py` 的公开面** → `_PRESCRIPTION_PUBLIC_BASELINE`（**24 个二元组**）**不动**；**指纹测试钉的是 YAML 文件、不是 `.py`** → 也不动。⚠️ `app/refdata_yaml.py` 在 `app/` 根下，**不在 `SCANNED_DIRS` 任何一项里**（与 `app/main.py` / `app/config.py` / `app/refdata.py` 同档），故架构守卫不扫它、**扫描面也不因它而涨**（只涨 `app/domain/alerts.py` 那一个：51 → 52）。

**P6-A3（确认，无需改）：两份守卫的下界全是 `>=`** —— `test_domain_purity.py` 的 `len(scanned) >= 5`、`len(real_py) >= 40`、`relative_seen >= 16`；`test_layering.py` 的 `len(scanned) >= 18`（= pipeline 5 + db 5 + domain 5 + api 3）、`len(api_py) >= 3`、`len(reverse_py) >= 15`、`len(cases) >= 22`。**加一个 domain 模块（16 → 17，扫描面 51 → 52）不会让任何一条红。S6 的裁定兑现了：本 Task 不需要动任何下界断言。**

**P6-A4（确认，无需改）：`ALLOWED_MODULES` 实测 = `{collections, collections.abc, dataclasses, enum, numpy, typing}`** —— `alerts.py` 要的 `dataclasses` / `enum` / `collections.abc` / `typing` **全在里面**，**不需要改 purity 守卫**。⚠️ 但 **`datetime` 不在白名单** → `alerts.py` 不得 import 它。**若日期字段的类型注解绕不过去（写 `dt.date` 就要 import），实现者应顶回来**，可选的处置有三：注解写成字符串形式（`"dt.date"` 仍需 import 才能求值，故不行）、干脆不注解那两个字段、或**把日期字段换成调用方已算好的 `str`**（控制者倾向第三个：`window_key` 里要的本来就是 ISO 串）。

**P6-A5（Minor）：`refdata_prescription.py` 没有 `__all__`** —— 它的公开面是靠 `test_refdata_prescription.py` 的 `_PRESCRIPTION_PUBLIC_BASELINE`（**24 个 `(名字, 所有者模块)` 二元组** + `assert len(...) == 24`）从**外部**钉住的。**裁定：`refdata_alerts.py` 照它的形状办（不写 `__all__`）**，改在 `tests/test_refdata_alerts.py` 里建 `_ALERTS_PUBLIC_BASELINE` + `assert len(...) == <自己数>`（**数用运行时口径**，硬规矩 #89）。⚠️ 而 **`app/domain/alerts.py` 要写 `__all__`**（它是 domain 模块，与 `app/domain/prescription/*.py` 同档，那些都写）。

**顺带核实到的**：`app/domain/` 今天 16 个 `.py` = 顶层 6 个（`__init__.py` 0 B、`derive.py` 39 717 B、`indicators.py` 23 244 B、`percentile.py` 43 088 B、`stratify.py` 18 851 B、`tables.py` 1 495 B）+ `prescription/` 子包 10 个。**`alerts.py` 放顶层是对的**（它与 `prescription/` 无隶属关系；而 spec §8.2 的预警规则也不属于处方装配）。`Alert` 表的类常量实测有 `LEVELS` / `STATUSES`（`level` ∈ red/yellow/green、`status` ∈ pending/handled/ignored），**`AlertLevel` 枚举的值要与 `Alert.LEVELS` 逐字一致**（单一所有者的问题：谁拥有那三个字符串？裁定 **`app/domain/alerts.py` 的 `AlertLevel` 是所有者，`Alert.LEVELS` 是它的 DB 镜像** —— 但 `Alert.LEVELS` 今天已经存在且被 `_in_domain` 用着，故本 Task **不改它**，改为**加一条测试断言两者逐字相等**）。

**计划正文更正**：`_t6_preflight_patch.py`，**4 处替换全部命中 1 次**（硬规矩 #79）。

**下一步**：抽 `task-6-brief.md` → 派实现者。**⚠️ 本 Task 是本计划唯一要求变异测试的**（Ruling 1：5 条规则的比较符各做一次，断言对应的边界测试变红；按硬规矩 #83 的 `.pyc` 纪律做，且**每条变异要先论证它在结构上可达**——硬规矩 #92）。
"""

if lnl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", lnl)
SENT = "Ruling 15 — 预检查出 1 Critical / 1 Important / 2 确认 / 1 Minor"
assert SENT not in lt, f"{SENT!r} 已存在"
LEDGER.write_bytes((lt.rstrip("\r\n") + BODY).encode("utf-8"))
c2 = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c2.encode('utf-8'))} lines={c2.count(lnl)}")
for k in ("Ruling 15", "硬规矩 #110", "控制者错误 #25", "P6-A1", "refdata_yaml"):
    print(f"  {k}: {c2.count(k)}")
print(f"\n[plan edits] {len(edits)} 处：")
for lab, n in edits:
    print(f"  {n}x  {lab}")

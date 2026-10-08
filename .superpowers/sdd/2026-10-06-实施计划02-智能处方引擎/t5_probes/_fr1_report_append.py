# -*- coding: utf-8 -*-
"""往 ``task-5-report.md`` **末尾追加** `## Task 5 fix round 1` 一节（只用 python，绝不用编辑器工具）。

⚠️ 这个文件是**纯 LF / 无 BOM**（与 progress.md 的纯 CRLF 相反），故追加内容一律写 ``\\n``。
两个 commit 的 sha 在运行时从 git 读，不手写。
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
REPORT = ROOT / ".superpowers" / "sdd" / "2026-10-06-实施计划02-智能处方引擎" / "task-5-report.md"


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def stats(p: pathlib.Path):
    raw = p.read_bytes()
    text = raw.decode("utf-8")
    crlf = text.count("\r\n")
    return dict(bytes=len(raw), splitlines=len(text.splitlines()),
                split_lf=len(text.split("\n")), crlf=crlf, bare_lf=text.count("\n") - crlf,
                bom=raw.startswith(b"\xef\xbb\xbf"))


SHA1 = git("rev-parse", "--short", "HEAD~1")
SHA2 = git("rev-parse", "--short", "HEAD")
SUBJ1 = git("log", "-1", "--format=%s", "HEAD~1")
SUBJ2 = git("log", "-1", "--format=%s", "HEAD")

LINES = [
    "",
    "---",
    "",
    "## Task 5 fix round 1",
    "",
    f"**基线** `fc8f5a8` → **本轮 2 个 commit**：`{SHA1}`（`{SUBJ1}`）/ "
    f"`{SHA2}`（`{SUBJ2}`）。",
    "**分支** `feature/plan-02-prescription-engine`。**没 push、没切分支、没碰 main。**",
    "**TDD**：F1-1 与 F1-2 都是先改测试跑到 **9 failed / 49 passed**（红的原因逐条是"
    "「`168.0` != `{'min': 48.0, 'reps': 120.0}`」「`'float' object is not iterable`」"
    "「`DID NOT RAISE ValueError`」，不是 import 错误），再改实现跑到全绿。",
    "",
    "### 0. 一句话结论",
    "",
    "5 项全部落地。全量 **672 → 679 passed**（不带 `--cov`）/ **678 passed, 1 skipped**"
    "（带 `--cov`）；覆盖率四格 **888/0/260/0 → 905/0/262/0/100%**；公开面 `__all__` "
    "**43 → 43**；扫描面 **32**；三个禁区指纹逐字不变；`backend/data/` 一个字节没动。"
    "计划正文 **151 467 B / 938 行 → 159 408 B / 939 行**；账本 "
    "**336 427 B / 2 153 行 → 346 910 B / 2 214 行**。",
    "**顶回控制者 6 处**（第 7–12 次），见 §9；**没按派单字面做的 7 处**，见 §8。",
    "",
    "### 1. F1-1（Critical）`weekly_volume_base` 从混合量纲改成按单位分列的只读 Mapping",
    "",
    "#### 1.1 新类型与那个例子的逐字面值（**期望值自己算**，硬规矩 #44）",
    "",
    "| 项 | 改前 | 改后 |",
    "|---|---|---|",
    "| 类型 | `float` | **`Mapping[str, float]`**（运行时是私有的 `_ReadOnlyVolumeBase`，"
    "`dict` 的子类，MRO = `[_ReadOnlyVolumeBase, dict, object]`） |",
    "| `RED-END-ABN-01`（男 20 岁、`endurance_score=50`）那一格 | `168.0` | "
    "**`{\"min\": 48.0, \"reps\": 120.0}`** |",
    "| 快照键数 | 12 | **12**（键名与键序一个字没动，"
    "`test_assembly_snapshot_keys_are_exactly_the_pinned_set` 仍全绿） |",
    "",
    "**我自己算的过程**（不复用 `assembler.py` 的任何代码；探针 "
    "`t5_probes/_fr1_recompute_volume_base.py` 直接读 `backend/data/prescription/*.yaml`，"
    "自己数 `sessions_per_week`、自己做乘法）：",
    "",
    "```",
    "RED-END-ABN-01：weekly_frequency = 4、sessions = 4、",
    "                per_ref = {interval_run: 4, compound_circuit: 4}",
    "  interval_run      structure {sets:4, work_min:3, rest_min:2}",
    "                    base = work_min × sets = 3 × 4 = 12 min/课",
    "                    min 档 = 12 × 4 课 = 48.0        （= base × sessions_per_week）",
    "  compound_circuit  structure {rounds:3, reps:10}",
    "                    base = rounds × reps = 3 × 10 = 30 reps/课",
    "                    reps 档 = 30 × 4 课 = 120.0",
    "  → {\"min\": 48.0, \"reps\": 120.0}      48.0 + 120.0 = 168.0 = 改前那个混合量纲的数 ✓",
    "```",
    "",
    "**与控制者派单里那个分解逐格相符**（派单自己写的「它是 `48.0 min + 120.0 reps` 相加的"
    "结果」），故不存在「先怀疑自己还是先怀疑派单」的分歧。",
    "",
    "顺带亲算了另外两套，用来证明**键集不是硬写死的**（它们各只有一个单位）：",
    "`GRN-END-NOR-14`（绿、2 课 × 2 个 12 min）= **`{\"min\": 48.0}`**；"
    "`YEL-STR-ABN-09`（黄、3 课 × 2 个 30 reps）= **`{\"reps\": 180.0}`**。",
    "⚠️ 绿层那套的 `min` 档**恰好也是 48.0**，与红层同值而来源完全不同"
    "（2 课 × 2 个 12 min 对 4 课 × 1 个 12 min）——这正是「按单位分列」比「一个总数」"
    "信息量大的地方。",
    "",
    "**18 套的键集分布**（探针独立算出、字面写死进测试）：",
    "`{(\"min\",): 10, (\"reps\",): 6, (\"min\", \"reps\"): 2}`——**16/18 套只有一个单位**，"
    "只有 `RED-END-ABN-01` / `RED-END-NOR-02` 两个都有。`\"unspecified\"` **0 次出现**"
    "（`assemble` 跑在 `apply_safety` 之前，那时还没有 addon block），与派单的预期一致。",
    "",
    "#### 1.2 `types` 是否被守卫放行 —— **实测：不放行**",
    "",
    "探针 `t5_probes/_fr1_probe_types_json.py`，做法是**真的把 `import types` 插进 "
    "`assembler.py`**（插在 `from collections import Counter` 上面一行）再跑守卫，"
    "跑完 `write_bytes(original)` 逐字节还原，并按**硬规矩 #83** 在每次跑测试前 "
    "`shutil.rmtree(__pycache__)` + 子进程设 `PYTHONDONTWRITEBYTECODE=1`：",
    "",
    "```",
    "[对照 M0：未插 import types] exit=0   4 passed in 0.22s",
    "[变异 M1：插了 import types] exit=1   1 failed, 3 passed in 0.37s",
    "  FAILED tests/architecture/test_domain_purity.py::test_domain_imports_stay_within_the_allow_list",
    "  AssertionError: app/domain 是叶子层，import 必须落在白名单内",
    "    （['collections', 'collections.abc', 'dataclasses', 'enum', 'numpy', 'typing'] + app.domain.*）：",
    "      assembler.py:148: types",
    "[还原] sha256 相同 = True（31817 B）",
    "```",
    "",
    "→ **`types` 不放行**，故 `types.MappingProxyType` 在 domain 里拿不到。"
    "**不改守卫**：往 `ALLOWED_MODULES` 加模块是扩大 domain 可用面的架构决策，"
    "与 P5-A4 拒绝 `math`、Task 3 拒绝 `datetime` 同一条纪律。",
    "",
    "#### 1.3 JSON 序列化测试（**派单说这是本轮最容易漏的一条**）",
    "",
    "两条，都在 `allow_nan=False` 下：",
    "",
    "| 测试 | 位置 | 钉的是什么 |",
    "|---|---|---|",
    "| `test_assembly_snapshot_is_json_serialisable` | "
    "`tests/domain/test_prescription_assembler.py` | `assemble` 直出的 **12** 键整个能 "
    "`json.dumps(snap, allow_nan=False)`；序列化文本里逐字含 "
    "`\"weekly_volume_base\": {\"min\": 48.0, \"reps\": 120.0}`、**不含** `168.0`；"
    "round-trip 之后 12 个键名与序不变；`endurance_score is None` 那一档序列化成 `null` "
    "而不是 `NaN`；round-trip 之后那一格是**普通 `dict`**，改它**不会**回写进程内的快照 |",
    "| `test_the_safety_snapshot_is_json_serialisable` | "
    "`tests/domain/test_prescription_safety.py` | `apply_safety` 之后那 **15** 键"
    "（= 12 + 3）整个能 JSON 化。⚠️ **这一条比上一条更承重**：Task 6 落进 "
    "`prescription.assembly_snapshot` 那个 `JsonText` 列的是**安全后置之后**的快照。"
    "挑的是三个触发全命中那一档，于是 `safety_volume_factor` 是 `0.8 × 0.9` 的**未 round "
    "乘积** `0.7200000000000001`（P5-A6）——序列化文本里逐字出现，证明「不 round 系数」"
    "这个决定不会在落库时炸 |",
    "",
    "**结论：两条都通过。**`JsonText.process_bind_param` 用的正是 "
    "`json.dumps(value, ensure_ascii=False)`（不带 `default=`），"
    "所以「`json` 默认能不能认它」就是真判据，不是理论问题。",
    "",
    "#### 1.4 落地的构造为什么是「屏蔽 mutator 的 `dict` 子类」（三条亲跑取证）",
    "",
    "派单给的决策树是「`types` 红 → 改用 `collections.abc.Mapping` 标注 + 一个不可变的构造」"
    "「若 `MappingProxyType` 序列化失败 → 就在快照里存 `dict`，只读性靠约定」。"
    "**这两条备选我都实测了，都不成立**，最后落的是第三个构造：",
    "",
    "```",
    "② json.dumps({\"weekly_volume_base\": types.MappingProxyType({\"min\": 48.0, \"reps\": 120.0})})",
    "   → TypeError: Object of type mappingproxy is not JSON serializable",
    "   isinstance(proxy, dict) = False",
    "③ 屏蔽 mutator 的 dict 子类：",
    "   isinstance(m, dict) = True",
    "   json.dumps 成功: {\"weekly_volume_base\": {\"min\": 48.0, \"reps\": 120.0}}",
    "   m['min'] = 0 / del / update / pop / popitem / clear / setdefault → 全部 TypeError",
    "   m == {'min': 48.0, 'reps': 120.0} → True     （故整快照的 == 字面断言仍可用）",
    "   {**m} → 普通 dict                            （故 apply_safety 的 {**snap, …} 仍产出普通外层）",
    "```",
    "",
    "`collections.abc.Mapping` 的自定义子类**同样不在 `json` 的默认类型表里**"
    "（`json` 只认 `dict` 及其子类），故派单的第一条备选走到头还是落到第二条备选"
    "（存 `dict` + 只读性靠约定），而那会让派单同时要求的测试③"
    "（`pytest.raises(TypeError)`）**无法成立**。`dict` 子类是两条约束唯一的交集，"
    "故没有走 fallback。→ **顶回，见 §9 第 2 条。**",
    "",
    "⚠️ **两个实测撞出来的坑**（都已修、都有守卫，也都写进了 `assembler.py` 的 docstring）：",
    "",
    "* **`|=` 必须单独挡**：`dict.__ior__` 是 C 实现、**绕过**被覆盖的 `update`。"
    "  亲跑：只挡 7 个 mutator 时 `m |= {\"reps\": 120.0}` **未抛**、`m` 真的变成了 "
    "`{'min': 48.0, 'reps': 120.0}` ——那就是「看起来只读、其实一改就穿」。"
    "  故 `_ReadOnlyVolumeBase` 挡的是 **8** 个入口："
    "`__setitem__` / `__delitem__` / `pop` / `popitem` / `clear` / `update` / "
    "`setdefault` / `__ior__`。",
    "* **屏蔽 `__setitem__` 会顺手打断 `copy`**：亲跑，没有 `__reduce__` 时 `copy.copy(m)` 抛 "
    "`TypeError`，栈里是 `copy.py:301 y[key] = value`——`copy._reconstruct` 正是靠逐项赋值"
    "重建的。`TrainingPackage` 是 frozen dataclass，Task 6/8 完全可能对整包 `deepcopy`，"
    "那时一个会炸的只读映射就是埋好的地雷。故给它一个 `__reduce__`"
    "（`(_ReadOnlyVolumeBase, (dict(self),))`），`copy` / `deepcopy` / `pickle` "
    "三条路径一次修好（亲跑：三者都返回**同类型、同内容、不同身份**的新对象）。"
    "守卫是 `test_weekly_volume_base_survives_copy_and_pickle`。",
    "",
    "⚠️ **`m.__init__({...})` 重调仍能改内容**（亲跑未抛）：这是 `dict` 子类做不到"
    "「构造后彻底封死」的那一格。没挡它，因为挡了就没法构造；"
    "如实记录为能力边界（硬规矩 #39），守卫也不假装覆盖它。",
    "",
    "⚠️ **只读性只在进程内成立**：落进 JSON 列再读回来就是普通 `dict`、可变的了。"
    "这不是缺陷而是事实，`test_assembly_snapshot_is_json_serialisable` 里**显式断言**了"
    "「round-trip 之后类型是 `dict`」并证明改它不会回写进程内的快照。",
    "",
    "#### 1.5 为什么做成**私有**（`__all__` 43 → 43）",
    "",
    "`tests/test_refdata_prescription.py::test_prescription_public_namespace_is_pinned_verbatim` "
    "的**支 5** 要求「七个 `_OWNED_MODULES` 的**公有**顶层定义与 `_PRESCRIPTION_PUBLIC_BASELINE` "
    "互为充要」。做成公有就要同步改 `__all__`、那份基线与它的两句 `assert … == 43`（43 → 44），"
    "而派单 F1-1 没有要求扩公开面。故类名带前导下划线（`_ReadOnlyVolumeBase`），"
    "支 5 数不到它，**三处一个字都没动**。消费者看到的就是一个「改不动的 `dict`」。",
    "",
    "#### 1.6 实现口径与派单口径的一处差别（**顶回，见 §9 第 1 条**）",
    "",
    "派单写「值 = 该单位下所有 block 的 `base × sessions_per_week` 之和」。"
    "**字面照做会算错**：若「所有 block」指遍历每个 `(session, block)` 实例，"
    "`RED-END-ABN-01` 会得到 `{\"min\": 192.0, \"reps\": 480.0}`（把课数乘了两遍），"
    "而派单自己把 `168.0` 分解成 `48.0 min + 120.0 reps`，说明它要的是**去重后**的那一份。",
    "",
    "落地取的是**逐 `(session, block)` 累加 `base`**（改前的 `volume_base += base` 只是加了个"
    "分桶键），它与「去重后 `base × sessions_per_week` 之和」**逐格相等**——"
    "因为 `sum(base over 每一次出现) == base × 该 ref 的出现次数 == base × sessions_per_week`。"
    "探针对真仓 **18/18 套**做了两种口径的对拍，**全部相同**。"
    "选逐次累加是因为它对「同一 `exercise_ref` 在不同课里 `structure` 不同」这一档更稳健"
    "（那档下 `base × sessions_per_week` 得先挑一个 `base`，而挑哪一个没有答案；"
    "加载器不约束「同 ref 同 structure」）。今天真仓没有这一档。",
    "",
    "#### 1.7 新增/改动的守卫清单（`+6` 条）",
    "",
    "| 测试 | 新/改 | 钉什么 |",
    "|---|---|---|",
    "| `test_weekly_volume_base_is_split_by_volume_unit` | **新** | 派单要求的①："
    "三套模板（红/绿/黄，各代表一种键集形状）的逐个字面值 + **键序** |",
    "| `test_weekly_volume_base_keys_are_a_subset_of_volume_units` | **新** | 派单要求的②："
    "真仓 18 套，键集 ⊆ `VOLUME_UNITS`、**不含 `\"unspecified\"`**、值全是 `float`、"
    "非空，且键集分布 == `{(\"min\",): 10, (\"reps\",): 6, (\"min\", \"reps\"): 2}` |",
    "| `test_weekly_volume_base_is_read_only` | **新** | 派单要求的③："
    "`base[\"min\"] = 0` 抛 `TypeError`，外加 8 个 mutator 逐个抛、8 次尝试后一个字没变 |",
    "| `test_weekly_volume_base_survives_copy_and_pickle` | **新** | `copy` / `deepcopy` / "
    "`pickle` 三条路径都返回同类型同内容的**新**对象，且副本仍然只读 |",
    "| `test_assembly_snapshot_is_json_serialisable` | **新** | 派单要求的④（12 键，`allow_nan=False`） |",
    "| `test_the_safety_snapshot_is_json_serialisable` | **新** | 15 键（Task 6 真正落库的那一份） |",
    "| `test_assembly_snapshot_keys_are_exactly_the_pinned_set` | 未改 | 键数仍是 **12**、键序不变 ✓ |",
    "| `test_assembly_snapshot_values_are_the_independently_recomputed_literals` | 改 | "
    "那一格的字面值 `168.0` → `{\"min\": 48.0, \"reps\": 120.0}`；"
    "整条 `==` 顺带钉住「只读映射能与普通 `dict` 字面量相等」（`dict.__eq__` 不看子类型） |",
    "| `test_rest_min_is_not_counted_as_volume` | 改 | 末句 `== 168.0` → `== {\"min\": 48.0, "
    "\"reps\": 120.0}`，并**同时**对账变异前后两份（`rest_min` 2 → 20，两档都一个字不变） |",
    "",
    "### 2. F1-2（Critical）`rpe` 的值域改成 **0–10**",
    "",
    "#### 2.1 全仓扫 `6–20` / `6-20` / `Borg` 的命中清单与逐条处置",
    "",
    "两份探针：`t5_probes/_fr1_scan_rpe.py`（**全仓**，含 `.superpowers/`，改前跑一次、"
    "改后跑一次，输出落盘在 `t5_probes/_fr1_scan_rpe.out.txt`）与 "
    "`t5_probes/_fr1_scan_narrow.py`（**只扫 `backend/` + `Document/`**，"
    "并自动判定每条是不是显式否定句）。",
    "",
    "**为什么要两份**：全仓扫的改后结果被**取证件自己**污染了"
    "（`6–20` 从 8 命中涨到 39 命中，涨的 31 条全在 `.superpowers/` 的补丁脚本、"
    "commit 信息、账本追加节与本探针里，它们**必须**引用被撤回的写法才能说明改了什么）。"
    "故真正有意义的判据是**收敛扫描**：`backend/` + `Document/` 里每一处命中都必须是"
    "「这个标度是错的」的显式否定句。",
    "",
    "**A. `6–20`（en dash）—— `backend/` + `Document/`：改前 3 处 → 改后 7 处，7/7 全是否定语境**",
    "",
    "| # | 位置 | 改前/改后 | 处置 |",
    "|---|---|---|---|",
    "| 1 | `backend/app/domain/prescription/assembler.py`（`_render` 的 docstring） | 改前 1 处 | "
    "**改了**：原文是「`rpe` 是自觉受累程度（Borg 6–20；spec §8.2 的课堂快评写的是 0–10，"
    "两处口径不一致，已记进报告的待清扫清单）」——那是把 spec 讲成「自相矛盾」。"
    "改成「**0–10** 标度（**不是** Borg 经典的 6–20；出处逐字引在 `_RPE_MIN` 的注释里）」"
    "并补上「这是跨计划契约」那一段 |",
    "| 2 | `backend/app/domain/prescription/assembler.py`（`_RPE_MIN` 的注释） | 改后新增 | "
    "**刻意保留 1 处显式否定**：这一格是值域的**唯一住址**，"
    "「不是 Borg 经典的 6–20」这句是挡「下一个人好心改回去」的那道闸 |",
    "| 3 | `backend/app/domain/prescription/assembler.py`（`ValueError` 的消息） | 改后新增 | "
    "**刻意保留**：开发者真撞到这道拒绝时，看到的就是这条消息，"
    "它必须自己说清「不是那套标度」 |",
    "| 4 | `backend/tests/domain/test_prescription_assembler.py`"
    "（`test_rpe_intensity_renders_text_without_an_hr_zone` 的 docstring） | 改前 1 处 | "
    "**改了**：与 #1 同型的改写 |",
    "| 5 | `Document/2026-10-06-实施计划02-智能处方引擎.md`（P5-A5 的「更正」列） | 改前 1 处 | "
    "**改了**（补丁脚本的 **E7**）：值域改成 0–10、`value=13` → `value=7`，"
    "并把 spec 四处出处逐字引进去、点明「这是跨计划契约」。"
    "⚠️ 这一格是**错误的源头**（我上一轮就是照它写的），故必须改，"
    "否则 Plan 03 的实现者读到的还是那一套标度 |",
    "| 6 | `backend/app/domain/prescription/intensity.py` | **0 处** | "
    "**不用改**：亲扫这个文件里 `6–20` / `Borg` 各 **0** 命中；它唯一提到 RPE 的是"
    "「§7.4 的安全后置与 §8.2 的课堂 RPE 快评是兜住过量的那两道」，没有值域断言 |",
    "| 7 | `backend/app/domain/prescription/templates.py` | **0 处** | "
    "**不用改，而且它是本轮最有力的一条佐证**：`INTENSITY_TYPES` 的注释本来就逐字写着"
    "「`rpe` 的出处是 spec §8.2 的课堂快评 **RPE 0–10**」，`Intensity` 的字段表也写着"
    "「`rpe` | `value` | spec §8.2 的 RPE **0–10** 同一套语义」。"
    "故改前的 `assembler.py` **与它自己的上游矛盾** |",
    "",
    "**B. `6-20`（连字符）—— `backend/` + `Document/`：改前 0 处 → 改后 0 处**",
    "",
    "全仓那 **12**（改前）/ **32**（改后）条命中**全是假阳性**，逐类处置：",
    "",
    "| 类 | 例 | 处置 |",
    "|---|---|---|",
    "| 行号区间 | `test_domain_purity.py:196-201`、`:2397-2402`、`:97-100` | "
    "**不用改**：子串 `6-20` 恰好落在 `19**6-20**1` 里，与 RPE 无关 |",
    "| 日期区间 | `首日 2016-2026-1008` | **不用改**：`201**6-20**26` 的巧合子串 |",
    "| 本轮取证件 | `_t5_fr1_plan_patch.py` 的 `TOKENS = (\"6\\u201320\", \"6-20\", \"Borg\")` "
    "与它的两道闸门断言 | **不用改**：那是尺子本身 |",
    "",
    "**C. `Borg` —— `backend/` + `Document/`：改前 2 处 → 改后 5 处，5/5 全是显式否定句**",
    "",
    "与 A 的 #1 / #2 / #3 / #4 / #5 是同样 5 个位置（每一处都是「**不是** Borg 经典的…"
    "或「原先写成 Borg 经典的那一套标度，**错了**」）。"
    "⚠️ 计划正文那一处**只有 1 次**：补丁脚本 E7 的正文里其余提及一律改用"
    "「**那套标度**」指代，好让「计划正文里 `6–20` 恰好 1 处、`Borg` 恰好 1 处」"
    "这道闸门可用（脚本里的 `after_hits == {\"6–20\": 1, \"6-20\": 0, \"Borg\": 1}` 断言"
    "亲跑通过）。",
    "",
    "**D. 取证件（`.superpowers/`）里的命中一律不改**，逐条理由：",
    "`_t5_preflight_patch.py:39`（控制者的预检补丁，**已入库的历史件**，改它等于改历史）、"
    "`task-5-brief.md:168`（本轮派单的抄本，历史件）、"
    "`task-5-report.md:478`（**我上一轮报告里那条「待清扫清单」的原文**，历史件；"
    "本节取代它，但按审计链的纪律不回头改旧报告）、"
    "`_fr1_scan_rpe.py` / `_fr1_scan_narrow.py` / `_t5_fr1_plan_patch.py` / "
    "`_fr1_commit1.py` / `_fr1_msg1.txt` / `_fr1_ledger_append.py` / `progress.md` 的追加节"
    "（本轮取证与入账，**必须**引用被撤回的写法才说得清改了什么）。",
    "",
    "#### 2.2 `value=13` 改成了什么",
    "",
    "`13` → **`7.0`**（`Intensity(type=\"rpe\", value=7.0)`），"
    "断言的 `intensity_text` 随之从 `\"RPE 13\"` 改成 **`\"RPE 7\"`**。"
    "挑 `7` 而不是别的合法值有两个理由：① 它是 spec 自己的数"
    "（`YELLOW_CLASS_RPE_HIGH` = 「课堂 RPE 均值 **> 7** 分」，§13 的数据分布预期也写着"
    "「课堂 RPE 集中在 **5–7**」），故这一格同时是「渲染正确」与「值在 spec 的真实分布里」"
    "两件事的证据；② `7` 渲染成 `\"RPE 7\"`（`%g`），不与 `hrmax_pct` 那档的"
    "「60–70% HRmax」串味。",
    "另外 3 处跟着改：`assembler.py` 模块 docstring 的 Ruling 133 段"
    "（`Intensity(type=\"rpe\", value=13.0)` → `value=7.0`）、"
    "计划正文 P5-A5 的「更正」列（E7）、计划正文 Step 1 的测试清单（E8）。",
    "",
    "#### 2.3 加没加运行时校验 —— **加了**，理由四条",
    "",
    "落地：`_render` 的 `rpe` 那一支新增一道 `[0, 10]`（两端**闭**）的拒绝，"
    "私有常量 `_RPE_MIN = 0.0` / `_RPE_MAX = 10.0`，消息里带**实际收到的值**与 spec 的四处"
    "出处。守卫 `test_rpe_value_outside_zero_to_ten_is_rejected`，四个值 "
    "**`-0.1` / `0.0` / `10.0` / `10.1`**（两端合法、两侧越界；`0.0` 与 `10.0` 断言渲染成 "
    "`\"RPE 0\"` / `\"RPE 10\"`）。亲跑另加两格：`7.0` → `\"RPE 7\"`、`13.0` → `ValueError`。",
    "",
    "1. **它与 `hr_zone` 对称**：`intensity.hr_zone` 里**本来就有**一道 "
    "`0 <= low <= high <= 100` 的值域拒绝（`hrmax_pct` 那一档）。"
    "改前 `_render` 的 docstring 写的是「本函数**只渲染、不校验值域**：值域的校验属于加载器」"
    "——那句话**与本仓已有的做法自相矛盾**：`hrmax_pct` 的值域就在 domain 这一层被守着。"
    "故「单一所有者」在这里不是不加的理由，加了才是对称的。",
    "2. **加载器确实不校值域**：`app/refdata_prescription.py` 的 `_INTENSITY_FIELDS` "
    "只映射「哪一种 `type` 该有哪几个字段」（`\"rpe\": (\"value\",)`），"
    "校的是**字段形状**、不是取值。故没有本条的话，一份 "
    "`intensity: {type: rpe, value: 13}` 的 YAML **能加载成功**、渲染成学生端的「RPE 13」"
    "——在 0–10 标度上那是**一个看起来完全正常的谎**，正是本计划反复惩罚的失效形态。",
    "3. **可证明不会让任何真仓模板炸**（派单要求的证明）：`rpe` 在 18 套模板里出现 **0** 次"
    "（P5-A5 亲扫：`none` 82 / `hrmax_pct` 24 / `onerm_pct` 24，共 130）。"
    "本轮另跑了一遍全量 **679 passed**，18 套模板的装配测试一条没红。"
    "故这道拒绝今天在生产路径上**不可达**，只有那一条边界测试走它"
    "（覆盖率仍是 Miss 0 / BrPart 0，`+2` 个 branch 就是它）。",
    "4. **spec §14 那条待确认事项不构成反对理由**：它记的是「大屏阈值 RPE > **8** 与"
    "预警规则 RPE 连续 ≥ **9** 不一致」——那是两个**告警阈值**之间的矛盾，"
    "不是**标度**的矛盾。标度在 spec 里四处一致（0–10），故钉住 0–10 "
    "**不是**在替那条待确认事项做决定。",
    "",
    "⚠️ **`onerm_pct` 与 `none` 两档仍不校验值域**（刻意不对称，理由写进 docstring）："
    "前者的百分比合法性是加载器与 `EquivalenceTable` 的账，且 spec §7.2 只给了 `70` "
    "一个例子、**值域无出处**（编一个 `[0, 100]` 就是替专家做决定）；后者没有标量。",
    "",
    "### 3. F1-3（Important）撤回 P5-A10",
    "",
    "#### 3.1 补丁脚本的逐条命中清单",
    "",
    "脚本 `.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/_t5_fr1_plan_patch.py`"
    "（**已入库**）。纪律照硬规矩 #79：**每一处替换都先 `assert` 命中次数**，"
    "两遍走（第一遍只 assert、第二遍才替换），任何一处不符就**整体不落盘**；"
    "另有四道落盘闸门。**没用编辑器工具碰 `Document/` 下的任何 md。**",
    "",
    "```",
    "改前：bytes=151467  CRLF=937  裸LF=0  lines(split)=938  splitlines=937",
    "改前的 F1-2 扫描闸门：{'6–20': 1, '6-20': 0, 'Borg': 0}",
    "E1    命中 1 次 ✓  （old  77 字 → new  353 字）   F1-3：P5-A10「更正」列整格重写为「撤回」",
    "E2    命中 1 次 ✓  （old 204 字 → new  355 字）   F1-3：5.3 正文恢复可核的原文引用",
    "E3    命中 1 次 ✓  （old  61 字 → new  255 字）   F1-5①：P5-A2 补明「按 block 计数加权」",
    "E4    命中 1 次 ✓  （old  51 字 → new  542 字）   F1-5②：5.5 补 _OWNED_MODULES 3→7 + 第二句 assert",
    "E5    命中 1 次 ✓  （old 100 字 → new  256 字）   F1-5③：5.3 的 Consumes 补 Template / ExerciseSpec",
    "E6    命中 1 次 ✓  （old  65 字 → new  478 字）   F1-5④：5.5 补 --cov 与不带的 passed 差 1",
    "E7    命中 1 次 ✓  （old 164 字 → new  933 字）   F1-2：P5-A5 的值域 0–10 + value=7",
    "E8    命中 1 次 ✓  （old 112 字 → new  360 字）   F1-2：Step 1 的 value=7 + 新增边界测试名",
    "E9    命中 1 次 ✓  （old  80 字 → new 1325 字）   F1-1：六步口径第 6 步改成分列的只读 Mapping",
    "E10a  命中 1 次 ✓  （old  95 字 → new  622 字）   5.3 的 apply_safety 签名扩参",
    "E10b  命中 1 次 ✓  （old  95 字 → new  393 字）   5.4 的 apply_overrides 签名扩参",
    "追加型（闸门 ① 跳过、由闸门 ④ 接管）= ['E4', 'E5', 'E6']",
    "改后的 F1-2 扫描闸门：{'6–20': 1, '6-20': 0, 'Borg': 1}",
    "改后：bytes=159408  CRLF=938  裸LF=0  lines(split)=939  splitlines=938",
    "字节增量 = 7941 B   行数增量 = 1     BOM = False",
    "```",
    "",
    "**四道落盘闸门**（全部亲跑通过）：① 替换型的旧串一律 **0** 命中"
    "（**追加型** `old in new` 的三条 E4/E5/E6 在这一道上天然不可能 0 命中——那正是「追加」的"
    "定义，故跳过并**逐条打印**是哪三条，由闸门 ④ 接管，免得「跳过」变成静默）；"
    "② `6–20` / `6-20` / `Borg` 改后各只剩 E7 那一次显式否定；"
    "③ 5.3 正文里那句自我指控 `**行号口径错、引文控制者未核**` **0** 命中；"
    "④ 14 个新串各命中预期次数（`控制者错误 #140` 刻意 **2** 次：E1 的撤回格 + E2 的正文）。",
    "",
    "#### 3.2 计划正文的新字节数/行数",
    "",
    "| 口径 | 改前 | 改后 |",
    "|---|---|---|",
    "| 字节 | **151 467 B** | **159 408 B**（+7 941 B） |",
    "| 行（`len(text.split(\"\\r\\n\"))`，与派单的「938 行」同口径） | **938** | **939**（E8 多加了一个列表项） |",
    "| 行（`splitlines()`） | 937 | 938 |",
    "| 换行 | 纯 CRLF（937 个，裸 LF 0） | **纯 CRLF**（938 个，裸 LF **0**） |",
    "| BOM | 无 | **无** |",
    "| `git diff --stat` | — | **12 insertions / 11 deletions**（11 行整行替换 + 1 行新增，"
    "无 CRLF 抖动） |",
    "",
    "⚠️ **派单只要求改「更正」列，我照做了**：P5-A10 那一行的**事实列**一个字没动，"
    "于是同一行里「事实」列仍写着「**行号口径错**，且『明写严格大于』的引文控制者未核」、"
    "「更正」列以「**撤回**」开头整格反驳它。**两格直接对打。**→ **顶回，见 §9 第 6 条。**",
    "",
    "E2 恢复后的 5.3 正文（可核的原文引用，硬规矩 #78 的「按可 grep 的原文找」半句保留）："
    "三处可 grep 的原文各点名——① 一行 dict 定义 "
    "`BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}`；② 唯一消费点 `body_fat_pct > limit`；"
    "③ **定义行上一行**那句逐字注释「体成分异常 C 的体脂率阈值（spec §6.3②）：男 > 20%、"
    "女 > 28%，**严格大于**。」。本轮已用 Grep 亲核这三处都在 "
    "`backend/app/domain/derive.py` 里逐字存在（定义行的**上一行**就是那句注释）。",
    "",
    "### 4. F1-4（Important）硬规矩 #82 / #83 入账",
    "",
    "#### 4.1 `progress.md` 追加前后的字节数/行数",
    "",
    "脚本 `t5_probes/_fr1_ledger_append.py`，用 `LEDGER.open(\"a\", encoding=\"utf-8\", "
    "newline=\"\")` 追加、内容自己写 `\\r\\n`。**没用编辑器工具打开过这个文件。**",
    "",
    "| 口径 | 追加前 | 追加后 |",
    "|---|---|---|",
    "| 字节 | **336 427 B** | **346 910 B**（+10 483 B） |",
    "| 行（`splitlines()`） | **2 153** | **2 214**（+61） |",
    "| 行（`len(text.split(\"\\r\\n\"))`） | 2 154 | 2 215（+61） |",
    "| 换行 | 纯 CRLF（2 153 个，裸 LF 0） | **纯 CRLF**（2 214 个，裸 LF **0**） |",
    "| BOM | 无 | **无** |",
    "",
    "**最强的一道闸门**（写盘后）：`after_text == before_text + payload` **逐字相同**——"
    "即前 336 KB 一个字都没被碰过。这一条是冲着 Ruling 116 那次事故写的"
    "（IDE 把陈旧且截断的缓存写回磁盘、永久丢了约 107 KB）。"
    "另有 10 个必需串的**写盘前**闸门（追加是不可撤销的，故闸门必须在写之前跑）：",
    "`**→ 补硬规矩 #82：探针「0 命中」时` / `**→ 补硬规矩 #83：变异取证与任何「改了又还原」的取证` / "
    "`#### 一、控制者错误 #140` / `恰好等长（都是 47 字符）` / `四步又在**同一秒**内完成` / "
    "`#### 三、控制者采纳实现者的两处签名扩参` / `第 **5**、**6** 次顶回成立` / "
    "两个扩参后的签名字面 / `**905 stmts / Miss 0 / 262 branch / BrPart 0 / 100%**`，"
    "**各命中 1 次 ✓**。",
    "",
    "#### 4.2 硬规矩 #83 的正文（逐字，即入账那一份）",
    "",
    "> **→ 补硬规矩 #83：变异取证与任何「改了又还原」的取证，必须在跑测试前 "
    "`shutil.rmtree(__pycache__, ignore_errors=True)` 并设 `PYTHONDONTWRITEBYTECODE=1`；"
    "**等长改动 + 同一秒**会让 CPython 的 `(mtime 截断到秒, size)` 失效判据不触发，"
    "于是加载陈旧字节码、产出假红或假绿。**",
    "",
    "**依据（5.5 变异 ④ 的实测经过，本轮又独立复核了那两个具体条件）**：那条变异打的是 "
    "`intensity.py` 里 `hr_zone` 的取整方向。四步是「量基线 → 打变异 → 跑红 → 还原再跑绿」，"
    "而**还原后重跑出现了假红**：文件 sha256 **已还原成功**（逐字节相同），"
    "pytest 却仍报变异行为。本轮用探针 `t5_probes/_fr1_probe_47chars.py` **自己又数了一遍**"
    "那两个条件（硬规矩 #82 的自证义务也用在自己的入账上，不照抄派单）：",
    "",
    "```",
    "命中 1 处：",
    "  行 170: len=47  '    return int(low_bpm), int(-(-high_bpm // 1))'",
    "  变异后: len=47  '    return int(-(-low_bpm // 1)), int(high_bpm)'",
    "  等长? True   差 = 0",
    "```",
    "",
    "→ **「恰好等长（都是 47 字符）」坐实**；四步在同一秒内完成（脚本是一次进程内跑完的）。"
    "两个条件合起来让 `(mtime 截断到秒, size)` 二元组一字未变 → `.pyc` 被判定仍有效 → "
    "加载的是**变异版字节码**。",
    "",
    "**它为什么比一般的 flaky 更危险**（三条，都写进了账本）：",
    "",
    "* **假红**会让人**怀疑一个正确的还原**：于是「再还原一次」「再跑一次」，"
    "  而真因（陈旧字节码）从来不在被怀疑的清单里；更坏的是有人为了让它变绿而**再改一次代码**，"
    "  于是工作树与 index 悄悄分叉。",
    "* **假绿更坏**：它让人以为**一条守卫还在工作**。变异取证的全部价值就是「M1 必须红」，"
    "  一次假绿等于把「这条守卫有牙」这个结论建立在一个**没被真正执行过的文件**上——"
    "  那正是硬规矩 #50/#53 要挡的「尺子恒绿」。",
    "* 触发条件是**两个都很常见的巧合**（等长改动、同一秒完成），不是罕见的时序竞争，"
    "  故**会复发**：任何「语义等价改写」型的变异（正是硬规矩 #65 的 M1 对照要求的形状）"
    "  **天然等长**。",
    "",
    "**本轮的三次取证一律带了这两项**：`import types` 的纯净性探针"
    "（脚本里 `clean_pyc()` + 子进程 `env[\"PYTHONDONTWRITEBYTECODE\"] = \"1\"`，"
    "且还原后打印 `[还原] sha256 相同 = True（31817 B）`）、"
    "以及两次全量跑（终端里 `$env:PYTHONDONTWRITEBYTECODE=\"1\"` + `-p no:cacheprovider`）。",
    "",
    "#### 4.3 硬规矩 #82 的正文（逐字）",
    "",
    "> **→ 补硬规矩 #82：探针「0 命中」时，必须先用一个已知存在的串验证这条查询本身有效，"
    "才允许把「没查到」讲成「不存在」。**",
    "",
    "**依据**：账本 Ruling 147 的 **P5-A13**（用一个自己没验证过的正则去数一个已经有字面断言的"
    "量，数出 3 而真值是 24）与本次的 **P5-A10** 是**同一根因的两次发作**，"
    "而硬规矩 #80 只覆盖了「已有字面断言」那一半——**「探针 0 命中」这一半它管不到**："
    "0 命中看起来像「事实」，而它同样可能是「查询本身无效」。"
    "自证的办法只有一步：拿一个**已知存在**的串跑同一条查询，看它是否命中。"
    "→ **控制者错误 #140**，与 #80 同型第 **9** 次。",
    "",
    "**本轮自己就用了一次**：§4.2 那个 47 字符的复核，就是拿「已知存在的那一行」"
    "去验证「len() 这把尺子」有效，然后才把它写进账本。",
    "",
    "#### 4.4 同一节还记了什么",
    "",
    "账本追加节的完整目录：一、控制者错误 #140（+ 硬规矩 #82）；"
    "二、硬规矩 #83（`.pyc` 陈旧失效）；"
    "三、**控制者采纳实现者的两处签名扩参（Plan 02 实现者第 5、6 次顶回成立）**——"
    "`apply_safety(pkg, inp, eq, *, template, exercises)` 与 "
    "`apply_overrides(pkg, records, *, exercises)`，两条的理由逐字入账"
    "（`TrainingPackage` 里没有 `addons` / `weekly_frequency`；"
    "`SUBSTITUTE_EXERCISE` 只换 ref 会留着旧动作的视频 URL，那是「一个看起来正常的谎」）；"
    "四、本轮另两条 Critical 裁定（F1-1 / F1-2）；五、本轮的验收数字。",
    "⚠️ **本节由实现者按 fix round 1 派单代笔入账，Ruling 编号留给控制者结案时统一分配**"
    "（账本上一个号是 Ruling 147），故标题里没有自铸新号。",
    "",
    "### 5. F1-5（Minor）4 条待清扫的落地位置",
    "",
    "| # | 条目 | 落地位置（补丁脚本的哪一条） | 写进去的内容 |",
    "|---|---|---|---|",
    "| ① | P5-A2 的分布口径未说明 | **E3** → 计划正文 Task 5 节「⚠️ 预检更正」总表的 "
    "P5-A2 那一格（事实列） | 在 `{2: 24, 3: 42, 4: 64}` 后面补明："
    "**这个分布是按 block 计数加权的、不是按模板计数**——按 `exercise_ref` 去重是 "
    "`{2: 12, 3: 14, 4: 16}` 共 **42** 个 ref，各乘以自己的 `sessions_per_week` 才得到 "
    "`{2: 24, 3: 42, 4: 64}` 共 **130** 个 block。（这三个数与 "
    "`test_every_block_appears_in_every_session_of_the_real_templates` 的 docstring "
    "里已有的口径逐字一致） |",
    "| ② | 简报 5.5 漏点 `_OWNED_MODULES` 与第二句 assert | **E4** → 5.5 节 Step 5 的"
    "第一个 `- [ ]`（公开面那一条） | 补明两处：**① `_OWNED_MODULES` 从 3 个模块扩到 7 个**"
    "（支 5 的穷尽判据只对**本包拥有**的模块成立，Task 5 新建的四个都是本包拥有的，"
    "不加进去就等于**放弃这四个模块的穷尽守卫**——谁往 `assembler.py` 加一个公有顶层定义"
    "而不重导出，全量测试照样绿）；**② 那句 `assert len(...) == 24` 其实是两句**"
    "（`assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 43` 与 `assert len(set(names)) == 43`，"
    "后者钉「基线里没有重名」），**两句都要改**。并逐字标注"
    "「**实现者超出派单发现，控制者采纳**」 |",
    "| ③ | 5.3 的 `Consumes` 漏列 `Template` / `ExerciseSpec` | **E5** → 5.3 节的 "
    "`**Consumes:**` 那一行 | 补上 Task 2 的 **`ExerciseSpec`** 与 Task 3 的 **`Template`**，"
    "并注明「`apply_safety` 的签名已扩参成 `(pkg, inp, eq, *, template, exercises)`，"
    "`Consumes` 要跟上」。⚠️ **同一节 `Produces` 的签名行也一并改了**（E10a / E10b），"
    "因为它**当时还是旧签名**、只补 `Consumes` 会让同一节自相矛盾 → 见 §9 第 4 条 |",
    "| ④ | 带 `--cov` 与不带的 passed 数差 1 | **E6** → 5.5 节 Step 5 的"
    "「全量 `pytest -q` 的 passed 数自己数」那一条 | 补明口径：不带 `--cov` 是 `N passed`，"
    "带 `--cov=app.domain --cov-branch` 是 `N-1 passed, 1 skipped`；那 **1 个 skip** 是 "
    "`tests/pipeline/test_backfill.py` 里**既有**的墙钟断言，它按硬规矩 #42 在 "
    "`sys.gettrace()` 非空时**主动跳**，而 `pytest-cov` 正是靠 `sys.settrace()` 实现的；"
    "Task 5 落地时实测 **679** / **678 + 1 skipped**，两个数指同一套测试，"
    "**没有丢测试**（正是为了「免得下一个 Task 的实现者以为丢了一条测试」） |",
    "",
    "### 6. 最终验收（全部实现者亲跑）",
    "",
    "| 项 | 基线（`fc8f5a8`） | 本轮 | 判据 |",
    "|---|---|---|---|",
    "| `python -m pytest -q` | 672 passed | **679 passed**（+7） | 亲跑 `61.27s` |",
    "| `… --cov=app.domain --cov-branch` | 671 passed, 1 skipped | "
    "**678 passed, 1 skipped** | 亲跑 `138.98s`；差的那 1 个 skip 见 §5 的 ④ |",
    "| 覆盖率四格 | 888 stmts / Miss 0 / 260 branch / BrPart 0 / 100% | "
    "**905 / 0 / 262 / 0 / 100%** | `+17` stmts（只读映射 12 + 两个 `_RPE_*` 常量 + "
    "值域拒绝 2 + 分桶累加 1）、`+2` branch（`rpe` 值域那个 `if` 的两条弧）。"
    "**spec §12 的硬要求仍满足** |",
    "| 公开面 `__all__` | 43 | **43** | `_ReadOnlyVolumeBase` 是私有的（§1.5）；"
    "`_PRESCRIPTION_PUBLIC_BASELINE` 与它的两句 `assert … == 43` 一个字没动 |",
    "| 扫描面 | 32 | **32** | domain **14** + pipeline **7** + db **11** |",
    "| 禁区指纹 | `D2C8E539E2FA0029` / `3DE598AF38631209` / `822CB86A5E998301` | "
    "**三个逐字不变** | 探针 `t5_probes/_fr1_verify.py` 逐个重算 sha256[:16] |",
    "| `backend/pe.db` | 不存在 | **不存在** | 同上 |",
    "| `backend/data/seed/` | 0 文件 | **0 文件** | 同上 |",
    "| `backend/data/` | — | **一个字节没动** | `git status --short` 里 `backend/data/` "
    "零条目；模板 YAML 仍是 18 个 / 123 848 B |",
    "| 控制者实算的算例 | 逐格命中 | **仍逐格命中** | `interval_run` 第 1 周 **38.4** / "
    "第 4 周 **32.6**；`compound_circuit` **96.0** / **81.6**；"
    "`hr_zone(194.0, 60, 70) == (116, 136)`；`volume_factor` **0.8** / band **`'low'`** |",
    "",
    "**四个新模块的 sha256[:16] 与体积**（`intensity.py` / `safety.py` / `override.py` "
    "本轮**一个字没改**，故它们的 sha256 与 5.5 收尾时相同）：",
    "",
    "| 模块 | 字节 | 行 | 换行 | sha256[:16] | import 面 | 违规 |",
    "|---|---|---|---|---|---|---|",
    "| `intensity.py` | 13 092 | 193 | 纯 LF | `9D8336D25A2DF196` | `[]`（一个都没有） | 无 |",
    "| `assembler.py` | **43 779**（改前 31 817） | **689** | 纯 LF | "
    "**`D443187E541379CE`** | `collections` / `collections.abc` / `dataclasses` / "
    "`app.domain.indicators` / `.exercises` / `.intensity` / `.templates` | "
    "**无 `import math`、无 `import types`、无 `import json`** |",
    "| `safety.py` | 24 266 | 407 | 纯 LF | `BC471A4B5161D10C` | `collections.abc` / "
    "`dataclasses` / `.assembler` / `.exercises` / `.templates` | 无 |",
    "| `override.py` | 24 483 | 419 | 纯 LF | `1E2E088C886B4990` | `collections.abc` / "
    "`dataclasses` / `enum` / `.assembler` / `.exercises` | 无 |",
    "",
    "⚠️ **`assembler.py` 里没有 `import types`、也没有 `import json`**：只读映射靠 `dict` "
    "子类实现，JSON 化的**证据在测试侧**（`tests/` 不受 domain 的 allow-list 约束）。"
    "两份架构守卫（`test_domain_purity.py` 4 条 + `test_layering.py`）本轮全绿。",
    "",
    "### 7. 两个 commit 的 sha",
    "",
    f"1. **`{SHA1}`** —— `{SUBJ1}`（3 个文件：`assembler.py` + 两个测试文件；"
    "+481 / −29）",
    f"2. **`{SHA2}`** —— `{SUBJ2}`（计划正文 + 账本 + 补丁脚本 + 本轮 14 个取证脚本）",
    "",
    "`git add` 一律**按文件名逐个加**；两条 commit 信息都是 python 写 UTF-8 无 BOM 临时文件 "
    "+ `git commit -F`（`t5_probes/_fr1_msg1.txt` / `_fr1_msg2.txt`，两份都入库）。",
    "",
    "### 8. 我没按本派单做的地方（**7 处**，逐条）",
    "",
    "1. **没有走派单 F1-1 的 fallback**（「若 `MappingProxyType` 序列化失败，就在快照里存 "
    "`dict`，只读性靠 frozen dataclass + 文档约定」）。实测两条备选都不成立"
    "（`collections.abc.Mapping` 的自定义子类同样不可 JSON 序列化），"
    "落的是第三个构造：屏蔽 8 个 mutator 的 `dict` 子类，**同时满足只读与 JSON 化**，"
    "故派单要求的测试③（`pytest.raises(TypeError)`）**成立了**、没被降级成「等价的不可变性"
    "守卫」。取证见 §1.4。",
    "2. **`weekly_volume_base` 的实现口径与派单的字面表述不同**：派单写「所有 block 的 "
    "`base × sessions_per_week` 之和」，字面照做会把课数乘两遍"
    "（`RED-END-ABN-01` 得 `{\"min\": 192.0, \"reps\": 480.0}`）。"
    "我按派单**自己给出的分解**（`48.0 min + 120.0 reps`）实现，"
    "落的是「逐 `(session, block)` 累加 `base`」，与去重后的 "
    "`base × sessions_per_week` 之和在真仓 **18/18** 逐格相等（探针对拍）。见 §1.6。",
    "3. **加了 `[0, 10]` 的运行时校验**（派单说「加或不加都可以」，我选了加，"
    "并配了派单要求的四值边界测试）。理由四条见 §2.3。",
    "4. **计划正文多改了 3 处**（E9 / E10a / E10b），都不在派单 F1-5 的字面 4 条里："
    "E9 是六步口径第 6 步的 `weekly_volume_base` 类型（原文写「`float`，`round(…, 1)`」，"
    "F1-1 落地后与代码矛盾，而 Task 6/8 的实现者读的就是它）；"
    "E10a / E10b 是 5.3 / 5.4 的 `Produces` 签名行（**当时还是旧签名**，"
    "只补 F1-5③ 的 `Consumes` 会让同一节自相矛盾）。见 §9 第 4、5 条。",
    "5. **只读映射做成了私有**（`_ReadOnlyVolumeBase`），故 `__all__` 是 **43 → 43**"
    "而不是 44。派单的验收清单问「`__all__` 的大小（43 → ?）」，答案是 **43**；"
    "理由（支 5 的穷尽判据 + 派单没要求扩公开面）见 §1.5。",
    "6. **入库范围比派单的字面清单大**：派单只点名「补丁脚本入库」"
    "（`_t5_fr1_plan_patch.py`），我把本轮 **14 个取证脚本 + 2 份 commit 信息 + "
    "1 份扫描输出**也一并入库了（`t5_probes/_fr1_*`）。理由是账本对 `t5_probe{1,2,3,4}.py` "
    "记的就是「四份全部入库」，`fr2_probes/` / `fr3_probes/` / `fr4_probes/` / `t3_probes/` / "
    "`t4_probes/` 也全部已入库。",
    "7. **`task-5-report.md`（本文件）与 `task-5-brief.md` / `_mk_brief5.py` / "
    "`_t5_verify.py` 至今未入库**，本轮也没提交（不在派单 commit 2 的字面清单里，"
    "且上一轮同样没提交）。⚠️ 但 `task-1..4-report.md` 与 `task-1..4-brief.md` **全部已入库**，"
    "`.superpowers/**` 又是 `-text`（git 不做行尾转换）。按 Ruling 116 的立意"
    "（审计链入库以防数据丢失），**这 4 个文件是当前唯一的裸露面**"
    "（本文件此刻 ≈ 100 KB，只在磁盘上）。在此报出请控制者裁定。",
    "",
    "### 9. 我认为本派单错了的地方（**顶回 6 处**，这是 Plan 02 实现者第 7–12 次顶回）",
    "",
    "**① F1-1 的口径表述有歧义，字面照做会算错。**"
    "「值 = 该单位下所有 block 的 `base × sessions_per_week` 之和」——"
    "若「所有 block」指遍历每个 `(session, block)` 实例，`RED-END-ABN-01` 会得到 "
    "`{\"min\": 192.0, \"reps\": 480.0}`（课数乘了两遍），"
    "而派单**自己**把 `168.0` 分解成 `48.0 min + 120.0 reps`。"
    "两处对打，我按后者（分解）实现。**这不是派单的结论错，是表述漏了「去重」两个字。**"
    "建议正文写成「值 = 该单位下**每个不同 `exercise_ref`** 的 "
    "`base × sessions_per_week` 之和」。",
    "",
    "**② F1-1 的决策树漏了一格，照它走会自相矛盾。**"
    "派单说「`types` 红 → 改用 `collections.abc.Mapping` 标注 + 返回一个不可变的构造」，"
    "又说「若 `MappingProxyType` 序列化失败 → 就在快照里存 `dict`（只读性靠 frozen dataclass "
    "+ 文档约定）」。而 **`collections.abc.Mapping` 的自定义子类同样不可 JSON 序列化**"
    "（`json` 的默认类型表只认 `dict` 及其子类），"
    "故第一条备选走到头**还是**落到第二条，于是派单**同时**要求的测试③"
    "（`with pytest.raises(TypeError): snap[\"weekly_volume_base\"][\"min\"] = 0`）"
    "**无法成立**——派单要求了一个它自己的决策树排除掉的结果。"
    "第三个构造（屏蔽 mutator 的 `dict` 子类）同时满足两条，故没走 fallback。",
    "",
    "**③ F1-2 那条「不要顺手加校验」的禁令，前提不完整。**"
    "派单给的唯一门槛是「能不能证明它不会让真仓模板炸」（能，`rpe` 出现 0 次）。"
    "但它没提到 **`hr_zone` 已经在同一层校验 `hrmax_pct` 的值域**"
    "（`0 <= low <= high <= 100`），而改前 `_render` 的 docstring 恰恰用"
    "「值域的校验属于加载器」当不加的理由——**那句话与本仓已有的做法自相矛盾**。"
    "故「单一所有者」在这里不构成反对理由；不加才是不对称的那个选择。我加了。",
    "",
    "**④ F1-5③ 的前提「签名已经扩参了」在计划正文里不成立。**"
    "计划 5.3 / 5.4 的 `Produces` 两行**当时仍是旧签名**"
    "（`apply_safety(pkg, inp, eq)` / `apply_overrides(pkg, records)`）——"
    "扩参只发生在**代码**里。只补 `Consumes` 会让同一节的 `Consumes` 说有 "
    "`Template` / `ExerciseSpec`、而 `Produces` 的签名里没有它们。故连 `Produces` 两行"
    "一起改了（E10a / E10b），并把「控制者第 5 / 6 次采纳」的理由写进那两行。",
    "",
    "**⑤ F1-1 是 Critical 级裁定，但派单没要求同步计划正文——那会留下一处活的矛盾。**"
    "计划 5.2 六步口径的第 6 步逐字写着 `weekly_volume_base` = "
    "「未乘个体系数、未乘 `week_deltas` 的周量总和（**`float`**，`round(…, 1)`）」。"
    "F1-1 落地后这一行与代码矛盾，而 **Task 6 的实现者要照它建 `prescription` 表、"
    "Task 8 的实现者要照它建读模型**。派单 F1-3/F1-5 已经让我改计划正文了，"
    "把这一处落下是漏项，故补成 E9。**建议：凡 Critical 级的口径裁定，"
    "派单应当同时点名计划正文的哪一行要跟着改**（本轮 F1-1 没有）。",
    "",
    "**⑥ F1-3 只要求重写「更正」列，于是 P5-A10 那一行自己跟自己打。**"
    "改后同一行里：「事实」列仍写着「计划 5.3 写的是「`derive.py:68-69`」，"
    "**行号口径错**，且「明写严格大于」的引文控制者未核」、"
    "「更正」列以「**撤回**…原计划的行号 `:68-69` 与引文双双正确」开头。"
    "对照账本 Ruling 147 里 **P5-A13** 的写法（那条同样是控制者错误，"
    "它的**事实列**直接以「**控制者错误 #139**：…」开头、把错的结论放在事实列里讲清楚），"
    "**本仓的既有惯例是连事实列一起改**。我按派单字面只改了「更正」列，"
    "请控制者裁定要不要照 P5-A13 的体例把事实列也改掉。",
    "",
    "**另有一处口径提醒（不算顶回）**：派单说计划正文是「151 467 B / **938 行**」。"
    "实测 `splitlines()` = **937**、`len(text.split(\"\\r\\n\"))` = **938**，"
    "故派单用的是后一种口径（把结尾换行后的空位也算一行）。"
    "本轮报告一律**两个口径都给**，免得下一个人数出 937 以为丢了行。",
    "",
    "### 10. 本轮的取证脚本清单（全部入库）",
    "",
    "| 脚本 | 干什么 |",
    "|---|---|",
    "| `_t5_fr1_plan_patch.py` | **计划正文的 11 处替换**（E1–E10b），四道落盘闸门 |",
    "| `t5_probes/_fr1_env_probe.py` | 14 个关键文件的字节数 / 行数 / 换行 / BOM 对账 |",
    "| `t5_probes/_fr1_probe_types_json.py` | **三条实测**：`import types` 让守卫变红（含还原后 "
    "sha256 对账）/ `MappingProxyType` 不可 JSON 化 / `dict` 子类两条都过 |",
    "| `t5_probes/_fr1_probe_ior.py` | 撞出 `|=` 与 `copy.copy` 两个口子 |",
    "| `t5_probes/_fr1_probe_reduce.py` | `__reduce__` 一次修好 copy / deepcopy / pickle |",
    "| `t5_probes/_fr1_recompute_volume_base.py` | **不 import 被测模块**，直接读 18 份 YAML "
    "独立重算 `weekly_volume_base`，并对拍两种口径（18/18 相同） |",
    "| `t5_probes/_fr1_probe_47chars.py` | 硬规矩 #82 的自证：自己数一遍「47 字符等长」 |",
    "| `t5_probes/_fr1_scan_rpe.py` / `_fr1_scan_narrow.py` | F1-2 的全仓扫（含取证件）"
    "与收敛扫（只 `backend/` + `Document/`，自动判定是否否定句） |",
    "| `t5_probes/_fr1_plan_lines.py` / `_fr1_plan_range.py` / `_fr1_ledger_tail.py` | "
    "**只读**地看计划正文与账本（不打开编辑器） |",
    "| `t5_probes/_fr1_verify.py` | 实现者自验：公开面 / 扫描面 / 三个指纹 / 禁区 / "
    "四个模块的 sha256 与 import 面 / F1-1 的新类型与字面值 / 12 与 15 键的 JSON 化 / "
    "F1-2 的六个值 / 两处签名 / 控制者的算例 |",
    "| `t5_probes/_fr1_ledger_append.py` | **账本追加**（`open(..., \"a\", newline=\"\")` + "
    "写盘前闸门 + `after == before + payload` 逐字对账） |",
    "| `t5_probes/_fr1_commit1.py` / `_fr1_commit2.py` / `_fr1_report_append.py` | "
    "两个 commit 与本节追加 |",
    "",
    "**下一步**：控制者复核本轮 → Task 5 结案 → 抽 Task 6 简报。",
    "",
]


def main() -> int:
    before_text = REPORT.read_bytes().decode("utf-8")
    before = stats(REPORT)
    print(f"追加前：bytes={before['bytes']}  splitlines={before['splitlines']}  "
          f"split(\\n)={before['split_lf']}  CRLF={before['crlf']}  BOM={before['bom']}")
    assert before["bom"] is False
    assert before["crlf"] == 0, "本报告是纯 LF，实测出现 CRLF"
    assert before_text.endswith("\n"), "报告不以换行结尾"

    payload = "\n".join(LINES)
    assert "\r" not in payload, "追加内容里混进了 CR"

    # ⚠️ 闸门**全部在写盘之前**跑（追加不可撤销）。语义是「必需内容至少出现 min 次」：
    #    真闸门是下面那句 `after_text == before_text + payload`，这一组只挡「漏写了一节」。
    for token, minimum in {
        "## Task 5 fix round 1": 1,
        "### 1. F1-1（Critical）": 1,
        "### 2. F1-2（Critical）": 1,
        "### 3. F1-3（Important）撤回 P5-A10": 1,
        "### 4. F1-4（Important）硬规矩 #82 / #83 入账": 1,
        "### 5. F1-5（Minor）4 条待清扫的落地位置": 1,
        "### 6. 最终验收": 1,
        "### 7. 两个 commit 的 sha": 1,
        "### 8. 我没按本派单做的地方": 1,
        "### 9. 我认为本派单错了的地方": 1,
        "{\"min\": 48.0, \"reps\": 120.0}": 3,
        "_ReadOnlyVolumeBase": 3,
        "assembler.py:148: types": 1,
        "Object of type mappingproxy is not JSON serializable": 1,
        "test_assembly_snapshot_is_json_serialisable": 1,
        "test_the_safety_snapshot_is_json_serialisable": 1,
        "test_rpe_value_outside_zero_to_ten_is_rejected": 1,
        "test_weekly_volume_base_is_split_by_volume_unit": 1,
        "test_weekly_volume_base_keys_are_a_subset_of_volume_units": 1,
        "test_weekly_volume_base_is_read_only": 1,
        "test_weekly_volume_base_survives_copy_and_pickle": 1,
        "905 / 0 / 262 / 0 / 100%": 1,
        "679 passed": 2,
        "43 → 43": 1,
        "159 408 B": 1,
        "346 910 B": 1,
        "D443187E541379CE": 1,
        "9D8336D25A2DF196": 1,
        "BC471A4B5161D10C": 1,
        "1E2E088C886B4990": 1,
        "D2C8E539E2FA0029": 1,
        "3DE598AF38631209": 1,
        "822CB86A5E998301": 1,
        "硬规矩 #82": 2,
        "硬规矩 #83": 2,
        "控制者错误 #140": 1,
        "47 字符": 1,
        "apply_safety(pkg, inp, eq, *, template, exercises)": 1,
        "apply_overrides(pkg, records, *, exercises)": 1,
        "value=7": 2,
        "RPE 13": 1,
        "RPE 7": 2,
        "0–10": 5,
        "PYTHONDONTWRITEBYTECODE": 1,
        "shutil.rmtree": 1,
        "(mtime 截断到秒, size)": 1,
    }.items():
        got = payload.count(token)
        assert got >= minimum, (
            f"追加内容里 {token[:44]!r} 命中 {got} 次、至少需要 {minimum} 次")
    print(f"写盘前闸门：{len(LINES)} 行追加内容、必需串逐条达标 ✓")

    with REPORT.open("a", encoding="utf-8", newline="") as fh:
        fh.write(payload)

    after_text = REPORT.read_bytes().decode("utf-8")
    after = stats(REPORT)
    assert after_text == before_text + payload, "追加之外的内容被动过了"
    assert after["crlf"] == 0, "追加后出现 CRLF"
    assert after["bom"] is False
    print(f"追加后：bytes={after['bytes']}  splitlines={after['splitlines']}  "
          f"split(\\n)={after['split_lf']}  CRLF={after['crlf']}  BOM={after['bom']}")
    print(f"增量：bytes +{after['bytes'] - before['bytes']}  "
          f"splitlines +{after['splitlines'] - before['splitlines']}")
    print(f"落盘闸门：「旧文件 + 追加内容」逐字相同 ✓")
    print(f"commit1 = {SHA1}  commit2 = {SHA2}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

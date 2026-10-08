# -*- coding: utf-8 -*-
"""F1-4：往 ``progress.md`` **末尾追加**一节（硬规矩 #82 / #83 + 控制者错误 #140 + 两处签名采纳）。

纪律：
* **只用 python 追加**，``open(..., "a", encoding="utf-8", newline="")``；
  **绝不用编辑器工具打开这个文件**——它有 336 KB，IDE 曾把陈旧且截断的缓存写回磁盘、
  永久丢了约 107 KB（账本 Ruling 116 的数据丢失事故）。
* 它现在是**纯 CRLF / 无 BOM**，故追加的内容一律自己写 ``\\r\\n``。
* 追加前后各打印一次字节数与行数。
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
LEDGER = ROOT / ".superpowers" / "sdd" / "2026-10-06-实施计划02-智能处方引擎" / "progress.md"
CRLF = "\r\n"

LINES = [
    "---",
    "",
    "### Task 5（合并后）: fix round 1 —— 控制者裁定入账（实现者代笔，Ruling 编号留给结案时统一分配）",
    "",
    "**代码基线**：`fc8f5a8`（Task 5 的 5.5 收尾，全量 672 passed）→ 本轮 `fix` 一个 commit + `docs` 一个 commit。",
    "**本节的主语**（硬规矩 #56）：下面 5 条裁定全部是**控制者在 fix round 1 派单里下的**，"
    "实现者只负责落地与代笔入账；两条新硬规矩（#82 / #83）与一条控制者错误（#140）同理。",
    "",
    "#### 一、控制者错误 #140 —— P5-A10 的「更正」本身是错的，整格撤回",
    "",
    "**事实（控制者亲跑坐实）**：`backend/app/domain/derive.py` 里 `BODY_FAT_LIMIT` 的定义行"
    "**上一行**逐字就是注释「体成分异常 C 的体脂率阈值（spec §6.3②）：男 > 20%、女 > 28%，"
    "**严格大于**。」，定义行逐字是 `BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}`。",
    "",
    "**故原计划写的「`derive.py:68-69` 明写严格大于」行号与引文双双正确。**"
    "控制者的探针只 grep 了**标识符** `BODY_FAT_LIMIT`、没 grep **注释行**，"
    "于是把「我的探针没显示它」讲成了「它不存在」。",
    "",
    "**→ 控制者错误 #140**，与同一个 commit（`c8e26b8`）里刚立下的**硬规矩 #80 同型**，"
    "这是第 **9** 次「把自己没验证的工具输出当事实」（前 8 次见硬规矩 #53/#57/#59/#60/#76/#77/#80）。",
    "",
    "**→ 补硬规矩 #82：探针「0 命中」时，必须先用一个已知存在的串验证这条查询本身有效，"
    "才允许把「没查到」讲成「不存在」。**",
    "",
    "**依据**：账本 Ruling 147 的 **P5-A13**（用一个自己没验证过的正则去数一个已经有字面断言的量，"
    "数出 3 而真值是 24）与本次的 **P5-A10** 是**同一根因的两次发作**，"
    "而硬规矩 #80 只覆盖了「已有字面断言」那一半——**「探针 0 命中」这一半它管不到**："
    "0 命中看起来像「事实」，而它同样可能是「查询本身无效」。"
    "自证的办法只有一步：拿一个**已知存在**的串跑同一条查询，看它是否命中。",
    "",
    "**落地**：计划正文 P5-A10 那一格的「更正」列已整格重写为「**撤回**」（补丁脚本 "
    "`_t5_fr1_plan_patch.py` 的 E1），5.3 正文里被 P5-A10 改坏的 `BODY_FAT_LIMIT` 描述"
    "已恢复成**可核的原文引用**（E2，保留「按可 grep 的原文找、不要按裸行号找」这半句——"
    "硬规矩 #78 仍成立），并删掉「原文行号口径错、引文控制者未核」那段自我指控。",
    "⚠️ 表格里 P5-A10 的**事实列**一个字没动（派单只要求重写「更正」列），"
    "改由紧邻的「更正」列以「**撤回**」开头整格反驳；已在实现者报告里显式列出请控制者裁定。",
    "",
    "#### 二、硬规矩 #83 —— `.pyc` 陈旧失效是**取证陷阱**，不是一般的 flaky",
    "",
    "**→ 补硬规矩 #83：变异取证与任何「改了又还原」的取证，必须在跑测试前 "
    "`shutil.rmtree(__pycache__, ignore_errors=True)` 并设 `PYTHONDONTWRITEBYTECODE=1`；"
    "**等长改动 + 同一秒**会让 CPython 的 `(mtime 截断到秒, size)` 失效判据不触发，"
    "于是加载陈旧字节码、产出假红或假绿。**",
    "",
    "**依据（Task 5 的 5.5 变异 ④ 实测经过）**：那一条变异打的是 "
    "`app/domain/prescription/intensity.py` 里 `hr_zone` 的取整方向"
    "（`int(-(-high_bpm // 1))` ↔ 反向写法）。四步是「量基线 → 打变异 → 跑红 → 还原再跑绿」，"
    "而**还原后重跑出现了假红**：文件的 sha256 **已经还原成功**（逐字节相同），"
    "pytest 却仍然报变异行为。机制是 CPython 的 `.pyc` 失效判据只有两项——"
    "**源文件 mtime 截断到秒** 与 **源文件 size**；而那一行的新旧两个写法"
    "**恰好等长（都是 47 字符）**，四步又在**同一秒**内完成，"
    "于是 `(mtime, size)` 二元组一字未变 → `.pyc` 被判定为仍然有效 → "
    "加载的是**变异版的字节码**。",
    "",
    "**已修**：变异脚本改成每次跑测试前 `shutil.rmtree(<模块所在包>/__pycache__, "
    "ignore_errors=True)`，并在子进程环境里设 `PYTHONDONTWRITEBYTECODE=1`（不再产出新的 `.pyc`），"
    "六次变异全部按新脚本重跑。⚠️ 本轮 fix round 1 的三次取证"
    "（`import types` 的纯净性探针、`.pyc` 无关的 YAML 重算、commit 前的全量）"
    "也一律带这两项。",
    "",
    "**它为什么比一般的 flaky 更危险**（这一条是硬规矩 #83 的立意，不是修饰）：",
    "",
    "* **假红**会让人**怀疑一个正确的还原**——于是开始「再还原一次」「再跑一次」，"
    "  而真因（陈旧字节码）从来不在被怀疑的清单里；更坏的是有人为了让它变绿而**再改一次代码**，"
    "  于是工作树与 index 悄悄分叉。",
    "* **假绿**更坏：它让人以为**一条守卫还在工作**。变异取证的整个价值就是「M1 必须红」，"
    "  一次假绿等于把「这条守卫有牙」这个结论建立在一个**没被真正执行过的文件**上——"
    "  而这恰好是硬规矩 #50/#53 要挡的那一类「尺子恒绿」。",
    "* 它的触发条件是**两个都很常见的巧合**（等长改动、同一秒完成），"
    "  而不是罕见的时序竞争，故**会复发**：任何「语义等价改写」型的变异"
    "  （正是硬规矩 #65 的 M1 对照要求的形状）**天然等长**。",
    "",
    "#### 三、控制者采纳实现者的两处签名扩参（Plan 02 实现者第 **5**、**6** 次顶回成立）",
    "",
    "| # | 落地签名 | 顶回的理由（控制者已认） |",
    "|---|---|---|",
    "| 5 | `apply_safety(pkg, inp, eq, *, template, exercises)` | "
    "`TrainingPackage` 里**没有** `addons` / `weekly_frequency`，故 P5-A3 要求的"
    "「追加**模板自己的** addon」、addon 的 `exercise_name` / `video_url` / `impact_level`"
    "「从 `exercises[addon.module]` 取」、`sessions_per_week = template.weekly_frequency` "
    "**一件都给不出来**；替身的 `name` / `url` / `impact_level` 同样只能从 `ExerciseSpec` 取"
    "（P5-A8：读**源**、不读模板里的冗余副本）。 |",
    "| 6 | `apply_overrides(pkg, records, *, exercises)` | "
    "`SUBSTITUTE_EXERCISE` 若只换 `exercise_ref`，那个 block 会**留着旧动作的视频 URL 与中文名**"
    "——学生扫码看到的是被换掉的那个动作，那是「**一个看起来正常的谎**」。 |",
    "",
    "**新增的两个形参一律 keyword-only**，口径照 `assemble` 的 `*, exercises`；"
    "三个位置参数与计划原文逐字一致。计划正文 5.3 / 5.4 的 `Produces` 两行与 5.3 的 "
    "`Consumes` 已同步（补丁脚本的 E5 / E10a / E10b）。",
    "",
    "#### 四、本轮另两条 Critical 裁定（F1-1 / F1-2）",
    "",
    "| # | 级别 | 裁定 | 落地 |",
    "|---|---|---|---|",
    "| **F1-1** | **Critical** | `assembly_snapshot[\"weekly_volume_base\"]` 原先是"
    "**混合量纲**的裸 `float`：`RED-END-ABN-01` 那一格是 `168.0` = `48.0 min + 120.0 reps`，"
    "**一个把分钟和次数加在一起的数没有意义**，而它要落进 `prescription.assembly_snapshot` "
    "这个 JSON 列、并在 Plan 03/04 被前端读出来展示，与 P5-A1 自己立的"
    "「两种单位不可通约」互相打脸。→ **改成按单位分列的 `Mapping[str, float]`，"
    "键数仍然是 12（不动键集契约）**。**实现者上一轮的异议成立、控制者采纳其替代方案。** | "
    "键 = 实际出现过的 `volume_unit`、值 = 该单位下的周量之和 `round(…, 1)`；"
    "`RED-END-ABN-01` 逐字面 = `{\"min\": 48.0, \"reps\": 120.0}`。"
    "**键集不写死**（18 套亲扫 `{(\"min\",): 10, (\"reps\",): 6, (\"min\", \"reps\"): 2}`，"
    "`\"unspecified\"` 0 次）。只读性：`types` **不在** `ALLOWED_MODULES` 里"
    "（亲跑：插一句 `import types` → 守卫报 `assembler.py:148: types`），"
    "而 `MappingProxyType` 又**不是** JSON 可序列化的"
    "（亲跑 `TypeError: Object of type mappingproxy is not JSON serializable`）→ "
    "落地是**屏蔽了全部 8 个 mutator 的私有 `dict` 子类** `_ReadOnlyVolumeBase`，"
    "两条约束唯一的交集。新增 6 条守卫（分列字面值 / 键集 / 8 个 mutator / "
    "copy+deepcopy+pickle / 12 键 JSON 化 / 15 键 JSON 化）。 |",
    "| **F1-2** | **Critical** | `rpe` 的值域原先写成 Borg 经典的那一套标度，**错了**："
    "spec 全篇的 RPE 都是 **0–10**，四处逐字可 grep（`rpe_record` 表字段「RPE 0–10」、"
    "§8.2 小标题「课堂端 RPE（0–10 主观疲劳）」、`RED_RPE_SUSTAINED`「RPE 连续 ≥ 9 分」、"
    "`YELLOW_CLASS_RPE_HIGH`「课堂 RPE 均值 > 7 分」、大屏异常名单「RPE > 8」）。"
    "**这是跨计划契约**：Plan 03 的实现者若把「9 分」读成那套标度的中高档，"
    "阈值语义整个错位。 | 值域改 **0–10** 并把出处逐字引进 docstring（硬规矩 #78：不写裸行号）；"
    "手工构造的测试值从 `13`（在该标度上非法）改成 `7`，断言的 `intensity_text` 随之改成 "
    "`\"RPE 7\"`；**新增**一道 `[0, 10]` 的运行时拒绝（与 `hr_zone` 的 "
    "`0 <= low <= high <= 100` 对称；加载器只校字段形状不校值域；`rpe` 在 18 套模板里出现 "
    "**0** 次，故可证明不会让任何真仓模板炸），守卫是 "
    "`test_rpe_value_outside_zero_to_ten_is_rejected`（`-0.1` / `0.0` / `10.0` / `10.1`）。 |",
    "",
    "#### 五、本轮的验收数字（实现者亲跑）",
    "",
    "* 全量：`cd backend; python -m pytest -q` → **679 passed**（基线 672）；"
    "带 `--cov=app.domain --cov-branch` → **678 passed, 1 skipped**。"
    "⚠️ **差的那 1 个是 `tests/pipeline/test_backfill.py` 里既有的墙钟断言**："
    "它按硬规矩 #42 在 `sys.gettrace()` 非空时**主动跳**，而 `pytest-cov` 正是靠 "
    "`sys.settrace()` 实现的。两个数指的是同一套测试，**没有丢测试**"
    "（已写进计划 5.5，补丁脚本的 E6）。",
    "* 覆盖率四格：**905 stmts / Miss 0 / 262 branch / BrPart 0 / 100%**"
    "（基线 888 / 0 / 260 / 0 / 100%；+17 stmts、+2 branch 全部来自 F1-1 的只读映射与 "
    "F1-2 的值域拒绝）。spec §12 的硬要求仍满足。",
    "* 公开面 `__all__` = **43**（`_ReadOnlyVolumeBase` 是**私有**的，故 43 → 43；"
    "`_PRESCRIPTION_PUBLIC_BASELINE` 与它的两句 `assert … == 43` 一个字没动）。",
    "* 扫描面 = **32**（domain 14 + pipeline 7 + db 11）。",
    "* 三个禁区指纹逐字不变：`D2C8E539E2FA0029` / `3DE598AF38631209` / `822CB86A5E998301`；"
    "`backend/pe.db` 不存在；`backend/data/seed/` 0 文件；`backend/data/` 一个字节没动。",
    "",
    "**下一步**：控制者复核本轮 → Task 5 结案 → 抽 Task 6 简报。",
    "",
]


def stats(path: pathlib.Path) -> tuple[int, int, int, int, bool]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    crlf = text.count("\r\n")
    return (len(raw), len(text.split("\r\n")), len(text.splitlines()),
            text.count("\n") - crlf, raw.startswith(b"\xef\xbb\xbf"))


def main() -> int:
    before_text = LEDGER.read_bytes().decode("utf-8")
    before = stats(LEDGER)
    print(f"追加前：bytes={before[0]}  split_lines={before[1]}  splitlines={before[2]}  "
          f"裸LF={before[3]}  BOM={before[4]}")
    assert before[3] == 0, "账本应为纯 CRLF"
    assert before[4] is False, "账本不该有 BOM"
    assert before_text.endswith("\r\n"), "账本不以 CRLF 结尾，追加会与旧尾行黏在一起"

    payload = CRLF.join(LINES)
    assert "\n" not in payload.replace("\r\n", ""), "追加内容里混进了裸 LF"

    # ⚠️ 闸门**全部在写盘之前**跑：写盘之后再断言就晚了（追加是不可撤销的）。
    for token, want in {
        "**→ 补硬规矩 #82：探针「0 命中」时": 1,
        "**→ 补硬规矩 #83：变异取证与任何「改了又还原」的取证": 1,
        "#### 一、控制者错误 #140": 1,
        "恰好等长（都是 47 字符）": 1,
        "四步又在**同一秒**内完成": 1,
        "#### 三、控制者采纳实现者的两处签名扩参": 1,
        "第 **5**、**6** 次顶回成立": 1,
        "`apply_safety(pkg, inp, eq, *, template, exercises)`": 1,
        "`apply_overrides(pkg, records, *, exercises)`": 1,
        "**905 stmts / Miss 0 / 262 branch / BrPart 0 / 100%**": 1,
    }.items():
        got = payload.count(token)
        assert got == want, f"追加内容里 {token[:40]!r} 命中 {got} 次、期望 {want}"
    print("写盘前闸门：10 个必需串在追加内容里各命中 1 次 ✓")

    with LEDGER.open("a", encoding="utf-8", newline="") as fh:
        fh.write(payload)

    after_text = LEDGER.read_bytes().decode("utf-8")
    after = stats(LEDGER)
    print(f"追加后：bytes={after[0]}  split_lines={after[1]}  splitlines={after[2]}  "
          f"裸LF={after[3]}  BOM={after[4]}")
    assert after[3] == 0, f"追加后出现裸 LF {after[3]} 个"
    assert after[4] is False
    # **最强的一道闸门**：改后的文件必须逐字等于「旧文件 + 本次追加的内容」，
    # 即前 336 KB 一个字都没被碰过（IDE 曾把陈旧且截断的缓存写回磁盘、丢了约 107 KB）。
    assert after_text == before_text + payload, "追加之外的内容被动过了"
    print(f"增量：bytes +{after[0] - before[0]}  split_lines +{after[1] - before[1]}  "
          f"splitlines +{after[2] - before[2]}  payload_crlf={payload.count(CRLF)}")
    assert after[1] - before[1] == payload.count(CRLF)
    print("落盘闸门：「旧文件 + 追加内容」逐字相同 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())

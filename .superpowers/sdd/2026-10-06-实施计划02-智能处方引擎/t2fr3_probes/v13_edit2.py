# -*- coding: utf-8 -*-
"""fr3 edit engine, group yaml + spec.

usage: python v13_edit2.py <yaml|spec|fp> [--dry]
  yaml : the two backend/data YAML comment fixes (I3 / I6 / M-4 / M-6 / M-8 / M-9)
  spec : Document/...设计spec.md §14 item 28 last cell (I7)
  fp   : the two fingerprint constants in tests/test_refdata_prescription.py
"""
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims")
CRLF = bytes([13, 10])
LF = bytes([10])


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16].upper()


def norm_fp(b):
    return hashlib.sha256(b.replace(CRLF, LF)).hexdigest()[:16].upper()


class File:
    def __init__(self, rel):
        self.rel = rel
        self.path = ROOT / rel
        self.raw = self.path.read_bytes()
        self.n_crlf = self.raw.count(CRLF)
        self.n_lf = self.raw.count(LF)
        if self.n_crlf == 0:
            self.eol = "\n"
        elif self.n_crlf == self.n_lf:
            self.eol = "\r\n"
        else:
            raise SystemExit(f"REFUSE: {rel} MIXED eol (CRLF {self.n_crlf} / LF {self.n_lf})")
        self.text = self.raw.decode("utf-8").replace("\r\n", "\n")

    def sub(self, tag, old, new, expect=1):
        n = self.text.count(old)
        if n != expect:
            raise SystemExit(f"FAIL[{tag}] {self.path.name}: expected {expect} OLD hit(s), got {n}")
        if self.text.count(old[:40]) < 1:
            raise SystemExit(f"FAIL[{tag}] search mechanism invalid")
        self.text = self.text.replace(old, new)
        if self.text.count(old) != 0 or self.text.count(new) < expect:
            raise SystemExit(f"FAIL[{tag}] after replace: old={self.text.count(old)} "
                             f"new={self.text.count(new)}")
        print(f"  OK [{tag}] old {n}->0 ; new ->{self.text.count(new)}")

    def write(self, dry):
        out = self.text.replace("\n", self.eol).encode("utf-8")
        eolname = "CRLF" if self.eol == "\r\n" else "LF"
        ncrlf = out.count(CRLF)
        nlf = out.count(LF)
        if dry:
            print(f"  DRY {self.rel}: {len(self.raw)} -> {len(out)} B ; eol={eolname} ; "
                  f"CRLF {self.n_crlf}->{ncrlf} ; normfp {norm_fp(self.raw)} -> {norm_fp(out)}")
            return out
        self.path.write_bytes(out)
        chk = self.path.read_bytes()
        if chk != out:
            raise SystemExit(f"FAIL write-verify {self.path}")
        print(f"  WROTE {self.rel}: {len(self.raw)} -> {len(chk)} B ; eol={eolname} ; "
              f"CRLF {self.n_crlf}->{chk.count(CRLF)} / LF {nlf} ; "
              f"normfp {norm_fp(self.raw)} -> {norm_fp(chk)} ; rawsha {sha(self.raw)} -> {sha(chk)}")
        return chk


def group_yaml(dry):
    f = File("backend/data/exercises.yaml")
    f.sub("I6/exercises.yaml #29 -> #30", """#                 ⚠️ 这一条**尚未登记进 spec §14**：本轮只被授权追加第 28 项
#                 （volume_reduction 系数），而计划 Task 12 Step 3 已把「动作库的视频源」
#                 预留为 #29 —— 见 task-2-report.md 的「关切与未尽事项」。
""", """#                 ⚠️ 这一条**尚未登记进 spec §14**：Task 2 只被授权追加第 28 项
#                 （volume_reduction 系数），而计划 02 的 Task 12 Step 3 那份 §14 补项清单里
#                 「动作库的视频源」排在 **#30**（fix round 3 更正：此前这里印的「预留为 #29」
#                 是本文件落地那一刻（`3ea27cc`）的旧编号；紧接着的 `d40f36c` 把 #28 让给本
#                 文件的 volume_reduction 项、Task 12 的清单去重后整体前移一位，于是原 #29
#                 变成 **#30**。计划正文那一行逐字是「**#30** 动作库的视频源（占位 `.invalid`
#                 URL；⚠️ Task 2 已把它写进 `exercises.yaml` 的头注释，本项是把它正式登记进
#                 §14）」）—— 见 task-2-report.md 的「关切与未尽事项」。
""")
    f.sub("M4/exercises.yaml 12 项的出处", """# 【条目数 23 的口径】计划 Task 2 Step 1 定的骨架 = spec §7.2 :487 点名的 **12** 项
# （间歇跑、复合循环、持续跑、台阶训练、自重抗阻、弹力带抗阻、兴趣球类、定向越野、
# 功能性训练、HIIT、能量消耗模块、抗阻优先模块）+ 速度柔韧类 **4** 项（50 米冲刺间歇、
# 动态拉伸、折返跑、坐位体前屈专项）= **16**，再按 18 套模板（3 层 × 3 主导短板 ×
# 2 体成分）的实际需要补 **7** 项 = **23**，落在计划「预估 20–30 个」的区间内。
# 补的 7 项及理由，逐条写在下面各分节的注释里。
""", """# 【条目数 23 的口径】计划 Task 2 Step 1 定的骨架 = spec §7.2 点名的 **12** 项
# （间歇跑、复合循环、持续跑、台阶训练、自重抗阻、弹力带抗阻、兴趣球类、定向越野、
# 功能性训练、HIIT、能量消耗模块、抗阻优先模块）+ 速度柔韧类 **4** 项（50 米冲刺间歇、
# 动态拉伸、折返跑、坐位体前屈专项）= **16**，再按 18 套模板（3 层 × 3 主导短板 ×
# 2 体成分）的实际需要补 **7** 项 = **23**，落在计划「预估 20–30 个」的区间内。
# ⚠️ 这 12 项的**出处不止一行**（fix round 3 更正：此前写「spec §7.2 :487 点名的 12 项」，
# 归属不对——数字 12 / 16 / 23 都是对的）。spec §7.2 末尾那段「指导文件给出的层级参数已
# 全部落入模板」的散文确实点名了 **12** 个东西，但**其中一个是「可选挑战任务」**，而本文件
# 把它算作下面的补项 7（它此前没有 ref）；反过来，本文件这 12 项里的「**抗阻优先模块**」
# 出自 §7.2 的 `addons` 代码块（`when: muscle_low` / `module: resistance_priority`），
# 那段散文里**没有**它。即：**散文的 12 项 − 可选挑战任务 + 抗阻优先模块（addons 代码块）
# = 本文件的 12 项**。「能量消耗模块」两处都点了（addons 代码块的
# `energy_expenditure_plus_10pct` 与散文的「体脂超标追加 10% 能量消耗模块」），是同一个
# 东西，不重复计数。
# 补的 7 项及理由，逐条写在下面各分节的注释里。
""")
    f.sub("M6/exercises.yaml 2-3 倍体重的出处（首现处）", """# 直接落进 spec §7.4 :514 的 needs_review 路径。
brisk_walking:
""", """# 直接落进 spec §7.4 :514 的 needs_review 路径。
# ⚠️ **「2–3 倍体重」与「约 1.2 倍」这两个数没有出处**（硬规矩 #19；fix round 3 补记）：
# spec 全文没有它们，本轮也拿不出可引用的指导文件 / 运动处方规范条文。它们是**工程估计**，
# 单位口径是「地面反作用力峰值 ÷ 体重」（无量纲倍数），只用来解释「为什么选这两个动作当
# 替身」，**不被任何测试守卫**，也**不得被 Task 7 当成 spec 条文或医学阈值引用**——这一点
# 与 `exercise_equivalence.yaml` 的 `volume_reduction` 两个系数**不同**（那两个数虽然同样
# 无 spec 出处，但已按 Plan02 账本 P2-A3 登记进 spec §14 第 28 项）。若项目组能给出实测或
# 文献出处，请替换本段并注明来源与测量口径。下面 `plyometric_jump` 那节的「反复 2–3 倍
# 体重冲击」是同一个数、同一处置。
brisk_walking:
""")
    f.sub("M6/exercises.yaml 2-3 倍体重（第二处）", """# 而它同时是 BMI > 30 时**最该被换掉**的动作（反复落地 = 反复 2–3 倍体重冲击）。
""", """# 而它同时是 BMI > 30 时**最该被换掉**的动作（反复落地 = 反复 2–3 倍体重冲击；⚠️ 这个
# 倍数是**工程估计、无出处、不被任何测试守卫**，处置同上面 `brisk_walking` 那节的说明）。
""")
    f.sub("M8/exercises.yaml 节标题不是清一色绿层", """# 绿层兴趣 / 综合，与两个 addon 模块（spec §7.2 :480-487）
""", """# 兴趣 / 综合，与两个 addon 模块（spec §7.2 :480-487）
# ⚠️ 本节 5 个条目**跨红 / 黄 / 绿三层**，不是清一色绿层（fix round 3 更正：节标题此前写
# 「绿层兴趣 / 综合」，而本节里 `hiit` 自己的注释写的是**黄层**、
# `energy_expenditure_plus_10pct` 写的是**红层**）：interest_ball_games（绿层）/
# functional_training（绿层）/ hiit（**黄层**，「体脂偏高附加 5min HIIT」）/
# energy_expenditure_plus_10pct（**红层**，「体脂超标追加 10% 能量消耗模块」）/
# challenge_task（绿层，「可选挑战任务」）。逐条的层归属见各自注释。
# ⚠️ 别把两个维度混起来：这里的「层」是**红/黄/绿分层**（spec §7.2 的训练频次与参数档位），
# 与条目的 `impact_level`（high/medium/low **冲击**）无关——本节标题说的是前者。
""")
    f.sub("M9/exercises.yaml challenge_task 的断言依赖", """# ⚠️ 变异验收 ② 用的正是这个 ref：删掉它，全仓**只有**指纹测试会红——因为没有任何一条
# 映射或断言依赖它（Plan02 账本 P2-C1：原文还要求「模板引用存在性」测试变红，而那个
# 测试是 Task 3 才建的）。
""", """# ⚠️ 变异验收 ② 用的正是这个 ref：删掉它，全仓**只有**指纹测试会红——因为没有任何一条
# **映射**依赖它（实测它既不是任何映射的 `from`、也不是任何映射的 `to`），也没有任何一条
# 断言会**因为它消失**而变红。⚠️ 后半句要分开说（fix round 3 更正：此前写「没有任何一条
# 映射或断言依赖它」，字面上不成立）——`tests/test_refdata_prescription.py` 的
# `test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable` 把这个 ref
# **硬编码**进了断言，当「无映射的 ref」探针用（`assert table.lookup("challenge_task", …)
# is None`）；而 `lookup` 只查等价表、不查动作库，故删掉它那条**仍然绿**，只是探针语义变弱
# （它不再证明「动作库里有、等价表里没有的 ref 返回 None」，只证明「等价表里没有的 ref
# 返回 None」）。（Plan02 账本 P2-C1：原文还要求「模板引用存在性」测试变红，而那个测试是
# Task 3 才建的。）
""")
    f.write(dry)

    g = File("backend/data/exercise_equivalence.yaml")
    g.sub("I3/exercise_equivalence.yaml 5 个 -> 4 个", """# `low`（8 个 low 动作里的 5 个被用到：stationary_cycling / brisk_walking /
# bodyweight_resistance / functional_training，其中 stationary_cycling 被 4 条复用）。
""", """# `low`（8 个 low 动作里被用到的是 **4** 个：stationary_cycling / brisk_walking /
# bodyweight_resistance / functional_training，其中 stationary_cycling 被 4 条复用、其余
# 三个各被 2 条复用；fix round 3 更正：此前印的「5 个」与本句自己列出的 4 个名字自相矛盾，
# 实测 `to` 的去重集合就是这 4 个。另外 4 个 low 动作——band_resistance / dynamic_stretching
# / pnf_stretching / sit_and_reach_drill——今天**不是任何映射的落点**，将来加映射时优先从
# 它们里挑，不必新造动作）。
""")
    g.write(dry)


def group_spec(dry):
    f = File("Document/2026-09-28-体育闭环原型-设计spec.md")
    # take OLD verbatim from the file (no transcription risk): from the warning marker
    # up to the trailing cell terminator of that one table row.
    MARK = "⚠️ **编号冲突待 Task 12 处理**"
    if f.text.count(MARK) != 1:
        raise SystemExit(f"FAIL: marker hits = {f.text.count(MARK)}")
    i = f.text.index(MARK)
    j = f.text.index("\n", i)
    row = f.text[i:j]
    if not row.endswith(" |"):
        raise SystemExit(f"FAIL: row tail is {row[-20:]!r}")
    old = row[:-2]  # drop the trailing ' |' cell terminator
    new = ("⚠️ **编号冲突已由计划 02 的 `d40f36c` 处理完毕**（本项此前印的「待 Task 12 处理」"
           "已过期，且它开的处方与实际执行结果不符 —— Task 2 fix round 3 更正）：Task 12 "
           "Step 3 的原文把 **#28** 预留给「18 套模板的审校状态」、把 **#32** 预留给与本项"
           "**同一主题**的「§7.4 的跑量下调系数与『提高抗阻比重』的处置」；本项因「值在这一刻"
           "被写死」提前到 Task 2 登记（Plan02 账本 P2-A3 的裁定），故 Task 12 的清单**去重后"
           "整体前移一位**：原 #28→**#29**、原 #29→**#30**、原 #30→**#31**、原 #31→**#32**、"
           "~~原 #32~~（**删除**，已由本项覆盖）、原 #33→**#33**、原 #34→**#34**，即 "
           "**7 项 − 1 项重复 = 6 项、连续编号 #29–#34**，§14 总数仍是 "
           "`27 + 1（Task 2）+ 6（Task 12）= **34**`。⚠️ **不是**此前这里写的「整体后移为 "
           "**#29–#35**」—— 照那句执行会得到一个 7 个号宽的号段，删掉其中重复的一项后凭空多出"
           "一个 **#35** 并留下一个空洞，与已执行的结果不符，Task 12 若照它办事会把已经正确的"
           "计划正文再改一遍。逐字依据在计划 02 的 Task 12 Step 3：标题行「本 Task 追加 **6 项，"
           "#29–#34**」、其下的「⚠️ **P2-A3 的后续更正（Task 2 实现后）**」整段、§14 补项清单行"
           "（「**#30** 动作库的视频源」），以及「计划完成后的状态」里的「spec §14 从 27 项扩到 "
           "**34** 项」（计划行号绑 `2df6825`：`:682` / `:684` / `:688` / `:707`；此前这里引的 "
           "`:681` 与 `:685` 是 `fb5bddb` 的位置）。**唯一仍可能出现的 #35** 是计划 Step 3 "
           "自己留的条件项：若 Task 7 落地时发现本项正文没有覆盖「提高抗阻比重」的处置，才由 "
           "Task 7 追加为 #35。")
    if "|" in new:
        raise SystemExit("FAIL: NEW contains a pipe, would break the markdown table row")
    print(f"  OLD cell length = {len(old)} ; NEW cell length = {len(new)}")
    f.sub("I7/spec §14 第 28 项 影响面格", old, new)
    f.write(dry)


def group_fp(dry):
    ex = (ROOT / "backend/data/exercises.yaml").read_bytes()
    eq = (ROOT / "backend/data/exercise_equivalence.yaml").read_bytes()
    new_ex = norm_fp(ex)
    new_eq = norm_fp(eq)
    print(f"  computed from disk: exercises.yaml normfp={new_ex} ({len(ex)} B, CRLF {ex.count(CRLF)})")
    print(f"  computed from disk: exercise_equivalence.yaml normfp={new_eq} ({len(eq)} B, CRLF {eq.count(CRLF)})")
    f = File("backend/tests/test_refdata_prescription.py")
    f.sub("FP/EXERCISES_FINGERPRINT", 'EXERCISES_FINGERPRINT = "A6A000F58815FCBB"',
          f'EXERCISES_FINGERPRINT = "{new_ex}"')
    f.sub("FP/EQUIVALENCE_FINGERPRINT", 'EQUIVALENCE_FINGERPRINT = "0FFB881574AC04F3"',
          f'EQUIVALENCE_FINGERPRINT = "{new_eq}"')
    f.write(dry)


if __name__ == "__main__":
    g = sys.argv[1]
    dry = "--dry" in sys.argv
    {"yaml": group_yaml, "spec": group_spec, "fp": group_fp}[g](dry)

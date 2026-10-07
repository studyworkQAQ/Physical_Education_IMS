# -*- coding: utf-8 -*-
"""生成 backend/data/prescription/*.yaml 的 18 套模板（一次性工具，留作取证）。

**为什么用生成器而不是手写 18 份**：18 份文件必须结构完全同形（同一批校验路径、同一批
不变量：天数 = weekly_frequency、week_deltas 长度 = microcycle_weeks、day 连续、
reachable 与维度一致），手写 18 遍最容易出的错正是「某一份少写一天」这类**结构**错，
而它恰好是 test_sessions_total_is_fifty_four 要抓的东西。生成器把「矩阵 × 序号」的规则
写在一处，逐份的差异只有三处：维度、blocks、注释里的出处。

**每个值的出处**都在文件自己的注释里（硬规矩 #19：散文带口径）。生成器不发明任何运动
生理学参数：blocks 的动作与强度只取 spec §7.2 :470-477（骨架逐字）、:487（指导文件转述）
与 exercises.yaml 里各「补项」注释声明的层/桶归属；structure 只取 :473 与 :477 的两个字面
字典，按「时间型动作 / 次数型动作」二选一。
"""
import pathlib

OUT = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\backend\data\prescription")

REVIEWER = "原型自审（占位）"
REVIEWED_AT = "2026-10-06"

# 时间型结构 = spec §7.2 :473 逐字；次数型结构 = :477 逐字
TIME = "{sets: 4, work_min: 3, rest_min: 2}"
REPS = "{rounds: 3, reps: 10}"

LAYERS = [("red", "RED", 4), ("yellow", "YEL", 3), ("green", "GRN", 2)]
BUCKETS = [("endurance", "END", "耐力"), ("strength", "STR", "力量"),
           ("speed_flexibility", "SPD", "速度柔韧")]
BODY = [("abnormal", "ABN"), ("normal", "NOR")]

# blocks: (ref, impact_level, intensity 流式映射字面量, structure)
BLOCKS = {
    ("red", "endurance"): [
        ("interval_run", "high", "{type: hrmax_pct, low: 60, high: 70}", TIME),
        ("compound_circuit", "medium", "{type: onerm_pct, value: 70}", REPS),
    ],
    ("red", "strength"): [
        ("compound_circuit", "medium", "{type: onerm_pct, value: 70}", REPS),
        ("medicine_ball_core", "medium", "{type: onerm_pct, value: 70}", REPS),
        ("plyometric_jump", "high", "{type: none}", REPS),
    ],
    ("red", "speed_flexibility"): [
        ("sprint_50m_intervals", "high", "{type: hrmax_pct, low: 60, high: 70}", TIME),
        ("shuttle_run", "high", "{type: hrmax_pct, low: 60, high: 70}", TIME),
        ("dynamic_stretching", "low", "{type: none}", TIME),
    ],
    ("yellow", "endurance"): [
        ("steady_run", "medium", "{type: none}", TIME),
        ("step_training", "medium", "{type: none}", TIME),
    ],
    ("yellow", "strength"): [
        ("bodyweight_resistance", "low", "{type: none}", REPS),
        ("band_resistance", "low", "{type: none}", REPS),
    ],
    ("yellow", "speed_flexibility"): [
        ("shuttle_run", "high", "{type: none}", TIME),
        ("sit_and_reach_drill", "low", "{type: none}", TIME),
        ("pnf_stretching", "low", "{type: none}", TIME),
    ],
    ("green", "endurance"): [
        ("orienteering", "medium", "{type: none}", TIME),
        ("interest_ball_games", "medium", "{type: none}", TIME),
    ],
    ("green", "strength"): [
        ("functional_training", "low", "{type: none}", REPS),
        ("challenge_task", "medium", "{type: none}", REPS),
    ],
    ("green", "speed_flexibility"): [
        ("interest_ball_games", "medium", "{type: none}", TIME),
        ("agility_ladder", "medium", "{type: none}", TIME),
    ],
}

ADDONS = {
    "red": [
        ("body_fat_over", "energy_expenditure_plus_10pct",
         "红层 +10% 能量消耗（spec §7.2 :482 逐字）"),
        ("muscle_low", "resistance_priority",
         "spec §7.2 :484 逐字；spec §7.4 :509「提高抗阻模块比重」与层无关"),
    ],
    "yellow": [
        ("body_fat_over", "energy_expenditure_plus_5min_hiit",
         "黄层「体脂偏高附加 5min HIIT」（spec §7.2 :487）；ref 由 Task 3 按 P3-A4 追加"),
        ("muscle_low", "resistance_priority",
         "照红层（spec §7.2 :484 未给层限定；spec §7.4 :509 与层无关）"),
    ],
    "green": [],
}

# 每格 blocks 的出处（逐字写进文件注释，硬规矩 #19）
SOURCE = {
    ("red", "endurance"): """\
# · blocks 的两项 —— spec §7.2 :470-477 的骨架**逐字**（那一节的示例文件正是
#   RED-END-ABN-01）：interval_run + compound_circuit，连 intensity 与 structure 都照抄
# · 60–70% HRmax —— spec §7.2 :487「红层…耐力短板 60–70% HRmax 间歇跑」
# · 70% 1RM —— spec §7.2 :487「力量短板 70% 1RM 复合循环」（骨架把它也放进了耐力那一套，
#   作为辅项；本套照骨架）""",
    ("red", "strength"): """\
# · 70% 1RM 复合循环 —— spec §7.2 :487「红层…力量短板 70% 1RM 复合循环」+ :476 的字面强度
# · medicine_ball_core 同用 70% 1RM —— exercises.yaml 的「补项 3」注释：红层力量短板需要一个
#   70% 1RM 量级的**可加载单动作**抗阻主项（复合循环是多动作串联、单动作强度上不去）
# · plyometric_jump 的 intensity 是 none —— exercises.yaml 的「补项 4」注释把它归给红层力量
#   （立定跳远是国标 6 个短板判定项之一、归 strength 桶），但**指导文件没给跳跃类的负荷
#   参数**，故不编一个数：type: none 是「指导文件未给」的显式写法（留空分不清「不需要」与
#   「忘了填」）。它的 impact_level 仍是 high（动作库所有），于是 BMI > 30 的学生会被
#   spec §7.4 :508 换成 bodyweight_resistance（等价表里有那两条映射）""",
    ("red", "speed_flexibility"): """\
# ⚠️⚠️ **强度参数借用同层耐力短板的配置**：指导文件未给出速度柔韧桶的层级参数
#   （spec §7.2 :487 的空洞——那一行只点了耐力与力量两个桶），见 **spec §14 第 31 项**
#   与 §7.2 的勘误。故本套的 60–70% HRmax 借自红层耐力（:487「红层…耐力短板 60–70% HRmax」），
#   **不是**速度柔韧桶的实测参数，须由体育专家给出该桶的实际参数后替换。
# · 动作选自简报 Step 2-5 点名的四项速度柔韧类动作里的三项（50 米冲刺间歇、折返跑、动态拉伸）
# · dynamic_stretching 的 intensity 是 none：拉伸类没有 HRmax / 1RM 量级的强度目标，
#   编一个数就是编造运动生理学参数（简报明令禁止）""",
    ("yellow", "endurance"): """\
# · 持续跑 + 台阶训练 —— spec §7.2 :487「黄层…耐力短板持续跑+台阶训练」
# · intensity 一律 none —— **指导文件没给黄层任何强度数值**（:487 只给了红层的两个数：
#   60–70% HRmax 与 70% 1RM）。故不编：type: none 是「指导文件未给」的显式写法。
#   ⚠️ 这与 spec §14 第 31 项（速度柔韧桶的空洞）是同一类空洞、但**不是同一处**：
#   那一处是「红/黄层的 speed_flexibility 桶没有参数」，这一处是「整个黄层没有强度数值」。
#   已在 spec §7.2 的勘误里一并交代，并作为关切报给控制者""",
    ("yellow", "strength"): """\
# · 自重 + 弹力带抗阻 —— spec §7.2 :487「黄层…力量短板自重+弹力带抗阻」
# · intensity 一律 none —— 同上：指导文件没给黄层任何强度数值，且自重/弹力带本就没有
#   1RM 量级的可加载强度（1RM 是杠铃类动作的概念）。不编造参数""",
    ("yellow", "speed_flexibility"): """\
# ⚠️⚠️ **本套没有任何强度数值，因为黄层根本没有**：简报 Step 2-5 说「红/黄层的
#   speed_flexibility 用**该层已给出的强度区间**（红 60–70% HRmax、黄层按耐力那套的量）」，
#   而黄层耐力那套的量**也是空的**（spec §7.2 :487 只给了红层两个数）。故本套 intensity
#   一律 none，与黄层其余两套同形。指导文件未给出速度柔韧桶的层级参数这件事见
#   **spec §14 第 31 项**与 §7.2 的勘误。
# · 动作选自简报 Step 2-5 点名的四项速度柔韧类动作里的三项（折返跑、坐位体前屈专项、PNF 拉伸）
#   ——50 米冲刺间歇留给了红层（同一桶在两层的负荷档位应当不同，而指导文件没给，故按
#   「红层用 high 冲击的冲刺、黄层用 high 冲击的折返 + 两个 low 冲击的柔韧项」区分）""",
    ("green", "endurance"): """\
# · 定向越野 + 兴趣球类 —— spec §7.2 :487「绿层每周 2 天、兴趣球类/定向越野/功能性训练
#   + 可选挑战任务」。**指导文件没按桶区分绿层**（那一行是绿层的整段），故三个桶各自从
#   这四个动作里挑与桶的 targets 相符的两个（本套挑 targets 含 endurance 的两个）
# · intensity 一律 none —— 指导文件没给绿层任何强度数值。不编造参数
# · addons 是空列表 —— **指导文件未给绿层附加模块**（简报 Step 2-5 的裁定）。
#   ⚠️ 后果：spec §7.4 :510 的第三个触发（体脂率异常）对绿层学生将无模块可追加。
#   今天这条路不可达（绿层必然 NOT C，spec §7.1 :445），但 :510 没写层限定，故分层规则
#   一旦调整它就变成真漏洞——已作为关切报给控制者""",
    ("green", "strength"): """\
# · 功能性训练 + 可选挑战任务 —— spec §7.2 :487 绿层那一段点名的第三与第四个动作
#   （指导文件没按桶区分绿层，故三个桶各自从那四个里挑；本套挑 targets 含 strength 的两个）
#   ⚠️ 「可选挑战任务」在 spec 里是**可选**的，本套把它写成一个固定 block：模板是骨架，
#   「可选」的语义（教师可以拿掉）属于 spec §7.5 的教师覆盖，不属于模板本身
# · intensity 一律 none —— 指导文件没给绿层任何强度数值。不编造参数
# · addons 是空列表 —— **指导文件未给绿层附加模块**（同 green/endurance 那一份的注释）""",
    ("green", "speed_flexibility"): """\
# · 兴趣球类 + 绳梯敏捷 —— spec §7.2 :487 绿层那一段点名的「兴趣球类」+ exercises.yaml
#   「补项 5」（绳梯敏捷：绿层速度柔韧短板需要一个 medium 档的敏捷主项，两个 low 档的
#   拉伸类动作撑不起一次课的主体部分）。指导文件没按桶区分绿层，故三个桶各自挑
# · intensity 一律 none —— 指导文件没给绿层任何强度数值。不编造参数
# · addons 是空列表 —— **指导文件未给绿层附加模块**（同 green/endurance 那一份的注释）""",
}

UNREACHABLE_NOTE = """\
# ⚠️⚠️ **本套当前不可达，但内容齐全**（spec §7.1 :445「按 §6.2 决策表，绿色层必然 NOT C，
#   因此 (green, *, abnormal) 这 3 套当前不可达」；:447「保留为**预留位**，不删除」）。
#   `reachable: false` 的唯一所有者是 `app/domain/prescription/templates.py` 的
#   `is_reachable()`——加载器会校验这一行与它一致，故**只翻这一行是不够的**：分层规则若
#   真的调整（:447 的②「允许『8 项达标但体成分异常』者留在绿色层做体成分专项干预」），
#   要改的是那个函数。
#   **为什么预留位也有完整的 sessions**（本 Task 的自主决定，三条理由）：
#   ① :447 的②说「模板位已就绪」，就绪意味着内容齐全，空壳不是就绪；
#   ② :447 的①说「维持指导文件『18 套』的字面完整性，专家评审时无需解释为何只有 15 套」，
#      专家要能审的是一套真模板；
#   ③ 空壳会迫使加载器为预留位开一条豁免分支，于是 18 套里有 3 套走另一条校验路径
#      ——那条路径永远不被真数据走过，正是 Review Focus 第 1 条要消灭的静默失效。
#   故本套与其余 15 套**同形**，只有 reachable 一个字段不同。""",

FREQUENCY_NOTE = {
    "red": "# · weekly_frequency: 4 —— spec §7.2 :465 的行内注释「红 4 / 黄 3 / 绿 2（指导文件原文）」",
    "yellow": "# · weekly_frequency: 3 —— spec §7.2 :465 的行内注释「红 4 / 黄 3 / 绿 2（指导文件原文）」",
    "green": "# · weekly_frequency: 2 —— spec §7.2 :465 的行内注释「红 4 / 黄 3 / 绿 2（指导文件原文）」",
}

COMMON_TAIL = """\
# · microcycle_weeks: 4 与 week_deltas [1.00, 1.05, 1.10, 0.85] —— spec §7.2 :464 与 :479
#   （:479 的行内注释逐字「第 4 周减量，超量恢复」）。18 套全部相同：指导文件给的是一个
#   4 周微周期，没有按层/桶区分递进曲线
# · version / review —— 用户已裁定：18 套全部 `approved` + 占位审校人 + **固定** ISO 日期
#   （不能用 date.today()：那会让 YAML 每次生成都变、指纹测试天天红）。
#   ⚠️ 这不是审校结果，须由邹红老师实际审校后替换 —— **spec §14 第 29 项**
#
# ⚠️ **本文件被指纹钉住**：`tests/domain/test_prescription_templates.py` 的
#   `TEMPLATE_FINGERPRINTS`（sha256 前 16 位、行尾归一化为 LF 之后），键是本文件的
#   `template_id`。改任何一个字节都要同步那一行（「知识资产变更需被显式承认」）。
# ⚠️ **行尾必须是 LF**：`.gitattributes` 的 `backend/data/**/*.yaml text eol=lf`
#   （Plan02 账本 P3-D2 新加——原有的 `backend/data/*.yaml` 的 `*` **不跨 `/`**、盖不住
#   本子目录）。守卫是 `test_every_template_yaml_is_lf_only_in_the_worktree`。
# ⚠️ **文件名必须 == template_id**（加载器校验）：这样「文件 ↔ 模板」不需要第二张对照表，
#   且报错里的文件名与专家手里的文件名对得上。
"""


def _c(text, comment, width=32):
    """把一行 ``text  # comment`` 的注释对齐到第 ``width`` 列（专家要逐份读，对齐是可读性）。"""
    return text + " " * max(1, width - len(text)) + "# " + comment


def render(template_id, serial, layer, layer_code, freq, bucket, bucket_code,
           focus, body_comp, body_code):
    reachable = not (layer == "green" and body_comp == "abnormal")
    blocks = BLOCKS[(layer, bucket)]
    addons = ADDONS[layer]

    head = [
        f"# backend/data/prescription/{template_id}.yaml —— 18 套处方模板的第 {serial:02d} 套",
        "#",
        f"# 维度：层 {layer} × 主导短板 {bucket} × 体成分 {body_comp}",
        "#       （spec §7.1 :443「层(3) × 主导短板(3) × 体成分(2) = 18」的一格）",
        f"# 可达：{'**是**' if reachable else '**否**（预留位）'}",
        "#",
        "# 【template_id 的格式】<层3>-<桶3>-<体成分3>-<序号2>，共 14 字符，照 spec §7.2 :454",
        "# 的骨架首行 `template_id: RED-END-ABN-01`。缩写：层 RED/YEL/GRN，桶 END/STR/SPD，",
        "# 体成分 ABN/NOR（spec 只给了 END 与 ABN 两个，其余由本 Task 定）。末两位是**全局序号**",
        "# 01-18，枚举序 = 层（红→黄→绿）× 桶（耐力→力量→速度柔韧）× 体成分（**异常→正常**）。",
        "# ⚠️ 体成分取「异常在前」是为了让 spec :454 那个字面示例由这条规则**原样重现**——",
        "# spec 只给了这一个 id，任何「正常在前」的定序都会让它变成 -02，即与 spec 的字面冲突。",
        "#",
        "# 【本套每个值的出处】（硬规矩 #19：散文带口径；spec 行号绑定 2026-10-06 的 spec 文件）",
        FREQUENCY_NOTE[layer],
        "# · sessions 的天数 = weekly_frequency（简报 Step 2-5），day 从 1 连续递增",
        "# · focus 一律是桶名 —— 指导文件按「层 × 短板」给参数、**没有**按周内第几天给，",
        "#   故同一套模板的每一天 focus 相同、blocks 也相同。要分化到「周一练什么、周三练什么」",
        "#   需要专家给出参数，已并入 spec §14 第 29 项的审校范围",
    ]
    head.append(SOURCE[(layer, bucket)])
    if not reachable:
        head.append(UNREACHABLE_NOTE[0])
    head.append(COMMON_TAIL.rstrip("\n"))

    body = [
        f"template_id: {template_id}",
        _c('version: "1.0"', "字符串：不加引号的 1.10 会被 PyYAML 读成 1.1"),
        _c(f"layer: {layer}", "red | yellow | green（spec §7.2 :456）"),
        _c(f"weakness: {bucket}", "endurance | strength | speed_flexibility（:457）"),
        _c(f"body_comp: {body_comp}", "normal | abnormal（:458）"),
        _c(f"reachable: {'true' if reachable else 'false'}",
           "必须与 is_reachable(layer, body_comp) 一致（spec §7.1 :447）"),
        "review:",
        _c("  status: approved",
           "pending | approved（:461）；:451「!= approved 拒绝用于生成」"),
        _c(f"  reviewer: {REVIEWER}",
           "⚠️ 占位，须由邹红老师实际审校后替换（spec §14 第 29 项）"),
        _c(f'  reviewed_at: "{REVIEWED_AT}"', "固定日期字面量，不是 date.today()"),
        _c("microcycle_weeks: 4", "spec §7.2 :464"),
        _c(f"weekly_frequency: {freq}", "红 4 / 黄 3 / 绿 2（指导文件原文，spec §7.2 :465）"),
        "sessions:",
    ]
    for day in range(1, freq + 1):
        body.append(f"  - day: {day}")
        body.append(f"    focus: {focus}")
        body.append("    blocks:")
        for index, (ref, impact, intensity, structure) in enumerate(blocks):
            body.append(f"      - exercise_ref: {ref}")
            if index == 0:
                body.append(_c(f"        impact_level: {impact}",
                               "供安全后置处理识别；必须与 exercises.yaml 逐字相同（P2-B2）",
                               width=36))
            else:
                body.append(f"        impact_level: {impact}")
            body.append(f"        intensity: {intensity}")
            if index == 0:
                body.append(_c(f"        structure: {structure}",
                               "spec §7.2 :473（时间型）/ :477（次数型）的字面字典",
                               width=56))
            else:
                body.append(f"        structure: {structure}")
    body.append("progression:")
    body.append(_c("  week_deltas: [1.00, 1.05, 1.10, 0.85]",
                   "第 4 周减量，超量恢复（spec §7.2 :479）", width=42))
    if addons:
        body.append("addons:")
        for when, module, note in addons:
            body.append(f"  - when: {when}")
            body.append(f"    module: {module}")
            body.append(f"    # ↑ {note}")
    else:
        body.append(_c("addons: []",
                       "⚠️ 指导文件未给绿层附加模块（见本文件头注释的最后一段）", width=13))
    return "\n".join(head) + "\n" + "\n".join(body) + "\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    serial = 0
    written = []
    for layer, layer_code, freq in LAYERS:
        for bucket, bucket_code, focus in BUCKETS:
            for body_comp, body_code in BODY:
                serial += 1
                template_id = (f"{layer_code}-{bucket_code}-{body_code}-{serial:02d}")
                text = render(template_id, serial, layer, layer_code, freq, bucket,
                              bucket_code, focus, body_comp, body_code)
                path = OUT / f"{template_id}.yaml"
                path.write_bytes(text.encode("utf-8"))
                written.append((template_id, len(path.read_bytes()),
                                path.read_bytes().count(b"\r\n")))
    for row in written:
        print("%s  bytes=%4d  CRLF=%d" % row)
    print("total files =", len(written))


if __name__ == "__main__":
    main()

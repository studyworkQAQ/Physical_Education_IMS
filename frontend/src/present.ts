/**
 * `present.ts` —— **展示口径的唯一所有者**（纯函数，无 I/O、无 Vue）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 它此前住在 `views/student/present.ts`；Plan 04 Task 3 把它搬到了 `src/present.ts`
 * ---------------------------------------------------------------------------
 * 搬的理由：它**不再是学生端专用的**。派单逐字要求「`present.ts` 是中文标签的
 * 唯一所有者，（教师端）从它 import，不要抄第二份」—— 而 RPE 的 11 档 Borg CR-10
 * 锚点、分层标签、预警规则的人话、`volume_unit` 的中文这几格，教师端**同一套**要用
 * （大屏上染 7–8 琥珀 / 9–10 砖红的阈值就来自这里的 `RPE_SCALE.tone`）。
 * 把它留在 `views/student/` 下会让教师页面写出 `../../views/student/present` 这种
 * 「跨端伸手进另一个端的目录」的 import —— 那正是「两端各有一份标签」的前一步。
 * ⚠️ 搬动只改了 6 个学生端页面的 import 路径，**一个函数都没动**。
 *
 * ---------------------------------------------------------------------------
 * 为什么会有这个文件
 * ---------------------------------------------------------------------------
 * 后端有一批**刻意只存英文 token、把中文标签留给前端**的列。最直白的一处是
 * `app/db/models/feedback.py:397-400` 的逐字注释：
 *
 *     「``feeling`` 的取值域 = spec §8.1 的「轻松 / 适中 / 吃力」三选一。
 *       存英文 token（与全库其余枚举同一口径），**中文标签由前端映射**。」
 *
 * 「由前端映射」就意味着前端是那些标签的**所有者**，而所有者只能有一个住址：
 * 6 个页面里各写一份 `feeling === 'easy' ? '轻松' : …` 的失效形态是
 * 「打卡页写『轻松』、训练单页写『自如』」，而两处各自的测试都还是绿的。
 *
 * ⚠️ 计划约束第 17 条同一族的事实：**枚举读不到契约**（`AlertHandleCreate.action`
 * 在 schema 里逐字是 `{"type":"string"}`，因为闸门是 `field_validator`）。
 * 故这里的每一个值域都是**实测**出来的（运行时读响应体 / 读后端源码的常量），
 * 并在注释里写了出处。
 *
 * ⚠️ 本文件**不含**任何设计令牌（颜色/字号在 `styles/tokens.css`），
 * 只返回「用哪个 class」「显示哪几个字」这类**语义**决定。
 *
 * ---------------------------------------------------------------------------
 * 目录：①「不知道」不得显示成 0 · ② 日期与周次 · ③ 分层标签 · ④ 预警规则 id
 *       ⑤ 打卡的 feeling · ⑥ 课堂快评的 11 档 · ⑦ 训练单的 block token
 *       ⑧ **教师端**（Task 3 加的：三档处置动作 / 预警状态 / 异常名单的理由 /
 *       教学班的分组方式 / 训练单系数那句话）
 */
import { HANDLE_ACTIONS, type HandleAction } from './api/types'

/* ==========================================================================
   ①「不知道」不得显示成「0」（计划约束第 10 条 —— 本项目最响的一条纪律）
   ========================================================================== */

/** `null` / `undefined` 一律渲染成这个破折号。
 *  ⚠️ 它是**居中的短横**（U+2014），不是减号 —— 于是不会被人读成一个负数。
 *  ⚠️ `base.css` 的 `.unknown` 是它的样式住址；本函数只给字符。 */
export const UNKNOWN = '—'

/** 一个可能是 `null` 的数 → 显示串。`null` 走 {@link UNKNOWN}，**不是** `0`。 */
export function num(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return UNKNOWN
  return value.toFixed(decimals)
}

/** ⚠️ 一个可能是 `null` 的**比率** → 百分数的**数值**（给 `StatBlock` 的 `value`）。
 *
 *  后端一律给 0–1 的小数：`completion_rate` 实测是 `0.3333` 而不是 `33.33`
 *  （`feedback.py:822` 的 `round(numerator / denominator, RATE_PRECISION)`），
 *  `shuttle_score` 是 0–100 的百分位（**已经**是百分数，不要再乘）。
 *  故 ×100 **只在这里做一次** —— 首页与打卡页各乘一次是同一件事的两个住址，
 *  而漂开的形态是「一处 33.3%、另一处 3330%」。
 *
 *  ⚠️ `null` 原样传出：`StatBlock` 会把它渲染成「—」而**不是** `0`
 *  （约束第 10 条，那一格在组件里拦，见 `StatBlock.vue` 的文件头）。 */
export function toPercent(fraction: number | null | undefined): number | null {
  if (fraction === null || fraction === undefined || Number.isNaN(fraction)) return null
  return fraction * 100
}

/** 一个可能是 `null` 的字符串 → 显示串。 */
export function text(value: string | null | undefined): string {
  return value === null || value === undefined || value === '' ? UNKNOWN : value
}

/* ==========================================================================
   ② 日期与周次
   ========================================================================== */

/** `YYYY-MM-DD` → `Date`（**按 UTC 解析**，避免东八区把日期读成前一天）。 */
function parseIso(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(y, (m ?? 1) - 1, d ?? 1))
}

/** `Date` → `YYYY-MM-DD`（同样走 UTC，与 {@link parseIso} 对称）。 */
export function toIso(date: Date): string {
  return date.toISOString().slice(0, 10)
}

/** 星期几的中文（**下标 0 = 周一**，与训练单的 `day` 同口径）。 */
const WEEKDAY_ZH = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'] as const

/** `YYYY-MM-DD` → 「周一」…「周日」。 */
export function weekdayOf(iso: string): string {
  const d = parseIso(iso)
  // getUTCDay(): 0 = 周日 → 折成 0 = 周一
  return WEEKDAY_ZH[(d.getUTCDay() + 6) % 7]
}

/** `YYYY-MM-DD` → 「10 月 06 日」。 */
export function shortDate(iso: string): string {
  const [, m, d] = iso.split('-')
  return `${Number(m)} 月 ${d} 日`
}

/**
 * 这个日期所在**学期周的周一**。
 *
 * ⚠️ 后端的周是**周一起、1-based**（`app/domain/calendar.py` 的 `semester_week_range`；
 * 实测口径：学期起点 `2025-09-01` 是周一，第 6 周 = `2025-10-06`…`2025-10-12`，
 * 而 `GET …/completion-rate?semester_id=2&week=6` 回的 `expected_days` 正是
 * `["2025-10-06","2025-10-07","2025-10-08"]` = 训练单里的 `day` 1/2/3）。
 */
export function mondayOf(iso: string): string {
  const d = parseIso(iso)
  d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7))
  return toIso(d)
}

/** 训练单里的 `day`（1 = 周一）→ 那一周的日历日期。 */
export function sheetDayToDate(monday: string, day: number): string {
  const d = parseIso(monday)
  d.setUTCDate(d.getUTCDate() + (day - 1))
  return toIso(d)
}

/** `2025-10-12T00:00:00` → `2025-10-12 00:00`（通知的 `created_at`、快评的 `submitted_at`）。 */
export function stampOf(isoDateTime: string): string {
  const [date, time] = isoDateTime.split('T')
  return `${date} ${time ? time.slice(0, 5) : ''}`.trim()
}

/* ==========================================================================
   ③ 分层标签（`stratification.label`）
   ==========================================================================
   ⚠️ 值域 = `red` / `yellow` / `green`（计划约束第 18 条：`AlertLevel` 是所有者）。
      本表把它折成 `base.css` 的 `.pill--*` 三个类名 —— ⚠️ **不写色值**，
      色值在 `tokens.css`（唯一住址）。                                            */

export type Level = 'red' | 'amber' | 'moss'

const LABEL_TO_LEVEL: Record<string, Level> = {
  red: 'red',
  yellow: 'amber',
  green: 'moss',
}

/** `label` → `.pill--*` 的那一档。⚠️ 不认识的值退回 `amber`（不是 `moss`）：
 *  把一个新出现的分层画成绿色，等于把「我不知道这是什么」讲成「一切正常」。 */
export function levelOf(label: string | null | undefined): Level {
  if (!label) return 'amber'
  return LABEL_TO_LEVEL[label] ?? 'amber'
}

const LABEL_ZH: Record<string, string> = { red: '红色层', yellow: '黄色层', green: '绿色层' }

/** `label` → 「红色层」/「黄色层」/「绿色层」。不认识的原样带出（不猜）。 */
export function labelZh(label: string | null | undefined): string {
  if (!label) return UNKNOWN
  return LABEL_ZH[label] ?? label
}

/* ==========================================================================
   ④ 预警规则 id → 一句人话
   ==========================================================================
   ⚠️ 值域实测自演示库的 `weekly_adjustment.reason`（10 行全是 `RED_RPE_SUSTAINED`
      与 `RED_MINITEST_DROP`）与 `app/domain/alerts.py:164-187` 的 `RuleId`
      （**恰好 5 个**，那个 Enum 的 docstring 逐字写了「spec §8.2 表格的 5 行」，
      且它的键集与 `alert_rules.yaml` 的 `rules:` 键集被要求**恰好相等**）。
      ⚠️ 它**不在契约里**（约束第 17 条同一族）：`WeeklySheetRead.reasons` 逐字是
      `string[]`。故认不出来的一律原样显示那个 id —— 那是可追溯性的一部分
      （spec §8.4「可追溯、可回滚」），不能翻成一句含糊的中文把它盖掉。       */

const REASON_ZH: Record<string, string> = {
  RED_MINITEST_DROP: '连续两次二次小测下降 ≥ 5%',
  RED_RPE_SUSTAINED: '课堂 RPE 连续 3 次 ≥ 9 分',
  YELLOW_CHECKIN_GAP: '连续 2 个应打卡训练日未打卡',
  YELLOW_CLASS_RPE_HIGH: '课堂 RPE 均值 > 7 分（班级）',
  GREEN_MASTERY: '本周完成度 100% 且小测有提升',
}

/** `reason` → 中文；认不出来的**原样带出**。 */
export function reasonZh(reason: string): string {
  return REASON_ZH[reason] ?? reason
}

/** `sources[i]` → 中文。⚠️ 值域实测是 `auto` 与 `teacher`
 *  （`app/domain/prescription/weekly.py:365-384` 逐字交代了这两档，
 *  并说明 `teacher` 今天**没有生产写入方**、只在测试里可达）。 */
export function sourceZh(source: string): string {
  if (source === 'auto') return '系统自动（红色预警触发）'
  if (source === 'teacher') return '教师手工调整'
  return source
}

/* ==========================================================================
   ⑤ 打卡的 `feeling`（spec §8.1 的三选一）
   ==========================================================================
   ⚠️ 值域的所有者是 `TrainingLog.FEELINGS = {"easy", "moderate", "hard"}`
      （DB 上有 CHECK），中文标签由前端映射（见那个模型 397-400 行的逐字注释）。 */

export interface FeelingOption {
  readonly value: 'easy' | 'moderate' | 'hard'
  readonly zh: string
  readonly caps: string
  readonly hint: string
}

export const FEELINGS: readonly FeelingOption[] = [
  { value: 'easy', zh: '轻松', caps: 'EASY', hint: '做完还能再聊两句' },
  { value: 'moderate', zh: '适中', caps: 'MODERATE', hint: '有点喘，但撑得住' },
  { value: 'hard', zh: '吃力', caps: 'HARD', hint: '最后几下是咬着牙的' },
]

export function feelingZh(value: string | null | undefined): string {
  if (!value) return UNKNOWN
  return FEELINGS.find((f) => f.value === value)?.zh ?? value
}

/* ==========================================================================
   ⑥ 课堂快评的 11 档（RPE 0–10）
   ==========================================================================
   ⚠️⚠️ **标度是 0–10，不是 Borg 经典的 6–20**。这一点后端在四处逐字钉住
      （`app/domain/prescription/assembler.py:235-238` 与 `:464-467`）：
      「① `rpe_record` 表字段「RPE 0–10」；② spec §8.2 小标题「课堂端 RPE
      （0–10 主观疲劳）」；③ `RED_RPE_SUSTAINED`「RPE 连续 ≥ 9 分」；
      ④ `YELLOW_CLASS_RPE_HIGH`「课堂 RPE 均值 > 7 分」」。

   ⚠️ 而 **0–10 恰好就是 Borg 的 CR-10 标度**（6–20 那张是 1970 年的原始 RPE 表）。
      故下面 11 档的**中文锚点逐条对译 Borg CR-10 的标准语言锚点**（verbal anchors：
      Nothing at all / Extremely weak / Very weak / Weak / Somewhat weak /
      Moderate / Somewhat strong / Strong / Very strong / Extremely strong / Maximal），
      **不是自己另编一套** —— 自编的失效形态是「学生按自己的话理解 7 分」，
      于是同一个 7 分在两个班里不是一个意思，而 `YELLOW_CLASS_RPE_HIGH` 的
      「均值 > 7」就失去了可比性。

   ⚠️ `tone` 那两档（9 与 10 是 `red`、7 与 8 是 `amber`）**取自后端的两条规则**，
      不是我挑的颜色：`RED_RPE_SUSTAINED` 是「连续 ≥ 9」、`YELLOW_CLASS_RPE_HIGH`
      是「均值 > 7」。故按钮上那一格提示与教师端看到的预警**同一套阈值**。        */

export interface RpeStep {
  readonly rpe: number
  /** 中文锚点（Borg CR-10 的对译）。 */
  readonly zh: string
  /** Borg CR-10 的英文原文（给要核对量表的人看）。 */
  readonly en: string
  /** 这一档会不会触发预警（用于按钮上的极小提示）。 */
  readonly tone: 'calm' | 'amber' | 'red'
}

export const RPE_SCALE: readonly RpeStep[] = [
  { rpe: 0, zh: '毫无感觉', en: 'Nothing at all', tone: 'calm' },
  { rpe: 1, zh: '极其轻松', en: 'Extremely weak', tone: 'calm' },
  { rpe: 2, zh: '非常轻松', en: 'Very weak', tone: 'calm' },
  { rpe: 3, zh: '比较轻松', en: 'Weak', tone: 'calm' },
  { rpe: 4, zh: '略微轻松', en: 'Somewhat weak', tone: 'calm' },
  { rpe: 5, zh: '适中', en: 'Moderate', tone: 'calm' },
  { rpe: 6, zh: '略微吃力', en: 'Somewhat strong', tone: 'calm' },
  { rpe: 7, zh: '比较吃力', en: 'Strong', tone: 'amber' },
  { rpe: 8, zh: '非常吃力', en: 'Very strong', tone: 'amber' },
  { rpe: 9, zh: '极其吃力', en: 'Extremely strong', tone: 'red' },
  { rpe: 10, zh: '力竭极限', en: 'Maximal', tone: 'red' },
]

export function rpeZh(rpe: number | null | undefined): string {
  if (rpe === null || rpe === undefined) return UNKNOWN
  return RPE_SCALE.find((s) => s.rpe === rpe)?.zh ?? String(rpe)
}

/* ==========================================================================
   ⑦ 训练单的 block 上的几个 token
   ========================================================================== */

/** `impact_level` 的实测值域 = `high` / `medium` / `low`
 *  （`AssembledBlockRead.impact_level`；演示库里三档都有）。 */
export function impactZh(value: string): string {
  if (value === 'high') return '高冲击'
  if (value === 'medium') return '中冲击'
  if (value === 'low') return '低冲击'
  return value
}

/** ⚠️ `volume_unit` 的实测值域 = `min` / `reps` / `unspecified`，而
 *  `prescription_stage.py:411-417` 逐字交代了「**刻意不加任何跨单位的周总量
 *  汇总字段**……把它们相加就是混合量纲的错误 —— 48 分钟 + 120 次 = 168 什么？」
 *  故前端**按单位分列**显示，本函数只给单位的中文。 */
export function volumeUnitZh(unit: string): string {
  if (unit === 'min') return '分钟'
  if (unit === 'reps') return '次'
  if (unit === 'unspecified') return '未指定'
  return unit
}

/** 通知的 `channel`（实测演示库里只有 `in_app` 一个值；spec §8.3 逐字「原型不做真实推送」）。 */
export function channelZh(channel: string): string {
  if (channel === 'in_app') return '站内消息'
  return channel
}

/* ==========================================================================
   ⑧ 教师端（Plan 04 Task 3 加的）
   ==========================================================================
   ⚠️ 这一节与学生端那七节**同一个纪律**：值域一律实测出来（读响应体 / 读后端常量），
      中文标签住在这里、色值住在 `tokens.css`、三档动作的**字面值**住在
      `api/types.ts` 的 `HANDLE_ACTIONS`（它是值的唯一所有者，本节只拥有标签与顺序）。 */

/* ------------------------------------------------- ⑧-1 三档处置动作
   ⚠️ 计划约束第 17 条 + Task 1 顶回 4：三档**读不到契约**
   （`AlertHandleCreate.action` 在 OpenAPI 里逐字是 `{"type":"string","title":"Action"}`，
   闸门是 `field_validator`、不进 JSON Schema）。故字面值由 `api/types.ts` 的
   `HANDLE_ACTIONS` 持有（后端 `app/api/schemas/alerts.py:79` 的 `HANDLE_ACTIONS`
   是它的上游所有者），本节把「按什么顺序出三个按钮」与「每一档叫什么、点了会发生什么」
   收在这里 —— 预警队列与大屏两处都从这个数组渲染，故顺序不会漂。
   ⚠️ `Record<HandleAction, …>` 是**编译期的穷尽性守卫**：后端加第四档时
   `HANDLE_ACTIONS` 一改，这里不跟着加就 `vue-tsc` 当场报错。                  */

export interface HandleActionOption {
  /** 送进请求体的字面值（`reduce_20pct` / `ignore` / `note`）。 */
  readonly value: HandleAction
  /** 按钮上的中文。 */
  readonly zh: string
  /** 按钮上的拉丁小标题（计时牌的「项目代码」）。 */
  readonly caps: string
  /** 一句「点下去会发生什么」。**它不是装饰**：三档的副作用差别很大，
   *  而 `note` 那一档**处置后仍是 pending**（备注不是处置）。 */
  readonly hint: string
  /** 这一档要不要填备注（`note` 为空 → 422 `unprocessable_value`）。 */
  readonly needsNote: boolean
  /** 按钮的语义色（`.btn--*` 那一档，不写色值）。 */
  readonly tone: 'red' | 'default' | 'amber'
}

const ACTION_ZH: Record<HandleAction, string> = {
  reduce_20pct: '减量 20%',
  ignore: '忽略',
  note: '记一笔备注',
}

const ACTION_CAPS: Record<HandleAction, string> = {
  reduce_20pct: 'REDUCE 20%',
  ignore: 'IGNORE',
  note: 'NOTE',
}

const ACTION_HINT: Record<HandleAction, string> = {
  reduce_20pct:
    '写一条 weekly_adjustment（source=auto、factor=0.8）+ 推一条站内消息给学生。' +
    '⚠️ 一处方一周至多一条 auto 调整：那一周已经减过时响应里 adjustment 是 null、' +
    '本次不再减（HTTP 仍是 200、status 仍变 handled）。',
  ignore: '只把 status 改成 ignored。不发消息、不动训练量。',
  note: '只写 handled_action 一列，⚠️ status **保持 pending**（备注不是处置），' +
    '故可以连着记多条。备注为空 → 422 unprocessable_value。',
}

/** 三个按钮的**顺序**：减量在最前（它是 spec §8.4 逐字要求的那一条主路径）。 */
export const HANDLE_ACTION_OPTIONS: readonly HandleActionOption[] = [
  {
    value: HANDLE_ACTIONS.reduce,
    zh: ACTION_ZH[HANDLE_ACTIONS.reduce],
    caps: ACTION_CAPS[HANDLE_ACTIONS.reduce],
    hint: ACTION_HINT[HANDLE_ACTIONS.reduce],
    needsNote: false,
    tone: 'red',
  },
  {
    value: HANDLE_ACTIONS.note,
    zh: ACTION_ZH[HANDLE_ACTIONS.note],
    caps: ACTION_CAPS[HANDLE_ACTIONS.note],
    hint: ACTION_HINT[HANDLE_ACTIONS.note],
    needsNote: true,
    tone: 'amber',
  },
  {
    value: HANDLE_ACTIONS.ignore,
    zh: ACTION_ZH[HANDLE_ACTIONS.ignore],
    caps: ACTION_CAPS[HANDLE_ACTIONS.ignore],
    hint: ACTION_HINT[HANDLE_ACTIONS.ignore],
    needsNote: false,
    tone: 'default',
  },
]

/** `alert.handled_action` → 中文。
 *
 *  ⚠️ 那一列存的**不只是**动作：后端 `app/api/routers/alerts.py` 逐字是
 *  `row.handled_action = f"{action}: {note}" if note else action`（`ignore` 那一档），
 *  而 `note` 那一档存的是**裸备注**。故本函数要认三种形状：
 *   1. 裸动作（`"reduce_20pct"`）→ 「减量 20%」；
 *   2. `"动作: 备注"` → 「减量 20%：备注」（⚠️ 只切**第一个** `": "`，
 *      因为备注自己可以含冒号）；
 *   3. 认不出来的（例如 `note` 那一档存的一句人话）→ **原样带出**
 *      （那是可追溯性的一部分，不能翻成一句含糊的中文把它盖掉）。
 */
export function actionZh(action: string | null | undefined): string {
  if (!action) return UNKNOWN
  const direct = ACTION_ZH[action as HandleAction]
  if (direct) return direct
  const cut = action.indexOf(': ')
  if (cut > 0) {
    const head = ACTION_ZH[action.slice(0, cut) as HandleAction]
    if (head) return `${head}：${action.slice(cut + 2)}`
  }
  return action
}

/* ------------------------------------------------- ⑧-2 预警的 status
   ⚠️ 值域 = `pending` / `handled` / `ignored`（计划约束第 18 条：`AlertLevel` 是
      `level` 的所有者、`Alert.STATUSSES` 是 `status` 的 DB 镜像）。
      ⚠️ `note` 那一档处置后**仍是 pending**，故「pending」不等于「没人看过」——
      `handled_action` 非空而 `status` 仍 pending 就是「记了备注、还没处置完」。   */

const ALERT_STATUS_ZH: Record<string, string> = {
  pending: '待处理',
  handled: '已处理',
  ignored: '已忽略',
}

export function alertStatusZh(status: string | null | undefined): string {
  if (!status) return UNKNOWN
  return ALERT_STATUS_ZH[status] ?? status
}

/** `level` → `.pill--*` 的那一档。⚠️ **复用**学生端 ③ 的 {@link levelOf}：
 *  `alert.level` 与 `stratification.label` 是**同一套词表**（`red` / `yellow` / `green`，
 *  所有者是 `app/domain/alerts.py` 的 `AlertLevel`，`Alert.LEVELS` 是它的 DB 镜像），
 *  故两处必须是同一个映射 —— 大屏上「红色层」与「红色预警」若染成两个红，
 *  教师就会以为它们是两件事。 */
export function alertLevelZh(level: string | null | undefined): string {
  if (!level) return UNKNOWN
  return LABEL_ZH[level] ?? `${level} 级`
}

/* ------------------------------------------------- ⑧-3 大屏异常名单的 reasons
   ⚠️ 值域实测自 `GET /api/dashboard/class/{id}` 的 `blocks.abnormal_roster[i].reasons`
      （演示库里两个值：`rpe_high` / `checkin_gap`）。它们的**阈值不在这里**：
      响应体另给了 `screen_thresholds = {gap_days: 3, rpe_max: 8}`，
      而那一格的所有者是 `app/domain/report.py` 的 `SCREEN_GAP_DAYS` / `SCREEN_RPE_MAX`。
      ⚠️ 计划约束（dashboard.py 的 docstring 逐字）：`screen_thresholds`（大屏异常名单的
      筛选阈值）与 `rpe_threshold_lines`（7 / 9，预警的判据线）是**两套并存**的东西，
      前端**不得**拿一个去画另一个。                                          */

const ABNORMAL_REASON_ZH: Record<string, string> = {
  rpe_high: '课堂 RPE 偏高',
  checkin_gap: '连续多天未打卡',
}

export function abnormalReasonZh(reason: string): string {
  return ABNORMAL_REASON_ZH[reason] ?? reason
}

/* ------------------------------------------------- ⑧-4 教学班的分组方式
   ⚠️ 值域实测自 `GET /api/course-sections`（演示库 5 个班：2 个 `administrative`
      + 3 个 `stratified`）。spec §6.2 的两阶段：阶段一按行政班、阶段二分层走班。 */

export function groupingModeZh(mode: string | null | undefined): string {
  if (mode === 'administrative') return '行政班（阶段一）'
  if (mode === 'stratified') return '分层走班（阶段二）'
  if (!mode) return UNKNOWN
  return mode
}

/* ------------------------------------------------- ⑧-5 分层的四个键
   ⚠️ `layer_distribution.by_layer` / `checkin_rate_by_layer` 的键**恰好四个**：
      `red` / `yellow` / `green` / `insufficient_data`（实测演示库：
      `{"red": 3, "yellow": 17, "green": 10, "insufficient_data": 0}`）。
      第四档不是分层结果、是「数据不足以分层」，故它的语义色是**中性**的
      （不染红/黄/绿 —— 把「我不知道」染成任何一种颜色都是撒谎）。
      ⚠️ 顺序是**固定的**（红→黄→绿→数据不足），于是大屏的环形图与周报的
      完成率条两块读出来是同一个序。                                          */

export interface LayerSlot {
  readonly key: 'red' | 'yellow' | 'green' | 'insufficient_data'
  readonly zh: string
  /** `.pill--*` / `.layer--*` 的那一档。`insufficient_data` 是 `default`（中性）。 */
  readonly level: Level | 'default'
}

export const LAYER_SLOTS: readonly LayerSlot[] = [
  { key: 'red', zh: '红色层', level: 'red' },
  { key: 'yellow', zh: '黄色层', level: 'amber' },
  { key: 'green', zh: '绿色层', level: 'moss' },
  { key: 'insufficient_data', zh: '数据不足', level: 'default' },
]

/* ------------------------------------------------- ⑧-6 训练单系数那句话
   ⚠️ 计划约束第 13 条逐字要求的那一句：「本周减量 20%（由 2 条红色预警触发）」。
      它此前住在 `WeeklySheet.vue` 的一个 `computed` 里；教师端的「学生详情」
      要显示**同一句**（教师看的就是学生将看到的那个量），故搬到这里 ——
      两个端各写一份的失效形态是「学生端说减了 20%、教师端说减了 36%」。
      ⚠️ 算式**不在这里**：`factor` 是后端 `weekly_training_sheet` 给的
      （骨架 × 本周全部微调的**累乘**），本函数只把它翻成一句人话。        */

/** 一张训练单（学生侧与教师侧两个端点的响应体**逐字相同**，故一个类型够用）。 */
export interface SheetLike {
  readonly factor: number
  readonly reasons: readonly string[]
  readonly sources: readonly string[]
}

/** `sources` 里 `auto` 的条数 = 「由几条红色预警触发」。 */
export function autoCountOf(sheet: SheetLike): number {
  return sheet.sources.filter((src) => src === 'auto').length
}

/** 「本周减量 20%（由 2 条红色预警触发 + 1 条教师手工调整）」那一句话。 */
export function factorSentenceOf(sheet: SheetLike): string {
  const delta = Math.round(Math.abs(1 - sheet.factor) * 100)
  if (sheet.reasons.length === 0 || delta === 0) {
    return `本周不调整（系数 ${sheet.factor.toFixed(2)}）`
  }
  const verb = sheet.factor < 1 ? '减量' : '加量'
  const auto = autoCountOf(sheet)
  const teacher = sheet.sources.length - auto
  const parts: string[] = []
  if (auto > 0) parts.push(`${auto} 条红色预警触发`)
  if (teacher > 0) parts.push(`${teacher} 条教师手工调整`)
  const by = parts.length > 0 ? `（由 ${parts.join(' + ')}）` : ''
  return `本周${verb} ${delta}%${by}`
}

/** `factor` → 语义色（`< 1` 砖红 / `> 1` 苔绿 / `= 1` 中性）。 */
export function factorToneOf(factor: number | null | undefined): 'default' | 'red' | 'moss' {
  if (factor === null || factor === undefined) return 'default'
  if (factor < 1) return 'red'
  if (factor > 1) return 'moss'
  return 'default'
}

/* ------------------------------------------------- ⑧-7 RPE 的语义色
   ⚠️ 阈值**取自后端两条规则**（不是挑的颜色）：`YELLOW_CLASS_RPE_HIGH` 是
      「班级均值 > 7」、`RED_RPE_SUSTAINED` 是「连续 ≥ 9」。⑥ 的 `RPE_SCALE[i].tone`
      已经把它们钉在了 11 档上，本函数是同一个映射在「一个任意的均值」上的推广
      （大屏的 `rpe_summary.mean` 是 6.37 这样的小数，落不到 11 档里的任何一格）。
      ⚠️ 于是教师端与学生端**同一套锚点、同一套阈值**，这是派单逐字要求的。   */

export function rpeToneOf(mean: number | null | undefined): 'default' | 'amber' | 'red' {
  if (mean === null || mean === undefined || Number.isNaN(mean)) return 'default'
  if (mean >= 9) return 'red'
  if (mean > 7) return 'amber'
  return 'default'
}

/** 一句给人看的 RPE 锚点（`6.4` → 「略微吃力」那一档的中文，取**下整**的那一格）。
 *  ⚠️ 它只用来说「这个均值大概落在量表的哪一格」，故取 floor 而不是四舍五入：
 *  把 6.9 说成「比较吃力」（7 那一格）会让人以为已经越过了 `> 7` 那条阈值线。 */
export function rpeAnchorOf(mean: number | null | undefined): string {
  if (mean === null || mean === undefined || Number.isNaN(mean)) return UNKNOWN
  const step = RPE_SCALE[Math.min(RPE_SCALE.length - 1, Math.max(0, Math.floor(mean)))]
  return step ? step.zh : UNKNOWN
}

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
 *       ⑨ **管理台**（Task 4 加的：列名的中文标签 / 单元格的显示串 / 删除策略三档）
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

/** `2026-10-14T13:16:58.788453` → `2026-10-14 13:16:58`（**秒级**；审计留痕的 `at`）。
 *
 *  ⚠️ 与 :func:`stampOf` 的差别**只在切到第几格**：那一个切到分钟（通知 / 快评够了），
 *  本个切到秒。⚠️ 而审计页**必须**要秒：`audit_log` 按 `id DESC` 排，而「一次登录 +
 *  紧接着一次写」可以落在同一分钟里，两行显示成同一个时刻会让人以为「记重了」
 *  （那正是审计页最不该引起的一种怀疑）。⚠️ 于是它不是 `stampOf` 的替代品、
 *  是它的**兄弟**：两者各自的服务对象不同，故两个都留着。
 *  ⚠️⚠️ 两者都**只切串、不建 `Date`**：本仓的 `DateTime` 列存 **naive 本地时刻**
 *  （后端 `app.config.TIMEZONE`，序列化成 `2025-10-12T09:30:00` 而**不带** `Z` 后缀），
 *  故任何时区换算都是错的（差 8 小时）。⚠️ 而「无 `Z` 的 date-time 串」在 ES2016+ 的
 *  `new Date(...)` 里按**浏览器本地时区**解释 —— 于是同一个后端值在两个时区的浏览器上
 *  会显示成两个时刻，而它本该是「后端存的那一串本地时刻原样」。
 *  那一格是后端 `app/api/schemas/audit.py` 的 `AuditLogRead` docstring 逐字记过的顶回。 */
export function stampSecondsOf(isoDateTime: string): string {
  const [date, time] = isoDateTime.split('T')
  return `${date} ${time ? time.slice(0, 8) : ''}`.trim()
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

/* ==========================================================================
   ⑨ **管理台**（Task 4 加的：列名的中文标签 / 单元格的显示串 / 删除策略的三档）
   ==========================================================================
   ⚠️ 派单让 present.ts「加 23 个资源的中文标题」—— **这一格没有做**，
   因为它已经有住址了：`catalog/resources.ts` 那 23 行的 `titleZh`
   （Task 1 建目录时就写全了 23/23）。再抄一份到这里的失效形态是
   「目录页显示『课堂课次』、列表页显示『课次』」，而两处各自都还是对的。
   故本节加的是 present.ts **真正缺**的那一格：

   **列名 → 中文标签**。管理台是一套通用组件渲染 23 个资源，它拿到的只有
   列名（`course_section_id` / `body_comp_abnormal` / …）。而本仓的表头一律是
   中文（`views/teacher/*.vue` 的 `<th>` 逐个是「等级」「周次」「动作」），
   故这一份映射是它唯一的住址。

   ⚠️ **141 个键**，是实测出来的、不是猜的（硬规矩 #89：运行时口径）：
   122 个 = 23 个资源的 list 项列名的**并集**（后端 `crud._json_text_columns`
   与 `model.__table__.columns` 现算出来的 `kept`，共 194 个槽位、122 个不同名），
   + 19 个 = 8 个资源被 list 排掉的那些 `JsonText` 列（详情页会显示它们）。
   ⚠️ **认不出来的列名一律原样返回**（`fieldLabelZh` 的兜底），**不返回空串**：
   后端加一列时管理台会显示一个英文列名（看得出是新的），
   而空表头会让人以为这一列坏了。                                              */

const FIELD_LABELS: Record<string, string> = {
  /* ---- 通用 ---- */
  id: 'id',
  batch_id: '批处理 id',
  created_at: '创建时刻',
  source: '来源',
  version: '版本',
  status: '状态',
  reason: '理由',
  week: '周次',
  name: '名称',

  /* ---- 组织与身份（spec §4.1）---- */
  semester_id: '学期 id',
  start_date: '开始日',
  end_date: '结束日',
  weeks: '总周数',
  is_current: '当前学期',
  staff_no: '教师工号',
  teacher_id: '教师 id',
  student_id: '学生 id',
  student_no: '学号',
  sex: '性别',
  birth: '出生日期',
  department: '院系',
  grade: '年级',
  course_section_id: '教学班 id',
  schedule_text: '上课时间（文字）',
  grouping_mode: '分组方式',

  /* ---- 体测（spec §4.2）---- */
  test_batch_id: '体测批次 id',
  timepoint: '体测时点',
  test_date: '体测日期',
  academic_year: '学年',
  tested_on: '测试日',
  height_cm: '身高（cm）',
  weight_kg: '体重（kg）',
  vital_capacity_ml: '肺活量（mL）',
  sprint_50m_s: '50 米跑（秒）',
  sit_and_reach_cm: '坐位体前屈（cm）',
  standing_jump_cm: '立定跳远（cm）',
  strength_count: '引体向上/仰卧起坐（次）',
  distance_run_s: '耐力跑（秒）',
  score_bmi: '得分 · BMI',
  score_vital_capacity: '得分 · 肺活量',
  score_sprint_50m: '得分 · 50 米跑',
  score_sit_and_reach: '得分 · 坐位体前屈',
  score_standing_jump: '得分 · 立定跳远',
  score_pull_up_or_sit_up: '得分 · 引体/仰卧',
  score_distance_run: '得分 · 耐力跑',
  total_score: '总分',
  national_grade: '国标等级',
  measured_on: '测量日',
  muscle_mass_kg: '肌肉量（kg）',
  body_fat_pct: '体脂率（%）',
  smi: '骨骼肌指数 SMI',
  device: '测量设备',
  filled_on: '填写日',
  dimensions: '维度得分（JSON）',
  raw_answers: '原始作答（JSON）',

  /* ---- 百分位与派生（spec §4.3）---- */
  computed_on: '计算日',
  item: '体测项目',
  age_group: '年龄段',
  p10: 'P10',
  p20: 'P20',
  p25: 'P25',
  p50: 'P50（中位）',
  p75: 'P75',
  sample_size: '样本量',
  trend: '年度趋势',
  weakness_count: '短板项数',
  valid_count: '有效项数',
  body_comp_abnormal: '体成分异常',
  annual_change: '年度变化（JSON）',
  weaknesses: '短板清单（JSON）',
  body_comp_reasons: '体成分异常的理由（JSON）',
  label: '分层标签',
  hit_rules: '命中的规则',
  percentile_source: '百分位判定线来源',
  valid_from: '生效起',
  valid_to: '生效止',
  input_snapshot: '输入快照（JSON）',

  /* ---- 处方（spec §4.4）---- */
  ref: '动作 ref',
  video_url: '示范视频',
  impact_level: '冲击等级',
  equipment: '器械',
  targets: '目标肌群/能力（JSON）',
  layer: '分层',
  weakness: '短板',
  body_comp: '体成分档',
  template_ref: '模板 ref',
  review_status: '评审状态',
  reviewer: '评审人',
  reviewed_at: '评审日',
  reachable: '该维度组合可达',
  generated_on: '生成日',
  generated_at: '生成时刻',
  microcycle_weeks: '微周期（周）',
  label_at_generation: '生成时的分层标签',
  previous_had_overrides: '上一张有教师覆盖',
  training_package: '训练包（JSON）',
  assembly_snapshot: '装配快照（JSON）',
  safety_substitutions: '安全替换（JSON）',
  teacher_overrides: '教师覆盖（JSON）',
  trigger_reasons: '触发理由（JSON）',
  prescription_id: '处方 id',
  factor: '训练量系数',

  /* ---- 反馈三源（spec §4.5）---- */
  session_date: '上课日',
  period: '节次',
  rpe_opened: '已发起课堂快评',
  class_session_id: '课堂课次 id',
  rpe: 'RPE（0–10）',
  submitted_at: '提交时刻',
  elapsed_seconds: '提交耗时（秒）',
  log_date: '打卡日',
  completed: '已完成',
  duration_min: '时长（分钟）',
  feeling: '主观感受',
  is_rest_day: '休息日',
  late: '迟交',
  squat_30s_count: '30 秒深蹲（次）',
  shuttle_20m_s: '20 米折返（秒）',
  normalized_score: '标准化得分',
  item_combo: '项目组合（JSON）',
  entered_by: '录入人工号',

  /* ---- 预警与通知（spec §4.6）---- */
  rule_id: '规则 id',
  level: '等级',
  subject_key: '主体键',
  window_key: '去重窗口键',
  triggered_at: '触发时刻',
  handled_action: '处置动作',
  handled_at: '处置时刻',
  trigger_snapshot: '触发快照（JSON）',
  alert_id: '预警 id',
  recipient_kind: '收件人类型',
  recipient_id: '收件人 id',
  channel: '推送渠道',
  title: '标题',
  body: '正文',
  is_read: '已读',

  /* ---- 班级周报（spec §4.7）---- */
  suggestion: '给教师的一句话',
  layer_distribution: '分层分布（JSON）',
  rpe_summary: 'RPE 汇总（JSON）',
  checkin_rate_by_layer: '三层完成率（JSON）',
  progress_board: '进步榜（JSON）',
  alert_summary: '预警汇总（JSON）',
}

/** 列名 → 中文标签。⚠️ **认不出来就原样返回列名**（不是空串，理由见上面那段）。 */
export function fieldLabelZh(field: string): string {
  return FIELD_LABELS[field] ?? field
}

/** 已标签的列名总数。⚠️ 给管理台页脚那句「本台认得 N 个列名」用 ——
 *  它是「后端加了一列而前端没跟上」这件事在 UI 上唯一的可见痕迹。 */
export const FIELD_LABEL_COUNT = Object.keys(FIELD_LABELS).length

/** `true` / `false` → 「是」/「否」。⚠️ **`null` 不走这里**（它是「不知道」，
 *  显示成「否」就是把一个未知说成一个否定 —— 约束第 10 条的同族失效）。 */
export function boolZh(value: boolean): string {
  return value ? '是' : '否'
}

/**
 * 一个任意的列值 → 表格里该显示的串。
 *
 * ⚠️ 四档，每一档都对应一个真实的失效形态：
 *  - `null` / `undefined` → **{@link UNKNOWN}**（约束第 10 条：不得显示成 `0`，
 *    也不得显示成空白 —— 空白与「这一格是空的」在表格里长得一样）；
 *  - `boolean` → 「是」/「否」（`false` 显示成空白是数据表最经典的坑）；
 *  - 对象 / 数组 → **一行压缩的 JSON**（详情页的 `JsonText` 列有 5 个是嵌套结构，
 *    `[object Object]` 与 `Array(3)` 都没有信息量）；
 *  - 其余 → `String(value)`。
 *
 * ⚠️ 它**不做**任何语义加工（不判 `level === 'red'` 就染色、不把 `0.8` 说成
 * 「减量 20%」）：管理台是**运维视角**，它要的是库里那一格**逐字**是什么。
 * 语义化的那一份住在学生端与教师端的页面里（它们才该说人话）。
 */
export function cellText(value: unknown): string {
  if (value === null || value === undefined) return UNKNOWN
  if (typeof value === 'boolean') return boolZh(value)
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

/** `on_delete` 的三档 → 中文。⚠️ 值域与 `catalog/resources.ts` 的 `OnDelete`
 *  同源（后端 `app/api/crud.py` 的三个常量）。 */
export function onDeleteZh(onDelete: string): string {
  if (onDelete === 'restrict') return '限制删除（有子行就删不掉）'
  if (onDelete === 'forbid') return '禁止删除（没有 DELETE 端点）'
  if (onDelete === 'cascade') return '级联删除（连带删掉子行）'
  return onDelete
}


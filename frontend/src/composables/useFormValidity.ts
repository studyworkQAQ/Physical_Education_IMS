/**
 * `composables/useFormValidity.ts` —— **浏览器原生校验拦下一次提交时，让用户看得见**
 * （Plan 07 Task 5b 缺陷 ① 的病灶那一半；本仓那件事的**单一所有者**）。
 *
 * ---------------------------------------------------------------------------
 * 为什么会有这个文件
 * ---------------------------------------------------------------------------
 * 一个 `<form>` 里只要有一格不满足原生约束（`required` / `step` / `min` / `pattern` …），
 * 点提交就**不会**触发 `submit` 事件 —— 浏览器自己把它拦下来。本仓此前**没有任何一处**
 * 处置那一档，于是失效方向是**完全静默**的：页面不报错、不打日志、一个请求都不发，
 * 用户只看到「点了没反应」。
 *
 * ⚠️ 2026-10-15 甲方试用路线上的实测取证（真鼠标点击 `Input.dispatchMouseEvent` + CDP）：
 *    `/s/check-in` 的 `duration_min` 被 `CheckIn.vue` 的一个 `watch` 预填成库里那一位
 *    小数的真值（学生 4 的 2025-10-12 那一行是 `30.9`），而那个
 *    `<input type="number" step="0.5">` 因此 `validity.stepMismatch === true`
 *    ⇒ `form.checkValidity() === false` ⇒ 点了「提交打卡」之后
 *    **`POST /api/training-logs` 一个都没发出去**（同屏 11 个 `/api` 请求，点击前后逐字
 *    相同），而页面上一个字都没多（无成功印章、无 `.s-notice`、无横幅、无 `[role=alert]`）。
 *    ⚠️ 而它**不是**一个边角案例：演示库 840 行 `training_log` 里 `duration_min` 非空的
 *    628 行，小数位数实测是「1 位 565 行 / 0 位 63 行」，327 个 distinct 值里
 *    **258 个不是 0.5 的整数倍** ⇒ 任何学生选任何一天都大概率撞上。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 它修的**不是** `step` 那一格
 * ---------------------------------------------------------------------------
 * `step` 改对了只让「今天不撞」（那一格的所有权争议逐字写在 `CheckIn.vue` 那个
 * `<input>` 上方）。本文件修的是**失效方向**：原生校验拦下提交时，用户必须看得见
 * 一句人话 —— **哪个字段**、**为什么**、**该怎么改**，以及「**本次没有发出任何请求**」。
 * 判据（控制者裁定，逐字）：**校验失败永远不许静默**。
 *
 * ---------------------------------------------------------------------------
 * 挂钩点为什么是 `invalid` 事件（而不是 `submit`）
 * ---------------------------------------------------------------------------
 * `submit` 在校验失败时**根本不触发**，故它没法用来报「校验失败了」。
 * HTML 规范给的另一件事是 **`invalid`** 事件：交互式校验对每一个「候选且不合格」的
 * 可校验元素各触发一次。⚠️ 它**不冒泡**，故监听器要挂在那个 `<form>` 上并开**捕获**
 * （第三个实参 `true`）：捕获阶段自上而下经过 form，于是 form 上的监听器收得到
 * 后代元素那一次。⚠️ 一次点击可能触发多次（多格都不合格），故按元素去重，
 * 并同时给出**总数**与**第一格**（浏览器聚焦的也是第一格）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 「为什么」那一格**读浏览器的 `validationMessage`**，本文件不重算
 * ---------------------------------------------------------------------------
 * `stepMismatch` 的合法值算术（Chrome 中文版本实测原文：「请输入一个有效的值。
 * 最接近的两个有效值为 30.5 和 31。」）由浏览器按 HTML 规范算，且**已经本地化**。
 * 本文件再算一遍就是那套算术的**第二个所有者**（改一处漏一处，而漏掉的那一处
 * 正印在用户眼前）。故本文件只负责三件浏览器不管的事：
 *   ① 给那一格一个**人能认出来的名字** —— 浏览器的气泡指着输入框，而一屏上有六个框时
 *      「哪个字段」要靠 label 的文本（`el.labels`，HTML 规范给的那一格）；
 *   ② 一句**下一步** —— 气泡不说「改完再点一次提交」；
 *   ③ 一句**「本次没有发出任何请求」** —— 这是本缺陷最贵的一格：不说它，用户会以为
 *      「卡打出去了、只是页面没反应」，而打卡完成率是 spec §8.1 逐字点名的
 *      「RCT 关键过程指标」。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 它**刻意不引入任何新 CSS**、也**刻意不画**任何东西
 * ---------------------------------------------------------------------------
 * 本文件只产出**文本**（`title` + `body` 两格），画它的责任在调用方，而调用方一律用
 * **它自己那一端既有的错误态类**（学生端 `.s-notice .s-notice--warn`、鉴权页
 * `.auth__advice`）。理由与 `App.vue` 的 `.trial-note` 那段注释逐字同一条：
 * `.s-` / `.t-` / `.a-` 三个前缀是**端**的口径，一个跨端的模块挑一个前缀用
 * 就是第二个所有者；而让每页用自己的类，`npm run check:tokens` 一格都不退。
 * ⚠️ 也**刻意不用** `alert()`：它打断试用、且在无头取证里读不到（`scripts/smoke.mjs`
 *    第 14 步量的是渲染后的 DOM 文本）。同理「只 `console.error`」等于没修 ——
 *    甲方不开 devtools。
 *
 * ---------------------------------------------------------------------------
 * 用法（三个调用点，各两行）
 * ---------------------------------------------------------------------------
 *     const { notice: formNotice, bind: bindForm, clear: clearFormNotice } = useFormValidity()
 *     <form :ref="bindForm" @submit.prevent="submit"> … </form>
 *     <p v-if="formNotice" class="…" role="alert">{{ formNotice.title }} {{ formNotice.body }}</p>
 *
 * ⚠️ 今天挂了它的三张表单 = 本仓**全部**带原生约束的表单（`required` / `step` / `min`）：
 *    `views/student/CheckIn.vue`、`views/auth/Login.vue`、`views/auth/Bind.vue`。
 *    另外三张（`views/student/RpeEntry.vue` 与管理台那两张契约驱动的表单）**一格原生
 *    约束都没有**（RPE 页的提交按钮是 `:disabled="!canSubmit"`；管理台把 number 一律
 *    画成 `type="text"` 再由 `api/contract.ts` 的 `assembleBody` 自己报错），
 *    故挂上去是一条**恒不触发**的死路径（硬规矩 #50）。
 *    ⚠️ 「新加一张带约束的表单时不许漏挂」由 `scripts/smoke.mjs` 第 17 步的
 *    §FormValidity 那一拍钉住：它扫**整个 `src/`** 下的 `.vue`（⚠️ 含 `components/`），
 *    凡是 `<form>` 里出现原生约束属性的文件，必须同时出现 `useFormValidity`。
 *    ⚠️ 改前本处逐字写着「扫全部 `src/views/`」，而那一拍**实际**扫的是全 `src/`
 *    —— 同组只有第 ⑤ 拍（模板里不许出现 `step="<数字>"`）真的只走 `views/`，
 *    于是终审照着本处把它读成了「整个 §FormValidity 只扫 views/」（S4-8）。
 *    Plan 07 Task 8 把第 ⑤ 拍也放宽到全 `src/`、把本处改成与实物一致，并给两拍
 *    各加一条「扫描面**至少**含 N 个 `.vue`」的反空转（防的是目录改名之后
 *    守卫静默扫空 —— 硬规矩 #50：一条恒真的守卫与一条真的守卫在颜色上无法区分）。
 */
import { ref, type Ref } from 'vue'

/** 一句给用户看的处置。⚠️ 两格而不是一格：调用方既有的错误态类都是
 *  「标题 + 正文」的形状（`.s-notice__title` + `<p>`）。 */
export interface FormValidityNotice {
  readonly title: string
  readonly body: string
}

export interface UseFormValidityReturn {
  /** 当前那一句。`null` = 没拦下过，或用户已经开始改了。 */
  notice: Ref<FormValidityNotice | null>
  /** 挂到 `<form :ref="…">` 上的**函数式 ref**。⚠️ 卸载时 Vue 会用 `null` 再调一次，
   *  那一支负责摘掉监听器（不留一个指着已卸载 DOM 的闭包）。 */
  bind: (el: unknown) => void
  /** 手动清掉那一句。⚠️ 提交成功之后调它：否则「上一次没交出去」那句话会留在
   *  已经交出去了的表单上 —— 那是一句**过期**的话（本仓反复修的那一类）。 */
  clear: () => void
}

/** 不合格的那些 flag → 一句**下一步**。
 *
 *  ⚠️ 顺序是承重的：`badInput` 排第一（那一档 `el.value` 是空串，说「你填的是 X」
 *  是假话），其余按「用户最可能撞到的那一档」排。⚠️ 一个元素可以同时有几个 flag
 *  （既 `valueMissing` 又 `tooShort`），故只取**第一个**成立的那一句。
 *  ⚠️ 键集合是 HTML 规范 `ValidityState` 上那些**会**不合格的 flag（`valid` 与
 *  `customError` 除外：前者恒真、后者要有人调 `setCustomValidity`，而本仓一处都没有）。 */
const ADVICE: readonly (readonly [flag: keyof ValidityState, advice: string])[] = [
  ['badInput', '这一格里现在不是一个浏览器读得出来的值。请把它清空重填。'],
  ['valueMissing', '这一格是必填的。请填一个值再提交。'],
  ['stepMismatch', '请填一个符合那一格步长的值（步长写在那个输入框的 `step` 上）。'],
  ['rangeUnderflow', '这个值太小了。请填到那一格标注的下界（`min`）或以上。'],
  ['rangeOverflow', '这个值太大了。请填到那一格标注的上界（`max`）或以下。'],
  ['tooShort', '这一格太短了。请填到那一格标注的最少字符数（`minlength`）以上。'],
  ['tooLong', '这一格太长了。请填到那一格标注的最多字符数（`maxlength`）以下。'],
  ['patternMismatch', '这一格的格式不对（它有一个 `pattern`）。请照着那一格的提示改。'],
  ['typeMismatch', '这一格的类型不对（例如要一个日期）。请改成那一格要的形状。'],
]

/** 一格的名字，**按可靠性排**：`<label>` 的文本 > `aria-label` > `name` > `id` > 标签名。
 *
 *  ⚠️ `el.labels` 是 HTML 规范给的那一格（`HTMLLabelElement` 列表），它同时认
 *  「`<label>` 包住输入框」（`CheckIn.vue` 的形状）与「`<label for="…">` 另写一个」
 *  （`Login.vue` / `Bind.vue` 的形状）—— 故本仓今天三种表单形状都由这一个判据覆盖。
 *  ⚠️ 它**不读任何 class 名**（`.field__label` 一类是学生端/管理台各自的口径，
 *  在这里认它就是第二个所有者）。 */
function labelOf(el: HTMLElement): string {
  const fromLabel = el instanceof HTMLInputElement || el instanceof HTMLSelectElement
    || el instanceof HTMLTextAreaElement
    ? (el.labels?.[0]?.textContent ?? '')
    : ''
  const candidates = [
    fromLabel,
    el.getAttribute('aria-label') ?? '',
    el instanceof HTMLInputElement || el instanceof HTMLSelectElement
      || el instanceof HTMLTextAreaElement ? (el.name ?? '') : '',
    el.id ?? '',
    el.tagName.toLowerCase(),
  ]
  for (const raw of candidates) {
    const text = raw.replace(/\s+/g, ' ').trim()
    if (text !== '') return text.length > 48 ? `${text.slice(0, 48)}…` : text
  }
  return el.tagName.toLowerCase()
}

/** 那一句「下一步」。⚠️ 一个 flag 都认不出来时给一句**兜底**（不返回空串：
 *  空的处置建议就是本文件要消灭的那个静默）。 */
function adviceOf(el: HTMLElement): string {
  const validity = (el as HTMLInputElement).validity
  if (validity === undefined) return '请按那一格旁边的提示改一改。'
  for (const [flag, advice] of ADVICE) {
    if (validity[flag] === true) return advice
  }
  return '请按那一格旁边的提示改一改。'
}

export function useFormValidity(): UseFormValidityReturn {
  const notice = ref<FormValidityNotice | null>(null)

  /** 本轮不合格的那些元素。⚠️ `Set` 而不是数组：一次点击里同一个元素只算一格，
   *  而连点两次「提交」不该把计数涨成 2。⚠️ 迭代顺序 = 浏览器触发的顺序 = DOM 序，
   *  故「第一格」与浏览器聚焦的那一格是同一个。 */
  const invalid = new Set<HTMLElement>()
  let form: HTMLFormElement | null = null

  function publish(): void {
    if (invalid.size === 0) {
      notice.value = null
      return
    }
    const first = [...invalid][0] as HTMLElement
    const label = labelOf(first)
    const why = (first as HTMLInputElement).validationMessage?.replace(/\s+/g, ' ').trim() ?? ''
    const advice = adviceOf(first)
    notice.value = {
      title: invalid.size === 1
        ? `表单没有提交出去：「${label}」这一格没通过浏览器自带的校验`
        : `表单没有提交出去：${invalid.size} 格没通过浏览器自带的校验（第一格是「${label}」）`,
      body: `${why === '' ? '' : `浏览器给的理由：「${why}」`}${advice}`
        + '⚠️ 本次**没有**发出任何请求（原生校验拦在 `submit` 事件之前），改完再点一次提交。',
    }
  }

  function onInvalid(event: Event): void {
    const target = event.target
    if (!(target instanceof HTMLElement)) return
    invalid.add(target)
    publish()
  }

  /** `submit` 只在**校验通过**时才触发 ⇒ 那一刻这句话已经过期了。 */
  function onSubmitted(): void {
    invalid.clear()
    notice.value = null
  }

  /** 用户一开始改就把那句话撤掉：留着一句「这一格不合格」而用户正在改它，
   *  读起来像系统卡住了（与 `.trial-note` 那一格同一条「不说过期话」的口径）。 */
  function onEditing(): void {
    if (invalid.size === 0) return
    invalid.clear()
    notice.value = null
  }

  function attach(target: HTMLFormElement): void {
    // ⚠️ 第三个实参 `true`（捕获）是承重的：`invalid` **不冒泡**。
    target.addEventListener('invalid', onInvalid, true)
    target.addEventListener('submit', onSubmitted, true)
    target.addEventListener('input', onEditing, true)
    target.addEventListener('change', onEditing, true)
  }

  function detach(target: HTMLFormElement): void {
    target.removeEventListener('invalid', onInvalid, true)
    target.removeEventListener('submit', onSubmitted, true)
    target.removeEventListener('input', onEditing, true)
    target.removeEventListener('change', onEditing, true)
  }

  function bind(el: unknown): void {
    const next = el instanceof HTMLFormElement ? el : null
    if (next === form) return
    if (form !== null) detach(form)
    form = next
    invalid.clear()
    notice.value = null
    if (form !== null) attach(form)
  }

  function clear(): void {
    invalid.clear()
    notice.value = null
  }

  return { notice, bind, clear }
}

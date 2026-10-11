/**
 * `stores/identity.ts` —— **当前身份 + 业务日 `as_of`**。持久化到 `localStorage`。
 *
 * ---------------------------------------------------------------------------
 * 为什么会有这个 store（计划非目标第 1 条）
 * ---------------------------------------------------------------------------
 * 本系统**不做真实登录/鉴权**。身份走两个请求头（`X-Student-Id` /
 * `X-Teacher-Staff-No`），它们是后端 OpenAPI 的 `apiKey` securityScheme，
 * 原型口径逐字是「挡事故、不挡攻击」（`app/api/deps.py:3-7`）。
 * 故前端用一个**身份切换器**（`components/IdentitySwitcher.vue`）代替登录页。
 *
 * ⚠️ 这里只存**三样**（计划第 3 节的技术选型表：「只存三样：当前身份、
 * 当前学期/`as_of`、服务端缓存」），而第三样今天还没有住址 —— 本 store 只负责前两样。
 *
 * ⚠️ **`as_of` 的缺省是 `2025-10-12`，不是「今天」**：演示库的业务日就是那一天
 * （学期第 6 周的周日，`scripts/demo_bootstrap.py` 的 `DEMO_AS_OF`）。
 * 用「今天」当查询日期会查不到任何数据（计划约束第 22 条）。
 */
import { defineStore } from 'pinia'

/** 两种身份。**一次只有一种生效**（`client.ts` 因此只注入一个请求头）。 */
export type IdentityRole = 'student' | 'teacher'

/**
 * `as_of` 的缺省值 = **演示库的业务日**。
 *
 * ⚠️ 唯一所有者是后端 `backend/scripts/demo_bootstrap.py` 的 `DEMO_AS_OF`
 * （`demo.ps1` 也从那里读）。它是「学期第 6 周的周日」—— 而
 * `weekly_class_report` **只在周日**生成（`report_stage.REPORT_WEEKDAY = 6`），
 * 故这一天既能读到本周的周报，又落在处方的微周期内。
 * ⚠️ 处方的 `generated_on` 是 `2025-10-06`（早于 `as_of`），这也是承重的：
 * 若两者同日，报表窗口里「<= as_of 的训练日」只有周日一天（休息日），
 * 三层完成率会恒为 0。
 */
export const DEMO_AS_OF = '2025-10-12'

/** `localStorage` 的键。⚠️ 带版本号：改了下面 `Persisted` 的形状就把 `v1` 抬上去，
 *  否则老浏览器里存着的那一份会被当成新形状读进来。 */
const STORAGE_KEY = 'pe.identity.v1'

interface Persisted {
  role: IdentityRole | null
  studentId: number | null
  studentLabel: string | null
  teacherStaffNo: string | null
  teacherLabel: string | null
  asOf: string
}

function initial(): Persisted {
  return {
    role: null,
    studentId: null,
    studentLabel: null,
    teacherStaffNo: null,
    teacherLabel: null,
    asOf: DEMO_AS_OF,
  }
}

/**
 * 从 `localStorage` 读回来。
 *
 * ⚠️ 三层防御，每一层都对应一个真实的失效形态：
 *  1. `localStorage` 本身可能不可用（Safari 隐私模式、`file://`、被禁用的三方存储）
 *     → 读它**抛异常**，不是返回 null；
 *  2. 存进去的可能不是本版本的形状（老版本、或有人手工改过）→ 逐格校验；
 *  3. `asOf` 可能不是一个 `YYYY-MM-DD` 串 → 用正则验，不合格退回 {@link DEMO_AS_OF}。
 *
 * 一律**退回缺省值而不是抛错**：身份丢了最多是「要重选一次」，
 * 而抛错会让整个应用在 `main.ts` 里起不来。
 */
function load(): Persisted {
  const base = initial()
  let raw: string | null = null
  try {
    raw = window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return base
  }
  if (!raw) return base
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return base
  }
  if (typeof parsed !== 'object' || parsed === null) return base
  const p = parsed as Partial<Persisted>
  const role = p.role === 'student' || p.role === 'teacher' ? p.role : null
  return {
    role,
    studentId:
      role === 'student' && typeof p.studentId === 'number' && Number.isInteger(p.studentId)
        ? p.studentId
        : null,
    studentLabel: typeof p.studentLabel === 'string' ? p.studentLabel : null,
    teacherStaffNo:
      role === 'teacher' && typeof p.teacherStaffNo === 'string' && p.teacherStaffNo !== ''
        ? p.teacherStaffNo
        : null,
    teacherLabel: typeof p.teacherLabel === 'string' ? p.teacherLabel : null,
    asOf: typeof p.asOf === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(p.asOf) ? p.asOf : base.asOf,
  }
}

export const useIdentityStore = defineStore('identity', {
  state: (): Persisted => load(),

  getters: {
    /** 有没有选中一个可用的身份（写请求的前提）。 */
    hasIdentity(state): boolean {
      return (
        (state.role === 'student' && state.studentId !== null) ||
        (state.role === 'teacher' && state.teacherStaffNo !== null)
      )
    },
    /** 给人看的一行：「学生 3 · 2025010003 张三」/「教师 T0001 李老师」/「未选择身份」。 */
    summary(state): string {
      if (state.role === 'student' && state.studentId !== null) {
        return `学生 #${state.studentId}${state.studentLabel ? ` · ${state.studentLabel}` : ''}`
      }
      if (state.role === 'teacher' && state.teacherStaffNo !== null) {
        return `教师 ${state.teacherStaffNo}${state.teacherLabel ? ` · ${state.teacherLabel}` : ''}`
      }
      return '未选择身份'
    },
    /** 能不能写。⚠️ 后端 26 个泛型 CRUD 写入操作 + 12 个特例写入操作**全部**要教师头，
     *  只有 3 个学生侧的写（打卡 / 交快评 / 标已读）要学生头。 */
    canWriteAsTeacher(state): boolean {
      return state.role === 'teacher' && state.teacherStaffNo !== null
    },
    canWriteAsStudent(state): boolean {
      return state.role === 'student' && state.studentId !== null
    },
  },

  actions: {
    /** 选「我是学生 N」。`label` 只用于显示（学号 + 姓名），不参与任何请求。 */
    becomeStudent(studentId: number, label: string | null = null): void {
      this.role = 'student'
      this.studentId = studentId
      this.studentLabel = label
      this.teacherStaffNo = null
      this.teacherLabel = null
      this.persist()
    },

    /** 选「我是教师 X」。`staffNo` 是 `teacher.staff_no` 的字面量（例如 `T0001`）。 */
    becomeTeacher(staffNo: string, label: string | null = null): void {
      this.role = 'teacher'
      this.teacherStaffNo = staffNo
      this.teacherLabel = label
      this.studentId = null
      this.studentLabel = null
      this.persist()
    },

    /** 回到「未选择身份」。⚠️ **不清 `asOf`** —— 业务日是演示口径的一部分，
     *  与「我是谁」无关。 */
    clearIdentity(): void {
      this.role = null
      this.studentId = null
      this.studentLabel = null
      this.teacherStaffNo = null
      this.teacherLabel = null
      this.persist()
    },

    /**
     * 改业务日。
     *
     * ⚠️ **不合格的值一律退回 {@link DEMO_AS_OF}**，不是抛错也不是原样存下来：
     * 一个 `as_of=abc` 会被后端 Pydantic 折成 422 `request_validation_failed`，
     * 而那句报错会把下一个人支去查「哪个字段填错了」，真因却是「这里存了个垃圾」。
     */
    setAsOf(asOf: string): void {
      this.asOf = /^\d{4}-\d{2}-\d{2}$/.test(asOf) ? asOf : DEMO_AS_OF
      this.persist()
    },

    resetAsOf(): void {
      this.asOf = DEMO_AS_OF
      this.persist()
    },

    /**
     * **深链接身份**：从一段查询串里认一个身份（`?student=4` / `?teacher=T0001` /
     * `?as_of=2025-10-12`）。`main.ts` 在挂载前调它一次。
     *
     * -----------------------------------------------------------------------
     * 为什么会有这一格（本仓没有登录页）
     * -----------------------------------------------------------------------
     * 非目标第 1 条逐字：「不做真实登录/鉴权，前端做一个**身份切换器**代替登录页」。
     * 而「切换器」只能被**人**点 —— 一条 `http://…/s/check-in?student=4` 的链接
     * （学校推送、教师投屏上的二维码、以及 Task 2 的无头浏览器取证）落地时
     * 没有人去点它。故这里补上「URL 也能认身份」这一格：它**不是**调试后门，
     * 而是「没有登录页」这个决定的必要补充 —— 一个真的 H5 打卡入口本来就是
     * 一条带身份的链接。
     *
     * ⚠️ 三条纪律：
     *  1. **只在参数存在时才动状态**：没有 `?student=` 就一个字都不改，
     *     于是刷新页面不会把用户已选的身份冲掉；
     *  2. **不合格的值一律忽略**（`?student=abc` / `?student=-3` / `?as_of=今天`），
     *     不抛错、不写进 `localStorage` —— 一个垃圾值被存下来的失效形态是
     *     「之后每一次刷新都 422」，而真因藏在一个用户看不见的 URL 里；
     *  3. **一次只认一种身份**（与 `client.ts` 的「一次只注入一个头」同一条口径）：
     *     两个参数都给了就以 `student` 为准，因为 `/s/*` 是本仓的缺省树。
     *
     * @returns 有没有认出一个身份（`main.ts` 只把它写进日志，不据此分支）。
     */
    adoptFromUrl(search: string): boolean {
      const params = new URLSearchParams(search)
      let adopted = false

      const rawStudent = params.get('student')
      const rawTeacher = params.get('teacher')
      if (rawStudent !== null) {
        const id = Number(rawStudent)
        if (Number.isInteger(id) && id > 0) {
          this.becomeStudent(id, params.get('label'))
          adopted = true
        }
      } else if (rawTeacher !== null && rawTeacher.trim() !== '') {
        this.becomeTeacher(rawTeacher.trim(), params.get('label'))
        adopted = true
      }

      const rawAsOf = params.get('as_of')
      if (rawAsOf !== null && /^\d{4}-\d{2}-\d{2}$/.test(rawAsOf)) {
        this.setAsOf(rawAsOf)
        adopted = true
      }
      return adopted
    },

    /** 写回 `localStorage`。⚠️ 写失败静默（隐私模式下配额为 0）：
     *  身份仍然在本次会话里有效，只是刷新之后要重选一次。 */
    persist(): void {
      const snapshot: Persisted = {
        role: this.role,
        studentId: this.studentId,
        studentLabel: this.studentLabel,
        teacherStaffNo: this.teacherStaffNo,
        teacherLabel: this.teacherLabel,
        asOf: this.asOf,
      }
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
      } catch {
        // 存不下就算了（见上面那句）。
      }
    },
  },
})

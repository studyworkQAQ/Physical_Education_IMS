<script setup lang="ts">
/**
 * `views/student/MiniTest.vue` —— 二次小测（`/s/mini-test`）。
 *
 * ---------------------------------------------------------------------------
 * 读的端点（⚠️ 四个，**一律走学生会话**：`pe_session` cookie，由 `client.ts` 带上）
 * ---------------------------------------------------------------------------
 *  1. `GET /api/students/{id}/home?as_of=` —— 只为拿 `semester_id` 与 `week`
 *     （下面 ③ 的两个查询参数都是**必填**，别处读不到）；
 *  2. `GET /api/mini-tests?limit=200` —— ⚠️ 安全收紧波起它是 `read_scope="student_self"`，
 *     故服务端**已经**只回我自己的行（演示库上是 3 行），下面那一次
 *     `filter(row => row.student_id === id)` 因此变成 no-op（仍然正确，留着是防御）。
 *     ⚠️ 它的 list 项**不含** `item_combo`（那是 8 个「list 比 `*Read` 少列」的资源之一）。
 *  3. `GET /api/mini-tests/normalized?semester_id=&week=` —— ⚠️ **交付前收尾波 ③ 起
 *     要登录会话**（学生或教职皆可，匿名 **401**）。它回**我自己所在班**的全部 entries
 *     （Plan 06 Task 8 的响应级裁班），⚠️ 而 **Plan 06 Task 9 起每个 entry 只有三格**
 *     （`student_id` / `mini_test_id` / `shuttle_score`）：`squat_score` 与 `composite`
 *     已从 `NormalizedEntryRead` 上**摘掉**（改前是「别人的行置 `null`」的**列级**收窄，
 *     而那让同一个操作的响应体**随身份而变**、OpenAPI 只有一张 schema →
 *     生成出来的 `schema.d.ts` 是一份**假契约**）。
 *     ⚠️ `shuttle_score`（班内百分位）**照常给全班**，而本页要的正是它
 *     （`sample` / `slower` / `tied` / `rank` 四格都从它算出来）。
 *  4. `GET /api/mini-tests/normalized/me?semester_id=&week=` —— ⚠️ **Plan 06 Task 9
 *     新加，仅学生本人**（实测四档：匿名 **401** / 学生 **200** / 教师 **403** /
 *     管理员 **403**）。它回**我自己**那几行的**全列**三格（`squat_score` /
 *     `shuttle_score` / `composite`），故第 02 块的「小测综合分」与「深蹲得分」两个
 *     `StatBlock` 自本波起读它（`row.self.*`）。⚠️ 它的形状**恒定**
 *     （恒为「调用者自己的那几行、全列」），故它是**真契约** —— 那正是 ③ 此前给不出的。
 *     ⚠️ 两个查询参数与 ③ **同一组**（`home.semester_id` + `home.week`），故两次请求
 *     **并行**发（`Promise.all`）；任何一次失败都落到**同一块**「有解释的区域」
 *     （下面 `normalizedError` 那一档）。逐字取证住在
 *     `backend/app/api/routers/feedback.py` 的 `normalized_scores_self`。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ ③ 的身份口径换过**三次**（Task 2 顶回控制者的第 2 处，Critical；已修）
 * ---------------------------------------------------------------------------
 * ① **Task 2 交付时**它挂的是 `X-Teacher-Staff-No`（教师头 200 / 学生头 401 / 匿名 401），
 *   而计划把「班内百分位」分给了**学生**页面，且 `client.ts` 一次只注入一个身份头
 *   → 「有 `studentId`」与「能读 normalized」互斥。当时的处置是「降级但不撒谎」：
 *   原始成绩走匿名 list（永远有）、401 渲染成一块有解释的区域、**不在前端重算百分位**
 *   （算式只有一个住址 `app/domain/report.py`，后端有 AST 守卫数定义份数），
 *   而**成功支路照样实现**（含 `scored_count == 1` → 「无排名」、「比自己慢的人数」）。
 * ② **Plan 04 Task 3 的后端小修波**把那个头**摘掉**（改成匿名），于是成功支路
 *   **一行没改就亮起来了**（Task 2 那句「后端一改本页一行都不用动」在**渲染**上成立）。
 *   ⚠️ 而支撑「摘掉它不新增泄漏面」的那张对账表，前提是 `GET /api/mini-tests` 与
 *   `GET /api/enrollments` **也匿名** —— 安全收紧波把两者都收到了 `student_self`，
 *   两条腿都被抽掉，它于是成了**最后一个匿名的学生键读端点**。
 * ③ **交付前收尾波 ③** 给它挂上「学生或教职皆可」+ 学生档列级收窄（见上面第 3 条）。
 *   ⚠️ 本文件在那一波里**一行代码都没改**，改的只有这段注释 ——
 *   「降级但不撒谎」那块区域因此留着当**兜底**（422 缺参数、500 都走它），
 *   而它的文字早在 ② 就换成了**与 code 无关**的一档（只报 code / status / message，
 *   不再断言身份口径），故 ③ 没有让它变成假话。
 * ④ **Plan 06 Task 9** 动的**不是**身份口径、而是**列**：`NormalizedEntryRead` 摘掉
 *   `squat_score` / `composite` 两格（列级收窄 → **schema 级摘列**），本人那两格搬到
 *   上面第 4 条那个**窄端点**上。⚠️ 于是本文件在那一波里**真的改了代码**
 *   （多读一个端点、`mySections` 多带一格 `self`），而 ③ 那一句「一行代码都没改」
 *   **只对 ② 与 ③ 成立**、不再往后延。⚠️ 而「降级但不撒谎」那块区域**一行没动**，
 *   继续兜 ③ 与 ④ 两者的失败（它的文字与 code 无关，故 ④ 也没有让它变成假话）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ `scored_count == 1` → 显示「无排名」（计划约束第 11 条）
 * ---------------------------------------------------------------------------
 * 后端 `shuttle_percentile` 的算式是 `(比自己慢的人数 + 0.5 × 并列人数) / 样本数 × 100`，
 * `n = 1` 时它给 **50.0** —— 数学上正确（`app/domain/report.py:632-639` 逐字承认了
 * 「单人班给 50.0 在真实数据下看起来像真排过名」，并写明「本函数**刻意不改**：
 * 什么时候不该显示一个数是**展示层**的口径」）。故这一格由前端负责。
 *
 * ⚠️ 「比自己慢的人数」= 同一个班里 `shuttle_score` **严格小于**我的人数。
 * 这不是重算百分位，而是把后端已经算好的百分位**反读**成人数：
 * 折返跑秒数越少越好，故「比我慢」⟺「百分位比我低」，且并列的人百分位相同
 * （中点口径），于是「严格小于」恰好就是后端算式里那个「比自己慢的人数」。
 */
import { computed, ref, watch } from 'vue'

import { ApiError } from '../../api/client'
import {
  getNormalizedScores,
  getNormalizedSelf,
  getStudentHome,
  listMiniTests,
  listOnePage,
  truncationNoteOf,
} from '../../api/endpoints'
import type { components } from '../../api/generated/schema'
import type { MiniTestListItem } from '../../api/types'
import SectionHead from '../../components/SectionHead.vue'
import StatBlock from '../../components/StatBlock.vue'
import StudentNav from '../../components/StudentNav.vue'
import { useAsync } from '../../composables/useAsync'
import { useIdentityStore } from '../../stores/identity'
import { UNKNOWN, num, shortDate, text, weekdayOf } from '../../present'

type Normalized = components['schemas']['NormalizedScoreRead']
type Section = components['schemas']['NormalizedSectionRead']
/** ⚠️ Plan 06 Task 9：本人那几行的**全列**三格（窄端点 `/normalized/me`）。 */
type Self = components['schemas']['NormalizedSelfRead']
type SelfSection = components['schemas']['NormalizedSelfSectionRead']

const identity = useIdentityStore()

const { data, loading, settled, reload } = useAsync(async () => {
  const id = identity.studentId
  if (id === null) return null
  const [home, tests] = await Promise.all([
    getStudentHome(id, { asOf: identity.asOf }),
    listOnePage(listMiniTests, '小测成绩'),
  ])
  const mine = tests.items.filter((row) => row.student_id === id)
  let normalized: Normalized | null = null
  let self: Self | null = null
  let normalizedError: ApiError | null = null
  if (home.semester_id !== null && home.week !== null) {
    try {
      // ⚠️ **两次请求并行**（Plan 06 Task 9）：③ 给全班的折返百分位（算名次要它），
      //    ④ 给本人那三格的全列。⚠️ 两者用的是**同一组**查询参数，故一起发；
      //    任何一次失败都落到**同一块**「有解释的区域」（下面 `normalizedError`）——
      //    刻意不给 ④ 单开一块错误区：两块会说同一句话，而「一屏两块相同的红」
      //    会让人以为是两个故障。
      const query = { semesterId: home.semester_id, week: home.week }
      ;[normalized, self] = await Promise.all([
        getNormalizedScores(query),
        getNormalizedSelf(query),
      ])
    } catch (err) {
      // ⚠️ 这一档**不送红色横幅**（`silent` 的等效做法：在这里就接住）。
      //    401 是本页的**内容**：那个端点挂教师头是设计如此，不是故障。
      normalizedError = err instanceof ApiError ? err : null
      if (!(err instanceof ApiError)) console.error('[mini-test]', err)
    }
  }
  return {
    home,
    mine,
    normalized,
    self,
    normalizedError,
    /** ⚠️ Plan 06 Task 11 / B4：`listOnePage` 给的「没取全」那一句。 */
    truncation: truncationNoteOf([tests]),
  }
})

watch([() => identity.studentId, () => identity.asOf], () => void reload())

const mine = computed<MiniTestListItem[]>(() =>
  [...(data.value?.mine ?? [])].sort((a, b) => a.week - b.week),
)

/** 我有成绩的那几个周次（实测演示库是第 2 / 4 / 6 周各一次）。 */
const weeks = computed(() => [...new Set(mine.value.map((r) => r.week))].sort((a, b) => a - b))

/** 选中哪一周看班内百分位。缺省 = `home.week`（那一周有成绩的话），否则最近一次。 */
const pickedWeek = ref<number | null>(null)
watch(
  [weeks, () => data.value?.home.week ?? null],
  () => {
    if (pickedWeek.value !== null && weeks.value.includes(pickedWeek.value)) return
    const homeWeek = data.value?.home.week ?? null
    pickedWeek.value =
      homeWeek !== null && weeks.value.includes(homeWeek)
        ? homeWeek
        : (weeks.value[weeks.value.length - 1] ?? null)
  },
  { immediate: true },
)

const pickedRow = computed(
  () => mine.value.find((r) => r.week === pickedWeek.value) ?? null,
)

/* ------------------------------------------------------------- 班内百分位 */
const normalized = computed<Normalized | null>(() => data.value?.normalized ?? null)
const normalizedError = computed<ApiError | null>(() => data.value?.normalizedError ?? null)

/** 窄端点（④）给的**本人**那几行，按班号索引。
 *  ⚠️ 它是 `mySections` 里 `self` 那一格的唯一来源，故「深蹲得分」与「小测综合分」
 *  两个 `StatBlock` 的取值口径只有这一个住址。 */
const selfBySection = computed<Map<number, SelfSection>>(() => {
  const out = new Map<number, SelfSection>()
  for (const row of data.value?.self?.sections ?? []) out.set(row.course_section_id, row)
  return out
})

/** 我在的那几个班（一个学生同一学期**可能在两个班**：行政班与分层班并存，
 *  那时他在两个班里各有一行、百分位各不相同 —— 后端因此按班分组而不是平铺）。
 *
 *  ⚠️ **这一格自 Plan 04 Task 3 的后端小修波起真的渲染出来了**（此前 `normalized`
 *  挂教师头，而 `client.ts` 一次只注入一个身份头，故「有 studentId」与「能读它」互斥；
 *  ⚠️ 交付前收尾波 ③ 又给它挂回了身份，但那一档是「学生**或**教职皆可」，
 *  故本页照常读得到 —— 见文件头第 3 条）。
 *  它当初被保留下来的三个理由，第 ② 条已经兑现：
 *  ① 它是计划 Task 2 逐字要求的那一格（`scored_count == 1` → 「无排名」在这里落地）；
 *  ② 控制者一旦裁定改后端，本页**一行都不用改**就会亮起来 —— 实测成立（渲染上），
 *     而 ③ 那一次改身份口径**又一次**验证了它（本页在那一波里一行代码没动）；
 *  ③ 它的输入形状已由真 HTTP 取证核过（**Plan 06 Task 9 复测**：学生会话 → 200，
 *     `sections` 是我自己 enrolled 的 **2** 个班、`scored_count` 分别是 30 与 20、
 *     `entries[i]` 的键集合是 `mini_test_id,shuttle_score,student_id`；
 *     ⚠️ 而**教师与管理员两档的键集合逐字相同** —— 响应体不再有任何一列随身份而变，
 *     随身份而变的只有「哪些班」）。
 *     ⚠️ 于是本页读 ③ 的**只有** `shuttle_score`（算 `sample` / `slower` / `tied` /
 *     `rank`）与 `scored_count`，而「小测综合分」「深蹲得分」两格改读上面第 4 条那个
 *     **窄端点**（下面模板里的 `row.self?.*`）。
 *     ⚠️ 两侧的**班号**由后端守卫钉成逐字相同
 *     （`test_the_self_endpoint_agrees_with_the_class_level_percentile`：两个端点共用
 *     同一份分组与取样），故 `selfBySection` 那一次查找**恒配得上**；
 *     ⚠️ 而配不上时它渲染「—」（`StatBlock` 对 `null` / `undefined` 的既有处置），
 *     **不是** 0 —— 计划约束第 10 条。
 *     守卫是 `smoke.mjs` 第 13 步那几拍与后端 `tests/api/test_feedback.py` 的
 *     `test_a_student_session_reads_the_whole_class_percentile_but_no_raw_squat_count`。
 *  ⚠️ 演示库上没有 `scored_count == 1` 的班（最小的是 20），故「无排名」那一支
 *  在演示数据下**走不到**；它由后端 `tests/api/test_feedback.py` 的
 *  `test_a_null_shuttle_time_stays_out_of_the_percentile_and_gets_a_null_score`
 *  一族与本页的模板分支共同钉住，如实记录。 */
interface MySection {
  section: Section
  /** 班级端点（③）里**我**那一行。⚠️ Plan 06 Task 9 起它只有三格，
   *  故本页从它读的只有 `shuttle_score`（算名次）与 `mini_test_id`（「小测行 id」那一行）。 */
  entry: components['schemas']['NormalizedEntryRead']
  /** 窄端点（④）里**我**在这个班的那一行（全列三格）。
   *  ⚠️ 类型上是 `| null`：`selfBySection` 查不到时渲染「—」，**不是**抛、也不是 0。
   *  ⚠️ 而「查不到」今天不可达（两侧的班号由后端守卫钉成逐字相同），
   *  留这一档是为了让「后端把两个端点的判据写岔了」在**屏上可见**而不是白屏。 */
  self: SelfSection | null
  /** 同一个班里折返百分位**非空**的行数 = 后端算式里的那个「样本数 n」。 */
  sample: number
  /** 百分位严格比我低的人数 = 「比自己慢的人数」。 */
  slower: number
  /** 百分位与我相同的人数（并列取中点的那一档）。 */
  tied: number
  /** 我在这个班的排名（1 = 最快）。⚠️ `scored_count == 1` 时不显示。 */
  rank: number
}

const mySections = computed<MySection[]>(() => {
  const id = identity.studentId
  const n = normalized.value
  if (id === null || !n) return []
  const out: MySection[] = []
  for (const section of n.sections) {
    const entry = section.entries.find((e) => e.student_id === id)
    if (!entry) continue
    const scored = section.entries.filter((e) => e.shuttle_score !== null)
    const mine = entry.shuttle_score
    out.push({
      section,
      entry,
      self: selfBySection.value.get(section.course_section_id) ?? null,
      sample: scored.length,
      slower: mine === null ? 0 : scored.filter((e) => (e.shuttle_score ?? 0) < mine).length,
      tied: mine === null ? 0 : scored.filter((e) => e.shuttle_score === mine).length,
      rank:
        mine === null
          ? 0
          : 1 + scored.filter((e) => (e.shuttle_score ?? 0) > mine).length,
    })
  }
  return out
})

/** 我在 `unassigned` 里吗（不在任何教学班 → 班内百分位**无定义**）。 */
const unassigned = computed(() => {
  const id = identity.studentId
  return (normalized.value?.unassigned ?? []).some((u) => u.student_id === id)
})
</script>

<template>
  <div class="s-page">
    <StudentNav />

    <!-- ⚠️ Plan 06 Task 11 / B4：单页取值被截断时**必须**让用户看见。
         判据与那句话的唯一住址是 `api/endpoints.ts` 的 `listOnePage` /
         `truncationNoteOf`；本处只负责把它画出来（用既有的 note 类，
         ⚠️ 不引新 CSS ⇒ `check:tokens` 一格都不退）。 -->
    <p v-if="data?.truncation" class="s-block__note">{{ data.truncation }}</p>

    <div v-if="identity.studentId === null" class="s-empty">
      <p class="s-empty__title zh-title">还不知道你是谁</p>
      <p class="s-empty__note">
        本页要在 180 行小测里挑出<strong>你的</strong>那几行，故得先知道你是谁。
      </p>
    </div>

    <div v-else-if="loading && !settled" class="s-loading">
      <span class="s-loading__rule" aria-hidden="true"></span>
      <span>正在读小测成绩…</span>
    </div>

    <template v-else-if="data">
      <header class="s-head">
        <p class="caps s-head__kicker">
          MINI TEST · 学期 {{ num(data.home.semester_id) }} ·
          第 {{ num(data.home.week) }} 周
        </p>
        <h2 class="zh-title s-head__title">二次小测</h2>
        <p class="s-head__meta">
          30 秒深蹲（次数越多越好）+ 20 米折返（秒数越少越好）。两次小测之间隔两周。
        </p>
      </header>

      <!-- 01 · 我的成绩 -->
      <section class="s-card">
        <SectionHead :index="1" label="MY SCORES" />
        <div class="s-subhead">
          <span class="s-subhead__title">我的 {{ mine.length }} 次小测</span>
          <span class="s-subhead__aside">
            录入人 {{ pickedRow ? pickedRow.entered_by : UNKNOWN }}
          </span>
        </div>

        <div v-if="weeks.length > 1" class="weekpick">
          <span class="weekpick__label caps">看哪一次</span>
          <button
            v-for="w in weeks"
            :key="w"
            type="button"
            class="weekpick__btn"
            :class="{ 'weekpick__btn--on': pickedWeek === w }"
            @click="pickedWeek = w"
          >
            第 {{ w }} 周
          </button>
        </div>

        <div v-if="mine.length === 0" class="s-empty">
          <svg class="s-empty__mark" viewBox="0 0 88 20" aria-hidden="true">
            <path class="s-empty__mark-line" d="M2 6 H86" />
            <path class="s-empty__mark-hair" d="M2 14 H30" />
          </svg>
          <p class="s-empty__title zh-title">还没有小测成绩</p>
          <p class="s-empty__note">
            <code>mini_test</code> 表里没有 <code>student_id = {{ identity.studentId }}</code> 的行。
            小测由教师批量录入（<code>POST /api/mini-tests/batch</code>，教师头），
            学生端不能自己填。
          </p>
        </div>

        <table v-else class="data-table scores">
          <thead>
            <tr>
              <th scope="col">周次</th>
              <th scope="col">测于</th>
              <th scope="col">深蹲 30s</th>
              <th scope="col">折返 20m</th>
              <th scope="col">标准化分</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in mine"
              :key="row.id"
              :class="{ 'scores--on': row.week === pickedWeek }"
            >
              <td>第 {{ row.week }} 周</td>
              <td>
                {{ row.tested_on }}
                <span class="scores__wd">{{ weekdayOf(row.tested_on) }}</span>
              </td>
              <!-- ⚠️ 两格都可空（「没测」）→ 「—」，**不是** 0：
                   一个没测的人若被当成「最差的那个」，会把全班的百分位一起往下拽
                   （后端 `normalized_scores` 的 docstring 逐字写了这件事）。 -->
              <td>{{ num(row.squat_30s_count) }}</td>
              <td>{{ num(row.shuttle_20m_s, 1) }}</td>
              <td>{{ num(row.normalized_score, 2) }}</td>
            </tr>
          </tbody>
        </table>

        <p class="s-block__note">
          ⚠️ 「标准化分」这一列是 <code>mini_test.normalized_score</code>（录入时算好的存量列），
          与下面那块<strong>班内百分位</strong>不是同一个量、也不是同一个窗口 ——
          进步榜一律读班级周报的 <code>progress_board</code>（约束第 12 条），
          本页两块都<strong>不</strong>拿来拼进步榜。
        </p>
      </section>

      <!-- 02 · 班内百分位 -->
      <section class="s-card">
        <SectionHead :index="2" label="PERCENTILE" />
        <div class="s-subhead">
          <span class="s-subhead__title">班内百分位</span>
          <span class="s-subhead__aside">
            <template v-if="normalized">
              学期 {{ normalized.semester_id }} · 第 {{ normalized.week }} 周
            </template>
            <template v-else>读不到</template>
          </span>
        </div>

        <p class="weekpick__note">
          ⚠️ 本块只算 <code>home.week</code>（第 {{ num(data.home.week) }} 周）——
          端点的 <code>semester_id</code> 与 <code>week</code> 都是<strong>必填</strong>的，
          而它们只能从 <code>/home</code> 读出来，故本页不猜别的周。
          上面第 01 块的「看哪一次」只切换原始成绩。
        </p>

        <!-- ⚠️⚠️ 读不到那一档：本页的**内容**，不是错误横幅。
             ⚠️ 文字**与 code 无关**（Plan 04 Task 3 的小修波改的）：这一块此前逐字写着
             「挂的是 X-Teacher-Staff-No」「学生头 → 401」，而后端把那个头摘掉之后
             那句话就成了假话。现在它只报后端给的 code / status / message，
             不再对身份口径下任何断言 —— 于是它不会因为下一次后端改动而过期。 -->
        <div v-if="normalizedError" class="s-notice">
          <p class="s-notice__title">
            {{ normalizedError.code }} · {{ normalizedError.status }} —— 班内百分位读不到
          </p>
          <p>
            <code>GET /api/mini-tests/normalized</code>（与本人那几格的
            <code>/normalized/me</code>）这一格没有读到数据。
            后端给的 <code>code</code> 是
            <strong><code>{{ normalizedError.code }}</code></strong>
            （HTTP {{ normalizedError.status }}）。
            ⚠️ 本页<strong>不会</strong>在前端重算一遍百分位，也<strong>不会</strong>
            把它显示成 0 —— 那个算式只有一个住址（<code>app/domain/report.py</code>），
            后端有一条 AST 守卫数它的定义份数。
          </p>
          <!-- ⚠️ 改前这一段逐字写着「它走的是**匿名** `GET /api/mini-tests`
               （180 行全量 + 客户端按 `student_id` 过滤）」，而 2026-10-16 实测四档是：
               匿名 **401 `unauthenticated`**（249 B）、学生会话 **200 / 3 行**
               （= 只有他自己那几行）、教师会话 **200 / 123 行**（= 他任教的那几个班）、
               管理员 **200 / 180 行**（才是全量）⇒ **两半都假**：它要会话，
               而且是**服务端按身份筛**、不是「全量拉下来客户端筛」。
               openapi 上它挂着 security（`X-Student-Id` / `X-Teacher-Staff-No`）。
               ⚠️ 与 spec §13.18.5 已修的 #4/#5/#12 同族同形，而那一节逐字写着
               「这两类**必须本波修完**」，且本文件**不在 Plan 07 的 diff 里**
               ⇒ Task 5b 的自查整个漏掉了它（终审 S3-1）。见 spec §13.20。
               守卫：frontend/scripts/check-dist.mjs 的 FORBIDDEN_STALE_CLAIM。 -->
          <p>
            上面第 01 块的<strong>原始成绩</strong>不受影响：它走的是
            <code>GET /api/mini-tests</code>（⚠️ <strong>要会话</strong>：匿名打过去是
            <code>401</code>；而且<strong>服务端按身份筛</strong> —— 学生只拿到自己
            那几行，教师拿到自己任教班的，管理员才是全量），与本块是两个独立的请求。
          </p>
          <p><code>{{ normalizedError.message }}</code></p>
        </div>

        <template v-else-if="normalized">
          <div v-if="unassigned" class="s-unknown">
            <p class="s-unknown__title zh-title">你不在任何教学班里 → 班内百分位无定义</p>
            <p class="s-unknown__note">
              后端的 <code>unassigned</code> 那一支：三种候选处置（当成一个人的班 → 你会拿到
              50.0；给 0 → 把「不知道」讲成「最差」；点名报出来）里只有第三种不撒谎，
              而它顺带把「选课记录漏了一条」这个<strong>要修的数据问题</strong>摆到台面上。
            </p>
          </div>

          <div v-else-if="mySections.length === 0" class="s-empty">
            <p class="s-empty__title zh-title">
              第 {{ num(data.home.week) }} 周没有你的小测行
            </p>
            <p class="s-empty__note">
              端点按 <code>semester_id</code> + <code>week</code> 取行；你在那一周没有成绩，
              故班内百分位里找不到你。上面第 01 块列出的是你<strong>全部</strong>三次成绩。
            </p>
          </div>

          <div v-for="row in mySections" :key="row.section.course_section_id" class="sect">
            <p class="sect__head zh-title">
              教学班 {{ row.section.course_section_id }}
              <span class="sect__n">（班内 {{ row.section.scored_count }} 人有成绩）</span>
            </p>

            <!-- ⚠️ 约束第 11 条：`scored_count == 1` → 「无排名」，不是 50.0 -->
            <div v-if="row.section.scored_count === 1" class="s-unknown">
              <p class="s-unknown__title zh-title">无排名</p>
              <p class="s-unknown__note">
                这个班只有 <strong>1</strong> 个人有成绩。后端仍然给了
                <code>{{ num(row.entry.shuttle_score, 1) }}</code> 分 ——
                那是标准 percentile rank 公式在 <code>n = 1</code> 时的自洽结果
                （<code>(0 + 0.5 × 1) / 1 × 100 = 50.0</code>），
                但它<strong>看起来像真排过名</strong>，故本页显示「无排名」。
              </p>
            </div>

            <template v-else>
              <div class="sect__stats">
                <!-- ⚠️ Plan 06 Task 9 起这一格读**窄端点**（`row.self`），不再读
                     `row.entry`：`composite` 已从 `NormalizedEntryRead` 上摘掉了
                     （列级收窄 → schema 级摘列）。⚠️ 查不到时 `StatBlock` 渲染「—」。 -->
                <StatBlock
                  :value="row.self?.composite"
                  :decimals="2"
                  label="小测综合分"
                  size="display"
                  caption="两项等权平均"
                />
                <StatBlock
                  :value="row.entry.shuttle_score"
                  :decimals="1"
                  label="折返班内百分位"
                  size="display"
                  :level="
                    row.entry.shuttle_score === null
                      ? 'default'
                      : row.entry.shuttle_score >= 50
                        ? 'moss'
                        : row.entry.shuttle_score >= 25
                          ? 'amber'
                          : 'red'
                  "
                  :caption="`样本 ${row.sample} 人`"
                />
                <!-- ⚠️ 同上：`squat_score` 也只住在窄端点上。⚠️ 它与第 01 块表格里的
                     「深蹲 30s」是**同一个数**（spec §8.1「深蹲得分 = 次数（直接用）」），
                     而两块**可能不是同一周**（第 01 块跟着 `pickedWeek`，本块只算
                     `home.week`），故本页刻意两处都显示、不合并。 -->
                <StatBlock
                  :value="row.self?.squat_score"
                  :decimals="1"
                  label="深蹲得分"
                  size="body"
                  caption="= 30 秒次数"
                />
              </div>

              <div class="s-rows">
                <div class="s-row">
                  <span class="s-row__key">比你慢的人数</span>
                  <span class="s-row__val">
                    <!-- ⚠️ 折返没测（`shuttle_score` 为 null）时它**无定义**，不是 0 -->
                    <template v-if="row.entry.shuttle_score === null">
                      <span class="unknown">{{ UNKNOWN }}</span>（你这次没测折返）
                    </template>
                    <template v-else>{{ row.slower }} 人</template>
                  </span>
                </div>
                <div class="s-row">
                  <span class="s-row__key">与你并列</span>
                  <span class="s-row__val">
                    <template v-if="row.entry.shuttle_score === null">
                      <span class="unknown">{{ UNKNOWN }}</span>
                    </template>
                    <template v-else>{{ row.tied }} 人</template>
                  </span>
                </div>
                <div class="s-row">
                  <span class="s-row__key">班内名次（折返）</span>
                  <span class="s-row__val">
                    <template v-if="row.entry.shuttle_score === null">
                      <span class="unknown">{{ UNKNOWN }}</span>
                    </template>
                    <template v-else>
                      第 {{ row.rank }} / {{ row.sample }}
                    </template>
                  </span>
                </div>
                <div class="s-row">
                  <span class="s-row__key">小测行 id</span>
                  <span class="s-row__val">{{ row.entry.mini_test_id }}</span>
                </div>
              </div>
            </template>
          </div>

          <p class="s-block__note">
            算式（spec §8.1，唯一住址 <code>app/domain/report.py</code>）：
            <strong>深蹲得分 = 30 秒次数</strong>、
            <strong>折返得分 = 该教学班内折返秒数的百分位反查</strong>、
            <strong>综合分 = 两项等权平均</strong>。
            ⚠️ 综合分的<strong>量纲是混的</strong>（次数 vs 百分位），后端如实记录了这一点，
            本页也不把它换算成什么「总分」。
          </p>
        </template>
      </section>

      <!-- 03 · 选中那一次的原始成绩 -->
      <section v-if="pickedRow" class="s-card">
        <SectionHead :index="3" label="RAW" />
        <div class="s-subhead">
          <span class="s-subhead__title">
            第 {{ pickedRow.week }} 周那一次（{{ shortDate(pickedRow.tested_on) }}
            {{ weekdayOf(pickedRow.tested_on) }}）
          </span>
          <span class="s-subhead__aside">id {{ pickedRow.id }}</span>
        </div>
        <div class="s-rows">
          <div class="s-row">
            <span class="s-row__key">30 秒深蹲次数</span>
            <span class="s-row__val">{{ num(pickedRow.squat_30s_count) }} 次</span>
          </div>
          <div class="s-row">
            <span class="s-row__key">20 米折返</span>
            <span class="s-row__val">{{ num(pickedRow.shuttle_20m_s, 1) }} 秒</span>
          </div>
          <div class="s-row">
            <span class="s-row__key">录入人（工号）</span>
            <span class="s-row__val">{{ text(pickedRow.entered_by) }}</span>
          </div>
          <div class="s-row">
            <span class="s-row__key">项目组合 item_combo</span>
            <span class="s-row__val">
              <span class="unknown">{{ UNKNOWN }}</span>
              <span class="scores__why">（泛型 list 把这一列排掉了，要它得读单条）</span>
            </span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.scores {
  font-size: var(--fs-micro);
}

.scores td,
.scores th {
  padding-inline-end: var(--space-2);
}

.scores--on td {
  background: var(--amber-faint);
  font-weight: 600;
}

.scores__wd {
  color: var(--ink-faint);
  font-family: var(--font-ui);
  font-size: var(--fs-micro);
}

.scores__why {
  font-family: var(--font-ui);
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.weekpick {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.weekpick__label {
  color: var(--ink-faint);
}

.weekpick__btn {
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-raise);
  font-family: var(--font-ui);
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.weekpick__btn--on {
  border-color: var(--primary);
  background: var(--primary);
  color: var(--on-primary);
}

.weekpick__note {
  flex: 1 1 100%;
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.sect {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding-block: var(--space-3);
  border-block-end: var(--border-hairline);
}

.sect:last-of-type {
  border-block-end: none;
}

.sect__head {
  font-size: var(--fs-body);
  font-weight: var(--fw-700);
}

.sect__n {
  font-family: var(--font-ui);
  font-size: var(--fs-micro);
  font-weight: var(--fw-400);
  color: var(--ink-faint);
}

.sect__stats {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}
</style>

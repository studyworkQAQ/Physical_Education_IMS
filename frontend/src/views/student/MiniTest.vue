<script setup lang="ts">
/**
 * `views/student/MiniTest.vue` —— 二次小测（`/s/mini-test`）。
 *
 * ---------------------------------------------------------------------------
 * 读的端点（⚠️ 三个，其中一个是**教师头**）
 * ---------------------------------------------------------------------------
 *  1. `GET /api/students/{id}/home?as_of=` · **学生头** —— 只为拿 `semester_id` 与 `week`
 *     （下面 ③ 的两个查询参数都是**必填**，别处读不到）；
 *  2. `GET /api/mini-tests?limit=200` · **匿名** —— 全量 180 行，客户端按
 *     `student_id === 我` 过滤（泛型 list 没有筛选参数，约束第 9 条）。
 *     ⚠️ 它的 list 项**不含** `item_combo`（那是 8 个「list 比 `*Read` 少列」的资源之一）。
 *  3. `GET /api/mini-tests/normalized?semester_id=&week=` · **匿名**。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ ③ 曾经是**教师头**（Task 2 顶回控制者的第 2 处，Critical）；已修
 * ---------------------------------------------------------------------------
 * Task 2 交付时它挂的是 `X-Teacher-Staff-No`（教师头 200 / 学生头 401 / 匿名 401），
 * 而计划把「班内百分位」分给了**学生**页面，且 `client.ts` 一次只注入一个身份头
 * → 「有 `studentId`」与「能读 normalized」互斥。当时的处置是「降级但不撒谎」：
 * 原始成绩走匿名 list（永远有）、401 渲染成一块有解释的区域、**不在前端重算百分位**
 * （算式只有一个住址 `app/domain/report.py`，后端有 AST 守卫数定义份数），
 * 而**成功支路照样实现**（含 `scored_count == 1` → 「无排名」、「比自己慢的人数」）。
 *
 * ⚠️ **Plan 04 Task 3 的后端小修波把那个头摘掉了**，于是成功支路**一行没改就亮起来了**
 * （Task 2 那句「后端一改本页一行都不用动」在**渲染**上成立）。实测：匿名 200 /
 * 学生头 200 / 教师头 200，三者响应体逐字相同；演示库上 5 个 section、
 * `scored_count` 分别是 30/30/20/20/20、`unassigned` 为空。
 * ⚠️ **但那一块「有解释的区域」的文字必须改**（这就是本页在本波里唯一动过的地方）：
 * 它逐字写着「挂的是 `X-Teacher-Staff-No`」「学生头 → 401」，后端一改它就成了假话。
 * 故把它换成**与 code 无关**的一档（只报 code / status / message，不再断言身份口径）——
 * 于是将来任何一次读失败（422 缺参数、500）都有一块诚实的区域，而不是一句过期的人话。
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
  getStudentHome,
  listMiniTests,
} from '../../api/endpoints'
import type { components } from '../../api/generated/schema'
import type { MiniTestListItem } from '../../api/types'
import LaneDivider from '../../components/LaneDivider.vue'
import StatBlock from '../../components/StatBlock.vue'
import StudentNav from '../../components/StudentNav.vue'
import { useAsync } from '../../composables/useAsync'
import { useIdentityStore } from '../../stores/identity'
import { UNKNOWN, num, shortDate, text, weekdayOf } from '../../present'

type Normalized = components['schemas']['NormalizedScoreRead']
type Section = components['schemas']['NormalizedSectionRead']

const identity = useIdentityStore()

const { data, loading, settled, reload } = useAsync(async () => {
  const id = identity.studentId
  if (id === null) return null
  const [home, tests] = await Promise.all([
    getStudentHome(id, { asOf: identity.asOf }),
    listMiniTests({ limit: 200 }),
  ])
  const mine = tests.items.filter((row) => row.student_id === id)
  let normalized: Normalized | null = null
  let normalizedError: ApiError | null = null
  if (home.semester_id !== null && home.week !== null) {
    try {
      normalized = await getNormalizedScores({ semesterId: home.semester_id, week: home.week })
    } catch (err) {
      // ⚠️ 这一档**不送红色横幅**（`silent` 的等效做法：在这里就接住）。
      //    401 是本页的**内容**：那个端点挂教师头是设计如此，不是故障。
      normalizedError = err instanceof ApiError ? err : null
      if (!(err instanceof ApiError)) console.error('[mini-test]', err)
    }
  }
  return { home, mine, normalized, normalizedError }
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

/** 我在的那几个班（一个学生同一学期**可能在两个班**：行政班与分层班并存，
 *  那时他在两个班里各有一行、百分位各不相同 —— 后端因此按班分组而不是平铺）。
 *
 *  ⚠️ **这一格自 Plan 04 Task 3 的后端小修波起真的渲染出来了**（此前 `normalized`
 *  挂教师头，而 `client.ts` 一次只注入一个身份头，故「有 studentId」与「能读它」互斥）。
 *  它当初被保留下来的三个理由，第 ② 条已经兑现：
 *  ① 它是计划 Task 2 逐字要求的那一格（`scored_count == 1` → 「无排名」在这里落地）；
 *  ② 控制者一旦裁定改后端，本页**一行都不用改**就会亮起来 —— 实测成立（渲染上）；
 *  ③ 它的输入形状已由真 HTTP 取证核过（教师头 → 200：5 个 section、`scored_count`
 *  分别是 30/30/20/20/20、`entries[i]` 的键集合是
 *  `composite,mini_test_id,shuttle_score,squat_score,student_id`）。
 *  ⚠️ 演示库上没有 `scored_count == 1` 的班（最小的是 20），故「无排名」那一支
 *  在演示数据下**走不到**；它由后端 `tests/api/test_feedback.py` 的
 *  `test_a_null_shuttle_time_stays_out_of_the_percentile_and_gets_a_null_score`
 *  一族与本页的模板分支共同钉住，如实记录。 */
interface MySection {
  section: Section
  entry: components['schemas']['NormalizedEntryRead']
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
      <section class="s-card lane-block" :style="{ '--lane-index': 0 }">
        <LaneDivider :index="1" label="MY SCORES" />
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
      <section class="s-card lane-block" :style="{ '--lane-index': 1 }">
        <LaneDivider :index="2" label="PERCENTILE" />
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
            <code>GET /api/mini-tests/normalized</code> 这一格没有读到数据。
            后端给的 <code>code</code> 是
            <strong><code>{{ normalizedError.code }}</code></strong>
            （HTTP {{ normalizedError.status }}）。
            ⚠️ 本页<strong>不会</strong>在前端重算一遍百分位，也<strong>不会</strong>
            把它显示成 0 —— 那个算式只有一个住址（<code>app/domain/report.py</code>），
            后端有一条 AST 守卫数它的定义份数。
          </p>
          <p>
            上面第 01 块的<strong>原始成绩</strong>不受影响：它走的是匿名
            <code>GET /api/mini-tests</code>（180 行全量 + 客户端按
            <code>student_id</code> 过滤），与本块是两个独立的请求。
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
                <StatBlock
                  :value="row.entry.composite"
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
                <StatBlock
                  :value="row.entry.squat_score"
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
                      <span class="unknown">—</span>（你这次没测折返）
                    </template>
                    <template v-else>{{ row.slower }} 人</template>
                  </span>
                </div>
                <div class="s-row">
                  <span class="s-row__key">与你并列</span>
                  <span class="s-row__val">
                    <template v-if="row.entry.shuttle_score === null">
                      <span class="unknown">—</span>
                    </template>
                    <template v-else>{{ row.tied }} 人</template>
                  </span>
                </div>
                <div class="s-row">
                  <span class="s-row__key">班内名次（折返）</span>
                  <span class="s-row__val">
                    <template v-if="row.entry.shuttle_score === null">
                      <span class="unknown">—</span>
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
      <section v-if="pickedRow" class="s-card lane-block" :style="{ '--lane-index': 2 }">
        <LaneDivider :index="3" label="RAW" />
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
              <span class="unknown">—</span>
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
  font-size: 9px;
}

.scores__why {
  font-family: var(--font-ui);
  font-size: 9px;
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

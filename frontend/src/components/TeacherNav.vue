<script setup lang="ts">
/**
 * `TeacherNav.vue` —— 教师端 4 个页面的**跑道导航**。
 *
 * ---------------------------------------------------------------------------
 * 为什么会有这个组件（Task 3 加的，派单的 Create 清单里没有它）
 * ---------------------------------------------------------------------------
 * 与 `StudentNav.vue` 完全同一条理由：`App.vue` 的报头只有三棵树的入口，而
 * `router/index.ts` 已经把 4 条 `/t/*` 路由建好了。没有这一格，那 4 条路由
 * **只能靠手敲 URL 到达** —— 一个「能点着走完一条业务链」的原型（计划第 0 节的判据）
 * 就不能从大屏走到预警队列、再走到某个学生的详情页。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 第 4 格不是一个链接，是一个**班 → 学生 两级选择器**
 * ---------------------------------------------------------------------------
 * 那条路由是 `/t/students/:studentId`（Task 1 定的，⚠️ **带一个必填的路径参数**），
 * 而 `/t/students` 本身**不在**路由树里（打过去会被 catch-all 折回 `/s/home`）。
 * 故这一格做成两个 `<select>`：先选班、再选那个人 → `router.push`。
 *
 * ⚠️⚠️ **为什么是两级而不是一级**（Plan 06 Task 8 改的；改前是一级「全校 60 人」）：
 * 那 13 个学生键资源的 `read_scope` 从 `student_self`（教职全读）改成了
 * `staff_taught`（**教师只读自己本学期任教班级的学生行**），而一级的名单来自
 * `GET /api/students`（`staff` 档 = 教职全读，**没有**跟着收），于是改前的选择器
 * 会把全校 60 人都列出来，而其中 **19 个**（演示库实测：T0001 的任教范围是 41 / 60）
 * 点进去只会渲染出 403 面板 —— 一个「列出来但点不开」的下拉框是一句谎话。
 * 两级之后第一级就是「我任教的班」，第二级因此只可能是点得开的人。
 *
 * ⚠️ **名单从四个既有端点拼出来，一个新端点都不加**（派单 §3 第 1 条要求「优先复用」；
 * 实测 `/api/teacher/students/*` 那一族只有 `weekly-sheet` 与 `home` 两个**按人**的
 * 端点，**没有**「我的学生」那一格，故复用不了它 —— 已顶回）：
 *  1. `GET /api/teachers`（`staff` 档）→ 工号 → `teacher.id`；
 *  2. `GET /api/course-sections`（匿名档）→ `teacher_id == 我` 的那些班；
 *  3. `GET /api/enrollments`（⚠️ `staff_taught` 档）→ 每个班有哪些学生；
 *  4. `GET /api/students`（`staff` 档）→ id → 学号 + 姓名。
 * ⚠️ 第 3 条**自己就已经按任教范围收窄了**，故两级选择器不需要在前端再筛一次人；
 * 而第一级**仍然**要按 `teacher_id == 我` 筛（`course-sections` 是匿名档、给的是全校的班）。
 * ⚠️ **管理员不受影响**：`session.isAdmin` 时第一级列**全部**班（他越过任教范围，
 * 后端也是全读），故管理台与 `/t/*` 两侧对同一个人给出同一份名单。
 * ⚠️ 到达那一页的**主要**路径其实是下钻：大屏的异常名单、预警队列的每一行
 * 都是 `<RouterLink :to="/t/students/{id}">`。本选择器只是「我知道学号、
 * 想直接看」的那一档。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 两个所有者，各自只管一件事（与 `StudentNav` 同一条）
 * ---------------------------------------------------------------------------
 *  - **标题**读 `router` 的 `meta.title`（那是它的唯一住址，Task 1 立的规矩）；
 *  - **顺序**由下面那个 `ORDER` 数组定（`router.getRoutes()` 的返回序是匹配器的
 *    打分序，不是声明序）。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  listCourseSections,
  listEnrollments,
  listOnePage,
  listStudents,
  listTeachers,
  truncationNoteOf,
} from '../api/endpoints'
import { useSessionStore } from '../stores/session'

/** 4 条 `/t/*` 路由的 `name`，**顺序就是显示的顺序**（与计划 Task 3 那张表逐行同序）。 */
const ORDER = [
  'teacher-dashboard',
  'teacher-class-report',
  'teacher-alert-queue',
  'teacher-student-detail',
] as const

/** 每一格右上角那个极小的拉丁缩写：计时牌上的「项目代码」。 */
const CAPS: Record<string, string> = {
  'teacher-dashboard': 'WALL',
  'teacher-class-report': 'REPORT',
  'teacher-alert-queue': 'ALERTS',
  'teacher-student-detail': 'STUDENT',
}

const router = useRouter()
const route = useRoute()

/** 第 4 格（学生详情）没有固定的 `to`，故它的链接指向「当前正在看的那个人」，
 *  没有就指向 1（演示库的第一个学生）。⚠️ 只在**没选中**时用作兜底：
 *  一个「点了就跳到学生 1」的导航格会让人以为它坏了。 */
const fallbackStudent = computed(() => {
  const param = route.params.studentId
  const id = typeof param === 'string' ? Number(param) : Number(param?.[0])
  return Number.isInteger(id) && id > 0 ? id : 1
})

const items = computed(() => {
  const all = router.getRoutes()
  return ORDER.map((name, i) => {
    const record = all.find((r) => r.name === name)
    const path = record?.path ?? '/t/dashboard'
    return {
      name,
      to: name === 'teacher-student-detail' ? `/t/students/${fallbackStudent.value}` : path,
      title: record?.meta.title ?? name,
      caps: CAPS[name] ?? '',
      /** 道次编号 01–04：与 `SectionHead` 同一套母题。 */
      lane: String(i + 1).padStart(2, '0'),
      on: route.name === name,
      isPicker: name === 'teacher-student-detail',
    }
  })
})

/* ------------------------------------------------------- 班 → 学生 两级名单 */
interface Option {
  id: number
  label: string
}

/** 第一级：一个班 + 它的那些学生（第二级的选项）。 */
interface SectionOption extends Option {
  students: Option[]
}

const sections = ref<SectionOption[]>([])
const pickedSection = ref<string>('')
const picked = ref<string>('')
const listError = ref<string | null>(null)
/** ⚠️ 四个名单里有任何一个**没一页取全**时，给用户看的那一句
 *  （Plan 06 Task 11 / B4）。判据与措辞的唯一住址是 `api/endpoints.ts` 的
 *  `listOnePage` / `truncationNoteOf`；本处只负责画出来。
 *  ⚠️ 它渲染成 `.t-block__note`（`styles/teacher.css` 里的既有类，全局的，
 *  故本组件的 scoped 样式挡不住它）而**不是**一条新 CSS —— 于是
 *  `npm run check:tokens` 的扫描面与色值住址一格都不变。 */
const truncation = ref<string | null>(null)

const session = useSessionStore()

/** 第二级的选项 = 当前那个班的学生。⚠️ 换了班而没选人时**不导航**
 *  （一个「选了班就跳过去」的导航格会让人以为它坏了，与上面 `fallbackStudent`
 *  那条注释同一条口径）。 */
const currentStudents = computed<Option[]>(
  () => sections.value.find((s) => String(s.id) === pickedSection.value)?.students ?? [],
)

/** 两级各自的计数，写在页面上（不是藏在代码里）：教师要能看出
 *  「这一份名单是我任教的班」而不是「全校」。 */
const scopeNote = computed(() => {
  const total = sections.value.reduce((n, s) => n + s.students.length, 0)
  return session.isAdmin
    ? `管理员 · 全部 ${sections.value.length} 个班 / ${total} 人次`
    : `我任教的 ${sections.value.length} 个班 / ${total} 人次`
})

/** 把选择器同步到「当前正在看的那个人」（下钻进来时也要对得上）。 */
function sync(): void {
  const target = fallbackStudent.value
  const host = sections.value.find((s) => s.students.some((o) => o.id === target))
  if (host === undefined) {
    pickedSection.value = sections.value.length > 0 ? String(sections.value[0].id) : ''
    picked.value = ''
    return
  }
  pickedSection.value = String(host.id)
  picked.value = String(target)
}

onMounted(async () => {
  try {
    // ⚠️ 四个端点各一页就够（演示库实测：教师 3 行 / 班 5 行 / 选课 120 行 / 学生 60 行，
    //    都在 `limit` 的 200 上界之内）。⚠️ 而 `enrollments` 那一页对**教师**已经是
    //    收窄过的（`staff_taught`：只含他任教学生的选课行），故它天然 < 200；
    //    管理员那一档是全表，人数上到 100 人以上时**会溢出**。
    //    ⚠️ Plan 06 Task 11 / B4：溢出不再静默 —— 四个调用一律走 `listOnePage`，
    //    它把「服务端说一共有多少条 / 还差多少条」算成一句人话交给 `truncation`，
    //    模板末尾那个 `<p>` 把它画在跑道导航下面。
    const [teachers, allSections, enrollments, students] = await Promise.all([
      listOnePage(listTeachers, '教师名册'),
      listOnePage(listCourseSections, '教学班'),
      listOnePage(listEnrollments, '选课名册'),
      listOnePage(listStudents, '学生名册'),
    ])
    truncation.value = truncationNoteOf([teachers, allSections, enrollments, students])
    const me = teachers.items.find((t) => t.staff_no === session.staffNo) ?? null
    // ⚠️ 第一级：管理员列全部班，教师只列 `teacher_id == 我` 的
    //    （判据与 `AlertQueue.vue` 的 `mySections`、`ClassReport.vue` 的
    //    「只列我任教的」逐字同一条，三处各写一遍是这个仓既有的口径：
    //    「哪个班是我的」在前端是**展示**判据，后端的**授权**判据住在
    //    `app/api/deps.py` 的 `taught_section_ids`）。
    const mine = session.isAdmin
      ? allSections.items
      : allSections.items.filter((s) => me !== null && s.teacher_id === me.id)
    const labelOf = new Map(students.items.map((s) => [s.id, s]))
    const bySection = new Map<number, Option[]>()
    for (const row of enrollments.items) {
      const student = labelOf.get(row.student_id)
      if (student === undefined) continue
      const list = bySection.get(row.course_section_id) ?? []
      list.push({
        id: row.student_id,
        label: `#${row.student_id} · ${student.student_no} · ${student.name}`,
      })
      bySection.set(row.course_section_id, list)
    }
    sections.value = mine
      .map((s) => ({
        id: s.id,
        label: `#${s.id} · ${s.name}`,
        students: (bySection.get(s.id) ?? []).sort((a, b) => a.id - b.id),
      }))
      .sort((a, b) => a.id - b.id)
    sync()
  } catch (err) {
    // ⚠️ 导航拉不到名单**不该**成为一次页面级故障：那一格退化成「直接看学生 1」。
    listError.value = err instanceof Error ? err.message : String(err)
  }
})

// ⚠️ 下钻进来（`route.params.studentId` 变了）时把两级同步过去，
//    否则选择器会显示上一个人、而页面显示的是这一个。
watch(() => route.params.studentId, sync)

function go(): void {
  const id = Number(picked.value)
  if (Number.isInteger(id) && id > 0) void router.push(`/t/students/${id}`)
}
</script>

<template>
  <nav class="tnav" aria-label="教师端的四个页面">
    <template v-for="item in items" :key="item.name">
      <!-- 第 4 格：班 → 学生 两级选择器（⚠️ 不是链接，理由见文件头） -->
      <div v-if="item.isPicker" class="tnav__cell tnav__cell--picker" :class="{ 'tnav__cell--on': item.on }">
        <span class="tnav__lane num" aria-hidden="true">{{ item.lane }}</span>
        <span class="tnav__title zh-title">{{ item.title }}</span>
        <span class="tnav__caps caps" aria-hidden="true">{{ item.caps }}</span>
        <span class="tnav__pick">
          <template v-if="sections.length > 0">
            <!-- ⚠️ 两级：第一级选班（**只列我任教的**，管理员列全部），
                 第二级只列那个班的学生 —— 于是第二级里不可能出现一个点进去 403 的人
                 （Plan 06 Task 8：教师只读自己任教班级的学生行）。 -->
            <select
              v-model="pickedSection"
              class="tnav__select"
              aria-label="选一个我任教的教学班"
            >
              <option value="" disabled>选一个班…</option>
              <option v-for="sec in sections" :key="sec.id" :value="String(sec.id)">
                {{ sec.label }}（{{ sec.students.length }} 人）
              </option>
            </select>
            <select
              v-model="picked"
              class="tnav__select"
              aria-label="选一个学生看详情"
              :disabled="currentStudents.length === 0"
              @change="go"
            >
              <option value="" disabled>
                {{ currentStudents.length === 0 ? '这个班没有选课记录' : '选一个学生…' }}
              </option>
              <option v-for="opt in currentStudents" :key="opt.id" :value="String(opt.id)">
                {{ opt.label }}
              </option>
            </select>
            <span class="tnav__scope">{{ scopeNote }}</span>
          </template>
          <RouterLink v-else class="tnav__fallback" :to="item.to">
            {{ listError ? '名单读不到 · 直接看学生 1' : '名单加载中…' }}
          </RouterLink>
        </span>
      </div>

      <RouterLink
        v-else
        class="tnav__cell"
        :class="{ 'tnav__cell--on': item.on }"
        :to="item.to"
        :aria-current="item.on ? 'page' : undefined"
      >
        <span class="tnav__lane num" aria-hidden="true">{{ item.lane }}</span>
        <span class="tnav__title zh-title">{{ item.title }}</span>
        <span class="tnav__caps caps" aria-hidden="true">{{ item.caps }}</span>
      </RouterLink>
    </template>
  </nav>

  <!-- ⚠️ Plan 06 Task 11 / B4：`<nav>` 之外**第二个根节点**（Vue 3 支持多根）。
       放外面的理由：`.tnav` 是一个 4 列的 grid，把提示塞进去会占掉一格跑道；
       而 `v-if` 为假时它一个字节都不渲染，故今天的 DOM 逐字不变。 -->
  <p v-if="truncation" class="t-block__note">{{ truncation }}</p>
</template>

<style scoped>
/* ⚠️ Plan 05B：与学生端 `StudentNav` 同一套手法 ——
   ① 左端那条「竖过来的分道线」（`::before` 的 3px 竖条）删掉；
      `.tnav__lane` 自己长成那个 20×20 的主蓝序号方块（尺寸同读 `--chip-size`）；
   ② 原有 5 条 `.surface-board .tnav__xxx` 的覆盖（大屏是深底时的反白档）整组删掉：
      大屏翻浅底之后**全站只有一套颜色**，留着就是死配置。 */
.tnav {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-2);
}

.tnav__cell {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: var(--space-2);
  min-height: 62px;
  padding: var(--space-2) var(--space-3);
  background: var(--surface-raise);
  border: var(--border-hairline);
  border-radius: var(--radius);
  text-decoration: none;
  color: var(--ink-soft);
  overflow: hidden;
  transition:
    background-color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.tnav__cell:hover {
  border-color: var(--primary);
  background: var(--primary-faint);
  color: var(--primary-press);
}

/* 当前页：一整块主蓝（厦大蓝）+ 白字（13.06:1，过 AA） */
.tnav__cell--on {
  color: var(--on-primary);
  background: var(--primary);
  border-color: var(--primary);
}

.tnav__cell--on:hover {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
  color: var(--on-primary);
}

/* 序号方块：20×20、圆角、主蓝底、白字、居中（计划 §2 第 1 条）；选中态反白 */
.tnav__lane {
  display: grid;
  place-items: center;
  inline-size: var(--chip-size);
  block-size: var(--chip-size);
  border-radius: var(--chip-radius);
  background: var(--primary);
  color: var(--on-primary);
  font-family: var(--font-ui);
  font-size: var(--chip-font);
  font-weight: var(--fw-700);
  line-height: 1;
  font-variant-numeric: tabular-nums lining-nums;
}

.tnav__cell--on .tnav__lane {
  background: var(--on-primary);
  color: var(--primary);
}

.tnav__title {
  font-size: var(--fs-body);
  font-weight: var(--fw-700);
  line-height: 1.2;
  white-space: nowrap;
}

/* ⚠️ 字号从写死的 9px 抬到 `--fs-micro`（12px）：公共标识没有 9px 这一档。
   ⚠️ 它仍是 absolute 定位在右上角，与左上角的方块、底部的中文标题
      三者的矩形两两不相交（§4.1 的重叠守卫会实测这件事）。 */
.tnav__caps {
  position: absolute;
  inset-block-start: var(--space-2);
  inset-inline-end: var(--space-3);
  font-size: var(--fs-micro);
  letter-spacing: var(--tracking-caps);
  color: var(--ink-faint);
}

.tnav__cell--on .tnav__caps {
  color: var(--on-primary-dim);
}

/* ------------------------------------------------------------- 学生选择器 */
.tnav__pick {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.tnav__select {
  width: 100%;
  min-width: 0;
  padding: 2px var(--space-2);
  background: var(--surface-raise);
  border: 1px solid var(--border-input);
  border-radius: var(--radius-sm);
  font-family: var(--font-data);
  font-size: var(--fs-micro);
  color: var(--ink);
}

.tnav__select:disabled {
  color: var(--ink-faint);
  cursor: not-allowed;
}

/* ⚠️ 两级选择器下面那一行小字：它把「这一份名单是我任教的班」写在页面上，
   而不是让教师去猜「为什么下拉框里只有 41 个人」（Plan 06 Task 8）。 */
.tnav__scope {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tnav__fallback {
  font-size: var(--fs-micro);
  color: inherit;
  text-decoration: underline;
}
</style>

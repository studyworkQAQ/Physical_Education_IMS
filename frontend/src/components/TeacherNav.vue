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
 * ⚠️ 第 4 格不是一个链接，是一个**学生选择器**
 * ---------------------------------------------------------------------------
 * 那条路由是 `/t/students/:studentId`（Task 1 定的，⚠️ **带一个必填的路径参数**），
 * 而 `/t/students` 本身**不在**路由树里（打过去会被 catch-all 折回 `/s/home`）。
 * 故这一格做成一个 `<select>`：选一个人 → `router.push`。
 * 名单从 `GET /api/students?limit=200` 拉（匿名，60 人），**不硬编码**
 * （口径逐字同 Task 1 第 9 步对 `IdentitySwitcher` 的要求）。
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
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { listStudents } from '../api/endpoints'

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
      /** 道次编号 01–04：与 `LaneDivider` 同一套母题。 */
      lane: String(i + 1).padStart(2, '0'),
      on: route.name === name,
      isPicker: name === 'teacher-student-detail',
    }
  })
})

/* ------------------------------------------------------------- 学生名单 */
interface Option {
  id: number
  label: string
}

const options = ref<Option[]>([])
const picked = ref<string>('')
const listError = ref<string | null>(null)

onMounted(async () => {
  try {
    // ⚠️ 60 人 < 200 的 `limit` 上界，故一页就够（不必翻页收集）。
    const page = await listStudents({ limit: 200 })
    options.value = page.items.map((s) => ({
      id: s.id,
      label: `#${s.id} · ${s.student_no} · ${s.name}`,
    }))
    if (route.name === 'teacher-student-detail') picked.value = String(fallbackStudent.value)
  } catch (err) {
    // ⚠️ 导航拉不到名单**不该**成为一次页面级故障：那一格退化成「直接输学号」。
    listError.value = err instanceof Error ? err.message : String(err)
  }
})

function go(): void {
  const id = Number(picked.value)
  if (Number.isInteger(id) && id > 0) void router.push(`/t/students/${id}`)
}
</script>

<template>
  <nav class="tnav" aria-label="教师端的四个页面">
    <template v-for="item in items" :key="item.name">
      <!-- 第 4 格：学生选择器（⚠️ 不是链接，理由见文件头） -->
      <div v-if="item.isPicker" class="tnav__cell tnav__cell--picker" :class="{ 'tnav__cell--on': item.on }">
        <span class="tnav__lane num" aria-hidden="true">{{ item.lane }}</span>
        <span class="tnav__title zh-title">{{ item.title }}</span>
        <span class="tnav__caps caps" aria-hidden="true">{{ item.caps }}</span>
        <span class="tnav__pick">
          <select
            v-if="options.length > 0"
            v-model="picked"
            class="tnav__select"
            aria-label="选一个学生看详情"
            @change="go"
          >
            <option value="" disabled>选一个学生…</option>
            <option v-for="opt in options" :key="opt.id" :value="String(opt.id)">
              {{ opt.label }}
            </option>
          </select>
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
</template>

<style scoped>
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
  gap: var(--space-1);
  min-height: 62px;
  padding: var(--space-2) var(--space-3);
  background: var(--surface-raise);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  text-decoration: none;
  color: var(--ink-soft);
  overflow: hidden;
}

/* 左端那条竖线 = 分道线母题竖过来（粗线 3px 墨 + 偏移 6px 的 1px 砖红） */
.tnav__cell::before {
  content: '';
  position: absolute;
  inset-block: 0;
  inset-inline-start: 0;
  width: var(--bar-accent);
  background: var(--border);
}

.tnav__cell--on {
  color: var(--on-primary);
  background: var(--primary);
  border-color: var(--primary);
}

.tnav__cell--on::before {
  background: var(--primary);
}

/* 深底（大屏）上的那一档：导航要能被读出来，故反白 */
.surface-ink .tnav__cell {
  background: var(--surface-raise);
  border-color: var(--border);
  color: var(--ink-soft);
}

.surface-ink .tnav__cell--on {
  background: var(--primary);
  border-color: var(--primary);
  color: var(--ink);
}

.surface-ink .tnav__cell--on::before {
  background: var(--primary);
}

.tnav__lane {
  font-size: var(--chip-font);
  font-weight: var(--fw-700);
  letter-spacing: var(--primarying-caps);
  line-height: 1;
  color: var(--primary);
}

.tnav__cell--on .tnav__lane {
  color: var(--primary);
}

.surface-ink .tnav__cell--on .tnav__lane {
  color: var(--ink);
}

.tnav__title {
  font-size: var(--fs-body);
  font-weight: var(--fw-700);
  line-height: 1.2;
  white-space: nowrap;
}

.tnav__caps {
  position: absolute;
  inset-block-start: var(--space-2);
  inset-inline-end: var(--space-2);
  font-size: 9px;
  color: var(--ink-faint);
}

.tnav__cell--on .tnav__caps {
  color: var(--ink-faint);
}

.surface-ink .tnav__cell--on .tnav__caps {
  color: var(--ink);
}

/* ------------------------------------------------------------- 学生选择器 */
.tnav__pick {
  display: block;
  min-width: 0;
}

.tnav__select {
  width: 100%;
  padding: 2px var(--space-2);
  background: var(--surface-raise);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-family: var(--font-data);
  font-size: var(--fs-micro);
  color: var(--ink);
}

.surface-ink .tnav__select {
  background: var(--surface-sunken);
  border-color: var(--border);
  color: var(--on-primary);
}

.tnav__fallback {
  font-size: var(--fs-micro);
  color: inherit;
  text-decoration: underline;
}
</style>

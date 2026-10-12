<script setup lang="ts">
/**
 * `views/admin/ResourceIndex.vue` —— **23 个资源的目录**（`/admin`）。
 *
 * ---------------------------------------------------------------------------
 * 它渲染什么（计划 Task 4 + 派单第 3 节）
 * ---------------------------------------------------------------------------
 * 23 格，每格一个 `RouterLink` → `/admin/{resource}`（`ResourceList.vue`）。
 * **顺序 = `catalog/resources.ts` 那 23 行的顺序**（= 后端 `RESOURCES` 的顺序
 * = spec §4.1 → §4.7），故三处可以逐行对拍。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 只读的 14 个要「标出来并说明理由」（计划约束第 20 条）
 * ---------------------------------------------------------------------------
 * 两个手段，缺一不可：
 *  1. **视觉上**：只读那 14 格的左端竖线是砖红（`--primary`）、底色是 `--paper`
 *     而不是卡片的 `--surface-raise` —— 于是「哪些格子点进去没有写按钮」在
 *     滚动之前就能一眼扫出来（不是靠读 23 行小字）；
 *  2. **文字上**：每一格把 `catalog/resources.ts` 的 `readOnlyReason` **原样**显示。
 *     ⚠️ 那 14 段理由**不在本页写第二份**：目录是它们的唯一住址，
 *     本页只是把它们摊开来给人看。
 *
 * 而 `exercises` 与 `prescription-templates` 这两格额外单独成一段（下面第 03 块），
 * 因为它们是**唯一两处 spec 逐字点名**的（§4.4：「这是体育专家维护的知识资产……
 * 改阈值应走版本控制与评审，不应在运行时改数据库」），而且它们在演示库上
 * **还是空表** —— 两件事叠在一起，最容易被读成「数据丢了 + 页面坏了」。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 页面上那几个计数一律是**现算**的（`RESOURCES.filter(...)`）
 * ---------------------------------------------------------------------------
 * 23 / 9 / 14 / 12 / 10 / 1 / 8 这七个数**一个都不写死**：它们是目录的派生量，
 * 写死一份就是第二个所有者，而后端加第 24 个资源时它会先漂。
 * （第二道守卫在 Task 5 的 `smoke.mjs` 第 12 步：从 `/openapi.json` 反查目录。）
 */
import { computed } from 'vue'

import LaneDivider from '../../components/LaneDivider.vue'
import { RESOURCES } from '../../catalog/resources'
import { onDeleteZh } from '../../present'

/** 23 格。**顺序与目录逐行同序**。 */
const cells = computed(() =>
  RESOURCES.map((entry, i) => ({
    entry,
    lane: String(i + 1).padStart(2, '0'),
    to: `/admin/${entry.resource}`,
  })),
)

const total = computed(() => RESOURCES.length)
const writable = computed(() => RESOURCES.filter((r) => r.writable))
const readOnly = computed(() => RESOURCES.filter((r) => !r.writable))

/** `on_delete` 的三档计数。⚠️ 实测 `restrict` 12 / `forbid` 10 / `cascade` 1。 */
function countOnDelete(kind: string): number {
  return RESOURCES.filter((r) => r.onDelete === kind).length
}

/** **有 DELETE 端点的**资源数（实测 8）。⚠️ 它不等于「可写 − forbid」那么显然：
 *  `semesters` 是**可写 + forbid**，故 9 个可写资源里只有 8 个能删。 */
const deleteCount = computed(() => RESOURCES.filter((r) => r.hasDeleteEndpoint).length)

/** spec §4.4 逐字点名的那两格（本页给它们单独一块）。 */
const KNOWLEDGE_ASSETS = ['exercises', 'prescription-templates'] as const
const knowledgeCells = computed(() =>
  cells.value.filter((c) => (KNOWLEDGE_ASSETS as readonly string[]).includes(c.entry.resource)),
)
</script>

<template>
  <div class="a-page">
    <section class="lane-block" :style="{ '--lane-index': 0 }">
      <LaneDivider :index="1" label="ADMIN · RESOURCE INDEX" />
      <header class="a-head">
        <div>
          <h2 class="zh-title a-head__title">资源目录</h2>
          <p class="a-head__path data">/admin · {{ total }} resources</p>
        </div>
        <div class="a-head__meta">
          <span class="pill pill--green">可写 {{ writable.length }}</span>
          <span class="pill a-pill--neutral">只读 {{ readOnly.length }}</span>
          <span class="pill a-pill--neutral">DELETE 端点 {{ deleteCount }}</span>
        </div>
      </header>
    </section>

    <!-- ① 口径：这一台能做什么、不能做什么 -->
    <section class="lane-block" :style="{ '--lane-index': 1 }">
      <LaneDivider :index="2" label="HOW IT WORKS" />
      <div class="a-note">
        <span class="a-note__title">三个口径</span>
        <p>
          <strong>读是匿名的</strong>：{{ total }} 个资源的列表与详情都不需要身份
          （后端 48 个匿名 GET 里就包括这 23 个 list 与 23 个 read-one）。
        </p>
        <p>
          <strong>写要教师身份</strong>：{{ writable.length }} 个可写资源的
          POST / PATCH / DELETE 全挂了 <code class="data">require_teacher</code>，
          匿名写是 <code class="data">401 unauthenticated</code>。
          故在没选教师身份时，「新建 / 编辑 / 删除」按钮<strong>不出现</strong>
          —— 页面上会写明要先去左上角的身份切换器选一个教师。
        </p>
        <p>
          <strong>删除策略三档</strong>：
          <code class="data">restrict</code> {{ countOnDelete('restrict') }} 个
          （{{ onDeleteZh('restrict') }}）、
          <code class="data">forbid</code> {{ countOnDelete('forbid') }} 个
          （{{ onDeleteZh('forbid') }}）、
          <code class="data">cascade</code> {{ countOnDelete('cascade') }} 个
          （{{ onDeleteZh('cascade') }}）。
          ⚠️ <code class="data">forbid</code> 的那
          {{ countOnDelete('forbid') }} 个<strong>根本不注册 DELETE 端点</strong>
          （打过去是 <code class="data">405 http_405</code>），故它们的删除按钮
          也是<strong>不出现</strong>，不是禁用。
        </p>
      </div>
    </section>

    <!-- ② 23 格 -->
    <section class="lane-block" :style="{ '--lane-index': 2 }">
      <LaneDivider :index="3" label="23 RESOURCES" />
      <div class="a-index">
        <RouterLink
          v-for="cell in cells"
          :key="cell.entry.resource"
          class="a-index__cell"
          :class="{ 'a-index__cell--ro': !cell.entry.writable }"
          :to="cell.to"
        >
          <span class="a-index__head">
            <span class="a-index__lane num" aria-hidden="true">{{ cell.lane }}</span>
            <span class="a-index__title zh-title">{{ cell.entry.titleZh }}</span>
          </span>
          <code class="a-index__slug data">{{ cell.entry.path }}</code>
          <span class="a-index__badges">
            <span v-if="cell.entry.writable" class="pill pill--green">可写</span>
            <span v-else class="pill a-pill--neutral">只读</span>
            <span class="pill a-pill--neutral data">
              on_delete={{ cell.entry.onDelete }}
            </span>
            <span v-if="!cell.entry.hasDeleteEndpoint" class="pill a-pill--ink">无 DELETE</span>
          </span>
          <span v-if="cell.entry.readOnlyReason" class="a-index__reason">
            {{ cell.entry.readOnlyReason }}
          </span>
        </RouterLink>
      </div>
    </section>

    <!-- ③ spec §4.4 逐字点名的那两格 -->
    <section class="lane-block" :style="{ '--lane-index': 3 }">
      <LaneDivider :index="4" level="amber" label="KNOWLEDGE ASSETS" />
      <div class="a-note">
        <span class="a-note__title">为什么这两格是刻意只读的（spec §4.4 逐字）</span>
        <blockquote>
          「这是体育专家维护的知识资产……改阈值应走版本控制与评审，不应在运行时改数据库。」
        </blockquote>
        <p v-for="cell in knowledgeCells" :key="cell.entry.resource">
          <strong>{{ cell.entry.titleZh }}</strong>
          <code class="data">{{ cell.entry.path }}</code> ——
          {{ cell.entry.emptyNote ?? cell.entry.readOnlyReason }}
        </p>
        <p>
          ⚠️ 于是这两格在管理台里点进去<strong>大概率是 0 行</strong>（演示库上确实是 0 行），
          而<strong>那不是数据丢了</strong>：处方装配读的是 YAML 的进程内只读单例，
          一次都不查这两张表。列表页会把上面那两段解释原样显示在空态里。
        </p>
      </div>
    </section>
  </div>
</template>

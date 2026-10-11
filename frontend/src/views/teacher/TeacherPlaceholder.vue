<script setup lang="ts">
/**
 * `views/teacher/TeacherPlaceholder.vue` —— **教师端 4 条路由的占位页**。
 *
 * ⚠️ Task 3 会把 `router/index.ts` 里 `/t/*` 那 4 条的 `component:` 逐个换成
 * `Dashboard`（大屏）/ `ClassReport` / `AlertQueue` / `StudentDetail`，然后删掉本文件。
 *
 * ⚠️ 它与学生端那个占位页**刻意不是同一个组件**，差在两处：
 *  1. `LaneDivider` 的 `tone` 跟着 `meta.surface` 走 —— `/t/dashboard` 是深底，
 *     分道线的粗线要换成 `--paper`、细线换成 `--track-on-ink`，否则投影上看不见；
 *  2. 多一行「大屏口径」的提示（1440px、字号下限 18px、5 秒轮播教学班）。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import LaneDivider from '../../components/LaneDivider.vue'
import StatBlock from '../../components/StatBlock.vue'
import { useIdentityStore } from '../../stores/identity'

const route = useRoute()
const identity = useIdentityStore()

const isBigScreen = computed(() => route.meta.surface === 'ink')
const tone = computed<'paper' | 'ink'>(() => (isBigScreen.value ? 'ink' : 'paper'))
</script>

<template>
  <section class="placeholder">
    <LaneDivider :index="1" :tone="tone" label="TEACHER · WALL · 1440PX" />

    <h2 class="zh-title placeholder__title">{{ route.meta.title }}</h2>

    <p class="placeholder__lead">
      这一页是<strong>占位</strong>。它由 <strong>{{ route.meta.task }}</strong> 落地。
    </p>

    <p v-if="route.meta.intent" class="placeholder__intent">
      <span class="caps">将要做的事</span>
      <span class="data">{{ route.meta.intent }}</span>
    </p>

    <p v-if="isBigScreen" class="placeholder__bigscreen">
      <span class="caps">大屏口径</span>
      深底 <code class="data">--ink</code> · 字号下限 <code class="data">18px</code>（投影场景）·
      5 秒自动轮播教学班 · 不对称网格：预警队列跨
      <code class="data">5</code> 列 / 分层分布跨 <code class="data">4</code> 列 / 本周概览跨
      <code class="data">3</code> 列（⚠️ 刻意不均分三列）。
    </p>

    <LaneDivider :index="2" :tone="tone" level="red" label="ALERTS" />

    <div class="placeholder__stats">
      <!-- ⚠️ 三个 StatBlock 证明深底那一档也能渲染：一个真数、一个 null（→「—」）、
           一个红色语义（预警数）。 -->
      <StatBlock :value="null" label="待处置预警" tone="paper" caption="null → 「—」，不是 0" />
      <StatBlock
        :value="null"
        label="三层完成率"
        unit="%"
        :decimals="1"
        :tone="tone"
        level="red"
        caption="演示库实测 0.5–0.79（Task 3 会填真数）"
      />
      <StatBlock
        :value="null"
        label="本周减量系数"
        :tone="tone"
        size="hero"
        caption="0.8 = 减量 20%（一处方一周至多一条 auto 调整）"
      />
    </div>

    <p class="placeholder__note">
      业务日 <code class="data">{{ identity.asOf }}</code> ·
      ⚠️ <code class="data">weekly_class_report</code> 只在<strong>周日</strong>生成，
      故周中读本周的周报会 404 <code class="data">no_weekly_report</code>
      —— 要显示「本周周报将在周日生成」，<strong>不要</strong>显示一堆 0。
    </p>
  </section>
</template>

<style scoped>
.placeholder__title {
  font-size: var(--fs-title);
  margin-block: var(--space-3) var(--space-2);
}

.placeholder__lead {
  font-size: var(--fs-body);
  color: var(--ink-soft);
}

.surface-ink .placeholder__lead {
  color: var(--paper-soft);
}

.placeholder__intent,
.placeholder__bigscreen {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-block-start: var(--space-3);
  padding: var(--space-3);
  background: var(--paper-sunken);
  font-size: var(--fs-small);
}

.placeholder__bigscreen {
  border-inline-start: var(--lane-thick) solid var(--track);
}

.placeholder__intent .caps,
.placeholder__bigscreen .caps {
  color: var(--ink-faint);
}

.surface-ink .placeholder__intent,
.surface-ink .placeholder__bigscreen {
  background: var(--ink-sunken);
  color: var(--paper-soft);
}

.surface-ink .placeholder__intent .caps,
.surface-ink .placeholder__bigscreen .caps {
  color: var(--paper-faint);
}

.surface-ink .placeholder__bigscreen {
  border-inline-start-color: var(--track-on-ink);
}

.placeholder__stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-4);
  margin-block-start: var(--space-3);
}

.placeholder__note {
  margin-block-start: var(--space-4);
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.surface-ink .placeholder__note {
  color: var(--paper-faint);
}
</style>

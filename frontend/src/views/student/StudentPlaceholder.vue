<script setup lang="ts">
/**
 * `views/student/StudentPlaceholder.vue` —— **学生端 6 条路由的占位页**。
 *
 * ⚠️ Task 2 会把 `router/index.ts` 里 `/s/*` 那 6 条的 `component:` 逐个换成
 * `Home` / `WeeklySheet` / `CheckIn` / `RpeEntry` / `MiniTest` / `Notifications`，
 * 然后删掉本文件。它今天存在的**全部理由**是：没有它，`npm run dev` 打开
 * `/s/home` 是白屏，而白屏无法验收「壳与身份切换器通了」。
 *
 * ⚠️ 但它**不是**一块空白：它把这一页将来要打的端点（`meta.intent`）与
 * 归属的 Task（`meta.task`）显示出来，于是「这是占位」不会被下一个人误读成 bug。
 */
import { useRoute } from 'vue-router'

import LaneDivider from '../../components/LaneDivider.vue'
import StatBlock from '../../components/StatBlock.vue'
import { useIdentityStore } from '../../stores/identity'

const route = useRoute()
const identity = useIdentityStore()
</script>

<template>
  <section class="placeholder">
    <LaneDivider :index="1" label="STUDENT · H5 · 375PX" />

    <h2 class="zh-title placeholder__title">{{ route.meta.title }}</h2>

    <p class="placeholder__lead">
      这一页是<strong>占位</strong>。它由 <strong>{{ route.meta.task }}</strong> 落地。
    </p>

    <p v-if="route.meta.intent" class="placeholder__intent">
      <span class="caps">将要做的事</span>
      <span class="data">{{ route.meta.intent }}</span>
    </p>

    <LaneDivider :index="2" label="AS OF" />

    <div class="placeholder__stats">
      <!-- ⚠️ 三个 StatBlock 是**承重的**：它们证明设计系统的三档口径都能渲染 ——
           ① 一个真数（学生 id）② 一个 null（→「—」，⚠️ 不是 0，约束第 10 条）
           ③ 一个大号的计时牌数字（数字滚动动效）。 -->
      <StatBlock
        :value="identity.studentId"
        label="当前学生 id"
        caption="X-Student-Id 请求头带的就是它"
      />
      <StatBlock
        :value="null"
        label="本周训练量"
        unit="min"
        caption="null → 显示「—」，不显示 0"
      />
      <StatBlock
        :value="identity.studentId ?? 0"
        label="占位的大数字"
        size="hero"
        tone="paper"
        caption="Task 2 会把它换成真的本周训练量"
      />
    </div>

    <p class="placeholder__note">
      业务日 <code class="data">{{ identity.asOf }}</code> ·
      ⚠️ 演示库的业务日是 <code class="data">2025-10-12</code>（学期第 6 周的周日），
      用别的日期会查不到数据。
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

.placeholder__intent {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-block-start: var(--space-3);
  padding: var(--space-3);
  background: var(--paper-sunken);
  font-size: var(--fs-small);
}

.placeholder__intent .caps {
  color: var(--ink-faint);
}

.placeholder__stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--space-4);
  margin-block-start: var(--space-3);
}

.placeholder__note {
  margin-block-start: var(--space-4);
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}
</style>

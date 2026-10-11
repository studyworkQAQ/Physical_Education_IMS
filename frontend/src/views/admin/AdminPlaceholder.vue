<script setup lang="ts">
/**
 * `views/admin/AdminPlaceholder.vue` —— **管理台 3 条路由的占位页**。
 *
 * ⚠️ Task 4 会把 `router/index.ts` 里 `/admin/*` 那 3 条的 `component:` 逐个换成
 * `ResourceIndex` / `ResourceList` / `ResourceDetail`，然后删掉本文件。
 *
 * ⚠️ Task 4 的口径**今天就钉在这里**（那三条路由的 `meta.intent` 逐字写着）：
 * 一个通用组件 + 一份 23 行的资源目录（`catalog/resources.ts`），
 * **不是 23 套页面** —— 那会产生 23 份互相不一致的分页/错误/空态行为。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import LaneDivider from '../../components/LaneDivider.vue'
import { RESOURCES } from '../../catalog/resources'

const route = useRoute()

/** 路径参数 `:resource`（列表页与详情页有，目录页没有）。 */
const resourceParam = computed(() => String(route.params.resource ?? ''))
const idParam = computed(() => String(route.params.id ?? ''))

const matched = computed(() => RESOURCES.find((r) => r.resource === resourceParam.value))

/** 23 行目录的实时计数。⚠️ 它是 `catalog/resources.ts` 与后端
 *  `app/api/routers/catalog.py` 的 `RESOURCES` 之间的**第一道**对拍
 *  （第二道在 Task 5 的联调脚本里，从 `/openapi.json` 反查）。 */
const writableCount = computed(() => RESOURCES.filter((r) => r.writable).length)
const readOnlyCount = computed(() => RESOURCES.length - writableCount.value)
</script>

<template>
  <section class="placeholder">
    <LaneDivider :index="1" label="ADMIN · CRUD · 23 RESOURCES" />

    <h2 class="zh-title placeholder__title">{{ route.meta.title }}</h2>

    <p class="placeholder__lead">
      这一页是<strong>占位</strong>。它由 <strong>{{ route.meta.task }}</strong> 落地。
    </p>

    <p v-if="route.meta.intent" class="placeholder__intent">
      <span class="caps">将要做的事</span>
      <span class="data">{{ route.meta.intent }}</span>
    </p>

    <LaneDivider :index="2" label="CATALOG" />

    <p class="placeholder__counts num">
      目录里 <strong>{{ RESOURCES.length }}</strong> 个资源 ·
      可写 <strong>{{ writableCount }}</strong> · 只读 <strong>{{ readOnlyCount }}</strong>
    </p>

    <p v-if="resourceParam" class="placeholder__intent">
      <span class="caps">当前路径参数</span>
      <span class="data">
        resource = {{ resourceParam }}<template v-if="idParam"> · id = {{ idParam }}</template>
      </span>
      <span v-if="matched" class="data">
        ✓ 目录里有这一行：{{ matched.titleZh }} · writable={{ matched.writable }} ·
        on_delete={{ matched.onDelete }}
      </span>
      <span v-else class="placeholder__bad">
        ✗ 目录里<strong>没有</strong>这一行 —— 会渲染成「未知资源」，不是白屏。
      </span>
    </p>

    <LaneDivider :index="3" level="amber" label="READ ONLY" />

    <p class="placeholder__note">
      ⚠️ 只读的那 {{ readOnlyCount }} 个资源，「新建 / 编辑 / 删除」按钮要
      <strong>不出现</strong>（不是禁用）。理由（spec §4.4 逐字）：
      <code class="data">exercises</code> 与 <code class="data">prescription-templates</code>
      是体育专家维护的知识资产，改阈值应走版本控制与评审，不应在运行时改数据库；
      其余只读资源是批处理产物（<code class="data">on_delete='forbid'</code>），
      DELETE 端点根本不注册，打过去是 <code class="data">405</code>。
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

.placeholder__counts {
  margin-block-start: var(--space-3);
  font-size: var(--fs-body);
}

.placeholder__bad {
  color: var(--red-on-paper);
}

.placeholder__note {
  margin-block-start: var(--space-3);
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}
</style>

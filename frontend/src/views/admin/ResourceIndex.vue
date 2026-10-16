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
 * ⚠️⚠️ **Plan 06 Task 9 起本页还有第 04 块**（`NOT A RESOURCE`）：审计留痕只读页
 * （`/admin/audit-logs`）的入口。⚠️ 它**刻意不在**那 23 格里、也**刻意不改**
 * `cells` / `total` / `writable` / `readOnly` 那四个 computed —— `audit_log`
 * **不是资源**（它是特例端点，同 `/api/health` 那一族，后端连 `PATCH` / `DELETE`
 * 都不注册），把它塞进 `RESOURCES` 会让后端 `test_crud.py` 那张读写矩阵的三格数字
 * （23 / 9 / 14）与 `smoke.mjs` 第 12 步的反查一起红。⚠️ 而**没有入口的页面等于不存在**
 * （深链接只有取证脚本会走），故它单独成一块、并写明「为什么它不在那 23 格里」。
 *
 * 而 `exercises` 与 `prescription-templates` 这两格额外单独成一段（下面第 03 块），
 * 因为它们是**唯一两处 spec 逐字点名**的（§4.4：「这是体育专家维护的知识资产……
 * 改阈值应走版本控制与评审，不应在运行时改数据库」），而且它们在演示库上
 * **还是空表** —— 两件事叠在一起，最容易被读成「数据丢了 + 页面坏了」。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 页面上那几个计数一律是**现算**的（`RESOURCES.filter(...)`）
 * ---------------------------------------------------------------------------
 * 23 / 9 / 14 / 12 / 10 / 1 / 8 / 26 这八个数**一个都不写死**：它们是目录的派生量，
 * 写死一份就是第二个所有者，而后端加第 24 个资源时它会先漂。
 * （第二道守卫在 Task 5 的 `smoke.mjs` 第 12 步：从 `/openapi.json` 反查目录。）
 * ⚠️⚠️ **例外是下面那两个（`ANONYMOUS_READABLE` / `ANONYMOUS_GETS`）**：
 * 它们派生不出来（前端目录刻意不带 `read_scope` 那一格），故写死 + 由守卫钉住，
 * 逐字理由与来历写在它们自己那一段注释里。
 */
import { computed } from 'vue'

import SectionHead from '../../components/SectionHead.vue'
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

/** 泛型 CRUD 的写入操作数：9 个 POST + 9 个 PATCH + **8** 个 DELETE
 *  （`on_delete='forbid'` 那 10 个根本不注册 DELETE，而 `semesters` 是「可写 + forbid」那一个）。
 *  ⚠️ 它**能**现算，故不写死（与下面那两个不同）。 */
const writeOps = computed(() => writable.value.length * 2 + deleteCount.value)

/* ---------------------------------------------------------------------------
 * ⚠️⚠️ 本页**唯一**两处写死的计数（Plan 06 Task 15 / 终审 S2-①）
 * ---------------------------------------------------------------------------
 * 「哪几行匿名可读」的唯一所有者是后端 `app/api/routers/catalog.py` 的
 * `read_scope` 那一列（五档表在它的模块 docstring 里：**7** 行 `None` /
 * **13** 行 `staff_taught` / **1** 行 `staff_taught_section` / **2** 行 `staff` /
 * **0** 行 `student_self`），而**前端目录 `catalog/resources.ts` 刻意不带这一格**
 * （它带的是渲染要用的 `writable` / `onDelete` / `displayFields`），
 * 故本页**无从派生**它们。
 *
 * ⚠️ 于是这两个数是**刻意的第二所有者**，而它由两道守卫钉住
 * （与本仓既有的 `_MODELS_PUBLIC_BASELINE` 钉 33、18 个模板钉 sha256 同一条姿势）：
 *  1. `scripts/smoke.mjs` 第 12 步**从 `/openapi.json` 现量**「没有 `security` 键的 GET
 *     有几个」与「23 个资源里集合 GET 匿名的有几个」，再与本文件这两个字面量对拍
 *     （期望侧 = openapi 的 `security` 键在不在，被测侧 = 本文件，两侧不同源）；
 *  2. 第 14 步的 admin-index 那一拍钉「页面上真的印着那三句、且每句**只印一次**」。
 *
 * ⚠️ 来历（如实记）：终审 S2-① 查出改前这一段逐字写着「**读是匿名的**：
 * 23 个资源的列表与详情都不需要身份（后端 **48 个匿名 GET** 里就包括这 23 个
 * list 与 23 个 read-one）」「**写要教师身份**……全挂了 `require_teacher`」
 * 「要先去左上角的身份切换器选一个教师」—— 三句**全是假话**（本波自己重新实测，
 * 不抄终审报告）：匿名可读的只有 **7** 个（另 **16** 个匿名 list 一律 **401**）、
 * openapi 上匿名 GET 是 **15** 个（匿名操作共 **18** 个 = 15 GET + 3 POST：登录与两个绑定）、
 * 写侧挂的是 `require_admin`（教师 T0001 实测 **403**「不是管理员」，不是 200）、
 * `require_teacher` 这个名字自 Plan 05A Task 2 起**已不存在**（改名 `require_staff`，
 * 而管理台走的不是它）、身份切换器那两个下拉框是 **DEV-only**
 * （判据是编译期常量 `import.meta.env.DEV`，产品构建里整个被摇掉）。
 */
/** 匿名可读的资源数（= 后端 `read_scope=None` 那 7 行；名单印在模板那一句里）。 */
const ANONYMOUS_READABLE = 7
/** openapi 上没有 `security` 键的 **GET** 数（= 7 个 list + 7 个 read-one + `/api/health`）。 */
const ANONYMOUS_GETS = 15
</script>

<template>
  <div class="a-page">
    <section class="">
      <SectionHead :index="1" label="ADMIN · RESOURCE INDEX" />
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
    <section class="">
      <SectionHead :index="2" label="HOW IT WORKS" />
      <div class="a-note">
        <span class="a-note__title">三个口径</span>
        <p>
          <strong>读要身份，只有 {{ ANONYMOUS_READABLE }} 个例外</strong>：
          {{ total }} 个资源里匿名可读的只有那 {{ ANONYMOUS_READABLE }} 个
          <strong>不含任何学生键</strong>的参考数据（学期 / 教学班 / 体测批次 /
          百分位快照 / 动作库 / 处方模板 / 课堂课次），另
          {{ total - ANONYMOUS_READABLE }} 个一律要 <code class="data">pe_session</code> cookie
          —— 匿名打过去是 <code class="data">401 unauthenticated</code>。
          ⚠️ 那 {{ total - ANONYMOUS_READABLE }} 个还各有一道<strong>范围闸门</strong>：
          <code class="data">students</code> / <code class="data">teachers</code> 两行是
          「任何在册教职」（⚠️ 它们正是绑定口令的验身材料，故匿名一律不给），
          13 行是「教师只读自己<strong>本学期任教班</strong>的学生」，
          1 行（<code class="data">weekly-class-reports</code>）是「只读自己本学期任教的班」。
          学生会话只读得到自己那一份。
          （后端 openapi 上匿名 GET 一共 {{ ANONYMOUS_GETS }} 个 = 这
          {{ ANONYMOUS_READABLE }} 个资源的 list 与 read-one 各 {{ ANONYMOUS_READABLE }} 个
          + <code class="data">/api/health</code>；另有 3 个匿名 POST = 登录与两个绑定。）
        </p>
        <p>
          <strong>写仅管理员</strong>：{{ writable.length }} 个可写资源的
          POST / PATCH / DELETE（一共 {{ writeOps }} 个操作）一律挂
          <code class="data">require_admin</code>：匿名是 <code class="data">401 unauthenticated</code>，
          学生是 <code class="data">403 forbidden</code>，而一个
          <code class="data">role='teacher'</code> 的<strong>普通教师也是
          <code class="data">403</code></strong>（报文逐字是「不是管理员」）。
          故没登录成管理员时，「新建 / 编辑 / 删除」按钮<strong>不出现</strong>。
          ⚠️ 课堂功能（大屏 / 周报 / 三源采集 / 预警处置）走的是
          <strong>另一道</strong>闸门 <code class="data">require_staff</code>（教师或管理员都放行），
          不受这一格影响（读写两侧的完整五档口径见 spec §13.4.4）。
        </p>
        <p>
          <strong>身份从哪来</strong>：<code class="data">/login</code> 页登录
          （<code class="data">POST /api/auth/login</code> 换一个 <code class="data">HttpOnly</code> 的
          <code class="data">pe_session</code> cookie；首次使用先走 <code class="data">/bind</code>
          自绑口令）。⚠️ 报头下面那条会话栏在<strong>产品档</strong>上
          只有「当前身份 + 登出」；那两个身份下拉框是 <strong>DEV-only</strong>
          的开发工具（判据是编译期常量 <code class="data">import.meta.env.DEV</code>，
          生产构建里整个被摇掉），故<strong>换身份请登出再登录</strong>，
          不要去找切换器。
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
    <section class="">
      <SectionHead :index="3" label="23 RESOURCES" />
      <div class="a-index">
        <RouterLink
          v-for="cell in cells"
          :key="cell.entry.resource"
          class="a-index__cell"
          :class="{ 'a-index__cell--ro': !cell.entry.writable }"
          :to="cell.to"
        >
          <span class="a-index__head">
            <span class="a-index__chip num" aria-hidden="true">{{ cell.lane }}</span>
            <span class="a-index__title zh-title">{{ cell.entry.titleZh }}</span>
          </span>
          <code class="a-index__slug data">{{ cell.entry.path }}</code>
          <span class="a-index__badges">
            <span v-if="cell.entry.writable" class="pill pill--green">可写</span>
            <span v-else class="pill a-pill--neutral">只读</span>
            <span class="pill a-pill--neutral data">
              on_delete={{ cell.entry.onDelete }}
            </span>
            <span v-if="!cell.entry.hasDeleteEndpoint" class="pill a-pill--solid">无 DELETE</span>
          </span>
          <span v-if="cell.entry.readOnlyReason" class="a-index__reason">
            {{ cell.entry.readOnlyReason }}
          </span>
        </RouterLink>
      </div>
    </section>

    <!-- ③ spec §4.4 逐字点名的那两格 -->
    <section class="">
      <SectionHead :index="4" level="amber" label="KNOWLEDGE ASSETS" />
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

    <!-- ④ 不是资源的那一页（Plan 06 Task 9）：审计留痕只读页的入口。
         ⚠️ 复用上面那 23 格的同一批 class（`.a-index` / `.a-index__cell--ro` /
         `.pill`），故本页**没有新增一行 CSS** —— ⚠️ `npm run check:tokens` 的扫描面
         35 → **36** 个文件只是因为多了一个 `.vue`（`AuditLogList.vue`），
         而它的结论一字未变：「tokens.css 之外一个色值字面量都没有」（下界是 25）。
         ⚠️ 序号方块刻意**不画**：那 23 格用它当「第几个资源」，而本页这一格
         不是资源，画一个 24 就是一句假话。 -->
    <section class="">
      <SectionHead :index="5" label="NOT A RESOURCE" />
      <div class="a-index">
        <RouterLink class="a-index__cell a-index__cell--ro" to="/admin/audit-logs">
          <span class="a-index__head">
            <span class="a-index__title zh-title">审计留痕</span>
          </span>
          <code class="a-index__slug data">/admin/audit-logs · GET /api/audit-logs</code>
          <span class="a-index__badges">
            <span class="pill a-pill--solid">只读</span>
            <span class="pill a-pill--neutral data">仅 role=admin</span>
            <span class="pill a-pill--neutral data">不在那 {{ total }} 格里</span>
          </span>
          <span class="a-index__reason">
            ⚠️ <code class="data">audit_log</code> 是<strong>特例端点</strong>（同
            <code class="data">/api/health</code> 那一族），故它<strong>不在</strong>
            <code class="data">catalog/resources.ts</code> 那 {{ total }} 行里：
            后端连 <code class="data">PATCH</code> / <code class="data">DELETE</code>
            都不注册（不可改写是审计的第一条性质），泛型 CRUD 那一套对它无意义。
            ⚠️ 那一页画的是 <code class="data">AuditLogRead</code> 的<strong>九格</strong>
            （全是标量），<strong>一个请求体都不落</strong> —— 那张表的 9 列里
            根本没有能装请求体的位置，故那是一条<strong>结构性质</strong>、
            不是「克制住不写」。
          </span>
        </RouterLink>
      </div>
    </section>
  </div>
</template>

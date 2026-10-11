<script setup lang="ts">
/**
 * `views/student/Notifications.vue` —— 消息中心（`/s/notifications`）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 端点路径：**实测过两轮**，第二轮把第一轮的答案改掉了
 * ---------------------------------------------------------------------------
 * Task 2 实测的结论是「`GET /api/students/{id}/notifications` **不存在**」，含
 * `notification` 的路径只有三条（匿名的 list、匿名的 detail、学生头的 `read`），
 * 故本页当时走「匿名 list 翻页收集 + 客户端过滤
 * `recipient_kind === 'student' && recipient_id === 我`」。那一处顶回了控制者，
 * 控制者裁定**补上那个端点**，于是 Plan 04 Task 3 的后端小修波加了：
 *
 *     GET  /api/students/{student_id}/notifications   security = [{"X-Student-Id": []}]
 *
 * 本页现在读它（`endpoints.ts` 的 `listStudentNotifications`）。
 * ⚠️ **加它的理由不是堵洞**：`GET /api/notifications` 今天仍然是匿名的、
 * 仍然一次能读到全部 19 条 —— 那是本仓「读 ⇒ 一律匿名」的既有口径
 * （48 个匿名 GET 里已经包括 `GET /api/students`，它给的是 60 个人的出生日期）。
 * 理由是**前端的代价**：泛型 list 没有筛选参数，故「发给我的」此前只能拉全表再筛。
 *
 * ⚠️ **服务端已经排好序**（`created_at` 降序、同刻按 `id` 降序 tie-break），
 * 故本页**不再** `.sort()` —— 「新的在上面」这件事现在只有一个住址（后端）。
 * Task 2 交付时那一行 `.sort()` 是必需的（匿名 list 给的是 `id` 升序）。
 *
 * ---------------------------------------------------------------------------
 * `POST /api/notifications/{id}/read` 的两档
 * ---------------------------------------------------------------------------
 *  - 200：只改 `is_read`、**不删行**（`notification` 是 `on_delete='forbid'`
 *    且刻意不带 `batch_id`，故「从任何入口都删不掉一行通知」是有意的）；
 *  - **403 `not_recipient`**：那条消息不是发给请求头里这个学生的
 *    —— **或它根本不存在**（两档刻意同形：`notification.id` 是连续代理键，
 *    区分两者等于让「扫一遍 id」成为一次有效探测）。本页给这一档一句人话。
 *  ⚠️ 而**列表**那一侧的越权是 **403 `forbidden`**（`require_scope` 的既有口径，
 *    与首页同档），两档 code 不同是**有意的**：一个按主键改行、一个按收件人列行。
 */
import { computed, ref } from 'vue'

import { ApiError } from '../../api/client'
import { listMyNotifications, markNotificationRead } from '../../api/endpoints'
import type { NotificationListItem } from '../../api/types'
import LaneDivider from '../../components/LaneDivider.vue'
import StudentNav from '../../components/StudentNav.vue'
import { useAsync } from '../../composables/useAsync'
import { useIdentityStore } from '../../stores/identity'
import { UNKNOWN, channelZh, stampOf } from '../../present'

const identity = useIdentityStore()

const { data, loading, settled, reload } = useAsync(async () => {
  const id = identity.studentId
  if (id === null) return null
  return listMyNotifications(id)
})

/** ⚠️ **不再排序**：服务端已经按 `created_at` 降序（同刻按 `id` 降序）给过来了。
 *  Task 2 交付时这里有一行 `.sort((a, b) => b.created_at.localeCompare(a.created_at) || b.id - a.id)`，
 *  因为匿名 list 给的是 `id` 升序。Plan 04 Task 3 的小修波把排序搬进了后端
 *  （`dashboard.py` 的 `student_notifications`），于是「新的在上面」只有一个住址。
 *  守卫在后端：`tests/api/test_dashboard.py` 的
 *  `test_the_notification_list_returns_only_the_requesters_rows_newest_first`。 */
const items = computed<NotificationListItem[]>(() => data.value?.items ?? [])

const unreadCount = computed(() => items.value.filter((n) => !n.is_read).length)
const totalCount = computed(() => items.value.length)

/* ------------------------------------------------------------- 标已读 */
const busy = ref<number | null>(null)
const readError = ref<{ id: number; error: ApiError } | null>(null)

async function markRead(id: number): Promise<void> {
  if (busy.value !== null) return
  busy.value = id
  readError.value = null
  try {
    await markNotificationRead(id)
    // ⚠️ 重读而不是就地改 `is_read`：响应体就是那一行的最新状态（`NotificationRead`），
    //    但重读能顺带把「别的入口又推了一条」也拿进来，且只有一个数据住址。
    await reload()
  } catch (err) {
    if (err instanceof ApiError) readError.value = { id, error: err }
    else console.error('[notifications]', err)
  } finally {
    busy.value = null
  }
}

/** 403 `not_recipient` 那一档的人话（派单要求「这一档要处理」）。 */
function adviceFor(code: string): string {
  if (code === 'not_recipient') {
    return '这条消息不是发给你的（或者它根本不存在 —— 后端刻意让这两档同形：`notification.id` 是连续代理键，区分两者等于让「扫一遍 id」成为一次有效探测）。'
  }
  if (code === 'unauthenticated') return '没有带上 `X-Student-Id`：请在身份切换器里选一个学生。'
  if (code === 'not_found') return '这条消息的 id 不存在。'
  return ''
}

/** 通知的 `title` 实测只有两种（演示库：13 条勋章 + 6 条补练提醒）。
 *  ⚠️ 认不出来的**原样带出**（不按 `message` 字符串匹配，约束第 8 条同一族）。 */
function kindOf(item: NotificationListItem): 'badge' | 'makeup' | 'other' {
  if (item.title.includes('勋章')) return 'badge'
  if (item.title.includes('补练')) return 'makeup'
  return 'other'
}
</script>

<template>
  <div class="s-page">
    <StudentNav />

    <div v-if="identity.studentId === null" class="s-empty">
      <p class="s-empty__title zh-title">还不知道你是谁</p>
      <p class="s-empty__note">
        「发给我的消息」里的「我」就是 <code>X-Student-Id</code>。
        没选身份时本页只显示空态 —— 它<strong>不会</strong>把库里那 19 条都倒出来
        （那里面有发给别人的）。
      </p>
    </div>

    <div v-else-if="loading && !settled" class="s-loading">
      <span class="s-loading__rule" aria-hidden="true"></span>
      <span>正在收站内消息…</span>
    </div>

    <template v-else>
      <header class="s-head">
        <p class="caps s-head__kicker">INBOX · IN_APP · {{ identity.asOf }}</p>
        <h2 class="zh-title s-head__title">消息中心</h2>
        <p class="s-head__meta">
          未读 <strong class="num">{{ unreadCount }}</strong> 条 /
          共 <strong class="num">{{ totalCount }}</strong> 条发给
          学生 {{ identity.studentId }} 的站内消息。
        </p>
      </header>

      <!-- 01 · 端点的口径（⚠️ 这一段是**内容**：把「这一页读的是哪个端点、为什么」写在页面上） -->
      <section class="s-card lane-block" :style="{ '--lane-index': 0 }">
        <LaneDivider :index="1" label="ENDPOINT" />
        <div class="s-notice">
          <p class="s-notice__title">这一页读的是哪个端点</p>
          <p>
            <code>GET /api/students/{id}/notifications</code>，挂
            <strong><code>X-Student-Id</code></strong> + <code>require_scope</code>：
            服务端<strong>已经</strong>按收件人过滤好了（判据是
            <code>recipient_kind = 'student'</code> ∧ <code>recipient_id = 请求头里那个学号</code>），
            并且<strong>已经</strong>按 <code>created_at</code> 降序排好（同刻按 <code>id</code> 降序）。
            故本页既不做客户端过滤、也不再 <code>.sort()</code>。
          </p>
          <p>
            ⚠️ 越权是 <strong>403 <code>forbidden</code></strong>（学生 A 用
            <code>X-Student-Id: A</code> 去读 B 的那一条路径），而「学号不在册」
            <strong>也是</strong> 403 <code>forbidden</code> —— 两档刻意同形，
            因为区分它们等于把在册名单告诉调用方。
            ⚠️ 这与下面「标为已读」那一档的 <code>not_recipient</code> 是<strong>两个</strong>
            code：那一个按主键改行（它要让「id 不存在」与「不是你的」同形），
            本端点按收件人列行（它走的是 <code>require_scope</code>）。
          </p>
          <p>
            ⚠️ 这个端点是 <strong>Plan 04 Task 3 的后端小修波</strong>加的。此前本页只能
            「匿名 <code>GET /api/notifications</code> 翻页收集 + 客户端过滤」——
            页面是对的，但每打开一次都要把整张表拉下来。那个匿名 list
            <strong>今天仍然存在、仍然是匿名的</strong>（本仓的读侧口径是「读 ⇒ 一律匿名」，
            48 个匿名 GET 里已经包括给出 60 人出生日期的 <code>GET /api/students</code>），
            故补这个端点的理由是<strong>省掉客户端过滤的代价</strong>，不是堵洞。
          </p>
        </div>
        <p v-if="data?.truncated" class="s-block__note">
          ⚠️ 只显示前 {{ totalCount }} 条（超过客户端的安全上限
          <code>cap</code>；后端本端点不分页，故这一档在演示库上走不到）。
        </p>
      </section>

      <!-- 02 · 消息列表 -->
      <section class="s-card lane-block" :style="{ '--lane-index': 1 }">
        <LaneDivider :index="2" label="MESSAGES" />
        <div class="s-subhead">
          <span class="s-subhead__title">站内消息</span>
          <span class="s-subhead__aside">未读 {{ unreadCount }} / {{ totalCount }}</span>
        </div>

        <div v-if="items.length === 0" class="s-empty">
          <svg class="s-empty__mark" viewBox="0 0 88 20" aria-hidden="true">
            <path class="s-empty__mark-line" d="M2 6 H86" />
            <path class="s-empty__mark-hair" d="M2 14 H24" />
          </svg>
          <p class="s-empty__title zh-title">没有发给你的站内消息</p>
          <p class="s-empty__note">
            ⚠️ 这与「消息中心坏了」是两件事：演示库里一共有
            <strong>19</strong> 条通知，而它们是<strong>一人一条</strong>发给了
            19 个不同的学生（4、5、6、10、11、15、17、25、26、35、38、40、43、47、48、53、54、56、60）。
            换一个身份就能看到那一条。
            两种自动推送是：<code>GREEN_MASTERY</code> 的电子勋章（13 条）与
            <code>YELLOW_CHECKIN_GAP</code> 的补练提醒（6 条）；
            而两条 <code>RED_*</code> 规则<strong>刻意不自动推送</strong>
            （spec §8.2：教师在预警队列里点一次「减量」，学生才会收到那一条）。
          </p>
        </div>

        <ol v-else class="msgs">
          <li
            v-for="item in items"
            :key="item.id"
            class="msg"
            :class="[`msg--${kindOf(item)}`, item.is_read ? 'msg--read' : 'msg--unread']"
          >
            <div class="msg__head">
              <span class="msg__title zh-title">{{ item.title }}</span>
              <span v-if="!item.is_read" class="pill pill--red">未读</span>
              <span v-else class="pill msg__readpill">已读</span>
            </div>

            <p class="msg__body">{{ item.body }}</p>

            <dl class="msg__meta">
              <dt>id</dt>
              <dd class="data">{{ item.id }}</dd>
              <dt>收件人</dt>
              <dd class="data">{{ item.recipient_kind }} #{{ item.recipient_id }}</dd>
              <dt>渠道</dt>
              <dd>{{ channelZh(item.channel) }}</dd>
              <dt>推于</dt>
              <dd class="data">{{ stampOf(item.created_at) }}</dd>
              <dt>来源预警</dt>
              <dd class="data">
                <!-- ⚠️ 两格都可空 → 「—」，不是 0（约束第 10 条） -->
                <template v-if="item.alert_id === null"><span class="unknown">—</span></template>
                <template v-else>alert #{{ item.alert_id }}</template>
              </dd>
              <dt>关联处方</dt>
              <dd class="data">
                <template v-if="item.prescription_id === null"><span class="unknown">—</span></template>
                <template v-else>prescription #{{ item.prescription_id }}</template>
              </dd>
            </dl>

            <div class="s-actions">
              <button
                v-if="!item.is_read"
                class="btn btn--primary"
                type="button"
                :disabled="busy !== null"
                @click="markRead(item.id)"
              >
                {{ busy === item.id ? '正在标…' : '标为已读' }}
              </button>
              <span v-else class="msg__done caps">已读过</span>
            </div>

            <div v-if="readError && readError.id === item.id" class="s-notice s-notice--warn">
              <p class="s-notice__title">
                {{ readError.error.code }} · {{ readError.error.status }}
              </p>
              <p v-if="adviceFor(readError.error.code)">{{ adviceFor(readError.error.code) }}</p>
              <p><code>{{ readError.error.message }}</code></p>
            </div>
          </li>
        </ol>
      </section>

      <!-- 03 · 计数（对拍用） -->
      <section class="s-card lane-block" :style="{ '--lane-index': 2 }">
        <LaneDivider :index="3" label="CROSS CHECK" />
        <div class="s-subhead">
          <span class="s-subhead__title">与 <code>/home</code> 的未读数对拍</span>
          <span class="s-subhead__aside">两个来源</span>
        </div>
        <p class="s-block__note">
          本页的未读数是<strong>数列表里 <code>is_read</code> 为假的行</strong>数出来的
          （{{ unreadCount }} 条）；<code>GET /api/students/{id}/home</code> 的
          <code>unread_notifications</code> 是后端<strong>另一次 COUNT</strong>。
          两者应当相等 —— 它们现在共用<strong>同一个</strong>筛选条件
          （<code>dashboard.py</code> 的 <code>_student_notifications</code>，
          一个 <code>select(Notification).where(…)</code> 的两个消费者），
          故结构上不可能漂开；守卫是后端
          <code>test_the_notification_list_and_the_unread_badge_agree</code>
          （标已读前后两边同时增减）。
          去首页看那一格：<RouterLink to="/s/home">首页</RouterLink>。
        </p>
        <p class="s-block__note">
          消息总数 <strong class="num">{{ totalCount }}</strong> 条 ·
          最近一条推于
          <strong class="data">{{ items[0] ? stampOf(items[0].created_at) : UNKNOWN }}</strong> ·
          标题实测只有
          <strong>{{ [...new Set(items.map((i) => i.title))].join('、') || UNKNOWN }}</strong>
          这几种（⚠️ 前端<strong>不按标题分支</strong>：那是给人看的中文、会变；
          要按类型分支得读 <code>alert_id</code> 再去查那条预警的 <code>rule_id</code>）。
        </p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.msgs {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  list-style: none;
  padding: 0;
  margin: 0;
}

/* ⚠️ 已读 / 未读的视觉区分靠**三件一起变**（只变一件的话，
   在投影或色弱的情况下就读不出来）：左端色带、底色、标题字重。 */
.msg {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-3) var(--space-3) var(--space-4);
  border: var(--border-hairline);
  border-radius: var(--radius-sharp);
  border-inline-start: var(--lane-thick) solid var(--rule-hairline);
  background: var(--paper);
}

.msg--unread {
  border-inline-start-color: var(--track);
  background: var(--paper-raised);
  box-shadow: var(--shadow-paper);
}

.msg--read {
  border-inline-start-color: var(--moss-on-paper);
  background: var(--paper-sunken);
}

.msg--read .msg__title,
.msg--read .msg__body {
  color: var(--ink-faint);
  font-weight: var(--fw-body-400);
}

.msg__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
}

.msg__title {
  font-size: var(--fs-body);
  font-weight: var(--fw-zh-title-900);
}

.msg__readpill {
  background: transparent;
  border: 1px solid var(--rule-hairline);
  color: var(--ink-faint);
}

.msg__body {
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.msg__meta {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 2px var(--space-3);
  padding-block: var(--space-2);
  border-block: var(--border-hairline);
  font-size: var(--fs-micro);
}

.msg__meta dt {
  font-family: var(--font-display);
  font-weight: var(--fw-display-600);
  letter-spacing: var(--tracking-caps);
  text-transform: uppercase;
  color: var(--ink-faint);
  white-space: nowrap;
}

.msg__meta dd {
  margin: 0;
  color: var(--ink-soft);
  min-width: 0;
  overflow-wrap: anywhere;
}

.msg__done {
  color: var(--moss-on-paper);
}
</style>

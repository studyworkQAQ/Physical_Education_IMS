<script setup lang="ts">
/**
 * `views/student/Notifications.vue` —— 消息中心（`/s/notifications`）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 端点路径是**实测**出来的（计划 Task 2 那一格标了「实现者要实测确切路径」）
 * ---------------------------------------------------------------------------
 * 计划猜的是 `GET /api/students/{id}/notifications`。**它不存在。**
 * 实测 `/openapi.json` 里含 `notification` 的路径只有三条：
 *
 *     GET  /api/notifications                       security = null（匿名）
 *     GET  /api/notifications/{notification_id}     security = null（匿名）
 *     POST /api/notifications/{notification_id}/read security = [{"X-Student-Id": []}]
 *
 * 而泛型 list **没有筛选参数**（约束第 9 条：`?recipient_id=4` 会被 FastAPI
 * **静默忽略**、只返回全量）→ 故「发给我的消息」只能在**客户端**过滤：
 * `recipient_kind === 'student' && recipient_id === 我`。
 *
 * ⚠️ **这是顶回控制者的第 1 处**：客户端过滤让**页面**只显示我的（正确的 UI），
 * 但它**堵不住那个洞** —— 洞在 API 上：任何调用方匿名 GET 一次就能读到全部 19 条、
 * 包括发给别人的。而后端**已经会**按学生过滤：`GET /api/students/{id}/home` 的
 * `unread_notifications` 就是服务端按 `recipient_kind + recipient_id + is_read`
 * 数出来的（`dashboard.py:489-497`）。故补一个学生侧的 list 端点是**几行**的事。
 * 要不要开一个小修波，请控制者裁定；本页在那之前照客户端过滤渲染。
 *
 * ---------------------------------------------------------------------------
 * `POST /api/notifications/{id}/read` 的两档
 * ---------------------------------------------------------------------------
 *  - 200：只改 `is_read`、**不删行**（`notification` 是 `on_delete='forbid'`
 *    且刻意不带 `batch_id`，故「从任何入口都删不掉一行通知」是有意的）；
 *  - **403 `not_recipient`**：那条消息不是发给请求头里这个学生的
 *    —— **或它根本不存在**（两档刻意同形：`notification.id` 是连续代理键，
 *    区分两者等于让「扫一遍 id」成为一次有效探测）。本页给这一档一句人话。
 */
import { computed, ref } from 'vue'

import { ApiError } from '../../api/client'
import { listMyNotifications, markNotificationRead } from '../../api/endpoints'
import type { NotificationListItem } from '../../api/types'
import LaneDivider from '../../components/LaneDivider.vue'
import StudentNav from '../../components/StudentNav.vue'
import { useAsync } from '../../composables/useAsync'
import { useIdentityStore } from '../../stores/identity'
import { UNKNOWN, channelZh, stampOf } from './present'

const identity = useIdentityStore()

const { data, loading, settled, reload } = useAsync(async () => {
  const id = identity.studentId
  if (id === null) return null
  return listMyNotifications(id)
})

/** 后端给的序是 `id` 升序（实测 1,2,3,…），而消息中心要「新的在上面」。 */
const items = computed<NotificationListItem[]>(() =>
  [...(data.value?.items ?? [])].sort(
    (a, b) => b.created_at.localeCompare(a.created_at) || b.id - a.id,
  ),
)

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

      <!-- 01 · 端点的口径（⚠️ 这一段是**内容**：把顶回控制者的那一处如实写在页面上） -->
      <section class="s-card lane-block" :style="{ '--lane-index': 0 }">
        <LaneDivider :index="1" label="ENDPOINT" />
        <div class="s-notice">
          <p class="s-notice__title">这一页读的是哪个端点</p>
          <p>
            计划里猜的 <code>GET /api/students/{id}/notifications</code>
            <strong>不存在</strong>。实测含 <code>notification</code> 的路径只有三条：
            <code>GET /api/notifications</code>（匿名）、
            <code>GET /api/notifications/{id}</code>（匿名）、
            <code>POST /api/notifications/{id}/read</code>（学生头）。
          </p>
          <p>
            而泛型 list <strong>没有筛选参数</strong>（传了会被 FastAPI 静默忽略、只返回全量），
            故「发给我的」是在<strong>客户端</strong>过滤出来的：
            <code>recipient_kind === 'student' &amp;&amp; recipient_id === {{ identity.studentId }}</code>。
          </p>
          <p>
            ⚠️ 这挡住了「页面显示别人的消息」，但<strong>挡不住</strong>
            「任何调用方匿名 GET 一次就读到全部 19 条」—— 那一个洞在 API 上。
            后端已经会按学生过滤（<code>/home</code> 的 <code>unread_notifications</code>
            就是服务端数的），故这一处已顶回控制者，等裁定要不要补一个学生侧端点。
          </p>
        </div>
        <p v-if="data?.truncated" class="s-block__note">
          ⚠️ 只收到前 {{ totalCount }} 条（翻页收集撞到上限）。
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
          本页的未读数是<strong>客户端</strong>数出来的（{{ unreadCount }} 条）；
          <code>GET /api/students/{id}/home</code> 的 <code>unread_notifications</code>
          是<strong>服务端</strong>数出来的。两者应当相等 ——
          不等就说明客户端过滤的判据（<code>recipient_kind</code> /
          <code>recipient_id</code> / <code>is_read</code>）与后端不是同一套。
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

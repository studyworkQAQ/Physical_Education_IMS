<script setup lang="ts">
/**
 * `SuccessMark.vue` —— **一个对勾淡入**：打卡成功 / 快评交上去了的那一下。
 *
 * ⚠️⚠️ 它原名 `StampFeedback.vue`（**盖章**：印泥色扩散 + 轻微旋转 + 一层
 * `feTurbulence` 颗粒 + 双框章面），那是《田径场年鉴》味道最重的一处。
 * Plan 05B 计划 §3 的动效第 ② 条逐字要求换成「一个 200ms 的对勾淡入」，
 * 于是**连文件名一起换了**：一个叫「Stamp」却画对勾的组件会当场撒谎。
 * 只有 2 个调用点（`CheckIn.vue` / `RpeEntry.vue`），改动面实测极小。
 *
 * ⚠️ **它只用在「一次真的写进了库」的时刻**：`POST /api/training-logs` 201、
 * `POST /api/rpe-records` 201。不要拿它当 hover 反馈（计划 §2：不做无意义的动效）。
 *
 * ⚠️ 颜色**默认是绿**（`tone="moss"`）而不是主蓝：`--red` 在本系统里被
 * 「红色预警」占死了，一次成功的打卡出一个红勾会被读成一条事故。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ `done` 的时机：淡入 200ms 之后**再停 1600ms** 才发
 * ---------------------------------------------------------------------------
 * 两个调用点都写的是 `@done="stamp = false"`（`done` 是它们收起本组件的**唯一**
 * 机制）。旧版的 `done` 绑在 `animationend` 上，于是「可见时长 = 动画时长」
 * （460ms）。若照抄这一手，200ms 的对勾会在人能读出「已打卡 · 2025-10-12 第 6 周」
 * 之前就消失 —— 计划只钉了**淡入**的时长（200ms），没钉停留时长，故这里分开：
 * 淡入读 `--dur-check`（200ms），停留读 `--dur-check-hold`（1600ms），
 * 两个数都只有一个住址（`tokens.css`），本文件不写第二份字面量。
 * ⚠️ 用 `setTimeout` 而不是 `animationend`：`prefers-reduced-motion` 会把
 *    animation-duration 压到 0.01ms（`base.css` 的总开关），于是「停留」这件事
 *    不能挂在动画事件上，否则开了减动效的用户根本看不见这一格反馈。
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

interface Props {
  /** 显示不显示。⚠️ false→true 的**每一次**都会重放淡入（靠内部自增的 `key`）。 */
  visible: boolean
  /** 一行大字（两到四个字最好：「已打卡」「已提交」）。 */
  text: string
  /** 下面的一行小字（可选，例如「2025-10-12 · 第 6 周」）。 */
  caption?: string
  /** 对勾的颜色档。 */
  tone?: 'moss' | 'primary' | 'red' | 'amber'
}

const props = withDefaults(defineProps<Props>(), {
  caption: '',
  tone: 'moss',
})

const emit = defineEmits<{
  /** 该收起了。⚠️ 时长是**本组件**的知识（见文件头那段），调用方不必自己数。 */
  (e: 'done'): void
}>()

/** 每次 `visible` 翻到 true 就自增，作为 `:key` 强制重建元素、重放 CSS 淡入。 */
const markKey = ref(0)
let timer: ReturnType<typeof setTimeout> | null = null

/** 从 CSS 令牌读时长（`--dur-check-hold`），不在这里写第二份字面量。
 *  读不到（SSR、令牌被删）就退回 1600ms —— 那是 tokens.css 里今天的值。 */
function holdMs(): number {
  const fallback = 1600
  if (typeof window === 'undefined') return fallback
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue('--dur-check-hold')
    .trim()
  const n = Number.parseFloat(raw)
  if (!Number.isFinite(n) || n <= 0) return fallback
  return raw.endsWith('ms') ? n : n * 1000
}

function clear(): void {
  if (timer !== null) {
    clearTimeout(timer)
    timer = null
  }
}

watch(
  () => props.visible,
  (next) => {
    clear()
    if (!next) return
    markKey.value += 1
    timer = setTimeout(() => {
      timer = null
      emit('done')
    }, holdMs())
  },
  { immediate: true },
)

onBeforeUnmount(clear)

const rootClass = computed(() => ['mark', `mark--${props.tone}`])
</script>

<template>
  <div v-if="visible" :class="rootClass" role="status" aria-live="polite">
    <!-- ⚠️ 内联 SVG（计划纪律：图标用内联 SVG 或 Unicode 符号，不引图标库） -->
    <span :key="markKey" class="mark__figure" aria-hidden="true">
      <svg viewBox="0 0 48 48" class="mark__svg">
        <circle class="mark__ring" cx="24" cy="24" r="21" />
        <path class="mark__tick" d="M14.5 24.8 L21 31.3 L33.5 17.8" />
      </svg>
    </span>
    <p class="mark__text">{{ text }}</p>
    <p v-if="caption" class="mark__caption num">{{ caption }}</p>
  </div>
</template>

<style scoped>
.mark {
  /* 对勾颜色的唯一住址：四个 tone，值全部从 tokens.css 取 */
  --mark-ink: var(--green);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) 0;
}

.mark--primary {
  --mark-ink: var(--primary);
}
.mark--red {
  --mark-ink: var(--red);
}
.mark--amber {
  --mark-ink: var(--amber);
}
.mark--moss {
  --mark-ink: var(--green);
}

/* 200ms 淡入（计划 §3 逐字）。⚠️ 没有旋转、没有 scale、没有扩散环、没有颗粒：
   北欧标识的成功反馈就是「一个符号出现」。 */
.mark__figure {
  animation: mark-in var(--dur-check) var(--ease-out) both;
}

.mark__svg {
  inline-size: 56px;
  block-size: 56px;
}

.mark__ring {
  fill: none;
  stroke: var(--mark-ink);
  stroke-opacity: 0.28;
  stroke-width: 2;
}

.mark__tick {
  fill: none;
  stroke: var(--mark-ink);
  stroke-width: 4.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.mark__text {
  color: var(--mark-ink);
  font-family: var(--font-ui);
  font-size: var(--fs-subtitle);
  font-weight: var(--fw-700);
  line-height: var(--lh-heading);
  text-align: center;
}

.mark__caption {
  color: var(--ink-soft);
  font-size: var(--fs-small);
  text-align: center;
}

@keyframes mark-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
</style>

<script setup lang="ts">
/**
 * `StampFeedback.vue` —— **盖章**。打卡成功 / 快评交上去了的那一下。
 *
 * 计划第 2 节的动效第 ③ 条：「打卡/RPE 提交成功时一个『盖章』动效
 * （`scale(1.4→1)` + 一次轻微旋转 + 印泥色扩散）」。
 *
 * ⚠️ **它是三个动效里最贵的一个，故只用在「一次真的写进了库」的时刻**：
 * `POST /api/training-logs` 201、`POST /api/rpe-records` 201、
 * `POST /api/alerts/{id}/handle` 200。不要拿它当 hover 反馈
 * （计划第 2 节逐字：「不做无意义的 hover 浮动」）。
 *
 * ⚠️ 印泥色**默认是 `--moss`（绿）而不是红**：真印泥是朱红的，但本系统里
 * `--red` 已经被「红色预警」占死了 —— 一次成功的打卡盖出一个红章，
 * 在教师大屏上会被读成一条事故。故成功 = 绿，`tone` 可以覆盖。
 */
import { computed, ref, watch } from 'vue'

interface Props {
  /** 盖不盖。⚠️ false→true 的**每一次**都会重放动画（靠内部自增的 `key`）。 */
  visible: boolean
  /** 章面上的字（两到四个字最好：「已打卡」「已提交」「已处置」）。 */
  text: string
  /** 章下面的一行小字（可选，例如「2025-10-12 · 第 6 周」）。 */
  caption?: string
  /** 印泥色。 */
  tone?: 'moss' | 'track' | 'red' | 'amber'
  /** 底色（教师大屏是深底，印泥要换成 `*-on-ink` 那一档才够对比）。 */
  surface?: 'paper' | 'ink'
}

const props = withDefaults(defineProps<Props>(), {
  caption: '',
  tone: 'moss',
  surface: 'paper',
})

const emit = defineEmits<{
  /** 动画放完了。⚠️ 调用方用它来收起本组件 —— 时长是**本组件**的
   *  （`--dur-stamp`）知识，不该让调用方再抄一份字面量。 */
  (e: 'done'): void
}>()

/** 每次 `visible` 翻到 true 就自增，作为 `:key` 强制重建元素、重放 CSS 动画。 */
const stampKey = ref(0)

watch(
  () => props.visible,
  (next) => {
    if (next) stampKey.value += 1
  },
)

/**
 * `animationend` 是**冒泡**的，而章面上有两个动画（`.stamp` 的落下 + `.stamp__ring`
 * 的扩散），故直接绑会让 `done` 响两次。⚠️ 也不能比对 `event.animationName`：
 * `<style scoped>` 会给 `@keyframes` 的名字加上作用域后缀，那个字面量在这里对不上。
 * 判「是不是我自己这个元素上的动画」用的是 target === currentTarget。
 */
function onAnimationEnd(event: AnimationEvent): void {
  if (event.target === event.currentTarget) emit('done')
}

const rootClass = computed(() => [
  'stamp-root',
  `stamp-root--${props.tone}`,
  props.surface === 'ink' ? 'stamp-root--on-ink' : '',
])
</script>

<template>
  <div v-if="visible" :class="rootClass" role="status" aria-live="polite">
    <div :key="stampKey" class="stamp" @animationend="onAnimationEnd">
      <span class="stamp__ring" aria-hidden="true"></span>
      <span class="stamp__face">
        <span class="stamp__text zh-title">{{ text }}</span>
      </span>
      <span class="stamp__grain" aria-hidden="true"></span>
    </div>
    <p v-if="caption" class="stamp__caption num">{{ caption }}</p>
  </div>
</template>

<style scoped>
.stamp-root {
  /* 印泥色的唯一住址：四个 tone × 两种底色，值全部从 tokens.css 取 */
  --stamp-ink: var(--moss-on-paper);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) 0;
}

.stamp-root--track {
  --stamp-ink: var(--track-on-paper);
}
.stamp-root--red {
  --stamp-ink: var(--red-on-paper);
}
.stamp-root--amber {
  --stamp-ink: var(--amber-on-paper);
}
.stamp-root--moss {
  --stamp-ink: var(--moss-on-paper);
}

.stamp-root--on-ink.stamp-root--moss {
  --stamp-ink: var(--moss-on-ink);
}
.stamp-root--on-ink.stamp-root--track {
  --stamp-ink: var(--track-on-ink);
}
.stamp-root--on-ink.stamp-root--red {
  --stamp-ink: var(--red-on-ink);
}
.stamp-root--on-ink.stamp-root--amber {
  --stamp-ink: var(--amber-on-ink);
}

.stamp {
  position: relative;
  display: grid;
  place-items: center;
  inline-size: 132px;
  block-size: 132px;
  /* 落下：1.4 → 1，带一次轻微旋转。曲线用 --ease-stamp（有一点回弹） */
  animation: stamp-hit var(--dur-stamp) var(--ease-stamp) both;
}

.stamp__face {
  position: relative;
  z-index: 2;
  display: grid;
  place-items: center;
  inline-size: 108px;
  block-size: 108px;
  /* 双框：外 3px（= 分道线的粗线）+ 内 1px（= 那条细线），
     与母题同一套尺寸，故它看起来是「同一个系统里的东西」 */
  border: var(--lane-thick) solid var(--stamp-ink);
  border-radius: var(--radius-stamp);
  box-shadow: inset 0 0 0 var(--lane-thin) var(--paper), inset 0 0 0 4px var(--stamp-ink);
}

.stamp-root--on-ink .stamp__face {
  box-shadow: inset 0 0 0 var(--lane-thin) var(--ink), inset 0 0 0 4px var(--stamp-ink);
}

.stamp__text {
  padding: 0 var(--space-2);
  color: var(--stamp-ink);
  font-size: 30px;
  font-weight: var(--fw-zh-title-900);
  line-height: 1.05;
  letter-spacing: 0.06em;
  text-align: center;
  /* 印泥不是满的：稍微透一点，像盖在纸上 */
  opacity: 0.92;
}

/* 印泥色扩散：一圈从章面上漾出去的环 */
.stamp__ring {
  position: absolute;
  z-index: 1;
  inset: 0;
  border-radius: 50%;
  border: 2px solid var(--stamp-ink);
  animation: stamp-spread var(--dur-stamp) var(--ease-lane) both;
}

/* 纸上的一点颗粒，让章面不是矢量的干净 */
.stamp__grain {
  position: absolute;
  z-index: 3;
  inset: 12px;
  pointer-events: none;
  mix-blend-mode: multiply;
  opacity: 0.5;
  border-radius: var(--radius-stamp);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='pe-stamp'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='120' height='120' filter='url(%23pe-stamp)'/%3E%3C/svg%3E");
  background-size: 120px 120px;
}

.stamp-root--on-ink .stamp__grain {
  mix-blend-mode: screen;
  opacity: 0.22;
}

.stamp__caption {
  color: var(--ink-soft);
  font-size: var(--fs-small);
  letter-spacing: 0.04em;
}

.stamp-root--on-ink .stamp__caption {
  color: var(--paper-soft);
}

@keyframes stamp-hit {
  0% {
    transform: scale(1.4) rotate(-11deg);
    opacity: 0;
  }
  55% {
    opacity: 1;
  }
  100% {
    transform: scale(1) rotate(-6deg);
    opacity: 1;
  }
}

@keyframes stamp-spread {
  0% {
    transform: scale(0.62);
    opacity: 0.75;
  }
  100% {
    transform: scale(1.55);
    opacity: 0;
  }
}
</style>

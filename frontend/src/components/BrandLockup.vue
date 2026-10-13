<script setup lang="ts">
/**
 * `BrandLockup.vue` —— **厦门大学品牌锁排（lockup）的唯一住址**。
 *
 * ---------------------------------------------------------------------------
 * 三档，一档一个使用点（⚠️ 不是「三种皮肤」，是三个不同的排版任务）
 * ---------------------------------------------------------------------------
 *  · `lockup`   登录页：校徽 + 嘉庚体校名 + 系统名 + 拉丁副题 + 校训小字。
 *               ⚠️ 这是唯一把**两个**素材同时排出来的一档 —— 登录页是甲方
 *               看到的第一屏，品牌要在这里说全。
 *  · `masthead` 三端报头：校徽（小）+ 拉丁校名 + 系统名。
 *               ⚠️ 系统名在这一档是 `<h1>`：改前 `App.vue` 的报头里就有全站
 *               **唯一的**一个 `<h1>`（每条路由都是它，页面自己的标题是 `<h2>`），
 *               搬进本组件之后这个「一页一个 h1」的形状逐字不变。
 *  · `colophon` 页脚：嘉庚体校名 + 校训 + 版本行。
 *               ⚠️ 校训按控制者裁定只排**一行小字**（品牌元素，不做大标语）；
 *               版本号读 `brand.ts` 的 `VERSION`（编译期取自 `package.json`）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 素材一律 `<img src>`，**不内联 svg**
 * ---------------------------------------------------------------------------
 * 两个 svg 的 fill 逐字是 `#122e66`（厦大蓝，与 `tokens.css` 的 `--primary` 同值）。
 * 内联进 `.vue` 会让那 10 处色值字面量落进 `npm run check:tokens` 的扫描面
 * （`SCANNED_EXTENSIONS = {.css, .vue}`）→ 当场 10 处 offender，而正确的处置不是
 * 放宽守卫、也不是给素材开豁免，是**别把它搬进 .vue**。
 * ⚠️ 代价：`<img>` 里的 svg 颜色**不跟随** `--primary`。这里可以接受 —— 校徽的蓝
 * 是甲方的品牌色、不是本系统的设计令牌，它不该因为我们改皮肤而变。
 *
 * ⚠️ 两个 `width`/`height` 属性是**固有尺寸**（防 CLS：图片没到之前先占住位置），
 *    实际渲染尺寸由 CSS 的 `block-size` + `inline-size: auto` 决定，
 *    于是宽高比由 svg 自己的 `viewBox` 保证，不会被拉扁。
 *    嘉庚体校名的宽高比 3.662:1 由 `brand.ts` 的 `WORDMARK_RATIO` 给出。
 */
import {
  BRAND_EMBLEM,
  BRAND_WORDMARK,
  MOTTO,
  SYSTEM_NAME,
  SYSTEM_SUBTITLE,
  UNIVERSITY_NAME,
  UNIVERSITY_NAME_EN,
  VERSION,
  WORDMARK_RATIO,
} from '../brand'

interface Props {
  /** 见文件头那三档。 */
  variant?: 'lockup' | 'masthead' | 'colophon'
}

withDefaults(defineProps<Props>(), { variant: 'masthead' })

/** 嘉庚体校名的宽高比，四舍五入到 3 位（给 `aspect-ratio` 用，避免一长串小数）。 */
const RATIO = WORDMARK_RATIO.toFixed(3)
</script>

<template>
  <!-- ① 登录页：校徽 + 嘉庚体校名 + 系统名 + 拉丁副题 + 校训 -->
  <div v-if="variant === 'lockup'" class="brand brand--lockup">
    <img
      class="brand__emblem brand__emblem--lg"
      :src="BRAND_EMBLEM"
      :alt="`${UNIVERSITY_NAME}校徽`"
      width="1067"
      height="1067"
    />
    <img
      class="brand__wordmark brand__wordmark--lg"
      :src="BRAND_WORDMARK"
      :alt="UNIVERSITY_NAME"
      :style="{ 'aspect-ratio': RATIO }"
      width="533"
      height="146"
    />
    <p class="zh-title brand__name brand__name--lg">{{ SYSTEM_NAME }}</p>
    <p class="caps brand__subtitle">{{ SYSTEM_SUBTITLE }}</p>
    <p class="zh-title brand__motto">{{ MOTTO }}</p>
  </div>

  <!-- ② 三端报头：校徽（小）+ 拉丁校名 + 系统名（全站唯一的 h1） -->
  <div v-else-if="variant === 'masthead'" class="brand brand--masthead">
    <img
      class="brand__emblem"
      :src="BRAND_EMBLEM"
      :alt="`${UNIVERSITY_NAME}校徽`"
      width="1067"
      height="1067"
    />
    <div class="brand__masthead-text">
      <p class="caps brand__kicker">{{ UNIVERSITY_NAME_EN }}</p>
      <h1 class="zh-title brand__name">{{ SYSTEM_NAME }}</h1>
    </div>
  </div>

  <!-- ③ 页脚：嘉庚体校名 + 校训 + 版本行 -->
  <div v-else class="brand brand--colophon">
    <img
      class="brand__wordmark"
      :src="BRAND_WORDMARK"
      :alt="UNIVERSITY_NAME"
      :style="{ 'aspect-ratio': RATIO }"
      width="533"
      height="146"
    />
    <span class="zh-title brand__motto">{{ MOTTO }}</span>
    <span class="caps brand__version num">{{ SYSTEM_NAME }} · v{{ VERSION }}</span>
  </div>
</template>

<style scoped>
/* ⚠️ 一个色值都不写死（`npm run check:tokens` 扫本文件）；尺寸走 `tokens.css` 的
   间距/字号令牌，只有素材自己的几何（固有宽高比）走 `brand.ts`。
   ⚠️ **零投影、零渐变、零纹理**：北欧公共标识靠「填充差 + 一条细规则线」建立层次，
   品牌块也跟着这一条走（本波只换主色，不换设计语言）。 */
.brand {
  min-width: 0;
}

.brand__emblem {
  display: block;
  block-size: 36px;
  inline-size: auto;
  flex: 0 0 auto;
}

.brand__emblem--lg {
  block-size: 64px;
}

.brand__wordmark {
  display: block;
  block-size: auto;
  inline-size: 112px;
  flex: 0 0 auto;
}

.brand__wordmark--lg {
  inline-size: 184px;
}

/* ------------------------------------------------- ① 登录页那一档（居中一列）
   ⚠️ 登录页在 375px 的壳里（`.body` 的 `--w-student`），故这一列的宽度预算是
   343px：校名 184px、系统名 8 × 24px = 192px，都放得下、都不会折行。 */
.brand--lockup {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding-block: var(--space-3) var(--space-1);
  text-align: center;
}

.brand--lockup .brand__wordmark--lg {
  margin-block-start: var(--space-1);
}

.brand__name {
  font-size: var(--fs-title);
  line-height: var(--lh-heading);
  color: var(--ink);
  margin: 0;
}

.brand__name--lg {
  font-size: var(--fs-title);
  letter-spacing: var(--tracking-title);
  color: var(--primary);
  margin-block-start: var(--space-1);
}

.brand__subtitle {
  color: var(--ink-faint);
  margin: 0;
}

/* 校训：⚠️ 控制者裁定「tasteful，不要做成大标语」—— 故它是 12px 的一行小字，
   字距拉开一点（书法字排小字时靠字距找回呼吸），颜色用主蓝而不是纯墨，
   于是它读起来像**印章**而不像一句正文。 */
.brand__motto {
  font-size: var(--fs-micro);
  line-height: var(--lh-body);
  letter-spacing: 0.24em;
  color: var(--primary);
  margin: 0;
}

/* ------------------------------------------------- ② 报头那一档（横排） */
.brand--masthead {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.brand__masthead-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.brand__kicker {
  color: var(--ink-faint);
  margin: 0;
}

/* ------------------------------------------------- ③ 页脚那一档（横排，一行）
   ⚠️ 页脚在 375px 的壳里也要放得下：112px 校名 + 4 字校训 + 版本行，
   `flex-wrap` 让它在窄壳上折成两行而不是横向溢出（§4.1 的溢出守卫看着）。 */
.brand--colophon {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}

.brand__version {
  color: var(--ink-faint);
}
</style>

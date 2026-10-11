/**
 * `composables/useAsync.ts` —— **一次读取的四态**（未开始 / 加载中 / 成了 / 坏了）。
 *
 * ---------------------------------------------------------------------------
 * 为什么会有这个文件（Task 2 加的，计划的 File Structure 里没有它）
 * ---------------------------------------------------------------------------
 * 学生端 6 个页面每一个都要「挂载时读一到四个端点，然后按 loading / error / empty
 * 三档渲染」。把那 20 行抄 6 遍的失效形态不是「代码长」，而是**6 份会各自漂开**：
 * 有的忘了处理「响应回来时组件已经卸载」、有的忘了「身份换了要重读」、有的把
 * `ApiError` 送进横幅而有的吞掉 —— 于是同一个后端故障在 6 个页面上长 6 个样子。
 * 故这里只留**一份**，而每一页只写「读什么」与「怎么渲染」。
 *
 * ⚠️ 它**刻意不是**一个数据缓存层（计划第 3 节：Pinia 只存三样，第三样「服务端缓存」
 * 今天没有住址）。它没有 TTL、没有去重、没有跨页共享 —— 换页就重读。原型口径下
 * 「总是读最新的」比「省一次请求」重要：教师刚处置完一条预警，学生刷新就该看到
 * 减量后的训练单（计划约束第 13 条那一档）。
 */
import { ref, shallowRef, type Ref, type ShallowRef } from 'vue'

import { ApiError } from '../api/client'
import { useApiError } from '../components/ApiErrorBanner.vue'

export interface UseAsyncReturn<T> {
  /** 成功读到的东西。⚠️ `shallowRef`：响应体是后端给的**数据**，
   *  深度响应化它没有意义（页面只读不改），而 `weekly_sheet` 那种嵌套结构
   *  深代理一遍是纯浪费。 */
  data: ShallowRef<T | null>
  loading: Ref<boolean>
  /** 只可能是 `ApiError` 或渲染前的意外异常。⚠️ 页面按 `err instanceof ApiError`
   *  再取 `code` 分支（约束第 8 条：按 code，不按 message）。 */
  error: ShallowRef<unknown | null>
  /** 有没有跑过一次（无论成败）。⚠️ 与 `loading` 是两件事：
   *  「还没开始」与「开始了但失败」要渲染成两种样子。 */
  settled: Ref<boolean>
  /** 重读一次。⚠️ 提交成功之后调它，于是「盖章动效」与「列表里多了一行」是同一份数据。 */
  reload: () => Promise<void>
}

export interface UseAsyncOptions {
  /** 挂载时就跑（缺省 `true`）。 */
  immediate?: boolean
  /** ⚠️ `true` = **不**把 `ApiError` 送进 `ApiErrorBanner` 的常驻位。
   *  用在「这一档错误本身就是页面内容」的地方：例如小测页的 401
   *  （那个端点挂的是教师头）要在页面里画成一块有解释的区域，
   *  而不是一条红色横幅 —— 横幅会把「这是设计如此」讲成「出事了」。 */
  silent?: boolean
}

/**
 * @param load 「读什么」。**一次调用里把这一页要的端点全读完**（可以并发），
 *   返回一个组装好的对象 —— 于是页面模板里不再出现「A 读到了但 B 还没到」
 *   那个中间态（那正是「本周训练量显示成 0」这一类 bug 的住址）。
 */
export function useAsync<T>(
  load: () => Promise<T>,
  options: UseAsyncOptions = {},
): UseAsyncReturn<T> {
  const { immediate = true, silent = false } = options

  const data = shallowRef<T | null>(null)
  const loading = ref(false)
  const error = shallowRef<unknown | null>(null)
  const settled = ref(false)

  /** 竞态守卫：身份切换 / 连点「重试」时，**只有最后发起的那一次**能写状态。
   *  没有它的失效形态是「慢的那一次后到、把新的覆盖掉」，而它在演示时
   *  恰好最难复现（要网络抖一下）。 */
  let token = 0

  async function reload(): Promise<void> {
    const mine = ++token
    loading.value = true
    error.value = null
    try {
      const next = await load()
      if (mine !== token) return
      data.value = next
      settled.value = true
    } catch (err) {
      if (mine !== token) return
      error.value = err
      data.value = null
      settled.value = true
      if (!silent && err instanceof ApiError) {
        useApiError().raise(err)
      }
      // ⚠️ 不吞：非 ApiError 的那一档要能在 devtools 里看到堆栈。
      if (!(err instanceof ApiError)) console.error('[useAsync]', err)
    } finally {
      if (mine === token) loading.value = false
    }
  }

  if (immediate) {
    // ⚠️ 不在这里 `await`：`useAsync` 是在 `setup()` 里同步调用的，
    //    等它会让整个组件的创建变成异步（模板第一帧就渲染不出来，
    //    而无头浏览器的 `--dump-dom` 抓的正是那一帧）。
    void reload()
  }

  return { data, loading, error, settled, reload }
}

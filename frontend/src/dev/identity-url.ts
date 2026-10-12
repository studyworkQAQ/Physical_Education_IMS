/**
 * `dev/identity-url.ts` —— **深链接身份**（`?student=4` / `?teacher=T0001` /
 * `?as_of=2025-10-12`）。⚠️ **DEV-only 的开发工具**（Plan 05A Task 3 把它降级到本模块）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 为什么它从 `stores/identity.ts` 搬出来、住进 `src/dev/`
 * ---------------------------------------------------------------------------
 * Plan 04 那一版它叫 `identity.adoptFromUrl()`，是 store 的一个 action，
 * 理由是「本仓没有登录页，而一条 `http://…/s/check-in?student=4` 的链接落地时
 * 没有人去点那个身份切换器」。
 *
 * **Plan 05A 之后那个理由不成立了**：本仓**有**登录页，而真实的身份载体是
 * `pe_session` cookie（HttpOnly）。请求头那条通道只在后端
 * `PE_ALLOW_HEADER_IDENTITY=1` 时存在（生产缺省 `"0"` = 只认 cookie），
 * 故「URL 能认身份」从「没有登录页的必要补充」降级成了**开发工具**：
 * 它只在 `npm run dev`（DEV 构建）下有意义，而**生产构建里它必须不存在**。
 *
 * ⚠️ **搬进一个独立模块正是为了「不存在」这件事可以被机器验证**：
 * `main.ts` 里那一处调用被包在 `if (import.meta.env.DEV) { … }` 里，
 * 而 `import.meta.env.DEV` 是**编译期常量**（Vite 在生产构建里把它替换成 `false`），
 * 于是 Rollup 会 ① 删掉那个 `if` 块 ② 发现本模块的导出再没有使用者
 * ③ 把整个模块从产物里摇掉。
 * 若它仍然是 store 的一个 action，那三格都不成立 —— store 本体一定在产物里，
 * 于是那个 action 也一定在，「生产构建里它不存在」就无从谈起。
 *
 * ⚠️ **守卫**：`scripts/check-dist.mjs`（`npm run check:dist`）在 `npm run build`
 * 之后逐个读 `dist/` 里的产物，断言 `adoptFromUrl` 这个串出现 **0** 次；
 * 并**反向**断言它在 `src/dev/identity-url.ts` 与 `src/main.ts` 里**确实存在**
 * （少了这一拍，「谓词写坏了 / 路径指错了」会得到同样的 0，硬规矩 #50）。
 * `smoke.mjs` 的第 15 步也会 `spawn` 它一次。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 它**不**是一条后门（三条纪律逐字沿用 Plan 04 那一版）
 * ---------------------------------------------------------------------------
 *  1. **只在参数存在时才动状态**：没有 `?student=` 就一个字都不改，
 *     于是刷新页面不会把用户已选的身份冲掉；
 *  2. **不合格的值一律忽略**（`?student=abc` / `?student=-3` / `?as_of=今天`），
 *     不抛错、不写进 `localStorage` —— 一个垃圾值被存下来的失效形态是
 *     「之后每一次刷新都 422」，而真因藏在一个用户看不见的 URL 里；
 *  3. **一次只认一种身份**（与 `client.ts` 的「一次只注入一个头」同一条口径）：
 *     两个参数都给了就以 `student` 为准，因为 `/s/*` 是本仓的缺省树。
 *
 * ⚠️ 而在 Plan 05A 之后它**连「后门」都算不上**：它改的是 `stores/identity.ts`
 * 里那两个**只被 `client.ts` 的 DEV 分支读**的字段，而生产构建里那个分支不存在、
 * 后端生产档也忽略那两个头。故它的效力上界是「一个开着
 * `PE_ALLOW_HEADER_IDENTITY=1` 的开发后端」。
 */
import type { useIdentityStore } from '../stores/identity'

/** store 的类型（⚠️ `import type`：它会被完全擦掉，故本模块对 store 没有运行时依赖，
 *  Rollup 因此可以放心地把它整个摇掉）。 */
type IdentityStore = ReturnType<typeof useIdentityStore>

/**
 * 从一段查询串里认一个开发期身份。`main.ts` 在挂载**之前**调它一次。
 *
 * ⚠️ 挂载之前是承重的：页面组件的 `onMounted` 里就要发请求，而 DEV 的身份头由
 * `client.ts` 从 store 读 —— 晚一步认，第一屏就是 401（而那一屏的横幅会把人
 * 支去查后端）。⚠️ 它不删查询串：`?as_of=` 一类参数还要被页面自己读。
 *
 * @returns 有没有认出一个身份（`main.ts` 只把它写进日志，不据此分支）。
 */
export function adoptFromUrl(identity: IdentityStore, search: string): boolean {
  const params = new URLSearchParams(search)
  let adopted = false

  const rawStudent = params.get('student')
  const rawTeacher = params.get('teacher')
  if (rawStudent !== null) {
    const id = Number(rawStudent)
    if (Number.isInteger(id) && id > 0) {
      identity.becomeStudent(id, params.get('label'))
      adopted = true
    }
  } else if (rawTeacher !== null && rawTeacher.trim() !== '') {
    identity.becomeTeacher(rawTeacher.trim(), params.get('label'))
    adopted = true
  }

  const rawAsOf = params.get('as_of')
  if (rawAsOf !== null && /^\d{4}-\d{2}-\d{2}$/.test(rawAsOf)) {
    identity.setAsOf(rawAsOf)
    adopted = true
  }
  return adopted
}

<script setup lang="ts">
/**
 * `views/admin/AuditLogList.vue` —— **审计留痕（只读）**（`/admin/audit-logs`）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ Plan 08 Task 1：本页今天是**两张表 / 两个端点 / 一个页面**
 * ---------------------------------------------------------------------------
 * 页首有一个「**写 / 读**」的切换：
 *
 * ======  ==================================  ==================================
 * 档位    端点                                  它答的那一句
 * ======  ==================================  ==================================
 * **写**  `GET /api/audit-logs`               「谁在什么时候**对什么做了什么**」
 *        （`audit_log`，Plan 06 Task 5/9）     （三个写方法 + 登录/绑定）
 * **读**  `GET /api/read-audit-logs`          「谁在什么时候**翻过哪个学生的档案**」
 *        （`read_audit_log`，Plan 08 Task 1）  （64 个 GET 里被归为敏感的 **46** 个）
 * ======  ==================================  ==================================
 *
 * ⚠️⚠️ **刻意不新开一个页面**（派单 §2 第 7 条的裁定）。理由逐字是派单给的：
 * 新开页面会让路由数 **16 → 17**，而 `smoke.mjs` 第 14 步（`eq('路由条数 = 16…')`）、
 * 甲方试用说明书 §5、README **三处**都钉着 16 ⇒ 一次改动要同步四处（含路由表自己），
 * 而换来的只是「审计这件事在本仓有两个页面住址」。⚠️ 于是本页的**路由一条都没动**
 * （`router/index.ts` 上仍然只有 `admin-audit-logs` 这一条），
 * 而「写 / 读」是**页面内的一个状态**（`tab`，缺省 `'write'`）。
 *
 * ⚠️⚠️ **缺省档是「写」，而那一格是承重的**：`smoke.mjs` 第 14 步的
 * `admin-audit-logs` 那一条 route 钉了六条 needle（`审计留痕` / `/api/audit-logs` /
 * `仅 role=admin 可读` / `身份类型 subject_kind` / `subject_kind` / `/api/auth/login`）
 * 与「`.a-table thead th` **恰好 9 个**」+「九列的文案与 slug 逐字相同、且顺序相同」
 * +「与后端 `GET /api/audit-logs` 真回的那一行的键顺序逐字相同」。
 * ⚠️ 于是两张表**一律 `v-if` 互斥**（同一时刻 DOM 里只有一张 `<table>`）：
 * 若两张都渲染，`querySelectorAll('.a-table thead th')` 会数到 **18** 个，
 * 那三拍当场红。⚠️ 「读」那一档另有一组对拍（同一条 smoke step 里新加的三拍）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 九列，一列不多（隐私那一格的验收面 —— **两档各九列**）
 * ---------------------------------------------------------------------------
 * 两个读模型的九格里**七格同名**（`id` / `at` / `subject_kind` / `subject_id` /
 * `staff_no` / `status` / `target`），而**各另有两格不同**：
 *
 * * **写**：`method`（`POST`/`PATCH`/`DELETE`）+ `path`（请求路径**原文**）；
 * * **读**：`route`（路由**模板**，`/api/students/{student_id}`）
 *   + `student_id`（「**哪个学生的**档案」——⚠️ 那一格正是这张表存在的理由）。
 *
 * ⚠️ 于是「九列」这个数在两档上相同而**内容不同**，本页因此有**两份**字面清单
 * （`WRITE_COLUMNS` / `READ_COLUMNS`）与**两个** `cellOf`。⚠️ 而两份都受
 * **编译期**的穷尽性检查（`satisfies` + 不写 `default` 的 `switch` + 那个
 * `_NineColumns` 类型断言）：少写一个 `case` 会让 `vue-tsc -b` 当场红，
 * 多写一个不存在的键则过不了 `key: keyof …Item`。
 *
 * ⚠️⚠️ **一个请求体都不落、一个查询串都不落**（两档同一条）：那两张表的 9 列里
 * **根本没有**能装它们的位置，故「不记请求体」是一条**结构性质**、不是「克制住不写」
 * （后端 `app/db/models/audit.py` 的模块 docstring 第三节）。守卫是
 * `tests/api/test_audit_api.py` 的
 * `test_a_login_with_a_password_leaves_no_trace_of_that_password_in_the_audit_row`
 * 与 `tests/api/test_read_audit_api.py` 的
 * `test_a_sensitive_read_with_a_body_and_a_query_string_leaves_no_trace_of_either`
 * （后者**真发**一次带请求体 + 带探针查询串的敏感读，然后扫落库那一行的全部 9 列）。
 *
 * ⚠️⚠️ **本页不得成为绕过那两条守卫的路**（派单 §2 第 5 条同一条口径）：
 * 页面上只画端点已经给的那 9 格，**不**去别处补任何一格。于是「审计页上看不到口令」
 * 与「审计行里没有口令」是同一件事的两个说法，而前者由 `smoke.mjs` 第 14 步的
 * DOM 取证钉（needle 命中 + 无重叠 + 无溢出），后者由上面那两条后端守卫钉。
 *
 * ⚠️⚠️ 三处**刻意不做**（都是「凭空加一列就是凭空撒一句关于这张表的谎」）：
 *  1. **没有「请求体」列**，也没有耗时 / ip / user-agent —— 它们**不在这两个契约里**；
 *  2. **不把 `subject_id` / `student_id` 回查名册补成人名 / 学号**。⚠️ 两格都是
 *     **代理键**（`student.id` / `teacher.id`，1–60 的小整数），不是学号；
 *     `staff_no` 才是工号（且**只对教职有值**）。
 *     ⚠️ 不回查是后端两个 `…Read` 模型的既有裁定，理由逐字住在它们的 docstring 里：
 *     写审计那一档鉴权失败时**根本不知道**是谁（`subject_kind='anonymous'`、两格皆 `null`），
 *     而一个事后补出来的 id 会把「撞门的人」伪装成「在册的人」。
 *     ⚠️ 而**读审计那一档另有**一格如实记：`subject_id` 在**教职走请求头通道**时是 `null`
 *     （后端 `current_teacher` 的那一支刻意不查 `teacher.id`），故「教职」那一档
 *     要认人就认 `staff_no`。本页因此把两格都**原样**画成代理键，并在第 02 块写明；
 *  3. **不给「读」那一档加一个 `route` 过滤下拉**。⚠️ 后端**刻意没有**那个参数
 *     （逐字理由见 `ReadAuditLogFilter` 的 docstring：46 个模板串塞进一个下拉
 *     比不给这个过滤更难用；要加的话正确的形状是按后端那 **10 个归类**过滤，
 *     而那需要把「类」也落进行里）。故本页只有后端真给的那两个参数。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 权限：只有 admin 能进（**复用既有那一套路由守卫，不写第二套**）
 * ---------------------------------------------------------------------------
 * `router/index.ts` 上这一条路由的 `meta.requires` 是字面的 `'admin'`，
 * 与另外三条 `/admin/*` **逐字同形**；判据是 `stores/session.ts` 的 `satisfies`
 * （`kind === 'teacher' && role === 'admin'`），落空时守卫把用户送到**他自己的**首页
 * 并写一句 `session.notice`。
 * ⚠️ 于是本页**不写任何角色判断**：一个普通教师点进来会被弹回 `/t/dashboard`，
 * 根本到不了这里的 `setup()`。⚠️ 而**后端那两道闸门照旧在**（两个端点各一个
 * `require_admin`，且它们的矩阵**逐字相同**：管理员 200 / 普通教师 403 /
 * 学生 403 / 匿名 401 —— 由 `test_the_read_audit_endpoint_admits_only_an_admin`
 * **同时打两个端点**钉住，故「读审计的权限面比写审计宽」当场红）。
 * ⚠️ 守卫是 `smoke.mjs` 第 14 步的两拍（admin 档渲染出九列 / 非 admin 档被弹走）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 排序与信封：两档**同形而同序**
 * ---------------------------------------------------------------------------
 * 四个信封键逐字同形（`items` / `total` / `limit` / `offset`），`total` 是**过滤后**的
 * 计数（与 `items` 走同一个 `WHERE`），故下面那个分页器不会给出一个翻不到的页数。
 * ⚠️ 两档的 `items` 都按 **`id DESC`**（最新在前），与泛型 list 的 `ORDER BY id`
 * 升序**相反** —— 审计要的是「最近谁动了什么 / 谁翻了什么」。
 * ⚠️ 本页因此**不再排一次序**：顺序是后端给的，前端重排就是第二个所有者。
 *
 * ⚠️⚠️ **「翻这一页会不会留下行」在两档上答案相反**（如实画在第 02 块里）：
 *  * **写**档：`GET /api/audit-logs` **不产生**任何审计行（`should_record` 只认三个
 *    写方法），否则审计页会自己喂自己；
 *  * **读**档：`GET /api/read-audit-logs` **会产生一行**读审计（它被后端归在
 *    `AUDIT_TRAIL` 那一类）。⚠️ 那一格是**要的**：「谁看过审计」正是它存在的理由
 *    （它兑现了后端两处**如实记下**的代价），而它有界（一次翻页一行、
 *    只有 `role='admin'` 打得到），处置是 Plan 08 Task 2 的 90 天留存窗口。
 *    守卫是 `test_reading_the_read_audit_page_adds_exactly_one_row_about_itself`。
 *
 * ⚠️ **本页没有任何写操作**（不可改写是审计的第一条性质）：没有「新建」、
 * 没有「编辑」、没有「删除」，故 `AuditLog` 与 `ReadAuditLog` 也都**不在**
 * `catalog/resources.ts` 那 23 行里（它们是特例端点，同 `/api/health` 那一族）。
 */
import { computed, ref, watch } from 'vue'

import { listAuditLogs, listReadAuditLogs } from '../../api/endpoints'
import type {
  AuditLogItem,
  AuditMethod,
  AuditSubjectKind,
  ReadAuditLogItem,
  ReadAuditSubjectKind,
} from '../../api/types'
import {
  AUDITED_METHODS,
  AUDIT_SUBJECT_KINDS,
  READ_AUDIT_SUBJECT_KINDS,
} from '../../api/types'
import SectionHead from '../../components/SectionHead.vue'
import { useAsync } from '../../composables/useAsync'
import { UNKNOWN, stampSecondsOf, text } from '../../present'

/* ------------------------------------------------------------------ 写/读 切换
   ⚠️ **两档、缺省 `'write'`**（缺省档承重：`smoke.mjs` 第 14 步那六条 needle 与
   「列头恰好 9 个」那一拍打的就是缺省档，逐字理由见文件头第 2 节）。
   ⚠️ `label` 是**给人看的**一个字，`endpoint` 是**给页首那行路径看的**：
   两者都写死在这里，于是「这一档打的是哪个端点」在本页只有一处住址。 */
const AUDIT_TABS = [
  { key: 'write', label: '写', endpoint: '/api/audit-logs', table: 'audit_log' },
  { key: 'read', label: '读', endpoint: '/api/read-audit-logs', table: 'read_audit_log' },
] as const

type AuditTab = (typeof AUDIT_TABS)[number]['key']

const tab = ref<AuditTab>('write')

const activeTab = computed(() => AUDIT_TABS.find((t) => t.key === tab.value) ?? AUDIT_TABS[0])

/* ------------------------------------------------------------------ 写档九列
   ⚠️ **字面清单**（硬规矩 #35）：不从响应体反推。两侧同源的话，「后端给那张表加了
   一列 `body`」会让本清单自动多一列、于是隐私守卫**仍然绿** —— 而那正是它要抓的失效。
   ⚠️ 而「一格不多、一格不少」由下面 `writeCellOf` 的那个 `switch` 在**编译期**钉住：
   它的形参是 `WriteColumnKey`（= 这九个键的并集）而返回类型是 `string`，
   故少写一个 `case` 会让 `vue-tsc -b` 当场红（TS 的穷尽性检查），
   多写一个不存在的键则过不了 `key: keyof AuditLogItem`。 */
/* ⚠️⚠️ `wrap: true` 那三列是 **Plan 06 Task 12（C1）** 加的，而它是**承重**的：
   那三列装的正是**客户端可控**的原文（`path` = 请求路径、`target` = 路径段原文、
   `staff_no` = 开发档那个请求头），后端 `app/db/width.py` 把它们按声明宽度截到
   **256 / 64 / 32** 个字符（并留下 `…[cut]` 或 `<over:N>` 的标记）。
   ⚠️ 而 256 个字符里**没有一个空格**（一条 `/aaa…` 的探测路径），
   `.a-table td` 那句 `white-space: nowrap` + `max-width: 340px` 在**自动表格布局**下
   夹不住它 —— 实测（`smoke.mjs` 第 14 步的布局守卫，真扣一条 400 字符的路径进库）：
   那一格 `scrollWidth 1927 / clientWidth 413`，而且它的矩形**压到了**同一行的
   「状态码」与「对象」两格上（`ratio 1` = 完全覆盖）。
   ⚠️ 修法不是新写一条 CSS，而是复用既有的 `.a-cell--wrap`
   （`styles/admin.css`：`white-space: normal; word-break: break-word`）
   ⇒ **一条新 CSS 都没加、一个色值裸值都没引**（`npm run check:tokens` 一格未退）。 */
const WRITE_COLUMNS = [
  { key: 'id', label: '行 id', wrap: false },
  { key: 'at', label: '时刻', wrap: false },
  { key: 'subject_kind', label: '身份类型', wrap: false },
  { key: 'subject_id', label: '身份 id', wrap: false },
  { key: 'staff_no', label: '工号', wrap: true },
  { key: 'method', label: '方法', wrap: false },
  { key: 'path', label: '路径', wrap: true },
  { key: 'status', label: '状态码', wrap: false },
  { key: 'target', label: '对象', wrap: true },
  /* ⚠️ `wrap` 逐格**显式写出**（`false` 也写）：`as const` 之下少写一格的失效是
     **编译期**的（`vue-tsc` 报 `Property 'wrap' does not exist`，本机实测踩过），
     而写全之后「哪三列会折行」是一件一眼看完的事。 */
] as const satisfies readonly { key: keyof AuditLogItem; label: string; wrap: boolean }[]

type WriteColumnKey = (typeof WRITE_COLUMNS)[number]['key']

/** ⚠️⚠️ **编译期的「九列恰好是 `AuditLogRead` 的九格」**（两个方向都查）：
 *  少一列 → 下面 `writeCellOf` 的 `switch` 返回类型带上 `undefined`、与声明的 `string`
 *  冲突；多一列 / 写错一个键 → 过不了 `satisfies` 里的 `key: keyof AuditLogItem`。
 *  ⚠️ 本行是第三道（也是唯一一道**点名**这件事的）：`_NineWriteColumns` 若不是 `true`
 *  就无从赋值，`vue-tsc -b` 当场红。 */
type _NineWriteColumns = WriteColumnKey extends keyof AuditLogItem
  ? keyof AuditLogItem extends WriteColumnKey
    ? true
    : never
  : never
const _writeColumnsAreExactlyTheNineFields: _NineWriteColumns = true
void _writeColumnsAreExactlyTheNineFields

/* ------------------------------------------------------------------ 读档九列
   ⚠️ 与写档**七格同名、各另有两格不同**（写档 `method` + `path`；
   读档 `route` + `student_id`）。⚠️ **顺序必须与后端 `ReadAuditLogRead` 的
   字段声明序逐字相同**：`smoke.mjs` 第 14 步新加的那一拍把「DOM 上九个 slug 的顺序」
   与「`GET /api/read-audit-logs` 真回的那一行的键顺序」逐字对拍（两侧不同源）。 */
const READ_COLUMNS = [
  { key: 'id', label: '行 id', wrap: false },
  { key: 'at', label: '时刻', wrap: false },
  { key: 'subject_kind', label: '身份类型', wrap: false },
  { key: 'subject_id', label: '身份 id', wrap: false },
  { key: 'staff_no', label: '工号', wrap: true },
  /* ⚠️ `route` 存的是**路由模板**（`/api/students/{student_id}`）而不是请求路径原文，
     故它**不可能**含一条客户端可控的 URL、也**不可能**含查询串
     （后端 `app/api/read_audit.py` 的模块 docstring 第 6 节）。
     ⚠️ 而它仍然是本页最长的串之一（今天最长 57 个字符：
     `/api/students/{student_id}/training-logs/completion-rate`），故 `wrap: true`。 */
  { key: 'route', label: '路由模板', wrap: true },
  /* ⚠️ **这一格是这张表存在的理由**：「谁翻过**谁的**档案」里的那个「谁」。
     ⚠️ 它是**代理键**（`student.id`），⚠️ 而它有两档合法的 `null`：
     ① 读的是名册/班级聚合（一次请求里没有「某一个学生」）；
     ② 读的是自己（`/api/mini-tests/normalized/me`，那一格由「身份 id」回答）。
     两档都画成 `—`（`UNKNOWN`），**不画成 0**（0 会被读成「学生 0」，而 id 恒 ≥ 1）。 */
  { key: 'student_id', label: '学生 id', wrap: false },
  { key: 'status', label: '状态码', wrap: false },
  { key: 'target', label: '对象', wrap: true },
] as const satisfies readonly { key: keyof ReadAuditLogItem; label: string; wrap: boolean }[]

type ReadColumnKey = (typeof READ_COLUMNS)[number]['key']

/** ⚠️⚠️ 与上面 `_NineWriteColumns` **同形的第三道闸**（读档那一份）。 */
type _NineReadColumns = ReadColumnKey extends keyof ReadAuditLogItem
  ? keyof ReadAuditLogItem extends ReadColumnKey
    ? true
    : never
  : never
const _readColumnsAreExactlyTheNineFields: _NineReadColumns = true
void _readColumnsAreExactlyTheNineFields

/** `subject_kind` 的中文。⚠️ **三档**（含 `anonymous`）：写审计有匿名那一档
 *  （「谁在撞门」），读审计**没有**（`READ_AUDIT_SUBJECT_KINDS` 只有两档）。
 *  ⚠️ 于是这一份翻译表**两档共用**、而**取值域各自的所有者是后端**
 *  （`types.ts` 的 `AUDIT_SUBJECT_KINDS` / `READ_AUDIT_SUBJECT_KINDS` 各指向一个
 *  模型类常量），故本表**只负责翻译**、不负责定义；⚠️ 不认识的值原样显示
 *  （把一个新出现的身份类型画成「匿名」等于把「我不知道」讲成「没人」）。 */
const SUBJECT_KIND_ZH: Record<string, string> = {
  anonymous: '匿名',
  student: '学生',
  teacher: '教职',
}

function subjectKindZh(value: string): string {
  return SUBJECT_KIND_ZH[value] ?? value
}

/** 状态码那一格的语义色。⚠️ **不写色值**：折成 `base.css` 既有的三个 `.pill--*`
 *  类名（色值的唯一住址是 `styles/tokens.css`，守卫是 `npm run check:tokens`）。
 *  ⚠️ 4xx 一律 `amber` 而不是 `red`：审计里 4xx 是**常态**（一次口令敲错就是一条 401），
 *  把它画成红的会让整页看起来像出了事；⚠️ 5xx 才是 `red`。
 *  ⚠️ **读档也用它**，而读档的 4xx **另有**一层含义：一条 `403` 是
 *  「一个**已登录**的人试了一次他范围外的读」——⚠️ 那一格**要记**
 *  （它是「有人在探边界」的唯一可见性，后端那些闸门故意不回显「你差在哪」），
 *  故读档里看到 403 **不是**故障，是一格事实。第 02 块把这句话写给了运维。 */
function statusPillOf(status: number): string {
  if (status >= 500) return 'pill pill--red num'
  if (status >= 400) return 'pill pill--amber num'
  return 'pill pill--green num'
}

/** 写档九列各自的取值口径。⚠️ `switch` **不写 `default`**：那是刻意的，
 *  少一个 `case` 会让返回类型带上 `undefined`、与声明的 `string` 冲突 → 编译期红。 */
function writeCellOf(row: AuditLogItem, key: WriteColumnKey): string {
  switch (key) {
    case 'id':
      return String(row.id)
    case 'at':
      // ⚠️ **秒级**、且**不做任何时区换算**（`at` 是 naive 本地时刻，逐字理由见
      //    `present.ts` 的 `stampSecondsOf`）。
      return stampSecondsOf(row.at)
    case 'subject_kind':
      return subjectKindZh(row.subject_kind)
    case 'subject_id':
      // ⚠️ **代理键**，不是学号（`anonymous` 那一档是 `null` → 「—」，不是 0）
      return row.subject_id === null ? UNKNOWN : String(row.subject_id)
    case 'staff_no':
      return text(row.staff_no)
    case 'method':
      return row.method
    case 'path':
      return row.path
    case 'status':
      return String(row.status)
    case 'target':
      return text(row.target)
  }
}

/** 读档九列各自的取值口径。⚠️ 与上面那个 `switch` **同形而不合并**：
 *  合并成一个「按 key 查一个字典」的函数会**丢掉编译期的穷尽性检查**
 *  （字典少一个键在 TS 上只是少一个属性，不是类型错误），
 *  而那一格正是「九列一个都不多、一个都不少」这件事在本页的唯一自动闸门。 */
function readCellOf(row: ReadAuditLogItem, key: ReadColumnKey): string {
  switch (key) {
    case 'id':
      return String(row.id)
    case 'at':
      return stampSecondsOf(row.at)
    case 'subject_kind':
      return subjectKindZh(row.subject_kind)
    case 'subject_id':
      // ⚠️ **教职走请求头那一档是 `null`**（后端 `current_teacher` 刻意不查
      //    `teacher.id`），故教职要认人请认「工号」那一列。→ 「—」，不是 0。
      return row.subject_id === null ? UNKNOWN : String(row.subject_id)
    case 'staff_no':
      return text(row.staff_no)
    case 'route':
      return row.route
    case 'student_id':
      return row.student_id === null ? UNKNOWN : String(row.student_id)
    case 'status':
      return String(row.status)
    case 'target':
      return text(row.target)
  }
}

/* ------------------------------------------------------------------ 分页 + 过滤 */

/** 一页几行。⚠️ 上界 200 是后端 `deps.Page` 的（`1 <= limit <= 200`），
 *  故这三档是**后端认得的**值，不是随便挑的（与 `ResourceList.vue` 逐字同一组）。 */
const LIMITS = [20, 50, 200] as const
const limit = ref<number>(LIMITS[1])
const offset = ref(0)

/* ⚠️ **两档各有一组过滤 ref**（刻意不共用）：两个端点的过滤参数**各有一个不同**
   （写档 `method`、读档 `student_id`），而共用一个 ref 会让「切档时把上一档的过滤
   带过去」成为一件在类型上可能的事 —— 那一格的失效形态是**静默的**：
   `?method=DELETE` 打在读端点上是 **422**（它没有那个参数……⚠️ 实测其实是
   「未声明的查询参数被忽略」，于是更坏：它**不响**、只是过滤没生效，
   而运维会以为「今天没有删除操作」）。 */
const writeSubjectKind = ref<AuditSubjectKind | null>(null)
const writeMethod = ref<AuditMethod | null>(null)
const readSubjectKind = ref<ReadAuditSubjectKind | null>(null)
/** ⚠️ 空串 = 「不过滤」。⚠️ 刻意不用 `ref<number | null>` + `<input type="number">`：
 *  那一档在清空时会给出 `null` 与 `NaN` 两种值（浏览器行为），而 `NaN` 会被
 *  `apiRequest` 序列化成 `student_id=NaN` → 后端 **422**。用一个字符串 ref
 *  + 一次显式的「空串就传 `null`」是把那一格收在本页里、而不是留给后端去猜。 */
const readStudentId = ref<string>('')

function readStudentIdParam(): number | null {
  const trimmed = readStudentId.value.trim()
  if (trimmed === '') return null
  const parsed = Number(trimmed)
  return Number.isInteger(parsed) ? parsed : null
}

const writeView = useAsync(() =>
  listAuditLogs({
    limit: limit.value,
    offset: offset.value,
    subjectKind: writeSubjectKind.value,
    method: writeMethod.value,
  }),
)

/* ⚠️ **`immediate: false`**：页面打开时只读缺省那一档（写）。⚠️ 那一格不只是省一次
   请求 —— 读档那一次请求**会在 `read_audit_log` 里留一行**（本端点自己被归在
   `AUDIT_TRAIL` 那一类），故「打开审计页就顺手翻一次读审计」会让运维看到一行
   他没做过的读。切到「读」那一档时才第一次读它。 */
const readView = useAsync(
  () =>
    listReadAuditLogs({
      limit: limit.value,
      offset: offset.value,
      subjectKind: readSubjectKind.value,
      studentId: readStudentIdParam(),
    }),
  { immediate: false },
)

/** 当前档的那一份状态。⚠️ 五个 computed 各读**一个**视图，于是模板里不再出现
 *  `tab === 'write' ? … : …` 这类三元（那会让「哪一档驱动哪一格」散在十几处）。 */
const loading = computed(() =>
  tab.value === 'write' ? writeView.loading.value : readView.loading.value,
)
const error = computed(() => (tab.value === 'write' ? writeView.error.value : readView.error.value))
const settled = computed(() =>
  tab.value === 'write' ? writeView.settled.value : readView.settled.value,
)
const total = computed(() =>
  tab.value === 'write'
    ? writeView.data.value?.total ?? 0
    : readView.data.value?.total ?? 0,
)
/* ⚠️ 一律读**响应体里**的 `offset`（后端实际用的那一个），不读自己发出去的 ref。 */
const shownFrom = computed(() => {
  if (total.value === 0) return 0
  const base = tab.value === 'write'
    ? writeView.data.value?.offset ?? 0
    : readView.data.value?.offset ?? 0
  return base + 1
})
const shownTo = computed(() => {
  const base = tab.value === 'write'
    ? writeView.data.value?.offset ?? 0
    : readView.data.value?.offset ?? 0
  const count = tab.value === 'write'
    ? writeView.data.value?.items.length ?? 0
    : readView.data.value?.items.length ?? 0
  return base + count
})
const canPrev = computed(() => offset.value > 0)
const canNext = computed(() => offset.value + limit.value < total.value)
const isEmpty = computed(() => settled.value && !loading.value && total.value === 0)

async function reloadActive(): Promise<void> {
  if (tab.value === 'write') await writeView.reload()
  else await readView.reload()
}

function reload(): void {
  void reloadActive()
}

/** 换过滤 / 换每页行数 / **换档** → 回到第一页（否则「第 3 页」在一个只剩 1 页的
 *  结果集上是空的，而空态会说「今天没有删除操作」——那是一句由分页造成的假话）。
 *  ⚠️ 换档那一格还要**触发一次读**：`useAsync` 的 `watch` 只盯自己那一份 ref，
 *  而 `tab` 不在任何一份里，故这里显式调一次。 */
function resetPage(): void {
  offset.value = 0
}

function prevPage(): void {
  offset.value = Math.max(0, offset.value - limit.value)
}

function nextPage(): void {
  offset.value += limit.value
}

watch(tab, () => {
  offset.value = 0
  void reloadActive()
})

/* ⚠️ 四个 ref 一起看：一次「换过滤」会把 `offset` 归零（下面那几个 `@change`），
   于是同一 tick 里有两个 dep 变了 —— Vue 的 watcher 按 tick 合并，故只重读一次。
   ⚠️ 两个 watcher 各自带一个 `tab` 判断：不判的话「切到读档」会**同时**触发
   写档那一份重读（`offset` 归零是两档共用的 dep），于是页面上多一次没人要的请求。 */
watch([writeSubjectKind, writeMethod, limit, offset], () => {
  if (tab.value === 'write') void writeView.reload()
})
watch([readSubjectKind, readStudentId, limit, offset], () => {
  if (tab.value === 'read') void readView.reload()
})
</script>

<template>
  <div class="a-page">
    <!-- ① 抬头 -->
    <section class="">
      <SectionHead :index="1" label="ADMIN · AUDIT TRAIL" />
      <header class="a-head">
        <div>
          <h2 class="zh-title a-head__title">审计留痕</h2>
          <p class="a-head__path data">
            /admin/audit-logs · GET {{ activeTab.endpoint }}
          </p>
        </div>
        <div class="a-head__meta">
          <span class="pill a-pill--neutral">共 {{ total }} 行</span>
          <span class="pill pill--green">仅 role=admin 可读</span>
          <span class="pill a-pill--solid">只读 · 无写操作</span>
        </div>
      </header>
    </section>

    <!-- ② 口径：两张表各记什么、不记什么 -->
    <section class="">
      <SectionHead :index="2" level="amber" label="WHAT IT RECORDS" />
      <div class="a-note">
        <span class="a-note__title">
          两档口径（一律是后端的既有裁定，本页只把它摊开）
        </span>
        <p>
          <strong>「写」档只记三个写方法</strong>：<code class="data">POST</code> /
          <code class="data">PATCH</code> / <code class="data">DELETE</code>
          （唯一所有者是后端 <code class="data">app/api/audit.py</code> 的
          <code class="data">AUDITED_METHODS</code>）+ 登录 / 登出 / 两个绑定。
          ⚠️ 翻「写」这一页自己**不会**留下行（否则审计页会自己喂自己）。
        </p>
        <p>
          <strong>「读」档只记敏感读</strong>：后端把
          <code class="data">/openapi.json</code> 的 <strong>64</strong> 个 GET
          逐个归了类，其中 <strong>46 记 / 18 不记</strong>，而那张
          「路由模板 → 归类」的表是<strong>唯一</strong>的判据住址
          （<code class="data">app/api/read_audit.py</code> 的
          <code class="data">READ_ROUTES</code> + <code class="data">READ_CLASSES</code>）。
          ⚠️ <strong>不记的那 18 条</strong>是：7 个参考数据资源（学期 / 班级 / 体测批次 /
          百分位快照 / 动作库 / 处方模板 / 课次，<strong>一行学生键都没有</strong>）的
          集合与成员 GET、存活探针 <code class="data">/api/health</code>（隧道每 60 秒打一次）、
          会话自证 <code class="data">/api/auth/me</code>（前端每次路由守卫都打一次）、
          与课次级快评口令那两格。⚠️ 全部 GET 都记的话，量级会淹掉真正要看的那几行。
        </p>
        <p>
          <strong>「读」档不记匿名</strong>：那 46 条<strong>全部</strong>要身份
          （匿名一律 <code class="data">401</code>），而一行「匿名读了什么」答不出
          <strong>谁</strong>——本表存在的理由就是答「<strong>谁</strong>翻过谁的档案」。
          ⚠️ 那一格还有一道 <strong>DB 层</strong>的闸
          （<code class="data">subject_kind</code> 的 CHECK 只有
          <code class="data">student</code> / <code class="data">teacher</code> 两档），
          故「把判据放宽到匿名也记」会先撞成一次响亮的失败、而不是静默灌一批无主的行。
          ⚠️ 而<strong>「写」档刻意相反</strong>：它<strong>要</strong>匿名的行
          （<code class="data">anonymous</code> 那一档就是「<strong>谁在撞门</strong>」）。
        </p>
        <p>
          <strong>「读」档里 <code class="data">403</code> 也记</strong>：一个
          <strong>已登录</strong>的人试了一次他范围外的读（例如教师翻别的班的学生），
          那一行会带着 <code class="data">status = 403</code> 落下来。⚠️ 它是
          「有人在探边界」的<strong>唯一</strong>可见性——后端那些闸门
          <strong>故意不回显</strong>「你差在哪」（回显就是一个枚举信号）。
          ⚠️ 于是在「读」档里看到 403 <strong>不是</strong>故障，是一格事实。
        </p>
        <p>
          <strong>「自己翻自己」也记</strong>：学生读自己的档案、教师读自己任教班的学生，
          两档<strong>都留一行</strong>。⚠️ 判据里<strong>刻意没有</strong>「是不是自己」
          这一维（46 条里有 21 条身上根本没有「某一个学生」，于是「自己翻自己」
          会变成一个只对一半端点生效的例外）；⚠️ 而它<strong>正是</strong>抢绑那一族
          要看的线索：一个刚被抢绑的账号第一次登录就会把自己那份档案翻一遍。
        </p>
        <p>
          <strong>九格全是标量，一个请求体、一个查询串都不落</strong>：那两张表的 9 列里
          <strong>根本没有</strong>能装它们的位置，故「不记请求体」是一条
          <strong>结构性质</strong>、不是「克制住不写」。⚠️ 于是本页<strong>没有</strong>
          「请求体」列，也<strong>没有</strong>耗时 / ip / user-agent ——
          它们不在这两个契约里，凭空加一列就是凭空撒一句关于那张表的谎。
          ⚠️ 「读」档的 <code class="data">route</code> 那一列存的是
          <strong>路由模板</strong>（<code class="data">/api/students/{student_id}</code>）
          而不是请求路径原文，故<strong>查询串</strong>连一个能落进去的位置都没有。
        </p>
        <p>
          <strong>「身份」那三格怎么读</strong>：<code class="data">subject_kind</code> 在
          「写」档是三档（<code class="data">anonymous</code> = <strong>谁在撞门</strong>）、
          在「读」档是<strong>两档</strong>；<code class="data">subject_id</code> 是
          <strong>代理键</strong>（<code class="data">student.id</code> 或
          <code class="data">teacher.id</code>，⚠️ <strong>不是学号</strong>）；
          <code class="data">staff_no</code> 是工号、且<strong>只对教职有值</strong>。
          ⚠️ 「读」档还有一格 <code class="data">student_id</code> =
          <strong>被翻的是哪个学生</strong>（同样代理键），⚠️ 它有<strong>两档合法的
          <code class="data">null</code></strong>：① 读的是名册 / 班级聚合
          （一次请求里没有「某一个学生」）；② 读的是自己
          （<code class="data">/api/mini-tests/normalized/me</code>，那一格看「身份 id」）。
          ⚠️ 本页<strong>刻意不回查名册</strong>把代理键补成人名：鉴权失败时根本不知道是谁，
          而一个事后补出来的 id 会把「撞门的人」伪装成「在册的人」。
        </p>
        <p>
          <strong>时刻是 naive 本地时刻</strong>：<code class="data">at</code> 序列化成
          <code class="data">2025-10-12T09:30:00</code> 而<strong>不带</strong>
          <code class="data">Z</code> 后缀，故本页<strong>只切串、不建 Date</strong>
          （任何时区换算都会差 8 小时）。⚠️ 两档<strong>同一个时钟所有者</strong>
          （<code class="data">app.auth.sessions.now</code>），故把两张表按时间
          对齐着看（「他先翻了档案、然后改了它」）不会差 8 小时。
          ⚠️ 顺序都是 <code class="data">id DESC</code>（最新在前），
          与泛型 list 的升序<strong>相反</strong>，而本页<strong>不再排一次序</strong>。
        </p>
        <p>
          ⚠️ <strong>「读」档会自己喂自己一格</strong>：翻「读」这一页<strong>会</strong>
          往 <code class="data">read_audit_log</code> 里加一行
          （<code class="data">route = /api/read-audit-logs</code>）。
          ⚠️ 那一格是<strong>要的</strong>——「<strong>谁看过审计</strong>」正是它存在的理由
          （它兑现了后端两处如实记下的代价）；⚠️ 而它<strong>有界</strong>
          （一次翻页一行、只有 <code class="data">role='admin'</code> 打得到），
          处置是留存清理（读审计 90 天 / 写审计不少于 1 年）。
        </p>
      </div>
    </section>

    <!-- ③ 工具条 + 表格 -->
    <section class="">
      <SectionHead :index="3" label="ROWS" />

      <div class="a-toolbar">
        <div class="a-pager">
          <!-- ⚠️ 写 / 读 的切换。⚠️ **只用既有的 `.btn--primary` / `.btn--ghost`
               两个类**（`base.css`），故一条新 CSS 都没加、一个色值裸值都没引
               （`npm run check:tokens` 一格未退）。
               ⚠️ `data-audit-tab` 是给 `smoke.mjs` 第 14 步那三拍新取证用的钩子
               （它要点到「读」那一档、再数一次列头），⚠️ 它**不是**样式钩子。
               ⚠️ `aria-pressed` 是给读屏的：两个按钮里只有一个处于按下态。 -->
          <button
            v-for="item in AUDIT_TABS"
            :key="item.key"
            class="btn a-btn--sm"
            :class="tab === item.key ? 'btn--primary' : 'btn--ghost'"
            type="button"
            :data-audit-tab="item.key"
            :aria-pressed="tab === item.key"
            :disabled="loading"
            @click="tab = item.key"
          >
            {{ item.label }}审计 · {{ item.table }}
          </button>
          <button class="btn a-btn--sm" type="button" :disabled="!canPrev || loading" @click="prevPage">
            ← 上一页
          </button>
          <button class="btn a-btn--sm" type="button" :disabled="!canNext || loading" @click="nextPage">
            下一页 →
          </button>
          <span class="a-pager__where num">
            {{ loading ? '读取中…' : `${shownFrom}–${shownTo} / 共 ${total} 行` }}
          </span>
          <label class="a-pager__where">
            每页
            <select v-model.number="limit" class="select a-select--inline" @change="resetPage">
              <option v-for="n in LIMITS" :key="n" :value="n">{{ n }}</option>
            </select>
          </label>
          <!-- ⚠️ 两个过滤参数**就是端点那两个**（后端刻意没有第三个：没有 `since` /
               `until`、也没有 `path` / `route` 前缀匹配，逐字理由见两个 `…Filter`
               的 docstring）。⚠️ 下拉只列合法值，故「敲一个 422 进去」在本页做不到。
               ⚠️ 而「身份类型」那个下拉在**两档下列表不同**（写档三档含 `anonymous`、
               读档两档）：取值域的唯一所有者是后端那两个模型类常量，
               本页只把 `types.ts` 里指着它们的那两份常量摊开。 -->
          <label v-if="tab === 'write'" class="a-pager__where">
            身份类型
            <select v-model="writeSubjectKind" class="select a-select--inline" @change="resetPage">
              <option :value="null">（不过滤）</option>
              <option v-for="value in Object.values(AUDIT_SUBJECT_KINDS)" :key="value" :value="value">
                {{ subjectKindZh(value) }} · {{ value }}
              </option>
            </select>
          </label>
          <label v-if="tab === 'write'" class="a-pager__where">
            方法
            <select v-model="writeMethod" class="select a-select--inline" @change="resetPage">
              <option :value="null">（不过滤）</option>
              <option v-for="value in Object.values(AUDITED_METHODS)" :key="value" :value="value">
                {{ value }}
              </option>
            </select>
          </label>
          <label v-if="tab === 'read'" class="a-pager__where">
            身份类型
            <select v-model="readSubjectKind" class="select a-select--inline" @change="resetPage">
              <option :value="null">（不过滤）</option>
              <option
                v-for="value in Object.values(READ_AUDIT_SUBJECT_KINDS)"
                :key="value"
                :value="value"
              >
                {{ subjectKindZh(value) }} · {{ value }}
              </option>
            </select>
          </label>
          <!-- ⚠️ 「读」档独有的那一格：「**这一个学生**的档案被谁翻过」——
               它正是这张表存在的理由，走后端那个索引
               （`ix_read_audit_log_student_id_at`）。⚠️ 用**文本框**而不是下拉：
               60 个学生的代理键塞进一个下拉没有意义，而运维手上通常已经有那个 id
               （从名册页或从另一行审计里）。⚠️ 空串 = 不过滤；一个不是整数的串
               **不发**那个参数（`readStudentIdParam` 折成 `null`），
               于是「敲一个 422 进去」在本页同样做不到。 -->
          <label v-if="tab === 'read'" class="a-pager__where">
            学生 id
            <input
              v-model="readStudentId"
              class="select a-select--inline"
              type="text"
              inputmode="numeric"
              placeholder="（不过滤）"
              aria-label="按学生 id 过滤读审计"
              @change="resetPage"
            />
          </label>
        </div>

        <div class="a-actions">
          <button class="btn a-btn--sm" type="button" :disabled="loading" @click="reload">
            ⟳ 重读
          </button>
        </div>
      </div>

      <!-- 空态（两档共用一段，而「为什么是 0 行」那句话按档分开说） -->
      <div v-if="isEmpty" class="a-empty a-mt">
        <p class="a-empty__title zh-title">这一张表今天是 0 行</p>
        <p class="a-empty__why">
          <template v-if="tab === 'write'">
            <template v-if="writeSubjectKind !== null || writeMethod !== null">
              ⚠️ 而这一格<strong>可能是过滤造成的</strong>：当前过滤是
              <code class="data">subject_kind={{ writeSubjectKind ?? '（不限）' }}</code> ·
              <code class="data">method={{ writeMethod ?? '（不限）' }}</code>。
              把两个下拉都调回「（不过滤）」再看一次 —— 否则「今天没有删除操作」
              这句结论是由一个还挂着的过滤给出的。
            </template>
            <template v-else>
              演示库刚复原时它就是 0 行（<code class="data">demo.ps1</code> 灌数据走的是
              <strong>进程内</strong>调用，不经过 HTTP，故不产生审计行）。
              在前端登录一次、或处置一条预警，这一页立刻就有行。
            </template>
          </template>
          <template v-else>
            <template v-if="readSubjectKind !== null || readStudentId.trim() !== ''">
              ⚠️ 而这一格<strong>可能是过滤造成的</strong>：当前过滤是
              <code class="data">subject_kind={{ readSubjectKind ?? '（不限）' }}</code> ·
              <code class="data">student_id={{ readStudentIdParam() ?? '（不限）' }}</code>。
              把两格都清空再看一次 —— 否则「没有人翻过档案」这句结论是由一个
              还挂着的过滤给出的。
            </template>
            <template v-else>
              ⚠️ 而这一档<strong>更可能不是「没人翻过」</strong>：本表是
              <strong>Plan 08 Task 1</strong> 新加的，故<strong>升级之前</strong>
              发生过的读一行都没有（审计行不可重推）。
              在前端翻一屏学生详情、或打开一次名册，这一页立刻就有行
              （⚠️ 而打开本页的「读」档自己也会留下一行）。
            </template>
          </template>
        </p>
      </div>

      <!-- 写档表格（⚠️ 与下面那张 `v-if` 互斥：同一时刻 DOM 里只有一张 `.a-table`，
           否则 `smoke.mjs` 那句 `querySelectorAll('.a-table thead th')` 会数到 18 个） -->
      <div v-else-if="tab === 'write'" class="a-scroll a-mt">
        <table class="data-table a-table">
          <thead>
            <tr>
              <th v-for="column in WRITE_COLUMNS" :key="column.key" scope="col">
                {{ column.label }}
                <code class="a-slug data">{{ column.key }}</code>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in writeView.data.value?.items ?? []" :key="row.id">
              <td
                v-for="column in WRITE_COLUMNS"
                :key="column.key"
                :class="{ 'a-cell--wrap': column.wrap }"
              >
                <span v-if="column.key === 'subject_kind'" class="pill a-pill--neutral">
                  {{ writeCellOf(row, column.key) }}
                </span>
                <span v-else-if="column.key === 'method'" class="pill a-pill--solid data">
                  {{ writeCellOf(row, column.key) }}
                </span>
                <span v-else-if="column.key === 'status'" :class="statusPillOf(row.status)">
                  {{ writeCellOf(row, column.key) }}
                </span>
                <template v-else>{{ writeCellOf(row, column.key) }}</template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 读档表格 -->
      <div v-else class="a-scroll a-mt">
        <table class="data-table a-table">
          <thead>
            <tr>
              <th v-for="column in READ_COLUMNS" :key="column.key" scope="col">
                {{ column.label }}
                <code class="a-slug data">{{ column.key }}</code>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in readView.data.value?.items ?? []" :key="row.id">
              <td
                v-for="column in READ_COLUMNS"
                :key="column.key"
                :class="{ 'a-cell--wrap': column.wrap }"
              >
                <span v-if="column.key === 'subject_kind'" class="pill a-pill--neutral">
                  {{ readCellOf(row, column.key) }}
                </span>
                <span v-else-if="column.key === 'route'" class="pill a-pill--solid data">
                  {{ readCellOf(row, column.key) }}
                </span>
                <span v-else-if="column.key === 'status'" :class="statusPillOf(row.status)">
                  {{ readCellOf(row, column.key) }}
                </span>
                <template v-else>{{ readCellOf(row, column.key) }}</template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 读取失败：`useAsync` 已经把它送进 `ApiErrorBanner` 的常驻位，
           这里只留一句就地说明，不重复整份错误体（与 `ResourceList.vue` 同一条处置）。 -->
      <p v-if="error" class="a-count a-mt">
        审计行读不到（详见页面上方的错误横幅）。⚠️ 两个端点<strong>都仅 role='admin'</strong>：
        一个普通教师打过去是 <code class="data">403 forbidden</code>，
        而路由守卫本该在进本页之前就把他弹回 <code class="data">/t/dashboard</code>
        —— 故这一档若真的出现在屏上，说明会话在页面打开之后变了（例如被登出）。
      </p>

      <p class="a-count a-mt">
        ⚠️ 本页<strong>没有任何写操作</strong>：审计行不可改写是审计的第一条性质，
        后端连 <code class="data">PATCH</code> / <code class="data">DELETE</code>
        都不注册（打过去是 <code class="data">405</code>）。
        ⚠️ 而 <code class="data">audit_log</code> 与 <code class="data">read_audit_log</code>
        都<strong>不是</strong> <code class="data">catalog/resources.ts</code>
        那 23 个资源之一（它们是特例端点，同 <code class="data">/api/health</code> 那一族），
        故它们<strong>不出现</strong>在 <code class="data">/admin</code> 的资源目录那 23 格里。
      </p>
    </section>
  </div>
</template>

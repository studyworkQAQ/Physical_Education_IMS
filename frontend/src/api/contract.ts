/**
 * `contract.ts` —— **从 `/openapi.json` 读「一个写请求该填哪几格」**。
 *
 * ---------------------------------------------------------------------------
 * 为什么会有这个文件（Task 4 加的，派单的 Create 清单里没有它）
 * ---------------------------------------------------------------------------
 * 管理台要给 **9** 个可写资源各画一张「新建 / 编辑」表单。字段清单有两个可能的住址：
 *
 *  (a) 抄进 `catalog/resources.ts`（每个资源一行 `createFields: [...]`）；
 *  (b) 运行时读 `/openapi.json` 的 `components.schemas[*Create | *Update]`。
 *
 * 本文件选 **(b)**，理由是派单自己点出的那一档：
 *
 *   「⚠️ **有些列是服务端填的**（`_SERVER_FILLED_COLUMNS`）→ **编辑表单里不要出现它们**」
 *
 * 而 `_SERVER_FILLED_COLUMNS` 的**唯一住址是 `backend/tests/api/test_crud.py:1510`**
 * （实测：`app/api/crud.py` 里根本没有这个名字，只有测试侧那一份），
 * 且它今天**只有一条**：`{"/api/class-sessions": ("rpe_token",)}`。
 * 选 (a) 就意味着前端要照着**一个测试文件的常量**手抄 45 个字段名，
 * 并且后端每加一列就漂一次；选 (b) 则「请求模型不收的列不会出现在表单里」
 * 是**自动成立**的 —— 表单只画 `*Create` / `*Update` 的 `properties`，
 * 而后端刻意不让请求模型带上那些列（`app/api/schemas/feedback.py:399` 的守卫
 * `test_the_request_models_cannot_carry_the_server_filled_fields` 钉的就是这一格）。
 *
 * ⚠️ **一处更正（顶回）**：派单举的三个例子（`submitted_at` / `late` / `batch_id`）
 * 里，前两个属于 `training-logs` / `rpe-records` —— 那两个资源**不是泛型 CRUD 可写的**
 * （写入走各自的学生头特例端点，请求模型是 `TrainingLogCreate` / `RpeSubmitCreate`），
 * 故它们在管理台里**根本没有表单**；而 `batch_id` **在** `ClassSessionCreate` /
 * `ClassSessionUpdate` 上（可空、缺省 `null`），故它**会**出现在表单里 ——
 * 契约说收，本表单就画。**判据一律是契约，不是一份清单。**
 *
 * 实测（Task 4 从 `/openapi.json` 逐个读出来的，9 个可写资源全中）：
 * **`*Update` 的字段集与 `*Create` 逐字相等**，而 `*Read` = `*Create` + `id`。
 * 故「一张表单同时服务新建与编辑」是安全的，差异只有「编辑时 `id` 不在表单里」。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 它**不是** codegen 的替代品
 * ---------------------------------------------------------------------------
 * `generated/schema.d.ts` 给的是**编译期**类型（Task 2/3 的页面用它）；本文件给的是
 * **运行时**的字段清单（管理台的表单是数据驱动的，它渲染哪些 `<input>` 取决于响应体）。
 * 两者同源（都是那份 OpenAPI），故不会漂。
 *
 * ⚠️ 一次会话只拉一次：模块级缓存那个 Promise（**不是**缓存结果），
 * 于是并发的两个页面不会各拉一次 278 KB。
 *
 * ⚠️ 拉它走 `client.ts` 的 `apiRequest`（本前端唯一直接调 `fetch` 的地方），
 * 故 `vite.config.ts` 的 `server.proxy` 里**多了一条 `/openapi.json`**：
 * 它不在 `/api` 前缀下，不加那一条开发期会打到 vite 自己身上（404 index.html）。
 */
import { apiRequest } from './client'

/* ------------------------------------------------------------------ 结构类型
   ⚠️ 只声明本文件**真的读**的那几个键。OpenAPI 3.1 的完整类型有几万个组合，
      而这里要的只有「一个 schema 的 properties / required」与
      「一个操作的 requestBody 指向哪个 schema」。                          */

/** 一个 JSON Schema 节点（够用就好）。 */
interface JsonSchema {
  readonly type?: string
  readonly format?: string
  readonly anyOf?: readonly JsonSchema[]
  readonly $ref?: string
  readonly default?: unknown
  readonly additionalProperties?: unknown
  readonly items?: JsonSchema
}

interface ObjectSchema {
  readonly properties?: Record<string, JsonSchema>
  readonly required?: readonly string[]
}

interface Operation {
  readonly requestBody?: {
    readonly content?: { readonly 'application/json'?: { readonly schema?: JsonSchema } }
  }
}

interface OpenApiDoc {
  readonly paths: Record<string, Record<string, Operation>>
  readonly components?: { readonly schemas?: Record<string, ObjectSchema> }
}

/* ------------------------------------------------------------------ 字段规格 */

/** 一个输入框的**控件类型**。⚠️ 由 JSON Schema 推出来，不是猜的。 */
export type FieldKind =
  | 'string'
  | 'integer'
  | 'number'
  | 'boolean'
  /** `{"type":"string","format":"date"}` → `<input type="date">` */
  | 'date'
  /** `{"type":"string","format":"date-time"}` → `<input type="datetime-local">` */
  | 'datetime'
  /** ⚠️ `{"type":"object"}` / `{"type":"array"}`：**唯一需要 bespoke 控件的一档**
   *  （今天只有 `interest-surveys` 的 `dimensions` 与 `raw_answers` 两格），
   *  渲染成一个 JSON 文本域 + 一次 `JSON.parse` 校验。 */
  | 'json'

/** 表单里的一格。 */
export interface FormField {
  readonly name: string
  readonly kind: FieldKind
  /** 在 `required` 里。⚠️ `*Create` 有必填、`*Update` **一律全可选**
   *  （PATCH 的语义是「只改传上来的那几格」，实测 9 个 `*Update` 的 `required` 全是 `[]`）。 */
  readonly required: boolean
  /** `anyOf: [T, {"type":"null"}]` 那一档（可空）。 */
  readonly nullable: boolean
  /** schema 里写了 `default`。⚠️ 表单会把它当**占位提示**显示，
   *  但**不会**替用户填进请求体：后端有 default 的字段不传就是取 default，
   *  而前端替它填一份等于把「缺省值是多少」抄成第二个所有者。 */
  readonly hasDefault: boolean
  readonly defaultValue: unknown
}

/* ------------------------------------------------------------------ 推导 */

/** `anyOf: [{"type":"string"},{"type":"null"}]` → 取那个非 null 的分支。 */
function unwrap(schema: JsonSchema): [JsonSchema, boolean] {
  const branches = schema.anyOf
  if (!branches || branches.length === 0) return [schema, false]
  let nullable = false
  let picked: JsonSchema = schema
  for (const branch of branches) {
    if (branch.type === 'null') {
      nullable = true
      continue
    }
    picked = branch
  }
  return [picked, nullable]
}

/** 一个 JSON Schema 节点 → 控件类型。 */
export function kindOf(schema: JsonSchema): FieldKind {
  const [inner] = unwrap(schema)
  const type = inner.type
  if (type === 'object' || type === 'array') return 'json'
  if (type === 'integer') return 'integer'
  if (type === 'number') return 'number'
  if (type === 'boolean') return 'boolean'
  if (type === 'string') {
    if (inner.format === 'date') return 'date'
    if (inner.format === 'date-time') return 'datetime'
    return 'string'
  }
  // 认不出来的一律当 JSON 处理：一个文本域至少能把值原样送上去，
  // 而一个 `<input type="text">` 会把对象送成 "[object Object]"。
  return 'json'
}

/** `#/components/schemas/SemesterCreate` → `SemesterCreate`。 */
function refName(ref: string | undefined): string | null {
  if (!ref) return null
  const parts = ref.split('/')
  return parts[parts.length - 1] ?? null
}

/* ------------------------------------------------------------------ 缓存 */

let pending: Promise<OpenApiDoc> | null = null

/** 拉一次 `/openapi.json`（**模块级缓存那个 Promise**，故并发只拉一次）。 */
export function loadOpenApi(): Promise<OpenApiDoc> {
  if (pending === null) {
    pending = apiRequest<OpenApiDoc>('GET', '/openapi.json')
  }
  return pending
}

/** 清缓存。⚠️ 只在「拉失败了、要重试」时用：一个失败的 Promise 被缓存下来
 *  会让每一次重试都拿到同一份错误。 */
export function resetOpenApi(): void {
  pending = null
}

/** 一个资源路径 + 方法 → 它的请求体 schema 名（`SemesterCreate`）。
 *  端点不存在（14 个只读资源的 POST/PATCH）→ `null`。 */
export function requestSchemaName(
  doc: OpenApiDoc,
  path: string,
  method: 'post' | 'patch',
): string | null {
  const op = doc.paths[path]?.[method]
  if (!op) return null
  return refName(op.requestBody?.content?.['application/json']?.schema?.$ref)
}

/**
 * 一个资源的写请求在 OpenAPI 的 `paths` 里挂哪个键。
 *
 * ⚠️ **POST 与 PATCH 不在同一个键上**（Task 4 实测踩到的一格）：
 * POST 挂在**集合**路径（`/api/semesters`），PATCH 挂在**成员**路径
 * （`/api/semesters/{semester_id}`）。而那个成员路径的花括号里是
 * **该资源的 pk 别名**（`catalog/resources.ts` 的 `pkField`，23 个各不相同，
 * 唯一的手工覆盖是 `fitness-test-batches` → `fitness_test_batch_id`）。
 * 拿集合路径去查 PATCH 会**静默**得到 `null` → 一张空表单
 * （提交按钮还在，于是看起来像「表单坏了」而不是「路径查错了」）。
 */
export function writePathOf(
  basePath: string,
  pkField: string,
  method: 'post' | 'patch',
): string {
  return method === 'post' ? basePath : `${basePath}/{${pkField}}`
}

/** 一个 schema 名 → 它的表单字段（**顺序 = `properties` 的声明序**，
 *  而后端的声明序与 DB 列序一致，故表单读起来就是那张表）。 */
export function fieldsOfSchema(doc: OpenApiDoc, schemaName: string | null): FormField[] {
  if (!schemaName) return []
  const schema = doc.components?.schemas?.[schemaName]
  if (!schema || !schema.properties) return []
  const required = new Set(schema.required ?? [])
  return Object.entries(schema.properties).map(([name, prop]) => {
    const [, nullable] = unwrap(prop)
    return {
      name,
      kind: kindOf(prop),
      required: required.has(name),
      nullable,
      hasDefault: Object.prototype.hasOwnProperty.call(prop, 'default'),
      defaultValue: prop.default,
    }
  })
}

/** 一步到位：`('/api/semesters', 'semester_id', 'post')` → 那张表单该画哪几格。
 *  ⚠️ `pkField` 只在 `method === 'patch'` 时用得上（见 {@link writePathOf}）。 */
export async function formFields(
  basePath: string,
  pkField: string,
  method: 'post' | 'patch',
): Promise<{ schemaName: string | null; fields: FormField[] }> {
  const doc = await loadOpenApi()
  const path = writePathOf(basePath, pkField, method)
  const schemaName = requestSchemaName(doc, path, method)
  return { schemaName, fields: fieldsOfSchema(doc, schemaName) }
}

/* ------------------------------------------------------------------ 取值与回填
   ⚠️ 两个方向的转换都必须过这里，于是「一个 `date` 字段在表单里长什么样」
      只有一个住址。`<input type="date">` 的值是 `YYYY-MM-DD`（与后端的
      `format: date` 逐字相同），`datetime-local` 是 `YYYY-MM-DDTHH:mm`
      （**少一个时区**，故提交前要补成后端要的 ISO 串）。                  */

/** 后端给的值 → 输入框里该显示的串。 */
export function toInputValue(field: FormField, value: unknown): string {
  if (value === null || value === undefined) return ''
  if (field.kind === 'boolean') return value === true ? 'true' : 'false'
  if (field.kind === 'json') {
    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return String(value)
    }
  }
  if (field.kind === 'datetime') {
    const text = String(value)
    // `2025-10-12T08:30:00` → `2025-10-12T08:30`（`datetime-local` 只吃到分钟）
    return text.length >= 16 ? text.slice(0, 16) : text
  }
  return String(value)
}

/** 输入框里的串 → 请求体里的值。
 *
 *  ⚠️ **空串一律变成「这一格不传」**（返回 `undefined`），不是变成 `null`：
 *  PATCH 的语义是「只改传上来的那几格」，而 `{"weeks": null}` 会被 Pydantic
 *  折成 422。可空的字段要**显式**清空时用 {@link NULL_SENTINEL}。
 *  ⚠️ 类型转换在这里做（`integer` → `Number`），于是页面不必自己判 kind。
 *
 *  @throws 值不合法时抛一个 `Error`（**不是** `ApiError`）：那一档还没发请求，
 *          不该走后端错误横幅，而应该在表单旁边就地显示。
 */
export const NULL_SENTINEL = '__null__'

export function fromInputValue(field: FormField, raw: string): unknown {
  const text = raw.trim()
  if (text === NULL_SENTINEL) return null
  if (text === '') {
    if (field.required) throw new Error(`「${field.name}」是必填的。`)
    return undefined
  }
  switch (field.kind) {
    case 'integer': {
      const n = Number(text)
      if (!Number.isInteger(n)) throw new Error(`「${field.name}」要一个整数，收到的是「${text}」。`)
      return n
    }
    case 'number': {
      const n = Number(text)
      if (!Number.isFinite(n)) throw new Error(`「${field.name}」要一个数，收到的是「${text}」。`)
      return n
    }
    case 'boolean':
      return text === 'true'
    case 'json': {
      try {
        return JSON.parse(text) as unknown
      } catch {
        throw new Error(`「${field.name}」要一段合法的 JSON（对象或数组），现在解析不出来。`)
      }
    }
    default:
      return text
  }
}

/**
 * 一整张表单 → 一个请求体。
 *
 * ⚠️ 它是 {@link fromInputValue} 的批量版，**两个页面共用**（新建与编辑），
 * 于是「哪些键会进请求体」这件事只有一个住址。
 *
 * @returns `error` 非空时 `body` 是 `null`（**第一格**解析失败就停，
 *   不把半份请求体交出去）。`error` 是给人看的一句中文，就地显示在表单旁边
 *   —— 它**不是** `ApiError`：那一档还没发请求，不该走后端错误横幅。
 */
export function assembleBody(
  fields: readonly FormField[],
  values: Record<string, string>,
): { body: Record<string, unknown> | null; error: string | null } {
  const body: Record<string, unknown> = {}
  for (const field of fields) {
    let value: unknown
    try {
      value = fromInputValue(field, values[field.name] ?? '')
    } catch (err) {
      return { body: null, error: err instanceof Error ? err.message : String(err) }
    }
    if (value !== undefined) body[field.name] = value
  }
  return { body, error: null }
}

/**
 * 还差哪几格必填。
 *
 * ⚠️ 它存在的理由是**把两档错误分开**：「必填的还没填」与「填了但解析不出来」
 * 是两件不同的事，而 {@link assembleBody} 只报第一个撞上的（必填那一档会先撞上，
 * 于是刚打开的空表单会立刻显示「『name』是必填的」—— 用户还没开始填就被骂了一句）。
 * 预览因此先问本函数：**缺必填**就说缺哪几格，只有全都填了才去解析。
 *
 * ⚠️ 只有 `*Create` 有必填；9 个 `*Update` 的 `required` 实测**全是 `[]`**，
 * 故编辑表单里本函数恒返回 `[]`。
 */
export function missingRequired(
  fields: readonly FormField[],
  values: Record<string, string>,
): string[] {
  return fields
    .filter((field) => field.required && (values[field.name] ?? '').trim() === '')
    .map((field) => field.name)
}

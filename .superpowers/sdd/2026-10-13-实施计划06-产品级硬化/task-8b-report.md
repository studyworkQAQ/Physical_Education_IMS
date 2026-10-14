# Plan 06 Task 8b 实现者报告 —— 接手关机事故、把两条顶回落地

> 本报告由**第二任**实现者写。上一位在同一个 Task 上做到一半、机器关机，
> 留下 5 个文件 +1514 / −236 的未提交改动与 **9 条红**。本波先打 WIP 检查点，
> 再把它续完并修绿。
>
> **结论**：全绿。`1502 passed`（不带 `--cov`）/ `1501 passed + 1 skipped`（带），
> `app/domain/` 覆盖率四格 `1268 / 0 / 376 / 0 / 100%` 一字未动，
> smoke **两档各 18/18 步 · 531 断言 · 退出码 0**，禁区一格未碰。
> ⚠️ 顶回 **3 处**（都是对派单里三格**事实陈述**的更正，附实测取证），
> 没按派单做的 **2 处**（逐字见 §7）。

---

## ① 环境与接手现场

### 1.1 环境（硬规矩 #73：开工第一件事亲跑）

| 格 | 实测 |
|---|---|
| `node --version` | **v24.19.0** |
| `python --version` | **Python 3.11.1**（无 venv，`C:\Python\python.exe`） |
| 分支 / HEAD（接手时） | `p06/teacher-scope-fix` / **`fae7e92`**（`main` 仍在 `601c79a`，Task 8 未合并） |
| 未提交改动 | 5 个文件 **+1514 / −236**（`git diff --stat` 亲验，与派单逐字一致） |
| `git stash list` | 空 |
| worktree | 主仓 + 陈旧的 `Temp/pe-baseline-e5efe6e`（**一个字节都没碰**） |
| 进程 | 接手时 8000/8001/8020/5174 无 listener；**5173 上有一个不是我起的 vite**（见 §7.4） |
| `core.autocrlf` | `true`（故后端 `.py` / `.vue` / `smoke.mjs` 工作树是 **CRLF**、入库 blob 是 LF；`schema.d.ts` 与 `.superpowers/**` 是 **LF**） |

### 1.2 WIP 检查点（派单 §0.1，第一件事）

**`de0fb8b`** —— `wip(api): Plan 06 Task 8b 检查点 —— 关机前半成品（9 红），原样入库以便续做`

原样提交那 5 个文件（`git add` 逐个文件名），commit 正文逐字写明
「本 commit **刻意是红的**（9 failed），后续 commit 会修绿；不要 revert、不要 cherry-pick」。
**没有 push、没有碰 main、没有切分支。**

### 1.3 接手时那 9 条红的原文（亲跑 `pytest tests/api/test_crud.py tests/db/test_models.py -q --no-cov` → `9 failed / 87 passed`）

| # | 测试 | 报错原文（截取） |
|---|---|---|
| 1 | `test_the_read_scope_tiers_are_pinned_to_those_seven_zero_thirteen_and_three` | `KeyError: 'staff_taught_section'`（`by_tier` 那本字典只有四档键） |
| 2 | `test_every_student_keyed_resource_declares_a_student_scoped_read_scope` | `StudentOwner(..., orphan=OrphanOwner(column='recipient_id', by='teacher_self', kind=('recipient_kind','teacher'))) != StudentOwner(..., orphan=None)` |
| 3 | `test_the_student_keyed_resources_admit_four_read_tiers` | `assert (13, 2) == (13, 3)` |
| 4 | `test_a_notification_addressed_to_a_teacher_is_not_readable_by_a_student` | `AssertionError: ('/api/notifications/2', '{"error":{"code":"forbidden","message":"notification 的这一行没有学生所有者，而它也**不属于**教师 'T2025900'：第二根轴的判据是「recipient_id 落在他本学期的任教范围里」（teacher_self），逐字见 app/api/crud.py 的 _orphan_condition","detail":null}}')` + `assert 403 == 200` |
| 5 | `test_a_class_level_alert_is_visible_to_the_teacher_of_that_section_only` | 同形（`taught_section` 那支）：`('/api/alerts/2', '…第二根轴的判据是「course_section_id 落在他本学期的任教范围里」（taught_section），逐字见 app/api/crud.py 的 _orphan_condition…')` + `assert 403 == 200` |
| 6 | `test_a_notification_addressed_to_a_teacher_is_readable_by_him_only` | `assert 403 == 200`，`where 403 = get('/api/notifications/2', headers={'X-Teacher-Staff-No': 'T2025900'})` |
| 7 | `test_no_column_uses_builtin_sqlalchemy_json` | `守卫的覆盖面必须先被确认是这 27 张表` |
| 8 | `test_only_batch_owned_tables_expose_batch_id` | 同上（`27 张表`） |
| 9 | `test_models_public_namespace_is_unchanged_by_the_split` | `少了 []，多了 ['audit']` |

⚠️⚠️ **而 4 / 5 / 6 三条的根因与派单 §0.2 那张表的判断不同**（逐字见 §7.1 顶回 2）：
它们**全部**倒在 `_require_orphan_row_readable` **缺管理员那一支**上，
不是倒在 403 的文案上。取证：三条红的失败行分别是
`test_crud.py:3411`（③ 管理员 read-one）、`:3554`（② 管理员 read-one）、
`:3738`（⑤ 管理员 read-one），三处用的都是 `admin_headers`（= `T2025900`）；
而「教师本人读不到」那一格**当时就是绿的**（第 6 条的 ② 拍在 ⑤ 拍之前就过了）。
403 文案泄漏是真事、也真修了（§3.4），但它是**在报错文本里被顺带看见的**，
不是这三条红的原因。

---

## ② `test_models.py` 事故的定位取证

### 2.1 它是什么事故

`git diff fae7e92 -- backend/tests/db/test_models.py` → **24 insertions / 50 deletions**
（181 行 diff **全读过**）。逐行看下来，那 74 行改动里 **没有一处是 Task 8b 需要的**：
第二根轴 `orphan` 与第五档 `staff_taught_section` 都不碰表数、不碰子模块清单、
不碰 CHECK 列数、不碰 `models` 的公有导入面。它整份是 **Task 5 的更新被写回了旧版**：

| 被冲掉的一格 | HEAD（`fae7e92`） | 工作树（事故版） |
|---|---|---|
| 表数（两处守卫的覆盖面断言 + 散文） | **28** | 27 |
| `_MODELS_SUBMODULES` | **8** 项，含 `audit` | 7 项，`audit` 消失 |
| Ruling 97 的表类 | **14**（含 `("audit", ("AuditLog",))`） | 13 |
| `_in_domain` 的 CHECK 列 | **29**（+ `audit_log.subject_kind`） | 28 |
| `audit_log.method` 那一段「看着像枚举、却故意不设防」的逐字理由 | 在 | **整段消失** |
| `audit_log` 不该被 `delete_by_batch` 碰的理由 | 在 | **整段消失** |
| `test_all_twenty_eight_tables_created` 的引用 | 与函数名一致 | 引用被改成 `…_twenty_seven_…`，**而函数名没改** |

⚠️ 最后那一行是**决定性的**：文件内部自相矛盾（函数还叫 `twenty_eight`、
docstring 却引用 `twenty_seven`），那是「编辑器写回一份旧缓冲」的形状，
不是「有人有意改口径」的形状。派单的判断（「我判断是事故」）**成立**。

### 2.2 怎么还原的

`git checkout fae7e92 -- backend/tests/db/test_models.py` —— **整文件还原，一行不保留**
（因为那 74 行里没有一行是 8b 需要的）。
⚠️ 取证：`git diff --stat fae7e92 HEAD` 的最终输出里**没有** `test_models.py` 这一行
→ 它与 `fae7e92` **逐字节相同**。

### 2.3 还原后三格实测（探针直接读运行时，不是读代码）

| 格 | 实测 |
|---|---|
| ① `len(Base.metadata.tables)` | **28**（`audit_log` 与 `login_attempt` 都在） |
| ② `len(_MODELS_PUBLIC_BASELINE)` | **33** |
| ③ `len(_MODELS_SUBMODULES)` | **8** = `assessment / audit / auth / derived / feedback / ops / organisation / prescription` |
| ④（顺手）Ruling 97 的表类 | **14** = `prescription 4 + feedback 7 + auth 2 + audit 1` |

⚠️ 派单写的是「`_MODELS_PUBLIC_BASELINE` 是 **33** 项且含 `audit`」——
**后半句与实测不符**（逐字见 §7.1 顶回 1）：`'audit'` 不在那 33 项里，
它在 `_MODELS_SUBMODULES`（8 项）里；第 9 条红报的 `多了 ['audit']`
正是因为**排除集**少了它，而不是因为基线少了它。33 这个数**是对的**。

---

## ③ 裁定 A：`StudentOwner` 的第二根轴 `orphan`

### 3.1 落地的形状（承接上一位实现者已选的形状，我认可、续做）

`OrphanOwner(column, by, kind)` 挂在 `StudentOwner.orphan` 上（**frozen** dataclass），
两档判据由 `ORPHAN_BY_VALUES` 那两个常量做唯一所有者：

| 档 | 声明（`catalog.RESOURCES` 逐行显式） | 生成的 SQL 判据 |
|---|---|---|
| `ORPHAN_BY_TAUGHT_SECTION` | `alerts` → `StudentOwner(column="student_id", orphan=OrphanOwner(column="course_section_id", by=…))` | `alert.student_id IS NULL AND alert.course_section_id IN (taught_section_ids(me, 本学期))` |
| `ORPHAN_BY_TEACHER_SELF` | `notifications` → `StudentOwner(column="recipient_id", kind=("recipient_kind","student"), orphan=OrphanOwner(column="recipient_id", by=…, kind=("recipient_kind","teacher")))` | `recipient_kind='teacher' AND recipient_id = 我作为教师的 id` |

派单 §1 裁定 A 的五条要求逐格核过：

1. **判据单一所有者** ✅ —— 两档都复用 `app/api/deps.py::taught_section_ids`
   （第四档的 `taught_student_ids` 就是它的 `IN (…)` 消费者）。本波**没有**写第二个
   「哪些班是我的」。`deps.py` 的 docstring 把它从「两个消费者」改成「**四个**」，
   并逐字写明后两个与它们的 read-one 那一侧同源。
2. **403 的 message 不复述内部实现** ✅ —— 见 §3.4，且有守卫钉住。
3. **`total` 是过滤后的** ✅ —— `_list_page` 拿的是 `_taught_filter` 那**一个**
   `WHERE`（它把 orphan 那一支 `OR` 上来），`total` 与 `items` 同源；
   矩阵里每一格 `total` 都被断言（§3.2 / §3.3）。
4. **定点变异** ✅ —— M1（去掉 `OR`）与 M2a/M2b（两种判据互换）全红，见 §3.5。
5. **只能靠 pytest 夹具造这两类行** ✅ —— `other_section` 那第二个班 +
   第二位带班教师是本波三条守卫能取证的**全部理由**；`backend/data/**` 一个字节没动
   （§8 的四个指纹 + 18 模板指纹全绿）。⚠️ 于是 **smoke 覆盖不到它**，
   已按派单要求显式登记（§7.3 待清扫 1）。

⚠️ **「`OrphanOwner` 该不该长在 `StudentOwner` 上」（派单点名的最可能顶回项）—— 我核过、不顶回**：
「这一行有没有学生所有者」与「没有的话按哪一格判」是**同一行数据**的两个问题；
拆成两个平行声明的话 `RESOURCES` 那 2 行要各挂两格，而「两格对不对得上」
（主轴 `recipient_id`+`kind='student'`、第二根轴却写了别的列）会变成只有人能回答的问题。
⚠️ 而工厂的**第 15 道校验**把这件事机器化了（四支：`by` 的取值域 / 列在不在表上 /
`via` 与 `orphan` 不许并存 / 两根轴的 `kind` 必须读**同一列的两个不同取值**），
故「对不对得上」今天不是只有人能回答。

### 3.2 班级级预警的矩阵（守卫 `test_a_class_level_alert_is_visible_to_the_teacher_of_that_section_only`）

夹具自己造**两行**班级级预警（形状逐字照 `alert_stage` 那个班级级循环：
`student_id=None` + `course_section_id=<班>`，两列恰好一个非空 = `ck_alert_subject_is_exactly_one`），
两个班各一行；另有一行 seeded 的**学生级**预警当反空转。

| 身份 | read-one 我班那条 | read-one 别的班那条 | read-one 学生级那条 | list `total` |
|---|---|---|---|---|
| 匿名 | **401** `unauthenticated` | **401** | 401 | 401 |
| 教 seeded 那个班的教师（`T2025001`） | **200** | **403** `forbidden` | **200** | **2** |
| 教另一个班的教师（`other_section`） | **403** | **200** | **403** | **1** |
| 不带任何班的教师（`T2025901`） | **403** | **403** | **403** | **0** |
| 管理员（`T2025900`） | **200** | **200** | 200 | **3** |
| 学生（seeded） | **403** | **403** | 200 | **1** |

⚠️ 「教另一个班的教师 list 恰好 **1** 行」那一格是承重的：他那个班**没有编任何学生**，
故 seeded 那条学生级预警对他不可见 —— 它顺带钉住「**第二根轴没有把主轴一起放宽**」。
⚠️ 本条由 Task 8 的
`test_a_class_level_alert_is_invisible_to_its_own_teacher_and_visible_to_an_admin`
**改名 + 翻转**而来（改前它断「教那个班的教师 403」并把那格 Critical 钉住，
好让修它的人先看到红）。**翻转它本身就是取证。**

### 3.3 发给教师的站内信的矩阵（守卫 `test_a_notification_addressed_to_a_teacher_is_readable_by_him_only`）

| 身份 | read-one | list `total` |
|---|---|---|
| 匿名 | **401** | 401 |
| **收件人本人** | **200**（响应体里 `recipient_kind='teacher'` / `recipient_id` = 他） | **1**（只有这一行；seeded 那条「发给学生」的对它不可见） |
| 别的带班教师 | **403** | **1**（= seeded 那条发给学生的；且他 read-one 它 **200** = 反空转） |
| 不带任何班的教师 | **403** | **0** |
| 管理员 | **200** | **2**（两根轴都放开） |
| seeded 那个学生 | **403** | 不含它 |
| **与收件人同号的那个学生** | **403** | 不含它 |

⚠️ 最后一行是本条**最刁钻**的一拍：`student.id` 与 `teacher.id` 是两个独立的自增序列、
必然重叠，故夹具先插**第二个学生**（它的 id 于是恰好等于收件人那一位教师的 id，
并用一句 `assert twin_id == other_section["teacher_id"]` 把「恰好相等」**断言出来**、
不再靠巧合）。少了它，「`OrphanOwner.kind` 那一格被删掉」是**绿的**。
⚠️ 另有 `test_a_notification_addressed_to_a_teacher_is_not_readable_by_a_student`
的第 ④ 拍被**翻转**（改前断「教那个学生的教师 403」，今天断「收件人本人 200」），
而它的 ①②③ 三拍（学生读不到）**判据一个字没改** —— 学生那一支走 `_owner_filter`，
一个字节都没动。

### 3.4 403 文案的收窄（一格**信息泄漏**）

改前那三份 message 把**给实现者读的话发给了调用方**：

```text
notification 的这一行没有学生所有者，而它也**不属于**教师 'T2025900'：
第二根轴的判据是「recipient_id 落在他本学期的任教范围里」（teacher_self），
逐字见 app/api/crud.py 的 _orphan_condition
```

四格全中：内部设计词汇（「第二根轴」）/ 档位常量（`teacher_self`）/
模块路径（`app/api/crud.py`）/ 私有函数名（`_orphan_condition`）。
⚠️ 而 `teacher_self` 那一支的文案**还是假的**：它写「落在他本学期的任教范围里」，
实际判据是「就是我本人」。`_require_section_readable` 同样吐了
`app.api.deps.taught_section_ids`。

收窄后（实测原文，产品档 8020）：

```text
weekly_class_report 的这一行挂的教学班不是教师 'T0001' 本学期任教的班（判据是 course_section_id）
alert 的这一行没有学生所有者，而它挂的教学班不是教师 'T2025001' 本学期任教的班（判据是 course_section_id）
notification 的这一行没有学生所有者，而它的收件人不是教师 'T2025001' 本人（判据是 recipient_kind 与 recipient_id）
```

⚠️ **口径是照既有 403 写的**（派单要求「先 Grep 既有 `_require_row_matches` 的 message
长什么样，照它写」）：`app/api/deps.py` 里 `require_teaches_section` 的 403 逐字是
「教学班 {id} 不是教师 {staff_no!r} 任教的班（或这个班不存在）：**判据是
`course_section.teacher_id`**，两者都报 403 而不是 404…」——
即**本仓既有的 403 会点名列、但从不点名函数与模块路径**。故收窄的边界是：
去掉模块路径 / 私有函数名 / 档位常量 / 内部设计词汇，**保留列名**
（列名同时是这个资源 `read` schema 里的字段名，本来就在这次响应的邻域里）。

**守卫**：`test_the_read_denial_messages_do_not_disclose_internal_identifiers`
（新加）。四拍 = 三份**运行期可达**的 message（班级级预警 / 教师站内信 / 别的班周报）
+ 一份 **HTTP 层不可达**的防御支（「这张表没有声明第二根轴」那一支，直接调函数取证 ——
实测它今天不可达：13 个学生键资源里只有 `alert.student_id` 可空且已声明 orphan、
`notification` 那一档由种类列回答且已声明、`weekly_adjustment` 的间接键要中间行消失
而外键挡住了它）。
禁词清单 `_DENIAL_BODY_FORBIDDEN_TOKENS` **20 项**（`app/api` / `app.api` / `crud.py` /
`deps.py` / 7 个私有函数名 / `taught_section` / `teacher_self` / `StudentOwner` /
`OrphanOwner` / `READ_SCOPE` / `NOT_STUDENT_OWNED` / 「第二根轴」/「第四档」/「第五档」），
断言的是**整个响应体原文**（不只是 message 那一格）。
⚠️ **每拍带反空转**：断言表名与工号**仍然在**，故「把 message 删空 / 换成一句
`forbidden`」不会让它更绿 —— 那正是派单 §1 裁定 A 第 2 条要防的另一头
（一条「403 不许解释自己」的规矩会把「调用方拿不到任何可行动信息」变成契约）。

### 3.5 管理员那一支（本波实测出来的一格红，也就是 4/5/6 三条的真根因）

`_require_orphan_row_readable` 缺一句 `is_admin` 放行 → 管理员读一条班级级预警会 **403**，
而 list 那一侧 `_reader_filter` 的 `is_admin` 明明放行了它，
「**列表里看得见、点进去 403**」这个本仓一路在消灭的失效形态当场复活。
⚠️ 有学生所有者的那一支不需要这一句（它整个委托给 `require_teaches_student`，
那道闸门自己第一句就是 `require_staff(...) == ADMIN_ROLE → return`）；
本格**没有**那样一道闸门可委托（逐字理由住在 `_require_orphan_row_readable` 的 docstring：
`require_teaches_section` **不判学期**、而 list 那一侧判，两侧不同源正是要消灭的形状），
故必须由本模块判。判据是**同一个** `ReaderIdentity.is_admin`。

### 3.6 定点变异（派单 §1 裁定 A 第 4 条 + 我加的两条）

驱动器按字节打补丁（自动适配 CRLF、断言恰好命中 N 处）→ 跑守卫 → **还原并逐字节复核**。
6 条**全红**：

| # | 变异 | 结果 |
|---|---|---|
| **M1** | 去掉 `_taught_filter` 里 orphan 那一支的 `OR`（`return owned if orphan is None else or_(owned, orphan)` → `return owned`） | **3 条红**：班级级预警矩阵、教师站内信矩阵、多态键红档 |
| **M2a** | **声明面**把两种判据互换（`catalog.py` 的两个 `by=`） | **导入期 `ValueError`**（工厂第 15 道校验：`/api/alerts 的 student_owner.orphan.by 是 'teacher_self'，但没有给出 kind…`）→ conftest 加载失败、整个 `tests/api` 红 |
| **M2b** | **行为侧**把 `_orphan_condition` 的分派互换（两个 `if orphan.by == ORPHAN_BY_TAUGHT_SECTION` → `…TEACHER_SELF`） | **2 条红**（教师站内信那两条）。⚠️ 班级级那一条在这个夹具下**恰好同值**（seeded 那个班的 id 与那位教师的 `teacher.id` 都是 1 → `course_section_id == teacher_id` 恰好命中），故 **M2a 那一格声明面守卫是必需的补充**，两侧各钉一半（如实记，§7.2 关切 1） |
| **M3** | 去掉第五档 `_section_filter` 的 `IN` 子查询（整个 `return` 换成 `return None`） | **2 条红**：第五档矩阵 + 403 文案守卫 |
| **M4** | 把 403 的 message 改回泄漏内部标识符的那一份 | **1 条红**：`…_do_not_disclose_internal_identifiers` |
| **M5** | 去掉 `_require_orphan_row_readable` 的管理员那一支 | **3 条红** = §3.5 那格红的复现 |

⚠️ 每条变异之后驱动器都 `assert path.read_bytes() == original`，
且全部跑完后 `git status --porcelain` **空**（工作树与 `f5e8907` 逐字节相同）。

---

## ④ 裁定 B：第五档 `READ_SCOPE_STAFF_TAUGHT_SECTION`

### 4.1 T0001 / T0002 读 5 个班周报的**改前 / 改后逐格**

⚠️ **两格都是实测**（硬规矩 #89/#103：不靠读代码推断）。
产品档 `scripts\serve.ps1 -Port 8020` + **cookie 会话**（`POST /api/auth/login`，
一个身份请求头都不发）；「改前」是把 `catalog.py` 那一行临时改回
`read_scope="staff"`（并去掉 `section_column`，否则工厂第 13 道校验当场抛）、
重启产品档后量的，量完按备份**逐字节还原**（`git status` 复核干净）。

| 身份 | 改前 list `total` | 改前 5 个 read-one | 改后 list `total` | 改后 5 个 read-one |
|---|---|---|---|---|
| **T0001 陈国华**（`role=teacher`，任教班 **1 + 3**） | **5**（读到班 1–5） | **200 ×5** | **2**（班 1、3） | 班 1 → **200**、班 2 → **403**、班 3 → **200**、班 4 → **403**、班 5 → **403** |
| **T0002 林慧敏**（`role=teacher`，任教班 **2 + 4**） | **5** | **200 ×5** | **2**（班 2、4） | 班 1 → **403**、班 2 → **200**、班 3 → **403**、班 4 → **200**、班 5 → **403** |
| **T0003 赵志刚**（`role=admin`） | 5 | 200 ×5 | **5**（越过任教范围） | 200 ×5 |

⚠️ 改前 T0001 读**班 2** 那一份，`progress_board.top` 开头逐字是
`[{"student_id":48,"change_pct":188.53},{"student_id":47,"change_pct":165.0}]`
—— 那是**别的班**的进步榜（与 Task 8 登记的取证逐字一致）。
改后同一个请求是 **403**，message 见 §3.4 第一行。
⚠️ 演示库实测（`demo.ps1` 的 `[7/7]`）：`weekly_class_report` **5 行**、
`course_section` **5 个**、`alert` **32 条**、`notification` **19 条**、表数 **28**。

### 4.2 openapi 五格 + `security` / `parameters` 逐字对比

派单 §1 裁定 B 第 4 条要求「实测复核这条论证」。探针直接读 `/openapi.json`：

| 格 | 实测 | 基线 |
|---|---|---|
| `/api/` 路径模板 | **72** | 72 ✅ |
| 操作 | **100** | 100 ✅ |
| 挂 `security` 的操作 | **82** | 82 ✅ |
| GET | **61** = 匿名 **15** + 挂 security **46** | 61（15+46） ✅ |
| `components.securitySchemes` | **3** = `X-Student-Id` / `X-Teacher-Staff-No` / `pe_session` | 3 ✅ |

**一个字节都没变。** 而「第五档刻意沿用 `_require_staff_identity` 而不是 `current_reader`」
那条论证的取证（把 `security` + **请求头** `parameters` 序列化成 JSON 后逐字比）：

```json
{"header_parameters":[{"in":"header","name":"x-teacher-staff-no","required":false,
  "schema":{"anyOf":[{"type":"string"},{"type":"null"}],"title":"X-Teacher-Staff-No"}}],
 "security":[{"X-Teacher-Staff-No":[]}]}
```

上面这**一份** JSON 同时是以下 **6 个**操作的取值（逐字相同）：
`/api/weekly-class-reports`、`/api/weekly-class-reports/{weekly_class_report_id}`、
`/api/students`、`/api/students/{student_id}`、`/api/teachers`、`/api/teachers/{teacher_id}`。
→ **没有**凭空多出 `X-Student-Id`。⚠️ 这一格已**做成守卫**（不是只写在报告里）：
`test_weekly_class_reports_are_scoped_to_the_sections_a_teacher_teaches` 末段
把两档**互为对照**（`set(tier5) == set(staff_tier)` + 对照组自己一致性反空转），
比「各比一个字面量」强一格（字面量允许两档各自漂到同一个错值上）。

### 4.3 派单裁定 B 的六条要求逐格核过

1. **list 与 read-one 用同一个表达式** ✅ —— `_section_filter` 产出的表达式既进
   `_list_page` 的 `WHERE`，也进 `_require_row_matches` 那一次按主键的点查。
2. **`section_column` 逐行显式声明、不靠推断；工厂第 12/13/14 道校验核一遍** ✅ ——
   **三道都在**（`crud.py` 亲验）：第 12 道 = 第五档必填 `section_column`；
   第 13 道 = 其余四档必须省略它；第 14 道 = 那一列必须真的在这张表上
   （与 `student_owner` 那四格同一条口径，写错列名在**导入期** `ValueError`，
   不会退化成「过滤条件恒假 → 教师看到空列表」）。⚠️ 于是第五档与「学生键」
   在结构上**互斥**（第 10 道挡 `student_owner` 出现在那两档之外）。
3. **学生那一档的码逐字不变** ✅ —— 请求头通道 **401** / cookie 通道 **403**；
   守卫是 `test_the_student_keyed_resources_admit_four_read_tiers` 的 ②′ 那一次遍历
   （本波把第五档**并进**了那一次遍历，与 `staff` 档跑同一份判据）
   + 第五档矩阵的 ⑥ 拍。
4. **openapi 五格一个字节不变** ✅ —— §4.2。
5. **`_require_staff_identity` 从 `None` 改成 `ReaderIdentity`；另两个消费者行为逐字不变** ✅ ——
   `role` 由既有 `require_staff` 顺带给出（**不多一次查库**）；两份名册
   `students` / `teachers` 挂在 `dependencies=[...]` 里、返回值被 FastAPI 丢弃，
   守卫 `test_the_two_roster_resources_admit_only_staff_reads` 的**五拍一字未改而全绿**
   （含 openapi `security` 那一格 + ⑤ 反空转「响应体里确实有 `birth` / `name`」）。
6. **定点变异：去掉第五档的 IN 子查询 → 守卫红** ✅ —— M3，2 条红（§3.6）。

---

## ⑤ 裁定 C：分布守卫改名与全仓引用同步

**改名**：`test_the_read_scope_tiers_are_pinned_to_those_seven_zero_thirteen_and_three`
→ **`test_the_read_scope_tiers_are_pinned_to_those_seven_zero_thirteen_one_and_two`**

**新分布**（字面写死，不从 `RESOURCES` 反推）：**7 / 0 / 13 / 1 / 2**
= `None` / `student_self` 残留 / `staff_taught` / **`staff_taught_section`** / `staff`，
且五档各自的**名单**也逐字钉住（第五档恰好 `["/api/weekly-class-reports"]`、
`staff` 档恰好 `["/api/students","/api/teachers"]`）。

**全仓引用同步**（`Grep` 全仓取证，旧名字共 6 处）：

| 位置 | 处置 |
|---|---|
| `backend/tests/api/test_crud.py`（2 处 `:func:` 引用） | **改** |
| `Document/2026-09-28-体育闭环原型-设计spec.md`（2 处） | **改** |
| 新 docstring 里那一处 `` `seven_zero_thirteen_and_three` `` | **刻意保留**（它是解释改名来历的历史引用，不是活引用） |
| `.superpowers/sdd/…/task-8-report.md`（2 处） | **刻意不动**（已入库的历史报告；硬规矩 #66 的另一半：绑时点的历史陈述在它绑定的时点上是真的） |

→ **活文档引用同步 4 处**，改法是按**字节**替换（`Document/**` 是 CRLF + 无 BOM，
`.gitattributes` 钉着 `text eol=crlf`，故不走文本模式）。

⚠️ **另一条守卫的名字刻意不改**：`test_the_student_keyed_resources_admit_four_read_tiers`
里的 `four` **仍然为真** —— 它钉的是「**学生键**资源承认哪几档」，
而第五档与学生键在结构上互斥（工厂第 10 / 13 道校验），故一个学生键资源
**不可能**声明第五档。理由逐字写进了那条的 docstring（§7.2 关切 2 记了它的代价）。
⚠️ 顺手收了那条 docstring 里一格手抄的假数：「共 **168** 发」实测是 **172**
（32 + 130 + 1 + 9），今天由 `assert fired == 172` **机器钉住**。

⚠️ 另：`test_every_student_keyed_resource_declares_a_student_scoped_read_scope`
（第 2 条红）同步了**第二根轴的声明面** —— 13 行里**恰好 2 行**有 `orphan`、
两档判据**各一行**、两行各自的 `(column, by, kind)` 组合逐字钉住
（`alerts` 的 `orphan.kind is None`、`notifications` 的是 `("recipient_kind","teacher")`）。
少了这一段，「把第二根轴加到第三行」与「把两档判据互换」都是静默的。

---

## ⑥ 前端 + `gen:api`

### 6.1 `ClassReport.vue`（教师端周报页）—— **功能一个字没改**

派单 §2.1 要求「实测它今天怎么拿到班列表与周报」。**实测结论**：

| 它读什么 | 档位 | 用来做什么 |
|---|---|---|
| `GET /api/teachers?limit=200` | `staff`（教职） | 工号 → `teacher.id` |
| `GET /api/course-sections?limit=200` | **匿名**（`None` 档） | 选班下拉的数据源 |
| `GET /api/weekly-class-reports?limit=200` | **第五档**（本波新收） | **只**用来算 `weeksBySection`（哪几周有周报） |
| `GET /api/dashboard/weekly-class-report/{id}?week=` | 教师头 + **`require_teaches_section`** | 那一份含 5 个 JSON 列的真数据 |
| `GET /api/students?limit=200` | `staff`（教职） | `student_id` → 姓名（进步榜要显示人） |

⚠️ **派单担心的「选班下拉是全校 5 个班 → 选得到、读不到（403）」不成立**，
两条**各自独立**的理由（§7.1 顶回 3）：

1. 下拉**本来就只列我任教的班** —— 源码逐字是
   `sections: sections.items.filter((s) => me !== null && s.teacher_id === me.id)`；
2. 选中之后读的**不是**第五档，而是那个早就有 `require_teaches_section` 的特例端点
   （它**不判学期**，与第五档是两个判据、两个住址）。

第五档只收窄了第 3 行那一个 list，而它在本页只填 `weeksBySection`：
改前给的是全校 5 个班的周次、本页只查自己那几个班的键（多余的键从来读不到）；
改后给的就是我这几个班的周次 —— **可见结果逐字相同**，少读了几行别人的数据。
→ **一个新端点都没加**（派单要求「不要加新端点，除非你顶回来」；我顶回的是
「连改都不用改」，取证在 §7.1）。

**实际改的**：三处**假话** + 一段实测记录 + 一格如实记的接缝。
① 端点清单里 `teachers` / `weekly-class-reports` / `students` 三格此前逐字标着
「· **匿名**」，实测各是 **401**（`security` 各是 `[{"X-Teacher-Staff-No": []}]`）——
`AlertQueue.vue` 的同一份清单当时已经改过，本页漏了；
② 接缝：下拉的判据 `teacher_id == 我`（**不判学期**）vs 第五档的 `taught_section_ids`
（**判学期**）。⚠️ 演示库上**不可达**（`app/seed/generate.py` 第 446 行逐字把每一个
`course_section` 都写进 `current_id` 那一个学期），且失效方向是**优雅**的：
`availableWeeks` 空 → `week` 留 `null` → 特例端点取「已存下来的最新一周」→
若一份都没有就是 **404 `no_weekly_report`**（本页把它渲染成「本周周报将在周日生成」
+ 一个去大屏的按钮），**不是 403**。⚠️ 本波**刻意不给下拉加学期过滤**：
那要多读一次 `GET /api/semesters` 去问「哪一个是 `is_current`」
= 把服务端那一个判据在前端重算一遍（两个所有者）。

### 6.2 `AlertQueue.vue` —— 文案不许撒谎（派单 §2.2）

Task 8 给它加的「班级级空态的**第二个**理由」**今天是假话**，两处都改了：

| 位置 | 改前（假） | 改后 |
|---|---|---|
| 「为什么这四档筛选在客户端做」那段 | 「自 Plan 06 Task 8 起，『归属 → 班级级』那一档**对教师恒为空**，且理由不再是『规则没命中』…只有管理员读得到」 | 「在演示库上**仍然为空**，但理由**只有一个**，且它就是上面那一条『规则没命中』」+ 逐字记下本波把那一格 Critical 修了 |
| 班级级空态那块 | 「有**两个**各自独立的理由，任一个都足以让这一档为空：① 演示库没有 ② 就算触发了教师也读不到」 | **只剩 ①**；② 删掉，并补一句「而它**一旦触发**，本页就显示得到：我任教的班的班级级预警会出现在这一档里（别的班的不会）」 |
| 页头「范围」那句 | 「范围：**我本学期任教班级的学生**（不是全校）」 | 「…（不是全校），**外加我任教班自己的班级级预警**」 |
| 文件头端点清单 | ①「`staff_taught`…教师只读得到自己本学期任教班级的学生那些行」 | 补上第二根轴那半句，并逐字写明「演示库上那一类行是 **0**，故 T0001 21 行 / T0002 22 行两个数**一个都没变**」 |

⚠️ 空态那块**仍然渲染得到**（演示库上那一档确实为空），故它不是死代码。

### 6.3 `npm run gen:api` + 一致性守卫

**必须重跑**，且实测证明它真的漂了：改前产物里有 **280 行** description
与当前后端不一致（含 Task 8 登记在案的那 3 行旧漂移，例如产物里还写着
「`read_scope` 那张**四**档表」「**两个**端点分支」，而源码早已是五档 / 三个分支）。

| 格 | 实测 |
|---|---|
| `npm run gen:api` 退出码 | **0**（openapi-typescript **7.13.0**，442 ms） |
| 产物 `frontend/src/api/generated/schema.d.ts` | **+276 / −46 行**，458 139 B → **480 541 B**，纯 **LF** / 无 BOM |
| `npm run build` 退出码 | **0**（`vue-tsc -b && vite build`，497 ms） |
| 产物哈希 | `index-Dm5ljZoJ.css`（**不变**）/ **`index-COTDuJIB.js`**（Task 8 是 `index-BHZyrjkk.js`；变的是 AlertQueue / ClassReport 两页的文案） |
| 24 个未定型响应 | **不变**（smoke 第 12 步 ⑤ 拍：23 个 list + `/api/health` = 24，**绿**） |
| `npm run check:tokens` | 绿（扫描面 **35** 个文件，下界 25） |
| `npm run check:dist` | 绿（`adoptFromUrl` 0 次 / 两个 fonts 域 0 次，三条谓词都带反空转） |
| 新增依赖 | **0**（`frontend/package.json` 与 `backend/pyproject.toml` 对 `fae7e92` **零 diff**，依赖清单守卫 `tests/test_dependencies.py` 一字不红） |

**新守卫**：`test_the_generated_typescript_client_matches_the_current_openapi_document`
（`backend/tests/api/test_prescription_api.py`，批次 C「前后端对接面」那一节）。

* **正向**：当前 `/openapi.json` 里每一段 `description` 的**每一非空行**都在产物里
  逐字找得到（挡「后端改了、产物没重生成」）；
* **反向**：产物里每一行 JSDoc 内容都能在 spec 的 `description` / `summary` / `title`
  里找到出处（挡「后端**删掉**了一段说明、而产物里它还躺着」——正向那一拍对删除
  **完全无感**，故两侧都要）；
* **反空转**：正向那一拍的行数有字面下界（1500，实测去重后 **1760**）。

**取舍（速度 vs 强度，派单 §2.4 要求说明）**：

| 方案 | 强度 | 代价 |
|---|---|---|
| 跑一次 `gen:api` 再 `git diff --exit-code`（派单举的例子） | 更强（连生成器自己的输出格式漂了都抓得到） | ① 要一个**监听 8000 的真 uvicorn**（`gen:api` 的输入是一个 URL），而 `tests/` 的既有口径是「一律 `TestClient`、**一个端口都不占**」（逐字见 `tests/test_serve.py` 模块 docstring 第一节）；② 要 `frontend/node_modules` 装好（本仓的**后端**测试今天一个 Node 依赖都不要）；③ 起 uvicorn + 装依赖是秒级到分钟级 |
| **本波选的**：纯 Python 双向逐行比对 | 抓得到任何 description 漂移（含删除），抓不到「生成器输出格式变了」 | 读一次 480 KB + 两个集合比对，实测 **0.30 s**（`--durations` 亲验）；不碰 Node、不占端口 |

⚠️ 那一格漏掉的由 `package.json` 钉住的 `openapi-typescript ^7.13.0` 兜着，
已如实记为已知边界（硬规矩 #39）。
⚠️ **归一化的两个坑（都实测过、都写进了 docstring）**：
① 生成器给续行加 **4 个空格**的缩进，而原文续行没有（`inspect.cleandoc` 吃掉了公共缩进），
故两侧一律 `strip()`；② **只能剥一个 `*`** —— 本仓 docstring 里满是 markdown 项目符号
（`* **422 …** —— 口令太短`），用 `^\s*\*?\s?` 那种宽松正则会把这个符号一起吃掉、
于是逐字比对**假绿**（第一版探针就是这么错的，实测 3113 行全部「不匹配」）。
③ `info.description` 与 `components.securitySchemes[*].description` **不进产物**
（实测那 4 段长句在 `schema.d.ts` 里连头 40 个字都找不到），故两棵子树排除掉。

**定点变异**：把产物还原成 HEAD 那一份 → 本守卫**红**，报
「当前 `/openapi.json` 里有 **12** 行 description 不在 `schema.d.ts` 里」并给出重生成命令；
重跑 `gen:api` 后逐字节复现同一份产物（+276 / −46）。

### 6.4 `smoke.mjs` 两档

| 档 | 跑法 | 结果 |
|---|---|---|
| **dev** | 后端 `demo.ps1 -Port 8000` + `npm run dev`（**5174**，见 §7.4） | **18/18 步 · 531 断言 · 退出码 0** |
| **产品档** | `scripts\serve.ps1 -Port 8020`（同源，`PE_API_BASE` = `PE_WEB_BASE` = 8020；dist 不比 src 旧 → 跳过构建；`/api/health` → `{"status":"ok","tables":28,"students":60}`） | **18/18 步 · 531 断言 · 退出码 0** |

基线是 **18 步 / 520 断言**；**531 = 520 + 11**，多出来的 11 条全是第 12 步**新加的 ⑧ 拍**
（第五档的端到端取证）：教师档 `total=2`（班 1 与 3）/ 管理员档 `total=5` /
教师档 < 管理员档 / 教师档每一行的 `course_section_id` 都在「我任教的班」里 /
`total` 与 `items` 同源 / 管理员档里找得到一份不是他班的（反空转）/
read-one 别的班 **403** + `code=forbidden` / read-one 自己班 **200**（绿档）/
而那份 200 的响应体里确实有带 `student_id` 的 `progress_board`
（反空转：证明那个 403 挡住的正是这一格泄漏面）。

⚠️ **改过一格 needle**（派单 §2.3 授权的那一档，硬规矩 #92 判据本身不许改）：
第 0 步 `'weekly-class-reports': [5, 'teacher']` → `[5, 'admin']`。
**行数 5 一个字没改**，改的是取数用的身份 —— 按本表**既有的约定**
（Task 8 已经为 5 个学生键资源这么做过：这一格数的是「一个刚复原的演示库有多少行」，
与「谁能读到多少」是两件事，故一律用不被任教范围收窄的那一档）。
⚠️ 首跑（未改 needle 时）实测就是这一条红：
`第 0 步 ✗ weekly-class-reports 的行数 → actual=2 expected=5`，其余 **519 绿 / 1 红**。
⚠️「T0001 读到 2 / T0003 读到 5」那一格改由新加的 ⑧ 拍钉。

⚠️⚠️ **裁定 A 的第二根轴在 smoke 上没有对应的一拍**，且这不是漏掉的（派单 §1 裁定 A
第 5 条要求显式写明）：演示库那两类无主行各 **0** 行
（班级级规则 `YELLOW_CLASS_RPE_HIGH` 的阈值是班级 RPE 均值 > 7，实测最高 **6.93**、
差 0.07；19 行站内信全部 `recipient_kind='student'`），
而 `backend/data/**` 是指纹禁区、一字节不许动，故 smoke **造不出**它们。
→ 那一格是 **pytest-only 覆盖，产品档 smoke 无对应拍**（已登记为待清扫 1，
并逐字写进了 `smoke.mjs` 第 12 步 ⑧ 拍的注释与 spec §13.4.8 第 10 条）。

---

## ⑦ 待清扫 / 关切 / 没按派单做的 / **顶回**

### 7.1 顶回（**3 处**，都是对派单里三格事实陈述的更正，各附实测取证）

**顶回 1（口径更正）：「`_MODELS_PUBLIC_BASELINE` 是 33 项且含 `audit`」的后半句与实测不符。**
实测（探针直接读运行时）：`len(_MODELS_PUBLIC_BASELINE) == 33` ✅，
而 `'audit' in _MODELS_PUBLIC_BASELINE` 是 **False** —— `audit` 在
`_MODELS_SUBMODULES`（**8** 项）里，那是「拆包新增的子模块名」的**排除集**、
不是公有导入面的基线。第 9 条红报的 `少了 []，多了 ['audit']` 正是因为
**排除集**被事故版删掉了 `audit`，于是它作为「包属性」出现在实际命名空间里、
却不在排除集里。**33 这个数是对的**、还原口径也是对的（28 表 / 8 子模块 / 14 表类），
只是派单那半句把两个清单说成了一个。⚠️ 派单 §0.2 邀我「若实测发现 27 才是对的，顶回来」
—— **27 不对，28 才对**，与派单的判断一致（`git diff` 取证见 §2.1）。

**顶回 2（根因更正，⚠️ 影响「修什么」）：第 4 / 5 / 6 条红不是 403 文案造成的，
而是 `_require_orphan_row_readable` 缺管理员那一支。**
派单 §0.2 把第 6 条描述成「发给教师本人的站内信，教师本人读不到」——
实测**教师本人当时就读得到**（那条测试的 ② 拍「收件人本人 → 200」在 ⑤ 拍之前、
且它过了）；红的是 **⑤ 管理员 → 200** 那一拍
（`assert 403 == 200`，`headers={'X-Teacher-Staff-No': 'T2025900'}` = `admin_headers`）。
第 4 / 5 条同理（失败行分别是 `:3411` 与 `:3554`，都是管理员那一拍）。
⚠️ 这一格更正**改变了修复动作**：只按派单的描述去收窄文案，三条红**一条都不会消**
（我亲验：文案收窄 + 补上 `is_admin` 之后三条同时转绿，见 commit `f5e8907`；
而 M5 变异把 `is_admin` 那一支去掉，三条**立刻复现**）。
⚠️ 403 文案泄漏**是真事**、也真修了、也有守卫钉住（§3.4）——
它只是**不是这三条红的原因**，而是在报错文本里被顺带看见的。

**顶回 3（前端）：`ClassReport.vue` 不需要「改成只列自己任教的班」，因为它今天就是这么做的。**
派单 §2.1 的前提是「若它有『选班』下拉是**全校 5 个班**」——实测**不是**：
数据源是匿名的 `course-sections`（全校 5 个）再在客户端
`filter((s) => me !== null && s.teacher_id === me.id)`，故下拉**本来就只列我任教的班**
（T0001 → 班 1 与 3）。且选中之后读的是特例端点
`GET /api/dashboard/weekly-class-report/{id}`（它自己有 `require_teaches_section`），
**不是**第五档那个泛型 read-one，故「选得到、读不到（403）」在结构上不成立。
→ **功能一个字没改、一个新端点都没加**；改的只有三处假话与两段实测记录（§6.1）。
⚠️ 独立复核：上一位实现者在 `catalog.py` 那一行的注释里也写了同一句结论
（「故它**本来就只列我任教的班**，收紧后不需要改一个字」），我是**自己实测**之后
才读到它的，两侧一致。

### 7.2 关切（如实记，硬规矩 #39）

1. **M2b 只红了 2 条**：把 `_orphan_condition` 的分派互换之后，
   **班级级预警那条守卫没红** —— 因为夹具里 seeded 那个班的 id 与那位教师的
   `teacher.id` **恰好都是 1**，于是错误的判据 `course_section_id == teacher_id`
   恰好命中。⚠️ 这不是一格漏洞而是一格**分辨率**：声明面那一格（M2a + 遍历守卫里
   新加的 `owners["/api/alerts"] == StudentOwner(...)` 逐字比对）**红在导入期**，
   两侧各钉一半。⚠️ 若要行为侧也分得开，得让 `other_section` 那个班的 id
   与教师的 id **不重叠**——那要给夹具再插一行教师，代价与收益不成比例，故不做。
2. **`admit_four_read_tiers` 的 `four` 保留**是有代价的：下一个人看到五档表、
   再看到这个名字会愣一下。我把理由逐字写进了那条的 docstring
   （第五档与学生键在结构上互斥 → 那句话仍然为真），并在新分布守卫的 docstring 里
   **对照着**说明了「为什么那一条必须改名、这一条不必」。
3. **`gen:api` 的一致性守卫抓不到生成器自己的输出格式变化**（§6.3 的取舍表），
   靠 `package.json` 的版本钉兜着。⚠️ 而它有一个**副作用**要知道：
   任何人改任何进 openapi 的 docstring，都会让这条守卫红，
   直到他重跑 `gen:api` 并把产物一起提交 —— 那正是它设计出来的行为
   （报错信息里逐字给了重生成命令），但它会让「只改后端注释」的 commit 变成
   「后端 + 前端产物」两个文件的 commit。
4. **`progress_board` 里的 `student_id` 仍然是一个 JSON 列**：第五档收的是
   「**哪个教师**能读哪一行」，不是「一行里的哪几个学生」。要收到人就得拆子表
   （`progress_board_entry`），那是一次 schema 改动、**不在 Task 8b**
   （spec §1.2 第 18 条留着它，Task 8 也登记过）。
5. **`AlertQueue.vue` 的页面上仍然印着后端模块路径与私有标识符**
   （`backend/app/api/crud.py` 的 `OrphanOwner` / `_orphan_condition`）。
   ⚠️ 这与 §3.4 收窄 403 文案**不矛盾**：页面上那段是给**已登录的任课教师**读的
   「为什么」说明块（本页从 Task 8 起就是这个体例，改前那段逐字写着
   `_taught_filter`），而 403 是发给**被判定为不该看这一行**的调用方的。
   ⚠️ 但「产品级系统要不要在 UI 上印实现细节」这件事本身值得一问，
   已登记为待清扫 4（不在本波改：改它要动 6 个页面的体例，是一次口径决定）。

### 7.3 待清扫（**6 条**，本波新增；另收掉 Task 8 的 1 条）

1. **第二根轴在 smoke 上没有对应的一拍**（= 派单要求登记的那一条）：
   「若要 smoke 也覆盖，需要一个**不碰指纹禁区**的造数入口」——
   例如一个只在 dev 档可达、往演示库里插一条班级级预警 + 一封发给教师的站内信的
   窄端点，或让 `demo.ps1` 的 `[5/7]` 把班级 RPE 均值推过 7.0 的阈值。
   ⚠️ 两档都要小心：前者是新端点（要进 openapi 五格与 `expected` 清单），
   后者会改掉演示库的行数（smoke 第 0 步那一批 needle 全要跟着改）。
2. **`test_the_student_keyed_resources_admit_the_read_tiers`（少了 `four`）这个
   `:func:` 引用在 `test_crud.py:590` 与 `catalog.py:172` 各有一处、指向一个不存在的名字**
   —— 是 Task 8 之前就有的旧漂移（那条守卫在安全收紧波改过名），本波**没动它**
   （不在这次改名的引用面里，动它会把两格无关的 diff 混进本波）。
3. **`spec §13.6` 的前端 URL 是 `/m/` 与 `/screen/`**，而路由树今天是
   `/s/*` / `/t/*` / `/admin/*`（15 条）—— 旧漂移，本波没动。
4. **UI 上印不印后端实现细节**（§7.2 关切 5）：一次口径决定，要动 6 个页面的体例。
5. **`_require_orphan_row_readable` 里那句 `assert orphan is not None`** 是
   「`where is not None` 已经蕴含它」的反空转，今天不可达。若将来给它加第三个档，
   要回来把它换成一支真的错误处理。
6. **`$env:TEMP` 里躺着 106 个之前各波留下的 `pe_*` 探针**（`pe_dom_*` 21 个、
   `pe_edge_*` 31 个、`pe_rr_*` 14 个、`pe_t4_*` / `pe_t5_*` / `pe_task3_*` 一批、
   还有 `pe_http_run2.log` / `pe_vite.txt` / `pe_demo_final.txt` /
   `pe_fe_stale_plan01_task2_report.md` 等）。⚠️ **本波刻意没删它们**：
   ① 它们不是本波的产物，删别人的取证材料不在授权面里；
   ② 之前各波的报告里有引用到 TEMP 路径的取证，删掉会让那些引用**指空**。
   ⚠️ 而「探针跑完整目录删并复验」这条纪律对**本波**是干净的（本波 31 个全删、复验 0）。
   处置建议：由控制者裁定一次「TEMP 里的历史探针统一清掉」，
   并把「探针一律放 `$env:TEMP\<波次名>\` 子目录、跑完删**那个子目录**」写进纪律 ——
   那样「哪些是我的」就不必靠名字前缀猜。

⚠️ **本波收掉的 Task 8 待清扫 1 条**：「`gen:api` 产物在 HEAD 上先前就漂了 3 行、
无守卫抓得到」→ 已加守卫（§6.3），并实测它抓得到（还原成 HEAD 那一份 → 红，
报 12 行）。

### 7.4 没按派单做的（**2 处**）

1. **smoke dev 档跑在 5174 而不是 5173**：`npm run dev` 起来时报
   `Port 5173 is in use, trying another one...`。实测占着 5173 的是 **PID 20240**
   （`node …\Physical_Education_IMS\frontend\node_modules\vite\bin\vite.js`，
   启动于 **11:03:50**，而本波第一条命令跑在 12:04 之前不久）——
   **不是我起的**（派单 §0 说接手时 5173 无 listener，故它是接手之后、
   由本波之外的东西起来的；我一次都没往 5173 上起过服务）。
   ⚠️ 处置：**不杀它**（不是我的进程），改用 `PE_WEB_BASE=http://localhost:5174`
   跑 dev 档 smoke，于是「我起的进程我全停」这条纪律是干净的。
   ⚠️ 产品档 smoke 不受影响（同源 8020）。
2. **派单建议的 commit 切分是 5 段，我切了 5 段但边界不同**：
   派单建议「② 裁定 A 落地 + 守卫 + 变异 → ③ 裁定 B 落地 + 分布守卫改名 + openapi 五格复核」。
   而裁定 A 与 B 的**产品代码**都在 WIP 检查点 `de0fb8b` 里（上一位已经写完），
   本波要提交的是**修绿**与**守卫**，两者在 `test_crud.py` 里交织（同一批 docstring、
   同一批计数），硬拆会得到两个都不自洽的中间 commit。故我切成：
   ①`test_models.py` 还原 → ②裁定 A 收口 + 裁定 C 改名 + 裁定 B 的守卫同步 →
   ③`gen:api` + 一致性守卫 + 前端 + smoke → ④spec + 本报告。
   ⚠️ **每个中间 commit 都自洽**（②与③各自都是全绿的，亲验：
   ② 之后 `pytest tests/api/test_crud.py tests/api/test_prescription_api.py` → 81 passed；
   ③ 之后全量 1502 passed）。定点变异**不单独成 commit**（它们是取证，跑完即还原）。

---

## ⑧ 最终验收

### 8.1 后端

| 格 | 基线（`fae7e92`） | 本波实测 | 判 |
|---|---|---|---|
| `pytest -q`（不带 `--cov`） | 1498 passed | **1502 passed**（149.16 s） | ✅ **+4** = WIP 新增 2 条 + 本波新增 2 条 |
| `pytest -q --cov=app.domain --cov-branch` | 1497 passed + 1 skipped | **1501 passed + 1 skipped**（256.76 s） | ✅ 那 1 skipped 是 `test_backfill.py` 的 trace 钩子那一档（带 `--cov` 才跳） |
| `app/domain/` 覆盖率四格 | 1268 / 0 / 376 / 0 / 100% | **1268 / 0 / 376 / 0 / 100%**（`TOTAL` 行亲验） | ✅ 一字未动 |
| 表数（health 口径） | 28 | **28**（`{"status":"ok","tables":28,"students":60}`） | ✅ |
| 扫描面 | 71 | **71** = pipeline 10 + db 13 + domain 18 + api 26 + auth 4 | ✅ |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33** | ✅ |
| `_MODELS_SUBMODULES` | 8（含 `audit`） | **8**（含 `audit`） | ✅ |
| Ruling 97 的表类 | 14 | **14**（`prescription 4 + feedback 7 + auth 2 + audit 1`） | ✅ |
| 黄金用例 | 14 | **14**（守卫在 `tests/` 里，全量绿） | ✅ |
| 迁移链 | 3 单头 | **3 单头**（`demo.ps1` 亲跑打印：`→ 53e5a548c40e → 0b7da3d20211 → 7f3923d8af84`） | ✅ |
| openapi 五格 | 72 / 100 / 82 / 61（15+46）/ 3 | **72 / 100 / 82 / 61（15+46）/ 3** | ✅ 一个字节没变 |
| `securitySchemes` | 3 | **3**（`X-Student-Id` / `X-Teacher-Staff-No` / `pe_session`） | ✅ |
| `read_scope` 分布 | 7 / 0 / 13 / 3（四档） | **7 / 0 / 13 / 1 / 2**（五档） | ✅ 裁定 C |
| 新增后端依赖 | — | **0**（`backend/pyproject.toml` 对 `fae7e92` 零 diff） | ✅ |

### 8.2 前端

| 格 | 基线 | 本波实测 | 判 |
|---|---|---|---|
| 路由 | 15 条 | **15 条**（smoke 第 14 步逐条 DOM 取证，110/110） | ✅ |
| `npm run build` 退出码 | 0 | **0**（497 ms） | ✅ |
| 产物哈希 | `index-Dm5ljZoJ.css` / `index-BHZyrjkk.js` | **`index-Dm5ljZoJ.css`（不变）** / **`index-COTDuJIB.js`（变）** | ✅ CSS 一字未动；JS 变是两页文案改了 |
| `npm run check:tokens` | 绿（35 文件） | **绿**（扫描面 35，下界 25） | ✅ |
| `npm run check:dist` | 绿 | **绿**（三条谓词都带反空转） | ✅ |
| 新增依赖 | 0（有依赖清单守卫钉住） | **0**，`tests/test_dependencies.py` **一字不红** | ✅ |
| `npm run gen:api` | — | 退出码 **0**，产物 **+276 / −46**（458 139 → 480 541 B） | ✅ 有一致性守卫钉住 |
| smoke（dev） | 18 步 / 520 断言 / 0 | **18/18 · 531 · 0**（后端 8000 + vite **5174**） | ✅ +11 = 第 12 步 ⑧ 拍 |
| smoke（产品档 8020） | 18 步 / 520 断言 / 0 | **18/18 · 531 · 0**（同源） | ✅ |

### 8.3 禁区（逐格亲验）

| 格 | 实测 |
|---|---|
| `backend/pe.db` 存在？ | **False** |
| `backend/data/seed/` 文件数（`-Recurse`） | **0** |
| `git diff --stat fae7e92 HEAD -- backend/data` | **空**（工作树对 `fae7e92` 也是空） |
| 四个数据指纹 | 全绿（`tests/test_refdata*.py` 的守卫在全量里跑过；`D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` / `E48E3AC82BB45BB7`） |
| 18 个模板指纹 | 全绿（`tests/domain/test_prescription_templates.py`，含「工作树里 0 个 CRLF」那一拍） |
| `.gitattributes` | 对 `fae7e92` **零 diff**（四条钉扎一条没碰） |
| `frontend/dist` 入库？ | **0 个文件**（`git ls-files frontend/dist` 空） |
| 跑过 `app.seed.generate` / `backfill` / `daily` 吗？ | **没有**（要数据一律用 `backend\scripts\demo.ps1`，它自带两道禁区守卫，且 `[7/7]` 复核逐字打印「禁区复核：`backend\pe.db` 不存在、`backend\data\seed\` 仍为 0 文件 ✓」） |
| 工作树行尾 | 6 个被改文件全部 **纯 CRLF / 0 个裸 LF / 无 BOM**（`schema.d.ts` 与本报告是**纯 LF**，与各自的原形状一致）；spec 归一化后 **0 裸 LF** |
| 我起的进程 | **全停**（8000 三次 `demo.ps1`、8020 两次 `serve.ps1`、5174 一次 `npm run dev`，逐个 `StopCommand`；收尾复核 8000/8020/5174 无 listener，**5173 那个不是我起的、没动它**） |
| `$env:TEMP` 里**本波的**探针 | **0 个**（28 个点名文件 + 3 个 `demo.ps1` 的 `pe_demo_csv_<PID>` 目录，逐个删并复验；`pe_probe1.py` / `pe_tocrlf.py` 也删了）。⚠️ 另有 **106 个 `pe_*` 是之前各波留下的**（`pe_dom_*` / `pe_edge_*` / `pe_t4_*` / `pe_task3_*` / `pe_rr_*` / `pe_replay_*` 等，名字里各自带着波次），**不是本波产物、本波一个都没动**（逐字见 §7.3 待清扫 6） |

### 8.4 spec

| 格 | 基线 | 本波 |
|---|---|---|
| 字节数 | 287 894 B | **316 380 B**（+28 486） |
| 行数 | 2578 | **2851**（+273） |
| 行尾 | 全 CRLF | **全 CRLF**（2851 个 CRLF / **0** 个裸 LF / 0 个孤 CR） |
| BOM | 无 | **无** |
| `sha256[:16]` | `74cb465ca2cba17b` | **`865840cd3909db59`** |

改的 6 处：§1.2 第 **17** / **18** 条（两条顶回**结案**：标题加删除线 + 结案段，
Task 8 原文逐字保留）、§13.4.4（标题四档→**五档** + 那张表加第五档一行 +
`staff` 档 3→2 + 第二根轴写进第四档那一格 + 五格 openapi 的 Task 8b 复核 +
「无主行给不给教师」那段改写）、§13.4.4 末的守卫清单（改名 + 4 条新增 +
smoke ⑧ 拍 + pytest-only 那一格）、§13.4.7（item 7 与守卫清单里 **5 处**就地加
⚠️ 指回 §13.4.8，原文一律保留）、**新 §13.4.8**（10 条：第二根轴 / 两张矩阵 /
403 文案 / 第五档含改前改后逐格与 openapi 取证 / 分布守卫改名 / gen:api 守卫与取舍 /
前端两页 / 6 条定点变异 / 覆盖不到的一格）、§13.5（五格不变的 Task 8b 复核 +
codegen 守卫）、§13.11.4（断言数 500 → 520 → **531** 的时点记录 + 本波两档实测 +
那一格 needle 的处置）。

### 8.5 commit

| sha | 一句话 | 自洽？ |
|---|---|---|
| **`de0fb8b`** | WIP 检查点：把关机前的 5 个文件 +1514/−236 **原样**入库 | ⚠️ **刻意是红的**（9 failed），commit 正文逐字写明「不要 revert、不要 cherry-pick」 |
| **`0d7db3b`** | ①：`test_models.py` 按 HEAD 整文件还原（28 表 / 33 项 / 8 子模块 / `audit`） | ✅ 绿（那 3 条红随之消失） |
| **`f5e8907`** | ②：裁定 A 收口（管理员那一支 + 403 文案收窄 + 泄漏守卫）+ 裁定 C 分布守卫改名 + 裁定 B 的守卫同步 | ✅ 绿（`test_crud.py` + `test_prescription_api.py` → 81 passed） |
| **`fd94d0b`** | ③：`gen:api` 重跑 + 产物一致性守卫 + 前端两页口径 + smoke needle/⑧ 拍 | ✅ 绿（全量 1502 passed；smoke 两档 18/18 · 531 · 0） |
| **`<本 commit>`** | ④：spec（6 处）+ 本报告 | ✅ 绿（只改文档） |

⚠️ **没有 push、没有碰 `main`、没有切分支**（全程在 `p06/teacher-scope-fix` 上）。
⚠️ `main` 仍在 `601c79a`，Task 8 与本波都还没合并进去 —— 合并是控制者的动作。

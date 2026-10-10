"""T8 commit ③：dashboard + 教师端训练单变体（P8-A5）+ 通知已读。"""
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[4]
MSG = pathlib.Path(tempfile.mkdtemp(prefix="t8_msg_")) / "m3.txt"

TEXT = """feat(api): Plan03 Task 8 ③ —— 大屏/首页聚合读接口 + 教师端训练单变体 + 通知已读

四个新端点（app/api/routers/dashboard.py）+ 一个加在 alerts.py 里的动作端点：
* GET /api/dashboard/class/{course_section_id}?week=&as_of=          教师大屏（§9.1 整屏）
* GET /api/dashboard/weekly-class-report/{course_section_id}?week=   存下来的那一份周报（§4.7）
* GET /api/students/{student_id}/home?as_of=                        学生端首页（§9.2）
* GET /api/teacher/students/{student_id}/weekly-sheet?as_of=        P8-A5 的教师端变体
* POST /api/notifications/{notification_id}/read                    通知已读（§9.2 红点的另一半）

⚠️ 大屏**一条聚合都不算、一条 SQL 都不为自己写**：取数走 report_stage.class_snapshot、
聚合走 report_stage.aggregates_of —— 那两个是「怎么读一个班的一周」与「怎么调 domain
那九个纯函数」在全仓的唯一编排。守卫是
test_the_dashboard_and_the_stored_report_agree_on_the_same_sunday
（同一个周日、同一个班，现算的大屏与存下来的周报的六个共有键逐字相等）。

spec §14 #11 的「两套并存」在响应体里是两个独立的键：
rpe_threshold_lines（7 / 9，现读 alert_rules.yaml，是预警的判据线）与
screen_thresholds（3 天 / RPE > 8，现读 app.domain.report，是大屏的筛选阈值），
前端不得拿一个去画另一个。⚠️ 顶栏的「预警角标」刻意不另给一个计数
（它等于 blocks.alert_summary 里三档 pending 之和，另给一格就是第二个所有者）。

P8-A5（Task 4 留下的能力缺口）：GET /api/students/{id}/weekly-sheet 挂的是学生身份头，
教师用 X-Teacher-Staff-No 调它会 401，而 §9.1/§9.3 都要「教师点开一个学生看他的训练单」。
* 补一条教师身份的路径，用 deps.require_teacher + **任教关系**校验
  （enrollment ⋈ course_section.teacher_id，且两行的 semester_id 都必须等于
  as_of 所属的那个学期）；
* ⚠️ 顶回自己的一版：第一版的闸门**不带学期**，判据于是退化成「他曾经教过这个学生」，
  被 test_teaching_last_semester_does_not_grant_access_this_semester 当场抓到
  （一位上学期教过某人的教师仍读得到他本学期的训练单）。故 semester_id 是必填的第四个入参，
  由调用方经 current_semester_of 解析（「哪一个是本学年」的唯一所有者），闸门不自己猜；
* ⚠️ 响应体与学生侧那个端点**逐字相同**：Task 4 的 weekly_sheet 函数体被抽成
  prescription._weekly_sheet_response（两处共用同一个所有者，含两档 404 的 code 与文案），
  先例是 Task 7 把 training_days_of 从 feedback.py 提到 prescription_stage。

新增两道闸门住在 deps.py（它是「身份与作用域闸门」的既有住址）：
require_teaches_section / require_teaches_student，两者都先过 require_teacher（在册）。
⚠️ 「不存在」与「不是你的」一律同报 403（区分两者等于把在册名单告诉调用方，
口径同 require_scope）。⚠️ 而三个**写入**端点（教师覆盖 / 手动重生成 / 预警处置）
今天仍只过 require_teacher —— 如实记录，已登记为关切，收窄它们是一次一行的改动，
但那会改掉 Plan 04 教师端的可点范围，故不在本 Task 里顺手做。

学生首页的五格：当前分层 + **可解释性展开**（spec §14 #17「做」）、本周训练单、
待办卡片（已发起快评而未交的课）、未读通知数、电子勋章。
* explanation 由 stratification_result.input_snapshot **离线重建**出
  DerivedResult + StratResult 后现调 domain 的 explain()——那一列的契约逐字就是
  「判定当时的全部输入，使任一条结果都能离线复算」（spec §4.3），故不必回到原始数据；
  label / hit_rules / reason 三格一律取**库里存的**那一份，不取重建后重算的。
  守卫两条：一条手写的快照（与测试里直接调 explain 对账）+ 一条真跑 run_daily 的
  end-to-end（否则 input_snapshot 改一个键名不会让任何手写快照的测试变红，
  而首页会在生产数据上 500）。
* ⚠️ 本周完成度**刻意不在首页**：它的唯一所有者是 …/completion-rate 端点
  （再算一遍就是第二个所有者，而两处的分母窗口一旦漂开，环形进度条与被预警的
  完成率就会给出两个数）。前端在首页上发两个并行的 GET。
* ⚠️ 任何一格缺数据都返回 null、不返回 404：首页是一屏，一格缺数据不该让整屏失败。

通知已读：notification 在 CRUD 目录里是 writable=False + on_delete=forbid，
故本端点是它在 API 侧唯一的写入方，改 is_read 一列、不删行、幂等（弱网重试不是错误）。
⚠️ 收件人判据（recipient_kind = student ∧ recipient_id = 请求头里的学号）**融进了那一次查询**，
不是「先按主键取、再比两列」——recipient_id 不是外键、是多态的，故一条
recipient_kind=teacher ∧ recipient_id=1 的消息与 id=1 的那个学生在库里同形，
少了 recipient_kind 那一格，学生 1 就能把发给教师 1 的班级黄牌通知标成已读。
⚠️ 教师侧的「标已读」今天没有端点（spec §9.1 的版面里没有消息中心），已登记为关切。

前后端对接面：新增 app/api/schemas/dashboard.py（**16** 个响应模型），
五个新端点各挂对的那一格 securityScheme，故
test_the_identity_headers_are_registered_as_openapi_security_schemes 的清单
由 **12 项扩到 17 项**（那条守卫的 docstring 逐字写着「Task 8/9 每加一个带身份的
特例端点都要回来加一行——这是有意的」）。⚠️ 那 16 个模型**不进**「14 + 9 × 3 = 41」
那条算式（它数的是 23 个资源），守卫 test_the_dashboard_schemas_are_not_part_of_the_crud_matrix。
⚠️ 两个 weekly-sheet 端点在 /openapi.json 里指向**同一个** WeeklySheetRead。

include 顺序：dashboard 排在 catalog 之前（实测五个路径与 23 个资源的端点没有一个同形，
故顺序今天不承重——但规则是「特例一律在泛型之前」，一条不需要逐个 router 去论证
「它同形吗」的规则才是能执行的规则）。

新增测试 35 条（tests/api/test_dashboard.py，七支）。
全量 1189 → 1224 passed, 1 skipped。
app/domain/ 覆盖率四格：1147/0/336/0 → **1259/0/376/0/100%**（Miss 与 BrPart 仍是 0）。
"""

MSG.write_text(TEXT, encoding="utf-8", newline="\n")
raw = MSG.read_bytes()
assert raw[:3] != bytes([239, 187, 191]), "BOM!"
print("commit 信息:", len(raw), "字节, CRLF =", raw.count(bytes([13, 10])))

files = [
    "backend/app/api/deps.py",
    "backend/app/api/routers/dashboard.py",
    "backend/app/api/routers/alerts.py",
    "backend/app/api/routers/prescription.py",
    "backend/app/api/routers/__init__.py",
    "backend/app/api/schemas/dashboard.py",
    "backend/app/api/schemas/__init__.py",
    "backend/tests/api/test_dashboard.py",
    "backend/tests/api/test_prescription_api.py",
]
for f in files:
    subprocess.run(["git", "add", "--", f], cwd=ROOT, check=True)
    print("added", f)
print(subprocess.run(["git", "status", "--short"], cwd=ROOT,
                     capture_output=True, text=True).stdout)
subprocess.run(["git", "commit", "-F", str(MSG)], cwd=ROOT, check=True)
print("HEAD =", subprocess.run(["git", "log", "--oneline", "-1"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip())

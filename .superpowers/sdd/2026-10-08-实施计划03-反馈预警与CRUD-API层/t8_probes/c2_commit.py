"""T8 commit ②：report_stage + daily.py 接线。"""
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[4]
MSG = pathlib.Path(tempfile.mkdtemp(prefix="t8_msg_")) / "m2.txt"

TEXT = """feat(pipeline): Plan03 Task 8 ② —— Report 阶段接进 daily.py + _replay_cleanup 扩到七张

新增 app/pipeline/report_stage.py：spec §8.5 班级周报的生成阶段
（= spec §5 十阶段里的第 9 个 Weekly），跑在 Alert 之后、同一个 SAVEPOINT 之内。

本模块一条判据都不写：九个聚合量全在 app/domain/report.py（commit ①）。
它只有三件事——
* class_snapshot：把一个教学班一周的库里的行读成一个 ClassSnapshot；
* aggregates_of：把那个快照喂给 domain 的九个纯函数，得到七个键的载荷；
* generate_weekly_reports：把其中六个键落进 weekly_class_report 的 5 个 JsonText 列
  + suggestion 那一列 Text。

⚠️ class_snapshot / aggregates_of 是**公开面**，Task 8 ③ 的教师大屏也走它们：
大屏是实时刷新的、周报是周日存下来的，两条路径若各自读一遍库、各自调一遍 domain，
「大屏上的人均 RPE」与「同一周周报里的人均 RPE」就必然某天对不上（P8-A2 的落地）。

周日判据（spec §8.5 逐字「每周日批处理生成」）：
* 判据住在 report_stage.is_report_day + REPORT_WEEKDAY = 6（有名字的常量），
  daily.py 只持有调用点——生成器本身无条件生成，故手工补生成上周周报的入口
  不会被生成器自己挡掉；
* ⚠️ 6 是周日（weekday() 的 Monday == 0），而 isoweekday() == 6 是**周六**、
  weekday() == 7 永不成立（周报永远不生成、且全链路不报错）；
* daily.py 的调用点是两个条件：is_report_day(as_of) 且 semester_week_of(...) 非 None
  （后者挡「开学日之前的那个周日」——那一天没有学期周次，而 week 是 NOT NULL
  且是幂等键的一列）。两件事不互相掩盖。
* 三格边界测试用真实日期字面：2025-09-13 周六不生成 / 2025-09-14 周日生成 /
  2025-09-15 周一不生成，另加一条把一整周七天逐个过一遍的。

_replay_cleanup 从六张扩到七张（加 WeeklyClassReport，P8-A1）：
* 照 Alert 的形状写**裸名**（它不在 app.db.models 的公有导入面上，Ruling 97），
  而前三个带 models. 前缀是因为那三张**在**公有导入面上——两种写法的区别是一个事实、
  不是风格，故不「统一」；已实测两种在函数体里都能解析；
* 位置不承重（全库没有外键指向 weekly_class_report）；
* 清单的长度与成员由 test_the_replay_cleanup_list_is_pinned_to_seven_tables
  按 **AST 口径**钉住（7 个名字逐字），行为面由
  test_replay_cleanup_covers_weekly_class_report 钉住（跑完 _replay_cleanup 表空了）。

签名顶回：简报写的是 (session, semester_id, batch_id, week, *, as_of)，
而它跑不起来——generated_at 是 DateTime NOT NULL 且无缺省（时钟由调用方注入），
training_days_of 要 exercises（本仓既有纪律：三份参考数据一律由调用方注入）。
故补 now 与 exercises 两个 keyword-only 形参（与 Task 7 给 evaluate_alerts 补的
是同一件事）。⚠️ now 必须与预警阶段同一个：daily.py 因此把内联的
dt.datetime.now() 提成一个局部变量喂给两个阶段，守卫是
test_the_report_stage_runs_last_and_shares_one_instant_with_the_alert_stage
（期望侧是 evaluate_alerts 的 spy 现场记下来的 now）。

顶回自己的一版草稿：generate_weekly_reports 里原本又校验了一次
「semester_id 存不存在」，而 _require_batch_in_semester 过后那一档**不可达**
（daily_sync_run.semester_id 是 NOT NULL 外键），故删掉；可达的那一道在
class_snapshot 里（大屏可以直接用一个打错的 semester_id 调它）。

三个窗口口径刻意不同（硬规矩 #113：两处要回答的是不是同一个问题）：
* 完成率的分母 = 处方训练日 ∩ 学期第 N 周（周报问「这个班本周练得怎么样」），
  与 alert_stage 的「整个处方周」（GREEN_MASTERY 问「这个学生在他的处方周里练满了没」）
  刻意不同；
* 连续未打卡天数的窗口与 alert_stage **逐字相同**（同一个问题：「他失联多久了」），
  收窄到学期周会让一个上周就开始失联的学生在工单里在、在大屏上不在；
* 分子的四个条件与 _reported / _counted 两个口径一律 import alert_stage 的，不写第二份。

性能：ClassCache 按 (prescription_id, 处方周次) 记忆化训练日装配。
实测（探针 t8_probes/p2_timing.py，500 人 / 17 个班 / 1000 行 enrollment / 498 张处方）：
一次 training_days_of 约 0.39 ms，故整学期回放（16 个周日）记忆化后约 +3.1 s、
不记忆化约 +6.2 s。守卫是 test_the_cache_memoises_the_training_day_assembly
（判据是装配**次数**，不是耗时）+ 一条反证（换一个 cache 就会重新装配）。

新增测试 37 条（tests/pipeline/test_report_stage.py 35 + tests/pipeline/test_daily.py 2）。
全量 1097 → 1189 passed。
"""

MSG.write_text(TEXT, encoding="utf-8", newline="\n")
raw = MSG.read_bytes()
assert raw[:3] != bytes([239, 187, 191]), "BOM!"
print("commit 信息:", len(raw), "字节, CRLF =", raw.count(bytes([13, 10])))

files = [
    "backend/app/pipeline/report_stage.py",
    "backend/app/pipeline/daily.py",
    "backend/tests/pipeline/test_report_stage.py",
    "backend/tests/pipeline/test_daily.py",
]
for f in files:
    subprocess.run(["git", "add", "--", f], cwd=ROOT, check=True)
    print("added", f)
print(subprocess.run(["git", "status", "--short"], cwd=ROOT,
                     capture_output=True, text=True).stdout)
subprocess.run(["git", "commit", "-F", str(MSG)], cwd=ROOT, check=True)
print("HEAD =", subprocess.run(["git", "log", "--oneline", "-1"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip())

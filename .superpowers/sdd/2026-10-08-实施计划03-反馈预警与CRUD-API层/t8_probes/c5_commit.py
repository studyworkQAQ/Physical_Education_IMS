"""T8 commit ④：报告 + 派单 + 7 个探针脚本（一律按文件名逐个 add，不用 -A）。"""
import pathlib
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[4]
PLAN = ROOT / ".superpowers" / "sdd" / "2026-10-08-实施计划03-反馈预警与CRUD-API层"
PROBES = PLAN / "t8_probes"

# py_compile 会留下 __pycache__，它不该入库
cache = PROBES / "__pycache__"
if cache.is_dir():
    shutil.rmtree(cache)
    print("已删掉探针目录下的 __pycache__")

MSG = pathlib.Path(tempfile.mkdtemp(prefix="t8_msg_")) / "m4.txt"
TEXT = """docs(sdd): Plan03 Task 8 结案 —— 1225 passed，62 个端点，周报阶段接通，domain 四格 1259/0/376/0/100%

Task 8（§8.5 班级周报 + 大屏/首页聚合读接口 + 教师端训练单变体）结案。
fix round 0；顶回控制者 4 处；没按派单做的 5 处；待清扫 6 条；关切 4 条。

验收：
* 全量 1097 → **1225 passed**（带 --cov 时 1224 passed, 1 skipped）
* app/domain/ 覆盖率四格 1147/0/336/0/100% → **1259/0/376/0/100%**
  （Miss 与 BrPart 仍是 0；stmts +112、branch +40 恰为 report.py 一个文件的量）
* 表数 **25**（不建表）；_MODELS_PUBLIC_BASELINE **33**（不动）
* 扫描面 54 → **58**（pipeline 10 + db 11 + domain 18 + api 19）
* 端点数（openapi()["paths"]）57 → **62**，operations 85 → **90**
* _replay_cleanup 6 张 → **7 张**（加 WeeklyClassReport，AST 口径 + 一条测试钉住长度与成员）
* training_days_of 定义份数仍是 **1**（P8-A3）
* 带 security 的特例端点 12 → **17**；不带 security 的 /api/ 操作数 73（守卫下界 >= 70）
* 四个指纹逐字不变（含 E48E3AC82BB45BB7：按 P8-A6 不加 screen: 段），CRLF 全 0
* git diff 6127fc7 HEAD -- backend/data 为**空**；pe.db 不存在；data/seed 0 文件
* backfill 哨兵 elapsed 实测 43.96 / 48.37 s（n=2，基线 47.33 / 47.96），余量 1.86×（基线 1.88×）
  —— 取证手段照 Plan 03 Task 5：临时把阈值改成必然红的 1、读回真值、按字节还原并复核

顶回 4 处（报告 7.1 逐条）：
1. generate_weekly_reports 的签名跑不起来，缺 now 与 exercises（与 Task 7 顶回
   evaluate_alerts 签名同型同理由）；
2. ReportSummary 加第三格 errors（两层异常捕获没有它就是「只有一条日志、报表上看不见」），
   并给派单没定义的 skipped 定了口径（= 名册为空的班，且明确它不是「判不了」的垃圾桶）；
3. P8-A5 那条链**必须带学期**（派单没说）：不带的话判据退化成「他曾经教过这个学生」，
   一位上学期教过某人的教师这学期仍读得到他本学期的训练单——被自己的测试当场抓到；
4. P8-A6 不加 screen: 段是对的，而成本比派单说的更高：refdata_alerts 的校验顺序是
   「顶层键集 → version → rules 键集 → 逐条规则」，即顶层键集是**恰好相等**的判据，
   故加一个 screen: 顶层段会当场让加载器响亮失败，必须再动一个 Task 6 已结案的守卫。

没按派单做的 5 处（报告 7.2 逐条）：新增 schemas/dashboard.py（16 个响应模型，
派单 Create 清单之外，理由是 P4-A5「要确保后端和前端能够对接的上」）；
多改 deps.py / routers/prescription.py / schemas/__init__.py 三个文件；
_replay_cleanup 的 AST 断言放在 test_report_stage.py 而不是 test_daily.py（与 Task 7 同构）；
test_daily.py 的 PIPELINE_TABLES 刻意不加 weekly_class_report（那条测试跑在周一，
加了是空转守卫）；删掉 generate_weekly_reports 里一段自己第一版写的、实测不可达的学期校验。

本次一并入库的 7 个探针脚本（t8_probes/，一律不在 backend/ 下，硬规矩 #108）：
p1 基线实测 / p2 training_days_of 吞吐 / p3 domain 的 24 条变异取证（24 killed，0 存活）
/ p4 端点与 schema 计数 / p5 19 处错误响应形状的机械修正 / p6 backfill elapsed 取证
/ p7 最终验收。p3 与 p6 会临时改文件，一律先存原字节、finally 写回、写回后按字节复核。
"""
MSG.write_text(TEXT, encoding="utf-8", newline="\n")
raw = MSG.read_bytes()
assert raw[:3] != bytes([239, 187, 191]), "BOM!"
print("commit 信息:", len(raw), "字节, CRLF =", raw.count(bytes([13, 10])))

rel_plan = PLAN.relative_to(ROOT).as_posix()
files = [
    f"{rel_plan}/task-8-report.md",
    f"{rel_plan}/task-8-brief.md",
] + sorted(f"{rel_plan}/t8_probes/{p.name}" for p in PROBES.glob("*.py"))
for f in files:
    subprocess.run(["git", "add", "--", f], cwd=ROOT, check=True)
    print("added", f)

print(subprocess.run(["git", "status", "--short"], cwd=ROOT,
                     capture_output=True, text=True, encoding="utf-8").stdout)
subprocess.run(["git", "commit", "-F", str(MSG)], cwd=ROOT, check=True)
print("HEAD =", subprocess.run(["git", "log", "--oneline", "-1"], cwd=ROOT,
                               capture_output=True, text=True,
                               encoding="utf-8").stdout.strip())
print("\n--- git log -5 ---")
print(subprocess.run(["git", "log", "--oneline", "-5"], cwd=ROOT,
                     capture_output=True, text=True, encoding="utf-8").stdout)
print("--- 工作树 ---")
print(repr(subprocess.run(["git", "status", "--short"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8").stdout))

"""T8 commit 信息生成器：用 python 写 UTF-8 无 BOM 临时文件，交给 git commit -F。"""
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[4]
MSG = pathlib.Path(tempfile.mkdtemp(prefix="t8_msg_")) / "m1.txt"

TEXT = """feat(domain): Plan03 Task 8 ① —— app/domain/report.py：周报与大屏共享的九个聚合量

spec §8.5 班级周报与 §9.1 教师大屏共享同一批聚合量（分层分布、周环比流动、
人均 RPE 曲线、按层完成率、进步榜、预警汇总、算法建议、大屏异常名单），
故按 P8-A2 把它们放进 app/domain/（纯函数叶子层、无 I/O、无时钟），
而不是 router 或 report_stage —— 那里只有集成测试够得着，而 spec §12 要求
app/domain/ 100% 分支覆盖。

公开面 24 个名字（16 个常量 + 1 个值对象 + 9 个函数，__all__ 实测）。
覆盖率四格：112 stmts / Miss 0 / 40 branch / BrPart 0 / 100%。

三个「两套并存」（各有一条测试把两侧钉成不相等，防止被悄悄合并）：
* 大屏阈值 SCREEN_GAP_DAYS=3 / SCREEN_RPE_MAX=8 ≠ 预警的 2 / ≥9
  （spec §14 #11「预警=正式工单，大屏=宽松展示筛选器」）；
* 建议步长 SUGGESTION_STEP_PCT=10% ≠ spec §8.4 自动减量的 20%
  （前者是给教师的建议、不自动执行，后者对单个学生且系统自动写入）；
* 进步榜按 normalized_score 的相对变化排序 ≠ GREEN_MASTERY 的
  「三指标任一改善 ≥3%」（榜要一个可排序的单一量）。

按 P8-A6 不加 alert_rules.yaml 的 screen: 段，故 E48E3AC82BB45BB7 逐字不变；
大屏与周报的阈值/文案一律做成本模块的模块级常量并注明「待体育专家确认」。

六处 None 一律是「判不了」而不是 0（RPE 曲线的空日、上一周不存在、
一层无人可测、peak_rpe 缺失、mean/previous_mean/delta）。

domain 不 import datetime（ALLOWED_MODULES 实测六项里没有它），
故一周的 7 天以 ISO 串元组由调用方注入（RpeWeek.days）；
「学期第 N 周 → 那 7 天」的算式仍只有 alert_stage.semester_week_range
与 api 层 _week_days 两处，本模块不造第三处。

alert_summary 的 statuses 由调用方注入而不是在 domain 里再声明一份：
值域的所有者是 Alert.STATUSES，而 domain import 不到 app.db / app.pipeline，
传参比「两份并存 + 一条对账测试」少一个可能漂移的住址。

测试 55 条（tests/domain/test_report.py，八支），断言两侧不同源：
期望值一律字面写在测试里，不从被测模块读回来。
变异取证 24 条全部 killed、0 存活、0 跳过（探针 p3_mutation.py），
其中两条是「先写测试、变异存活、再补反例」的产物：
* M13（flow 名单去掉 sorted）在 id 取 9/3/6 时**存活** —— CPython 的 set
  迭代序恰好等于升序；换成实测挑出的 1/2/16（并集迭代序 [16,1,2]）后 killed
  （硬规矩 #107：用谓词挑对象之前先对一个已知反例验证谓词）；
* M23（!= → is not）在两个字面量 "yellow" 上**存活** —— 它们是同一个驻留对象；
  改成 "".join(...) 现拼的串后 killed（生产路径上的标签是从 SQLite 读回来的
  两个不同 str 对象）。
"""

MSG.write_text(TEXT, encoding="utf-8", newline="\n")
raw = MSG.read_bytes()
assert raw[:3] != bytes([239, 187, 191]), "BOM!"
print("commit 信息:", len(raw), "字节, CRLF =", raw.count(bytes([13, 10])), ", 行数 =", raw.count(bytes([10])))

files = ["backend/app/domain/report.py", "backend/tests/domain/test_report.py"]
for f in files:
    subprocess.run(["git", "add", "--", f], cwd=ROOT, check=True)
    print("added", f)
print(subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True).stdout)
subprocess.run(["git", "commit", "-F", str(MSG)], cwd=ROOT, check=True)
out = subprocess.run(["git", "log", "--oneline", "-1"], cwd=ROOT, capture_output=True, text=True).stdout
print("HEAD =", out.strip())

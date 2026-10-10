"""Task 9 落地脚本 03：写 commit 信息（UTF-8 无 BOM）并 git commit -F。

用法：python w03_commit.py <msgfile-relname> <file1> <file2> ...
"""
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[4]
MESSAGES = {
    "gc14": """test(golden): Plan03 Task 9 ① —— GC14 让 spec §7.4「BMI > 30」那一档在黄金用例里第一次真的命中

Plan 02 Task 9 结案时把这一格登记为关切：13 例的 bmi 全落在 [18.9, 25.7]，
触发 1「可求值但不命中」，于是 needs_review 与 safety_substitutions 在黄金用例里
恒为 false / 0 —— 安全后置那一环只被 tests/domain/test_prescription_safety.py
的合成输入守着，没有一个「逐条人读确认过」的真实用例走到底。

GC14（**只新增一例，既有 13 例的输入一个字节未动**）：
  男 / 19 岁 / 175.0 cm / 95.0 kg → bmi = round(95 / 1.75², 1) = 31.0 > 30
  体脂率 28.0% > 男生 20% 阈值 → C=True（reasons=("body_fat_high",)）
  50 米跑 40 分 < P25 50、坐位体前屈 60 分 < P25 62 → W=2，两项同在
  speed_flexibility 桶（13 例里没有一例的主导桶是它）→ 命中 R1 → 红
  → 模板 RED-SPD-ABN-05，safety_triggers = ["bmi_over_30", "body_fat_abnormal"]

它是 14 例里唯一同时命中两个安全触发、也是唯一 safety_substitution_count 非 0 的一例：
  substitution_count 32 = 该模板 48 个 block 里的 32 个 high
  （sprint_50m_intervals → stationary_cycling、shuttle_run → brisk_walking，等价表 v1.0）
  week1_block0_exercise_ref = "stationary_cycling"（**替身**，不是原 ref），
  而替身继承原动作的剂量：hr_zone [116, 137]、volume_unit min 逐字不变，
  weekly_volume 48.0 × safety_volume_factor 0.8 = 38.4

四格数字全部手算复核（探针 t9_probes/p05_gc14_handcheck.py）：
  38.4 = work_min 3 × sets 4 × freq 4 × 个体修正 1.0(band=mid) × week_deltas[0] 1.0
         = 48.0，再 × 0.8（rest_min 2 不计入量，spec §14 #36）
  [116, 137] = [floor(194.7 × 0.60), ceil(194.7 × 0.70)]，194.7 = 208 − 0.7 × 19

连带的三处相等断言（硬规矩 #88：先跑一次全量、把红掉的逐个收进来）：
  test_golden_case_input_and_expected_align_one_to_one_by_student_id 的
  `== 13` ×3 → `== 14`（先改断言看它红：`assert 13 == 14`，再写夹具转绿）。
  全量 1225 → **1226 passed**（多出来的 1 条是参数化的 GC14），**没有第二处相等断言变红**
  —— 这与 Plan 02 Task 6 的教训相反，那一轮漏掉的两格是「别的事实被同一改动证伪」，
  本轮实测没有那一类。

散文里的「13 例 / 13 人」按「只改当前事实、不动历史陈述」清了 28 处（7 个文件，
字节级替换，工作树行尾逐文件保持原样：全部 w/crlf、bare LF 仍为 0）。
刻意不动的三处历史陈述绑的是 Task 7 / Plan 02 Task 9 的时点：
run_stratify.py 的「代价是 13 例的 "bmi" 全 None」、test_prescription_stage.py 的
「13 例夹具的顶层没有它们」与「三档安全触发在 13 例里一档都走不到」。

muscle_low_p10 那一档**仍刻意不可达**，理由逐字写进夹具 _meta.caveats_training_package ②：
黄金用例路径刻意不调 resolve_muscle_lines，而 14 人 < MIN_SAMPLE=30 → 肌肉量组不产出行
→ P10 恒 None。要让它可达就得把样本量抬到 30 人以上，那会改掉 percentile_note 的
「24 行」与全部 14 例 P25 判定线的整个前提。needs_review=True 那一档同理仍不可达
（等价表 v1.0 给全部 5 个 high 动作都备了 low 替身）。两者的行为守卫都在
tests/domain/test_prescription_safety.py。

变异自证 3/3 killed（探针 t9_probes/p08_gc14_mutations.py，跑完从字节备份还原、
sha256[:16] 39FC9C29D9106C47 逐字相同）：
  M1 substitution_count 32 → 0                      KILLED
  M2 block0 ref stationary_cycling → sprint_50m_intervals  KILLED
  M3 curr.weight_kg 95.0 → 78.0（bmi 31.0 → 25.5）  KILLED

golden_cases.json 的指纹（**这份文件没有指纹常量钉住**，全仓 5 个指纹是国标 CSV /
exercises.yaml / exercise_equivalence.yaml / alert_rules.yaml / 18 套模板，一个都不在它上面；
下面两个数供报告与后续对账）：
  43 571 B → 51 619 B，892 → 959 行，CRLF 959 / bare LF 0
  sha256[:16] as-is      A08B6AE9A463BBA3 → 39FC9C29D9106C47
  sha256[:16] CRLF→LF    E0E2DABA0FE97344 → 9FB1C619F896D418
⚠️ backend/data/ 一个字节未动（git diff 只含 tests/ 与 app/ 下的 7 个文件）。
""",
}


def main() -> int:
    key = sys.argv[1]
    files = sys.argv[2:]
    message = MESSAGES[key]
    tmp = pathlib.Path(tempfile.gettempdir()) / f"t9_commit_{key}.txt"
    tmp.write_bytes(message.encode("utf-8"))  # 无 BOM
    assert not tmp.read_bytes().startswith(b"\xef\xbb\xbf")
    add = subprocess.run(["git", "add", "--"] + files, cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8")
    print("git add rc:", add.returncode, add.stdout, add.stderr)
    if add.returncode:
        return add.returncode
    commit = subprocess.run(["git", "commit", "-F", str(tmp)], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8")
    print("git commit rc:", commit.returncode)
    print(commit.stdout)
    print(commit.stderr)
    log = subprocess.run(["git", "log", "--oneline", "-1"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8")
    print(log.stdout)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8")
    print("status:", status.stdout)
    tmp.unlink(missing_ok=True)
    return commit.returncode


if __name__ == "__main__":
    sys.exit(main())

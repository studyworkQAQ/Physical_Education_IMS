# -*- coding: utf-8 -*-
"""写 commit message 到 UTF-8 临时文件（PowerShell 的 Add-Content 会静默写坏中文）。"""
import pathlib

MSG = """feat: Plan02 Task3 处方模板——18 套模板 YAML + prescription_template 表（第 16 张）+ 加载器与 sync_templates，531 → 581 passed

交付
- backend/data/prescription/*.yaml：**18 个**文件（一套一文件，体育专家可独立审校），
  合计 123 848 B、全部 CRLF = 0，逐个 sha256[:16] 钉在测试里。
  template_id 照 spec §7.2 :454 的 <层3>-<桶3>-<体成分3>-<序号2>（14 字符）：
  RED-END-ABN-01 … GRN-SPD-NOR-18；(green, *, abnormal) 3 套标 reachable: false。
- app/domain/prescription/templates.py：从 2 stmts 的空壳变成 **12 个公有顶层定义**
  （WeaknessBucket / BodyCompState / ReviewStatus 三个枚举、Intensity / Block / Session /
  Addon / Template 五个 frozen dataclass、TEMPLATE_LAYERS / INTENSITY_TYPES /
  ADDON_TRIGGERS 三张词表、is_reachable 一个纯函数）；Layer 从 app.domain.stratify
  **re-export**（绝对导入，理由见报告 §3.6），不新建。
- app/domain/prescription/__init__.py：公开面 **7 → 20** 个名字（两份 __all__ 一起改）。
- app/refdata_prescription.py：load_templates / templates 单例 / **sync_templates**
  （P3-A1：灌数据函数放这里、**不在** app/seed/，app/seed/ 一个字没改）；
  报错点名**文件 + 行号**（另跑一次 yaml.compose 建键路径→行号索引）。
- app/db/models/prescription.py：PrescriptionTemplate（第 **16** 张表，四个 _in_domain
  CHECK，layer 的取值域**不含** insufficient_data）。Ruling 97：不进 models 公有导入面。
- backend/data/exercises.yaml：23 → **24** 个键（P3-A4 追加 energy_expenditure_plus_5min_hiit，
  medium，故 exercise_equivalence.yaml **字节不变**、version 不需要升）。
- .gitattributes：**+1 条** backend/data/**/*.yaml text eol=lf（P3-D2，Critical：
  原有的 backend/data/*.yaml 的 * **不跨 /**、盖不住子目录）。
- spec：§14 追加 **#29**（模板审校状态占位）与 **#31**（speed_flexibility 参数空洞），
  §7.2 加 **6 条勘误**（P3-A9 裁定归本 Task）。

测试
- 531 → **581 passed**（+50：test_prescription_templates.py 4 → 42、
  test_refdata_prescription.py 45 → 57）。
- --cov=app.domain --cov-branch：TOTAL **499 stmts / Miss 0 / 120 branch / BrPart 0 / 100%**
  （441 → 499 = templates.py +56、prescription/__init__.py +2；**branch +0**，
  逐类拆解见报告 §7）。
- 表数 15 → **16**（test_models.py 三处 == 、函数名、expected 集合、列数 11 → 15 全同步）。
- REFERENCE_TABLES 加 prescription_template（**定义与 assert 两处**同步，P3-A6 第 4 项）。
- 四处钉死基线全部更新且**保持字面写死**；_PRESCRIPTION_PUBLIC_BASELINE 从裸名字改成
  (名字, 所有者模块) 二元组（公开面横跨三个所有者了），支 6a 的哨兵换成一个刻意不可能
  成为真名字的双下划线串（理由见报告 §12.2）。
- 变异验收 **10 个相位**全部串行实跑、逐个按字节复原并核 sha256（报告 §8）：
  ① M1 → 2 红（目标判据 test_loader_preserves_a_pending_review_status_verbatim）；
  ② M2a → 19 红 / M2b → 26 红（目标判据 test_every_exercise_ref_exists_in_the_exercise_library，
  加载器点名文件+行号先开火）；③ M3a → 19 红 / M3b → **2 红**（目标判据
  test_week_deltas_length_equals_microcycle_weeks）；④ M4a → 19 红 / M4c → 24 红 /
  M4d → **1 红**（目标判据 test_weekly_frequency_follows_the_guidance_document 的支 1）；
  ⑤ M5a → 19 红 / M5b → 19 红（两者红名单**互相鉴别**：M5a 含指纹不含 is_reachable，
  M5b 反之）。

禁区自证：pe.db 不存在；data/seed/ 0 文件；national_standard_2014.csv 21412 B /
D2C8E539E2FA0029 / CRLF 0 不变；exercise_equivalence.yaml 8245 B / 822CB86A5E998301 不变；
没跑过 app.seed.generate / app.pipeline.backfill / app.pipeline.daily。
改动面自证（AST + 解析结果，带对照组）PASS：exercises.py 与等价表**逐字节未改**，
refdata_prescription.py 既有 12 个顶层定义 AST 逐字不变、只新增 30 个、删除 0 个，
exercises.yaml 既有 23 个条目逐字不变、只多 1 个键。

报告与取证：.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-3-report.md
（82 367 B / 982 LF）+ t3_probes/（16 个脚本 + mutation_log.txt + 一份字节备份）。
报告 §9 记了 **4 条控制者错误**（CE-1 派单里 test_models.py 的四个行号是 966eae0 上的、
账本 P3-A11 却记成「核对通过」；CE-2 那份 5 项连带清单不在 fr3 节；CE-3 计划 :741 的
§7.2 勘误没按 P3-A9 减掉；CE-4 派单待改文件表一行混两个口径没标注）与 **6 条自纠**
（含一次编辑工具「报成功而磁盘未写」，已用 python 字节级重写并双向串查复核）。
"""

import tempfile
out = pathlib.Path(tempfile.gettempdir()) / 't3_commit_msg.txt'   # 仓库外，不污染审计链
out.write_bytes(MSG.replace('\r\n', '\n').encode('utf-8'))
b = out.read_bytes()
print('written %d bytes -> %s, LF=%d CRLF=%d' % (len(b), out, b.count(b'\n'), b.count(b'\r\n')))
print(b.decode('utf-8').split('\n')[0])

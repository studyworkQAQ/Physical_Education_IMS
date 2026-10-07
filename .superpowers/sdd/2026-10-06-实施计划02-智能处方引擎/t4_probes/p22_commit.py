import pathlib, subprocess, sys

MSG = """feat: Plan02 Task4 模板匹配器——match.py（MatchStatus 6 档 + 32 格穷举 + 6 段优先级链）+ 公开面 20→24 + 两份架构守卫改扫真仓对拍，581 → 592 passed

新建 3 个、修改 4 个（git diff --numstat：__init__.py +27/−4、test_refdata_prescription.py
+69/−69、test_domain_purity.py +141/−54、test_layering.py +141/−49）：

* app/domain/prescription/match.py（新，18 589 B / 287 行 / 纯 LF，sha256[:16] 裸字节
  40E08F5587C92F46）：MatchStatus（6 档）/ MatchInput / MatchOutcome（都是 frozen dataclass）
  / match_template()。优先级链 NO_LAYER → NO_BUCKET → NO_TEMPLATE → UNREACHABLE →
  NOT_APPROVED → MATCHED，三处承重顺序的理由写进 docstring（P4-A3）；reachable 读**字段**、
  不调 is_reachable（P4-A2，并按 #39 写明「绕过加载器手工构造矛盾模板本函数不会发现」，
  且把这一档钉成期望行为的一条测试）；NO_LAYER 的 reason 与 stratify 的 Z0 文案**同源**
  （P4-A7：生产码持副本、插值公开的 MIN_VALID_COUNT，漂移守卫在测试侧触私有名）。
  import 面 = collections.abc / dataclasses / enum + app.domain.indicators /
  app.domain.stratify（绝对，指向所有者）+ .templates（level == 1，同包兄弟），
  与 templates.py / __init__.py 既有写法一致，没有一半绝对一半相对。
* tests/domain/test_prescription_match.py（新，11 条）：32 格穷举**按链序**字面写死
  （status 与 15 个 template_id 都不从 templates 反推，Global Constraint #4），
  实测 {NO_LAYER:8, NO_BUCKET:6, UNREACHABLE:3, MATCHED:15}、总数 32；
  另加承重格 (green, None, abnormal) 单格钉住 + 反面对照、NOT_APPROVED（含「待审校」
  与 UNREACHABLE 先于 NOT_APPROVED）、NO_TEMPLATE（reason 指出缺哪一格 + 反面对照）、
  字典顺序确定性、MatchStatus 6 个 (name, value) 与声明序、两个值对象的 frozen 与字段序、
  Z0 文案漂移守卫。
* tests/domain/test_prescription_exercises.py（新，1 条）：EquivalenceTable.lookup() 的
  分支测试从 tests/test_refdata_prescription.py **搬来**（Ruling 107-1 → 134-1③），
  断言与期望值一个字未改；那条测试是 lookup 全部分支的唯一守卫，住在 domain 测试目录之外时
  删掉它 pytest 退出码仍 0、只有 BrPart 会红。
* app/domain/prescription/__init__.py：加 from .match import (…) 一句、__all__ 20 → **24**，
  docstring 三处计数与「谁是所有者」段同步（Layer 仍取自 app.domain.stratify、
  Template/ReviewStatus/BodyCompState 仍取自 .templates 而不是 .match）。
* tests/test_refdata_prescription.py：_PRESCRIPTION_PUBLIC_BASELINE 20 → **24**
  （仍是字面清单，照 Ruling 136-1 的 (名字, 所有者模块) 二元组模式）、_OWNED_MODULES
  2 → **3**、assert len(...) == 24 **两处**、57 → 56 条、删掉 2 个因搬动而不再被使用的
  import、6 处交叉引用与时点（含 Ruling 127-5 的「本条之前」）。
* tests/architecture/test_domain_purity.py 与 test_layering.py（**两份**，硬规矩 #51）：
  3 处过期/写错的陈述**改了 5 处**（① 2 份、② 只有 1 份、③ 2 份；
  git grep "这一层子包已经建出" -- backend/tests 只命中 purity 一处）；
  手写 4 格 pkg_cases **换成**扫真仓与 py.relative_to(BACKEND).parent.parts 对拍（C-fr4-1），
  并**新增**扫真仓每个 .py 的 ImportFrom 与 resolve_name 对拍（Ruling 56/66），
  带空转守卫（>= 40 个 .py、>= 16 条相对导入、5 个字面折算串）；
  **12 格矩阵刻意保留**——真仓今天 0 条 level >= 2、0 个越界档、0 个 offender，
  这三类只有手写矩阵能提供，删掉它会让 Ruling 35/46 修掉过的「479 passed、退出码 0」
  假绿复活（Ruling 56 自己把「换成」的前提定在 level == 2 真实出现之后，而 Ruling 104
  已推翻那个前提）；相对导入计数 16 → **18**（不是简报预测的 17：__init__.py 那句
  from .match import (…) 自己就是一条）、扫描面 27 → **28**（domain 9 → 10）。

覆盖：app/domain 499 stmts / 120 branch → **541 stmts / 132 branch**，Miss 0 / BrPart 0 /
**100%** 维持（match.py 41 stmts / 12 branch，6 个判定点每支都有测试走到）。
表数 **16** 不变。变异验收 4 条 + M0/M1 对照全部**串行**跑过（harness 与完整输出入库
t4_probes/p12_mutate.py 与 mutate_log.txt）：① 删 reachable 检查 → 3 failed（穷举那 3 格
全部变 MATCHED、没有一个变 NOT_APPROVED）；② 删 review_status 检查 → 1 failed；
③ 删 Layer.INSUFFICIENT 分支 → 2 failed（8 格不符）；④ UNREACHABLE 判据提到 NO_BUCKET
之前 → 3 failed（分类变 {8,5,4,15}、总数仍 32、只有承重格不符）；M0 592 passed、
M1（sorted(templates) → sorted(templates.keys())，AST 真变、值不变）仍 592 passed。
每个变异都在剥 docstring 的 ast.dump 上确认真改了代码、按字节还原并核 sha256。
改动面自证：基线 ab075d3 下 backend/app 的 44 个 .py 里 **43 SAME + 1 DIFF
（prescription/__init__.py）+ 1 新增（match.py）**，授权面之外 = 无；对照组 4 个真语义变异
全部报 DIFF、3 个阴性对照（含「只改 docstring」）全部报 SAME。

禁区未动：CSV 21 412 B / D2C8E539E2FA0029、exercises.yaml 22 739 B / 3DE598AF38631209、
exercise_equivalence.yaml 8 245 B / 822CB86A5E998301（都是归一化后 sha256[:16]、CRLF 全 0），
pe.db 不存在、data/seed 0 文件、backend/data/ 一个字节没改、.gitattributes 与 app/seed/ 没碰。

报告 .superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-4-report.md（78 226 B /
1 050 行 / 纯 LF / sha256[:16] EAF9A6448C81534B），连同 t4_probes/ 的 21 个取证脚本、
变异 harness 输出与追加前的字节备份一起入库（硬规矩 #68）。报告含 **7 条控制者错误**
（CE-1「触私有名」的先例指错文件、CE-2 相对导入少算一条、CE-3 变异④的分类两个数写反、
CE-4 硬规矩 #76 未彻底且 10 处裸行号全部绑在 a5bdebe 而非简报自称的 8631744、
CE-5 ①②③ 都不改 passed 数、CE-6 三处陈述实际只有 5 份、CE-7「换成扫真仓」会削弱守卫）
与 **8 条自纠**（含 3 次「编辑工具报成功并回显 diff、而磁盘逐字未写」）。
"""

path = pathlib.Path(".git/T4_COMMIT_MSG.txt")
path.write_bytes(MSG.encode("utf-8"))
print("msg bytes", len(MSG.encode("utf-8")))
r = subprocess.run(["git", "commit", "-F", str(path)], capture_output=True, text=True,
                   encoding="utf-8")
print(r.stdout)
print(r.stderr)
sys.exit(r.returncode)

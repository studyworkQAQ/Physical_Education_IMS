"""回填 task-4-report.md 的 §13.1（commit 之后才取得到的证据）。
python 字节级重写 + 双向串查（本轮已实测到 SearchReplace 对这个文件「报成功而未写」3 次）。
"""
import hashlib
import pathlib

p = pathlib.Path(r".superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-4-report.md")
bak = p.parent / "t4_probes" / "task-4-report.md.bak-before-131"
b0 = p.read_bytes()
bak.write_bytes(b0)
print("backup: %s  %d B  sha16 %s" % (bak.name, len(b0), hashlib.sha256(b0).hexdigest()[:16].upper()))
assert b0.count(b"\r\n") == 0
t = b0.decode("utf-8")

OLD = """### 13.1 commit 之后补录

见 §13.2（这一节的数字**只能**在 commit 之后取到，故留到 commit 之后回填；
若本文件在 commit 之后被追加，追加前先按硬规矩 #68 做字节备份）。
"""
NEW = """### 13.1 commit 之后补录（这一节的数字**只能**在 commit 之后取到）

主体 commit = **`fe5e6dd`**（32 个条目，+4 534 / −176 行）。取证脚本
`t4_probes/p23_postcommit.py`，追加本节前先做了字节备份
`t4_probes/task-4-report.md.bak-before-131`（硬规矩 #68）。

```
HEAD           = fe5e6dd
git status --short = 只有 p23_postcommit.py 自己（它是本节写完之后才建的，随第二个 commit 入库）
git log --oneline -3
  fe5e6dd feat: Plan02 Task4 模板匹配器——match.py（MatchStatus 6 档 + 32 格穷举 + 6 段优先级链）+ 公开面 20→24 + 两份架构守卫改扫真仓对拍，581 → 592 passed
  3473dc6 chore: 清掉误入库的三个 Task 4 预检一次性脚本；Task 4 简报已抽取（24221 B / 152 行）
  8631744 docs: Task 4 预检更正计划正文 6 处（P4-A1..A7）+ 账本预检节
```

**commit 之后复跑全量**：`cd backend; python -m pytest -q` → **592 passed in 62.64s** ✓
（与 commit 之前 M0 相位、以及带 coverage 那次的 591 + 1 skipped 同一批用例）。

**`git ls-files --eol`（本轮 8 个文件，逐行）**：

```
i/lf  w/lf    attr/-text  .superpowers/…/task-4-report.md
i/lf  w/crlf  attr/       backend/app/domain/prescription/__init__.py
i/lf  w/lf    attr/       backend/app/domain/prescription/match.py
i/lf  w/crlf  attr/       backend/tests/architecture/test_domain_purity.py
i/lf  w/crlf  attr/       backend/tests/architecture/test_layering.py
i/lf  w/lf    attr/       backend/tests/domain/test_prescription_exercises.py
i/lf  w/lf    attr/       backend/tests/domain/test_prescription_match.py
i/lf  w/crlf  attr/       backend/tests/test_refdata_prescription.py
```

即：**index 侧 8 个全是 `i/lf`**；4 个既有文件的工作树仍是 `w/crlf`（编辑工具保留了原行尾），
3 个新建 `.py` 是 `w/lf`（§1.1 说过的那件事，仓内已有 3 个同类先例），
报告是 `w/lf` 且 `attr/-text`（`.gitattributes` 对 `.superpowers/**` 的规定：双向零转换）。

**blob 字节 vs 工作树字节**（口径：`git show HEAD:<path>` 给的是 blob 字节，
比对前先归一化 CRLF→LF）：

| 文件 | blob | 工作树 | 裸字节 | 归一化后 | blob 的 CRLF 数 |
|---|---|---|---|---|---|
| `match.py` | 18 589 B | 18 589 B | **同** | 同 ✓ | 0 |
| `test_prescription_match.py` | 25 936 B | 25 936 B | **同** | 同 ✓ | 0 |
| `test_prescription_exercises.py` | 4 841 B | 4 841 B | **同** | 同 ✓ | 0 |
| `prescription/__init__.py` | 5 100 B | 5 206 B | 异 | **同 ✓** | 0 |
| `test_refdata_prescription.py` | 79 574 B | 80 866 B | 异 | **同 ✓** | 0 |
| `test_domain_purity.py` | 55 261 B | 56 058 B | 异 | **同 ✓** | 0 |
| `test_layering.py` | 39 855 B | 40 418 B | 异 | **同 ✓** | 0 |
| `task-4-report.md` | 78 226 B | 78 226 B | **同** | 同 ✓ | 0 |

⚠️ 4 个「裸字节异」的差值**恰好等于各自工作树的 CRLF 行数**（106 / 1 292 / 797 / 563），
即派单说的「`backend/**` 的 blob 是 LF、工作树是 CRLF，差值 = CRLF 行数」逐字成立 ✓。

**禁区四项（commit 之后复验）**：

* CSV 21 412 B / `D2C8E539E2FA0029`（归一化后）/ CRLF 0 ✓
* `exercises.yaml` 22 739 B / `3DE598AF38631209` / CRLF 0 ✓
* `exercise_equivalence.yaml` 8 245 B / `822CB86A5E998301` / CRLF 0 ✓
* `backend/pe.db` 不存在 ✓；`backend/data/seed/` 0 文件 ✓
* `git diff --name-only ab075d3 HEAD -- backend/data` → **空** ✓
* `git diff --name-only 3473dc6 HEAD -- backend/data` → **空**（本轮 commit 没碰数据目录）✓
* `git diff --name-only 3473dc6 HEAD -- .gitattributes backend/app/seed` → **空** ✓
* `Base.metadata.tables` = **16 张** ✓
* SDD 目录下 `_xxx.py` / `tmp*` 残留 = **无** ✓（本轮 23 个取证脚本全部在 `t4_probes/` 里）
"""
assert t.count(OLD) == 1, t.count(OLD)
t = t.replace(OLD, NEW)
b1 = t.encode("utf-8")
p.write_bytes(b1)
b2 = p.read_bytes()
t2 = b2.decode("utf-8")
print("after : %d B  sha16 %s  lines %d" % (
    len(b2), hashlib.sha256(b2).hexdigest()[:16].upper(), len(b2.splitlines())))
assert b2 != b0

HAVE = ["### 13.1 commit 之后补录（这一节的数字**只能**在 commit 之后取到）",
        "主体 commit = **`fe5e6dd`**",
        "**592 passed in 62.64s**",
        "差值**恰好等于各自工作树的 CRLF 行数**",
        "`Base.metadata.tables` = **16 张** ✓"]
NOT = ["见 §13.2（这一节的数字**只能**在 commit 之后取到，故留到 commit 之后回填"]
ok = True
for s in HAVE:
    n = t2.count(s); print(("HAVE  " if n >= 1 else "MISS!!"), n, repr(s[:58])); ok &= n >= 1
for s in NOT:
    n = t2.count(s); print(("CLEAN " if n == 0 else "RESID!!"), n, repr(s[:58])); ok &= n == 0
print("control probe:", t2.count("硬规矩"))
ok &= t2.count("硬规矩") >= 1
print("OK" if ok else "FAILED")

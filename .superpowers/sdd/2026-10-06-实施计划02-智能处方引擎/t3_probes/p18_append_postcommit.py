# -*- coding: utf-8 -*-
"""把 commit 之后的实测证据追加进 task-3-report.md 的 §14（新增 §14.1）。

⚠️ 用 python 字节级写：上一轮编辑工具对本报告文件「报成功而磁盘未写」（§9.3 第 6 条）。
追加前先做字节备份（硬规矩 #68 第 2 条），追加后双向串查。
"""
import hashlib
import pathlib
import shutil

D = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers'
                 r'\sdd\2026-10-06-实施计划02-智能处方引擎')
P = D / 'task-3-report.md'
BAK = D / 't3_probes' / 'task-3-report.md.bak-before-postcommit'

before = P.read_bytes()
shutil.copyfile(P, BAK)
print('备份 %s  bytes=%d sha16=%s'
      % (BAK.name, len(BAK.read_bytes()), hashlib.sha256(before).hexdigest()[:16].upper()))

ANCHOR = '''无临时目录残留：变异全部走 tmp_path 或 harness 内复原；t3_probes/ 是**入库的取证脚本**、
  不是临时目录（派单 §3 指定了这个名字）
```
'''

SECTION = '''
### 14.1 commit 之后的实测（这一节的数字**只能**在 commit 之后取到）

**两个 commit**（派单 §3 允许「代码 + 报告两个」；本报告的 §14.1 与 commit 短哈希属于
「commit 之后才存在的事实」，故另开一笔 `docs:`）：

```
$ git log --oneline -2
<本节的落库 commit>  docs: Plan02 Task3 报告补 §14.1 —— commit 之后的实测证据（…）
4af83bc              feat: Plan02 Task3 处方模板——18 套模板 YAML + prescription_template 表（第 16 张）+ 加载器与 sync_templates，531 → 581 passed
```

⚠️ **上面第一行的短哈希刻意留空**：写本节的那一刻它还不存在，印一个就是编造
（硬规矩 #29）。要它请自己跑 `git log --oneline -2`。**主体 commit `4af83bc` 是实测的**。

**主体 commit `4af83bc`**：53 个条目 = 12 个修改 + 18 个模板 YAML + 1 份本报告 +
22 个 `t3_probes/` 取证文件（16 个 `.py` + `mutation_log.txt` + 两份字节备份 +
`defs.py`/`dump.py`/`outline.py` 三个读文件工具）。`git add` 逐个点名，**没有用
`git add -A`/`.`**；提交前实测「未暂存 = 空、未跟踪 = 空」。

**`git ls-files --eol -- backend/data/`（P3-D2 的最终收口，23 行）**：

```
i/lf    w/lf    attr/text eol=lf        backend/data/README_national_standard.md
i/lf    w/lf    attr/text eol=lf        backend/data/exercise_equivalence.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/exercises.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/indicator_ranges.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/national_standard_2014.csv
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/GRN-END-ABN-13.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/GRN-END-NOR-14.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/GRN-SPD-ABN-17.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/GRN-SPD-NOR-18.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/GRN-STR-ABN-15.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/GRN-STR-NOR-16.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/RED-END-ABN-01.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/RED-END-NOR-02.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/RED-SPD-ABN-05.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/RED-SPD-NOR-06.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/RED-STR-ABN-03.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/RED-STR-NOR-04.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/YEL-END-ABN-07.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/YEL-END-NOR-08.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/YEL-SPD-ABN-11.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/YEL-SPD-NOR-12.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/YEL-STR-ABN-09.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/prescription/YEL-STR-NOR-10.yaml
```

**23 行、不合 `i/lf w/lf attr/text eol=lf` 形状的行数 = 0**（`Select-String -NotMatch` 实测空输出）。
⚠️ **commit 之前跑同一条命令只列出 5 行**——18 个模板那时还是 untracked，而 `ls-files`
看不见未跟踪文件。这**不是**规则没生效：`check-attr` 对**路径模式**求值、不要求文件被跟踪
（正是控制者 P3-D2 用的那个性质），所以改完 `.gitattributes` 当场就验到了 `text: set / eol: lf`。
但「`ls-files --eol` 每一行都是 lf」这条收工判据**必须在 commit 之后重跑**才算数，
故本节单列。

**commit 之后复核（确认 `git add`/`commit` 没有按 `core.autocrlf` 重写工作树，硬规矩 #46）**：

```
$ python -m pytest -q                                          → 581 passed in 60.83s
$ python -c "…len(Base.metadata.tables)"                       → 16
$ backend/pe.db 存在?                                          → False
$ backend/data/seed/ 文件数                                    → 0
$ national_standard_2014.csv                                   → 21412 B / CRLF 0 / D2C8E539E2FA0029
$ exercise_equivalence.yaml                                    → 8245 B / CRLF 0 / 822CB86A5E998301
```

18 个模板的指纹在 commit 之后仍然逐格相符（`test_template_yaml_fingerprints_are_pinned`
与 `test_every_template_yaml_is_lf_only_in_the_worktree` 都在那 581 里）。

**无临时目录残留**：变异 harness 的临时文件全部走 pytest 的 `tmp_path`；commit message 的
UTF-8 临时文件写在 `$env:TEMP\\t3_commit_msg.txt`（仓库外），用完已删。
`t3_probes/` 是**入库的取证脚本**、不是临时目录（派单 §3 指定了这个名字，
并已避开 Task 1 的 `fr{N}_probes` 与 Task 2 的 `t2fr3_probes`）。
'''

t = before.decode('utf-8')
assert t.count(ANCHOR) == 1, '锚命中 %d 次' % t.count(ANCHOR)
t = t.replace(ANCHOR, ANCHOR + SECTION)
P.write_bytes(t.encode('utf-8'))

after = P.read_bytes()
u = after.decode('utf-8')
print('改前 bytes=%d sha16=%s' % (len(before), hashlib.sha256(before).hexdigest()[:16].upper()))
print('改后 bytes=%d LF=%d CRLF=%d sha16=%s'
      % (len(after), after.count(b'\n'), after.count(b'\r\n'),
         hashlib.sha256(after).hexdigest()[:16].upper()))
checks = [
    ('§14.1 标题', '### 14.1 commit 之后的实测', 1),
    ('ls-files 23 行', 'i/lf    w/lf    attr/text eol=lf        backend/data/', 23),
    ('主体 commit 短哈希', '4af83bc', 3),
    ('旧锚仍在（§14 主体没被吃掉）', '无临时目录残留：变异全部走 tmp_path', 1),
    ('§15 尾部仍在（没被截断）', '⑨ 一处我没改、但认为该报的过期散文', 1),
    ('§9.3 第 6 条仍在', '6. **编辑工具对本报告文件的两次写入', 1),
    ('§0 头部仍在', '## 0. 环境与基线复现', 1),
]
bad = 0
for name, s, want in checks:
    got = u.count(s)
    ok = got == want
    bad += (not ok)
    print('  %-4s %-34s 命中 %d（期望 %d）' % ('OK' if ok else 'FAIL', name, got, want))
print()
print('双向串查判定: %s' % ('PASS' if bad == 0 else 'FAIL(%d)' % bad))

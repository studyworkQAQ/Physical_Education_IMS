import os
import pathlib
import subprocess

ROOT = pathlib.Path('.')
WS = ROOT / '.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎'

tmp = pathlib.Path(os.environ['TEMP']) / 'pe_cm9.txt'
tmp.write_bytes(
    ("docs: P3-D2 升级为 Critical —— .gitattributes 的 backend/data/*.yaml 不覆盖子目录\n\n"
     "git check-attr 亲验：backend/data/exercises.yaml -> text: set / eol: lf；\n"
     "backend/data/prescription/RED-END-ABN-01.yaml -> text: unspecified / eol: unspecified。\n"
     "gitattributes 的 * 不跨 /，故计划 :250 那句「不需要改 .gitattributes」是假的。\n"
     "照原文做会让 18 个模板 YAML 在 core.autocrlf=true 下检出成 CRLF，\n"
     "重演 Plan 01 国标评分表的指纹事故（硬规矩 #46/#47）。裁定：加 backend/data/**/*.yaml。\n"
     "另记方法论：check-attr 对不存在的路径也能求值，「目录还不存在所以验不了」是错的。\n").encode('utf-8'))
subprocess.run(['git', 'add', '-A', 'Document', '.superpowers'], capture_output=True, text=True)
r = subprocess.run(['git', 'commit', '-q', '-F', str(tmp)], capture_output=True, text=True)
print('commit rc =', r.returncode, r.stderr.strip()[:200])
tmp.unlink()
head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
st = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True).stdout
print('HEAD =', head, '| git status = %r' % st)
assert st.strip() == ''

# 重抽 Task 3 简报（硬规矩 #48：从已提交状态抽）
PLAN = ROOT / 'Document/2026-10-06-实施计划02-智能处方引擎.md'
blob = subprocess.run(['git', 'show', 'HEAD:Document/2026-10-06-实施计划02-智能处方引擎.md'],
                      capture_output=True).stdout
wt = PLAN.read_bytes()
assert blob.replace(b'\r\n', b'\n') == wt.replace(b'\r\n', b'\n'), 'blob 与工作树不一致'
print('blob == worktree (normalized) ✓')

L = wt.decode('utf-8').replace('\r\n', '\n').split('\n')
h_t1 = next(i for i, l in enumerate(L) if l.startswith('## Task 1'))
h_t3 = next(i for i, l in enumerate(L) if l.startswith('## Task 3'))
h_t4 = next(i for i, l in enumerate(L) if l.startswith('## Task 4'))
print('Task1 @%d  Task3 @%d  Task4 @%d  Task3 节 %d 行' % (h_t1 + 1, h_t3 + 1, h_t4 + 1, h_t4 - h_t3))

preamble = [
    '# Task 3 简报 — 18 套模板 YAML + `prescription_template` 表 + 加载器',
    '',
    '> 抽取自 `Document/2026-10-06-实施计划02-智能处方引擎.md` @ commit `%s`'
    '（控制者用 python 从**已提交**状态抽，抽前验过工作树干净、blob 与工作树内容一致 —— 硬规矩 #48）。' % head,
    '> 内容 = 计划头部（**Global Constraints 10 条** / **Review Focus 5 条** / **File Structure**）'
    ' + **Task 3 全节**。',
    '> ⚠️ Task 3 全节里的 `P3-A1 … P3-D4` 标记是**控制者预检的更正与裁定**，完整依据在账本 '
    '`.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md` 的 '
    '`### Task 3: 18 套模板 — 预检扫描（Pre-flight，控制者亲跑）` 一节。'
    '**以更正后的正文为准**；正文里凡写「原文……」的都是已被作废的旧说法。',
    '> ⚠️ 本简报有 **2 处 Critical**：**P3-A1**（不许新建 `app/seed/prescription.py`、'
    '不许改 `seed_database`，改用 `refdata_prescription.sync_templates(session)`）与 '
    '**P3-D2**（**必须改 `.gitattributes`**，加 `backend/data/**/*.yaml text eol=lf`——'
    '现有规则不覆盖子目录，`git check-attr` 已亲验）。',
    '> ⚠️ 硬规矩的**定义**分两处：**#1–#47 在 Plan 01 账本** '
    '`.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md`（约 806 KB）；'
    '**#48–#75 在 Plan 02 账本**（上面那个 progress.md，约 265 KB）。'
    '**Plan 02 账本的裁定编号从 47 跳到 49，`Ruling 48` 号未使用**（已知勘误）。',
    '',
]
body = L[:h_t1] + ['---', ''] + L[h_t3:h_t4]
OUT = WS / 'task-3-brief.md'
OUT.write_bytes(('\n'.join(preamble + body)).encode('utf-8'))
o = OUT.read_bytes()
ot = o.decode('utf-8')
print()
print('WROTE %s  %d B  %d 行  CRLF=%d' % (OUT.name, len(o), ot.count('\n'), o.count(b'\r\n')))

MUST = ['## Global Constraints', '## Review Focus', '## File Structure', '## Task 3: 18 套模板',
        'P3-A1', 'P3-A2', 'P3-A3', 'P3-A4', 'P3-A5', 'P3-A6', 'P3-A7', 'P3-A8', 'P3-A9',
        'P3-A10', 'P3-D2', 'P3-D4', 'sync_templates', 'RED-END-ABN-01',
        'energy_expenditure_plus_5min_hiit', '_PRESCRIPTION_PUBLIC_BASELINE', 'REFERENCE_TABLES',
        'backend/data/**/*.yaml', 'git check-attr', 'Step 1', 'Step 6', 'Step 7',
        'prescription_template', 'week_deltas', 'reachable', 'speed_flexibility',
        'test_all_fifteen_tables_created']
missing = [k for k in MUST if k not in ot]
print('missing markers =', missing or 'NONE')
MUSTNOT = ['`backend/app/seed/prescription.py` 的模板 seed、',
           '每个 `String(n)` 都要过 Plan 01 的列宽遍历测试',
           '本 Task 追加 **6 项，#29–#34**',
           '- **不需要改 `.gitattributes`**']
survived = [k for k in MUSTNOT if k in ot]
print('superseded strings survived =', survived or 'NONE')
gc = ot[ot.index('## Global Constraints'):ot.index('## Review Focus')]
print('Global Constraints bullets =', len([x for x in gc.split('\n') if x.startswith('- ')]))
print('app/seed/prescription.py 出现次数 =', ot.count('app/seed/prescription.py'), '（应为 1，在 P3-A1 的作废说明里）')
print('.gitattributes 出现次数 =', ot.count('.gitattributes'))

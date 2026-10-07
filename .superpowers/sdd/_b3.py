import os
import pathlib
import subprocess

ROOT = pathlib.Path('.')
WS = ROOT / '.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎'

# ---------- (a) commit 计划更正 + 账本 ----------
tmp = pathlib.Path(os.environ['TEMP']) / 'pe_cm8.txt'
tmp.write_bytes(
    ("docs: Task 3 预检更正计划正文 13 处（P3-A1..A11 / B1-B3 / C1-C3 / D1-D4）+ 账本 Ruling 128\n\n"
     "1 处 Critical：Task 3 的 Create 清单里仍有 app/seed/prescription.py 的模板 seed，\n"
     "与 Global Constraint #10（app/seed 冻结）及 test_generate.py:491 的守卫直接冲突——\n"
     "这与 Task 2 的 P2-A1 是同一个缺陷，控制者当时裁了却没传导到 Task 3（补硬规矩 #75）。\n"
     "5 处 Important：test_prescription_templates.py 已存在（Modify 不是 Create）；\n"
     "spec §14 的 #29/#31 编号已由 d40f36c 分配（第二次差点撞车）；\n"
     "黄层 addon 的 energy_expenditure_plus_5min_hiit 不在动作库里；\n"
     "列宽遍历测试只覆盖带 _in_domain CHECK 的列（template_ref/version 不被覆盖）；\n"
     "四处字面钉死的基线断言会被撞红而计划只字未提；\n"
     "Step 7 的变异①在本 Task 无可观测后果（不是变异测试）。\n"
     "另同步 Task 12 Step 3 的 §14 清单（6 项 -> 4 项：#30/#32/#33/#34，总数仍 34）。\n").encode('utf-8'))
subprocess.run(['git', 'add', '-A', 'Document', '.superpowers'], capture_output=True, text=True)
r = subprocess.run(['git', 'commit', '-q', '-F', str(tmp)], capture_output=True, text=True)
print('commit rc =', r.returncode, r.stderr.strip()[:200])
tmp.unlink()
print(subprocess.run(['git', 'log', '--oneline', '-2'], capture_output=True, text=True).stdout)
st = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True).stdout
print('git status --short = %r' % st)

# ---------- (b) 抽 Task 3 简报（硬规矩 #48：从已提交状态抽）----------
head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
assert st.strip() == '', '工作树不干净，不能抽简报'
PLAN = ROOT / 'Document/2026-10-06-实施计划02-智能处方引擎.md'
blob = subprocess.run(['git', 'show', 'HEAD:Document/2026-10-06-实施计划02-智能处方引擎.md'],
                      capture_output=True).stdout
wt = PLAN.read_bytes()
assert blob.replace(b'\r\n', b'\n') == wt.replace(b'\r\n', b'\n'), 'blob 与工作树不一致'
print('HEAD =', head, '| worktree clean | blob == worktree (normalized)')

L = wt.decode('utf-8').replace('\r\n', '\n').split('\n')


def find(pred, start=0):
    for i in range(start, len(L)):
        if pred(L[i]):
            return i
    raise AssertionError('not found')


h_t1 = find(lambda l: l.startswith('## Task 1'))
h_t3 = find(lambda l: l.startswith('## Task 3'))
h_t4 = find(lambda l: l.startswith('## Task 4'))
print('Task1 @%d  Task3 @%d  Task4 @%d (1-based)  Task3 节 %d 行'
      % (h_t1 + 1, h_t3 + 1, h_t4 + 1, h_t4 - h_t3))

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
    '> ⚠️ 硬规矩的**定义**分两处：**#1–#47 在 Plan 01 账本** '
    '`.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md`（约 806 KB）；'
    '**#48–#75 在 Plan 02 账本**（上面那个 progress.md，约 264 KB）。'
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

# 硬规矩 #59/#61：交出去之前亲眼核一遍
MUST = ['## Global Constraints', '## Review Focus', '## File Structure',
        '## Task 3: 18 套模板', 'P3-A1', 'P3-A2', 'P3-A3', 'P3-A4', 'P3-A5', 'P3-A6',
        'P3-A7', 'P3-A8', 'P3-A9', 'P3-A10', 'P3-A11', 'P3-D4',
        'sync_templates', 'RED-END-ABN-01', 'energy_expenditure_plus_5min_hiit',
        '_PRESCRIPTION_PUBLIC_BASELINE', 'REFERENCE_TABLES',
        'Step 1', 'Step 2', 'Step 6', 'Step 7',
        'prescription_template', 'week_deltas', 'reachable', 'speed_flexibility']
missing = [k for k in MUST if k not in ot]
print('missing markers =', missing or 'NONE')
MUSTNOT = ['`backend/app/seed/prescription.py` 的模板 seed、',
           '每个 `String(n)` 都要过 Plan 01 的列宽遍历测试',
           '本 Task 追加 **6 项，#29–#34**']
survived = [k for k in MUSTNOT if k in ot]
print('superseded strings survived =', survived or 'NONE')
gc = ot[ot.index('## Global Constraints'):ot.index('## Review Focus')]
print('Global Constraints bullets =', len([x for x in gc.split('\n') if x.startswith('- ')]))
rf = ot[ot.index('## Review Focus'):ot.index('## File Structure')]
print('Review Focus 条目 =', len([x for x in rf.split('\n') if x.strip()[:2] in
                                  ('1.', '2.', '3.', '4.', '5.')]))
print('简报里提到 app/seed/prescription.py 的次数 =', ot.count('app/seed/prescription.py'),
      '（应为 1，且是在 P3-A1 的作废说明里）')

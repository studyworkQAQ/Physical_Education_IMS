import ast
import pathlib
import re
import sys

B = pathlib.Path('backend')
sys.path.insert(0, str(B))
SPEC = pathlib.Path('Document/2026-09-28-体育闭环原型-设计spec.md').read_text(encoding='utf-8').split('\n')

print('=== H1: Task 3 交付的 templates.py 公开面（计划 :370 的 Consumes 清单够不够）===')
import app.domain.prescription as dp
print('  prescription.__all__ (%d) = %s' % (len(dp.__all__), list(dp.__all__)))
import app.domain.prescription.templates as tp
print('  templates.__all__ (%d) = %s' % (len(tp.__all__), list(tp.__all__)))
print('  有 ReviewStatus 吗 =', hasattr(tp, 'ReviewStatus'),
      '| 有 is_reachable 吗 =', hasattr(tp, 'is_reachable'))
if hasattr(tp, 'ReviewStatus'):
    print('  ReviewStatus 成员 =', [(m.name, m.value) for m in tp.ReviewStatus])
if hasattr(tp, 'is_reachable'):
    print('  is_reachable 源码（从文件 AST 取）：')
    _t = ast.parse((B / 'app/domain/prescription/templates.py').read_text(encoding='utf-8'))
    for _n in _t.body:
        if isinstance(_n, ast.FunctionDef) and _n.name == 'is_reachable':
            for _l in ast.unparse(_n).splitlines():
                print('    ', _l)

print()
print('=== H2: Template 的字段与 reachable 的来源（数据 or 规则？）===')
print('  Template 字段 =', [f.name for f in tp.Template.__dataclass_fields__.values()])
L = (B / 'app/domain/prescription/templates.py').read_text(encoding='utf-8').splitlines()
for i, l in enumerate(L, 1):
    if 'is_reachable' in l or 'reachable' in l and 'def ' not in l:
        print('  %4d| %s' % (i, l.strip()[:140]))

print()
print('=== H3: 计划 :378 说的 derive.py:330 与 dominant_bucket ===')
dv = (B / 'app/domain/derive.py').read_text(encoding='utf-8').splitlines()
for i, l in enumerate(dv, 1):
    if 'dominant_bucket' in l:
        print('  %4d| %s' % (i, l.strip()[:140]))
print('  :330 =', repr(dv[329].strip()[:120]))

print()
print('=== H4: stratify.explain() 的 Z0 文案（计划 :379 说要复用）===')
st = (B / 'app/domain/stratify.py').read_text(encoding='utf-8').splitlines()
for i, l in enumerate(st, 1):
    if re.search(r'def explain|Z0|insufficient', l):
        print('  %4d| %s' % (i, l.strip()[:140]))

print()
print('=== H5: _BUCKET_ORDER 与 Plan 01 Ruling 100 ===')
for f in sorted((B / 'app').rglob('*.py')):
    s = f.read_text(encoding='utf-8')
    if '_BUCKET_ORDER' in s:
        for i, l in enumerate(s.splitlines(), 1):
            if '_BUCKET_ORDER' in l:
                print('  %s:%d| %s' % (f.relative_to(B).as_posix(), i, l.strip()[:130]))

print()
print('=== H6: spec §11.2 的 NOT_APPROVED 原文（计划 :380 的引文）===')
a = next(i for i, l in enumerate(SPEC) if l.startswith('### 11.2'))
for i in range(a, min(a + 22, len(SPEC))):
    if 'approved' in SPEC[i] or '待审校' in SPEC[i] or '模板' in SPEC[i] or SPEC[i].startswith('|'):
        print('  %4d| %s' % (i + 1, SPEC[i][:170]))

print()
print('=== H7: 32 格穷举的分类是否互斥（计划 :385-389 的算术）===')
LAYERS = ['red', 'yellow', 'green', 'insufficient_data']
BUCKETS = ['endurance', 'strength', 'speed_flexibility', None]
BODIES = [False, True]
cats = {}
for la in LAYERS:
    for bu in BUCKETS:
        for bo in BODIES:
            if la == 'insufficient_data':
                c = 'NO_LAYER'
            elif bu is None:
                c = 'NO_BUCKET'
            elif la == 'green' and bo:
                c = 'UNREACHABLE'
            else:
                c = 'MATCHED'
            cats[c] = cats.get(c, 0) + 1
print('  总数 =', sum(cats.values()), '（应 32）')
print('  分类 =', cats)
print('  计划写的 8 / 6 / 3 / 15 =', cats == {'NO_LAYER': 8, 'NO_BUCKET': 6, 'UNREACHABLE': 3, 'MATCHED': 15})
print('  ⚠️ (green, None, abnormal) 落在哪一类 =',
      'NO_BUCKET' if True else '?', '—— 故 NO_BUCKET 必须先于 UNREACHABLE 判')

print()
print('=== H8: 架构守卫的扫描面与两处过期注释 ===')
scan = sum(len(list((B / 'app' / d).rglob('*.py'))) for d in ('pipeline', 'db', 'domain'))
print('  SCANNED_DIRS 合计 =', scan, '（Task 4 加 match.py 后应为', scan + 1, '）')
print('  app/domain 下 .py =', len(list((B / 'app/domain').rglob('*.py'))))
for f in ('tests/architecture/test_domain_purity.py', 'tests/architecture/test_layering.py'):
    s = (B / f).read_text(encoding='utf-8').splitlines()
    for i, l in enumerate(s, 1):
        if '子包' in l or '今天不存在' in l or 'prescription/' in l:
            print('  %s:%d| %s' % (f, i, l.strip()[:130]))

print()
print('=== H9: 全仓相对导入的当前条数（Task 4 若写 level==2 会变）===')
cnt = {}
tot = 0
for p in sorted((B / 'app').rglob('*.py')):
    t = ast.parse(p.read_text(encoding='utf-8'))
    for n in ast.walk(t):
        if isinstance(n, ast.ImportFrom) and n.level:
            tot += 1
            cnt[n.level] = cnt.get(n.level, 0) + 1
print('  合计 =', tot, ' 按 level =', cnt)

print()
print('=== H10: _PRESCRIPTION_PUBLIC_BASELINE 现状（Task 4 加名字要再改）===')
tr = (B / 'tests/test_refdata_prescription.py').read_text(encoding='utf-8').splitlines()
for i, l in enumerate(tr, 1):
    if '_PRESCRIPTION_PUBLIC_BASELINE' in l and ('=' in l or 'len(' in l):
        print('  %4d| %s' % (i, l.strip()[:130]))

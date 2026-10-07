import hashlib, pathlib
ROOT = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims')
BE = ROOT / 'backend'
files = [
    '.gitattributes',
    'Document/2026-09-28-体育闭环原型-设计spec.md',
    'backend/app/db/models/__init__.py',
    'backend/app/db/models/prescription.py',
    'backend/app/domain/prescription/__init__.py',
    'backend/app/domain/prescription/templates.py',
    'backend/app/domain/prescription/exercises.py',
    'backend/app/refdata_prescription.py',
    'backend/data/exercises.yaml',
    'backend/data/exercise_equivalence.yaml',
    'backend/data/national_standard_2014.csv',
    'backend/tests/db/test_models.py',
    'backend/tests/domain/test_prescription_templates.py',
    'backend/tests/seed/test_generate.py',
    'backend/tests/test_refdata_prescription.py',
]
print('%-58s %8s %6s %6s  %s' % ('文件', 'bytes', '行', 'CRLF', 'sha16(归一化)'))
for rel in files:
    b = (ROOT / rel).read_bytes()
    n = b.replace(b'\r\n', b'\n')
    print('%-58s %8d %6d %6d  %s' % (rel, len(b), n.count(b'\n'), b.count(b'\r\n'),
                                     hashlib.sha256(n).hexdigest()[:16].upper()))
print()
tot = 0
for p in sorted((BE / 'data/prescription').glob('*.yaml')):
    b = p.read_bytes()
    tot += len(b)
    assert b.count(b'\r\n') == 0
print('18 个模板 YAML 合计 %d B，全部 CRLF=0' % tot)
print()
# 测试条数
import subprocess, sys
for rel in ('backend/tests/domain/test_prescription_templates.py',
            'backend/tests/test_refdata_prescription.py'):
    out = subprocess.run([sys.executable, '-m', 'pytest', '--collect-only', '-q',
                          rel.split('backend/')[1]], cwd=BE, capture_output=True, text=True)
    last = [l for l in out.stdout.splitlines() if 'test' in l and '::' not in l]
    n = len([l for l in out.stdout.splitlines() if '::' in l])
    print('%s -> 收集到 %d 条' % (rel, n))

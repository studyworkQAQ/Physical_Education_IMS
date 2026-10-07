import hashlib, pathlib, subprocess, sys, ast

ROOT = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims')
BE = ROOT / 'backend'

def sha16(b):
    return hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()[:16].upper()

print('=== 禁区四项 ===')
pe = BE / 'pe.db'
print('  backend/pe.db 存在?', pe.exists())
seed = BE / 'data' / 'seed'
print('  backend/data/seed/ 存在?', seed.exists(),
      '文件数 =', len(list(seed.rglob('*'))) if seed.exists() else 'N/A')
csv = (BE / 'data' / 'national_standard_2014.csv').read_bytes()
print('  CSV bytes=%d CRLF=%d sha16=%s  （期望 21412 / 0 / D2C8E539E2FA0029）'
      % (len(csv), csv.count(b'\r\n'), sha16(csv)))
eq = (BE / 'data' / 'exercise_equivalence.yaml').read_bytes()
print('  exercise_equivalence.yaml bytes=%d CRLF=%d sha16=%s （期望 8245 / 0 / 822CB86A5E998301）'
      % (len(eq), eq.count(b'\r\n'), sha16(eq)))

print()
print('=== git ls-files --eol -- backend/data/ ===')
r = subprocess.run(['git', 'ls-files', '--eol', '--', 'backend/data/'], cwd=ROOT,
                   capture_output=True, text=True)
print(r.stdout)
bad = [l for l in r.stdout.splitlines() if l.strip() and 'i/lf    w/lf    attr/text eol=lf' not in l]
print('  不合 i/lf w/lf attr/text eol=lf 的行数 =', len(bad))
for l in bad:
    print('   !!', l)

print()
print('=== check-attr 逐路径（18 个模板 + 3 个既有 data 文件）===')
paths = ['backend/data/prescription/%s.yaml' % t for t in (
    'RED-END-ABN-01', 'YEL-SPD-NOR-12', 'GRN-SPD-NOR-18')] + [
    'backend/data/exercises.yaml', 'backend/data/exercise_equivalence.yaml',
    'backend/data/national_standard_2014.csv']
for p in paths:
    out = subprocess.run(['git', 'check-attr', 'text', 'eol', '--', p], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip().replace('\n', ' | ')
    print('  ' + out)

print()
print('=== 表数 ===')
sys.path.insert(0, str(BE))
import app.db.models  # noqa
from app.db.session import Base
print('  Base.metadata.tables =', len(Base.metadata.tables))

print()
print('=== app/ 下的 .py 数（SCANNED_DIRS = pipeline + db + domain）===')
for d in ('pipeline', 'db', 'domain'):
    files = sorted((BE / 'app' / d).rglob('*.py'))
    print('  app/%-9s %d 个 .py' % (d, len(files)))

print()
print('=== git grep 计数（散文里的预测逐条核）===')
for pat, target in (
    (r'== 16', 'backend/tests/db/test_models.py'),
    (r'== 15', 'backend/tests/db/test_models.py'),
    (r'test_all_sixteen_tables_created', 'backend'),
    (r'test_all_fifteen_tables_created', 'backend'),
    (r'REFERENCE_TABLES', 'backend/tests/seed/test_generate.py'),
):
    out = subprocess.run(['git', 'grep', '-n', pat, '--', target], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip().splitlines()
    print('  %-34s -- %-40s 命中 %d' % (pat, target, len(out)))
    for l in out:
        print('      ' + l[:120])

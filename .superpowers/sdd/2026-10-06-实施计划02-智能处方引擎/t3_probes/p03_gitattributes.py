import hashlib, pathlib, subprocess
ROOT = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims')
p = ROOT / '.gitattributes'
b = p.read_bytes()
print('bytes=%d CRLF=%d LF=%d sha16=%s' % (len(b), b.count(b'\r\n'), b.count(b'\n'),
                                           hashlib.sha256(b).hexdigest()[:16].upper()))
t = b.decode('utf-8')
new = 'backend/data/**/*.yaml text eol=lf'
old_marker = 'backend/data/*.md    text eol=lf'
print('新串命中 =', t.count(new), '（期望 1）')
print('旧锚仍在 =', t.count(old_marker), '（期望 1）')
print('混合行尾?', b.count(b'\n') - b.count(b'\r\n'), '裸 LF（期望 0）')
print()
print('--- check-attr 改后 ---')
for path in ('backend/data/exercises.yaml',
             'backend/data/prescription/RED-END-ABN-01.yaml',
             'backend/data/prescription/GRN-SPD-NOR-18.yaml',
             'backend/data/national_standard_2014.csv',
             'backend/data/README_national_standard.md',
             '.superpowers/sdd/x/task-3-report.md'):
    r = subprocess.run(['git', 'check-attr', 'text', 'eol', '--', path], cwd=ROOT,
                       capture_output=True, text=True)
    print('  ' + r.stdout.strip().replace('\n', '\n  '))
print()
print('--- git ls-files --eol -- backend/data/ ---')
r = subprocess.run(['git', 'ls-files', '--eol', '--', 'backend/data/'], cwd=ROOT,
                   capture_output=True, text=True)
print(r.stdout)

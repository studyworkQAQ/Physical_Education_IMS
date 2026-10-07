import subprocess, re, hashlib, pathlib

ROOT = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims')
BE = ROOT / 'backend'

def blob_lines(rev, rel):
    out = subprocess.run(['git', 'show', f'{rev}:{rel}'], cwd=ROOT,
                         capture_output=True).stdout
    return out.replace(b'\r\n', b'\n').decode('utf-8').split('\n'), out

print('--- test_models.py 定位（工作树 vs c29bc69 blob vs 966eae0 blob）---')
rel = 'backend/tests/db/test_models.py'
wt = (BE / 'tests/db/test_models.py').read_bytes().replace(b'\r\n', b'\n').decode('utf-8').split('\n')
for rev in ('c29bc69', '966eae0'):
    lines, _ = blob_lines(rev, rel)
    hits = [i for i, l in enumerate(lines, 1) if re.search(r'== 15\b', l)]
    fn = [i for i, l in enumerate(lines, 1) if 'test_all_fifteen_tables_created' in l]
    print(f'  {rev}: "== 15" -> {hits} ; funcname -> {fn} ; total_lines={len(lines)}')
hits = [i for i, l in enumerate(wt, 1) if re.search(r'== 15\b', l)]
fn = [i for i, l in enumerate(wt, 1) if 'test_all_fifteen_tables_created' in l]
print(f'  worktree: "== 15" -> {hits} ; funcname -> {fn} ; total_lines={len(wt)}')
print('  worktree == c29bc69 blob ?', wt == blob_lines('c29bc69', rel)[0])

print()
print('--- .gitattributes ---')
ga = (ROOT / '.gitattributes').read_bytes().replace(b'\r\n', b'\n').decode('utf-8').split('\n')
for i, l in enumerate(ga, 1):
    if l.strip():
        print('%3d|%s' % (i, l))
print('CRLF=%d' % (ROOT / '.gitattributes').read_bytes().count(b'\r\n'))

print()
print('--- check-attr 现状 ---')
for p in ('backend/data/exercises.yaml',
          'backend/data/prescription/RED-END-ABN-01.yaml'):
    r = subprocess.run(['git', 'check-attr', 'text', 'eol', '--', p], cwd=ROOT,
                       capture_output=True, text=True)
    print(r.stdout.strip())

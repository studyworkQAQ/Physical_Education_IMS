import os
import pathlib
import subprocess
import tempfile

# CE-1: test_models.py 的 == N 在代码基线 c29bc69 与 HEAD 上的真实行号
tmp = pathlib.Path(tempfile.mkdtemp())
for rev in ('966eae0', 'c29bc69', 'HEAD'):
    out = subprocess.run(['git', 'show', '%s:backend/tests/db/test_models.py' % rev],
                         capture_output=True).stdout.decode('utf-8')
    p = tmp / ('tm_%s.py' % rev)
    p.write_bytes(out.encode('utf-8'))
    L = out.splitlines()
    hits = [(i, l.strip()[:78]) for i, l in enumerate(L, 1)
            if '== 15' in l or '== 16' in l or 'fifteen' in l or 'sixteen' in l]
    print('--- %s (%d 行)' % (rev, len(L)))
    for i, l in hits:
        print('    %4d| %s' % (i, l))

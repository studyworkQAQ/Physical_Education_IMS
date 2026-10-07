import hashlib, pathlib
p = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-3-report.md')
b = p.read_bytes()
t = b.decode('utf-8')
print('bytes=%d LF=%d CRLF=%d sha16=%s' % (len(b), b.count(b'\n'), b.count(b'\r\n'),
                                          hashlib.sha256(b).hexdigest()[:16].upper()))
for probe in ('5. **我在源码 docstring 里逐字复述',
              '9.3 我自己本轮犯的错（5 条',
              '9.3 我自己本轮犯的错（4 条',
              'p14_landing_gate.py'):
    print('  %-42r 命中 %d' % (probe[:40], t.count(probe)))
bak = p.parent / 't3_probes' / 'task-3-report.md.bak-before-append'
print('backup bytes=%d sha16=%s' % (len(bak.read_bytes()),
                                    hashlib.sha256(bak.read_bytes()).hexdigest()[:16].upper()))
print('与备份相同?', b == bak.read_bytes())

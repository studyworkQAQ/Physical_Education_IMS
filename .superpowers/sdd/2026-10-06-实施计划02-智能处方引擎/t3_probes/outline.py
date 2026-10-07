import re, sys, hashlib

p = r'..\.superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\progress.md'
b = open(p, 'rb').read()
print('bytes=%d CRLF=%d sha16=%s' % (len(b), b.count(b'\r\n'), hashlib.sha256(b).hexdigest()[:16].upper()))
txt = b.replace(b'\r\n', b'\n').decode('utf-8')
lines = txt.split('\n')
print('lines(split)=%d' % len(lines))
pat = re.compile(sys.argv[1] if len(sys.argv) > 1 else r'^#{2,4} ')
for i, ln in enumerate(lines, 1):
    if pat.search(ln):
        print('%5d|%s' % (i, ln[:150]))

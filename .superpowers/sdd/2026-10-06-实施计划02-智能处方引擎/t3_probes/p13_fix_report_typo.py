import pathlib, hashlib
p = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd\2026-10-06-实施计划02-智能处方引擎\task-3-report.md')
before = p.read_bytes()
t = before.decode('utf-8')
bad = 'datetime' + '`' * 2
print('命中数(改前) =', t.count(bad))
for i, l in enumerate(t.split('\n'), 1):
    if bad in l:
        print('%4d|%s' % (i, l))
t2 = t.replace(bad, 'datetime' + '`')
p.write_bytes(t2.encode('utf-8'))
after = p.read_bytes()
print()
print('改前 bytes=%d sha16=%s' % (len(before), hashlib.sha256(before).hexdigest()[:16].upper()))
print('改后 bytes=%d sha16=%s' % (len(after), hashlib.sha256(after).hexdigest()[:16].upper()))
a = after.decode('utf-8')
print('双向串查: 新串(`datetime` + 右括号) 命中 =', a.count('datetime`）'), '；旧串残留 =', a.count(bad))
print('LF=%d CRLF=%d' % (after.count(b'\n'), after.count(b'\r\n')))

import pathlib, re, sys
p = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd\2026-09-28-实施计划01-数据基座与分层引擎\progress.md')
L = p.read_text(encoding='utf-8').splitlines()
want = {int(x) for x in sys.argv[1:]}
for i, line in enumerate(L):
    m = re.match(r'^(\d+)\.\s+\*\*(.{0,120})', line)
    if m and int(m.group(1)) in want:
        print('%5d| %s' % (i + 1, line[:400]))

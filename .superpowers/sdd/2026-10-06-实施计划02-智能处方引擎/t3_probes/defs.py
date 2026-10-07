import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
b = p.read_bytes()
lines = b.replace(b'\r\n', b'\n').decode('utf-8').split('\n')
for i, ln in enumerate(lines, 1):
    if re.match(r'^(def |class |@pytest|# ---)', ln):
        print('%4d|%s' % (i, ln[:110]))

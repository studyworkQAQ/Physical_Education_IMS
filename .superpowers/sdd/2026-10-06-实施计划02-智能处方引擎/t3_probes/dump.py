import sys, hashlib
p = sys.argv[1]
start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
end = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9
b = open(p, 'rb').read()
lines = b.replace(b'\r\n', b'\n').split(b'\n')
sys.stdout.write("=== %s  bytes=%d  lines=%d  sha16=%s  CRLF=%d\n" % (
    p, len(b), len(lines), hashlib.sha256(b).hexdigest()[:16].upper(), b.count(b'\r\n')))
for i, ln in enumerate(lines, 1):
    if start <= i <= end:
        sys.stdout.write("%4d|%s\n" % (i, ln.decode('utf-8')))

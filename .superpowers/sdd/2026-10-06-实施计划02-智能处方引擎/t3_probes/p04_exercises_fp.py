import hashlib, pathlib
p = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims\backend\data\exercises.yaml')
b = p.read_bytes()
print('bytes=%d CRLF=%d LF=%d sha16(normalized)=%s' % (
    len(b), b.count(b'\r\n'), b.count(b'\n'),
    hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()[:16].upper()))
import yaml
lib = yaml.safe_load(b.decode('utf-8'))
print('keys=%d' % len(lib))
print('has 5min_hiit:', 'energy_expenditure_plus_5min_hiit' in lib)
print('longest ref:', max(lib, key=len), len(max(lib, key=len)))
from collections import Counter
print('impact:', Counter(v['impact_level'] for v in lib.values()))
eq = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims\backend\data\exercise_equivalence.yaml').read_bytes()
print('equivalence bytes=%d CRLF=%d sha16=%s' % (
    len(eq), eq.count(b'\r\n'),
    hashlib.sha256(eq.replace(b'\r\n', b'\n')).hexdigest()[:16].upper()))

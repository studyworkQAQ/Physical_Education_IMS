import ast, pathlib, sys, subprocess
BE = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims\backend')

print('--- app/domain 下的全部 import（AST）---')
for p in sorted((BE / 'app/domain').rglob('*.py')):
    t = ast.parse(p.read_text(encoding='utf-8'))
    mods = sorted({a.name for n in ast.walk(t) if isinstance(n, ast.Import) for a in n.names}
                  | {n.module for n in ast.walk(t) if isinstance(n, ast.ImportFrom) and n.module})
    print('  %-18s %s' % (p.name, mods))

print()
print('--- _is_allowed 源码 ---')
src = (BE / 'tests/architecture/test_domain_purity.py').read_bytes().replace(b'\r\n', b'\n').decode('utf-8').split('\n')
for i in range(198, 208):
    print('%4d|%s' % (i + 1, src[i]))

print()
print('--- tests/architecture 目录 ---')
for p in sorted((BE / 'tests/architecture').rglob('*')):
    print('  ', p.relative_to(BE))

print()
print('--- 相对导入全仓计数 ---')
out = subprocess.run([sys.executable, '-c',
    "import ast,pathlib;[print(p,n.lineno,n.level,n.module) for p in sorted(pathlib.Path('app').rglob('*.py')) for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n,ast.ImportFrom) and n.level]"],
    cwd=BE, capture_output=True, text=True)
print(out.stdout)
print('count =', len([l for l in out.stdout.splitlines() if l.strip()]))

print('--- data/exercise_equivalence.yaml version 行 ---')
eq = (BE / 'data/exercise_equivalence.yaml').read_bytes().replace(b'\r\n', b'\n').decode('utf-8').split('\n')
for i, l in enumerate(eq, 1):
    if 'version' in l or 'volume_reduction' in l:
        print('%4d|%s' % (i, l))

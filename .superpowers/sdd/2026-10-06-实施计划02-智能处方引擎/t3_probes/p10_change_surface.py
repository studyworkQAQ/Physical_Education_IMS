# -*- coding: utf-8 -*-
"""改动面自证（硬规矩 #32）：AST / 解析结果层面的等价性 + 一组**对照**。

判据分三类：
1. **应当 AST 逐字不变**的生产码（我只加了新东西、没改既有语义）；
2. **应当只有注释/docstring 变**的文件（AST 相等即证明）；
3. **数据文件**：``exercises.yaml`` 的既有 23 个条目应当逐字不变、只多 1 个键；
   ``exercise_equivalence.yaml`` 应当**字节**不变。

对照组（硬规矩 #32/#53）：把基线的一个真语义注入进去，本闸门必须抓到——
否则「AST 相等」可能只是我的比对写得太松。
"""
import ast
import hashlib
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims')
BE = ROOT / 'backend'
BASE = 'c29bc69'


def blob(rel):
    return subprocess.run(['git', 'show', f'{BASE}:{rel}'], cwd=ROOT,
                          capture_output=True).stdout


def norm(b):
    return b.replace(b'\r\n', b'\n')


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16].upper()


def work(rel):
    return (ROOT / rel).read_bytes()


def top_level_defs(tree):
    """把 AST 拆成「顶层定义名 → 该节点 dump」的字典（剥掉模块 docstring）。"""
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = ast.dump(node)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = ast.dump(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out[node.target.id] = ast.dump(node)
    return out


def compare_defs(rel, expect_unchanged, expect_new=(), expect_changed=()):
    old = top_level_defs(ast.parse(norm(blob(rel)).decode('utf-8')))
    new = top_level_defs(ast.parse(norm(work(rel)).decode('utf-8')))
    print('--- %s' % rel)
    print('    基线顶层定义 %d 个，现 %d 个' % (len(old), len(new)))
    bad = []
    for name in expect_unchanged:
        if name not in old:
            bad.append('%s 不在基线里（期望侧写错了）' % name)
        elif name not in new:
            bad.append('%s 被删掉了' % name)
        elif old[name] != new[name]:
            bad.append('%s 的 AST 变了' % name)
    for name in expect_changed:
        if old.get(name) == new.get(name):
            bad.append('%s 期望变而 AST 未变（比对可能太松）' % name)
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    print('    新增: %s' % (added,))
    print('    删除: %s' % (removed,))
    if sorted(added) != sorted(expect_new):
        bad.append('新增的顶层定义 %s != 期望 %s' % (added, list(expect_new)))
    if removed:
        bad.append('有顶层定义被删: %s' % removed)
    for b in bad:
        print('    !! %s' % b)
    print('    判定: %s' % ('PASS' if not bad else 'FAIL'))
    return not bad


ok = True

# 1) refdata_prescription.py：既有的 8 个顶层定义 AST 必须逐字不变，只新增模板那一批
ok &= compare_defs(
    'backend/app/refdata_prescription.py',
    expect_unchanged=['_exercise_spec', 'load_exercises', 'exercises',
                      '_equivalence_mapping', 'load_equivalence', 'equivalence',
                      'sync_exercises', '_EXERCISE_KEYS', '_MAPPING_KEYS', '_REF_SHAPE',
                      'EXERCISES_FILENAME', 'EQUIVALENCE_FILENAME'],
    expect_new=['PRESCRIPTION_DIRNAME', '_TEMPLATE_KEYS', '_REVIEW_KEYS',
                '_PROGRESSION_KEYS', '_SESSION_KEYS', '_BLOCK_KEYS', '_INTENSITY_KEYS',
                '_ADDON_KEYS', '_ID_SHAPE', '_DATE_SHAPE', '_GUIDANCE_FREQUENCY',
                '_INTENSITY_FIELDS', '_templates_cache', '_line_index', '_fail',
                '_exact_keys', '_as_int', '_as_float', '_as_optional_text', '_intensity',
                '_block', '_structure', '_session', '_addon', '_review', '_week_deltas',
                '_template', 'load_templates', 'templates', 'sync_templates'],
)

# 2) exercises.py：本 Task **一个字都不该改**
b_old, b_new = norm(blob('backend/app/domain/prescription/exercises.py')), \
    norm(work('backend/app/domain/prescription/exercises.py'))
print('--- backend/app/domain/prescription/exercises.py')
print('    归一化字节相同? %s  (基线 %s / 现 %s)'
      % (b_old == b_new, sha(b_old), sha(b_new)))
ok &= (b_old == b_new)

# 3) 只改注释/docstring 的文件：AST 必须相等
for rel in ('backend/app/db/models/__init__.py',):
    a = ast.dump(ast.parse(norm(blob(rel)).decode('utf-8')))
    # 剥 docstring 后比：模块 docstring 我改了
    def strip_doc(t):
        t = ast.parse(t)
        if t.body and isinstance(t.body[0], ast.Expr) and isinstance(t.body[0].value, ast.Constant):
            t.body = t.body[1:]
        return ast.dump(t)
    same = strip_doc(norm(blob(rel)).decode('utf-8')) == strip_doc(norm(work(rel)).decode('utf-8'))
    print('--- %s  剥模块 docstring 后 AST 相同? %s' % (rel, same))
    ok &= same

# 4) models/prescription.py：Exercise 类 AST 必须逐字不变，只新增 PrescriptionTemplate
ok &= compare_defs(
    'backend/app/db/models/prescription.py',
    expect_unchanged=['Exercise'],
    expect_new=['PrescriptionTemplate'],
)

# 5) exercises.yaml：既有 23 个条目逐字不变，只多 1 个键
old_lib = yaml.safe_load(norm(blob('backend/data/exercises.yaml')).decode('utf-8'))
new_lib = yaml.safe_load(norm(work('backend/data/exercises.yaml')).decode('utf-8'))
print('--- backend/data/exercises.yaml')
print('    基线 %d 个键 → 现 %d 个键' % (len(old_lib), len(new_lib)))
added = sorted(set(new_lib) - set(old_lib))
removed = sorted(set(old_lib) - set(new_lib))
drift = [k for k in old_lib if k in new_lib and old_lib[k] != new_lib[k]]
print('    新增键: %s' % added)
print('    删除键: %s' % removed)
print('    既有键里值漂了的: %s' % drift)
ok &= (added == ['energy_expenditure_plus_5min_hiit'] and not removed and not drift)

# 6) exercise_equivalence.yaml：字节必须完全不变
for rel in ('backend/data/exercise_equivalence.yaml',
            'backend/data/national_standard_2014.csv'):
    same = norm(blob(rel)) == norm(work(rel))
    print('--- %s  归一化字节相同? %s (sha16=%s)' % (rel, same, sha(norm(work(rel)))))
    ok &= same

# 7) 对照组：往基线的 load_exercises 注入一个真语义变异，闸门必须抓到
print('--- 对照组（硬规矩 #53：闸门自己有牙吗）')
src = norm(work('backend/app/refdata_prescription.py')).decode('utf-8')
mutated = src.replace('    library = {ref: _exercise_spec(yaml_path, ref, entry) for ref, entry in raw.items()}',
                      '    library = {ref: _exercise_spec(yaml_path, ref, entry) for ref, entry in list(raw.items())[:3]}')
assert mutated != src, '对照组的锚没命中，这次对照无效'
a = top_level_defs(ast.parse(src))['load_exercises']
b = top_level_defs(ast.parse(mutated))['load_exercises']
print('    注入「只取前 3 个动作」后 AST 相等? %s（必须是 False）' % (a == b))
ok &= (a != b)

print()
print('总判定: %s' % ('PASS' if ok else 'FAIL'))
sys.exit(0 if ok else 1)

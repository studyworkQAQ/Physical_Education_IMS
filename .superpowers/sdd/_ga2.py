import hashlib
import pathlib
import subprocess

GA = pathlib.Path('.gitattributes')
raw = GA.read_bytes()
txt = raw.decode('utf-8').replace('\r\n', '\n')

OLD = """.superpowers/**  text eol=lf
"""
NEW = """.superpowers/**  -text
"""
assert txt.count(OLD) == 1, txt.count(OLD)
txt = txt.replace(OLD, NEW, 1)

# 同时把上面那段理由改对：eol=lf 只保证「以后」，对已经是 CRLF 的工作树会造成
# index(LF) 与 工作树(CRLF) 长期不一致，一次 checkout 就重写 164 个文件。
OLD2 = """# 为什么也要钉行尾：这些文件里**大量引用自己的字节数与 sha256**（例如报告顶部的
# 「245 229 B / sha256[:16]=292F6251FD45AE8E」、账本里的「117 694 B / 972 LF」）。
# core.autocrlf=true 下，一次 checkout / merge 就会把 LF 重写成 CRLF，
# 于是文件里印着的每一个字节数当场变假——而这类假数字正是本仓花了 114 次控制者错误
# 才学会去核的东西。钉成 eol=lf 后工作树字节与 blob 逐字节相同、与平台配置无关，
# 与 backend/data/ 的处置同一条理由（见上面那一段）。"""
NEW2 = """# 为什么要钉行尾：这些文件里**大量引用自己的字节数与 sha256**（例如报告顶部的
# 「245 229 B / sha256[:16]=292F6251FD45AE8E」、账本里的「117 694 B / 972 LF」）。
# core.autocrlf=true 下，一次 checkout / merge 就会重写成 CRLF，
# 于是文件里印着的每一个字节数当场变假——而这类假数字正是本仓花了 114 次控制者错误
# 才学会去核的东西。
#
# ⚠️ 用 `-text`（双向零转换）而**不是** `text eol=lf`：控制者先试了 `text eol=lf`，
# `git ls-files --eol` 立刻报出 `i/lf  w/crlf  attr/text eol=lf` —— 这些文件的工作树
# 本来就是**混合**的（task-1-report.md 纯 LF、task-2-report.md 与 progress.md 纯 CRLF），
# 而 `eol=lf` 只规定「以后检出成 LF」，于是 index 与工作树长期不一致，
# **下一次 checkout 会把 164 个文件全部重写一遍**，届时它们内部引用的每一个字节数都会变假。
# `-text` 让 git 完全不转换：blob 与工作树逐字节相同、且与 core.autocrlf 无关，
# 每个文件保持它现在的行尾（各文件内部是一致的，只是彼此不同）。
# 这与 backend/data/ 用 `text eol=lf` 不矛盾：那几个文件本来就是 LF，钉 eol=lf 是零成本的保证。"""
assert txt.count(OLD2) == 1, txt.count(OLD2)
txt = txt.replace(OLD2, NEW2, 1)
GA.write_bytes(txt.replace('\n', '\r\n').encode('utf-8'))
a = GA.read_bytes()
print('.gitattributes: %d -> %d B  纯CRLF=%s' % (len(raw), len(a), a.count(b'\r\n') == a.count(b'\n')))
print('  -text 规则在 =', '.superpowers/**  -text' in a.decode('utf-8'))

# 让 index 按新属性重新存一遍（-text 下存的是工作树的原始字节）
r = subprocess.run(['git', 'add', '-A', '.gitattributes', '.superpowers'],
                   capture_output=True, text=True)
print('add ->', r.returncode, (r.stderr or r.stdout).strip()[:160])

print()
print('=== ls-files --eol 抽查（attr 应为 -text，i/ 与 w/ 应一致）===')
for f in ('.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md',
          '.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md',
          '.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-2-report.md'):
    o = subprocess.run(['git', 'ls-files', '--eol', '--', f], capture_output=True, text=True).stdout
    print('  ', o.strip()[:104])

print()
print('=== check-attr ===')
o = subprocess.run(['git', 'check-attr', 'text', 'eol', '--',
                    '.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md'],
                   capture_output=True, text=True).stdout
print('  ', o.strip().replace('\n', ' | ')[:200])

st = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True).stdout
print()
print('staged 行数 =', len([l for l in st.splitlines() if l.strip()]))

tmp = pathlib.Path('.superpowers/sdd/_msg.txt')
tmp.write_bytes(
    ("chore: .gitattributes 把 .superpowers/** 改成 -text（双向零转换），而不是 text eol=lf\n\n"
     "text eol=lf 只规定「以后检出成 LF」，而这些文件的工作树本来就是混合的\n"
     "（task-1-report.md 纯 LF、task-2-report.md 与 progress.md 纯 CRLF），\n"
     "于是 git ls-files --eol 报 i/lf w/crlf —— index 与工作树长期不一致，\n"
     "下一次 checkout 会把 164 个文件全部重写，届时它们内部引用的每一个字节数与\n"
     "sha256 都会变假（硬规矩 #70 要防的正是这件事）。\n"
     "-text 让 blob 与工作树逐字节相同、与 core.autocrlf 无关，各文件保持现有行尾。\n").encode('utf-8'))
c = subprocess.run(['git', 'commit', '-q', '-F', str(tmp)], capture_output=True, text=True)
print('commit ->', c.returncode, c.stderr.strip()[:200])
tmp.unlink()
print(subprocess.run(['git', 'log', '--oneline', '-3'], capture_output=True, text=True).stdout)
print('git status --short = %r' % subprocess.run(['git', 'status', '--short'],
                                                 capture_output=True, text=True).stdout)

# 终验：blob 字节 == 工作树字节（-text 的核心保证）
print()
print('=== 终验：git show HEAD:<path> 的字节是否与工作树逐字相同 ===')
for f in ('.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md',
          '.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-2-report.md',
          '.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-1-report.md'):
    blob = subprocess.run(['git', 'show', 'HEAD:' + f], capture_output=True).stdout
    wt = pathlib.Path(f).read_bytes()
    print('  %-70s blob %7d  wt %7d  相同=%s  sha16=%s'
          % (f.split('/')[-1], len(blob), len(wt), blob == wt,
             hashlib.sha256(wt).hexdigest()[:16].upper()))

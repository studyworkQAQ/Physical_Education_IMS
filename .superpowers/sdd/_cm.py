import os
import pathlib
import subprocess

MSG = """chore: 把 SDD 审计链纳入版本控制（Ruling 116 数据丢失事故 + 用户裁定）

2026-10-07 16:44 IDE 把陈旧且截断的文件缓存写回磁盘，task-1-report.md 从
295 KB / 3906 行掉到 78 KB / 1031 行、task-2-report.md 从 118 KB 掉到 63 KB。
因为 .superpowers/ 整个被忽略，**无法用版本控制恢复**，永久丢失约 107 KB
（task-1 的 fix round 5 节 + task-2 的 fix round 1 节）。技术结论无损——两节的
全部裁定与关键取证已转录进 Plan 02 账本 Ruling 79-88 与 Ruling 101-109。

改动：
- 根 .gitignore：删掉裸规则 `.superpowers/`，改成只忽略 `.superpowers/_snapshots/`
  （全树冗余备份；git 已经承担这个角色，再入库等于同一份内容存两遍）。
  `__pycache__/` 由既有的全局规则覆盖。
- `.superpowers/sdd/.gitignore`：原本是一行 `*`（第二层全量忽略，导致
  `git add --dry-run` 报 0 个文件）。**删不掉**——IDE 持有句柄，
  `Path.unlink()` 抛 WinError 32；故改成纯注释（等效于不忽略任何东西）。
  这本身是「IDE 正在占用 .superpowers/ 下文件」的又一个证据。

入库 164 个文件 / 约 4.9 MB：Plan 01 与 Plan 02 两份账本、全部任务简报、
实现者报告、评审包、以及各轮 fix 的取证探针脚本（fr2/fr3/fr4/fr5/review_probes）。
已核：0 个 _snapshots、0 个 .pyc/__pycache__。

同时提交 task-1-report.md 的还原结果（从 $env:TEMP 的 pre-fr5 字节备份恢复，
78 KB / 10 节 -> 245 KB / 15 节，recover 了 ## 9 与 ## fix round 1-4）与
两份报告顶部的事故说明。
"""

tmp = pathlib.Path(os.environ['TEMP']) / 'pe_commit_msg.txt'
tmp.write_bytes(MSG.encode('utf-8'))

r = subprocess.run(['git', 'add', '-A', '.gitignore', '.superpowers'],
                   capture_output=True, text=True)
print('add:', r.returncode, r.stdout.strip()[:200], r.stderr.strip()[:300])

st = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True).stdout
lines = [l for l in st.splitlines() if l.strip()]
print('staged 行数 =', len(lines))
print('  非 .superpowers/.gitignore 的 =',
      [l for l in lines if '.superpowers' not in l and '.gitignore' not in l] or 'NONE')

c = subprocess.run(['git', 'commit', '-q', '-F', str(tmp)], capture_output=True, text=True)
print('commit:', c.returncode, c.stderr.strip()[:300])
print(subprocess.run(['git', 'log', '--oneline', '-2'], capture_output=True, text=True).stdout)
print('git status --short = %r' % subprocess.run(['git', 'status', '--short'],
                                                  capture_output=True, text=True).stdout)
sh = subprocess.run(['git', 'show', '--stat', '--oneline', 'HEAD'], capture_output=True, text=True).stdout
print('show --stat 末行:', sh.strip().splitlines()[-1][:160])

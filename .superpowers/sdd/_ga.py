import os
import pathlib
import subprocess

ROOT = pathlib.Path('.')

# ---------- (a) .gitattributes：把 .superpowers/** 钉成 eol=lf ----------
GA = ROOT / '.gitattributes'
raw = GA.read_bytes()
crlf0, lf0 = raw.count(b'\r\n'), raw.count(b'\n')
txt = raw.decode('utf-8').replace('\r\n', '\n')
ADD = """
# .superpowers/ 是 SDD 审计链（账本 / 简报 / 实现者报告 / 评审包 / 取证探针），
# 自 2026-10-07 起入库（Ruling 116 的数据丢失事故 + 用户裁定）。
#
# 为什么也要钉行尾：这些文件里**大量引用自己的字节数与 sha256**（例如报告顶部的
# 「245 229 B / sha256[:16]=292F6251FD45AE8E」、账本里的「117 694 B / 972 LF」）。
# core.autocrlf=true 下，一次 checkout / merge 就会把 LF 重写成 CRLF，
# 于是文件里印着的每一个字节数当场变假——而这类假数字正是本仓花了 114 次控制者错误
# 才学会去核的东西。钉成 eol=lf 后工作树字节与 blob 逐字节相同、与平台配置无关，
# 与 backend/data/ 的处置同一条理由（见上面那一段）。
.superpowers/**  text eol=lf
"""
assert '.superpowers/**' not in txt
txt = txt.rstrip('\n') + '\n' + ADD
GA.write_bytes(txt.replace('\n', '\r\n').encode('utf-8'))
a = GA.read_bytes()
print('.gitattributes: %d -> %d B  CRLF %d -> %d  纯CRLF=%s'
      % (len(raw), len(a), crlf0, a.count(b'\r\n'), a.count(b'\r\n') == a.count(b'\n')))
print('  .superpowers/** 规则在 =', '.superpowers/**  text eol=lf' in a.decode('utf-8'))

# 复核：规则真的生效了吗（硬规矩 #59：写完断言性产物必须亲眼看输出）
r = subprocess.run(['git', 'check-attr', 'text', 'eol', '--',
                    '.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md'],
                   capture_output=True, text=True)
print('  check-attr progress.md ->', r.stdout.strip().replace('\n', ' | '))
r2 = subprocess.run(['git', 'ls-files', '--eol', '--', '.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/progress.md'],
                    capture_output=True, text=True)
print('  ls-files --eol       ->', r2.stdout.strip()[:120])

# ---------- (b) 账本：用户裁定 + 硬规矩 #68 修订 + #70 ----------
WS = ROOT / '.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎'
L = WS / 'progress.md'
src = L.read_text(encoding='utf-8')
MARK = ('Task 2: fix round 2/5 完成并亲验（**531 passed**、domain 441/120/100%、4 个测试文件、'
        '生产码 0 字节改动），**尚未做 Task 2 收尾评审**。⚠️ 同期发生数据丢失事故（Ruling 116），'
        '已抢救回 165 KB、永久丢失约 107 KB（技术结论无损）。基线 `966eae0`。')
assert src.count(MARK) == 1, src.count(MARK)

NEW = """
#### Ruling 118（用户裁定）— SDD 审计链纳入版本控制；Task 3–12 照当前强度自动推进

控制者用 `AskUserQuestion` 提了两个问题，用户的裁定：
1. **`.superpowers/`（账本 / 报告 / 评审包）→ 「纳入 git 版本控制」**（三选一里的推荐项）。另两个选项是「只提交账本、报告仍忽略」与「保持忽略、只强化备份纪律」。
2. **Task 3–12 的推进节奏 → 「照当前强度自动推进」**。即每个 Task 走完整循环（预检扫描 → 派实现者 → 控制者亲验含独立变异 → fix round 到收敛 → 收尾评审），**不降低文档精度要求**、每个 Task 结案后不必等用户确认。

**落地（控制者已做，commit `8e6a38f` + `.gitattributes` 那一笔）**：

- **根 `.gitignore`**：删掉裸规则 `.superpowers/`，改成只忽略 `.superpowers/_snapshots/`（全树冗余备份——git 已经承担这个角色，再入库等于同一份内容存两遍）。`__pycache__/` 由既有的全局规则覆盖。**原注释「本流程的临时产物（台账、任务简报、评审包），永不入库」已随之作废**——它现在是**永久产物**。
- **⚠️ 发现了第二层忽略规则**：`.superpowers/sdd/.gitignore` 的内容是**一行 `*`**（2 字节），即「忽略本目录下的一切」。**它导致 `git add -A --dry-run .superpowers` 报 0 个文件**——控制者先改了根 `.gitignore`、以为完事，是这条 dry-run 的 0 才把第二层暴露出来（`git check-ignore -v` 指认 `.superpowers/sdd/.gitignore:1:*`）。**这是硬规矩 #59 的正面回报：写完断言性的改动必须亲眼看它的实际输出，而不是推演。**
- **该文件删不掉**：`Path.unlink()` 抛 **`PermissionError: [WinError 32] 另一个程序正在使用此文件`**。改成纯注释（等效于不忽略任何东西）才成功。**→ 这是「IDE 正持有 `.superpowers/` 下文件句柄」的直接证据，与 Ruling 116 的根因推断（IDE 把它那份陈旧且截断的缓存写回磁盘）互相印证。**
- **入库 164 个文件 / 约 4.9 MB**：Plan 01 与 Plan 02 两份账本、全部任务简报、实现者报告、评审包、以及各轮取证探针（`fr2_probes` 11 / `fr3_probes` 11 / `fr4_probes` 21 / `fr5_probes` 39 / `review_probes` 28）。**亲核：0 个 `_snapshots`、0 个 `.pyc`/`__pycache__`。** commit `8e6a38f`，`166 files changed, 61768 insertions(+), 2 deletions(-)`。
- **同时入库了抢救结果**：`task-1-report.md` 78 KB / 10 节 → **245 KB / 15 节**，以及两份报告顶部的事故说明与被截断版本的取证物 `task-1-report.TRUNCATED-20261007-174217.md`。

**→ 补硬规矩 #70：`.gitattributes` 把 `.superpowers/**` 钉成 `text eol=lf`。** 依据：这些文件里**大量引用自己的字节数与 sha256**（报告顶部的「245 229 B / `292F6251FD45AE8E`」、账本里的「117 694 B / 972 LF」），而 `core.autocrlf=true` 下一次 `checkout` / `merge` 就会把 LF 重写成 CRLF，**于是文件里印着的每一个字节数当场变假**——而这类假数字正是本仓花了 114 次控制者错误才学会去核的东西。与 `backend/data/` 的处置同一条理由（Plan 01 的 autocrlf 事故、硬规矩 #46/#47）。**亲验生效**：`git check-attr text eol` 返回 `text: set / eol: lf`。

**→ 硬规矩 #68 修订**：原文要求「每次追加前先做字节备份到 `$env:TEMP` 或 `.superpowers/_snapshots/`」。**现在 git 是主要保护**，故修订为：
1. **每轮（预检 / 实现 / fix round / 评审）结束时，`.superpowers/` 的改动必须与代码改动一起 commit**（可以分开两个 commit，但都要在当轮结束前落库）。这是主要防线。
2. **轮内**（一次追加之前）仍要做字节备份——因为一轮之内可能有多次追加，而 git 只能恢复到上一个 commit。备份路径与 sha256[:16] 记进报告。
3. `.superpowers/_snapshots/` 仍然忽略（git 已替代它）。

**Task 1 的 fr5 实现者做了 (2)、Task 2 的 fr1 实现者没做**——那正是 165 KB 被救回、107 KB 永久丢失的分界。**从本轮起 (1) 也生效，故同类事故不再可能整节丢失。**

Task 2: fix round 2/5 完成并亲验（**531 passed**、domain 441/120/100%、生产码 0 字节改动）；审计链已入库（`8e6a38f` + `.gitattributes`）。**下一步：Task 2 收尾评审**（`fb5bddb..HEAD` 的代码链），然后 Task 3。基线 `966eae0`（代码）/ `8e6a38f`（含审计链）。
"""

L.write_text(src.replace(MARK, MARK + "\n" + NEW), encoding='utf-8')
out = L.read_bytes().decode('utf-8')
print()
print('LEDGER OK', len(L.read_bytes()))
for k in ('Ruling 118（用户裁定）', '补硬规矩 #70', '硬规矩 #68 修订', '第二层忽略规则',
          'WinError 32', '8e6a38f'):
    print('  %-24s %d' % (k, out.count(k)))

# 提交 .gitattributes + 账本
tmp = pathlib.Path(os.environ['TEMP']) / 'pe_cm2.txt'
tmp.write_bytes(("chore: .gitattributes 把 .superpowers/** 钉成 eol=lf（硬规矩 #70）\n\n"
                 "审计链里大量引用自己的字节数与 sha256，core.autocrlf=true 下一次 checkout\n"
                 "就会把 LF 重写成 CRLF、让那些数字当场变假。与 backend/data/ 同一条理由。\n"
                 "另含账本的 Ruling 118（用户裁定：审计链入库 + Task 3-12 照当前强度自动推进）。\n").encode('utf-8'))
print()
for args in (['git', 'add', '-A', '.gitattributes', '.superpowers'],
             ['git', 'commit', '-q', '-F', str(tmp)]):
    r = subprocess.run(args, capture_output=True, text=True)
    print(args[1], '->', r.returncode, (r.stderr or r.stdout).strip()[:200])
print(subprocess.run(['git', 'log', '--oneline', '-3'], capture_output=True, text=True).stdout)
print('git status --short = %r' % subprocess.run(['git', 'status', '--short'],
                                                 capture_output=True, text=True).stdout)

import pathlib

ROOT = pathlib.Path('.')

# ---------- (a) 计划 :250 的 .gitattributes 断言是假的（P3-D2 升级为 Critical） ----------
P = ROOT / 'Document/2026-10-06-实施计划02-智能处方引擎.md'
raw = P.read_bytes()
assert raw.count(b'\r\n') == raw.count(b'\n')
txt = raw.decode('utf-8').replace('\r\n', '\n')

OLD = ('- **不需要改 `.gitattributes`**（同 P2-A7：`backend/data/*.yaml text eol=lf` 已经覆盖 '
       '`backend/data/prescription/*.yaml`，本 Task 只需**确认**，`git ls-files --eol` 看一眼即可）')
NEW = ('- ⛔ **必须改 `.gitattributes`（P3-D2，Critical；原文说「不需要改」是假的）**\n'
       '\n'
       '  原文写「同 P2-A7：`backend/data/*.yaml text eol=lf` 已经覆盖 '
       '`backend/data/prescription/*.yaml`，本 Task 只需确认」。**控制者亲跑 `git check-attr` 推翻它**：\n'
       '\n'
       '  ```\n'
       '  $ git check-attr text eol -- backend/data/exercises.yaml\n'
       '  backend/data/exercises.yaml: text: set\n'
       '  backend/data/exercises.yaml: eol: lf\n'
       '  $ git check-attr text eol -- backend/data/prescription/RED-END-ABN-01.yaml\n'
       '  backend/data/prescription/RED-END-ABN-01.yaml: text: unspecified\n'
       '  backend/data/prescription/RED-END-ABN-01.yaml: eol: unspecified\n'
       '  ```\n'
       '\n'
       '  **gitattributes 的 `*` 不跨 `/`**，所以 `.gitattributes:14` 的 `backend/data/*.yaml` '
       '**只匹配 `data/` 根下的 `.yaml`，不匹配 `data/prescription/` 子目录**。\n'
       '\n'
       '  **后果**：`core.autocrlf=true` 下，那 18 个模板 YAML 检出时会变成 CRLF，'
       '而「归一化后 sha256[:16]」的指纹虽然本身不受影响（`test_refdata_prescription.py:83-84` '
       '与 Task 3 要新写的指纹测试都先 `replace(b"\\r\\n", b"\\n")`），'
       '**但工作树字节会随平台配置漂移**——**这正是 Plan 01 的国标评分表事故的原型**'
       '（硬规矩 #46/#47：21412 字节 LF ↔ 21915 字节 CRLF，`git checkout` 一次就让指纹测试变红）。'
       '而且 Task 3 的 YAML 里会有大量中文注释，CRLF/LF 混用还会让「按字节比对」的取证全部失真。\n'
       '\n'
       '  **裁定**：在 `.gitattributes` 的 `backend/data/*.md` 那一条之后加一行\n'
       '\n'
       '  ```\n'
       '  backend/data/**/*.yaml text eol=lf\n'
       '  ```\n'
       '\n'
       '  （`**` 跨目录；已有的 `backend/data/*.yaml` 可以留着，两条不冲突，'
       '**后写的优先**故 `**` 那条要放在后面）。加完必须亲验：\n'
       '  `git check-attr text eol -- backend/data/prescription/RED-END-ABN-01.yaml` 要返回 '
       '`text: set` / `eol: lf`；18 个文件落地后再跑 `git ls-files --eol -- backend/data/` '
       '确认每一行都是 `i/lf w/lf attr/text eol=lf`。\n'
       '\n'
       '  ⚠️ **这是本计划里第二次「以为不用改 `.gitattributes`」**（P2-A7 那次是把「已有规则」'
       '错列进 Modify，方向相反但同属「没有亲验属性覆盖范围」）。'
       '**→ 补进硬规矩 #61 的适用范围：`.gitattributes` / `.gitignore` 这类「规则文件」的覆盖面，'
       '必须用 `git check-attr` / `git check-ignore` 对**具体的目标路径**亲验，'
       '不能靠读规则文本推断。**')
assert txt.count(OLD) == 1, txt.count(OLD)
txt = txt.replace(OLD, NEW, 1)
P.write_bytes(txt.replace('\n', '\r\n').encode('utf-8'))
a = P.read_bytes()
at = a.decode('utf-8')
print('(a) PLAN bytes %d -> %d  纯CRLF=%s' % (len(raw), len(a), a.count(b'\r\n') == a.count(b'\n')))
print('    P3-D2 新文本在 =', at.count('必须改 `.gitattributes`（P3-D2，Critical'),
      '| 旧文本残留 =', at.count(OLD))
print('    计划里 .gitattributes 提到次数 =', at.count('.gitattributes'))

# ---------- (b) 账本：P3-D2 从「未亲验」升级为 Critical + 派单前的事实刷新 ----------
WS = ROOT / '.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎'
L = WS / 'progress.md'
src = L.read_text(encoding='utf-8')
OLD2 = ('- **D2**：`backend/data/prescription/*.yaml` 是新目录，`.gitattributes:14` 的 `backend/data/*.yaml` '
        '**只匹配 `data/` 根、不匹配子目录**（gitattributes 的 `*` 不跨 `/`）。'
        '**⚠️ 计划 `:250` 说「已经覆盖 `backend/data/prescription/*.yaml`」——这一句需要实现者亲验**：'
        '`git check-attr text eol -- backend/data/prescription/x.yaml`。'
        '**若不覆盖，必须加一条 `backend/data/**/*.yaml text eol=lf`**'
        '（那么 `.gitattributes` 就**真的要改**，与 `:250` 的「不需要改」相反）。'
        '**这是控制者没有亲验的一项**（那个目录还不存在，无法 `check-attr` 一个不存在的文件——'
        '但可以用一个临时路径试），**已在派单里要求实现者第一件事就验它**。')
NEW2 = ('- **D2 → 升级为 Critical，已更正计划（P3-D2）**：`backend/data/prescription/*.yaml` 是新目录，'
        '而 `.gitattributes:14` 的 `backend/data/*.yaml` **只匹配 `data/` 根、不匹配子目录**'
        '（gitattributes 的 `*` 不跨 `/`）。'
        '**控制者原先写「这一句需要实现者亲验」（因为那个目录还不存在），'
        '但随后用一条假想路径 `backend/data/prescription/RED-END-ABN-01.yaml` 亲跑了 '
        '`git check-attr`——`check-attr` 不要求文件存在**：\n\n'
        '```\n'
        '$ git check-attr text eol -- backend/data/exercises.yaml\n'
        '  backend/data/exercises.yaml: text: set      eol: lf\n'
        '$ git check-attr text eol -- backend/data/prescription/RED-END-ABN-01.yaml\n'
        '  …/prescription/RED-END-ABN-01.yaml: text: unspecified   eol: unspecified\n'
        '```\n\n'
        '**故计划 `:250` 那句「不需要改 `.gitattributes`（同 P2-A7：已经覆盖）」是假的**，'
        '必须加 `backend/data/**/*.yaml text eol=lf`。**后果是 Plan 01 国标评分表事故的原型**'
        '（硬规矩 #46/#47：`core.autocrlf=true` 下一次 checkout 就让工作树字节漂移、指纹测试变红），'
        '而 Task 3 的 18 个 YAML 会有大量中文注释，行尾混用还会让「按字节比对」的取证全部失真。\n\n'
        '**⚠️ 方法论上值得记的一点**：控制者第一反应是「目录不存在，验不了，交给实现者」——'
        '**这是错的**。`git check-attr` / `git check-ignore` 都是对**路径模式**求值、不要求文件存在，'
        '所以「还不存在的路径」照样能亲验。**「验不了」在绝大多数情况下是「没想到怎么验」。**\n'
        '**→ 补进硬规矩 #61 的适用范围：规则文件（`.gitattributes` / `.gitignore`）的覆盖面，'
        '必须用 `git check-attr` / `git check-ignore` 对具体目标路径亲验，不能靠读规则文本推断；'
        '且「目标路径还不存在」不是不验的理由。**')
assert src.count(OLD2) == 1, src.count(OLD2)
src = src.replace(OLD2, NEW2, 1)

OLD3 = ('**11 处计划更正已落盘（P3-A1…A10 + P3-D4），其中 1 处 Critical（P3-A1，'
        '与 Task 2 的 P2-A1 同型、控制者没把裁定传导过来）、5 处 Important（A2/A3/A4/A5/A6/A7）。**')
NEW3 = ('**12 处计划更正已落盘（P3-A1…A11 + P3-D2 + P3-D4），其中 2 处 Critical**：'
        '**P3-A1**（`app/seed/prescription.py`，与 Task 2 的 P2-A1 同型、控制者没把裁定传导过来）与 '
        '**P3-D2**（`.gitattributes` 不覆盖 `data/prescription/` 子目录，照原文做会重演 Plan 01 的指纹事故）；'
        '**5 处 Important**（A2/A3/A4/A5/A6/A7）。')
assert src.count(OLD3) == 1, src.count(OLD3)
src = src.replace(OLD3, NEW3, 1)

OLD4 = ('**控制者错误计数**：本轮预检查出的都是**计划编写期（`e26347f`）就存在的缺陷**，'
        '与 Task 2 预检的 P2-A1…A10 同源，故合并记 **#124**（一次预检不足，覆盖 11 处）；'
        '**P3-A1 单独记 #125**')
NEW4 = ('**控制者错误计数**：本轮预检查出的都是**计划编写期（`e26347f`）就存在的缺陷**，'
        '与 Task 2 预检的 P2-A1…A10 同源，故合并记 **#124**（一次预检不足，覆盖 12 处，'
        '**含 P3-D2 这条 Critical**——它是 `e26347f` 写计划时就没验过 `.gitattributes` 的覆盖面，'
        '而在 Task 2 预检写 P2-A7 时**又错过一次**：那一轮我亲验了 `backend/data/*.yaml` 存在、'
        '就顺手写下「已经覆盖 `backend/data/prescription/*.yaml`」，**把「规则存在」当成了「规则覆盖」**）；'
        '**P3-A1 单独记 #125**')
assert src.count(OLD4) == 1, src.count(OLD4)
src = src.replace(OLD4, NEW4, 1)

L.write_text(src, encoding='utf-8')
out = L.read_bytes().decode('utf-8')
print()
print('(b) LEDGER OK', len(L.read_bytes()))
for k in ('D2 → 升级为 Critical', 'text: unspecified', '补进硬规矩 #61 的适用范围',
          '12 处计划更正已落盘', '含 P3-D2 这条 Critical'):
    print('  %-34s %d' % (k, out.count(k)))

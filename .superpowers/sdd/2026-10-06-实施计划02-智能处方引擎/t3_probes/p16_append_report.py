# -*- coding: utf-8 -*-
"""把 §9.3 的第 5 条与标题计数追加进 task-3-report.md。

⚠️ **为什么用 python 字节级写而不是编辑工具**：上一轮我用编辑工具做了这两处改动，它
**报了成功、还回显了 diff**，而 `read_bytes()` 显示文件与改动前的备份**逐字节相同**
（79 881 B / sha16 `1D4555B2D4D22070`，`t3_probes/p15_verify_report_append.py` 实跑，
新串命中 0、旧串「（4 条」命中 1）。这正是派单 §0 记的那个失效形态
（「已记录 59+ 次报成功而磁盘未写，最新形态是连 diff 和整篇 cat -n 回显一起伪造」）。
故本轮按派单的硬要求「所有写文件走 python」重写，并在写完后立刻双向串查。
"""
import hashlib
import pathlib

P = pathlib.Path(r'c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers'
                 r'\sdd\2026-10-06-实施计划02-智能处方引擎\task-3-report.md')

OLD_HEADER = '### 9.3 我自己本轮犯的错（4 条，全部自纠）'
NEW_HEADER = ('### 9.3 我自己本轮犯的错（5 条，全部自纠；其中 2 条是被我自己写的'
              '断言/闸门拦下的）')

ANCHOR = '''4. **`test_sync_templates_updates_a_changed_field_in_place` 的签名里多带了一个用不到的
   `monkeypatch` fixture**（我原本打算改 YAML、后来改成改 DB 行，忘了把参数删掉）。已删。
'''

ITEM5 = '''5. **我在源码 docstring 里逐字复述了被自己撤销的旧断言**（`_PRESCRIPTION_PUBLIC_BASELINE`
   加 `["Template"]` 那一整串），**被自己的落盘闸门抓出来了**：`t3_probes/p14_landing_gate.py`
   的「旧串残留 == 0」那一栏对它命中 1 次。这正是硬规矩 **#74** 要挡的形态——更正说明里抄一遍
   原句，「grep 旧串应当 0 命中」这道闸门就失效了，下一个人分不清「还在用」与「已作废但被引用」。
   已改成描述式（「基线**加上一个当时还不在公开面里的名字**，而它挑的那个名字正是 `Template`」），
   并在源码里明写「被撤销的旧字面量本轮**不再逐字复述**」。⚠️ **本报告 §12.2 仍保留那个旧
   字面量**：报告是审计链、不是源码更正说明，而落盘闸门是**逐文件**的（`p14` 的 32 条 case
   里没有一条查本报告），故不冲突。⚠️ 同一个闸门第一次跑还假红了 3 条，那是**探针自己的缺陷**
   （多行锚用 `\\n` 写、而 `backend/**` 的工作树是 CRLF，跨行的锚一律 0 命中），不是磁盘未写；
   修法是串查前先归一化，并按升级口径 ③ 加了一条「查询有效性对照」（用一个已知存在的串验证
   查询本身有效）。**两件事合起来正好说明这道闸门为什么值得跑**：它一次里既抓到了我自己的真
   错误（#74），也暴露了它自己的假阳性来源。
6. **编辑工具对本报告文件的两次写入「报成功而磁盘未写」**，即上面第 5 条那个改动本身第一次
   根本没落盘。取证：改动前先做了字节备份
   `t3_probes/task-3-report.md.bak-before-append`（79 881 B / `1D4555B2D4D22070`），
   两次编辑都回显了 diff，随后 `p15_verify_report_append.py` 实测文件与备份**逐字节相同**、
   新串命中 **0**、旧串「（4 条」命中 **1**。处置：改用 python `read_bytes`/`write_bytes`
   重写（本脚本），写完立刻双向串查（下面打印）。
   ⚠️ **同一轮里对 `backend/tests/test_refdata_prescription.py` 的编辑是真落盘了的**
   （`p14_landing_gate.py` 那条 case 从「旧串=1」变成「旧串=0」），故这不是「工具全局失效」，
   而是**逐次不可信**——唯一可靠的判据是写完立刻用 `read_bytes()` 双向串查（硬规矩 #48 升级口径）。
'''

b = P.read_bytes()
t = b.decode('utf-8')
print('改前 bytes=%d sha16=%s' % (len(b), hashlib.sha256(b).hexdigest()[:16].upper()))
assert t.count(OLD_HEADER) == 1, 'header 锚命中 %d' % t.count(OLD_HEADER)
assert t.count(ANCHOR) == 1, 'item4 锚命中 %d' % t.count(ANCHOR)
t = t.replace(OLD_HEADER, NEW_HEADER).replace(ANCHOR, ANCHOR + ITEM5)
P.write_bytes(t.encode('utf-8'))

a = P.read_bytes()
u = a.decode('utf-8')
print('改后 bytes=%d LF=%d CRLF=%d sha16=%s'
      % (len(a), a.count(b'\n'), a.count(b'\r\n'),
         hashlib.sha256(a).hexdigest()[:16].upper()))
checks = [
    ('新 header', NEW_HEADER, 1),
    ('旧 header 残留', OLD_HEADER, 0),
    ('第 5 条', '5. **我在源码 docstring 里逐字复述', 1),
    ('第 6 条', '6. **编辑工具对本报告文件的两次写入', 1),
    ('p14 引用', 'p14_landing_gate.py', 2),
    ('p15 引用', 'p15_verify_report_append.py', 1),
    ('原第 4 条仍在', 'monkeypatch` fixture**（我原本打算改 YAML', 1),
    ('§12.2 仍在', '12.2 `:951` 那条的用意', 1),
    ('§15 仍在（尾部没被截断）', '⑨ 一处我没改、但认为该报的过期散文', 1),
]
bad = 0
for name, s, want in checks:
    got = u.count(s)
    ok = got == want
    bad += (not ok)
    print('  %-4s %-24s 命中 %d（期望 %d）' % ('OK' if ok else 'FAIL', name, got, want))
print()
print('双向串查判定: %s' % ('PASS' if bad == 0 else 'FAIL(%d)' % bad))

# -*- coding: utf-8 -*-
"""pe_fr2_edit_fix.py — 修我自己刚写进 purity 的两处不准（AST 形状 / G3 的机制）。"""
import pathlib
import sys

P = pathlib.Path(sys.argv[1]).resolve() / "tests/architecture/test_domain_purity.py"

EDITS = [
    ('''    还原不出来的形态（``f()()``、``table[0]()``、``getattr(x, "now")()``、
    ``__import__("datetime").datetime.now()``——它们的 ``node.func`` 分别是 ``ast.Call`` /
    ``ast.Subscript`` / ``ast.Call`` / ``ast.Attribute(value=ast.Call)``，本函数只沿
    ``ast.Attribute`` 下溯到 ``ast.Name``，故一律返回 ``None``），本守卫因此**放过**它们。
''',
     '''    还原不出点号串的形态一律返回 ``None``，本守卫因此**放过**它们。四种形态的
    ``node.func`` 是什么，本机 Python 3.11.1 实跑（``ast.parse(s).body[0].value.func``）::

        f()()                                   ast.Call
        table[0]()                              ast.Subscript
        getattr(x, "now")()                     ast.Call
        __import__("datetime").datetime.now()   ast.Attribute(value=ast.Attribute(value=ast.Call))

    本函数只沿 ``ast.Attribute`` 下溯、走到 ``ast.Name`` 才收工，故上面四种都还原不出来。
    ``eval("…")`` 是**另一种**放过法：它的 ``node.func`` 是 ``ast.Name(id="eval")``、点号串
    还原得出 ``"eval"``，只是 ``eval`` 不在 :data:`FORBIDDEN_CALLS` 里。
'''),
    ('''    ⚠️ **「拿到工具必经 import」也不成立**（上表第 8–14 行，Plan02 Ruling 38）：
    ``__import__`` / ``eval`` / ``getattr`` 三个**内置名**都能在不写一条 ``ast.Import`` 的
    前提下拿到 ``datetime`` / ``os`` / ``builtins``，而 G2 的 :func:`_dotted` 对这些形态
    一律返回 ``None``、G3 的子串表里也没有 ``__import__`` / ``eval``，于是三条守卫**全绿**。
    ``__import__("os").listdir(".")`` 这一行尤其值得记住：它同时绕过了「不许取时钟」与
    「不许读盘」两条**立意**，而三条守卫一条都不响。这七行不是待修的漏洞清单，而是本条
    守卫的**能力边界**：它守的是「直白地写出 ``datetime.now()`` / ``open()``」，不守任何
    需要还原、求值或别名追踪才能看清的形态。要堵这一族就得把 ``__import__`` / ``eval`` /
    ``getattr`` 这些内置名本身列进封禁，代价是 domain 里连一个正常的
    ``getattr(obj, "name", default)`` 都写不了——本仓不做，但必须写清楚（硬规矩 #39）。
''',
     '''    ⚠️ **「拿到工具必经 import」也不成立**（上表第 8–14 行，Plan02 Ruling 38）：
    ``__import__`` / ``eval`` / ``getattr`` 三个**内置名**都能在不写一条 ``ast.Import`` 的
    前提下拿到 ``datetime`` / ``os`` / ``builtins``，于是 G1 一声不响；G2 对
    ``__import__(…).datetime.now()`` / ``getattr(x, "now")()`` / ``table[0]()`` 还原不出
    点号串（见 :func:`_dotted`），对 ``eval(…)`` 还原得出 ``"eval"``、只是它不在
    :data:`FORBIDDEN_CALLS` 里；G3 的子串表里既没有 ``__import__`` 也没有 ``eval``——
    三条守卫**全绿**。

    ``__import__("os").listdir(".")`` 这一行尤其值得记住：``os.listdir`` 与 ``import os``
    **两个子串都在** :data:`FORBIDDEN_IO` 里，而写成这个形状后源码里**一个都不出现**
    （本机实跑：该探针命中的 ``FORBIDDEN_IO`` 子串数 = 0；对照组 ``import os`` 换行
    ``os.listdir(".")`` 命中 2 个），于是第三条子串守卫也一声不响——「不许读盘」这条立意
    被完整绕过。这七行不是待修的漏洞清单，而是本条守卫的**能力边界**：它守的是「直白地
    写出 ``datetime.now()`` / ``open()`` / ``os.listdir()``」，不守任何需要还原、求值或
    别名追踪才能看清的形态。要堵这一族就得把 ``__import__`` / ``eval`` / ``getattr`` 这些
    内置名本身列进封禁，代价是 domain 里连一个正常的 ``getattr(obj, "name", default)``
    都写不了——本仓不做，但必须写清楚（硬规矩 #39）。
'''),
]

raw = P.read_bytes()
text = raw.decode("utf-8")
crlf = raw.count(b"\r\n")
assert crlf == text.count("\n"), "不是纯 CRLF"
norm = text.replace("\r\n", "\n")
for i, (old, new) in enumerate(EDITS):
    n = norm.count(old)
    assert n == 1, "第 %d 处命中 %d 次" % (i, n)
    norm = norm.replace(old, new)
out = norm.replace("\n", "\r\n").encode("utf-8")
P.write_bytes(out)
print("已写 %s  %d 处  %d -> %d 字节  CRLF %d" % (P.name, len(EDITS), len(raw), len(out), out.count(b"\r\n")))

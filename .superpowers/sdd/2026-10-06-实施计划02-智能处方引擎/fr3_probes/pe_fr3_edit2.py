# -*- coding: utf-8 -*-
"""pe_fr3_edit2.py — 自查后的一处修正：新测试 docstring 里「见任务报告 fix round 3」这个指针
指向不入库的文件（.gitignore:10 的 .superpowers/），正是账本 Ruling 27 / 评审 M2 要消灭的形态。
改成「写全复现命令 + 贴实跑的断言原文」。只改两个新函数的 docstring，不动任何代码。

用法: python pe_fr3_edit2.py <仓库根>
"""
import pathlib
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
PURITY = REPO / "backend/tests/architecture/test_domain_purity.py"
LAYER = REPO / "backend/tests/architecture/test_layering.py"

REPRO_PURITY = """
    三条的复现命令是同一条（在 ``backend/`` 下）：把对应改动打回本文件的 ``_absolute`` /
    ``_imported_modules``，再跑 ``python -m pytest tests/architecture -q``。本轮实测三种变异
    各让**本文件这一条**红、而 :mod:`tests.architecture.test_layering` 那一条**保持绿**——
    两份 ``_absolute`` 互相独立，这正是硬规矩 #51 要两份回归测试的原因。断言里印出来的折算值
    也是实跑的：越界档报 ``_absolute('domain', 4, ('app', 'domain'), 'tables') =
    'app.domain'``（而 ``resolve_name('....domain', 'app.domain')`` 抛 ``ImportError``）、
    ``tail = module`` 报 ``_absolute('', 2, ('app', 'pipeline'), 'seed') = 'app'``（正确答案
    ``'app.seed'``）、展开档报 ``['app.seed'] != ['app.seed', 'app.pipeline']``。
""".strip("\n").split("\n")

REPRO_LAYER = """
    三条的复现命令是同一条（在 ``backend/`` 下）：把对应改动打回本文件的 ``_absolute`` /
    ``_imported_modules``，再跑 ``python -m pytest tests/architecture -q``。本轮实测三种变异
    各让**本文件这一条**红、而 :mod:`tests.architecture.test_domain_purity` 那一条**保持绿**——
    两份 ``_absolute`` 互相独立，这正是硬规矩 #51 要两份回归测试的原因。断言里印出来的折算值
    也是实跑的：越界档报 ``_absolute('seed', 5, ('app', 'db', 'models'), 'generate') =
    'app.db.seed'``（而 ``resolve_name('.....seed', 'app.db.models')`` 抛 ``ImportError``）、
    ``tail = module`` 报 ``_absolute('', 2, ('app', 'pipeline'), 'seed') = 'app'``（正确答案
    ``'app.seed'``）、展开档报 ``['app.seed'] != ['app.seed', 'app.pipeline']``。
""".strip("\n").split("\n")

EDITS = [
    (PURITY,
     "      → 本测试红（变异实测，见任务报告 fix round 3）。",
     ["      → 本测试红。"]),
    (PURITY,
     "      ``app.seed`` → 本测试红（同上，变异实测）。",
     ["      ``app.seed`` → 本测试红。"]),
    (PURITY,
     "      模块，Plan02 Ruling 36）→ 末尾那一段红。",
     ["      模块，Plan02 Ruling 36）→ 末尾那一段红。", ""] + REPRO_PURITY),
    (LAYER,
     "      ``None`` → 本测试红（变异实测，见任务报告 fix round 3）。",
     ["      ``None`` → 本测试红。"]),
    (LAYER,
     "      ``app.seed`` → 本测试红（同上，变异实测）。",
     ["      ``app.seed`` → 本测试红。"]),
    (LAYER,
     "      模块，Plan02 Ruling 36）→ 末尾那一段红。",
     ["      模块，Plan02 Ruling 36）→ 末尾那一段红。", ""] + REPRO_LAYER),
    (LAYER,
     "    下面的变异实测证明了这一点：只变异本文件的 ``_absolute``，purity 那条**保持绿**。",
     ["    下面「复现命令」那一段给了实测：只变异本文件的 ``_absolute``，purity 那条**保持绿**。"]),
]


def main():
    cache = {}
    for path, old, new in EDITS:
        if path not in cache:
            raw = path.read_bytes()
            assert raw[:3] != b"\xef\xbb\xbf"
            text = raw.decode("utf-8")
            assert text.count("\n") == text.count("\r\n"), path
            cache[path] = text.split("\r\n")
        lines = cache[path]
        hits = [i for i, l in enumerate(lines) if l == old]
        assert len(hits) == 1, (path.name, old[:40], hits)
        lines[hits[0]:hits[0] + 1] = new
        print("  %-24s 行 %d：%r -> %d 行" % (path.name, hits[0] + 1, old.strip()[:36], len(new)))
    for path, lines in cache.items():
        data = "\r\n".join(lines).encode("utf-8")
        path.write_bytes(data)
        back = path.read_bytes()
        assert back == data, path
        text = back.decode("utf-8")
        compile(text, str(path), "exec")
        print("  写盘 %-24s %d 字节 CRLF=%d 裸LF=%d 乱码=%s compile=OK 行数=%d"
              % (path.name, len(back), back.count(b"\r\n"),
                 back.count(b"\n") - back.count(b"\r\n"), "\ufffd" in text,
                 len(text.split("\r\n"))))
        assert "任务报告" not in text, (path.name, "还留着指向不入库文件的指针")
        assert text.count("python -m pytest tests/architecture -q") >= 1
    print("写盘完成")


main()

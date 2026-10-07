# -*- coding: utf-8 -*-
"""pe_fr4_edit.py — fix round 4 的落盘（Ruling 54 + Ruling 55）。

用法: python pe_fr4_edit.py <仓库根>

编辑工具在本仓不可信（账本记录 47+ 次「报成功而磁盘未写」），故一律用 python 按字节写：
  * 读字节 -> 断言「裸 LF == 0」-> 归一成 LF 做替换 -> 整体换回 CRLF -> write_bytes
  * 每处替换都按**行号区间 + 指纹**双确认（行号会漂，指纹防止改错地方）
  * 自底向上改，避免前面的插入让后面的行号失效
  * 落盘后重新读字节、逐处 assert 新串出现次数恰为 1、旧串出现次数为 0
"""
import pathlib
import sys

REPO = pathlib.Path(sys.argv[1]).resolve()
PURITY = REPO / "backend/tests/architecture/test_domain_purity.py"
LAYERING = REPO / "backend/tests/architecture/test_layering.py"

# --------------------------------------------------------------- 新文本块

PURITY_DOC_HEAD_OLD = [
    "三条守卫，Plan 02 Task 1 全部改写过一次，改动理由各写在对应测试的 docstring 里：",
]
PURITY_DOC_HEAD_NEW = [
    "本文件有 **4 个 ``test_*``**：**三条架构守卫** + 一条**辅助函数的单元测试**",
    "（``test_absolute_folding_matches_resolve_name``，测的是 ``_absolute`` / ``_package_of``",
    "这两个辅助函数，**不是第四条守卫**；Plan02 Ruling 46/54）。三条守卫 Plan 02 Task 1 全部",
    "改写过一次，改动理由各写在对应测试的 docstring 里：",
]

PURITY_R37_OLD = [
    "    就会折成 ``app.domain.seed.generate``、命中白名单前缀 ``app.domain.`` → **守卫当场假绿**",
]
PURITY_R37_NEW = [
    "    就会折成 ``app.domain.seed``（**不是** ``app.domain.seed.generate``：``generate`` 住在",
    "    ``node.names`` 里、不进折算串，Plan02 Ruling 36；本机 Python 3.11.1 实跑",
    "    ``_absolute(\"seed\", 2, (\"app\", \"domain\", \"ind\"))`` -> ``'app.domain.seed'``、",
    "    ``_is_allowed('app.domain.seed')`` -> ``True``）、命中白名单前缀 ``app.domain.`` →",
    "    **守卫当场假绿**",
]

BOUND_OLD_PURITY = [
    "    * ``package`` 入参是**手写的**，故 :func:`_package_of` 不在守卫范围内：谁把它改成返回",
    "      「模块名」而不是「包名」（``(\"app\", \"domain\", \"x\")``），本测试**照样全绿**，而两条",
    "      架构守卫会一起假绿。那一档今天只有 :func:`_absolute` docstring 里 ``resolve_name``",
    "      的两行实跑举例（Plan02 Ruling 37）在交代，仓库里同样没有断言看着。",
]
BOUND_OLD_LAYERING = [
    "    * ``package`` 入参是**手写的**，故 :func:`_package_of` 不在守卫范围内：谁把它改成返回",
    "      「模块名」而不是「包名」，本测试**照样全绿**，而守卫会假绿（``app/db/models/x.py``",
    "      里的 ``from ...seed import …`` 会折成 ``app.db.seed``、不再以 ``app.seed`` 开头）。",
    "      那一档今天只有 :func:`_absolute` docstring 里的实跑举例（Plan02 Ruling 37）在交代。",
]
BOUND_NEW = [
    "    * :func:`_package_of` 由本测试**末尾那一段**看着（Plan02 Ruling 54），但**只在枚举到",
    "      的那 4 个形状上**：``app/db/models/organisation.py`` 与 ``app/db/models/__init__.py``",
    "      （包深 3；两者必须给出**同一个**包——这一格正是 ``parts[:-1]`` 这个写法的全部理由）、",
    "      ``app/domain/indicators.py``（包深 2）、``app/domain/prescription/match.py``（包深 3，",
    "      Task 2 才会出现的形状；``_package_of`` 是纯路径运算、不碰文件系统，故可以先断言）。",
    "      **没枚举进去的包深（包深 4 及更深）不被覆盖**；上面那 11 格矩阵的 ``package`` 入参",
    "      仍是**手写的**，故矩阵与末尾那一段互不覆盖、谁也不替代谁。",
]


def block(msg):
    return [
        "",
        "    # ---------------------------------------------------------------- Ruling 54",
        "    # 上面 11 格的 package 入参是**手写的**，故 _package_of 被改坏时它们照样全绿；而它是",
        "    # 两条守卫共同的假绿入口（Plan02 Ruling 37/54）。_package_of 是纯路径运算、不碰文件",
        "    # 系统，故最后一格可以写 Task 2 才会出现的形状。",
        "    pkg_cases = [",
        "        # (backend/ 下的相对路径, 正确的**包**, parts[:-1] 写成 parts 时会得到的**模块路径**)",
        "        (\"app/db/models/organisation.py\", (\"app\", \"db\", \"models\"),",
        "         (\"app\", \"db\", \"models\", \"organisation\")),",
        "        # __init__.py 与同目录的普通模块给出**同一个**包：这一格是 parts[:-1] 的全部理由",
        "        (\"app/db/models/__init__.py\", (\"app\", \"db\", \"models\"),",
        "         (\"app\", \"db\", \"models\", \"__init__\")),",
        "        (\"app/domain/indicators.py\", (\"app\", \"domain\"), (\"app\", \"domain\", \"indicators\")),",
        "        # Task 2 会新建 app/domain/prescription/ 子包（今天不存在）",
        "        (\"app/domain/prescription/match.py\", (\"app\", \"domain\", \"prescription\"),",
        "         (\"app\", \"domain\", \"prescription\", \"match\")),",
        "    ]",
        "    pkg_offenders: list[str] = []",
        "    for rel, want_pkg, module_path in pkg_cases:",
        "        got_pkg = _package_of(BACKEND / rel)",
        "        if got_pkg != want_pkg:",
        "            pkg_offenders.append(",
        "                f\"_package_of(BACKEND / {rel!r}) = {got_pkg!r}，应为**包** {want_pkg!r}\"",
        "            )",
        "        if got_pkg == module_path:",
        "            pkg_offenders.append(",
        "                f\"_package_of(BACKEND / {rel!r}) = {got_pkg!r} 是**模块路径**、不是包\"",
        "                f\"（parts[:-1] 被写成了 parts）\"",
        "            )",
        "    # 后果也要能跑、不能只写在断言消息里：把 _package_of 的输出直接喂给 _absolute，",
        "    # 结果仍须与 resolve_name 逐字相同（判据同上，锚在 Python 自己的语义上）。",
        "    for rel, level, module, want_pkg in (",
        "            (\"app/domain/indicators.py\", 2, \"seed\", (\"app\", \"domain\")),",
        "            (\"app/db/models/organisation.py\", 3, \"seed\", (\"app\", \"db\", \"models\"))):",
        "        rel_import = \".\" * level + module",
        "        pkg_str = \".\".join(want_pkg)",
        "        got = _absolute(module, level, _package_of(BACKEND / rel))",
        "        want = importlib.util.resolve_name(rel_import, pkg_str)",
        "        if got != want:",
        "            pkg_offenders.append(",
        "                f\"{rel} 里的 from {rel_import} import …：用 _package_of 的结果折算得到 \"",
        "                f\"{got!r}，而 resolve_name({rel_import!r}, {pkg_str!r}) = {want!r}\"",
        "            )",
        "    assert pkg_offenders == [], (",
    ] + msg + [
        "        + \"\\n\".join(pkg_offenders)",
        "    )",
    ]


PURITY_MSG = [
    "        \"_package_of 返回的不是**包**（Plan02 Ruling 37/54）：parts[:-1] 写成 parts 会让\"",
    "        \"它返回**模块路径**，于是 app/domain/x.py 里的 from ..seed import … 折成 \"",
    "        \"app.domain.seed、命中白名单前缀 app.domain. → 本文件的守卫假绿（test_layering.py \"",
    "        \"那一份同理：app/db/models/x.py 里的 from ...seed import … 折成 app.db.seed、不再\"",
    "        \"以 app.seed 开头），而在本段断言加上之前，这么改一次全量测试都照样通过：\\n\"",
]
LAYERING_MSG = [
    "        \"_package_of 返回的不是**包**（Plan02 Ruling 37/54）：parts[:-1] 写成 parts 会让\"",
    "        \"它返回**模块路径**，于是 app/db/models/x.py 里的 from ...seed import … 折成 \"",
    "        \"app.db.seed、不再以 app.seed 开头 → 本守卫假绿（test_domain_purity.py 那一份同理：\"",
    "        \"app/domain/x.py 里的 from ..seed import … 折成 app.domain.seed、命中白名单前缀 \"",
    "        \"app.domain.），而在本段断言加上之前，这么改一次全量测试都照样通过：\\n\"",
]

TAIL_ANCHOR = '    assert got == want, f"一名一条的展开失效: {got} != {want}"'


def edit(path, ops):
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    assert text.count("\r\n") > 0 and text.count("\n") == text.count("\r\n"), "行尾不是纯 CRLF"
    lines = text.replace("\r\n", "\n").split("\n")
    # ops: (start1, end1, fingerprint, new_lines)；自底向上
    for start, end, finger, new in sorted(ops, key=lambda o: -o[0]):
        got = lines[start - 1:end]
        assert got == finger, (path.name, start, end, got, finger)
        lines[start - 1:end] = new
    out = "\r\n".join(lines).encode("utf-8")
    path.write_bytes(out)
    return raw, out


def verify(path, must_have, must_not):
    t = path.read_bytes().decode("utf-8")
    for s in must_have:
        assert t.count(s) == 1, (path.name, "缺失或重复", s, t.count(s))
    for s in must_not:
        assert t.count(s) == 0, (path.name, "旧串未清除", s, t.count(s))
    b = path.read_bytes()
    print("  %-22s bytes=%d CRLF=%d 裸LF=%d BOM=%s 行尾纯CRLF=%s"
          % (path.name, len(b), b.count(b"\r\n"),
             b.count(b"\n") - b.count(b"\r\n"), b.startswith(b"\xef\xbb\xbf"),
             b.count(b"\n") == b.count(b"\r\n")))


def tail_line(lines_of, anchor):
    idx = [i for i, l in enumerate(lines_of, 1) if l == anchor]
    assert len(idx) == 1, idx
    return idx[0]


print("=== 落盘前：确认插入锚点唯一 ===")
for p in (PURITY, LAYERING):
    ls = p.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
    print("  %-22s %r 在第 %d 行（唯一）" % (p.name, TAIL_ANCHOR[:40] + "…", tail_line(ls, TAIL_ANCHOR)))

pl = PURITY.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
ll = LAYERING.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
p_tail = tail_line(pl, TAIL_ANCHOR)
l_tail = tail_line(ll, TAIL_ANCHOR)

print()
print("=== 落盘 ===")
edit(PURITY, [
    (p_tail, p_tail, [pl[p_tail - 1]], [pl[p_tail - 1]] + block(PURITY_MSG)),
    (233, 236, BOUND_OLD_PURITY, BOUND_NEW),
    (139, 139, PURITY_R37_OLD, PURITY_R37_NEW),
    (8, 8, PURITY_DOC_HEAD_OLD, PURITY_DOC_HEAD_NEW),
])
edit(LAYERING, [
    (l_tail, l_tail, [ll[l_tail - 1]], [ll[l_tail - 1]] + block(LAYERING_MSG)),
    (227, 230, BOUND_OLD_LAYERING, BOUND_NEW),
])
print("  已写盘")

print()
print("=== 落盘后读回确认（shell 口径）===")
verify(PURITY,
       ["本文件有 **4 个 ``test_*``**：**三条架构守卫** + 一条**辅助函数的单元测试**",
        "就会折成 ``app.domain.seed``（**不是** ``app.domain.seed.generate``",
        ":func:`_package_of` 由本测试**末尾那一段**看着（Plan02 Ruling 54）",
        '        ("app/db/models/organisation.py", ("app", "db", "models"),',
        '        ("app/domain/prescription/match.py", ("app", "domain", "prescription"),',
        "    assert pkg_offenders == [], ("],
       ["就会折成 ``app.domain.seed.generate``、命中白名单前缀",
        "``package`` 入参是**手写的**，故 :func:`_package_of` 不在守卫范围内",
        "三条守卫，Plan 02 Task 1 全部改写过一次"])
verify(LAYERING,
       [":func:`_package_of` 由本测试**末尾那一段**看着（Plan02 Ruling 54）",
        '        ("app/db/models/__init__.py", ("app", "db", "models"),',
        "    assert pkg_offenders == [], (",
        "app.db.seed、不再以 app.seed 开头 → 本守卫假绿"],
       ["``package`` 入参是**手写的**，故 :func:`_package_of` 不在守卫范围内"])
print("  两个文件的全部新串命中恰 1 次、旧串命中 0 次")

"""``backend/scripts/demo_bootstrap.py`` 的守卫：**刻意留着不绑口令的那两个账号**（台账 G23）。

--------------------------------------------------------------------------
为什么会有这个文件
--------------------------------------------------------------------------

灌库器自 Plan 09 Task 2 起**刻意不绑全**：:data:`scripts.demo_bootstrap.UNBOUND_LOGINS`
点名的两个账号（一个学生 + 一个教师）灌完仍然 ``password_hash IS NULL``，于是
「管理台签发一次性绑定令牌 → 拿它去首次绑定」那一条路线在**刚灌出来的库上**走得通
（改前 63 个账号全绑定，签发端点对已绑定账号一律 409 ``password_already_bound``，
甲方**一次都没用过** Plan 08 最重要的那一格安全功能）。

⚠️ 而这件事的失效方向**全是静默的**，故每一条守卫都对着一个具体的静默档：

* :func:`test_the_guide_names_exactly_the_unbound_logins_of_the_seeder` —— 说明书点名的
  那两个登录名与灌库器的常量**恰好相等**（两侧不同源：一侧读文档文本、一侧读常量）。
  少了它，「改常量的人漏改说明书」是静默的，而甲方照着说明书去签发会得到 409；
* :func:`test_a_freshly_seeded_database_leaves_exactly_those_two_password_hashes_null` ——
  **真灌一份库**（子进程跑灌库器，不是 mock）再逐行读回来；
* :func:`test_every_other_account_in_a_freshly_seeded_database_is_bound` —— 上一条的补集
  （互为冗余：少任何一条，「跳过的判据被反过来」都有一侧是绿的）；
* :func:`test_is_deliberately_unbound_requires_both_the_kind_and_the_login` —— 判据函数的
  ``kind`` 与 ``login`` **都要对**（交叉不成立 ⇒「只看 login」那一档当场红）；
* :func:`test_the_four_route_accounts_are_never_left_unbound` —— 说明书 §4 那四条路线
  要登录的四个账号一个都不能被留成未绑定（留了就是把试用路线弄坏）；
* :func:`test_the_unbound_pair_keeps_the_constraints_that_make_it_safe` —— 那两条
  **结构性**约束（``frontend/scripts/smoke.mjs`` 按代理键登录 1 / 4 / 5、并在运行时现找
  「``T0001`` 本学期任教的学生」去登录）与「教师那一侧不能是唯一的管理员」；
* :func:`test_the_seeder_refuses_a_login_that_is_not_on_the_roster` —— 第一道：**响亮失败**；
* :func:`test_the_seeder_says_out_loud_when_the_scale_arguments_are_not_the_defaults` ——
  第三道：非缺省参数下**打印一句人话**（登录名仍成立、背后那个人换了）；
* :func:`test_the_seeder_prints_the_two_it_left_unbound` —— [6/7] 真的把它们印出来
  （台账 G23 逐字要求「留哪两个要写进说明书，否则下一个人以为灌库漏了」，
  而说明书是**时点快照**、终端输出是**当场**的，故两处都要有）；
* :func:`test_no_ps1_becomes_a_second_owner_of_the_unbound_roster` —— 两个调用者
  （``scripts/trial.ps1`` 的 ``-Reset`` 与 ``backend/scripts/demo.ps1``）走的是**同一个**
  灌库器，且**不抄第二份清单**。

⚠️ **本文件一律用 ``tmp_path`` 下的库**，且从不让 ``PE_DB_URL`` 落到缺省：
``app.config.DEFAULT_DB_URL`` 逐字指向 ``backend/pe.db``（禁区），而
``backend/pe_trial.db`` 是甲方**正在试用**的那一份活库（一个字节都不许动）。
"""
from __future__ import annotations

import os
import pathlib
import re
import sqlite3
import subprocess
import sys

import pytest

from scripts import demo_bootstrap as boot

#: ``backend/``（本文件在 ``backend/tests/`` 下）。
BACKEND = pathlib.Path(__file__).resolve().parents[1]

#: 仓库根。
REPO_ROOT = BACKEND.parent

#: 甲方试用说明书。⚠️ 它是 :data:`boot.UNBOUND_LOGINS` 的**另一个**住址，
#: 也是本文件核心守卫的期望侧之一（两侧不同源：一侧是文档文本、一侧是 Python 常量）。
GUIDE_MD = REPO_ROOT / "Document" / "2026-10-15-甲方试用说明书.md"

#: 说明书里点名「刻意未绑定」的那些行要认的两个词。⚠️ 判据是**两个词同时在一行里**：
#: 只有「刻意」会拖进一大片散文，只有「未绑定」会拖进须知 ②（那一节讲的是**抢绑**
#: 这个安全风险，不是「本库留了哪两个」）。
DELIBERATE_WORDS = ("刻意", "未绑定")

#: 学号 / 工号的形状。⚠️ 与 ``frontend/scripts/smoke.mjs`` 第 14 步 §I1 那一拍
#: 逐字同一条谓词（学生 = 10 位数字、教师 = ``T`` + 4 位数字），两侧刻意各写一份：
#: 那一条钉的是**登录页上印的例子**，本条钉的是**说明书点名的那两个**。
LOGIN_SHAPE = re.compile(r"`(\d{10}|T\d{4})`")

#: 说明书 §4 那四条试用路线**要登录**的四个账号（路线一 = 学生 ``2023120001``、
#: 路线二第 7 步 = 学生 ``2025060001``、路线二/四 = 教师 ``T0001``、
#: 路线二第 5 步与路线三 = 管理员 ``T0003``）。
#: ⚠️ 它在本文件里是**断言的期望侧**，故逐字写死；而:func:`test_the_four_route_accounts_are_never_left_unbound`
#: 另外核实这四个字面量**真的**出现在说明书 §4 里（反空转：文档换了账号，本清单会红）。
ROUTE_LOGINS = ("2023120001", "2025060001", "T0001", "T0003")

#: ``frontend/scripts/smoke.mjs`` 按**代理键**登录的三个学生（第 2 步那一拍
#: ``for (const id of [4, 5, 1])``）。⚠️ 期望侧写死，理由同 :data:`ROUTE_LOGINS`。
SMOKE_PROXY_IDS = (1, 4, 5)

#: 缺省参数下灌出来的账号总数（60 学生 + 3 教师）与其中**已绑定**的数。
#: ⚠️ 两个都是字面量：它们的 owner 是 :data:`boot.DEMO_STUDENTS` 与
#: :data:`boot.UNBOUND_LOGINS`，而本文件刻意抄一份当期望侧（抄了才有牙：
#: 改任何一侧而忘了另一侧，本条当场红）。
TOTAL_ACCOUNTS = 63
BOUND_ACCOUNTS = 61


def _guide_text() -> str:
    return GUIDE_MD.read_text(encoding="utf-8")


def _guide_section(no: int) -> str:
    """说明书第 ``no`` 节的正文（``## <no>.`` 到下一个 ``## `` 之前）。"""
    text = _guide_text()
    start = text.index(f"\n## {no}. ")
    rest = text[start + 1:]
    end = rest.find("\n## ")
    return rest if end < 0 else rest[:end]


def _guide_deliberate_logins() -> set[str]:
    """说明书里被点名为「**刻意**未绑定」的那些登录名（核心守卫的**文档侧**）。

    ⚠️ 判据是「同一行里同时出现 :data:`DELIBERATE_WORDS` 的两个词」，再从那一行里
    摘出全部反引号包着的学号/工号形状。⚠️ 它**刻意不认**别的行：说明书 §3 与 §4
    另外提到过 ``T0001`` / ``2023120001`` 一类账号，而那些行讲的是「用它走哪一条路线」，
    把它们拖进来会让本判据恒等于「说明书里出现过的全部登录名」—— 那就抓不到
    「常量改了、文档没改」了。
    """
    found: set[str] = set()
    for line in _guide_text().splitlines():
        if all(word in line for word in DELIBERATE_WORDS):
            found.update(LOGIN_SHAPE.findall(line))
    return found


def _seed(tmp: pathlib.Path, *extra: str) -> tuple[pathlib.Path, str]:
    """**真跑一次灌库器**（子进程，与 ``trial.ps1`` / ``demo.ps1`` 同一个入口）。

    ⚠️ 刻意用子进程而不是 ``boot.main()``：灌库器会写
    ``os.environ[PBKDF2_ITERATIONS_ENV_VAR]``（``[6/7]`` 的第一行），在测试进程里跑
    就是把一个全局状态留给后面几百条测试；子进程跑完那个状态跟着进程一起消失。
    （:func:`test_the_seeder_refuses_a_login_that_is_not_on_the_roster` 是唯一的例外，
    因为它要 monkeypatch 那个常量，故在进程内跑、并自己把环境变量登记给 monkeypatch。）

    返回 ``(库文件路径, stdout 全文)``。
    """
    db = tmp / "seeded.db"
    csv = tmp / "csv"
    url = "sqlite:///" + db.as_posix()
    proc = subprocess.run(
        [sys.executable, "scripts/demo_bootstrap.py", "--db-url", url,
         "--csv-dir", str(csv), *extra],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    return db, proc.stdout


def _accounts(db: pathlib.Path) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """从库里读回 ``(全部账号, password_hash IS NULL 的账号)``，两格都是 ``(kind, login)``。

    ⚠️ **被测侧**：它只认库里的事实，不认灌库器声称自己做了什么。
    """
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        everything = {("student", r[0]) for r in con.execute(
            "select student_no from student")} | {("teacher", r[0]) for r in con.execute(
            "select staff_no from teacher")}
        nulls = {("student", r[0]) for r in con.execute(
            "select student_no from student where password_hash is null")} | {
            ("teacher", r[0]) for r in con.execute(
                "select staff_no from teacher where password_hash is null")}
    finally:
        con.close()
    return everything, nulls


@pytest.fixture(scope="module")
def seeded(tmp_path_factory) -> tuple[pathlib.Path, str]:
    """**缺省参数**灌出来的一份库（模块级：本文件四条测试共用它，只灌一次）。"""
    return _seed(tmp_path_factory.mktemp("demo-seed"))


# ===========================================================================
# ① 核心守卫：说明书点名的那两个 == 灌库器常量里的那两个
# ===========================================================================


def test_the_guide_names_exactly_the_unbound_logins_of_the_seeder():
    """说明书里被点名为「刻意未绑定」的登录名，**恰好等于** :data:`boot.UNBOUND_LOGINS`。

    ⚠️ 两侧不同源：期望侧是灌库器的 Python 常量，被测侧是**文档文本**
    （:func:`_guide_deliberate_logins` 现场解析）。

    ⚠️⚠️ 这一条是台账 G23 那一句「留哪两个要写进说明书，否则下一个人以为灌库漏了」
    的**唯一**执行者。少了它，两档失效都是静默的：

    * 改了常量、忘了改说明书 ⇒ 甲方照着说明书去签发，得到 409
      ``password_already_bound``（而那一句报文说的是「它已经绑过了」，
      离真因「文档与库漂了」隔两层）；
    * 改了说明书、忘了改常量 ⇒ 甲方拿一个**已经绑好**的学号去签发，同样 409。

    ⚠️ 判据用**相等**（不是「常量 ⊆ 文档」）：包含关系抓不到「文档多写了一个」，
    而那正好是「下一个人以为灌库漏了」的反面 —— 他会去绑一个灌库器压根没留的账号。
    """
    named = _guide_deliberate_logins()
    declared = {login for _kind, login in boot.UNBOUND_LOGINS}
    assert named, (
        "说明书里一行「刻意 … 未绑定」都没扫到：那一句被删了，或换了措辞"
        f"（本判据认的两个词是 {DELIBERATE_WORDS}）⇒ 台账 G23 逐字要求的那一件事没了"
    )
    assert named == declared, (
        f"说明书点名的 {sorted(named)} ≠ 灌库器 UNBOUND_LOGINS 的 {sorted(declared)}："
        "两侧漂了。⚠️ 唯一所有者是 backend/scripts/demo_bootstrap.py 的 UNBOUND_LOGINS，"
        "改它就要**同时**改说明书（§3 账号表与 §4 路线三第 6 步）"
    )
    # ⚠️ 反空转的另一半：文档侧真的扫到了**两个**（一个学生 + 一个教师），
    #    而不是「同一条学号被数了两次」。少了这一拍，把 UNBOUND_LOGINS 改成
    #    只有一个学生也会绿（文档侧跟着只剩一个 ⇒ 相等成立）。
    kinds = {kind for kind, _login in boot.UNBOUND_LOGINS}
    assert kinds == {"student", "teacher"}, (
        f"UNBOUND_LOGINS 的 kind 集合是 {sorted(kinds)}，应为 ['student', 'teacher']："
        "绑定那一格两侧的验身材料形状不同（学生 =「学号 + 出生日期」、"
        "教师 =「工号 + 姓名」），而管理台那个页面上正是两个单选 ⇒ 只留一侧，"
        "另一侧在刚灌出来的库上仍然签发不出去（409）"
    )
    assert len(declared) == len(boot.UNBOUND_LOGINS) == 2, (
        f"登录名有重复，或个数不是 2（实测 {sorted(declared)}）"
    )


# ===========================================================================
# ② 真灌一份库：库里的事实
# ===========================================================================


def test_a_freshly_seeded_database_leaves_exactly_those_two_password_hashes_null(seeded):
    """**真灌**出来的库里，``password_hash IS NULL`` 的**恰好**是点名的那两个。

    ⚠️ 不用 mock：``_seed`` 起一个子进程跑 ``scripts/demo_bootstrap.py``
    （与 ``trial.ps1 -Reset`` / ``demo.ps1`` 逐字同一个入口），然后
    :func:`_accounts` 只读打开那个 ``.db`` 文件逐行数。

    ⚠️ 少了本条，「把 ``[6/7]`` 那两个 ``continue`` 的判据反过来」与
    「把 ``is_deliberately_unbound`` 的 ``kind`` 打错一个字」都是**绿的**：
    库会静默地退回「63 个全绑定」，而灌库器 ``[7/7]`` 那一格报的是症状、不是真因。
    """
    db, _out = seeded
    _everything, nulls = _accounts(db)
    assert nulls == set(boot.UNBOUND_LOGINS), (
        f"库里 password_hash IS NULL 的是 {sorted(nulls)}，"
        f"应为 {sorted(boot.UNBOUND_LOGINS)}"
    )


def test_every_other_account_in_a_freshly_seeded_database_is_bound(seeded):
    """上一条的**补集**：其余 61 个账号一律已绑定（两个数都是字面量）。

    ⚠️ 与 :func:`test_a_freshly_seeded_database_leaves_exactly_those_two_password_hashes_null`
    **互为冗余、而不是重复**：那一条只数 NULL 的那一侧，本条钉的是
    「总数 63 / 已绑定 61」这两个**绝对数**，于是「一个都没绑」与「绑了 62 个」
    两档都红（前一条对「一个都没绑」是绿的：NULL 集合会是 63 个 ≠ 2 个 ⇒ 也红，
    但对「多绑了一个、少留了一个」两档，只有本条能说出**差了几个**）。

    ⚠️ 期望侧与被测侧**不同源**：期望侧是 :data:`TOTAL_ACCOUNTS` /
    :data:`BOUND_ACCOUNTS` 两个字面量，被测侧是两条独立的 SQL
    （「全部账号」与「hash 非空的账号」），而「已绑定 == 全部 − 刻意留的那两个」
    这一格把常量也拉进来对账 ⇒ 三侧任一漂了都红。
    """
    db, _out = seeded
    everything, nulls = _accounts(db)
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        bound = {("student", r[0]) for r in con.execute(
            "select student_no from student where password_hash is not null")} | {
            ("teacher", r[0]) for r in con.execute(
                "select staff_no from teacher where password_hash is not null")}
    finally:
        con.close()
    assert len(everything) == TOTAL_ACCOUNTS, (
        f"账号总数是 {len(everything)}，应为 {TOTAL_ACCOUNTS}"
        f"（= --students 缺省 {boot.DEMO_STUDENTS} + 3 个工号）"
    )
    assert len(bound) == BOUND_ACCOUNTS, (
        f"已绑定 {len(bound)} 个，应为 {BOUND_ACCOUNTS}"
        f"（= {TOTAL_ACCOUNTS} − 刻意留的 {len(boot.UNBOUND_LOGINS)} 个）"
    )
    assert bound == everything - set(boot.UNBOUND_LOGINS), (
        "「已绑定的那一组」≠「全部账号 − UNBOUND_LOGINS」：有账号既不在刻意留的清单里、"
        "也没被绑上口令（那正是台账 G23 改前那一格的**反面**：一个静默登不进去的人）"
    )
    assert bound.isdisjoint(nulls) and bound | nulls == everything


def test_the_seeder_prints_the_two_it_left_unbound(seeded):
    """``[6/7]`` **真的把它们印出来**（附姓名，姓名从库里当场取）。

    ⚠️ 台账 G23 逐字要求「留哪两个要写进说明书，**否则下一个人以为灌库漏了**」。
    而说明书是**时点快照**、终端输出是**当场**的：换过 ``--seed`` 之后说明书里那一个
    学号背后是另一个人，而终端印的永远是真值 ⇒ 两处都要有，本条钉终端这一处。

    ⚠️ 也钉「它同时说了去哪走那一条路线」：光印两个账号，读的人仍然会以为是灌漏了。
    """
    _db, out = seeded
    assert "刻意" in out and "未绑定口令" in out, out[-2000:]
    for _kind, login in boot.UNBOUND_LOGINS:
        assert login in out, f"[6/7] 没有把 {login} 印出来：{out[-2000:]}"
    assert "一次性绑定令牌" in out, "[6/7] 没有说清那两个账号是用来干什么的"
    # ⚠️ 反空转：它印的是**已绑定**的那一批当登录例子（改前逐字写着「任何一个在册学号」，
    #    而 G23 之后那是假话），且例子里**不含**刻意留的那两个学号。
    #    ⚠️ 期望侧**刻意不抄**那个学号的字面量（唯一所有者是 UNBOUND_LOGINS）：
    #    本条要钉的是「印出来的例子来自已绑定的那一组」这个**性质**，不是某一个值。
    example_line = next(
        (line for line in out.splitlines() if "任何一个**已绑定**的在册学号" in line), None)
    assert example_line is not None, (
        "[6/7] 没有印「任何一个**已绑定**的在册学号」那一行：G23 之后「任何一个在册学号」"
        "是假话（有两个刻意没绑），故那一行必须写明是**已绑定**的那一批"
    )
    for kind, login in boot.UNBOUND_LOGINS:
        if kind == "student":
            assert login not in example_line, example_line
    # ⚠️ 缺省参数下**不该**出现「非缺省参数」那一句（它只在参数漂了时才印）
    assert "非缺省" not in out, out[-1500:]


# ===========================================================================
# ③ 判据函数：kind 与 login 都要对
# ===========================================================================


def test_is_deliberately_unbound_requires_both_the_kind_and_the_login():
    """:func:`boot.is_deliberately_unbound` 的 ``kind`` 与 ``login`` **都要对**。

    ⚠️ 交叉那两拍是本条的全部理由：把函数体从 ``(kind, login) in UNBOUND_LOGINS``
    改成 ``login in {l for _k, l in UNBOUND_LOGINS}``（只看 login）之后，
    「用学生的 ``kind`` 配教师的工号」会**静默地**成立 —— 而在 ``[6/7]`` 那两个循环里
    它不会多跳过谁（学号与工号不同域），于是失效要等到某一次重构把两个循环合成一个
    才浮现，而那时已经没人记得这一格。

    ⚠️ 打错一个字的 ``kind``（``"students"``）也要是 ``False``：它让 ``[6/7]``
    一个都跳不过，而 :func:`test_a_freshly_seeded_database_leaves_exactly_those_two_password_hashes_null`
    当场报警（两道互为冗余）。
    """
    assert boot.UNBOUND_LOGINS, "常量空了：本条会假绿"
    for kind, login in boot.UNBOUND_LOGINS:
        assert boot.is_deliberately_unbound(kind, login) is True, (kind, login)
        other = "teacher" if kind == "student" else "student"
        assert boot.is_deliberately_unbound(other, login) is False, (
            f"交叉成立了：({other!r}, {login!r}) 不该被认成刻意未绑定"
        )
        assert boot.is_deliberately_unbound(kind + "s", login) is False, (
            f"打错一个字的 kind 被放行了：({kind + 's'!r}, {login!r})"
        )
    # ⚠️ 已绑定的那些一律 False（含管理员：它要是被留成未绑定，
    #    管理台就没人能登进去签发令牌 ⇒ 那一条路线自己把自己锁死）
    assert boot.is_deliberately_unbound("teacher", "T0001") is False
    assert boot.is_deliberately_unbound("teacher", boot.DEMO_ADMIN_STAFF_NO) is False
    assert boot.is_deliberately_unbound("student", "2023120001") is False


# ===========================================================================
# ④ 那两条结构性约束 + 「不能是路线要登录的账号」
# ===========================================================================


def test_the_four_route_accounts_are_never_left_unbound():
    """说明书 §4 那四条路线**要登录**的四个账号，一个都不能被留成未绑定。

    ⚠️ 未绑定 ⇒ ``password_hash IS NULL`` ⇒ 登录是 403 ``password_not_bound``，
    故留错一个就是**把甲方的试用路线弄坏**（而那一句 403 说的是「不在名册上」，
    会把人支去查后端）。

    ⚠️ 两侧不同源：期望侧是 :data:`ROUTE_LOGINS`（本文件写死的字面量），
    被测侧是 :data:`boot.UNBOUND_LOGINS`；⚠️ 而第一拍另外核实那四个字面量**真的**
    出现在说明书 §4 里 —— 少了它，「说明书换了路线账号而本清单没跟着换」是静默的。
    """
    four = _guide_section(4)
    for login in ROUTE_LOGINS:
        assert login in four, (
            f"{login} 不在说明书 §4 里了：那四条路线换了账号，"
            f"而本文件的 ROUTE_LOGINS 是**期望侧**，要跟着换（否则本条会假绿）"
        )
    unbound = {login for _kind, login in boot.UNBOUND_LOGINS}
    assert unbound.isdisjoint(ROUTE_LOGINS), (
        f"UNBOUND_LOGINS 里有一个是试用路线要登录的账号：{sorted(unbound & set(ROUTE_LOGINS))}"
    )


def test_the_unbound_pair_keeps_the_constraints_that_make_it_safe(seeded):
    """那两条**结构性**约束与「教师那一侧不能是唯一的管理员」。

    ⚠️ 为什么这一格要真灌一份库来量（而不是读常量）：三个判据里有两个是**库的事实**，
    而它们会随 ``app/seed/population.py`` 的名册生成规则、``app/seed/sections.py`` 的
    发班规则漂 —— 漂了之后 ``UNBOUND_LOGINS`` 一个字都不用改就变坏，而症状是
    ``frontend/scripts/smoke.mjs`` 在离真因两层远的地方红（它按代理键登录、
    并在运行时**现找**一个学生去登录）。

    三拍：

    ① 那个学生的代理键**不在** ``smoke.mjs`` 硬登录的 ``(1, 4, 5)`` 里；
    ② 它**不在** ``T0001`` 本学期任教的名册里（``smoke.mjs`` 运行时现找的那几个
       恒落在这一族里：``SHARED.taughtStudent`` 与绿牌那一个）；
    ③ 教师那一侧**不是**唯一的管理员（:data:`boot.DEMO_ADMIN_STAFF_NO`）——
       管理台那一格「一次性绑定令牌」**仅管理员**可用，把管理员留成未绑定
       等于让那一条路线自己把自己锁死。

    ⚠️ 附带钉一格交付面的便利：那个学生在管理台学生列表的**第一页**
    （缺省按 ``id`` 升序、每页 20 行）就看得见，甲方不必翻页去凑一个学号。
    """
    db, _out = seeded
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        unbound_students = [r[0] for r in con.execute(
            "select student_no from student where password_hash is null")]
        unbound_teachers = [r[0] for r in con.execute(
            "select staff_no from teacher where password_hash is null")]
        assert len(unbound_students) == 1 and len(unbound_teachers) == 1, (
            unbound_students, unbound_teachers)
        sid, sname = con.execute(
            "select id, name from student where student_no = ?", (unbound_students[0],)
        ).fetchone()
        t1 = con.execute(
            "select id from teacher where staff_no = 'T0001'").fetchone()
        assert t1 is not None, "名册里没有 T0001：smoke.mjs 的教师档压根登不进去"
        mine = [r[0] for r in con.execute(
            "select id from course_section where teacher_id = ? and semester_id = "
            "(select id from semester where name = ?)", (t1[0], boot.DEMO_SEMESTER))]
        taught = {r[0] for r in con.execute(
            "select student_id from enrollment where course_section_id in (%s)"
            % ",".join("?" * len(mine)), mine)}
    finally:
        con.close()
    # ①
    assert sid not in SMOKE_PROXY_IDS, (
        f"未绑定的那个学生 id={sid}（{unbound_students[0]}）撞上了 smoke.mjs 硬登录的"
        f" {SMOKE_PROXY_IDS} 之一：那三拍会红在「学生 {sid} 能登录」上"
    )
    # ②
    assert sid not in taught, (
        f"未绑定的那个学生 id={sid}（{unbound_students[0]}）落在 T0001 本学期任教的"
        f" {len(taught)} 人里：smoke.mjs 运行时现找的那几个学生可能正是它，"
        "而那几拍会红在 403 password_not_bound 上（离真因两层远）"
    )
    # ③
    assert unbound_teachers[0] != boot.DEMO_ADMIN_STAFF_NO, (
        f"把唯一的管理员 {boot.DEMO_ADMIN_STAFF_NO} 留成未绑定：管理台那一格"
        "「一次性绑定令牌」仅管理员可用 ⇒ 那一条路线自己把自己锁死"
    )
    assert unbound_teachers[0] not in ROUTE_LOGINS, (unbound_teachers, ROUTE_LOGINS)
    # ⚠️ 交付面的便利格
    assert sid <= 20, (
        f"未绑定的那个学生 id={sid}（{sname}）不在管理台学生列表的第一页"
        "（缺省按 id 升序、每页 20 行）：甲方要翻页才找得到它"
    )


# ===========================================================================
# ⑤ 两道**响亮**：名册上找不到它 / 参数不是缺省值
# ===========================================================================


def test_the_seeder_refuses_a_login_that_is_not_on_the_roster(tmp_path, monkeypatch):
    """第一道：点名的登录名**不在刚灌出来的名册上** ⇒ ``SystemExit`` + 一句人话。

    ⚠️ 失效方向是**响亮**（控制者裁定）：不响的话，那两个 ``continue`` 一次都不命中，
    库会静默地退回「63 个全绑定」，而灌库器 ``[7/7]`` 那一格报的是症状
    （「库里未绑定的账号不是 UNBOUND_LOGINS 点名的那两个」），离真因隔一层。

    ⚠️ 本条是**唯一**一条在测试进程里直接调 :func:`boot.main` 的（它要 monkeypatch
    那个常量）。故它自己把 ``PBKDF2_ITERATIONS`` 登记给 monkeypatch：``main`` 会写
    ``os.environ``，不登记就是把一个全局状态留给后面几百条测试。
    ⚠️ 而它**跑得完**灌库的前五步才 ``SystemExit``（那一格在 ``[6/7]``），故本条
    用 ``--students 30``（能编班的最小规模）把耗时压下来。
    """
    monkeypatch.setenv("PBKDF2_ITERATIONS", os.environ.get("PBKDF2_ITERATIONS", "100000"))
    bogus = "2099999999"
    monkeypatch.setattr(boot, "UNBOUND_LOGINS", (("student", bogus),))
    db = tmp_path / "refused.db"
    with pytest.raises(SystemExit) as exc:
        boot.main([
            "--db-url", "sqlite:///" + db.as_posix(),
            "--csv-dir", str(tmp_path / "csv"),
            "--students", "30",
        ])
    message = str(exc.value)
    assert bogus in message, message
    assert "UNBOUND_LOGINS" in message, message
    assert "不在刚灌出来的名册上" in message, message
    # ⚠️ 反空转：它**确实**走到了 [6/7]（前五步都打印了），不是在前置守卫上就退了
    assert "名册" in message and "app/seed/population.py" in message, message


def test_the_seeder_says_out_loud_when_the_scale_arguments_are_not_the_defaults(tmp_path):
    """第三道：``--students`` / ``--seed`` 不是缺省值 ⇒ **打印一句人话**（不拒灌）。

    ⚠️ 这一格的裁定与六份库的实测逐字写在 :data:`boot.UNBOUND_LOGINS` 的注释末节：
    非缺省参数下**登录名那一半仍然成立**（实测 30 / 40 / 60 / 120 人 × seed
    20250828 / 999，那两个登录名一律仍在册 ⇒ 说明书点名的那一句不会变假），
    而**登录名背后那个人**（姓名 / 出生日期 / 代理键 / 在哪几个班）会静默地换掉。
    ⇒ 失效方向取「响亮地说清」而不是「拒灌」：``smoke.mjs`` 在非缺省参数下本来就
    跑不了（它钉着一整片绝对数），为一条已经死掉的路径拒灌一份**能用**的库
    是把方向搞反了。

    ⚠️ 两拍互为红绿（硬规矩 #50）：非缺省 ⇒ 那一句**在**；缺省 ⇒ 那一句**不在**
    （后半拍由 :func:`test_the_seeder_prints_the_two_it_left_unbound` 钉，
    它跑的是缺省参数那一份）。
    """
    _db, out = _seed(tmp_path, "--students", "30")
    assert "**非缺省**参数" in out, out[-2500:]
    assert f"--students=30（缺省 {boot.DEMO_STUDENTS}）" in out, out[-2500:]
    assert "背后那个人" in out and "smoke.mjs" in out, out[-2500:]
    # ⚠️ 而它**没有**因此少留：那两个登录名在非缺省参数下仍然在册、仍然未绑定
    _everything, nulls = _accounts(_db)
    assert nulls == set(boot.UNBOUND_LOGINS), sorted(nulls)


# ===========================================================================
# ⑥ 没有第二份口径：两个调用者都不抄那份清单
# ===========================================================================


def _ps1_files() -> list[pathlib.Path]:
    return sorted(
        path
        for root in ("scripts", pathlib.Path("backend") / "scripts")
        for path in (REPO_ROOT / root).glob("*.ps1")
    )


def _ps1_statements(text: str) -> str:
    """一个 ``.ps1`` 的**语句**（文件头那个 ``<# … #>`` 注释块与每一行 ``#`` 注释都剥掉）。

    ⚠️ 姿势逐字抄 ``tests/test_trial.py`` 的 :func:`_statements`（提及不是本身，
    硬规矩 #109）。⚠️ 它在本条里是承重的：``backend/scripts/demo.ps1`` 的注释里
    **刻意**留着终审 I1 那个病灶的原文（「例如 2025010004」，一个从来不在册的学号），
    那是**教训**、不是一份活清单 —— 按全文断的话，唯一的出路就是把那一句解释删掉。
    """
    body = text.split("#>", 1)[1] if "#>" in text else text
    return "\n".join(
        line for line in body.splitlines() if not line.lstrip().startswith("#")
    )


def test_no_ps1_becomes_a_second_owner_of_the_unbound_roster():
    """``trial.ps1`` 与 ``demo.ps1`` 走**同一个**灌库器，且**不抄第二份清单**。

    四拍：

    ① 两个调用者都真的调 ``scripts/demo_bootstrap.py``（⇒ 只有一份口径可改）；
    ② **任何** ``.ps1`` 的**语句**里都没有学号形状的字面量（⚠️ 注释里刻意提到的
       **历史反例**不算，逐字理由见 :func:`_ps1_statements`）。这一拍把
       ``tests/test_serve.py`` / ``test_trial.py`` / ``test_tunnel.py`` 各自只钉
       **自己那一个文件**的既有判据**扩到全部** ``.ps1``；
    ②b 而 :data:`boot.UNBOUND_LOGINS` 里那个学号**连注释都不许出现** ——
       它不是一个历史反例，它是一份**活**清单：一旦被抄进任何一个脚本，改常量的人
       就会漏改它，而漏改的那一处是**要念给甲方听的**那一处
       （工号 ``T0001``/``T0002``/``T0003`` 是**允许**的，逐字理由见
       ``tests/test_serve.py`` 的同名一条）；
    ③ 任何 ``.ps1`` 只要**说**了「某个账号是刻意未绑定的」，就必须**同时**点名
       唯一所有者 ``UNBOUND_LOGINS``（⇒ 它是在**指向**那份清单，不是在**抄**它）。
    """
    files = _ps1_files()
    assert len(files) >= 6, [p.name for p in files]
    texts = {p: p.read_bytes()[3:].decode("utf-8") for p in files}  # 剥 BOM

    # ①
    callers = [p for p, t in texts.items()
               if re.search(r"python scripts/demo_bootstrap\.py", t)]
    assert {p.name for p in callers} == {"trial.ps1", "demo.ps1"}, (
        f"调灌库器的脚本是 {[p.name for p in callers]}，应为 trial.ps1 与 demo.ps1"
    )
    # ②（⚠️ 反空转：它**确实**扫到了语句，而不是把整个文件都当注释剥光了）
    for path, text in texts.items():
        statements = _ps1_statements(text)
        assert len(statements) > 500, (path.name, len(statements))
        assert re.search(r"\b20\d{8}\b", statements) is None, (
            f"{path.name} 的**语句**里抄了一个学号形状的字面量：名册由 "
            "app/seed/population.py 现造，一个字面量会在改 --students / --seed 之后变假"
        )
    # ②b（⚠️ 全文，含注释）
    unbound_student_nos = [login for kind, login in boot.UNBOUND_LOGINS
                           if kind == "student"]
    assert unbound_student_nos, "UNBOUND_LOGINS 里没有学生那一侧：本拍会假绿"
    for path, text in texts.items():
        for login in unbound_student_nos:
            assert login not in text, (
                f"{path.name} 里抄了一份 {login!r}：它是 UNBOUND_LOGINS 的一份活清单，"
                "唯一所有者是 backend/scripts/demo_bootstrap.py（改常量的人会漏改这里，"
                "而漏改的那一处是要念给甲方听的）"
            )
    # ③
    for path, text in texts.items():
        for line in text.splitlines():
            if "刻意" in line and "未绑定" in line and "Write-Host" in line:
                assert "UNBOUND_LOGINS" in line or "demo_bootstrap" in line, (
                    f"{path.name} 里有一行对甲方**说**了「刻意未绑定」却没有点名唯一所有者："
                    f"{line.strip()[:160]}"
                )

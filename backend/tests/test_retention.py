"""留存清理的守卫（Plan 08 Task 2）：``scripts/retention.py`` + 两个 ``.ps1``。

派单 §2 第 7 条点名的六格逐条落地，另加它们挡不住的那几档：

========  ==============================================================  ==========================
派单        守卫                                                          它挡的失效形态
========  ==============================================================  ==========================
①          :func:`test_a_dry_run_deletes_not_a_single_row`                ``--dry-run`` 其实删了
②          :func:`test_a_real_run_deletes_exactly_what_it_announced`      实删与预告不符
③          :func:`test_an_unexpired_session_survives_while_an_expired_one_goes`
                                                                          把在线的人踢下线
④          :func:`test_the_row_exactly_on_the_window_boundary_is_kept`    边界那一行删不删没裁定
⑤/⑥        :func:`test_the_cutoff_comes_from_the_session_clock_owner_not_from_utcnow`
           + :func:`test_the_module_takes_no_second_clock`                时间口径差 8 小时
⑥          :func:`test_the_four_tables_are_pinned_to_the_spec_windows`    窗口被改（含 90 → 0）
           + :func:`test_a_zero_day_window_is_refused_loudly`             「误删一切」
========  ==============================================================  ==========================

⚠️ 另有七条不在派单清单里的守卫，各挡一个具体的洞：不许静默删（输出里四张表与两个数
都在）、不自动备份（那一段告示在、且 ``backend/backups/`` 一个文件都没多）、
写审计窗口不得低于一年、已吊销但未到期的会话不删、``--dry-run`` 不取写锁、
禁区（``backend/pe.db`` / ``backend/data/**``）、两个 ``.ps1`` 是 UTF-8 + BOM + CRLF、
注册脚本**只打印不注册**。

⚠️ **一律用 ``tmp_path`` 下的临时库**（照 ``tests/test_backup_restore.py`` 的姿势）：
两个真库的文件名不许出现在本文件**任何一个字符串字面量**里（含 docstring），
而 :func:`test_this_file_never_names_a_real_database` 把那一格按 AST 钉成可执行的。
"""
import ast
import datetime as dt
import importlib.util
import pathlib
import re
import sqlite3
import sys

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR
from app.db.models.audit import AuditLog, ReadAuditLog
from app.db.models.auth import LoginAttempt, UserSession
from app.db.session import init_db

#: ``backend/scripts/``。⚠️ 它**不是包**（没有 ``__init__.py``），故两个脚本按路径加载。
SCRIPTS_DIR = BACKEND_DIR / "scripts"


def _load(name: str):
    """按路径加载 ``backend/scripts/<name>.py``。

    ⚠️ **它同时把模块塞进 ``sys.modules``**：``retention.py`` 在模块体里
    ``from backup import …``，而 ``scripts/`` 不是包、也不在 ``sys.path`` 上
    （``retention.py`` 自己会无条件插一次，与 ``restore.py`` 同款兜底），
    故 ``backup`` 必须先在 ``sys.modules`` 里。⚠️ 加载顺序因此**承重**：
    先 ``backup``、后 ``retention``。姿势逐字同 ``tests/test_backup_restore.py``。
    """
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


backup = _load("backup")
retention = _load("retention")

#: 可注入的「现在」。**字面量**：它是全部期望值的锚（``moment`` 可注入的先例是
#: ``app.pipeline.daily.run_daily`` 的 ``now``），故它不得从被测代码那侧读回来。
MOMENT = dt.datetime(2026, 10, 17, 12, 0, 0)

#: ⚠️⚠️ **期望侧一律是字面量**（硬规矩 #35 两侧不同源）：下面这四行**不是**从
#: ``retention.SPECS`` 读出来的，故「把某个缺省窗口改掉」（派单 §2 第 7 条 ⑥ 的
#: 定点变异：90 → 0）与「把某张表的时间列换掉」都会当场红在
#: :func:`test_the_four_tables_are_pinned_to_the_spec_windows` 上。
#: 四个数的住址逐字见 ``scripts/retention.py`` 模块 docstring 那张表
#: （7 = ``app/db/models/auth.py``；30 = spec §15 B3；365 与 90 = spec §13.9.1）。
CASES = (
    ("session", "user_session", "expires_at", 7),
    ("login_attempt", "login_attempt", "at", 30),
    ("audit", "audit_log", "at", 365),
    ("read_audit", "read_audit_log", "at", 90),
)


def _url(path: pathlib.Path) -> str:
    return "sqlite:///" + path.as_posix()


@pytest.fixture()
def db(tmp_path) -> pathlib.Path:
    """一个**走迁移链**建出来的临时磁盘库（空的，四张表都在）。

    ⚠️ 走磁盘、不走内存：清理说的是**一个库文件**，而
    ``backup.db_path_from_url`` 对 ``sqlite://`` 那一档直接拒绝。
    ⚠️ 走 ``init_db`` 而不是 ``create_all``：于是这个库带着 ``alembic_version``，
    与甲方现场那一份同形。
    """
    path = tmp_path / "target.db"
    engine = create_engine(_url(path))
    init_db(engine)
    engine.dispose()
    return path


def _write(path: pathlib.Path, *rows) -> None:
    """往临时库里插若干行（一个 Session、一次 commit）。"""
    engine = create_engine(_url(path))
    with Session(engine) as session:
        for row in rows:
            session.add(row)
        session.commit()
    engine.dispose()


def _session_row(token: str, expires_at: dt.datetime, *, revoked_at=None) -> UserSession:
    """一行会话。⚠️ 判据锚在 ``expires_at`` 上，故其余三个时刻列取什么都行 ——
    而**取一个明显不同的值**是有意的：若有人把清理判据换到 ``created_at`` 或
    ``last_seen_at`` 上，:func:`test_an_unexpired_session_survives_while_an_expired_one_goes`
    会给出一个错的答案（那两列在这里都被刻意设成「很久以前」）。"""
    return UserSession(
        id=token, kind="teacher", subject_id=1, role="teacher",
        created_at=dt.datetime(2020, 1, 1), expires_at=expires_at,
        last_seen_at=dt.datetime(2020, 1, 1), revoked_at=revoked_at,
    )


def _login_row(at: dt.datetime, *, login: str = "T0001", ok: bool = False) -> LoginAttempt:
    return LoginAttempt(kind="teacher", login=login, ok=ok, at=at, ip="127.0.0.1")


def _audit_row(at: dt.datetime, *, path: str = "/api/students/4", status: int = 200) -> AuditLog:
    return AuditLog(
        at=at, subject_kind="teacher", subject_id=1, staff_no="T0001",
        method="PATCH", path=path, status=status, target="4",
    )


def _read_audit_row(
    at: dt.datetime, *, route: str = "/api/students/{student_id}", student_id=4
) -> ReadAuditLog:
    return ReadAuditLog(
        at=at, subject_kind="teacher", subject_id=None, staff_no="T0001",
        route=route, student_id=student_id, status=200, target="4",
    )


def _counts(path: pathlib.Path) -> dict[str, int]:
    """四张表**各自**的行数 —— ⚠️ 走一条**独立的** ``sqlite3`` 连接（不是被测代码的
    引擎），于是「其实删了 / 其实没删」这件事由**第二个**读者证实。"""
    connection = sqlite3.connect(str(path))
    try:
        return {
            table: connection.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
            for table in ("user_session", "login_attempt", "audit_log", "read_audit_log")
        }
    finally:
        connection.close()


def _by_key(results) -> dict[str, object]:
    return {result.spec.key: result for result in results}


# ===========================================================================
# ① ``--dry-run``：一行都不删（派单点名的**命门**）
# ===========================================================================


def test_a_dry_run_deletes_not_a_single_row(db):
    """``dry_run=True`` 之下四张表**一行都不少**，而预告的数是真的数出来了。

    ⚠️ 三拍（红绿两档都在场，硬规矩 #50）：
    ① 每张表的 ``deleted`` 恒 0；② 四张表的行数与进来时**逐字相同**
    （由 :func:`_counts` 那条独立连接复核，不是读被测代码的返回值）；
    ③ **反空转**：``predicted`` 不是 0 —— 少了这一拍，「一张空库上的 dry-run」
    与「一个真的没删的 dry-run」在断言上不可分辨。
    """
    old = MOMENT - dt.timedelta(days=400)
    fresh = MOMENT - dt.timedelta(minutes=5)
    _write(
        db,
        _session_row("expired-token", MOMENT - dt.timedelta(days=8)),
        _session_row("live-token", MOMENT + dt.timedelta(hours=2)),
        _login_row(old), _login_row(fresh),
        _audit_row(old), _audit_row(fresh),
        _read_audit_row(old), _read_audit_row(fresh),
    )
    before = _counts(db)

    results = retention.clean(_url(db), dry_run=True, moment=MOMENT, emit=lambda _line: None)

    got = _by_key(results)
    # ① 一行都没删
    assert {key: result.deleted for key, result in got.items()} == {
        "session": 0, "login_attempt": 0, "audit": 0, "read_audit": 0,
    }
    # ② 行数逐字相同（第二个读者）
    assert _counts(db) == before == {
        "user_session": 2, "login_attempt": 2, "audit_log": 2, "read_audit_log": 2,
    }
    # ③ 反空转：预告真的数出了旧行（会话那一格只有一行过期，另一行还在有效期里）
    assert {key: result.predicted for key, result in got.items()} == {
        "session": 1, "login_attempt": 1, "audit": 1, "read_audit": 1,
    }


def test_a_dry_run_succeeds_while_another_connection_holds_the_write_lock(db):
    """``--dry-run`` **不取写锁**：另一个连接握着 ``BEGIN IMMEDIATE`` 时它照样跑完。

    ⚠️ 这一格是承重的运维性质：清理会在**甲方服务正在跑**的时候被手工探查一次
    （``--dry-run`` 就是为那一档准备的），而一次只读的探查若也去抢写锁，
    它会卡住 5 秒（``sqlite3`` 的缺省 ``timeout``）然后失败 —— 于是运维得到的
    答案是「数据库被锁」而不是「将删多少行」。
    ⚠️ 而**真删那一档刻意相反**（它必须取写锁，逐字理由见
    ``retention._engine`` 的 docstring：不取锁的话「预告」与「实删」之间
    可以插进一次 ``clear_failures``，对账就会假红）。
    """
    _write(db, _login_row(MOMENT - dt.timedelta(days=400)))
    holder = sqlite3.connect(str(db), isolation_level=None)
    try:
        holder.execute("BEGIN IMMEDIATE")
        results = retention.clean(
            _url(db), dry_run=True, moment=MOMENT, emit=lambda _line: None
        )
        assert [result.predicted for result in results] == [0, 1, 0, 0]
        assert [result.deleted for result in results] == [0, 0, 0, 0]
        holder.execute("ROLLBACK")
    finally:
        holder.close()


def test_the_engine_takes_the_write_lock_only_for_a_real_run(db, monkeypatch):
    """``immediate`` 那一格**只**在真删时打开（:func:`retention._engine` 的入参）。

    ⚠️ 它是上一条的**结构侧配套**：上一条证的是「dry-run 跑得过」，本条证的是
    「真删那一档确实要了写锁」。少了本条，把 ``immediate=not dry_run`` 写成
    ``immediate=False``（于是对账在有并发写者时会假红）不会让任何一条守卫变红。
    """
    seen: list[bool] = []
    real = retention._engine

    def spy(db_url: str, *, immediate: bool):
        seen.append(immediate)
        return real(db_url, immediate=immediate)

    monkeypatch.setattr(retention, "_engine", spy)
    retention.clean(_url(db), dry_run=True, moment=MOMENT, emit=lambda _line: None)
    retention.clean(_url(db), dry_run=False, moment=MOMENT, emit=lambda _line: None)
    assert seen == [False, True]


# ===========================================================================
# ② 预告 → 删 → 复核
# ===========================================================================


def test_a_real_run_deletes_exactly_what_it_announced(db):
    """实删行数与预告**逐字相符**，且删掉的正是那一批旧行、新行一行没动。

    ⚠️ 三面各自独立：``predicted``（删之前的 ``COUNT``）、``deleted``
    （``DELETE`` 的 ``rowcount``）、:func:`_counts`（**第三条连接**读回来的行数）。
    三面相符才叫「复核过」。
    """
    old = MOMENT - dt.timedelta(days=400)
    fresh = MOMENT - dt.timedelta(minutes=5)
    _write(
        db,
        _session_row("expired-1", MOMENT - dt.timedelta(days=8)),
        _session_row("expired-2", MOMENT - dt.timedelta(days=30)),
        _session_row("live", MOMENT + dt.timedelta(hours=2)),
        _login_row(old), _login_row(old, login="2023120001"), _login_row(fresh),
        _audit_row(old), _audit_row(fresh),
        _read_audit_row(old), _read_audit_row(old, student_id=None),
    )
    results = retention.clean(_url(db), moment=MOMENT, emit=lambda _line: None)
    got = _by_key(results)

    assert {key: (r.predicted, r.deleted) for key, r in got.items()} == {
        "session": (2, 2), "login_attempt": (2, 2), "audit": (1, 1), "read_audit": (2, 2),
    }
    # 复核那一格：删完之后**没有**任何一行仍满足判据
    assert {key: r.remaining for key, r in got.items()} == {
        "session": 0, "login_attempt": 0, "audit": 0, "read_audit": 0,
    }
    assert _counts(db) == {
        "user_session": 1, "login_attempt": 1, "audit_log": 1, "read_audit_log": 0,
    }
    # ⚠️ 而**留下来的**正是那几行新的（不是「删对了行数、删错了行」）
    engine = create_engine(_url(db))
    with Session(engine) as session:
        assert [row.id for row in session.scalars(select(UserSession))] == ["live"]
        assert [row.login for row in session.scalars(select(LoginAttempt))] == ["T0001"]
        assert [row.path for row in session.scalars(select(AuditLog))] == ["/api/students/4"]
    engine.dispose()


def test_the_announced_and_deleted_counts_are_both_in_the_output(db, capsys):
    """**不许静默删**：输出里四张表各占一行、预告与实删**两个数都在**。

    ⚠️ 派单对「静默」的定义逐字是「没有输出、或输出里看不出删了哪张表多少行」，
    故本条钉的是**控制台**（不是返回值）：四张表的名字、两个合计、以及那句
    「预告 N == 实删 N」都必须在。
    """
    old = MOMENT - dt.timedelta(days=400)
    _write(db, _login_row(old), _login_row(old), _audit_row(old), _read_audit_row(old))
    retention.clean(_url(db), moment=MOMENT)
    out = capsys.readouterr().out

    for table in ("user_session", "login_attempt", "audit_log", "read_audit_log"):
        assert table in out, (table, out)
    # ⚠️ 字面量 4 = 2 条 login_attempt + 1 条 audit_log + 1 条 read_audit_log
    assert "合计：将删 4 行" in out, out
    assert "合计：预告 4 == 实删 4 ✓" in out, out
    assert "复核：四张表上「仍满足判据的行」合计 0" in out, out
    # ⚠️ 反空转：那一档「一行都没删」的措辞**不得**出现在真删的输出里
    assert "一行都没删" not in out, out


def test_a_count_mismatch_rolls_the_whole_batch_back(db, monkeypatch):
    """对账失败 ⇒ **四张表全部回滚**（一行都没删）+ 一句指认真因的人话。

    ⚠️ 它用 monkeypatch 造出「实删与预告不符」那一档（把其中一次 ``DELETE`` 的
    ``rowcount`` 谎报成 99），因为真实世界里这一格**不该**发生
    （``BEGIN IMMEDIATE`` 把临界区焊死了）—— 而正因为它不该发生，
    「发生了会怎样」必须有证据，不能靠推断（硬规矩 #89）。
    """
    old = MOMENT - dt.timedelta(days=400)
    _write(db, _login_row(old), _audit_row(old), _read_audit_row(old))
    before = _counts(db)

    # ⚠️ 造出「预告 != 实删」那一档的办法是让**预告**说谎（把 login_attempt 的
    #    COUNT 多报 1）。真实的失效形态是「判据在两处不一致」，而它与本处造的
    #    在**对账那一段看来完全相同** —— 本条钉的是对账，不是造因。
    real_count = retention._count_matching

    def lying_count(conn, spec, cutoff):
        found = real_count(conn, spec, cutoff)
        return found + 1 if spec.key == "login_attempt" else found

    monkeypatch.setattr(retention, "_count_matching", lying_count)
    with pytest.raises(retention.RetentionError) as excinfo:
        retention.clean(_url(db), moment=MOMENT, emit=lambda _line: None)

    assert "不符" in str(excinfo.value), str(excinfo.value)
    assert "全部回滚" in str(excinfo.value), str(excinfo.value)
    # ⚠️ 承重的一拍：三张表里**已经删掉的**那些行也回来了
    assert _counts(db) == before == {
        "user_session": 0, "login_attempt": 1, "audit_log": 1, "read_audit_log": 1,
    }


# ===========================================================================
# ③ 未过期的会话不被删（两行样本、两侧不同源）
# ===========================================================================


def test_an_unexpired_session_survives_while_an_expired_one_goes(db):
    """一个**已过期** + 一个**未过期**：前者删、后者留。

    ⚠️ 派单 §2 第 7 条 ③ 逐字要求「两行样本、两侧不同源」：期望侧是**字面量**
    算出来的两个时刻，被测侧是 ``retention.clean`` 自己的判据 —— 两者不共用任何一个函数。
    ⚠️ 定点变异「把未过期会话的判据反过来」（``<`` → ``>``）会当场红在本条上
    （它会删掉活着的那一行、留下过期的那一行）。

    ⚠️⚠️ **「已过期」那一行必须过期得比窗口更久**：判据是 ``expires_at < now − 7 天``，
    故一个「一秒前刚过期」的会话**不在**这一批里（它还要在库里留满 7 天，
    那 7 天是「这个人上周登过」这一格事后线索的留存期，逐字理由见
    ``retention.DEFAULT_SESSION_DAYS``）。本条因此取 ``MOMENT − 7 天 − 1 秒``。
    """
    _write(
        db,
        _session_row("expired", MOMENT - dt.timedelta(days=7, seconds=1)),
        _session_row("live", MOMENT + dt.timedelta(hours=2)),
    )
    results = retention.clean(_url(db), moment=MOMENT, emit=lambda _line: None)
    assert _by_key(results)["session"].deleted == 1

    engine = create_engine(_url(db))
    with Session(engine) as session:
        assert [row.id for row in session.scalars(select(UserSession))] == ["live"]
    engine.dispose()


def test_a_live_session_survives_even_a_zero_length_window_is_refused_not_destructive(db):
    """⚠️ **结构性**性质：判据锚在 ``expires_at`` 上 ⇒ 一个活着的会话对**任何**被接受的
    窗口都删不到（连下界 ``1`` 天都删不到它，因为它的 ``expires_at`` 在未来）。

    这一格是「把人踢下线」这个失效方向的**第二道**证据：第一道是上一条的两行样本，
    本条问的是「窗口取到允许的最小值时还成不成立」。
    """
    _write(db, _session_row("live", MOMENT + dt.timedelta(hours=2)))
    results = retention.clean(
        _url(db), days={"session": 1}, moment=MOMENT, emit=lambda _line: None
    )
    assert _by_key(results)["session"].deleted == 0
    assert _counts(db)["user_session"] == 1


def test_a_revoked_but_unexpired_session_is_kept(db):
    """**已吊销**（``revoked_at`` 非空）但还没到期的会话**不删**。

    ⚠️ 这是一条**裁定**（逐字理由见 ``retention.TableSpec`` 的 docstring）：
    ``app.auth.sessions.revoke`` 的整个立意是「登出 = 写一列、**不删行**」，
    好让「被偷的 cookie 在登出后失效」可追溯；清理任务立刻把最新的那一条登出痕迹
    删掉等于抹掉它。⚠️ 而它有界（最多再活一个 ``SESSION_TTL`` = 2 小时就落进判据），
    故不需要第二个判据。
    """
    _write(
        db,
        _session_row("revoked-fresh", MOMENT + dt.timedelta(hours=1), revoked_at=MOMENT),
        _session_row("revoked-old", MOMENT - dt.timedelta(days=9), revoked_at=MOMENT - dt.timedelta(days=9)),
    )
    results = retention.clean(_url(db), moment=MOMENT, emit=lambda _line: None)
    assert _by_key(results)["session"].deleted == 1

    engine = create_engine(_url(db))
    with Session(engine) as session:
        assert [row.id for row in session.scalars(select(UserSession))] == ["revoked-fresh"]
    engine.dispose()


# ===========================================================================
# ④ 窗口边界
# ===========================================================================


def test_the_row_exactly_on_the_window_boundary_is_kept(db):
    """**恰好等于**截止时刻的那一行**不删**（判据是严格 ``<``），早一微秒的那一行删。

    ⚠️ 派单 §2 第 7 条 ④ 要求「要有裁定并被钉住」：裁定是**严格小于**
    （两条理由逐字见 ``retention._predicate`` 的 docstring：spec 两处已写下的算式
    都是 ``<``；而它是**保守**的那一侧 —— 边界那一行留下来最坏是多留一行）。
    ⚠️ 定点变异（``<`` → ``<=``）会当场红在本条上。
    """
    cutoff = MOMENT - dt.timedelta(days=30)
    _write(
        db,
        _login_row(cutoff, login="boundary"),
        _login_row(cutoff - dt.timedelta(microseconds=1), login="one-microsecond-older"),
        _login_row(cutoff + dt.timedelta(microseconds=1), login="one-microsecond-newer"),
    )
    results = retention.clean(
        _url(db), days={"login_attempt": 30}, moment=MOMENT, emit=lambda _line: None
    )
    assert _by_key(results)["login_attempt"].deleted == 1

    engine = create_engine(_url(db))
    with Session(engine) as session:
        assert sorted(row.login for row in session.scalars(select(LoginAttempt))) == [
            "boundary", "one-microsecond-newer",
        ]
    engine.dispose()


# ===========================================================================
# ⑤/⑥ 四张表的判据 + 缺省窗口（定点变异「90 → 0」红在这里）
# ===========================================================================


def test_the_four_tables_are_pinned_to_the_spec_windows():
    """四张表 × 四格（``key`` / 表名 / **时间列** / **缺省窗口**）逐字钉住。

    ⚠️ 期望侧是 :data:`CASES` 那四行**字面量**（两侧不同源）：
    「把 90 改成 0」（派单 §2 第 7 条 ⑥ 的第三格定点变异）、「把 ``audit_log`` 的
    判据从 ``at`` 换到别的列」、「漏掉一张表」三种改动都会红在这里。
    """
    assert [
        (spec.key, spec.table, spec.column_name, spec.default_days)
        for spec in retention.SPECS
    ] == list(CASES)
    # ⚠️ 四个常量另钉一次（它们是缺省值的**单一所有者**，而 :data:`CASES` 是它的复述）
    assert retention.DEFAULT_SESSION_DAYS == 7
    assert retention.DEFAULT_LOGIN_ATTEMPT_DAYS == 30
    assert retention.DEFAULT_AUDIT_DAYS == 365
    assert retention.DEFAULT_READ_AUDIT_DAYS == 90
    # ⚠️ 下界两格
    assert retention.MIN_DAYS == 1
    assert retention.AUDIT_MIN_DAYS == 365
    # ⚠️ 写审计那一格的下界**就是** 365（spec §13.9.1「不少于 1 年」）
    assert {spec.key: spec.min_days for spec in retention.SPECS} == {
        "session": 1, "login_attempt": 1, "audit": 365, "read_audit": 1,
    }
    # ⚠️ 环境变量名（派单 §2 第 3 条：每个窗口都要能由命令行/环境变量覆盖）
    assert [spec.env_var for spec in retention.SPECS] == [
        "PE_RETENTION_SESSION_DAYS",
        "PE_RETENTION_LOGIN_ATTEMPT_DAYS",
        "PE_RETENTION_AUDIT_DAYS",
        "PE_RETENTION_READ_AUDIT_DAYS",
    ]


@pytest.mark.parametrize("key,table,column,days", CASES)
def test_each_table_uses_its_own_column_and_its_own_default_window(db, key, table, column, days):
    """逐表一条**行为**守卫：窗口内那一行留、窗口外那一行删（缺省值、不传 ``days``）。

    ⚠️ 这一条同时钉住三件事：① 判据用的是**这一张表**的时间列
    （``column`` 那一格是字面量，换列就红）；② 缺省窗口真的是 ``days`` 天
    （传 ``days ± 1`` 两行，落在窗口两侧）；③ 缺省值**不需要**调用方传
    （本条一个 ``days=`` 都不传）。
    """
    older = MOMENT - dt.timedelta(days=days + 1)
    newer = MOMENT - dt.timedelta(days=days - 1)
    if key == "session":
        # ⚠️ 会话那一格的列是 ``expires_at``，故「窗口外」= 早就过期了
        rows = [_session_row("old", older), _session_row("new", newer)]
    elif key == "login_attempt":
        rows = [_login_row(older, login="old"), _login_row(newer, login="new")]
    elif key == "audit":
        rows = [_audit_row(older, path="/old"), _audit_row(newer, path="/new")]
    else:
        rows = [_read_audit_row(older, route="/old"), _read_audit_row(newer, route="/new")]
    _write(db, *rows)

    results = retention.clean(_url(db), moment=MOMENT, emit=lambda _line: None)
    result = _by_key(results)[key]
    assert (result.days, result.predicted, result.deleted, result.remaining) == (days, 1, 1, 0)
    assert _counts(db)[table] == 1


def test_a_zero_day_window_is_refused_loudly(db):
    """``0`` 天的窗口被**拒**（一句人话 + 一行都没删），而不是「把表清空」。

    ⚠️ 派单 §2 第 7 条 ⑥ 逐字点名这一格是「**误删一切**的形状，必须有拍挡住」。
    ⚠️ 三拍：① 抛 :class:`retention.RetentionError`；② 报错文本里点名了「全部删掉」
    与下界；③ **库里一行都没少**（拒绝发生在任何一条语句之前）。
    """
    _write(db, _login_row(MOMENT - dt.timedelta(minutes=1)), _audit_row(MOMENT))
    before = _counts(db)
    with pytest.raises(retention.RetentionError) as excinfo:
        retention.clean(
            _url(db), days={"login_attempt": 0}, moment=MOMENT, emit=lambda _line: None
        )
    message = str(excinfo.value)
    assert "下界是 1 天" in message, message
    assert "全部**删掉" in message, message
    assert _counts(db) == before == {
        "user_session": 0, "login_attempt": 1, "audit_log": 1, "read_audit_log": 0,
    }


def test_the_write_audit_window_cannot_go_below_one_year(db):
    """``audit_log`` 的窗口**不得低于 365 天**（spec §13.9.1 逐字「不少于 1 年」）。

    ⚠️ 三拍：① 364 天被拒；② 报错文本指着 spec 那一句（不是「本模块规定的」）；
    ③ **365 天被接受**（下界是「不少于」，不是「多于」）。
    """
    _write(db, _audit_row(MOMENT - dt.timedelta(days=400)))
    with pytest.raises(retention.RetentionError) as excinfo:
        retention.clean(_url(db), days={"audit": 364}, moment=MOMENT, emit=lambda _line: None)
    assert "不少于 1 年" in str(excinfo.value), str(excinfo.value)
    assert _counts(db)["audit_log"] == 1

    results = retention.clean(
        _url(db), days={"audit": 365}, moment=MOMENT, emit=lambda _line: None
    )
    assert _by_key(results)["audit"].deleted == 1


def test_a_negative_window_is_refused_too(db):
    """负数窗口同样被拒（``--audit-days -1`` 是 argparse 会放行的一档）。"""
    with pytest.raises(retention.RetentionError):
        retention.clean(_url(db), days={"read_audit": -1}, moment=MOMENT, emit=lambda _line: None)


def test_an_unparsable_env_var_is_refused_loudly(db, monkeypatch):
    """坏的环境变量值 → 一句人话（不是 ``ValueError`` 的裸栈）。

    ⚠️ 空字符串按「没设」处理（``$env:X = ""`` 在 PowerShell 里是「设了一个空值」），
    口径与 ``app/auth/policy.py`` 的 ``_int_from_env`` 逐字相同。
    """
    monkeypatch.setenv("PE_RETENTION_READ_AUDIT_DAYS", "九十")
    with pytest.raises(retention.RetentionError) as excinfo:
        retention.clean(_url(db), moment=MOMENT, emit=lambda _line: None)
    assert "PE_RETENTION_READ_AUDIT_DAYS" in str(excinfo.value)

    monkeypatch.setenv("PE_RETENTION_READ_AUDIT_DAYS", "")
    _write(db, _read_audit_row(MOMENT - dt.timedelta(days=91)))
    results = retention.clean(_url(db), moment=MOMENT, emit=lambda _line: None)
    assert _by_key(results)["read_audit"].days == 90


def test_the_env_var_overrides_the_default_and_the_flag_overrides_the_env(db, monkeypatch):
    """优先级：**CLI 实参 > 环境变量 > 缺省值**（派单 §2 第 3 条）。"""
    monkeypatch.setenv("PE_RETENTION_SESSION_DAYS", "3")
    assert retention.resolve_days(retention.SPECS[0]) == 3
    assert retention.resolve_days(retention.SPECS[0], 11) == 11
    monkeypatch.delenv("PE_RETENTION_SESSION_DAYS")
    assert retention.resolve_days(retention.SPECS[0]) == 7


# ===========================================================================
# ⑤ 时间口径：naive **本地**时刻，唯一所有者 app.auth.sessions.now
# ===========================================================================


def test_the_cutoff_comes_from_the_session_clock_owner_not_from_utcnow(db, monkeypatch):
    """截止时刻由 :func:`app.auth.sessions.now` 给出，**不是** ``utcnow()``。

    ⚠️ 这一条的判据是**可观测的**（不是「读代码看见它调了 now()」）：把那个所有者
    monkeypatch 成一个**未来**的时刻（2030-01-01），于是「按真实时钟还只有 0 天大」
    的那一行 ``audit_log``（``MOMENT``，即 2026-10-17）在 365 天的窗口下**该被删**。
    ⚠️ 一个用 ``datetime.utcnow()`` 当「现在」的实现给出的截止时刻是**真实的**今天
    减一年（2025-10-17），那一行于是**活下来** ⇒ 本条当场红。
    ⚠️ 定点变异（把 ``sessions.now()`` 换成 ``dt.datetime.utcnow()``）因此有拍挡着。
    """
    _write(db, _audit_row(MOMENT))
    monkeypatch.setattr(retention.sessions, "now", lambda: dt.datetime(2030, 1, 1))
    results = retention.clean(_url(db), emit=lambda _line: None)
    result = _by_key(results)["audit"]
    assert result.cutoff == dt.datetime(2029, 1, 1), result.cutoff
    assert result.deleted == 1
    assert _counts(db)["audit_log"] == 0


def test_the_module_takes_no_second_clock():
    """**源码级**：本模块里出现的每一次「取时钟」都是 ``sessions.now``。

    ⚠️ 用 **AST** 而不是字面量扫描：模块 docstring 里逐字**提及**了
    ``datetime.utcnow()``（它在解释为什么不能用它），而提及不是本身（硬规矩 #109）。
    ⚠️ 两拍：① 全部「取时钟」的调用**恰好**是 ``sessions.now``；
    ② **反空转** —— 它至少出现一次（否则 ① 会恒真）。
    """
    tree = ast.parse((SCRIPTS_DIR / "retention.py").read_text(encoding="utf-8"))
    clocks = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in ("now", "utcnow", "today", "fromtimestamp")
        and (
            ast.unparse(node.func.value).endswith(("datetime", "date", "sessions", "time"))
        )
    ]
    assert clocks, "一条取时钟的调用都没扫到 —— 判据写错了，本条空转"
    assert set(clocks) == {"sessions.now"}, clocks


def test_an_aware_moment_is_refused(db):
    """注入一个 **aware** 的 ``moment`` 被拒：四张表的列是 naive 本地时刻，
    而 aware 与 naive 的比较在 SQLite 上会**静默**按字符串比出错误答案。"""
    with pytest.raises(retention.RetentionError) as excinfo:
        retention.clean(
            _url(db),
            moment=dt.datetime(2026, 10, 17, tzinfo=dt.timezone.utc),
            emit=lambda _line: None,
        )
    assert "naive" in str(excinfo.value)


# ===========================================================================
# 不自动备份（派单 §2 第 4 条那个开放问题的裁定）
# ===========================================================================


def test_a_real_run_prints_the_loud_notice_and_makes_no_backup(db, capsys):
    """真删那一档打印那段**响亮的告示**，而 ``backend/backups/`` 一个文件都没多。

    ⚠️ 两面都要：告示是「运维看得见的提示」，而「一个文件都没多」才是
    「它真的没有自动备份」的证据 —— 少了后半拍，一个「打印了告示却照样备份」的
    实现会让本条恒绿。
    """
    _write(db, _login_row(MOMENT - dt.timedelta(days=400)))
    before = sorted(path.name for path in backup.BACKUPS_DIR.glob("*")) if backup.BACKUPS_DIR.is_dir() else []

    retention.clean(_url(db), moment=MOMENT)
    out = capsys.readouterr().out

    assert "不会**自动备份" in out, out
    assert "backup.ps1" in out, out
    assert "明文" in out, out
    after = sorted(path.name for path in backup.BACKUPS_DIR.glob("*")) if backup.BACKUPS_DIR.is_dir() else []
    assert after == before, (before, after)


def test_a_dry_run_does_not_print_the_destructive_notice(db, capsys):
    """``--dry-run`` 那一档**不**打印「下面这一步不可撤销」——它确实不删。"""
    retention.clean(_url(db), dry_run=True, moment=MOMENT)
    out = capsys.readouterr().out
    assert "DRY-RUN：**一行都没删**" in out, out
    assert "不可撤销" not in out, out


# ===========================================================================
# 禁区与库路径（复用 backup.py 的那一个所有者）
# ===========================================================================


def test_the_forbidden_paths_are_refused():
    """``backend/pe.db`` 与 ``backend/data/**`` 一律拒（复用 ``backup._ensure_not_forbidden``）。

    ⚠️ 本条**不写第二道禁区守卫**：它证的是 ``retention`` 走的是 ``backup`` 那一个
    所有者（``resolve_db_path``），故那两个禁区对本 CLI 同样成立。
    """
    with pytest.raises(backup.BackupError):
        retention.resolve_db_path("sqlite:///" + (BACKEND_DIR / "pe.db").as_posix())
    with pytest.raises(backup.BackupError):
        retention.resolve_db_path(
            "sqlite:///" + (BACKEND_DIR / "data" / "whatever.db").as_posix()
        )


def test_main_refuses_a_db_that_does_not_exist(tmp_path, capsys):
    """库文件不存在 → 退出码 **2** + 一句人话。

    ⚠️ 承重的一格：SQLite 对「打开一个不存在的文件」的缺省行为是**建一个空库**，
    于是「路径写错了」会静默变成一次「四张表都是 0 行、什么都没删」的**成功**运行
    —— 而运维会把它读成「今天没有过期行」。
    """
    missing = tmp_path / "nope.db"
    with pytest.raises(SystemExit) as excinfo:
        _main(["--db-url", "sqlite:///" + missing.as_posix(), "--dry-run"])
    assert excinfo.value.code == 2
    assert "不存在" in capsys.readouterr().err


def test_main_dry_run_prints_the_resolved_db_path(tmp_path, capsys, monkeypatch):
    """``main()`` 的缺省库路径与 ``backup`` **同源**（``PE_DB_URL``），且 ``--dry-run`` 透传。"""
    path = tmp_path / "from-env.db"
    engine = create_engine("sqlite:///" + path.as_posix())
    init_db(engine)
    engine.dispose()
    monkeypatch.setenv("PE_DB_URL", "sqlite:///" + path.as_posix())

    assert _main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert str(path) in out, out
    assert "DRY-RUN" in out, out


def test_main_passes_the_four_window_flags_through(tmp_path, capsys):
    """四个 ``--<表>-days`` 旗标真的到了判据上（输出里打印的就是这四个数）。"""
    path = tmp_path / "flags.db"
    engine = create_engine("sqlite:///" + path.as_posix())
    init_db(engine)
    engine.dispose()

    code = _main([
        "--db-url", "sqlite:///" + path.as_posix(), "--dry-run",
        "--session-days", "9", "--login-attempt-days", "31",
        "--audit-days", "730", "--read-audit-days", "91",
    ])
    assert code == 0
    out = capsys.readouterr().out
    for needle in ("9 天", "31 天", "730 天", "91 天"):
        assert needle in out, (needle, out)


def test_main_refuses_a_window_below_the_floor(tmp_path, capsys):
    """CLI 那一侧的下界（``--read-audit-days 0``）→ 退出码 2 + 一句人话。"""
    path = tmp_path / "floor.db"
    engine = create_engine("sqlite:///" + path.as_posix())
    init_db(engine)
    engine.dispose()
    with pytest.raises(SystemExit) as excinfo:
        _main([
            "--db-url", "sqlite:///" + path.as_posix(), "--dry-run",
            "--read-audit-days", "0",
        ])
    assert excinfo.value.code == 2
    assert "误删一切" in capsys.readouterr().err


def _main(argv):
    """跑一次 ``main()``，⚠️ 并把 ``__main__`` 那一段的异常折法一并走到
    （``RetentionError`` / ``BackupError`` → 一句人话 + 退出码 2），
    于是 ``main()`` 的调用方口径与 ``python scripts/retention.py`` **逐字相同**。"""
    try:
        return retention.main(argv)
    except (retention.RetentionError, backup.BackupError) as exc:
        print("清理**没有**执行（拒绝或回滚）：%s" % exc, file=sys.stderr)
        raise SystemExit(2)


def test_this_file_never_names_a_real_database():
    """**反空转**：本文件**代码里的字符串字面量**不许出现一个真库的文件名。

    ⚠️ 判据落在 **AST** 上（只收 :class:`ast.Constant` 的 ``str`` 值），故注释里的
    **提及**不算（硬规矩 #109：提及不是本身）—— 而 docstring 是 ``Constant``，
    故本文件连 docstring 里都不写那两个名字。
    ⚠️ 禁区那一个文件名**刻意不在判据里**：
    :func:`test_the_forbidden_paths_are_refused` 必须点名它才证得了「禁区被拒」。
    ⚠️ 姿势同 ``tests/test_backup_restore.py`` 的同名守卫，而判据比它严一格
    （那一个扫源码字面、这一个扫 AST）。
    """
    tree = ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    # ⚠️ 那个模式**拼出来**、不写成一个字面量：写成一整串的话它会匹配到自己
    #    （本条正是要扫字面量），于是恒红在自己身上。
    pattern = "pe_" + "(demo|trial)" + r"\.db"
    offenders = [text for text in literals if re.search(pattern, text)]
    assert offenders == [], offenders
    # ⚠️ 反空转的第二拍：本条真的扫到了东西（否则一个写错的判据会恒绿）
    assert len(literals) > 100, len(literals)


# ===========================================================================
# 两个 ``.ps1``：形状与「只打印不注册」
# ===========================================================================

RETENTION_PS1 = SCRIPTS_DIR / "retention.ps1"
#: ⚠️ 注册脚本与两个包装**同住** ``backend/scripts/``（逐字理由见它自己的
#: ``.DESCRIPTION``：仓库根那一层的四个各自都同时碰 ``backend/`` 与 ``frontend/``，
#: 而本脚本只碰 ``backend/scripts/`` 下的两个包装与这台机器的计划任务）。
REGISTER_PS1 = SCRIPTS_DIR / "register_retention_task.ps1"


def _ps1_bytes(path: pathlib.Path) -> bytes:
    assert path.is_file(), f"{path} 不存在"
    return path.read_bytes()


def test_the_two_new_ps1_files_are_utf8_with_bom_and_crlf():
    """两个新 ``.ps1`` 一律 **UTF-8 + BOM + 纯 CRLF**。

    ⚠️ PowerShell 5.1 读一个**没有 BOM** 的 ``.ps1`` 时按系统 ANSI 代码页（本机 GBK）
    解码，而这两个文件的注释里全是 UTF-8 中文 —— 轻则注释乱码，重则某个字节序列里
    出现一个引号把语法弄坏（上一波实现者被工具剥过一次 BOM，原地复现过解析失败）。
    ⚠️ 姿势逐字同 ``tests/test_backup_restore.py`` 的同名守卫。
    """
    for path in (RETENTION_PS1, REGISTER_PS1):
        raw = _ps1_bytes(path)
        assert raw[:3] == b"\xef\xbb\xbf", f"{path} 没有 BOM"
        body = raw[3:]
        crlf = body.count(b"\r\n")
        bare_lf = body.count(b"\n") - crlf
        assert bare_lf == 0, f"{path} 有 {bare_lf} 个裸 LF（应是纯 CRLF）"
        assert crlf > 20, f"{path} 只有 {crlf} 行 —— 文件被截断了？"
        body.decode("utf-8")  # ⚠️ 解码失败就是「不是 UTF-8」


def test_neither_ps1_restates_a_retention_window():
    """两个 ``.ps1`` 里**一个「N 天」都不许出现**：四个缺省窗口只有一个所有者。

    ⚠️ 派单 §2 第 3 条逐字要求「缺省值必须有单一所有者（不许 CLI 里一份、
    文档里另一份）」。那一所有者是 ``retention.py`` 的四个 ``DEFAULT_*_DAYS``；
    两个包装一律**复述而不重定义** —— 而本条把「不复述」钉成可执行的：
    一个 ``\\d+\\s*天`` 都不许匹配到（含注释块，因为注释块正是最容易过期的一处）。
    ⚠️ 反空转：同一条正则**在 ``retention.py`` 里必须匹配到**（它那里就是所有者）。
    """
    pattern = re.compile(r"\d+\s*天")
    for path in (RETENTION_PS1, REGISTER_PS1):
        body = _ps1_bytes(path)[3:].decode("utf-8")
        assert pattern.findall(body) == [], (path.name, pattern.findall(body))
    owner = (SCRIPTS_DIR / "retention.py").read_text(encoding="utf-8")
    assert len(pattern.findall(owner)) >= 4, pattern.findall(owner)
    # ⚠️ 而**判据那一句人话**里也不许有：它打印在窗口那一列的**旁边**，
    #    那一列已经印着实数了，故复述一遍就是第二个所有者（改窗口时会当场过期）。
    for spec in retention.SPECS:
        assert pattern.findall(spec.criterion) == [], (spec.key, spec.criterion)


def test_the_register_script_prints_the_command_and_never_registers():
    """注册脚本**只打印**那一对命令，⚠️ 自己不注册（派单 §2 第 5 条）。

    ⚠️ 四拍：① 它打印一条 ``schtasks /Create``；② 它打印对应的 ``schtasks /Delete``；
    ③ 它的**代码段**里没有任何一处真的去执行它们
    （``schtasks`` 只允许出现在 ``Write-Host`` 里）；④ 它明写了「不自动注册」的理由
    （与 ``serve.ps1 -Lan`` 不改防火墙同一条口径：静默改甲方的机器不是交付物该有的形状）。
    """
    raw = _ps1_bytes(REGISTER_PS1)
    body = raw[3:].decode("utf-8")
    # ⚠️ **只扫代码段**（``#>`` 之后那一部分）：``<# .DESCRIPTION #>`` 里逐字**提及**
    #    了 ``schtasks`` 若干次（它在解释那四条命令各是什么），而提及不是本身
    #    （硬规矩 #109）。姿势逐字同 ``tests/test_package.py`` 的 ``_package_ps1_code``。
    assert body.count("#>") == 1, (
        "register_retention_task.ps1 的注释块形状变了，本条的切法要跟着改"
    )
    code = "\n".join(
        line for line in body.split("#>", 1)[1].splitlines()
        if not line.lstrip().startswith("#")
    )

    assert "/Create" in body and "/Delete" in body
    # ③ 代码段里**每一次**提到 schtasks 都在一句 Write-Host 里
    for line in code.splitlines():
        if "schtasks" in line:
            assert "Write-Host" in line, f"这一行不是在打印：{line!r}"
    # ⚠️ 反空转：真的打印了不止一条
    assert sum(1 for line in code.splitlines() if "schtasks" in line) >= 2
    # ④ 那段理由在（⚠️ 它在注释块里，故查 body 而不是 code）
    assert "不自动注册" in body
    assert "静默" in body

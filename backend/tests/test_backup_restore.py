"""备份与恢复的端到端守卫（Plan 06 Task 6）。

派单 §2 第 5 条点名了**三条**，本文件逐条落地、并各加它挡不住的那几档：

========  ==========================================================  ======================
派单        守卫                                                       它挡的失效形态
========  ==========================================================  ======================
①          :func:`test_backup_then_restore_puts_the_changed_row_back`  恢复不到备份点
②          :func:`test_a_tampered_sidecar_makes_restore_refuse`         侧车被人改过
③          :func:`test_a_tampered_backup_file_makes_restore_refuse`     备份本体被改过 1 字节
========  ==========================================================  ======================

⚠️ **一律用 ``tmp_path`` 下的临时库**（派单 §2 第 6 条：「不要碰 ``backend/pe_demo.db``
以外的真库；测试一律临时库；``backend/data/**`` 一字节不许动」）。
:func:`test_the_two_scripts_never_touch_the_real_database_or_the_data_directory`
把那一格钉成**可执行**的（本文件的源码里不许出现 ``pe_demo.db`` 这个字面量，
而两个脚本的禁区守卫另外单独钉）。

--------------------------------------------------------------------------
⚠️ 本文件另有九条不在派单清单里的守卫，各挡一个具体的洞
--------------------------------------------------------------------------

* **自动留后路**（派单 §2 第 3 条）—— :func:`test_restoring_leaves_a_pre_restore_safety_net`
  与它的关闭档 :func:`test_the_safety_net_is_skipped_when_there_is_nothing_to_lose`；
* **写锁那一档要可读**（派单 §2 第 3 条）—— :func:`test_a_locked_target_answers_with_a_readable_error`；
* **在线备份**（派单 §2 第 2 条：「不是复制文件」）——
  :func:`test_the_backup_is_taken_online_while_a_write_transaction_is_open`
  与结构侧的 :func:`test_neither_script_copies_files_or_adds_a_dependency`；
* **侧车的两格**（sha256 **+ 字节数**）—— :func:`test_the_sidecar_carries_both_facts`；
* **禁区**（``backend/pe.db`` / ``backend/data/**``）—— :func:`test_the_forbidden_paths_are_refused`；
* **``backend/backups/`` 真的被忽略、且没有备份入库**（派单 §2 第 2 条）——
  :func:`test_backups_are_gitignored_and_none_is_tracked`；
* **两个 ``.ps1`` 是 UTF-8 + BOM + CRLF**（派单 §2 第 1 条，⚠️ 上一波实现者被工具剥 BOM
  导致脚本解析失败）—— :func:`test_the_two_ps1_wrappers_are_utf8_with_bom_and_crlf`；
* **库路径与 app 同源**（派单 §2 第 4 条）—— :func:`test_the_db_path_comes_from_the_same_owner_as_the_app`；
* **自检那一格**（派单 §2 第 3 条：「打印恢复后的表数自检」）——
  :func:`test_the_selfcheck_reports_what_is_really_on_disk`。
"""
import ast
import datetime as dt
import importlib.util
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR
from app.db.models.organisation import Semester
from app.db.session import init_db

#: ``backend/scripts/``。⚠️ 它**不是包**（没有 ``__init__.py``），故两个脚本按路径加载。
SCRIPTS_DIR = BACKEND_DIR / "scripts"

#: 仓库根（``.gitignore`` 在那里）。
REPO_ROOT = BACKEND_DIR.parent

def _load(name: str):
    """按路径加载 ``backend/scripts/<name>.py``。

    ⚠️ **它同时把模块塞进 ``sys.modules``**：``restore.py`` 在模块体里
    ``from backup import …``，而 ``scripts/`` 不是包、也不在 ``sys.path`` 上
    （``restore.py`` 自己会无条件插一次，与 ``migrations/env.py`` 同款兜底），
    故 ``backup`` 必须先在 ``sys.modules`` 里，那一句 import 才解析得到。
    ⚠️ 加载顺序因此是**承重**的：先 ``backup``、后 ``restore``
    （:data:`backup` / :data:`restore` 两个模块级名字就是这个顺序）。
    """
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


backup = _load("backup")
restore = _load("restore")

#: 备份点那一行的 ``name``。**字面量**：它就是「恢复之后应当读到什么」的期望值，
#: 从被测代码那侧读回来的话，「恢复其实没恢复」这件事会两侧一起变、断言恒成立。
BACKED_UP_NAME = "备份点上的名字"
CHANGED_NAME = "被改坏之后的名字"

#: ``moment`` 的可注入值（同 :func:`app.pipeline.daily.run_daily` 的 ``now`` 先例）：
#: 文件名里带时间戳，而 ``datetime.now`` 会让期望值随墙钟漂。
FIXED_MOMENT = dt.datetime(2026, 10, 13, 3, 4, 5, tzinfo=dt.timezone.utc)
FIXED_NAME = "pe-20261013T030405Z.db"


@pytest.fixture()
def db(tmp_path) -> pathlib.Path:
    """一个**走迁移链**建出来的临时磁盘库，里面有一行 ``semester``。

    ⚠️ 走磁盘、不走内存：备份/恢复说的就是**文件**，而内存 SQLite 没有文件可备
    （:func:`backup.db_path_from_url` 对 ``sqlite://`` 那一档直接拒绝，
    由 :func:`test_the_db_path_comes_from_the_same_owner_as_the_app` 钉住）。
    ⚠️ 走 ``init_db`` 而不是 ``create_all``：于是这个库**带着** ``alembic_version``，
    而 :func:`restore.selfcheck` 那一格 ``revision`` 才有东西可报
    （甲方现场那份库就是这个形状）。
    """
    path = tmp_path / "target.db"
    engine = create_engine("sqlite:///" + path.as_posix())
    init_db(engine)
    with Session(engine) as session:
        session.add(
            Semester(
                name=BACKED_UP_NAME, start_date=dt.date(2025, 9, 1),
                end_date=dt.date(2026, 1, 20), weeks=16, is_current=True,
            )
        )
        session.commit()
    engine.dispose()
    return path


def _semester_name(path: pathlib.Path) -> str:
    """``semester`` 表里 id=1 那一行的 ``name``。

    ⚠️ **显式 ``close()``**，不用 ``with sqlite3.connect(…)``：后者是**事务**上下文
    管理器（退出时 commit/rollback），**不关连接**——于是一个句柄会一直握着那个文件，
    而 Windows 上后续任何 ``unlink`` 都会 ``PermissionError: [WinError 32]``。
    ⚠️ 本 Task 的探针正好踩了这一格（报告 §5 有取证），故这里写成显式的
    ``try/finally``，并把那一条教训钉进
    :func:`test_a_locked_target_answers_with_a_readable_error`。
    """
    connection = sqlite3.connect(str(path))
    try:
        row = connection.execute("SELECT name FROM semester WHERE id = 1").fetchone()
    finally:
        connection.close()
    return row[0]


def _rewrite(path: pathlib.Path, name: str) -> None:
    """把 id=1 那一行的 ``name`` 改成 ``name``（模拟「备份之后库被改坏了」）。"""
    engine = create_engine("sqlite:///" + path.as_posix())
    try:
        with Session(engine) as session:
            session.execute(
                text("UPDATE semester SET name = :n WHERE id = 1"), {"n": name}
            )
            session.commit()
    finally:
        engine.dispose()


# ===========================================================================
# ① 备份 → 改一行 → 恢复 → 那一行回到备份点
# ===========================================================================


def test_backup_then_restore_puts_the_changed_row_back(db, tmp_path):
    """派单 §2 第 5 条的主判据：**端到端**，临时库。

    五拍，每一拍各挡一个失效形态：

    ① 备份**产出了两个文件**（``pe-<UTC ts>.db`` 与**同名**的 ``.sha256``）；
    ② 备份是一份**真的能打开的库**（``sqlite3`` 直接读它，读到的是备份点那一行）
       ——⚠️ 少了这一拍，「备份了一个 0 字节的文件」也会绿；
    ③ 改坏之后读到的确实是**改坏的值**（否则④证明不了什么）；
    ④ 恢复之后读到的是**备份点的值**；
    ⑤ 恢复之后 ``alembic_version`` 还在（它是 :func:`app.db.session.init_db`
       判「这个库有没有被纳管」的唯一依据，丢了它会让下次起服务走**档 2**）。

    ⚠️ 文件名**逐字**是 ``pe-20261013T030405Z.db``：``moment`` 被注入成
    :data:`FIXED_MOMENT`，故「``pe-<UTC ts>.db``」这个形状（派单 §2 第 2 条）
    是被钉住的，不是「看起来像」。
    """
    backups_dir = tmp_path / "backups"
    made = backup.create_backup(db, backups_dir, moment=FIXED_MOMENT)

    # ① 两个文件
    assert made.name == FIXED_NAME, made.name
    assert made.is_file()
    sidecar = backup.sidecar_of(made)
    assert sidecar.name == FIXED_NAME + ".sha256", sidecar.name
    assert sidecar.is_file()
    assert sorted(p.name for p in backups_dir.iterdir()) == [
        FIXED_NAME, FIXED_NAME + ".sha256"
    ]

    # ② 备份本身是一份能打开的库，且内容就是备份点
    assert _semester_name(made) == BACKED_UP_NAME
    assert made.stat().st_size > 0

    # ③ 改坏
    _rewrite(db, CHANGED_NAME)
    assert _semester_name(db) == CHANGED_NAME

    # ④ 恢复
    result = restore.restore_database(made, db, backups_dir=backups_dir)
    assert _semester_name(db) == BACKED_UP_NAME

    # ⑤ 版本表还在（恢复的是**整份库**，不是某几张表）
    # ⚠️ 那个修订号是**字面量**（= 迁移链的头，今天 `0ac943e0da9b`）。
    #    它与 `tests/db/test_migration_baseline.py` 的 `HEAD_REVISION` 是**两个所有者**、
    #    刻意各写一份：本处答的是「一份备份/恢复往返之后，磁盘上写着的是**当时**那个头」，
    #    那一份答的是「一条全新的库 `upgrade head` 之后停在哪个号」。
    #    ⚠️ 于是**每加一条迁移，这两处一起红、一起改**（Plan 06 Task 11 是第三次：
    #    `7f3923d8af84` → `0ac943e0da9b`；⚠️ 而 `tables` 那两格 29 / 28 都没动 ——
    #    第四条迁移只改一列的宽度、不加表）。
    assert result["selfcheck"]["revision"] == "03331a689ee4", result["selfcheck"]
    connection = sqlite3.connect(str(db))
    try:
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        connection.close()
    assert "audit_log" in tables and "alembic_version" in tables
    assert len(tables) == 30, sorted(tables)


# ===========================================================================
# ②③ 两种篡改都拒绝
# ===========================================================================


def test_a_tampered_sidecar_makes_restore_refuse(db, tmp_path):
    """派单 §2 第 5 条第二拍：**篡改侧车 sha → 恢复拒绝**。

    ⚠️ 两格各试一次（侧车有**两个**事实，故两格都可能被改）：

    * ``sha256`` 换成 64 个 ``0`` → :func:`restore.verify_backup` 抛
      :class:`backup.BackupError`，而 message 里**同时**给出期望值与实测值的前 16 位
      （于是运维能看出「是完全不同的文件」还是「只差一点」）；
    * ``bytes`` 改成 ``1`` → 同样拒绝，而 message 说的是**字节数**、不是 sha
      （两格的报错**可区分**，否则「侧车写错了」与「备份被改了」在屏幕上长一个样）。

    ⚠️ 并且断言**目标库一个字节都没动**：拒绝必须发生在动手之前
    （:func:`restore.restore_database` 的四步里，校验是第①步）。
    ⚠️ 以及 ``main()`` 那一档的**退出码非 0**（派单 §2 第 3 条逐字要求）：
    它抛 :class:`backup.BackupError`，而 ``__main__`` 那一段把它折成 ``sys.exit(2)``。
    """
    backups_dir = tmp_path / "backups"
    made = backup.create_backup(db, backups_dir, moment=FIXED_MOMENT)
    sidecar = backup.sidecar_of(made)
    original = sidecar.read_text(encoding="utf-8")
    before = db.read_bytes()

    good = backup.read_sidecar(sidecar)
    sidecar.write_text(
        "sha256=%s\nbytes=%d\n" % ("0" * 64, good["bytes"]), encoding="utf-8"
    )
    with pytest.raises(backup.BackupError) as sha_info:
        restore.verify_backup(made)
    assert "sha256 不吻合" in str(sha_info.value), str(sha_info.value)
    assert str(good["sha256"])[:16] in str(sha_info.value)

    sidecar.write_text(
        "sha256=%s\nbytes=%d\n" % (good["sha256"], 1), encoding="utf-8"
    )
    with pytest.raises(backup.BackupError) as size_info:
        restore.verify_backup(made)
    assert "字节数不吻合" in str(size_info.value), str(size_info.value)

    # ⚠️ 拒绝发生在动手之前：目标库一个字节都没变
    assert db.read_bytes() == before
    assert _semester_name(db) == BACKED_UP_NAME

    # ⚠️ 侧车改回来之后**又能恢复**（证明上面两拍挡的确实是「篡改」而不是「一律拒绝」）
    sidecar.write_text(original, encoding="utf-8")
    assert restore.verify_backup(made) == good

    # ⚠️ main() 那一档：抛 BackupError（``__main__`` 折成退出码 2）
    sidecar.write_text(
        "sha256=%s\nbytes=%d\n" % ("0" * 64, good["bytes"]), encoding="utf-8"
    )
    with pytest.raises(backup.BackupError):
        restore.main([str(made), "--db-url", "sqlite:///" + db.as_posix()])


def test_a_tampered_backup_file_makes_restore_refuse(db, tmp_path):
    """派单 §2 第 5 条第三拍：**篡改备份文件 1 字节 → 恢复拒绝**。

    ⚠️ 改的是**第 100 个字节**（不是第 0 个）：SQLite 的文件头是前 100 字节，
    改头会让 ``sqlite3`` 直接报「file is not a database」——那一档**太响**，
    证明不了「校验挡住了一个不校验就会被用上去的备份」。

    ⚠️⚠️ **两格取证，第二格是本条真正承重的部分**：

    ① ``sha256`` **变了**（故校验必然拒绝）；
    ② ``bytes`` **没变**（故侧车里的字节数那一格**单独挡不住它**）。

    ⚠️ ①+② 合起来才证明「两格不是冗余」：一个只校验字节数的实现会在本档下
    **放行**一份被改过的备份。⚠️ 本 Task 的第一版在这里还写了一拍
    「篡改之后那个文件仍然能被 sqlite3 打开」，实测**不成立**
    （``database disk image is malformed``：第 100 个字节落在第一页的
    schema 区，翻一位就把 b-tree 页头改坏了）——故那一拍删掉，
    换成①②这个**不依赖 SQLite 内部布局**的判据。⚠️ 而「改坏了、而恢复上去
    得到一个坏库」这件事仍然成立：``malformed`` 只是**其中一种**坏法，
    另一种是「照旧能打开、而某一行的值变了」——两档下 sha256 都变，
    故本条的判据对两档**同样**有效（这正是用 sha 而不是用「能不能打开」当判据的理由）。

    ⚠️ 并且断言：拒绝发生在动手之前（目标库一个字节都没动），
    以及改回来之后**又能恢复**（证明本条挡的是「篡改」而不是「一律拒绝」）。
    """
    backups_dir = tmp_path / "backups"
    made = backup.create_backup(db, backups_dir, moment=FIXED_MOMENT)
    original = made.read_bytes()
    assert len(original) > 200, "备份太小，第 100 个字节可能不存在"
    good = backup.read_sidecar(backup.sidecar_of(made))

    flipped = bytearray(original)
    flipped[100] ^= 0xFF
    made.write_bytes(bytes(flipped))

    # ①② sha 变了、字节数没变 → 「只校验字节数」的实现会放行它
    assert made.stat().st_size == good["bytes"], "字节数那一格挡不住本次篡改"
    assert backup.sha256_of(made) != good["sha256"], "sha 那一格必须能看出来"

    with pytest.raises(backup.BackupError) as excinfo:
        restore.verify_backup(made)
    message = str(excinfo.value)
    assert "sha256 不吻合" in message, message
    assert "被动过" in message and "哪怕只改了 1 个字节" in message, message

    before = db.read_bytes()
    with pytest.raises(backup.BackupError):
        restore.restore_database(made, db, backups_dir=backups_dir)
    assert db.read_bytes() == before, "拒绝必须发生在动手之前"
    assert _semester_name(db) == BACKED_UP_NAME

    # 改回来之后又能恢复
    made.write_bytes(original)
    assert restore.verify_backup(made)["sha256"] == good["sha256"]
    _rewrite(db, CHANGED_NAME)
    restore.restore_database(made, db, backups_dir=backups_dir)
    assert _semester_name(db) == BACKED_UP_NAME


# ===========================================================================
# 自动留后路（派单 §2 第 3 条）
# ===========================================================================


def test_restoring_leaves_a_pre_restore_safety_net(db, tmp_path):
    """**覆盖之前**先给当前库留一份 ``…-pre-restore.db``（派单 §2 第 3 条逐字要求）。

    三拍：

    ① 那一份**存在**，文件名带 ``-pre-restore``（于是运维一眼能认出它不是定时备份）；
    ② 它的内容是**恢复之前**的那一份（= 被改坏的值），故「选错了备份」时
       可以用它再恢复一次——那正是派单 §4 顶回 ② 问的「多一个文件 vs 二次丢失」，
       实现者核过、**维持**（两条理由逐字见 :mod:`restore` 的模块 docstring 第一节）；
    ③ 它**也有侧车**（于是它自己也能被校验着恢复回去）。

    ⚠️ 用 :data:`FIXED_MOMENT` 之外的时刻做后路那一份：``restore_database`` 不接受
    ``moment``（它调 :func:`backup.create_backup` 的缺省路径 = 真实时钟），
    故本条只钉「文件名**以** ``-pre-restore.db`` 结尾」而不是钉整个时间戳。
    """
    backups_dir = tmp_path / "backups"
    made = backup.create_backup(db, backups_dir, moment=FIXED_MOMENT)
    _rewrite(db, CHANGED_NAME)

    result = restore.restore_database(made, db, backups_dir=backups_dir)
    net = result["safety_net"]
    assert net is not None, "覆盖之前必须留一份后路"
    assert net.name.endswith("-pre-restore.db"), net.name
    assert net.name.startswith("pe-"), net.name
    assert net.is_file()

    # ② 后路里是**恢复之前**的内容
    assert _semester_name(net) == CHANGED_NAME
    assert _semester_name(db) == BACKED_UP_NAME

    # ③ 后路也有侧车，且它自己校验得过
    net_sidecar = backup.sidecar_of(net)
    assert net_sidecar.is_file()
    assert restore.verify_backup(net)["sha256"] == backup.sha256_of(net)

    # ⚠️ 用后路再恢复一次 → 回到「被改坏」那一份（证明它是一份**可用的**备份，
    #    不是一个占位文件）
    restore.restore_database(net, db, backups_dir=backups_dir, auto_backup=False)
    assert _semester_name(db) == CHANGED_NAME


def test_the_safety_net_is_skipped_when_there_is_nothing_to_lose(db, tmp_path):
    """后路**不是无条件**的：目标库不存在 / 是 0 字节时跳过它。

    ⚠️ 派单 §2 第 3 条要的是「避免恢复本身造成**二次丢失**」，而没有东西可丢时
    「自动备份」只会抛（:func:`backup.backup_database` 对不存在与 0 字节两档都拒绝）
    ——于是「把一份备份恢复成一个新库」这个**合法且常见**的动作会被自己的后路挡住。

    两拍：① 目标不存在 → 后路是 ``None``、而恢复**成功**；
    ② 目标是 0 字节 → 同上。
    """
    backups_dir = tmp_path / "backups"
    made = backup.create_backup(db, backups_dir, moment=FIXED_MOMENT)

    fresh = tmp_path / "fresh.db"
    result = restore.restore_database(made, fresh, backups_dir=backups_dir)
    assert result["safety_net"] is None
    assert fresh.is_file()
    assert _semester_name(fresh) == BACKED_UP_NAME
    assert result["selfcheck"]["tables"] == 30

    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")
    result = restore.restore_database(made, empty, backups_dir=backups_dir)
    assert result["safety_net"] is None
    assert _semester_name(empty) == BACKED_UP_NAME


def test_no_verify_and_no_auto_backup_are_explicit_escapes(db, tmp_path):
    """两个逃生口**只**关掉它们各自那一步，其余照跑。

    ⚠️ ``--no-verify`` 跳过①，而②③④一律照跑（跳过锁检测会得到一个覆盖到一半的库，
    跳过自动备份会得到一次不可逆的覆盖——两者都与「侧车丢了」无关）。
    ⚠️ ``--no-auto-backup`` 跳过③，而①照跑（侧车在的时候没有理由不校验）。

    ⚠️ 本条同时是那两个逃生口的**存在性守卫**：少了它，
    「有人把 ``verify`` 的缺省值改成 ``False``」不会有任何测试红
    （上面那两条篡改守卫都是显式传参或走缺省 ``True``……⚠️ 而它们走的**正是**缺省，
    故那一档其实由它们挡着；本条挡的是**另一半**：逃生口本身还能用）。
    """
    backups_dir = tmp_path / "backups"
    made = backup.create_backup(db, backups_dir, moment=FIXED_MOMENT)
    sidecar = backup.sidecar_of(made)
    good = backup.read_sidecar(sidecar)
    sidecar.write_text("sha256=%s\nbytes=%d\n" % ("0" * 64, 1), encoding="utf-8")

    _rewrite(db, CHANGED_NAME)
    result = restore.restore_database(
        made, db, verify=False, auto_backup=False, backups_dir=backups_dir
    )
    assert result["sidecar"] is None, "--no-verify 那一档不该去读侧车"
    assert result["safety_net"] is None
    assert _semester_name(db) == BACKED_UP_NAME
    # ⚠️ 反空转：侧车此刻**确实是坏的**，故上面能过只能是 ``verify=False`` 起了作用
    with pytest.raises(backup.BackupError):
        restore.verify_backup(made)

    sidecar.write_text(
        "sha256=%s\nbytes=%d\n" % (good["sha256"], good["bytes"]), encoding="utf-8"
    )
    result = restore.restore_database(
        made, db, auto_backup=False, backups_dir=backups_dir
    )
    assert result["sidecar"] == good, "--no-auto-backup 不该顺带关掉校验"
    assert result["safety_net"] is None


# ===========================================================================
# 写锁那一档（派单 §2 第 3 条：「要报一个**可读的**错」）
# ===========================================================================


def test_a_locked_target_answers_with_a_readable_error(db, tmp_path):
    """目标库正被**写锁**占住 → :class:`backup.BackupError`，message 里有「请先停服务」。

    ⚠️ 判据是 ``BEGIN IMMEDIATE``（要**写**锁）：一次只读的 ``SELECT`` 在 WAL 模式下
    不与写者冲突，于是「服务正在跑」会被漏判、而恢复会在覆盖到一半时撞锁。

    ⚠️⚠️ **它挡不住「服务在跑但此刻空闲」**（SQLite 的锁是**事务级**的），
    故它是「尽力」的、不是「充分」的——那一格如实记在
    :func:`restore._assert_not_in_use` 的 docstring 里，而 ``restore.py`` 的 ``main``
    **每次都打印**「请先停服务」。本条钉的是「撞上了的时候报错可读」，
    不是「一定能探到」。

    ⚠️ 三拍：① 占住 → 拒绝且 message 可读；② 放开 → 放行；
    ③ **目标不存在** → 直接放行（那不是「被占用」，那是「恢复到一个新位置」）。
    """
    holder = sqlite3.connect(str(db), timeout=0.2)
    try:
        holder.execute("BEGIN IMMEDIATE")
        with pytest.raises(backup.BackupError) as excinfo:
            restore._assert_not_in_use(db)
        message = str(excinfo.value)
        assert "请先停服务" in message, message
        assert "尽力" in message, "那句「本检测是尽力的」必须在，否则运维会以为它充分"
    finally:
        holder.rollback()
        holder.close()

    restore._assert_not_in_use(db)  # ② 放开之后放行（不抛就是过）
    restore._assert_not_in_use(tmp_path / "not-there.db")  # ③ 不存在也放行


# ===========================================================================
# 在线备份（派单 §2 第 2 条：「不是复制文件——复制在写进行中会坏」）
# ===========================================================================


def test_the_backup_is_taken_online_while_a_write_transaction_is_open(db, tmp_path):
    """**写事务开着**的时候备份仍然成功，且备到的是**事务开始之前**的那一份。

    ⚠️ 这一条是「``backup()`` 而不是 ``copyfile``」的**行为面**取证：
    复制文件在这一档下会读到一份**不自洽**的库（新页还在 ``-journal`` 里），
    而 ``sqlite3`` 的在线备份在一个读事务里逐页拷，故它拿到的永远是某一个时刻的
    一致快照。⚠️ 它**不阻塞**写（这正是「服务跑着的时候每天夜里 cron 一次」
    能成立的前提）。

    ⚠️ 第二拍钉的是**一致性语义**：那个未提交的事务**不在**备份里
    （``rollback`` 之后目标库仍然是备份点的值）。⚠️ 少了这一拍，
    「备份到了一半的脏数据」这个失效形态没有守卫。
    """
    holder = sqlite3.connect(str(db))
    try:
        holder.execute("BEGIN IMMEDIATE")
        holder.execute("UPDATE semester SET name = ? WHERE id = 1", (CHANGED_NAME,))
        # ⚠️ 事务**没提交**，连接也**没关**：这就是「写进行中」
        made = backup.create_backup(db, tmp_path / "backups", moment=FIXED_MOMENT)
        assert _semester_name(made) == BACKED_UP_NAME, "未提交的事务不该出现在备份里"
        holder.rollback()
    finally:
        holder.close()
    assert _semester_name(db) == BACKED_UP_NAME
    assert _semester_name(made) == BACKED_UP_NAME


def test_neither_script_copies_files_or_adds_a_dependency():
    """**结构侧**的两格：不复制文件、不加依赖（派单 §2 第 2 条与 §0 的「新增依赖 = 0」）。

    ① 两个脚本的 AST 里**没有** ``shutil``、也没有 ``open(…, "wb")`` 一类
       「自己搬字节」的写法。⚠️ 判据是**导入名**而不是文本搜索：
       两个脚本的 docstring 里都**提及**了 ``shutil.copyfile``（解释为什么不用它），
       而提及不是本身（硬规矩 #109）。
    ② 两个脚本 import 的**非 ``app.*``** 顶层模块全部在 :data:`sys.stdlib_module_names`
       里（``sqlalchemy`` 除外：它是既有依赖，不是本波加的）。
       ⚠️ 于是「本波新增依赖 = 0」在**这两个脚本上**是可执行的，
       而不只是 ``tests/test_dependencies.py`` 那份清单上的一个数
       （那一份钉的是 ``pyproject.toml``，钉不到「有人在一个脚本里 ``import zstd``」）。
    """
    for name in ("backup", "restore"):
        source = (SCRIPTS_DIR / f"{name}.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
        assert "shutil" not in imported, f"{name}.py 导入了 shutil（不许复制文件）"
        third_party = imported - set(sys.stdlib_module_names) - {"app", "sqlalchemy",
                                                                 "backup"}
        assert third_party == set(), (
            f"{name}.py 引入了非标准库的依赖 {sorted(third_party)}："
            "本波新增依赖 = 0（备份用标准库 sqlite3 + hashlib）"
        )
        # ⚠️ 反空转：``sqlite3`` 与 ``hashlib`` 确实被 backup.py 用上了
        if name == "backup":
            assert {"sqlite3", "hashlib"} <= imported, sorted(imported)


# ===========================================================================
# 侧车的两格 + 库路径同源 + 禁区
# ===========================================================================


def test_the_sidecar_carries_both_facts(db, tmp_path):
    """侧车里有 sha256 **与** 字节数两格（派单 §2 第 2 条），且两格都是**真的**。

    四拍：

    ① 格式是两行 ``key=value``（⚠️ **刻意不是** coreutils 的 ``sha256sum`` 格式：
       一行装不下第二格，而「半兼容」比「明显是自己的格式」更坏——
       ``sha256sum -c`` 会把第二行报成一条格式错误，于是运维以为备份坏了。
       逐字理由见 :mod:`backup` 的模块 docstring 第四节）；
    ② ``sha256`` 与 :func:`backup.sha256_of` 现算的**逐字相同**；
    ③ ``bytes`` 与 ``stat().st_size`` **相同**；
    ④ 侧车是 **UTF-8 无 BOM**：一个 BOM 会让 ``line.partition("=")`` 在第一行拿到
       ``"\\ufeffsha256"``（一个**静默**的失配 → 「缺 sha256」）。

    ⚠️ 并且钉住「sha256 是**分块**算的」不会算错：换一个 1 MiB+ 的库再算一次，
    两格的值仍然自洽（:func:`backup.sha256_of` 的块大小是 1 MiB，
    小于块大小的库走不到第二块，故那一格必须单独验）。
    """
    made = backup.create_backup(db, tmp_path / "backups", moment=FIXED_MOMENT)
    sidecar = backup.sidecar_of(made)
    raw = sidecar.read_bytes()

    assert raw[:3] != b"\xef\xbb\xbf", "侧车带 BOM"
    lines = raw.decode("utf-8").splitlines()
    assert len(lines) == 2, lines
    assert lines[0].startswith("sha256=") and lines[1].startswith("bytes=")

    got = backup.read_sidecar(sidecar)
    assert got["sha256"] == backup.sha256_of(made)
    assert got["bytes"] == made.stat().st_size
    assert len(str(got["sha256"])) == 64

    # ④ 分块那一格：造一个 > 1 MiB 的库，两格仍然自洽
    big = tmp_path / "big.db"
    engine = create_engine("sqlite:///" + big.as_posix())
    init_db(engine)
    with Session(engine) as session:
        session.add(
            Semester(name="x" * 4000, start_date=dt.date(2025, 9, 1),
                     end_date=dt.date(2026, 1, 20), weeks=16, is_current=True)
        )
        for index in range(400):
            session.execute(
                text("INSERT INTO semester (name, start_date, end_date, weeks, is_current) "
                     "VALUES (:n, '2025-09-01', '2026-01-20', 16, 0)"),
                {"n": "填充%d%s" % (index, "y" * 2000)},
            )
        session.commit()
    engine.dispose()
    assert big.stat().st_size > 1024 * 1024, "这一拍要一个超过块大小的库才有意义"
    big_backup = backup.create_backup(big, tmp_path / "backups", label="-big")
    big_sidecar = backup.read_sidecar(backup.sidecar_of(big_backup))
    assert big_sidecar["bytes"] == big_backup.stat().st_size
    assert big_sidecar["sha256"] == backup.sha256_of(big_backup)


def test_the_db_path_comes_from_the_same_owner_as_the_app(db, tmp_path, monkeypatch):
    """库路径与 app **同源**（派单 §2 第 4 条）：三档优先级 + 不写第二个解析器。

    四拍：

    ① ``--db-url`` 实参 > ``PE_DB_URL`` > :data:`app.main.DEMO_DB_URL`
       （⚠️ **缺省值刻意不是** :func:`app.main._resolve_db_url` 的那个：
       那一个回落到 :data:`app.config.DEFAULT_DB_URL` = 禁区 ``backend/pe.db``。
       本脚本回落到 ``DEMO_DB_URL``，与 ``demo.ps1`` 逐字一致）；
    ② 解析用的是 :func:`app.db.session._db_file_of`（AST 判：本脚本**没有**第二个
       ``sqlite:///`` 的字面量剥离）；
    ③ 内存库（``sqlite://``）与 ``:memory:`` 一律拒绝（备份一个内存库没有意义）；
    ④ 空字符串按「没设」处理（``$env:PE_DB_URL = ""`` 在 PowerShell 里是
       「设了一个空值」而不是「删掉这个变量」）。
    """
    monkeypatch.delenv("PE_DB_URL", raising=False)
    from app.main import DEMO_DB_URL

    assert backup.resolve_db_path() == backup.db_path_from_url(DEMO_DB_URL)
    assert backup.resolve_db_path().name == "pe_demo.db"

    monkeypatch.setenv("PE_DB_URL", "sqlite:///" + db.as_posix())
    assert backup.resolve_db_path() == db
    other = tmp_path / "explicit.db"
    assert backup.resolve_db_path("sqlite:///" + other.as_posix()) == other

    monkeypatch.setenv("PE_DB_URL", "")
    assert backup.resolve_db_path().name == "pe_demo.db", "空串按「没设」处理"

    for memory in ("sqlite://", "sqlite:///:memory:"):
        with pytest.raises(backup.BackupError):
            backup.db_path_from_url(memory)

    # ② 结构侧：没有第二个解析器。
    #    ⚠️ 判据是 **AST**（有没有一处 ``.removeprefix(...)`` 一类的**调用**），
    #    不是文本搜索：``backup.py`` 的模块 docstring 里**逐字提及**了
    #    ``url.removeprefix("sqlite:///")``（解释为什么不用它），而提及不是本身
    #    （硬规矩 #109）。⚠️ 本 Task 的第一版正是写成「去掉 ``#`` 注释行之后搜文本」，
    #    它**漏掉了 docstring**、当场红给自己看。
    tree = ast.parse((SCRIPTS_DIR / "backup.py").read_text(encoding="utf-8"))
    #: ⚠️ **``partition`` 不在本清单里**（本 Task 第一版把它加进去、当场红）：
    #: ``read_sidecar`` 用 ``line.partition("=")`` 解析侧车，那是**侧车格式**的解析、
    #: 不是 URL 的解析。本清单只列「剥 ``sqlite:///`` 前缀」那一族的三个方法名。
    calls = sorted({
        node.attr for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in ("removeprefix", "removesuffix", "lstrip")
    })
    assert calls == [], (
        f"backup.py 里出现了自己剥前缀的调用 {calls}：那是第二个解析器，"
        "而它在 UNC 路径（sqlite:////server/share/x.db）上会错。"
        "「URL → 磁盘文件」的唯一所有者是 app.db.session._db_file_of"
    )
    imported_from_session = [
        alias.name for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "app.db.session"
        for alias in node.names
    ]
    assert "_db_file_of" in imported_from_session, imported_from_session
    # ⚠️ 反空转：``make_url`` 那一次调用**在**（否则上面那条「没有第二个解析器」
    #    可能只是因为整个函数都被删了）
    assert any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "make_url"
        for node in ast.walk(tree)
    ), "backup.py 不再调 make_url 了，db_path_from_url 的口径可能被换掉"


def test_the_forbidden_paths_are_refused(tmp_path, monkeypatch):
    """**禁区守卫**：``backend/pe.db`` 与 ``backend/data/**`` 一律拒绝（三档写法都挡）。

    ⚠️ 与 ``demo.ps1`` 的⑤那一步、``demo_bootstrap.py`` 的两道前置守卫同一个姿势：
    失效方向是「当场退出 + 一句人话」，不是「静默操作禁区」。

    ⚠️ **三档写法**逐个试（判据一律走 :meth:`pathlib.Path.resolve`）：
    直写、``backend/../backend/pe.db``、以及 ``PE_DB_URL`` 里设成它。
    ⚠️ 少了后两档，「用相对路径绕过」这个失效形态没有守卫。

    ⚠️ 并断言 ``backend/pe.db`` **仍然不存在**（本文件跑完不许留下它）。
    """
    pe_db = BACKEND_DIR / "pe.db"
    assert not pe_db.exists(), "开工前 pe.db 就不该存在"
    candidates = [
        "sqlite:///" + pe_db.as_posix(),
        "sqlite:///" + (BACKEND_DIR / ".." / "backend" / "pe.db").as_posix(),
        "sqlite:///" + (BACKEND_DIR / "data" / "x.db").as_posix(),
        "sqlite:///" + (BACKEND_DIR / "data" / "seed" / "y.db").as_posix(),
        "sqlite:///" + (BACKEND_DIR / "." / "data" / "z.db").as_posix(),
    ]
    for url in candidates:
        with pytest.raises(backup.BackupError) as excinfo:
            backup.resolve_db_path(url)
        message = str(excinfo.value)
        assert "拒绝操作" in message, (url, message)
        assert "禁区" in message or "一个字节都不许动" in message, (url, message)

    monkeypatch.setenv("PE_DB_URL", "sqlite:///" + pe_db.as_posix())
    with pytest.raises(backup.BackupError):
        backup.resolve_db_path()

    # ⚠️ 两个 main() 也守（它们都经 resolve_db_path）
    with pytest.raises(backup.BackupError):
        backup.main(["--db-url", "sqlite:///" + pe_db.as_posix()])
    assert not pe_db.exists(), "本文件跑完不许留下 backend/pe.db"


def test_a_missing_or_empty_source_is_refused_before_writing_anything(tmp_path):
    """源库**不存在**或**是 0 字节** → 拒绝，且**不留下任何文件**。

    ⚠️ 两档都不是「SQLite 的缺省行为」能兜的：``sqlite3.connect`` 对一个不存在的
    路径**建一个空库**，于是「库路径写错了」会静默产出一份 0 张表的备份——
    而它在侧车里看起来**完全合法**（sha256 与字节数都吻合它自己）。
    故本函数显式 ``mode=ro`` 打开源、并自己先判存在与大小。

    ⚠️ 0 字节那一档是**实测补的**：SQLite 自己就把「零长度文件」当成一个空库
    （:func:`app.db.session.init_db` 的档 1b 也认它），而备份它得到的是一份
    「合法但空」的备份——恢复上去等于把库清空。
    """
    backups_dir = tmp_path / "backups"
    missing = tmp_path / "nope.db"
    with pytest.raises(backup.BackupError) as excinfo:
        backup.create_backup(missing, backups_dir)
    assert "不存在" in str(excinfo.value)

    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")
    with pytest.raises(backup.BackupError) as excinfo:
        backup.create_backup(empty, backups_dir)
    assert "0 字节" in str(excinfo.value)

    assert not backups_dir.exists() or list(backups_dir.iterdir()) == [], (
        "拒绝之后不该留下任何半成品"
    )


def test_the_sidecar_parser_reports_which_line_is_broken(tmp_path):
    """侧车格式坏 → 报的是**哪一行/哪一格**，不是一个 ``KeyError`` 的裸栈。

    四档，各报一句能照着做的人话：文件不在 / 有一行不是 ``key=value`` /
    缺一个键 / 值解析不出来（``bytes`` 不是整数、``sha256`` 不是 64 个十六进制）。

    ⚠️ 这一条挡的是「运维手工编辑过侧车」那一档：那一次编辑通常是好意的
    （「我把备份复制到别的机器上了，路径变了」），而报错必须让他看出
    **是哪一格**坏了，否则他会去怀疑备份本身。
    """
    directory = tmp_path / "backups"
    directory.mkdir()
    target = directory / "pe-20261013T030405Z.db"
    target.write_bytes(b"whatever")
    sidecar = backup.sidecar_of(target)

    with pytest.raises(backup.BackupError) as excinfo:
        backup.read_sidecar(sidecar)
    assert "侧车文件不存在" in str(excinfo.value)

    sidecar.write_text("sha256=%s\nbytes=12\n" % ("a" * 64), encoding="utf-8")
    assert backup.read_sidecar(sidecar) == {"sha256": "a" * 64, "bytes": 12}

    sidecar.write_text("这一行没有等号\n", encoding="utf-8")
    with pytest.raises(backup.BackupError) as excinfo:
        backup.read_sidecar(sidecar)
    assert "第 1 行" in str(excinfo.value), str(excinfo.value)

    sidecar.write_text("sha256=%s\n" % ("a" * 64), encoding="utf-8")
    with pytest.raises(backup.BackupError) as excinfo:
        backup.read_sidecar(sidecar)
    assert "缺 ['bytes']" in str(excinfo.value), str(excinfo.value)

    sidecar.write_text("sha256=%s\nbytes=many\n" % ("a" * 64), encoding="utf-8")
    with pytest.raises(backup.BackupError) as excinfo:
        backup.read_sidecar(sidecar)
    assert "不是一个整数" in str(excinfo.value), str(excinfo.value)

    sidecar.write_text("sha256=tooshort\nbytes=12\n", encoding="utf-8")
    with pytest.raises(backup.BackupError) as excinfo:
        backup.read_sidecar(sidecar)
    assert "64 个十六进制" in str(excinfo.value), str(excinfo.value)


# ===========================================================================
# 自检 + 两个 .ps1 + .gitignore
# ===========================================================================


def test_the_selfcheck_reports_what_is_really_on_disk(db, tmp_path):
    """恢复后的自检三格（派单 §2 第 3 条：「打印恢复后的表数自检」）。

    ⚠️ ``tables`` 是 **29** 而不是 ``/api/health`` 报的 **28**：health 数的是
    ``Base.metadata``（**不含** ``alembic_version``），本自检数的是**磁盘上**的表。
    那一格差别由 ``tests/db/test_migration_baseline.py`` 的
    ``EXPECTED_TABLE_COUNT_WITH_VERSION``（29）与 ``EXPECTED_TABLES``（28 个名字）
    两个常量钉住——⚠️ **本条刻意取磁盘那一侧**：恢复要验的是「文件里有什么」，
    不是「模型声明了什么」。

    ⚠️ 三格各答一个不同的问题（与 ``/api/health`` 那两格同一个立意）：
    ``tables`` 是 schema 层面的数、``revision`` 是「这份库被纳管到哪一条迁移」、
    ``students`` 是一次**真的查询**（它证明文件不只是「能被 sqlite3 打开」）。

    ⚠️ **它只读**（``mode=ro``）：自检不该在刚恢复好的库上留下任何写痕迹。
    ⚠️ 而它**故意不跑** ``init_db``：那会**改**库（``upgrade head``），
    而恢复的语义是「把库变成备份那一刻的样子」。

    ⚠️ 下面那个 ``revision`` 是**字面量**（= 迁移链的头，今天 ``0ac943e0da9b``），
    与 ``tests/db/test_migration_baseline.py`` 的 :data:`~tests.db.test_migration_baseline.HEAD_REVISION`
    是**两个所有者**、刻意各写一份（一个答「备份/恢复往返之后磁盘上写着哪个号」、
    一个答「一条全新的库 ``upgrade head`` 之后停在哪个号」）。
    ⚠️ 于是**每加一条迁移，这两处一起红、一起改**（Plan 06 Task 11 是第三次：
    ``7f3923d8af84`` → ``0ac943e0da9b``，而 ``tables`` 那两格 **29 / 28 都没动**
    ——第四条迁移只改一列的宽度、不加表）。
    """
    check = restore.selfcheck(db)
    assert check["tables"] == 30, check
    assert check["revision"] == "03331a689ee4", check
    assert check["students"] == 0, check

    before = db.stat().st_mtime_ns
    restore.selfcheck(db)
    assert db.stat().st_mtime_ns == before, "自检不许写库"

    # ⚠️ 一份**没有**版本表的库（引入迁移链之前的备份）→ revision 是 None，
    #    而 main() 会因此多打印一段「下次起服务会走档 2」的提示
    legacy = tmp_path / "legacy.db"
    connection = sqlite3.connect(str(legacy))
    try:
        connection.execute("CREATE TABLE student (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO student (name) VALUES ('张三')")
        connection.commit()
    finally:
        connection.close()
    check = restore.selfcheck(legacy)
    assert check["revision"] is None, check
    assert check["tables"] == 1 and check["students"] == 1, check


def test_the_two_ps1_wrappers_are_utf8_with_bom_and_crlf():
    """两个 ``.ps1`` 是 **UTF-8 + BOM + CRLF**（派单 §2 第 1 条）。

    ⚠️ **BOM 是承重的、不是洁癖**：PowerShell 5.1 读一个**没有 BOM** 的 ``.ps1``
    时按**系统 ANSI 代码页**（本机是 GBK）解码，而两个脚本的注释里全是 UTF-8 中文
    ——于是中文字节被按 GBK 解释，轻则注释变乱码，重则**某个字节序列里出现一个
    反引号或引号**、把脚本的语法弄坏（派单逐字记了上一波的事故：
    「实现者被工具剥 BOM 导致脚本解析失败」）。

    ⚠️ 三拍：① 两个文件都是 BOM + 纯 CRLF（**0 个裸 LF**）；
    ② 去掉 BOM 之后能按 UTF-8 解码（证明 BOM 之外没有别的编码混进来）；
    ③ 与既有那一款 ``demo.ps1`` **同款**（那一格是「本仓的 ``.ps1`` 只有一种形状」
    的可执行形式）。

    ⚠️ 并钉住「它们是**薄**包装」：两个文件里都不许出现 ``sqlite3`` /
    ``hashlib`` / ``backup()`` 这些**实现**字样——逻辑的唯一所有者是那两个 ``.py``
    （派单 §2 第 1 条：「外加两个薄 ``.ps1`` 包装」）。
    """
    wrappers = [SCRIPTS_DIR / "backup.ps1", SCRIPTS_DIR / "restore.ps1"]
    for path in wrappers:
        assert path.is_file(), path
        raw = path.read_bytes()
        assert raw[:3] == b"\xef\xbb\xbf", f"{path.name} 没有 BOM（PowerShell 5.1 会按 GBK 读它）"
        body = raw[3:]
        crlf = body.count(b"\r\n")
        bare = body.count(b"\n") - crlf
        assert bare == 0, f"{path.name} 有 {bare} 个裸 LF（本仓的 .ps1 一律 CRLF）"
        assert crlf > 20, f"{path.name} 只有 {crlf} 行，可能不是一个完整的脚本"
        body.decode("utf-8")

    demo = (SCRIPTS_DIR / "demo.ps1").read_bytes()
    assert demo[:3] == b"\xef\xbb\xbf" and demo[3:].count(b"\n") == demo[3:].count(b"\r\n"), (
        "既有那一款 demo.ps1 的形状变了，本条的「同款」判据要跟着改"
    )

    for path in wrappers:
        body = path.read_bytes()[3:].decode("utf-8")
        # ⚠️ 只扫**代码**那一段（``#>`` 之后）：两个包装的 ``<# .DESCRIPTION #>`` 里
        #    都会**提及** ``sqlite3`` 的 ``backup()`` API、``backup.ps1`` 还**提及**了
        #    ``Get-FileHash``（作为「手工核一遍 sha」的姿势），而提及不是本身
        #    （硬规矩 #109）。⚠️ 本 Task 的第一版扫的是整个文件，当场红在自己写的
        #    说明文字上——那正是硬规矩 #109 点名的失效形态。
        assert body.count("#>") == 1, f"{path.name} 的注释块形状变了，本条的切法要跟着改"
        code = body.split("#>", 1)[1]
        for needle in (
            "Get-FileHash",          # 自己算哈希
            "Copy-Item",             # 自己复制文件
            "[System.IO.File]",      # 自己搬字节
            "[IO.File]",
            "sqlite3",               # 自己连库
            ".backup(",
            "sha256",
        ):
            assert needle not in code, (
                f"{path.name} 的代码段里出现了实现构造 {needle!r}：逻辑的唯一所有者是 "
                "scripts/backup.py 与 scripts/restore.py，包装只负责切目录、"
                "传参数、交回退出码（派单 §2 第 1 条：「两个**薄** .ps1 包装」）"
            )
        assert "python" in code and "$LASTEXITCODE" in code, path.name
        assert "exit $Code" in code, f"{path.name} 没有把退出码交回来"
        # ⚠️ 「薄」的可执行形式：**恰好一次** python 调用（两次就意味着包装里
        #    自己做了一部分逻辑，而那一部分没有守卫）
        assert code.count("\npython ") == 1, path.name
        assert "Set-Location $Backend" in code, (
            f"{path.name} 没有把工作目录切到 backend/：python scripts/….py 要能 import 到 app 包"
        )


def test_backups_are_gitignored_and_none_is_tracked():
    """``backend/backups/`` 进了 ``.gitignore``，且**没有任何备份入库**（派单 §2 第 2 条）。

    三拍，各挡一个不同的失效：

    ① ``.gitignore`` 里有 ``backend/backups/`` 那一行（文本判据）；
    ② **``git check-ignore`` 认它**（⚠️ 这一拍是承重的：一行写错缩进或写成
       ``backups/`` 的忽略规则在①里看起来是对的、而 git 不认；
       而「git 认不认」才是「会不会误提交」的真判据）；
    ③ ``git ls-files backend/backups`` 是**空的**（工作树里没有入库的备份）。

    ⚠️ 派单 §2 第 2 条还要求「**核实** ``.gitignore`` 改后没有把别的放进来」：
    ② 那一拍顺带核实了 ``backend/data/**`` 与两个 ``.db`` **仍然**按原来的口径走
    （``national_standard_2014.csv`` 必须**不**被忽略、``pe_demo.db`` 必须被忽略）。
    """
    ignore_file = REPO_ROOT / ".gitignore"
    assert ignore_file.is_file()
    lines = [
        line.strip() for line in ignore_file.read_text(encoding="utf-8").splitlines()
    ]
    assert "backend/backups/" in lines, lines
    assert not any(line.startswith("*.db") for line in lines), (
        "忽略规则里出现了 *.db 一类宽通配：它会连 tests/** 下将来的夹具库一起吞掉"
    )

    def ignored(relative: str) -> bool:
        got = subprocess.run(
            ["git", "check-ignore", "-q", relative],
            cwd=str(REPO_ROOT), capture_output=True,
        )
        return got.returncode == 0

    assert ignored("backend/backups/pe-20261013T030405Z.db")
    assert ignored("backend/backups/pe-20261013T030405Z.db.sha256")
    assert ignored("backend/pe_demo.db") and ignored("backend/pe.db")
    # ⚠️ 知识资产**必须仍然入库**（那一格是「没有把别的放进来」的反证）
    assert not ignored("backend/data/national_standard_2014.csv")
    assert not ignored("backend/data/prescription/RED-END-ABN-01.yaml")
    assert not ignored("backend/scripts/backup.py")

    tracked = subprocess.run(
        ["git", "ls-files", "backend/backups"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8",
    )
    assert tracked.returncode == 0
    assert tracked.stdout.strip() == "", (
        f"backend/backups/ 下有入库的文件：{tracked.stdout!r}。"
        "一份备份就是一整份库（全校学生的健康档案），而 git 历史删不掉"
    )


def test_the_two_scripts_never_touch_the_real_database_or_the_data_directory(db, tmp_path):
    """**行为面**的禁区守卫（派单 §2 第 6 条）：跑一遍全部动作，禁区一格都不许动。

    ⚠️⚠️ **本条刻意不扫源码**。第一版扫的是「本文件里有没有出现 ``pe.db`` 这个
    字符串常量」，而它当场红给自己看：禁区守卫的**断言消息**必须能点名
    ``backend/pe.db``（否则报错说不清是哪个禁区），于是「点名禁区」与「操作禁区」
    在文本口径下**长得一样**。要区分它们就得排除 docstring、排除 assert 的消息、
    排除 f-string 的片段……一份越写越长的排除清单，正是硬规矩 #109 要防的形状
    （「提及不是本身」，而文本扫描分不清两者）。

    故改成**行为**判据：把三个禁区的实测状态在**动作之前**记下来，跑一遍
    备份 + 恢复 + 篡改 + 拒绝各档，再把状态读回来逐格比对。三格各答一个问题：

    ① ``backend/pe.db`` **仍然不存在**（它不得存在，Global Constraints）；
    ② ``backend/data/`` 下**每一个文件**的 (大小, sha256) 都没变、且**没有新文件**
       （那一片是专家维护的知识资产：国标 CSV / 4 份 YAML / 18 份处方模板，
       一个字节都不许动；而 ``backend/data/seed/`` 恒为 0 文件）；
    ③ ``backend/backups/`` 下**没有多出任何文件**（本文件一律往 ``tmp_path`` 写）。

    ⚠️ ② 的 sha256 是**现算**的、不是从别处读回来的：那四个数据指纹 + 18 个模板指纹
    的正式守卫住在别处（``tests/seed/test_generate.py``），本条要的是
    「**本文件跑完之后**它们还在原样」，故两侧都现算才不同源。
    """
    data_dir = BACKEND_DIR / "data"
    forbidden_db = BACKEND_DIR / "pe.db"
    real_backups = backup.BACKUPS_DIR

    def snapshot(root: pathlib.Path) -> dict[str, tuple[int, str]]:
        if not root.is_dir():
            return {}
        return {
            path.relative_to(root).as_posix(): (
                path.stat().st_size, backup.sha256_of(path)
            )
            for path in sorted(root.rglob("*")) if path.is_file()
        }

    before_data = snapshot(data_dir)
    before_backups = snapshot(real_backups)
    assert forbidden_db.exists() is False, "开工前 backend/pe.db 就不该存在"
    assert before_data, "backend/data/ 是空的？扫描面可能被指错了"

    # --- 跑一遍全部动作（含被拒绝的那些档）-------------------------------------
    made = backup.create_backup(db, tmp_path / "backups", moment=FIXED_MOMENT)
    restore.restore_database(made, db, backups_dir=tmp_path / "backups")
    for url in (
        "sqlite:///" + forbidden_db.as_posix(),
        "sqlite:///" + (BACKEND_DIR / "data" / "x.db").as_posix(),
    ):
        with pytest.raises(backup.BackupError):
            backup.resolve_db_path(url)
    with pytest.raises(backup.BackupError):
        backup.main(["--db-url", "sqlite:///" + forbidden_db.as_posix()])
    with pytest.raises(backup.BackupError):
        restore.main([str(made), "--db-url", "sqlite:///" + forbidden_db.as_posix()])

    # --- ①②③ 三格逐格比对 -----------------------------------------------------
    assert forbidden_db.exists() is False, "backend/pe.db 被建出来了"
    after_data = snapshot(data_dir)
    assert after_data == before_data, (
        "backend/data/** 被动过了："
        f"多了 {sorted(set(after_data) - set(before_data))}、"
        f"少了 {sorted(set(before_data) - set(after_data))}、"
        f"变了 {sorted(k for k in set(after_data) & set(before_data) if after_data[k] != before_data[k])}"
    )
    seed_dir = data_dir / "seed"
    assert not seed_dir.exists() or list(seed_dir.rglob("*")) == [], (
        "backend/data/seed/ 必须恒为 0 文件"
    )
    after_backups = snapshot(real_backups)
    assert after_backups == before_backups, (
        f"backend/backups/ 下多出了文件：{sorted(set(after_backups) - set(before_backups))}"
        "（本文件一律往 tmp_path 写）"
    )


def test_the_two_mains_return_zero_and_print_measured_facts(db, tmp_path, capsys):
    """两个 ``main()`` 的**退出码**与「打印的是实测事实、不是一句写死的话」。

    ⚠️ 派单 §2 第 3 条要「校验不过就拒绝并报错（**退出码非 0**）」，
    故「成功那一档是 0」必须同样被钉住（否则「一律返回 0」也能满足那句话）。

    ⚠️ 打印那三拍各挡一个失效：① ``backup.main`` 打印的 sha256 前 16 位
    **就是**侧车里那一串（于是运维能拿屏幕上的串与文件对一眼）；
    ② ``restore.main`` 打印的表数是**实测**的 30（⚠️ 改前是 29；
       **Plan 08 Task 1** 加了 ``read_audit_log`` 一张 ⇒ ``sqlite_master`` 口径 29 → 30，
       而 ``GET /api/health`` 的 ``Base.metadata`` 口径 28 → **29**——
       两个口径恒差 1，差的那一张是 ``alembic_version``，
       而 ``restore.main`` 自己把这件事印在屏幕上）；
    ③ ``restore.main`` 打印了那句「请先停服务」（⚠️ 锁检测是**尽力**的，
    故那句话是它唯一的补充）。
    """
    backups_dir = tmp_path / "backups"
    assert backup.main([
        "--db-url", "sqlite:///" + db.as_posix(), "--dir", str(backups_dir)
    ]) == 0
    out = capsys.readouterr().out
    made = backups_dir / FIXED_NAME if (backups_dir / FIXED_NAME).is_file() else None
    if made is None:  # main() 用真实时钟，故文件名不是 FIXED_NAME
        candidates = sorted(p for p in backups_dir.iterdir() if p.suffix == ".db")
        assert len(candidates) == 1, candidates
        made = candidates[0]
    assert str(backup.read_sidecar(backup.sidecar_of(made))["sha256"])[:16] in out
    assert str(made.stat().st_size) in out

    _rewrite(db, CHANGED_NAME)
    assert restore.main([
        made.name, "--db-url", "sqlite:///" + db.as_posix(), "--dir", str(backups_dir)
    ]) == 0
    out = capsys.readouterr().out
    assert _semester_name(db) == BACKED_UP_NAME
    assert "请先停服务" in out
    assert "表数 = 30" in out, out
    # ⚠️ 迁移链头的**字面量**（同步面见上面 ``test_the_selfcheck_reports_what_is_really_on_disk``
    #    的 docstring 末段：每加一条迁移，它与 ``HEAD_REVISION`` 一起红、一起改）。
    assert "03331a689ee4" in out, out
    assert "-pre-restore" in out, "后路那一份必须被打印出来，否则运维不知道它在哪"
# ===========================================================================
# Plan 06 Task 15 / 终审 S4-⑤：「备份比当前代码旧」那一格要**响**
# ===========================================================================
#: 旧链那一份库里的**标记行**。⚠️ 字面量：它是「自愈不得以丢数据为代价」
#: 那一拍的期望值（从被测侧读回来的话两侧会一起变，断言恒成立）。
OLD_CHAIN_MARKER = "旧链上的标记行"


def _db_at_previous_head(path: pathlib.Path) -> str:
    """一个**停在 head 前一格**的库；返回它停的那个修订号。

    ⚠️ 修订号**一律从迁移链读**（``ScriptDirectory``），一个字都不写死：
    下一条迁移落地之后本函数自动指向新的「前一格」，
    于是那三条钉字面修订号的既有断言与本条**不会互相拖累**。
    ⚠️ 而 ``_alembic_config`` 读的是 :data:`app.db.session.ALEMBIC_INI`
    （「迁移链住在哪里」的唯一所有者），故本文件也**没有**第二份路径。
    """
    from alembic import command
    from alembic.script import ScriptDirectory

    from app.db.session import _alembic_config

    cfg = _alembic_config("sqlite:///" + path.as_posix())
    script = ScriptDirectory.from_config(cfg)
    head = script.get_heads()[0]
    previous = script.get_revision(head).down_revision
    assert previous is not None, "迁移链只有一格？那一档下本条无从构造"
    command.upgrade(cfg, previous)
    return previous


def _db_at_head(path: pathlib.Path, semester_name: str) -> None:
    """一个**当前代码**（head）的库，里面有一行标记数据。"""
    engine = create_engine("sqlite:///" + path.as_posix())
    init_db(engine)
    with Session(engine) as session:
        session.add(
            Semester(
                name=semester_name, start_date=dt.date(2025, 9, 1),
                end_date=dt.date(2026, 1, 20), weeks=16, is_current=True,
            )
        )
        session.commit()
    engine.dispose()


def test_restore_warns_loudly_when_the_backup_sits_on_an_older_migration_chain(
    tmp_path, capsys
):
    """把一份**旧链**的备份恢复到一个**新链**的库上：退出码 **0**、而那一句 ⚠️ **必须印**。

    ------------------------------------------------------------------------
    ⚠️⚠️ 本条钉的是什么（终审 S4-⑤）
    ------------------------------------------------------------------------
    改前 ``restore.py`` 只**印**恢复后的 ``alembic_version``、**不判**它与
    当前代码的 head 是不是同一个。于是一个不知道那串修订号是什么的运维
    **看不出**这一格，而它的后果是**静默**的：从「恢复完」到「下一次起服务」
    之间，那个库**真的停在旧链上**（⑥ 那一拍就是量这一格），
    此时一个**不经** ``init_db`` 的工具直接读它会看到旧结构。

    ⚠️⚠️ 而它**刻意不是硬失败**（④ 那一拍断言退出码仍然是 **0**）：
    本仓实测过这一档**会自愈**（⑦ 那一拍：起服务时 ``init_db`` 自己
    ``upgrade head``、版本号回到 head、标记数据一行都没丢），
    而一个非 0 退出码会把一条能自愈的路堵死（运维会以为「恢复失败了」
    而去再恢复一次）。⚠️ 故本波只加**打印**，不改 DDL、不改四步的顺序
    （顺序是承重的，§13.10 逐字写了理由）。

    ⚠️ 七拍逐格：① 建一个旧链的库 → ② 备份它 → ③ 建一个 head 的库
    （带一行标记数据）→ ④ 把 ① 恢复到 ③ 上（退出码 0）→
    ⑤ 那一句 ⚠️ 真的印了、且两个修订号都在 → ⑥ 而库里此刻**真的**
    停在旧链上 → ⑦ 起服务（= 再跑一次 ``init_db``）之后它自己补齐了。
    ⚠️ 另有一拍**反空转**（下面那一条测试）：一份 head 的备份恢复上去
    **不得**打那一句 —— 否则「把判据写成恒真」会让本条全绿。
    """
    # ① 一份停在旧链上的库（= 甲方现场「三个月前那次升级之前」的备份）
    old_db = tmp_path / "old.db"
    previous = _db_at_previous_head(old_db)
    heads = restore.code_head_revisions()
    assert heads and previous not in heads, (previous, heads)
    capsys.readouterr()

    # ② 往那一份旧链的库里放一行**标记数据**，再备份它
    #    （走真的 ``backup.create_backup``：侧车也一起写出来）。
    #    ⚠️ 标记行必须在**备份那一侧**：⑦ 那一拍要答的是「自愈之后备份里的数据
    #    一行都没丢」，而不是「被覆盖掉的那一份还在」。
    old_engine = create_engine("sqlite:///" + old_db.as_posix())
    with Session(old_engine) as session:
        session.add(
            Semester(
                name=OLD_CHAIN_MARKER, start_date=dt.date(2025, 2, 24),
                end_date=dt.date(2025, 6, 15), weeks=16, is_current=False,
            )
        )
        session.commit()
    old_engine.dispose()
    old_backups = tmp_path / "backups-old"
    old_backups.mkdir()
    saved = backup.create_backup(old_db, old_backups)
    assert saved.is_file(), saved

    # ③ 一个**当前代码**（head）的库，里面有一行标记数据
    target = tmp_path / "target.db"
    _db_at_head(target, BACKED_UP_NAME)
    assert restore.selfcheck(target)["revision"] in heads

    # ④ 把 ① 那一份恢复到 ③ 上（⚠️ 退出码必须仍然是 0）
    code = restore.main([
        saved.name, "--dir", str(old_backups),
        "--db-url", "sqlite:///" + target.as_posix(),
    ])
    out = capsys.readouterr().out
    assert code == 0, (code, out)

    # ⑤ 那一句 ⚠️ 真的印了，而且两个修订号、「会自己补齐」、「不要直接读」四格都在
    assert "这一份备份的迁移版本比**当前代码旧**" in out, out
    assert previous in out, (previous, out)
    for head in heads:
        assert head in out, (head, out)
    assert "upgrade head" in out and "init_db" in out, out
    assert "不要这样读它" in out, out
    # ⑥ 而库里此刻**真的**停在旧链上（不是印完那一句就自己补齐了）
    assert restore.selfcheck(target)["revision"] == previous, restore.selfcheck(target)

    # ⑦ 起服务（= 再跑一次 init_db）之后它**自己补齐**了，而标记数据一行都没丢
    engine = create_engine("sqlite:///" + target.as_posix())
    init_db(engine)
    engine.dispose()
    after = restore.selfcheck(target)
    assert after["revision"] in heads, after
    assert _semester_name(target) == OLD_CHAIN_MARKER, "自愈不得以丢数据为代价"


def test_a_backup_that_is_already_at_head_does_not_get_that_warning(tmp_path, capsys):
    """**反空转**：一份 head 的备份恢复上去，那一句 ⚠️ **不得**印。

    ⚠️ 少了本条，「把判据写成恒真」（于是每一次恢复都吓人一跳）会让上一条全绿
    —— 而「狼来了」喚多了之后，运维会开始忽略所有的 ⚠️（硬规矩 #50）。
    ⚠️ 它同时钉住了一格**不得退**的行为：一次正常的「备份与恢复」（同一份代码）
    不该多出任何警告。
    """
    source = tmp_path / "source.db"
    _db_at_head(source, BACKED_UP_NAME)
    heads = restore.code_head_revisions()
    assert restore.selfcheck(source)["revision"] in heads

    backups = tmp_path / "backups-head"
    backups.mkdir()
    saved = backup.create_backup(source, backups)

    target = tmp_path / "target2.db"
    _db_at_head(target, CHANGED_NAME)
    capsys.readouterr()

    code = restore.main([
        saved.name, "--dir", str(backups),
        "--db-url", "sqlite:///" + target.as_posix(),
    ])
    out = capsys.readouterr().out
    assert code == 0, (code, out)
    assert "这一份备份的迁移版本比**当前代码旧**" not in out, out
    assert "读不出当前代码的迁移链头" not in out, out
    # ⚠️ 反空转：自检那一格照旧印着修订号（故上面两条 not in 不是因为根本没印）
    assert heads[0] in out, out
    assert _semester_name(target) == BACKED_UP_NAME
# ===========================================================================
# ⚠️⚠️ 保留策略 ``-Keep``（Plan 08 Task 3）
# ===========================================================================
#
# 派单 §2 第 6 条点名的 ② 与 ③ 两格住在这一节：② 删除清单与「侧车跟着删」、
# ③ ``-Keep 0`` 被拒。⚠️ 而删备份是**不可逆**的，故本节另外钉住三件派单没点名、
# 而失效方向更坏的事：判据是**文件名时间戳**而不是 ``LastWriteTime``、
# 认不出的东西**一个都不碰**、以及「拒绝发生在任何一次写之前」。
#
# ⚠️ 一律用 ``tmp_path`` 下的临时库与临时备份目录（与本文件既有的姿势逐字相同），
# ⚠️ 而**「认不出的东西」那一档用 ``backend/backups/`` 里真实存在的那一个文件名**
# （``pe_trial-pre-migration5-…``）：那正是控制者手工做的一份迁移前备份的形状，
# 而它是本件最该保护的一类文件（名字不是 ``backup.py`` 写出来的）。


#: ``--keep`` 的下界。⚠️ **字面量**（不从 ``backup.MIN_KEEP`` 读回来跟自己比）：
#: 那是同源断言，而下界正是「一处改宽、两处一起变」最该挡住的一格。
#: 另有一条**反空转**在下面那条测试里钉住两者一致。
KEEP_FLOOR = 1

#: 五个「快照时刻」（``create_backup`` 的 ``moment`` 可注入，姿势与本文件的
#: :data:`FIXED_MOMENT` 逐字相同）。⚠️ 它们是**期望侧**：从被测代码读回来的话，
#: 「排序其实没排」这件事会两侧一起变、断言恒成立。
STAMPS = (
    "20261001T030000Z",
    "20261002T030000Z",
    "20261003T030000Z",
    "20261004T030000Z",
    "20261005T030000Z",
)


def _moment(stamp: str) -> dt.datetime:
    """``20261001T030000Z`` → 一个 aware 的 UTC 时刻（与 ``TIMESTAMP_FORMAT`` 同宽）。"""
    return dt.datetime.strptime(stamp, backup.TIMESTAMP_FORMAT).replace(
        tzinfo=dt.timezone.utc
    )


def _seed(directory: pathlib.Path, source: pathlib.Path, stamps=STAMPS) -> list[pathlib.Path]:
    """在 ``directory`` 里灌出 ``len(stamps)`` 份备份（**各带一个侧车**）。

    ⚠️ 它走的是**被测代码那一条**（:func:`backup.create_backup`），故侧车是它自己写的、
    形状不会与本文件的期望各说一套。⚠️ 而期望侧（哪几份该被删）一律由 :data:`STAMPS`
    这个字面量算出来，不读返回值。
    """
    made = [
        backup.create_backup(source, directory, moment=_moment(stamp))
        for stamp in stamps
    ]
    for path in made:
        assert backup.sidecar_of(path).is_file(), path
    return made


def _names(directory: pathlib.Path) -> list[str]:
    """目录里**所有**东西的名字（一层），排好序。⚠️ 它是本节的**第三方复核**：
    走 ``os`` 而不是被测代码的返回值，故「删了却报成功」在这一格上藏不住。"""
    return sorted(p.name for p in directory.iterdir())


def test_the_retention_criterion_is_the_filename_timestamp_and_not_the_mtime(db, tmp_path):
    """**判据的单一所有者**：``pe-<UTC ts>.db`` 里那个时间戳，⚠️ 不是 ``LastWriteTime``。

    ⚠️ 派单 §2 第 1 条逐字点了这一格：两者在「**拷进来的旧备份**」上会不一致。
    本条把那一份**真的造出来**：把最旧那一份的 mtime 改成「现在」
    （= 它刚从 U 盘上被拷回来的样子），于是

    * 按**文件名时间戳**排：它仍然是最旧的 ⇒ ``--keep 1`` 会删它；
    * 按 ``LastWriteTime`` 排：它是最新的 ⇒ ``--keep 1`` 会**留下它、删掉真正最新的那一份**。

    两拍各断一次，故「判据偷偷换成 mtime」会让本条红，而红的位置就写着差别在哪。

    ⚠️ **反空转**（两侧不同源）：写侧（:func:`backup.create_backup`）产出的每一个
    文件名都必须被读侧（:data:`backup.BACKUP_NAME_RE`）认出来 —— 否则
    「排序排的是文件名」可能只是因为**一个都没认出来**（于是恒等于「什么都不删」）。
    """
    backups = tmp_path / "backups"
    backups.mkdir()
    made = _seed(backups, db)

    # ⚠️ 把**最旧**那一份的 mtime 改成现在（= 它刚从 U 盘上被拷回来的样子）
    oldest = made[0]
    assert oldest.name == "pe-%s.db" % STAMPS[0]
    now = time.time()
    os.utime(oldest, (now, now))
    assert oldest.stat().st_mtime > made[-1].stat().st_mtime, (
        "夹具没搭对：最旧那一份的 mtime 应当已经被改成「现在」"
    )

    entries, _skipped = backup.list_backup_products(backups)
    got = [entry.path.name for entry in entries]
    # ① 按文件名时间戳：新 → 旧
    assert got == ["pe-%s.db" % stamp for stamp in reversed(STAMPS)], got
    # ② 而**不是**按 mtime（那一档下刚被拷回来的最旧那一份会排到队首）
    assert got[0] != oldest.name, got
    assert got[-1] == oldest.name, got

    # ⚠️ 反空转：写侧产出的每一个名字，读侧那个正则都认（两侧不同源）
    for path in made:
        assert backup.BACKUP_NAME_RE.match(path.name), path.name
    # ⚠️ 并钉住「-pre-restore 那一份也在同一个池子里」（派单没点名，而它是
    #    restore.py 自动留的后路；把它排除在外等于给 backups/ 又留一个永不收缩的角落）
    net = backup.create_backup(db, backups, moment=_moment("20261006T030000Z"),
                               label="-pre-restore")
    assert net.name == "pe-20261006T030000Z-pre-restore.db", net.name
    entries2, _ = backup.list_backup_products(backups)
    assert entries2[0].path.name == net.name, [e.path.name for e in entries2]
    assert entries2[0].label == "pre-restore", entries2[0]
    # ⚠️ 再钉一格：那个下界的字面量与被测代码一致（KEEP_FLOOR 是期望侧）
    assert backup.MIN_KEEP == KEEP_FLOOR


def test_prune_deletes_the_oldest_and_takes_their_sidecars_with_them(db, tmp_path, capsys):
    """**派单 §2 第 6 条 ②**：删除清单逐个打印（含字节数与 sha），⚠️ 侧车跟着一起删。

    五拍，各挡一个不同的失效：

    ① 该删的那几份**真的不在了**（走 :func:`_names`，不读返回值）；
    ② 该留的那几份**连同侧车**都还在；
    ③⚠️ **那几份的侧车也不在了** —— 少这一拍，一个「只删 ``.db``」的实现会全绿，
       而它留下的孤儿侧车会让下一次恢复报「备份文件不存在」（运维看着侧车会以为备份还在）；
    ④ 清单里**逐个**印出了文件名、字节数与 sha256 的前 16 位（派单逐字要求）；
    ⑤ 印出来那个 sha 与 :func:`backup.sha256_of` 现算的**逐字相同**
       （⚠️ 反空转：少了它，「清单里印一个假的 sha」不会红）。
    """
    backups = tmp_path / "backups"
    backups.mkdir()
    made = _seed(backups, db)
    doomed = made[:3]          # 最旧的三份
    kept = made[3:]            # 最新的两份
    # ⚠️ 删之前就把它们的两格事实**现算**下来（删完就 stat 不到了）
    facts = {path.name: (path.stat().st_size, backup.sha256_of(path)) for path in doomed}

    result = backup.prune_backups(backups, keep=2)

    names = _names(backups)
    # ①
    for path in doomed:
        assert path.name not in names, names
        # ③
        assert (path.name + backup.SIDECAR_SUFFIX) not in names, names
    # ②
    for path in kept:
        assert path.name in names, names
        assert (path.name + backup.SIDECAR_SUFFIX) in names, names
    assert names == sorted(
        [p.name for p in kept] + [p.name + backup.SIDECAR_SUFFIX for p in kept]
    ), names

    out = capsys.readouterr().out
    # ④⑤ 逐个打印文件名 + 字节数 + sha256 的前 16 位，⚠️ 而两格都是**真的**
    for name, (size, digest) in facts.items():
        assert name in out, (name, out)
        assert "%10d B" % size in out, (name, size, out)
        assert digest[:16] in out, (name, digest[:16], out)
    # ⑥ 返回值与磁盘对账（第三方复核）
    #    ⚠️ 顺序是「新→旧」：删除面就是排好序那个列表的尾巴，故它逐个删过去的次序
    #    与 :data:`STAMPS` 的正序**相反**。期望侧因此两个都断：集合（「删了哪几份」，
    #    本条真正要钉的）与顺序（「与清单逐个对得上」）。
    assert sorted(result["deleted"]) == sorted(p.name for p in doomed), result
    assert result["deleted"] == [p.name for p in reversed(doomed)], result
    assert result["deleted_sidecars"] == 3, result
    assert result["remaining"] == 2 == len([n for n in names if n.endswith(".db")]), result


def test_prune_prints_the_whole_list_before_it_deletes_anything(db, tmp_path):
    """**顺序是承重的**：先打印清单 → 再删 → 删完复核（与 :mod:`retention` 同一条口径）。

    ⚠️ 判据是**行序**，不是「三样都印了」：一个「先删、再打印它删了什么」的实现
    在「三样都印了」那一档下会全绿，而它恰好把派单要的那一格弄反了 ——
    运维要在**东西还在**的时候看见清单（那时他还能 Ctrl-C，还能先去核一眼那一份是什么）。

    ⚠️ 复核那一句必须排在**最后**（它答的是「删完对不对得上」）。
    """
    backups = tmp_path / "backups"
    backups.mkdir()
    made = _seed(backups, db)

    lines: list[str] = []
    backup.prune_backups(backups, keep=2, emit=lines.append)

    def index_of(needle: str) -> int:
        hits = [i for i, line in enumerate(lines) if needle in line]
        assert hits, (needle, lines)
        return hits[0]

    notice = index_of("下面这一步**不可逆**")
    first_doomed = index_of(made[0].name)
    last_doomed = max(index_of(path.name) for path in made[:3])
    started = index_of("开始删…")
    reconciled = index_of("实删")
    assert notice < first_doomed <= last_doomed < started < reconciled, lines
    # ⚠️ 反空转：清单里确实有**三份**（不是只印了一个标题）
    assert sum(1 for path in made[:3] if path.name in "\n".join(lines)) == 3
    assert "复核" in "\n".join(lines[reconciled:]), lines


def test_keep_zero_is_refused_before_a_single_write(db, tmp_path, capsys):
    """**派单 §2 第 6 条 ③**：``-Keep 0`` 被拒 + 退出码非 0，⚠️ 而那是在**任何一次写之前**。

    三拍，各挡一个不同的失效：

    ① :func:`backup.prune_backups` 直接调也拒（它是第二重，防别的调用方）；
    ② :func:`backup.main` 走整条 CLI 也拒，⚠️ 且**这一次备份也没有做**
       （目录里**一个新文件都没有**）—— 少这一拍，一个「先备份、再在 prune 里拒」
       的实现会全绿，而它已经往盘上写了一份含全校学生健康数据的副本；
    ③ 负数同档（``-Keep -1`` 的字面意思更荒唐，而它同样不该被当成「删到最后剩一份」）。

    ⚠️ 报错里必须说清「0 的字面意思是一份都不留」与「要清空请自己删」——
    一个只说「参数非法」的报错会让运维改成 ``-Keep 1``，而那**不是**他想要的。
    """
    backups = tmp_path / "backups"
    backups.mkdir()
    before = _names(backups)

    # ①
    for bad in (0, -1, -7):
        with pytest.raises(backup.BackupError) as excinfo:
            backup.prune_backups(backups, keep=bad, emit=lambda _line: None)
        message = str(excinfo.value)
        assert "一份都不留" in message, message
        assert "自己删" in message, message
    assert _names(backups) == before

    # ②（走 CLI；退出码由 __main__ 那一档的 BackupError → 2 给，本拍验它抛）
    for bad in ("0", "-1"):
        with pytest.raises(backup.BackupError):
            backup.main([
                "--db-url", "sqlite:///" + db.as_posix(),
                "--dir", str(backups), "--keep", bad,
            ])
    assert _names(backups) == before, (
        "--keep 0/-1 那一档动了目录：拒绝必须发生在**任何一次写之前**，"
        "否则盘上已经多了一份含全校学生健康数据的副本"
    )

    # ③⚠️ 反空转：同一条命令**去掉** --keep 就照常备份（故上面那两条不是因为
    #    命令本身就跑不通）
    assert backup.main([
        "--db-url", "sqlite:///" + db.as_posix(), "--dir", str(backups),
    ]) == 0
    assert len(_names(backups)) == 2, _names(backups)


def test_the_default_still_deletes_nothing_and_prints_nothing_about_retention(db, tmp_path, capsys):
    """⚠️ **缺省行为一格不变**（派单 §2 第 1 条逐字要求）：不给 ``-Keep`` = 一份都不删。

    三拍：① 目录里只多了这一次的**两个**文件（``.db`` + 侧车）；
    ② 输出里**一个字**都没提保留策略（⚠️ 少这一拍，一个「缺省也印一段清单」的实现
    会全绿，而那一段会把「今天到底删没删」这件事弄糊）；
    ③ 连着做四次备份，八份**全在**（那就是 Task 3 之前那一格的形状：跑一年就是 365 份）。

    ⚠️ 那四次里的前三次走 :func:`backup.create_backup` 而**不是** ``main``：
    ``backup_name`` 只到**秒**，而四次 ``main()`` 在本机上跑在同一秒里 ⇒ 后三次
    **同名覆盖**第一次（那是 :func:`backup.create_backup` docstring 里逐字记着的一个
    已知行为），于是「连跑三次应当有六份」这个期望会红在**夹具**上、不是红在被测代码上。
    ⚠️ 本条的第一版正是这么红的，故 ``moment`` 一律注入。
    """
    backups = tmp_path / "backups"
    backups.mkdir()
    for stamp in STAMPS[:3]:
        backup.create_backup(db, backups, moment=_moment(stamp))
    assert len(_names(backups)) == 6, _names(backups)   # ③ 三份 .db + 三个侧车

    capsys.readouterr()
    assert backup.main([
        "--db-url", "sqlite:///" + db.as_posix(), "--dir", str(backups),
    ]) == 0
    out = capsys.readouterr().out
    names = _names(backups)
    assert len(names) == 8, names                       # ① 只多了这一次的 .db + 侧车
    assert all(n.endswith(".db") or n.endswith(backup.SIDECAR_SUFFIX) for n in names), names
    assert "保留策略" not in out and "--keep" not in out, out   # ②
    # ⚠️ 反空转：那一次备份**真的做了**（故②不是因为 main 压根没跑）
    assert "sha256 " in out and "侧车" in out, out


def test_prune_never_touches_what_it_does_not_recognise(db, tmp_path):
    """**认不出的一律不碰**（失效方向是「多留一份」，不是「删错一份」）。

    四类各一份，``--keep 1`` 之后**一个都不许少**：

    * 控制者手工做的那一份迁移前备份（``pe_trial-pre-migration5-…``）——
      ⚠️ 它是**真实存在**在 ``backend/backups/`` 里的形状，而它的名字**不是**
      ``backup.py`` 写出来的；
    * 一个**孤儿侧车**（``.sha256`` 而它那份 ``.db`` 不在）—— ⚠️ 本策略**不**顺手删它，
      而它会被**单独点出来**（运维该知道：它会让下一次恢复报「备份文件不存在」）；
    * 一个子目录；
    * 一个别的文件。
    """
    backups = tmp_path / "backups"
    backups.mkdir()
    made = _seed(backups, db)

    foreign = backups / "pe_trial-pre-migration5-20261017-201257.db"
    foreign.write_bytes(db.read_bytes())
    orphan = backups / "pe-20250101T000000Z.db.sha256"
    orphan.write_bytes(b"sha256=" + b"0" * 64 + b"\nbytes=1\n")
    (backups / "sub").mkdir()
    (backups / "notes.txt").write_text("别的东西", encoding="utf-8")

    lines: list[str] = []
    result = backup.prune_backups(backups, keep=1, emit=lines.append)
    out = "\n".join(lines)

    names = _names(backups)
    assert foreign.name in names, names
    assert orphan.name in names, names
    assert "sub" in names and "notes.txt" in names, names
    assert made[-1].name in names and (made[-1].name + backup.SIDECAR_SUFFIX) in names, names
    for path in made[:-1]:
        assert path.name not in names, names
        assert (path.name + backup.SIDECAR_SUFFIX) not in names, names
    # ⚠️ 那四类**逐个**被打印出来（不是静默跳过）
    for needle in (foreign.name, orphan.name, "sub", "notes.txt"):
        assert needle in out, out
    # ⚠️ 而孤儿侧车有它自己那一句（与「认不出形状」那一句**不同**：
    #    侧车不是认不出，它是它那份 .db 不在了）
    assert "孤儿侧车" in out, out
    assert sorted(result["skipped"]) == sorted(
        [foreign.name, orphan.name, "sub", "notes.txt"]
    ), result


def test_prune_refuses_a_backup_dir_that_is_not_only_for_backups(db, tmp_path):
    """**删除面的禁区守卫**：``--dir`` 指到知识资产目录 / 源码目录一律拒。

    ⚠️ 三档（``backend/data`` / ``backend`` / 仓库根），⚠️ 而**承重的那一格**是
    ``backend/data``：它是**入库**的，一份写进去的整库副本会被下一次 ``git add``
    提交进版本控制，而 git 历史删不掉（与 :func:`test_backups_are_gitignored_and_none_is_tracked`
    同一条理由，只是方向相反 —— 那一条挡「备份目录被提交」，本条挡「备份写进被提交的目录」）。

    ⚠️ 而它排在**任何一次写之前**：本 Task 的探针当场撞出来过那一格
    （改前 ``--dir backend/data --keep 1`` 会先写一份整库副本进去、然后才被拒）。
    """
    from app.config import BACKEND_DIR as _BACKEND

    for bad in ((_BACKEND / "data"), (_BACKEND / "data" / "prescription"),
                _BACKEND, _BACKEND.parent):
        with pytest.raises(backup.BackupError) as excinfo:
            backup.prune_backups(bad, keep=1, emit=lambda _line: None)
        assert "只放备份" in str(excinfo.value) or "知识资产" in str(excinfo.value), (
            bad, str(excinfo.value)
        )
    # ⚠️ 走 CLI 同档，且**没有**写任何东西进去
    data = _BACKEND / "data"
    before = _names(data)
    with pytest.raises(backup.BackupError):
        backup.main([
            "--db-url", "sqlite:///" + db.as_posix(),
            "--dir", str(data), "--keep", "1",
        ])
    assert _names(data) == before, "拒绝发生在写之后：backend/data/ 被动过了"
    # ⚠️ 反空转：create_backup 自己那一道也在（它是第一重）
    with pytest.raises(backup.BackupError):
        backup.create_backup(db, data)
    assert _names(data) == before


def test_prune_reports_a_reconciled_summary_and_a_full_dir_deletes_nothing(db, tmp_path):
    """**两份都要**：现存 ≤ ``--keep`` 时**一份都不删**，而那一档也要**说清楚**。

    ⚠️ 「一份都不删」那一档**不打印清单**（没有要删的东西，印一个空清单只会让运维
    以为脚本卡住了），而**要打印一句「现存 N 份 ≤ --keep M」**——
    于是「跑过了、而它决定不删」与「压根没跑」在输出上可分辨。
    """
    backups = tmp_path / "backups"
    backups.mkdir()
    made = _seed(backups, db)
    before = _names(backups)

    lines: list[str] = []
    result = backup.prune_backups(backups, keep=len(made) + 3, emit=lines.append)
    out = "\n".join(lines)

    assert _names(backups) == before, "现存 ≤ keep 那一档删了东西"
    assert result["deleted"] == [] and result["deleted_sidecars"] == 0, result
    assert result["found"] == len(made) and result["remaining"] == len(made), result
    assert "一份都不删" in out, out
    assert "不可逆" not in out, out      # ⚠️ 没有要删的东西 ⇒ 不该吓运维


def test_the_keep_flag_is_passed_through_by_the_thin_wrapper_only_when_given():
    """薄包装 ``backup.ps1`` 的 ``-Keep`` 是**透传**，⚠️ 而缺省值**不在它那里**。

    ⚠️ 姿势与 ``tests/test_retention.py`` 的
    ``test_neither_ps1_restates_a_retention_window`` 逐字同族：包装里**一个数字都不许有**
    （``MIN_KEEP`` / 缺省「不删」都只有 ``backup.py`` 一个所有者），
    而「没给」与「给了一个值」在 argparse 那侧必须可分辨
    （⇒ 参数类型是 ``string`` 而不是 ``int``，且**只在非空时才往下传**）。
    """
    raw = (SCRIPTS_DIR / "backup.ps1").read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf", "backup.ps1 没有 BOM"
    body = raw[3:].decode("utf-8")
    assert body.count("#>") == 1
    code = body.split("#>", 1)[1]

    assert '[string]$Keep = ""' in code, code
    assert '[int]$Keep' not in code, "参数类型是 int 的话「没给」与「给了 0」就分不开了"
    assert 'if (-not [string]::IsNullOrEmpty($Keep)) { $Arguments += @("--keep", $Keep) }' in code, code
    # ⚠️ 参数面**恰好三个**，而 ``Keep`` 是 ``string``（不是 ``int``）
    assert re.findall(r"^\s*\[(string|int|switch)\]\$(\w+)", code, re.M) == [
        ("string", "DbUrl"), ("string", "Dir"), ("string", "Keep"),
    ], code
    # ⚠️ 包装里**一个与保留策略有关的数字都没有**（下界与缺省都只有 backup.py 一个所有者）。
    #    ⚠️ 而它**点名所有者**（``MIN_KEEP``）是允许的 —— 那是一个**指针**、不是复述：
    #    ``retention.ps1`` 对 ``AUDIT_MIN_DAYS`` 逐字同一条姿势（改下界的人只改一处，
    #    包装那一行不会因此变假）。要挡的是「包装里自己写了一个数」。
    for digit in "0123456789":
        assert ('$Keep = "' + digit) not in code, (digit, code)
        assert ('"--keep", "' + digit) not in code, (digit, code)
    assert "MIN_KEEP" in code, "包装连所有者都不点名了（那一格是运维唯一的线索）"
    # ⚠️ 反空转：那个下界的字面量在**被测代码**里（否则上一条可能只是「两边都没写」）
    owner = (SCRIPTS_DIR / "backup.py").read_text(encoding="utf-8")
    assert "MIN_KEEP = %d" % KEEP_FLOOR in owner, KEEP_FLOOR
def test_the_post_delete_reconciliation_has_teeth(db, tmp_path, monkeypatch):
    """⚠️⚠️ **删完那一次复核不是装饰**（本 Task 的定点变异 **M6** 当场量出来的缺口）。

    M6 = 把 :func:`backup.prune_backups` 里「删完复核」那**整段**去掉、只留下
    重新枚举那一行。改前改后本文件的其余守卫**全绿** —— 因为那一段是**自检**，
    在正常路径上恒不触发（它触发就意味着已经出了 bug）。⚠️ 于是「复核在不在」
    这件事只有**制造一次不一致**才可观测。本条造两档，各对应一个真实的失效形态：

    ① **一个 ``unlink`` 静默地什么都没做** ⇒ 预告要删的那一份仍在目录里。
       ⚠️ 那一档在 Windows 上不是假想：一个还握着句柄的进程会让删除失败，
       而一个「捕获异常然后继续」的实现会**报成功**（:mod:`backup` 的 docstring 里
       逐字记着同族的 ``PermissionError: [WinError 32]`` 那一格）；
    ② **侧车没跟着删掉** ⇒ 目录里留下一个指不到东西的 ``.sha256``。
       ⚠️ 那一档的后果是运维的：下一次恢复会报「备份文件不存在」，
       而他看着那个侧车会以为备份还在。

    ⚠️ 两档都断言报错里带「复核失败」与**那一个文件名** —— 一句「删除失败」
    不足以让运维知道该去核哪一份。
    """
    real_unlink = pathlib.Path.unlink

    # ---- ① 一个 unlink 静默失败 ----
    first = tmp_path / "backups-a"
    first.mkdir()
    made = _seed(first, db)
    victim = made[0]                                  # 最旧那一份（--keep 2 下它该被删）
    kept = made[-1]

    def fake_unlink(self, *args, **kwargs):
        if self.name == victim.name:
            return None                               # ⚠️ 静默地什么都不做
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "unlink", fake_unlink)
    with pytest.raises(backup.BackupError) as excinfo:
        backup.prune_backups(first, keep=2, emit=lambda _line: None)
    message = str(excinfo.value)
    assert "复核失败" in message, message
    assert victim.name in message, message
    # ⚠️ 反空转：那一份**确实**还在（故上面那条不是因为别的原因抛的）
    assert victim.is_file() and kept.is_file()
    monkeypatch.setattr(pathlib.Path, "unlink", real_unlink)

    # ---- ② 侧车没跟着删 ----
    second = tmp_path / "backups-b"
    second.mkdir()
    _seed(second, db)
    monkeypatch.setattr(
        backup, "sidecar_of",
        lambda path: path.with_name(path.name + ".not-the-sidecar"),
    )
    with pytest.raises(backup.BackupError) as excinfo:
        backup.prune_backups(second, keep=2, emit=lambda _line: None)
    message = str(excinfo.value)
    assert "复核失败" in message and "侧车" in message, message
    # ⚠️ 反空转：真的留下了孤儿侧车（⚠️ 数的是「``.db`` 不在了」的那些，
    #    而不是所有 ``.sha256``——留下来的那两份**该有**自己的侧车）
    orphans = [
        p.name for p in second.iterdir()
        if p.name.endswith(backup.SIDECAR_SUFFIX)
        and not (second / p.name[: -len(backup.SIDECAR_SUFFIX)]).is_file()
    ]
    assert len(orphans) == 3, orphans

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
import base64
import datetime as dt
import hashlib
import importlib.util
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.auth import passwords
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
    """**结构侧**的两格：不整份搬字节、不加依赖（派单 §2 第 2 条与 §0 的「新增依赖 = 0」）。

    ① 「把一个库文件整份搬到别处」那一族（``shutil`` 的 ``copyfile`` / ``copy`` /
       ``copy2`` / ``copytree`` / ``move`` / ``rmtree``）在两个脚本里**一次都不出现**：
       备份与恢复一律走 SQLite 的 ``backup()`` API，而复制文件在写进行中会坏
       （逐字理由见 ``backup.py`` 的模块 docstring 第一节）。
       ⚠️ 判据是 **AST 上的属性名**而不是文本搜索：两个脚本的 docstring 里都
       **提及**了 ``shutil.copyfile``（解释为什么不用它），而提及不是本身（硬规矩 #109）。
    ①b ⚠️ **唯一的那一个例外被钉到「哪一个属性 + 在哪一个函数里 + 出现几次」三格**
       （Plan 08 Task 3）：``shutil.copyfileobj`` 在 ``restore.py`` 里出现**恰好一次**，
       而它必须住在 ``_copy_corrupt_target_aside`` 里 —— 那一个函数搬的是
       「**已经不是一个库**」的目标文件（``backup()`` 读不了它；⚠️ 而**跳过**后路
       等于让步 ④ 把那些字节静默覆盖掉，一次不可逆的销毁），逐字理由见它自己的
       docstring。⚠️ 于是把这个例外**挪到别处**（例如挪进步 ④ 去覆盖目标库）、
       **换成 ``copyfile``**、或**删掉**，三档都会当场红：例外只有一个住址，
       而那个住址不在正常的备份/恢复路径上。
       ⚠️ ``backup.py`` 里连这一个例外都**没有**（``shutil`` 一次都不出现）。
       ⚠️ 如实记：本守卫**不**判 ``open(…, "wb")``——``backup.py`` 的
       :func:`encrypt_file`（写那 60 字节的产物头）与 :func:`decrypt_container`
       （把解出来的明文写进系统临时目录）都必须自己写字节，
       而那两处搬的**不是一个库文件**（改前本 docstring 声称也判它，是**说过头了**）。
    ② 两个脚本 import 的**非 ``app.*``** 顶层模块全部在 :data:`sys.stdlib_module_names`
       里（``sqlalchemy`` 除外：它是既有依赖，不是本波加的）。
       ⚠️ 于是「本波新增依赖 = 0」在**这两个脚本上**是可执行的，
       而不只是 ``tests/test_dependencies.py`` 那份清单上的一个数
       （那一份钉的是 ``pyproject.toml``，钉不到「有人在一个脚本里 ``import zstd``」）。
    """
    #: 每个脚本里 ``shutil.<属性>`` 的**允许清单**：``{脚本名: {(属性, 所在函数)}}``。
    #: ⚠️ 它是「恰好等于」而不是「子集」（反空转）：删掉那一个例外同样红。
    allowed = {
        "backup": set(),
        "restore": {("copyfileobj", "_copy_corrupt_target_aside")},
    }
    #: ⚠️ 这一族**无论住在哪儿**都一律不许出现（它们是「把一个库整份搬走」的形状）。
    absolutely_never = {"copyfile", "copy", "copy2", "copytree", "move", "rmtree"}
    for name in ("backup", "restore"):
        source = (SCRIPTS_DIR / f"{name}.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
        used: set[tuple[str, str]] = set()
        for func in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
            for node in ast.walk(func):
                if (isinstance(node, ast.Attribute)
                        and isinstance(node.value, ast.Name)
                        and node.value.id == "shutil"):
                    used.add((node.attr, func.name))
        banned = sorted(x for x in used if x[0] in absolutely_never)
        assert not banned, (
            f"{name}.py 用了 shutil 的整份搬运 {banned}："
            "备份与恢复一律走 SQLite 的 backup() API（复制文件在写进行中会坏）"
        )
        assert used == allowed[name], (
            f"{name}.py 里的 shutil 用法与允许清单不符：实到 {sorted(used)}、"
            f"允许 {sorted(allowed[name])}。⚠️ 那一个例外的全部理由是「目标库已经"
            "不是一个库、backup() 读不了它」，故它只能住在 "
            "_copy_corrupt_target_aside 里；正常的备份/恢复路径上"
            "**一个字节都不许自己搬**"
        )
        if name == "restore":
            assert "shutil" in imported, sorted(imported)
        else:
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
# ===========================================================================
# ⚠️⚠️ 可选加密（Plan 08 Task 3）
# ===========================================================================
#
# 派单 §2 第 6 条点名的 ①④⑤⑥ 四格住在这一节：① 明文档与加密档的**产物形状**、
# ④ 缺密钥时那段 ⚠️ 在**且产物仍是可用的明文档**、⑤ 密钥字面量不出现在任何入库文件里、
# ⑥ 密钥的**任何一部分**都不被打印。⚠️ 而「密钥不对 / 篡改密文 / 篡改 MAC」那三档
# 的**端到端**取证（走 restore）在下一节（派单 §2 第 4 条），本节只钉 backup 这一侧。
#
# ⚠️⚠️ **密钥纪律（派单 §3）**：下面这个口令是**假的**，它只为测试与探针存在，
# 不是任何真密钥、也从来没在任何一台机器上保护过任何一份真数据。它被刻意写得
# **一看就是假的**（``not-a-real-key-``），而 :func:`test_the_fake_passphrase_lives_in_exactly_one_tracked_file`
# 会去全仓扫它 —— 于是「有人把一个真口令抄进了测试」那一档会红在那一条上。
FAKE_PASSPHRASE = "not-a-real-key-用于测试"

#: 另一个**假**口令，只为「密钥不对」那一档存在（⚠️ 它同样是假的）。
OTHER_FAKE_PASSPHRASE = "also-not-a-real-key-用于测试"


def passphrase_forms(passphrase: str) -> dict[str, str]:
    """「密钥的**任何一部分**都不被打印」那一格的**判据**：口令的六种派生形态。

    ⚠️⚠️ 它是一个**函数**而不是内联在守卫里的一个 dict，而理由是**实测**出来的
    （Plan 08 Task 3 的定点变异 **M6b**）：改前那六种形态内联在
    :func:`test_no_part_of_the_passphrase_is_ever_printed` 里，把其中**五种删掉、
    只留「本体」**之后 —— **62 条全绿，一条都没红**。于是「放宽这一格的判据」
    是一个**静默**的动作，而那一条守卫要挡的失效（口令的一种派生形态进了日志）
    恰好也是静默的。⇒ 判据收进这里（唯一所有者），并由
    :func:`test_the_six_passphrase_forms_the_print_guard_scans_are_pinned`
    钉住它的**形状**（几种、标签逐字、每一种都真的由口令算出来、
    而那一条打印守卫**确实调它**）。

    ⚠️ 六种形态各挡一档不同的「顺口印出来」：本体（``print(passphrase)``）、
    base64（``-Key`` 那一族命令行参数的常见写法）、十六进制（调试时最常打的一种）、
    sha256 全串与前 16 位（「印一个指纹好让运维对一眼」——⚠️ 而口令的熵低，
    一个可离线枚举的口令的 sha256 等于把口令交出去）、倒序
    （挡「把口令反过来印就当 anonymize 了」那一档）。
    """
    digest = hashlib.sha256(passphrase.encode("utf-8")).hexdigest()
    return {
        "本体": passphrase,
        "base64": base64.b64encode(passphrase.encode("utf-8")).decode(),
        "十六进制": passphrase.encode("utf-8").hex(),
        "sha256": digest,
        "sha256[:16]": digest[:16],
        "倒序": passphrase[::-1],
    }

#: AES 那一个原语。⚠️ 它住在 ``backend/scripts/`` 下，由既有的
#: ``backend/scripts/*.ps1 text eol=crlf`` 那一条 gitattributes 规则盖住
#: （⚠️ **规则一个字都没改**，见 ``tests/test_serve.py`` 那份清单上的注释）。
AES_PS1 = SCRIPTS_DIR / "aes_cbc.ps1"


def _powershell() -> str:
    """本机的 ``powershell``；没有就跳过（本仓的目标平台是 Windows）。"""
    found = shutil.which("powershell") or shutil.which("powershell.exe")
    if not found:
        pytest.skip("本机没有 powershell：加密那一族的可执行判据跑不了")
    return found


@pytest.fixture(autouse=True)
def _backup_kdf_at_the_floor(monkeypatch):
    """把备份 KDF 的迭代次数压到**下界**（口径所有者是 ``app.auth.passwords``）。

    ⚠️ **为什么**：那一个 KDF 的缺省值是 600 000 次（本机实测一次约 0.25 s），
    而本节有二十几次加密/验 MAC，每次都派生一到两遍 ⇒ 按缺省值跑本文件会从
    15 s 变成半分钟以上。⚠️ 而**压到下界**（而不是压到 1 000）是有意的：
    下界是 ``PBKDF2_MIN_VERIFY_ITERATIONS``，而 :func:`backup._check_kdf_iterations`
    会拒任何低于它的值 —— 于是「测试跑的那一档」与「生产跑的那一档」在
    **同一道界之内**，本节因此不会因为一个界外的值而走到一条生产上走不到的路。

    ⚠️ **而缺省值本身另有一条钉**：
    :func:`test_the_backup_kdf_default_is_the_password_policy_default`
    （它 ``delenv`` 掉本 fixture 设的那个变量，故两侧不同源）。
    """
    monkeypatch.setenv(
        backup.BACKUP_KDF_ITER_ENV_VAR,
        str(passwords.PBKDF2_MIN_VERIFY_ITERATIONS),
    )


def _encrypted(db: pathlib.Path, directory: pathlib.Path, *,
               moment: dt.datetime | None = None) -> pathlib.Path:
    """一份**加密**备份（姿势与 :func:`_seed` 逐字同款，只是多给一个口令）。"""
    return backup.create_backup(
        db, directory,
        moment=moment or dt.datetime(2026, 10, 14, 3, 4, 5, tzinfo=dt.timezone.utc),
        passphrase=FAKE_PASSPHRASE,
    )


# --------------------------------------------------------------- ① 产物形状


def test_the_encrypted_product_is_self_describing_and_opaque(db, tmp_path):
    """**派单 §2 第 6 条 ①**：加密档的产物形状逐格对账，⚠️ 而它**打不开**。

    七拍，各钉布局里的一格（布局的正文在 :mod:`backup` 模块 docstring
    「可选加密」那一节，本条是它的**可执行**形式）：

    ① 魔数 ``PEBACKUP``（⚠️ 与 ``SQLite format 3\\0`` 不可能撞，故
       :func:`backup.product_kind` 的三分法是**互斥**的）；
    ② 版本 / 分组密码 id / KDF id / 保留字节四个单字节字段；
    ③ 迭代次数（大端 uint32）== 这一个进程解析出来的那一个；
    ④ 盐与 IV 各 16 字节、而头上那两格宽度字段与它们**自洽**；
    ⑤ 头上那个「明文字节数」== 同一份库的**明文**备份的字节数；
    ⑥ 总长 == 头 60 + 密文（明文向上补到 16 的倍数、且**至少多一个整块** = PKCS7）+ 尾 32；
    ⑦⚠️ **不用任何密钥读不出里面那一行** —— 那一格是本件存在的全部理由
       （Plan 07 Task 9 的实测是：明文档不用密钥就读出 60 人姓名与出生日期）。
    """
    _powershell()
    backups = tmp_path / "backups"
    backups.mkdir()
    plain = backup.create_backup(db, backups, moment=FIXED_MOMENT)
    enc = _encrypted(db, backups)

    raw = enc.read_bytes()
    plain_len = plain.stat().st_size
    head, body, tail = (raw[: backup.CONTAINER_HEADER_BYTES],
                        raw[backup.CONTAINER_HEADER_BYTES:-backup.CONTAINER_MAC_BYTES],
                        raw[-backup.CONTAINER_MAC_BYTES:])
    info = backup.describe_container(enc)

    # ①
    assert head[:8] == backup.CONTAINER_MAGIC == b"PEBACKUP", head[:8]
    assert backup.product_kind(enc) == backup.KIND_ENCRYPTED
    assert backup.product_kind(plain) == backup.KIND_PLAINTEXT
    assert not raw.startswith(backup.SQLITE_MAGIC), "加密档的头竟然仍是 SQLite 的格式串"
    # ②
    assert head[8] == backup.CONTAINER_VERSION == 1
    assert head[9] == backup.CIPHER_ID_AES_256_CBC == 1
    assert head[10] == backup.KDF_ID_PBKDF2_HMAC_SHA256 == 1
    assert head[11] == backup.CONTAINER_RESERVED == 0
    # ③（⚠️ 期望侧走 resolve_kdf_iterations，它是那个数的唯一解析方）
    assert int.from_bytes(head[12:16], "big") == backup.resolve_kdf_iterations()
    assert info["iterations"] == backup.resolve_kdf_iterations()
    # ④
    assert int.from_bytes(head[16:18], "big") == backup.CONTAINER_SALT_BYTES == 16
    assert int.from_bytes(head[18:20], "big") == backup.CONTAINER_IV_BYTES == 16
    assert len(info["salt"]) == 16 and len(info["iv"]) == 16
    # ⑤
    assert int.from_bytes(head[20:28], "big") == plain_len == info["plaintext_len"]
    # ⑥
    assert len(head) == backup.CONTAINER_HEADER_BYTES == 60
    assert len(tail) == backup.CONTAINER_MAC_BYTES == 32
    assert len(body) == plain_len - plain_len % 16 + 16, (len(body), plain_len)
    assert len(raw) == 60 + len(body) + 32
    # ⑦⚠️ 承重的一格：不用密钥**读不出来**
    connection = sqlite3.connect(enc.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute("SELECT name FROM semester WHERE id = 1").fetchone()
    finally:
        connection.close()
    # ⚠️ 反空转：同一份库的**明文**备份不用密钥**读得出来**（故⑦不是因为夹具坏了）
    assert _semester_name(plain) == BACKED_UP_NAME


def test_the_sidecar_covers_the_product_itself_not_the_plaintext(db, tmp_path):
    """**派单 §2 第 5 条的裁定**：侧车算的是**产物文件本身**（= 头 + 密文 + MAC）。

    三拍：① 加密档的侧车两格与 ``sha256_of(产物)`` / ``stat().st_size`` 逐字相同；
    ② 它**不等于**同一份库的明文备份的侧车（⚠️ 反空转：少了这一拍，
    「侧车其实算的是明文」会全绿 —— 而那一档下 :func:`restore.verify_backup`
    会拒绝每一份合法的加密档）；
    ③⚠️ **侧车的格式一个字都没改**（两行 ``key=value``，:func:`backup.read_sidecar`
    仍然解析得动）—— 于是「侧车怎么算」这件事在加密前后**只有一个所有者**。
    """
    _powershell()
    backups = tmp_path / "backups"
    backups.mkdir()
    plain = backup.create_backup(db, backups, moment=FIXED_MOMENT)
    enc = _encrypted(db, backups)

    sidecar = backup.read_sidecar(backup.sidecar_of(enc))          # ③
    assert sidecar["sha256"] == backup.sha256_of(enc)               # ①
    assert sidecar["bytes"] == enc.stat().st_size
    other = backup.read_sidecar(backup.sidecar_of(plain))
    assert sidecar["sha256"] != other["sha256"], "侧车算的不是产物本身"   # ②
    assert sidecar["bytes"] != other["bytes"]
    # ⚠️ 而侧车文件名仍然是「同名 + .sha256」（扩展名没有变成 .enc.sha256 一类）
    assert backup.sidecar_of(enc).name == enc.name + backup.SIDECAR_SUFFIX
    assert enc.suffix == plain.suffix == ".db", "加密档换了扩展名：判据必须是产物头"


def test_two_encryptions_differ_because_each_carries_its_own_salt_and_iv(db, tmp_path):
    """**每份备份自己的随机盐与随机 IV** ⇒ 同一个口令 + 同一份明文，两次产物字节不同。

    ⚠️ 那一格不是洁癖：一个**固定** IV 会让「两次备份之间哪些页没变」在密文上
    直接可读（CBC 下相同的明文前缀 ⇒ 相同的密文前缀），而一个固定盐会让
    一张预计算的表同时对**全部**备份有效。
    ⚠️ 三拍：① 盐不同；② IV 不同；③ 整份产物的字节不同（⚠️ 而两份都能各自验过 MAC、
    各自解回同一份明文 —— 少这一拍，「产物不同」可能只是因为有一份是坏的）。
    """
    _powershell()
    backups = tmp_path / "backups"
    backups.mkdir()
    first = _encrypted(db, backups, moment=dt.datetime(2026, 10, 14, tzinfo=dt.timezone.utc))
    second = _encrypted(db, backups, moment=dt.datetime(2026, 10, 15, tzinfo=dt.timezone.utc))

    a, b = backup.describe_container(first), backup.describe_container(second)
    assert a["salt"] != b["salt"], a["salt"].hex()
    assert a["iv"] != b["iv"], a["iv"].hex()
    assert first.read_bytes() != second.read_bytes()
    for path in (first, second):
        backup.verify_container(path, FAKE_PASSPHRASE)
        out = tmp_path / ("rt-" + path.name)
        backup.decrypt_container(path, out, FAKE_PASSPHRASE)
        assert _semester_name(out) == BACKED_UP_NAME, path


def test_encrypting_never_leaves_a_plaintext_copy_in_the_backup_directory(
    db, tmp_path, monkeypatch
):
    """**明文那一份从来不落进备份目录**（它落在系统临时目录里、并在 ``finally`` 里删掉）。

    ⚠️ 三拍：① 加密之后那个目录里**恰好两个**文件（产物 + 侧车），
    没有任何 ``*.tmp`` / ``*plain*`` / ``*.body`` 一类东西；
    ② 系统临时目录里也没有留下 ``pe-plain-*``；
    ③⚠️ **那一份明文临时文件是被写在系统临时目录里的**（监视
    :func:`tempfile.mkstemp` 的 ``dir`` 实参，断言它是 ``None``）。

    ⚠️⚠️ 第 ③ 拍是**承重**的，而它是被本 Task 的定点变异 **M14** 逼出来的：
    把 ``mkstemp`` 的 ``dir`` 指进备份目录之后，①②**照样全绿** —— 因为那一份
    临时明文在 ``finally`` 里被删掉了。⚠️ 于是「明文写在哪儿」这一格只有
    **在写的那一刻**才可观测，而它的后果恰恰只在**崩溃**时才现身
    （那时留下的正是一份明文，落在运维拷来拷去的那个目录里）。
    """
    _powershell()
    backups = tmp_path / "backups"
    backups.mkdir()
    before = {p.name for p in pathlib.Path(tempfile.gettempdir()).iterdir()
              if p.name.startswith("pe-plain-")}
    calls: list[object] = []
    real_mkstemp = tempfile.mkstemp

    def spy(*args, **kwargs):
        calls.append(kwargs.get("dir"))
        return real_mkstemp(*args, **kwargs)

    monkeypatch.setattr(backup.tempfile, "mkstemp", spy)

    enc = _encrypted(db, backups)

    assert sorted(p.name for p in backups.iterdir()) == [          # ①
        enc.name, enc.name + backup.SIDECAR_SUFFIX,
    ], sorted(p.name for p in backups.iterdir())
    after = {p.name for p in pathlib.Path(tempfile.gettempdir()).iterdir()
             if p.name.startswith("pe-plain-")}
    assert after == before, sorted(after - before)                 # ②
    assert calls == [None], calls                                  # ③


# ----------------------------------------------------- ④ 缺密钥：响亮 + 明文档


def test_a_missing_key_still_produces_a_usable_plaintext_backup_and_says_so_loudly(
    db, tmp_path, monkeypatch, capsys
):
    """**派单 §2 第 6 条 ④**：缺 ``PE_BACKUP_KEY`` 时**不加密**、⚠️ 而那段告示**在**，
    且产物**仍然是一份可用的明文档**（不是 raise）。

    ⚠️ 裁定逐字来自派单：「今天的缺省行为就是不加密，raise 会把既有用户打死」。
    四拍：

    ① ``resolve_backup_passphrase()`` 回 ``None``（⚠️ 而**不是**自己造一个缺省口令
       —— 一个内置的缺省口令等于「加密」这两个字变成一句假话）；
    ② 退出码 **0**、产物是**明文档**、而里面那一行**读得回来**（可用的）；
    ③ 那段告示逐格在：它说了「明文」、说了里面是什么（出生日期 / 体成分）、
       说了「拷进 U 盘」那一档为什么更危险、说了怎么加密（点名那个环境变量）、
       说了「口令丢了就打不开」；
    ④⚠️ **反空转**：设了口令之后那一段**不**印（改印「加密档」那几格）——
       少了这一拍，一个「无论加没加密都印一段明文警告」的实现会全绿，
       而那一档正是硬规矩 #50 点名的「狼来了」。
    """
    _powershell()
    monkeypatch.delenv(backup.BACKUP_KEY_ENV_VAR, raising=False)
    backups = tmp_path / "backups"
    backups.mkdir()
    assert backup.resolve_backup_passphrase() is None            # ①

    code = backup.main(["--db-url", "sqlite:///" + db.as_posix(),
                        "--dir", str(backups)])                  # ②
    out = capsys.readouterr().out
    assert code == 0, (code, out)
    products = [p for p in backups.iterdir() if not p.name.endswith(backup.SIDECAR_SUFFIX)]
    assert len(products) == 1
    assert backup.product_kind(products[0]) == backup.KIND_PLAINTEXT
    assert _semester_name(products[0]) == BACKED_UP_NAME

    for needle in ("**明文**的", "出生日期", "体成分", "U 盘", "邮件附件",
                   backup.BACKUP_KEY_ENV_VAR, "丢了就打不开", "**明文档**"):   # ③
        assert needle in out, (needle, out)

    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, FAKE_PASSPHRASE)
    capsys.readouterr()
    assert backup.main(["--db-url", "sqlite:///" + db.as_posix(),
                        "--dir", str(backups)]) == 0
    out2 = capsys.readouterr().out
    assert "这一份是**明文**的" not in out2, out2                  # ④
    assert "**加密档**" in out2 and backup.CONTAINER_MAGIC.decode() in out2, out2


def test_a_passphrase_shorter_than_the_password_policy_floor_is_refused(monkeypatch):
    """口令太短就拒，⚠️ 而那句报错**不印它收到了几个字符**（派单 §2 第 3 条：
    「不许打印它的任何一部分，包括长度与 sha」）。

    ⚠️ 下界不是本模块自己定的数：它是 ``app.auth.passwords.MIN_PASSWORD_LENGTH``
    （「一个人记得住的秘密至少多长」这件事在本仓只有一个所有者）。
    ⚠️ 而**空串按「没设」处理**是本仓对所有环境变量的既有口径
    （``$env:X = ""`` 在 PowerShell 里是「设了一个空值」），故它回 ``None``、不报错。
    """
    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, "")
    assert backup.resolve_backup_passphrase() is None
    for short in ("a", "ab", "abc", "1234567", "x" * (passwords.MIN_PASSWORD_LENGTH - 1)):
        monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, short)
        with pytest.raises(backup.BackupError) as excinfo:
            backup.resolve_backup_passphrase()
        message = str(excinfo.value)
        assert str(passwords.MIN_PASSWORD_LENGTH) in message, message   # 下界**要**说
        assert str(len(short)) + " 个字符" not in message, (short, message)
        # ⚠️ 「口令本体不在报错里」这一拍只对 ≥ 4 个字符的口令有意义：
        #    一个字符的口令（``"a"``）在任何一句中文报错里都找得到，
        #    而那一档下断言恒红、修它的人唯一的出路就是把这一拍删掉（硬规矩 #109）。
        if len(short) >= 4:
            assert short not in message, (short, message)
    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR,
                       "y" * passwords.MIN_PASSWORD_LENGTH)
    assert len(backup.resolve_backup_passphrase() or "") == passwords.MIN_PASSWORD_LENGTH


# ------------------------------------------- ⑤⑥ 密钥字面量与「任何一部分都不印」


def test_no_part_of_the_passphrase_is_ever_printed(db, tmp_path, monkeypatch, capsys):
    """**派单 §2 第 6 条 ⑥**：密钥的**任何一部分**都不被打印。

    ⚠️ 「任何一部分」按六种派生形态逐个扫（本体 / base64 / 十六进制 / sha256 全串 /
    sha256 的前 16 位 / 倒序；⚠️ 那六种的**唯一所有者**是 :func:`passphrase_forms`，
    而它自己由 :func:`test_the_six_passphrase_forms_the_print_guard_scans_are_pinned`
    钉住 —— 定点变异 **M6b** 实测过「把五种删掉只留本体」在当时一条都不红），
    ⚠️ 而**两面**都扫：进程内 ``main()`` 的 stdout+stderr
    与一次**真的子进程**（``python scripts/backup.py``）的 stdout+stderr
    ——后者才是要交给运维的那一份输出，而它走的是另一条编码路径
    （PowerShell 的控制台代码页），故不能只扫前者。

    ⚠️ 反空转：同一次输出里**必须**印出加密那几格事实（迭代次数、盐的宽度、
    产物字节数），故上面那些 not in 不是因为「什么都没印」。
    """
    _powershell()
    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, FAKE_PASSPHRASE)
    backups = tmp_path / "backups"
    backups.mkdir()

    capsys.readouterr()
    assert backup.main(["--db-url", "sqlite:///" + db.as_posix(),
                        "--dir", str(backups)]) == 0
    captured = capsys.readouterr()
    texts = {"进程内": captured.out + captured.err}

    env = dict(os.environ)
    env["PE_DB_URL"] = "sqlite:///" + db.as_posix()
    env[backup.BACKUP_KEY_ENV_VAR] = FAKE_PASSPHRASE
    proc = subprocess.run(
        [sys.executable, "scripts/backup.py", "--dir", str(backups)],
        cwd=str(BACKEND_DIR), capture_output=True, env=env,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    texts["子进程"] = (proc.stdout + proc.stderr).decode("utf-8", "replace")

    forms = passphrase_forms(FAKE_PASSPHRASE)
    for where, text in texts.items():
        for label, form in forms.items():
            assert form not in text, (where, label)
        # ⚠️ 反空转
        assert "**加密档**" in text, (where, text)
        assert str(passwords.PBKDF2_MIN_VERIFY_ITERATIONS) in text, (where, text)
        assert "盐 %d B" % backup.CONTAINER_SALT_BYTES in text, (where, text)


def test_the_six_passphrase_forms_the_print_guard_scans_are_pinned():
    """⚠️⚠️ **元守卫**：那六种派生形态**一种都不许少**（定点变异 **M6b** 量出来的缺口）。

    改前那六种形态是内联在 :func:`test_no_part_of_the_passphrase_is_ever_printed`
    里的一个 dict，⚠️ 而本 Task 的变异实测：把其中**五种删掉、只留「本体」**，
    **62 条全绿、一条都没红** —— 也就是说「放宽那一条守卫的判据」在当时是一个
    **完全静默**的动作。⇒ 判据收进 :func:`passphrase_forms`（唯一所有者），
    本条钉它的形状，三拍：

    ① 恰好 **6** 种、而标签逐字是那六个（⚠️ 期望侧是**字面量**，硬规矩 #109）；
    ② 每一种都**真的由口令算出来**（拿一个已知口令逐个对一遍期望值 ——
       少这一拍，一个「六种形态全都返回同一个空串」的实现会让上面那一条守卫永绿）；
    ③⚠️ 那一条打印守卫**确实调它**（AST 上找得到那一次调用）——
       少这一拍，把判据「收进唯一所有者」这件事可以被悄悄退回成内联，
       而本条与那一条从此各说一套。
    """
    forms = passphrase_forms("abcd1234")
    assert len(forms) == 6, sorted(forms)                                     # ①
    assert sorted(forms) == sorted(
        ["本体", "base64", "十六进制", "sha256", "sha256[:16]", "倒序"]), sorted(forms)
    assert forms["本体"] == "abcd1234"                                          # ②
    assert forms["base64"] == "YWJjZDEyMzQ="
    assert forms["十六进制"] == "6162636431323334"
    assert forms["倒序"] == "4321dcba"
    assert len(forms["sha256"]) == 64 and all(c in "0123456789abcdef" for c in forms["sha256"])
    assert forms["sha256"][:16] == forms["sha256[:16]"]
    assert len(set(forms.values())) == 6, sorted(forms.values())               # 六种互不相同
    tree = ast.parse(pathlib.Path(__file__).read_bytes().decode("utf-8"))       # ③
    called = [
        node.func.id
        for func in ast.walk(tree)
        if isinstance(func, ast.FunctionDef)
        and func.name == "test_no_part_of_the_passphrase_is_ever_printed"
        for node in ast.walk(func)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "passphrase_forms" in called, called


def test_the_fake_passphrase_lives_in_exactly_one_tracked_file():
    """**派单 §2 第 6 条 ⑤**：密钥字面量不出现在任何入库文件里（⚠️ 包括测试）。

    三拍，各挡一个不同的失效：

    ① ``git grep -F`` 全仓扫 :data:`FAKE_PASSPHRASE` 与
       :data:`OTHER_FAKE_PASSPHRASE` ⇒ **各命中恰好一个文件**（本文件）。
       ⚠️ 少这一拍，「有人把一个真口令抄进了某个脚本/文档/测试」是静默的
       —— 而本仓的 ``backend/backups/`` 已经被忽略了，一个入库的口令
       是**唯一**一处会让秘密进版本控制的路；
    ② **结构侧**：``backup.py`` 与 ``restore.py`` 的 AST 里，没有任何一个
       **字符串字面量**被赋给一个名字里带 ``key`` / ``passphrase`` / ``secret`` /
       ``password`` 的变量（⚠️ 判据是 AST、不是文本搜索：两个脚本的 docstring 里
       **逐字提及**了 ``PE_BACKUP_KEY``，而提及不是本身，硬规矩 #109）；
    ③ **行为侧**（⚠️ 承重）：把那个环境变量删掉之后
       ``resolve_backup_passphrase()`` 回 ``None`` —— 于是「它没有一个内置的缺省口令」
       是可执行的，而不只是一句注释。
    """
    repo = BACKEND_DIR.parent
    for literal in (FAKE_PASSPHRASE, OTHER_FAKE_PASSPHRASE):
        proc = subprocess.run(
            ["git", "grep", "-l", "-F", "--", literal],
            cwd=str(repo), capture_output=True, text=True, encoding="utf-8",
        )
        hits = [line for line in proc.stdout.splitlines() if line.strip()]
        # ⚠️ ``.superpowers/**`` 是本仓的 SDD 审计链（实现者报告 / 取证探针），
        #    而报告**应当**逐字引用它取过证的那个夹具（否则「密钥纪律」那一格无从复核）。
        #    它不是**发给甲方**的产物，故不在本条的扫描面里；除此之外一处都不许有。
        outside = [h for h in hits
                   if not h.startswith(".superpowers/")
                   and h != "backend/tests/test_backup_restore.py"]
        assert outside == [], (literal[:12], outside)
        assert "backend/tests/test_backup_restore.py" in hits, (literal[:12], hits)

    for name in ("backup", "restore"):
        tree = ast.parse((SCRIPTS_DIR / f"{name}.py").read_text(encoding="utf-8"))
        suspects = re.compile(r"(?i)(key|passphrase|secret|password)")
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t for t in node.targets if isinstance(t, ast.Name)]
                value = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets, value = [node.target], node.value
            else:
                continue
            for target in targets:
                if not suspects.search(target.id):
                    continue
                # ⚠️ 放过「一个**变量名**的字面量」：本仓的既有惯例是 ``*_ENV_VAR``
                #    （``DB_URL_ENV_VAR`` / ``PBKDF2_ITERATIONS_ENV_VAR`` / 本波新加的
                #    ``BACKUP_KEY_ENV_VAR`` 与 ``BACKUP_KDF_ITER_ENV_VAR``），
                #    那一份字面量是「去哪个环境变量里取」而**不是**取到的东西。
                #    ⚠️ 而③那一拍（行为侧）才是承重的一格：环境变量删掉之后
                #    它回 ``None`` ⇒ 「没有一个内置的缺省口令」是可执行的。
                if target.id.endswith("_ENV_VAR"):
                    continue
                assert not (isinstance(value, ast.Constant) and isinstance(value.value, str)), (
                    f"{name}.py 把一个字符串字面量赋给了 {target.id!r}："
                    "口令只从环境变量来（backup.BACKUP_KEY_ENV_VAR），"
                    "一个内置的缺省口令会让「加密」这两个字变成一句假话"
                )
    # ③
    saved = os.environ.pop(backup.BACKUP_KEY_ENV_VAR, None)
    try:
        assert backup.resolve_backup_passphrase() is None
    finally:
        if saved is not None:
            os.environ[backup.BACKUP_KEY_ENV_VAR] = saved


# ------------------------------------------------- KDF 的口径所有者与它的界


def test_the_backup_kdf_default_is_the_password_policy_default(db, tmp_path, monkeypatch):
    """**迭代次数的口径所有者是 ``app.auth.passwords``**（本模块一个数都不自己写），
    ⚠️ 而它**刻意不读** ``PBKDF2_ITERATIONS``。

    四拍：

    ① 环境变量没设时，缺省值**就是** ``PBKDF2_DEFAULT_ITERATIONS``（那一格由
       ``tests/auth/test_passwords.py`` 另外钉住是 600 000 ≥ OWASP 的下界）；
    ②⚠️ 把 ``PBKDF2_ITERATIONS`` 设成下界（根 conftest 就是这么设的）之后，
       备份那一个缺省**不变** —— 那一个环境变量是给测试套件降工作量的，
       而备份的 KDF 每份只跑一次，没有理由跟着降（⚠️ 而「跟着降」的失效方向是
       **静默**的：一份用低迭代派生的加密备份看起来与用高迭代的完全一样）；
    ③ ``PE_BACKUP_KDF_ITER`` 能覆盖，⚠️ 而它受**同一族**上下界管
       （``MIN-1`` / ``MAX+1`` / ``0`` / 负数 / 非整数五档各拒一次）；
    ④⚠️ **产物头里那一个数也过同一道界**：一份声称「迭代 1 次」的产物**当场被拒**
       （头里那个数是产物可控的，而恢复时若照它跑，就等于让造它的人把我们的
       工作量降到 1）。⚠️ 这一拍是派单 §2 第 6 条 ⑦ 那个定点变异
       （「把 PBKDF2 的迭代次数改成 1 → 红」）的**常驻**形式。
    """
    monkeypatch.delenv(backup.BACKUP_KDF_ITER_ENV_VAR, raising=False)
    assert backup.resolve_kdf_iterations() == passwords.PBKDF2_DEFAULT_ITERATIONS   # ①
    assert passwords.PBKDF2_DEFAULT_ITERATIONS >= passwords.PBKDF2_MIN_VERIFY_ITERATIONS

    monkeypatch.setenv(passwords.PBKDF2_ITERATIONS_ENV_VAR,                       # ②
                       str(passwords.PBKDF2_MIN_VERIFY_ITERATIONS))
    assert backup.resolve_kdf_iterations() == passwords.PBKDF2_DEFAULT_ITERATIONS

    monkeypatch.delenv(passwords.PBKDF2_ITERATIONS_ENV_VAR, raising=False)        # ③
    monkeypatch.setenv(backup.BACKUP_KDF_ITER_ENV_VAR, "250000")
    assert backup.resolve_kdf_iterations() == 250000
    for bad in ("0", "-1", "1",
                str(passwords.PBKDF2_MIN_VERIFY_ITERATIONS - 1),
                str(passwords.PBKDF2_MAX_VERIFY_ITERATIONS + 1),
                "很多", ""):
        monkeypatch.setenv(backup.BACKUP_KDF_ITER_ENV_VAR, bad)
        if bad == "":
            assert backup.resolve_kdf_iterations() == passwords.PBKDF2_DEFAULT_ITERATIONS
        else:
            with pytest.raises(backup.BackupError):
                backup.resolve_kdf_iterations()
    monkeypatch.delenv(backup.BACKUP_KDF_ITER_ENV_VAR, raising=False)

    # ④⚠️ 产物头里那一个数（写侧与读侧共用 _check_kdf_iterations）
    _powershell()
    backups = tmp_path / "backups"
    backups.mkdir()
    enc = _encrypted(db, backups)
    raw = bytearray(enc.read_bytes())
    raw[12:16] = (1).to_bytes(4, "big")          # 声称「迭代 1 次」
    forged = tmp_path / "forged.db"
    forged.write_bytes(bytes(raw))
    with pytest.raises(backup.BackupError) as excinfo:
        backup.describe_container(forged)
    assert "迭代次数" in str(excinfo.value), str(excinfo.value)
    with pytest.raises(backup.BackupError):
        backup.verify_container(forged, FAKE_PASSPHRASE)


# ------------------------------------------------- ①的另一半：HMAC 与篡改


def test_a_wrong_passphrase_never_reaches_the_cipher(db, tmp_path):
    """**派单 §2 第 4 条那一格的 backup 侧**：口令不对 ⇒ **一步都不解密**。

    ⚠️ 判据不是「报错了」，而是**三格**：

    ① :func:`backup.verify_container` 抛 :class:`backup.BackupError`；
    ② 目标文件**没有被创建**（⚠️ 那一格是「不许走到解密那一步」的**可执行**形式：
       一个「先解密到临时文件、再验 MAC」的实现会在临时目录里留下**明文**，
       而本条会红在它上面）；
    ③ 报错**同时**说了两种可能（口令不对 / 产物被改过）——⚠️ encrypt-then-MAC 之下
       两者在密码学上不可分辨，而一个只说「口令不对」的报错会把运维支去反复试口令，
       一个只说「被改过」的报错会让他去查一个根本不存在的入侵。
    ⚠️ 并钉住它**不印** MAC 的两个值（那是两个 32 字节的秘密派生物）。
    """
    _powershell()
    backups = tmp_path / "backups"
    backups.mkdir()
    enc = _encrypted(db, backups)

    with pytest.raises(backup.BackupError) as excinfo:
        backup.verify_container(enc, OTHER_FAKE_PASSPHRASE)
    message = str(excinfo.value)
    assert "HMAC" in message and "验不过" in message, message
    assert "口令" in message and "改过" in message, message          # ③
    real_mac = enc.read_bytes()[-backup.CONTAINER_MAC_BYTES:].hex()
    assert real_mac not in message and real_mac[:16] not in message, message

    out = tmp_path / "must-not-exist.db"
    with pytest.raises(backup.BackupError):
        backup.decrypt_container(enc, out, OTHER_FAKE_PASSPHRASE)
    assert not out.exists(), "解密先跑了一步：口令不对时不许产出任何文件"     # ②
    assert not out.with_name(out.name + ".body").exists()


def test_tampering_with_the_ciphertext_or_with_the_mac_is_both_refused(db, tmp_path):
    """**篡改那一档在加密档上有两个形状**（派单 §2 第 4 条逐字要求：两个都要试）。

    四拍，各改一个字节：① 改**密文**中间的一个字节；② 改**尾部 MAC** 的一个字节；
    ③ 改**头里的保留字节**；④ 把产物**截断** 1 字节。四档一律拒。

    ⚠️⚠️ **① 是本件最要紧的一格**：本 Task 实测过「只靠 AES-CBC 自己」的话
    那一档**不响** —— 改密文中间一个字节只坏那两个块，PKCS7 的 padding 常常仍然合法，
    ``aes_cbc.ps1`` **退出码 0**、静默产出一个坏库（取证见
    ``task-3-report.md`` §4）。⚠️ 于是「必须有独立的 HMAC」不是理论洁癖，
    是本机量出来的一格。
    """
    _powershell()
    backups = tmp_path / "backups"
    backups.mkdir()
    enc = _encrypted(db, backups)
    raw = enc.read_bytes()

    cases = [
        ("改密文中间一个字节", lambda b: b.__setitem__(60 + len(b) // 3, b[60 + len(b) // 3] ^ 0x01)),
        ("改尾部 MAC 一个字节", lambda b: b.__setitem__(len(b) - 1, b[len(b) - 1] ^ 0x01)),
        ("改头里的保留字节", lambda b: b.__setitem__(11, 0x7F)),
    ]
    for index, (_label, mutate) in enumerate(cases):
        data = bytearray(raw)
        mutate(data)
        forged = tmp_path / ("forged-%d.db" % index)
        forged.write_bytes(bytes(data))
        with pytest.raises(backup.BackupError):
            backup.verify_container(forged, FAKE_PASSPHRASE)
        # ⚠️ 而「保留字节」那一档报的是**布局**不一致，不是 MAC 不一致
        #    （它响得**更早**，因为 MAC 覆盖的头已经对不上了 —— 两档都响，理由不同）
    truncated = tmp_path / "truncated.db"
    truncated.write_bytes(raw[:-1])                                       # ④
    with pytest.raises(backup.BackupError):
        backup.verify_container(truncated, FAKE_PASSPHRASE)
    # ⚠️ 反空转：没被改过的那一份**验得过**
    assert backup.verify_container(enc, FAKE_PASSPHRASE)["plaintext_len"] == len(raw) - 60 - 32 - 16


def test_an_unrecognised_product_head_is_refused_loudly(db, tmp_path):
    """**产物头认不出**（既不是明文 SQLite、也不是本仓的加密档）⇒ 响亮。

    三档：① 一个文本文件；② 一个 0 字节文件；③ 一个魔数对、而**版本**是 99 的
    （= 由一个更新的版本写出来的）⇒ 报错要说清「不要猜着解，请拿写它的那一份代码来恢复」。
    ⚠️ 而 :func:`backup.product_kind` 对①②回 ``unknown``（不是抛），
    因为「它是什么形状」与「它能不能用」是两个问题：前者是一个判断、
    后者由调用方（:mod:`restore`）按那个判断决定响不响。
    """
    text_file = tmp_path / "notes.db"
    text_file.write_text("这不是一份库", encoding="utf-8")
    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")
    assert backup.product_kind(text_file) == backup.KIND_UNKNOWN
    assert backup.product_kind(empty) == backup.KIND_UNKNOWN

    forged = tmp_path / "from-the-future.db"
    forged.write_bytes(b"PEBACKUP" + bytes((99, 1, 1, 0)) + b"\x00" * 200)
    assert backup.product_kind(forged) == backup.KIND_ENCRYPTED, "魔数对了就该认成加密档"
    with pytest.raises(backup.BackupError) as excinfo:
        backup.describe_container(forged)
    message = str(excinfo.value)
    assert "版本" in message and "99" in message, message
    assert "不要猜着解" in message, message


def test_decrypting_gives_back_exactly_the_plaintext_bytes(db, tmp_path):
    """**往返**：加密档解回来与「同一份库的明文备份」**逐字节相同**，
    ⚠️ 而头上那个 ``plaintext_len`` 与解出来的字节数对得上。

    ⚠️ 三拍：① 逐字节相同（不是「能打开」，那不够 —— 一个坏在半路的库也能打开）；
    ② 里面那一行读得回来（一次**真的查询**）；
    ③ 解密过程用的 ``.body`` 临时文件**没有**留在目录里。
    """
    _powershell()
    backups = tmp_path / "backups"
    backups.mkdir()
    plain = backup.create_backup(db, backups, moment=FIXED_MOMENT)
    enc = _encrypted(db, backups)

    out = tmp_path / "roundtrip.db"
    info = backup.decrypt_container(enc, out, FAKE_PASSPHRASE)
    assert out.read_bytes() == plain.read_bytes()                     # ①
    assert _semester_name(out) == BACKED_UP_NAME                      # ②
    assert info["plaintext_len"] == out.stat().st_size
    assert not out.with_name(out.name + ".body").exists()             # ③
    assert [p.name for p in backups.iterdir()
            if p.name.endswith(".body")] == [], sorted(p.name for p in backups.iterdir())


# ------------------------------------------------- AES 那一个原语的形状


def test_the_aes_helper_is_a_primitive_that_knows_nothing_about_the_format():
    """``aes_cbc.ps1``：UTF-8 + BOM + 纯 CRLF，⚠️ 而它是**一个原语**、不认识我们的格式。

    四拍：

    ① BOM + 纯 CRLF（与本仓其余九个 ``.ps1`` 同款；⚠️ BOM 是承重的：
       PowerShell 5.1 读一个没有 BOM 的 ``.ps1`` 时按系统 ANSI 代码页解码，
       而本文件的注释全是 UTF-8 中文）；
    ②⚠️ **它的代码段里一个格式字节都不认识**：``PEBACKUP`` / ``HMAC`` /
       ``sha256`` / ``Rfc2898`` / ``PE_BACKUP_KEY`` / 侧车 一律不许出现
       （⚠️ 只扫 ``#>`` 之后的**代码段**：说明段里逐字**提及**了它们来解释
       「为什么这些不在这里」，而提及不是本身，硬规矩 #109）；
    ③ 它**只**做 AES-256-CBC + PKCS7（``CipherMode]::CBC`` 与 ``PaddingMode]::PKCS7``
       两个字面量都在，⚠️ 反空转）；
    ④⚠️ 密钥走 **stdin**、**不走 argv**：代码段里有 ``[Console]::In``、
       而 ``param`` 块里没有任何一个参数是用来收密钥的
       （⚠️ 参数面恰好四个：``-Action`` / ``-In`` / ``-Out`` / ``-Append``）。
       理由逐字：Windows 上任何同机进程都能用 ``Get-CimInstance Win32_Process``
       读到别人完整的命令行。
    """
    _powershell()
    raw = AES_PS1.read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf", "aes_cbc.ps1 没有 BOM（PS 5.1 会按 GBK 读它）"
    body = raw[3:].decode("utf-8")
    crlf = body.count("\r\n")
    assert body.count("\n") - crlf == 0, "有裸 LF（本仓的 .ps1 一律纯 CRLF）"
    assert crlf > 50, crlf
    assert body.count("#>") == 1, "注释块形状变了，本条的切法要跟着改"
    code = body.split("#>", 1)[1]

    # ⚠️ 判据是**实现级**的（它用了哪些 .NET 密码学类型 / 哪些格式字面量），
    #    而不是「文本里有没有 HMAC 这个词」：本文件的报错文字里**逐字提及**了
    #    上游那一道 HMAC（那是给运维的线索，很有用），而提及不是本身
    #    （硬规矩 #109；姿势与本文件既有那条 ``…two_ps1_wrappers…`` 守卫
    #    「只扫 ``#>`` 之后的代码段」逐字同族）。
    for needle in ("PEBACKUP", ".sha256", "sqlite", "PE_BACKUP_KEY", "Rfc2898",
                   "HMACSHA256", "SIDECAR", "BitConverter", "Get-FileHash"):
        assert needle not in code, (
            f"aes_cbc.ps1 的代码段里出现了 {needle!r}：它只是「一块字节进、一块字节出」的"
            "那一个原语，而产物形状（魔数/头/HMAC/侧车）的唯一所有者是 backup.py"
        )
    # ⚠️⚠️ 而**它用了哪些 .NET 密码学类型**是按集合钉死的：多一个（例如
    #    ``Rfc2898DeriveBytes`` = 它自己派生密钥、或 ``HMACSHA256`` = 它自己算 MAC）
    #    就意味着产物形状有了第二个所有者。
    assert sorted(set(re.findall(r"System\.Security\.Cryptography\.(\w+)", code))) == [
        "Aes", "CipherMode", "CryptoStream", "CryptoStreamMode",
        "CryptographicException", "PaddingMode",
    ], sorted(set(re.findall(r"System\.Security\.Cryptography\.(\w+)", code)))
    assert "[System.Security.Cryptography.CipherMode]::CBC" in code          # ③
    assert "[System.Security.Cryptography.PaddingMode]::PKCS7" in code
    assert "$Aes.KeySize = $KEY_BYTES * 8" in code
    assert "[Console]::In.ReadLine()" in code                                # ④
    assert re.findall(r"^\s*\[(?:Parameter\(Mandatory = \$true\)\s*)?"
                      r"(?:string|switch)\]\$(\w+)", code, re.M) == [
        "Action", "In", "Out", "Append",
    ], code
    assert "[Convert]::FromBase64String" in code
    # ⚠️ 而它**刻意不印**收到的密钥材料的任何一部分（连长度都不印）：
    #    那两句「宽度不对」的报错里只印**期望值**（一个常量），不印实到值
    for line in code.splitlines():
        if "Fail 3" in line or "$Why" in line:
            assert "$Key.Length" not in line and "$Iv.Length" not in line, line


def test_the_two_wrappers_stay_thin_even_though_encryption_exists():
    """⚠️ **加密没有把逻辑搬进 ``.ps1``**：两个薄包装仍然恰好调一次 ``python``。

    ⚠️ 本条存在的理由是**一处真实的张力**：``tests/test_backup_restore.py`` 既有的
    ``test_the_two_ps1_wrappers_are_utf8_with_bom_and_crlf`` 钉住「两个包装的代码段里
    不许出现任何实现构造、且 ``python`` 恰好被调用一次」，而加密**只能**在
    PowerShell 侧做（Python 标准库没有 AES）⇒ 最省事的实现就是把加密写进
    ``backup.ps1``，而那会当场弄红既有守卫、并把产物形状变成**两个所有者**。
    本仓选的是第三条路：逻辑仍在 ``backup.py``，只有那**一次**分组密码变换
    住在 ``aes_cbc.ps1``（由 ``backup.py`` 经 ``subprocess`` 叫）。
    ⚠️ 本条把那一个选择钉成可执行的：两个包装里**一个加密构造都不许出现**。
    """
    for name in ("backup.ps1", "restore.ps1"):
        body = (SCRIPTS_DIR / name).read_bytes()[3:].decode("utf-8")
        code = body.split("#>", 1)[1]
        for needle in ("Aes", "Crypto", "HMAC", "Rfc2898", "PE_BACKUP_KEY",
                       "aes_cbc", "[Convert]", "Encrypt"):
            assert needle not in code, (
                f"{name} 的代码段里出现了 {needle!r}：加密的编排住在 backup.py / restore.py，"
                "AES 那一个原语住在 aes_cbc.ps1，而两个包装只负责切目录、传参数、"
                "交回退出码（派单 §2 第 1 条：「两个**薄** .ps1 包装」）"
            )
        assert code.count("\npython ") == 1, name
def test_the_cipher_key_and_the_mac_key_are_not_the_same_key():
    """**两把钥匙不同源**：一次 PBKDF2 派生 64 字节、对半切，
    ⚠️ 而不是「同一把钥匙既加密又做 MAC」。

    ⚠️ 那一格不是洁癖：用同一把钥匙同时做加密与 MAC 是一个被反复研究过的坏姿势
    （它把「MAC 是否泄漏关于明文的信息」与「密文是否泄漏」两件事耦在一起），
    而正确的做法只是把 ``dklen`` 从 32 改成 64、对半切 —— 代价是**零**。

    四拍，⚠️ 期望侧**另算一遍**（本文件自己调 :func:`hashlib.pbkdf2_hmac`，
    不走被测代码）：① 两把各 32 字节；② 两把**不相同**；
    ③ 它们逐字等于那一次 64 字节派生的前 32 与后 32；
    ④⚠️ 换一个盐 ⇒ 两把**都**变（故上面三拍不是因为派生了一个常量）。
    """
    salt = bytes(range(backup.CONTAINER_SALT_BYTES))
    iterations = passwords.PBKDF2_MIN_VERIFY_ITERATIONS
    cipher_key, mac_key = backup.derive_keys(FAKE_PASSPHRASE, salt, iterations)

    assert len(cipher_key) == backup.CONTAINER_AES_KEY_BYTES == 32            # ①
    assert len(mac_key) == backup.CONTAINER_MAC_KEY_BYTES == 32
    assert cipher_key != mac_key                                              # ②
    material = hashlib.pbkdf2_hmac(                                          # ③
        "sha256", FAKE_PASSPHRASE.encode("utf-8"), salt, iterations,
        backup.CONTAINER_DERIVED_BYTES,
    )
    assert len(material) == 64
    assert cipher_key == material[:32] and mac_key == material[32:]
    other_cipher, other_mac = backup.derive_keys(                            # ④
        FAKE_PASSPHRASE, bytes(range(1, 1 + backup.CONTAINER_SALT_BYTES)), iterations)
    assert other_cipher != cipher_key and other_mac != mac_key
# ===========================================================================
# ⚠️⚠️ restore 吃加密档（Plan 08 Task 3 · 派单 §2 第 4 条）
# ===========================================================================
#
# ⚠️⚠️ **本节与 Plan 06 Task 10 那三档取证的关系**：那三档（篡改 / 写锁 / 跨链版本）
# 住在上面既有的三条里，⚠️ 而它们**在明文档上仍然逐字成立**（本文件改后 47 条全绿，
# 一条都没改判据）。本节做的是派单逐字要求的两件事：
# ① **新增第四档「密钥不对」**；② 把那三档**在加密档上复跑一遍**
#    （篡改那一档在加密档上有**两个**形状：改密文 与 改 MAC，⚠️ 两个都试）。


def _temp_leftovers(prefix: str) -> set[str]:
    """系统临时目录里 ``prefix`` 开头的那些名字（⚠️ 前后各取一次做差）。"""
    return {p.name for p in pathlib.Path(tempfile.gettempdir()).iterdir()
            if p.name.startswith(prefix)}


def test_restoring_an_encrypted_backup_puts_the_changed_row_back(
    tmp_path, monkeypatch, capsys
):
    """**端到端**：加密档备份 → 改一行 → 恢复 → 那一行回到备份点。

    ⚠️ 判据与既有那条 :func:`test_backup_then_restore_puts_the_changed_row_back`
    **逐字同一条**（同一对名字字面量、同一个「改坏了再恢复回来」的形状），
    只是产物是加密档 ⇒ 「加密那一层没有把恢复弄坏」是**可执行**的，
    而不是一句「看起来应该行」。

    ⚠️ 三拍：① 恢复回去的那一行是备份点上的名字；② 输出里说了它是**加密档**、
    且 HMAC 验过；③⚠️ 输出里**没有**口令的任何一部分（派单 §2 第 6 条 ⑥ 在
    恢复这一侧同样成立 —— 恢复的报错与提示是最容易顺口把口令回显的地方）。
    """
    _powershell()
    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, FAKE_PASSPHRASE)
    source = tmp_path / "source.db"
    _db_at_head(source, BACKED_UP_NAME)
    backups = tmp_path / "backups"
    backups.mkdir()
    saved = backup.create_backup(source, backups, passphrase=FAKE_PASSPHRASE)
    assert backup.product_kind(saved) == backup.KIND_ENCRYPTED

    _rewrite(source, CHANGED_NAME)
    assert _semester_name(source) == CHANGED_NAME

    capsys.readouterr()
    code = restore.main([
        saved.name, "--dir", str(backups),
        "--db-url", "sqlite:///" + source.as_posix(), "--no-auto-backup",
    ])
    out = capsys.readouterr().out
    assert code == 0, (code, out)
    assert _semester_name(source) == BACKED_UP_NAME               # ①
    assert "**加密档**" in out and "HMAC-SHA256 验过" in out, out    # ②
    for form in (FAKE_PASSPHRASE,
                 base64.b64encode(FAKE_PASSPHRASE.encode("utf-8")).decode(),
                 hashlib.sha256(FAKE_PASSPHRASE.encode("utf-8")).hexdigest()[:16]):
        assert form not in out, (form[:12], out)                   # ③


def test_a_wrong_passphrase_makes_restore_refuse_without_touching_the_target(
    tmp_path, monkeypatch
):
    """⚠️⚠️ **第四档：密钥不对**（派单 §2 第 4 条逐字新增的那一格）。

    五拍，而**②是本条的全部理由**：

    ① :func:`restore.main` 抛 :class:`backup.BackupError`（⇒ ``__main__`` 那一路退出码 **2**）；
    ②⚠️ **目标库逐字节未变**（sha256 前后相同）——「不许静默产出一个坏库」的
      **可执行**形式。⚠️ 少了这一拍，一个「先解密到目标库、验不过再报错」的实现会全绿，
      而它在报错之前已经把目标库毁了；
    ③ 系统临时目录里**没有**留下解出来的明文（``pe-restore-*``）；
    ④ 报错**同时**说了两种可能（口令不对 / 产物被改过），并说了「目标库没有被改动」；
    ⑤⚠️ 报错里**不印** MAC 的两个值、也不印口令的任何一部分。
    """
    _powershell()
    source = tmp_path / "source.db"
    _db_at_head(source, BACKED_UP_NAME)
    backups = tmp_path / "backups"
    backups.mkdir()
    saved = backup.create_backup(source, backups, passphrase=FAKE_PASSPHRASE)

    target = tmp_path / "target.db"
    _db_at_head(target, CHANGED_NAME)
    before = backup.sha256_of(target)
    leftovers = _temp_leftovers("pe-restore-")

    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, OTHER_FAKE_PASSPHRASE)
    with pytest.raises(backup.BackupError) as excinfo:
        restore.main([
            saved.name, "--dir", str(backups),
            "--db-url", "sqlite:///" + target.as_posix(),
        ])
    message = str(excinfo.value)

    assert backup.sha256_of(target) == before, "目标库被动过了"        # ②
    assert _semester_name(target) == CHANGED_NAME
    assert _temp_leftovers("pe-restore-") == leftovers                 # ③
    assert "HMAC" in message and "验不过" in message, message          # ④
    assert "口令" in message and "改过" in message, message
    assert "没有被改动" in message, message
    real_mac = saved.read_bytes()[-backup.CONTAINER_MAC_BYTES:].hex()   # ⑤
    assert real_mac not in message and real_mac[:16] not in message, message
    assert OTHER_FAKE_PASSPHRASE not in message and FAKE_PASSPHRASE not in message


def test_a_missing_passphrase_on_an_encrypted_backup_says_how_to_put_it_back(
    tmp_path, monkeypatch
):
    """加密档 + ``PE_BACKUP_KEY`` **不在** ⇒ 一句**能照着做**的人话，⚠️ 而不是一句「解密失败」。

    三拍：① 报错点名那个环境变量、并给出把它设回去的**那两行命令**；
    ② 它明说了「``--no-verify`` 跳的是侧车那一格，HMAC 那一格跳不掉」
    （⚠️ 少了这一句，运维的下一个动作一定是去试 ``--no-verify``）；
    ③ 目标库逐字节未变。
    """
    _powershell()
    monkeypatch.delenv(backup.BACKUP_KEY_ENV_VAR, raising=False)
    source = tmp_path / "source.db"
    _db_at_head(source, BACKED_UP_NAME)
    backups = tmp_path / "backups"
    backups.mkdir()
    saved = backup.create_backup(source, backups, passphrase=FAKE_PASSPHRASE)

    target = tmp_path / "target.db"
    _db_at_head(target, CHANGED_NAME)
    before = backup.sha256_of(target)

    with pytest.raises(backup.BackupError) as excinfo:
        restore.main([saved.name, "--dir", str(backups),
                      "--db-url", "sqlite:///" + target.as_posix()])
    message = str(excinfo.value)
    assert backup.BACKUP_KEY_ENV_VAR in message, message                # ①
    assert "$env:" in message and "restore.ps1" in message, message
    assert "--no-verify" in message and "HMAC" in message, message       # ②
    assert backup.sha256_of(target) == before                            # ③


def test_no_verify_skips_the_sidecar_but_never_the_hmac(tmp_path, monkeypatch):
    """⚠️⚠️ ``--no-verify`` **没有**变成加密那一层的后门。

    三拍：① 侧车**删掉**之后，``--no-verify`` + **正确**口令仍然恢复成功
    （⇒ 那个逃生口对它本来的用途仍然有效，不是一句空话）；
    ② 同一档下**口令不对** ⇒ 仍然拒（⚠️ 这就是「HMAC 跳不掉」）；
    ③ 目标库在②那一档逐字节未变。

    ⚠️ 理由是两格答的**不是同一个问题**：侧车答「拷来拷去有没有坏」
    （那一份 ``.sha256`` 可能真的丢了），HMAC 答「我解出来的东西是不是当初加密的那一份」
    ——跳过它就等于允许「口令不对也照样解、解出一个坏库」，那正是派单逐字禁止的一档。
    """
    _powershell()
    source = tmp_path / "source.db"
    _db_at_head(source, BACKED_UP_NAME)
    backups = tmp_path / "backups"
    backups.mkdir()
    saved = backup.create_backup(source, backups, passphrase=FAKE_PASSPHRASE)
    backup.sidecar_of(saved).unlink()                    # ⚠️ 侧车丢了
    assert not backup.sidecar_of(saved).is_file()

    target = tmp_path / "target.db"
    _db_at_head(target, CHANGED_NAME)

    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, OTHER_FAKE_PASSPHRASE)
    before = backup.sha256_of(target)
    with pytest.raises(backup.BackupError) as excinfo:
        restore.main([saved.name, "--dir", str(backups), "--no-verify",
                      "--db-url", "sqlite:///" + target.as_posix()])
    assert "HMAC" in str(excinfo.value), str(excinfo.value)               # ②
    assert backup.sha256_of(target) == before                             # ③

    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, FAKE_PASSPHRASE)
    assert restore.main([saved.name, "--dir", str(backups), "--no-verify",
                         "--db-url", "sqlite:///" + target.as_posix()]) == 0
    assert _semester_name(target) == BACKED_UP_NAME                       # ①


def test_tampering_with_an_encrypted_product_is_refused_by_both_layers(
    tmp_path, monkeypatch
):
    """**篡改那一档在加密档上有两个形状**（派单 §2 第 4 条逐字要求：两个都要试）。

    ⚠️ 而**两层都响**，各答一个问题：

    * 侧车还在 ⇒ **步 ①**（sha256 + 字节数）先响，报的是「这一份被动过」；
    * 侧车删掉 + ``--no-verify`` ⇒ **步 ⓪**（HMAC）接着响，报的是「口令不对或被改过」。

    两形状 × 两层 = 四拍，各断一次退出路径与「目标库逐字节未变」。
    ⚠️ 少「侧车删掉」那两拍，一个「只有侧车、没有 HMAC」的实现会全绿
    —— 而那正是 encrypt-then-MAC 存在的理由（本 Task 实测过：只靠 AES-CBC 自己，
    改密文中间一个字节**不响**，padding 仍然合法、解密退出码 0）。
    """
    _powershell()
    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, FAKE_PASSPHRASE)
    source = tmp_path / "source.db"
    _db_at_head(source, BACKED_UP_NAME)
    backups = tmp_path / "backups"
    backups.mkdir()
    saved = backup.create_backup(source, backups, passphrase=FAKE_PASSPHRASE)
    original = saved.read_bytes()

    target = tmp_path / "target.db"
    _db_at_head(target, CHANGED_NAME)
    before = backup.sha256_of(target)

    shapes = {
        "改密文一个字节": lambda b: b.__setitem__(60 + len(b) // 3, b[60 + len(b) // 3] ^ 0x01),
        "改 MAC 一个字节": lambda b: b.__setitem__(len(b) - 1, b[len(b) - 1] ^ 0x01),
    }
    for index, (label, mutate) in enumerate(shapes.items()):
        data = bytearray(original)
        mutate(data)
        assert bytes(data) != original, label

        # 第一层：只改产物、**不动侧车** ⇒ 步 ① 当场失配（报的是「这一份被动过」）
        naive = backups / ("naive-%d.db" % index)
        naive.write_bytes(bytes(data))
        (backups / (naive.name + backup.SIDECAR_SUFFIX)).write_bytes(
            backup.sidecar_of(saved).read_bytes()      # ⚠️ 抄的是**改之前**那一份的侧车
        )
        with pytest.raises(backup.BackupError) as first:
            restore.main([naive.name, "--dir", str(backups),
                          "--db-url", "sqlite:///" + target.as_posix()])
        assert "不吻合" in str(first.value), (label, str(first.value))

        # 第二层：一个**有本事**改产物的人也会把侧车一起改掉 ⇒ 侧车吻合了，
        #         于是只剩 HMAC 那一层。⚠️ 那一层挡得住，因为 HMAC 的钥匙不在产物里。
        forged = backups / ("forged-%d.db" % index)
        forged.write_bytes(bytes(data))
        backup.write_sidecar(forged)                   # ⚠️ 与**改过**的产物吻合
        backup.read_sidecar(backup.sidecar_of(forged))
        with pytest.raises(backup.BackupError) as second:
            restore.main([forged.name, "--dir", str(backups),
                          "--db-url", "sqlite:///" + target.as_posix()])
        assert "HMAC" in str(second.value), (label, str(second.value))
        assert backup.sha256_of(target) == before, label


def test_a_locked_target_is_still_refused_when_the_backup_is_encrypted(
    tmp_path, monkeypatch
):
    """**Plan 06 Task 10 那三档之一（写锁）在加密档上复跑**：仍然成立。

    ⚠️ 判据逐字同既有那条 :func:`test_a_locked_target_answers_with_a_readable_error`
    （``BEGIN IMMEDIATE`` 占住写锁 → 一句「请先停服务」），⚠️ 而本条多两拍：
    ② 目标库逐字节未变；③⚠️ **系统临时目录里没有留下解出来的明文** ——
    那一格是「步 ② 排在步 ⓪ 之前」的可执行形式（撞锁时**根本不解密**，
    于是运维不会白等 0.5 s、也不会在盘上多留一份明文）。
    """
    _powershell()
    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, FAKE_PASSPHRASE)
    source = tmp_path / "source.db"
    _db_at_head(source, BACKED_UP_NAME)
    backups = tmp_path / "backups"
    backups.mkdir()
    saved = backup.create_backup(source, backups, passphrase=FAKE_PASSPHRASE)

    target = tmp_path / "target.db"
    _db_at_head(target, CHANGED_NAME)
    before = backup.sha256_of(target)
    leftovers = _temp_leftovers("pe-restore-")

    holder = sqlite3.connect(str(target), timeout=0.2)
    try:
        holder.execute("BEGIN IMMEDIATE")
        with pytest.raises(backup.BackupError) as excinfo:
            restore.main([saved.name, "--dir", str(backups),
                          "--db-url", "sqlite:///" + target.as_posix()])
        message = str(excinfo.value)
        assert "请先停服务" in message, message
        assert "尽力" in message, message
    finally:
        holder.rollback()
        holder.close()
    assert backup.sha256_of(target) == before
    assert _temp_leftovers("pe-restore-") == leftovers, "撞锁那一档白解了一次密"


def test_the_older_migration_chain_warning_still_fires_for_an_encrypted_backup(
    tmp_path, monkeypatch, capsys
):
    """**Plan 06 Task 10 那三档之一（跨链版本）在加密档上复跑**：仍然成立。

    ⚠️ 判据逐字同既有那条
    :func:`test_restore_warns_loudly_when_the_backup_sits_on_an_older_migration_chain`
    的 ④⑤⑥ 三拍（退出码 **0**、那一句 ⚠️ 印了、库里此刻真的停在旧链上），
    而产物是加密档 ⇒ 「加密那一层没有把那一句警告吃掉」。
    ⚠️ 修订号一律从迁移链读（:func:`_db_at_previous_head`），一个字都不写死。
    """
    _powershell()
    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, FAKE_PASSPHRASE)
    old_db = tmp_path / "old.db"
    previous = _db_at_previous_head(old_db)
    heads = restore.code_head_revisions()
    assert heads and previous not in heads, (previous, heads)
    old_engine = create_engine("sqlite:///" + old_db.as_posix())
    with Session(old_engine) as session:
        session.add(Semester(name=OLD_CHAIN_MARKER, start_date=dt.date(2025, 2, 24),
                             end_date=dt.date(2025, 6, 15), weeks=16, is_current=False))
        session.commit()
    old_engine.dispose()

    backups = tmp_path / "backups-old"
    backups.mkdir()
    saved = backup.create_backup(old_db, backups, passphrase=FAKE_PASSPHRASE)
    assert backup.product_kind(saved) == backup.KIND_ENCRYPTED

    target = tmp_path / "target.db"
    _db_at_head(target, BACKED_UP_NAME)
    capsys.readouterr()
    code = restore.main([saved.name, "--dir", str(backups),
                         "--db-url", "sqlite:///" + target.as_posix(),
                         "--no-auto-backup"])
    out = capsys.readouterr().out
    assert code == 0, (code, out)
    assert "这一份备份的迁移版本比**当前代码旧**" in out, out
    assert previous in out, (previous, out)
    for head in heads:
        assert head in out, (head, out)
    assert restore.selfcheck(target)["revision"] == previous, restore.selfcheck(target)
    # ⚠️ 自愈那一格（⑦）在明文档上已经钉过，本条不重复：它只钉「警告没被加密层吃掉」
    #    ⚠️ 显式 close()：``with sqlite3.connect(…)`` 是**事务**上下文、不关连接，
    #    而一个握着的句柄会让 Windows 上后续任何 unlink 都 WinError 32
    #    （逐字理由见本文件 :func:`_semester_name` 的 docstring）。
    connection = sqlite3.connect(str(target))
    try:
        names = [row[0] for row in connection.execute("SELECT name FROM semester")]
    finally:
        connection.close()
    assert OLD_CHAIN_MARKER in names, names


def test_an_unknown_product_head_is_refused_by_restore(tmp_path, monkeypatch):
    """**认不出的产物头** ⇒ 响亮拒绝，⚠️ 而报错给出实到的前 16 字节的**十六进制**。

    ⚠️ 三档各一次：一个文本文件 / 一个 0 字节文件 / 一个由**别的**工具加密过的文件
    （拿 ``age`` 的魔数当样子）。⚠️ 而三档都走 ``--no-verify``：侧车那一格
    在这一档下**帮不上忙**（那一份文件可能压根没有侧车），故「认不出头」必须自己响。

    ⚠️ 报错里给十六进制而**不是原文**：那一份文件是什么谁都不知道，
    而原文可能是一个别的系统的秘密（与本模块「不印口令任何一部分」同一条纪律）。
    """
    _powershell()
    monkeypatch.delenv(backup.BACKUP_KEY_ENV_VAR, raising=False)
    backups = tmp_path / "backups"
    backups.mkdir()
    target = tmp_path / "target.db"
    _db_at_head(target, CHANGED_NAME)
    before = backup.sha256_of(target)

    cases = {
        "text.db": "这不是一份库".encode("utf-8"),
        "empty.db": b"",
        "age.db": b"age-encryption.org/v1\n" + b"\x00" * 64,
    }
    for name, payload in cases.items():
        product = backups / name
        product.write_bytes(payload)
        with pytest.raises(backup.BackupError) as excinfo:
            restore.main([name, "--dir", str(backups), "--no-verify",
                          "--db-url", "sqlite:///" + target.as_posix()])
        message = str(excinfo.value)
        assert "认不出" in message, (name, message)
        assert payload[:16].hex() in message, (name, message)
        assert backup.CONTAINER_MAGIC.decode("ascii") in message, (name, message)
    assert backup.sha256_of(target) == before


def test_the_pre_restore_safety_net_follows_the_passphrase(tmp_path, monkeypatch):
    """**步 ③ 的后路跟着口令走**：有口令 ⇒ 后路也是加密档；没有 ⇒ 明文档（与 Task 3 之前逐字相同）。

    ⚠️ 裁定：「本系统写出来的备份」只有**一种**形状 —— ``PE_BACKUP_KEY`` 在就都是加密档。
    反过来做（后路一律明文）会让**最紧急**的那一份（恢复前刚留的后路）恰好是
    整个目录里唯一一份明文，而它含的是**当前**全校学生的健康数据。

    ⚠️ 三拍：① 有口令 ⇒ 后路是加密档、而输出里标了【加密档】；
    ② 没有口令 ⇒ 后路是明文档、标了【明文档】；
    ③⚠️ 恢复一份**明文**备份时口令在 ⇒ 后路**也**加密（而输出会说清
    「这一份是明文档、它是在设那个变量之前做的」）。
    """
    _powershell()
    source = tmp_path / "source.db"
    _db_at_head(source, BACKED_UP_NAME)

    # ① 有口令
    first = tmp_path / "b1"
    first.mkdir()
    encrypted = backup.create_backup(source, first, passphrase=FAKE_PASSPHRASE)
    target = tmp_path / "target.db"
    _db_at_head(target, CHANGED_NAME)
    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, FAKE_PASSPHRASE)
    assert restore.main([encrypted.name, "--dir", str(first),
                         "--db-url", "sqlite:///" + target.as_posix()]) == 0
    nets = [p for p in first.iterdir() if p.name.endswith("-pre-restore.db")]
    assert len(nets) == 1 and backup.product_kind(nets[0]) == backup.KIND_ENCRYPTED, nets

    # ② 没有口令（⇒ 明文档，与 Task 3 之前逐字相同）
    second = tmp_path / "b2"
    second.mkdir()
    plain_backup = backup.create_backup(source, second)
    target2 = tmp_path / "target2.db"
    _db_at_head(target2, CHANGED_NAME)
    monkeypatch.delenv(backup.BACKUP_KEY_ENV_VAR, raising=False)
    assert restore.main([plain_backup.name, "--dir", str(second),
                         "--db-url", "sqlite:///" + target2.as_posix()]) == 0
    nets2 = [p for p in second.iterdir() if p.name.endswith("-pre-restore.db")]
    assert len(nets2) == 1 and backup.product_kind(nets2[0]) == backup.KIND_PLAINTEXT, nets2

    # ③ 明文备份 + 口令在 ⇒ 后路加密
    #    ⚠️ 换一个目录：``-pre-restore`` 的文件名只到**秒**，与②那一份撞在同一个目录里
    #    会**互相覆盖**（那是 create_backup docstring 里逐字记着的已知行为），
    #    于是「两份、两种形状」这个期望会红在夹具上、不是红在被测代码上。
    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, FAKE_PASSPHRASE)
    third = tmp_path / "b3"
    third.mkdir()
    plain_again = backup.create_backup(source, third)
    assert backup.product_kind(plain_again) == backup.KIND_PLAINTEXT
    target3 = tmp_path / "target3.db"
    _db_at_head(target3, CHANGED_NAME)
    assert restore.main([plain_again.name, "--dir", str(third),
                         "--db-url", "sqlite:///" + target3.as_posix()]) == 0
    nets3 = [p for p in third.iterdir() if p.name.endswith("-pre-restore.db")]
    assert len(nets3) == 1 and backup.product_kind(nets3[0]) == backup.KIND_ENCRYPTED, nets3


def test_restore_never_leaves_the_decrypted_plaintext_behind(tmp_path, monkeypatch, capsys):
    """解出来的那一份明文**从来不留在** ``backups/``、目标库那一层或系统临时目录里。

    ⚠️ 两拍，各挡一个不同的失效：① **成功**那一档：恢复跑完之后
    ``backups/`` 里只有产物 + 侧车 + 后路那两份、目标库那一层没有多出来的东西、
    系统临时目录里没有 ``pe-restore-*``；②⚠️ **失败**那一档（口令不对）同样不留
    —— 那一格更要紧，因为失败的路径最容易漏掉 ``finally``。
    """
    _powershell()
    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, FAKE_PASSPHRASE)
    source = tmp_path / "source.db"
    _db_at_head(source, BACKED_UP_NAME)
    backups = tmp_path / "backups"
    backups.mkdir()
    saved = backup.create_backup(source, backups, passphrase=FAKE_PASSPHRASE)

    leftovers = _temp_leftovers("pe-restore-")
    target = tmp_path / "target.db"
    _db_at_head(target, CHANGED_NAME)
    capsys.readouterr()
    assert restore.main([saved.name, "--dir", str(backups),
                         "--db-url", "sqlite:///" + target.as_posix()]) == 0
    assert _temp_leftovers("pe-restore-") == leftovers                    # ①
    assert [p.name for p in tmp_path.iterdir()
            if p.name.endswith(".body")] == []
    assert sorted(p.suffix for p in backups.iterdir()) == [".db", ".db", ".sha256", ".sha256"], (
        sorted(p.name for p in backups.iterdir())
    )

    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, OTHER_FAKE_PASSPHRASE)
    with pytest.raises(backup.BackupError):
        restore.main([saved.name, "--dir", str(backups),
                      "--db-url", "sqlite:///" + target.as_posix()])
    assert _temp_leftovers("pe-restore-") == leftovers                    # ②


# ===========================================================================
# ⚠️⚠️ 目标库**已损坏**那一档（Plan 08 Task 3 · 端到端实测当场撞出来的洞）
# ===========================================================================
#
# 「库坏了」恰恰是恢复**最常见**的理由，⚠️ 而改前这一档是
# ``sqlite3.DatabaseError: file is not a database`` 的**裸栈 + 退出码 1**：
# 步 ② 的锁检测只捕 ``OperationalError``、步 ③ 的 ``backup()`` 读不了它、
# 步 ④ 的 ``sqlite3_backup_init`` 也读不了它 ⇒ **最需要恢复的那一档恢复不了**。
# 逐字口径住在 :mod:`restore` 的模块 docstring「目标库已损坏那一档」那一节，
# 本节是它的**可执行**形式。


def _corrupt(path: pathlib.Path) -> bytes:
    """把一个库**改坏**（写一坨不是 SQLite 的字节进去），并返回那一坨字节。

    ⚠️ 返回它是为了后面能断言「步 ③ 留住的那一份**逐字**就是它」——
    而那一份是本档唯一的后路（步 ④ 会把目标文件覆盖掉）。
    """
    garbage = b"THIS IS NOT A SQLITE DATABASE \x00" * 40
    path.write_bytes(garbage)
    return garbage


def test_a_corrupt_target_is_restored_instead_of_answering_with_a_traceback(
    tmp_path, capsys
):
    """**明文档**那一档：目标库已损坏 ⇒ 恢复**成功**，⚠️ 而且**说清楚了**它做了什么。

    五拍，各挡一个失效形态：

    ① ``main`` 返回 **0**（改前是抛栈、退出码 1）；
    ② 那一行回到了备份点（= 恢复真的恢复了，不是「安静地什么都没做」）；
    ③ 自检报的表数是磁盘上真的那一个（**30** = 29 + ``alembic_version``）；
    ④⚠️ 输出里把「锁检测无从谈起」与「后路是逐字节副本」两格**都说了**
      （失效方向必须是响亮的：一次静默的放行 = 运维不知道自己刚刚覆盖了什么）；
    ⑤⚠️ 那一份后路**逐字**就是覆盖之前那坨字节，而它的产物头认不出
      （⇒ 它不会被误当成一份可恢复的备份）。
    """
    source = tmp_path / "source.db"
    _db_at_head(source, BACKED_UP_NAME)
    backups = tmp_path / "backups"
    backups.mkdir()
    saved = backup.create_backup(source, backups)
    assert backup.product_kind(saved) == backup.KIND_PLAINTEXT

    target = tmp_path / "target.db"
    _db_at_head(target, CHANGED_NAME)
    garbage = _corrupt(target)
    # ⚠️ 反空转：判据真的认得「这不是一个库」（否则下面全绿是因为夹具没改坏）
    assert not restore.is_readable_database(target)
    assert restore.is_readable_database(source)

    capsys.readouterr()
    code = restore.main([saved.name, "--dir", str(backups),
                         "--db-url", "sqlite:///" + target.as_posix()])
    out = capsys.readouterr().out
    assert code == 0, (code, out)                                        # ①
    assert _semester_name(target) == BACKED_UP_NAME                       # ②
    assert "sqlite_master 里的表数 = 30" in out, out                      # ③
    assert "已经不是一个可读的 SQLite 库" in out, out                        # ④
    assert "**逐字节副本**" in out, out
    nets = [p for p in backups.iterdir()
            if p.name.endswith(restore.CORRUPT_SAFETY_NET_LABEL + ".db")]
    assert len(nets) == 1, sorted(p.name for p in backups.iterdir())
    assert nets[0].read_bytes() == garbage                                # ⑤
    assert backup.product_kind(nets[0]) == backup.KIND_UNKNOWN
    assert restore.read_sidecar(backup.sidecar_of(nets[0]))["bytes"] == len(garbage)


def test_a_corrupt_target_is_restored_from_an_encrypted_backup_too(
    tmp_path, monkeypatch, capsys
):
    """同一档、而备份是**加密档**：步 ⓪（验 MAC + 解密）与「目标已损坏」互不干扰。

    ⚠️ 这一格是派单 §2 第 4 条与本档的**交叉**：加密那一层加了三步
    （认产物头 / 验 HMAC / 解密到系统临时目录），而目标库损坏那一档改了步 ②③④
    ⇒ 两侧**同时**发生时必须仍然绿，且系统临时目录里**不留**解出来的明文。
    """
    _powershell()
    monkeypatch.setenv(backup.BACKUP_KEY_ENV_VAR, FAKE_PASSPHRASE)
    source = tmp_path / "source.db"
    _db_at_head(source, BACKED_UP_NAME)
    backups = tmp_path / "backups"
    backups.mkdir()
    saved = backup.create_backup(source, backups, passphrase=FAKE_PASSPHRASE)
    assert backup.product_kind(saved) == backup.KIND_ENCRYPTED

    target = tmp_path / "target.db"
    _db_at_head(target, CHANGED_NAME)
    _corrupt(target)
    leftovers = _temp_leftovers("pe-restore-")

    capsys.readouterr()
    code = restore.main([saved.name, "--dir", str(backups),
                         "--db-url", "sqlite:///" + target.as_posix()])
    out = capsys.readouterr().out
    assert code == 0, (code, out)
    assert _semester_name(target) == BACKED_UP_NAME
    assert "HMAC-SHA256 验过" in out and "**逐字节副本**" in out, out
    assert _temp_leftovers("pe-restore-") == leftovers
    # ⚠️ 后路只有**一份**，而它是那一份逐字节副本（= 步 ③ 没有再去调 backup()：
    #    目标不是一个库，那一次调用只会抛）
    nets = [p for p in backups.iterdir()
            if p.name.endswith(restore.CORRUPT_SAFETY_NET_LABEL + ".db")]
    assert len(nets) == 1, sorted(p.name for p in backups.iterdir())
    assert not [p for p in backups.iterdir() if p.name.endswith("-pre-restore.db")]


def test_the_corrupt_safety_net_is_never_offered_as_a_restorable_backup(tmp_path):
    """拿那一份**逐字节副本**去恢复 ⇒ 响亮拒绝，⚠️ 而不是产出一个坏库。

    ⚠️ 这一格挡的是「运维在 ``backups/`` 里看见一个 ``pe-…-pre-restore-corrupt.db``、
    以为它是一份备份、于是拿它去恢复」：它**必须**当场被认不出产物头而拒掉，
    而目标库一个字节都不动。
    """
    source = tmp_path / "source.db"
    _db_at_head(source, BACKED_UP_NAME)
    backups = tmp_path / "backups"
    backups.mkdir()
    saved = backup.create_backup(source, backups)
    target = tmp_path / "target.db"
    _db_at_head(target, CHANGED_NAME)
    _corrupt(target)
    assert restore.main([saved.name, "--dir", str(backups),
                         "--db-url", "sqlite:///" + target.as_posix()]) == 0
    net = [p for p in backups.iterdir()
           if p.name.endswith(restore.CORRUPT_SAFETY_NET_LABEL + ".db")][0]

    other = tmp_path / "other.db"
    _db_at_head(other, CHANGED_NAME)
    before = backup.sha256_of(other)
    with pytest.raises(backup.BackupError) as excinfo:
        restore.main([net.name, "--dir", str(backups),
                      "--db-url", "sqlite:///" + other.as_posix()])
    message = str(excinfo.value)
    assert "认不出" in message and "产物头" in message, message
    assert backup.sha256_of(other) == before, "目标库被动过了"
    assert _semester_name(other) == CHANGED_NAME


def test_a_corrupt_target_with_no_auto_backup_still_restores(tmp_path, capsys):
    """``--no-auto-backup`` + 目标已损坏 ⇒ 仍然恢复成功，⚠️ 而**不留**任何后路。

    ⚠️ 这一格钉的是「那一份逐字节副本**不是**一个偷偷多出来的产物」：
    关掉后路它就一个字节都不写（关后路是一次显式的选择，语义必须一贯）。
    """
    source = tmp_path / "source.db"
    _db_at_head(source, BACKED_UP_NAME)
    backups = tmp_path / "backups"
    backups.mkdir()
    saved = backup.create_backup(source, backups)
    target = tmp_path / "target.db"
    _db_at_head(target, CHANGED_NAME)
    _corrupt(target)

    capsys.readouterr()
    code = restore.main([saved.name, "--dir", str(backups), "--no-auto-backup",
                         "--db-url", "sqlite:///" + target.as_posix()])
    out = capsys.readouterr().out
    assert code == 0, (code, out)
    assert _semester_name(target) == BACKED_UP_NAME
    assert "后路   无" in out, out
    assert sorted(p.name for p in backups.iterdir()) == [
        saved.name, saved.name + backup.SIDECAR_SUFFIX
    ], sorted(p.name for p in backups.iterdir())


@pytest.mark.skipif(sys.platform != "win32",
                    reason="「delete pending」是 Windows 的一格（POSIX 上 unlink 立刻生效）")
def test_a_corrupt_target_is_truncated_and_never_unlinked(tmp_path, capsys):
    """⚠️⚠️ 目标库被**清空**而不是被 ``unlink``（本 Task 端到端实测换来的那一格）。

    形状：一个**旁观者仍开着那个文件的句柄**（杀毒实时扫描 / 索引服务 /
    一个还没退干净的 SQLite 浏览器就是这一档）。此时——

    * ``unlink`` 在 Windows 上会**成功**，而文件进入「delete pending」：名字还在、
      **最后一个句柄一关整个文件就消失**。实测撞到的形状是：恢复的自检与事后的
      行数复核都读到 60 人，而起服务那一刻文件**不在了**，于是服务从零建了一个
      **空**库、``/api/health`` 报 ``students: 0``；
    * **清空到 0 字节**不删名字 ⇒ 那一档在结构上不可能发生，而 SQLite 把
      「0 字节文件」当成一个空库，``sqlite3_backup_init`` 照样能把它写成恢复出来的那一份。

    ⚠️ 三拍：① 句柄**开着**的时候恢复就成功（``unlink`` 那一版会在这里抛
    ``sqlite3.OperationalError: unable to open database file``）；② 句柄关掉之后
    那个文件**还在**、而且就是恢复出来的那一份；③ 目标库那一层没有多出
    ``-journal`` / ``-wal`` / ``-shm``（一个属于**旧**库的 ``-wal`` 会让
    下一次打开时恢复出一个坏库）。
    """
    source = tmp_path / "source.db"
    _db_at_head(source, BACKED_UP_NAME)
    backups = tmp_path / "backups"
    backups.mkdir()
    saved = backup.create_backup(source, backups)
    target = tmp_path / "target.db"
    _db_at_head(target, CHANGED_NAME)
    _corrupt(target)
    (target.parent / (target.name + "-wal")).write_bytes(b"stale wal of the OLD db")

    bystander = target.open("rb")            # ⚠️ 一个仍开着句柄的旁观者
    try:
        capsys.readouterr()
        code = restore.main([saved.name, "--dir", str(backups),
                             "--db-url", "sqlite:///" + target.as_posix()])
        assert code == 0, capsys.readouterr().out                        # ①
    finally:
        bystander.close()
    assert target.is_file(), "句柄关掉之后那个文件**消失了**（= 用了 unlink）"   # ②
    assert _semester_name(target) == BACKED_UP_NAME
    assert not (target.parent / (target.name + "-wal")).exists()                # ③
    assert not (target.parent / (target.name + "-journal")).exists()
    assert not (target.parent / (target.name + "-shm")).exists()

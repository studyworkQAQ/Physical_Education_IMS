"""从一份备份**恢复**库：校验侧车 → 自动留后路 → 覆盖 → 自检（Plan 06 Task 6）。

「库坏了怎么回到昨天的状态」这半个问题的答案。做备份的那一半在
``backend/scripts/backup.py``；本模块从它 import 五个名字（``BackupError`` /
``backup_database`` / ``create_backup`` / ``read_sidecar`` / ``resolve_db_path`` /
``sidecar_of``），⚠️ **一个都不重写**——尤其：

* 「URL → 磁盘文件」的解析是 :func:`app.db.session._db_file_of`（经
  :func:`backup.db_path_from_url`），本模块**没有**第二个解析器；
* 「禁区是哪两个」的判据是 :func:`backup._ensure_not_forbidden`（经
  :func:`backup.resolve_db_path`），本模块**没有**第二份禁区清单；
* 「侧车长什么样」的解析是 :func:`backup.read_sidecar`，本模块**没有**第二份格式。

--------------------------------------------------------------------------
⚠️⚠️ 四步的顺序是**承重的**（派单 §2 第 3 条）
--------------------------------------------------------------------------

===========  ==========================================  ================================
步            做什么                                       跳过它会怎样
===========  ==========================================  ================================
① 校验        侧车的 sha256 与字节数**都**要吻合           恢复一份被改过/被截断的备份，
                                                        得到的是一个坏库（而它看起来是好的）
② 锁检测      目标库正被写锁占住 → **一句人话** + 退出      裸 ``sqlite3.OperationalError``
                                                        的栈，运维读不出「请先停服务」
③ 自动备份    覆盖**之前**先给当前库留一份 ``-pre-restore`` 恢复本身造成**二次丢失**：
                                                        选错一份备份 = 现在这份也没了
④ 覆盖 + 自检  ``backup()`` 反向拷 + 打印表数与版本号       「恢复成功了」而库其实是空的
===========  ==========================================  ================================

⚠️ **③ 排在 ④ 之前**是派单逐字要求的（「覆盖前先对当前库做一次自动备份，避免恢复本身
造成二次丢失」）。⚠️ 派单 §4 把「③ 是否多余」列为本波最可能的顶回之一，
实现者**核过、不顶回**，两条理由：

1. 它挡的不是「备份坏了」（①已经挡了），而是**「人选错了备份」**——那是恢复这个动作
   里唯一无法用校验挡住的失效：一份 sha 完全吻合、而内容是三个月前的备份，
   恢复上去就把这三个月的数据删了。③ 是那一档**唯一**的后路。
2. 代价是**一个文件**（几十 MB），而不是一份需要人维护的策略。

⚠️ 而它**不是无条件**的：当前库不存在或是 0 字节时**跳过**（那两档下「自动备份」
会抛，而恢复一份不存在的库恰恰是合法且常见的动作——派单 §2 第 3 条要的是
「避免二次丢失」，没有东西可丢时就不该拦着）。

--------------------------------------------------------------------------
⚠️⚠️ 明文档与加密档都吃（Plan 08 Task 3）：判据是**产物头**，不是扩展名
--------------------------------------------------------------------------

两档的扩展名**逐字相同**（都是 ``pe-<UTC ts>.db``），而改前那些明文备份已经在
甲方手上了 ⇒ 「这一份是什么形状」只能由**产物头**回答
（``PEBACKUP`` = 加密档、``SQLite format 3\\0`` = 明文档）。
⚠️ 那一个判断的**唯一所有者**是 :func:`backup.product_kind`，本模块**没有**第二份魔数。

⚠️⚠️ 加密档多一步「**步 ⓪**：验 HMAC → 解密到系统临时目录」，⚠️ 而它排在
**步 ① 之后、步 ② 之后、步 ④ 之前**：

===========  ==========================================  ================================
步            做什么                                       跳过它会怎样
===========  ==========================================  ================================
① 校验        侧车两格（算的是**产物本身** = 头+密文+MAC）    一份拷坏的加密档会走到解密那一步
② 锁检测      与明文档逐字相同                              裸栈（且**白白**做了 0.5 s 的解密）
⓪ 验 + 解     HMAC-SHA256 **先验**、验过了才解密            ⚠️ 见下面那一段
③ 自动备份    与明文档逐字相同（⚠️ 有口令时**后路也加密**）    恢复本身造成二次丢失
④ 覆盖 + 自检  源是**解出来的那一份明文**（系统临时目录里）    「恢复成功了」而库其实是空的
===========  ==========================================  ================================

⚠️⚠️ **步 ⓪ 的形状是承重的**（派单 §2 第 4 条逐字要求：「密钥不对 → 不许静默产出
一个坏库，HMAC 先验、验不过就退出非 0 并说人话，⚠️ **不许走到解密那一步**」）：

* **HMAC 先验**：:func:`backup.verify_container` 是 encrypt-then-MAC 的读侧，
  它**只算 MAC**、不解密。⚠️ 那一格不是理论洁癖 —— 本 Task 实测过
  「只靠 AES-CBC 自己」的话**篡改密文不响**：改密文中间一个字节只坏那两个块，
  PKCS7 的 padding 常常仍然合法，``aes_cbc.ps1`` **退出码 0**、静默产出一个坏库
  （取证见 ``task-3-report.md`` §4/§5）；
* **验不过就抛**，⚠️ 而报错**同时**说两种可能（口令不对 / 产物被改过）——
  encrypt-then-MAC 之下两者在密码学上**不可分辨**，一个只说「口令不对」的报错
  会把运维支去反复试口令，一个只说「被改过」的报错会让他去查一个根本不存在的入侵；
* **解出来的明文落在系统临时目录**、``finally`` 里删掉，⚠️ **从来不落进
  ``backups/`` 或目标库所在的那个目录**（与 :func:`backup.create_backup` 的加密档
  同一条口径）。

⚠️ **认不出的产物头**（既不是明文 SQLite、也不是本仓的加密档）同样响亮拒绝，
而报错里给出**实到的前 16 字节的十六进制**（⚠️ 十六进制、不是原文：那一份文件
是什么谁都不知道，而原文可能是一个别的系统的秘密）。

⚠️⚠️ **``--no-verify`` 跳的是步 ①（侧车），步 ⓪ 的 HMAC 跳不掉** —— 它**没有**后门。
理由是两格答的不是同一个问题：侧车答「拷来拷去有没有坏」（那一份文件可能真的丢了），
HMAC 答「我解出来的东西是不是当初加密的那一份」（⚠️ 而跳过它就等于允许
「口令不对也照样解、解出一个坏库」，那正是派单逐字禁止的一档）。

⚠️ **有口令时步 ③ 的后路也加密**（``create_backup(..., passphrase=…)``）：
「本系统写出来的备份」这件事只有一种形状 —— ``PE_BACKUP_KEY`` 在就都是加密档。
⚠️ 而**没有**口令时（例如恢复一份改前的明文档）后路就是明文档，
与 Plan 08 Task 3 之前**逐字相同**。

--------------------------------------------------------------------------
⚠️ 覆盖用 ``backup()`` 反向拷，**不是** ``shutil.copyfile``
--------------------------------------------------------------------------

与 :mod:`backup` 那一条同款的理由（模块 docstring 第一节），而**恢复这一侧更要紧**：
目标库上可能还挂着一个 ``-journal`` 或 ``-wal`` 文件（上一次进程被杀留下的），
一个文件级的覆盖会让主库与它的 journal **对不上**——SQLite 下一次打开时会按
journal 回滚，于是「刚恢复上去的内容」被 journal 抹掉一部分。
:meth:`sqlite3.Connection.backup` 走的是 SQLite 自己的页级拷贝，
它在一个事务里做、并让目标库的 journal 状态自洽。

⚠️ 代价（如实记，硬规矩 #39）：``backup()`` 之后目标库的**页数**等于源库的页数，
而一个原本更大的目标文件**不会**被截断成更小的物理文件（SQLite 会重用那些游离页）。
故「恢复之后 ``.db`` 文件没变小」是正常的，不是没恢复。
自检那一格（④）打印的是**表数**与 ``alembic_version``，不是文件字节数。

--------------------------------------------------------------------------
⚠️ 退出码
----------------------------------------------------------------==========

=====  ==========================================
码      含义
=====  ==========================================
0      恢复成功（自检也跑过了）
2      一份**该拒绝**的恢复（校验不过 / 库被占 / 禁区 / 文件不在）
1      预期外的 bug（照常抛栈，不捕）
=====  ==========================================

⚠️ 派单 §2 第 3 条逐字要求「校验不过就拒绝并报错（**退出码非 0**）」。
两个 ``main()`` 只捕 :class:`backup.BackupError`，故「预期内的拒绝」与「预期外的 bug」
在退出码上可区分（2 vs 1），而后者**照常抛栈**——失效方向是响亮的。
"""
from __future__ import annotations

import argparse
import ast
import configparser
import os
import pathlib
import sqlite3
import sys
import tempfile

from app.db.session import ALEMBIC_INI, ALEMBIC_VERSION_TABLE

#: ⚠️ ``scripts/`` 不是包（没有 ``__init__.py``），故 ``import backup`` 要靠
#:    本文件所在目录在 ``sys.path`` 上。⚠️ **它是无条件的**：
#:    ``python scripts/restore.py`` 时 Python 会把脚本所在目录放进 ``sys.path[0]``
#:    （于是本段是冗余的），而 ``tests/test_backup_restore.py`` 用
#:    ``importlib`` 按路径加载本模块时**不会**（于是本段是承重的）。
#:    与 ``backend/migrations/env.py`` 那段 sys.path 兜底同一个形状。
_SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from backup import (  # noqa: E402
    BACKUPS_DIR,
    BACKUP_KEY_ENV_VAR,
    CONTAINER_MAGIC,
    KIND_ENCRYPTED,
    KIND_PLAINTEXT,
    KIND_UNKNOWN,
    SQLITE_MAGIC,
    BackupError,
    backup_database,
    create_backup,
    decrypt_container,
    product_kind,
    read_sidecar,
    resolve_backup_passphrase,
    resolve_db_path,
    sha256_of,
    sidecar_of,
)

__all__ = [
    "LOCK_TIMEOUT_SECONDS",
    "code_head_revisions",
    "restore_database",
    "selfcheck",
    "verify_backup",
]

#: 探锁时 ``BEGIN IMMEDIATE`` 的等待秒数。⚠️ **刻意短**（1 秒）：本档要的是
#: 「服务正在跑」这个**稳态**，而不是一次几毫秒的写事务；等 30 秒只会让运维
#: 以为脚本卡住了。⚠️ 而 :func:`backup.backup_database` 那一侧用的是 5 秒
#: （在线备份**可以**与服务并存，故它值得多等一会儿）——两个数不同是有意的。
LOCK_TIMEOUT_SECONDS = 1.0


def verify_backup(backup_path: pathlib.Path) -> dict[str, object]:
    """**步 ①**：侧车的两格（sha256 + 字节数）都要吻合；不吻合就 :class:`BackupError`。

    ⚠️ **两格都校验**，而不是「sha 对了就行」：字节数那一格让「侧车被人手工改过、
    而改的人只改了 sha」这一档也响（他得同时改对两格）。⚠️ 它**不是**冗余设计——
    派单 §2 第 5 条要的两种篡改里，第二种正是「篡改备份文件 1 字节」，
    那一档下**两格同时**失配，而报错要能说清是**哪一格**。

    三档失败，各报一句**能照着做**的人话：

    * 备份文件不在；
    * 侧车不在 / 侧车格式坏（由 :func:`backup.read_sidecar` 报，本函数不重写）；
    * sha256 或字节数不吻合 —— ⚠️ 那一档的 message 里**同时给出期望值与实测值的前 16 位**，
      于是运维能一眼看出「是完全不同的文件」还是「只差一点」（后者通常是截断）。

    ⚠️ **返回侧车那两格**（而不是 ``None``）：调用方
    （:func:`restore_database` 与 ``main``）要把它打印出来，
    而再读一次侧车就是第二次解析。
    """
    if not backup_path.is_file():
        raise BackupError(f"备份文件不存在：{backup_path}")
    sidecar = read_sidecar(sidecar_of(backup_path))
    actual_size = backup_path.stat().st_size
    if actual_size != sidecar["bytes"]:
        raise BackupError(
            f"拒绝恢复 {backup_path.name}：字节数不吻合。"
            f"侧车说 {sidecar['bytes']}，实测 {actual_size}"
            f"（差 {actual_size - int(sidecar['bytes'])} 字节）。"
            "⚠️ 这一份被动过或被截断过，恢复上去得到的是一个坏库。"
            "请换一份备份（backup.py 每做一次就留一份，侧车同名的那些都可以用）"
        )
    actual_sha = sha256_of(backup_path)
    if actual_sha != sidecar["sha256"]:
        raise BackupError(
            f"拒绝恢复 {backup_path.name}：sha256 不吻合。"
            f"侧车说 {str(sidecar['sha256'])[:16]}…，实测 {actual_sha[:16]}…。"
            "⚠️ 这一份被动过（哪怕只改了 1 个字节），恢复上去得到的是一个坏库——"
            "而它**看起来**是好的，故本脚本一律拒绝。请换一份备份"
        )
    return sidecar


def _assert_not_in_use(db_path: pathlib.Path) -> None:
    """**步 ②**：目标库正被写锁占住 → 一句**可读的**人话，不是裸异常。

    ⚠️ 判据是 ``BEGIN IMMEDIATE``：它要的是**写**锁，而一次只读的
    ``SELECT`` 在 WAL 模式下**不会**与写者冲突（于是「服务正在跑」会被漏判，
    而恢复会在覆盖到一半时撞锁）。⚠️ ``IMMEDIATE`` 在 rollback-journal 模式下
    拿的是 ``RESERVED`` 锁，同样会与任何正在写的事务冲突，故两档都判得出来。

    ⚠️ **它挡不住「服务在跑但此刻空闲」**：SQLite 的锁是**事务级**的，
    一个开着连接而没有在写事务里的 uvicorn 不持有任何锁。
    于是本检测是「**尽力**」的，不是「充分」的。⚠️ 如实记录（硬规矩 #39）：
    恢复前**仍然要停服务**（``main`` 每次都打印那一句），
    而本函数的职责是把「恰好撞上了」那一档从裸栈变成一句人话。
    要真的充分，得让服务自己建一个 ``.lock`` 文件（那是 Task 7 部署入口的活）。

    ⚠️ 目标库**不存在**时直接放行：那不是「被占用」，那是「恢复到一个新位置」，
    是合法且常见的动作（:func:`restore_database` 的③那一档也会跳过自动备份）。
    """
    if not db_path.is_file():
        return
    connection = sqlite3.connect(str(db_path), timeout=LOCK_TIMEOUT_SECONDS)
    try:
        connection.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as exc:
        message = str(exc).lower()
        if "locked" in message or "busy" in message:
            raise BackupError(
                f"目标库 {db_path} 正被别的进程占着（SQLite 报 {exc}）："
                "**请先停服务**再恢复。"
                "⚠️ 恢复要覆盖整个库文件，而一个正在写的 uvicorn 会让覆盖只落到一半"
                "（那一半在磁盘上不是一个自洽的库）。停服务的姿势见 "
                "backend/scripts/demo.ps1（前台跑的话 Ctrl-C 即可）；"
                "⚠️ 而本检测是**尽力**的：SQLite 的锁是事务级的，"
                "一个开着连接却空闲的服务不持锁，故「没报错」不等于「服务停了」"
            ) from exc
        raise BackupError(f"打不开目标库 {db_path}：{exc}") from exc
    else:
        connection.rollback()
    finally:
        connection.close()


def selfcheck(db_path: pathlib.Path) -> dict[str, object]:
    """**步 ④ 的后半**：恢复完的库**能不能打开、里面有什么**。

    三格，各答一个不同的问题（与 ``GET /api/health`` 那两格同一个立意：
    「schema 层面的数」与「一次真的查询」必须各有一格，否则证明不了「连上了正确的库」）：

    * ``tables`` —— ``sqlite_master`` 里 ``type='table'`` 的张数。
      ⚠️ **它比 ``/api/health`` 报的多 1**：health 数的是 ``Base.metadata``
      （**不含** ``alembic_version``），本函数数的是磁盘上的表。
      那一格差别由 ``tests/db/test_migration_baseline.py`` 的
      ``EXPECTED_TABLE_COUNT_WITH_VERSION`` 与 ``EXPECTED_TABLES`` 两个常量钉住，
      本函数**刻意**取磁盘那一侧：恢复要验的是「文件里有什么」，不是「模型声明了什么」。
    * ``revision`` —— ``alembic_version`` 里的那一个修订号（表不在就是 ``None``）。
      ⚠️ 这一格是**恢复之后最该看的一格**：它是 ``None`` 意味着这份备份来自
      「引入迁移链之前」的版本，下次起服务时 :func:`app.db.session.init_db`
      会走**档 2**（比对结构后 stamp 基线），而不是一次干净的 ``upgrade head``。
    * ``students`` —— ``student`` 表的行数（表不在就是 ``None``）。
      一次**真的查询**：它证明这个文件不只是「能被 sqlite3 打开」，
      而是一份**有内容**的库。

    ⚠️ 它**只读**（``mode=ro``）：自检不该在刚恢复好的库上留下任何写痕迹。
    ⚠️ 而它**故意不跑** :func:`app.db.session.init_db`：那会**改**库
    （``upgrade head``），而恢复的语义是「把库变成备份那一刻的样子」。
    起服务时 lifespan 自己会跑 ``init_db``（派单 §2 第 3 条要的是「打印自检」，
    不是「顺手升级」）。
    """
    connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro",
                                 uri=True, timeout=5.0)
    try:
        # ⚠️ ``fetchone()[0]`` 而不是 ``.scalar()``：后者是 **SQLAlchemy** 的
        # ``Result`` 上的方法，而本函数用的是标准库 ``sqlite3``（本波新增依赖 = 0，
        # 故这里刻意不经 SQLAlchemy）。⚠️ 本 Task 的第一版写了 ``.scalar()``、
        # 当场 ``AttributeError``——两个 API 长得像，而这一格只有真跑一次才响。
        tables = connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        names = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        revision = None
        if ALEMBIC_VERSION_TABLE in names:
            revision = connection.execute(
                f"SELECT version_num FROM {ALEMBIC_VERSION_TABLE}"  # noqa: S608
            ).fetchone()[0]
        students = None
        if "student" in names:
            students = connection.execute(
                "SELECT count(*) FROM student"
            ).fetchone()[0]
    finally:
        connection.close()
    return {"tables": tables, "revision": revision, "students": students}


def code_head_revisions() -> tuple[str, ...]:
    """**当前代码**那条迁移链的头（链分叉时会多于一个）。查不出来就回**空元组**。

    ⚠️⚠️ 本函数存在的全部理由（Plan 06 Task 15 / 终审 S4-⑤）：
    改前本脚本只**印**恢复后的 ``alembic_version``、**不判**它与代码的 head
    是不是同一个。于是一个不知道 ``7f3923d8af84`` 是什么的运维**看不出**
    「这一份备份比当前代码旧」，而那一格的后果是**静默**的：
    从「恢复完」到「下一次起服务」之间，那个库**真的停在旧链上**，
    此时若跑一个**不经** :func:`app.db.session.init_db` 的工具（直接 ``sqlite3`` 查、
    或一个旧的报表脚本），它看到的是**旧结构**。

    ⚠️ 它读的是 ``backend/alembic.ini`` 的 ``script_location``（「迁移链住在哪里」
    的唯一所有者是 :data:`app.db.session.ALEMBIC_INI` 指向的那个文件），
    故本模块**没有**第二份 ``migrations/`` 路径。

    ⚠️⚠️ **它刻意不 import alembic**，而是用标准库的 ``ast`` 读 ``versions/*.py``
    里那两个模块级常量（``revision`` / ``down_revision``），再取「没人当父亲的那一个」：
    ``tests/test_backup_restore.py`` 的 ``test_neither_script_copies_files_or_adds_a_dependency``
    逐字钉住「两个脚本 import 的非 ``app.*`` 顶层模块全部在
    ``sys.stdlib_module_names`` 里（``sqlalchemy`` 除外）」，而本波实测把它弄红了一次
    （第一版写的是 ``ScriptDirectory.from_config``）—— 那一条守卫的立意是
    「备份/恢复这两个脚本是**救灾工具**，不该拖着一条 ORM/迁移依赖链」，
    本波**不改守卫**、改自己（硬规矩 #66：账面不得与代码打架）。
    ⚠️ 代价（如实记）：本函数是「迁移链的头是谁」这个问题的**第二个读点**
    （alembic 自己是第一个），而它们会一起漂的那一档由
    ``tests/db/test_migration_chain.py`` 挡住（那一份逐字钉住 **4 单头**与四个修订号，
    且它走的是 alembic 自己的 ``ScriptDirectory``）—— 两侧不同源，故不是自指。
    ⚠️ 而它**不碰库**（只读 ``versions/`` 下的脚本），故不需要一个库 URL、
    也不会在刚恢复好的库上留下任何痕迹。
    ⚠️ 而它只是「多印一句人话」的附加信息，故它挂了也**不该**让一次已经成功的
    恢复变成失败 —— 回空元组，调用方如实印一句「比不了」。
    """
    try:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(ALEMBIC_INI, encoding="utf-8")
        location = parser.get("alembic", "script_location")
        versions = (ALEMBIC_INI.parent
                    / location.replace("%(here)s", ".") / "versions").resolve()
        revisions: dict[str, str | None] = {}
        for script in sorted(versions.glob("*.py")):
            revision = down = None
            for node in ast.parse(script.read_text(encoding="utf-8")).body:
                # ⚠️ 两档都要认：``revision = "x"`` 与 alembic 模板写出来的
                #    ``revision: str = "x"``（本仓四份迁移实测一律是后者）。
                target = None
                if isinstance(node, ast.Assign) and len(node.targets) == 1:
                    target = node.targets[0]
                elif isinstance(node, ast.AnnAssign):
                    target = node.target
                if not isinstance(target, ast.Name) or not isinstance(node.value, ast.Constant):
                    continue
                if target.id == "revision":
                    revision = node.value.value
                elif target.id == "down_revision":
                    down = node.value.value
            if isinstance(revision, str):
                revisions[revision] = down if isinstance(down, str) else None
        parents = {down for down in revisions.values() if down is not None}
        return tuple(sorted(set(revisions) - parents))
    except Exception:  # noqa: BLE001  ← 逐字理由见 docstring 末段
        return ()


def restore_database(
    backup_path: pathlib.Path,
    db_path: pathlib.Path,
    *,
    verify: bool = True,
    auto_backup: bool = True,
    backups_dir: pathlib.Path = BACKUPS_DIR,
    passphrase: str | None = None,
) -> dict[str, object]:
    """把 ``backup_path`` 那一份恢复成 ``db_path``；返回 ``{"sidecar", "safety_net", "selfcheck"}``。

    ⚠️⚠️ ``passphrase``（Plan 08 Task 3）有**两个**用途，⚠️ 而它**不从环境里自己读**
    （读环境的唯一一处是 :func:`main`，于是「密钥从哪来」在全仓只有一个住址）：

    1. 那一份产物是**加密档**时用它解密（⚠️ 先验 HMAC、验不过一步都不解密）；
    2. 步 ③ 那份 ``-pre-restore`` 后路**也**用它加密（``None`` 就是明文档，
       与 Task 3 之前逐字相同）。

    ⚠️ ``passphrase=None`` 且产物是加密档 ⇒ :class:`BackupError`（一句人话：
    怎么把口令设回去），⚠️ 而目标库**一个字节都没被改动**
    （那一格排在步 ④ 之前，与步 ①② 同一条口径）。

    四步的顺序与「跳过每一步会怎样」逐字见模块 docstring 第一节。

    ⚠️ ``verify=False`` 是**逃生口**（``--no-verify``）：侧车丢了、而运维确定那一份
    备份是好的时候用。⚠️ 它**只**跳过①，②③④ 一律照跑（跳过锁检测会得到一个
    覆盖到一半的库，跳过自动备份会得到一次不可逆的覆盖——两者都与「侧车丢了」无关）。
    ⚠️ 走这一档时 ``main`` 会**多打印一句警告**，因为它把「这一份没有被动过」
    这个断言从脚本转移到了人身上。

    ⚠️ ``auto_backup=False`` 同理（``--no-auto-backup``）：一个已经手工备份过、
    不想在 ``backups/`` 里多留一份的人用。⚠️ 派单 §4 顶回 ② 问的正是这一格
    「是否多余」，实现者**核过、维持**（两条理由逐字见模块 docstring 第一节），
    故缺省是 **True**，而关掉它是一次**显式**的动作。
    """
    sidecar = verify_backup(backup_path) if verify else None      # 步 ①
    kind = product_kind(backup_path)
    if kind == KIND_ENCRYPTED and passphrase is None:
        raise BackupError(
            f"{backup_path.name} 是一份**加密档**（产物头 {CONTAINER_MAGIC.decode('ascii')}），"
            f"而 ${BACKUP_KEY_ENV_VAR} 不在 ⇒ 没有口令就解不开它。"
            "⚠️ 请把**加密那一份时用的同一个口令**设回去再跑一次：\n"
            f'      $env:{BACKUP_KEY_ENV_VAR} = "<那一个口令>"\n'
            f"      powershell -ExecutionPolicy Bypass -File backend\\scripts\\restore.ps1 "
            f"{backup_path.name}\n"
            "⚠️ 本仓刻意不做密钥托管，也**没有**第二个后门：--no-verify 跳的是**侧车**"
            "那一格，HMAC 那一格跳不掉。⚠️ 目标库因此**没有被改动**"
        )
    if kind == KIND_UNKNOWN:
        with backup_path.open("rb") as handle:
            head = handle.read(max(len(CONTAINER_MAGIC), len(SQLITE_MAGIC)))
        raise BackupError(
            f"认不出 {backup_path.name} 的产物头：它既不是明文 SQLite（头 16 字节应当是 "
            f"{SQLITE_MAGIC!r}）、也不是本仓的加密档（头 8 字节应当是 {CONTAINER_MAGIC!r}）；"
            f"实到的前 {len(head)} 字节是 {head.hex()}。⚠️ 那通常意味着三档之一："
            "① 它被截断过或被别的文件覆盖过（一次没拷完的 U 盘）；"
            "② 给错文件了（它压根不是一份备份）；"
            "③ 它由**别的**工具加密过（age / gpg / BitLocker 的单文件加密），"
            "那三种本仓都读不了。⚠️ 目标库因此**没有被改动**"
        )
    _assert_not_in_use(db_path)                                   # 步 ②

    temp_plain: pathlib.Path | None = None
    source = backup_path
    container: dict[str, object] | None = None
    try:
        if kind == KIND_ENCRYPTED:                                # 步 ⓪
            handle, temp_name = tempfile.mkstemp(prefix="pe-restore-", suffix=".db")
            os.close(handle)
            temp_plain = pathlib.Path(temp_name)
            # ⚠️ decrypt_container 内部**先验 HMAC**、验不过就抛（一步都不解密）
            container = decrypt_container(backup_path, temp_plain, str(passphrase))
            source = temp_plain

        safety_net: pathlib.Path | None = None                    # 步 ③
        if auto_backup and db_path.is_file() and db_path.stat().st_size > 0:
            safety_net = create_backup(db_path, backups_dir,
                                       label="-pre-restore", passphrase=passphrase)

        size = backup_database(source, db_path)                   # 步 ④
        return {"sidecar": sidecar, "safety_net": safety_net,
                "bytes": size, "selfcheck": selfcheck(db_path),
                "kind": kind, "container": container,
                "safety_net_encrypted": (
                    safety_net is not None
                    and product_kind(safety_net) == KIND_ENCRYPTED
                )}
    finally:
        # ⚠️ 解出来的那一份明文**从来不留在 backups/ 或目标库那一层**：
        #    它落在系统临时目录里、而这里把它删掉（崩溃时最多在 %TEMP% 里留一份，
        #    与 backup.create_backup 的加密档同一条口径）。
        if temp_plain is not None:
            temp_plain.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    """``python scripts/restore.py <备份文件> [--db-url URL] [--no-verify] …``。

    ⚠️ 那个位置参数**既收文件名也收路径**：只给一个名字时按
    ``--dir``（缺省 :data:`backup.BACKUPS_DIR`）去拼。⚠️ 于是运维可以照
    ``backup.py`` 打印的最后一行原样粘过来（它打印的就是**文件名**），
    而不必先 ``cd`` 或先敲一长串绝对路径。
    """
    parser = argparse.ArgumentParser(
        description=(
            "从一份备份恢复本系统的 SQLite 库：先校验 .sha256 侧车（不吻合就拒绝）、"
            "再自动备份当前库（避免二次丢失）、然后覆盖、最后打印表数自检。"
            "⚠️ 请先停服务。"
        )
    )
    parser.add_argument("backup", help="备份文件名或路径（pe-<UTC ts>.db）")
    parser.add_argument(
        "--dir", default=None,
        help=f"只给文件名时去哪个目录找它。缺省 {BACKUPS_DIR}",
    )
    parser.add_argument(
        "--db-url", default=None,
        help="恢复成哪个库。缺省与 backup.py 逐字同源（PE_DB_URL > DEMO_DB_URL）",
    )
    parser.add_argument(
        "--no-verify", action="store_true",
        help="跳过侧车校验（⚠️ 侧车丢了才用；它把「这一份没被动过」的断言交给人）",
    )
    parser.add_argument(
        "--no-auto-backup", action="store_true",
        help="覆盖前不给当前库留后路（⚠️ 恢复因此变成不可逆的动作）",
    )
    args = parser.parse_args(argv)

    given = pathlib.Path(args.backup)
    if given.is_absolute() or given.parent != pathlib.Path("."):
        backup_path = given
    else:
        backups_dir = pathlib.Path(args.dir) if args.dir else BACKUPS_DIR
        backup_path = backups_dir / given.name
    if not backup_path.is_file():
        raise BackupError(
            f"找不到备份文件：{backup_path}。"
            f"⚠️ 只给文件名时本脚本去 {BACKUPS_DIR if not args.dir else args.dir} 找它；"
            "要指别处请给一个路径，或传 --dir"
        )

    db_path = resolve_db_path(args.db_url)
    # ⚠️⚠️ 口令**只在这一处**从环境里取（与 backup.py 的 main() 同一条纪律）
    passphrase = resolve_backup_passphrase()
    kind = product_kind(backup_path)
    print("== 厦大体育数智系统 · 恢复 ==")
    print("   备份   %s" % backup_path)
    print("   目标   %s" % db_path)
    if kind == KIND_ENCRYPTED:
        print("   形状   **加密档**（产物头 %s）⇒ 先验尾部那 32 字节的 HMAC-SHA256、"
              "验过了才解密" % CONTAINER_MAGIC.decode("ascii"))
        print("          口令来自 $%s（⚠️ 本脚本刻意不印它的任何一部分）"
              % BACKUP_KEY_ENV_VAR)
    elif kind == KIND_PLAINTEXT:
        print("   形状   **明文档**（产物头是 SQLite 自己的格式串）")
        if passphrase is not None:
            print("   ⚠️ $%s **在**，而这一份是明文档 ⇒ 它是在设那个变量**之前**做的。"
                  % BACKUP_KEY_ENV_VAR)
            print("      步 ③ 那份 -pre-restore 后路**会**被加密（本系统写出来的备份"
                  "只有一种形状）。")
    print("   ⚠️ 恢复会**覆盖**目标库。请先停服务（Ctrl-C 那个 uvicorn）。")

    result = restore_database(
        backup_path,
        db_path,
        verify=not args.no_verify,
        auto_backup=not args.no_auto_backup,
        backups_dir=pathlib.Path(args.dir) if args.dir else BACKUPS_DIR,
        passphrase=passphrase,
    )

    if args.no_verify:
        print("   ⚠️⚠️ --no-verify：**没有**校验侧车，故「这一份没有被动过」")
        print("      这个断言现在由你自己承担（脚本只能证明它拷过去了）。")
    else:
        print("   校验   sha256 %s… / %d 字节 ✓"
              % (str(result["sidecar"]["sha256"])[:16], result["sidecar"]["bytes"]))
    if result["kind"] == KIND_ENCRYPTED:
        container = result["container"] or {}
        print("   解密   HMAC-SHA256 验过 ✓（⚠️ 验不过就一步都不解密）；"
              "PBKDF2-HMAC-SHA256 × %s 次、明文 %s B"
              % (container.get("iterations"), container.get("plaintext_len")))
    if result["safety_net"] is not None:
        print("   后路   %s（覆盖前自动备份的当前库；恢复错了就用它再恢复一次）%s"
              % (result["safety_net"],
                 "【**加密档**】" if result["safety_net_encrypted"] else "【明文档】"))
    else:
        print("   后路   无（目标库此前不存在/是 0 字节，或传了 --no-auto-backup）")
    print("   字节   %d" % result["bytes"])
    check = result["selfcheck"]
    print("")
    print("   自检   sqlite_master 里的表数 = %s" % check["tables"])
    print("          %s = %s" % (ALEMBIC_VERSION_TABLE, check["revision"]))
    print("          student 行数 = %s" % check["students"])
    if check["revision"] is None:
        print("   ⚠️ 这份备份里**没有** %s 表：它来自引入迁移链之前的版本。"
              % ALEMBIC_VERSION_TABLE)
        print("      下次起服务时 init_db 会走**档 2**（比对结构后 stamp 基线再 upgrade head），")
        print("      而不是一次干净的 upgrade head。逐字口径见 app/db/session.py 的 init_db。")
    # ⚠️⚠️ **Plan 06 Task 15 / 终审 S4-⑤**：把恢复后的版本号与**当前代码**的 head
    #    比一次，不一致就印一句响亮的 ⚠️。改前本脚本只**印**不**判**，
    #    而那一格的后果是静默的（逐字理由见 :func:`code_head_revisions`）。
    #    ⚠️ 而它**刻意不是硬失败**：本仓实测过这一档**会自愈**
    #    （起服务时 init_db 自己 ``upgrade head``、被迁移改过的那一列宽度回到新值、
    #    标记数据一行都没丢），而一个非 0 退出码会把一条能自愈的路堵死
    #    （运维会以为「恢复失败了」而去再恢复一次）。
    heads = code_head_revisions()
    if check["revision"] is not None and heads and check["revision"] not in heads:
        print("")
        print("   ⚠️⚠️⚠️ 这一份备份的迁移版本比**当前代码旧**：")
        print("      备份停在    %s" % check["revision"])
        print("      代码的 head  %s" % " / ".join(heads))
        print("      ⇒ 从**现在**到**下一次起服务**之间，这个库真的停在那条旧链上：")
        print("        此时若用一个**不经** init_db 的工具直接读它（sqlite3 命令行、")
        print("        一个旧的报表脚本），它看到的是**旧结构**（例如被某一条迁移")
        print("        改宽过的那一列仍然是旧宽度）。⚠️ 在补齐之前请不要这样读它。")
        print("      ⇒ 起服务时 init_db 会自己 upgrade head 补齐（本仓实测过这一档：")
        print("        日志里会出现一行 Running upgrade <备份停的那个> -> <head>、")
        print("        被迁移改过的那一列回到新值、标记数据一行都没丢），")
        print("        故本脚本**刻意不把它当成失败**（退出码仍然是 0）。")
    elif check["revision"] is not None and not heads:
        print("")
        print("   ⚠️ 读不出当前代码的迁移链头（alembic 不可用？），故本脚本**没能**比对")
        print("      备份的版本与代码的版本。请自己核一次 alembic heads 再起服务。")
    print("")
    print("   ⚠️ 表数比 GET /api/health 报的**多 1**：health 数的是 Base.metadata")
    print("      （不含 %s），本自检数的是磁盘上的表。" % ALEMBIC_VERSION_TABLE)
    print("   现在可以起服务了：backend\\scripts\\demo.ps1 -Port 8000（⚠️ 它会**删掉**")
    print("   演示库重灌，故要保住刚恢复的这份请手工起 uvicorn，见 demo.ps1 的模块注释）。")
    return 0


if __name__ == "__main__":
    BACKEND = pathlib.Path(__file__).resolve().parents[1]
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    try:
        sys.exit(main())
    except BackupError as exc:
        print("恢复失败（拒绝执行）：%s" % exc, file=sys.stderr)
        sys.exit(2)

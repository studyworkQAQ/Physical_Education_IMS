"""**在线**备份 SQLite 库 + 写一份 sha256 侧车（Plan 06 Task 6）。

「库坏了怎么回到昨天的状态」这半个问题的答案。另半个（恢复）在
``backend/scripts/restore.py``；两个薄包装 ``backup.ps1`` / ``restore.ps1`` 只是给运维
一个双击/一行命令的姿势，**逻辑一律住在本文件与 ``restore.py``**（可测试、可守卫）。

--------------------------------------------------------------------------
⚠️⚠️ 用 SQLite 的 ``backup()`` API，**不是复制文件**（派单 §2 第 2 条）
--------------------------------------------------------------------------

:meth:`sqlite3.Connection.backup` 走的是 SQLite 自己的在线备份接口
（``sqlite3_backup_init`` / ``_step`` / ``_finish``）。它与 ``shutil.copyfile`` 的差别
不是「快慢」，而是**正确性**：

* 复制文件在**写进行中**会坏。SQLite 的一次写事务在 rollback-journal 模式下会先写
  ``-journal`` 文件、提交时才回滚进主库；WAL 模式下更是把新页写在 ``-wal`` 里、
  主库文件**滞后**。于是一个正在被 uvicorn 写的库，它的 ``.db`` 文件在磁盘上
  **不是一个自洽的库**——复制出来的那一份可能少了半个事务，
  恢复上去就是 ``sqlite3.DatabaseError: file is not a database`` 或（更糟）
  「能打开、而某些行是半截的」。
* ``backup()`` 则在一个**读事务**里逐页拷，故它拿到的永远是某一个时刻的**一致快照**，
  且**不阻塞**写（它只在每一步之间短暂让出）。

⚠️ **它因此可以在服务跑着的时候做**（这是「每天夜里 cron 一次」能成立的前提）。
⚠️ 而 :mod:`restore` 那一侧**相反**：恢复要覆盖目标库，必须**先停服务**
（那边有一道可读的锁检测，理由逐字见它的 docstring）。
两者的不对称是有意的，不是疏忽。

--------------------------------------------------------------------------
⚠️ 库路径与 app **同源**（派单 §2 第 4 条）
--------------------------------------------------------------------------

``PE_DB_URL`` → :func:`sqlalchemy.engine.make_url` → :func:`app.db.session._db_file_of`。
⚠️ **不写第二个解析器**：``sqlite:///C:/x/pe_demo.db`` 的第三段之后全是路径，而
Windows 的盘号里就有一个冒号，手工 ``url.removeprefix("sqlite:///")`` 在 UNC 路径
（``sqlite:////server/share/x.db``）上会错——``backend/scripts/demo.ps1`` 的注释里
逐字记着同一个坑。:func:`app.db.session._db_file_of` 已经是「URL → 磁盘文件」的
唯一所有者（它还要认「内存库」与「非 SQLite」两档），故本模块**调它**。

⚠️ 而**缺省值刻意不等于** :func:`app.main._resolve_db_url` 的缺省值：那一个回落到
:data:`app.config.DEFAULT_DB_URL` = ``backend/pe.db``，本仓的**禁区**。
本模块回落到 :data:`app.main.DEMO_DB_URL`（= ``backend/pe_demo.db``），
与 ``backend/scripts/demo.ps1`` 逐字一致（它就是先把 ``DEMO_DB_URL`` 读进
``PE_DB_URL`` 再起服务的）。⚠️ 于是**两个脚本在结构上碰不到 ``pe.db``**，
:func:`_ensure_not_forbidden` 那一道守卫是第二重（与 ``demo.ps1`` 的⑤那一步、
``demo_bootstrap.py`` 的两道前置守卫同一个姿势：失效方向是「当场退出」，不是「静默操作禁区」）。

--------------------------------------------------------------------------
⚠️ 侧车文件的格式：**不是** coreutils 的 ``sha256sum`` 格式
--------------------------------------------------------------------------

::

    sha256=<64 个十六进制字符>
    bytes=<整数>

⚠️ 派单 §2 第 2 条要的是「备份文件的 sha256 **+ 字节数**」两格，而 coreutils 的
``<hex>  <文件名>`` 一行装不下第二格。⚠️ **刻意不做「半兼容」**
（第一行照 coreutils 写、第二行塞字节数）：``sha256sum -c`` 会把第二行报成
一条格式错误，于是「一个看起来能用的标准文件」在标准工具下**响一半**——
那比一个明显是自己的格式更坏（运维会以为备份坏了）。
故本格式**自描述**：两个 ``key=value``，:func:`read_sidecar` 是它唯一的解析方。

⚠️ **字节数不是冗余**：sha256 已经能查出任何改动，而字节数让
「一个被截断到 0 字节的备份」在**算 sha 之前**就能被认出来（0 字节的 sha256 是
``e3b0c442…``，一个合法的值），也让 ``ls -l`` 一眼能看出哪一份是空的。
两格都由 :func:`read_sidecar` 校验，:mod:`restore` 两格都要求吻合。

--------------------------------------------------------------------------
⚠️⚠️ 保留策略 ``--keep N``（Plan 08 Task 3）：判据是**文件名里的时间戳**
--------------------------------------------------------------------------

「哪几份算旧」这件事**只有一个所有者**：:data:`BACKUP_NAME_RE` +
:func:`list_backup_products`。⚠️ 判据是**文件名里那个 UTC 时间戳**，
**不是** ``LastWriteTime``。两者的差别恰好落在派单点名的那一档上：

===========================  ==================================  ==============================
                             文件名时间戳（本模块选的）            ``LastWriteTime``
===========================  ==================================  ==============================
它答的问题                   「这一份是**什么时候的库**」          「这个**文件**什么时候被写过」
从别的机器/U 盘拷进来的一份    仍然报出它**快照**的那一刻           报出「拷贝那一刻」（= 刚刚）
⇒ ``-Keep 7`` 会             留下**最新的 7 个快照**              留下「最近被拷进来的 7 个文件」
===========================  ==================================  ==============================

⚠️ 保留策略要回答的是「我还留着哪几天的库」，那是**快照**的属性、不是文件的属性：
一份上周做的备份今天被拷回来，它**仍然是上周的那一份**——按 ``LastWriteTime``
排序会让它插到队首、把真正更新的那几份挤出去删掉。故取文件名那一侧。

⚠️ 而文件名**认不出**的那些一律**不碰**（:func:`list_backup_products` 的第二个返回值，
逐个打印出来）：失效方向是「多留一份」，不是「删错一份」。于是控制者手工做的
``pe_trial-pre-migration5-20261017-201257.db`` 这类**不是** ``pe-<UTC ts>.db`` 形状的文件
对 ``-Keep`` 是**隐形**的（⚠️ 删备份不可逆，故这里刻意保守）。

⚠️ **``.sha256`` 侧车跟着一起删**：留下一个指不到东西的侧车比不留更坏——
它让 :func:`restore.verify_backup` 在**下一次**恢复时报「备份文件不存在」，
而运维看着那个侧车会以为备份还在。

⚠️⚠️ **``-Keep 0`` 一律拒**（:data:`MIN_KEEP` = 1）：它的字面意思是「一份都不留」
——连**这一次刚做出来的那一份**也删掉，而那几乎肯定不是运维想要的
（最常见的一档是一个没设上的变量落成了 ``0``）。⚠️ 拒绝发生在**任何一次写之前**：
那一档下这一次备份**也不做**，目录里一个文件都没动（与 :mod:`retention` 对
「窗口 0 天」同一条口径：破坏性参数的失效方向必须是「什么都不做 + 退出码 2」）。

⚠️ **``-pre-restore`` 那些后路与普通备份在同一个池子里**：它们**也是**这台库的一个快照，
而把它们排除在外就等于给 ``backend/backups/`` 又留了一个**永不收缩**的角落
（那正是本件要收掉的东西）。⚠️ 删除清单里**逐个印出 label**，故运维看得见
自己正要删掉几份「恢复前留的后路」。

--------------------------------------------------------------------------
本模块刻意不做的事
--------------------------------------------------------------------------

* ~~**不做保留策略**（「只留最近 7 份」）~~ → ⚠️⚠️ **Plan 08 Task 3（2026-10-17）做掉了**：
  ``--keep N``（薄包装 ``backup.ps1`` 上是 ``-Keep N``）在**这一次备份做完之后**按快照时刻
  删旧的，⚠️ 而**缺省不删** —— 不传 ``--keep`` 时本模块的行为与 Task 3 之前**逐字相同**
  （那正是当初那一句「由运维显式选，而不是让脚本自己删」的落地）。
  判据、失效方向与「侧车跟着一起删」逐字见下面「保留策略」那一节。
* **不压缩**：SQLite 库压缩比很高，而压缩要一个第三方库或 ``shutil`` 的
  ``tarfile`` 路径；``.backup()`` 之后直接落一个 ``.db`` 让运维能用任何 SQLite
  客户端**直接打开看**（「昨天那份里到底有没有那一行」这个问题不必先恢复）。
* **不加密**：备份里是全校学生的体测与健康数据。⚠️ 如实记录（硬规矩 #39）：
  今天 ``backend/backups/`` 下是一份**明文** SQLite 文件，它的保护等于那台机器的
  文件系统权限。生产上要么把 ``backups/`` 放在加密卷上，要么在落盘前过一层
  ``age`` / ``gpg``——两者都超出本 Task 的范围（且都要一个新依赖，而本波新增依赖 = 0）。
  已写进 spec §13 的已知局限。
* **不碰 ``backend/data/**``**：本模块只读一个库文件、只往 ``backend/backups/`` 写。
  那两个禁区（``backend/pe.db`` 不得存在、``backend/data/seed/`` 恒为 0 文件）
  由 :func:`_ensure_not_forbidden` 与 ``tests/test_backup_restore.py`` 双向钉住。
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import os
import pathlib
import re
import sqlite3
import sys
from typing import Callable

from app.config import BACKEND_DIR
from app.db.session import _db_file_of

#: ⚠️ ``app.main`` **刻意不在模块顶层 import**（与 ``backend/migrations/env.py`` 同一条
#: 口径，逐字理由也相同）：``app.main`` 有一条模块级的 ``app = create_app()``，
#: 放进顶层会让「import 一个备份脚本」顺带装配一次 FastAPI 应用
#: （造引擎、装中间件、注册路由）。本模块只需要它那两个**常量**，
#: 故在 :func:`resolve_db_path` 的函数体里取。

__all__ = [
    "BACKUPS_DIR",
    "MIN_KEEP",
    "SIDECAR_SUFFIX",
    "BackupEntry",
    "backup_database",
    "create_backup",
    "db_path_from_url",
    "list_backup_products",
    "prune_backups",
    "read_sidecar",
    "resolve_db_path",
    "sha256_of",
    "sidecar_of",
    "write_sidecar",
]

#: 备份落在哪里。⚠️ **它是「备份目录叫什么」的唯一所有者**：``restore.py``、
#: 两个 ``.ps1`` 包装与 ``.gitignore`` 里那一行都从这里读（``.gitignore`` 那一行
#: 是字面量，故 ``tests/test_backup_restore.py`` 把两侧对拍一次）。
#: ⚠️ 它在 ``.gitignore`` 里：备份是**运行时产物**，入库等于把一学期的学生健康数据
#: 提交进版本控制（而 git 历史删不掉）。
BACKUPS_DIR: pathlib.Path = BACKEND_DIR / "backups"

#: 侧车文件的后缀。⚠️ 派单 §2 第 2 条逐字要求「**同名**的 ``.sha256`` 侧车文件」。
SIDECAR_SUFFIX = ".sha256"

#: 备份文件名的时间戳格式。**UTC**（``Z`` 后缀）。
#: ⚠️ 这里用 UTC 与 ``audit_log.at`` 用本地时刻**不冲突**：那一列要与人读的日志、
#: 与 ``user_session.last_seen_at`` 对齐（逐字理由见 :class:`app.db.models.audit.AuditLog`
#: 的 ``at``），而**文件名**要的是「全球唯一且可排序」——一个 cron 在 UTC 0 点跑的
#: 备份，它的名字里写本地时刻会让「哪一份是昨天的」这个问题在跨时区的机器上有两个答案。
#: ⚠️ 派单 §2 第 2 条逐字给的就是 ``pe-<UTC ts>.db``。
TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"

#: 禁区文件名。⚠️ 判据是**文件名**、不是路径前缀：``backend/pe.db`` 的语义是
#: 「``app.seed.generate`` 写出来的那份不可复现的库」（``tests/test_config.py`` 的模块
#: docstring），而 ``pe_demo.db`` 只差四个字符——错的那一个是禁区。
FORBIDDEN_DB_NAME = "pe.db"


class BackupError(RuntimeError):
    """一次备份/恢复**该拒绝**的动作。

    ⚠️ 它是一个具名异常而不是裸 :class:`RuntimeError`：两个 ``main()`` 只捕它，
    于是「预期内的拒绝」打印一句人话 + 退出码非 0，而「预期外的 bug」照常抛栈
    （失效方向是响亮的，与 :func:`app.deploy.tier` 对认不出的 ``PE_ENV`` 同一条口径）。
    """


def db_path_from_url(url: str) -> pathlib.Path:
    """一个 ``sqlite:///`` URL → 它指向的**磁盘**文件。

    ⚠️ 复用 :func:`app.db.session._db_file_of`（「URL → 磁盘文件」的唯一所有者），
    **不写第二个解析器**——逐字理由见模块 docstring 第二节。
    ⚠️ 那个函数对「内存库」与「非 SQLite」两档返回 ``None``，本函数把两档都折成
    :class:`BackupError`：备份一个 ``sqlite://`` 是没有意义的（它活不过一个进程），
    而备份一个 PostgreSQL 不是本 Task 的范围（spec §15 把非 SQLite 排在第三批）。
    """
    from sqlalchemy.engine import make_url

    try:
        made = make_url(url)
    except Exception as exc:  # noqa: BLE001  一个坏 URL 要报成「坏 URL」，不是抛栈
        raise BackupError(f"解析不了这个数据库 URL：{url!r}（{exc}）") from exc
    path = _db_file_of(made)
    if path is None:
        raise BackupError(
            f"这个 URL 不指向一个磁盘上的 SQLite 文件，故备份/恢复无从谈起：{url!r}。"
            "⚠️ 内存库（sqlite:// 或 :memory:）活不过一个进程，而非 SQLite 后端"
            "不是本脚本的范围（spec §15 把它排在第三批）"
        )
    return path


def resolve_db_path(explicit: str | None = None) -> pathlib.Path:
    """要操作的那个库文件：``--db-url`` 实参 > ``PE_DB_URL`` > :data:`app.main.DEMO_DB_URL`。

    ⚠️⚠️ **缺省值是 ``DEMO_DB_URL`` 而不是 :func:`app.main._resolve_db_url` 的那个**
    （后者回落到 :data:`app.config.DEFAULT_DB_URL` = 禁区 ``backend/pe.db``）。
    逐字理由见模块 docstring 第二节。⚠️ 于是本函数**在结构上**返回不了禁区路径，
    而 :func:`_ensure_not_forbidden` 是第二重（它挡的是「有人显式把
    ``--db-url sqlite:///…/pe.db`` 敲进来」与「有人把 ``PE_DB_URL`` 设成了它」两档）。

    ⚠️ 空字符串按「没设」处理（``or``）：``$env:PE_DB_URL = ""`` 在 PowerShell 里是
    「设了一个空值」而不是「删掉这个变量」（:func:`app.main._resolve_db_url` 同一条口径）。
    """
    url = (explicit or os.environ.get(_env_var(), "") or _demo_url()).strip()
    path = db_path_from_url(url)
    _ensure_not_forbidden(path)
    return path


def _env_var() -> str:
    """:data:`app.main.DB_URL_ENV_VAR` —— 在**函数体内**取，理由见模块顶层那段注释。"""
    from app.main import DB_URL_ENV_VAR

    return DB_URL_ENV_VAR


def _demo_url() -> str:
    """:data:`app.main.DEMO_DB_URL` —— 同上。⚠️ 它是「演示库叫什么」的唯一所有者，
    故本模块**不写第二遍那个路径**（``demo.ps1`` 也是从它读出来的）。"""
    from app.main import DEMO_DB_URL

    return DEMO_DB_URL


def _ensure_not_forbidden(path: pathlib.Path) -> None:
    """**禁区守卫**：``backend/pe.db`` 与 ``backend/data/**`` 一律拒绝。

    与 ``backend/scripts/demo.ps1`` 的⑤那一步、``demo_bootstrap.py`` 的两道前置守卫
    同一个姿势：失效方向必须是「当场退出 + 一句人话」，不是「静默操作禁区」。

    ⚠️ 三档，逐档点名：

    1. **``backend/pe.db``** —— 它**不得存在**（Global Constraints）。
       ⚠️ 备份它看似无害（只读），而恢复它会**建出**它；且它一旦存在，
       本仓那十几条禁区守卫会一起红在一个与本脚本无关的地方。
    2. **``backend/data/**`` 下的任何东西** —— 那一片是「专家维护的知识资产」
       （国标评分表 / 常模 / 阈值 YAML / 18 份处方模板），**一个字节都不许动**，
       而 ``backend/data/seed/`` 更是恒为 0 文件。
    3. ⚠️ 判据一律用 :meth:`pathlib.Path.resolve`：``backend/../backend/pe.db`` 与
       ``backend/./data/x.db`` 这类写法在字符串口径下会绕过前两道。
    """
    resolved = path.resolve()
    if resolved.name == FORBIDDEN_DB_NAME and resolved.parent == BACKEND_DIR.resolve():
        raise BackupError(
            f"拒绝操作 {resolved}：backend/pe.db 是本仓的**禁区**（它不得存在）。"
            f"要备份演示库请设 ${_env_var()}"
            '（`python -c "from app.main import DEMO_DB_URL; print(DEMO_DB_URL)"` 读出来），'
            "或者干脆不设它——本脚本的缺省值就是那一个（与 backend/scripts/demo.ps1 一致）"
        )
    data_dir = (BACKEND_DIR / "data").resolve()
    if data_dir in resolved.parents or resolved == data_dir:
        raise BackupError(
            f"拒绝操作 {resolved}：backend/data/** 是专家维护的知识资产，"
            "一个字节都不许动（而 backend/data/seed/ 恒为 0 文件）"
        )


def sha256_of(path: pathlib.Path) -> str:
    """一个文件的 sha256（十六进制小写）。**分块读**，故它不把整个库读进内存。

    ⚠️ 块大小 1 MiB：一个 5 MB 的演示库一次读完也无所谓，而甲方现场一学期的库
    是 GB 量级——``path.read_bytes()`` 在那一档会把整份库塞进内存。
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sidecar_of(backup_path: pathlib.Path) -> pathlib.Path:
    """备份文件 → 它**同名**的侧车文件（``pe-….db`` → ``pe-….db.sha256``）。

    ⚠️ 是 ``with_name(name + SUFFIX)`` 而不是 ``with_suffix(SUFFIX)``：后者会把
    ``.db`` **换掉**（得到 ``pe-….sha256``），于是「同名」不成立、而两个文件的关系
    要靠猜。派单 §2 第 2 条逐字要求「**同名**的 ``.sha256`` 侧车文件」。
    """
    return backup_path.with_name(backup_path.name + SIDECAR_SUFFIX)


def write_sidecar(backup_path: pathlib.Path) -> pathlib.Path:
    """给一个**已经写好**的备份文件写侧车；返回侧车路径。

    ⚠️ **它现算 sha256 与字节数**，不接受调用方交进来的值：两格都由本函数从
    磁盘上那一个文件读出来，于是「侧车说的」与「文件实际是」**不可能**不一致
    （交给调用方填的话，一个先算 sha、后写文件的顺序错误会产出一份恒不吻合的侧车）。
    """
    if not backup_path.is_file():
        raise BackupError(f"备份文件不存在，写不出侧车：{backup_path}")
    text = "sha256=%s\nbytes=%d\n" % (
        sha256_of(backup_path), backup_path.stat().st_size
    )
    sidecar = sidecar_of(backup_path)
    # ⚠️ 侧车一律 **UTF-8 无 BOM + LF**：它是给 :func:`read_sidecar` 与
    # ``Get-Content`` 读的机器文件，不是给人读的文档；而一个 BOM 会让
    # ``line.split("=", 1)[0]`` 在第一行拿到 ``"\\ufeffsha256"``（一个静默的失配）。
    sidecar.write_bytes(text.encode("utf-8"))
    return sidecar


def read_sidecar(sidecar: pathlib.Path) -> dict[str, object]:
    """侧车文件 → ``{"sha256": str, "bytes": int}``。格式不对就 :class:`BackupError`。

    ⚠️ **它是那个格式的唯一解析方**（模块 docstring 第四节）。三档失败各报一句人话：
    文件不在 / 缺一个键 / 值解析不出来。⚠️ 而「sha 不吻合」**不在这里**报——
    那是 :func:`restore.verify_backup` 的活（本函数只负责「侧车说了什么」，
    不负责「它说的是不是真的」；两件事分开，于是「侧车坏了」与「备份被改过」
    在报错上可区分）。
    """
    if not sidecar.is_file():
        raise BackupError(
            f"侧车文件不存在：{sidecar}。⚠️ 没有它就无法证明那一份备份没有被动过，"
            "故恢复会被拒绝（要跳过校验请显式传 --no-verify，而那等于自己承担风险）"
        )
    got: dict[str, object] = {}
    for lineno, line in enumerate(
        sidecar.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        key, sep, value = line.partition("=")
        if not sep:
            raise BackupError(
                f"侧车文件 {sidecar} 的第 {lineno} 行不是 key=value：{line!r}"
            )
        got[key.strip()] = value.strip()
    missing = {"sha256", "bytes"} - set(got)
    if missing:
        raise BackupError(
            f"侧车文件 {sidecar} 缺 {sorted(missing)}（实到 {sorted(got)}）："
            "它应当由 backup.py 写出来，两格都在"
        )
    try:
        size = int(str(got["bytes"]))
    except ValueError as exc:
        raise BackupError(
            f"侧车文件 {sidecar} 的 bytes 不是一个整数：{got['bytes']!r}"
        ) from exc
    digest = str(got["sha256"])
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise BackupError(
            f"侧车文件 {sidecar} 的 sha256 不是 64 个十六进制字符：{digest!r}"
        )
    return {"sha256": digest, "bytes": size}


def backup_database(source: pathlib.Path, destination: pathlib.Path) -> int:
    """把 ``source`` **在线**备份到 ``destination``；返回目标文件的字节数。

    ⚠️ 用的是 :meth:`sqlite3.Connection.backup`（模块 docstring 第一节：
    复制文件在写进行中会坏）。

    ⚠️ **目标已存在时先删掉**：``backup()`` 会覆盖目标库的**内容**，
    而一个比源更大的旧目标会留下尾部的游离页（SQLite 会按 ``backup`` 的页数截断，
    故实际上不会——但显式删掉让「目标就是这一次的产物」这件事在代码里看得见，
    而不是依赖一个 API 细节）。
    ⚠️ 而**删之前先确认源能打开**：反过来做的话，一个坏掉的源会先把上一次的好备份删掉。

    ⚠️ 源文件不存在时是 :class:`BackupError`（一句人话）而不是 ``sqlite3.OperationalError``
    的裸栈：SQLite 对「打开一个不存在的文件」的缺省行为是**建一个空库**，
    于是「库路径写错了」会静默产出一份 0 张表的备份——那比报错坏得多。
    故本函数显式 ``uri=True`` + ``mode=ro`` 打开源：只读模式下文件不存在会当场抛。
    """
    if not source.is_file():
        raise BackupError(
            f"要备份的库文件不存在：{source}。⚠️ 本脚本刻意不让 SQLite「打开即建」："
            "那会把「路径写错了」变成一份 0 张表的空备份，而它在侧车里看起来完全合法"
        )
    if source.stat().st_size == 0:
        raise BackupError(
            f"要备份的库文件是 0 字节：{source}。⚠️ SQLite 把「零长度文件」当成一个空库，"
            "故备份它会产出一份合法但**空**的备份；那通常是上一次进程被杀在建表中途，"
            "请确认路径对不对（演示库用 backend/scripts/demo.ps1 重建）"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    # ⚠️⚠️ **刻意不先 ``unlink`` 目标**（本 Task 在 Windows 上实测撞出来的）：
    # 一个**空闲**（没有活动事务、因而 :func:`restore._assert_not_in_use` 探不到）
    # 却仍被某个进程开着的句柄，会让 ``os.unlink`` 在 Windows 上当场
    # ``PermissionError: [WinError 32] 另一个程序正在使用此文件``；
    # 而在 POSIX 上同一个 ``unlink`` **会成功**——于是那个进程继续写一个已经被删掉的
    # inode，磁盘上的新文件与它再无关系。**两种操作系统给出两种不同的坏法**，
    # 而两种都不是「恢复失败」这么响亮。
    # ⚠️ 不删也没问题：``sqlite3_backup_step`` 在开始时**重置**目标库
    # （destination 的全部内容被源覆盖，多余的尾部页在结束时被截掉），
    # 故「目标是这一次的产物」这一格由 API 保证、不必靠先删文件来保证。
    # ⚠️ 而「目标正被**写**」那一档由 :func:`restore._assert_not_in_use` 的
    # ``BEGIN IMMEDIATE`` 在**动手之前**拦下（一句人话，不是裸栈）。
    # ⚠️ ``uri=True`` + ``mode=ro``：源一律只读打开。于是「备份把库写坏了」
    #    这件事在结构上不可能发生，而一个正被 uvicorn 写着的库也不会因为
    #    多了一条读写连接而更容易撞锁。
    # ⚠️ ``as_uri()`` 要求**绝对**路径（相对路径当场 ``ValueError``），故先 ``resolve()``：
    #    ``sqlite:///relative.db`` 这一档下 :func:`app.db.session._db_file_of` 给回的是
    #    一个相对 ``Path``，而它由 CWD 决定指向哪个文件——``resolve()`` 把那一格
    #    在本函数里定死（⚠️ 与 :data:`app.config.DEFAULT_DB_URL` 刻意用绝对路径
    #    是同一条理由：Plan01 Ruling 190）。
    source_connection = sqlite3.connect(
        source.resolve().as_uri() + "?mode=ro", uri=True, timeout=5.0
    )
    try:
        destination_connection = sqlite3.connect(str(destination), timeout=5.0)
        try:
            source_connection.backup(destination_connection)
        finally:
            destination_connection.close()
    finally:
        source_connection.close()
    return destination.stat().st_size


def backup_name(moment: dt.datetime | None = None) -> str:
    """``pe-<UTC ts>.db``。``moment`` 可注入（同 :func:`app.pipeline.daily.run_daily`
    的 ``now`` 先例）：测试要能钉住文件名，而 ``datetime.now`` 让文件名随墙钟漂。

    ⚠️ **传进来的 ``moment`` 若带 tzinfo，先转到 UTC 再摘掉**：缺省路径给的就是
    ``datetime.now(timezone.utc)``，而一个调用方传本地 aware 时刻进来时，
    ``strftime`` 会照它自己的偏移渲染——于是同一个瞬间在两台不同时区的机器上
    得到两个文件名。⚠️ naive 时刻按「已经是 UTC」处理（本函数**不猜**时区）。
    """
    if moment is None:
        moment = dt.datetime.now(dt.timezone.utc)
    if moment.tzinfo is not None:
        moment = moment.astimezone(dt.timezone.utc)
    return "pe-%s.db" % moment.strftime(TIMESTAMP_FORMAT)


def create_backup(
    db_path: pathlib.Path,
    backups_dir: pathlib.Path = BACKUPS_DIR,
    *,
    moment: dt.datetime | None = None,
    label: str = "",
) -> pathlib.Path:
    """做一次完整备份：在线拷到 ``backups_dir/pe-<UTC ts><label>.db`` + 写侧车。

    **返回备份文件的路径**（侧车由 :func:`sidecar_of` 现算，故不必返回两个）。

    ⚠️ ``label`` 存在的全部理由是**同一秒内的第二次备份**：文件名只到秒，
    而 :func:`restore.restore_database` 在覆盖目标之前会先自动备份一次当前库
    （派单 §2 第 3 条）——那一次紧跟在运维手工做的那一次之后，两者会撞名。
    它传 ``label="-pre-restore"``，于是文件名同时**说明了自己是什么**
    （``pe-20261013T112233Z-pre-restore.db``），运维一眼能认出「这一份是恢复前
    自动留的后路」，而不是一份普通的定时备份。

    ⚠️ **撞名仍然可能**（同一个 ``label`` 在同一秒内跑两次），那时本函数
    **覆盖**旧的：备份是幂等的产物，而拒绝会让「cron 一秒内被触发两次」变成
    一次失败的备份——那比覆盖坏。⚠️ 如实记录（硬规矩 #39）。
    """
    if label and not label.startswith("-"):
        raise BackupError(f"label 必须以 '-' 开头（它是文件名的一部分）：{label!r}")
    # ⚠️⚠️ 排在 ``mkdir`` **之前**：那一道守卫挡的是「往知识资产目录里写一份整库副本」，
    #    而 ``mkdir(parents=True)`` 会先把目录建出来 —— 拒得晚一步就已经动过盘了。
    _ensure_backup_dir_allowed(backups_dir, must_exist=False)
    backups_dir.mkdir(parents=True, exist_ok=True)
    name = backup_name(moment)
    if label:
        name = name[: -len(".db")] + label + ".db"
    destination = backups_dir / name
    size = backup_database(db_path, destination)
    write_sidecar(destination)
    return destination


# ==========================================================================
# ⚠️⚠️ 保留策略（Plan 08 Task 3）：``--keep N``
# ==========================================================================

#: 「哪几份算旧」的**判据的唯一所有者**（模块 docstring「保留策略」那一节）。
#:
#: ⚠️ 它同时是 :func:`backup_name` / :func:`create_backup` 那一侧「文件名怎么拼」的
#: **对拍方**：``pe-<UTC ts>.db`` 与 ``pe-<UTC ts>-pre-restore.db`` 两个形状都要认，
#: 而**别的形状一律不认**（⇒ 不碰）。``tests/test_backup_restore.py`` 的
#: ``test_the_retention_criterion_is_the_filename_timestamp_and_not_the_mtime``
#: 把两侧对拍一次，故「写侧改了文件名形状而读侧没跟着改」会当场红。
BACKUP_NAME_RE = re.compile(
    r"^pe-(?P<timestamp>\d{8}T\d{6}Z)(?:-(?P<label>[A-Za-z0-9][A-Za-z0-9_-]*))?\.db$"
)

#: ``--keep`` 的下界。⚠️ **0 一律拒**，逐字理由见模块 docstring「保留策略」那一节。
MIN_KEEP = 1


@dataclasses.dataclass(frozen=True)
class BackupEntry:
    """``backups/`` 下**认得出时间戳**的一份备份。

    ⚠️ ``sort_key`` 是 ``(timestamp, 文件名)``：第一格就是「哪一份更新」的判据，
    第二格只为**同一秒**内的那几份（``backup_name`` 只到秒，而
    :func:`create_backup` 的 ``label`` 正是为那一档存在的）给一个**确定**的次序，
    于是「删哪几份」不依赖 :func:`pathlib.Path.glob` 的枚举顺序
    （它在 Windows 上按目录项顺序、不是按名字）。
    """

    path: pathlib.Path
    timestamp: str
    label: str

    @property
    def sort_key(self) -> tuple[str, str]:
        return (self.timestamp, self.path.name)


def list_backup_products(
    directory: pathlib.Path,
) -> tuple[list[BackupEntry], list[pathlib.Path]]:
    """一个目录 → ``(认得出时间戳的那些（**新→旧**）, 认不出的那些（**一律不碰**）)``。

    ⚠️ 它是 :data:`BACKUP_NAME_RE` 唯一的调用方，故「哪几份算旧」这件事
    在全仓**只有一个住址**。

    ⚠️⚠️ 第二个返回值的定义是**收紧过的**：「既不是候选、**也不是候选自己的侧车**」
    的那些。⚠️ 本 Task 的探针当场撞出来过那一格：第一版把 ``.sha256`` 侧车也放进了
    ``skipped``，而侧车**是要跟着自己那一份一起删的** ⇒ :func:`prune_backups` 的
    复核第三拍（「认不出的那些一个都没动」）当场红在它自己正确的行为上。
    于是``skipped`` 里剩下的是三类，各有一个不碰它的理由：

    * **不是 ``pe-<UTC ts>.db`` 形状的 ``.db``** —— 例如控制者手工做的
      ``pe_trial-pre-migration5-20261017-201257.db``；
    * **孤儿侧车** —— 一个 ``.sha256`` 而它那份 ``.db`` 不在这个目录里
      （⚠️ 它**不**被本策略顺手删掉：删一个别人可能正在核的侧车不是本件的授权范围，
      而 :func:`prune_backups` 会把它单独点出来，因为那一格运维该知道 ——
      它会让下一次恢复报「备份文件不存在」，而他看着那个侧车会以为备份还在）；
    * **子目录与任何别的东西**。

    ⚠️ 只枚举**一层**（``iterdir`` 而不是 ``rglob``）：``-Keep`` 会删文件，
    而一个递归的删除面在运维把 ``--dir`` 指错时会大得多。
    """
    entries: list[BackupEntry] = []
    others: list[pathlib.Path] = []
    for path in sorted(directory.iterdir(), key=lambda p: p.name):
        match = BACKUP_NAME_RE.match(path.name) if path.is_file() else None
        if match is None:
            others.append(path)
            continue
        entries.append(
            BackupEntry(
                path=path,
                timestamp=match.group("timestamp"),
                label=match.group("label") or "",
            )
        )
    entries.sort(key=lambda e: e.sort_key, reverse=True)
    owned = {e.path.name + SIDECAR_SUFFIX for e in entries}
    return entries, [p for p in others if p.name not in owned]


def _ensure_backup_dir_allowed(directory: pathlib.Path, *, must_exist: bool = True) -> None:
    """**备份目录**的禁区守卫：``--dir`` 指到哪儿是有后果的（写进去 / 从里面删）。

    ⚠️ 与 :func:`_ensure_not_forbidden`（它守的是**库**那一侧）是一对、
    而**不是**同一个函数：那一个挡「备份/恢复哪一个库」，本函数挡
    「往哪个目录里写备份、在哪个目录里删备份」。三档：

    1. ``backend/data/**`` —— 专家维护的知识资产，**一个字节都不许动**。
       ⚠️ 而这一档比「改坏一个 YAML」更坏：``backend/data/`` 是**入库**的，
       于是一份写进去的整库副本（全校学生的健康档案）会被下一次 ``git add -A``
       提交进版本控制，而 git 历史删不掉；
    2. ``backend/`` 本身与仓库根 —— ``--dir`` 要的是一个**只放备份**的目录，
       而这两层里住着源码。⚠️ 对**删除**那一侧，:data:`BACKUP_NAME_RE` 已经挡住了
       （那里没有 ``pe-<UTC ts>.db``），本函数是**第二重**（与
       :func:`_ensure_not_forbidden` 对 ``pe.db`` 的两重同款）；
    3. 目录不存在 —— ⚠️ 而这一档**可以被显式关掉**（``must_exist=False``）：
       :func:`main` 在**做任何一次写之前**就要判前两档，而那时目录还不存在
       （:func:`create_backup` 会建它），故它传 ``must_exist=False``；
       :func:`prune_backups` 走的是缺省的 ``True``（它排在备份之后，那时目录一定在，
       走到「不在」就是路径写错了）。
    """
    resolved = directory.resolve()
    data_dir = (BACKEND_DIR / "data").resolve()
    if resolved == data_dir or data_dir in resolved.parents:
        raise BackupError(
            f"拒绝把 {resolved} 当备份目录：backend/data/** 是专家维护的知识资产，"
            "一个字节都不许动，⚠️ 而它是**入库**的 —— 一份写进去的整库副本"
            "（全校学生的健康档案）会被下一次 git add 提交进版本控制，"
            "而 git 历史删不掉（--dir 要的是一个**只放备份**的目录）"
        )
    for name, forbidden in (("backend/", BACKEND_DIR.resolve()),
                            ("仓库根", BACKEND_DIR.parent.resolve())):
        if resolved == forbidden:
            raise BackupError(
                f"拒绝把 {resolved}（{name}）当备份目录：--dir 要的是一个**只放备份**"
                "的目录（缺省是 backend/backups/），而这一层里住着源码"
            )
    if must_exist and not directory.is_dir():
        raise BackupError(f"备份目录不存在，故保留策略无从谈起：{directory}")


def prune_backups(
    directory: pathlib.Path,
    keep: int,
    *,
    emit: Callable[[str], None] = print,
) -> dict[str, object]:
    """按 ``-Keep`` 删旧备份（**连侧车一起**）；返回一份可对账的 dict。

    ⚠️⚠️ 删备份是**不可逆**的，故形状与 :func:`retention.clean` 逐字同一条口径：
    **先逐个打印要删哪几份（含字节数与 sha256 的前 16 位）→ 再删 → 删完复核**。
    复核三拍，任一拍不符就 :class:`BackupError`（⚠️ 而那时已经删掉的部分
    **回不来**，故这一格的意义是「响亮」而不是「回滚」——它挡的是
    「删了却报成功」，那是更坏的一档）：

    ① 那 ``keep`` 份**新的**一份都没少；
    ② 预告要删的那些文件名与它们的侧车**都不在了**；
    ③ 认不出的那些文件**一个都没动**（``-Keep`` 对它们是隐形的）。

    ⚠️ ``keep`` 的下界由 :data:`MIN_KEEP` 给（``0`` 一律拒），而**调用方也要自己判一次**：
    :func:`main` 在**做任何一次写之前**就判，于是 ``--keep 0`` 那一档连备份都不做。
    本函数再判一次是第二重（它也可能被别的调用方直接调）。
    """
    if keep < MIN_KEEP:
        raise BackupError(
            f"--keep 要 ≥ {MIN_KEEP}（收到 {keep}）：它的字面意思是「一份都不留」——"
            "连这一次刚做出来的那一份也一起删掉，而那几乎肯定不是运维想要的"
            "（最常见的一档是一个没设上的变量落成了 0）。⚠️ 要「清空备份目录」"
            "请自己删那个目录里的文件：那是一次**显式**的动作，本 CLI 不替你做"
        )
    _ensure_backup_dir_allowed(directory)
    entries, skipped = list_backup_products(directory)

    emit("   保留策略  --keep %d（判据 = **文件名里的 UTC 时间戳**，新→旧；"
         "所有者 backup.BACKUP_NAME_RE）" % keep)
    emit("   目录      %s" % directory)
    emit("   现存      %d 份认得出时间戳的备份 + %d 个认不出的东西（**一律不碰**）"
         % (len(entries), len(skipped)))
    known = {e.path.name for e in entries}
    for path in skipped:
        if path.name.endswith(SIDECAR_SUFFIX) and path.name[: -len(SIDECAR_SUFFIX)] not in known:
            emit("      · 跳过 %s（⚠️ 一个**孤儿侧车**：它那份 .db 不在这个目录里。"
                 "本策略**不碰**它，而它会让下一次恢复报「备份文件不存在」——"
                 "请自己确认那一份备份去哪了，再决定删不删这个侧车）" % path.name)
        else:
            emit("      · 跳过 %s%s（不是 pe-<UTC ts>.db 那个形状 ⇒ 本策略对它隐形）"
                 % (path.name, "/" if path.is_dir() else ""))

    doomed = entries[keep:]
    result: dict[str, object] = {
        "keep": keep, "directory": directory, "found": len(entries),
        "skipped": [p.name for p in skipped],
        "deleted": [], "deleted_sidecars": 0, "remaining": len(entries) - len(doomed),
    }
    if not doomed:
        emit("   ⇒ 现存 %d 份 ≤ --keep %d：**一份都不删**（侧车也一个都不动）"
             % (len(entries), keep))
        return result

    emit("")
    emit("   ⚠️⚠️ 下面这一步**不可逆**：将删 %d 份（连它们各自的 .sha256 侧车一起）："
         % len(doomed))
    total_bytes = 0
    for entry in doomed:
        size = entry.path.stat().st_size
        total_bytes += size
        sidecar = sidecar_of(entry.path)
        emit("      · %-42s %10d B  sha256 %s…  侧车 %s%s"
             % (entry.path.name, size, sha256_of(entry.path)[:16],
                "✓" if sidecar.is_file() else "**不在**",
                "" if not entry.label else "（label=%s）" % entry.label))
    emit("   合计：将删 %d 份 / %d B → 开始删…" % (len(doomed), total_bytes))

    deleted: list[str] = []
    sidecars = 0
    for entry in doomed:
        sidecar = sidecar_of(entry.path)
        entry.path.unlink()
        if sidecar.is_file():
            sidecar.unlink()
            sidecars += 1
        deleted.append(entry.path.name)

    # ⚠️⚠️ 删完复核（三拍，逐字见 docstring）
    after, skipped_after = list_backup_products(directory)
    after_names = {e.path.name for e in after}
    kept_names = {e.path.name for e in entries[:keep]}
    if not kept_names <= after_names:
        raise BackupError(
            f"复核失败：--keep 要留的那几份里有 {sorted(kept_names - after_names)} 不在了"
            "⇒ 判据与删除面不一致，请**立刻**停止使用 --keep 并手工核对那个目录"
        )
    still_there = [name for name in deleted if name in after_names]
    if still_there:
        raise BackupError(f"复核失败：预告要删的 {still_there} 仍在目录里")
    for name in deleted:
        orphan = directory / (name + SIDECAR_SUFFIX)
        if orphan.exists():
            raise BackupError(
                f"复核失败：{name} 删了、而它的侧车 {orphan.name} 还留着 —— "
                "一个指不到东西的侧车会让下一次恢复报「备份文件不存在」，"
                "而运维看着它会以为备份还在"
            )
    if len(after) != min(keep, len(entries)):
        raise BackupError(
            f"复核失败：目录里认得出时间戳的备份剩 {len(after)} 份，"
            f"而应当是 min(--keep {keep}, 现存 {len(entries)}) = {min(keep, len(entries))} 份"
        )
    if sorted(p.name for p in skipped_after) != sorted(p.name for p in skipped):
        raise BackupError(
            "复核失败：「既不是候选、也不是候选侧车」的那些东西被动过了 —— "
            f"{sorted(p.name for p in skipped)} → {sorted(p.name for p in skipped_after)}。"
            "⚠️ 本策略的授权范围只有「候选 + 它们自己的侧车」，多删一个都是 bug"
        )

    result["deleted"] = deleted
    result["deleted_sidecars"] = sidecars
    emit("   实删 %d 份 + %d 个侧车（%d B）。复核：目录里认得出时间戳的备份剩 %d 份"
         "（== min(--keep %d, 现存 %d) ✓）、那 %d 个文件名与它们的侧车都已不在、"
         "认不出的那 %d 个东西一个都没动。"
         % (len(deleted), sidecars, total_bytes, len(after), keep, len(entries),
            len(deleted), len(skipped)))
    return result


def main(argv: list[str] | None = None) -> int:
    """``python scripts/backup.py [--db-url URL] [--dir DIR] [--keep N]``；**退出码 0 = 成功**。

    ⚠️ 它打印三行**实测**出来的事实（备份路径、字节数、sha256 的前 16 位），
    而不是一句「备份完成」：运维要能把屏幕上的那一串与侧车文件对一眼。
    """
    parser = argparse.ArgumentParser(
        description=(
            "在线备份本系统的 SQLite 库（sqlite3 的 backup() API，不是复制文件），"
            "并写一份同名的 .sha256 侧车。"
        )
    )
    parser.add_argument(
        "--db-url", default=None,
        help=(
            f"要备份的库 URL（sqlite:///…）。缺省读 ${_env_var()}，"
            "再缺省是 app.main.DEMO_DB_URL（= backend/pe_demo.db，与 demo.ps1 一致）。"
            "⚠️ 刻意不回落到 app.config.DEFAULT_DB_URL：那是禁区 backend/pe.db"
        ),
    )
    parser.add_argument(
        "--dir", default=None,
        help=f"备份落在哪个目录。缺省 {BACKUPS_DIR}（已进 .gitignore）",
    )
    parser.add_argument(
        "--keep", type=int, default=None,
        help=(
            f"只留最近 N 份（按**文件名里的 UTC 时间戳**判新旧），其余的连 .sha256 侧车"
            f"一起删。⚠️ 缺省**一份都不删**；⚠️ N 要 ≥ {MIN_KEEP}（0 = 「一份都不留」，"
            "一律拒 + 退出码 2，而那一档连这一次备份都不做）；⚠️ 删之前会逐个打印"
            "要删哪几份与它们的字节数/sha256，删完再复核一遍"
        ),
    )
    args = parser.parse_args(argv)

    # ⚠️⚠️ ``--keep`` 的**下界在任何一次写之前就判**：``--keep 0`` 那一档
    #    连这一次备份都不做（失效方向是「什么都没发生 + 退出码 2」，
    #    与 retention.py 对「窗口 0 天」逐字同一条口径）。
    if args.keep is not None and args.keep < MIN_KEEP:
        raise BackupError(
            f"--keep 要 ≥ {MIN_KEEP}（收到 {args.keep}）：它的字面意思是「一份都不留」——"
            "连这一次刚做出来的那一份也一起删掉，而那几乎肯定不是运维想要的"
            "（最常见的一档是一个没设上的变量落成了 0）。⚠️ 故本 CLI 在**做任何一次写"
            "之前**就拒绝：这一次备份也没有做。要「清空备份目录」请自己删那个目录里的"
            "文件——那是一次**显式**的动作，本 CLI 不替你做"
        )

    db_path = resolve_db_path(args.db_url)
    backups_dir = pathlib.Path(args.dir) if args.dir else BACKUPS_DIR
    # ⚠️⚠️ 同样排在**任何一次写之前**（``must_exist=False``：目录此刻还不存在是正常的，
    #    create_backup 会建它）。本 Task 的探针当场撞出来过这一格：改前
    #    ``--dir backend/data --keep 1`` 会**先写一份整库副本进 backend/data/**、
    #    然后才被 prune 的守卫拒掉 —— 拒掉的是删除，写已经发生了。
    _ensure_backup_dir_allowed(backups_dir, must_exist=False)
    if not db_path.is_file():
        raise BackupError(
            f"{db_path} 不存在：还没有库可备份。演示库请用 backend/scripts/demo.ps1 建一份"
        )
    destination = create_backup(db_path, backups_dir)
    sidecar = read_sidecar(sidecar_of(destination))
    print("== 厦大体育数智系统 · 备份 ==")
    print("   源库   %s" % db_path)
    print("   备份   %s" % destination)
    print("   侧车   %s" % sidecar_of(destination))
    print("   字节   %d" % sidecar["bytes"])
    print("   sha256 %s…" % str(sidecar["sha256"])[:16])
    print("")
    print("   ⚠️ 恢复：python scripts/restore.py %s" % destination.name)
    print("      （恢复会先校验侧车、再自动备份当前库、然后覆盖；请先停服务）")
    if args.keep is not None:
        print("")
        prune_backups(backups_dir, args.keep)
    return 0


if __name__ == "__main__":
    BACKEND = pathlib.Path(__file__).resolve().parents[1]
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    try:
        sys.exit(main())
    except BackupError as exc:
        print("备份失败：%s" % exc, file=sys.stderr)
        sys.exit(2)

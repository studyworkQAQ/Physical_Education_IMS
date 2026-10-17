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
⚠️⚠️ 可选加密（Plan 08 Task 3）：``PE_BACKUP_KEY`` 在就加密、不在就**响亮地**不加密
--------------------------------------------------------------------------

**为什么这一格比在线库更危险**：备份文件的常态是被拷进 U 盘 / 网盘 / 邮件附件，
而一个 U 盘**没有**权限、也**没有**防火墙。Plan 07 Task 9 实测过改前的产物：
文件头 ``SQLite format 3\0``、**不用任何密钥**就读出 60 人姓名与出生日期、
240 行体成分、47 行审计。

**产物形状**（⚠️ 自描述；:func:`build_container_header` 与
:func:`parse_container_header` 是它唯一的写方与读方）::

    偏移   宽    是什么
    0      8     魔数 ``PEBACKUP``（⚠️ 与 ``SQLite format 3\0`` 不可能撞）
    8      1     容器版本（今天恒 1）
    9      1     分组密码 id（1 = AES-256-CBC + PKCS7）
    10     1     KDF id（1 = PBKDF2-HMAC-SHA256）
    11     1     保留（恒 0）
    12     4     KDF 迭代次数（uint32，**大端**）
    16     2     盐的字节数（uint16，大端；今天恒 16）
    18     2     IV 的字节数（uint16，大端；今天恒 16）
    20     8     **明文**的字节数（uint64，大端）
    28     16    盐（⚠️ 每份备份**自己的**随机盐）
    44     16    IV（⚠️ 每份备份**自己的**随机 IV）
    60     N     密文
    60+N   32    HMAC-SHA256（**encrypt-then-MAC**：算的是上面 0..60+N 那一段）

⇒ 头 **60** 字节（:data:`CONTAINER_HEADER_BYTES`）、尾 **32** 字节
（:data:`CONTAINER_MAC_BYTES`），中间是密文。⚠️ **文件名与侧车都不变**
（仍然是 ``pe-<UTC ts>.db`` + ``.db.sha256``）：「这一份是明文还是密文」
由**产物头**回答，⚠️ **不由扩展名回答** —— 改前那些明文备份已经在甲方手上了，
:mod:`restore` 两种都要能吃（:func:`product_kind` 是那一个判断的唯一所有者）。

**四格裁定**（派单 §2 第 3 条逐字点名的四个开放问题）：

* ⚠️ **AES-GCM 在本机不可用**（实测：PowerShell **5.1.26100.9711** /
  CLR **4.0.30319.42000** = .NET Framework 4.x，``[System.Security.Cryptography.AesGcm]``
  报 ``Unable to find type``、``New-Object`` 同样失败）⇒ **AES-256-CBC + 独立的
  HMAC-SHA256**，而且是 **encrypt-then-MAC**：:func:`verify_container` **先验 MAC**、
  验不过**一步都不解密**（派单逐字要求）。⚠️ 那一格是**承重**的，不是洁癖：
  本 Task 实测过「把密文中间一个字节翻掉再解密」——AES-CBC 只坏那两个块、
  padding 常常仍然合法，``aes_cbc.ps1`` **退出码 0**、静默产出一个坏库。
* ⚠️ **密钥不是那个环境变量的字节**：``PE_BACKUP_KEY`` 是一个**口令**，
  32 字节的 AES 密钥由 :func:`hashlib.pbkdf2_hmac` 从「口令 + 这一份自己的随机盐」
  派生（一次派生 **64** 字节：前 32 给 AES、后 32 给 HMAC ⇒ 两把钥匙**不同源**）。
  直接把环境变量当密钥是弱的（长度不定、熵低，而且同一把钥匙既加密又做 MAC）。
* ⚠️ **迭代次数的口径所有者是 :mod:`app.auth.passwords`**
  （``PBKDF2_DEFAULT_ITERATIONS`` 与那一族上下界），本模块**一个数都不自己写**。
  ⚠️ 而它刻意**不读** ``PBKDF2_ITERATIONS`` 那个环境变量：那一个是给**测试套件**
  降工作量的（根 conftest 设成 100 000），而备份的 KDF 每份**只跑一次**、
  没有理由跟着降（一次 ~0.3 s）。要覆盖请给 ``PE_BACKUP_KDF_ITER``，
  ⚠️ 同样受那一族上下界管，且**写进产物头** ⇒ 恢复时按头上那一个跑，
  而头上那一个也要过同一道界 ⇒ 一份声称「迭代 1 次」的产物**当场被拒**。
* ⚠️ **侧车算的是产物文件本身**（= 头 + 密文 + MAC），不是明文。理由：侧车答的
  问题是「拷来拷去有没有坏」，不是「里面是什么」。⚠️ 于是 :func:`write_sidecar`
  与 :func:`read_sidecar` **一个字都没改**，:func:`restore.verify_backup` 那一格
  也**一个字都没改** —— 加密对它们是完全透明的。

⚠️⚠️ **缺 ``PE_BACKUP_KEY`` 时不加密、而是打印一段响亮的 ⚠️**（派单逐字裁定：
**不是** raise —— 改前的缺省行为就是不加密，raise 会把既有用户打死）。
那一段告示由 ``tests/test_backup_restore.py`` 的
``test_a_missing_key_still_produces_a_usable_plaintext_backup_and_says_so_loudly`` 钉住。

⚠️ **AES 那一格住在 ``scripts/aes_cbc.ps1``**：Python 的标准库**没有** AES
（``hashlib`` 有 PBKDF2 与摘要、``hmac`` 有 MAC，而分组密码一个都没有），
而本波**新增依赖 = 0** ⇒ 那一次变换只能叫 .NET 的 BCL。⚠️ 而它是**唯一**住在那里的东西：
产物形状、KDF、MAC、侧车、保留策略一律仍在本模块（那个 ``.ps1`` 只做
「一块字节进、一块字节出」，**一个格式字节都不认识**）。
⚠️ 密钥与 IV 走 **stdin** 的两行 base64，**不走 argv**：Windows 上任何同机进程都能用
``Get-CimInstance Win32_Process`` 读到别人完整的命令行。
⚠️ 而 :mod:`restore` 因此**也**依赖 ``powershell.exe``（只有吃加密档时）；
一台没有 PowerShell 的机器上，明文档的备份与恢复**照旧**（那一格是本仓的目标平台
= Windows 之外的唯一一处妥协，如实记）。

⚠️ **明文那一份从来不落进备份目录**：加密档走「``sqlite3.backup()`` → **系统临时目录**里
的一份明文 → 加密进 ``backups/`` → ``finally`` 里删掉临时那一份」。⚠️ 如实记（硬规矩 #39）：
一次崩溃最多在 ``%TEMP%`` 里留一份明文，而**不会**在运维拷来拷去的那个目录里留。

⚠️⚠️ **口令丢了这一份就打不开**：本仓**刻意不做**密钥托管、也不做「口令错了给个提示」
（HMAC 验不过就是验不过，而「验不过」的两种原因——口令不对 / 产物被改过——
在密码学上**不可分辨**，故报错把两档一起说）。⚠️ 而它**没有**第二个后门：
``restore --no-verify`` 跳的是**侧车**那一格，**HMAC 那一格跳不掉**。已登记 §15。

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
* ~~**不加密**~~ → ⚠️⚠️ **Plan 08 Task 3（2026-10-17）做掉了**：设一个
  ``PE_BACKUP_KEY`` 就产出加密档（AES-256-CBC + HMAC-SHA256，产物形状自描述），
  逐字口径见上面「可选加密」那一节。⚠️ 而它**缺省仍然不加密**（那个环境变量不在时
  打印一段响亮的 ⚠️、而不是 raise —— 改前的缺省行为就是不加密，raise 会把既有用户打死）。
  ⚠️ ``age`` / ``gpg`` 那条路**仍然没走**：两者都要一个新依赖，而本波新增依赖 = 0。
* **不碰 ``backend/data/**``**：本模块只读一个库文件、只往 ``backend/backups/`` 写。
  那两个禁区（``backend/pe.db`` 不得存在、``backend/data/seed/`` 恒为 0 文件）
  由 :func:`_ensure_not_forbidden` 与 ``tests/test_backup_restore.py`` 双向钉住。
"""
from __future__ import annotations

import argparse
import base64
import dataclasses
import datetime as dt
import hashlib
import hmac
import os
import pathlib
import re
import secrets
import sqlite3
import struct
import subprocess
import sys
import tempfile
from typing import Callable

from app.auth.passwords import (
    MIN_PASSWORD_LENGTH,
    PBKDF2_DEFAULT_ITERATIONS,
    PBKDF2_MAX_VERIFY_ITERATIONS,
    PBKDF2_MIN_VERIFY_ITERATIONS,
)
from app.config import BACKEND_DIR
from app.db.session import _db_file_of

#: ⚠️ ``app.main`` **刻意不在模块顶层 import**（与 ``backend/migrations/env.py`` 同一条
#: 口径，逐字理由也相同）：``app.main`` 有一条模块级的 ``app = create_app()``，
#: 放进顶层会让「import 一个备份脚本」顺带装配一次 FastAPI 应用
#: （造引擎、装中间件、注册路由）。本模块只需要它那两个**常量**，
#: 故在 :func:`resolve_db_path` 的函数体里取。

__all__ = [
    "BACKUPS_DIR",
    "BACKUP_KEY_ENV_VAR",
    "BACKUP_KDF_ITER_ENV_VAR",
    "CONTAINER_HEADER_BYTES",
    "CONTAINER_MAC_BYTES",
    "CONTAINER_MAGIC",
    "KIND_ENCRYPTED",
    "KIND_PLAINTEXT",
    "KIND_UNKNOWN",
    "MIN_KEEP",
    "SIDECAR_SUFFIX",
    "SQLITE_MAGIC",
    "BackupEntry",
    "backup_database",
    "create_backup",
    "db_path_from_url",
    "decrypt_container",
    "derive_keys",
    "describe_container",
    "encrypt_file",
    "list_backup_products",
    "product_kind",
    "prune_backups",
    "read_sidecar",
    "resolve_backup_passphrase",
    "resolve_db_path",
    "resolve_kdf_iterations",
    "sha256_of",
    "sidecar_of",
    "verify_container",
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
    passphrase: str | None = None,
) -> pathlib.Path:
    """做一次完整备份：在线拷到 ``backups_dir/pe-<UTC ts><label>.db`` + 写侧车。

    ⚠️⚠️ ``passphrase=None``（缺省）时本函数的行为与 Plan 08 Task 3 之前
    **逐字相同**：产物就是一份明文 SQLite + 一个侧车。给了口令就多一步封装
    （逐字口径见模块 docstring「可选加密」那一节），而**文件名与侧车都不变**
    ——「这一份是明文还是密文」由产物头回答（:func:`product_kind`）。

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
    if passphrase is None:
        backup_database(db_path, destination)
        # ⚠️ 侧车一律算**产物文件本身**（明文档就是那份库、加密档就是头+密文+MAC）
        write_sidecar(destination)
        return destination
    # ⚠️⚠️ 加密档：明文那一份**从来不落进备份目录**（它落在系统临时目录里、
    #    并在 finally 里删掉）。逐字理由见模块 docstring「可选加密」那一节。
    handle, temp_name = tempfile.mkstemp(prefix="pe-plain-", suffix=".db")
    os.close(handle)
    plain = pathlib.Path(temp_name)
    try:
        backup_database(db_path, plain)
        encrypt_file(plain, destination, passphrase)
    finally:
        plain.unlink(missing_ok=True)
    write_sidecar(destination)
    return destination


# ==========================================================================
# ⚠️⚠️ 可选加密（Plan 08 Task 3）：产物形状的唯一所有者在本模块
# ==========================================================================

#: 口令从哪个环境变量读。⚠️ **它不是密钥本身**，而是 PBKDF2 的输入
#: （逐字理由见模块 docstring「可选加密」那一节的四格裁定）。
BACKUP_KEY_ENV_VAR = "PE_BACKUP_KEY"

#: KDF 迭代次数的覆盖口。⚠️ 刻意**不是** :data:`app.auth.passwords.PBKDF2_ITERATIONS_ENV_VAR`：
#: 那一个是给测试套件降工作量的，而备份的 KDF 每份只跑一次（~0.3 s），没有理由跟着降。
BACKUP_KDF_ITER_ENV_VAR = "PE_BACKUP_KDF_ITER"

#: 产物头的魔数。⚠️ 8 字节、可读、且与 ``SQLite format 3\0`` **不可能**撞
#: （第一个字节就不同）。:func:`product_kind` 靠它分辨明文档与加密档。
CONTAINER_MAGIC = b"PEBACKUP"

#: 容器版本。⚠️ 改它就是「读不懂全部既有产物」，故将来加算式是**加一个新 id**、
#: 不是改这一个数（与 :data:`app.auth.passwords.ALGORITHM` 同一条口径）。
CONTAINER_VERSION = 1

#: 分组密码 id：1 = AES-256-CBC + PKCS7（``scripts/aes_cbc.ps1`` 唯一支持的那一档）。
CIPHER_ID_AES_256_CBC = 1

#: KDF id：1 = PBKDF2-HMAC-SHA256。
KDF_ID_PBKDF2_HMAC_SHA256 = 1

#: 头里那个保留字节。⚠️ 读侧要求它**恒为 0**：一个非 0 的保留字节意味着
#: 「写侧与读侧对同一份布局的理解不一致」，而那一格必须响、不能猜。
CONTAINER_RESERVED = 0

#: 盐与 IV 的字节数。⚠️ 与 :data:`app.auth.passwords.SALT_BYTES` 同一个数、
#: 同一条来历（NIST SP 800-132 对随机盐的下界是 128 bit）。
CONTAINER_SALT_BYTES = 16
CONTAINER_IV_BYTES = 16

#: HMAC-SHA256 的宽度，也是产物尾部那一段的宽度。
CONTAINER_MAC_BYTES = 32

#: 一次 PBKDF2 派生 **64** 字节：前 32 给 AES、后 32 给 HMAC。
#: ⚠️ **两把钥匙不同源**（不是「同一把钥匙既加密又做 MAC」）—— 后者是一个
#: 已被反复研究过的坏姿势，而前者的代价只是把 ``dklen`` 从 32 改成 64。
CONTAINER_AES_KEY_BYTES = 32
CONTAINER_MAC_KEY_BYTES = 32
CONTAINER_DERIVED_BYTES = CONTAINER_AES_KEY_BYTES + CONTAINER_MAC_KEY_BYTES

#: 头的宽度（**固定**）：前 28 字节是定长字段，后面接盐与 IV。
#: ⚠️ 头里那两格 ``salt_len`` / ``iv_len`` 因此是**冗余**的 —— 而冗余是有意的：
#: 它们是「写侧与读侧对同一份布局的理解」的对账，一个被改坏的产物在这两格上就响。
CONTAINER_HEADER_BYTES = 28 + CONTAINER_SALT_BYTES + CONTAINER_IV_BYTES

#: 明文档的文件头。⚠️ 它是 SQLite 自己的格式串，本模块只**读**它来做判断、
#: 从不写它（写它的是 ``sqlite3`` 的 ``backup()``）。
SQLITE_MAGIC = b"SQLite format 3\x00"

#: :func:`product_kind` 的三个答案。⚠️ 具名常量而不是裸串：
#: :mod:`restore` 也按它们分支，两侧写串会漂。
KIND_ENCRYPTED = "encrypted"
KIND_PLAINTEXT = "plaintext"
KIND_UNKNOWN = "unknown"

#: AES 那一个原语住在哪里。⚠️ 逐字理由见模块 docstring「可选加密」那一节
#: （Python 标准库没有 AES，而本波新增依赖 = 0）。
AES_HELPER_PS1 = pathlib.Path(__file__).resolve().parent / "aes_cbc.ps1"

#: 那一次子进程调用的上界（秒）。⚠️ 给得很宽：实测 1.6 MB ≈ 0.34 s（含 PowerShell
#: 的启动），而 AES-CBC 在 .NET Framework 上约 25 MB/s ⇒ 一个 4 GB 的库约 160 s。
#: 一个 GB 量级的库不该被一个 30 s 的上界打死，而一个真的挂住的进程也不该永远等。
AES_HELPER_TIMEOUT_SECONDS = 1800.0

#: 分块读写的一块（与 :func:`sha256_of` 逐字同宽：1 MiB）。
CHUNK_BYTES = 1024 * 1024


def resolve_backup_passphrase(explicit: str | None = None) -> str | None:
    """``PE_BACKUP_KEY`` → 口令；**没设（或设成空串）就返回 ``None``**。

    ⚠️ **刻意不 ``strip()``**：一个口令里的空格是口令的一部分，
    悄悄去掉它会造出一档最难查的失效——「运维明明设了同一个口令，
    而带尾随空格的那一次加密出来的产物，另一次解不开」。
    ⚠️ 而**空串按「没设」处理**是另一回事，那是本仓对**所有**环境变量的既有口径
    （:func:`resolve_db_path` 与 :func:`app.auth.passwords.iterations` 逐字相同）：
    ``$env:PE_BACKUP_KEY = ""`` 在 PowerShell 里是「设了一个空值」。

    ⚠️⚠️ **太短就拒**，而那句报错**刻意不说它收到了几个字符**、也不说它的 sha / base64 /
    任何一部分（派单 §2 第 3 条逐字要求）。下界复用
    :data:`app.auth.passwords.MIN_PASSWORD_LENGTH` —— 「一个人记得住的秘密至少多长」
    这件事在本仓只有一个所有者。
    """
    raw = os.environ.get(BACKUP_KEY_ENV_VAR, "") if explicit is None else explicit
    if not raw:
        return None
    if len(raw) < MIN_PASSWORD_LENGTH:
        raise BackupError(
            f"${BACKUP_KEY_ENV_VAR} 太短：它至少要有 {MIN_PASSWORD_LENGTH} 个字符"
            f"（那个数的唯一所有者是 app.auth.passwords.MIN_PASSWORD_LENGTH）。"
            "⚠️ 本句刻意**不说**它收到了几个字符、也不印它的任何一部分。"
            "⚠️ 一个短口令会让「一份被拷走的加密备份」在离线爆破面前只剩几小时；"
            "要么给一个够长的口令，要么**不设**它（那一档会产出一份明文档并响亮地告诉你）"
        )
    return raw


def _check_kdf_iterations(value: int) -> int:
    """迭代次数的**界**（写侧与读侧共用同一个函数 ⇒ 只有一个所有者）。

    ⚠️ 读侧也要过这一道：产物头里那个数是**攻击者可控**的（他可以造一份声称
    「迭代 1 次」的产物），而恢复时若照它跑，就等于让他把我们的工作量降到 1。
    ⚠️ 于是「把头里那个数写进产物、恢复时照它跑」与「不让头里的数把我们降级」
    两件事同时成立 —— 界是那一对的接缝。
    """
    if value < 1:
        raise BackupError(
            f"KDF 的迭代次数必须 ≥ 1（收到 {value}）：0 会让 hashlib 抛 ValueError，"
            "而负数没有意义"
        )
    if not PBKDF2_MIN_VERIFY_ITERATIONS <= value <= PBKDF2_MAX_VERIFY_ITERATIONS:
        raise BackupError(
            f"KDF 的迭代次数必须在 [{PBKDF2_MIN_VERIFY_ITERATIONS}, "
            f"{PBKDF2_MAX_VERIFY_ITERATIONS}] 之内（收到 {value}）：那一族数的唯一所有者是 "
            "app.auth.passwords（Plan 06 Task 11 收过「口令迭代上下界」那一格，"
            "本模块**复用**它、不写第二个数）。⚠️ 下界挡的是「为了快把口令散列 weakening」"
            "——一份离线可爆破的加密备份比一份明文档好不了多少，而它**看起来**安全得多"
        )
    return value


def resolve_kdf_iterations(explicit: int | None = None) -> int:
    """这一次要用的迭代次数：实参 > ``PE_BACKUP_KDF_ITER`` >
    :data:`app.auth.passwords.PBKDF2_DEFAULT_ITERATIONS`。

    ⚠️ 缺省值是那个**字面量**（600 000）而**不是** ``passwords.iterations()``
    的返回值 —— 后者读 ``PBKDF2_ITERATIONS``，而那一个环境变量是**测试套件**
    为了不把 2 分钟拖成半小时才设的（根 conftest 里设成 100 000）。
    ⚠️ 备份的 KDF 每份**只跑一次**（本机实测 600 000 次约 0.3 s），
    故它没有任何理由跟着测试套件一起降 —— 而「跟着降」的失效方向是**静默**的
    （一份用 1 000 次迭代派生的加密备份看起来与用 600 000 次的完全一样）。
    """
    if explicit is not None:
        return _check_kdf_iterations(explicit)
    raw = os.environ.get(BACKUP_KDF_ITER_ENV_VAR, "").strip()
    if not raw:
        return _check_kdf_iterations(PBKDF2_DEFAULT_ITERATIONS)
    try:
        value = int(raw)
    except ValueError as exc:
        raise BackupError(
            f"${BACKUP_KDF_ITER_ENV_VAR} 必须是一个整数，收到 {raw!r}"
        ) from exc
    return _check_kdf_iterations(value)


def derive_keys(passphrase: str, salt: bytes, iterations: int) -> tuple[bytes, bytes]:
    """口令 + 盐 → ``(AES 的 32 字节, HMAC 的 32 字节)``。

    ⚠️ **一次** PBKDF2 派生 64 字节再对半切，而不是派生两次：两次的代价是
    2 × 0.3 s，而「两把钥匙不同源」这个性质一次就够了（PBKDF2 的输出在
    ``dklen`` 超过一个摘要宽度时本来就是分段算的，前后两段互不推出）。
    ⚠️ 口径与 :func:`app.auth.passwords.hash_password` 逐字同款
    （``pbkdf2_hmac`` + ``sha256``），故「同一个口令在两侧派生出同一个东西」
    是本仓已经验过的一格，不是本模块新赌的一次。
    """
    material = hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt,
        _check_kdf_iterations(iterations), CONTAINER_DERIVED_BYTES,
    )
    return material[:CONTAINER_AES_KEY_BYTES], material[CONTAINER_AES_KEY_BYTES:]


def build_container_header(
    iterations: int, salt: bytes, iv: bytes, plaintext_len: int
) -> bytes:
    """拼那 60 个字节的产物头（布局逐字见模块 docstring「可选加密」那一节）。

    ⚠️ 整数一律**大端**（``>``）：产物是会被拷到别的机器上的，
    而小端会让「同一份产物在两台机器上读出两个迭代次数」变成可能。
    ⚠️ 它**校验**盐与 IV 的宽度而不是「写进去多少算多少」：一个 15 字节的 IV
    会让读侧把头后面的第一个字节当成密文，而那一档在解密时**未必**会响。
    """
    if len(salt) != CONTAINER_SALT_BYTES:
        raise BackupError(
            f"盐必须是 {CONTAINER_SALT_BYTES} 字节（收到 {len(salt)}）"
        )
    if len(iv) != CONTAINER_IV_BYTES:
        raise BackupError(f"IV 必须是 {CONTAINER_IV_BYTES} 字节（收到 {len(iv)}）")
    _check_kdf_iterations(iterations)
    header = (
        CONTAINER_MAGIC
        + bytes((CONTAINER_VERSION, CIPHER_ID_AES_256_CBC,
                 KDF_ID_PBKDF2_HMAC_SHA256, CONTAINER_RESERVED))
        + struct.pack(">I", iterations)
        + struct.pack(">H", len(salt))
        + struct.pack(">H", len(iv))
        + struct.pack(">Q", plaintext_len)
        + salt
        + iv
    )
    # ⚠️ 结构上不可达，而它是「布局没有被人改过半格」的自我复核：
    #    下一个人往头里加一个字段而忘了改 CONTAINER_HEADER_BYTES，这一格当场响。
    if len(header) != CONTAINER_HEADER_BYTES:
        raise BackupError(
            f"产物头拼出来是 {len(header)} 字节，而 CONTAINER_HEADER_BYTES 写的是 "
            f"{CONTAINER_HEADER_BYTES}：布局与那个常量打架了"
        )
    return header


def parse_container_header(head: bytes, size: int) -> dict[str, object]:
    """产物头 → ``{"iterations", "salt", "iv", "plaintext_len", "header_len"}``。

    ⚠️ **它不解密、也不验 MAC**（那是 :func:`verify_container` 的活）。
    ⚠️ 认不出的东西一律 :class:`BackupError` + 一句人话，**七档**逐个点名：
    被截断 / 版本不对 / 分组密码 id 不对 / KDF id 不对 / 保留字节非 0 /
    盐或 IV 的宽度不对 / 迭代次数出界。⚠️ 而最后那一档是**承重**的：
    头里那个数是**产物可控**的，故读侧要过 :func:`_check_kdf_iterations`
    （否则一份声称「迭代 1 次」的产物就能把恢复时的工作量降到 1）。

    ⚠️ 最后一档（``plaintext_len`` 与密文长度对不上）不报「被改过」而报「不自洽」：
    它更可能是截断（一次没拷完的 U 盘），而 MAC 那一格才是「被改过」的判据。
    """
    if size < CONTAINER_HEADER_BYTES + CONTAINER_MAC_BYTES:
        raise BackupError(
            f"这一份产物只有 {size} 字节，而一个加密档至少要 "
            f"{CONTAINER_HEADER_BYTES + CONTAINER_MAC_BYTES} 字节"
            f"（头 {CONTAINER_HEADER_BYTES} + 尾 {CONTAINER_MAC_BYTES}）："
            "它被截断过，或者压根不是本仓的加密档"
        )
    if len(head) < CONTAINER_HEADER_BYTES:
        raise BackupError(f"读不出完整的产物头（只读到 {len(head)} 字节）")
    if head[: len(CONTAINER_MAGIC)] != CONTAINER_MAGIC:
        raise BackupError(
            f"产物头的魔数不是 {CONTAINER_MAGIC!r}：它不是本仓的加密档"
        )
    version, cipher_id, kdf_id, reserved = head[8], head[9], head[10], head[11]
    if version != CONTAINER_VERSION:
        raise BackupError(
            f"这一份产物的容器版本是 {version}，而本仓只会读 {CONTAINER_VERSION}："
            "它由一个**更新**的版本写出来（⚠️ 不要猜着解，请拿写它的那一份代码来恢复）"
        )
    if cipher_id != CIPHER_ID_AES_256_CBC:
        raise BackupError(
            f"这一份产物的分组密码 id 是 {cipher_id}，而本仓只会读 "
            f"{CIPHER_ID_AES_256_CBC}（AES-256-CBC + PKCS7）"
        )
    if kdf_id != KDF_ID_PBKDF2_HMAC_SHA256:
        raise BackupError(
            f"这一份产物的 KDF id 是 {kdf_id}，而本仓只会读 "
            f"{KDF_ID_PBKDF2_HMAC_SHA256}（PBKDF2-HMAC-SHA256）"
        )
    if reserved != CONTAINER_RESERVED:
        raise BackupError(
            f"产物头的保留字节是 {reserved}（应当恒为 0）："
            "写侧与读侧对这一份布局的理解不一致，或者这一份被改过"
        )
    iterations = struct.unpack(">I", head[12:16])[0]
    salt_len = struct.unpack(">H", head[16:18])[0]
    iv_len = struct.unpack(">H", head[18:20])[0]
    plaintext_len = struct.unpack(">Q", head[20:28])[0]
    if salt_len != CONTAINER_SALT_BYTES or iv_len != CONTAINER_IV_BYTES:
        raise BackupError(
            f"产物头声称盐 {salt_len} 字节 / IV {iv_len} 字节，而本仓只写 "
            f"{CONTAINER_SALT_BYTES} / {CONTAINER_IV_BYTES}：这一份的布局本仓读不了"
        )
    salt = head[28:28 + salt_len]
    iv = head[28 + salt_len:28 + salt_len + iv_len]
    _check_kdf_iterations(iterations)
    cipher_len = size - CONTAINER_HEADER_BYTES - CONTAINER_MAC_BYTES
    if cipher_len <= 0 or cipher_len % CONTAINER_IV_BYTES != 0:
        raise BackupError(
            f"密文那一段是 {cipher_len} 字节，而 AES-CBC 的输出必须是 "
            f"{CONTAINER_IV_BYTES} 的整数倍且非空：这一份被截断过或被改过"
        )
    if not cipher_len - CONTAINER_IV_BYTES <= plaintext_len <= cipher_len - 1:
        raise BackupError(
            f"产物头声称明文 {plaintext_len} 字节，而 {cipher_len} 字节的密文"
            f"（PKCS7）只可能装下 {cipher_len - CONTAINER_IV_BYTES}.."
            f"{cipher_len - 1} 字节：这一份不自洽（通常是一次没拷完的截断）"
        )
    return {
        "iterations": iterations, "salt": salt, "iv": iv,
        "plaintext_len": plaintext_len, "cipher_len": cipher_len,
        "header_len": CONTAINER_HEADER_BYTES,
    }


def product_kind(path: pathlib.Path) -> str:
    """一个产物是**加密档**、**明文档**，还是**认不出**。

    ⚠️⚠️ 判据是**产物头**、⚠️ **不是扩展名**：改前那些明文备份已经在甲方手上了，
    两种都要能吃，而它们的扩展名**逐字相同**（都是 ``pe-<UTC ts>.db``）。
    ⚠️ 它是「这一份是什么形状」这个问题在全仓的**唯一**所有者
    （:mod:`restore` 靠它决定要不要解密）。

    ⚠️ 只读前 16 字节：一个 GB 量级的库不该为了这一格被读一遍。
    ⚠️ 而 16 ≥ 两个魔数的宽度（``PEBACKUP`` 8 字节、``SQLite format 3\\0`` 16 字节）。
    """
    width = max(len(CONTAINER_MAGIC), len(SQLITE_MAGIC))
    with path.open("rb") as handle:
        head = handle.read(width)
    if head.startswith(CONTAINER_MAGIC):
        return KIND_ENCRYPTED
    if head.startswith(SQLITE_MAGIC):
        return KIND_PLAINTEXT
    return KIND_UNKNOWN


def describe_container(path: pathlib.Path) -> dict[str, object]:
    """一份**加密档**的头（不需要口令）。⚠️ 它只答「头上写了什么」，
    不答「MAC 对不对」——那是 :func:`verify_container`。"""
    size = path.stat().st_size
    with path.open("rb") as handle:
        head = handle.read(CONTAINER_HEADER_BYTES)
    return parse_container_header(head, size)


def _mac_over(mac_key: bytes, path: pathlib.Path, start: int, end: int) -> bytes:
    """``path[start:end]`` 的 HMAC-SHA256。**分块**（1 MiB），故不把整份读进内存。"""
    digest = hmac.new(mac_key, digestmod="sha256")
    remaining = end - start
    with path.open("rb") as handle:
        handle.seek(start)
        while remaining > 0:
            chunk = handle.read(min(CHUNK_BYTES, remaining))
            if not chunk:
                raise BackupError(
                    f"{path.name} 在算 HMAC 的过程中短了 {-remaining} 字节："
                    "它在本函数读它的同时被别的进程改小了"
                )
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.digest()


def _read_tail_mac(path: pathlib.Path, size: int) -> bytes:
    with path.open("rb") as handle:
        handle.seek(size - CONTAINER_MAC_BYTES)
        return handle.read(CONTAINER_MAC_BYTES)


def _aes_cbc(
    action: str,
    source: pathlib.Path,
    destination: pathlib.Path,
    key: bytes,
    iv: bytes,
    *,
    append: bool = False,
) -> None:
    """叫一次 ``scripts/aes_cbc.ps1``（AES-256-CBC + PKCS7 的**那一个原语**）。

    ⚠️ **密钥与 IV 走 stdin 的两行 base64**，⚠️ 不走 argv：Windows 上任何同机进程
    都能用 ``Get-CimInstance Win32_Process`` 读到别人**完整的命令行**，
    而 argv 里的那一份会明文出现在进程表里（也会被任何一份进程审计日志收走）。
    ⚠️ 也**不写一个临时文件**（那就是把密钥落盘）。

    ⚠️ 如实记（硬规矩 #39）：那一份 base64 在本进程的内存里是一个 ``bytes``，
    而 Python **不保证**能把它抹掉（不可变对象、且可能已被 GC 复制）。
    ``aes_cbc.ps1`` 那一侧对它自己那一份做了 ``[Array]::Clear``（也是尽力）。
    """
    if not AES_HELPER_PS1.is_file():
        raise BackupError(
            f"找不到 {AES_HELPER_PS1}：AES-256-CBC 的那一个原语住在那个 .ps1 里"
            "（Python 的标准库没有 AES，而本波新增依赖 = 0）。"
            "⚠️ 请确认 backend/scripts/ 是完整的"
        )
    payload = base64.b64encode(key) + b"\n" + base64.b64encode(iv) + b"\n"
    argv = [
        "powershell", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass", "-File", str(AES_HELPER_PS1),
        "-Action", action,
        "-In", str(source.resolve()), "-Out", str(destination.resolve()),
    ]
    if append:
        argv.append("-Append")
    try:
        proc = subprocess.run(
            argv, input=payload, capture_output=True,
            timeout=AES_HELPER_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise BackupError(
            "本机找不到 powershell：加密/解密那一步要经 .NET 的 BCL 做 AES-256-CBC，"
            "而在 Windows 上叫它的唯一姿势是 PowerShell（Python 标准库没有 AES，"
            "本波新增依赖 = 0）。⚠️ 明文档的备份与恢复**不需要**它"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise BackupError(
            f"aes_cbc.ps1 -Action {action} 超过 {AES_HELPER_TIMEOUT_SECONDS:.0f} 秒没有返回："
            "它被挂住了（那一档下产物可能只写了一半，请删掉重来）"
        ) from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise BackupError(
            f"AES 的那一个原语（aes_cbc.ps1 -Action {action}）退出码 "
            f"{proc.returncode}：{detail or '（它没有留下 stderr）'}"
        )


def encrypt_file(
    plain_path: pathlib.Path,
    dest_path: pathlib.Path,
    passphrase: str,
    *,
    iterations: int | None = None,
    salt: bytes | None = None,
    iv: bytes | None = None,
) -> dict[str, object]:
    """把一个**明文**文件封成一个加密产物；返回头上那几格（不含任何秘密）。

    ⚠️ 三步，顺序是**承重**的：① 写 60 字节的头 → ② 让 ``aes_cbc.ps1`` 把密文
    **接在头后面**（``-Append``，于是密文只被写一次）→ ③ 算
    ``HMAC(头 || 密文)`` 追加到尾巴。⚠️ 那正是 **encrypt-then-MAC**：
    MAC 覆盖的是**密文**（连同头），不是明文 —— 于是恢复侧可以
    **在解密之前**就判掉「口令不对」与「产物被改过」两档。

    ⚠️ ``salt`` / ``iv`` / ``iterations`` 都可注入（同 :func:`create_backup` 的
    ``moment`` 先例）：守卫要能钉住产物形状，而 ``secrets.token_bytes`` 会让
    期望值每次都不同。⚠️ 缺省路径一律**现取随机**，故两份备份的盐与 IV
    **不可能**相同（同一个口令、同一份库，两次加密出来的产物字节完全不同）。

    ⚠️ 失败时把 ``dest_path`` 删掉：留一个「头对了、而密文只有前半截」的文件
    比留一个错误更坏（它会被 :func:`product_kind` 认成一份加密档）。
    """
    if not plain_path.is_file():
        raise BackupError(f"要加密的明文文件不存在：{plain_path}")
    plaintext_len = plain_path.stat().st_size
    if plaintext_len == 0:
        raise BackupError(
            f"要加密的明文文件是 0 字节：{plain_path}"
            "（⚠️ 那通常意味着上游的 sqlite3 backup() 没有真的跑成）"
        )
    salt = secrets.token_bytes(CONTAINER_SALT_BYTES) if salt is None else salt
    iv = secrets.token_bytes(CONTAINER_IV_BYTES) if iv is None else iv
    used_iterations = (
        resolve_kdf_iterations() if iterations is None
        else _check_kdf_iterations(iterations)
    )
    header = build_container_header(used_iterations, salt, iv, plaintext_len)
    aes_key, mac_key = derive_keys(passphrase, salt, used_iterations)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with dest_path.open("wb") as handle:
            handle.write(header)
        _aes_cbc("encrypt", plain_path, dest_path, aes_key, iv, append=True)
        mac = _mac_over(mac_key, dest_path, 0, dest_path.stat().st_size)
        with dest_path.open("ab") as handle:
            handle.write(mac)
    except BaseException:
        dest_path.unlink(missing_ok=True)
        raise
    return {
        "iterations": used_iterations, "salt": salt, "iv": iv,
        "plaintext_len": plaintext_len,
        "bytes": dest_path.stat().st_size,
        "header_len": CONTAINER_HEADER_BYTES,
    }


def _verify_container_with_key(
    container_path: pathlib.Path, passphrase: str
) -> tuple[dict[str, object], bytes]:
    """**先验 HMAC**、验过了才把 AES 的钥匙交出去；验不过就 :class:`BackupError`。

    ⚠️⚠️ 派单 §2 第 4 条逐字要求的那一格：「密钥不对 → 不许静默产出一个坏库，
    HMAC 先验、验不过就退出非 0 并说人话，⚠️ **不许走到解密那一步**」。
    本函数**结构上**做不到解密（它只算 MAC 与派生钥匙），故那一格不是靠纪律、
    是靠形状。

    ⚠️ 报错**刻意把两档一起说**（口令不对 / 产物被改过）：encrypt-then-MAC 之下
    两者在密码学上**不可分辨**，而一个只说「口令不对」的报错会把运维支去
    反复试口令，一个只说「被改过」的报错会让他去查一个根本不存在的入侵。
    ⚠️ 而它**刻意不印**期望的 MAC 与实到的 MAC（那是两个 32 字节的秘密派生物；
    印出来对运维没有任何可操作的意义，而它会进日志）。
    """
    size = container_path.stat().st_size
    with container_path.open("rb") as handle:
        head = handle.read(CONTAINER_HEADER_BYTES)
    info = parse_container_header(head, size)
    _aes_key, mac_key = derive_keys(
        passphrase, bytes(info["salt"]), int(info["iterations"])  # type: ignore[arg-type]
    )
    expected = _mac_over(mac_key, container_path, 0, size - CONTAINER_MAC_BYTES)
    got = _read_tail_mac(container_path, size)
    if not hmac.compare_digest(expected, got):
        raise BackupError(
            f"拒绝解密 {container_path.name}：HMAC-SHA256 **验不过**。"
            "⚠️ 只有两种可能，而它们在密码学上不可分辨："
            f"① ${BACKUP_KEY_ENV_VAR} 里那个口令**不是**加密这一份时用的那一个；"
            "② 这一份产物被改过（哪怕只改了 1 个字节，或只改了一个字节的位置）。"
            "⚠️ 本脚本**一步都没有解密**（先验 MAC、验不过就不往下走），"
            "故目标库**没有被改动**、也没有产出一个坏库。"
            "⚠️ 处置：确认那一个口令（它没有第二个后门：--no-verify 跳的是侧车那一格，"
            "HMAC 这一格跳不掉），或换一份备份"
        )
    return info, _aes_key


def verify_container(container_path: pathlib.Path, passphrase: str) -> dict[str, object]:
    """:func:`_verify_container_with_key` 的公开面：只返回头上那几格（不含钥匙）。"""
    info, _key = _verify_container_with_key(container_path, passphrase)
    return info


def decrypt_container(
    container_path: pathlib.Path,
    dest_plain: pathlib.Path,
    passphrase: str,
) -> dict[str, object]:
    """**验过 MAC 之后**把一份加密档解成 ``dest_plain``；返回头上那几格。

    ⚠️ 四步：① 验 MAC（:func:`_verify_container_with_key`）→ ② 把密文那一段
    （``[60, size-32)``）抠到一个临时文件（``aes_cbc.ps1`` 只吃「一块字节」，
    它**不认识**我们的头，⚠️ 而那正是有意的：格式的所有者只有一个）→
    ③ 解密 → ④ 拿头上那个 ``plaintext_len`` 与解出来的字节数**对账**。

    ⚠️ 第 ④ 步不是冗余：它挡的是「MAC 对了、而解密出来的东西不是当初那一份」
    ——结构上不可达（MAC 覆盖密文、密文决定明文），而它是这一条链上**唯一**
    一处能自我复核的地方，故留着（与 :func:`prune_backups` 的删完复核同一条口径）。
    """
    info, aes_key = _verify_container_with_key(container_path, passphrase)
    size = container_path.stat().st_size
    header_len = int(info["header_len"])  # type: ignore[arg-type]
    cipher_end = size - CONTAINER_MAC_BYTES
    body_path = dest_plain.with_name(dest_plain.name + ".body")
    try:
        with container_path.open("rb") as source, body_path.open("wb") as sink:
            source.seek(header_len)
            remaining = cipher_end - header_len
            while remaining > 0:
                chunk = source.read(min(CHUNK_BYTES, remaining))
                if not chunk:
                    raise BackupError(
                        f"{container_path.name} 在抠密文那一段时短了 {remaining} 字节"
                    )
                sink.write(chunk)
                remaining -= len(chunk)
        _aes_cbc("decrypt", body_path, dest_plain, aes_key, bytes(info["iv"]))  # type: ignore[arg-type]
    finally:
        body_path.unlink(missing_ok=True)
    actual = dest_plain.stat().st_size
    if actual != info["plaintext_len"]:
        raise BackupError(
            f"解密出来的明文是 {actual} 字节，而产物头声称 {info['plaintext_len']} 字节："
            "这一份不自洽（⚠️ MAC 是验过的，故那一格说明写侧与读侧对布局的理解不同）。"
            f"⚠️ {dest_plain} 因此**不是**一份可用的库，请不要恢复它"
        )
    return info


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
    # ⚠️⚠️ 口令**只在这一处**从环境里取（``create_backup`` 与 ``restore`` 都不自己读），
    #    于是「密钥从哪来」这件事在全仓只有一个住址。
    passphrase = resolve_backup_passphrase()
    destination = create_backup(db_path, backups_dir, passphrase=passphrase)
    sidecar = read_sidecar(sidecar_of(destination))
    print("== 厦大体育数智系统 · 备份 ==")
    print("   源库   %s" % db_path)
    print("   备份   %s" % destination)
    print("   侧车   %s" % sidecar_of(destination))
    print("   字节   %d" % sidecar["bytes"])
    print("   sha256 %s…" % str(sidecar["sha256"])[:16])
    if product_kind(destination) == KIND_ENCRYPTED:
        info = describe_container(destination)
        print("   形状   **加密档**（魔数 %s + 版本 %d）"
              % (CONTAINER_MAGIC.decode("ascii"), CONTAINER_VERSION))
        print("          AES-256-CBC + PKCS7，尾 %d B 的 HMAC-SHA256（encrypt-then-MAC）"
              % CONTAINER_MAC_BYTES)
        print("          口令来自 $%s（⚠️ 本脚本刻意不印它的任何一部分——"
              "长度、sha、base64 都不印）" % BACKUP_KEY_ENV_VAR)
        print("          KDF    PBKDF2-HMAC-SHA256 × %s 次、盐 %d B（这一份自己的随机盐）"
              % (info["iterations"], CONTAINER_SALT_BYTES))
        print("          明文   %s B → 产物 %d B（头 %d + 密文 + 尾 %d）"
              % (info["plaintext_len"], sidecar["bytes"],
                 CONTAINER_HEADER_BYTES, CONTAINER_MAC_BYTES))
        print("   ⚠️⚠️ 口令**丢了这一份就打不开**（本仓刻意不做密钥托管，也没有第二个后门："
              "restore 的 --no-verify 跳的是侧车那一格，HMAC 那一格跳不掉）。")
        print("      请把它记在与备份**分开**的地方；恢复时同一个环境变量要在。")
    else:
        print("   形状   **明文档**（产物头是 SQLite 自己的格式串，任何 SQLite 客户端直接打开）")
        print("")
        print("   ⚠️⚠️⚠️ 这一份是**明文**的：它是一个可以直接用任何 SQLite 客户端打开的")
        print("      整库副本，里面是全校学生的**出生日期、体成分、体测结果、运动处方与预警**。")
        print("      它一旦被拷进 U 盘 / 网盘 / 邮件附件，就**只**受那台机器的文件系统权限")
        print("      保护 —— 而一个 U 盘没有权限、也没有防火墙。")
        print("      ⇒ 要加密请设一个环境变量、再跑一次同一条命令：")
        print('            $env:%s = "<一个只有运维知道的口令，至少 %d 个字符>"'
              % (BACKUP_KEY_ENV_VAR, MIN_PASSWORD_LENGTH))
        print("            powershell -ExecutionPolicy Bypass -File backend\\scripts\\backup.ps1")
        print("        产物会变成一份**自描述**的加密档（AES-256-CBC + HMAC-SHA256），")
        print("        而**文件名与侧车都不变** ⇒ restore.ps1 两种都吃")
        print("        （它按**产物头**认，⚠️ 不按扩展名）。")
        print("      ⚠️ 口令**丢了就打不开**（本仓刻意不做密钥托管），请把它记在")
        print("        与备份**分开**的地方。")
        print("      ⚠️ 本段告示**不因任何别的环境变量而闭嘴**：$%s 不在，这一份就是明文的，"
              % BACKUP_KEY_ENV_VAR)
        print("        而那一格必须响（而不是静默产出一份看起来一样的备份）。")
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

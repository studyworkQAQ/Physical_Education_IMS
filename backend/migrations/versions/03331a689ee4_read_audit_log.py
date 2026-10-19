"""迁移 5：加 ``read_audit_log`` 一张表（Plan 08 Task 1 的**敏感读**留痕）。

⚠️ **本文件是 ``alembic revision --autogenerate`` 的原始输出 + 人审**，而人审只做了
一件事：把这段 docstring 写出来（**DDL 一个字都没改**）。审的四格逐条如下
（与第三条迁移 ``7f3923d8af84`` 同款）：

1. **autogenerate 的 diff 只含新表 + 那一个索引**（亲跑取证，命令与库见本 Task 报告 §3）::

       INFO [alembic.autogenerate.compare.tables]       Detected added table 'read_audit_log'
       INFO [alembic.autogenerate.compare.constraints]  Detected added index
            'ix_read_audit_log_student_id_at' on '('student_id', 'at')'

   ⚠️ **两行、没有第三行**是本条迁移最重要的性质：它证明 ``app/db/models/**`` 的其余
   28 张表与 ``0ac943e0da9b`` 建出来的库**逐格一致**（否则 autogenerate 会顺手报出
   ``add_column`` / ``alter_column`` 一类），也就是「本 Task 只加了一张表」。
   判据不靠人眼：``tests/db/test_migration_chain.py`` 的
   :func:`test_the_migration_chain_is_in_sync_with_the_models` 在 head 上再跑一次
   ``command.check``，**应当无 diff**；有 diff 就是模型改了没配迁移。
   ⚠️ **本条生成过两次**，而第二次才是入库的那一份（如实记，硬规矩 #39）：
   第一次把 ``subject_id`` 声明成 ``NOT NULL``，实现者跑行为探针时当场撞上
   ``sqlite3.IntegrityError: NOT NULL constraint failed: read_audit_log.subject_id``
   —— 成因是 :func:`app.api.deps.current_teacher` 的**请求头那一支刻意不查**
   ``teacher.id``（它的注释逐字写着「那一次查询对审计没有任何用处」），
   故教职走请求头时那一格是 ``NULL``。⚠️ 处置是**沿用那一条既有裁定**（把列改成可空，
   与 ``audit_log.subject_id`` 同档）而**不是**推翻它（那会给 1600+ 条测试走的
   每一个教职请求头请求多一次点查）。逐字理由见
   :attr:`app.db.models.audit.ReadAuditLog.subject_id` 的列注释。
   ⚠️ 于是第一次生成的那个修订号（``8f58ae5216a8``）被**删掉重新生成**，
   为的是保住本文件开头那一句「DDL 一个字都没改」——手工把 ``nullable=False``
   改成 ``True`` 会让那句话变成假的。
2. **没有 ``JsonText`` 列**，故**不需要**基线迁移里那句承重的
   ``import app.db.models._shared``（alembic 会把自定义 ``TypeDecorator`` 渲染成限定名
   却**不生成 import**，理由逐字见基线迁移的模块 docstring）。⚠️ 本表 9 列全是标量
   （``Integer`` ×4 / ``String`` ×3 / ``DateTime`` ×1，其中四个可空），
   与 ``audit_log`` 的 9 列**同族同数**、而**各另有两格不同**
   （写审计是 ``method`` + ``path``，本表是 ``route`` + ``student_id``；
   对照表逐字见 :class:`app.db.models.audit.ReadAuditLog` 的 docstring）。
   ⚠️ 而「9 列全是标量」不是一个巧合，它是**隐私纪律的结构形式**（与 ``audit_log``
   逐字同一条）：本表里**没有**能装请求体或查询串的列，故「读审计不落请求体」
   不是一条要靠人克住的规矩。守卫是 ``tests/api/test_read_audit_api.py`` 的
   ``test_a_sensitive_read_with_a_body_and_a_query_string_leaves_no_trace_of_either``
   （**真的**发一次带请求体 + 带探针查询串的敏感读，然后把落库那一行的**全部 9 列**
   逐列扫一遍）与 ``test_no_read_audit_schema_mentions_a_credential_or_a_body``
   （结构侧：三个契约模型的字段名里不出现 ``password`` / ``birth`` / ``body`` 一类）。
3. **``create_index`` 被包进 ``batch_alter_table``**，那是 ``migrations/env.py`` 的
   ``render_as_batch=True`` 的后果（SQLite 没有 ``ALTER COLUMN``，批处理是那条链上
   唯一能落地的改法），与 ``7f3923d8af84`` 里那一个索引**同一个形状**。
   ⚠️ **对一张刚建出来的空表走批处理只是多一次「建新表 → 拷 0 行 → 改名」**，
   正确性不受影响；而「迁移建出来的库 == ``create_all`` 建出来的库」由
   ``tests/db/test_migration_baseline.py`` 逐表逐列逐索引逐唯一约束逐外键钉住。
   ⚠️ 它是**全库第三个复合索引**（前两个是 ``ix_login_attempt_kind_login_at`` 与
   ``ix_audit_log_subject_kind_at``）；列序 ``(student_id, at)`` 与那两个**刻意不同**，
   逐字理由见 :class:`app.db.models.audit.ReadAuditLog` 的 ``__table_args__`` 注释
   （一句话：写审计最常问「**哪一类人**做了什么」，读审计最常问「**这一个学生**的档案
   被谁翻过」，故等值列不同；「等值在前、范围在后」那一条口径三张表相同）。
4. **一行数据都没有**（``tests/db/test_migration_chain.py`` 的
   :func:`test_the_migration_scripts_carry_no_data` 按 AST 判：不许出现
   ``op.bulk_insert`` / ``op.execute``，也不许有非 docstring 的字符串常量以
   ``INSERT`` / ``UPDATE`` / ``DELETE`` 开头）。⚠️ 读审计行**天然**只能由运行时的
   HTTP 请求经 :class:`app.api.read_audit.ReadAuditMiddleware` 写，故「升级完甲方库里
   就有一堆读审计行」这件事不仅不该发生、发生了还是错的
   （那些行会指向从未发生过的读）。

--------------------------------------------------------------------------
⚠️⚠️ ``downgrade`` **真跑过一遍**（计划 §1 第 5 条逐字要求；§15 C3 不许再犯）
--------------------------------------------------------------------------

Plan 06 Task 4 在**迁移 4** 上留过一个跑不通的 ``downgrade``（已登记 spec §15 C3），
计划 §1 因此逐字写着「**本波不许再犯**」。本条的取证不是「我看它像是对的」，
两格亲跑（命令与输出逐字见本 Task 报告 §3）：

* **一次性探针**（临时库）：``upgrade head`` → **灌一行 ``read_audit_log``
  + 一行 ``audit_log``** → ``downgrade -1`` → 实测 ``read_audit_log`` 没了、
  ``alembic_version`` 停在 ``0ac943e0da9b``、**``audit_log`` 那一行逐字还在** →
  ``upgrade head`` → 表回来了且是空的；
* **常驻守卫**：``tests/db/test_migration_chain.py`` 的
  :func:`test_the_read_audit_log_migration_round_trips_and_keeps_every_other_row`
  把上面那一圈钉成一条会红的断言（⚠️ 姿势照迁移 4 那一条
  :func:`test_the_column_width_migration_round_trips_and_keeps_every_row`，
  而它比那一条**多钉一格**：回滚**不许碰**另一张审计表的行）。

⚠️ **``downgrade`` 是有意义的**（``drop_index`` + ``drop_table``），而 ⚠️⚠️
它与 ``7f3923d8af84`` 一样是「**回滚会丢数据**」的一档：``read_audit_log`` 里装的是
**已经发生过**的读的留痕，删掉它不可重推。故要回滚这一条，请先跑
``backend/scripts/backup.py``（Plan 06 Task 6）。
⚠️ 而它比迁移 4 那一格**好**在：它不动任何既有表的行（迁移 4 的 ``downgrade`` 要把
``login_attempt`` 的列宽改回去，库里已有 33–64 字符的键时换后端会失败/静默截断）。
本条只 ``DROP`` 一张**本条自己建的**表，故它在任何后端上都是同一件事。

⚠️ **本文件的行尾与编码与既有四款同款**（实测 CRLF / UTF-8 无 BOM；
``alembic revision`` 自己写出来的是**混行尾**——本次实测 28 个 CRLF + 22 个裸 LF，
与迁移 3 那一格逐字相同，故本次显式归一成 CRLF，判据是
``tests/db/test_migration_chain.py`` 的
:func:`test_the_migration_scripts_are_utf8_without_bom_and_parse` 与本 Task 报告 §3 的
逐文件实测），且 ``alembic.ini`` 的 ``output_encoding = utf-8`` 就是为此显式钉住的
（缺省是平台 locale = 本机 GBK，于是这段中文 docstring 会以另一种编码落盘）。

Revision ID: 03331a689ee4
Revises: 0ac943e0da9b
Create Date: 2026-10-17 17:45:17.244394

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03331a689ee4'
down_revision: Union[str, Sequence[str], None] = '0ac943e0da9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('read_audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('at', sa.DateTime(), nullable=False),
    sa.Column('subject_kind', sa.String(length=16), nullable=False),
    sa.Column('subject_id', sa.Integer(), nullable=True),
    sa.Column('staff_no', sa.String(length=32), nullable=True),
    sa.Column('route', sa.String(length=256), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.Column('target', sa.String(length=64), nullable=True),
    sa.CheckConstraint("subject_kind IN ('student', 'teacher')", name='ck_read_audit_log_subject_kind'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('read_audit_log', schema=None) as batch_op:
        batch_op.create_index('ix_read_audit_log_student_id_at', ['student_id', 'at'], unique=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema.

    ⚠️⚠️ **下面那一句 ``drop_table`` 会连 ``read_audit_log`` 里的行一起丢掉，而 alembic
    一句警告都不印**（Plan 08 Task 8 补，终审 **R7-11**）：``DROP TABLE`` 的语义
    就是「表**与它的全部行**」，而 alembic 只报一行
    ``Running downgrade 03331a689ee4 -> 0ac943e0da9b``。⚠️ 这与 ``backend/scripts/retention.py``
    的口径**不一致**：那一个删行之前先**预告**将删多少行、删完再**逐格复核**
    「实删与预告对不上就整批回滚」（退出码 2），而本函数**既不预告也不复核**
    （它是一次 DDL，不是一个能对账的批处理）。⇒ **回滚之前请先跑一次
    ``backup.ps1``**（⚠️ 缺省产出的是**明文**整库副本；设 ``PE_BACKUP_KEY``
    才是加密档，逐字见 spec §13.25）。⚠️ 取证（终审在一份探针库上亲跑）：
    灌进 ``read_audit_log`` 1 行 → ``downgrade -1`` → ``upgrade head`` ⇒ 表**回来了但是空的**，
    而其余 28 张表逐字未变（摊平求 sha256 三次都是 ``57BB3C86CF4604E3``）。
    ⚠️ 而「**跑过一遍**」不等于「**有常驻守卫**」：迁移 1/2/3 至今没有各自的
    往返守卫（⇒ spec §15 **F13** 与 ``tests/db/test_migration_chain.py:84`` 的自陈）。
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('read_audit_log', schema=None) as batch_op:
        batch_op.drop_index('ix_read_audit_log_student_id_at')

    op.drop_table('read_audit_log')
    # ### end Alembic commands ###

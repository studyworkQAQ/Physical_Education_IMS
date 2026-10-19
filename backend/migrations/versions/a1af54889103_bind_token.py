"""迁移 6：加 ``bind_token`` 一张表（Plan 08 Task 4 的**一次性绑定令牌**）。

⚠️ **本文件是 ``alembic revision --autogenerate`` 的原始输出 + 人审**，而人审只做了
一件事：把这段 docstring 写出来（**DDL 一个字都没改**）。审的四格逐条如下
（与第五条迁移 ``03331a689ee4`` 同款）：

1. **autogenerate 的 diff 只含新表 + 那一个索引**（亲跑取证，命令与库见本 Task 报告 §2）::

       INFO [alembic.autogenerate.compare.tables]       Detected added table 'bind_token'
       INFO [alembic.autogenerate.compare.constraints]  Detected added index
            'ix_bind_token_kind_login_expires_at' on '('kind', 'login', 'expires_at')'

   ⚠️ **两行、没有第三行**是本条迁移最重要的性质：它证明 ``app/db/models/**`` 的其余
   29 张表与 ``03331a689ee4`` 建出来的库**逐格一致**（否则 autogenerate 会顺手报出
   ``add_column`` / ``alter_column`` 一类），也就是「本 Task 只加了一张表」。
   判据不靠人眼：``tests/db/test_migration_chain.py`` 的
   :func:`test_the_migration_chain_is_in_sync_with_the_models` 在 head 上再跑一次
   ``command.check``，**应当无 diff**；有 diff 就是模型改了没配迁移。
   ⚠️ 取证的姿势是「先 ``alembic upgrade 03331a689ee4`` 灌一个**29 张表**的临时库、
   再对着它 autogenerate」——直接对一个 ``create_all`` 出来的库跑 autogenerate 会得到
   「0 行 diff」，而那是一格**假绿**（它证明的是「模型等于模型」）。
2. **没有 ``JsonText`` 列**，故**不需要**基线迁移里那句承重的
   ``import app.db.models._shared``（alembic 会把自定义 ``TypeDecorator`` 渲染成限定名
   却**不生成 import**，理由逐字见基线迁移的模块 docstring）。⚠️ 本表 9 列全是标量
   （``Integer`` ×1 / ``String`` ×4 / ``DateTime`` ×4，其中两个可空）。
   ⚠️⚠️ 而「9 列全是标量」里的 ``token_hash`` 那一格是**隐私纪律的结构形式**
   （与 ``student.password_hash`` / ``audit_log`` 那两张表逐字同一条）：
   库里存的是 :func:`app.auth.passwords.hash_password` 的产出，**明文令牌从来没有落过库**。
   ⚠️ 而同表的 ``token_id`` 那一格**是明文**（它是选择子、不是秘密），
   逐字理由与「为什么必须有它」住在
   :class:`app.db.models.auth.BindToken` 的 docstring 第二节，本处不抄第二份。
   守卫是 ``tests/api/test_bind_token.py`` 的
   ``test_the_plaintext_token_and_its_secret_never_reach_any_column_of_any_table``
   （扫**全库 30 张表的每一列**）。
3. **``create_index`` 被包进 ``batch_alter_table``**，那是 ``migrations/env.py`` 的
   ``render_as_batch=True`` 的后果（SQLite 没有 ``ALTER COLUMN``，批处理是那条链上
   唯一能落地的改法），与 ``7f3923d8af84`` / ``03331a689ee4`` 里那两个索引**同一个形状**。
   ⚠️ **对一张刚建出来的空表走批处理只是多一次「建新表 → 拷 0 行 → 改名」**，
   正确性不受影响；而「迁移建出来的库 == ``create_all`` 建出来的库」由
   ``tests/db/test_migration_baseline.py`` 逐表逐列逐索引逐唯一约束逐外键钉住。
   ⚠️ 它是**全库第四个复合索引**（前三个是 ``ix_login_attempt_kind_login_at`` /
   ``ix_audit_log_subject_kind_at`` / ``ix_read_audit_log_student_id_at``）；
   列序 ``(kind, login, expires_at)`` 与那三个**同一条口径**（等值列在前、范围列在后），
   逐字理由见 :class:`app.db.models.auth.BindToken` 的 ``__table_args__`` 注释。
   ⚠️⚠️ 而 ``token_id`` 上那一个 **UNIQUE 约束**（``sa.UniqueConstraint('token_id')``）
   是**本条迁移里唯一一格不服务于查询的东西**：它是一张唯一索引，
   既是「兑换那一次点查」的索引、又是「两行不得共用一个选择子」的不变量
   （逐字理由见 :attr:`app.db.models.auth.BindToken.token_id` 的列注释）。
4. **一行数据都没有**（``tests/db/test_migration_chain.py`` 的
   :func:`test_the_migration_scripts_carry_no_data` 按 AST 判：不许出现
   ``op.bulk_insert`` / ``op.execute``，也不许有非 docstring 的字符串常量以
   ``INSERT`` / ``UPDATE`` / ``DELETE`` 开头）。⚠️ 令牌行**天然**只能由
   ``POST /api/auth/bind-tokens``（**仅管理员**）经 :func:`app.auth.bind_tokens.issue` 写，
   故「升级完甲方库里就有一堆令牌行」这件事不仅不该发生、发生了还是错的
   （那些行会是**活的凭据**——一张没人签发过、却可以兑换的令牌）。

--------------------------------------------------------------------------
⚠️⚠️ ``downgrade`` **真跑过一遍**（计划 §2 第 2 条逐字要求；§15 C3 不许再犯）
--------------------------------------------------------------------------

Plan 06 Task 4 在**迁移 4** 上留过一个跑不通的 ``downgrade``（已登记 spec §15 C3），
Plan 08 §1 因此逐字写着「**本波不许再犯**」（Task 1 兑现过一次，本条是第二次）。
本条的取证不是「我看它像是对的」，两格亲跑（命令与输出逐字见本 Task 报告 §2）：

* **一次性探针**（临时库）：``upgrade head`` → **灌一行 ``bind_token``
  + 一行 ``audit_log`` + 一行 ``read_audit_log`` + 一行 ``student``** → ``downgrade -1``
  → 实测 ``bind_token`` 没了、``alembic_version`` 停在 ``03331a689ee4``、
  **另外三张表的那些行逐字还在** → ``upgrade head`` → 表回来了且是空的；
* **常驻守卫**：``tests/db/test_migration_chain.py`` 的
  :func:`test_the_bind_token_migration_round_trips_and_keeps_every_other_row`
  把上面那一圈钉成一条会红的断言（⚠️ 姿势照迁移 5 那一条
  :func:`test_the_read_audit_log_migration_round_trips_and_keeps_every_other_row`，
  而它比那一条**多钉两张表**：回滚不许碰 ``student`` 的行 —— 那张表是本 Task
  的**业务对象**，「回滚一条迁移把名册也带走了」是这一族里最坏的一格失效）。

⚠️ **``downgrade`` 是有意义的**（``drop_index`` + ``drop_table``），而 ⚠️⚠️
它与 ``7f3923d8af84`` / ``03331a689ee4`` 一样是「**回滚会丢数据**」的一档：
``bind_token`` 里装的是**已经签发过**的凭据台账（谁在什么时候给谁发的、有没有用掉），
删掉它不可重推。故要回滚这一条，请先跑 ``backend/scripts/backup.py``（Plan 06 Task 6）。
⚠️ 而它比迁移 4 那一格**好**在：它不动任何既有表的行（迁移 4 的 ``downgrade`` 要把
``login_attempt`` 的列宽改回去，库里已有 33–64 字符的键时换后端会失败/静默截断）。
本条只 ``DROP`` 一张**本条自己建的**表，故它在任何后端上都是同一件事。

⚠️⚠️ **回滚之后那两个自助绑定端点照旧工作**（``PE_ALLOW_SELF_BIND`` 缺省是 ``1``），
故「回滚这一条迁移」不会把任何人锁在门外 —— 那一格是计划 §4 那句
「**要做得可回退**」的**数据库侧**的一半（另一半是开关本身）。
⚠️ 而**代码侧不回滚**的话（模型上还有 ``BindToken``、端点还在），
一个回滚过迁移的库会让三个新端点一律 500（``no such table: bind_token``）。
故正确的回滚姿势是「**代码与迁移一起退**」（``git revert`` 那个 commit），
如实记录（硬规矩 #39）。

⚠️ **本文件的行尾与编码与既有五款同款**（实测 CRLF / UTF-8 无 BOM；
``alembic revision`` 自己写出来的是**混行尾**——本次实测与迁移 3/5 那两格逐字同款，
故本次显式归一成 CRLF，判据是
``tests/db/test_migration_chain.py`` 的
:func:`test_the_migration_scripts_are_utf8_without_bom_and_parse` 与本 Task 报告 §9 的
逐文件实测），且 ``alembic.ini`` 的 ``output_encoding = utf-8`` 就是为此显式钉住的
（缺省是平台 locale = 本机 GBK，于是这段中文 docstring 会以另一种编码落盘）。

Revision ID: a1af54889103
Revises: 03331a689ee4
Create Date: 2026-10-18 16:09:45.547714

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1af54889103'
down_revision: Union[str, Sequence[str], None] = '03331a689ee4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('bind_token',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('token_id', sa.String(length=32), nullable=False),
    sa.Column('token_hash', sa.String(length=255), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('login', sa.String(length=32), nullable=False),
    sa.Column('issued_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.Column('issued_by', sa.String(length=32), nullable=True),
    sa.CheckConstraint("kind IN ('student', 'teacher')", name='ck_bind_token_kind'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_id')
    )
    with op.batch_alter_table('bind_token', schema=None) as batch_op:
        batch_op.create_index('ix_bind_token_kind_login_expires_at', ['kind', 'login', 'expires_at'], unique=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema.

    ⚠️⚠️ **下面那一句 ``drop_table`` 会连 ``bind_token`` 里的行一起丢掉，而 alembic
    一句警告都不印**（Plan 08 Task 8 补，终审 **R7-11**）：``DROP TABLE`` 的语义
    就是「表**与它的全部行**」，而 alembic 只报一行
    ``Running downgrade a1af54889103 -> 03331a689ee4``。⚠️ 这与 ``backend/scripts/retention.py``
    的口径**不一致**：那一个删行之前先**预告**将删多少行、删完再**逐格复核**
    「实删与预告对不上就整批回滚」（退出码 2），而本函数**既不预告也不复核**
    （它是一次 DDL，不是一个能对账的批处理）。⇒ **回滚之前请先跑一次
    ``backup.ps1``**（⚠️ 缺省产出的是**明文**整库副本；设 ``PE_BACKUP_KEY``
    才是加密档，逐字见 spec §13.25）。⚠️ 取证（终审在一份探针库上亲跑）：
    灌进 ``bind_token`` 1 行 → ``downgrade -1`` → ``upgrade head`` ⇒ 表**回来了但是空的**，
    而其余 28 张表逐字未变（摊平求 sha256 三次都是 ``57BB3C86CF4604E3``）。
    ⚠️ 而「**跑过一遍**」不等于「**有常驻守卫**」：迁移 1/2/3 至今没有各自的
    往返守卫（⇒ spec §15 **F13** 与 ``tests/db/test_migration_chain.py:84`` 的自陈）。
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('bind_token', schema=None) as batch_op:
        batch_op.drop_index('ix_bind_token_kind_login_expires_at')

    op.drop_table('bind_token')
    # ### end Alembic commands ###

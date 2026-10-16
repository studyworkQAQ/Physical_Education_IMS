"""**公网隧道档**的守卫（Plan 07 Task 3）：``scripts/tunnel.ps1`` + ``tools/`` + ``.trial/`` 那一条纪律。

--------------------------------------------------------------------------
⚠️ 本文件钉的是**脚本的形状**，不是「隧道真的开起来了」
--------------------------------------------------------------------------
「一条命令开一条甲方能点开的公网链接」那一格的可执行判据是**跨进程 + 跨公网**的
（起一个 uvicorn、起一个 ``cloudflared``、从 Cloudflare 的边缘绕回来打一次
``/api/health``、再用真浏览器量 cookie 的 ``secure`` 属性），故它的取证住在
本波实现者报告里（六格端到端），而**不在** pytest 里：``tests/`` 一律用
:class:`fastapi.testclient.TestClient`、一个端口都不占、更不出网
（逐字口径见 ``tests/test_serve.py`` 的模块 docstring 第一节）。

⚠️ **本文件补的是那一格补不到的东西**：端到端全绿只证明「今天这台机器上这个网络里
这条链接打得开」，而它**证明不了**下面这七档 —— 七档的失效方向都是**静默**的：

1. ``tunnel.ps1`` 变成了**第二个服务器启动器**（于是「服务怎么起」有了两个所有者，
   改一处漏一处，而漏掉的那一处是要交给甲方运维跑的）；
2. 健康检查那一步被删掉 ⇒ 服务没起时也照样开隧道，于是**一条打到空端口的公网链接**
   被印出来交给甲方（Cloudflare 会回它自己的 5xx 错误页，看上去「链接是活的」）；
3. 「抓到 URL 之后**真发一次请求复核它活着**」被删掉 ⇒ 抓到一串字符就算成功，
   而 quick tunnel 自己就印一句 "it may take some time to be reachable"；
4. 抓 URL 的正则**放宽**（例如 ``https://\\S+``）⇒ 抓到的是 cloudflared 日志第一行
   免责声明里的 ``https://www.cloudflare.com/website-terms/``，
   于是「一条打不开的公网链接」被印给甲方（本条有一拍**行为**取证，不只是文本比对）；
5. ``tools/`` 或 ``.trial/`` 从 ``.gitignore`` 里掉出去 ⇒ 一个 55 MB 的平台绑死二进制
   或**一条公网可达的临时地址**被提交进 git 历史（历史删不掉）；
6. 孤儿清理的判据**放宽**成「进程名是 cloudflared 就杀」⇒ 杀掉甲方 IT 自己在跑的
   named tunnel（本仓的口径是「宁可漏杀不可误杀」）；
7. 六条风险告示少了一条 ⇒ 交付现场没人念到「未绑定账号可被抢绑」或
   「GET 读操作今天不留审计」那两条（spec §1.2 第 4 / 第 14 条）。

--------------------------------------------------------------------------
⚠️ 为什么切「代码段」而不是整个文件
--------------------------------------------------------------------------
``<# .DESCRIPTION #>`` 里会**提及**若干它刻意不做的事（``netsh`` 的形状、
``uvicorn`` 的名字、演示口令的唯一所有者在哪一行、``-Lan`` 那一档为什么必须留在 dev），
扫整个文件会红在自己的说明文字上（硬规矩 #109）。姿势与
``tests/test_serve.py`` 的 :func:`_serve_ps1_code` /
``tests/test_trial.py`` 的 ``_trial_ps1_code`` 逐字相同。
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess

from app.config import BACKEND_DIR

#: 仓库根。⚠️ 由 :data:`app.config.BACKEND_DIR` 推出来、**不在本文件里敲第二遍路径**
#: （与 ``tests/test_serve.py`` / ``tests/test_trial.py`` 的 ``REPO_ROOT`` 同一条口径）。
REPO_ROOT = BACKEND_DIR.parent

TUNNEL_PS1 = REPO_ROOT / "scripts" / "tunnel.ps1"
SERVE_PS1 = REPO_ROOT / "scripts" / "serve.ps1"
TRIAL_PS1 = REPO_ROOT / "scripts" / "trial.ps1"
GITIGNORE = REPO_ROOT / ".gitignore"
PYPROJECT = REPO_ROOT / "backend" / "pyproject.toml"
PACKAGE_JSON = REPO_ROOT / "frontend" / "package.json"

#: 公网 URL 落在哪个文件（相对于仓库根）。⚠️ **字面量**（硬规矩 #35）：
#: 它的一半就是被测对象（``tunnel.ps1`` 的 ``$UrlFile`` 与 ``.gitignore`` 的那一行），
#: 从任何一侧读回来跟自己比都是同源断言。
URL_FILE_RELATIVE = ".trial/public-url.txt"

#: ``.gitignore`` 里那两条目录规则（⚠️ 字面量，理由同上）。
IGNORED_DIRS = ("tools/", ".trial/")

#: 隧道档缺省的端口。⚠️ 字面量：它必须与 ``trial.ps1`` 的缺省**对齐**
#: （那一个是「给甲方点的那一份」，本档是把它接到公网上）。
TUNNEL_PORT = 8030

#: 六条风险告示各自的**无歧义串**（派单 §2 第 4 条逐字点名的六件事）。
#: ⚠️ 顺序即打印顺序；每一串都只在 ⑥ 那一段里出现一次，故删掉任何一条当场红。
SIX_WARNINGS = (
    "这条链接是**公网可达**的",           # ① 任何知道它的人都能打开
    "**演示口令是公开的**",                # ② 指向 DEMO_PASSWORD，不抄字面量
    "未绑定的账号可以被**抢绑**",          # ③ spec §1.2 第 4 条
    "GET 读操作今天**不留审计**",          # ④ spec §1.2 第 14 条 / §13.9
    "**不要录入真实学生信息**",            # ⑤ 页面上也挂着同一条告示
    "**链接的寿命 = 本进程的寿命**",       # ⑥ 重开会变
)

#: 档位矩阵（派单 §4 第 ③ 条）：两处打印的档位提示必须是**两段不同的话**。
#: ⚠️ 每一串都是那一段里**独有**的一句话，不是共用的词（``Secure`` / ``dev`` /
#: ``prod`` / ``§13.11.3`` 两处都有，拿它们当判据会恒绿）。
PUBLIC_TIER_NEEDLE = "公网档就是这一档：隧道边缘是 HTTPS"
LAN_TIER_NEEDLE = "同一个网段里的任何人都打得开"


def _tunnel_ps1_code() -> str:
    """``tunnel.ps1`` 的**代码段**（那块 comment-based help 之后那一部分）。

    ⚠️ ``count("#>") == 1`` 那一拍是承重的：本文件里的函数**一律不用** PowerShell 的
    块注释（用 ``#`` 行注释），于是全文件恰好一个收尾符；谁在函数里加了一块
    ``<# … #>``，本函数会当场 assert 而不是**静默切错位置**（那会让下面每一条
    守卫都在一段错误的文本上恒绿）。
    """
    raw = TUNNEL_PS1.read_bytes()
    body = raw[3:].decode("utf-8") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("utf-8")
    assert body.count("#>") == 1, "tunnel.ps1 的注释块形状变了，本函数的切法要跟着改"
    # ⚠️ 行尾归一成 ``\n``：本仓的 ``.ps1`` 一律 CRLF，而下面有几条判据用 ``re.M`` + ``$``
    #    （行尾锚），不归一的话 ``$`` 会落在 ``\r`` 之前、于是那些判据**恒红**在一个
    #    与真因无关的地方（``\r`` 在行尾）。⚠️ 而「CRLF 本身」由
    #    :func:`test_tunnel_ps1_is_utf8_with_bom_and_crlf_like_every_other_ps1_in_this_repo`
    #    按**字节**钉住，故归一不会把那一格放掉。
    return body.split("#>", 1)[1].replace("\r\n", "\n")


def _statements() -> str:
    """代码段里**去掉注释行**之后的那一部分（提及不是本身，硬规矩 #109）。"""
    return "\n".join(
        line for line in _tunnel_ps1_code().splitlines()
        if not line.lstrip().startswith("#")
    )


def _git(*args: str) -> str:
    """在**仓库根**跑一条 git 命令并要它的 stdout（失败当场 assert）。"""
    run = subprocess.run(
        ("git", "-c", "core.quotepath=false", *args),
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    assert run.returncode == 0, (args, run.stderr)
    return run.stdout


# ===========================================================================
# ① 文件形状：UTF-8 + BOM + 纯 CRLF（与本仓另外 5 个 .ps1 同款）
# ===========================================================================


def test_tunnel_ps1_is_utf8_with_bom_and_crlf_like_every_other_ps1_in_this_repo():
    """**UTF-8 + BOM + 纯 CRLF**。

    ⚠️ BOM 是承重的、不是洁癖：PowerShell 5.1 读一个**没有 BOM** 的 ``.ps1`` 时按
    系统 ANSI 代码页（本机 GBK）解码，而本文件的注释里全是 UTF-8 中文——
    轻则注释乱码，重则某个字节序列里出现一个引号/反引号把语法弄坏。
    本仓为此付过四次代价（``.gitattributes`` 那一段逐字记着）。
    ⚠️ 三拍与 ``tests/test_trial.py`` 的
    ``test_trial_ps1_is_utf8_with_bom_and_crlf_like_every_other_ps1_in_this_repo``
    逐字同款。
    """
    raw = TUNNEL_PS1.read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf", "tunnel.ps1 没有 BOM（PowerShell 5.1 会按 GBK 读它）"
    body = raw[3:]
    crlf = body.count(b"\r\n")
    bare = body.count(b"\n") - crlf
    assert bare == 0, f"tunnel.ps1 有 {bare} 个裸 LF（本仓的 .ps1 一律 CRLF）"
    assert crlf > 100, f"tunnel.ps1 只有 {crlf} 行，可能不是一个完整的脚本"
    body.decode("utf-8")

    for sibling in (SERVE_PS1, TRIAL_PS1):
        raw_sibling = sibling.read_bytes()
        assert raw_sibling[:3] == b"\xef\xbb\xbf", sibling
        assert raw_sibling[3:].count(b"\n") == raw_sibling[3:].count(b"\r\n"), sibling


# ===========================================================================
# ② 它**不是**第二个服务器启动器；健康检查打不通就报一句人话
# ===========================================================================


def test_tunnel_ps1_health_checks_the_local_port_and_refuses_to_start_a_second_server():
    """第 ③ 步**先健康检查那个本地端口**，打不通就报一句人话、退出非 0，⚠️ 而不自己起服务。

    ⚠️ 六拍，每拍各挡一档（红绿两侧都在场，硬规矩 #50）：
    ① 它轮询的是 ``/api/health``（不是「端口上有没有 listener」——那一档会把
       「起在那个端口上的是别的东西」判成「服务在跑」）；
    ② 打不通时**退出非 0**（``exit 1``），⚠️ 而不是安静地继续开隧道；
    ③ 那句**人话**逐字在场：先跑 ``trial.ps1 -Port <Port> -Reset``，
       公网档还要先设 ``PE_ENV='prod'``；
    ④ 全文**一次都不起 uvicorn**（``uvicorn`` 只许出现在注释/散文里，
       不许出现在语句里）⇒ 「顺手把服务也起了」这一档红；
    ⑤ 它**不灌数据**（``demo_bootstrap`` 一次都不出现在语句里）；
    ⑥ 它**不委托** ``serve.ps1`` / ``trial.ps1`` 去起服务
       （``-File`` 后面跟的一律不是那两个脚本）。
    """
    code = _tunnel_ps1_code()
    statements = _statements()

    # ① 轮询的是 /api/health
    assert '$LocalHealth = "$LocalBase/api/health"' in code, "健康检查的 URL 那一行变了"
    assert "Invoke-WebRequest -Uri $LocalHealth" in statements, "健康检查不再打 /api/health 了"
    # ② 打不通就退出非 0
    assert re.search(r"if \(\$null -eq \$LocalBody\) \{", statements), "健康检查失败那一支不见了"
    failed_branch = statements.split("if ($null -eq $LocalBody) {", 1)[1]
    assert "exit 1" in failed_branch.split("}", 20)[-1] or "exit 1" in failed_branch[:3000], (
        "健康检查失败那一支不再退出非 0（于是服务没起时也照样开隧道，"
        "印给甲方的是一条打到空端口的链接）"
    )
    # ③ 那句人话（⚠️ 派单 §2 第 1 条逐字点名的内容）
    assert "trial.ps1 -Port $Port -Reset" in code, "少了那句人话：先跑 trial.ps1 -Port <Port> -Reset"
    assert "$env:PE_ENV='prod'" in code, "少了那句人话的后半：公网档还要先设 PE_ENV='prod'"
    assert "本脚本**不自己起服务**" in code, "少了「不自己起服务」那一句（它是本条的全部理由）"
    # ④ 一次都不起 uvicorn（⚠️ 判据落在「它是不是被**执行**」上：③ 那一句人话里
    #    逐字**印着**「起 uvicorn 归 scripts\serve.ps1」——那是指着别人说话，
    #    提及不是本身，硬规矩 #109。姿势与下面 ⑨ 那条对 ``netsh`` 的判据同款。）
    for line in statements.splitlines():
        stripped = line.strip()
        if "uvicorn" in stripped:
            assert stripped.startswith("Write-Host"), (
                f"tunnel.ps1 的语句里执行了 uvicorn ⇒ 它成了第二个服务器启动器：{stripped[:160]}"
            )
    # ⑤ 不灌数据（⚠️ ``demo_bootstrap.py`` 那个**名字**会出现在 ⑥ 的第 ② 条告示里
    #    ——那一句是「口令的唯一所有者在哪儿」，是**指着**它说话、不是**调**它。
    #    故判据是「它后面没有跟一次调用」，而不是「这个名字一次都不出现」。）
    assert not re.search(r"demo_bootstrap\.py[^\n\"]*--db-url", statements), (
        "tunnel.ps1 调了 demo_bootstrap.py ⇒ 它成了第二个灌库器"
    )
    assert not re.search(r"python[^\n]*demo_bootstrap", statements), "同上"
    # ⑥ 不委托那两个脚本去起服务
    assert not re.search(r"-File[^\n]*(serve|trial)\.ps1", statements), (
        "tunnel.ps1 委托了 serve.ps1 / trial.ps1 去起服务：本档的判据是「只读那个端口上的服务」"
    )


# ===========================================================================
# ③ 抓到 URL 之后**真发一次请求复核它活着**
# ===========================================================================


def test_the_public_url_is_reverified_over_the_internet_before_it_is_handed_out():
    """「抓到一串字符」≠「那条链接打得开」：④ b 必须**穿过公网**打一次 ``/api/health``。

    ⚠️ 五拍：
    ① 它打的是 ``<公网 URL>/api/health``（而不是本地那一格 —— 本地那一格证明不了
       Cloudflare 的边缘已经把这条隧道接上了）；
    ② 要求 **200**，且**轮询**（quick tunnel 自己就印一句
       "it may take some time to be reachable"，一次就打会假红）；
    ③ 要求响应体的 ``status`` 是 ``ok``；
    ④⚠️ 要求公网那一格的 ``tables`` 与**本地那一格逐字相同** —— 这一拍挡的是
       「隧道打到别的东西上了」（⚠️ 而它刻意**不**写死一个数字：``28`` 的所有者是
       schema，在脚本里敲第二遍就是第二个所有者，改表的人会漏改这里）；
    ⑤ 复核**排在写 URL 文件之前**（顺序是承重的：先写文件再复核的话，
       复核失败会留下一份写着死链接的文件）。
    """
    code = _tunnel_ps1_code()
    statements = _statements()

    # ① 打的是公网那一格
    assert '$RemoteHealthUrl = $PublicUrl.TrimEnd(\'/\') + "/api/health"' in code, (
        "公网存活探针的 URL 那一行变了"
    )
    assert "Invoke-WebRequest -Uri $RemoteHealthUrl" in statements, "④ b 不再穿过公网打 /api/health 了"
    # ② 要 200，且轮询
    assert "if ($RemoteStatus -eq 200) { $RemoteBody = $Remote.Content; break }" in statements, (
        "④ b 不再要求 200（或不再轮询）"
    )
    assert "while ((Get-Date) -lt $ReachDeadline)" in statements, "④ b 的那一轮轮询不见了"
    # ③ status 必须是 ok
    assert "if ($RemoteObject.status -ne 'ok') {" in statements, "④ b 不再核 status == ok"
    # ④ tables 与本地那一格**逐字相同**（⚠️ 而不是写死一个数字）
    assert "[string]$RemoteObject.tables -ne [string]$LocalHealthObject.tables" in statements, (
        "④ b 不再把公网那一格的 tables 与本地那一格比 ⇒ 「隧道打到别的东西上」这一档静默通过"
    )
    assert not re.search(r"tables\D{0,6}28", statements), (
        "④ b 里写死了一个 28：那个数的所有者是 schema（/api/health 现场答的那一格），"
        "在本文件里敲第二遍就是第二个所有者"
    )
    # 复核不通过时**throw**（不是打印一句 ⚠️ 就继续）
    assert statements.count("throw (\"穿过公网打不通") == 1, "④ b 打不通时不再 throw"
    # ⑤ 顺序：复核在写 URL 文件之前
    reverify_at = statements.index("-- ④ b 复核这条公网 URL 真的活着")
    write_at = statements.index("[System.IO.File]::WriteAllText($UrlFile")
    assert reverify_at < write_at, "写 URL 文件排在了复核之前 ⇒ 复核失败会留下一份写着死链接的文件"


# ===========================================================================
# ④ 抓 URL 的正则：一个所有者，而它**不宽松**（本条有一拍行为取证）
# ===========================================================================


def test_the_url_regex_has_one_owner_and_picks_the_tunnel_not_the_disclaimer():
    """抓 URL 的正则**只有一处**，而它抓到的是隧道地址、不是免责声明里的条款链接。

    ⚠️ 四拍（前三拍是文本、第四拍是**行为**；红绿两侧都在场）：
    ① ``$TunnelUrlPattern`` 在全文件里**恰好赋值一次**（单一所有者），
       而抓 URL 的那个函数用的就是它（不是就地又敲了一遍正则）；
    ② 它**同时**认两家的形状（``trycloudflare.com`` = cloudflared 的 quick tunnel、
       ``lhr.life`` = localhost.run），因为后端有两个而正则只有一个住址；
    ③ 它**不是**宽松的 ``https://\\S+`` 一类；
    ④⚠️ **行为取证**：把 ① 那条正则从文件里读出来、拿一份**本机实测抓到的**
       cloudflared 日志喂它（那一份的第一行里就有两条 ``https://…cloudflare.com/…``
       的条款/文档链接，而隧道地址在第 5 行），断言它抓到的是 ``trycloudflare.com``
       那一条；再断言一条**宽松**正则在同一份输入上会抓错
       （⇒ ③ 那一拍不是洁癖，而「抓错」的样子是把 Cloudflare 的条款页印给甲方）。
    """
    code = _tunnel_ps1_code()
    statements = _statements()

    # ① 恰好一次赋值，而抓 URL 的函数用的就是那个变量
    assignments = re.findall(r"^\$TunnelUrlPattern = '([^']+)'$", code, re.M)
    assert len(assignments) == 1, (
        f"$TunnelUrlPattern 被赋值了 {len(assignments)} 次（要恰好 1 次 = 单一所有者）"
    )
    pattern = assignments[0]
    assert "[regex]::Match($All, $TunnelUrlPattern)" in code, (
        "抓 URL 的那个函数不再用 $TunnelUrlPattern（就地又敲了一遍正则 = 第二个所有者）"
    )
    # ⚠️ 数的是**语句**（3 = 一次赋值、一次 Match、一次打印给运维看）。
    #    注释里另有两处**提及**它（那是散文，提及不是本身，硬规矩 #109）。
    assert statements.count("$TunnelUrlPattern") == 3, (
        f"$TunnelUrlPattern 在语句里出现了 {statements.count('$TunnelUrlPattern')} 次"
        "（期望 3：一次赋值、一次 Match、一次打印给运维看）"
    )
    # ② 两家的形状都在
    assert "trycloudflare" in pattern and "lhr.life" in pattern.replace("\\.", "."), pattern
    # ③ 不宽松（⚠️ 判据落在**语句**上：注释里逐字**引用**了那条被否掉的宽正则
    #    作为理由，而提及不是本身）
    assert r"https://\S+" not in statements, "正则被放宽成 https://\\S+ 了"
    assert pattern.startswith("https://[a-z0-9]"), pattern

    # ④ 行为取证。⚠️ 输入是**本机实测**抓到的那份日志的前 6 行（形状逐字照抄：
    #    第 1 行的免责声明里含两条 cloudflare.com 的链接，隧道地址在第 5 行的横幅里、
    #    后面还跟着一串补齐横幅宽度的空格）。
    sample = "\n".join([
        '2026-10-15T09:25:56Z INF Thank you for trying Cloudflare Tunnel. Doing so, without a '
        'Cloudflare account, is a quick way to experiment and try it out. However, be aware that '
        'these account-less Tunnels have no uptime guarantee, are subject to the Cloudflare Online '
        'Services Terms of Use (https://www.cloudflare.com/website-terms/), and Cloudflare reserves '
        'the right to investigate your use of Tunnels for violations of such terms. If you intend to '
        'use Tunnels in production you should use a pre-created named tunnel by following: '
        'https://developers.cloudflare.com/cloudflare-one/connections/connect-apps',
        "2026-10-15T09:25:56Z INF Requesting new quick Tunnel on trycloudflare.com...",
        "2026-10-15T09:25:59Z INF +-------------------------------+",
        "2026-10-15T09:25:59Z INF |  Your quick Tunnel has been created!  |",
        "2026-10-15T09:25:59Z INF |  https://assume-val-recording-studying.trycloudflare.com       |",
        "2026-10-15T09:25:59Z INF +-------------------------------+",
    ])
    got = re.search(pattern, sample)
    assert got is not None, "本文件的正则在一份**实测**日志上什么都没抓到"
    assert got.group(0) == "https://assume-val-recording-studying.trycloudflare.com", got.group(0)
    # ⚠️ 红档半边：一条宽松正则在**同一份输入**上会抓到条款链接（= 印给甲方一个打不开的地址）
    loose = re.search(r"https://\S+", sample)
    assert loose is not None and "cloudflare.com/website-terms" in loose.group(0), (
        "「宽松正则会抓错」这一档不再成立 ⇒ ③ 那一拍失去了它的红档半边"
    )
    # ⚠️ 而 localhost.run 那一家的形状也认
    assert re.search(pattern, "** https://abcd1234.lhr.life **") is not None, pattern


# ===========================================================================
# ⑤ URL 文件的路径：一个所有者，而 .gitignore 与它不许漂开
# ===========================================================================


def test_the_url_file_path_has_one_owner_and_gitignore_agrees():
    """``.trial/public-url.txt`` 这个路径：``tunnel.ps1`` 是所有者，``.gitignore`` 逐字同意它。

    ⚠️ 四拍（⚠️ 三侧不同源：一侧是脚本、一侧是 ``.gitignore``、第三侧是 git 自己）：
    ① 脚本里 ``$UrlFile`` 由 ``$TrialDir`` + ``public-url.txt`` 拼出来，
       而 ``$TrialDir`` 是仓库根下的 ``.trial``；⚠️ 那个文件名在**语句**里恰好出现
       **一次**（就是拼路径那一次）。⚠️ 判据刻意落在语句上、不落在整个代码段上
       （Plan 07 Task 4 改的）：散文里**提及**那个路径不是「第二份路径」
       （硬规矩 #109），而按整个代码段数的话，下一个人每写一句解释就会被本条红一次，
       而他唯一的出路是**删掉那句解释** —— 那一格与本仓各波反复踩的
       「守卫红在自己的说明文字上」同族；
    ② ``.gitignore`` 里有 ``.trial/`` 那一行；
    ③ ``git check-ignore`` 说那个路径**真的**被忽略（②③ 两侧不同源：
       一行文本 vs git 自己的判定）；
    ④ 而它**没有被入库**（``git ls-files`` 底下空）。
    """
    code = _tunnel_ps1_code()
    statements = _statements()
    assert '$TrialDir = Join-Path $RepoRoot ".trial"' in code, ".trial 那个目录名变了"
    assert '$UrlFile = Join-Path $TrialDir "public-url.txt"' in code, "URL 文件名的那一行变了"
    assert statements.count("public-url.txt") == 1, (
        f"public-url.txt 在**语句**里出现了 {statements.count('public-url.txt')} 次"
        "（期望 1 = 拼路径那一次；散文里的提及不算，理由见上面 ① 那一段）"
    )
    # ⚠️ 反空转：那个文件名在**代码段**里确实还被提及过（否则上面那一拍可能只是
    #    因为切法失效、把整个代码段都切没了）。
    assert code.count("public-url.txt") > statements.count("public-url.txt")

    ignored_lines = {
        line.strip() for line in GITIGNORE.read_bytes().decode("utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    for entry in IGNORED_DIRS:
        assert entry in ignored_lines, f".gitignore 里少了 {entry!r}"

    checked = _git("check-ignore", "-v", URL_FILE_RELATIVE, "tools/cloudflared.exe")
    assert ".trial/" in checked and "tools/" in checked, checked
    assert _git("ls-files", "--", ".trial", "tools").strip() == "", (
        ".trial/ 或 tools/ 下有文件被入库了（一条公网可达的临时地址 / 一个 55 MB 的二进制"
        "进了 git 历史，而历史删不掉）"
    )


# ===========================================================================
# ⑥ 六条风险告示：各在无歧义串上钉住
# ===========================================================================


def test_the_six_public_exposure_warnings_are_each_pinned_on_an_unambiguous_string():
    """六条风险告示**一条都不许少**（派单 §2 第 4 条）。

    ⚠️ 三拍：
    ① 六条各自的无歧义串都在**语句**里（⚠️ 不是注释里 —— 提及不是本身）；
    ② 那一段是**打印**出来的（六条一律住在 ``Write-Host`` 行里）；
    ③ 反空转：那一段的小节标题在场，且六条各只出现一次
       （少了 ③ 的话，「把六条挪进注释」与「删掉一条」在颜色上无法区分）。
    ⚠️ 而 ② ③ 两条**同时**指向 spec：抢绑是 §1.2 第 4 条、读操作不留审计是
    §1.2 第 14 条 / §13.9 —— 那两条不是本波新发明的风险，是 spec 里已经念过的。
    """
    statements = _statements()
    assert "-- ⑥ ⚠️⚠️⚠️ 公网暴露的风险告示" in statements, "⑥ 那一段的小节标题不见了"
    for needle in SIX_WARNINGS:
        hits = [line for line in statements.splitlines() if needle in line]
        assert len(hits) == 1, f"风险告示 {needle!r} 在语句里出现了 {len(hits)} 次（要恰好 1 次）"
        assert hits[0].lstrip().startswith("Write-Host"), (
            f"风险告示 {needle!r} 不在一条 Write-Host 里 ⇒ 它不会被打印出来"
        )
    # ⚠️ 那两条指向 spec 的告示必须**点名** spec（交付现场要能顺着查到原文）
    assert "spec §1.2 第 4 条" in statements, "抢绑那一条不再点名 spec §1.2 第 4 条"
    assert "spec §1.2 第 14 条 / §13.9" in statements, "读审计那一条不再点名 spec §1.2 第 14 条 / §13.9"
    # ⚠️ ⑥ 那一格：链接寿命那一条要说清「重开会变」（派单 §2 第 3 条点名的一句）
    assert "全新的随机地址" in statements, "「重开会变」那一句不见了"


# ===========================================================================
# ⑦ 档位矩阵：公网 = prod、局域网 = dev，而两处打印是**两段不同的话**
# ===========================================================================


def test_the_public_tier_hint_and_the_lan_tier_hint_are_two_different_passages():
    """公网档与局域网档的档位提示是**两段不同的话**，而两段的**理由**都写在注释里。

    ⚠️ 派单 §4 第 ③ 条逐字点名的一格。四拍（⚠️ 两侧不同源：一侧是 ``tunnel.ps1``、
    一侧是 ``serve.ps1``）：
    ① ``tunnel.ps1`` 里那句独有的话在场，而它**不在** ``serve.ps1`` 里；
    ② ``serve.ps1`` 的 ``-Lan`` 那一段里那句独有的话在场，而它**不在** ``tunnel.ps1`` 里
       （⚠️ 少了这一拍，「两处抄成同一段」与「两处各说各的」在颜色上无法区分）；
    ③ 两边的**理由**都在：公网那一侧说「边缘是 HTTPS」、局域网那一侧说「明文 http」，
       而两侧都点名 spec §13.11.3（那条论证的唯一住址）；
    ④ ``tunnel.ps1`` **不设** ``PE_ENV``（档位是部署事实、归运维的环境变量），
       而在实测到 ``dev`` 时**只打印、不 throw**（dev 在隧道下也能登，是一档可用的退路）。
    """
    tunnel = TUNNEL_PS1.read_bytes()[3:].decode("utf-8")
    serve = SERVE_PS1.read_bytes()[3:].decode("utf-8")

    # ① / ②
    assert PUBLIC_TIER_NEEDLE in tunnel, "tunnel.ps1 里那句公网档独有的话不见了"
    assert PUBLIC_TIER_NEEDLE not in serve, "serve.ps1 里出现了公网档那句话 ⇒ 两处抄成了同一段"
    assert LAN_TIER_NEEDLE in serve, "serve.ps1 的 -Lan 那一段里那句独有的话不见了"
    assert LAN_TIER_NEEDLE not in tunnel, "tunnel.ps1 里出现了 -Lan 那句话 ⇒ 两处抄成了同一段"

    # ③ 两边的理由 + 同一条 spec 出处
    assert "边缘是 HTTPS" in tunnel, "公网档的理由（边缘是 HTTPS）不在 tunnel.ps1 里"
    assert "明文 http" in serve, "局域网档的理由（明文 http）不在 serve.ps1 里"
    assert "§13.11.3" in tunnel and "§13.11.3" in serve, "两侧都要点名 spec §13.11.3"
    assert "登录 200、下一个请求 401" in tunnel and "登录 200、下一个请求 401" in serve, (
        "「症状」那一句两侧都要有（它是这条裁定唯一能被运维**看见**的后果）"
    )

    # ④ 不设 PE_ENV，而 dev 那一档只打印不 throw
    statements = _statements()
    # ⚠️ 判据是「没有任何一行**以它开头**」（= 一次赋值），而不是「全文不含
    #    ``$env:PE_ENV=``」：③ 那一句人话里逐字**印着** ``$env:PE_ENV='prod'``
    #    （那是叫**运维**去设它，不是本脚本替他设），按全文判会红在自己身上。
    assert not any(
        line.strip().startswith("$env:PE_ENV") for line in statements.splitlines()
    ), (
        "tunnel.ps1 自己设了 PE_ENV：档位是**部署事实**、归运维的环境变量"
        "（与 serve.ps1 刻意没有 -Prod 开关同一条理由）"
    )
    assert "elseif ($Tier -eq 'dev') {" in statements, "dev 那一档的提示不见了"
    # ⚠️ 只切到那一档**自己的**收尾大括号为止：后面紧跟的就是 ④ 那一段，
    #    而它里面有真的 ``throw``（拿不到 URL / 复核不通都要 throw），
    #    按「往后 2000 字符」切会红在别人的 throw 上。
    dev_lines: list[str] = []
    for line in statements.split("elseif ($Tier -eq 'dev') {", 1)[1].splitlines():
        if line.strip() == "}":
            break
        dev_lines.append(line)
    assert dev_lines, "dev 那一档里一句打印都没有了"
    # ⚠️ 判据是「有没有一行**以 throw 开头**」（= 一次真的 throw 语句），
    #    而不是「文本里含不含 throw 这个词」：那一档的散文里逐字写着
    #    「故它是一档可用的退路、本脚本不 throw」——提及不是本身（硬规矩 #109）。
    assert not any(line.strip().startswith("throw") for line in dev_lines), (
        "dev 那一档改成了 throw（它是一档**可用的退路**，本波用真浏览器实测过：\n"
        "HTTPS 页面上收一张非 Secure 的 cookie 是允许的，故 dev 在隧道下也能登）"
    )
    assert any("也能登" in line for line in dev_lines), (
        "dev 那一档要说清「也能登」（否则运维会以为它坏了、去改一档本来能用的退路）"
    )


# ===========================================================================
# ⑧ 口令与学号：一个都不许抄（唯一所有者是 demo_bootstrap.py）
# ===========================================================================


def test_tunnel_ps1_does_not_become_a_second_owner_of_the_demo_credentials():
    """演示口令与学号**一个都不许抄**在这里。

    ⚠️ 姿势与 ``tests/test_trial.py`` 的
    ``test_trial_ps1_does_not_become_a_second_owner_of_the_demo_credentials``
    逐字同款（扫**整个文件**，含注释：一份抄在注释里的口令同样是要念给甲方听的那一份）。
    ⚠️ 而本文件比那一条**多一拍**：公网档是三条链接里唯一一条
    「任何知道地址的人都能打开」的，故它必须**打印**一句「口令是公开的」
    （⑥ 的第 ② 条）—— 指着唯一所有者说，而不是把口令抄一遍。
    """
    whole = TUNNEL_PS1.read_bytes()[3:].decode("utf-8")
    for needle in ("pe-demo-2025", "DEMO_PASSWORD ="):
        assert needle not in whole, f"tunnel.ps1 里抄了一份 {needle!r}"
    assert re.search(r"\b20\d{8}\b", whole) is None, (
        "tunnel.ps1 里抄了一个学号形状的字面量：名册由 app/seed/population.py 现造，"
        "而 demo.ps1 曾因为抄了一个从来不在册的学号把演示带进 403（Plan 06 终审 I1）"
    )
    # ⚠️ 多出来的那一拍：指着唯一所有者说
    assert "demo_bootstrap.py" in whole and "DEMO_PASSWORD" in whole, (
        "⑥ 的第 ② 条不再点名唯一所有者（backend/scripts/demo_bootstrap.py 的 DEMO_PASSWORD）"
    )


# ===========================================================================
# ⑨ 防火墙：隧道是**出站**连接，故一次都不碰（连 netsh 都不打印）
# ===========================================================================


def test_tunnel_ps1_never_touches_the_firewall_because_a_tunnel_is_outbound_only():
    """``netsh`` **只许出现在打印行里**，而本文件连打印都不打印它。

    ⚠️ 三拍：
    ① 语句里**一次都不执行** ``netsh``（派单 §4 第 ① 条：``netsh`` / ``cloudflared``
       只出现在打印行里而不自动执行 —— 静默提权不是交付物该有的形状）；
    ②⚠️ 而本文件比 ``serve.ps1 -Lan`` 那一档**更进一步**：连一条 ``netsh`` 命令都
       不打印。理由是实测的：隧道是一条**出站**连接（``cloudflared`` 主动拨到
       Cloudflare 的边缘，走 443 / QUIC），Windows 的防火墙缺省就放行出站，
       故**不需要任何入站规则**；而 ``-Lan`` 那一档要让别的机器**连进来**，
       那才需要一条入站放行；
    ③ 那一句「为什么不碰」在场（少了它，下一个人会以为这一格是漏掉的）。
    """
    statements = _statements()
    whole = TUNNEL_PS1.read_bytes()[3:].decode("utf-8")

    # ① 一次都不执行
    for line in statements.splitlines():
        stripped = line.strip()
        if "netsh" in stripped:
            assert stripped.startswith("Write-Host"), (
                f"netsh 出现在一条非打印的语句里：{stripped[:160]}"
            )
    # ② 而它连打印都不打印（⚠️ 只在**注释与散文**里提到，用于解释为什么）
    assert "netsh advfirewall firewall add rule" not in whole, (
        "tunnel.ps1 打印了一条入站放行命令：隧道是**出站**连接，不需要它"
        "（而打印一条运维其实不该跑的命令，比不打印更坏）"
    )
    # ③ 那一句「为什么不碰」
    assert "本脚本**一次都不碰**" in statements, "少了「本脚本一次都不碰防火墙」那一句"
    assert "**出站**连接" in statements, "少了「隧道是一条出站连接」那个理由"


# ===========================================================================
# ⑩ 孤儿清理：只杀**自己留下的**那一些（宁可漏杀不可误杀）
# ===========================================================================


def test_the_orphan_cleanup_only_kills_processes_that_carry_this_scripts_own_marker():
    """第 ① 步的判据是**两条同时成立**，而「只按进程名杀」这一档红。

    ⚠️ 派单 §2 第 5 条逐字点名的那一格（Task 1+2 登记过「进程被工具硬杀时 ``finally``
    跑不到」；本波**实测**过：硬杀掉 ``tunnel.ps1`` 那个 powershell 之后，
    ``cloudflared`` 作为孤儿**活着**、``.trial/public-url.txt`` 也留着）。
    五拍：
    ① 标记是 ``pe_tunnel_<Port>``（按端口分，于是两个端口上的两轮互不相干）；
    ② 判据的**第一条**是进程名（``cloudflared.exe`` / ``ssh.exe``）；
    ③ 判据的**第二条**是命令行里含那个标记，⚠️ 而两条是 ``-and`` 关系；
    ④⚠️ 红档半边：全文**没有**一处按进程名裸杀（``Stop-Process -Name cloudflared``
       一类）—— 那会杀掉甲方 IT 自己在跑的 named tunnel；
    ⑤ 杀之前**先打印**它是谁（PID + 完整命令行）⇒ 一次误杀是**看得见**的，
       而不是安静地少了一个进程。
    """
    code = _tunnel_ps1_code()
    statements = _statements()

    # ① 标记
    assert '$LogDirName = "pe_tunnel_$Port"' in code, "孤儿判据的标记变了（它同时是日志目录名）"
    # ② 第一条：进程名（⚠️ 在 WQL 的 -Filter 里，不是在 PowerShell 侧过滤）
    assert """-Filter "Name='cloudflared.exe' OR Name='ssh.exe'\"""" in statements, (
        "孤儿清理不再按进程名收窄 ⇒ 它会枚举本机全部进程再在 PowerShell 侧筛"
    )
    # ③ 第二条：命令行含标记，而两条是 -and
    assert re.search(
        r"Where-Object \{ \$_\.CommandLine -and \$_\.CommandLine\.Contains\(\$LogDirName\) \}",
        statements,
    ), "孤儿清理的第二条判据（命令行里含本脚本自己的标记）不见了"
    # ④ 红档半边：不许按进程名裸杀
    assert not re.search(r"Stop-Process\s+-Name", statements), (
        "出现了 Stop-Process -Name …：那是**按进程名裸杀**，会杀掉别人在跑的隧道"
    )
    assert "Get-Process cloudflared" not in statements, "出现了按名字取 cloudflared 的写法"
    # ⑤ 杀之前先打印它是谁
    orphan_block = statements.split("-- ① 上一轮留下的孤儿隧道进程", 1)[1]
    orphan_block = orphan_block.split("-- ② 后端", 1)[0]
    print_at = orphan_block.index('"     PID "')
    kill_at = orphan_block.index("Stop-Process -Id $Orphan.ProcessId")
    assert print_at < kill_at, "杀之前没有先打印它是谁（一次误杀就变成静默的了）"
    assert '$Orphan.CommandLine' in orphan_block, "打印里没有完整命令行（判据是不是命中就看不出来了）"
    # ⚠️ 而两个后端都要**带上**那个标记（否则判据对 ssh 那一支恒不命中 = 漏杀）
    # ⚠️ 判的是**带引号的那一个变量**（``$QuotedLogFile`` / ``$QuotedSshDebugFile``），
    #    不是原始路径：Plan 07 Task 7 起那两个元素**自带引号**（与 serve.ps1 的 S1-1 同族：
    #    ``Start-Process -ArgumentList <数组>`` 不给含空格的元素加引号，而这两个路径都落在
    #    ``$env:TEMP`` 下 ⇒ **用户名带空格**的机器上会被切开）。
    #    ⚠️ 而「标记还在不在」由下面那两条钉住：引号是**加在整个值外面**的，
    #    故 ``pe_tunnel_<Port>`` 一个字都没变（第 ① 步的孤儿判据读的就是命令行）。
    assert "'--logfile', $QuotedLogFile" in code, (
        "cloudflared 的 --logfile 不见了、或没有走那个自带引号的变量（它是标记的落脚点之一）"
    )
    assert "'-E', $QuotedSshDebugFile" in code, (
        "ssh 的 -E 不见了、或没有走那个自带引号的变量（它是标记的落脚点之一）"
    )
    assert "'--logfile', $LogFile" not in code, "--logfile 还在用未加引号的原始路径"
    assert "'-E', $SshDebugFile" not in code, "-E 还在用未加引号的原始路径"


# ===========================================================================
# ⑪ 后端选择：一个所有者，两个后端都在它里面
# ===========================================================================


def test_the_backend_choice_has_one_owner_and_auto_prefers_cloudflared():
    """「用哪个后端 / 怎么起它 / 从哪一份日志里抓 URL」只在一个函数里决定一次。

    ⚠️ 派单 §1 的控制者裁定（``-Backend cloudflared|ssh``，缺省自动探测：
    先找 cloudflared，找不到再用 ssh）。五拍：
    ① 参数面恰好两个（``-Port`` 缺省 **8030** 与 ``trial.ps1`` 对齐、``-Backend``），
       而 ``-Backend`` 的取值被 ``ValidateSet`` 收窄成三个；
    ② 那**一个函数**在场，而两个后端的参数表都住在它里面；
    ③ ``auto`` 的顺序是 cloudflared 先、ssh 后；
    ④ cloudflared 的找法是三档（``PATH`` → 本仓 ``tools\\`` → winget 的 ``Links``），
       ⚠️ 而本仓那一份的路径**逐字**是 ``tools\\cloudflared.exe``
       （它与 ``.gitignore`` 的 ``tools/`` 那一行不许漂开）；
    ⑤ ssh 那一支有一道**前置 TCP 探测**，⚠️ 探测不过就退出非 0
       （本机实测 ``localhost.run:22`` 的握手会挂住 30 秒以上而零输出，
       连 ``ConnectTimeout`` 都不触发；没有这一道，运维会盯着一个空屏幕等一分半）。
    """
    code = _tunnel_ps1_code()
    statements = _statements()

    # ① 参数面
    assert "[int]$Port = 8030," in code, f"缺省端口不是 {TUNNEL_PORT}（要与 trial.ps1 对齐）"
    assert "[ValidateSet('auto', 'cloudflared', 'ssh')]" in code, "-Backend 的取值没有被 ValidateSet 收窄"
    assert "[string]$Backend = 'auto'" in code, "-Backend 的缺省不是 auto（= 自动探测）"
    assert not re.search(r"^\s*\[switch\]\$", code, re.M), "tunnel.ps1 多了一个开关参数（参数面只有两个）"
    # 与 trial.ps1 的缺省**对齐**（⚠️ 两侧不同源：读的是另一个文件）
    trial_code = TRIAL_PS1.read_bytes()[3:].decode("utf-8")
    assert f"[int]$Port = {TUNNEL_PORT}," in trial_code, (
        "trial.ps1 的缺省端口变了 ⇒ 本条①那一句「对齐」的判据要跟着改"
    )

    # ② 一个函数，两个后端都在里面
    assert code.count("function Resolve-TunnelBackend") == 1, "后端解析不再只有一个住址"
    resolver = code.split("function Resolve-TunnelBackend", 1)[1].split("\n$Tunnel = Resolve-TunnelBackend", 1)[0]
    for needle in ("'tunnel', '--url', $LocalBase", "'nokey@localhost.run'"):
        assert needle in resolver, f"{needle!r} 不在那个函数里 ⇒ 后端选择有了第二个所有者"
    assert "Resolve-TunnelBackend -Requested $Backend" in statements, "那个函数没有被调用"

    # ③ auto 的顺序
    auto_at = resolver.index("if ($Chosen -eq 'auto')")
    assert resolver.index("$CloudflaredExe") < auto_at < resolver.index("$Chosen = 'ssh'"), (
        "auto 的顺序不是「先 cloudflared、再 ssh」"
    )
    # ④ cloudflared 的三档找法
    assert '(Get-Command cloudflared -ErrorAction SilentlyContinue).Source' in resolver, "PATH 那一档不见了"
    assert '(Join-Path $RepoRoot "tools\\cloudflared.exe")' in resolver, (
        "本仓 tools\\cloudflared.exe 那一档不见了（它与 .gitignore 的 tools/ 不许漂开）"
    )
    assert "Microsoft\\WinGet\\Links\\cloudflared.exe" in resolver, "winget 的 Links 那一档不见了"

    # ⑤ ssh 的前置探测
    assert "if ($Tunnel.Name -eq 'ssh') {" in statements, "ssh 那一支的前置探测不见了"
    ssh_probe = statements.split("if ($Tunnel.Name -eq 'ssh') {", 1)[1][:2500]
    assert "ConnectAsync('localhost.run', 22)" in ssh_probe, "前置探测不再连 localhost.run:22"
    assert "exit 1" in ssh_probe, "前置探测不过时不再退出非 0（于是运维会盯着一个空屏幕等）"


# ===========================================================================
# ⑫ finally：杀掉隧道进程 + 复核归零 + 复核本地服务**没被带走**
# ===========================================================================


def test_the_tunnel_process_is_killed_in_finally_and_the_local_service_survives_it():
    """``finally`` 那一段兜住隧道进程，并**复核**两件相反方向的事。

    ⚠️ 五拍：
    ① ``finally`` 里杀掉隧道进程（Ctrl-C / throw / 任何一条异常路径都不该留下
       一个**开着公网入口**的孤儿）；
    ② 杀完**复核归零**（用与第 ① 步**同一条**判据再数一次，⚠️ 不是「杀了就算」）；
    ③⚠️ 而它**同时**复核本地服务还活着 —— 方向相反的一格：隧道死了**不该**带走服务
       （那正是本脚本与 ``trial.ps1`` 分成两个所有者的理由：运维要能「只重开隧道、
       不动服务」）；
    ④ URL 文件在 ``finally`` 里被**删掉**（那条链接已经失效，留一份写着死链接的文件
       比没有文件更坏 —— 下一个人会照着它去点）；
    ⑤ 隧道日志**刻意留着**（它是「隧道为什么失败」的唯一现场），而它按端口命名、
       每次跑本脚本时自己清空，故不会累积。
    """
    statements = _statements()
    assert "} finally {" in statements, "finally 那一段不见了"
    finally_block = statements.split("} finally {", 1)[1]

    # ① 杀
    assert "Stop-Process -Id $Proc.Id -Force" in finally_block, "finally 里不再杀隧道进程"
    # ② 复核归零（同一条判据）
    assert """-Filter "Name='cloudflared.exe' OR Name='ssh.exe'\"""" in finally_block, (
        "finally 里的归零复核不再用与第 ① 步同一条判据"
    )
    assert "$_.CommandLine.Contains($LogDirName)" in finally_block, "归零复核的标记判据不见了"
    assert "复核 · 隧道进程归零" in finally_block, "归零复核不再**打印**（于是它是不是真跑了看不出来）"
    # ③ 本地服务还活着
    assert "Invoke-WebRequest -Uri $LocalHealth" in finally_block, (
        "finally 不再复核本地服务 ⇒ 「隧道死了带走服务」这一档静默通过"
    )
    assert "复核 · 本地服务" in finally_block, "本地服务那一格的复核不再打印"
    # ④ URL 文件删掉
    assert "Remove-Item $UrlFile -Force" in finally_block, "finally 不再删 URL 文件（留下一份死链接）"
    # ⑤ 日志留着（⚠️ 红档半边：它**不许**被删）
    assert "Remove-Item $LogDir" not in finally_block, (
        "finally 把隧道日志目录也删了：那是「隧道为什么失败」的唯一现场"
    )
    assert "隧道日志留着" in finally_block, "「日志刻意留着」那一句不见了（下一个人会以为是漏掉的）"


# ===========================================================================
# ⑬ cloudflared 是**本机工具**，一个 manifest 都不许进
# ===========================================================================


def test_cloudflared_is_a_machine_tool_and_never_enters_a_manifest():
    """``cloudflared`` 在两份 manifest 里**一个字都不出现**（派单 §5 / 计划 §7）。

    ⚠️ 三拍：
    ① ``backend/pyproject.toml`` 里没有它；
    ② ``frontend/package.json`` 里没有它；
    ③ 反空转：那两份文件**确实被读到了**（``pyproject.toml`` 里有 ``fastapi``、
       ``package.json`` 里有 ``vue``）—— 少了这一拍，「路径指错、读到一份空文件」
       与「干净」在颜色上无法区分。
    ⚠️ 理由是分类的：它是「运维那台机器上的一个可执行文件」（与 python / node 同级），
    不是「这个项目的依赖」（与 fastapi / vue 同级）。⚠️ 而本波**新增依赖 = 后端 0、前端 0**。
    """
    pyproject = PYPROJECT.read_bytes().decode("utf-8")
    package = PACKAGE_JSON.read_bytes().decode("utf-8")
    for name, text in (("pyproject.toml", pyproject), ("package.json", package)):
        assert "cloudflared" not in text.lower(), f"{name} 里出现了 cloudflared"
        assert "ngrok" not in text.lower() and "localhost.run" not in text.lower(), name
    # ③ 反空转
    assert "fastapi" in pyproject.lower(), "pyproject.toml 读错了（里面应当有 fastapi）"
    assert '"vue"' in package, "package.json 读错了（里面应当有 vue）"
# ===========================================================================
# ⑨ Plan 07 Task 4：``-Protocol`` 三档 + HTTP 530 判据 + ``-Watchdog``
# ===========================================================================
#
# ⚠️ 这一组守卫是**运维实证带出来的**（控制者 2026-10-15 亲验）：第一条隧道用缺省
#    协议跑了约 3 小时之后，本机到 Cloudflare 边缘的 **UDP 路径断了**，隧道进程从此
#    一路 ``failed to dial to edge with quic: timeout`` + 指数退避而**不退**，
#    那条公网 URL 于是回 **HTTP 530**（响应体 17 字节的 ``error code: 1033``）。
#    ⚠️ 那是最坏的失效形态：**进程在、链接死**，而改前的脚本对这一档没有任何自检。


#: ``-Protocol`` 的三档。⚠️ **字面量**（硬规矩 #35）：期望侧不从被测脚本读回来跟自己比。
PROTOCOLS = ("auto", "quic", "http2")

#: Cloudflare 边缘在「隧道到不了源站」时回的那一档状态码。⚠️ 字面量。
EDGE_DEAD_STATUS = 530

#: 控制者在真死链上量到的那 17 字节响应体（⚠️ 它只该出现在**给人看的话**里，
#: 判据落在状态码上 —— ``Invoke-WebRequest`` 抛出来时响应流已经被它消费过了，
#: 本波实测 ``GetResponseStream()`` 读回来是 0 字节）。
EDGE_DEAD_BODY = "error code: 1033"


def _tunnel_ps1_help() -> str:
    """``tunnel.ps1`` 的 **comment-based help** 那一段（``#>`` **之前**）。

    ⚠️ 与 :func:`_tunnel_ps1_code` 互补：那一个切代码段，本函数切说明段。
    ``.DESCRIPTION`` / ``.PARAMETER`` 住在这一侧，而派单要求「把为什么缺省是
    这一档写进 ``.DESCRIPTION``」⇒ 判据必须落在这一侧。
    """
    raw = TUNNEL_PS1.read_bytes()
    body = raw[3:].decode("utf-8") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("utf-8")
    assert body.count("#>") == 1
    return body.split("#>", 1)[0]


def _backend_resolver() -> str:
    """把 ``Resolve-TunnelBackend`` 那**一个函数**原样切出来（含 ``function`` 那一行）。

    ⚠️ 切法与 :func:`test_the_backend_choice_has_one_owner_and_auto_prefers_cloudflared`
    逐字相同（两侧不同源：那一拍钉它的**内部顺序**，本处把它**整个跑一遍**）。
    """
    code = _tunnel_ps1_code()
    body = code.split("function Resolve-TunnelBackend", 1)[1]
    body = body.split("\n$Tunnel = Resolve-TunnelBackend", 1)[0]
    return "function Resolve-TunnelBackend" + body


def _run_ps1(snippet: str, tmp_path: pathlib.Path, name: str = "probe.ps1") -> str:
    """把一段 PowerShell 写进 ``tmp_path`` 并跑它，要它的 stdout（⚠️ UTF-8+BOM+CRLF）。

    ⚠️ BOM 是承重的：切出来的那一段里全是中文注释，而 PowerShell 5.1 读一个没有 BOM 的
    ``.ps1`` 时按系统 ANSI 代码页（本机 GBK）解码（姿势与 ``tests/test_serve.py`` 的
    :func:`_run_ps1` 逐字相同）。
    """
    powershell = shutil.which("powershell") or shutil.which("powershell.exe")
    assert powershell, "本机没有 powershell：这一格的可执行判据跑不了"
    path = tmp_path / name
    path.write_bytes(b"\xef\xbb\xbf" +
                     snippet.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
    run = subprocess.run(
        (powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)),
        capture_output=True, check=False,
    )
    out = run.stdout.decode("utf-8", "replace")
    assert run.returncode == 0, (run.returncode, out[-2000:],
                                 run.stderr.decode("utf-8", "replace")[-2000:])
    return out


def test_the_protocol_flag_is_passed_through_verbatim_in_all_three_tiers(tmp_path):
    """``-Protocol`` 的**三档逐个**断言命令行拼装（派单 Task 4 §2.4）。

    ⚠️ 判据是**真的把那个函数跑一遍**、不是读字符串：把 :func:`_backend_resolver`
    切出来，在一个干净的 PowerShell 里定义好它要的那几个脚本级变量，
    然后三档各调一次、断言它返回的 ``Arguments``。⚠️ 两侧不同源：
    期望侧是下面那份**字面量**命令行，被测侧是脚本自己的拼装。

    四拍：

    ① 三档各拼出 ``--protocol <原值>``（⚠️ **原样**传，本脚本不在自己这一层
       再实现一遍「先 quic、N 秒不行就换 http2」—— 那是 cloudflared 自己 ``auto``
       那一档的活；逐字理由见 ``.DESCRIPTION``）；
    ② 三档拼出来的命令行**互不相同**（⚠️ 反空转：若三档都拼成同一条，
       ①那三拍会被同一个串满足三次而全绿）；
    ③ 那个旗标**排在 ``--logfile`` 之前**，而 ``--logfile`` 的值里含本脚本自己的
       标记 ``pe_tunnel_<Port>``（第 ① 步的孤儿清理判据读的就是命令行，
       少一个参数就认不出自己留下的孤儿）；
    ④ ``ssh`` 那一支**一个 ``--protocol`` 都没有**（那是 cloudflared 的旗标，
       ssh 没有同名的；给了 ``-Protocol`` 时脚本打印一段 ⚠️ 说它被忽略）。
    """
    resolver = _backend_resolver()
    snippet = (
        '$ErrorActionPreference = "Stop"\n'
        f'$RepoRoot = "{REPO_ROOT}"\n'
        f'$LocalBase = "http://127.0.0.1:{TUNNEL_PORT}"\n'
        '$LogFile = "C:\\pe-probe\\pe_tunnel_' + str(TUNNEL_PORT) + '\\tunnel.log"\n'
        '$ErrFile = "C:\\pe-probe\\stderr.log"\n'
        '$OutFile = "C:\\pe-probe\\stdout.log"\n'
        '$SshDebugFile = "C:\\pe-probe\\ssh-debug.log"\n'
        + resolver + "\n"
        "foreach ($P in @('auto','quic','http2')) {\n"
        "    $T = Resolve-TunnelBackend -Requested 'cloudflared' -ChosenProtocol $P\n"
        "    Write-Output ('CF|' + $P + '|' + ($T.Arguments -join ' '))\n"
        "}\n"
        "$S = Resolve-TunnelBackend -Requested 'ssh' -ChosenProtocol 'http2'\n"
        "Write-Output ('SSH|http2|' + ($S.Arguments -join ' '))\n"
    )
    rows = {}
    for line in _run_ps1(snippet, tmp_path).splitlines():
        if "|" in line:
            kind, protocol, arguments = line.split("|", 2)
            rows[(kind, protocol)] = arguments
    assert len(rows) == 4, rows

    # ①③
    for protocol in PROTOCOLS:
        arguments = rows[("CF", protocol)]
        assert f"--protocol {protocol}" in arguments, (protocol, arguments)
        assert arguments.startswith(
            f"tunnel --url http://127.0.0.1:{TUNNEL_PORT} --no-autoupdate --protocol {protocol} "
        ), (protocol, arguments)
        assert arguments.index("--protocol") < arguments.index("--logfile"), arguments
        # ⚠️ 那个孤儿标记来自 ``--logfile`` 的**值**（``$LogDir`` 按端口命名），
        #    故本拍的期望侧把它写进了上面那个假的 ``$LogFile``：判的是「加了
        #    ``--protocol`` 之后，``--logfile`` 那一个参数一个都没少」。
        assert f"pe_tunnel_{TUNNEL_PORT}" in arguments, (
            "命令行里那个孤儿标记不见了：第 ① 步的保守清理判据读的就是命令行"
        )
    # ②
    distinct = {rows[("CF", protocol)] for protocol in PROTOCOLS}
    assert len(distinct) == 3, distinct
    # ④
    assert "--protocol" not in rows[("SSH", "http2")], rows[("SSH", "http2")]
    assert "nokey@localhost.run" in rows[("SSH", "http2")]


def test_the_parameter_face_gains_two_values_and_still_has_no_switch():
    """参数面从两个抬到四个，⚠️ 而**一个 ``[switch]`` 都没有**那一格不变。

    ① ``-Protocol`` 被 ``ValidateSet`` 收窄成三档、缺省 ``auto``。
       ⚠️ ``ValidateSet`` 是承重的、不是装饰：本机实测 ``--protocol bogus`` 被
       cloudflared **静默接受**了（它照样开出一条隧道），故拼错一个值不会报错、
       只会得到一档没人知道原因的回落；
    ② ``-Watchdog`` 是 ``[int]``、缺省 **60**（Plan 07 Task 7 · 终审 S3-6 把
       改前那个「缺省 0 = 关」推翻了，逐字理由见 ``.DESCRIPTION`` 里那一节；
       ``0`` 仍然可用 = 显式关掉，⑦ 那一圈的循环体在那一档与改前逐字相同）；
    ③ 那个「参数面上没有开关」的判据由
       :func:`test_the_backend_choice_has_one_owner_and_auto_prefers_cloudflared`
       的 ① 那拍按正则钉住，本条**不重复**它（只把两个新参数的形状钉住）。
    """
    code = _tunnel_ps1_code()
    assert "[ValidateSet('auto', 'quic', 'http2')]" in code, (
        "-Protocol 的取值没有被 ValidateSet 收窄（cloudflared 会静默接受一个拼错的值）"
    )
    assert "[string]$Protocol = 'auto'" in code, "-Protocol 的缺省不是 auto"
    assert "[int]$Watchdog = 60" in code, (
        "-Watchdog 的缺省不是 60：它缺省关掉一个**只报警、不改变任何行为**的自检，"
        "换来的是「与本波之前逐字相同」，而「进程在、链接死」是两波里亲自撞到两次的那一档"
    )
    assert "[int]$Watchdog = 0" not in code, "-Watchdog 的缺省又回到 0（= 关）了"
    # ⚠️ 切 param 块**不能**用「第一个 ``)``」：``[ValidateSet('auto', 'cloudflared', 'ssh')]``
    #    里就有两个。故按「行首那个 ``)``」切（本仓四个 .ps1 的 param 块都是那个形状）。
    match = re.search(r"param\((.*?)^\)", code, re.S | re.M)
    assert match, code[:400]
    block = match.group(1)
    assert sorted(set(re.findall(r"\$(\w+)", block))) == [
        "Backend", "Port", "Protocol", "Watchdog",
    ], block
    assert f"[int]$Port = {TUNNEL_PORT}," in block, block
    assert not re.search(r"^\s*\[switch\]\$", code, re.M)


def test_the_two_logfile_arguments_survive_a_temp_path_with_spaces(tmp_path):
    """``--logfile`` 与 ``-E`` 的值**自带引号**（Plan 07 Task 7 · 终审 S4-11，与 S1-1 同族）。

    病灶与 ``scripts\\serve.ps1`` 的 S1-1 逐字同族：``Start-Process -ArgumentList <数组>``
    把元素**用空格连起来、一个引号都不加**，而这两个日志路径都落在 ``$env:TEMP`` 下 ——
    **Windows 的用户名可以带空格**（``C:\\Users\\张三 李四\\AppData\\Local\\Temp\\…``），
    那一档会把路径切成两截，cloudflared / ssh 于是各收到一个多余的 positional 参数。

    ⚠️ 判据是**真的把那个函数跑一遍**（姿势与
    :func:`test_the_protocol_flag_is_passed_through_verbatim_in_all_three_tiers`
    逐字相同：切出来、在干净 PowerShell 里喂它一个带空格的 ``$LogFile``、断言返回值）。
    两侧不同源：期望侧是下面那几条**字面量**命令行。

    三拍：

    ① 带空格的路径 → 那个元素被一对引号包起来（两个后端各一处）；
    ② 不带空格的路径 → **一个引号都不加**（加了等于凭空改命令行，而
       :func:`test_the_protocol_flag_is_passed_through_verbatim_in_all_three_tiers`
       的 ①③ 两拍按 ``startswith`` 与 ``index`` 钉着它的形状）；
    ③⚠️ **反空转**：把那两个变量换回原始路径（= 改前的行为），①当场对不上
       ⇒ 这一格钉的是**引号**，不是「有一个变量在那儿」。
       ⚠️ 而**孤儿标记 ``pe_tunnel_<Port>`` 在两档里都在**（引号加在整个值外面，
       故第 ① 步那道「命令行里含本脚本自己的标记」的判据一个字都没变）。
    """
    resolver = _backend_resolver()
    # ⚠️ 那两行前导是承重的：``$ErrorActionPreference`` 让一处失败真的红；
    #    ``[Console]::OutputEncoding`` 让 PowerShell 5.1 把 stdout 按 **UTF-8** 写出去
    #    （缺省是 OEM 代码页 = 本机 936，于是①那条含中文的期望值会红在**编码**上、
    #    离真因有一层；``_run_ps1`` 那侧按 utf-8 解码）。
    prefix = (
        '$ErrorActionPreference = "Stop"\n'
        "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)\n"
    )
    tail = (
        "$T = Resolve-TunnelBackend -Requested 'cloudflared' -ChosenProtocol 'http2'\n"
        "Write-Output ('CF|' + ($T.Arguments -join ' '))\n"
        "$S = Resolve-TunnelBackend -Requested 'ssh' -ChosenProtocol 'http2'\n"
        "Write-Output ('SSH|' + ($S.Arguments -join ' '))\n"
    )

    def _rows(directory: str, name: str) -> dict:
        snippet = (
            f'$RepoRoot = "{REPO_ROOT}"\n'
            f'$LocalBase = "http://127.0.0.1:{TUNNEL_PORT}"\n'
            f"$LogFile = '{directory}\\tunnel.log'\n"
            f"$ErrFile = '{directory}\\stderr.log'\n"
            f"$OutFile = '{directory}\\stdout.log'\n"
            f"$SshDebugFile = '{directory}\\ssh-debug.log'\n"
            + resolver + "\n" + tail
        )
        rows = {}
        for line in _run_ps1(prefix + snippet, tmp_path, name=name).splitlines():
            if "|" in line:
                kind, arguments = line.split("|", 1)
                rows[kind] = arguments
        assert len(rows) == 2, rows
        return rows

    marker = "pe_tunnel_" + str(TUNNEL_PORT)
    spaced = "C:\\Users\\张三 李四\\AppData\\Local\\Temp\\" + marker
    plain = "C:\\pe-probe\\" + marker

    # ①
    rows = _rows(spaced, "spaced.ps1")
    assert rows["CF"].endswith('--logfile "' + spaced + '\\tunnel.log"'), rows["CF"]
    assert '-E "' + spaced + '\\ssh-debug.log"' in rows["SSH"], rows["SSH"]
    # ③ 的反空转那一半：孤儿标记在两档里都在（引号加在整个值**外面**）
    assert marker in rows["CF"], rows["CF"]
    assert marker in rows["SSH"], rows["SSH"]

    # ②
    rows2 = _rows(plain, "plain.ps1")
    assert rows2["CF"].endswith("--logfile " + plain + "\\tunnel.log"), rows2["CF"]
    assert '"' not in rows2["CF"], rows2["CF"]
    assert rows2["CF"].startswith(
        f"tunnel --url http://127.0.0.1:{TUNNEL_PORT} --no-autoupdate --protocol http2 "
    ), rows2["CF"]

    # ③⚠️ 反空转：改前的写法（直接把原始路径塞进 Arguments）必须对不上①
    # ⚠️ 光把两个变量名换回去**不算**改前：那两段 ``if`` 会转而给 ``$LogFile`` /
    #    ``$SshDebugFile`` 自己加引号，输出逐字相同（本波首跑实测就是这么假绿的）。
    #    故这里把**整个引号块**切掉 —— 那才是改前的形状。
    cut_from = resolver.index("$QuotedLogFile = $LogFile")
    cut_to = resolver.index("if ($Chosen -eq 'cloudflared') {")
    assert cut_from < cut_to, (cut_from, cut_to)
    naive = (resolver[:cut_from] + resolver[cut_to:]).replace(
        "$QuotedLogFile", "$LogFile").replace("$QuotedSshDebugFile", "$SshDebugFile")
    assert naive != resolver, "③那一拍是空转的：切出来的那一段里没有那两个变量"
    assert "$QuotedLogFile" not in naive and "$QuotedSshDebugFile" not in naive
    snippet = (
        f'$RepoRoot = "{REPO_ROOT}"\n'
        f'$LocalBase = "http://127.0.0.1:{TUNNEL_PORT}"\n'
        f"$LogFile = '{spaced}\\tunnel.log'\n"
        "$ErrFile = 'x'\n$OutFile = 'y'\n"
        f"$SshDebugFile = '{spaced}\\ssh-debug.log'\n"
        + naive + "\n" + tail
    )
    naive_rows = {}
    for line in _run_ps1(prefix + snippet, tmp_path, name="naive.ps1").splitlines():
        if "|" in line:
            kind, arguments = line.split("|", 1)
            naive_rows[kind] = arguments
    assert naive_rows["CF"] != rows["CF"], (
        "①那一拍是空转的：不加引号也能满足它，于是这一格没有钉住引号"
    )
    assert naive_rows["CF"].endswith("--logfile " + spaced + "\\tunnel.log"), naive_rows["CF"]



def test_the_edge_530_is_recognised_and_never_reaches_the_url_file():
    """HTTP 530 **被认出来**、被点名，⚠️ 而它**永远走不到 ⑤ 写 URL 文件**那一步。

    五拍：

    ① 那一档状态码只有一个住址（``$EdgeDeadStatus = 530``），⚠️ 而 **530 这个字面量
       在语句里恰好一次**（就是那次赋值；别处一律用变量，于是「Cloudflare 换了
       一个码」只改一处）；
    ② 状态码是从 ``$_.Exception.Response`` 上取的，⚠️ 而**先判 ``$null``**
       （本波实测：一个 530 的响应，``Response`` 是 ``HttpWebResponse``、
       ``[int]`` 它那个 ``StatusCode`` 得 530；而「压根连不上」那一档 ``Response``
       是 ``$null``、``Status`` 是 ``ConnectFailure`` ⇒ 不判空就是一段
       ``You cannot call a method on a null-valued expression``，离真因有一层）；
    ③ 认出 530 之后**打印的处置**里逐字有 ``-Protocol http2``（换协议重开）
       与那 17 字节响应体的原文（``error code: 1033``，让读日志的人对得上浏览器里那一页）；
    ④⚠️ **顺序是承重的**：复核失败那一句 ``throw`` 排在 ⑤ 写 URL 文件**之前**
       ——把一条死链接写进 ``.trial\\public-url.txt`` 比不写更坏
       （下一个人会照着它去点）；
    ⑤ 反静默：复核那 90 秒里每 15 秒打一行进度（改前屏幕上一行都没有，
       于是「边缘还没就绪（正常）」与「链接已经死了（永远不好）」长得一模一样）。
    """
    statements = _statements()

    # ①
    assert statements.count(f"$EdgeDeadStatus = {EDGE_DEAD_STATUS}") == 1, statements[:400]
    assert statements.count(str(EDGE_DEAD_STATUS)) == 1, (
        f"{EDGE_DEAD_STATUS} 这个字面量在语句里出现了 "
        f"{statements.count(str(EDGE_DEAD_STATUS))} 次（期望 1 = 那次赋值；"
        "别处一律用变量，于是「Cloudflare 换了一个码」只改一处）"
    )
    assert "$EdgeDeadStatus" in statements

    # ②
    null_check = "$null -ne $_.Exception.Response"
    take_status = "[int]$_.Exception.Response.StatusCode"
    assert statements.count(null_check) >= 2, (
        "④ b 与 watchdog 两处都要先判 Response 是不是 $null（连不上时它是 $null）"
    )
    assert statements.count(take_status) >= 2
    assert statements.index(null_check) < statements.index(take_status), (
        "取状态码排在了判空之前：连不上时那一句会变成一段 null-valued expression 的报错"
    )
    assert "$EdgeDeadTries += 1" in statements

    # ③
    assert "-Protocol http2" in statements, "认出 530 之后没有把处置（换协议重开）说清楚"
    assert EDGE_DEAD_BODY in statements, (
        "那 17 字节响应体的原文不在打印里：读日志的人对不上浏览器里那一页"
    )
    assert "failed to dial to edge with quic" in statements, (
        "成因那一句不见了（隧道日志里一路是这一行 + 指数退避，那是认这一档的现场特征）"
    )

    # ④
    throw_at = statements.index("throw (\"穿过公网打不通：\"")
    write_at = statements.index("[System.IO.File]::WriteAllText($UrlFile")
    assert throw_at < write_at, (
        f"复核失败那一句 throw（{throw_at}）排在了写 URL 文件（{write_at}）之后："
        "一条死链接会被写进 .trial/public-url.txt"
    )
    assert statements.index("$EdgeDeadTries -gt 0") < write_at

    # ⑤
    assert "$NextReachProgressSeconds += 15" in statements
    assert "…还在复核那条公网链接" in statements


def test_the_watchdog_defaults_to_sixty_and_alarms_without_reopening():
    """``-Watchdog``：缺省 **60**（改前是 0 = 关），报警时**只报警、不自动重开**。

    ⚠️ 本条在 Plan 07 Task 7 改过两处（终审 S3-6），而**「不自动重开」那条裁定没动**
    （Task 4 的裁定与 Task 6 的终审都同意它：自动重开会换掉甲方手上那条链接，
    一条换掉地址的自愈比一条看得见的死链更坏）。改的是：

    * **缺省值**：``0`` → ``60``。「进程在、链接死」是两波里**亲自撞到两次**的那一档
      （quic 跑约 3 小时后本机 UDP 出网断了；以及主机名被边缘撤掉、DNS 直接 NXDOMAIN），
      而缺省关掉一个只报警、不改变任何行为的自检，换来的只是「与本波之前逐字相同」；
    * **落点**：报警那一拍除了 ``Write-Host``，还要往 ``.trial\\public-url.txt`` 里
      **追加**三行。终端是没人看的（那格事故里链接死了几个小时、机器上没有任何一处
      说它死了），而那个文件是甲方/运维**真会去打开**的那一个。

    八拍：

    ① ``0`` 那一档仍然可用（判据是 ``$Watchdog -gt 0``），而那一档下 ⑦ 的循环体与
       改前**逐字相同**（``Start-Sleep -Seconds 2`` + ``Write-NewTunnelLog``，一格都不许多）；
    ② 报警的阈值是一个**有名字的变量**（``$WatchdogAlarmAfter = 3``）而不是散在三处的 3；
    ③⚠️ **那一块里没有任何一处会重开隧道**：``Start-Process`` / ``Stop-Process`` /
       ``Resolve-TunnelBackend`` / 给 ``$Proc`` 赋值，四样一个都不出现；
    ④ 而它**确实**打印了一段响亮的 ⚠️，里面逐字有「不自动重开」与那条重开命令；
    ⑤ 恢复之后**重新武装**（``$WatchdogAlarmShown = $false``）：
       一个只会报一次的自检是半个自检；
    ⑥⚠️ 报警那一拍**往 URL 文件里追加**（``AppendAllText``），而**不是重写**
       （``WriteAllText``）、也**不是删掉它**（``Remove-Item``）：重写会把 ``url`` /
       ``隧道 PID`` / 两格 health 一起冲掉，于是「死的是哪一条链接」反而查不到；
       而那个文件此刻正是**唯一**写着链接的地方；
    ⑦ 追加进去的那几行里逐字有「**不会自动恢复**」与「**全新的地址**」
       （读那个文件的人下一步该干什么，得写清楚），且报了「从什么时候起」
       连续几拍不通（``$WatchdogFailingSince``）—— 只知道「死了」不知道「死了多久」，
       就判不了「要不要现在重开」；
    ⑧ 那个文件不在时**不炸**（``Test-Path`` 兜住），只打印一句说明。
    """
    statements = _statements()

    # ①
    assert "$Watchdog -gt 0" in statements
    loop_at = statements.index("while (-not $Proc.HasExited) {")
    loop_body = statements[loop_at:loop_at + 400]
    assert "Start-Sleep -Seconds 2" in loop_body, loop_body
    assert "Write-NewTunnelLog -Path $LogFile" in loop_body

    # ②
    assert statements.count("$WatchdogAlarmAfter = 3") == 1
    assert statements.count("$WatchdogFailures -ge $WatchdogAlarmAfter") == 1

    # ③⚠️ 本条的**牙**（派单点名的定点变异就是打在这一拍上）
    #    ⚠️ 那一块的下界是 ``$Proc.Refresh()``（⑦ 的循环结束之后那一句），
    #    不能一路切到语句末尾：``finally`` 里**本来就有**一句 ``Stop-Process``
    #    （那是「Ctrl-C 时兜住隧道进程」，与本条要挡的「自动重开」是两件事），
    #    切过头会让本拍红在一句正确的代码上。
    watchdog_at = statements.index("$WatchdogFailures = 0")
    watchdog_end = statements.index("$Proc.Refresh()", watchdog_at)
    assert watchdog_at < watchdog_end
    watchdog_block = statements[watchdog_at:watchdog_end]
    for needle in ("Start-Process", "Stop-Process", "Resolve-TunnelBackend",
                   "$Proc = ", "$Proc="):
        assert needle not in watchdog_block, (
            f"watchdog 那一块里出现了 {needle!r}：裁定是**只打印、不自动重开**"
            "（自动重开会换掉甲方手上那条链接）"
        )

    # ④
    assert "那条公网链接**可能已经死了**" in watchdog_block
    assert "**不自动重开**" in watchdog_block
    assert "-Protocol http2 -Watchdog" in watchdog_block, (
        "那段 ⚠️ 里没有给出重开的命令（读了它的人下一步该跑什么，得写清楚）"
    )

    # ⑤
    assert "$WatchdogAlarmShown = $false" in watchdog_block
    assert watchdog_block.count("$WatchdogAlarmShown = $true") == 1

    # ⑥⚠️ 本拍是 Plan 07 Task 7 的**牙**：把「追加」改成「重写」或「删掉再写」，
    #    下面三条里就会红一条（派单点名的定点变异正是打在这里）。
    assert watchdog_block.count("AppendAllText($UrlFile") == 1, (
        "报警那一拍没有往 URL 文件里**追加**：终端是没人看的，而那个文件是"
        "甲方/运维真会去打开的那一个"
    )
    assert "WriteAllText($UrlFile" not in watchdog_block, (
        "报警那一拍**重写**了 URL 文件：那会把 url / 隧道 PID / 两格 health 一起冲掉，"
        "于是「死的是哪一条链接」反而查不到"
    )
    assert "Remove-Item $UrlFile" not in watchdog_block, (
        "报警那一拍**删掉**了 URL 文件：它此刻正是唯一写着链接的地方"
    )
    assert "Test-Path $UrlFile" in watchdog_block, "⑧ 那一格：文件不在时要兜住、不炸"

    # ⑦
    assert "**不会自动恢复**" in watchdog_block, (
        "追加进去的那几行里没有「不会自动恢复」：读它的人下一步该干什么就看不出来"
    )
    assert "**全新的地址**" in watchdog_block
    assert "$WatchdogFailingSince" in watchdog_block, (
        "没有报「从什么时候起」不通：只知道「死了」不知道「死了多久」，判不了要不要现在重开"
    )
    assert "$WatchdogFailures + ' 拍打不通" in watchdog_block

    # ⚠️ 而「追加进 URL 文件」这一格**不许**把 public-url.txt 这个字面量写进语句里
    #    （那会撞 :func:`test_the_url_file_path_has_one_owner_and_gitignore_agrees` 的「语句里恰好一次」那一拍）：
    #    路径只有一个所有者 = ``$UrlFile``。
    assert statements.count("public-url.txt") == 1, statements.count("public-url.txt")


def test_the_description_names_the_default_protocol_and_the_watchdog_ruling():
    """``.DESCRIPTION`` 里写着两个缺省**与它们的理由**（派单 Task 4 §2.1 / §2.3 逐字要求）。

    ⚠️ 为什么这一条要单独存在：``Get-Help scripts\\tunnel.ps1`` 的**缺省视图**
    只显示 ``.SYNOPSIS`` / ``.DESCRIPTION`` / 语法，⚠️ **不显示** ``.PARAMETER``
    的帮助文本（要 ``-detailed`` 或 ``-full``；Task 5 实测过）⇒ 只写在
    ``.PARAMETER`` 里的话，跑一次缺省 ``Get-Help`` 的人看不见这两格裁定。
    """
    help_text = _tunnel_ps1_help()
    for needle in (
        "``-Protocol`` 的缺省是 **``auto``**",
        "``-Watchdog``：长跑期的自检，⚠️ **只报警、不自动重开**",
        "HTTP 530",
        "error code: 1033",
        "--protocol http2",
        "UDP 路径断了",
        "第二个所有者",
    ):
        assert needle in help_text, f".DESCRIPTION 里少了 {needle!r}"


def test_the_student_count_in_warning_five_is_read_from_the_health_probe():
    """⑤ 那一条风险告示里的人数**从 ③ 那一次 ``/api/health`` 里取**，⚠️ 不写死 60。

    病灶（Plan 07 Task 8 · 终审 S4-3 的**同族自查**；终审只点名了 ``trial.ps1``）：
    改前 ⑤ 逐字印着「库里 60 名学生均为虚构」，而那一个数的唯一所有者是
    ``backend/scripts/demo_bootstrap.py`` 的 ``--students`` argparse 缺省
    ⇒ 同一件事两个所有者，而漏改的那一处正是**要念给甲方听**的那一处。

    ⚠️ 本文件与 ``trial.ps1`` 的处置**不同**（那一格走库、这一格走 health）：
    本脚本**手上有**那一份 health —— ``$LocalHealthObject`` 就是 ③ 那一次 200 的
    响应体 ``ConvertFrom-Json`` 的结果，而 ④ b 已经拿它的 ``tables`` 与 ``trial``
    两格与公网那一次对过账。⚠️ 而 ``trial.ps1`` 的 ⑤ b 排在 ``serve.ps1`` 起来
    **之前**，那时端口上还没有任何东西在听，故它只能走库。两处**各走自己手上有的
    那一份**，而两份都不是字面量。

    三拍：

    ① 语句里没有那个字面量；
    ② ⑤ 那一行读的是 ``$LocalHealthObject.students``；
    ③ 反空转：⑤ 的那条无歧义串仍然恰好一次 ⇒ ① 不是靠把整条告示删掉换来的绿
       （那一格由
       :func:`test_the_six_public_exposure_warnings_are_each_pinned_on_an_unambiguous_string`
       钉着，本条不复述它的判据）。
    """
    statements = _statements()
    assert "库里 60 名学生" not in statements, "⑤ 又写死了 60（终审 S4-3 的同族）"
    hits = [line for line in statements.splitlines() if "**不要录入真实学生信息**" in line]
    assert len(hits) == 1, hits
    assert "$LocalHealthObject.students" in hits[0], (
        f"⑤ 那一行不再从 ③ 那一次 /api/health 里取人数 → {hits[0][:200]}"
    )

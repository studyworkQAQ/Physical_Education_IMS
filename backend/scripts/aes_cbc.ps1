<#
.SYNOPSIS
    AES-256-CBC + PKCS7 的**一个原语**（Plan 08 Task 3）。⚠️ 它**不是**给人跑的命令。

.DESCRIPTION
    ⚠️⚠️ **本文件存在的唯一理由**：Python 的标准库里**没有 AES**（``hashlib`` 有
    PBKDF2 与摘要、``hmac`` 有 MAC，而分组密码一个都没有），而本波**新增依赖必须是 0**
    （``pyproject.toml`` 一个字都不许改；``tests/test_dependencies.py`` 与
    ``tests/test_backup_restore.py`` 的
    ``test_neither_script_copies_files_or_adds_a_dependency`` 两面钉着）
    ⇒ 那一次变换只能叫 **.NET 的 BCL**（``System.Security.Cryptography.Aes``），
    而在 Windows 上叫 BCL 的唯一姿势是 PowerShell。

    ⚠️ 于是本仓「逻辑一律住 ``.py``、``.ps1`` 只是薄包装」那条纪律在这里有一个
    **例外**，而例外**只有这一格**：``backend/scripts/backup.py`` 仍然是
    **产物形状的唯一所有者**（魔数 / 版本 / KDF 参数 / 盐 / IV / HMAC / 侧车 /
    保留策略全在它那里），本文件只做「一块字节进、一块字节出」的那一次分组密码变换，
    ⚠️ **一个格式字节都不认识**（它不知道什么叫 ``PEBACKUP``、不知道 HMAC 在哪一段）。

    ⚠️ **为什么不是 AES-GCM**（派单 §2 第 3 条要的是「先实测」）：本机实测
    PowerShell **5.1.26100.9711** / CLR **4.0.30319.42000**（= .NET Framework 4.x）下
    ``[System.Security.Cryptography.AesGcm]`` 报 ``Unable to find type``
    （它是 .NET Core 3.0+ 才有的类型），``New-Object`` 同样失败
    ⇒ 走 **AES-256-CBC + 独立的 HMAC-SHA256**。⚠️ 而「先验 MAC、验不过就**不解密**」
    那一格住在 ``backup.py`` 的 ``verify_container``（**不是**这里）：
    本文件被叫到时 MAC 已经验过了。

    -----------------------------------------------------------------------
    ⚠️ 调用形状（密钥走 **stdin**，⚠️ 不走 argv、不走环境变量、不落盘）
    -----------------------------------------------------------------------

        powershell -NoProfile -ExecutionPolicy Bypass -File aes_cbc.ps1 -Action encrypt -In <明文> -Out <密文> [-Append]

    stdin 上要**恰好两行 base64**：第 1 行 = 32 字节密钥、第 2 行 = 16 字节 IV。

    ⚠️ **刻意不走 argv**：Windows 上任何同机进程都能用
    ``Get-CimInstance Win32_Process`` 读到别人**完整的命令行**，而 argv 里的密钥会在
    那一刻明文出现在进程表里（也进不了任何一份日志）。⚠️ 也**刻意不写一个临时文件**
    （那就是把密钥落盘）。
    ⚠️ **刻意不自己生成 IV**：IV 要进产物头，而 ``backup.py`` 是那个头的唯一所有者
    ⇒ IV 由调用方生成、传进来，于是「头上写着的那个 IV」与「真的用来加密的那个 IV」
    **不可能**不是同一个。

    ``-Append`` 只给加密那一档用：调用方先把 60 字节的产物头写进 ``-Out``，
    本文件再把密文**接在它后面**（于是密文只被写一次；⚠️ 不给 ``-Append`` 时
    ``-Out`` 会被**截断重写**，那是解密那一档要的形状）。

    -----------------------------------------------------------------------
    退出码
    -----------------------------------------------------------------------

        0   成功
        3   一次**该拒绝**的调用（参数不对 / stdin 的形状不对 / 密钥或 IV 的宽度不对 /
            输入不在 / -In 与 -Out 是同一个文件）
        4   变换本身失败（解密那一档下通常是 padding 不对 = 密文被改过或密钥不对；
            ⚠️ 而上游的 HMAC 本应先把它挡下 —— 走到这里说明 HMAC 与密文不是同一份东西算的）

    ⚠️ 退出码非 0 时 ``-Out`` 那个半成品文件**会被删掉**：留一个「看起来像库、
    而其实只有前半截」的文件比留一个错误更坏。
    ⚠️ 报错里**刻意不复述**它收到的任何一部分密钥材料（连长度都不印）。

    ⚠️ **流式**：走 ``CryptoStream`` + ``Stream.CopyTo``（80 KiB 一块）而不是
    ``ReadAllBytes``，故一个 GB 量级的库也**不会**被整份读进内存
    （与 ``backup.py`` 的 ``sha256_of`` 分块算同一条口径）。实测 1 MiB 的一次
    加密 + 一次解密 ≈ 41 ms（本机，.NET Framework 4.x）。

    ⚠️ **一句语法教训（本 Task 第一版当场红在这里）**：PS 5.1 的解析器
    **不接受**「括号内换行、而运算符在**下一行行首**」那种续行::

        Fail 3 ('第一段'
                + '第二段')          # ← Missing closing ')' in expression

    故本文件里所有多段的报错一律写成**两条语句**（``$Why = '…'`` / ``$Why += '…'``），
    与 ``register_retention_task.ps1`` 把整条 ``schtasks`` 写在一行上同一条理由：
    不给 PS 5.1 的解析器留猜测的余地。
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("encrypt", "decrypt")]
    [string]$Action,
    [Parameter(Mandatory = $true)]
    [string]$In,
    [Parameter(Mandatory = $true)]
    [string]$Out,
    [switch]$Append
)

$ErrorActionPreference = "Stop"
# ⚠️ 让 stderr 上的中文按 UTF-8 出去（调用方按 utf-8 解码）。姿势与本仓
#    tests/test_tunnel.py 的 _run_ps1 前缀逐字相同。⚠️ 包在 try 里：某些宿主下
#    输出被重定向时这个 setter 会抛，而它抛了也不该让一次加解密失败。
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$KEY_BYTES = 32      # AES-256
$IV_BYTES = 16       # AES 的分组宽度

function Fail([int]$Code, [string]$Message) {
    [Console]::Error.WriteLine($Message)
    exit $Code
}

# ---- stdin 上的两行 base64（密钥 / IV）-------------------------------------
$Lines = New-Object 'System.Collections.Generic.List[string]'
while ($null -ne ($Line = [Console]::In.ReadLine())) {
    $Trimmed = $Line.Trim()
    if ($Trimmed.Length -gt 0) { $Lines.Add($Trimmed) }
}
if ($Lines.Count -ne 2) {
    $Why = 'aes_cbc.ps1 要在 stdin 上收到**恰好两行** base64（第 1 行 = 密钥、第 2 行 = IV），'
    $Why += '实到 ' + $Lines.Count + ' 行。'
    $Why += '⚠️ 本文件不是给人跑的命令：请走 backup.ps1 / restore.ps1'
    $Why += '（它们经 scripts/backup.py 与 scripts/restore.py 调它）。'
    Fail 3 $Why
}
try { $Key = [Convert]::FromBase64String($Lines[0]) }
catch { Fail 3 'aes_cbc.ps1：stdin 的第 1 行不是 base64。⚠️ 本文件刻意不复述它收到的任何一部分。' }
try { $Iv = [Convert]::FromBase64String($Lines[1]) }
catch { Fail 3 'aes_cbc.ps1：stdin 的第 2 行不是 base64。' }
# ⚠️ 下面两句都**刻意不印实到的字节数**：那是密钥材料的一部分（派单 §2 第 3 条
#    逐字要求「不许打印它的任何一部分，包括长度与 sha」）。
if ($Key.Length -ne $KEY_BYTES) {
    $Why = 'aes_cbc.ps1：密钥的宽度不对（AES-256 要 ' + $KEY_BYTES + ' 字节）。'
    $Why += '⚠️ 上游（backup.py 的 derive_keys）派生出来的恒是那一个宽度，'
    $Why += '故走到这里说明本文件被别的什么东西调了'
    Fail 3 $Why
}
if ($Iv.Length -ne $IV_BYTES) {
    Fail 3 'aes_cbc.ps1：IV 的宽度不对（AES-CBC 要一个分组 = 16 字节）'
}
if (-not (Test-Path -LiteralPath $In)) { Fail 3 ('aes_cbc.ps1：输入文件不存在：' + $In) }
if ((Resolve-Path -LiteralPath $In).Path -eq [System.IO.Path]::GetFullPath($Out)) {
    # ⚠️ 那一档下 -Out 会先把 -In 截断，于是「输入」在第一个字节被读之前就没了
    Fail 3 'aes_cbc.ps1：-In 与 -Out 是同一个文件（那会先把输入截断）'
}

$Aes = [System.Security.Cryptography.Aes]::Create()
$Ok = $false
try {
    $Aes.KeySize = $KEY_BYTES * 8
    $Aes.Mode = [System.Security.Cryptography.CipherMode]::CBC
    $Aes.Padding = [System.Security.Cryptography.PaddingMode]::PKCS7
    $Aes.Key = $Key
    $Aes.IV = $Iv
    if ($Action -eq "encrypt") { $Transform = $Aes.CreateEncryptor() }
    else { $Transform = $Aes.CreateDecryptor() }

    $InStream = [System.IO.File]::OpenRead($In)
    try {
        if ($Append) { $OutStream = [System.IO.File]::Open($Out, [System.IO.FileMode]::Append) }
        else { $OutStream = [System.IO.File]::Create($Out) }
        try {
            if ($Action -eq "encrypt") {
                $Crypto = New-Object System.Security.Cryptography.CryptoStream($OutStream, $Transform, [System.Security.Cryptography.CryptoStreamMode]::Write)
                try { $InStream.CopyTo($Crypto); $Crypto.FlushFinalBlock() } finally { $Crypto.Dispose() }
            } else {
                $Crypto = New-Object System.Security.Cryptography.CryptoStream($InStream, $Transform, [System.Security.Cryptography.CryptoStreamMode]::Read)
                try { $Crypto.CopyTo($OutStream) } finally { $Crypto.Dispose() }
            }
            $Ok = $true
        } finally { $OutStream.Dispose() }
    } finally { $InStream.Dispose() }
} catch [System.Security.Cryptography.CryptographicException] {
    $Why = 'aes_cbc.ps1：AES-256-CBC 的 ' + $Action + ' 失败（' + $_.Exception.Message + '）。'
    $Why += '⚠️ 解密那一档下这通常意味着密文被改过或密钥不对 —— '
    $Why += '而上游（scripts/backup.py 的 verify_container）本应在 HMAC 那一步就把它挡下；'
    $Why += '走到了这里说明 HMAC 与密文**不是同一份东西**算出来的'
    Fail 4 $Why
} catch {
    Fail 4 ('aes_cbc.ps1：' + $Action + ' 失败（' + $_.Exception.GetType().Name + ': ' + $_.Exception.Message + '）')
} finally {
    $Aes.Dispose()
    # ⚠️ 尽力抹掉本进程内存里那两份密钥材料（.NET 不保证：字节数组一旦进过 GC 堆
    #    就可能还有副本；如实记，硬规矩 #39）
    if ($null -ne $Key) { [Array]::Clear($Key, 0, $Key.Length) }
    if ($null -ne $Iv) { [Array]::Clear($Iv, 0, $Iv.Length) }
    if (-not $Ok) {
        # ⚠️ 不留一个「看起来像库、而其实只有前半截」的文件
        if (Test-Path -LiteralPath $Out) {
            try { Remove-Item -LiteralPath $Out -Force } catch { }
        }
    }
}
exit 0

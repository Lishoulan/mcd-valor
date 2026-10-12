<#
.SYNOPSIS
    在 PowerShell 里实跑所有命令，验证 Windows 用户路径可用。

.DESCRIPTION
    为什么需要这个：这个项目的其他测试都在 Git Bash / subprocess 里跑，
    Windows 用户路径从来没被验证过。

    实测撞到过：PowerShell 5.1 捕获 stdout 会把中文显示成乱码，
    一度以为是产品 bug，查下来是 PowerShell 5.1 的老问题（看终端显示是正常的）。
    所以本脚本只检查「退出码 + 有没有 Traceback」，不比对输出内容。

.EXAMPLE
    $env:MCD_MCP_TOKEN = "你的Token"
    python tools\test_windows.ps1
#>

$ErrorActionPreference = 'Continue'

# 关键：PowerShell 不会拆 `& $py -m butler $c` 里的 $c，
# 整串会被当成一个参数。必须显式 -split。
# 另外把控制台输出编码设为 UTF-8，否则中文参数在 PowerShell 5.1 里会变 GBK 乱码。
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch { }

# 可用环境变量 MCD_TEST_PYTHON 指定 python 路径
$py = if ($env:MCD_TEST_PYTHON) { $env:MCD_TEST_PYTHON } else { 'python' }
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Output "=== PowerShell $($PSVersionTable.PSVersion) / $py ==="
Write-Output ""

$cmds = @(
    'account',
    'coupons',
    'claim',
    'expiring',
    'redeem',
    'value',
    'prizes',
    'spend',
    'calendar',
    'calendar --date 2026-10-15',
    'nutrition 麦满分',
    'stores 爱联',
    'stores 北大 --city 北京',
    'stores 地铁站 --dt --city 深圳',
    'redeem 爱联 --limit 2',
    'expiring --window 14'
)

$pass = 0
$failed = @()
foreach ($c in $cmds) {
    $out = & $py -m butler ($c -split ' ') 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0 -and $out -notmatch 'Traceback') {
        $pass++
        Write-Output "  OK   butler $c"
    } else {
        $failed += $c
        Write-Output "  FAIL butler $c  (exit=$LASTEXITCODE)"
        $err = $out -split "`n" | Where-Object { $_ -match 'Error|error' } | Select-Object -First 2
        foreach ($e in $err) { Write-Output "        $e" }
    }
}

Write-Output ""
Write-Output "通过 $pass / $($cmds.Count)"
if ($failed.Count -gt 0) {
    Write-Output "失败的命令：$($failed -join ' | ')"
    exit 1
}
Write-Output "OK Windows 路径全部可用"
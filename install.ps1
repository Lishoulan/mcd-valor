<#
.SYNOPSIS
    积值 Valor · 一键安装为 WorkBuddy Skill

.DESCRIPTION
    把 SKILL.md 放到 WorkBuddy 能识别的技能目录。
    重复运行 = 更新；卸载 = 删除 ~/.workbuddy/skills/mcd-valor 目录。

.EXAMPLE
    irm https://raw.githubusercontent.com/Lishoulan/mcd-valor/main/install.ps1 | iex
#>

$ErrorActionPreference = 'Stop'

$repo  = 'https://raw.githubusercontent.com/Lishoulan/mcd-valor/main'
$skills = if ($env:WORKBUDDY_SKILLS) { $env:WORKBUDDY_SKILLS }
           else { Join-Path $HOME '.workbuddy\skills' }
$dest = Join-Path $skills 'mcd-valor'

function Info($m) { Write-Host "▸ $m" -ForegroundColor DarkYellow }
function Ok($m)   { Write-Host "✓ $m" -ForegroundColor Green }
function Warn($m) { Write-Host "! $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "✗ $m" -ForegroundColor Red; exit 1 }

if (Test-Path (Join-Path $dest 'SKILL.md')) {
    Info "检测到已安装，将更新…"
} else {
    Info "正在安装积值 Valor 到 $dest"
}

New-Item -ItemType Directory -Force -Path $dest | Out-Null

# TLS 1.2（部分旧版 PowerShell 默认协议偏旧，raw.githubusercontent 需要）
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch { }

try {
    Invoke-WebRequest -Uri "$repo/SKILL.md" -OutFile (Join-Path $dest 'SKILL.md') -UseBasicParsing
    Ok "SKILL.md 安装完成"
} catch {
    Die "下载失败，请检查网络后重试。$($_.Exception.Message)"
}

# 可选：附带 examples 说明（失败不影响主流程）
try {
    New-Item -ItemType Directory -Force -Path (Join-Path $dest 'examples') | Out-Null
    Invoke-WebRequest -Uri "$repo/examples/README.md" `
        -OutFile (Join-Path $dest 'examples\README.md') -UseBasicParsing
    Ok "附带了 examples 说明"
} catch { }

Write-Host ''
Ok '装好了。请**重开一轮 WorkBuddy 会话**，然后说：'
Write-Host ''
Write-Host '    我的积分该换成什么'
Write-Host '    我这几张券今天该去哪家店用'
Write-Host '    抽奖抽的券还有哪些能用'
Write-Host ''
Warn '首次使用需要配置 MCP Token：https://open.mcd.cn/mcp 申请'
Write-Host ''
Info "卸载：Remove-Item -Recurse -Force `"$dest`""

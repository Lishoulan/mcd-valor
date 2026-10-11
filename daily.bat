@echo off
REM 积值 Valor · 每日记录任务（Windows 版）
REM
REM 用「任务计划程序」新建基本任务，每天 09:00 运行本文件即可：
REM   程序:  powershell -NoProfile -ExecutionPolicy Bypass -File <本文件路径>
REM   或直接: schtasks /create /tn "积值每日记录" /sc daily /st 09:00 ^
REM                /tr "cmd /c \"<完整路径>\daily.bat\"" /rl LIMITED

setlocal
cd /d "%~dp0"

REM 需要预先设置 MCD_MCP_TOKEN，方式任选：
REM   setx MCD_MCP_TOKEN "你的Token"     （永久，当前窗口不生效，需重开终端）
REM   或在系统环境变量里配置

if "%MCD_MCP_TOKEN%"=="" (
    echo [%date% %time%] 跳过：未设置 MCD_MCP_TOKEN
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo [%date% %time%] 跳过：未找到 python
    exit /b 1
)

echo [%date% %time%] 开始记录...
python tools\record_run.py
if errorlevel 1 (
    echo [%date% %time%] 记录失败（网络或接口问题）
    exit /b 1
)

REM 有变化就提交推送
git diff --quiet examples\run-log.jsonl docs\RUN_LOG.md
if errorlevel 1 (
    git add examples\run-log.jsonl docs\RUN_LOG.md
    git commit -m "chore: 跨天记录 %date:~0,4%-%date:~5,2%-%date:~8,2%"
    git push origin HEAD
    echo [%date% %time%] 已提交并推送
) else (
    echo [%date% %time%] 数据未变化，无需提交
)

endlocal

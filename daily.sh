#!/usr/bin/env bash
# 积值 Valor · 每日记录任务（本地版）
#
# 为什么不用 GitHub Actions：
#   实测 GitHub 的美国 runner 访问 https://mcp.mcd.cn 会返回 **HTTP 401**
#   （同一个 Token 在本机是 200）。原因未公开，但结论是：
#   境外 runner 拿不到授权，且你的 Token 也不该从境外机器发出去。
#   → 所以改为在本机定时跑。
#
# 安装（Linux/macOS crontab）：
#   crontab -e
#   0 9 * * * /path/to/butler/daily.sh >> /path/to/butler/daily.log 2>&1
#
# 安装（Windows 任务计划）：
#   schtasks /create /tn "积值每日记录" /sc daily /st 09:00 ^
#           /tr "\"C:\path\to\butler\daily.bat\"" /rl LIMITED
#   或直接在「任务计划程序」里新建基本任务，每天 09:00 运行 daily.bat

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python

if [ -z "${MCD_MCP_TOKEN:-}" ]; then
  echo "[$(date '+%F %T')] 跳过：未设置 MCD_MCP_TOKEN" >&2
  exit 1
fi

echo "[$(date '+%F %T')] 开始记录…"
if "$PY" tools/record_run.py; then
  # 有变化就提交并推送，让记录表在GitHub 上公开可见
  if ! git diff --quiet examples/run-log.jsonl docs/RUN_LOG.md 2>/dev/null; then
    git add examples/run-log.jsonl docs/RUN_LOG.md
    git commit -m "chore: 跨天记录 $(date '+%Y-%m-%d')" >/dev/null 2>&1 \
      && git push -q origin HEAD 2>/dev/null \
      && echo "[$(date '+%F %T')] 已提交并推送" \
      || echo "[$(date '+%F %T')] 记录已生成，但推送失败（可能无网络或无权限）" >&2
  else
    echo "[$(date '+%F %T')] 数据未变化，无需提交"
  fi
else
  echo "[$(date '+%F %T')] 记录失败（网络或接口问题），不影响其他功能" >&2
  exit 1
fi

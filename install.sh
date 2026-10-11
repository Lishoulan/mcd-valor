#!/usr/bin/env bash
# 积值 Valor · 一键安装为 WorkBuddy Skill
#
#   curl -fsSL https://raw.githubusercontent.com/Lishoulan/mcd-valor/main/install.sh | bash
#
# 重复运行 = 更新；卸载 = 删除 ~/.workbuddy/skills/mcd-valor 目录。
# 本脚本只做一件事：把 SKILL.md 放到 WorkBuddy 能识别的技能目录。

set -euo pipefail

REPO="https://raw.githubusercontent.com/Lishoulan/mcd-valor/main"
DEST="${WORKBUDDY_SKILLS:-$HOME/.workbuddy/skills}/mcd-valor"

info()  { printf '\033[38;5;208m▸\033[0m %s\n' "$1"; }
ok()    { printf '\033[32m✓\033[0m %s\n' "$1"; }
warn()  { printf '\033[33m!\033[0m %s\n' "$1"; }
die()   { printf '\033[31m✗\033[0m %s\n' "$1" >&2; exit 1; }

command -v curl >/dev/null 2>&1 || die "需要 curl，请先安装。"

if [ -f "$DEST/SKILL.md" ]; then
  info "检测到已安装，将更新…"
else
  info "正在安装积值 Valor 到 $DEST"
fi

mkdir -p "$DEST"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

if curl -fsSL "$REPO/SKILL.md" -o "$TMP"; then
  mv "$TMP" "$DEST/SKILL.md"
  trap - EXIT
  ok "SKILL.md 安装完成"
else
  die "下载失败，请检查网络后重试。"
fi

# 若仓库里有 references/ 之类可选资料，一并取回（失败不影响主流程）
if curl -fsSL "$REPO/examples/README.md" -o "$TMP" 2>/dev/null; then
  mkdir -p "$DEST/examples"
  cp "$TMP" "$DEST/examples/README.md"
  ok "附带了examples 说明"
fi

echo
ok "装好了。**请重开一轮 WorkBuddy 会话**，然后说："
echo
echo "    我的积分该换成什么"
echo "    我这几张券今天该去哪家店用"
echo "    抽奖抽的券还有哪些能用"
echo
warn "首次使用需要配置 MCP Token：https://open.mcd.cn/mcp 申请"
echo
info "卸载：rm -rf \"$DEST\""

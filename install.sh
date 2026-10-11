#!/usr/bin/env bash
# 积值 Valor · 一键安装为 WorkBuddy Skill
#
#   curl -fsSL https://raw.githubusercontent.com/Lishoulan/mcd-valor/HEAD/install.sh | bash
#
# 重复运行 = 更新；卸载 = 删除 ~/.workbuddy/skills/mcd-valor 目录。
#
# 关于分支：用 HEAD 而非写死 main/master —— GitHub 的 raw 端点
# 支持 /HEAD/ 跟随默认分支，写死分支名会在改默认分支时静默失效。

set -euo pipefail

REPO="https://raw.githubusercontent.com/Lishoulan/mcd-valor/HEAD"
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

# fetch <远端路径> <本地目标> [是否必需]
fetch() {
  local remote="$1" dest="$2" required="${3:-0}"
  mkdir -p "$(dirname "$dest")"
  if curl -fsSL "$REPO/$remote" -o "$TMP" 2>/dev/null; then
    mv "$TMP" "$dest"
    trap - EXIT
    return 0
  fi
  if [ "$required" = "1" ]; then
    die "下载失败：$remote —— 请检查网络后重试。"
  fi
  return 1
}

fetch "SKILL.md" "$DEST/SKILL.md" 1 || die "下载 SKILL.md 失败，请检查网络。"
ok "SKILL.md 安装完成"

# SKILL.md 的「参考」一节直接引用MCP_INTEGRATION.md，
# 缺了它技能里的字段映射就悬空了，所以这个是必需项。
fetch "MCP_INTEGRATION.md" "$DEST/MCP_INTEGRATION.md" 0 \
  && ok "附带MCP 字段映射（技能会用到）"

# 可选资料，缺了不影响
fetch "examples/README.md" "$DEST/examples/README.md" 0 \
  && ok "附带示例说明"

echo
ok "装好了。**请重开一轮 WorkBuddy 会话**，然后说："
echo
echo "    我的积分该换成什么"
echo "    我这几张券今天该去哪家店用"
echo "    抽奖抽的券还有哪些能用"
echo
warn "首次使用需要配置 MCP Token：https://open.mcd.cn/mcp 申请"
echo
info "想要命令行版（更快的精确数字）："
echo "    git clone https://github.com/Lishoulan/mcd-valor.git && cd mcd-valor"
echo "    export MCD_MCP_TOKEN=你的Token   # Windows: set MCD_MCP_TOKEN=你的Token"
echo "    python -m butler redeem"
echo
info "卸载：rm -rf \"$DEST\""
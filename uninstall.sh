#!/usr/bin/env bash
# 卸载 symlink 矩阵，恢复为普通目录
# 注意：此脚本只删除 symlink，不删除 monorepo 中的实际文件
set -euo pipefail

GREEN='\033[0;32m' YELLOW='\033[1;33m' NC='\033[0m'
info() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

remove_symlink() {
  local dst="$1"
  if [ -L "$dst" ]; then
    rm "$dst"
    info "已删除 symlink: $dst"
  elif [ -d "$dst" ]; then
    warn "不是 symlink，跳过: $dst"
  fi
}

# 1. ~/.agents/skills
remove_symlink "$HOME/.agents/skills"
mkdir -p "$HOME/.agents/skills"

# 2. ~/.codex/skills 下的用户级 symlink（不动 .system）
for item in "$HOME/.codex/skills"/*/; do
  [ -L "${item%/}" ] && remove_symlink "${item%/}"
done

# 3. ~/.claude/skills 下的用户级 symlink
for item in "$HOME/.claude/skills"/*/; do
  [ -L "${item%/}" ] && remove_symlink "${item%/}"
done

# 4. 项目级
WORKSPACE="$HOME/Desktop/量化投资程序"
for item in "$WORKSPACE/.agents/skills"/*/; do
  [ -L "${item%/}" ] && remove_symlink "${item%/}"
done
for item in "$WORKSPACE/skills"/*/; do
  [ -L "${item%/}" ] && remove_symlink "${item%/}"
done

echo "卸载完成。如需恢复，运行: bash ~/skills-monorepo/install.sh"

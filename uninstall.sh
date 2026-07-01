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

# 4. ~/.workbuddy/skills 下的 symlink（不动 builtin 真目录）
if [ -d "$HOME/.workbuddy/skills" ]; then
  for item in "$HOME/.workbuddy/skills"/*/; do
    [ -L "${item%/}" ] && remove_symlink "${item%/}"
  done
fi

# 5. ~/.kimi-code/skills
if [ -d "$HOME/.kimi-code/skills" ]; then
  for item in "$HOME/.kimi-code/skills"/*/; do
    [ -L "${item%/}" ] && remove_symlink "${item%/}"
  done
fi

# 6. ~/.kimi/skills（旧版 Kimi 兼容）
if [ -d "$HOME/.kimi/skills" ]; then
  for item in "$HOME/.kimi/skills"/*/; do
    [ -L "${item%/}" ] && remove_symlink "${item%/}"
  done
fi

# 7. 项目级（WORKSPACE 可用环境变量覆盖；不存在则跳过）
WORKSPACE="${WORKSPACE:-$HOME/Desktop/量化投资程序}"
if [ -d "$WORKSPACE" ]; then
  for item in "$WORKSPACE/.agents/skills"/*/; do
    [ -L "${item%/}" ] && remove_symlink "${item%/}"
  done
  for item in "$WORKSPACE/skills"/*/; do
    [ -L "${item%/}" ] && remove_symlink "${item%/}"
  done
fi

echo "卸载完成。如需恢复，运行: bash ~/skills-monorepo/install.sh"

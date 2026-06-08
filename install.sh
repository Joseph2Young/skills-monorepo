#!/usr/bin/env bash
set -euo pipefail
MONOREPO="$(cd "$(dirname "$0")" && pwd)"
SHARED="$MONOREPO/shared"
PROJECT="$MONOREPO/project"
GREEN='\033[0;32m' YELLOW='\033[1;33m' RED='\033[0;31m' NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }

safe_symlink() {
  local src="$1" dst="$2"
  if [ -L "$dst" ]; then
    local current; current="$(readlink "$dst")"
    if [ "$current" = "$src" ]; then info "已就绪: $dst → $src"; return 0; fi
    rm "$dst"
  elif [ -d "$dst" ]; then
    warn "目录已存在，备份到: ${dst}.backup.$(date +%Y%m%d%H%M%S)"
    mv "$dst" "${dst}.backup.$(date +%Y%m%d%H%M%S)"
  elif [ -e "$dst" ]; then
    mv "$dst" "${dst}.backup.$(date +%Y%m%d%H%M%S)"
  fi
  ln -s "$src" "$dst"
  info "已创建: $dst → $src"
}

echo "============================================================"
echo "  Skills Monorepo 安装 (macOS)"
echo "  仓库: $MONOREPO"
echo "============================================================"

# 1. ~/.agents/skills → monorepo/shared
echo "--- ~/.agents/skills (Codex + Claude Code 共用) ---"
safe_symlink "$SHARED" "$HOME/.agents/skills"

# 2. ~/.codex/skills 用户级
echo "--- ~/.codex/skills (Codex 专属) ---"
mkdir -p "$HOME/.codex/skills"
for skill_dir in "$SHARED"/*/; do
  skill_name="$(basename "$skill_dir")"
  [[ "$skill_name" == .* ]] && continue
  safe_symlink "$skill_dir" "$HOME/.codex/skills/$skill_name"
done

# 3. ~/.claude/skills 用户级
echo "--- ~/.claude/skills (Claude Code 专属) ---"
mkdir -p "$HOME/.claude/skills"
for skill_dir in "$SHARED"/*/; do
  skill_name="$(basename "$skill_dir")"
  [[ "$skill_name" == .* ]] && continue
  safe_symlink "$skill_dir" "$HOME/.claude/skills/$skill_name"
done

# 4. 项目级
echo "--- 项目级 skills ---"
WORKSPACE="$HOME/Desktop/量化投资程序"
if [ -d "$WORKSPACE" ]; then
  mkdir -p "$WORKSPACE/.agents/skills" "$WORKSPACE/skills"
  for skill_dir in "$PROJECT"/*/; do
    skill_name="$(basename "$skill_dir")"
    [[ "$skill_name" == .* ]] && continue
    safe_symlink "$skill_dir" "$WORKSPACE/.agents/skills/$skill_name"
    safe_symlink "$skill_dir" "$WORKSPACE/skills/$skill_name"
  done
fi

echo "============================================================"
echo "  完成！共享: $(ls "$SHARED" | wc -l | tr -d ' ') 个 | 项目: $(ls "$PROJECT" 2>/dev/null | wc -l | tr -d ' ') 个"
echo "============================================================"

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

# 如果某客户端 skill 目录被误设成指向 $SHARED 的 symlink，
# 后续在该目录下创建单个 skill symlink 会导致 shared 自引用损坏。
# 此函数确保目标是一个真实目录。
ensure_real_dir() {
  local dir="$1"
  if [ -L "$dir" ] && [ "$(readlink "$dir")" = "$SHARED" ]; then
    warn "$dir 是指向 shared 的 symlink，先移除并重建为真实目录"
    rm "$dir"
  fi
  mkdir -p "$dir"
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
ensure_real_dir "$HOME/.codex/skills"
for skill_dir in "$SHARED"/*/; do
  skill_name="$(basename "$skill_dir")"
  [[ "$skill_name" == .* || "$skill_name" == *.backup.* ]] && continue
  safe_symlink "$skill_dir" "$HOME/.codex/skills/$skill_name"
done

# 3. ~/.claude/skills 用户级
echo "--- ~/.claude/skills (Claude Code 专属) ---"
ensure_real_dir "$HOME/.claude/skills"
for skill_dir in "$SHARED"/*/; do
  skill_name="$(basename "$skill_dir")"
  [[ "$skill_name" == .* || "$skill_name" == *.backup.* ]] && continue
  safe_symlink "$skill_dir" "$HOME/.claude/skills/$skill_name"
done

# 4. ~/.workbuddy/skills 用户级（可选，守护模式）
echo "--- ~/.workbuddy/skills (WorkBuddy，可选) ---"
if [ -d "$HOME/.workbuddy/skills" ] && [ ! -L "$HOME/.workbuddy/skills" ]; then
  for skill_dir in "$SHARED"/*/; do
    skill_name="$(basename "$skill_dir")"
    [[ "$skill_name" == .* || "$skill_name" == *.backup.* ]] && continue
    # 跳过跟 workbuddy builtin 同名 + 同名 backup，避免覆盖原生 skill
    if [ -d "$HOME/.workbuddy/skills/$skill_name" ] && [ ! -L "$HOME/.workbuddy/skills/$skill_name" ]; then
      :  # 真目录，workbuddy 原生，跳过
    else
      safe_symlink "$skill_dir" "$HOME/.workbuddy/skills/$skill_name"
    fi
  done
else
  warn "~/.workbuddy/skills 不存在，跳过（WorkBuddy 未安装？）"
fi

# 5. 项目级
echo "--- 项目级 skills ---"
WORKSPACE="$HOME/Desktop/量化投资程序"
if [ -d "$WORKSPACE" ]; then
  mkdir -p "$WORKSPACE/.agents/skills" "$WORKSPACE/skills"
  for skill_dir in "$PROJECT"/*/; do
    skill_name="$(basename "$skill_dir")"
    [[ "$skill_name" == .* || "$skill_name" == *.backup.* ]] && continue
    safe_symlink "$skill_dir" "$WORKSPACE/.agents/skills/$skill_name"
    safe_symlink "$skill_dir" "$WORKSPACE/skills/$skill_name"
  done
fi

# 6. ~/.kimi-code/skills 用户级
echo "--- ~/.kimi-code/skills (Kimi 专属) ---"
ensure_real_dir "$HOME/.kimi-code/skills"
for skill_dir in "$SHARED"/*/; do
  skill_name="$(basename "$skill_dir")"
  [[ "$skill_name" == .* || "$skill_name" == *.backup.* ]] && continue
  safe_symlink "$skill_dir" "$HOME/.kimi-code/skills/$skill_name"
done

# 7. ~/.kimi/skills 用户级（旧版 Kimi 兼容）
echo "--- ~/.kimi/skills (Kimi 旧目录兼容) ---"
ensure_real_dir "$HOME/.kimi/skills"
for skill_dir in "$SHARED"/*/; do
  skill_name="$(basename "$skill_dir")"
  [[ "$skill_name" == .* || "$skill_name" == *.backup.* ]] && continue
  safe_symlink "$skill_dir" "$HOME/.kimi/skills/$skill_name"
done

echo "============================================================"
echo "  完成！共享: $(ls "$SHARED" | wc -l | tr -d ' ') 个 | 项目: $(ls "$PROJECT" 2>/dev/null | wc -l | tr -d ' ') 个"
echo "============================================================"

#!/usr/bin/env bash
# skills-monorepo 状态体检（只读，macOS）
# 用法: bash scripts/status.sh
# 检查: 入口覆盖、死链、Parallels Windows、gh/git 推送工具
set -euo pipefail

MONOREPO="${SKILLS_MONOREPO:-$HOME/skills-monorepo}"
SHARED="$MONOREPO/shared"
PROJECT="$MONOREPO/project"
[ -d "$SHARED" ] || { echo "[!] 找不到 $SHARED"; exit 1; }

GREEN='\033[0;32m' YELLOW='\033[1;33m' RED='\033[0;31m' CYAN='\033[0;36m' NC='\033[0m'
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
bad()  { echo -e "${RED}[✗]${NC} $1"; }
hdr()  { echo -e "\n${CYAN}[$1]${NC} $2"; }

SHARED_COUNT="$(find "$SHARED" -mindepth 1 -maxdepth 1 -type d ! -name '.*' ! -name '*.backup.*' | wc -l | tr -d ' ')"
PROJECT_COUNT="$(find "$PROJECT" -mindepth 1 -maxdepth 1 -type d ! -name '.*' ! -name '*.backup.*' 2>/dev/null | wc -l | tr -d ' ')"
BRANCH="$(cd "$MONOREPO" && git branch --show-current 2>/dev/null || echo '?')"
REMOTE="$(cd "$MONOREPO" && git remote get-url origin 2>/dev/null || echo '无')"
DIRTY="$(cd "$MONOREPO" && git status -s 2>/dev/null | wc -l | tr -d ' ')"

echo "============================================================"
echo "  Skills Monorepo 状态体检"
echo "  仓库: $MONOREPO ($BRANCH) | shared: $SHARED_COUNT | project: $PROJECT_COUNT"
echo "============================================================"

hdr 1 "入口覆盖"

# 目录级 symlink 入口（整个目录指向 shared）
check_dirlink() {
  local dst="$1"
  if [ -L "$dst" ]; then
    local tgt; tgt="$(readlink "$dst")"
    if [ -e "$dst" ]; then ok "$dst → $tgt ($(ls "$dst" 2>/dev/null | wc -l | tr -d ' ') 个)"
    else bad "$dst → $tgt (死链：目标不存在)"; fi
  elif [ -d "$dst" ]; then
    warn "$dst 是真目录（非 symlink，未被 monorepo 接管）"
  else
    warn "$dst 不存在"
  fi
}
check_dirlink "$HOME/.agents/skills"

# 逐个 symlink 入口：统计已装/死链
check_entry() {
  local dst="$1" label="$2" expected="${3:-$SHARED_COUNT}"
  if [ ! -d "$dst" ]; then warn "$label: 不存在（跳过）"; return; fi
  local installed=0
  local -a deadlist=()
  # 用 find -type l 遍历，只看 symlink（跳过真目录如 workbuddy builtin），避免 glob 字面量陷阱
  while IFS= read -r -d '' link; do
    if [ -e "$link" ]; then installed=$((installed+1))
    else deadlist+=("$link"); fi
  done < <(find "$dst" -mindepth 1 -maxdepth 1 -type l -print0)
  local missing=$((expected - installed))
  if [ "${#deadlist[@]}" -gt 0 ]; then
    bad "$label: 已装 $installed | 死链 ${#deadlist[@]}"
    printf '      └ %s\n' "${deadlist[@]}"
  elif [ "$missing" -gt 0 ]; then
    warn "$label: 已装 ${installed} / 应装 ${expected}（缺 ${missing}，重跑 install.sh）"
  else
    ok "$label: 已装 ${installed} / ${expected}"
  fi
}
check_entry "$HOME/.codex/skills"    "~/.codex/skills"
check_entry "$HOME/.claude/skills"   "~/.claude/skills"
check_entry "$HOME/.workbuddy/skills" "~/.workbuddy/skills (含 builtin，installed 只计 monorepo 装的)"
check_entry "$HOME/.kimi-code/skills" "~/.kimi-code/skills"
check_entry "$HOME/.kimi/skills"      "~/.kimi/skills"
WS="${WORKSPACE:-$HOME/Desktop/量化投资程序}"
if [ -d "$WS" ]; then
  check_entry "$WS/.agents/skills" "项目 .agents/skills" "$PROJECT_COUNT"
  check_entry "$WS/skills"         "项目 skills"         "$PROJECT_COUNT"
fi

hdr 2 "Parallels Windows 检测"
if command -v prlctl >/dev/null 2>&1; then
  win_vm="$(prlctl list --all 2>/dev/null | tail -n +2 | awk '{ $1=$2=$3=""; sub(/^   /,""); print }' | grep -i 'windows' || true)"
  if [ -n "$win_vm" ]; then
    ok "prlctl 已安装，检测到 Windows VM: $(echo "$win_vm" | head -1)"
    ok "→ Windows 同步功能: 可用（可跑 sync-windows-skills.ps1）"
  else
    warn "prlctl 已安装，但未检测到 Windows VM"
    warn "→ Windows 同步功能: 退化（无 Windows 目标，跳过同步）"
  fi
else
  warn "prlctl 未安装（本机无 Parallels Desktop）"
  warn "→ Windows 同步功能: 退化（跳过 sync-windows-skills.ps1）"
fi

hdr 3 "推送工具"
if command -v gh >/dev/null 2>&1; then
  if gh auth status >/dev/null 2>&1; then ok "gh: 已安装且已认证"
  else warn "gh: 已安装但未认证（运行 gh auth login）"; fi
else
  warn "gh: 未安装（git push 失败时无法用 gh 自动重试）"
fi

hdr 4 "git 状态"
echo "  remote: $REMOTE"
if [ "$DIRTY" = "0" ]; then ok "工作区: 干净"
else warn "工作区: $DIRTY 个未提交变更"; fi

echo ""
echo "============================================================"
echo "  体检完成"
echo "============================================================"

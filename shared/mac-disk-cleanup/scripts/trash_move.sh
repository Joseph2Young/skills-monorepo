#!/bin/bash
# 将目标移入废纸篓（可恢复），并写入恢复映射表
#
# 用法：
#   source trash_move.sh
#   move "$HOME/.npm/_cacache"
#
# 环境变量（可选）：
#   TRASH_LOG_DIR  映射表输出目录，默认 /tmp

TS="${TRASH_TS:-$(date +%Y%m%d)}"
TRASH="$HOME/.Trash"
LOG_DIR="${TRASH_LOG_DIR:-/tmp}"
LOG="$LOG_DIR/恢复映射_${TS}.tsv"

mkdir -p "$LOG_DIR"
[ -f "$LOG" ] || printf "状态\t原始路径\t废纸篓位置\n" > "$LOG"

# 已知坑：这些情形会导致 mv 失败，需要重试
#   1) Broker request timed out —— 文件数过多（>1 万）或文件名含《》等特殊字符
#   2) Operation not permitted —— 目标受系统保护
move() {
  local src="$1"
  if [ ! -e "$src" ]; then
    printf "SKIP不存在\t%s\t-\n" "$src" >> "$LOG"
    echo "  SKIP  $src"
    return
  fi

  # 用完整路径生成唯一目标名，避免同名冲突且便于追溯
  local safe dst i
  safe=$(printf '%s' "$src" | sed 's|^/||; s|/|_|g')
  dst="$TRASH/${TS}__${safe}"
  i=1
  while [ -e "$dst" ]; do dst="${TS}__${safe}_$i"; dst="$TRASH/$dst"; i=$((i+1)); done

  # 带重试的移动（应对 broker IPC 超时）
  local attempt
  for attempt in 1 2 3 4 5; do
    mv "$src" "$dst" 2>/dev/null && break
    sleep 1
  done

  if [ -e "$src" ]; then
    printf "失败\t%s\t-\n" "$src" >> "$LOG"
    echo "  FAIL  $src"
  else
    printf "已移入废纸篓\t%s\t%s\n" "$src" "$dst" >> "$LOG"
    echo "  OK    $src"
  fi
}

# 批量移动某目录下的平行副本（Finder 复制产生的 "xxx 2" 目录）
# 用法：move_parallel_dupes "$HOME/project/node_modules"
move_parallel_dupes() {
  local parent="$1" p base dst ok=0 fail=0 n=0
  while IFS= read -r -d '' p; do
    n=$((n+1))
    base=$(basename "$p")
    dst="$TRASH/${TS}__dup_$(printf '%s' "$base" | tr ' ' '_' | tr -d '/')"
    local i=1; while [ -e "$dst" ]; do dst="${dst}_$i"; i=$((i+1)); done
    local attempt
    for attempt in 1 2 3; do
      mv "$p" "$dst" 2>/dev/null && break
      sleep 1
    done
    if [ -e "$p" ]; then echo "  FAIL  $base"; fail=$((fail+1)); else ok=$((ok+1)); fi
  done < <(find "$parent" -maxdepth 1 -name "* 2" -print0 2>/dev/null)
  echo "平行副本处理：$n 项，成功 $ok，失败 $fail"
}

# 检查原路径是否已清空（不要用 ls ~/.Trash 判断，那里会因权限返回空）
verify_gone() {
  local p
  for p in "$@"; do
    [ -e "$p" ] && echo "  仍存在: $p" || echo "  已移走: $p"
  done
}

echo "映射表: $LOG"
echo "提示：移入废纸篓后空间不会立即释放，需主人在 Finder 中按 ⌘⇧⌫ 清空。"

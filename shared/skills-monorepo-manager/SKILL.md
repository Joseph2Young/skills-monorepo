---
name: skills-monorepo-manager
description: "统一管理跨平台 Skills Monorepo（macOS + Parallels Windows）。支持体检/同步/添加/删除/修改/查找/安装 skills，自动处理 GitHub 推送（gh CLI）和 symlink 安装与死链清理。触发词：管理skills、同步skills、添加skill、删除skill、修改skill、查找skill、安装skill、部署skills、体检skills、skills状态"
---

# Skills Monorepo Manager

统一管理跨平台（macOS + Parallels Windows）的 skills 仓库。所有 skill 文件**只存一份**在 `~/skills-monorepo/`，各客户端通过 symlink 读取，改一处全局生效。

## 仓库结构

```
~/skills-monorepo/
├── shared/                                       # 全局 skills（所有客户端共用）
├── project/                                      # 项目级 skills（仅挂到指定工作区）
├── install.sh / install.ps1                      # macOS / Windows symlink 安装
├── uninstall.sh                                  # macOS 卸载
├── README.md
└── shared/skills-monorepo-manager/scripts/
    ├── status.sh                                 # macOS 状态体检（只读）
    └── sync-windows-skills.ps1                   # Windows → monorepo 同步（在 Windows 跑）
```

## 核心心智模型（必须理解）

数据流向是**双向但分职能**的，两个脚本各管一个方向：

| 方向 | 用什么 | 做什么 |
|------|--------|--------|
| **Windows → monorepo** | `sync-windows-skills.ps1`（在 Windows 跑） | 把 Windows 独有的新 skill **复制文件**进 monorepo |
| **monorepo → 各端** | `install.sh`（macOS）/ `install.ps1`（Windows） | 为每个客户端**建 symlink** 指向 monorepo |

> ⚠️ 常见困惑：「我在 macOS 加了 skill，为什么 Windows 看不到？」→ 因为 Windows 端还没跑 `install.ps1` 重建 symlink。sync 只管进，install 只管铺。

## 入口矩阵（install.sh 实际覆盖，操作时以此为准）

| 客户端路径 | 挂载方式 | 备注 |
|-----------|---------|------|
| `~/.agents/skills` | 目录级 symlink → shared/ | Codex + Claude Code 共用 |
| `~/.codex/skills/{skill}/` | 逐个 symlink | 不动 `.system/` 内置目录 |
| `~/.claude/skills/{skill}/` | 逐个 symlink | Claude Code |
| `~/.workbuddy/skills/{skill}/` | 逐个 symlink | 跳过 builtin 真目录，仅当 `~/.workbuddy` 存在 |
| `~/.kimi-code/skills/{skill}/` | 逐个 symlink | Kimi |
| `~/.kimi/skills/{skill}/` | 逐个 symlink | Kimi 旧目录兼容 |
| `$WORKSPACE/.agents/skills/{skill}/`、`$WORKSPACE/skills/{skill}/` | 逐个 symlink | 项目级（来自 project/） |

- `$WORKSPACE` 默认 `~/Desktop/量化投资程序`，可用环境变量覆盖；不存在则自动跳过项目级。
- macOS 与 Windows 的 install 脚本**入口口径一致**（都覆盖上述全部入口）。

---

## 操作前必做：体检（status）

**任何操作前先跑一次体检**，掌握当前状态再动手：

```bash
bash ~/skills-monorepo/shared/skills-monorepo-manager/scripts/status.sh
```

输出包含：各入口已装/缺失/死链计数、Parallels Windows 检测、`gh`/`git` 状态。**死链和缺失一目了然**，避免盲操作。

---

## 操作命令参考

### 1. 同步（sync）—— Windows → monorepo

**场景**：Windows 端积累了新 skill，要收入 monorepo。

**前置：Parallels 退化判断**（第 11 条铁律）。在 macOS 端发起同步前，必须先确认本机有可用的 Parallels Windows：

```bash
# 检测：prlctl 存在 且 有可用 Windows VM（状态为 invalid 的 VM 视为不可用）
command -v prlctl >/dev/null 2>&1 && \
  prlctl list --all 2>/dev/null | tail -n +2 | grep -i 'windows' | grep -qvi 'invalid'
```

- 返回 **0**（有可用的 Parallels Windows）→ 让用户在 Windows 里跑下面的 `sync-windows-skills.ps1`。
- 返回 **非 0**（无 prlctl、无 Windows VM、或 VM 状态为 invalid 损坏不可用）→ **直接退化**：告知用户「未检测到可用的 Parallels Windows，Windows 同步已跳过」，只做 macOS 侧同步，不要让用户白跑脚本。可直接 `bash scripts/status.sh` 看 Parallels 检测结果（含 VM 状态）。

**Windows 端执行**（用户在 Windows PowerShell 里跑，不要内联代码——直接调用脚本）：

```powershell
powershell -ExecutionPolicy Bypass -File \\Mac\Home\skills-monorepo\shared\skills-monorepo-manager\scripts\sync-windows-skills.ps1
```

脚本自动完成：跳过 `.backup.*`、跳过 monorepo 已有的同名 skill、从 Claude Code 和 Codex 两处收集独有 skill、复制进 `shared/`、末尾自动调用 `install.ps1` 重建 Windows symlink。

**同步后推送**（macOS 端）：

```bash
cd ~/skills-monorepo
git add -A
git commit -m "sync: 从 Windows 同步 N 个新 skills"
push_to_git   # 见第 7 节
```

---

### 2. 添加（add）

**场景**：用户说「添加一个叫 xxx 的 skill」或有新 skill 目录要加入。

```bash
# 1. 复制到 monorepo（全局放 shared/，项目级放 project/）
cp -r /path/to/new-skill ~/skills-monorepo/shared/

# 2. 安装 symlink（macOS）
bash ~/skills-monorepo/install.sh

# 3. 验证
ls -la ~/.codex/skills/new-skill ~/.claude/skills/new-skill

# 4. 提交推送
cd ~/skills-monorepo
git add shared/new-skill/
git commit -m "add: new-skill - 简要描述"
push_to_git
```

> 提醒用户：Windows 端也需要跑 `install.ps1` 才能看到新 skill。

---

### 3. 删除（delete）—— 带护栏 + 必须确认

**场景**：用户说「删除 xxx skill」。

**铁律（CLAUDE.md 权限红线）**：禁止 `rm -rf`。删除前必须①校验 skill 名非空且路径在 monorepo 下，②**列出 skill 内容与用户确认要删哪些**，③用 `rm -r`（非 `-rf`）或 `git rm -r`。

```bash
SKILL=skill-name
TARGET="$HOME/skills-monorepo/shared/$SKILL"

# ① 护栏：skill 名非空 + 路径在 monorepo 下
[ -n "$SKILL" ] || { echo "[!] skill 名为空，中止"; exit 1; }
REAL="$(cd "$TARGET" 2>/dev/null && pwd)" || { echo "[!] 不存在: $TARGET"; exit 1; }
case "$REAL" in
  "$HOME/skills-monorepo"/shared/*|"$HOME/skills-monorepo"/project/*) : ;;
  *) echo "[!] 拒绝：路径越出 monorepo: $REAL"; exit 1 ;;
esac

# ② 列出内容，向用户确认（agent 用 AskUserQuestion 或文字确认，得到明确「删」才继续）
echo "[i] 将删除: $REAL"; ls -la "$REAL"

# ③ 确认后执行（rm -r，不是 -rf）
rm -r "$REAL"

# ④ 更新 symlink（install.sh 末尾会清理这个 skill 留下的死链）
bash ~/skills-monorepo/install.sh

# ⑤ 提交推送
cd ~/skills-monorepo
git rm -r "shared/$SKILL"
git commit -m "remove: $SKILL"
push_to_git
```

---

### 4. 修改（modify）

**场景**：用户说「修改 xxx skill 的 SKILL.md」或「更新 xxx skill」。

**单文件编辑**（首选，最精准）：

```bash
# 直接编辑 monorepo 中的文件（各客户端 symlink 即时生效）
"${EDITOR:-vi}" ~/skills-monorepo/shared/skill-name/SKILL.md
```

**整目录替换**（仅当确实要整体替换时，套用与 delete 相同的护栏，先确认再 `rm -r` + `cp -r`）：

```bash
SKILL=skill-name
TARGET="$HOME/skills-monorepo/shared/$SKILL"
# 同 delete 的 ①②护栏 + 确认
rm -r "$TARGET"
cp -r /path/to/updated-skill/ "$TARGET"
```

```bash
cd ~/skills-monorepo
git add shared/skill-name/
git commit -m "update: skill-name - 更新说明"
push_to_git
```

---

### 5. 查找（find）

```bash
# 按名称
ls ~/skills-monorepo/shared/ | grep -i keyword

# 按 SKILL.md 描述
grep -rl "keyword" ~/skills-monorepo/shared/*/SKILL.md 2>/dev/null

# 按文件内容
grep -rl "keyword" ~/skills-monorepo/shared/*/ --include="*.md" 2>/dev/null

# 查看详情
head -20 ~/skills-monorepo/shared/skill-name/SKILL.md
```

---

### 6. 安装（install）—— 安装/更新 symlink

**macOS**：

```bash
bash ~/skills-monorepo/install.sh
# 脚本末尾自动清理各入口的死链（monorepo 里已删 skill 留下的断链）
```

**Parallels Windows**（让用户在 Windows 执行）：

```powershell
powershell -ExecutionPolicy Bypass -File \\Mac\Home\skills-monorepo\install.ps1
```

**验证**：跑 `bash scripts/status.sh`，看各入口「已装 / 应装」是否对齐、有无死链。

---

### 7. GitHub 推送辅助（push_to_git，默认 gh CLI）

**所有操作的推送统一调用此函数**（替代旧的空壳 `github_api_push`）。策略：先 `git push`，失败则用 `gh auth setup-git` 注入凭据后重试；再失败提示用户手动推。

```bash
push_to_git() {
  cd ~/skills-monorepo || return 1
  if git push origin main 2>&1; then
    echo "[✓] 推送成功"
    return 0
  fi
  echo "[!] git push 失败，尝试用 gh CLI 认证后重试..."
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    gh auth setup-git && git push origin main && { echo "[✓] gh 重试成功"; return 0; }
  fi
  echo "[!] 自动推送失败。请在终端手动执行：cd ~/skills-monorepo && git push origin main"
  return 1
}
```

---

## 完整工作流示例

### 「同步 Windows 的 skills 到 monorepo」

1. macOS 端先检测 Parallels Windows（见第 1 节退化判断）；没有就直接退化、告知用户跳过。
2. 有的话，让用户在 Windows 跑 `sync-windows-skills.ps1`。
3. 等用户确认执行完毕。
4. macOS 侧验证：`ls ~/skills-monorepo/shared/`（新 skill 已出现）。
5. 跑 `install.sh` 更新 macOS symlink。
6. `git add → commit → push_to_git`。

### 「添加一个新 skill」

1. 确认 skill 名称和来源。
2. 决定 shared（全局）还是 project（项目级）。
3. 复制到对应目录 → `install.sh` → `status.sh` 验证 → git 提交推送。
4. 提醒用户 Windows 端跑 `install.ps1`。

### 「查找关于回测的 skill」

1. `ls ~/skills-monorepo/shared/ | grep -i backtest`
2. `grep -rl -i "backtest\|回测" ~/skills-monorepo/shared/*/SKILL.md`
3. 展示匹配列表 + 简短描述，需要详情再 `head -20`。

---

## 注意事项

- **文件权限**：monorepo 在 `~/skills-monorepo/`，沙箱不可写时用提权；写入受限时**不要**越过报错强推，按「错误降级策略」汇报。
- **网络限制**：沙箱可能阻止出站 HTTPS。`git push` 失败走 `push_to_git`（gh 重试）；仍失败则**提示用户手动**，不要静默吞错。
- **Windows 路径**：通过 Parallels 共享文件夹 `\\Mac\Home\skills-monorepo` 访问；本机无 Parallels、无 Windows VM 或 VM 状态为 invalid 时退化、跳过 Windows 同步（只做 macOS 侧）。
- **删除红线**：禁止 `rm -rf`；删除/整体替换必须走第 3 节护栏（非空校验 + 路径在 monorepo 下 + 用户确认 + `rm -r`/`git rm -r`）。
- **版本化 skills**：`skill-name` 与 `skill-name-1.0.0` 是同一 skill 的不同版本。规则是**带版本号的视为新版优先保留**，无版本号的同名 bare 目录视为旧版；`sync-windows-skills.ps1` 内置跳过表（brainstorming/executing-plans/frontend-design/skill-creator/writing-plans）即此规则的实例，新增版本化 skill 时更新该表。
- **备份目录**：`.backup.*` 后缀是 install 时自动备份，**不纳入** monorepo、不提交 git。
- **全局 vs 项目级**：`shared/` 放所有客户端共用的 skill；`project/` 仅放只属于某个工作区的 skill。当前 `jq-full-optimizer`、`sop-factory` 均为**全局共用**（在 shared/），`project/` 为空——勿再误当作项目级处理。
- **.system 目录**：`~/.codex/skills/.system/` 是 Codex 内置系统 skill，**绝不**纳入管理。
- **WORKSPACE**：项目级默认 `~/Desktop/量化投资程序`，可用 `WORKSPACE=/path bash install.sh` 覆盖；不存在则自动跳过项目级（不报错）。

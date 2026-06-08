---
name: skills-monorepo-manager
description: "统一管理跨平台 Skills Monorepo（macOS + Parallels Windows）。支持同步/添加/删除/修改/查找 skills，自动处理 GitHub 推送和 symlink 安装。触发词：管理skills、同步skills、添加skill、删除skill、修改skill、查找skill、安装skill、部署skills"
---

# Skills Monorepo Manager

统一管理跨平台（macOS + Parallels Windows）的 skills 仓库。

## 仓库结构

```
~/skills-monorepo/
├── shared/          # 全局 skills（Codex + Claude Code 共用）
├── project/         # 项目级 skills
├── install.sh       # macOS symlink 安装
├── install.ps1      # Windows symlink 安装
├── uninstall.sh     # macOS 卸载
└── README.md
```

## 前置条件检查

在操作前先检查：

1. **monorepo 是否存在**: `ls ~/skills-monorepo/`
2. **GitHub remote**: `cd ~/skills-monorepo && git remote -v`
3. **GitHub token**: 若需推送但远程含 token 的 URL 失效，提示用户："请提供 GitHub Personal Access Token（需要 repo 权限）"
4. **当前平台**: 通过 `uname` 检测（Darwin=macOS, 否则可能是 Parallels Windows）

## 操作命令参考

### 1. 同步（sync）—— 跨平台 skills 同步

**场景**: 用户在 macOS 或 Windows 上积累了自己的 skills，需要同步到 monorepo。

**macOS 端同步**:
```bash
# 检查 monorepo 是否存在
cd ~/skills-monorepo

# 查看当前的 skill 目录
ls shared/
ls project/

# 检查是否安装了 symlink
readlink ~/.agents/skills
ls ~/.codex/skills/ | wc -l
ls ~/.claude/skills/ | wc -l
```

**Parallels Windows 端同步**（需要用户在 Windows 里执行）:
```powershell
# 在 Windows PowerShell 中执行
$Monorepo = "\\Mac\Home\skills-monorepo"
$Shared = Join-Path $Monorepo "shared"
$ClaudeSkills = "$env:USERPROFILE\.claude\skills"

# 找出 Windows 独有 skills（不在 monorepo 里的）
$existing = @{}
Get-ChildItem $Shared -Directory | ForEach-Object { $existing[$_.Name] = $true }

$newSkills = Get-ChildItem $ClaudeSkills -Directory | Where-Object {
    $name = $_.Name
    # 跳过备份目录和版本化 duplicates
    $name -notmatch '\.backup\.' -and
    -not $existing.ContainsKey($name)
}

# 显示新 skills
$newSkills | Select-Object Name
Write-Host "发现 $($newSkills.Count) 个需要同步的新 skills"

# 复制到 monorepo
foreach ($skill in $newSkills) {
    $dest = Join-Path $Shared $skill.Name
    Copy-Item -Path $skill.FullName -Destination $dest -Recurse -Force
    Write-Host "[OK] $($skill.Name)"
}

# 安装 symlink
powershell -ExecutionPolicy Bypass -File (Join-Path $Monorepo "install.ps1")
```

**同步后的 GitHub 推送**:
```bash
cd ~/skills-monorepo
git add -A
git commit -m "sync: 从 Windows 同步 N 个新 skills"
# 尝试推送，若网络不通则用 API
git push origin main 2>&1 || github_api_push
```

---

### 2. 添加（add）—— 添加新 skill

**场景**: 用户说"添加一个叫 xxx 的 skill" 或有新的 skill 目录要加入。

```bash
# 1. 复制到 monorepo
cp -r /path/to/new-skill ~/skills-monorepo/shared/
# 或如果是项目级 skill
cp -r /path/to/project-skill ~/skills-monorepo/project/

# 2. 安装 symlink
bash ~/skills-monorepo/install.sh

# 3. 验证
ls ~/.codex/skills/new-skill/
ls ~/.claude/skills/new-skill/

# 4. 提交到 git
cd ~/skills-monorepo
git add shared/new-skill/
git commit -m "add: new-skill - 简要描述"
git push origin main 2>&1 || github_api_push
# 如果 push 失败，提示用户在终端手动 git push
```

---

### 3. 删除（delete）—— 删除 skill

**场景**: 用户说"删除 xxx skill"。

```bash
# 1. 确认要删除的 skill 存在
ls ~/skills-monorepo/shared/skill-name/

# 2. 删除
rm -rf ~/skills-monorepo/shared/skill-name/

# 3. 更新 symlink（重新安装会清理不存在的）
bash ~/skills-monorepo/install.sh

# 4. 提交
cd ~/skills-monorepo
git rm -r shared/skill-name/
git commit -m "remove: skill-name"
git push origin main 2>&1 || github_api_push
```

---

### 4. 修改（modify）—— 修改已有 skill

**场景**: 用户说"修改 xxx skill 的 SKILL.md" 或 "更新 xxx skill"。

```bash
# 直接编辑 monorepo 中的文件
vim ~/skills-monorepo/shared/skill-name/SKILL.md
# 或替换整个 skill 目录
rm -rf ~/skills-monorepo/shared/skill-name/
cp -r /path/to/updated-skill/ ~/skills-monorepo/shared/skill-name/

# 提交
cd ~/skills-monorepo
git add shared/skill-name/
git commit -m "update: skill-name - 更新说明"
git push origin main 2>&1 || github_api_push
```

---

### 5. 查找（find）—— 查找 skill

**场景**: 用户说"查找 xxx skill" 或 "有没有关于 xxx 的 skill"。

```bash
# 按名称搜索
ls ~/skills-monorepo/shared/ | grep -i keyword

# 按描述搜索（从 SKILL.md 中找）
grep -rl "keyword" ~/skills-monorepo/shared/*/SKILL.md 2>/dev/null

# 按文件内容搜索
grep -rl "keyword" ~/skills-monorepo/shared/*/ --include="*.md" 2>/dev/null

# 查看 skill 详情
head -10 ~/skills-monorepo/shared/skill-name/SKILL.md
```

---

### 6. 安装（install）—— 安装/更新 symlink

**场景**: 用户说"安装 skills" 或 "更新 symlink"。

**macOS**:
```bash
bash ~/skills-monorepo/install.sh
```

**Parallels Windows**（让用户在 Windows 执行）:
```powershell
powershell -ExecutionPolicy Bypass -File \\Mac\Home\skills-monorepo\install.ps1
```

**验证安装**:
```bash
# macOS
readlink ~/.agents/skills
ls ~/.codex/skills/ | wc -l
ls ~/.claude/skills/ | wc -l

# Windows（在 CMD/PowerShell 中）
dir %USERPROFILE%\.agents\skills
dir %USERPROFILE%\.codex\skills | find /c "<DIR>"
dir %USERPROFILE%\.claude\skills | find /c "<DIR>"
```

---

### 7. GitHub 推送辅助（github_api_push）

**场景**: 沙箱环境无法直连 github.com，需要用 GitHub API。

```bash
# haPushToGitHub(){
#   local token="$1"  # 需要用户提供
#   local repo="$2"   # Joseph2Young/skills-monorepo
#   local msg="$3"    # commit message
#   
#   base64 -i install.ps1 | tr -d '\n'
#   # 用 GitHub Contents API 推送关键文件
#   curl -s -X PUT \
#     -H "Authorization: token $token" \
#     -H "Accept: application/vnd.github.v3+json" \
#     "https://api.github.com/repos/$repo/contents/path/to/file" \
#     -d "{\"message\":\"$msg\",\"content\":\"$b64\",\"sha\":\"$sha\",\"branch\":\"main\"}"
# }
```

**常规推送（用户终端）**: 如果 agent 推不动，提示用户在自己的终端执行：
```bash
cd ~/skills-monorepo
git push origin main
```

---

## 完整工作流示例

### 用户说"同步 Windows 的 skills 到 monorepo"

1. 检查 monorepo 是否存在 → `ls ~/skills-monorepo/`
2. 确认当前是 macOS 还是 Windows
3. 如果当前是 macOS：
   - 告诉用户需要在 Windows 上执行同步脚本
   - 提供 Windows PowerShell 命令
4. 等待用户确认执行完毕
5. 从 macOS 侧验证新 skills 已出现 → `ls ~/skills-monorepo/shared/`
6. 检查 `jq-full-optimizer` 是否从 shared/ 移到了 project/
7. 运行 `bash ~/skills-monorepo/install.sh` 更新 macOS symlink
8. git add → commit → push

### 用户说"添加一个新 skill"

1. 确认 skill 名称和来源
2. 决定是 shared（全局）还是 project（项目级）
3. 复制到对应目录
4. 运行 `install.sh`
5. 验证 symlink
6. git add → commit → push
7. 告知用户 Windows 上也需要跑 `install.ps1`

### 用户说"查找关于回测的 skill"

1. `ls ~/skills-monorepo/shared/ | grep -i backtest`
2. `grep -rl -i "backtest\|回测" ~/skills-monorepo/shared/*/SKILL.md 2>/dev/null`
3. 显示匹配的 skills 列表和简短描述
4. 如果用户想查看详情，`head -20 shared/skill-name/SKILL.md`

## 注意事项

- **文件权限**: monorepo 目录在 `~/skills-monorepo/`，可能不在沙箱可写范围内，需要用 `require_escalated`
- **网络限制**: 沙箱可能阻止出站 HTTPS，`git push` 失败时用 GitHub API 或提示用户手动执行
- **Windows 路径**: 通过 Parallels 共享文件夹 `\\Mac\Home\skills-monorepo` 访问
- **版本化 skills**: `skill-name` vs `skill-name-1.0.0` 是同一 skill 的不同版本，只保留最新的
- **备份目录**: `.backup.*` 后缀的目录是自动备份，不需要同步到 monorepo
- **项目级 skill**: 属于特定工作区的 skill 放 `project/`（如 `jq-full-optimizer`、`sop-factory`）
- **.system 目录**: `~/.codex/skills/.system/` 是 Codex 内置系统 skill，不纳入管理

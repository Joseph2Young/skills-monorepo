# ============================================================
# Skills Monorepo 安装脚本 (Parallels Desktop / Windows)
# 用法: powershell -ExecutionPolicy Bypass -File install.ps1
# 前提: Parallels 共享文件夹已启用，Mac Home 映射到 \\Mac\Home
# ============================================================

$ErrorActionPreference = "Stop"

# Parallels 共享文件夹中 Mac Home 的路径
$MacHome = "\\Mac\Home"
$Monorepo = Join-Path $MacHome "skills-monorepo"
$Shared = Join-Path $Monorepo "shared"
$Project = Join-Path $Monorepo "project"

# Windows 端各工具的 skills 路径
$AgentsSkills = Join-Path $env:USERPROFILE ".agents\skills"
$CodexSkills = Join-Path $env:USERPROFILE ".codex\skills"
$ClaudeSkills = Join-Path $env:USERPROFILE ".claude\skills"

function Safe-Symlink {
    param([string]$Src, [string]$Dst)
    
    # Windows symlink 需要检查是否已有
    if (Test-Path $Dst) {
        $item = Get-Item $Dst -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $currentTarget = $item.Target
            if ($currentTarget -eq $Src) {
                Write-Host "[OK] $Dst -> $Src" -ForegroundColor Green
                return
            }
            Remove-Item $Dst -Force
        } else {
            $backup = "${Dst}.backup.$(Get-Date -Format 'yyyyMMddHHmmss')"
            Write-Host "[!] 备份 $Dst -> $backup" -ForegroundColor Yellow
            Move-Item $Dst $backup
        }
    }
    
    # 确保父目录存在
    $parent = Split-Path $Dst -Parent
    if (!(Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    
    # 使用目录 junction（不需要管理员权限，且支持网络路径）
    New-Item -ItemType Junction -Path $Dst -Target $Src | Out-Null
    Write-Host "[+] $Dst -> $Src" -ForegroundColor Green
}

Write-Host "============================================================"
Write-Host "  Skills Monorepo 安装 (Parallels Windows)"
Write-Host "  仓库: $Monorepo"
Write-Host "============================================================"

# 验证 Parallels 共享文件夹可用
if (!(Test-Path $Monorepo)) {
    Write-Host "[!] 找不到 $Monorepo" -ForegroundColor Red
    Write-Host "    请确认 Parallels 共享文件夹已启用"
    exit 1
}

# 1. ~/.agents/skills
Write-Host "`n--- ~/.agents/skills (Codex + Claude Code 共用) ---"
Safe-Symlink -Src $Shared -Dst $AgentsSkills

# 2. ~/.codex/skills
Write-Host "`n--- ~/.codex/skills (Codex 专属) ---"
if (Test-Path $Shared) {
    Get-ChildItem $Shared -Directory | ForEach-Object {
        Safe-Symlink -Src $_.FullName -Dst (Join-Path $CodexSkills $_.Name)
    }
}

# 3. ~/.claude/skills
Write-Host "`n--- ~/.claude/skills (Claude Code 专属) ---"
if (Test-Path $Shared) {
    Get-ChildItem $Shared -Directory | ForEach-Object {
        Safe-Symlink -Src $_.FullName -Dst (Join-Path $ClaudeSkills $_.Name)
    }
}

# 4. 项目级 skills
Write-Host "`n--- 项目级 skills ---"
$Workspace = Join-Path $MacHome "Desktop\量化投资程序"
if (Test-Path $Project) {
    Get-ChildItem $Project -Directory | ForEach-Object {
        Safe-Symlink -Src $_.FullName -Dst (Join-Path "$Workspace\.agents\skills" $_.Name)
        Safe-Symlink -Src $_.FullName -Dst (Join-Path "$Workspace\skills" $_.Name)
    }
}

$sharedCount = (Get-ChildItem $Shared -Directory).Count
$projectCount = (Get-ChildItem $Project -Directory -ErrorAction SilentlyContinue).Count
Write-Host "`n============================================================"
Write-Host "  完成！共享: $sharedCount 个 | 项目: $projectCount 个"
Write-Host "============================================================"

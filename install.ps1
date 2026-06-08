# ============================================================
# Skills Monorepo install script (Parallels Desktop / Windows)
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1
# ============================================================

$ErrorActionPreference = "Stop"

$MacHome = "\\Mac\Home"
$Monorepo = Join-Path $MacHome "skills-monorepo"
$Shared = Join-Path $Monorepo "shared"
$Project = Join-Path $Monorepo "project"

$AgentsSkills = Join-Path $env:USERPROFILE ".agents\skills"
$CodexSkills = Join-Path $env:USERPROFILE ".codex\skills"
$ClaudeSkills = Join-Path $env:USERPROFILE ".claude\skills"

function Safe-Symlink {
    param([string]$Src, [string]$Dst)

    if (Test-Path $Dst) {
        $item = Get-Item $Dst -Force
        $isSymlink = $item.Attributes -band [System.IO.FileAttributes]::ReparsePoint
        if ($isSymlink) {
            Remove-Item $Dst -Force
        } else {
            $backup = $Dst + ".backup." + (Get-Date -Format "yyyyMMddHHmmss")
            Write-Host "[!] Backup $Dst -> $backup" -ForegroundColor Yellow
            Move-Item $Dst $backup
        }
    }

    $parent = Split-Path $Dst -Parent
    if (!(Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    New-Item -ItemType Junction -Path $Dst -Target $Src | Out-Null
    Write-Host "[OK] $Dst -> $Src" -ForegroundColor Green
}

Write-Host "============================================================"
Write-Host "  Skills Monorepo Setup (Parallels Windows)"
Write-Host "  Repo: $Monorepo"
Write-Host "============================================================"

if (!(Test-Path $Monorepo)) {
    Write-Host "[!] Cannot find $Monorepo" -ForegroundColor Red
    Write-Host "    Please enable Parallels shared folders"
    exit 1
}

Write-Host "--- ~/.agents/skills (Codex + Claude Code shared) ---"
Safe-Symlink -Src $Shared -Dst $AgentsSkills

Write-Host "--- ~/.codex/skills (Codex only) ---"
if (Test-Path $Shared) {
    Get-ChildItem $Shared -Directory | ForEach-Object {
        Safe-Symlink -Src $_.FullName -Dst (Join-Path $CodexSkills $_.Name)
    }
}

Write-Host "--- ~/.claude/skills (Claude Code only) ---"
if (Test-Path $Shared) {
    Get-ChildItem $Shared -Directory | ForEach-Object {
        Safe-Symlink -Src $_.FullName -Dst (Join-Path $ClaudeSkills $_.Name)
    }
}

Write-Host "--- Project-level skills ---"
$Workspace = Join-Path $MacHome "Desktop\量化投资程序"
if (Test-Path $Project) {
    Get-ChildItem $Project -Directory | ForEach-Object {
        $agentsDst = Join-Path (Join-Path $Workspace ".agents\skills") $_.Name
        $skillsDst = Join-Path (Join-Path $Workspace "skills") $_.Name
        Safe-Symlink -Src $_.FullName -Dst $agentsDst
        Safe-Symlink -Src $_.FullName -Dst $skillsDst
    }
}

$sharedCount = (Get-ChildItem $Shared -Directory).Count
$projectCount = (Get-ChildItem $Project -Directory -ErrorAction SilentlyContinue).Count
Write-Host "Done! Shared: $sharedCount  Project: $projectCount"

# sync-windows-skills.ps1
# 从 Windows Claude Code / Codex 收集独有 skills 到 monorepo
# 用法: powershell -ExecutionPolicy Bypass -File sync-windows-skills.ps1

$ErrorActionPreference = "Stop"

$Monorepo = "\\Mac\Home\skills-monorepo"
$Shared = Join-Path $Monorepo "shared"
$Project = Join-Path $Monorepo "project"

$ClaudeSkills = "$env:USERPROFILE\.claude\skills"
$CodexSkills = "$env:USERPROFILE\.codex\skills"
$AgentsSkills = "$env:USERPROFILE\.agents\skills"

# 版本化 skills（monorepo 里已存在带版本号的同名 skill）
$versioned = @{
    "brainstorming" = $true
    "executing-plans" = $true
    "frontend-design" = $true
    "skill-creator" = $true
    "writing-plans" = $true
}

Write-Host "============================================================"
Write-Host "  Skills Monorepo Windows Sync"
Write-Host "  Monorepo: $Monorepo"
Write-Host "============================================================"

# 检查 monorepo 是否可访问
if (!(Test-Path $Monorepo)) {
    Write-Host "[!] 错误: 无法访问 $Monorepo" -ForegroundColor Red
    Write-Host "    请确保 Parallels 共享文件夹已启用" 
    exit 1
}

# 建立 monorepo 已有 skills 的索引
$existing = @{}
Get-ChildItem $Shared -Directory | ForEach-Object {
    $existing[$_.Name] = $true
}

Write-Host "--- 从 Claude Code 收集独有 skills ---"
$newClaude = @()
if (Test-Path $ClaudeSkills) {
    Get-ChildItem $ClaudeSkills -Directory | ForEach-Object {
        $name = $_.Name
        if ($name -match '\.backup\.') { return }          # 跳过备份
        if ($versioned.ContainsKey($name)) { 
            Write-Host "[跳过] $name (已存在版本化版本)" -ForegroundColor DarkGray
            return 
        }
        if ($existing.ContainsKey($name)) {
            Write-Host "[已存在] $name" -ForegroundColor DarkGray
            return
        }
        $newClaude += $_
    }
}

Write-Host "--- 从 Codex 收集独有 skills ---"
$newCodex = @()
if (Test-Path $CodexSkills) {
    Get-ChildItem $CodexSkills -Directory | ForEach-Object {
        $name = $_.Name
        if ($name -eq '.system') { return }                # 跳过系统 skill
        if ($name -match '\.backup\.') { return }
        if ($versioned.ContainsKey($name)) { return }
        if ($existing.ContainsKey($name)) { return }
        $newCodex += $_
    }
}

$allNew = $newClaude + $newCodex | Sort-Object -Property Name -Unique

if ($allNew.Count -eq 0) {
    Write-Host "[!] 没有发现需要同步的新 skills" -ForegroundColor Yellow
} else {
    Write-Host "发现 $($allNew.Count) 个新 skills:" -ForegroundColor Cyan
    foreach ($skill in $allNew) {
        Write-Host "  [+] $($skill.Name)" -ForegroundColor Green
    }
    
    Write-Host "--- 复制到 monorepo ---"
    foreach ($skill in $allNew) {
        $dest = Join-Path $Shared $skill.Name
        Write-Host "  复制: $($skill.Name) ..." -NoNewline
        Copy-Item -Path $skill.FullName -Destination $dest -Recurse -Force
        Write-Host " OK" -ForegroundColor Green
    }
}

# 检查项目级 skills
Write-Host "--- 检查项目级 skills ---"
$projectClaude = Join-Path $ClaudeSkills "jq-full-optimizer"
$projectDst = Join-Path $Project "jq-full-optimizer"
if (Test-Path $projectClaude) {
    if (!(Test-Path $projectDst)) {
        Write-Host "[+] 复制项目级 skill: jq-full-optimizer" -ForegroundColor Cyan
        Copy-Item -Path $projectClaude -Destination $projectDst -Recurse -Force
    } else {
        Write-Host "[已存在] project/jq-full-optimizer"
    }
}

# 更新计数
$sharedCount = (Get-ChildItem $Shared -Directory).Count
$projectCount = (Get-ChildItem $Project -Directory -ErrorAction SilentlyContinue).Count
Write-Host "--- 同步完成！shared: $sharedCount | project: $projectCount ---" -ForegroundColor Green

# 安装 symlink
Write-Host "--- 运行 install.ps1 更新 symlink ---"
$installScript = Join-Path $Monorepo "install.ps1"
& $installScript

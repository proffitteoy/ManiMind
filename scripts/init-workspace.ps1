<#
.SYNOPSIS
初始化 ManiMind 工作区目录与基础占位文件。
#>

param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$workspaceDirs = @(
    "configs",
    "scripts",
    "src",
    "src\manimind",
    "tests",
    "resources",
    "resources\skills",
    "resources\skills\html-animation",
    "resources\skills\manim",
    "resources\references",
    "resources\references\hyperframes",
    "runtime",
    "runtime\projects",
    "runtime\sessions",
    "runtime\cache",
    "outputs",
    "logs"
)

$requiredPaths = @(
    "docs",
    "resources\skills\html-animation",
    "resources\skills\manim\SKILL.md",
    "resources\references\hyperframes"
)

$created = @()
$validated = @()
$missing = @()

foreach ($dir in $workspaceDirs) {
    $target = Join-Path $Root $dir
    if (-not (Test-Path $target)) {
        New-Item -ItemType Directory -Path $target | Out-Null
        $created += $dir
    }
}

foreach ($relativePath in $requiredPaths) {
    $target = Join-Path $Root $relativePath
    if (Test-Path $target) {
        $validated += $relativePath
    }
    else {
        $missing += $relativePath
    }
}

$gitkeepTargets = @(
    "runtime\projects\.gitkeep",
    "runtime\sessions\.gitkeep",
    "runtime\cache\.gitkeep",
    "outputs\.gitkeep",
    "logs\.gitkeep"
)

foreach ($relativeFile in $gitkeepTargets) {
    $target = Join-Path $Root $relativeFile
    if (-not (Test-Path $target)) {
        New-Item -ItemType File -Path $target | Out-Null
    }
}

$manimSkillFile = Join-Path $Root "resources\skills\manim\SKILL.md"
if (-not (Test-Path -LiteralPath $manimSkillFile)) {
    @"
# Manim Skill Placeholder

Run scripts/sync-thirdparty-assets.ps1 to sync full skill content.
"@ | Set-Content -Path $manimSkillFile -Encoding UTF8
}

$report = [ordered]@{
    root = $Root
    created_directories = $created
    validated_paths = $validated
    missing_paths = $missing
    timestamp = (Get-Date).ToString("s")
}

$reportPath = Join-Path $Root "runtime\bootstrap-report.json"
$report | ConvertTo-Json -Depth 4 | Set-Content -Path $reportPath -Encoding UTF8

Write-Host "ManiMind workspace bootstrap finished."
Write-Host "Report: $reportPath"
if ($missing.Count -gt 0) {
    Write-Warning ("Missing required paths: " + ($missing -join ", "))
}

<#
.SYNOPSIS
按白名单同步第三方仓库中的可复用资产到 resources 目录。

.DESCRIPTION
该脚本只复制项目已批准的子目录，避免把完整上游仓库直接暴露在项目根目录。
#>

param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$HtmlSkillSource = "",
    [string]$HyperframesSource = "",
    [string]$ManimSkillSource = "",
    [switch]$DryRun
)

if ([string]::IsNullOrWhiteSpace($HtmlSkillSource)) {
    $htmlDefaultRoot = Join-Path $Root "AI-Animation-Skill-main"
    $htmlNestedRoot = Join-Path $htmlDefaultRoot "AI-Animation-Skill-main"
    if (Test-Path -LiteralPath $htmlNestedRoot) {
        $HtmlSkillSource = $htmlNestedRoot
    }
    else {
        $HtmlSkillSource = $htmlDefaultRoot
    }
}

if ([string]::IsNullOrWhiteSpace($HyperframesSource)) {
    $hyperframesDefaultRoot = Join-Path $Root "hyperframes-main"
    $hyperframesNestedRoot = Join-Path $hyperframesDefaultRoot "hyperframes-main"
    if (Test-Path -LiteralPath $hyperframesNestedRoot) {
        $HyperframesSource = $hyperframesNestedRoot
    }
    else {
        $HyperframesSource = $hyperframesDefaultRoot
    }
}

$htmlTarget = Join-Path $Root "resources\skills\html-animation"
$hyperframesTarget = Join-Path $Root "resources\references\hyperframes"
$manimSkillTarget = Join-Path $Root "resources\skills\manim\SKILL.md"

$htmlAllowlist = @(
    "SKILL.md",
    "LICENSE",
    "assets\templates\Animation",
    "assets\templates\PPT",
    "assets\templates\PPT Template-level2"
)

$hyperframesAllowlist = @(
    "LICENSE",
    "skills\gsap",
    "skills\hyperframes",
    "skills\hyperframes-cli",
    "skills\hyperframes-registry",
    "docs\guides\common-mistakes.mdx",
    "docs\guides\gsap-animation.mdx",
    "docs\guides\rendering.mdx",
    "docs\reference\html-schema.mdx",
    "docs\schema",
    "registry\blocks\flowchart",
    "registry\blocks\data-chart",
    "registry\blocks\transitions-dissolve",
    "registry\blocks\transitions-cover",
    "registry\blocks\transitions-scale",
    "registry\blocks\whip-pan",
    "registry\blocks\ui-3d-reveal",
    "registry\components\grain-overlay",
    "registry\components\grid-pixelate-wipe",
    "registry\components\shimmer-sweep",
    "registry\examples\decision-tree",
    "registry\examples\kinetic-type",
    "registry\examples\nyt-graph",
    "registry\examples\swiss-grid",
    "registry\examples\warm-grain"
)

function Assert-InsideRoot {
    param([string]$Path, [string]$WorkspaceRoot)
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    if (-not $resolved.StartsWith($WorkspaceRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escapes workspace: $resolved"
    }
}

function Reset-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
        return
    }

    Assert-InsideRoot -Path $Path -WorkspaceRoot $Root
    Get-ChildItem -LiteralPath $Path -Force | Remove-Item -Recurse -Force
}

function Copy-AllowlistedItems {
    param(
        [string]$SourceRoot,
        [string]$TargetRoot,
        [string[]]$Allowlist
    )

    if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
        return [ordered]@{
            source_exists = $false
            copied = @()
            missing = $Allowlist
        }
    }

    if (-not (Test-Path -LiteralPath $SourceRoot)) {
        return [ordered]@{
            source_exists = $false
            copied = @()
            missing = $Allowlist
        }
    }

    if (-not $DryRun) {
        Reset-Directory -Path $TargetRoot
    }

    $copied = @()
    $missing = @()

    foreach ($relativePath in $Allowlist) {
        $sourcePath = Join-Path $SourceRoot $relativePath
        $targetPath = Join-Path $TargetRoot $relativePath

        if (-not (Test-Path -LiteralPath $sourcePath)) {
            $missing += $relativePath
            continue
        }

        $targetParent = Split-Path -Parent $targetPath
        if (-not $DryRun -and -not (Test-Path -LiteralPath $targetParent)) {
            New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
        }

        if (-not $DryRun) {
            Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Recurse -Force
        }
        $copied += $relativePath
    }

    return [ordered]@{
        source_exists = $true
        copied = $copied
        missing = $missing
    }
}

function Resolve-SourceRoot {
    param(
        [string]$SourceRoot,
        [string[]]$ProbePaths
    )

    if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
        return $null
    }

    if (-not (Test-Path -LiteralPath $SourceRoot)) {
        return $SourceRoot
    }

    foreach ($probe in $ProbePaths) {
        $candidate = Join-Path $SourceRoot $probe
        if (Test-Path -LiteralPath $candidate) {
            return $SourceRoot
        }
    }

    $children = @(Get-ChildItem -LiteralPath $SourceRoot -Directory -ErrorAction SilentlyContinue)
    if ($children.Count -eq 1) {
        $nested = $children[0].FullName
        foreach ($probe in $ProbePaths) {
            $candidate = Join-Path $nested $probe
            if (Test-Path -LiteralPath $candidate) {
                return $nested
            }
        }
    }

    return $SourceRoot
}

if (-not $DryRun -and -not (Test-Path -LiteralPath (Split-Path -Parent $manimSkillTarget))) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $manimSkillTarget) -Force | Out-Null
}

$manimCopied = $false
if (-not $DryRun -and -not [string]::IsNullOrWhiteSpace($ManimSkillSource) -and (Test-Path -LiteralPath $ManimSkillSource)) {
    Copy-Item -LiteralPath $ManimSkillSource -Destination $manimSkillTarget -Force
    $manimCopied = $true
}

$resolvedHtmlSource = Resolve-SourceRoot -SourceRoot $HtmlSkillSource -ProbePaths @("SKILL.md", "LICENSE")
$resolvedHyperframesSource = Resolve-SourceRoot -SourceRoot $HyperframesSource -ProbePaths @("LICENSE", "skills\hyperframes")

$htmlResult = Copy-AllowlistedItems -SourceRoot $resolvedHtmlSource -TargetRoot $htmlTarget -Allowlist $htmlAllowlist
$hyperframesResult = Copy-AllowlistedItems -SourceRoot $resolvedHyperframesSource -TargetRoot $hyperframesTarget -Allowlist $hyperframesAllowlist

$report = [ordered]@{
    root = $Root
    dry_run = [bool]$DryRun
    html_skill = [ordered]@{
        source = $resolvedHtmlSource
        target = $htmlTarget
        source_exists = $htmlResult.source_exists
        copied = $htmlResult.copied
        missing = $htmlResult.missing
    }
    hyperframes = [ordered]@{
        source = $resolvedHyperframesSource
        target = $hyperframesTarget
        source_exists = $hyperframesResult.source_exists
        copied = $hyperframesResult.copied
        missing = $hyperframesResult.missing
    }
    manim_skill = [ordered]@{
        source = $ManimSkillSource
        target = $manimSkillTarget
        copied = $manimCopied
    }
    timestamp = (Get-Date).ToString("s")
}

$reportPath = Join-Path $Root "runtime\thirdparty-sync-report.json"
if (-not $DryRun) {
    $report | ConvertTo-Json -Depth 6 | Set-Content -Path $reportPath -Encoding UTF8
}

Write-Host "Third-party asset sync finished."
Write-Host ("HTML source path: " + $resolvedHtmlSource)
Write-Host ("HyperFrames source path: " + $resolvedHyperframesSource)
Write-Host ("HTML source exists: " + $htmlResult.source_exists)
Write-Host ("HyperFrames source exists: " + $hyperframesResult.source_exists)
if (-not $DryRun) {
    Write-Host ("Report: " + $reportPath)
}

<#
.SYNOPSIS
检测 ManiMind 所需工具链是否可用。
#>

param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

function Get-ToolStatus {
    param(
        [string]$Name,
        [bool]$Required,
        [string]$EnvVar = "",
        [string[]]$CandidatePaths = @()
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return [ordered]@{
            name = $Name
            required = $Required
            available = $true
            path = $command.Source
            source = "command"
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($EnvVar)) {
        $configured = [Environment]::GetEnvironmentVariable($EnvVar, "Process")
        if ([string]::IsNullOrWhiteSpace($configured)) {
            $configured = [Environment]::GetEnvironmentVariable($EnvVar, "User")
        }
        if ([string]::IsNullOrWhiteSpace($configured)) {
            $configured = [Environment]::GetEnvironmentVariable($EnvVar, "Machine")
        }
        if (-not [string]::IsNullOrWhiteSpace($configured) -and (Test-Path -LiteralPath $configured)) {
            return [ordered]@{
                name = $Name
                required = $Required
                available = $true
                path = $configured
                source = "env:$EnvVar"
            }
        }
    }

    foreach ($candidate in $CandidatePaths) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path -LiteralPath $candidate)) {
            return [ordered]@{
                name = $Name
                required = $Required
                available = $true
                path = $candidate
                source = "candidate"
            }
        }
    }

    return [ordered]@{
        name = $Name
        required = $Required
        available = $false
        path = $null
        source = $null
    }
}

$userProfile = [Environment]::GetFolderPath("UserProfile")
$localAppData = [Environment]::GetFolderPath("LocalApplicationData")

function Join-IfPresent {
    param([string]$Base, [string]$Relative)
    if ([string]::IsNullOrWhiteSpace($Base)) {
        return ""
    }
    return (Join-Path $Base $Relative)
}

$tools = @(
    (Get-ToolStatus -Name "node" -Required $true -EnvVar "MANIMIND_NODE_PATH"),
    (Get-ToolStatus -Name "python" -Required $true -EnvVar "MANIMIND_PYTHON_PATH" -CandidatePaths @(
        (Join-IfPresent $localAppData "Programs\Python\Python312\python.exe"),
        (Join-IfPresent $localAppData "Microsoft\WindowsApps\python.exe")
    )),
    (Get-ToolStatus -Name "bun" -Required $false -EnvVar "MANIMIND_BUN_PATH"),
    (Get-ToolStatus -Name "ffmpeg" -Required $true -EnvVar "MANIMIND_FFMPEG_PATH" -CandidatePaths @(
        "D:\ffmpeg\bin\ffmpeg.exe",
        (Join-IfPresent $userProfile "scoop\apps\ffmpeg\current\bin\ffmpeg.exe")
    )),
    (Get-ToolStatus -Name "manim" -Required $true -EnvVar "MANIMIND_MANIM_PATH" -CandidatePaths @(
        (Join-IfPresent $localAppData "Programs\Python\Python312\Scripts\manim.exe"),
        (Join-IfPresent $userProfile "AppData\Local\Programs\Python\Python312\Scripts\manim.exe")
    ))
)

$missingRequired = @($tools | Where-Object { -not $_.available -and $_.required } | ForEach-Object { $_.name })

$report = [ordered]@{
    root = $Root
    tools = $tools
    missing_required = $missingRequired
    timestamp = (Get-Date).ToString("s")
}

$reportPath = Join-Path $Root "runtime\doctor-report.json"
$report | ConvertTo-Json -Depth 4 | Set-Content -Path $reportPath -Encoding UTF8

Write-Host "ManiMind prerequisite check finished."
Write-Host "Report: $reportPath"

foreach ($tool in $tools) {
    if ($tool.available) {
        Write-Host ("[OK]   " + $tool.name + " -> " + $tool.path)
    }
    else {
        Write-Host ("[MISS] " + $tool.name)
    }
}

if ($missingRequired.Count -gt 0) {
    Write-Warning ("Missing required tools: " + ($missingRequired -join ", "))
    exit 1
}

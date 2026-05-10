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
        [bool]$Required
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        return [ordered]@{
            name = $Name
            required = $Required
            available = $false
            path = $null
        }
    }

    return [ordered]@{
        name = $Name
        required = $Required
        available = $true
        path = $command.Source
    }
}

$tools = @(
    (Get-ToolStatus -Name "node" -Required $true),
    (Get-ToolStatus -Name "python" -Required $true),
    (Get-ToolStatus -Name "bun" -Required $false),
    (Get-ToolStatus -Name "ffmpeg" -Required $true),
    (Get-ToolStatus -Name "manim" -Required $true)
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

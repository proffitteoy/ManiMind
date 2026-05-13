param(
    [string]$Manifest = "configs/max-function-review-demo.json",
    [string]$ProjectId = "max-function-review-demo",
    [string]$SessionId = "",
    [string]$ReferenceAudio = "",
    [string]$ReferenceText = "",
    [string]$Model = "F5TTS_v1_Base",
    [double]$RefMinSeconds = 28.0,
    [double]$MaxTotalSeconds = 30.0,
    [string]$HfCacheRoot = "",
    [string]$PythonExe = "C:\\Users\\84025\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
    [string]$FfmpegExe = "D:\\ffmpeg\\bin\\ffmpeg.exe",
    [switch]$RemoveSilence
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if ([string]::IsNullOrWhiteSpace($SessionId)) {
    $SessionId = "f5-session-" + (Get-Date -Format "yyyyMMdd-HHmmss")
}

if ([string]::IsNullOrWhiteSpace($ReferenceAudio)) {
    $ReferenceAudio = Join-Path $repoRoot ("runtime/projects/{0}/voice/selena_reference.m4a" -f $ProjectId)
}

if ([string]::IsNullOrWhiteSpace($ReferenceText)) {
    $referenceTextPath = [System.IO.Path]::ChangeExtension($ReferenceAudio, ".txt")
    if (Test-Path -LiteralPath $referenceTextPath) {
        $ReferenceText = Get-Content -Raw -LiteralPath $referenceTextPath -Encoding UTF8
    }
}
if (-not [string]::IsNullOrWhiteSpace($ReferenceText)) {
    $ReferenceText = ($ReferenceText -replace "`r", " " -replace "`n", " ").Trim()
}

$outputAudioDir = Join-Path $repoRoot ("outputs/{0}/audio" -f $ProjectId)
if ([string]::IsNullOrWhiteSpace($HfCacheRoot)) {
    $cacheRoot = Join-Path $repoRoot ("runtime/projects/{0}/voice/hf-cache" -f $ProjectId)
} else {
    $cacheRoot = $HfCacheRoot
}
$hubCache = Join-Path $cacheRoot "hub"
$transformersCache = Join-Path $cacheRoot "transformers"

if (-not (Test-Path -LiteralPath $Manifest)) {
    throw "manifest_not_found: $Manifest"
}
if (-not (Test-Path -LiteralPath $ReferenceAudio)) {
    throw "reference_audio_not_found: $ReferenceAudio"
}
if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "python_not_found: $PythonExe"
}
if (-not (Test-Path -LiteralPath $FfmpegExe)) {
    throw "ffmpeg_not_found: $FfmpegExe"
}

New-Item -ItemType Directory -Path $outputAudioDir -Force | Out-Null
New-Item -ItemType Directory -Path $hubCache -Force | Out-Null
New-Item -ItemType Directory -Path $transformersCache -Force | Out-Null

$ffmpegDir = Split-Path -Parent $FfmpegExe
$env:PATH = "$ffmpegDir;$env:PATH"
$env:MANIMIND_FFMPEG_PATH = $FfmpegExe
$env:PYTHONPATH = (Join-Path $repoRoot "src")
$env:HF_HOME = $cacheRoot
$env:HUGGINGFACE_HUB_CACHE = $hubCache
$env:TRANSFORMERS_CACHE = $transformersCache

$runner = Join-Path $repoRoot "scripts\\f5_tts_generate.py"
if (-not (Test-Path -LiteralPath $runner)) {
    throw "f5_runner_not_found: $runner"
}

$env:MANIMIND_F5_PYTHON_EXE = $PythonExe
$env:MANIMIND_F5_RUNNER_PATH = $runner
$env:MANIMIND_F5_MODEL = $Model
$env:MANIMIND_F5_REFERENCE_AUDIO = $ReferenceAudio
$env:MANIMIND_F5_HF_CACHE_ROOT = $cacheRoot
$env:MANIMIND_F5_DEVICE = "cpu"
$env:MANIMIND_F5_REF_MIN_SECONDS = [string]$RefMinSeconds
$env:MANIMIND_F5_MAX_TOTAL_SECONDS = [string]$MaxTotalSeconds
if ($RemoveSilence.IsPresent) {
    $env:MANIMIND_F5_REMOVE_SILENCE = "true"
} else {
    $env:MANIMIND_F5_REMOVE_SILENCE = "false"
}
if (-not [string]::IsNullOrWhiteSpace($ReferenceText)) {
    $env:MANIMIND_F5_REFERENCE_TEXT = $ReferenceText
}

Write-Host "ProjectId: $ProjectId"
Write-Host "Manifest: $Manifest"
Write-Host "SessionId: $SessionId"
Write-Host "ReferenceAudio: $ReferenceAudio"
Write-Host "RefMinSeconds: $env:MANIMIND_F5_REF_MIN_SECONDS"
Write-Host "MaxTotalSeconds: $env:MANIMIND_F5_MAX_TOTAL_SECONDS"
Write-Host "HF Cache: $cacheRoot"
Write-Host "F5 Runner: $env:MANIMIND_F5_RUNNER_PATH"
Write-Host "TTS Provider: f5_tts"

& $PythonExe -m manimind.main finalize $Manifest --session-id $SessionId --tts-provider f5_tts

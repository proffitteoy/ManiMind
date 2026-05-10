"""TTS 适配层：支持 noop / powershell_sapi / command。"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import subprocess
from typing import Protocol


@dataclass(slots=True)
class TTSJob:
    project_id: str
    script_text: str
    output_path: str
    voice: str = "neutral"
    language: str = "zh-CN"


class TTSAdapter(Protocol):
    def synthesize(self, job: TTSJob) -> str:
        """执行 TTS 并返回产物路径。"""


class NoopTTSAdapter:
    """占位实现。"""

    def synthesize(self, job: TTSJob) -> str:
        target = Path(job.output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "\n".join(
                [
                    "# TTS Placeholder",
                    f"project_id={job.project_id}",
                    f"voice={job.voice}",
                    f"language={job.language}",
                    "",
                    job.script_text,
                ]
            ),
            encoding="utf-8",
        )
        return str(target)


class PowerShellSapiTTSAdapter:
    """Windows 本地语音合成（System.Speech）。"""

    def synthesize(self, job: TTSJob) -> str:
        target = Path(job.output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # System.Speech SaveToWaveFile 只支持 wav。
        if target.suffix.lower() != ".wav":
            target = target.with_suffix(".wav")

        text_file = target.with_suffix(".txt")
        text_file.write_text(job.script_text, encoding="utf-8")
        script_file = target.with_suffix(".sapi.ps1")

        script = r"""
param([string]$TextFile,[string]$OutputFile,[string]$VoiceHint,[string]$LanguageHint)
Add-Type -AssemblyName System.Speech
$text = Get-Content -Raw -LiteralPath $TextFile -Encoding UTF8
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
if ($VoiceHint -and $VoiceHint -ne 'neutral') {
  try { $synth.SelectVoice($VoiceHint) } catch {}
}
if ($LanguageHint) {
  $candidate = $synth.GetInstalledVoices() |
    Where-Object { $_.VoiceInfo.Culture.Name -like "$LanguageHint*" } |
    Select-Object -First 1
  if ($null -ne $candidate) {
    try { $synth.SelectVoice($candidate.VoiceInfo.Name) } catch {}
  }
}
$synth.SetOutputToWaveFile($OutputFile)
$synth.Speak($text)
$synth.Dispose()
"""
        script_file.write_text(script, encoding="utf-8")
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_file),
            "-TextFile",
            str(text_file),
            "-OutputFile",
            str(target),
            "-VoiceHint",
            job.voice,
            "-LanguageHint",
            job.language,
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(
                "tts_powershell_failed:"
                + (result.stderr.strip() or result.stdout.strip() or "unknown")
            )
        if script_file.exists():
            script_file.unlink()
        if text_file.exists():
            text_file.unlink()
        return str(target)


class CommandTTSAdapter:
    """外部命令适配器。命令模板通过环境变量 MANIMIND_TTS_COMMAND 提供。"""

    def __init__(self, command_template: str) -> None:
        self.command_template = command_template

    def synthesize(self, job: TTSJob) -> str:
        target = Path(job.output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        text_file = target.with_suffix(".txt")
        text_file.write_text(job.script_text, encoding="utf-8")

        rendered = (
            self.command_template.replace("{text_file}", str(text_file))
            .replace("{output}", str(target))
            .replace("{voice}", job.voice)
            .replace("{language}", job.language)
        )
        command = shlex.split(rendered, posix=False)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(
                "tts_command_failed:"
                + (result.stderr.strip() or result.stdout.strip() or "unknown")
            )
        if not target.exists():
            raise RuntimeError(f"tts_output_not_found:{target}")
        return str(target)


def build_tts_adapter(provider: str = "noop") -> TTSAdapter:
    """构建 TTS 适配器。"""
    normalized = provider.strip().lower()
    if normalized == "noop":
        return NoopTTSAdapter()
    if normalized in {"powershell", "powershell_sapi", "sapi"}:
        return PowerShellSapiTTSAdapter()
    if normalized == "command":
        template = os.environ.get("MANIMIND_TTS_COMMAND", "").strip()
        if not template:
            raise ValueError("missing_MANIMIND_TTS_COMMAND")
        return CommandTTSAdapter(template)
    raise ValueError(f"unsupported_tts_provider: {provider}")

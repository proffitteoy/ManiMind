"""TTS 适配层测试。"""

from pathlib import Path

from manimind.tts import TTSJob, build_tts_adapter


def test_noop_tts_writes_placeholder(tmp_path: Path) -> None:
    adapter = build_tts_adapter("noop")
    output = adapter.synthesize(
        TTSJob(
            project_id="demo",
            script_text="hello tts",
            output_path=str(tmp_path / "voice.txt"),
            voice="neutral",
            language="zh-CN",
        )
    )
    path = Path(output)
    assert path.exists()
    assert "hello tts" in path.read_text(encoding="utf-8")

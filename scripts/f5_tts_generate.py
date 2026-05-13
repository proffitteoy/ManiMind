#!/usr/bin/env python
"""Generate wav with F5-TTS while keeping full reference audio when requested."""

from __future__ import annotations

import argparse
import inspect
import os
from pathlib import Path
import tempfile


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate wav with F5-TTS.")
    parser.add_argument("--model", default="F5TTS_v1_Base")
    parser.add_argument("--ref-audio", required=True, help="Reference audio path.")
    parser.add_argument("--ref-text", default="", help="Optional reference transcript.")
    parser.add_argument("--gen-file", required=True, help="Input narration text file.")
    parser.add_argument("--output", required=True, help="Output wav path.")
    parser.add_argument(
        "--hf-cache-root",
        default="",
        help="Optional HuggingFace cache root for model/vocoder reuse.",
    )
    parser.add_argument("--device", default="cpu", help="cpu/cuda/xpu/mps")
    parser.add_argument(
        "--ref-min-seconds",
        type=float,
        default=0.0,
        help="Require effective reference audio duration to be >= this value.",
    )
    parser.add_argument(
        "--max-total-seconds",
        type=float,
        default=30.0,
        help="Target total seconds per batch (reference + generated) for text chunking.",
    )
    parser.add_argument("--remove-silence", action="store_true")
    return parser


def _set_cache_env(cache_root: str) -> None:
    if not cache_root:
        return
    root = Path(cache_root)
    hub = root / "hub"
    transformers_cache = root / "transformers"
    hub.mkdir(parents=True, exist_ok=True)
    transformers_cache.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(root)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(hub)
    os.environ["TRANSFORMERS_CACHE"] = str(transformers_cache)


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def _load_audio_tensor_with_soundfile(path: str):
    import numpy as np
    import soundfile as sf
    import torch

    audio_np, sample_rate = sf.read(path, dtype="float32")
    if audio_np.ndim == 1:
        audio = torch.from_numpy(audio_np).unsqueeze(0)
    else:
        audio = torch.from_numpy(np.transpose(audio_np, (1, 0)))
    return audio, sample_rate


def _normalize_reference_text(text: str) -> str:
    normalized = text.strip()
    if not normalized:
        return normalized
    if not normalized.endswith(". ") and not normalized.endswith("。"):
        if normalized.endswith("."):
            normalized += " "
        else:
            normalized += ". "
    return normalized


def _prepare_reference_audio_without_short_clip(
    ui,
    ref_audio: str,
    ref_text: str,
) -> tuple[str, str]:
    from pydub import AudioSegment

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    audio_seg = AudioSegment.from_file(ref_audio)
    audio_seg.export(str(tmp_path), format="wav")

    if ref_text.strip():
        resolved_ref_text = ref_text
    else:
        print("No reference text provided, transcribing full reference audio...", flush=True)
        resolved_ref_text = ui.transcribe(str(tmp_path))

    return str(tmp_path), _normalize_reference_text(resolved_ref_text)


def _prepare_reference_audio(ui, ref_audio: str, ref_text: str) -> tuple[str, str, Path | None]:
    preprocess_sig = inspect.signature(ui.preprocess_ref_audio_text)
    if "clip_short" in preprocess_sig.parameters:
        processed_audio, processed_text = ui.preprocess_ref_audio_text(
            ref_audio,
            ref_text,
            clip_short=False,
        )
        return processed_audio, processed_text, None

    processed_audio, processed_text = _prepare_reference_audio_without_short_clip(
        ui,
        ref_audio,
        ref_text,
    )
    return processed_audio, processed_text, Path(processed_audio)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    _set_cache_env(args.hf_cache_root)

    import f5_tts.infer.utils_infer as ui
    from cached_path import cached_path
    from hydra.utils import get_class
    from importlib.resources import files
    from omegaconf import OmegaConf
    import soundfile as sf

    gen_text = _read_text(args.gen_file)
    if not gen_text:
        raise RuntimeError(f"empty_gen_text_file: {args.gen_file}")

    print("loading_model_and_vocoder...", flush=True)
    model_cfg = OmegaConf.load(str(files("f5_tts").joinpath(f"configs/{args.model}.yaml")))
    model_cls = get_class(f"f5_tts.model.{model_cfg.model.backbone}")
    ckpt_file = str(cached_path(f"hf://SWivid/F5-TTS/{args.model}/model_1250000.safetensors"))

    vocoder = ui.load_vocoder(vocoder_name="vocos", is_local=False, local_path="", device=args.device)
    ema_model = ui.load_model(
        model_cls,
        model_cfg.model.arch,
        ckpt_file,
        mel_spec_type="vocos",
        vocab_file="",
        device=args.device,
    )

    print("preprocessing_reference_audio...", flush=True)
    cleanup_audio: Path | None = None
    ref_audio_prep, ref_text, cleanup_audio = _prepare_reference_audio(
        ui,
        args.ref_audio,
        args.ref_text,
    )
    try:
        audio, sample_rate = _load_audio_tensor_with_soundfile(ref_audio_prep)
    finally:
        if cleanup_audio is not None and cleanup_audio.exists():
            cleanup_audio.unlink(missing_ok=True)

    ref_duration_seconds = audio.shape[-1] / sample_rate
    print(f"reference_audio_seconds={ref_duration_seconds:.2f}", flush=True)
    if args.ref_min_seconds > 0 and ref_duration_seconds + 1e-6 < args.ref_min_seconds:
        import torch

        pad_seconds = args.ref_min_seconds - ref_duration_seconds
        pad_samples = int(round(pad_seconds * sample_rate))
        if pad_samples > 0:
            pad = torch.zeros((audio.shape[0], pad_samples), dtype=audio.dtype)
            audio = torch.cat([audio, pad], dim=-1)
            ref_duration_seconds = audio.shape[-1] / sample_rate
            print(
                "reference_audio_padded_seconds="
                f"{ref_duration_seconds:.2f} (target={args.ref_min_seconds:.2f})",
                flush=True,
            )

    # Keep each chunk within model total-duration budget.
    chunk_budget_seconds = max(args.max_total_seconds - ref_duration_seconds, 1.0)
    max_chars = int(
        len(ref_text.encode("utf-8"))
        / max(ref_duration_seconds, 1e-6)
        * chunk_budget_seconds
        * ui.speed
    )
    if max_chars < 20:
        max_chars = 20
    batches = ui.chunk_text(gen_text, max_chars=max_chars)
    if not batches:
        raise RuntimeError("empty_text_batches")

    print("running_inference...", flush=True)
    wave, sr, _ = next(
        ui.infer_batch_process(
            (audio, sample_rate),
            ref_text,
            batches,
            ema_model,
            vocoder,
            mel_spec_type="vocos",
            target_rms=ui.target_rms,
            cross_fade_duration=ui.cross_fade_duration,
            nfe_step=ui.nfe_step,
            cfg_strength=ui.cfg_strength,
            sway_sampling_coef=ui.sway_sampling_coef,
            speed=ui.speed,
            fix_duration=ui.fix_duration,
            device=args.device,
        )
    )
    if wave is None:
        raise RuntimeError("f5_tts_infer_returned_empty_wave")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), wave, sr)
    if args.remove_silence:
        ui.remove_silence_for_generated_wav(str(output_path))
    print("done", flush=True)
    print(str(output_path))


if __name__ == "__main__":
    main()

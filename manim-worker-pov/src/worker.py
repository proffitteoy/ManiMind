"""Manim Worker POV：spec -> code -> render -> repair。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from log_parser import classify_error
from renderer import render_scene

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC_PATH = ROOT / "specs" / "derivative_geometry.yaml"
DEFAULT_RUN_DIR = ROOT / "runs" / "derivative_geometry"
DEFAULT_PROMPTS_DIR = ROOT / "prompts"
MAX_REPAIR_ROUNDS = 3


def _load_yaml_module():
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: pyyaml. Install with: pip install pyyaml"
        ) from exc
    return yaml


def load_spec(spec_path: Path) -> dict[str, Any]:
    """加载 scene spec。"""
    yaml = _load_yaml_module()
    return yaml.safe_load(spec_path.read_text(encoding="utf-8"))


def _read_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _render_prompt(template: str, replacements: dict[str, str]) -> str:
    prompt = template
    for key, value in replacements.items():
        prompt = prompt.replace(key, value)
    return prompt


def _run_llm(prompt: str, llm_command: list[str], timeout: int = 300) -> str:
    """通过外部命令调用 LLM，读取 stdout 作为代码输出。"""
    if not llm_command:
        raise ValueError("llm_command cannot be empty")

    result = subprocess.run(
        llm_command,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(
            "LLM command failed.\n"
            f"command: {' '.join(llm_command)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    output = result.stdout.strip()
    if not output:
        raise RuntimeError("LLM returned empty output.")
    return output


def _strip_markdown_fences(text: str) -> str:
    """容错处理：若模型误输出 fenced code block，则自动剥离。"""
    text = text.strip()
    fenced = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip() + "\n"
    return text + "\n"


def _validate_scene_code(code: str, scene_class: str) -> None:
    """在渲染前做最小结构校验，减少无意义尝试。"""
    class_defs = re.findall(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", code, flags=re.MULTILINE)
    if len(class_defs) != 1:
        raise ValueError(
            f"Expected exactly one class definition, but found {len(class_defs)}."
        )
    if class_defs[0] != scene_class:
        raise ValueError(
            f"Scene class mismatch. Expected {scene_class}, got {class_defs[0]}."
        )
    if "from manim import *" not in code:
        raise ValueError("Missing required import: from manim import *")


def call_llm_generate(
    scene_spec: str,
    generate_prompt_template: str,
    llm_command: list[str],
    llm_timeout: int,
) -> str:
    """首次代码生成。"""
    prompt = _render_prompt(
        generate_prompt_template,
        {
            "{{SCENE_SPEC}}": scene_spec,
        },
    )
    return _strip_markdown_fences(_run_llm(prompt, llm_command, timeout=llm_timeout))


def call_llm_repair(
    scene_spec: str,
    previous_code: str,
    render_log: str,
    error_type: str,
    repair_prompt_template: str,
    llm_command: list[str],
    llm_timeout: int,
) -> str:
    """基于日志的代码修复。"""
    prompt = _render_prompt(
        repair_prompt_template,
        {
            "{{SCENE_SPEC}}": scene_spec,
            "{{PREVIOUS_CODE}}": previous_code,
            "{{RENDER_LOG}}": render_log,
            "{{ERROR_TYPE}}": error_type,
        },
    )
    return _strip_markdown_fences(_run_llm(prompt, llm_command, timeout=llm_timeout))


def _locate_rendered_video(media_dir: Path, scene_class: str) -> Path | None:
    if not media_dir.exists():
        return None

    exact_matches = sorted(
        media_dir.rglob(f"{scene_class}.mp4"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if exact_matches:
        return exact_matches[0]

    any_matches = sorted(
        media_dir.rglob("*.mp4"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if any_matches:
        return any_matches[0]

    return None


def run_worker(
    spec_path: Path,
    run_dir: Path,
    prompts_dir: Path,
    llm_command: list[str],
    max_repair_rounds: int = MAX_REPAIR_ROUNDS,
    render_timeout: int = 120,
    llm_timeout: int = 300,
) -> dict[str, Any]:
    """执行 worker 闭环。"""
    run_dir.mkdir(parents=True, exist_ok=True)

    spec_text = spec_path.read_text(encoding="utf-8")
    spec = load_spec(spec_path)
    scene_class = spec["scene_class"]
    quality = spec.get("quality", "ql")
    media_dir = run_dir / "media"

    shutil.copyfile(spec_path, run_dir / "scene_spec.yaml")

    generate_prompt_template = _read_prompt(prompts_dir / "generate_scene.md")
    repair_prompt_template = _read_prompt(prompts_dir / "repair_scene.md")

    code = call_llm_generate(
        scene_spec=spec_text,
        generate_prompt_template=generate_prompt_template,
        llm_command=llm_command,
        llm_timeout=llm_timeout,
    )

    for attempt in range(1, max_repair_rounds + 2):
        scene_file = run_dir / f"attempt_{attempt:03d}.py"
        log_file = run_dir / f"attempt_{attempt:03d}.log"
        scene_file.write_text(code, encoding="utf-8")

        try:
            _validate_scene_code(code, scene_class)
            success, log = render_scene(
                scene_file=scene_file,
                scene_class=scene_class,
                quality=quality,
                timeout=render_timeout,
                media_dir=media_dir,
            )
        except ValueError as exc:
            success = False
            log = f"PRE_RENDER_VALIDATION_ERROR: {exc}"
        log_file.write_text(log, encoding="utf-8")

        if success:
            final_file = run_dir / "final_scene.py"
            final_file.write_text(code, encoding="utf-8")

            output_video = None
            rendered_video = _locate_rendered_video(media_dir, scene_class)
            if rendered_video is not None:
                output_video = run_dir / "output.mp4"
                shutil.copyfile(rendered_video, output_video)

            result = {
                "status": "success",
                "attempts": attempt,
                "final_scene": str(final_file),
                "output_mp4": str(output_video) if output_video else None,
            }
            (run_dir / "result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return result

        error_type = classify_error(log)
        if attempt > max_repair_rounds:
            result = {
                "status": "failed",
                "attempts": attempt,
                "last_error_type": error_type,
                "last_log": str(log_file),
            }
            (run_dir / "result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return result

        code = call_llm_repair(
            scene_spec=spec_text,
            previous_code=code,
            render_log=log,
            error_type=error_type,
            repair_prompt_template=repair_prompt_template,
            llm_command=llm_command,
            llm_timeout=llm_timeout,
        )

    raise RuntimeError("Unexpected state: repair loop exited without result.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manim Worker POV runner")
    parser.add_argument(
        "--spec",
        type=Path,
        default=DEFAULT_SPEC_PATH,
        help="Path to scene spec yaml.",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=DEFAULT_RUN_DIR,
        help="Directory for attempts/logs/final output.",
    )
    parser.add_argument(
        "--prompts-dir",
        type=Path,
        default=DEFAULT_PROMPTS_DIR,
        help="Directory containing generate_scene.md and repair_scene.md.",
    )
    parser.add_argument(
        "--llm-command",
        nargs="+",
        required=True,
        help="External command used to call your LLM. It must read prompt from stdin and output code to stdout.",
    )
    parser.add_argument(
        "--max-repair-rounds",
        type=int,
        default=MAX_REPAIR_ROUNDS,
        help="Maximum number of repair rounds.",
    )
    parser.add_argument(
        "--render-timeout",
        type=int,
        default=120,
        help="Timeout seconds for each manim render attempt.",
    )
    parser.add_argument(
        "--llm-timeout",
        type=int,
        default=300,
        help="Timeout seconds for each LLM call.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_worker(
        spec_path=args.spec,
        run_dir=args.run_dir,
        prompts_dir=args.prompts_dir,
        llm_command=args.llm_command,
        max_repair_rounds=args.max_repair_rounds,
        render_timeout=args.render_timeout,
        llm_timeout=args.llm_timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

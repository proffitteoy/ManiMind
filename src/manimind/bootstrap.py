"""ManiMind 初始化工具：负责目录准备与依赖检测。"""

from __future__ import annotations

import os
from pathlib import Path
import re
from shutil import which

from .models import RuntimeLayout


WORKSPACE_DIRECTORIES = [
    "inputs/papers",
    "inputs/notes",
    "configs",
    "scripts",
    "src/manimind",
    "tests",
    "resources/skills/html-animation",
    "resources/skills/manim",
    "resources/references/hyperframes",
    "runtime/projects",
    "runtime/sessions",
    "runtime/cache",
    "outputs",
    "logs",
]

EXTERNAL_PATHS = {
    "html_skill_root": "resources/skills/html-animation",
    "hyperframes_root": "resources/references/hyperframes",
    "manim_skill_file": "resources/skills/manim/SKILL.md",
    "pdf_skill_root": "pdf",
    "docs_root": "docs",
}

REFERENCE_ARCHIVES = {
    "claude_code_source_zip": "ClaudeCode/src.zip",
    "claude_code_release_tgz": "ClaudeCode/anthropic-ai-claude-code-2.1.88.tgz",
}


def repo_root() -> Path:
    """返回仓库根目录。"""
    return Path(__file__).resolve().parents[2]


def sanitize_identifier(value: str) -> str:
    """将项目或会话标识转换为稳定目录名。"""
    normalized = re.sub(r"[^0-9A-Za-z_-]+", "-", value).strip("-").lower()
    if not normalized:
        raise ValueError("identifier must contain at least one ASCII letter or digit")
    return normalized


def build_runtime_layout(project_id: str, root: Path | None = None) -> RuntimeLayout:
    """生成符合仓库约定的产物路径蓝图。"""
    base = root or repo_root()
    safe_project_id = sanitize_identifier(project_id)
    return RuntimeLayout(
        project_context_dir=str(base / "runtime" / "projects" / safe_project_id),
        session_context_root=str(base / "runtime" / "sessions"),
        output_dir=str(base / "outputs" / safe_project_id),
        bootstrap_report=str(base / "runtime" / "bootstrap-report.json"),
        doctor_report=str(base / "runtime" / "doctor-report.json"),
    )


def ensure_workspace(root: Path | None = None) -> dict[str, object]:
    """创建或校验工作区目录。"""
    base = root or repo_root()
    created: list[str] = []

    for relative_dir in WORKSPACE_DIRECTORIES:
        target = base / relative_dir
        target.mkdir(parents=True, exist_ok=True)
        created.append(relative_dir)

    return {
        "root": str(base),
        "created_or_verified": created,
        "external_paths": check_external_paths(base),
        "reference_archives": check_reference_archives(base),
    }


def check_external_paths(root: Path | None = None) -> dict[str, bool]:
    """检查第三方能力路径是否存在。"""
    base = root or repo_root()
    return {
        name: (base / relative_path).exists()
        for name, relative_path in EXTERNAL_PATHS.items()
    }


def check_reference_archives(root: Path | None = None) -> dict[str, bool]:
    """检查参考源码压缩包是否存在（可选，不影响运行时）。"""
    base = root or repo_root()
    return {
        name: (base / relative_path).exists()
        for name, relative_path in REFERENCE_ARCHIVES.items()
    }


def check_tools() -> dict[str, bool]:
    """检查关键工具是否可用。"""
    def _path_exists(raw_path: str | None) -> bool:
        if not raw_path:
            return False
        return Path(raw_path).expanduser().exists()

    def _tool_available(name: str, *, env_var: str, extra_candidates: list[str]) -> bool:
        if which(name) is not None:
            return True
        if _path_exists(os.environ.get(env_var)):
            return True
        for candidate in extra_candidates:
            if _path_exists(candidate):
                return True
        return False

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    user_profile = os.environ.get("USERPROFILE", "")
    python_root = Path(local_app_data) / "Programs" / "Python" / "Python312"
    manim_path = python_root / "Scripts" / "manim.exe"
    python_path = python_root / "python.exe"
    windows_apps_python = Path(local_app_data) / "Microsoft" / "WindowsApps" / "python.exe"
    user_python_scripts = Path(user_profile) / "AppData" / "Local" / "Programs" / "Python" / "Python312" / "Scripts" / "manim.exe"

    python_ok = _tool_available(
        "python",
        env_var="MANIMIND_PYTHON_PATH",
        extra_candidates=[
            str(python_path),
            str(windows_apps_python),
        ],
    ) or which("py") is not None

    return {
        "node": _tool_available(
            "node",
            env_var="MANIMIND_NODE_PATH",
            extra_candidates=[],
        ),
        "python": python_ok,
        "bun": _tool_available(
            "bun",
            env_var="MANIMIND_BUN_PATH",
            extra_candidates=[],
        ),
        "ffmpeg": _tool_available(
            "ffmpeg",
            env_var="MANIMIND_FFMPEG_PATH",
            extra_candidates=[
                r"D:\ffmpeg\bin\ffmpeg.exe",
                str(Path(user_profile) / "scoop" / "apps" / "ffmpeg" / "current" / "bin" / "ffmpeg.exe"),
            ],
        ),
        "manim": _tool_available(
            "manim",
            env_var="MANIMIND_MANIM_PATH",
            extra_candidates=[
                str(manim_path),
                str(user_python_scripts),
            ],
        ),
        "hyperframes": _tool_available(
            "npx",
            env_var="MANIMIND_NPX_PATH",
            extra_candidates=[],
        ),
    }

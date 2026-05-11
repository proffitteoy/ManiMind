"""能力注册表：管理第三方资源和 skills 的角色分发。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .bootstrap import repo_root


@dataclass(slots=True)
class CapabilityRef:
    name: str
    path: str
    roles: list[str] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)
    purpose: str = ""
    summary: str = ""
    available: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": self.path,
            "roles": self.roles,
            "stages": self.stages,
            "purpose": self.purpose,
            "summary": self.summary,
            "available": self.available,
        }


CAPABILITY_DEFINITIONS: list[dict[str, object]] = [
    {
        "name": "pdf_ingest_skill",
        "rel_path": "pdf",
        "roles": ["lead", "explorer"],
        "stages": ["ingest", "summarize"],
        "purpose": "PDF text/OCR/table/form/image extraction",
        "summary": (
            "本地 PDF 处理能力包，支持 pypdf 文本抽取、pdfplumber 表格解析、"
            "OCR 扫描件处理、表单字段提取和页面图像导出。"
            "入口文档：pdf/SKILL.md；辅助脚本：pdf/scripts/。"
        ),
    },
    {
        "name": "html_animation_skill",
        "rel_path": "resources/skills/html-animation",
        "roles": ["explorer", "planner", "coordinator", "html_worker"],
        "stages": ["summarize", "plan", "dispatch"],
        "purpose": "HTML template and motion patterns for intro/bridge/explainer segments",
        "summary": (
            "HTML 科普动画 skill，提供 PPT 轮播和流程图两种模式。"
            "包含 25+ 级别二模板和 14 个动画模板。"
            "适用于开头引子、段间衔接、弱科普说明和轻量信息卡。"
            "入口文档：SKILL.md；模板目录：templates/。"
        ),
    },
    {
        "name": "hyperframes_reference",
        "rel_path": "resources/references/hyperframes",
        "roles": ["explorer", "planner", "coordinator", "html_worker", "svg_worker"],
        "stages": ["summarize", "plan", "dispatch"],
        "purpose": "Video composition framework with GSAP timelines and transitions",
        "summary": (
            "HyperFrames 视频合成框架参考，包含 GSAP 时间线、过渡动画、"
            "字幕系统和音频响应视觉。"
            "docs/ 提供渲染指南和 HTML schema；"
            "registry/ 提供 blocks（data-chart, flowchart, transitions）"
            "和 components（grain-overlay, shimmer-sweep 等）。"
        ),
    },
    {
        "name": "manim_skill",
        "rel_path": "resources/skills/manim",
        "roles": ["explorer", "planner", "coordinator", "manim_worker"],
        "stages": ["summarize", "plan", "dispatch"],
        "purpose": "Manim math animation generation and repair",
        "summary": (
            "Manim 数学动画 skill，指导如何生成带同步旁白和字幕的数学动画。"
            "支持 gTTS、pyttsx3 和高级 TTS 引擎。"
            "入口文档：SKILL.md。"
        ),
    },
]


def resolve_capabilities(root: Path | None = None) -> list[CapabilityRef]:
    """解析所有能力定义，检查路径是否存在。"""
    base = root or repo_root()
    result: list[CapabilityRef] = []
    for defn in CAPABILITY_DEFINITIONS:
        rel_path = str(defn["rel_path"])
        full_path = base / rel_path
        result.append(
            CapabilityRef(
                name=str(defn["name"]),
                path=rel_path,
                roles=list(defn.get("roles", [])),  # type: ignore[arg-type]
                stages=list(defn.get("stages", [])),  # type: ignore[arg-type]
                purpose=str(defn.get("purpose", "")),
                summary=str(defn.get("summary", "")),
                available=full_path.exists(),
            )
        )
    return result


def capabilities_for_role(
    role_id: str,
    stage: str,
    root: Path | None = None,
) -> list[CapabilityRef]:
    """返回某角色在某阶段可用的能力引用。"""
    all_caps = resolve_capabilities(root)
    return [
        cap
        for cap in all_caps
        if cap.available and role_id in cap.roles and stage in cap.stages
    ]


def build_capability_summaries(
    role_id: str,
    stage: str,
    root: Path | None = None,
) -> str:
    """构建注入 prompt 的能力摘要文本。"""
    caps = capabilities_for_role(role_id, stage, root)
    if not caps:
        return ""

    is_worker = role_id.endswith("_worker")
    lines = ["可用能力资源："]
    for cap in caps:
        if is_worker:
            lines.append(
                f"- [{cap.name}] {cap.purpose}\n"
                f"  路径：{cap.path}\n"
                f"  说明：{cap.summary}"
            )
        else:
            lines.append(f"- [{cap.name}] {cap.purpose} → {cap.path}")
    return "\n".join(lines)

"""独立提示词系统：按角色、阶段和任务动态拼装系统提示词。"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from .context_assembly import (
    PromptSection,
    PromptSectionCache,
    build_context_packet,
    build_default_prompt_sections,
    section,
)
from .models import PipelineStage, ProjectPlan

_REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE_PROMPT_DIR = _REPO_ROOT / "resources" / "prompts" / "roles"
SHARED_PROMPT_DIR = _REPO_ROOT / "resources" / "prompts" / "shared"


def load_role_prompt(role_id: str) -> str:
    path = ROLE_PROMPT_DIR / f"{role_id}.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_shared_prompts() -> str:
    parts = []
    for name in ["manimind-core.md", "anti-bad-script.md"]:
        path = SHARED_PROMPT_DIR / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


@dataclass(slots=True)
class PromptRecipe:
    name: str
    focus: str
    deliverable: str
    task_brief: str
    response_contract: str
    extra_rules: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PromptBundle:
    packet: dict[str, object]
    prompt_sections: list[str]
    system_prompt: str
    user_prompt: str


def _default_quality_rules(role_id: str) -> list[str]:
    shared = [
        "严格忠于输入材料，不得捏造数学结论、证明步骤或外部事实。",
        "术语、符号、变量名和结论口径必须前后一致。",
        "避免占位内容、空泛修辞和模板化官话，输出必须可直接进入下一步执行。",
        "如果信息不足，只能做最小必要假设，并在输出中显式标记该假设。",
    ]
    if role_id == "reviewer":
        return shared + [
            "审核只基于结构化证据，不依赖模糊记忆或主观好感。",
            "不能替人工做 approve，只能输出待人工确认的审核草案。",
        ]
    if role_id.endswith("_worker"):
        return shared + [
            "优先选择稳定、可渲染、可审阅的实现，避免炫技和脆弱 API。",
            "输出必须可落盘、可复跑、可进入审核证据。",
        ]
    return shared + [
        "输出要服务于后续角色，不把关键事实埋在长段自然语言里。",
    ]


def build_recipe_sections(
    packet: dict[str, object],
    recipe: PromptRecipe,
) -> list[PromptSection]:
    role_id = str(packet["role_id"])

    def _system_section() -> str:
        return (
            "你在 ManiMind 多 Agent 编排系统中工作。\n"
            f"当前聚焦：{recipe.focus}\n"
            f"本轮交付：{recipe.deliverable}"
        )

    def _quality_section() -> str:
        lines = [f"- {item}" for item in _default_quality_rules(role_id)]
        lines.extend(f"- {item}" for item in recipe.extra_rules)
        return "质量门槛：\n" + "\n".join(lines)

    def _contract_section() -> str:
        output_contract = packet.get("output_contract")
        lines = [
            f"交付说明：{recipe.deliverable}",
            f"任务说明：{recipe.task_brief}",
            f"响应契约：{recipe.response_contract}",
        ]
        if isinstance(output_contract, str) and output_contract.strip():
            lines.append(f"角色输出契约：{output_contract.strip()}")
        return "\n".join(lines)

    return [
        section(f"{role_id}.shared-contract", load_shared_prompts),
        section(f"{role_id}.role-prompt", lambda: load_role_prompt(role_id)),
        section(f"{role_id}.{recipe.name}.system", _system_section),
        section(f"{role_id}.{recipe.name}.quality", _quality_section),
        section(f"{role_id}.{recipe.name}.contract", _contract_section),
    ]


def _render_sections(
    sections: list[PromptSection],
    cache: PromptSectionCache | None,
) -> list[str]:
    if cache is not None:
        return cache.resolve(sections)
    rendered: list[str] = []
    for item in sections:
        value = item.render()
        if value:
            rendered.append(value)
    return rendered


def _render_user_prompt(recipe: PromptRecipe, payload: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            f"任务：{recipe.task_brief}",
            "输入载荷（JSON）：",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )


def build_prompt_bundle(
    *,
    plan: ProjectPlan,
    session_id: str,
    role_id: str,
    stage: PipelineStage,
    recipe: PromptRecipe,
    payload: dict[str, Any],
    cache: PromptSectionCache | None = None,
    allow_disallowed_stage: bool = False,
) -> PromptBundle:
    packet = build_context_packet(
        plan=plan,
        role_id=role_id,
        stage=stage,
        session_id=session_id,
        allow_disallowed_stage=allow_disallowed_stage,
    )
    sections = build_default_prompt_sections(packet)
    sections.extend(build_recipe_sections(packet, recipe))
    prompt_sections = _render_sections(sections, cache)
    return PromptBundle(
        packet=packet,
        prompt_sections=prompt_sections,
        system_prompt="\n\n".join(prompt_sections),
        user_prompt=_render_user_prompt(recipe, payload),
    )


def explorer_recipe() -> PromptRecipe:
    return PromptRecipe(
        name="explorer-findings",
        focus="从原始材料里提取结构化数学事实、叙事线索和风险点。",
        deliverable="只读探索结果 JSON",
        task_brief=(
            "阅读源材料，提取关键命题、证明骨架、术语候选、章节风险和适合镜头化的切分线索。"
        ),
        response_contract=(
            "只输出一个 JSON 对象。字段必须包含 "
            "`document_findings`, `formula_candidates`, `glossary_candidates`, "
            "`story_beats`, `risk_flags`, `source_highlights`。"
        ),
        extra_rules=[
            "不要直接改写脚本或分镜，只给结构化发现。",
            "风险点要具体到术语、证明缺口、符号歧义或镜头负担。",
        ],
    )


def lead_summary_recipe() -> PromptRecipe:
    return PromptRecipe(
        name="lead-summary",
        focus="沉淀长期上下文：研究总结、术语表、公式目录和风格规范。",
        deliverable="项目级长期上下文 JSON",
        task_brief=(
            "基于探索结果，把原始数学材料整理成可复用的长期事实层，服务后续 planner、coordinator 和 workers。"
        ),
        response_contract=(
            "只输出一个 JSON 对象。字段必须包含 "
            "`research_summary`, `glossary_terms`, `formula_catalog`, `style_guide`。"
        ),
        extra_rules=[
            "研究总结要先讲结论，再讲证明主线和应用价值。",
            "公式目录要保留用途说明，不能只列公式字符串。",
        ],
    )


def planner_recipe() -> PromptRecipe:
    return PromptRecipe(
        name="planner-brief",
        focus="把长期事实转成镜头级规划、审查项和风险控制。",
        deliverable="结构化规划建议 JSON",
        task_brief=(
            "给出适合视频编排的段落切分、每段目标、主要媒介、节奏预算和审核检查项。"
        ),
        response_contract=(
            "只输出一个 JSON 对象。字段必须包含 "
            "`segment_priorities`（每条必须含 semantic_type、cognitive_goal、why_this_worker）, "
            "`must_checks`, `risk_flags`, `visual_briefs`, `narrative_arc`。"
        ),
        extra_rules=[
            "每个 segment 的目标必须清晰可审阅，不能写成泛泛的’介绍背景’。",
            "如果某段数学负荷过高，要主动提出降载或拆段建议。",
            "第一个 segment 的 semantic_type 必须是 hook 或 motivation，不能是 formalization。",
            "不得存在连续两个 density_level=high 的 segment 之间没有 relief/bridge 段。",
        ],
    )


def coordinator_recipe() -> PromptRecipe:
    return PromptRecipe(
        name="coordinator-storyboard",
        focus="生成真正可执行的旁白脚本、分镜和 worker handoff。",
        deliverable="讲解脚本与分镜 JSON",
        task_brief=(
            "围绕既定 segments 生成每段旁白、公式呈现、视觉节拍、以及 html/manim/svg 的执行说明。"
        ),
        response_contract=(
            "只输出一个 JSON 对象。字段必须包含 "
            "`script_outline`, `storyboard_master`, `handoff_notes`, `quality_self_check`。"
            "`quality_self_check` 必须含 every_segment_has_hook, every_formula_has_motivation, "
            "adjacent_segments_have_bridge, no_consecutive_high_density, "
            "last_segment_has_summary, narration_sounds_like_speech，且所有字段必须为 true。"
        ),
        extra_rules=[
            "脚本必须像成片旁白，而不是摘要条目。",
            "每段都要显式说明该段要让观众理解什么，而不是只重复公式。",
            "每段必须有 hook_sentence 和 bridge_to_next。",
            "handoff_notes 中每个 segment 必须有 worker_type、why_this_worker、narration_text。",
        ],
    )


def reviewer_recipe() -> PromptRecipe:
    return PromptRecipe(
        name="review-draft",
        focus="基于结构化证据给出审核草案和人工检查重点。",
        deliverable="审核草案 JSON",
        task_brief=(
            "审查脚本、分镜和 worker 产物是否数学正确、叙事一致、渲染可信，并输出待人工确认的草案。"
        ),
        response_contract=(
            "只输出一个 JSON 对象。字段必须包含 "
            "`summary`, `decision`, `risk_notes`, `must_check`, `evidence_checks`, "
            "`script_quality`, `return_recommendation_if_needed`；"
            "`decision` 必须固定为 `pending_human_confirmation`。"
            "`script_quality` 必须含 has_hooks, has_motivation_before_formulas, "
            "has_bridges, sounds_like_speech, no_consecutive_high_density, weak_points。"
            "`return_recommendation_if_needed` 必须含 should_return, target_roles, must_fix, prompt_patch。"
        ),
        extra_rules=[
            "不能输出 approve/approved。",
            "必须指出人工还需要看的具体风险，而不是只写’整体良好’。",
            "必须检查配音语速与时长对齐：每段视觉产物时长与 timing_manifest 偏差是否 < 10%。",
            "必须检查叙事质量：hook、桥接、动机铺垫是否齐全。",
        ],
    )


def html_worker_recipe() -> PromptRecipe:
    return PromptRecipe(
        name="html-worker",
        focus="生成可直接预览的单文件 HTML 科普动画片段。",
        deliverable="完整 HTML 文档",
        task_brief="输出一个带样式和轻量动效的单文件 HTML 片段，用于科普讲解预览。",
        response_contract=(
            "只输出完整 HTML 文本，不要 Markdown，不要解释。"
            "必须包含 `<!doctype html>`、`<html>`、`<head>`、`<body>`。"
        ),
        extra_rules=[
            "版式要适合 16:9 画面预览。",
            "避免依赖外部字体、外链脚本和网络资源。",
        ],
    )


def svg_worker_recipe() -> PromptRecipe:
    return PromptRecipe(
        name="svg-worker",
        focus="生成可审阅的单文件 SVG 动效片段。",
        deliverable="完整 SVG 文本",
        task_brief="输出一个可直接保存为 `.svg` 的视觉片段，用于补充概念关系、流程或强调动画。",
        response_contract=(
            "只输出完整 SVG 文本，不要 Markdown，不要解释。输出必须以 `<svg` 开头。"
        ),
        extra_rules=[
            "尺寸按 1280x720 设计。",
            "优先使用稳定 SVG 元素和 SMIL/CSS 动画，不引用外部资源。",
        ],
    )


def manim_generate_recipe() -> PromptRecipe:
    return PromptRecipe(
        name="manim-generate",
        focus="生成可渲染的 Manim 场景代码，用于进入最终成片。",
        deliverable="完整 Manim Python 文件",
        task_brief="输出一个可直接渲染的 Manim Community Scene，突出数学证明、结构关系和视觉节奏。",
        response_contract=(
            "只输出完整 Python 代码，不要 Markdown。必须使用 `from manim import *`，"
            "只定义一个 Scene 类，类名必须与输入提供的 `scene_class` 一致。"
        ),
        extra_rules=[
            "优先使用稳定 Manim API，避免插件、外部资产、额外依赖和脆弱 LaTeX。",
            "画面要适合最终视频，禁止只打印一页静态文本后结束。",
        ],
    )


def manim_repair_recipe() -> PromptRecipe:
    return PromptRecipe(
        name="manim-repair",
        focus="基于渲染日志做最小修复，直到场景真正渲染成功。",
        deliverable="修复后的完整 Manim Python 文件",
        task_brief="阅读渲染日志，在最小变更前提下修复 Manim 代码，保留原叙事目标。",
        response_contract=(
            "只输出完整 Python 代码，不要 Markdown。必须保留同一个 Scene 类名。"
        ),
        extra_rules=[
            "不要大改故事，只修复导致渲染失败或明显不稳定的问题。",
            "如果 LaTeX 风险高，优先简化为稳定的 MathTex 或 Text。",
        ],
    )

"""ManiMind CLI 入口。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .bootstrap import check_tools, ensure_workspace, sanitize_identifier
from .artifact_store import has_output_key
from .context_assembly import (
    PromptSectionCache,
    build_context_packet,
    build_default_prompt_sections,
)
from .executor import run_to_review
from .models import (
    EventType,
    PipelineStage,
    SegmentModality,
    SegmentSpec,
    SourceBundle,
    TaskStatus,
)
from .post_produce import finalize_delivery
from .review_workflow import apply_human_review_decision
from .runtime_store import (
    load_execution_task_snapshot,
    persist_agent_message,
    persist_context_packet,
    persist_plan_snapshot,
    persist_task_update,
)
from .task_board import update_execution_task_status
from .workflow import build_project_plan

DEFAULT_SESSION_ID = "manual-session"


def _load_manifest(manifest_path: Path) -> dict:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _build_segments(raw_segments: list[dict]) -> list[SegmentSpec]:
    return [
        SegmentSpec(
            id=item["id"],
            title=item["title"],
            goal=item["goal"],
            narration=item["narration"],
            modality=SegmentModality(item.get("modality", "hybrid")),
            formulas=item.get("formulas", []),
            html_motion_notes=item.get("html_motion_notes", []),
            requires_svg_motion=item.get("requires_svg_motion", False),
            estimated_seconds=item.get("estimated_seconds", 20),
        )
        for item in raw_segments
    ]


def build_plan_from_manifest(manifest_path: Path) -> dict:
    payload = _load_manifest(manifest_path)
    source_bundle = SourceBundle(**payload["source_bundle"])
    segments = _build_segments(payload["segments"])
    plan = build_project_plan(
        project_id=payload["project_id"],
        title=payload["title"],
        source_bundle=source_bundle,
        segments=segments,
    )
    return plan.to_dict()


def _build_plan_model_from_manifest(manifest_path: Path):
    payload = _load_manifest(manifest_path)
    source_bundle = SourceBundle(**payload["source_bundle"])
    segments = _build_segments(payload["segments"])
    return build_project_plan(
        project_id=payload["project_id"],
        title=payload["title"],
        source_bundle=source_bundle,
        segments=segments,
    )


def _configure_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ManiMind 项目工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("bootstrap", help="创建并校验工作区目录")
    subparsers.add_parser("doctor", help="检查工具链可用性")

    plan_parser = subparsers.add_parser("plan", help="从 JSON 清单构建项目计划")
    plan_parser.add_argument("manifest", type=Path)
    plan_parser.add_argument(
        "--session-id",
        type=str,
        default=DEFAULT_SESSION_ID,
        help="本次计划构建对应的会话标识",
    )

    context_parser = subparsers.add_parser(
        "context-pack",
        help="按角色与阶段装配上下文包",
    )
    context_parser.add_argument("manifest", type=Path)
    context_parser.add_argument("role_id", type=str)
    context_parser.add_argument("stage", type=str)
    context_parser.add_argument(
        "--session-id",
        type=str,
        default=DEFAULT_SESSION_ID,
        help="上下文装配对应的会话标识",
    )
    context_parser.add_argument(
        "--render-prompt-sections",
        action="store_true",
        help="额外输出提示词分段渲染结果",
    )
    context_parser.add_argument(
        "--allow-disallowed-stage",
        action="store_true",
        help="允许在角色未声明支持的阶段生成 context packet",
    )

    task_parser = subparsers.add_parser("task-update", help="按状态机规则推进执行任务")
    task_parser.add_argument("manifest", type=Path)
    task_parser.add_argument("task_id", type=str)
    task_parser.add_argument("status", type=str)
    task_parser.add_argument("actor_role", type=str)
    task_parser.add_argument(
        "--session-id",
        type=str,
        default=DEFAULT_SESSION_ID,
        help="任务更新对应的会话标识",
    )

    message_parser = subparsers.add_parser(
        "agent-message",
        help="写入 worker/reviewer 结构化消息事件",
    )
    message_parser.add_argument("manifest", type=Path)
    message_parser.add_argument("event_type", type=str)
    message_parser.add_argument("role_id", type=str)
    message_parser.add_argument("stage", type=str)
    message_parser.add_argument(
        "--task-id",
        type=str,
        default=None,
        help="可选：关联的执行任务 ID",
    )
    message_parser.add_argument(
        "--payload",
        type=str,
        default="{}",
        help="JSON 字符串，写入事件 payload",
    )
    message_parser.add_argument(
        "--session-id",
        type=str,
        default=DEFAULT_SESSION_ID,
        help="消息写入对应的会话标识",
    )

    run_parser = subparsers.add_parser(
        "run-to-review",
        help="按最小闭环把流程推进到 review 阶段",
    )
    run_parser.add_argument("manifest", type=Path)
    run_parser.add_argument(
        "--session-id",
        type=str,
        default=DEFAULT_SESSION_ID,
        help="执行链路对应的会话标识",
    )

    review_parser = subparsers.add_parser(
        "human-review",
        help="人工审核决定（approve 或 return）",
    )
    review_parser.add_argument("manifest", type=Path)
    review_parser.add_argument("decision", type=str, help="approve 或 return")
    review_parser.add_argument(
        "--session-id",
        type=str,
        default=DEFAULT_SESSION_ID,
        help="人工审核对应的会话标识",
    )
    review_parser.add_argument("--reason", type=str, default=None)
    review_parser.add_argument("--must-fix", type=str, default=None)
    review_parser.add_argument("--should-keep", type=str, default=None)
    review_parser.add_argument("--prompt-patch", type=str, default=None)
    review_parser.add_argument(
        "--target-roles",
        type=str,
        default="coordinator,reviewer,html_worker,manim_worker,svg_worker",
        help="逗号分隔目标角色，仅 return 时有效",
    )

    finalize_parser = subparsers.add_parser(
        "finalize",
        help="在审核通过后执行后处理并完成 package",
    )
    finalize_parser.add_argument("manifest", type=Path)
    finalize_parser.add_argument(
        "--session-id",
        type=str,
        default=DEFAULT_SESSION_ID,
        help="后处理对应的会话标识",
    )
    finalize_parser.add_argument(
        "--tts-provider",
        type=str,
        default="powershell_sapi",
        help="TTS provider: powershell_sapi | command | f5_tts | noop",
    )

    return parser


def main() -> None:
    parser = _configure_parser()
    args = parser.parse_args()

    if args.command == "bootstrap":
        print(json.dumps(ensure_workspace(), ensure_ascii=False, indent=2))
        return

    if args.command == "doctor":
        print(json.dumps(check_tools(), ensure_ascii=False, indent=2))
        return

    if args.command == "plan":
        plan = _build_plan_model_from_manifest(args.manifest)
        persisted = persist_plan_snapshot(
            plan=plan,
            session_id=args.session_id,
            source_manifest=str(args.manifest),
        )
        print(
            json.dumps(
                {
                    "plan": plan.to_dict(),
                    "persisted_paths": persisted,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "context-pack":
        plan = _build_plan_model_from_manifest(args.manifest)
        load_execution_task_snapshot(plan)
        stage = PipelineStage(args.stage)
        try:
            packet = build_context_packet(
                plan=plan,
                role_id=args.role_id,
                stage=stage,
                allow_disallowed_stage=args.allow_disallowed_stage,
                session_id=args.session_id,
            )
        except PermissionError as exc:
            raise SystemExit(str(exc)) from exc

        output: dict[str, object] = {"context_packet": packet}
        prompt_sections: list[str] | None = None
        if args.render_prompt_sections:
            cache = PromptSectionCache()
            prompt_sections = cache.resolve(build_default_prompt_sections(packet))
            output["prompt_sections"] = prompt_sections
        output["persisted_paths"] = persist_context_packet(
            plan=plan,
            session_id=args.session_id,
            packet=packet,
            prompt_sections=prompt_sections,
        )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if args.command == "task-update":
        plan = _build_plan_model_from_manifest(args.manifest)
        load_execution_task_snapshot(plan)
        result = update_execution_task_status(
            plan=plan,
            task_id=args.task_id,
            new_status=TaskStatus(args.status),
            actor_role=args.actor_role,
            output_checker=lambda key: has_output_key(plan, args.session_id, key),
        )
        mutation = {
            "success": result.success,
            "task_id": result.task_id,
            "from_status": result.from_status,
            "to_status": result.to_status,
            "reason": result.reason,
            "verification_nudge_needed": result.verification_nudge_needed,
        }
        persisted = persist_task_update(
            plan=plan,
            session_id=args.session_id,
            mutation=mutation,
        )
        print(
            json.dumps(
                {
                    "mutation": mutation,
                    "execution_tasks": [task.to_dict() for task in plan.execution_tasks],
                    "persisted_paths": persisted,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "agent-message":
        plan = _build_plan_model_from_manifest(args.manifest)
        load_execution_task_snapshot(plan)
        try:
            event_type = EventType(args.event_type)
        except ValueError as exc:
            raise SystemExit(f"unsupported_event_type: {args.event_type}") from exc
        try:
            stage = PipelineStage(args.stage)
        except ValueError as exc:
            raise SystemExit(f"unsupported_stage: {args.stage}") from exc
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid_payload_json: {exc}") from exc
        if not isinstance(payload, dict):
            raise SystemExit("invalid_payload_json: payload must be JSON object")
        persist_agent_message(
            plan=plan,
            session_id=args.session_id,
            event_type=event_type,
            role_id=args.role_id,
            stage=stage,
            payload=payload,
            task_id=args.task_id,
        )
        safe_session_id = sanitize_identifier(args.session_id)
        print(
            json.dumps(
                {
                    "event_type": event_type.value,
                    "role_id": args.role_id,
                    "stage": stage.value,
                    "task_id": args.task_id,
                    "payload": payload,
                    "persisted_paths": {
                        "project_events": str(
                            Path(plan.runtime_layout.project_context_dir) / "events.jsonl"
                        ),
                        "session_events": str(
                            Path(plan.runtime_layout.session_context_root)
                            / safe_session_id
                            / "events.jsonl"
                        ),
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "run-to-review":
        plan = _build_plan_model_from_manifest(args.manifest)
        result = run_to_review(
            plan=plan,
            session_id=args.session_id,
            source_manifest=str(args.manifest),
        )
        print(
            json.dumps(
                {
                    "result": result,
                    "execution_tasks": [task.to_dict() for task in plan.execution_tasks],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "human-review":
        plan = _build_plan_model_from_manifest(args.manifest)
        load_execution_task_snapshot(plan)
        target_roles = [item.strip() for item in args.target_roles.split(",") if item.strip()]
        try:
            result = apply_human_review_decision(
                plan=plan,
                session_id=args.session_id,
                decision=args.decision,
                reason=args.reason,
                must_fix=args.must_fix,
                should_keep=args.should_keep,
                prompt_patch=args.prompt_patch,
                target_roles=target_roles or None,
            )
        except (ValueError, RuntimeError) as exc:
            raise SystemExit(str(exc)) from exc
        print(
            json.dumps(
                {
                    "result": result,
                    "current_stage": plan.current_stage.value,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "finalize":
        plan = _build_plan_model_from_manifest(args.manifest)
        try:
            result = finalize_delivery(
                plan=plan,
                session_id=args.session_id,
                tts_provider=args.tts_provider,
            )
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        print(
            json.dumps(
                {
                    "result": result,
                    "execution_tasks": [task.to_dict() for task in plan.execution_tasks],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return


if __name__ == "__main__":
    main()

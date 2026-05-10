"""ManiMind 工作流编排规则与任务切分策略。"""

from __future__ import annotations

from .bootstrap import build_runtime_layout
from .models import (
    AgentMode,
    AgentProfile,
    ContextRecord,
    ContextScope,
    ExecutionTask,
    PipelineStage,
    ProjectPlan,
    ReviewCheckpoint,
    SegmentModality,
    SegmentSpec,
    SourceBundle,
    WorkerKind,
    WorkerTask,
)


DEFAULT_STAGES = [
    PipelineStage.PRESTART,
    PipelineStage.INGEST,
    PipelineStage.SUMMARIZE,
    PipelineStage.PLAN,
    PipelineStage.DISPATCH,
    PipelineStage.REVIEW,
    PipelineStage.POST_PRODUCE,
    PipelineStage.PACKAGE,
    PipelineStage.DONE,
]


def build_context_blueprint(project_id: str) -> list[ContextRecord]:
    return [
        ContextRecord(
            key=f"{project_id}.research.summary",
            scope=ContextScope.LONG_TERM,
            summary="论文与笔记的研究总结",
            writer_role="lead",
            consumer_roles=["coordinator", "html_worker", "manim_worker", "svg_worker", "reviewer"],
            lifecycle="project",
            invalidation_rule="new_ingest_round",
            sticky=True,
        ),
        ContextRecord(
            key=f"{project_id}.glossary",
            scope=ContextScope.LONG_TERM,
            summary="术语表与概念统一口径",
            writer_role="lead",
            consumer_roles=["coordinator", "html_worker", "manim_worker", "svg_worker", "reviewer"],
            lifecycle="project",
            invalidation_rule="new_ingest_round",
            sticky=True,
        ),
        ContextRecord(
            key=f"{project_id}.formula.catalog",
            scope=ContextScope.LONG_TERM,
            summary="公式目录与解释",
            writer_role="lead",
            consumer_roles=["coordinator", "manim_worker", "reviewer"],
            lifecycle="project",
            invalidation_rule="new_ingest_round",
            sticky=True,
        ),
        ContextRecord(
            key=f"{project_id}.style.guide",
            scope=ContextScope.LONG_TERM,
            summary="受众画像与视觉风格规范",
            writer_role="lead",
            consumer_roles=["coordinator", "html_worker", "manim_worker", "svg_worker", "reviewer"],
            lifecycle="project",
            invalidation_rule="manual_style_update",
            sticky=True,
        ),
        ContextRecord(
            key=f"{project_id}.narration.script",
            scope=ContextScope.LONG_TERM,
            summary="讲解脚本与叙事节奏",
            writer_role="coordinator",
            consumer_roles=["html_worker", "manim_worker", "svg_worker", "reviewer"],
            lifecycle="project",
            invalidation_rule="storyboard_replanned",
            sticky=True,
        ),
        ContextRecord(
            key=f"{project_id}.storyboard.master",
            scope=ContextScope.LONG_TERM,
            summary="已批准分镜版本",
            writer_role="coordinator",
            consumer_roles=["html_worker", "manim_worker", "svg_worker", "reviewer"],
            lifecycle="project",
            invalidation_rule="storyboard_replanned",
            sticky=True,
        ),
        ContextRecord(
            key=f"{project_id}.asset.manifest",
            scope=ContextScope.LONG_TERM,
            summary="片段资产索引与交付清单",
            writer_role="lead",
            consumer_roles=["reviewer", "lead"],
            lifecycle="project",
            invalidation_rule="rebuild_or_post_produce_retry",
            sticky=True,
        ),
        ContextRecord(
            key=f"{project_id}.review.report",
            scope=ContextScope.LONG_TERM,
            summary="审核结论与阻塞项",
            writer_role="reviewer",
            consumer_roles=["lead"],
            lifecycle="project",
            invalidation_rule="next_review_round",
            sticky=True,
        ),
        ContextRecord(
            key=f"{project_id}.session.handoff",
            scope=ContextScope.SHORT_TERM,
            summary="当前会话交接记录",
            writer_role="lead",
            consumer_roles=["coordinator", "html_worker", "manim_worker", "svg_worker", "reviewer"],
            lifecycle="session",
            invalidation_rule="session_end_or_new_session",
        ),
    ]


def build_worker_tasks(project_id: str, segment: SegmentSpec) -> list[WorkerTask]:
    shared_inputs = [
        f"{project_id}.research.summary",
        f"{project_id}.glossary",
        f"{project_id}.formula.catalog",
        f"{project_id}.style.guide",
        f"{project_id}.narration.script",
        f"{project_id}.storyboard.master",
    ]
    tasks: list[WorkerTask] = []

    if segment.modality in {SegmentModality.HTML, SegmentModality.HYBRID}:
        tasks.append(
            WorkerTask(
                worker=WorkerKind.HTML,
                segment_id=segment.id,
                objective=f"生成 HTML 科普片段：{segment.title}",
                input_context_keys=shared_inputs,
                long_term_outputs=[f"{project_id}.html.{segment.id}.approved"],
                short_term_outputs=[f"{project_id}.session.html.{segment.id}"],
            )
        )

    if segment.modality in {SegmentModality.MANIM, SegmentModality.HYBRID} or segment.formulas:
        tasks.append(
            WorkerTask(
                worker=WorkerKind.MANIM,
                segment_id=segment.id,
                objective=f"生成 Manim 数学片段：{segment.title}",
                input_context_keys=shared_inputs,
                long_term_outputs=[f"{project_id}.manim.{segment.id}.approved"],
                short_term_outputs=[f"{project_id}.session.manim.{segment.id}"],
            )
        )

    if segment.modality in {SegmentModality.SVG, SegmentModality.HYBRID} or segment.requires_svg_motion:
        tasks.append(
            WorkerTask(
                worker=WorkerKind.SVG,
                segment_id=segment.id,
                objective=f"生成 SVG 动效片段：{segment.title}",
                input_context_keys=shared_inputs,
                long_term_outputs=[f"{project_id}.svg.{segment.id}.approved"],
                short_term_outputs=[f"{project_id}.session.svg.{segment.id}"],
            )
        )

    return tasks


def build_review_checkpoints(
    project_id: str, worker_tasks: list[WorkerTask]
) -> list[ReviewCheckpoint]:
    worker_outputs = [
        output_key
        for task in worker_tasks
        for output_key in task.long_term_outputs
    ]
    return [
        ReviewCheckpoint(
            name="数学正确性",
            stage=PipelineStage.REVIEW,
            required_inputs=[
                f"{project_id}.research.summary",
                f"{project_id}.formula.catalog",
                f"{project_id}.narration.script",
            ],
        ),
        ReviewCheckpoint(
            name="叙事与分镜一致性",
            stage=PipelineStage.REVIEW,
            required_inputs=[
                f"{project_id}.style.guide",
                f"{project_id}.narration.script",
                f"{project_id}.storyboard.master",
            ]
            + worker_outputs,
        ),
        ReviewCheckpoint(
            name="渲染可执行性",
            stage=PipelineStage.REVIEW,
            required_inputs=[f"{project_id}.session.handoff"] + worker_outputs,
        ),
    ]


def build_agent_profiles(
    project_id: str, worker_tasks: list[WorkerTask]
) -> list[AgentProfile]:
    shared_inputs = [
        f"{project_id}.research.summary",
        f"{project_id}.glossary",
        f"{project_id}.formula.catalog",
        f"{project_id}.style.guide",
        f"{project_id}.narration.script",
        f"{project_id}.storyboard.master",
    ]
    worker_outputs = [
        output_key
        for task in worker_tasks
        for output_key in task.long_term_outputs
    ]

    return [
        AgentProfile(
            id="lead",
            mode=AgentMode.STRUCTURED_WRITE,
            responsibility="维护项目全局状态、汇总上下文并推进阶段切换。",
            allowed_stages=[
                PipelineStage.PRESTART,
                PipelineStage.INGEST,
                PipelineStage.SUMMARIZE,
                PipelineStage.DISPATCH,
                PipelineStage.POST_PRODUCE,
                PipelineStage.PACKAGE,
            ],
            required_inputs=[f"{project_id}.session.handoff"],
            owned_outputs=[
                f"{project_id}.research.summary",
                f"{project_id}.glossary",
                f"{project_id}.formula.catalog",
                f"{project_id}.asset.manifest",
            ],
            output_contract="只能写入结构化项目状态，不直接替代所有媒体子任务。",
        ),
        AgentProfile(
            id="explorer",
            mode=AgentMode.READ_ONLY,
            responsibility="只读检索论文、现有代码与第三方资产中的相关模式。",
            allowed_stages=[
                PipelineStage.PRESTART,
                PipelineStage.INGEST,
                PipelineStage.SUMMARIZE,
                PipelineStage.PLAN,
            ],
            required_inputs=[],
            owned_outputs=[],
            output_contract="只返回搜索发现与候选引用，不直接落盘项目产物。",
        ),
        AgentProfile(
            id="planner",
            mode=AgentMode.READ_ONLY,
            responsibility="只读分析约束并提出分镜与实现规划建议。",
            allowed_stages=[PipelineStage.SUMMARIZE, PipelineStage.PLAN],
            required_inputs=shared_inputs[:5],
            owned_outputs=[],
            output_contract="只能产出规划建议，正式分镜需由协调层写入结构化上下文。",
        ),
        AgentProfile(
            id="coordinator",
            mode=AgentMode.STRUCTURED_WRITE,
            responsibility="生成讲解脚本、分镜和任务分发表，负责把建议落实为结构化计划。",
            allowed_stages=[PipelineStage.PLAN, PipelineStage.DISPATCH],
            required_inputs=shared_inputs[:5],
            owned_outputs=[
                f"{project_id}.narration.script",
                f"{project_id}.storyboard.master",
                f"{project_id}.session.handoff",
            ],
            output_contract="必须写出可追溯任务分发结果，不能只停留在自然语言说明。",
        ),
        AgentProfile(
            id="html_worker",
            mode=AgentMode.STRUCTURED_WRITE,
            responsibility="生成 HTML 科普片段并回填片段索引。",
            allowed_stages=[PipelineStage.DISPATCH],
            required_inputs=shared_inputs,
            owned_outputs=[
                output
                for task in worker_tasks
                if task.worker == WorkerKind.HTML
                for output in task.long_term_outputs
            ],
            output_contract="只负责 HTML 片段及其回传说明，不越权修改其他媒介片段。",
        ),
        AgentProfile(
            id="manim_worker",
            mode=AgentMode.STRUCTURED_WRITE,
            responsibility="生成 Manim 数学片段并回填公式动画结果。",
            allowed_stages=[PipelineStage.DISPATCH],
            required_inputs=shared_inputs,
            owned_outputs=[
                output
                for task in worker_tasks
                if task.worker == WorkerKind.MANIM
                for output in task.long_term_outputs
            ],
            output_contract="只负责 Manim 片段及其回传说明，不跨写 HTML 或 SVG 产物。",
        ),
        AgentProfile(
            id="svg_worker",
            mode=AgentMode.STRUCTURED_WRITE,
            responsibility="生成 SVG 补充动效并记录局部失败与重试信息。",
            allowed_stages=[PipelineStage.DISPATCH],
            required_inputs=shared_inputs,
            owned_outputs=[
                output
                for task in worker_tasks
                if task.worker == WorkerKind.SVG
                for output in task.long_term_outputs
            ],
            output_contract="只负责 SVG 片段及其回传说明，失败信息必须进入短期上下文。",
        ),
        AgentProfile(
            id="reviewer",
            mode=AgentMode.VERIFY_ONLY,
            responsibility="只消费结构化产物并给出可执行的放行或阻塞结论。",
            allowed_stages=[PipelineStage.REVIEW],
            required_inputs=shared_inputs + worker_outputs,
            owned_outputs=[f"{project_id}.review.report"],
            output_contract="必须提供基于证据的审核结论，审核未通过前禁止进入后处理。",
        ),
    ]


def build_execution_tasks(
    project_id: str, worker_tasks: list[WorkerTask]
) -> list[ExecutionTask]:
    segment_task_ids = [
        f"render.{task.segment_id}.{task.worker.value}" for task in worker_tasks
    ]
    review_blocked_by = segment_task_ids or ["plan.storyboard"]

    tasks = [
        ExecutionTask(
            id="ingest.sources",
            subject="归档论文、笔记和风格输入",
            owner_role="lead",
            active_form="正在归档输入",
            blocks=["summarize.research"],
            required_outputs=[f"{project_id}.session.handoff"],
        ),
        ExecutionTask(
            id="summarize.research",
            subject="生成研究总结、术语表和公式目录",
            owner_role="lead",
            active_form="正在总结研究素材",
            blocked_by=["ingest.sources"],
            blocks=["plan.storyboard"],
            required_outputs=[
                f"{project_id}.research.summary",
                f"{project_id}.glossary",
                f"{project_id}.formula.catalog",
            ],
        ),
        ExecutionTask(
            id="plan.storyboard",
            subject="生成讲解脚本、分镜和任务分发表",
            owner_role="coordinator",
            active_form="正在规划分镜与任务",
            blocked_by=["summarize.research"],
            blocks=segment_task_ids or ["review.outputs"],
            required_outputs=[
                f"{project_id}.narration.script",
                f"{project_id}.storyboard.master",
            ],
        ),
    ]

    for task in worker_tasks:
        tasks.append(
            ExecutionTask(
                id=f"render.{task.segment_id}.{task.worker.value}",
                subject=task.objective,
                owner_role=f"{task.worker.value}_worker",
                active_form=f"正在产出 {task.worker.value} 片段",
                blocked_by=["plan.storyboard"],
                blocks=["review.outputs"],
                required_outputs=task.long_term_outputs + task.short_term_outputs,
            )
        )

    tasks.append(
        ExecutionTask(
            id="review.outputs",
            subject="审核结构化产物并给出放行或阻塞结论",
            owner_role="reviewer",
            active_form="正在审核产物证据",
            blocked_by=review_blocked_by,
            blocks=["post_produce.package"],
            required_outputs=[f"{project_id}.review.report"],
            verification_required=True,
        )
    )
    tasks.append(
        ExecutionTask(
            id="post_produce.package",
            subject="仅在审核通过后执行后处理与交付打包",
            owner_role="lead",
            active_form="正在打包交付产物",
            blocked_by=["review.outputs"],
            required_outputs=[f"{project_id}.asset.manifest"],
        )
    )

    return tasks


def build_project_plan(
    project_id: str,
    title: str,
    source_bundle: SourceBundle,
    segments: list[SegmentSpec],
) -> ProjectPlan:
    tasks: list[WorkerTask] = []
    for segment in segments:
        tasks.extend(build_worker_tasks(project_id, segment))

    return ProjectPlan(
        project_id=project_id,
        title=title,
        source_bundle=source_bundle,
        stages=DEFAULT_STAGES,
        segments=segments,
        tasks=tasks,
        contexts=build_context_blueprint(project_id),
        review_checkpoints=build_review_checkpoints(project_id, tasks),
        agent_profiles=build_agent_profiles(project_id, tasks),
        execution_tasks=build_execution_tasks(project_id, tasks),
        runtime_layout=build_runtime_layout(project_id),
    )

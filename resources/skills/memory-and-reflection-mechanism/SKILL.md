---
name: memory-and-reflection-mechanism
description: "为 ManiMind 系统设计和验证跨会话的记忆与反思机制。当前此能力完全缺失——没有跨任务的失败模式库、没有生成质量自评、没有经验积累。本 skill 定义记忆和反思的最小可行设计及其在现有 runtime 架构中的落盘位置。触发短语：记忆机制、反思机制、experience memory、reflection、失败模式库、self-improvement。"
roles: ["lead", "explorer", "coordinator", "reviewer"]
stages: ["review", "post_produce"]
---

# 记忆与反思机制

## Overview

ManiMind 当前的结构化上下文管理系统（`runtime/projects/` + `runtime/sessions/`）只覆盖"当前任务链路"内的状态传递，缺乏跨任务的长期经验积累。具体缺失：

| 能力 | 当前状态 | 差距 |
|------|----------|------|
| 经验记忆 | 无 | 相同类型的 Manim 渲染错误每次从零开始修复 |
| 反思 | 无 | 每次 run_to_review 完成后无质量自评和策略调整 |
| 失败模式库 | 无 | `manim_repair_recipe()` 每次都做全量重新生成 |
| 媒介选择经验 | 无 | planner 每次从零判断 HTML vs Manim 路由 |

本 skill 定义两类"记忆"的最小可行设计：

1. **经验记忆**（Experience Memory）：跨任务的失败模式、修复策略、媒介选择偏好。落盘在 `runtime/projects/<project_id>/experience/patterns.jsonl`。
2. **反思**（Reflection）：当前任务执行完毕后对输出的质量评估和改进方向。落盘在 `runtime/projects/<project_id>/experience/reflections.jsonl`。

## When to use

- 设计记忆/反思系统的初始架构时（规划阶段）
- 每次 `run_to_review` 完成后（自动触发反思后置任务）
- 人工打回（`return`）时（提取经验）
- 相同类型的 Manim 错误再次出现时（经验未被利用的证据）
- 阶段里程碑：检查经验库规模是否在合理增长
- coordinator 规划新项目时（读取历史媒介选择经验）

## Required inputs

1. **当前任务的完整执行记录**：`runtime/projects/<project_id>/events.jsonl`
2. **审核结果**：`review.report`（pass/return）和 `review.return.memo`
3. **Manim Worker 修复历史**：`outputs/<project_id>/manim/<seg_id>/attempt_*.py` 和 `attempt_*.log`
4. **已有的经验库**（如果存在）：`runtime/projects/<project_id>/experience/patterns.jsonl`
5. **已有的反思记录**（如果存在）：`runtime/projects/<project_id>/experience/reflections.jsonl`

## Step-by-step process

### Step 1: 经验提取

当以下事件发生时，尝试从执行记录中提取经验：

事件 A：Manim Worker 经修复后成功渲染
- 提取：错误类型、根因、修复策略、修复行数
- 形成 `fix_pattern`
- 如果该 pattern 已存在（相同 error_type + root_cause），只更新 `occurrence_count` 和 `last_seen_at`
- 如果该 pattern 不存在，新增记录

事件 B：人工 reviewer 打回
- 提取：打回原因、must_fix、should_keep、target_roles
- 形成 `review_pattern`
- 记录关系：打回原因 → 受影响的角色 → 修复方向

事件 C：planner 做出了某种媒介路由决策
- 提取：segment 语义类型、特征参数、路由结果、后续成功/失败
- 形成 `routing_pattern`
- 用于后续向 coordinator 推荐路由

### Step 2: 经验落盘

经验文件格式（`patterns.jsonl`，每行一条 JSON）：

```json
{
  "pattern_id": "latex_xrightarrow_multiline",
  "pattern_type": "fix_pattern|review_pattern|routing_pattern",
  "error_type": "latex_error",
  "root_cause": "Manim 0.20.x 中 MathTex 不支持 \\xrightarrow 多行参数",
  "fix_strategy": "用 Arrow + Text 替代，3 行变更",
  "occurrence_count": 3,
  "project_ids": ["cauchy-001", "cauchy-002", "max-function-001"],
  "first_seen_at": "2026-05-10T...",
  "last_seen_at": "2026-05-12T...",
  "source_task_id": "render.seg-02.manim",
  "evidence_path": "outputs/cauchy-002/manim/seg-02/attempt_001.log"
}
```

落盘约束：
- 相同 `pattern_id` 不重复写入（更新 occurrence_count）
- 至少出现 2 次才记录（单次可能是偶发问题）
- 不保存完整代码正文（只保存引用路径 + 修复摘要）
- 不同项目的经验混合存储在同一 `patterns.jsonl`（项目级，非仓库级）

### Step 3: 反思触发

反思在以下时机触发（作为异步后置任务，不阻塞主链路）：

1. `run_to_review` 完成后
2. 人工 `approve` 后
3. 人工 `return` 后

反思内容（`reflections.jsonl`）：

```json
{
  "reflection_id": "ref-2026-05-12-001",
  "task_id": "render.seg-02.manim",
  "stage": "dispatch",
  "quality_self_score": "pass_with_warnings",
  "what_worked": [
    "切线可视化效果清晰",
    "MathTex 替换为 Text 避免了 LaTeX 超时"
  ],
  "what_failed": [
    "第一次尝试的 \\xrightarrow 多行参数导致渲染崩溃"
  ],
  "next_time_hint": "优先使用 always_redraw + ValueTracker 替代复杂 LaTeX 箭头",
  "should_update_skill": true,
  "skill_target": "resources/skills/manim/SKILL.md",
  "skill_patch_suggestion": "在 LaTeX 限制段落新增 \\xrightarrow 限制说明",
  "timing": {
    "total_attempts": 2,
    "total_llm_calls": 2,
    "total_wall_time_seconds": 145
  },
  "created_at": "2026-05-12T18:30:00Z"
}
```

### Step 4: 经验注入

在下一次执行中，将相关经验注入到对应角色的 prompt 中：

| 角色 | 注入方式 | 注入内容 |
|------|----------|----------|
| `manim_worker` | `prompt_system.py` 的 generate payload 新增 `past_patterns` 字段 | 最近 5 条 `fix_pattern` |
| `coordinator` | `context_assembly` 的 `capabilities` 段增加经验摘要 | `routing_pattern` 中成功的路由选择 |
| `explorer` | `prompt_system.py` 的 explorer payload | `review_pattern`（了解哪些内容被反复打回） |
| `planner` | `prompt_system.py` 的 planner payload | `routing_pattern`（媒介选择的历史成功率） |

注入量控制：
- 每条 pattern 摘要不超过 100 字符
- 每个角色最多注入 5 条相关经验
- 注入顺序：按 `occurrence_count` 降序（高频问题优先）
- 不注入 `project_id` 不在当前项目的经验（避免跨项目污染）

### Step 5: 经验库维护

定期执行维护操作（建议每 10 次 run 后）：

1. 合并相似 pattern：相同 `error_type` + 相似 `root_cause` → 保留 `fix_strategy` 最成功的一条
2. 淘汰过期 pattern：超过 30 天未出现的 pattern 降级为 `archived`
3. 统计经验库健康度：新增 pattern 速率、pattern 解决率、平均 occurrence_count

## Forbidden behaviors

- 禁止把经验记忆混入长期上下文（`review.report` 或 `research.summary`）
- 禁止在反思中修改原始产物（反思是观察，不是重写）
- 禁止基于单次失败过度泛化经验（occurrence_count ≥ 2 才记录）
- 禁止让反思阻塞主执行链路（反思是异步后置）
- 禁止在 patterns.jsonl 中保存完整代码正文（只保存模式摘要 + 引用路径）
- 禁止把不同项目的经验混入同一个经验文件（每个 project_id 独立）
- 禁止在没有 LLM 调用的情况下伪造反思记录

## Verification checklist

| # | 检查项 | 方式 |
|---|--------|------|
| 1 | patterns.jsonl 格式正确（每行合法 JSON） | `jq . patterns.jsonl` |
| 2 | pattern_id 唯一（无重复写入） | `jq -r .pattern_id patterns.jsonl | sort | uniq -d` |
| 3 | 相同 pattern 只更新不重复 | 检查 occurrence_count 递增 |
| 4 | reflections.jsonl 格式正确 | `jq . reflections.jsonl` |
| 5 | 反思记录 non-blocking（不增加主链路延迟） | 检查触发时机 |
| 6 | 经验注入不影响角色输出契约 | 对比注入前后的 prompt 结构 |
| 7 | 经验不跨项目泄露 | project_id 过滤检查 |
| 8 | 物理路径遵循约定：`runtime/projects/<project_id>/experience/` | stat 检查 |

## Common failure modes

| 模式 | 症状 | 修复 |
|------|------|------|
| 经验膨胀 | patterns.jsonl 超过 1000 行，注入 prompt 过长 | 限制每个角色最多 5 条，每条 100 字符 |
| 模式泛化过度 | "所有 LaTeX 错误都用 Text 替代"导致画面质量下降 | 细分 error_type，不同子类型不同策略 |
| 经验跨项目污染 | 项目 A 的 routing_pattern 被错误注入项目 B | 严格按 project_id 过滤 |
| 反思信息量低 | 所有反思都是 "what_worked: everything" | 在反思 prompt 中强制要求至少 1 条 what_failed |
| 经验从未被利用 | patterns.jsonl 持续增长但 worker 仍犯同样错误 | 检查经验注入链路是否实际生效 |
| 物理路径混写 | 经验文件写入了 session/ 目录 | 固定路径约定 |

## Expected output

```json
{
  "experience_update": {
    "new_patterns": 0,
    "updated_patterns": 1,
    "pattern_id": "latex_xrightarrow_multiline",
    "occurrence_count": 3,
    "action": "updated"
  },
  "reflection": {
    "reflection_id": "ref-2026-05-12-001",
    "task_id": "render.seg-manim.manim",
    "quality_self_score": "pass_with_warnings",
    "what_worked": [
      "切线可视化效果清晰",
      "MathTex 替换为 Text 避免了 LaTeX 超时"
    ],
    "what_failed": [
      "第一次尝试的 \\xrightarrow 多行参数导致渲染崩溃"
    ],
    "next_time_hint": "优先使用 always_redraw + ValueTracker 替代复杂 LaTeX 箭头",
    "should_update_skill": true,
    "skill_target": "resources/skills/manim/SKILL.md"
  },
  "patterns_injected": {
    "target_role": "manim_worker",
    "patterns_count": 3,
    "injected_by": "prompt_system.py payload.past_patterns"
  },
  "experience_health": {
    "total_patterns": 12,
    "total_reflections": 5,
    "avg_occurrence_count": 2.3
  }
}
```

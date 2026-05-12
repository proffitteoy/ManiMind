---
name: task-decomposition-planning
description: "对一篇新的数学论文或科普话题，设计并验证从原始论文到可执行任务 DAG 的完整分解方案。强制按 intro -> formula_core -> bridge -> summary 的叙事骨架切分，并严格路由到正确的 worker（HTML 负责引子/桥接/总结，Manim 负责公式核心，SVG 仅按需增强）。解决当前仓库中媒介路由未收敛的核心问题。触发短语：任务分解、segment planning、分镜设计、task DAG、媒介路由、narrative arc。"
roles: ["planner", "coordinator", "lead"]
stages: ["plan", "summarize"]
---

# 任务分解与规划

## Overview

当前 ManiMind 的任务分解流程是：

```
lead (ingest/summarize) → explorer (explore) → lead (summarize) → planner (plan) → coordinator (plan/dispatch) → workers
```

核心问题：`workflow.py:177-225` 的 `build_worker_tasks()` 按 `segment.modality` 做机械路由——HYBRID 段触发所有三个 worker，HTML 段带 formulas 也会触发 Manim。这导致"媒介路由不收敛"，实际效果接近"所有片段尝试所有媒介"。

本 skill 在 planner 和 coordinator 之间插入结构化的"叙事骨架验证"和"媒介路由收敛"步骤，确保：
- 每个 project 的 segments 列表满足叙事完整性（hook → formula_core → bridge → summary）
- 每个 segment 被分配给正确的 worker（而非全部 HYBRID）
- 公式段之间必须有桥接段
- 高密度段之间必须有 relief 段

## When to use

- 启动新项目（新的 project_id + manifest）时
- 现有项目新增 segments 时
- 人工打回且原因为"媒介路由不当"或"叙事结构缺失"时
- 验收审查前，检查现有项目是否满足叙事骨架约束
- coordinator 执行 `plan.storyboard` 前的规划验证

## Required inputs

1. **研究总结**：`research.summary`（从 `runtime/projects/<project_id>/` 加载）
2. **术语表**：`glossary`
3. **公式目录**：`formula.catalog`
4. **目标受众描述**：来自 manifest 的 `source_bundle.audience`
5. **风格规范**：`style.guide`
6. **预估总时长**：用户指定或默认 5-8 分钟
7. **HTML 能力限制摘要**：`resources/skills/html-animation/SKILL.md` 的模板类型和能力边界
8. **Manim 能力限制摘要**：`resources/skills/manim/SKILL.md` 的 API 限制（LaTeX 限制、动画复杂度上限）

## Step-by-step process

### Step 1: 内容分析

从研究总结和公式目录中提取：
- 核心结论（1 句话）
- 证明主线（关键步骤，2-5 步）
- 需要直观理解的公式（不超过 3 个核心公式）
- 需要动机铺垫的抽象概念
- 适合引子的"问题场景"或"历史轶事"

### Step 2: 叙事骨架设计

强制按以下骨架生成 segment 列表：

```
seg-01 (intro/hook):        引子——抛出问题/场景，让观众知道"为什么关心"
                            媒介：HTML（问题场景卡片 + 数据可视化）
                            时长：10-15 秒
                            密度：low

seg-02 (bridge/motivation): 动机铺垫——用已知概念类比新概念
                            媒介：HTML（对比卡片 + 流程动画）
                            时长：10-15 秒
                            密度：low

seg-03 (formula_core):     公式核心 1——第一个关键公式的直觉+推导
                            媒介：Manim（数学动画）
                            时长：20-30 秒
                            密度：high

seg-04 (bridge):            桥接——回顾上一步结论，引出下一步
                            媒介：HTML（总结卡片 + 过渡动画）
                            时长：10 秒
                            密度：low

seg-05 (formula_core):     公式核心 2（如有）
                            媒介：Manim
                            时长：20-30 秒
                            密度：high

seg-06 (summary):           总结回扣——我们学到了什么，下一步是什么
                            媒介：HTML（总结卡片 + 数据回顾）
                            时长：10-15 秒
                            密度：low
```

关键约束：
- 第一个 segment 的 semantic_type 必须是 hook 或 motivation，不是 formalization
- 不存在连续两个 density_level=high 的 segment
- 每个 formula_core 段前面都有一个 motivation/bridge 段
- 最后一个 segment 的 semantic_type 必须是 summary
- HTML worker 的任务数 > Manim worker 的任务数（引子+桥接+总结 > 纯公式段）
- SVG worker 只在明确需要关系图或覆盖层时启用，不是默认全跑

### Step 3: 媒介路由收敛

为每个 segment 分配 worker：

| 语义类型 | 媒介 | Worker | 条件 |
|----------|------|--------|------|
| hook / motivation / bridge / summary | HTML | html_worker | 始终 |
| formula_core | MANIM | manim_worker | 包含公式 |
| weak_explainer | HTML | html_worker | 科普解释 |
| relationship_diagram | SVG | svg_worker | 仅当需要关系图 |
| comparison_overlay | SVG | svg_worker | 仅当需要增强覆盖层 |

禁止的分配：
- formula_core → html_worker（公式核心不应做成 HTML 幻灯片）
- hook/motivation → manim_worker（引子不应是数学动画）
- 任意 segment → HYBRID（废除 HYBRID 模态，强制单一 worker）

### Step 4: Worker 任务生成

为每个 segment 生成对应的 WorkerTask：

```python
for segment in segments:
    if segment.semantic_type in {"hook", "bridge", "motivation", "summary", "weak_explainer"}:
        tasks.append(WorkerTask(worker=WorkerKind.HTML, ...))
    elif segment.semantic_type == "formula_core":
        tasks.append(WorkerTask(worker=WorkerKind.MANIM, ...))
    elif segment.semantic_type == "relationship_diagram":
        tasks.append(WorkerTask(worker=WorkerKind.SVG, ...))
```

### Step 5: 叙事完整性验证

检查 segment 列表是否满足所有叙事约束：

```json
{
  "has_hook": true,
  "has_motivation_before_first_formula": true,
  "has_bridges": true,
  "has_summary": true,
  "no_consecutive_high_density": true,
  "every_formula_has_hook_sentence": true,
  "every_formula_has_motivation": true,
  "adjacent_segments_have_bridge": true,
  "narration_sounds_like_speech": true
}
```

所有字段必须为 true。任一 false 则规划不通过。

### Step 6: 时长预算

每个 segment 的预估时长在 8-30 秒之间（可配音范围）。

总时长预算：
- 5-8 分钟科普视频：5-8 个 segments，总时长 250-480 秒
- 公式段单段不超过 30 秒（超过则拆分为多个 formula_core + bridge）
- 桥接段不超过 15 秒

## Forbidden behaviors

- 禁止生成没有 hook 段（intro）的 segment 列表
- 禁止生成没有 bridge 段（在 formula_core 之间）的 segment 列表
- 禁止生成没有 summary 段（结尾）的 segment 列表
- 禁止让 manim_worker 负责 intro/bridge/summary 段
- 禁止让 html_worker 负责纯公式推导和证明核心段
- 禁止在连续两个 density_level=high 的公式段之间不插入 relief 段
- 禁止跳过 planner 直接让 coordinator 写 segments
- 禁止使用 HYBRID 模态（强制单一 worker 分配）
- 禁止生成超过 15 个 segments（信息过载）
- 禁止公式段在 8 秒内完成（无法有效讲解）

## Verification checklist

| # | 检查项 | 方式 |
|---|--------|------|
| 1 | 第一个 segment 是 hook 或 motivation | 检查 semantic_type |
| 2 | 不存在连续 density_level=high | 遍历 segments |
| 3 | 每个 formula_core 前面有 motivation/bridge | 遍历 segments |
| 4 | 最后一个 segment 是 summary | 检查 semantic_type |
| 5 | HTML worker 任务数 > Manim worker 任务数 | 计数 |
| 6 | SVG worker 非默认（只在明确需要时） | 检查分配原因 |
| 7 | 每段时长 8-30 秒 | 检查 estimated_seconds |
| 8 | 公式段 LaTeX 不超过 Manim 复杂度上限 | 参考 manim SKILL.md |
| 9 | 所有 narrative_completeness_check 为 true | 逐项检查 |
| 10 | 无 HYBRID 模态 | grep modality |

## Common failure modes

| 模式 | 症状 | 修复 |
|------|------|------|
| 公式堆砌 | 所有 segments 都是 formula_core，无 hook/bridge/summary | 强制插入 hook + bridge + summary |
| 媒介混用 | 同一个 segment 同时触发 HTML + Manim + SVG | 废除 HYBRID，强制单一分配 |
| 桥接缺失 | 两个 formula_core 直接相邻 | 中间插入 bridge（HTML） |
| 密度失衡 | 前 3 个 segments 都是 high density | 将前 2 个改为 low density 的 motivation |
| 开头冷启动 | 第一个 segment 就是公式 | 添加 hook 段（HTML 问题场景卡片） |
| 结尾断裂 | 最后一个 segment 是 bridge 而非 summary | 添加 summary 段 |
| SVG 泛滥 | 所有 segments 都有 requires_svg_motion=true | 只在明确需要关系图或增强覆盖层时启用 |

## Expected output

```json
{
  "project_id": "cauchy-backward-induction-real",
  "narrative_arc": "hook -> motivation -> formula_core_1 -> bridge -> formula_core_2 -> summary",
  "segments": [
    {
      "id": "seg-01",
      "title": "为什么需要向后归纳",
      "semantic_type": "hook",
      "modality": "html",
      "goal": "用'爬梯子向下'的类比引入向后归纳的概念",
      "estimated_seconds": 15,
      "density_level": "low",
      "formulas": [],
      "hook_sentence": "...",
      "bridge_to_next": "..."
    },
    {
      "id": "seg-02",
      "title": "柯西准则回顾",
      "semantic_type": "motivation",
      "modality": "html",
      "goal": "...",
      "estimated_seconds": 12,
      "density_level": "low",
      "formulas": [],
      "hook_sentence": "...",
      "bridge_to_next": "..."
    },
    {
      "id": "seg-03",
      "title": "向后归纳的形式化",
      "semantic_type": "formula_core",
      "modality": "manim",
      "goal": "...",
      "estimated_seconds": 25,
      "density_level": "high",
      "formulas": ["\\forall\\varepsilon>0,\\exists N,\\forall n,m\\geq N: |a_n-a_m|<\\varepsilon"],
      "hook_sentence": "...",
      "bridge_to_next": "..."
    },
    {
      "id": "seg-04",
      "title": "关键步骤衔接",
      "semantic_type": "bridge",
      "modality": "html",
      "goal": "...",
      "estimated_seconds": 10,
      "density_level": "low",
      "formulas": [],
      "hook_sentence": "...",
      "bridge_to_next": "..."
    },
    {
      "id": "seg-05",
      "title": "归纳步骤的数学验证",
      "semantic_type": "formula_core",
      "modality": "manim",
      "goal": "...",
      "estimated_seconds": 28,
      "density_level": "high",
      "formulas": ["..."],
      "hook_sentence": "...",
      "bridge_to_next": "..."
    },
    {
      "id": "seg-06",
      "title": "总结与展望",
      "semantic_type": "summary",
      "modality": "html",
      "goal": "...",
      "estimated_seconds": 15,
      "density_level": "low",
      "formulas": [],
      "hook_sentence": "..."
    }
  ],
  "worker_allocation": {
    "html_worker": 4,
    "manim_worker": 2,
    "svg_worker": 0
  },
  "narrative_completeness_check": {
    "has_hook": true,
    "has_motivation_before_first_formula": true,
    "has_bridges": true,
    "has_summary": true,
    "no_consecutive_high_density": true,
    "every_formula_has_hook_sentence": true,
    "every_formula_has_motivation": true,
    "adjacent_segments_have_bridge": true,
    "narration_sounds_like_speech": true
  },
  "execution_tasks": [
    {"id": "render.seg-01.html", "blocked_by": ["plan.storyboard"], "blocks": ["review.outputs"]},
    {"id": "render.seg-02.html", "blocked_by": ["plan.storyboard"], "blocks": ["review.outputs"]},
    {"id": "render.seg-03.manim", "blocked_by": ["plan.storyboard"], "blocks": ["review.outputs"]},
    ...
  ]
}
```

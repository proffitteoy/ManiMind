---
name: agent-role-prompt-design
description: "为 ManiMind 系统设计、评审和修改 Agent 角色 Prompt。覆盖两套 Prompt 体系：resources/prompts/roles/*.md（角色定义文档，共 7 个）和 src/manimind/prompt_system.py（PromptRecipe 代码配方，共 9 个）。确保两套 Prompt 与 workflow.py 的角色定义三方一致。触发短语：设计角色 prompt、修改 agent prompt、review role prompt、角色职责定义、prompt consistency check。"
roles: ["lead", "reviewer"]
stages: ["prestart", "plan", "review"]
---

# Agent 角色与 Prompt 设计

## Overview

ManiMind 有两套 Prompt 体系，加上 `workflow.py` 的角色定义，形成三方依赖：

```
resources/prompts/roles/<role_id>.md   ← 人类可读的角色描述文档（7 个角色文件）
src/manimind/prompt_system.py          ← PromptRecipe 代码配方（9 个函数）
src/manimind/workflow.py               ← AgentProfile 级别定义（9 个角色）
```

此外还有两套共享约束：
- `resources/prompts/shared/manimind-core.md`：全局操作契约（5 条核心原则）
- `resources/prompts/shared/anti-bad-script.md`：反烂脚本规则（3 种好脚本结构模式 + 自检清单）

当前不一致风险：
- `resources/prompts/roles/` 只有 7 个文件（缺 `human_reviewer.md`）
- `prompt_system.py` 有 9 个 recipe 函数（多了 `manim_generate_recipe` 和 `manim_repair_recipe`）
- `workflow.py` 有 9 个 AgentProfile

## When to use

- 新增角色时（需要在三处添加定义）
- 修改现有角色职责或输出边界时
- 角色输出质量持续不达标（说明 prompt 约束不够）
- 两套 prompt 出现矛盾（`.md` 文件说"可以写 X"但 recipe 没要求输出 X）
- 添加新的 PipelineStage（需要更新受影响角色的 `allowed_stages`）
- 上下文蓝图变更（`build_context_blueprint`）后需要更新 `required_inputs`
- 发现角色越权（write 了不属于它的 output key）

## Required inputs

1. **要审查/设计的角色 ID**：如 `coordinator`、`manim_worker`
2. **对应的 `.md` 文件**：`resources/prompts/roles/<role_id>.md`（可能不存在）
3. **对应的 recipe 函数**：`src/manimind/prompt_system.py` 中的 `*_recipe()`
4. **对应的 AgentProfile**：`src/manimind/workflow.py` 的 `build_agent_profiles()` 中该角色的定义
5. **该角色最近的执行结果**：`runtime/sessions/<session_id>/events.jsonl`（可选，用于评估）

## Step-by-step process

### Step 1: 建立三方映射

列出当前三方是否对齐：

```text
角色 ID        .md 存在?   recipe 存在?   AgentProfile 存在?
lead           ✓          lead_summary_recipe()  ✓
explorer       ✓          explorer_recipe()       ✓
planner        ✓          planner_recipe()        ✓
coordinator    ✓          coordinator_recipe()    ✓
html_worker    ✓          html_worker_recipe()    ✓
manim_worker   ✓          manim_generate_recipe() ✓
                           manim_repair_recipe()
svg_worker     ✓          svg_worker_recipe()     ✓
reviewer       ✓          reviewer_recipe()       ✓
human_reviewer ✗          (无独立 recipe)         ✓
```

### Step 2: 逐角色对齐检查

对于每个角色，执行以下 6 项对齐检查：

1. **写入权限对齐**：`.md` 文件的"可以写入"列表 == `AgentProfile.owned_outputs`
2. **读取需求对齐**：`.md` 文件的"必须读取"列表 == `AgentProfile.required_inputs`
3. **禁止行为对齐**：`.md` 文件的"不得做"列表 ⊆ `AgentProfile.output_contract` 和 `allowed_stages` 的隐含约束
4. **角色定位对齐**：`PromptRecipe.focus` ≈ `.md` 文件的"角色定位"
5. **输出契约对齐**：`PromptRecipe.deliverable` ≈ `.md` 文件的"输出契约"
6. **共享约束不重复**：`PromptRecipe.extra_rules` 不与 `manimind-core.md` / `anti-bad-script.md` 重复

### Step 3: 特殊角色检查

**coordinator**：
- `quality_self_check` 字段要求 7 个 `true` 子项（every_segment_has_hook, every_formula_has_motivation, adjacent_segments_have_bridge, no_consecutive_high_density, last_segment_has_summary, narration_sounds_like_speech, all_true）
- 与 `anti-bad-script.md` 的自检清单对齐

**reviewer**：
- `decision` 必须固定为 `pending_human_confirmation`
- `script_quality` 字段要求 6 个子检查项
- 与 `anti-bad-script.md` 的自检清单对齐

**human_reviewer**：
- `.md` 文件缺失！需确认是否需要创建
- `AgentProfile` 中 `owned_outputs` = `review.report`、`review.return.memo`、`review.return.prompt_patch`

### Step 4: 新增/修改角色 Prompt

若需要新增角色或修改现有角色：

1. 先更新 `workflow.py` 的 `build_agent_profiles()`（角色画像）
2. 再更新 `prompt_system.py` 的对应 recipe 函数
3. 最后更新 `resources/prompts/roles/<role_id>.md`

修改时必须遵守的规则：
- `read_only` 角色的 recipe 不能有写入指令
- `verify_only` 角色的 recipe 不能有"建议修改为..."的指令
- `structured_write` 角色的 `deliverable` 必须对应 `owned_outputs` 中的 key

### Step 5: Prompt 长度评估

对 system prompt 做 token 估算（每个中文字符 ≈ 2 tokens，英文 ≈ 1.3 tokens）：

| 角色 | system prompt 估算 tokens | 建议上限 |
|------|--------------------------|----------|
| lead | ~800 | 1500 |
| coordinator | ~1200 | 2000 |
| reviewer | ~1000 | 2000 |
| html_worker | ~600 | 1500 |
| manim_worker | ~700 | 1500 |

超限的风险：模型幻觉增加、关键约束被上下文窗口挤出。

### Step 6: 死锁检测

检查是否存在以下循环依赖：
- 角色 A 的 `required_inputs` 需要角色 B 的 `owned_outputs`
- 角色 B 的 `required_inputs` 需要角色 A 的 `owned_outputs`
- 且两者在同一阶段都需要这些输入

## Forbidden behaviors

- 禁止修改角色后只更新一处（必须三处同步）
- 禁止扩大角色的 `allowed_stages` 而不更新 `workflow.py`
- 禁止删除角色的 `output_contract` 约束
- 禁止在 prompt 中加入与 `manimind-core.md` 全局契约冲突的指令
- 禁止给 `read_only` 角色写"你需要生成..."的指令
- 禁止给 `verify_only` 角色写"你可以修改..."的指令
- 禁止在 recipe 的 `extra_rules` 中重复共享 prompt 已有的规则

## Verification checklist

| # | 检查项 | 方式 |
|---|--------|------|
| 1 | `.md` 文件的"可以写入" == AgentProfile.owned_outputs | 逐项 diff |
| 2 | `.md` 文件的"必须读取" == AgentProfile.required_inputs | 逐项 diff |
| 3 | `.md` 文件的"不得做" ⊆ output_contract 和 allowed_stages 隐含约束 | 语义分析 |
| 4 | PromptRecipe.focus ≈ .md "角色定位" | 语义分析 |
| 5 | PromptRecipe.deliverable ≈ .md "输出契约" | 语义分析 |
| 6 | extra_rules 不与共享 prompt 重复 | 比较去重 |
| 7 | coordinator `quality_self_check` 与 anti-bad-script 对齐 | 逐项 diff |
| 8 | reviewer `decision` == "pending_human_confirmation" | 字面检查 |
| 9 | 无循环依赖（deadlock） | DAG 拓扑排序 |
| 10 | system prompt token 数在建议上限内 | 字符数估算 |

## Common failure modes

| 模式 | 症状 | 修复 |
|------|------|------|
| 三方不一致 | coordinator.md 说可以写 asset.manifest，但 AgentProfile.owned_outputs 不含此项 | 以 AgentProfile 为事实源，更新 .md |
| human_reviewer.md 缺失 | `load_role_prompt("human_reviewer")` 返回 "" | 创建 human_reviewer.md |
| recipe 约束过于宽松 | html_worker 生成了 Manim 代码 | 在 extra_rules 加"只输出 HTML"约束 |
| recipe 约束过于严格 | manim_worker 不敢用 VGroup 因为 extra_rules 说"避免炫技" | 调整措辞为"优先选择稳定 API 而非最新特性" |
| 共享约束被覆盖 | recipe 说"输出 Markdown"但 core.md 说"要求 JSON 的角色只输出 JSON" | 删除 recipe 中的冲突指令 |
| 阶段越权 | explorer 被允许在 DISPATCH 阶段工作 | 检查 AgentProfile.allowed_stages |

## Expected output

```json
{
  "role_id": "coordinator",
  "consistency_status": "consistent|has_issues",
  "mapping": {
    "md_file": "resources/prompts/roles/coordinator.md",
    "recipe_function": "coordinator_recipe()",
    "agent_profile": "workflow.py:build_agent_profiles -> coordinator"
  },
  "checks": [
    {
      "id": "write_permission_alignment",
      "result": "pass",
      "detail": "md: [narration.script, storyboard.master, session.handoff] == AgentProfile.owned_outputs"
    },
    {
      "id": "read_requirement_alignment",
      "result": "pass",
      "detail": "md: [research.summary, glossary, formula.catalog, style.guide, narration.script] ⊆ AgentProfile.required_inputs"
    },
    {
      "id": "forbidden_alignment",
      "result": "warning",
      "detail": "md 的'不得做'未提及'不得跳过 planner 直接写 segments'，但 workflow 隐含此约束"
    }
  ],
  "issues": [
    {
      "type": "missing_md_file",
      "role": "human_reviewer",
      "severity": "medium",
      "suggestion": "创建 resources/prompts/roles/human_reviewer.md"
    }
  ],
  "prompt_token_estimate": {"system": 1200, "quality": 300},
  "recommendations": [
    "coordinator 的 output_contract 建议增加 timing_manifest 引用",
    "reviewer 的 extra_rules 已覆盖 anti-bad-script 的全部检查点，无需重复"
  ]
}
```

---
name: tool-routing-and-permission-control
description: "审计 ManiMind 的三层路由/权限体系：LLM 路由（llm_client.py 的 primary/review/worker 三路）、能力分发（capability_registry.py 的 4 个能力定义）、任务权限（task_board.py 的 owner/blocker/verification）。确保无越权路径、无死锁、无遗漏角色。触发短语：工具路由审计、权限控制检查、routing audit、permission check、模型路由验证。"
roles: ["lead"]
stages: ["prestart", "review", "package"]
---

# 工具路由与权限控制

## Overview

ManiMind 有三层独立的路由/权限控制：

| 层级 | 位置 | 决策逻辑 | 粒度 |
|------|------|----------|------|
| LLM 路由 | `llm_client.py:39-51` `route_for_role()` | 角色 ID → primary/review/worker | 角色级 |
| 能力分发 | `capability_registry.py:109-120` `capabilities_for_role()` | 角色 ID + 阶段 → 可用能力列表 | 角色+阶段级 |
| 任务权限 | `task_board.py:48-146` `update_execution_task_status()` | actor_role vs owner_role + lead 特权 | 任务级 |

三层之间没有形式化的关联——例如，能力分发不检查"该角色在当前阶段是否有 LLM 路由"。

当前事实：
- LLM 路由：9 个角色 → 3 条路由（primary/review/worker）
- 能力分发：4 个能力 → 每个能力有独立的 roles 和 stages 定义
- 任务权限：每个 ExecutionTask 有 owner_role，只有 owner 或 lead 可推进

## When to use

- 新增 LLM provider 或修改 `route_for_role()` 后
- `CAPABILITY_DEFINITIONS` 列表变更后
- 新增或修改角色 `AgentProfile.allowed_stages` 后
- 发现某角色读取了不应读的上下文
- 发现某角色修改了不应改的任务状态
- 环境变量 `MANIMIND_WORKER_MODEL` 等 LLM 配置变更后
- 发现 `_can_consume` 过滤未生效

## Required inputs

1. `src/manimind/llm_client.py`：`route_for_role()` 和 `load_llm_runtime_config()`
2. `src/manimind/capability_registry.py`：`CAPABILITY_DEFINITIONS` 和 `capabilities_for_role()`
3. `src/manimind/task_board.py`：`update_execution_task_status()` 和 `list_available_tasks()`
4. `src/manimind/context_assembly.py`：`_can_consume()` 和 `build_context_packet()`
5. `src/manimind/workflow.py`：`build_agent_profiles()` 返回的完整角色列表

## Step-by-step process

### Step 1: LLM 路由矩阵审计

从 `route_for_role()` 提取当前映射：

```text
primary:  lead, human_reviewer
review:   reviewer
worker:   explorer, planner, coordinator, html_worker, manim_worker, svg_worker
```

检查点：
- 所有 9 个角色都有路由映射（无 fallback 到 default）
- `reviewer` 使用专用 review 路由（不应与其他 worker 共享）
- `human_reviewer` 使用 primary 路由（因为是人工角色，不用 LLM）
- worker 路由的模型配置（`MANIMIND_WORKER_MODEL`）适合代码生成任务

从 `load_llm_runtime_config()` 验证三套路由的环境变量配置完整：
- primary: `MANIMIND_MODEL`、`MANIMIND_MODEL_BASE_URL`、`OPENAI_API_KEY`
- review: `MANIMIND_REVIEW_MODEL`（默认复用 primary）
- worker: `MANIMIND_WORKER_MODEL`、`MANIMIND_WORKER_MODEL_BASE_URL`、`MANIMIND_WORKER_API_KEY`

### Step 2: 能力分发矩阵审计

从 `CAPABILITY_DEFINITIONS` 提取 4 个能力的分发规则：

| 能力 | 适用角色 | 适用阶段 |
|------|----------|----------|
| pdf_ingest_skill | lead, explorer | ingest, summarize |
| html_animation_skill | explorer, planner, coordinator, html_worker | summarize, plan, dispatch |
| hyperframes_reference | explorer, planner, coordinator, html_worker, svg_worker | summarize, plan, dispatch |
| manim_skill | explorer, planner, coordinator, manim_worker | summarize, plan, dispatch |

检查点：
- 每个能力的路径在仓库中确实存在（`rel_path` 可 resolve）
- 角色不在其 `allowed_stages` 之外的阶段收到能力
  - 例：`html_worker` 的 `allowed_stages` 只有 `dispatch`，但 html_animation_skill 的 stages 包含 `summarize` 和 `plan`。这不会造成问题（能力分发只在允许的阶段生效），但能力注册表过于宽松
- `html_worker` 不应拿到 `pdf_ingest_skill`
- `manim_worker` 不应拿到 `hyperframes_reference`（或应在注册表中限定为 `explorer, planner, coordinator, html_worker, svg_worker`）

### Step 3: 任务权限审计

检查 `update_execution_task_status()` 的权限控制：

```python
# task_board.py:67
if actor_role not in {task.owner_role, "lead"}:
    return TaskMutationResult(success=False, reason="owner_mismatch")
```

检查点：
- `review.outputs` 的特殊保护：`actor_role` 必须是 `human_reviewer` 或 `lead`
- 没有角色可以通过 `owner_role` 字段篡改（`ExecutionTask.owner_role` 来自 `workflow.py` 的 `build_execution_tasks`，是硬编码的）
- `lead` 的 superuser 权限合理（lead 需要能在紧急情况下推进任何任务）

### Step 4: 上下文访问权限审计

从 `context_assembly.py:61-68` 的 `_can_consume()`：

```python
def _can_consume(record, role_id):
    if role_id == "lead": return True           # lead 全部可读
    if role_id == record.writer_role: return True  # 写者可读自己的
    if not record.consumer_roles: return True    # 空列表 = 公开
    return role_id in record.consumer_roles      # 显式白名单
```

检查点：
- 敏感上下文（如 `review.report`）的 `consumer_roles` 应有限制
  - 当前 `review.report.consumer_roles = ["lead"]` ✓
- 不应有 `consumer_roles=[]` 的敏感上下文（空列表 = 公开给所有角色）
- `review.return.memo` 的 consumer 包含所有 worker 和 coordinator ✓
- `session.handoff` 的 consumer 包含所有 worker ✓

### Step 5: 越权路径扫描

搜索潜在越权路径：
1. 是否有代码绕过 `_can_consume()` 直接读文件？
2. 是否有代码绕过 `task_board` 直接修改 `ExecutionTask.status`？
3. 前端是否可以通过 API 绕过审核门禁触发 finalize？

```bash
# 搜索直接状态修改
grep -rn "task.status\s*=" src/manimind/ --include="*.py" | grep -v task_board.py
# 搜索绕过 context_assembly 的直接文件读取
grep -rn "read_text\|open.*runtime/projects" src/manimind/ --include="*.py" | grep -v runtime_store.py | grep -v artifact_store.py
```

### Step 6: 死锁检测

检查任务 DAG 中是否有死锁：
- 任务 A `blocked_by` 任务 B，且任务 B `blocked_by` 任务 A（循环依赖）
- 任务 A 的 `required_outputs` 需要任务 B 完成，但任务 B 的 `blocked_by` 包含任务 A

## Forbidden behaviors

- 禁止在未理解三层路由关系时提出修改建议
- 禁止建议移除 `review.outputs` 的 `verification_required=True`
- 禁止建议让 `read_only` 角色获得写入权限
- 禁止建议让非 `human_reviewer` 角色完成 `review.outputs`
- 禁止建议在生产环境关闭 `stage_allowed` 门禁

## Verification checklist

| # | 检查项 | 方式 |
|---|--------|------|
| 1 | 所有 9 个角色都有 LLM 路由 | grep route_for_role |
| 2 | reviewer 使用 review 路由 | 字面检查 |
| 3 | human_reviewer 使用 primary 路由 | 字面检查 |
| 4 | 4 个能力的路径确实存在 | stat rel_path |
| 5 | 能力的 roles 字段都是有效角色 ID | 与 AgentProfile 列表对比 |
| 6 | HTML worker 不被分发 pdf_ingest_skill | 检查 capabilities_for_role |
| 7 | 非 owner 角色被 task_board 拒绝 | 单元测试覆盖 |
| 8 | review.outputs 只有 human_reviewer 可完成 | 单元测试覆盖 |
| 9 | _can_consume 不被绕过 | grep 搜索 |
| 10 | 无循环依赖 | DAG 拓扑排序 |
| 11 | review.report 只有 lead 可读 | consumer_roles 检查 |
| 12 | 前端 finalize 触发需要 review 状态前置检查 | 代码搜索 |

## Common failure modes

| 模式 | 症状 | 修复 |
|------|------|------|
| 新角色无路由 | 调用 LLM 时 fallback 到 primary，浪费昂贵模型 | 在 route_for_role 中显式添加 |
| 能力路径失效 | 能力注册表引用不存在的目录 | 更新 rel_path |
| consumer_roles 过于宽松 | review.report 被 worker 读取，造成循环 | 收紧 consumer_roles |
| lead 权限过大 | lead 可以完成 review.outputs，绕过人工审核 | 保持现状（lead 需要 emergency override）但增加警告日志 |
| 能力分发阶段不匹配 | pdf_ingest_skill 的 stages 包含 summarize，但 pdf/ 脚本只在 ingest 触发 | 收窄 stages |
| LLM 路由环境变量未配置 | worker 路由错误使用 primary 的 API key | 检查配置完整性 |

## Expected output

```json
{
  "routing_matrix": {
    "lead": {"route": "primary", "model_env": "MANIMIND_MODEL"},
    "explorer": {"route": "worker", "model_env": "MANIMIND_WORKER_MODEL"},
    "planner": {"route": "worker", "model_env": "MANIMIND_WORKER_MODEL"},
    "coordinator": {"route": "worker", "model_env": "MANIMIND_WORKER_MODEL"},
    "html_worker": {"route": "worker", "model_env": "MANIMIND_WORKER_MODEL"},
    "manim_worker": {"route": "worker", "model_env": "MANIMIND_WORKER_MODEL"},
    "svg_worker": {"route": "worker", "model_env": "MANIMIND_WORKER_MODEL"},
    "reviewer": {"route": "review", "model_env": "MANIMIND_REVIEW_MODEL"},
    "human_reviewer": {"route": "primary", "model_env": "MANIMIND_MODEL", "note": "人工角色，实际不调用 LLM"}
  },
  "capability_audit": [
    {
      "name": "pdf_ingest_skill",
      "path_exists": true,
      "roles_valid": true,
      "stages_overly_broad": false,
      "issues": []
    },
    {
      "name": "html_animation_skill",
      "path_exists": true,
      "roles_valid": true,
      "stages_overly_broad": false,
      "issues": []
    },
    {
      "name": "hyperframes_reference",
      "path_exists": true,
      "roles_valid": true,
      "stages_overly_broad": false,
      "issues": []
    },
    {
      "name": "manim_skill",
      "path_exists": true,
      "roles_valid": true,
      "stages_overly_broad": true,
      "issues": ["stages 包含 'summarize' 但 manim_worker 只能在 'dispatch' 阶段工作——能力注册表过于宽松但不会造成运行时问题"]
    }
  ],
  "permission_audit": {
    "review_gate_bypassable": false,
    "orphan_contexts": [],
    "dead_tasks": [],
    "owner_conflicts": [],
    "direct_status_mutations_outside_task_board": []
  },
  "warnings": [
    "manim_skill 的 stages 声明过于宽松（summarize/plan 阶段 manim_worker 不活跃），建议收窄为 dispatch"
  ]
}
```

---
name: project-architecture-review
description: "审计 ManiMind 项目架构合规性——检查 src/manimind/ 模块边界、上下文路径分离、审核关卡强制性、角色模式约束和第三方能力接入方式。对比 docs/architecture.canvas、docs/通用项目架构模板.md、docs/强前置条件约束.md 与代码实际实现的一致性。触发短语包括：架构审查、arch review、audit architecture、check compliance、P0 audit。"
required_inputs:
  - docs/architecture.canvas
  - docs/通用项目架构模板.md
  - docs/强前置条件约束.md
  - src/manimind/*.py（全量模块）
  - capability_registry.py
  - workflow.py
roles: ["lead", "reviewer"]
stages: ["prestart", "review", "package"]
---

# 项目架构审查

## Overview

系统性地审计 ManiMind 项目是否遵守 `docs/` 中定义的架构红线。当前仓库的架构信息分布在以下位置：

| 约束来源 | 文件 | 效力 |
|----------|------|------|
| 架构白板 | `docs/architecture.canvas` | 模块/子系统级授权图 |
| 架构模板（已实现） | `docs/通用项目架构模板.md` | 分层描述、角色架构、状态机、CLI |
| 强前置条件 | `docs/强前置条件约束.md` | 6 条项目级红线、架构/上下文/实现/交付约束 |
| AGENTS.md | 根目录 | 文档优先级、仓库边界、修改原则、产物约定 |

代码事实源：`src/manimind/` 共 17 个模块，`backend/api/` 共 7 个路由，`frontend/manimind-console/` 的 App Router。

## When to use

- 修改了 `src/manimind/` 下任何模块的边界（导入关系、新增模块、删除模块）
- 修改了角色定义（`workflow.py` 的 `build_agent_profiles`）
- 修改了上下文蓝图（`workflow.py` 的 `build_context_blueprint`）
- 修改了任务 DAG（`workflow.py` 的 `build_execution_tasks`）
- 新增或删除能力注册（`capability_registry.py` 的 `CAPABILITY_DEFINITIONS`）
- 发现运行时异常且怀疑根因是架构违规
- 发布前（阶段 milestone）
- 收到 "审核被绕过"、"上下文路径混写" 相关 bug

## Required inputs

1. **必需**：仓库根目录路径（从 `bootstrap.repo_root()` 或 `MANIMIND_PROJECT_ROOT` 获取）
2. **必需**：受影响的架构层范围（`core` / `api` / `frontend` / `resources` / `all`）
3. **可选**：git diff（如果限制在变更范围内，否则全量审计）

## Step-by-step process

### Step 1: 加载约束声明

读取以下文件并提取所有显式约束：

```bash
# 提取所有 "不允许" "不得" "禁止" "必须" 约束
grep -n -E "(不允许|不得|禁止|必须|强制|红线)" docs/强前置条件约束.md
grep -n -E "(不允许|不得|禁止|必须)" docs/通用项目架构模板.md
```

输出为 `constraint_index`：约束 ID、来源文件、原文、适用范围。

### Step 2: P0 检查（阻塞级）

按以下顺序逐项验证，任一项失败即 `audit_result = blocked`：

1. **P0-1: 无 vendor 复制**：`src/manimind/` 中不应有从第三方仓库复制内部实现的代码
   - 检查：grep `import` 语句中是否有 `vendor/` 或外部克隆路径
   - 检查：是否存在与 `ClaudeCode/`（已被移除的参考归档）的功能重写

2. **P0-2: 长期上下文路径隔离**：所有对 `runtime/projects/` 的写入必须通过 `runtime_store.py` 或 `artifact_store.py`
   - 检查：grep `runtime/projects` 在所有 `.py` 中被用作写入路径的位置
   - 允许：`runtime_store.py`（`_write_json`、`_append_jsonl`）、`artifact_store.py`（`write_output_key`）
   - 禁止：其他模块直接 `open("runtime/projects/...")` 写文件

3. **P0-3: 短期上下文路径隔离**：所有对 `runtime/sessions/` 的写入必须通过 `runtime_store.py`
   - 同上检查逻辑

4. **P0-4: 长短期不混写**：不应出现将 `long_term` 和 `short_term` 写入同一文件的代码
   - 检查：`workflow.py` 的 `build_context_blueprint` 中每个 `ContextRecord.scope` 与其建议物理路径一致

5. **P0-5: 审核关卡不可绕过**：`review.outputs` 是 `verification_required=True`，没有任何路径能跳过
   - 检查：`executor.py` 的 `_complete_task` 对 `review.outputs` 的调用链
   - 检查：`post_produce.py` 的 `finalize_delivery` 是否检查 `review.outputs` 已完成
   - 检查：`main.py` 的 `finalize` 命令是否先验证 review 状态

6. **P0-6: 阶段枚举一致性**：`PipelineStage` 枚举（`models.py`）与 `DEFAULT_STAGES`（`workflow.py`）一致

7. **P0-7: 架构文档同步**：`docs/architecture.canvas` 与 `docs/通用项目架构模板.md` 的模块列表和分层描述一致

### Step 3: P1 检查（高影响）

8. **P1-1: 上下文治理完整性**：每个 `ContextRecord` 都有 `writer_role`、`consumer_roles`、`lifecycle`、`invalidation_rule`
   - 检查对象：`workflow.py` 的 `build_context_blueprint` 返回的 11 条记录

9. **P1-2: 角色模式约束**：
   - `read_only` 角色（explorer, planner）的 `owned_outputs` 为空
   - `verify_only` 角色（reviewer, human_reviewer）不能声明 `owned_outputs`
   - `structured_write` 角色的 `owned_outputs` 非空且与 `output_contract` 一致

10. **P1-3: 状态生命周期覆盖**：
    - `ExecutionTask` 的 `blocked_reason`、`blocked_at`、`last_progress`、`last_progress_at` 字段有明确的写入者和更新时机

### Step 4: P2 检查（中影响）

11. **P2-1: 第三方资产修改可追溯**：
    - 检查 `resources/skills/html-animation/` 和 `resources/references/hyperframes/` 是否有本地修改
    - 若有，检查对应文档是否写明了来源与裁剪原因

12. **P2-2: 能力路径一致**：
    - `capability_registry.py` 中 4 个能力的 `rel_path` 在仓库中确实存在
    - 检查：`pdf/`、`resources/skills/html-animation/`、`resources/references/hyperframes/`、`resources/skills/manim/`

### Step 5: 生成报告

汇总所有检查结果，按 P0/P1/P2 分级输出。

## Forbidden behaviors

- 禁止修改任何源文件、配置文件或文档
- 禁止提出超出 `docs/` 中已定义约束的建议（不允许自行发明新约束）
- 禁止在没有 grep/read_file 证据的情况下宣称"合规"
- 禁止跳过 P0 中的任一项
- 禁止把口头约定当作约束来审计
- 禁止运行依赖安装或编译

## Verification checklist

| # | 检查项 | 级别 | 验证方式 |
|---|--------|------|----------|
| 1 | src/manimind/ 无 vendor 复制 | P0 | grep import |
| 2 | 长期上下文路径隔离 | P0 | grep runtime/projects 写入 |
| 3 | 短期上下文路径隔离 | P0 | grep runtime/sessions 写入 |
| 4 | 长短期不混写 | P0 | 检查 ContextRecord.scope |
| 5 | 审核关卡不可绕过 | P0 | 追踪 review.outputs 调用链 |
| 6 | 阶段枚举一致 | P0 | 对比 models.py vs workflow.py |
| 7 | 架构文档同步 | P0 | 对比 canvas vs 模板 |
| 8 | 上下文治理字段完整 | P1 | 审计 build_context_blueprint |
| 9 | 角色模式约束 | P1 | 审计 build_agent_profiles |
| 10 | 状态生命周期覆盖 | P1 | 审计 ExecutionTask 字段 |
| 11 | 第三方资产可追溯 | P2 | git diff resources/ |
| 12 | 能力路径一致 | P2 | stat capability paths |

## Common failure modes

| 模式 | 症状 | 修复方向 |
|------|------|----------|
| 审核被绕过 | `finalize` 在 review 前被调用 | 在 `post_produce.py` 加 review 状态前置检查 |
| 上下文路径混写 | session 数据写入 projects/ | 统一通过 `runtime_store.py`，禁止直接文件操作 |
| 能力路径失效 | `pdf/` 或 `resources/skills/manim/` 被移动 | 更新 `capability_registry.py` 和 `bootstrap.py` |
| 角色越权 | html_worker 修改了 manim 产物 | 检查 `owned_outputs` 和 `output_contract` |
| 死任务 | DAG 中 `blocked_by` 指向不存在的 task_id | 检查 `build_execution_tasks` 的 ID 一致性 |
| canvas 过时 | 新增模块后 canvas 未更新 | 对比 canvas mtime 与 src/ 最新 commit 时间 |

## Expected output

```json
{
  "audit_result": "pass|blocked|needs_fix",
  "project_root": "/mnt/f/ManiMind",
  "audit_time": "2026-05-12T18:00:00Z",
  "checks": {
    "p0": [
      {
        "check": "P0-1: no_vendor_copy",
        "status": "pass|fail",
        "evidence": "grep 结果摘要或文件引用",
        "location": "受影响的文件路径"
      }
    ],
    "p1": [],
    "p2": []
  },
  "failures": [
    {
      "code": "P0-5",
      "severity": "blocker",
      "description": "post_produce.py 未检查 review.outputs 状态即执行 finalize",
      "fix_suggestion": "在 finalize_delivery 入口增加 review 任务状态检查",
      "affected_files": ["src/manimind/post_produce.py"]
    }
  ],
  "architecture_canvas_synced": true,
  "constraints_source_mtime": {
    "docs/architecture.canvas": "2026-05-10T...",
    "docs/通用项目架构模板.md": "2026-05-11T..."
  },
  "recommendations": []
}
```

---
name: repository-docs-contract
description: "验证 ManiMind 仓库文档是否符合内部约定。检查 docs/ 目录与 src/manimind/ 实际代码的一致性、文档间交叉引用的完整性、以及架构文档的同步性。触发短语：文档契约、docs contract、文档一致性、documentation audit、check docs。"
roles: ["lead"]
stages: ["prestart", "review", "package"]
---

# 仓库文档契约

## Overview

ManiMind 的文档分布在多个位置，之间存在隐式契约：

| 文档 | 定位 | 依赖 |
|------|------|------|
| `AGENTS.md` | 文档优先级 + 仓库边界 + 产物约定 | 无 |
| `README.md` | 项目总览 + 目录结构 + CLI 参考 | docs/* |
| `docs/architecture.canvas` | 模块/子系统级架构白板 | src/manimind/ |
| `docs/通用项目架构模板.md` | 已实现架构的分层描述 | canvas + src/ |
| `docs/强前置条件约束.md` | 6 条项目级红线 | 所有代码 |
| `docs/代码组织.md` | 模块索引 | src/ |
| `docs/角色职责与能力分发说明.md` | 角色能力分发矩阵 | workflow.py + capability_registry.py |
| `docs/上下文与状态设计.md` | 上下文分层与治理 | context_assembly.py + runtime_store.py |
| `docs/阶段1计划.md` | 阶段 1 设计基线 | 所有代码 |

关键约束（来自 `AGENTS.md`）：
- 任何涉及模块边界、角色分布、状态路径等的结构变更，必须同步更新 canvas 和模板
- `resources/` 下第三方资产修改必须在文档中写明来源与裁剪原因

## When to use

- 修改了 `src/manimind/` 模块边界后
- 修改了角色分布或状态存储路径后
- 发布/合并前（CI 门禁）
- CI/CD 流水线中作为文档一致性检查
- 新人入职时验证文档是否可读且准确

## Required inputs

1. **仓库根目录**：`bootstrap.repo_root()`
2. **文档范围**：`docs/` | `resources/` | `AGENTS.md` | `README.md` | `all`
3. **可选的 git diff**：只检查变更影响的文档

## Step-by-step process

### Step 1: 文档存在性检查

验证 `README.md` 中声明的文档入口文件都存在：

```text
README.md 列出的文档入口：
├── docs/README.md                   ✓ 存在
├── docs/角色职责与能力分发说明.md    ✓ 存在
├── docs/前端控制台骨架方案.md        ✓ 存在
├── docs/阶段1计划.md                ✓ 存在
├── docs/通用项目架构模板.md          ✓ 存在
├── docs/上下文与状态设计.md          ✓ 存在
├── docs/第三方整合.md               ✓ 存在
└── docs/ClaudeCode抽取清单.md        ✓ 存在
```

验证 `AGENTS.md` 中列出的文档优先级文件存在：

```text
AGENTS.md 优先级列表：
1. 当前文件                           ✓ AGENTS.md
2. docs/强前置条件约束.md             ✓ 存在
3. docs/通用项目架构模板.md           ✓ 存在
4. docs/代码组织.md                   ✓ 存在
5. 根目录 README.md                   ✓ 存在
```

### Step 2: 模块列表一致性

`docs/通用项目架构模板.md` 的"编排核心层"列出了 16 个模块。对比 `src/manimind/` 实际文件列表：

```text
模板列出（16 个）：           实际存在（17 个）：
models.py                  ✓  models.py
workflow.py                ✓  workflow.py
ingest.py                  ✓  ingest.py
prompt_system.py           ✓  prompt_system.py
llm_client.py              ✓  llm_client.py
worker_adapters.py         ✓  worker_adapters.py
executor.py                ✓  executor.py
review_workflow.py         ✓  review_workflow.py
post_produce.py            ✓  post_produce.py
tts.py                     ✓  tts.py
context_assembly.py        ✓  context_assembly.py
task_board.py              ✓  task_board.py
runtime.py                 ✓  runtime.py
runtime_store.py           ✓  runtime_store.py
bootstrap.py               ✓  bootstrap.py
main.py                    ✓  main.py
                           +  capability_registry.py  ← 未在模板列出！
                           +  artifact_store.py       ← 未在模板列出！
```

差距：`capability_registry.py` 和 `artifact_store.py` 实际存在但模板未列出。

### Step 3: 角色列表一致性

`docs/通用项目架构模板.md` 的角色列表与 `workflow.py` 的 `build_agent_profiles()` 对比：

```text
模板列出：                  workflow.py：
lead                       ✓
explorer                   ✓
planner                    ✓
coordinator                ✓
html_worker                ✓
manim_worker               ✓
svg_worker                 ✓
reviewer                   ✓
human_reviewer             ✓
```

此处一致 ✓

### Step 4: 能力分发矩阵一致性

`docs/角色职责与能力分发说明.md` 的"分发矩阵"与 `capability_registry.py` 的 `CAPABILITY_DEFINITIONS` 对比：

| 能力 | 文档声明的 roles | registry 的 roles | 一致？ |
|------|------------------|-------------------|--------|
| pdf_ingest_skill | lead, explorer (via ingest) | lead, explorer | ✓ |
| html_animation_skill | explorer, planner, coordinator, html_worker | explorer, planner, coordinator, html_worker | ✓ |
| hyperframes_reference | explorer, planner, coordinator, html_worker, svg_worker | explorer, planner, coordinator, html_worker, svg_worker | ✓ |
| manim_skill | explorer, planner, coordinator, manim_worker | explorer, planner, coordinator, manim_worker | ✓ |

此处一致 ✓

### Step 5: 上下文蓝图一致性

`docs/上下文与状态设计.md` 的"默认上下文蓝图"与 `workflow.py` 的 `build_context_blueprint()` 对比：

```text
文档列出（9 项）：           workflow.py（12 项）：
research.summary            ✓
glossary                    ✓
formula.catalog             ✓
style.guide                 ✓
narration.script            ✓
storyboard.master           ✓
asset.manifest              ✓
review.report               ✓
session.handoff             ✓
                            + review.evidence         ← 未在文档列出
                            + review.return.memo       ← 未在文档列出
                            + review.return.prompt_patch ← 未在文档列出
```

差距：3 个 context record 在代码中存在但文档未列出。

### Step 6: 强前置条件红线合规

`docs/强前置条件约束.md` 定义了 6 条项目级红线：

1. 不在当前仓库重复实现 resources/ 已提供的底层能力 → 检查 src/ 是否有 vendor 复制
2. 不把长期上下文和短期上下文写进同一路径 → 检查 context_assembly.py
3. 不允许跳过审核 Agent 直接合成最终视频 → 检查 executor.py + post_produce.py
4. 不允许用隐式全局状态驱动多 Agent 协作 → 检查状态管理方式
5. 不允许把数学事实只保存在对话里而不落成结构化摘要 → 检查 ingest -> summarize 链路
6. 结构变更必须同步更新 canvas 和模板 → 检查最近变更

### Step 7: 交叉引用完整性

检查所有 .md 文件中的相对链接是否有效：

```bash
grep -rn '\[.*\](\./.*\.md)' docs/ --include="*.md"
# 验证每个链接的目标文件存在
```

检查 `.md` 文件中引用的代码路径：
```bash
grep -rn '`src/manimind/.*\.py`' docs/ --include="*.md"
# 验证每个引用的 .py 文件存在
```

## Forbidden behaviors

- 禁止修改文档内容（只做检查和报告）
- 禁止基于猜测创建缺失的文档
- 禁止在不理解关联关系时报告"文档过时"
- 禁止在 CI 中就措辞差异报错（只检查结构化事实，不检查措辞）

## Verification checklist

| # | 检查项 | 方式 |
|---|--------|------|
| 1 | README.md 文档入口全部存在 | stat 每个路径 |
| 2 | AGENTS.md 优先级文件全部存在 | stat 每个路径 |
| 3 | 模板模块列表 == src/manimind/ 实际文件（±1） | ls + diff |
| 4 | 模板角色列表 == workflow.py 角色列表 | diff |
| 5 | 能力分发矩阵文档 == capability_registry | 逐行对比 |
| 6 | 上下文蓝图文档 == build_context_blueprint（±3） | diff |
| 7 | 6 条红线无一条被违反 | 逐个验证 |
| 8 | 所有 .md 文件的相对链接有效 | grep + stat |
| 9 | canvas mtime >= 最近一次修改 src/ 的 commit 时间 | git log + stat |
| 10 | 无 .md 引用不存在的文件路径 | grep + stat |

## Common failure modes

| 模式 | 症状 | 修复 |
|------|------|------|
| 模块遗漏 | capability_registry.py 实际存在但模板未列出 | 在模板的编排核心层新增该模块 |
| 上下文记录遗漏 | review.evidence 在代码中存在但文档未列出 | 在上下文与状态设计.md 补充 |
| canvas 过时 | canvas 最后修改时间早于 src/ 最新提交 | 更新 canvas |
| 链接断裂 | .md 文件引用已被删除或重命名的文件 | 修复链接或删除引用 |
| 能力说明过时 | 文档说 pdf/ 是"正式 ingest 增强能力"但代码未接入 | 同步文档状态 |
| 模板与 canvas 不同步 | canvas 的模块连接图与模板分层描述不一致 | 双向同步 |

## Expected output

```json
{
  "contract_status": "valid|stale|broken",
  "checked_at": "2026-05-12T18:00:00Z",
  "docs_checked": 8,
  "modules_in_template": 16,
  "modules_actual": 17,
  "modules_missing_from_template": [
    "capability_registry.py",
    "artifact_store.py"
  ],
  "contexts_in_doc": 9,
  "contexts_actual": 12,
  "contexts_missing_from_doc": [
    "review.evidence",
    "review.return.memo",
    "review.return.prompt_patch"
  ],
  "roles_consistency": "consistent",
  "capabilities_consistency": "consistent",
  "redline_violations": [],
  "broken_links": [],
  "canvas_mtime": "2026-05-10T21:06:00Z",
  "latest_src_change": "2026-05-11T21:55:00Z",
  "canvas_up_to_date": false,
  "recommendations": [
    "在 docs/通用项目架构模板.md 的编排核心层新增 capability_registry.py 和 artifact_store.py",
    "在 docs/上下文与状态设计.md 补充 review.evidence、review.return.memo、review.return.prompt_patch 三项",
    "更新 docs/architecture.canvas 使其与最新的编排核心层一致"
  ]
}
```

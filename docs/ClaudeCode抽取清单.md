# ClaudeCode 抽取清单

本文记录从 `ClaudeCode/` 参考源码中抽取到 ManiMind 编排层的可复用设计，便于后续移除 `ClaudeCode/` 目录后持续维护。

## 一、角色编排（已落地）

来源（参考）：

- `src/tools/AgentTool/built-in/exploreAgent.ts`
- `src/tools/AgentTool/built-in/planAgent.ts`
- `src/tools/AgentTool/built-in/verificationAgent.ts`

落地位置：

- [models.py](../src/manimind/models.py)
- [workflow.py](../src/manimind/workflow.py)

抽取结果：

- `AgentMode` 三态：`read_only` / `structured_write` / `verify_only`
- 角色画像 `AgentProfile`：职责、允许阶段、必需输入、产出归属、输出契约
- `reviewer` 作为强制验证角色，禁止绕过审核直达后处理

## 二、上下文装配（已落地）

来源（参考）：

- `src/context.ts`
- `src/constants/systemPromptSections.ts`
- `src/utils/systemPrompt.ts`

落地位置：

- [context_assembly.py](../src/manimind/context_assembly.py)
- [models.py](../src/manimind/models.py)

抽取结果：

- `ContextRecord` 补充上下文治理字段：
  - `writer_role`
  - `consumer_roles`
  - `lifecycle`
  - `invalidation_rule`
- `build_context_packet(...)`：按角色与阶段装配上下文包
- `PromptSection` / `PromptSectionCache`：提示词分段与缓存机制
- `build_default_prompt_sections(...)`：标准角色、上下文、输出、约束分段

## 三、任务清单与验证关卡（已落地）

来源（参考）：

- `src/tools/TaskUpdateTool/TaskUpdateTool.ts`
- `src/tools/TodoWriteTool/TodoWriteTool.ts`
- `src/utils/tasks.ts`

落地位置：

- [models.py](../src/manimind/models.py)
- [workflow.py](../src/manimind/workflow.py)
- [task_board.py](../src/manimind/task_board.py)

抽取结果：

- `ExecutionTask`：任务 ID、owner、阻塞依赖、required outputs、验证标记
- `list_available_tasks(...)`：仅返回 blocker 已完成的 pending 任务
- `update_execution_task_status(...)`：状态推进时校验 owner 与 blocker
- 验证 nudge：非审核任务全部完成但审核未完成时返回提醒

## 四、运行时路径与可选参考依赖（已落地）

来源（参考）：

- `src/memdir/paths.ts`（路径归一化/稳定命名思路）

落地位置：

- [bootstrap.py](../src/manimind/bootstrap.py)

抽取结果：

- `sanitize_identifier(...)`：稳定化项目标识
- `build_runtime_layout(...)`：统一项目上下文、会话上下文、输出与报告路径
- `check_external_paths(...)`：仅检查运行时硬依赖（`resources/` + `docs`）
- `check_reference_archives(...)`：单独检查 `ClaudeCode` 压缩包（可选）

## 五、CLI 能力（已落地）

落地位置：

- [main.py](../src/manimind/main.py)

抽取结果：

- `context-pack`：从清单生成角色上下文包
- `context-pack --render-prompt-sections`：输出提示词分段
- `task-update`：按状态机推进任务并返回最新执行任务状态
- `--session-id`：支持把同一会话的上下文包与任务更新串联落盘

## 六、运行时落盘（已落地）

落地位置：

- [runtime_store.py](../src/manimind/runtime_store.py)

抽取结果：

- 项目级快照：`state.json`、`context-records.json`、`execution-tasks.json`、`project-plan.json`
- 会话级快照：`context-packets/*.json`、`task-updates/*.json`
- 审计日志：项目级与会话级 `events.jsonl`
- 任务状态回填：`load_execution_task_snapshot(...)` 支持跨命令续跑

## 七、测试覆盖（已落地）

- [test_bootstrap.py](../tests/test_bootstrap.py)
- [test_workflow.py](../tests/test_workflow.py)
- [test_context_assembly.py](../tests/test_context_assembly.py)
- [test_task_board.py](../tests/test_task_board.py)

说明：

- 当前环境无法直接执行 Python 解释器（沙箱拒绝访问），测试仅完成静态核对，待你授权后可补跑 `pytest`。

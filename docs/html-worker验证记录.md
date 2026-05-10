# html_worker 验证记录（待审阅）

## 1. 目标

基于仓库内已经并入的两类现有能力，先完成 `html_worker` 的编排层验证，并形成可复跑、可审阅的记录：

- HTML skill 与模板资产：`resources/skills/html-animation/`
- HyperFrames 参考、规则与精选组件：`resources/references/hyperframes/`

本次验证目标不是接入真实 HTML 渲染执行器，而是确认当前 `src/manimind/` 编排层已经具备以下最小能力：

1. 能为 HTML 片段正确派发 `html_worker`
2. 能给 `html_worker` 装配正确上下文与写入边界
3. 能把验证链路落盘到 `runtime/projects/` 与 `runtime/sessions/`
4. 能在 reviewer 放行前挡住 `post_produce.outputs`

## 2. 验证边界

### 已覆盖

- 第三方 HTML / HyperFrames 资源存在性
- `html_worker` 的任务派发、角色契约、上下文装配
- 最小 CLI 链路：`plan -> context-pack -> task-update`
- reviewer 前置关卡是否生效

### 未覆盖

- 真实 HTML 页面生成
- 模板自动选型与页面重构质量
- HyperFrames `lint / validate / inspect / render`
- `html_worker` 产物内容本身的 schema 与审阅规则

结论上，这次只能证明“编排 contract 已可验证”，不能证明“HTML 渲染生产链已经可用”。

## 3. 使用的验证输入

新增最小验证清单：

- [configs/html-worker-validation.example.json](../configs/html-worker-validation.example.json)

该清单只包含一个 `html` 片段，目的是把验证范围收敛到 `html_worker` 本身，避免 `hybrid` 片段把 Manim / SVG 依赖一起带进来。

## 4. 发现并修复的问题

验证过程中发现一个真实契约冲突：

- `html_worker` 与 `svg_worker` 的 `required_inputs` 都声明依赖 `formula.catalog`
- 但上下文蓝图里 `formula.catalog.consumer_roles` 原先没有 `html_worker` / `svg_worker`
- 结果是 `context-pack` 实际不会把这条长期上下文下发给 `html_worker`

这会导致“任务契约要求读取，但上下文装配层不给读”的不一致。

已在 [workflow.py](../src/manimind/workflow.py) 修正：将 `formula.catalog` 的消费者扩展为：

- `coordinator`
- `html_worker`
- `manim_worker`
- `svg_worker`
- `reviewer`

这是本次验证中唯一必须先修再谈通过的编排缺陷。

## 5. 自动化验证

### 5.1 新增测试

新增测试文件：

- [test_html_worker_validation.py](../tests/test_html_worker_validation.py)

覆盖点：

1. 仓库包含 HTML skill / HyperFrames 关键参考路径
2. `html_worker` 的 `owned_outputs` 只指向 HTML 长期产物
3. `render.<segment>.html` 同时要求长期与短期输出
4. `html_worker` 的 `context-pack` 包含预期输入与写入目标

### 5.2 全量测试结果

执行：

```powershell
& 'C:\Users\84025\AppData\Local\Programs\Python\Python312\python.exe' -m pytest -q
```

结果：

- `24 passed`

说明本次修正没有破坏现有编排测试基线。

## 6. CLI 运行时验证

### 6.1 计划快照

执行：

```powershell
$env:PYTHONPATH='src'
& 'C:\Users\84025\AppData\Local\Programs\Python\Python312\python.exe' `
  -m manimind.main plan configs\html-worker-validation.example.json `
  --session-id html-worker-validation
```

关键确认：

- 仅生成一个 `html` worker task
- `html_worker` 的长期写入目标为 `html-worker-validation.html.seg-html-01.approved`
- `review.outputs` 被 `render.seg-html-01.html` 阻塞

项目级证据文件：

- [state.json](../runtime/projects/html-worker-validation/state.json)
- [context-records.json](../runtime/projects/html-worker-validation/context-records.json)
- [execution-tasks.json](../runtime/projects/html-worker-validation/execution-tasks.json)
- [project-plan.json](../runtime/projects/html-worker-validation/project-plan.json)

### 6.2 html_worker 上下文包

执行：

```powershell
$env:PYTHONPATH='src'
& 'C:\Users\84025\AppData\Local\Programs\Python\Python312\python.exe' `
  -m manimind.main context-pack configs\html-worker-validation.example.json `
  html_worker dispatch `
  --session-id html-worker-validation `
  --render-prompt-sections
```

关键确认：

1. `stage_allowed = true`
2. `mode = structured_write`
3. `write_targets = ["html-worker-validation.html.seg-html-01.approved"]`
4. `context_specs` 包含：
   - `research.summary`
   - `glossary`
   - `formula.catalog`
   - `style.guide`
   - `narration.script`
   - `storyboard.master`
   - `session.handoff`
5. 不包含 `review.report`

会话级证据文件：

- [context-pack-latest.json](../runtime/sessions/html-worker-validation/context-pack-latest.json)
- [20260510T020655Z-html_worker-dispatch.json](../runtime/sessions/html-worker-validation/context-packets/20260510T020655Z-html_worker-dispatch.json)

### 6.3 最小任务推进链路

执行顺序：

1. `ingest.sources -> completed`
2. `summarize.research -> completed`
3. `plan.storyboard -> completed`
4. `render.seg-html-01.html -> in_progress`
5. `render.seg-html-01.html -> completed`
6. `post_produce.outputs -> in_progress`（预期失败）

关键结果：

- `render.seg-html-01.html` 在 `plan.storyboard` 完成后成功解锁
- `render.seg-html-01.html -> completed` 时 `verification_nudge_needed = true`
- `post_produce.outputs` 在 reviewer 未完成时被拒绝，原因为 `task_blocked`
- 项目当前阶段推进到 `review`

对应证据：

- [state.json](../runtime/projects/html-worker-validation/state.json)
- [events.jsonl](../runtime/projects/html-worker-validation/events.jsonl)
- [task-update-latest.json](../runtime/sessions/html-worker-validation/task-update-latest.json)

## 7. 当前结论

`html_worker` 的编排层验证可以认为通过，但通过的含义需要严格限定为：

1. HTML 片段会被正确派发给 `html_worker`
2. `html_worker` 当前已能拿到符合契约的长期/短期上下文
3. 任务推进链路可追溯，并能落盘到项目级与会话级 runtime
4. reviewer 关卡没有被绕过

换句话说，当前仓库已经具备“接真实 HTML 执行器前的编排底座”，但还没有具备“可直接产出可交付 HTML 成片”的能力。

## 8. 剩余风险

### 风险 1：第三方能力仍是“文档引用”，尚未成为结构化执行输入

当前 `html_worker` 已知要基于：

- `resources/skills/html-animation/`
- `resources/references/hyperframes/`

但 `context-pack` 还没有显式下发这些资源的结构化入口路径、模板选择策略或规则索引。现在更多依赖仓库约定和人工查找。

### 风险 2：HTML 产物还没有正式 schema

当前只约定了输出 key：

- 长期：`<project_id>.html.<segment_id>.approved`
- 短期：`<project_id>.session.html.<segment_id>`

但没有定义：

- 产物文件名规范
- HTML 源文件、截图、lint 结果、审阅摘要的组织方式
- 失败时短期上下文该记录哪些字段

### 风险 3：还没有把 HyperFrames 质量门接进 reviewer 前流程

当前 reviewer 关卡只验证“任务状态与结构化产物依赖”，没有把 HyperFrames 的：

- `lint`
- `validate`
- `inspect`

变成 `html_worker` 或 reviewer 的强制输入。

## 9. 建议的下一步

建议按下面顺序推进，不要直接跳去做复杂 HTML 成片：

1. 在 `context-pack` 中为 `html_worker` 显式补充第三方资源引用入口
2. 定义 `html_worker` 的长期/短期产物 schema
3. 再把 `html-animation` 模板选型与 HyperFrames 规则校验接到真实执行链

## 10. 待审阅问题

本审阅稿建议重点确认三件事：

1. `formula.catalog` 是否应继续作为 `html_worker` 的强制输入
2. `html_worker` 是否需要在上下文包里显式拿到模板与 HyperFrames 规则路径
3. reviewer 前是否要把 HyperFrames 质量检查升级为硬门禁

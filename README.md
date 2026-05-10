# ManiMind

ManiMind 是一个面向数学科普动画生产的多 Agent 编排项目。输入论文和笔记，输出可审核的讲解脚本、分镜、Manim 数学动画、HTML 科普片段，以及后续配音、字幕、剪辑拼接所需的结构化产物。

仓库定位是“编排层”，不重写外部渲染引擎内部实现。
`ClaudeCode/` 仅作为可选参考源码包，其可复用编排能力已抽取到 `src/manimind/`。

## 当前架构要点

1. 预启动阶段加载文档与配置，检测工具链，注册能力路径。
2. 主 Agent 解析论文与笔记，产出研究总结、公式目录与项目状态。
3. 协调 Agent 切分分镜并并发派发 HTML / Manim / SVG 子任务。
4. 子 Agent 分别回写长期上下文和短期协作上下文。
5. 审核 Agent 通过后，进入配音、字幕、剪辑拼接。

## 目录结构

```text
ManiMind/
├─ AGENTS.md
├─ README.md
├─ docs/
├─ frontend/
├─ configs/
├─ scripts/
├─ src/manimind/
├─ manim-worker-pov/
├─ tests/
├─ resources/
│  ├─ skills/html-animation/
│  ├─ skills/manim/
│  └─ references/hyperframes/
├─ runtime/
├─ outputs/
└─ logs/
```

## 初始化步骤

1. 初始化目录与占位文件：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init-workspace.ps1
```

2. 同步第三方精选资产（白名单）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync-thirdparty-assets.ps1
```

注意：

- 该脚本会先清空 `resources/skills/html-animation/` 与 `resources/references/hyperframes/` 后再复制白名单内容。
- 当前仓库已经带有这两份资源；若未确认上游源码路径存在，不要直接重跑。
- 需要刷新资源时，优先显式传入上游路径。

源仓库不在项目根目录时，可显式传路径：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync-thirdparty-assets.ps1 `
  -HtmlSkillSource "<AI-Animation-Skill-main 路径>" `
  -HyperframesSource "<hyperframes-main 路径>"
```

3. 检查依赖：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-prerequisites.ps1
```

## 关键约束

- 第三方资产统一放在 `resources/`，不再使用独立 `vendor/`。
- 长期上下文只写 `runtime/projects/<project_id>/`。
- 短期协作上下文只写 `runtime/sessions/<session_id>/`。
- 审核未通过不得进入后处理。

## 编排 CLI（新增）

- `plan <manifest.json>`：生成标准项目计划。
- `context-pack <manifest.json> <role_id> <stage>`：生成角色上下文包。
- `context-pack ... --render-prompt-sections`：额外输出提示词分段渲染结果。
- `task-update <manifest.json> <task_id> <status> <actor_role>`：按状态机推进任务。
- `agent-message <manifest.json> <event_type> <role_id> <stage> --payload '{...}'`：写入 `worker.progress / worker.blocker / worker.result / review.decision` 结构化消息。
- `run-to-review <manifest.json>`：执行 ingest/summarize/plan/dispatch，并推进到 `review`。
- `human-review <manifest.json> approve|return`：人工审核放行或打回。
- `finalize <manifest.json> --tts-provider powershell_sapi|command|noop`：审核通过后执行后处理并完成打包。
- `context-pack` 默认会阻断角色非法阶段请求；需要显式放行时使用 `--allow-disallowed-stage`。
- 三个命令支持 `--session-id`，并会把状态与事件日志落盘到 `runtime/projects/<project_id>/` 与 `runtime/sessions/<session_id>/`。

## Web API 骨架（新增）

- 新增 `backend/` FastAPI 骨架，直接复用编排内核：
  - `POST /api/projects/plan`
  - `GET /api/projects/{project_id}/runtime`
  - `POST /api/projects/tasks`
  - `POST /api/projects/tasks/update`
  - `POST /api/projects/context-pack`
  - `POST /api/projects/events/message`
  - `GET /api/projects/{project_id}/events`
  - `POST /api/projects/run-to-review`
  - `POST /api/projects/review/decision`
  - `GET /api/projects/{project_id}/review-return`
  - `POST /api/projects/finalize`
- 启动示例（安装 `api` 依赖后）：

```powershell
& 'C:\Users\84025\AppData\Local\Programs\Python\Python312\python.exe' -m pip install -e ".[api]"
& 'C:\Users\84025\AppData\Local\Programs\Python\Python312\python.exe' -m uvicorn backend.main:app --reload
```

## 前端控制台骨架（新增）

- 新增目录：`frontend/manimind-console/`
- 技术栈：`Next.js 16 + React 19 + Tailwind CSS 4`
- 当前作用：先验证控制台首页的信息结构、模块边界和后续 API 接线点
- 当前数据：静态 mock 数据，后续替换为 `backend/` 的项目、任务、上下文和事件接口

启动示例：

```powershell
cd F:\ManiMind\frontend\manimind-console
npm install
npm run dev
```

## 文档入口

- [docs/README.md](./docs/README.md)
- [docs/前端控制台骨架方案.md](./docs/前端控制台骨架方案.md)
- [docs/阶段1计划.md](./docs/阶段1计划.md)
- [docs/通用项目架构模板.md](./docs/通用项目架构模板.md)
- [docs/上下文与状态设计.md](./docs/上下文与状态设计.md)
- [docs/第三方整合.md](./docs/第三方整合.md)
- [docs/ClaudeCode抽取清单.md](./docs/ClaudeCode抽取清单.md)

## 独立 POV（新增）

- `manim-worker-pov/`：Manim Worker 最小验证闭环（固定 spec -> 代码生成 -> 渲染 -> 日志修复）。
- 当前定位是独立 POC，用于验证 worker 侧协议与渲染修复，不视为 `src/manimind/` 已接入的正式执行器。

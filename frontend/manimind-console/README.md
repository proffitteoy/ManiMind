# ManiMind Console Skeleton

`frontend/manimind-console/` 是 ManiMind 控制台首页骨架，用于把现有编排内核包装成可视化驾驶舱。

## 当前范围

- 参考 `F:\ManiMind\d51e9537af482750899e7485b285e9b0.png` 的信息结构与节奏。
- 参考 `F:\ManiMind\next-shadcn-dashboard-starter-main\` 的技术方向，但不直接复制其业务实现。
- 当前版本使用静态 mock 数据，优先验证页面壳、布局切分、组件职责和后续 API 接线点。

## 技术栈

- `Next.js 16`
- `React 19`
- `Tailwind CSS 4`
- `lucide-react`

## 目录

```text
frontend/manimind-console/
├─ src/app/                  App Router 入口与全局样式
├─ src/components/console/   控制台壳层、阶段流、任务看板、概览卡片
├─ src/components/ui/        轻量基础展示组件
├─ src/data/                 首页 mock 数据与类型
└─ src/lib/                  通用工具
```

## 启动

```powershell
cd F:\ManiMind\frontend\manimind-console
npm install
npm run dev
```

默认首页为 `/`，展示：

- 左侧导航与项目状态
- 阶段流
- 任务看板
- Runtime / Context Packet / 事件日志
- Agent 状态、产物预览、能力清单

## 后续接线原则

- 前端只通过 `backend/` 的 HTTP API 读取和更新状态。
- 不允许前端直接读写 `runtime/projects/*` 或 `runtime/sessions/*`。
- `src/data/console-demo.ts` 中的 mock 数据后续可逐步替换为：
  - `GET /api/projects/{project_id}/runtime`
  - `GET /api/projects/{project_id}/tasks`
  - `POST /api/projects/{project_id}/tasks/{task_id}/update`
  - `POST /api/projects/{project_id}/context-pack`

## 对齐审查与闭环

- 审查基线：`../../docs/前端骨架对齐审查.md`
- 闭环记录：`../../docs/前端骨架对齐闭环记录.md`

---
name: frontend-console-review
description: "审查 frontend/manimind-console/ 前端控制台的代码质量和 API 对齐度。当前前端技术栈为 Next.js 16 + React 19 + Tailwind CSS 4，通过 App Router 提供 /live 和 /mock 两套页面。检查前端页面是否与 backend/ 的 10 个 API 端点契约一致、数据流映射是否正确、错误状态覆盖是否完整。触发短语：前端审查、frontend review、console check、前端 API 对齐、UI audit。"
roles: ["lead"]
stages: ["prestart", "review", "package"]
---

# 前端控制台审查

## Overview

`frontend/manimind-console/` 是 ManiMind 的 Web 控制台骨架。当前页面结构：

```
src/app/
├── page.tsx                       → 重定向到 /live
├── live/
│   ├── page.tsx                   → 项目概览（project_id, stage, 上下文, 事件）
│   ├── tasks/
│   │   └── page.tsx               → 任务状态、依赖、审核门禁
│   ├── review/
│   │   ├── page.tsx               → 审核草案、证据、人工审核入口
│   │   └── review-actions.tsx     → run-to-review / approve / return / finalize
│   └── artifacts/
│       └── page.tsx               → 产物、字幕、音频、最终视频
├── mock/
│   └── page.tsx                   → 静态演示页
└── layout.tsx
```

`src/data/` 下有 API 响应映射层。
`src/components/console/` 下有业务卡片组件。
`src/components/ui/` 下有轻量展示组件。

## When to use

- 修改了 `backend/api/` 任何路由后（需检查前端是否兼容）
- 前端新增页面或组件后
- 发现前端展示的数据与 backend 返回不符时
- 发布前（确保控制台可用）
- 发现前端直接 import 了 `src/manimind/` 的模块（应为违规）

## Required inputs

1. **前端源码目录**：`frontend/manimind-console/src/`
2. **后端 API 定义**：`backend/api/*.py`（7 个路由文件）+ `backend/main.py`
3. **前端 package.json**：检查依赖版本
4. **前端 next.config.ts**：检查 API 代理配置

## Step-by-step process

### Step 1: API 端点映射检查

后端 API 端点（从 `backend/main.py` 和 `backend/api/*.py` 中提取）：

| 方法 | 路径 | 处理模块 | 前端调用页面 |
|------|------|----------|-------------|
| POST | /api/projects/plan | projects.py | review-actions（run-to-review 前置） |
| GET | /api/projects/{id}/runtime | projects.py | /live/page |
| POST | /api/projects/tasks | tasks.py | /live/tasks/page |
| POST | /api/projects/tasks/update | tasks.py | /live/tasks/page |
| POST | /api/projects/context-pack | contexts.py | /live/page |
| POST | /api/projects/events/message | events.py | 各页面（进度推送） |
| GET | /api/projects/{id}/events | events.py | /live/page |
| POST | /api/projects/run-to-review | execution.py | review-actions |
| POST | /api/projects/review/decision | reviews.py | review-actions |
| POST | /api/projects/finalize | execution.py | review-actions |

检查每个前端页面中的 fetch 调用：
- HTTP 方法是否正确（POST 还是 GET）
- 路径是否与后端路由一致（含路径参数格式）
- 请求体（body）的字段名是否与后端期望的一致

搜索前端中的 fetch/axios 调用：
```bash
grep -rn "fetch\|axios\|/api/" frontend/manimind-console/src/ --include="*.tsx" --include="*.ts"
```

### Step 2: 数据流一致性检查

检查 `src/data/` 下的数据映射是否与后端响应 schema 一致：

后端关键响应 schema（从 `models.py` 的 `to_dict()` 推导）：
- `ProjectPlan.to_dict()` → 18 个顶层字段
- `ExecutionTask.to_dict()` → 15 个字段
- `AgentProfile.to_dict()` → 7 个字段
- `ContextRecord.to_dict()` → 8 个字段

前端从 API 响应中读取的字段必须与这些 schema 一致。不允许前端使用后端未返回的字段。

### Step 3: 错误状态覆盖检查

每个页面应覆盖以下 UI 状态：

| 状态 | 含义 | 应有 UI |
|------|------|---------|
| loading | 数据正在加载 | 骨架屏或 loading spinner |
| empty | 数据为空（如无项目） | "暂无数据"提示 |
| error | API 请求失败 | 错误信息 + 重试按钮 |
| partial | 部分数据可用 | 部分展示 + 缺失说明 |
| success | 数据完整 | 正常展示 |

检查每个页面是否覆盖了这些状态。

### Step 4: 安全性检查

1. **前端是否直接 import `src/manimind/`**：
   ```bash
   grep -rn "from.*manimind\|import.*manimind" frontend/manimind-console/src/ --include="*.tsx" --include="*.ts"
   ```
   如果存在，这是严重违规——前端只能通过 API 访问后端。

2. **前端是否绕过审核门禁**：
   检查 `review-actions.tsx` 中 finalize 按钮是否在 `review.outputs` 未完成时仍可点击。

3. **API 代理配置**：
   检查 `next.config.ts` 中 `rewrites` 或 `proxy` 配置的 `destination` 是否与 backend 端口（默认 8000）一致。

### Step 5: 依赖一致性检查

对比 `package.json` 中的依赖与 `node_modules/` 实际安装：

```bash
# 如果 node_modules 存在
diff <(jq -r '.dependencies | keys[]' package.json | sort) <(ls node_modules/ | sort)
```

## Forbidden behaviors

- 禁止修改前端或后端代码
- 禁止启动 dev server（只做静态代码分析）
- 禁止安装前端依赖（只读取已有文件）
- 禁止在没有后端 API 契约时猜测前端 bug
- 禁止报告 CSS 风格或设计审美问题（只关注功能对齐和数据流）

## Verification checklist

| # | 检查项 | 方式 |
|---|--------|------|
| 1 | 每个页面的 API 调用与后端路由匹配 | grep fetch + 路径对比 |
| 2 | HTTP 方法正确 | 对比前端调用与后端路由 |
| 3 | 请求体字段名与后端 schema 一致 | 对比 TypeScript 类型与 Python to_dict |
| 4 | 所有页面覆盖 loading/empty/error/success 状态 | 代码审查 |
| 5 | 前端无 `src/manimind/` 直接 import | grep |
| 6 | finalize 触发需要 review 状态前置检查 | 代码审查 review-actions |
| 7 | next.config.ts 代理配置与 backend 端口一致 | 文件对比 |
| 8 | dependencies 版本与 node_modules 一致（如已安装） | diff |

## Common failure modes

| 模式 | 症状 | 修复 |
|------|------|------|
| API 路径不匹配 | 前端 fetch `/api/project/{id}` 但后端是 `/api/projects/{id}` | 统一路径 |
| HTTP 方法错误 | 前端用 GET 调用 POST 端点 | 修正方法 |
| 字段名不匹配 | 后端返回 `project_id`，前端读 `projectId` | 统一命名或添加映射 |
| 缺少错误状态 | 页面在 API 失败时白屏 | 添加 error boundary 和 Error 状态组件 |
| 直接 import 后端 | `import { ProjectPlan } from "manimind/models"` | 移除，改用 API 类型定义 |
| 绕过审核门禁 | finalize 按钮在 review 未完成时可点击 | 添加 review 状态前置检查 |

## Expected output

```json
{
  "pages_audited": [
    {
      "route": "/live",
      "api_calls": ["GET /api/projects/{id}/runtime", "GET /api/projects/{id}/events", "POST /api/projects/context-pack"],
      "methods_correct": true,
      "paths_correct": true,
      "aligned": true
    },
    {
      "route": "/live/tasks",
      "api_calls": ["POST /api/projects/tasks", "POST /api/projects/tasks/update"],
      "methods_correct": true,
      "paths_correct": true,
      "aligned": true
    },
    {
      "route": "/live/review",
      "api_calls": ["POST /api/projects/run-to-review", "POST /api/projects/review/decision", "POST /api/projects/finalize"],
      "methods_correct": true,
      "paths_correct": true,
      "aligned": false,
      "issue": "review-actions.tsx 的 finalize 按钮未检查 review.outputs 状态"
    },
    {
      "route": "/live/artifacts",
      "api_calls": ["GET /api/projects/{id}/runtime"],
      "methods_correct": true,
      "paths_correct": true,
      "aligned": true
    },
    {
      "route": "/mock",
      "api_calls": [],
      "aligned": true,
      "note": "静态页面，无 API 依赖"
    }
  ],
  "api_orphans": ["POST /api/projects/events/message", "GET /api/projects/{id}/review-return"],
  "missing_error_states": [
    {"page": "/live/artifacts", "missing": "empty_state, error_state"},
    {"page": "/live/tasks", "missing": "empty_state"}
  ],
  "direct_backend_imports": [],
  "security_flags": [
    {
      "location": "review-actions.tsx",
      "issue": "finalize 可以在 review.outputs 未完成时触发",
      "severity": "high"
    }
  ],
  "api_proxy_config": {
    "configured": true,
    "port": 8000,
    "matches_backend": true
  }
}
```

# ManiMind Console

`frontend/manimind-console/` 是 ManiMind 控制台前端（Next.js 16 + React 19 + Tailwind CSS 4）。

## 页面路由

- `/live`：真实 API 接线页（默认首页会重定向到这里）
- `/mock`：原有 mock 骨架页

## 本地启动

1. 启动后端 API（建议在仓库根目录）：

```powershell
python -m uvicorn backend.main:app --reload
```

2. 启动前端：

```powershell
cd frontend/manimind-console
npm install
npm run dev
```

## Live 模式使用

`/live` 页面支持：

1. 查看真实 `runtime` / `events` / `review-return` 数据
2. 触发 `run-to-review`
3. 人工审核 `approve` / `return`
4. 审核通过后触发 `finalize`（post_produce + package）

默认参数：

- `project_id=max-function-review-demo`
- `session_id=manual-session`
- `manifest_path=configs/max-function-review-demo.json`

可通过 query 覆盖，例如：

`/live?project_id=stage1-golden-path&session_id=manual-session&manifest_path=configs/stage1-golden-path.example.json`

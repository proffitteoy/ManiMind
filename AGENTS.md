# ManiMind Agent Notes

默认使用中文。

## 文档优先级

1. 当前文件
2. `docs/强前置条件约束.md`
3. `docs/通用项目架构模板.md`
4. `docs/代码组织.md`
5. 根目录 `README.md`

## 仓库边界

- `resources/skills/html-animation/`：HTML 动画 skill 与模板资产（白名单并入）。
- `resources/references/hyperframes/`：HyperFrames 参考与精选 registry 片段（白名单并入）。
- `resources/skills/manim/SKILL.md`：Manim skill 文档副本。
- 编排逻辑统一放在 `src/manimind/`。

## 修改原则

- 优先改编排层，不复制外部仓库内部实现。
- 长期上下文与短期上下文必须分离建模，不允许混写。
- 任何新增状态都必须定义生命周期、写入者、消费者和失效规则。
- 审核 Agent 是强制关卡，不能跳过直接进入成片拼接。
- 修改 `resources/` 下第三方资产时，必须在文档中写明来源与裁剪原因。

## 产物约定

- 长期上下文：`runtime/projects/<project_id>/`
- 短期协作上下文：`runtime/sessions/<session_id>/`
- 输出产物：`outputs/<project_id>/`
- 检测报告：`runtime/bootstrap-report.json`、`runtime/doctor-report.json`

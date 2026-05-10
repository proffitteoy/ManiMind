# canvas-dev

## Profile
- scope: Canvas 白板驱动开发流程
- primary_target: llm
- secondary_target: human
- last_verified: 2026-02-26

## Core Idea
将 Canvas 白板作为架构显式工件，代码作为其可执行映射。

## ManiMind 落地约定

- 当前仓库的正式白板文件是 `docs/architecture.canvas`。
- 当前采用“模块/子系统级”粒度，不按单个测试文件建节点。
- 结构变更必须在同一次修改中同步更新：
  - `docs/architecture.canvas`
  - `docs/通用项目架构模板.md`
- 对 ManiMind 而言，白板用于表达模块边界、角色分布、状态写入路径、上下文装配链路和第三方能力接入边界。

## I/O Contract for LLM
- input:
  - 项目代码目录或模块清单
  - `.canvas` 文件或 Canvas JSON
  - 目标变更说明
- output:
  - 架构图更新建议
  - 代码改动建议或补丁
  - 白板与代码一致性检查结论

## Structure
```text
canvas-dev/
├── README.md
├── workflow.md
├── prompts/
│   ├── 01-架构分析.md
│   ├── 02-白板驱动编码.md
│   └── 03-白板同步检查.md
├── templates/
│   ├── project.canvas
│   └── module.canvas
└── examples/
    └── demo-project.canvas
```

## Minimal Workflow
1. 用 `prompts/01-架构分析.md` 从现有代码生成或更新白板。
2. 在白板上调整模块与依赖关系。
3. 用 `prompts/02-白板驱动编码.md` 生成或修改代码。
4. 用 `prompts/03-白板同步检查.md` 校验代码与白板一致性。

## Related
- [workflow.md](./workflow.md)
- [四阶段×十二原则方法论](../documents/四阶段×十二原则方法论.md)
- [编程之道](../documents/编程之道.md)
- [Obsidian Canvas AI驱动的项目架构洞察与生成引擎.md](./Obsidian Canvas AI驱动的项目架构洞察与生成引擎.md)

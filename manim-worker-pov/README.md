# manim-worker-pov

最小 POV：只验证 Manim Worker 能否在固定结构化 spec 下完成：

1. `scene_spec.yaml` -> 生成可运行 `scene.py`
2. 执行 `manim render`
3. 基于渲染日志修复（最多 3 轮）

不验证多 Agent、Planner、Explorer、数学讲解设计能力。

## 目录结构

```text
manim-worker-pov/
├── README.md
├── specs/
│   └── derivative_geometry.yaml
├── prompts/
│   ├── generate_scene.md
│   └── repair_scene.md
├── src/
│   ├── worker.py
│   ├── renderer.py
│   └── log_parser.py
└── runs/
    └── derivative_geometry/
        └── scene_spec.yaml
```

运行后会在 `runs/derivative_geometry/` 下生成：

- `attempt_001.py` / `attempt_001.log`
- `attempt_002.py` / `attempt_002.log`（如果需要修复）
- `attempt_003.py` / `attempt_003.log`（如果需要修复）
- `attempt_004.py` / `attempt_004.log`（如果需要修复）
- `final_scene.py`（成功时）
- `output.mp4`（成功时）
- `result.json`

其中最多允许 1 次初始生成 + 3 次修复（总计不超过 4 次尝试）。

## 运行前依赖

1. Python 3.11+
2. `manim` 命令可用
3. `pyyaml` 可用
4. 一个外部 LLM 命令：从 `stdin` 读取 prompt，从 `stdout` 输出完整 Python 文件

## 运行方式

在 `manim-worker-pov/` 目录下执行：

```powershell
python .\src\worker.py `
  --spec .\specs\derivative_geometry.yaml `
  --run-dir .\runs\derivative_geometry `
  --prompts-dir .\prompts `
  --llm-command <your-llm-command> <arg1> <arg2>
```

如果你的环境没有 `python` 命令，可改用 `py -3`：

```powershell
py -3 .\src\worker.py --llm-command <your-llm-command> <arg1> <arg2>
```

例如（示意）：

```powershell
python .\src\worker.py --llm-command codex run
```

`--llm-command` 后面的程序必须满足：

- 输入：prompt（stdin）
- 输出：完整 Python 代码（stdout）

## 成功标准（POV）

- 在固定 `scene_spec.yaml` 下，`<= 4` 次尝试内产出可渲染 `final_scene.py`
- 成功输出 `output.mp4`
- 每轮 `attempt_xxx.py` 与 `attempt_xxx.log` 可追溯保留

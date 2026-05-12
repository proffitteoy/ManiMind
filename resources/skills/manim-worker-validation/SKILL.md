---
name: manim-worker-validation
description: "验证 Manim Worker 的端到端可行性——从结构化 spec 出发，经历代码生成、渲染执行、日志修复的完整闭环。同时覆盖编排层内的 ManimWorkerAdapter（src/manimind/worker_adapters.py）和独立 POV（manim-worker-pov/src/worker.py）两条路径。触发短语：manim worker validation、验证 Manim Worker、test manim render、check manim setup、manim feasibility。"
required_tools:
  - name: manim
    install: "pip install manim>=0.19.0"
    version_min: "0.19.0"
  - name: python3
    install: "Python 3.11+"
required_packages:
  - "manim"
roles: ["manim_worker", "lead"]
stages: ["dispatch", "prestart"]
---

# Manim Worker 可行性验证

## Overview

ManiMind 当前有两条 Manim Worker 实现路径：

| 路径 | 位置 | 调用方式 | 集成状态 |
|------|------|----------|----------|
| 编排层 ManimWorkerAdapter | `src/manimind/worker_adapters.py:332-587` | `render_with_worker()` via `executor.py` | 已接入主链路 |
| 独立 POV | `manim-worker-pov/src/worker.py:163-258` | CLI `--llm-command` | 未接入 runtime |

两条路径的核心能力一致：spec -> generate code -> render -> error classify -> repair（最多 3 轮）。

本 skill 验证两者在当前环境（WSL + manim 版本 + LLM 配置）下是否可用，并发现版本不兼容、缺失依赖、API 变动等问题。

默认使用 POV 侧的最小验证 spec：`manim-worker-pov/specs/derivative_geometry.yaml`。该 spec 定义了一个"导数切线几何直觉"场景，只包含最基本的 MathTex、Axes、VGroup、动画，是 Manim Community 稳定 API 的子集。

## When to use

- 首次部署 ManiMind 或更换 Manim 版本后
- `manim` 命令路径变更后（如 `pip install --upgrade manim`）
- 修改了 `resources/skills/manim/SKILL.md` 后（能力说明变更可能暗示 API 变更）
- 修改了 `src/manimind/prompt_system.py` 的 `manim_generate_recipe()` 或 `manim_repair_recipe()` 后
- 修改了 `src/manimind/worker_adapters.py` 的 `ManimWorkerAdapter` 后
- 发现生产环境中 Manim Worker 频繁渲染失败（> 50% 失败率）
- 新增场景类型需要验证时

## Required inputs

1. **Manim 可执行文件**：自动检测 `which manim`，若失败则读取 `MANIMIND_MANIM_PATH` 环境变量
2. **最小 scene spec**：默认 `manim-worker-pov/specs/derivative_geometry.yaml`
3. **LLM 配置**：从环境变量读取（`MANIMIND_WORKER_MODEL`、`MANIMIND_WORKER_MODEL_BASE_URL` 等）
4. **最大修复轮数**：默认 3（= 总共最多 4 次 LLM 调用）
5. **渲染 quality**：默认 `ql`（480p），可选 `qh`（720p）、`qk`（1080p）

## Step-by-step process

### Step 1: 环境检测

```bash
# 检测 manim 命令
which manim
manim --version

# 检测 Python 版本
python3 --version

# 检查 ffmpeg（Manim 渲染依赖）
which ffmpeg
```

如果这三者任一项缺失，验证结果为 `blocked` 并给出安装指令。

### Step 2: 加载 spec

读取 `manim-worker-pov/specs/derivative_geometry.yaml`（或用户指定的 spec）：

```yaml
scene_class: "DerivativeGeometryScene"
quality: "ql"
title: "导数的切线几何直觉"
segments:
  - id: "intro"
    narration: "..."
    manim_elements: [...]
```

关键检查项：
- `scene_class` 存在且与 `prompts/generate_scene.md` 中的 `{{SCENE_SPEC}}` 占位符兼容
- `manim_elements` 不超过 5 个（最小场景复杂度）
- 没有 LaTeX 多行环境（`\begin{}` ... `\end{}`）

### Step 3: 执行生成（首次尝试）

调用 LLM 生成 Manim 代码。编排层内使用 `ManimWorkerAdapter.render()`；POV 侧使用 `call_llm_generate()`。

收集输出：
- 生成的 Python 代码文本
- LLM 响应元数据（token 数、延迟）

### Step 4: 预渲染验证

在调用 `manim render` 之前，先做静态验证（`_validate_scene_code`）：

```
1. 包含 "from manim import *"？
2. 只定义了 1 个 Scene 类？
3. 类名与 spec 中 scene_class 一致？
4. 没有 import 第三方库（除 manim）？
5. 没有引用外部文件路径？
```

### Step 5: 渲染执行

```bash
manim -ql attempt_001.py DerivativeGeometryScene --media_dir ./media
```

超时：120 秒（`ql`）/ 240 秒（`qh`）

### Step 6: 结果判定与修复循环

- 若渲染成功：定位输出 mp4，记录尝试次数，结束
- 若渲染失败：分类错误（latex_error / attribute_error / syntax_error / type_error / name_error / validation_error / render_error）
- 若仍有修复轮数：调用 repair prompt，新代码覆盖，回到 Step 4
- 若已耗尽修复轮数：验证结果为 `fail`，保留所有 attempt 日志

### Step 7: 产物收集

```
runs/<run_name>/
├── scene_spec.yaml        # 使用的 spec 副本
├── attempt_001.py         # 首次生成
├── attempt_001.log        # 首次渲染日志
├── attempt_002.py         # 修复（如有）
├── attempt_002.log
├── ...
├── scene.py               # 最终成功代码
├── scene.mp4              # 最终渲染产物
└── validation_report.json # 验证报告
```

## Forbidden behaviors

- 禁止修改已验证通过的 scene spec（若 spec 本身有问题，报告而非修改）
- 禁止在验证失败时降低 spec 复杂度使其通过——应报告"spec 在当前环境不可行"
- 禁止跳过渲染步骤而仅做代码语法检查（静态验证通过不代表 Manim 可渲染）
- 禁止删除失败尝试的日志和代码（每个 attempt 必须保留用于审计）
- 禁止超过 4 次 LLM 调用（1 生成 + 3 修复）而不报告失败
- 禁止在 WSL 中用 Windows 路径（如 `F:\`）调用 manim

## Verification checklist

| # | 检查项 | 判定标准 |
|---|--------|----------|
| 1 | `manim` 命令可用 | `which manim` 返回有效路径 |
| 2 | manim 版本 >= 0.19.0 | `manim --version` 输出解析 |
| 3 | ffmpeg 可用 | `which ffmpeg` 返回有效路径 |
| 4 | 生成代码含 `from manim import *` | grep 检查 |
| 5 | 只定义 1 个 Scene 类 | regex: `class X(Scene)` 计数 = 1 |
| 6 | 类名与 spec 一致 | 提取类名与 `scene_class` 对比 |
| 7 | 无外部资源引用 | 无 `import` 非 manim 库，无文件路径 |
| 8 | 无 LaTeX 多行环境 | 无 `\begin{` |
| 9 | 渲染 exit code = 0 | subprocess 返回码 |
| 10 | 输出 mp4 存在 | `scene.mp4` 或 `output.mp4` 可定位 |
| 11 | mp4 时长 > 0 | ffprobe 检测 |
| 12 | 修复日志完整 | 每轮 attempt_xxx.log 非空 |

## Common failure modes

| 模式 | 症状 | 根因 | 修复方向 |
|------|------|------|----------|
| manim 未安装 | `command not found: manim` | 缺少 pip install manim | `pip install manim>=0.19.0` |
| manim API 变更 | `AttributeError: 'Scene' object has no attribute 'xxx'` | Manim CE 版本升级 | 检查 changelog，更新代码/提示词 |
| LaTeX 未安装 | `LaTeX Error: ...` | 系统缺少 texlive/miktex | `sudo apt install texlive texlive-latex-extra` |
| LaTeX 表达式超限 | 渲染超时或崩溃 | MathTex 字符串过长（>200 字符）或多行环境 | 简化表达式，使用 Text 替代 |
| 视频编码失败 | mp4 文件 0 字节 | 缺少 libx264 | `sudo apt install ffmpeg`（含编码器） |
| WSL 路径问题 | `FileNotFoundError` | Windows 路径 `/mnt/f/` vs Linux 路径不一致 | 统一使用 WSL 风格路径或 `wslpath` |
| LLM 超时 | 生成阶段超时 | 模型响应慢或 prompt 过长 | 减小 spec 大小或增加 timeout |

## Expected output

```json
{
  "status": "pass|fail|blocked",
  "environment": {
    "manim_version": "0.20.1",
    "manim_path": "/home/kali/.local/bin/manim",
    "python_version": "3.12.3",
    "ffmpeg_available": true,
    "os": "WSL (Linux)"
  },
  "spec_used": "manim-worker-pov/specs/derivative_geometry.yaml",
  "scene_class": "DerivativeGeometryScene",
  "attempts": 2,
  "attempts_detail": [
    {
      "attempt": 1,
      "code_path": ".../attempt_001.py",
      "log_path": ".../attempt_001.log",
      "render_success": false,
      "error_type": "latex_error",
      "error_summary": "MathTex 中 \\xrightarrow 多行参数不兼容 Manim 0.20.1"
    },
    {
      "attempt": 2,
      "code_path": ".../attempt_002.py",
      "log_path": ".../attempt_002.log",
      "render_success": true
    }
  ],
  "final_scene": ".../scene.py",
  "output_video": ".../scene.mp4",
  "video_duration_seconds": 18.5,
  "warnings": [
    "Manim 0.20.1 中部分 LaTeX 箭头宏不再支持多行参数，已在修复中规避"
  ]
}
```

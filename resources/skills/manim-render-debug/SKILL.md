---
name: manim-render-debug
description: "系统性地排查 Manim 渲染失败原因——分类错误、定位根因、产出最小修复方案。与 manim_repair_recipe() 的区别：此 skill 追求最小 patch（不超过 10 行），而不做全量重新生成。触发短语：manim render debug、排查 Manim 渲染、manim error fix、render failed、manim latex error、manim attribute error。"
roles: ["manim_worker"]
stages: ["dispatch"]
---

# Manim 渲染错误排查

## Overview

当 `ManimWorkerAdapter`（`src/manimind/worker_adapters.py`）或 `manim-worker-pov/src/worker.py` 的渲染步骤失败时，此 skill 提供结构化的错误排查流程。

当前 ManiMind 的错误分类函数位于两处（实现一致）：

| 位置 | 函数 | 分类数 |
|------|------|--------|
| `worker_adapters.py:115-129` | `_classify_manim_error()` | 7 类 |
| `manim-worker-pov/src/log_parser.py` | `classify_error()` | 7 类 |

支持的 7 种错误分类：
- `latex_error`：LaTeX 编译失败（tex 引擎报错）
- `attribute_error`：Manim API 不存在或已改名
- `syntax_error`：Python 语法错误
- `type_error`：参数类型不匹配
- `name_error`：变量未定义
- `validation_error`：预渲染验证失败（class 数量、名称、import 等）
- `render_error`：其他渲染失败（兜底）

## When to use

- Manim Worker 渲染失败且失败日志已收集
- 同一类型错误在一周内出现 3 次以上（说明修复策略需要调整）
- 需要理解为什么某类 LaTeX 表达式在特定 Manim 版本下失败
- 需要在"修复当前场景"和"降低数学复杂度"之间做决策
- 人工打回原因包含"渲染失败"或"画面质量问题"

## Required inputs

1. **失败的代码文件**：`attempt_xxx.py`（或其他 .py 文件）
2. **完整渲染日志**：`attempt_xxx.log`（不能截断）
3. **Scene class 名称**：从 spec 或 `segment.to_dict()` 中提取
4. **原始 segment spec**：含 formulas、narration、goal
5. **已执行的修复轮数**：当前 attempt 编号

## Step-by-step process

### Step 1: 错误分类

从渲染日志中提取关键错误行，匹配已知分类模式：

```
latex_error:     "LaTeX Error" / "tex" / "latex"（出现在日志中）
attribute_error: "AttributeError: ... has no attribute ..."
syntax_error:    "SyntaxError: ..."  
type_error:      "TypeError: ..."
name_error:      "NameError: name '...' is not defined"
validation_error: "PRE_RENDER_VALIDATION_ERROR: ..."（worker_adapters 自己注入的）
```

使用 `grep -n -E "(Error|Exception|Traceback)" attempt_xxx.log` 快速定位。

### Step 2: 根因诊断

根据错误分类做进一步诊断：

**latex_error**：
```bash
# 提取所有 MathTex 字符串
grep -oP 'MathTex\(.*?\)' attempt_xxx.py
# 检查是否有 LaTeX 多行环境
grep -n '\\begin{' attempt_xxx.py
# 检查每个 MathTex 字符串长度
# 超 200 字符的标记为风险
```

常见子类型：
- `\begin{}` 多行环境 → Manim MathTex 不支持，需用 Text 替代或拆为多个 MathTex
- `\xrightarrow{...}` 多行参数 → 部分 Manim 版本不兼容
- 缺失 LaTeX 包 → 需要 `texlive-latex-extra`
- unicode 字符在 LaTeX 中不支持 → 需用 ASCII 替代或 Text

**attribute_error**：
- 检查 Manim 版本：`manim --version`
- 检查 API 是否在 changelog 中被标记为 deprecated
- 常见：`self.play(Transform(...))` → 参数类型错误；`VGroup.arrange()` → kwargs 参数名变更

**syntax_error**：
- 检查代码中是否有未闭合的括号、引号
- 常见：MathTex 字符串中使用了 Python 的三引号但未转义

**name_error**：
- 变量定义在使用之前被删除或未定义
- 常见：修复时删除了某行代码但保留了对该变量的引用

**validation_error**：
- class 数量不对：修复时新增了辅助 class 但忘记删除
- 类名不匹配：spec 的 `scene_class` 与代码中不一致
- 缺少 `from manim import *`：修复时误删

### Step 3: 最小修复方案

针对根因，产出最小变更方案：

规则：
- 单次修复不超过 10 行变更
- 尽量不改动叙事结构和动画顺序
- 选择更稳定的替代 API（如 MathTex → Text 用于纯文本）
- 修复后必须通过 `_validate_scene_code`

针对各错误类型的标准修复策略：

| 错误类型 | 首选修复 | 备选方案 |
|----------|----------|----------|
| latex_error (多行环境) | 拆为多个 MathTex 并用 VGroup 组合 | 用 Text 替代 |
| latex_error (单行超长) | 拆为 2-3 个 MathTex 分步展示 | 用 Text + 手动格式 |
| attribute_error | 查 Manim 文档找替代 API | 降级 Manim 版本 |
| syntax_error | 修正语法错误 | 从正确版本重新生成该行 |
| type_error | 补类型转换 | 调整参数顺序 |
| name_error | 补变量定义 | 删除对该变量的引用 |
| validation_error | 修正 class 结构 | 从正确版本恢复 import |
| render_error | grep 日志中的第一个 ERROR | 按错误类型进一步分类 |

### Step 4: 验证修复

1. 静态验证：`_validate_scene_code(fixed_code, scene_class)`
2. 渲染验证：执行 `manim -ql scene.py SceneClass`（超时 120 秒）
3. 对比验证：修复前后 diff 不超过 10 行
4. 时长验证：渲染产物时长与配音时长偏差 < 15%

### Step 5: 如果最小修复失败

若最小修复后仍然渲染失败，且已执行 2 次最小修复尝试，则升级为"全量重新生成"，调用 `manim_repair_recipe()`。

## Forbidden behaviors

- 禁止删除日志中的错误行（日志必须完整保留）
- 禁止在没有理解根因时猜测修复（"试试删掉这行"不可接受）
- 禁止超过 10 行以上的重写（超过则升级为 full regenerate）
- 禁止把 LaTeX 错误当作文本错误来修（MathTex 的数学表达式 ≠ Python 字符串）
- 禁止擅自降低 spec 中的数学精度要求（只修渲染，不改内容）
- 禁止在修复后跳过 re-render 验证
- 禁止修改原始 spec 使其"更简单"

## Verification checklist

| # | 检查项 | 方式 |
|---|--------|------|
| 1 | 错误日志已解析出 error_type | `_classify_manim_error(log)` |
| 2 | 错误行号已定位 | 日志中 `line N` 或 grep |
| 3 | 根因诊断完成 | 人工确认对 error_type 的理解 |
| 4 | 修复方案是"最小 patch" | `diff -u old.py new.py | wc -l` < 20 |
| 5 | 修复后代码通过 `_validate_scene_code` | 静态检查 |
| 6 | 修复后渲染成功 | `manim render` exit 0 |
| 7 | 渲染产物时长与配音偏差 < 15% | ffprobe 对比 timing_manifest |

## Common failure modes

| 模式 | 症状 | 根因 | 修复 |
|------|------|------|------|
| `\xrightarrow` 多行 | `LaTeX Error: ... \xrightarrow` | Manim 0.20.x 中 MathTex 不支持多行箭头参数 | 用 Arrow + Text 组合替代 |
| `\begin{aligned}` | `LaTeX Error: Bad math environment delimiter` | MathTex 不支持 `\begin`/`\end` 环境 | 拆为单行公式，用 `\\\\` 分隔 |
| `set_color` 不存在 | `AttributeError: 'VMobject' has no attribute 'set_color'` | API 在 Manim 0.19+ 变更为 `set(color=...)` 或 `animate.set_color()` | 更新为当前 API |
| `arrange` 参数变更 | `TypeError: arrange() got unexpected keyword argument 'direction'` | `direction` → `direction` 参数名在版本间变更 | 检查当前版本文档 |
| WSL 下 manim 路径 | `manim: command not found` 尽管已安装 | pip 安装到 `~/.local/bin/` 不在 PATH | `export PATH="$HOME/.local/bin:$PATH"` |
| TeX 未安装 | `LaTeX Error: File '...' not found` | WSL 默认不含 texlive | `sudo apt install texlive texlive-latex-extra` |
| GPU/CPU 混合 | 渲染极慢（> 5 分钟） | manim 默认用 CPU 渲染，`--renderer=opengl` 可能不兼容 | 使用默认 Cairo 渲染器 |

## Expected output

```json
{
  "error_classification": "latex_error",
  "root_cause": "Manim 0.20.1 中 MathTex 不支持 \\xrightarrow 的多行参数语法",
  "error_location": {
    "file": "attempt_001.py",
    "line": 47,
    "snippet": "MathTex(r\"A \\xrightarrow[below]{above} B\")"
  },
  "fix_applied": {
    "type": "minimal_patch",
    "description": "将 \\xrightarrow 替换为 Arrow + 上方 MathTex 标签 + 下方 MathTex 标签的组合",
    "lines_changed": 3,
    "before": "MathTex(r\"...\\xrightarrow[...]{...}...\")",
    "after": "arrow = Arrow(...); label_up = MathTex(...).next_to(arrow, UP); label_down = MathTex(...).next_to(arrow, DOWN)"
  },
  "render_result": "success",
  "preventive_notes": "如未来需大量极限/变换箭头，建议在 manim SKILL.md 的限制段落新增此类 LaTeX 限制说明",
  "should_update_skill": true,
  "skill_patch_target": "resources/skills/manim/SKILL.md",
  "skill_patch_suggestion": "在 LaTeX 限制段落添加：避免 \\xrightarrow 多行参数，使用 Arrow + Text 组合"
}
```

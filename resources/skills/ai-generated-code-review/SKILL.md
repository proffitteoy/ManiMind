---
name: ai-generated-code-review
description: "对 ManiMind 系统中 AI 生成的代码（Manim Python、HTML 动画、SVG 关系图）进行结构性质量审查。关注的是 AI 产出物的代码质量，不替代 reviewer 的数学正确性审核。覆盖三种媒介产物的独立检查标准。触发短语：AI 代码审查、生成代码审查、code review AI output、check manim code quality、check HTML output、review generated code。"
roles: ["reviewer", "html_worker", "manim_worker", "svg_worker"]
stages: ["dispatch", "review"]
---

# AI 生成代码审查

## Overview

ManiMind 的三种 Worker 会产生三种不同的 AI 生成代码：

| Worker | 产物类型 | 输出目录 | 验证函数 |
|--------|----------|----------|----------|
| html_worker | 单文件 HTML | `outputs/<project_id>/html/<seg_id>/index.html` | `_ensure_html_document()` |
| svg_worker | 单文件 SVG | `outputs/<project_id>/svg/<seg_id>/scene.svg` | `_ensure_svg_document()` |
| manim_worker | 单文件 Python | `outputs/<project_id>/manim/<seg_id>/scene.py` | `_validate_scene_code()` |

本 skill 在 reviewer 的"数学正确性"审查之前，先做"代码结构质量"审查。reviewer 不应浪费时间审查有结构性缺陷的代码。

与 `reviewer_recipe()` 的职责边界：
- 本 skill → 代码结构质量（语法、格式、API 用法、渲染可行性）
- reviewer → 数学正确性、叙事一致性、媒介匹配度
- human_reviewer → 最终放行/打回

## When to use

- 每个 worker 完成片段生成后（reviewer 之前）
- 人工打回后，worker 重新生成的代码需要验证修复质量
- 新增模板或修改 worker prompt 后（需要抽检产出物质量）
- 发现某类产物反复被 reviewer 打回时（可能是结构性缺陷未被发现）

## Required inputs

1. **要审查的代码文件**：`.py` / `.html` / `.svg` 路径
2. **对应的 segment spec**：`SegmentSpec.to_dict()`（含 narration、formulas、goal、modality）
3. **worker 的原始 prompt**：`runtime/sessions/<session_id>/context-packets/*.json`
4. **渲染日志**：Manim 需要 `render.log`
5. **能力限制参考**：
   - `resources/skills/manim/SKILL.md`：Manim API 限制
   - `resources/skills/html-animation/SKILL.md`：HTML 模板约束

## Step-by-step process

### Step 1: 确定代码类型

根据文件扩展名确定审查模式：`.py` → Manim 模式，`.html` → HTML 模式，`.svg` → SVG 模式。

### Step 2: 通用质量检查（所有类型）

无论什么类型的产物，都执行以下检查：

1. **完整性检查**：文件非空，不含 Markdown fence（` ``` `），不含解释性文字
2. **无外部依赖**：不引用外部 CDN、字体、脚本、图片 URL
3. **无硬编码绝对路径**：不引用 `/home/`、`C:\`、`/mnt/` 等本地路径
4. **编码正确**：文件为 UTF-8 编码

### Step 3: 媒介特定检查

#### Manim Python 产物

执行 `worker_adapters.py:97-112` 的 `_validate_scene_code()` 等效检查：

1. **单类检查**：`class X(Scene)` 定义计数 = 1。如果 > 1（如同时定义了 Scene 和辅助类），标记为 warning 而非 fail（辅助类是合理的）
2. **类名匹配**：Scene 类名与 segment spec 的 `scene_class` 一致
3. **必需 import**：含 `from manim import *`
4. **无第三方 import**：不 import manim 以外的渲染库（numpy、scipy 允许）
5. **LaTeX 单行检查**：每个 MathTex 字符串 ≤ 200 字符；无 `\begin{` 或 `\end{` 环境
6. **动画时长检查**：总动画时长不超过 spec 的 `estimated_seconds` + 50%（避免无限动画）
7. **播放节奏检查**：存在 ≥ 2 处 `self.wait()`（确保画面有停顿，不连续播放）
8. **无硬编码坐标检查**：`to_edge()`、`next_to()` 优先于 `move_to((3.5, 2.0))`

#### HTML 产物

执行 `worker_adapters.py:80-87` 的 `_ensure_html_document()` 等效检查：

1. **文档结构检查**：含 `<!doctype html>`、`<html>`、`<head>`、`<body>`
2. **无外部资源检查**：无 `<link href="http...">`、无 `<script src="http...">`
3. **内联样式检查**：所有 CSS 在 `<style>` 标签内，无外部 `.css` 引用
4. **16:9 视口检查**：建议宽高比 1920x1080 或 1280x720；无固定像素宽度造成溢出
5. **文本可读性检查**：文本内容不使用绝对定位逐字放置（应使用正常文档流或 flexbox）
6. **无 JS 依赖检查**：动画使用 CSS animation/transition 而非 JavaScript

#### SVG 产物

执行 `worker_adapters.py:90-94` 的 `_ensure_svg_document()` 等效检查：

1. **根元素检查**：以 `<svg` 开头，有 `xmlns="http://www.w3.org/2000/svg"`
2. **viewBox 检查**：viewBox 尺寸适合视频合成（建议 `0 0 1280 720`）
3. **无外部资源检查**：无 `<image href="http...">`、无外部字体引用
4. **动画方式检查**：使用 SMIL（`<animate>`）或 CSS animation，不使用 JS
5. **元素数量检查**：根级元素数量 ≤ 20（避免过于复杂的 SVG）

### Step 4: 与 segment spec 对齐检查

检查生成代码是否覆盖了 spec 中要求的核心元素：

- **formulas 覆盖**：spec 中的每个 formula（LaTeX 字符串）在代码中有对应呈现
- **narration 覆盖**：如果 spec 指定了 narration_text，代码中的 Text/MathTex 覆盖了关键概念
- **goal 对应**：代码的视觉焦点与 spec 的 goal 一致

### Step 5: 生成质量评分

综合评分：

```text
pass:                所有 MUST 检查通过
pass_with_warnings:  MUST 检查全部通过，但 SHOULD 检查有建议
fail:                至少一项 MUST 检查失败
```

## Forbidden behaviors

- 禁止执行代码（只做静态分析，不运行 manim render 或浏览器预览）
- 禁止基于代码风格偏好做判断（如缩进宽度、变量命名风格）
- 禁止对数学正确性做判断（那是 reviewer 的工作）
- 禁止在没有 spec 参考的情况下断言"遗漏了关键信息"
- 禁止把 AI 的"保守回答"（如只用 Text 不用 MathTex）当作高质量

## Verification checklist

### Manim Python 检查清单

| # | 检查项 | 级别 | 检查方式 |
|---|--------|------|----------|
| M1 | 含 `from manim import *` | MUST | grep |
| M2 | 单个 Scene 类（辅助类不计数） | MUST | regex class X(Scene) |
| M3 | Scene 类名与 spec 一致 | MUST | 提取类名对比 |
| M4 | 无第三方渲染库 import | MUST | grep import（排除 manim/numpy/scipy） |
| M5 | 无外部文件路径 | MUST | 无 open()/Path() 读外部文件 |
| M6 | MathTex 字符串 ≤ 200 字符 | MUST | 每个 MathTex 字数统计 |
| M7 | 无 `\begin{}` / `\end{}` 环境 | MUST | grep |
| M8 | 总动画时长 ≤ spec + 50% | SHOULD | 估算 self.wait + play 时长 |
| M9 | ≥ 2 处 self.wait() | SHOULD | grep self.wait |
| M10 | 优先相对布局 | SHOULD | 减少硬编码坐标 |

### HTML 检查清单

| # | 检查项 | 级别 | 检查方式 |
|---|--------|------|----------|
| H1 | 含 `<!doctype html>` | MUST | grep -i |
| H2 | 含 `<html>`、`<head>`、`<body>` | MUST | grep |
| H3 | 无外部 CDN 引用 | MUST | 无 http:// 或 https:// 的 `<link>` / `<script>` |
| H4 | 无外部 JS 依赖 | MUST | 无 `<script src=>` |
| H5 | CSS 内联在 `<style>` | SHOULD | 检查 |
| H6 | 视口适合 16:9 | SHOULD | 检查 body max-width / aspect-ratio |
| H7 | 文本可读（非绝对定位堆砌） | SHOULD | 代码审查 |

### SVG 检查清单

| # | 检查项 | 级别 | 检查方式 |
|---|--------|------|----------|
| S1 | 以 `<svg` 开头 | MUST | 检查首行 |
| S2 | xmlns 声明 | MUST | grep xmlns |
| S3 | viewBox 适合视频 (1280x720) | SHOULD | 提取 viewBox 属性 |
| S4 | 无外部图片引用 | MUST | 无 `<image href="http...">` |
| S5 | 使用 SMIL 或 CSS 动画 | SHOULD | grep animate 或 @keyframes |
| S6 | 根级元素 ≤ 20 | SHOULD | 计数 |

## Common failure modes

| 模式 | 产物类型 | 症状 | 修复建议 |
|------|----------|------|----------|
| Markdown fence 泄露 | 全部 | 代码被 ` ``` ` 包裹 | 调用 `_strip_markdown_fences()`，如果仍失败则升级为 fail |
| 多类定义 | Manim | 代码中 class 定义 > 1 | 排除辅助类后仍 > 1 的标记为 fail |
| LaTeX 多行环境 | Manim | `\begin{aligned}` 导致渲染失败 | 拆为单行 MathTex |
| 外部字体引用 | HTML | `<link href="https://fonts.googleapis.com">` | 使用系统字体 fallback |
| CDN 脚本 | HTML | `<script src="https://cdn.jsdelivr.net">` | 移除或内联 |
| 绝对坐标硬编码 | Manim | `move_to((4.5, -2.3))` | 使用 `to_edge()` / `next_to()` |
| viewBox 缺失 | SVG | `<svg>` 无 viewBox | 添加 `viewBox="0 0 1280 720"` |
| 外部图片 | SVG | `<image href="https://...png">` | 移除或用纯 SVG 元素替代 |
| 公式遗漏 | Manim | spec 要求 3 个 formulas，代码只呈现 2 个 | 标记为 warning，通知 reviewer |

## Expected output

```json
{
  "file": "outputs/cauchy/manim/seg-03/scene.py",
  "media_type": "manim",
  "overall_grade": "pass_with_warnings",
  "checks": [
    {"id": "M1", "rule": "has_manim_star_import", "result": "pass"},
    {"id": "M2", "rule": "single_scene_class", "result": "pass"},
    {"id": "M3", "rule": "class_name_matches_spec", "result": "pass", "expected": "SegmentCauchyInductionScene", "got": "SegmentCauchyInductionScene"},
    {"id": "M4", "rule": "no_external_imports", "result": "pass"},
    {"id": "M5", "rule": "no_external_file_paths", "result": "pass"},
    {"id": "M6", "rule": "latex_length_limit", "result": "fail", "detail": "line 52: MathTex 字符串 248 字符超限（200 限制）"},
    {"id": "M7", "rule": "no_latex_environments", "result": "pass"},
    {"id": "M8", "rule": "animation_duration_budget", "result": "pass", "estimated_seconds": 22, "budget": 30},
    {"id": "M9", "rule": "has_wait_pauses", "result": "pass", "wait_count": 3},
    {"id": "M10", "rule": "prefer_relative_layout", "result": "warning", "detail": "line 67: 使用硬编码坐标 (4.2, -1.8)，建议用 next_to()"}
  ],
  "failures": [
    {
      "rule": "M6",
      "severity": "must_fix",
      "detail": "line 52: MathTex 字符串 '\\xrightarrow[\\text{归纳假设}]{...}' 248 字符超限"
    }
  ],
  "warnings": [
    {
      "rule": "M10",
      "severity": "should_fix",
      "detail": "line 67: 使用硬编码坐标，建议改为相对布局"
    }
  ],
  "segment_id": "seg-03",
  "worker_role": "manim_worker",
  "review_escalation": "M6 latex_length_limit 失败，reviewer 应关注该 LaTeX 表达的替代方案是否改变了数学语义",
  "spec_alignment": {
    "formulas_in_spec": 1,
    "formulas_present": 1,
    "narration_keywords_covered": ["归纳", "假设", "验证"]
  }
}
```

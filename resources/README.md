# resources 目录说明

`resources/` 用于存放并入项目的第三方精选资产，不再使用独立 `vendor/` 根目录。

## 目录结构

- `resources/skills/html-animation/`：HTML 科普动画相关 skill 与模板
- `resources/skills/manim/`：Manim skill 文档镜像
- `resources/references/hyperframes/`：HyperFrames 精选参考与 registry 片段

## 同步方式

使用 [sync-thirdparty-assets.ps1](/C:/Users/84025/Desktop/ManiMind/scripts/sync-thirdparty-assets.ps1) 进行白名单同步：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync-thirdparty-assets.ps1
```

如果开源仓库不在根目录，使用显式参数：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync-thirdparty-assets.ps1 `
  -HtmlSkillSource "<AI-Animation-Skill-main 路径>" `
  -HyperframesSource "<hyperframes-main 路径>"
```

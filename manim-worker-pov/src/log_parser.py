"""Render 日志分类器（规则版）。"""

from __future__ import annotations


def classify_error(log: str) -> str:
    """根据关键词规则分类渲染失败类型。"""
    lower = log.lower()

    if "pre_render_validation_error" in lower:
        return "validation_error"
    if "syntaxerror" in lower:
        return "syntax_error"
    if "nameerror" in lower:
        return "name_error"
    if "attributeerror" in lower:
        return "attribute_error"
    if "typeerror" in lower:
        return "type_error"
    if "valueerror" in lower:
        return "value_error"
    if "latex" in lower or "tex error" in lower or "latex error" in lower:
        return "latex_error"
    if "no module named" in lower:
        return "dependency_error"
    if "timeout" in lower:
        return "render_timeout"
    return "unknown_error"

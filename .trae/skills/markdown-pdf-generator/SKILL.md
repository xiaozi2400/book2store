---
name: "markdown-pdf-generator"
description: "Converts Markdown to PDF using Playwright+Chrome browser rendering with excellent Chinese support. Invoke when user needs to generate PDF from Markdown content."
---

# Markdown to PDF Generator

将 Markdown 内容高质量转换为 PDF，使用 Playwright + Chrome 浏览器渲染。

## 核心功能

- Markdown 转 HTML 渲染（支持 tables, fenced_code, nl2br 扩展）
- Playwright + Chrome 无头浏览器生成 PDF
- 中文排版优化（Microsoft YaHei 字体）
- A4 纸张格式，20mm 页边距
- 支持标题、段落、列表、表格、代码块、引用等元素

## 使用方式

```python
from .markdown_pdf import MarkdownPdfGenerator

generator = MarkdownPdfGenerator()
generator.generate(
    markdown_content="# 标题\n\n内容...",
    output_path="output.pdf",
    title="书籍标题",
    author="作者"
)
```

## HTML 模板样式

- 标题：28px，居中，页面分割后显示
- 作者：14px，居中，灰色
- 二级标题：20px，底部边框
- 段落：首行缩进 2em，1.8 行高
- 引用：左侧 4px 边框，灰色背景
- 表格：边框线，斑马色表头

## 异常处理

优先使用 Playwright + Chrome，失败时回退到 reportlab。

## 依赖

- playwright
- markdown (Python package)
- Chrome/Chromium 浏览器（Windows 系统）
# Plan: 创建 Markdown 转 PDF 生成技能

## 目标
创建一个专门的 skill，用于将 Markdown 内容高质量转换为 PDF，支持中文显示。

## 实现步骤

### 1. 创建 Skill 目录结构
```
.trae/skills/markdown-pdf-generator/
```

### 2. 创建 SKILL.md 文件
- **name**: `markdown-pdf-generator`
- **description**: 将 Markdown 内容转换为 PDF，使用 Playwright+Chrome 浏览器渲染确保中文支持。适用于需要生成书籍、文档等精美 PDF 排版的场景。
- **功能**:
  - Markdown 转 HTML 渲染
  - Playwright + Chrome 无头浏览器生成 PDF
  - 中文排版优化（微软雅黑字体）
  - A4 纸张格式设置
  - 支持标题、段落、列表、表格、代码块等元素

### 3. 核心实现
- `markdown_to_pdf(markdown_content, output_path, title, author)`
- 内置 HTML 模板，包含专业排版样式
- 异常处理：Playwright 失败时回退方案

### 4. 与现有系统集成
- 在 `content_summarizer.py` 中调用此 skill
- 解决标题从书籍元数据获取而非文件名的修改
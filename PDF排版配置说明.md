# PDF排版配置说明

## 简介

现在您可以通过修改 `pdf_config.json` 文件来调整PDF排版设置，无需修改代码。

## 配置文件位置

配置文件 `pdf_config.json` 位于项目根目录（与 `generate_chinese_pdf.py` 同级）。

## 常用配置项

### 1. 排版设置（typography）

控制行间距、段间距等核心排版参数：

```json
"typography": {
    "line_height": 1.8,              // 行距倍数（1.6-2.0之间较舒适）
    "minimum_line_height": 150,       // 最小行高百分比（120-180之间）
    "paragraph_indent": 2.0,          // 首行缩进（em单位，2em为标准中文缩进）
    "paragraph_spacing": 1.5,         // 段间距（em单位，1.0-2.0之间）
    "justify": true,                  // 两端对齐
    "hyphenate": true,                // 英文连字符断字
    "hyphenate_chinese": true         // 中文断字
}
```

**推荐设置：**
- **紧凑排版**：`line_height: 1.6`, `paragraph_spacing: 1.0`
- **舒适排版**：`line_height: 1.8`, `paragraph_spacing: 1.5`（默认）
- **宽松排版**：`line_height: 2.0`, `paragraph_spacing: 2.0`

### 2. 页面设置（page）

控制页面大小和边距：

```json
"page": {
    "paper_size": "letter",          // 纸张大小：letter, a4, a5
    "margin_top": 29,                // 上边距（pt，约10mm）
    "margin_bottom": 29,             // 下边距
    "margin_left": 29,               // 左边距
    "margin_right": 29,              // 右边距
    "background_color": "#f8f8f8"    // 背景色
}
```

**边距参考：**
- 电脑阅读（窄边距）：`margin_*: 29`（约10mm）
- 打印版本（标准边距）：`margin_*: 72`（约25mm）

### 3. 字体设置（font）

控制字体和字号：

```json
"font": {
    "default_size": 18,              // 正文字号（pt）
    "mono_size": 14,                 // 等宽字体字号
    "serif": "Source Han Serif SC,Noto Serif CJK SC,SimSun,serif",
    "sans": "Source Han Sans SC,Noto Sans CJK SC,SimHei,sans-serif",
    "mono": "Consolas,Microsoft YaHei Mono,monospace"
}
```

**字号参考：**
- 小字体：`default_size: 14`
- 中等字体：`default_size: 16`
- 大字体：`default_size: 18`（默认，适合电脑阅读）
- 超大字体：`default_size: 20`

### 4. CSS样式设置（css）

控制EPUB中的段落样式（最终影响PDF）：

```json
"css": {
    "paragraph_margin_bottom": "1.5em",    // 段间距
    "paragraph_line_height": "1.8",         // 行高
    "paragraph_text_indent": "2em",         // 首行缩进
    "heading_margin_top": "1.5em",          // 标题上边距
    "heading_margin_bottom": "1em",         // 标题下边距
    "list_item_margin_bottom": "0.8em",     // 列表项间距
    "blockquote_margin": "1.5em",           // 引用块边距
    "blockquote_padding_left": "1.5em",     // 引用块左内边距
    "blockquote_border_left": "3px solid #ccc" // 引用块左边框
}
```

### 5. 页眉页脚（header_footer）

```json
"header_footer": {
    "header_template": "",    // 页眉（空字符串表示不显示）
    "footer_template": "<div style=\"text-align:center;\">第 _PAGENUM_ 页 / 共 _TOTALPAGES_ 页</div>"
}
```

## 使用步骤

### 1. 修改配置

编辑 `pdf_config.json` 文件，修改您需要的参数。例如，增加段间距：

```json
"typography": {
    "line_height": 1.8,
    "paragraph_spacing": 2.0    // 从1.5改为2.0
}
```

### 2. 重新生成PDF

运行生成脚本：

```bash
python generate_chinese_pdf.py
```

程序会自动读取 `pdf_config.json` 中的最新配置。

## 配置示例

### 示例1：电脑阅读优化（默认）

```json
{
  "typography": {
    "line_height": 1.8,
    "paragraph_spacing": 1.5,
    "paragraph_indent": 2.0
  },
  "font": {
    "default_size": 18
  },
  "page": {
    "margin_top": 29,
    "margin_bottom": 29,
    "margin_left": 29,
    "margin_right": 29
  }
}
```

### 示例2：打印版本

```json
{
  "typography": {
    "line_height": 1.6,
    "paragraph_spacing": 1.0,
    "paragraph_indent": 2.0
  },
  "font": {
    "default_size": 16
  },
  "page": {
    "margin_top": 72,
    "margin_bottom": 72,
    "margin_left": 72,
    "margin_right": 72
  }
}
```

### 示例3：宽松阅读

```json
{
  "typography": {
    "line_height": 2.0,
    "paragraph_spacing": 2.0,
    "paragraph_indent": 2.0
  },
  "font": {
    "default_size": 20
  },
  "css": {
    "paragraph_margin_bottom": "2.0em",
    "paragraph_line_height": "2.0"
  }
}
```

## 注意事项

1. **JSON格式**：确保配置文件是有效的JSON格式（注意逗号、引号等）
2. **单位**：
   - 字号、边距使用 **pt**（点）
   - 行高、缩进、间距使用 **em**（相对单位）
3. **注释**：配置文件中以 `_` 开头的字段是注释，会被忽略
4. **默认值**：如果某个配置项缺失，程序会使用默认值
5. **生效方式**：修改配置后，需要重新运行生成脚本才能生效

## 故障排除

### 配置文件加载失败

如果看到 `[配置] 使用默认PDF排版配置`，说明配置文件未找到或格式错误。请检查：
- 文件是否位于项目根目录
- JSON格式是否正确（可使用在线JSON验证工具检查）

### 排版效果未改变

如果修改配置后PDF排版没有变化，请检查：
- 是否保存了配置文件
- 是否重新运行了生成脚本
- 修改的是否是正确的配置项

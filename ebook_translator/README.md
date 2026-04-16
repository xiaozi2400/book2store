# 电子书翻译和转换脚本

## 功能说明

本脚本可以将英文 EPUB 电子书翻译为中文，并生成以下四种文件：
- 中英对照 EPUB（原文+译文，段落间有空行）
- 纯中文 EPUB（段落前空两字）
- 中英对照 PDF
- 纯中文 PDF

## 技术特点

- **智能翻译**：调用 DeepSeek API 进行高质量英译中
- **排版保留**：保持原书的排版结构
- **缓存机制**：本地 JSON 缓存，避免重复翻译
- **格式转换**：自动将 EPUB 转换为 PDF
- **批量处理**：支持整本书的翻译和转换

## 环境要求

- Python 3.8+
- 依赖库：ebooklib, requests, beautifulsoup4, lxml
- 外部工具：Calibre（用于 EPUB 到 PDF 转换）

## 安装步骤

1. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

2. **安装 Calibre**：
   - 下载并安装 Calibre：https://calibre-ebook.com/download
   - 确保 `ebook-convert` 工具在系统 PATH 中

3. **配置 API 密钥**：
   - 访问 https://deepseek.com 注册账号并获取 API 密钥
   - 编辑 `config.py` 文件，将 API 密钥替换到 `DEEPSEEK_API_KEY` 变量中

## 使用方法

### 基本用法

```bash
python main.py input_book.epub
```

### 高级选项

```bash
# 指定输出目录
python main.py input_book.epub --output-dir output

# 直接指定 API 密钥（优先级高于 config.py）
python main.py input_book.epub --api-key your_api_key
```

## 输出文件命名

- 输入文件：`example.epub`
- 输出文件：
  - 中英对照 EPUB：`中英双语-example.epub`
  - 纯中文 EPUB：`中文版本-example.epub`
  - 中英对照 PDF：`中英双语-example.pdf`
  - 纯中文 PDF：`中文版本-example.pdf`

## 排版说明

- **中英对照版本**：以段落为单位，原文和译文之间有一个空行
- **纯中文版本**：每个段落前空两字，符合中文排版习惯

## 缓存机制

- 翻译结果会保存在 `translation_cache.json` 文件中
- 缓存基于文本内容的 MD5 哈希，避免重复翻译
- 缓存有效期为 30 天

## 注意事项

1. **API 费用**：DeepSeek API 可能会产生费用，请参考官方定价
2. **速率限制**：请遵守 DeepSeek API 的速率限制
3. **版权问题**：请确保翻译内容的版权合规
4. **大文件处理**：处理大文件时可能需要较长时间和较多内存
5. **网络连接**：需要稳定的网络连接以调用 API

## 故障排除

- **API 错误**：检查 API 密钥是否正确，网络连接是否正常
- **PDF 转换失败**：确保 Calibre 已正确安装，`ebook-convert` 工具在 PATH 中
- **EPUB 解析错误**：确保输入的 EPUB 文件格式正确

## 示例

```bash
# 翻译并转换示例电子书
python main.py sample_book.epub

# 输出结果：
# - 中英双语-sample_book.epub
# - 中文版本-sample_book.epub
# - 中英双语-sample_book.pdf
# - 中文版本-sample_book.pdf
```

## 项目结构

```
ebook-translator/
├── main.py              # 主脚本
├── translator/          # 核心模块
│   ├── __init__.py
│   ├── epub_parser.py   # EPUB 解析
│   ├── deepseek_api.py  # API 调用
│   ├── cache.py         # 缓存管理
│   ├── epub_generator.py # EPUB 生成
│   └── pdf_converter.py # PDF 转换
├── config.py            # 配置文件
├── requirements.txt     # 依赖管理
└── translation_cache.json # 缓存文件
```

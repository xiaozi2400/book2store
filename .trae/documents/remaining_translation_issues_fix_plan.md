# 遗留翻译问题修复方案

## 问题概览

用户检查中文 EPUB 后发现 4 个未翻译问题，分为两类：

| 类别 | 问题 | 严重程度 |
|------|------|----------|
| 整段未翻译 | "With Early Release ebooks..." 长段落 | 高 |
| 整段未翻译 | "Machines Can Think" 引用段落 (blockquote) | 高 |
| 单词未翻译 | "NOTE" 警告标签 | 中 |
| 单词未翻译 | "TIP" 提示标签 | 中 |

---

## 根因分析

### 问题1: "With Early Release ebooks..." 整段未翻译

**现象**：该段落在中文 EPUB 中完全保持英文原文。

**触达路径**：
- 文本位于 `<p>` 标签中，属于块级标签
- `_process_html_content` 的 block_tags 阶段会处理 `<p>` 标签
- 通过 `tag.get_text(strip=True)` 提取文本 → `normalize_text()` 标准化 → 在 `translation_map` 中查找

**根因分析**：
- `epub_parser.py` 的 `normalize_text`：`' '.join(text.split())` → `strip()`
- `epub_generator.py` 的 `normalize_text`：`' '.join(text.split()).strip()`
- 两者逻辑等价，问题不在此
- 关键差异在于**输入文本**：parser 解析原始 EPUB，generator 解析已解压提取的临时文件
- 最可能原因：段落中包含 em-dash `—` (U+2014)、curly apostrophe `'` (U+2019) 等特殊字符，在解压+重读过程中可能因为文件编码声明或 BeautifulSoup 的实体处理行为，导致 `get_text()` 输出与原始 EPUB 解析时存在细微差异，normalize 后的文本不匹配

**待验证**：需要通过 hex dump 确认 parser 提取的文本与 generator 在标签中获取的文本是否逐字节一致。

**修复方案**（按优先级）：

- **方案A（推荐）**：增强 `normalize_text` 函数，增加更激进的标准化
  - 将所有 Unicode 引号/破折号统一替换为 ASCII 等价字符
  - 添加 `.replace('\u2014', '-')` 和 `.replace('\u2018', "'")` 等转换
  - 优点：一次修复，一劳永逸；缺点：影响范围广，需要验证不产生副作用

- **方案B**：在生成器中添加回退匹配逻辑
  - 当精确匹配失败时，尝试 fuzzy 匹配（忽略特殊字符差异）
  - 优点：不影响现有逻辑；缺点：性能略差

- **方案C**：仅在诊断确认差异后，针对性修复该段落
  - 在 `normalize_text` 中添加针对性的字符映射
  - 优点：改动最小；缺点：治标不治本

### 问题2: "Machines Can Think" 引用段落未翻译

**现象**：blockquote 中的英文引用完全保留，仅末尾的作者名 "Edsger Dijkstra" 被部分翻译为中文。

**根因分析**：

查看 [epub_generator.py:L383-L384](file:///d:/project/bookfile_bat/ebook_translator/translator/epub_generator.py#L383-L384) 的 `block_tags` 列表：

```python
block_tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'dt', 'dd',
              'figcaption', 'td', 'th', 'caption']
```

**`blockquote` 不在 `block_tags` 列表中！**

而 [epub_parser.py](file:///d:/project/bookfile_bat/ebook_translator/translator/epub_parser.py) 的 `content_tags` 包含 `blockquote`：
```python
'content_tags': ['p', 'h1', ..., 'blockquote', 'a', ...]
```

这导致：
1. Parser 正确提取了 blockquote 的完整文本（包含引用 + 作者名），并生成翻译
2. Generator 的块级标签阶段**跳过** blockquote
3. blockquote 内部的 `<a>` 标签（作者名链接）在 inline 阶段被处理 → "Eds" → "艾兹格"
4. 但 blockquote 的 `<a>` 标签被处理后，其父元素 blockquote 的文本发生变化（作者名被替换为中文），导致即便后续尝试匹配也已太晚
5. 引用正文 `"The question of whether Machines Can Think..."` 从未被匹配和替换

**修复方案**：

**方案A（推荐）**：将 `blockquote` 加入 `block_tags` 列表

```python
block_tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'dt', 'dd',
              'figcaption', 'td', 'th', 'caption', 'blockquote']
```

- 优点：简单直接，与 parser 逻辑一致
- 风险：blockquote 可能包含嵌套的块级子元素（如 `<p>`），需要确认 `tag.clear()` 行为是否正常

### 问题3 & 4: "NOTE" 和 "TIP" 标签未翻译

**现象**：中文 EPUB 中保留了英文的 "NOTE"、 "TIP" 警告标签文字。

**根因分析**：

查看 [config.py:L235](file:///d:/project/bookfile_bat/ebook_translator/config.py#L235) 中 `EXTRACTION_CONFIG`：
```python
'min_text_length': 5,
```

- "NOTE" = 4 个字符 < 5
- "TIP" = 3 个字符 < 5

在 [epub_parser.py:L136](file:///d:/project/bookfile_bat/ebook_translator/translator/epub_parser.py#L136)：
```python
if not text or len(text) < min_length:
    continue
```

这两个标签文本因为太短而**被 parser 完全跳过**，从未提取翻译，自然不在 `translation_map` 中。

而 `_process_html_content` 的处理阈值是 `len(normalized_text) <= 1`，远低于 5，所以 generator 会尝试处理它们——但找不到翻译。

**修复方案**：

- **方案A**：降低 `min_text_length` 从 5 到 3
  - 优点：简单
  - 缺点：可能提取大量噪音短文本（如 "1."、"a)" 等），增加翻译成本

- **方案B（推荐）**：增加硬编码的警告标签翻译映射
  - 在 `epub_generator.py` 的 `_process_html_content` 开头增加一个固定映射：
    ```python
    ADMONITION_LABELS = {
        'NOTE': '注意',
        'TIP': '提示',
        'WARNING': '警告',
        'CAUTION': '注意',
        'IMPORTANT': '重要',
        'INFO': '信息',
    }
    ```
  - 在块级标签处理循环中，当 en-us 长度在 3-10 之间且无法在 translation_map 中找到时，回退检查此映射
  - 此方案处理 `blockquote` 标签内的引用文本，替换全文内容

- **方案C**：方案B的改进——将映射加入 `translation_map` 构建时
  - 在 `_create_translation_map` 末尾合并固定映射条目
  - 优点：统一处理，无需特殊分支

---

## 文件修改清单

| 文件 | 修改内容 | 对应问题 |
|------|----------|----------|
| `ebook_translator/translator/epub_generator.py` | 1. `block_tags` 增加 `blockquote` | 问题2 |
|  | 2. 添加 `ADMONITION_LABELS` 映射并合并到 `translation_map` | 问题3,4 |
|  | 3. 增强 `normalize_text` 处理 special Unicode 字符 | 问题1 |
| `ebook_translator/translator/epub_parser.py` | 无需修改 | — |
| `ebook_translator/config.py` | 无需修改（保留 `min_text_length=5`） | — |

---

## 验证步骤

1. 修改代码
2. 删除 `translation_cache.json`
3. 重新执行翻译：`python main.py "E:\ebooks\input\Building AI Agent Platforms...epub" -o "D:\project\bookfile_bat\output\Building AI Agent Platforms..."`
4. 解压中文 EPUB 验证：
   - "With Early Release" 段落的 `data-original` 属性是否存在
   - blockquote 内容是否全部替换为中文
   - NOTE/TIP 标签是否替换为中文
5. 运行 `verify_translation_fix.py` 确认翻译率接近 100%

---

## 风险评估

- **blockquote 加入 block_tags**：低风险。需要确保当 blockquote 包含嵌套 `<p>` 时，`tag.clear()` 不会破坏结构。如果出现问题，可以改用在匹配成功后保留结构、仅替换文本内容。
- **增强 normalize_text**：中风险。Unicode 字符替换可能影响其他正常内容。建议仅在匹配失败时尝试增强标准化。
- **ADMONITION_LABELS 映射**：低风险。这些是公认的标准翻译，不会产生歧义。

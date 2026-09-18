# 修复终端进度显示和 XML 警告

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 1) 翻译进度实时显示在终端 2) 消除 BeautifulSoup XMLParsedAsHTMLWarning 警告

**架构：** 
- 翻译进度用 `logger.info` 写日志，但 StreamHandler 仅输出 WARNING 及以上级别，导致进度被静默。改用 `print()` 输出到终端，同时保留 `logger.info` 写日志文件。
- `BeautifulSoup(content, 'lxml')` 解析 XHTML 文件时触发 Python 警告，在模块顶部添加 `warnings.filterwarnings` 过滤该特定警告。

**技术栈：** Python, BeautifulSoup, logging

---

### 任务 1：翻译进度实时显示在终端

**文件：**
- 修改：`d:\project\bookfile_bat\ebook_translator\translator\translator.py:447-450`

- [ ] **步骤 1.1：将进度输出从 logger.info 改为 print + logger.info**

当前代码：
```python
completed += len(batch)
progress = completed / len(paragraphs) * 100
logger.info(f"  进度: {completed}/{len(paragraphs)} ({progress:.1f}%)")
```

改为：
```python
completed += len(batch)
progress = completed / len(paragraphs) * 100
# print 直接输出到终端（不受日志级别限制），同时保留日志文件记录
print(f"  翻译进度: {completed}/{len(paragraphs)} ({progress:.1f}%)")
logger.info(f"  进度: {completed}/{len(paragraphs)} ({progress:.1f}%)")
```

- [ ] **步骤 1.2：验证修改**

运行 pytest 检查是否破坏了任何测试：
```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -m pytest tests/test_translation_pipeline.py tests/test_translator_stats.py -v
```
预期：所有测试通过。

### 任务 2：消除 BeautifulSoup XMLParsedAsHTMLWarning

**文件：**
- 修改：`d:\project\bookfile_bat\ebook_translator\translator\epub_parser.py:1-7`

- [ ] **步骤 2.1：在 epub_parser.py 顶部添加 warning 过滤**

在 `epub_parser.py` 现有 import 块之后、`logger = logging.getLogger(__name__)` 之前添加：

```python
import warnings
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
```

完整顶部应变为：
```python
import os
import re
import logging
import warnings
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from config import TIER_CONFIG, EXTRACTION_CONFIG

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

logger = logging.getLogger(__name__)
```

- [ ] **步骤 2.2：验证修改**

运行 EPUB 解析测试：
```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -m pytest tests/test_translation_pipeline.py -v
```
预期：测试通过，终端无 XMLParsedAsHTMLWarning。

### 任务 3：提交变更

- [ ] **步骤 3.1：提交 git**

```powershell
Set-Location d:\project\bookfile_bat
$env:GIT_PAGER = "cat"
git add ebook_translator/translator/translator.py ebook_translator/translator/epub_parser.py
git commit -m "$(cat <<'EOF'
fix: 终端显示翻译实时进度，消除 XML 解析警告

- 翻译进度改用 print() 确保终端实时可见，同时保留 logger.info 写日志文件
- 过滤 BeautifulSoup解析XHTML时的 XMLParsedAsHTMLWarning 警告
EOF
)"
```


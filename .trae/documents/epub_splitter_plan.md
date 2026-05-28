# EPUB 拆分工具 - 实施计划

## 1. 目标

开发一个独立工具，将 `E:\ebooks\test-input` 目录中的 EPUB 文件拆分为 10 个较小的 EPUB 文件。

## 2. 原则

遵循"拼好码"原则：
- **使用成熟方案**：`ebooklib`（EPUB读写）、`BeautifulSoup`（HTML解析）、`pytest`（测试）、`typer`（CLI）
- **只编写胶水代码和业务编排**：业务逻辑是"如何将 EPUB 内容均匀分配到 N 个文件中"
- **先测试，再代码**：先写测试用例，再实现功能，最后验证

## 3. 技术选型

| 需求 | 方案 | 说明 |
|------|------|------|
| EPUB 读写 | `ebooklib` (v0.20) | 成熟、稳定，已安装在项目中 |
| HTML 解析 | `BeautifulSoup4` + `lxml` | 已安装在项目中 |
| 测试框架 | `pytest` (v9.0) | 已安装在项目中 |
| CLI 框架 | `typer` | 项目中已有使用 |
| 文件操作 | `zipfile`, `shutil`, `tempfile` | Python 标准库 |

## 4. 拆分策略

按 **OPF manifest 中的文档条目（ITEM_DOCUMENT）** 进行拆分：

1. 读取 EPUB，获取所有 `ITEM_DOCUMENT` 类型的内容项
2. 将内容项均匀分配到 10 个组中（保持章节完整）
3. 为每组生成独立的 EPUB 文件：
   - 复制原始元数据（标题、作者、封面等）
   - 只包含该组对应的内容项
   - 重新生成 OPF 清单和 NCX/TOC 导航
   - 保留所有样式、图片等资源
   - 输出文件名格式：`{原书名}_part01.epub` ~ `{原书名}_part10.epub`

## 5. 目录结构

```
ebook_splitter/
    __init__.py              # 空文件
    epub_splitter.py         # 核心拆分逻辑 (EPUBSplitter 类)
    cli.py                   # CLI 入口
    tests/
        __init__.py          # 空文件
        test_epub_splitter.py  # 测试用例（直接使用 E:\ebooks\test-input 中的真实 EPUB）
```

## 6. 实施步骤

### Step 1: 创建目录结构
- 创建 `ebook_splitter/` 和 `ebook_splitter/tests/` 目录及 `__init__.py`

### Step 2: 编写测试用例
测试文件 `ebook_splitter/tests/test_epub_splitter.py`，直接使用 `E:\ebooks\test-input` 中的真实 EPUB 文件测试：

1. **test_split_into_10_parts** - 验证拆分后得到 10 个 EPUB 文件
2. **test_each_part_is_valid_epub** - 验证每个部分都是有效的 EPUB（能用 ebooklib 正常读取）
3. **test_all_parts_sum_to_original** - 验证所有部分的文档项数之和等于原文件
4. **test_part_content_not_empty** - 验证每个部分都有内容
5. **test_parts_have_correct_metadata** - 验证各部分保留了原文件的元数据（标题、作者）
6. **test_parts_have_unique_filenames** - 验证输出文件名格式正确且不重复
7. **test_balance_distribution** - 验证内容分配相对均匀（各部分文档项数相差不大）
8. **test_edge_case_small_epub** - 测试只有少量文档项的 EPUB（少于 10 项）
9. **test_edge_case_single_item** - 测试只有 1 个文档项的 EPUB
10. **test_preserves_resources** - 验证资源文件（图片、CSS）被正确保留

### Step 3: 实现核心拆分逻辑 `ebook_splitter/epub_splitter.py`

`EPUBSplitter` 类：

```python
class EPUBSplitter:
    def __init__(self, epub_path: str)
    def analyze(self) -> dict          # 分析 EPUB 结构
    def split(self, output_dir: str, num_parts: int = 10) -> list[str]
```

**`split()` 方法流程：**
1. 用 `ebooklib.epub.read_epub()` 读取原 EPUB
2. 过滤出 `ITEM_DOCUMENT` 类型的内容项
3. 将文档项均匀分配到 N 组（按顺序平分）
4. 对于每组：
   a. 创建新的 `epub.EpubBook()` 对象
   b. 复制元数据（标题、作者、语言等）
   c. 复制封面图片
   d. 从原 EPUB 复制该组分配到的文档项内容
   e. 复制所有资源文件（图片、CSS、字体等）
   f. 重新生成目录（Table of Contents）
   g. 添加 spine（阅读顺序）
   h. 写入 EPUB 文件
5. 返回所有输出文件路径

### Step 4: 实现 CLI 入口 `ebook_splitter/cli.py`

### Step 5: 运行测试验证
- 运行 `pytest ebook_splitter/tests/ -v` 确认所有测试通过
- 验证方法：打开生成的 EPUB 文件，检查内容是否完整、格式是否正常

## 7. 关键设计考虑

### 内容分配算法
- **首选：按文档项数量分配** - 简单可靠，将文档项列表按顺序分到 N 组
  - 例如 25 个文档项分 10 组：第 1-5 组各 3 项，第 6-10 组各 2 项

### 导航（TOC）处理
- 每个拆分后的 EPUB 需要重新生成 TOC
- 只包含该部分的文档项对应的 TOC 条目
- 保留原 TOC 的层级结构

### 资源文件处理
- 图片、CSS、字体等资源文件（非 ITEM_DOCUMENT 类型）需要复制到每个分卷
- 确保路径引用正确

### 元数据
- 标题添加分卷标识：`原书名 - 第1卷/10`

## 8. 验证标准

1. ✅ 所有 pytest 测试通过
2. ✅ 拆分后的所有 10 个 EPUB 文件能在电子书阅读器中正常打开
3. ✅ 每个 EPUB 内容可读，格式正常
4. ✅ 原始文件不被修改
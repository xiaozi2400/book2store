# 流水线优化设计文档

## 概述

对自动化流水线进行三项优化：质量报告终端统一输出、输入文件名规范化、处理完成后文件转移。

---

## 1. 质量报告终端统一输出

### 现状
- `translation_processor.py` 的 `_run_quality_check()` 将 JSON 报告写入 `output/<书名>/质量报告-<书名>.json`
- 同时存入数据库 `books.quality_report` 字段
- 终端只输出 Token 消耗汇总，无质量报告展示

### 改动

#### translation_processor.py
- `_run_quality_check()` 不再写 JSON 文件到磁盘
- 仅保留数据库写入：`db.update_book_quality_report(book_id, report.to_json())`
- 方法签名和日志输出保持不变

#### main.py
- `auto()` 命令末尾（所有书籍处理完后），从数据库读取质量报告
- 用 Rich 表格在终端展示汇总：
  - 书名 | 总分 | 等级 | 主要问题（最多3条）
- `process()` 命令末尾同理展示单本质量报告
- 不展示各维度详细评分，保持简洁

### 数据流

```
翻译完成
  → QualityChecker.check() → QualityReport
  → DB: update_book_quality_report()
  → (不再写文件)
  → auto/process 命令末尾 → 从 DB 读取 → Rich 表格输出
```

---

## 2. 输入文件名规范化

### 现状
- `directory_scanner.py` 的 `_fix_filenames()` 只处理尾随空格
- 存在长文件名（>60字符）和含 `--` 的文件名

### 改动

在 `_fix_filenames()` 中追加规范化逻辑（在空格处理之后）：

```
处理规则（按顺序，一步到位）：
1. 完整 stem 去除首尾空格
2. 如果包含 "--"，取 "--" 之前的部分（去除首尾空格）
3. 如果结果 > 60 字符，截取前 60 字符（去除首尾空格）
4. 拼回 .epub 扩展名，不一致则重命名
```

#### 示例

| 原文件名 | 处理后 |
|----------|--------|
| `Long-Book-Title--Some-Extra-Description.epub` | `Long-Book-Title.epub` |
| `A very long book title with many words in it and keeps going more than sixty characters.epub` | `A very long book title with many words in it and keeps going m.epub` |
| `A very long book title--with-extra-desc goes way beyond sixty characters total.epub` | `A very long book title.epub` |

### 影响范围
- 仅限于扫描阶段的 `_fix_filenames()`，不影响后续处理流程
- 数据库中 `filename` 字段为规范化后的文件名

---

## 3. 处理完成后转移文件

### 现状
- 文件处理完成后仍留在 `input_dir`
- 下次 `scan` / `auto` 时会因已存在记录跳过，但文件仍占据空间

### 改动

在 `auto()` 命令末尾（所有书籍处理完后）：

```python
processed_dir = Path(config.input_dir) / "已处理"
processed_dir.mkdir(exist_ok=True)

for epub_file in Path(config.input_dir).glob("*.epub"):
    shutil.move(str(epub_file), str(processed_dir / epub_file.name))
```

### 注意事项
- 仅移动 `.epub` 文件，不移动其他文件
- 目录名为中文"已处理"，符合中文用户习惯
- 创建目录时不受已存在影响（`exist_ok=True`）
- 移动在全部处理完成后执行，避免中断后文件丢失

---

## 4. 测试方案

### 4.1 质量报告终端输出测试

创建测试脚本 `test_quality_report.py`，验证以下场景：

| 测试项 | 方法 | 预期结果 |
|--------|------|----------|
| JSON 文件不再写入 | 创建临时输出目录，运行 `auto` 后检查 | `output_dir` 下无 `质量报告-*.json` 文件 |
| 数据库仍保存报告 | 运行后查询 `db.get_book_quality_report()` | 返回非空 JSON 字符串 |
| 终端表格格式正确 | 捕获 `console.print` 输出 | 包含"质量报告"、"书名"、"总分"、"等级"等字段 |

### 4.2 文件名规范化测试

创建测试脚本 `test_filename_normalization.py`，直接调用 `_fix_filenames()`：

创建临时 input 目录，放入以下文件后运行规范化：

| 测试场景 | 原始文件名 | 预期规范化结果 |
|----------|-----------|---------------|
| 含 `--` | `Book-Title--Some-Extra-Description.epub` | `Book-Title.epub` |
| 超长无 `--` | `A very long book title with many words in it and keeps going more than sixty characters.epub` | 截断至60字符 |
| 含 `--` 且前面超60字符 | `This is a really long book title that goes well beyond sixty characters--and extra.epub` | `--` 前部分截断60字符 |
| `--` 后有空格 | `Title  --  Extra.epub` | `Title.epub` |
| 正常文件名 | `Normal Book.epub` | 不变 |
| 仅尾随空格 | `Trailing Space .epub` | `Trailing Space.epub`（现有逻辑） |

### 4.3 文件转移测试

创建测试脚本 `test_file_moving.py`，验证 `auto()` 末尾的文件移动逻辑：

| 测试项 | 方法 | 预期结果 |
|--------|------|----------|
| 移动 EPUB 文件 | 创建临时 input 目录放 3 个 `.epub`，运行移动逻辑 | 3 个文件在 `已处理/` 目录下 |
| 不移动非 EPUB | 在 input 目录放 `.pdf`、`.txt` 各一个 | 这些文件不被移动 |
| 目录不存在时自动创建 | 删除 `已处理/` 目录后运行 | 目录自动创建成功 |
| 重复运行不报错 | 再次运行移动逻辑 | 第二次不移动（无可移动文件），无报错 |

---

## 改动文件清单

| 文件 | 改动内容 |
|------|----------|
| `automation/directory_scanner.py` | `_fix_filenames()` 增加长度截断和 `--` 拆分 |
| `automation/translation_processor.py` | `_run_quality_check()` 移除 JSON 文件写入 |
| `automation/main.py` | `auto()` 末尾增加质量报告终端展示 + 文件转移到"已处理"；`process()` 末尾增加质量报告展示 |
| `test_quality_report.py` | 新增测试：质量报告终端输出 |
| `test_filename_normalization.py` | 新增测试：文件名规范化 |
| `test_file_moving.py` | 新增测试：文件转移 |
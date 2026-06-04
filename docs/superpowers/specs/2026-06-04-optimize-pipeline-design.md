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

## 改动文件清单

| 文件 | 改动内容 |
|------|----------|
| `automation/directory_scanner.py` | `_fix_filenames()` 增加长度截断和 `--` 拆分 |
| `automation/translation_processor.py` | `_run_quality_check()` 移除 JSON 文件写入 |
| `automation/main.py` | `auto()` 末尾增加质量报告终端展示 + 文件转移到"已处理"；`process()` 末尾增加质量报告展示 |
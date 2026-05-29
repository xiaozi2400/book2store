# 闲鱼文案提示词优化设计

## 背景

当前闲鱼文案生成流程中，AI 提示词要求模型「联网搜索」获取书籍信息来生成销售文案。这导致两个问题：

1. AI 网络搜索不稳定，可能搜索失败或返回错误信息
2. 文案内容与书籍实际内容脱节，出现虚假描述

实际项目中，书籍的**精简版摘要**已经在文案生成之前由 `ContentSummarizer` 生成完毕（包含核心观点、章节摘要、金句、适用人群等），数据完全可用。

## 目标

1. 将闲鱼文案生成从「联网搜索」改为「基于书籍摘要」
2. 将摘要文本持久化存入数据库，供文案生成使用
3. 保持文案输出格式不变（爆款标题、作者简介、一句话总结等模块）
4. 零额外 AI 调用成本（摘要已生成，仅存储和传递）

## 改动范围

### 1. 数据库 — Book 模型新增字段

**文件**: `automation/models.py`

在 `Book` 表中新增：

| 字段名 | 类型 | 说明 |
|-------|------|------|
| `summary_text` | `Text` | 精简版摘要原始文本，可为 NULL |

### 2. ContentSummarizer — 保存摘要文本

**文件**: `automation/content_summarizer.py`

在 `generate()` 方法中，AI 生成摘要内容后（`_generate_summary()` 返回后），新增以下步骤：

- 调用 `_format_summary_to_text()` 将摘要字典格式化为结构化纯文本
- 调用 `db.update_book_summary(book_id, summary_text)` 存入数据库

### 3. DatabaseManager — 新增方法

**文件**: `automation/database.py`

新增 `update_book_summary(book_id, summary_text)` 方法：

```python
def update_book_summary(self, book_id: str, summary_text: str):
    """保存摘要文本到书籍记录"""
    with self.get_session() as session:
        book = session.query(Book).filter_by(book_id=book_id).first()
        if book:
            book.summary_text = summary_text
            session.commit()
```

### 4. config.yaml — 修改闲鱼提示词

将旧的含「联网搜索」提示词替换为基于摘要的版本。

**关键变化**：
- 删除「Step 1: Auto Search」整个步骤
- 在提示词头部嵌入 `{summary}` 占位符
- 文案依据从「搜索到的真实资料」改为「以上摘要内容」
- 其余输出格式（标题、作者简介、一句话总结等模块）保持不变

### 5. AIClient — 传递摘要参数

**文件**: `automation/ai_client.py`

`generate_xianyu_listing(book_info)` 中，从 `book_info` 读取 `summary` 字段，填充到提示词模板的 `{summary}` 占位符。

### 6. AICopywriter — 透传摘要

**文件**: `automation/ai_copywriter.py`

`generate(title, author, summary)` 新增 `summary` 参数，将其放入 `book_info` 字典后传给 AI client。

### 7. main.py — 从数据库读取摘要

**文件**: `automation/main.py`

在 `process()`、`auto()`、`test()` 三个命令的文案生成步骤中，从数据库读取 `book.summary_text` 传入 `AICopywriter.generate()`。

## 数据流

```
ContentSummarizer.generate()
  ├── _generate_summary()        → 返回摘要字典
  ├── _format_summary_to_text()  → 转为纯文本
  ├── db.update_book_summary()   → 存入 books.summary_text
  └── _create_pdf()              → 生成 PDF（已有）

...（后续步骤）...

main.py process/auto/test
  ├── db.get_book(book_id)               → 读取 book.summary_text
  ├── AICopywriter.generate(summary=...) → 传入摘要
  │   └── ai_client.generate_xianyu_listing(book_info)
  │       └── prompt_template.format(summary=...) → 填充提示词
  └── AI 生成文案（基于摘要，不联网）
```

## 影响范围

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `automation/models.py` | 新增字段 | Book.summary_text |
| `automation/database.py` | 新增方法 | update_book_summary() |
| `automation/content_summarizer.py` | 新增逻辑 | 摘要生成后保存文本 |
| `automation/ai_client.py` | 修改参数 | 传递 summary 到提示词 |
| `automation/ai_copywriter.py` | 修改接口 | generate() 新增 summary 参数 |
| `automation/main.py` | 修改调用 | 从 DB 读取摘要传入文案 |
| `config.yaml` | 修改提示词 | 联网搜索 → 基于摘要 |

## 测试策略

| 测试 | 验证内容 |
|------|---------|
| `test_update_book_summary` | DB 方法能正确存储和读取 summary_text |
| `test_summary_saved_after_generate` | ContentSummarizer 生成后自动保存摘要 |
| `test_xianyu_prompt_uses_summary` | 提示词中 `{summary}` 被正确填充 |
| `test_copywriting_with_summary` | 完整流程：有摘要时正确生成文案 |
| `test_copywriting_without_summary` | 无摘要时优雅降级（空字符串） |

## 降级策略

如果书籍没有摘要（如老数据或摘要生成失败），`summary` 传入空字符串，提示词中 `{summary}` 位置显示「暂无摘要信息」。AI 将仅凭书名和作者生成文案（效果不如有摘要，但不会报错中断）。

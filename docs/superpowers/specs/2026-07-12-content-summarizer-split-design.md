# 内容精简器重构设计方案

## 现状分析

`content_summarizer.py` (2097行/74KB) 混合了多个职责：

| 职责 | 行数 | 问题 |
|------|------|------|
| 字体注册 | 16-69 | 应独立 |
| 封面提取 | 91-216 | 应独立 |
| 章节提取 | 351-506 | 应独立 |
| AI摘要生成 | 508-572 | 应独立 |
| PDF生成 (5种方式) | 647-2086 | 应拆分 |
| 主流程编排 | 218-321 | 保留在主编排器 |

## 目标拆分结构

```
automation/summarizer/
├── __init__.py           # 导出 ContentSummarizer, generate_summary
├── fonts.py              # 字体注册 (原 16-69 行)
├── cover_extractor.py    # 封面提取 (原 91-216 行)
├── chapter_extractor.py   # 章节提取 (原 351-506 行)
├── ai_generator.py        # AI摘要生成 (原 508-572 行)
├── pdf_generator.py       # PDF生成 (原 647-2086 行，5种方式)
└── content_summarizer.py  # 主编排器 (精简后 ~250行)
```

## 拆分原则

1. **每个模块独立可测试**
2. **保持向后兼容** - 导出接口不变
3. **减少循环依赖** - 字体模块不依赖其他业务模块
4. **PDF生成器内部不再拆分** - 5种方式都是PDF生成器的内部实现

## 实施步骤

1. 创建 `automation/summarizer/` 目录
2. 创建 `fonts.py` - 字体注册
3. 创建 `cover_extractor.py` - 封面提取
4. 创建 `chapter_extractor.py` - 章节提取
5. 创建 `ai_generator.py` - AI摘要生成
6. 创建 `pdf_generator.py` - PDF生成（包含所有5种方式）
7. 重构 `content_summarizer.py` - 仅保留主编排逻辑
8. 添加 `__init__.py` 导出
9. 运行测试确保无回归
"""
内容精简器 - 生成书籍核心内容精简版PDF

此文件已重构，请使用 automation.summarizer 模块：
    from automation.summarizer import ContentSummarizer, generate_summary
"""
# 向后兼容：直接从 summarizer 子模块导入
from automation.summarizer import ContentSummarizer, generate_summary

__all__ = ['ContentSummarizer', 'generate_summary']

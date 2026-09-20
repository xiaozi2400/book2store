"""
summarizer 包 - 内容精简器子模块
"""

from .content_summarizer import ContentSummarizer, generate_summary
from .suitability_evaluator import SuitabilityEvaluator, SuitabilityResult
from .template_generator import TemplateGenerator, detect_and_generate_prompt

__all__ = [
    "ContentSummarizer",
    "generate_summary",
    "SuitabilityEvaluator",
    "SuitabilityResult",
    "TemplateGenerator",
    "detect_and_generate_prompt",
]

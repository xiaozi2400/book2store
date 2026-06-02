"""翻译质量检查模块"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from .config import config
from .utils import logger


# ============================================================
# 数据模型
# ============================================================

@dataclass
class DimensionResult:
    """单维度检查结果"""
    score: float
    issues: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityReport:
    """质量检查报告"""
    book_title: str
    overall_score: float
    overall_grade: str
    dimensions: Dict[str, DimensionResult]
    summary: str
    recommendation: str

    def to_dict(self) -> Dict:
        result = {
            "book_title": self.book_title,
            "overall_score": self.overall_score,
            "overall_grade": self.overall_grade,
            "summary": self.summary,
            "recommendation": self.recommendation,
            "dimensions": {}
        }
        for dim_name, dim_result in self.dimensions.items():
            result["dimensions"][dim_name] = asdict(dim_result)
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ============================================================
# 维度 7：翻译完整性检查
# ============================================================

class CompletenessChecker:
    """检查翻译完整性——所有源段落是否都已成功翻译，无遗漏"""

    def check(self, cache_data: Dict, source_paragraphs: List[str]) -> Dict:
        if not source_paragraphs:
            return {
                "score": 100,
                "source_paragraphs": 0,
                "translated_paragraphs": 0,
                "missing_count": 0,
                "empty_paragraphs": 0,
                "issues": []
            }

        translated_count = 0
        empty_count = 0
        missing_paragraphs = []

        for para in source_paragraphs:
            found = False
            for cache_key, cache_entry in cache_data.items():
                if cache_entry.get("source", "").strip() == para.strip():
                    found = True
                    translated_text = cache_entry.get("translated", "").strip()
                    if translated_text:
                        translated_count += 1
                    else:
                        empty_count += 1
                    break
            if not found:
                missing_paragraphs.append(para[:50])

        total = len(source_paragraphs)
        missing_count = total - translated_count - empty_count
        ratio = (translated_count / total) if total > 0 else 1.0
        score = round(ratio * 100, 1)

        issues = []
        if missing_count > 0:
            issues.append(f"有 {missing_count} 个段落未翻译（共 {total} 段）")
        if empty_count > 0:
            issues.append(f"有 {empty_count} 个段落译文为空")

        return {
            "score": score,
            "source_paragraphs": total,
            "translated_paragraphs": translated_count,
            "missing_count": missing_count,
            "empty_paragraphs": empty_count,
            "issues": issues
        }
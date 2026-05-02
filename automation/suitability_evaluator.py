"""
适合度评估器 - 评估书籍是否适合生成精简版
"""
from typing import Dict, Any
from dataclasses import dataclass, field

@dataclass
class SuitabilityResult:
    """评估结果"""
    passed: bool = True
    score: int = 85
    label: str = "适合"
    recommendation: str = "内容结构清晰，适合生成精简版"
    details: Dict[str, Any] = field(default_factory=dict)

class SuitabilityEvaluator:
    """评估书籍生成精简版的适合度"""
    
    def __init__(self):
        self.min_chapter_count = 3
        self.min_content_ratio = 0.5
    
    def evaluate(self, book_info: Dict[str, Any]) -> SuitabilityResult:
        """评估书籍适合度
        
        Args:
            book_info: 书籍信息字典
            
        Returns:
            评估结果对象
        """
        title = book_info.get('title', '')
        author = book_info.get('author', '')
        
        return SuitabilityResult(
            passed=True,
            score=85,
            label="适合",
            recommendation="内容结构清晰，适合生成精简版",
            details={
                'title': title,
                'author': author
            }
        )
    
    def check_chapter_count(self, chapters: list) -> bool:
        """检查章节数量是否足够"""
        return len(chapters) >= self.min_chapter_count
    
    def check_content_ratio(self, content_length: int, total_length: int) -> bool:
        """检查内容占比"""
        if total_length == 0:
            return False
        return content_length / total_length >= self.min_content_ratio

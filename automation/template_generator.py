"""
模板生成器 - 生成书籍精简版提示词模板
"""
import os
import sys
from typing import Dict, Any, Optional
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .config import config

@dataclass
class TemplateResult:
    """模板结果"""
    template_name: str
    prompt_for_ai: str
    book_type: str

class TemplateGenerator:
    """生成精简版提示词模板"""
    
    def __init__(self):
        self.default_template = self._get_default_template()
    
    def _get_default_template(self) -> str:
        # 从配置文件读取提示词
        summarizer_cfg = config.summarizer_config()
        if 'prompt' in summarizer_cfg and summarizer_cfg['prompt']:
            return summarizer_cfg['prompt']
        
        raise ValueError("config.yaml 中没有配置 summarizer.prompt，无法生成精简版！")
    
    def detect_book_type(self, book_info: Dict[str, Any], details: Optional[Dict] = None) -> str:
        """检测书籍类型"""
        title = book_info.get('title', '').lower()
        
        if any(kw in title for kw in ['python', '编程', '代码', '程序']):
            return '技术编程'
        elif any(kw in title for kw in ['商业', '创业', '管理']):
            return '商业管理'
        elif any(kw in title for kw in ['小说', '文学', '故事']):
            return '小说文学'
        else:
            return '通用'
    
    def detect_and_generate_prompt(self, book_info: Dict[str, Any], details: Optional[Dict] = None) -> TemplateResult:
        """生成提示词"""
        title = book_info.get('title', '未知书籍')
        author = book_info.get('author', '未知作者')
        book_type = self.detect_book_type(book_info, details)
        
        # 不要在这里格式化模板，保持原始占位符让 _build_summary_prompt 统一处理
        # 只返回原始模板字符串
        return TemplateResult(
            template_name=f"{book_type}_template",
            prompt_for_ai=self.default_template,
            book_type=book_type
        )

def detect_and_generate_prompt(book_info: Dict[str, Any], details: Optional[Dict] = None) -> TemplateResult:
    """生成提示词（便捷函数）"""
    generator = TemplateGenerator()
    return generator.detect_and_generate_prompt(book_info, details)

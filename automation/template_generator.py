"""
模板生成器 - 生成书籍精简版提示词模板
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass

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
        return """请分析以下书籍内容，提取核心要点，生成精简版本。
        
书籍信息：
- 书名：{title}
- 作者：{author}

内容：
{content}

请按以下格式生成精简版：
1. 核心主题（100字以内）
2. 主要章节要点（每个章节50字以内）
3. 关键结论（100字以内）
4. 一句话总结（30字以内）
"""
    
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
        
        prompt = self.default_template.format(
            title=title,
            author=author,
            content='{content}'
        )
        
        return TemplateResult(
            template_name=f"{book_type}_template",
            prompt_for_ai=prompt,
            book_type=book_type
        )

def detect_and_generate_prompt(book_info: Dict[str, Any], details: Optional[Dict] = None) -> TemplateResult:
    """生成提示词（便捷函数）"""
    generator = TemplateGenerator()
    return generator.detect_and_generate_prompt(book_info, details)

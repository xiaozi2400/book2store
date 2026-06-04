import os
import re
import logging
import warnings
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from config import TIER_CONFIG, EXTRACTION_CONFIG

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

logger = logging.getLogger(__name__)

def normalize_text(text):
    """标准化文本：去除多余空格，保留换行"""
    if not text:
        return ""
    # 替换多个连续空格为单个空格
    text = ' '.join(text.split())
    return text.strip()

def get_text_tier(text):
    """判断文本属于哪个分层"""
    text = text.strip()
    text_len = len(text)
    
    # Tier 1: 短文本且可重复
    tier1_config = TIER_CONFIG['tier1_short_repeatable']
    if text_len <= tier1_config['max_length']:
        for pattern in tier1_config['patterns']:
            if re.match(pattern, text, re.IGNORECASE):
                return 'tier1_short_repeatable'
    
    # Tier 3: 长文本
    tier3_config = TIER_CONFIG['tier3_long_complex']
    if text_len >= tier3_config['min_length']:
        return 'tier3_long_complex'
    
    # Tier 2: 普通文本
    tier2_config = TIER_CONFIG['tier2_normal']
    if tier2_config['min_length'] <= text_len <= tier2_config['max_length']:
        return 'tier2_normal'
    
    # 默认归为 tier2
    return 'tier2_normal'

def should_exclude_tag(tag):
    """判断标签是否应该被排除"""
    config = EXTRACTION_CONFIG
    
    # 检查标签名
    if tag.name in config['exclude_tags']:
        return True
    
    # 检查 class 和 id
    tag_classes = tag.get('class', [])
    tag_id = tag.get('id', '')
    
    for pattern in config['exclude_patterns']:
        # 检查 class
        for cls in tag_classes:
            if re.search(pattern, str(cls), re.IGNORECASE):
                return True
        # 检查 id
        if re.search(pattern, str(tag_id), re.IGNORECASE):
            return True
    
    return False

def has_block_level_children(tag):
    """检查标签是否包含块级子元素"""
    block_tags = ['div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                  'li', 'blockquote', 'pre', 'table']
    return bool(tag.find(block_tags))

class EPUBParser:
    """EPUB 解析器 - 智能分层版本"""
    
    def __init__(self, epub_path):
        """初始化解析器"""
        self.epub_path = epub_path
        self.book = None
        self.content_items = []
        self.path = epub_path
        self.extraction_stats = {
            'total_tags': 0,
            'excluded_tags': 0,
            'duplicates': 0,
            'by_tier': {'tier1_short_repeatable': 0, 'tier2_normal': 0, 'tier3_long_complex': 0}
        }
    
    def parse(self):
        """解析 EPUB 文件"""
        try:
            self.book = epub.read_epub(self.epub_path)
            self._extract_content_items()
            return True
        except Exception as e:
            logger.error(f"解析 EPUB 文件时出错: {e}")
            return False
    
    def _extract_content_items(self):
        """提取 EPUB 中的内容项"""
        for item in self.book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                self.content_items.append(item)
    
    def get_paragraphs(self, item):
        """从内容项中提取段落 - 智能分层版本"""
        try:
            content = item.get_content().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(content, 'lxml')
            paragraphs = []
            
            # 用于 tier1 去重
            tier1_texts = {}  # text -> paragraph_id
            
            item_id = item.get_name().replace('/', '_').replace('\\', '_')
            global_idx = 0
            
            content_tags = EXTRACTION_CONFIG['content_tags']
            min_length = EXTRACTION_CONFIG['min_text_length']
            
            for tag_name in content_tags:
                for tag in soup.find_all(tag_name):
                    self.extraction_stats['total_tags'] += 1
                    
                    # 排除导航、页眉页脚等
                    if should_exclude_tag(tag):
                        self.extraction_stats['excluded_tags'] += 1
                        continue
                    
                    # 排除包含块级子元素的标签（避免重复），但提取其中裸文本节点
                    if has_block_level_children(tag):
                        from bs4 import NavigableString
                        for child in tag.children:
                            if isinstance(child, NavigableString):
                                child_text = str(child).strip()
                                child_text = normalize_text(child_text)
                                if child_text and len(child_text) >= min_length:
                                    tier = get_text_tier(child_text)
                                    self.extraction_stats['by_tier'][tier] += 1
                                    para_id = f"{item_id}_{global_idx}"
                                    global_idx += 1
                                    import hashlib
                                    trans_id = hashlib.md5(f"{item_id}_{child_text}".encode('utf-8')).hexdigest()[:12]
                                    is_duplicate = False
                                    original_id = None
                                    if tier == 'tier1_short_repeatable' and TIER_CONFIG[tier]['deduplicate']:
                                        if child_text in tier1_texts:
                                            is_duplicate = True
                                            original_id = tier1_texts[child_text]
                                            self.extraction_stats['duplicates'] += 1
                                        else:
                                            tier1_texts[child_text] = para_id
                                    paragraphs.append({
                                        'id': para_id,
                                        'trans_id': trans_id,
                                        'text': child_text,
                                        'html': child_text,
                                        'tag': tag_name,
                                        'tier': tier,
                                        'is_duplicate': is_duplicate,
                                        'original_id': original_id,
                                        'source_file': item.get_name()
                                    })
                        continue
                    
                    # 获取文本
                    text = tag.get_text(strip=True)
                    text = normalize_text(text)
                    
                    # 过滤太短文本
                    if not text or len(text) < min_length:
                        continue
                    
                    # 判断分层
                    tier = get_text_tier(text)
                    self.extraction_stats['by_tier'][tier] += 1
                    
                    # 生成唯一 ID
                    para_id = f"{item_id}_{global_idx}"
                    global_idx += 1

                    # 生成翻译用唯一标识（基于文本内容的hash）
                    import hashlib
                    trans_id = hashlib.md5(f"{item_id}_{text}".encode('utf-8')).hexdigest()[:12]
                    
                    # Tier 1 去重处理
                    is_duplicate = False
                    original_id = None
                    
                    if tier == 'tier1_short_repeatable' and TIER_CONFIG[tier]['deduplicate']:
                        if text in tier1_texts:
                            is_duplicate = True
                            original_id = tier1_texts[text]
                            self.extraction_stats['duplicates'] += 1
                        else:
                            tier1_texts[text] = para_id
                    
                    paragraphs.append({
                        'id': para_id,
                        'trans_id': trans_id,
                        'text': text,
                        'html': str(tag),
                        'tag': tag_name,
                        'tier': tier,
                        'is_duplicate': is_duplicate,
                        'original_id': original_id,
                        'source_file': item.get_name()
                    })
            
            return paragraphs
        except Exception as e:
            logger.warning(f"提取段落时出错: {e}")
            return []
    
    def get_content_items(self):
        """获取所有内容项"""
        return self.content_items
    
    def get_book(self):
        """获取解析后的书籍对象"""
        return self.book
    
    def get_extraction_stats(self):
        """获取提取统计信息"""
        return self.extraction_stats
    
    def print_extraction_report(self):
        """打印提取报告"""
        stats = self.extraction_stats
        logger.info("=== EPUB 提取报告 ===")
        logger.info(f"总标签数: {stats['total_tags']}")
        logger.info(f"排除标签: {stats['excluded_tags']}")
        logger.info(f"去重节省: {stats['duplicates']} 个段落")
        logger.info(f"分层统计:")
        for tier, count in stats['by_tier'].items():
            tier_name = {
                'tier1_short_repeatable': '短文本(可重复)',
                'tier2_normal': '普通文本',
                'tier3_long_complex': '长文本(复杂)'
            }.get(tier, tier)
            logger.info(f"  {tier_name}: {count}")
        logger.info("====================")

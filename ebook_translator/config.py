# 配置文件
import os

# DeepSeek API 配置
# 从环境变量读取 API 密钥
# 请设置环境变量 DEEPSEEK_API_KEY 为您的 API 密钥
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 翻译配置
TRANSLATION_MODEL = "deepseek-chat"
MAX_TOKENS = 2048
TEMPERATURE = 0.7

# 缓存配置
CACHE_FILE = "translation_cache.json"
CACHE_EXPIRY = 30 * 24 * 60 * 60  # 30天过期

# EPUB 处理配置
CHUNK_SIZE = 1000  # 翻译的文本块大小

# PDF 转换配置
CALIBRE_PATH = ""  # 如果 ebook-convert 不在 PATH 中，需要指定路径

# 专业PDF排版配置 - 针对电脑阅读优化（大字体+窄边距）
PDF_CONFIG = {
    # 页面设置（电脑阅读优化）
    'page': {
        'paper_size': 'letter',     # Letter尺寸更适合电脑屏幕阅读
        'margin_top': 29,           # 约10mm（缩小到原来的3/5）
        'margin_bottom': 29,        # 约10mm
        'margin_left': 29,          # 约10mm（缩小到原来的3/5）
        'margin_right': 29,         # 约10mm（缩小到原来的3/5）
        'background_color': '#f8f8f8', # 柔和背景色，减轻眼睛疲劳
    },
    # 字体配置（电脑阅读优化 - 大字体）
    'font': {
        'serif': 'Source Han Serif SC,Noto Serif CJK SC,SimSun,STSong,serif',
        'sans': 'Source Han Sans SC,Noto Sans CJK SC,SimHei,STHeiti,sans-serif',
        'mono': 'Source Han Mono SC,Noto Sans Mono CJK SC,Consolas,Microsoft YaHei Mono,monospace',
        'default_size': 18,          # 正文字号（pt）- 增大字体，适合电脑阅读
        'mono_size': 14,             # 等宽字体字号
        'bilingual_default_size': 18, # 双语版正文字号
        'bilingual_mono_size': 14,   # 双语版等宽字体字号
        'title_size': 24,            # 标题字号
        'heading_size': 20,          # 章节标题字号
    },
    # 排版设置（电脑阅读优化）
    'typography': {
        'line_height': 1.8,         # 行距倍数（1.8倍行距更舒适）
        'minimum_line_height': 150,  # 最小行高百分比（从130%增加到150%）
        'paragraph_indent': 2.0,    # 首行缩进（2倍字号，标准中文缩进）
        'paragraph_spacing': 1.5,   # 段间距（1.5倍字号，增加段落区分度）
        'justify': True,            # 两端对齐（提高可读性）
        'hyphenate': True,          # 连字符断字
        'hyphenate_chinese': True,  # 中文断字
    },
    # 页眉页脚（简洁设计）
    'header_footer': {
        'header_template': '',  # 删除页眉
        'footer_template': '<div style="text-align:center;font-size:11pt;color:#666;margin-top:8pt;">第 _PAGENUM_ 页 / 共 _TOTALPAGES_ 页</div>',
    },
    # 目录与书签
    'toc': {
        'add_toc': True,       # 添加目录
        'toc_depth': 3,        # 目录深度
        'toc_title': '目录',    # 目录标题
        'use_bookmarks': True, # 使用书签
    },
    # 图片优化
    'image': {
        'dpi': 150,              # 图片分辨率（屏幕阅读不需要300dpi）
        'max_width': 600,        # 最大宽度（适应屏幕）
        'max_height': 800,       # 最大高度
    },
    # 高级选项
    'advanced': {
        'use_xmp_metadata': True,      # 使用XMP元数据
        'mark_links': True,            # 标记链接
        'page_numbers': True,          # 页码
        'disable_resample': False,     # 允许图片重采样
        'preserve_cover_aspect_ratio': True, # 保持封面宽高比
    },
    # 阅读体验优化
    'reading': {
        'two_column': False,     # 单栏布局（电脑阅读更适合）
        'page_break_before_h1': True,  # H1前分页
        'keep_with_next': True,        # 保持段落连贯性
        'widow_control': True,         # 控制孤行
    }
}

# 日志配置
LOG_LEVEL = "INFO"

# 智能分层处理配置（方案C）
TIER_CONFIG = {
    'tier1_short_repeatable': {
        # 短文本且可重复（如图表标题、章节编号）
        'deduplicate': True,           # 启用去重
        'batch_translate': True,       # 批量翻译
        'max_length': 30,              # 最大长度
        'patterns': [                  # 匹配模式
            r'^Figure\s+\d+[\.\d]*',      # Figure 1, Figure 1.1
            r'^Table\s+\d+[\.\d]*',       # Table 1, Table 1.1
            r'^Chapter\s+\d+',            # Chapter 1
            r'^Section\s+\d+',            # Section 1
            r'^Appendix\s+[A-Z]',         # Appendix A
            r'^\d+[\.\d]*\s+\w+',          # 1.1 Introduction
            r'^[A-Z][\.\)]\s+',            # A. 或 A)
            r'^Listing\s+\d+[\.\d]*',      # Listing 1.1
            r'^Example\s+\d+[\.\d]*',      # Example 1.1
        ]
    },
    'tier2_normal': {
        # 普通段落
        'deduplicate': False,          # 不去重
        'batch_translate': True,       # 批量翻译
        'min_length': 30,              # 最小长度
        'max_length': 200,             # 最大长度
    },
    'tier3_long_complex': {
        # 长段落或复杂内容
        'deduplicate': False,          # 不去重
        'batch_translate': False,      # 单独翻译（保证质量）
        'min_length': 200,             # 最小长度
    }
}

# 文本提取过滤配置
EXTRACTION_CONFIG = {
    # 排除的标签（导航、页眉页脚等）
    'exclude_tags': [
        'script', 'style', 'nav', 'header', 'footer',
    ],
    # 排除的class/id模式
    'exclude_patterns': [
        r'nav', r'menu', r'navbar',
        r'header', r'footer',
        r'sidebar', r'toc', r'index',
        r'pagination', r'prev', r'next',
    ],
    # 内容标签（按优先级）
    'content_tags': [
        'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'li', 'dt', 'dd', 'blockquote', 'a',
        'figcaption', 'td', 'th', 'caption'
    ],
    # 最小文本长度
    'min_text_length': 5,
}

# 翻译优化配置
TRANSLATION_OPTIMIZATION = {
    # 批量翻译配置
    'batch': {
        'tier1_batch_size': 10,        # 短文本批量大小
        'tier2_batch_size': 5,         # 普通文本批量大小
        'max_workers': 3,              # 最大并发数（降低避免限流）
    },
    # 质量检查配置
    'quality_check': {
        'enabled': True,
        'min_translation_ratio': 0.3,   # 翻译长度最小比例
        'max_translation_ratio': 3.0,   # 翻译长度最大比例
        'retry_empty': True,            # 空翻译重试
    }
}

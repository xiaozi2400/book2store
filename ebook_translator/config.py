# 配置文件
import os
import json

# DeepSeek API 配置
# 从环境变量读取 API 密钥
# 请设置环境变量 DEEPSEEK_API_KEY 为您的 API 密钥
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# MiniMax API 配置
# 请设置环境变量 MINIMAX_API_KEY 为您的 API 密钥
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_API_URL = "https://api.minimax.io/v1/text/chatcompletion_v2"
MINIMAX_MODEL = "MiniMax-M2.7"



# 翻译器选择配置
# 可选值: "deepseek" 或 "minimax"
# 也可以通过环境变量 TRANSLATION_PROVIDER 设置
TRANSLATION_PROVIDER = os.environ.get("TRANSLATION_PROVIDER", "deepseek")

# 翻译配置
# 根据 provider 自动选择模型
if TRANSLATION_PROVIDER == "minimax":
    TRANSLATION_MODEL = MINIMAX_MODEL
else:
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

# 外部PDF配置文件路径（相对于项目根目录）
PDF_CONFIG_FILE = "pdf_config.json"


def load_pdf_config():
    """从外部JSON文件加载PDF配置
    
    如果外部配置文件存在，则使用外部配置；
    否则使用默认配置。
    
    Returns:
        dict: PDF配置字典
    """
    # 默认PDF排版配置 - 针对电脑阅读优化（大字体+窄边距）
    default_config = {
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
    },
    # CSS样式配置（用于EPUB生成）
    'css': {
        'paragraph_margin_bottom': '1.5em',
        'paragraph_line_height': '1.8',
        'paragraph_text_indent': '2em',
        'heading_margin_top': '1.5em',
        'heading_margin_bottom': '1em',
        'list_item_margin_bottom': '0.8em',
        'blockquote_margin': '1.5em',
        'blockquote_padding_left': '1.5em',
        'blockquote_border_left': '3px solid #ccc',
    }
    }
    
    # 尝试从外部配置文件加载
    config_paths = [
        # 1. 当前工作目录
        os.path.join(os.getcwd(), PDF_CONFIG_FILE),
        # 2. 项目根目录（根据此文件位置推算）
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), PDF_CONFIG_FILE),
        # 3. 上级目录
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', PDF_CONFIG_FILE),
    ]
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    external_config = json.load(f)
                
                # 递归合并配置
                def merge_config(default, external):
                    result = default.copy()
                    for key, value in external.items():
                        if key.startswith('_'):  # 跳过注释字段
                            continue
                        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                            result[key] = merge_config(result[key], value)
                        else:
                            result[key] = value
                    return result
                
                merged_config = merge_config(default_config, external_config)
                print(f"[配置] 已从 {config_path} 加载PDF排版配置")
                return merged_config
            except Exception as e:
                print(f"[警告] 加载配置文件 {config_path} 失败: {e}")
                continue
    
    print("[配置] 使用默认PDF排版配置")
    return default_config


# 加载PDF配置
PDF_CONFIG = load_pdf_config()

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
        r'nav\b', r'\bmenu\b', r'navbar',
        r'\bheader\b', r'\bfooter\b',
        r'\bindex\b',
        r'pagination', r'\bprev\b', r'\bnext\b',
    ],
    # 内容标签（按优先级）
    'content_tags': [
        'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
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
        'tier1_batch_size': 15,        # 短文本批量大小（保守优化）
        'tier2_batch_size': 8,         # 普通文本批量大小（保守优化）
        'max_workers': 5,              # 最大并发数（保守优化）
        # 按字符数合并策略（类似 Calibre 插件，可大幅减少 API 调用）
        'use_char_based_batching': True,  # 是否启用按字符数合并策略
        'max_chars_per_batch': 1800,    # 每个批次的最大字符数（Calibre 默认是 1800）
    },
    # 质量检查配置
    'quality_check': {
        'enabled': True,
        'min_translation_ratio': 0.3,   # 翻译长度最小比例（Tier1/2 默认）
        'max_translation_ratio': 3.0,   # 翻译长度最大比例（Tier1/2 默认）
        'tier3_min_ratio': 0.1,         # Tier3（长文本/代码）最小比例
        'tier3_max_ratio': 5.0,         # Tier3（长文本/代码）最大比例
        'short_text_min_length': 30,    # 短文本原文长度阈值，≤此值使用绝对长度检查
        'short_text_min_absolute': 3,   # 短文本翻译绝对长度下限
        'retry_empty': True,            # 质量问题重试
    }
}

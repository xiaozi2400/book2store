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

# 日志配置
LOG_LEVEL = "INFO"

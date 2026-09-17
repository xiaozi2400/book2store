"""
AI文案生成器 - 已迁移至 automation.publishing.ai_copywriter
"""
from automation.metadata_writer import MetadataWriter
from automation.publishing.ai_copywriter import *

# 显式从真实路径导入，使测试 patch automation.ai_client.AIClient 能拦截到
from automation.ai_client import AIClient
from automation.database import DatabaseManager

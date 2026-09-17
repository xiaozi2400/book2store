"""
SQLite 翻译缓存实现（使用项目已有的数据库连接）
"""
import os
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime

# 导入缓存接口
sys_path_fix = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ebook_translator')
if sys_path_fix not in os.sys.path:
    os.sys.path.insert(0, sys_path_fix)
from translator.cache_interface import TranslationCache

# 导入项目的数据库模块
from automation.database import get_session, close_session
from automation.models import TranslationCache as TranslationCacheModel


logger = logging.getLogger(__name__)


class SQLiteTranslationCache(TranslationCache):
    """使用项目 SQLite 数据库的翻译缓存实现"""
    
    def __init__(self):
        """初始化 SQLite 缓存"""
        logger.info("初始化 SQLite 翻译缓存")
    
    def _get_hash(self, text):
        """获取文本的 MD5 哈希值"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def get(self, text):
        """从数据库获取缓存的翻译结果"""
        source_hash = self._get_hash(text)
        
        session = get_session()
        try:
            record = session.query(TranslationCacheModel)\
                .filter(TranslationCacheModel.source_hash == source_hash)\
                .first()
            
            if record:
                logger.debug(f"缓存命中: {source_hash[:12]}...")
                return record.translated_text
            else:
                return None
                
        except Exception as e:
            logger.error(f"读取缓存失败: {e}")
            return None
        finally:
            close_session(session)
    
    def set(self, text, translated):
        """保存翻译结果到数据库"""
        source_hash = self._get_hash(text)
        
        session = get_session()
        try:
            # 检查是否已存在，存在则更新，否则新建
            existing = session.query(TranslationCacheModel)\
                .filter(TranslationCacheModel.source_hash == source_hash)\
                .first()
            
            if existing:
                existing.translated_text = translated
                existing.updated_at = datetime.utcnow()
                logger.debug(f"更新缓存: {source_hash[:12]}...")
            else:
                new_record = TranslationCacheModel(
                    source_hash=source_hash,
                    source_text=text,
                    translated_text=translated,
                    model=None  # 暂时不记录模型
                )
                session.add(new_record)
                logger.debug(f"添加新缓存: {source_hash[:12]}...")
            
            session.commit()
        except Exception as e:
            logger.error(f"写入缓存失败: {e}")
            session.rollback()
        finally:
            close_session(session)
    
    def migrate_from_json(self, json_cache_path):
        """从旧 JSON 缓存文件迁移数据到 SQLite
        
        Args:
            json_cache_path: JSON 缓存文件的路径
            
        Returns:
            迁移的数据条数
        """
        if not json_cache_path or not Path(json_cache_path).exists():
            logger.warning("JSON 缓存文件不存在，跳过迁移")
            return 0
        
        try:
            logger.info(f"开始从 JSON 缓存迁移数据: {json_cache_path}")
            
            with open(json_cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cache_data = data.get("cache", {})
            if not cache_data:
                logger.info("JSON 缓存中没有数据")
                return 0
            
            session = get_session()
            count = 0
            
            for cache_hash, cache_item in cache_data.items():
                source_text = cache_item.get("source", "")
                translated_text = cache_item.get("translated", "")
                
                if source_text and translated_text:
                    # 检查是否已存在
                    existing = session.query(TranslationCacheModel)\
                        .filter(TranslationCacheModel.source_hash == cache_hash)\
                        .first()
                    
                    if not existing:
                        new_record = TranslationCacheModel(
                            source_hash=cache_hash,
                            source_text=source_text,
                            translated_text=translated_text
                        )
                        session.add(new_record)
                        count += 1
                        if count % 100 == 0:
                            logger.debug(f"已迁移 {count} 条缓存数据...")
                            session.commit()
            
            session.commit()
            logger.info(f"JSON 缓存迁移完成，共迁移 {count} 条数据")
            return count
            
        except Exception as e:
            logger.error(f"迁移 JSON 缓存失败: {e}")
            if 'session' in locals():
                session.rollback()
            return 0
        finally:
            if 'session' in locals():
                close_session(session)

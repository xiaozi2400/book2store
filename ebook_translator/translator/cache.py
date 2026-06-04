import json
import os
import hashlib
import time
import logging
from typing import Optional
from config import CACHE_FILE, CACHE_EXPIRY
from .cache_interface import TranslationCache

logger = logging.getLogger(__name__)


class CacheManager(TranslationCache):
    """缓存管理器 - 实现 TranslationCache 接口"""
    
    def __init__(self):
        """初始化缓存管理器"""
        self.cache_file = CACHE_FILE
        self.cache = self._load_cache()
    
    def _load_cache(self):
        """加载缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 清理过期缓存
                    self._clean_expired_cache(data)
                    return data
            except Exception as e:
                logger.warning(f"加载缓存时出错: {e}")
                return {"cache": {}}
        return {"cache": {}}
    
    def _clean_expired_cache(self, data):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = []
        
        for key, value in data.get("cache", {}).items():
            timestamp = value.get("timestamp", 0)
            if current_time - timestamp > CACHE_EXPIRY:
                expired_keys.append(key)
        
        for key in expired_keys:
            del data["cache"][key]
    
    def _save_cache(self):
        """保存缓存"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存缓存时出错: {e}")
    
    def get_hash_key(self, text):
        """生成文本的哈希键"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def get(self, text):
        """获取缓存的翻译"""
        key = self.get_hash_key(text)
        if key in self.cache.get("cache", {}):
            return self.cache["cache"][key]["translated"]
        return None
    
    def set(self, text, translated):
        """设置缓存的翻译"""
        key = self.get_hash_key(text)
        self.cache["cache"][key] = {
            "source": text,
            "translated": translated,
            "timestamp": time.time()
        }
        self._save_cache()
    
    def clear(self):
        """清空缓存"""
        self.cache = {"cache": {}}
        self._save_cache()

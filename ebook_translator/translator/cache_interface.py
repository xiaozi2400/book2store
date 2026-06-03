
"""
翻译缓存接口抽象
用于解耦 ebook_translator 和具体缓存实现
"""
from abc import ABC, abstractmethod


class TranslationCache(ABC):
    """翻译缓存接口"""
    
    @abstractmethod
    def get(self, text):
        """
        获取缓存的翻译结果
        
        Args:
            text: 源文本
            
        Returns:
            缓存的翻译结果，如果没有则返回 None
        """
        pass
    
    @abstractmethod
    def set(self, text, translated):
        """
        设置翻译缓存
        
        Args:
            text: 源文本
            translated: 翻译结果
        """
        pass


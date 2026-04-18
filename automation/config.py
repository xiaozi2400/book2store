"""
配置管理模块
"""
import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional


class Config:
    """配置类"""

    _instance = None
    _config: Dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """加载配置文件"""
        config_path = Path(__file__).parent.parent / "config.yaml"

        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = self._get_default_config()

    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "paths": {
                "input_dir": "E:\\ebooks\\input",
                "output_dir": "./output",
                "data_dir": "./data",
                "log_dir": "./logs"
            },
            "sku": [
                {
                    "name": "纯英文原版",
                    "price": 3.99,
                    "includes": ["english_pdf"]
                },
                {
                    "name": "完整套装",
                    "price": 8.99,
                    "includes": ["english_pdf", "chinese_pdf", "bilingual_pdf", "summary_pdf"]
                }
            ],
            "ai": {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "max_tokens": 4096,
                "temperature": 0.7,
                "retry_times": 3,
                "retry_delay": 5
            },
            "image": {
                "max_width": 1200,
                "max_height": 1600,
                "quality": 85,
                "format": "jpg"
            },
            "xianyu": {
                "login_method": "qr_code",
                "base_url": "https://www.xianyu.com",
                "timeout": 30,
                "auto_retry": True
            },
            "error_handling": {
                "api_error": "retry",
                "file_error": "skip",
                "parse_error": "skip",
                "publish_error": "manual"
            },
            "summarizer": {
                "core_insight_length": "300-500",
                "chapter_summary_length": "150-200",
                "max_quotes": 15,
                "max_content_length": 10000,
                "prompt": "你是一位专业的书籍摘要专家..."
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    @property
    def input_dir(self) -> str:
        """输入目录"""
        return self.get("paths.input_dir", "E:\\ebooks\\input")

    @property
    def output_dir(self) -> str:
        """输出目录"""
        return self.get("paths.output_dir", "./output")

    @property
    def data_dir(self) -> str:
        """数据目录"""
        return self.get("paths.data_dir", "./data")

    @property
    def log_dir(self) -> str:
        """日志目录"""
        return self.get("paths.log_dir", "./logs")

    @property
    def sku_config(self) -> List[Dict]:
        """SKU配置"""
        return self.get("sku", [])

    @property
    def ai_config(self) -> Dict:
        """AI配置"""
        return self.get("ai", {})

    @property
    def image_config(self) -> Dict:
        """图片配置"""
        return self.get("image", {})

    @property
    def xianyu_config(self) -> Dict:
        """闲鱼配置"""
        return self.get("xianyu", {})

    @property
    def error_handling_config(self) -> Dict:
        """错误处理配置"""
        return self.get("error_handling", {})

    def get_sku_price(self, sku_name: str) -> float:
        """获取SKU价格"""
        for sku in self.sku_config:
            if sku.get("name") == sku_name:
                return sku.get("price", 0)
        return 0

    def summarizer_config(self) -> Dict:
        """精简版生成配置"""
        return self.get("summarizer", {})

    def get_sku_includes(self, sku_name: str) -> List[str]:
        """获取SKU包含内容"""
        for sku in self.sku_config:
            if sku.get("name") == sku_name:
                return sku.get("includes", [])
        return []


config = Config()

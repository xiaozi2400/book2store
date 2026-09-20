"""
配置管理模块
"""

from pathlib import Path
from typing import Any, Dict, List

import yaml


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
            with open(config_path, "r", encoding="utf-8") as f:
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
                "log_dir": "./logs",
            },
            "sku": [
                {"name": "纯英文原版", "price": 3.99, "includes": ["english_pdf"]},
                {
                    "name": "完整套装",
                    "price": 8.99,
                    "includes": ["english_pdf", "chinese_pdf", "bilingual_pdf", "summary_pdf"],
                },
            ],
            "ai": {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "max_tokens": 4096,
                "temperature": 0.7,
                "retry_times": 3,
                "retry_delay": 5,
            },
            "minimax": {
                "enabled": True,
                "provider": "minimax",
                "model": "MiniMax-2.7-Globe",
                "api_key": "",
                "api_url": "https://api.minimax.chat/v1/chat/completions",
                "max_tokens": 4096,
                "temperature": 0.7,
                "retry_times": 3,
            },
            "image": {"max_width": 1200, "max_height": 1600, "quality": 85, "format": "jpg"},
            "xianyu": {
                "login_method": "qr_code",
                "base_url": "https://www.xianyu.com",
                "timeout": 30,
                "auto_retry": True,
            },
            "error_handling": {
                "api_error": "retry",
                "file_error": "skip",
                "parse_error": "skip",
                "publish_error": "manual",
            },
            "summarizer": {
                "core_insight_length": "300-500",
                "chapter_summary_length": "150-200",
                "max_quotes": 15,
                "max_content_length": 10000,
                "prompt": "你是一位专业的书籍摘要专家...",
            },
            "quality_check": {
                "enabled": True,  # 纯程序化检查，零 API 成本
                "thresholds": {
                    "excellent": 90,  # 优秀
                    "good": 75,  # 良好
                    "pass": 60,  # 合格
                },
                "dimensions": {
                    "fidelity": True,
                    "fluency": True,
                    "consistency": True,
                    "format": True,
                    "terminology": True,
                    "cultural": True,
                    "completeness": True,
                    "pdf_toc_links": True,
                },
            },
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
    def test_input_dir(self) -> str:
        """测试输入目录"""
        return self.get("paths.test_input_dir", "E:\\ebooks\\test-input")

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
    def minimax_config(self) -> Dict:
        """MiniMax AI配置"""
        return self.get("minimax", {})

    @property
    def image_config(self) -> Dict:
        """图片配置"""
        return self.get("image", {})

    @property
    def image_generator_config(self) -> Dict:
        """图片生成器配置"""
        return self.get("image_generator", {})

    @property
    def xianyu_config(self) -> Dict:
        """闲鱼配置"""
        return self.get("xianyu", {})

    @property
    def xianyu_inventory(self) -> int:
        """闲鱼库存"""
        return self.get("xianyu.inventory", 1)

    @property
    def xianyu_location(self) -> str:
        """闲鱼所在地"""
        return self.get("xianyu.location", "深圳北站")

    @property
    def xianyu_shipping(self) -> str:
        """闲鱼发货方式"""
        return self.get("xianyu.shipping", "包邮")

    @property
    def xianyu_cookie_path(self) -> str:
        """闲鱼Cookie持久化路径"""
        return self.get("xianyu.cookie_path", "data/xianyu_cookie.json")

    @property
    def xianyu_max_retries(self) -> int:
        """闲鱼最大重试次数"""
        return self.get("xianyu.max_retries", 3)

    @property
    def xianyu_retry_interval(self) -> int:
        """闲鱼重试间隔(秒)"""
        return self.get("xianyu.retry_interval", 2)

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

    @property
    def copywriting_config(self) -> Dict:
        """文案生成配置"""
        return self.get("copywriting", {})

    def suitability_eval_config(self) -> Dict:
        """精简版适合度评估配置"""
        return self.get("suitability_eval", {})

    def get_sku_includes(self, sku_name: str) -> List[str]:
        """获取SKU包含内容"""
        for sku in self.sku_config:
            if sku.get("name") == sku_name:
                return sku.get("includes", [])
        return []

    def get_quality_check_enabled(self) -> bool:
        """获取质量检查是否启用"""
        return self.get("quality_check.enabled", True)

    def get_quality_check_threshold(self, key: str, default=60) -> int:
        """获取质量检查阈值"""
        return self.get(f"quality_check.thresholds.{key}", default)


config = Config()

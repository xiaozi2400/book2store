"""
配置管理模块
"""

from pathlib import Path
from typing import Any, Dict, List

import yaml

x = 1


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
                "log_dir": "./logs",
            },
            "sku": [
                {"name": "纯英文原版", "price": 3.99},
                {"name": "完整套装", "price": 8.99},
            ],
            "ai": {
                "provider": "deepseek",
                "retry_times": 3,
            },
            "xianyu": {
                "base_url": "https://www.xianyu.com",
                "timeout": 30,
            },
            "quality_check": {
                "enabled": True,
                "thresholds": {
                    "excellent": 90,
                    "good": 75,
                    "pass": 60,
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

    def get_sku_price(self, sku_name: str) -> float:
        """获取SKU价格"""
        for sku in self.sku_config:
            if sku.get("name") == sku_name:
                return sku.get("price", 0)
        return 0

    @property
    def copywriting_config(self) -> Dict:
        """文案生成配置"""
        return self.get("copywriting", {})

    def get_quality_check_enabled(self) -> bool:
        """获取质量检查是否启用"""
        return self.get("quality_check.enabled", True)

    def get_quality_check_threshold(self, key: str, default=60) -> int:
        """获取质量检查阈值"""
        return self.get(f"quality_check.thresholds.{key}", default)


config = Config()

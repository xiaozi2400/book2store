"""
AI文案生成器 - 生成闲鱼文案和小红书笔记
"""
import os
import sys
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .ai_client import AIClient
from .database import DatabaseManager
from .config import config
from .utils import logger


class AICopywriter:
    """AI文案生成器"""

    def __init__(self):
        self.ai = AIClient()
        self.db = DatabaseManager()
        self.sku_config = config.sku_config

    def generate(self, book_id: str, book_info: Dict = None) -> bool:
        """生成文案"""
        logger.info(f"开始生成文案: {book_id}")

        try:
            self.db.update_book_status(book_id, "copywriting")
            self.db.add_log(book_id, "copywriting", "start", "开始生成文案")

            if not book_info:
                book_info = {
                    'title': 'Unknown',
                    'author': 'Unknown',
                    'summary': ''
                }

            xianyu_result = self.ai.generate_xianyu_listing(book_info)
            logger.info(f"闲鱼文案生成结果: {xianyu_result}")

            xiaohongshu_result = self.ai.generate_xiaohongshu_note(book_info)
            logger.info(f"小红书笔记生成结果: {xiaohongshu_result[:100] if xiaohongshu_result else 'None'}...")

            logger.info(f"更新数据库: book_id={book_id}")
            self.db.update_book_output(
                book_id,
                xianyu_title=xianyu_result.get('title'),
                xianyu_description=xianyu_result.get('description'),
                xianyu_tags=','.join(xianyu_result.get('tags', [])),
                xiaohongshu_note=xiaohongshu_result
            )
            logger.info(f"数据库更新完成")

            self.db.add_log(book_id, "copywriting", "success", "文案生成完成")

            logger.info(f"文案生成成功: {book_id}")
            return True

        except Exception as e:
            logger.error(f"生成文案失败: {book_id}, 错误: {e}")
            self.db.add_log(book_id, "copywriting", "error", str(e))
            return False

    def get_sku_info(self) -> list:
        """获取SKU信息"""
        return [
            {
                'name': sku.get('name'),
                'price': sku.get('price'),
                'includes': ', '.join(sku.get('includes', []))
            }
            for sku in self.sku_config
        ]


def generate_copywriting(book_id: str, book_info: Dict = None) -> bool:
    """生成文案"""
    copywriter = AICopywriter()
    return copywriter.generate(book_id, book_info)


if __name__ == "__main__":
    print("AI文案生成器测试")

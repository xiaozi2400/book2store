"""
闲鱼发布器 - 使用Playwright自动化发布商品
"""
import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
from .database import DatabaseManager
from .config import config
from .utils import logger, ensure_dir


class XianyuPublisher:
    """闲鱼发布器"""

    def __init__(self):
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir)
        self.xianyu_config = config.xianyu_config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def publish(self, book_id: str) -> bool:
        """发布到闲鱼"""
        logger.info(f"开始发布: {book_id}")

        try:
            self.db.update_book_status(book_id, "publishing")
            self.db.add_log(book_id, "publishing", "start", "开始发布到闲鱼")

            book_output = self.db.get_book_output(book_id)
            if not book_output:
                raise ValueError(f"未找到书籍输出: {book_id}")

            self._start_browser()

            self._login()

            self._fill_listing_form(book_output)

            self._setup_sku(book_output)

            self._set_delivery_links(book_output)

            self.db.update_book_output(
                book_id,
                publish_status="published",
                xianyu_listing_url="https://www.xianyu.com/item/detail/xxx"
            )

            self.db.add_log(book_id, "publishing", "success", "发布成功")
            logger.info(f"发布成功: {book_id}")

            self._close()
            return True

        except Exception as e:
            logger.error(f"发布失败: {book_id}, 错误: {e}")
            self.db.add_log(book_id, "publishing", "error", str(e))
            self._close()
            return False

    def _start_browser(self):
        """启动浏览器"""
        try:
            playwright = sync_playwright().start()
            self.browser = playwright.chromium.launch(headless=False)
            self.context = self.browser.new_context()
            self.page = self.context.new_page()
            logger.info("浏览器启动成功")
        except Exception as e:
            logger.error(f"浏览器启动失败: {e}")
            raise

    def _login(self):
        """登录闲鱼"""
        logger.info("请扫码登录闲鱼...")

        self.page.goto("https://www.xianyu.com")

        self.page.wait_for_timeout(5000)

        if "login" in self.page.url.lower():
            logger.info("等待用户扫码登录...")
            self.page.wait_for_timeout(30000)

        logger.info("登录完成")

    def _fill_listing_form(self, book_output):
        """填写商品表单"""
        logger.info("填写商品信息...")

        self.page.goto("https://www.xianyu.com/publish")

        title = book_output.xianyu_title or "英文原版电子书"
        description = book_output.xianyu_description or ""

        self.page.fill('input[placeholder*="标题"]', title)

        self.page.fill('textarea[placeholder*="描述"]', description)

        images = []
        if book_output.cover_image:
            images.append(book_output.cover_image)
        if book_output.toc_preview_image:
            images.append(book_output.toc_preview_image)

        if images:
            for img in images[:9]:
                self.page.click('input[type="file"]')
                self.page.wait_for_timeout(500)

        logger.info("商品信息填写完成")

    def _setup_sku(self, book_output):
        """配置SKU"""
        logger.info("配置SKU...")

        self.page.click('text=设置SKU')
        self.page.wait_for_timeout(1000)

        sku1_price = "3.99"
        sku2_price = "8.99"

        self.page.fill('input[placeholder*="价格"]', sku1_price)

        logger.info("SKU配置完成")

    def _set_delivery_links(self, book_output):
        """设置发货链接"""
        logger.info("设置发货链接...")

        if book_output.pan_link_sku1:
            logger.info(f"SKU1发货链接: {book_output.pan_link_sku1}")

        if book_output.pan_link_sku2:
            logger.info(f"SKU2发货链接: {book_output.pan_link_sku2}")

        logger.info("发货链接设置完成")

    def _close(self):
        """关闭浏览器"""
        if self.browser:
            self.browser.close()
            logger.info("浏览器已关闭")

    def generate_publish_list(self, book_id: str) -> str:
        """生成发布清单（备用方案）"""
        book_output = self.db.get_book_output(book_id)

        if not book_output:
            return "未找到书籍信息"

        content = f"""【闲鱼发布清单】

📚 书名: {book_output.book.title if book_output.book else 'Unknown'}
✍️ 作者: {book_output.book.author if book_output.book else 'Unknown'}

━━━━━━━━━━━━━━━━━━━━

💰 价格:
• 纯英文原版: ¥3.99
• 完整套装: ¥8.99

📦 包含内容:
• 纯英文原版PDF
• 中文翻译版PDF
• 中英双语版PDF
• 核心内容精简版PDF

━━━━━━━━━━━━━━━━━━━━

📝 标题:
{book_output.xianyu_title or '请手动填写'}

📖 描述:
{book_output.xianyu_description or '请手动填写'}

🏷️ 标签:
{book_output.xianyu_tags or '英文原版, 电子书, PDF, 翻译版, 学习资料'}

━━━━━━━━━━━━━━━━━━━━

🔗 SKU1链接 (纯英文):
{book_output.pan_link_sku1 or '请手动填写'}

🔗 SKU2链接 (完整套装):
{book_output.pan_link_sku2 or '请手动填写'}

📌 提取码: {book_output.pan_code or '无'}
"""

        list_dir = ensure_dir(self.output_dir / "publish_lists")
        list_path = list_dir / f"{book_id}_publish_list.txt"

        with open(list_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"发布清单已生成: {list_path}")
        return str(list_path)


def publish_to_xianyu(book_id: str) -> bool:
    """发布到闲鱼"""
    publisher = XianyuPublisher()
    return publisher.publish(book_id)


if __name__ == "__main__":
    print("闲鱼发布器测试")

"""
闲鱼发布器 - 使用 Playwright 自动化发布商品
"""
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
from .database import DatabaseManager
from .config import config
from .metadata_writer import MetadataWriter
from .utils import logger, ensure_dir


class XianyuPublisher:
    """闲鱼发布器"""

    def __init__(self):
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir).resolve()
        self.xianyu_cfg = config.xianyu_config
        self.sku_config = config.sku_config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def publish(self, book_id: str) -> bool:
        """发布到闲鱼"""
        logger.info(f"=== 开始发布: {book_id} ===")

        try:
            self.db.update_book_status(book_id, "publishing")
            self.db.add_log(book_id, "publishing", "start", "开始发布到闲鱼")

            metadata = self._load_metadata(book_id)
            if not metadata:
                raise ValueError(f"未找到 metadata.json: {book_id}")

            copywriting = metadata.get("copywriting", {}).get("xianyu", {})
            description = copywriting.get("description", "")
            if not description:
                raise ValueError(f"闲鱼文案为空: {book_id}")

            self._start_browser()

            self._login()

            self._navigate_to_publish()

            self._fill_description(description)

            meta_dir = self._get_meta_dir(book_id)
            self._upload_images(meta_dir)

            self._setup_skus(self.sku_config)

            self._fill_basic_info()

            listing_url = self._submit_and_get_url()

            self._save_result(book_id, listing_url)

            self.db.update_book_status(book_id, "published")
            self.db.add_log(book_id, "publishing", "success", f"发布成功: {listing_url}")
            logger.info(f"=== 发布成功: {book_id} ===")

            self._close()
            return True

        except Exception as e:
            logger.error(f"发布失败: {book_id}, 错误: {e}")
            self.db.add_log(book_id, "publishing", "error", str(e))
            self._capture_error_screenshot(book_id)
            self._close()
            return False

    def _load_metadata(self, book_id: str) -> Optional[dict]:
        """加载 metadata.json"""
        book = self.db.get_book_by_id(book_id)
        if not book:
            return None

        base_name = Path(book.filename).stem
        meta_path = self.output_dir / f"{base_name}_metadata" / "metadata.json"

        if not meta_path.exists():
            logger.warning(f"metadata.json 不存在: {meta_path}")
            return None

        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _get_meta_dir(self, book_id: str) -> Path:
        """获取 metadata 目录路径"""
        book = self.db.get_book_by_id(book_id)
        base_name = Path(book.filename).stem
        return self.output_dir / f"{base_name}_metadata"

    def _start_browser(self):
        """启动浏览器"""
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=self.xianyu_cfg.get("headless", False))
            cookie_path = Path(config.xianyu_cookie_path)

            if cookie_path.exists():
                self.context = self.browser.new_context(storage_state=str(cookie_path))
            else:
                self.context = self.browser.new_context()

            self.page = self.context.new_page()
            logger.info("浏览器启动成功")
        except Exception as e:
            logger.error(f"浏览器启动失败: {e}")
            raise

    def _login(self):
        """登录验证"""
        self.page.goto(config.xianyu_cfg.get("base_url", "https://seller.goofish.com"))
        self.page.wait_for_load_state("networkidle")
        time.sleep(2)

        cookies = self.context.cookies()
        if cookies and any(c.get("name") == "smt" for c in cookies):
            logger.info("已有有效登录态")
            return

        logger.info("等待用户扫码登录闲鱼...")
        self.db.add_log("", "publishing", "info", "请扫码登录闲鱼卖家中心")

        max_wait = self.xianyu_cfg.get("timeout", 60)
        for i in range(max_wait):
            time.sleep(1)
            cookies = self.context.cookies()
            if cookies and any(c.get("name") == "smt" for c in cookies):
                logger.info("登录成功")
                cookie_path = Path(config.xianyu_cookie_path)
                cookie_path.parent.mkdir(parents=True, exist_ok=True)
                self.context.storage_state(path=str(cookie_path))
                return

        raise TimeoutError("登录超时，请重试")

    def _navigate_to_publish(self):
        """导航到发布页：点击「商品」→「商品发布」"""
        logger.info("导航到商品发布页...")

        goods_tab = self.page.locator("text=商品").first
        goods_tab.wait_for(timeout=10000)
        goods_tab.click()
        time.sleep(1)

        publish_btn = self.page.locator("text=商品发布").first
        publish_btn.wait_for(timeout=10000)
        publish_btn.click()

        self.page.wait_for_load_state("networkidle")
        time.sleep(3)
        logger.info("已进入商品发布页")

    def _fill_description(self, description: str):
        """填写宝贝描述"""
        logger.info("填写宝贝描述...")

        desc_input = self.page.locator("textarea").or_(self.page.locator("[contenteditable=\"true\"]")).first
        desc_input.wait_for(timeout=10000)
        desc_input.fill(description)
        logger.info("宝贝描述已填写")

    def _upload_images(self, meta_dir: Path):
        """上传宝贝图片"""
        logger.info("上传宝贝图片...")

        images_to_upload = []
        for img_name in ["cover.jpg", "toc_preview.jpg"]:
            img_path = meta_dir / img_name
            if img_path.exists():
                images_to_upload.append(str(img_path))

        if not images_to_upload:
            logger.warning("没有找到可上传的图片")
            return

        file_input = self.page.locator("input[type=\"file\"]").first
        if file_input.is_hidden():
            upload_area = self.page.locator("text=上传图片").or_(
                self.page.locator("text=添加图片")
            ).first
            upload_area.click()
            time.sleep(1)

        file_input = self.page.locator("input[type=\"file\"]").first
        file_input.set_input_files(images_to_upload)
        time.sleep(3)
        logger.info(f"已上传 {len(images_to_upload)} 张图片")

    def _setup_skus(self, sku_list: list):
        """设置商品规格（SKU）"""
        logger.info("设置商品规格...")

        for i, sku in enumerate(sku_list):
            if i > 0:
                add_btn = self.page.locator("text=添加规格类型").or_(
                    self.page.locator("text=+ 添加规格类型")
                ).first
                if add_btn.is_visible():
                    add_btn.click()
                    time.sleep(1)

            sku_name = sku.get("name", f"规格{i+1}")
            sku_price = sku.get("price", 0)

            name_input = self.page.locator("input[placeholder*=\"规格\"]").or_(
                self.page.locator("input[placeholder*=\"名称\"]")
            ).nth(i)
            if name_input.is_visible():
                name_input.fill(sku_name)

            price_input = self.page.locator("input[placeholder*=\"价格\"]").or_(
                self.page.locator("input[placeholder*=\"价格\"]")
            ).nth(i)
            if price_input.is_visible():
                price_input.fill(str(sku_price))

            stock_input = self.page.locator("input[placeholder*=\"库存\"]").or_(
                self.page.locator("input[placeholder*=\"数量\"]")
            ).nth(i)
            if stock_input.is_visible():
                stock_input.fill(str(config.xianyu_inventory))

            logger.info(f"  SKU {i+1}: {sku_name} ¥{sku_price}")

    def _fill_basic_info(self):
        """填写基础信息（库存、所在地、发货方式）"""
        logger.info("填写基础信息...")

        stock_input = self.page.locator("input[placeholder*=\"库存\"]").or_(
            self.page.locator("input[placeholder*=\"数量\"]")
        ).first
        if stock_input.is_visible():
            stock_input.fill(str(config.xianyu_inventory))
        logger.info(f"  库存: {config.xianyu_inventory}")

        location_input = self.page.locator("input[placeholder*=\"所在地\"]").or_(
            self.page.locator("input[placeholder*=\"地区\"]")
        ).first
        if location_input.is_visible():
            location_input.fill(config.xianyu_location)
        logger.info(f"  宝贝所在地: {config.xianyu_location}")

        shipping_input = self.page.locator("input[placeholder*=\"发货\"]").or_(
            self.page.locator("input[placeholder*=\"运费\"]")
        ).first
        if shipping_input.is_visible():
            shipping_input.fill(config.xianyu_shipping)
        logger.info(f"  发货方式: {config.xianyu_shipping}")

    def _submit_and_get_url(self) -> str:
        """点击发布并获取商品链接"""
        logger.info("点击发布...")

        publish_btn = self.page.locator("button:has-text(\"发布\")").or_(
            self.page.locator("text=立即发布")
        ).first
        publish_btn.wait_for(timeout=10000)
        publish_btn.click()

        time.sleep(5)

        self.page.wait_for_load_state("networkidle")

        current_url = self.page.url
        logger.info(f"发布后当前URL: {current_url}")

        self.page.wait_for_timeout(3000)

        current_url = self.page.url
        return current_url

    def _save_result(self, book_id: str, listing_url: str):
        """保存发布结果到数据库和 metadata.json"""
        self.db.update_book_output(
            book_id,
            publish_status="published",
            xianyu_listing_url=listing_url,
        )
        logger.info(f"数据库已更新: xianyu_listing_url={listing_url}")

        MetadataWriter().update_publish_info(book_id, listing_url)
        logger.info(f"metadata.json 已更新")

    def _capture_error_screenshot(self, book_id: str):
        """错误时截图保存"""
        try:
            if self.page:
                log_dir = Path(config.log_dir)
                log_dir.mkdir(parents=True, exist_ok=True)
                screenshot_path = log_dir / f"publish_error_{book_id}_{int(time.time())}.png"
                self.page.screenshot(path=str(screenshot_path))
                logger.info(f"错误截图已保存: {screenshot_path}")
        except Exception as e:
            logger.warning(f"截图保存失败: {e}")

    def _close(self):
        """关闭浏览器"""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.warning(f"关闭浏览器时出错: {e}")
        finally:
            self.browser = None
            self.context = None
            self.page = None
            self.playwright = None


def publish_to_xianyu(book_id: str) -> bool:
    """便捷函数：发布到闲鱼"""
    publisher = XianyuPublisher()
    return publisher.publish(book_id)
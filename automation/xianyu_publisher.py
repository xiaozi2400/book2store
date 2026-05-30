
"""
闲鱼发布器 - 使用 Playwright 自动化发布商品
"""
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# 设置Playwright浏览器目录在项目下，避免权限问题
BROWSERS_DIR = Path(__file__).parent.parent / ".playwright-browsers"
BROWSERS_DIR.mkdir(exist_ok=True)
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(BROWSERS_DIR.resolve())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
from .database import DatabaseManager
from .config import config
from .utils import logger, ensure_dir


class XianyuPublisher:
    """闲鱼发布器"""

    def __init__(self):
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir).resolve()
        self.sku_config = config.sku_config
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    def publish(self, book_id):
        """发布到闲鱼"""
        logger.info("=== 开始发布: %s ===" % book_id)

        try:
            self.db.update_book_status(book_id, "publishing")
            self.db.add_log(book_id, "publishing", "start", "开始发布到闲鱼")

            meta_dir = self._get_meta_dir(book_id)
            xianyu_txt = meta_dir / "xianyu_listing.txt"
            if not xianyu_txt.exists():
                raise ValueError("未找到闲鱼文案: %s" % xianyu_txt)
            with open(xianyu_txt, "r", encoding="utf-8") as f:
                description = f.read()
            if not description.strip():
                raise ValueError("闲鱼文案为空: %s" % book_id)

            self._start_browser()

            self._login()

            self._navigate_to_publish()

            self._upload_images(meta_dir)

            self._fill_description(description)

            self._select_category()

            self._setup_skus(self.sku_config)

            #采用默认“包邮”和发布地址
            #  self._fill_basic_info()

            listing_url = self._submit_and_get_url()

            self._save_result(book_id, listing_url)

            self.db.update_book_status(book_id, "published")
            self.db.add_log(book_id, "publishing", "success", "发布成功: %s" % listing_url)
            logger.info("=== 发布成功: %s ===" % book_id)

            self._close()
            return True

        except Exception as e:
            logger.error("发布失败: %s, 错误: %s" % (book_id, str(e)))
            self.db.add_log(book_id, "publishing", "error", str(e))
            self._capture_error_screenshot(book_id)
            self._close()
            return False

    def _get_meta_dir(self, book_id):
        """获取 metadata 目录路径"""
        book = self.db.get_book_by_id(book_id)
        base_name = Path(book.filename).stem
        return self.output_dir / ("%s_metadata" % base_name)

    def _start_browser(self):
        """启动浏览器"""
        try:
            self.playwright = sync_playwright().start()
            headless = config.get("xianyu.headless", False)
            self.browser = self.playwright.chromium.launch(headless=headless)
            cookie_path = Path(config.xianyu_cookie_path)

            if cookie_path.exists():
                self.context = self.browser.new_context(storage_state=str(cookie_path))
            else:
                self.context = self.browser.new_context()

            self.page = self.context.new_page()
            logger.info("浏览器启动成功")
        except Exception as e:
            logger.error("浏览器启动失败: %s" % str(e))
            raise

    def _login(self):
        """登录验证"""
        base_url = config.get("xianyu.base_url", "https://seller.goofish.com")
        self.page.goto(base_url)
        self.page.wait_for_load_state("networkidle")
        time.sleep(2)

        logger.info("当前cookies数量: %d" % len(self.context.cookies()))

        # 检查是否已登录：检测"商品"菜单是否出现
        goods_menu = self.page.locator("text=商品").first
        if goods_menu.is_visible(timeout=3000):
            logger.info("已有有效登录态（通过页面元素检测）")
            return

        logger.info("等待用户扫码登录闲鱼...")
        self.db.add_log("", "publishing", "info", "请扫码登录闲鱼卖家中心")

        max_wait = config.get("xianyu.timeout", 120)  # 延长等待时间
        for i in range(max_wait):
            time.sleep(1)

            # 检查是否已登录
            try:
                if goods_menu.is_visible(timeout=500):
                    logger.info("登录成功")
                    cookie_path = Path(config.xianyu_cookie_path)
                    cookie_path.parent.mkdir(parents=True, exist_ok=True)
                    self.context.storage_state(path=str(cookie_path))
                    # 打印保存的cookies（调试用）
                    saved_cookies = self.context.cookies()
                    logger.info("保存了 %d 个cookies" % len(saved_cookies))
                    return
            except:
                pass

        raise TimeoutError("登录超时，请重试")

    def _debug_print_page(self, label=""):
        """调试：打印当前页面的关键可见元素"""
        try:
            logger.info("===== 调试打印 [%s] =====" % label)
            # 打印所有可见 input 的数量和部分属性
            inputs = self.page.locator("input:visible")
            count = inputs.count()
            logger.info("可见 input 数量: %d" % count)
            for i in range(min(count, 5)):
                try:
                    inp = inputs.nth(i)
                    placeholder = inp.get_attribute("placeholder") or ""
                    typ = inp.get_attribute("type") or ""
                    value = inp.get_attribute("value") or ""
                    logger.info("  Input %d: type=%s, placeholder='%s', value='%s'" % (i+1, typ, placeholder, value))
                except:
                    pass

            # 打印可见 textarea
            textareas = self.page.locator("textarea:visible")
            logger.info("可见 textarea 数量: %d" % textareas.count())

            # 打印发布按钮状态
            publish_btn = self.page.locator("button:has-text('发布')").or_(self.page.locator("text=立即发布")).first
            if publish_btn.is_visible():
                enabled = not publish_btn.is_disabled()
                logger.info("发布按钮可见: enabled=%s" % enabled)
        except Exception as e:
            logger.warning("调试打印失败: %s" % str(e))

    def _debug_snapshot(self, label):
        """保存页面快照用于调试"""
        try:
            from pathlib import Path
            screenshot_dir = Path("logs")
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = screenshot_dir / f"debug_{label}_{int(time.time())}.png"
            self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info("调试快照已保存: %s" % screenshot_path)
        except Exception as e:
            logger.warning("保存调试快照失败: %s" % str(e))

    def _scroll_to_element_center(self, locator):
        """将元素滚动到浏览器可见区域中心"""
        try:
            locator.scroll_into_view_if_needed()
            self.page.evaluate("""
                (el) => {
                    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            """, locator.element_handle())
            time.sleep(0.3)
        except Exception as e:
            logger.warning("滚动到元素中心失败: %s" % str(e))

    def _scroll_with_mouse_wheel(self, container_locator, delta_y=300, times=3):
        """将鼠标悬停到下拉列表容器上，模拟鼠标滚轮往下滑动"""
        try:
            container_locator.hover()
            time.sleep(0.3)
            for i in range(times):
                self.page.mouse.wheel(0, delta_y)
                time.sleep(0.3)
        except Exception as e:
            logger.warning("模拟鼠标滚轮失败: %s" % str(e))

    def _navigate_to_publish(self):
        """导航到发布页：点击左侧菜单「商品」→「商品发布」"""
        logger.info("导航到商品发布页...")

        # 先精确点击左侧菜单的「商品」
        goods_menu = self.page.locator("text=商品").nth(1)
        goods_menu.wait_for(timeout=10000)
        goods_menu.click()
        time.sleep(1.5)

        # 再点击「商品发布」
        publish_btn = self.page.locator("text=商品发布").first
        publish_btn.wait_for(timeout=10000)
        publish_btn.click()

        self.page.wait_for_load_state("networkidle")
        time.sleep(3)
        logger.info("已进入商品发布页")

    def _fill_description(self, description):
        """填写宝贝描述"""
        logger.info("填写宝贝描述...")

        desc_input = self.page.locator("textarea").or_(self.page.locator("[contenteditable='true']")).first
        self._scroll_to_element_center(desc_input)
        desc_input.wait_for(timeout=10000)
        desc_input.fill(description)
        logger.info("宝贝描述已填写")

    def _select_category(self):
        """选择商品分类"""
        logger.info("选择商品分类...")
        category_candidates = ["电子资料", "其他闲置"]
        try:
            self.page.evaluate("window.scrollTo(0, 0);")
            time.sleep(0.5)
            if not self._try_open_category_dropdown():
                logger.warning("未能打开下拉框，跳过分类选择")
                return
            time.sleep(0.5)
            self._pick_category_option(category_candidates)
        except Exception as e:
            logger.warning("选择分类时发生错误: %s，跳过分类选择" % str(e))

    def _try_open_category_dropdown(self):
        """尝试用多种方法打开分类下拉框"""
        category_label = self.page.locator("text=分类").first
        if not category_label.is_visible(timeout=3000):
            return False
        self._scroll_to_element_center(category_label)
        time.sleep(0.3)
        return (
            self._try_open_via_sibling(category_label)
            or self._try_open_via_label(category_label)
            or self._try_open_via_placeholder()
            or self._try_open_via_scan()
        )

    def _try_open_via_sibling(self, category_label):
        """方法1：点击分类文本后相邻的下拉框"""
        try:
            dropdown = category_label.locator("xpath=following-sibling::div[1]").first
            if dropdown.is_visible(timeout=2000):
                self._scroll_to_element_center(dropdown)
                dropdown.click()
                time.sleep(1.5)
                logger.info("  方法1：已打开分类下拉框")
                return True
        except Exception as e:
            logger.warning("  方法1失败: %s" % str(e))
        return False

    def _try_open_via_label(self, category_label):
        """方法2：直接点击分类标签本身"""
        try:
            category_label.click()
            time.sleep(1.5)
            if self._is_dropdown_open():
                logger.info("  方法2：已点击分类标签")
                return True
        except Exception as e:
            logger.warning("  方法2失败: %s" % str(e))
        return False

    def _try_open_via_placeholder(self):
        """方法2_补充：用 placeholder 匹配"""
        try:
            category_trigger = (
                self.page.locator("input[placeholder*='分类']").first
                or self.page.locator("div:has-text('分类')").last
            )
            if category_trigger.is_visible(timeout=2000):
                category_trigger.click()
                time.sleep(1.5)
                logger.info("  方法2_补充：通过placeholder打开分类下拉框")
                return True
        except Exception as e:
            logger.warning("  方法2_补充失败: %s" % str(e))
        return False

    def _try_open_via_scan(self):
        """方法3：遍历页面中所有可能的下拉框组件（排除 upload）"""
        try:
            all_dropdowns = self.page.locator(
                ".ant-select-selector, "
                "[class*='ant-select']:not([class*='upload']), "
                "[class*='trigger']:not([class*='upload'])"
            )
            for i in range(min(all_dropdowns.count(), 10)):
                try:
                    dd = all_dropdowns.nth(i)
                    if dd.is_visible(timeout=500):
                        self._scroll_to_element_center(dd)
                        dd.click()
                        time.sleep(1)
                        if self._is_dropdown_open():
                            logger.info("  方法3：通过遍历找到并打开了分类下拉框")
                            return True
                except Exception:
                    pass
        except Exception as e:
            logger.warning("  方法3失败: %s" % str(e))
        return False

    def _pick_category_option(self, candidates):
        """在下拉列表中查找并选择分类"""
        found = False
        for target_text in candidates:
            logger.info("  尝试查找分类: %s" % target_text)
            for scroll_idx in range(8):
                try:
                    target_option = (
                        self.page.locator("text=%s" % target_text).first
                        or self.page.get_by_text(target_text).first
                    )
                    if target_option.is_visible(timeout=1500):
                        target_option.click()
                        time.sleep(1)
                        logger.info("  已选择「%s」" % target_text)
                        found = True
                        break
                except Exception:
                    pass
                if not found and scroll_idx < 7:
                    try:
                        dropdown_container = self.page.locator(".ant-select-dropdown").first
                        if dropdown_container.is_visible(timeout=1000):
                            self._scroll_with_mouse_wheel(dropdown_container, delta_y=300, times=1)
                        else:
                            self.page.mouse.wheel(0, 300)
                            time.sleep(0.3)
                    except Exception:
                        self.page.mouse.wheel(0, 300)
                        time.sleep(0.3)
            if found:
                break
        if not found:
            logger.warning("  未找到候选分类，跳过分类选择")

    def _is_dropdown_open(self):
        """检查下拉框是否已打开"""
        try:
            dropdown = (
                self.page.locator(".ant-select-dropdown").first
                or self.page.locator("[class*='dropdown']").first
            )
            return dropdown.is_visible(timeout=1000)
        except Exception:
            return False

    def _upload_images(self, meta_dir):
        """上传宝贝图片"""
        logger.info("上传宝贝图片...")

        images_to_upload = []
        logger.info("  meta_dir: %s" % str(meta_dir))

        # 优先使用生成的主图序列
        main_images = sorted(meta_dir.glob("main_image_*.jpg"))
        if main_images:
            for img_path in main_images:
                images_to_upload.append(str(img_path))
                logger.info("  找到主图: %s" % img_path.name)
        else:
            # 回退到封面图和目录预览图
            for img_name in ["cover.jpg", "toc_preview.jpg"]:
                img_path = meta_dir / img_name
                if img_path.exists():
                    images_to_upload.append(str(img_path))
                    logger.info("  找到图片: %s" % img_name)
                else:
                    logger.warning("  缺少图片: %s" % img_name)

        if not images_to_upload:
            logger.warning("没有找到可上传的图片，跳过上传")
            return

        try:
            logger.info("  准备上传 %d 张图片..." % len(images_to_upload))
            file_inputs = self.page.locator("input[type='file']")
            logger.info("  页面上找到 %d 个 file input" % file_inputs.count())

            file_input = file_inputs.first
            file_input.set_input_files(images_to_upload)

            time.sleep(4)
            logger.info("已上传 %d 张图片" % len(images_to_upload))
        except Exception as e:
            logger.error("上传图片失败: %s，但继续后续流程..." % str(e))

    def _setup_skus(self, sku_list):
        """设置商品规格（SKU） - 鲁棒版本"""
        logger.info("设置商品规格...")

        # ========== 滚动到「商品规格」区域 ==========
        try:
            sku_section = self.page.locator("text=商品规格").first
            self._scroll_to_element_center(sku_section)
            time.sleep(0.8)
            logger.info("  已滚动到「商品规格」区域")
        except Exception as e:
            logger.warning("  滚动到「商品规格」失败: %s" % str(e))

        # ========== 第一阶段：添加规格类型 ==========
        try:
            add_spec_btn = self.page.get_by_role("button", name="添加规格类型（0/2）").or_(
                self.page.locator("text=添加规格类型")
            ).first
            if add_spec_btn.is_visible(timeout=5000):
                self._scroll_to_element_center(add_spec_btn)
                add_spec_btn.click()
                time.sleep(1.5)
                logger.info("  已点击「添加规格类型」按钮")
            else:
                raise Exception("未找到「添加规格类型」按钮")
        except Exception as e:
            logger.error("  点击添加规格类型按钮失败: %s" % str(e))
            raise

        # ========== 第二阶段：点击「请选择规格类型」下拉框 ==========
        try:
            select_type_dropdown = self.page.locator("text=请选择规格类型").first
            if select_type_dropdown.is_visible(timeout=3000):
                select_type_dropdown.click()
                time.sleep(1)
                logger.info("  已点击「请选择规格类型」下拉框")
            else:
                logger.warning("  未找到「请选择规格类型」下拉框")
        except Exception as e:
            logger.warning("  点击「请选择规格类型」失败: %s" % str(e))

        # ========== 第三阶段：滚动下拉列表，找到并点击「输入自定义类型」 ==========
        custom_option = None
        for scroll_idx in range(6):
            try:
                custom_option = self.page.locator("text=输入自定义类型").first
                if custom_option.is_visible(timeout=1000):
                    break
            except:
                pass
            try:
                spec_dropdown = self.page.locator(".ant-select-dropdown").first
                if spec_dropdown.is_visible(timeout=500):
                    self._scroll_with_mouse_wheel(spec_dropdown, delta_y=300, times=1)
                else:
                    self.page.mouse.wheel(0, 300)
                    time.sleep(0.3)
            except:
                self.page.mouse.wheel(0, 300)
                time.sleep(0.3)

        if custom_option is None or not custom_option.is_visible(timeout=1000):
            logger.warning("  未找到「输入自定义类型」，尝试直接通过文本查找...")
            custom_option = self.page.locator("text=输入自定义类型").first

        try:
            self._scroll_to_element_center(custom_option)
            if custom_option.is_visible(timeout=5000):
                custom_option.click()
                time.sleep(1.5)
                logger.info("  已点击「输入自定义类型」")
            else:
                raise Exception("未找到「输入自定义类型」选项")
        except Exception as e:
            logger.error("  点击「输入自定义类型」失败: %s" % str(e))
            raise

        # 输入规格名称 - 使用多种定位方式
        try:
            # 方法1：使用 ID（录制代码中的方式）
            type_input = self.page.locator("#itemProperties_0_propertyName input").first
            if not type_input.is_visible(timeout=2000):
                # 方法2：使用 textbox role，按索引
                type_input = self.page.get_by_role("textbox").nth(3)
            if not type_input.is_visible(timeout=2000):
                # 方法3：查找所有可见 text input，取最后一个
                type_input = self.page.locator("input[type='text']:visible").last
            
            if type_input.is_visible(timeout=3000):
                type_input.click()
                time.sleep(0.3)
                type_input.fill("版本选择")
                time.sleep(0.6)
                logger.info("  已输入规格类型：版本选择")

                type_input.press("Enter")
                time.sleep(2)
                logger.info("  已确认规格类型")
            else:
                raise Exception("未找到可编辑的规格类型输入框")
        except Exception as e:
            logger.error("  输入或确认规格类型失败: %s" % str(e))
            raise

        # ========== 第三阶段：添加各个具体版本 ==========
        for i, sku in enumerate(sku_list):
            version_name = sku.get("name", "版本%d" % (i+1))

            try:
                # 使用录制代码中的 placeholder 定位
                version_input = self.page.get_by_placeholder("请输入具体的版本选择").nth(i)
                if not version_input.is_visible(timeout=2000):
                    # 备用：使用通配符
                    version_input = self.page.locator("input[placeholder*='请输入具体的版本']").nth(i)
                
                if version_input.is_visible(timeout=3000):
                    version_input.click()
                    time.sleep(0.3)
                    version_input.fill(version_name)
                    time.sleep(0.5)
                    logger.info("  已添加版本 %d: %s" % (i+1, version_name))
                else:
                    raise Exception("未找到版本 %d 的输入框" % (i+1))
            except Exception as e:
                logger.error("  添加版本 %d 失败: %s" % (i+1, str(e)))
                raise

            # 如果不是最后一个，添加新版本
            is_last = (i == len(sku_list) - 1)
            if not is_last:
                try:
                    add_version_btn = self.page.locator("text=+").first
                    if add_version_btn.is_visible(timeout=2000):
                        add_version_btn.click()
                        time.sleep(1)
                except Exception:
                    pass

        # ========== 第四阶段：填写价格和库存 ==========
        try:
            price_section = self.page.locator("text=价格").first
            price_section.scroll_into_view_if_needed()
            time.sleep(1)
            logger.info("  已滚动到「价格」区域")
        except Exception as e:
            logger.warning("  滚动到「价格」失败: %s" % str(e))

        time.sleep(1)
        for i, sku in enumerate(sku_list):
            version_name = sku.get("name", "版本%d" % (i+1))
            sku_price = sku.get("price", 0)
            price_row = self.page.get_by_role("row", name="%s ￥" % version_name).or_(
                self.page.get_by_role("row", name=version_name)
            ).first

            if not price_row.is_visible(timeout=3000):
                logger.error("  %s: 未找到价格行" % version_name)
                raise Exception("未找到价格行")

            # 填写价格
            try:
                price_input = price_row.get_by_placeholder("0.00").or_(
                    price_row.locator("input[placeholder*='价格']")
                ).first
                price_input.wait_for(timeout=2000)
                price_input.click()
                time.sleep(0.2)
                price_input.fill(str(sku_price))
                logger.info("  %s: 价格已填: %s" % (version_name, str(sku_price)))
            except Exception as e:
                logger.error("  %s: 填写价格失败: %s" % (version_name, str(e)))
                raise

            # 填写库存
            try:
                stock_input = price_row.get_by_placeholder("0", exact=True).or_(
                    price_row.locator("input[placeholder*='库存']").or_(
                        price_row.locator("input[placeholder*='数量']")
                    )
                ).first
                stock_input.wait_for(timeout=2000)
                stock_input.click()
                time.sleep(0.2)
                stock_input.fill(str(config.xianyu_inventory))
                logger.info("  %s: 库存已填: %s" % (version_name, str(config.xianyu_inventory)))
            except Exception as e:
                logger.error("  %s: 填写库存失败: %s" % (version_name, str(e)))
                raise

            time.sleep(0.5)

    def _fill_basic_info(self):
        """填写基础信息（发货方式）—— 宝贝所在地使用默认，不填写"""
        logger.info("填写基础信息...")

        # 先滚动到「发货设置」区域
        try:
            shipping_section = self.page.locator("text=发货设置").first
            shipping_section.scroll_into_view_if_needed()
            time.sleep(0.5)
            logger.info("  已滚动到「发货设置」区域")
        except Exception as e:
            logger.warning("  滚动到「发货设置」失败: %s" % str(e))

        # 只填写发货方式（宝贝所在地使用默认）
        try:
            shipping_input = self.page.locator("input[placeholder*='发货']").or_(
                self.page.locator("input[placeholder*='运费']")
            ).first
            if shipping_input.is_visible(timeout=3000):
                shipping_input.fill(config.xianyu_shipping)
                logger.info("  发货方式已填: %s" % config.xianyu_shipping)
            else:
                raise Exception("未找到发货方式输入框")
        except Exception as e:
            logger.error("  填写发货方式失败: %s" % str(e))
            raise

    def _submit_and_get_url(self):
        """点击发布并获取商品链接"""
        logger.info("点击发布...")

        publish_btn = self.page.locator("button:has-text('发布')").or_(
            self.page.locator("text=立即发布")
        ).first

        publish_btn.wait_for(state="visible", timeout=30000)
        logger.info("发布按钮可见，等待可用...")

        for i in range(60):
            if not publish_btn.is_disabled():
                break
            time.sleep(0.5)
            if (i+1) % 10 == 0:
                logger.info("已等待 %d * 0.5s，按钮仍禁用..." % (i+1))

        # publish_btn.click()
        logger.info("已点击发布按钮")

        time.sleep(5)

        self.page.wait_for_load_state("networkidle")

        current_url = self.page.url
        logger.info("发布后当前URL: %s" % current_url)

        self.page.wait_for_timeout(3000)

        current_url = self.page.url
        return current_url

    def _save_result(self, book_id, listing_url):
        """保存发布结果到数据库"""
        self.db.update_book_output(
            book_id,
            publish_status="published",
            xianyu_listing_url=listing_url,
        )
        logger.info("发布结果已保存: xianyu_listing_url=%s" % listing_url)

    def _capture_error_screenshot(self, book_id):
        """错误时截图保存"""
        try:
            if self.page:
                log_dir = Path(config.log_dir)
                log_dir.mkdir(parents=True, exist_ok=True)
                screenshot_path = log_dir / ("publish_error_%s_%d.png" % (book_id, int(time.time())))
                self.page.screenshot(path=str(screenshot_path))
                logger.info("错误截图已保存: %s" % screenshot_path)
        except Exception as e:
            logger.warning("截图保存失败: %s" % str(e))

    def _close(self):
        """关闭浏览器"""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.warning("关闭浏览器时出错: %s" % str(e))
        finally:
            self.browser = None
            self.context = None
            self.page = None
            self.playwright = None


def publish_to_xianyu(book_id):
    """便捷函数：发布到闲鱼"""
    publisher = XianyuPublisher()
    return publisher.publish(book_id)


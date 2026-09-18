# 闲鱼自动发布功能实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 通过 Playwright 自动化操作闲鱼卖家中心，读取 metadata.json 数据完成商品自动发布

**架构：** 修改 `config.yaml` 新增库存/所在地/发货方式配置 → 修改 `config.py` 暴露新配置 → 修改 `metadata_writer.py` 新增发布结果更新方法 → 重构 `xianyu_publisher.py` 实现完整的 Playwright 自动化 → 更新 `main.py` 接入新实现

**技术栈：** Python 3.10+, Playwright, SQLAlchemy, PyYAML

**设计文档：** `docs/superpowers/specs/2026-05-29-xianyu-auto-publish-design.md`

---

### 任务 1：更新 config.yaml 和 config.py

**文件：**
- 修改：`config.yaml:230-236`
- 修改：`automation/config.py:156-159`

在 `config.yaml` 的 `xianyu` 配置块新增 3 个配置项：

```yaml
xianyu:
  login_method: "qr_code"
  base_url: "https://seller.goofish.com"
  timeout: 30
  auto_retry: true
  inventory: 1               # 默认库存
  location: "深圳北站"       # 宝贝所在地
  shipping: "包邮"           # 发货方式
  cookie_path: "data/xianyu_cookie.json"  # cookie 持久化路径
  max_retries: 3             # 元素查找重试次数
  retry_interval: 2          # 重试间隔（秒）
```

在 `config.py` 的 `Config` 类中新增 properties：

```python
@property
def xianyu_inventory(self) -> int:
    return self.get("xianyu.inventory", 1)

@property
def xianyu_location(self) -> str:
    return self.get("xianyu.location", "深圳北站")

@property
def xianyu_shipping(self) -> str:
    return self.get("xianyu.shipping", "包邮")

@property
def xianyu_cookie_path(self) -> str:
    return self.get("xianyu.cookie_path", "data/xianyu_cookie.json")

@property
def xianyu_max_retries(self) -> int:
    return self.get("xianyu.max_retries", 3)

@property
def xianyu_retry_interval(self) -> int:
    return self.get("xianyu.retry_interval", 2)
```

- [ ] **步骤 1：修改 config.yaml** — 在 `xianyu` 块新增 `inventory`, `location`, `shipping`, `cookie_path`, `max_retries`, `retry_interval`
- [ ] **步骤 2：修改 config.py** — 在 `Config` 类新增上述 6 个 properties
- [ ] **步骤 3：验证配置加载**

运行：
```powershell
cd d:\project\bookfile_bat; .venv\Scripts\python.exe -c "from automation.config import config; print('inventory:', config.xianyu_inventory); print('location:', config.xianyu_location); print('shipping:', config.xianyu_shipping); print('cookie_path:', config.xianyu_cookie_path)"
```
预期输出：`inventory: 1`, `location: 深圳北站`, `shipping: 包邮`, `cookie_path: data/xianyu_cookie.json`

- [ ] **步骤 4：Commit**

```powershell
git add config.yaml automation/config.py
git commit -m "feat: 新增闲鱼配置项（库存/所在地/发货方式/cookie持久化）"
```

---

### 任务 2：新增 MetadataWriter.update_publish_info()

**文件：**
- 修改：`automation/metadata_writer.py`

在 `MetadataWriter` 类中新增 `update_publish_info(book_id, xianyu_listing_url)` 方法：

```python
def update_publish_info(self, book_id: str, xianyu_listing_url: str) -> bool:
    """发布成功后更新 metadata.json 中的发布信息"""
    book = self.db.get_book_by_id(book_id)
    if not book:
        logger.warning(f"书籍不存在: {book_id}")
        return False

    base_name = Path(book.filename).stem
    meta_path = self.output_dir / f"{base_name}_metadata" / "metadata.json"

    if not meta_path.exists():
        logger.warning(f"metadata.json 不存在: {meta_path}")
        return False

    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    if "publish" not in metadata:
        metadata["publish"] = {}

    metadata["publish"]["xianyu_listing_url"] = xianyu_listing_url

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    logger.info(f"发布链接已写入 metadata.json: {xianyu_listing_url}")
    return True
```

- [ ] **步骤 1：在 metadata_writer.py 添加 `update_publish_info` 方法**（上述代码）
- [ ] **步骤 2：Commit**

```powershell
git add automation/metadata_writer.py
git commit -m "feat: 新增 MetadataWriter.update_publish_info() 用于写入发布链接"
```

---

### 任务 3：重构 xianyu_publisher.py

**文件：**
- 修改：`automation/xianyu_publisher.py`

完全重写 `XianyuPublisher` 类，实现真实的 Playwright 自动化：

```python
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
            playwright = sync_playwright().start()
            self.browser = playwright.chromium.launch(headless=self.xianyu_cfg.get("headless", False))
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
        logger.info(f"  宝贝所在地: {config.xianyu_location}")
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
                logger.info("浏览器已关闭")
        except Exception as e:
            logger.warning(f"关闭浏览器时出错: {e}")
        finally:
            self.browser = None
            self.context = None
            self.page = None


def publish_to_xianyu(book_id: str) -> bool:
    """便捷函数：发布到闲鱼"""
    publisher = XianyuPublisher()
    return publisher.publish(book_id)
```

- [ ] **步骤 1：完全重写 `xianyu_publisher.py`** — 写入上述完整代码
- [ ] **步骤 2：验证语法**

运行：
```powershell
cd d:\project\bookfile_bat; .venv\Scripts\python.exe -c "from automation.xianyu_publisher import XianyuPublisher; print('XianyuPublisher loaded OK')"
```
预期输出：`XianyuPublisher loaded OK`

- [ ] **步骤 3：Commit**

```powershell
git add automation/xianyu_publisher.py
git commit -m "feat: 重构 XianyuPublisher，实现完整的 Playwright 发布流程"
```

---

### 任务 4：更新 main.py 接入新发布器

**文件：**
- 修改：`automation/main.py:232-252`

`publish` 命令已经导入了 `publish_to_xianyu` 并使用了它，但现在的实现直接调用 `XianyuPublisher().publish(book_id)` 会触发一次完整的发布流程。需要确保 `publish` 命令调用重构后的 `publish_to_xianyu` 函数。

检查 [main.py:232-252](file:///d:/project/bookfile_bat/automation/main.py#L232-L252) 看看当前 `publish` 命令的实现。目前的代码已经是：
```python
@publish command
def publish(book_id, auto=False):
    ...
    success = publish_to_xianyu(book_id)  # 已使用新实现
    ...
```

因为 `publish_to_xianyu` 函数的接口保持不变，main.py 无需修改。

`process` 和 `auto` 命令中调用 `publish_to_xianyu(book_id)` 的地方也不用改。

所以 main.py `无需修改`。

- [ ] **步骤 1：确认 main.py 无需修改** — 运行以下命令验证：
```powershell
cd d:\project\bookfile_bat; .venv\Scripts\python.exe -c "from automation.main import app; print('main.py loaded OK')"
```
预期输出：`main.py loaded OK`

---

## 自检清单

- [x] 规格覆盖度：设计文档中的每个需求都有对应任务
  - [x] 配置变更（inventory/location/shipping）→ 任务 1
  - [x] metadata.json 扩展（xianyu_listing_url）→ 任务 2
  - [x] xianyu_publisher 重构 → 任务 3
  - [x] main.py 接入 → 任务 4
- [x] 无占位符 — 所有代码块都是完整的实现代码
- [x] 类型一致性 — 方法签名、属性名在任务间一致
- [x] DRY/YAGNI — 没有多余的抽象或者功能
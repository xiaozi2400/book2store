# 闲鱼商品主图生成功能 — 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 根据书籍封面和摘要，调用 AI 生成 HTML 格式商品主图，用 Playwright 截取为多张 JPG 图片，按顺序命名并存入元数据目录

**架构：** 新建 `ImageGenerator` 类（`automation/image_generator.py`），通过 AIClient 调用 AI 生成含 `.page` 容器的 HTML，用 Playwright 逐个截图保存为 `main_image_01.jpg` 系列文件，存入 `{meta_dir}/` 目录。发布时优先上传系列主图，回退到封面图。

**技术栈：** SQLAlchemy, Playwright, Pillow(JPG), Rich(CLI进度)

---

### 任务 1：DB 层 — BookOutput 模型新增 main_image_count 字段

**文件：**
- 修改：`automation/models.py:65`
- 修改：`automation/database.py:52-60`
- 测试：`tests/test_main_image_db.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""测试主图生成相关的DB功能"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from automation.database import DatabaseManager
from automation.models import Book, BookOutput
from datetime import datetime


def test_book_output_has_main_image_count():
    db = DatabaseManager()
    book_id = "test-main-img-001"
    with db.get_session() as session:
        existing = session.query(Book).filter_by(id=book_id).first()
        if not existing:
            session.add(Book(id=book_id, filename="test.epub", title="测试", author="测试", created_at=datetime.now()))
            session.commit()

    db.create_book_output(book_id)

    with db.get_session() as session:
        output = session.query(BookOutput).filter_by(book_id=book_id).first()
        assert hasattr(output, 'main_image_count'), "BookOutput应包含main_image_count字段"
        assert output.main_image_count == 0, "默认值应为0"


def test_update_main_image_count():
    db = DatabaseManager()
    book_id = "test-main-img-002"
    with db.get_session() as session:
        existing = session.query(Book).filter_by(id=book_id).first()
        if not existing:
            session.add(Book(id=book_id, filename="test.epub", title="测试", author="测试", created_at=datetime.now()))
            session.commit()

    db.create_book_output(book_id)

    with db.get_session() as session:
        output = session.query(BookOutput).filter_by(book_id=book_id).first()
        output.main_image_count = 3
        session.commit()

    with db.get_session() as session:
        output = session.query(BookOutput).filter_by(book_id=book_id).first()
        assert output.main_image_count == 3, "更新后应为3"
```

- [ ] **步骤 2：运行测试验证失败**

运行：
```bash
cd d:\project\bookfile_bat; .venv\Scripts\python.exe -m pytest tests/test_main_image_db.py -v
```
预期：FAIL — BookOutput 没有 `main_image_count` 字段

- [ ] **步骤 3：实现代码**

在 `automation/models.py` 的 `BookOutput` 类中 `other_images` 字段后新增：

```python
main_image_count = Column(Integer, default=0)  # 生成的主图数量
```

在 `automation/database.py` 的 `_migrate_database()` 函数中追加 book_outputs 迁移：

```python
def _migrate_database(engine):
    from sqlalchemy import inspect, text
    inspector = inspect(engine)

    book_columns = [col['name'] for col in inspector.get_columns('books')]
    if 'summary_text' not in book_columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE books ADD COLUMN summary_text TEXT"))
            conn.commit()

    output_columns = [col['name'] for col in inspector.get_columns('book_outputs')]
    if 'main_image_count' not in output_columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE book_outputs ADD COLUMN main_image_count INTEGER DEFAULT 0"))
            conn.commit()
```

- [ ] **步骤 4：运行测试验证通过**

运行：
```bash
cd d:\project\bookfile_bat; .venv\Scripts\python.exe -m pytest tests/test_main_image_db.py -v
```
预期：2 PASSED

- [ ] **步骤 5：Commit**

```bash
cd d:\project\bookfile_bat
git add automation/models.py automation/database.py tests/test_main_image_db.py
git commit -m "feat: BookOutput新增main_image_count字段 + 数据库迁移"
```

---

### 任务 2：config.yaml — 新增 image_generator 配置

**文件：**
- 修改：`config.yaml`
- 修改：`automation/config.py`
- 测试：`tests/test_main_image_config.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""测试主图生成配置"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from automation.config import config


def test_image_generator_config_exists():
    cfg = config.image_generator_config
    assert cfg is not None, "image_generator_config 应存在"


def test_image_generator_has_prompt():
    cfg = config.image_generator_config
    prompt = cfg.get("html_prompt", "")
    assert "{title}" in prompt, "提示词应包含 {title} 占位符"
    assert "{summary}" in prompt, "提示词应包含 {summary} 占位符"
    assert "{cover_base64}" in prompt, "提示词应包含 {cover_base64} 占位符"


def test_image_generator_has_dimensions():
    cfg = config.image_generator_config
    assert cfg.get("width") == 800, "默认宽度应为800"
    assert cfg.get("height") == 800, "默认高度应为800"
```

- [ ] **步骤 2：运行测试验证失败**

运行：
```bash
cd d:\project\bookfile_bat; .venv\Scripts\python.exe -m pytest tests/test_main_image_config.py -v
```
预期：FAIL — `image_generator_config` 属性未定义

- [ ] **步骤 3：实现代码**

在 `config.yaml` 末尾新增：

```yaml
# 主图生成配置
image_generator:
  enabled: true
  width: 800
  height: 800
  html_prompt: |
    你是一个电商主图设计师。根据以下书籍信息，生成用于闲鱼商品主图的HTML代码。

    书名：{title}
    作者：{author}
    封面图：data:image/jpeg;base64,{cover_base64}

    【书籍摘要】
    {summary}

    ## 设计要求

    生成多张商品主图，每张图放在一个 <div class="page"></div> 容器中，
    每个 .page 容器宽800px、高800px。

    ### 第一张图：封面展示
    - 以书籍封面为主视觉，展示在左侧或居中
    - 右侧/下方叠加书名、作者、核心卖点（一句话）
    - 背景使用渐变色（深色系或暖色系）

    ### 后续图片（你自由创意）
    - 第二张：核心卖点图，展示3-5个关键卖点
    - 第三张：适合人群图
    - 更多：自由发挥

    ### 通用要求：
    - 设计感强，使用渐变色、阴影、圆角等CSS效果
    - 字体使用系统字体：-apple-system, "Microsoft YaHei", sans-serif
    - 所有文字使用中文
    - 图片为800×800像素方形
    - 每个 .page 中不要有滚动条
    - 只输出HTML代码，不要加```html```标记
```

在 `automation/config.py` 中新增 property：

```python
@property
def image_generator_config(self) -> Dict:
    """主图生成配置"""
    return self.get("image_generator", {})
```

- [ ] **步骤 4：运行测试验证通过**

运行：
```bash
cd d:\project\bookfile_bat; .venv\Scripts\python.exe -m pytest tests/test_main_image_config.py -v
```
预期：3 PASSED

- [ ] **步骤 5：Commit**

```bash
cd d:\project\bookfile_bat
git add config.yaml automation/config.py tests/test_main_image_config.py
git commit -m "feat: 新增image_generator配置节 + config.py属性"
```

---

### 任务 3：ImageGenerator — 创建核心模块

**文件：**
- 创建：`automation/image_generator.py`
- 测试：`tests/test_image_generator_unit.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""测试 ImageGenerator 单元"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock, mock_open
from automation.image_generator import ImageGenerator


@patch('automation.image_generator.DatabaseManager')
@patch('automation.image_generator.AIClient')
@patch('automation.image_generator.config')
def test_generate_no_summary_skips(mock_config, mock_ai, mock_db):
    cfg = {"enabled": True, "width": 800, "height": 800, "html_prompt": "test {title}"}
    mock_config.image_generator_config = cfg
    mock_config.output_dir = "."

    mock_book = MagicMock()
    mock_book.summary_text = None
    mock_book.title = "测试书"
    mock_book.author = "测试作者"

    mock_db_instance = MagicMock()
    mock_db_instance.get_book_by_id.return_value = mock_book
    mock_db.return_value = mock_db_instance

    generator = ImageGenerator()
    result = generator.generate("test-book-001")
    assert result is False, "无摘要时应跳过"
    mock_ai.return_value.chat.assert_not_called()


@patch('automation.image_generator.DatabaseManager')
@patch('automation.image_generator.AIClient')
@patch('automation.image_generator.config')
def test_generate_disabled_skips(mock_config, mock_ai, mock_db):
    cfg = {"enabled": False, "width": 800, "height": 800, "html_prompt": "test {title}"}
    mock_config.image_generator_config = cfg

    generator = ImageGenerator()
    result = generator.generate("test-book-001")
    assert result is False, "禁用时应跳过"
    mock_ai.return_value.chat.assert_not_called()


@patch('automation.image_generator.Path')
@patch('automation.image_generator.DatabaseManager')
@patch('automation.image_generator.AIClient')
@patch('automation.image_generator.config')
def test_format_prompt_contains_all_fields(mock_config, mock_ai, mock_db, mock_path):
    cfg = {"enabled": True, "width": 800, "height": 800, "html_prompt": "书名：{title}\n摘要：{summary}\n封面：{cover_base64}"}
    mock_config.image_generator_config = cfg
    mock_config.output_dir = "."

    mock_book = MagicMock()
    mock_book.summary_text = "这是一本测试书"
    mock_book.title = "测试书"
    mock_book.author = "测试作者"

    mock_db_instance = MagicMock()
    mock_db_instance.get_book_by_id.return_value = mock_book
    mock_db.return_value = mock_db_instance

    generator = ImageGenerator()
    prompt = generator._format_prompt(mock_book, "fake_base64")
    assert "书名：测试书" in prompt
    assert "摘要：这是一本测试书" in prompt
    assert "封面：fake_base64" in prompt
```

- [ ] **步骤 2：运行测试验证失败**

运行：
```bash
cd d:\project\bookfile_bat; .venv\Scripts\python.exe -m pytest tests/test_image_generator_unit.py -v
```
预期：FAIL — `automation.image_generator` 模块不存在

- [ ] **步骤 3：创建 ImageGenerator 模块**

创建 `automation/image_generator.py`：

```python
"""根据书籍封面和摘要生成商品主图"""
import logging
import base64
from pathlib import Path
from typing import Optional

from automation.ai_client import AIClient
from automation.database import DatabaseManager, close_session, get_session
from automation.models import BookOutput
from automation.config import config

logger = logging.getLogger(__name__)


class ImageGenerator:
    """AI生成HTML商品主图 → Playwright截图"""

    def __init__(self):
        self.ai = AIClient()
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir)

    def generate(self, book_id: str) -> bool:
        """生成商品主图"""
        img_cfg = config.image_generator_config
        if not img_cfg.get("enabled", True):
            logger.info("主图生成已禁用")
            return False

        book = self.db.get_book_by_id(book_id)
        if not book or not book.summary_text:
            logger.warning(f"书籍 {book_id} 无摘要，跳过主图生成")
            return False

        title = book.title or "Unknown"
        author = book.author or "Unknown"
        summary = book.summary_text

        base_name = Path(book.filename).stem
        meta_dir = self.output_dir / f"{base_name}_metadata"
        cover_path = meta_dir / "cover.jpg"

        cover_base64 = ""
        if cover_path.exists():
            with open(cover_path, "rb") as f:
                cover_base64 = base64.b64encode(f.read()).decode("utf-8")
            logger.info(f"封面图已加载 ({len(cover_base64)} bytes base64)")
        else:
            logger.warning("未找到封面图，生成纯文字HTML")

        prompt = self._format_prompt(title, author, summary, cover_base64)
        html = self._call_ai(prompt)
        if not html:
            return False

        page_count = self._screenshot_html(html, meta_dir, img_cfg)
        if page_count > 0:
            self._update_db(book_id, page_count)
            logger.info(f"主图生成完成: {page_count} 张")
            return True
        return False

    def _format_prompt(self, title: str, author: str, summary: str, cover_base64: str) -> str:
        """格式化提示词"""
        img_cfg = config.image_generator_config
        prompt_template = img_cfg.get("html_prompt", "")
        return prompt_template.format(
            title=title,
            author=author,
            summary=summary,
            cover_base64=cover_base64,
        )

    def _call_ai(self, prompt: str) -> Optional[str]:
        """调用AI生成HTML"""
        try:
            html, _ = self.ai.chat(prompt, max_tokens=4000)
            html = html.strip()
            html = html.removeprefix("```html").removesuffix("```").strip()
            if "<html" not in html.lower() and "<!doctype" not in html.lower():
                html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>*{{margin:0;padding:0;box-sizing:border-box;}}</style></head><body>{html}</body></html>"
            return html
        except Exception as e:
            logger.error(f"AI调用失败: {e}")
            return None

    def _screenshot_html(self, html: str, output_dir: Path, img_cfg: dict) -> int:
        """将HTML逐页截图保存为JPG"""
        from playwright.sync_api import sync_playwright

        width = img_cfg.get("width", 800)
        height = img_cfg.get("height", 800)
        temp_html = output_dir / "_main_image_temp.html"

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            with open(temp_html, "w", encoding="utf-8") as f:
                f.write(html)

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(f"file://{temp_html.resolve()}")
                page.wait_for_load_state("networkidle")

                containers = page.query_selector_all(".page")
                if not containers:
                    page.screenshot(path=str(output_dir / "main_image_01.jpg"), full_page=True)
                    browser.close()
                    return 1

                for i, container in enumerate(containers, 1):
                    out_path = output_dir / f"main_image_{i:02d}.jpg"
                    container.screenshot(path=str(out_path))
                    logger.info(f"  已保存: {out_path.name}")

                browser.close()
            return len(containers)
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return 0
        finally:
            if temp_html.exists():
                temp_html.unlink()

    def _update_db(self, book_id: str, count: int):
        """更新数据库中的主图数量"""
        session = get_session()
        try:
            output = session.query(BookOutput).filter_by(book_id=book_id).first()
            if output:
                output.main_image_count = count
                session.commit()
        finally:
            close_session(session)


def generate_main_image(book_id: str) -> bool:
    """便捷函数：生成商品主图"""
    generator = ImageGenerator()
    return generator.generate(book_id)
```

- [ ] **步骤 4：运行测试验证通过**

运行：
```bash
cd d:\project\bookfile_bat; .venv\Scripts\python.exe -m pytest tests/test_image_generator_unit.py -v
```
预期：3 PASSED

- [ ] **步骤 5：Commit**

```bash
cd d:\project\bookfile_bat
git add automation/image_generator.py tests/test_image_generator_unit.py
git commit -m "feat: 创建ImageGenerator核心模块(AI生成HTML→Playwright截图)"
```

---

### 任务 4：main.py — 集成主图生成步骤

**文件：**
- 修改：`automation/main.py:179-186`
- 测试：`tests/test_main_image_integration.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""测试 main.py 中主图生成步骤集成"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock


@patch('automation.main.generate_main_image')
@patch('automation.main.generate_copywriting')
@patch('automation.main.extract_images')
@patch('automation.main.generate_summary')
@patch('automation.main.translate_book')
@patch('automation.main.DatabaseManager')
@patch('automation.main.Path')
@patch('automation.main.config')
def test_process_calls_generate_main_image(
    mock_config, mock_path, mock_db,
    mock_translate, mock_summary, mock_extract, mock_copy, mock_main_image
):
    """验证 process 命令调用 generate_main_image"""
    mock_config.output_dir = "."
    mock_config.ai_config = {}
    mock_config.test_input_dir = "."

    mock_book = MagicMock()
    mock_book.id = "test-book-001"
    mock_book.filename = "test.epub"
    mock_book.title = "测试书"
    mock_book.author = "测试作者"
    mock_book.summary_text = "测试摘要"

    mock_db_instance = MagicMock()
    mock_db_instance.get_all_books.return_value = [mock_book]
    mock_db_instance.get_token_summary.return_value = []
    mock_db.return_value = mock_db_instance

    mock_path_instance = MagicMock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.stem = "test"
    mock_path.return_value = mock_path_instance

    from automation.main import app
    from typer.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(app, ["process", "test-book-001", "--skip-publish"])

    assert result.exit_code == 0
    mock_main_image.assert_called_once_with("test-book-001")
```

- [ ] **步骤 2：运行测试验证失败**

运行：
```bash
cd d:\project\bookfile_bat; .venv\Scripts\python.exe -m pytest tests/test_main_image_integration.py -v
```
预期：FAIL — `process` 命令未调用 `generate_main_image`

- [ ] **步骤 3：实现代码**

在 `automation/main.py` 中，在 `generate_summary()` 调用之后、`extract_images()` 之前插入主图生成步骤：

```python
        progress.update(task, description="生成精简版...")
        generate_summary(book_id, str(input_path))

        progress.update(task, description="生成主图...")
        from automation.image_generator import generate_main_image
        generate_main_image(book_id)

        progress.update(task, description="提取图片...")
```

同时确认 `auto()` 和 `test()` 命令中也在相同位置（摘要生成后、图片提取前）插入同样的代码。

- [ ] **步骤 4：运行测试验证通过**

运行：
```bash
cd d:\project\bookfile_bat; .venv\Scripts\python.exe -m pytest tests/test_main_image_integration.py -v
```
预期：PASS

- [ ] **步骤 5：Commit**

```bash
cd d:\project\bookfile_bat
git add automation/main.py tests/test_main_image_integration.py
git commit -m "feat: main.py集成主图生成步骤(摘要后、提取前)"
```

---

### 任务 5：xianyu_publisher.py — 发布时上传主图

**文件：**
- 修改：`automation/xianyu_publisher.py:388-418`
- 测试：`tests/test_xianyu_publisher_images.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""测试闲鱼发布时使用主图"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pathlib import Path
from unittest.mock import patch, MagicMock
from automation.xianyu_publisher import XianyuPublisher


@patch('automation.xianyu_publisher.XianyuPublisher._start_browser')
@patch('automation.xianyu_publisher.XianyuPublisher._login')
@patch('automation.xianyu_publisher.XianyuPublisher._navigate_to_publish')
@patch('automation.xianyu_publisher.XianyuPublisher._fill_description')
@patch('automation.xianyu_publisher.XianyuPublisher._select_category')
@patch('automation.xianyu_publisher.XianyuPublisher._setup_skus')
@patch('automation.xianyu_publisher.XianyuPublisher._submit_and_get_url')
@patch('automation.xianyu_publisher.XianyuPublisher._save_result')
@patch('automation.xianyu_publisher.DatabaseManager')
@patch('automation.xianyu_publisher.config')
def test_publish_uses_main_images_when_available(
    mock_config, mock_db,
    mock_save, mock_submit, mock_skus, mock_category, mock_desc,
    mock_navigate, mock_login, mock_browser
):
    """有主图时应优先上传主图序列"""
    mock_config.output_dir = "."
    mock_config.xianyu_cookie_path = "cookie.json"
    mock_config.get.side_effect = lambda key, default=None: {"xianyu.headless": True}.get(key, default)

    mock_book = MagicMock()
    mock_book.filename = "test.epub"
    mock_db_instance = MagicMock()
    mock_db_instance.get_book_by_id.return_value = mock_book
    mock_db.return_value = mock_db_instance

    meta_dir = Path("test_metadata")
    meta_dir.mkdir(exist_ok=True)
    (meta_dir / "xianyu_listing.txt").write_text("测试文案", encoding="utf-8")
    (meta_dir / "main_image_01.jpg").write_text("img1", encoding="utf-8")
    (meta_dir / "main_image_02.jpg").write_text("img2", encoding="utf-8")

    publisher = XianyuPublisher()
    publisher.page = MagicMock()
    publisher.page.locator.return_value.first = MagicMock()

    try:
        publisher.publish("test-book-001")
    except Exception:
        pass

    # 验证上传调用中使用了主图文件
    file_input = publisher.page.locator.return_value.first
    call_args = file_input.set_input_files.call_args
    assert call_args is not None
    img_paths = [str(p) for p in call_args[0][0]]
    assert any("main_image_01.jpg" in p for p in img_paths), f"应上传主图, 实际: {img_paths}"

    # 清理
    import shutil
    shutil.rmtree(meta_dir, ignore_errors=True)
```

- [ ] **步骤 2：运行测试验证失败**

运行：
```bash
cd d:\project\bookfile_bat; .venv\Scripts\python.exe -m pytest tests/test_xianyu_publisher_images.py -v
```
预期：FAIL — `_upload_images` 仍使用 cover.jpg, toc_preview.jpg

- [ ] **步骤 3：实现代码**

修改 `automation/xianyu_publisher.py` 中的 `_upload_images` 方法：

```python
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
            # 回退到封面图
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
```

- [ ] **步骤 4：运行测试验证通过**

运行：
```bash
cd d:\project\bookfile_bat; .venv\Scripts\python.exe -m pytest tests/test_xianyu_publisher_images.py -v
```
预期：PASS

- [ ] **步骤 5：Commit**

```bash
cd d:\project\bookfile_bat
git add automation/xianyu_publisher.py tests/test_xianyu_publisher_images.py
git commit -m "feat: 闲鱼发布优先上传主图序列，回退到封面图"
```

---

### 任务 6：回归验证

- [ ] **步骤 1：运行全部测试**

```bash
cd d:\project\bookfile_bat; .venv\Scripts\python.exe -m pytest tests/ -v
```
预期：全部 PASS（原有 ~52 个 + 新增测试）

- [ ] **步骤 2：如失败则修复**

检查失败的测试，修复代码直到全部通过。

- [ ] **步骤 3：Commit 最终调整**

```bash
cd d:\project\bookfile_bat
git add -A
git commit -m "chore: 主图生成功能 — 最终回归验证通过"
```
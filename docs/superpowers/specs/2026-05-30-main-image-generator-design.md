# 闲鱼商品主图生成功能设计

## 背景

当前闲鱼发布流程中，商品主图使用 EPUB 封面图（`cover.jpg`），信息单一，缺乏营销吸引力。需要根据书籍封面和书籍摘要，调用 AI 模型生成设计感强的 HTML 格式商品主图，截图保存为图片供闲鱼发布使用。

## 目标

1. 根据书籍封面+摘要，调用 AI 生成多张 HTML 格式商品主图
2. 用 Playwright 截图保存为 JPG 图片，按顺序命名
3. 图片存入元数据目录，供闲鱼发布时按顺序上传
4. 提示词写在配置文件中，方便修改

## 整体架构

### 新增文件

| 文件 | 职责 |
|------|------|
| `automation/image_generator.py` | 主图生成核心逻辑：读取数据→调用AI→HTML截图→保存 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `automation/models.py` | `BookOutput` 新增 `main_image_count` 字段 |
| `automation/database.py` | 迁移逻辑添加新字段 |
| `config.yaml` | 新增 `image_generator` 配置节 + HTML prompt |
| `automation/main.py` | process/auto/test 新增主图生成步骤 |
| `automation/xianyu_publisher.py` | 上传主图替代/补充封面图 |

### 数据流

```
ContentSummarizer.generate()
  └── 摘要生成 → 存入 books.summary_text + cover.jpg → meta_dir

main.py process/auto/test
  ├── translate_book()           → (已有)
  ├── generate_summary()         → (已有) 生成摘要 + cover.jpg
  ├── generate_main_image()      → ★ 新增步骤
  │   └── ImageGenerator.generate(book_id)
  │       ├── 读取 summary_text + cover.jpg
  │       ├── 调用 AI → HTML (含多个 .page 容器)
  │       ├── Playwright 逐页截图
  │       └── 保存 main_image_01.jpg, main_image_02.jpg, ...
  ├── extract_images()           → (已有)
  ├── generate_copywriting()     → (已有)
  └── publish_to_xianyu()        → 上传 main_image_xx.jpg
```

## 详细设计

### 1. image_generator.py — 主图生成器

**类：`ImageGenerator`**

```python
class ImageGenerator:
    def __init__(self):
        self.ai = AIClient()
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir)

    def generate(self, book_id: str) -> bool:
        """生成商品主图"""
```

**`generate()` 内部流程：**

```
1. 读取书籍信息
   - db.get_book_by_id(book_id) → book.title, book.author, book.summary_text
   - 如果 summary_text 为空，记录警告并跳过

2. 读取封面图
   - 路径: {output_dir}/{base_name}_metadata/cover.jpg
   - 转为 base64 编码

3. 构造 HTML prompt
   - 从 config.image_generator_config 读取 html_prompt
   - 填充 {title}, {author}, {summary}, {cover_base64}

4. 调用 AI
   - ai_client.chat(prompt) → 返回 HTML 代码字符串
   - 清理 AI 返回内容（去除 ```html ``` 标记）

5. 写入临时 HTML 文件
   - 在 meta_dir 下创建临时文件 main_image_temp.html
   - 写入完整 HTML 文档（含 DOCTYPE html）

6. Playwright 截图
   - 启动 Playwright → 打开 HTML 文件
   - 查询所有 .page 容器: page.query_selector_all('.page')
   - 遍历每个元素:
     - element.screenshot(path=main_image_{i:02d}.jpg)
   - 关闭浏览器

7. 更新数据库
   - db.update_book_output(book_id, main_image_count=N)
   - 记录成功日志

8. 清理临时 HTML 文件
```

**截图核心代码逻辑：**

```python
from playwright.sync_api import sync_playwright

def _screenshot_pages(self, html_path: str, output_dir: Path, width: int, height: int) -> int:
    """截取HTML中所有.page容器为单独图片，返回截图数量"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(f"file://{html_path}")
        page.wait_for_load_state("networkidle")

        containers = page.query_selector_all('.page')
        for i, container in enumerate(containers, 1):
            out_path = output_dir / f"main_image_{i:02d}.jpg"
            container.screenshot(path=str(out_path))

        browser.close()
        return len(containers)
```

### 2. models.py — 新增字段

在 `BookOutput` 中新增：

```python
main_image_count = Column(Integer, default=0)  # 生成的主图数量
```

### 3. database.py — 迁移逻辑

在 `_migrate_database()` 中添加 `book_outputs` 表的字段检测：

```python
def _migrate_database(engine):
    inspector = inspect(engine)
    
    # books 表迁移
    book_columns = [col['name'] for col in inspector.get_columns('books')]
    if 'summary_text' not in book_columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE books ADD COLUMN summary_text TEXT"))
            conn.commit()

    # book_outputs 表迁移
    output_columns = [col['name'] for col in inspector.get_columns('book_outputs')]
    if 'main_image_count' not in output_columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE book_outputs ADD COLUMN main_image_count INTEGER DEFAULT 0"))
            conn.commit()
```

### 4. config.yaml — 新增配置

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

在 `automation/config.py` 中新增属性：

```python
@property
def image_generator_config(self) -> Dict:
    """主图生成配置"""
    return self.get("image_generator", {})
```

### 5. main.py — 新增命令步骤

在 `process()` 命令中，在 `generate_summary()` 之后、`extract_images()` 之前插入：

```python
progress.update(task, description="生成主图...")
from automation.image_generator import generate_main_image
generate_main_image(book_id)
```

`auto()` 和 `test()` 命令同样在摘要生成后插入主图生成步骤。

**顶层函数：**

```python
def generate_main_image(book_id: str) -> bool:
    """生成商品主图"""
    from automation.image_generator import ImageGenerator
    generator = ImageGenerator()
    return generator.generate(book_id)
```

### 6. xianyu_publisher.py — 上传主图

修改发布流程中的图片上传逻辑：

```python
def _get_image_files(self, meta_dir: Path) -> list:
    """获取按顺序排列的商品图片列表"""
    # 优先使用生成的主图
    main_images = sorted(meta_dir.glob("main_image_*.jpg"))
    if main_images:
        return main_images
    # 回退到封面图
    cover = meta_dir / "cover.jpg"
    return [cover] if cover.exists() else []
```

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| `summary_text` 为空 | 记录日志，跳过主图生成，流程继续 |
| `cover.jpg` 不存在 | 记录日志，生成不带封面图片的纯文字 HTML |
| AI 调用失败 | 记录错误，跳过主图生成 |
| AI 返回空 HTML | 记录错误，跳过主图生成 |
| HTML 中没有 `.page` 容器 | 将整个页面截图作为一张图 |
| Playwright 启动失败 | 记录错误，跳过主图生成 |
| 用户禁用（enabled: false） | 完全跳过 |

## 测试策略

| 测试 | 验证内容 |
|------|---------|
| `test_generate_no_summary_skips` | summary_text 为空时跳过 |
| `test_generate_no_cover_uses_text_only` | 无封面时生成纯文字 HTML |
| `test_ai_returns_html` | AI 调用返回含 .page 容器的 HTML |
| `test_screenshot_creates_images` | Playwright 截图能生成 JPG 文件 |
| `test_screenshot_multiple_pages` | 多 .page 容器生成多张图片 |
| `test_images_named_sequentially` | 图片按 main_image_01.jpg 格式命名 |
| `test_xianyu_publisher_uses_main_images` | 发布时优先使用主图 |
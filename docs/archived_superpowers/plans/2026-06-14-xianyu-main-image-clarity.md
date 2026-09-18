# 闲鱼主图清晰度优化 — 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把闲鱼主图从 800×800 物理像素 / 低质量 JPEG 升级到 1600×1600 / quality=92,提升手机端显示锐利度。不动 AI 设计、不动 prompt、不动闲鱼上传链路。

**架构：** 只动截图阶段两个文件。`config.yaml` 的 `image_generator` 段加 `device_scale_factor: 2` 和 `screenshot_quality: 92` 两个可调字段;`automation/image_generator.py` 的 `_screenshot_html` 读这两个字段,传给 Playwright 的 `new_page(device_scale_factor=...)` 和 `container.screenshot(type="jpeg", quality=...)`。

**技术栈：** Playwright(Python)、Pillow(验证)、pytest + unittest.mock(测试)

---

## 文件结构

| 文件 | 角色 | 改动类型 |
|---|---|---|
| `config.yaml` (line 338-341,`image_generator` 段) | 集中可调参数 | 新增 2 个字段 |
| `automation/image_generator.py:191-229` (`_screenshot_html`) | 截图实现 | 加 2 个参数透传 |
| `tests/test_image_generator_clarity.py` | 新建,测新参数透传 | 新建 |

无新增模块、无 DB 变更、无 AI prompt 变更。改动局限于截图阶段。

---

### Task 1:配置层 — `config.yaml` 新增两个可调字段

**Files:**
- Modify: `config.yaml:338-341`(`image_generator` 段)

- [ ] **Step 1:在 `image_generator` 段新增字段**

打开 `config.yaml`,定位到 line 338-341:

```yaml
image_generator:
  enabled: true
  width: 800
  height: 800
```

修改为:

```yaml
image_generator:
  enabled: true
  width: 800
  height: 800
  # 截图物理像素密度倍率(对应 CSS 800×800 → 输出 1600×1600 物理像素)
  device_scale_factor: 2
  # 容器截图的 JPEG 质量(0-100),Playwright 默认 80 偏低
  screenshot_quality: 92
```

- [ ] **Step 2:语法验证**

运行:
```bash
cd d:\project\bookfile_bat
python -c "import yaml; cfg = yaml.safe_load(open('config.yaml')); print(cfg['image_generator'])"
```

预期输出(键值):
```
{'enabled': True, 'width': 800, 'height': 800, 'device_scale_factor': 2, 'screenshot_quality': 92}
```

- [ ] **Step 3:Commit**

```bash
cd d:\project\bookfile_bat
git add config.yaml
git commit -m "config: image_generator 新增 device_scale_factor 和 screenshot_quality"
```

---

### Task 2:测试 — `_screenshot_html` 透传新参数

**Files:**
- Create: `tests/test_image_generator_clarity.py`

- [ ] **Step 1:编写失败的测试**

新建 `tests/test_image_generator_clarity.py`:

```python
"""测试 ImageGenerator 截图参数透传(清晰度优化)"""
import sys, os
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from automation.image_generator import ImageGenerator


def _build_generator_with_config(cfg: dict) -> ImageGenerator:
    """构造一个 ImageGenerator,通过 mock 让 config 可控"""
    with patch('automation.image_generator.config') as mock_config, \
         patch('automation.image_generator.AIClient'), \
         patch('automation.image_generator.DatabaseManager'):
        mock_config.image_generator_config = cfg
        mock_config.output_dir = "."
        gen = ImageGenerator()
    return gen


@patch('automation.image_generator.sync_playwright')
def test_screenshot_passes_device_scale_factor(mock_sync_playwright):
    """device_scale_factor 应透传到 browser.new_page"""
    cfg = {
        "enabled": True, "width": 800, "height": 800,
        "device_scale_factor": 2, "screenshot_quality": 92,
    }
    gen = _build_generator_with_config(cfg)

    # 构造 playwright mock 链
    mock_container = MagicMock()
    mock_page = MagicMock()
    mock_page.query_selector_all.return_value = [mock_container]
    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser
    mock_sync_playwright.return_value.__enter__.return_value = mock_p

    # 调 _screenshot_html,output_dir 用一个临时目录
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        gen._screenshot_html(
            html="<html><body><div class='page'></div></body></html>",
            output_dir=__import__('pathlib').Path(tmp),
            img_cfg=cfg,
        )

    # 断言:new_page 收到 viewport + device_scale_factor
    kwargs = mock_browser.new_page.call_args.kwargs
    assert kwargs.get("viewport") == {"width": 800, "height": 800}, \
        f"viewport 应是 {{'width': 800, 'height': 800}},实际 {kwargs.get('viewport')}"
    assert kwargs.get("device_scale_factor") == 2, \
        f"device_scale_factor 应是 2,实际 {kwargs.get('device_scale_factor')}"


@patch('automation.image_generator.sync_playwright')
def test_screenshot_passes_jpeg_quality(mock_sync_playwright):
    """screenshot_quality 应透传到 container.screenshot 的 type/quality"""
    cfg = {
        "enabled": True, "width": 800, "height": 800,
        "device_scale_factor": 2, "screenshot_quality": 92,
    }
    gen = _build_generator_with_config(cfg)

    mock_container = MagicMock()
    mock_page = MagicMock()
    mock_page.query_selector_all.return_value = [mock_container]
    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser
    mock_sync_playwright.return_value.__enter__.return_value = mock_p

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        gen._screenshot_html(
            html="<html><body><div class='page'></div></body></html>",
            output_dir=__import__('pathlib').Path(tmp),
            img_cfg=cfg,
        )

    # 断言:container.screenshot 收到 type='jpeg' + quality=92
    ckwargs = mock_container.screenshot.call_args.kwargs
    assert ckwargs.get("type") == "jpeg", \
        f"screenshot type 应是 'jpeg',实际 {ckwargs.get('type')}"
    assert ckwargs.get("quality") == 92, \
        f"screenshot quality 应是 92,实际 {ckwargs.get('quality')}"


@patch('automation.image_generator.sync_playwright')
def test_screenshot_defaults_when_config_missing(mock_sync_playwright):
    """config 缺新字段时,默认值应为 device_scale_factor=2, quality=92"""
    cfg = {"enabled": True, "width": 800, "height": 800}  # 无新字段
    gen = _build_generator_with_config(cfg)

    mock_container = MagicMock()
    mock_page = MagicMock()
    mock_page.query_selector_all.return_value = [mock_container]
    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser
    mock_sync_playwright.return_value.__enter__.return_value = mock_p

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        gen._screenshot_html(
            html="<html><body><div class='page'></div></body></html>",
            output_dir=__import__('pathlib').Path(tmp),
            img_cfg=cfg,
        )

    kwargs = mock_browser.new_page.call_args.kwargs
    assert kwargs.get("device_scale_factor") == 2, \
        f"缺省时 device_scale_factor 应是 2,实际 {kwargs.get('device_scale_factor')}"

    ckwargs = mock_container.screenshot.call_args.kwargs
    assert ckwargs.get("type") == "jpeg", "缺省时 type 应是 jpeg"
    assert ckwargs.get("quality") == 92, f"缺省时 quality 应是 92,实际 {ckwargs.get('quality')}"
```

- [ ] **Step 2:运行测试验证失败**

```bash
cd d:\project\bookfile_bat
.venv\Scripts\python.exe -m pytest tests/test_image_generator_clarity.py -v
```

预期:3 个测试全部 FAIL(因为 `_screenshot_html` 当前没传 `device_scale_factor` / `type` / `quality`)。

- [ ] **Step 3:实现 `_screenshot_html`**

打开 `automation/image_generator.py`,定位到 line 191-229 的 `_screenshot_html` 方法,整段替换为:

```python
    def _screenshot_html(self, html: str, output_dir: Path, img_cfg: dict) -> int:
        """将HTML逐页截图保存为JPG(物理像素 2×,quality=92)"""
        from playwright.sync_api import sync_playwright

        width = img_cfg.get("width", 800)
        height = img_cfg.get("height", 800)
        device_scale_factor = img_cfg.get("device_scale_factor", 2)
        jpeg_quality = img_cfg.get("screenshot_quality", 92)
        temp_html = output_dir / "_main_image_temp.html"

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            with open(temp_html, "w", encoding="utf-8") as f:
                f.write(html)

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    viewport={"width": width, "height": height},
                    device_scale_factor=device_scale_factor,
                )
                page.goto(temp_html.resolve().as_uri())
                page.wait_for_load_state("networkidle")

                containers = page.query_selector_all(".page")
                if not containers:
                    page.screenshot(
                        path=str(output_dir / "main_image_01.jpg"),
                        type="jpeg",
                        quality=jpeg_quality,
                        full_page=True,
                    )
                    browser.close()
                    return 1

                for i, container in enumerate(containers, 1):
                    out_path = output_dir / f"main_image_{i:02d}.jpg"
                    container.screenshot(
                        path=str(out_path),
                        type="jpeg",
                        quality=jpeg_quality,
                    )
                    logger.info(f"  已保存: {out_path.name}")

                browser.close()
            return len(containers)
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return 0
        finally:
            if temp_html.exists():
                # temp_html.unlink()  # 暂不删除，用于调试
                pass
```

关键改动:
- `new_page(...)` 加 `device_scale_factor=device_scale_factor`
- `page.screenshot(...)`(无 .page 容器分支)显式 `type="jpeg", quality=jpeg_quality, full_page=True`
- `container.screenshot(...)` 显式 `type="jpeg", quality=jpeg_quality`

- [ ] **Step 4:运行测试验证通过**

```bash
cd d:\project\bookfile_bat
.venv\Scripts\python.exe -m pytest tests/test_image_generator_clarity.py -v
```

预期:3 PASSED。

- [ ] **Step 5:运行整个 image_generator 测试套件,确认无回归**

```bash
cd d:\project\bookfile_bat
.venv\Scripts\python.exe -m pytest tests/test_image_generator.py tests/test_image_generator_unit.py tests/test_image_generator_clarity.py -v
```

预期:全部通过(原有用例不应受影响,它们 mock 了 DB/AI,根本没走到 `_screenshot_html`)。

- [ ] **Step 6:Commit**

```bash
cd d:\project\bookfile_bat
git add automation/image_generator.py tests/test_image_generator_clarity.py
git commit -m "feat(image): 截图物理像素 2× + JPEG quality 92,提升主图清晰度"
```

---

### Task 3:端到端验证 — 实际跑一本书,看产物像素和文件大小

**Files:**
- 验证: `output/<书名>_metadata/main_image_*.jpg`(不修改源文件,只读产物验证)

- [ ] **Step 1:挑一本已有 metadata 的书**

任意一本已经走过 `auto` 的书都可以(封面/摘要已在 DB)。例如:

```bash
cd d:\project\bookfile_bat
ls "output" | grep -i lean
```

预期:`The Lean Startup_ How Today's Entrepreneurs Use Continuous_metadata`

- [ ] **Step 2:重跑主图(用 `regenerate-images` 命令)**

`regenerate-images` 只重跑主图阶段,会重调 AI 生 HTML(此为预期,设计风格不变),然后走新的截图逻辑。

```bash
cd d:\project\bookfile_bat
.venv\Scripts\python.exe -m automation.main regenerate-images --book-id "lean"
```

预期:跑完 4 张主图生成,日志显示 `主图生成完成: 4 张` 或类似。

- [ ] **Step 3:用 PIL 验证像素和文件大小**

```bash
cd d:\project\bookfile_bat
.venv\Scripts\python.exe -c "
from PIL import Image
import os
d = r'output/The Lean Startup_ How Today’s Entrepreneurs Use Continuous_metadata'
for f in sorted(os.listdir(d)):
    if f.startswith('main_image_') and f.endswith('.jpg'):
        img = Image.open(os.path.join(d, f))
        size_kb = os.path.getsize(os.path.join(d, f)) // 1024
        print(f'{f}: {img.size[0]}x{img.size[1]}  {size_kb}KB')
"
```

预期输出(每行):`main_image_0X.jpg: 1600x1600  100-250KB`

若仍是 `800x800`:说明改动没生效,检查 `_screenshot_html` 是否有 `device_scale_factor=2` 透传,以及 `config.yaml` 加载是否读到。

- [ ] **Step 4:视觉对比(可选但推荐)**

把 `output/<书名>_metadata/main_image_01.jpg` 在 Chrome 浏览器打开,DevTools 切到手机模拟(iPhone 12 Pro,390×844 设备像素比 3),把图设成 100% 宽度,观察:
- 文字边缘是否锐利(尤其中文标题)
- 封面图(嵌入到 400px 高度那块)是否清晰
- 缩略图比例下文字是否还可读

对比之前 800×800 的同文件:锐利度应有肉眼可见的提升。

- [ ] **Step 5:Commit(若产物由 git 跟踪,本次不需 commit;若 .gitignore 排除则跳过)**

```bash
cd d:\project\bookfile_bat
git status output/ 2>&1 | head -20
```

通常 `output/` 在 .gitignore,验证完即可,无需 commit。

---

## Self-Review 检查

1. **Spec 覆盖**:
   - ✅ Context(根因)→ 已写入 plan 头部
   - ✅ 配置变更(`config.yaml` 两个字段)→ Task 1
   - ✅ 代码变更(`_screenshot_html` 加 2 个 Playwright 参数)→ Task 2 Step 3
   - ✅ 风险(文件变大、截图耗时)→ 验证 Task 3 已检查文件大小
   - ✅ 验证(像素 1600×1600 + 100-200KB)→ Task 3 Step 3
2. **Placeholder scan**:无 TBD、无 "类似 Task N",每步都有完整代码
3. **类型一致**:`device_scale_factor` / `screenshot_quality` 在 config、代码、测试三处命名一致;`type="jpeg"` 在两个 screenshot 调用处都设了
4. **方法签名一致**:`_screenshot_html(html, output_dir, img_cfg)` 三处调用都匹配

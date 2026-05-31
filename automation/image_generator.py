"""根据书籍封面和摘要生成商品主图"""
import logging
import base64
from collections import Counter
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

        # 1. 提取封面主色调
        cover_path = meta_dir / "cover.jpg"
        cover_colors = self._extract_cover_colors(cover_path)

        # 2. 设计分析（Chain-of-Thought）
        design_plan = self._design_analysis(title, author, summary, cover_colors)

        # 3. 生成HTML提示词（含设计分析结果）
        prompt = self._format_html_prompt(title, author, summary, cover_colors, design_plan)
        # 2. 调用 AI 生成 HTML
        html = self._call_ai(prompt)
        if not html:
            return False

        # 3. 注入封面图（替换占位符）
        cover_base64 = self._load_cover_base64(cover_path)
        if cover_base64:
            html = self._inject_cover_image(html, cover_base64)
            logger.info(f"封面图已注入 HTML")
        else:
            logger.warning("未找到封面图，HTML中无封面")

        # 4. 截图
        page_count = self._screenshot_html(html, meta_dir, img_cfg)
        if page_count > 0:
            self._update_db(book_id, page_count)
            logger.info(f"主图生成完成: {page_count} 张")
            return True
        return False

    def _format_prompt(self, title: str, author: str, summary: str, cover_colors: str = "", design_plan: str = "") -> str:
        """格式化提示词（含封面主色调，不含 base64）"""
        img_cfg = config.image_generator_config
        prompt_template = img_cfg.get("html_prompt", "")
        return prompt_template.format(
            title=title,
            author=author,
            summary=summary,
            cover_colors=cover_colors,
            design_plan=design_plan,
        )

    def _extract_cover_colors(self, cover_path: Path) -> str:
        """从封面图提取完整配色方案"""
        if not cover_path.exists():
            return ""
        try:
            from PIL import Image
            img = Image.open(cover_path).convert("RGB")
            small = img.resize((100, 100))
            reduced = small.quantize(colors=12).convert("RGB")
            color_counts = Counter(reduced.getdata())

            seen = set()
            hex_colors = []
            for color, _ in color_counts.most_common(12):
                r, g, b = color
                hex_str = f"#{r:02x}{g:02x}{b:02x}"
                if hex_str not in seen:
                    seen.add(hex_str)
                    hex_colors.append(hex_str)

            if hex_colors:
                return f"封面配色方案: {'、'.join(hex_colors)}"
            return ""
        except Exception as e:
            logger.warning(f"提取封面颜色失败: {e}")
            return ""

    def _design_analysis(self, title: str, author: str, summary: str, cover_colors: str) -> str:
        """AI 输出设计方案（布局/配色/风格定位），约200字"""
        img_cfg = config.image_generator_config
        prompt_template = img_cfg.get("design_prompt", "")
        if not prompt_template:
            return ""
        prompt = prompt_template.format(
            title=title,
            author=author,
            summary=summary,
            cover_colors=cover_colors,
        )
        try:
            plan, _ = self.ai.chat(prompt, max_tokens=500)
            plan = plan.strip()
            logger.info(f"设计分析完成: {plan[:80]}...")
            return plan
        except Exception as e:
            logger.warning(f"设计分析失败，将跳过: {e}")
            return ""

    def _format_html_prompt(self, title: str, author: str, summary: str, cover_colors: str, design_plan: str) -> str:
        """格式化 HTML 生成提示词（含 design_plan，不含 base64）"""
        img_cfg = config.image_generator_config
        prompt_template = img_cfg.get("html_prompt", "")
        return prompt_template.format(
            title=title,
            author=author,
            summary=summary,
            cover_colors=cover_colors,
            design_plan=design_plan,
        )

    def _call_ai_wrap_html(self, html: str) -> str:
        """清理AI输出并包装为完整HTML文档"""
        html = html.strip()
        html = html.removeprefix("```html").removesuffix("```").strip()
        if "<html" not in html.lower() and "<!doctype" not in html.lower():
            html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>*{{margin:0;padding:0;box-sizing:border-box;}}.page{{overflow:hidden;}}</style></head><body>{html}</body></html>"
        return html

    def _call_ai(self, prompt: str) -> Optional[str]:
        """调用AI生成HTML"""
        try:
            html, _ = self.ai.chat(prompt, max_tokens=8000)
            return self._call_ai_wrap_html(html)
        except Exception as e:
            logger.error(f"AI调用失败: {e}")
            return None

    def _inject_cover_image(self, html: str, cover_base64: str) -> str:
        """将HTML中的__COVER_PLACEHOLDER__替换为真实封面base64"""
        if not cover_base64:
            return html
        return html.replace("__COVER_PLACEHOLDER__", cover_base64)

    def _load_cover_base64(self, cover_path: Path) -> str:
        """加载封面图并返回base64编码"""
        if cover_path.exists():
            with open(cover_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        return ""

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
                # temp_html.unlink()  # 暂不删除，用于调试
                pass

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
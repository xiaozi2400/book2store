"""根据书籍封面和摘要生成商品主图"""
import logging
import base64
import json
import random
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Optional

from automation.ai_client import AIClient
from automation.database import DatabaseManager, close_session, get_session
from automation.models import BookOutput
from automation.config import config

logger = logging.getLogger(__name__)


# 克制配色池 — 全 palette 共用 4 色
# 深色主题: 4 张卡半透底色(在深色背景上)
UNIVERSAL_ACCENTS_DARK = [
    "rgba(254,243,199,0.40)",   # #FEF3C7 米白
    "rgba(229,231,235,0.40)",   # #E5E7EB 银灰
    "rgba(253,215,170,0.40)",   # #FED7AA 干桃
    "rgba(196,181,253,0.40)",   # #C4B5FD 薰衣草紫
]
UNIVERSAL_PILLS_DARK = [
    "rgba(254,243,199,0.40)",
    "rgba(229,231,235,0.40)",
    "rgba(253,215,170,0.40)",
    "rgba(196,181,253,0.40)",
    "rgba(254,243,199,0.40)",
]
# 浅色主题: 不透明柔和色(在浅色背景上可见)
UNIVERSAL_ACCENTS_LIGHT = [
    "#FDEFC4",   # 米黄
    "#E4E8ED",   # 浅灰
    "#FDDCAB",   # 干桃
    "#D4C8F5",   # 薰衣草紫
]
UNIVERSAL_PILLS_LIGHT = [
    "#FDEFC4",
    "#E4E8ED",
    "#FDDCAB",
    "#D4C8F5",
    "#FDEFC4",
]

# 4 张主图的 CSS+HTML 骨架 — 与 prompt 解耦,只做纯渲染,不参与 AI 上下文
_CSS_SKELETON = """*{margin:0;padding:0;box-sizing:border-box}
body{background:#f2f4f8;display:flex;flex-direction:column;align-items:center;padding:40px 20px;font-family:"PingFang SC","Microsoft YaHei",sans-serif}
.page,.content,.footer-tags,.skill-card,.reader-tag,.left-col,.right-col{display:flex;flex-direction:column;align-items:center}
.page{width:800px;height:800px;box-shadow:0 12px 40px rgba(0,0,0,.1);margin-bottom:40px;overflow:hidden;padding:30px 40px;justify-content:space-between}
.content{width:100%;flex:1;justify-content:center}
.footer-tags{flex-direction:row;justify-content:center;gap:24px;width:100%;margin-top:20px}
.tag{padding:6px 22px;border-radius:40px;font-size:14px;font-weight:500;box-shadow:0 2px 6px rgba(0,0,0,.08)}
.tag-pdf{background:#1E3A5F}.tag-lang{background:#8E3A3A}
.section-title{font-size:48px;font-weight:700;margin-bottom:28px}
/* 深色主题默认白字 */
.page{color:#fff}
.tag{color:#fff}
/* 浅色主题深色字 */
.page.light{color:#1a1a1a}
.page.light .tag{color:#1a1a1a}
/* 四色主背景占位符 */
.page-1{background:__COLOR1__}.page-2{background:__COLOR2__}.page-3{background:__COLOR3__}.page-4{background:__COLOR4__}
/* 浅色主题下正文变深,副文字用中灰 */
.page.light{color:#1a1a1a}
.page.light .author,.page.light .sub-line,.page.light .quote-line{color:rgba(26,26,26,.75)}
.page.light .quote-line{border-top-color:rgba(26,26,26,.15)}
.page.light .footer-tags .tag{color:#fff}
.book-title{font-size:54px;font-weight:700;line-height:1.2;text-align:center;max-width:90%}
.author{font-size:24px;font-weight:300;margin-top:8px;opacity:.9}
.cover-img{height:340px;margin:20px 0 10px;box-shadow:0 20px 50px rgba(0,0,0,.35)}
.sub-line{font-size:32px;font-weight:500;margin-top:20px;text-align:center;letter-spacing:2px}
.quote-line{font-size:16px;opacity:.75;margin-top:16px;border-top:1px solid rgba(255,255,255,.2);padding-top:16px;text-align:center;quotes:"\\201C""\\201D"}
.quote-line::before{content:open-quote}.quote-line::after{content:close-quote}
.grid-2x2{display:grid;grid-template-columns:1fr 1fr;gap:24px;width:100%;max-width:700px}
.skill-card{padding:24px 16px;border-radius:16px;box-shadow:0 8px 20px rgba(0,0,0,.2);text-align:center;position:relative}
.skill-card .num{font-size:36px;font-weight:700;font-family:"Georgia","Times New Roman",serif;position:absolute;top:12px;left:16px;line-height:1}
.skill-card h3{font-size:22px;font-weight:600;margin-bottom:6px;margin-top:8px}
.skill-card p{font-size:15px;opacity:.9;line-height:1.4}
/* 深色主题:数字淡白 */
.skill-card .num{color:rgba(255,255,255,.25)}
/* 浅色主题:数字深灰 */
.page.light .skill-card .num{color:rgba(26,26,26,.2)}
.skill-card:nth-child(1){background:__TINT1__}
.skill-card:nth-child(2){background:__TINT2__}
.skill-card:nth-child(3){background:__TINT3__}
.skill-card:nth-child(4){background:__TINT4__}
.tag-row{display:flex;flex-wrap:wrap;justify-content:center;gap:28px;width:100%;max-width:720px}
.reader-tag{padding:20px 28px;border-radius:60px;box-shadow:0 8px 20px rgba(0,0,0,.18);min-width:140px;position:relative;align-items:center}
.reader-tag .label{font-size:22px;font-weight:600}
.reader-tag .desc{font-size:14px;opacity:.85;margin-top:4px;text-align:center}
.reader-tag:nth-child(1){background:__PILL1__}
.reader-tag:nth-child(2){background:__PILL2__}
.reader-tag:nth-child(3){background:__PILL3__}
.reader-tag:nth-child(4){background:__PILL4__}
.reader-tag:nth-child(5){background:__PILL5__}
/* --- Page 4 三版式 --- */
/* 版式A: ≤10章 双栏简略 */
.dual-col{display:flex;width:100%;max-width:720px;border-radius:20px;box-shadow:0 8px 24px rgba(0,0,0,.25);overflow:hidden;border:1px solid rgba(255,255,255,.1)}
.left-col,.right-col{padding:24px 16px;justify-content:space-around;align-items:stretch}
.left-col{flex:1;background:rgba(0,0,0,.35)}
.right-col{flex:1.6;background:#f5ede6;color:#2d2d2d}
/* 浅色主题版式A右栏保持浅色 */
.page.light .right-col{background:rgba(0,0,0,.06);color:#1a1a1a}
.rule-item{font-size:20px;font-weight:600;padding:10px 8px;border-bottom:1px solid rgba(255,255,255,.1)}
.strategy-item{font-size:16px;font-weight:500;padding:10px 8px;border-bottom:1px solid rgba(0,0,0,.08);line-height:1.3}
.rule-item:last-child,.strategy-item:last-child{border-bottom:none}
/* 版式B: 11~14章 紧凑单栏 */
.dual-col-b{display:flex;flex-direction:column;width:100%;max-width:720px;border-radius:20px;box-shadow:0 8px 24px rgba(0,0,0,.25);overflow:hidden;border:1px solid rgba(255,255,255,.1);background:rgba(0,0,0,.35)}
.chapter-row{display:flex;align-items:center;padding:12px 20px;border-bottom:1px solid rgba(255,255,255,.1)}
.chapter-row:last-child{border-bottom:none}
.chapter-num{font-size:18px;font-weight:700;font-family:"Georgia","Times New Roman",serif;min-width:48px}
.chapter-text{flex:1;font-size:18px;font-weight:600}
.chapter-brief{flex:1;font-size:15px;padding-left:16px}
/* 深色:章节号淡白/浅色文字;浅色:深灰文字 */
.chapter-num{color:rgba(255,255,255,.35)}
.chapter-text{color:#fff}
.chapter-brief{color:rgba(255,255,255,.7)}
/* 版式C: ≥15章 双栏纯列表 */
.dual-col-c{display:flex;width:100%;max-width:720px;border-radius:20px;box-shadow:0 8px 24px rgba(0,0,0,.25);overflow:hidden;border:1px solid rgba(255,255,255,.1)}
.left-col-c{flex:3;background:rgba(0,0,0,.3);padding:20px 16px}
.right-col-c{flex:1;background:#f5ede6;color:#2d2d2d;padding:20px 16px}
.chapter-item{font-size:17px;font-weight:600;padding:10px 8px;border-bottom:1px solid rgba(255,255,255,.1)}
.chapter-item:last-child{border-bottom:none}
.strategy-item-c{font-size:15px;font-weight:500;padding:10px 8px;border-bottom:1px solid rgba(0,0,0,.08);line-height:1.3;color:#2d2d2d}
.strategy-item-c:last-child{border-bottom:none}
/* 浅色主题覆盖 */
.page.light .chapter-num{color:rgba(26,26,26,.3)}
.page.light .chapter-text{color:#1a1a1a}
.page.light .chapter-brief{color:rgba(26,26,26,.65)}
.page.light .left-col-c{background:rgba(0,0,0,.06)}
.page.light .right-col-c{background:rgba(0,0,0,.04);color:#1a1a1a}
.page.light .chapter-item{color:#1a1a1a;border-bottom-color:rgba(26,26,26,.1)}
.page.light .strategy-item-c{color:#1a1a1a}
.page.light .strategy-item-c{border-bottom-color:rgba(26,26,26,.08)}
.page.light .left-col{background:rgba(0,0,0,.08)}
.page.light .rule-item{border-bottom-color:rgba(26,26,26,.1);color:#1a1a1a}
.page.light .strategy-item{border-bottom-color:rgba(26,26,26,.08);color:#1a1a1a}
.page.light .dual-col{border-color:rgba(26,26,26,.1)}
.page.light .dual-col-b{border-color:rgba(26,26,26,.1)}
.page.light .dual-col-c{border-color:rgba(26,26,26,.1)}"""

_FOOTER_TAGS = ('<div class="footer-tags">'
                '<span class="tag tag-pdf">支持PDF+EPUB双格式</span>'
                '<span class="tag tag-lang">英文+中译+双语+精简版</span></div>')


def _safe_format(template: str, **kwargs) -> str:
    """按命名占位符做纯替换,不解析模板中其他 `{`/`}`。

    `str.format` 会把模板里所有 `{...}` 当作占位符,一旦 YAML 中出现
    CSS/JS 字面量(如 `:root { --primary: ... }`)就会抛 `KeyError: '\\n  --primary'`。
    这里改用逐个 `str.replace`,让 CSS/JSON/JS 代码块可以原样出现在提示词里。
    """
    result = template
    for name, value in kwargs.items():
        result = result.replace("{" + name + "}", str(value))
    return result


class ImageGenerator:
    """AI生成HTML商品主图 → Playwright截图"""

    def __init__(self):
        self.ai = AIClient()
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir)

    def generate(self, book_id: str) -> bool:
        """生成商品主图"""
        from automation.progress import event
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

        base_name = Path(book.filename).stem.strip()
        meta_dir = self.output_dir / f"{base_name}_metadata"

        # 1. 查找封面（支持多个扩展名）
        cover_path = self._find_cover_path(meta_dir)
        cover_colors = self._extract_cover_colors(cover_path)
        event("封面配色提取完成")

        # 2. 设计分析（Chain-of-Thought）
        event("AI 设计分析")
        palette_name, palette_lines, palette_colors, palette_theme = self._pick_palette()
        logger.info(f"本次选用配色方案: {palette_name} [{palette_theme}] → 图1/2/3/4 = {palette_colors}")
        design_plan = self._design_analysis(title, author, summary, cover_colors, palette_name, palette_lines)

        # 3. 抽取原书完整章节目录(用于图 4)——避免 summary_text 截断导致目录缺失
        full_toc = self._extract_full_toc(book)
        toc_text = "\n".join(f"- {c}" for c in full_toc) if full_toc else "(未能读到 EPUB 目录,请依据摘要中的章节)"
        if full_toc:
            logger.info(f"从 EPUB 读到完整目录 {len(full_toc)} 章: {full_toc[:3]}...")
        else:
            logger.warning("未能读取原书 EPUB 目录,图 4 将依赖 summary 中的章节")

        # 4. 生成JSON提示词(AI 只出内容,不出 HTML)
        prompt = self._format_html_prompt(title, author, summary, cover_colors, design_plan, toc_text)
        event("调用 AI 生成主图内容 JSON")
        content = self._call_ai_json(prompt)
        if not content:
            return False

        # 5. 用固定骨架 + AI 内容 + 4 主色(代码直接决定,不再从 AI 输出解析)渲染 HTML
        chapter_count = len(full_toc) if full_toc else 0
        html = self._render_html(content, palette_colors, chapter_count, palette_theme)

        # 5. 注入封面图（替换占位符）
        cover_base64 = self._load_cover_base64(cover_path) if cover_path else None
        if cover_base64:
            html = self._inject_cover_image(html, cover_base64)
            logger.info(f"封面图已注入 HTML")
        else:
            logger.warning("未找到封面图，HTML中无封面")

        # 6. 截图
        event("截图生成主图")
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
        return _safe_format(
            prompt_template,
            title=title,
            author=author,
            summary=summary,
            cover_colors=cover_colors,
            design_plan=design_plan,
        )

    def _find_cover_path(self, meta_dir: Path) -> Optional[Path]:
        """在metadata目录中查找封面，支持多个扩展名"""
        cover_exts = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]
        for ext in cover_exts:
            path = meta_dir / f"cover{ext}"
            if path.exists():
                logger.info(f"找到封面: {path}")
                return path
        logger.warning(f"未在 {meta_dir} 找到封面")
        return None

    def _extract_cover_colors(self, cover_path: Optional[Path]) -> str:
        """从封面图提取完整配色方案"""
        if not cover_path or not cover_path.exists():
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

    def _pick_palette(self) -> tuple:
        """从 palettes 池随机挑一套 + 打乱色序,返回 (name, palette_lines_text, colors_list, theme)。

        - 按 config 中 color_theme 过滤 palette
        - 深色 palette:打乱 4 色在图 1/2/3/4 之间的分配
        - 浅色 palette:不 shuffle,保持 bg + 3 强调色固定顺序
        - palette_lines_text:注入 design_prompt 供 AI 参考
        - colors_list:代码渲染时直接使用,不再依赖 AI 回写 HEX
        """
        img_cfg = config.image_generator_config
        palettes = img_cfg.get("palettes") or []
        theme = img_cfg.get("color_theme", "dark")
        default_colors = ["#1A365D", "#276749", "#553C9A", "#9B2C2C"]

        # 按 theme 过滤
        candidates = [p for p in palettes if p.get("theme", "dark") == theme]
        if not candidates:
            candidates = palettes if palettes else [{"name": "经典深沉", "colors": default_colors}]

        chosen = random.choice(candidates)
        name = chosen.get("name", "未命名")

        if theme == "light":
            # 浅色 palette: bg + 3 强调色,不 shuffle
            bg = chosen.get("bg", "#FAFAF9")
            accents = chosen.get("accents", ["#C8C4BC", "#7A7670", "#3D3B38"])
            colors = [bg] + accents  # 保持顺序不被打乱
            # AI prompt 用 accent 色展示
            lines = "\n      ".join(f"- 强调色{i+1}: {c}" for i, c in enumerate(accents))
        else:
            colors = list(chosen.get("colors", []) or [])
            if len(colors) < 4:
                logger.warning(f"配色方案 {name} 少于 4 色,补齐经典色")
                colors = (colors + default_colors)[:4]
            else:
                colors = colors[:4]
            random.shuffle(colors)
            lines = "\n      ".join(f"- 图{i+1}主色: {c}" for i, c in enumerate(colors))

        return (name, lines, colors, theme)

    @staticmethod
    def _hex_to_rgb(hex_str: str) -> tuple:
        s = hex_str.lstrip("#")
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)

    @staticmethod
    def _hex_to_rgba(hex_str: str, alpha: float) -> str:
        r, g, b = ImageGenerator._hex_to_rgb(hex_str)
        return f"rgba({r},{g},{b},{alpha:.2f})"

    @staticmethod
    def _lighten(hex_str: str, amount: float) -> str:
        """把 hex 色混入 amount 比例的白色,返回极浅的新 hex。amount=0.88 表示 12%原色+88%白"""
        r, g, b = ImageGenerator._hex_to_rgb(hex_str)
        nr = int(r + (255 - r) * amount)
        ng = int(g + (255 - g) * amount)
        nb = int(b + (255 - b) * amount)
        return f"#{nr:02x}{ng:02x}{nb:02x}"

    @staticmethod
    def _mix_with_white(hex_color: str, alpha: float = 0.22) -> str:
        """把主色按 alpha 混到白底上,得到"辅助色"—— 保证同 palette 下辅助色也随主色变化。"""
        r, g, b = ImageGenerator._hex_to_rgb(hex_color)
        return f"rgba({r},{g},{b},{alpha:.2f})"

    def _derive_tints(self, page2_main: str) -> list:
        """图 2 的 4 张卡背景:用图 2 主色 + 4 档不同透明度,得到"同色系深浅"辅助色。"""
        return [self._mix_with_white(page2_main, a) for a in (0.20, 0.30, 0.40, 0.50)]

    def _derive_pills(self, page3_main: str) -> list:
        """图 3 的 5 个标签背景:用图 3 主色 + 5 档不同透明度。"""
        return [self._mix_with_white(page3_main, a) for a in (0.28, 0.40, 0.55, 0.40, 0.28)]

    def _extract_full_toc(self, book) -> list:
        """从 EPUB 的 NCX/nav 里抽正文章节(过滤 Cover/TOC/Copyright/Acknowledgments 等前后件)。

        返回像 ["1: Creating Alien Minds", "2: Aligning the Alien", ...] 这样的正文章节列表;
        找不到 EPUB 或抽不出时返回空 list,由调用方回落到 summary_text。
        """
        try:
            epub_path = self._find_epub_path(book)
            if not epub_path or not epub_path.exists():
                return []
            with zipfile.ZipFile(epub_path) as z:
                ncx_name = next((n for n in z.namelist() if n.lower().endswith(".ncx")), None)
                if not ncx_name:
                    return []
                content = z.read(ncx_name).decode("utf-8", errors="ignore")
            raw = [m.group(1).strip() for m in re.finditer(r"<text>([^<]+)</text>", content)]
            # 过滤明显的前后件
            skip_patterns = re.compile(
                r"^(cover|title\s*page|copyright|dedication|contents?|epigraph|"
                r"acknowledg?ments?|notes?|about\s+the\s+author|index|bibliography|"
                r"foreword|preface|part\s+[ivx0-9]+|page\s+mapping.*|"
                r"目录|扉页|版权|献辞|致谢|注释|附录|参考文献|前言|序言|后记|作者简介)\s*$",
                re.IGNORECASE)
            book_title = (getattr(book, "title", "") or "").strip().lower()
            chapters = []
            for t in raw:
                if not t or skip_patterns.match(t):
                    continue
                # 过滤只有页码的项 (罗马数字/阿拉伯数字)
                if re.match(r"^[ivxlcdm]+$", t, re.IGNORECASE) or t.isdigit():
                    continue
                # 过滤书名本身(常见:NCX 首项 = 书名)
                if book_title and t.lower() == book_title:
                    continue
                chapters.append(t)
            return chapters
        except Exception as e:
            logger.warning(f"读取 EPUB 目录失败: {e}")
            return []

    def _find_epub_path(self, book) -> Optional[Path]:
        """定位原书 EPUB 路径 (output/<basename>/英文-*.epub)。"""
        base_name = Path(book.filename).stem.strip()
        content_dir = self.output_dir / base_name
        if not content_dir.exists():
            return None
        # 优先英文-*.epub
        candidates = list(content_dir.rglob("英文-*.epub")) + list(content_dir.rglob("*.epub"))
        return candidates[0] if candidates else None

    def _design_analysis(self, title: str, author: str, summary: str, cover_colors: str,
                         palette_name: str = "", palette_lines: str = "") -> str:
        """AI 输出设计方案（布局/配色/风格定位），约200字"""
        img_cfg = config.image_generator_config
        prompt_template = img_cfg.get("design_prompt", "")
        if not prompt_template:
            return ""
        prompt = _safe_format(
            prompt_template,
            title=title,
            author=author,
            summary=summary,
            cover_colors=cover_colors,
            palette_name=palette_name,
            palette_lines=palette_lines,
        )
        try:
            plan, _ = self.ai.chat(prompt, max_tokens=500)
            plan = plan.strip()
            logger.info(f"设计分析完成: {plan[:80]}...")
            return plan
        except Exception as e:
            logger.warning(f"设计分析失败，将跳过: {e}")
            return ""

    def _format_html_prompt(self, title: str, author: str, summary: str, cover_colors: str, design_plan: str, full_toc: str = "") -> str:
        """格式化 HTML 生成提示词（含 design_plan + full_toc，不含 base64）"""
        img_cfg = config.image_generator_config
        prompt_template = img_cfg.get("html_prompt", "")
        return _safe_format(
            prompt_template,
            title=title,
            author=author,
            summary=summary,
            cover_colors=cover_colors,
            design_plan=design_plan,
            full_toc=full_toc,
        )

    def _call_ai_json(self, prompt: str) -> Optional[dict]:
        """调用 AI,解析 JSON。max_tokens 大幅下调 — 只出 JSON,不再是完整 HTML。"""
        try:
            raw, _ = self.ai.chat(prompt, max_tokens=2048)
        except Exception as e:
            logger.error(f"AI调用失败: {e}")
            return None
        text = raw.strip()
        # 去掉可能的 ```json ... ``` 包裹
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
        # 兜底:抽取第一个 `{` 到最后一个 `}`
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"AI 返回 JSON 解析失败: {e}\n原文前 500 字: {text[:500]}")
            return None
        # 结构校验 + 归一化:AI 偶尔把 pageN 直接输出为数组,统一包成 {"items": [...]}
        for key in ("page1", "page2", "page3", "page4"):
            if key not in data:
                logger.error(f"AI JSON 缺失字段: {key}")
                return None
            if key != "page1" and isinstance(data[key], list):
                logger.warning(f"AI 把 {key} 输出为数组,已包成 {{'items': [...]}}")
                data[key] = {"items": data[key]}
        return data

    def _parse_palette_from_design_plan(self, design_plan: str) -> list:
        """[已弃用] 保留仅作向后兼容;主色现由 _pick_palette 代码级决定,不再从 AI 输出解析。

        从 design_plan 文本中抽取 4 个"图N主色"HEX;失败则回落到经典色。
        """
        colors = []
        for i in range(1, 5):
            m = re.search(rf"图\s*{i}\s*主色\s*[:：]\s*(#[0-9A-Fa-f]{{6}})", design_plan)
            colors.append(m.group(1) if m else None)
        default = ["#1A365D", "#276749", "#553C9A", "#9B2C2C"]
        for i, c in enumerate(colors):
            if not c:
                colors[i] = default[i]
        return colors

    def _render_html(self, content: dict, colors: list, chapter_count: int = 0, theme: str = "dark") -> str:
        """用骨架 + AI 出的 content JSON + 4 主色,渲染最终 HTML。

        布局与 section 标题**固定**:
        - page2 = 2x2 网格 (grid), 标题"能学到什么"
        - page3 = 标签展示 (pill),  标题"适合谁阅读"
        - page4 = 自适应三版式(≤10章 A / 11-14章 B / ≥15章 C), 标题"目录内容"
        """
        css = _CSS_SKELETON

        if theme == "light":
            # 浅色模式:3个强调色分别混入大量白色,生成4张图各自的极浅背景色
            # 混入比例 0.85 = 15%原色+85%白,产生"近白但有色调"的背景
            accent0_pale = self._lighten(colors[1], 0.85)  # 强调色0的极浅版
            accent1_pale = self._lighten(colors[2], 0.85)  # 强调色1的极浅版
            accent2_pale = self._lighten(colors[3], 0.85)  # 强调色2的极浅版
            accent0_paler = self._lighten(colors[1], 0.90)  # 强调色0的更浅版
            page_bgs = [accent0_pale, accent1_pale, accent2_pale, accent0_paler]
            for i, c in enumerate(page_bgs, 1):
                css = css.replace(f"__COLOR{i}__", c)
            # 强调色半透明用于标签/卡片底色
            accent_rgba = [self._hex_to_rgba(c, 0.55) for c in colors[1:4]]
            for i, rgba in enumerate(accent_rgba[:3], 1):
                css = css.replace(f"__TINT{i}__", rgba)
            css = css.replace(f"__TINT4__", accent_rgba[2])
            pill_rgba = [self._hex_to_rgba(c, 0.50) for c in colors[1:4]]
            pills_order = [pill_rgba[0], pill_rgba[1], pill_rgba[2], pill_rgba[1], pill_rgba[0]]
            for i, rgba in enumerate(pills_order, 1):
                css = css.replace(f"__PILL{i}__", rgba)
        else:
            # 深色模式:每页各自背景色
            for i, c in enumerate(colors[:4], 1):
                css = css.replace(f"__COLOR{i}__", c)
            for i, t in enumerate(UNIVERSAL_ACCENTS_DARK, 1):
                css = css.replace(f"__TINT{i}__", t)
            for i, p in enumerate(UNIVERSAL_PILLS_DARK, 1):
                css = css.replace(f"__PILL{i}__", p)

        light_cls = " light" if theme == "light" else ""

        page1 = self._render_page1(content.get("page1", {}), light_cls)
        page2 = self._render_content_page(
            "page-2" + light_cls, "能学到什么", content.get("page2", {}), self._render_layout_grid)
        page3 = self._render_content_page(
            "page-3" + light_cls, "适合谁阅读", content.get("page3", {}), self._render_layout_pill)
        page4 = self._render_content_page(
            "page-4" + light_cls, "目录内容",  content.get("page4", {}),
            lambda items: self._render_layout_dual(items, chapter_count))

        return (
            f'<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8">'
            f'<title>主图</title><style>{css}</style></head><body>'
            f'{page1}{page2}{page3}{page4}'
            f'</body></html>'
        )

    def _render_page1(self, p, light_cls: str = "") -> str:
        if not isinstance(p, dict):
            logger.warning(f"page1 内容非 dict: {type(p).__name__},当作空处理")
            p = {}
        subline = p.get("subline", "").replace("·", "｜")
        return (
            f'<div class="page page-1{light_cls}"><div class="content">'
            f'<div class="book-title">{p.get("title","")}</div>'
            f'<div class="author">{p.get("author","")}</div>'
            f'<img class="cover-img" src="data:image/jpeg;base64,__COVER_PLACEHOLDER__" alt="封面">'
            f'<div class="sub-line">{subline}</div>'
            f'<div class="quote-line">{p.get("quote","")}</div>'
            f'</div>{_FOOTER_TAGS}</div>'
        )

    def _render_content_page(self, page_cls: str, section: str, p, layout_fn) -> str:
        """渲染图 2/3/4:page_cls/section/layout 由调用方指定(硬编码),内容由 AI 提供。

        兼容两种输入:
        - {"items": [...]}(schema 定义)
        - [...](AI 偶发直接输出数组,已在 _call_ai_json 归一化,这里再兜一次)
        """
        if isinstance(p, list):
            items = p
        elif isinstance(p, dict):
            items = p.get("items", []) or []
        else:
            logger.warning(f"{page_cls} 内容非 dict/list: {type(p).__name__},当作空处理")
            items = []
        body = layout_fn(items)
        return (
            f'<div class="page {page_cls}"><div class="content">'
            f'<div class="section-title">{section}</div>{body}'
            f'</div>{_FOOTER_TAGS}</div>'
        )

    def _render_layout_grid(self, items: list) -> str:
        cards = "".join(
            f'<div class="skill-card">'
            f'<div class="num">{i+1:02d}</div>'
            f'<h3>{it.get("title","")}</h3>'
            f'<p>{it.get("desc","")}</p></div>'
            for i, it in enumerate(items[:4])
        )
        return f'<div class="grid-2x2">{cards}</div>'

    def _render_layout_pill(self, items: list) -> str:
        tags = "".join(
            f'<div class="reader-tag">'
            f'<span class="label">{it.get("label","")}</span>'
            f'<span class="desc">{it.get("desc","")}</span></div>'
            for i, it in enumerate(items[:5])
        )
        return f'<div class="tag-row">{tags}</div>'

    def _render_layout_dual(self, items: list, chapter_count: int = 0) -> str:
        """三版式自适应:
        - A: ≤10章 双栏简略(左列规则+右列策略)
        - B: 11-14章 紧凑单栏(章节号+名+要点,单列)
        - C: ≥15章 双栏纯列表(左3/4列章节名,右1/4列策略)
        """
        n = len(items)
        if n <= 10:
            # 版式A:双栏简略
            left = "".join(f'<div class="rule-item">{it.get("chapter","")}</div>' for it in items[:10])
            right = "".join(f'<div class="strategy-item">{it.get("brief","")}</div>' for it in items[:10])
            return f'<div class="dual-col"><div class="left-col">{left}</div><div class="right-col">{right}</div></div>'
        elif n <= 14:
            # 版式B:紧凑单栏
            rows = "".join(
                f'<div class="chapter-row">'
                f'<div class="chapter-num">{i+1:02d}</div>'
                f'<div class="chapter-text">{it.get("chapter","")}</div>'
                f'<div class="chapter-brief">{it.get("brief","")}</div>'
                f'</div>'
                for i, it in enumerate(items[:14])
            )
            return f'<div class="dual-col-b">{rows}</div>'
        else:
            # 版式C:双栏纯列表
            left = "".join(f'<div class="chapter-item">{it.get("chapter","")}</div>' for it in items[:15])
            right = "".join(f'<div class="strategy-item-c">{it.get("brief","")}</div>' for it in items[:15])
            return f'<div class="dual-col-c"><div class="left-col-c">{left}</div><div class="right-col-c">{right}</div></div>'

    def _inject_cover_image(self, html: str, cover_base64: str) -> str:
        """将HTML中的__COVER_PLACEHOLDER__替换为真实封面base64"""
        if not cover_base64:
            return html
        return html.replace("__COVER_PLACEHOLDER__", cover_base64)

    def _load_cover_base64(self, cover_path: Optional[Path]) -> str:
        """加载封面图并返回base64编码"""
        if cover_path and cover_path.exists():
            with open(cover_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        return ""

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
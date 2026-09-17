import os
import subprocess
import tempfile
import logging
from config import CALIBRE_PATH, PDF_CONFIG

logger = logging.getLogger(__name__)

class PDFConverter:
    """专业级 PDF 转换器 - 针对电脑阅读优化（大字体+窄边距）"""

    def __init__(self):
        """初始化转换器"""
        self.ebook_convert_path = self._find_ebook_convert()
        self.config = PDF_CONFIG
        
    def _find_ebook_convert(self):
        """查找 ebook-convert 工具"""
        if CALIBRE_PATH:
            return os.path.join(CALIBRE_PATH, "ebook-convert")

        # 尝试在 PATH 中查找
        try:
            result = subprocess.run(["where", "ebook-convert"], capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except Exception:
            pass

        # 常见安装路径
        common_paths = [
            r"C:\Program Files\Calibre2\ebook-convert.exe",
            r"C:\Program Files (x86)\Calibre2\ebook-convert.exe"
        ]

        for path in common_paths:
            if os.path.exists(path):
                return path

        return None

    def _build_professional_cmd(self, epub_path, pdf_path, is_bilingual=False):
        """构建专业级排版的转换命令（针对电脑阅读优化，兼容Calibre 8.x）"""
        # 从配置获取设置
        page_cfg = self.config['page']
        font_cfg = self.config['font']
        typo_cfg = self.config['typography']
        hf_cfg = self.config['header_footer']
        
        # 基础配置
        cmd = [
            self.ebook_convert_path,
            epub_path,
            pdf_path,
        ]
        
        # ==================== 页面设置（电脑阅读优化 - 窄边距）====================
        cmd.extend([
            "--paper-size", page_cfg['paper_size'],
            "--margin-top", str(page_cfg['margin_top']),
            "--margin-bottom", str(page_cfg['margin_bottom']),
            "--margin-left", str(page_cfg['margin_left']),
            "--margin-right", str(page_cfg['margin_right']),
        ])
        
        # ==================== 字体配置（电脑阅读优化 - 大字体）====================
        # 根据是否双语选择字号
        if is_bilingual:
            default_size = font_cfg['bilingual_default_size']
            mono_size = font_cfg['bilingual_mono_size']
        else:
            default_size = font_cfg['default_size']
            mono_size = font_cfg['mono_size']
        
        cmd.extend([
            "--pdf-default-font-size", str(default_size),
            "--pdf-mono-font-size", str(mono_size),
            "--pdf-serif-family", font_cfg['serif'],
            "--pdf-sans-family", font_cfg['sans'],
            "--pdf-mono-family", font_cfg['mono'],
        ])
        
        # ==================== 排版设置（电脑阅读优化 - 舒适行距）====================
        # 设置最小行高（确保足够的行间距）
        cmd.extend([
            "--minimum-line-height", str(typo_cfg['minimum_line_height']),
        ])

        # ==================== 强制段落样式 ====================
        # 原始EPUB的CSS可能覆盖翻译样式，使用--extra-css强制设置
        css_config = self.config.get('css', {})
        margin_bottom = css_config.get('paragraph_margin_bottom', '1.5em')
        line_height = css_config.get('paragraph_line_height', '2.2')
        text_indent = css_config.get('paragraph_text_indent', '0em')

        extra_css = f"p, div {{ margin-top: 0 !important; text-indent: {text_indent} !important; margin-bottom: {margin_bottom} !important; line-height: {line_height} !important; }} li {{ margin-bottom: 0.3em !important; line-height: {line_height} !important; }} ol, ul {{ padding-left: 1.5em !important; margin: 0.3em 0 !important; }}"
        cmd.extend(["--extra-css", extra_css])
        
        # ==================== 页眉页脚（简洁设计）====================
        # 使用默认的页码功能（不使用自定义模板，避免变量替换问题）
        cmd.append("--pdf-page-numbers")
        
        # ==================== 目录与书签 ====================
        # 添加目录页，并使用XPath表达式明确指定章节标题
        # 从 <a> 标签提取目录，因为目录页的链接结构为 <p><a href="...">Title</a></p>
        cmd.extend([
            "--pdf-add-toc",
            "--duplicate-links-in-toc",
            "--level1-toc", "//h:h1",  # 从h1标签构建一级目录
            "--level2-toc", "//h:h2",  # 从h2标签构建二级目录
            "--level3-toc", "//h:h3",  # 从h3标签构建三级目录
        ])
        
        # ==================== 高级选项 ====================
        cmd.append("--pdf-page-numbers")
        
        return cmd

    def _build_ps_command(self, epub_path, pdf_path, is_bilingual=False):
        """构建 PowerShell 命令（管理员权限）"""
        cmd_list = self._build_professional_cmd(epub_path, pdf_path, is_bilingual)
        # 将命令列表转换为 PowerShell 字符串
        escaped_args = []
        for arg in cmd_list:
            if ' ' in arg or '"' in arg:
                escaped_args.append(f"'{arg}'")
            else:
                escaped_args.append(arg)
        return "& " + " ".join(escaped_args)

    def convert_to_pdf(self, epub_path, pdf_path, is_bilingual=False):
        """将 EPUB 转换为 PDF（专业级排版）
        
        Args:
            epub_path: EPUB 文件路径
            pdf_path: 输出 PDF 路径
            is_bilingual: 是否为中英双语版本
        """
        if not self.ebook_convert_path:
            logger.error("未找到 ebook-convert 工具，请安装 Calibre 或设置 CALIBRE_PATH")
            return False

        if not os.path.exists(epub_path):
            logger.warning(f"EPUB 文件不存在: {epub_path}")
            return False

        # 确保输出目录存在
        pdf_dir = os.path.dirname(pdf_path)
        if pdf_dir and not os.path.exists(pdf_dir):
            os.makedirs(pdf_dir, exist_ok=True)

        # 使用绝对路径
        epub_path = os.path.abspath(epub_path)
        pdf_path = os.path.abspath(pdf_path)

        try:
            logger.info(f"正在转换 {epub_path} 到 {pdf_path}")

            # 构建专业级转换命令
            cmd = self._build_professional_cmd(epub_path, pdf_path, is_bilingual)
            
            logger.info(f"执行命令: {' '.join(cmd[:12])}...")

            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0:
                if os.path.exists(pdf_path):
                    logger.info(f"PDF 转换成功: {pdf_path}")
                    # 添加书签增强
                    self._enhance_pdf_with_bookmarks(pdf_path)
                    return True
                else:
                    logger.warning(f"PDF 转换命令成功，但文件未生成: {pdf_path}")
            else:
                logger.error(f"PDF 转换失败: {result.stderr}")
            
            # 尝试以管理员身份运行
            logger.info("尝试以管理员身份运行...")
            
            # 构建 PowerShell 命令
            ps_cmd = self._build_ps_command(epub_path, pdf_path, is_bilingual)
            
            # 保存为临时脚本文件
            with tempfile.NamedTemporaryFile(suffix='.ps1', delete=False, mode='w', encoding='utf-8') as f:
                f.write(ps_cmd)
                temp_script = f.name
            
            try:
                # 使用 PowerShell 以管理员身份运行
                run_cmd = f"powershell -Command \"Start-Process powershell -ArgumentList '-ExecutionPolicy Bypass -File \"{temp_script}\"' -Verb RunAs -Wait\""
                result = subprocess.run(
                    run_cmd,
                    shell=True,
                    capture_output=True,
                    encoding='utf-8',
                    errors='replace'
                )
                
                if os.path.exists(pdf_path):
                    logger.info(f"PDF 转换成功: {pdf_path}")
                    # 添加书签增强
                    self._enhance_pdf_with_bookmarks(pdf_path)
                    return True
                else:
                    logger.warning(f"以管理员身份运行后文件仍未生成: {pdf_path}")
                    logger.info(f"PowerShell 输出: {result.stdout}")
                    logger.warning(f"PowerShell 错误: {result.stderr}")
            except Exception as e:
                logger.warning(f"以管理员身份运行出错: {e}")
            finally:
                if os.path.exists(temp_script):
                    try:
                        os.unlink(temp_script)
                    except:
                        pass
            
            logger.info("建议：请手动使用 Calibre 转换 EPUB 到 PDF")
            return False

        except Exception as e:
            logger.error(f"转换过程出错: {e}")
            logger.info("建议：请手动使用 Calibre 转换 EPUB 到 PDF")
            return False

    def _enhance_pdf_with_bookmarks(self, pdf_path):
        """增强PDF书签（尝试使用PyPDF2）"""
        try:
            from PyPDF2 import PdfReader, PdfWriter
            
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            
            # 复制所有页面
            for page in reader.pages:
                writer.add_page(page)
            
            # 检查是否已有书签
            try:
                root_obj = reader.trailer.get('/Root')
                if hasattr(root_obj, 'get') and root_obj.get('/Outlines') is not None:
                    logger.info("PDF已包含书签")
                    return
            except Exception:
                pass
            
            # 如果没有书签，尝试从内容生成简单书签
            logger.info("尝试添加书签...")
            page_count = len(reader.pages)
            
            # 添加基本书签结构
            if page_count > 1:
                writer.add_outline_item("封面", 0)
                if page_count > 2:
                    writer.add_outline_item("目录", 1)
                    writer.add_outline_item("正文", 2)
                else:
                    writer.add_outline_item("正文", 1)
            
            # 写回PDF
            with open(pdf_path, 'wb') as f:
                writer.write(f)
            logger.info("书签添加完成")
            
        except ImportError:
            logger.info("PyPDF2 未安装，跳过书签增强")
        except Exception as e:
            logger.warning(f"书签增强失败: {e}")

    def optimize_for_screen_reading(self, epub_path, pdf_path, is_bilingual=False):
        """专门针对屏幕阅读优化的转换方法"""
        logger.info("=== 屏幕阅读优化模式 ===")
        logger.info("使用优化配置：大字体(18pt)、窄边距(10mm)、舒适行距")
        return self.convert_to_pdf(epub_path, pdf_path, is_bilingual)
import os
import subprocess
from config import CALIBRE_PATH

class PDFConverter:
    """PDF 转换器"""

    def __init__(self):
        """初始化转换器"""
        self.ebook_convert_path = self._find_ebook_convert()

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

    def convert_to_pdf(self, epub_path, pdf_path, is_bilingual=False):
        """将 EPUB 转换为 PDF
        
        Args:
            epub_path: EPUB 文件路径
            pdf_path: 输出 PDF 路径
            is_bilingual: 是否为中英双语版本
        """
        if not self.ebook_convert_path:
            print("错误：未找到 ebook-convert 工具，请安装 Calibre 或设置 CALIBRE_PATH")
            return False

        if not os.path.exists(epub_path):
            print(f"EPUB 文件不存在: {epub_path}")
            return False

        # 确保输出目录存在
        pdf_dir = os.path.dirname(pdf_path)
        if pdf_dir and not os.path.exists(pdf_dir):
            os.makedirs(pdf_dir, exist_ok=True)

        # 使用绝对路径
        epub_path = os.path.abspath(epub_path)
        pdf_path = os.path.abspath(pdf_path)

        try:
            print(f"正在转换 {epub_path} 到 {pdf_path}")

            # 根据是否为双语版本选择不同的配置
            if is_bilingual:
                # 中英双语 PDF 配置 - 字号放大
                cmd = [
                    self.ebook_convert_path,
                    epub_path,
                    pdf_path,
                    "--pdf-page-numbers",
                    "--pdf-footer-template", "",
                    "--pdf-header-template", "",
                    "--pdf-default-font-size", "18",
                    "--pdf-mono-font-size", "16",
                    "--pdf-serif-family", "SimSun",
                    "--pdf-sans-family", "SimHei",
                    "--pdf-mono-family", "Consolas",
                    "--paper-size", "a4",
                    "--margin-top", "36",
                    "--margin-bottom", "36",
                    "--margin-left", "16",
                    "--margin-right", "16"
                ]
            else:
                # 纯中文 PDF 配置 - 字号放大
                cmd = [
                    self.ebook_convert_path,
                    epub_path,
                    pdf_path,
                    "--pdf-page-numbers",
                    "--pdf-footer-template", "",
                    "--pdf-header-template", "",
                    "--pdf-default-font-size", "16",
                    "--pdf-mono-font-size", "14",
                    "--pdf-serif-family", "SimSun",
                    "--pdf-sans-family", "SimHei",
                    "--pdf-mono-family", "Consolas",
                    "--paper-size", "a4",
                    "--margin-top", "36",
                    "--margin-bottom", "36",
                    "--margin-left", "16",
                    "--margin-right", "16"
                ]

            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0:
                if os.path.exists(pdf_path):
                    print(f"PDF 转换成功: {pdf_path}")
                    return True
                else:
                    print(f"PDF 转换命令成功，但文件未生成: {pdf_path}")
            else:
                print(f"PDF 转换失败: {result.stderr}")
                
            # 尝试以管理员身份运行
            print("\n尝试以管理员身份运行...")
            
            # 构建 PowerShell 命令
            ps_cmd = self._build_ps_command(epub_path, pdf_path, is_bilingual)
            
            # 保存为临时脚本文件
            import tempfile
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
                    print(f"PDF 转换成功: {pdf_path}")
                    return True
                else:
                    print(f"以管理员身份运行后文件仍未生成: {pdf_path}")
                    print(f"PowerShell 输出: {result.stdout}")
                    print(f"PowerShell 错误: {result.stderr}")
            except Exception as e:
                print(f"以管理员身份运行出错: {e}")
            finally:
                if os.path.exists(temp_script):
                    try:
                        os.unlink(temp_script)
                    except:
                        pass
            
            print("\n建议：请手动使用 Calibre 转换 EPUB 到 PDF")
            return False

        except Exception as e:
            print(f"转换过程出错: {e}")
            print("\n建议：请手动使用 Calibre 转换 EPUB 到 PDF")
            return False

    def _build_ps_command(self, epub_path, pdf_path, is_bilingual):
        """构建 PowerShell 命令"""
        if is_bilingual:
            return f"""& '{self.ebook_convert_path}' '{epub_path}' '{pdf_path}' --pdf-page-numbers --pdf-footer-template '' --pdf-header-template '' --pdf-default-font-size 18 --pdf-mono-font-size 16 --pdf-serif-family SimSun --pdf-sans-family SimHei --pdf-mono-family Consolas --paper-size a4 --margin-top 36 --margin-bottom 36 --margin-left 16 --margin-right 16"""
        else:
            return f"""& '{self.ebook_convert_path}' '{epub_path}' '{pdf_path}' --pdf-page-numbers --pdf-footer-template '' --pdf-header-template '' --pdf-default-font-size 16 --pdf-mono-font-size 14 --pdf-serif-family SimSun --pdf-sans-family SimHei --pdf-mono-family Consolas --paper-size a4 --margin-top 36 --margin-bottom 36 --margin-left 16 --margin-right 16"""

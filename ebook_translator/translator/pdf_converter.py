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
    
    def convert_to_pdf(self, epub_path, pdf_path):
        """将 EPUB 转换为 PDF"""
        if not self.ebook_convert_path:
            print("错误：未找到 ebook-convert 工具，请安装 Calibre 或设置 CALIBRE_PATH")
            return False
        
        try:
            print(f"正在转换 {epub_path} 到 {pdf_path}")
            
            # 构建命令
            cmd = [
                self.ebook_convert_path,
                epub_path,
                pdf_path,
                "--page-breaks-before", "/\*/",
                "--pdf-page-numbers",
                "--pdf-footer-template", "",
                "--pdf-header-template", ""
            ]
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"PDF 转换成功: {pdf_path}")
                return True
            else:
                print(f"PDF 转换失败: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"转换过程出错: {e}")
            return False

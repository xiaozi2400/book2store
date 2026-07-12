"""
字体注册模块 - 中文字体注册供 ReportLab 使用
"""
import os
import glob
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_font_registered = False
_registered_font_name = None


def register_chinese_fonts():
    """注册中文字体"""
    global _font_registered, _registered_font_name

    if _font_registered:
        return

    font_candidates = [
        ("SimHei", "C:/Windows/Fonts/simhei.ttf"),
        ("MicrosoftYaHei", "C:/Windows/Fonts/msyh.ttc"),
        ("SimSun", "C:/Windows/Fonts/simsun.ttc"),
        ("STKaiti", "C:/Windows/Fonts/STKAITI.TTF"),
    ]

    for font_name, font_path in font_candidates:
        try:
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                _font_registered = True
                _registered_font_name = font_name
                return
        except Exception:
            continue

    font_patterns = [
        "C:/Windows/Fonts/*.ttf",
        "C:/Windows/Fonts/*.ttc",
    ]

    for pattern in font_patterns:
        for font_path in glob.glob(pattern):
            try:
                font_name = os.path.splitext(os.path.basename(font_path))[0]
                if any(keyword in font_name.lower() for keyword in ['kai', 'song', 'hei', 'ming', 'ti', 'yahei']):
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    _font_registered = True
                    _registered_font_name = font_name
                    return
            except Exception:
                continue


def get_chinese_font() -> str:
    """获取已注册的中文字体名称"""
    global _registered_font_name
    if _registered_font_name:
        return _registered_font_name
    if _font_registered:
        return "SimHei"
    return "Helvetica"

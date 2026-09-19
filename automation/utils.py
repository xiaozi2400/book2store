"""
工具函数模块
"""
import os
import re
import json
import hashlib
import logging
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


def setup_logging(log_dir: str = "./logs"):
    """配置日志"""
    Path(log_dir).mkdir(exist_ok=True)

    log_file = Path(log_dir) / f"automation_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    # 仅终端输出 WARNING 及以上（保留错误和警告），细节日志只写入文件
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            handler.setLevel(logging.WARNING)

    return logging.getLogger(__name__)


logger = setup_logging()


def calculate_file_hash(filepath: str) -> str:
    """计算文件MD5哈希"""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def ensure_dir(path: str) -> Path:
    """确保目录存在"""
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_file_size(filepath: str) -> int:
    """获取文件大小（字节）"""
    return os.path.getsize(filepath) if os.path.exists(filepath) else 0


def clean_filename(filename: str) -> str:
    """清理文件名"""
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    return filename


def extract_title_from_filename(filename: str) -> str:
    """从文件名提取书名"""
    name = os.path.splitext(filename)[0]
    name = re.sub(r'[-_]+', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def is_valid_epub(filepath: str) -> bool:
    """验证EPUB文件"""
    import zipfile

    if not filepath.lower().endswith('.epub'):
        return False

    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            namelist = zf.namelist()
            has_html = any(f.endswith(('.html', '.xhtml', '.htm')) for f in namelist)
            return has_html
    except Exception as e:
        logger.warning(f"验证EPUB失败: {filepath}, 错误: {e}")
        return False


def parse_author_from_metadata(metadata: Dict) -> Optional[str]:
    """从元数据解析作者"""
    author = metadata.get('author') or metadata.get('creator')
    if isinstance(author, list):
        author = author[0] if author else None
    return author


def parse_title_from_metadata(metadata: Dict) -> Optional[str]:
    """从元数据解析标题"""
    title = metadata.get('title')
    if isinstance(title, list):
        title = title[0] if title else None
    return title


def format_price(price: float) -> str:
    """格式化价格"""
    return f"¥{price:.2f}"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def similarity_score(s1: str, s2: str) -> float:
    """计算两个字符串的相似度"""
    s1 = s1.lower().strip()
    s2 = s2.lower().strip()

    if s1 == s2:
        return 1.0

    if s1 in s2 or s2 in s1:
        return 0.8

    from difflib import SequenceMatcher
    return SequenceMatcher(None, s1, s2).ratio()


def match_filename_to_book(filename: str, book_title: str) -> float:
    """匹配文件名和书名"""
    filename_clean = re.sub(r'[_\-\.]+', ' ', filename.lower())
    book_title_clean = book_title.lower()

    return similarity_score(filename_clean, book_title_clean)


def load_json(filepath: str) -> Dict:
    """加载JSON文件"""
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_json(data: Dict, filepath: str):
    """保存JSON文件"""
    ensure_dir(os.path.dirname(filepath))
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def move_processed_epubs(input_dir: str) -> int:
    """将 input_dir 中的 epub 文件移到 '已处理' 子目录

    Args:
        input_dir: 输入目录路径

    Returns:
        成功移动的文件数量
    """
    processed_dir = Path(input_dir) / "已处理"
    processed_dir.mkdir(exist_ok=True)

    moved = 0
    for epub_file in Path(input_dir).glob("*.epub"):
        dest = processed_dir / epub_file.name
        # 避免同名覆盖，追加时间戳
        if dest.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = processed_dir / f"{epub_file.stem}_{timestamp}{epub_file.suffix}"
        try:
            shutil.move(str(epub_file), str(dest))
            moved += 1
        except Exception as e:
            logger.warning(f"移动文件失败: '{epub_file.name}' -> {e}")
    return moved


def check_unbackfilled_failed_books():
    """启动时静默检测：若有历史发布失败未回填则打印黄色提示。不修改数据。"""
    from .database import DatabaseManager
    try:
        db = DatabaseManager()
        count = db.count_unbackfilled_failed()
        if count > 0:
            print("\n[yellow]⚠ 检测到 %d 本历史发布失败未标记 publish_status='failed'[/yellow]" % count)
            print("[yellow]  运行 python -m automation.main backfill-publish-status 一次性回填[/yellow]\n")
    except Exception:
        pass  # 启动检测失败不应阻塞主流程

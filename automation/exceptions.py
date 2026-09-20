"""
自定义异常体系 - 为各模块提供统一的错误类型
"""


class BookfileBaseError(Exception):
    """所有自定义异常的基类"""

    def __init__(self, message: str = "", book_id: str = ""):
        self.message = message
        self.book_id = book_id
        super().__init__(self.message)

    def __str__(self):
        if self.book_id:
            return f"[{self.book_id}] {self.message}"
        return self.message


# ===== 流水线相关 =====
class PipelineError(BookfileBaseError):
    """流水线执行错误"""

    pass


# ===== 翻译相关 =====
class TranslationError(PipelineError):
    """翻译失败"""

    pass


class TranslationCacheError(BookfileBaseError):
    """翻译缓存错误"""

    pass


# ===== 精简版相关 =====
class SummaryError(BookfileBaseError):
    """精简版生成失败"""

    pass


class SuitabilityError(BookfileBaseError):
    """适合度评估失败"""

    pass


# ===== 图片相关 =====
class ImageError(BookfileBaseError):
    """图片处理失败（生成或提取）"""

    pass


class ImageGenerationError(ImageError):
    """主图生成失败"""

    pass


# ===== 文案相关 =====
class CopywritingError(BookfileBaseError):
    """文案生成失败"""

    pass


# ===== 发布相关 =====
class PublishError(PipelineError):
    """发布到闲鱼失败"""

    pass


class LoginError(PublishError):
    """闲鱼登录失败"""

    pass


class SKUConfigError(PublishError):
    """SKU 配置失败"""

    pass


# ===== 文件相关 =====
class FileError(BookfileBaseError):
    """文件操作失败"""

    pass


class EPUBParseError(FileError):
    """EPUB 解析失败"""

    pass


class PDFConvertError(FileError):
    """PDF 转换失败"""

    pass


# ===== 数据库相关 =====
class DatabaseError(BookfileBaseError):
    """数据库操作失败"""

    pass


# ===== 配置相关 =====
class ConfigError(BookfileBaseError):
    """配置错误"""

    pass


# ===== 阶段处理工具 =====
def wrap_stage_error(stage_name: str, original_error: Exception, book_id: str = "") -> BookfileBaseError:
    """将原始异常包装为阶段异常"""
    error_map = {
        "translation": TranslationError,
        "summarize": SummaryError,
        "image_generation": ImageGenerationError,
        "copywriting": CopywritingError,
        "publish": PublishError,
    }
    error_class = error_map.get(stage_name, BookfileBaseError)
    return error_class(str(original_error), book_id)

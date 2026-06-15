"""EPUB 文件质量检查工具。

一个独立子项目，调用外部 EPUBCheck（Java）验证 EPUB 文件是否符合 EPUB 3.3 出版社标准。
本工具只做胶水代码：参数拼装、JSON 解析、报告渲染、CLI 编排。所有校验规则由 EPUBCheck 提供。
"""
__version__ = "0.1.0"

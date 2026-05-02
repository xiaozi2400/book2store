# Checklist: EPUB 翻译映射系统重构

## 编码阶段

- [ ] `epub_parser.py` 中 `get_paragraphs()` 为段落添加 `trans_id` 字段
- [ ] `epub_parser.py` 生成的段落数据包含 `trans_id`
- [ ] `epub_generator.py` 中 `_create_translation_map()` 使用 `trans_id` 作为键
- [ ] `epub_generator.py` 中 `_process_html_content()` 为标签添加 `data-trans-id` 属性
- [ ] `epub_generator.py` 中 `_process_html_content()` 通过 `data-trans-id` 直接查找翻译
- [ ] `<a>` 标签的 `href` 属性在翻译时保留

## 验证阶段

- [ ] 测试模式生成双语 EPUB
- [ ] 第一章（c01）正文段落有翻译 span
- [ ] 目录页（toc.xhtml）`<a>` 标签保留 href
- [ ] 目录页翻译 span 在 `<a>` 内部
- [ ] 完整翻译模式生成正确结果

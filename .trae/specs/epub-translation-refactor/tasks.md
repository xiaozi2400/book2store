# Tasks: EPUB 翻译映射系统重构

## 任务列表

### Task 1: 修改 EPUBParser 为 HTML 元素添加 data-trans-id 标记
[ ] Task 1.1: 在 `epub_parser.py` 中修改 `get_paragraphs()` 方法
- [ ] 为每个提取的段落添加 `trans_id` 字段（基于文本内容生成 hash）
- [ ] 在返回的段落数据中包含 `trans_id`

### Task 2: 修改 EPUBGenerator._create_translation_map() 使用 trans_id 作为键
[ ] Task 2.1: 修改 `_create_translation_map()` 方法
- [ ] 使用 `trans_id` 而非 `para_id` 作为映射键
- [ ] 保留 original, translated, html 等字段

### Task 3: 修改 _process_html_content() 使用 data-trans-id 直接查找翻译
[ ] Task 3.1: 修改 `_process_html_content()` 方法
- [ ] 读取 HTML 内容后，为需要翻译的标签添加 `data-trans-id` 属性
- [ ] 通过 `tag.get('data-trans-id')` 直接查找翻译映射
- [ ] 保留 `<a>` 标签的 `href` 属性用于目录链接

### Task 4: 验证正文翻译是否正确应用
[ ] Task 4.1: 运行测试模式生成 EPUB
- [ ] 检查第一章（c01）段落是否有翻译 span
- [ ] 确认双语结构正确：`原文<br/><span class="translated">翻译</span>`

### Task 5: 验证目录链接保留
[ ] Task 5.1: 检查目录页（toc.xhtml）
- [ ] 确认 `<a>` 标签保留 `href` 属性
- [ ] 确认翻译 span 添加在 `<a>` 标签内部

### Task 6: 完整翻译测试
[ ] Task 6.1: 不使用测试模式，运行完整翻译
- [ ] 生成双语 EPUB
- [ ] 生成中文 EPUB
- [ ] 生成 PDF

## 任务依赖关系

- Task 2 依赖 Task 1（需要 trans_id）
- Task 3 依赖 Task 1 和 Task 2（需要 data-trans-id 标记和正确的翻译映射）
- Task 4, 5, 6 依赖 Task 3

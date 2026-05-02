# EPUB 翻译映射系统重构规格说明

## Why
当前 EPUB 翻译系统存在翻译映射与 HTML 内容文本不匹配的根本性架构问题，导致正文内容无法正确应用翻译。问题根源在于 `_create_translation_map` 使用段落 ID 作为键，但 `_process_html_content` 实际匹配时是通过文本内容查找，而非 ID 匹配。

## What Changes

### 核心问题分析

**当前流程（有问题）：**
1. `parser.get_paragraphs()` 提取纯文本和 ID
2. `_create_translation_map(translated_paragraphs)` 创建映射：`{para_id: {original, translated}}`
3. `_process_html_content()` 处理 HTML 时，使用 `tag.get_text()` 获取文本并遍历 translation_map 匹配

**问题：**
- translation_map 的键是 `para_id`（如 `xhtml_c01_0`）
- 但匹配时用文本内容去比较 `para_data['original']`
- 存在文本不同步问题：HTML 中的实际文本与 get_paragraphs 提取的文本可能不一致

### 重构方案

**新流程：**
1. 解析 EPUB 时，为每个需要翻译的元素添加唯一标识（使用 ID 属性或生成 hash）
2. 翻译时，存储 `(identifier, original_text, translated_text)` 三元组
3. 处理 HTML 时，通过 ID 直接查找翻译，而非文本匹配

**关键设计决策：**
- 在原始 HTML 标签上添加 `data-trans-id` 属性标记需要翻译的元素
- `_process_html_content` 通过 `data-trans-id` 直接定位翻译，而非文本匹配

## Impact

### 受影响的规格
- EPUB 生成器规格
- 翻译缓存规格

### 受影响的代码
- `ebook_translator/translator/epub_generator.py` - 核心重构
- `ebook_translator/translator/epub_parser.py` - 添加元素标记功能

## ADDED Requirements

### Requirement: HTML 元素翻译标记系统
系统 SHALL 在解析 EPUB 时为需要翻译的 HTML 元素添加唯一标识符。

#### Scenario: 解析 EPUB 时标记元素
- **WHEN** `EPUBParser.parse()` 解析 EPUB 内容文件
- **THEN** 为每个需要翻译的标签（p, h1-h6, li, div, a 等）添加 `data-trans-id="hash值"` 属性

### Requirement: 基于 ID 的翻译映射
系统 SHALL 使用唯一 ID 而非文本内容来匹配翻译。

#### Scenario: 创建翻译映射
- **WHEN** `_create_translation_map()` 被调用
- **THEN** 创建映射 `{data_trans_id: {original, translated, html}}`

#### Scenario: 应用翻译到 HTML
- **WHEN** `_process_html_content()` 处理 HTML
- **THEN** 通过 `tag.get('data-trans-id')` 直接查找翻译
- **AND** 若找到翻译，应用双语结构：`原文 + <span class="translated">翻译</span>`

### Requirement: 目录链接保留
系统 SHALL 在翻译目录页时保留 `<a>` 标签的 `href` 属性，确保 PDF 目录跳转功能正常。

#### Scenario: 目录页 `<a>` 标签翻译
- **WHEN** 处理目录页（文件名包含 'toc'）中的 `<a>` 标签
- **THEN** 保留 `href` 属性
- **AND** 生成结构：`<a href="..." data-trans-id="...">原文<span class="translated">翻译</span></a>`

## MODIFIED Requirements

### Requirement: 正文内容翻译
系统 SHALL 为正文内容中的段落添加翻译，生成双语结构。

#### Scenario: 正文段落翻译
- **WHEN** 处理正文文件中的 `<p>` 标签
- **THEN** 保留所有原有属性
- **AND** 添加双语结构：`<p original-text>原文<br/><span class="translated">翻译</span></p>`

## REMOVED Requirements

### Requirement: 基于文本匹配的翻译查找（旧方案）
**Reason**: 文本匹配在复杂 EPUB 结构中不可靠，容易出现不匹配问题
**Migration**: 改用基于 ID 的精确匹配

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 安装
pip install -r requirements-automation.txt
pip install -r ebook_translator/requirements.txt
playwright install chromium

# 核心工作流
python -m automation.main init                                     # 初始化数据库
python -m automation.main auto                                     # 一键处理 input_dir 新书
python -m automation.main auto --skip-publish --skip-cache         # 跑到发布前 + 强制重译
python -m automation.main process <book_id>                        # 处理单本(book_id 支持前缀匹配)
python -m automation.main test                                     # 测试模式(从 test_input_dir 读,跳过发布)
python -m automation.main publish <book_id> --auto                 # 发布到闲鱼
python -m automation.main generate_list <book_id>                  # 发布失败的备用方案
python -m automation.main regenerate-images --book-id <book_id>   # 修改主图 prompt 后复用 summary 重跑

Excel 链接导入

# 测试(conftest.py 自动用内存数据库,无需 mock)
pytest
pytest tests/test_quality_checker.py -v
pytest -k "token" -v

# standalone 翻译(不依赖数据库)
python -m ebook_translator.main <input.epub> -o <output_dir> --test-mode
```

## 架构

CLI 入口:`automation/main.py` (Typer)。`auto` 是核心命令,流水线为:扫描 → 翻译 → 摘要 → 主图 → 文案 → 发布,每步 `--skip-*` 可控。`phase()` 上下文管理器(`automation/progress.py`)包裹每个耗时阶段输出进度。

`automation/` 下按流水线分模块:`directory_scanner` / `translation_processor` (包装 `ebook_translator.library`) / `translation_cache` / `content_summarizer` (大文件 74KB,先经 `suitability_evaluator` 评估再生成精简版 PDF) / `image_generator` / `ai_copywriter` / `xianyu_publisher` (大文件 31KB,Playwright 自动化) / `quality_checker` (大文件 27KB,纯规则 8 维度质检,零 API 成本)。

`ebook_translator/` 是可独立运行的 EPUB 翻译子项目,`library.py` 是给 automation 调用的接口。

## 数据

SQLite (`data/automation.db`,SQLAlchemy ORM,`automation/database.py` 管理):`Book` (基础信息/status) / `BookOutput` (1:1,存所有产物路径+ `quality_report` JSON) / `TokenUsage` (按 book × step 统计) / `TranslationCache` (段落 MD5 查重,替代旧 `translation_cache.json`) / `ProcessingLog` / `ShareLink`。

## 配置

- `config.yaml` — 主配置(`ai.api_key` 必填,SKU、闲鱼、适合度评估、质量阈值)
- `pdf_config.json` — PDF 排版
- `automation/config.py` — `Config` 单例,缺失字段回落默认值

## 关键约定与坑点

- **状态机**:`Book.status` 走 `pending → processing → completed/failed`,`auto` 跑完会把 input_dir 的 EPUB 移到"已处理"子目录(`utils.move_processed_epubs`)
- **缓存**:`TranslationCache` 段落 MD5 查重,旧 `translation_cache.json` 首次运行自动迁移
- **EPUB 文件名尾随空格会导致路径异常** — `directory_scanner` 已用 `Path(...).stem.strip()` 防御
- **API Key 两处**:`config.yaml` 的 `ai.api_key`(主流程);`ebook_translator/config.py` 的 `DEEPSEEK_API_KEY`(standalone 模式)
- **闲鱼发布失败**:`logs/publish_error_*.png` 有截图;`metadata/` 目录未删除时可直接重试,删除后需重跑 `auto`
- **跨平台**:Windows + Git Bash,Playwright/Chrome 路径处理需在 Windows 验证
- **测试**:`tests/` 正式测试,根目录 `test_*.py` 是历史遗留脚本(基本被替代)
- **历史/计划文档**:`docs/superpowers/{plans,specs}/` 改大功能前可翻

## 详细文档

- `README.md` — 完整命令参考 + 配置 + 输出结构 + FAQ
- `PRD.md` / `TECH_SPEC.md` — 产品需求与技术方案
- `PDF排版配置说明.md` — PDF 排版字段说明
- `ebook_translator/README.md` — standalone 翻译器

# 运行测试 Skill

## 触发条件

- 用户调用 `/run-tests`
- 用户请求"执行测试"、"运行测试"、"run tests"、"测试"

## 步骤

### 1. 获取代码变更

运行 `git diff --name-only HEAD~1` 获取变更文件列表。

### 2. 分析影响范围

根据变更文件确定受影响的模块：

| 触发条件 | 策略 |
|-----------------|----------|
| 变更了 `database.py`、`models.py`、`config.py`、`conftest.py` | 运行所有测试 |
| 变更了配置文件（`.yaml`、`.json`） | 运行所有测试（跳过 E2E） |
| 变更文件数 > 10 | 运行所有测试 |
| 变更了 `pipeline.py` | 运行单元测试 + 集成测试 + e2e |
| 变更了 `main.py` | 运行集成测试 |
| 单个模块变更 | 精确映射 |

### 3. 构建测试列表

使用以下映射确定要运行的测试：

```python
MODULE_TEST_MAPPING = {
    "automation/main.py": [
        "tests/unit/test_progress.py",
        "tests/integration/test_main_image_integration.py",
        "tests/integration/test_main_summary_flow.py",
    ],
    "automation/pipeline.py": [
        "tests/unit/test_pipeline.py",
        "tests/integration/test_translation_pipeline.py",
        "tests/integration/test_main_image_integration.py",
        "tests/integration/test_main_summary_flow.py",
        "tests/integration/test_republish_failed.py",
        "tests/e2e/test_full_pipeline.py",
    ],
    "automation/summarizer/": [
        "tests/unit/test_summary_text.py",
        "tests/unit/test_content_summarizer_tokens.py",
        "tests/integration/test_main_summary_flow.py",
        "tests/integration/test_summary_save.py",
    ],
    "automation/translation/": [
        "tests/integration/test_translation_pipeline.py",
    ],
    "automation/image/": [
        "tests/unit/test_image_generator.py",
        "tests/unit/test_image_generator_clarity.py",
        "tests/unit/test_image_generator_unit.py",
        "tests/integration/test_main_image_integration.py",
    ],
    "automation/publishing/": [
        "tests/unit/test_copywriting_bugs.py",
        "tests/unit/test_xianyu_prompt_config.py",
        "tests/integration/test_republish_failed.py",
    ],
    "automation/database.py": ["tests/"],  # 基础设施 - 所有测试
    "automation/models.py": ["tests/"],     # 基础设施 - 所有测试
    "automation/config.py": ["tests/"],      # 配置驱动 - 所有测试
    "automation/ai_client.py": [
        "tests/unit/test_ai_client_summary.py",
        "tests/unit/test_ai_client_tokens.py",
    ],
    "tests/conftest.py": ["tests/"],       # 全局 fixture - 所有测试
}
```

### 4. 执行测试

使用选定的测试路径运行 pytest：
```bash
pytest <test_files> -v --tb=short
```

### 5. 报告结果

展示：
- 变更文件列表
- 选中的测试
- 通过/失败汇总
- 执行时间

## 注意事项

- 默认跳过 E2E 测试，除非 `pipeline.py` 或 `main.py` 发生变更
- 如果未检测到变更，提示"未检测到代码变更"
- 测试会自动去重

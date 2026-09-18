# Run Tests Skill

## Triggers

- User invokes `/run-tests`
- User requests "执行测试", "运行测试", "run tests", "测试"

## Steps

### 1. Get Code Changes

Run `git diff --name-only HEAD~1` to get the list of modified files.

### 2. Analyze Impact

Determine affected modules based on changed files:

| Trigger Condition | Strategy |
|-----------------|----------|
| Changed `database.py`, `models.py`, `config.py`, `conftest.py` | Run all tests |
| Changed config files (`.yaml`, `.json`) | Run all tests (skip E2E) |
| Changed file count > 10 | Run all tests |
| Changed `pipeline.py` | Run unit + integration + e2e |
| Changed `main.py` | Run integration tests |
| Single module change | Precise mapping |

### 3. Build Test List

Use this mapping to determine which tests to run:

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
    "automation/database.py": ["tests/"],  # Infrastructure - all tests
    "automation/models.py": ["tests/"],     # Infrastructure - all tests
    "automation/config.py": ["tests/"],      # Config driven - all tests
    "automation/ai_client.py": [
        "tests/unit/test_ai_client_summary.py",
        "tests/unit/test_ai_client_tokens.py",
    ],
    "tests/conftest.py": ["tests/"],       # Global fixture - all tests
}
```

### 4. Execute Tests

Run pytest with selected test paths:
```bash
pytest <test_files> -v --tb=short
```

### 5. Report Results

Display:
- Changed files list
- Tests selected for execution
- Pass/fail summary
- Execution time

## Notes

- E2E tests are skipped by default unless `pipeline.py` or `main.py` changed
- If no changes detected, prompt "No code changes detected"
- Tests are de-duplicated automatically

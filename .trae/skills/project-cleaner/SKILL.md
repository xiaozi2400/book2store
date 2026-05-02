---
name: "project-cleaner"
description: "Cleans temporary and unused files from the project. Invoke when user asks to clean temporary files, remove unused files, or organize project structure."
---

# Project Cleaner

Cleans temporary and unused files from the project while preserving core functionality.

## When to Invoke

This skill should be invoked when:
- User says "清理临时文件" or "清理无用文件"
- User asks to "clean up the project"
- User mentions removing temporary debug/test files
- User wants to organize project structure

## Important Precautions

### ⚠️ SAFETY FIRST - NEVER delete without verification

1. **Preview before delete**: Always run `git status` and `git clean -n -d` first
2. **Check if file is imported**: Before deleting any `.py` file, verify it's not imported by other modules:
   ```bash
   grep -r "from.*import\|import" --include="*.py" | grep "filename"
   ```
3. **Verify in Git history**: Check if file was ever tracked in Git:
   ```bash
   git log --all --oneline -- filename.py
   ```
4. **List files to be deleted**: Show user the list before executing deletion

## Safe Cleanup Rules

### CAN safely delete:
- Debug scripts: `analyze_*.py`, `check_*.py`, `verify_*.py`, `test_*.py`
- Temporary outputs: `*.log`, `temp*.txt`, `toc_*.txt`
- Build artifacts: `__pycache__/`, `*.pyc`
- Backup files: `*.bak`, `*.swp`

### DO NOT delete:
- Any file in `automation/` directory (core modules)
- Any file in `ebook_translator/` directory (core modules)
- Config files: `config.yaml`, `pdf_config.json`, `.gitignore`
- Documentation: `README.md`, `PRD.md`, `TECH_SPEC.md`

### VERIFY before deleting:
- Check if file is imported: `grep -r "suitability_evaluator\|template_generator" --include="*.py"`
- Check if file exists in current codebase: `ls -la filename.py`

## Automatic Verification Steps

The skill MUST perform these checks before any deletion:

### Step 1: Check if file is imported by any Python module
```bash
# For each .py file to be deleted, check if it's imported elsewhere
grep -r "import.*filename\|from.*filename" --include="*.py" .
# Or for specific files:
grep -r "suitability_evaluator\|template_generator" --include="*.py" .
```

### Step 2: Check Git history
```bash
# Verify file was never committed (or was deleted intentionally)
git log --all --oneline -- filename.py
```

### Step 3: Check if in critical directories
```bash
# NEVER proceed if file is in these directories:
# - automation/
# - ebook_translator/
# - Any directory with core business logic
```

### Step 4: Test import before deleting
```bash
# Try importing the module to verify it works
python -c "from automation.content_summarizer import ContentSummarizer; print('OK')"
```

## Workflow with Auto-Check

1. **List untracked files**: `git status --porcelain`
2. **For each .py file**, run:
   - `grep -r "import.*<filename>" --include="*.py" .`
   - If found imports → STOP, do not delete
3. **Verify directory location**:
   - Files in `automation/` or `ebook_translator/` → STOP
4. **Test run**: Run import test to ensure project works
5. **Only then**: Create cleanup plan in Plan Mode

## Cleanup Workflow

1. **Check current status**:
   ```bash
   git status --porcelain
   git clean -n -d
   ```

2. **Identify untracked files**:
   ```bash
   git status | grep "^??"
   ```

3. **Verify each file**:
   - Check if imported in any Python file
   - Check if in `.gitignore`
   - Check if created during normal operation

4. **Create plan** (in Plan Mode):
   - List files to delete
   - List files to keep
   - Get user confirmation

5. **Execute and commit**:
   - Delete confirmed files
   - Commit with clear message

## Recovery

If something goes wrong:
- Most files can be recovered: `git checkout -- filename`
- Full reset: `git reset --hard HEAD`
- Or re-clone from remote

## Post-Cleanup Verification

After cleanup, MUST verify project still works:

```bash
# Test core imports
python -c "from automation.main import app; print('OK')"
python -c "from automation.content_summarizer import ContentSummarizer; print('OK')"
python -c "from ebook_translator.main import main; print('OK')"
```

If any import fails → STOP and restore deleted files immediately.

## Example Dialog

User: "清理项目中的临时文件"

Response:
1. First check: `git status` and `git clean -n -d`
2. Analyze untracked files
3. Identify which are safe to delete
4. Create cleanup plan in Plan Mode
5. Execute after user approval

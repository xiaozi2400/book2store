# Deprecated Code Review Report

**Date**: 2026-09-18
**Reviewer**: Claude Code Architecture Review
**Scope**: automation/, ebook_translator/, tests/, docs/

---

## 1. P0 - Critical (Should Fix Now)

### 1.1 `ImageExtractionError` Class - Orphaned After Stage Removal

| Item | Detail |
|------|--------|
| **Location** | `automation/exceptions.py:52-54` (class definition)<br>`automation/exceptions.py:114` (error_map entry) |
| **Issue** | `ImageExtractionStage` was removed from `pipeline.py` but `ImageExtractionError` remains. The error is only referenced in `wrap_stage_error()` for a stage that no longer exists. |
| **Code** | ```python<br>class ImageExtractionError(ImageError):<br>    """图片提取失败"""<br>    pass<br><br># In error_map:<br>"image_extraction": ImageExtractionError,<br>``` |
| **Action** | **DELETE** `ImageExtractionError` class and remove `"image_extraction"` from `error_map` |
| **Priority** | P0 |

---

## 2. P1 - Deprecated (Should Address)

### 2.1 Legacy JSON Cache Migration Code

| Item | Detail |
|------|--------|
| **Location** | `automation/translation/translation_processor.py:128-140`<br>`automation/translation/translation_cache.py:90-150` |
| **Issue** | Old JSON cache (`ebook_translator/translation_cache.json`, 122KB) still exists. Migration code runs on every translation startup, checking for JSON file existence. After migration completes, this becomes dead code. |
| **Files** | JSON cache at `ebook_translator/translation_cache.json` (exists since May 30) |
| **Action** | After confirming migration is complete, remove the one-time migration logic from `_do_translate()` and `migrate_from_json()` method |
| **Priority** | P1 |

### 2.2 Outdated `.gitignore` Patterns

| Item | Detail |
|------|--------|
| **Location** | `.gitignore:39, 44` |
| **Issue** | Patterns `!test_*.py` exist but no legacy root-level `test_*.py` files found (CLAUDE.md:60 claims they exist but they don't) |
| **Code** | ```gitignore<br>!test_*.py  # line 39<br>!test_*.py  # line 44<br>``` |
| **Action** | Remove `!test_*.py` patterns from `.gitignore` since these files don't exist |
| **Priority** | P1 |

### 2.3 Documentation References Removed Code

| Item | Detail |
|------|--------|
| **Location** | `docs/ARCHITECTURE_REVIEW.md:122, 417, 461-485, 700, 711` |
| **Issue** | Documents reference `ImageExtractionStage` as "disabled" but it has already been removed from `pipeline.py`. The P2 item (line 700) titled "清理 ImageExtractionStage" is no longer applicable. |
| **Action** | Update ARCHITECTURE_REVIEW.md to reflect current state - `ImageExtractionStage` is already cleaned up |
| **Priority** | P1 |

---

## 3. P2 - Low Priority / Informational

### 3.1 Placeholder Fallback Method

| Item | Detail |
|------|--------|
| **Location** | `automation/publishing/xianyu_publisher.py:344-358` |
| **Issue** | `_try_open_via_placeholder()` is a 4th fallback method for opening category dropdown. It works but may be redundant given 3 other methods (`_try_open_via_sibling`, `_try_open_via_label`, `_try_open_via_scan`) |
| **Status** | Currently used in production, not dead code |
| **Action** | Consider consolidating if reliability is confirmed |
| **Priority** | P2 |

### 3.2 Empty `pass` Statements in Exception Classes

| Item | Detail |
|------|--------|
| **Location** | `automation/exceptions.py:22, 27, 33, 38, 44, 49, 54, 60, 66, 71, 76, 82, 87, 92, 98, 104` |
| **Issue** | Many exception classes just have `pass` (body-less subclasses that inherit behavior). This is normal Python idiom, not deprecated code, but noted for awareness |
| **Action** | None - this is idiomatic |
| **Priority** | P2 (informational only) |

---

## 4. Already Cleaned (Confirmed)

| Item | Status |
|------|--------|
| `ImageExtractionStage` in `pipeline.py` | ✅ Removed (only 5 stages now: Translation, Summary, ImageGeneration, Copywriting, Publish) |
| `image_extractor.py` | ✅ Deleted |
| `ImageExtractionStage` in `build_pipeline()` | ✅ Removed |

---

## 5. Summary of Recommended Actions

| Priority | Item | Action |
|----------|------|--------|
| P0 | `ImageExtractionError` | Delete class and error_map entry |
| P1 | JSON cache migration code | Remove after confirming migration complete |
| P1 | `.gitignore` patterns | Remove `!test_*.py` entries |
| P1 | `docs/ARCHITECTURE_REVIEW.md` | Update to reflect current state |
| P2 | Placeholder fallback | Consider consolidating later |

---

## 6. Files Scanned

- `automation/` - 31 Python files
- `ebook_translator/` - 10 Python files (excluding venv)
- `tests/` - 24 test files
- `docs/` - 2 main docs + 20 archived superpowers docs

**Search patterns used**:
- `TODO|FIXME|DEPRECATED|HACK|XXX|BUG` - No matches
- `image_extractor|ImageExtraction` - Found only `ImageExtractionError`
- `translation_cache.json|old_cache|migrate_from_json` - Found migration code
- `^\s*#\s*(def|class|if|for|while|import)` - No commented-out code blocks
- `@pytest.mark.skip` - No skipped tests

# 修复"翻译过短被回退到原文"问题

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 修复 `_quality_check` 在"翻译过短"分支错误地将译文回退为原文的问题，并适度放宽比例阈值，让翻译结果能正常展示。

**架构：** 
- 空翻译仍保留原文（合理）。
- 翻译过短（绝对长度不足或比例过低）改为"保留翻译"而非"保留原文"，同时不重试。
- 长文本（> 50 字符）翻译过短仍触发重试以保证质量。
- 调整 `min_translation_ratio` 默认值从 0.3 到 0.2，让章节标题等短翻译能通过。

**技术栈：** Python, pytest

---

### 任务 1：添加失败测试，捕获 bug

**文件：**
- 修改：`d:\project\bookfile_bat\tests\test_quality_check_optimization.py`

- [ ] **步骤 1.1：添加新测试用例：翻译过短时保留翻译而非原文**

在 `test_quality_check_optimization.py` 的 `FakeTranslator` 类之后添加新的测试函数：

```python
def test_short_translation_keeps_translated_not_original():
    """翻译过短（但非空）应保留翻译，不应回退原文"""
    t = FakeTranslator()
    result = {
        'id': 10,
        'original': '1 The Surprising Power of Atomic Habits',
        'translated': '1 原子习惯的惊人力量',  # 短但有效
        'html': '<p>1 The Surprising Power of Atomic Habits</p>',
        'tier': 'tier2_normal'
    }
    checked = t._quality_check(result, 'tier2_normal')
    assert checked['translated'] == '1 原子习惯的惊人力量', \
        f"翻译过短但有效的应保留翻译，实际得到: {checked['translated']}"
    assert checked['translated'] != result['original'], \
        "不应回退到原文"


def test_ratio_too_low_long_text_keeps_translated():
    """长文本翻译比例过低时保留翻译（不重试，因为重试大概率无效）"""
    t = FakeTranslator()
    result = {
        'id': 11,
        'original': 'This is a long English sentence that should normally translate to Chinese with similar length.',
        'translated': '短译文',  # 比例极低
        'html': '<p>Original</p>',
        'tier': 'tier2_normal'
    }
    # 当 min_translation_ratio = 0.3 时 '短译文' (3字符) 远低于 0.3 * 70 = 21 字符
    # 新行为: 应该保留翻译（不重试，不回退原文）
    checked = t._quality_check(result, 'tier2_normal')
    assert checked['translated'] == '短译文', \
        f"翻译过短应保留翻译，实际得到: {checked['translated']}"
```

- [ ] **步骤 1.2：运行测试验证失败**

运行：
```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -m pytest tests/test_quality_check_optimization.py -v
```

预期：新增的 `test_short_translation_keeps_translated_not_original` 失败（因为当前代码会回退到原文）。

- [ ] **步骤 1.3：运行更新前的检查脚本，记录当前未翻译段落数**

为后续对比，保存当前统计：

```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" d:\project\bookfile_bat\visual_inspect2.py > d:\project\bookfile_bat\before_fix.txt 2>&1
Get-Content d:\project\bookfile_bat\before_fix.txt -Encoding UTF8 | Select-Object -First 3
```

记录 `<p> 标签中 untranslated 段数` 作为基线（应当接近 2984）。

### 任务 2：修复 _quality_check —— 翻译过短保留翻译

**文件：**
- 修改：`d:\project\bookfile_bat\ebook_translator\translator\translator.py:479-553`

- [ ] **步骤 2.1：修改空翻译分支 —— 仍保留原文（合理）**

当前代码（保持不变）：

```python
if should_skip_retry:
    logger.info(f"  质量问题 ({', '.join(issues)}): {original[:50]}...")
    logger.info(f"  跳过重试，保留原文")
    result['translated'] = original
    self.stats['failed'] += 1
    return result
```

**问题**：该分支同时处理"空翻译"和"翻译过短"，但两者策略应不同。

- [ ] **步骤 2.2：拆分"空翻译"和"翻译过短"的处理逻辑**

将整个 `_quality_check` 方法替换为以下实现：

```python
    def _quality_check(self, result, tier='tier2_normal'):
        """质量检查 - 按 tier 和原文长度区分重试策略"""
        original = result['original']
        translated = result['translated']

        issues = []
        should_keep_original = False  # 保留原文（仅空翻译时使用）
        should_skip_retry = False     # 不重试

        # 空翻译：保留原文，不重试
        if not translated or not translated.strip():
            issues.append("空翻译")
            should_keep_original = True
            should_skip_retry = True

        orig_len = len(original)
        trans_len = len(translated)
        short_threshold = self.opt_config['quality_check'].get('short_text_min_length', 30)

        if orig_len > 0 and translated and translated.strip():
            ratio = trans_len / orig_len

            if orig_len <= short_threshold:
                min_absolute = self.opt_config['quality_check'].get('short_text_min_absolute', 3)
                if trans_len < min_absolute:
                    issues.append(f"翻译过短 (绝对长度 {trans_len} < {min_absolute})")
                    should_skip_retry = True
                if tier != 'tier3_long_complex' and ratio > self.opt_config['quality_check']['max_translation_ratio']:
                    issues.append(f"翻译过长 ({ratio:.2f})")
            else:
                if tier == 'tier3_long_complex':
                    min_ratio = self.opt_config['quality_check'].get('tier3_min_ratio', 0.1)
                    max_ratio = self.opt_config['quality_check'].get('tier3_max_ratio', 5.0)
                else:
                    min_ratio = self.opt_config['quality_check']['min_translation_ratio']
                    max_ratio = self.opt_config['quality_check']['max_translation_ratio']

                if ratio < min_ratio:
                    issues.append(f"翻译过短 ({ratio:.2f})")
                    should_skip_retry = True
                if ratio > max_ratio:
                    issues.append(f"翻译过长 ({ratio:.2f})")

            has_code_chars = any(c in original for c in ['{', '(', '[', '=', '<', '>', '\\', '`', '|', '&'])
            if not has_code_chars:
                if '===' in translated or '[段落' in translated:
                    issues.append("分隔符残留")

        # 空翻译：保留原文
        if should_keep_original:
            logger.info(f"  质量问题 ({', '.join(issues)}): {original[:50]}...")
            logger.info(f"  跳过重试，保留原文")
            result['translated'] = original
            self.stats['failed'] += 1
            return result

        # 翻译过短：保留翻译，不重试
        if should_skip_retry:
            logger.info(f"  质量问题 ({', '.join(issues)}): {original[:50]}...")
            logger.info(f"  跳过重试，保留翻译")
            self.stats['failed'] += 1
            return result

        if issues:
            logger.info(f"  质量问题 ({', '.join(issues)}): {original[:50]}...")

            # 仅对长文本（> 50 字符）重试，最多 1 次
            if len(original) > 50:
                logger.info(f"  尝试重译...")
                self.stats['retried'] += 1
                retry_result = self.translate(original, max_retries=1)

                if retry_result and len(retry_result) > len(translated) * 0.5:
                    result['translated'] = retry_result
                    logger.info(f"  重译成功")
                else:
                    logger.info(f"  重译失败或质量无改善，保留原结果")
                    self.stats['failed'] += 1
            else:
                logger.info(f"  短文本质量异常，跳过重试")
                self.stats['failed'] += 1

        return result
```

**关键变化**：
1. 新增 `should_keep_original` 标志，仅空翻译时为 True
2. 拆分"空翻译"和"翻译过短"为两个独立分支
3. 翻译过短时不再修改 `result['translated']`，保留翻译

- [ ] **步骤 2.3：运行新测试验证通过**

```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -m pytest tests/test_quality_check_optimization.py -v
```

预期：所有测试通过（包括任务 1 新增的 `test_short_translation_keeps_translated_not_original` 和 `test_ratio_too_low_long_text_keeps_translated`）。

- [ ] **步骤 2.4：运行全套翻译相关测试确保无回归**

```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -m pytest tests/test_translation_pipeline.py tests/test_translator_stats.py tests/test_quality_check_optimization.py -v
```

预期：所有测试通过。

### 任务 3：调整配置阈值

**文件：**
- 修改：`d:\project\bookfile_bat\ebook_translator\config.py:253-264`

- [ ] **步骤 3.1：将 min_translation_ratio 从 0.3 改为 0.2**

```python
    # 质量检查配置
    'quality_check': {
        'enabled': True,
        'min_translation_ratio': 0.2,   # 翻译长度最小比例（Tier1/2 默认）— 原 0.3，放宽为 0.2
        'max_translation_ratio': 3.0,   # 翻译长度最大比例（Tier1/2 默认）
        'tier3_min_ratio': 0.1,         # Tier3（长文本/代码）最小比例
        'tier3_max_ratio': 5.0,         # Tier3（长文本/代码）最大比例
        'short_text_min_length': 30,    # 短文本原文长度阈值
        'short_text_min_absolute': 3,   # 短文本翻译绝对长度下限
        'retry_empty': True,            # 质量问题重试
    }
```

**说明**：0.3 的阈值对章节标题（41 字符）来说，要求翻译至少 12 字符，常因模型返回 "1 原子习惯" 这样的 5-6 字符短翻译而触发。改为 0.2 后，要求 8 字符，更宽松。

- [ ] **步骤 3.2：验证配置生效**

```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -c "from ebook_translator.config import TRANSLATION_OPTIMIZATION; print(TRANSLATION_OPTIMIZATION['quality_check']['min_translation_ratio'])"
```

预期输出：`0.2`

### 任务 4：清理临时调试脚本

**文件：**
- 删除：`d:\project\bookfile_bat\inspect_epub.py`
- 删除：`d:\project\bookfile_bat\analyze_epub.py`
- 删除：`d:\project\bookfile_bat\visual_inspect.py`
- 删除：`d:\project\bookfile_bat\visual_inspect2.py`
- 删除：`d:\project\bookfile_bat\smoke_test.py`
- 删除：`d:\project\bookfile_bat\epub_inspect_tmp\` 目录
- 删除：`d:\project\bookfile_bat\epub_src_tmp\` 目录
- 删除：`d:\project\bookfile_bat\inspect_output.txt`
- 删除：`d:\project\bookfile_bat\analyze_output.txt`
- 删除：`d:\project\bookfile_bat\visual_output.txt`
- 删除：`d:\project\bookfile_bat\visual2.txt`
- 删除：`d:\project\bookfile_bat\smoke_out.txt`
- 删除：`d:\project\bookfile_bat\before_fix.txt`

- [ ] **步骤 4.1：删除所有调试文件**

```powershell
Remove-Item d:\project\bookfile_bat\inspect_epub.py, d:\project\bookfile_bat\analyze_epub.py, d:\project\bookfile_bat\visual_inspect.py, d:\project\bookfile_bat\visual_inspect2.py, d:\project\bookfile_bat\smoke_test.py -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force d:\project\bookfile_bat\epub_inspect_tmp, d:\project\bookfile_bat\epub_src_tmp -ErrorAction SilentlyContinue
Remove-Item d:\project\bookfile_bat\inspect_output.txt, d:\project\bookfile_bat\analyze_output.txt, d:\project\bookfile_bat\visual_output.txt, d:\project\bookfile_bat\visual2.txt, d:\project\bookfile_bat\smoke_out.txt, d:\project\bookfile_bat\before_fix.txt -ErrorAction SilentlyContinue
```

### 任务 5：重新生成 EPUB 验证

- [ ] **步骤 5.1：重新处理 Atomic Habits 验证修复效果**

```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -m automation.main auto
```

预期：
- 终端显示翻译进度（`翻译进度: x/y (z%)`）
- 无 `XMLParsedAsHTMLWarning` 警告
- 重新生成的中文 EPUB 中，"未翻译段数"显著减少

- [ ] **步骤 5.2：使用统计脚本对比验证（可选用完删）**

写入临时验证脚本：

```python
# d:\project\bookfile_bat\verify_fix.py
import re
import zipfile
import sys
import io
import tempfile
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

epub_path = "D:/project/bookfile_bat/output/Atomic Habits_ Tiny Changes, Remarkable Results/中文-Atomic Habits/中文-Atomic Habits.epub"

# 解压
tmpdir = Path(tempfile.mkdtemp())
with zipfile.ZipFile(epub_path) as z:
    z.extractall(tmpdir)

p_pattern = re.compile(r'<p[^>]*data-original="([^"]+)"[^>]*>([^<]+)</p>')
total, untranslated = 0, []
for f in tmpdir.glob("index_split_*.html"):
    content = f.read_text(encoding="utf-8")
    for m in p_pattern.finditer(content):
        orig, cur = m.groups()
        total += 1
        if orig.strip() == cur.strip():
            untranslated.append(orig[:80])

print(f"总段数: {total}")
print(f"未翻译段数: {len(untranslated)}")
print(f"未翻译比例: {len(untranslated)/total*100:.1f}%")
```

运行：
```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" d:\project\bookfile_bat\verify_fix.py
```

预期：未翻译段数应 < 500（原 2984），主要剩章节标题的英文（这些通常是不需要翻译的版权/版式信息）。

- [ ] **步骤 5.3：删除验证脚本**

```powershell
Remove-Item d:\project\bookfile_bat\verify_fix.py
```

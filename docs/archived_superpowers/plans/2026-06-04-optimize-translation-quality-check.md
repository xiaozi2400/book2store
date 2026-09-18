# 翻译质量检查优化 —— 最小改动实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 消除空翻译/翻译过短导致的不必要重试，减少 API 调用次数，降低终端噪音，总体翻译时间减少 30%+

**架构：** 修改 `_quality_check` 方法：空翻译和翻译过短不重试（直接保留原文），仅对有意义的长文本质量问题进行重试。同时将质量问题的日志级别从 WARNING 降为 INFO。

**技术栈：** Python, Calibre EPUB 翻译管线

**测试方式：** 直接使用真实 EPUB 文件运行翻译，对比优化前后的重试次数和翻译时间。

---

### 任务 1：修改 `_quality_check` —— 空翻译/翻译过短不重试

**文件：**
- 修改：`d:\project\bookfile_bat\ebook_translator\translator\translator.py:479-550`

- [ ] **步骤 1.1：理解当前逻辑**

当前 `_quality_check` 在发现质量问题后，**统一执行重试**：
```python
if issues:
    logger.warning(f"  质量问题 ({', '.join(issues)}): {original[:50]}...")
    logger.info(f"  尝试重译...")
    self.stats['retried'] += 1
    retry_result = self.translate(original, max_retries=2)
    ...
```

问题：空翻译和翻译过短的重试大概率还是空/短，白花 API 调用时间。

- [ ] **步骤 1.2：修改 `_quality_check`，空翻译保留原文**

在 `_quality_check` 方法中，检测到空翻译时，**不重试**，直接将原文作为翻译结果返回：

```python
        if not translated or not translated.strip():
            issues.append("空翻译")
            # 空翻译不重试，保留原文
            logger.info(f"  空翻译，保留原文: {original[:50]}...")
            result['translated'] = original
            self.stats['failed'] += 1
            return result
```

- [ ] **步骤 1.3：修改 `_quality_check`，翻译过短保留原文**

在短文本检测逻辑中，如果判定为翻译过短，**不重试**，直接保留原文：

```python
        if orig_len > 0:
            ratio = trans_len / orig_len

            if orig_len <= short_threshold:
                min_absolute = self.opt_config['quality_check'].get('short_text_min_absolute', 3)
                if trans_len < min_absolute:
                    issues.append(f"翻译过短 (绝对长度 {trans_len} < {min_absolute})")
                    # 过短翻译不重试，保留原文
                    logger.info(f"  翻译过短，保留原文: {original[:50]}...")
                    result['translated'] = original
                    self.stats['failed'] += 1
                    return result
```

- [ ] **步骤 1.4：将质量问题的日志级别从 WARNING 降为 INFO**

修改重试相关的日志输出：

```python
if issues:
    logger.info(f"  质量问题 ({', '.join(issues)}): {original[:50]}...")
    # 仅在非空、非过短时重试
    ...
```

- [ ] **步骤 1.5：调整重试条件，仅对有意义的长文本重试**

重试仅对满足以下条件的文本执行：
1. 有质量问题
2. 非空翻译
3. 非过短翻译
4. 原文长度 > 50 字符

```python
        if issues:
            # 空翻译和过短翻译已提前返回，此处只处理比例异常
            logger.info(f"  质量问题 ({', '.join(issues)}): {original[:50]}...")
            
            # 仅对长文本重试（> 50 字符）
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
```

### 任务 2：运行验证

- [ ] **步骤 2.1：运行翻译处理，验证重试次数减少**

用一本之前处理慢的书测试：

```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -m automation.main process <book_id>
```

预期：终端不再看到大量 `质量问题 (空翻译)` 的 WARNING 日志，翻译时间显著减少。

- [ ] **步骤 2.2：检查翻译质量**

打开生成的 EPUB 文件，确认原本会触发空翻译/过短翻译的段落保留了原文，而非被截断或空白。

- [ ] **步骤 2.3：对比优化前后的统计指标**

观察 `print_translation_report` 输出中的 `重试次数` 和 `失败次数`：
- 优化前：重试 ≈ 段落数的 20-30%
- 优化后：重试 ≈ 段落数的 5% 以下（仅对长文本比例异常重试）


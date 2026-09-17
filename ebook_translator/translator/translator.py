import os
import sys
import requests
import time
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    TRANSLATION_PROVIDER,
    DEEPSEEK_API_KEY, DEEPSEEK_API_URL,
    MINIMAX_API_KEY, MINIMAX_API_URL,
    DEEPSEEK_MODEL, MINIMAX_MODEL,
    MAX_TOKENS, TEMPERATURE,
    TIER_CONFIG, TRANSLATION_OPTIMIZATION
)

PROVIDER_CONFIG = {
    "deepseek": {
        "api_key": DEEPSEEK_API_KEY,
        "api_url": DEEPSEEK_API_URL,
        "model": DEEPSEEK_MODEL,
    },
    "minimax": {
        "api_key": MINIMAX_API_KEY,
        "api_url": MINIMAX_API_URL,
        "model": MINIMAX_MODEL,
    }
}

class Translator:
    """通用翻译器 - 支持多种AI提供商"""

    def __init__(self, provider: str = None):
        """初始化翻译器

        Args:
            provider: AI提供商，可选 "deepseek" 或 "minimax"，默认从配置读取
        """
        self.provider = provider or TRANSLATION_PROVIDER

        if self.provider not in PROVIDER_CONFIG:
            raise ValueError(f"不支持的翻译提供商: {self.provider}")

        config = PROVIDER_CONFIG[self.provider]
        self.api_key = config["api_key"]
        self.api_url = config["api_url"]
        self.model = config["model"]
        self.max_tokens = MAX_TOKENS
        self.temperature = TEMPERATURE

        if not self.api_key:
            logger.warning(f"未设置 {self.provider.upper()} API 密钥")

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        self.session = requests.Session()
        self.session.headers.update(self.headers)

        self.stats = {
            "api_calls": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cache_hits": 0,
            "translated_paragraphs": 0,
            "retried": 0,
            "failed": 0,
            "by_tier": {"tier1_short_repeatable": 0, "tier2_normal": 0, "tier3_long_complex": 0}
        }

        self.opt_config = TRANSLATION_OPTIMIZATION

    def translate(self, text, max_retries=3, max_tokens=None):
        """翻译单个文本"""
        if not text:
            return ""

        effective_max_tokens = max_tokens if max_tokens else self.max_tokens
        retry_count = 0

        while retry_count < max_retries:
            if getattr(sys, 'interrupted', False) or (os.environ.get('INTERRUPTED') == '1'):
                logger.info("翻译被中断")
                return ""

            try:
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是科技领域专业译者，擅长AI、软件开发、创业和投资，负责将英文文本翻译成中文，保持翻译准确、流畅，符合中文表达习惯。要求：1、只将给定内容从英语翻译成中文，不要解释任何术语或回答任何类似问题的内容。2、你的答案应该仅仅是给定内容的翻译。在你的答案中，不要给翻译内容添加任何前缀或后缀。3、代码/命令行/配置文件/网站的URL地址等，应保持原样保留在翻译输出中。4、不要遗漏内容的任何部分，即使它看起来不重要。"
                        },
                        {
                            "role": "user",
                            "content": f"请将以下英文文本翻译成中文：\n{text}"
                        }
                    ],
                    "max_tokens": effective_max_tokens,
                    "temperature": self.temperature
                }

                response = self.session.post(self.api_url, json=payload, timeout=120)
                response.raise_for_status()

                self.stats["api_calls"] += 1
                result = response.json()

                choices = result.get("choices")
                if choices and len(choices) > 0:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        usage = result.get("usage", {})
                        self.stats["prompt_tokens"] += usage.get("prompt_tokens", 0)
                        self.stats["completion_tokens"] += usage.get("completion_tokens", 0)
                        self.stats["total_tokens"] += usage.get("total_tokens", 0)
                        return content.strip()
                logger.warning(f"translate() API 返回异常或内容为空: {str(result)[:200]}")

            except requests.exceptions.Timeout:
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)
                    time.sleep(wait_time)
            except Exception as e:
                retry_count += 1
                logger.warning(f"AI调用失败 (重试 {retry_count}/{max_retries}): {type(e).__name__}: {str(e)[:200]}")
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)
                    time.sleep(wait_time)

        return ""

    def chat(self, prompt: str, max_retries: int = 3, max_tokens: int = None) -> str:
        """通用对话方法"""
        if not prompt:
            return ""

        effective_max_tokens = max_tokens if max_tokens else self.max_tokens
        retry_count = 0

        while retry_count < max_retries:
            try:
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": effective_max_tokens,
                    "temperature": self.temperature
                }

                response = self.session.post(self.api_url, json=payload, timeout=120)
                response.raise_for_status()

                self.stats["api_calls"] += 1
                result = response.json()

                choices = result.get("choices")
                if choices and len(choices) > 0:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        usage = result.get("usage", {})
                        self.stats["prompt_tokens"] += usage.get("prompt_tokens", 0)
                        self.stats["completion_tokens"] += usage.get("completion_tokens", 0)
                        self.stats["total_tokens"] += usage.get("total_tokens", 0)
                        return content.strip()
                logger.warning(f"chat() API 返回异常或内容为空: {str(result)[:200]}")

            except Exception as e:
                retry_count += 1
                logger.warning(f"AI chat调用失败 (重试 {retry_count}/{max_retries}): {type(e).__name__}: {str(e)[:200]}")
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)
                    time.sleep(wait_time)

        return ""

    def chat_raw(self, prompt: str, max_retries: int = 3, max_tokens: int = None) -> dict:
        """通用对话，返回完整 API 响应（包含 usage）"""
        if not prompt:
            return {"choices": [{"message": {"content": ""}}], "usage": {}}

        effective_max_tokens = max_tokens if max_tokens else self.max_tokens
        retry_count = 0

        while retry_count < max_retries:
            try:
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": effective_max_tokens,
                    "temperature": self.temperature
                }

                response = self.session.post(self.api_url, json=payload, timeout=120)
                response.raise_for_status()

                self.stats["api_calls"] += 1
                result = response.json()

                usage = result.get("usage", {})
                self.stats["prompt_tokens"] += usage.get("prompt_tokens", 0)
                self.stats["completion_tokens"] += usage.get("completion_tokens", 0)
                self.stats["total_tokens"] += usage.get("total_tokens", 0)

                return result

            except Exception as e:
                retry_count += 1
                logger.warning(f"AI chat_raw 调用失败 (重试 {retry_count}/{max_retries}): {type(e).__name__}: {str(e)[:200]}")
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)
                    time.sleep(wait_time)

        return {"choices": [{"message": {"content": ""}}], "usage": {}}

    def translate_batch(self, paragraphs, tier):
        """批量翻译"""
        if not paragraphs:
            return []

        tier_config = TIER_CONFIG.get(tier, {})
        if not tier_config.get('batch_translate', True):
            return self._translate_individually(paragraphs)

        logger.info(f"批量翻译 {len(paragraphs)} 个 {tier} 段落")

        numbered_texts = []
        for i, para in enumerate(paragraphs):
            numbered_texts.append(f"[{i+1}] {para['text']}")

        combined = "\n\n".join(numbered_texts)

        estimated_tokens = len(combined) * 2 + 500
        dynamic_max_tokens = min(estimated_tokens, 4000)

        prompt = f"""请将以下编号段落翻译成中文，保持编号格式：

{combined}

要求：
1. 保留每段开头的编号 [数字]
2. 只返回翻译结果，不要解释
3. 保持段落顺序"""

        translated = self.translate(prompt, max_retries=5, max_tokens=dynamic_max_tokens)

        if not translated:
            logger.warning("批量翻译失败，转为单条翻译")
            return self._translate_individually(paragraphs)

        results = self._parse_batch_result(translated, paragraphs)

        if len(results) != len(paragraphs):
            logger.warning(f"批量解析失败（期望{len(paragraphs)}，实际{len(results)}），转为单条")
            return self._translate_individually(paragraphs)

        return results

    def _parse_batch_result(self, translated, original_paragraphs):
        """解析批量翻译结果"""
        results = []

        pattern = r'\[(\d+)\]\s*'
        parts = re.split(pattern, translated)

        if len(parts) > 1:
            translations = {}
            for i in range(1, len(parts), 2):
                if i < len(parts):
                    try:
                        idx = int(parts[i]) - 1
                        text = parts[i+1].strip() if i+1 < len(parts) else ""
                        translations[idx] = text
                    except:
                        pass

            for i, para in enumerate(original_paragraphs):
                translated_text = translations.get(i, "")
                results.append({
                    'id': para['id'],
                    'trans_id': para.get('trans_id'),
                    'original': para['text'],
                    'translated': translated_text,
                    'html': para['html'],
                    'tier': para.get('tier', 'unknown')
                })

        return results

    def _translate_individually(self, paragraphs):
        """单独翻译每个段落"""
        results = []
        for para in paragraphs:
            translated = self.translate(para['text'])
            results.append({
                'id': para['id'],
                'trans_id': para.get('trans_id'),
                'original': para['text'],
                'translated': translated,
                'html': para['html'],
                'tier': para.get('tier', 'unknown')
            })
        return results

    def translate_smart(self, paragraphs):
        """智能分层翻译 - 核心方法"""
        if not paragraphs:
            return []

        logger.info(f"开始智能分层翻译，共 {len(paragraphs)} 个段落")

        tier_groups = {
            'tier1_short_repeatable': [],
            'tier2_normal': [],
            'tier3_long_complex': []
        }

        duplicates = []

        for para in paragraphs:
            tier = para.get('tier', 'tier2_normal')

            if para.get('is_duplicate') and para.get('original_id'):
                duplicates.append(para)
            else:
                tier_groups[tier].append(para)

        all_results = {}

        batch_config = self.opt_config['batch']

        total_paragraphs = len(tier_groups['tier1_short_repeatable']) + \
                          len(tier_groups['tier2_normal']) + \
                          len(tier_groups['tier3_long_complex'])

        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeRemainingColumn(),
            console=Console(stderr=True),
        ) as progress:
            task = progress.add_task(f"翻译 ({total_paragraphs} 段落)", total=total_paragraphs)

            if tier_groups['tier1_short_repeatable']:
                logger.info(f"[Tier 1] 翻译 {len(tier_groups['tier1_short_repeatable'])} 个短文本...")
                tier1_results = self._translate_tier(
                    tier_groups['tier1_short_repeatable'],
                    'tier1_short_repeatable',
                    batch_config['tier1_batch_size'],
                    progress,
                    task
                )
                all_results.update(tier1_results)

            if tier_groups['tier2_normal']:
                logger.info(f"[Tier 2] 翻译 {len(tier_groups['tier2_normal'])} 个普通文本...")
                tier2_results = self._translate_tier(
                    tier_groups['tier2_normal'],
                    'tier2_normal',
                    batch_config['tier2_batch_size'],
                    progress,
                    task
                )
                all_results.update(tier2_results)

            if tier_groups['tier3_long_complex']:
                logger.info(f"[Tier 3] 翻译 {len(tier_groups['tier3_long_complex'])} 个长文本...")
                tier3_results = self._translate_tier(
                    tier_groups['tier3_long_complex'],
                    'tier3_long_complex',
                    1,
                    progress,
                    task
                )
                all_results.update(tier3_results)

        for dup in duplicates:
            original_id = dup.get('original_id')
            if original_id in all_results:
                dup_result = all_results[original_id].copy()
                dup_result['id'] = dup['id']
                dup_result['is_duplicate'] = True
                all_results[dup['id']] = dup_result
                logger.info(f"  复用翻译: {dup['text'][:30]}...")

        ordered_results = []
        for para in paragraphs:
            if para['id'] in all_results:
                ordered_results.append(all_results[para['id']])

        logger.info(f"翻译完成: {len(ordered_results)}/{len(paragraphs)}")
        return ordered_results

    def _split_batches_by_chars(self, paragraphs, max_chars=1800):
        """按字符数切分批次（类似 Calibre 插件策略）"""
        batches = []
        current_batch = []
        current_chars = 0
        
        for para in paragraphs:
            para_chars = len(para['text'])
            
            # 如果当前批次已不为空，且加上这个段落会超过限制，则创建新批次
            if current_batch and (current_chars + para_chars > max_chars):
                batches.append(current_batch)
                current_batch = []
                current_chars = 0
            
            current_batch.append(para)
            current_chars += para_chars
        
        # 添加最后一个批次
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _translate_tier(self, paragraphs, tier, batch_size, progress=None, task=None):
        """翻译指定 tier 的段落"""
        if not paragraphs:
            return {}

        results = {}
        
        # 根据配置选择批次切分策略
        if self.opt_config['batch'].get('use_char_based_batching', False):
            max_chars = self.opt_config['batch'].get('max_chars_per_batch', 1800)
            batches = self._split_batches_by_chars(paragraphs, max_chars)
            logger.info(f"  [{tier}] 按字符数策略切分: {len(batches)} 批次 (最大 {max_chars} 字符/批次)")
        else:
            batches = [paragraphs[i:i+batch_size] for i in range(0, len(paragraphs), batch_size)]
            logger.info(f"  [{tier}] 按段落数策略切分: {len(batches)} 批次 ({batch_size} 段落/批次)")

        max_workers = self.opt_config['batch']['max_workers']

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_batch = {
                executor.submit(self.translate_batch, batch, tier): batch
                for batch in batches
            }

            completed = 0
            for future in as_completed(future_to_batch):
                batch = future_to_batch[future]
                try:
                    batch_results = future.result(timeout=180)
                    for result in batch_results:
                        if self.opt_config['quality_check']['enabled']:
                            result = self._quality_check(result, tier)

                        results[result['id']] = result
                        self.stats['translated_paragraphs'] += 1
                        self.stats['by_tier'][tier] += 1

                    completed += len(batch)
                    if progress and task is not None:
                        progress.update(task, completed=completed)
                    logger.info(f"  进度: {completed}/{len(paragraphs)}")

                except Exception as e:
                    logger.warning(f"  批次翻译出错: {e}")
                    for para in batch:
                        result = self._translate_single_with_retry(para)
                        results[result['id']] = result
                        if progress and task is not None:
                            progress.update(task, advance=1)

        return results

    def _translate_single_with_retry(self, para):
        """翻译单个段落（带质量检查和重试）"""
        text = para['text']
        translated = self.translate(text)

        result = {
            'id': para['id'],
            'original': text,
            'translated': translated,
            'html': para['html'],
            'tier': para.get('tier', 'unknown')
        }

        if self.opt_config['quality_check']['enabled']:
            result = self._quality_check(result, result.get('tier', 'tier2_normal'))

        self.stats['translated_paragraphs'] += 1
        return result

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

    def get_stats(self):
        """获取统计信息"""
        return self.stats

    def print_translation_report(self):
        """打印翻译报告"""
        logger.info(f"=== {self.provider.upper()} 翻译统计报告 ===")
        logger.info(f"API 调用次数: {self.stats['api_calls']}")
        logger.info(f"总 Token 消耗: {self.stats['total_tokens']}")
        logger.info(f"翻译段落数: {self.stats['translated_paragraphs']}")
        logger.info(f"重试次数: {self.stats['retried']}")
        logger.info(f"失败次数: {self.stats['failed']}")
        logger.info(f"分层统计:")
        for tier, count in self.stats['by_tier'].items():
            tier_name = {
                'tier1_short_repeatable': '短文本(可重复)',
                'tier2_normal': '普通文本',
                'tier3_long_complex': '长文本(复杂)'
            }.get(tier, tier)
            logger.info(f"  {tier_name}: {count}")
        logger.info("====================")

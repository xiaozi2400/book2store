import os
import sys
import requests
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_API_URL, 
    TRANSLATION_MODEL, MAX_TOKENS, TEMPERATURE,
    TIER_CONFIG, TRANSLATION_OPTIMIZATION
)

class DeepSeekTranslator:
    """DeepSeek API 翻译器 - 智能分层版本"""
    
    def __init__(self):
        """初始化翻译器"""
        self.api_key = DEEPSEEK_API_KEY
        self.api_url = DEEPSEEK_API_URL
        self.model = TRANSLATION_MODEL
        self.max_tokens = MAX_TOKENS
        self.temperature = TEMPERATURE
        
        if not self.api_key:
            print("错误：未设置 DeepSeek API 密钥")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        self.stats = {
            "api_calls": 0,
            "total_tokens": 0,
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
                print("翻译被中断")
                return ""
            
            try:
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是一个专业的翻译助手，将英文文本翻译成中文。保持翻译准确、流畅，符合中文表达习惯。"
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
                translated_text = result["choices"][0]["message"]["content"]
                
                if "usage" in result:
                    self.stats["total_tokens"] += result["usage"].get("total_tokens", 0)
                
                return translated_text.strip()
                
            except requests.exceptions.Timeout:
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)
                    time.sleep(wait_time)
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)
                    time.sleep(wait_time)
        
        return ""
    
    def translate_batch(self, paragraphs, tier):
        """批量翻译 - 简化可靠版本"""
        if not paragraphs:
            return []
        
        tier_config = TIER_CONFIG.get(tier, {})
        if not tier_config.get('batch_translate', True):
            # 该层不批量翻译，转为单条
            return self._translate_individually(paragraphs)
        
        print(f"批量翻译 {len(paragraphs)} 个 {tier} 段落")
        
        # 构建批量请求
        numbered_texts = []
        for i, para in enumerate(paragraphs):
            numbered_texts.append(f"[{i+1}] {para['text']}")
        
        combined = "\n\n".join(numbered_texts)
        
        # 估算所需 tokens
        estimated_tokens = len(combined) * 2 + 500  # 文本 + 系统提示
        dynamic_max_tokens = min(estimated_tokens, 4000)
        
        prompt = f"""请将以下编号段落翻译成中文，保持编号格式：

{combined}

要求：
1. 保留每段开头的编号 [数字]
2. 只返回翻译结果，不要解释
3. 保持段落顺序"""
        
        translated = self.translate(prompt, max_retries=5, max_tokens=dynamic_max_tokens)
        
        if not translated:
            print(f"批量翻译失败，转为单条翻译")
            return self._translate_individually(paragraphs)
        
        # 解析结果
        results = self._parse_batch_result(translated, paragraphs)
        
        if len(results) != len(paragraphs):
            print(f"批量解析失败（期望{len(paragraphs)}，实际{len(results)}），转为单条")
            return self._translate_individually(paragraphs)
        
        return results
    
    def _parse_batch_result(self, translated, original_paragraphs):
        """解析批量翻译结果"""
        results = []
        
        # 尝试按编号分割
        pattern = r'\[(\d+)\]\s*'
        parts = re.split(pattern, translated)
        
        # parts 格式: ['', '1', '翻译1', '2', '翻译2', ...]
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
        
        print(f"\n开始智能分层翻译，共 {len(paragraphs)} 个段落")
        
        # 按 tier 分组
        tier_groups = {
            'tier1_short_repeatable': [],
            'tier2_normal': [],
            'tier3_long_complex': []
        }
        
        duplicates = []  # 需要去重的段落
        
        for para in paragraphs:
            tier = para.get('tier', 'tier2_normal')
            
            if para.get('is_duplicate') and para.get('original_id'):
                duplicates.append(para)
            else:
                tier_groups[tier].append(para)
        
        all_results = {}
        
        # 翻译各层
        batch_config = self.opt_config['batch']
        
        # Tier 1: 短文本，大批量
        if tier_groups['tier1_short_repeatable']:
            print(f"\n[Tier 1] 翻译 {len(tier_groups['tier1_short_repeatable'])} 个短文本...")
            tier1_results = self._translate_tier(
                tier_groups['tier1_short_repeatable'],
                'tier1_short_repeatable',
                batch_config['tier1_batch_size']
            )
            all_results.update(tier1_results)
        
        # Tier 2: 普通文本，中批量
        if tier_groups['tier2_normal']:
            print(f"\n[Tier 2] 翻译 {len(tier_groups['tier2_normal'])} 个普通文本...")
            tier2_results = self._translate_tier(
                tier_groups['tier2_normal'],
                'tier2_normal',
                batch_config['tier2_batch_size']
            )
            all_results.update(tier2_results)
        
        # Tier 3: 长文本，单独翻译
        if tier_groups['tier3_long_complex']:
            print(f"\n[Tier 3] 翻译 {len(tier_groups['tier3_long_complex'])} 个长文本...")
            tier3_results = self._translate_tier(
                tier_groups['tier3_long_complex'],
                'tier3_long_complex',
                1  # 单独翻译
            )
            all_results.update(tier3_results)
        
        # 处理重复段落（复用翻译结果）
        for dup in duplicates:
            original_id = dup.get('original_id')
            if original_id in all_results:
                dup_result = all_results[original_id].copy()
                dup_result['id'] = dup['id']
                dup_result['is_duplicate'] = True
                all_results[dup['id']] = dup_result
                print(f"  复用翻译: {dup['text'][:30]}...")
        
        # 按原始顺序返回
        ordered_results = []
        for para in paragraphs:
            if para['id'] in all_results:
                ordered_results.append(all_results[para['id']])
        
        print(f"\n翻译完成: {len(ordered_results)}/{len(paragraphs)}")
        return ordered_results
    
    def _translate_tier(self, paragraphs, tier, batch_size):
        """翻译指定 tier 的段落"""
        if not paragraphs:
            return {}
        
        results = {}
        
        # 分批处理
        batches = [paragraphs[i:i+batch_size] for i in range(0, len(paragraphs), batch_size)]
        
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
                        # 质量检查
                        if self.opt_config['quality_check']['enabled']:
                            result = self._quality_check(result)
                        
                        results[result['id']] = result
                        self.stats['translated_paragraphs'] += 1
                        self.stats['by_tier'][tier] += 1
                    
                    completed += len(batch)
                    progress = completed / len(paragraphs) * 100
                    print(f"  进度: {completed}/{len(paragraphs)} ({progress:.1f}%)")
                    
                except Exception as e:
                    print(f"  批次翻译出错: {e}")
                    # 失败时单独翻译
                    for para in batch:
                        result = self._translate_single_with_retry(para)
                        results[result['id']] = result
        
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
        
        # 质量检查
        if self.opt_config['quality_check']['enabled']:
            result = self._quality_check(result)
        
        self.stats['translated_paragraphs'] += 1
        return result
    
    def _quality_check(self, result):
        """质量检查"""
        original = result['original']
        translated = result['translated']
        
        issues = []
        
        # 检查空翻译
        if not translated or not translated.strip():
            issues.append("空翻译")
        
        # 检查长度异常
        orig_len = len(original)
        trans_len = len(translated)
        
        if orig_len > 0:
            ratio = trans_len / orig_len
            min_ratio = self.opt_config['quality_check']['min_translation_ratio']
            max_ratio = self.opt_config['quality_check']['max_translation_ratio']
            
            if ratio < min_ratio:
                issues.append(f"翻译过短 ({ratio:.2f})")
            if ratio > max_ratio:
                issues.append(f"翻译过长 ({ratio:.2f})")
        
        # 检查分隔符残留
        if '===' in translated or '[段落' in translated:
            issues.append("分隔符残留")
        
        # 有问题则重试
        if issues and self.opt_config['quality_check']['retry_empty']:
            print(f"  质量问题 ({', '.join(issues)}): {original[:50]}...")
            print(f"  尝试重译...")
            
            self.stats['retried'] += 1
            retry_result = self.translate(original, max_retries=2)
            
            if retry_result and len(retry_result) > len(translated) * 0.5:
                result['translated'] = retry_result
                print(f"  重译成功")
            else:
                print(f"  重译失败，保留原结果")
                self.stats['failed'] += 1
        
        return result
    
    def get_stats(self):
        """获取统计信息"""
        return self.stats
    
    def print_translation_report(self):
        """打印翻译报告"""
        print("\n=== 翻译统计报告 ===")
        print(f"API 调用次数: {self.stats['api_calls']}")
        print(f"总 Token 消耗: {self.stats['total_tokens']}")
        print(f"翻译段落数: {self.stats['translated_paragraphs']}")
        print(f"重试次数: {self.stats['retried']}")
        print(f"失败次数: {self.stats['failed']}")
        print(f"\n分层统计:")
        for tier, count in self.stats['by_tier'].items():
            tier_name = {
                'tier1_short_repeatable': '短文本(可重复)',
                'tier2_normal': '普通文本',
                'tier3_long_complex': '长文本(复杂)'
            }.get(tier, tier)
            print(f"  {tier_name}: {count}")
        print("====================\n")

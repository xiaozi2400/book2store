import os
import sys
import requests
import time
import re
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor, as_completed

class DeepSeekTranslator:
    """DeepSeek API 翻译器"""
    
    def __init__(self):
        """初始化翻译器"""
        # 动态导入配置，确保获取最新的 API 密钥
        from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, TRANSLATION_MODEL, MAX_TOKENS, TEMPERATURE
        
        self.api_key = DEEPSEEK_API_KEY
        self.api_url = DEEPSEEK_API_URL
        self.model = TRANSLATION_MODEL
        self.max_tokens = MAX_TOKENS
        self.temperature = TEMPERATURE
        
        # 检查 API 密钥是否设置
        if not self.api_key:
            print("错误：未设置 DeepSeek API 密钥")
            print("请设置环境变量 DEEPSEEK_API_KEY 或使用 --api-key 参数")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 添加会话保持
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # 监控统计
        self.stats = {
            "api_calls": 0,
            "total_tokens": 0,
            "cache_hits": 0,
            "translated_paragraphs": 0
        }
    
    def translate(self, text, max_retries=3, max_tokens=None):
        """翻译文本"""
        if not text:
            return ""
        
        # 使用动态的 max_tokens 或默认的 self.max_tokens
        effective_max_tokens = max_tokens if max_tokens else self.max_tokens
        
        retry_count = 0
        while retry_count < max_retries:
            # 检查是否收到中断信号
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
                
                # 使用会话发送请求，增加超时时间
                # 批量翻译可能需要更长时间，使用更长的超时
                response = self.session.post(self.api_url, json=payload, timeout=120)  # 增加到 120 秒
                response.raise_for_status()
                
                # 增加 API 调用计数
                self.stats["api_calls"] += 1
                
                result = response.json()
                translated_text = result["choices"][0]["message"]["content"]
                
                # 统计 token 消耗
                if "usage" in result:
                    self.stats["total_tokens"] += result["usage"].get("total_tokens", 0)
                
                return translated_text.strip()
                
            except requests.exceptions.Timeout as e:
                print(f"API 请求超时: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)  # 最大等待30秒
                    print(f"请求超时，等待 {wait_time} 秒后重试... ({retry_count}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print("达到最大重试次数，翻译失败")
                    return ""
            except requests.exceptions.ConnectionError as e:
                print(f"API 连接错误: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)
                    print(f"连接错误，等待 {wait_time} 秒后重试... ({retry_count}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print("达到最大重试次数，翻译失败")
                    return ""
            except requests.exceptions.RequestException as e:
                print(f"API 请求出错: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)
                    print(f"请求错误，等待 {wait_time} 秒后重试... ({retry_count}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print("达到最大重试次数，翻译失败")
                    return ""
            except Exception as e:
                print(f"翻译过程出错: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)
                    print(f"发生错误，等待 {wait_time} 秒后重试... ({retry_count}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print("达到最大重试次数，翻译失败")
                    return ""
    
    def translate_batch(self, paragraphs):
        """批量翻译多个段落"""
        if not paragraphs:
            return []
        
        print(f"开始批量翻译 {len(paragraphs)} 个段落")
        
        # 使用更独特的分割符，避免在翻译结果中出现
        separator = "\n===DEEPSEEK_BATCH_SEPARATOR===-" 
        
        # 构建批量翻译请求
        batch_texts = []
        for i, para in enumerate(paragraphs):
            # 为每个段落添加编号，确保分割准确
            batch_texts.append(f"[段落 {i+1}]\n{para['text']}")
        
        combined_text = separator.join(batch_texts)
        
        # 根据段落数量动态调整 max_tokens
        # 每个中文段落大约需要英文段落的 1.5-2 倍 token
        estimated_tokens = len(combined_text) * 2
        dynamic_max_tokens = max(self.max_tokens, min(estimated_tokens, 4000))
        
        # 构建更明确的翻译提示
        prompt = f"""请将以下英文段落翻译成中文，保持段落顺序和编号：

{combined_text}

翻译要求：
1. 保持每个段落的独立性
2. 保留段落编号 [段落 X]
3. 不要添加额外的解释或说明
4. 保持翻译准确、流畅"""
        
        # 翻译组合文本，使用动态的 max_tokens
        translated_combined = self.translate(prompt, max_retries=5)
        
        translated_results = []
        if translated_combined:
            print(f"批量翻译成功，结果长度: {len(translated_combined)} 字符")
            
            # 尝试多种方式分割翻译结果
            # 方式1：按段落编号分割（支持多种格式）
            translated_parts = re.split(r'\[段落\s*\d+\]\s*\n?', translated_combined)
            translated_parts = [part.strip().replace('===DEEPSEEK_BATCH_SEPARATOR===', '').strip() for part in translated_parts if part.strip()]
            
            # 方式2：如果方式1失败，尝试按原始分隔符分割
            if len(translated_parts) != len(paragraphs):
                print(f"方式1分割失败，尝试方式2...")
                translated_parts = translated_combined.split('===DEEPSEEK_BATCH_SEPARATOR===-')
                translated_parts = [part.strip() for part in translated_parts if part.strip()]
                # 移除段落编号
                translated_parts = [re.sub(r'^\[段落\s*\d+\]\s*\n?', '', part).strip() for part in translated_parts]
            
            # 方式3：如果还是失败，尝试按换行分割（每行一个段落）
            if len(translated_parts) != len(paragraphs) and len(paragraphs) <= 5:
                print(f"方式2分割失败，尝试方式3...")
                # 清理后按空行分割
                cleaned = re.sub(r'\[段落\s*\d+\]', '', translated_combined)
                cleaned = cleaned.replace('===DEEPSEEK_BATCH_SEPARATOR===-', '\n')
                translated_parts = [p.strip() for p in cleaned.split('\n\n') if p.strip()]
            
            # 确保分割结果数量正确
            if len(translated_parts) == len(paragraphs):
                print(f"分割成功，得到 {len(translated_parts)} 个段落")
                for para, translated_part in zip(paragraphs, translated_parts):
                    translated_results.append({
                        'original': para['text'],
                        'translated': translated_part,
                        'html': para['html']
                    })
            else:
                # 如果分割失败，回退到单独翻译
                print(f"批量翻译分割失败，回退到单独翻译 (期望 {len(paragraphs)} 个段落，实际 {len(translated_parts)} 个)")
                for para in paragraphs:
                    translated = self.translate(para['text'])
                    # 清理分隔符
                    if translated:
                        translated = translated.replace('===DEEPSEEK_BATCH_SEPARATOR===', '').strip()
                    translated_results.append({
                        'original': para['text'],
                        'translated': translated,
                        'html': para['html']
                    })
        else:
            # 如果批量翻译失败，回退到单独翻译
            print("批量翻译失败：未收到翻译结果")
            for para in paragraphs:
                translated = self.translate(para['text'])
                # 清理分隔符
                if translated:
                    translated = translated.replace('===DEEPSEEK_BATCH_SEPARATOR===', '').strip()
                translated_results.append({
                    'original': para['text'],
                    'translated': translated,
                    'html': para['html']
                })
        
        # 增加翻译段落计数
        self.stats["translated_paragraphs"] += len(translated_results)
        
        return translated_results
    
    def translate_optimized(self, paragraphs, batch_size=3, max_workers=3):
        """优化的翻译方法：批量 + 并发"""
        if not paragraphs:
            return []
        
        # 先按 batch_size 分组
        batches = []
        for i in range(0, len(paragraphs), batch_size):
            batch = paragraphs[i:i+batch_size]
            batches.append(batch)
        
        # 并发处理每个批次
        translated_results = []
        executor = ThreadPoolExecutor(max_workers=min(max_workers, len(batches)))
        
        # 进度统计
        total_batches = len(batches)
        completed_batches = 0
        total_paragraphs = len(paragraphs)
        completed_paragraphs = 0
        
        try:
            future_to_batch = {}
            for batch in batches:
                # 检查是否收到中断信号
                if getattr(sys, 'interrupted', False) or (os.environ.get('INTERRUPTED') == '1'):
                    print("翻译被中断")
                    break
                
                future = executor.submit(self.translate_batch, batch)
                future_to_batch[future] = batch
            
            # 处理完成的任务，捕获超时异常
            try:
                for future in as_completed(future_to_batch, timeout=600):  # 增加超时时间到 10 分钟
                    # 检查是否收到中断信号
                    if getattr(sys, 'interrupted', False) or (os.environ.get('INTERRUPTED') == '1'):
                        print("翻译被中断")
                        break
                    
                    try:
                        batch_results = future.result(timeout=120)  # 增加每个任务的超时时间
                        translated_results.extend(batch_results)
                        completed_batches += 1
                        completed_paragraphs += len(batch_results)
                        # 展示进度
                        progress = (completed_paragraphs / total_paragraphs) * 100
                        print(f"翻译进度: {completed_paragraphs}/{total_paragraphs} 段落 ({progress:.1f}%)")
                    except Exception as e:
                        print(f"批量并发翻译出错: {e}")
                        # 出错时回退到单独翻译
                        batch = future_to_batch[future]
                        for para in batch:
                            translated = self.translate(para['text'])
                            translated_results.append({
                                'original': para['text'],
                                'translated': translated,
                                'html': para['html']
                            })
                        completed_batches += 1
                        completed_paragraphs += len(batch)
                        # 展示进度
                        progress = (completed_paragraphs / total_paragraphs) * 100
                        print(f"翻译进度: {completed_paragraphs}/{total_paragraphs} 段落 ({progress:.1f}%)")
            except TimeoutError:
                print("翻译超时，已完成部分段落的翻译")
                # 处理已完成的任务
                for future in future_to_batch:
                    if future.done():
                        try:
                            batch_results = future.result()
                            translated_results.extend(batch_results)
                            completed_paragraphs += len(batch_results)
                        except Exception as e:
                            print(f"处理已完成任务时出错: {e}")
                # 展示最终进度
                progress = (completed_paragraphs / total_paragraphs) * 100
                print(f"翻译进度: {completed_paragraphs}/{total_paragraphs} 段落 ({progress:.1f}%)")
            
        finally:
            # 无论如何都关闭 executor
            print("正在关闭线程池...")
            executor.shutdown(wait=True)  # 等待所有任务完成
    
        # 保持结果顺序
        result_map = {r['original']: r for r in translated_results}
        ordered_results = []
        for para in paragraphs:
            if para['text'] in result_map:
                result = result_map[para['text']]
                # 如果翻译为空，尝试单独翻译
                if not result['translated']:
                    print(f"警告：段落翻译为空，尝试单独翻译: {para['text'][:50]}...")
                    translated = self.translate(para['text'])
                    if translated:
                        translated = translated.replace('===DEEPSEEK_BATCH_SEPARATOR===', '').strip()
                    result = {
                        'original': para['text'],
                        'translated': translated,
                        'html': para['html']
                    }
                ordered_results.append(result)
            else:
                # 如果段落没有翻译结果，尝试单独翻译
                print(f"警告：段落没有翻译结果，尝试单独翻译: {para['text'][:50]}...")
                translated = self.translate(para['text'])
                if translated:
                    translated = translated.replace('===DEEPSEEK_BATCH_SEPARATOR===', '').strip()
                ordered_results.append({
                    'original': para['text'],
                    'translated': translated,
                    'html': para['html']
                })
        
        return ordered_results
    
    async def translate_async(self, text, max_retries=3, max_tokens=None):
        """异步翻译文本"""
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
                
                timeout = aiohttp.ClientTimeout(total=180, connect=60, sock_read=150)
                connector = aiohttp.TCPConnector(limit=3, ttl_dns_cache=300, force_close=False)
                async with aiohttp.ClientSession(headers=self.headers, timeout=timeout, connector=connector) as session:
                    async with session.post(self.api_url, json=payload) as response:
                        response.raise_for_status()
                        self.stats["api_calls"] += 1
                        result = await response.json()
                        translated_text = result["choices"][0]["message"]["content"]
                        
                        if "usage" in result:
                            self.stats["total_tokens"] += result["usage"].get("total_tokens", 0)
                        
                        return translated_text.strip()
                        
            except asyncio.TimeoutError:
                print(f"异步API请求超时 (重试 {retry_count + 1}/{max_retries})")
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(3 ** retry_count)  # 更长的等待时间
                else:
                    return ""
            except aiohttp.ClientError as e:
                print(f"异步API客户端错误: {e} (重试 {retry_count + 1}/{max_retries})")
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(3 ** retry_count)
                else:
                    return ""
            except Exception as e:
                print(f"异步API请求出错: {type(e).__name__}: {e} (重试 {retry_count + 1}/{max_retries})")
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(3 ** retry_count)
                else:
                    return ""
    
    async def translate_batch_async(self, paragraphs, max_retries=3):
        """异步批量翻译多个段落"""
        if not paragraphs:
            return []
        
        print(f"开始异步批量翻译 {len(paragraphs)} 个段落")
        
        separator = "\n===DEEPSEEK_BATCH_SEPARATOR===-"
        
        batch_texts = []
        for i, para in enumerate(paragraphs):
            batch_texts.append(f"[段落 {i+1}]\n{para['text']}")
        
        combined_text = separator.join(batch_texts)
        
        estimated_tokens = len(combined_text) * 2
        dynamic_max_tokens = max(self.max_tokens, min(estimated_tokens, 4000))
        
        prompt = f"""请将以下英文段落翻译成中文，保持段落顺序和编号：

{combined_text}

翻译要求：
1. 保持每个段落的独立性
2. 保留段落编号 [段落 X]
3. 不要添加额外的解释或说明
4. 保持翻译准确、流畅"""
        
        translated_combined = await self.translate_async(prompt, max_retries=max_retries, max_tokens=dynamic_max_tokens)
        
        translated_results = []
        if translated_combined:
            print(f"异步批量翻译成功，结果长度: {len(translated_combined)} 字符")
            translated_parts = re.split(r'\[段落 \d+\]\n', translated_combined)
            # 清理分隔符
            translated_parts = [part.strip().replace('===DEEPSEEK_BATCH_SEPARATOR===', '').strip() for part in translated_parts if part.strip()]
            
            if len(translated_parts) == len(paragraphs):
                for para, translated_part in zip(paragraphs, translated_parts):
                    translated_results.append({
                        'original': para['text'],
                        'translated': translated_part,
                        'html': para['html']
                    })
            else:
                print(f"异步批量翻译分割失败，回退到单独翻译")
                tasks = [self.translate_async(para['text'], max_retries=max_retries) for para in paragraphs]
                translations = await asyncio.gather(*tasks, return_exceptions=True)
                for para, translation in zip(paragraphs, translations):
                    if isinstance(translation, Exception):
                        translation = ""
                    else:
                        # 清理分隔符
                        translation = translation.replace('===DEEPSEEK_BATCH_SEPARATOR===', '').strip()
                    translated_results.append({
                        'original': para['text'],
                        'translated': translation,
                        'html': para['html']
                    })
        else:
            print("异步批量翻译失败，回退到单独翻译")
            tasks = [self.translate_async(para['text'], max_retries=max_retries) for para in paragraphs]
            translations = await asyncio.gather(*tasks, return_exceptions=True)
            for para, translation in zip(paragraphs, translations):
                if isinstance(translation, Exception):
                    translation = ""
                else:
                    # 清理分隔符
                    translation = translation.replace('===DEEPSEEK_BATCH_SEPARATOR===', '').strip()
                translated_results.append({
                    'original': para['text'],
                    'translated': translation,
                    'html': para['html']
                })
        
        self.stats["translated_paragraphs"] += len(translated_results)
        return translated_results
    
    async def translate_all_async(self, paragraphs, batch_size=20, max_concurrent=20):
        """异步批量翻译所有段落"""
        if not paragraphs:
            return []
        
        batches = []
        for i in range(0, len(paragraphs), batch_size):
            batch = paragraphs[i:i+batch_size]
            batches.append(batch)
        
        print(f"开始异步翻译 {len(batches)} 个批次，共 {len(paragraphs)} 个段落")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def translate_with_semaphore(batch, batch_idx):
            async with semaphore:
                print(f"异步翻译批次 {batch_idx + 1}/{len(batches)}")
                return await self.translate_batch_async(batch)
        
        tasks = [translate_with_semaphore(batch, idx) for idx, batch in enumerate(batches)]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        translated_results = []
        for result in results:
            if isinstance(result, Exception):
                print(f"批次翻译出错: {result}")
                continue
            translated_results.extend(result)
        
        result_map = {r['original']: r for r in translated_results}
        ordered_results = []
        for para in paragraphs:
            if para['text'] in result_map:
                ordered_results.append(result_map[para['text']])
            else:
                ordered_results.append({
                    'original': para['text'],
                    'translated': "",
                    'html': para['html']
                })
        
        return ordered_results
    
    def translate_optimized_async(self, paragraphs, batch_size=20, max_concurrent=20):
        """优化的异步翻译方法"""
        return asyncio.run(self.translate_all_async(paragraphs, batch_size, max_concurrent))
    
    def get_stats(self):
        """获取翻译统计信息"""
        return self.stats
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            "api_calls": 0,
            "total_tokens": 0,
            "cache_hits": 0,
            "translated_paragraphs": 0
        }

import requests
import time
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, TRANSLATION_MODEL, MAX_TOKENS, TEMPERATURE

class DeepSeekTranslator:
    """DeepSeek API 翻译器"""
    
    def __init__(self):
        """初始化翻译器"""
        self.api_key = DEEPSEEK_API_KEY
        self.api_url = DEEPSEEK_API_URL
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def translate(self, text, max_retries=3):
        """翻译文本"""
        if not text:
            return ""
        
        retry_count = 0
        while retry_count < max_retries:
            try:
                payload = {
                    "model": TRANSLATION_MODEL,
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
                    "max_tokens": MAX_TOKENS,
                    "temperature": TEMPERATURE
                }
                
                response = requests.post(self.api_url, headers=self.headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                translated_text = result["choices"][0]["message"]["content"]
                
                return translated_text.strip()
                
            except requests.exceptions.RequestException as e:
                print(f"API 请求出错: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    print(f"重试中... ({retry_count}/{max_retries})")
                    time.sleep(2 ** retry_count)  # 指数退避
                else:
                    print("达到最大重试次数，翻译失败")
                    return ""
            except Exception as e:
                print(f"翻译过程出错: {e}")
                return ""
    
    def translate_paragraphs(self, paragraphs):
        """翻译多个段落"""
        translated_paragraphs = []
        
        for i, paragraph in enumerate(paragraphs):
            print(f"翻译段落 {i+1}/{len(paragraphs)}")
            translated = self.translate(paragraph["text"])
            translated_paragraphs.append({
                "original": paragraph["text"],
                "translated": translated,
                "html": paragraph["html"]
            })
        
        return translated_paragraphs

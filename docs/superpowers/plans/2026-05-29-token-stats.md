# Token 消耗统计功能 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在自动化处理流程中记录每个步骤（翻译、摘要、闲鱼文案、小红书文案）的 Token 消耗和费用，最终在终端输出汇总报表，并支持通过 `stats` 命令查询历史记录。

**架构：**
1. 新增 `token_usage` 数据库表记录每步的 input/output tokens 和费用
2. 翻译步骤通过子进程桥接（临时 JSON 文件）传递 stats
3. 摘要/文案步骤在 `AIClient.chat()` 返回 tuple `(text, usage)` 后在调用方写入 DB
4. 费用按 DeepSeek 定价（¥1/百万输入 + ¥2/百万输出）自动计算

**技术栈：** SQLAlchemy (已有), DeepSeek API, subprocess, tempfile, argparse, rich.console (已有)

---

### 任务 1：在 models.py 新增 TokenUsage 模型

**文件：**
- 修改：`automation/models.py`

- [ ] **步骤 1.1：在 models.py 末尾添加 TokenUsage 模型**

```python
class TokenUsage(Base):
    """Token消耗记录"""
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(String(36), ForeignKey("books.id"), nullable=False, index=True)
    step = Column(String(32), nullable=False)  # translation / summary / xianyu / xiaohongshu
    model = Column(String(64), default="deepseek-chat")
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    book = relationship("Book", backref="token_usages")
```

---

### 任务 2：在 database.py 新增 Token 统计方法

**文件：**
- 修改：`automation/database.py`

- [ ] **步骤 2.1：在 DatabaseManager 类中添加 pricing 常量和 record_token_usage 方法**

```python
# DeepSeek 定价（元/百万token）
INPUT_PRICE_PER_MILLION = 1.0
OUTPUT_PRICE_PER_MILLION = 2.0

def record_token_usage(self, book_id, step, input_tokens, output_tokens, model="deepseek-chat"):
    """记录Token消耗"""
    from .models import TokenUsage
    total_tokens = input_tokens + output_tokens
    cost = (input_tokens / 1_000_000 * INPUT_PRICE_PER_MILLION +
            output_tokens / 1_000_000 * OUTPUT_PRICE_PER_MILLION)
    with self.get_session() as session:
        record = TokenUsage(
            book_id=book_id,
            step=step,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=round(cost, 6)
        )
        session.add(record)
        session.commit()
        return record
```

- [ ] **步骤 2.2：添加 get_token_usage 方法**

```python
def get_token_usage(self, book_id=None):
    """查询Token消耗记录"""
    from .models import TokenUsage
    with self.get_session() as session:
        query = session.query(TokenUsage)
        if book_id:
            query = query.filter(TokenUsage.book_id == book_id)
        return query.order_by(TokenUsage.created_at).all()
```

- [ ] **步骤 2.3：添加 get_token_summary 方法（用于终端输出）**

```python
def get_token_summary(self, book_id):
    """获取指定书籍的Token消耗汇总"""
    records = self.get_token_usage(book_id)
    if not records:
        return None
    
    steps = {}
    for r in records:
        step = r.step
        if step not in steps:
            steps[step] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost": 0.0}
        steps[step]["input_tokens"] += r.input_tokens
        steps[step]["output_tokens"] += r.output_tokens
        steps[step]["total_tokens"] += r.total_tokens
        steps[step]["cost"] += r.cost
    
    return steps
```

---

### 任务 3：在 translator.stats 中增加 prompt_tokens / completion_tokens 计数

**文件：**
- 修改：`ebook_translator/translator/translator.py`

- [ ] **步骤 3.1：在 stats 初始化中增加两个新字段**

```python
self.stats = {
    "api_calls": 0,
    "total_tokens": 0,
    "prompt_tokens": 0,    # 新增
    "completion_tokens": 0,  # 新增
    "cache_hits": 0,
    "translated_paragraphs": 0,
    "retried": 0,
    "failed": 0,
    "by_tier": {"tier1_short_repeatable": 0, "tier2_normal": 0, "tier3_long_complex": 0}
}
```

- [ ] **步骤 3.2：在 translate() 方法中增加 prompt_tokens / completion_tokens 计数**

```python
# 在 self.stats["total_tokens"] += ... 的附近增加：
self.stats["prompt_tokens"] += result.get("usage", {}).get("prompt_tokens", 0)
self.stats["completion_tokens"] += result.get("usage", {}).get("completion_tokens", 0)
self.stats["total_tokens"] += result.get("usage", {}).get("total_tokens", 0)
```

- [ ] **步骤 3.3：在 chat() 方法中做同样的修改**

```python
# 同上，在 chat() 方法的对应位置增加相同的三行
```

---

### 任务 4：ebook_translator/main.py — 写入临时 stats JSON 文件

**文件：**
- 修改：`ebook_translator/main.py`

- [ ] **步骤 4.1：在 argparse 中增加 --book-id 参数**

```python
parser.add_argument('--book-id', help='书籍ID（用于传递统计信息）')
```

- [ ] **步骤 4.2：在翻译完成后的统计显示区域，增加写入临时文件的逻辑**

```python
# 在显示统计信息之后，成本估算之前，增加：
if args.book_id:
    import json
    import tempfile
    stats_file = os.path.join(tempfile.gettempdir(), f"translation_stats_{args.book_id}.json")
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump({
            "prompt_tokens": stats.get("prompt_tokens", 0),
            "completion_tokens": stats.get("completion_tokens", 0),
            "total_tokens": stats.get("total_tokens", 0),
            "api_calls": stats.get("api_calls", 0),
            "cache_hits": stats.get("cache_hits", 0),
            "translated_paragraphs": stats.get("translated_paragraphs", 0)
        }, f, ensure_ascii=False)
    print(f"[Token统计] 已保存到临时文件: {stats_file}")
```

---

### 任务 5：translation_processor.py — 子进程结束后读取 stats 并写入 DB

**文件：**
- 修改：`automation/translation_processor.py`

- [ ] **步骤 5.1：在 subprocess 命令中添加 --book-id 参数**

```python
cmd = [
    sys.executable,
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "ebook_translator", "main.py"),
    epub_path,
    "--output-dir", str(self.output_dir / base_name),
    "--book-id", book_id
]
```

- [ ] **步骤 5.2：在 process.wait() 之后、返回之前，读取临时文件并写入 DB**

```python
# 在 process.wait() 之后、if process.returncode 之前：
import tempfile
import json
stats_file = os.path.join(tempfile.gettempdir(), f"translation_stats_{book_id}.json")
if os.path.exists(stats_file):
    try:
        with open(stats_file, "r", encoding="utf-8") as f:
            stats = json.load(f)
        os.remove(stats_file)
        self.db.record_token_usage(
            book_id=book_id,
            step="translation",
            input_tokens=stats.get("prompt_tokens", 0),
            output_tokens=stats.get("completion_tokens", 0)
        )
        logger.info(f"翻译Token消耗: 输入={stats.get('prompt_tokens', 0)}, 输出={stats.get('completion_tokens', 0)}")
    except Exception as e:
        logger.warning(f"读取翻译Token统计失败: {e}")
```

---

### 任务 6：ai_client.py — chat() 返回 (text, usage) tuple

**文件：**
- 修改：`automation/ai_client.py`

- [ ] **步骤 6.1：修改 chat() 返回 tuple**

```python
def chat(self, prompt: str, max_retries: int = None, max_tokens: int = None) -> tuple:
    """通用对话，返回 (text, usage)"""
    retries = max_retries or self.ai_config.get("retry_times", 3)
    result = self.translator.chat(prompt, max_retries=retries, max_tokens=max_tokens)
    # result 是 chat() 返回的完整 API 响应（dict）
    # Note: translator.chat() 返回的是 content 字符串（见 translator.py 第 166 行 return content.strip()）
    # 所以这里需要调整，让 translator.chat() 返回完整响应对象
    return result, {}
```

**⚠️ 注意：** 当前 `translator.chat()` 返回的是 `content.strip()` 字符串，不是完整的 API 响应。需要将它改为返回完整 `result` 字典，或在 `translator` 中新增一个方法。

有两种修复方式：

**方案 A（推荐）：在 translator.py 中新增 `chat_raw()` 方法，返回完整响应**

- [ ] **步骤 6.1a：在 translator.py 中新增 chat_raw() 方法**

```python
def chat_raw(self, prompt, max_retries=3, max_tokens=None):
    """通用对话，返回完整 API 响应"""
    effective_max_tokens = max_tokens if max_tokens else self.max_tokens
    retry_count = 0
    while retry_count < max_retries:
        if getattr(sys, 'interrupted', False) or (os.environ.get('INTERRUPTED') == '1'):
            return {"choices": [{"message": {"content": ""}}], "usage": {}}
        try:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": effective_max_tokens,
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
            if retry_count < max_retries:
                time.sleep(min(2 ** retry_count, 30))
    return {"choices": [{"message": {"content": ""}}], "usage": {}}
```

- [ ] **步骤 6.1b：修改 AIClient.chat() 改用 chat_raw()**

```python
def chat(self, prompt: str, max_retries: int = None, max_tokens: int = None) -> tuple:
    """通用对话，返回 (text, usage)"""
    retries = max_retries or self.ai_config.get("retry_times", 3)
    result = self.translator.chat_raw(prompt, max_retries=retries, max_tokens=max_tokens)
    text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    usage = result.get("usage", {})
    return text, usage
```

- [ ] **步骤 6.2：更新 generate_xianyu_listing() 和 generate_xiaohongshu_note() 返回 usage**

```python
def generate_xianyu_listing(self, book_info: Dict[str, Any]) -> tuple:
    """生成闲鱼商品文案，返回 (text, usage)"""
    # ... prompt 构建逻辑不变 ...
    return self.chat(prompt)

def generate_xiaohongshu_note(self, book_info: Dict[str, Any]) -> tuple:
    """生成小红书种草笔记，返回 (text, usage)"""
    # ... prompt 构建逻辑不变 ...
    return self.chat(prompt, max_tokens=2000)
```

---

### 任务 7：ContentSummarizer — 记录摘要的 Token 消耗

**文件：**
- 修改：`automation/content_summarizer.py`

- [ ] **步骤 7.1：在 _generate_summary() 中解包 usage 并记录**

```python
# 将：
result = self.ai.chat(prompt, max_tokens=8000)

# 改为：
result, usage = self.ai.chat(prompt, max_tokens=8000)

# 在 AI 调用完成后（parsed_result 之后），增加：
if usage:
    self.db.record_token_usage(
        book_id=book_id,
        step="summary",
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0)
    )
    logger.info(f"摘要Token消耗: 输入={usage.get('prompt_tokens', 0)}, 输出={usage.get('completion_tokens', 0)}")
```

---

### 任务 8：AICopywriter — 记录文案的 Token 消耗

**文件：**
- 修改：`automation/ai_copywriter.py`

- [ ] **步骤 8.1：在 generate() 中解包 usage 并记录**

```python
# 将：
xianyu_result = self.ai.generate_xianyu_listing(book_info)

# 改为：
xianyu_result, xianyu_usage = self.ai.generate_xianyu_listing(book_info)

# 将：
xiaohongshu_result = self.ai.generate_xiaohongshu_note(book_info)

# 改为：
xiaohongshu_result, xiaohongshu_usage = self.ai.generate_xiaohongshu_note(book_info)

# 在两次调用之后、MetadataWriter 之前，增加：
if xianyu_usage:
    self.db.record_token_usage(
        book_id=book_id, step="xianyu",
        input_tokens=xianyu_usage.get("prompt_tokens", 0),
        output_tokens=xianyu_usage.get("completion_tokens", 0)
    )
if xiaohongshu_usage:
    self.db.record_token_usage(
        book_id=book_id, step="xiaohongshu",
        input_tokens=xiaohongshu_usage.get("prompt_tokens", 0),
        output_tokens=xiaohongshu_usage.get("completion_tokens", 0)
    )
```

---

### 任务 9：automation/main.py — 新增 stats 命令 + 自动汇总输出

**文件：**
- 修改：`automation/main.py`

- [ ] **步骤 9.1：添加 `format_token_summary()` 辅助函数**

```python
def format_token_summary(book_id, book_title="书籍"):
    """格式化Token消耗汇总报表"""
    from automation.database import DatabaseManager
    db = DatabaseManager()
    steps = db.get_token_summary(book_id)
    if not steps:
        return None
    
    total_input = sum(s["input_tokens"] for s in steps.values())
    total_output = sum(s["output_tokens"] for s in steps.values())
    total_all = sum(s["total_tokens"] for s in steps.values())
    total_cost = sum(s["cost"] for s in steps.values())
    
    step_names = {
        "translation": "翻译",
        "summary": "摘要",
        "xianyu": "闲鱼文案",
        "xiaohongshu": "小红书文案"
    }
    
    lines = []
    lines.append("")
    lines.append("═" * 55)
    lines.append(f"  Token 消耗统计 — {book_title}")
    lines.append("═" * 55)
    lines.append(f"  {'步骤':<12} {'输入 Token':>12} {'输出 Token':>12} {'总 Token':>10} {'费用(¥)':>10}")
    lines.append(f"  {'─' * 54}")
    
    for step_key in ["translation", "summary", "xianyu", "xiaohongshu"]:
        if step_key in steps:
            s = steps[step_key]
            name = step_names.get(step_key, step_key)
            lines.append(
                f"  {name:<12} {s['input_tokens']:>12,} {s['output_tokens']:>12,} "
                f"{s['total_tokens']:>10,} {s['cost']:>10.4f}"
            )
    
    lines.append(f"  {'─' * 54}")
    lines.append(
        f"  {'合计':<12} {total_input:>12,} {total_output:>12,} "
        f"{total_all:>10,} {total_cost:>10.4f}"
    )
    lines.append("═" * 55)
    lines.append("")
    
    return "\n".join(lines)
```

- [ ] **步骤 9.2：在 process 命令末尾增加汇总输出**

```python
# 在 console.print(f"[bold green]处理完成: {book_id}[/bold green]") 之前增加：
summary = format_token_summary(book_obj.id, book_obj.title or book_id)
if summary:
    print(summary)
    db.add_log(book_id, "token_stats", "info", f"Token消耗: 总计{total_all}, 费用¥{total_cost:.4f}")
```

- [ ] **步骤 9.3：在 test 命令末尾增加汇总输出**

```python
# 在每个测试书籍处理完成后的合适位置，增加同样的汇总输出
summary = format_token_summary(book_id, final_title)
if summary:
    print(summary)
```

- [ ] **步骤 9.4：在 auto 命令中的每本书处理完成后增加汇总输出**

```python
# 在 auto 命令中每个书籍成功处理后增加
summary = format_token_summary(book_id, title)
if summary:
    console.print(summary)
```

- [ ] **步骤 9.5：添加 stats CLI 子命令**

```python
@app.command()
def stats(
    book_id: str = typer.Argument(..., help="书籍ID")
):
    """查看指定书籍的Token消耗统计"""
    from automation.database import DatabaseManager
    db = DatabaseManager()
    
    book = None
    all_books = db.get_all_books()
    for b in all_books:
        if b.id == book_id or b.id.startswith(book_id):
            book = b
            break
    
    if not book:
        console.print(f"[bold red]未找到书籍: {book_id}[/bold red]")
        raise typer.Exit(1)
    
    summary = format_token_summary(book.id, book.title or book_id)
    if summary:
        console.print(summary)
    else:
        console.print(f"[yellow]未找到 Token 消耗记录: {book_id}[/yellow]")
```

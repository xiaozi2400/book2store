# 重新发布失败书籍功能实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 让用户能列出发布失败的书籍并重新发布；同时修复发布失败状态的持久化与历史数据 backfill

**架构：** 修改 `xianyu_publisher.py` 在 `publish()` 失败时回写 `BookOutput.publish_status='failed'` + `publish_error`；在 `database.py` 新增 3 个方法（`get_books_by_publish_status` / `backfill_failed_publish_status` / `count_unbackfilled_failed`）；在 `main.py` 新增 3 个 Typer 命令（`list-failed` / `republish-failed` / `backfill-publish-status`）；在 `utils.py` 添加启动时静默检测的辅助函数；写 7 个 pytest 用例

**技术栈：** Python 3.9+, SQLAlchemy, Typer, Rich, pytest (内存数据库 via conftest.py)

**设计文档：** `docs/superpowers/specs/2026-06-14-republish-failed-books-design.md`

---

## 文件结构

**修改的文件：**
- `automation/xianyu_publisher.py` — `publish()` 的 except 块添加 3 行回写
- `automation/database.py` — `DatabaseManager` 类新增 3 个方法
- `automation/main.py` — 新增 3 个 Typer 命令 + 2 个辅助函数
- `automation/utils.py` — 新增 `check_unbackfilled_failed_books()` 工具函数
- `automation/__init__.py` — 启动时调用 `check_unbackfilled_failed_books()` 输出黄色提示
- `tests/test_republish_failed.py` — 新文件，7 个 pytest 用例
- `README.md` — 命令参考章节追加 3 个新命令

**不修改：** `config.yaml`（无新配置项）、`requirements-automation.txt`（无新依赖）、`CLAUDE.md`（README 更新后自然吸收）

---

### 任务 1：DatabaseManager 新增 `get_books_by_publish_status` 方法

**文件：**
- 修改：`automation/database.py:89-368`（在 `DatabaseManager` 类内追加）
- 测试：`tests/test_republish_failed.py`（新文件，先写失败测试）

- [ ] **步骤 1：写失败测试**

在 `tests/test_republish_failed.py` 新建文件，写入：

```python
"""发布失败书籍重新发布功能测试"""
import pytest
from automation.database import DatabaseManager
from automation.models import Book, BookOutput, ProcessingLog
from datetime import datetime


def test_get_books_by_publish_status_returns_only_failed(in_memory_db):
    """get_books_by_publish_status('failed') 只返回 publish_status='failed' 的书"""
    in_memory_db.add(Book(id="book-failed-1", filename="f1.epub", title="失败书1", status="completed"))
    in_memory_db.add(Book(id="book-failed-2", filename="f2.epub", title="失败书2", status="completed"))
    in_memory_db.add(Book(id="book-published-1", filename="p1.epub", title="已发布书", status="published"))
    in_memory_db.add(BookOutput(book_id="book-failed-1", publish_status="failed", publish_error="登录超时"))
    in_memory_db.add(BookOutput(book_id="book-failed-2", publish_status="failed", publish_error="扫码失败"))
    in_memory_db.add(BookOutput(book_id="book-published-1", publish_status="published", xianyu_listing_url="https://example.com/1"))
    in_memory_db.commit()

    db = DatabaseManager()
    result = db.get_books_by_publish_status("failed")

    assert len(result) == 2
    titles = {b.title for b in result}
    assert titles == {"失败书1", "失败书2"}
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest tests/test_republish_failed.py::test_get_books_by_publish_status_returns_only_failed -v
```

预期：FAIL，错误信息 `AttributeError: 'DatabaseManager' object has no attribute 'get_books_by_publish_status'`

- [ ] **步骤 3：实现方法**

在 `automation/database.py` 的 `DatabaseManager` 类末尾（`get_token_summary` 方法之后）追加：

```python
    def get_books_by_publish_status(self, status: str) -> list:
        """获取指定发布状态的书籍（join BookOutput）

        返回 Book 对象列表，按 updated_at DESC 排序（最近失败/成功的在前）
        """
        from .models import Book, BookOutput

        session = get_session()
        try:
            return session.query(Book).join(
                BookOutput, Book.id == BookOutput.book_id
            ).filter(
                BookOutput.publish_status == status
            ).order_by(Book.updated_at.desc()).all()
        finally:
            close_session(session)
```

- [ ] **步骤 4：运行测试确认通过**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest tests/test_republish_failed.py::test_get_books_by_publish_status_returns_only_failed -v
```

预期：PASS

- [ ] **步骤 5：提交**

```bash
cd D:/project/bookfile_bat && git add automation/database.py tests/test_republish_failed.py
git commit -m "feat(db): 新增 get_books_by_publish_status 查询方法"
```

---

### 任务 2：XianyuPublisher.publish() 失败时回写状态

**文件：**
- 修改：`automation/xianyu_publisher.py:84-89`（except 块）
- 测试：`tests/test_republish_failed.py`（追加测试）

- [ ] **步骤 1：写失败测试**

在 `tests/test_republish_failed.py` 末尾追加：

```python
def test_publish_failure_writes_publish_status_failed(in_memory_db, monkeypatch):
    """XianyuPublisher.publish() 失败时回写 BookOutput.publish_status='failed' 和 publish_error"""
    from automation.xianyu_publisher import XianyuPublisher

    in_memory_db.add(Book(id="book-001", filename="b1.epub", title="测试书", status="completed"))
    in_memory_db.add(BookOutput(book_id="book-001", publish_status="pending"))
    in_memory_db.commit()

    # Mock 整个 _start_browser 抛异常来触发 except 分支
    def mock_start_browser(self):
        raise RuntimeError("浏览器启动失败：playwright 未安装")

    monkeypatch.setattr(XianyuPublisher, "_start_browser", mock_start_browser)

    publisher = XianyuPublisher()
    result = publisher.publish("book-001")

    assert result is False  # 保留现有 API 契约

    in_memory_db.expire_all()
    book = in_memory_db.query(Book).filter(Book.id == "book-001").first()
    output = in_memory_db.query(BookOutput).filter(BookOutput.book_id == "book-001").first()
    assert output.publish_status == "failed"
    assert "playwright 未安装" in output.publish_error
    assert len(output.publish_error) <= 1000
    # 关键设计：Book.status 保持 'completed'（翻译等已完成），不回退为 'failed'
    assert book.status == "completed"
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest tests/test_republish_failed.py::test_publish_failure_writes_publish_status_failed -v
```

预期：FAIL, `assert output.publish_status == "failed"` 失败，因为当前 except 块没有回写

- [ ] **步骤 3：修改 except 块**

在 `automation/xianyu_publisher.py:84-89` 替换为：

```python
        except Exception as e:
            error_msg = str(e)[:1000]  # 防止异常信息过长撑爆数据库
            logger.error("发布失败: %s, 错误: %s" % (book_id, error_msg))
            self.db.update_book_output(
                book_id,
                publish_status="failed",
                publish_error=error_msg,
            )
            # 翻译/摘要/图片/文案都已完成，不算"整本失败"
            self.db.update_book_status(book_id, "completed")
            self.db.add_log(book_id, "publishing", "error", error_msg)
            self._capture_error_screenshot(book_id)
            self._close()
            return False
```

- [ ] **步骤 4：运行测试确认通过**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest tests/test_republish_failed.py::test_publish_failure_writes_publish_status_failed -v
```

预期：PASS

- [ ] **步骤 5：提交**

```bash
cd D:/project/bookfile_bat && git add automation/xianyu_publisher.py tests/test_republish_failed.py
git commit -m "feat(publisher): 发布失败时回写 publish_status 与 publish_error"
```

---

### 任务 3：新增 `list-failed` CLI 命令

**文件：**
- 修改：`automation/main.py`（在 `auto` 命令前插入新 Typer 命令）
- 测试：`tests/test_republish_failed.py`（追加 CliRunner 测试）

- [ ] **步骤 1：写失败测试**

在 `tests/test_republish_failed.py` 末尾追加：

```python
def test_list_failed_command_shows_failed_books(in_memory_db):
    """list-failed 命令输出含失败书名 + 提示运行 republish-failed"""
    from typer.testing import CliRunner
    from automation.main import app

    in_memory_db.add(Book(id="book-failed-1", filename="f1.epub", title="失败的书", status="completed"))
    in_memory_db.add(BookOutput(book_id="book-failed-1", publish_status="failed", publish_error="登录超时，请重试"))
    in_memory_db.commit()

    runner = CliRunner()
    result = runner.invoke(app, ["list-failed"])

    assert result.exit_code == 0
    assert "失败的书" in result.stdout
    assert "book-failed-1" in result.stdout  # 完整 UUID 必须显示
    assert "登录超时" in result.stdout
    assert "republish-failed" in result.stdout
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest tests/test_republish_failed.py::test_list_failed_command_shows_failed_books -v
```

预期：FAIL, `result.exit_code == 0` 失败（命令不存在会 exit 2）

- [ ] **步骤 3：实现 list-failed 命令**

在 `automation/main.py` 中，`@app.command() def auto(` 之前插入：

```python
@app.command()
def list_failed():
    """列出所有发布失败的书籍"""
    from automation.database import DatabaseManager
    from rich.table import Table
    from datetime import datetime

    db = DatabaseManager()
    failed_books = db.get_books_by_publish_status("failed")

    if not failed_books:
        console.print("[green]没有发布失败的书籍[/green]")
        return

    table = Table(title=f"发布失败的书籍 (共 {len(failed_books)} 本)")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("书名", style="white")
    table.add_column("作者", style="green")
    table.add_column("失败原因", style="red")
    table.add_column("失败时间", style="dim")

    for book in failed_books:
        output = book.outputs
        error = (output.publish_error or "")[:80]
        if len(output.publish_error or "") > 80:
            error += "..."

        # 查最近一条 publishing error 的时间
        last_err = db.get_logs(book.id)
        last_pub_err = None
        for log in reversed(last_err):
            if log.stage == "publishing" and log.status == "error":
                last_pub_err = log
                break
        ts = last_pub_err.created_at.strftime("%Y-%m-%d %H:%M") if last_pub_err else "-"

        table.add_row(
            book.id,  # 完整 UUID
            book.title or "Unknown",
            book.author or "Unknown",
            error,
            ts,
        )

    console.print(table)
    console.print(f"\n[red]共 {len(failed_books)} 本发布失败[/red]")
    console.print("[dim]运行 python -m automation.main republish-failed --all 重新发布[/dim]")
```

注意：`db.get_logs(book.id)` 已经存在于 `database.py:278`,直接复用。

- [ ] **步骤 4：运行测试确认通过**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest tests/test_republish_failed.py::test_list_failed_command_shows_failed_books -v
```

预期：PASS

- [ ] **步骤 5：提交**

```bash
cd D:/project/bookfile_bat && git add automation/main.py tests/test_republish_failed.py
git commit -m "feat(cli): 新增 list-failed 命令列出发布失败书籍"
```

---

### 任务 4：新增 `republish-failed` CLI 命令

**文件：**
- 修改：`automation/main.py`（在 `list-failed` 之后插入）
- 测试：`tests/test_republish_failed.py`（追加 CliRunner 测试）

- [ ] **步骤 1：写失败测试**

在 `tests/test_republish_failed.py` 末尾追加：

```python
def test_republish_failed_command_retries_all(in_memory_db, monkeypatch):
    """republish-failed --all --auto 重新发布所有失败书籍"""
    from typer.testing import CliRunner
    from automation.main import app
    from automation.xianyu_publisher import XianyuPublisher

    # 造 2 本失败书
    in_memory_db.add(Book(id="book-failed-1", filename="f1.epub", title="失败1", status="completed"))
    in_memory_db.add(Book(id="book-failed-2", filename="f2.epub", title="失败2", status="completed"))
    in_memory_db.add(BookOutput(book_id="book-failed-1", publish_status="failed", publish_error="登录超时"))
    in_memory_db.add(BookOutput(book_id="book-failed-2", publish_status="failed", publish_error="扫码失败"))
    in_memory_db.commit()

    # Mock publish：第 1 本仍失败，第 2 本成功
    call_count = {"n": 0}

    def mock_publish(self, book_id):
        call_count["n"] += 1
        if book_id == "book-failed-1":
            # 模拟真实的失败回写
            self.db.update_book_output(book_id, publish_status="failed", publish_error="再次登录超时")
            return False
        else:
            self.db.update_book_output(book_id, publish_status="published", xianyu_listing_url="https://example.com/2")
            self.db.update_book_status(book_id, "published")
            return True

    monkeypatch.setattr(XianyuPublisher, "publish", mock_publish)

    runner = CliRunner()
    result = runner.invoke(app, ["republish-failed", "--all", "--auto"])

    assert result.exit_code == 0
    assert call_count["n"] == 2

    in_memory_db.expire_all()
    out1 = in_memory_db.query(BookOutput).filter(BookOutput.book_id == "book-failed-1").first()
    out2 = in_memory_db.query(BookOutput).filter(BookOutput.book_id == "book-failed-2").first()
    assert out1.publish_status == "failed"  # 重试仍失败
    assert out2.publish_status == "published"  # 重试成功


def test_republish_failed_book_id_not_found_warns(in_memory_db):
    """republish-failed --book-id <not_found> 警告并跳过"""
    from typer.testing import CliRunner
    from automation.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["republish-failed", "--book-id", "nonexistent-uuid-xxx", "--auto"])

    assert result.exit_code == 0
    assert "未找到" in result.stdout or "跳过" in result.stdout
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest tests/test_republish_failed.py::test_republish_failed_command_retries_all tests/test_republish_failed.py::test_republish_failed_book_id_not_found_warns -v
```

预期：FAIL（命令不存在）

- [ ] **步骤 3：实现 republish-failed 命令**

在 `automation/main.py` 中 `list_failed` 命令之后插入：

```python
@app.command()
def republish_failed(
    all_: bool = typer.Option(False, "--all", help="重试所有发布失败的书籍"),
    book_id: Optional[list[str]] = typer.Option(None, "--book-id", help="重试指定 book_id（可多次）"),
    auto: bool = typer.Option(False, "--auto", help="跳过执行前的确认"),
):
    """重新发布失败的书籍"""
    from automation.database import DatabaseManager
    from automation.xianyu_publisher import publish_to_xianyu
    from rich.table import Table

    db = DatabaseManager()

    # 1. 筛选目标书
    if book_id:
        target_books = []
        for bid in book_id:
            book = db.get_book_by_id(bid)
            if book is None:
                console.print(f"[yellow]未找到书籍: {bid}，跳过[/yellow]")
                continue
            target_books.append(book)
    elif all_:
        target_books = db.get_books_by_publish_status("failed")
    else:
        # 无参数 = 等同 list-failed，只看不发
        console.print("[yellow]请指定 --all 或 --book-id <id>。先列出失败书籍：[/yellow]\n")
        list_failed()
        return

    if not target_books:
        console.print("[green]没有需要重新发布的书籍[/green]")
        return

    # 2. 确认（无 --auto 时）
    if not auto:
        table = Table(title=f"待重新发布 ({len(target_books)} 本)")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("书名", style="white")
        for book in target_books:
            table.add_row(book.id, book.title or "Unknown")
        console.print(table)

        confirm = typer.confirm(f"确认重新发布 {len(target_books)} 本书籍?")
        if not confirm:
            console.print("[yellow]已取消[/yellow]")
            return

    # 3. 逐本执行
    success_count = 0
    fail_count = 0
    failed_books = []

    for book in target_books:
        with phase(f"重新发布 {book.title or book.id}"):
            ok = publish_to_xianyu(book.id)
            if ok:
                success_count += 1
            else:
                fail_count += 1
                failed_books.append(book)

    # 4. 汇总
    console.print(f"\n[bold]===== 重新发布完成 =====[/bold]")
    console.print(f"[green]成功: {success_count}[/green]")
    if fail_count > 0:
        console.print(f"[red]失败: {fail_count}[/red]")

    if failed_books:
        fail_table = Table(title="失败明细")
        fail_table.add_column("ID", style="cyan", no_wrap=True)
        fail_table.add_column("书名", style="white")
        fail_table.add_column("失败原因", style="red")
        for book in failed_books:
            output = db.get_book_output(book.id)
            err = (output.publish_error or "")[:80] if output else "未知"
            fail_table.add_row(book.id, book.title or "Unknown", err)
        console.print(fail_table)
        console.print("[dim]查看 logs/publish_error_<id>_<ts>.png 截图或 logs/automation_YYYYMMDD.log 详细日志[/dim]")
```

- [ ] **步骤 4：运行测试确认通过**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest tests/test_republish_failed.py::test_republish_failed_command_retries_all tests/test_republish_failed.py::test_republish_failed_book_id_not_found_warns -v
```

预期：PASS

- [ ] **步骤 5：提交**

```bash
cd D:/project/bookfile_bat && git add automation/main.py tests/test_republish_failed.py
git commit -m "feat(cli): 新增 republish-failed 命令批量重试发布"
```

---

### 任务 5：DatabaseManager 新增 backfill 与 count 方法

**文件：**
- 修改：`automation/database.py`（在 `get_books_by_publish_status` 之后追加）
- 测试：`tests/test_republish_failed.py`（追加测试）

- [ ] **步骤 1：写失败测试**

在 `tests/test_republish_failed.py` 末尾追加：

```python
def test_backfill_failed_publish_status_marks_pending_as_failed(in_memory_db):
    """backfill_failed_publish_status 把'日志中曾失败但 publish_status 仍 pending'的回填为 failed"""
    from automation.database import DatabaseManager

    # 造历史失败数据：publish_status='pending' 但日志里有 error
    in_memory_db.add(Book(id="book-hist-1", filename="h1.epub", title="历史失败", status="completed"))
    in_memory_db.add(BookOutput(book_id="book-hist-1", publish_status="pending"))
    in_memory_db.add(ProcessingLog(book_id="book-hist-1", stage="publishing", status="error", message="历史登录超时"))

    # 造已发布成功的书：不应被回填
    in_memory_db.add(Book(id="book-pub-1", filename="p1.epub", title="已成功", status="published"))
    in_memory_db.add(BookOutput(book_id="book-pub-1", publish_status="published"))
    in_memory_db.add(ProcessingLog(book_id="book-pub-1", stage="publishing", status="error", message="早期错误但后来成功了"))
    in_memory_db.add(ProcessingLog(book_id="book-pub-1", stage="publishing", status="success", message="成功发布"))

    # 造完全干净的书：不应被回填
    in_memory_db.add(Book(id="book-clean-1", filename="c1.epub", title="干净", status="completed"))
    in_memory_db.add(BookOutput(book_id="book-clean-1", publish_status="pending"))
    in_memory_db.commit()

    db = DatabaseManager()
    count = db.backfill_failed_publish_status()

    assert count == 1  # 只有 book-hist-1 应被回填

    in_memory_db.expire_all()
    out_hist = in_memory_db.query(BookOutput).filter(BookOutput.book_id == "book-hist-1").first()
    out_pub = in_memory_db.query(BookOutput).filter(BookOutput.book_id == "book-pub-1").first()
    out_clean = in_memory_db.query(BookOutput).filter(BookOutput.book_id == "book-clean-1").first()

    assert out_hist.publish_status == "failed"
    assert out_hist.publish_error == "历史登录超时"
    # 已成功的不应被覆盖
    assert out_pub.publish_status == "published"
    # 干净的不应被回填
    assert out_clean.publish_status == "pending"


def test_backfill_is_idempotent(in_memory_db):
    """backfill 重复运行返回 0（幂等）"""
    from automation.database import DatabaseManager

    in_memory_db.add(Book(id="book-idem-1", filename="i1.epub", title="幂等测试", status="completed"))
    in_memory_db.add(BookOutput(book_id="book-idem-1", publish_status="pending"))
    in_memory_db.add(ProcessingLog(book_id="book-idem-1", stage="publishing", status="error", message="错误"))
    in_memory_db.commit()

    db = DatabaseManager()
    assert db.backfill_failed_publish_status() == 1
    assert db.backfill_failed_publish_status() == 0  # 第二次幂等


def test_count_unbackfilled_failed(in_memory_db):
    """count_unbackfilled_failed 正确计数未回填的失败书"""
    from automation.database import DatabaseManager

    in_memory_db.add(Book(id="book-a", filename="a.epub", title="A", status="completed"))
    in_memory_db.add(BookOutput(book_id="book-a", publish_status="pending"))
    in_memory_db.add(ProcessingLog(book_id="book-a", stage="publishing", status="error", message="err"))
    in_memory_db.add(Book(id="book-b", filename="b.epub", title="B", status="completed"))
    in_memory_db.add(BookOutput(book_id="book-b", publish_status="failed"))  # 已回填
    in_memory_db.add(ProcessingLog(book_id="book-b", stage="publishing", status="error", message="err"))
    in_memory_db.commit()

    db = DatabaseManager()
    assert db.count_unbackfilled_failed() == 1  # 只有 book-a
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest tests/test_republish_failed.py::test_backfill_failed_publish_status_marks_pending_as_failed tests/test_republish_failed.py::test_backfill_is_idempotent tests/test_republish_failed.py::test_count_unbackfilled_failed -v
```

预期：FAIL（方法不存在）

- [ ] **步骤 3：实现 backfill 与 count 方法**

在 `automation/database.py` 中 `get_books_by_publish_status` 之后追加：

```python
    def backfill_failed_publish_status(self) -> int:
        """回填历史发布失败状态：把 processing_logs 里 publishing 阶段失败、但 publish_status 仍为 pending 的书标记为 failed。

        返回回填的数量。幂等：重复运行返回 0。
        """
        from .models import Book, BookOutput, ProcessingLog

        session = get_session()
        try:
            # 找出"日志中曾发布失败"的 book_id 集合
            failed_book_ids_subq = session.query(ProcessingLog.book_id).filter(
                ProcessingLog.stage == "publishing",
                ProcessingLog.status == "error",
            ).distinct().subquery()

            # 这些书里，publish_status 仍为 pending 或 NULL 的要回填
            targets = session.query(BookOutput).join(
                failed_book_ids_subq, BookOutput.book_id == failed_book_ids_subq.c.book_id
            ).filter(
                BookOutput.publish_status.in_(["pending", None])
            ).all()

            for output in targets:
                # 取该书最近一条 publishing error 的 message
                last_err = session.query(ProcessingLog).filter(
                    ProcessingLog.book_id == output.book_id,
                    ProcessingLog.stage == "publishing",
                    ProcessingLog.status == "error",
                ).order_by(ProcessingLog.created_at.desc()).first()

                output.publish_status = "failed"
                if last_err:
                    output.publish_error = (last_err.message or "")[:1000]
                # Book.status 保持不变（历史状态不动，避免误判）

            session.commit()
            return len(targets)
        finally:
            close_session(session)

    def count_unbackfilled_failed(self) -> int:
        """统计未回填的失败书数量（用于启动时提示）"""
        from .models import BookOutput, ProcessingLog

        session = get_session()
        try:
            failed_book_ids_subq = session.query(ProcessingLog.book_id).filter(
                ProcessingLog.stage == "publishing",
                ProcessingLog.status == "error",
            ).distinct().subquery()

            return session.query(BookOutput).join(
                failed_book_ids_subq, BookOutput.book_id == failed_book_ids_subq.c.book_id
            ).filter(
                BookOutput.publish_status.in_(["pending", None])
            ).count()
        finally:
            close_session(session)
```

- [ ] **步骤 4：运行测试确认通过**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest tests/test_republish_failed.py::test_backfill_failed_publish_status_marks_pending_as_failed tests/test_republish_failed.py::test_backfill_is_idempotent tests/test_republish_failed.py::test_count_unbackfilled_failed -v
```

预期：PASS

- [ ] **步骤 5：提交**

```bash
cd D:/project/bookfile_bat && git add automation/database.py tests/test_republish_failed.py
git commit -m "feat(db): 新增 backfill_failed_publish_status 与 count_unbackfilled_failed"
```

---

### 任务 6：新增 `backfill-publish-status` CLI 命令

**文件：**
- 修改：`automation/main.py`（在 `republish_failed` 之后插入）
- 测试：`tests/test_republish_failed.py`（追加 CliRunner 测试）

- [ ] **步骤 1：写失败测试**

在 `tests/test_republish_failed.py` 末尾追加：

```python
def test_backfill_publish_status_command_runs(in_memory_db):
    """backfill-publish-status 命令回填并打印数量"""
    from typer.testing import CliRunner
    from automation.main import app

    in_memory_db.add(Book(id="book-bf-1", filename="b1.epub", title="BF1", status="completed"))
    in_memory_db.add(BookOutput(book_id="book-bf-1", publish_status="pending"))
    in_memory_db.add(ProcessingLog(book_id="book-bf-1", stage="publishing", status="error", message="历史失败"))
    in_memory_db.commit()

    runner = CliRunner()
    result = runner.invoke(app, ["backfill-publish-status"])

    assert result.exit_code == 0
    assert "1" in result.stdout  # 回填了 1 本
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest tests/test_republish_failed.py::test_backfill_publish_status_command_runs -v
```

预期：FAIL

- [ ] **步骤 3：实现 backfill 命令**

在 `automation/main.py` 中 `republish_failed` 命令之后插入：

```python
@app.command()
def backfill_publish_status():
    """回填历史发布失败状态：把日志中曾发布失败但 publish_status 仍 pending 的书标记为 failed。幂等。"""
    from automation.database import DatabaseManager

    db = DatabaseManager()
    count = db.backfill_failed_publish_status()

    if count == 0:
        console.print("[green]没有需要回填的书籍[/green]")
    else:
        console.print(f"[bold green]回填完成：{count} 本书籍的 publish_status 标记为 failed[/bold green]")
        console.print("[dim]运行 python -m automation.main list-failed 查看[/dim]")
```

- [ ] **步骤 4：运行测试确认通过**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest tests/test_republish_failed.py::test_backfill_publish_status_command_runs -v
```

预期：PASS

- [ ] **步骤 5：提交**

```bash
cd D:/project/bookfile_bat && git add automation/main.py tests/test_republish_failed.py
git commit -m "feat(cli): 新增 backfill-publish-status 命令回填历史失败"
```

---

### 任务 7：启动时静默检测未回填书籍

**文件：**
- 修改：`automation/utils.py`（新增工具函数）
- 修改：`automation/main.py` 入口（启动时调用）
- 测试：`tests/test_republish_failed.py`（追加测试）

- [ ] **步骤 1：写失败测试**

在 `tests/test_republish_failed.py` 末尾追加：

```python
def test_check_unbackfilled_prints_warning(in_memory_db, capsys):
    """check_unbackfilled_failed_books 检测到未回填时打印黄色提示"""
    from automation.utils import check_unbackfilled_failed_books

    in_memory_db.add(Book(id="book-warn-1", filename="w1.epub", title="W1", status="completed"))
    in_memory_db.add(BookOutput(book_id="book-warn-1", publish_status="pending"))
    in_memory_db.add(ProcessingLog(book_id="book-warn-1", stage="publishing", status="error", message="err"))
    in_memory_db.commit()

    check_unbackfilled_failed_books()

    captured = capsys.readouterr()
    assert "1" in captured.out
    assert "backfill-publish-status" in captured.out
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest tests/test_republish_failed.py::test_check_unbackfilled_prints_warning -v
```

预期：FAIL（函数不存在）

- [ ] **步骤 3：实现工具函数**

在 `automation/utils.py` 末尾追加（先用 Read 确认文件末尾）：

```python
def check_unbackfilled_failed_books():
    """启动时静默检测：若有历史发布失败未回填则打印黄色提示。不修改数据。"""
    from .database import DatabaseManager
    try:
        db = DatabaseManager()
        count = db.count_unbackfilled_failed()
        if count > 0:
            print("\n[yellow]⚠ 检测到 %d 本历史发布失败未标记 publish_status='failed'[/yellow]" % count)
            print("[yellow]  运行 python -m automation.main backfill-publish-status 一次性回填[/yellow]\n")
    except Exception:
        pass  # 启动检测失败不应阻塞主流程
```

- [ ] **步骤 4：运行测试确认通过**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest tests/test_republish_failed.py::test_check_unbackfilled_prints_warning -v
```

预期：PASS

- [ ] **步骤 5：在 main.py 启动入口调用**

修改 `automation/main.py` 末尾：

```python
if __name__ == "__main__":
    from automation.utils import check_unbackfilled_failed_books
    check_unbackfilled_failed_books()
    app()
```

- [ ] **步骤 6：手动验证启动提示**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m automation.main --help
```

预期：输出 help 且无错误（无未回填数据时不打印提示）

- [ ] **步骤 7：提交**

```bash
cd D:/project/bookfile_bat && git add automation/utils.py automation/main.py tests/test_republish_failed.py
git commit -m "feat: 启动时静默检测未回填发布失败书籍"
```

---

### 任务 8：README 文档更新

**文件：**
- 修改：`README.md`（在"发布相关"章节追加 3 个命令）

- [ ] **步骤 1：在发布相关章节追加**

找到 README.md 的"发布相关"小节（在 auto 命令一节附近），在 `generate_list` 命令后追加：

````markdown
#### 查看与重试发布失败

```bash
# 列出所有发布失败的书籍（完整 ID + 失败原因 + 失败时间）
python -m automation.main list-failed

# 重新发布所有失败的书籍（带确认提示）
python -m automation.main republish-failed --all

# 重新发布指定 ID（可多次）
python -m automation.main republish-failed --book-id <id1> --book-id <id2>

# 跳过确认提示
python -m automation.main republish-failed --all --auto

# 回填历史发布失败状态（幂等，启动时若有未回填会自动提示）
python -m automation.main backfill-publish-status
```

发布失败的书籍在数据库中由 `BookOutput.publish_status='failed'` 标识，可通过 `list-failed` 查看。
````

- [ ] **步骤 2：验证 README 渲染正常**

```bash
cd D:/project/bookfile_bat && head -200 README.md | grep -A 5 "list-failed"
```

预期：能看到新命令的引用

- [ ] **步骤 3：提交**

```bash
cd D:/project/bookfile_bat && git add README.md
git commit -m "docs: README 追加 list-failed/republish-failed/backfill-publish-status 用法"
```

---

### 任务 9：全量回归测试

**文件：** 无（仅运行）

- [ ] **步骤 1：运行全部测试**

```bash
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m pytest -v
```

预期：全部 PASS（旧的 + 新增的 7 个）

- [ ] **步骤 2：手动冒烟测试**

```bash
# 1. 列出当前失败书
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m automation.main list-failed

# 2. 启动时检测提示（首次运行若有历史失败数据应有提示）
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m automation.main --help

# 3. 回填
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m automation.main backfill-publish-status

# 4. 重新查看
cd D:/project/bookfile_bat && .venv/Scripts/python.exe -m automation.main list-failed
```

预期：list-failed 输出表格；启动提示数量与实际一致；回填打印数量；第二次 list-failed 能看到更多

- [ ] **步骤 3：如有失败，修复并重跑**

若任何步骤失败，定位修复后重跑全量。

---

## 完成检查清单

- [ ] 任务 1-8 全部提交
- [ ] 任务 9 全量测试通过
- [ ] 手动冒烟测试通过
- [ ] 至少 1 本历史失败书籍被回填 + 重新发布成功

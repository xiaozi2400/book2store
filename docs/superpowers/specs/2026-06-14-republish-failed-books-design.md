# 重新发布失败书籍功能设计

**日期**: 2026-06-14
**状态**: 待评审

---

## 背景

当前系统的闲鱼发布流程偶有失败(扫码登录超时、页面元素定位失败、SKU 配置异常等)。失败后用户想再次发布,流程是:

1. 通过 `processing_logs` 表(`stage='publishing' AND status='error'`)反推哪些书失败
2. 拿到 `book_id`
3. 运行 `python -m automation.main publish <book_id> --auto`

**问题:**

- `book_id` 不直观,用户要先查数据库/日志才能找到
- 失败原因不可见,要翻日志才知道当时为啥挂的
- 没有批量入口,失败书多时要逐个重发
- **最关键的缺陷**:目前 `XianyuPublisher.publish()` 失败时**只写日志不写状态**——`BookOutput.publish_status` 失败时仍是默认值 `"pending"`,`publish_error` 字段模型里有但代码从未写入。失败状态没有任何持久化标志,只能从 `processing_logs` 反推,数据不干净

## 目标

1. 修复发布失败的持久化:让 `BookOutput.publish_status='failed'` 成为"发布失败"的权威标志
2. 新增 `list-failed` 命令:列出所有发布失败的书籍 + 失败原因
3. 新增 `republish-failed` 命令:批量或选定重试发布

## 非目标

- 不重做发布流程本身(`XianyuPublisher.publish()` 内部逻辑不动)
- 不改 `Book.status` 状态机(发布失败不算"整本失败",不触发 `auto` 重做翻译等)
- 不做自动定时重试(用户手动触发)
- 不做发送通知/邮件
- 不动 `processing_logs` 表结构

---

## 设计

### 1. 持久化修复

**位置**: `automation/xianyu_publisher.py:84-89`(现有 except 块)

**现状**(失败时只写日志):
```python
except Exception as e:
    logger.error("发布失败: %s, 错误: %s" % (book_id, str(e)))
    self.db.add_log(book_id, "publishing", "error", str(e))
    self._capture_error_screenshot(book_id)
    self._close()
    return False
```

**改为**:
```python
except Exception as e:
    error_msg = str(e)[:1000]  # 防止异常信息过长撑爆数据库
    logger.error("发布失败: %s, 错误: %s" % (book_id, error_msg))
    self.db.update_book_output(
        book_id,
        publish_status="failed",
        publish_error=error_msg,
    )
    # 翻译/摘要/图片/文案都已完成,不算"整本失败"
    self.db.update_book_status(book_id, "completed")
    self.db.add_log(book_id, "publishing", "error", error_msg)
    self._capture_error_screenshot(book_id)
    self._close()
    return False
```

**字段语义**(沿用 `BookOutput` 模型,无新字段):

| 字段 | 取值 |
|------|------|
| `BookOutput.publish_status` | `"pending"`(未发) / `"published"`(成功) / `"failed"`(失败) |
| `BookOutput.publish_error` | 失败时的异常信息,最多 1000 字符,成功时保持 None |
| `Book.status` | 保持原状态机;发布失败时设 `"completed"`(翻译等已完成) |

**重要设计选择**: `Book.status` 失败时**不回退为 `"failed"`**。原因:

- 翻译/摘要/图片/文案都已生成,这些产物都有效
- 如果 `Book.status='failed'`,用户看到的状态统计会把它和"整本失败"混在一起,容易误判要不要重跑 `auto`
- `BookOutput.publish_status` 已经够细粒度区分"整本完成但发布失败"vs"整本失败"

### 2. 数据库查询方法

**位置**: `automation/database.py` 中 `DatabaseManager` 类

**新增方法**:

```python
def get_books_by_publish_status(self, status: str) -> list:
    """获取指定发布状态的书籍(join BookOutput)
    
    返回 Book 对象列表,按 updated_at DESC 排序(最近失败的在前)
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

### 3. CLI 命令一:`list-failed`

**位置**: `automation/main.py`,新增 `@app.command() def list_failed()`

**行为**:

- 查 `BookOutput.publish_status='failed'` 的所有书
- 用 Rich 表格展示:

| 字段 | 来源 |
|------|------|
| ID | `book.id`(完整 UUID) |
| 书名 | `book.title` |
| 作者 | `book.author` |
| 失败原因 | `book.outputs.publish_error[:80] + '...'`(超过截断) |
| 失败时间 | 从 `processing_logs` 查 `stage='publishing' AND status='error' AND book_id=book.id ORDER BY created_at DESC LIMIT 1` 取 `created_at` |

- 末尾输出:
  - `[red]共 N 本发布失败[/red]`
  - 提示 `运行 python -m automation.main republish-failed --all 重新发布`
  - 如果没有失败书:`[green]没有发布失败的书籍[/green]`

**失败时间的二次查询**:可以容忍 N+1,因为失败书通常不多。如果担心性能,后面用 `IN` 批量查 + 内存分组——但暂不优化。

### 4. CLI 命令二:`republish-failed`

**位置**: `automation/main.py`,新增 `@app.command() def republish_failed(...)`

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `--all` | flag | 重试所有 `publish_status='failed'` 的书 |
| `--book-id` | List[str] | 重试指定 id(可多次);优先级高于 `--all` |
| `--auto` | flag | 跳过执行前的 y/n 确认 |

**行为**:

1. **筛选目标书**:
   - 如果给了 `--book-id`:从列表里用 `db.get_book_by_id()` 逐个查,跳过找不到的(打印警告)
   - 如果给了 `--all` 或无参数:查 `get_books_by_publish_status('failed')`
   - **都没有**:打印用法提示,退出 0
   - **筛选后为空**:打印"没有需要重新发布的书籍",退出 0

2. **确认(无 `--auto` 时)**:
   - 打印待重试清单(Rich 表格)
   - `typer.confirm(f"确认重新发布 {N} 本书籍?")` — 用户取消则退出 0

3. **逐本执行**:
   ```python
   for book in target_books:
       with phase(f"重新发布 {book.title}"):
           success = publish_to_xianyu(book.id)  # 复用现有函数
           # publish_to_xianyu 内部已会在失败时回写 publish_status='failed'
   ```

4. **执行后汇总**:
   - 统计 `success_count` / `fail_count`
   - 失败的书再查一次 `book.outputs.publish_error` 和 `book.outputs.publish_status`,在汇总表格里展示
   - 失败时指引:`查看 logs/publish_error_<id>_<ts>.png 截图` + `查看 logs/automation_YYYYMMDD.log 详细日志`

**复用原则**: `republish-failed` 调 `publish_to_xianyu()`(已存在)而不是直接调 `XianyuPublisher.publish()`,和现有 `publish` 命令路径一致。

### 6. 历史数据 backfill ⭐

**为什么需要**: 本次修复只对**新失败**生效。修复前已发布失败的书(典型场景:你仓库里现在就有的若干本失败书),它们的 `BookOutput.publish_status` 仍是默认 `"pending"`,`list-failed` 查不到,需要一次性回填。

**位置**: `automation/database.py`,`DatabaseManager` 新增方法:

```python
def backfill_failed_publish_status(self) -> int:
    """回填历史发布失败状态:把 processing_logs 里 publishing 阶段失败、
    但 publish_status 仍为 pending 的书标记为 failed。
    
    返回回填的数量。
    """
    from .models import Book, BookOutput, ProcessingLog
    from sqlalchemy import and_, not_
    session = get_session()
    try:
        # 找出"日志中曾发布失败,但 publish_status 仍 pending"的书
        failed_book_ids = session.query(ProcessingLog.book_id).filter(
            ProcessingLog.stage == "publishing",
            ProcessingLog.status == "error",
        ).distinct().subquery()

        # 这些书里,publish_status='pending' 或 publish_status is null 的要回填
        targets = session.query(BookOutput).join(
            failed_book_ids, BookOutput.book_id == failed_book_ids.c.book_id
        ).filter(
            BookOutput.publish_status.in_(["pending", None])
        ).all()

        for output in targets:
            # 取该书最近一条 publishing error 的 message 作为 publish_error
            last_err = session.query(ProcessingLog).filter(
                ProcessingLog.book_id == output.book_id,
                ProcessingLog.stage == "publishing",
                ProcessingLog.status == "error",
            ).order_by(ProcessingLog.created_at.desc()).first()

            output.publish_status = "failed"
            if last_err:
                output.publish_error = (last_err.message or "")[:1000]
            # Book.status 保持不变(历史状态不动,避免误判)
            # 不重写 Book.status='completed',因为可能历史本来就是其他状态
        session.commit()
        return len(targets)
    finally:
        close_session(session)
```

**触发方式**: 两条路,选其一:

- **A 方案(本次选)**: `XianyuPublisher.__init__` 或 `DatabaseManager.__init__` 启动时检测"日志里有 publishing error 但 publish_status 仍 pending 的书" > 0,打印黄色提示"检测到 N 本历史发布失败未标记,运行 `python -m automation.main backfill-publish-status` 回填"。**不自动改,只提示**——避免静默修改用户数据
- 用户跑 `python -m automation.main backfill-publish-status` 显式回填,打印回填数量,exit 0

**理由**:
- 静默改数据有风险(万一回填逻辑写错,数据污染)
- 启动提示是低侵入的好习惯,用户看到通知后主动决定

**幂等**: `book.outputs.publish_status` 已为 `'failed'` 的不会再次被处理(过滤条件)。重复运行安全。

**测试**:
- 在测试数据里造:`BookOutput(publish_status='pending')` + `ProcessingLog(stage='publishing', status='error', message='登录超时')`
- 调 `backfill_failed_publish_status()`
- 断言:返回 1,`output.publish_status == 'failed'`,`output.publish_error == '登录超时'`
- 再调一次,断言返回 0(幂等)

### 5. 错误处理

| 场景 | 处理 |
|------|------|
| 无 `--all` 也无 `--book-id` | 打印用法,退出 0 |
| `--book-id` 找不到 | 跳过该 id,打印黄色警告,继续其他 |
| 重试发布过程中某本失败 | `phase()` 会输出 `✗ 失败: <异常类型>: <消息>`,汇总表里展示原因和指引 |
| 数据库查询失败 | typer 异常打印,exit 1 |
| `publish_to_xianyu` 内部异常 | 透传(它自身已有 `return False` 路径,新加的回写也会跑) |

### 6. 与现有命令的关系

| 命令 | 关系 |
|------|------|
| `publish <book_id>` | 保留不变,单本发布入口;`republish-failed --book-id <id>` 是它的批量/列表增强版 |
| `auto` | 不动;`auto` 跑完后,用户用 `list-failed` 看哪些发布挂了,再用 `republish-failed` 补救 |
| `status` | 不动;它统计的是 `Book.status` 整体完成情况,不显示发布失败细分 |
| `list --status-filter failed` | 不动;它查的是 `Book.status='failed'`,与"发布失败"语义不同 |

### 7. 测试

**位置**: `tests/test_republish_failed.py`(新文件)

**用例**:

1. **`XianyuPublisher.publish` 失败时回写 `publish_status='failed'`**:
   - Mock `playwright` 让 `_start_browser` 抛异常
   - 调 `publish(book_id)`
   - 断言 `db.get_book_output(book_id).publish_status == 'failed'`
   - 断言 `db.get_book_output(book_id).publish_error` 非空且 ≤ 1000 字符
   - 断言 `db.get_book_by_id(book_id).status == 'completed'`(不是 `'failed'`)

2. **`get_books_by_publish_status('failed')` 返回正确**:
   - 创建 2 本 `publish_status='failed'` + 1 本 `publish_status='published'`
   - 断言返回 2 本,且按 `updated_at` DESC 排序

3. **`list_failed` CLI 命令**:
   - 用 `typer.testing.CliRunner` 调 `python -m automation.main list-failed`
   - 断言输出包含失败书名 + 提示运行 `republish-failed --all`

4. **`republish-failed --all` 实际重试**:
   - Mock `XianyuPublisher.publish` 让它第一次失败、第二次成功
   - 调 `republish_failed --all --auto`(避免 confirm)
   - 断言:失败的那本 `publish_status` 仍为 `'failed'`,成功的那本变为 `'published'`

5. **`republish-failed --book-id <not_found>` 警告并跳过**:
   - 断言 exit 0,输出警告,不抛异常

6. **`backfill_failed_publish_status` 回填历史失败**:
   - 造测试数据:`BookOutput(publish_status='pending')` + `ProcessingLog(stage='publishing', status='error', message='登录超时')`
   - 调 `backfill_failed_publish_status()`
   - 断言:返回 1,`output.publish_status == 'failed'`,`output.publish_error == '登录超时'`
   - 再调一次断言返回 0(幂等)
   - 另测:`publish_status='published'` 的不应被回填(过滤条件)

7. **启动提示历史未回填**:
   - 造 1 本未回填 + 1 本已回填的数据
   - 调用提示检测函数
   - 断言:返回 1(只有 1 本需要回填)

**测试基础设施复用**: `tests/conftest.py` 已有内存数据库 + `reset_db_engine` 自动 fixture,无需新加。

---

## 改动文件清单

| 文件 | 改动 |
|------|------|
| `automation/xianyu_publisher.py` | `publish()` except 块加 3 行回写(总改动 ~10 行) |
| `automation/database.py` | 新增 `get_books_by_publish_status(status)` + `backfill_failed_publish_status()` + `count_unbackfilled_failed()` 三个方法(~50 行) |
| `automation/main.py` | 新增 3 个 Typer 命令:`list-failed` / `republish-failed` / `backfill-publish-status` + 辅助函数(预估 ~120 行) |
| `tests/test_republish_failed.py` | 新增测试文件(预估 ~180 行,含 7 个用例) |
| `README.md` | 命令参考章节追加 3 个新命令的用例 + backfill 提示 |
| `CLAUDE.md` | 无需改(新命令属于常用命令,会随 README 更新被 agent 自然读到) |

**无 schema 变更**: `BookOutput.publish_status` 和 `publish_error` 字段已存在。
**无配置文件变更**: `config.yaml` 不动。
**无依赖变更**: `requirements-automation.txt` 不动。

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 现有数据库里"事实已失败"的书 `publish_status` 仍是 `"pending"`,被新命令漏掉 | **本次已处理**: 新增 `backfill-publish-status` 命令 + 启动时静默检测(只提示不自动改),用户主动运行回填。`backfill_failed_publish_status()` 幂等,反复跑安全。**注意**: backfill 不重写 `Book.status`(只动 `BookOutput`),避免历史状态被误改 |
| 重新发布时 `metadata/` 目录已被人手工删了 | 复用 `XianyuPublisher.publish()` 的现有校验(`xianyu_listing.txt` 不存在会抛 `ValueError("未找到闲鱼文案: ...")`,新加的回写会正确记录失败原因) |
| 扫码登录超时,Playwright 整个流程被打断 | 透传到现有 `XianyuPublisher._login()` 逻辑,新加的 except 块也会捕获,记录失败原因 |
| 批量重试过程中浏览器实例异常关闭 | `_close()` 已在 `publish()` finally / except 中调用,新加的回写在 except 块、`_close()` 之前执行,顺序安全 |
| Backfill SQL 误改 `publish_status='published'` 的成功书 | 过滤条件 `publish_status IN ('pending', NULL)` 显式排除已成功的;`tests/test_republish_failed.py` 用例 6 专门覆盖这个不变式 |
| 测试中 Mock Playwright 比较繁琐 | 已有 `tests/test_xianyu_publisher_images.py` 可参考其 Mock 模式 |

---

## 后续可考虑(本次不做)

- `list-failed` 输出支持 `--json` 给脚本消费
- `republish-failed --since YYYY-MM-DD` 只重试某个时间之后的失败
- 自动定时重试(用 cron + `republish-failed --all --auto`)
- 把"发布失败"统计集成到 `status` 命令的统计表
- 启动时如果检测到未回填,**自动**跑 backfill(本次只提示,不动数据)

# 生成单元测试 Skill

## 触发条件

- 用户调用 `/generate-unit-tests`
- 用户请求"生成单元测试"、"generate unit tests"、"写测试"、"单元测试"
- 可选：命令后可指定模块路径（例如 `/generate-unit-tests mymodule/`）

## 核心原则：Patch 在使用处，而非定义处

```
patch(target) 中的 target 是"被测模块中引用该对象时的完整路径"，
而非"被测对象原始定义的位置"。
```

示例：
- `DatabaseManager` 定义在 `mymodule.database`，但在 `mymodule.service.py` 中以 `from mymodule.database import DatabaseManager` 导入
- 正确 patch 路径：`patch('mymodule.service.DatabaseManager')`
- 错误 patch 路径：`patch('mymodule.database.DatabaseManager')`（对 service 的测试无效）

通用规则：
- `from module import Class` → patch `'被测模块.Class'`
- `import module; module.Class` → patch `'被测模块.module.Class'`
- `from module import func` → patch `'被测模块.func'`

## 测试结构模板

生成的测试遵循以下确切结构：

```python
"""ModuleName 测试"""
import pytest
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path

# 导入被测模块
from mymodule import MyClass
from mymodule.submodule import my_function


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_external_service():
    """外部服务 mock"""
    with patch('mymodule.service.ExternalService') as mock:
        yield mock


@pytest.fixture
def mock_config():
    """配置 mock"""
    with patch('mymodule.service.config') as mock:
        mock.output_dir = Path("/tmp/output")
        mock.get.side_effect = lambda k, d=None: {
            "paths.output_dir": "/tmp/output",
            "paths.data_dir": "/tmp/data",
        }.get(k, d)
        yield mock


# =============================================================================
# 正常路径测试
# =============================================================================

class TestMyClass:
    """MyClass 的测试"""

    def test_method_normal_case(self, mock_external_service, mock_config):
        """正常用例的描述"""
        # Arrange
        instance = MyClass()
        # Act
        result = instance.method("valid_input")
        # Assert
        assert result == expected_value

    def test_method_returns_correct_type(self):
        """返回类型与文档一致"""
        instance = MyClass()
        result = instance.method("input")
        assert isinstance(result, dict)


# =============================================================================
# 边界用例测试
# =============================================================================

    def test_method_with_empty_input(self):
        """优雅处理空字符串"""
        instance = MyClass()
        result = instance.method("")
        assert result is not None

    def test_method_with_none_input(self):
        """优雅处理 None"""
        instance = MyClass()
        result = instance.method(None)
        assert result == fallback_value

    def test_method_with_extreme_values(self):
        """处理边界值"""
        instance = MyClass()
        result = instance.method("x" * 10000)
        assert result is not None


# =============================================================================
# 异常路径测试
# =============================================================================

    def test_method_raises_on_invalid_input(self):
        """对错误输入抛出预期异常"""
        instance = MyClass()
        with pytest.raises(ValueError, match="expected error message"):
            instance.method("invalid")

    def test_method_handles_external_error(self, mock_external_service):
        """优雅处理外部服务错误"""
        mock_external_service.return_value.fetch.side_effect = RuntimeError("Service unavailable")
        instance = MyClass()
        result = instance.method("input")
        assert result is False


# =============================================================================
# 集成风格测试（仍是单元测试，通过 fixture 使用真实数据库）
# =============================================================================

    def test_method_persists_to_database(self, in_memory_db):
        """向数据库写入正确数据"""
        entity = Entity(...)
        in_memory_db.add(entity)
        instance = MyClass()
        result = instance.method("input")
        assert result is True
```

## 优秀测试示例

### 1. 简单函数测试（纯函数，无依赖）

```python
class TestStringUtils:
    """纯函数测试示例"""

    def test_truncate_long_string(self):
        """长字符串截断"""
        result = truncate("Hello, World!", max_length=5)
        assert result == "Hello..."

    def test_truncate_short_string_unchanged(self):
        """短字符串不变"""
        result = truncate("Hi", max_length=10)
        assert result == "Hi"

    def test_truncate_empty_string(self):
        """空字符串返回空字符串"""
        result = truncate("", max_length=5)
        assert result == ""

    def test_truncate_with_ellipsis_length(self):
        """恰好等于最大长度返回原字符串"""
        result = truncate("Hello", max_length=5)
        assert result == "Hello"
```

### 2. 带异常处理的测试

```python
class TestValidator:
    """异常抛出测试示例"""

    def test_raises_on_negative_age(self):
        """负数年龄抛出 ValueError"""
        with pytest.raises(ValueError, match="Age must be non-negative"):
            validate_age(-5)

    def test_raises_on_invalid_email(self):
        """无效邮箱格式抛出 ValueError"""
        with pytest.raises(ValueError, match="Invalid email format"):
            validate_email("not-an-email")

    def test_raises_on_empty_username(self):
        """空用户名抛出 ValueError"""
        with pytest.raises(ValueError, match="Username cannot be empty"):
            validate_username("")
```

### 3. 带 Mock 的测试（外部依赖）

```python
class TestUserService:
    """外部依赖 mock 示例"""

    def test_fetches_user_from_api(self, mock_http_client):
        """成功从 API 获取用户"""
        mock_http_client.get.return_value = {
            "id": 1,
            "name": "Alice",
            "email": "alice@example.com"
        }

        service = UserService(http_client=mock_http_client)
        user = service.get_user(1)

        assert user.name == "Alice"
        mock_http_client.get.assert_called_once_with("/users/1")

    def test_handles_api_timeout(self, mock_http_client):
        """API 超时时返回默认值"""
        mock_http_client.get.side_effect = TimeoutError("Request timed out")

        service = UserService(http_client=mock_http_client)
        user = service.get_user(1)

        assert user is None

    def test_retries_on_transient_error(self, mock_http_client):
        """临时错误自动重试"""
        mock_http_client.get.side_effect = [
            ConnectionError("Temporary failure"),
            {"id": 1, "name": "Bob"}
        ]

        service = UserService(http_client=mock_http_client, max_retries=2)
        user = service.get_user(1)

        assert user.name == "Bob"
        assert mock_http_client.get.call_count == 2
```

### 4. 边界条件测试

```python
class TestCalculator:
    """边界条件测试示例"""

    def test_handles_zero(self):
        """零值边界"""
        result = divide(10, 0)
        assert result is None  # 或抛出异常，视设计而定

    def test_handles_negative_numbers(self):
        """负数计算正确"""
        result = divide(-10, 2)
        assert result == -5

    def test_handles_very_large_numbers(self):
        """极大数不溢出"""
        result = multiply(999999999, 999999999)
        assert result == 999999998000000001

    def test_handles_empty_list(self):
        """空列表返回零"""
        result = sum_list([])
        assert result == 0

    def test_handles_single_element(self):
        """单元素列表正确"""
        result = sum_list([42])
        assert result == 42
```

### 5. 集成风格测试（使用真实数据库）

```python
class TestUserRepository:
    """集成风格测试示例"""

    def test_saves_and_retrieves_user(self, in_memory_db):
        """保存后能正确检索"""
        repo = UserRepository(session=in_memory_db)
        user = User(name="Charlie", email="charlie@example.com")

        repo.save(user)
        retrieved = repo.find_by_email("charlie@example.com")

        assert retrieved is not None
        assert retrieved.name == "Charlie"

    def test_returns_none_for_missing_user(self, in_memory_db):
        """不存在的用户返回 None"""
        repo = UserRepository(session=in_memory_db)
        result = repo.find_by_email("nonexistent@example.com")
        assert result is None

    def test_updates_existing_user(self, in_memory_db):
        """更新用户成功"""
        repo = UserRepository(session=in_memory_db)
        user = User(name="Dave", email="dave@example.com")
        repo.save(user)

        repo.update_email("dave@example.com", "new_dave@example.com")
        updated = repo.find_by_email("new_dave@example.com")

        assert updated is not None
        assert repo.find_by_email("dave@example.com") is None
```

---

## 反模式（必须避免）

### 1. Boolean trap — 严禁使用 `or` 连接断言

**错误：**
```python
def test_result_is_a_or_b():
    assert result == "A" or result == "B"  # Boolean trap!
```

**正确：**
```python
def test_returns_a_when_condition_x():
    # 分别为每种可能结果编写独立测试
    ...

def test_returns_b_when_condition_y():
    ...
```

---

### 2. 空测试体 — 禁止无验证的测试

**错误：**
```python
def test_something():
    try:
        do_something()
    except:
        pass  # 静默异常！
```

**正确：**
```python
def test_raises_on_invalid_input():
    with pytest.raises(ValueError, match="expected message"):
        my_function("invalid")
```

---

### 3. Existence 检查代替行为测试

**错误：**
```python
def test_method_exists():
    assert hasattr(MyClass, 'method')  # 只检查存在性！
```

**正确：**
```python
def test_method_returns_expected_value():
    result = MyClass().method("valid_input")
    assert result == expected_value
```

---

### 4. 过度宽松的断言

**错误：**
```python
def test_response_ok():
    assert response.status_code  # 太宽松！0 也被认为是 True

def test_has_items():
    assert len(items) > 0  # 可以被任意值绕过！
```

**正确：**
```python
def test_response_ok():
    assert response.status_code == 200

def test_has_exactly_five_items():
    assert len(items) == 5
```

---

### 5. 断言中包含预期值

**错误：**
```python
def test_user_name_contains_alice():
    assert "alice" in user.name  # 部分匹配！
```

**正确：**
```python
def test_user_name_is_alice():
    assert user.name == "alice", f"Expected 'alice', got '{user.name}'"
```

---

### 6. try-except 静默处理异常

**错误：**
```python
def test_risky_operation():
    try:
        result = risky_operation()
    except Exception:
        pass  # 掩盖所有异常！
```

**正确：**
```python
def test_risky_operation_succeeds():
    result = risky_operation()
    assert result == expected

# 或验证特定异常
def test_risky_operation_raises_on_invalid_input():
    with pytest.raises(ExpectedError):
        risky_operation("invalid")
```

---

### 7. 未使用的 fixture 或变量

**错误：**
```python
def test_something(unused_fixture):  # fixture 未使用
    data = {"key": "value"}
    # data 未使用
    assert True
```

**正确：**
```python
def test_something():
    data = {"key": "value"}
    assert process(data) == expected
```

---

### 8. 不完整的 Mock

**错误：**
```python
def test_with_incomplete_mock():
    mock_config.output_dir = "/tmp"  # 缺少 get() 方法的 mock
    # 运行时可能 AttributeError
```

**正确：**
```python
def test_with_complete_mock():
    mock_config.get.side_effect = lambda k, d=None: {
        "paths.output_dir": "/tmp",
    }.get(k, d)
```

---

### 9. 在 patch 路径上的常见错误

**错误：**
```python
# 错误：patch 了定义处的路径，而非使用处
with patch('mymodule.database.DatabaseManager'):  # 对 service 测试无效！
    service = MyService()
```

**正确：**
```python
# 正确：patch 在被测模块中的引用位置
with patch('mymodule.service.DatabaseManager'):
    service = MyService()
```

---

### 10. 缺少 setup/teardown 的共享状态

**错误：**
```python
# conftest.py 或测试文件顶部
shared_state = {"count": 0}

def test_increment():
    shared_state["count"] += 1
    assert shared_state["count"] == 1

def test_increment_again():
    # 可能依赖上一个测试的状态！
    assert shared_state["count"] == 2  # 脆弱的测试
```

**正确：**
```python
# 使用 fixture 管理状态
@pytest.fixture
def counter():
    return {"count": 0}

def test_increment(counter):
    counter["count"] += 1
    assert counter["count"] == 1

def test_increment_again(counter):
    counter["count"] += 1
    assert counter["count"] == 2
```

---

## Mock 策略通用指南

### 数据库 Mock

```python
# 正确：在被测模块内部 patch（"使用处"原则）
with patch('mymodule.service.DatabaseManager') as mock_cls:
    mock_instance = mock_cls.return_value
    mock_instance.get_by_id.return_value = mock_entity
    service = MyService()
    service.process("entity-id")
```

### 配置 Mock

```python
# Config 单例 mock
with patch('mymodule.service.config') as mock_cfg:
    mock_cfg.output_dir = Path("/tmp/output")
    mock_cfg.get.side_effect = lambda k, d=None: {
        "paths.output_dir": "/tmp/output",
    }.get(k, d)
    service = MyService()
```

### 外部 API/生成器 Mock

```python
# 外部服务在被测模块中导入并实例化
with patch('mymodule.service.ExternalAPIClient') as mock_client:
    mock_client.return_value.generate.return_value = {
        "title": "Test", "content": "Content..."
    }
    service = MyService()
```

### 文件系统 Mock

```python
def test_handles_missing_file(tmp_path):
    """优雅处理缺失的文件"""
    missing_path = tmp_path / "nonexistent.txt"
    result = read_file(str(missing_path))
    assert result is None
```

---

## 断言质量规则

生成测试时必须遵循以下规则，确保断言精确、不可绕过：

### 1. 使用精确断言（而非模糊断言）
- 正确：`assert response.status_code == 200`
- 错误：`assert response.status_code`（可被数字变异绕过）

### 2. 包含具体值验证
- 正确：`assert len(items) == 5`
- 错误：`assert len(items) > 0`（阈值变异可绕过）

### 3. 断言需包含预期值
- 正确：`assert actual == expected, f"Expected {expected}, got {actual}"`
- 错误：`assert "alice" in user.name`（部分匹配易被绕过）

### 4. 使用严格相等而非包含检查
- 正确：`assert result == 42`
- 错误：`assert "42" in str(result)`

---

## 示例：为 `MyService` 生成测试

### 步骤 1：分析类

```
类：MyService
方法：
  - __init__(db, config, api_client)：初始化依赖
  - process(entity_id) -> bool：处理实体
  - _validate_input(data) -> bool：验证输入

依赖（从 mymodule.service 内部看）：
  - DatabaseManager（from mymodule.database import DatabaseManager）
  - config（from mymodule.config import config）
  - APIClient（from mymodule.external import APIClient）
```

### 步骤 2：识别测试场景

| 方法 | 正常 | 边界 | 异常 |
|------|------|------|------|
| `process` | 找到实体，处理成功 | 实体未找到 | API 调用失败 |
| `_validate_input` | 有效数据通过 | 空数据、None | - |

### 步骤 3：生成的测试文件

```python
"""MyService 测试"""
import pytest
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path

from mymodule.service import MyService


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db_manager():
    with patch('mymodule.service.DatabaseManager') as mock:
        yield mock


@pytest.fixture
def mock_config():
    with patch('mymodule.service.config') as mock:
        mock.output_dir = Path("/tmp/output")
        mock.get.side_effect = lambda k, d=None: {
            "paths.output_dir": "/tmp/output",
        }.get(k, d)
        yield mock


@pytest.fixture
def mock_api_client():
    with patch('mymodule.service.APIClient') as mock:
        yield mock


# =============================================================================
# 测试 process
# =============================================================================

class TestMyServiceProcess:
    """MyService.process 方法的测试"""

    def test_process_success(self, mock_db_manager, mock_config, mock_api_client):
        """所有依赖正常时处理成功"""
        mock_entity = MagicMock()
        mock_entity.id = "entity-123"
        mock_entity.name = "Test Entity"

        mock_db_manager.return_value.get_by_id.return_value = mock_entity
        mock_api_client.return_value.submit.return_value = True

        service = MyService(
            db=mock_db_manager.return_value,
            config=mock_config,
            api_client=mock_api_client.return_value
        )
        result = service.process("entity-123")

        assert result is True
        mock_api_client.return_value.submit.assert_called_once()

    def test_process_returns_false_when_entity_not_found(self, mock_db_manager, mock_config):
        """实体不存在时返回 False"""
        mock_db_manager.return_value.get_by_id.return_value = None

        service = MyService(
            db=mock_db_manager.return_value,
            config=mock_config,
            api_client=mock_api_client.return_value
        )
        result = service.process("nonexistent-id")

        assert result is False

    def test_process_handles_api_error(self, mock_db_manager, mock_config, mock_api_client):
        """API 错误时返回 False"""
        mock_entity = MagicMock()
        mock_entity.id = "entity-123"
        mock_db_manager.return_value.get_by_id.return_value = mock_entity
        mock_api_client.return_value.submit.side_effect = RuntimeError("API Error")

        service = MyService(
            db=mock_db_manager.return_value,
            config=mock_config,
            api_client=mock_api_client.return_value
        )
        result = service.process("entity-123")

        assert result is False


# =============================================================================
# 测试 _validate_input
# =============================================================================

class TestMyServiceValidateInput:
    """MyService._validate_input 方法的测试"""

    def test_valid_input_returns_true(self):
        """有效输入返回 True"""
        service = MyService()
        result = service._validate_input({"name": "Valid", "value": 42})
        assert result is True

    def test_empty_input_returns_false(self):
        """空输入返回 False"""
        service = MyService()
        result = service._validate_input({})
        assert result is False

    def test_none_input_returns_false(self):
        """None 输入返回 False"""
        service = MyService()
        result = service._validate_input(None)
        assert result is False
```

---

## 输出

Skill 将完整的测试文件写入 `tests/unit/` 下的适当位置：
- **已有测试文件时**：追加新的测试函数（不覆盖现有内容）
- **无测试文件时**：创建 `tests/unit/test_<module_name>.py`

报告内容：
- 创建/修改的文件路径
- 新增的测试类和测试函数数量
- 关于未覆盖分支的任何说明（需要手动测试或集成测试）

---

## 质量检查清单

生成后验证：
- [ ] 测试文件保存到 `tests/unit/test_<module_name>.py`
- [ ] 测试可独立运行：`pytest tests/unit/test_xxx.py -v`
- [ ] 使用 `conftest.py` fixtures（`in_memory_db`、`sample_entity`、`reset_db_engine(autouse=True)`）
- [ ] 所有外部依赖都已 mock（patch 路径遵循"使用处"原则）
- [ ] **遵循 AAA 模式（Arrange / Act / Assert）**
- [ ] 添加描述性断言消息，提高失败时的可读性
- [ ] 测试覆盖：正常路径、边界用例（空值、None、极端值）、异常
- [ ] 路径处理在 Windows 上正常工作（使用 `Path` 或 `os.path.join`）
- [ ] 断言遵循"断言质量规则"（精确值、严格相等、包含预期值）
- [ ] **没有使用反模式（检查上述 10 种禁止模式）**

---

## 注意事项

- 当模块没有现有测试时，始终在 `tests/unit/test_<module_name>.py` 创建文件
- 当模块已有测试时，追加新的测试函数（不要覆盖现有测试）
- 对于子包中的模块（例如 `mymodule/submodule/`），测试文件名用 `test_<module_name>.py`
- 对可选依赖使用 `pytest.importorskip` 而不是跳过整个测试
- 保持测试函数简短（50 行以内）。将长测试拆分为辅助方法或单独的测试函数
- 不要手动操作 `sys.path`——pytest 会自动处理导入路径
- **优先测试行为，而非实现细节**
- **测试应该相互独立，不依赖执行顺序**

# Trae 项目规则配置

## 执行环境

请在执行 Python 命令时使用以下 Python 解释器：
- 路径：`D:/project/bookfile_bat/.venv/Scripts/python.exe`

## 执行规则

1. **Python 命令**：运行 Python 命令时，必须使用完整路径 `D:/project/bookfile_bat/.venv/Scripts/python.exe`
2. **工作目录**：切换到项目目录 `D:/project/bookfile_bat` 后执行命令
3. **编码设置**：确保输出编码为 UTF-8

## 示例

执行命令时：
- 错误：`python -m automation.main process 58d61dd3`
- 正确：`D:/project/bookfile_bat/.venv/Scripts/python.exe -m automation.main process 58d61dd3`

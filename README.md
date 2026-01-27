# 图书文件处理脚本

## 功能介绍

本脚本用于处理图书文件，主要提供以下功能：

1. **文件重命名**：在文件名的第二个"--"处截断，删除后面的部分
2. **文件分组**：将前缀相同的文件移动到同一个文件夹中
3. **语言检测**：检测PDF和EPUB文件的语言，为纯英文书添加"英文原版-"前缀，为中英混合书添加"中英对照-"前缀

## 安装依赖

脚本需要以下Python库：

```bash
pip install PyPDF2 ebooklib
```

- `PyPDF2`：用于PDF文件文本提取
- `ebooklib`：用于EPUB文件文本提取

如果未安装相关库，脚本会显示警告并跳过相应文件，不影响其他功能。

## 使用方法

### 基本用法

```bash
# 默认处理当前目录下的file文件夹
python process_files.py

# 指定要处理的目录
python process_files.py /path/to/your/folder
```

### 操作模式

```bash
# 重命名并分组模式（默认）
python process_files.py --mode=rename

# 语言检测模式
python process_files.py --mode=lang

# 两者都执行模式
python process_files.py --mode=both
```

### 高级选项

```bash
# 调整相似文件判断的页数（仅语言检测模式有效）
python process_files.py --mode=lang --pages=3

# 干运行模式（预览操作）
python process_files.py --dry-run

# 组合使用
python process_files.py /path/to/folder --mode=both --pages=4 --dry-run
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `directory` | 要处理的目录 | `file` |
| `--mode` | 处理模式：`rename`=重命名分组, `lang`=语言检测加前缀, `both`=两者都执行 | `rename` |
| `--pages` | 检测语言时分析的文本页面数（自动跳过非文本页面） | `2` |
| `--dry-run` | 干运行模式，只显示将要执行的操作而不实际执行 | `False` |

## 工作原理

### 文件重命名

脚本会在文件名的第二个"--"处截断，删除后面的部分，保留原始扩展名。例如：

```
原始文件名：Badass habits _ cultivate the awareness, boundaries, and -- Jen Sincero; cloudLibrary -- Penguin Random House LLC.pdf
重命名后：Badass habits _ cultivate the awareness, boundaries, and -- Jen Sincero; cloudLibrary.pdf
```

### 文件分组

脚本会根据文件名中第一个"_"前的部分判断文件是否相似，将相似文件移动到同一个文件夹中。例如：

- `Big Magic _ Creative Living Beyond Fear -- Elizabeth Gilbert.pdf`
- `Big magic_ creative living beyond fear -- Elizabeth Gilbert.epub`

这两个文件会被移动到同一个文件夹中，因为它们的前缀都是"Big Magic"（忽略大小写）。

### 语言检测

脚本会：
1. 跳过非文本页面（如封面、版权页等）
2. 提取PDF/EPUB文件的前几页文本
3. 检测文本中是否包含中文字符
4. 根据检测结果添加相应前缀：
   - 纯英文书：添加"英文原版-"前缀
   - 中英混合书：添加"中英对照-"前缀

## 示例

### 示例1：处理默认目录

```bash
python process_files.py --mode=both
```

处理当前目录下`file`文件夹中的所有文件，执行重命名分组和语言检测功能。

### 示例2：处理指定文件夹

```bash
python process_files.py d:\books\english --mode=lang
```

处理`d:\books\english`目录中的所有文件，仅执行语言检测功能。

### 示例3：干运行模式

```bash
python process_files.py --mode=both --dry-run
```

预览将要执行的操作，不实际修改文件。

## 注意事项

1. **文件命名格式**：脚本假设文件名为"书名 -- 作者 -- 其他信息"的格式，会在第二个"--"处截断。

2. **语言检测**：
   - 仅支持PDF和EPUB文件
   - 会自动跳过非文本页面（如封面、版权页等）
   - 基于文本内容检测语言，可能对图片扫描版PDF不准确

3. **文件分组**：
   - 基于文件名中第一个"_"前的部分判断文件是否相似
   - 忽略大小写和特殊字符

4. **执行顺序**：
   - 在`both`模式下，会先执行重命名分组，再执行语言检测
   - 语言检测会保留重命名后的结果

5. **兼容性**：
   - 脚本支持Windows、Linux和macOS
   - 需要Python 3.6或更高版本

## 故障排除

### 1. 依赖安装失败

如果安装依赖时遇到问题，可以尝试使用国内镜像：

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple PyPDF2 ebooklib
```

### 2. 语言检测失败

如果语言检测失败，可能是因为：
- 文件不是PDF或EPUB格式
- 文件是图片扫描版PDF，无法提取文本
- 依赖库未正确安装

### 3. 文件分组不正确

如果文件分组不正确，可能是因为：
- 文件名格式不符合预期
- 文件名中没有"_"字符

## 许可证

本脚本采用MIT许可证。
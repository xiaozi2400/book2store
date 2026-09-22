---
name: auto-commit
description: use when user explicitly asks to commit code like "提交git", "提交", "提交代码"  or similar phrases indicating a commit request
---

# Auto Commit Skill



## Execution Protocol (Strict Order)

### Step 1: 检查改动
- **Action**: Run `git status` and `git diff --stat`
- **Output**: 显示改动文件列表和统计
- **Checkpoint**: 必须看到`git status` and `git diff --stat`的输出才能继续，**禁止仅凭记忆或假设继续**

### Step 2: 生成提交日志
- **Prerequisite**: Step 1 完成
- **Action**: 基于改动内容生成 Conventional Commits 格式提交信息
- **Output**: 提交日志文本（如 `fix: resolve null pointer exception in auth module`）
- **Checkpoint**: 必须生成日志文本后才能继续，**禁止跳过此步骤**

### Step 3: 展示完整摘要
- **Prerequisite**: Step 1 和 Step 2 完成
- **Action**: 显示以下全部内容：
  1. 改动文件列表
  2. diff 统计摘要
  3. 提交日志预览
- **Checkpoint**: 必须展示全部三项内容后才能进入批准，**禁止直接跳到批准提示**

### Step 4: 等待批准
- **Prerequisite**: Step 3 全部完成
- **Action**: 显示 `提交？ [Y/n]`
- **Constraint**: 
  - **禁止**在 Step 3 完成前显示此提示
  - 如果用户选择 n，终止流程，不执行提交
- **Checkpoint**: 用户必须明确选择 Y 才能继续

### Step 5: 执行提交
- **Prerequisite**: Step 4 用户选择 Y
- **Action**: 
  1. `git add .`
  2. `git commit -m "<Step 2 生成的日志>"`
- **Output**: 成功消息 + commit hash

### Step 6: 显示结果
- **Prerequisite**: Step 5 完成
- **Action**: 显示完整提交结果

## Edge Cases

| 情况 | 处理 |
|------|------|
| 无改动 | 显示"暂无需要提交的内容"，终止流程 |
| 用户选择 n | 显示"已取消提交"，终止流程 |
| `git commit` 失败 | 显示错误信息，保留改动 |

## Notes

- Commit message type options: feat, fix, chore, refactor, docs, test, style, perf, ci
- 提交日志应简洁，格式：`type: description`，日志内容使用中文

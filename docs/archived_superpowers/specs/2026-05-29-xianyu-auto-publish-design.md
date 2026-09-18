# 闲鱼自动发布功能设计

## 背景

电子书处理系统已完成文案生成和元数据导出（`metadata.json`），现在需要实现通过 Playwright 自动化操作闲鱼卖家中心，完成商品自动发布。

## 目标

1. 根据 `metadata.json` 中的数据，自动填写闲鱼发布页表单
2. 上传封面图、设置价格、SKU等
3. 发布成功后，记录商品链接到数据库和 `metadata.json`

## 输入数据来源

优先从以下位置读取数据（按优先级排序）：

| 数据项 | 来源 | 说明 |
|-------|------|------|
| 宝贝描述 | `metadata.json.copywriting.xianyu.description` | 闲鱼自动取前20字符当标题 |
| SKU列表 | `config.yaml.sku` | 规格名称、价格、包含文件 |
| 图片 | `{base_name}_metadata/` 目录 | `cover.jpg`、`toc_preview.jpg` |
| 库存 | `config.yaml.xianyu.inventory` | 全局配置值 |
| 宝贝所在地 | `config.yaml.xianyu.location` | 全局配置值 |
| 发货方式 | `config.yaml.xianyu.shipping` | 全局配置值 |

## 发布流程

```
1. 启动浏览器，访问闲鱼卖家中心首页
   URL: https://seller.goofish.com/

2. 登录验证
   - 检查是否已登录（通过 cookie）
   - 如未登录，显示二维码等待扫码
   - 登录成功后保存 cookie 供后续使用

3. 进入发布页
   - 点击左侧「商品」菜单
   - 点击「商品发布」进入发布页面

4. 填写宝贝描述
   - 定位描述输入框
   - 填入 `xianyu.description` 内容

5. 上传宝贝图片
   - 定位图片上传区域
   - 依次上传 `cover.jpg`、`toc_preview.jpg`（存在的话）

6. 设置商品规格（SKU）
   - 点击「+ 添加规格类型」按钮（最多2个）
   - 对每个 SKU：
     - 填写规格名称（如「纯英文原版」）
     - 填写价格（从 config 读）
     - 填写库存（从 config 读）

7. 填写基础信息
   - 原价 = 价格（和现价一样）
   - 库存 = 全局配置值
   - 宝贝所在地 = 全局配置值
   - 发货设置 = 全局配置值（如「包邮」）

8. 点击发布
   - 定位发布按钮并点击
   - 等待发布成功，获取商品 URL

9. 保存发布结果
   - 更新数据库：`BookOutput.xianyu_listing_url`、`xianyu_product_id`
   - 更新 `metadata.json.publish.xianyu_listing_url`
   - 更新状态为「已发布」
```

## 配置变更

在 `config.yaml` 中新增/完善 `xianyu` 配置块：

```yaml
xianyu:
  login_method: "qr_code"
  base_url: "https://seller.goofish.com"
  timeout: 30
  auto_retry: true
  # 新增配置项：
  inventory: 1               # 默认库存
  location: "深圳北站"       # 宝贝所在地
  shipping: "包邮"           # 发货方式
```

## metadata.json 扩展

在 `metadata.json.publish` 中新增字段：

```json
{
  "publish": {
    "pan_link_sku1": null,
    "pan_link_sku2": null,
    "pan_code": null,
    "xianyu_listing_url": null  // 新增：闲鱼商品链接
  }
}
```

## 模块设计

### 1. 修改：`automation/config.py`

新增配置项读取方法，支持读取 `xianyu.inventory`、`xianyu.location`、`xianyu.shipping`。

### 2. 重构：`automation/xianyu_publisher.py`

完全重构现有类，实现真实的 Playwright 自动化：

| 方法 | 说明 |
|------|------|
| `__init__()` | 初始化，加载配置，准备数据库连接 |
| `publish(book_id)` | 主入口：从 `metadata.json` 读数据，执行发布 |
| `_load_metadata(book_id)` | 定位并加载 `{base_name}_metadata/metadata.json` |
| `_start_browser()` | 启动 Playwright，加载 cookie（如有） |
| `_login()` | 检查登录状态，如需扫码则等待 |
| `_navigate_to_publish()` | 点击「商品」→「商品发布」进入发布页 |
| `_fill_description(description)` | 填写宝贝描述 |
| `_upload_images(meta_dir)` | 上传封面和目录图 |
| `_setup_skus(sku_list)` | 按配置设置商品规格 |
| `_fill_basic_info()` | 填库存、所在地、发货方式 |
| `_submit_and_get_url()` | 点击发布，获取商品链接 |
| `_save_result(book_id, listing_url)` | 写入数据库和 metadata.json |
| `_close()` | 保存 cookie，关闭浏览器 |

### 3. 修改：`automation/metadata_writer.py`

新增 `update_publish_info(book_id, xianyu_listing_url)` 方法，用于更新 `metadata.json` 中的发布链接。

### 4. 可选：修改：`automation/main.py`

在 `publish` 命令中，调用新的 `xianyu_publisher.publish()` 而非旧的实现。

## 技术细节

### Cookie 持久化

- 首次登录成功后，将 Playwright 的 context storageState 保存到 `data/xianyu_cookie.json`
- 下次启动时自动加载，避免重复扫码

### 错误处理

| 错误场景 | 处理策略 |
|---------|---------|
| 元素未找到 | 重试3次，每次间隔2秒，失败则抛出异常 |
| 登录超时 | 等待30秒，超时提示用户重新扫码 |
| 发布失败 | 截图保存到 `logs/` 目录，记录错误信息到数据库 |

### 选择器策略

由于闲鱼是动态 JS 渲染，使用 Playwright 的：
- `locator()` + 可见性等待
- 优先用 `text=xxx` 和 `role=xxx`，其次用类名选择器
- 尽量避免脆弱的绝对 XPath

## 变更文件清单

| 文件 | 操作 |
|------|------|
| `config.yaml` | 修改（新增 xianyu 配置项） |
| `automation/config.py` | 修改（新增配置读取方法） |
| `automation/xianyu_publisher.py` | 重构（完全重写实现） |
| `automation/metadata_writer.py` | 修改（新增 update_publish_info） |
| `automation/main.py` | 修改（可选：publish 命令调用新实现） |

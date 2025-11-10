# Unpaywall API 测试报告

## 测试概述

本次测试针对 Unpaywall API，查询最近7天论文的开放获取状态，验证系统对 Unpaywall API 的集成能力。

**测试时间**: 2025-11-10  
**测试范围**: 最近7天有DOI的论文  
**测试数量**: 4篇论文

---

## 发现的问题与修复

### 1. 邮箱验证问题

**问题**：
- Unpaywall API 不接受 `test@example.com` 等测试邮箱
- 返回 422 错误：`Please use your own email address in API calls`

**修复**：
- 实现环境变量支持，从 `.env` 文件或环境变量读取邮箱
- 添加友好的错误提示
- 更新配置系统，支持 `MAILTO` 和 `PAPERGAZER_MAILTO` 两种格式

### 2. 环境变量配置

**实现**：
- 修改 `papergazer/config.py`，支持从环境变量读取敏感信息
- 环境变量优先级高于配置文件
- 创建 `.env.example` 示例文件

---

## 测试结果

### 测试执行

**执行命令**: `python scripts/test_unpaywall_query.py 7 10`

**结果**:
- ✅ 成功查询 Unpaywall API
- ✅ 查询了4篇论文的开放获取状态
- ✅ 无查询错误

### 数据统计

- **总查询数**: 4篇
- **✅ 开放获取**: 3篇 (75%)
- **❌ 非开放获取**: 1篇 (25%)
- **⚠️ 查询错误**: 0篇
- **💾 已保存到数据库**: 4条记录
- **数据库验证**: 3条Unpaywall OA记录已保存

### 查询结果示例

| 标题 | DOI | OA状态 | OA位置 |
|------|-----|--------|--------|
| Quasi-constant time gap | 10.1029/2025EA004321 | ✅ 是 | https://onlinelibrary.wiley.com/... |
| SolarCrossForm | 10.1109/TSTE.2025.3624044 | ❌ 否 | 无 |
| Coronal hole picoflare jets | 10.1051/0004-6361/202452737 | ✅ 是 | http://purl.org/... |
| Ionospheric responses | 10.1016/j.asr.2025.10.107 | ✅ 是 | https://arxiv.org/pdf/... |

---

## 环境变量配置

### 配置方式

1. **使用 .env 文件（推荐）**：
   ```bash
   cp .env.example .env
   # 编辑 .env，设置 MAILTO=your-email@domain.com
   ```

2. **直接设置环境变量**：
   ```bash
   export MAILTO=your-email@domain.com
   ```

3. **在配置文件中设置**（优先级最低）：
   ```yaml
   mailto: "your-email@domain.com"
   ```

### 支持的格式

- `MAILTO` (不带前缀)
- `PAPERGAZER_MAILTO` (带前缀，pydantic-settings 自动处理)

### 优先级

1. 环境变量（最高优先级）
2. 配置文件

---

## 数据库保存

### 保存的字段

Unpaywall API 查询结果会保存到数据库的以下字段：

- **`is_oa`**: 布尔值，表示是否为开放获取
- **`oa_source`**: 字符串，保存为 `"unpaywall"`
- **`oa_pdf_url`**: 文本，保存PDF URL（优先）或landing page URL
- **`abstract_jats`**: 文本，如果数据库中没有摘要，会从Crossref获取并保存（特别是非OA论文）

### 保存逻辑

```python
# 更新数据库中的OA信息
db_item.is_oa = oa_info.is_oa
if oa_info.is_oa and oa_info.best_oa_location:
    db_item.oa_source = "unpaywall"
    db_item.oa_pdf_url = (
        oa_info.best_oa_location.get("url_for_pdf")
        or oa_info.best_oa_location.get("url_for_landing_page")
        or oa_info.best_oa_location.get("url")
    )
else:
    # 如果不是OA，清除OA相关字段
    db_item.oa_source = None
    db_item.oa_pdf_url = None

# 如果数据库中没有摘要，尝试从Crossref获取（特别是非OA论文）
if not db_item.abstract_jats or db_item.abstract_jats.strip() == "":
    work = await fetch_crossref_by_doi(item.doi, config.mailto)
    if work and work.abstract:
        db_item.abstract_jats = work.abstract
```

## 代码改进

### 1. 配置系统增强

```python
# 支持从环境变量读取
mailto_from_env = os.getenv("MAILTO") or os.getenv("PAPERGAZER_MAILTO")
if mailto_from_env:
    settings.mailto = mailto_from_env
```

### 2. 错误处理改进

```python
# 处理422错误（邮箱验证失败）
if response.status_code == 422:
    error_data = response.json()
    error_msg = error_data.get("message", "Unpaywall API 邮箱验证失败")
    raise httpx.HTTPStatusError(...)
```

### 3. 友好的错误提示

```python
if "422" in error_msg or "email" in error_msg.lower():
    error_msg = "邮箱验证失败（请使用真实邮箱）"
```

---

## 测试脚本

创建了 `scripts/test_unpaywall_query.py` 测试脚本，支持：
- 查询最近N天有DOI的论文
- 批量查询 Unpaywall API
- 显示开放获取状态和位置
- 显示统计信息

**使用方式**：
```bash
# 查询最近7天的论文（最多20篇）
python scripts/test_unpaywall_query.py 7

# 查询最近7天的论文（最多10篇）
python scripts/test_unpaywall_query.py 7 10
```

---

## 注意事项

1. **邮箱要求**: Unpaywall API 要求使用真实邮箱地址，不能使用测试邮箱
2. **请求频率**: 建议在请求之间添加小延迟（0.5秒），避免请求过快
3. **数据来源**: 测试脚本从数据库中查询有DOI的论文，需要先运行 arXiv 或 Crossref 巡检

---

## 相关文件

- 测试脚本: `scripts/test_unpaywall_query.py`
- 数据源实现: `papergazer/sources/unpaywall.py`
- 配置系统: `papergazer/config.py`
- 环境变量示例: `.env.example`
- 环境变量文档: `docs/ENVIRONMENT_VARIABLES.md`

---

**测试完成时间**: 2025-11-10  
**测试状态**: ✅ 成功


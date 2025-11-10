# arXiv论文查询测试报告

## 测试概述

本次测试针对arXiv预印本平台，查询近7天的论文信息，验证系统对arXiv API的集成能力。

**测试时间**: 2025-11-10  
**测试范围**: eess.SP, physics.space-ph  
**测试天数**: 7天

---

## 发现的问题与修复

### 1. HTTPS重定向问题

**问题**：
- arXiv API从HTTP重定向到HTTPS
- 使用`http://export.arxiv.org/api/query`会返回301重定向错误

**修复**：
- 将URL改为`https://export.arxiv.org/api/query`
- 添加`follow_redirects=True`到httpx客户端

### 2. 查询字符串格式问题

**问题**：
- 使用`+OR+`连接多个分类时，arXiv API返回0条结果
- 例如：`cat:eess.SP+OR+cat:physics.space-ph` → 0 entries

**修复**：
- 改用空格分隔的`OR`：`cat:eess.SP OR cat:physics.space-ph`
- 修改查询字符串构建逻辑

**修改前**：
```python
query = "+OR+".join([f"cat:{cat}" for cat in categories])
```

**修改后**：
```python
if len(categories) == 1:
    query = f"cat:{categories[0]}"
else:
    query = " OR ".join([f"cat:{cat}" for cat in categories])
```

### 3. 日志记录缺失

**问题**：
- `arxiv.py`中缺少logger导入
- 无法记录调试信息

**修复**：
- 添加`import logging`
- 添加`logger = logging.getLogger(__name__)`
- 添加空结果警告日志

---

## 测试结果

### 测试执行

**执行命令**: `python scripts/test_arxiv_query.py 7`

**结果**:
- ✅ 成功查询arXiv API
- ✅ 获取了50条记录（符合配置的max_results）
- ✅ 成功存储到数据库
- ✅ 显示前20条记录

### 数据统计

- **获取记录数**: 50条
- **过滤记录数**: 0条（所有记录都在检查点之后）
- **处理记录数**: 50条
- **数据库总数**: 50条

### 查询到的论文示例

- Bayesian Self-Calibration and Parametric Channel Estimation (2025-11-07更新)
- Lossy Beyond Diagonal Reconfigurable Intelligent Surface (2025-11-07更新)
- Quasi-constant time gap in multiple rings of elves (2025-11-07发布)
- Location-Informed Interference Suppression (2025-11-07发布)

---

## 测试脚本

创建了`scripts/test_arxiv_query.py`测试脚本，支持：
- 查询指定天数的arXiv论文
- 显示论文详细信息（标题、ID、日期、作者等）
- 显示统计信息

**使用方式**：
```bash
# 查询近7天的arXiv论文
python scripts/test_arxiv_query.py 7

# 查询近5天的arXiv论文
python scripts/test_arxiv_query.py 5
```

---

## 代码改进

### 1. arXiv API URL更新

```python
# 修改前
ARXIV_API_URL = "http://export.arxiv.org/api/query"

# 修改后
ARXIV_API_URL = "https://export.arxiv.org/api/query"
```

### 2. 查询字符串构建

```python
# 修改前
query = "+OR+".join([f"cat:{cat}" for cat in categories])

# 修改后
if len(categories) == 1:
    query = f"cat:{categories[0]}"
else:
    query = " OR ".join([f"cat:{cat}" for cat in categories])
```

### 3. 添加日志支持

```python
import logging
logger = logging.getLogger(__name__)

# 添加空结果警告
if len(feed.entries) == 0:
    logger.warning(f"arXiv API 返回空结果，响应长度: {len(response.text)}")
```

### 4. 改进调试信息

在`ingest_arxiv`中添加了统计信息：
```python
logger.info(f"arXiv 巡检完成，获取 {total_fetched} 条，过滤 {filtered_count} 条，处理 {count} 条记录")
```

---

## 与Crossref的对比

| 特性 | arXiv | Crossref |
|------|-------|----------|
| API类型 | Atom Feed | REST API |
| 分页方式 | start参数 | cursor分页 |
| 时间过滤 | 基于updated日期 | 基于published日期 |
| 查询限制 | 每片最多2000条 | 每页最多1000条 |
| 排序方式 | lastUpdatedDate | issued/published |

---

## 注意事项

1. **时间过滤**：
   - arXiv使用`updated`日期进行过滤
   - 这是合理的，因为预印本平台主要关注更新日期

2. **查询语法**：
   - arXiv API使用空格分隔的`OR`
   - 多个分类时使用：`cat:cat1 OR cat:cat2`

3. **请求间隔**：
   - 建议保持3秒以上的请求间隔
   - 遵守arXiv API的使用规范

4. **数据量**：
   - arXiv每天有大量新论文
   - 建议合理设置`max_results`和检查点

---

## 相关文件

- 测试脚本: `scripts/test_arxiv_query.py`
- 数据源实现: `papergazer/sources/arxiv.py`
- 巡检逻辑: `papergazer/core/ingest.py`
- 测试配置: `configs/config.test.yaml`

---

**测试完成时间**: 2025-11-10  
**测试状态**: ✅ 成功


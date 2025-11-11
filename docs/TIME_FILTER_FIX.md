# 时间过滤问题修复总结

## 问题描述

在项目的多个模块中，使用 `PaperItem.updated_date >= cutoff_date` 进行时间过滤时，会导致 **Crossref 等数据源的论文被完全排除**，因为这些数据源的 `updated_date` 字段为 `None`。

### 受影响的功能

1. **论文分析** (`analyze_papers.py`): venues、authors、abstracts、OA 状态分析
2. **论文下载** (`download.py`): arXiv 和 OA 论文下载
3. **论文查询** (`query.py`): Unpaywall OA 状态查询

## 根本原因

Crossref API 返回的论文数据没有 `updated_date` 字段，导致数据库中该字段为 `None`。使用 SQL 过滤时：

```python
# 旧代码（有问题）
query.filter(PaperItem.updated_date >= cutoff_date)
```

当 `updated_date` 为 `None` 时，比较结果为 `NULL`，这些记录被排除在结果集之外。

### 影响统计

修复前：
- 最近 30 天论文数: **210 篇**（仅 arXiv）

修复后：
- 最近 30 天论文数: **7597 篇**（arXiv 210 + Crossref 7387）

## 解决方案

### 1. 创建统一的时间过滤函数

创建 `papergazer/utils/db_filters.py` 模块，提供 `get_effective_date_filter()` 函数：

```python
def get_effective_date_filter(cutoff_date: datetime):
    """
    获取有效的日期过滤条件
    
    优先使用 updated_date，如果为 None 则使用 published_date，
    再为 None 则使用 ingested_at
    """
    effective_date = func.coalesce(
        PaperItem.updated_date,
        func.datetime(PaperItem.published_date),
        PaperItem.ingested_at
    )
    return effective_date >= cutoff_date
```

### 2. 修复的文件

| 文件 | 修复数量 | 说明 |
|------|---------|------|
| `papergazer/utils/analyze.py` | 5 处 | 分析功能（作者、摘要、OA、期刊、论文列表） |
| `papergazer/utils/download.py` | 2 处 | arXiv 和 OA 论文下载 |
| `papergazer/utils/query.py` | 1 处 | Unpaywall OA 状态查询 |

### 3. 使用示例

**旧代码**:
```python
cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
query = session.query(PaperItem).filter(PaperItem.updated_date >= cutoff_date)
```

**新代码**:
```python
from papergazer.utils.db_filters import get_effective_date_filter

cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
query = session.query(PaperItem).filter(get_effective_date_filter(cutoff_date))
```

## 优先级策略

时间字段选择优先级（从高到低）：

1. **`updated_date`** (datetime): 论文更新时间（arXiv 有此字段）
2. **`published_date`** (date): 论文发表日期（所有数据源都有）
3. **`ingested_at`** (datetime): 数据入库时间（所有记录都有）

### SQL 实现

使用 SQLAlchemy 的 `coalesce` 函数，返回第一个非 `NULL` 值：

```sql
COALESCE(
    updated_date,
    datetime(published_date),  -- 将 Date 转换为 DateTime
    ingested_at
) >= cutoff_date
```

## 验证测试

### 测试脚本

```python
from papergazer.utils.db_filters import get_effective_date_filter
from datetime import datetime, timedelta, timezone

cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
query = session.query(PaperItem).filter(get_effective_date_filter(cutoff_date))
total_count = query.count()

print(f'最近 30 天的论文总数: {total_count}')
```

### 测试结果

```
最近 30 天的论文总数: 7597

按数据源统计:
  arxiv: 210 篇
  crossref: 7387 篇

✅ 所有时间过滤问题已修复！
```

## 相关问题修复

### 1. Rich 表格显示问题

**问题**: `arXiv [cs.AI]` 中的方括号被 Rich 解释为样式标记，导致显示为 `arXiv`

**解决**: 使用 `Text` 对象避免样式解析

```python
from rich.text import Text

venue_text = Text(venue_info["venue"], style="yellow")
table.add_row(str(idx), venue_text, str(count), sources_str)
```

### 2. arXiv 论文 venue 缺失

**问题**: arXiv 论文的 `venue` 字段为空

**解决**: 在 `ArxivEntry.to_metadata()` 中使用主分类作为 venue

```python
if self.categories:
    venue = f"arXiv [{self.categories[0]}]"
```

## 注意事项

1. **数据一致性**: 旧数据可能仍有 `updated_date = None`，但不影响查询
2. **性能**: `coalesce` 函数在数据库层面执行，性能良好
3. **向后兼容**: 修复不影响已有数据，完全向后兼容

## 后续改进建议

- [ ] 考虑在数据入库时自动填充 `updated_date`（使用 `published_date` 或 `ingested_at`）
- [ ] 添加单元测试验证各种数据源的时间过滤
- [ ] 文档化各数据源的时间字段差异

## 相关文档

- [数据库设计](DATABASE_SCHEMA.md)
- [分析功能](ANALYZE_USAGE.md)
- [下载功能](DOWNLOAD_USAGE.md)
- [查询功能](QUERY_USAGE.md)


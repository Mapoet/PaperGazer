# Crossref API 游标分页问题分析

## 问题描述

在巡检Crossref API时，发现每次只获取了固定的2000条记录，即使API返回的总记录数远大于此（例如74728条）。

## 问题根源

### 现象
- Crossref API返回的总记录数：74728条
- 实际获取的记录数：2000条（2页，每页1000条）
- 游标分页在第二次请求后退出

### 原因分析

1. **游标分页机制**：
   - 第一次请求：`cursor=*`，返回1000条记录
   - 第二次请求：使用新的`cursor`，返回1000条记录
   - 第三次请求：`next-cursor`与当前`cursor`相同，退出循环

2. **Crossref API的限制**：
   - 当使用游标分页时，如果结果集很大，API可能会在某些情况下返回相同的`next-cursor`
   - 即使还有更多数据，API也可能返回相同的游标，导致分页提前结束
   - 这是Crossref API游标分页的已知限制

## 当前解决方案

### 1. 改进的游标分页逻辑

在 `papergazer/sources/crossref.py` 中实现了以下改进：

- **详细日志记录**：记录每次请求的游标、返回记录数、API总记录数
- **智能退出判断**：
  - 如果返回记录数少于请求数（`rows`），说明确实没有更多数据，正常退出
  - 如果返回满页数据但`next-cursor`相同，记录警告并退出，避免无限循环

### 2. 增量查询策略

由于使用了`from-index-date`参数进行增量查询：
- 每次巡检只查询自上次检查点以来的新数据
- 即使本次只获取了部分数据，下次巡检时会继续获取剩余数据
- 通过定期巡检，可以逐步获取所有数据

## 影响分析

### 优点
1. **避免无限循环**：当`next-cursor`相同时，及时退出，避免程序卡死
2. **增量获取**：通过定期巡检，可以逐步获取所有数据
3. **稳定性**：不会因为API限制导致程序异常

### 缺点
1. **获取速度慢**：需要多次巡检才能获取所有数据
2. **数据延迟**：新数据可能需要多次巡检才能完全获取

## 可能的改进方案

### 方案1：使用Offset分页作为备选

当游标分页遇到限制时，可以尝试使用offset分页：

```python
# 当游标分页失败时，使用offset分页
if next_cursor == current_cursor and items_count == rows:
    # 尝试使用offset分页
    offset = iteration * rows
    params.pop("cursor", None)
    params["offset"] = offset
    # 继续请求...
```

**缺点**：
- Crossref API不推荐使用offset分页，性能较差
- 对于大数据集，offset分页可能更慢

### 方案2：分批查询

将大时间范围拆分为多个小时间范围，分别查询：

```python
# 将7天拆分为7个1天范围
for day in range(7):
    since_date = start_date + timedelta(days=day)
    # 查询当天的数据...
```

**优点**：
- 每个查询的结果集较小，游标分页更稳定
- 可以并行查询多个时间范围

**缺点**：
- 增加了API请求次数
- 需要更复杂的逻辑

### 方案3：接受限制，依赖增量查询

当前方案：接受API的限制，依赖增量查询逐步获取数据。

**优点**：
- 实现简单
- 稳定可靠
- 符合API推荐的使用方式

**缺点**：
- 获取速度较慢

## 建议

1. **短期**：保持当前方案，接受API限制，依赖增量查询
2. **中期**：考虑实现方案2（分批查询），提高获取速度
3. **长期**：关注Crossref API的更新，看是否有更好的分页机制

## 相关文件

- 数据源实现：`papergazer/sources/crossref.py`
- 巡检逻辑：`papergazer/core/ingest.py`
- 测试脚本：`scripts/test_cns_query.py`

## 参考

- [Crossref API文档](https://github.com/CrossRef/rest-api-doc)
- [Crossref API游标分页](https://github.com/CrossRef/rest-api-doc/blob/master/rest_api_tutorial.md#cursor-based-paging)

---

**文档创建时间**: 2025-11-10  
**问题状态**: 已识别，已实现临时解决方案


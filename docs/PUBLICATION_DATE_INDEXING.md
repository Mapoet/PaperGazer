# 出版时间索引实现说明

## 问题背景

### 原有问题

1. **使用`from-index-date`导致数据量过大**：
   - `from-index-date`返回"自给定日期起被索引或重索引的所有记录"
   - 这包括历史论文的重新索引，导致数据量远超实际新发表论文数
   - 例如：查询近5天，但返回74730条记录（包含大量历史数据）

2. **Offset分页限制**：
   - Crossref API的offset上限为10,000
   - 超过会返回400错误
   - 不应该混用cursor和offset分页

3. **Checkpoint使用索引时间而非出版时间**：
   - 原有实现使用`datetime.now()`作为checkpoint
   - 无法准确反映论文的实际出版时间

## 解决方案

### 1. 改用出版时间过滤器

**修改前**：
```python
filter_str = f"{issn_filter},from-index-date:{since_str}"
sort = "indexed"
```

**修改后**：
```python
filter_str = f"{issn_filter},type:journal-article,from-pub-date:{since_str},until-pub-date:{until_str}"
sort = "issued"  # 按最早已知出版日排序
```

### 2. 移除Offset分页

- 完全移除offset分页相关代码
- 只使用cursor分页（官方推荐方式）
- 当cursor遇到限制时，记录警告并接受限制，剩余数据在下次巡检时继续获取

### 3. 使用出版时间作为Checkpoint

**修改前**：
```python
new_checkpoint = datetime.now(timezone.utc)
```

**修改后**：
```python
# 跟踪所有记录中的最大issued日期
max_issued_date = max(work.issued for work in works)
new_checkpoint = datetime.combine(max_issued_date, datetime.min.time()).replace(tzinfo=timezone.utc)
```

### 4. 添加时间窗口重叠

为了防止出版社回填/修订导致遗漏，使用检查点前1-2天作为起始日期：
```python
since_date = (last_checkpoint - timedelta(days=2)).date()
```

## 实现细节

### Crossref API查询参数

```python
params = {
    "filter": "issn:0028-0836,issn:1476-4687,...,type:journal-article,from-pub-date:2025-11-05,until-pub-date:2025-11-10",
    "select": "DOI,title,author,issued,published-online,published-print,container-title,ISSN,link,abstract",
    "sort": "issued",  # 按最早已知出版日排序
    "order": "asc",
    "cursor": "*",
    "rows": 1000,
    "mailto": "your-email@domain.com"
}
```

### 停止条件

- 当返回记录数 < rows 时，说明没有更多数据，正常退出
- 当返回满页数据但`next-cursor`相同时，记录警告并退出（这是API限制）

### Checkpoint更新逻辑

```python
# 提取每条记录的issued日期
if work.issued and "date-parts" in work.issued:
    date_parts = work.issued["date-parts"][0]
    year, month, day = date_parts[0], date_parts[1] or 1, date_parts[2] or 1
    issued_date = date(year, month, day)
    if max_issued_date is None or issued_date > max_issued_date:
        max_issued_date = issued_date

# 使用最大issued日期作为checkpoint
new_checkpoint = datetime.combine(max_issued_date, datetime.min.time()).replace(tzinfo=timezone.utc)
```

## 其他API检查

### arXiv API

arXiv API使用`lastUpdatedDate`排序，这是基于更新时间的。对于预印本来说，这是合理的，因为：
- arXiv主要是预印本平台
- 更新时间通常就是提交/更新时间
- 不需要修改

### Europe PMC / Unpaywall

这些API主要用于按需抓取，不涉及时间索引问题，无需修改。

## 优势

1. **数据量准确**：只获取实际在指定时间范围内出版的论文
2. **符合API规范**：使用cursor分页，不混用offset
3. **准确的增量查询**：基于出版时间而非索引时间
4. **防止遗漏**：使用时间窗口重叠机制

## 注意事项

1. **时间窗口重叠**：使用检查点前1-2天作为起始日期，防止遗漏
2. **Cursor限制**：如果遇到cursor限制（返回满页但cursor相同），剩余数据将在下次巡检时继续获取
3. **日期格式**：`from-pub-date`和`until-pub-date`支持`YYYY`、`YYYY-MM`、`YYYY-MM-DD`格式

## 相关文件

- 实现代码：`papergazer/sources/crossref.py`
- 巡检逻辑：`papergazer/core/ingest.py`
- 数据模型：`papergazer/models.py`

---

**实现时间**: 2025-11-10  
**状态**: ✅ 已实现


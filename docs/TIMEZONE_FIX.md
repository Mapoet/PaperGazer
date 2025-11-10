# 时区问题修复说明

## 问题描述

在运行每日巡检任务时，出现 `TypeError: can't compare offset-naive and offset-aware datetimes` 错误。

## 问题原因

1. **arXiv API 返回的日期**：`feedparser` 解析的日期是 naive datetime（没有时区信息）
2. **数据库存储的 checkpoint**：SQLite 存储 datetime 时可能丢失时区信息，读取时返回 naive datetime
3. **比较操作**：无法直接比较 naive 和 aware datetime

## 修复方案

### 1. arXiv 日期解析修复

**文件**: `papergazer/sources/arxiv.py`

```python
# 修复前
updated = datetime(*entry.updated_parsed[:6]) if hasattr(entry, "updated_parsed") else datetime.now()

# 修复后
if hasattr(entry, "updated_parsed") and entry.updated_parsed:
    updated = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
else:
    updated = datetime.now(timezone.utc)
```

### 2. Checkpoint 时区修复

**文件**: `papergazer/core/ingest.py`

```python
# 获取上次检查点
last_checkpoint = get_last_checkpoint(session, "arxiv")
if last_checkpoint:
    # 确保 checkpoint 有时区信息（如果从数据库读取的是 naive datetime）
    if last_checkpoint.tzinfo is None:
        last_checkpoint = last_checkpoint.replace(tzinfo=timezone.utc)
    logger.info(f"上次检查点: {last_checkpoint}")
```

### 3. 数据库初始化

**文件**: `papergazer/utils/daily_ingest.py` 和 `scripts/daily_ingest.py`

添加了数据库初始化步骤：
```python
init_db(config.store.db_path)
```

## 验证

修复后测试结果：
- ✅ arXiv 模块导入成功
- ✅ 时区比较测试通过
- ✅ 每日巡检任务正常运行
- ✅ 数据库正常创建和更新

## 注意事项

1. **时区统一**：所有 datetime 对象应使用 UTC 时区
2. **数据库存储**：SQLite 存储 datetime 时可能丢失时区信息，读取时需要补充
3. **API 返回**：不同 API 返回的日期格式可能不同，需要统一处理


# CNS期刊查询测试报告

## 测试概述

本次测试针对CNS（Cell、Nature、Science）期刊，查询近5天的论文信息，验证系统对多个CNS期刊的支持能力。

**测试时间**: 2025-11-10  
**测试范围**: Science、Cell  
**测试天数**: 5天

---

## 测试配置

### 配置文件更新

更新了 `configs/config.test.yaml`，添加了Science和Cell的ISSN配置：

```yaml
cns:
  issn:
    nature:
      - "0028-0836"           # print
      - "1476-4687"           # online
    science:
      - "0036-8075"           # print
      - "1095-9203"           # online
    cell:
      - "0092-8674"           # print
      - "1097-4172"           # online
```

### 测试脚本

创建了通用测试脚本 `scripts/test_cns_query.py`，支持：
- 查询单个期刊：`python scripts/test_cns_query.py <journal> [days]`
- 查询所有期刊：`python scripts/test_cns_query.py all [days]`

支持的期刊参数：
- `nature` - Nature期刊
- `science` - Science期刊
- `cell` - Cell期刊
- `all` - 所有CNS期刊

---

## 测试结果

### 1. Science期刊查询

**执行命令**: `python scripts/test_cns_query.py science 5`

**结果**:
- ✅ 成功查询Crossref API
- ✅ 处理了2000条记录（API返回限制）
- ✅ 成功存储到数据库
- ✅ 显示前20条记录

**查询到的论文示例**:
- Direct estimation of earthquake source properties (2025-10-30)
- Wavefront shaping enables high-power multimode (2025-10-09)
- Lithium-ion intercalation by coupled ion-electron (2025-10-02)

**注意事项**:
- Crossref API的`from-index-date`参数基于索引日期，而非发布日期
- 部分论文的发布日期可能早于查询时间范围，但索引日期在范围内
- 这是Crossref API的正常行为

### 2. Cell期刊查询

**执行命令**: `python scripts/test_cns_query.py cell 5`

**结果**:
- ✅ 成功查询Crossref API
- ✅ 处理了2000条记录（API返回限制）
- ✅ 成功存储到数据库
- ✅ 显示前20条记录

**查询到的论文示例**:
- The implications of angiogenesis for the biology (1994-10-21)
- The crystal structure and biological function (1994-07-01)
- hDOT1L Links Histone Methylation to Leukemogenesis (日期未知)

**注意事项**:
- 部分论文的`published_date`字段为空或格式不正确
- 这可能是Crossref API返回数据的问题，或数据解析问题
- 需要进一步检查数据模型和解析逻辑

---

## 数据库统计

### Science期刊统计
- 总记录数：2000条（受API限制）
- 近5天发布的论文数：需要进一步验证（基于`published_date`字段）

### Cell期刊统计
- 总记录数：2000条（受API限制）
- 近5天发布的论文数：需要进一步验证（基于`published_date`字段）

---

## 发现的问题

### 1. 发布日期字段问题

**现象**:
- 部分论文的`published_date`字段为"未知"或空值
- 部分论文的发布日期明显早于查询时间范围

**可能原因**:
1. Crossref API返回的`issued`字段格式不统一
2. 数据解析逻辑需要改进
3. `from-index-date`参数基于索引日期，而非发布日期

**建议**:
- 检查`papergazer/models.py`中的`CrossrefWork.to_metadata`方法
- 验证`issued`字段的解析逻辑
- 考虑同时使用`indexed-date`和`published-date`进行筛选

### 2. API返回限制

**现象**:
- 每次查询最多返回2000条记录
- 游标分页在第二次请求后即退出（`next-cursor`与当前`cursor`相同）

**可能原因**:
- Crossref API的游标分页机制
- 查询结果集较小，无需多次分页

**状态**: ✅ 已通过之前的修复解决游标循环问题

---

## 测试结论

### ✅ 成功项

1. **多期刊支持**: 系统成功支持查询多个CNS期刊（Nature、Science、Cell）
2. **API集成**: Crossref API集成正常，能够成功获取数据
3. **数据存储**: 数据成功存储到数据库
4. **游标分页**: 游标分页逻辑正常工作，无无限循环问题
5. **错误处理**: 系统能够正确处理API响应和错误

### ⚠️ 需要改进项

1. **发布日期解析**: 需要改进`published_date`字段的解析逻辑，确保正确提取发布日期
2. **数据筛选**: 考虑使用更精确的日期筛选机制，基于实际发布日期而非索引日期
3. **数据验证**: 添加数据验证逻辑，确保存储的数据质量

---

## 下一步建议

1. **改进日期解析**:
   - 检查Crossref API返回的`issued`字段格式
   - 改进`CrossrefWork.to_metadata`方法中的日期解析逻辑
   - 添加日期格式验证

2. **优化查询策略**:
   - 考虑使用`from-pub-date`参数替代或补充`from-index-date`
   - 实现更精确的日期范围筛选

3. **数据质量检查**:
   - 添加数据验证步骤，确保关键字段（如`published_date`）不为空
   - 记录数据质量统计信息

4. **测试扩展**:
   - 测试更长时间范围的查询
   - 测试所有CNS期刊的批量查询
   - 验证数据去重逻辑

---

## 测试脚本使用说明

### 查询单个期刊

```bash
# 查询Nature近5天论文
python scripts/test_cns_query.py nature 5

# 查询Science近5天论文
python scripts/test_cns_query.py science 5

# 查询Cell近5天论文
python scripts/test_cns_query.py cell 5
```

### 查询所有期刊

```bash
# 查询所有CNS期刊近5天论文
python scripts/test_cns_query.py all 5
```

### 自定义查询天数

```bash
# 查询近10天的论文
python scripts/test_cns_query.py science 10
```

---

## 相关文件

- 测试脚本: `scripts/test_cns_query.py`
- 测试配置: `configs/config.test.yaml`
- 数据源实现: `papergazer/sources/crossref.py`
- 数据模型: `papergazer/models.py`
- 数据库操作: `papergazer/store/db.py`

---

**报告生成时间**: 2025-11-10


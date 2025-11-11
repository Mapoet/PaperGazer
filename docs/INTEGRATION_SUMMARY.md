# 工具模块整合总结

## 完成的工作

### 1. 创建工具模块 (`papergazer/utils/`)

#### `query.py` - 多来源论文查询工具
- `query_arxiv_by_days()` - arXiv 查询
- `query_crossref_by_days()` - Crossref (CNS) 查询
- `query_europe_pmc_by_days()` - Europe PMC 查询
- `query_unpaywall_by_days()` - Unpaywall OA 状态查询
- `query_all_sources_by_days()` - 统一查询所有数据源

#### `analyze.py` - 论文分析工具
- `analyze_authors_by_days()` - 作者分析（Top N 作者、机构分布）
- `analyze_abstracts_by_days()` - 摘要分析（覆盖率、长度统计）
- `analyze_oa_status_by_days()` - OA 状态分析（OA率、来源分布）
- `analyze_venues_by_days()` - 期刊/会议分析（Top N 期刊）
- `get_papers_by_days()` - 获取论文列表

#### `daily_ingest.py` - 每日巡检任务工具
- `daily_ingest_all()` - 执行所有数据源的每日巡检
- `daily_ingest_sources()` - 执行指定数据源的每日巡检

### 2. 创建示例脚本 (`scripts/`)

#### Python 脚本
- `query_papers.py` - 统一查询脚本
- `analyze_papers.py` - 分析脚本
- `daily_ingest.py` - 每日巡检脚本

#### Bash 脚本
- `query_papers.sh` - 查询脚本封装
- `analyze_papers.sh` - 分析脚本封装
- `daily_ingest.sh` - 巡检脚本封装

## 使用示例

### 查询功能

```bash
# 查询最近7天的所有数据源
python scripts/query_papers.py 7
./scripts/query_papers.sh 7

# 查询指定数据源
python scripts/query_papers.py 7 arxiv crossref
./scripts/query_papers.sh 7 arxiv crossref
```

### 分析功能

```bash
# 作者分析
python scripts/analyze_papers.py authors 7
./scripts/analyze_papers.sh authors 7

# 摘要分析
python scripts/analyze_papers.py abstracts 30 arxiv crossref
./scripts/analyze_papers.sh abstracts 30 arxiv crossref

# OA状态分析
python scripts/analyze_papers.py oa 7
./scripts/analyze_papers.sh oa 7

# 期刊/会议分析
python scripts/analyze_papers.py venues 30
./scripts/analyze_papers.sh venues 30

# 论文列表
python scripts/analyze_papers.py list 7 10
./scripts/analyze_papers.sh list 7 10
```

### 每日巡检

```bash
# 执行所有数据源的巡检
python scripts/daily_ingest.py
./scripts/daily_ingest.sh

# 执行指定数据源的巡检
python scripts/daily_ingest.py arxiv crossref
./scripts/daily_ingest.sh arxiv crossref
```

> 巡检脚本在抓取与下载完成后，会自动执行 TEI 生成、图表抽取、引用网络构建以及语义向量写入；
> 可通过 `--skip-tei` / `--skip-figures` / `--skip-citations` / `--skip-embeddings` 精细控制。

## 定时任务设置

### Cron 示例

```bash
# 每天凌晨2点执行每日巡检
0 2 * * * cd /path/to/PaperGazer && /usr/bin/python3 scripts/daily_ingest.py >> logs/daily_ingest.log 2>&1
```

### Systemd Timer 示例

创建 `papergazer-daily.service` 和 `papergazer-daily.timer` 文件（详见 `docs/UTILS_MODULE.md`）

## 功能特点

1. **统一接口**: 所有数据源使用统一的查询接口
2. **灵活配置**: 支持指定数据源、时间范围、结果数量限制
3. **自动保存**: 查询结果自动保存到数据库
4. **丰富分析**: 提供作者、摘要、OA状态、期刊等多维度分析
5. **易于使用**: 提供 Python 和 Bash 两种调用方式
6. **错误处理**: 完善的错误处理和日志记录

## 文件结构

```
papergazer/utils/
├── __init__.py          # 模块导出
├── query.py             # 查询工具
├── analyze.py           # 分析工具
└── daily_ingest.py      # 巡检工具

scripts/
├── query_papers.py      # 查询脚本
├── query_papers.sh      # 查询脚本（Bash）
├── analyze_papers.py    # 分析脚本
├── analyze_papers.sh    # 分析脚本（Bash）
├── daily_ingest.py      # 巡检脚本
└── daily_ingest.sh      # 巡检脚本（Bash）
```

## 后续改进建议

1. **性能优化**: 考虑批量处理和并发优化
2. **缓存机制**: 添加查询结果缓存
3. **导出功能**: 支持导出分析结果为 CSV/JSON
4. **可视化**: 添加图表可视化功能
5. **向量检索**: 基于 `embeddings` 表实现相似论文检索接口
6. **Web界面**: 考虑开发 Web 界面


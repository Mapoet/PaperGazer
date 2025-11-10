# 工具模块文档

## 概述

`papergazer/utils/` 目录提供了统一的工具模块，整合了多数据源的查询、分析和巡检功能。

## 模块结构

```
papergazer/utils/
├── __init__.py          # 模块导出
├── query.py             # 多来源论文查询工具
├── analyze.py           # 论文分析工具
└── daily_ingest.py      # 每日巡检任务工具
```

## 功能模块

### 1. query.py - 查询工具

提供多数据源的统一查询接口。

#### 主要函数

- `query_arxiv_by_days(config, days, categories=None)` - 查询 arXiv 论文
- `query_crossref_by_days(config, days, issns=None)` - 查询 Crossref 论文（CNS期刊）
- `query_europe_pmc_by_days(config, days, max_results=1000, save_to_db=True)` - 查询 Europe PMC 论文
- `query_unpaywall_by_days(config, days, limit=None)` - 查询 Unpaywall OA 状态
- `query_all_sources_by_days(config, days, sources=None, max_results=None)` - 查询所有数据源

#### 使用示例

```python
from papergazer.config import load_config
from papergazer.utils import query_all_sources_by_days

config = load_config("configs/config.yaml")
results = await query_all_sources_by_days(
    config,
    days=7,
    sources=["arxiv", "crossref", "eupmc"],
    max_results={"eupmc": 1000, "unpaywall": 100}
)
```

### 2. analyze.py - 分析工具

提供论文数据的分析功能。

#### 主要函数

- `analyze_authors_by_days(days, sources=None, top_n=10)` - 作者分析
- `analyze_abstracts_by_days(days, sources=None, min_length=100)` - 摘要分析
- `analyze_oa_status_by_days(days, sources=None)` - OA状态分析
- `analyze_venues_by_days(days, sources=None, top_n=10)` - 期刊/会议分析
- `get_papers_by_days(days, sources=None, limit=None, order_by="updated_date")` - 获取论文列表

#### 使用示例

```python
from papergazer.utils import analyze_authors_by_days, analyze_oa_status_by_days

# 作者分析
authors_result = analyze_authors_by_days(days=7, sources=["arxiv", "crossref"])

# OA状态分析
oa_result = analyze_oa_status_by_days(days=30)
```

### 3. daily_ingest.py - 巡检工具

提供每日巡检任务的执行功能。

#### 主要函数

- `daily_ingest_all(config)` - 执行所有数据源的每日巡检
- `daily_ingest_sources(config, sources)` - 执行指定数据源的每日巡检

#### 使用示例

```python
from papergazer.config import load_config
from papergazer.utils import daily_ingest_all

config = load_config("configs/config.yaml")
results = await daily_ingest_all(config)
```

## 脚本使用

### 1. query_papers.py - 统一查询脚本

```bash
# 查询最近7天的所有数据源
python scripts/query_papers.py 7

# 查询指定数据源
python scripts/query_papers.py 7 arxiv crossref

# 使用 bash 脚本
./scripts/query_papers.sh 7
./scripts/query_papers.sh 7 arxiv crossref
```

### 2. analyze_papers.py - 分析脚本

```bash
# 作者分析
python scripts/analyze_papers.py authors 7

# 摘要分析
python scripts/analyze_papers.py abstracts 30 arxiv crossref

# OA状态分析
python scripts/analyze_papers.py oa 7

# 期刊/会议分析
python scripts/analyze_papers.py venues 30

# 论文列表
python scripts/analyze_papers.py list 7 10

# 使用 bash 脚本
./scripts/analyze_papers.sh authors 7
./scripts/analyze_papers.sh abstracts 30 arxiv crossref
```

### 3. daily_ingest.py - 每日巡检脚本

```bash
# 执行所有数据源的巡检
python scripts/daily_ingest.py

# 执行指定数据源的巡检
python scripts/daily_ingest.py arxiv crossref

# 使用 bash 脚本
./scripts/daily_ingest.sh
./scripts/daily_ingest.sh arxiv crossref
```

## 定时任务设置

### 使用 cron

编辑 crontab：
```bash
crontab -e
```

添加每日巡检任务（每天凌晨2点执行）：
```
0 2 * * * cd /path/to/PaperGazer && /usr/bin/python3 scripts/daily_ingest.py >> logs/daily_ingest.log 2>&1
```

### 使用 systemd timer

创建 `papergazer-daily.service`：
```ini
[Unit]
Description=PaperGazer Daily Ingest
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/PaperGazer
ExecStart=/usr/bin/python3 scripts/daily_ingest.py
User=your_user
```

创建 `papergazer-daily.timer`：
```ini
[Unit]
Description=Run PaperGazer Daily Ingest
Requires=papergazer-daily.service

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

启用定时器：
```bash
sudo systemctl enable papergazer-daily.timer
sudo systemctl start papergazer-daily.timer
```

## 注意事项

1. **配置文件**: 所有脚本默认使用 `configs/config.test.yaml`，生产环境请修改为 `configs/config.yaml`
2. **数据库路径**: 确保数据库路径配置正确
3. **API限制**: 遵守各API的速率限制
4. **错误处理**: 脚本包含错误处理和日志记录
5. **并发控制**: 查询工具已实现适当的延迟和并发控制

## 扩展开发

### 添加新的数据源

1. 在 `papergazer/sources/` 下实现数据源模块
2. 在 `papergazer/utils/query.py` 中添加查询函数
3. 在 `query_all_sources_by_days` 中添加支持

### 添加新的分析功能

1. 在 `papergazer/utils/analyze.py` 中添加分析函数
2. 在 `scripts/analyze_papers.py` 中添加对应的处理逻辑


# PaperGazer 技术路线与实施方案

## 1. 项目概述

PaperGazer 是一个自动化论文监控与抓取系统，旨在实现：
- 每日自动巡检 arXiv 预印本和 CNS（Nature/Science/Cell）期刊
- 按需抓取开放获取（OA）全文或非 OA 摘要
- 结构化存储与去重管理
- 友好的命令行接口

## 2. 技术架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    CLI Interface (Typer)                 │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼────┐            ┌─────▼─────┐
    │  Ingest │            │   Fetch   │
    │ Pipeline│            │ Pipeline  │
    └────┬────┘            └─────┬─────┘
         │                       │
    ┌────┴───────────────────────┴────┐
    │      Data Sources Layer          │
    ├──────────┬──────────┬───────────┤
    │  arXiv   │ Crossref │ Unpaywall │
    │ EuropePMC│          │           │
    └──────────┴──────────┴───────────┘
         │                       │
    ┌────┴───────────────────────┴────┐
    │      Storage Layer               │
    ├──────────────┬───────────────────┤
    │   SQLite DB  │  File System      │
    └──────────────┴───────────────────┘
```

### 2.2 核心模块设计

#### 2.2.1 数据源模块 (`sources/`)

**职责**：封装各数据源的 API 调用与数据解析

- `arxiv.py`：arXiv Atom API 查询与解析
- `crossref.py`：Crossref REST API 增量拉取
- `unpaywall.py`：Unpaywall OA 状态查询
- `europe_pmc.py`：Europe PMC 全文获取

**设计原则**：
- 异步 HTTP 请求（`httpx.AsyncClient`）
- 统一错误处理与重试机制（`tenacity`）
- 返回标准化数据结构（`pydantic` models）

#### 2.2.2 存储模块 (`store/`)

**职责**：数据持久化与文件管理

- `db.py`：SQLAlchemy ORM 模型与数据库操作
- `files.py`：PDF/XML 文件存储路径规范与去重

**数据表设计**：

```sql
-- items: 论文主表
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,  -- 'arxiv' | 'crossref'
    identifier TEXT NOT NULL,  -- arxiv_id 或 doi
    title TEXT,
    authors_json TEXT,  -- JSON 数组
    venue TEXT,  -- 期刊/会议名称
    issn_print TEXT,
    issn_online TEXT,
    published_date DATE,
    updated_date DATETIME,
    doi TEXT UNIQUE,
    url_landing TEXT,
    is_oa BOOLEAN DEFAULT 0,
    oa_source TEXT,  -- 'unpaywall' | 'eupmc' | 'arxiv'
    oa_pdf_url TEXT,
    pdf_path TEXT,
    abstract_jats TEXT,
    ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    hash TEXT  -- 文件哈希（用于去重）
);

-- runs: 巡检记录表
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,  -- 'arxiv' | 'crossref'
    last_checkpoint DATETIME NOT NULL,
    items_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 2.2.3 核心逻辑模块 (`core/`)

**职责**：业务流程编排

- `ingest.py`：每日巡检 Pipeline
  - arXiv 分类查询 → 本地过滤 → 入库
  - Crossref ISSN + 日期过滤 → 游标分页 → 入库
- `fetch.py`：按需抓取 Pipeline
  - 优先级：arXiv → Unpaywall → Europe PMC → Crossref 摘要
  - 文件下载与存储
  - 元数据回填

#### 2.2.4 CLI 模块 (`cli.py`)

**职责**：命令行接口

- `check`：执行每日巡检
- `fetch <identifier>`：按需抓取
- `search --q <query>`：搜索论文
- `export --since <date> --format <format>`：导出数据

## 3. 实施方案

### 3.1 开发阶段

#### Phase 1: 基础框架（Week 1-2）
- [x] 项目初始化与目录结构
- [ ] 数据源模块实现（arXiv, Crossref）
- [ ] 存储模块实现（SQLite + 文件系统）
- [ ] 基础 CLI 接口

#### Phase 2: 核心功能（Week 3-4）
- [ ] 巡检 Pipeline 实现
- [ ] 抓取 Pipeline 实现
- [ ] 去重与质量控制
- [ ] 错误处理与重试机制

#### Phase 3: 优化与扩展（Week 5-6）
- [ ] 任务调度（apscheduler/cron）
- [ ] 日志系统（结构化日志）
- [ ] 性能优化（并发控制、缓存）
- [ ] 测试覆盖

#### Phase 4: 文档与部署（Week 7-8）
- [ ] 用户文档完善
- [ ] API 文档
- [ ] 部署指南
- [ ] 示例与教程

### 3.2 技术选型理由

| 技术 | 选型理由 |
|------|---------|
| `httpx` | 异步 HTTP 客户端，性能优于 `requests`，支持 HTTP/2 |
| `feedparser` | 成熟的 Atom/RSS 解析库，arXiv API 返回 Atom 格式 |
| `pydantic` | 数据验证与配置管理，类型安全 |
| `SQLAlchemy` | ORM 框架，便于数据库迁移与维护 |
| `typer` | 基于 `click` 的现代 CLI 框架，类型提示友好 |
| `tenacity` | 优雅的重试机制，支持指数退避 |
| `apscheduler` | Python 原生任务调度，无需系统 cron |

### 3.3 数据流设计

#### 巡检流程

```
1. 读取配置（config.yaml）
   ↓
2. 查询 arXiv API（按分类）
   ↓
3. 本地过滤（基于 last_checkpoint）
   ↓
4. 批量入库（items 表）
   ↓
5. 更新 runs.last_checkpoint
   ↓
6. 查询 Crossref API（ISSN + from-index-date）
   ↓
7. 游标分页遍历
   ↓
8. 批量入库（items 表）
   ↓
9. 更新 runs.last_checkpoint
```

#### 抓取流程

```
输入：identifier (DOI 或 arXiv id)
   ↓
判断类型
   ├─ arXiv id → 直接下载 PDF
   └─ DOI → 优先级链
       ├─ Unpaywall → 检查 is_oa → 下载 PDF
       ├─ Europe PMC → DOI → PMCID → 下载 XML
       └─ Crossref → 获取摘要（fallback）
   ↓
保存文件（按路径规范）
   ↓
更新 items 表（pdf_path, oa_source 等）
```

### 3.4 去重策略

1. **数据库层面**：
   - `doi` 字段设置 UNIQUE 约束
   - `identifier`（arxiv_id 或 doi）作为业务主键

2. **文件层面**：
   - 文件路径规范化（`{year}/{sanitized_id}/paper.pdf`）
   - 文件哈希（SHA256）存储，下载前检查

3. **数据归一化**：
   - DOI：小写、去空格
   - arXiv id：去除版本号（`vN`），保留在 `updated_date`

### 3.5 错误处理与重试

- **网络错误**：使用 `tenacity` 指数退避重试（最多 3 次）
- **API 限流**：请求间隔控制（arXiv ≥3s，Crossref 礼貌池）
- **数据异常**：记录日志，跳过异常项，继续处理
- **存储失败**：回滚事务，记录错误

### 3.6 性能优化

1. **并发控制**：
   - arXiv：单线程（API 限制）
   - Crossref：异步批量请求（控制并发数）

2. **缓存策略**：
   - Unpaywall 查询结果缓存（TTL 24h）
   - 文件存在性检查缓存

3. **批量操作**：
   - 数据库批量插入（`bulk_insert_mappings`）
   - 文件下载批量处理

## 4. 部署方案

### 4.1 本地部署

```bash
# 使用 apscheduler（应用内调度）
python -m papergazer.scheduler start
```

### 4.2 服务器部署

```bash
# 使用系统 cron
0 7 * * * /path/to/venv/bin/python -m papergazer.cli check
```

### 4.3 Docker 部署（可选）

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "-m", "papergazer.cli", "check"]
```

## 5. 监控与日志

- **结构化日志**：JSON 格式，记录每源抓取数、失败重试、PDF 命中率
- **指标收集**：每日巡检统计、抓取成功率、存储使用量
- **告警机制**：连续失败告警、存储空间告警

## 6. 合规性

- **仅使用 OA 渠道**：不跨越付费墙
- **遵守 API 使用规范**：请求间隔、邮箱标识
- **数据使用声明**：仅用于个人研究，不商业用途

## 7. 未来扩展

- [ ] Web UI（基于 FastAPI + React）
- [ ] 论文推荐系统（基于关键词/作者）
- [ ] 邮件通知（新论文提醒）
- [ ] 多语言支持
- [ ] 更多数据源（PubMed, IEEE Xplore 等）


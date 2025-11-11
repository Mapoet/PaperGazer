# PaperGazer 项目结构说明

## 目录结构

```
PaperGazer/
├── .gitignore              # Git 忽略文件配置
├── .cursorrules            # Cursor IDE 规则配置
├── LICENSE                 # MIT 许可证
├── README.md               # 项目说明文档
├── requirements.txt        # Python 依赖列表
├── pyproject.toml          # Python 项目配置（setuptools, black, mypy 等）
│
├── papergazer/             # 主包目录
│   ├── __init__.py         # 包初始化文件
│   ├── cli.py              # 命令行接口（Typer）
│   │
│   ├── sources/            # 数据源模块
│   │   ├── __init__.py     # 模块导出
│   │   ├── arxiv.py        # arXiv API 封装
│   │   ├── crossref.py     # Crossref API 封装
│   │   ├── openalex.py     # OpenAlex API 封装
│   │   ├── unpaywall.py    # Unpaywall API 封装
│   │   └── europe_pmc.py   # Europe PMC API 封装
│   │
│   ├── store/              # 存储模块
│   │   ├── __init__.py     # 模块导出
│   │   ├── db.py           # 数据库操作（SQLAlchemy ORM）
│   │   └── files.py        # 文件存储管理
│   │
│   └── core/               # 核心逻辑模块
│       ├── __init__.py     # 模块导出
│       ├── ingest.py       # 每日巡检 Pipeline
│       ├── fetch.py        # 按需抓取 Pipeline
│       ├── fulltext.py     # GROBID/文本 → TEI
│       ├── figures.py      # 图表抽取
│       ├── identity_enrich.py  # ORCID/ROR 标准化
│       └── embeddings.py   # 语义向量生成
│
│   ├── analytics/          # 分析模块
│   │   ├── __init__.py
│   │   ├── citation.py     # 引用网络 / 合作网络
│   │   ├── concepts.py     # 概念热度
│   │   ├── oa.py           # OA / FAIR 指标
│   │   └── topics.py       # 主题趋势分析
│
├── configs/                # 配置文件目录
│   └── config.yaml.example # 配置文件示例（需复制为 config.yaml）
│
├── data/                   # 数据目录（gitignore）
│   ├── papers/             # 论文文件存储
│   │   └── {year}/         # 按年份组织
│   │       └── {id}/       # 按论文 ID 组织
│   │           ├── paper.pdf
│   │           └── fulltext.xml
│   └── db.sqlite3          # SQLite 数据库
│
├── tests/                  # 测试代码目录
│   ├── __init__.py
│   ├── conftest.py         # pytest 配置与 fixtures
│   ├── test_sources/       # 数据源模块测试
│   ├── test_store/         # 存储模块测试
│   └── test_core/          # 核心逻辑测试
│
├── docs/                   # 文档目录
│   ├── requires.md         # 需求文档
│   ├── TECHNICAL_ROADMAP.md # 技术路线与实施方案
│   └── PROJECT_STRUCTURE.md # 本文件
│
└── scripts/                # 工具脚本目录
    ├── daily_ingest.py     # 巡检 + 元数据 + 下载 + 后处理
    ├── analyze_papers.py   # 综合分析入口
    ├── query_papers.py     # 查询示例
    └── export_abstracts.py # 摘要导出
```

## 模块说明

### papergazer.sources

**职责**：封装各数据源的 API 调用与数据解析

| 文件 | 功能 |
|------|------|
| `arxiv.py` | arXiv Atom API 查询与解析，提取论文元数据和 PDF 链接 |
| `crossref.py` | Crossref REST API 增量拉取，支持 ISSN 过滤和游标分页 |
| `unpaywall.py` | Unpaywall API 查询 OA 状态和最佳 OA 位置 |
| `europe_pmc.py` | Europe PMC API，DOI → PMCID → FullTextXML |

**设计原则**：
- 异步 HTTP 请求（`httpx.AsyncClient`）
- 统一错误处理与重试机制（`tenacity`）
- 返回标准化数据结构（`pydantic` models）

### papergazer.store

**职责**：数据持久化与文件管理

| 文件 | 功能 |
|------|------|
| `db.py` | SQLAlchemy ORM 模型定义、数据库初始化、CRUD 操作 |
| `files.py` | PDF/XML 文件存储路径规范、文件哈希计算、去重检查 |

**数据表**：
- `items`：论文主表（元数据 + 文件路径）
- `runs`：巡检记录表（检查点追踪）

### papergazer.core

**职责**：业务流程编排

| 文件 | 功能 |
|------|------|
| `ingest.py` | 每日巡检 Pipeline：arXiv + Crossref 增量抓取 → 入库 |
| `fetch.py` | 按需抓取 Pipeline：优先级链（arXiv → Unpaywall → Europe PMC → Crossref） |
| `fulltext.py` | 调用 GROBID 或本地文本生成 TEI |
| `figures.py` | 从 TEI / PDF 抽取图表结构 |
| `identity_enrich.py` | 对接 ORCID / ROR，写入标准化身份表 |
| `embeddings.py` | 基于 sentence-transformers 生成语义向量 |

### papergazer.cli

**职责**：命令行接口（基于 Typer）

**子命令**：
- `check`：执行每日巡检
- `fetch <identifier>`：按需抓取（DOI 或 arXiv id）
- `search --q <query>`：搜索论文
- `export --since <date> --format <format>`：导出数据

## 配置文件

### configs/config.yaml

主要配置项：
- `mailto`：联系邮箱（用于 API 礼貌池）
- `arxiv.categories`：关注的 arXiv 分类
- `journals.issn`：期刊 ISSN 列表（print/online）
- `store.root`：数据存储根目录
- `schedule`：定时任务配置
- `logging`：日志配置
- `retry`：重试配置
- `grobid` / `figures` / `identity`：全文、图表、身份识别流程开关
- `embeddings`：语义向量模型、字段、批次大小、截断长度

## 数据存储规范

### 数据库（SQLite）

- 位置：`data/db.sqlite3`
- 表结构：见 `docs/TECHNICAL_ROADMAP.md`

### 文件系统

论文文件存储路径：
```
data/papers/{year}/{sanitized_id}/
├── paper.pdf          # PDF 文件
└── fulltext.xml       # XML 全文（来自 Europe PMC）
```

路径规范：
- `year`：论文发表年份（YYYY）
- `sanitized_id`：DOI 或 arXiv id 的规范化版本（去除特殊字符）

## 开发规范

详见 `.cursorrules` 文件，主要包括：
- Python 代码风格（black, isort）
- 类型提示要求
- 异步编程规范
- 错误处理与重试
- 测试要求
- 日志规范

## 依赖管理

- **生产依赖**：`requirements.txt`
- **项目配置**：`pyproject.toml`（setuptools, black, mypy, pytest 等）

## 测试结构

```
tests/
├── conftest.py           # 共享 fixtures
├── test_sources/         # 数据源模块测试
│   ├── test_arxiv.py
│   ├── test_crossref.py
│   ├── test_unpaywall.py
│   └── test_europe_pmc.py
├── test_store/           # 存储模块测试
│   ├── test_db.py
│   └── test_files.py
└── test_core/            # 核心逻辑测试
    ├── test_ingest.py
    └── test_fetch.py
```

## 扩展点

未来可扩展的模块：
- `papergazer.scheduler`：任务调度模块（apscheduler 封装）
- `papergazer.api`：REST API 接口（FastAPI）
- `papergazer.web`：Web UI（React + FastAPI）
- `papergazer.notify`：通知模块（邮件/推送）


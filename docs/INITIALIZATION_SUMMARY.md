# PaperGazer 项目初始化总结

## 完成的工作

### 1. 标准 Git 项目结构 ✅

已创建以下基础文件：
- `.gitignore`：Python 项目标准忽略规则
- `README.md`：项目说明文档（功能特性、快速开始、使用示例）
- `LICENSE`：MIT 许可证
- `Makefile`：开发命令快捷方式

### 2. 技术路线与实施方案 ✅

已创建技术文档：
- `docs/TECHNICAL_ROADMAP.md`：完整的技术架构、实施方案、数据流设计、性能优化等

**核心架构**：
```
CLI Interface → Ingest/Fetch Pipeline → Data Sources → Storage Layer
```

**技术选型**：
- 异步 HTTP：`httpx`
- 数据解析：`feedparser`
- 配置管理：`pydantic` + `pyyaml`
- 数据存储：`SQLAlchemy` + `sqlite3`
- CLI 框架：`typer`
- 重试机制：`tenacity`
- 任务调度：`apscheduler`

### 3. 程序层次结构 ✅

已创建完整的模块结构：

```
papergazer/
├── sources/          # 数据源模块
│   ├── arxiv.py
│   ├── crossref.py
│   ├── unpaywall.py
│   └── europe_pmc.py
├── store/            # 存储模块
│   ├── db.py
│   └── files.py
├── core/             # 核心逻辑
│   ├── ingest.py
│   └── fetch.py
└── cli.py            # 命令行接口
```

**模块职责**：
- `sources/`：封装各数据源 API，返回标准化数据结构
- `store/`：数据持久化（SQLite + 文件系统）
- `core/`：业务流程编排（巡检、抓取 Pipeline）
- `cli.py`：命令行接口（check, fetch, search, export）

### 4. 项目配置文件 ✅

已创建：
- `requirements.txt`：Python 依赖列表
- `pyproject.toml`：项目配置（setuptools, black, isort, mypy, pytest）
- `configs/config.yaml.example`：配置文件示例

**主要依赖**：
- `httpx>=0.25.0`：异步 HTTP 客户端
- `feedparser>=6.0.10`：Atom/RSS 解析
- `pydantic>=2.5.0`：数据验证
- `sqlalchemy>=2.0.23`：ORM
- `typer[all]>=0.9.0`：CLI 框架
- `tenacity>=8.2.3`：重试机制
- `apscheduler>=3.10.4`：任务调度

### 5. Cursor Rules ✅

已创建 `.cursorrules` 文件，包含：
- 代码风格与规范（Python 3.11+, black, isort, 类型提示）
- 项目结构说明
- 模块职责定义
- API 使用规范
- 测试要求
- 日志规范
- 合规性要求

## 项目结构总览

```
PaperGazer/
├── .gitignore
├── .cursorrules          # Cursor IDE 规则
├── LICENSE
├── README.md
├── requirements.txt
├── pyproject.toml
├── Makefile              # 开发命令
│
├── papergazer/           # 主包
│   ├── __init__.py
│   ├── cli.py
│   ├── sources/          # 数据源模块
│   ├── store/            # 存储模块
│   └── core/             # 核心逻辑
│
├── configs/
│   └── config.yaml.example
│
├── data/                 # 数据目录（gitignore）
│   ├── papers/
│   └── db.sqlite3
│
├── tests/                # 测试代码
│   ├── conftest.py
│   └── (待实现)
│
└── docs/                 # 文档
    ├── requires.md
    ├── TECHNICAL_ROADMAP.md
    └── PROJECT_STRUCTURE.md
```

## 下一步开发计划

### Phase 1: 基础框架实现（优先级：高）

1. **数据源模块实现**
   - [ ] `sources/arxiv.py`：arXiv API 封装
   - [ ] `sources/crossref.py`：Crossref API 封装
   - [ ] `sources/unpaywall.py`：Unpaywall API 封装
   - [ ] `sources/europe_pmc.py`：Europe PMC API 封装

2. **存储模块实现**
   - [ ] `store/db.py`：SQLAlchemy 模型定义与数据库操作
   - [ ] `store/files.py`：文件存储管理

3. **核心逻辑实现**
   - [ ] `core/ingest.py`：每日巡检 Pipeline
   - [ ] `core/fetch.py`：按需抓取 Pipeline

4. **CLI 接口实现**
   - [ ] `cli.py`：Typer 命令行接口

### Phase 2: 测试与优化（优先级：中）

- [ ] 单元测试（各模块）
- [ ] 集成测试（完整 Pipeline）
- [ ] 错误处理完善
- [ ] 性能优化

### Phase 3: 文档与部署（优先级：低）

- [ ] API 文档
- [ ] 用户指南
- [ ] 部署脚本
- [ ] Docker 支持（可选）

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
make install
# 或
pip install -r requirements.txt
```

### 2. 配置

```bash
# 复制配置文件
cp configs/config.yaml.example configs/config.yaml

# 编辑配置文件，设置邮箱、arXiv 分类等
vim configs/config.yaml
```

### 3. 开发

```bash
# 代码格式化
make format

# 运行测试
make test

# 类型检查
make type-check
```

## 开发规范

详见 `.cursorrules` 文件，关键点：
- Python 3.11+，使用类型提示
- 代码格式化：`black` + `isort`
- 异步编程：优先使用 `async/await`
- 错误处理：使用 `tenacity` 重试
- 数据验证：使用 `pydantic`
- 测试覆盖：至少 80%

## 参考文档

- **需求文档**：`docs/requires.md`
- **技术路线**：`docs/TECHNICAL_ROADMAP.md`
- **项目结构**：`docs/PROJECT_STRUCTURE.md`
- **Cursor Rules**：`.cursorrules`

## 注意事项

1. **配置文件**：`configs/config.yaml` 包含敏感信息（邮箱），不应提交到版本控制
2. **数据目录**：`data/` 已加入 `.gitignore`，不会提交到版本控制
3. **API 使用规范**：遵守各数据源的 API 使用规范（请求间隔、邮箱标识等）
4. **合规性**：仅使用 OA 渠道，不跨越付费墙

## Git 仓库状态

已初始化 Git 仓库，基础文件已添加到暂存区。

**首次提交建议**：
```bash
git commit -m "chore: 初始化项目结构

- 创建标准 Git 项目结构
- 设计技术路线与实施方案
- 创建程序层次结构
- 配置开发环境（requirements.txt, pyproject.toml）
- 创建 Cursor Rules
"
```

---

**初始化完成时间**：2025-01-XX  
**项目版本**：0.1.0  
**维护者**：Mapoet


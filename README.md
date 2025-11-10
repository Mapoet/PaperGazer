# PaperGazer

**CNS + arXiv 每日巡检与 OA 全文抓取系统**

PaperGazer 是一个自动化论文监控与抓取系统，支持每日巡检 arXiv 预印本和 CNS（Nature/Science/Cell）期刊，并按需抓取开放获取（OA）全文或非 OA 摘要。

## 功能特性

- 📡 **每日自动巡检**：定时抓取 arXiv 和 CNS 期刊最新论文元数据
- 🔍 **多源数据采集**：支持 arXiv、Crossref、Unpaywall、Europe PMC
- 📥 **智能全文抓取**：按优先级自动获取 OA PDF 或摘要
- 💾 **结构化存储**：SQLite 数据库 + 文件系统存储
- 🎯 **去重与质量控制**：自动去重、数据归一化、错误重试
- 🖥️ **命令行接口**：基于 Typer 的友好 CLI

## 技术栈

- **Python 3.11+**
- **异步 HTTP**：`httpx`
- **数据解析**：`feedparser`, `lxml`
- **配置管理**：`pydantic`, `pyyaml`
- **数据存储**：`SQLAlchemy`, `sqlite3`
- **重试机制**：`tenacity`
- **CLI 框架**：`typer`
- **任务调度**：`apscheduler` 或 `cron`

## 快速开始

### 安装

```bash
# 克隆仓库
git clone <repository-url>
cd PaperGazer

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 配置

复制并编辑配置文件：

```bash
cp configs/config.yaml.example configs/config.yaml
# 编辑 config.yaml，设置邮箱、arXiv 分类等
```

**重要配置项**：
- `mailto`: 联系邮箱（用于 Crossref/Unpaywall API，必须使用真实邮箱，不能使用 `test@example.com`）
- `arxiv.categories`: 关注的 arXiv 分类列表
- `store.db_path`: 数据库文件路径
- `store.papers_dir`: 论文文件存储目录

**注意**: 
- 配置文件 `config.yaml` 已加入 `.gitignore`，不会被提交到版本控制
- 测试时可以使用 `configs/config.test.yaml`（同样已加入 `.gitignore`）
- 参考 `configs/config.yaml.example` 了解所有可配置项

### 使用

```bash
# 每日巡检（arXiv + CNS）
python -m papergazer.cli check

# 按需抓取全文
python -m papergazer.cli fetch 10.1038/s41586-xxxx-xxxx-x
python -m papergazer.cli fetch arXiv:2501.01234

# 搜索论文
python -m papergazer.cli search --q "GNSS radio occultation"

# 导出数据
python -m papergazer.cli export --since 2025-01-01 --format csv
```

## 项目结构

```
PaperGazer/
├── papergazer/          # 主包
│   ├── sources/         # 数据源模块
│   ├── store/           # 存储模块
│   ├── core/            # 核心逻辑
│   └── cli.py           # 命令行接口
├── configs/             # 配置文件
├── data/                # 数据目录（gitignore）
├── tests/               # 测试代码
├── docs/                # 文档
├── scripts/             # 工具脚本
└── requirements.txt     # Python 依赖
```

## 数据源

- **arXiv**：官方 Atom API（无需授权）
- **Crossref**：REST API（需邮箱）
- **Unpaywall**：OA 状态查询（需邮箱）
- **Europe PMC**：全文 XML 获取（无需授权）

## 开发

```bash
# 运行测试
pytest tests/

# 代码格式化
black papergazer/
isort papergazer/

# 类型检查
mypy papergazer/
```

## 许可证

[待定]

## 作者

Mapoet


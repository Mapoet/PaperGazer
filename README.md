# PaperGazer

**Toward an integrated scientific literature intelligence platform**

PaperGazer 自动化地巡检、抓取并分析科研论文元数据与全文，在统一的数据底座上完成计量学、NLP、知识图谱与长文档问答所需的关键步骤。

---

## 核心能力

- 📡 **每日巡检管线**：支持 arXiv、Crossref、OpenAlex、Europe PMC、Unpaywall 等来源，按时间窗口自适应分批抓取，RunRecord 记录游标并自动增量。
- 🧭 **多源元数据补全**：整合 Crossref/OpenAlex/Unpaywall API，补齐引用、基金、许可、OA 状态、概念标签、引用网络等结构化字段。
- 📑 **全文结构化处理**：可选对接 GROBID 生成 TEI，内置 TEI 图表解析、pdffigures2/Table-Transformer 抽取图像与表格结构。
- 🧬 **身份识别与语义增强**：支持 ORCID/ROR 标准化作者与机构，串联概念热度、OA/FAIR 指标、引用网络等分析模块。
- 🖥️ **统一 CLI 工作流**：`daily_ingest.py`、`analyze_papers.py`、`query_papers.py`、`export_abstracts.py` 提供巡检、分析、检索、导出的一体化体验。
- 🧰 **可组合的核心模块**：`papergazer.core`、`papergazer.analytics`、`papergazer.utils` 暴露可复用函数，支持脚本与服务化集成。

---

## 架构总览

```
┌──────────────────────┐
│      CLI / Scripts    │  daily_ingest / analyze / query / export
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│     Core Pipelines    │  ingest · fetch · fulltext · figures · identity
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│  Analytics Modules    │  citation · concepts · OA dashboards
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│   Data Access Layer   │  utils.metadata · download · db_filters
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│     External APIs     │  arXiv · Crossref · OpenAlex · Unpaywall · Europe PMC · ORCID · ROR
└──────────────────────┘
```

数据存储由 SQLite + 文件系统组成，`PaperItem` 主表扩展了 TEI、图表、概念、引用、身份等列，`RunRecord` 保留游标与运行摘要以支持可追溯的增量流程。

---

## 快速上手

### 1. 安装环境

```bash
git clone <repository-url>
cd PaperGazer
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 准备配置

```bash
cp configs/config.yaml.example configs/config.yaml
# 然后编辑 config.yaml，填入邮箱、数据源分类、存储目录等
```

关键配置节：

- `mailto`: 用于 Crossref / Unpaywall / OpenAlex 的邮箱（必须真实）。
- `arxiv.categories`: 巡检的 arXiv 分类（可覆盖 geoscience、remote sensing、AI 等学科）。
- `journals.*`: 按 print / online ISSN 组织的期刊集合，可扩展任意同领域期刊。
- `grobid`, `figures`, `identity`: 控制全文解析、图表抽取、ORCID/ROR 匹配等高级流程。
- `store.db_path` / `store.papers_dir`: 数据库与全文存储路径。

`configs/config.test.yaml` 便于本地调试，已加入 `.gitignore`。

### 3. 初始化数据库

任一 CLI 脚本都会调用 `papergazer.store.db.init_db`；首次运行时会自动建表并执行轻量级列迁移，无需手工干预。

---

## 常用工作流

### 每日巡检与元数据补全

```bash
# 巡检全部数据源（含自动分批、RunRecord 游标）
python scripts/daily_ingest.py --days 7

# 巡检 + 下载 OA/fulltext + 后处理（TEI / 图表 / 引用网络）
python scripts/daily_ingest.py --days 7 --download \
  --post-tei --post-figures --post-citation --post-dry-run

# 仅补全元数据（Crossref / OpenAlex / Unpaywall）
python scripts/daily_ingest.py --enrich-metadata --enrich-limit 500
```

### 分析与导出

```bash
# 组合分析（作者 / 期刊 / OA / 概念）
python scripts/analyze_papers.py authors venues oa concepts 30 \
  --window-days 60 --top 20 --concept-dry-run --oa-dry-run

# 导出指定时间段的摘要（支持作者/关键词过滤）
python scripts/export_abstracts.py --days 30 --keyword "GNSS" \
  --output exports/gnss_abstracts.md

# 查询模式：days / author / venue / keyword
python scripts/query_papers.py days 7
python scripts/query_papers.py author "Smith" --limit 20
```

所有 CLI 均支持 `--config` 切换配置、`--verbose` 输出详细日志。

---

## 项目结构

```
papergazer/
├── analytics/          # Citation graph · concept trends · OA dashboards
├── core/               # ingest · fetch · fulltext · figures · identity
├── sources/            # arxiv · crossref · openalex · unpaywall · europe_pmc
├── store/              # SQLAlchemy models · migrations · file helpers
├── utils/              # metadata · download · db_filters · logging
└── config.py           # Pydantic settings (YAML)

scripts/
├── daily_ingest.py     # 巡检 + 下载 + 元数据补全 + 后处理
├── analyze_papers.py   # 作者/期刊/OA/概念等组合分析
├── query_papers.py     # days / author / venue / keyword 查询
└── export_abstracts.py # Markdown 摘要导出

docs/                   # 路线图、规范、操作手册
configs/                # YAML 配置（example + 本地/测试）
data/                   # 数据库存档与全文目录（gitignore）
```

---

## 开发与质量

```bash
# 单元 / 集成测试
pytest tests/ -v

# 代码格式化
black papergazer scripts
isort papergazer scripts

# 类型检查
mypy papergazer

# 静态检查（可选）
ruff check papergazer scripts
```

推荐阅读：

- `.cursorrules` —— 代码规范、模块职责、API 约束。
- `docs/INTELLIGENT_PLATFORM_ROADMAP.md` —— 总体路线图。
- `docs/INTELLIGENT_PLATFORM_ACTION_PLAN.md` —— 阶段性建设计划。
- `docs/PROJECT_COLLAB_SETUP.md` —— 协同流程与看板约定。

---

## 许可证与贡献

- 许可证：MIT（见 `LICENSE`）
- 维护者：Mapoet（欢迎 Issue / PR / Feature Request）

PaperGazer 已具备构建领域专题图谱、开放获取评估、长文档 QA 等上层应用所需的核心能力。欢迎基于现有模块扩展更多科研工作流。 


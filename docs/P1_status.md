## P1 阶段执行状态（已完成）

### 1. 全文批处理能力 ✅
- `papergazer/core/fulltext.generate_tei_for_papers` 负责批量生成 TEI，并写回 `PaperItem.tei_path`。  
- `papergazer/core/figures.extract_figures_and_tables` 从 TEI 中抽取图表结构，持久化到 `figures_json` / `tables_json`。  
- 配置文件新增 `grobid.*` / `figures.*`，支持 dry-run、force、最大处理量等参数。

### 2. 外部元数据补全 ✅
- `papergazer/utils/metadata` 统一封装 Crossref / OpenAlex / Unpaywall 增量抓取，RunRecord 持续保存游标与摘要。  
- `scripts/daily_ingest.py` 内建 `--enrich-*` 参数，可结合巡检一次完成元数据补充。  
- 数据库 `PaperItem` 增加 `crossref_json`、`openalex_json`、`references_json` 等字段，以结构化方式存储补全结果。

### 3. 身份与引用增强 ✅
- `papergazer/core/identity_enrich.enrich_identities` 对接 ORCID / ROR v2，写入 `identities_author`、`identities_affiliation`。  
- `papergazer/analytics/citation.build_citation_graph` 基于 `references_json` 构建 `graphs_citation` 表，支持 dry-run、重建、本地 DOI 匹配。

## P2 阶段执行状态（分析能力）

### 1. 语义向量与相似文献 ✅
- `papergazer/core/embeddings.generate_embeddings_for_papers` 生成语义向量并存储于 `embeddings` 表，支持标题/摘要/TEI 组合。  
- `scripts/generate_embeddings.py` 作为轻量入口，提供 `--model`、`--fields`、`--since-days`、`--dry-run` 等选项。

### 2. 主题演化 ✅
- `papergazer/analytics/topics.analyze_topic_trends` 基于 OpenAlex concepts 统计年/季度趋势，输出 Top-N 增长主题及完整时间序列。  
- `scripts/analyze_papers.py` 新增 `topics` 分析类型，可配置粒度 (`--topics-granularity`) 与跨度 (`--topics-since-years`)。

### 3. 引用与合作网络 ✅
- `papergazer/analytics/citation.summarize_citation_network` 使用 networkx 计算 PageRank / 入度 Top 节点。  
- `papergazer/analytics/citation.analyze_collaboration_network` 基于标准化机构信息得出合作边列表。  
- CLI 新增 `citation`、`collaboration` 分析类型，输出富表格结果。

### 4. OA/FAIR 指标 ✅
- `papergazer/analytics/oa.monitor_oa` 统计 OA 占比、许可分布、数据/代码链接并可持久化至 `analytics_oa`。  
- `scripts/analyze_papers.py` 的 `oa` 分析支持窗口调整、dry-run、数据库写入。

## 后续建议
- **语义检索**：在 `papergazer/core/embeddings` 之上实现相似论文检索接口，服务化供 API/前端使用。  
- **主题深化**：结合语义向量接入 BERTopic / 主题突变检测，将热点演化写入 dashboards。  
- **可视化与仪表盘**：基于 `analytics_*` 表构建 Superset/Metabase 图表，形成日常监测面板。  
- **长文档 QA**：利用 TEI、图表 JSON、语义向量构建证据仓，为 P3/P4 的问答与综述自动化奠定基础。
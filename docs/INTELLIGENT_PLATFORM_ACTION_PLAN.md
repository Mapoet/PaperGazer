## PaperGazer 平台建设行动方案

> 目标：将《INTELLIGENT_PLATFORM_ROADMAP.md》的蓝图细化为可执行的建设任务，明确阶段、子任务、产出物与依赖关系，保障在 3–6 个月内搭建“计量学 + NLP + 知识图谱 + 长文档 QA”一体化平台。

---

### 全局规划

| 阶段 | 时间（建议） | 核心目标 | 关键产出 |
|------|--------------|----------|----------|
| P0：准备 | 周 0 | 团队协同框架、现状评估、数据抽样 | 项目计划、现有库审计报告 |
| P1：数据底座 | 周 1–6 | 外部元数据补全、OA 状态、全文结构化、作者/机构标准化 | 扩展字段、GROBID TEI、ORCID/ROR 映射 |
| P2：分析能力 | 周 7–12 | 语义向量、主题演化、引用网络、OA/FAIR 指标 | 向量库、分析脚本、仪表盘初版 |
| P3：知识层 & QA | 周 10–16 | 知识图谱、表格抽取、证据仓、长文档 QA | 三元组/表格仓、QA Demo |
| P4：专题化产品 | 周 13–18 | GNSS/电离层专题图谱与复现力报告、综述机器人 | 专题可视化、自动综述模块 |
| P5：运营化 | 周 16+ | 数据增量、指标监控、日志审计、权限安全 | 定期 ETL、监控告警、API 服务 |

> 阶段交叉进行：例如 ORCID/ROR 匹配可在 P1 后半并行；QA Demo 可在 P3 试运行，P4 针对特定领域固化。

---

### P0：准备工作（Week 0）

1. **团队与协作框架**
   - 建立任务板（Trello/JIRA）与文档库（Notion/Docs）。
   - 明确责任分工：数据工程、后端、NLP、可视化、DevOps。
2. **现状评估**
   - 随机抽取 200 条 `PaperItem`，核对字段完整性、doi 缺失比例、PDF 下载成功率。
   - 检查已有脚本、日志、数据目录结构。
3. **环境准备**
   - Docker 化 GROBID（可选），准备 ORCID/ROR/OpenAlex/Crossref API Key 或 mailto。
   - 评估目标数据库（如迁移至 PostgreSQL + JSONB 以提升扩展性）。

---

### P1：数据底座建设（Weeks 1–6）

#### 1. Crossref/ OpenAlex/ Unpaywall ETL
1. 设计增量策略  
   - Crossref：`from-pub-date` + 游标；OpenAlex：`updated_date`；Unpaywall：每日增量或全量快照。
2. 实现 `scripts/ingest_crossref_metadata.py`：  
   - 输入游标/日期，输出 `references_json`, `funder_json`, `license_json`, `source_type` 等。
3. 实现 `scripts/ingest_openalex.py`：  
   - 补齐 `is_oa`, `host_venue`, `concepts_json`, `referenced_work_ids`, `cited_by_count`。
4. 实现 `scripts/ingest_unpaywall.py`：  
   - 更新 `oa_status`, `oa_best_location`, `oa_pdf_url`, `oa_license`。
5. 写入 `RunRecord` 控制增量；保存 API 响应摘要日志。

#### 2. GROBID + 全文结构化
1. 配置 `grobid.enabled`、`base_url`；部署 Docker 服务。
2. 开发 `scripts/process_fulltext_batch.py`：  
   - 扫描 `PaperItem` 中无 `tei_path` 的记录 → 调 `process_fulltext_document` → 保存 TEI → 更新数据库。
   - 支持 `--since-days`, `--limit`, `--retry` 参数。
3. Todo：设计任务队列表（`fulltext_jobs`）记录状态（待处理、成功、失败）。
4. 执行首轮批处理（例如 5k PDF），记录耗时与失败样本。

#### 3. 图表抽取
1. 选型：`pdffigures2`（图/表位置信息）与 `Table-Transformer`（结构化表格）。
2. 实现 `scripts/extract_figures_tables.py`（✅ 已上线 dry-run/force/max-limit）：  
   - 输入 `tei_path` 与原 PDF → 输出图表 JSON（路径、标题、说明、坐标）。
3. 定义 JSON schema：`figures_json`, `tables_json`（已写入 `PaperItem`）。

#### 4. ORCID/ ROR 对接
1. 编写 `utils/identity.py`（✅ 已实现缓存与搜索封装）：  
   - 名称标准化、请求 ORCID Search (`/expanded-search`)、ROR v2 (`/organizations?query=`)。  
   - 内建缓存（SQLite/JSON 文件）。
2. 新增表：`identities_author`, `identities_affiliation`（✅ 自动迁移完成）；
   - 字段：`paper_id`, `local_index`, `source_name`, `matched_name`, `orcid/ror_id`, `confidence`, `metadata`。
3. 编写 `scripts/enrich_identities.py`（✅ 支持 dry-run/force/source 过滤）：  
   - 支持 `--since`, `--limit`, `--sources`，执行批量匹配。  
   - 记录无法匹配的清单，回显到终端供人工修正。

---

### P2：分析能力建设（Weeks 7–12）

#### 1. 语义向量与相似文献 ✅
1. **已完成**：`papergazer/core/embeddings.generate_embeddings_for_papers` 支持基于标题/摘要/TEI 生成语义向量，写入 `embeddings` 表。  
2. **脚本入口**：`scripts/generate_embeddings.py` 作为轻量包装，支持 `--model`、`--fields`、`--since-days` 等参数。  
3. **后续可拓展**：基于生成的向量实现近邻检索接口（规划在 P3 阶段纳入 `services/similarity`）。

#### 2. 主题演化 ✅
1. **已完成**：`papergazer/analytics/topics.analyze_topic_trends` 基于 OpenAlex concepts 计算年/季度趋势，返回 Top-N 增长主题及完整时间序列。  
2. **CLI 集成**：`scripts/analyze_papers.py` 新增 `topics` 分析类型，可配置时间粒度与统计跨度。  
3. **后续建议**：结合语义向量做 BERTopic 聚类或主题突变检测（留待 P3/P4）。

#### 3. 引用网络与合作网络 ✅
1. **已完成**：在 `papergazer/analytics/citation` 中新增 `summarize_citation_network`（networkx PageRank / 入度指标）及 `analyze_collaboration_network`（基于 ROR/机构对组成合作边）。  
2. **CLI 集成**：`scripts/analyze_papers.py` 新增 `citation`、`collaboration` 分析类型，输出富表格指标。  
3. **后续建议**：结合 `AuthorIdentity` / `AffiliationIdentity` 扩展国家区域聚合与社区发现。

#### 4. OA/FAIR 指标 ✅
1. **已完成**：`papergazer/analytics/oa.monitor_oa` 统计 OA 状态、许可分布、数据/代码链接并可持久化到 `analytics_oa`。  
2. **CLI 集成**：`scripts/analyze_papers.py` 中 `oa` 分析类型支持窗口配置、持久化写入。  
3. **后续建议**：基于指标输出 Superset/Metabase Dashboard，纳入 FAIR checklist 评分。

---

### P3：知识图谱 & 长文档 QA（Weeks 10–16）

#### 1. 知识抽取
1. 利用 SciSpacy、正则或自定义模型，从 TEI 中抽取“任务-方法-数据-指标”等实体。  
2. 定义三元组表：`knowledge_triples(paper_id, subject, predicate, object, evidence_span, confidence)`。
3. 设计简单评估集，人工审核样本。

#### 2. 表格/图注证据仓
1. 对 `tables_json`、`figures_json` 做 schema 清洗，提取指标-数值-单位。  
2. 建立 `evidence_blocks` 表，记录证据类型、位置、引用字段。  
3. 与知识抽取结果关联（如某指标对应的表格行）。

#### 3. 长文档 QA MVP
1. 搭建 RAG 管线：  
   - 检索：BM25 + 向量检索混合；  
   - 读取：LLM（长上下文）或多段生成。  
2. 评测：使用 QASPER 结构构建内部问答集；计算准确率、证据覆盖率。  
3. 输出 Demo 服务（REST/CLI），“输入问题 → 返回答案 + 证据片段”。

---

### P4：专题化产品（Weeks 13–18）

以 GNSS/电离层为例：

1. **专题数据编排**  
   - OpenAlex + 内部库过滤主题（概念/关键词），构建专题文献清单。
2. **专题图谱**  
   - 生成方法谱系图、机构合作图、年度热词/主题迁移图。  
   - 自动推荐关键 SOTA 指标表格。
3. **综述机器人**  
   - 按 PRISMA 记录检索与筛选流程。  
   - 输出包含结论、证据、图表的综述文档。
4. **复现力评分**  
   - 综合 OA、数据/代码链接、方法描述结构化程度，生成可视化报告。

---

### P5：运营与保障（Week 16+ 持续）

1. **自动化**  
   - 定时任务（cron/Workflow）维护增量 ETL、GROBID、向量更新。  
   - 监控 API 调用失败、数据延迟。
2. **版本与审计**  
   - 数据版本管理（加 `ingested_at`, `updated_at` 字段）。  
   - 保留 ETL 日志与原始 JSON 快照，便于重跑。
3. **开放接口与权限**  
   - 对外提供标准 API 或数据导出；  
   - 权限层控制（例如 ORCID/ROR 数据需要授权访问）。
4. **质量反馈**  
   - 建立人工审查流程，定期抽样验证匹配准确率、知识抽取质量。

---

### 里程碑检查表

- ✅ `P1` 完成：数据字段完整、TEI 可用、图表 JSON 生成、作者/机构已匹配。  
- ✅ `P2` 完成：相似文献检索、主题演化、OA/FAIR 仪表盘上线。  
- ✅ `P3` 完成：三元组/证据仓落地、QA Demo 可回答事实性问题。  
- ✅ `P4` 完成：至少一个专题（GNSS/电离层）产出可视化与自动综述。  
- ✅ `P5` 完成：定期 ETL、监控告警、数据导出流程稳定运行。

---

### 建议协作工具

- **数据存储**：PostgreSQL（JSONB + 向量拓展）或 DuckDB + Parquet 备份  
- **任务调度**：Airflow / Prefect / Dagster  
- **可视化**：Metabase / Superset / Grafana  
- **知识图谱**：Neo4j / ArangoDB / RDF Store（视需求）  
- **向量搜索**：Faiss / Milvus / qdrant  
- **模型服务**：HuggingFace Transformers、LangChain、Ray Serve

---

> 此行动方案需结合团队实际资源进行时间与任务调整。若并行实施多个阶段，需确保变更管理与数据质量控制同步推进，避免对现有服务造成影响。



## PaperGazer 一体化平台实施指南

> 目标：以现有的 `PaperItem` 主表 + 全文（PDF/TEI）为核心，构建贯穿 **计量学 → NLP → 知识图谱 → 长文档 QA** 的科研数据底座。

---

### 1. 数据底座加厚

| 模块 | 任务 | 实施要点 | 对应字段（建议） |
|------|------|-----------|-------------------|
| Crossref 元数据 | 拉取出版日期、来源类型、基金资助、参考文献、许可证等 | 使用 `/works` 接口，支持 `filter=from-pub-date` + 游标分页，解析 `relation`, `funder`, `license`, `reference` | `published_date`, `source_type`, `funder_json`, `license_json`, `references_json` |
| OpenAlex 补充 | 同步 `is_oa`, `host_venue`, `concepts`, `referenced_works`, `cited_by_count` | 快照（S3/BigQuery）或 API (`/works?filter=from_publication_date`)；按 `ids` 或 `doi` 批量匹配 | `is_oa`, `host_venue`, `concepts_json`, `referenced_work_ids`, `cited_by_count` |
| Unpaywall OA | 获取 `is_oa`, `oa_locations`, `oa_pdf_url`, `license` | `/v2/<doi>` 支持批量（配 rate limit）；与 OpenAlex OA 字段交叉验证 | `oa_status`, `oa_best_location`, `oa_pdf_url` |
| GROBID 全文 | 产出 `tei_path`, 分节、参考文献、附录等 | 已实现 `process_fulltext_document`；批量时可写任务队列，成功后更新数据库 | `tei_path`, `tei_metadata_json` |
| 图表抽取 | Table-Transformer（PubTables-1M）/pdffigures2 抽取表格、图注 | 对 TEI 或 PDF 的页面坐标做跨模态映射，保存结构化 JSON | `tables_json`, `figures_json` |
| 作者/机构标识 | ORCID + ROR v2 | 解析 `authors_json`，调用 ORCID Search, ROR API (`/organizations?query=`)，落库置信度与原始名称 | `author_identities`, `affiliation_identities` |

> **幂等性**：以 `doi` 为主键；若无 DOI，则以 `(source, identifier)`。`hash` 字段用于 PDF 重复检测。

---

### 2. ETL 设计建议

1. **Crossref / OpenAlex / Unpaywall**
   - 统一封装 `async` 客户端，支持 `mailto` 与重试。
   - `RunRecord` 存储游标（如 `last_pub_date`）；每次成功批处理后更新。
   - 对引用数据（参考文献、引用链接）定期全量刷新，或以差量/增量方式拉取。

2. **GROBID & 全文处理**
   - 开关控制：`grobid.enabled=false` 时跳过。
   - 处理流程：下载 PDF → 调用 `process_fulltext_document` → 存储 TEI → 抽解析度数据。
   - 建议编排批处理脚本 `scripts/process_fulltext_batch.py`，支持失败重试与断点续跑。

3. **识别缓存层**
   - ORCID / ROR 调用结果写入缓存表或 `sqlite` 文件，避免重复请求。
   - 可配置缓存 TTL；手动修正（CSV/JSON）优先于自动匹配。

---

### 3. 分析层能力拓展

| 能力 | 说明 | 技术路线 |
|------|------|----------|
| 文档语义向量 | 文献相似度、主题聚类、推荐 | SPECTER / SPECTER2 或 SciBERT；向量存储在 `fulltext_embeddings` 或外部向量库 |
| 主题演化 & 波动 | 年度主题分布、突变检测 | BERTopic、OpenAlex Concepts，配合时间序列分析 |
| 引用网络 | PageRank、社区发现、方法谱系 | 基于 `referenced_work_ids` 构建图；NetworkX / igraph / Neo4j |
| FAIR/OA 指标 | OA 占比、许可类型、延时 OA、数据/代码引用 | 使用 Crossref `relation`, `link`, `is-referenced-by-count`，结合 FAIR 原则 |
| 综述自动化 | PRISMA 流程 + 证据表 | 记录检索、筛选、纳入步骤日志；利用 TEI/表格抽取构建证据表 |

---

### 4. 知识图谱与问答

1. **实体抽取与三元组**
   - 使用 SciSpacy 或自研模型从 TEI 段落抽取“任务-方法-数据-指标”等。
   - 安装自定义 schema（可借鉴 ORKG），存入 `extractions` 表。

2. **表格/图注证据仓**
   - 表格结构化后提取关键指标（如 Accuracy、RMSE）。配合图注识别实验条件。
   - 为综述、评测、QA 提供高置信度证据块。

3. **长文档 QA 管线**
   - 检索：段落向量或 BM25；
   - 聚合：证据段落排序；
   synthesizer：Long-context LLM、RAG、多跳推理；
   - 评测：QASPER/CrisisQA 等数据集，记录准确率与可解释性。

---

### 5. 数据库扩展建议

| 表/列 | 说明 |
|-------|------|
| `items` 扩展 | `references_json`, `funder_json`, `license_json`, `host_venue_json`, `concepts_json`, `oa_json`, `tei_path`, `tables_json`, `figures_json`, `author_identities` |
| `fulltext` | 存 TEI/段落/句向量，按 `paper_id` 分片 |
| `identities_author` | `paper_id`, `local_author_idx`, `orcid`, `confidence`, `matched_name`, `matched_affiliation` |
| `identities_affiliation` | `paper_id`, `local_affiliation_idx`, `ror_id`, `confidence`, `matched_name`, `country_code`, `lat`, `lon` |
| `graphs_citation` | `source_paper_id`, `target_paper_id`, `relation_type`, `weight` |
| `analytics_metrics` | 预计算指标（OA 比例、SOTA 统计等，可用于仪表盘） |

---

### 6. 七天冲刺计划（最小闭环）

| 天数 | TODO |
|------|------|
| Day 1 | 实现 Crossref/OpenAlex/Unpaywall 增量脚本，补齐 OA、引用、概念字段 |
| Day 2 | 运行 GROBID 批处理，产出 TEI；抽取表格/图注样例 |
| Day 3 | 生成文档向量（SPECTER2），完成相似文献 Demo |
| Day 4 | 构建引用网络和机构合作图，完成初步分析 |
| Day 5 | ORCID/ROR 匹配 MVP，写入新表；验证匹配质量 |
| Day 6 | 选定主题（如 GNSS-RO）做自动综述原型（PRISMA 流程 + 证据表） |
| Day 7 | 输出可视化与报告，整理下一阶段任务（知识图谱 / QA） |

---

### 7. 参考文献 & 资源

- Crossref REST API 文档（works、filter、使用 tips）  
- OpenAlex API & 快照文档  
- Unpaywall API & 快照  
- ROR API v2、ORCID Search API  
- GROBID 文档、Table-Transformer (PubTables-1M)、pdffigures2  
- SPECTER/SPECTER2 论文与模型，BERTopic  
- FAIR 原则、PRISMA 2020、QASPER 数据集  
- SciSpacy、ORKG 相关仓库  

以上文档建议保留在项目 Wiki/Docs 中，作为团队协作的实施基准。根据业务重点可对列展开详细的开发任务说明或对应的 CLI/Pipeline。



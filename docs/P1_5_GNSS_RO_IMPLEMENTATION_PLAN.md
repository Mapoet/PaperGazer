# PaperGazer P1.5 工程收敛与 GNSS-RO 专题闭环计划

## 1. 目标与验收口径

采用“双轨收敛”路线：前 3 周关闭工程、数据质量和全库存运行风险，第 4–8 周完成 P2 产品接口和 GNSS-RO 气象专题闭环。

- 保留 SQLite，建立可迁移的数据契约；本轮不引入 PostgreSQL、Qdrant、Neo4j 或重型调度平台。
- 交付形态为 CLI + 中文 Markdown/HTML 静态报告。
- QA 使用 OpenAI 兼容接口；未配置模型时仍能完成检索和证据报告。
- 第一专题固定为 GNSS-RO 气象、商业星座数据质量和数值天气同化。

最终验收：

1. Python 3.11/3.12 CI 全部通过。
2. 全库存可断点、可重试、可审计地处理完毕。
3. 自动生成全库存数据质量报告。
4. 可按论文和自然语言查询执行相似文献检索。
5. 可生成 GNSS-RO 气象专题趋势、机构网络、证据表和中文报告。
6. 窄域 QA 能回答数据源、同化方法、验证资料和性能指标，并返回论文、章节和证据文本。
7. 文档状态与实际验收结果一致，不再用“函数存在”代替“阶段完成”。

## 2. 阶段 0：保护分支并建立可信基线（第 1–2 天）

- 审查 `dev-codex` 当前改动，将提交拆分为工程化、格式化、HTTP、自动化等独立主题。
- 建立 Python 3.11/3.12 独立环境；Python 3.8 明确标为不支持。
- 运行离线 pytest、Ruff、mypy、wheel 构建和安装 smoke test，保存初始失败清单。
- 检查现有测试库和生产配置位置，不修改原始数据库；所有迁移先在副本验证。
- 将 P1–P5 状态改为 `planned/scaffolded/implemented/verified/operational` 五级。

验收：wheel 包含全部 `papergazer.*` 子包；CLI 可在干净环境启动；基线报告记录测试、类型、数据库版本和阻断项。

## 3. 阶段 1：工程基础与数据安全（第 1 周）

### 3.1 包、依赖和质量门禁

- 以 `pyproject.toml` 为唯一依赖真源，`requirements.txt` 作为兼容导出。
- `lxml` 为必需依赖；`networkx`、`sentence-transformers` 分别进入 extras。
- CI 覆盖 Python 3.11/3.12、离线测试、Ruff、mypy、wheel 构建和 clean-install。
- Ruff 保持零错误；mypy 优先覆盖模型、数据源、存储和 ingest 主链。

### 3.2 SQLAlchemy 与迁移

- ORM 更新为 SQLAlchemy 2 的 `Mapped[]/mapped_column()`。
- 引入 Alembic，建立当前 schema 基线和旧 SQLite 兼容迁移。
- 迁移前备份，迁移后校验行数、约束、索引和 schema revision。
- 移除运行时无版本 `_ensure_schema()`；只保留一次性 legacy bridge。
- 为新增表和派生 JSON 建立 schema version。

### 3.3 HTTP 与配置

- 统一 HTTP 超时、代理、重试、User-Agent 和限速配置。
- `trust_env` 默认开启，可通过 YAML 关闭。
- 对 429、`Retry-After`、连接/读取超时、5xx 和无效 JSON 分类记录。
- 日志不得输出 API key、完整授权头或敏感配置。

验收：旧数据库升级后数据不丢失；重复迁移无副作用；HTTP 策略有离线测试；CI 工程门禁全部通过。

## 4. 阶段 2：全库存 P1 数据质量验收（第 2–3 周）

### 4.1 运行与任务状态

```python
RunStatus = Literal[
    "pending", "running", "succeeded", "partial", "failed", "cancelled"
]

JobStatus = Literal[
    "pending", "running", "succeeded", "retryable", "dead"
]
```

新增表：

- `pipeline_runs`：运行范围、配置摘要、代码版本、开始/结束时间和总体状态。
- `pipeline_jobs`：论文、处理阶段、尝试次数、下次重试时间、错误分类。
- `data_quality_snapshots`：审计指标、分子、分母和生成版本。
- `manual_corrections`：ORCID/ROR、专题标签和证据的人工覆盖值。

行为要求：

- 各数据源和处理阶段故障隔离。
- checkpoint 使用远端 cursor、时间戳和稳定标识符组合。
- 相同时间戳跨页不得漏数；重复记录由幂等 upsert 吸收。
- 进程中断后只重跑未成功任务。
- 永久失败进入 dead-letter 清单，不阻塞其余库存。

### 4.2 CLI

```bash
papergazer audit inventory
papergazer pipeline run --stage metadata --all
papergazer pipeline run --stage fulltext --all
papergazer pipeline run --stage identity --all
papergazer pipeline resume <run-id>
papergazer pipeline failures <run-id>
```

### 4.3 数据质量报告

至少包含：

- 总量和来源分布。
- DOI、摘要、作者、机构和出版日期覆盖率。
- Crossref/OpenAlex/Unpaywall 补全率。
- OA 类型、PDF 下载率、TEI 和有效章节覆盖率。
- GROBID 成功率、耗时和失败分类。
- ORCID/ROR 匹配率、置信度和人工抽样准确率。
- 引用边、概念、图表和向量覆盖率。
- 重复 DOI/PDF、非法日期、孤立文件。
- 与上一次审计的变化。

验收：全库存论文都有终态任务；失败项可导出、重试和追溯；完成 200 篇分层人工抽样；报告可重复生成且分母明确。

## 5. 阶段 3：P2 产品化接口（第 4–5 周）

### 5.1 相似文献检索

首版使用 SQLite + NumPy cosine 检索，不引入独立向量数据库。

```python
def similar_papers(
    paper_id: int,
    *,
    model_name: str,
    top_k: int = 10,
    filters: SimilarityFilters | None = None,
) -> list[SimilarityHit]: ...
```

```bash
papergazer similar --paper-id 123 --top 10
papergazer similar --query "commercial GNSS-RO data assimilation" --top 20
```

结果返回论文、相似度、模型、参与字段和过滤条件；缺失或维数不一致的向量必须显式报错。

### 5.2 趋势、网络和报告

```bash
papergazer trends --topic gnss-ro --granularity quarter
papergazer network institutions --topic gnss-ro
papergazer report metrics --topic gnss-ro
```

- OpenAlex Concepts 与领域词表联合过滤。
- 计算年度/季度趋势、增长率和最小样本阈值。
- 输出 PageRank、入度、机构合作边和基础社区发现。
- OA/FAIR 使用明确评分规则。

报告目录：

```text
reports/<topic>/<run-date>/
├── report.md
├── report.html
├── data_quality.json
├── papers.csv
├── trends.csv
├── institutions.csv
└── figures/
```

验收：检索结果可复现；趋势避免小样本虚假增长；网络节点可回溯论文；报告数字可追踪到 CSV/JSON。

## 6. 阶段 4：GNSS-RO 气象专题数据模型（第 5–6 周）

建立版本化专题词表：

- 技术：GNSS-RO、radio occultation、RO、掩星。
- 任务：COSMIC、COSMIC-2、MetOp、Spire、PlanetIQ、FY-3 等。
- 产品：弯曲角、折射率、温度、湿度、气压、电子密度。
- 方法：1D-Var、3D-Var、4D-Var、EnKF、混合同化。
- 应用：NWP、热带气旋、天气预报和气候监测。
- 指标：bias、RMSE、STD、forecast impact、anomaly correlation。
- 验证源：radiosonde、reanalysis、NWP background/analysis 和卫星交叉验证。

新增实体：

```python
TopicDefinition
ScreeningDecision
EvidenceBlock
MetricObservation
DatasetMention
MissionMention
MethodMention
```

规则：

- 关键词命中只生成候选，不直接纳入。
- 每篇候选记录检索式版本、纳入/排除原因和人工覆盖值。
- 证据块保存论文、TEI 章节、位置、原文和规范化字段。
- 指标保存值、单位、实验条件和证据位置；无法确定时不得推断。

```bash
papergazer topic build gnss-ro-weather
papergazer topic screen gnss-ro-weather
papergazer evidence extract gnss-ro-weather
papergazer topic report gnss-ro-weather
```

验收：形成版本化候选/纳入/排除集；人工审核至少 100 篇；报告专题 precision/recall；结构化指标均可定位原始证据。

## 7. 阶段 5：窄域证据 QA（第 7 周）

仅支持：数据或卫星任务、同化/反演方法、验证资料、性能指标及条件。

数据流：

```text
问题分类
→ BM25/关键词候选召回
→ 向量重排
→ EvidenceBlock 过滤
→ OpenAI 兼容模型生成
→ 引用完整性校验
→ 答案 + 证据
```

```python
def answer_question(
    question: str,
    *,
    topic: str = "gnss-ro-weather",
    model: LLMConfig | None = None,
    top_k: int = 8,
) -> EvidenceAnswer: ...
```

`EvidenceAnswer` 包含 `answer`、`question_type`、`citations`、`evidence_blocks`、`confidence`、`abstained` 和 `model_metadata`。

- 未配置模型时返回排序证据，不生成综合答案。
- 证据不足或冲突时拒答。
- 每个事实性句子至少对应一个证据块。
- 默认中文回答，保留英文题名、术语和原始证据。
- API key 仅从环境变量或未跟踪配置读取。

```bash
papergazer qa ask "商业GNSS-RO数据对数值天气预报有什么影响？"
papergazer qa evaluate --dataset tests/fixtures/qa/gnss_ro.jsonl
```

验收：不少于 50 个专家审查问题；报告答案正确率、证据召回率、引用正确率和拒答准确率；无证据问题不得生成确定性结论。

## 8. 阶段 6：运营化与文档收口（第 8 周）

- 将 `weekly.sh` 收敛为 `papergazer weekly-report`，shell 仅作兼容入口。
- 每次 cron 运行产生唯一 `run_id`，记录阶段状态和报告路径。
- 连续失败、库存延迟、磁盘不足和 dead-letter 增长通过日志及非零退出码暴露。
- 提供备份、恢复、迁移前检查和失败回滚手册。
- README 只描述已验证能力；规划和状态文档分别维护。
- 归档互相矛盾的完成报告，建立统一 `PROJECT_STATUS.md`。

## 9. 兼容策略

- 现有脚本保留一个发布周期，内部改用服务层并输出弃用提示。
- Typer 成为唯一正式 CLI，脚本不再拥有独立业务逻辑。
- OpenAlex 归类为 enrichment provider，不声明当前不存在的 discovery source。
- 原 `items` 表继续可读；新增结构化表通过 `paper_id` 关联。
- 原始 API JSON 保留，派生字段记录生成版本。
- 专题词表、筛选规则、模型名称和报告配置写入运行摘要。
- repository/service 边界不得依赖 SQLite 专有查询语义，为未来迁移保留空间。

## 10. 测试与全库存验收

### 单元和契约测试

- 各外部 API 使用固定响应 fixture。
- 覆盖 429、`Retry-After`、超时、5xx、空页、重复 cursor 和非法 JSON。
- 覆盖同时间戳跨页、迟到数据、重复 DOI 和无 DOI 记录。
- 覆盖损坏 TEI、空表格、坐标缺失、身份同名和低置信度。
- 覆盖向量缺失、维度冲突、模型变化、证据冲突和 QA 拒答。

### 集成测试

- 临时 SQLite 完成发现、补全、下载、TEI、身份、向量和报告链路。
- 旧数据库副本升级并验证行数和约束。
- 中断运行后恢复，不重复成功任务。
- 单数据源失败不阻断其他来源。
- CLI 从 clean install 环境运行。

### 全库存验收

- 每个阶段保存 `run_id`、配置摘要、代码 commit 和终态统计。
- 处理前后核对数据库行数和文件数量。
- 200 篇分层数据质量抽样。
- 100 篇 GNSS-RO 专题筛选抽样。
- 50 个窄域 QA 专家评测问题。

## 11. 明确边界

- 当前以单机、单维护者工作流为主，优先可复现性和低运维成本。
- GROBID 和模型服务是可选依赖，缺失时记录跳过，不伪装成功。
- 本轮不建设通用论文 QA、Web 前端、PostgreSQL、独立向量库或知识图数据库。
- 任何阶段只有通过代码测试、真实数据验收并生成可审计产物后，才能标为 `verified` 或 `operational`。

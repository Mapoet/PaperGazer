[14 tools called]

### P1 启动：全文批处理能力已就绪 ✅

本轮落地了 P1 阶段的首个关键任务——批量生成 TEI 全文的脚手架，具体包括：

1. **数据库扩展**
   - `PaperItem` 新增 `tei_path` 字段，并在 `init_db` 中增加轻量级 schema 校验（自动 `ALTER TABLE`）。
   - 兼容已有 SQLite 库；无须手工迁移即可写入新列。

2. **批处理脚本**
   - 新增 `scripts/process_fulltext_batch.py`：
     - 支持 `--limit`、`--since-days`、`--force`、`--dry-run`、`--output-dir` 等参数；
     - 遍历尚未生成 TEI 的论文，调用 `process_fulltext_document`（含 GROBID 支持），生成文件并回写 `tei_path`；
     - 提供 dry-run 模式评估计划（默认输出目录 `config.grobid.output_dir` 或覆盖参数）。
   - 示例运行（dry-run）：
     ```bash
     python scripts/process_fulltext_batch.py --limit 5 --dry-run
     ```
     若未启用 GROBID，会提示“仅对有文本/XML 的条目进行包装”。

3. **工具导出**
   - `papergazer.utils` 现在额外导出 `GrobidDisabledError`，便于调用层判断 GROBID 开关。

### P1 进展：外部元数据补全已整合 ✅

1. **工具沉淀**
   - `papergazer/utils/metadata.py` 统一封装 Crossref / OpenAlex / Unpaywall 的抓取与入库逻辑。
   - 新增 `enrich_crossref_metadata` / `enrich_openalex_metadata` / `enrich_unpaywall_metadata`，支持 `limit`、`since_days`、`force`、`dry_run`。

2. **CLI 集成**
   - `scripts/daily_ingest.py` 增加 `--enrich-metadata` 与 `--enrich-sources` 等参数，在巡检流程内即可触发 OA 元数据补全。
   - 运行结果按来源输出成功 / 跳过 / 失败统计，便于与巡检日志统一查看。

3. **仓库简化**
   - 移除了独立的 `ingest_crossref_metadata.py`、`ingest_openalex.py`、`ingest_unpaywall.py`，减少脚本分散。
   - 元数据接口现由 `papergazer.utils` 直接导出，方便后续批处理或服务端复用。
4. **运行记录与摘要**
   - `RunRecord` 新增 `cursor` 与 `summary_json` 字段，`enrich_*` 回写运行摘要并更新检查点。
   - `daily_ingest.py --enrich-*` 默认按上次运行的 `ingested_at` 游标增量处理，日志中打印请求统计。

### 下一步建议
- 启动 GROBID 服务后，去掉 `--dry-run` 实际生成 TEI（需配置 `grobid.enabled=true` 并确保服务可达）。
- 补齐 PDF 缺失问题（当前抽样显示约 99% 缺少 PDF），否则 TEI 批量流程仍会大量跳过。
- 利用元数据补全成果，规划下一波 P1 任务：如引用网络 / 概念统计 / OA 占比监控等分析模块。

如需继续编排 Crossref/OpenAlex 批量 ETL 或运行 TEI 实测，请随时告知。
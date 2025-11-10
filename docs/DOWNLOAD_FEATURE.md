# 论文下载功能说明

## 概述

`daily_ingest.py` 脚本现在支持在巡检完成后自动下载论文。可以下载：
- **arXiv 论文**：所有 arXiv 论文都可以直接下载 PDF
- **开放获取（OA）论文**：通过 Unpaywall、Europe PMC 等来源获取的 OA 论文

## 使用方法

### 基本用法

```bash
# 执行巡检并下载所有可用的论文（arXiv + OA）
python scripts/daily_ingest.py --download

# 只下载 arXiv 论文
python scripts/daily_ingest.py --download --download-arxiv-only

# 只下载 OA 论文
python scripts/daily_ingest.py --download --download-oa-only
```

### 高级选项

```bash
# 下载最近 7 天的论文，每个来源最多 100 篇
python scripts/daily_ingest.py --download --download-days 7 --download-limit 100

# 只巡检 arXiv，然后下载 arXiv 论文
python scripts/daily_ingest.py --sources arxiv --download --download-arxiv-only
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--download` | 启用下载功能 | 否 |
| `--download-arxiv-only` | 只下载 arXiv 论文 | 否（下载所有） |
| `--download-oa-only` | 只下载 OA 论文 | 否（下载所有） |
| `--download-days N` | 下载最近 N 天的论文 | 所有未下载的 |
| `--download-limit N` | 限制每个来源的下载数量 | 无限制 |

## 下载逻辑

### arXiv 论文下载

1. 查询数据库中 `source='arxiv'` 且 `pdf_path` 为空或 `None` 的记录
2. 如果指定了 `--download-days`，只下载最近 N 天的论文
3. 如果指定了 `--download-limit`，限制下载数量
4. 使用 `fetch_by_identifier` 下载 PDF
5. 更新数据库中的 `pdf_path` 和 `hash` 字段

### OA 论文下载

1. 查询数据库中 `is_oa=True` 且 `doi` 不为空且 `pdf_path` 为空或 `None` 的记录
2. 如果指定了 `--download-days`，只下载最近 N 天的论文
3. 如果指定了 `--download-limit`，限制下载数量
4. 使用 `fetch_by_identifier` 尝试下载（优先级：Unpaywall → Europe PMC → Crossref 摘要）
5. 更新数据库中的 `pdf_path`、`hash` 和 `oa_source` 字段

## 下载优先级

对于 DOI 论文，下载优先级链为：
1. **Unpaywall**：如果论文是 OA，尝试下载 PDF
2. **Europe PMC**：如果 Unpaywall 失败，尝试从 Europe PMC 下载 XML
3. **Crossref**：如果都失败，至少获取摘要

## 输出示例

```
开始执行每日巡检任务（所有数据源）...
数据库已初始化: ./data/test/test.db
...

每日巡检结果
┏━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━┓
┃ 数据源 ┃ 状态    ┃ 记录数 ┃ 备注 ┃
┡━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━┩
│ ARXIV  │ ✅ 成功 │ 50     │      │
│ CROSSREF│ ✅ 成功 │ 60     │      │
└────────┴─────────┴────────┴──────┘

总计: 110 条记录

开始下载论文...
找到 50 篇需要下载的 arXiv 论文
找到 30 篇需要下载的 OA 论文
...

论文下载结果
┏━━━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━┓
┃ 来源   ┃ 总数 ┃ 成功 ┃ 失败 ┃
┡━━━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━┩
│ ARXIV  │ 50   │ 48   │ 2    │
│ OA     │ 30   │ 25   │ 5    │
└────────┴──────┴──────┴──────┘

下载总计: 成功 73 篇, 失败 7 篇
```

## 注意事项

1. **下载速度**：每次下载之间有 0.5 秒延迟，避免请求过快
2. **去重**：只下载 `pdf_path` 为空或 `None` 的论文，避免重复下载
3. **错误处理**：下载失败会记录日志，但不会中断整个流程
4. **存储路径**：论文保存在 `config.store.papers_dir` 配置的目录中
5. **文件命名**：文件路径格式为 `{year}/{sanitized_id}/paper.pdf`

## 实现细节

### 新增模块

- `papergazer/utils/download.py`：提供批量下载功能
  - `download_arxiv_papers()`：下载 arXiv 论文
  - `download_oa_papers()`：下载 OA 论文
  - `download_all_papers()`：下载所有可用论文

### 修改文件

- `scripts/daily_ingest.py`：
  - 添加 `argparse` 参数解析
  - 添加下载功能调用
  - 添加下载结果展示

- `papergazer/utils/__init__.py`：
  - 导出下载相关函数

## 相关文档

- [技术路线](./TECHNICAL_ROADMAP.md)
- [项目结构](./PROJECT_STRUCTURE.md)
- [集成总结](./INTEGRATION_SUMMARY.md)


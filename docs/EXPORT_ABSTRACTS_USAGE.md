# 论文摘要导出脚本使用指南

## 简介

`export_abstracts.py` 是一个用于查询和导出论文摘要的工具脚本。它可以：

- 查询指定时间段的论文
- 支持按作者、关键词、期刊、数据源过滤
- 将论文摘要导出为美观的 Markdown 格式
- 自动生成统计信息和目录

## 安装依赖

确保已安装所有必需的依赖：

```bash
pip install -r requirements.txt
```

## 基本用法

### 1. 查询最近 N 天的论文

```bash
# 查询最近30天的所有论文
python scripts/export_abstracts.py --days 30 --output abstracts.md

# 或使用 Shell 脚本
./scripts/export_abstracts.sh --days 30 --output abstracts.md
```

### 2. 查询指定日期范围的论文

```bash
# 查询2025年1月的论文
python scripts/export_abstracts.py \
    --since 2025-01-01 \
    --until 2025-01-31 \
    --output jan2025.md
```

### 3. 按作者过滤

```bash
# 查询包含作者 "Zhang" 的论文
python scripts/export_abstracts.py \
    --days 30 \
    --author "Zhang" \
    --output zhang_papers.md
```

### 4. 按关键词过滤

```bash
# 查询包含 "machine learning" 的论文（搜索标题和摘要）
python scripts/export_abstracts.py \
    --days 30 \
    --keyword "machine learning" \
    --output ml_papers.md
```

### 5. 按期刊过滤

```bash
# 查询 Nature 和 Science 的论文
python scripts/export_abstracts.py \
    --days 30 \
    --venues "Nature" "Science" \
    --output cns_papers.md
```

### 6. 组合过滤条件

```bash
# 查询特定作者在特定时间段发表的包含特定关键词的论文
python scripts/export_abstracts.py \
    --since 2025-01-01 \
    --until 2025-01-31 \
    --author "Zhang" \
    --keyword "deep learning" \
    --venues "Nature" \
    --output results.md
```

### 7. 按数据源过滤

```bash
# 只查询 arXiv 的论文
python scripts/export_abstracts.py \
    --days 30 \
    --sources arxiv \
    --output arxiv_papers.md

# 查询 Crossref 和 Europe PMC 的论文
python scripts/export_abstracts.py \
    --days 30 \
    --sources crossref eupmc \
    --output journal_papers.md
```

### 8. 使用自定义配置文件

```bash
python scripts/export_abstracts.py \
    --days 30 \
    --config configs/my_config.yaml \
    --output papers.md
```

## 参数说明

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `--since` | 字符串 | 否* | 起始日期（格式: YYYY-MM-DD） |
| `--until` | 字符串 | 否 | 结束日期（格式: YYYY-MM-DD），默认为今天 |
| `--days` | 整数 | 否* | 查询最近 N 天的论文 |
| `--author` | 字符串 | 否 | 按作者名称过滤（部分匹配） |
| `--keyword` | 字符串 | 否 | 按关键词过滤（搜索标题和摘要） |
| `--sources` | 列表 | 否 | 指定数据源（arxiv, crossref, eupmc） |
| `--venues` | 列表 | 否 | 按期刊名称过滤（支持多个，部分匹配） |
| `--output`, `-o` | 字符串 | 是 | 输出文件路径（.md） |
| `--config` | 字符串 | 否 | 配置文件路径 |

\* 必须指定 `--days` 或 `--since` 中的一个

## 输出格式

导出的 Markdown 文件包含：

### 1. 头部信息
- 查询时间范围
- 过滤条件
- 论文总数
- 开放获取论文比例
- 期刊分布（前10个）

### 2. 目录
- 所有论文的标题列表（带锚点链接）

### 3. 论文详情
每篇论文包含：
- 标题
- 作者列表（最多10个）
- 期刊名称
- 发表日期
- DOI 或 arXiv ID（带链接）
- 开放获取状态
- 摘要（如果有）

## 示例输出

```markdown
# 论文摘要汇总

**时间范围**: 2025-01-01 至 2025-01-31

**过滤条件**: 作者: Zhang, 关键词: machine learning

**论文总数**: 15

**开放获取论文**: 10/15 (66%)

**期刊分布**（前10个）:

- Nature Machine Intelligence: 3 篇
- IEEE Transactions on Pattern Analysis and Machine Intelligence: 2 篇
- arXiv: 5 篇
- ...

## 目录

1. [Deep Learning for Climate Prediction](#1-deep-learning-for-climate-prediction)
2. [Neural Networks in Remote Sensing](#2-neural-networks-in-remote-sensing)
...

---

## 1. Deep Learning for Climate Prediction

**作者**: Zhang Wei, Li Ming, Wang Jun

**期刊**: Nature Machine Intelligence

**发表日期**: 2025-01-15

**DOI**: [10.1038/s42256-025-00123-4](https://doi.org/10.1038/s42256-025-00123-4)

**状态**: ✅ Open Access (来源: unpaywall) - 已下载

**摘要**:

This paper presents a novel deep learning approach for climate prediction...

---

...
```

## 高级用法

### 1. 批量导出

创建一个批处理脚本来导出多个类别的论文：

```bash
#!/bin/bash

# 导出地学论文
./scripts/export_abstracts.sh --days 30 --keyword "geophysics" -o exports/geophysics.md

# 导出遥感论文
./scripts/export_abstracts.sh --days 30 --keyword "remote sensing" -o exports/remote_sensing.md

# 导出机器学习论文
./scripts/export_abstracts.sh --days 30 --keyword "machine learning" -o exports/ml.md

echo "所有导出完成！"
```

### 2. 定期导出

可以使用 cron 定时任务定期导出论文摘要：

```bash
# 编辑 crontab
crontab -e

# 每周一早上8点导出上周的论文
0 8 * * 1 cd /path/to/PaperGazer && ./scripts/export_abstracts.sh --days 7 -o /path/to/weekly_$(date +\%Y\%m\%d).md
```

### 3. 与其他工具集成

导出的 Markdown 文件可以：

- 用 Pandoc 转换为 PDF、Word 等格式
- 导入到 Obsidian、Notion 等笔记工具
- 通过 Jekyll、Hugo 等工具生成静态网站
- 用于生成周报、月报

## 注意事项

1. **数据库要求**: 脚本需要访问已经初始化的数据库，确保已经运行过 `daily_ingest.py`
2. **摘要可用性**: 并非所有论文都有摘要，无摘要的论文会显示"*摘要暂不可用*"
3. **大量论文**: 如果匹配的论文很多（如数百篇），生成的 Markdown 文件会很大
4. **作者匹配**: 作者过滤使用部分匹配，可能会匹配到姓或名包含指定字符串的作者
5. **关键词搜索**: 关键词搜索不区分大小写，会搜索标题和摘要

## 故障排除

### 问题：找不到论文

**可能原因**:
1. 数据库中没有符合条件的论文
2. 过滤条件太严格
3. 时间范围不对

**解决方法**:
1. 先运行 `daily_ingest.py` 抓取数据
2. 放宽过滤条件
3. 检查时间范围是否正确

### 问题：配置文件不存在

**解决方法**:
```bash
# 复制示例配置文件
cp configs/config.yaml.example configs/config.yaml
# 编辑配置文件
vim configs/config.yaml
```

### 问题：数据库未初始化

**解决方法**:
```bash
# 运行一次巡检来初始化数据库
python scripts/daily_ingest.py --sources arxiv
```

## 相关文档

- [项目 README](../README.md)
- [每日巡检脚本使用](./DAILY_INGEST_USAGE.md)
- [查询脚本使用](./QUERY_PAPERS_USAGE.md)
- [分析脚本使用](./ANALYZE_PAPERS_USAGE.md)


#!/bin/bash
# 论文查询脚本（Bash封装）
# 用法: ./scripts/query_papers.sh <mode> [options...]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# 打印使用说明
print_usage() {
    echo "用法: $0 <mode> [options...]"
    echo ""
    echo "查询模式:"
    echo "  days <days> [--ingest] [sources...]"
    echo "    - 按天数查询论文"
    echo "    - days: 查询天数（必需）"
    echo "    - --ingest: 是否执行 ingest 过程（抓取新数据），默认只查询已有数据"
    echo "    - sources: 数据源列表，可选值：arxiv, crossref, eupmc, unpaywall"
    echo ""
    echo "  author <author_name> [--limit N] [sources...]"
    echo "    - 按作者名称搜索论文"
    echo "    - author_name: 作者名称（支持部分匹配）"
    echo "    - --limit N: 限制返回数量（默认不限制）"
    echo "    - sources: 数据源列表"
    echo ""
    echo "  venue <venue_name> [--limit N] [sources...]"
    echo "    - 按期刊/会议名称搜索论文"
    echo "    - venue_name: 期刊/会议名称（支持部分匹配）"
    echo "    - --limit N: 限制返回数量（默认不限制）"
    echo "    - sources: 数据源列表"
    echo ""
    echo "  keyword <keyword> [--in title|abstract|both] [--limit N] [sources...]"
    echo "    - 按关键词搜索论文（标题和/或摘要）"
    echo "    - keyword: 搜索关键词（支持部分匹配）"
    echo "    - --in: 搜索范围，可选：title（仅标题）、abstract（仅摘要）、both（标题和摘要，默认）"
    echo "    - --limit N: 限制返回数量（默认不限制）"
    echo "    - sources: 数据源列表"
    echo ""
    echo "示例:"
    echo "  $0 days 7"
    echo "  $0 days 7 --ingest"
    echo "  $0 days 7 arxiv crossref"
    echo "  $0 author \"Einstein\" --limit 10"
    echo "  $0 venue \"Nature\" --limit 20"
    echo "  $0 keyword \"machine learning\" --in both --limit 50"
    echo "  $0 keyword \"GNSS\" --in title arxiv crossref"
}

# 检查参数
if [ $# -lt 1 ]; then
    print_usage
    exit 1
fi

MODE=$1
shift
ARGS="$@"

# 执行查询
python scripts/query_papers.py "$MODE" $ARGS

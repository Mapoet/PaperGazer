#!/bin/bash
# 论文查询脚本（Bash封装）
# 用法: ./scripts/query_papers.sh <days> [sources...]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# 检查参数
if [ $# -lt 1 ]; then
    echo "用法: $0 <days> [sources...]"
    echo ""
    echo "参数:"
    echo "  days: 查询天数（必需）"
    echo "  sources: 数据源列表，可选值：arxiv, crossref, eupmc, unpaywall"
    echo "          如果不指定，则查询所有数据源"
    echo ""
    echo "示例:"
    echo "  $0 7"
    echo "  $0 7 arxiv crossref"
    echo "  $0 30 eupmc"
    exit 1
fi

DAYS=$1
shift
SOURCES="$@"

# 执行查询
if [ -z "$SOURCES" ]; then
    python scripts/query_papers.py "$DAYS"
else
    python scripts/query_papers.py "$DAYS" $SOURCES
fi


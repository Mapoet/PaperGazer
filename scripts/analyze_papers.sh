#!/bin/bash
# 论文分析脚本（Bash封装）
# 用法: ./scripts/analyze_papers.sh <analysis_type> <days> [sources...] [limit]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# 检查参数
if [ $# -lt 2 ]; then
    echo "用法: $0 <analysis_type> <days> [sources...] [limit]"
    echo ""
    echo "分析类型:"
    echo "  authors    - 作者分析"
    echo "  abstracts  - 摘要分析"
    echo "  oa         - OA状态分析"
    echo "  venues     - 期刊/会议分析"
    echo "  list       - 论文列表"
    echo ""
    echo "参数:"
    echo "  days: 查询天数（必需）"
    echo "  sources: 数据源列表，可选值：arxiv, crossref, eupmc"
    echo "          如果不指定，则分析所有数据源"
    echo "  limit: 限制返回数量（仅用于 list 类型）"
    echo ""
    echo "示例:"
    echo "  $0 authors 7"
    echo "  $0 abstracts 30 arxiv crossref"
    echo "  $0 oa 7"
    echo "  $0 venues 30"
    echo "  $0 list 7 10"
    exit 1
fi

ANALYSIS_TYPE=$1
DAYS=$2
shift 2
ARGS="$@"

# 执行分析
python scripts/analyze_papers.py "$ANALYSIS_TYPE" "$DAYS" $ARGS


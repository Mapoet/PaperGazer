#!/bin/bash
# 论文分析脚本（Bash封装）
# 用法: ./scripts/analyze_papers.sh <analysis_type> <days> [options]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# 显示帮助信息
show_help() {
    echo "用法: $0 <analysis_type> <days> [options]"
    echo ""
    echo "分析类型:"
    echo "  authors    - 作者分析"
    echo "  abstracts  - 摘要分析"
    echo "  oa         - OA状态分析"
    echo "  venues     - 期刊/会议分析"
    echo "  list       - 论文列表"
    echo ""
    echo "必需参数:"
    echo "  analysis_type  分析类型"
    echo "  days           查询天数（正整数）"
    echo ""
    echo "可选参数:"
    echo "  -s, --sources <source1> [source2...]  指定数据源（arxiv, crossref, eupmc）"
    echo "  -l, --limit <number>                  限制返回数量（默认：100，用于list）"
    echo "  -t, --top <number>                    显示Top N（默认：10，用于authors和venues）"
    echo "  -c, --config <path>                   配置文件路径"
    echo "  -o, --output <format>                 输出格式（table, json, csv）"
    echo "  -v, --verbose                         详细输出模式"
    echo "  -h, --help                            显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 authors 7"
    echo "  $0 abstracts 30 --sources arxiv crossref"
    echo "  $0 oa 7 --verbose"
    echo "  $0 venues 30 --top 20"
    echo "  $0 list 7 --limit 50"
    echo "  $0 authors 7 --config configs/config.prod.yaml"
    exit 0
}

# 检查是否需要显示帮助
if [ $# -eq 0 ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_help
fi

# 检查基本参数
if [ $# -lt 2 ]; then
    echo "错误: 需要至少2个参数（analysis_type和days）"
    echo "使用 '$0 --help' 查看完整用法"
    exit 1
fi

# 提取位置参数
ANALYSIS_TYPE=$1
DAYS=$2
shift 2

# 构建Python命令
PYTHON_CMD="python scripts/analyze_papers.py $ANALYSIS_TYPE $DAYS"

# 解析可选参数
while [ $# -gt 0 ]; do
    case "$1" in
        -s|--sources)
            PYTHON_CMD="$PYTHON_CMD --sources"
            shift
            # 收集所有数据源，直到遇到下一个选项或参数结束
            while [ $# -gt 0 ] && [[ ! "$1" =~ ^- ]]; do
                PYTHON_CMD="$PYTHON_CMD $1"
                shift
            done
            ;;
        -l|--limit)
            PYTHON_CMD="$PYTHON_CMD --limit $2"
            shift 2
            ;;
        -t|--top)
            PYTHON_CMD="$PYTHON_CMD --top $2"
            shift 2
            ;;
        -c|--config)
            PYTHON_CMD="$PYTHON_CMD --config $2"
            shift 2
            ;;
        -o|--output)
            PYTHON_CMD="$PYTHON_CMD --output $2"
            shift 2
            ;;
        -v|--verbose)
            PYTHON_CMD="$PYTHON_CMD --verbose"
            shift
            ;;
        *)
            echo "未知选项: $1"
            echo "使用 '$0 --help' 查看完整用法"
            exit 1
            ;;
    esac
done

# 执行分析
eval $PYTHON_CMD


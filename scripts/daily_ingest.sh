#!/bin/bash
# 每日巡检脚本（Bash封装）
# 用法: ./scripts/daily_ingest.sh [sources...]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# 执行巡检
if [ $# -eq 0 ]; then
    echo "执行所有数据源的每日巡检..."
    python scripts/daily_ingest.py
else
    echo "执行指定数据源的每日巡检: $@"
    python scripts/daily_ingest.py "$@"
fi


#!/bin/bash
# 论文摘要导出脚本（Bash封装）
# 用法: ./scripts/export_abstracts.sh <options>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# 直接将所有参数传递给 Python 脚本
python scripts/export_abstracts.py "$@"


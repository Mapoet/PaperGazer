#!/bin/bash
# 更新 arXiv 论文 venue 字段脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "更新数据库中 arXiv 论文的 venue 字段..."
python scripts/update_arxiv_venues.py


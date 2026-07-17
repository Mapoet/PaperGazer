#!/bin/bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_root"

# Prefer project .venv311 (Python 3.11+); datetime.UTC requires 3.11+.
# Override with PAPERGAZER_PYTHON if needed. Do not use appservice (3.8).
if [[ -n "${PAPERGAZER_PYTHON:-}" ]]; then
  python_bin="$PAPERGAZER_PYTHON"
elif [[ -x "$project_root/.venv311/bin/python" ]]; then
  python_bin="$project_root/.venv311/bin/python"
else
  python_bin="python3"
fi
config_path="${PAPERGAZER_CONFIG:-configs/config.yaml}"
days="${PAPERGAZER_DAYS:-7}"

"$python_bin" -c 'import sys; assert sys.version_info >= (3, 11), f"PaperGazer needs Python 3.11+, got {sys.version}"'
"$python_bin" scripts/daily_ingest.py --config "$config_path" --days "$days"
"$python_bin" scripts/export_abstracts.py --config "$config_path" --days "$days" --output data/data7d.md
"$python_bin" scripts/export_abstracts.py --config "$config_path" --days "$days" --keyword "GNSS" --output data/gnss7d.md
"$python_bin" scripts/export_abstracts.py --config "$config_path" --days "$days" --keyword "Atmosphere" --output data/atmo7d.md
"$python_bin" scripts/export_abstracts.py --config "$config_path" --days "$days" --keyword "Ionosphere" --output data/iono7d.md
"$python_bin" scripts/export_abstracts.py --config "$config_path" --days "$days" --keyword "GPS" --output data/gps7d.md

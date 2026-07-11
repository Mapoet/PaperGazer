#!/bin/bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_root"

python_bin="${PAPERGAZER_PYTHON:-python3}"
config_path="${PAPERGAZER_CONFIG:-configs/config.yaml}"
days="${PAPERGAZER_DAYS:-7}"

"$python_bin" scripts/daily_ingest.py --config "$config_path" --days "$days"
"$python_bin" scripts/export_abstracts.py --config "$config_path" --days "$days" --output data/data7d.md
"$python_bin" scripts/export_abstracts.py --config "$config_path" --days "$days" --keyword "GNSS" --output data/gnss7d.md
"$python_bin" scripts/export_abstracts.py --config "$config_path" --days "$days" --keyword "Atmosphere" --output data/atmo7d.md
"$python_bin" scripts/export_abstracts.py --config "$config_path" --days "$days" --keyword "Ionosphere" --output data/iono7d.md
"$python_bin" scripts/export_abstracts.py --config "$config_path" --days "$days" --keyword "GPS" --output data/gps7d.md

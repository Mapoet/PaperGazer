#!/bin/bash
days=7;
python3 ./scripts/daily_ingest.py --days $days
python3 scripts/export_abstracts.py --days $days   --output data/data7d.md
python3 scripts/export_abstracts.py --days $days --keyword "GNSS"   --output data/gnss7d.md
python3 scripts/export_abstracts.py --days $days --keyword "Atmosphere"   --output data/atmo7d.md
python3 scripts/export_abstracts.py --days $days --keyword "Ionosphere"   --output data/iono7d.md
python3 scripts/export_abstracts.py --days $days --keyword "GPS"   --output data/gps7d.md
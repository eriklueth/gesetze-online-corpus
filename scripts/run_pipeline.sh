#!/usr/bin/env bash
set -euo pipefail
python3 scripts/parse/normalize_law.py
python3 scripts/export/generate_markdown.py
python3 scripts/export/generate_chunks.py

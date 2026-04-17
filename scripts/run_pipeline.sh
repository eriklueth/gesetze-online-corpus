#!/usr/bin/env bash
set -euo pipefail

if [ -f index/toc.json ]; then
  python3 scripts/parse/normalize_from_raw.py || true
fi

if [ ! -f normalized/example-law.json ] && [ ! -f index/laws.json ]; then
  python3 scripts/parse/normalize_law.py
fi

python3 scripts/export/generate_markdown.py
python3 scripts/export/generate_chunks.py

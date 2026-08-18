#!/usr/bin/env bash
# Serve the demo locally: ./serve.sh [port]  then open http://localhost:8000/
cd "$(dirname "$0")"
cp -f ../wheels/bskcore-*.whl . 2>/dev/null || true
python3 -m http.server "${1:-8000}"

#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"

echo "== Step 1: check /material/info =="
curl -s "${BASE_URL}/material/info"
echo ""
echo ""

echo "== Step 2: POST /material/match-segments =="
curl -s -X POST "${BASE_URL}/material/match-segments" \
  -H "Content-Type: application/json" \
  -d '{"uid":13,"audio_url":"https://example.com/audio.mp3"}' | head -c 1200
echo ""
echo ""

echo "== Step 3: grep logs for api_version and raw_text =="
grep -E "api_version=v2-dual-text|raw_text_len=|segment_fields=raw_text" logs/app.log | tail -5

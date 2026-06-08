#!/usr/bin/env bash
# 快速验证 match-segments 接口与日志是否写入 logs/app.log
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
FIXTURE="${2:-tests/material/fixtures/sample_asr.json}"

echo "POST ${BASE_URL}/material/match-segments"
curl -s -w "\nHTTP %{http_code}\n" -X POST "${BASE_URL}/material/match-segments" \
  -H "Content-Type: application/json" \
  --data-binary @"${FIXTURE}"

echo ""
echo "Recent logs:"
grep -E "request start|match_segments|service ready" logs/app.log | tail -10

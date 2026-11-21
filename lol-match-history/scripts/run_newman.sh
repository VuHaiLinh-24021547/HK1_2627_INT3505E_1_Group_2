#!/usr/bin/env bash
set -euo pipefail

COLLECTION="postman/lol-match-history.postman_collection.json"
ENVIRONMENT="postman/local.postman_environment.json"
REPORT_DIR="reports/newman"

mkdir -p "$REPORT_DIR"

if ! command -v newman >/dev/null 2>&1; then
  echo "Lỗi: chưa cài đặt newman. Hãy chạy: npm install -g newman"
  exit 1
fi

if [[ "${SEED:-0}" == "1" ]]; then
  FLASK_APP=app:create_app flask seed-demo
fi

newman run "$COLLECTION" \
  -e "$ENVIRONMENT" \
  --reporters cli,junit \
  --reporter-junit-export "$REPORT_DIR/junit-report.xml" \
  --bail

echo "Tất cả API endpoint tests (Newman) đã pass!"

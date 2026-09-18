#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
FILE="${1:-samples/Vanikavipuldata_sample.xls}"

if [[ ! -f "$FILE" ]]; then
  echo "File not found: $FILE" >&2
  exit 2
fi

curl --fail-with-body -X POST "$BASE_URL/api/v1/calculations/client-workbook/" \
  -H "Accept: application/json" \
  -F "file=@$FILE" \
  -F "consent=true" \
  -F "pv_size_kw=5" \
  -F "battery_annual_cost_per_kwh=50" \
  -F "battery_installed_cost_per_kwh=1000" \
  -F "retail_price_per_kwh=0.3773" \
  -F "feed_in_tariff_per_kwh=0.124" \
  -F "max_battery_capacity_kwh=50"

#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
API_KEY="${ROUTEWISE_API_KEY:-}"

routewise_curl() {
  if [[ -n "$API_KEY" ]]; then
    curl "$@" -H "X-API-Key: $API_KEY"
  else
    curl "$@"
  fi
}

printf "Health: "
curl --fail --silent --show-error --max-time 10 "$BASE_URL/health"
printf "\n"

printf "Readiness: "
curl --fail --silent --show-error --max-time 15 "$BASE_URL/readiness"
printf "\n"

printf "Route preview: "
routewise_curl --fail --silent --show-error --max-time 15 \
  -X POST "$BASE_URL/route/preview" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"smoke-test","messages":[{"role":"user","content":"Say hello in one sentence."}],"quality_target":0,"max_cost_tier":"small"}'
printf "\n"

printf "Dashboard: "
curl --fail --silent --show-error --max-time 10 \
  -o /dev/null -w "%{http_code}\n" "$BASE_URL/dashboard"

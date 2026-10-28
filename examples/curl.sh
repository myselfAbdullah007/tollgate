#!/bin/sh
set -eu
curl --fail-with-body "${TOLLGATE_BASE_URL:-http://localhost:8187/v1}/chat/completions" \
  -H "Authorization: Bearer ${TOLLGATE_API_KEY:-tg_live_demo_tollgate_local_only}" \
  -H 'X-Tollgate-Customer: cus_acme' -H 'Content-Type: application/json' \
  -d '{"model":"smart","messages":[{"role":"user","content":"Email ali@example.com a refund update"}],"stream":true}'

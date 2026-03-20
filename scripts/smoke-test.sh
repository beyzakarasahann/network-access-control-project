#!/usr/bin/env bash
# Yerel / CI hizli dogrulama: API + (varsa) Docker RADIUS.
# Kullanim: bash scripts/smoke-test.sh
#          API_URL=http://localhost:8000 bash scripts/smoke-test.sh

set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"
RADIUS_CONTAINER="${RADIUS_CONTAINER:-nac_radius}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-nac_postgres}"
PG_USER="${POSTGRES_USER:-nac}"
PG_DB="${POSTGRES_DB:-nacdb}"

pretty() {
  if command -v jq &>/dev/null; then jq .; else python3 -m json.tool 2>/dev/null || cat; fi
}

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK   $*"; }

echo "=== GET $API_URL/health ==="
code=$(curl -sS -o /tmp/nac_health.json -w "%{http_code}" "$API_URL/health") || fail "curl health"
cat /tmp/nac_health.json | pretty
[[ "$code" == "200" ]] || fail "health HTTP $code (beklenen 200)"

echo ""
echo "=== POST $API_URL/authorize (demo -> VLAN JSON) ==="
code=$(curl -sS -o /tmp/nac_authz.json -w "%{http_code}" \
  -X POST "$API_URL/authorize" \
  -H "Content-Type: application/json" \
  -d '{"User-Name":{"type":"string","value":["demo"]}}') || fail "curl authorize"
cat /tmp/nac_authz.json | pretty
[[ "$code" == "200" ]] || fail "authorize HTTP $code (beklenen 200)"

echo ""
echo "=== GET $API_URL/monitoring/snapshot (ozet) ==="
code=$(curl -sS -o /tmp/nac_mon.json -w "%{http_code}" "$API_URL/monitoring/snapshot") || fail "curl monitoring"
if command -v jq &>/dev/null; then
  jq '{timestamp, health, sessions: .sessions.count, radacct: .accounting.radacct_rows}' /tmp/nac_mon.json
else
  echo "(jq yok; /tmp/nac_mon.json)"
fi
[[ "$code" == "200" ]] || fail "monitoring snapshot HTTP $code"

echo ""
echo "=== GET $API_URL/users (ozet) ==="
code=$(curl -sS -o /tmp/nac_users.json -w "%{http_code}" "$API_URL/users") || fail "curl users"
if command -v jq &>/dev/null; then
  jq '{radcheck_count: (.radcheck|length), radusergroup_count: (.radusergroup|length), first_user: .radcheck[0].username}' /tmp/nac_users.json
else
  echo "(jq yok; tam yanit /tmp/nac_users.json)"
fi
[[ "$code" == "200" ]] || fail "users HTTP $code"

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$RADIUS_CONTAINER"; then
  echo ""
  echo "=== radtest PAP (demo) — $RADIUS_CONTAINER ==="
  out=$(docker exec "$RADIUS_CONTAINER" radtest demo DemoPass123 127.0.0.1 0 testing123 2>&1) || true
  echo "$out"
  echo "$out" | grep -q "Access-Accept" || fail "radtest demo beklenen Access-Accept"
  ok "radtest demo"
else
  echo ""
  echo "SKIP Docker: $RADIUS_CONTAINER bulunamadi (sadece API test edildi)."
fi

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$POSTGRES_CONTAINER"; then
  echo ""
  echo "=== Postgres radcheck (demo satiri) ==="
  docker exec "$POSTGRES_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -tAc \
    "SELECT 1 FROM radcheck WHERE username='demo' AND attribute='MD5-Password' LIMIT 1;" | grep -q 1 \
    || fail "demo radcheck yok — seed calistirin"
  ok "radcheck demo"
fi

echo ""
echo "Tum kontroller tamam."

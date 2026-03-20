#!/usr/bin/env bash
# FreeRADIUS accounting demo: Start -> Interim-Update -> Stop
# Calistir: bash scripts/radacct-demo.sh   (proje kokunden)
# Onceden: docker compose up -d

set -euo pipefail

SECRET="${RADIUS_SECRET:-testing123}"
RADIUS_CONTAINER="${RADIUS_CONTAINER:-nac_radius}"
PORT="${RADIUS_ACCT_PORT:-1813}"
SESS_ID="${ACCT_SESSION_ID:-demo-radacct-$(date +%s)}"

radacct() {
  docker exec -i "$RADIUS_CONTAINER" radclient -x -r 2 "127.0.0.1:${PORT}" acct "$SECRET" <<< "$1"
}

echo "=== Accounting-Start (Acct-Session-Id=$SESS_ID) ==="
radacct "User-Name = \"demo\"
Acct-Status-Type = Start
Acct-Session-Id = \"${SESS_ID}\"
NAS-IP-Address = 127.0.0.1"

sleep 1

echo ""
echo "=== Interim-Update ==="
radacct "User-Name = \"demo\"
Acct-Status-Type = Interim-Update
Acct-Session-Id = \"${SESS_ID}\"
NAS-IP-Address = 127.0.0.1
Acct-Session-Time = 30
Acct-Input-Octets = 1024
Acct-Output-Octets = 2048"

sleep 1

echo ""
echo "=== Accounting-Stop ==="
radacct "User-Name = \"demo\"
Acct-Status-Type = Stop
Acct-Session-Id = \"${SESS_ID}\"
NAS-IP-Address = 127.0.0.1
Acct-Session-Time = 60
Acct-Terminate-Cause = User-Request"

echo ""
echo "Bitti."
echo "- Stop sonrasi Redis anahtari silinir; aktif oturum bos olabilir."
echo "- radacct satiri: docker exec nac_postgres psql -U \"\${POSTGRES_USER:-nac}\" -d \"\${POSTGRES_DB:-nacdb}\" -c \"SELECT acctsessionid, username, acctstoptime FROM radacct WHERE acctsessionid='${SESS_ID}';\""

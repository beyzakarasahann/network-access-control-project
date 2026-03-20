# NAC — İstek ve test komutları

Varsayılan portlar: **API `8000`**, **Monitoring `3000`**, **Postgres `5432`**, **Redis `6379`**, **RADIUS auth `1812`**, **acct `1813`**.  
Proje kökünden çalıştırın; `.env` ile portlar değiştiyse URL’leri uyarlayın.

---

## 1. Altyapı

```bash
cd "/path/to/Network Access Control Project"

docker compose up -d
docker compose ps

# API kodu değişince (reload yoksa)
docker compose restart api

# Monitoring imajını yenilemek için
docker compose build monitoring && docker compose up -d monitoring
```

---

## 2. FastAPI — tarayıcı

| Ne | Adres |
|----|--------|
| Swagger (tüm endpoint’ler) | http://localhost:8000/docs |
| OpenAPI JSON | http://localhost:8000/openapi.json |

---

## 3. FastAPI — `curl` (hosttan, `localhost`)

**Sağlık ve sürüm**

```bash
curl -s http://localhost:8000/ | jq .
curl -s http://localhost:8000/health | jq .
```

**Monitoring snapshot (dashboard verisi)**

```bash
curl -s http://localhost:8000/monitoring/snapshot | jq .
```

**Yetkilendirme (rlm_rest ile aynı mantık)**

```bash
curl -s -X POST http://localhost:8000/authorize \
  -H "Content-Type: application/json" \
  -d '{"User-Name":{"type":"string","value":["demo"]}}' | jq .
```

**PAP benzeri doğrulama**

```bash
curl -s -X POST http://localhost:8000/auth \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"DemoPass123"}' | jq .
```

**Kullanıcı listesi**

```bash
curl -s http://localhost:8000/users | jq .
```

**Aktif oturumlar (Redis)**

```bash
curl -s http://localhost:8000/sessions/active | jq .
```

**Accounting (HTTP testi)**

```bash
# Start
curl -s -X POST http://localhost:8000/accounting \
  -H "Content-Type: application/json" \
  -d '{
    "status": "Start",
    "username": "demo",
    "acct_session_id": "curl-sess-1",
    "acct_unique_session_id": "curl-uniq-1",
    "nas_ip_address": "10.0.0.1"
  }' | jq .

# Stop
curl -s -X POST http://localhost:8000/accounting \
  -H "Content-Type: application/json" \
  -d '{
    "status": "Stop",
    "username": "demo",
    "acct_session_id": "curl-sess-1",
    "acct_unique_session_id": "curl-uniq-1",
    "nas_ip_address": "10.0.0.1"
  }' | jq .
```

---

## 4. Next.js monitoring paneli

Tarayıcı: **http://localhost:3000**  
(`.env` içinde `MONITORING_PORT` farklıysa onu kullanın.)

Yerel Next (Docker’sız), API Docker’da:

```bash
cd monitoring
INTERNAL_API_URL=http://127.0.0.1:8000 npm run dev
```

---

## 5. FreeRADIUS — container içinden

Paylaşılan sır: **`testing123`** (lab).

**PAP**

```bash
docker exec nac_radius radtest demo DemoPass123 127.0.0.1 0 testing123
docker exec nac_radius radtest -x demo DemoPass123 127.0.0.1 0 testing123
```

**CHAP**

```bash
docker exec nac_radius radtest -t chap chapuser ChapPass789 127.0.0.1 0 testing123
```

**MAB (demo MAC)**

```bash
docker exec nac_redis redis-cli DEL nac_auth_fail_aabbccddeeff
docker exec nac_radius radtest -x AA-BB-CC-DD-EE-FF AA-BB-CC-DD-EE-FF 127.0.0.1 0 testing123
```

**Accounting (radclient)**

```bash
bash scripts/radacct-demo.sh
```

veya tek paket:

```bash
docker exec -i nac_radius radclient -x 127.0.0.1:1813 acct testing123 <<'EOF'
User-Name = "demo"
Acct-Status-Type = Start
Acct-Session-Id = "manual-1"
NAS-IP-Address = 127.0.0.1
EOF
```

---

## 6. Redis / Postgres (isteğe bağlı)

```bash
docker exec nac_redis redis-cli PING
docker exec nac_redis redis-cli KEYS 'nac:acct:*'
docker exec nac_redis redis-cli DEL nac_auth_fail_demo

docker exec nac_postgres psql -U nac -d nacdb -c "SELECT COUNT(*) FROM radcheck;"
docker exec nac_postgres psql -U nac -d nacdb -c "SELECT acctsessionid, username, acctstoptime FROM radacct ORDER BY radacctid DESC LIMIT 5;"
```

*(Kullanıcı / veritabanı adı `.env` ile aynı olmalı.)*

---

## 7. Otomatik duman testi

```bash
bash scripts/smoke-test.sh
# veya
make smoke
```

---

## 8. API’ye Docker ağı içinden örnek

Başka bir konteynerden veya debug için:

```bash
docker compose exec api python -c "
import urllib.request, json
u = urllib.request.urlopen('http://127.0.0.1:8000/monitoring/snapshot')
print(json.loads(u.read().decode())['health'])
"
```

---

*İlgili: `README.md`, `scripts/radacct-demo.sh`, `scripts/smoke-test.sh`*

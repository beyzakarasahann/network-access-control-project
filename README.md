# Ağ Erişim Kontrolü (NAC) — Laboratuvar Projesi

Docker tabanlı **Network Access Control** demonstrasyonu: **FreeRADIUS 3.2**, **PostgreSQL** (FreeRADIUS SQL modülü), **Redis** (rate limit + aktif oturum özeti), **FastAPI** (`rlm_rest` ile yetkilendirme + HTTP accounting). İsteğe bağlı **Next.js** izleme paneli (ödev bonusu).

**API sürümü:** `0.2.2` (`api/main.py` → FastAPI `version`).

---

## İçindekiler

1. [Gereksinimler](#gereksinimler)
2. [Hızlı başlangıç](#hizli-baslangic)
3. [Mimari ve servisler](#mimari-ve-servisler)
4. [Depo yapısı](#depo-yapisi)
5. [Ortam değişkenleri](#ortam-degiskenleri)
6. [Veritabanı başlatma (init sırası)](#veritabani-init)
7. [Sağlık kontrolü ve smoke test](#saglik-ve-smoke)
8. [Dokümantasyon (rapor / komutlar)](#dokumantasyon)
9. [Adım 2 — Kimlik doğrulama](#adim-2-auth)
10. [Adım 3 — Yetkilendirme](#adim-3-authorize)
11. [Adım 4 — Accounting](#adim-4-accounting)
12. [Bonus: İzleme paneli](#bonus-monitoring)
13. [Teslim kontrol listesi](#teslim-checklist)
14. [Sorun giderme](#sorun-giderme)

---

<a id="gereksinimler"></a>
## Gereksinimler

- **Docker** ve **Docker Compose** (v2)
- FreeRADIUS imajı `linux/amd64` — Apple Silicon’da Docker **Rosetta / QEMU** emülasyonu kullanılır
- İsteğe bağlı: `make` (kökteki `Makefile` kısayolları için)

---

<a id="hizli-baslangic"></a>
## Hızlı başlangıç

```bash
cp .env.example .env
# .env içinde POSTGRES_PASSWORD değerini güçlü bir parola ile değiştirin

docker compose up -d
docker compose ps
```

**Beklenen:** `postgres`, `redis`, `api` sağlıklı olduktan sonra `freeradius` ayağa kalkar; isteğe bağlı `monitoring` ayrı servistir.

---

<a id="mimari-ve-servisler"></a>
## Mimari ve servisler

| Servis (Compose adı) | Konteyner adı   | Rol | Varsayılan erişim |
|----------------------|-----------------|-----|-------------------|
| `postgres`           | `nac_postgres`  | FreeRADIUS + API veritabanı, `db/init/*.sql` ile seed | `${POSTGRES_PORT}:5432` |
| `redis`              | `nac_redis`     | Auth rate limit, accounting oturum anahtarları | `${REDIS_PORT}:6379` |
| `api`                | `nac_api`       | FastAPI: `/authorize`, `/accounting`, `/users`, … | `${API_PORT}:8000` |
| `freeradius`         | `nac_radius`    | RADIUS auth (1812/udp), acct (1813/udp), `rlm_sql` + `rlm_rest` | `.env` portları |
| `monitoring` (bonus) | `nac_monitoring`| Next.js panel → API `GET /monitoring/snapshot` | `${MONITORING_PORT:-3000}:3000` |

**Ağ:** Tüm servisler köprü ağı **`nac_dedicated_network`** üzerinde konuşur (`.env` ile isim sabitlenir).

**Bağımlılık sırası:** RADIUS, API’nin sağlıklı olmasına bağlıdır (`rlm_rest` için).

---

<a id="depo-yapisi"></a>
## Depo yapısı

```
.
├── api/                    # FastAPI uygulaması (main.py, requirements.txt)
├── db/init/                # PostgreSQL: şema + seed (01 … 05)
├── freeradius/config/      # sites, mods, policy.d
├── monitoring/             # Next.js bonus paneli
├── redis/                  # redis.conf
├── scripts/                # smoke-test.sh, radacct-demo.sh, …
├── docs/                   # RAPOR-TASLAK, ISTEK-KOMUTLARI, terimler, plan
├── docker-compose.yml
├── .env.example
└── Makefile
```

---

<a id="ortam-degiskenleri"></a>
## Ortam değişkenleri

1. `.env.example` dosyasını kopyalayıp **`.env`** oluşturun.
2. **`POSTGRES_PASSWORD`** değerini güçlü bir parola ile değiştirin.
3. `.env` `.gitignore` içindedir; repoya eklenmez.

Açıklamalar ve tüm anahtarlar: **`.env.example`**.

**Geliştirme:** Kod değişince API’yi yeniden başlatmadan denemek için `.env` içinde `UVICORN_RELOAD=1` kullanın; ardından API konteynerini yeniden başlatın.

---

<a id="veritabani-init"></a>
## Veritabanı başlatma (init sırası)

Yeni bir Postgres volume ile ilk `docker compose up` çalıştığında `docker-entrypoint-initdb.d` şu sırayı uygular:

| Dosya | İçerik |
|-------|--------|
| `01-freeradius-schema.sql` | FreeRADIUS tabloları (`radcheck`, `radreply`, `radacct`, …) |
| `02-seed-demo-user.sql` | Demo kullanıcılar (PAP hash, CHAP lab kullanıcısı, admin) |
| `03-authorization-policy.sql` | Gruplar, VLAN (`radgroupreply`), `radusergroup` |
| `04-mab-demo-device.sql` | MAB demo MAC / kullanıcı |
| `05-radreply-demo.sql` | `radreply` örneği: `demo` → `Session-Timeout` (PDF 3.6) |

**Eski volume:** Bu SQL’ler otomatik çalışmaz; aşağıdaki komutları **proje kökünden** bir kez çalıştırın:

```bash
docker exec -i nac_postgres psql -U nac -d nacdb < db/init/02-seed-demo-user.sql
docker exec -i nac_postgres psql -U nac -d nacdb < db/init/03-authorization-policy.sql
docker exec -i nac_postgres psql -U nac -d nacdb < db/init/04-mab-demo-device.sql
docker exec -i nac_postgres psql -U nac -d nacdb < db/init/05-radreply-demo.sql
```

`radreply` doğrulama örneği:

```bash
docker exec nac_postgres psql -U nac -d nacdb -c \
  "SELECT username, attribute, op, value FROM radreply ORDER BY id;"
```

---

<a id="saglik-ve-smoke"></a>
## Sağlık kontrolü ve smoke test

- **API:** `GET /health` — Postgres + Redis ping (200 / aksi halde 503).
- **Kök:** `GET http://localhost:8000/` — sürüm ve kısa rota listesi.
- **Otomatik:** `bash scripts/smoke-test.sh` veya `make smoke` (API + isteğe bağlı `radtest` / Postgres).

```bash
make ps      # docker compose ps
make smoke
```

---

<a id="dokumantasyon"></a>
## Dokümantasyon (rapor / komutlar)

| Dosya | Amaç |
|-------|------|
| [`docs/RAPOR-TASLAK.md`](docs/RAPOR-TASLAK.md) | Teknik rapor boş başlıklar |
| [`docs/ISTEK-KOMUTLARI.md`](docs/ISTEK-KOMUTLARI.md) | curl, radtest, radclient, psql |
| [`docs/TERIMLER-NAC.md`](docs/TERIMLER-NAC.md) | Terimler (octet, session id, NAS, …) |
| [`docs/CORE-DURUM-VE-PLAN.md`](docs/CORE-DURUM-VE-PLAN.md) | PDF çekirdek maddeleri + kalan plan |

---

<a id="adim-2-auth"></a>
## Adım 2 — Kimlik doğrulama (PAP, CHAP, MAB, rate limit)

Özet (ödev maddeleriyle eşleme):

| Madde | Uygulama |
|--------|-----------|
| Kimlik bilgileri PostgreSQL | `radcheck` (`demo`, `chapuser`, MAB: `aabbccddeeff`) |
| Parola hash; düz metin zorunluluğu (PAP) | **PAP:** `demo` → `MD5-Password` |
| Başarısız giriş rate limit | `freeradius/config/policy.d/nac` — `User-Name` bazlı sayaç |
| Doğrulama `radtest` | Aşağıdaki komutlar |

**CHAP ve hash:** RFC 1994 CHAP, sunucunun paylaşılan sırrı doğrulama anında bilmesini gerektirir; veritabanında yalnızca tek yönlü hash varken **standart CHAP doğrulaması yapılamaz**. Bu nedenle ödevdeki “plaintext yok / hash” şartı **PAP (`demo` + `MD5-Password`)** ile karşılanır. **CHAP** gösterimi için **`chapuser`** yalnızca `Cleartext-Password` ile eklenmiştir; rapor/videoda bu teknik nokta kısaca anlatılmalıdır.

### radtest (konteyner içinden)

**PAP (hash’li kullanıcı):**

```bash
docker exec nac_radius radtest demo DemoPass123 127.0.0.1 0 testing123
```

**CHAP (lab kullanıcısı — yukarıdaki notu okuyun):**

```bash
docker exec nac_radius radtest -t chap chapuser ChapPass789 127.0.0.1 0 testing123
```

**MAB (MAC Authentication Bypass) — bonus / lab**

- **Politika:** `freeradius/config/policy.d/nac_mab` — `User-Name` / `User-Password` MAC biçimindeyse **12 hex küçük harfe** normalize edilir; `radcheck` + PAP ile eşleşir.
- **Demo cihaz:** MAC `AA:BB:CC:DD:EE:FF` → kullanıcı `aabbccddeeff`, parola aynı (`Cleartext-Password`), grup **guest** → VLAN **30** (`db/init/04-mab-demo-device.sql`).

```bash
docker exec nac_redis redis-cli DEL nac_auth_fail_aabbccddeeff   # rate limit varsa
docker exec nac_radius radtest -x AA-BB-CC-DD-EE-FF AA-BB-CC-DD-EE-FF 127.0.0.1 0 testing123
```

Çıktıda `Tunnel-Private-Group-Id = 30` beklenir. **Not:** Üretimde port güvenliği + MAC whitelist şarttır; bu senaryo lab içindir.

**Kayıtlı olmayan MAC:** `policy.d/nac_mab_unknown` — veritabanında eşleşme yoksa `Access-Reject` + `Reply-Message`.

```bash
docker exec nac_radius radtest -x EE-EE-EE-EE-EE-EE EE-EE-EE-EE-EE-EE 127.0.0.1 0 testing123
# Beklenen: Access-Reject + Reply-Message
```

**Rate limit:** Başarısız denemeler Redis’te `nac_auth_fail_<User-Name>` ile sayılır; **5** başarısız reddedilen denemeden sonra **6.** istekte (parola doğru olsa bile) `Access-Reject`. TTL **900 sn**. Test için: `docker exec nac_redis redis-cli DEL nac_auth_fail_demo`. Başarılı girişte sayaç silinir.

---

<a id="adim-3-authorize"></a>
## Adım 3 — Yetkilendirme (grup, VLAN, `rlm_rest`)

- **Gruplar:** `admin`, `employee`, `guest` — `radusergroup` + `radgroupreply` (`db/init/03-authorization-policy.sql`).
- **VLAN:** `Tunnel-Type`, `Tunnel-Medium-Type`, `Tunnel-Private-Group-Id` — admin **10**, employee **20**, guest **30**.
- **rlm_sql:** `read_groups = no` — VLAN tekrarını önlemek için grup satırları yalnızca API tarafından okunur.
- **rlm_rest:** `mods-enabled/rest` → `POST http://api:8000/authorize` (JSON yanıt → reply attribute).
- **Kullanıcılar:** `demo` → employee, `chapuser` → guest, `admin` / `AdminPass!99` (MD5) → admin.

### VLAN doğrulama (`radtest -x`)

```bash
docker exec nac_redis redis-cli DEL nac_auth_fail_demo   # rate limit varsa
docker exec nac_radius radtest -x demo DemoPass123 127.0.0.1 0 testing123
```

Çıktıda `Tunnel-Private-Group-Id = 20` (employee) görülmeli.

### API doğrudan

```bash
curl -s -X POST http://localhost:8000/authorize -H "Content-Type: application/json" \
  -d '{"User-Name":{"type":"string","value":["demo"]}}' | jq .
```

**Not:** Eski Postgres volume için yetkilendirme + `radreply` örneği: [Veritabanı başlatma](#veritabani-init) bölümündeki `03` ve `05` (veya tüm zincir).

---

<a id="adim-4-accounting"></a>
## Adım 4 — Accounting, Redis, API

- **FreeRADIUS:** `acct` bölümünde `sql` + `policy.d/nac_accounting` ile `radacct` ve Redis `nac:acct:<Acct-Unique-Session-Id>` güncellenir.
- **API:** `POST /accounting` aynı mantığı HTTP ile test etmek için; `GET /sessions/active` Redis özetini döner.

### Accounting (`curl` — snake_case veya RADIUS alan adları)

```bash
curl -s -X POST http://localhost:8000/accounting -H "Content-Type: application/json" \
  -d '{
    "status": "Start",
    "username": "demo",
    "acct_session_id": "http-sess-1",
    "acct_unique_session_id": "http-uniq-1",
    "nas_ip_address": "10.0.0.1"
  }' | jq .

curl -s -X POST http://localhost:8000/accounting -H "Content-Type: application/json" \
  -d '{
    "Acct-Status-Type": "Interim-Update",
    "User-Name": "demo",
    "Acct-Session-Id": "http-sess-1",
    "Acct-Unique-Session-Id": "http-uniq-1",
    "NAS-IP-Address": "10.0.0.1",
    "Acct-Input-Octets": 1000,
    "Acct-Output-Octets": 2000,
    "Acct-Session-Time": 60
  }' | jq .

curl -s -X POST http://localhost:8000/accounting -H "Content-Type: application/json" \
  -d '{
    "status": "Stop",
    "username": "demo",
    "acct_session_id": "http-sess-1",
    "acct_unique_session_id": "http-uniq-1",
    "nas_ip_address": "10.0.0.1",
    "acct_session_time": 120
  }' | jq .

curl -s http://localhost:8000/sessions/active | jq .
```

### FreeRADIUS accounting — `radclient`

`radclient` `nac_radius` imajında vardır; kaynak adres `127.0.0.1` olduğu için `clients.conf` ile uyumludur.

```bash
bash scripts/radacct-demo.sh
```

Tekil paket örneği ve sorgular için detay: [`docs/ISTEK-KOMUTLARI.md`](docs/ISTEK-KOMUTLARI.md).

**Not:** `Stop` sonrası Redis anahtarı silinir; `GET /sessions/active` boş dönmesi beklenen davranıştır.

---

<a id="bonus-monitoring"></a>
## Bonus: İzleme paneli

Ödev PDF Bölüm 6: *“Bonus (+%5): PAP + MAB birlikte, **veya** monitoring dashboard, **veya** unit test.”* — bunlar alternatif bonus kalemleridir.

Bu repoda **monitoring dashboard**: **Next.js** (`monitoring/`) + FastAPI **`GET /monitoring/snapshot`**.

```bash
docker compose up -d
# Panel: http://localhost:3000  —  MONITORING_PORT .env ile değişir
curl -s http://localhost:8000/monitoring/snapshot | jq .
```

Yerel geliştirme (Docker’sız Next):

```bash
cd monitoring && npm install && INTERNAL_API_URL=http://127.0.0.1:8000 npm run dev
```

İmaj yenileme: `make monitoring-build && docker compose up -d monitoring` veya `docker compose build monitoring && docker compose up -d monitoring`.

**Panel “snapshot alınamadı”:** Eski imajda build zamanı sabitlenmiş olabilir — `docker compose build monitoring --no-cache && docker compose up -d monitoring`. `.env` içinde **`INTERNAL_API_URL=http://localhost:8000` kullanmayın** (monitoring konteynerinde yanlış host); compose zaten `http://api:8000` atar.

**`curl .../monitoring/snapshot` → 404:** API güncel `main.py` yüklemeden çalışıyor olabilir. `docker compose restart api` veya `UVICORN_RELOAD=1`. Doğrulama: `curl -s http://localhost:8000/ | jq .` → `"version": "0.2.2"` ve `"monitoring": "/monitoring/snapshot"`.

**API dokümantasyonu (Swagger):** `http://localhost:8000/docs`

---

<a id="teslim-checklist"></a>
## Teslim kontrol listesi

- [ ] `docker compose ps` — servisler healthy
- [ ] PAP + VLAN: `radtest -x demo ...` → `Tunnel-Private-Group-Id`
- [ ] MAB (isteğe bağlı): `radtest -x AA-BB-CC-DD-EE-FF ...` → VLAN 30
- [ ] Rate limit: ardışık başarısız deneme → `Access-Reject`
- [ ] `bash scripts/radacct-demo.sh` → `radacct` satırı + (Stop öncesi) Redis anahtarı
- [ ] API: `/health`, `/docs`, `/users`, `/sessions/active`, `POST /accounting`
- [ ] `make smoke` veya `bash scripts/smoke-test.sh`
- [ ] Bonus: monitoring `http://localhost:3000` + videoda kısa gösterim
- [ ] Kısa video: auth + accounting + API ekran görüntüsü
- [ ] Teknik rapor + anlamlı Git geçmişi (PDF Bölüm 4)

---

<a id="sorun-giderme"></a>
## Sorun giderme

| Belirti | Öneri |
|---------|--------|
| RADIUS auth başarısız, API log yok | `docker compose ps` — `api` healthy mi? `freeradius` API’ye bağlıdır. |
| API route yok (404) | `docker compose restart api` veya `docker compose build api && docker compose up -d --force-recreate api` |
| Seed / kullanıcı yok | [Veritabanı başlatma](#veritabani-init) — eski volume için `02`–`05` |
| Monitoring API’ye erişemiyor | Konteyner içi adres `http://api:8000`; `.env`’de localhost vermeyin |
| Apple Silicon RADIUS yavaş / platform | `platform: linux/amd64` — emülasyon normaldir |

Daha fazla komut: [`docs/ISTEK-KOMUTLARI.md`](docs/ISTEK-KOMUTLARI.md).

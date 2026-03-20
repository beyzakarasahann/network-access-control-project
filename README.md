# network-access-control-project

Docker altyapisi asagidaki ek gereksinimlerle guncellenmistir:

- Servisler arasi iletisim icin dedicated bridge network: `nac_dedicated_network`
- Tum servislerde `.env` tabanli environment variable kullanimi
- Her servis icin `healthcheck` tanimi
- Konfigurasyon ve veri kaliciligi icin volume mount yapisi

## Ortam degiskenleri

1. `.env.example` dosyasini kopyalayip `.env` olusturun.
2. `POSTGRES_PASSWORD` degerini guclu bir sifre ile degistirin.
3. `.env` dosyasi `.gitignore` icinde oldugu icin git'e dahil edilmez.

## Calistirma

```bash
docker compose up -d
```

Servis durumlarini kontrol etmek icin:

```bash
docker compose ps
# veya: make ps
```

### Hizli saglilik kontrolu

- **API:** `GET /health` — Postgres + Redis ping (HTTP 200 / aksi halde 503).
- **Otomatik test:** `bash scripts/smoke-test.sh` veya `make smoke` (API + istege bagli `radtest` / Postgres).
- **Gelistirme:** `.env` icinde `UVICORN_RELOAD=1` yapip API container’ini yeniden baslatin; `main.py` degisiklikleri `--reload` ile alinir (`.env.example`).

### Odev raporu

Bos basliklar: `docs/RAPOR-TASLAK.md`  
**İstek / curl / radtest komutları:** `docs/ISTEK-KOMUTLARI.md`

### Bonus puan (odev PDF — Bolum 6)

Metinde: *“Bonus puanlar (+%5): Her iki auth metodu (PAP + MAB), **monitoring dashboard**, unit test.”*  
Bunlar **alternatif bonus kalemleri**dir (her biri +%5 havuzundan bir parca olarak degerlendirilir; hepsini ayni anda yapmak zorunlu degil).

Bu repoda **monitoring dashboard**: **Next.js 15** (`monitoring/`) + FastAPI **`GET /monitoring/snapshot`**.

```bash
docker compose up -d
# Panel (varsayilan): http://localhost:3000  —  .env: MONITORING_PORT
curl -s http://localhost:8000/monitoring/snapshot | jq .
```

Yerel gelistirme (Docker’siz Next): `cd monitoring && npm install && INTERNAL_API_URL=http://127.0.0.1:8000 npm run dev`

Imaj yenileme: `docker compose build monitoring && docker compose up -d monitoring`

**Panel “snapshot alınamadı” diyorsa:** Eski imajda sayfa build anında statik gömülmüş olabilir — `docker compose build monitoring --no-cache && docker compose up -d monitoring`. `.env` içinde **`INTERNAL_API_URL=http://localhost:8000` kullanmayın** (container içinde localhost yanlış host); boş bırakın veya compose’daki `http://api:8000` kalsın.

**`curl .../monitoring/snapshot` → HTTP 404:** API süreci güncel `main.py` yüklemeden çalışıyordur (`uvicorn` varsayılan olarak `--reload` kullanmaz). Çözüm: `docker compose restart api` veya `.env` içinde `UVICORN_RELOAD=1` ile geliştirme. Doğrulama: `curl -s http://localhost:8000/ | jq .` çıktısında `"version": "0.2.2"` ve `"monitoring": "/monitoring/snapshot"` görünmeli.

## Adim 2 — PAP / CHAP, PostgreSQL, hash, Redis rate limit, radtest

Ozet (odev maddeleriyle esleme):

| Madde | Uygulama |
|--------|-----------|
| Kimlik bilgileri PostgreSQL | `radcheck` tablosu (`demo`, `chapuser`, MAB: `aabbccddeeff`) |
| Parola hash, plaintext kabul edilmez | **PAP:** `demo` kullanicisi `MD5-Password` (duz metin yok) |
| Basarisiz giris rate limit (Redis) | `freeradius/config/policy.d/nac` — tum auth denemeleri `User-Name` bazli sayilir |
| Dogrulama `radtest` | Asagidaki iki komut |

**CHAP ve hash:** RFC 1994 CHAP, sunucunun paylasilan sirri (parolayi) **dogrulama aninda** bilmesini gerektirir; veritabaninda yalnizca tek yonlu hash tutuldugunda **standart CHAP dogrulamasi yapilamaz**. Bu yuzden odevdeki **"plaintext yok / hash"** sarti **PAP (`demo` + `MD5-Password`)** ile tam karsilanir. **CHAP** gosterimi icin ayri lab kullanicisi **`chapuser`** yalnizca `Cleartext-Password` ile eklenmistir; rapor/videoda bu teknik zorunluluk kisaca aciklanmalidir.

### radtest (container icinden)

**PAP (hash’li kullanici):**

```bash
docker exec nac_radius radtest demo DemoPass123 127.0.0.1 0 testing123
```

**CHAP (lab kullanicisi — yukaridaki notu oku):**

```bash
docker exec nac_radius radtest -t chap chapuser ChapPass789 127.0.0.1 0 testing123
```

**MAB (MAC Authentication Bypass) — bonus / lab:**

- **Politika:** `freeradius/config/policy.d/nac_mab` — `User-Name` ve `User-Password` MAC formatindaysa (iki nokta, tire veya 12 hex) **12 hex kucuk harfe** normalize edilir; `radcheck` + PAP ile eslesir.
- **Demo cihaz:** MAC `AA:BB:CC:DD:EE:FF` → kullanici `aabbccddeeff` / parola ayni (`Cleartext-Password`), grup **guest** → VLAN **30** (`db/init/04-mab-demo-device.sql`).

```bash
docker exec nac_redis redis-cli DEL nac_auth_fail_aabbccddeeff   # rate limit varsa
docker exec nac_radius radtest -x AA-BB-CC-DD-EE-FF AA-BB-CC-DD-EE-FF 127.0.0.1 0 testing123
```

Ciktda `Tunnel-Private-Group-Id = 30` beklenir. **Not:** MAB’te parola MAC ile ayni oldugu icin bu **lab senaryosudur**; uretimde port bazli guvenlik + MAC whitelist sarttir.

- Basarisiz girisler Redis'te `nac_auth_fail_<User-Name>` anahtari ile sayilir; **5** basarisiz reddedilen denemeden sonra **6.** istekte (sifre dogru olsa bile) `Access-Reject` + `Reply-Message`. TTL **900 sn**; test icin: `docker exec nac_redis redis-cli DEL nac_auth_fail_demo`. Basarili giris yapilabildiginde sayac silinir.

**Not:** Postgres volume daha once olusturulduysa seed otomatik calismamis olabilir:

```bash
docker exec -i nac_postgres psql -U nac -d nacdb < db/init/02-seed-demo-user.sql
docker exec -i nac_postgres psql -U nac -d nacdb < db/init/04-mab-demo-device.sql
```

## Adim 3 — Yetkilendirme (grup / VLAN) ve FastAPI + rlm_rest

- **Gruplar:** `admin`, `employee`, `guest` — `radusergroup` + `radgroupreply` (`db/init/03-authorization-policy.sql`).
- **VLAN:** `Tunnel-Type`, `Tunnel-Medium-Type`, `Tunnel-Private-Group-Id` — admin **10**, employee **20**, guest **30**.
- **rlm_sql:** `read_groups = no` — VLAN tekrar etmesin; grup satirlari yalnizca API tarafindan okunur.
- **rlm_rest:** `mods-enabled/rest` → `POST http://api:8000/authorize` (JSON cevap → reply attribute).
- **Kullanicilar:** `demo`→employee, `chapuser`→guest, `admin` / `AdminPass!99` (MD5) → admin grubu.

### VLAN dogrulama (radtest -x)

```bash
docker exec nac_redis redis-cli DEL nac_auth_fail_demo   # rate limit varsa temizle
docker exec nac_radius radtest -x demo DemoPass123 127.0.0.1 0 testing123
```

Ciktda `Tunnel-Private-Group-Id = 20` (employee) gorulmeli.

### API dogrudan

```bash
curl -s -X POST http://localhost:8000/authorize -H "Content-Type: application/json" \
  -d '{"User-Name":{"type":"string","value":["demo"]}}' | jq .
```

**Not:** Eski Postgres volume icin: `docker exec -i nac_postgres psql -U nac -d nacdb < db/init/03-authorization-policy.sql`

**Compose sira:** `freeradius`, API ayakta olduktan sonra baslar (`rlm_rest` icin).

## Adim 4 — Accounting, Redis aktif oturum, API

- **FreeRADIUS:** `acct` bolumunde `sql` + `policy.d/nac_accounting` ile `radacct` ve Redis `nac:acct:<Acct-Unique-Session-Id>` guncellenir.
- **API:** `POST /accounting` ayni mantigi HTTP ile test etmek icin (FreeRADIUS SQL’den bagimsiz cagri); `GET /sessions/active` Redis ozeti.

**404 / eski kod:** API container `--reload` kullanmiyorsa `main.py` degisince route gorunmeyebilir:

```bash
docker compose restart api
# veya imaji yeniden uretmek icin:
# docker compose build api && docker compose up -d --force-recreate api
```

### Accounting (curl — snake_case veya RADIUS alan adlari)

```bash
curl -s -X POST http://localhost:8000/accounting -H "Content-Type: application/json" \
  -d '{
    "status": "Start",
    "username": "demo",
    "acct_session_id": "http-sess-1",
    "acct_unique_session_id": "http-uniq-1",
    "nas_ip_address": "10.0.0.1"
  }' | jq .

# RADIUS tarzi anahtarlar da kabul edilir:
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

### FreeRADIUS accounting — `radclient` (onerilen: container icinden)

`radclient` paketi `nac_radius` imajinda vardir; **kaynak adres `127.0.0.1`** oldugu icin `clients.conf` icindeki `localhost` istemcisi ile uyumludur. Makineden dogrudan `localhost:1813` denemek bazen Docker NAT yuzunden istemci eslesmez; bu yuzden asagidaki yontem daha guvenilir.

```bash
bash scripts/radacct-demo.sh
```

Tekil paket ornegi:

```bash
docker exec -i nac_radius radclient -x -r 2 127.0.0.1:1813 acct testing123 <<'EOF'
User-Name = "demo"
Acct-Status-Type = Start
Acct-Session-Id = "manual-1"
NAS-IP-Address = 127.0.0.1
EOF

# Start + Interim sonrasi (Stop oncesi) aktif oturum:
curl -s http://localhost:8000/sessions/active | jq .

# radacct satiri (Postgres kullanici/db .env ile ayni olmali):
docker exec nac_postgres psql -U nac -d nacdb -c \
  "SELECT acctsessionid, username, acctstoptime FROM radacct ORDER BY radacctid DESC LIMIT 5;"

docker exec nac_redis redis-cli --scan --pattern 'nac:acct:*'
```

**Not:** `Accounting-Stop` geldikten sonra Redis anahtari silinir; `GET /sessions/active` bos donmesi beklenen davranistir.

## Teslim / rapor icin kontrol listesi

- [ ] `docker compose ps` — tum servisler healthy
- [ ] PAP + VLAN: `radtest -x demo ...` → `Tunnel-Private-Group-Id`
- [ ] MAB (istege bagli): `radtest -x AA-BB-CC-DD-EE-FF ...` → VLAN 30
- [ ] Rate limit: ardisik basarisiz deneme → `Access-Reject`
- [ ] `bash scripts/radacct-demo.sh` → `radacct` satiri + (Stop oncesi) Redis anahtari
- [ ] API: `/health`, `/docs`, `/users`, `/sessions/active`, `POST /accounting`
- [ ] `make smoke` veya `bash scripts/smoke-test.sh`
- [ ] Bonus: monitoring `http://localhost:3000` + videoda kisa gosterim
- [ ] Kisa video: auth + accounting + API ekran goruntusu

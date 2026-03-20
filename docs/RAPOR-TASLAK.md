# NAC Projesi — Rapor Taslagi (odev / teslim)

Asagidaki basliklari kendi gozlemleriniz ve ekran goruntulerinizle doldurun.

## 1. Giris

- Proje amaci (802.1X / NAC, AAA)
- Kullanilan bilesenler: Docker, FreeRADIUS, PostgreSQL, Redis, FastAPI

## 2. Mimari

- Servis diyagrami (kutu: NAS / RADIUS / DB / Redis / API)
- Ag: `nac_dedicated_network`, port ozeti (`1812/1813`, `8000`, `5432`, `6379`)

## 3. Kimlik dogrulama (Authentication)

- PostgreSQL `radcheck`: ornek kullanicilar (`demo` MD5-Password, `chapuser` CHAP notu)
- PAP testi: `radtest` komutu + cikti ozeti
- CHAP: neden ayri Cleartext-Password kullanicisi gerektigi (RFC / hash)
- Redis rate limit: esik, anahtar adi, TTL, kilitlenme davranisi

## 4. Yetkilendirme (Authorization)

- Gruplar ve VLAN (`radusergroup`, `radgroupreply`)
- `rlm_sql` `read_groups = no` gerekcesi
- `rlm_rest` → `POST /authorize`: ornek JSON cevap (Tunnel-*)

## 5. MAB (varsa)

- `nac_mab_normalize` politikasinin rolu
- Demo MAC ve VLAN sonucu (`radtest -x`)

## 6. Accounting

- FreeRADIUS: `sql` + Redis `nac_acct:*` politikasi
- `radclient` veya `scripts/radacct-demo.sh` ozeti
- API: `POST /accounting`, `GET /sessions/active` (HTTP test)

## 6b. Monitoring dashboard (bonus)

- Next.js panelinin rolu, `INTERNAL_API_URL` / Docker agi
- `GET /monitoring/snapshot` icinde hangi metrikler (saglik, Redis oturum, radacct ozeti)

## 7. Guvenlik ve sinirlar

- Paylasilan sifre (`testing123`) yalnizca lab
- `.env` / sifrelerin repoda olmamasi
- MAB ve Cleartext-Password’un uretim riski

## 8. Sonuc

- Odev maddeleriyle eslestirme tablosu
- Karsilasilan sorunlar ve cozumler
- Istege bagli gelistirmeler

## Ek: Komut listesi

README’deki `docker compose`, `radtest`, `curl`, `scripts/smoke-test.sh` satirlarini buraya kopyalayip calistirdiginiz ciktiyi yapistirin.

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
```

# MultiScout — Akıllı Fırsat Takipçisi

Amazon.tr, Trendyol ve N11 üzerindeki indirimli ürünleri tarayan, fiyat geçmişini saklayan FastAPI + Next.js uygulaması.

## Canlı Demo
- Frontend: https://multi-scouts-6mvzgir42-gokhansprojects.vercel.app
- Backend API: https://multiscout.onrender.com

## Hızlı Kurulum (Lokal Docker)

```bash
cp backend/.env.example backend/.env
# .env içine DATABASE_URL (Neon/Postgres) gir; API_KEY istersen üret
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs

## Ortam Değişkenleri (backend)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `DATABASE_URL` | (zorunlu) | PostgreSQL connection string |
| `API_KEY` | (boş) | Boşsa korumalı endpoint'ler açık; doluysa `X-API-KEY` header zorunlu |
| `CORS_ORIGINS` | `http://localhost:3000` | Virgülle ayrılmış |
| `SCHEDULER_ENABLED` | `true` | `false` = otomatik tarama kapalı |
| `AMAZON_SCRAPE_INTERVAL_MIN` | `60` | Amazon scheduler aralığı (dk) |
| `OTHER_SCRAPE_INTERVAL_MIN` | `45` | Trendyol/N11 scheduler aralığı |
| `CLEANUP_INTERVAL_HOUR` | `3` | DB duplicate temizlik aralığı |
| `DATA_DIR` | `data` | JSON dosyaları için klasör |

## API

- `GET /api/categories` — düz kategori listesi
- `GET /api/category-tree` — sidebar için iç içe ağaç
- `GET /api/deals?platform=amazon&category=gida&sort_by=last_updated`
- `GET /api/scrape-all-status` — top-level `status` + per-platform durum
- `GET /api/compare-prices?product_id=amazon_XXXXX`
- `POST /api/scrape-all?platform=all` — `X-API-KEY` gerekli (API_KEY varsa)
- `POST /api/deals-reset-db` — korumalı
- `POST /api/deals-cleanup-json` — korumalı
- `POST /api/deals-cleanup-duplicates` — korumalı

## Mimari

```
backend/
  app/
    core/auth.py          # X-API-KEY dependency
    core/category_mapping.py
    models/database.py    # SQLAlchemy + deal_score
    routers/              # deals, scrape, compare
    scrapers/             # amazon, trendyol, n11
    scrapers/io.py        # paylaşılan JSON IO + asyncio lock
    services/             # sync, scheduler
frontend/app/page.tsx     # ana arayüz
frontend/components/Sidebar.tsx
```

## Bilinen Sınırlamalar

- **Hepsiburada** devre dışı (bot koruması).
- Render ücretsiz: 512MB RAM Playwright için sınırda, cold start ~15dk inaktivitenin sonunda.
- JSON dosyaları geçici (Render restart'ta silinir); kalıcı veri PostgreSQL'de.

## Üretim Deploy

- Backend: Render Web Service (Docker) — `API_KEY` ve `CORS_ORIGINS` set et.
- Frontend: Vercel veya Render — `NEXT_PUBLIC_API_URL` build-time tanımlı olmalı.
- DB: Neon.tech (ücretsiz Postgres).

"""
marketfiyati.org.tr scraper — TÜBİTAK + Ticaret Bakanlığı + TCMB destekli resmi
market fiyatı API'sini kullanarak A101, BİM, ŞOK, MİGROS, CarrefourSA, HAKMAR,
Tarım Kredi Kooperatif marketlerinin fiyatlarını çeker.

Cross-market discount: aynı ürün için en yüksek vs bulduğumuz fiyat farkı
discount yüzdesi olarak hesaplanır. Yalnızca en yüksek fiyatı sunan market
filtrelenir (gerçek tasarruf sunan marketler kaydedilir).
"""
import asyncio
import json
import ssl
from datetime import datetime
from typing import Iterable
import urllib.parse
import urllib.request
import urllib.error

from app.scrapers.io import get_file_lock, load_deals, save_deals, merge_deals_by_link


API_URL = "https://api.marketfiyati.org.tr/api/v2/search"
SITE_PRODUCT_URL = "https://marketfiyati.org.tr/ara?q={}"

HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "referer": "https://marketfiyati.org.tr/",
    "origin": "https://marketfiyati.org.tr",
    "pragma": "no-cache",
    "cache-control": "no-cache",
    "withcredentials": "true",
}

_SSL_CTX = ssl.create_default_context()

# Aynı zincirin farklı yazımları için normalize map
MARKET_KEY_ALIASES = {
    "a101": "a101",
    "bim": "bim",
    "sok": "sok",
    "şok": "sok",
    "migros": "migros",
    "carrefour": "carrefoursa",
    "carrefoursa": "carrefoursa",
    "tarim_kredi": "tarimkredi",
    "tarimkredi": "tarimkredi",
    "tarımkredi": "tarimkredi",
}

# Internal label → bizim platform key
ALL_MARKET_KEYS = ["a101", "bim", "sok", "migros", "carrefoursa", "tarimkredi"]


def _normalize_market(raw: str) -> str | None:
    if not raw:
        return None
    return MARKET_KEY_ALIASES.get(raw.lower().strip())


def _format_tl(n: float) -> str:
    s = f"{n:,.2f}"
    # locale-aware TR format: 1,234.56 → 1.234,56
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} TL"


def _fetch_keyword(keyword: str, size: int = 24, timeout: int = 30) -> list[dict]:
    body = json.dumps({"keywords": keyword, "pages": 0, "size": size}).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, method="POST", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data.get("content", []) or []
    except urllib.error.HTTPError as e:
        print(f"[MarketFiyati] HTTP {e.code} ({keyword}): {e.read()[:200]!r}", flush=True)
        return []
    except Exception as e:
        print(f"[MarketFiyati] HATA ({keyword}): {e}", flush=True)
        return []


def _build_link(product_id: str, title: str) -> str:
    if product_id:
        return f"https://marketfiyati.org.tr/urun/{product_id}"
    return SITE_PRODUCT_URL.format(urllib.parse.quote_plus(title))


async def scrape_marketfiyati_all(
    output_files: dict[str, str],
    category: str = "temel-gida",
    keywords: Iterable[str] = (),
    min_discount: int = 5,
    page_size: int = 30,
) -> dict[str, int]:
    """
    Tek API çağrısında 7 market için fırsat üretir.
    output_files: {"a101": "data/deals_a101.json", "bim": ..., ...}
    keywords: aramada kullanılacak anahtar kelimeler (örn. ["süt","ekmek","yumurta"])
    """
    bucket: dict[str, list[dict]] = {k: [] for k in ALL_MARKET_KEYS}
    seen_links: dict[str, set[str]] = {k: set() for k in ALL_MARKET_KEYS}
    raw_total = 0

    for kw in keywords:
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, _fetch_keyword, kw, page_size)
        raw_total += len(content)
        print(f"[MarketFiyati] '{kw}': {len(content)} ürün", flush=True)

        for item in content:
            depots = item.get("productDepotInfoList") or []
            if len(depots) < 2:
                # Sadece tek market satıyorsa cross-market discount yok
                continue
            prices = [d.get("price") for d in depots if isinstance(d.get("price"), (int, float)) and d.get("price") > 0]
            if not prices:
                continue
            max_price = max(prices)
            if max_price <= 0:
                continue

            title_base = (item.get("title") or "").strip()
            if not title_base or len(title_base) < 3:
                continue
            img = item.get("imageUrl") or ""
            product_id = item.get("id") or ""
            link_base = _build_link(product_id, title_base)

            for d in depots:
                market_key = _normalize_market(d.get("marketAdi"))
                if not market_key or market_key not in bucket:
                    continue
                price = d.get("price")
                if not isinstance(price, (int, float)) or price <= 0:
                    continue
                # Her marketin bu üründeki en iyi fiyatını tut (aynı zincirin farklı mağazalarından sadece en ucuzu)
                discount = int(round(((max_price - price) / max_price) * 100))
                if discount < min_discount:
                    continue
                # link unique per market: marketfiyati ortak link + market suffix
                link = f"{link_base}#{market_key}"
                if link in seen_links[market_key]:
                    # daha önce gördükse en ucuz olanı tut
                    continue
                seen_links[market_key].add(link)

                depot_name = (d.get("depotName") or "").strip()
                # title örneğin: "Süt 1L · Şube: Çiçekçi Üsküdar"
                title = title_base
                if len(title) > 110:
                    title = title[:110] + "..."

                bucket[market_key].append({
                    "title": title,
                    "price": _format_tl(float(price)),
                    "discount_percentage": discount,
                    "link": link,
                    "image": img,
                    "source": market_key,
                    "category": category,
                    "depot": depot_name,
                    "unit_price": d.get("unitPrice") or "",
                    "max_price": _format_tl(float(max_price)),
                    "last_updated": datetime.now().isoformat(),
                })

    counts = {}
    for market_key, deals in bucket.items():
        out_path = output_files.get(market_key)
        if not out_path:
            continue
        async with get_file_lock(out_path):
            existing = load_deals(out_path)
            merged = merge_deals_by_link(existing, deals)
            save_deals(out_path, merged)
        counts[market_key] = len(deals)
        print(f"[MarketFiyati] {market_key}: {len(deals)} yeni / {len(merged)} toplam", flush=True)

    print(f"[MarketFiyati] Toplam ham: {raw_total}, kelime sayısı: {len(list(keywords))}", flush=True)
    return counts

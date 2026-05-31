"""Peynirci Baba scraper — peynircibaba.com / .com.tr

Klasik OpenCart tarzı statik HTML sitesi. Playwright gerekmez — urllib + regex
yeterli. Her kategori sayfasında `.one-product` card'ları var, indirimli olanlar
`<span class="price old" data-original="86,25 TL">86,25 TL</span>` + bir başka
`<span class="price">75,25 TL</span>` çiftiyle gösteriliyor.

Sayfalama: `?sayfa=N`. Bir kategoride 21 ürün/sayfa.
"""
import asyncio
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime

from app.scrapers.io import get_file_lock, load_deals, merge_deals_by_link, save_deals


BASE = "https://www.peynircibaba.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "tr-TR,tr;q=0.9",
}
_SSL_CTX = ssl.create_default_context()

# `<div class="one-product"> ... <div class="product-actions">` arası tek kart.
_CARD_RE = re.compile(
    r'<div class="one-product">(.*?)<div class="product-actions">',
    re.DOTALL,
)
_NAME_RE = re.compile(r'<span class="product-name">(.*?)</span>', re.DOTALL)
_LINK_IMG_RE = re.compile(
    r'<div class="product-image">\s*<a href="([^"]+)"><img src="([^"]+)"',
    re.DOTALL,
)
_OLD_PRICE_RE = re.compile(
    r'<span class="price old" data-original="([^"]+)"', re.IGNORECASE
)
_NEW_PRICE_RE = re.compile(
    r'<span class="price">([^<]+)</span>', re.IGNORECASE
)
_PAGE_RE = re.compile(r'\?sayfa=(\d+)', re.IGNORECASE)


def _tr_to_float(s: str) -> float | None:
    if not s:
        return None
    m = re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}|\d+(?:,\d{2})?", s)
    if not m:
        return None
    try:
        return float(m.group(0).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _fetch(url: str, timeout: int = 25) -> str | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[PeynirciBaba] fetch error {url}: {e}", flush=True)
        return None


def _max_page(html: str) -> int:
    pages = [int(m) for m in _PAGE_RE.findall(html) if m.isdigit()]
    return max(pages) if pages else 1


def _parse_cards(html: str) -> list[dict]:
    items: list[dict] = []
    for card_html in _CARD_RE.findall(html):
        link_img = _LINK_IMG_RE.search(card_html)
        if not link_img:
            continue
        link = link_img.group(1).strip()
        image = link_img.group(2).strip()
        name_m = _NAME_RE.search(card_html)
        if not name_m:
            continue
        # <br />, <br>, gereksiz html temizle
        raw_title = re.sub(r"<[^>]+>", " ", name_m.group(1))
        title = re.sub(r"\s+", " ", raw_title).strip()
        if len(title) < 3:
            continue

        old_m = _OLD_PRICE_RE.search(card_html)
        new_m = _NEW_PRICE_RE.search(card_html)
        if not old_m or not new_m:
            continue
        old_price = _tr_to_float(old_m.group(1))
        new_price = _tr_to_float(new_m.group(1))
        if not old_price or not new_price or new_price <= 0:
            continue
        if old_price <= new_price:
            continue
        discount = round((old_price - new_price) / old_price * 100)

        items.append({
            "title": title[:150],
            "price": f"{new_price:.2f}".replace(".", ",") + " TL",
            "original": f"{old_price:.2f}".replace(".", ",") + " TL",
            "discount_percentage": int(discount),
            "link": link,
            "image": image,
        })
    return items


async def scrape_peynircibaba_deals(
    output_file: str,
    category: str = "indirimli-urunler",
    min_discount: int = 5,
    max_pages: int = 5,
    category_url: str | None = None,
):
    """Peynirci Baba kategori sayfasından indirimli ürünleri çeker.

    category: site slug (örn. "beyaz-peynir", "kasar-peyniri", "indirimli-urunler").
    category_url: opsiyonel doğrudan URL; verilmezse BASE/{category}/ oluşturulur.
    """
    base_url = (category_url or f"{BASE}/{category}/").rstrip("/")
    deals: list[dict] = []
    print(f"[PeynirciBaba] Başlıyor: {base_url}", flush=True)

    loop = asyncio.get_running_loop()
    first_html = await loop.run_in_executor(None, _fetch, base_url + "/")
    if not first_html:
        print(f"[PeynirciBaba] {category}: ilk sayfa alınamadı", flush=True)
        return
    total_pages = min(_max_page(first_html), max_pages)
    print(f"[PeynirciBaba] {category}: {total_pages} sayfa taranacak", flush=True)

    raw_total = 0
    for page_no in range(1, total_pages + 1):
        url = base_url + ("/" if page_no == 1 else f"/?sayfa={page_no}")
        html = first_html if page_no == 1 else await loop.run_in_executor(None, _fetch, url)
        if not html:
            continue
        cards = _parse_cards(html)
        raw_total += len(cards)
        for c in cards:
            if c["discount_percentage"] < min_discount:
                continue
            deals.append({
                "title": c["title"],
                "price": c["price"],
                "discount_percentage": c["discount_percentage"],
                "link": c["link"],
                "image": c["image"],
                "source": "peynircibaba",
                "category": category,
                "last_updated": datetime.now().isoformat(),
            })
        # nazik gecikme
        if page_no < total_pages:
            await asyncio.sleep(0.8)

    print(
        f"[PeynirciBaba] {category}: {raw_total} ham, {len(deals)} kept "
        f"(min_discount={min_discount})",
        flush=True,
    )

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(
            f"[PeynirciBaba] Toplam {len(merged)} ürün kaydediliyor (yeni: {len(deals)})...",
            flush=True,
        )
        save_deals(output_file, merged)

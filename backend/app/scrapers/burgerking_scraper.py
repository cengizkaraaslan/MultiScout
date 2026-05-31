"""Burger King kampanya scraper — burgerking.com.tr/kampanyalar

Klasik server-side render edilmiş HTML. Her kampanya `.item.item-primary`
wrapper'ında:
  - .figure img[src + alt]    → banner + alt
  - .heading > a[href]          → kampanya başlığı + detay URL'i
  - .desc > p                   → kısa açıklama (fiyat satırı varsa burada)
  - .content > p                → şartlar (kampanya bitiş tarihi vb.)

İki tab: paket-servis-kampanyalari + restoran-kampanyalari (ikisi de aynı
markup, ayrım yapmadan hepsini çekiyoruz).
"""
import asyncio
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime
from html import unescape

from app.scrapers.io import get_file_lock, load_deals, merge_deals_by_link, save_deals


BASE = "https://www.burgerking.com.tr"
LIST_URL = f"{BASE}/kampanyalar"
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

# Bir kampanya kartı: <div class="item item-primary col-sm-6">…</div>
# Bir sonraki kampanyaya geçene kadar tüm içeriği al.
_CARD_RE = re.compile(
    r'<div class="item item-(?:primary|secondary)[^"]*">(.*?)(?=<div class="item item-(?:primary|secondary)|<footer|$)',
    re.DOTALL,
)
_IMG_RE = re.compile(
    r'<a href="(/kampanyalar/[^"]+)"[^>]*><img src="([^"]+)" alt="([^"]*)"',
    re.DOTALL,
)
_HEADING_RE = re.compile(
    r'<h2 class="heading"><a[^>]*>(.*?)</a></h2>',
    re.DOTALL,
)
_DESC_RE = re.compile(r'<div class="desc">\s*<p>(.*?)</p>', re.DOTALL)


def _clean_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _fetch(url: str, timeout: int = 25) -> str | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[BurgerKing] fetch error {url}: {e}", flush=True)
        return None


def _detect_category(title: str, desc: str) -> str:
    """Title + desc'den kampanya tipi tahmin et — frontend filtresi için."""
    t = (title + " " + desc).lower()
    # 1+1 / 2 alana 1 bedava / ikincisi bedava → BOGO
    if re.search(r"(alana|al,?)\s*1\s*bedava|ikincisi\s+bedava|1\+1\b|2\+1\b|3\+1\b", t):
        return "1plus1-bedava"
    if "ikili" in t or "2'li" in t or "2li" in t or "ikinci" in t:
        return "ikili-firsat"
    if "kral" in t or "menü" in t or "menu" in t or "kombo" in t:
        return "kombo-menu"
    if "çocuk" in t or "cocuk" in t or "king junior" in t:
        return "cocuk-menusu"
    if "kahvaltı" in t or "kahvalti" in t:
        return "kahvalti"
    return "kampanya"


def _extract_price_hint(desc: str) -> tuple[str, int]:
    """desc'te "550 TL'den başlayan" tarzı fiyat varsa yakala."""
    m = re.search(r"(\d{1,4}(?:\.\d{3})*)\s*TL", desc)
    if not m:
        return ("Kampanya", 0)
    return (f"{m.group(1)} TL'den", 0)


async def scrape_burgerking_deals(
    output_file: str,
    category: str = "kampanya",
    min_discount: int = 0,
    max_pages: int = 1,
    category_url: str | None = None,
):
    """Burger King kampanya sayfasını çeker. Tek sayfa, ~10-20 kampanya."""
    url = category_url or LIST_URL
    deals: list[dict] = []
    print(f"[BurgerKing] Başlıyor: {url}", flush=True)

    loop = asyncio.get_running_loop()
    html = await loop.run_in_executor(None, _fetch, url)
    if not html:
        print("[BurgerKing] HTML alınamadı", flush=True)
        return

    raw = 0
    seen: set[str] = set()
    for card in _CARD_RE.findall(html):
        raw += 1
        img_m = _IMG_RE.search(card)
        if not img_m:
            continue
        slug = img_m.group(1).strip()
        link = BASE + slug
        if link in seen:
            continue
        seen.add(link)

        image_path = img_m.group(2).strip()
        if image_path.startswith("/"):
            image = BASE + image_path
        elif image_path.startswith("//"):
            image = "https:" + image_path
        else:
            image = image_path

        head_m = _HEADING_RE.search(card)
        title = _clean_text(head_m.group(1)) if head_m else _clean_text(img_m.group(3))
        if len(title) < 3:
            continue
        title = title[:180]

        desc_m = _DESC_RE.search(card)
        desc = _clean_text(desc_m.group(1)) if desc_m else ""

        price, _disc = _extract_price_hint(desc)
        cat_slug = _detect_category(title, desc)

        deals.append({
            "title": title,
            "price": price,
            "discount_percentage": 0,
            "link": link,
            "image": image,
            "source": "burgerking",
            "category": cat_slug,
            "last_updated": datetime.now().isoformat(),
        })

    print(f"[BurgerKing] {raw} ham, {len(deals)} kampanya kaydedilecek", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(
            f"[BurgerKing] Toplam {len(merged)} kampanya (yeni: {len(deals)})...",
            flush=True,
        )
        save_deals(output_file, merged)

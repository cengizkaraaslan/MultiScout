"""McDonald's Türkiye kampanya scraper — mcdonalds.com.tr/kampanyalar

Server-side render edilmiş klasik HTML. Tüm kampanyalar `div.campaign-box`
wrapper'ında, içinde:
  - <img src="/Files/Kampanyalar/...">  → banner
  - <div class="campaign-text">
      <h2>BAŞLIK</h2>
      <p>açıklama (genelde boş)</p>
      <a href="/kampanyalar/...">DAHA FAZLA BİLGİ</a>

Tab'lar (type-1, type-2, ...) farklı kategoriler için ama hepsi aynı sayfada
render ediliyor; tabsız hepsini sıyırıyoruz.
"""
import asyncio
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime
from html import unescape

from app.scrapers.io import get_file_lock, load_deals, merge_deals_by_link, save_deals


BASE = "https://www.mcdonalds.com.tr"
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

# Bir kampanya kartı: <div class="campaign-box clearfix">…</div>
# Sonraki campaign-box veya bölüm sonuna kadar yakala.
_CARD_RE = re.compile(
    r'<div class="campaign-box[^"]*">(.*?)(?=<div class="campaign-box|</div>\s*</div>\s*</div>\s*</div>)',
    re.DOTALL,
)
_IMG_RE = re.compile(r'<img\s+src="([^"]+)"', re.DOTALL)
_TITLE_RE = re.compile(r'<h2[^>]*>(.*?)</h2>', re.DOTALL)
_LINK_RE = re.compile(r'<a\s+href="(/kampanyalar/[^"]+)"', re.DOTALL)
_DESC_RE = re.compile(r'<p[^>]*>(.*?)</p>', re.DOTALL)

# BurgerKing'den alındı — 1+1 / alana 1 bedava / ikincisi bedava
_BOGO_RE = re.compile(
    r"(alana|al,?)\s*1\s*bedava|ikincisi\s+bedava|1\+1\b|2\+1\b|3\+1\b",
    re.IGNORECASE,
)


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
        print(f"[McDonalds] fetch error {url}: {e}", flush=True)
        return None


def _detect_category(title: str, desc: str) -> str:
    """Title + desc'den kampanya tipi tahmin et — frontend filtresi için."""
    t = (title + " " + desc).lower()
    if _BOGO_RE.search(t):
        return "1plus1-bedava"
    if "ikili" in t or "2'li" in t or "2li" in t or "ikinci" in t:
        return "ikili-firsat"
    if "happy meal" in t or "çocuk" in t or "cocuk" in t:
        return "cocuk-menusu"
    if "kahvaltı" in t or "kahvalti" in t or "mcmuffin" in t:
        return "kahvalti"
    if "mchesaplı" in t or "mchesapli" in t or "menü" in t or "menu" in t or "kombo" in t:
        return "kombo-menu"
    return "kampanya"


def _extract_price_hint(text: str) -> str:
    m = re.search(r"(\d{1,4}(?:\.\d{3})*)\s*TL", text)
    if not m:
        return "Kampanya"
    return f"{m.group(1)} TL'den"


async def scrape_mcdonalds_deals(
    output_file: str,
    category: str = "kampanya",
    min_discount: int = 0,
    max_pages: int = 1,
    category_url: str | None = None,
):
    """McDonald's Türkiye kampanya sayfasını çeker. Tek sayfa, ~20-30 kampanya."""
    url = category_url or LIST_URL
    deals: list[dict] = []
    print(f"[McDonalds] Başlıyor: {url}", flush=True)

    loop = asyncio.get_running_loop()
    html = await loop.run_in_executor(None, _fetch, url)
    if not html:
        print("[McDonalds] HTML alınamadı", flush=True)
        return

    raw = 0
    seen: set[str] = set()
    for card in _CARD_RE.findall(html):
        raw += 1
        link_m = _LINK_RE.search(card)
        if not link_m:
            continue
        slug = link_m.group(1).strip()
        link = BASE + slug
        if link in seen:
            continue
        seen.add(link)

        img_m = _IMG_RE.search(card)
        image = ""
        if img_m:
            image_path = img_m.group(1).strip()
            if image_path.startswith("//"):
                image = "https:" + image_path
            elif image_path.startswith("/"):
                image = BASE + image_path
            else:
                image = image_path

        title_m = _TITLE_RE.search(card)
        title = _clean_text(title_m.group(1)) if title_m else ""
        if len(title) < 3:
            continue
        title = title[:180]

        desc_m = _DESC_RE.search(card)
        desc = _clean_text(desc_m.group(1)) if desc_m else ""

        price = _extract_price_hint(desc + " " + title)
        cat_slug = _detect_category(title, desc)

        deals.append({
            "title": title,
            "price": price,
            "discount_percentage": 0,
            "link": link,
            "image": image,
            "source": "mcdonalds",
            "category": cat_slug,
            "last_updated": datetime.now().isoformat(),
        })

    print(f"[McDonalds] {raw} ham, {len(deals)} kampanya kaydedilecek", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(
            f"[McDonalds] Toplam {len(merged)} kampanya (yeni: {len(deals)})...",
            flush=True,
        )
        save_deals(output_file, merged)

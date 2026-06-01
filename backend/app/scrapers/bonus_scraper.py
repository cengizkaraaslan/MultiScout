"""Bonus (Garanti BBVA) kampanya scraper — bonus.com.tr/kampanyalar

Klasik server-side render edilmiş Angular sayfası — kampanyalar HTML'e
gömülü, JS gerekmez. Tüm kartlar tek sayfada, hidden olanlar da dahil.

Kart şablonu (tek satıra sıkıştırılmış):
  <li itemprop="itemListElement" itemscope itemtype="http://schema.org/Offer"
      class="campaign-box check-box-item ..."
      data-sector="market" data-brand="bonus"
      data-name="bonus - ... TL ... bonus!" data-text="..." ...>
    <a class="add-to-favorite"></a>
    <a itemprop="url" href="/kampanyalar/<slug>" class="direct"
       aria-label="Kampanya - <başlık>">
       <div class="campaign-box__image-content">
         <picture>
           <source data-srcset=".../x.webp" type="image/webp" ...>
           <img data-src=".../x.jpg" class="campaign-box__image lazy" alt="<başlık>">
         </picture>
       </div>
       <h3 itemprop="name" class="campaign-box__title">başlık <strong>vurgu</strong></h3>
    </a>
    ...
  </li>

Gzip decode için urllib zaten plain alıyor ama server `Accept-Encoding: gzip`
istediğimizde gzip dönerse Turkcell scraper'daki gibi manuel açıyoruz.
"""
import asyncio
import gzip
import re
import ssl
import urllib.error
import urllib.request
import zlib
from datetime import datetime
from html import unescape

from app.scrapers.io import get_file_lock, load_deals, merge_deals_by_link, save_deals


BASE = "https://www.bonus.com.tr"
CANDIDATE_URLS = [
    f"{BASE}/kampanyalar",
    f"{BASE}/firsatlar",
    f"{BASE}/",
]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}
_SSL_CTX = ssl.create_default_context()

# Her <li ... class="campaign-box check-box-item ..."> ... </li> kartı.
# Aynı satırda yüzlerce kart olabilir, bir sonraki <li ...campaign-box'a kadar al.
_CARD_RE = re.compile(
    r'<li itemprop="itemListElement"[^>]*class="campaign-box check-box-item[^"]*"'
    r'(?P<attrs>[^>]*)>'
    r'(?P<body>.*?)</li>',
    re.DOTALL,
)
_ATTR_RE = re.compile(r'\b([a-z][\w-]*)="([^"]*)"')
_HREF_RE = re.compile(r'<a itemprop="url" href="([^"]+)"', re.DOTALL)
_TITLE_RE = re.compile(
    r'<h3 itemprop="name" class="campaign-box__title">(.*?)</h3>',
    re.DOTALL,
)
_IMG_SRC_RE = re.compile(r'<img[^>]*data-src="([^"]+)"', re.DOTALL)
_WEBP_RE = re.compile(r'<source[^>]*data-srcset="([^"]+\.webp)"', re.DOTALL)
_ARIA_RE = re.compile(r'aria-label="([^"]+)"')


def _clean_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = unescape(s)
    s = s.replace("\xa0", " ").replace("​", "")
    s = s.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip()


def _fetch(url: str, timeout: int = 25) -> str | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as r:
            raw = r.read()
            enc = (r.headers.get("Content-Encoding") or "").lower()
            if enc == "gzip":
                raw = gzip.decompress(raw)
            elif enc == "deflate":
                try:
                    raw = zlib.decompress(raw)
                except zlib.error:
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            html = raw.decode("utf-8", errors="ignore")
            # BOM kırp
            if html and html[0] == "﻿":
                html = html.lstrip("﻿")
            return html
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[Bonus] fetch error {url}: {e}", flush=True)
        return None


def _ascii_lower(s: str) -> str:
    return (
        s.lower()
        .replace("ı", "i").replace("İ", "i")
        .replace("ş", "s").replace("Ş", "s")
        .replace("ç", "c").replace("Ç", "c")
        .replace("ğ", "g").replace("Ğ", "g")
        .replace("ü", "u").replace("Ü", "u")
        .replace("ö", "o").replace("Ö", "o")
    )


# Sector slug -> normalize kategori
_SECTOR_MAP = {
    "market": "market",
    "gida": "market",
    "yeme-icme": "restoran",
    "restaurant": "restoran",
    "turizm": "seyahat",
    "otel": "seyahat",
    "havayollari": "seyahat",
    "ulasim": "seyahat",
    "arac-kiralama": "seyahat",
    "akaryakit": "akaryakit",
    "otomotiv": "akaryakit",
    "oto-bakim": "akaryakit",
    "eglence": "sinema",
    "dijital-platformlar": "sinema",
    "e-ticaret": "online",
    "giyim": "giyim",
    "kozmetik": "kisisel-bakim",
    "saglik": "kisisel-bakim",
    "spor-salonu": "spor",
    "egitim": "egitim",
    "elektronik": "elektronik",
    "beyaz-esya": "elektronik",
    "ev-tekstili": "ev",
    "mobilya": "ev",
    "zuccaciye": "ev",
    "isitmasogutma": "ev",
    "yapi-sektoru": "ev",
    "kuyumculuk": "aksesuar",
    "saat": "aksesuar",
    "kirtasiye": "kirtasiye",
    "oyuncak": "oyuncak",
    "kamu-ve-vergi-odemeleri": "fatura",
}


def _detect_category(sector: str, blob_low: str, flags: dict[str, str]) -> str:
    """Önce title/desc'teki güçlü ipuçları (chargeback/iade/taksit), sonra sector."""
    if "chargeback" in blob_low:
        return "chargeback"
    if "iade" in blob_low and ("%" in blob_low or "geri" in blob_low):
        return "iade"
    # data-taksit-kampanyalari="true" ise taksit
    if flags.get("data-taksit-kampanyalari") == "true" or re.search(r"\btaksit\b", blob_low):
        return "taksit"
    if flags.get("data-indirim-kampanyalari") == "true" or "indirim" in blob_low:
        # sector daha spesifikse onu kullan
        sec = _SECTOR_MAP.get(sector)
        if sec and sec != "kampanya":
            return sec
        return "indirim"
    sec_first = (sector or "").split(",")[0].strip()
    mapped = _SECTOR_MAP.get(sec_first)
    if mapped:
        return mapped
    if "bonus" in blob_low and ("tl" in blob_low or "varan" in blob_low):
        return "bonus"
    return "kampanya"


def _extract_price(title: str, desc: str) -> str:
    """Title/desc'ten anlamlı bir 'fiyat'/teklif çıkar.

    Bonus kampanyalarında tipik kalıplar:
      - "1.500 TL bonus" / "X TL'ye varan bonus"
      - "%10 iade" / "%20 chargeback"
      - "12 taksit" / "9 taksit + 3 erteleme"
      - "Ücretsiz"
    """
    blob = (title + " | " + desc).strip()
    low = _ascii_lower(blob)

    if "ucretsiz" in low or "bedava" in low:
        return "Ücretsiz"

    # %X chargeback / iade
    m = re.search(r"%\s*(\d{1,3})\s*(chargeback|iade|geri)", low)
    if m:
        kw = m.group(2)
        kind = "chargeback" if kw == "chargeback" else "iade"
        return f"%{m.group(1)} {kind}"

    # X TL chargeback
    m = re.search(r"(\d{1,4}(?:\.\d{3})*)\s*tl[^a-z0-9]{0,6}chargeback", low)
    if m:
        return f"{m.group(1)} TL chargeback"

    # X TL'ye varan bonus / X TL bonus
    m = re.search(r"(\d{1,4}(?:\.\d{3})*)\s*tl(?:'?ye)?\s*(?:varan\s*)?bonus", low)
    if m:
        return f"{m.group(1)} TL bonus"

    # X+Y taksit (örn. "9+3 taksit")
    m = re.search(r"\b(\d{1,2})\s*\+\s*(\d{1,2})\s*taksit", low)
    if m:
        return f"{m.group(1)}+{m.group(2)} taksit"

    # X taksit
    m = re.search(r"\b(\d{1,2})\s*taksit\b", low)
    if m:
        return f"{m.group(1)} taksit"

    # %X indirim
    m = re.search(r"%\s*(\d{1,3})\s*indirim", low)
    if m:
        return f"%{m.group(1)} indirim"
    m = re.search(r"%\s*(\d{1,3})\b", low)
    if m:
        return f"%{m.group(1)}"

    # X TL indirim/hediye
    m = re.search(r"(\d{1,4}(?:\.\d{3})*)\s*tl[^a-z0-9]{0,6}(indirim|hediye)", low)
    if m:
        kind = "indirim" if m.group(2) == "indirim" else "hediye"
        return f"{m.group(1)} TL {kind}"

    # Sadece bonus kelimesi varsa
    if "bonus" in low:
        return "Bonus"

    return "Kampanya"


def _parse_cards(html: str) -> list[dict]:
    deals: list[dict] = []
    seen: set[str] = set()

    for m in _CARD_RE.finditer(html):
        attrs_blob = m.group("attrs")
        body = m.group("body")
        attrs = dict(_ATTR_RE.findall(attrs_blob))

        href_m = _HREF_RE.search(body)
        if not href_m:
            continue
        href = href_m.group(1).strip()
        # Relative URL'leri normalize et (../kampanyalar/... olabiliyor)
        if href.startswith("../"):
            href = "/" + href.lstrip("./")
        if not href.startswith("/"):
            href = "/" + href
        link = BASE + href

        # Sadece gerçek kampanya detay URL'leri /kampanyalar/<slug> formunda.
        # /garantipay, /bonusflas gibi marka sayfalarını filtrele.
        if not href.startswith("/kampanyalar/"):
            continue
        if link in seen:
            continue
        seen.add(link)

        title_m = _TITLE_RE.search(body)
        title = _clean_text(title_m.group(1)) if title_m else ""
        if not title or len(title) < 4:
            # Fallback: aria-label
            aria_m = _ARIA_RE.search(body)
            if aria_m:
                title = _clean_text(aria_m.group(1))
                # "Kampanya - <gerçek başlık>" temizle
                title = re.sub(r"^Kampanya\s*-\s*", "", title)
        if not title or len(title) < 4:
            continue
        title = title[:200]

        # Image: webp önce, fallback jpg
        image = ""
        webp_m = _WEBP_RE.search(body)
        if webp_m:
            image = webp_m.group(1).strip()
        else:
            img_m = _IMG_SRC_RE.search(body)
            if img_m:
                image = img_m.group(1).strip()
        if image.startswith("//"):
            image = "https:" + image
        elif image.startswith("/"):
            image = BASE + image

        sector = attrs.get("data-sector", "")
        # data-text kampanyanın açıklamasını da içeriyor — category/price ipucu
        desc = attrs.get("data-text") or attrs.get("data-name") or ""
        desc = _clean_text(desc)[:600]

        blob_low = _ascii_lower(title + " " + desc)
        price = _extract_price(title, desc)
        cat = _detect_category(sector, blob_low, attrs)

        deals.append({
            "title": title,
            "price": price,
            "discount_percentage": 0,
            "link": link,
            "image": image,
            "source": "bonus",
            "category": cat,
            "last_updated": datetime.now().isoformat(),
        })
    return deals


async def scrape_bonus_deals(
    output_file: str,
    category: str = "kampanya",
    min_discount: int = 0,
    max_pages: int = 1,
    category_url: str | None = None,
):
    """Bonus (Garanti BBVA) kampanya sayfasını çeker.

    Sayfa tek sayfalık, tüm kampanyalar HTML'e gömülü (~200+ kart).
    max_pages parametresi kullanılmıyor — sadece imza tutarlılığı için.
    Adaylar sırayla denenir; ilk 200 dönen + kampanya kartı içeren kazanır.
    """
    urls = [category_url] if category_url else CANDIDATE_URLS
    print(f"[Bonus] {len(urls)} URL denenecek", flush=True)

    loop = asyncio.get_running_loop()
    html = None
    chosen_url = None
    for url in urls:
        if not url:
            continue
        print(f"[Bonus] -> {url}", flush=True)
        h = await loop.run_in_executor(None, _fetch, url)
        if not h:
            continue
        # Kampanya kartı içeriyor mu hızlı kontrol
        if "campaign-box check-box-item" in h:
            html = h
            chosen_url = url
            break
        else:
            print(f"[Bonus]    sayfa indi ama kampanya kartı yok ({len(h)} bytes)", flush=True)

    if not html:
        print("[Bonus] HTML alınamadı — fallback Playwright gerekebilir", flush=True)
        return

    print(f"[Bonus] Kullanılan URL: {chosen_url} ({len(html)} bytes)", flush=True)
    deals = _parse_cards(html)
    print(f"[Bonus] {len(deals)} kampanya parse edildi", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(
            f"[Bonus] Kaydediliyor: {len(merged)} kampanya (yeni: {len(deals)})...",
            flush=True,
        )
        save_deals(output_file, merged)

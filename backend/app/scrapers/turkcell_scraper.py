"""Turkcell kampanya scraper — turkcell.com.tr/kampanyalar/<kategori>

Next.js SSR + CSS-modules. Class isim'leri hash'li ama prefix sabit:
  - <div class="molecule-offer-card_card__XXXXX"> ... </div>      → kart wrapper
    - <h4 class="molecule-offer-card_card__info__title__XXXXX">TITLE</h4>
    - <div class="molecule-offer-card_card__info__description__XXXXX"><p>...</p></div>
    - <img class="molecule-offer-card_card__header__img__XXXXX" src="HTTPS" />
  - Ana <a href="/kampanyalar/<cat>/<sub>/<slug>"> kartı sarıyor.

/kampanyalar ana sayfası SADECE kategori linklerini render ediyor; gerçek
kampanya kartları alt-sayfalarda. Alt-sayfalar 308-redirect ile kendi
default sekmesine (örn. /yeni-turkcell-musterisi) gidiyor — `curl -L` taklit.

Statik HTML yeterli; Playwright gerekmez. Urllib gzip decode etmediği için
manuel `gzip.decompress` lazım.
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


BASE = "https://www.turkcell.com.tr"
LIST_URL = f"{BASE}/kampanyalar"

# Gerçek kampanya kartları bu kategori sayfalarında. Ana /kampanyalar
# sayfasında sadece bu kategorilerin linkleri var.
SUB_PAGES = [
    "/kampanyalar/mobil-hat-data-hatti-kampanyalari",
    "/kampanyalar/dijital-servis-kampanyalari",
    "/kampanyalar/marka-kampanyalari",
    "/kampanyalar/diger-kampanyalar",
    "/kampanyalar/basvuru-suresi-dolanlar",
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


# Kart wrapper'ı: en yakın <a href="/kampanyalar/.../.../slug"> sarmalıyor.
# Slug 3+ segmentli (alt sayfa düzeyinde gerçek kampanya).
_CARD_RE = re.compile(
    r'<a href="(/kampanyalar/[a-z0-9-]+/[a-z0-9-]+/[a-z0-9-]+(?:/[a-z0-9-]+)*)"'
    r'>\s*<div class="molecule-offer-card_card__[^"]+">(.*?)</a>',
    re.DOTALL,
)
_IMG_RE = re.compile(
    r'<img[^>]*class="molecule-offer-card_card__header__img[^"]*"[^>]*src="([^"]+)"',
    re.DOTALL,
)
_TITLE_RE = re.compile(
    r'<h4 class="molecule-offer-card_card__info__title[^"]*">(.*?)</h4>',
    re.DOTALL,
)
_DESC_RE = re.compile(
    r'<div class="molecule-offer-card_card__info__description[^"]*">(.*?)</div>',
    re.DOTALL,
)


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
            return raw.decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[Turkcell] fetch error {url}: {e}", flush=True)
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


def _detect_category(title: str, desc: str, page_slug: str) -> str:
    t = _ascii_lower(title + " " + desc)
    page = _ascii_lower(page_slug)

    if "ev-interneti" in page or "ev interneti" in t or "fiber" in t or "superonline" in t:
        return "ev-interneti"
    if "ucretsiz" in t or "bedava" in t:
        return "ucretsiz-internet" if ("gb" in t or "internet" in t) else "ucretsiz-hediye"
    if re.search(r"\d+\s*gb\b", t) and ("hediye" in t or "bedava" in t or "ek" in t):
        return "gb-hediye"
    if "faturasiz" in page or "faturasiz" in t:
        return "faturasiz"
    if "faturali" in t or "platinum" in t:
        return "faturali"
    if "marka" in page:
        return "marka"
    if "dijital-servis" in page or "tv plus" in t or "fizy" in t or "lifebox" in t:
        return "dijital-servis"
    if "hediye" in t:
        return "hediye"
    if "indirim" in t:
        return "indirim"
    return "kampanya"


def _extract_price(title: str, desc: str) -> str:
    """Title/desc'ten anlamlı bir 'fiyat'/teklif çıkar."""
    blob = (title + " | " + desc).strip()
    low = _ascii_lower(blob)

    # 1) "X ay/gün ücretsiz"
    m = re.search(r"(\d+)\s*(ay|gun|hafta)\s*ucretsiz", low)
    if m:
        unit = {"ay": "ay", "gun": "gün", "hafta": "hafta"}[m.group(2)]
        return f"{m.group(1)} {unit} ücretsiz"

    if "ucretsiz" in low or "bedava" in low:
        return "Ücretsiz"

    # 2) "X GB hediye/ek/bedava"
    m = re.search(r"(\d+)\s*gb\b(?:[^a-z0-9]{1,20}(hediye|bedava|ek|sosyal|internet))?", low)
    if m:
        kw = m.group(2)
        if kw == "ek":
            return f"{m.group(1)} GB ek"
        return f"{m.group(1)} GB hediye"

    # 3) "X dakika" hediye
    m = re.search(r"(\d{2,5})\s*(?:dakika|dk)\b", low)
    if m and ("hediye" in low or "her yone" in low or "5000" in m.group(1)):
        return f"{m.group(1)} dk hediye"

    # 4) "X TL/ay" / "X TL'den"
    m = re.search(r"(\d{1,4}(?:\.\d{3})*)\s*tl\s*/?\s*ay\b", low)
    if m:
        return f"{m.group(1)} TL/ay"

    # 5) "X TL indirim/hediye/ceki"
    m = re.search(r"(\d{1,4}(?:\.\d{3})*)\s*tl(?:'?lik|'?lik)?\s*(indirim|hediye|ceki|money|cek)?", low)
    if m:
        kind_raw = (m.group(2) or "indirim").strip()
        kind_map = {"ceki": "çeki", "cek": "çeki", "money": "para", "indirim": "indirim", "hediye": "hediye"}
        return f"{m.group(1)} TL {kind_map.get(kind_raw, kind_raw)}"

    # 6) "%X indirim"
    m = re.search(r"%\s*(\d{1,3})", low)
    if m:
        return f"%{m.group(1)} indirim"

    return "Kampanya"


def _parse_cards(html: str, page_slug: str) -> list[dict]:
    deals: list[dict] = []
    seen: set[str] = set()

    for href, body in _CARD_RE.findall(html):
        link = BASE + href
        if link in seen:
            continue
        seen.add(link)

        img_m = _IMG_RE.search(body)
        image = ""
        if img_m:
            image = img_m.group(1).strip()
            if image.startswith("//"):
                image = "https:" + image
            elif image.startswith("/"):
                image = BASE + image

        title_m = _TITLE_RE.search(body)
        title = _clean_text(title_m.group(1)) if title_m else ""
        if not title or len(title) < 3:
            continue
        title = title[:180]

        desc_m = _DESC_RE.search(body)
        desc = _clean_text(desc_m.group(1)) if desc_m else ""
        # Çok uzun açıklamayı price extract için kısaltıyoruz (regex hızı).
        desc_short = desc[:600]

        price = _extract_price(title, desc_short)
        cat = _detect_category(title, desc_short, page_slug)

        deals.append({
            "title": title,
            "price": price,
            "discount_percentage": 0,
            "link": link,
            "image": image,
            "source": "turkcell",
            "category": cat,
            "last_updated": datetime.now().isoformat(),
        })
    return deals


async def scrape_turkcell_deals(
    output_file: str,
    category: str = "kampanya",
    min_discount: int = 0,
    max_pages: int = 1,
    category_url: str | None = None,
):
    """Turkcell kampanya kategori sayfalarını çeker.

    max_pages: kaç kategori sayfası taransın. max_pages=1 ise sadece ilk
    SUB_PAGES kategorisi; >=len(SUB_PAGES) ise hepsi.
    """
    targets: list[tuple[str, str]] = []
    if category_url:
        slug = category_url.replace(BASE, "") or "/kampanyalar"
        targets.append((category_url, slug))
    else:
        for sub in SUB_PAGES[:max_pages]:
            targets.append((BASE + sub, sub))
        if not targets:
            targets.append((LIST_URL, "/kampanyalar"))

    print(f"[Turkcell] {len(targets)} kategori taranacak", flush=True)

    loop = asyncio.get_running_loop()
    all_deals: list[dict] = []
    seen_global: set[str] = set()

    for url, slug in targets:
        print(f"[Turkcell] -> {url}", flush=True)
        html = await loop.run_in_executor(None, _fetch, url)
        if not html:
            continue
        page_deals = _parse_cards(html, slug)
        before = len(all_deals)
        for d in page_deals:
            if d["link"] in seen_global:
                continue
            seen_global.add(d["link"])
            all_deals.append(d)
        print(
            f"[Turkcell]    {len(page_deals)} kart, "
            f"{len(all_deals) - before} yeni eklendi",
            flush=True,
        )

    print(f"[Turkcell] Toplam {len(all_deals)} kampanya parse edildi", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, all_deals)
        print(
            f"[Turkcell] Kaydediliyor: {len(merged)} kampanya "
            f"(yeni: {len(all_deals)})...",
            flush=True,
        )
        save_deals(output_file, merged)

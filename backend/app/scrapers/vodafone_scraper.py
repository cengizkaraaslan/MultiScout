"""Vodafone TR kampanya scraper — vodafone.com.tr/kampanyalar

Server-side render edilmiş HTML. Her kampanya tek satır <a> elementi:
  <a title="" href="/kampanyalar/SLUG" class="cmp-card "
     data-item_id="..." data_item_title="">
    <div class="cmp-content "><div class="img-block-hover">
      <div class="img-block">
        <img class="lazyload" src="HTTPS_BANNER_URL" alt="UZUN_BASLIK"/>
      </div>
    </div>
    <div class="text-content "><strong>KISA_BASLIK</strong></div>
  </a>

Birden çok alt-sayfa var: ana /kampanyalar listesi + alt başlıklar
(faturasiz-kampanyalar, ev-interneti-kampanyalari, red-marka-ayricaliklari).
max_pages parametresi kaç alt-sayfayı tarayacağımızı belirler.
"""
import asyncio
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime
from html import unescape

from app.scrapers.io import get_file_lock, load_deals, merge_deals_by_link, save_deals


BASE = "https://www.vodafone.com.tr"
LIST_URL = f"{BASE}/kampanyalar"

# Alt-sayfalar — max_pages kadarı taranır (ana sayfa hariç).
SUB_PAGES = [
    "/kampanyalar/faturasiz-kampanyalar",
    "/kampanyalar/ev-interneti-kampanyalari",
    "/kampanyalar/red-marka-ayricaliklari",
    "/kampanyalar/freezone-guzellikleri",
    "/kampanyalar/kupon-kodu-kampanyalari",
]

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

# Bir kampanya kartı <a class="cmp-card "> ... </a>. href ve class arasında
# newline + boşluk var (HTML kaynağında öyle render ediliyor), bu yüzden
# DOTALL şart.
_CARD_RE = re.compile(
    # href değeri "/kampanyalar/slug\n          " gibi multi-line olabilir.
    # slug = ilk whitespace/" /? karakterine kadar olan kısım.
    r'<a[^>]*href="(/kampanyalar/[^\s"?#]+)[^"]*"\s*class="cmp-card[^"]*"(.*?)</a>',
    re.DOTALL,
)
_IMG_RE = re.compile(
    r'<img[^>]*src="(https?://[^"]+)"[^>]*alt="([^"]*)"',
    re.DOTALL,
)
_STRONG_RE = re.compile(
    r'<div class="text-content[^"]*"\s*>\s*<strong>(.*?)</strong>',
    re.DOTALL,
)


def _clean_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = unescape(s)
    s = s.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip()


def _clean_href(s: str) -> str:
    # href içinde "  /kampanyalar/slug\n                  " olabiliyor.
    return re.sub(r"\s+", "", s or "")


def _fetch(url: str, timeout: int = 25) -> str | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[Vodafone] fetch error {url}: {e}", flush=True)
        return None


def _detect_category(title: str, alt: str, page_slug: str) -> str:
    """Title+alt+source-sayfa'dan kampanya tipini tahmin et."""
    t = (title + " " + alt).lower()
    t = t.replace("ı", "i").replace("ş", "s").replace("ç", "c").replace("ğ", "g").replace("ü", "u").replace("ö", "o")
    page = page_slug.lower()

    if "ev-interneti" in page or "ev interneti" in t or "fiber" in t:
        return "ev-interneti"
    if "faturasiz" in page or "faturasiz" in t:
        return "faturasiz"
    if "red-marka" in page or "red marka" in t or "red ayricalik" in t:
        return "red-ayricalik"
    if "ucretsiz" in t or "bedava" in t:
        return "ucretsiz-internet" if ("gb" in t or "internet" in t) else "ucretsiz-hediye"
    if re.search(r"\d+\s*gb\b", t) and ("hediye" in t or "bedava" in t):
        return "gb-hediye"
    if "hediye" in t:
        return "hediye"
    if "indirim" in t:
        return "indirim"
    return "kampanya"


def _extract_price(title: str, alt: str) -> str:
    """Title/alt'tan extract edilebilen 'fiyat'/teklif ifadesi."""
    blob = (title + " | " + alt).strip()
    low = blob.lower().replace("ı", "i").replace("ü", "u").replace("ö", "o").replace("ç", "c").replace("ş", "s").replace("ğ", "g")

    # 1) "X ay/gun ucretsiz" → "Ucretsiz"
    m = re.search(r"(\d+)\s*(ay|gun|hafta)\s*ucretsiz", low)
    if m:
        unit_map = {"ay": "ay", "gun": "gün", "hafta": "hafta"}
        return f"{m.group(1)} {unit_map[m.group(2)]} ücretsiz"
    if "ucretsiz" in low or "bedava" in low:
        return "Ücretsiz"

    # 2) "X GB hediye" / "X GB bedava"
    m = re.search(r"(\d+)\s*gb\s*(hediye|bedava|hediyeli)?", low)
    if m:
        return f"{m.group(1)} GB hediye"

    # 3) "X TL indirim" / "X TL hediye" / "X TL'ye varan"
    m = re.search(r"(\d{1,4}(?:\.\d{3})*)\s*tl(?:'?ye)?\s*(varan\s*)?(indirim|hediye|money)?", low)
    if m:
        amount = m.group(1)
        kind = (m.group(3) or "indirim").strip()
        return f"{amount} TL {kind}"

    # 4) "%X indirim"
    m = re.search(r"%\s*(\d{1,3})\s*(indirim|ek\s*indirim)?", low)
    if m:
        return f"%{m.group(1)} indirim"

    # 5) "ikinci(si) hediye/bedava" / "1+1"
    if "ikincisi hediye" in low or "ikinci kahve hediye" in low or "1 alana 1" in low:
        return "İkincisi hediye"

    return "Kampanya"


def _parse_cards(html: str, page_slug: str) -> list[dict]:
    """Verilen HTML'den kampanyaları çıkar."""
    deals: list[dict] = []
    seen_links: set[str] = set()

    for href_raw, body in _CARD_RE.findall(html):
        slug = _clean_href(href_raw)
        if not slug or slug.endswith("/kampanyalar"):
            continue
        link = BASE + slug
        if link in seen_links:
            continue
        seen_links.add(link)

        img_m = _IMG_RE.search(body)
        if not img_m:
            continue
        image = img_m.group(1).strip()
        alt = _clean_text(img_m.group(2))

        strong_m = _STRONG_RE.search(body)
        title = _clean_text(strong_m.group(1)) if strong_m else alt
        if not title or len(title) < 3:
            title = alt
        if not title or len(title) < 3:
            continue
        title = title[:180]

        # Title kısa ise alt'taki daha açıklayıcı metni ek bilgi olarak kullan.
        descriptive = alt if len(alt) > len(title) else title

        price = _extract_price(title, alt)
        cat_slug = _detect_category(title, alt, page_slug)

        deals.append({
            "title": title,
            "price": price,
            "discount_percentage": 0,
            "link": link,
            "image": image,
            "source": "vodafone",
            "category": cat_slug,
            "last_updated": datetime.now().isoformat(),
            # Not: descriptive değişkenini sadece local kullandık; çıktıda
            # alt yerine title'ı tutuyoruz (frontend ile uyumlu).
        })
        _ = descriptive  # noqa — niyet sadece dokümante etmek
    return deals


async def scrape_vodafone_deals(
    output_file: str,
    category: str = "kampanya",
    min_discount: int = 0,
    max_pages: int = 1,
    category_url: str | None = None,
):
    """Vodafone kampanya sayfalarını çeker. max_pages=1 ise sadece ana liste;
    >1 ise SUB_PAGES'den ilk (max_pages-1) tanesi de eklenir.
    """
    targets: list[tuple[str, str]] = []
    if category_url:
        slug = category_url.replace(BASE, "") or "/kampanyalar"
        targets.append((category_url, slug))
    else:
        targets.append((LIST_URL, "/kampanyalar"))
        extras = max(0, max_pages - 1)
        for sub in SUB_PAGES[:extras]:
            targets.append((BASE + sub, sub))

    print(f"[Vodafone] {len(targets)} sayfa taranacak", flush=True)

    loop = asyncio.get_running_loop()
    all_deals: list[dict] = []
    seen_global: set[str] = set()

    for url, slug in targets:
        print(f"[Vodafone] -> {url}", flush=True)
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
            f"[Vodafone]    {len(page_deals)} kart bulundu, "
            f"{len(all_deals) - before} yeni eklendi",
            flush=True,
        )

    print(f"[Vodafone] Toplam {len(all_deals)} kampanya parse edildi", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, all_deals)
        print(
            f"[Vodafone] Kaydediliyor: {len(merged)} kampanya "
            f"(yeni: {len(all_deals)})...",
            flush=True,
        )
        save_deals(output_file, merged)

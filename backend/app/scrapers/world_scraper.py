"""World (Yapı Kredi) kampanya scraper — yapikredi.com.tr/kampanyalar

worldkart.com.tr ve worldlimitsiz.com domainleri artık çözümlenmiyor; gerçek
kampanya kataloğu yapikredi.com.tr içinde:

    /kampanyalar/                       -> 302 -> /kampanyalar/kategori/bireysel/
    /kampanyalar/kategori/bireysel/?data-page=N   (4 sayfa, 6'şar kart)
    /kampanyalar/kategori/kobi/?data-page=N
    /kampanyalar/detay/<id>             (kampanya detayı)

Klasik server-side render edilmiş HTML, çok temiz markup. Her kampanya kartı:

    <div class="item col-md-6 col-sm-12">
      <a href="/kampanyalar/detay/256017" class="...">
        <div class="kampanyalar-img">
          <picture>
            <img alt="Kampanyanın tam başlığı..." data-src="/medium/image/..." />
          </picture>
        </div>
      </a>
      <div class="title ..."><a href="/kampanyalar/detay/256017">Başlık</a></div>
      <div class="text ..."><p><a href="...">Açıklama</a></p></div>
      <a href="/kampanyalar/detay/256017" class="detayli-bilgi">Detaylı Bilgi</a>
    </div>

Trailing slash şart: `/kategori/bireysel?data-page=2` (slash yok) → ana sayfaya
redirect. Pagination URL formu: `?data-page=N` (1 indeksli).

Statik HTML yeterli; Playwright gerekmez. Urllib gzip decode etmediği için
manuel `gzip.decompress` (Turkcell scraper'ından kopya).
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


BASE = "https://www.yapikredi.com.tr"
# Hedef kategori sayfaları + her birinden kaç sayfa taranacağı.
# bireysel: 4 sayfa, kobi: ~3-4 sayfa (script kendisi 1.sayfadaki pager'dan
# total sayıyı bulup max_pages ile sınırlıyor, bu liste sadece startpoint).
LIST_PATHS = [
    "/kampanyalar/kategori/bireysel/",
    "/kampanyalar/kategori/kobi/",
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

# Her bir kampanya kartı: <div class="item col-md-6 col-sm-12"> wrapper'ı.
# Strateji: tüm "item col-md-6 col-sm-12" başlangıçlarında split — sonuncusu
# da pager'a kadar uzanır. lookahead'i sadece "next card OR pager div" yap.
_CARD_RE = re.compile(
    r'<div class="item col-md-6 col-sm-12">(.*?)(?=<div class="item col-md-6 col-sm-12">|<div class="pager">|<ul class="pager)',
    re.DOTALL,
)
_LINK_RE = re.compile(r'href="(/kampanyalar/detay/\d+)"')
# Başlık tercih sırası: <img alt="..."> > <div class="title"><a>...</a>.
# alt en uzun ve doğru olanı.
_IMG_RE = re.compile(
    r'<img[^>]*alt="([^"]+)"[^>]*data-src="([^"]+)"',
    re.DOTALL,
)
_IMG_FALLBACK_RE = re.compile(
    r'<img[^>]*alt="([^"]+)"',
    re.DOTALL,
)
_TITLE_RE = re.compile(
    r'<div class="title[^"]*">\s*<a[^>]*>(.*?)</a>\s*</div>',
    re.DOTALL,
)
_DESC_RE = re.compile(
    r'<div class="text[^"]*">\s*<p>\s*<a[^>]*>(.*?)</a>\s*</p>',
    re.DOTALL,
)
# Pagination: <li data-page="N"><a ...>N</a></li>  — son sayfa N.
_PAGER_RE = re.compile(r'<li[^>]*data-page="(\d+)"')


def _clean_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = unescape(s)
    s = s.replace("\xa0", " ").replace("​", "")
    s = s.replace("’", "'").replace("‘", "'").replace("–", "-")
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
        print(f"[World] fetch error {url}: {e}", flush=True)
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

    # Spesifik olanlar önce.
    if "sinema" in t or "cinemaximum" in t or "cinepol" in t:
        return "sinema"
    if "restoran" in t or "yemek" in t or "fuudy" in t or "kafe" in t:
        return "restoran"
    if "market" in t or "carrefour" in t or "migros" in t or "a101" in t or "bim" in t or "sok" in t:
        return "market"
    if "akaryakit" in t or "opet" in t or "shell" in t or "petrol" in t:
        return "akaryakit"
    if "otel" in t or "seyahat" in t or "tatil" in t or "ucak" in t or "uçak" in t or "rezervasyon" in t:
        return "seyahat"
    if "chargeback" in t or "iade" in t:
        return "chargeback"
    if "worldpuan" in t or "puan" in t:
        return "puan"
    if re.search(r"\d+\s*\+\s*\d+\s*taksit", t) or "taksit" in t:
        return "taksit"
    if "kobi" in page or "tuzel" in t or "business" in t or "isyeri" in t or "ticari" in t:
        return "kobi"
    return "kampanya"


def _extract_price(title: str, desc: str) -> str:
    """Title + desc'den anlamlı bir 'fiyat'/teklif teaser üret."""
    blob = (title + " | " + desc).strip()
    low = _ascii_lower(blob)

    # 1) Ücretsiz / bedava
    if "ucretsiz" in low or "bedava" in low:
        return "Ücretsiz"

    # 2) "X TL chargeback / iade"
    m = re.search(r"(\d{1,4}(?:\.\d{3})*)\s*tl[^a-z]{0,20}(chargeback|iade)", low)
    if m:
        kind = "chargeback" if m.group(2) == "chargeback" else "iade"
        return f"{m.group(1)} TL {kind}"

    # 3) "%X iade / indirim / chargeback"
    m = re.search(r"%\s*(\d{1,3})\s*(iade|indirim|chargeback|geri)?", low)
    if m:
        kind = m.group(2) or "indirim"
        kind_map = {"geri": "iade", "iade": "iade", "indirim": "indirim", "chargeback": "chargeback"}
        return f"%{m.group(1)} {kind_map.get(kind, kind)}"

    # 4) "X worldpuan" / "X puan"
    m = re.search(r"(\d{1,4}(?:\.\d{3})*)\s*(worldpuan|puan)", low)
    if m:
        return f"{m.group(1)} {m.group(2)}"

    # 5) Taksit: "X+Y taksit" / "X taksit"
    m = re.search(r"(\d{1,2})\s*\+\s*(\d{1,2})\s*taksit", low)
    if m:
        return f"{m.group(1)}+{m.group(2)} taksit"
    m = re.search(r"(\d{1,2})\s*taksit", low)
    if m:
        return f"{m.group(1)} taksit"

    # 6) "X TL'ye varan" / "X TL hediye"
    m = re.search(r"(\d{1,4}(?:\.\d{3})*)\s*tl(?:'?ye|'?ye)?\s*(varan|hediye|nakit|indirim)", low)
    if m:
        return f"{m.group(1)} TL {m.group(2)}"

    # 7) Sadece "X TL"
    m = re.search(r"(\d{1,4}(?:\.\d{3})*)\s*tl\b", low)
    if m:
        return f"{m.group(1)} TL"

    return "Kampanya"


def _parse_cards(html: str, page_slug: str) -> list[dict]:
    deals: list[dict] = []
    seen: set[str] = set()

    for card in _CARD_RE.findall(html):
        link_m = _LINK_RE.search(card)
        if not link_m:
            continue
        link = BASE + link_m.group(1)
        if link in seen:
            continue
        seen.add(link)

        # Title: <img alt="..."> tercih (en uzun + temiz). Olmazsa .title <a>.
        title = ""
        image = ""
        img_m = _IMG_RE.search(card)
        if img_m:
            title = _clean_text(img_m.group(1))
            img_src = img_m.group(2).strip()
            if img_src.startswith("/"):
                image = BASE + img_src
            elif img_src.startswith("//"):
                image = "https:" + img_src
            else:
                image = img_src
        else:
            alt_m = _IMG_FALLBACK_RE.search(card)
            if alt_m:
                title = _clean_text(alt_m.group(1))
        if not title:
            t_m = _TITLE_RE.search(card)
            if t_m:
                title = _clean_text(t_m.group(1))
        if not title or len(title) < 5:
            continue
        title = title[:200]

        desc_m = _DESC_RE.search(card)
        desc = _clean_text(desc_m.group(1)) if desc_m else ""
        desc_short = desc[:600]

        price = _extract_price(title, desc_short)
        cat = _detect_category(title, desc_short, page_slug)

        deals.append({
            "title": title,
            "price": price,
            "discount_percentage": 0,
            "link": link,
            "image": image,
            "source": "world",
            "category": cat,
            "last_updated": datetime.now().isoformat(),
        })
    return deals


def _detect_total_pages(html: str) -> int:
    nums = [int(n) for n in _PAGER_RE.findall(html)]
    return max(nums) if nums else 1


async def scrape_world_deals(
    output_file: str,
    category: str = "kampanya",
    min_discount: int = 0,
    max_pages: int = 1,
    category_url: str | None = None,
):
    """Yapı Kredi World kampanya sayfalarını çeker.

    max_pages: HER kategori için maksimum kaç sayfa taransın. Toplam tarama
    = len(kategori_listesi) * min(max_pages, gerçek_pager_total).
    category_url: tek bir kategori başlangıç URL'i verilirse sadece o
    çekilir; pagination yine aynı şekilde uygulanır.
    """
    if category_url:
        slug = category_url.replace(BASE, "") or "/kampanyalar/kategori/bireysel/"
        if not slug.endswith("/"):
            slug += "/"
        start_paths = [slug]
    else:
        start_paths = list(LIST_PATHS)

    print(f"[World] {len(start_paths)} kategori, max {max_pages} sayfa", flush=True)

    loop = asyncio.get_running_loop()
    all_deals: list[dict] = []
    seen_global: set[str] = set()

    for path in start_paths:
        # 1. sayfayı çek, pager'dan total sayıyı al.
        first_url = BASE + path
        print(f"[World] -> {first_url}", flush=True)
        html = await loop.run_in_executor(None, _fetch, first_url)
        if not html:
            continue

        page_deals = _parse_cards(html, path)
        for d in page_deals:
            if d["link"] in seen_global:
                continue
            seen_global.add(d["link"])
            all_deals.append(d)
        print(f"[World]    sayfa 1: {len(page_deals)} kart", flush=True)

        total = _detect_total_pages(html)
        upto = min(max_pages, total)
        for p in range(2, upto + 1):
            url = f"{first_url}?data-page={p}"
            print(f"[World] -> {url}", flush=True)
            page_html = await loop.run_in_executor(None, _fetch, url)
            if not page_html:
                continue
            page_deals = _parse_cards(page_html, path)
            new_count = 0
            for d in page_deals:
                if d["link"] in seen_global:
                    continue
                seen_global.add(d["link"])
                all_deals.append(d)
                new_count += 1
            print(f"[World]    sayfa {p}: {len(page_deals)} kart, {new_count} yeni", flush=True)

    print(f"[World] Toplam {len(all_deals)} kampanya parse edildi", flush=True)

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, all_deals)
        print(
            f"[World] Kaydediliyor: {len(merged)} kampanya "
            f"(yeni: {len(all_deals)})...",
            flush=True,
        )
        save_deals(output_file, merged)

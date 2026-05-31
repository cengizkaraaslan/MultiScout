"""Maximum (İş Bankası) kampanya scraper — maximum.com.tr/kampanyalar

Klasik server-side render. Her kampanya kartı `_campDiv` ID'li bir col
wrapper içinde:
  - <div id="..._campDiv" class="col mt-30 cat<N> [past-campaign ...]">
    - <div class="card shadow-lg card-anm-1">
        - <picture><img class="...card-img-top..." src='/contentmanagement/...'
            alt='TITLE' /></picture>
        - <h3 class="card-text">TITLE</h3>
        - <a href="/kampanyalar/<slug>">Detaylı Bilgi</a>

Statik HTML ~8MB ama tam render; Playwright gerekmiyor. Gzip Accept-Encoding
gönderiyoruz ama upstream identity dönüyor — yine de gzip/deflate decode
yolu Turkcell scraper'ından kopyalanmış halde.

`price` alanı: title'dan "X TL MaxiPuan", "%X indirim", "X+1 taksit",
"X TL chargeback" gibi anlamlı bir teaser; çıkarılamazsa "Kampanya".
`discount_percentage` her zaman 0 (banka kampanyaları indirim yüzdesi
değil, puan/chargeback).
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


BASE = "https://www.maximum.com.tr"
# Sırasıyla dene — ilk 200 dönen URL kullanılır.
CANDIDATE_URLS = [
    f"{BASE}/kampanyalar",
    f"{BASE}/firsatlar",
    "https://www.maximummobil.com.tr/kampanyalar",
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

# Bir kampanya kartı, _campDiv ID'li col wrapper ile başlıyor. Sonraki
# _campDiv'e ya da dosya sonuna kadar al — DOTALL ile çok satırlı.
_CARD_SPLIT_RE = re.compile(r'(?=<div id="[^"]+_campDiv" class="col mt-30)')

# Card içinden: /kampanyalar/<slug> ilk eşleşme (Detaylı Bilgi linki).
_LINK_RE = re.compile(r'href="(/kampanyalar/[a-z0-9-]+)"')
_TITLE_RE = re.compile(r'<h3 class="card-text">(.*?)</h3>', re.DOTALL)
# <img ... src='...' alt='...' /> — single quote'lu attribute.
_IMG_RE = re.compile(
    r"<img[^>]*class=\"[^\"]*card-img-top[^\"]*\"[^>]*src='([^']+)'(?:[^>]*alt='([^']*)')?",
    re.DOTALL,
)
# Past-campaign (geçmiş kampanya) — atla.
_PAST_RE = re.compile(r'class="col mt-30 cat\d+ past-campaign')


def _clean_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = unescape(s)
    s = s.replace("\xa0", " ").replace("​", "")
    s = s.replace("’", "'").replace("‘", "'").replace("`", "'")
    return re.sub(r"\s+", " ", s).strip()


def _fetch(url: str, timeout: int = 30) -> tuple[int, str | None]:
    """Returns (status, body_or_None)."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as r:
            status = r.status
            raw = r.read()
            enc = (r.headers.get("Content-Encoding") or "").lower()
            if enc == "gzip":
                raw = gzip.decompress(raw)
            elif enc == "deflate":
                try:
                    raw = zlib.decompress(raw)
                except zlib.error:
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            return status, raw.decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        print(f"[Maximum] HTTP {e.code} {url}", flush=True)
        return e.code, None
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"[Maximum] fetch error {url}: {e}", flush=True)
        return 0, None


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


def _detect_category(title: str, desc: str = "") -> str:
    t = _ascii_lower(title + " " + desc)
    # Chargeback / geri ödeme / iade — önce kontrol (puan'dan ayrı bir kova).
    if "chargeback" in t or "geri odeme" in t or re.search(r"\biade\b", t):
        return "chargeback"
    # Sinema
    if "sinema" in t or "cinemaximum" in t or "biletinial" in t or "biletix" in t:
        return "sinema"
    # Seyahat — uçak, otel, tur, THY, Pegasus...
    if re.search(
        r"\b(ucak|ucus|otel|tur|seyahat|tatil|rezervasyon|bilet|thy|pegasus|"
        r"sunexpress|etstur|ets|jolly|tatilbudur|trivago|booking|enuygun|"
        r"obilet|ucuzabilet|aegean|airlines|airline|havayolu|havalimani)\b",
        t,
    ):
        return "seyahat"
    # Market / gıda
    if re.search(
        r"\b(market|bim|a101|sok|migros|carrefour|file|hakmar|macrocenter|"
        r"sokmarket|gida|getir|banabi|istegelsin|trendyol\s*go)\b",
        t,
    ):
        return "market"
    # Restoran / yemek
    if re.search(
        r"\b(restoran|yemeksepeti|getiryemek|trendyol\s*yemek|cafe|kafe|"
        r"kahve|lokanta|burger|pizza|fast\s*food)\b",
        t,
    ):
        return "restoran"
    # Taksit
    if re.search(
        r"\b(taksit|pesin\s*fiyat|ek\s*taksit|x?\s*\+?\s*\d+\s*taksit|"
        r"sonradan\s+taksit)\b",
        t,
    ) or re.search(r"\b\d+\s*\+\s*\d+\b", t):
        return "taksit"
    # Puan / Maxipuan — chargeback dışındaki para iadesi tipi kampanyalar.
    if "maxipuan" in t or "puan" in t or "maximil" in t:
        return "puan"
    return "kampanya"


def _extract_price(title: str, desc: str = "") -> str:
    """Title'dan anlamlı bir 'teklif' string'i çıkar.

    Öncelik: TL MaxiPuan miktarı > %X indirim/iade > X+Y taksit > X kat puan >
    Ücretsiz > Kampanya.
    """
    blob = title + " | " + desc
    low = _ascii_lower(blob)

    # 1) "X TL'ye varan MaxiPuan" / "X TL MaxiPuan"
    m = re.search(
        r"(\d{1,3}(?:[.\s]\d{3})*|\d+)\s*tl(?:'?ye)?\s*(?:varan\s+)?maxipuan",
        low,
    )
    if m:
        amt = m.group(1).replace(" ", ".").replace("..", ".")
        return f"{amt} TL MaxiPuan"

    # 2) "%X indirim/iade"
    m = re.search(r"%\s*(\d{1,3})\s*(indirim|iade|geri)?", low)
    if m:
        kind_raw = (m.group(2) or "indirim").strip()
        kind_map = {"iade": "iade", "geri": "iade", "indirim": "indirim"}
        return f"%{m.group(1)} {kind_map.get(kind_raw, 'indirim')}"

    # 3) "X TL indirim" (yüzde değil, sabit tutar)
    m = re.search(
        r"(\d{1,3}(?:[.\s]\d{3})*|\d+)\s*tl(?:'?lik|'?lik)?\s*(indirim|iade|chargeback)",
        low,
    )
    if m:
        amt = m.group(1).replace(" ", ".").replace("..", ".")
        kind = m.group(2)
        kind_map = {"indirim": "indirim", "iade": "iade", "chargeback": "chargeback"}
        return f"{amt} TL {kind_map.get(kind, kind)}"

    # 4) "X+Y taksit" / "X aya varan taksit"
    m = re.search(r"\b(\d{1,2})\s*\+\s*(\d{1,2})\s*taksit", low)
    if m:
        return f"{m.group(1)}+{m.group(2)} taksit"
    m = re.search(r"(\d{1,2})\s*ay(?:a)?\s*(?:varan\s+)?taksit", low)
    if m:
        return f"{m.group(1)} ay taksit"
    if "pesin fiyat" in low and "taksit" in low:
        return "Peşin fiyatına taksit"

    # 5) "X kat puan" / "X kat MaxiPuan"
    m = re.search(r"(\d{1,2})\s*(?:kat|x)\s*(maxi)?puan", low)
    if m:
        return f"{m.group(1)}x puan"

    # 6) "X TL'ye varan" (puan tipi belirtilmemiş)
    m = re.search(r"(\d{1,3}(?:[.\s]\d{3})*|\d+)\s*tl(?:'?ye)?\s*varan", low)
    if m:
        amt = m.group(1).replace(" ", ".").replace("..", ".")
        return f"{amt} TL'ye varan"

    # 7) "Ücretsiz" / "Bedava"
    if "ucretsiz" in low or "bedava" in low:
        return "Ücretsiz"

    return "Kampanya"


def _parse_cards(html: str) -> list[dict]:
    deals: list[dict] = []
    seen: set[str] = set()

    chunks = _CARD_SPLIT_RE.split(html)
    # İlk chunk header — kart değil; gerisi her bir col wrapper.
    for chunk in chunks[1:]:
        # Sadece kart'ın kendi kapsamını dikkate al (sonraki kartı kesmek
        # için zaten splitter ayırmış). past-campaign'i atla.
        head = chunk[:300]
        if _PAST_RE.search(head):
            continue

        link_m = _LINK_RE.search(chunk)
        if not link_m:
            continue
        slug = link_m.group(1).strip()
        # #gecmis fragment'lı linkleri at; arşiv kayıtları.
        if "#gecmis" in slug or slug.endswith("/gecmis"):
            continue
        link = BASE + slug
        if link in seen:
            continue
        seen.add(link)

        title_m = _TITLE_RE.search(chunk)
        title = _clean_text(title_m.group(1)) if title_m else ""
        if len(title) < 3:
            continue
        title = title[:200]

        img_m = _IMG_RE.search(chunk)
        image = ""
        alt_title = ""
        if img_m:
            image_path = img_m.group(1).strip()
            alt_title = _clean_text(img_m.group(2) or "")
            if image_path.startswith("//"):
                image = "https:" + image_path
            elif image_path.startswith("/"):
                image = BASE + image_path
            elif image_path.startswith("http"):
                image = image_path

        price = _extract_price(title, alt_title)
        cat_slug = _detect_category(title, alt_title)

        deals.append({
            "title": title,
            "price": price,
            "discount_percentage": 0,
            "link": link,
            "image": image,
            "source": "maximum",
            "category": cat_slug,
            "last_updated": datetime.now().isoformat(),
        })
    return deals


async def scrape_maximum_deals(
    output_file: str,
    category: str = "kampanya",
    min_discount: int = 0,
    max_pages: int = 1,
    category_url: str | None = None,
):
    """Maximum kampanyalar sayfasını çeker.

    Tek liste sayfası — `max_pages` sınırı pratikte uygulanmıyor (site
    sayfalama yapmıyor; tek sayfada ~200 kart döner). `category_url`
    verilirse o URL kullanılır.
    """
    loop = asyncio.get_running_loop()

    urls: list[str] = [category_url] if category_url else list(CANDIDATE_URLS)
    html: str | None = None
    used_url: str | None = None
    for url in urls:
        if not url:
            continue
        print(f"[Maximum] Deniyor: {url}", flush=True)
        status, body = await loop.run_in_executor(None, _fetch, url)
        if status == 200 and body and "_campDiv" in body:
            html = body
            used_url = url
            print(f"[Maximum] OK  ({status}, {len(body) // 1024} KB)", flush=True)
            break
        print(f"[Maximum] Atla: status={status}, body_len={len(body) if body else 0}", flush=True)

    if not html:
        print("[Maximum] Hiçbir aday URL'den kullanılabilir HTML alınamadı", flush=True)
        return

    deals = _parse_cards(html)
    print(
        f"[Maximum] {used_url} -> {len(deals)} kampanya parse edildi",
        flush=True,
    )

    async with get_file_lock(output_file):
        existing = load_deals(output_file)
        merged = merge_deals_by_link(existing, deals)
        print(
            f"[Maximum] Toplam {len(merged)} kampanya (yeni: {len(deals)})...",
            flush=True,
        )
        save_deals(output_file, merged)
